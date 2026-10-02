"""Espelho de MOTION: hidraw cru do DualSense físico → vpad uhid (GYRO-01).

Por que este módulo existe
--------------------------
O vpad uhid (máscara DualSense Edge) monta o report 0x01 a partir do evdev do
físico — sticks/botões/d-pad — e deixava a janela de motion (bytes 15..39 do
payload: gyro, accel, sensor_timestamp e os 2 pontos de toque) NEUTRA. Medido
ao vivo (2026-07-19): o físico emite gyro a 250 Hz no USB e, no BT, em RAJADA
(veja "A taxa do rádio é RAJADA", abaixo) — e o nó Motion do vpad emite ZERO:
gyro aiming morto para quem joga pelo hefesto.

A cura é um espelho de report PARCIAL (ARCH-1 do estudo
`docs/process/estudos/2026-07-18-estudo-imu-touchpad-vpad.md`): uma thread
abre um 2º fd SOMENTE-LEITURA no hidraw do físico, extrai VERBATIM a janela
`raw[base+15 : base+40]` de cada report cru (0x01 USB, base 1; 0x31 BT, base 2
com CRC-32 validado — seed 0xA1, o `PS_INPUT_CRC32_SEED` do kernel) e a entrega
em `vpad.forward_motion(window)`. Cópia byte a byte: zero matemática, e o
`sensor_timestamp` (que o SDL usa como dt de integração do gyro e que o evdev
NÃO expõe) vem de graça. Sticks/botões continuam no caminho evdev endurecido.

O reader é o RELÓGIO: ao abrir o device ele liga `set_motion_streaming(True)`
no vpad — os forwards do poll loop (60 Hz) viram só-cache e cada janela nova
sai na taxa do físico, com throttle. Ao perder o device (hotplug, BT caiu,
retarget) desliga o streaming: o vpad volta ao delta de 60 Hz com IMU neutra —
fail-safe por construção, nunca um gyro congelado.

Throttle (obrigatório, não otimização): o BT desta máquina entrega em rajada,
com PICO de ~797 Hz por controle; sem cap, 4 vpads em co-op seriam ~3200
writes/s no /dev/uhid. A emissão é capada em `MOTION_EMIT_MAX_HZ` (250 Hz — a
taxa nativa USB, e a mesma faixa do rate-limit do REPLICA-03) com dedup por
valor e COALESCÊNCIA: janela retida é sobrescrita pela mais nova e a última
nunca se perde (flush no timeout do select).

O teto é uma GRADE DE PRAZO, e isso não é detalhe (GRADE-QUE-NAO-BATIA-01,
19/08/2026): ele pergunta "já chegou o próximo prazo?", nunca "já passou um
período desde a última entrega?". A segunda forma esteve no lugar até 19/08 e
custava 36% das amostras NO CABO — cada entrega carimbava o instante REAL da
chegada, empurrando a referência à frente, e o report seguinte chegava cedo por
essa mesma diferença. Basta a fonte estar um pelo ACIMA do teto (o cabo entrega
250,88 Hz contra 250,0 de cap) para meia amostra cair fora, e a taxa colapsar
para perto da metade. Ela sentiu isso como giroscópio aos saltos, com os valores
todos certos. Jogos integram gyro bem em
250 Hz; o timestamp do sensor segue exato em cada janela entregue.

A taxa do rádio é RAJADA, não uma taxa (medido em 11/08/2026)
-------------------------------------------------------------
Este módulo dizia "~765 Hz" para o BT. Aquilo era a média de UMA janela curta,
e a remedição de 11/08/2026 — cinco janelas de 8 a 10 s no mesmo controle, por
duas réguas (o relógio do host e o `sensor_timestamp` do próprio controle) —
mostrou que o rádio não tem "uma taxa". Fonte:
`docs/protocol/driver-hid-playstation.md`, seção "Rádio: variável, em rajadas,
e longe de 1000 Hz" (:740-761 e :902):

* **PICO, dentro da rajada:** o p05 do intervalo é teimosamente 1255 us —
  ~797 Hz instantâneos (:757-758). É este o número que dimensiona o
  /dev/uhid, porque é a taxa que chega quando chega.
* **SUSTENTADO:** não é estável. Caiu de ~334 Hz para ~55 Hz entre duas
  janelas consecutivas de 8 s, sem nada ter mudado; o p95 do intervalo chega
  a 187 ms. A faixa registrada é "entre ~55 e ~392 Hz" (:902).
* **Divergência de RÉGUA, registrada e não resolvida:**
  `docs/protocol/pilha-steam-input-xpad-sdl.md:753` escreve o piso como
  38 Hz — é a régua do controle (janela 4, 38,3 Hz); a de :902 é a do host
  (55,4 Hz na mesma janela). O teto (~392 Hz) é o mesmo nas duas. Quem citar
  um piso, cite junto de qual régua ele veio.

Isto NÃO é licença para afrouxar o teto de emissão — veja a nota do
`MOTION_EMIT_MAX_HZ`, mais abaixo. Nenhuma constante mudou por causa desta
remedição: o que estava errado era o número que as justificava, não elas.

Leitura NÃO reabre a guerra de escritores: a guerra (2026-07-18) é sobre
WRITERS no hidraw; o kernel replica cada input report para TODOS os fds
abertos (fila própria por leitor) — este fd O_RDONLY não rouba nada da
pydualsense nem do jogo, e não gera tráfego novo de rádio/USB.

O clique do touchpad pega carona (TOUCH-CLICK-01)
-------------------------------------------------
O mesmo report cru carrega, no byte de botões `payload[9]`, o
`DS_BUTTONS2_TOUCHPAD` — o clique do touchpad. Ele NÃO viajava: a janela
espelhada começa no byte 15, e o conjunto de botões que o caminho do jogo
repassa (`dispatch_gamepad`, `CoopManager.forward_all`) vem do nó evdev
PRINCIPAL, cujo `BUTTON_MAP` não tem touchpad. Quem produz os nomes
`touchpad_*_press` é o `TouchpadReader`, que lê o nó SEPARADO e cujo consumidor
é o teclado virtual — o jogo nunca via o botão acender.

Este reader passou a extrair também esse bit e a entregá-lo em
`vpad.forward_touchpad_click(bool)`, por BORDA. A escolha do lugar é o
requisito: o reader é POR JOGADOR (o do P1 nasce em
`daemon/subsystems/gamepad.py:start_motion_reader`, os do co-op em
`CoopManager._start_player_motion_reader`) e vive com o daemon — não com a
janela. O leitor por controle do `daemon/sensor_hub.py` é sob demanda da aba
Status, então amarrar o clique a ele faria o botão do jogador 2 depender de a
janela do Hefesto estar aberta.

O fone e o microfone pegam a mesma carona (JACK-QUE-NAO-LIGOU-01)
----------------------------------------------------------------
O byte 53 do payload (`status[1]`) diz ao jogo se há fone plugado no controle,
se há microfone e se ele está mudo. O vpad tinha o `forward_jack` desde 02/08
e ele NUNCA foi chamado — a sprint `2026-08-03-ENTREGA-QUE-NAO-LIGOU-01` já o
tinha declarado órfão, e seis dias depois continuava com zero referências. Pior:
mesmo fiado ele não emitiria, porque escrevia o cache e não chamava
`_emit_if_changed`. Os dois defeitos foram curados em 09/08/2026 — o chamador é
este reader, pela mesma razão do clique: o byte mora no report cru, fora da
janela de motion, e o reader é por jogador e vive com o daemon.

E a bateria, que é o mesmo defeito com 25 dias a mais (BATERIA-QUE-NAO-CHEGOU-01)
--------------------------------------------------------------------------------
O byte 52 diz ao jogo quanta carga o controle tem. O `forward_battery` do vpad
nasceu em 15/07 (`69951a7`) e nunca teve um único chamador em `src/` — e a
consequência estava escrita na docstring dele desde o primeiro dia: *"o vpad
anuncia 5% descarregando para sempre e o jogo mostra alerta de bateria fraca num
controle cheio"*. Ele tinha também o segundo defeito do jack, numa forma mais
sorrateira: chamava `_emit_if_changed()` **sem** `from_reader=True`, e o gate do
`_motion_streaming` — que está LIGADO exatamente quando há reader, o caso normal
— engolia a emissão. Fiado sem isso, ele continuaria não chegando ao jogo.

Nada aqui toca o cursor: o clique é um BIT no report do vpad, não um evento de
mouse. O descarte do movimento do dedo para o cursor enquanto o vpad está de pé
(`daemon/subsystems/mouse.discard_touchpad_motion`) e a exclusão do nó do vpad
do libinput (`assets/76-dualsense-touchpad-libinput-ignore.rules`) seguem
intocados — é o `TouchpadReader`/`UinputMouseDevice` que mexem em cursor, e
este módulo não fala com nenhum dos dois.
"""
from __future__ import annotations

