"""GRAB-DOBRADO-01 — o `EVIOCGRAB` do P1 falhava e NINGUÉM tentava de novo.

O DEFEITO, medido no journal dela
=================================
14/08/2026, 15:54:58 — o primário trocou de controle::

    evdev_reopen_requested         reason=retarget
    controller_primary_bound       transport=bt with_evdev=True
    evdev_started                  path=/dev/input/event265
    evdev_grab_failed              err='[Errno 16] ... ocupado' path=/dev/input/event265

O `[Errno 16]` é EBUSY: outro cliente de evdev já tinha o grab exclusivo do nó.
O `grab_state` virou `"failed"` **e ficou lá até aquele daemon morrer** — o
`daemon.state_full` foi lido com `primary_grab_state="failed"` minutos depois, e
de novo em 15/08 às 01:48 com outro PID.

Com o vpad do P1 de pé, `failed` é input **DOBRADO** no jogo: o `EVIOCGRAB` é o
que impede o evdev físico de chegar ao jogo, o broker esconde apenas o `hidraw`,
e o jogo passa a receber cada comando duas vezes.

POR QUE SÓ O PRIMÁRIO — o que já funcionava, e por quê
======================================================
A mesma recusa num **secundário** se cura sozinha: `CoopManager.sync` procura
`grab_state == "failed"` a cada ciclo, derruba o jogador
(`coop_player_grab_failed_retry`) e o respawna; e o vpad dele nem nasce sem grab
confirmado (BUG-COOP-GRAB-PENDING-VPAD-01). O P1 não tinha nenhum dos dois:
`_set_controller_grab(daemon, True)` só roda no **start** da emulação, e
`_reapply_grab` só no **(re)open** do node. Sem troca de node e sem toggle,
ninguém tentava outra vez — e o vpad do P1 seguia de pé com o grab recusado.

Mesma recusa transitória, dois destinos: o secundário volta em um tique, o
primário fica dobrado até um replug ou um restart do daemon. É por isso que o
restart "curava" e o defeito parecia intermitente.

A CURA
======
`reconciliar_grab_do_primario`, chamada pelo poll loop a cada
`GRAB_RECONCILE_SEC` — o irmão que faltava do retry do co-op. Sem poder
destrutivo (não reabre nem recria device nenhum) e com os MESMOS gates do estado
canônico, porque *duplicado > zero controles*.
"""
from __future__ import annotations

import ast
import errno
from pathlib import Path
from typing import Any

from hefesto_dualsense4unix.core.evdev_reader import EvdevReader
from hefesto_dualsense4unix.daemon.subsystems import gamepad as gp

RAIZ = Path(__file__).resolve().parents[2]
LIFECYCLE = RAIZ / "src" / "hefesto_dualsense4unix" / "daemon" / "lifecycle.py"

NODE = Path("/dev/input/event265")  # o nó da medição de 14/08


class _DevOcupado:
    """Um nó de evdev cujo `grab()` levanta EBUSY enquanto `ocupado` for True.

    É o kernel do defeito em miniatura: `EVIOCGRAB` é exclusivo por CLIENTE, e
    o segundo cliente leva `-EBUSY`. Solta-se o `ocupado` para representar o
    outro processo largando o nó (fechar o jogo, o co-op derrubar o jogador, a
    Steam soltar o controle).
    """

    def __init__(self, ocupado: bool = True) -> None:
        self.ocupado = ocupado
        self.grabs = 0
        self.ungrabs = 0

    def grab(self) -> None:
        self.grabs += 1
        if self.ocupado:
            raise OSError(errno.EBUSY, "Dispositivo ou recurso está ocupado")

    def ungrab(self) -> None:
        self.ungrabs += 1


class _Store:
    def __init__(self) -> None:
        self.bumps: list[str] = []

    def bump(self, chave: str) -> None:
        self.bumps.append(chave)


class _Config:
    def __init__(self, emulacao: bool = True) -> None:
        self.gamepad_emulation_enabled = emulacao


class _Controller:
    def __init__(self, evdev: Any) -> None:
        self._evdev = evdev


class _Vpad:
    """Vpad VIVO no sentido de `vpad_vivo` (`_started` não-False)."""

    _started = True


