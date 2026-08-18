"""Subsystem Keyboard — emulação de teclado virtual via uinput.

Introduzido em FEAT-KEYBOARD-EMULATOR-01. Encapsula criação, despacho e
destruição do `UinputKeyboardDevice`. Ativado por padrão: a instalação do
daemon já espera que os 4 botões default (Options/Share/L1/R1) emitam teclas
correspondentes assim que o serviço sobe.

EMULACAO-NO-JOGO-01 (29/07) corrigiu a assimetria que este cabeçalho declarava:
o teclado NÃO tinha toggle explícito nenhum — nem gate de criação, nem flag em
disco, nem IPC —, e por isso o R1 (Alt+Tab, `core/keyboard_mappings.py`)
trocava de aplicativo no meio da partida dela. Agora `keyboard_emulation_enabled`
é respeitado no gate de criação abaixo (molde de `subsystems/mouse.py`), a
preferência é persistida em `keyboard_emulation.flag`
(`utils/session.py:save_keyboard_emulation`) e o runtime alterna por
`keyboard.emulation.set`. O default continua LIGADO — desligar tira também o
teclado virtual do sistema (L3/R3) e as três regiões do touchpad.

Wire-up no Daemon (armadilha A-07 — 3 pontos):
  1. Slot `_keyboard_device: Any = None` em `Daemon` (lifecycle.py).
  2. `start_keyboard_emulation(daemon)` chamado em `Daemon.run()` antes de
     `_stop_event.wait()`, quando `config.keyboard_emulation_enabled` for True.
  3. `dispatch_keyboard(daemon, buttons_pressed)` chamado no `_poll_loop`
     reusando o mesmo `buttons_pressed` já obtido via `_evdev_buttons_once()`
     (armadilha A-09 — snapshot único por tick).
  4. `shutdown` em `connection.py` zera o slot e chama `stop()` para liberar
     teclas pressionadas antes do destroy (evita ghost-keys).
"""
from __future__ import annotations

import contextlib
import os
import shutil
import subprocess
import time
from typing import TYPE_CHECKING

from hefesto_dualsense4unix.core.keyboard_mappings import TOKEN_CLOSE_OSK, TOKEN_OPEN_OSK
from hefesto_dualsense4unix.utils.logging_config import get_logger

if TYPE_CHECKING:
    from hefesto_dualsense4unix.daemon.protocols import DaemonProtocol

logger = get_logger(__name__)

# TECLADO-QUE-NAO-DIGITA-01 — o CONTRATO DE NOMES.
#
# Estas duas constantes são as mesmas do `scripts/install_osk.sh` (quem
# instala) e do `scripts/doctor.sh` (quem confere), e o
# `scripts/check_packaging_parity.sh` cobra a coincidência dos três. Sem esse
# amarre, o produto pode instalar um binário e procurar outro — e os três
# passam sozinhos, cada um coerente consigo mesmo.
_OSK_BIN_WAYLAND = "wvkbd-mobintl"
_OSK_BIN_X11 = "onboard"

# Candidatos de teclado virtual. Cada string aqui é um `shutil.which`-ável; o
# argv completo para spawn fica em `_OSK_SPAWN_ARGS`.
#
# A ORDEM FIXA ERA UM DEFEITO, e ele estava aqui desde sempre: era
# `("onboard", "wvkbd-mobintl")`, com o onboard PRIMEIRO. Numa sessão Wayland
# com os dois instalados, o daemon escolheria o onboard — que digita por XTEST
# (`Depends: libxtst6`) e portanto só alcança clientes XWayland. A janela nativa
# em foco não receberia nada: o teclado ABRE e não DIGITA, que é pior que não
# abrir, porque parece que funcionou. Quem decide agora é `_osk_candidatos()`,
# pela sessão viva.
_OSK_CANDIDATES: tuple[str, ...] = (_OSK_BIN_WAYLAND, _OSK_BIN_X11)
_OSK_SPAWN_ARGS: dict[str, list[str]] = {
    _OSK_BIN_X11: [_OSK_BIN_X11],
    # `--layer 0` ancora wvkbd no bottom (padrão); mantém footprint mínimo.
    _OSK_BIN_WAYLAND: [_OSK_BIN_WAYLAND],
}

