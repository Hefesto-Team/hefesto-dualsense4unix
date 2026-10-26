"""Subsystem Mouse — emulação de mouse+teclado virtual via uinput."""
from __future__ import annotations

import contextlib
import time
from typing import TYPE_CHECKING, Any

from hefesto_dualsense4unix.core import acoes_de_botao as acoes
from hefesto_dualsense4unix.core import ativacao_de_botao, filtro_de_botao
from hefesto_dualsense4unix.utils.logging_config import get_logger

if TYPE_CHECKING:
    from hefesto_dualsense4unix.daemon.protocols import DaemonProtocol

logger = get_logger(__name__)


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


def _entregar_o_ajuste(daemon: Any, device: Any) -> None:
    """Entrega ao device o ajuste do cursor que vale AGORA (e a época dele). Nunca levanta."""
    try:
        from hefesto_dualsense4unix.integrations.uinput_mouse import ajuste_ativo

        ajuste, epoca = ajuste_ativo(getattr(daemon, "store", None))
        device.definir_ajuste(ajuste, epoca)
    except Exception as exc:
        logger.warning("cursor_ajuste_falhou", err=str(exc))


def soltar_o_mouse(daemon: Any) -> None:
    """Solta o clique travado do mouse virtual, no desktop e na tabela. Nunca levanta."""
    tabela = getattr(daemon, "_tabela_no_jogo", None)
    for device in (getattr(daemon, "_mouse_device", None), getattr(tabela, "_mouse", None)):
        _soltar_o_travado(device)


def soltar_o_cursor(daemon: Any) -> None:
    """Solta o clique travado e as teclas do analógico, no desktop e na tabela, de quem perdeu
    o controle, suspendeu a emulação ou saiu do jogo. Nunca levanta."""
    soltar_o_mouse(daemon)
    soltar_as_teclas_do_analogico(daemon)


def _soltar_o_travado(device: Any) -> None:
    """Solta o clique travado de um mouse virtual (ou de nenhum). Nunca levanta."""
    solta = getattr(device, "soltar_o_clique_travado", None)
    if solta is not None:
        with contextlib.suppress(OSError):
            solta()


def dispatch_mouse(daemon: DaemonProtocol, state: Any, buttons_pressed: frozenset[str]) -> None:
    """Traduz o estado do controle em eventos de mouse+teclado virtual.

    Chamado pelo poll loop a cada tick se _mouse_device não for None.
    Não relança exceções — falhas são logadas como warning.
    """
    device = daemon._mouse_device
    if device is None:
        return
    _entregar_o_ajuste(daemon, device)
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
    reader = getattr(daemon, "_touchpad_reader", None)
    consume = getattr(reader, "consume_motion", None)
    if consume is not None:
        try:
            dx, dy = consume()
            if dx or dy:
                device.emit_touchpad_move(dx, dy)
        except Exception as exc:
            logger.warning("touchpad_move_dispatch_failed", err=str(exc))
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


ESPACO_DA_TABELA = "tabela"


def _agora() -> float:
    """O relógio do laço da tabela (um nome só para os testes trocarem)."""
    return time.monotonic()


