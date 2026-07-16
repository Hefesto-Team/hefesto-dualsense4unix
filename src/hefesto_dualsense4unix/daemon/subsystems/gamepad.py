"""Subsystem Gamepad — gamepad virtual (DualSense/Xbox).

FEAT-DSX-GAMEPAD-FLAVOR-01. Integra o bridge — antes um processo CLI avulso
(`emulate xbox360`) que abria um SEGUNDO leitor do mesmo controle e causava
input duplicado/perdido — ao daemon como subsystem. Agora há UM leitor evdev
(o do daemon) que faz fan-out para mouse/teclado/gamepad.

Política:
  - **Mutuamente exclusivo com a emulação de mouse**: ligar o gamepad desliga o
    mouse (jogar = o controle vai pro jogo, não pro cursor do desktop). O poll
    loop, quando o gamepad está ativo, NÃO despacha mouse/teclado.
  - **Máscara (flavor)**: `dualsense` (prompts PlayStation) ou `xbox` (fallback
    p/ jogos XInput-only). Quem escolhe o BACKEND por trás da máscara (uhid ou
    uinput) é `integrations/virtual_pad.make_virtual_pad`, com o fallback e o
    motivo logado num lugar só — este subsystem não sabe em qual está.
  - **Grab do controle físico** (best-effort): enquanto o gamepad virtual está
    ativo, o daemon faz EVIOCGRAB no evdev do controle real para o jogo enxergar
    SÓ o device virtual (senão veria o controle cru + o virtual = input dobrado,
    BUG-DSX-GAMEPAD-DOUBLE-INPUT-01). Liberado ao desligar.
  - **Persistência**: liga/desliga + flavor sobrevivem a restart/reboot via
    `utils.session` (igual ao mouse).
  - **Force-feedback do jogo** (FEAT-VPAD-FF-PASSTHROUGH-01): o vpad do P1
    nasce com um `rumble_sink` que devolve o rumble pedido pelo JOGO ao
    controle físico PRIMÁRIO, passando pela mesma política global de
    intensidade do reassert. `dispatch_gamepad` bombeia o FF a cada tick.
"""
from __future__ import annotations

import contextlib
import time
from collections.abc import Callable
from typing import TYPE_CHECKING, Any, Literal

from hefesto_dualsense4unix.utils.logging_config import get_logger

if TYPE_CHECKING:
    from hefesto_dualsense4unix.daemon.lifecycle import DaemonConfig
    from hefesto_dualsense4unix.daemon.protocols import DaemonProtocol
    from hefesto_dualsense4unix.integrations.virtual_pad import VirtualPad

logger = get_logger(__name__)

#: VPAD-01/VPAD-02: cooldown (s) COMPARTILHADO entre as duas bordas de rebackend
#: do vpad do P1 (uinput→uhid): a promoção do hotplug (`reconnect_loop`) e o
#: "botão de força" da GUI (re-selecionar DualSense). O precheck
#: `uhid_available()` pega o uhid quebrado ANTES do device existir (nó ausente,
#: sem ACL); não pega o que aceita o CREATE2 e nunca faz bind (kernel sem
#: `hid_playstation`, MAC duplicado). Sem a trava, cada reconexão BT (frequente
#: nesta máquina) ou clique repetido na GUI derrubaria e recriaria o vpad
#: uinput que FUNCIONA — input drop em loop no meio do jogo. O apply de
#: perfil/autoswitch nem chega ao cooldown: o latch do BT-04(b) veta a promoção
#: por origem automática em `_deve_promover_backend`.
REBACKEND_COOLDOWN_SEC = 30.0


