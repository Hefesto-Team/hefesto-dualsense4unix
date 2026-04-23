"""Cliente IPC síncrono/assíncrono para a GUI GTK.

`_run_call` é síncrono e bloqueante — NÃO chamar da thread principal GTK.
`call_async` despacha para um ThreadPoolExecutor (1 worker) e re-posta os
callbacks via `GLib.idle_add`, mantendo a thread GTK livre durante I/O.
"""
from __future__ import annotations

import asyncio
import concurrent.futures
from collections.abc import Callable
from typing import Any

from hefesto.cli.ipc_client import IpcClient, IpcError
from hefesto.utils.logging_config import get_logger

logger = get_logger(__name__)

# Executor lazy-init — criado na primeira chamada de call_async.
_EXECUTOR: concurrent.futures.ThreadPoolExecutor | None = None


def _get_executor() -> concurrent.futures.ThreadPoolExecutor:
    """Retorna (criando se necessário) o executor IPC compartilhado."""
    global _EXECUTOR  # necessário: lazy singleton
    if _EXECUTOR is None:
        _EXECUTOR = concurrent.futures.ThreadPoolExecutor(
            max_workers=1,
            thread_name_prefix="hefesto-ipc",
        )
    return _EXECUTOR


def _run_call(
    method: str,
    params: dict[str, Any] | None = None,
    timeout: float | None = 0.25,
) -> Any:
    """Executa RPC de forma síncrona com timeout.

    ATENÇÃO: função bloqueante. Não deve ser chamada da thread principal GTK.
    Indicada para uso em CLI, TUI ou dentro do worker do executor.
    """
    async def _do() -> Any:
        async with IpcClient.connect(timeout=timeout) as client:
            return await client.call(method, params or {})

    return asyncio.run(_do())


def call_async(
    method: str,
    params: dict[str, Any] | None,
    on_success: Callable[[Any], None],
    on_failure: Callable[[Exception], None] | None = None,
    timeout_s: float = 0.25,
) -> None:
    """Despacha RPC para thread worker; callbacks re-postados via GLib.idle_add.

    - `on_success(result)` é chamado na thread principal GTK após conclusão.
    - `on_failure(exc)` é chamado na thread principal GTK em caso de erro.
    - Ambos os callbacks DEVEM retornar `False` para não serem repetidos
      pelo GLib.

    A função não bloqueia a thread GTK em nenhuma circunstância.
    """
    # Import adiado para permitir testes sem GTK instalado.
    from gi.repository import GLib  # type: ignore[import]

    def _worker() -> None:
        try:
            result = _run_call(method, params, timeout=timeout_s)
        except Exception as exc:
            if on_failure is not None:
                GLib.idle_add(on_failure, exc)
            else:
                logger.warning(
                    "ipc_bridge.call_async falhou sem handler de erro",
                    method=method,
                    erro=str(exc),
                )
            return
        GLib.idle_add(on_success, result)

    _get_executor().submit(_worker)


# ---------------------------------------------------------------------------
# Helpers síncronos de alto nível (usados por CLI e código legado da GUI que
# já está em thread worker ou contexto de teste).
# ---------------------------------------------------------------------------


def daemon_state_full() -> dict[str, Any] | None:
    """Retorna estado completo via IPC; None se daemon offline."""
    try:
        result = _run_call("daemon.state_full")
        if isinstance(result, dict):
            return result
        return None
    except (FileNotFoundError, ConnectionError, IpcError, OSError):
        return None


def daemon_status_basic() -> dict[str, Any] | None:
    try:
        result = _run_call("daemon.status")
        if isinstance(result, dict):
            return result
        return None
    except (FileNotFoundError, ConnectionError, IpcError, OSError):
        return None


def profile_list() -> list[dict[str, Any]]:
    """Lista perfis. Preferência: daemon (traz 'active'); fallback: disco."""
    try:
        result = _run_call("profile.list")
        if isinstance(result, dict):
            profiles = list(result.get("profiles", []))
            if profiles:
                return profiles
    except (FileNotFoundError, ConnectionError, IpcError, OSError):
        pass

    try:
        from hefesto.profiles.loader import load_all_profiles

        return [
            {
                "name": p.name,
                "priority": p.priority,
                "match_type": p.match.type,
                "active": False,
            }
            for p in load_all_profiles()
        ]
    except Exception:
        return []


def profile_switch(name: str) -> bool:
    try:
        _run_call("profile.switch", {"name": name})
        return True
    except Exception:
        return False


def trigger_set(side: str, mode: str, params: list[int]) -> bool:
    try:
        _run_call("trigger.set", {"side": side, "mode": mode, "params": params})
        return True
    except Exception:
        return False


