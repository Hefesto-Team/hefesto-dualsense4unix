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
import json
import os
import shutil
import signal
import subprocess
import tempfile
import threading
import time
from pathlib import Path
from typing import TYPE_CHECKING

from hefesto_dualsense4unix.core.keyboard_mappings import (
    TOKEN_CLOSE_OSK,
    TOKEN_OPEN_OSK,
    TOKEN_TOGGLE_OSK,
)
from hefesto_dualsense4unix.integrations import fora_do_servico
from hefesto_dualsense4unix.utils.logging_config import get_logger

if TYPE_CHECKING:
    from hefesto_dualsense4unix.daemon.protocols import DaemonProtocol

logger = get_logger(__name__)

_OSK_BIN_WAYLAND = "wvkbd-mobintl"
_OSK_BIN_X11 = "onboard"
_OSK_BIN_SQUEEKBOARD = "squeekboard"
_OSK_BIN_MALIIT = "maliit-keyboard"

_OSK_CANDIDATES: tuple[str, ...] = (
    _OSK_BIN_WAYLAND,
    _OSK_BIN_X11,
    _OSK_BIN_SQUEEKBOARD,
    _OSK_BIN_MALIIT,
)
_OSK_SPAWN_ARGS: dict[str, list[str]] = {
    _OSK_BIN_X11: [_OSK_BIN_X11],
    _OSK_BIN_WAYLAND: [_OSK_BIN_WAYLAND],
    _OSK_BIN_SQUEEKBOARD: [_OSK_BIN_SQUEEKBOARD],
    _OSK_BIN_MALIIT: [_OSK_BIN_MALIIT],
}

#: loop) e no `disponivel()` que o `state_full` consulta.
_OSK_RESOLVE_TTL_SEG = 10.0

_OSK_SESSAO_ARQUIVO = "teclado-na-tela.json"

_COMM_MAX = 15

_OSK_GESTOS_NA_FILA = 4

_OSK_ESPERA_DA_PARADA_S = 2 * fora_do_servico.ESPERA_DO_SYSTEMD_RUN_S + 1.0


def _osk_candidatos() -> tuple[str, ...]:
    """Candidatos na ordem que FUNCIONA na sessão gráfica de agora."""
    if os.environ.get("WAYLAND_DISPLAY") or os.environ.get("XDG_SESSION_TYPE") == "wayland":
        return (_OSK_BIN_WAYLAND, _OSK_BIN_SQUEEKBOARD, _OSK_BIN_MALIIT, _OSK_BIN_X11)
    if os.environ.get("DISPLAY") or os.environ.get("XDG_SESSION_TYPE") == "x11":
        return (_OSK_BIN_X11, _OSK_BIN_WAYLAND, _OSK_BIN_SQUEEKBOARD, _OSK_BIN_MALIIT)
    return (_OSK_BIN_WAYLAND, _OSK_BIN_SQUEEKBOARD, _OSK_BIN_MALIIT, _OSK_BIN_X11)


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


def _sessao_do_teclado() -> Path:
    """Onde o PID do teclado na tela deste produto fica entre dois daemons."""
    from hefesto_dualsense4unix.utils.xdg_paths import runtime_dir

    return runtime_dir(ensure=True) / _OSK_SESSAO_ARQUIVO


def _gravar_sessao(pid: int, binario: str, unidade: str | None = None) -> None:
    """Anota quem abrimos: o PID e o NOME do binário que spawnamos."""
    try:
        caminho = _sessao_do_teclado()
        registro: dict[str, object] = {"pid": int(pid), "comm": binario}
        if unidade:
            registro["unidade"] = unidade
        dados = json.dumps(registro, ensure_ascii=False)
        fd, tmp = tempfile.mkstemp(dir=caminho.parent, prefix=".teclado_")
        try:
            os.write(fd, dados.encode())
        finally:
            os.close(fd)
        os.replace(tmp, caminho)
        logger.debug("osk_sessao_gravada", pid=pid, comm=binario)
    except Exception as exc:
        logger.debug("osk_sessao_gravar_falhou", err=str(exc))


