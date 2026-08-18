"""Microfone do DualSense por BLUETOOTH — Opus tunelado em HID (BT-MIC-01).

Por que este módulo existe
--------------------------
Por USB o microfone do DualSense é um dispositivo de áudio USB comum e o
PipeWire o publica sozinho — é dele que o `app/mic_monitor.py` lê o nível.
Por **Bluetooth não existe fonte de áudio nenhuma**, e a razão não é bug do
BlueZ: o DualSense simplesmente **não implementa A2DP/HFP/HSP**. O SDP dele só
anuncia HID (`0x1124`) e PnP (`0x1200`) — comportamento CORRETO, confirmado
pelo mantenedor do BlueZ (Luiz Von Dentz, bluez/bluez#892: *"Doesn't seem like
it is using A2DP/HFP for audio, so I guess it is transmitted over HID so it
needs a kernel driver that can handle these reports"*). Forçar perfil no BlueZ
(`RegisterProfile`) é fantasia: aquilo registra SDP **local**, não muda o que o
controle fala.

O áudio vai **dentro do HID**, no canal L2CAP de interrupção, como quadros
**Opus**. O `hid-playstation` do kernel não trata esses reports (ele loga
"Unhandled reportID" e segue), então o `hidraw` os entrega intactos — dá para
fazer a ponte inteiramente em espaço de usuário, sem patch de kernel. Este
módulo é essa ponte, e é o primeiro daemon nativo de Linux a fazê-la: as
implementações que existiam do protocolo eram firmware de Pico 2 W
(`awalol/DS5Dongle`, MIT — de onde o protocolo abaixo foi extraído e conferido
byte a byte contra `src/audio.cpp`/`src/main.cpp`/`src/bt.cpp`) e hápticos
(`egormanga/SAxense`).

O protocolo (medido AO VIVO nesta máquina, 2026-07-25, DualSense por BT)
------------------------------------------------------------------------
**Ligar o mic (host → controle).** Output report **0x32**, 142 bytes. O corpo
do 0x32 é uma cadeia TLV de blocos ``[tag|flags][len][valor...]`` — o mesmo
envelope que o `update_state` do DS5Dongle usa para o SetState (tag 0x10) e
que o report 0x39 usa para hápticos (0x12) e alto-falante (0x13/0x16)::

    [0]        = 0x32                 report ID
    [1]        = seq << 4             nibble de sequência (ver "disputa", abaixo)
    [2]        = 0x11 | 0x80          tag 0x11 = AudioControl, bit7 = bloco presente
    [3]        = 1                    tamanho do valor do bloco
    [4]        = 0b011 liga / 0b010 desliga     ← o bit que destrava o mic por BT
    [5..137]   = 0
    [138..141] = CRC-32 little-endian, seed 0xA2 (header HIDP DATA|OUTPUT)

**Ouvir o mic (controle → host).** Input report **0x31**, os mesmos 78 bytes de
sempre. O byte ``[1]`` é seq+flags: bit0 = o pacote traz estado de input
(sticks/botões/IMU), **bit1 = o pacote traz ÁUDIO**. Os dois são exclusivos —
não cabem juntos em 78 bytes, e o firmware alterna::

    [0]      = 0x31
    [1] & 2  = pacote de ÁUDIO (se 0, é o report de input normal do kernel)
    [3..73]  = 71 bytes de Opus: mono, 48 kHz, quadro de 10 ms (480 amostras)
    [74..77] = CRC-32 little-endian, seed 0xA1 (o `PS_INPUT_CRC32_SEED`)

O CRC é o MESMO utilitário que o espelho de motion já usa: `bt_crc32` de
`core/ds_output_report.py`, com `BT_INPUT_CRC_SEED`/`BT_CRC_SEED`. Nada de
reimplementar tabela de CRC aqui.

A disputa do contador de sequência (o risco real de integração)
---------------------------------------------------------------
O `hid-playstation` mantém `ds->output_seq` e o rotaciona a cada report **0x31**
que ELE escreve (rumble, lightbar, gatilhos). Nós escrevemos **0x32**. Essa é a
mitigação de verdade e é estrutural, não sorte: *são report IDs diferentes* —
nunca montamos, tocamos ou renumeramos um 0x31, então o kernel continua dono
absoluto do fluxo dele e o nosso contador vive só neste processo.

Sobra a pergunta de se o FIRMWARE mantém um contador único para os dois IDs. A
evidência diz que não importa: o SDL manda 0 fixo em todo report BT desde
sempre e o controle aceita; e na medição ao vivo desta implementação os nossos
0x32 (seq 1 e 2) foram aceitos com o `hid-playstation` escrevendo 0x31 no mesmo
link, sem perder um único report de input. A segunda linha de defesa é a
PARCIMÔNIA: escrevemos 0x32 só na borda (ligar, desligar, e o re-arme quando o
fluxo de áudio morre) — nunca em regime. Um punhado de writes por sessão não
tem como esfomear o fluxo do kernel, mesmo no pior caso.

O preço do mic: ele divide a banda do rádio com o input
--------------------------------------------------------
Medido ao vivo (2026-07-25, A/B no mesmo controle, 3 s por janela)::

    mic DESLIGADO : input 260.4 Hz   audio   0.0 Hz   total 260.4 Hz
    mic LIGADO    : input 170.5 Hz   audio 106.2 Hz   total 276.7 Hz
    desligado again: input 274.3 Hz  audio   0.0 Hz   total 274.6 Hz

O TOTAL de pacotes por segundo é praticamente o mesmo: o áudio não abre um
canal novo, ele ocupa lugar na mesma fila. Ligar o mic custa ~35% dos reports
de input. 170 Hz segue muito acima do poll de 60 Hz do daemon (jogar não
piora), mas o espelho de motion — que mira 250 Hz — entrega menos janelas de
gyro enquanto o mic está no ar. Por isso a ponte é sempre um gesto explícito da
usuária, nunca algo que sobe sozinho: quem usa gyro aiming precisa saber que
está trocando uma coisa pela outra. E a recuperação é total no desligar (a
terceira linha da medição), o que confirma que o efeito é de banda e não um
estado que fica preso no firmware.

ABERTO — o gating do firmware (BT-MIC-GATING-01)
-------------------------------------------------
O microfone FUNCIONA (áudio real, decodificado, gravável), mas com o mic no ar
o firmware declara `MicMuted` (byte 55, bit 2) numa fração grande dos reports
de input, e os quadros de áudio dessa fração vêm silenciosos. Medido nesta
máquina, 6 s por janela::

    MicMuted=False : 405 quadros,  97% não-silenciosos, pico médio 9.1, máx 255
    MicMuted=True  : 767 quadros,  17% não-silenciosos, pico médio 1.1, máx  14

Ou seja: o flag é REAL e o áudio o segue. O ciclo de trabalho medido fica entre
55% e 75% de MUDO, o que na prática entrega ~40% do sinal.

O que já está PROVADO sobre ele:

* **A causa é o nosso próprio pedido de mic**, não um estado prévio. Sem o
  0x32 o flag é estável em False (1183 reports, ZERO transições); com ele,
  ~100 transições em 6 s; ao desligar, volta a False e fica. É uma reação do
  firmware ao mic ativo, não o botão físico de mute (nenhum humano alterna
  20 vezes por segundo).
* **Não é falta de "sustentação" do bloco AudioControl.** Refutado por medição:
  bloco completo (`0b01111111`, len 6, com volumes, buffer e o `packetCounter`
  avançando como no DS5Dongle) a 100 Hz — um bloco por quadro de áudio, a
  cadência exata da referência — deixa o MUDO em 60% contra 68% da borda
  simples. Marginal, e ao custo de 598 escritas contra UMA.
* **Não é o caminho do microfone.** `MicSelect` interno / auto / externo,
  fixado por bloco SetState (tag 0x10) com `MuteControl` zerado e
  `AllowAudioMute`, dá 56% / 59% / 69% de MUDO. Nenhum resolve.

Por isso o código mantém a borda simples (UMA escrita): as alternativas custam
centenas de escritas por segundo disputando o link com o `hid-playstation` e
não compram o problema de volta.

**Principal suspeito não testado**: existe um SEGUNDO escritor de 0x31 neste
device — o próprio daemon do hefesto, que emite output report a 60 Hz com
`valid_flag1` bit 0x02 (`POWER_SAVE_CONTROL_ENABLE`) SEMPRE asserido e
`common[9]` (MuteControl/PowerSave) escrito a cada quadro
(`core/backend_pydualsense.py`, no builder do report). É o padrão de "escritor
sem dono" que este projeto já pagou caro em outra área. O A/B decisivo —
medir o ciclo de trabalho do MUDO com o poll do daemon parado — NÃO foi feito
porque parar o daemon estava fora do que esta tarefa podia tocar. É o primeiro
experimento a rodar quando alguém retomar isto.

Enquanto isso, a `EstatisticaMic` expõe `mudo_pct` e o `mic bt` o imprime: dá
para medir a anomalia em um comando, com e sem daemon, sem instrumentar nada.

Invariantes (as mesmas do `app/mic_monitor.py`, pagas com os mesmos incidentes)
-------------------------------------------------------------------------------
* **Nada de busy-loop: o áudio é o relógio.** A thread da ponte fica BLOQUEADA
  num `select`+`read` do hidraw. Cada quadro de 10 ms chega quando o rádio o
  entrega; não existe laço de espera ativa em lugar nenhum (foi um laço desses
  que fez os 104% de CPU da v3.8.1).
* **Nada de subprocess na thread GTK.** `pactl` só roda no start/stop da ponte,
  na thread de quem chamou (CLI/daemon), nunca na interface.
* **Ausência é resposta.** Sem `libopus`, sem `pactl`, sem controle em BT, sem
  fd do hidraw ⇒ `disponivel()` é False e nada sobe. NUNCA publicamos uma
  source que só emitiria silêncio: um microfone falso é pior que microfone
  nenhum — é a mesma regra do medidor que prefere sumir a fingir zero.
* **Escrita de PCM NUNCA bloqueia.** O fifo do PipeWire é escrito em
  O_NONBLOCK e o quadro é DESCARTADO em EAGAIN. Bloquear ali penduraria a
  leitura do hidraw e estouraria a fila do kernel — em áudio ao vivo, atrasar
  é pior que perder.
"""
from __future__ import annotations

