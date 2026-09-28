"""Subsystem Keyboard — emulação de teclado virtual via uinput.

Introduzido em FEAT-KEYBOARD-EMULATOR-01. Encapsula criação, despacho e
destruição do `UinputKeyboardDevice`. Ativado por padrão: a instalação do
daemon já espera que os 4 botões default (Options/Share/L1/R1) emitam teclas
correspondentes assim que o serviço sobe.

EMULACAO-NO-JOGO-01 (29/07) corrigiu a assimetria que este cabeçalho declarava:
o teclado NÃO tinha toggle explícito nenhum — nem gate de criação, nem flag em
disco, nem IPC —, e por isso o R1 (Alt+Tab, `core/keyboard_mappings.py`)
trocava de aplicativo no meio da partida dela. Agora `keyboard_emulation_enabled`
é respeitado no gate de criação abaixo (molde de `subsystems/mouse.py`), a
preferência é persistida em `keyboard_emulation.flag`
(`utils/session.py:save_keyboard_emulation`) e o runtime alterna por
`keyboard.emulation.set`. O default continua LIGADO — desligar tira também o
teclado virtual do sistema (L3/R3) e as três regiões do touchpad.

Wire-up no Daemon (armadilha A-07 — 3 pontos):
  1. Slot `_keyboard_device: Any = None` em `Daemon` (lifecycle.py).
  2. `start_keyboard_emulation(daemon)` chamado em `Daemon.run()` antes de
     `_stop_event.wait()`, quando `config.keyboard_emulation_enabled` for True.
  3. `dispatch_keyboard(daemon, buttons_pressed)` chamado no `_poll_loop`
     reusando o mesmo `buttons_pressed` já obtido via `_evdev_buttons_once()`
     (armadilha A-09 — snapshot único por tick).
  4. `shutdown` em `connection.py` zera o slot e chama `stop()` para liberar
     teclas pressionadas antes do destroy (evita ghost-keys).
"""
from __future__ import annotations

import contextlib
import json
import os
import shutil
import signal
import subprocess
import tempfile
import threading
import time
from pathlib import Path
from typing import TYPE_CHECKING

from hefesto_dualsense4unix.core.keyboard_mappings import (
    TOKEN_CLOSE_OSK,
    TOKEN_OPEN_OSK,
    TOKEN_TOGGLE_OSK,
)
from hefesto_dualsense4unix.integrations import fora_do_servico
from hefesto_dualsense4unix.utils.logging_config import get_logger

if TYPE_CHECKING:
    from hefesto_dualsense4unix.daemon.protocols import DaemonProtocol

logger = get_logger(__name__)

# TECLADO-QUE-NAO-DIGITA-01 — o CONTRATO DE NOMES.
#
# Estas duas constantes são as mesmas do `scripts/install_osk.sh` (quem
# instala) e do `scripts/doctor.sh` (quem confere), e o
# `scripts/check_packaging_parity.sh` cobra a coincidência dos três. Sem esse
# amarre, o produto pode instalar um binário e procurar outro — e os três
# passam sozinhos, cada um coerente consigo mesmo.
_OSK_BIN_WAYLAND = "wvkbd-mobintl"
_OSK_BIN_X11 = "onboard"
#: T-11 (ONDA0-Z7, 24/08/2026): dois candidatos que o produto não conhecia —
#: medido em §3.6 da sprint O AMBIENTE PRESUMIDO 01. Os dois digitam por
#: PROTOCOLO Wayland (`virtual-keyboard-unstable-v1`/input-method), como o
#: `wvkbd-mobintl` — nunca XTEST — então entram na mesma classe dele na ordem
#: abaixo, nunca à frente do `onboard` em sessão X11.
_OSK_BIN_SQUEEKBOARD = "squeekboard"  # GNOME móvel
_OSK_BIN_MALIIT = "maliit-keyboard"  # Plasma Mobile

# Candidatos de teclado virtual. Cada string aqui é um `shutil.which`-ável; o
# argv completo para spawn fica em `_OSK_SPAWN_ARGS`.
#
# A ORDEM FIXA ERA UM DEFEITO, e ele estava aqui desde sempre: era
# `("onboard", "wvkbd-mobintl")`, com o onboard PRIMEIRO. Numa sessão Wayland
# com os dois instalados, o daemon escolheria o onboard — que digita por XTEST
# (`Depends: libxtst6`) e portanto só alcança clientes XWayland. A janela nativa
# em foco não receberia nada: o teclado ABRE e não DIGITA, que é pior que não
# abrir, porque parece que funcionou. Quem decide agora é `_osk_candidatos()`,
# pela sessão viva.
_OSK_CANDIDATES: tuple[str, ...] = (
    _OSK_BIN_WAYLAND,
    _OSK_BIN_X11,
    _OSK_BIN_SQUEEKBOARD,
    _OSK_BIN_MALIIT,
)
_OSK_SPAWN_ARGS: dict[str, list[str]] = {
    _OSK_BIN_X11: [_OSK_BIN_X11],
    # `--layer 0` ancora wvkbd no bottom (padrão); mantém footprint mínimo.
    _OSK_BIN_WAYLAND: [_OSK_BIN_WAYLAND],
    _OSK_BIN_SQUEEKBOARD: [_OSK_BIN_SQUEEKBOARD],
    _OSK_BIN_MALIIT: [_OSK_BIN_MALIIT],
}

