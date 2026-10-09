"""Subsystem Mouse — emulação de mouse+teclado virtual via uinput."""
from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING, Any

from hefesto_dualsense4unix.utils.logging_config import get_logger

if TYPE_CHECKING:
    from hefesto_dualsense4unix.daemon.context import DaemonContext
    from hefesto_dualsense4unix.daemon.lifecycle import DaemonConfig
    from hefesto_dualsense4unix.daemon.protocols import DaemonProtocol

logger = get_logger(__name__)


class MouseSubsystem:
    """Subsystem que gerencia a emulação de mouse virtual."""

    name = "mouse"
    _device: Any = None

    async def start(self, ctx: DaemonContext) -> None:
        """Cria o dispositivo uinput se mouse_emulation_enabled=True."""
        cfg = ctx.config
        if not cfg.mouse_emulation_enabled:
            return
        if self._device is not None:
            return
        try:
            from hefesto_dualsense4unix.integrations.uinput_mouse import UinputMouseDevice

            device = UinputMouseDevice(
                mouse_speed=cfg.mouse_speed,
                scroll_speed=cfg.mouse_scroll_speed,
                poll_hz=cfg.poll_hz,
            )
        except Exception as exc:
            logger.warning("mouse_subsystem_import_failed", err=str(exc))
            return
        if not device.start():
            logger.warning("mouse_subsystem_start_failed")
            return
        self._device = device
        logger.info(
            "mouse_subsystem_started",
            speed=cfg.mouse_speed,
            scroll_speed=cfg.mouse_scroll_speed,
        )

    async def stop(self) -> None:
        """Para e descarta o dispositivo virtual. Idempotente."""
        if self._device is not None:
            with contextlib.suppress(Exception):
                self._device.stop()
            self._device = None
            logger.info("mouse_subsystem_stopped")

    def is_enabled(self, config: DaemonConfig) -> bool:
        return config.mouse_emulation_enabled


def start_mouse_emulation(daemon: DaemonProtocol) -> bool:
    """Cria device virtual de mouse+teclado (FEAT-MOUSE-01). Idempotente."""
    if daemon._mouse_device is not None:
        return True
    try:
        from hefesto_dualsense4unix.integrations.uinput_mouse import UinputMouseDevice

        device = UinputMouseDevice(
            mouse_speed=daemon.config.mouse_speed,
            scroll_speed=daemon.config.mouse_scroll_speed,
            poll_hz=daemon.config.poll_hz,
        )
    except Exception as exc:
        logger.warning("mouse_emulation_import_failed", err=str(exc))
        return False
    if not device.start():
        logger.warning("mouse_emulation_start_failed")
        return False
    daemon._mouse_device = device
    daemon.config.mouse_emulation_enabled = True
    with contextlib.suppress(Exception):
        from hefesto_dualsense4unix.utils.session import save_mouse_emulation

        save_mouse_emulation(
            True,
            speed=daemon.config.mouse_speed,
            scroll_speed=daemon.config.mouse_scroll_speed,
        )
    logger.info(
        "mouse_emulation_started",
        speed=daemon.config.mouse_speed,
        scroll_speed=daemon.config.mouse_scroll_speed,
    )
    return True


def stop_mouse_emulation(daemon: DaemonProtocol, *, persist: bool = True) -> None:
    """Para e descarta o dispositivo virtual. Idempotente."""
    if daemon._mouse_device is None:
        return
    with contextlib.suppress(Exception):
        daemon._mouse_device.stop()
    daemon._mouse_device = None
    daemon.config.mouse_emulation_enabled = False
    if persist:
        with contextlib.suppress(Exception):
            from hefesto_dualsense4unix.utils.session import save_mouse_emulation

            save_mouse_emulation(False)
    logger.info("mouse_emulation_stopped", persist=persist)