def _esquecer_sessao() -> None:
    """Apaga o arquivo de sessão. Nunca levanta."""
    with contextlib.suppress(Exception):
        _sessao_do_teclado().unlink(missing_ok=True)


def _comm_do_pid(pid: int) -> str | None:
    """O `/proc/<pid>/comm` do processo, ou None se ele não existe mais."""
    try:
        return Path(f"/proc/{int(pid)}/comm").read_text(encoding="utf-8").strip()
    except (FileNotFoundError, ProcessLookupError, OSError, ValueError):
        return None


def _pid_e_zumbi(pid: int) -> bool:
    """O processo já morreu e só falta alguém colher o corpo?"""
    try:
        stat = Path(f"/proc/{int(pid)}/stat").read_text(encoding="utf-8")
    except (FileNotFoundError, ProcessLookupError, OSError, ValueError):
        return False
    _, _, resto = stat.rpartition(")")
    campos = resto.split()
    return bool(campos) and campos[0] == "Z"


def _adotar_orfao() -> int | None:
    """O PID do teclado na tela que o daemon ANTERIOR deixou aberto, se for nosso."""
    try:
        bruto = _sessao_do_teclado().read_text(encoding="utf-8")
        dados = json.loads(bruto)
        pid = int(dados["pid"])
        comm_gravado = str(dados["comm"])
    except (FileNotFoundError, json.JSONDecodeError, OSError, KeyError, TypeError, ValueError):
        return None
    except Exception as exc:  # pragma: no cover - defesa de borda
        logger.debug("osk_sessao_ler_falhou", err=str(exc))
        return None

    if comm_gravado not in _OSK_CANDIDATES:
        logger.debug("osk_orfao_recusado_binario_desconhecido", comm=comm_gravado)
        _esquecer_sessao()
        return None

    comm_vivo = _comm_do_pid(pid)
    if comm_vivo is None or _pid_e_zumbi(pid):
        logger.debug("osk_orfao_ja_morreu", pid=pid)
        _esquecer_sessao()
        return None
    if comm_vivo[:_COMM_MAX] != comm_gravado[:_COMM_MAX]:
        logger.info("osk_orfao_recusado_pid_reciclado", pid=pid, comm=comm_vivo)
        _esquecer_sessao()
        return None
    return pid


def _pid_na_unidade(unidade: str, binario: str) -> int | None:
    """O PID do teclado na tela dentro da unidade que o abriu — pergunta à unidade."""
    for pid in fora_do_servico.pids_da_unidade(unidade):
        comm = _comm_do_pid(pid)
        if comm is None or comm[:_COMM_MAX] != binario[:_COMM_MAX]:
            continue
        if _pid_e_zumbi(pid):
            continue
        return pid
    return None