#: Janela (s) do cache de resolução do binário. O `_resolve` era um cache
#: PERMANENTE (`_resolved_checked` nunca voltava a False), e isso tinha um custo
#: concreto: ela roda `sudo apt install wvkbd` com o daemon no ar, aperta o L3 e
#: continua não acontecendo nada — o daemon decidiu "não existe" antes de o
#: pacote existir e não reveria a decisão até o próximo start. É a armadilha do
#: "daemon vivo mais velho que o código" na forma de PATH. Dez segundos é
#: barato: o `shutil.which` só é chamado quando o L3 é apertado (não no poll
#: loop) e no `disponivel()` que o `state_full` consulta.
_OSK_RESOLVE_TTL_SEG = 10.0

#: O-TECLADO-QUE-SOBREVIVE-AO-DAEMON-01 — o teclado na tela é ESTADO DE SESSÃO,
#: e o arquivo abaixo é o único fio entre um daemon e o seguinte.
#:
#: O defeito que ele fecha, medido em 30/08/2026 e remedido em 06/09: o daemon
#: abre o teclado na tela e para sem fechá-lo; o daemon seguinte não sabe que
#: aquele processo existe, então o R3 dela não fecha nada e o L3 empilha um
#: segundo teclado por cima do primeiro. O `_OSKController` recém-criado tem
#: sempre `_process is None`, e tanto o `close()` quanto o guarda do `open()`
#: perguntavam só a esse atributo.
#:
#: MORA NO `runtime_dir`, e a escolha é parte da cura: `XDG_RUNTIME_DIR` é
#: varrido a cada boot, então um PID de outra inicialização não sobrevive para
#: ser confundido com o de agora. O `config_dir` — onde moram o
#: `save_paused_state` e o `load_gamepad_emulation` — guarda ESCOLHA dela, que
#: atravessa reboots de propósito; um PID atravessando reboot é lixo perigoso.
_OSK_SESSAO_ARQUIVO = "teclado-na-tela.json"

#: `/proc/<pid>/comm` é truncado pelo kernel em 15 caracteres (`TASK_COMM_LEN`
#: menos o terminador). `maliit-keyboard` tem exatamente 15 e passaria raspando;
#: qualquer candidato futuro mais longo casaria por engano se a comparação
#: fosse ingênua. Compara-se sempre truncado dos DOIS lados.
_COMM_MAX = 15

#: Quantos toques do L3/R3 esperam atrás do que está em voo no fio do teclado
#: na tela (TODO-PROGRAMA-DO-DAEMON-NASCE-FORA-DO-SERVICO-01). Alternar é ida e
#: volta, e a ORDEM dos toques é a resposta: eles se enfileiram, e não se
#: descartam. Quatro é mais que qualquer mão entre dois `systemd-run`.
_OSK_GESTOS_NA_FILA = 4

#: Quanto a parada espera o toque em voo antes de fechar: as duas formas do
#: `systemd-run`, cada uma com o teto do dono, e a folga do aviso na tela.
_OSK_ESPERA_DA_PARADA_S = 2 * fora_do_servico.ESPERA_DO_SYSTEMD_RUN_S + 1.0


def _osk_candidatos() -> tuple[str, ...]:
    """Candidatos na ordem que FUNCIONA na sessão gráfica de agora.

    `WAYLAND_DISPLAY` primeiro, `DISPLAY` só depois — e essa ordem é o miolo da
    correção. Numa sessão Wayland com XWayland os DOIS estão setados (medido em
    10/08/2026 no ambiente do daemon vivo desta máquina: `WAYLAND_DISPLAY=
    wayland-1` E `DISPLAY=:1`, importados pelo `ExecStartPre` da unit), então
    olhar `DISPLAY` antes classificaria toda sessão Wayland moderna como X11.

    O daemon enxerga essas variáveis porque a unit faz
    `systemctl --user import-environment WAYLAND_DISPLAY DISPLAY`; isso não é
    detalhe de conforto, é o que permite ao `wvkbd-mobintl` que nós spawnamos
    achar o compositor — o filho herda este mesmo ambiente.

    A lista sempre traz os DOIS: se o preferido não estiver instalado, o outro
    ainda é melhor que nada (num X11 sem onboard, um wvkbd instalado não abre —
    mas aí o `open()` falha e loga, em vez de o produto fingir que não há nada).
    """
    # T-11 (ONDA0-Z7): squeekboard e maliit-keyboard entraram na lista — os
    # dois digitam por protocolo Wayland, então seguem a MESMA regra do
    # wvkbd-mobintl (vêm antes do onboard em sessão Wayland, depois em X11).
    if os.environ.get("WAYLAND_DISPLAY") or os.environ.get("XDG_SESSION_TYPE") == "wayland":
        return (_OSK_BIN_WAYLAND, _OSK_BIN_SQUEEKBOARD, _OSK_BIN_MALIIT, _OSK_BIN_X11)
    if os.environ.get("DISPLAY") or os.environ.get("XDG_SESSION_TYPE") == "x11":
        return (_OSK_BIN_X11, _OSK_BIN_WAYLAND, _OSK_BIN_SQUEEKBOARD, _OSK_BIN_MALIIT)
    # Sessão desconhecida (daemon headless, CI): a aposta é declarada — vale a
    # de Wayland, que é o padrão de todo desktop atual.
    return (_OSK_BIN_WAYLAND, _OSK_BIN_SQUEEKBOARD, _OSK_BIN_MALIIT, _OSK_BIN_X11)


#: Cache (instante, resposta) da sonda de módulo abaixo. Lista de um elemento
#: para não precisar de `global`.
_OSK_SONDA: list[tuple[float, bool]] = [(float("-inf"), False)]


