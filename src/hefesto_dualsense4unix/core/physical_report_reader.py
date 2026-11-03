"""Espelho do hidraw cru de cada DualSense físico para o pad virtual, e o relógio do mudo dele.

Uma thread por jogador lê o hidraw (0x01 no cabo, 0x31 com CRC no rádio) e é o relógio do pad:
entrega a janela de movimento (`forward_motion`), o clique do touchpad, o botão do microfone, o
fone e a bateria. Passado `REPOUSO_DO_MUDO_S` sem report válido, declara a peça muda
(`soltar_por_mudo` e `a_peca_calou`); o primeiro report válido desfaz. O número: o p95 do
intervalo do rádio é 187 ms (canônica §5), o dobro dá 374 ms, o piso é 0,4 s, e o maior do
rádio são segue a medir. A história: `docs/research/o-porque-dos-modulos.md`, seção do módulo.
"""
from __future__ import annotations

import contextlib
import os
import threading
import time
from collections.abc import Callable
from typing import Any

from hefesto_dualsense4unix.core.ds_output_report import BT_INPUT_CRC_SEED, bt_crc32
from hefesto_dualsense4unix.core.roteador_de_movimento import janela_que_sai
from hefesto_dualsense4unix.core.virtual_motion import DESTINO_JOGO, REGISTRO
from hefesto_dualsense4unix.integrations import usb_pai
from hefesto_dualsense4unix.utils.espera import prontos_ou_acordado
from hefesto_dualsense4unix.utils.logging_config import get_logger

logger = get_logger(__name__)
INPUT_REPORT_USB = 0x01
INPUT_REPORT_BT = 0x31
INPUT_REPORT_BT_SIZE = 78
_USB_STRUCT_BASE = 1
_BT_STRUCT_BASE = 2

INPUT_FLAG_AUDIO = 0x02

MOTION_WINDOW_OFFSET = 15
CONTADOR_DE_REPORT_OFFSET = 11
MOTION_WINDOW_LEN = 25

BUTTONS2_OFFSET = 9
TOUCHPAD_CLICK_BIT = 0x02

MIC_BUTTON_BIT = 0x04

JACK_STATUS_OFFSET = 53

BATTERY_STATUS_OFFSET = 52

TRIGGER_R2_STATUS_OFFSET = 41
TRIGGER_L2_STATUS_OFFSET = 42
TRIGGER_STATE_SHIFT = 4
TRIGGER_ESTADO_DISPAROU = 2

_CARGA_DESCARREGANDO = 0x0
_CARGA_CARREGANDO = 0x1
_CARGA_CHEIO = 0x2

HZ_DO_CABO = 250.0
_CARIMBO_NA_JANELA = slice(12, 16)

_READ_LEN = 128

_SELECT_TIMEOUT_S = 0.25

_SILENCE_REOPEN_USB_S = 1.0
_SILENCE_REOPEN_BT_S = 30.0

REPOUSO_DO_MUDO_S = 0.4
_ESPERA_MINIMA_S = 0.005

_BUS_USB = 0x03
_BUS_BLUETOOTH = 0x05

_BACKOFF_START_S = 0.5
_BACKOFF_MAX_S = 5.0

_HZ_EMA_ALPHA = 0.25
_HZ_STALE_S = 1.0


_RAIZ_HIDRAW = usb_pai.RAIZ_HIDRAW


def uniq_do_hidraw(path: str) -> str | None:
    """O endereço de rádio da peça dona deste `/dev/hidrawN`; `None` sem ele.

    SENSOR-DE-VERDADE-01. O `PhysicalReportReader` recebe um CAMINHO, e o
    interruptor de sensor é por PEÇA — sem esta tradução o filtro não teria
    como saber de quem é a janela que está copiando, e a alternativa (levar o
    `uniq` por parâmetro) atravessaria `gamepad.py` e `coop.py`, dois arquivos
    de outra posse, para carregar um dado que o sysfs já tem.

    Lê o `HID_UNIQ` do uevent do device pai, que é a mesma chave que a janela
    usa por controle (`integrations/usb_pai`). `None` em qualquer erro: o
    sysfs some debaixo da mão em hotplug, e "não sei de quem é" tem de
    resultar em NÃO FILTRAR — desligar o sensor do controle errado é pior do
    que não desligar.
    """
    nome = os.path.basename(str(path or "").rstrip("/"))
    if not nome.startswith("hidraw"):
        return None
    try:
        with open(
            os.path.join(_RAIZ_HIDRAW, nome, "device", "uevent"),
            encoding="utf-8",
            errors="replace",
        ) as arquivo:
            texto = arquivo.read()
    except OSError:
        return None
    for linha in texto.splitlines():
        if linha.startswith("HID_UNIQ="):
            valor = linha[len("HID_UNIQ=") :].strip().lower()
            return valor or None
    return None


def a_peca_calou(leitor: Any) -> bool:
    """A peça deste leitor está muda: o pad fica em repouso e o laço não o reescreve."""
    return bool(getattr(leitor, "mudo", False))


