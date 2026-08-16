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
nunca se perde (flush no timeout do select). Jogos integram gyro bem em
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
import select
import threading
import time
from collections.abc import Callable
from typing import Any

from hefesto_dualsense4unix.core.ds_output_report import BT_INPUT_CRC_SEED, bt_crc32
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
#: `struct dualsense_input_report` (payload[9]), bit 1 = `DS_BUTTONS2_TOUCHPAD`
#: do hid-playstation.c. Mesmos números do `_BUTTONS2_OFFSET`/`_TOUCHPAD_BIT`
#: do vpad (`integrations/uhid_gamepad.py`) — travados um no outro por teste.
#:
#: Ele está FORA da janela de motion (que começa no 15) e fora do vocabulário
#: do evdev principal (o `BUTTON_MAP` do `EvdevReader` não tem touchpad: o nó
#: do touchpad é separado, e quem o lê é o `TouchpadReader`, do caminho do
#: teclado/cursor). Este byte é a ÚNICA fonte de clique que o caminho do jogo
#: alcança sem depender de nó extra nem de janela aberta — e ele já chega aqui
#: de graça, no mesmo report que o motion.
BUTTONS2_OFFSET = 9
TOUCHPAD_CLICK_BIT = 0x02

#: JACK-QUE-NAO-LIGOU-01 — o byte de `status[1]` dentro do payload
#: (`payload[53]`): fone plugado (bit 0), microfone presente (bit 1) e
#: microfone mudo no firmware (bit 2). Mesmo número do `_STATUS1_OFFSET` do
#: vpad (`integrations/uhid_gamepad.py`) — travados um no outro por teste.
#:
#: Ele pega carona aqui pelo MESMO argumento que o clique do touchpad já usou:
#: mora fora da janela de motion (15..39), chega de graça no mesmo report cru,
#: e o reader é POR JOGADOR e vive com o daemon — não com a janela. O
#: `forward_jack` do vpad existia desde 02/08 sem um único chamador, e a
#: sprint `2026-08-03-ENTREGA-QUE-NAO-LIGOU-01` já o tinha declarado órfão.
JACK_STATUS_OFFSET = 53

#: BATERIA-QUE-NAO-CHEGOU-01 (09/08/2026) — o byte de `status[0]` dentro do
#: payload (`payload[52]`): nibble baixo = nível, nibble alto = estado de
#: carga. Mesmo número do `_STATUS_OFFSET` do vpad
#: (`integrations/uhid_gamepad.py`) — travados um no outro por teste.
#:
#: Terceiro passageiro da mesma carona, pelo mesmo argumento do clique e do
#: jack: mora fora da janela de motion (15..39) e chega de graça no mesmo
#: report cru. O `forward_battery` do vpad nasceu em 15/07 (`69951a7`) e
#: passou 25 dias com ZERO chamadores em `src/` — a consequência estava
#: escrita na própria docstring dele desde o primeiro dia: *"o vpad anuncia 5%
#: descarregando para sempre e o jogo mostra alerta de bateria fraca num
#: controle cheio"*.
BATTERY_STATUS_OFFSET = 52

#: A tabela do `dualsense_parse_report` (kernel 6.18, `hid-playstation.c`) —
#: grau **ALTA** pela régua da referência canônica (§6 e a linha 52,
#: `ucBatteryLevel` = `nibble*10+5`), porque está no kernel mainline e é o
#: MESMO código que vai ler o report do nosso vpad do outro lado.
#:
#: nibble alto  significado                       o que o kernel faz
#: -----------  -------------------------------   ------------------------
#: 0x0          descarregando                     capacidade = nibble*10+5
#: 0x1          carregando                        capacidade = nibble*10+5
#: 0x2          cheio (na base)                   capacidade = 100
#: 0xa, 0xb     tensão/temperatura fora de faixa  capacidade = 0
#: 0xf          erro de carga                     capacidade = 0
_CARGA_DESCARREGANDO = 0x0
_CARGA_CARREGANDO = 0x1
_CARGA_CHEIO = 0x2