def osk_disponivel_no_sistema() -> bool:
    """Há teclado na tela instalado nesta máquina, agora?

    Existe para quem precisa da resposta SEM ter um `_OSKController` à mão — o
    `state_full` do daemon, que a publica para a janela. A janela não pode fazer
    o `shutil.which` por conta própria: num Flatpak ela olharia dentro do
    sandbox e responderia sobre uma máquina que não é a da usuária.

    Mesmo TTL do `_OSKController._resolve` e pelo mesmo motivo (instalar o
    pacote com o daemon no ar tem de passar a valer sem restart), e mesmo custo:
    um `shutil.which` a cada 10 s, no máximo, mesmo com o `state_full` a 20 Hz.
    """
    agora = time.monotonic()
    quando, valor = _OSK_SONDA[0]
    if agora - quando < _OSK_RESOLVE_TTL_SEG:
        return valor
    valor = any(shutil.which(candidato) for candidato in _osk_candidatos())
    _OSK_SONDA[0] = (agora, valor)
    return valor


def _sessao_do_teclado() -> Path:
    """Onde o PID do teclado na tela deste produto fica entre dois daemons."""
    from hefesto_dualsense4unix.utils.xdg_paths import runtime_dir

    return runtime_dir(ensure=True) / _OSK_SESSAO_ARQUIVO


def _gravar_sessao(pid: int, binario: str, unidade: str | None = None) -> None:
    """Anota quem abrimos: o PID e o NOME do binário que spawnamos.

    E a unidade, quando o teclado nasceu numa (``fora_do_servico``): é o nome
    que a ``systemd`` deu a ele, anotado para quem mede.

    Grava o nome que ESTE produto mandou abrir, e não o que o `/proc` diz — é a
    comparação entre os dois, na adoção, que separa o nosso teclado de um PID
    que o kernel reciclou. Best-effort de ponta a ponta: sem `XDG_RUNTIME_DIR`
    gravável o produto perde a adoção, não o teclado.
    """
    try:
        caminho = _sessao_do_teclado()
        registro: dict[str, object] = {"pid": int(pid), "comm": binario}
        if unidade:
            registro["unidade"] = unidade
        dados = json.dumps(registro, ensure_ascii=False)
        fd, tmp = tempfile.mkstemp(dir=caminho.parent, prefix=".teclado_")
        try:
            os.write(fd, dados.encode())
        finally:
            os.close(fd)
        os.replace(tmp, caminho)
        logger.debug("osk_sessao_gravada", pid=pid, comm=binario)
    except Exception as exc:
        logger.debug("osk_sessao_gravar_falhou", err=str(exc))


def _esquecer_sessao() -> None:
    """Apaga o arquivo de sessão. Nunca levanta."""
    with contextlib.suppress(Exception):
        _sessao_do_teclado().unlink(missing_ok=True)


def _comm_do_pid(pid: int) -> str | None:
    """O `/proc/<pid>/comm` do processo, ou None se ele não existe mais.

    Função de módulo (e não método) para ter UM ponto de dublê: é aqui que a
    régua troca o `/proc` de verdade quando precisa medir o caso do PID
    reciclado sem depender de o kernel reciclar um PID durante o teste.
    """
    try:
        return Path(f"/proc/{int(pid)}/comm").read_text(encoding="utf-8").strip()
    except (FileNotFoundError, ProcessLookupError, OSError, ValueError):
        return None


def _pid_e_zumbi(pid: int) -> bool:
    """O processo já morreu e só falta alguém colher o corpo?

    UM ZUMBI PASSARIA NAS TRÊS PERGUNTAS DA ADOÇÃO e não é um teclado na tela:
    `/proc/<pid>` e `/proc/<pid>/comm` continuam legíveis, com o mesmo nome de
    binário, depois que o processo morreu — o que sobrou é a entrada na tabela,
    esperando o pai chamar `wait`. Adotar um deles faria o L3 dela achar que já
    há teclado aberto e nunca mais abrir nenhum.

    Na máquina dela isso é raro: o teclado do daemon anterior fica órfão de
    verdade e o `init` o colhe. Mas ele é o caso COMUM em quem mede — a régua é
    o pai do processo que ela abre —, e um instrumento que precisa contornar o
    produto para medir é o instrumento errado.
    """
    try:
        stat = Path(f"/proc/{int(pid)}/stat").read_text(encoding="utf-8")
    except (FileNotFoundError, ProcessLookupError, OSError, ValueError):
        return False
    # O `comm` vem entre parênteses no `stat` e pode conter espaços e `)`: o
    # estado é o primeiro campo DEPOIS do ÚLTIMO `)`. Partir por espaço direto
    # erraria em qualquer binário com espaço no nome.
    _, _, resto = stat.rpartition(")")
    campos = resto.split()
    return bool(campos) and campos[0] == "Z"


