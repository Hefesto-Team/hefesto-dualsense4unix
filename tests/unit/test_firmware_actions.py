"""Testes unitários de FirmwareActionsMixin (AUDIT-FINDING-COVERAGE-ACTIONS-ZERO-01).

Cobrem:
  - install_firmware_tab (binário disponível / ausente).
  - on_firmware_check com info OK / erro variantes.
  - on_firmware_apply sem blob selecionado / com blob.
  - callbacks de sucesso/falha/progresso na main thread.
  - _friendly_error tradutor de mensagens.

Padrão `_FakeMixin` + stubs de `gi.repository.{Gtk,GLib}` (armadilha A-12).
"""
from __future__ import annotations

import sys
import types
from pathlib import Path
from typing import Any

import pytest


def _install_gi_stubs() -> None:
    gi_mod = sys.modules.get("gi") or types.ModuleType("gi")
    gi_mod.require_version = lambda _n, _v: None  # type: ignore[attr-defined]
    repo_mod = sys.modules.get("gi.repository") or types.ModuleType(
        "gi.repository"
    )
    gtk_mod = sys.modules.get("gi.repository.Gtk") or types.ModuleType(
        "gi.repository.Gtk"
    )
    glib_mod = sys.modules.get("gi.repository.GLib") or types.ModuleType(
        "gi.repository.GLib"
    )

    class _ResponseType:
        OK = -5
        CANCEL = -6

    class _MessageType:
        WARNING = 1

    class _ButtonsType:
        OK_CANCEL = 4

    class _FileChooserAction:
        OPEN = 0

    # Classes mínimas (idempotente).
    for cls_name in (
        "Builder", "Window", "Button", "ToggleButton", "ComboBoxText",
        "Switch", "TextView", "TextBuffer", "Scale", "Label", "Box",
        "FileFilter", "FileChooserDialog", "MessageDialog",
    ):
        if not hasattr(gtk_mod, cls_name):
            setattr(gtk_mod, cls_name, type(cls_name, (), {}))
    if not hasattr(gtk_mod, "ResponseType"):
        gtk_mod.ResponseType = _ResponseType  # type: ignore[attr-defined]
    if not hasattr(gtk_mod, "MessageType"):
        gtk_mod.MessageType = _MessageType  # type: ignore[attr-defined]
    if not hasattr(gtk_mod, "ButtonsType"):
        gtk_mod.ButtonsType = _ButtonsType  # type: ignore[attr-defined]
    if not hasattr(gtk_mod, "FileChooserAction"):
        gtk_mod.FileChooserAction = _FileChooserAction  # type: ignore[attr-defined]

    # idle_add síncrono: roda callback imediatamente.
    def _idle_add(fn: Any, *a: Any, **kw: Any) -> int:
        fn(*a, **kw)
        return 0

    glib_mod.idle_add = _idle_add  # type: ignore[attr-defined]
    glib_mod.timeout_add = lambda *_a, **_kw: 0  # type: ignore[attr-defined]

    repo_mod.Gtk = gtk_mod  # type: ignore[attr-defined]
    repo_mod.GLib = glib_mod  # type: ignore[attr-defined]

    sys.modules["gi"] = gi_mod
    sys.modules["gi.repository"] = repo_mod
    sys.modules["gi.repository.Gtk"] = gtk_mod
    sys.modules["gi.repository.GLib"] = glib_mod


_install_gi_stubs()

from hefesto_dualsense4unix.app.actions import firmware_actions  # noqa: E402
from hefesto_dualsense4unix.integrations.firmware_updater import (  # noqa: E402
    ControllerNotConnectedError,
    DualsensectlNotAvailableError,
    FirmwareApplyResult,
    FirmwareError,
    FirmwareInfo,
)

# --- Fakes ------------------------------------------------------------


class _FakeLabel:
    def __init__(self) -> None:
        self.text = ""

    def set_text(self, t: str) -> None:
        self.text = t

    def set_label(self, t: str) -> None:
        self.text = t


class _FakeButton:
    def __init__(self) -> None:
        self.sensitive = True

    def set_sensitive(self, v: bool) -> None:
        self.sensitive = bool(v)


class _FakeProgressBar:
    def __init__(self) -> None:
        self.fraction = 0.0
        self.text = ""
        self.show_text = False

    def set_fraction(self, f: float) -> None:
        self.fraction = float(f)

    def set_text(self, t: str) -> None:
        self.text = t

    def set_show_text(self, v: bool) -> None:
        self.show_text = bool(v)


class _FakeExecutor:
    """Substitui ThreadPoolExecutor: executa sincronamente."""

    def __init__(self) -> None:
        self.submitted: list[Any] = []

    def submit(self, fn: Any, *a: Any, **kw: Any) -> None:
        self.submitted.append(fn)
        fn(*a, **kw)


