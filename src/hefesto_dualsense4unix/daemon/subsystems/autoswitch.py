"""Subsystem Autoswitch — gerencia troca automática de perfis por janela ativa.

Implementa o protocolo Subsystem e expõe start_autoswitch() / stop_autoswitch()
como funções utilitárias para uso direto pelo Daemon.
"""
from __future__ import annotations

import contextlib
import os
from typing import TYPE_CHECKING, Any

from hefesto_dualsense4unix.utils.logging_config import get_logger

if TYPE_CHECKING:
    from collections.abc import Callable

    from hefesto_dualsense4unix.daemon.context import DaemonContext
    from hefesto_dualsense4unix.daemon.lifecycle import DaemonConfig
    from hefesto_dualsense4unix.daemon.protocols import DaemonProtocol
    from hefesto_dualsense4unix.daemon.state_store import StateStore

logger = get_logger(__name__)


def _ensure_display_env() -> None:
    """Importa WAYLAND_DISPLAY/DISPLAY de `systemctl --user show-environment`.

    AUTOSWITCH-FLOOD-FIX-01. O .service ancora em default.target (autostart
    resiliente em qualquer DE) e pode subir ANTES de o compositor exportar
    WAYLAND_DISPLAY/DISPLAY para o gerenciador de usuário — o processo nasce
    sem eles, o autoswitch cai em NullBackend e o perfil-por-app fica morto a
    sessão toda (além do flood). Aqui, se ambos faltam no os.environ, puxamos
    do systemd user (que os tem após o login do COSMIC). Best-effort: nunca
    propaga exceção. Complementa o `ExecStartPre=... import-environment` do
    .service (que cobre o próximo boot); este cobre a sessão atual / restart.
    """
    if os.environ.get("WAYLAND_DISPLAY") or os.environ.get("DISPLAY"):
        return
    import shutil
    import subprocess

    systemctl = shutil.which("systemctl")
    if systemctl is None:
        return
    try:
        result = subprocess.run(
            [systemctl, "--user", "show-environment"],
            capture_output=True,
            text=True,
            timeout=2,
            check=False,
        )
    except Exception as exc:  # best-effort, nunca derruba o boot
        logger.debug("autoswitch_display_env_probe_failed", err=str(exc))
        return
    for line in result.stdout.splitlines():
        if line.startswith(("WAYLAND_DISPLAY=", "DISPLAY=")):
            key, _, value = line.partition("=")
            if value and not os.environ.get(key):
                os.environ[key] = value
                logger.info("autoswitch_display_env_imported", var=key)


def _build_diag_window_reader(store: StateStore) -> Callable[[], dict[str, Any]]:
    """Constrói o window reader e o instrumenta com diagnóstico no store.

    FEAT-WINDOW-DETECT-DIAG-01: antes, quando a detecção de janela falhava
    (ex.: cosmic-comp sem wlr-foreign-toplevel-management), o autoswitch
    ficava silenciosamente cego — perfil-por-jogo virava letra morta e nada
    apontava qual backend estava ativo. Agora cada leitura do poll grava no
    StateStore:

      window_detect_backend    -- backend efetivamente ativo, re-lido a cada
                                  leitura (a cascata Wayland pode migrar
                                  portal -> wlrctl -> null em runtime);
      window_detect_healthy    -- saudável = >= 1 leitura útil desde o boot
                                  OU presunção inicial do xlib (só escolhido
                                  com DISPLAY presente; cobre XWayland e
                                  Proton mesmo antes da primeira leitura
                                  útil — desktop vazio também dá "unknown");
      window_detect_last_class -- última wm_class útil (captura o wm_class
                                  de um jogo direto do estado, sem journal).

    Retorna um callable compatível com `AutoSwitcher.window_reader` (API
    legada de dict). O envelope fica AQUI (e não no AutoSwitcher) para o
    diagnóstico existir mesmo se alguém instanciar o AutoSwitcher com outro
    reader — o contrato do AutoSwitcher permanece intocado.
    """
    from hefesto_dualsense4unix.integrations.window_detect import build_window_reader

    reader = build_window_reader()

    def _backend_name() -> str | None:
        # Defensivo: readers substitutos (testes/integrações antigas) podem
        # não expor metadados de diagnóstico — None = "desconhecido".
        name = getattr(reader, "backend_name", None)
        return name if isinstance(name, str) else None

    # Presunção documentada: "xlib" só é escolhido com DISPLAY presente e
    # cobre o caso de uso principal (jogos XWayland/Proton) — nasce saudável.
    initial_backend = _backend_name()
    initial_healthy = initial_backend == "xlib"
    store.set_window_detect_backend(initial_backend, healthy=initial_healthy)
    logger.info(
        "window_detect_diag_seeded",
        backend=initial_backend,
        healthy=initial_healthy,
    )

    def _read() -> dict[str, Any]:
        info = reader()
        wm_class = info.get("wm_class")
        store.record_window_detect_read(
            _backend_name(),
            wm_class if isinstance(wm_class, str) else None,
        )
        return info

    return _read