class GamepadSubsystem:
    """Subsystem que gerencia o gamepad virtual. Espelha MouseSubsystem."""

    name = "gamepad"

    async def start(self, ctx: Any) -> None:
        """Cria o device virtual se gamepad_emulation_enabled=True.

        Idempotente: retorna sem erro se já existe. Lê o flavor da config.
        DEDUP-04: materializa o `launch_env/` também quando a emulação está
        DESLIGADA no boot — sem isso o wrapper leria um `default.env` rançoso
        da sessão anterior (ex.: com IGNORE de um vpad que não existe mais).
        O ramo LIGADO cobre os dois desfechos: sucesso e falha total do start
        regravam o arquivo dentro de `start_gamepad_emulation` — TODO boot
        reescreve o launch_env com o estado real.
        """
        cfg = ctx.config
        daemon = getattr(ctx, "daemon", ctx)
        if not getattr(cfg, "gamepad_emulation_enabled", False):
            _materialize_launch_env(daemon)
            return
        start_gamepad_emulation(daemon, flavor=getattr(cfg, "gamepad_flavor", None))

    async def stop(self) -> None:  # pragma: no cover - simetria de protocolo
        # O teardown real fica a cargo de stop_gamepad_emulation no shutdown do
        # daemon (que tem a referência ao device). Aqui é no-op seguro.
        return

    def is_enabled(self, config: DaemonConfig) -> bool:
        return bool(getattr(config, "gamepad_emulation_enabled", False))


def _materialize_launch_env(daemon: DaemonProtocol) -> None:
    """Regrava as envs de launch do wrapper (DEDUP-04) — sempre best-effort.

    Chamado nas bordas de transição do vpad (start/stop cobrem troca de
    máscara, promoção uhid<->uinput e liga/desliga por perfil). NUNCA pode
    derrubar a emulação: a falha vira log e o wrapper degrada sozinho.
    """
    with contextlib.suppress(Exception):
        from hefesto_dualsense4unix.daemon.launch_env import materialize_launch_env

        materialize_launch_env(daemon)


def _set_controller_grab(daemon: DaemonProtocol, grab: bool) -> None:
    """Grab/ungrab do evdev do controle físico, com resultado OBSERVÁVEL.

    Sem isso, o jogo veria o controle cru (js0) + o virtual = input dobrado. O
    grab faz o daemon ser o leitor exclusivo do evdev real (ele já é o leitor),
    escondendo o controle cru dos clientes evdev (SDL2). Nunca propaga exceção:
    em FAKE mode / sem device / sem suporte, o gamepad ainda funciona. Falha de
    EVIOCGRAB deixa de ser silenciosa (BUG-COOP-GRAB-SILENT-FAIL-01): loga
    warning e conta no store — a GUI/doctor podem apontar "input dobrado".
    """
    controller = getattr(daemon, "controller", None)
    evdev = getattr(controller, "_evdev", None)
    setter = getattr(evdev, "set_grab", None)
    if setter is None:
        return
    with contextlib.suppress(Exception):
        ok = setter(grab)
        state = getattr(evdev, "grab_state", None)
        logger.info("gamepad_controller_grab", grab=grab, ok=ok, state=state)
        if grab and ok is False:
            store = getattr(daemon, "store", None)
            if store is not None:
                with contextlib.suppress(Exception):
                    store.bump("gamepad.grab.failed")


def _game_rumble_mult(daemon: DaemonProtocol, now: float) -> float:
    """Multiplicador da política global de rumble para o rumble do JOGO.

    FEAT-VPAD-FF-PASSTHROUGH-01: o FF do vpad passa pela MESMA política
    (economia/balanceado/max/auto/custom) do slider "Intensidade global" —
    espelho fiel de `subsystems.rumble.reassert_rumble` (bateria do snapshot
    do store + `_effective_mult` com o estado de debounce compartilhado do
    daemon). Duplicado aqui de propósito: o reassert é do caminho do rumble
    FIXADO e este é do rumble do jogo; a fonte canônica do cálculo segue
    sendo `core.rumble._effective_mult`.
    """
    from hefesto_dualsense4unix.core.rumble import _effective_mult
    from hefesto_dualsense4unix.daemon.subsystems.rumble import AUTO_DEBOUNCE_SEC

    battery_pct = 50  # fallback neutro (igual ao reassert)
    try:
        ctrl = daemon.store.snapshot().controller
        if ctrl is not None and ctrl.battery_pct is not None:
            battery_pct = int(ctrl.battery_pct)
    except Exception:
        logger.debug("game_rumble_state_read_fallback", exc_info=True)
    mult, daemon._last_auto_mult, daemon._last_auto_change_at = _effective_mult(
        config=daemon.config,
        battery_pct=battery_pct,
        now=now,
        last_auto_mult=daemon._last_auto_mult,
        last_auto_change_at=daemon._last_auto_change_at,
        auto_debounce_sec=AUTO_DEBOUNCE_SEC,
    )
    return mult