import contextlib
import os
import threading
import time
from collections.abc import Callable
from typing import Any

from hefesto_dualsense4unix.core.ds_output_report import BT_INPUT_CRC_SEED, bt_crc32
from hefesto_dualsense4unix.core.virtual_motion import REGISTRO
from hefesto_dualsense4unix.utils.espera import prontos_para_ler
from hefesto_dualsense4unix.utils.logging_config import get_logger

logger = get_logger(__name__)

#: Report de input do DualSense por transporte (hid-playstation.c):
#: USB = 0x01 (64 B, payload começa em data[1]); BT = 0x31 (78 B, payload em
#: data[2] — 0x31 + 1 byte de header — e CRC-32 nos 4 últimos bytes).
INPUT_REPORT_USB = 0x01
INPUT_REPORT_BT = 0x31
INPUT_REPORT_BT_SIZE = 78
_USB_STRUCT_BASE = 1
_BT_STRUCT_BASE = 2

#: Bit 1 do byte 1 de um `0x31` de BT: **este report carrega ÁUDIO**, não
#: estado de input. Mesmo id, mesmo tamanho, mesmo CRC válido — só este bit
#: separa um do outro. Ver `_struct_base` e o PS-PRESO-01 de 16/08/2026.
#: Espelha `integrations/dualsense_bt_audio.INPUT_FLAG_AUDIO`; os dois estão
#: travados por teste, e a duplicação é para o caminho quente não importar
#: ctypes/libopus.
INPUT_FLAG_AUDIO = 0x02

