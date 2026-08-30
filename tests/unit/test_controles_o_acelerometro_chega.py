"""ONDA-CONTROLES-04 — o acelerômetro sai do node e chega ao card.

**O fato que originou esta sprint, e ele é o oposto do que se dizia.** Correu
por esta casa a frase de que *"o aparelho não entrega o acelerômetro — nem pelo
cabo, nem pelo rádio"*. É falsa, e a medição é de 15/08/2026, nos DOIS
transportes e em quatro unidades (cabo 1,0095 g e 0,9777 g; rádio 0,9899 g e
0,9777 g), com o módulo da gravidade como régua absoluta. Refeita em 29/08 com
dois DualSense no cabo desta bancada: `EVIOCGABS` devolveu `res=8192` nos três
eixos dos dois, e o vetor em repouso mediu 0,996 g e 0,992 g.

Quem não entregava era o PRODUTO: o `MotionSensorReader` abria o node dos SEIS
eixos e lia três. Os quatro testes abaixo são um por degrau da cadeia — leitor,
hub, tela e desconexão —, e cada um morde num lugar diferente:

1. **o leitor** — os dois sensores vêm do mesmo `eventN` e NÃO se misturam;
2. **o hub** — `accel` e `gyro` são chaves independentes no `state_full`;
3. **a tela** — sem o bloco, o módulo SOME do card; nunca três zeros;
4. **desconectou** — zera os SEIS, não três.

O caso 3 é o que mais engana num teste ingênuo: um acelerômetro parado NÃO
marca zero, marca ~1 g no eixo que aponta para o chão. Três barras no centro
não diriam "em repouso" — diriam "este controle está em queda livre".
"""
from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from hefesto_dualsense4unix.app.widgets.controller_card import (
    accel_do_inputs,
    gyro_do_inputs,
)
from hefesto_dualsense4unix.core.evdev_reader import (
    DUALSENSE_ACC_RES_PER_G,
    MotionSensorReader,
    g_por_unidade,
)
from hefesto_dualsense4unix.daemon.sensor_hub import SensorHub


class _Ecodes:
    """Só as constantes que o reader consulta (o módulo real é enorme)."""

    EV_ABS = 3
    EV_KEY = 1
    ABS_X = 0
    ABS_Y = 1
    ABS_Z = 2
    ABS_RX = 3
    ABS_RY = 4
    ABS_RZ = 5


def _evento(code: int, value: int, tipo: int = _Ecodes.EV_ABS) -> Any:
    return SimpleNamespace(type=tipo, code=code, value=value)


def _reader() -> MotionSensorReader:
    """Reader sem `/dev/input`, com as DUAS escalas já conhecidas.

    As duas são diferentes de propósito (1024 contra 8192): é assim que um
    eixo lido pela tabela errada aparece na asserção como número, e não como
    coincidência.
    """
    reader = MotionSensorReader(device_path=None)
    reader._resolucoes = {"x": 1024, "y": 1024, "z": 1024}
    reader._resolucoes_accel = {"x": 8192, "y": 8192, "z": 8192}
    return reader


# ---------------------------------------------------------------------------
# 1. O leitor
# ---------------------------------------------------------------------------


def test_g_por_unidade_usa_a_resolucao_do_node() -> None:
    """A escala sai do `absinfo`, não de constante — como a do giro."""
    assert g_por_unidade(8192, 8192) == pytest.approx(1.0)
    assert g_por_unidade(-4096, 8192) == pytest.approx(-0.5)
    # Node com OUTRA escala: quem manda é o que ele declara.
    assert g_por_unidade(4096, 4096) == pytest.approx(1.0)


def test_g_por_unidade_sem_resolucao_cai_no_default_do_kernel() -> None:
    """Zero/negativo não pode virar valor cru: seriam "8192 g" na tela."""
    assert g_por_unidade(DUALSENSE_ACC_RES_PER_G, 0) == pytest.approx(1.0)
    assert g_por_unidade(DUALSENSE_ACC_RES_PER_G, -5) == pytest.approx(1.0)


def test_o_leitor_traz_os_tres_eixos_do_acelerometro() -> None:
    """`ABS_X/Y/Z` do mesmo node viram g no `accel_snapshot()`."""
    reader = _reader()
    reader._handle_event(_evento(_Ecodes.ABS_X, -409), _Ecodes)
    reader._handle_event(_evento(_Ecodes.ABS_Y, 8028), _Ecodes)
    reader._handle_event(_evento(_Ecodes.ABS_Z, 1409), _Ecodes)

    snap = reader.accel_snapshot()
    assert (snap.x, snap.y, snap.z) == pytest.approx(
        (-409 / 8192, 8028 / 8192, 1409 / 8192)
    )
    # A régua absoluta: parado, o módulo do vetor é a gravidade.
    modulo = (snap.x**2 + snap.y**2 + snap.z**2) ** 0.5
    assert modulo == pytest.approx(1.0, abs=0.02)