#: Cap da taxa de emissão ao vpad. 250 Hz = taxa nativa do físico em USB (nada
#: é jogado fora no cabo) e o mesmo teto do rate-limit do REPLICA-03; em BT
#: (rajada, pico de ~797 Hz) vira downsample com coalescência — o estudo
#: aceita 250-500 Hz.
#:
#: TETO-DE-EMISSÃO-01 (13/08/2026) — POR QUE O TETO FICA. A remedição de
#: 11/08/2026 (veja o bloco "A taxa do rádio é RAJADA", no topo do módulo)
#: registra o rádio sustentando "entre ~55 e ~392 Hz"
#: (`docs/protocol/driver-hid-playstation.md:902`). Ler isso como "o rádio é
#: mais lento que 250 Hz, logo o cap sobrou" é a leitura ERRADA, e é o motivo
#: desta nota existir: o que o /dev/uhid tem de aguentar não é a média, é o
#: PICO DENTRO da rajada — p05 do intervalo em 1255 us, ~797 Hz (:757-758).
#: Sem teto, quatro vpads em co-op fariam ~3200 writes/s no /dev/uhid.
#:
#: O valor 250.0 NÃO muda: é decisão medida (a taxa nativa do cabo, onde
#: nada se perde) e o estudo do IMU a aceita. O que a remedição corrigiu foi
#: o número que a justificava, não ela. `tests/unit/test_teto_de_emissao.py`
#: reprova se esta constante sumir, subir, ou deixar de ser o default do
#: `PhysicalReportReader`.
MOTION_EMIT_MAX_HZ = 250.0

#: Tamanho de leitura: cobre 64 (USB) e 78 (BT) com folga.
_READ_LEN = 128

#: Timeout do select por iteração — o teto de latência para ver o stop_flag e
#: para o flush da janela retida pelo throttle quando o fluxo para.
_SELECT_TIMEOUT_S = 0.25

#: Silêncio máximo com o fd aberto antes de declarar o físico mudo e reabrir.
#: Larga o fd, desliga o streaming (fail-safe p/ 60 Hz) e re-resolve o path
#: (o provider aponta o primário ATUAL).
#:
#: GYRO-BT-SILENCIO-01: o teto é POR TRANSPORTE porque a premissa "um
#: DualSense vivo emite SEMPRE" só vale NO CABO, onde os 250 Hz são
#: constantes. No rádio ele emite em RAJADA — o p95 do intervalo chega a
#: 187 ms mesmo com o enlace vivo (11/08/2026,
#: `docs/protocol/driver-hid-playstation.md:757-758`) — e o
#: firmware emudece quando o controle está em repouso: o mesmo fato que o
#: projeto já tinha medido em outro contexto ("firmware BT ocioso emudece",
#: achado do veneno do launch option). Com 1 s valendo para os dois, um
#: DualSense parado em BT caía num ciclo eterno a ~1 Hz: silêncio -> larga o
#: fd -> `set_motion_streaming(False)` -> reabre pelo broker -> streaming
#: True -> silêncio de novo. Isso queimava um round-trip de SCM_RIGHTS por
#: segundo, piscava o motion do vpad na mesma cadência e enchia o journal
#: (~1.600 linhas em 45 min só desse laço).
#:
#: No cabo o valor antigo continua: 1 s mudo com 250 Hz nominais É link morto.
#: Em BT o silêncio não é evidência de nada, então o teto vira só uma rede de
#: segurança para o nó obsoleto que não deu ENODEV — 30 s custa um reopen a
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


def _open_por_caminho(path: str) -> int:
    """Opener default (sem broker): o `os.open` por caminho de sempre.

    BROKER-01 (Onda S): o construtor aceita um `opener` injetável — o
    broker-aware (`integrations.hidraw_broker_client.make_broker_opener`)
    pede o fd ao broker root (funciona com o nó ESCONDIDO pelo hide) e cai
    neste mesmo `os.open` quando o broker está ausente/recusou/timeout.
    """
    return os.open(path, os.O_RDONLY)


def _novo_wake_pipe() -> tuple[int, int]:
    """Par de self-pipe (não-bloqueante) para acordar o select do reader.

    GYRO-FD-01: `stop()`/`request_reopen()` NUNCA fecham o fd do hidraw de
    fora — só escrevem 1 byte aqui. Fechar de fora libera o NÚMERO do fd
    enquanto a thread ainda está em select/read nele; qualquer open
    concorrente do daemon (eventX do `_recompute_primary`, /dev/uhid de um
    vpad novo) recicla o número e o reader passa a drenar um fd ALHEIO —
    input do jogo congela e a janela fatiada vira gyro-lixo no vpad.
    """
    lado_r, lado_w = os.pipe()
    os.set_blocking(lado_r, False)
    os.set_blocking(lado_w, False)
    return lado_r, lado_w