#: Janela (s) do cache de resolução do binário. O `_resolve` era um cache
#: PERMANENTE (`_resolved_checked` nunca voltava a False), e isso tinha um custo
#: concreto: ela roda `sudo apt install wvkbd` com o daemon no ar, aperta o L3 e
#: continua não acontecendo nada — o daemon decidiu "não existe" antes de o
#: pacote existir e não reveria a decisão até o próximo start. É a armadilha do
#: "daemon vivo mais velho que o código" na forma de PATH. Dez segundos é
#: barato: o `shutil.which` só é chamado quando o L3 é apertado (não no poll
#: loop) e no `disponivel()` que o `state_full` consulta.
_OSK_RESOLVE_TTL_SEG = 10.0


def _osk_candidatos() -> tuple[str, ...]:
    """Candidatos na ordem que FUNCIONA na sessão gráfica de agora.

    `WAYLAND_DISPLAY` primeiro, `DISPLAY` só depois — e essa ordem é o miolo da
    correção. Numa sessão Wayland com XWayland os DOIS estão setados (medido em
    10/08/2026 no ambiente do daemon vivo desta máquina: `WAYLAND_DISPLAY=
    wayland-1` E `DISPLAY=:1`, importados pelo `ExecStartPre` da unit), então
    olhar `DISPLAY` antes classificaria toda sessão Wayland moderna como X11.

    O daemon enxerga essas variáveis porque a unit faz
    `systemctl --user import-environment WAYLAND_DISPLAY DISPLAY`; isso não é
    detalhe de conforto, é o que permite ao `wvkbd-mobintl` que nós spawnamos
    achar o compositor — o filho herda este mesmo ambiente.

    A lista sempre traz os DOIS: se o preferido não estiver instalado, o outro
    ainda é melhor que nada (num X11 sem onboard, um wvkbd instalado não abre —
    mas aí o `open()` falha e loga, em vez de o produto fingir que não há nada).
    """
    if os.environ.get("WAYLAND_DISPLAY") or os.environ.get("XDG_SESSION_TYPE") == "wayland":
        return (_OSK_BIN_WAYLAND, _OSK_BIN_X11)
    if os.environ.get("DISPLAY") or os.environ.get("XDG_SESSION_TYPE") == "x11":
        return (_OSK_BIN_X11, _OSK_BIN_WAYLAND)
    # Sessão desconhecida (daemon headless, CI): a aposta é declarada — vale a
    # de Wayland, que é o padrão de todo desktop atual.
    return (_OSK_BIN_WAYLAND, _OSK_BIN_X11)


#: Cache (instante, resposta) da sonda de módulo abaixo. Lista de um elemento
#: para não precisar de `global`.
_OSK_SONDA: list[tuple[float, bool]] = [(float("-inf"), False)]


def osk_disponivel_no_sistema() -> bool:
    """Há teclado na tela instalado nesta máquina, agora?

    Existe para quem precisa da resposta SEM ter um `_OSKController` à mão — o
    `state_full` do daemon, que a publica para a janela. A janela não pode fazer
    o `shutil.which` por conta própria: num Flatpak ela olharia dentro do
    sandbox e responderia sobre uma máquina que não é a da usuária.

    Mesmo TTL do `_OSKController._resolve` e pelo mesmo motivo (instalar o
    pacote com o daemon no ar tem de passar a valer sem restart), e mesmo custo:
    um `shutil.which` a cada 10 s, no máximo, mesmo com o `state_full` a 20 Hz.
    """
    agora = time.monotonic()
    quando, valor = _OSK_SONDA[0]
    if agora - quando < _OSK_RESOLVE_TTL_SEG:
        return valor
    valor = any(shutil.which(candidato) for candidato in _osk_candidatos())
    _OSK_SONDA[0] = (agora, valor)
    return valor


