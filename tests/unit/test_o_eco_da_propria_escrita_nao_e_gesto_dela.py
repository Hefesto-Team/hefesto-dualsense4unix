"""A borda do botão do microfone não conta o ECO da nossa própria escrita.

O DEFEITO ERA UM LAÇO FECHADO, medido na bancada dela em 10/09/2026 com o
DualSense do rádio na mesa::

    1. o daemon liga o microfone            -> set_microphone_mute(False)
    2. o firmware apaga o bit de mudo
    3. a mudança volta no report de entrada
    4. `_registrar_borda_do_mic` incrementava o contador de bordas
    5. `mic_da_mesa_loop` lia isso como "ela apertou o botão do microfone"
    6. o daemon DESLIGAVA o microfone

No journal dela::

    02:11:15.541  bt_mic_palavra_dela   ligado=True
    02:11:15.547  bt_mic_pedido         ligar=True  seq=4
    02:11:16.164  mic_da_mesa_borda     mudo=True  repiques_engolidos=3  seq=5
    02:11:16.166  bt_mic_pedido         ligar=False seq=5

**620 ms, sem ninguém encostar no controle.** E o áudio captado parava no mesmo
instante: o perfil de energia da gravação dava `53 267 121 102 73 34 35 71` nos
primeiros 800 ms e zero pelo resto — **o microfone captava, e o daemon o
desligava sozinho.**

O contador de bordas está CERTO em existir: o `hid-playstation` consome o botão
do microfone e não o entrega como evento evdev, então a única pista de que ela
apertou é a mudança do bit `STATUS_MIC_MUDO`. O que faltava era distinguir a
mudança que ELA causou da que NÓS causamos.

A MORDIDA: apagar a marca de `set_microphone_mute` (ou o ramo que a consome)
faz `test_o_eco_da_nossa_escrita_nao_conta_borda` reprovar.
"""
from __future__ import annotations

import pytest

from hefesto_dualsense4unix.integrations.dualsense_bt_audio import STATUS_MIC_MUDO


class _HandleDeMentira:
    """O mínimo do handle real para exercitar o contador de bordas.

    Ele reusa os métodos DE VERDADE do backend — `_registrar_borda_do_mic` e
    `set_microphone_mute` — em vez de reimplementá-los, que é o que faria esta
    régua medir a si mesma.
    """

    def __init__(self) -> None:
        from hefesto_dualsense4unix.core.backend_pydualsense import _PinnedPyDualSense as _Alvo

        self._mic_mudo: bool | None = None
        self._mic_mudo_seq = 0
        self._mic_mudo_em: float | None = None
        self._mudos_que_pedimos: list[bool] = []
        self._mic_mute_desejado: bool | None = None
        self._registrar_borda_do_mic = _Alvo._registrar_borda_do_mic.__get__(self)
        self._set_mute = _Alvo.set_microphone_mute.__get__(self)

    def chega_report(self, mudo: bool) -> None:
        self._registrar_borda_do_mic(STATUS_MIC_MUDO if mudo else 0x00)


@pytest.fixture()
def handle() -> _HandleDeMentira:
    h = _HandleDeMentira()
    h.chega_report(True)   # a primeira leitura só adota o estado
    assert h._mic_mudo_seq == 0
    return h


def test_o_gesto_DELA_conta_borda(handle: _HandleDeMentira) -> None:  # noqa: N802
    """O positivo, e ele vem primeiro: sem isto a cura poderia matar tudo."""
    handle.chega_report(False)
    assert handle._mic_mudo_seq == 1, (
        "o aperto dela no botão do microfone TEM de contar — é a única pista "
        "que existe, porque o hid-playstation consome o botão e não o entrega"
    )


def test_o_eco_da_nossa_escrita_nao_conta_borda(handle: _HandleDeMentira) -> None:
    """O caso EXATO da bancada dela: nós pedimos, e o eco volta."""
    handle._set_mute(False)          # o daemon liga o microfone
    handle.chega_report(False)       # o firmware ecoa a nossa própria ordem
    assert handle._mic_mudo_seq == 0, (
        "o eco da nossa escrita virou «ela apertou o botão» — é o laço de "
        "10/09/2026, que desligava o microfone 620 ms depois de ligá-lo"
    )


def test_o_eco_e_consumido_UMA_vez(handle: _HandleDeMentira) -> None:  # noqa: N802
    """Depois do eco, o botão volta a ser dela — senão a cura vira mordaça."""
    handle._set_mute(False)
    handle.chega_report(False)       # o eco, engolido
    handle.chega_report(True)        # ela apertou de verdade
    assert handle._mic_mudo_seq == 1
    handle.chega_report(False)       # e de novo
    assert handle._mic_mudo_seq == 2


def test_o_gesto_dela_no_sentido_CONTRARIO_ao_que_pedimos_conta(handle) -> None:  # noqa: N802
    """Pedimos «cala» e ela apertou para FALAR: isso é gesto, não eco.

    O estado da fixture é mudo=True. Pedimos `True` — o que já vale, e portanto
    não gera eco nenhum — e então ela aperta e DESMUTA. A mudança existe e vai
    no sentido oposto ao do nosso pedido: é dela, e conta.
    """
    handle._set_mute(True)
    handle.chega_report(False)
    assert handle._mic_mudo_seq == 1, (
        "a marca só cobre a mudança que CASA com o que pedimos; o contrário "
        "é sempre dela"
    )


def test_devolver_a_posse_nao_prevê_eco(handle: _HandleDeMentira) -> None:
    """`None` devolve o campo ao kernel — e não engole borda nenhuma."""
    handle._set_mute(None)
    handle.chega_report(False)
    assert handle._mic_mudo_seq == 1