def silence_budget_for(path: str | None) -> float:
    """Teto de silêncio (s) do nó `path`, decidido pelo BUS do sysfs.

    GYRO-BT-SILENCIO-01. O bus sai de `/sys/class/hidraw/<nó>/device/uevent`
    (`HID_ID=000<bus>:<vendor>:<product>`) — o mesmo campo que o resto do
    projeto já usa para separar cabo de rádio, e um fato do kernel, não uma
    inferência sobre o conteúdo dos reports. Decidir pelo primeiro report
    lido não serviria: o caso que interessa é justamente o do controle que
    NUNCA emitiu.

    Desconhecido cai no teto de BT (o generoso): errar para o lado do cabo
    devolveria o laço a 1 Hz, enquanto errar para o lado do rádio custa no
    máximo meio minuto a mais para largar um nó já morto — e o ENODEV do
    hotplug continua sendo o caminho normal de saída nos dois transportes.
    """
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
        return _USB_STRUCT_BASE
    if report[0] == INPUT_REPORT_BT:
        if len(report) != INPUT_REPORT_BT_SIZE:
            return None
        if report[1] & INPUT_FLAG_AUDIO:
            # Áudio, não input. Descartar é o certo: o payload aqui é Opus.
            return None
        crc = int.from_bytes(report[-4:], "little")
        if bt_crc32(report[:-4], seed=BT_INPUT_CRC_SEED) != crc:
            return None
        return _BT_STRUCT_BASE
    return None


def extract_motion_window(report: bytes) -> bytes | None:
    """Janela de motion (25 B) de um report CRU do físico, ou None.

    - ``0x01`` (USB): janela = ``report[16:41]``.
    - ``0x31`` (BT): janela = ``report[17:42]``, só com CRC válido.
    - Qualquer outro id/tamanho → None. Report curto demais → None.
    """
    base = _struct_base(report)
    if base is None:
        return None
    start = base + MOTION_WINDOW_OFFSET
    end = start + MOTION_WINDOW_LEN
    if len(report) < end:
        return None
    return bytes(report[start:end])


def extract_touchpad_click(report: bytes) -> bool | None:
    """Clique do touchpad de um report CRU do físico, ou None (TOUCH-CLICK-01).

    ``None`` significa "este report não diz nada sobre o clique" (id
    desconhecido, tamanho curto, CRC de BT ruim) — e é DIFERENTE de ``False``,
    que é "o report chegou íntegro e o dedo não está apertando". Quem consome
    tem de tratar os dois separados: transformar um CRC ruim em ``False``
    soltaria o botão no meio de uma pressionada.
    """
    base = _struct_base(report)
    if base is None:
        return None
    idx = base + BUTTONS2_OFFSET
    if len(report) <= idx:
        return None
    return bool(report[idx] & TOUCHPAD_CLICK_BIT)


def extract_jack_status(report: bytes) -> int | None:
    """Byte de fone/microfone (`status[1]`) de um report CRU, ou None.

    JACK-QUE-NAO-LIGOU-01. Mesma disciplina de transporte do clique
    (`_struct_base`, com CRC do BT): ``None`` é *"este report não diz nada
    sobre o jack"* — id desconhecido, tamanho curto, CRC ruim — e é DIFERENTE
    de ``0x00``, que é *"o report chegou íntegro e não há fone nem microfone"*.
    Confundir os dois faria um pacote corrompido de rádio desplugar o fone
    dentro do jogo.

    Devolve o byte INTEIRO, sem máscara: quem decide o que encaminhar é o vpad
    (`forward_jack` filtra pelos três bits conhecidos). O extrator lê o
    aparelho; a política de o que sai no report é do outro lado.
    """
    base = _struct_base(report)
    if base is None:
        return None
    idx = base + JACK_STATUS_OFFSET
    if len(report) <= idx:
        return None
    return int(report[idx])