class _OSKController:
    """Gerencia o processo do teclado virtual (onboard/wvkbd-mobintl).

    Detecta o binário disponível apenas 1x (cache em `_resolved_bin`); warning
    é logado uma única vez se nenhum dos candidatos estiver instalado. Abrir
    quando já há processo ativo é no-op (evita stack de janelas sobrepostas).
    Fechar sem processo ativo também é no-op.
    """

    def __init__(self) -> None:
        self._resolved_bin: str | None = None
        self._resolved_checked: bool = False
        self._resolved_em: float = 0.0
        self._process: subprocess.Popen[bytes] | None = None
        self._missing_warned: bool = False

    def _resolve(self) -> str | None:
        """Primeiro binário de teclado na tela que existe, na ordem da sessão.

        O cache tem PRAZO (`_OSK_RESOLVE_TTL_SEG`) em vez de ser eterno: ver a
        constante para o porquê — sem prazo, instalar o pacote com o daemon no
        ar não tinha efeito nenhum até o próximo start, e o sintoma para ela é
        idêntico ao de não ter instalado.
        """
        agora = time.monotonic()
        if self._resolved_checked and (agora - self._resolved_em) < _OSK_RESOLVE_TTL_SEG:
            return self._resolved_bin
        self._resolved_em = agora
        self._resolved_checked = True
        for candidate in _osk_candidatos():
            path = shutil.which(candidate)
            if path:
                self._resolved_bin = candidate
                return candidate
        self._resolved_bin = None
        return None

    def disponivel(self) -> bool:
        """True se há programa de teclado na tela instalado (cache do `_resolve`).

        TECLADO-QUE-NAO-DIGITA-01: quem quiser dizer na tela que L3 não tem o
        que abrir pergunta aqui, em vez de repetir o `shutil.which`.
        """
        return self._resolve() is not None

    def _avisar_ausencia(self) -> None:
        """L3 sem teclado na tela deixa de ser silêncio (TECLADO-QUE-NAO-DIGITA-01).

        O ramo "nenhum candidato instalado" logava um `warning` e retornava —
        e um warning no journal não é resposta a quem acabou de apertar um
        botão. Medido na máquina dela em 09/08/2026: nem `onboard` nem
        `wvkbd-mobintl` existem, e `l3` é justamente o ÚNICO caminho do produto
        para ESCREVER texto com o controle (nenhum binding de fábrica digita
        letra). O aperto sumia inteiro.

        O log continua uma vez só (`_missing_warned`); a notificação tem
        dedup próprio (`once_key` do `notify`), então ela sobrevive a um
        `_OSKController` novo dentro do mesmo daemon sem virar rajada.
        Best-effort de ponta a ponta: sem jeepney/sem servidor de notificação o
        `notify` devolve False e nada quebra.
        """
        # `_osk_candidatos()` e não `_OSK_CANDIDATES`: a frase é "instale X ou
        # Y", e QUAL vem primeiro é a diferença entre um conselho que resolve e
        # um que faz ela instalar o programa que abre sem digitar. Em Wayland o
        # primeiro nome tem de ser o wvkbd.
        candidatos = list(_osk_candidatos())
        if not self._missing_warned:
            logger.warning(
                "osk_binary_missing",
                candidates=candidatos,
            )
            self._missing_warned = True
        with contextlib.suppress(Exception):
            from hefesto_dualsense4unix.integrations.desktop_notifications import (
                notify_teclado_na_tela_ausente,
            )

            notify_teclado_na_tela_ausente(candidatos)

    def open(self) -> None:
        if self._process is not None and self._process.poll() is None:
            return
        resolved = self._resolve()
        if resolved is None:
            self._avisar_ausencia()
            return
        args = _OSK_SPAWN_ARGS[resolved]
        try:
            self._process = subprocess.Popen(
                args,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            logger.info("osk_opened", binary=resolved, pid=self._process.pid)
        except Exception as exc:
            logger.warning("osk_open_failed", binary=resolved, err=str(exc))
            self._process = None

    def close(self) -> None:
        proc = self._process
        if proc is None:
            return
        if proc.poll() is not None:
            self._process = None
            return
        try:
            proc.terminate()
            logger.info("osk_closed", pid=proc.pid)
        except Exception as exc:
            logger.warning("osk_close_failed", err=str(exc))
        self._process = None

    def dispatch_token(self, token: str, phase: str) -> None:
        """Callback registrado no UinputKeyboardDevice.

        Só atua em press (edge-triggered pull-to-focus). Release é no-op para
        evitar fechar no release de L3 logo após o press abrir.
        """
        if phase != "press":
            return
        if token == TOKEN_OPEN_OSK:
            self.open()
        elif token == TOKEN_CLOSE_OSK:
            self.close()
        else:
            logger.warning("osk_token_desconhecido", token=token)


def start_keyboard_emulation(daemon: DaemonProtocol) -> bool:
    """Cria device virtual de teclado + touchpad reader. Idempotente.

    Retorna True se ativo ao final; False se falhou ao iniciar o device
    principal. O `TouchpadReader` é best-effort: se o device evdev do
    touchpad não existir (controle BT, kernel velho), não quebra o fluxo.

    EMULACAO-NO-JOGO-01: o gate de `keyboard_emulation_enabled` mora AQUI,
    espelhando `subsystems/mouse.py` (`if not cfg.mouse_emulation_enabled:
    return`). É o que dá dentes ao interruptor: desligada, o device NÃO nasce,
    e o gate de despacho do poll loop (`_keyboard_device is not None`) fecha
    sozinho — a mesma mecânica que fazia o mouse dela estar honestamente
    desligado enquanto o teclado emitia Alt+Tab dentro da partida. `getattr`
    defensivo em dois níveis: dublê de teste sem `config` (ou sem o campo)
    segue com o comportamento histórico (ligado).
    """
    if getattr(daemon, "_keyboard_device", None) is not None:
        return True
    cfg = getattr(daemon, "config", None)
    if cfg is not None and not getattr(cfg, "keyboard_emulation_enabled", True):
        logger.debug("keyboard_emulation_desligada_device_nao_criado")
        return False
    try:
        from hefesto_dualsense4unix.integrations.uinput_keyboard import UinputKeyboardDevice

        device = UinputKeyboardDevice()
    except Exception as exc:
        logger.warning("keyboard_emulation_import_failed", err=str(exc))
        return False
    # OSK controller vive 1x por daemon; callback é registrado na inicialização
    # para que L3/R3 já funcionem antes do primeiro switch de perfil.
    osk = getattr(daemon, "_osk_controller", None)
    if osk is None:
        osk = _OSKController()
        daemon._osk_controller = osk
    device.virtual_token_callback = osk.dispatch_token
    if not device.start():
        logger.warning("keyboard_emulation_start_failed")
        return False
    daemon._keyboard_device = device
    # TouchpadReader best-effort: emite 3 strings virtuais (touchpad_*_press)
    # que o dispatcher mescla ao frozenset de botões. Bindings default
    # mapeiam para KEY_BACKSPACE/ENTER/DELETE.
    _start_touchpad_reader(daemon)
    logger.info("keyboard_emulation_started")
    return True


def _start_touchpad_reader(daemon: DaemonProtocol) -> None:
    """Inicia TouchpadReader se device evdev disponível; no-op caso contrário.

    Em modo FAKE (testes, CI, smoke runs) o reader é pulado pois
    `find_dualsense_touchpad_evdev()` pode demorar >60ms enumerando evdev
    em ambiente com muitos devices, o que compete com janelas de teste
    curtas do poll loop.
    """
    if getattr(daemon, "_touchpad_reader", None) is not None:
        return
    if os.environ.get("HEFESTO_DUALSENSE4UNIX_FAKE"):
        logger.debug("touchpad_reader_desativado_em_fake_mode")
        return
    try:
        from hefesto_dualsense4unix.core.evdev_reader import TouchpadReader
    except Exception as exc:
        logger.warning("touchpad_reader_import_failed", err=str(exc))
        return
    reader = TouchpadReader()
    if not reader.is_available():
        logger.debug("touchpad_reader_ausente")
        return
    if reader.start():
        daemon._touchpad_reader = reader
        logger.info("touchpad_reader_iniciado")


def stop_keyboard_emulation(daemon: DaemonProtocol) -> None:
    """Para device + reader + OSK. Idempotente."""
    device = getattr(daemon, "_keyboard_device", None)
    if device is not None:
        with contextlib.suppress(Exception):
            device.stop()
        daemon._keyboard_device = None
    reader = getattr(daemon, "_touchpad_reader", None)
    if reader is not None:
        with contextlib.suppress(Exception):
            reader.stop()
        daemon._touchpad_reader = None
    osk = getattr(daemon, "_osk_controller", None)
    if osk is not None:
        with contextlib.suppress(Exception):
            osk.close()
        daemon._osk_controller = None
    logger.info("keyboard_emulation_stopped")


def _combine_with_touchpad(
    daemon: DaemonProtocol, buttons_pressed: frozenset[str]
) -> frozenset[str]:
    """Mescla as regiões do TouchpadReader ao frozenset de botões.

    Extraído para reuso por `dispatch_keyboard` e `prime_keyboard` (mesma
    visão de botões que o device de teclado enxerga). Falha de leitura do
    reader é tratada como "nenhuma região pressionada".

    TOUCHPAD-DO-SISTEMA-01 (2026-08-09): quando o touchpad é ponteiro do
    SISTEMA, o mesmo `BTN_LEFT` já está virando botão do mouse no libinput —
    somar a região aqui faria um clique só disparar DUAS coisas (o clique dela e
    um `KEY_BACKSPACE`/`ENTER`/`DELETE` dos bindings default de
    `core/keyboard_mappings.py`). É o defeito do cursor engasgado de 26/06 na
    forma de tecla, e ele nasceria no mesmo dia em que o touchpad físico voltou
    ao libinput. Quem responde é o próprio reader (`ponteiro_do_sistema`), pelo
    estado real do nó. Reader antigo/dublê sem a propriedade conta como "o
    hefesto é o dono", que é o comportamento histórico.
    """
    reader = getattr(daemon, "_touchpad_reader", None)
    if reader is None:
        return buttons_pressed
    if getattr(reader, "ponteiro_do_sistema", False):
        return buttons_pressed
    regions: frozenset[str]
    try:
        regions = frozenset(reader.regions_pressed())
    except Exception as exc:
        logger.warning("touchpad_regions_read_failed", err=str(exc))
        regions = frozenset()
    return buttons_pressed | regions


def prime_keyboard(daemon: DaemonProtocol, buttons_pressed: frozenset[str]) -> None:
    """Semeia o edge-tracker do device de teclado com o baseline da conexão.

    Usado pelo poll loop no 1º tick conectado (BUG-DAEMON-CONNECT-GHOST-
    INPUT-01). Reaplica a mesma combinação botões+touchpad de `dispatch_keyboard`
    para que o estado semeado seja idêntico ao que o device veria, e delega ao
    `UinputKeyboardDevice.prime` (zero emissão). No-op sem device.
    """
    device = getattr(daemon, "_keyboard_device", None)
    if device is None:
        return
    combined = _combine_with_touchpad(daemon, buttons_pressed)
    try:
        device.prime(combined)
    except Exception as exc:
        logger.warning("keyboard_prime_failed", err=str(exc))


def dispatch_keyboard(daemon: DaemonProtocol, buttons_pressed: frozenset[str]) -> None:
    """Traduz o set de botões pressionados em eventos de teclado virtual.

    Chamado pelo poll loop a cada tick. Reusa `buttons_pressed` já obtido
    via `_evdev_buttons_once` (armadilha A-09). Mescla as 3 regiões do
    `TouchpadReader` (`touchpad_{left,middle,right}_press`) ao frozenset
    antes de passar ao device — regiões são tratadas como "botões virtuais"
    com os bindings default KEY_BACKSPACE/ENTER/DELETE. Não relança
    exceções — falhas são logadas como warning.
    """
    device = getattr(daemon, "_keyboard_device", None)
    if device is None:
        return
    combined = _combine_with_touchpad(daemon, buttons_pressed)
    try:
        device.dispatch(combined)
    except Exception as exc:
        logger.warning("keyboard_dispatch_failed", err=str(exc))


__all__ = [
    "_OSKController",
    "dispatch_keyboard",
    "osk_disponivel_no_sistema",
    "prime_keyboard",
    "start_keyboard_emulation",
    "stop_keyboard_emulation",
]

# "A natureza nada faz em vão." — Aristóteles