def _resolve_output_index(controller: Any, uniq: str) -> int | None:
    """Posição do controle de MAC `uniq` em `describe_controllers`, ou None.

    É o mesmo índice que `set_output_target` espera
    (FEAT-DSX-CONTROLLER-SELECTOR-01). None = backend sem introspecção
    (ex.: FakeController) ou controle não encontrado.
    """
    describe = getattr(controller, "describe_controllers", None)
    if not callable(describe):
        return None
    try:
        for entry in describe():
            if entry.get("uniq") == uniq:
                index = entry.get("index")
                return index if isinstance(index, int) else None
    except Exception:
        logger.debug("game_rumble_describe_failed", exc_info=True)
    return None


def apply_game_rumble(
    daemon: DaemonProtocol,
    weak: int,
    strong: int,
    *,
    target_uniq: str | None = None,
) -> None:
    """Aplica no controle FÍSICO o rumble vindo do jogo (FF do vpad).

    FEAT-VPAD-FF-PASSTHROUGH-01. Decisões (documentadas):
      - `rumble_active` FIXADO manual VENCE: com rumble fixado (usuária
        testando os motores pela GUI), o FF do jogo é IGNORADO — o reassert
        de 200ms manteria o valor fixado de qualquer forma; ignorar evita
        briga de escrita HID. Em passthrough (`rumble_active is None`) o
        reassert é no-op e o FF do jogo manda sozinho.
      - A política global de intensidade é aplicada AQUI (mesmo multiplicador
        do reassert) — o slider vale também para o rumble do jogo.
      - `target_uniq` (MAC) mira o controle de UM jogador via o seletor
        público do backend (`set_output_target` por índice, resolvido por
        `describe_controllers`), salvando e restaurando o alvo anterior. O
        bloco todo é síncrono (sem await), então nenhuma outra task do event
        loop intercala um output no alvo trocado. Sem targeting público
        (ex.: FakeController) ou sem MAC, cai no broadcast histórico —
        limitação documentada: TODOS os controles vibram juntos.
    """
    if daemon.config.rumble_active is not None:
        return  # rumble fixado manual vence o FF do jogo
    controller = daemon.controller
    mult = _game_rumble_mult(daemon, time.monotonic())
    weak_eff = max(0, min(255, round(weak * mult)))
    strong_eff = max(0, min(255, round(strong * mult)))

    # Any: métodos de targeting são opcionais no backend (só o PyDualSense os
    # tem; IController/FakeController não) — o gate é o callable() abaixo.
    set_target: Any = getattr(controller, "set_output_target", None)
    get_target: Any = getattr(controller, "get_output_target_index", None)
    index: int | None = None
    if target_uniq is not None and callable(set_target) and callable(get_target):
        index = _resolve_output_index(controller, target_uniq)
    if index is None:
        try:
            controller.set_rumble(weak=weak_eff, strong=strong_eff)
        except Exception as exc:
            logger.warning("game_rumble_failed", err=str(exc))
        return
    previous: int | None = None
    try:
        previous = get_target()
        set_target(index)
        controller.set_rumble(weak=weak_eff, strong=strong_eff)
    except Exception as exc:
        logger.warning("game_rumble_target_failed", err=str(exc), target=target_uniq)
    finally:
        # Restaura o alvo anterior mesmo em falha (o seletor da usuária não
        # pode ficar sequestrado pelo rumble de um jogador).
        with contextlib.suppress(Exception):
            set_target(previous)