def led_set(
    rgb: tuple[int, int, int],
    brightness: float | None = None,
) -> bool:
    """Aplica cor RGB (opcionalmente escalada) no lightbar via IPC.

    ``brightness`` (0.0-1.0) é repassado ao daemon quando fornecido; omitido
    preserva o contrato v1 (sem multiplicador). Ver FEAT-LED-BRIGHTNESS-01.
    """
    payload: dict[str, Any] = {"rgb": list(rgb)}
    if brightness is not None:
        payload["brightness"] = float(brightness)
    try:
        _run_call("led.set", payload)
        return True
    except Exception:
        return False


def rumble_set(weak: int, strong: int) -> bool:
    """Aplica rumble persistente via IPC (BUG-RUMBLE-APPLY-IGNORED-01).

    O daemon persiste (weak, strong) em daemon.config.rumble_active e
    re-afirma a cada 200ms — vibração contínua até rumble_stop() ou
    rumble_passthrough().
    """
    try:
        _run_call("rumble.set", {"weak": weak, "strong": strong})
        return True
    except Exception:
        return False


def rumble_stop() -> bool:
    """Para rumble e fixa estado (0, 0) para re-asserção (BUG-RUMBLE-APPLY-IGNORED-01)."""
    try:
        _run_call("rumble.stop", {})
        return True
    except Exception:
        return False


def rumble_passthrough(enabled: bool = True) -> bool:
    """Libera controle de rumble para o jogo (BUG-RUMBLE-APPLY-IGNORED-01)."""
    try:
        _run_call("rumble.passthrough", {"enabled": bool(enabled)})
        return True
    except Exception:
        return False


def rumble_policy_set(policy: str) -> bool:
    """Altera política global de intensidade de rumble (FEAT-RUMBLE-POLICY-01).

    ``policy`` deve ser um de "economia", "balanceado", "max", "auto", "custom".
    Retorna True se o daemon confirmou; False se offline ou parâmetro inválido.
    """
    try:
        _run_call("rumble.policy_set", {"policy": policy})
        return True
    except Exception:
        return False


def rumble_policy_custom(mult: float) -> bool:
    """Define política "custom" com multiplicador explícito (FEAT-RUMBLE-POLICY-01).

    ``mult`` deve ser float em [0.0, 1.0].
    Retorna True se o daemon confirmou; False se offline ou parâmetro inválido.
    """
    try:
        _run_call("rumble.policy_custom", {"mult": float(mult)})
        return True
    except Exception:
        return False


def player_leds_set(bits: tuple[bool, bool, bool, bool, bool]) -> bool:
    """Aplica bitmask de 5 LEDs de player no hardware via IPC (FEAT-PLAYER-LEDS-APPLY-01).

    ``bits[0]`` = LED 1 (extremo esquerdo), ``bits[4]`` = LED 5 (extremo direito).
    Retorna True se o daemon confirmou; False se offline ou erro.
    """
    try:
        _run_call("led.player_set", {"bits": list(bits)})
        return True
    except Exception:
        return False


def apply_draft(draft_dict: dict) -> bool:  # type: ignore[type-arg]
    """Envia ``profile.apply_draft`` ao daemon via IPC (FEAT-PROFILE-STATE-01).

    ``draft_dict`` segue o contrato definido em ``DraftConfig.to_ipc_dict()``:
    chaves triggers/leds/rumble/mouse.

    Retorna True se o daemon confirmou aplicacao (status ok). False se daemon
    offline, erro de transporte ou resposta inesperada.
    """
    try:
        result = _run_call("profile.apply_draft", draft_dict, timeout=1.0)
        if isinstance(result, dict):
            return result.get("status") == "ok"
        return False
    except Exception:
        return False


def mouse_emulation_set(
    enabled: bool,
    speed: int | None = None,
    scroll_speed: int | None = None,
) -> bool:
    """Liga/desliga emulação de mouse e atualiza velocidades via IPC."""
    params: dict[str, Any] = {"enabled": bool(enabled)}
    if speed is not None:
        params["speed"] = int(speed)
    if scroll_speed is not None:
        params["scroll_speed"] = int(scroll_speed)
    try:
        _run_call("mouse.emulation.set", params)
        return True
    except Exception:
        return False


__all__ = [
    "apply_draft",
    "call_async",
    "daemon_state_full",
    "daemon_status_basic",
    "led_set",
    "mouse_emulation_set",
    "player_leds_set",
    "profile_list",
    "profile_switch",
    "rumble_passthrough",
    "rumble_policy_custom",
    "rumble_policy_set",
    "rumble_set",
    "rumble_stop",
    "trigger_set",
]

# "O segredo de ter sucesso é saber o que descartar." — Charlie Munger
