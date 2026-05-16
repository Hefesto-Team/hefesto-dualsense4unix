"""Handlers JSON-RPC do `IpcServer` (AUDIT-FINDING-IPC-SERVER-SPLIT-01).

Separado de `ipc_server.py` para manter o dispatcher de IO enxuto (<500 LOC)
e concentrar a lógica de cada método em um único lugar. Exposto como mixin
`IpcHandlersMixin` — `IpcServer` herda dele e o dispatcher continua
registrando os handlers em `__post_init__` via `self._handle_*`.

Helper `DraftApplier` extrai as 4 seções do `profile.apply_draft` (leds,
triggers, rumble, mouse) em métodos isolados, reduzindo o tamanho do handler
orquestrador para muito abaixo do limite de 100 LOC por método.
"""
from __future__ import annotations

from dataclasses import asdict, replace
from typing import TYPE_CHECKING, Any

from hefesto_dualsense4unix.core.trigger_effects import build_from_name
from hefesto_dualsense4unix.core.trigger_effects import off as trigger_off
from hefesto_dualsense4unix.daemon.ipc_draft_applier import DraftApplier
from hefesto_dualsense4unix.daemon.ipc_rumble_policy import apply_rumble_policy
from hefesto_dualsense4unix.profiles.schema import MatchAny
from hefesto_dualsense4unix.utils.logging_config import get_logger

if TYPE_CHECKING:
    from hefesto_dualsense4unix.core.controller import IController
    from hefesto_dualsense4unix.daemon.protocols import DaemonProtocol
    from hefesto_dualsense4unix.daemon.state_store import StateStore

logger = get_logger(__name__)