#: Janela de motion DENTRO do payload (offsets do `struct dualsense_input_
#: report`): gyro[3] 15-20, accel[3] 21-26, sensor_timestamp 27-30, reserved2
#: 31, touch points 32-39. Mesmos números do `_MOTION_WINDOW` do vpad
#: (`integrations/uhid_gamepad.py`) — travados um no outro por teste.
MOTION_WINDOW_OFFSET = 15
MOTION_WINDOW_LEN = 25

#: TOUCH-CLICK-01 — o CLIQUE do touchpad dentro do payload: `buttons[2]` do
BUTTONS2_OFFSET = 9
TOUCHPAD_CLICK_BIT = 0x02

MIC_BUTTON_BIT = 0x04

#: microfone mudo no firmware (bit 2). Mesmo número do `_STATUS1_OFFSET` do
#: mora fora da janela de motion (15..39), chega de graça no mesmo report cru,
JACK_STATUS_OFFSET = 53

#:
BATTERY_STATUS_OFFSET = 52

_CARGA_DESCARREGANDO = 0x0
_CARGA_CARREGANDO = 0x1
_CARGA_CHEIO = 0x2

#: contagem antiga isso jogava fora 36% das amostras justamente no transporte em
MOTION_EMIT_MAX_HZ = 250.0

_READ_LEN = 128

_SELECT_TIMEOUT_S = 0.25

#: DualSense vivo emite SEMPRE" só vale NO CABO, onde os 250 Hz são
#: DualSense parado em BT caía num ciclo eterno a ~1 Hz: silêncio -> larga o
#: segundo, piscava o motion do vpad na mesma cadência e enchia o journal
#: cada meio minuto no pior caso, contra 30 no arranjo anterior.
_SILENCE_REOPEN_USB_S = 1.0
_SILENCE_REOPEN_BT_S = 30.0

