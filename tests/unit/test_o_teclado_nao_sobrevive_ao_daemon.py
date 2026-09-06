#!/usr/bin/env python3
"""A RÉGUA DO TECLADO ÓRFÃO — quem fecha o que o daemon abriu.

O DEFEITO, NUMA FRASE (medido em 30/08/2026, remedido em 06/09): o daemon abre
o teclado na tela e para sem fechá-lo; o daemon seguinte não sabe que aquele
teclado existe, então o R3 dela não fecha nada e o L3 empilha um segundo por
cima do primeiro. São TRÊS defeitos independentes, e por isso três arrancadas:

  1. `shutdown` (`daemon/connection.py`) fechava o `_keyboard_device` e passava
     direto pelo `_osk_controller`;
  2. `close()` voltava na primeira linha com `self._process is None`, e um
     `_OSKController` recém-criado tem SEMPRE None — o R3 era no-op silencioso;
  3. o guarda do `open()` perguntava pelo mesmo atributo, que não conhece o
     órfão — o L3 empilhava.

## POR QUE ESTA RÉGUA USA PROCESSO DE VERDADE, e qual

Ela abre `sleep`, e isso é a medição do §1 da sprint repetida: **o que se mede
é o CICLO DE VIDA DO PROCESSO, não a janela.** O `sleep` faz o papel do
`wvkbd-mobintl` pelo caminho declarado do produto — `_OSK_SPAWN_ARGS` mais o
cache `_resolved_bin`/`_resolved_checked`/`_resolved_em` do `_resolve`, os
mesmos três atributos que o §4 da sprint manda dublar.

**Nada de janela de verdade, e o motivo é a tela dela**: o teclado na tela é
`layer-shell` e aparece por cima de TODOS os workspaces, o dela inclusive. Um
`wvkbd` de verdade nesta régua nasceria na frente dela.

O que fica REAL é justamente o que decide: o PID é do kernel, o
`/proc/<pid>/comm` é o do kernel, e o `SIGTERM` mata de verdade. Uma régua que
dublasse o `/proc` mediria o dublê — e a adoção conservadora, que é o que separa
esta cura de um `pkill wvkbd`, seria exatamente o que ficaria sem prova.

## AS PROVAS DE QUE A ADOÇÃO NÃO PEGA O QUE NÃO É DELA

Elas não são cortesia: `pkill wvkbd` fecharia o teclado que o COSMIC ou a mão
dela abriu, e isso é estrago, não cura. São TRÊS formas de "o PID existe"
mentir, e cada uma tem caso próprio:

  - PID no arquivo que já morreu → nada é adotado, nada estoura, o L3 abre
    normal;
  - PID VIVO cujo `/proc/<pid>/comm` não é o binário do teclado (um PID
    reciclado pelo kernel) → não é adotado, **e** o R3 não mata o processo
    alheio. As duas metades são casos separados de propósito: num teste só, a
    asserção da recusa dispara primeiro e o estrago nunca chega a ser medido;
  - PID de um DEFUNTO por colher (`Z` no `/proc/<pid>/stat`) → `/proc` e `comm`
    passariam nas três perguntas, e não há teclado na tela nenhum.
"""
from __future__ import annotations

import contextlib
import json
import os
import signal
import subprocess
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.core.keyboard_mappings import (
    TOKEN_CLOSE_OSK,
    TOKEN_TOGGLE_OSK,
)
from hefesto_dualsense4unix.daemon.subsystems import keyboard as subsistema
from hefesto_dualsense4unix.daemon.subsystems.keyboard import _OSKController

#: O dublê do binário do teclado na tela. `sleep` porque ele existe em qualquer
#: máquina que rode esta suíte, morre com `SIGTERM` sem reclamar e — o que
#: importa — tem um `/proc/<pid>/comm` de verdade para a adoção conferir.
_DUBLE = "sleep"
#: Longo o bastante para que a morte medida seja sempre a que a régua causou.
_DUBLE_ARGV = [_DUBLE, "600"]


def _vivo(pid: int) -> bool:
    """O PID existe E ainda roda? Pergunta ao kernel, não a um atributo Python.

    O ZUMBI NÃO CONTA, e essa distinção quase deixou esta régua mentir ao
    contrário: um filho que recebeu `SIGTERM` e cujo pai ainda não chamou `wait`
    mantém `/proc/<pid>` inteiro. Como o pai destes processos é o próprio pytest,
    um `Path("/proc/<pid>").exists()` ingênuo dava "VIVO" para todo teclado que a
    cura tinha acabado de fechar corretamente.
    """
    if not Path(f"/proc/{pid}").exists():
        return False
    # O produto responde a mesma pergunta, e a régua pergunta a ELE — assim as
    # duas nunca divergem sobre o que é "morto".
    return not subsistema._pid_e_zumbi(pid)


