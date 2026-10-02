"""Testes do ALVO de output por controle (FEAT-DSX-CONTROLLER-SELECTOR-01).

Cobre:
  - `set_output_target`/`get_output_target_index`: índice → key, ida e volta,
    índice fora de faixa → "todos", e alvo que sumiu (desconexão) → None;
  - `_for_each` mirando SÓ o alvo selecionado vs. broadcast (padrão);
  - NÃO-regressão: sem alvo, o output segue indo para TODOS os controles;
  - `describe_controllers` expõe `index` por entrada;
  - PERFIL-01 (4P-01): o REGISTRO do estado desejado segue o escopo do alvo —
    escrita mirada vai para o override por-uniq (não contamina o default),
    broadcast "Todos" limpa o campo escrito dos overrides, alvo sem MAC não
    entra no mapa, e `set_rumble_for` mira sem tocar no seletor global.

Reusa o estilo de stub de handle de `test_backend_multi_controller.py`.
"""
from __future__ import annotations

from types import SimpleNamespace

from hefesto_dualsense4unix.core.backend_pydualsense import PyDualSenseController
from hefesto_dualsense4unix.core.evdev_reader import EvdevReader

KEY_1 = "AA:BB:CC:00:00:01"
KEY_2 = "AA:BB:CC:00:00:02"
UNIQ_1 = "aabbcc000001"
UNIQ_2 = "aabbcc000002"


def _null_evdev() -> EvdevReader:
    """EvdevReader sem device — força is_available=False (não interfere)."""
    reader = EvdevReader(device_path=None)
    reader._device_path = None
    return reader


class _FakeLight:
    def __init__(self) -> None:
        self.colors: list[tuple[int, int, int]] = []

    def setColorI(self, r: int, g: int, b: int) -> None:  # noqa: N802 — API pydualsense
        self.colors.append((r, g, b))


class _FakeHandle:
    """Stub mínimo de um handle pydualsense (set_led/set_mic_led/set_rumble)."""

    def __init__(self, *, connected: bool = True, transport_name: str = "USB") -> None:
        self.connected = connected
        self.light = _FakeLight()
        self.conType = type("CT", (), {"name": transport_name})()
        self.mic: list[bool] = []
        self.audio = SimpleNamespace(setMicrophoneLED=self.mic.append)
        self.motors: list[tuple[str, int]] = []

    def setLeftMotor(self, intensity: int) -> None:  # noqa: N802 — API pydualsense
        self.motors.append(("left", intensity))

    def setRightMotor(self, intensity: int) -> None:  # noqa: N802 — API pydualsense
        self.motors.append(("right", intensity))


def _with_two_handles() -> tuple[PyDualSenseController, _FakeHandle, _FakeHandle]:
    inst = PyDualSenseController(evdev_reader=_null_evdev())
    h1, h2 = _FakeHandle(), _FakeHandle()
    inst._handles = {"a": h1, "b": h2}  # type: ignore[dict-item]
    inst._primary_key = "a"
    return inst, h1, h2


def _with_two_macs() -> tuple[PyDualSenseController, _FakeHandle, _FakeHandle]:
    """Dois controles com keys MAC reais (uniq resolve) — cenários PERFIL-01."""
    inst = PyDualSenseController(evdev_reader=_null_evdev())
    h1, h2 = _FakeHandle(), _FakeHandle()
    inst._handles = {KEY_1: h1, KEY_2: h2}  # type: ignore[dict-item]
    inst._primary_key = KEY_1
    return inst, h1, h2


class TestSetGetTarget:
    def test_default_e_todos(self) -> None:
        inst, _h1, _h2 = _with_two_handles()
        assert inst.get_output_target_index() is None

    def test_indice_mapeia_para_key_e_volta(self) -> None:
        inst, _h1, _h2 = _with_two_handles()
        assert inst.set_output_target(1) == 1
        assert inst._output_target_key == "b"
        assert inst.get_output_target_index() == 1

    def test_none_volta_para_todos(self) -> None:
        inst, _h1, _h2 = _with_two_handles()
        inst.set_output_target(1)
        assert inst.set_output_target(None) is None
        assert inst._output_target_key is None
        assert inst.get_output_target_index() is None

    def test_indice_fora_de_faixa_vira_todos(self) -> None:
        inst, _h1, _h2 = _with_two_handles()
        assert inst.set_output_target(9) is None
        assert inst._output_target_key is None
        assert inst.get_output_target_index() is None

    def test_alvo_que_some_volta_a_none(self) -> None:
        """Se o controle alvo desconecta, o índice efetivo cai para None."""
        inst, _h1, _h2 = _with_two_handles()
        inst.set_output_target(1)
        del inst._handles["b"]
        assert inst.get_output_target_index() is None

    def test_indice_acompanha_reordenacao_por_key(self) -> None:
        """O alvo é a KEY: se o primário cai, o índice da key sobrevivente muda."""
        inst, _h1, _h2 = _with_two_handles()
        inst.set_output_target(1)
        del inst._handles["a"]
        assert inst.get_output_target_index() == 0