def _adotar_orfao() -> int | None:
    """O PID do teclado na tela que o daemon ANTERIOR deixou aberto, se for nosso.

    A ADOÇÃO É CONSERVADORA, e isso é requisito da sprint, não zelo. Só se
    adota um PID que passa nas TRÊS perguntas:

      (a) está no arquivo que ESTE produto escreveu;
      (b) ainda existe DE VERDADE — `/proc/<pid>` legível e o estado não é `Z`
          (ver `_pid_e_zumbi`: um defunto por colher tem `/proc` intacto e não
          desenha teclado nenhum);
      (c) o `/proc/<pid>/comm` é o mesmo binário que nós mandamos abrir, E esse
          binário é um dos candidatos que este produto conhece.

    Falhando qualquer uma, o arquivo é ESQUECIDO e a resposta é None — o L3
    seguinte abre um teclado novo, que é o comportamento honesto.

    **Matar por nome (`pkill wvkbd`) está PROIBIDO** e é justamente o que estas
    três perguntas existem para não precisar: ela pode ter um teclado na tela
    aberto pelo COSMIC ou pela mão dela, e fechar o que não foi o produto que
    abriu é estrago, não cura. Um PID reciclado pelo kernel cai em (c).
    """
    try:
        bruto = _sessao_do_teclado().read_text(encoding="utf-8")
        dados = json.loads(bruto)
        pid = int(dados["pid"])
        comm_gravado = str(dados["comm"])
    except (FileNotFoundError, json.JSONDecodeError, OSError, KeyError, TypeError, ValueError):
        return None
    except Exception as exc:  # pragma: no cover - defesa de borda
        logger.debug("osk_sessao_ler_falhou", err=str(exc))
        return None

    if comm_gravado not in _OSK_CANDIDATES:
        # Arquivo de uma versão que abria outra coisa, ou adulterado. Não é
        # nosso pelo critério de hoje: esquece em vez de arriscar.
        logger.debug("osk_orfao_recusado_binario_desconhecido", comm=comm_gravado)
        _esquecer_sessao()
        return None

    comm_vivo = _comm_do_pid(pid)
    if comm_vivo is None or _pid_e_zumbi(pid):
        logger.debug("osk_orfao_ja_morreu", pid=pid)
        _esquecer_sessao()
        return None
    if comm_vivo[:_COMM_MAX] != comm_gravado[:_COMM_MAX]:
        # PID reciclado pelo kernel: existe um processo com este número, e ele
        # NÃO é o nosso. Fechá-lo mataria programa alheio.
        logger.info("osk_orfao_recusado_pid_reciclado", pid=pid, comm=comm_vivo)
        _esquecer_sessao()
        return None
    return pid


def _pid_na_unidade(unidade: str, binario: str) -> int | None:
    """O PID do teclado na tela dentro da unidade que o abriu — pergunta à unidade.

    O PID do ``systemd-run`` não é o do teclado: a unidade é que sabe quem roda
    nela (``fora_do_servico.pids_da_unidade``). Das perguntas da adoção valem
    as duas que o PID ainda precisa responder: o ``comm`` é o binário que
    mandamos abrir, e o processo não é um defunto por colher.
    """
    for pid in fora_do_servico.pids_da_unidade(unidade):
        comm = _comm_do_pid(pid)
        if comm is None or comm[:_COMM_MAX] != binario[:_COMM_MAX]:
            continue
        if _pid_e_zumbi(pid):
            continue
        return pid
    return None