class AutoswitchSubsystem:
    """Subsystem que gerencia o AutoSwitcher de perfis."""

    name = "autoswitch"
    _autoswitch: Any = None

    async def start(self, ctx: DaemonContext) -> None:
        """Inicia o AutoSwitcher com as dependências do DaemonContext."""
        from hefesto_dualsense4unix.profiles.autoswitch import AutoSwitcher
        from hefesto_dualsense4unix.profiles.manager import ProfileManager

        _ensure_display_env()
        # FEAT-POINT-AND-CLICK-01 (fix A-06/A8): provider lazy + appliers de
        # emulação — antes o manager nascia sem keyboard_device e o autoswitch
        # nunca propagava key_bindings/mouse ao focar a janela do jogo.
        daemon = getattr(ctx, "daemon", None)
        manager = ProfileManager(
            controller=ctx.controller,
            store=ctx.store,
            keyboard_device_provider=lambda: getattr(
                daemon, "_keyboard_device", None
            ),
            mouse_applier=getattr(daemon, "apply_profile_mouse", None),
            suppression_applier=getattr(daemon, "apply_profile_suppression", None),
            mode_applier=getattr(daemon, "apply_profile_mode", None),
            # FEAT-RUMBLE-POLICY-PROFILE-01: política de rumble por perfil.
            rumble_policy_applier=getattr(
                daemon, "apply_profile_rumble_policy", None
            ),
            rumble_passthrough_applier=getattr(
                daemon, "apply_profile_rumble_passthrough", None
            ),
        )
        # FEAT-WINDOW-DETECT-DIAG-01: reader instrumentado — grava backend/
        # saúde/última wm_class útil no store a cada leitura do poll.
        self._autoswitch = AutoSwitcher(
            manager=manager,
            window_reader=_build_diag_window_reader(ctx.store),
            store=ctx.store,
        )
        if not self._autoswitch.disabled():
            self._autoswitch.start()
            logger.info("autoswitch_subsystem_started")
        else:
            logger.info("autoswitch_subsystem_disabled_by_config")

    async def stop(self) -> None:
        """Para o AutoSwitcher de forma limpa. Idempotente."""
        if self._autoswitch is not None:
            with contextlib.suppress(Exception):
                self._autoswitch.stop()
            self._autoswitch = None
            logger.info("autoswitch_subsystem_stopped")

    def is_enabled(self, config: DaemonConfig) -> bool:
        return config.autoswitch_enabled


async def start_autoswitch(daemon: DaemonProtocol) -> None:
    """Função utilitária: inicia o AutoSwitcher usando o Daemon diretamente."""
    from hefesto_dualsense4unix.profiles.autoswitch import AutoSwitcher
    from hefesto_dualsense4unix.profiles.manager import ProfileManager

    _ensure_display_env()
    # FEAT-POINT-AND-CLICK-01 (fix A-06/A8): provider lazy — a captura eager de
    # `_keyboard_device` congelava None (autoswitch sobe antes do keyboard no
    # boot, lifecycle.py) e ficava stale após disconnect/reload. Os appliers
    # ligam a seção `mouse` e a supressão de modo-jogo do perfil ao daemon.
    manager = ProfileManager(
        controller=daemon.controller,
        store=daemon.store,
        keyboard_device_provider=lambda: getattr(daemon, "_keyboard_device", None),
        mouse_applier=daemon.apply_profile_mouse,
        suppression_applier=daemon.apply_profile_suppression,
        mode_applier=getattr(daemon, "apply_profile_mode", None),
        # FEAT-RUMBLE-POLICY-PROFILE-01: política de rumble por perfil.
        rumble_policy_applier=getattr(daemon, "apply_profile_rumble_policy", None),
        rumble_passthrough_applier=getattr(
            daemon, "apply_profile_rumble_passthrough", None
        ),
    )
    # FEAT-WINDOW-DETECT-DIAG-01: reader instrumentado — grava backend/
    # saúde/última wm_class útil no store a cada leitura do poll.
    daemon._autoswitch = AutoSwitcher(
        manager=manager,
        window_reader=_build_diag_window_reader(daemon.store),
        store=daemon.store,
    )
    if not daemon._autoswitch.disabled():
        daemon._autoswitch.start()


async def stop_autoswitch(daemon: DaemonProtocol) -> None:
    """Função utilitária: para o AutoSwitcher do Daemon."""
    if daemon._autoswitch is not None:
        with contextlib.suppress(Exception):
            daemon._autoswitch.stop()
        daemon._autoswitch = None


__all__ = ["AutoswitchSubsystem", "start_autoswitch", "stop_autoswitch"]