def _mk_widgets() -> dict[str, Any]:
    keys_label = [
        "firmware_current_version_label",
        "firmware_hardware_label",
        "firmware_build_date_label",
        "firmware_file_entry",
        "firmware_status_label",
        "firmware_risk_banner_label",
    ]
    keys_button = [
        "firmware_check_btn",
        "firmware_browse_btn",
        "firmware_apply_btn",
    ]
    widgets: dict[str, Any] = {}
    for k in keys_label:
        widgets[k] = _FakeLabel()
    for k in keys_button:
        widgets[k] = _FakeButton()
    widgets["firmware_progress_bar"] = _FakeProgressBar()
    widgets["main_window"] = None  # Diálogos não são testados aqui
    return widgets


class _FakeFirmwareMixin:
    def __init__(self) -> None:
        self._widgets = _mk_widgets()

    def _get(self, key: str) -> Any:
        return self._widgets.get(key)


def _build_mixin(
    monkeypatch: pytest.MonkeyPatch,
    binary_available: bool = True,
) -> _FakeFirmwareMixin:
    # Stub do FirmwareUpdater para não rodar subprocess real.
    fake_executor = _FakeExecutor()
    monkeypatch.setattr(
        firmware_actions, "_get_executor", lambda: fake_executor
    )

    # Patch FirmwareUpdater.is_available para variar disponibilidade.
    monkeypatch.setattr(
        firmware_actions.FirmwareUpdater,
        "is_available",
        lambda self: binary_available,
    )

    inst = _FakeFirmwareMixin()
    inst._fake_executor = fake_executor  # type: ignore[attr-defined]

    for name in (
        "install_firmware_tab",
        "on_firmware_check",
        "on_firmware_apply",
        "_on_firmware_info_ok",
        "_on_firmware_info_fail",
        "_on_firmware_progress",
        "_on_firmware_apply_ok",
        "_on_firmware_apply_fail",
        "_set_firmware_label",
        "_set_progress",
        "_set_button_enabled",
    ):
        setattr(
            inst,
            name,
            firmware_actions.FirmwareActionsMixin.__dict__[name].__get__(
                inst, type(inst)
            ),
        )
    return inst


# --- Testes -----------------------------------------------------------