class _OSKController:
    """Gerencia o processo do teclado virtual (onboard/wvkbd-mobintl).

    Detecta o binário disponível apenas 1x (cache em `_resolved_bin`); warning
    é logado uma única vez se nenhum dos candidatos estiver instalado. Abrir
    quando já há processo ativo é no-op (evita stack de janelas sobrepostas).

    A PROMESSA ACIMA VALIA DENTRO DE UM DAEMON SÓ, e é isso que a
    O-TECLADO-QUE-SOBREVIVE-AO-DAEMON-01 fechou: o teclado aberto por um daemon
    sobrevivia à parada dele, e o controlador do daemon SEGUINTE não sabia que
    aquele processo existia — `self._process` nasce None. O R3 não fechava nada
    e o L3 empilhava. Agora `open`, `close` e `aberto` passam todos pelo
    `_pid_vivo()`, que olha o processo deste daemon E o órfão anotado no arquivo
    de sessão (`_adotar_orfao`). Fechar sem nada aberto continua no-op.

    TRÊS VERBOS, e o terceiro é o do L3: `open`, `close` e `toggle`. O
    alternador não é açúcar em cima dos dois primeiros — ele depende de
    `aberto()`, que pergunta ao PROCESSO se ele ainda vive em vez de acreditar
    no atributo. Ver o corpo daquele método para o que isso evita.
    """

    def __init__(self) -> None:
        self._resolved_bin: str | None = None
        self._resolved_checked: bool = False
        self._resolved_em: float = 0.0
        self._process: subprocess.Popen[bytes] | None = None
        #: O teclado que nasceu numa unidade própria (``fora_do_servico``): o
        #: nome dela e o binário que ela roda. Pelo ``Popen`` é o ``_process``.
        self._unidade: str | None = None
        self._binario_da_unidade: str = ""
        self._missing_warned: bool = False
        #: O fio do L3/R3 (``dispatch_token``) e a parada mexem no mesmo estado.
        self._tranca = threading.RLock()
        self._fio = fora_do_servico.FioDeTrabalho(
            "hefesto-teclado-na-tela",
            espera=_OSK_GESTOS_NA_FILA,
            ao_falhar=lambda erro: logger.warning("osk_gesto_falhou", err=str(erro)),
        )

    def _resolve(self) -> str | None:
        """Primeiro binário de teclado na tela que existe, na ordem da sessão.

        O cache tem PRAZO (`_OSK_RESOLVE_TTL_SEG`) em vez de ser eterno: ver a
        constante para o porquê — sem prazo, instalar o pacote com o daemon no
        ar não tinha efeito nenhum até o próximo start, e o sintoma para ela é
        idêntico ao de não ter instalado.
        """
        agora = time.monotonic()
        if self._resolved_checked and (agora - self._resolved_em) < _OSK_RESOLVE_TTL_SEG:
            return self._resolved_bin
        self._resolved_em = agora
        self._resolved_checked = True
        for candidate in _osk_candidatos():
            path = shutil.which(candidate)
            if path:
                self._resolved_bin = candidate
                return candidate
        self._resolved_bin = None
        return None

    def disponivel(self) -> bool:
        """True se há programa de teclado na tela instalado (cache do `_resolve`).

        TECLADO-QUE-NAO-DIGITA-01: quem quiser dizer na tela que L3 não tem o
        que abrir pergunta aqui, em vez de repetir o `shutil.which`.
        """
        return self._resolve() is not None

    def _avisar_ausencia(self) -> None:
        """L3 sem teclado na tela deixa de ser silêncio (TECLADO-QUE-NAO-DIGITA-01).

        O ramo "nenhum candidato instalado" logava um `warning` e retornava —
        e um warning no journal não é resposta a quem acabou de apertar um
        botão. Medido na máquina dela em 09/08/2026: nem `onboard` nem
        `wvkbd-mobintl` existem, e `l3` é justamente o ÚNICO caminho do produto
        para ESCREVER texto com o controle (nenhum binding de fábrica digita
        letra). O aperto sumia inteiro.

        O log continua uma vez só (`_missing_warned`); a notificação tem
        dedup próprio (`once_key` do `notify`), então ela sobrevive a um
        `_OSKController` novo dentro do mesmo daemon sem virar rajada.
        Best-effort de ponta a ponta: sem jeepney/sem servidor de notificação o
        `notify` devolve False e nada quebra.
        """
        # `_osk_candidatos()` e não `_OSK_CANDIDATES`: a frase é "instale X ou
        # Y", e QUAL vem primeiro é a diferença entre um conselho que resolve e
        # um que faz ela instalar o programa que abre sem digitar. Em Wayland o
        # primeiro nome tem de ser o wvkbd.
        candidatos = list(_osk_candidatos())
        if not self._missing_warned:
            logger.warning(
                "osk_binary_missing",
                candidates=candidatos,
            )
            self._missing_warned = True
        with contextlib.suppress(Exception):
            from hefesto_dualsense4unix.integrations.desktop_notifications import (
                notify_teclado_na_tela_ausente,
            )

            notify_teclado_na_tela_ausente(candidatos)

    def aberto(self) -> bool:
        """True se HÁ um teclado na tela vivo que este daemon abriu.

        ELA NÃO É `self._process is not None`, e a diferença é o defeito que o
        alternador teria: o wvkbd/onboard pode morrer por fora (ela fecha a
        janela, o compositor o derruba, a sessão troca) e o `Popen` continua no
        atributo, com `poll()` já devolvendo o código de saída. Um alternador
        que confiasse na presença do objeto mandaria FECHAR o que já está
        fechado, e o próximo aperto abriria — o L3 passaria a precisar de dois
        toques para abrir, de forma intermitente.

        Enxuga o atributo quando o processo morreu por fora, para o `close()`
        seguinte não ter o que terminar e o estado não ficar mentindo.

        DESDE O-TECLADO-QUE-SOBREVIVE-AO-DAEMON-01 ela olha TAMBÉM o órfão do
        daemon anterior: sem isso, um `_OSKController` recém-criado responde
        "fechado" com o teclado dela na tela, e é dessa mentira que nascem o R3
        que não fecha nada e o L3 que empilha.
        """
        with self._tranca:
            return self._pid_vivo() is not None

    def _pid_vivo(self) -> int | None:
        """O PID do teclado na tela que ESTE produto abriu e ainda vive.

        Três fontes, nesta ordem: o processo deste daemon, a UNIDADE em que
        ele nasceu fora do serviço (`_pid_na_unidade`: o PID do `systemd-run`
        não é o do teclado) e, na falta dos dois, o órfão que o daemon anterior
        deixou (`_adotar_orfao`, que só devolve o que passa nas três
        perguntas). Devolve None quando não há nenhum.
        """
        proc = self._process
        if proc is not None:
            if proc.poll() is None:
                return proc.pid
            self._process = None
        if self._unidade is not None:
            pid = _pid_na_unidade(self._unidade, self._binario_da_unidade)
            if pid is not None:
                return pid
            self._unidade = None
        return _adotar_orfao()

    def toggle(self) -> None:
        """O SEGUNDO TOQUE FECHA — decisão dela, 02/09/2026.

        *"deixar no preset do botão L3, no mapeamento, abrir o teclado virtual e
        fechar o teclado virtual caso apertado novamente."*

        Sem binário instalado, `open()` avisa e não deixa processo: o estado
        continua "fechado" e o toque seguinte volta a tentar abrir, que é o
        certo — o aviso tem dedup próprio e o TTL do `_resolve` faz um pacote
        instalado com o daemon no ar passar a valer em até dez segundos.
        """
        with self._tranca:
            if self._pid_vivo() is not None:
                self._fechar()
            else:
                self._abrir()

    def open(self) -> None:
        """Abre o teclado na tela — no-op se JÁ há um aberto, deste daemon ou do anterior.

        O guarda pergunta ao `_pid_vivo()` e não ao `self._process`: era o
        atributo que fazia o L3 EMPILHAR um segundo teclado por cima do que o
        daemon anterior tinha deixado na tela dela.

        E O SUCESSO AVISA (O-TECLADO-QUE-NAO-DIZ-COMO-SAIR-01): o `logger.info`
        abaixo ganhou irmão na TELA. Um `osk_opened` no journal não é resposta a
        quem acabou de clicar um analógico — foi o que deixou ela vinte minutos
        com um teclado na tela sem saber o que o tinha aberto nem como sair.

        **SÓ NO SUCESSO, e os três ramos que voltam antes NÃO avisam** — os três
        estão acima desta linha de propósito: o "já aberto" não teve transição
        para anunciar (dois avisos para um teclado só), o "sem binário" já tem
        dono e frase própria (`_avisar_ausencia`, e dois avisos no mesmo gesto
        seria ruído), e o `Popen` que estourou não abriu teclado nenhum — avisar
        ali seria a tela mentindo sobre o que existe.

        E ELE NASCE FORA DO SERVIÇO (TODO-PROGRAMA-DO-DAEMON-NASCE-FORA-DO-SERVICO-01):
        o teclado é programa dela, e pelo `Popen` de dentro do daemon herdava o
        `nice 5` e o `oom 200` do serviço. Quem decide a forma é
        `fora_do_servico.abrir`; pela unidade, o PID se pergunta a ela.
        """
        with self._tranca:
            self._abrir()

    def _abrir(self) -> None:
        if self._pid_vivo() is not None:
            return
        resolved = self._resolve()
        if resolved is None:
            self._avisar_ausencia()
            return
        from hefesto_dualsense4unix.integrations.ambiente_do_jogo import ambiente_limpo

        args = _OSK_SPAWN_ARGS[resolved]
        try:
            abertura = fora_do_servico.abrir(
                args,
                env=ambiente_limpo(os.environ),
                aplicativo=resolved,
                popen=subprocess.Popen,
            )
        except Exception as exc:
            logger.warning("osk_open_failed", binary=resolved, err=str(exc))
            self._process = None
            return
        pid: int | None
        if abertura.caminho == "unidade" and abertura.unidade:
            self._process = None
            self._unidade = abertura.unidade
            self._binario_da_unidade = resolved
            pid = _pid_na_unidade(abertura.unidade, resolved)
        else:
            self._process = abertura.processo
            pid = getattr(abertura.processo, "pid", None)
        logger.info(
            "osk_opened",
            binary=resolved,
            pid=pid,
            caminho=abertura.caminho,
            unidade=abertura.unidade,
            motivo=abertura.motivo,
        )
        if pid is not None:
            _gravar_sessao(pid, resolved, abertura.unidade)
        self._avisar_abertura()

    def _avisar_abertura(self) -> None:
        """Diz na TELA que o teclado na tela abriu, e como fechá-lo.

        Best-effort de ponta a ponta, no molde do `_avisar_ausencia`: sem
        jeepney, sem servidor de notificação ou sem barramento, o `notify`
        devolve False e o teclado continua aberto. **Um aviso que estoura
        derrubaria o gesto que ele veio explicar** — foi um recado de recusa
        quebrando a tela que vinha explicar que custou a leva de 04/09.

        O import é tardio pelo mesmo motivo do irmão: o subsistema do daemon não
        arrasta o `jeepney` para dentro de quem só quer despachar teclas.
        """
        with contextlib.suppress(Exception):
            from hefesto_dualsense4unix.integrations.desktop_notifications import (
                notify_teclado_na_tela_aberto,
            )

            notify_teclado_na_tela_aberto()

    def close(self) -> None:
        """Fecha o teclado na tela — o deste daemon, ou o órfão do anterior.

        A segunda metade é a cura do R3 que não fechava nada: `close()` voltava
        na primeira linha quando `self._process is None`, e um controlador
        recém-criado tem SEMPRE None. O aperto virava no-op silencioso com o
        teclado dela na tela.

        O órfão morre por `SIGTERM` no PID adotado — nunca por nome. Ver
        `_adotar_orfao` para as três perguntas que decidem se o PID é nosso.

        QUEM CHAMA DE FORA (a parada do daemon) ESPERA O FIO PRIMEIRO: um L3 na
        fila abriria o teclado DEPOIS da parada, sem dono para fechá-lo. Os
        toques que não começaram saem da fila, e o que está em voo termina.
        """
        if not self._fio.no_fio():
            self._fio.descartar()
            self.esperar_os_toques(_OSK_ESPERA_DA_PARADA_S)
        with self._tranca:
            self._fechar()

    def _fechar(self) -> None:
        proc = self._process
        if proc is not None:
            self._process = None
            if proc.poll() is None:
                try:
                    proc.terminate()
                    logger.info("osk_closed", pid=proc.pid)
                except Exception as exc:
                    logger.warning("osk_close_failed", err=str(exc))
                _esquecer_sessao()
                return
        unidade = self._unidade
        if unidade is not None:
            self._unidade = None
            pid_da_unidade = _pid_na_unidade(unidade, self._binario_da_unidade)
            if pid_da_unidade is not None:
                try:
                    os.kill(pid_da_unidade, signal.SIGTERM)
                    logger.info("osk_closed", pid=pid_da_unidade, unidade=unidade)
                except Exception as exc:
                    logger.warning("osk_close_failed", err=str(exc), unidade=unidade)
                _esquecer_sessao()
                return
        pid = _adotar_orfao()
        if pid is None:
            # `_adotar_orfao` já esqueceu o arquivo quando ele era inválido;
            # aqui não há nada aberto e nada a matar.
            return
        try:
            os.kill(pid, signal.SIGTERM)
            logger.info("osk_orfao_fechado", pid=pid)
        except Exception as exc:
            logger.warning("osk_orfao_close_failed", pid=pid, err=str(exc))
        _esquecer_sessao()

    def dispatch_token(self, token: str, phase: str) -> None:
        """Callback registrado no UinputKeyboardDevice.

        Só atua em press (edge-triggered pull-to-focus). Release é no-op para
        evitar fechar no release de L3 logo após o press abrir.

        O LAÇO SÓ DISPARA (TODO-PROGRAMA-DO-DAEMON-NASCE-FORA-DO-SERVICO-01):
        este callback roda no laço que lê os quatro controles, e abrir o
        teclado custa o `systemd-run` (6 a 20 ms, teto de 2 s por forma). O
        toque vai para o fio do teclado, na ordem em que chegou.
        """
        if phase != "press":
            return
        if token not in (TOKEN_TOGGLE_OSK, TOKEN_OPEN_OSK, TOKEN_CLOSE_OSK):
            logger.warning("osk_token_desconhecido", token=token)
            return
        if not self._fio.disparar(lambda: self._atender(token)):
            logger.info("osk_toque_descartado", token=token)

    def _atender(self, token: str) -> None:
        """O toque, já no fio do teclado."""
        with self._tranca:
            if token == TOKEN_TOGGLE_OSK:
                if self._pid_vivo() is not None:
                    self._fechar()
                else:
                    self._abrir()
            elif token == TOKEN_OPEN_OSK:
                self._abrir()
            else:
                self._fechar()

    def esperar_os_toques(self, teto: float | None = None) -> bool:
        """Espera os toques do L3/R3 que estão no fio. True = nenhum ficou."""
        return self._fio.esperar(teto)


