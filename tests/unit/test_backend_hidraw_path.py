"""`hidraw_path` — de onde o vpad uhid copia o blueprint (SPRINT-UHID-VPAD-01).

O backend já abre cada controle "pinado" a um path; expor isso é o que permite ao
vpad uhid de CADA jogador ler o report descriptor e os features do probe do SEU
controle físico. Errar o alvo aqui não dá erro visível: o vpad sobe com o
blueprint do controle errado, ou simplesmente cai no uinput e a máscara DualSense
volta a não vibrar.

Estilo de stub de handle reusado de `test_backend_output_target.py`.
"""
from __future__ import annotations

from hefesto_dualsense4unix.core.backend_pydualsense import PyDualSenseController
from hefesto_dualsense4unix.core.evdev_reader import EvdevReader

MAC_A = "aabbcc001100"
MAC_B = "aabbcc001122"


def _null_evdev() -> EvdevReader:
    reader = EvdevReader(device_path=None)
    reader._device_path = None
    return reader


class _FakeHandle:
    """Handle "pinado": só o atributo que o `hidraw_path` lê."""

    def __init__(self, path: bytes | str | None) -> None:
        if path is not None:
            self._pinned_path = path


def _with_handles(**by_key: _FakeHandle) -> PyDualSenseController:
    inst = PyDualSenseController(evdev_reader=_null_evdev())
    inst._handles = dict(by_key)  # type: ignore[arg-type]
    inst._primary_key = next(iter(by_key), None)
    return inst


class TestHidrawPath:
    def test_sem_uniq_devolve_o_do_primario(self) -> None:
        inst = _with_handles(**{
            MAC_A: _FakeHandle(b"/dev/hidraw4"),
            MAC_B: _FakeHandle(b"/dev/hidraw7"),
        })

        assert inst.hidraw_path() == "/dev/hidraw4"

    def test_uniq_mira_o_controle_daquele_jogador(self) -> None:
        inst = _with_handles(**{
            MAC_A: _FakeHandle(b"/dev/hidraw4"),
            MAC_B: _FakeHandle(b"/dev/hidraw7"),
        })

        assert inst.hidraw_path(MAC_B) == "/dev/hidraw7"

    def test_uniq_desconhecido_devolve_none(self) -> None:
        inst = _with_handles(**{MAC_A: _FakeHandle(b"/dev/hidraw4")})

        assert inst.hidraw_path(MAC_B) is None

    def test_offline_devolve_none(self) -> None:
        inst = _with_handles()

        assert inst.hidraw_path() is None

    def test_path_de_libusb_nao_e_hidraw(self) -> None:
        """hidapi sobre libusb dá paths tipo "0001:0002:00" — ninguém abre isso.

        Deixar passar daria uma falha obscura lá no `capture_dualsense_blueprint`.
        """
        inst = _with_handles(**{MAC_A: _FakeHandle(b"0001:0002:00")})

        assert inst.hidraw_path() is None

    def test_handle_sem_path_pinado_devolve_none(self) -> None:
        """Handle de teste/legado (`_ds = fake`) não tem `_pinned_path`."""
        inst = _with_handles(**{MAC_A: _FakeHandle(None)})

        assert inst.hidraw_path() is None
