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
    from collections.abc import Callable, Mapping, Sequence

    from hefesto_dualsense4unix.core.evdev_reader import EvdevReader
    from hefesto_dualsense4unix.daemon.protocols import DaemonProtocol
    from hefesto_dualsense4unix.integrations.virtual_pad import VirtualPad

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
    vpad: VirtualPad | None = None


class CoopManager:
    """Gerencia os jogadores secundários (P2+) do co-op local.

    Aditivo e idempotente: `sync()` reconcilia o conjunto de secundários com os
    controles fisicamente plugados (hotplug-safe); `forward_all()` repassa cada
    um ao seu gamepad virtual; `disable()`/`stop_all()` desmontam tudo (solta o
    grab, fecha os vpads e restaura os player-LEDs do perfil). Nunca propaga
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

    def player_indexes(self) -> dict[str, int]:
        """MAC -> número do jogador que o JOGO vê (P1 no primário, P2+ nos demais).

        LEIGO-01b: a GUI rotulava os cards por POSIÇÃO na lista (`idx+1`), o que
        mente em dois casos reais — com o co-op desligado todos os controles
        alimentam o MESMO vpad (são um jogador só) e, com ele ligado,
        `_next_player_index` REUSA índices de quem saiu, então a ordem da lista
        deixa de casar com o número do jogador.

        Só entra quem o jogo enxerga: um secundário ainda aguardando o grab não
        tem vpad — reservou o índice, mas não é jogador nenhum até ser promovido.
        Identidade sem MAC ("path:") fica de fora (não há como casar o card).
        """
        out: dict[str, int] = {}
        primary = self._primary_identity()
        if primary is not None and not primary.startswith("path:"):
            out[primary] = 1
        for mac, player in self._players.items():
            if player.vpad is not None and not mac.startswith("path:"):
                out[mac] = player.player_index
        return out

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
        # BUG-COOP-BOOT-PRIMARY-DUP-01: o conjunto `want` é keyed por MAC; se o
        # primário ainda não resolveu o MAC (`primary_uniq` None no boot/restart
        # com controles já plugados → fallback "path:"), não há como excluí-lo de
        # `want` e um secundário nasceria para o PRÓPRIO controle do P1 (input
        # DOBRADO até o próximo sync ~2s). Adia enquanto não há MAC do primário;
        # `_retry_spawn` garante o re-teste no tick seguinte, sem depender do
        # watch de /dev/input (resolver o MAC não muda os nodes).
        if primary is None or primary.startswith("path:"):
            logger.debug("coop_sync_defer_primary_sem_mac", primary=primary)
            self._retry_spawn = True
            return
        want = {
            mac: str(path)
            for mac, path in discover_dualsense_evdevs().items()
            if mac != primary
        }
        # SPRINT-GAME-RUMBLE-01: a máscara (flavor) do P1 pode ter mudado em
        # runtime (aba Início / perfil xboxdualsense). O vpad de cada
        # secundário nasce com o flavor vigente na criação (`_flavor()`), mas
        # não se repropaga sozinho — sem isto, P2+ ficam presos no flavor antigo
        # (rumble morto e prompts divergentes do P1). Derrubar por mismatch aqui
        # força a recriação com a máscara nova. Só efetiva no ciclo cheio (o
        # `set_gamepad_emulation` chama `sync(force=True)` após trocar o flavor).
        desired_flavor = self._flavor()

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
            elif (
                player.vpad is not None
                and getattr(player.vpad, "flavor", None) != desired_flavor
            ):
                logger.info(
                    "coop_player_flavor_changed",
                    identity=mac,
                    old=getattr(player.vpad, "flavor", None),
                    new=desired_flavor,
                )
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
        `target_uniq=MAC` — targeting via a API por-uniq do backend
        (`set_rumble_for`, PERFIL-01, sem flip do seletor global), com a
        política global de intensidade e o respeito ao rumble fixado já
        embutidos lá. Identidade sem MAC ("path:...") não tem como casar o
        handle → broadcast (limitação documentada; não acontece com DualSense
        real).
        """
        daemon = self._daemon

        def _sink(weak: int, strong: int) -> None:
            from hefesto_dualsense4unix.daemon.subsystems.gamepad import apply_game_rumble

            target = None if identity.startswith("path:") else identity
            apply_game_rumble(daemon, weak, strong, target_uniq=target)

        return _sink

    def _promote_player(self, player: _SecondaryPlayer) -> None:
        """Cria o vpad de um jogador com grab CONFIRMADO. Falha derruba o jogador."""
        from hefesto_dualsense4unix.daemon.subsystems.gamepad import controller_allows_uhid
        from hefesto_dualsense4unix.integrations.virtual_pad import make_virtual_pad

        # SPRINT-UHID-VPAD-01 + VPAD-03: `player_index` não é detalhe — no
        # backend uhid o índice vira o MAC do vpad (02:fe:00:00:00:0N), e MAC
        # repetido faz o probe do 2º jogador em diante morrer com -EEXIST (co-op
        # de 4 reduzido a 1). O blueprint é o canônico embutido (nenhuma leitura
        # do físico): jogador com controle não-DualSense (8BitDo, Pro Controller)
        # também ganha vpad uhid Edge — decisão de produto do VPAD-09
        # (uniformidade, dedup segura e rumble via hidraw para todos). O backend
        # fake veta o uhid (VPAD-08).
        vpad = make_virtual_pad(
            self._flavor(),
            rumble_sink=self._make_player_rumble_sink(player.identity),
            player=player.player_index,
            allow_uhid=controller_allows_uhid(self._daemon),
        )
        if vpad is None:
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
        # DEDUP-04: gatilho "mudança do conjunto de jogadores" — o dedup_ok do
        # launch é POR JOGADOR (um único vpad de co-op degradado em uinput já
        # proíbe o IGNORE), então cada spawn regrava as envs do wrapper.
        self._materialize_launch_env()

    def _materialize_launch_env(self) -> None:
        """Regrava as envs do wrapper hefesto-launch (best-effort, DEDUP-04)."""
        with contextlib.suppress(Exception):
            from hefesto_dualsense4unix.daemon.launch_env import (
                materialize_launch_env,
            )

            materialize_launch_env(self._daemon)

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
        # DEDUP-04: o conjunto de jogadores mudou — regrava as envs do wrapper.
        self._materialize_launch_env()
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

        Decisão (documentada): o perfil aplica player-LEDs por broadcast
        (`apply_output_defaults`/`set_player_leds`) e o backend guarda o
        último padrão pedido no DEFAULT do estado desejado para re-afirmá-lo
        em reconexões. PERFIL-01: `_desired` é a property de compatibilidade
        do backend → `_desired_default` (o padrão broadcast, exatamente o que
        este revert precisa); overrides por-controle são assunto do
        PERFIL-06 (revert por-uniq). Ler esse valor é a forma mais simples e
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


