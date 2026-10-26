"""A luz do botão de mudo pisca com som captado, em qualquer modo.

Sprint O-MICROFONE-GANHA-O-MODO-E-A-LUZ-QUE-PULSA-01.

A resposta de 13/10/2026: acesa parada com o microfone ligado, piscando enquanto entra som, apagada
no mudo; sem ajuste novo na tela, e em todo modo (Nativo, Xbox, DualSense, Navegação).

Duas metades, e cada uma tem a sua mordida:

1. ``decidir`` pisca com som captado sem perguntar se há app de fora ouvindo, e o laço manda medir
   todo microfone ligado no cabo (no rádio, medir liga a ponte de áudio do controle e custa banda a
   todos do adaptador: o rádio segue medido só quando alguém já ouve). Mordida: devolver o ramo
   «sem ouvinte acende fixo» ou medir só quem tem ouvinte reprova.
2. No Modo Nativo o laço de escrita do controle cala (o jogo é dono da saída), e a luz decidida
   ficava na memória. Ela sai no report mínimo (só o bit ``0x01`` do flag1 e o ``common[8]``), com o
   ``seq`` e o CRC do handle no rádio. Mordida: tirar a escrita mínima do
   ``PyDualSenseController.set_microphone_led`` reprova.
"""

from __future__ import annotations

import sys
import threading
import types
from typing import Any

import pytest

from hefesto_dualsense4unix.core import ds_output_report as rep
from hefesto_dualsense4unix.core.backend_pydualsense import (
    PyDualSenseController,
    _PinnedPyDualSense,
)
from hefesto_dualsense4unix.daemon.subsystems import luz_do_mic as mod
from hefesto_dualsense4unix.integrations.dualsense_bt_audio import STATUS_MIC_MUDO
from tests.unit.test_a_luz_do_mic_diz_quem_te_escuta import (
    _Controle,
    _Daemon,
    _MedidorFalso,
    _rodar,
)

STARLIGHT = "aabbcc0000f1"
WHITE = "aabbcc0000f2"
COSMIC = "aabbcc0000f3"

_BASE_DO_COMMON = {"usb": 1, "bt": 3}


@pytest.fixture(autouse=True)
def _bancada(monkeypatch: pytest.MonkeyPatch) -> None:
    """As cadências encolhidas e o mundo de fora (as peças A e B) fora do teste."""
    monkeypatch.setattr(mod, "INTERVALO_S", 0.001)
    monkeypatch.setattr(mod, "INTERVALO_DE_QUEM_OUVE_S", 0.0)
    monkeypatch.setattr(mod, "ESPERA_DO_REPORT_S", 0.001)
    monkeypatch.setattr(mod, "SEM_RESPOSTA_ATE_SOLTAR_S", 0.05)
    monkeypatch.setattr(
        mod, "_fontes_para", lambda uniqs, _mesa: {u: f"fonte-de-{u}" for u in uniqs}
    )
    for caminho in (mod.MODULO_DE_QUEM_OUVE, mod.MODULO_DO_NIVEL):
        monkeypatch.setitem(sys.modules, caminho, types.ModuleType(caminho))


@pytest.mark.parametrize(
    ("mudo", "captando", "bateria", "esperado"),
    [
        (True, True, 80, mod.APAGADA),
        (True, None, None, mod.APAGADA),
        (False, False, 80, mod.ACESA),
        (False, None, 80, mod.ACESA),
        (False, True, 80, mod.PISCANDO),
        (False, True, None, mod.PISCANDO),
        (False, True, 29, mod.PISCANDO_LENTO),
        (None, True, 80, None),
    ],
)
def test_a_luz_e_zero_no_mudo_um_no_silencio_e_dois_com_som(
    mudo: bool | None, captando: bool | None, bateria: int | None, esperado: int | None
) -> None:
    """A régua da sprint: 0 no mudo, 1 no silêncio, 2 com som; ninguém pergunta quem ouve.

    Prova da D-1610-A-LUZ-DO-MIC-PISCA-COM-O-SOM.
    """
    assert mod.decidir(mudo=mudo, captando=captando, bateria_pct=bateria) == esperado


