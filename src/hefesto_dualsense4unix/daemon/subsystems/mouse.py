"""Subsystem Mouse — emulação de mouse+teclado virtual via uinput.

Encapsula a criação, despacho e destruição do dispositivo virtual UinputMouseDevice.
Implementa o protocolo Subsystem e expõe funções utilitárias start_mouse / stop_mouse.

O despacho de eventos (dispatch_mouse) é chamado pelo poll loop a cada tick.
"""
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
        """Cria o dispositivo uinput se mouse_emulation_enabled=True.

        Idempotente: retorna sem erro se o dispositivo já existe.
        """
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
                # FEAT-MOUSE-CURSOR-FEEL-01: o device integra px/s pelo período
                # real do tick — passa o poll_hz configurado (não hardcodar 60).
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
    """Cria device virtual de mouse+teclado (FEAT-MOUSE-01). Idempotente.

    Retorna True se ativo ao final; False se falhou ao iniciar.
    """
    if daemon._mouse_device is not None:
        return True
    try:
        from hefesto_dualsense4unix.integrations.uinput_mouse import UinputMouseDevice

        device = UinputMouseDevice(
            mouse_speed=daemon.config.mouse_speed,
            scroll_speed=daemon.config.mouse_scroll_speed,
            # FEAT-MOUSE-CURSOR-FEEL-01: período real do tick p/ integrar px/s.
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
    # FEAT-MOUSE-PERSIST-01 + FEAT-MOUSE-CURSOR-FEEL-01 (A5): persiste toggle E
    # velocidades p/ sobreviver a restart/reboot (antes só o toggle era salvo e
    # speed/scroll voltavam a 6/1 a cada reinício do daemon).
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
    """Para e descarta o dispositivo virtual. Idempotente.

    ``persist=False`` (HARM-06) desliga o device SEM tocar na preferência
    persistida — é o que a exclusão mútua do gamepad usa. Desligar o mouse
    porque o controle foi para o jogo não é a usuária dizendo "não quero mouse";
    gravar "off" ali fazia o round-trip desktop->gamepad->desktop apagar a
    preferência e o controle voltava sem função nenhuma.
    Espelha `stop_gamepad_emulation(persist=...)`.
    """
    if daemon._mouse_device is None:
        return
    with contextlib.suppress(Exception):
        daemon._mouse_device.stop()
    daemon._mouse_device = None
    daemon.config.mouse_emulation_enabled = False
    # FEAT-MOUSE-PERSIST-01: grava "off" para não religar no próximo boot.
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
    # já gateia por mouse_device != None e not _emulation_suppressed.
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


def mover_o_cursor_pelo_giro(daemon: DaemonProtocol, botoes_do_primario: frozenset[str]) -> None:
    """Na Navegação, o giro de quem está com a Mira acesa move o cursor.

    A-MIRA-NA-NAVEGACAO-01 (24/09/2026), pela frase dela: *"A exceção do nativo
    todo o resto deve ter mira Virtual"*.  <!-- noqa-acento: citação literal dela -->
    Na Navegação não há controle virtual — o `dispatch_gamepad` volta no
    `device is None` —, e o chip da Mira acendia sem mover nada. Este é o único
    tique da Navegação, e é daqui que o giro vai ao cursor.

    O MOTOR É O MESMO, chamado e não copiado: `gamepad.aplicar_o_movimento`
    com ``na_navegacao=True``. A sensibilidade, o «Ignorar tremor até», o «Só
    enquanto eu segurar», os dois «Inverter» e o interruptor do Giroscópio de
    cada controle valem igual.

    QUEM É DONO DO CURSOR NA NAVEGAÇÃO, medido: o PRIMÁRIO. O `state` que chega
    aqui é só o dele — o analógico esquerdo move, o direito rola, os botões
    clicam —, e os outros controles não mexem no cursor por analógico. A Mira é
    por controle e vale nos quatro: cada peça com a Mira acesa SOMA o próprio
    giro ao MESMO cursor, porque o mouse é um só, como duas mãos no mesmo
    mouse. Cada peça drena o PRÓPRIO leitor, e nenhum giro conta duas vezes.

    QUAIS PEÇAS: ver `_pecas_da_navegacao`. Os botões do «Só enquanto eu
    segurar» de quem não é o primário vêm do leitor de entradas do hub, sem
    grab; sem leitura, o botão está solto e a mira fica parada.

    Sem mira em peça nenhuma, o custo é o do `roteador.ativo`: dois `getattr`.
    NUNCA LEVANTA — o tique da Navegação leva o cursor, os cliques e o teclado.
    """
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
    """As peças que PODEM mirar agora: o primário primeiro, uma vez cada.

    O PRIMÁRIO VAI COM O `uniq` DO BACKEND, como o `dispatch_gamepad` o passa;
    os outros vão pela chave da peça (`chave_de_sensor`, os 12 hex), que é a
    grafia com que o hub os conhece (`discover_dualsense_motion_evdevs`, MAC
    normalizado) e com que o registro de identidade guarda os conectados.

    Entram as peças com a Mira acesa e, quando a mira é do perfil inteiro,
    todo controle conectado. Com o registro de identidade de pé, só o
    CONECTADO entra: uma peça com a Mira acesa no perfil e fora da mesa
    pediria ao hub, a cada tique, um leitor que não há. Sem registro (o
    `FakeController`), vale a lista das peças.

    A peça que não mira sai no portão da peça (`roteador.da_peca`), e só drena
    quando a mesa inteira mira — a regra de sempre.
    """
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
    """Os botões apertados AGORA num controle que não é o primário.

    Só se pergunta quando o botão importa — a peça com «Só enquanto eu
    segurar» —, e a pergunta é ao leitor de entradas do hub, que abre o nó de
    gamepad SEM grab (o jogo e o computador continuam vendo o controle). A
    primeira pergunta não tem resposta ainda (o leitor nasce na volta seguinte
    da manutenção do hub): até lá o botão está solto, e a mira fica parada em
    vez de andar sem o botão que ela escolheu.
    """
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
    """Drena-e-descarta o movimento acumulado do touchpad (B4).

    Chamado pelo poll loop quando a emulação está suprimida (modo-jogo) ou sem
    device de mouse: sem isso, o delta acumularia enquanto a emulação está
    desligada e o cursor "pularia" o acúmulo ao religar.
    """
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