import contextlib
import ctypes
import fcntl
import os
import select
import shutil
import subprocess
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from hefesto_dualsense4unix.core.ds_output_report import (
    BT_CRC_SEED,
    BT_INPUT_CRC_SEED,
    bt_crc32,
)
from hefesto_dualsense4unix.utils.logging_config import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Protocolo — input 0x31 com carga de áudio
# ---------------------------------------------------------------------------

#: Report de input do DualSense por BT (o mesmo do espelho de motion).
INPUT_REPORT_BT = 0x31
INPUT_REPORT_BT_SIZE = 78

#: Bits do byte de seq+flags (`raw[1]`) do input BT. bit0 = o pacote traz o
#: estado de input; bit1 = o pacote traz um quadro de áudio do microfone.
INPUT_FLAG_HID = 0x01
INPUT_FLAG_AUDIO = 0x02

#: Janela do quadro Opus dentro do report de áudio. 3 + 71 = 74, e 74..77 é o
#: CRC — o quadro ocupa EXATAMENTE o que sobra do report de 78 bytes.
MIC_OPUS_OFFSET = 3
MIC_OPUS_LEN = 71

#: Formato do que sai do decodificador. O firmware manda quadros de 10 ms a
#: 48 kHz (TOC medido: CELT, 480 amostras por quadro) ≈ 100 pacotes/s.
MIC_TAXA_HZ = 48000
MIC_CANAIS = 1
MIC_AMOSTRAS_POR_QUADRO = 480
MIC_BYTES_POR_AMOSTRA = 2
MIC_BYTES_POR_QUADRO = MIC_AMOSTRAS_POR_QUADRO * MIC_CANAIS * MIC_BYTES_POR_AMOSTRA

# ---------------------------------------------------------------------------
# Protocolo — output 0x32 (AudioControl)
# ---------------------------------------------------------------------------

#: Output report de áudio de menor tamanho declarado pelo report descriptor do
#: DualSense em BT (`85 32 09 32 95 8d 91 02` = 141 bytes de payload + o ID).
AUDIO_OUTPUT_REPORT_ID = 0x32
AUDIO_OUTPUT_REPORT_LEN = 142

#: Tags dos blocos TLV do corpo. Só usamos o de AudioControl; os demais estão
#: aqui para quem for ler o protocolo depois (0x10 SetState, 0x12 hápticos,
#: 0x13/0x16 alto-falante) e para o teste que trava os valores.
BLOCO_SET_STATE = 0x10
BLOCO_AUDIO_CONTROL = 0x11
BLOCO_HAPTICS = 0x12
BLOCO_SPEAKER = 0x13

#: bit7 do byte de tag = "este bloco está presente". (bit6 = "vêm DOIS
#: sub-blocos do tamanho declarado" — é assim que o 0x39 manda dois blocos de 200 bytes de
#: Opus para o alto-falante com `len` 200. Não usamos.)
BLOCO_PRESENTE = 0x80
BLOCO_DUPLO = 0x40