def start_keyboard_emulation(daemon: DaemonProtocol) -> bool:
    """Cria device virtual de teclado + touchpad reader. Idempotente.

    Retorna True se ativo ao final; False se falhou ao iniciar o device
    principal. O `TouchpadReader` é best-effort: se o nó evdev do touchpad não
    existir, não quebra o fluxo.

    CORREÇÃO DE FATO — 25/08/2026. Esta linha dizia que o nó podia faltar "(
    controle BT, kernel velho)", e o **BT saiu**: o `hid_playstation` cria o nó
    de touchpad nos dois transportes, e ele foi medido no rádio em 21/07/2026
    (o nome muda, não a existência — o BlueZ o batiza sem o prefixo do
    fabricante, e é por isso que o casamento por nome exato falhava; ver o
    cabeçalho de `assets/76-dualsense-touchpad-libinput-ignore.rules`). Nem a
    descoberta olha transporte: `_discover_dualsense_por_nome` filtra por
    vendor/product e marcador de nome, sem uma linha sobre `bustype`. Medido de
    novo em 25/08 no DualSense do CABO desta bancada: gamepad em `event21` e
    touchpad em `event23`, a mesma identidade nos dois.

    O que faz as três regiões não dispararem tecla HOJE é outra coisa, e é
    decisão dela: o touchpad voltou a ser ponteiro do SISTEMA
    (TOUCHPAD-DO-SISTEMA-01), e quem se cala é o `_combine_with_touchpad`
    abaixo, pelo `ponteiro_do_sistema` do reader. Medido na mesma leitura:
    `LIBINPUT_IGNORE_DEVICE` ausente no nó do touchpad físico.

    EMULACAO-NO-JOGO-01: o gate de `keyboard_emulation_enabled` mora AQUI,
    espelhando `subsystems/mouse.py` (`if not cfg.mouse_emulation_enabled:
    return`). É o que dá dentes ao interruptor: desligada, o device NÃO nasce,
    e o gate de despacho do poll loop (`_keyboard_device is not None`) fecha
    sozinho — a mesma mecânica que fazia o mouse dela estar honestamente
    desligado enquanto o teclado emitia Alt+Tab dentro da partida. `getattr`
    defensivo em dois níveis: dublê de teste sem `config` (ou sem o campo)
    segue com o comportamento histórico (ligado).
    """
    if getattr(daemon, "_keyboard_device", None) is not None:
        return True
    cfg = getattr(daemon, "config", None)
    if cfg is not None and not getattr(cfg, "keyboard_emulation_enabled", True):
        logger.debug("keyboard_emulation_desligada_device_nao_criado")
        return False
    try:
        from hefesto_dualsense4unix.integrations.uinput_keyboard import UinputKeyboardDevice

        device = UinputKeyboardDevice()
    except Exception as exc:
        logger.warning("keyboard_emulation_import_failed", err=str(exc))
        return False
    # OSK controller vive 1x por daemon; callback é registrado na inicialização
    # para que L3/R3 já funcionem antes do primeiro switch de perfil.
    osk = getattr(daemon, "_osk_controller", None)
    if osk is None:
        osk = _OSKController()
        daemon._osk_controller = osk
    device.virtual_token_callback = osk.dispatch_token
    if not device.start():
        logger.warning("keyboard_emulation_start_failed")
        return False
    daemon._keyboard_device = device
    # TouchpadReader best-effort: emite 3 strings virtuais (touchpad_*_press)
    # que o dispatcher mescla ao frozenset de botões. Bindings default
    # mapeiam para KEY_BACKSPACE/ENTER/DELETE.
    _start_touchpad_reader(daemon)
    logger.info("keyboard_emulation_started")
    return True