def _com_o_modo(
    store: Any, uniq: str | None, botoes: frozenset[str], l2: int, r2: int
) -> tuple[frozenset[str], int, int]:
    """O filtro e o modo (alternar, repetir, longo, duplo) deste controle, ANTES de a tabela somar.

    A tabela lê os botões como o controle os aperta (sem a troca de botões), então guarda
    o estado dela à parte do pad virtual: o filtro primeiro, como no pad, e o modo depois.
    """
    agora = _agora()
    botoes, l2, r2, _ = filtro_de_botao.traduzir(
        store, uniq, botoes, l2, r2, agora, espaco=ESPACO_DA_TABELA)
    botoes, l2, r2, _ = ativacao_de_botao.traduzir(
        store, uniq, botoes, l2, r2, agora, espaco=ESPACO_DA_TABELA)
    return botoes, l2, r2


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
      ativação; a chave não obedece à Função do teclado nem à supressão do perfil do jogo,
      e cala com «Suspender mouse e teclado» (`despachar_no_jogo`).
    """

    def __init__(self, button_actions: Any, key_bindings: Any, *, ligada: bool) -> None:
        from hefesto_dualsense4unix.core.acoes_de_botao import botoes_calados

        self.ligada = bool(ligada)
        self._do_mouse, self._do_teclado, _sem_dono = acoes.resolver(button_actions, key_bindings)
        self._calados = botoes_calados(button_actions, key_bindings)
        self._teclas_dos_analogicos = acoes.teclas_dos_analogicos(self._do_mouse)
        self._mouse: Any = None
        self._teclado: Any = None
        self._desistiu = False
        self._store: Any = None

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
            from hefesto_dualsense4unix.daemon.subsystems.keyboard import (
                atendente_do_teclado_na_tela,
            )

            teclado.virtual_token_callback = atendente_do_teclado_na_tela(daemon)
            if not mouse.start() or not teclado.start():
                with contextlib.suppress(Exception):
                    mouse.stop()
                with contextlib.suppress(Exception):
                    teclado.stop()
                self._desistiu = True
                logger.warning("tabela_no_jogo_sem_uinput")
                return False
            mouse.set_button_actions(
                self._do_mouse, self._calados | frozenset(self._do_teclado))
            ligacoes = resolve_key_bindings(
                {b: list(t) for b, t in self._do_teclado.items()})
            for nome, tecla in self._teclas_dos_analogicos.items():
                ligacoes[nome] = (tecla,)
            teclado.set_bindings(ligacoes)
        except Exception as exc:
            self._desistiu = True
            logger.warning("tabela_no_jogo_abrir_falhou", err=str(exc))
            return False
        self._mouse, self._teclado = mouse, teclado
        logger.info("tabela_no_jogo_aberta")
        return True

    def soltar(self) -> None:
        """Solta tudo o que a tabela mantém apertado. Idempotente; nunca levanta."""
        ativacao_de_botao.esquecer(self._store, espaco=ESPACO_DA_TABELA)
        filtro_de_botao.esquecer(self._store, espaco=ESPACO_DA_TABELA)
        if self._teclado is not None:
            with contextlib.suppress(Exception):
                self._teclado.dispatch(frozenset())
        if self._mouse is not None:
            with contextlib.suppress(Exception):
                self._mouse.dispatch(
                    lx=128, ly=128, rx=128, ry=128, l2=0, r2=0, buttons=frozenset())
            solta = getattr(self._mouse, "soltar_o_clique_travado", None)
            if solta is not None:
                with contextlib.suppress(OSError):
                    solta()

    def fechar(self) -> None:
        """Solta e destrói os dois devices. Idempotente."""
        self.soltar()
        for dispositivo in (self._mouse, self._teclado):
            if dispositivo is not None:
                with contextlib.suppress(Exception):
                    dispositivo.stop()
        self._mouse = None
        self._teclado = None

    def tick(self, daemon: Any, state: Any, botoes_do_p1: frozenset[str]) -> None:
        """Um tique COM o jogo: a união dos controles aperta as linhas da tabela."""
        if not self.ligada or not self._abrir(daemon):
            return
        from hefesto_dualsense4unix.daemon.subsystems.poll import gatilhos_de_cada_controle
        l2 = int(getattr(state, "l2_raw", 0) or 0)
        r2 = int(getattr(state, "r2_raw", 0) or 0)
        store = self._store = getattr(daemon, "store", None)
        com_modo = ativacao_de_botao.alguma(store) or filtro_de_botao.alguma(store)
        if com_modo:
            from hefesto_dualsense4unix.daemon.subsystems.gamepad import primary_identity

            botoes_do_p1, l2, r2 = _com_o_modo(
                store, primary_identity(daemon), botoes_do_p1, l2, r2)
        conjunto = botoes_com_os_gatilhos(botoes_do_p1, l2, r2)
        outros = gatilhos_de_cada_controle(daemon)
        for uniq, (botoes, outro_l2, outro_r2) in outros.items():
            if com_modo:
                botoes, outro_l2, outro_r2 = _com_o_modo(store, uniq, botoes, outro_l2, outro_r2)
            conjunto |= botoes_com_os_gatilhos(botoes, outro_l2, outro_r2)
        _entregar_o_ajuste(daemon, self._mouse)
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
            from hefesto_dualsense4unix.integrations.uinput_mouse import botoes_do_cursor

            do_teclado = conjunto - botoes_do_cursor(store)
            self._teclado.dispatch(do_teclado | self._teclas_apertadas(daemon, state, outros))
        except Exception as exc:
            logger.warning("tabela_no_jogo_dispatch_falhou", err=str(exc))

    def _teclas_apertadas(
        self, daemon: Any, state: Any, outros: Any
    ) -> frozenset[str]:
        """As direções dos analógicos que viraram tecla, apertadas AGORA por QUALQUER controle."""
        if not self._teclas_dos_analogicos:
            return frozenset()
        return acoes.direcoes_apertadas(
            self._teclas_dos_analogicos, eixos_de_cada_controle(daemon, state, outros))


def eixos_de_cada_controle(
    daemon: Any, state: Any, outros: Any
) -> list[tuple[int, int, int, int]]:
    """Os analógicos `(lx, ly, rx, ry)` de cada controle lido neste tique.

    O primeiro é o do posto de P1 (`state`, o que o laço leu); os demais, dos mesmos leitores
    e com a mesma regra de `poll.gatilhos_de_cada_controle`: o co-op (`live_snapshots`) ou o
    leitor passivo do `SensorHub`, e quem o co-op numera sem o vpad de pé fica de fora (o leitor
    passivo veria o último valor, e a tecla ficaria presa). `outros` são os MACs dos demais
    controles (chaves de `gatilhos_de_cada_controle`). Nunca levanta.
    """
    from hefesto_dualsense4unix.daemon.subsystems import poll

    centro = acoes.CENTRO_DO_ANALOGICO
    maos = [(
        int(getattr(state, "raw_lx", centro)), int(getattr(state, "raw_ly", centro)),
        int(getattr(state, "raw_rx", centro)), int(getattr(state, "raw_ry", centro)),
    )]
    if not outros:
        return maos
    try:
        vivos = poll._snapshots_do_coop(daemon)
        sem_leitor = [u for u in outros if u not in vivos]
        sentados = poll._sentados_no_coop(daemon) if sem_leitor else frozenset()
        passivos = [u for u in sem_leitor if u not in sentados]
        entradas: Any = poll._entradas_do_hub(daemon) if passivos else None
        for uniq in outros:
            if uniq in vivos:
                snap = vivos[uniq]
                leitura: Any = {c: getattr(snap, c, centro) for c in ("lx", "ly", "rx", "ry")}
            elif uniq in passivos and callable(entradas):
                leitura = entradas(uniq)
            else:
                continue
            if isinstance(leitura, dict):
                maos.append(tuple(  # type: ignore[arg-type]
                    int(leitura.get(c, centro)) for c in ("lx", "ly", "rx", "ry")))
    except Exception as exc:
        logger.debug("analogicos_dos_outros_sem_leitura", err=str(exc))
    return maos


class TeclasDoAnalogicoNoDesktop:
    """O analógico em «Teclas WASD» ou «Setas» agindo no DESKTOP, sem o jogo aberto.

    Com o jogo aberto quem age é a :class:`TabelaNoJogo`; fora dele o laço do daemon chama
    esta (com a emulação de mouse ligada ou não), pela MESMA tradução
    (`acoes_de_botao.direcoes_apertadas`), num teclado PRIVADO. A tecla é a união dos controles;
    cursor e rolagem seguem do primário. Nasce do perfil EFETIVO
    (`trocar_a_tabela_no_jogo`); trocar de perfil ou fechar solta tudo.
    """

    def __init__(self, button_actions: Any, key_bindings: Any) -> None:
        do_mouse, _teclado, _sem_dono = acoes.resolver(button_actions, key_bindings)
        self._teclas = acoes.teclas_dos_analogicos(do_mouse)
        self._teclado: Any = None
        self._desistiu = False

    @property
    def ativa(self) -> bool:
        """Algum analógico escolheu teclas neste perfil?"""
        return bool(self._teclas)

    def _abrir(self) -> bool:
        if self._teclado is not None:
            return True
        if self._desistiu:
            return False
        try:
            from hefesto_dualsense4unix.integrations.uinput_keyboard import (
                UinputKeyboardDevice,
            )

            teclado = UinputKeyboardDevice()
            if not teclado.start():
                self._desistiu = True
                logger.warning("teclas_do_analogico_sem_uinput")
                return False
            teclado.set_bindings({nome: (tecla,) for nome, tecla in self._teclas.items()})
        except Exception as exc:
            self._desistiu = True
            logger.warning("teclas_do_analogico_abrir_falhou", err=str(exc))
            return False
        self._teclado = teclado
        return True

    def tick(self, daemon: Any, state: Any) -> None:
        """Um tique do desktop: aperta e solta as teclas pela deflexão de todos os controles."""
        if not self._teclas or not self._abrir():
            return
        from hefesto_dualsense4unix.daemon.subsystems.poll import gatilhos_de_cada_controle

        try:
            outros = gatilhos_de_cada_controle(daemon)
            self._teclado.dispatch(acoes.direcoes_apertadas(
                self._teclas, eixos_de_cada_controle(daemon, state, outros)))
        except Exception as exc:
            logger.warning("teclas_do_analogico_dispatch_falhou", err=str(exc))

    def soltar(self) -> None:
        """Solta as teclas que o analógico segura. Idempotente; nunca levanta."""
        if self._teclado is not None:
            try:
                self._teclado.dispatch(frozenset())
            except Exception as exc:
                logger.debug("teclas_do_analogico_soltar_falhou", err=str(exc))

    def fechar(self) -> None:
        """Solta e destrói o teclado. Idempotente."""
        self.soltar()
        if self._teclado is not None:
            try:
                self._teclado.stop()
            except Exception as exc:
                logger.debug("teclas_do_analogico_fechar_falhou", err=str(exc))
        self._teclado = None


def teclas_do_analogico_no_desktop(daemon: Any, state: Any) -> None:
    """O laço do desktop: as teclas do analógico, se o perfil efetivo as escolheu.

    As teclas do analógico são do teclado: a «Função do teclado» «Desativado» (sem
    `_keyboard_device`) e «Só dentro do jogo» calam também estas no desktop.
    """
    atendente = getattr(daemon, "_teclas_do_analogico", None)
    if atendente is None:
        return
    if getattr(daemon, "_keyboard_device", None) is None or getattr(
            daemon, "_teclado_so_no_jogo", False):
        atendente.soltar()
        return
    atendente.tick(daemon, state)


def soltar_as_teclas_do_analogico(daemon: Any) -> None:
    """Solta as teclas do analógico no desktop (o laço não as despacha neste tique)."""
    atendente = getattr(daemon, "_teclas_do_analogico", None)
    if atendente is not None:
        atendente.soltar()


def fechar_as_teclas_do_analogico(daemon: Any) -> None:
    """Fecha o teclado das teclas do analógico no desktop (a troca de perfil, a parada)."""
    atendente = getattr(daemon, "_teclas_do_analogico", None)
    if atendente is not None:
        atendente.fechar()
    daemon._teclas_do_analogico = None


def trocar_a_tabela_no_jogo(daemon: Any, profile: Any) -> None:
    """Trava, a partir do perfil EFETIVO, o que a tabela faz com o jogo aberto.

    Chamado a cada ativação (e a cada `reaplicar`), ANTES de qualquer saída por
    lock manual: a chave é do perfil, não da supressão. Fecha a tabela anterior
    (solta o que ela segurava) e abre outra só quando a chave estiver ligada.
    """
    anterior = getattr(daemon, "_tabela_no_jogo", None)
    if anterior is not None:
        anterior.fechar()
    fechar_as_teclas_do_analogico(daemon)
    do_desktop = TeclasDoAnalogicoNoDesktop(
        getattr(profile, "button_actions", None), getattr(profile, "key_bindings", None))
    daemon._teclas_do_analogico = do_desktop if do_desktop.ativa else None
    ligada = bool(getattr(profile, "tabela_no_jogo", None))
    daemon._tabela_no_jogo = TabelaNoJogo(
        getattr(profile, "button_actions", None),
        getattr(profile, "key_bindings", None),
        ligada=ligada,
    ) if ligada else None
    daemon._teclado_so_no_jogo = bool(getattr(profile, "teclado_so_no_jogo", None))
    daemon._teclado_sempre = bool(getattr(profile, "teclado_sempre", None))


def _suspenso_por_ela(daemon: Any) -> bool:
    """A emulação está suspensa por gesto do usuário (e não pelo perfil do jogo)?"""
    return bool(getattr(daemon, "_emulation_suppressed", False)) and not bool(
        getattr(daemon, "_suppress_from_profile", False))


def despachar_no_jogo(
    daemon: Any,
    state: Any,
    emu_buttons: frozenset[str],
    *,
    no_jogo: bool,
) -> None:
    """O que o laço faz com o gamepad virtual despachando, e a saída dele.

    * Tabela ligada: ela age (mouse e teclado privados). O teclado do desktop
      não despacha junto, para a mesma tecla não sair duas vezes.
    * O teclado «Só dentro do jogo» ou «Sempre»: o teclado do desktop despacha daqui,
      mesmo com a emulação suprimida pelo perfil do jogo.
    * Ao sair do jogo (ou ao largar a chave) tudo é solto.
    * «Suspender mouse e teclado» (o gesto, a interface, o IPC) cala os dois aqui
      também: a supressão que ELA ligou vale com o jogo aberto. A do perfil do jogo
      não cala, porque o jogo aberto é justamente onde a chave e o «Só dentro» agem.
    """
    if no_jogo:
        _soltar_o_travado(getattr(daemon, "_mouse_device", None))
        soltar_as_teclas_do_analogico(daemon)
    if no_jogo and _suspenso_por_ela(daemon):
        no_jogo = False
    tabela = getattr(daemon, "_tabela_no_jogo", None)
    so_dentro = bool(getattr(daemon, "_teclado_so_no_jogo", False)) or bool(
        getattr(daemon, "_teclado_sempre", False))
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
    "discard_touchpad_motion",
    "dispatch_mouse",
    "fechar_as_teclas_do_analogico",
    "soltar_as_teclas_do_analogico",
    "soltar_o_cursor",
    "soltar_o_mouse",
    "start_mouse_emulation",
    "stop_mouse_emulation",
]