def dedup_status(daemon: DaemonProtocol) -> tuple[bool, list[str]]:
    """(dedup_ok, motivos) agregados POR JOGADOR — o guard DEDUP-06.

    `dedup_ok=True` significa: um jogo lançado AGORA com o IGNORE congelado na
    env não deixa NENHUM jogador sem controle utilizável. A agregação é por
    jogador de propósito (exigência da revisão): no co-op cada vpad nasce do
    hidraw daquele controle e cai individualmente em uinput/0ce6 — um único
    jogador degradado com o IGNORE congelado é AQUELE jogador com zero
    controle, e um `dedup_ok` só-do-P1 mentiria.

    Estados:
      - emulação desligada / Modo Nativo: nenhum IGNORE materializado → ok
        (o launch_env já omite o IGNORE nesses estados);
      - máscara xbox: o vpad é uinput 045e POR DESIGN — o IGNORE cirúrgico do
        físico Sony nunca o esconde (invariante VPAD-06) → ok;
      - máscara dualsense: ok SÓ se o vpad do P1 e TODOS os vpads do co-op
        estão em uhid. Motivos: `fallback_motivo` do P1 (ou `sem_uhid`) e
        `jogador_<N>_uinput` por jogador degradado;
      - emulação ligada SEM device (start falhou): `vpad_ausente`.

    Só leitura de atributos — nunca propaga exceção pro `state_full` (getattr
    defensivo em tudo; daemons dublados de teste não têm coop/store).
    """
    cfg = getattr(daemon, "config", None)
    enabled = bool(getattr(cfg, "gamepad_emulation_enabled", False))
    if not enabled:
        return True, []
    with contextlib.suppress(Exception):
        if bool(daemon.is_native_mode()):
            return True, []
    device = getattr(daemon, "_gamepad_device", None)
    if device is None:
        return False, ["vpad_ausente"]
    if getattr(device, "flavor", None) != "dualsense":
        return True, []
    motivos: list[str] = []
    if getattr(device, "backend", None) == "uinput":
        motivo = getattr(device, "fallback_motivo", None)
        motivos.append(motivo if isinstance(motivo, str) and motivo else "sem_uhid")
    coop = getattr(daemon, "_coop_manager", None)
    players = getattr(coop, "_players", None)
    if isinstance(players, dict):
        for player in players.values():
            vpad = getattr(player, "vpad", None)
            if vpad is None or getattr(vpad, "backend", None) != "uinput":
                continue
            indice = getattr(player, "player_index", None)
            rotulo = str(indice) if isinstance(indice, int) else "?"
            motivos.append(f"jogador_{rotulo}_uinput")
    return not motivos, motivos


def controller_allows_uhid(daemon: DaemonProtocol) -> bool:
    """True quando o backend do controle é o real (pydualsense) — uhid liberado.

    VPAD-08: o modo FAKE (`run.sh --fake`, usado em smoke NA MÁQUINA da usuária)
    não pode registrar um DualSense Edge REAL no kernel — a Steam enxergaria um
    controle fantasma. O único backend com `hidraw_path` no repo é o pydualsense
    (`backend_pydualsense.py`); `FakeController`/`IController` não têm o método,
    e essa é a declaração explícita de "sem uhid" que a factory recebe em
    `allow_uhid`. Não confundir com "controle conectado": o blueprint do vpad é
    o canônico embutido (VPAD-03/BT-01) e o uhid sobe mesmo sem físico nenhum —
    este gate é sobre o BACKEND, não sobre o hardware do momento.
    """
    return callable(getattr(daemon.controller, "hidraw_path", None))


def _rebackend_em_cooldown(daemon: DaemonProtocol, now: float) -> bool:
    """True se a última tentativa de rebackend está a menos de um cooldown.

    O carimbo (`daemon._last_rebackend_ts`) é um só para as duas bordas
    (hotplug e re-seleção pela GUI) de propósito: o modo de falha que a trava
    cobre — uhid que aceita o CREATE2 mas nunca faz bind — é o mesmo nos dois
    caminhos, e alternar entre eles não pode burlar o cooldown.
    """
    carimbo = getattr(daemon, "_last_rebackend_ts", float("-inf"))
    return (now - carimbo) < REBACKEND_COOLDOWN_SEC