def _start_touchpad_reader(daemon: DaemonProtocol) -> None:
    """Inicia TouchpadReader se device evdev disponível; no-op caso contrário.

    Em modo FAKE (testes, CI, smoke runs) o reader é pulado pois
    `find_dualsense_touchpad_evdev()` pode demorar >60ms enumerando evdev
    em ambiente com muitos devices, o que compete com janelas de teste
    curtas do poll loop.
    """
    if getattr(daemon, "_touchpad_reader", None) is not None:
        return
    if os.environ.get("HEFESTO_DUALSENSE4UNIX_FAKE"):
        logger.debug("touchpad_reader_desativado_em_fake_mode")
        return
    try:
        from hefesto_dualsense4unix.core.evdev_reader import TouchpadReader
    except Exception as exc:
        logger.warning("touchpad_reader_import_failed", err=str(exc))
        return
    reader = TouchpadReader()
    if not reader.is_available():
        logger.debug("touchpad_reader_ausente")
        return
    if reader.start():
        daemon._touchpad_reader = reader
        logger.info("touchpad_reader_iniciado")


def stop_keyboard_emulation(daemon: DaemonProtocol) -> None:
    """Para device + reader + OSK. Idempotente."""
    device = getattr(daemon, "_keyboard_device", None)
    if device is not None:
        with contextlib.suppress(Exception):
            device.stop()
        daemon._keyboard_device = None
    reader = getattr(daemon, "_touchpad_reader", None)
    if reader is not None:
        with contextlib.suppress(Exception):
            reader.stop()
        daemon._touchpad_reader = None
    osk = getattr(daemon, "_osk_controller", None)
    if osk is not None:
        with contextlib.suppress(Exception):
            osk.close()
        daemon._osk_controller = None
    logger.info("keyboard_emulation_stopped")