#: Valor do bloco AudioControl. bit0 é o liga/desliga do microfone; o bit1
#: acompanha nas duas formas (é o que o firmware espera receber).
AUDIO_CONTROL_MIC_ON = 0b011
AUDIO_CONTROL_MIC_OFF = 0b010

#: Offset do byte de estado do áudio dentro do report de INPUT (offset 53 do
#: `USBGetStateData` + 2 do envelope BT): bit0 fone plugado, bit1 mic externo
#: plugado, bit2 microfone MUDO pelo botão físico / powersave.
INPUT_OFFSET_AUDIO_STATUS = 55
STATUS_FONE_PLUGADO = 0x01
STATUS_MIC_EXTERNO = 0x02
STATUS_MIC_MUDO = 0x04


def montar_pedido_de_mic(ligar: bool, *, seq: int = 0) -> bytes:
    """Report 0x32 completo (142 B) que LIGA ou DESLIGA o microfone por BT.

    Um único bloco TLV de AudioControl. O CRC é o de OUTPUT (seed 0xA2), o
    mesmo `bt_crc32` que o `build_bt_report` do 0x31 usa — o firmware descarta
    silenciosamente qualquer report BT com CRC errado, e "não faz nada e não
    reclama" é exatamente o sintoma mais caro de depurar.
    """
    pkt = bytearray(AUDIO_OUTPUT_REPORT_LEN)
    pkt[0] = AUDIO_OUTPUT_REPORT_ID
    pkt[1] = (int(seq) & 0x0F) << 4
    pkt[2] = BLOCO_AUDIO_CONTROL | BLOCO_PRESENTE
    pkt[3] = 1
    pkt[4] = AUDIO_CONTROL_MIC_ON if ligar else AUDIO_CONTROL_MIC_OFF
    crc = bt_crc32(pkt[: AUDIO_OUTPUT_REPORT_LEN - 4], seed=BT_CRC_SEED)
    pkt[AUDIO_OUTPUT_REPORT_LEN - 4 :] = crc.to_bytes(4, "little")
    return bytes(pkt)


def eh_report_de_audio(raw: bytes | bytearray) -> bool:
    """True se este report de input BT carrega áudio em vez de estado de input."""
    return (
        len(raw) == INPUT_REPORT_BT_SIZE
        and raw[0] == INPUT_REPORT_BT
        and bool(raw[1] & INPUT_FLAG_AUDIO)
    )


def frame_opus_do_report(
    raw: bytes | bytearray, *, validar_crc: bool = True
) -> bytes | None:
    """Extrai os 71 bytes de Opus de um report 0x31 de áudio; None se não for.

    Devolve None (e não levanta) para QUALQUER coisa que não seja exatamente um
    report de áudio íntegro: tamanho errado, ID errado, bit de áudio apagado,
    CRC quebrado. O chamador não precisa distinguir os casos — todos querem a
    mesma ação, que é ignorar o pacote e esperar o próximo, 10 ms depois.

    `validar_crc=False` existe só para o teste que monta report sintético sem
    querer recalcular CRC; no caminho real o CRC é conferido SEMPRE (um quadro
    corrompido pelo rádio vira estouro audível no decodificador Opus).
    """
    if not eh_report_de_audio(raw):
        return None
    if validar_crc:
        esperado = int.from_bytes(raw[74:78], "little")
        if bt_crc32(raw[:74], seed=BT_INPUT_CRC_SEED) != esperado:
            return None
    return bytes(raw[MIC_OPUS_OFFSET : MIC_OPUS_OFFSET + MIC_OPUS_LEN])


def status_de_audio(raw: bytes | bytearray) -> int | None:
    """Byte de estado do áudio de um report de INPUT normal (None se for áudio).

    Só o report com estado de input carrega isso; o de áudio usa aquele mesmo
    espaço para Opus. Ler o byte do pacote errado devolveria bits de áudio
    comprimido interpretados como "fone plugado" — daí a checagem explícita.
    """
    if len(raw) != INPUT_REPORT_BT_SIZE or raw[0] != INPUT_REPORT_BT:
        return None
    if raw[1] & INPUT_FLAG_AUDIO or not raw[1] & INPUT_FLAG_HID:
        return None
    return int(raw[INPUT_OFFSET_AUDIO_STATUS])


# ---------------------------------------------------------------------------
# Descoberta dos DualSense em Bluetooth
# ---------------------------------------------------------------------------

#: Bus HID do `HID_ID` no sysfs (`BUS_BLUETOOTH` do kernel).
_BUS_BLUETOOTH = 0x05
_VENDOR_SONY = 0x054C
#: DualSense (0x0CE6) e DualSense Edge (0x0DF2). O vpad do próprio hefesto
#: também se apresenta como 0x0DF2, mas em `BUS_USB` — o filtro de bus já o
#: exclui, e o `HID_PHYS=hefesto-vpad` é a segunda rede.
_PRODUTOS_DUALSENSE = (0x0CE6, 0x0DF2)
_PHYS_VPAD = "hefesto-vpad"

_SYSFS_HIDRAW = "/sys/class/hidraw"


@dataclass(frozen=True)
class NoDualSenseBT:
    """Um DualSense falando por Bluetooth, do jeito que o sysfs o descreve."""

    caminho: str
    uniq: str
    produto: int

    @property
    def nome_curto(self) -> str:
        """Sufixo estável do MAC — o que vai no nome da source do PipeWire.

        Controle sem `HID_UNIQ` (raro, mas acontece em BT recém-pareado) cai no
        nome do nó: o que não pode é dois controles gerarem o MESMO nome de
        source e um sobrescrever o outro.
        """
        hexa = "".join(ch for ch in self.uniq.lower() if ch in "0123456789abcdef")
        if len(hexa) >= 6:
            return hexa[-6:]
        return self.caminho.rsplit("/", 1)[-1] or "desconhecido"


def _uevent(diretorio: Path) -> dict[str, str]:
    try:
        texto = (diretorio / "device" / "uevent").read_text(encoding="utf-8")
    except OSError:
        return {}
    out: dict[str, str] = {}
    for linha in texto.splitlines():
        chave, _, valor = linha.partition("=")
        if chave:
            out[chave.strip()] = valor.strip()
    return out


def nos_dualsense_bluetooth(raiz: str = _SYSFS_HIDRAW) -> list[NoDualSenseBT]:
    """Todos os DualSense conectados por BT, na ordem do sysfs.

    Sem BT nenhum devolve lista vazia — é o caminho normal de quem só usa cabo,
    não um erro.
    """
    achados: list[NoDualSenseBT] = []
    try:
        entradas = sorted(Path(raiz).iterdir())
    except OSError:
        return achados
    for entrada in entradas:
        info = _uevent(entrada)
        hid_id = info.get("HID_ID", "")
        partes = hid_id.split(":")
        if len(partes) != 3:
            continue
        try:
            bus, vendor, product = (int(p, 16) for p in partes)
        except ValueError:
            continue
        if bus != _BUS_BLUETOOTH or vendor != _VENDOR_SONY:
            continue
        if product not in _PRODUTOS_DUALSENSE:
            continue
        if info.get("HID_PHYS", "") == _PHYS_VPAD:
            continue
        achados.append(
            NoDualSenseBT(
                caminho=f"/dev/{entrada.name}",
                uniq=info.get("HID_UNIQ", ""),
                produto=product,
            )
        )
    return achados


