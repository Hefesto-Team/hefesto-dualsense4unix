"""A mesa de DOIS: o laço de saída divide o barramento em vez de saturá-lo.

O QUE ESTE ARQUIVO GUARDA
-------------------------
A cura `PERF-MULTI-CONTROLLER-01` / `BUG-MULTI-CONTROLLER-BT-CRC-CONTENTION-01`,
em `core/backend_pydualsense.py`: no fim de todo `connect()`, o estrangulamento
do laço de OUTPUT de cada handle vira `REPORT_THREAD_THROTTLE_SEC * N` (capado
em `REPORT_THREAD_THROTTLE_MAX_SEC`), onde `N` é o número de controles abertos.

O comentário da própria constante diz o que ela previne, com todas as letras:
*"Com 2+ controles são 2+ threads saturando o controlador USB compartilhado — e
o adaptador Bluetooth vive no MESMO controlador (família do storm), degradando o
link BT (`DualSense input CRC's check failed`) e matando o output do controle
BT."* É a forma exata do defeito de 10/08/2026 que a família `combinacao` do
mapa de canais existe para não deixar voltar: **um controle no cabo matava a
saída do controle no rádio**.

POR QUE ELE EXISTE, e o que ele NÃO prova
-----------------------------------------
Em 12/08/2026, com os controles na mesa dela, os dois lados foram MEDIDOS e
gravados em `docs/data/ensaios.csv`: `comb-cabo-radio-saida-2212` (+ o irmão de
rádio) — FF disparado no cabo e no rádio na MESMA janela, os dois vibraram
iguais; e `comb-dois-no-radio-saida-2235` — os DOIS controles do rádio
obedecendo nas duas rotas (0x31 e sysfs). Observados pelo `olho-dela`.

Este arquivo NÃO reproduz aquilo — o encontro de dois escritores com o
controlador USB compartilhado não cabe num teste de unidade. O que ele faz é
impedir que a ÚNICA peça do código que reconhece que *dois controles na mesa não
é o mesmo que um* seja removida sem ninguém perceber. É o que a `ressalva` da
linha `plataforma.limitador_subcomando@dualsense` do mapa já dizia por escrito.

MORDE? Troque, no fim de `connect()`, o `min(REPORT_THREAD_THROTTLE_SEC * n,
REPORT_THREAD_THROTTLE_MAX_SEC)` por `REPORT_THREAD_THROTTLE_SEC` e estes testes
reprovam — inclusive o caso do cabo+rádio, que é a linha do defeito.

MORDIDA PROVADA (15/08/2026, com o `src/` COPIADO para fora da árvore e o
`PYTHONPATH` apontado para a cópia — a árvore de trabalho nunca foi mutada):
ver o bloco `MORDIDA` de cada teste; o resultado dos dois lados está registrado
na coluna `mordida_provada_em` das linhas `combinacao.cabo_e_radio.saida@
dualsense` e `combinacao.dois_no_radio.saida@dualsense` do mapa de canais.

MACs: SEMPRE na faixa forjada canônica da casa (`aa:bb:cc:*`).
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from hefesto_dualsense4unix.core.backend_pydualsense import (
    REPORT_THREAD_THROTTLE_MAX_SEC,
    REPORT_THREAD_THROTTLE_SEC,
    PyDualSenseController,
)
from hefesto_dualsense4unix.core.evdev_reader import EvdevReader

#: Chaves MAC-formadas na faixa forjada (o guarda de anonimato só aceita essas).
CHAVE_CABO = "AA:BB:CC:00:00:01"
CHAVE_RADIO = "AA:BB:CC:00:00:02"


class _FakeTrigger:
    def __init__(self) -> None:
        self.mode: object = None
        self.forces: list[int] = [0] * 7

    def setForce(self, idx: int, value: int) -> None:  # noqa: N802 — API pydualsense
        self.forces[idx] = value


class _FakeLight:
    def __init__(self) -> None:
        self.colors: list[tuple[int, int, int]] = []
        self.playerNumber: object = None  # espelha o atributo da pydualsense

    def setColorI(self, r: int, g: int, b: int) -> None:  # noqa: N802 — API pydualsense
        self.colors.append((r, g, b))


class _FakeAudio:
    def __init__(self) -> None:
        self.mic_led_history: list[bool] = []

    def setMicrophoneLED(self, flag: bool) -> None:  # noqa: N802 — API pydualsense
        self.mic_led_history.append(flag)


class _FakeHandle:
    """Um controle aberto. `transporte` decide se ele está no cabo ou no rádio."""

    def __init__(self, transporte: str = "USB") -> None:
        self.connected = True
        self.triggerL = _FakeTrigger()
        self.triggerR = _FakeTrigger()
        self.light = _FakeLight()
        self.audio = _FakeAudio()
        self.left_motor: list[int] = []
        self.right_motor: list[int] = []
        self.closed = False
        self.conType = type("CT", (), {"name": transporte})()
        #: o que a cura escreve — nasce no valor de UM controle só.
        self._throttle_sec = REPORT_THREAD_THROTTLE_SEC

    def setLeftMotor(self, intensity: int) -> None:  # noqa: N802 — API pydualsense
        self.left_motor.append(intensity)

    def setRightMotor(self, intensity: int) -> None:  # noqa: N802 — API pydualsense
        self.right_motor.append(intensity)

    def close(self) -> None:
        self.closed = True


def _null_evdev() -> EvdevReader:
    """EvdevReader sem device — não interfere no `connect()`."""
    reader = EvdevReader(device_path=None)
    reader._device_path = None
    return reader


def _mesa(*transportes: str) -> list[_FakeHandle]:
    """Abre a mesa com um handle por transporte pedido, via `connect()` real."""
    inst = PyDualSenseController(evdev_reader=_null_evdev())
    handles = [_FakeHandle(t) for t in transportes]
    chaves = [
        (f"AA:BB:CC:00:00:{i:02x}", f"/dev/hidraw{i}".encode(), False)
        for i in range(1, len(handles) + 1)
    ]
    with patch.object(
        PyDualSenseController, "_enumerate_device_keys", return_value=chaves
    ), patch.object(PyDualSenseController, "_open_one", side_effect=list(handles)):
        inst.connect()
    assert len(inst._handles) == len(handles), "a mesa não montou como pedido"
    return handles


def _teto_esperado(n: int) -> float:
    return min(REPORT_THREAD_THROTTLE_SEC * n, REPORT_THREAD_THROTTLE_MAX_SEC)


def test_um_no_cabo_e_um_no_radio_dividem_o_teto_do_laco_de_saida() -> None:
    """A linha do defeito de 10/08: um no cabo, um no rádio, e a saída dos DOIS.

    MORDIDA: troque o `min(REPORT_THREAD_THROTTLE_SEC * n, ...)` do fim de
    `connect()` por `REPORT_THREAD_THROTTLE_SEC` e este teste reprova — o
    controle do cabo volta a martelar o hidraw na taxa de um controle só, que é
    o que satura o controlador USB onde o adaptador Bluetooth também vive.
    """
    cabo, radio = _mesa("USB", "BT")
    esperado = _teto_esperado(2)
    for onde, handle in (("cabo", cabo), ("rádio", radio)):
        assert handle._throttle_sec == pytest.approx(esperado), (
            f"o controle do {onde} ficou com throttle {handle._throttle_sec} e o "
            f"esperado com DOIS na mesa é {esperado}: sem a escala, as duas "
            "threads de output saturam o MESMO controlador USB e a saída do "
            "controle do rádio morre (BUG-MULTI-CONTROLLER-BT-CRC-CONTENTION-01)"
        )


def test_dois_no_radio_dividem_o_mesmo_teto() -> None:
    """O braço de controle: com os DOIS no rádio a conta é a mesma.

    Se a escala fosse por transporte (só quando há alguém no cabo), a mesa de
    dois no rádio ficaria descoberta — e ela é medida do mesmo jeito
    (`comb-dois-no-radio-saida-2235`, olho-dela, 12/08).

    MORDIDA: a mesma do teste acima.
    """
    primeiro, segundo = _mesa("BT", "BT")
    esperado = _teto_esperado(2)
    for i, handle in enumerate((primeiro, segundo), start=1):
        assert handle._throttle_sec == pytest.approx(esperado), (
            f"o {i}º controle do rádio ficou com throttle {handle._throttle_sec}, "
            f"e o esperado com DOIS na mesa é {esperado}"
        )


def test_a_mesa_cheia_nao_passa_do_teto() -> None:
    """Quatro controles: a escala existe, mas tem limite — `* N` sem teto viraria
    latência visível no LED/gatilho."""
    handles = _mesa("USB", "USB", "BT", "BT")
    for handle in handles:
        assert handle._throttle_sec == pytest.approx(REPORT_THREAD_THROTTLE_MAX_SEC)


def test_um_controle_sozinho_nao_paga_o_preco_da_mesa() -> None:
    """Não-regressão do caso de UM: quem está sozinho continua no valor base."""
    (unico,) = _mesa("USB")
    assert unico._throttle_sec == pytest.approx(REPORT_THREAD_THROTTLE_SEC)
