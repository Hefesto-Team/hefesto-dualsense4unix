"""Auto-diagnóstico de infra no boot (FEAT-SYSTEM-AUTOREPAIR-BOOT-01).

`system_warnings()` detecta (read-only, sem sudo) udev de hotplug com nome de
unit antigo e WirePlumber sequestrando o microfone do DualSense, devolvendo o
comando de reparo sugerido.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from hefesto_dualsense4unix.core import system_check


def test_udev_outdated_detecta_nome_errado(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    rule = tmp_path / "73.rules"
    rule.write_text(
        'ENV{SYSTEMD_USER_WANTS}="hefesto-gui-hotplug.service"\n', encoding="utf-8"
    )
    monkeypatch.setattr(system_check, "_UDEV_RULES", (str(rule),))
    assert system_check._udev_hotplug_outdated() is True


def test_udev_ok_com_nome_certo(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    rule = tmp_path / "73.rules"
    rule.write_text(
        'ENV{SYSTEMD_USER_WANTS}="hefesto-dualsense4unix-gui-hotplug.service"\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(system_check, "_UDEV_RULES", (str(rule),))
    assert system_check._udev_hotplug_outdated() is False


def test_wireplumber_hijack_detecta_dualsense(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    state = tmp_path / ".local/state/wireplumber"
    state.mkdir(parents=True)
    (state / "default-nodes").write_text(
        "default.configured.audio.source=alsa_input.usb-Sony_DualSense-00\n",
        encoding="utf-8",
    )
    assert system_check._wireplumber_hijacks_mic() is True


def test_system_warnings_vazio_quando_tudo_ok(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(system_check, "_UDEV_RULES", ())  # sem regras
    monkeypatch.setenv("HOME", str(tmp_path))  # sem default-nodes
    assert system_check.system_warnings() == []
