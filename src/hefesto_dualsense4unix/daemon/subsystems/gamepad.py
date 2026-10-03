"""Subsystem Gamepad — gamepad virtual (DualSense/Xbox).

FEAT-DSX-GAMEPAD-FLAVOR-01. Integra o bridge — antes um processo CLI avulso
(`emulate xbox360`) que abria um SEGUNDO leitor do mesmo controle e causava
input duplicado/perdido — ao daemon como subsystem. Agora há UM leitor evdev
(o do daemon) que faz fan-out para mouse/teclado/gamepad.

Política:
  - **Mutuamente exclusivo com a emulação de mouse**: ligar o gamepad desliga o
    mouse (jogar = o controle vai pro jogo, não pro cursor do desktop). O poll
    loop, quando o gamepad está ativo, NÃO despacha mouse/teclado.
  - **Máscara (flavor)**: `dualsense`, `nintendo` (Switch Pro, 07/09/2026) ou `xbox` (fallback
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
  - **Um controle físico = UM dispositivo de jogo** (JOGO-01): a allowlist do
    Steam Input escolhe QUAL dispositivo o jogo enxerga, nunca QUANTOS.
  - **A marca esconde o FÍSICO; ela não tira o Hefesto da frente**
    (ESCONDER-EM-VEZ-DE-SAIR-01, 09/08/2026 — decisão dela). Um controle
    duplicado se cura por dois lados: escondendo o virtual (o produto saindo de
    cena) ou escondendo o físico (o produto ficando). O caminho escolhido é o
    segundo, e o mecanismo é o MESMO na direção contrária — o `hide` do broker
    de hidraw, que é o estado canônico desta casa desde sempre.

    NOTA DATADA — o que morreu aqui em 09/08, e a medição que o matou: até esta
    data a exceção soltava o grab, mandava o broker `restore_all` e **suspendia
    os gamepads virtuais** (`suspend_vpads_for_steam_input`). Curava o duplicado
    com UM controle e derrubava o jogador 2 junto, porque o jogador 2 **é** um
    gamepad virtual — `coop_derrubado_pela_excecao_steam_input`, vinte
    ocorrências no journal dela em 08/08. O raciocínio antigo não estava errado
    sobre o duplicado; estava errado sobre o preço, que ninguém tinha declarado.
    As funções da suspensão saíram em 02/10/2026 (O-CODIGO-SEM-CHAMADOR-LIGA-OU-SAI-01):
    sem chamador desde 09/08, o flag que elas armavam nunca podia ser verdade.
  - **A exceção mexe na ENTRADA, e só nela** (NOTA DATADA, 07/08/2026): a casa
    dizia *"o Hefesto sai da frente"*, e a medição dela de 06/08
    (a sprint `CONTROLE-SONY-MEDIDO-01`,
    seção *A INVERSÃO*, grau MEDIDO) mostrou que a frase é meia verdade.
    **Nenhum caminho fecha o handle de saída**: os chamadores de
    `steam_input_excecao_ativa` estão todos NESTE arquivo, nenhum em `core/`, e
    por isso lightbar, gatilhos, vibração e LED de jogador seguem sendo
    escritos no físico durante a exceção inteira. Com o Mullet Mad Jack aberto,
    os gatilhos dela seguraram duros e o vermelho dela ficou. Com a inversão de
    09/08 isso deixou de ser meia verdade e virou verdade inteira: a entrada
    também continua sendo do Hefesto.
"""
from __future__ import annotations

import contextlib
import time
from collections.abc import Callable
from typing import TYPE_CHECKING, Any, Literal

from hefesto_dualsense4unix.profiles.schema import MOTOR_PCT_PADRAO
from hefesto_dualsense4unix.utils.logging_config import get_logger

if TYPE_CHECKING:
    from hefesto_dualsense4unix.daemon.lifecycle import DaemonConfig
    from hefesto_dualsense4unix.daemon.protocols import DaemonProtocol
    from hefesto_dualsense4unix.integrations.virtual_pad import VirtualPad

logger = get_logger(__name__)

#: "botão de força" da GUI (re-selecionar DualSense). O precheck
REBACKEND_COOLDOWN_SEC = 30.0

LAUNCH_RECONCILE_INTERVAL_SEC = 1.0


EMU_APLICADO = "aplicado"
EMU_JA_ESTAVA = "ja_estava"
EMU_BLOQUEADO_POR_JOGO = "bloqueado_por_jogo"
EMU_RECUSADO_STEAM_INPUT = "recusado_steam_input"
EMU_FALHOU = "falhou"
EMU_DESLIGADO = "desligado"

DESFECHOS_EMULACAO_ATIVA = frozenset(
    {EMU_APLICADO, EMU_JA_ESTAVA, EMU_BLOQUEADO_POR_JOGO}
)

#:   - ``"gesto_de_perfil"`` — ela ATIVOU um perfil na mão (`profile.switch` da
ORIGENS_GESTO_DELA = frozenset({"manual", "gesto_de_perfil"})

ORIGENS_QUE_PASSAM_COM_O_JOGO: dict[str, str] = {
    "manual": "D-A-MASCARA-POR-CONTROLE-VALE-NO-APLICAR",
    "gesto_de_perfil": "D-A-MASCARA-POR-CONTROLE-VALE-NO-APLICAR",
    "ordem_do_coop": "D-2309-FORA-DE-ORDEM-SE-RECRIA-NA-HORA",
}

OrigemEmulacao = Literal["manual", "profile", "gesto_de_perfil"]


class GamepadSubsystem:
    """Subsystem que gerencia o gamepad virtual. Espelha MouseSubsystem."""

    name = "gamepad"

    async def start(self, ctx: Any) -> None:
        """Cria o device virtual se gamepad_emulation_enabled=True."""
        cfg = ctx.config
        daemon = getattr(ctx, "daemon", ctx)
        if not getattr(cfg, "gamepad_emulation_enabled", False):
            _materialize_launch_env(daemon)
            return
        start_gamepad_emulation(
            daemon,
            flavor=getattr(cfg, "gamepad_flavor", None),
            origin="profile",
            caminho=getattr(daemon, "_caminho_do_boot", None),
        )

    async def stop(self) -> None:  # pragma: no cover - simetria de protocolo
        return

    def is_enabled(self, config: DaemonConfig) -> bool:
        return bool(getattr(config, "gamepad_emulation_enabled", False))


def _materialize_launch_env(daemon: DaemonProtocol) -> None:
    """Regrava as envs de launch do wrapper (DEDUP-04) — sempre best-effort."""
    with contextlib.suppress(Exception):
        from hefesto_dualsense4unix.daemon.launch_env import (
            armar_rematerializacao,
            materialize_launch_env,
        )

        materialize_launch_env(daemon)
        armar_rematerializacao(daemon, motivo="borda de vpad do P1")


def _set_evdev_grab(daemon: DaemonProtocol, grab: bool) -> None:
    """Só o EVIOCGRAB do evdev físico, com resultado OBSERVÁVEL."""
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


def _set_controller_grab(daemon: DaemonProtocol, grab: bool) -> None:
    """Grab/ungrab do evdev do controle físico + hide/restore do hidraw."""
    _set_evdev_grab(daemon, grab)
    _broker_sync_grab(daemon, grab)


def _broker_sync_grab(daemon: DaemonProtocol, grab: bool) -> None:
    """Hide/restore do hidraw do físico colado ao EVIOCGRAB (BROKER-01)."""
    with contextlib.suppress(Exception):
        hidraw_fn = getattr(getattr(daemon, "controller", None), "hidraw_path", None)
        if not callable(hidraw_fn):
            return
        from hefesto_dualsense4unix.integrations.hidraw_broker_client import (
            broker_call_nonblocking,
            broker_client_for,
        )

        client = broker_client_for(daemon)
        if grab:
            if daemon.is_native_mode():
                return
            # o hidraw para entregar o DualSense pela API dela"*. O raciocínio
            node = hidraw_fn()
            if isinstance(node, str) and node:
                broker_call_nonblocking(daemon, lambda: client.hide(node))
        elif isinstance(node := hidraw_fn(), str) and node:
            broker_call_nonblocking(daemon, lambda: client.restore(node))


GRAB_AVISO_A_CADA: int = 30


def reconciliar_grab_do_primario(daemon: DaemonProtocol) -> bool:
    """Retoma o `EVIOCGRAB` do primário quando ele ficou `failed`."""
    if not grab_do_primario_dobrado(daemon):
        return False
    evdev = getattr(getattr(daemon, "controller", None), "_evdev", None)
    setter = getattr(evdev, "set_grab", None)
    if not callable(setter):
        return False
    with contextlib.suppress(Exception):
        if daemon.is_native_mode():
            return False
    with contextlib.suppress(Exception):
        setter(True)
    estado = getattr(evdev, "grab_state", None)
    store = getattr(daemon, "store", None)
    if estado == "held":
        tentativas = _grab_falhas(daemon)
        _grab_falhas_set(daemon, 0)
        logger.info("gamepad_grab_recuperado", tentativas=tentativas)
        if store is not None:
            with contextlib.suppress(Exception):
                store.bump("gamepad.grab.recovered")
        return True
    if estado == "pending":
        _grab_falhas_set(daemon, 0)
        return False
    falhas = _grab_falhas(daemon) + 1
    _grab_falhas_set(daemon, falhas)
    if store is not None:
        with contextlib.suppress(Exception):
            store.bump("gamepad.grab.retry_failed")
    if falhas == 1 or falhas % GRAB_AVISO_A_CADA == 0:
        logger.warning(
            "gamepad_grab_dobrado_persiste",
            tentativas=falhas,
            path=str(getattr(evdev, "_device_path", None)),
            hint="EVIOCGRAB recusado por outro processo; o P1 chega DOBRADO no jogo",
        )
    return False


def _grab_falhas(daemon: Any) -> int:
    """Quantas retomadas seguidas do grab do primário já falharam."""
    n = getattr(daemon, "_grab_retry_falhas", 0)
    return n if isinstance(n, int) else 0


def _grab_falhas_set(daemon: Any, n: int) -> None:
    with contextlib.suppress(Exception):
        daemon._grab_retry_falhas = n


def grab_do_primario_dobrado(daemon: Any) -> bool:
    """O P1 está chegando DOBRADO no jogo agora? (detecção, GRAB-DOBRADO-01)"""
    evdev = getattr(getattr(daemon, "controller", None), "_evdev", None)
    if getattr(evdev, "grab_state", None) != "failed":
        return False
    if not getattr(getattr(daemon, "config", None), "gamepad_emulation_enabled", False):
        return False
    return _vpad_vivo(daemon)


def steam_input_excecao_ativa(daemon: Any) -> bool:
    """True enquanto a exceção de Steam Input por appid estiver valendo (R-06)."""
    return bool(getattr(daemon, "_steam_input_excecao", False))


