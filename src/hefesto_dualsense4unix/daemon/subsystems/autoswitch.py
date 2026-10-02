"""Subsystem Autoswitch — gerencia troca automática de perfis por janela ativa."""
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
    """Importa WAYLAND_DISPLAY/DISPLAY de `systemctl --user show-environment`."""
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
    except Exception as exc:
        logger.debug("autoswitch_display_env_probe_failed", err=str(exc))
        return
    for line in result.stdout.splitlines():
        if line.startswith(("WAYLAND_DISPLAY=", "DISPLAY=")):
            key, _, value = line.partition("=")
            if value and not os.environ.get(key):
                os.environ[key] = value
                logger.info("autoswitch_display_env_imported", var=key)


def _build_diag_window_reader(store: StateStore) -> Callable[[], dict[str, Any]]:
    """Constrói o window reader e o instrumenta com diagnóstico no store."""
    from hefesto_dualsense4unix.integrations.window_detect import build_window_reader

    reader = build_window_reader()

    def _backend_name() -> str | None:
        name = getattr(reader, "backend_name", None)
        return name if isinstance(name, str) else None

    def _saude_com_prova(backend: str | None) -> bool:
        """`healthy` inicial de um backend recém-escolhido, com PROVA."""
        if backend != "xlib":
            return False
        reader()
        conexao_provada = getattr(reader, "conexao_provada", None)
        return callable(conexao_provada) and conexao_provada() is True

    initial_backend = _backend_name()
    initial_healthy = _saude_com_prova(initial_backend)
    store.set_window_detect_backend(initial_backend, healthy=initial_healthy)
    logger.info(
        "window_detect_diag_seeded",
        backend=initial_backend,
        healthy=initial_healthy,
    )

    _recover_next = [0.0]

    def _read() -> dict[str, Any]:
        recover = getattr(reader, "maybe_recover", None)
        precisa = getattr(reader, "precisa_de_resgate", None)
        cego = precisa() if callable(precisa) else (_backend_name() == "null")
        if callable(recover) and cego:
            import time

            agora = time.monotonic()
            if agora >= _recover_next[0]:
                _recover_next[0] = agora + 15.0
                _ensure_display_env()
                if recover():
                    nome = _backend_name()
                    store.set_window_detect_backend(
                        nome, healthy=_saude_com_prova(nome)
                    )
                    logger.info(
                        "window_detect_backend_recuperado", backend=nome
                    )
        info = reader()
        wm_class = info.get("wm_class")
        store.record_window_detect_read(
            _backend_name(),
            wm_class if isinstance(wm_class, str) else None,
            reason=getattr(reader, "last_reason", None),
        )
        return info

    return _read


class AutoswitchSubsystem:
    """Subsystem que gerencia o AutoSwitcher de perfis."""

    name = "autoswitch"
    _autoswitch: Any = None

    async def start(self, ctx: DaemonContext) -> None:
        """Inicia o AutoSwitcher com as dependências do DaemonContext."""
        from hefesto_dualsense4unix.integrations import lista_de_exclusao
        from hefesto_dualsense4unix.profiles.autoswitch import AutoSwitcher
        from hefesto_dualsense4unix.profiles.manager import gerente_do_daemon

        _ensure_display_env()
        daemon = getattr(ctx, "daemon", None)
        manager = gerente_do_daemon(daemon, controller=ctx.controller, store=ctx.store)
        self._autoswitch = AutoSwitcher(
            manager=manager,
            window_reader=_build_diag_window_reader(ctx.store),
            store=ctx.store,
            modo_jogo_padrao_applier=getattr(
                daemon, "aplicar_modo_jogo_padrao", None
            ),
            modo_jogo_padrao_reverter=getattr(
                daemon, "reverter_modo_jogo_padrao", None
            ),
            exclusao_applier=getattr(daemon, "aplicar_a_exclusao", None),
            exclusao_reverter=getattr(daemon, "reverter_a_exclusao", None),
            exclusao_reader=lista_de_exclusao.contem,
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
    from hefesto_dualsense4unix.integrations import lista_de_exclusao
    from hefesto_dualsense4unix.profiles.autoswitch import AutoSwitcher
    from hefesto_dualsense4unix.profiles.manager import gerente_do_daemon

    _ensure_display_env()
    manager = gerente_do_daemon(daemon, store=daemon.store)
    daemon._autoswitch = AutoSwitcher(
        manager=manager,
        window_reader=_build_diag_window_reader(daemon.store),
        store=daemon.store,
        modo_jogo_padrao_applier=getattr(daemon, "aplicar_modo_jogo_padrao", None),
        modo_jogo_padrao_reverter=getattr(daemon, "reverter_modo_jogo_padrao", None),
        exclusao_applier=getattr(daemon, "aplicar_a_exclusao", None),
        exclusao_reverter=getattr(daemon, "reverter_a_exclusao", None),
        exclusao_reader=lista_de_exclusao.contem,
    )
    if not daemon._autoswitch.disabled():
        daemon._autoswitch.start()


__all__ = ["AutoswitchSubsystem", "start_autoswitch"]
