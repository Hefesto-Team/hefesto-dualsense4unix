"""Materialização das envs de launch para o wrapper `hefesto-launch` (DEDUP-04).

A launch option persistida na Steam virou uma string CONSTANTE (o wrapper);
quem varia é ISTO aqui: arquivos `VAR=VAL` em
`~/.local/state/hefesto-dualsense4unix/launch_env/` que o daemon REGRAVA a
cada transição de estado e que o wrapper lê no momento do launch — depois de
passar no gate de vida (connect+ping IPC). Daemon morto/degradado => o
wrapper não exporta NADA e o jogo abre com o físico visível (pior caso:
controle duplicado, nunca zero controles).

Gatilhos de regravação (os três do sprint doc + o da revisão adversarial):
1. mudança de perfil/config (troca de máscara, liga/desliga emulação, Modo
   Nativo, `profile.switch`/`daemon.reload` via IPC);
2. transição de backend do vpad (uhid<->uinput — as promoções recriam o
   device via `start/stop_gamepad_emulation`, que chamam aqui; a falha TOTAL
   do start também regrava — daemon vivo sem vpad não pode deixar um IGNORE
   rançoso da sessão anterior no arquivo);
3. mudança do conjunto de jogadores do co-op (spawn/teardown de vpad);
4. mudança do CONJUNTO de perfis (save/delete/import pela GUI grava direto no
   disco — a GUI avisa via IPC `launch_env.refresh`, senão o
   `steam_app_<appid>.env` de um perfil novo ficaria ausente/rançoso na
   primeira sessão do jogo).

O conteúdo reflete o backend REAL agregado POR JOGADOR (espelha a
honestidade do `daemon_actions.compose_launch` histórico): QUALQUER vpad em
uinput/0ce6 => SEM `IGNORE_DEVICES` (esconder o físico com um vpad que a SDL
pode mapear errado deixaria um controle de botões trocados — ou nenhum —
como único; duplicado > zero controles).

Arquivos por appid: perfil com `steam_app_<appid>` no `window_class` ganha
`steam_app_<appid>.env` com a opinião DAQUELE perfil (o jogo é lançado ANTES
de a janela existir, então o autoswitch ainda não ativou o perfil — o
arquivo antecipa o modo que ele vai impor). Perfil sem opinião => sem
arquivo => o wrapper cai no `default.env` (máscara/backend globais atuais).
Resolução no MÍNIMO, sem UI de biblioteca de jogos.
"""
from __future__ import annotations

import contextlib
import datetime as _dt
import re
from collections.abc import Sequence
from pathlib import Path
from typing import TYPE_CHECKING, Any

from hefesto_dualsense4unix.utils.logging_config import get_logger
from hefesto_dualsense4unix.utils.xdg_paths import launch_env_dir

if TYPE_CHECKING:
    from hefesto_dualsense4unix.daemon.protocols import DaemonProtocol

logger = get_logger(__name__)

#: Vars que o wrapper aceita exportar (allowlist ESPELHADA em
#: `assets/hefesto-launch.sh` — mudar aqui exige mudar lá). Qualquer outra
#: linha no arquivo é ignorada pelo wrapper (fail-safe contra arquivo
#: corrompido/adulterado exportando LD_PRELOAD e afins).
ENV_ALLOWLIST = (
    "SDL_GAMECONTROLLER_IGNORE_DEVICES",
    "SDL_JOYSTICK_HIDAPI",
    "PROTON_ENABLE_HIDRAW",
    "__GL_SHADER_DISK_CACHE",
    "__GL_SHADER_DISK_CACHE_SKIP_CLEANUP",
)

_IGNORE_VALUE = "0x054c/0x0ce6"

_STEAM_APP_WC_RE = re.compile(r"^steam_app_(\d+)$")


def compose_env(
    *,
    native_mode: bool,
    emulation_enabled: bool,
    flavor: str,
    backends: Sequence[str],
) -> dict[str, str]:
    """Envs de launch para UM estado do daemon. Pura e testável.

    - Modo Nativo: `PROTON_ENABLE_HIDRAW=1` SEM IGNORE — o jogo fala com o
      hidraw do FÍSICO; esconder o físico aqui é exatamente o "zero
      controles" relatado ao vivo.
    - Xbox: `SDL_JOYSTICK_HIDAPI=0` (SDL lê o evdev, que o daemon graba) +
      IGNORE do físico. O vpad é 045e — nunca colide com o 0ce6.
    - DualSense com TODOS os vpads em uhid (Edge 0df2 com hidraw real):
      `PROTON_ENABLE_HIDRAW=1` + IGNORE — dedup no layout PS.
    - DualSense com QUALQUER vpad em uinput (degradado), emulação desligada
      ou sem vpad vivo: SÓ o preload de shaders. Duplicado > zero controles.

    O preload (`__GL_SHADER_*`) entra em toda variante: é inócuo e é a parte
    "carregamento completo" que o botão da GUI sempre prometeu.
    """
    env: dict[str, str] = {}
    if native_mode:
        env["PROTON_ENABLE_HIDRAW"] = "1"
    elif emulation_enabled and backends:
        if flavor == "xbox":
            env["SDL_JOYSTICK_HIDAPI"] = "0"
            env["SDL_GAMECONTROLLER_IGNORE_DEVICES"] = _IGNORE_VALUE
        elif flavor == "dualsense" and all(b == "uhid" for b in backends):
            env["PROTON_ENABLE_HIDRAW"] = "1"
            env["SDL_GAMECONTROLLER_IGNORE_DEVICES"] = _IGNORE_VALUE
        # dualsense degradado (algum uinput) => sem IGNORE, de propósito.
    env["__GL_SHADER_DISK_CACHE"] = "1"
    env["__GL_SHADER_DISK_CACHE_SKIP_CLEANUP"] = "1"
    return env


