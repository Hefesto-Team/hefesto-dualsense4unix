"""Diagnóstico do storm -71 do DualSense (FEAT-DSX-UNIFY-01).

Checks READ-ONLY do estado anti-storm, integrados ao hefesto (o launcher
standalone dsx.sh foi removido — teoria de HW refutada; a cura de raiz do storm
é o quirk do snd_usb_audio). NÃO muta nada; NÃO precisa de root. Cada função
recebe os paths por parâmetro (default = sistema real) para testes com fixtures.

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
# SPRINT-GAME-RUMBLE-01: a cura de raiz é o quirk_flags do snd_usb_audio para o
# DualSense COM ignore_ctl_error (o que ataca o mixer que martela o EP0).
_SND_QUIRK_RE = re.compile(r"054c:0ce6:.*ignore_ctl_error")
_STEAM_INPUT_RE = re.compile(
    r'"(SteamController_PSSupport|UseSteamControllerConfig)"\s+"[12]"'
)

# STEAM-INPUT-ALLOWLIST-01 (22/07): alguns jogos entregam o suporte a DualSense
# PELA Steam (API Steamworks — caso medido: Mullet Mad Jack chama
# SetDualSenseTriggerEffect, que só funciona com o Steam Input do jogo LIGADO).
# O opt-in per-app desses títulos é deliberado — os checks não devem acusá-lo
# de conflito. Mesma allowlist do disable_steam_input.sh.
_ALLOWLIST_PATH = (
    Path.home() / ".config" / "hefesto-dualsense4unix" / "steam_input_apps.txt"
)
_SI_KEY_RE = re.compile(
    r'"(SteamController_PSSupport|SteamController_SwitchSupport|'
    r'UseSteamControllerConfig)"\s+"[12]"'
)
_VDF_BLOCK_NAME_RE = re.compile(r'^\s*"([^"]*)"\s*$')


def steam_input_allowlist(path: Path | None = None) -> set[str]:
    """AppIDs com Steam Input per-app deliberado (uma linha por id; # comenta)."""
    caminho = path or _ALLOWLIST_PATH
    out: set[str] = set()
    try:
        for linha in caminho.read_text(encoding="utf-8").splitlines():
            token = linha.split("#", 1)[0].strip()
            if token:
                out.add(token)
    except OSError:
        pass
    return out


def steam_input_on_fora_da_allowlist(text: str, allow: set[str]) -> bool:
    """True se alguma chave de Steam Input em "1"/"2" está FORA da allowlist.

    Anda a pilha de blocos do VDF (linha `"nome"` seguida de `{` abre bloco):
    `UseSteamControllerConfig` dentro de `apps/<appid>` da allowlist é opt-in
    deliberado e não conta; qualquer outra ocorrência (inclusive as chaves
    GLOBAIS PSSupport/SwitchSupport) conta como ligado-conflitante.
    """
    stack: list[str] = []
    pending = ""
    for line in text.splitlines():
        m = _VDF_BLOCK_NAME_RE.match(line)
        if m:
            pending = m.group(1)
            continue
        s = line.strip()
        if s == "{":
            stack.append(pending)
            pending = ""
            continue
        if s == "}":
            if stack:
                stack.pop()
            continue
        km = _SI_KEY_RE.search(line)
        if km is None:
            continue
        if (
            km.group(1) == "UseSteamControllerConfig"
            and stack
            and stack[-1] in allow
        ):
            continue
        return True
    return False


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
    # STEAM-INPUT-ALLOWLIST-01: opt-in per-app deliberado (ex.: MMJ) não é
    # conflito — só acusa o que a transformação do guard corrigiria.
    allow = steam_input_allowlist()
    on = [
        v
        for v in vdfs
        if steam_input_on_fora_da_allowlist(_safe_read(v), allow)
    ]
    if on:
        return (
            WARN,
            f"Steam Input LIGADO em {len(on)} perfil(is) fora da allowlist — "
            "clique 'Reaplicar fixes seguros' para desligar",
        )
    excecoes = [
        v for v in vdfs if _STEAM_INPUT_RE.search(_safe_read(v))
    ]
    if excecoes:
        return OK, (
            "Steam Input desligado (exceções per-app da allowlist ativas — "
            "ex.: jogos cujo DualSense é entregue pela Steam)"
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


def check_snd_quirk(
    quirk_flags_text: str | None = None, conf_path: Path | None = None
) -> tuple[str, str]:
    """A CURA DE RAIZ do storm (snd_usb_audio quirk_flags) está ativa?

    SPRINT-GAME-RUMBLE-01: o quirk `054c:0ce6:ignore_ctl_error|ctl_msg_delay_1m`
    torna o probe do mixer UAC tolerante e espaça o EP0 — mata o storm na origem
    PRESERVANDO mic+fone (ao contrário da regra 75). Reporta o sysfs (sessão) e o
    drop-in de /etc/modprobe.d (persistente).
    """
    if quirk_flags_text is None:
        try:
            quirk_flags_text = Path(
                "/sys/module/snd_usb_audio/parameters/quirk_flags"
            ).read_text(encoding="utf-8", errors="ignore")
        except Exception:
            quirk_flags_text = ""
    active = bool(_SND_QUIRK_RE.search(quirk_flags_text or ""))
    conf = conf_path or Path("/etc/modprobe.d/hefesto-dualsense-storm.conf")
    persisted = bool(conf.is_file() and _SND_QUIRK_RE.search(_safe_read(conf)))
    if active:
        return OK, "cura do travamento do USB ATIVA (mic e fone do controle preservados)"
    if persisted:
        return INFO, "cura do travamento agendada (reconecte o controle p/ ativar)"
    return (
        WARN,
        "cura do travamento do USB AUSENTE — clique 'Reaplicar fixes seguros' "
        "(o controle pode desconectar no meio do jogo)",
    )


def check_snd_audio_healthy(cards_text: str | None = None) -> tuple[str, str]:
    """O áudio do controle (mic+fone) está presente? Prova que a cura não o quebrou."""
    if cards_text is None:
        cards_text = _safe_read(Path("/proc/asound/cards"))
    if re.search(r"DualSense", cards_text or "", re.IGNORECASE):
        return OK, "áudio do controle presente (mic+fone do DualSense ativos)"
    return INFO, "áudio do controle ausente (controle desconectado? — ou áudio-off)"


def storm_report(
    home: Path | None = None,
    *,
    quirks_text: str | None = None,
    dropin_dir: Path | None = None,
    rules_dir: Path | None = None,
    snd_quirk_text: str | None = None,
    snd_conf_path: Path | None = None,
    cards_text: str | None = None,
) -> list[tuple[str, str]]:
    """Bloco de diagnóstico storm para o `doctor` (read-only)."""
    home = home or Path.home()
    return [
        check_snd_quirk(snd_quirk_text, snd_conf_path),
        check_snd_audio_healthy(cards_text),
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
    "check_snd_audio_healthy",
    "check_snd_quirk",
    "check_steam_input",
    "check_wireplumber",
    "find_localconfig_vdfs",
    "storm_report",
]