# ---------------------------------------------------------------------------
# Decodificador Opus (ctypes sobre libopus.so.0)
# ---------------------------------------------------------------------------

#: `libopus` já vem instalada nesta plataforma (dependência de PipeWire,
#: Firefox, WebRTC...). Preferimos ctypes a um binding pip (`opuslib`/`PyOgg`)
#: DE PROPÓSITO: o projeto não adiciona dependência Python que precise de pip
#: ad-hoc quando a .so do sistema resolve — e um binding a menos é um caminho a
#: menos para quebrar no .deb/flatpak.
_SONAMES_OPUS = ("libopus.so.0", "libopus.so")

#: Códigos de erro da libopus que nos interessam citar em log.
OPUS_OK = 0


class DecodadorOpus:
    """Decodificador Opus mono 48 kHz — quadro de 71 B → 480 amostras s16le.

    Levanta `OpusIndisponivelError` na construção quando a `libopus` não está no
    sistema. Quem chama trata isso como "a ponte não sobe" (ausência é
    resposta), nunca como exceção a propagar para a interface.
    """

    def __init__(self, *, taxa_hz: int = MIC_TAXA_HZ, canais: int = MIC_CANAIS) -> None:
        self._lib = _carregar_libopus()
        erro = ctypes.c_int(0)
        ponteiro = self._lib.opus_decoder_create(taxa_hz, canais, ctypes.byref(erro))
        if not ponteiro or erro.value != OPUS_OK:
            raise OpusIndisponivelError(f"opus_decoder_create falhou: {erro.value}")
        self._dec: int | None = ponteiro
        self._canais = canais
        # Buffer reusado: alocar 480 int16 a 100 Hz por controle geraria lixo
        # de GC a cada 10 ms sem necessidade nenhuma.
        self._pcm = (ctypes.c_int16 * (MIC_AMOSTRAS_POR_QUADRO * canais))()

    def decodificar(self, quadro: bytes) -> bytes | None:
        """Quadro Opus → PCM s16le. None quando a libopus recusa o quadro.

        Um quadro recusado (rádio corrompeu abaixo do que o CRC pega, ou o
        firmware mandou algo fora do contrato) é DESCARTADO. Não interpolamos:
        o `module-pipe-source` já preenche o buraco com silêncio e 10 ms de
        silêncio é inaudível.
        """
        if self._dec is None:
            return None
        n = self._lib.opus_decode(
            self._dec,
            quadro,
            len(quadro),
            self._pcm,
            MIC_AMOSTRAS_POR_QUADRO,
            0,
        )
        if n <= 0:
            return None
        return bytes(memoryview(self._pcm).cast("B")[: n * self._canais * 2])

    def close(self) -> None:
        """Libera o decodificador. Idempotente."""
        if self._dec is not None:
            with contextlib.suppress(Exception):
                self._lib.opus_decoder_destroy(self._dec)
            self._dec = None

    def __enter__(self) -> DecodadorOpus:
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()


class OpusIndisponivelError(RuntimeError):
    """A libopus não está instalada (ou recusou criar o decodificador)."""


_LIB_OPUS: ctypes.CDLL | None = None
_LOCK_OPUS = threading.Lock()


def _carregar_libopus() -> ctypes.CDLL:
    """Carrega e prototipa a libopus uma vez por processo (sob lock).

    Duas pontes (dois controles) subindo em paralelo carregariam a .so duas
    vezes e prototipariam por cima uma da outra — é barato evitar.
    """
    global _LIB_OPUS
    if _LIB_OPUS is not None:
        return _LIB_OPUS
    with _LOCK_OPUS:
        if _LIB_OPUS is not None:
            return _LIB_OPUS
        lib: ctypes.CDLL | None = None
        for soname in _SONAMES_OPUS:
            try:
                lib = ctypes.CDLL(soname)
                break
            except OSError:
                continue
        if lib is None:
            raise OpusIndisponivelError(
                "libopus não encontrada (instale libopus0 — ver install.sh)"
            )
        lib.opus_decoder_create.restype = ctypes.c_void_p
        lib.opus_decoder_create.argtypes = [
            ctypes.c_int32,
            ctypes.c_int,
            ctypes.POINTER(ctypes.c_int),
        ]
        lib.opus_decoder_destroy.restype = None
        lib.opus_decoder_destroy.argtypes = [ctypes.c_void_p]
        lib.opus_decode.restype = ctypes.c_int
        lib.opus_decode.argtypes = [
            ctypes.c_void_p,
            ctypes.c_char_p,
            ctypes.c_int32,
            ctypes.POINTER(ctypes.c_int16),
            ctypes.c_int,
            ctypes.c_int,
        ]
        lib.opus_get_version_string.restype = ctypes.c_char_p
        lib.opus_get_version_string.argtypes = []
        _LIB_OPUS = lib
        return lib


def versao_libopus() -> str | None:
    """Versão da libopus, ou None se ela não estiver no sistema (p/ o doctor)."""
    try:
        bruto = _carregar_libopus().opus_get_version_string()
        # ctypes devolve `Any`; o gate de tipos é rígido e o retorno é público.
        return str(bytes(bruto).decode("utf-8", "replace"))
    except Exception:
        # Inclui `OpusIndisponivelError` e qualquer .so exótica que não exporte o
        # símbolo: um diagnóstico nunca derruba quem o chama.
        return None


# ---------------------------------------------------------------------------
# Publicação: source virtual do PipeWire alimentada por fifo
# ---------------------------------------------------------------------------

#: `module-pipe-source` publica uma source de CAPTURA de verdade (não um
#: `.monitor` de sink), alimentada por um fifo. É o caminho mais curto entre
#: "tenho PCM" e "o mic aparece em qualquer app": um módulo, um fifo, zero
#: processo intermediário segurando o áudio. A alternativa clássica
#: (null-sink + remap-source) precisaria de DOIS módulos e ainda publicaria um
#: `.monitor` no meio — que é justamente o que `fontes_dualsense()` do
#: `mic_monitor` aprendeu a descartar.
#:
#: ARMADILHA MEDIDA (2026-07-25, custou uma hora): a source só é LIGADA por um
#: gerenciador de sessão. Com o `wireplumber.service` parado, o módulo carrega,
#: `pactl list sources` mostra o nó — e ele fica em `SUSPENDED` para sempre:
#: ninguém cria o link do cliente que grava, o fifo enche, todo quadro vira
#: descarte e o `parec` colhe ZERO byte. O sintoma é indistinguível de "o
#: protocolo está errado". Se a ponte estiver decodificando (`quadros_audio`
#: subindo) e mesmo assim não sair áudio, o primeiro suspeito é
#: `systemctl --user status wireplumber`, não o DualSense.
_MODULO_PIPE_SOURCE = "module-pipe-source"