def test_a_decisao_nao_pergunta_o_modo_nem_quem_ouve() -> None:
    """A luz é global: o que entra na decisão é o mudo, o som e a bateria, e mais nada."""
    import inspect

    assert set(inspect.signature(mod.decidir).parameters) == {
        "mudo",
        "captando",
        "bateria_pct",
    }


class _ControleComTransporte(_Controle):
    """O dublê da casa, com o transporte de cada controle (o real lê o `conType` do handle)."""

    def __init__(self, *, transportes: dict[str, str], **kw: Any) -> None:
        super().__init__(**kw)
        self.transportes = dict(transportes)

    def describe_controllers(self) -> list[dict[str, object]]:
        itens = super().describe_controllers()
        for item in itens:
            item["transport"] = self.transportes.get(str(item["uniq"]), "usb")
        return itens


def _plantar(
    monkeypatch: pytest.MonkeyPatch, *, ouvintes: dict[str, list[str]], captando: Any
) -> _MedidorFalso:
    peca_a = types.ModuleType(mod.MODULO_DE_QUEM_OUVE)
    peca_a.quem_ouve_agora = lambda _u: dict(ouvintes)  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, mod.MODULO_DE_QUEM_OUVE, peca_a)
    medidor = _MedidorFalso(captando)
    peca_b = types.ModuleType(mod.MODULO_DO_NIVEL)
    peca_b.NivelDoMicrofone = lambda: medidor  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, mod.MODULO_DO_NIVEL, peca_b)
    return medidor