class IpcHandlersMixin:
    """Mixin com os 19 métodos `_handle_*` do IpcServer.

    Não instanciável isolado — espera atributos `controller`, `store`,
    `profile_manager`, `daemon` providos pela classe concreta (IpcServer).
    """

    # Atributos fornecidos pela classe concreta. Declarados para o mypy.
    controller: IController
    store: StateStore
    profile_manager: Any
    daemon: DaemonProtocol

    # --- perfis ----------------------------------------------------------

    async def _handle_profile_switch(self, params: dict[str, Any]) -> dict[str, Any]:
        """Aplica perfil escolhido pelo usuário (entrada manual via IPC).

        Persistência (CLUSTER-IPC-STATE-PROFILE-01 Bug B):
          - `manager.activate(name)` já grava `session.json` (canônico — usado
            pelo daemon em `restore_last_profile` no boot/reconnect).
          - Adicionalmente, escrevemos `active_profile.txt` para paridade com
            a CLI legada (`hefesto-dualsense4unix profile current` ainda lê esse marker).
          - Falha em escrever o marker é best-effort: loga warning mas não
            falha o IPC. Atomicidade do conjunto: se `activate` levantar,
            `active_profile.txt` NÃO é tocado.

        Lock manual (Bug C): após persistir, ativa lock de
        ``MANUAL_PROFILE_LOCK_SEC`` segundos no `StateStore` para suprimir
        autoswitch enquanto o usuário "respira" — autoswitch volta ao normal
        quando o lock expira.
        """
        name = params.get("name")
        if not isinstance(name, str) or not name:
            raise ValueError("profile.switch exige 'name' string")
        profile = self.profile_manager.activate(name)
        # Bug B: paridade do marker da CLI legada com session.json.
        from hefesto_dualsense4unix.utils.session import save_active_marker
        save_active_marker(profile.name)
        # Usuário escolheu perfil explícito: libera autoswitch de novo
        # (BUG-MOUSE-TRIGGERS-01).
        self.store.clear_manual_trigger_active()
        # Bug C: arma lock manual; autoswitch suprime por
        # MANUAL_PROFILE_LOCK_SEC segundos.
        import time as _time

        from hefesto_dualsense4unix.daemon.state_store import (
            MANUAL_PROFILE_LOCK_SEC,
        )
        self.store.mark_manual_profile_lock(
            _time.monotonic() + MANUAL_PROFILE_LOCK_SEC
        )
        return {"active_profile": profile.name}

    async def _handle_profile_list(self, params: dict[str, Any]) -> dict[str, Any]:
        profiles = self.profile_manager.list_profiles()
        return {
            "profiles": [
                {
                    "name": p.name,
                    "priority": p.priority,
                    "match_type": "any" if isinstance(p.match, MatchAny) else "criteria",
                }
                for p in profiles
            ]
        }

    async def _handle_profile_apply_draft(
        self, params: dict[str, Any]
    ) -> dict[str, Any]:
        """Aplica draft completo em ordem canonica: leds -> triggers -> rumble -> mouse.

        Cada setor é aplicado de forma best-effort pelo `DraftApplier`: falha em
        um setor loga warning mas não bloqueia os demais. Retorna lista
        ``applied`` com setores que foram aplicados com sucesso
        (FEAT-PROFILE-STATE-01).
        """
        applier = DraftApplier(
            controller=self.controller,
            store=self.store,
            daemon=self.daemon,
        )
        applied = applier.apply(params)
        return {"status": "ok", "applied": applied}

    # --- triggers --------------------------------------------------------

    async def _handle_trigger_set(self, params: dict[str, Any]) -> dict[str, Any]:
        side = params.get("side")
        mode = params.get("mode")
        trigger_params = params.get("params", [])
        if side not in ("left", "right"):
            raise ValueError("trigger.set: side precisa ser 'left' ou 'right'")
        if not isinstance(mode, str):
            raise ValueError("trigger.set: mode precisa ser string")
        if not isinstance(trigger_params, list):
            raise ValueError("trigger.set: params precisa ser lista")
        effect = build_from_name(mode, trigger_params)
        self.controller.set_trigger(side, effect)
        # BUG-MOUSE-TRIGGERS-01: usuário aplicou trigger manual via GUI/IPC.
        # Marca override para o autoswitch não sobrescrever (especialmente
        # ao ligar emulação de mouse, cujo movimento muda foco de janela).
        self.store.mark_manual_trigger_active()
        return {"status": "ok"}

    async def _handle_trigger_reset(self, params: dict[str, Any]) -> dict[str, Any]:
        target = params.get("side", "both")
        if target not in ("left", "right", "both"):
            raise ValueError("trigger.reset: side deve ser left|right|both")
        if target in ("left", "both"):
            self.controller.set_trigger("left", trigger_off())
        if target in ("right", "both"):
            self.controller.set_trigger("right", trigger_off())
        # Reset explícito libera autoswitch de volta (BUG-MOUSE-TRIGGERS-01).
        self.store.clear_manual_trigger_active()
        return {"status": "ok"}

    # --- leds ------------------------------------------------------------

    async def _handle_led_set(self, params: dict[str, Any]) -> dict[str, Any]:
        rgb = params.get("rgb")
        if not isinstance(rgb, list) or len(rgb) != 3:
            raise ValueError("led.set: rgb precisa ser lista com 3 inteiros")
        for idx, v in enumerate(rgb):
            if not isinstance(v, int) or not (0 <= v <= 255):
                raise ValueError(f"led.set: rgb[{idx}] fora de byte")
        # brightness opcional (FEAT-LED-BRIGHTNESS-01): multiplicador 0.0-1.0.
        # Ausente ou inválido -> assume 1.0 (retrocompatível com chamadas v1).
        brightness_raw = params.get("brightness", 1.0)
        try:
            brightness = float(brightness_raw)
        except (TypeError, ValueError) as exc:
            raise ValueError("led.set: brightness precisa ser numerico") from exc
        if not (0.0 <= brightness <= 1.0):
            raise ValueError(
                f"led.set: brightness fora de [0.0, 1.0]: {brightness}"
            )
        r = max(0, min(255, int(rgb[0] * brightness)))
        g = max(0, min(255, int(rgb[1] * brightness)))
        b = max(0, min(255, int(rgb[2] * brightness)))
        self.controller.set_led((r, g, b))
        return {"status": "ok"}

    async def _handle_led_player_set(self, params: dict[str, Any]) -> dict[str, Any]:
        """Aplica bitmask de 5 LEDs de player no controle.

        Params:
            bits: lista de 5 booleanos (LED1..LED5).
        """
        bits_raw = params.get("bits")
        if not isinstance(bits_raw, list) or len(bits_raw) != 5:
            raise ValueError("led.player_set: 'bits' precisa ser lista com exatamente 5 booleanos")
        for idx, v in enumerate(bits_raw):
            if not isinstance(v, bool):
                raise ValueError(f"led.player_set: bits[{idx}] precisa ser booleano")
        bits: tuple[bool, bool, bool, bool, bool] = (
            bits_raw[0], bits_raw[1], bits_raw[2], bits_raw[3], bits_raw[4]
        )
        self.controller.set_player_leds(bits)
        return {"status": "ok", "bits": list(bits)}

    # --- estado ----------------------------------------------------------

    async def _handle_daemon_status(self, params: dict[str, Any]) -> dict[str, Any]:
        snap = self.store.snapshot()
        controller = snap.controller
        return {
            "connected": bool(controller and controller.connected),
            "transport": controller.transport if controller else None,
            "active_profile": snap.active_profile,
            "battery_pct": controller.battery_pct if controller else None,
        }

    async def _handle_daemon_state_full(self, params: dict[str, Any]) -> dict[str, Any]:
        """Estado completo pra GUI consumir a 20Hz.

        FEAT-CLI-PARITY-01: inclui bloco `mouse_emulation` com enabled/speed/
        scroll_speed para o subcomando `hefesto-dualsense4unix mouse status` consultar via IPC.
        Quando `self.daemon` for None (contextos de teste ou modos legados),
        o bloco é omitido e o cliente trata como "estado indisponível".

        CLUSTER-IPC-STATE-PROFILE-01 (Bug A): preferimos `daemon._last_state`
        (último tick do poll loop) sobre `store.snapshot().controller` quando
        ambos disponíveis. Buttons saem de `state.buttons_pressed` (já
        consolidado em `backend_pydualsense.read_state` — armadilha A-09:
        nada de novos snapshots evdev no async loop). Fallback gracioso:
        se daemon ausente (testes legados), cai em store.controller_state;
        se ambos None, devolve neutro como antes.
        """
        snap = self.store.snapshot()
        # Bug A: prioriza estado LIVE do poll loop (daemon._last_state) sobre
        # snapshot do store. Em testes legados sem daemon injetado, cai no
        # store. Em ambos cenários, evita ler `_evdev.snapshot()` aqui (já
        # consolidado em buttons_pressed pelo poll loop).
        state = (
            getattr(self.daemon, "_last_state", None) if self.daemon else None
        ) or snap.controller

        # Bug A — diagnóstico de "state estagnado" quando hardware está
        # conectado mas todos os campos chegam neutros (sticks=128, gatilhos=0,
        # buttons vazio). Indica evdev_reader não inicializado ou backend HID
        # estagnado. Threshold por chamadas IPC (não por ticks).
        stale_warn_threshold = 3
        if (
            state is not None
            and self.controller.is_connected()
            and state.raw_lx == 128
            and state.raw_ly == 128
            and state.raw_rx == 128
            and state.raw_ry == 128
            and state.l2_raw == 0
            and state.r2_raw == 0
            and not state.buttons_pressed
        ):
            stale_count = self.store.bump("state_full.stale_neutral")
            if stale_count == stale_warn_threshold:
                logger.warning(
                    "state_stale_neutral_warning",
                    state_full_calls=stale_count,
                    hint="evdev_reader pode não ter conectado; HID-raw fallback estagnado",
                )

        buttons: list[str] = sorted(state.buttons_pressed) if state else []
        result: dict[str, Any] = {
            "connected": bool(state and state.connected),
            "transport": state.transport if state else None,
            "active_profile": snap.active_profile,
            "battery_pct": state.battery_pct if state else None,
            "l2_raw": state.l2_raw if state else 0,
            "r2_raw": state.r2_raw if state else 0,
            "lx": state.raw_lx if state else 128,
            "ly": state.raw_ly if state else 128,
            "rx": state.raw_rx if state else 128,
            "ry": state.raw_ry if state else 128,
            "buttons": buttons,
            "counters": snap.counters,
        }

        # Paridade CLI-GUI: expõe estado da emulação de mouse se o daemon
        # dono da IPC tiver config acessível (FEAT-CLI-PARITY-01).
        daemon_cfg = getattr(self.daemon, "config", None) if self.daemon else None
        if daemon_cfg is not None:
            result["mouse_emulation"] = {
                "enabled": bool(getattr(daemon_cfg, "mouse_emulation_enabled", False)),
                "speed": int(getattr(daemon_cfg, "mouse_speed", 6)),
                "scroll_speed": int(getattr(daemon_cfg, "mouse_scroll_speed", 1)),
            }
            # FEAT-RUMBLE-POLICY-01: expõe política e mult efetivo ao estado.
            rumble_mult_applied: float = 1.0
            rumble_engine = getattr(self.daemon, "_rumble_engine", None)
            if rumble_engine is not None:
                rumble_mult_applied = float(rumble_engine.last_mult_applied)
            result["rumble_policy"] = str(getattr(daemon_cfg, "rumble_policy", "balanceado"))
            result["rumble_policy_custom_mult"] = float(
                getattr(daemon_cfg, "rumble_policy_custom_mult", 0.7)
            )
            result["rumble_mult_applied"] = rumble_mult_applied

        return result

    async def _handle_controller_list(self, params: dict[str, Any]) -> dict[str, Any]:
        return {
            "controllers": [
                {
                    "connected": self.controller.is_connected(),
                    "transport": self.controller.get_transport()
                    if self.controller.is_connected()
                    else None,
                }
            ]
        }

    # --- rumble ----------------------------------------------------------

    async def _handle_rumble_set(self, params: dict[str, Any]) -> dict[str, Any]:
        """Aplica rumble com política de intensidade (FEAT-RUMBLE-POLICY-01).

        Persiste (weak, strong) brutos em daemon.config.rumble_active para que
        o poll loop continue re-afirmando via _reassert_rumble. O multiplicador
        de política é aplicado antes de enviar ao hardware — tanto aqui quanto
        em _reassert_rumble.
        """
        weak = params.get("weak")
        strong = params.get("strong")
        if not isinstance(weak, int) or not isinstance(strong, int):
            raise ValueError("rumble.set exige 'weak' e 'strong' inteiros 0-255")
        weak = max(0, min(255, weak))
        strong = max(0, min(255, strong))
        # Persiste estado bruto antes de aplicar para o poll loop continuar re-afirmando.
        daemon_cfg = getattr(self.daemon, "config", None) if self.daemon else None
        if daemon_cfg is not None:
            daemon_cfg.rumble_active = (weak, strong)
        # Aplica política antes de enviar ao hardware.
        eff_weak, eff_strong = apply_rumble_policy(self.daemon, weak, strong)
        self.controller.set_rumble(weak=eff_weak, strong=eff_strong)
        return {"status": "ok", "weak": weak, "strong": strong}

    async def _handle_rumble_stop(self, params: dict[str, Any]) -> dict[str, Any]:
        """Para rumble e persiste estado (0, 0) (BUG-RUMBLE-APPLY-IGNORED-01).

        Zera os motores imediatamente e atualiza daemon.config.rumble_active para
        (0, 0) de forma que o poll loop re-afirme o silêncio, evitando que outro
        write HID re-ative motores inadvertidamente. Use rumble.passthrough para
        liberar controle completo ao jogo.
        """
        daemon_cfg = getattr(self.daemon, "config", None) if self.daemon else None
        if daemon_cfg is not None:
            daemon_cfg.rumble_active = (0, 0)
        self.controller.set_rumble(weak=0, strong=0)
        return {"status": "ok"}

    async def _handle_rumble_passthrough(self, params: dict[str, Any]) -> dict[str, Any]:
        """Libera controle de rumble para jogo/UDP (BUG-RUMBLE-APPLY-IGNORED-01).

        Zera daemon.config.rumble_active, desativando a re-asserção do poll loop.
        O jogo retoma controle via UDP ou emulação Xbox360. Use rumble.set para
        retomar controle manual.

        Params:
            enabled: bool — True = habilitar passthrough (zerar rumble_active).
                            False = sem efeito; para fixar valores use rumble.set.
        """
        enabled = params.get("enabled")
        if not isinstance(enabled, bool):
            raise ValueError("rumble.passthrough exige 'enabled' boolean")
        if enabled:
            daemon_cfg = getattr(self.daemon, "config", None) if self.daemon else None
            if daemon_cfg is not None:
                daemon_cfg.rumble_active = None
        return {"status": "ok", "passthrough": enabled}

    async def _handle_rumble_policy_set(self, params: dict[str, Any]) -> dict[str, Any]:
        """Altera política global de intensidade de rumble (FEAT-RUMBLE-POLICY-01).

        Params:
            policy: "economia" | "balanceado" | "max" | "auto" | "custom"
        """
        policy = params.get("policy")
        valid_policies = ("economia", "balanceado", "max", "auto", "custom")
        if policy not in valid_policies:
            raise ValueError(
                f"rumble.policy_set: policy deve ser um de {valid_policies}"
            )
        daemon_cfg = getattr(self.daemon, "config", None) if self.daemon else None
        if daemon_cfg is None:
            raise ValueError("daemon não disponível para alterar política de rumble")
        daemon_cfg.rumble_policy = policy
        logger.info("rumble_policy_alterada", policy=policy)
        return {"status": "ok", "policy": policy}

    async def _handle_rumble_policy_custom(self, params: dict[str, Any]) -> dict[str, Any]:
        """Define política "custom" com multiplicador explícito (FEAT-RUMBLE-POLICY-01).

        Params:
            mult: float 0.0-1.0
        """
        mult_raw = params.get("mult")
        try:
            mult = float(mult_raw)  # type: ignore[arg-type]
        except (TypeError, ValueError) as exc:
            raise ValueError("rumble.policy_custom: 'mult' precisa ser float") from exc
        if not (0.0 <= mult <= 1.0):
            raise ValueError(
                f"rumble.policy_custom: mult fora de [0.0, 1.0]: {mult}"
            )
        daemon_cfg = getattr(self.daemon, "config", None) if self.daemon else None
        if daemon_cfg is None:
            raise ValueError("daemon não disponível para alterar política de rumble")
        daemon_cfg.rumble_policy = "custom"
        daemon_cfg.rumble_policy_custom_mult = mult
        logger.info("rumble_policy_custom_definida", mult=mult)
        return {"status": "ok", "mult": mult}

    # --- daemon / mouse / plugins ----------------------------------------

    async def _handle_daemon_reload(self, params: dict[str, Any]) -> dict[str, Any]:
        """Aplica overrides parciais de config em runtime (REFACTOR-DAEMON-RELOAD-01).

        Params:
            config_overrides: dict com subset de campos de DaemonConfig.
                              Chaves inexistentes em DaemonConfig sao rejeitadas.

        Retorna:
            {status: "ok", config: <novo DaemonConfig como dict>}

        Erros:
            ValueError se daemon não disponível, ou se override contém chave
            desconhecida em DaemonConfig.
        """
        if self.daemon is None:
            raise ValueError("daemon não disponível para reload")

        from hefesto_dualsense4unix.daemon.lifecycle import DaemonConfig

        overrides = params.get("config_overrides", {})
        if not isinstance(overrides, dict):
            raise ValueError("daemon.reload: 'config_overrides' deve ser objeto")

        # Validação antecipada: rejeita chaves que não existem em DaemonConfig.
        known_fields = set(DaemonConfig.__dataclass_fields__)
        unknown = set(overrides) - known_fields
        if unknown:
            raise ValueError(
                f"daemon.reload: campos desconhecidos em config_overrides: {sorted(unknown)}"
            )

        new_cfg = replace(self.daemon.config, **overrides)
        self.daemon.reload_config(new_cfg)
        return {"status": "ok", "config": asdict(new_cfg)}

    async def _handle_mouse_emulation_set(
        self, params: dict[str, Any]
    ) -> dict[str, Any]:
        """Liga/desliga emulação de mouse+teclado (FEAT-MOUSE-01).

        Params:
            enabled: bool (obrigatório)
            speed: int 1-12 (opcional)
            scroll_speed: int 1-5 (opcional)
        """
        enabled = params.get("enabled")
        if not isinstance(enabled, bool):
            raise ValueError("mouse.emulation.set exige 'enabled' boolean")
        speed = params.get("speed")
        scroll_speed = params.get("scroll_speed")
        if speed is not None and not isinstance(speed, int):
            raise ValueError("mouse.emulation.set: 'speed' precisa ser int")
        if scroll_speed is not None and not isinstance(scroll_speed, int):
            raise ValueError("mouse.emulation.set: 'scroll_speed' precisa ser int")

        if self.daemon is None:
            raise ValueError("daemon não disponível para alterar emulação de mouse")

        ok = self.daemon.set_mouse_emulation(
            enabled=enabled, speed=speed, scroll_speed=scroll_speed
        )
        return {"status": "ok" if ok else "failed", "enabled": enabled and ok}

    async def _handle_plugin_list(self, params: dict[str, Any]) -> list[dict[str, Any]]:
        """Lista plugins carregados no daemon (FEAT-PLUGIN-01).

        Retorna lista de dicts com: name, profile_match, disabled, classe.
        Requer plugins_enabled=True no daemon ou HEFESTO_DUALSENSE4UNIX_PLUGINS_ENABLED=1.
        """
        ps = getattr(self.daemon, "_plugins_subsystem", None) if self.daemon else None
        if ps is None:
            return []
        result: list[dict[str, Any]] = ps.list_plugins()
        return result

    async def _handle_plugin_reload(self, params: dict[str, Any]) -> dict[str, Any]:
        """Recarrega plugins do disco (FEAT-PLUGIN-01).

        Descarrega todos os plugins atuais, recarrega do diretório configurado
        e retorna o numero de plugins carregados.
        """
        from hefesto_dualsense4unix.daemon.context import DaemonContext

        ps = getattr(self.daemon, "_plugins_subsystem", None) if self.daemon else None
        if ps is None:
            raise ValueError("plugins não habilitados neste daemon")

        ctx = DaemonContext(
            controller=self.controller,
            bus=getattr(self.daemon, "bus", None),  # type: ignore[arg-type]
            store=self.store,
            config=getattr(self.daemon, "config", None),
            executor=getattr(self.daemon, "_executor", None),
        )
        total = ps.reload(ctx)
        return {"status": "ok", "total": total}


__all__ = ["DraftApplier", "IpcHandlersMixin"]
