"""Checks de infra read-only para auto-diagnóstico no boot.

FEAT-SYSTEM-AUTOREPAIR-BOOT-01: espelha em Python parte do `scripts/doctor.sh`,
focado no que vale AVISAR ao usuário no boot do daemon (udev de hotplug
desatualizado, WirePlumber sequestrando o microfone do DualSense). NUNCA levanta
e NUNCA roda sudo/reparo — apenas detecta e devolve mensagens com o comando
sugerido. O reparo de fato fica a cargo do usuário (`doctor --fix`).
"""
from __future__ import annotations

import contextlib
import os
from collections.abc import Callable
from pathlib import Path
from typing import Any

_WRONG_HOTPLUG_PATTERN = 'SYSTEMD_USER_WANTS}="hefesto-gui-hotplug.service"'
_UDEV_RULES = (
    "/etc/udev/rules.d/73-ps5-controller-hotplug.rules",
    "/etc/udev/rules.d/74-ps5-controller-hotplug-bt.rules",
)

_PROC_CARDS = "/proc/asound/cards"
_RAIZ_UCM = "/usr/share/alsa/ucm2"
_NOME_DO_DUALSENSE = "Sony Interactive Entertainment DualSense"


def _udev_hotplug_outdated() -> bool:
    """True se alguma regra 73/74 instalada cita a unit de hotplug ERRADA."""
    for rule in _UDEV_RULES:
        try:
            text = Path(rule).read_text(encoding="utf-8")
        except OSError:
            continue
        if _WRONG_HOTPLUG_PATTERN in text:
            return True
    return False


_CHAVE_DA_FONTE_CONFIGURADA = "default.configured.audio.source"


def fonte_configurada_do_wireplumber() -> str | None:
    """O microfone padrão que alguém ESCOLHEU e o WirePlumber gravou, ou `None`.

    É o `default.configured.audio.source` do `default-nodes`: o que um
    `pactl set-default-source` (nosso ou de qualquer outro programa) ou a
    escolha nas configurações de som deixou gravado. O WirePlumber o devolve
    sozinho quando aquele nó reaparece — é por isso que ele é a escolha do usuário,
    e não o ativo de agora.

    **UM LEITOR SÓ DESTE ARQUIVO no lado Python.** O aviso de boot
    (`_wireplumber_hijacks_mic`) e o nascimento do microfone
    (`daemon/subsystems/hotkey._a_escolha_gravada_e_de_outro_controle`) fazem
    a mesma pergunta ao mesmo disco; duas leituras seriam duas réguas sobre o
    mesmo estado. O caminho é o mesmo dos donos do shell (`doctor.sh`,
    `fix_wireplumber_default_source.sh`: `${HOME}/.local/state/...`).

    `None` quando não há escolha gravada (a máquina nova, que nunca escolheu),
    ou quando o arquivo não se deixa ler. Nunca levanta.
    """
    return escolha_configurada_do_wireplumber(_CHAVE_DA_FONTE_CONFIGURADA)


def escolha_configurada_do_wireplumber(chave_pedida: str) -> str | None:
    """O valor de ``chave_pedida`` no `default-nodes` do WirePlumber, ou `None`.

    O leitor único do arquivo: a fonte (``default.configured.audio.source``,
    :func:`fonte_configurada_do_wireplumber`) e a saída
    (``default.configured.audio.sink``) que alguém escolheu. Nunca levanta.
    """
    estado = Path.home() / ".local/state/wireplumber/default-nodes"
    try:
        linhas = estado.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return None
    for linha in linhas:
        chave, igual, valor = linha.partition("=")
        if igual and chave.strip().lower() == chave_pedida:
            return valor.strip() or None
    return None


def _wireplumber_hijacks_mic() -> bool:
    """True se o WirePlumber fixou o DualSense como fonte de áudio padrão."""
    fonte = fonte_configurada_do_wireplumber()
    return fonte is not None and "dualsense" in fonte.lower()


def _dir_dos_dropins() -> Path:
    """Onde o `fix_wireplumber_default_source.sh` põe os drop-ins 51/52/53/54.

    O script grava em `$HOME/.config`, então esta pergunta também parte dali. Quem
    decide a pasta e a forma (SPA-JSON ou Lua) é `xdg_paths`.
    """
    from hefesto_dualsense4unix.utils.xdg_paths import (
        wireplumber_forma,
        wireplumber_pasta_da_forma,
    )

    return wireplumber_pasta_da_forma(wireplumber_forma(), Path.home() / ".config")


