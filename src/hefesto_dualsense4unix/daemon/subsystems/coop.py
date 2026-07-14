"""Subsystem Co-op local — N controles = N jogadores (FEAT-DSX-COOP-LOCAL-01).

O multi-controle base (FEAT-DSX-MULTI-CONTROLLER-01) é "N controles, 1 player":
o OUTPUT é broadcast e o INPUT vem só do primário. Isso serve para reserva/troca
de controle, mas NÃO para co-op (2 pessoas) — os dois viram o mesmo player.

Este subsystem adiciona, SEM tocar no caminho do primário (P1), uma camada de
"jogadores secundários": para cada controle FÍSICO além do primário, cria um
leitor evdev dedicado (com grab) e um gamepad virtual próprio (P2, P3, …). O
poll loop, depois de despachar o P1, chama `forward_all()` para repassar cada
secundário ao SEU gamepad virtual. Assim o jogo enxerga N devices distintos =
co-op local de verdade.

BUG-COOP-GRAB-PENDING-VPAD-01 — garantia: o gamepad virtual de um secundário SÓ
nasce depois do EVIOCGRAB CONFIRMADO (`grab_state == "held"`). Um jogador cujo
grab ainda está "pending" (a thread do reader não abriu o device) fica
registrado SEM vpad — o jogo não vê nada dobrado — e é promovido pelo próprio
tick (`forward_all`/`sync`) assim que o grab confirmar. Antes, o vpad nascia
com grab apenas "pendente" e uma recusa tardia (EBUSY) deixava até ~2s de
input DOBRADO no jogo até o sync derrubar o jogador.

FEAT-COOP-PLAYER-LED-01: com o co-op ativo, cada controle acende o padrão
canônico de player-LED do SEU jogador (P1 no primário, P2.. nos secundários,
na ordem de criação), via a rota sysfs do kernel — a mesma da lightbar BT
(FEAT-DSX-LIGHTBAR-SYSFS-01). Quando um jogador sai ou o co-op desliga, o
padrão do perfil ativo é restaurado (ver `_revert_player_leds`).

Pré-requisitos (gate em `should_be_active`):
  - `config.coop_enabled` ligado (default OFF — preserva o modo "1 player");
  - emulação de gamepad ativa (o P1 já é um gamepad virtual; os secundários
    seguem a mesma máscara/flavor);
  - 2+ controles físicos conectados.

FEAT-VPAD-FF-PASSTHROUGH-01: o vpad de cada jogador nasce com um
`rumble_sink` que devolve o rumble pedido pelo JOGO ao controle físico
DAQUELE jogador (targeting por MAC via `apply_game_rumble`); o
`forward_all()` bombeia o FF de cada vpad a cada tick.
"""
from __future__ import annotations

import contextlib
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from hefesto_dualsense4unix.utils.logging_config import get_logger

if TYPE_CHECKING:
    from collections.abc import Callable

    from hefesto_dualsense4unix.core.evdev_reader import EvdevReader
    from hefesto_dualsense4unix.daemon.protocols import DaemonProtocol
    from hefesto_dualsense4unix.integrations.uinput_gamepad import UinputGamepad

logger = get_logger(__name__)

#: FEAT-COOP-PLAYER-LED-01 — padrões canônicos do DualSense para os 5 LEDs de
#: player (ordem física esquerda→direita: [L2, L1, centro, R1, R2]), os mesmos
#: que o PS5 usa para indicar P1..P4.
_PLAYER_LED_PATTERNS: dict[int, tuple[bool, bool, bool, bool, bool]] = {
    1: (False, False, True, False, False),
    2: (False, True, False, True, False),
    3: (True, False, True, False, True),
    4: (True, True, False, True, True),
}


def player_led_pattern(index: int) -> tuple[bool, bool, bool, bool, bool]:
    """Padrão canônico de player-LED do jogador `index`.

    P5+ não tem padrão oficial no DualSense: acende os 5 LEDs (fallback
    inequívoco — nunca colide com P1..P4).
    """
    return _PLAYER_LED_PATTERNS.get(index, (True, True, True, True, True))