class _OSKController:
    """Gerencia o processo do teclado virtual (onboard/wvkbd-mobintl)."""

    def __init__(self) -> None:
        self._resolved_bin: str | None = None
        self._resolved_checked: bool = False
        self._resolved_em: float = 0.0
        self._process: subprocess.Popen[bytes] | None = None
        self._unidade: str | None = None
        self._binario_da_unidade: str = ""
        self._missing_warned: bool = False
        self._tranca = threading.RLock()
        self._fio = fora_do_servico.FioDeTrabalho(
            "hefesto-teclado-na-tela",
            espera=_OSK_GESTOS_NA_FILA,
            ao_falhar=lambda erro: logger.warning("osk_gesto_falhou", err=str(erro)),
        )

    def _resolve(self) -> str | None:
        """Primeiro binário de teclado na tela que existe, na ordem da sessão."""
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
        """True se há programa de teclado na tela instalado (cache do `_resolve`)."""
        return self._resolve() is not None

    def _avisar_ausencia(self) -> None:
        """L3 sem teclado na tela deixa de ser silêncio (TECLADO-QUE-NAO-DIGITA-01)."""
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

    def aberto(self) -> bool:
        """True se HÁ um teclado na tela vivo que este daemon abriu."""
        with self._tranca:
            return self._pid_vivo() is not None

    def _pid_vivo(self) -> int | None:
        """O PID do teclado na tela que ESTE produto abriu e ainda vive."""
        proc = self._process
        if proc is not None:
            if proc.poll() is None:
                return proc.pid
            self._process = None
        if self._unidade is not None:
            pid = _pid_na_unidade(self._unidade, self._binario_da_unidade)
            if pid is not None:
                return pid
            self._unidade = None
        return _adotar_orfao()

    def toggle(self) -> None:
        """O SEGUNDO TOQUE FECHA — decisão, 02/09/2026."""
        with self._tranca:
            if self._pid_vivo() is not None:
                self._fechar()
            else:
                self._abrir()

    def open(self) -> None:
        """Abre o teclado na tela — no-op se JÁ há um aberto, deste daemon ou do anterior."""
        with self._tranca:
            self._abrir()

    def _abrir(self) -> None:
        if self._pid_vivo() is not None:
            return
        resolved = self._resolve()
        if resolved is None:
            self._avisar_ausencia()
            return
        from hefesto_dualsense4unix.integrations.ambiente_do_jogo import ambiente_limpo

        args = _OSK_SPAWN_ARGS[resolved]
        try:
            abertura = fora_do_servico.abrir(
                args,
                env=ambiente_limpo(os.environ),
                aplicativo=resolved,
                popen=subprocess.Popen,
            )
        except Exception as exc:
            logger.warning("osk_open_failed", binary=resolved, err=str(exc))
            self._process = None
            return
        pid: int | None
        if abertura.caminho == "unidade" and abertura.unidade:
            self._process = None
            self._unidade = abertura.unidade
            self._binario_da_unidade = resolved
            pid = _pid_na_unidade(abertura.unidade, resolved)
        else:
            self._process = abertura.processo
            pid = getattr(abertura.processo, "pid", None)
        logger.info(
            "osk_opened",
            binary=resolved,
            pid=pid,
            caminho=abertura.caminho,
            unidade=abertura.unidade,
            motivo=abertura.motivo,
        )
        if pid is not None:
            _gravar_sessao(pid, resolved, abertura.unidade)
        self._avisar_abertura()

    def _avisar_abertura(self) -> None:
        """Diz na TELA que o teclado na tela abriu, e como fechá-lo."""
        with contextlib.suppress(Exception):
            from hefesto_dualsense4unix.integrations.desktop_notifications import (
                notify_teclado_na_tela_aberto,
            )

            notify_teclado_na_tela_aberto()

    def close(self) -> None:
        """Fecha o teclado na tela — o deste daemon, ou o órfão do anterior."""
        if not self._fio.no_fio():
            self._fio.descartar()
            self.esperar_os_toques(_OSK_ESPERA_DA_PARADA_S)
        with self._tranca:
            self._fechar()

    def _fechar(self) -> None:
        proc = self._process
        if proc is not None:
            self._process = None
            if proc.poll() is None:
                try:
                    proc.terminate()
                    logger.info("osk_closed", pid=proc.pid)
                except Exception as exc:
                    logger.warning("osk_close_failed", err=str(exc))
                _esquecer_sessao()
                return
        unidade = self._unidade
        if unidade is not None:
            self._unidade = None
            pid_da_unidade = _pid_na_unidade(unidade, self._binario_da_unidade)
            if pid_da_unidade is not None:
                try:
                    os.kill(pid_da_unidade, signal.SIGTERM)
                    logger.info("osk_closed", pid=pid_da_unidade, unidade=unidade)
                except Exception as exc:
                    logger.warning("osk_close_failed", err=str(exc), unidade=unidade)
                _esquecer_sessao()
                return
        pid = _adotar_orfao()
        if pid is None:
            return
        try:
            os.kill(pid, signal.SIGTERM)
            logger.info("osk_orfao_fechado", pid=pid)
        except Exception as exc:
            logger.warning("osk_orfao_close_failed", pid=pid, err=str(exc))
        _esquecer_sessao()

    def dispatch_token(self, token: str, phase: str) -> None:
        """Callback registrado no UinputKeyboardDevice."""
        if phase != "press":
            return
        if token not in (TOKEN_TOGGLE_OSK, TOKEN_OPEN_OSK, TOKEN_CLOSE_OSK):
            logger.warning("osk_token_desconhecido", token=token)
            return
        if not self._fio.disparar(lambda: self._atender(token)):
            logger.info("osk_toque_descartado", token=token)

    def _atender(self, token: str) -> None:
        """O toque, já no fio do teclado."""
        with self._tranca:
            if token == TOKEN_TOGGLE_OSK:
                if self._pid_vivo() is not None:
                    self._fechar()
                else:
                    self._abrir()
            elif token == TOKEN_OPEN_OSK:
                self._abrir()
            else:
                self._fechar()

    def esperar_os_toques(self, teto: float | None = None) -> bool:
        """Espera os toques do L3/R3 que estão no fio. True = nenhum ficou."""
        return self._fio.esperar(teto)