def upgrade_primary_vpad_to_uhid(daemon: DaemonProtocol) -> bool:
    """Recria em uhid o vpad do P1 que degradou para uinput. True = trocou.

    Pós-VPAD-03/BT-01 o vpad do P1 já NASCE uhid no boot — o blueprint canônico
    embutido não depende de controle conectado, então o caso histórico ("o
    gamepad sobe antes do `controller.connect` e caía no uinput") morreu. Esta
    função virou REDE DE SEGURANÇA: recupera o vpad que caiu no uinput por razão
    transitória (ex.: /dev/uhid ainda sem ACL na primeira sessão pós-install),
    chamada quando o controle conecta (boot em `lifecycle.run`; hotplug tardio
    no `reconnect_loop` — VPAD-01). Conservadora de propósito:

    - só age no vpad do P1 que é uinput com máscara DualSense (a Xbox é uinput
      por design — o `hid_playstation` não faz bind em VID/PID da Microsoft);
    - precheck `uhid_available()` (ressalva do VPAD-01): sem ele, com o uhid
      persistentemente quebrado (permissão do nó, kernel sem `hid_playstation`),
      cada conexão destruiria e recriaria o vpad uinput que ESTÁ funcionando —
      input drop em loop com o jogo aberto;
    - cooldown compartilhado com a re-seleção da GUI (`REBACKEND_COOLDOWN_SEC`):
      o precheck não pega o uhid que aceita o CREATE2 e nunca binda — sem a
      trava, cada reconexão BT viraria o mesmo input drop em loop;
    - backend fake nunca promove (VPAD-08);
    - recria o device, então o jogo aberto PERDE o vpad por um instante. É
      aceitável porque a janela real é a recuperação de uma degradação que já
      tirou a vibração do jogo de qualquer forma.
    """
    from hefesto_dualsense4unix.integrations.uhid_gamepad import (
        UhidDualSense,
        uhid_available,
    )

    device = getattr(daemon, "_gamepad_device", None)
    if device is None or isinstance(device, UhidDualSense):
        return False
    if getattr(device, "flavor", None) != "dualsense":
        return False
    if not controller_allows_uhid(daemon):
        return False  # backend fake: nunca registrar um Edge real (VPAD-08)
    if not uhid_available():
        return False  # uhid segue quebrado: derrubar o uinput seria só input drop
    now = time.monotonic()
    if _rebackend_em_cooldown(daemon, now):
        # A tentativa anterior (desta borda OU da re-seleção na GUI — o
        # carimbo é um só) acabou de recriar o device e voltou ao uinput:
        # insistir agora seria o input drop em loop que a ressalva do
        # VPAD-01 proíbe. Nunca silencioso: o motivo fica no journal.
        logger.info("rebackend_suprimido_por_cooldown", origem="hotplug")
        return False
    daemon._last_rebackend_ts = now

    logger.info("vpad_promovendo_para_uhid", motivo="vpad degradado com uhid disponível")
    # `persist=False`: a preferência não mudou, só o backend. `release_grab=False`:
    # soltar o grab aqui devolveria o controle físico ao jogo no meio da troca.
    stop_gamepad_emulation(daemon, persist=False, release_grab=False)
    return start_gamepad_emulation(daemon, flavor="dualsense")


def make_primary_rumble_sink(daemon: DaemonProtocol) -> Callable[[int, int], None]:
    """Sink de FF do vpad do P1 → rumble físico do controle PRIMÁRIO.

    FEAT-VPAD-FF-PASSTHROUGH-01: o MAC do primário é resolvido NA HORA do
    rumble (`primary_uniq` muda em hotplug); com o co-op ativo isso garante
    que o rumble do P1 não sacode o controle dos outros jogadores. Backend
    sem `primary_uniq` (ex.: FakeController) cai em broadcast.
    """

    def _sink(weak: int, strong: int) -> None:
        uniq = getattr(daemon.controller, "primary_uniq", None)
        apply_game_rumble(
            daemon,
            weak,
            strong,
            target_uniq=uniq if isinstance(uniq, str) and uniq else None,
        )

    return _sink