def _comm_real(pid: int) -> str | None:
    """O `/proc/<pid>/comm` lido pela régua, sem passar pelo produto.

    Existe para o arranjo do caso do PID reciclado se conferir a si mesmo: se o
    processo alheio tivesse por acaso o mesmo `comm` do dublê, o caso mediria
    outra coisa e ninguém veria.
    """
    try:
        return Path(f"/proc/{pid}/comm").read_text(encoding="utf-8").strip()
    except OSError:
        return None


def _esperar_morrer(pid: int, *, segundos: float = 5.0) -> bool:
    """O `SIGTERM` é assíncrono: espera o kernel derrubar o processo.

    Colhe o corpo pelo caminho (`waitpid` com `WNOHANG`) para a tabela de
    processos de quem roda a suíte não encher de defuntos.

    Sem esta espera a régua ficaria intermitente — e um teste de ciclo de vida
    intermitente é pior que nenhum, porque ensina a ignorar o vermelho.
    """
    limite = time.monotonic() + segundos
    while True:
        with contextlib.suppress(ChildProcessError, OSError):
            os.waitpid(pid, os.WNOHANG)
        if not _vivo(pid):
            return True
        if time.monotonic() >= limite:
            return False
        time.sleep(0.02)


@pytest.fixture
def mesa(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> Iterator[dict[str, Any]]:
    """Um teclado na tela dublado por `sleep`, e um `XDG_RUNTIME_DIR` só desta régua.

    O `XDG_RUNTIME_DIR` próprio importa: o arquivo de sessão é o fio entre dois
    daemons, e um teste que o herdasse do anterior mediria o teclado do vizinho.
    """
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path))
    # Os TRÊS atributos do cache do `_resolve` que a sprint manda dublar vêm
    # pelo caminho declarado: o candidato único é o dublê, e o `which` o acha.
    monkeypatch.setattr(subsistema, "_OSK_CANDIDATES", (_DUBLE,))
    monkeypatch.setattr(subsistema, "_osk_candidatos", lambda: (_DUBLE,))
    monkeypatch.setattr(subsistema, "_OSK_SPAWN_ARGS", {_DUBLE: list(_DUBLE_ARGV)})
    monkeypatch.setattr(
        subsistema.shutil,
        "which",
        lambda nome: f"/usr/bin/{nome}" if nome == _DUBLE else None,
    )
    monkeypatch.setattr(subsistema, "_OSK_SONDA", [(float("-inf"), False)])

    nascidos: list[int] = []
    popen_real = subprocess.Popen

    def _popen(argv: list[str], **kw: Any) -> Any:
        proc = popen_real(argv, **kw)
        nascidos.append(proc.pid)
        return proc

    monkeypatch.setattr(subsistema.subprocess, "Popen", _popen)

    estado = {"nascidos": nascidos, "runtime": tmp_path}
    try:
        yield estado
    finally:
        # Nenhum `sleep` desta régua atravessa para a máquina de quem a rodou —
        # nem quando um caso reprova no meio.
        for pid in nascidos:
            with contextlib.suppress(ProcessLookupError, PermissionError):
                os.kill(pid, signal.SIGKILL)
        for pid in nascidos:
            with contextlib.suppress(ChildProcessError, OSError):
                os.waitpid(pid, 0)


def _arquivo_de_sessao(_runtime: Path) -> Path:
    """O caminho do arquivo de sessão, PERGUNTADO ao produto.

    Não se remonta o caminho à mão aqui: o `runtime_dir` conhece o slug da
    identidade e o fallback para o `cache_dir` quando não há `XDG_RUNTIME_DIR`.
    Uma régua que digitasse o caminho mediria a própria digitação — é a forma
    exata do "a régua digita o que devia LER".
    """
    return subsistema._sessao_do_teclado()