#: Tamanho do fifo. Ele é o ÚNICO buffer entre o rádio e o PipeWire, então ele
#: é o teto de latência: 8 KiB = 4096 amostras ≈ 85 ms. Maior só acumularia
#: áudio velho quando ninguém está gravando (a source fica SUSPENDED e não
#: drena) e o primeiro segundo de gravação sairia atrasado.
_FIFO_BYTES = 8192

_TIMEOUT_PACTL_S = 5.0

#: `fcntl.F_SETPIPE_SZ` não é exposto em toda build do CPython; o número é
#: estável no Linux desde o 2.6.35.
_F_SETPIPE_SZ = getattr(fcntl, "F_SETPIPE_SZ", 1031)


class SourceVirtualPipeWire:
    """Uma source de captura publicada no PipeWire, alimentada por um fifo.

    `nome` é o `source_name` (o que aparece em `pactl list sources short`);
    `descricao` é o rótulo legível que a bandeja de som mostra.  (noqa-acento:
    nomes dos parâmetros, não texto)
    """

    def __init__(
        self,
        *,
        nome: str,
        descricao: str,
        taxa_hz: int = MIC_TAXA_HZ,
        canais: int = MIC_CANAIS,
        runner: Callable[[list[str]], str | None] | None = None,
    ) -> None:
        self.nome = nome
        self.descricao = descricao
        self.taxa_hz = taxa_hz
        self.canais = canais
        self.runner = runner or _rodar
        self.descartes = 0
        self._module_id: str | None = None
        self._fifo: str | None = None
        self._fd: int | None = None

    # -- ciclo de vida ----------------------------------------------------

    def iniciar(self) -> bool:
        """Carrega o módulo e abre o fifo. False = não deu (e nada ficou de pé).

        Ordem obrigatória: o módulo PRIMEIRO. É ele quem cria o fifo e mantém a
        ponta de leitura aberta; abrir a ponta de escrita antes daria ENXIO.
        """
        if self._module_id is not None:
            return True
        if shutil.which("pactl") is None:
            logger.info("bt_mic_sem_pactl")
            return False
        self._fifo = self._caminho_do_fifo()
        with contextlib.suppress(OSError):
            os.unlink(self._fifo)
        saida = self.runner(
            [
                "pactl",
                "load-module",
                _MODULO_PIPE_SOURCE,
                f"source_name={self.nome}",
                f"file={self._fifo}",
                "format=s16le",
                f"rate={self.taxa_hz}",
                f"channels={self.canais}",
                # `priority.session` baixa de propósito: o mic do controle NÃO
                # deve virar a entrada padrão do sistema sozinho. É o mesmo
                # princípio do drop-in 51 do WirePlumber
                # (FEAT-WIREPLUMBER-DUALSENSE-NOT-DEFAULT-SOURCE-01) — "o
                # controle fica mexendo no microfone" foi um sintoma real.
                "source_properties="
                + " ".join(
                    (
                        f"device.description='{self.descricao}'",
                        "priority.session=200",
                        "device.icon_name=audio-input-microphone",
                    )
                ),
            ]
        )
        linhas = [ln.strip() for ln in (saida or "").splitlines() if ln.strip()]
        if not linhas or not linhas[-1].isdigit():
            logger.warning("bt_mic_load_module_falhou", saida=(saida or "")[:200])
            self._fifo = None
            return False
        self._module_id = linhas[-1]
        if not self._abrir_fifo():
            self.parar()
            return False
        logger.info(
            "bt_mic_source_publicada", source=self.nome, module_id=self._module_id
        )
        return True

    def parar(self) -> None:
        """Descarrega o módulo e fecha o fifo. Idempotente."""
        if self._fd is not None:
            with contextlib.suppress(OSError):
                os.close(self._fd)
            self._fd = None
        if self._module_id is not None:
            self.runner(["pactl", "unload-module", self._module_id])
            logger.info("bt_mic_source_removida", source=self.nome)
            self._module_id = None
        if self._fifo is not None:
            with contextlib.suppress(OSError):
                os.unlink(self._fifo)
            self._fifo = None

    # -- escrita ----------------------------------------------------------

    def escrever(self, pcm: bytes) -> bool:
        """Empurra PCM para o fifo SEM bloquear. False = quadro descartado.

        Descarte é comportamento CORRETO aqui, não falha: quando ninguém está
        gravando, a source fica suspensa e o PipeWire não drena o fifo — se
        bloqueássemos, a thread pararia de ler o hidraw, a fila do kernel
        estouraria e o prejuízo cairia no gyro e no rumble, que dividem o mesmo
        link. Em áudio ao vivo, perder 10 ms é invisível; atrasar não é.
        """
        if self._fd is None and not self._abrir_fifo():
            return False
        fd = self._fd
        if fd is None:
            return False
        try:
            os.write(fd, pcm)
        except BlockingIOError:
            self.descartes += 1
            return False
        except (BrokenPipeError, OSError):
            # PipeWire soltou a ponta de leitura (módulo descarregado por fora,
            # serviço reiniciado). Fecha e deixa a próxima escrita reabrir.
            # Fecha o `fd` LOCAL, não `self._fd`: outra thread pode tê-lo posto
            # em None entre o write e aqui, e aí o close receberia None.
            with contextlib.suppress(OSError):
                os.close(fd)
            self._fd = None
            return False
        return True

    # -- interno ----------------------------------------------------------

    def _caminho_do_fifo(self) -> str:
        base = os.environ.get("XDG_RUNTIME_DIR") or "/tmp"
        return os.path.join(base, f"hefesto-{self.nome}.fifo")

    def _abrir_fifo(self) -> bool:
        if self._fifo is None:
            return False
        try:
            fd = os.open(self._fifo, os.O_WRONLY | os.O_NONBLOCK)
        except OSError as exc:
            # ENXIO = o módulo ainda não abriu a ponta de leitura. Não é erro
            # fatal: a próxima escrita, 10 ms depois, tenta de novo.
            logger.debug("bt_mic_fifo_sem_leitor", fifo=self._fifo, err=str(exc))
            return False
        with contextlib.suppress(OSError):
            fcntl.fcntl(fd, _F_SETPIPE_SZ, _FIFO_BYTES)
        self._fd = fd
        return True