def _deve_promover_backend(
    daemon: DaemonProtocol,
    existing: Any,
    key: str,
    origin: Literal["manual", "profile"] = "manual",
) -> bool:
    """True quando um apply de flavor IDÊNTICO deve recriar o vpad (VPAD-02).

    Re-selecionar DualSense na GUI é o "botão de força" da promoção
    uinput→uhid: os dois backends respondem flavor 'dualsense', então o
    early-return que comparava SÓ o flavor fazia da re-seleção um no-op — não
    existia caminho pela interface para recuperar um vpad degradado. A
    comparação agora é (flavor, backend), com os MESMOS gates da promoção do
    hotplug — porque perfis/autoswitch reaplicam a emulação a cada troca de
    janela e um apply idêntico não pode recriar o device à toa:

    - backend já uhid (ou máscara xbox, uinput por design) → no-op de verdade;
    - **latch do BT-04(b)**: `origin != "manual"` NUNCA promove — o botão de
      força é gesto da USUÁRIA (1 clique = 1 tentativa). Perfis/autoswitch
      reaplicam a emulação a cada troca de janela; com o uhid quebrado por
      razão estável que o precheck não enxerga (kernel sem `hid_playstation`:
      `uhid_available()` só testa o acesso ao nó), cada apply automático
      pós-cooldown destruiria o vpad uinput que FUNCIONA e pagaria ~0,5 s de
      `wait_for_bind` com o input congelado — input drop periódico indefinido
      no meio do jogo. A recuperação automática que existe é a do hotplug
      (VPAD-01), em borda física de conexão — não em timer de janela;
    - backend fake veta (VPAD-08): recriar daria só OUTRO uinput (churn);
    - `uhid_available()`: com o uhid quebrado, derrubar o uinput que funciona
      seria input drop sem ganho nenhum;
    - cooldown compartilhado com o VPAD-01 (`REBACKEND_COOLDOWN_SEC`): o uhid
      que aceita o CREATE2 mas nunca binda passa pelo precheck — sem a trava,
      cada apply derrubaria o vpad em loop no meio do jogo. Ressalva do
      VPAD-02: esse no-op devolve True (a GUI mostra sucesso), então NÃO pode
      ser mudo — o motivo vai para o journal ("cliquei e nada" tem rastro).
    """
    from hefesto_dualsense4unix.integrations.uhid_gamepad import uhid_available

    if key != "dualsense" or getattr(existing, "backend", None) != "uinput":
        return False
    if origin != "manual":
        # BT-04(b): apply automático (perfil/autoswitch) com vpad degradado é
        # no-op SEMPRE. DEBUG de propósito: o autoswitch flapando reaplicaria
        # a cada troca de janela e um INFO viraria spam no journal; o rastro
        # visível para a usuária é o badge de degradação do VPAD-05.
        logger.debug("rebackend_suprimido_por_origem_automatica", origem=origin)
        return False
    if not controller_allows_uhid(daemon):
        return False  # backend fake: nunca registrar um Edge real (VPAD-08)
    if not uhid_available():
        return False  # uhid segue quebrado: derrubar o uinput seria só input drop
    now = time.monotonic()
    if _rebackend_em_cooldown(daemon, now):
        logger.info("rebackend_suprimido_por_cooldown", origem="reselecao_gui")
        return False
    daemon._last_rebackend_ts = now
    logger.info(
        "vpad_promovendo_para_uhid", motivo="re-seleção da máscara DualSense (VPAD-02)"
    )
    return True


