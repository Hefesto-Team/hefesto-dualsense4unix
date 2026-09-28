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

**620 ms, sem ninguém encostar no controle**, e o áudio captado parava no mesmo
instante. No mesmo dia, o GATING do rádio (o bit oscilando a ~16,7 Hz com o
microfone no ar) cortava o microfone aos 1,1 s pelo mesmo caminho.

AS CURAS DE 10/09 FORAM DUAS GUARDAS SOBRE O BIT DE MUDO — uma fila com as
marcas do que NÓS pedimos, e uma sustentação de 300 ms. As duas tinham furo:
uma escrita que não ecoava (o bit já estava lá) deixava a marca viva e ela
engolia o aperto SEGUINTE dela; e um aperto com o bit parado sumia calado.

28/09/2026 — A CURA FOI À ORIGEM (O-BOTAO-DO-MIC-SO-OBEDECE-A-MAO-01): a borda
passou a ser o BOTÃO (`buttons[2]` bit 2), que nem o eco nem o gating apertam.
As réguas deste arquivo ficam, com o mesmo cenário do fio — o bit ecoando, o
bit oscilando — e o botão parado; e ganham a do furo da marca velha.

A MORDIDA: volte `_registrar_borda_do_mic` a contar a virada do bit de estado
e `test_o_eco_da_nossa_escrita_nao_conta_borda` e
`test_o_gating_do_firmware_nao_e_o_dedo_dela` reprovam.
"""
from __future__ import annotations

from typing import Any

import pytest

from hefesto_dualsense4unix.core import backend_pydualsense as bp
from hefesto_dualsense4unix.integrations.dualsense_bt_audio import STATUS_MIC_MUDO


class _Handle(bp._PinnedPyDualSense):
    """O handle de produção por `__new__`, com o estado do DONO ÚNICO.

    Os métodos sob prova — `_registrar_borda_do_mic` e `set_microphone_mute`
    — são os de verdade; reimplementá-los faria esta régua medir a si mesma.
    """

    def __new__(cls) -> Any:
        return object.__new__(cls)

    def __init__(self) -> None:
        self._audio_status = None
        self._mic_mute_desejado = None
        self.zerar_estado_da_borda_do_mic()

    def report(self, mudo: bool, *, botao: bool = False, vezes: int = 10) -> None:
        """O mesmo report `vezes` vezes — no fio o valor se repete ~10x."""
        for _ in range(vezes):
            self._registrar_borda_do_mic(STATUS_MIC_MUDO if mudo else 0x00, botao)

    def aperta(self, *, antes: bool, depois: bool) -> None:
        """O dedo desce com o firmware em `antes`, o kernel vira para `depois`."""
        self.report(antes, botao=True, vezes=2)
        self.report(depois, botao=True, vezes=6)
        self.report(depois)

    def oscila(self, vezes: int) -> None:
        """O GATING: o bit alterna e nunca fica, com o botão parado."""
        valor = bool(self._mic_mudo)
        for _ in range(vezes):
            valor = not valor
            self.report(valor)


@pytest.fixture(autouse=True)
def _relogio(monkeypatch: pytest.MonkeyPatch) -> None:
    """O carimbo do aperto sai do ponto de injeção, nunca da stdlib."""
    marca = {"agora": 1000.0}

    def _andar() -> float:
        marca["agora"] += 0.006
        return marca["agora"]

    monkeypatch.setattr(bp, "_relogio_da_borda", _andar)


@pytest.fixture()
def handle() -> _Handle:
    h = _Handle()
    h.report(True)   # a primeira leitura só adota o estado
    assert h._mic_mudo_seq == 0
    return h


def test_o_gating_do_firmware_nao_e_o_dedo_dela(handle: _Handle) -> None:
    """40 oscilações a ~16,7 Hz não são 40 apertos — não são aperto nenhum."""
    handle.oscila(40)
    assert handle._mic_mudo_seq == 0, (
        f"o gating do firmware virou {handle._mic_mudo_seq} aperto(s) dela — "
        "é o corte de 1,1 s do microfone por rádio"
    )


def test_depois_do_gating_o_dedo_dela_continua_valendo(handle: _Handle) -> None:
    """A cura não pode virar mordaça: o botão tem de sobreviver ao gating."""
    handle.oscila(40)
    estado = bool(handle._mic_mudo)
    handle.aperta(antes=estado, depois=not estado)
    assert handle._mic_mudo_seq == 1, (
        "depois do gating o aperto dela parou de contar — a guarda virou "
        "mordaça, que é a cura errada"
    )


def test_o_gesto_DELA_conta_borda(handle: _Handle) -> None:  # noqa: N802
    """O positivo, e ele vem primeiro: sem isto a cura poderia matar tudo."""
    handle.aperta(antes=True, depois=False)
    assert handle._mic_mudo_seq == 1, (
        "o aperto dela no botão do microfone TEM de contar — o hid-playstation "
        "consome o botão e não o entrega como evento"
    )


def test_o_eco_da_nossa_escrita_nao_conta_borda(handle: _Handle) -> None:
    """O caso EXATO da bancada dela: nós pedimos, e o eco volta."""
    handle.set_microphone_mute(False)   # o daemon liga o microfone
    handle.report(False)                # o firmware ecoa a nossa própria ordem
    assert handle._mic_mudo_seq == 0, (
        "o eco da nossa escrita virou «ela apertou o botão» — é o laço de "
        "10/09/2026, que desligava o microfone 620 ms depois de ligá-lo"
    )


def test_depois_do_eco_o_botao_e_dela(handle: _Handle) -> None:
    """Depois do eco, cada aperto dela conta — nos dois sentidos."""
    handle.set_microphone_mute(False)
    handle.report(False)                          # o eco
    handle.aperta(antes=False, depois=True)       # ela calou
    assert handle._mic_mudo_seq == 1
    handle.aperta(antes=True, depois=False)       # e ligou de novo
    assert handle._mic_mudo_seq == 2


def test_a_escrita_que_nao_ecoou_nao_engole_o_aperto_seguinte(handle: _Handle) -> None:
    """O furo da fila de marcas: pedir o que já vale não ecoa, e a marca ficava.

    O «calado» do perfil pede mudo sobre um microfone já mudo. A marca antiga
    esperava um eco que nunca vinha — e engolia o PRIMEIRO aperto dela que
    levasse o bit ao mesmo valor. Medido nesta árvore com o leitor de antes:
    dois apertos, uma borda.
    """
    handle.set_microphone_mute(True)              # o bit já está mudo
    handle.report(True)
    handle.aperta(antes=True, depois=False)
    handle.aperta(antes=False, depois=True)
    assert handle._mic_mudo_seq == 2, "um aperto dela foi engolido como eco"


def test_devolver_a_posse_nao_engole_borda(handle: _Handle) -> None:
    """`None` devolve o campo ao kernel — e não engole borda nenhuma."""
    handle.set_microphone_mute(None)
    handle.aperta(antes=True, depois=False)
    assert handle._mic_mudo_seq == 1