def _rodar(argv: list[str]) -> str | None:
    """Roda um comando curto e devolve o stdout (None em qualquer falha).

    Nunca `shell=True` (invariante do projeto) e sempre com timeout — um
    `pactl` pendurado num PipeWire morto não pode segurar o start da ponte.
    """
    if shutil.which(argv[0]) is None:
        return None
    try:
        proc = subprocess.run(
            argv,
            timeout=_TIMEOUT_PACTL_S,
            check=False,
            capture_output=True,
            text=True,
        )
    except Exception as exc:
        logger.debug("bt_mic_comando_falhou", argv=argv[0], err=str(exc))
        return None
    if proc.returncode != 0:
        logger.debug(
            "bt_mic_comando_rc", argv=argv[0], rc=proc.returncode, err=proc.stderr[:200]
        )
        return None
    return proc.stdout


# ---------------------------------------------------------------------------
# A ponte
# ---------------------------------------------------------------------------

#: Timeout do `select` por iteração — o teto de latência para ver o stop_flag
#: e para o watchdog de re-arme. Nada acontece nesse tempo: a thread DORME.
_SELECT_TIMEOUT_S = 0.25

#: Silêncio de áudio (com o mic supostamente ligado) que dispara UM re-arme.
#: O firmware manda ~100 quadros/s em CBR mesmo em sala silenciosa, então 2 s
#: sem quadro nenhum não é "ninguém falou": é o mic desligado. Acontece de
#: verdade quando o controle sai e volta do powersave, ou quando outro
#: escritor (o PS app rodando em Proton, por exemplo) manda o 0b010.
_REARME_S = 2.0

#: Piso entre dois re-armes. Sem isso um controle que RECUSA ligar o mic (fone
#: com mic externo em estado esquisito, firmware antigo) viraria um write a
#: cada 2 s para sempre — tráfego de rádio inútil disputando com o rumble.
_REARME_MIN_INTERVALO_S = 2.0

#: Leitura: cobre os 78 bytes do 0x31 com folga.
_READ_LEN = 128


@dataclass(frozen=True)
class EstatisticaMic:
    """Contadores da ponte — o que o `mic bt` e os testes olham.

    `input_mudos` sobre `quadros_input` é o CICLO DE TRABALHO do mute — a
    medida da anomalia aberta descrita no cabeçalho ("o gating do firmware").
    Ele existe para que a mantenedora possa medir o problema com um comando,
    em vez de acreditar num relatório.
    """

    quadros_audio: int = 0
    quadros_input: int = 0
    quadros_invalidos: int = 0
    quadros_descartados: int = 0
    input_mudos: int = 0
    rearmes: int = 0
    mudo: bool | None = None
    fone_plugado: bool | None = None
    source: str = ""

    @property
    def mudo_pct(self) -> float:
        """% dos reports de input em que o firmware declarou o mic MUDO."""
        if self.quadros_input <= 0:
            return 0.0
        return 100.0 * self.input_mudos / self.quadros_input