def test_install_firmware_tab_binario_disponivel_habilita_botoes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Aba Firmware redesenhada (2026-04-27): atualização Linux removida por
    risco de brick. Apenas 'Verificar versão' (firmware_check_btn) fica
    enabled quando binário presente; browse/apply SEMPRE desabilitados.
    """
    mixin = _build_mixin(monkeypatch, binary_available=True)
    mixin.install_firmware_tab()

    assert mixin._widgets["firmware_check_btn"].sensitive is True
    assert mixin._widgets["firmware_browse_btn"].sensitive is False
    assert mixin._widgets["firmware_apply_btn"].sensitive is False
    # Status label mostra _OFFICIAL_GUIDE (link Sony oficial) por default.
    assert "playstation" in mixin._widgets["firmware_status_label"].text.lower()
    assert mixin._firmware_selected_blob is None
    assert mixin._firmware_in_progress is False


def test_install_firmware_tab_binario_ausente_desabilita_e_mostra_help(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mixin = _build_mixin(monkeypatch, binary_available=False)
    mixin.install_firmware_tab()

    assert mixin._widgets["firmware_check_btn"].sensitive is False
    assert mixin._widgets["firmware_browse_btn"].sensitive is False
    assert "dualsensectl" in mixin._widgets["firmware_status_label"].text


def test_on_firmware_check_sucesso_popula_labels(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mixin = _build_mixin(monkeypatch, binary_available=True)
    mixin.install_firmware_tab()

    info = FirmwareInfo(
        hardware="DualSense",
        build_date="2024-06-10",
        firmware_version="2.24",
        update_version="0422",
        fw_type="type_a",
        fw_version="2.24",
        sw_series="ABCD",
        raw="...",
    )
    monkeypatch.setattr(
        firmware_actions.FirmwareUpdater,
        "get_info",
        lambda self: info,
    )

    mixin.on_firmware_check(None)

    assert "0422" in mixin._widgets["firmware_current_version_label"].text
    assert "DualSense" in mixin._widgets["firmware_hardware_label"].text
    assert mixin._widgets["firmware_status_label"].text == "Controle detectado."


def test_on_firmware_check_sem_controle_mostra_erro_amigavel(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mixin = _build_mixin(monkeypatch, binary_available=True)
    mixin.install_firmware_tab()

    def fake_get_info(_self: Any) -> FirmwareInfo:
        raise ControllerNotConnectedError("nenhum controle USB")

    monkeypatch.setattr(
        firmware_actions.FirmwareUpdater,
        "get_info",
        fake_get_info,
    )

    mixin.on_firmware_check(None)

    assert "DualSense" in mixin._widgets["firmware_status_label"].text
    assert "USB-C" in mixin._widgets["firmware_status_label"].text


def test_on_firmware_check_binario_ausente_usa_install_help(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mixin = _build_mixin(monkeypatch, binary_available=True)
    mixin.install_firmware_tab()

    def fake_get_info(_self: Any) -> FirmwareInfo:
        raise DualsensectlNotAvailableError("binário ausente")

    monkeypatch.setattr(
        firmware_actions.FirmwareUpdater,
        "get_info",
        fake_get_info,
    )

    mixin.on_firmware_check(None)

    assert "dualsensectl" in mixin._widgets["firmware_status_label"].text


def test_on_firmware_check_firmware_error_generico(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mixin = _build_mixin(monkeypatch, binary_available=True)
    mixin.install_firmware_tab()

    def fake_get_info(_self: Any) -> FirmwareInfo:
        raise FirmwareError("algum outro erro")

    monkeypatch.setattr(
        firmware_actions.FirmwareUpdater,
        "get_info",
        fake_get_info,
    )

    mixin.on_firmware_check(None)

    assert (
        mixin._widgets["firmware_status_label"].text
        == "Falha ao consultar firmware."
    )


def test_on_firmware_apply_sem_blob_selecionado_informa_usuario(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mixin = _build_mixin(monkeypatch, binary_available=True)
    mixin.install_firmware_tab()

    mixin.on_firmware_apply(None)

    assert "Selecione primeiro" in mixin._widgets["firmware_status_label"].text


def test_on_firmware_apply_em_progresso_eh_noop(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mixin = _build_mixin(monkeypatch, binary_available=True)
    mixin.install_firmware_tab()
    mixin._firmware_in_progress = True
    mixin._widgets["firmware_status_label"].text = "Aplicando..."

    mixin.on_firmware_apply(None)

    # Label não mudou — in_progress cortou cedo.
    assert mixin._widgets["firmware_status_label"].text == "Aplicando..."


def test_on_firmware_info_ok_atualiza_labels() -> None:
    from hefesto_dualsense4unix.app.actions.firmware_actions import FirmwareActionsMixin

    class _Bare:
        def __init__(self) -> None:
            self._widgets = _mk_widgets()

        def _get(self, k: str) -> Any:
            return self._widgets.get(k)

    inst = _Bare()
    for n in ("_on_firmware_info_ok", "_set_firmware_label"):
        setattr(
            inst,
            n,
            FirmwareActionsMixin.__dict__[n].__get__(inst, type(inst)),
        )
    info = FirmwareInfo(
        hardware="DS Edge",
        build_date="2024-01-01",
        firmware_version="?",
        update_version="0500",
        fw_type="",
        fw_version="",
        sw_series="",
        raw="",
    )
    result = inst._on_firmware_info_ok(info)

    assert result is False  # GLib.idle_add contrato: retorna False para não repetir
    assert "DS Edge" in inst._widgets["firmware_hardware_label"].text
    assert "0500" in inst._widgets["firmware_current_version_label"].text


def test_on_firmware_apply_ok_reseta_estado(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mixin = _build_mixin(monkeypatch, binary_available=True)
    mixin.install_firmware_tab()
    # Simula estado durante aplicação.
    mixin._firmware_in_progress = True
    mixin._firmware_selected_blob = Path("/tmp/blob.bin")

    result = FirmwareApplyResult(
        previous_update_version="0422",
        new_update_version="0500",
    )
    ret = mixin._on_firmware_apply_ok(result)

    assert ret is False
    assert mixin._firmware_in_progress is False
    assert mixin._firmware_selected_blob is None
    assert "0422" in mixin._widgets["firmware_status_label"].text
    assert "0500" in mixin._widgets["firmware_status_label"].text
    assert mixin._widgets["firmware_apply_btn"].sensitive is False


def test_on_firmware_apply_fail_restaura_botoes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mixin = _build_mixin(monkeypatch, binary_available=True)
    mixin.install_firmware_tab()
    mixin._firmware_in_progress = True
    mixin._firmware_selected_blob = Path("/tmp/blob.bin")

    ret = mixin._on_firmware_apply_fail("timeout do controle")

    assert ret is False
    assert mixin._firmware_in_progress is False
    # blob ainda selecionado -> apply_btn habilitado.
    assert mixin._widgets["firmware_apply_btn"].sensitive is True
    assert "Falha" in mixin._widgets["firmware_status_label"].text


def test_on_firmware_progress_atualiza_barra(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mixin = _build_mixin(monkeypatch, binary_available=True)
    mixin.install_firmware_tab()

    mixin._on_firmware_progress(42)

    bar = mixin._widgets["firmware_progress_bar"]
    assert bar.fraction == pytest.approx(0.42)
    assert "42%" in bar.text


def test_friendly_error_traducoes() -> None:
    """Unit test puro do helper (não depende de mixin)."""
    friendly = firmware_actions._friendly_error

    assert "modelo correto" in friendly("Retornou código 3")
    assert "Tamanho" in friendly("código 2 recebido")
    assert "Tempo" in friendly("timeout excedido")
    assert "USB-C" in friendly("No device found")
    # Mensagem desconhecida é devolvida tal como veio.
    assert friendly("erro esotérico") == "erro esotérico"