def sync_steam_input_exception(
    daemon: DaemonProtocol, *, now: float | None = None
) -> bool:
    """Liga/desliga a exceção de Steam Input por appid. True = ativa (R-06).

    O que a marca do Steam Input faz, desde 09/08/2026
    -------------------------------------------------
    **Esconde o controle FÍSICO do jogo marcado e mantém os virtuais de pé**
    (ESCONDER-EM-VEZ-DE-SAIR-01, decisão dela). O jogo enxerga um dispositivo
    por controle — o do Hefesto —, e cor, gatilhos, vibração e numeração
    continuam sendo nossos. É o mesmo estado canônico de qualquer outro jogo,
    reforçado na borda de entrada por `esconder_o_fisico_para_o_jogo`.

    NOTA DATADA — o que esta função fazia até 08/08, e por que morreu
    ----------------------------------------------------------------
    Ela era o "Modo Nativo por appid": na borda de entrada soltava o grab,
    pedia `restore_all` ao broker e **suspendia os gamepads virtuais**; na
    saída, devolvia tudo. Cada peça tinha medição por trás e nenhuma delas era
    boba:

    - **R-06 (23/07)** — a allowlist era INERTE: o daemon grabava e escondia o
      hidraw, e o jogo cuja via oficial de DualSense é a API Steamworks não
      achava controle nenhum da Sony;
    - **JOGO-01 (25/07)** — expor o físico COM o vpad de pé é o duplicado: o
      Mullet Mad Jack enumerava js0=vpad e js2=físico e repartia os dois entre
      dois jogadores. Daí a suspensão do vpad.

    O que ninguém tinha declarado é o preço, e ele foi MEDIDO na máquina dela em
    08/08: **o jogador 2 é um gamepad virtual.** Derrubar os virtuais para curar
    o duplicado do jogador 1 derruba o jogador 2 junto —
    `coop_derrubado_pela_excecao_steam_input`, vinte ocorrências num dia.

    A decisão dela fecha a conta pelo outro lado: *"a allowlist do Steam Input
    NÃO tira o Hefesto da frente"*. O duplicado tem duas curas — esconder o
    virtual ou esconder o físico — e a segunda custa o jogador 2, a primeira
    não. O mecanismo é o mesmo `hide`/`restore` do broker, na direção contrária.

    Só age nas BORDAS (o flag em memória guarda o estado anterior): sem borda,
    a função é uma comparação e nada de I/O de grab/broker.
    """
    from hefesto_dualsense4unix.daemon.launch_env import steam_input_exception_appid

    appid = steam_input_exception_appid(daemon, now=now)
    ativa = appid is not None
    anterior = steam_input_excecao_ativa(daemon)
    if ativa == anterior:
        return ativa
    daemon._steam_input_excecao = ativa  # type: ignore[attr-defined]
    if ativa:
        logger.info("steam_input_excecao_ativada", appid=appid)
        esconder_o_fisico_para_o_jogo(daemon, appid=appid)
        return True
    logger.info("steam_input_excecao_encerrada")
    if daemon.is_native_mode():
        return False
    if not getattr(daemon.config, "gamepad_emulation_enabled", False):
        return False
    if not _vpad_vivo(daemon):
        return False
    _set_evdev_grab(daemon, True)
    with contextlib.suppress(Exception):
        rehide_physical_hidraw(daemon)
    return False


def esconder_o_fisico_para_o_jogo(
    daemon: DaemonProtocol, *, appid: int | None = None
) -> bool:
    """Borda de ENTRADA da marca: garante o físico escondido e os virtuais de pé."""
    if daemon.is_native_mode():
        logger.info("steam_input_fisico_nao_escondido", appid=appid, motivo="modo_nativo")
        return False
    if not getattr(daemon.config, "gamepad_emulation_enabled", False):
        logger.info(
            "steam_input_fisico_nao_escondido", appid=appid, motivo="emulacao_desligada"
        )
        return False
    if not _vpad_vivo(daemon):
        logger.info(
            "steam_input_fisico_nao_escondido", appid=appid, motivo="sem_vpad_vivo"
        )
        return False
    _set_evdev_grab(daemon, True)
    with contextlib.suppress(Exception):
        from hefesto_dualsense4unix.integrations.hidraw_broker_client import (
            broker_call_nonblocking,
        )

        broker_call_nonblocking(daemon, lambda: rehide_physical_hidraw(daemon))
    _materialize_launch_env(daemon)
    logger.info("steam_input_fisico_escondido", appid=appid)
    return True


def _daemon_parando(daemon: Any) -> bool:
    """True quando o daemon já está em shutdown (tolerante a dublês)."""
    fn = getattr(daemon, "_is_stopping", None)
    if not callable(fn):
        return False
    try:
        return bool(fn())
    except Exception:
        return False


def vpad_vivo(device: Any) -> bool:
    """VIDA de UM objeto vpad, não existência (lição 6/#17 da auditoria)."""
    if device is None:
        return False
    return getattr(device, "_started", None) is not False


def _vpad_vivo(daemon: DaemonProtocol) -> bool:
    """VIDA do vpad do P1 (gate do rehide/hide do primário) — ver `vpad_vivo`."""
    return vpad_vivo(getattr(daemon, "_gamepad_device", None))


def rehide_physical_hidraw(daemon: DaemonProtocol) -> None:
    """Re-hide de TODOS os hidraw físicos com vpad vivo (P1 + jogadores co-op)."""
    if daemon.is_native_mode():
        return
    if not getattr(daemon.config, "gamepad_emulation_enabled", False):
        return
    hidraw_fn = getattr(daemon.controller, "hidraw_path", None)
    if not callable(hidraw_fn):
        return
    nodes: set[str] = set()
    if _vpad_vivo(daemon):
        node = hidraw_fn()
        if isinstance(node, str) and node:
            nodes.add(node)
    coop = getattr(daemon, "_coop_manager", None)
    players = getattr(coop, "_players", None) or {}
    for identity, player in list(players.items()):
        if not vpad_vivo(getattr(player, "vpad", None)) or identity.startswith("path:"):
            continue
        n = hidraw_fn(identity)
        if isinstance(n, str) and n:
            nodes.add(n)
    if not nodes:
        return
    from hefesto_dualsense4unix.integrations.hidraw_broker_client import (
        broker_client_for,
    )

    client = broker_client_for(daemon)
    for n in sorted(nodes):
        client.hide(n)


def _game_rumble_mult(daemon: DaemonProtocol, now: float) -> float:
    """Multiplicador da política global de rumble para o rumble do JOGO."""
    from hefesto_dualsense4unix.core.rumble import _effective_mult
    from hefesto_dualsense4unix.daemon.subsystems.rumble import AUTO_DEBOUNCE_SEC

    battery_pct = 50
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


def _chave_da_peca(uniq: str | None) -> str | None:
    """MAC normalizado do jeito que o perfil chaveia `controllers`, ou `None`."""
    from hefesto_dualsense4unix.core.sysfs_leds import norm_mac

    return norm_mac(uniq)


def _motores_do_perfil_ativo(daemon: Any) -> dict[str, tuple[int, int]]:
    """`{uniq: (forte_pct, fraco_pct)}` do perfil ATIVO, memoizado pelo nome."""
    nome = getattr(getattr(daemon, "store", None), "active_profile", None)
    if not isinstance(nome, str) or not nome:
        nome = None
    selo = _selo_da_maquina_a_cada_segundo()
    cache = getattr(daemon, "_rumble_motores_pct", None)
    if (isinstance(cache, tuple) and len(cache) == 3 and cache[0] == nome
            and cache[2] == selo):
        mapa_cacheado = cache[1]
        if isinstance(mapa_cacheado, dict):
            return mapa_cacheado
    mapa: dict[str, tuple[int, int]] = {}
    try:
        from hefesto_dualsense4unix.profiles.loader import load_profile
        from hefesto_dualsense4unix.profiles.o_padrao_do_computador import (
            o_computador,
            o_que_vale,
        )
        from hefesto_dualsense4unix.profiles.schema import motores_dos_controles

        controles = (
            o_que_vale(load_profile(nome)).controllers
            if nome is not None else o_computador().controles or None
        )
        cru = motores_dos_controles(controles)
        mapa = {
            chave: par
            for uniq, par in cru.items()
            if (chave := _chave_da_peca(uniq)) is not None
        }
    except Exception:
        logger.debug("rumble_motores_perfil_ilegivel", exc_info=True)
        mapa = {}
    with contextlib.suppress(Exception):
        daemon._rumble_motores_pct = (nome, mapa, selo)
    return mapa


_SELO_DA_MAQUINA: tuple[float, Any] = (float("-inf"), None)


def _selo_da_maquina_a_cada_segundo() -> Any:
    """O selo do ``maquina.json``, relido no máximo uma vez por segundo. Nunca levanta."""
    global _SELO_DA_MAQUINA
    agora = time.monotonic()
    quando, selo = _SELO_DA_MAQUINA
    if agora - quando < 1.0:
        return selo
    with contextlib.suppress(Exception):
        from hefesto_dualsense4unix.profiles.o_padrao_do_computador import (
            selo_da_maquina,
        )

        selo = selo_da_maquina()
    _SELO_DA_MAQUINA = (agora, selo)
    return selo


def esquecer_motores_do_perfil(daemon: Any) -> None:
    """Derruba o mapa memoizado das barras — **a linha que faz a barra valer AGORA**."""
    with contextlib.suppress(Exception):
        daemon._rumble_motores_pct = None


def _pcts_dos_motores(daemon: Any, target_uniq: str | None) -> tuple[int, int]:
    """`(forte_pct, fraco_pct)` da peça mirada — `(100, 100)` sem opinião."""
    chave = _chave_da_peca(target_uniq)
    if chave is None:
        return (MOTOR_PCT_PADRAO, MOTOR_PCT_PADRAO)
    par = _motores_do_perfil_ativo(daemon).get(chave)
    if par is None:
        return (MOTOR_PCT_PADRAO, MOTOR_PCT_PADRAO)
    return par


def _mults_por_motor(
    daemon: DaemonProtocol, now: float, target_uniq: str | None
) -> tuple[float, float]:
    """`(mult_fraco, mult_forte)` — o DEGRAU da coluna VEZES a barra de cada motor.

    A CONTA DELA, 04/09/2026, com os números dela:

        efetivo(motor) = degrau x barra(motor)

        degrau 150 %, fraca 100 %, forte 100 %  ->  150 % e 150 %
        degrau 150 %, fraca 100 %, forte  50 %  ->  150 % e  75 %

    **É O ÚNICO LUGAR ONDE A MULTIPLICAÇÃO ACONTECE.** Se ela aparecesse em
    dois, um dos dois envelheceria sozinho — e a barra é justamente o tipo de
    ajuste que só se percebe errado com a mão no plástico.

    E ELA COMPÕE COM O TETO POR CONTROLE em vez de apagá-lo: o teto do card do
    cabo (`08-conexoes`) vira fator por uniq em
    `profiles/manager._controllers_to_rumble_scales` e é aplicado um andar
    ABAIXO, dentro do backend (`_escalar_rumble`, sobre o par já escrito). Os
    dois se multiplicam na ordem degrau → barra → teto, e nenhum come o outro.
    """
    degrau = _game_rumble_mult(daemon, now)
    forte_pct, fraco_pct = _pcts_dos_motores(daemon, target_uniq)
    return (degrau * fraco_pct / 100.0, degrau * forte_pct / 100.0)