class _Daemon:
    def __init__(
        self,
        evdev: Any,
        *,
        emulacao: bool = True,
        nativo: bool = False,
        vpad: Any = None,
    ) -> None:
        self.controller = _Controller(evdev)
        self.config = _Config(emulacao)
        self.store = _Store()
        self._gamepad_device = _Vpad() if vpad is None else vpad
        self._nativo = nativo

    def is_native_mode(self) -> bool:
        return self._nativo


def _reader_com_grab_recusado(dev: _DevOcupado) -> EvdevReader:
    """Um reader do PRIMÁRIO no estado exato do journal de 14/08 15:54:58.

    `device_path` explícito para o `__init__` não varrer /dev/input (o teste
    roda sem hardware). O `_grab=True` é a INTENÇÃO registrada pelo start da
    emulação; o `failed` é o que o `_reapply_grab` deixou ao levar EBUSY.
    """
    reader = EvdevReader(device_path=NODE)
    reader._active_dev = dev
    reader._grab = True
    reader._grab_state = "failed"
    return reader


# -- Mordida 1: a cura ------------------------------------------------------


def test_o_grab_do_primario_e_retomado_quando_o_no_libera() -> None:
    """A cura, e é a mordida principal.

    Arranque o corpo de `reconciliar_grab_do_primario` (ou o `set_grab` de
    dentro dele) e este teste reprova: o estado fica em `failed` para sempre,
    que é o produto até 15/08/2026 — input dobrado no jogo para o P1 até o
    próximo replug ou restart.
    """
    dev = _DevOcupado(ocupado=True)
    reader = _reader_com_grab_recusado(dev)
    daemon = _Daemon(reader)

    # 1º ciclo: o outro processo ainda segura o nó — nada a fazer além de tentar.
    assert gp.reconciliar_grab_do_primario(daemon) is False
    assert reader.grab_state == "failed"
    assert dev.grabs == 1, "o produto tem de TENTAR de novo, e tentou uma vez"

    # 2º ciclo: continua ocupado. O retry não pode desistir.
    assert gp.reconciliar_grab_do_primario(daemon) is False
    assert dev.grabs == 2

    # O nó liberou (jogo fechado, co-op derrubou o jogador, Steam soltou).
    dev.ocupado = False
    assert gp.reconciliar_grab_do_primario(daemon) is True
    assert reader.grab_state == "held", "o P1 voltou a ser exclusivo do daemon"
    assert "gamepad.grab.recovered" in daemon.store.bumps

    # E depois de retomado a função vira uma comparação de string: sem I/O.
    grabs_antes = dev.grabs
    assert gp.reconciliar_grab_do_primario(daemon) is False
    assert dev.grabs == grabs_antes, "reconciliar com o grab de pé não pode tocar no nó"


def test_cada_recusa_conta_no_store_para_o_doctor_enxergar() -> None:
    """A recusa que PERSISTE não pode ficar muda depois da primeira linha.

    Antes desta entrega o journal tinha UMA linha `evdev_grab_failed`, no
    instante da recusa, e silêncio depois: meia hora de input dobrado ficava
    indistinguível de meio segundo. Arranque o `store.bump` do caminho de falha
    e este teste reprova.
    """
    dev = _DevOcupado(ocupado=True)
    daemon = _Daemon(_reader_com_grab_recusado(dev))
    for _ in range(3):
        gp.reconciliar_grab_do_primario(daemon)
    assert daemon.store.bumps.count("gamepad.grab.retry_failed") == 3


# -- Mordida 2: os gates ("duplicado > zero controles") ---------------------


def test_nao_graba_com_a_emulacao_desligada() -> None:
    """Sem vpad para devolver o controle ao jogo, grabar é ZERO controles.

    Arranque o gate da emulação e este teste reprova — o retry passaria a
    esconder o físico dela de todo jogo com a emulação desligada, que é o
    estrago relatado ao vivo na GUERRA-01.
    """
    dev = _DevOcupado(ocupado=False)
    daemon = _Daemon(_reader_com_grab_recusado(dev), emulacao=False)
    assert gp.reconciliar_grab_do_primario(daemon) is False
    assert dev.grabs == 0


def test_nao_graba_em_modo_nativo() -> None:
    """No Modo Nativo o dispositivo do jogo é o FÍSICO — por escolha dela."""
    dev = _DevOcupado(ocupado=False)
    daemon = _Daemon(_reader_com_grab_recusado(dev), nativo=True)
    assert gp.reconciliar_grab_do_primario(daemon) is False
    assert dev.grabs == 0


