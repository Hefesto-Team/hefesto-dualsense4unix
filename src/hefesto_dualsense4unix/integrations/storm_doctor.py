"""Diagnóstico do storm -71 do DualSense (FEAT-DSX-UNIFY-01).

Checks READ-ONLY do estado anti-storm — a parte "segura" do dsx.sh trazida para
dentro do hefesto. NÃO muta nada; NÃO precisa de root. Cada função recebe os
paths por parâmetro (default = sistema real) para ser testável com fixtures.

Fronteira Aurora: o quirk `054c:0ce6:gn` do cmdline e as regras 99-usb são do
ritual-Aurora — aqui só REPORTAMOS o estado, não mexemos.
"""
from __future__ import annotations

import re
from pathlib import Path

# Tags no padrão do doctor.
OK = "[ OK ]"
WARN = "[WARN]"
INFO = "[INFO]"

_QUIRK_RE = re.compile(r"054c:0ce6")
_STEAM_INPUT_RE = re.compile(
    r'"(SteamController_PSSupport|UseSteamControllerConfig)"\s+"[12]"'
)


def check_quirk(quirks_text: str | None = None) -> tuple[str, str]:
    """O quirk anti-storm (DELAY_CTRL_MSG) está ativo? (preserva o áudio do controle)."""
    if quirks_text is None:
        try:
            quirks_text = Path(
                "/sys/module/usbcore/parameters/quirks"
            ).read_text(encoding="utf-8", errors="ignore")
        except Exception:
            quirks_text = ""
    if _QUIRK_RE.search(quirks_text or ""):
        return OK, "quirk anti-storm ativo (054c:0ce6 — áudio USB espaçado)"
    return WARN, "quirk anti-storm AUSENTE do usbcore (storm pode reincidir sob carga)"


def find_localconfig_vdfs(home: Path) -> list[Path]:
    """localconfig.vdf per-user em layouts comuns de Steam no Linux (dedup)."""
    globs = [
        ".steam/steam/userdata/*/config/localconfig.vdf",
        ".local/share/Steam/userdata/*/config/localconfig.vdf",
        ".var/app/com.valvesoftware.Steam/.steam/steam/userdata/*/config/localconfig.vdf",
        "snap/steam/common/.steam/steam/userdata/*/config/localconfig.vdf",
    ]
    seen: set[Path] = set()
    out: list[Path] = []
    for pattern in globs:
        for path in home.glob(pattern):
            real = path.resolve()
            if real.is_file() and real not in seen:
                seen.add(real)
                out.append(real)
    return out


def check_steam_input(home: Path | None = None) -> tuple[str, str]:
    """Steam Input (PSSupport/UseSteamControllerConfig) ON para o DualSense?

    ON é RUIM neste contexto (incompatível no Linux p/ Grim; e o storm/duplo-input).
    """
    home = home or Path.home()
    vdfs = find_localconfig_vdfs(home)
    if not vdfs:
        return INFO, "Steam Input: nenhum localconfig.vdf encontrado (Steam instalada?)"
    on = [v for v in vdfs if _STEAM_INPUT_RE.search(_safe_read(v))]
    if on:
        return (
            WARN,
            f"Steam Input LIGADO em {len(on)} perfil(is) — 'doctor --fix-safe' desliga",
        )
    return OK, "Steam Input desligado para o DualSense"


def check_wireplumber(dropin_dir: Path | None = None) -> tuple[str, str]:
    """Drop-in do WirePlumber (DualSense não-default / só-HID) instalado?"""
    dropin_dir = dropin_dir or (
        Path.home() / ".config" / "wireplumber" / "wireplumber.conf.d"
    )
    names = [
        "51-hefesto-dualsense-no-default-source.conf",
        "52-hefesto-dualsense-disable-source.conf",
    ]
    present = [n for n in names if (dropin_dir / n).is_file()]
    if present:
        return OK, f"WirePlumber configurado ({', '.join(present)})"
    return INFO, "WirePlumber sem drop-in do hefesto ('doctor --fix-safe' instala)"


def check_authorized_rule(rules_dir: Path | None = None) -> tuple[str, str]:
    """Regra udev authorized=0 (rota áudio-off agressiva) instalada?

    Opt-in: presença = mic/fone do controle desligados. Só INFO.
    """
    rules_dir = rules_dir or Path("/etc/udev/rules.d")
    rule = rules_dir / "75-ps5-controller-disable-usb-audio.rules"
    if rule.is_file():
        return INFO, "regra áudio-off (authorized=0) ATIVA — mic/fone do controle off"
    return INFO, "regra áudio-off inativa (áudio do controle preservado)"


def storm_report(
    home: Path | None = None,
    *,
    quirks_text: str | None = None,
    dropin_dir: Path | None = None,
    rules_dir: Path | None = None,
) -> list[tuple[str, str]]:
    """Bloco de diagnóstico storm para o `doctor` (read-only)."""
    home = home or Path.home()
    return [
        check_quirk(quirks_text),
        check_steam_input(home),
        check_wireplumber(dropin_dir),
        check_authorized_rule(rules_dir),
    ]


def _safe_read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return ""


__all__ = [
    "check_authorized_rule",
    "check_quirk",
    "check_steam_input",
    "check_wireplumber",
    "find_localconfig_vdfs",
    "storm_report",
]