#: Bus HID do `HID_ID` no sysfs (`BUS_USB` / `BUS_BLUETOOTH` do kernel).
_BUS_USB = 0x03
_BUS_BLUETOOTH = 0x05

#: Backoff de reconexão (mesma curva do `_EvdevReconnectLoop`).
_BACKOFF_START_S = 0.5
_BACKOFF_MAX_S = 5.0

#: Telemetria GYRO-03 — taxa de emissão (`emit_hz`) por EMA dos intervalos
#: entre entregas. Alpha 0.25 ≈ estabiliza em ~1 s a 250 Hz sem congelar em
#: transientes; acima de `_HZ_STALE_S` sem entrega a taxa reportada é 0.0
#: (uma EMA "congelada" de um fluxo morto mentiria 250 Hz para sempre).
_HZ_EMA_ALPHA = 0.25
_HZ_STALE_S = 1.0


#: Raiz do sysfs onde cada nó `hidraw` declara de quem é (`HID_UNIQ`).
_RAIZ_HIDRAW = "/sys/class/hidraw"


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
        with open(f"/sys/class/hidraw/{nome}/device/uevent", encoding="utf-8") as fh:
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

    Medido ao vivo na máquina dela: 3 minutos depois de a ponte do mic subir, os
    botões **MIC e PS** (que moram no mesmo `buttons[2]`) ficaram presos, e cada
    leitura disparava `ps_button_action_steam` — o daemon tentando abrir a Steam
    dezenas de vezes por segundo. Ela descreveu como *"o teclado e o mouse com
    vida própria"* e desligou o controle. Três segundos depois o controle caiu
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
        #: BATERIA-QUE-PULA-01 (16/09/2026) — o tamanho passou a ser conferido
        #: TAMBÉM no cabo. Esta linha era um `return` seco, e um `0x01` de dez
        #: bytes atravessava: medido, `_struct_base(bytes([0x01]) + bytes(9))`
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


def eh_report_de_estado(report: bytes) -> bool:
    """Este report cru é ESTADO DE INPUT? — a porta pública do `_struct_base`."""
    return _struct_base(report) is not None