def _snapshot(daemon: DaemonProtocol) -> tuple[bool, bool, str, list[str]]:
    """(native, emulation_enabled, flavor, backends REAIS de todos os vpads)."""
    native = False
    with contextlib.suppress(Exception):
        native = bool(daemon.is_native_mode())
    cfg = getattr(daemon, "config", None)
    enabled = bool(getattr(cfg, "gamepad_emulation_enabled", False))
    flavor = str(getattr(cfg, "gamepad_flavor", "dualsense") or "dualsense")

    backends: list[str] = []
    primary = getattr(daemon, "_gamepad_device", None)
    if primary is not None:
        backends.append(str(getattr(primary, "backend", "") or ""))
    coop = getattr(daemon, "_coop_manager", None)
    players = getattr(coop, "_players", None)
    if isinstance(players, dict):
        for player in players.values():
            vpad = getattr(player, "vpad", None)
            if vpad is not None:
                backends.append(str(getattr(vpad, "backend", "") or ""))
    return native, enabled, flavor, backends


def _load_profiles(daemon: DaemonProtocol) -> list[Any]:
    """Perfis do disco, best-effort ([] quando indisponível)."""
    try:
        from hefesto_dualsense4unix.profiles.manager import ProfileManager

        return list(ProfileManager(controller=daemon.controller).list_profiles())
    except Exception:
        logger.debug("launch_env_perfis_indisponiveis", exc_info=True)
        return []


def _steam_profiles(daemon: DaemonProtocol) -> list[tuple[int, Any]]:
    """(appid, Profile) para cada perfil com `steam_app_<appid>` no match."""
    out: list[tuple[int, Any]] = []
    for profile in _load_profiles(daemon):
        match = getattr(profile, "match", None)
        for wc in getattr(match, "window_class", None) or []:
            m = _STEAM_APP_WC_RE.match(str(wc))
            if m is not None:
                out.append((int(m.group(1)), profile))
    return out


def _nativos_fora_da_antecipacao(profiles: Sequence[Any]) -> list[str]:
    """Nomes dos perfis nativo/desktop que a antecipação por-appid NÃO cobre.

    Achado MED da revisão adversarial da Fase 2: um perfil `kind=native|
    desktop` casado por `window_title_regex`/`process_name` (o próprio sprint
    UX recomenda "perfil para o launcher" por título) — ou por um
    `window_class` que não seja `steam_app_<id>` — não gera arquivo por appid,
    então o jogo lança pelo `default.env`. Se esse default carrega IGNORE, a
    sequência é determinística: a janela ganha foco → o autoswitch ativa o
    perfil nativo → a emulação cai → o vpad some e o físico continua escondido
    pelo IGNORE congelado na env do processo = ZERO controles. Quando existe
    ao menos um perfil assim, o `default.env` OMITE o IGNORE (conservador:
    duplicado > zero controles). Perfil coberto = só `steam_app_*` no
    window_class e nenhum outro critério (o arquivo por-appid antecipa o modo
    dele). `MatchAny` com modo nativo/desktop conta como arriscado.
    """
    out: list[str] = []
    for profile in profiles:
        kind = getattr(getattr(profile, "mode", None), "kind", None)
        if kind not in ("native", "desktop"):
            continue
        match = getattr(profile, "match", None)
        wcs = [str(wc) for wc in getattr(match, "window_class", None) or []]
        coberto = (
            bool(wcs)
            and all(_STEAM_APP_WC_RE.match(wc) is not None for wc in wcs)
            and not getattr(match, "window_title_regex", None)
            and not (getattr(match, "process_name", None) or [])
        )
        if not coberto:
            out.append(str(getattr(profile, "name", "?")))
    return out