def dispatch_mouse(daemon: DaemonProtocol, state: Any, buttons_pressed: frozenset[str]) -> None:
    """Traduz o estado do controle em eventos de mouse+teclado virtual.

    Chamado pelo poll loop a cada tick se _mouse_device não for None.
    Não relança exceções — falhas são logadas como warning.
    """
    device = daemon._mouse_device
    if device is None:
        return
    try:
        device.dispatch(
            lx=state.raw_lx,
            ly=state.raw_ly,
            rx=state.raw_rx,
            ry=state.raw_ry,
            l2=state.l2_raw,
            r2=state.r2_raw,
            buttons=buttons_pressed,
        )
    except Exception as exc:
        logger.warning("mouse_dispatch_failed", err=str(exc))
    # B4 (FEAT-DSX-TOUCHPAD-CURSOR-B4): o touchpad é fonte ÚNICA do cursor.
    # Drena o delta acumulado pelo TouchpadReader desde o tick anterior e o
    # converte em REL_X/REL_Y. Só roda aqui (dispatch_mouse), que o poll loop
    reader = getattr(daemon, "_touchpad_reader", None)
    consume = getattr(reader, "consume_motion", None)
    if consume is not None:
        try:
            dx, dy = consume()
            if dx or dy:
                device.emit_touchpad_move(dx, dy)
        except Exception as exc:
            logger.warning("touchpad_move_dispatch_failed", err=str(exc))
    # A-MIRA-NA-NAVEGACAO-01: a Mira de cada controle, no cursor.
    mover_o_cursor_pelo_giro(daemon, buttons_pressed)


def botoes_com_os_gatilhos(botoes: frozenset[str], l2: int, r2: int) -> frozenset[str]:
    """Os botões apertados, com `l2`/`r2` quando o gatilho passa do limiar.

    O gatilho analógico é uma LINHA da tabela como qualquer botão, e as duas
    pontas (o mouse e o teclado) a leem pelo nome: este é o único lugar onde o
    curso vira o nome, pelo limiar de `uinput_mouse.gatilho_apertado`.
    """
    from hefesto_dualsense4unix.integrations.uinput_mouse import gatilho_apertado

    extra = {nome for nome, bruto in (("l2", l2), ("r2", r2)) if gatilho_apertado(bruto)}
    return frozenset(botoes) | extra if extra else frozenset(botoes)


