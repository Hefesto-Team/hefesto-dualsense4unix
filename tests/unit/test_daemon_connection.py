"""Testes de `hefesto_dualsense4unix.daemon.connection` — AUDIT-FINDING-LOG-EXC-INFO-01."""
from __future__ import annotations


def test_is_connected_default_false_quando_attr_ausente() -> None:
    """`PyDualSenseController.is_connected()` retorna False quando `connected` ausente."""
    from hefesto_dualsense4unix.core.backend_pydualsense import PyDualSenseController

    ctrl = PyDualSenseController()

    class _FakeDS:
        pass

    ctrl._ds = _FakeDS()  # type: ignore[assignment]
    assert ctrl.is_connected() is False, "deve retornar False quando attr ausente (conservador)"


def test_is_connected_true_quando_attr_true() -> None:
    from hefesto_dualsense4unix.core.backend_pydualsense import PyDualSenseController

    ctrl = PyDualSenseController()

    class _FakeDS:
        connected = True

    ctrl._ds = _FakeDS()  # type: ignore[assignment]
    assert ctrl.is_connected() is True


def test_is_connected_false_quando_attr_false() -> None:
    from hefesto_dualsense4unix.core.backend_pydualsense import PyDualSenseController

    ctrl = PyDualSenseController()

    class _FakeDS:
        connected = False

    ctrl._ds = _FakeDS()  # type: ignore[assignment]
    assert ctrl.is_connected() is False


def test_is_connected_false_sem_ds() -> None:
    from hefesto_dualsense4unix.core.backend_pydualsense import PyDualSenseController

    ctrl = PyDualSenseController()
    assert ctrl.is_connected() is False