def _marca_do_gesto_do_mic() -> Path:
    """O arquivo em que quem PEDIU o mic do controle deixou o gesto gravado."""
    estado = os.environ.get("XDG_STATE_HOME") or str(Path.home() / ".local/state")
    return Path(estado) / "hefesto-dualsense4unix" / "mic-do-dualsense-pedido.conf"


def _dualsense_mic_intended() -> bool:
    """True quando o mic do DualSense ser a fonte padrão é o que a pessoa PEDIU.

    **O DEFEITO, medido em 16/09/2026 na máquina do usuário.** Esta função perguntava
    a UMA variável de ambiente, e só a ela — enquanto o `doctor.sh` responde à
    MESMA pergunta com CINCO degraus (`_prefere_mic_do_dualsense`). Duas fontes
    de verdade para a mesma decisão, e esta lia a mais fraca: o daemon sobe pelo
    systemd com `Environment=PYTHONUNBUFFERED=1` e mais nada, então a variável
    **nunca chega aqui** por esse caminho.

    O estado em que os dois se contradizem não é hipotético — é o que o próprio
    instalador produz. Quem roda `install.sh --keep-dualsense-mic` sai com a
    marca do gesto gravada (`install.sh:4039`) e SEM o drop-in 51, e então:

        doctor.sh ....... [OK] microfone ativo é o DualSense (foi pedido)
        system_check .... WirePlumber fixou o DualSense — rode doctor.sh --fix

    O produto mandava desfazer a escolha que a pessoa acabara de fazer no
    instalador, a cada boot do daemon — e `--fix` instala o 51, que rebaixa
    justamente o microfone pedido. **Quem usa o mic do controle por
    acessibilidade seguiria a instrução do produto e perderia o microfone.**

    A cura é a regra da casa, sem novidade: *quando um valor tem dono, a régua
    PERGUNTA ao dono*. Os cinco degraus abaixo são os do `doctor.sh`, na mesma
    ordem e pela mesma razão — a ordem é a hierarquia de quem manda, e o último
    degrau é o que diz que **"não sei" nunca é "o usuário pediu"**.
    """
    from hefesto_dualsense4unix.utils.xdg_paths import wireplumber_nome_do_dropin

    conf = _dir_dos_dropins()
    if (conf / wireplumber_nome_do_dropin("52-hefesto-dualsense-disable-source.conf")).exists():
        return False
    if os.environ.get(
        "HEFESTO_DUALSENSE4UNIX_DUALSENSE_MIC_INTENDED", ""
    ).strip().lower() in ("1", "true", "yes"):
        return True
    if (conf / wireplumber_nome_do_dropin("51-hefesto-dualsense-no-default-source.conf")).exists():
        return False
    return _marca_do_gesto_do_mic().exists()


def _dualsenses_no_cabo_sem_ucm() -> list[str]:
    """Os nomes longos das placas de DualSense no cabo que o UCM não alcança.

    O mesmo teste do `check_ucm_do_dualsense` do `doctor.sh`: o
    `scripts/install_ucm_dualsense.sh` grava um gancho por controlador USB em
    `conf.d/USB-Audio/<nome longo>.conf`, e uma placa sem o gancho abre sem o
    sink `…HiFi__Speaker__sink` — o jogo da Sony pelo Proton não vibra. Uma
    distro sem `ucm.conf` não tem o que armar, e fica calada.
    """
    raiz = Path(_RAIZ_UCM)
    if not (raiz / "ucm.conf").is_file():
        return []
    try:
        linhas = Path(_PROC_CARDS).read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    sem = []
    for linha in linhas:
        nome = linha.strip()
        if not nome.startswith(_NOME_DO_DUALSENSE):
            continue
        if not (raiz / "conf.d" / "USB-Audio" / f"{nome}.conf").is_file():
            sem.append(nome)
    return sem


def system_warnings() -> list[str]:
    """Avisos de infra para o boot. Read-only; nunca levanta, nunca usa sudo."""
    warnings: list[str] = []
    try:
        if _udev_hotplug_outdated():
            warnings.append(
                "regras udev de hotplug desatualizadas (nome de unit antigo) — "
                "rode: sudo bash scripts/install_udev.sh"
            )
        if not _dualsense_mic_intended() and _wireplumber_hijacks_mic():
            warnings.append(
                "WirePlumber fixou o DualSense como microfone padrão — "
                "rode: scripts/doctor.sh --fix"
            )
        if _dualsenses_no_cabo_sem_ucm():
            warnings.append(
                "DualSense no cabo sem o perfil UCM — a vibração dos jogos da "
                "Sony não chega pelo cabo; rode: bash scripts/install_ucm_dualsense.sh"
            )
    except Exception:
        return warnings
    return warnings