def soltar_o_pad_da_peca_muda(pad: Any) -> None:
    """Põe em repouso o pad que não tem repouso próprio (o uinput do Xbox). Nunca levanta.

    O pad do uhid e do gadget recebe o repouso do próprio leitor (`soltar_por_mudo`), na
    thread dele e sob a trava do pad; aqui sobra o que só sabe `forward_analog` e
    `forward_buttons`, chamado pelo laço que o alimenta.
    """
    if pad is None or callable(getattr(pad, "soltar_por_mudo", None)):
        return
    try:
        pad.forward_analog(lx=128, ly=128, rx=128, ry=128, l2=0, r2=0)
        pad.forward_buttons(frozenset())
    except Exception as exc:
        logger.warning("pad_da_peca_muda_soltar_falhou", err=str(exc))


def _open_por_caminho(path: str) -> int:
    """Opener default (sem broker): o `os.open` por caminho de sempre."""
    return os.open(path, os.O_RDONLY)


def _novo_wake_pipe() -> tuple[int, int]:
    """Par de self-pipe (não-bloqueante) para acordar o select do reader."""
    lado_r, lado_w = os.pipe()
    os.set_blocking(lado_r, False)
    os.set_blocking(lado_w, False)
    return lado_r, lado_w


def silence_budget_for(path: str | None) -> float:
    """Teto de silêncio (s) do nó `path`, decidido pelo BUS do sysfs."""
    if not path:
        return _SILENCE_REOPEN_BT_S
    nome = os.path.basename(path)
    if not nome.startswith("hidraw"):
        return _SILENCE_REOPEN_BT_S
    try:
        with open(os.path.join(_RAIZ_HIDRAW, nome, "device", "uevent"), encoding="utf-8") as fh:
            for linha in fh:
                if not linha.startswith("HID_ID="):
                    continue
                bus = int(linha.split("=", 1)[1].split(":", 1)[0], 16)
                if bus == _BUS_USB:
                    return _SILENCE_REOPEN_USB_S
                return _SILENCE_REOPEN_BT_S
    except (OSError, ValueError) as exc:
        logger.debug("motion_reader_bus_indeterminado", path=path, err=str(exc))
    return _SILENCE_REOPEN_BT_S


def _struct_base(report: bytes) -> int | None:
    """Deslocamento do `struct dualsense_input_report` no report cru, ou None.

    Extraído para que motion e clique do touchpad apliquem EXATAMENTE a mesma
    disciplina de transporte — em especial o CRC do BT: se o clique tivesse um
    parser próprio sem CRC, rádio corrompido viraria mapa abrindo sozinho no
    meio da partida. Um portão, dois consumidores.

    - ``0x01`` (USB): payload em ``report[1:]``.
    - ``0x31`` (BT): exige os 78 B exatos, o bit de ÁUDIO **desligado** e
      CRC-32 válido (seed 0xA1 sobre os 74 primeiros bytes, LE nos 4 finais —
      `ps_check_crc32` do kernel).
    - Qualquer outro id/tamanho (0x05 de BT parcial, reports de feature) → None.

    **O bit de áudio, e o estrago que ele causou** (PS-PRESO-01, 16/08/2026).
    Com o microfone ligado, o DualSense manda áudio Opus **no mesmo report
    `0x31`, com o mesmo tamanho de 78 bytes** — a ÚNICA diferença é o bit
    ``0x02`` do byte 1. Sem conferir esse bit, este portão devolve base para um
    report de áudio, e os bytes de Opus caem exatamente sobre os eixos e os
    botões do `struct dualsense_input_report`.

    Medido ao vivo na máquina do usuário: 3 minutos depois de a ponte do mic subir, os
    botões **MIC e PS** (que moram no mesmo `buttons[2]`) ficaram presos, e cada
    leitura disparava `ps_button_action_steam` — o daemon tentando abrir a Steam
    dezenas de vezes por segundo. Na tela, o teclado e o mouse ganharam
    vida própria, e o controle foi desligado. Três segundos depois o controle caiu
    inteiro.

    O CRC **não** protegia disso: o report de áudio é legítimo e tem CRC válido.
    Ele só não é estado de input.

    `integrations/dualsense_bt_audio.py` conhecia esse bit desde sempre
    (`INPUT_FLAG_AUDIO`, `eh_report_de_audio`) — e era o único módulo do projeto
    que conhecia. A constante é redeclarada aqui de propósito: este arquivo é o
    caminho quente da leitura e não pode importar o módulo de áudio (que carrega
    ctypes/libopus). Os dois valores estão travados um no outro por teste.
    """
    if not report:
        return None
    if report[0] == INPUT_REPORT_USB:
        if len(report) <= _USB_STRUCT_BASE + JACK_STATUS_OFFSET:
            return None
        return _USB_STRUCT_BASE
    if report[0] == INPUT_REPORT_BT:
        if len(report) != INPUT_REPORT_BT_SIZE:
            return None
        if report[1] & INPUT_FLAG_AUDIO:
            return None
        crc = int.from_bytes(report[-4:], "little")
        if bt_crc32(report[:-4], seed=BT_INPUT_CRC_SEED) != crc:
            return None
        return _BT_STRUCT_BASE
    return None


def _janela_com_base(report: bytes, base: int) -> bytes | None:
    """Janela de motion (25 B) a partir da base já resolvida."""
    start = base + MOTION_WINDOW_OFFSET
    end = start + MOTION_WINDOW_LEN
    if len(report) < end:
        return None
    return bytes(report[start:end])


def _clique_com_base(report: bytes, base: int) -> bool | None:
    """Clique do touchpad a partir da base já resolvida."""
    idx = base + BUTTONS2_OFFSET
    if len(report) <= idx:
        return None
    return bool(report[idx] & TOUCHPAD_CLICK_BIT)