def apply_game_rumble(
    daemon: DaemonProtocol,
    weak: int,
    strong: int,
    *,
    target_uniq: str | None = None,
    vpad: Any = None,
) -> tuple[int, int] | None:
    """Aplica no controle FÍSICO o rumble vindo do jogo (FF do vpad).

    Devolve o par (weak, strong) EFETIVO que foi escrito no controle, ou
    ``None`` quando nada foi escrito (rumble fixado pela GUI vencendo, ou
    escrita recusada pelo backend). MOTOR-QUE-NAO-SE-VE-01, 09/08/2026: o
    valor de retorno é o único jeito de o vpad — e por ele a aba Status —
    saber o que chegou aos motores. Entre o pedido do jogo e este par há a
    multiplicação da política de intensidade, e ela era invisível: em
    `economia` (0,3) um pedido de 1 vira ZERO e a tela continuava dizendo
    "vibração chegando". Chamador que ignora o retorno continua correto (era
    o contrato até aqui).

    FEAT-VPAD-FF-PASSTHROUGH-01. Decisões (documentadas):
      - `rumble_active` FIXADO manual VENCE: com rumble fixado (usuária
        testando os motores pela GUI), o FF do jogo é IGNORADO — o reassert
        de 200ms manteria o valor fixado de qualquer forma; ignorar evita
        briga de escrita HID. Em passthrough (`rumble_active is None`) o
        reassert é no-op e o FF do jogo manda sozinho.
      - A política global de intensidade é aplicada AQUI (mesmo multiplicador
        do reassert) — o slider vale também para o rumble do jogo.
      - VIBRACAO-POR-MOTOR-01 (04/09/2026): e o degrau não vai sozinho — cada
        motor leva a SUA barra, `efetivo(motor) = degrau x barra(motor)`. Os
        dois `mult` abaixo saem de :func:`_mults_por_motor`, e por isso `weak`
        e `strong` podem sair com fatores diferentes do MESMO controle: é o
        caso dela, `degrau 150 · fraca 100 · forte 50 → 150 % e 75 %`. Sem
        barra escrita no perfil os dois fatores são o degrau, e o par é
        byte-idêntico ao que era.
      - `target_uniq` (MAC) mira o controle de UM jogador via a API por-uniq
        do backend (`set_rumble_for`, PERFIL-01) — SEM o flip transitório do
        seletor global (`set_output_target`) que existia antes: o flip corria
        com o executor multi-thread (max_workers=2) e, com o estado desejado
        keyed pelo alvo lido na hora, uma escrita da GUI intercalada
        persistiria config no controle errado. O seletor da usuária nunca é
        tocado.
      - BROADCAST-PROIBIDO-01 (24/08/2026): a decisão passou a ser a MESMA dos
        três irmãos deste arquivo (`apply_game_trigger`, `apply_game_lightbar`,
        `apply_game_player_leds`) — `target_uniq` **pedido** (não-`None`) e não
        casado (ou backend sem a API por-uniq) **descarta com log, nunca
        broadcast**: replicar o pulso do jogador 2 nos outros três é o próprio
        defeito que esta invariante existe para proibir. A ressalva que
        continua valendo: `target_uniq is None` **não** é o mesmo caso — um
        backend sem `primary_uniq` (ex.: `FakeController`) ou uma mesa de um
        controle só nunca pediu endereço, e ali broadcast e mira são a mesma
        coisa. A recusa vale só quando um endereço FOI pedido e não casou.
      - NO-MODO-XBOX-TUDO-FUNCIONA-01, parte 4 (29/09/2026): com ``vpad`` o
        pad ``uinput`` (o que só tem os dois motores para o jogo), o par
        efetivo vai também à háptica fina do lugar (:func:`_levar_a_haptica_fina`).
        Quando ela o leva até o controle, os motores do HID ficam em ZERO —
        o bit que pede rumble ao firmware cala a háptica por áudio — e o par
        devolvido é o que chegou pela háptica. Sem ``vpad`` (os chamadores de
        antes) nada muda.
    """
    if daemon.config.rumble_active is not None:
        _levar_a_haptica_fina(daemon, vpad, target_uniq, 0, 0)
        return None
    controller = daemon.controller
    mult_fraco, mult_forte = _mults_por_motor(daemon, time.monotonic(), target_uniq)
    weak_eff = max(0, min(255, round(weak * mult_fraco)))
    strong_eff = max(0, min(255, round(strong * mult_forte)))
    motores = (weak_eff, strong_eff)
    if _levar_a_haptica_fina(
        daemon,
        vpad,
        target_uniq,
        weak_eff,
        strong_eff,
        reaplicar=lambda: apply_game_rumble(
            daemon, weak, strong, target_uniq=target_uniq, vpad=vpad
        ),
    ):
        motores = (0, 0)

    # Any: o targeting por-uniq é opcional no backend (só o PyDualSense o
    rumble_for: Any = getattr(controller, "set_rumble_for", None)
    if target_uniq is not None:
        if callable(rumble_for):
            try:
                if rumble_for(target_uniq, *motores):
                    return (weak_eff, strong_eff)
            except Exception as exc:
                logger.warning("game_rumble_target_failed", err=str(exc), target=target_uniq)
                return None
        logger.debug("game_rumble_sem_alvo_descartado", target=target_uniq)
        return None
    try:
        controller.set_rumble(weak=weak_eff, strong=strong_eff)
    except Exception as exc:
        logger.warning("game_rumble_failed", err=str(exc))
        return None
    return (weak_eff, strong_eff)


def _levar_a_haptica_fina(
    daemon: Any,
    vpad: Any,
    target_uniq: str | None,
    weak: int,
    strong: int,
    *,
    reaplicar: Callable[[], object] | None = None,
) -> bool:
    """O rumble do pad SEM háptica vai à háptica fina do lugar. True = ela leva.

    NO-MODO-XBOX-TUDO-FUNCIONA-01, parte 4, 29/09/2026. Só o pad ``uinput``
    converte: ele é o pad de todo cartão no modo Xbox (o Xbox 360 vestido), e
    o do cartão Xbox ou Nintendo no modo DualSense — o jogo não tem canal de
    háptica nenhum ali, só os dois motores. O pad ``uhid`` é um DualSense para
    o jogo, e o jogo escolhe sozinho entre o rumble e a háptica dele.

    O pad que não converte manda ZERO ao dono: o tocador que tocava o rumble
    daquele controle (o pad que acabou de sair do ``uinput``, o rumble fixado
    pela tela) cala. Sem endereço não há lugar, e nada se pergunta.
    """
    if not isinstance(target_uniq, str) or not target_uniq:
        return False
    alto_falante = getattr(daemon, "_alto_falante_subsystem", None)
    levar = getattr(alto_falante, "levar_o_rumble", None)
    if not callable(levar):
        return False
    converte = getattr(vpad, "backend", None) == "uinput"
    try:
        leva = levar(
            target_uniq,
            weak if converte else 0,
            strong if converte else 0,
            reaplicar=reaplicar if converte else None,
        )
    except Exception as exc:
        logger.debug("haptica_fina_do_rumble_falhou", err=str(exc))
        return False
    return converte and leva is True


def apply_game_trigger(
    daemon: DaemonProtocol,
    side: str,
    block: bytes,
    *,
    target_uniq: str | None = None,
) -> None:
    """Aplica no físico o trigger effect que o JOGO escreveu no vpad (REPLICA-03).

    Sem broadcast de propósito (diferente do rumble): replicar um efeito de
    gatilho em TODOS os controles pintaria o jogador errado. Sem MAC alvo ou
    sem a API por-uniq no backend (FakeController), a réplica é descartada com
    log — nunca degrada para broadcast.
    """
    fn: Any = getattr(daemon.controller, "set_game_trigger_for", None)
    if target_uniq is None or not callable(fn):
        logger.debug("game_trigger_sem_alvo_descartado", target=target_uniq)
        return
    try:
        fn(target_uniq, side, block)
    except Exception as exc:
        logger.warning("game_trigger_failed", err=str(exc), target=target_uniq)


def apply_game_lightbar(
    daemon: DaemonProtocol,
    rgb: tuple[int, int, int],
    *,
    target_uniq: str | None = None,
) -> None:
    """Aplica no físico a cor de lightbar que o JOGO pintou no vpad (REPLICA-03)."""
    fn: Any = getattr(daemon.controller, "set_game_output_for", None)
    if target_uniq is None or not callable(fn):
        logger.debug("game_lightbar_sem_alvo_descartado", target=target_uniq)
        return
    try:
        fn(target_uniq, led=rgb)
    except Exception as exc:
        logger.warning("game_lightbar_failed", err=str(exc), target=target_uniq)


def apply_game_player_leds(
    daemon: DaemonProtocol,
    bits: tuple[bool, bool, bool, bool, bool],
    *,
    target_uniq: str | None = None,
) -> None:
    """Oferece ao físico os player-LEDs que o JOGO acendeu no vpad (REPLICA-03)."""
    if target_uniq is not None:
        _o_numero_que_o_jogo_escreveu(daemon, bits, target_uniq)
    fn: Any = getattr(daemon.controller, "set_game_output_for", None)
    if target_uniq is None or not callable(fn):
        logger.debug("game_player_leds_sem_alvo_descartado", target=target_uniq)
        return
    try:
        fn(target_uniq, player_leds=bits)
    except Exception as exc:
        logger.warning("game_player_leds_failed", err=str(exc), target=target_uniq)


def end_game_output_session(
    daemon: DaemonProtocol, *, target_uniq: str | None = None
) -> None:
    """Fim da sessão uhid do jogador: devolve perfil/paleta/co-op (REPLICA-03)."""
    _esquecer_o_numero_do_jogo(daemon, target_uniq)
    fn: Any = getattr(daemon.controller, "end_game_session_for", None)
    if target_uniq is None or not callable(fn):
        logger.debug("game_session_end_sem_alvo", target=target_uniq)
        return
    try:
        fn(target_uniq)
    except Exception as exc:
        logger.warning("game_session_end_failed", err=str(exc), target=target_uniq)


def make_primary_replica_sinks(daemon: DaemonProtocol) -> dict[str, Any]:
    """Sinks de replicação do vpad do P1 → físico PRIMÁRIO (REPLICA-03).

    Espelho de `make_primary_rumble_sink`: o MAC do primário é resolvido NA
    HORA de cada réplica (`primary_uniq` muda em hotplug). As chaves do dict
    casam com os kwargs de `make_virtual_pad`/`UhidDualSense` de propósito —
    o call site desempacota com `**`.

    O CLOSE encerra a sessão de CADA controle que recebeu réplica, não só o
    primário do INSTANTE do CLOSE: o primário pode ter caído/trocado no BT no
    meio do jogo (reconexão BT é frequente nesta máquina), e a camada GAME
    grudou no controle que RECEBEU a cor — não no primário atual. Encerrar só
    o `primary_uniq` corrente vazaria a camada game no controle original, que
    voltaria como TOPO do merge no reconnect (a mesma writer-war/paleta
    corrompida que o REPLICA-03 mata). Por isso lembramos todo uniq replicado
    na sessão e devolvemos CADA um. Tudo roda na thread de poll (sem lock).
    """

    replicados: set[str] = set()

    def _uniq() -> str | None:
        uniq = getattr(daemon.controller, "primary_uniq", None)
        if isinstance(uniq, str) and uniq:
            replicados.add(uniq)
            return uniq
        return None

    def _session_end() -> None:
        alvos = tuple(replicados)
        replicados.clear()
        for uniq in alvos:
            end_game_output_session(daemon, target_uniq=uniq)

    return {
        "trigger_sink": lambda side, block: apply_game_trigger(
            daemon, side, block, target_uniq=_uniq()
        ),
        "lightbar_sink": lambda r, g, b: apply_game_lightbar(
            daemon, (r, g, b), target_uniq=_uniq()
        ),
        "player_led_sink": lambda bits: apply_game_player_leds(
            daemon, bits, target_uniq=_uniq()
        ),
        "session_end_sink": _session_end,
        **ralos_do_mic(daemon, lambda: _primario_da_hora(daemon)),
    }