LINHA_LE_A_ENTRADA = "o Hefesto lê o teclado e o pedal declarados em «Usar como botões de»"
LINHA_SEM_ACIONADOR_DECLARADO = "nenhum teclado ou pedal declarado em «Usar como botões de»"
LINHA_ACIONADOR_FORA = "o teclado ou o pedal declarado não está ligado nesta máquina"


def permissao_de_ler_a_entrada(
    *,
    raiz: str | None = None,
    abrir: Callable[[str], Any] | None = None,
    declarados: Any = None,
) -> tuple[str, str]:
    """``(tag, mensagem)`` de «o Hefesto lê os aparelhos declarados no «Usar como botões de»?».

    Só o aparelho declarado (o ``acionadores`` do ``maquina.json``) se mede, e pelo mesmo dono
    da 08 e do daemon (``utils.maquina.abrir_o_aparelho_de_entrada``, que nunca prende e pede o
    nó ao broker quando o sistema não deixa abrir). Sem declaração, ``[INFO]``; ``[WARN]`` só
    quando um aparelho declarado e ligado não abre, com a frase do dono.
    """
    from hefesto_dualsense4unix.utils import maquina

    if declarados is None:
        declarados = maquina.carregar_maquina().acionadores
    chaves = {c for c, v in (declarados or {}).items() if isinstance(c, str) and v}
    if not chaves:
        return ("[INFO]", LINHA_SEM_ACIONADOR_DECLARADO)
    base = Path(maquina.RAIZ_DAS_ENTRADAS if raiz is None else raiz)
    abrir = abrir or maquina.abrir_o_aparelho_de_entrada
    ligados = [a for a in maquina.aparelhos_de_entrada(base) if a.chave in chaves]
    leu = False
    for aparelho in ligados:
        try:
            dispositivo = abrir(aparelho.evento)
        except PermissionError:
            nome = aparelho.nome or aparelho.evento
            return ("[WARN]", f"«{nome}»: {maquina.FRASE_SEM_PERMISSAO_DE_LER}")
        except OSError:
            # O nó que some entre o ``/sys`` e o ``/dev`` não mede nada.
            continue
        with contextlib.suppress(OSError):
            dispositivo.close()
        leu = True
    return ("[ OK ]", LINHA_LE_A_ENTRADA) if leu else ("[INFO]", LINHA_ACIONADOR_FORA)


def contrato_do_pad_em_usb(
    *, raiz_modulos: str = "/sys/module", lib_modules: str | None = None
) -> list[str]:
    """Os contratos do kernel que faltam para o pad nascer em USB; [] = nenhum.

    O-PAD-VIRTUAL-E-O-SOM-DELE-NASCEM-NO-MESMO-USB-01 (07/10/2026). É a
    pergunta de `pad_usb.contrato_que_falta`, importada e não redigitada: o
    daemon (`uhid_gamepad.CONTRATO_QUE_FALTA`) e o `doctor.sh` a fazem por
    aqui. Sem o contrato o pad nasce uhid, sem pai USB, e o jogo com a
    biblioteca da Sony pode não casar o som com o controle. Nunca levanta: o
    que não se lê volta como «não sei» (``["?"]``).
    """
    try:
        from hefesto_dualsense4unix.integrations import pad_usb

        return pad_usb.contrato_que_falta(raiz_modulos=raiz_modulos, lib_modules=lib_modules)
    except Exception:
        return ["?"]


def vagas_do_pad_em_usb(*, raiz_modulos: str = "/sys/module") -> tuple[int | None, int]:
    """``(vagas do usbip_vudc no ar, o teto do produto)``; None = o módulo fora do ar.

    O ``modprobe num=8`` do broker não troca o ``num`` de um módulo já
    carregado: com menos vagas que o teto, o pad que sobra nasce uhid, sem par.
    Nunca levanta.
    """
    try:
        import os

        from hefesto_dualsense4unix.integrations import pad_usb

        caminho = os.path.join(raiz_modulos, "usbip_vudc", "parameters", "num")
        return pad_usb.vagas_do_vudc(caminho), pad_usb.MAX_PADS_USB
    except Exception:
        return None, 0


__all__ = [
    "contrato_do_pad_em_usb",
    "fonte_configurada_do_wireplumber",
    "permissao_de_ler_a_entrada",
    "system_warnings",
    "vagas_do_pad_em_usb",
]