def test_os_dois_sensores_nao_se_misturam_no_mesmo_node() -> None:
    """MORDIDA. O erro que um teste ingênuo não pega: os eixos trocados.

    Os seis códigos chegam pelo MESMO `eventN` e pelo MESMO laço. Só o giro
    andou → o acelerômetro fica onde estava, e vice-versa. Escreva
    `self._accel[eixo]` no laço do giro (ou o contrário) e as duas metades
    deste teste reprovam.

    A escala é a segunda trava: 8192 unidades são 1 g pela tabela do
    acelerômetro e 8,0 pela do giro. Um eixo lido pela tabela errada não passa
    despercebido — aparece com uma ordem de grandeza de diferença.
    """
    reader = _reader()
    reader._handle_event(_evento(_Ecodes.ABS_RX, 2048), _Ecodes)
    reader._handle_event(_evento(_Ecodes.ABS_RY, -1024), _Ecodes)
    reader._handle_event(_evento(_Ecodes.ABS_RZ, 512), _Ecodes)

    assert (reader.snapshot().x, reader.snapshot().y, reader.snapshot().z) == (
        pytest.approx((2.0, -1.0, 0.5))
    )
    acc = reader.accel_snapshot()
    assert (acc.x, acc.y, acc.z) == (0.0, 0.0, 0.0), (
        "o giroscópio andou e o acelerômetro andou junto: os dois laços estão "
        "escrevendo no mesmo dicionário"
    )

    reader = _reader()
    reader._handle_event(_evento(_Ecodes.ABS_X, 8192), _Ecodes)
    reader._handle_event(_evento(_Ecodes.ABS_Y, 8192), _Ecodes)

    gyro = reader.snapshot()
    assert (gyro.x, gyro.y, gyro.z) == (0.0, 0.0, 0.0), (
        "o acelerômetro andou e o giroscópio andou junto — as barras de giro "
        "pulariam com a gravidade, sem ninguém girar nada"
    )
    assert reader.accel_snapshot().x == pytest.approx(1.0)


def test_evento_que_nao_e_dos_seis_eixos_nao_move_nada() -> None:
    """`EV_KEY` e um `ABS` de outro código passam sem tocar em sensor nenhum."""
    reader = _reader()
    reader._handle_event(_evento(_Ecodes.ABS_X, 8192, tipo=_Ecodes.EV_KEY), _Ecodes)
    reader._handle_event(_evento(99, 8192), _Ecodes)

    assert reader.accel_snapshot() == reader.accel_snapshot().__class__()
    assert reader.snapshot() == reader.snapshot().__class__()


def test_o_open_le_as_duas_escalas_do_absinfo() -> None:
    """Uma passada só lê a resolução dos SEIS eixos, cada uma no seu lugar."""
    reader = MotionSensorReader(device_path=None)
    escalas = {0: 8192, 1: 8192, 2: 4096, 3: 1024, 4: 1024, 5: 512}
    reader._on_device_opened(
        SimpleNamespace(absinfo=lambda code: SimpleNamespace(resolution=escalas[code]))
    )

    assert reader._resolucoes == {"x": 1024, "y": 1024, "z": 512}
    assert reader._resolucoes_accel == {"x": 8192, "y": 8192, "z": 4096}


# ---------------------------------------------------------------------------
# 2. O hub
# ---------------------------------------------------------------------------


class _MotionCompleto:
    """Dublê de reader que entrega os dois sensores."""

    def snapshot(self) -> Any:
        return SimpleNamespace(x=1.5, y=-2.5, z=0.25)

    def accel_snapshot(self) -> Any:
        return SimpleNamespace(x=-0.0049, y=0.9812, z=0.1719)

    def stop(self) -> None:
        """Nada a parar no dublê."""


class _MotionSoGiro:
    """Reader ANTIGO: sabe o giro e não sabe o acelerômetro."""

    def snapshot(self) -> Any:
        return SimpleNamespace(x=1.5, y=-2.5, z=0.25)

    def stop(self) -> None:
        """Nada a parar no dublê."""


class _MotionGiroQuebrado:
    """O giro levanta, o acelerômetro responde — o node sumiu no meio."""

    def snapshot(self) -> Any:
        raise RuntimeError("node sumiu no meio da leitura")

    def accel_snapshot(self) -> Any:
        return SimpleNamespace(x=-0.0049, y=0.9812, z=0.1719)

    def stop(self) -> None:
        """Nada a parar no dublê."""


class _MotionQueExplode:
    """Reader que levanta nos DOIS: o `state_full` não pode cair por isso."""

    def snapshot(self) -> Any:
        raise RuntimeError("node sumiu no meio da leitura")

    def accel_snapshot(self) -> Any:
        raise RuntimeError("node sumiu no meio da leitura")

    def stop(self) -> None:
        """Nada a parar no dublê."""


def _hub_com(motion: Any) -> SensorHub:
    hub = SensorHub(auto_manutencao=False)
    hub._motion["aabbcc000001"] = motion
    return hub


def test_o_hub_publica_accel_ao_lado_de_gyro() -> None:
    leitura = _hub_com(_MotionCompleto()).leitura("aabbcc000001")

    assert leitura["gyro"] == {"x": 1.5, "y": -2.5, "z": 0.25}
    assert leitura["accel"] == {"x": -0.005, "y": 0.981, "z": 0.172}


