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

import asyncio
import contextlib
import time
from dataclasses import asdict, replace
from typing import TYPE_CHECKING, Any

from hefesto_dualsense4unix.core.trigger_effects import build_from_name
from hefesto_dualsense4unix.core.trigger_effects import off as trigger_off
from hefesto_dualsense4unix.daemon.ipc_draft_applier import DraftApplier
from hefesto_dualsense4unix.daemon.ipc_rumble_policy import apply_rumble_policy
from hefesto_dualsense4unix.profiles.schema import RUMBLE_CUSTOM_MULT_MAX, MatchAny
from hefesto_dualsense4unix.utils.logging_config import get_logger

if TYPE_CHECKING:
    from hefesto_dualsense4unix.core.controller import IController
    from hefesto_dualsense4unix.daemon.protocols import DaemonProtocol
    from hefesto_dualsense4unix.daemon.state_store import StateStore

logger = get_logger(__name__)


def _as_str_or_none(value: Any) -> str | None:
    """Normaliza campos informativos do state_full para str | None.

    Blindagem de serialização: com daemon/controller dublados em teste
    (MagicMock), um getattr devolve um mock — que estoura no json.dumps do
    servidor. Só strings reais passam; o resto vira None.
    """
    return value if isinstance(value, str) else None


#: STATUS-01: TTL (s) da leitura sysfs por nó LED no enriquecimento do
#: `state_full`. O tick da GUI é 10 Hz (`LIVE_POLL_INTERVAL_MS=100`) e
#: `multi_intensity`/`brightness` são I/O de arquivo — sem o cache seriam até
#: 20 opens/s POR CONTROLE. Cor de lightbar com 1 s de frescor é imperceptível.
_LIGHTBAR_READ_TTL_SEC = 1.0


def _norm_uniq(value: Any) -> str | None:
    """MAC 12-hex normalizado de uma key/serial do backend, ou None.

    Mesma normalização + guarda de comprimento do `_key_to_uniq` do backend
    (uma key de fallback por path contém dígitos hex soltos e viraria um
    pseudo-MAC sem a guarda). Vive aqui para o handler casar as keys de
    `_sysfs`/`_sysfs_written` (serial com `:`) com o `uniq` do
    `describe_controllers` sem depender de método privado do backend.
    """
    if not isinstance(value, str):
        return None
    from hefesto_dualsense4unix.core.sysfs_leds import norm_mac

    normalized = norm_mac(value)
    if normalized is None or len(normalized) != 12:
        return None
    return normalized


def _rgb_or_none(value: Any) -> tuple[int, int, int] | None:
    """Coerção defensiva de um RGB vindo de backend/fake para tupla de ints."""
    if not isinstance(value, (tuple, list)) or len(value) != 3:
        return None
    try:
        return (int(value[0]), int(value[1]), int(value[2]))
    except (TypeError, ValueError):
        return None


# --- 8BIT-01: inventário de gamepads externos (opt-in do controller.list) ----

#: Orçamentos da sonda "quem segura o hidraw" (opcional e degradável): pgrep
#: com timeout curto e varredura de /proc/<pid>/fd com teto de tempo — o
#: estudo mediu ~6 ms para ~4600 fds, então 0.5 s é folga patológica. A sonda
#: roda na MESMA thread do inventário (nunca no event loop).
_HOLDERS_PGREP_TIMEOUT_SEC = 1.0
_HOLDERS_SCAN_BUDGET_SEC = 0.5
_HOLDERS_MAX_STEAM_PIDS = 8


def _steam_pids() -> list[int]:
    """PIDs do processo Steam via pgrep — padrões do `steam_running` canônico.

    Mesmos matches de `integrations/steam_launch_options.steam_running`
    (`-f steamrt64/steam` pega o runtime pelo PATH; nunca `-f steam` solto —
    o falso-positivo histórico do earlyoom), mais `-x steam` para instalações
    fora do runtime. Best-effort: qualquer falha devolve o que juntou.
    """
    import subprocess

    pids: set[int] = set()
    for args in (["pgrep", "-f", "steamrt64/steam"], ["pgrep", "-x", "steam"]):
        try:
            proc = subprocess.run(
                args,
                capture_output=True,
                timeout=_HOLDERS_PGREP_TIMEOUT_SEC,
                check=False,
                text=True,
            )
        except (OSError, subprocess.SubprocessError):
            continue
        if proc.returncode != 0:
            continue
        for token in proc.stdout.split():
            with contextlib.suppress(ValueError):
                pids.add(int(token))
    return sorted(pids)[:_HOLDERS_MAX_STEAM_PIDS]


def _steam_hidraw_holders() -> dict[str, list[int]]:
    """Mapa `/dev/hidrawN` -> PIDs do Steam que seguram o nó (8BIT-01).

    Sonda OPCIONAL e degradável, restrita aos PIDs do Steam (nunca
    `/proc/*/fd` de todos os processos) — funciona sem sudo para processos do
    mesmo usuário (readlink em /proc/<pid>/fd, provado ao vivo no estudo).
    Estourou o orçamento/permissão -> devolve o que tem; quem consome trata
    ausência como "não sondado", NUNCA como "ninguém segura". Lembrete de
    honestidade do sprint: fd aberto pelo Steam é estado NORMAL, não
    assinatura de conflito.
    """
    import os

    holders: dict[str, list[int]] = {}
    deadline = time.monotonic() + _HOLDERS_SCAN_BUDGET_SEC
    for pid in _steam_pids():
        fd_dir = f"/proc/{pid}/fd"
        try:
            entries = os.listdir(fd_dir)
        except OSError:
            continue  # processo morreu / sem permissão: segue degradado
        for fd in entries:
            if time.monotonic() > deadline:
                return holders
            target = ""
            with contextlib.suppress(OSError):
                target = os.readlink(os.path.join(fd_dir, fd))
            if target.startswith("/dev/hidraw"):
                pids_do_no = holders.setdefault(target, [])
                if pid not in pids_do_no:
                    pids_do_no.append(pid)
    return holders