def _botao_do_mic_com_base(report: bytes, base: int) -> bool | None:
    """Botão do microfone a partir da base já resolvida (mesmo byte do clique)."""
    idx = base + BUTTONS2_OFFSET
    if len(report) <= idx:
        return None
    return bool(report[idx] & MIC_BUTTON_BIT)


def _jack_com_base(report: bytes, base: int) -> int | None:
    """Byte de fone/microfone a partir da base já resolvida."""
    idx = base + JACK_STATUS_OFFSET
    if len(report) <= idx:
        return None
    return int(report[idx])


def _bateria_com_base(report: bytes, base: int) -> int | None:
    """Byte de bateria a partir da base já resolvida."""
    idx = base + BATTERY_STATUS_OFFSET
    if len(report) <= idx:
        return None
    return int(report[idx])


def _estado_do_gatilho_com_base(report: bytes, base: int) -> tuple[int, int] | None:
    """`(L2, R2)`: o nibble alto do status de cada gatilho, base já resolvida."""
    r2 = base + TRIGGER_R2_STATUS_OFFSET
    l2 = base + TRIGGER_L2_STATUS_OFFSET
    if len(report) <= max(r2, l2):
        return None
    return (
        int(report[l2]) >> TRIGGER_STATE_SHIFT,
        int(report[r2]) >> TRIGGER_STATE_SHIFT,
    )


def extract_estado_do_gatilho(report: bytes) -> tuple[int, int] | None:
    """`(L2, R2)` do estado do gatilho de um report CRU do físico, ou None.

    Passa pelo mesmo `_struct_base` dos outros bytes: o `0x31` com CRC inválido
    ou com o bit de áudio ligado não é estado de input e dá None.
    """
    base = _struct_base(report)
    if base is None:
        return None
    return _estado_do_gatilho_com_base(report, base)


def extract_touchpad_click(report: bytes) -> bool | None:
    """Clique do touchpad de um report CRU do físico, ou None (TOUCH-CLICK-01)."""
    base = _struct_base(report)
    if base is None:
        return None
    return _clique_com_base(report, base)


def extract_jack_status(report: bytes) -> int | None:
    """Byte de fone/microfone (`status[1]`) de um report CRU, ou None."""
    base = _struct_base(report)
    if base is None:
        return None
    idx = base + JACK_STATUS_OFFSET
    if len(report) <= idx:
        return None
    return int(report[idx])


def extract_estado_do_mic(report: bytes) -> tuple[int, bool] | None:
    """`(status[1], botão do microfone apertado)` de um report CRU, ou None."""
    base = _struct_base(report)
    if base is None:
        return None
    jack = _jack_com_base(report, base)
    idx = base + BUTTONS2_OFFSET
    if jack is None or len(report) <= idx:
        return None
    return jack, bool(report[idx] & MIC_BUTTON_BIT)


def extract_battery_status(report: bytes) -> int | None:
    """Byte de bateria (`status[0]`) de um report CRU, ou None."""
    base = _struct_base(report)
    if base is None:
        return None
    idx = base + BATTERY_STATUS_OFFSET
    if len(report) <= idx:
        return None
    return int(report[idx])


def decodificar_bateria(status0: int) -> tuple[int | None, bool]:
    """``(percentual, carregando)`` do byte de bateria; ``None`` = não sei.

    BATERIA-QUE-NAO-CHEGOU-01. A conta é a do `dualsense_parse_report` do
    kernel 6.18, e vale nos DOIS sentidos: é a mesma tabela que o
    `hid-playstation` vai aplicar ao byte que o nosso vpad escrever. Este é o
    ponto em que "não converta no chute" foi cobrado — a escala não é uma
    porcentagem, são **11 níveis** (5, 15, ..., 95, 100) num nibble.

    O caminho de volta (`_percent_para_nibble`, no vpad) é o inverso EXATO
    desta conta para os 11 níveis, e há teste que percorre os onze. Nenhum
    arredondamento é introduzido aqui: nível `n` vira `n*10+5`, que volta a
    ser `n`.

    Os estados de carga que o nibble alto pode dizer são cinco, e o report do
    vpad só sabe escrever dois (carregando / descarregando — o
    `_CHARGING_SHIFT` do `forward_battery`). A escolha de cada um:

    * **cheio (0x2)** vira ``(100, carregando=True)``. É o mais próximo que o
      campo consegue dizer, e é honesto no que importa: o controle está na
      base, cheio, e nenhum alerta de bateria fraca deve aparecer. Dizer
      "100% descarregando" seria inventar um consumo que não existe;
    * **fora de faixa / erro de carga (0xa, 0xb, 0xf)** e qualquer nibble que
      não conhecemos viram ``(None, False)`` — e ``None`` é o que faz o
      `forward_battery` escrever `_STATUS_DESCONHECIDO`. O kernel devolve
      capacidade **0** nesses casos, e repassar zero seria acender alerta de
      bateria crítica por causa de um controle quente. "Não sei" é a resposta
      que a casa já escolheu para esse byte, e não dispara alerta nenhum.
    """
    nivel = status0 & 0x0F
    carga = (status0 & 0xF0) >> 4
    if carga in (_CARGA_DESCARREGANDO, _CARGA_CARREGANDO):
        return (min(nivel * 10 + 5, 100), carga == _CARGA_CARREGANDO)
    if carga == _CARGA_CHEIO:
        return (100, True)
    return (None, False)