def test_reader_sem_acelerometro_publica_o_giro_e_mais_nada() -> None:
    """Contrato do daemon ANTIGO: reader sem `accel_snapshot` continua servindo.

    Isto NÃO é a mordida dos dois `suppress` — a primeira versão deste teste
    dizia que era, e a medição derrubou: com um bloco só ele passa igual,
    porque o `out["gyro"]` já foi atribuído quando o `AttributeError` sobe. A
    mordida verdadeira está no teste seguinte, e é no sentido contrário.
    """
    leitura = _hub_com(_MotionSoGiro()).leitura("aabbcc000001")

    assert leitura["gyro"] == {"x": 1.5, "y": -2.5, "z": 0.25}
    assert "accel" not in leitura


def test_giro_quebrado_nao_leva_o_acelerometro_junto() -> None:
    """MORDIDA. Junte os dois `suppress` do hub num só e isto reprova.

    Com um bloco só, o `snapshot()` que levanta aborta o bloco ANTES de chegar
    ao `accel_snapshot()`: o acelerômetro sumiria da tela por causa de um
    defeito do giroscópio, e os dois são sensores independentes do mesmo node.
    """
    leitura = _hub_com(_MotionGiroQuebrado()).leitura("aabbcc000001")

    assert "gyro" not in leitura
    assert leitura["accel"] == {"x": -0.005, "y": 0.981, "z": 0.172}


def test_reader_que_explode_nao_derruba_a_leitura() -> None:
    assert _hub_com(_MotionQueExplode()).leitura("aabbcc000001") == {}


def test_sem_reader_de_motion_nao_ha_nem_gyro_nem_accel() -> None:
    """Ausência é resposta: controle sem node não ganha zero fingindo repouso."""
    leitura = SensorHub(auto_manutencao=False).leitura("aabbcc000002")

    assert "gyro" not in leitura
    assert "accel" not in leitura


# ---------------------------------------------------------------------------
# 3. A tela
# ---------------------------------------------------------------------------


def test_accel_do_inputs_le_o_bloco() -> None:
    assert accel_do_inputs({"accel": {"x": -0.005, "y": 0.981, "z": 0.172}}) == (
        pytest.approx((-0.005, 0.981, 0.172))
    )


@pytest.mark.parametrize(
    "inputs",
    [
        None,
        "não é dicionário",
        {},
        {"accel": None},
        {"accel": "chegou como texto"},
        {"accel": {"x": 0.1, "y": 0.2}},  # falta o z
        {"accel": {"x": 0.1, "y": 0.2, "z": "nada"}},
        {"gyro": {"x": 1.0, "y": 2.0, "z": 3.0}},  # daemon antigo: só o giro
    ],
)
def test_sem_bloco_utilizavel_o_modulo_some_em_vez_de_zerar(inputs: Any) -> None:
    """MORDIDA. Troque o `return None` por `return (0.0, 0.0, 0.0)` e reprova.

    E aqui o zero mente DUAS vezes: além de dizer "eu sei" quando não se sabe,
    ele desenha um estado que o aparelho não produz parado. Um acelerômetro em
    repouso marca ~1 g; três zeros são queda livre.
    """
    assert accel_do_inputs(inputs) is None


def test_o_acelerometro_nao_rouba_o_bloco_do_giroscopio() -> None:
    """Cada função lê a SUA chave — o molde copiado não pode ficar pela metade."""
    inputs = {
        "gyro": {"x": 143.2, "y": -412.0, "z": 22.8},
        "accel": {"x": -0.005, "y": 0.981, "z": 0.172},
    }

    assert gyro_do_inputs(inputs) == pytest.approx((143.2, -412.0, 22.8))
    assert accel_do_inputs(inputs) == pytest.approx((-0.005, 0.981, 0.172))


# ---------------------------------------------------------------------------
# 4. Desconectou
# ---------------------------------------------------------------------------


def test_desconectar_zera_os_seis_eixos() -> None:
    """MORDIDA. Tire `self._accel` do `_reset_on_disconnect` e isto reprova.

    O acelerômetro congelado é pior que o giro congelado: parado ele marca ~1 g,
    então o último valor desenharia um controle de pé, para sempre, num controle
    que não está mais na mesa.
    """
    reader = _reader()
    reader._handle_event(_evento(_Ecodes.ABS_RX, 2048), _Ecodes)
    reader._handle_event(_evento(_Ecodes.ABS_Y, 8192), _Ecodes)
    assert reader.snapshot().x != 0.0
    assert reader.accel_snapshot().y != 0.0

    reader._reset_on_disconnect()

    snap, acc = reader.snapshot(), reader.accel_snapshot()
    assert (snap.x, snap.y, snap.z) == (0.0, 0.0, 0.0)
    assert (acc.x, acc.y, acc.z) == (0.0, 0.0, 0.0)
    assert reader._resolucoes == {}
    assert reader._resolucoes_accel == {}