def extract_battery_status(report: bytes) -> int | None:
    """Byte de bateria (`status[0]`) de um report CRU, ou None.

    BATERIA-QUE-NAO-CHEGOU-01. Mesma disciplina de transporte do clique e do
    jack (`_struct_base`, com CRC do BT): ``None`` é *"este report não diz
    nada sobre bateria"* — id desconhecido, tamanho curto, CRC ruim — e é
    DIFERENTE de ``0x00``, que é um controle descarregando com 5%. Confundir
    os dois faria um pacote corrompido de rádio anunciar bateria acabando no
    meio da partida dela.

    Devolve o byte INTEIRO, sem decodificar: a leitura é do aparelho, e o que
    significa cada nibble é a `decodificar_bateria`, logo abaixo.
    """
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
    """Thread que espelha a janela de motion do hidraw físico no vpad.

    `path_provider` (e não um path fixo) é a chave do retarget: a cada
    (re)abertura o reader pergunta "qual é o hidraw AGORA?" — troca de
    primário, reconexão BT e re-enumeração convergem sozinhas, e
    `request_reopen()` (chamado pelo backend em `_recompute_primary`) só
    precisa SINALIZAR (flag + self-pipe) para a própria thread largar o fd
    e a próxima volta resolver o nó certo — nunca um close de fora
    (GYRO-FD-01: número de fd liberado sob select seria reciclável).

    O contrato com o vpad são dois métodos: `set_motion_streaming(bool)` nas
    bordas abrir/perder e `forward_motion(window)` por janela (já throttled).
    """

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
        # BROKER-01 (Onda S §6.2): opener injetável — TODOS os gatilhos de
        # reopen (start inicial, silêncio ≥1 s, request_reopen do retarget,
        # ENODEV de wake BT/hotplug, backoff pós-falha) convergem no ÚNICO
        # open do `_run()`, então a injeção cobre todos por construção.
        # Contrato: devolve fd pronto para select/read; levanta OSError em
        # falha (o loop já trata com o backoff). Default = comportamento de
        # hoje (os.open por caminho). GYRO-FD-01 intacto: o opener é chamado
        # SEMPRE da própria thread do reader, que segue dona única do fd.
        self._opener: Callable[[str], int] = (
            opener if opener is not None else _open_por_caminho
        )
        self._stop_flag = threading.Event()
        self._thread: threading.Thread | None = None
        # fd ativo — a thread do reader é a ÚNICA dona (abre, usa e fecha).
        # Quem está fora só SINALIZA (flag + 1 byte no self-pipe): fechar de
        # fora liberaria o número do fd com a thread ainda em select/read
        # nele, e um open concorrente do daemon poderia RECICLAR o número
        # (reader drenando fd alheio = input congelado + gyro-lixo).
        self._fd: int | None = None
        self._fd_lock = threading.Lock()
        # Self-pipe de wake + flag de reopen (GYRO-FD-01). O par é recriado
        # no `start()` se um `stop()` anterior o fechou. O lock cobre a
        # corrida `_wake()` vs `_close_wake_pipe()`: escrever num número já
        # fechado/reciclado seria o mesmo defeito em miniatura.
        self._reopen_flag = threading.Event()
        self._wake_lock = threading.Lock()
        self._wake_r, self._wake_w = _novo_wake_pipe()
        # Throttle: último valor ENTREGUE (dedup), retido (coalescência) e o
        # instante da última entrega.
        self._last_window: bytes | None = None
        self._pending: bytes | None = None
        self._last_emit_at = float("-inf")
        # TOUCH-CLICK-01: último clique ENTREGUE ao vpad. `None` = nada
        # entregue ainda nesta abertura do fd — é o que faz o primeiro report
        # depois de reabrir re-sincronizar o botão, mesmo que o estado seja o
        # mesmo de antes da queda (o vpad solta o clique no
        # `set_motion_streaming(False)` do fail-safe, então o cache tem de
        # esquecer junto ou a pressionada não voltaria a ser entregue).
        self._touchpad_click: bool | None = None
        self._touchpad_clicks = 0
        # JACK-QUE-NAO-LIGOU-01: último byte de fone/mic ENTREGUE ao vpad.
        # `None` = nada entregue nesta abertura do fd, e é o que faz o primeiro
        # report depois de reabrir re-sincronizar o jack — o vpad zera o byte no
        # fail-safe de `set_motion_streaming(False)`, então o cache do reader
        # tem de esquecer junto ou um fone plugado antes da queda nunca mais
        # seria anunciado ao jogo.
        self._jack_status: int | None = None
        self._jack_forwards = 0
        # BATERIA-QUE-NAO-CHEGOU-01: último byte de bateria ENTREGUE ao vpad,
        # pelo mesmo contrato do jack acima. `None` = nada entregue nesta
        # abertura do fd — e é ele que faz o primeiro report depois de reabrir
        # re-sincronizar a carga, porque o vpad volta a "não sei" no fail-safe
        # de `set_motion_streaming(False)`.
        self._battery_status: int | None = None
        self._battery_forwards = 0
        # Telemetria (GYRO-03 lê): reports vistos, janelas emitidas, drops de
        # CRC/tamanho no caminho BT e a taxa de emissão (EMA em Hz).
        self._reports_seen = 0
        self._windows_emitted = 0
        self._bt_drops = 0
        self._emit_hz_ema = 0.0

    # -- telemetria -------------------------------------------------------

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

    # -- ciclo de vida ----------------------------------------------------

    def start(self) -> bool:
        """Sobe a thread (idempotente). O device é aberto DENTRO do loop."""
        if self.is_running:
            return True
        self._stop_flag.clear()
        self._reopen_flag.clear()
        if self._wake_r < 0 or self._wake_w < 0:
            # Um stop() anterior fechou o self-pipe — recria para esta vida.
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
                # Thread morta de verdade: o self-pipe pode ir sem risco de
                # reciclagem (o start() recria se este reader voltar).
                self._close_wake_pipe()
        else:
            self._close_wake_pipe()
        # Idempotente com o finally do loop — cinto e suspensório: o vpad não
        # pode ficar em streaming sem reader vivo (input congelaria no jogo),
        # nem com o clique do touchpad preso (TOUCH-CLICK-01), nem com um fone
        # fantasma anunciado ao jogo (JACK-QUE-NAO-LIGOU-01), nem com a bateria
        # de um controle que já foi embora (BATERIA-QUE-NAO-CHEGOU-01).
        self._reset_touchpad_click()
        self._reset_jack()
        self._reset_battery()
        with contextlib.suppress(Exception):
            self._vpad.set_motion_streaming(False)

    def request_reopen(self, reason: str = "retarget") -> None:
        """Pede à thread que largue o fd atual e reabra pelo `path_provider`.

        Barato e não-bloqueante de propósito: o backend chama isto de dentro
        do `_recompute_primary` (sob o `_io_lock` dele). GYRO-FD-01: NUNCA
        toca o fd — fechar de fora liberaria o número com a thread ainda em
        select/read e um open concorrente o reciclaria (fd alheio drenado).
        """
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

    # -- loop -------------------------------------------------------------

    def _run(self) -> None:
        backoff = _BACKOFF_START_S
        while not self._stop_flag.is_set():
            # Pedido de reopen anterior a este resolve já está atendido POR
            # este resolve (o provider aponta o alvo ATUAL); um set depois
            # do clear é pedido novo e derruba o fd na 1ª iteração do loop.
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
            logger.info("motion_reader_started", path=path)
            with contextlib.suppress(Exception):
                self._vpad.set_motion_streaming(True)
            try:
                self._read_until_lost(fd, silence_budget_for(path))
            finally:
                self._close_fd("read_lost")
                # Fail-safe: sem fonte de motion o vpad volta ao ritmo do poll
                # com IMU neutra (nunca um gyro congelado na mira do jogo) e
                # com o clique do touchpad SOLTO (TOUCH-CLICK-01 — nunca um
                # botão preso abrindo o mapa sozinho). O reset local vem junto:
                # o vpad esqueceu, o cache do reader tem de esquecer também.
                # O jack anda junto (JACK-QUE-NAO-LIGOU-01, mesmo fail-safe), e
                # a bateria também (BATERIA-QUE-NAO-CHEGOU-01): perder o físico
                # com 8% no cache deixaria o jogo alertando bateria fraca para
                # um controle que nem está mais lá.
                self._reset_touchpad_click()
                self._reset_jack()
                self._reset_battery()
                with contextlib.suppress(Exception):
                    self._vpad.set_motion_streaming(False)
            if not self._stop_flag.is_set():
                time.sleep(0.1)  # graça antes de reabrir (padrão do evdev)

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

        `silencio_max` vem do transporte (`silence_budget_for`) — ver
        GYRO-BT-SILENCIO-01 na constante.

        GYRO-FD-01: o select vigia TAMBÉM o self-pipe — `stop()` e
        `request_reopen()` acordam a thread na hora sem nunca fechar o fd
        (que é fechado pelo finally do `_run`, sempre pela própria thread).
        """
        silencio = 0.0
        while not self._stop_flag.is_set():
            if self._reopen_flag.is_set():
                # Sinal que chegou fora do select (ex.: entre o open e a 1ª
                # iteração): larga o fd para o loop re-resolver o alvo.
                self._reopen_flag.clear()
                return
            try:
                pronto, _, _ = select.select(
                    [fd, self._wake_r], [], [], _SELECT_TIMEOUT_S
                )
            except (OSError, ValueError):
                return  # fd morreu debaixo do select (ENODEV de hotplug)
            if self._wake_r in pronto:
                self._drain_wake()
                if self._stop_flag.is_set():
                    return
                if self._reopen_flag.is_set():
                    self._reopen_flag.clear()
                    return
                continue  # byte velho de um wake já atendido — segue
            if not pronto:
                silencio += _SELECT_TIMEOUT_S
                self._flush_pending()
                if silencio >= silencio_max:
                    # No cabo isto é nó obsoleto/link morto; em BT é só o teto
                    # de segurança do controle em repouso. Larga e re-resolve
                    # (o provider re-aponta).
                    logger.info(
                        "motion_reader_silencio_reabrindo", limite_s=silencio_max
                    )
                    return
                continue
            silencio = 0.0
            try:
                data = os.read(fd, _READ_LEN)
            except OSError:
                return  # ENODEV: hotplug-out (o fd é sempre o NOSSO, vivo)
            if not data:
                return
            self._reports_seen += 1
            # TOUCH-CLICK-01: o clique sai ANTES do motion e por caminho
            # próprio. Não pode entrar no `_maybe_emit`: aquele dedupa e capa
            # pela JANELA, e o clique não está nela — um controle parado
            # (janela repetida) engoliria a pressionada. Aqui é por borda e na
            # hora; o custo é 2 writes extras por clique, contra os 250/s que
            # o throttle já governa.
            self._observe_touchpad_click(data)
            # JACK-QUE-NAO-LIGOU-01: o fone/microfone sai pelo mesmo caminho e
            # pelo mesmo motivo do clique — mora fora da janela de motion, e o
            # `_maybe_emit` dedupa e capa POR JANELA. Um controle parado na
            # mesa (janela repetida, ou BT em repouso) engoliria o "plugou o
            # fone" se ele dependesse da janela para viajar. Por BORDA: o byte
            # muda uma vez por plugada, não 250 vezes por segundo.
            self._observe_jack(data)
            # BATERIA-QUE-NAO-CHEGOU-01: e a bateria, pelo terceiro motivo
            # idêntico. Ela muda ~11 vezes numa descarga inteira, então o custo
            # de olhar por report é uma comparação de inteiro, e o de entregar
            # por borda é irrisório perto dos 250/s do motion.
            self._observe_battery(data)
            window = extract_motion_window(data)
            if window is None:
                if data[0] == INPUT_REPORT_BT:
                    self._bt_drops += 1
                continue
            self._maybe_emit(window)

    # -- clique do touchpad (TOUCH-CLICK-01) ------------------------------

    def _observe_touchpad_click(self, report: bytes) -> None:
        """Entrega ao vpad a BORDA do clique do touchpad deste report cru.

        Só borda: o report vem a 250 Hz no cabo e em rajada no rádio (pico de
        ~797 Hz, 11/08/2026), e repetir "ainda apertado" em cada um seria um
        write no /dev/uhid por report, justamente o que o throttle do motion
        existe para evitar.

        `None` do extrator (report de outro id, curto, ou CRC de BT ruim) é
        "não sei" e NÃO mexe no estado — nem entrega, nem solta. Vpad sem o
        método (uinput, fakes de teste) degrada calado: é o mesmo contrato
        duck-typed do `forward_motion`.
        """
        pressed = extract_touchpad_click(report)
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
        """Esquece o clique ao perder o fd — o vpad já o soltou no fail-safe.

        Sem este esquecimento, um dedo apertado no instante do hotplug ficaria
        `True` no cache: o vpad solta o botão em `set_motion_streaming(False)`
        e, na reabertura, o reader compararia `True == True` e nunca
        reentregaria a pressionada — clique morto até soltar e apertar de novo.
        """
        self._touchpad_click = None

    # -- fone e microfone do controle (JACK-QUE-NAO-LIGOU-01) -------------

    def _observe_jack(self, report: bytes) -> None:
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
        """
        status = extract_jack_status(report)
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
        """Esquece o fone ao perder o fd — o vpad já o zerou no fail-safe.

        Sem este esquecimento, um fone plugado no instante do hotplug ficaria
        no cache: o vpad zera o byte em `set_motion_streaming(False)` e, na
        reabertura, o reader compararia igual e nunca reentregaria — o jogo
        ficaria sem saber do fone até ela desplugar e plugar de novo.
        """
        self._jack_status = None

    # -- bateria do controle (BATERIA-QUE-NAO-CHEGOU-01) ------------------

    def _observe_battery(self, report: bytes) -> None:
        """Entrega ao vpad a MUDANÇA de bateria deste report cru.

        Terceiro irmão do `_observe_touchpad_click`, com as três defesas dele
        pelas mesmas razões: só borda, ``None`` do extrator não mexe no estado
        (CRC ruim de rádio não descarrega o controle dela) e vpad sem o método
        degrada calado — que aqui não é hipótese de teste: o `UinputGamepad`
        **não tem** `forward_battery`, porque o evdev não carrega bateria no
        mesmo canal. Vale para USB e para BT (o `_struct_base` já cuida dos
        dois transportes) e para os N controles, um reader por jogador.

        A comparação é com o byte CRU, e quem o traduz é a
        `decodificar_bateria`. É de propósito, e o motivo é o mesmo do jack:
        se o firmware mexer num bit que não sabemos ler, o cache muda, a
        tradução dá o mesmo par e o `forward_battery` sai cedo — nenhum report
        a mais no /dev/uhid.
        """
        status = extract_battery_status(report)
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
        """Esquece a bateria ao perder o fd — o vpad já voltou a "não sei".

        Mesma armadilha do fone, com um custo maior: sem este esquecimento, um
        controle que caiu com 8% ficaria 8% no cache do reader; o vpad volta
        para `_STATUS_DESCONHECIDO` no fail-safe e, na reabertura, o reader
        compararia igual e NUNCA reentregaria — o jogo passaria a partida
        inteira achando que o controle está cheio e carregando.
        """
        self._battery_status = None

    # -- throttle ---------------------------------------------------------

    def _maybe_emit(self, window: bytes, now: float | None = None) -> None:
        """Dedup por valor + cap de taxa com coalescência do último valor."""
        if window == self._last_window:
            return
        if now is None:
            now = self._time_fn()
        if (now - self._last_emit_at) < self._min_interval:
            # Retida pelo cap — a mais nova SEMPRE sobrescreve (coalescência);
            # sai no próximo report pós-janela ou no flush do select-timeout.
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
        if (now - self._last_emit_at) < self._min_interval:
            return
        self._pending = None
        if pending == self._last_window:
            return
        self._emit(pending, now)

    def _emit(self, window: bytes, now: float) -> None:
        # EMA da taxa ANTES de carimbar o novo instante (o intervalo é entre
        # a entrega anterior e esta). A 1ª entrega não tem intervalo (last é
        # -inf) e a EMA fica em 0 até a 2ª.
        intervalo = now - self._last_emit_at
        if 0.0 < intervalo < _HZ_STALE_S:
            inst = 1.0 / intervalo
            self._emit_hz_ema = (
                inst
                if self._emit_hz_ema <= 0.0
                else _HZ_EMA_ALPHA * inst + (1.0 - _HZ_EMA_ALPHA) * self._emit_hz_ema
            )
        elif intervalo >= _HZ_STALE_S:
            # Fluxo voltou depois de um buraco: recomeça a medição do zero
            # (misturar a EMA de antes do buraco distorceria a taxa nova).
            self._emit_hz_ema = 0.0
        self._last_emit_at = now
        self._last_window = window
        try:
            self._vpad.forward_motion(window)
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
    "MOTION_EMIT_MAX_HZ",
    "MOTION_WINDOW_LEN",
    "MOTION_WINDOW_OFFSET",
    "TOUCHPAD_CLICK_BIT",
    "PhysicalReportReader",
    "decodificar_bateria",
    "extract_battery_status",
    "extract_jack_status",
    "extract_motion_window",
    "extract_touchpad_click",
]