class PhysicalReportReader:
    """Thread que espelha a janela de motion do hidraw físico no vpad."""

    def __init__(
        self,
        path_provider: Callable[[], str | None],
        vpad: Any,
        *,
        time_fn: Callable[[], float] = time.monotonic,
        opener: Callable[[str], int] | None = None,
    ) -> None:
        self._path_provider = path_provider
        self._vpad = vpad
        self._time_fn = time_fn
        self._opener: Callable[[str], int] = (
            opener if opener is not None else _open_por_caminho
        )
        self._stop_flag = threading.Event()
        self._thread: threading.Thread | None = None
        self._fd: int | None = None
        self._fd_lock = threading.Lock()
        self._uniq_aberto: str | None = None
        self._reopen_flag = threading.Event()
        self._wake_lock = threading.Lock()
        self._wake_r, self._wake_w = -1, -1
        self._last_window: bytes | None = None
        self._last_carimbo: bytes | None = None
        self._last_emit_at = float("-inf")
        self._lidos = 0
        self._duplicados = 0
        self._sessao_de_jogo: dict[str, int] | None = None
        self._touchpad_click: bool | None = None
        self._touchpad_clicks = 0
        self._mic_button: bool | None = None
        self._mic_button_forwards = 0
        self._jack_status: int | None = None
        self._jack_forwards = 0
        self._battery_status: int | None = None
        self._battery_forwards = 0
        self._gatilho: tuple[int, int] | None = None
        self._gatilho_desde = float("-inf")
        self._disparos: dict[str, int] = {"L2": 0, "R2": 0}
        self._disparou_em: dict[str, float] = {}
        self._gatilho_ouvinte: Callable[[str, int, int, float], None] | None = None
        self._reports_seen = 0
        self._windows_emitted = 0
        self._bt_drops = 0
        self._reports_estragados = 0
        self._contador_anterior: int | None = None
        self._ilegiveis_no_meio = 0
        self._reports_perdidos = 0
        self._emit_hz_ema = 0.0
        self._valido_em: float | None = None
        self._mudo = False
        self._mudos = 0
        self._mudo_desde = 0.0


    @property
    def mudo(self) -> bool:
        """A peça calou por mais de `REPOUSO_DO_MUDO_S` e ainda não voltou."""
        return self._mudo

    @property
    def mudos(self) -> int:
        """Quantas vezes a peça calou desde que o leitor nasceu."""
        return self._mudos

    @property
    def is_running(self) -> bool:
        thread = self._thread
        return thread is not None and thread.is_alive()

    @property
    def reports_seen(self) -> int:
        return self._reports_seen

    @property
    def windows_emitted(self) -> int:
        return self._windows_emitted

    @property
    def bt_drops(self) -> int:
        return self._bt_drops

    @property
    def reports_estragados(self) -> int:
        """Reports do rádio que chegaram e não passaram no portão (o CRC).

        O `bt_drops` conta também o report de áudio, que é legítimo e não é
        estado de entrada; este número fica só com o que chegou estragado.
        """
        return self._reports_estragados

    @property
    def reports_perdidos(self) -> int:
        """Reports que o aparelho mandou e não chegaram, pelo contador dele."""
        return self._reports_perdidos

    @property
    def touchpad_clicks(self) -> int:
        """Nº de PRESSIONADAS do touchpad entregues ao vpad (TOUCH-CLICK-01)."""
        return self._touchpad_clicks

    @property
    def mic_button_forwards(self) -> int:
        """Nº de APERTOS do botão do microfone entregues ao vpad."""
        return self._mic_button_forwards

    @property
    def jack_forwards(self) -> int:
        """Nº de mudanças de fone/mic entregues ao vpad (JACK-QUE-NAO-LIGOU-01)."""
        return self._jack_forwards

    @property
    def battery_forwards(self) -> int:
        """Nº de mudanças de bateria entregues ao vpad (BATERIA-QUE-NAO-CHEGOU-01)."""
        return self._battery_forwards

    @property
    def amostras(self) -> dict[str, int]:
        """As pontas do movimento: `lidos`, `pulados_no_ar`, `duplicados` e `entregues`.

        `lidos` conta as amostras que o hidraw trouxe a um pad que leva movimento;
        `pulados_no_ar` são as que o contador do aparelho diz que não chegaram. Sem perda
        no Hefesto, `entregues == lidos - duplicados`.
        """
        return {
            "lidos": self._lidos,
            "pulados_no_ar": self._reports_perdidos,
            "duplicados": self._duplicados,
            "entregues": self._windows_emitted,
        }

    @property
    def emit_hz(self) -> float:
        """Taxa de emissão ao vpad (Hz, EMA) — 0.0 quando o fluxo parou.

        GYRO-03: é ESTA taxa (o que o vpad de fato recebe) que
        o `state_full` publica como `motion_hz`. "Parou" = nenhuma entrega há
        mais de `_HZ_STALE_S` — a EMA antiga de um fluxo morto não vale nada.
        """
        if self._emit_hz_ema <= 0.0:
            return 0.0
        if (self._time_fn() - self._last_emit_at) > _HZ_STALE_S:
            return 0.0
        return round(self._emit_hz_ema, 1)


    @property
    def estado_do_gatilho(self) -> tuple[int, int] | None:
        """`(L2, R2)` do último report, ou None sem controle aberto."""
        return self._gatilho

    @property
    def gatilho_desde(self) -> float:
        """O instante (relógio do leitor) em que o estado de agora mudou."""
        return self._gatilho_desde

    @property
    def disparos_do_gatilho(self) -> dict[str, int]:
        """Quantas vezes cada gatilho chegou a «disparou» (L2 e R2)."""
        return dict(self._disparos)

    @property
    def disparou_em(self) -> dict[str, float]:
        """O instante do último «disparou» de cada gatilho que já disparou."""
        return dict(self._disparou_em)

    def ouvir_gatilho(
        self, ouvinte: Callable[[str, int, int, float], None] | None
    ) -> None:
        """Registra quem recebe cada mudança: `ouvinte(lado, antes, agora, instante)`.

        Só leitura: nada daqui escreve no controle por causa do estado. O
        ouvinte roda na thread do leitor e não pode demorar.
        """
        self._gatilho_ouvinte = ouvinte

    def start(self) -> bool:
        """Sobe a thread (idempotente). O device é aberto DENTRO do loop."""
        if self.is_running:
            return True
        self._stop_flag.clear()
        self._reopen_flag.clear()
        if self._wake_r < 0 or self._wake_w < 0:
            self._wake_r, self._wake_w = _novo_wake_pipe()
        player = getattr(self._vpad, "player", "?")
        self._thread = threading.Thread(
            target=self._run, name=f"hefesto-motion-p{player}", daemon=True
        )
        self._thread.start()
        return True

    def stop(self) -> None:
        """Para a thread e garante o streaming DESLIGADO no vpad.

        Chamar ANTES do `stop()` do vpad (ordem do teardown): o reader escreve
        no /dev/uhid via `forward_motion` e não pode sobreviver ao fd do device.

        GYRO-FD-01: NÃO fecha o fd do hidraw — só sinaliza (flag + wake) e a
        própria thread fecha o próprio fd no finally. O wake acorda o select na
        hora (sem esperar o timeout da iteração).
        """
        self._stop_flag.set()
        self._wake()
        thread = self._thread
        if thread is not None:
            thread.join(timeout=2.0)
            self._thread = None
            if not thread.is_alive():
                self._close_wake_pipe()
        else:
            self._close_wake_pipe()
        self._reset_touchpad_click()
        self._reset_mic_button()
        self._reset_jack()
        self._reset_battery()
        self._reset_gatilho()
        self._voltar_do_mudo(self._time_fn(), motivo="leitor_parou")
        self._fechar_a_sessao_de_jogo(motivo="leitor_parou")
        with contextlib.suppress(Exception):
            self._vpad.set_motion_streaming(False)

    def request_reopen(self, reason: str = "retarget") -> None:
        """Pede à thread que largue o fd atual e reabra pelo `path_provider`."""
        logger.info("motion_reader_reopen_requested", reason=reason)
        self._reopen_flag.set()
        self._wake()

    def _wake(self) -> None:
        """1 byte no self-pipe: acorda o select da thread imediatamente."""
        with self._wake_lock:
            if self._wake_w >= 0:
                with contextlib.suppress(OSError):
                    os.write(self._wake_w, b"w")

    def _drain_wake(self) -> None:
        """Esvazia o self-pipe (não-bloqueante; bytes velhos não acumulam)."""
        with contextlib.suppress(OSError):
            while os.read(self._wake_r, 64):
                pass

    def _close_wake_pipe(self) -> None:
        with self._wake_lock:
            for attr in ("_wake_r", "_wake_w"):
                fd = getattr(self, attr)
                if fd >= 0:
                    with contextlib.suppress(OSError):
                        os.close(fd)
                    setattr(self, attr, -1)

    def _close_fd(self, _reason: str) -> None:
        """Fecha o fd do hidraw — chamado SOMENTE pela thread do reader."""
        with self._fd_lock:
            fd, self._fd = self._fd, None
        if fd is not None:
            with contextlib.suppress(OSError):
                os.close(fd)


    def _run(self) -> None:
        backoff = _BACKOFF_START_S
        while not self._stop_flag.is_set():
            self._reopen_flag.clear()
            path = self._resolve_path()
            if path is None:
                if self._stop_flag.wait(backoff):
                    break
                backoff = min(backoff * 2, _BACKOFF_MAX_S)
                continue
            try:
                fd = self._opener(path)
            except OSError as exc:
                logger.warning("motion_reader_open_failed", path=path, err=str(exc))
                if self._stop_flag.wait(backoff):
                    break
                backoff = min(backoff * 2, _BACKOFF_MAX_S)
                continue
            with self._fd_lock:
                self._fd = fd
            backoff = _BACKOFF_START_S
            self._uniq_aberto = uniq_do_hidraw(path)
            logger.info("motion_reader_started", path=path)
            with contextlib.suppress(Exception):
                self._vpad.set_motion_streaming(True)
            try:
                self._read_until_lost(fd, silence_budget_for(path))
            finally:
                self._close_fd("read_lost")
                self._reset_touchpad_click()
                self._reset_mic_button()
                self._reset_jack()
                self._reset_battery()
                self._reset_gatilho()
                with contextlib.suppress(Exception):
                    self._vpad.set_motion_streaming(False)
            if not self._stop_flag.is_set():
                time.sleep(0.1)

    def _resolve_path(self) -> str | None:
        try:
            path = self._path_provider()
        except Exception as exc:
            logger.debug("motion_reader_provider_failed", err=str(exc))
            return None
        return path if isinstance(path, str) and path else None

    def _read_until_lost(
        self, fd: int, silencio_max: float = _SILENCE_REOPEN_BT_S
    ) -> None:
        """Lê reports até o fd morrer (ENODEV), silêncio longo ou sinal de fora.

        O silêncio maior que `REPOUSO_DO_MUDO_S` declara a peça muda (`_conferir_o_mudo`),
        e o primeiro report válido depois dele declara a volta. O mudo atravessa a
        reabertura: só um report válido, ou o leitor parado, o desfaz.
        """
        silencio = 0.0
        self._contador_anterior = None
        self._ilegiveis_no_meio = 0
        self._valido_em = self._time_fn()
        while not self._stop_flag.is_set():
            if self._reopen_flag.is_set():
                self._reopen_flag.clear()
                return
            espera = self._espera_ate_o_mudo()
            try:
                pronto = prontos_ou_acordado(fd, self._wake_r, espera)
            except (OSError, ValueError):
                return
            if self._wake_r in pronto:
                self._drain_wake()
                if self._stop_flag.is_set():
                    return
                if self._reopen_flag.is_set():
                    self._reopen_flag.clear()
                    return
                continue
            if not pronto:
                silencio += espera
                self._conferir_o_mudo(self._time_fn())
                if silencio >= silencio_max:
                    logger.info(
                        "motion_reader_silencio_reabrindo", limite_s=silencio_max
                    )
                    return
                continue
            silencio = 0.0
            try:
                data = os.read(fd, _READ_LEN)
            except OSError:
                return
            if not data:
                return
            self._processar(data, self._time_fn())

    def _processar(self, data: bytes, agora: float) -> None:
        """Um report cru lido do hidraw: o relógio do mudo, os bytes de estado e a janela."""
        self._reports_seen += 1
        base = _struct_base(data)
        if base is None:
            if data[0] == INPUT_REPORT_BT:
                self._bt_drops += 1
                self._ilegiveis_no_meio += 1
                de_audio = len(data) == INPUT_REPORT_BT_SIZE and bool(
                    data[1] & INPUT_FLAG_AUDIO
                )
                if not de_audio:
                    self._reports_estragados += 1
            self._conferir_o_mudo(agora)
            return
        self._voltar_do_mudo(agora)
        self._valido_em = agora
        self._observe_contador(data, base)
        self._observe_touchpad_click(data, base)
        self._observe_mic_button(data, base)
        self._observe_jack(data, base)
        self._observe_battery(data, base)
        self._observe_gatilho(data, base)
        if not callable(getattr(self._vpad, "forward_motion", None)):
            return
        window = _janela_com_base(data, base)
        if window is None:
            return
        self._acompanhar_a_sessao_de_jogo()
        self._lidos += 1
        self._maybe_emit(window)

    def _espera_ate_o_mudo(self) -> float:
        """O prazo do `poll`: o de sempre, encurtado para acordar no instante do mudo."""
        if self._mudo or self._valido_em is None:
            return _SELECT_TIMEOUT_S
        falta = self._valido_em + REPOUSO_DO_MUDO_S - self._time_fn()
        return min(_SELECT_TIMEOUT_S, max(_ESPERA_MINIMA_S, falta))

    def _conferir_o_mudo(self, agora: float) -> None:
        """Declara a peça muda quando o último report válido passou de `REPOUSO_DO_MUDO_S`.

        Uma vez por mudo: o pad recebe `soltar_por_mudo` (o repouso), e os caches de
        borda do clique e do botão do microfone se esquecem, para a volta reentregar o
        que o primeiro report disser.
        """
        if self._mudo or self._valido_em is None:
            return
        silencio = agora - self._valido_em
        if silencio < REPOUSO_DO_MUDO_S:
            return
        self._mudo = True
        self._mudos += 1
        self._mudo_desde = self._valido_em
        self._last_window = None
        self._last_carimbo = None
        self._touchpad_click = None
        self._mic_button = None
        logger.info(
            "motion_reader_peca_muda",
            player=getattr(self._vpad, "player", "?"),
            silencio_s=round(silencio, 3),
        )
        soltar = getattr(self._vpad, "soltar_por_mudo", None)
        if not callable(soltar):
            return
        try:
            soltar()
        except Exception as exc:
            logger.warning("motion_reader_repouso_falhou", err=str(exc))

    def _voltar_do_mudo(self, agora: float, motivo: str = "report_valido") -> None:
        """Desfaz o mudo: primeiro o leitor, depois o pad, para o laço nunca o refazer."""
        if not self._mudo:
            return
        self._mudo = False
        logger.info(
            "motion_reader_peca_voltou",
            player=getattr(self._vpad, "player", "?"),
            segundos=round(agora - self._mudo_desde, 3),
            motivo=motivo,
        )
        voltar = getattr(self._vpad, "voltar_do_mudo", None)
        if not callable(voltar):
            return
        try:
            voltar()
        except Exception as exc:
            logger.warning("motion_reader_volta_falhou", err=str(exc))


    def _observe_contador(self, report: bytes, base: int) -> None:
        """Soma os reports que o contador do aparelho pulou desde o anterior.

        O primeiro report de cada fd só semeia. A volta do `uint32` é um passo
        como outro qualquer; um contador que ANDA PARA TRÁS é o aparelho
        recomeçando, e semeia de novo em vez de contar quatro bilhões. O report
        do rádio que chegou e não se lê (CRC ruim) ocupou um número do contador
        sem ser perda, e sai da conta do buraco. O de áudio sai também, e é o
        lado seguro de uma pergunta ainda não medida no aparelho (se ele ocupa
        número): no pior caso esconde a perda que coincidir com ele, e nunca
        inventa perda com o microfone ligado.
        """
        inicio = base + CONTADOR_DE_REPORT_OFFSET
        if len(report) < inicio + 4:
            return
        valor = int.from_bytes(report[inicio : inicio + 4], "little")
        anterior, self._contador_anterior = self._contador_anterior, valor
        ilegiveis, self._ilegiveis_no_meio = self._ilegiveis_no_meio, 0
        if anterior is None:
            return
        passo = (valor - anterior) & 0xFFFFFFFF
        if passo >= 0x80000000:
            return
        self._reports_perdidos += max(0, passo - 1 - ilegiveis)

    def _observe_touchpad_click(self, report: bytes, base: int | None = None) -> None:
        """Entrega ao vpad a BORDA do clique do touchpad deste report cru.

        Só borda: repetir "ainda apertado" a 250-800 Hz seria um write no /dev/uhid por report.
        `None` do extrator (outro id, curto, CRC ruim) não mexe no estado, e vpad sem o método
        degrada calado, o contrato duck-typed do `forward_motion`. `base` é a de `_struct_base`
        quando quem chama já a tem (DAEMON-ACORDADO-01). O clique segue o destino do dedo
        (`REGISTRO.destino_do_toque`): fora do jogo não chega ao vpad, e o apertado se solta.
        """
        pressed = (
            _clique_com_base(report, base)
            if base is not None
            else extract_touchpad_click(report)
        )
        if REGISTRO.destino_do_toque(self._uniq_aberto) != DESTINO_JOGO:
            pressed = False if self._touchpad_click else None
        if pressed is None or pressed == self._touchpad_click:
            return
        forward = getattr(self._vpad, "forward_touchpad_click", None)
        if forward is None:
            return
        self._touchpad_click = pressed
        try:
            forward(pressed)
            if pressed:
                self._touchpad_clicks += 1
        except Exception as exc:
            logger.warning("motion_reader_touchpad_click_failed", err=str(exc))

    def _reset_touchpad_click(self) -> None:
        """Esquece o clique ao perder o fd — o vpad já o soltou no fail-safe."""
        self._touchpad_click = None


    def _observe_mic_button(self, report: bytes, base: int | None = None) -> None:
        """Entrega ao vpad a BORDA do botão do microfone deste report cru."""
        if base is None:
            base = _struct_base(report)
            if base is None:
                return
        pressed = _botao_do_mic_com_base(report, base)
        if pressed is None or pressed == self._mic_button:
            return
        forward = getattr(self._vpad, "forward_mic_button", None)
        if forward is None:
            return
        self._mic_button = pressed
        try:
            forward(pressed)
            if pressed:
                self._mic_button_forwards += 1
        except Exception as exc:
            logger.warning("motion_reader_mic_button_failed", err=str(exc))

    def _reset_mic_button(self) -> None:
        """Esquece o botão ao perder o fd: o vpad já o soltou no fail-safe."""
        self._mic_button = None


    def _observe_jack(self, report: bytes, base: int | None = None) -> None:
        """Entrega ao vpad a MUDANÇA de fone/microfone deste report cru.

        Irmão exato do `_observe_touchpad_click`, e as três defesas dele valem
        aqui pelas mesmas razões: só borda (o report vem a 250 Hz no cabo e em
        rajada no rádio, pico de ~797 Hz, e reafirmar o mesmo byte seria um
        write no /dev/uhid por report),
        ``None`` do extrator não mexe no estado (CRC ruim não despluga fone), e
        vpad sem o método degrada calado (uinput e dublês de teste — mesmo
        contrato duck-typed do `forward_motion`).

        A comparação é com o byte CRU, e o vpad filtra os três bits conhecidos.
        É de propósito: se o firmware mexer num bit que não encaminhamos, o
        cache muda, o `forward_jack` reconhece que o valor filtrado é o mesmo e
        sai cedo — nenhum report a mais no /dev/uhid, e nenhuma entrega perdida
        se o bit conhecido mudar junto.

        `base` tem o mesmo contrato do `_observe_touchpad_click`: quem já a
        resolveu passa, quem só tem o report omite.
        """
        status = (
            _jack_com_base(report, base)
            if base is not None
            else extract_jack_status(report)
        )
        if status is None or status == self._jack_status:
            return
        forward = getattr(self._vpad, "forward_jack", None)
        if forward is None:
            return
        self._jack_status = status
        try:
            forward(status)
            self._jack_forwards += 1
        except Exception as exc:
            logger.warning("motion_reader_jack_failed", err=str(exc))

    def _reset_jack(self) -> None:
        """Esquece o fone ao perder o fd — o vpad já o zerou no fail-safe."""
        self._jack_status = None


    def _observe_battery(self, report: bytes, base: int | None = None) -> None:
        """Entrega ao vpad a MUDANÇA de bateria deste report cru."""
        status = (
            _bateria_com_base(report, base)
            if base is not None
            else extract_battery_status(report)
        )
        if status is None or status == self._battery_status:
            return
        forward = getattr(self._vpad, "forward_battery", None)
        if forward is None:
            return
        self._battery_status = status
        percentual, carregando = decodificar_bateria(status)
        try:
            forward(percentual, charging=carregando, from_reader=True)
            self._battery_forwards += 1
        except Exception as exc:
            logger.warning("motion_reader_battery_failed", err=str(exc))

    def _reset_battery(self) -> None:
        """Esquece a bateria ao perder o fd — o vpad já voltou a "não sei"."""
        self._battery_status = None


    def _observe_gatilho(self, report: bytes, base: int | None = None) -> None:
        """Registra a MUDANÇA do estado dos dois gatilhos deste report cru.

        Só borda, como o clique: o report vem a 250 Hz no cabo. O contador de
        «disparou» sobe quando o gatilho CHEGA ao estado 2 vindo de outro;
        o estado 2 só quer dizer «a arma disparou» se o modo no gatilho é o da
        arma oficial, e quem consome sabe o modo (o arco e o galope nem mexem
        no nibble).
        """
        atual = (
            _estado_do_gatilho_com_base(report, base)
            if base is not None
            else extract_estado_do_gatilho(report)
        )
        if atual is None or atual == self._gatilho:
            return
        antes = self._gatilho
        agora = self._time_fn()
        self._gatilho = atual
        self._gatilho_desde = agora
        if antes is None:
            return
        for lado, ant, novo in (("L2", antes[0], atual[0]), ("R2", antes[1], atual[1])):
            if ant == novo:
                continue
            if novo == TRIGGER_ESTADO_DISPAROU:
                self._disparos[lado] += 1
                self._disparou_em[lado] = agora
            ouvinte = self._gatilho_ouvinte
            if ouvinte is None:
                continue
            try:
                ouvinte(lado, ant, novo, agora)
            except Exception as exc:
                logger.warning("motion_reader_gatilho_failed", err=str(exc))

    def _reset_gatilho(self) -> None:
        """Esquece o estado ao perder o fd; a contagem de disparos fica."""
        self._gatilho = None
        self._gatilho_desde = float("-inf")

    def _maybe_emit(self, window: bytes, now: float | None = None) -> None:
        """Entrega toda amostra distinta: a de valor repetido ou de carimbo repetido não sai.

        O carimbo zero é o do aparelho que não o preenche, e aí só o valor separa as amostras.
        """
        carimbo = window[_CARIMBO_NA_JANELA]
        if window == self._last_window or (
            carimbo == self._last_carimbo and any(carimbo)
        ):
            self._duplicados += 1
            return
        self._emit(window, self._time_fn() if now is None else now)

    def _emit(self, window: bytes, now: float) -> None:
        intervalo = now - self._last_emit_at
        if 0.0 < intervalo < _HZ_STALE_S:
            inst = 1.0 / intervalo
            self._emit_hz_ema = (
                inst
                if self._emit_hz_ema <= 0.0
                else _HZ_EMA_ALPHA * inst + (1.0 - _HZ_EMA_ALPHA) * self._emit_hz_ema
            )
        elif intervalo >= _HZ_STALE_S:
            self._emit_hz_ema = 0.0
        self._last_emit_at = now
        self._last_window = window
        self._last_carimbo = window[_CARIMBO_NA_JANELA]
        try:
            self._vpad.forward_motion(janela_que_sai(self._uniq_aberto, window))
            self._windows_emitted += 1
        except Exception as exc:
            logger.warning("motion_reader_forward_failed", err=str(exc))

    def _acompanhar_a_sessao_de_jogo(self) -> None:
        """Abre a conta da sessão quando o jogo abre o pad, e a fecha quando ele larga."""
        aberto = getattr(self._vpad, "game_open", False) is True
        if aberto and self._sessao_de_jogo is None:
            self._sessao_de_jogo = self.amostras
        elif not aberto:
            self._fechar_a_sessao_de_jogo(motivo="jogo_largou")

    def _fechar_a_sessao_de_jogo(self, *, motivo: str) -> None:
        """Uma linha do diário com as pontas da sessão de jogo que terminou."""
        inicio, self._sessao_de_jogo = self._sessao_de_jogo, None
        if inicio is None:
            return
        agora = self.amostras
        logger.info(
            "motion_reader_amostras_da_sessao",
            player=getattr(self._vpad, "player", "?"),
            motivo=motivo,
            **{nome: agora[nome] - inicio[nome] for nome in agora},
        )

__all__ = [
    "BATTERY_STATUS_OFFSET",
    "BUTTONS2_OFFSET",
    "HZ_DO_CABO",
    "INPUT_REPORT_BT",
    "INPUT_REPORT_BT_SIZE",
    "INPUT_REPORT_USB",
    "JACK_STATUS_OFFSET",
    "MIC_BUTTON_BIT",
    "MOTION_WINDOW_LEN",
    "MOTION_WINDOW_OFFSET",
    "REPOUSO_DO_MUDO_S",
    "TOUCHPAD_CLICK_BIT",
    "TRIGGER_ESTADO_DISPAROU",
    "TRIGGER_L2_STATUS_OFFSET",
    "TRIGGER_R2_STATUS_OFFSET",
    "TRIGGER_STATE_SHIFT",
    "PhysicalReportReader",
    "a_peca_calou",
    "decodificar_bateria",
    "extract_battery_status",
    "extract_estado_do_gatilho",
    "extract_estado_do_mic",
    "extract_jack_status",
    "extract_touchpad_click",
    "soltar_o_pad_da_peca_muda",
    "uniq_do_hidraw",
]