class TestForEachRespeitaAlvo:
    def test_broadcast_quando_sem_alvo(self) -> None:
        inst, h1, h2 = _with_two_handles()
        inst.set_led((1, 2, 3))
        assert h1.light.colors == [(1, 2, 3)]
        assert h2.light.colors == [(1, 2, 3)]

    def test_so_o_alvo_recebe(self) -> None:
        inst, h1, h2 = _with_two_handles()
        inst.set_output_target(1)
        inst.set_led((9, 9, 9))
        assert h1.light.colors == []
        assert h2.light.colors == [(9, 9, 9)]

    def test_alvo_sumido_nao_escreve_em_ninguem(self) -> None:
        """Alvo fora da mesa é NO-OP — o broadcast daqui caducou em 23/08/2026."""
        inst, h1, _h2 = _with_two_handles()
        inst.set_output_target(1)
        del inst._handles["b"]
        inst.set_led((4, 5, 6))
        assert h1.light.colors == [], (
            "o gesto mirado no controle que saiu chegou ao remanescente — em "
            "co-op, na mão de outra pessoa"
        )


class TestDescribeIndex:
    def test_describe_inclui_index(self) -> None:
        inst, _h1, _h2 = _with_two_handles()
        desc = inst.describe_controllers()
        assert [c["index"] for c in desc] == [0, 1]


class TestRegistroDoDesejadoPorAlvo:
    """PERFIL-01 (4P-01): o registro do desejado segue o ESCOPO do alvo."""

    def test_escrita_mirada_registra_no_override_nao_no_default(self) -> None:
        inst, _h1, h2 = _with_two_macs()
        inst.set_led((10, 10, 10))
        inst.set_output_target(1)
        inst.set_led((0, 255, 0))

        assert h2.light.colors[-1] == (0, 255, 0)
        assert inst._desired_default.led == (10, 10, 10)
        assert inst._desired_by_uniq[UNIQ_2].led == (0, 255, 0)
        assert UNIQ_1 not in inst._desired_by_uniq

    def test_broadcast_todos_limpa_o_campo_dos_overrides(self) -> None:
        """"Mudei todos para azul, repluguei e um voltou verde" — proibido."""
        inst, h1, h2 = _with_two_macs()
        inst.set_output_target(1)
        inst.set_led((0, 255, 0))
        inst.set_output_target(None)
        inst.set_led((0, 0, 255))

        assert h1.light.colors[-1] == (0, 0, 255)
        assert h2.light.colors[-1] == (0, 0, 255)
        assert inst._desired_default.led == (0, 0, 255)
        assert UNIQ_2 not in inst._desired_by_uniq

    def test_broadcast_limpa_so_o_campo_escrito(self) -> None:
        """Merge POR CAMPO: o broadcast de LED não apaga o override de mic."""
        inst, _h1, _h2 = _with_two_macs()
        inst.set_output_target(1)
        inst.set_led((0, 255, 0))
        inst.set_mic_led(True)
        inst.set_output_target(None)
        inst.set_led((0, 0, 255))

        override = inst._desired_by_uniq[UNIQ_2]
        assert override.led is None
        assert override.mic_led is True

    def test_alvo_sem_mac_nao_entra_no_mapa_mas_escreve_no_hardware(self) -> None:
        """Key de fallback por path não tem identidade estável (regra do sprint)."""
        inst, h1, h2 = _with_two_handles()
        inst.set_output_target(1)
        inst.set_led((1, 2, 3))

        assert h2.light.colors == [(1, 2, 3)]
        assert h1.light.colors == []
        assert inst._desired_by_uniq == {}
        assert inst._desired_default.led is None

    def test_registro_offline_vale_para_o_hotplug(self) -> None:
        """Perfil ativado sem controle nenhum ainda registra o default."""
        inst = PyDualSenseController(evdev_reader=_null_evdev())
        inst.set_led((7, 8, 9))
        assert inst._desired_default.led == (7, 8, 9)


class TestSetRumbleFor:
    """PERFIL-01: rumble por-uniq SEM flip do seletor global (anti-corrida)."""

    def test_mira_o_controle_certo_sem_tocar_o_seletor(self) -> None:
        inst, h1, h2 = _with_two_macs()
        inst.set_output_target(0)

        assert inst.set_rumble_for(UNIQ_2, 10, 20) is True
        assert h2.motors == [("left", 20), ("right", 10)]
        assert h1.motors == []
        assert inst.get_output_target_index() == 0

    def test_mac_desconhecido_devolve_false(self) -> None:
        inst, h1, h2 = _with_two_macs()
        assert inst.set_rumble_for("aabbcc0000ff", 10, 20) is False
        assert h1.motors == []
        assert h2.motors == []

    def test_rumble_nao_entra_no_desejado(self) -> None:
        inst, _h1, _h2 = _with_two_macs()
        inst.set_rumble_for(UNIQ_2, 10, 20)
        assert inst._desired_by_uniq == {}
