"""Testes do ALVO de output por controle (FEAT-DSX-CONTROLLER-SELECTOR-01).

Cobre:
  - `set_output_target`/`get_output_target_index`: índice → key, ida e volta,
    índice fora de faixa → "todos", e alvo que sumiu (desconexão) → None;
  - `_for_each` mirando SÓ o alvo selecionado vs. broadcast (padrão);
  - NÃO-regressão: sem alvo, o output segue indo para TODOS os controles;
  - `describe_controllers` expõe `index` por entrada.

Reusa o estilo de stub de handle de `test_backend_multi_controller.py`.
"""
from __future__ import annotations

from hefesto_dualsense4unix.core.backend_pydualsense import PyDualSenseController
from hefesto_dualsense4unix.core.evdev_reader import EvdevReader


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
    """Stub mínimo de um handle pydualsense (só o necessário p/ set_led)."""

    def __init__(self, *, connected: bool = True, transport_name: str = "USB") -> None:
        self.connected = connected
        self.light = _FakeLight()
        self.conType = type("CT", (), {"name": transport_name})()


def _with_two_handles() -> tuple[PyDualSenseController, _FakeHandle, _FakeHandle]:
    inst = PyDualSenseController(evdev_reader=_null_evdev())
    h1, h2 = _FakeHandle(), _FakeHandle()
    inst._handles = {"a": h1, "b": h2}  # type: ignore[dict-item]
    inst._primary_key = "a"
    return inst, h1, h2


class TestSetGetTarget:
    def test_default_e_todos(self) -> None:
        inst, _h1, _h2 = _with_two_handles()
        assert inst.get_output_target_index() is None

    def test_indice_mapeia_para_key_e_volta(self) -> None:
        inst, _h1, _h2 = _with_two_handles()
        assert inst.set_output_target(1) == 1
        # Guardou a KEY, não o índice.
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
        inst.set_output_target(1)  # alvo = "b"
        # "b" desconecta (hotplug-out simplificado).
        del inst._handles["b"]
        assert inst.get_output_target_index() is None

    def test_indice_acompanha_reordenacao_por_key(self) -> None:
        """O alvo é a KEY: se o primário cai, o índice da key sobrevivente muda."""
        inst, _h1, _h2 = _with_two_handles()
        inst.set_output_target(1)  # alvo = "b" (índice 1)
        del inst._handles["a"]  # "b" agora é o único → índice 0
        assert inst.get_output_target_index() == 0


class TestForEachRespeitaAlvo:
    def test_broadcast_quando_sem_alvo(self) -> None:
        inst, h1, h2 = _with_two_handles()
        inst.set_led((1, 2, 3))
        assert h1.light.colors == [(1, 2, 3)]
        assert h2.light.colors == [(1, 2, 3)]

    def test_so_o_alvo_recebe(self) -> None:
        inst, h1, h2 = _with_two_handles()
        inst.set_output_target(1)  # alvo = h2
        inst.set_led((9, 9, 9))
        assert h1.light.colors == []
        assert h2.light.colors == [(9, 9, 9)]

    def test_alvo_sumido_cai_em_broadcast(self) -> None:
        inst, h1, _h2 = _with_two_handles()
        inst.set_output_target(1)  # alvo = "b"
        del inst._handles["b"]  # alvo sumiu
        inst.set_led((4, 5, 6))  # deve ir ao remanescente (broadcast)
        assert h1.light.colors == [(4, 5, 6)]


class TestDescribeIndex:
    def test_describe_inclui_index(self) -> None:
        inst, _h1, _h2 = _with_two_handles()
        desc = inst.describe_controllers()
        assert [c["index"] for c in desc] == [0, 1]