def start_gamepad_emulation(
    daemon: DaemonProtocol,
    flavor: str | None = None,
    *,
    origin: Literal["manual", "profile"] = "manual",
) -> bool:
    """Cria o gamepad virtual com a máscara `flavor`. Idempotente.

    Desliga a emulação de mouse (mútua exclusão) e faz grab do controle real.
    Retorna True se ativo ao final; False se falhou ao iniciar. Idempotência
    por (flavor, backend): apply idêntico com backend saudável é no-op; mesma
    máscara DualSense com backend degradado (uinput) recria em uhid (VPAD-02).
    `origin` vem de `set_gamepad_emulation` (BT-04(b)): só o gesto MANUAL da
    usuária destrava a promoção por apply idêntico — perfil/autoswitch nunca
    recriam o vpad degradado (o latch anti-churn; ver `_deve_promover_backend`).
    """
    from hefesto_dualsense4unix.integrations.uinput_gamepad import normalize_flavor
    from hefesto_dualsense4unix.integrations.virtual_pad import make_virtual_pad

    key = normalize_flavor(
        flavor if flavor is not None else getattr(daemon.config, "gamepad_flavor", None)
    )

    existing = daemon._gamepad_device
    if existing is not None:
        if getattr(existing, "flavor", None) == key and not _deve_promover_backend(
            daemon, existing, key, origin
        ):
            return True
        # Flavor mudou — ou mesma máscara com backend degradado e uhid de
        # volta (VPAD-02): recria sem repersistir/regrab intermediário.
        stop_gamepad_emulation(daemon, persist=False, release_grab=False)

    # Mútua exclusão: o controle vai pro jogo, não pro cursor.
    # HARM-06: `persist=False` — a preferência de mouse da usuária sobrevive ao
    # modo jogo. Gravar "off" aqui fazia o round-trip desktop->gamepad->desktop
    # apagá-la e o controle voltava do jogo sem função nenhuma.
    if getattr(daemon, "_mouse_device", None) is not None:
        from hefesto_dualsense4unix.daemon.subsystems.mouse import stop_mouse_emulation

        stop_mouse_emulation(daemon, persist=False)

    # FEAT-VPAD-FF-PASSTHROUGH-01: o rumble que o JOGO pedir no vpad volta
    # para os motores do controle físico primário.
    # SPRINT-UHID-VPAD-01 + VPAD-03/BT-01: a factory prefere o backend uhid
    # (DualSense com hidraw de verdade = vibração in-game na máscara DualSense)
    # e cai no uinput sozinha quando o uhid não sobe. O blueprint é o canônico
    # embutido: o vpad nasce uhid Edge JÁ NO BOOT, mesmo com o
    # `_safe_start("gamepad")` rodando antes do `controller.connect()` e mesmo
    # sem controle nenhum conectado. `allow_uhid` veta o uhid no backend fake
    # (VPAD-08 — o smoke não pode plantar um Edge real no kernel).
    device: VirtualPad | None = make_virtual_pad(
        key,
        rumble_sink=make_primary_rumble_sink(daemon),
        player=1,
        allow_uhid=controller_allows_uhid(daemon),
    )
    if device is None:
        logger.warning("gamepad_emulation_start_failed", flavor=key)
        # DEDUP-04 (achado HIGH da revisão adversarial da Fase 2): a falha
        # TOTAL do start também é uma transição de estado. Sem regravar aqui,
        # um `default.env` rançoso da sessão anterior (com IGNORE) sobrevive a
        # um daemon que morreu SUJO (SIGKILL/OOM) e voltou sem conseguir subir
        # vpad nenhum (ex.: /dev/uhid E /dev/uinput sem ACL — classe já vista
        # nesta máquina pela ordem das regras udev >=73): daemon VIVO passa no
        # gate do wrapper, o IGNORE esconde o físico e não existe vpad = ZERO
        # controles NO LAUNCH. O `_snapshot` com `_gamepad_device=None` compõe
        # o arquivo seguro (só o preload de shaders).
        _materialize_launch_env(daemon)
        return False

    daemon._gamepad_device = device
    if key == "dualsense" and getattr(device, "backend", None) == "uinput":
        # VPAD-05 — fallback NUNCA silencioso: além do motivo que a factory já
        # logou, o degrau vira contador no store (doctor) e o `state_full` expõe
        # `gamepad_emulation.degraded`/`degraded_motivo` para a GUI. getattr
        # defensivo: daemons dublados em teste não têm store.
        store = getattr(daemon, "store", None)
        if store is not None:
            with contextlib.suppress(Exception):
                store.bump("gamepad.uhid.fallback")
    daemon.config.gamepad_emulation_enabled = True
    daemon.config.gamepad_flavor = key
    _set_controller_grab(daemon, True)
    with contextlib.suppress(Exception):
        from hefesto_dualsense4unix.utils.session import save_gamepad_emulation

        save_gamepad_emulation(True, key)
    # DEDUP-04: gatilho "transição de backend/máscara" da materialização — o
    # wrapper hefesto-launch decide as envs pelo que fica gravado aqui.
    _materialize_launch_env(daemon)
    logger.info("gamepad_emulation_started", flavor=key)
    return True