def notify_vpad_degradado(
    daemon: DaemonProtocol, *, player: int, motivo: str, indice: int | None = None
) -> None:
    """Anuncia a TRANSIÇÃO "vpad deste jogador nasceu degradado" (BT-03).

    Duas saídas, ambas best-effort e nunca fatais:

    - log estruturado ``vpad_degradado`` — a fonte de verdade nesta máquina é
      o stdout do daemon (roda ``--foreground`` fora do systemd; ver "Precisão
      de linguagem" do sprint BT: nenhum critério pode depender do journal);
    - ``daemon.bus.publish("vpad.degraded", ...)`` — o EventBus é a infra de
      notificação existente (``core/events.py``). O tópico vai como literal
      documentado porque `EventTopic` está fora da fronteira desta frente
      (promover a constante quando `events.py` entrar em escopo); publicar num
      tópico sem assinantes é no-op barato por construção do bus.

    Chamado SÓ na borda de criação degradada (P1 em `start_gamepad_emulation`;
    secundários em `CoopManager._promote_player`) — nunca no `state_full` a
    10 Hz (seria flood, a mesma regra do `dedup_broken` do DEDUP-06).
    """
    # O-NUMERO-DO-JOGADOR-SE-REORGANIZA-NA-HORA-E-O-JOGO-VE-01, cura 2: ``player``
    campos = {"indice": indice} if indice is not None else {}
    logger.warning("vpad_degradado", player=player, motivo=motivo, **campos)
    bus = getattr(daemon, "bus", None)
    if bus is None:
        return
    with contextlib.suppress(Exception):
        bus.publish("vpad.degraded", {"player": player, "motivo": motivo})


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
        `jogador_<N>_uinput` por jogador degradado. NOTA DATADA — PS-L3-MASCARA-01,
        14/09/2026: o uinput do caminho Xbox é ESCOLHA dela, não degradação, e não
        entra (o vpad carrega o caminho em que nasceu, `caminho_do_vpad`);
      - emulação ligada SEM device (start falhou): `vpad_ausente`.

    Só leitura de atributos — nunca propaga exceção pro `state_full` (getattr
    defensivo em tudo; daemons dublados de teste não têm coop/store).
    """
    from hefesto_dualsense4unix.integrations.virtual_pad import motivo_da_degradacao

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
    motivo_do_p1 = motivo_da_degradacao(device)
    if motivo_do_p1 is not None:
        motivos.append(motivo_do_p1)
    coop = getattr(daemon, "_coop_manager", None)
    players = getattr(coop, "_players", None)
    if isinstance(players, dict):
        for player in players.values():
            vpad = getattr(player, "vpad", None)
            if vpad is None or motivo_da_degradacao(vpad) is None:
                continue
            motivos.append(f"jogador_{_rotulo_do_jogador(coop, player)}_uinput")
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


def _autoridade_do_jogo(daemon: Any) -> bool:
    """True SÓ quando o sinal STICKY diz que o jogo tem a autoridade (R-04)."""
    return getattr(daemon, "display_authority", "unknown") == "game"


def _recriacao_bloqueada_por_jogo(
    daemon: DaemonProtocol, *, origin: str, motivo: str
) -> bool:
    """True quando destruir/recriar o vpad AGORA arrancaria o controle do jogo."""
    decisao = ORIGENS_QUE_PASSAM_COM_O_JOGO.get(origin)
    if decisao is not None:
        if _autoridade_do_jogo(daemon):
            logger.info(
                "pad_recriado_com_o_jogo_aberto",
                origem=origin,
                decisao=decisao,
                motivo=motivo,
            )
        return False
    if getattr(daemon, "_pad_travado_pelo_lancamento", None) is not None:
        if not _primeira_vez_no_episodio(daemon, "lancamento"):
            logger.debug(
                "vpad_recriacao_bloqueada_pelo_lancamento_repetida",
                motivo=motivo,
                origem=origin,
            )
        else:
            logger.warning(
                "vpad_recriacao_bloqueada_pelo_lancamento",
                motivo=motivo,
                origem=origin,
            )
        store = getattr(daemon, "store", None)
        if store is not None:
            with contextlib.suppress(Exception):
                store.bump("gamepad.recreate.blocked_by_launch")
        return True
    if not _autoridade_do_jogo(daemon):
        with contextlib.suppress(Exception):
            daemon._bloqueio_recriacao_episodio = None  # type: ignore[attr-defined]
        return False
    if not _primeira_vez_no_episodio(daemon, origin):
        logger.debug(
            "vpad_recriacao_bloqueada_por_jogo_repetida", motivo=motivo, origem=origin
        )
    else:
        logger.warning(
            "vpad_recriacao_bloqueada_por_jogo", motivo=motivo, origem=origin
        )
    store = getattr(daemon, "store", None)
    if store is not None:
        with contextlib.suppress(Exception):
            store.bump("gamepad.recreate.blocked_by_game")
    return True


def _primeira_vez_no_episodio(daemon: Any, chave: str) -> bool:
    """`chave` (uma origem, ou o lançamento) ainda não foi dita neste episódio?"""
    vistos = getattr(daemon, "_bloqueio_recriacao_episodio", None)
    if not isinstance(vistos, set):
        vistos = set()
    if chave in vistos:
        return False
    vistos.add(chave)
    with contextlib.suppress(Exception):
        daemon._bloqueio_recriacao_episodio = vistos
    return True


def _reconciliar_launch(daemon: DaemonProtocol) -> None:
    """Reconciliação de LAUNCH throttada a 1 Hz (R-04 arming + R-06 exceção)."""
    try:
        agora = time.monotonic()
        if agora < getattr(daemon, "_launch_reconcile_next_at", 0.0):
            return
        daemon._launch_reconcile_next_at = (  # type: ignore[attr-defined]
            agora + LAUNCH_RECONCILE_INTERVAL_SEC
        )
    except Exception:
        logger.debug("launch_reconcile_throttle_indisponivel", exc_info=True)
        return
    with contextlib.suppress(Exception):
        from hefesto_dualsense4unix.daemon.launch_env import arm_launch_profile

        arm_launch_profile(daemon)
    with contextlib.suppress(Exception):
        sync_steam_input_exception(daemon)
    with contextlib.suppress(Exception):
        from hefesto_dualsense4unix.daemon.launch_env import (
            rematerializar_se_sossegou,
            vigiar_a_mesa,
        )

        vigiar_a_mesa(daemon)
        rematerializar_se_sossegou(daemon)


def _rebackend_em_cooldown(daemon: DaemonProtocol, now: float) -> bool:
    """True se a última tentativa de rebackend está a menos de um cooldown."""
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

    - só age no vpad do P1 que caiu (`motivo_da_degradacao`): máscara DualSense
      no uinput com o caminho do DualSense. A máscara Xbox é uinput por design
      (o `hid_playstation` não faz bind em VID/PID da Microsoft), e o modo Xbox
      é uinput por escolha dela; o pad renasce no caminho em que nasceu;
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

    VPAD-09 (falha TOTAL): `_gamepad_device is None` com a emulação desejada na
    config = o boot perdeu a corrida da ACL uaccess de /dev/uhid E /dev/uinput
    contra o logind (visto ao vivo em 21/07: daemon de sessão sobe no login,
    logind aplica a ACL instantes depois; sem retry o vpad só voltava com
    restart manual). Aqui a borda de conexão REVIVE a emulação pela factory
    completa (uhid→uinput, flavor da config) — sem precheck `uhid_available()`
    (não há device funcionando para proteger; qualquer backend é melhor que
    nenhum), mas sob o MESMO cooldown (reconexão BT em rajada não vira spam).
    """
    from hefesto_dualsense4unix.integrations.uhid_gamepad import (
        UhidDualSense,
        uhid_available,
    )
    from hefesto_dualsense4unix.integrations.virtual_pad import motivo_da_degradacao

    device = getattr(daemon, "_gamepad_device", None)
    if isinstance(device, UhidDualSense):
        return False
    if not controller_allows_uhid(daemon):
        return False
    if device is None:
        # VPAD-09: sem device NENHUM. Se a emulação está desligada por escolha,
        # não há o que reviver; se está ligada na config, o start do boot
        if not getattr(daemon.config, "gamepad_emulation_enabled", False):
            return False
        now = time.monotonic()
        if _rebackend_em_cooldown(daemon, now):
            logger.info("rebackend_suprimido_por_cooldown", origem="revive")
            return False
        daemon._last_rebackend_ts = now
        logger.info(
            "vpad_revivendo_pos_falha_total",
            flavor=getattr(daemon.config, "gamepad_flavor", None),
        )
        # o start não opina, e o modo que o perfil escolheu voltava ao DualSense.
        return start_gamepad_emulation(
            daemon,
            origin="profile",
            caminho=nomear_o_restart(daemon, "revive_pos_falha_total"),
        )
    if motivo_da_degradacao(device) is None:
        return False
    if not uhid_available():
        return False
    if _recriacao_bloqueada_por_jogo(daemon, origin="hotplug", motivo="promocao_uhid"):
        return False
    now = time.monotonic()
    if _rebackend_em_cooldown(daemon, now):
        logger.info("rebackend_suprimido_por_cooldown", origem="hotplug")
        return False
    daemon._last_rebackend_ts = now

    logger.info("vpad_promovendo_para_uhid", motivo="vpad degradado com uhid disponível")
    stop_gamepad_emulation(daemon, persist=False, release_grab=False)
    return start_gamepad_emulation(
        daemon, origin="profile", caminho=nomear_o_restart(daemon, "promocao_uhid")
    )


def primary_identity(daemon: DaemonProtocol) -> str | None:
    """MAC canônico do controle PRIMÁRIO, ou None (MÁSCARA-POR-JOGADOR-01)."""
    uniq = getattr(getattr(daemon, "controller", None), "primary_uniq", None)
    return uniq if isinstance(uniq, str) and uniq else None


def read_primary_calibration(daemon: DaemonProtocol) -> bytes | None:
    """Feature 0x05 do controle PRIMÁRIO para o vpad do P1 (GYRO-01)."""
    fn: Any = getattr(daemon.controller, "read_calibration", None)
    if not callable(fn):
        return None
    try:
        data = fn()
    except Exception as exc:
        logger.warning("gamepad_calibration_read_failed", err=str(exc))
        return None
    return data if isinstance(data, bytes) else None


def start_motion_reader(daemon: DaemonProtocol, device: Any) -> None:
    """Sobe o espelho de motion do P1 (GYRO-01): hidraw do físico → vpad."""
    stop_motion_reader(daemon)
    if getattr(device, "backend", None) != "uhid":
        return
    hidraw_fn: Any = getattr(daemon.controller, "hidraw_path", None)
    if not callable(hidraw_fn):
        return
    from hefesto_dualsense4unix.core.physical_report_reader import (
        PhysicalReportReader,
    )
    from hefesto_dualsense4unix.integrations.hidraw_broker_client import (
        make_broker_opener,
    )

    def _primary_hidraw() -> str | None:
        try:
            path = hidraw_fn()
        except Exception:
            return None
        return path if isinstance(path, str) else None

    reader = PhysicalReportReader(
        path_provider=_primary_hidraw, vpad=device, opener=make_broker_opener(daemon)
    )
    if not reader.start():  # pragma: no cover - start() atual nunca falha
        return
    daemon._motion_reader = reader
    attach: Any = getattr(daemon.controller, "attach_motion_reader", None)
    if callable(attach):
        with contextlib.suppress(Exception):
            attach(reader)
    logger.info("motion_reader_spawned", player=1)


def stop_motion_reader(daemon: DaemonProtocol) -> None:
    """Para o espelho de motion do P1 (idempotente)."""
    reader = getattr(daemon, "_motion_reader", None)
    if reader is None:
        return
    daemon._motion_reader = None
    detach: Any = getattr(daemon.controller, "attach_motion_reader", None)
    if callable(detach):
        with contextlib.suppress(Exception):
            detach(None)
    with contextlib.suppress(Exception):
        reader.stop()
    logger.info("motion_reader_stopped", player=1)