# ---------------------------------------------------------------------------
# (1) o `shutdown` fecha o teclado que o daemon abriu
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_o_shutdown_do_daemon_fecha_o_teclado_na_tela(
    mesa: dict[str, Any],
) -> None:
    """O daemon PARA e o teclado morre junto.

    A MORDIDA: arranque o bloco `osk.close()` do `shutdown`
    (`daemon/connection.py`, ao lado do `_keyboard_device`) — este caso reprova
    dizendo que o processo continua VIVO depois do `shutdown`, que é a linha
    exata do §1 da sprint (`o daemon PARA (shutdown) : VIVO <- ficou na tela
    dela`).
    """
    from hefesto_dualsense4unix.core.controller import ControllerState
    from hefesto_dualsense4unix.core.events import EventBus
    from hefesto_dualsense4unix.daemon.connection import shutdown
    from hefesto_dualsense4unix.daemon.lifecycle import Daemon, DaemonConfig
    from hefesto_dualsense4unix.testing.fake_controller import FakeController

    ctrl = _OSKController()
    ctrl.open()
    pid = mesa["nascidos"][0]
    assert _vivo(pid), "o dublê do teclado na tela não chegou a nascer"

    daemon = Daemon(
        controller=FakeController(
            transport="usb",
            states=[ControllerState(battery_pct=80, l2_raw=0, r2_raw=0,
                                    connected=True, transport="usb")],
        ),
        bus=EventBus(),
        config=DaemonConfig(
            auto_reconnect=False, ipc_enabled=False, udp_enabled=False,
            autoswitch_enabled=False, mouse_emulation_enabled=False,
            keyboard_emulation_enabled=False, plugins_enabled=False,
        ),
    )
    daemon._osk_controller = ctrl

    await shutdown(daemon)

    assert _esperar_morrer(pid), (
        f"o teclado na tela (pid={pid}) SOBREVIVEU ao shutdown do daemon — é o "
        "defeito (1) da sprint: o `shutdown` fecha o `_keyboard_device` e passa "
        "direto pelo `_osk_controller`, e a janela fica na tela dela sem dono")
    assert getattr(daemon, "_osk_controller", None) is None, (
        "o shutdown fechou o teclado mas deixou o controlador pendurado no "
        "daemon — o slot tem de zerar como o dos outros subsystems")


# ---------------------------------------------------------------------------
# (2) o daemon NOVO adota o órfão, e o R3 fecha
# ---------------------------------------------------------------------------


def test_o_daemon_novo_adota_o_orfao_e_o_r3_fecha(mesa: dict[str, Any]) -> None:
    """Ela aperta R3 depois de o daemon reiniciar — e o teclado FECHA.

    O controlador do daemon novo é outro objeto, com `_process is None`. Ele só
    sabe do teclado pelo arquivo de sessão.

    A MORDIDA: arranque a leitura do arquivo de sessão (faça `_adotar_orfao`
    devolver None, ou devolva `close()` ao `if proc is None: return` do começo)
    — este caso reprova dizendo que o R3 virou no-op e o processo continua VIVO.
    """
    antigo = _OSKController()
    antigo.open()
    pid = mesa["nascidos"][0]
    assert _vivo(pid)

    # O daemon parou sem fechar (o defeito (1)) — e nasce um daemon NOVO.
    novo = _OSKController()
    assert novo._process is None, "o controlador novo tem de nascer sem processo"
    assert novo.aberto() is True, (
        "o daemon novo respondeu 'fechado' com o teclado na tela dela — é dessa "
        "mentira que nascem o R3 que não fecha e o L3 que empilha")

    novo.dispatch_token(TOKEN_CLOSE_OSK, "press")

    assert _esperar_morrer(pid), (
        f"o R3 do daemon novo não fechou o teclado órfão (pid={pid}) — defeito "
        "(2) da sprint: `close()` voltava na primeira linha porque "
        "`self._process is None` num controlador recém-criado")
    assert novo.aberto() is False
    assert not _arquivo_de_sessao(mesa["runtime"]).exists(), (
        "o teclado morreu mas o arquivo de sessão ficou apontando para ele — o "
        "PID seguinte que o kernel reciclar herdaria essa anotação")


# ---------------------------------------------------------------------------
# (3) o L3 do daemon novo NÃO empilha
# ---------------------------------------------------------------------------