class PonteMicBluetooth:
    """Liga o mic de UM DualSense por BT e publica o áudio dele no PipeWire.

    Uso::

        ponte = PonteMicBluetooth(no)
        if ponte.iniciar():          # False = faltou libopus/pactl/hidraw
            ...                      # o áudio flui numa thread própria
            ponte.parar()            # devolve o controle ao estado anterior

    A thread fica bloqueada no `select` do hidraw: nenhum quadro é processado
    sem que o rádio o entregue, e o custo em repouso é zero. `parar()` é
    idempotente e SEMPRE manda o 0x32 de desligar — deixar o microfone de
    alguém ligado depois de fechar o programa não é opção.
    """

    def __init__(
        self,
        no: NoDualSenseBT,
        *,
        opener: Callable[[str], int] | None = None,
        decodificador: Any = None,
        source: Any = None,
        nome_source: str | None = None,
    ) -> None:
        self.no = no
        self._opener = opener or abrir_hidraw_rw
        self._decodificador_injetado = decodificador
        self._nome_source = nome_source or f"hefesto_dualsense_bt_{no.nome_curto}"
        self._source = source
        self._fd: int | None = None
        self._dec: Any = None
        self._thread: threading.Thread | None = None
        self._parar_evt = threading.Event()
        self._lock = threading.Lock()
        self._seq = 0
        self._ultimo_audio = 0.0
        self._ultimo_rearme = 0.0
        self._stats = EstatisticaMic(source=self._nome_source)

    # -- API pública ------------------------------------------------------

    @property
    def nome_source(self) -> str:
        return self._nome_source

    def estatistica(self) -> EstatisticaMic:
        """Snapshot dos contadores (barato: só lê um dataclass sob lock).

        `quadros_descartados` é o contador da SOURCE (quadro decodificado que o
        fifo não aceitou), então ele é COPIADO de lá, não somado — a ponte não
        tem contador próprio para isso e dois donos do mesmo número seria
        exatamente o vício que este projeto já pagou caro.
        """
        with self._lock:
            stats = self._stats
        source = self._source
        if source is None:
            return stats
        return EstatisticaMic(
            quadros_audio=stats.quadros_audio,
            quadros_input=stats.quadros_input,
            quadros_invalidos=stats.quadros_invalidos,
            quadros_descartados=int(getattr(source, "descartes", 0)),
            input_mudos=stats.input_mudos,
            rearmes=stats.rearmes,
            mudo=stats.mudo,
            fone_plugado=stats.fone_plugado,
            source=stats.source,
        )

    def iniciar(self) -> bool:
        """Sobe tudo: decodificador, source, fd do hidraw, thread e o 0x32.

        Devolve False sem deixar nada de pé se qualquer peça faltar. Ausência é
        resposta: não existe modo degradado com source publicada e sem áudio.
        """
        if self._thread is not None and self._thread.is_alive():
            return True
        try:
            self._dec = self._decodificador_injetado or DecodadorOpus()
        except OpusIndisponivelError as exc:
            logger.info("bt_mic_sem_libopus", err=str(exc))
            return False
        try:
            self._fd = self._opener(self.no.caminho)
        except OSError as exc:
            logger.info("bt_mic_hidraw_sem_acesso", no=self.no.caminho, err=str(exc))
            self._encerrar_decodificador()
            return False
        if self._source is None:
            self._source = SourceVirtualPipeWire(
                nome=self._nome_source,
                descricao=f"Microfone DualSense BT ({self.no.uniq or self.no.caminho})",
            )
        if not self._source.iniciar():
            self._fechar_fd()
            self._encerrar_decodificador()
            return False

        self._parar_evt.clear()
        self._ultimo_audio = time.monotonic()
        self._escrever_pedido(ligar=True)
        self._thread = threading.Thread(
            target=self._loop,
            name=f"hefesto-btmic-{self.no.nome_curto}",
            daemon=True,
        )
        self._thread.start()
        return True

    def parar(self) -> None:
        """Desliga o mic no controle, encerra a thread e remove a source."""
        self._parar_evt.set()
        thread = self._thread
        self._thread = None
        if thread is not None:
            thread.join(timeout=2.0)
        # O desligar vai DEPOIS do join: a thread ainda podia estar num
        # `select` sobre o mesmo fd, e o write concorrente não tem por que
        # correr com ela.
        self._escrever_pedido(ligar=False)
        self._fechar_fd()
        if self._source is not None:
            self._source.parar()
        self._encerrar_decodificador()

    def __enter__(self) -> PonteMicBluetooth:
        return self

    def __exit__(self, *_exc: object) -> None:
        self.parar()

    # -- laço -------------------------------------------------------------

    def _loop(self) -> None:
        """O áudio é o relógio: bloqueia no `select`, nunca gira em falso."""
        while not self._parar_evt.is_set():
            fd = self._fd
            if fd is None:
                return
            try:
                prontos, _, _ = select.select([fd], [], [], _SELECT_TIMEOUT_S)
            except OSError as exc:
                logger.info("bt_mic_select_falhou", err=str(exc))
                return
            if not prontos:
                self._talvez_rearmar()
                continue
            try:
                raw = os.read(fd, _READ_LEN)
            except BlockingIOError:
                continue
            except OSError as exc:
                # ENODEV = o controle sumiu (BT caiu, desligou). Encerra a
                # thread; quem orquestra redescobre o nó e sobe outra ponte.
                logger.info("bt_mic_hidraw_perdido", no=self.no.caminho, err=str(exc))
                return
            if not raw:
                return
            self._processar(raw)

    def _processar(self, raw: bytes) -> None:
        if raw[0] != INPUT_REPORT_BT:
            return
        if raw[1] & INPUT_FLAG_AUDIO:
            quadro = frame_opus_do_report(raw)
            if quadro is None:
                self._bump(quadros_invalidos=1)
                return
            self._ultimo_audio = time.monotonic()
            dec = self._dec
            if dec is None:  # `parar()` correu com esta iteração
                return
            pcm = dec.decodificar(quadro)
            if pcm is None:
                self._bump(quadros_invalidos=1)
                return
            self._bump(quadros_audio=1)
            if self._source is not None:
                self._source.escrever(pcm)
            return
        status = status_de_audio(raw)
        if status is None:
            return
        mudo = bool(status & STATUS_MIC_MUDO)
        self._bump(
            quadros_input=1,
            input_mudos=1 if mudo else 0,
            mudo=mudo,
            fone_plugado=bool(status & STATUS_FONE_PLUGADO),
        )

    def _talvez_rearmar(self) -> None:
        """Reenvia o 0x32 quando o áudio morre com a ponte ainda ligada.

        Autocura de borda, não keepalive periódico: em regime NÃO escrevemos
        nada no controle (ver "disputa do contador de sequência" no cabeçalho).
        """
        agora = time.monotonic()
        if agora - self._ultimo_audio < _REARME_S:
            return
        if agora - self._ultimo_rearme < _REARME_MIN_INTERVALO_S:
            return
        self._ultimo_rearme = agora
        self._ultimo_audio = agora  # não re-armar de novo antes de dar chance
        self._escrever_pedido(ligar=True)
        self._bump(rearmes=1)

    # -- utilitários ------------------------------------------------------

    def _escrever_pedido(self, *, ligar: bool) -> bool:
        fd = self._fd
        if fd is None:
            return False
        self._seq = (self._seq + 1) & 0x0F
        try:
            os.write(fd, montar_pedido_de_mic(ligar, seq=self._seq))
        except OSError as exc:
            logger.info(
                "bt_mic_write_falhou", no=self.no.caminho, ligar=ligar, err=str(exc)
            )
            return False
        logger.info("bt_mic_pedido", no=self.no.caminho, ligar=ligar, seq=self._seq)
        return True

    def _bump(self, **campos: Any) -> None:
        with self._lock:
            self._stats = _com(self._stats, **campos)

    def _fechar_fd(self) -> None:
        if self._fd is not None:
            with contextlib.suppress(OSError):
                os.close(self._fd)
            self._fd = None

    def _encerrar_decodificador(self) -> None:
        dec = self._dec
        self._dec = None
        if dec is not None and hasattr(dec, "close"):
            with contextlib.suppress(Exception):
                dec.close()


def _com(stats: EstatisticaMic, **campos: Any) -> EstatisticaMic:
    """Novo snapshot: contadores SOMAM, flags SUBSTITUEM."""
    somaveis = (
        "quadros_audio",
        "quadros_input",
        "quadros_invalidos",
        "quadros_descartados",
        "input_mudos",
        "rearmes",
    )
    dados: dict[str, Any] = {
        "quadros_audio": stats.quadros_audio,
        "quadros_input": stats.quadros_input,
        "quadros_invalidos": stats.quadros_invalidos,
        "quadros_descartados": stats.quadros_descartados,
        "input_mudos": stats.input_mudos,
        "rearmes": stats.rearmes,
        "mudo": stats.mudo,
        "fone_plugado": stats.fone_plugado,
        "source": stats.source,
    }
    for chave, valor in campos.items():
        if chave in somaveis:
            dados[chave] = dados[chave] + valor
        else:
            dados[chave] = valor
    return EstatisticaMic(**dados)


# ---------------------------------------------------------------------------
# Abertura do hidraw: broker primeiro (é ele quem tem root)
# ---------------------------------------------------------------------------


def abrir_hidraw_rw(caminho: str) -> int:
    """Abre o hidraw em O_RDWR — via broker se ele estiver de pé.

    Precisa ser RDWR: a ponte LÊ o 0x31 e ESCREVE o 0x32. E precisa passar pelo
    broker porque, com a emulação ligada, o nó do físico está ESCONDIDO (modo
    0600 root, é o que `hide` faz) — sem o fd cedido por SCM_RIGHTS o
    `os.open` daria EACCES e o mic por BT só funcionaria com o hefesto
    desligado, que é o contrário do que se quer.

    O `make_broker_opener` do cliente não serve aqui: o fallback dele é
    O_RDONLY (basta para o espelho de motion, não basta para nós).
    """
    fd: int | None = None
    with contextlib.suppress(Exception):
        from hefesto_dualsense4unix.integrations.hidraw_broker_client import (
            broker_client_for,
        )

        fd = broker_client_for(_TITULAR_DA_LEASE).open_fd(caminho)
    if fd is not None:
        return fd
    return os.open(caminho, os.O_RDWR)