class TabelaNoJogo:
    """A tabela de botões da aba Navegação, agindo JUNTO com o jogo (a chave «Também no jogo»).

    Com o gamepad virtual despachando, o laço pula a emulação de desktop inteira
    (`gamepad_dispatched`), e o `_mouse_device` nem existe: ligar o mouse derruba o
    gamepad virtual. Esta classe é o caminho que NÃO derruba: dois devices
    PRIVADOS, de mouse e de teclado, criados só quando a chave está ligada, que
    nunca tocam o gamepad virtual nem o `_mouse_device` do desktop.

    O QUE ELA AGE, em frases:

    * cada controle aperta as PRÓPRIAS linhas — a união dos botões de P1 a P4,
      com o gatilho analógico de cada um virando `l2`/`r2` pelo mesmo limiar
      (`uinput_mouse.gatilho_apertado`) — e a borda é por código, então dois
      controles no mesmo clique soltam quando o último solta;
    * o cursor e a rolagem andam SÓ pelo P1 (os outros analógicos viram centro),
      e só se a linha do analógico escolheu o próprio token;
    * a tabela vem do perfil EFETIVO (as três camadas), resolvida uma vez por
      ativação; a chave não obedece à Função do teclado nem à supressão.
    """

    def __init__(self, button_actions: Any, key_bindings: Any, *, ligada: bool) -> None:
        from hefesto_dualsense4unix.core.acoes_de_botao import botoes_calados, resolver

        self.ligada = bool(ligada)
        self._do_mouse, self._do_teclado, _sem_dono = resolver(button_actions, key_bindings)
        self._calados = botoes_calados(button_actions, key_bindings)
        self._mouse: Any = None
        self._teclado: Any = None
        self._desistiu = False

    # -- ciclo de vida ---------------------------------------------------

    def _abrir(self, daemon: Any) -> bool:
        if self._mouse is not None and self._teclado is not None:
            return True
        if self._desistiu:
            return False
        try:
            from hefesto_dualsense4unix.integrations.uinput_keyboard import (
                UinputKeyboardDevice,
            )
            from hefesto_dualsense4unix.integrations.uinput_mouse import UinputMouseDevice
            from hefesto_dualsense4unix.profiles.manager import resolve_key_bindings

            cfg = daemon.config
            mouse = UinputMouseDevice(
                mouse_speed=cfg.mouse_speed,
                scroll_speed=cfg.mouse_scroll_speed,
                poll_hz=cfg.poll_hz,
            )
            teclado = UinputKeyboardDevice()
            if not mouse.start() or not teclado.start():
                with contextlib.suppress(Exception):
                    mouse.stop()
                    teclado.stop()
                self._desistiu = True
                logger.warning("tabela_no_jogo_sem_uinput")
                return False
            # O teclado é dono do que sai por tecla (o d-pad, o Círculo, o Quadrado
            # e o que ela escolheu): o mouse os cala, para a tecla não sair duas vezes.
            mouse.set_button_actions(
                self._do_mouse, self._calados | frozenset(self._do_teclado))
            teclado.set_bindings(resolve_key_bindings(
                {b: list(t) for b, t in self._do_teclado.items()}))
        except Exception as exc:
            self._desistiu = True
            logger.warning("tabela_no_jogo_abrir_falhou", err=str(exc))
            return False
        self._mouse, self._teclado = mouse, teclado
        logger.info("tabela_no_jogo_aberta")
        return True

    def soltar(self) -> None:
        """Solta tudo o que a tabela mantém apertado. Idempotente; nunca levanta."""
        if self._teclado is not None:
            with contextlib.suppress(Exception):
                self._teclado.dispatch(frozenset())
        if self._mouse is not None:
            with contextlib.suppress(Exception):
                self._mouse.dispatch(
                    lx=128, ly=128, rx=128, ry=128, l2=0, r2=0, buttons=frozenset())

    def fechar(self) -> None:
        """Solta e destrói os dois devices. Idempotente."""
        self.soltar()
        for dispositivo in (self._mouse, self._teclado):
            if dispositivo is not None:
                with contextlib.suppress(Exception):
                    dispositivo.stop()
        self._mouse = None
        self._teclado = None

    # -- o tique ---------------------------------------------------------

    def tick(self, daemon: Any, state: Any, botoes_do_p1: frozenset[str]) -> None:
        """Um tique COM o jogo: a união dos controles aperta as linhas da tabela."""
        if not self.ligada or not self._abrir(daemon):
            return
        from hefesto_dualsense4unix.daemon.subsystems.poll import gatilhos_de_cada_controle
        l2 = int(getattr(state, "l2_raw", 0) or 0)
        r2 = int(getattr(state, "r2_raw", 0) or 0)
        conjunto = botoes_com_os_gatilhos(botoes_do_p1, l2, r2)
        for botoes, outro_l2, outro_r2 in gatilhos_de_cada_controle(daemon).values():
            conjunto |= botoes_com_os_gatilhos(botoes, outro_l2, outro_r2)
        try:
            self._mouse.dispatch(
                lx=state.raw_lx,
                ly=state.raw_ly,
                rx=state.raw_rx,
                ry=state.raw_ry,
                l2=l2,
                r2=r2,
                buttons=conjunto,
            )
            self._teclado.dispatch(conjunto)
        except Exception as exc:
            logger.warning("tabela_no_jogo_dispatch_falhou", err=str(exc))


def trocar_a_tabela_no_jogo(daemon: DaemonProtocol, profile: Any) -> None:
    """Trava, a partir do perfil EFETIVO, o que a tabela faz com o jogo aberto.

    Chamado a cada ativação (e a cada `reaplicar`), ANTES de qualquer saída por
    lock manual: a chave é do perfil, não da supressão. Fecha a tabela anterior
    (solta o que ela segurava) e abre outra só quando a chave estiver ligada.
    """
    anterior = getattr(daemon, "_tabela_no_jogo", None)
    if anterior is not None:
        anterior.fechar()
    ligada = bool(getattr(profile, "tabela_no_jogo", None))
    daemon._tabela_no_jogo = TabelaNoJogo(
        getattr(profile, "button_actions", None),
        getattr(profile, "key_bindings", None),
        ligada=ligada,
    ) if ligada else None
    daemon._teclado_so_no_jogo = bool(getattr(profile, "teclado_so_no_jogo", None))