def test_nao_graba_com_o_vpad_morto() -> None:
    """VIDA do vpad, não existência (lição 6/#17): `_started=False` não vale.

    Um uhid derrubado por `UHID_STOP` deixa o objeto Python vivo. Grabar por
    causa dele esconderia o físico sem nenhum virtual de pé.
    """

    class _VpadMorto:
        _started = False

    dev = _DevOcupado(ocupado=False)
    daemon = _Daemon(_reader_com_grab_recusado(dev), vpad=_VpadMorto())
    assert gp.reconciliar_grab_do_primario(daemon) is False
    assert dev.grabs == 0


# -- Mordida 3: o reader tem de ACEITAR a nova tentativa --------------------


def test_set_grab_nao_engole_a_retomada_de_um_estado_failed() -> None:
    """A cura depende de `set_grab(True)` REALMENTE tentar quando está `failed`.

    O `BUG-GRAB-DOUBLE-EBUSY-01` pôs um atalho em `set_grab`: com o estado já
    `held`, não re-graba (re-grabar o próprio fd levanta EBUSY espúrio). Se
    algum dia esse atalho crescer para `failed`, a reconciliação vira um no-op
    silencioso e o defeito volta inteiro — sem nenhum outro teste notar.
    """
    dev = _DevOcupado(ocupado=False)
    reader = _reader_com_grab_recusado(dev)
    assert reader.set_grab(True) is True
    assert reader.grab_state == "held"
    assert dev.grabs == 1


def test_grab_do_primario_dobrado_e_a_conta_das_duas_metades() -> None:
    """`failed` sozinho não é o estrago: `failed` COM vpad vivo é.

    A aba Início já fazia esse `and` na mão. A detecção tem um dono agora, e
    arrancar qualquer uma das metades reprova aqui.
    """
    dev = _DevOcupado(ocupado=True)
    reader = _reader_com_grab_recusado(dev)
    assert gp.grab_do_primario_dobrado(_Daemon(reader)) is True
    # Sem emulação não há virtual concorrendo com o físico: não está dobrado.
    assert gp.grab_do_primario_dobrado(_Daemon(reader, emulacao=False)) is False
    # Com o grab de pé, idem.
    reader._grab_state = "held"
    assert gp.grab_do_primario_dobrado(_Daemon(reader)) is False


# -- Mordida 4: a cura tem de estar LIGADA no laço --------------------------
#
# "A casa sabe e o produto não faz" é o defeito mais caro daqui: a cura escrita
# e nunca chamada. Sem este teste, apagar a linha do poll loop devolveria o
# defeito inteiro com a suíte toda verde.


def _poll_loop() -> ast.AsyncFunctionDef:
    arvore = ast.parse(LIFECYCLE.read_text(encoding="utf-8"), filename=str(LIFECYCLE))
    for no in ast.walk(arvore):
        if isinstance(no, ast.AsyncFunctionDef) and no.name == "_poll_loop":
            return no
    raise AssertionError("não achei o _poll_loop")


def test_o_poll_loop_reconcilia_o_grab_do_primario() -> None:
    """Arranque a chamada do laço e este teste reprova."""
    chamadas = [
        no
        for no in ast.walk(_poll_loop())
        if isinstance(no, ast.Call)
        and isinstance(no.func, ast.Name)
        and no.func.id == "reconciliar_grab_do_primario"
    ]
    assert chamadas, (
        "o poll loop não chama mais `reconciliar_grab_do_primario` — o grab do "
        "P1 volta a ficar `failed` para sempre depois de UMA recusa transitória"
    )


def test_a_reconciliacao_do_grab_e_throttada_como_a_do_coop() -> None:
    """Rodar todo tick custaria um `ioctl` a 250 Hz por nada.

    O gate é o MESMO padrão dos outros seis blocos lentos do laço
    (`... >= *_next_at`), e o intervalo tem nome e razão escrita em
    `GRAB_RECONCILE_SEC`.
    """
    from hefesto_dualsense4unix.daemon import lifecycle

    assert lifecycle.GRAB_RECONCILE_SEC > 0
    fonte = LIFECYCLE.read_text(encoding="utf-8")
    assert "grab_reconcile_next_at" in fonte
    assert "GRAB_RECONCILE_SEC" in fonte