def start_keyboard_emulation(daemon: DaemonProtocol) -> bool:
    """Cria device virtual de teclado + touchpad reader. Idempotente.

    Retorna True se ativo ao final; False se falhou ao iniciar o device
    principal. O `TouchpadReader` é best-effort: se o nó evdev do touchpad não
    existir, não quebra o fluxo.

    CORREÇÃO DE FATO — 25/08/2026. Esta linha dizia que o nó podia faltar "(
    controle BT, kernel velho)", e o **BT saiu**: o `hid_playstation` cria o nó
    de touchpad nos dois transportes, e ele foi medido no rádio em 21/07/2026
    (o nome muda, não a existência — o BlueZ o batiza sem o prefixo do
    fabricante, e é por isso que o casamento por nome exato falhava; ver o
    cabeçalho de `assets/76-dualsense-touchpad-libinput-ignore.rules`). Nem a
    descoberta olha transporte: `_discover_dualsense_por_nome` filtra por
    vendor/product e marcador de nome, sem uma linha sobre `bustype`. Medido de
    novo em 25/08 no DualSense do CABO desta bancada: gamepad em `event21` e
    touchpad em `event23`, a mesma identidade nos dois.

    O que faz as três regiões não dispararem tecla HOJE é outra coisa, e é
    decisão de produto: o touchpad voltou a ser ponteiro do SISTEMA
    (TOUCHPAD-DO-SISTEMA-01), e quem se cala é o `_combine_with_touchpad`
    abaixo, pelo `ponteiro_do_sistema` do reader. Medido na mesma leitura:
    `LIBINPUT_IGNORE_DEVICE` ausente no nó do touchpad físico.

    EMULACAO-NO-JOGO-01: o gate de `keyboard_emulation_enabled` mora AQUI,
    espelhando `subsystems/mouse.py` (`if not cfg.mouse_emulation_enabled:
    return`). É o que dá dentes ao interruptor: desligada, o device NÃO nasce,
    e o gate de despacho do poll loop (`_keyboard_device is not None`) fecha
    sozinho — a mesma mecânica que fazia o mouse do usuário estar honestamente
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
    osk = getattr(daemon, "_osk_controller", None)
    if osk is None:
        osk = _OSKController()
        daemon._osk_controller = osk
    device.virtual_token_callback = osk.dispatch_token
    if not device.start():
        logger.warning("keyboard_emulation_start_failed")
        return False
    daemon._keyboard_device = device
    _start_touchpad_reader(daemon)
    logger.info("keyboard_emulation_started")
    return True


def _start_touchpad_reader(daemon: DaemonProtocol) -> None:
    """Inicia TouchpadReader se device evdev disponível; no-op caso contrário."""
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
    """Mescla as regiões do TouchpadReader ao frozenset de botões."""
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
    """Semeia o edge-tracker do device de teclado com o baseline da conexão."""
    device = getattr(daemon, "_keyboard_device", None)
    if device is None:
        return
    combined = _combine_with_touchpad(daemon, buttons_pressed)
    try:
        device.prime(combined)
    except Exception as exc:
        logger.warning("keyboard_prime_failed", err=str(exc))


def dispatch_keyboard(daemon: DaemonProtocol, buttons_pressed: frozenset[str]) -> None:
    """Traduz o set de botões pressionados em eventos de teclado virtual."""
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