def despachar_no_jogo(
    daemon: DaemonProtocol,
    state: Any,
    emu_buttons: frozenset[str],
    *,
    no_jogo: bool,
) -> None:
    """O que o laço faz com o gamepad virtual despachando, e a saída dele.

    * Tabela ligada: ela age (mouse e teclado privados). O teclado do desktop
      não despacha junto, para a mesma tecla não sair duas vezes.
    * Só o teclado «Só dentro do jogo»: o teclado do desktop despacha daqui,
      mesmo com a emulação suprimida pelo perfil do jogo.
    * Ao sair do jogo (ou ao largar a chave) tudo é solto.
    """
    tabela = getattr(daemon, "_tabela_no_jogo", None)
    so_dentro = bool(getattr(daemon, "_teclado_so_no_jogo", False))
    estava = bool(getattr(daemon, "_estava_no_jogo", False))
    daemon._estava_no_jogo = no_jogo
    teclado = getattr(daemon, "_keyboard_device", None)
    if not no_jogo:
        if estava:
            if tabela is not None:
                tabela.soltar()
            if so_dentro and teclado is not None:
                with contextlib.suppress(Exception):
                    teclado.dispatch(frozenset())
        return
    if tabela is not None:
        tabela.tick(daemon, state, emu_buttons)
    elif so_dentro and teclado is not None:
        daemon._dispatch_keyboard_emulation(emu_buttons)


def mover_o_cursor_pelo_giro(daemon: DaemonProtocol, botoes_do_primario: frozenset[str]) -> None:
    """Na Navegação, o giro de quem está com a Mira acesa move o cursor."""
    try:
        from hefesto_dualsense4unix.core import roteador_de_movimento as roteador

        store = getattr(daemon, "store", None)
        arranjo = roteador.ativo(store)
        if arranjo is None:
            return
        from hefesto_dualsense4unix.daemon.subsystems.gamepad import (
            aplicar_o_movimento,
            primary_identity,
        )

        primario = primary_identity(daemon)
        centro = roteador.CENTRO_DO_EIXO
        for uniq in _pecas_da_navegacao(daemon, store, arranjo, primario):
            botoes = (
                botoes_do_primario
                if uniq == primario
                else _botoes_da_peca(daemon, store, arranjo, uniq)
            )
            aplicar_o_movimento(
                daemon,
                arranjo,
                uniq=uniq,
                lx=centro,
                ly=centro,
                rx=centro,
                ry=centro,
                botoes=botoes,
                na_navegacao=True,
            )
    except Exception as exc:
        logger.warning("mira_na_navegacao_falhou", err=str(exc))


def _pecas_da_navegacao(
    daemon: DaemonProtocol, store: Any, arranjo: Any, primario: str | None
) -> list[str]:
    """As peças que PODEM mirar agora: o primário primeiro, uma vez cada."""
    from hefesto_dualsense4unix.core import roteador_de_movimento as roteador
    from hefesto_dualsense4unix.core.virtual_motion import chave_de_sensor

    registro = getattr(daemon, "identity_registry", None)
    perguntar = getattr(registro, "snapshot_connected", None)
    conectados: set[str] | None = None
    if callable(perguntar):
        conectados = {chave_de_sensor(str(u)) for u in perguntar()}

    candidatas = list(roteador.pecas_que_miram(store))
    if arranjo.ligado and conectados is not None:
        candidatas.extend(sorted(conectados))
    vistas = {chave_de_sensor(primario)} if primario else set()
    pecas = [primario] if primario else []
    for chave in candidatas:
        if not chave or chave in vistas:
            continue
        if conectados is not None and chave not in conectados:
            continue
        vistas.add(chave)
        pecas.append(chave)
    return pecas


def _botoes_da_peca(daemon: DaemonProtocol, store: Any, arranjo: Any, uniq: str) -> frozenset[str]:
    """Os botões apertados AGORA num controle que não é o primário."""
    from hefesto_dualsense4unix.core import roteador_de_movimento as roteador

    peca = roteador.da_peca(store, uniq, arranjo)
    if peca is None or peca.gatilho is None:
        return frozenset()
    garantir = getattr(daemon, "_garantir_sensor_hub", None)
    if garantir is None:
        return frozenset()
    entradas = getattr(garantir(), "entradas", None)
    leitura = entradas(uniq) if callable(entradas) else None
    botoes = leitura.get("buttons") if isinstance(leitura, dict) else None
    return frozenset(str(b) for b in botoes) if isinstance(botoes, list) else frozenset()


def discard_touchpad_motion(daemon: DaemonProtocol) -> None:
    """Drena-e-descarta o movimento acumulado do touchpad (B4)."""
    reader = getattr(daemon, "_touchpad_reader", None)
    consume = getattr(reader, "consume_motion", None)
    if consume is not None:
        with contextlib.suppress(Exception):
            consume()


__all__ = [
    "MouseSubsystem",
    "discard_touchpad_motion",
    "dispatch_mouse",
    "start_mouse_emulation",
    "stop_mouse_emulation",
]