def resolve_player_numbers(
    daemon: DaemonProtocol, controllers: Sequence[Mapping[str, object]]
) -> list[int | None]:
    """Número do jogador que o JOGO vê, para cada controle de `controllers`.

    LEIGO-01b: a fonte do número é o daemon, nunca a posição na lista. `None`
    significa "este controle não é um jogador agora" e a UI simplesmente não
    mostra número — melhor calar que mentir. Acontece em três casos:

    - sem gamepad virtual (modo desktop/nativo): não existe jogador — o controle
      mexe no PC ou fala direto com o jogo;
    - controle desconectado;
    - co-op ligado mas o jogador ainda não foi promovido (aguardando o grab), ou
      controle sem MAC para casar.

    Com o gamepad ligado e o co-op DESLIGADO todos os controles conectados são o
    jogador 1 — é literalmente o que o jogo vê (um vpad só, alimentado pelo
    primário). Função de leitura pura: não toca no estado do co-op.
    """
    if getattr(daemon, "_gamepad_device", None) is None:
        return [None] * len(controllers)
    connected = [bool(c.get("connected")) for c in controllers]
    coop_on = bool(getattr(getattr(daemon, "config", None), "coop_enabled", False))
    manager = getattr(daemon, "_coop_manager", None)
    if not coop_on or manager is None:
        return [1 if ok else None for ok in connected]
    index_by_mac = manager.player_indexes()
    out: list[int | None] = []
    for ctrl, ok in zip(controllers, connected, strict=True):
        uniq = ctrl.get("uniq")
        number = index_by_mac.get(uniq) if ok and isinstance(uniq, str) else None
        # Blindagem de serialização (mesma do `_as_str_or_none` do state_full):
        # com o daemon dublado por MagicMock em teste, `player_indexes()` devolve
        # um mock — que estoura no json.dumps do servidor IPC. Só int real passa.
        out.append(
            number if isinstance(number, int) and not isinstance(number, bool) else None
        )
    return out


def get_coop_manager(daemon: DaemonProtocol) -> CoopManager:
    """Retorna o `CoopManager` do daemon, criando-o sob demanda (lazy)."""
    manager = getattr(daemon, "_coop_manager", None)
    if manager is None:
        manager = CoopManager(daemon)
        daemon._coop_manager = manager
    return manager


__all__ = [
    "CoopManager",
    "get_coop_manager",
    "player_led_pattern",
    "resolve_player_numbers",
]