@dataclass
class _SecondaryPlayer:
    """Um jogador secundário: o evdev de um controle físico + seu gamepad virtual.

    FEAT-DSX-CONTROLLER-IDENTITY-01: a identidade do jogador é o MAC
    (`identity`); o `evdev_path` é só o node volátil que estava valendo quando
    o jogador nasceu — se o kernel re-enumerar (storm/replug), o `sync()`
    detecta a troca de node e recria o jogador limpo no node novo.

    BUG-COOP-GRAB-PENDING-VPAD-01: `vpad` nasce None quando o grab ainda está
    "pending"; `_promote_pending` cria o vpad SÓ quando `grab_state == "held"`.
    Nunca existe vpad sem grab confirmado — sem janela de input dobrado.

    FEAT-COOP-PLAYER-LED-01: `player_index` é o número do jogador (2..N),
    fixado na criação (menor índice livre — estável para quem segue vivo) e
    usado para escolher o padrão de player-LED do controle.
    """

    identity: str
    evdev_path: str
    reader: EvdevReader
    player_index: int
    vpad: UinputGamepad | None = None


class CoopManager:
    """Gerencia os jogadores secundários (P2+) do co-op local.

    Aditivo e idempotente: `sync()` reconcilia o conjunto de secundários com os
    controles fisicamente plugados (hotplug-safe); `forward_all()` repassa cada
    um ao seu gamepad virtual; `disable()`/`stop_all()` desmontam tudo (solta o
    grab, fecha os uinput e restaura os player-LEDs do perfil). Nunca propaga
    exceção para não derrubar o poll loop.
    """

    def __init__(self, daemon: DaemonProtocol) -> None:
        self._daemon = daemon
        self._players: dict[str, _SecondaryPlayer] = {}
        # PERF-MULTI-CONTROLLER-01: a enumeração completa de /dev/input é cara
        # (~10-40ms) e rodava a cada 2s NO EVENT LOOP (hitch rítmico de input
        # durante o jogo). O watch detecta mudança por listdir (~µs); a
        # enumeração cara só roda quando o conjunto de nodes mudou de fato.
        from hefesto_dualsense4unix.core.evdev_reader import InputDirWatch

        self._watch = InputDirWatch()
        self._was_active = False
        # FEAT-COOP-PLAYER-LED-01: True quando o co-op sobrescreveu algum
        # player-LED — gate para restaurar o padrão do perfil só quando preciso.
        self._leds_overridden = False
        # BUG-COOP-GRAB-PENDING-VPAD-01: True quando `_promote_pending` derrubou
        # um jogador (grab "failed"); força o próximo sync a rodar o ciclo cheio
        # e respawnar (retry), mesmo sem mudança em /dev/input.
        self._retry_spawn = False

    # -- estado / gate --------------------------------------------------

    def should_be_active(self) -> bool:
        """True se o co-op deve estar ativo agora (flag + gamepad + 2+ controles)."""
        cfg = getattr(self._daemon, "config", None)
        if not bool(getattr(cfg, "coop_enabled", False)):
            return False
        # co-op exige o caminho de gamepad virtual ligado (o P1 já é um vpad).
        return getattr(self._daemon, "_gamepad_device", None) is not None

    def player_count(self) -> int:
        """Total de jogadores ativos (P1 + secundários, incluindo pendentes)."""
        return 1 + len(self._players)

    def _primary_evdev_path(self) -> str | None:
        ev = getattr(getattr(self._daemon, "controller", None), "_evdev", None)
        path = getattr(ev, "_device_path", None)
        return str(path) if path is not None else None

    def _primary_identity(self) -> str | None:
        """Identidade (MAC) do primário; fallback por path do reader.

        FEAT-DSX-CONTROLLER-IDENTITY-01: antes o coop excluía o primário por
        PATH lido de `controller._evdev._device_path` — que fica stale/None
        durante hotplug/re-enumeração, fazendo o coop criar um vpad para o
        PRÓPRIO controle do P1 (input dobrado). O MAC do backend é estável.
        """
        ctrl = getattr(self._daemon, "controller", None)
        uniq = getattr(ctrl, "primary_uniq", None)
        if uniq:
            return str(uniq)
        path = self._primary_evdev_path()
        return f"path:{path}" if path else None

    # -- reconciliação --------------------------------------------------

    def sync(self, *, force: bool = False) -> None:
        """Reconcilia os secundários com os controles plugados. Idempotente.

        Keyed por IDENTIDADE (MAC). Derruba e recria um jogador quando:
        o controle sumiu; o node evdev do MESMO controle mudou (re-enumeração
        pós storm/replug — reconexão limpa no node novo); ou o EVIOCGRAB
        falhou (BUG-COOP-GRAB-SILENT-FAIL-01 — sem grab confirmado o físico
        dobraria o input no jogo; derrubar aqui garante retry a cada ciclo).

        BUG-COOP-GRAB-PENDING-VPAD-01: jogadores "aguardando grab" são
        promovidos (ganham vpad) aqui e a cada `forward_all` — nunca antes do
        grab confirmado. A promoção roda mesmo em tick quieto: o grab
        confirmar não muda /dev/input, então o watch não a cobriria.

        PERF-MULTI-CONTROLLER-01: a enumeração cara de /dev/input só roda
        quando (a) o listdir mudou (hotplug/re-enumeração), (b) o co-op acabou
        de ser ativado, (c) há grab degradado/derrubado a recuperar, ou
        (d) `force=True` (toggle explícito da usuária). Ticks quietos custam
        um listdir (~µs).
        """
        if not self.should_be_active():
            self._was_active = False
            if self._players or self._leds_overridden:
                self.disable()
            return

        activated = not self._was_active
        self._was_active = True
        self._promote_pending()
        retry_needed = self._retry_spawn
        self._retry_spawn = False
        grab_degraded = any(
            p.reader.grab_state == "failed" for p in self._players.values()
        )
        if not (self._watch.poll() or activated or grab_degraded or retry_needed or force):
            return

        from hefesto_dualsense4unix.core.evdev_reader import discover_dualsense_evdevs

        primary = self._primary_identity()
        want = {
            mac: str(path)
            for mac, path in discover_dualsense_evdevs().items()
            if mac != primary
        }

        for mac in list(self._players):
            player = self._players[mac]
            if mac not in want:
                self._teardown_player(mac)
            elif player.evdev_path != want[mac]:
                logger.info(
                    "coop_player_node_changed",
                    identity=mac,
                    old=player.evdev_path,
                    new=want[mac],
                )
                self._teardown_player(mac)
            elif player.reader.grab_state == "failed":
                logger.warning("coop_player_grab_failed_retry", identity=mac)
                self._teardown_player(mac)

        # hotplug-IN: cria secundários novos.
        for mac, path in want.items():
            if mac not in self._players:
                self._spawn_player(mac, path)

        # FEAT-COOP-PLAYER-LED-01: (re)afirma o padrão por jogador ao final de
        # todo ciclo cheio — cobre ativação, spawn, node novo e o replug (o
        # backend re-afirma o padrão broadcast do perfil no nó que reaparece;
        # como o replug também dispara o watch, este reassert devolve o padrão
        # do jogador logo em seguida).
        self._apply_coop_player_leds()

    def _flavor(self) -> str:
        from hefesto_dualsense4unix.integrations.uinput_gamepad import normalize_flavor

        cfg = getattr(self._daemon, "config", None)
        return normalize_flavor(getattr(cfg, "gamepad_flavor", None))

    def _next_player_index(self) -> int:
        """Menor índice de jogador livre (≥2).

        Estável para quem já está vivo (ninguém é renumerado) e sem duplicata:
        o índice de um jogador que saiu é reusado pelo próximo que entrar.
        """
        used = {p.player_index for p in self._players.values()}
        index = 2
        while index in used:
            index += 1
        return index

    def _spawn_player(self, identity: str, path: str) -> None:
        """Cria um jogador secundário para o controle `identity` no node `path`.

        BUG-COOP-GRAB-PENDING-VPAD-01: o vpad SÓ nasce com grab CONFIRMADO
        ("held"). Recusa imediata de EVIOCGRAB → nada é criado (retry natural
        no próximo sync, BUG-COOP-GRAB-SILENT-FAIL-01). Grab "pending" (a
        thread do reader ainda não abriu o device) → o jogador é registrado
        SEM vpad — o jogo não vê nada — e `_promote_pending` (todo tick) cria
        o vpad quando o grab confirmar.
        """
        from hefesto_dualsense4unix.core.evdev_reader import EvdevReader

        # target_uniq: reconexões do loop re-localizam ESTE controle pelo MAC,
        # nunca "o primeiro node da lista" (identidade estável por jogador).
        target = None if identity.startswith("path:") else identity
        reader = EvdevReader(device_path=Path(path), target_uniq=target)
        if not reader.start():
            logger.debug("coop_player_reader_unavailable", identity=identity, evdev=path)
            return
        # Grab: o jogo deve ver SÓ o gamepad virtual deste jogador, não o cru.
        if not reader.set_grab(True):
            logger.warning("coop_player_grab_refused", identity=identity, evdev=path)
            reader.stop()
            return
        player = _SecondaryPlayer(
            identity=identity,
            evdev_path=path,
            reader=reader,
            player_index=self._next_player_index(),
        )
        self._players[identity] = player
        if reader.grab_state == "held":
            self._promote_player(player)
        else:
            logger.info(
                "coop_player_grab_pending",
                identity=identity,
                evdev=path,
                player=player.player_index,
            )

    def _promote_pending(self) -> None:
        """Promove jogadores "aguardando grab": cria o vpad quando "held".

        BUG-COOP-GRAB-PENDING-VPAD-01: chamado a cada tick (`forward_all`) e a
        cada `sync`. Grab "failed" derruba o jogador SEM nunca ter criado o
        vpad e marca `_retry_spawn` (o próximo sync recria do zero).
        """
        for identity in list(self._players):
            player = self._players[identity]
            if player.vpad is not None:
                continue
            state = player.reader.grab_state
            if state == "held":
                self._promote_player(player)
            elif state == "failed":
                logger.warning(
                    "coop_player_grab_failed_drop",
                    identity=identity,
                    evdev=player.evdev_path,
                )
                self._teardown_player(identity)
                self._retry_spawn = True

    def _make_player_rumble_sink(self, identity: str) -> Callable[[int, int], None]:
        """Sink de FF do vpad de UM jogador → rumble no controle DELE (por MAC).

        FEAT-VPAD-FF-PASSTHROUGH-01: delega em `apply_game_rumble` com
        `target_uniq=MAC` — targeting via o seletor público do backend
        (`describe_controllers` + `set_output_target`), com a política global
        de intensidade e o respeito ao rumble fixado já embutidos lá.
        Identidade sem MAC ("path:...") não tem como casar o handle →
        broadcast (limitação documentada; não acontece com DualSense real).
        """
        daemon = self._daemon

        def _sink(weak: int, strong: int) -> None:
            from hefesto_dualsense4unix.daemon.subsystems.gamepad import apply_game_rumble

            target = None if identity.startswith("path:") else identity
            apply_game_rumble(daemon, weak, strong, target_uniq=target)

        return _sink

    def _promote_player(self, player: _SecondaryPlayer) -> None:
        """Cria o vpad de um jogador com grab CONFIRMADO. Falha derruba o jogador."""
        from hefesto_dualsense4unix.integrations.uinput_gamepad import UinputGamepad

        vpad = UinputGamepad.for_flavor(
            self._flavor(),
            rumble_sink=self._make_player_rumble_sink(player.identity),
        )
        if not vpad.start():
            logger.warning(
                "coop_player_vpad_failed",
                identity=player.identity,
                evdev=player.evdev_path,
            )
            self._teardown_player(player.identity)
            self._retry_spawn = True
            return
        player.vpad = vpad
        logger.info(
            "coop_player_added",
            identity=player.identity,
            evdev=player.evdev_path,
            player=player.player_index,
            players=self.player_count(),
        )

    def _teardown_player(self, identity: str) -> None:
        player = self._players.pop(identity, None)
        if player is None:
            return
        with contextlib.suppress(Exception):
            player.reader.set_grab(False)
        with contextlib.suppress(Exception):
            player.reader.stop()
        if player.vpad is not None:
            with contextlib.suppress(Exception):
                player.vpad.stop()
        # FEAT-COOP-PLAYER-LED-01: devolve ESTE controle ao padrão do perfil.
        # Best-effort: em hotplug-out o nó sysfs já sumiu junto com o controle
        # (nada a escrever); em teardown-com-respawn (node novo / retry de
        # grab) o reassert do mesmo ciclo de sync reaplica o padrão do jogador.
        self._revert_single_player_led(identity)
        logger.info("coop_player_removed", identity=identity, players=self.player_count())

    # -- player LEDs por jogador (FEAT-COOP-PLAYER-LED-01) ---------------

    def _apply_coop_player_leds(self) -> None:
        """Acende em cada controle o padrão canônico do SEU jogador.

        Rota sysfs do kernel (`sysfs_leds`, a mesma da lightbar BT): escreve
        nos nós `*:white:player-N` do controle certo, casado por MAC — o
        backend não tem escrita por-controle de player-LED (`set_player_leds`
        é broadcast) e fica intocado. Requer a regra udev
        `77-dualsense-leds.rules` (a mesma que a lightbar sysfs já usa); sem
        nó/permissão (ex.: BT sem driver novo), loga warning e segue —
        best-effort, o co-op continua funcional.

        Limitação documentada: um broadcast do perfil/GUI DURANTE o co-op
        (trocar perfil, "Aplicar LEDs") sobrescreve os padrões até o próximo
        ciclo cheio de sync (ativação/hotplug/força).
        """
        from hefesto_dualsense4unix.core import sysfs_leds

        try:
            nodes = sysfs_leds.discover()
        except Exception as exc:
            logger.warning("coop_player_led_discover_falhou", err=str(exc))
            return
        targets: list[tuple[str, int]] = []
        primary = self._primary_identity()
        if primary is not None:
            targets.append((primary, 1))
        targets.extend((mac, p.player_index) for mac, p in self._players.items())
        for mac, index in targets:
            if mac.startswith("path:"):
                # Sem MAC não há como casar o nó sysfs — controle segue com o
                # padrão broadcast (não deveria acontecer com DualSense real).
                logger.debug("coop_player_led_sem_mac", identity=mac, player=index)
                continue
            node = nodes.get(mac)
            if node is None or not node.set_players(player_led_pattern(index)):
                logger.warning("coop_player_led_indisponivel", identity=mac, player=index)
                continue
            self._leds_overridden = True

    def _profile_player_leds(self) -> tuple[bool, bool, bool, bool, bool] | None:
        """Último padrão de player-LED aplicado pelo perfil/GUI (broadcast).

        Decisão (documentada): o perfil aplica player-LEDs por broadcast via
        `controller.set_player_leds` (`core/led_control.apply_led_settings`) e
        o backend guarda o último padrão pedido em `_desired.player_leds` para
        re-afirmá-lo em reconexões. Ler esse valor é a forma mais simples e
        fiel de saber "o padrão do perfil ativo" sem recarregar o perfil aqui.
        None = nenhum perfil/GUI setou player-LED ainda.
        """
        ctrl = getattr(self._daemon, "controller", None)
        bits = getattr(getattr(ctrl, "_desired", None), "player_leds", None)
        if bits is None or len(bits) != 5:
            return None
        return (bool(bits[0]), bool(bits[1]), bool(bits[2]), bool(bits[3]), bool(bits[4]))

    def _revert_single_player_led(self, mac: str) -> None:
        """Devolve UM controle (por MAC) ao padrão do perfil. Best-effort."""
        if not self._leds_overridden or mac.startswith("path:"):
            return
        bits = self._profile_player_leds()
        if bits is None:
            return
        from hefesto_dualsense4unix.core import sysfs_leds

        try:
            node = sysfs_leds.discover().get(mac)
        except Exception:
            node = None
        if node is None or not node.set_players(bits):
            # Hotplug-out: o nó sumiu junto com o controle — nada a restaurar.
            logger.debug("coop_player_led_revert_indisponivel", identity=mac)

    def _revert_player_leds(self) -> None:
        """Restaura o padrão do perfil em TODOS os controles (co-op desligado).

        Decisão (documentada): reverter = re-emitir o último padrão broadcast
        pelo MESMO caminho público que o perfil usa (`set_player_leds`, que
        prefere sysfs e cai em pydualsense) — cobre o primário e quaisquer
        secundários de uma vez. Sem padrão conhecido (None), não escreve nada:
        o próximo apply de perfil / reassert do backend na reconexão cobre.
        """
        if not self._leds_overridden:
            return
        self._leds_overridden = False
        bits = self._profile_player_leds()
        ctrl = getattr(self._daemon, "controller", None)
        if bits is None or ctrl is None:
            logger.debug("coop_player_led_revert_sem_padrao")
            return
        try:
            ctrl.set_player_leds(bits)
        except Exception as exc:
            logger.warning("coop_player_led_revert_falhou", err=str(exc))

    # -- por tick -------------------------------------------------------

    def forward_all(self) -> None:
        """Repassa cada secundário ao seu gamepad virtual. Chamado por tick.

        Também promove jogadores "aguardando grab" (BUG-COOP-GRAB-PENDING-
        VPAD-01): o vpad nasce aqui, poucos ms depois de o grab confirmar —
        sem esperar o próximo sync (~2s). Jogadores ainda pendentes são
        pulados (não existe vpad para repassar; o jogo não vê nada).
        """
        self._promote_pending()
        for player in list(self._players.values()):
            if player.vpad is None:
                continue  # aguardando confirmação de grab
            try:
                snap = player.reader.snapshot()
                player.vpad.forward_analog(
                    lx=snap.lx,
                    ly=snap.ly,
                    rx=snap.rx,
                    ry=snap.ry,
                    l2=snap.l2_raw,
                    r2=snap.r2_raw,
                )
                player.vpad.forward_buttons(snap.buttons_pressed)
                # FEAT-VPAD-FF-PASSTHROUGH-01: rumble do jogo deste jogador.
                # getattr defensivo: fakes/vpads sem pump_ff degradam sem crash.
                pump = getattr(player.vpad, "pump_ff", None)
                if pump is not None:
                    pump()
            except Exception as exc:  # nunca derruba o poll loop
                logger.warning("coop_forward_failed", evdev=player.evdev_path, err=str(exc))

    # -- ciclo de vida --------------------------------------------------

    def disable(self) -> None:
        """Desmonta todos os secundários (solta grab, fecha uinput) e restaura
        os player-LEDs do perfil ativo. Idempotente."""
        for key in list(self._players):
            self._teardown_player(key)
        self._revert_player_leds()

    # Alias semântico para o shutdown do daemon.
    stop_all = disable


def get_coop_manager(daemon: DaemonProtocol) -> CoopManager:
    """Retorna o `CoopManager` do daemon, criando-o sob demanda (lazy)."""
    manager = getattr(daemon, "_coop_manager", None)
    if manager is None:
        manager = CoopManager(daemon)
        daemon._coop_manager = manager
    return manager


__all__ = ["CoopManager", "get_coop_manager", "player_led_pattern"]