def test_o_l3_do_daemon_novo_nao_empilha_um_segundo_teclado(
    mesa: dict[str, Any],
) -> None:
    """Um teclado na tela, um só — mesmo com o daemon trocado no meio.

    A MORDIDA: a mesma da (2). Sem a leitura do arquivo de sessão, o guarda do
    `open()` pergunta a um `self._process` que nasce None e este caso reprova
    com DOIS PIDs vivos onde devia haver um.
    """
    antigo = _OSKController()
    antigo.open()
    pid = mesa["nascidos"][0]

    novo = _OSKController()
    novo.dispatch_token(TOKEN_TOGGLE_OSK, "press")

    assert len(mesa["nascidos"]) == 1, (
        "o L3 do daemon novo ABRIU UM SEGUNDO teclado por cima do primeiro — "
        f"pids {mesa['nascidos']!r}. É o defeito (3) da sprint, e a docstring do "
        "controlador já prometia o contrário ('evita stack de janelas "
        "sobrepostas'): a promessa valia dentro de um daemon só")
    # E o alternador continua alternando: o toque seguinte FECHA o órfão.
    novo.dispatch_token(TOKEN_TOGGLE_OSK, "press")
    assert _esperar_morrer(pid), (
        "o segundo toque do L3 no daemon novo não fechou o teclado adotado")


# ---------------------------------------------------------------------------
# AS DUAS PROVAS DE QUE A ADOÇÃO NÃO PEGA O QUE NÃO É DELA
# ---------------------------------------------------------------------------


def test_pid_que_ja_morreu_nao_e_adotado_e_o_l3_abre_normal(
    mesa: dict[str, Any],
) -> None:
    """Arquivo apontando para um defunto: nada é adotado, nada estoura.

    Sem esta prova, uma adoção que confiasse no arquivo faria o L3 achar que já
    há teclado aberto e nunca mais abrir — o produto pararia de responder ao
    botão para sempre, e a causa estaria num arquivo que ninguém olha.
    """
    antigo = _OSKController()
    antigo.open()
    pid = mesa["nascidos"][0]
    # Mata pelo lado de fora, SEM passar pelo produto — o arquivo continua lá.
    os.kill(pid, signal.SIGKILL)
    os.waitpid(pid, 0)
    assert _esperar_morrer(pid)
    assert _arquivo_de_sessao(mesa["runtime"]).exists(), (
        "o arranjo deste caso exige o arquivo de sessão ainda apontando para o "
        "PID morto")

    novo = _OSKController()
    assert novo.aberto() is False, (
        "adotou um PID que já morreu — o L3 nunca mais abriria teclado nenhum")
    novo.dispatch_token(TOKEN_TOGGLE_OSK, "press")
    assert len(mesa["nascidos"]) == 2, (
        f"com o órfão morto, o L3 tinha de ABRIR: {mesa['nascidos']!r}")
    assert _vivo(mesa["nascidos"][1])


def test_o_defunto_por_colher_nao_conta_como_teclado_na_tela(
    mesa: dict[str, Any],
) -> None:
    """Um zumbi tem `/proc` e `comm` intactos — e não desenha teclado nenhum.

    A TERCEIRA FORMA DE "O PID EXISTE" MENTIR, depois do PID morto e do PID
    reciclado: o processo já morreu e ninguém chamou `wait`. As três perguntas
    da adoção passariam todas — o número está no arquivo, `/proc/<pid>` abre, e
    o `comm` é o do binário certo — e o produto concluiria que há teclado aberto
    onde não há mais nada na tela. O L3 dela nunca mais abriria nenhum.

    A MORDIDA: arranque o `or _pid_e_zumbi(pid)` do `_adotar_orfao` — este caso
    reprova dizendo que o daemon novo achou teclado aberto num defunto.
    """
    antigo = _OSKController()
    antigo.open()
    pid = mesa["nascidos"][0]

    # Mata e NÃO colhe: nada de `waitpid` e nada de `poll()` no `Popen` antigo
    # (o `poll` colhe por dentro, e o zumbi sumiria antes de ser medido).
    os.kill(pid, signal.SIGTERM)
    limite = time.monotonic() + 5.0
    while time.monotonic() < limite and not subsistema._pid_e_zumbi(pid):
        time.sleep(0.02)
    assert Path(f"/proc/{pid}").exists(), (
        "o arranjo deste caso exige `/proc/<pid>` AINDA legível — sem isso ele "
        "vira o caso do PID morto, que já tem régua própria")
    assert subsistema._pid_e_zumbi(pid) is True

    novo = _OSKController()
    assert novo.aberto() is False, (
        f"o daemon novo adotou um DEFUNTO (pid={pid}): `/proc` e `comm` "
        "continuam lá, mas não há teclado na tela dela — e o L3 nunca mais "
        "abriria nenhum")
    novo.dispatch_token(TOKEN_TOGGLE_OSK, "press")
    assert len(mesa["nascidos"]) == 2, (
        f"com o órfão defunto, o L3 tinha de ABRIR: {mesa['nascidos']!r}")