def anotar_rumble_no_vpad(vpad: Any, efetivo: tuple[int, int] | None) -> None:
    """Anota no vpad o par que FOI AOS MOTORES (MOTOR-QUE-NAO-SE-VE-01)."""
    if efetivo is None or vpad is None:
        return
    anotar = getattr(vpad, "registrar_rumble_no_fisico", None)
    if anotar is None:
        return
    with contextlib.suppress(Exception):
        anotar(efetivo[0], efetivo[1])


def make_primary_rumble_sink(daemon: DaemonProtocol) -> Callable[[int, int], None]:
    """Sink de FF do vpad do P1 → rumble físico do controle PRIMÁRIO."""

    def _sink(weak: int, strong: int) -> None:
        uniq = getattr(daemon.controller, "primary_uniq", None)
        vpad = getattr(daemon, "_gamepad_device", None)
        efetivo = apply_game_rumble(
            daemon,
            weak,
            strong,
            target_uniq=uniq if isinstance(uniq, str) and uniq else None,
            vpad=vpad,
        )
        anotar_rumble_no_vpad(vpad, efetivo)

    return _sink


def _deve_promover_backend(
    daemon: DaemonProtocol,
    existing: Any,
    key: str,
    origin: OrigemEmulacao = "manual",
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
        logger.debug("rebackend_suprimido_por_origem_automatica", origem=origin)
        return False
    if not controller_allows_uhid(daemon):
        return False
    if not uhid_available():
        return False
    now = time.monotonic()
    if _rebackend_em_cooldown(daemon, now):
        logger.info("rebackend_suprimido_por_cooldown", origem="reselecao_gui")
        return False
    daemon._last_rebackend_ts = now
    logger.info(
        "vpad_promovendo_para_uhid", motivo="re-seleção da máscara DualSense (VPAD-02)"
    )
    return True


def _caminho_a_herdar(daemon: DaemonProtocol) -> str | None:
    """De onde um start SEM opinião herda o caminho — e é UM lugar só.

    O-CAMINHO-NAO-VAZA-01, 17/09/2026. A herança é a ESCOLHA DELA
    (`config.gamepad_caminho_global`, o que o boot relê de
    `gamepad_caminho.flag`), nunca o caminho da sessão que está correndo.

    ATÉ 17/09 ESTA RESPOSTA SAÍA DE `config.gamepad_caminho` — o slot da SESSÃO
    —, e era o vazamento inteiro: o `"xbox"` que o perfil do DON'T SCREAM pede
    ficava lá e virava lei sobre os 29 perfis que não opinam. O PRAGMATA, que
    não tem sequer seção `mode`, abria em uinput, e com ele iam embora as dez
    linhas do mapa que só existem no caminho DualSense — a IMU entre elas. A
    queixa dela: *"joguei um jogo com controle por movimento e na hora do vamos
    ver o controle não deu resposta"*.

    É função nomeada, e não uma linha embutida, para a régua poder MORDER o
    ponto exato: `test_o_caminho_nao_vaza_entre_jogos` repõe aqui a leitura
    velha e o laço de produção inteiro roda por cima dela.

    E AGORA NÃO HERDA DE LUGAR NENHUM — CAMINHO-CONTAGIO-01, ponto 2 do escopo
    de 19/09/2026, e é ordem dela:

        *"sim tudo dualsense, tudo ligado mascara dualsense por default mas
        esse vazamento me preocupa"*  <!-- noqa-acento: citação literal dela -->

    A O-CAMINHO-NAO-VAZA-01 mudou a FONTE da herança — do slot da sessão para a
    escolha dela — e o vazamento voltou por outra porta: o `gamepad_caminho.flag`
    é escrito por TODO gesto manual, e o PS + R3 dentro de um jogo é manual.
    Medido em 18/09: um aperto no DON'T SCREAM carimbou `xbox` no arquivo
    global, e **26 dos 29 perfis não têm `mode.caminho`** — herdaram todos, o
    PRAGMATA entre eles, com giroscópio e touchpad fora do jogo.

    **A CURA NÃO É UMA FONTE MELHOR, É NENHUMA FONTE.** Enquanto um start sem
    opinião herdar de qualquer lugar, existe um lugar a envenenar; a terceira
    porta seria achada pela terceira vez. O caminho DualSense é o que tem TODAS
    as features (UHID: giroscópio, acelerômetro e touchpad chegam ao jogo), e é
    o default que a ordem dela de 17/09 já pedia — *"os jogos e perfis tem que
    iniciar com todas as features ativadas por default"*.

    O `gamepad_caminho_global` CONTINUA EXISTINDO e continua sendo escrito: ele
    é o que a tela mostra como escolha dela e o que o `--status` relata. O que
    mudou é que ninguém NASCE dele.

    **DEVOLVER ``None`` É O QUE ENTREGA «TUDO DUALSENSE», E NÃO CRAVAR
    `dualsense`** — medido em 19/09, e a diferença aparece num caso só, que é
    justamente o dela. ``None`` significa *"ninguém escolheu"*, e quem lê
    aplica `virtual_pad.caminho_resolvido`, que responde pela MÁSCARA:

        caminho_resolvido(None, "dualsense")  ->  dualsense   (UHID: tudo ligado)
        caminho_resolvido(None, "xbox")       ->  xbox

    A máscara nasce `dualsense`, então o default É DualSense para todo perfil
    que não opina — que é o PRAGMATA e os outros 25. Cravar `dualsense` aqui
    daria o mesmo resultado nesse caso e um resultado ERRADO no outro: com o
    cartão do P1 em «Xbox 360» (escolha dela, máscara `xbox`), o slot passaria
    a dizer `dualsense` sobre um aparelho que `quer_uhid` mantém em uinput — a
    tela afirmando DualSense sobre um vpad Xbox. É o F7 desta casa, o produto
    dizendo uma coisa e fazendo outra, e foi a premissa de
    `test_com_o_cartao_em_xbox_360_o_chip_acende_o_escolhido_e_nao_a_mascara`
    que o revelou.
    """
    return None


def _ha_jogo_em_foco(daemon: DaemonProtocol) -> bool:
    """Há uma janela de jogo em foco AGORA? — CAMINHO-CONTAGIO-01, 19/09/2026."""
    olhar = getattr(daemon, "_janela_de_jogo_em_foco", None)
    if not callable(olhar):
        return False
    try:
        return bool(olhar())
    except Exception as exc:  # pragma: no cover — detector de janela é frágil
        logger.debug("jogo_em_foco_indisponivel", err=str(exc))
        return False


_O_MESMO_QUE_O_PEDIDO: Any = object()


def _guardar_o_caminho(
    daemon: DaemonProtocol,
    caminho: str | None,
    *,
    origin: OrigemEmulacao,
    da_sessao: Any = _O_MESMO_QUE_O_PEDIDO,
) -> None:
    """Anota o CAMINHO — e são DOIS lugares, porque são DUAS perguntas."""
    from hefesto_dualsense4unix.integrations.virtual_pad import normalizar_caminho

    pedido = caminho if da_sessao is _O_MESMO_QUE_O_PEDIDO else da_sessao
    daemon.config.gamepad_caminho = normalizar_caminho(pedido)
    escolhido = normalizar_caminho(caminho)
    if escolhido is None or origin != "manual":
        return
    # vazamento."*  <!-- noqa-acento: citação literal dela -->
    if _ha_jogo_em_foco(daemon):
        logger.info(
            "caminho_do_gesto_ficou_no_jogo",
            caminho=escolhido,
            motivo="janela_de_jogo_em_foco",
        )
        return
    daemon.config.gamepad_caminho_global = escolhido
    with contextlib.suppress(Exception):
        from hefesto_dualsense4unix.utils.session import (
            ORIGEM_DO_GESTO_FORA_DO_JOGO,
            save_gamepad_caminho,
        )

        save_gamepad_caminho(escolhido, origem=ORIGEM_DO_GESTO_FORA_DO_JOGO)


def caminho_da_sessao(daemon: Any) -> str | None:
    """O MODO que vale nesta sessão — o dono único que todo restart lê.

    O-MODO-XBOX-NAO-E-QUEDA-02 (28/09/2026), item 1 da cura consolidada. O
    slot da sessão (`config.gamepad_caminho`) é escrito por quem ESCOLHE o
    modo: o perfil ativado (o lançamento, o autoswitch, o boot) e o gesto dela.
    Quem só RECRIA o pad (a ordem do co-op, o revive, a volta do Steam Input, a
    promoção, o juiz das máscaras, o cartão, a saída do Modo Nativo, a
    automação de dois controles) lê daqui e não escolhe nada.

    Medido na sessão dela de 27/09 às 21h07 e às 23h28: o lançamento do
    PRAGMATA pôs o pad em DualSense e, segundos depois, um restart o devolveu
    ao Xbox sem que o diário dissesse quem pediu. Cada restart tinha a sua
    fonte (a foto da suspensão, o caminho do pad velho, nenhuma).
    """
    from hefesto_dualsense4unix.integrations.virtual_pad import normalizar_caminho

    return normalizar_caminho(getattr(getattr(daemon, "config", None), "gamepad_caminho", None))


def nomear_o_restart(daemon: Any, motivo: str) -> str | None:
    """O restart diz quem o pediu, e devolve o caminho do dono."""
    caminho = caminho_da_sessao(daemon)
    logger.info("p1_reerguido", motivo=motivo, caminho=caminho)
    return caminho


def reerguer_o_p1(daemon: Any, *, motivo: str, flavor: str | None = None) -> str:
    """Recria o pad do P1 no modo da sessão e devolve o desfecho `EMU_*`."""
    return start_gamepad_emulation_desfecho(
        daemon,
        flavor,
        origin="profile",
        caminho=nomear_o_restart(daemon, motivo),
    )


def start_gamepad_emulation(
    daemon: DaemonProtocol,
    flavor: str | None = None,
    *,
    origin: OrigemEmulacao,
    caminho: str | None = None,
) -> bool:
    """Cria o gamepad virtual com a máscara `flavor`. Idempotente. True = ATIVO.

    Fachada histórica de `start_gamepad_emulation_desfecho`: devolve o bool que
    sempre quis dizer "ativo ao final" — e NUNCA "aplicou o pedido", que é o
    mal-entendido que o VERDADE-01 desfez. Quem precisa distinguir aplicou de
    já-estava de bloqueado-pelo-jogo chama a versão `_desfecho`.

    `origin` é OBRIGATÓRIO e keyword-only — decisão medida de 08/08/2026
    (ORIGEM-QUE-MENTE-01): o default `"manual"` fazia o SILÊNCIO de um cliente
    virar gesto dela, e foi assim que nasceu o "Jogador 3" fantasma (pedido sem
    origem furava o portão JOGO-01 e ainda calava o autoswitch por 30 s). O
    VERDADE-01 (18/08) só alargou o TIPO, para caber `"gesto_de_perfil"` — não
    devolveu o default. Há portão que reprova o retorno dele.
    """
    return (
        start_gamepad_emulation_desfecho(daemon, flavor, origin=origin, caminho=caminho)
        in DESFECHOS_EMULACAO_ATIVA
    )


def start_gamepad_emulation_desfecho(
    daemon: DaemonProtocol,
    flavor: str | None = None,
    *,
    origin: OrigemEmulacao,
    caminho: str | None = None,
    caminho_e_escolha: bool = True,
) -> str:
    """Cria o gamepad virtual com a máscara `flavor` e DIZ o que aconteceu.

    `caminho_e_escolha=False` (O-MODO-XBOX-NAO-E-QUEDA-02, 28/09/2026): o
    `caminho` veio do dono da sessão (:func:`caminho_da_sessao`) e não de uma
    escolha, então vale para o pad e para o slot e nunca chega ao arquivo dela,
    nem com `origin="manual"` (o gesto do cartão escolhe máscara, não modo).

    MODO-DE-CONEXAO-01 (13/09/2026): `caminho` é o MODO de conexão
    (`virtual_pad.CAMINHO_DUALSENSE` · `CAMINHO_XBOX`), e ele NÃO é a máscara.
    ``None`` = o chamador não opina, e vale a ESCOLHA DELA
    (`config.gamepad_caminho_global`, o que o boot relê de `gamepad_caminho.flag`)
    ou, sem escolha nenhuma, o que sai da máscara. Nunca o canal que o jogo
    anterior deixou de pé — O-CAMINHO-NAO-VAZA-01, 17/09/2026.
    A idempotência compara (máscara efetiva, canal): trocar de caminho com a
    mesma máscara RECRIA o vpad no outro canal — era o `ja_estava` desta função
    que fazia o chip «Xbox» dizer «aplicado» sem mudar nada.

    VERDADE-01: devolve o vocabulário `EMU_*` — `"aplicado"`, `"ja_estava"`,
    `"bloqueado_por_jogo"` ou `"falhou"`. Os três primeiros deixam a emulação
    ATIVA ao final (é isso, e só isso, que o bool da fachada diz).
    `"recusado_steam_input"` existe no vocabulário mas NÃO sai daqui desde
    09/08/2026 — ver a nota do ESCONDER-EM-VEZ-DE-SAIR-01 abaixo.

    `origin` é OBRIGATÓRIO aqui pela mesma razão da fachada (08/08/2026,
    ORIGEM-QUE-MENTE-01): este é o seam por onde o pedido entra de verdade, e
    um default reabriria a porta dos fundos que aquela cura fechou.

    Desliga a emulação de mouse (mútua exclusão) e faz grab do controle real.
    Idempotência por (flavor, backend): apply idêntico com backend saudável é no-op; mesma
    máscara DualSense com backend degradado (uinput) recria em uhid (VPAD-02).
    `origin` vem de `set_gamepad_emulation` (BT-04(b)): só o gesto MANUAL da
    usuária destrava a promoção por apply idêntico — perfil/autoswitch nunca
    recriam o vpad degradado (o latch anti-churn; ver `_deve_promover_backend`).
    `"gesto_de_perfil"` (VERDADE-01) conta como automático em TUDO aqui — só o
    gate R-04 o reconhece como gesto dela.

    NOTA DATADA — 09/08/2026 (ESCONDER-EM-VEZ-DE-SAIR-01). Aqui havia a trava da
    JOGO-01: *"com a exceção de Steam Input ATIVA, todo apply AUTOMÁTICO é
    recusado — nos appids da allowlist o dispositivo do jogo é o físico, e o
    autoswitch recriaria o vpad que a suspensão acabou de retirar"*. Ela existia
    para PROTEGER a suspensão, e a suspensão saiu do caminho da marca: no jogo
    marcado o dispositivo do jogo passou a ser o vpad. Recusar o apply do perfil
    ali seria recusar justamente o dispositivo que a marca promete entregar. O
    ramo que encerra uma suspensão HERDADA continua abaixo, agora guardado pelo
    flag da suspensão e não pela exceção: ele existe para o daemon que subiu
    ANTES desta cura e está com uma suspensão de pé agora. Deixou de ser só o
    gesto dela — QUALQUER apply passa a encerrá-la, e tem de ser assim, porque
    do contrário a suspensão herdada sobreviveria até ela lembrar de clicar no
    botão. Por isso a origem foi para dentro do log.
    """
    from hefesto_dualsense4unix.daemon.subsystems.coop import (
        numero_do_nome_do_primario,
    )
    from hefesto_dualsense4unix.daemon.subsystems.external_mask import mascara_efetiva
    from hefesto_dualsense4unix.integrations.uinput_gamepad import normalize_flavor
    from hefesto_dualsense4unix.integrations.virtual_pad import (
        caminho_do_vpad,
        caminho_resolvido,
        make_virtual_pad,
        motivo_da_degradacao,
        normalizar_caminho,
        o_aparelho_mudou,
        quer_uhid,
    )

    key = normalize_flavor(
        flavor if flavor is not None else getattr(daemon.config, "gamepad_flavor", None)
    )
    identity = primary_identity(daemon)
    mascara_do_p1 = mascara_efetiva(identity, key)
    caminho_pedido = normalizar_caminho(caminho) or _caminho_a_herdar(daemon)
    uhid_pedido = quer_uhid(caminho_pedido, mascara_do_p1)

    existing = daemon._gamepad_device
    if existing is not None:
        # DualSense caía aqui: a máscara efetiva não muda, a função voltava
        mesmo_canal = (
            quer_uhid(caminho_do_vpad(existing), mascara_do_p1) == uhid_pedido
            and not o_aparelho_mudou(existing, caminho_pedido, mascara_do_p1)
        )
        if (
            getattr(existing, "flavor", None) == mascara_do_p1
            and mesmo_canal
            and not (
                uhid_pedido
                and _deve_promover_backend(daemon, existing, mascara_do_p1, origin)
            )
        ):
            _guardar_o_caminho(
                daemon,
                caminho if caminho_e_escolha else None,
                origin=origin,
                da_sessao=caminho_pedido,
            )
            daemon.config.gamepad_flavor = key
            return EMU_JA_ESTAVA
        if vpad_vivo(existing) and _recriacao_bloqueada_por_jogo(
            daemon,
            origin=origin,
            motivo=(
                f"troca_de_mascara:{getattr(existing, 'flavor', None)}->{mascara_do_p1}"
                if getattr(existing, "flavor", None) != mascara_do_p1
                else "troca_de_caminho:"
                f"{caminho_resolvido(caminho_pedido, mascara_do_p1)}"
            ),
        ):
            return EMU_BLOQUEADO_POR_JOGO
        stop_gamepad_emulation(daemon, persist=False, release_grab=False)

    if getattr(daemon, "_mouse_device", None) is not None:
        from hefesto_dualsense4unix.daemon.subsystems.mouse import stop_mouse_emulation

        stop_mouse_emulation(daemon, persist=False)

    # (DualSense com hidraw de verdade = vibração in-game na máscara DualSense)
    device: VirtualPad | None = make_virtual_pad(
        key,
        identity=identity,
        rumble_sink=make_primary_rumble_sink(daemon),
        player=numero_do_nome_do_primario(daemon),
        allow_uhid=controller_allows_uhid(daemon),
        calibration_0x05=read_primary_calibration(daemon),
        caminho=caminho_pedido,
        **make_primary_replica_sinks(daemon),
    )
    if device is None:
        logger.warning("gamepad_emulation_start_failed", flavor=key)
        _materialize_launch_env(daemon)
        return EMU_FALHOU

    daemon._gamepad_device = device
    motivo_da_queda = motivo_da_degradacao(device)
    if motivo_da_queda is not None:
        # logou, o degrau vira contador no store (doctor) e o `state_full` expõe
        store = getattr(daemon, "store", None)
        if store is not None:
            with contextlib.suppress(Exception):
                store.bump("gamepad.uhid.fallback")
        notify_vpad_degradado(daemon, player=1, motivo=motivo_da_queda)
    start_motion_reader(daemon, device)
    daemon.config.gamepad_emulation_enabled = True
    daemon.config.gamepad_flavor = key
    _guardar_o_caminho(
        daemon,
        caminho if caminho_e_escolha else None,
        origin=origin,
        da_sessao=caminho_pedido,
    )
    _set_controller_grab(daemon, True)
    if origin == "manual":
        with contextlib.suppress(Exception):
            from hefesto_dualsense4unix.utils.session import (
                load_gamepad_preference,
                save_gamepad_emulation,
            )

            # medido na máquina dela: o gesto com que ela diz «Sony DualSense»
            # `gamepad.mask.set`, que grava no registro por aparelho.
            if flavor is not None:
                save_gamepad_emulation(True, key)
            else:
                _preferencia, gravada = load_gamepad_preference()
                save_gamepad_emulation(True, gravada)
    _materialize_launch_env(daemon)
    logger.info(
        "gamepad_emulation_started",
        flavor=key,
        mascara_do_p1=mascara_do_p1,
        caminho=caminho_resolvido(caminho_pedido, mascara_do_p1),
        identity=identity,
    )
    return EMU_APLICADO


def reconciliar_as_mascaras(daemon: Any) -> str | None:
    """Todo boneco veste a máscara efetiva de AGORA: o P1 e os secundários."""
    from hefesto_dualsense4unix.daemon.subsystems.external_mask import (
        mascara_efetiva,
        vpad_ficou_para_tras,
    )

    cfg = getattr(daemon, "config", None)
    if not getattr(cfg, "gamepad_emulation_enabled", False):
        return None
    if getattr(daemon, "_native_mode", False):
        return None
    flavor_do_jogo = getattr(cfg, "gamepad_flavor", None)
    caminho = caminho_da_sessao(daemon)
    desfecho: str | None = None
    vpad = getattr(daemon, "_gamepad_device", None)
    identity = primary_identity(daemon)
    p1_para_tras = bool(
        vpad is not None
        and vpad_vivo(vpad)
        and vpad_ficou_para_tras(
            getattr(vpad, "flavor", None),
            identity,
            flavor_do_jogo,
            vpad=vpad,
            caminho=caminho,
        )
    )
    coop = getattr(daemon, "_coop_manager", None)
    atrasado = getattr(coop, "algum_boneco_ficou_para_tras", None)
    secundario_para_tras = bool(coop is not None and callable(atrasado) and atrasado())
    if not (p1_para_tras or secundario_para_tras):
        return None
    if _recriacao_bloqueada_por_jogo(
        daemon, origin="reconciliacao", motivo="mascara_reconciliada"
    ):
        return None
    if p1_para_tras:
        logger.info(
            "mascara_do_p1_reconciliada",
            vestia=getattr(vpad, "flavor", None),
            veste=mascara_efetiva(identity, flavor_do_jogo),
        )
        with getattr(daemon, "_emu_lock", contextlib.nullcontext()):
            desfecho = reerguer_o_p1(daemon, motivo="mascara_reconciliada")
    if secundario_para_tras and coop is not None:
        coop.sync(force=True)
    return desfecho


def stop_gamepad_emulation(
    daemon: DaemonProtocol, *, persist: bool = True, release_grab: bool = True
) -> None:
    """Para e descarta o gamepad virtual. Idempotente."""
    stop_motion_reader(daemon)
    tinha_device = daemon._gamepad_device is not None
    if tinha_device:
        with contextlib.suppress(Exception):
            daemon._gamepad_device.stop()
        daemon._gamepad_device = None
    daemon.config.gamepad_emulation_enabled = False
    if release_grab:
        _set_controller_grab(daemon, False)
        soltar_o_cursor_do_toque(daemon)
    if persist:
        with contextlib.suppress(Exception):
            from hefesto_dualsense4unix.utils.session import save_gamepad_emulation

            save_gamepad_emulation(False)
    from hefesto_dualsense4unix.daemon.subsystems.rumble import zero_motors_on_mode_exit

    zero_motors_on_mode_exit(daemon)
    _materialize_launch_env(daemon)
    if tinha_device:
        logger.info("gamepad_emulation_stopped")
    if release_grab and not _daemon_parando(daemon):
        _avisar_troca_de_modo(daemon)


def _avisar_troca_de_modo(daemon: DaemonProtocol) -> None:
    """Dispara o aviso de modo na lightbar. AVISO-DE-MODO-01 (19/08/2026).

    Fina de propósito: a decisão inteira (qual é o modo, qual é a cor, se
    mudou, e a piscada numa thread) mora em
    `daemon/subsystems/hotkey.avisar_troca_de_modo`. Aqui fica só o GATILHO,
    porque é este arquivo que tem o ponto por onde toda troca passa.

    **Os dois pontos, e por que são estes dois.** Ela troca de modo por quatro
    portas — o gesto, a janela, a CLI/IPC e o autoswitch — e o aviso tem de
    acender nas quatro. Não há função única que todas atravessem, mas há dois
    estados e cada um tem seu ponto:

    - **com vpad de pé** (máscara DualSense, máscara Xbox, Steam Input na
      frente): `dispatch_gamepad`, que o poll loop chama a cada tique. O aviso
      é level-triggered, então uma comparação de string por tique cobre
      qualquer troca, tenha vindo de onde tiver vindo, com a latência de um
      tique;
    - **sem vpad** (mouse+teclado e Modo Nativo): o fim do
      `stop_gamepad_emulation`, que é por onde os dois entram — o Modo Nativo
      inclusive, porque `lifecycle._release_controller_to_game` desliga a
      emulação ANTES de mutar a saída (`set_output_mute(True)`). Até 23/09/2026
      essa ordem era o que deixava o branco do Nativo sair; hoje a luz sai sob o
      mute (`D-2309-NO-NATIVO-A-LUZ-E-O-NUMERO-SAO-DO-HEFESTO`). A guarda de lá
      (`release_grab`, não `persist`) está explicada no próprio ponto.

    `suppress(Exception)` largo: um aviso NUNCA pode derrubar o dispatch do
    controle, que é a ROTA do jogo. Mesma disciplina do `_reconciliar_launch`.
    """
    with contextlib.suppress(Exception):
        from hefesto_dualsense4unix.daemon.subsystems.hotkey import (
            avisar_troca_de_modo,
        )

        avisar_troca_de_modo(daemon)


from hefesto_dualsense4unix.core.remapeamento_de_botao import (  # noqa: E402
    GATILHOS as GATILHOS_DO_JOGO,
)
from hefesto_dualsense4unix.core.remapeamento_de_botao import (  # noqa: E402
    ativo as remapeamento_ativo,
)
from hefesto_dualsense4unix.core.remapeamento_de_botao import (  # noqa: E402
    traduzir as traduzir_remapeamento,
)
from hefesto_dualsense4unix.core.roteador_de_movimento import (  # noqa: E402
    ativo as roteador_ativo,
)


def aplicar_o_movimento(
    daemon: DaemonProtocol,
    arranjo: Any,
    *,
    uniq: str | None,
    lx: int,
    ly: int,
    rx: int,
    ry: int,
    botoes: frozenset[str],
    na_navegacao: bool = False,
) -> tuple[int, int, int, int]:
    """O giroscópio do físico vira deslocamento no que o jogo já lê."""
    try:
        if not uniq:
            return lx, ly, rx, ry
        garantir = getattr(daemon, "_garantir_sensor_hub", None)
        if garantir is None:
            return lx, ly, rx, ry
        hub = garantir()
        from hefesto_dualsense4unix.core import roteador_de_movimento as roteador

        store = getattr(daemon, "store", None)
        peca = roteador.da_peca(store, uniq, arranjo)
        if na_navegacao:
            arranjo = roteador.para_o_cursor(arranjo)
            peca = roteador.para_o_cursor(peca) if peca is not None else None
        quer_angulo = arranjo.quer_angulo or (peca is not None and peca.quer_angulo)
        angulo = hub.angulo_do_movimento(uniq) if quer_angulo else None
        if angulo is not None:
            angulo = roteador.angulo_do_tique(store, uniq, angulo, time.monotonic())
        if peca is None:
            return lx, ly, rx, ry
        arranjo = peca

        gatilho = arranjo.gatilho
        if gatilho is not None and GATILHOS_DO_JOGO.get(gatilho, gatilho) not in botoes:
            return lx, ly, rx, ry
        from hefesto_dualsense4unix.core.virtual_motion import REGISTRO

        sensores = REGISTRO.estado(uniq)
        if arranjo.inclina and sensores.acelerometro and not na_navegacao:
            lx, ly, rx, ry = _a_inclinacao(hub, store, arranjo, uniq, lx, ly, rx, ry)
        if not arranjo.ligado or not sensores.giroscopio:
            return lx, ly, rx, ry

        velocidade = hub.velocidade_do_movimento(uniq)
        if velocidade is None:
            return lx, ly, rx, ry

        if arranjo.quer_angulo:
            if angulo is None:
                return lx, ly, rx, ry
            if roteador.deflexao(velocidade, arranjo) == (0, 0):
                return lx, ly, rx, ry
            mouse = getattr(daemon, "_mouse_device", None)
            if mouse is not None:
                dx, dy = roteador.pixels(angulo, arranjo)
                mouse.emit_gyro_move(dx, dy)
            return lx, ly, rx, ry

        dh, dv = roteador.deflexao(velocidade, arranjo)
        if dh == 0 and dv == 0:
            return lx, ly, rx, ry
        if arranjo.destino == roteador.DESTINO_ANALOGICO_ESQUERDO:
            lx, ly = roteador.misturar(lx, ly, dh, dv)
        else:
            rx, ry = roteador.misturar(rx, ry, dh, dv)
        return lx, ly, rx, ry
    except Exception as exc:
        logger.warning("roteador_de_movimento_falhou", err=str(exc))
        return lx, ly, rx, ry


def dispatch_gamepad(
    daemon: DaemonProtocol, state: Any, buttons_pressed: frozenset[str]
) -> None:
    """Repassa o estado do controle ao gamepad virtual."""
    _reconciliar_launch(daemon)
    _avisar_troca_de_modo(daemon)
    device = daemon._gamepad_device
    if device is None:
        return
    buttons_pressed, soltos = _apertos_do_primario(daemon, device, buttons_pressed)
    store = getattr(daemon, "store", None)
    limiar_l, limiar_r = getattr(store, "udp_trigger_thresholds", (0, 0))
    try:
        l2 = state.l2_raw if state.l2_raw >= limiar_l else 0
        r2 = state.r2_raw if state.r2_raw >= limiar_r else 0
        botoes = buttons_pressed
        arranjo = roteador_ativo(store)
        uniq = primary_identity(daemon) if arranjo is not None else None
        if arranjo is not None:
            botoes, l2 = aplicar_o_toque(daemon, arranjo, uniq=uniq, botoes=botoes, l2=l2)
        if getattr(daemon, "_cursor_do_toque", None):
            _conferir_o_cursor_do_toque(daemon, store)
        da_mao = botoes
        troca = remapeamento_ativo(store)
        if troca:
            botoes, l2, r2 = traduzir_remapeamento(botoes, l2, r2, troca)
        lx, ly = state.raw_lx, state.raw_ly
        rx, ry = state.raw_rx, state.raw_ry
        if arranjo is not None:
            lx, ly, rx, ry = aplicar_o_movimento(
                daemon,
                arranjo,
                uniq=uniq,
                lx=lx,
                ly=ly,
                rx=rx,
                ry=ry,
                botoes=da_mao,
            )
        device.forward_analog(lx=lx, ly=ly, rx=rx, ry=ry, l2=l2, r2=r2)
        if soltos:
            com_soltos = da_mao | soltos
            if troca:
                com_soltos = traduzir_remapeamento(com_soltos, l2, r2, troca)[0]
            device.forward_buttons(com_soltos)
        device.forward_buttons(botoes)
        pump = getattr(device, "pump_ff", None)
        if pump is not None:
            pump()
    except Exception as exc:
        logger.warning("gamepad_dispatch_failed", err=str(exc))


def _a_inclinacao(
    hub: Any,
    store: Any,
    arranjo: Any,
    uniq: str,
    lx: int,
    ly: int,
    rx: int,
    ry: int,
) -> tuple[int, int, int, int]:
    """O acelerômetro da peça somado ao analógico do arranjo. Nunca levanta."""
    from hefesto_dualsense4unix.core import roteador_de_movimento as roteador

    perguntar = getattr(hub, "aceleracao_do_movimento", None)
    acel = perguntar(uniq) if callable(perguntar) else None
    if acel is None:
        return lx, ly, rx, ry
    neutro = roteador.neutro_da_inclinacao(store, uniq, acel, time.monotonic())
    dh, dv = roteador.deflexao_da_inclinacao(acel, neutro, arranjo)
    if dh == 0 and dv == 0:
        return lx, ly, rx, ry
    if arranjo.acelerometro == roteador.DESTINO_ANALOGICO_DIREITO:
        rx, ry = roteador.misturar(rx, ry, dh, dv)
    else:
        lx, ly = roteador.misturar(lx, ly, dh, dv)
    return lx, ly, rx, ry


def _dedos_do_toque(estado: Any) -> list[tuple[int, int, int]]:
    """Os dedos apoiados como `(identidade, x, y)`, do `TouchState` do leitor."""
    pontos = tuple(getattr(estado, "pontos", ()) or ())
    if pontos:
        return [(int(p.identidade), int(p.x), int(p.y)) for p in pontos]
    if getattr(estado, "touching", False):
        return [(-1, int(estado.x), int(estado.y))]
    return []


def aplicar_o_toque(
    daemon: DaemonProtocol,
    arranjo: Any,
    *,
    uniq: str | None,
    botoes: frozenset[str],
    l2: int,
) -> tuple[frozenset[str], int]:
    """O touchpad da peça `uniq` vira botões (zonas) ou cursor. Nunca levanta."""
    try:
        if not uniq:
            return botoes, l2
        from hefesto_dualsense4unix.core import roteador_de_movimento as roteador

        store = getattr(daemon, "store", None)
        peca = roteador.da_peca(store, uniq, arranjo)
        if peca is None or peca.toque != roteador.TOQUE_CURSOR:
            _largar_o_clique(daemon, uniq)
        if peca is None or not peca.toca:
            return botoes, l2
        garantir = getattr(daemon, "_garantir_sensor_hub", None)
        if garantir is None:
            return botoes, l2
        perguntar = getattr(garantir(), "toque_da_peca", None)
        leitura = perguntar(uniq) if callable(perguntar) else None
        if leitura is None:
            _largar_o_clique(daemon, uniq)
            return botoes, l2
        estado, clicado = leitura
        dedos = _dedos_do_toque(estado)
        if peca.toque == roteador.TOQUE_ZONAS:
            apertados = roteador.botoes_das_zonas(
                ((x, y) for _dedo, x, y in dedos),
                int(getattr(estado, "largura", 0) or 0),
                int(getattr(estado, "altura", 0) or 0),
            )
            if not apertados:
                return botoes, l2
            if roteador.BOTAO_DA_ZONA_DE_BAIXO in apertados:
                from hefesto_dualsense4unix.core.remapeamento_de_botao import FORCA_CHEIA

                l2 = max(l2, FORCA_CHEIA)
            return botoes | apertados, l2
        dx, dy = roteador.delta_do_toque(store, uniq, dedos, time.monotonic())
        garantir_o_cursor = getattr(daemon, "_garantir_cursor_do_toque", None)
        cursor = garantir_o_cursor() if callable(garantir_o_cursor) else None
        if cursor is not None:
            if dx or dy:
                cursor.mover(*roteador.pixels_do_toque(dx, dy, peca))
            cursor.clicar(uniq, bool(clicado))
        return botoes, l2
    except Exception as exc:
        logger.warning("roteador_do_toque_falhou", err=str(exc))
        return botoes, l2


def _largar_o_clique(daemon: Any, uniq: str) -> None:
    """O clique da peça `uniq` sai do botão do cursor, se o nó existe. Nunca levanta."""
    cursor = getattr(daemon, "_cursor_do_toque", None)
    if not cursor:
        return
    with contextlib.suppress(Exception):
        cursor.clicar(uniq, False)


def _conferir_o_cursor_do_toque(daemon: Any, store: Any) -> None:
    """O nó do cursor só fica de pé enquanto alguma peça o quer. Nunca levanta."""
    from hefesto_dualsense4unix.core import roteador_de_movimento as roteador

    try:
        if not roteador.quer_cursor(store):
            soltar_o_cursor_do_toque(daemon)
            return
        conferir = getattr(getattr(daemon, "_cursor_do_toque", None), "conferir", None)
        if callable(conferir):
            conferir()
    except Exception as exc:
        logger.warning("cursor_do_toque_conferir_falhou", err=str(exc))


# Com pad virtual DualSense, a luz e o mudo do microfone que o jogo pede vão

_RETIDO_JA_DITO: set[str] = set()


def _primario_da_hora(daemon: Any) -> str | None:
    """O `primary_uniq` do INSTANTE, sem entrar na conta das réplicas da sessão."""
    uniq = getattr(getattr(daemon, "controller", None), "primary_uniq", None)
    return uniq if isinstance(uniq, str) and uniq else None


def apply_game_mic(
    daemon: Any,
    *,
    target_uniq: str | None,
    luz: int | None = None,
    mudo: bool | None = None,
    solta: bool = False,
) -> bool | None:
    """Leva ao dono o pedido do microfone do jogo. `True` = aplicado."""
    from hefesto_dualsense4unix.core.events import EventTopic
    from hefesto_dualsense4unix.daemon.subsystems.luz_do_mic import chave_do_mic

    chave = chave_do_mic(target_uniq)
    if chave is None:
        logger.debug("game_mic_sem_alvo_descartado", target=target_uniq)
        return None
    evento: dict[str, Any] = {"uniq": chave, "em": time.monotonic()}
    if solta:
        evento["solta"] = True
    elif luz is not None:
        evento["luz"] = int(luz)
    elif mudo is not None:
        evento["mudo"] = bool(mudo)
    else:
        return None
    autoridade = getattr(daemon, "display_authority", "unknown")
    if not solta and autoridade == "daemon":
        if chave not in _RETIDO_JA_DITO:
            _RETIDO_JA_DITO.add(chave)
            logger.info("mic_do_jogo_retido_sem_jogo", uniq=chave, autoridade=autoridade)
        return False
    _RETIDO_JA_DITO.discard(chave)
    publicar = getattr(getattr(daemon, "bus", None), "publish", None)
    if not callable(publicar):
        logger.debug("game_mic_sem_barramento", uniq=chave)
        return None
    publicar(EventTopic.MIC_DO_JOGO, evento)
    return True


def ralos_do_mic(daemon: Any, alvo: Callable[[], str | None]) -> dict[str, Any]:
    """Os dois ralos do microfone de UM pad virtual; `alvo` diz o controle na hora."""
    luz_entregue_a: set[str] = set()

    def _luz(valor: int | None) -> bool | None:
        if valor is None:
            alvos = tuple(luz_entregue_a)
            luz_entregue_a.clear()
            for quem in alvos:
                apply_game_mic(daemon, target_uniq=quem, solta=True)
            return True
        uniq = alvo()
        aplicado = apply_game_mic(daemon, target_uniq=uniq, luz=valor)
        if aplicado and uniq:
            luz_entregue_a.add(uniq)
        return aplicado

    def _mudo(mudo: bool) -> bool | None:
        return apply_game_mic(daemon, target_uniq=alvo(), mudo=mudo)

    return {"mic_led_sink": _luz, "mic_mute_sink": _mudo}


def soltar_o_cursor_do_toque(daemon: Any) -> None:
    """Destrói o cursor do toque da sessão, se houver. Idempotente."""
    cursor = getattr(daemon, "_cursor_do_toque", None)
    if cursor is None:
        return
    if cursor is not False:
        with contextlib.suppress(Exception):
            cursor.stop()
    daemon._cursor_do_toque = None


def _rotulo_do_jogador(coop: Any, player: Any) -> str:
    """O ``N`` do ``jogador_N_uinput``: o número da carta, como o nome e a lâmpada."""
    indice = getattr(player, "player_index", None)
    if not isinstance(indice, int) or isinstance(indice, bool):
        return "?"
    perguntar = getattr(coop, "numero_do_diario", None)
    if callable(perguntar):
        with contextlib.suppress(Exception):
            numero = perguntar(getattr(player, "identity", None), indice)
            if isinstance(numero, int) and not isinstance(numero, bool) and numero >= 1:
                return str(numero)
    return str(indice)


_ATRIBUTO_DO_NUMERO_DO_JOGO = "_numero_que_o_jogo_escreveu"


def _marcas_do_numero_do_jogo(daemon: Any) -> dict[str, tuple[int | None, int | None]] | None:
    """O ``{uniq: (jogo, hefesto)}`` deste daemon, criado na primeira consulta."""
    marcas = getattr(daemon, _ATRIBUTO_DO_NUMERO_DO_JOGO, None)
    if isinstance(marcas, dict):
        return marcas
    novas: dict[str, tuple[int | None, int | None]] = {}
    try:
        setattr(daemon, _ATRIBUTO_DO_NUMERO_DO_JOGO, novas)
    except Exception:
        return None
    return novas


def _o_numero_que_o_jogo_escreveu(daemon: Any, bits: Any, target_uniq: str) -> None:
    """Diz no diário o número que o jogo escreveu nas lâmpadas, a cada mudança. Nunca levanta."""
    try:
        from hefesto_dualsense4unix.core.backend_pydualsense import (
            _endereco_mascarado,
            numero_do_desenho,
        )

        jogo = numero_do_desenho(bits)
        hefesto: int | None = None
        perguntar = getattr(getattr(daemon, "identity_registry", None), "numero_da_lampada", None)
        if callable(perguntar):
            bruto = perguntar(target_uniq, assign=False)
            if isinstance(bruto, int) and not isinstance(bruto, bool) and bruto >= 1:
                hefesto = bruto
        marcas = _marcas_do_numero_do_jogo(daemon)
        if marcas is None or marcas.get(target_uniq) == (jogo, hefesto):
            return
        marcas[target_uniq] = (jogo, hefesto)
        logger.info(
            "o_numero_que_o_jogo_escreveu",
            uniq=_endereco_mascarado(target_uniq) or "?",
            jogo="?" if jogo is None else jogo,
            hefesto=hefesto,
            concorda=jogo is not None and jogo == hefesto,
        )
    except Exception as exc:
        logger.debug("o_numero_que_o_jogo_escreveu_falhou", err=str(exc))


def _esquecer_o_numero_do_jogo(daemon: Any, target_uniq: str | None) -> None:
    """O fim da sessão do pad zera a marca: o próximo jogo é dito desde a primeira escrita."""
    if target_uniq is None:
        return
    marcas = getattr(daemon, _ATRIBUTO_DO_NUMERO_DO_JOGO, None)
    if isinstance(marcas, dict):
        marcas.pop(target_uniq, None)


class ApertosVistos:
    """A contagem de apertos que um pad virtual já recebeu, por par (leitor, pad)."""

    __slots__ = ("contagem", "leitor", "pad", "pronto_em")

    def __init__(self) -> None:
        self.leitor: Any = None
        self.pad: Any = None
        self.pronto_em: Any = None
        self.contagem: dict[str, int] = {}

    def soltos(
        self,
        *,
        leitor: Any,
        pad: Any,
        pronto_em: Any,
        apertos: Any,
        apertados: frozenset[str],
    ) -> frozenset[str]:
        """Os nomes que foram apertados E soltos desde a última entrega."""
        contagem = apertos if isinstance(apertos, dict) else {}
        mesmo_par = (
            leitor is self.leitor and pad is self.pad and pronto_em == self.pronto_em
        )
        antes = self.contagem
        self.leitor, self.pad, self.pronto_em, self.contagem = leitor, pad, pronto_em, contagem
        if not mesmo_par or not contagem:
            return frozenset()
        if any(contagem.get(nome, 0) < vezes for nome, vezes in antes.items()):
            return frozenset()
        return frozenset(
            nome
            for nome, vezes in contagem.items()
            if vezes > antes.get(nome, 0) and nome not in apertados
        )


_ATRIBUTO_DOS_APERTOS_DO_P1 = "_apertos_vistos_do_p1"


def _apertos_do_primario(
    daemon: Any, device: Any, buttons_pressed: frozenset[str]
) -> tuple[frozenset[str], frozenset[str]]:
    """(os botões de agora, os que já soltaram), lidos do retrato do primário."""
    try:
        leitor = getattr(getattr(daemon, "controller", None), "_evdev", None)
        if leitor is None or not leitor.is_available():
            return buttons_pressed, frozenset()
        retrato = leitor.snapshot()
        apertados = getattr(retrato, "buttons_pressed", None)
        apertos = getattr(retrato, "apertos", None)
        if not isinstance(apertados, frozenset) or not isinstance(apertos, dict):
            return buttons_pressed, frozenset()
        vistos = getattr(daemon, _ATRIBUTO_DOS_APERTOS_DO_P1, None)
        if not isinstance(vistos, ApertosVistos):
            vistos = ApertosVistos()
            setattr(daemon, _ATRIBUTO_DOS_APERTOS_DO_P1, vistos)
        soltos = vistos.soltos(
            leitor=leitor,
            pad=device,
            pronto_em=getattr(daemon, "_input_ready_at", None),
            apertos=apertos,
            apertados=apertados,
        )
        return apertados, soltos
    except Exception as exc:
        logger.debug("apertos_do_primario_falhou", err=str(exc))
        return buttons_pressed, frozenset()


__all__ = [
    "DESFECHOS_EMULACAO_ATIVA",
    "EMU_APLICADO",
    "EMU_BLOQUEADO_POR_JOGO",
    "EMU_DESLIGADO",
    "EMU_FALHOU",
    "EMU_JA_ESTAVA",
    "EMU_RECUSADO_STEAM_INPUT",
    "LAUNCH_RECONCILE_INTERVAL_SEC",
    "ORIGENS_GESTO_DELA",
    "ORIGENS_QUE_PASSAM_COM_O_JOGO",
    "REBACKEND_COOLDOWN_SEC",
    "GamepadSubsystem",
    "anotar_rumble_no_vpad",
    "aplicar_o_toque",
    "apply_game_lightbar",
    "apply_game_mic",
    "apply_game_player_leds",
    "apply_game_rumble",
    "apply_game_trigger",
    "dedup_status",
    "dispatch_gamepad",
    "end_game_output_session",
    "esconder_o_fisico_para_o_jogo",
    "esquecer_motores_do_perfil",
    "make_primary_replica_sinks",
    "make_primary_rumble_sink",
    "notify_vpad_degradado",
    "ralos_do_mic",
    "read_primary_calibration",
    "rehide_physical_hidraw",
    "soltar_o_cursor_do_toque",
    "start_gamepad_emulation",
    "start_gamepad_emulation_desfecho",
    "start_motion_reader",
    "steam_input_excecao_ativa",
    "stop_gamepad_emulation",
    "stop_motion_reader",
    "sync_steam_input_exception",
    "upgrade_primary_vpad_to_uhid",
    "vpad_vivo",
]