def _combine_with_touchpad(
    daemon: DaemonProtocol, buttons_pressed: frozenset[str]
) -> frozenset[str]:
    """Mescla as regiões do TouchpadReader ao frozenset de botões.

    Extraído para reuso por `dispatch_keyboard` e `prime_keyboard` (mesma
    visão de botões que o device de teclado enxerga). Falha de leitura do
    reader é tratada como "nenhuma região pressionada".

    TOUCHPAD-DO-SISTEMA-01 (2026-08-09): quando o touchpad é ponteiro do
    SISTEMA, o mesmo `BTN_LEFT` já está virando botão do mouse no libinput —
    somar a região aqui faria um clique só disparar DUAS coisas (o clique dela e
    um `KEY_BACKSPACE`/`ENTER`/`DELETE` dos bindings default de
    `core/keyboard_mappings.py`). É o defeito do cursor engasgado de 26/06 na
    forma de tecla, e ele nasceria no mesmo dia em que o touchpad físico voltou
    ao libinput. Quem responde é o próprio reader (`ponteiro_do_sistema`), pelo
    estado real do nó. Reader antigo/dublê sem a propriedade conta como "o
    hefesto é o dono", que é o comportamento histórico.
    """
    reader = getattr(daemon, "_touchpad_reader", None)
    if reader is None:
        return buttons_pressed
    if getattr(reader, "ponteiro_do_sistema", False):
        return buttons_pressed
    regions: frozenset[str]
    try:
        regions = frozenset(reader.regions_pressed())
    except Exception as exc:
        logger.warning("touchpad_regions_read_failed", err=str(exc))
        regions = frozenset()
    return buttons_pressed | regions


def prime_keyboard(daemon: DaemonProtocol, buttons_pressed: frozenset[str]) -> None:
    """Semeia o edge-tracker do device de teclado com o baseline da conexão.

    Usado pelo poll loop no 1º tick conectado (BUG-DAEMON-CONNECT-GHOST-
    INPUT-01). Reaplica a mesma combinação botões+touchpad de `dispatch_keyboard`
    para que o estado semeado seja idêntico ao que o device veria, e delega ao
    `UinputKeyboardDevice.prime` (zero emissão). No-op sem device.
    """
    device = getattr(daemon, "_keyboard_device", None)
    if device is None:
        return
    combined = _combine_with_touchpad(daemon, buttons_pressed)
    try:
        device.prime(combined)
    except Exception as exc:
        logger.warning("keyboard_prime_failed", err=str(exc))


def dispatch_keyboard(daemon: DaemonProtocol, buttons_pressed: frozenset[str]) -> None:
    """Traduz o set de botões pressionados em eventos de teclado virtual.

    Chamado pelo poll loop a cada tick. Reusa `buttons_pressed` já obtido
    via `_evdev_buttons_once` (armadilha A-09). Mescla as 3 regiões do
    `TouchpadReader` (`touchpad_{left,middle,right}_press`) ao frozenset
    antes de passar ao device — regiões são tratadas como "botões virtuais"
    com os bindings default KEY_BACKSPACE/ENTER/DELETE. Não relança
    exceções — falhas são logadas como warning.
    """
    device = getattr(daemon, "_keyboard_device", None)
    if device is None:
        return
    combined = _combine_with_touchpad(daemon, buttons_pressed)
    try:
        device.dispatch(combined)
    except Exception as exc:
        logger.warning("keyboard_dispatch_failed", err=str(exc))


__all__ = [
    "_OSKController",
    "dispatch_keyboard",
    "osk_disponivel_no_sistema",
    "prime_keyboard",
    "start_keyboard_emulation",
    "stop_keyboard_emulation",
]

# "A natureza nada faz em vão." — Aristóteles