class _TitularDaLease:
    """Dono do cliente-lease do broker deste módulo.

    O `broker_client_for` guarda o singleton num atributo do objeto que recebe
    (o daemon, normalmente). Fora do daemon — CLI, GUI — precisamos de um
    titular estável: um objeto por processo, para não abrir uma lease nova a
    cada `abrir_hidraw_rw` (cada lease é uma conexão viva no broker).
    """


_TITULAR_DA_LEASE = _TitularDaLease()


# ---------------------------------------------------------------------------
# Orquestração: todos os DualSense em BT de uma vez
# ---------------------------------------------------------------------------


class GerenciadorMicBluetooth:
    """Sobe/derruba uma `PonteMicBluetooth` por DualSense conectado em BT.

    É o objeto que o CLI e o subsystem do daemon usam. `reconciliar()` é
    idempotente e barato (uma varredura do sysfs), então dá para chamá-lo de
    tempos em tempos para pegar hotplug — mas ele NÃO tem thread própria: quem
    o usa decide a cadência, e o `dormir()` bloqueia num Event, nunca num
    sleep de laço apertado.
    """

    def __init__(self, *, fabrica: Callable[[NoDualSenseBT], Any] | None = None) -> None:
        self._fabrica = fabrica or PonteMicBluetooth
        self._pontes: dict[str, Any] = {}
        self._acordar = threading.Event()

    @property
    def pontes(self) -> dict[str, Any]:
        return dict(self._pontes)

    def reconciliar(self, nos: list[NoDualSenseBT] | None = None) -> None:
        """Casa as pontes vivas com os controles BT presentes agora."""
        atuais = nos if nos is not None else nos_dualsense_bluetooth()
        presentes = {no.caminho: no for no in atuais}
        for caminho in [c for c in self._pontes if c not in presentes]:
            ponte = self._pontes.pop(caminho)
            with contextlib.suppress(Exception):
                ponte.parar()
        for caminho, no in presentes.items():
            if caminho in self._pontes:
                continue
            # A CONSTRUÇÃO entra no try junto com o `iniciar()`: uma fábrica que
            # levanta (libopus sumiu no meio da sessão, injeção de teste) não
            # pode derrubar a reconciliação dos OUTROS controles.
            try:
                ponte = self._fabrica(no)
                ok = ponte.iniciar()
            except Exception as exc:
                logger.warning("bt_mic_ponte_falhou", no=caminho, err=str(exc))
                continue
            if ok:
                self._pontes[caminho] = ponte

    def dormir(self, segundos: float) -> bool:
        """Espera bloqueando (nunca em laço apertado). True se pediram parada."""
        return self._acordar.wait(segundos)

    def parar(self) -> None:
        """Derruba todas as pontes. Idempotente."""
        self._acordar.set()
        for caminho in list(self._pontes):
            ponte = self._pontes.pop(caminho)
            with contextlib.suppress(Exception):
                ponte.parar()

    def __enter__(self) -> GerenciadorMicBluetooth:
        return self

    def __exit__(self, *_exc: object) -> None:
        self.parar()


# ---------------------------------------------------------------------------
# Diagnóstico (o que o `mic bt-status` imprime)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Diagnostico:
    """Por que a ponte sobe — ou por que não sobe. Um fato por linha."""

    controles: list[NoDualSenseBT]
    libopus: str | None
    pactl: bool
    pipe_source: bool
    broker: bool

    @property
    def pronto(self) -> bool:
        return bool(self.controles) and bool(self.libopus) and self.pactl

    @property
    def impedimentos(self) -> list[str]:
        faltas: list[str] = []
        if not self.controles:
            faltas.append(
                "nenhum DualSense em Bluetooth (no cabo o mic já funciona sozinho)"
            )
        if not self.libopus:
            faltas.append("libopus ausente — instale libopus0 (ver install.sh)")
        if not self.pactl:
            faltas.append("pactl ausente — sem PipeWire/PulseAudio não há onde publicar")
        if self.pactl and not self.pipe_source:
            faltas.append(
                "module-pipe-source indisponível no servidor de áudio "
                "(libpipewire-module-pipe-tunnel.so)"
            )
        return faltas


def diagnosticar() -> Diagnostico:
    """Fotografa as pré-condições da ponte sem mexer em nada (só leitura)."""
    tem_pactl = shutil.which("pactl") is not None
    pipe_source = False
    if tem_pactl:
        # `pactl list modules short` só lista o que está CARREGADO; a presença
        # do .so é o que diz se dá para carregar. Checar o arquivo evita
        # carregar um módulo só para descobrir se ele existe.
        pipe_source = any(
            Path(d).joinpath("libpipewire-module-pipe-tunnel.so").exists()
            for d in _DIRS_PIPEWIRE
        )
    broker = False
    with contextlib.suppress(Exception):
        from hefesto_dualsense4unix.integrations.hidraw_broker_client import (
            broker_client_for,
        )

        broker = bool(broker_client_for(_TITULAR_DA_LEASE).is_available())
    return Diagnostico(
        controles=nos_dualsense_bluetooth(),
        libopus=versao_libopus(),
        pactl=tem_pactl,
        pipe_source=pipe_source,
        broker=broker,
    )


_DIRS_PIPEWIRE = (
    "/usr/lib/x86_64-linux-gnu/pipewire-0.3",
    "/usr/lib64/pipewire-0.3",
    "/usr/lib/pipewire-0.3",
)


__all__ = [
    "AUDIO_CONTROL_MIC_OFF",
    "AUDIO_CONTROL_MIC_ON",
    "AUDIO_OUTPUT_REPORT_ID",
    "AUDIO_OUTPUT_REPORT_LEN",
    "BLOCO_AUDIO_CONTROL",
    "BLOCO_DUPLO",
    "BLOCO_PRESENTE",
    "INPUT_FLAG_AUDIO",
    "INPUT_FLAG_HID",
    "INPUT_REPORT_BT",
    "INPUT_REPORT_BT_SIZE",
    "MIC_AMOSTRAS_POR_QUADRO",
    "MIC_BYTES_POR_QUADRO",
    "MIC_CANAIS",
    "MIC_OPUS_LEN",
    "MIC_OPUS_OFFSET",
    "MIC_TAXA_HZ",
    "STATUS_FONE_PLUGADO",
    "STATUS_MIC_MUDO",
    "DecodadorOpus",
    "Diagnostico",
    "EstatisticaMic",
    "GerenciadorMicBluetooth",
    "NoDualSenseBT",
    "OpusIndisponivelError",
    "PonteMicBluetooth",
    "SourceVirtualPipeWire",
    "abrir_hidraw_rw",
    "diagnosticar",
    "eh_report_de_audio",
    "frame_opus_do_report",
    "montar_pedido_de_mic",
    "nos_dualsense_bluetooth",
    "status_de_audio",
    "versao_libopus",
]