@pytest.mark.asyncio
async def test_no_cabo_a_luz_pisca_com_som_sem_app_nenhum_ouvindo(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """O arranjo da bancada: microfone ligado, ninguém gravando, ela fala; a luz pisca."""
    controle = _ControleComTransporte(
        uniqs=[STARLIGHT], mudo={STARLIGHT: False}, transportes={STARLIGHT: "usb"}
    )
    medidor = _plantar(
        monkeypatch,
        ouvintes={STARLIGHT: []},
        captando=lambda seguidos: dict.fromkeys(seguidos, True),
    )

    em_voo = await _rodar(_Daemon(controle), voltas=120)

    assert any(STARLIGHT in alvos for alvos in medidor.seguidos), (
        "o microfone ligado no cabo não foi medido: sem medida não há som captado, e a luz "
        "ficaria acesa parada enquanto ela fala"
    )
    escritos = [v for u, v in em_voo if u == STARLIGHT]
    assert escritos and escritos[-1] == mod.PISCANDO, escritos


@pytest.mark.asyncio
async def test_no_cabo_o_silencio_volta_a_luz_para_acesa_parada(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Parou de entrar som: acesa, sem oscilar."""
    som = {"agora": True}
    controle = _ControleComTransporte(
        uniqs=[STARLIGHT], mudo={STARLIGHT: False}, transportes={STARLIGHT: "usb"}
    )
    _plantar(
        monkeypatch,
        ouvintes={STARLIGHT: []},
        captando=lambda seguidos: dict.fromkeys(seguidos, som["agora"]),
    )

    def _cala(volta: int) -> None:
        if volta >= 60:
            som["agora"] = False

    em_voo = await _rodar(_Daemon(controle), voltas=140, entre=_cala)

    escritos = [v for u, v in em_voo if u == STARLIGHT]
    assert mod.PISCANDO in escritos
    assert escritos[-1] == mod.ACESA, escritos


@pytest.mark.asyncio
async def test_o_mudo_nao_e_medido_e_apaga(monkeypatch: pytest.MonkeyPatch) -> None:
    """No mudo não se captura nada: a luz apaga e o medidor não abre o microfone do usuário."""
    controle = _ControleComTransporte(
        uniqs=[STARLIGHT], mudo={STARLIGHT: True}, transportes={STARLIGHT: "usb"}
    )
    medidor = _plantar(
        monkeypatch,
        ouvintes={STARLIGHT: []},
        captando=lambda seguidos: dict.fromkeys(seguidos, True),
    )

    em_voo = await _rodar(_Daemon(controle), voltas=120)

    assert all(STARLIGHT not in alvos for alvos in medidor.seguidos), medidor.seguidos
    assert [v for u, v in em_voo if u == STARLIGHT][-1] == mod.APAGADA


@pytest.mark.asyncio
async def test_no_radio_sem_ouvinte_nao_se_liga_a_ponte_so_para_medir(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Medir o rádio sobe a ponte do microfone; sem ninguém ouvindo, ele não é medido."""
    controle = _ControleComTransporte(
        uniqs=[STARLIGHT, WHITE, COSMIC],
        mudo={STARLIGHT: False, WHITE: False, COSMIC: False},
        transportes={STARLIGHT: "usb", WHITE: "bt", COSMIC: "bt"},
    )
    medidor = _plantar(
        monkeypatch,
        ouvintes={STARLIGHT: [], WHITE: [], COSMIC: ["discord"]},
        captando=lambda seguidos: dict.fromkeys(seguidos, True),
    )

    em_voo = await _rodar(_Daemon(controle), voltas=150)

    seguidos = set().union(*medidor.seguidos) if medidor.seguidos else set()
    assert WHITE not in seguidos, (
        "o White pelo rádio, sem ouvinte, foi medido: o medidor liga a ponte do microfone dele "
        "e o adaptador passa a dividir o rádio com um áudio que ninguém pediu"
    )
    assert {STARLIGHT, COSMIC} <= seguidos, seguidos
    finais = {u: v for u, v in em_voo}
    assert finais[STARLIGHT] == mod.PISCANDO
    assert finais[COSMIC] == mod.PISCANDO
    assert finais[WHITE] == mod.ACESA


class _DeviceFalso:
    def __init__(self) -> None:
        self.escritos: list[bytes] = []

    def write(self, dados: bytes | bytearray) -> int:
        self.escritos.append(bytes(dados))
        return len(dados)


class _LockFalso:
    def __enter__(self) -> None:
        return None

    def __exit__(self, *_: Any) -> None:
        return None


def _handle(*, mudo: bool, transporte: str, nativo: bool) -> Any:
    """Handle REAL (`_PinnedPyDualSense`) com um fio de mentira.

    Quem monta e entrega é o produto.
    """
    from pydualsense.enums import ConnectionType
    from pydualsense.pydualsense import DSAudio, DSLight, DSTrigger

    h = _PinnedPyDualSense.__new__(_PinnedPyDualSense)
    h.audio = DSAudio()
    h.light = DSLight()
    h.triggerL = DSTrigger()
    h.triggerR = DSTrigger()
    h.leftMotor = 0
    h.rightMotor = 0
    h._suppress_leds = False
    h._volumes_audio = [None, None, None, None]
    h._preamp_audio = None
    h._mic_mute_desejado = None
    h._mic_led_desejado = None
    h._raw_trigger_left = None
    h._raw_trigger_right = None
    h._rumble_active = False
    h._rumble_stop_pending = False
    h._output_muted = nativo
    h.conType = ConnectionType.BT if transporte == "bt" else ConnectionType.USB
    h._write_lock = threading.Lock()
    h._bt_seq = 7
    h.device = _DeviceFalso()
    h._audio_status = STATUS_MIC_MUDO if mudo else 0x00
    return h


def _backend(handles: dict[str, Any], *, nativo: bool) -> Any:
    from hefesto_dualsense4unix.core.backend_pydualsense import _DesiredOutput

    ctrl = PyDualSenseController.__new__(PyDualSenseController)
    ctrl._handles = dict(handles)
    ctrl._io_lock = _LockFalso()
    ctrl._primary_key = next(iter(handles))
    ctrl._output_target_key = None
    ctrl._output_mute = nativo
    ctrl._desired_default = _DesiredOutput()
    ctrl._desired_by_uniq = {}
    ctrl._desired_owner_by_uniq = {}
    return ctrl


def _common(relatorio: bytes, transporte: str) -> bytes:
    base = _BASE_DO_COMMON[transporte]
    return relatorio[base : base + rep.COMMON_LEN]


@pytest.mark.parametrize("transporte", ["usb", "bt"])
@pytest.mark.parametrize("nivel", [mod.APAGADA, mod.ACESA, mod.PISCANDO, mod.PISCANDO_LENTO])
def test_no_nativo_a_luz_decidida_chega_ao_fio_no_report_minimo(
    transporte: str, nivel: int
) -> None:
    """No Nativo o laço do controle cala; a luz sai sozinha, e só ela."""
    handle = _handle(mudo=False, transporte=transporte, nativo=True)
    backend = _backend({STARLIGHT: handle}, nativo=True)

    assert backend.set_microphone_led(nivel, uniq=STARLIGHT) is True

    assert len(handle.device.escritos) == 1, (
        "no Modo Nativo a luz do botão de mudo ficava na memória: o laço de escrita está mudo e "
        "nada levava o nível ao controle"
    )
    common = _common(handle.device.escritos[0], transporte)
    assert common[0] == 0, "nada de vibração nem de volume: o jogo segue dono deles"
    assert common[1] == rep.VALID_FLAG1_MIC_MUTE_LED_CONTROL_ENABLE, hex(common[1])
    assert common[rep.COMMON_VALID_FLAG2] == 0, "nada de barra nem de brilho"
    assert common[8] == nivel


def test_no_nativo_pelo_radio_a_luz_sai_com_o_seq_e_o_crc_do_handle() -> None:
    from hefesto_dualsense4unix.core.ds_output_report import bt_crc32

    handle = _handle(mudo=False, transporte="bt", nativo=True)
    backend = _backend({WHITE: handle}, nativo=True)
    backend.set_microphone_led(mod.PISCANDO, uniq=WHITE)

    relatorio = handle.device.escritos[0]
    assert len(relatorio) == rep.BT_REPORT_LEN
    assert relatorio[0] == rep.BT_REPORT_ID
    assert relatorio[1] >> 4 == 7, "o `seq` do fluxo deste handle"
    assert handle._bt_seq == 8
    esperado = bt_crc32(relatorio[: rep.BT_REPORT_LEN - 4])
    assert int.from_bytes(relatorio[rep.BT_REPORT_LEN - 4 :], "little") == esperado


def test_no_nativo_a_luz_de_um_controle_nao_escreve_no_outro() -> None:
    a = _handle(mudo=False, transporte="usb", nativo=True)
    b = _handle(mudo=False, transporte="bt", nativo=True)
    backend = _backend({STARLIGHT: a, WHITE: b}, nativo=True)

    backend.set_microphone_led(mod.PISCANDO, uniq=WHITE)

    assert a.device.escritos == []
    assert len(b.device.escritos) == 1


def test_no_nativo_a_devolucao_repinta_na_lingua_do_kernel_e_solta() -> None:
    """A luz é nossa no Nativo também: soltá-la sem repintar deixaria o pisca preso."""
    handle = _handle(mudo=True, transporte="usb", nativo=True)
    backend = _backend({STARLIGHT: handle}, nativo=True)
    backend.set_microphone_led(mod.APAGADA, uniq=STARLIGHT)
    handle.device.escritos.clear()

    assert backend.set_microphone_led(None, uniq=STARLIGHT) is True

    assert len(handle.device.escritos) == 1
    common = _common(handle.device.escritos[0], "usb")
    assert common[1] == rep.VALID_FLAG1_MIC_MUTE_LED_CONTROL_ENABLE
    assert common[8] == 1, "mudo no firmware: na língua do kernel a luz fica acesa"
    assert handle._mic_led_desejado is None


@pytest.mark.parametrize("transporte", ["usb", "bt"])
def test_fora_do_nativo_a_luz_vai_pelo_laco_do_controle(transporte: str) -> None:
    """Xbox, DualSense e Navegação: tomar a posse não escreve avulso.

    O report da volta leva o nível.
    """
    handle = _handle(mudo=False, transporte=transporte, nativo=False)
    backend = _backend({STARLIGHT: handle}, nativo=False)

    backend.set_microphone_led(mod.PISCANDO, uniq=STARLIGHT)

    assert handle.device.escritos == []
    common = _common(bytes(handle.prepareReport()), transporte)
    assert common[1] & rep.VALID_FLAG1_MIC_MUTE_LED_CONTROL_ENABLE
    assert common[8] == mod.PISCANDO