# Na mesa dela — quatro DualSense por rádio, ~2.400 relatórios/s no total
# aparelho dela. O portão que trava a economia é


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
    kernel 6.18, e ela vale nos DOIS sentidos: é a mesma tabela que o
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
      que a casa já escolheu para esse byte, e ela não dispara alerta nenhum.
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
        max_hz: float = MOTION_EMIT_MAX_HZ,
        time_fn: Callable[[], float] = time.monotonic,
        opener: Callable[[str], int] | None = None,
    ) -> None:
        self._path_provider = path_provider
        self._vpad = vpad
        self._min_interval = 1.0 / float(max_hz) if max_hz > 0 else 0.0
        self._time_fn = time_fn
        # falha (o loop já trata com o backoff). Default = comportamento de
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
        self._wake_r, self._wake_w = _novo_wake_pipe()
        self._last_window: bytes | None = None
        self._pending: bytes | None = None
        self._last_emit_at = float("-inf")
        self._next_emit_at = float("-inf")
        self._touchpad_click: bool | None = None
        self._touchpad_clicks = 0
        self._mic_button: bool | None = None
        self._mic_button_forwards = 0
        self._jack_status: int | None = None
        self._jack_forwards = 0
        self._battery_status: int | None = None
        self._battery_forwards = 0
        self._reports_seen = 0
        self._windows_emitted = 0
        self._bt_drops = 0
        self._emit_hz_ema = 0.0


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
    def emit_hz(self) -> float:
        """Taxa de emissão ao vpad (Hz, EMA) — 0.0 quando o fluxo parou.

        GYRO-03: é ESTA taxa (pós-throttle, o que o vpad de fato recebe) que
        o `state_full` publica como `motion_hz`. "Parou" = nenhuma entrega há
        mais de `_HZ_STALE_S` — a EMA antiga de um fluxo morto não vale nada.
        """
        if self._emit_hz_ema <= 0.0:
            return 0.0
        if (self._time_fn() - self._last_emit_at) > _HZ_STALE_S:
            return 0.0
        return round(self._emit_hz_ema, 1)


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
        própria thread fecha o fd dela no finally. O wake acorda o select na
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
        """Lê reports até o fd morrer (ENODEV), silêncio longo ou sinal de fora."""
        silencio = 0.0
        while not self._stop_flag.is_set():
            if self._reopen_flag.is_set():
                self._reopen_flag.clear()
                return
            try:
                pronto = prontos_para_ler([fd, self._wake_r], _SELECT_TIMEOUT_S)
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
                silencio += _SELECT_TIMEOUT_S
                self._flush_pending()
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
            self._reports_seen += 1
            base = _struct_base(data)
            if base is None:
                if data[0] == INPUT_REPORT_BT:
                    self._bt_drops += 1
                continue
            self._observe_touchpad_click(data, base)
            self._observe_mic_button(data, base)
            self._observe_jack(data, base)
            self._observe_battery(data, base)
            window = _janela_com_base(data, base)
            if window is None:
                continue
            self._maybe_emit(window)


    def _observe_touchpad_click(self, report: bytes, base: int | None = None) -> None:
        """Entrega ao vpad a BORDA do clique do touchpad deste report cru.

        Só borda: o report vem a 250 Hz no cabo e em rajada no rádio (pico de
        ~797 Hz, 11/08/2026), e repetir "ainda apertado" em cada um seria um
        write no /dev/uhid por report, justamente o que o throttle do motion
        existe para evitar.

        `None` do extrator (report de outro id, curto, ou CRC de BT ruim) é
        "não sei" e NÃO mexe no estado — nem entrega, nem solta. Vpad sem o
        método (uinput, fakes de teste) degrada calado: é o mesmo contrato
        duck-typed do `forward_motion`.

        `base` é a saída de `_struct_base` para ESTE report, quando quem chama
        já a tem (DAEMON-ACORDADO-01: o laço quente resolve uma vez e passa
        para os quatro consumidores). Omitir é a forma de quem só tem o report
        na mão — e ela resolve a base aqui, como sempre fez.
        """
        pressed = (
            _clique_com_base(report, base)
            if base is not None
            else extract_touchpad_click(report)
        )
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


    def _maybe_emit(self, window: bytes, now: float | None = None) -> None:
        """Dedup por valor + cap de taxa com coalescência do último valor."""
        if window == self._last_window:
            return
        if now is None:
            now = self._time_fn()
        if now < self._next_emit_at:
            self._pending = window
            return
        self._pending = None
        self._emit(window, now)

    def _flush_pending(self, now: float | None = None) -> None:
        """Entrega a janela retida quando o cap venceu e o fluxo parou."""
        pending = self._pending
        if pending is None:
            return
        if now is None:
            now = self._time_fn()
        if now < self._next_emit_at:
            return
        self._pending = None
        if pending == self._last_window:
            return
        self._emit(pending, now)

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
        proximo = self._next_emit_at + self._min_interval
        self._next_emit_at = (
            proximo
            if proximo >= now - self._min_interval
            else now + self._min_interval
        )
        self._last_emit_at = now
        self._last_window = window
        try:
            self._vpad.forward_motion(REGISTRO.filtrar(self._uniq_aberto, window))
            self._windows_emitted += 1
        except Exception as exc:
            logger.warning("motion_reader_forward_failed", err=str(exc))


__all__ = [
    "BATTERY_STATUS_OFFSET",
    "BUTTONS2_OFFSET",
    "INPUT_REPORT_BT",
    "INPUT_REPORT_BT_SIZE",
    "INPUT_REPORT_USB",
    "JACK_STATUS_OFFSET",
    "MIC_BUTTON_BIT",
    "MOTION_EMIT_MAX_HZ",
    "MOTION_WINDOW_LEN",
    "MOTION_WINDOW_OFFSET",
    "TOUCHPAD_CLICK_BIT",
    "PhysicalReportReader",
    "decodificar_bateria",
    "eh_report_de_estado",
    "extract_battery_status",
    "extract_estado_do_mic",
    "extract_jack_status",
    "extract_touchpad_click",
    "uniq_do_hidraw",
]