def stop_gamepad_emulation(
    daemon: DaemonProtocol, *, persist: bool = True, release_grab: bool = True
) -> None:
    """Para e descarta o gamepad virtual. Idempotente.

    `persist=False` e `release_grab=False` são usados na troca de flavor (a
    recriação imediata reaplica ambos).

    HARM-16: zerar os motores é CONSEQUÊNCIA de parar o vpad, e por isso mora
    aqui. Era responsabilidade de cada caller lembrar, e um esqueceu: o
    `set_mouse_emulation(True)` derruba o gamepad pela exclusão mútua e o
    controle ficava vibrando para sempre (em passthrough o reassert do poll loop
    é no-op — ver `zero_motors_on_mode_exit`). Com o zero aqui, um caller novo
    não tem como esquecer. Vale também para a troca de flavor e o shutdown: o
    dono do FF (o jogo, via vpad) some nos dois, e o motor não pode ficar ligado
    no vácuo — quem tem rumble FIXO pela aba Rumble não é afetado (no-op).
    """
    tinha_device = daemon._gamepad_device is not None
    if tinha_device:
        with contextlib.suppress(Exception):
            daemon._gamepad_device.stop()
        daemon._gamepad_device = None
    # Sem device (ex.: falha no start) o resto ainda roda: config/flag/grab
    # coerentes valem em qualquer caso.
    daemon.config.gamepad_emulation_enabled = False
    if release_grab:
        _set_controller_grab(daemon, False)
    if persist:
        with contextlib.suppress(Exception):
            from hefesto_dualsense4unix.utils.session import save_gamepad_emulation

            save_gamepad_emulation(False)
    from hefesto_dualsense4unix.daemon.subsystems.rumble import zero_motors_on_mode_exit

    zero_motors_on_mode_exit(daemon)
    # DEDUP-04: sem vpad o wrapper não pode mais anunciar IGNORE — regrava as
    # envs de launch com o estado real (o `persist=False` da troca de flavor
    # regrava de novo no start seguinte; escrever 2x é barato e idempotente).
    _materialize_launch_env(daemon)
    if tinha_device:
        logger.info("gamepad_emulation_stopped")


def dispatch_gamepad(
    daemon: DaemonProtocol, state: Any, buttons_pressed: frozenset[str]
) -> None:
    """Repassa o estado do controle ao gamepad virtual.

    Chamado pelo poll loop a cada tick quando _gamepad_device != None.
    Não relança exceções — falhas viram warning.
    """
    device = daemon._gamepad_device
    if device is None:
        return
    try:
        device.forward_analog(
            lx=state.raw_lx,
            ly=state.raw_ly,
            rx=state.raw_rx,
            ry=state.raw_ry,
            l2=state.l2_raw,
            r2=state.r2_raw,
        )
        device.forward_buttons(buttons_pressed)
        # FEAT-VPAD-FF-PASSTHROUGH-01: drena o FF (rumble do jogo) do vpad e
        # repassa ao controle físico. getattr defensivo: fakes/devices sem
        # pump_ff degradam sem crash.
        pump = getattr(device, "pump_ff", None)
        if pump is not None:
            pump()
    except Exception as exc:
        logger.warning("gamepad_dispatch_failed", err=str(exc))


__all__ = [
    "REBACKEND_COOLDOWN_SEC",
    "GamepadSubsystem",
    "apply_game_rumble",
    "dedup_status",
    "dispatch_gamepad",
    "make_primary_rumble_sink",
    "start_gamepad_emulation",
    "stop_gamepad_emulation",
    "upgrade_primary_vpad_to_uhid",
]