def _external_inventory(dualsense_count: int = 0) -> list[dict[str, Any]]:
    """Inventário de externos + sonda de holders — roda FORA do event loop.

    Composição síncrona chamada via `asyncio.to_thread` pelo
    `_handle_controller_list`: a enumeração evdev custa 10-40 ms
    (PERF-MULTI-CONTROLLER-01) e a sonda faz subprocess/readlink — nada disso
    pode bloquear o loop do daemon (congelaria o input no meio do jogo).

    O campo `holders` só aparece quando a sonda RODOU e achou o Steam
    segurando aquele hidraw ({"steam_pids": [...]}); sonda falha/vazia =
    campo ausente, sem erro (não é critério de aceite do 8BIT-01).

    8BIT-02: cada externo ganha `player_slot` = número GLOBAL de co-op
    (continua a contagem dos DualSense: `dualsense_count + índice + 1`), e o
    daemon ESCREVE esse número no LED de player do controle (só LED, nunca
    input). Best-effort: sem a regra udev 79 (LED não gravável), a escrita
    falha em silêncio e o `player_slot` segue exposto para a GUI numerar.
    """
    from hefesto_dualsense4unix.core.evdev_reader import discover_external_gamepads
    from hefesto_dualsense4unix.core.external_leds import (
        hid_instance_for_hidraw,
        write_player_number,
    )

    inventory = discover_external_gamepads()
    holders: dict[str, list[int]] = {}
    with contextlib.suppress(Exception):
        holders = _steam_hidraw_holders()
    for index, entry in enumerate(inventory):
        hidraw = entry.get("hidraw")
        if holders and isinstance(hidraw, str) and hidraw in holders:
            entry["holders"] = {"steam_pids": holders[hidraw]}
        slot = dualsense_count + index + 1
        entry["player_slot"] = slot
        inst = hid_instance_for_hidraw(hidraw if isinstance(hidraw, str) else None)
        if inst:
            with contextlib.suppress(Exception):
                write_player_number(inst, slot)
    return inventory


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

    #: STATUS-01: cache TTL das leituras sysfs de lightbar (lazy, por
    #: instância — ver `_lightbar_read_cached`). Class attribute com default
    #: None de propósito: o mixin não é dataclass, então isto NÃO vira field
    #: do `IpcServer` (não muda o __init__ dele); a instância faz shadow na
    #: primeira leitura.
    _lightbar_read_cache: (
        dict[str, tuple[float, tuple[int, int, int] | None, bool]] | None
    ) = None

    # --- perfis ----------------------------------------------------------

    async def _handle_profile_switch(self, params: dict[str, Any]) -> dict[str, Any]:
        """Aplica perfil escolhido pelo usuário (entrada manual via IPC).

        Persistência (CLUSTER-IPC-STATE-PROFILE-01 Bug B):
          - `manager.activate(name, origin="manual")` grava `session.json`
            (canônico — usado pelo daemon em `restore_last_profile` no
            boot/reconnect). PERFIL-03: este handler é gesto MANUAL da
            usuária (GUI/CLI) — só os origins "manual" persistem a intenção.
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
        profile = self.profile_manager.activate(name, origin="manual")
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
        # DEDUP-04: gatilho "mudança de perfil" — perfis com `steam_app_<id>`
        # no match materializam arquivo de env próprio; a troca manual também
        # pode ter mudado modo/máscara via apply do perfil.
        if self.daemon is not None:
            with contextlib.suppress(Exception):
                from hefesto_dualsense4unix.daemon.launch_env import (
                    materialize_launch_env,
                )

                materialize_launch_env(self.daemon)
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
            # FEAT-DAEMON-PAUSE-RESUME-01: distingue pausado (vivo, sem input) de parado.
            "paused": bool(self.daemon is not None and self.daemon.is_paused()),
            "native_mode": bool(
                self.daemon is not None and self.daemon.is_native_mode()
            ),
            # FEAT-EMULATION-GAMEMODE-LONGPRESS-01: modo jogo (emulacao suprimida).
            "emulation_suppressed": bool(
                self.daemon is not None
                and getattr(self.daemon, "_emulation_suppressed", False)
            ),
        }

    async def _handle_daemon_pause(self, params: dict[str, Any]) -> dict[str, Any]:
        """Pausa o despacho de input sem matar o daemon (FEAT-DAEMON-PAUSE-RESUME-01)."""
        self.daemon.pause()
        return {"status": "ok", "paused": True}

    async def _handle_daemon_resume(self, params: dict[str, Any]) -> dict[str, Any]:
        """Retoma o despacho de input (FEAT-DAEMON-PAUSE-RESUME-01)."""
        self.daemon.resume()
        return {"status": "ok", "paused": False}

    async def _handle_native_mode_set(self, params: dict[str, Any]) -> dict[str, Any]:
        """Liga/desliga o Modo Nativo — "release total" do controle (FEAT-NATIVE-MODE-01).

        `enabled` opcional: ausente → toggle. Solta o controle para o jogo
        (gatilhos Off, rumble passthrough, emulação off, autoswitch/hotkey
        gateados, pausado). Desligar restaura o último perfil.
        """
        if self.daemon is None:
            raise RuntimeError("daemon indisponível")
        raw = params.get("enabled")
        if raw is None:
            enabled = not self.daemon.is_native_mode()
        elif isinstance(raw, bool):
            enabled = raw
        else:
            raise ValueError("native.mode.set exige 'enabled' boolean ou omitido")
        new_state = self.daemon.set_native_mode(enabled)
        return {"status": "ok", "native_mode": bool(new_state)}

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
            # FEAT-DAEMON-PAUSE-RESUME-01: applet/GUI distinguem pausado de parado.
            "paused": bool(self.daemon is not None and self.daemon.is_paused()),
            "native_mode": bool(
                self.daemon is not None and self.daemon.is_native_mode()
            ),
            # FEAT-PROFILE-MODE-01: origem do nativo ("manual"|"profile"|None) e
            # qual modo o perfil ativo ligou — a GUI mostra "Nativo (pelo
            # perfil)" e o comutador da aba Início reflete a origem.
            # `_as_str_or_none` blinda contra doubles de teste (MagicMock não é
            # serializável em JSON).
            "native_mode_origin": _as_str_or_none(
                getattr(self.store, "native_mode_origin", None)
            ),
            "mode_from_profile": _as_str_or_none(
                getattr(self.daemon, "_mode_from_profile", None)
                if self.daemon is not None
                else None
            ),
            # BUG-COOP-GRAB-SILENT-FAIL-01: estado observável do EVIOCGRAB do
            # primário ("off"|"pending"|"held"|"failed") — "failed" com gamepad
            # ligado = risco de input dobrado; a GUI/doctor avisam.
            "primary_grab_state": _as_str_or_none(
                getattr(
                    getattr(self.controller, "_evdev", None), "grab_state", None
                )
            ),
            # FEAT-EMULATION-GAMEMODE-LONGPRESS-01: modo jogo (emulacao suprimida).
            "emulation_suppressed": bool(
                self.daemon is not None
                and getattr(self.daemon, "_emulation_suppressed", False)
            ),
            # FEAT-WINDOW-DETECT-DIAG-01: saúde do detector de janela do
            # autoswitch — qual backend está ativo ("xlib"|"portal"|"wlrctl"|
            # "null"|None), se já houve leitura útil, e a última wm_class útil
            # vista (permite capturar o wm_class de um jogo sem ler journal).
            "window_detect_backend": _as_str_or_none(
                getattr(self.store, "window_detect_backend", None)
            ),
            "window_detect_healthy": bool(
                getattr(self.store, "window_detect_healthy", False)
            ),
            "window_detect_last_class": _as_str_or_none(
                getattr(self.store, "window_detect_last_class", None)
            ),
        }
        # DEDUP-06 (achado NOVO da revisão): físico primário em BT + Modo
        # Nativo é estruturalmente frágil — o SDL pode não enxergar o DualSense
        # BT nem SEM launch option (o backend evdev deferencia ao HIDAPI por
        # VID/PID e o HIDAPI não lê o hidraw BT). Fora do alcance do wrapper;
        # a GUI e o doctor avisam a partir DESTA flag.
        result["native_bt_fragil"] = bool(
            result["native_mode"] and result["transport"] == "bt"
        )

        # FEAT-DSX-MULTI-CONTROLLER-01: lista de controles conectados (uma entrada
        # por controle físico, com transporte e qual é o primário) para a GUI, o
        # tray e o applet mostrarem "N controles" sem uma chamada IPC separada.
        describe = getattr(self.controller, "describe_controllers", None)
        if callable(describe):
            controllers = describe()
            result["controllers"] = controllers
            # LEIGO-01b: o número do jogador de cada controle vem do daemon —
            # a GUI o rotulava por POSIÇÃO na lista (idx+1), que mente quando o
            # co-op está desligado (todos são o mesmo jogador) e quando um
            # índice é reusado depois de um jogador sair. `None` = não é jogador
            # agora; a UI omite o número em vez de inventar um.
            if self.daemon is not None and isinstance(controllers, list):
                from hefesto_dualsense4unix.daemon.subsystems.coop import (
                    resolve_player_numbers,
                )

                entries = [c for c in controllers if isinstance(c, dict)]
                with contextlib.suppress(Exception):
                    for entry, number in zip(
                        entries,
                        resolve_player_numbers(self.daemon, entries),
                        strict=True,
                    ):
                        entry["player"] = number
            # STATUS-01 + COR-05 + BT-03: enriquecimento POR CONTROLE físico —
            # slot de sessão, cor da lightbar (com dono da escrita), inputs ao
            # vivo e backend/motivo do vpad por jogador. Mora AQUI (no handler,
            # a 10 Hz com cache TTL), NUNCA em `describe_controllers()` — que
            # roda no caminho quente do FF do jogo e não pode fazer I/O de
            # arquivo. O suppress é a última linha de defesa da serialização
            # (daemon/controller dublados em teste); cada seção interna já é
            # defensiva por conta própria.
            if isinstance(controllers, list):
                with contextlib.suppress(Exception):
                    self._enrich_controllers_per_controller(
                        [c for c in controllers if isinstance(c, dict)], state
                    )

        # FEAT-DSX-CONTROLLER-SELECTOR-01: índice do controle-alvo de output
        # (None = TODOS / broadcast). getattr defensivo: backends sem o método
        # (FakeController) ou controller MagicMock em teste → None.
        get_target = getattr(self.controller, "get_output_target_index", None)
        target_index: int | None = None
        if callable(get_target):
            raw_target = get_target()
            if isinstance(raw_target, int) and not isinstance(raw_target, bool):
                target_index = raw_target
        result["output_target_index"] = target_index

        # Paridade CLI-GUI: expõe estado da emulação de mouse se o daemon
        # dono da IPC tiver config acessível (FEAT-CLI-PARITY-01).
        daemon_cfg = getattr(self.daemon, "config", None) if self.daemon else None
        if daemon_cfg is not None:
            result["mouse_emulation"] = {
                "enabled": bool(getattr(daemon_cfg, "mouse_emulation_enabled", False)),
                "speed": int(getattr(daemon_cfg, "mouse_speed", 6)),
                "scroll_speed": int(getattr(daemon_cfg, "mouse_scroll_speed", 1)),
            }
            # FEAT-DSX-GAMEPAD-FLAVOR-01: estado do gamepad virtual p/ GUI/applet.
            result["gamepad_emulation"] = {
                "enabled": bool(getattr(daemon_cfg, "gamepad_emulation_enabled", False)),
                "flavor": str(getattr(daemon_cfg, "gamepad_flavor", "dualsense")),
            }
            # UHID-04: backend do vpad primário VIVO ("uhid" = DualSense Edge real
            # 0x0df2, "uinput" = Xbox/fallback). O botão de Launch Options escolhe a
            # variante por aqui: só o "uhid" tem PID próprio e desduplica por
            # IGNORE_DEVICES; no flavor dualsense com backend "uinput" (uhid não
            # subiu) não há launch option que desduplique — a GUI avisa em vez de
            # prometer. ff_supported/plays saem no bloco rumble_ff abaixo.
            gp_dev = getattr(self.daemon, "_gamepad_device", None)
            if gp_dev is not None:
                with contextlib.suppress(Exception):
                    result["gamepad_emulation"]["backend"] = str(
                        getattr(gp_dev, "backend", "") or ""
                    )
                with contextlib.suppress(Exception):
                    result["gamepad_emulation"]["ff_supported"] = bool(
                        getattr(gp_dev, "ff_supported", False)
                    )
                # VPAD-05 — degradação NUNCA silenciosa: flavor dualsense em
                # backend uinput = vpad sem hidraw (vibração in-game morta) e
                # sem launch option segura. O dado honesto sai AQUI; o banner
                # da GUI (fase 2) e o doctor só consomem. `degraded_motivo` é
                # o que a factory pendurou no vpad ("uhid_indisponivel",
                # "uhid_start_falhou", "uhid_bind_falhou",
                # "uhid_vetado_pelo_chamador").
                with contextlib.suppress(Exception):
                    degraded = bool(
                        getattr(gp_dev, "flavor", None) == "dualsense"
                        and getattr(gp_dev, "backend", None) == "uinput"
                    )
                    result["gamepad_emulation"]["degraded"] = degraded
                    if degraded:
                        motivo = getattr(gp_dev, "fallback_motivo", None)
                        if isinstance(motivo, str) and motivo:
                            result["gamepad_emulation"]["degraded_motivo"] = motivo
            # DEDUP-06 — guard anti-veneno: `dedup_ok` agregado POR JOGADOR
            # (P1 + todos os vpads do co-op). `degraded` acima fala SÓ pelo
            # primário; um jogador do co-op em uinput com o IGNORE congelado
            # na env do jogo é AQUELE jogador com zero controle — o guard é
            # quem torna isso visível (GUI/doctor consomem daqui). O log de
            # transição (`dedup_broken`) sai na materialização do launch_env,
            # nunca aqui (o state_full roda a 20 Hz — seria flood).
            with contextlib.suppress(Exception):
                from hefesto_dualsense4unix.daemon.subsystems.gamepad import (
                    dedup_status,
                )

                dedup_ok, motivos = dedup_status(self.daemon)
                result["gamepad_emulation"]["dedup_ok"] = dedup_ok
                if motivos:
                    result["gamepad_emulation"]["dedup_motivo"] = ", ".join(motivos)
            # FEAT-DSX-COOP-LOCAL-01: estado do co-op local (toggle + nº de
            # jogadores ativos) p/ GUI/applet/CLI.
            coop_mgr = getattr(self.daemon, "_coop_manager", None)
            players_raw = coop_mgr.player_count() if coop_mgr is not None else 1
            result["coop"] = {
                "enabled": bool(getattr(daemon_cfg, "coop_enabled", False)),
                # coerção defensiva: em testes o daemon pode ser MagicMock e
                # player_count() devolver um mock não-serializável.
                "players": players_raw if isinstance(players_raw, int) else 1,
            }
            # FEAT-RUMBLE-POLICY-01: expõe política e mult efetivo ao estado.
            # L1: a observabilidade vem da ORIGEM VIVA — `daemon._last_auto_mult`,
            # o multiplicador auto mais recente, atualizado pela política que de
            # fato roda (`reassert_rumble` no poll loop / `apply_rumble_policy`
            # no rumble.set). O antigo `_rumble_engine` NÃO é instanciado no
            # daemon real (não existe esse atributo), então a leitura caía sempre
            # no fallback 1.0 — código morto. O RumbleEngine segue em uso por
            # testes/legado; só deixou de ser a fonte aqui.
            rumble_mult_applied = float(getattr(self.daemon, "_last_auto_mult", 1.0))
            result["rumble_policy"] = str(getattr(daemon_cfg, "rumble_policy", "balanceado"))
            result["rumble_policy_custom_mult"] = float(
                getattr(daemon_cfg, "rumble_policy_custom_mult", 0.7)
            )
            result["rumble_mult_applied"] = rumble_mult_applied

            # SPRINT-GAME-RUMBLE-01: diagnóstico de rumble in-game + estado do
            # rumble. `plays` = nº de "play" de FF que o JOGO pediu nos vpads
            # (P1 + co-op) desde a criação. Em 0 durante o jogo = o jogo NÃO
            # enxerga o vpad (ex.: máscara DualSense atraindo o hidraw do
            # físico). `passthrough` (rumble_active is None) distingue "jogo
            # controla a vibração" de "fixo (teste pela GUI)" — a GUI não tinha
            # como saber em qual estado estava.
            vpads: list[Any] = []
            gp_device = getattr(self.daemon, "_gamepad_device", None)
            if gp_device is not None:
                vpads.append(gp_device)
            coop_mgr = getattr(self.daemon, "_coop_manager", None)
            if coop_mgr is not None:
                players = getattr(coop_mgr, "_players", {})
                if isinstance(players, dict):
                    vpads.extend(
                        p.vpad
                        for p in players.values()
                        if getattr(p, "vpad", None) is not None
                    )
            ff_plays = 0
            ff_last: tuple[int, int] = (0, 0)
            for vp in vpads:
                with contextlib.suppress(Exception):
                    ff_plays += int(getattr(vp, "ff_play_count", 0) or 0)
                    last = getattr(vp, "ff_last_sent", None)
                    if isinstance(last, tuple) and len(last) == 2 and last != (0, 0):
                        ff_last = (int(last[0]), int(last[1]))
            result["rumble_ff"] = {
                "plays": ff_plays,
                "last_weak": ff_last[0],
                "last_strong": ff_last[1],
                "vpads": len(vpads),
            }
            rumble_active = getattr(daemon_cfg, "rumble_active", None)
            result["rumble_passthrough"] = rumble_active is None
            result["rumble_active"] = (
                [int(rumble_active[0]), int(rumble_active[1])]
                if rumble_active is not None
                else None
            )

        return result

    # --- STATUS-01 + COR-05 + BT-03: estado POR CONTROLE físico -----------

    def _enrich_controllers_per_controller(
        self, entries: list[dict[str, Any]], state: Any
    ) -> None:
        """Enriquece cada entrada de `controllers` com o estado POR CONTROLE.

        Campos novos (sempre presentes — shape estável para GUI/CLI/applet;
        os campos PRÉ-existentes não mudam):

        - ``player_slot``: número de sessão do CONTROLE (COR-01/D6), do
          `identity_registry` do daemon — consulta DEFENSIVA com
          ``assign=False`` (ler estado nunca aloca slot). O registry é
          entregue por outra frente; ausente → None.
        - ``lightbar_rgb``/``lightbar_on``/``lightbar_source``: a cor efetiva
          CONHECIDA (o que está/estaria aceso), decidida pelo DONO DA ESCRITA:
          * ``"sysfs"`` — nó gravável (mapa `_sysfs` do backend) E escrito por
            nós (rastreio `_sysfs_written`, com o priming do
            `_refresh_sysfs_leds` garantindo o frescor): a leitura da classe
            LED é a verdade. SÓ neste estado ``(0, 0, 0)`` significa
            "apagada" (refutação 1 do sprint).
          * ``"desired"`` — nó não-gravável/fora do mapa (a escrita foi por
            hidraw → classe stale POR CONSTRUÇÃO) mas o backend conhece a
            última cor mandada aplicar (`resolved_led_for`).
          * ``"desconhecida"`` — nada conhecido (rgb None; NUNCA rotular de
            "apagada" — o LED pode estar brilhando o azul-kernel agora).
          Modo Nativo: a matriz NÃO muda — o jogo escreve por hidraw (não
          toca a classe LED), então a fonte devolve a ÚLTIMA COR CONHECIDA; o
          campo global ``native_mode`` (já no payload) é o aviso da GUI ("o
          jogo é dono do LED") — nenhuma flag nova por controle.

          Contrato de cor (D8 — divergência fundamentada, decisão do
          orquestrador da onda): expõe-se UMA cor, a efetiva conhecida
          (pós-escala de brilho — o `_DesiredOutput.led` já é pós-escala; o
          manager pré-escala na borda). O par pré/pós-brilho do D8 original
          exigiria refactor do estado desejado fora do escopo; a legibilidade
          de cor escura (objetivo do D8) é da GUI via
          `utils/color_contrast.ensure_min_contrast`.
        - ``inputs``: ``{lx,ly,rx,ry,l2_raw,r2_raw,buttons}`` ou None. O
          PRIMÁRIO espelha o `state` do topo do payload (`daemon._last_state`
          — a MESMA fonte, nunca um snapshot evdev paralelo: armadilha A-09);
          secundários vêm de `CoopManager.live_snapshots()` (leitura
          não-destrutiva por MAC). Sem leitor → None (o card mostra "—",
          nunca um valor congelado fingindo vida).
        - ``vpad_backend``/``vpad_motivo`` (BT-03): backend real do vpad DO
          JOGADOR deste controle ("uhid" | "uinput") e o motivo quando
          degradado (máscara DualSense em uinput — `fallback_motivo` que a
          factory pendurou: "uhid_indisponivel", "uhid_start_falhou",
          "uhid_bind_falhou", "uhid_vetado_pelo_chamador"; ou "sem_uhid").
          Estende o `dedup_status` (DEDUP-06), que agrega por jogador — aqui
          o dado sai POR CONTROLE: primário → `_gamepad_device`; secundário
          promovido → o vpad dele no co-op; controle que não é jogador com
          vpad próprio (co-op off/pending/emulação off) → None. Máscara xbox
          é uinput POR DESIGN → nunca tem motivo.

        Custo: leituras sysfs no MÁXIMO 1x/s por nó (`_lightbar_read_cached`);
        o resto é leitura de atributos. Nada aqui toca hardware.
        """
        sysfs_map = getattr(self.controller, "_sysfs", None)
        written_map = getattr(self.controller, "_sysfs_written", None)
        node_by_uniq: dict[str, Any] = {}
        written_by_uniq: dict[str, tuple[int, int, int]] = {}
        if isinstance(sysfs_map, dict):
            for key, node in sysfs_map.items():
                uniq = _norm_uniq(key)
                if uniq is not None and node is not None:
                    node_by_uniq[uniq] = node
        if isinstance(written_map, dict):
            for key, raw in written_map.items():
                uniq = _norm_uniq(key)
                rgb = _rgb_or_none(raw)
                if uniq is not None and rgb is not None:
                    written_by_uniq[uniq] = rgb

        snapshots = self._coop_live_snapshots()
        vpad_by_uniq = self._coop_vpads_by_uniq()
        gp_dev = (
            getattr(self.daemon, "_gamepad_device", None)
            if self.daemon is not None
            else None
        )

        for entry in entries:
            uniq = entry.get("uniq")
            uniq = uniq if isinstance(uniq, str) and uniq else None

            entry["player_slot"] = self._player_slot_for(uniq)

            rgb, on, source = self._lightbar_for_uniq(
                uniq, node_by_uniq, written_by_uniq
            )
            entry["lightbar_rgb"] = list(rgb) if rgb is not None else None
            entry["lightbar_on"] = on
            entry["lightbar_source"] = source

            if entry.get("is_primary") and state is not None:
                entry["inputs"] = self._inputs_from_state(state)
            elif uniq is not None and uniq in snapshots:
                entry["inputs"] = self._inputs_from_snapshot(snapshots[uniq])
            else:
                entry["inputs"] = None

            backend, motivo = (None, None)
            if entry.get("is_primary") and gp_dev is not None:
                backend, motivo = self._vpad_backend_motivo(gp_dev)
            elif uniq is not None and uniq in vpad_by_uniq:
                backend, motivo = vpad_by_uniq[uniq]
            entry["vpad_backend"] = backend
            entry["vpad_motivo"] = motivo

    def _lightbar_for_uniq(
        self,
        uniq: str | None,
        node_by_uniq: dict[str, Any],
        written_by_uniq: dict[str, tuple[int, int, int]],
    ) -> tuple[tuple[int, int, int] | None, bool, str]:
        """(rgb, on, source) de UM controle, pelo dono da escrita (STATUS-01)."""
        if uniq is not None:
            node = node_by_uniq.get(uniq)
            if node is not None and uniq in written_by_uniq:
                rgb, node_on = self._lightbar_read_cached(node)
                if rgb is not None:
                    # `set_rgb` fixa brightness=255 e apaga por "0 0 0" — aceso
                    # de verdade = brightness > 0 E cor não-preta.
                    return rgb, bool(node_on and rgb != (0, 0, 0)), "sysfs"
                # Nó sumiu na corrida (replug) — cai para o desired abaixo.
            resolved = getattr(self.controller, "resolved_led_for", None)
            if callable(resolved):
                rgb = None
                with contextlib.suppress(Exception):
                    rgb = _rgb_or_none(resolved(uniq))
                if rgb is not None:
                    return rgb, rgb != (0, 0, 0), "desired"
        return None, False, "desconhecida"

    def _lightbar_read_cached(
        self, node: Any
    ) -> tuple[tuple[int, int, int] | None, bool]:
        """Leitura (rgb, brightness>0) de um nó LED com cache TTL por nó.

        STATUS-01: o `state_full` roda a 10 Hz e `get_rgb`/`is_on` são I/O de
        arquivo — o cache garante no máximo 1 leitura/s por nó
        (`_LIGHTBAR_READ_TTL_SEC`). Keyed pelo `indicator_dir` (estável por nó
        e muda quando o kernel recria o nó — invalidação natural no replug).
        """
        cache = self._lightbar_read_cache
        if cache is None:
            cache = {}
            self._lightbar_read_cache = cache
        cache_key = str(getattr(node, "indicator_dir", "") or f"id:{id(node)}")
        now = time.monotonic()
        hit = cache.get(cache_key)
        if hit is not None and (now - hit[0]) < _LIGHTBAR_READ_TTL_SEC:
            return hit[1], hit[2]
        rgb: tuple[int, int, int] | None = None
        on = False
        with contextlib.suppress(Exception):
            rgb = _rgb_or_none(node.get_rgb())
        with contextlib.suppress(Exception):
            on = bool(node.is_on())
        if len(cache) > 64:
            # Poda defensiva: replug infinito não pode crescer sem teto (o
            # conjunto real é 1-4 nós; 64 já é patológico).
            cache.clear()
        cache[cache_key] = (now, rgb, on)
        return rgb, on

    def _player_slot_for(self, uniq: str | None) -> int | None:
        """Slot de sessão do controle `uniq` via identity_registry (COR-01/D9).

        Consulta DEFENSIVA e só-leitura (``assign=False`` — expor estado nunca
        aloca slot novo). O registry é entregue pela frente de cores/perfis;
        daemon sem o atributo (ou dublê de teste devolvendo mock) → None.
        Controle sem MAC (uniq None) nunca tem slot (D9).
        """
        if uniq is None or self.daemon is None:
            return None
        registry = getattr(self.daemon, "identity_registry", None)
        slot_for = getattr(registry, "slot_for", None) if registry is not None else None
        if not callable(slot_for):
            return None
        raw: Any = None
        with contextlib.suppress(Exception):
            raw = slot_for(uniq, assign=False)
        if isinstance(raw, int) and not isinstance(raw, bool):
            return raw
        return None

    @staticmethod
    def _inputs_from_state(state: Any) -> dict[str, Any] | None:
        """Inputs do PRIMÁRIO a partir do `state` do topo (`daemon._last_state`)."""
        try:
            return {
                "lx": int(state.raw_lx),
                "ly": int(state.raw_ly),
                "rx": int(state.raw_rx),
                "ry": int(state.raw_ry),
                "l2_raw": int(state.l2_raw),
                "r2_raw": int(state.r2_raw),
                "buttons": sorted(state.buttons_pressed),
            }
        except (AttributeError, TypeError, ValueError):
            return None

    @staticmethod
    def _inputs_from_snapshot(snap: Any) -> dict[str, Any] | None:
        """Inputs de um secundário a partir do `EvdevSnapshot` do reader dele."""
        try:
            return {
                "lx": int(snap.lx),
                "ly": int(snap.ly),
                "rx": int(snap.rx),
                "ry": int(snap.ry),
                "l2_raw": int(snap.l2_raw),
                "r2_raw": int(snap.r2_raw),
                "buttons": sorted(snap.buttons_pressed),
            }
        except (AttributeError, TypeError, ValueError):
            return None

    def _coop_live_snapshots(self) -> dict[str, Any]:
        """`CoopManager.live_snapshots()` com blindagem de dublês de teste."""
        coop = (
            getattr(self.daemon, "_coop_manager", None)
            if self.daemon is not None
            else None
        )
        live = getattr(coop, "live_snapshots", None) if coop is not None else None
        if not callable(live):
            return {}
        out: Any = None
        with contextlib.suppress(Exception):
            out = live()
        return out if isinstance(out, dict) else {}

    def _coop_vpads_by_uniq(self) -> dict[str, tuple[str | None, str | None]]:
        """MAC -> (vpad_backend, vpad_motivo) dos jogadores secundários (BT-03).

        Mesma fonte (`coop._players`, getattr defensivo) e mesmo critério de
        degradação do `dedup_status` da Fase 2 — aqui POR CONTROLE em vez de
        agregado. Jogador pendente (sem vpad) fica fora: não é jogador ainda.
        """
        coop = (
            getattr(self.daemon, "_coop_manager", None)
            if self.daemon is not None
            else None
        )
        players = getattr(coop, "_players", None) if coop is not None else None
        if not isinstance(players, dict):
            return {}
        out: dict[str, tuple[str | None, str | None]] = {}
        for mac, player in players.items():
            if not isinstance(mac, str) or mac.startswith("path:"):
                continue
            vpad = getattr(player, "vpad", None)
            if vpad is None:
                continue
            out[mac] = self._vpad_backend_motivo(vpad)
        return out

    @staticmethod
    def _vpad_backend_motivo(vpad: Any) -> tuple[str | None, str | None]:
        """(backend, motivo) de UM vpad — motivo só quando degradado (BT-03).

        Degradado = máscara DualSense servida por uinput (sem hidraw → sem
        vibração in-game, sem dedup por PID próprio); o motivo é o
        `fallback_motivo` da factory, com "sem_uhid" de piso. Máscara xbox é
        uinput POR DESIGN — nunca é degradação (invariante do `dedup_status`).
        """
        raw_backend = getattr(vpad, "backend", None)
        backend = raw_backend if isinstance(raw_backend, str) and raw_backend else None
        motivo: str | None = None
        if backend == "uinput" and getattr(vpad, "flavor", None) == "dualsense":
            raw = getattr(vpad, "fallback_motivo", None)
            motivo = raw if isinstance(raw, str) and raw else "sem_uhid"
        return backend, motivo

    async def _handle_controller_list(self, params: dict[str, Any]) -> dict[str, Any]:
        """Lista os controles do daemon; opt-in `external` soma o inventário 8BIT-01.

        FEAT-DSX-MULTI-CONTROLLER-01: `controllers` segue com UMA entrada por
        controle físico ADOTADO (DualSense) — shape intocado. O backend real
        expõe `describe_controllers`; backends sem o método (FakeController)
        caem no resumo single-entry.

        8BIT-01 — decisão documentada: o handler é sync-fast (só leitura de
        atributos), então o inventário de gamepads EXTERNOS (read-only, todos
        os vendors) entra SÓ sob `{"external": true}` — quem não pediu não
        paga os 10-40 ms da enumeração. Mesmo sob opt-in, a enumeração roda
        FORA do event loop via `asyncio.to_thread` (pool default do loop, não
        o `daemon._executor` de 2 workers "hefesto-hid" — roubar um worker do
        HID atrasaria output de rumble/led; e `self.daemon` pode ser None).
        NADA disso entra no `state_full` (caminho quente).

        Resposta com opt-in: chave nova `external` = lista de
        `{name, vid, pid, bus, uniq, driver, evdev_path, hidraw[, holders]}`.
        Sem opt-in, a chave nem aparece (payload byte-idêntico ao legado).
        """
        external_raw = params.get("external", False)
        if not isinstance(external_raw, bool):
            raise ValueError("controller.list: 'external' precisa ser boolean")
        describe = getattr(self.controller, "describe_controllers", None)
        if callable(describe):
            result: dict[str, Any] = {"controllers": describe()}
        else:
            connected = self.controller.is_connected()
            result = {
                "controllers": [
                    {
                        "connected": connected,
                        "transport": self.controller.get_transport() if connected else None,
                    }
                ]
            }
        if external_raw:
            # 8BIT-02: os externos numeram CONTINUANDO os DualSense conectados
            # (o daemon é a fonte única do `player_slot` e escreve o LED).
            ds_count = sum(
                1
                for c in result["controllers"]
                if isinstance(c, dict) and c.get("connected")
            )
            result["external"] = await asyncio.to_thread(_external_inventory, ds_count)
        return result

    async def _handle_controller_target_set(
        self, params: dict[str, Any]
    ) -> dict[str, Any]:
        """Define o ALVO das ações de output (FEAT-DSX-CONTROLLER-SELECTOR-01).

        Params:
            index: int (posição em `controllers`, 0 = primário) ou null (TODOS).

        Com o alvo setado, lightbar/gatilhos/player-LED/rumble/mic-LED passam a
        mirar SÓ aquele controle — resolve o "ambos mostram Player 1". `index`
        null volta ao broadcast (padrão). Backends sem o método (FakeController,
        single-instance) são tolerados via getattr e tratados como broadcast.
        """
        index = params.get("index")
        # bool é subclasse de int — rejeitar True/False como índice.
        if index is not None and (isinstance(index, bool) or not isinstance(index, int)):
            raise ValueError("controller.target.set: 'index' precisa ser int ou null")
        setter = getattr(self.controller, "set_output_target", None)
        if not callable(setter):
            return {"status": "ok", "target_index": None}
        effective = setter(index)
        # Coerção defensiva: backend real devolve int|None; um mock devolveria
        # outra coisa — normaliza para int|None serializável.
        target_index = (
            effective if isinstance(effective, int) and not isinstance(effective, bool) else None
        )
        return {"status": "ok", "target_index": target_index}

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
        # FEAT-RUMBLE-POLICY-PROFILE-01: gesto MANUAL da usuária na política —
        # carimba o lock de 30s e limpa a origem "perfil" (um perfil sem
        # opinião não reverte mais o que ela escolheu na mão).
        self._mark_rumble_policy_manual()
        logger.info("rumble_policy_alterada", policy=policy)
        return {"status": "ok", "policy": policy}

    async def _handle_rumble_policy_custom(self, params: dict[str, Any]) -> dict[str, Any]:
        """Define política "custom" com multiplicador explícito (FEAT-RUMBLE-POLICY-01).

        Params:
            mult: float 0.0-2.0 (acima de 1.0 AMPLIFICA o que o jogo pediu)

        HARM-19: a faixa era `0.0-1.0` aqui e `0.0-2.0` no esquema de perfil
        (`RumbleConfig.custom_mult`), com o slider da GUI indo até 200% — três
        donos, três faixas. O slider manda `valor/100`, então de 101% em diante a
        usuária recebia um erro de validação (que a aba ainda reportava como
        "daemon offline?"). Alinhado ao esquema, que é quem documenta a intenção:
        o `BUG-RUMBLE-CUSTOM-MULT-CAP-01` subiu o slider para 200% justamente
        porque "o schema aceita custom_mult até 2.0" — e esqueceu deste handler.
        """
        mult_raw = params.get("mult")
        try:
            mult = float(mult_raw)  # type: ignore[arg-type]
        except (TypeError, ValueError) as exc:
            raise ValueError("rumble.policy_custom: 'mult' precisa ser float") from exc
        if not (0.0 <= mult <= RUMBLE_CUSTOM_MULT_MAX):
            raise ValueError(
                f"rumble.policy_custom: mult fora de [0.0, {RUMBLE_CUSTOM_MULT_MAX}]: {mult}"
            )
        daemon_cfg = getattr(self.daemon, "config", None) if self.daemon else None
        if daemon_cfg is None:
            raise ValueError("daemon não disponível para alterar política de rumble")
        daemon_cfg.rumble_policy = "custom"
        daemon_cfg.rumble_policy_custom_mult = mult
        # FEAT-RUMBLE-POLICY-PROFILE-01: gesto MANUAL — mesma razão do
        # rumble.policy_set acima.
        self._mark_rumble_policy_manual()
        logger.info("rumble_policy_custom_definida", mult=mult)
        return {"status": "ok", "mult": mult}

    def _mark_rumble_policy_manual(self) -> None:
        """Propaga o gesto manual de política de rumble ao daemon.

        FEAT-RUMBLE-POLICY-PROFILE-01: delega a `Daemon.mark_rumble_policy_manual`
        (carimbo de `_emu_manual_ts` + limpeza da origem "perfil") via getattr —
        daemons dublados em teste (MagicMock/enxutos) não têm o método e o
        handler segue funcionando.
        """
        mark_manual = getattr(self.daemon, "mark_rumble_policy_manual", None)
        if callable(mark_manual):
            mark_manual()

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
        # DEDUP-04: gatilho "mudança de config" da materialização das envs de
        # launch (o override pode ter trocado máscara/emulação sem passar
        # pelos hooks de start/stop).
        with contextlib.suppress(Exception):
            from hefesto_dualsense4unix.daemon.launch_env import (
                materialize_launch_env,
            )

            materialize_launch_env(self.daemon)
        return {"status": "ok", "config": asdict(new_cfg)}

    async def _handle_launch_env_refresh(
        self, _params: dict[str, Any]
    ) -> dict[str, Any]:
        """Rematerializa as envs de launch do wrapper (DEDUP-04) sob demanda.

        Gatilho que os hooks de transição NÃO cobrem (achado MED da revisão
        adversarial da Fase 2): criar/editar/apagar perfil pela GUI grava
        DIRETO no disco (processo da GUI) e o daemon nunca fica sabendo — o
        `steam_app_<appid>.env` de antecipação ficaria ausente/rançoso
        exatamente na PRIMEIRA sessão do jogo novo (perfil nativo recém-criado
        + launch em seguida = IGNORE congelado + autoswitch derrubando a
        emulação = zero controles). A GUI chama este método best-effort após
        save/delete/import de perfil; daemon dublado sem materialização
        responde `failed` em vez de estourar.
        """
        if self.daemon is None:
            return {"status": "failed"}
        from hefesto_dualsense4unix.daemon.launch_env import materialize_launch_env

        materialize_launch_env(self.daemon)
        return {"status": "ok"}

    async def _handle_mouse_emulation_set(
        self, params: dict[str, Any]
    ) -> dict[str, Any]:
        """Liga/desliga emulação de mouse+teclado (FEAT-MOUSE-01).

        Params:
            enabled: bool (opcional — ausente ativa a rota speed-only)
            speed: int 1-12 (opcional)
            scroll_speed: int 1-5 (opcional)

        Sem ``enabled`` (BUG-MOUSE-GUI-SYNC-01 A4): atualiza SÓ as velocidades
        na config e no device vivo (se existir), sem start/stop e sem persistir
        o flag — os sliders da GUI não conseguem religar uma emulação desligada.
        """
        enabled = params.get("enabled")
        if enabled is not None and not isinstance(enabled, bool):
            raise ValueError("mouse.emulation.set: 'enabled' precisa ser boolean ou omitido")
        speed = params.get("speed")
        scroll_speed = params.get("scroll_speed")
        if speed is not None and not isinstance(speed, int):
            raise ValueError("mouse.emulation.set: 'speed' precisa ser int")
        if scroll_speed is not None and not isinstance(scroll_speed, int):
            raise ValueError("mouse.emulation.set: 'scroll_speed' precisa ser int")

        if self.daemon is None:
            raise ValueError("daemon não disponível para alterar emulação de mouse")

        if enabled is None:
            ok = self.daemon.set_mouse_speed(speed=speed, scroll_speed=scroll_speed)
            return {
                "status": "ok" if ok else "failed",
                "enabled": bool(
                    getattr(self.daemon.config, "mouse_emulation_enabled", False)
                ),
            }

        ok = self.daemon.set_mouse_emulation(
            enabled=enabled, speed=speed, scroll_speed=scroll_speed
        )
        return {"status": "ok" if ok else "failed", "enabled": enabled and ok}

    async def _handle_mouse_emulation_restore(
        self, _params: dict[str, Any]
    ) -> dict[str, Any]:
        """Restaura a emulação de mouse conforme a preferência persistida (HARM-06).

        Params: nenhum — quem sabe qual é a preferência é o daemon, que a
        gravou. É o passo que faz "Controlar o PC" LIGAR o mouse em vez de só
        desligar gamepad/nativo; entra na transição de modo
        (`app/actions/mode_transition.py`), nunca em um botão solto.

        Daemon dublado em teste (sem o método) responde `failed` em vez de
        estourar: o modo desktop continua valendo sem o mouse.
        """
        if self.daemon is None:
            raise ValueError("daemon não disponível para restaurar emulação de mouse")
        restore = getattr(self.daemon, "restore_mouse_preference", None)
        if not callable(restore):
            return {"status": "failed", "enabled": False}
        enabled = bool(restore())
        return {"status": "ok", "enabled": enabled}

    async def _handle_gamepad_emulation_set(
        self, params: dict[str, Any]
    ) -> dict[str, Any]:
        """Liga/desliga o gamepad virtual e define a máscara (FEAT-DSX-GAMEPAD-FLAVOR-01).

        Params:
            enabled: bool (obrigatório)
            flavor: "dualsense" | "xbox" (opcional; mantém o atual se ausente)
        """
        enabled = params.get("enabled")
        if not isinstance(enabled, bool):
            raise ValueError("gamepad.emulation.set exige 'enabled' boolean")
        flavor = params.get("flavor")
        if flavor is not None and not isinstance(flavor, str):
            raise ValueError("gamepad.emulation.set: 'flavor' precisa ser string")
        if self.daemon is None:
            raise ValueError("daemon não disponível para alterar o gamepad virtual")

        ok = self.daemon.set_gamepad_emulation(enabled=enabled, flavor=flavor)
        active_flavor = getattr(self.daemon.config, "gamepad_flavor", None)
        return {
            "status": "ok" if ok else "failed",
            "enabled": enabled and ok,
            "flavor": active_flavor,
        }

    async def _handle_coop_set(self, params: dict[str, Any]) -> dict[str, Any]:
        """Liga/desliga o co-op local (FEAT-DSX-COOP-LOCAL-01).

        Params: enabled: bool (obrigatório). Com o co-op ligado + gamepad virtual
        ativo + 2+ controles, cada controle vira um jogador (P1, P2, …).
        """
        enabled = params.get("enabled")
        if not isinstance(enabled, bool):
            raise ValueError("coop.set exige 'enabled' boolean")
        if self.daemon is None:
            raise ValueError("daemon não disponível para alterar o co-op")
        effective = self.daemon.set_coop_enabled(enabled)
        coop = getattr(self.daemon, "_coop_manager", None)
        players = coop.player_count() if coop is not None else 1
        return {"status": "ok", "enabled": bool(effective), "players": players}

    async def _handle_emulation_suppress(
        self, params: dict[str, Any]
    ) -> dict[str, Any]:
        """Liga/desliga o modo jogo (suprime emulação mouse/teclado).

        FEAT-EMULATION-GAMEMODE-LONGPRESS-01. Param opcional `suppressed` (bool)
        define explicitamente; ausente faz toggle. Espelha o gesto de long-press
        do PS — usado por GUI/applet/CLI.
        """
        if self.daemon is None:
            raise ValueError("daemon não disponível para alterar modo jogo")
        suppressed = params.get("suppressed")
        if suppressed is not None and not isinstance(suppressed, bool):
            raise ValueError("emulation.suppress: 'suppressed' precisa ser bool")
        new_state = self.daemon.set_emulation_suppressed(suppressed)
        return {"status": "ok", "emulation_suppressed": new_state}

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