def _env_for_profile(
    profile: Any,
    *,
    flavor_atual: str,
    backends: list[str],
) -> tuple[dict[str, str], str] | None:
    """(env, motivo) antecipando o modo que o perfil impõe; None = sem opinião.

    Perfil `mode=None` não materializa arquivo próprio — o wrapper cai no
    `default.env`. `kind=gamepad` com máscara dualsense usa os backends
    REAIS atuais (se a emulação está desligada agora, não dá para garantir
    uhid no futuro => conservador, sem IGNORE).
    """
    mode = getattr(profile, "mode", None)
    if mode is None:
        return None
    kind = getattr(mode, "kind", None)
    if kind == "native":
        return (
            compose_env(
                native_mode=True, emulation_enabled=False,
                flavor=flavor_atual, backends=[],
            ),
            "perfil nativo",
        )
    if kind == "desktop":
        return (
            compose_env(
                native_mode=False, emulation_enabled=False,
                flavor=flavor_atual, backends=[],
            ),
            "perfil desktop",
        )
    if kind == "gamepad":
        flavor = str(getattr(mode, "gamepad_flavor", None) or flavor_atual)
        if flavor == "xbox":
            # O vpad Xbox é uinput 045e POR DESIGN — o IGNORE é seguro
            # independente do estado atual (invariante VPAD-06).
            return (
                compose_env(
                    native_mode=False, emulation_enabled=True,
                    flavor="xbox", backends=["uinput"],
                ),
                "perfil gamepad xbox",
            )
        return (
            compose_env(
                native_mode=False, emulation_enabled=True,
                flavor=flavor, backends=backends,
            ),
            "perfil gamepad dualsense (backends reais)",
        )
    return None


def _render(env: dict[str, str], estado: str) -> str:
    ts = _dt.datetime.now().isoformat(timespec="seconds")
    lines = [
        "# Materializado pelo daemon do Hefesto (DEDUP-04). Não edite:",
        "# é regravado a cada transição de estado do gamepad virtual.",
        f"# estado: {estado} | {ts}",
    ]
    lines.extend(f"{key}={value}" for key, value in env.items())
    return "\n".join(lines) + "\n"


def _write_atomic(path: Path, content: str) -> None:
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(content, encoding="utf-8")
    tmp.replace(path)


def materialize_launch_env(daemon: DaemonProtocol) -> None:
    """Regrava `default.env` + `steam_app_<appid>.env` com o estado REAL.

    Best-effort e barata (arquivos de ~200 B): NUNCA propaga exceção — o
    wrapper degrada sozinho para "nenhuma env" quando o arquivo falta; a
    materialização quebrada não pode derrubar o start da emulação.
    """
    try:
        target = launch_env_dir(ensure=True)
        native, enabled, flavor, backends = _snapshot(daemon)
        estado = (
            f"native={native} emulacao={enabled} mascara={flavor} "
            f"backends={backends or '[]'}"
        )
        # DEDUP-06: o log de "dedup quebrada" mora AQUI, na borda de
        # materialização (transição de estado) — nunca no state_full de 20 Hz.
        # O `dedup_ok` por jogador que a GUI/doctor consomem sai do IPC.
        if (
            not native
            and enabled
            and flavor == "dualsense"
            and backends
            and any(b != "uhid" for b in backends)
        ):
            logger.warning("dedup_broken", motivo="vpad_uinput", backends=backends)
        default_env = compose_env(
            native_mode=native,
            emulation_enabled=enabled,
            flavor=flavor,
            backends=backends,
        )
        if "SDL_GAMECONTROLLER_IGNORE_DEVICES" in default_env:
            arriscados = _nativos_fora_da_antecipacao(_load_profiles(daemon))
            if arriscados:
                # Perfil nativo/desktop fora do alcance da antecipação por
                # appid: o IGNORE congelado no default.env viraria zero
                # controles quando o autoswitch ativasse esse perfil (ver
                # `_nativos_fora_da_antecipacao`). Duplicado > zero.
                del default_env["SDL_GAMECONTROLLER_IGNORE_DEVICES"]
                estado += " ignore_omitido=perfil_nativo_sem_appid"
                logger.info(
                    "launch_env_ignore_omitido_por_perfil_nativo",
                    perfis=arriscados,
                )
        _write_atomic(target / "default.env", _render(default_env, estado))
        desired = {"default.env"}
        for appid, profile in _steam_profiles(daemon):
            per_profile = _env_for_profile(
                profile, flavor_atual=flavor, backends=backends
            )
            if per_profile is None:
                continue
            env, motivo = per_profile
            name = f"steam_app_{appid}.env"
            _write_atomic(target / name, _render(env, f"{motivo} | {estado}"))
            desired.add(name)
        for stale in target.glob("steam_app_*.env"):
            if stale.name not in desired:
                with contextlib.suppress(OSError):
                    stale.unlink()
        logger.info(
            "launch_env_materializado",
            native=native,
            emulacao=enabled,
            mascara=flavor,
            backends=backends,
            arquivos=len(desired),
        )
    except Exception:
        logger.warning("launch_env_materialize_falhou", exc_info=True)


__all__ = [
    "ENV_ALLOWLIST",
    "compose_env",
    "materialize_launch_env",
]