def _pid_reciclado(mesa: dict[str, Any]) -> subprocess.Popen[bytes]:
    """Arma o caso do PID reciclado: um processo ALHEIO com o nosso número anotado.

    O alheio é um `cat` bloqueado na leitura do próprio cano — vivo, real, e com
    um `/proc/<pid>/comm` que não é o do teclado.

    O BINÁRIO ANOTADO TEM DE SER UM CANDIDATO CONHECIDO, e esta linha é a
    cicatriz de uma medição falsa desta mesma régua: a primeira versão anotava
    `wvkbd-mobintl`, que a `mesa` tinha acabado de tirar do `_OSK_CANDIDATES`
    para pôr o dublê no lugar. A adoção recusava pelo guarda do binário
    DESCONHECIDO e nunca chegava à comparação de `comm` — os dois casos abaixo
    passavam VERDES com a conferência do `/proc` inteiramente arrancada, medido
    em 06/09/2026. Anota-se o dublê, então, e a divergência que sobra é
    exatamente a que se quer medir: mesmo nome de binário no arquivo, processo
    vivo de OUTRO nome no `/proc`.
    """
    alheio = subprocess.Popen(
        ["cat"],
        stdin=subprocess.PIPE,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    mesa["nascidos"].append(alheio.pid)
    assert _vivo(alheio.pid)
    assert _comm_real(alheio.pid) != _DUBLE, (
        "o processo alheio tem de ter um `comm` DIFERENTE do binário anotado — "
        "senão este caso não mede a conferência do `/proc`")

    caminho = _arquivo_de_sessao(mesa["runtime"])
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text(
        json.dumps({"pid": alheio.pid, "comm": _DUBLE}),
        encoding="utf-8",
    )
    return alheio


def test_pid_reciclado_pelo_kernel_nao_e_adotado(mesa: dict[str, Any]) -> None:
    """O PID vive, mas o `/proc/<pid>/comm` NÃO é o nosso binário: não é nosso.

    O kernel recicla PIDs; o número anotado pode ter virado o editor dela, o
    navegador, o compositor.
    """
    alheio = _pid_reciclado(mesa)
    try:
        assert _OSKController().aberto() is False, (
            "adotou um PID RECICLADO: o número está no arquivo, mas o processo "
            "vivo com esse número não é o teclado que abrimos")
    finally:
        alheio.kill()
        alheio.wait()


def test_o_r3_nao_mata_o_processo_alheio_do_pid_reciclado(
    mesa: dict[str, Any],
) -> None:
    """ESTE É O CASO QUE SEPARA A CURA DE UM `pkill wvkbd`.

    Fechar por número sem conferir o `comm` mataria programa alheio — e o
    sintoma para ela seria uma janela sumindo quando ela aperta R3.

    Ele é irmão do de cima e mede a metade SEGUINTE de propósito: lá a adoção
    recusa, aqui o R3 chega a agir e tem de não encostar no processo. Num teste
    só, a asserção da recusa dispara primeiro e o estrago nunca chega a ser
    medido — que é como uma cura pela metade atravessaria o vermelho.
    """
    alheio = _pid_reciclado(mesa)
    try:
        _OSKController().dispatch_token(TOKEN_CLOSE_OSK, "press")
        assert _vivo(alheio.pid), (
            f"o R3 MATOU UM PROCESSO ALHEIO (pid={alheio.pid}) — é o estrago "
            "que a adoção conservadora existe para não cometer, e o mesmo que "
            "um `pkill wvkbd` faria com o teclado que o COSMIC abriu")
    finally:
        alheio.kill()
        alheio.wait()


def test_o_arquivo_de_sessao_guarda_pid_e_binario(mesa: dict[str, Any]) -> None:
    """O que o `open()` anota é o PID e o NOME do binário que ELE spawnou.

    O nome gravado é o que o produto MANDOU abrir — não o que o `/proc` diz. É a
    comparação entre os dois que a adoção faz, e ela só tem sentido se as duas
    pontas vierem de origens diferentes.
    """
    ctrl = _OSKController()
    ctrl.open()

    dados = json.loads(_arquivo_de_sessao(mesa["runtime"]).read_text(encoding="utf-8"))
    assert dados == {"pid": mesa["nascidos"][0], "comm": _DUBLE}, (
        f"o arquivo de sessão não guarda o par (pid, binário): {dados!r}")
