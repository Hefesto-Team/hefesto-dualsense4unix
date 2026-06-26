"""Checks de infra read-only para auto-diagnóstico no boot.

FEAT-SYSTEM-AUTOREPAIR-BOOT-01: espelha em Python parte do `scripts/doctor.sh`,
focado no que vale AVISAR ao usuário no boot do daemon (udev de hotplug
desatualizado, WirePlumber sequestrando o microfone do DualSense). NUNCA levanta
e NUNCA roda sudo/reparo — apenas detecta e devolve mensagens com o comando
sugerido. O reparo de fato fica a cargo do usuário (`doctor --fix`).
"""
from __future__ import annotations

import os
from pathlib import Path

# Nome de unit ERRADO que versões antigas das regras 73/74 instalaram
# (BUG-UDEV-HOTPLUG-UNIT-NAME-MISMATCH-01). A unit real tem o prefixo completo.
_WRONG_HOTPLUG_PATTERN = 'SYSTEMD_USER_WANTS}="hefesto-gui-hotplug.service"'
_UDEV_RULES = (
    "/etc/udev/rules.d/73-ps5-controller-hotplug.rules",
    "/etc/udev/rules.d/74-ps5-controller-hotplug-bt.rules",
)


def _udev_hotplug_outdated() -> bool:
    """True se alguma regra 73/74 instalada cita a unit de hotplug ERRADA."""
    for rule in _UDEV_RULES:
        try:
            text = Path(rule).read_text(encoding="utf-8")
        except OSError:
            continue
        if _WRONG_HOTPLUG_PATTERN in text:
            return True
    return False


def _wireplumber_hijacks_mic() -> bool:
    """True se o WirePlumber fixou o DualSense como fonte de áudio padrão."""
    state = Path.home() / ".local/state/wireplumber/default-nodes"
    try:
        for line in state.read_text(encoding="utf-8").splitlines():
            low = line.lower()
            if low.startswith("default.configured.audio.source=") and "dualsense" in low:
                return True
    except OSError:
        pass
    return False


def _dualsense_mic_intended() -> bool:
    """True se a usuária declarou que QUER o mic do DualSense como entrada de áudio
    (opt-in via env HEFESTO_DUALSENSE4UNIX_DUALSENSE_MIC_INTENDED=1). Nesse caso o
    WirePlumber fixar o DualSense como fonte padrão é o COMPORTAMENTO DESEJADO — não
    um problema — então NÃO avisamos nem sugerimos `doctor --fix` (que o desligaria)."""
    return os.environ.get(
        "HEFESTO_DUALSENSE4UNIX_DUALSENSE_MIC_INTENDED", ""
    ).strip().lower() in ("1", "true", "yes")


def system_warnings() -> list[str]:
    """Avisos de infra para o boot. Read-only; nunca levanta, nunca usa sudo."""
    warnings: list[str] = []
    try:
        if _udev_hotplug_outdated():
            warnings.append(
                "regras udev de hotplug desatualizadas (nome de unit antigo) — "
                "rode: sudo bash scripts/install_udev.sh"
            )
        if not _dualsense_mic_intended() and _wireplumber_hijacks_mic():
            warnings.append(
                "WirePlumber fixou o DualSense como microfone padrão — "
                "rode: scripts/doctor.sh --fix"
            )
    except Exception:
        return warnings
    return warnings


__all__ = ["system_warnings"]
