"""O motor do alto-falante virtual — o encoder, o sink, os arranjos e a ponte.

SOM-QUE-SAI-01, rota corrigida em 06/09/2026. Espelho de saída do
:mod:`integrations.dualsense_bt_audio`, que é a metade de ENTRADA e **não é
tocada por este módulo** — ele importa dela, nunca a edita.

O SOM SAI PELO RÁDIO DESDE 10/09/2026, E A LIÇÃO FICA
------------------------------------------------------
Pelo ``0x35`` de 334 B, com UM quadro Opus por report (:data:`ARRANJO_035`,
que é o :data:`ARRANJO_PADRAO`): 70 s contínuos pelo alto-falante, com a
orelha dela, e o som CALA com o CRC invertido. Quem escreve no controle é a
:class:`PonteDeSomPorRadio`, uma por controle no rádio, e quem a sobe é o
subsystem (``daemon/subsystems/alto_falante._casar_as_pontes``).

A lição que o mapa guarda tem nome (``audio.saida_dedicada@dualsense``):
a FALÁCIA DO CANAL QUE RESPONDE — concluir que, porque um canal responde, ele
FAZ o que se esperava dele. Ela segurou o som em ``não`` até a orelha dela
ouvir o CONTEÚDO, em 10/09, e segura o degrau do produto em ``MONTOU`` até a
bancada ouvir o caminho inteiro: o nó, a ponte e o controle. Quem conta o som
pelo rádio conta pelo degrau e pela data, que estão no :data:`ARRANJO_035`.

O QUE FALTAVA, E ERA NOMEADO PELO PRÓPRIO MAPA
-----------------------------------------------
``audio.alto_falante@dualsense``.radio_codigo_ref listava três dívidas com
endereço, e as três estão pagas neste arquivo:

1. **o ENCODER** — ``dualsense_bt_audio.py`` prototipa só o decodificador;
   ``opus_encoder_create`` e ``opus_encode`` não apareciam em linha nenhuma
   de ``src/``. Ver :class:`CodificadorOpus`;
2. **o SINK** — a ponte de entrada publica uma SOURCE de captura
   (``module-pipe-source``) e não existia caminho de SAÍDA nenhum. Ver
   :class:`SinkVirtualPipeWire`;
3. **o ARRANJO** — as duas fontes publicadas descrevem o ``0x39`` e DIVERGEM
   (:data:`ARRANJOS`); o que tocou foi um terceiro, :data:`ARRANJO_035`. O
   parágrafo abaixo diz os três.

OS DOIS ARRANJOS DE FORA, E O QUE TOCOU
---------------------------------------
As duas fontes descrevem o MESMO report — id ``0x39``, 547 bytes, CRC nos
quatro últimos — e discordam sobre onde, dentro dele, mora o áudio:

===================  ==========================  ==========================
                     (A) DS5Dongle               (B) Senshi
===================  ==========================  ==========================
AudioControl         tag em [2], ``len`` 6       tag em [2], ``len`` 7
háptico              [10..139] (dois de 64 B)    [413..542], no FIM
áudio                [140..541] (dois de 200 B)  [11..412] (400 B)
CRC-32               [543..546]                  [543..546]
===================  ==========================  ==========================

**O Senshi não é testemunha independente:** ele cita o DS5Dongle
(``DualSenseBtReportBuilder.kt:76``) — leu a mesma fonte e chegou a outro
arranjo. **E NENHUM DOS DOIS TOCOU:** o ensaio de 10/09, com a orelha dela,
achou o ``0x35`` de 334 B com um quadro só. Os dois ficam montáveis pelo mesmo
PCM, para ensaio (`scripts/ensaios/o_som_que_sai.py` os monta lado a lado); o
produto não os usa.

AS TRÊS RESSALVAS QUE VIAJAM COM O ACHADO
------------------------------------------
Do mapa, ``audio.alto_falante@dualsense``.radio_ressalva, e nenhuma é enfeite:

(a) **o alto-falante interno é MONO**, medido em 16/08/2026 no ensaio
    ``sfx-tres-saidas-quatro-canais``: canal 0 → fone L, canal 1 → fone R ou
    alto-falante interno sem fone, canais 2 e 3 → nada. O encoder do
    DS5Dongle é ESTÉREO (``opus_encoder_create(48000, 2, …)``), e o estéreo
    casa com a rota de FONE (tag ``0x16``), não com o alto-falante interno
    (tag ``0x13``). Por isso :data:`CANAIS_DO_ENCODER` é 2 **e a tag é
    argumento**: os 200 bytes por quadro são o que o formato exige, e a ponte
    manda a tag do alto-falante (``BLOCO_SPEAKER``, a do report que tocou);
(b) **o byte [2] tem três leituras** — o DS5Dongle o lê como tag TLV
    ``0x11|0x80`` (= 0x91), e ``plataforma.escada_de_output@dualsense`` mediu
    o ``common`` de 47 B obedecendo em [3..49] com ``report[2] = 0x10``, SEM
    o bit 7. No ``0x35`` a disputa ficou respondida em 10/09: o ``[2]`` é a
    tag ``0x91``. Fora dele ela continua aberta, e o ``common`` fica fora;
(c) **o DS5Dongle é um DONGLE** — fala L2CAP direto e nunca toca
    ``/dev/hidraw``. Ele prova "report HID de saída", não "hidraw".

O QUE ESTE MÓDULO **NÃO** FAZ, E TEM DONO
------------------------------------------
* **não decide quando escrever.** O caminho dele até o aparelho é UM, a
  :class:`PonteDeSomPorRadio`, e quem a sobe é o subsystem; o resto monta;
* **não mexe em rota, volume nem pré-amplificador** — isso é de
  ``core/backend_pydualsense.py`` e de ``app/audio_saida.py``, e o segundo
  está em ``nao_toca:`` desta sprint. O nó virtual é **por onde o áudio
  entra**; o que o firmware faz com ele depois tem dono, e não é este;
* **não escolhe o degrau para regime.** A decisão dela
  (``D-0609-O-NO-DE-SOM-VIVE-COM-O-CONTROLE``) deixava ``0x32`` contra
  ``0x39`` para *depois do D5*, e a orelha dela achou o terceiro em 10/09: o
  ``0x35`` é o :data:`ARRANJO_PADRAO`. A escolha do degrau pelo tamanho do
  payload desceu para o ensaio que a usava (``scripts/ensaios/o_som_que_sai.py``,
  O-ALTO-FALANTE-TEM-UM-CAMINHO-SO-01, 28/09/2026): o produto escreve um degrau
  só, e o do arranjo.
"""

from __future__ import annotations

import contextlib
import ctypes
import errno as _errno
import json
import os
import shutil
import subprocess
import threading
import time
from collections.abc import Callable, Iterable, Iterator, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from hefesto_dualsense4unix.core import ds_output_report as rep
from hefesto_dualsense4unix.core.ds_output_report import (
    BT_CRC_SEED,
    BT_TAG,
    COMMON_LEN,
    bt_crc32,
)
from hefesto_dualsense4unix.integrations.dualsense_bt_audio import (
    BLOCO_AUDIO_CONTROL,
    BLOCO_DUPLO,
    BLOCO_HAPTICS,
    BLOCO_PRESENTE,
    BLOCO_SET_STATE,
    BLOCO_SPEAKER,
    MIC_TAXA_HZ,
    OpusIndisponivelError,
)
from hefesto_dualsense4unix.integrations.fontes_de_captura import so_hex
from hefesto_dualsense4unix.integrations.storm_doctor import gesto_de_instalar
from hefesto_dualsense4unix.utils.logging_config import get_logger

logger = get_logger(__name__)


TAMANHO_DO_DEGRAU: dict[int, int] = {
    0x31: 78,
    0x32: 142,
    0x33: 206,
    0x34: 270,
    0x35: 334,
    0x36: 398,
    0x37: 462,
    0x38: 526,
    0x39: 547,
}

DEGRAU_DO_KERNEL = 0x31

ENVELOPE_BYTES = 3

CRC_BYTES = 4

OFFSET_DO_COMMON = 3

OFFSET_APOS_O_COMMON = OFFSET_DO_COMMON + COMMON_LEN


def orcamento_do_degrau(degrau: int) -> int:
    """Quantos bytes de payload cabem NESTE degrau depois do ``common``."""
    return TAMANHO_DO_DEGRAU[degrau] - ENVELOPE_BYTES - COMMON_LEN - CRC_BYTES


ORCAMENTO_DO_DEGRAU: dict[int, int] = {
    degrau: orcamento_do_degrau(degrau) for degrau in TAMANHO_DO_DEGRAU
}


_SONAMES_OPUS = ("libopus.so.0", "libopus.so")

OPUS_APPLICATION_AUDIO = 2049
OPUS_SET_BITRATE_REQUEST = 4002
OPUS_SET_VBR_REQUEST = 4006
OPUS_OK = 0

TAXA_DO_ENCODER = MIC_TAXA_HZ

CANAIS_DO_ENCODER = 2

AMOSTRAS_POR_QUADRO = 480

BYTES_DE_PCM_POR_QUADRO = AMOSTRAS_POR_QUADRO * CANAIS_DO_ENCODER * 2

BITRATE_DO_ENCODER = 160000

BYTES_POR_QUADRO_OPUS = 200

_LIB_OPUS_ENC: ctypes.CDLL | None = None
_LOCK_OPUS_ENC = threading.Lock()


def _carregar_libopus_encoder() -> ctypes.CDLL:
    """Carrega e prototipa os símbolos de ENCODER da libopus, uma vez."""
    global _LIB_OPUS_ENC
    if _LIB_OPUS_ENC is not None:
        return _LIB_OPUS_ENC
    with _LOCK_OPUS_ENC:
        if _LIB_OPUS_ENC is not None:
            return _LIB_OPUS_ENC
        lib: ctypes.CDLL | None = None
        for soname in _SONAMES_OPUS:
            try:
                lib = ctypes.CDLL(soname)
                break
            except OSError:
                continue
        if lib is None:
            raise OpusIndisponivelError(
                f"libopus não encontrada ({gesto_de_instalar('opus')})"
            )
        lib.opus_encoder_create.restype = ctypes.c_void_p
        lib.opus_encoder_create.argtypes = [
            ctypes.c_int32,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.POINTER(ctypes.c_int),
        ]
        lib.opus_encoder_destroy.restype = None
        lib.opus_encoder_destroy.argtypes = [ctypes.c_void_p]
        lib.opus_encode.restype = ctypes.c_int32
        lib.opus_encode.argtypes = [
            ctypes.c_void_p,
            ctypes.POINTER(ctypes.c_int16),
            ctypes.c_int,
            ctypes.c_char_p,
            ctypes.c_int32,
        ]
        lib.opus_encoder_ctl.restype = ctypes.c_int
        _LIB_OPUS_ENC = lib
        return lib


class CodificadorOpus:
    """PCM ``s16le`` de 10 ms → um quadro Opus de tamanho FIXO."""

    def __init__(
        self,
        *,
        taxa_hz: int = TAXA_DO_ENCODER,
        canais: int = CANAIS_DO_ENCODER,
        bitrate_bps: int = BITRATE_DO_ENCODER,
        amostras_por_quadro: int = AMOSTRAS_POR_QUADRO,
    ) -> None:
        self._lib = _carregar_libopus_encoder()
        erro = ctypes.c_int(0)
        ponteiro = self._lib.opus_encoder_create(
            taxa_hz, canais, OPUS_APPLICATION_AUDIO, ctypes.byref(erro)
        )
        if not ponteiro or erro.value != OPUS_OK:
            raise OpusIndisponivelError(f"opus_encoder_create falhou: {erro.value}")
        self._enc: int | None = ponteiro
        self.canais = canais
        self.taxa_hz = taxa_hz
        self.amostras_por_quadro = amostras_por_quadro
        self.bitrate_bps = bitrate_bps
        self._ctl(OPUS_SET_VBR_REQUEST, 0)
        self._ctl(OPUS_SET_BITRATE_REQUEST, bitrate_bps)
        self._saida = ctypes.create_string_buffer(4000)

    def _ctl(self, request: int, valor: int) -> int:
        """`opus_encoder_ctl` com o ponteiro ENVELOPADO — dono único da chamada."""
        return int(
            self._lib.opus_encoder_ctl(
                ctypes.c_void_p(self._enc), int(request), ctypes.c_int32(int(valor))
            )
        )

    @property
    def bytes_de_pcm_por_quadro(self) -> int:
        """Quantos bytes de PCM ``s16le`` um quadro consome."""
        return self.amostras_por_quadro * self.canais * 2

    def codificar(self, pcm: bytes) -> bytes | None:
        """Um quadro de PCM → um quadro Opus. None quando a libopus recusa."""
        if self._enc is None:
            return None
        if len(pcm) != self.bytes_de_pcm_por_quadro:
            return None
        buffer_pcm = (ctypes.c_int16 * (self.amostras_por_quadro * self.canais))()
        ctypes.memmove(buffer_pcm, pcm, len(pcm))
        n = self._lib.opus_encode(
            self._enc,
            buffer_pcm,
            self.amostras_por_quadro,
            self._saida,
            len(self._saida),
        )
        if n <= 0:
            return None
        return bytes(self._saida.raw[:n])

    def close(self) -> None:
        """Libera o codificador. Idempotente."""
        if self._enc is not None:
            with contextlib.suppress(Exception):
                self._lib.opus_encoder_destroy(self._enc)
            self._enc = None

    def __enter__(self) -> CodificadorOpus:
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()


BLOCO_FONE = 0x16


def tag_tlv(tag: int, *, duplo: bool = False) -> int:
    """O byte de tag da cadeia TLV: ``tag | presente [| duplo]``."""
    valor = tag | BLOCO_PRESENTE
    if duplo:
        valor |= BLOCO_DUPLO
    return valor


@dataclass(frozen=True)
class Arranjo:
    """Um dos dois candidatos ao corpo do ``0x39``, com a procedência colada."""

    nome: str
    fonte: str
    degrau: int
    pos_tag_controle: int
    len_controle: int
    pos_tag_audio: int
    len_audio: int
    pos_audio: int
    quadros_de_audio: int
    pos_tag_haptico: int
    len_haptico: int
    pos_haptico: int
    de_onde_sei: str = "leitura de fonte externa — NÃO medido nesta bancada"
    intervalo_de_envio_s: float | None = None
    controle_conta_quadros: bool = False
    haptico_duplo: bool = True
    common_preservado: bool = False

    @property
    def bytes_de_audio(self) -> int:
        """Quantos bytes de Opus o arranjo carrega no total."""
        return self.len_audio * self.quadros_de_audio

    @property
    def tamanho(self) -> int:
        return TAMANHO_DO_DEGRAU[self.degrau]

    def montar(
        self,
        quadros: Sequence[bytes],
        *,
        seq: int = 0,
        tag_audio: int = BLOCO_SPEAKER,
        controle: bytes = b"",
        haptico: bytes = b"",
        common: bytes | None = None,
    ) -> bytes:
        """O report inteiro, com o CRC-32 já no lugar. Levanta em vez de mentir."""
        if len(quadros) != self.quadros_de_audio:
            raise ValueError(
                f"{self.nome} quer {self.quadros_de_audio} quadros, veio {len(quadros)}"
            )
        if self.common_preservado:
            return montar_com_o_common_preservado(
                quadros,
                bytes(COMMON_LEN) if common is None else common,
                degrau=self.degrau,
                seq=seq,
                tag_audio=tag_audio,
                len_audio=self.len_audio,
            )
        for quadro in quadros:
            if len(quadro) > self.len_audio:
                raise ValueError(
                    f"quadro de {len(quadro)} B não cabe em {self.len_audio} B"
                )
        pkt = bytearray(self.tamanho)
        pkt[0] = self.degrau
        pkt[1] = (int(seq) & 0x0F) << 4
        pkt[self.pos_tag_controle] = tag_tlv(BLOCO_AUDIO_CONTROL)
        pkt[self.pos_tag_controle + 1] = self.len_controle
        valor = controle[: self.len_controle]
        pkt[self.pos_tag_controle + 2 : self.pos_tag_controle + 2 + len(valor)] = valor
        if self.len_haptico:
            pkt[self.pos_tag_haptico] = tag_tlv(BLOCO_HAPTICS, duplo=self.haptico_duplo)
            pkt[self.pos_tag_haptico + 1] = self.len_haptico
            quantos = 2 if self.haptico_duplo else 1
            corpo = haptico[: self.len_haptico * quantos]
            pkt[self.pos_haptico : self.pos_haptico + len(corpo)] = corpo
        if not self.quadros_de_audio:
            crc_so_haptico = bt_crc32(pkt[: self.tamanho - CRC_BYTES], seed=BT_CRC_SEED)
            pkt[self.tamanho - CRC_BYTES :] = crc_so_haptico.to_bytes(4, "little")
            return bytes(pkt)
        pkt[self.pos_tag_audio] = tag_tlv(tag_audio, duplo=self.quadros_de_audio > 1)
        pkt[self.pos_tag_audio + 1] = self.len_audio
        for i, quadro in enumerate(quadros):
            comeco = self.pos_audio + i * self.len_audio
            pkt[comeco : comeco + len(quadro)] = quadro
        crc = bt_crc32(pkt[: self.tamanho - CRC_BYTES], seed=BT_CRC_SEED)
        pkt[self.tamanho - CRC_BYTES :] = crc.to_bytes(4, "little")
        return bytes(pkt)


#: ``src/audio.cpp:30-33`` e ``:118-173``. O áudio vem DEPOIS do háptico.
ARRANJO_DS5DONGLE = Arranjo(
    nome="ds5dongle",
    fonte=(
        "awalol/DS5Dongle@17385f8beeef17129f0b39d9e5fc2195ea89b322 "
        "src/audio.cpp:30-33, :118-173 (CRC em src/utils.h:126-137)"
    ),
    degrau=0x39,
    pos_tag_controle=2,
    len_controle=6,
    pos_tag_haptico=10,
    len_haptico=64,
    pos_haptico=12,
    pos_tag_audio=140,
    len_audio=200,
    pos_audio=142,
    quadros_de_audio=2,
)

#: ``…/settings/DualSenseBtReportBuilder.kt:959-1014``. O MESMO id, o MESMO
ARRANJO_SENSHI = Arranjo(
    nome="senshi",
    fonte=(
        "TechAntohere/Senshi@1de83a58f5ea29d12d06c2a38d4d7641090d49ff "
        ".../settings/DualSenseBtReportBuilder.kt:63-70, :76, :959-1014"
    ),
    degrau=0x39,
    pos_tag_controle=2,
    len_controle=7,
    pos_tag_audio=11,
    len_audio=200,
    pos_audio=13,
    quadros_de_audio=2,
    pos_tag_haptico=413,
    len_haptico=64,
    pos_haptico=415,
)

ARRANJOS: tuple[Arranjo, ...] = (ARRANJO_DS5DONGLE, ARRANJO_SENSHI)

ARRANJO_COMMON_PRIMEIRO = Arranjo(
    nome="common-preservado",
    fonte=(
        "esta bancada — plataforma.escada_de_output@dualsense, 15/08/2026: o "
        "`common` de 47 B por 0x32 e 0x39 acendeu a cor na lightbar por rádio, "
        "com o olho dela. NÃO é leitura de fonte externa."
    ),
    degrau=0x39,
    pos_tag_controle=2,
    len_controle=0,
    pos_tag_audio=OFFSET_APOS_O_COMMON,
    len_audio=BYTES_POR_QUADRO_OPUS,
    pos_audio=OFFSET_APOS_O_COMMON + 2,
    quadros_de_audio=2,
    pos_tag_haptico=0,
    len_haptico=0,
    pos_haptico=0,
    de_onde_sei=(
        "MEDIDO nesta bancada quanto ao envelope ([2]=0x10 e o common em "
        "[3..49]); a POSIÇÃO DO OPUS depois dele é hipótese não medida"
    ),
    common_preservado=True,
)


BYTES_DO_CONTROLE_035 = 7

BYTES_DO_BLOCO_HAPTICO = 64

QUADROS_POR_BLOCO_HAPTICO = 512
CANAIS_DA_HAPTICA = 4

ENABLES_SEM_MIC = 0xFE
ENABLES_COM_MIC = 0xFF

BUFFER_QUE_TOCOU = bytes((0x00, 0x00, 0x00, 0x00, 0xFF))

INTERVALO_DE_ENVIO_035 = 512 / 48_000

TAXA_DA_FONTE_DO_SOM = round(AMOSTRAS_POR_QUADRO / INTERVALO_DE_ENVIO_035)

TAXA_DA_FONTE_POR_PAPEL: dict[str, int] = {
    "som": TAXA_DA_FONTE_DO_SOM,
    "haptica": TAXA_DO_ENCODER,
}


def taxa_da_fonte(papel: str) -> int:
    """A taxa em que a fonte deste ``papel`` tem de entregar. 48 kHz se o papel é outro."""
    return TAXA_DA_FONTE_POR_PAPEL.get(papel, TAXA_DO_ENCODER)


def controle_de_audio_035(
    *,
    contador_de_quadros: int,
    com_microfone: bool = False,
    buffer: bytes = BUFFER_QUE_TOCOU,
) -> bytes:
    """Os sete bytes do bloco `0x11` do `0x35`, prontos para `Arranjo.montar`."""
    if len(buffer) != 5:
        raise ValueError(f"o audio_buffer_length tem 5 bytes, veio {len(buffer)}")
    return bytes(
        (ENABLES_COM_MIC if com_microfone else ENABLES_SEM_MIC, *buffer,
         int(contador_de_quadros) & 0xFF)
    )


#: segundos contínuos pelo alto-falante do DualSense, por rádio, sem um corte, e
ARRANJO_035 = Arranjo(
    nome="0x35",
    fonte=(
        "ESTA BANCADA, 10/09/2026 — o alto-falante tocou por rádio, 70 s "
        "contínuos, com a orelha dela e a mordida do CRC. O layout é o do "
        "`HeadsetPlayMusic` de awalol/dualsense-bt-haptics, e o achado [8.19] "
        "da pesquisa de 31/08 já trazia o tamanho: «0x35 com 334 (CRC em "
        "330..333)»."
    ),
    degrau=0x35,
    pos_tag_controle=2,
    len_controle=BYTES_DO_CONTROLE_035,
    pos_tag_audio=11,
    len_audio=BYTES_POR_QUADRO_OPUS,
    pos_audio=13,
    quadros_de_audio=1,
    pos_tag_haptico=0,
    len_haptico=0,
    pos_haptico=0,
    de_onde_sei=(
        "MEDIDO NESTA BANCADA, 10/09/2026, com som audível: 70 s contínuos "
        "pelo alto-falante, alcance testado, e o som CALA com o CRC invertido"
    ),
    intervalo_de_envio_s=INTERVALO_DE_ENVIO_035,
    controle_conta_quadros=True,
)

#: o medido.
#: como corrigimos isso"*.  <!-- noqa-acento: citação literal dela -->
ARRANJO_HAPTICA_032 = Arranjo(
    nome="0x32-háptica",
    fonte=(
        "ESTA BANCADA, 18/09/2026 — o motor voice-coil vibrou por rádio, com a "
        "mão dela, primeiro com senoide e depois com o PCM do PRAGMATA."
    ),
    degrau=0x32,
    pos_tag_controle=2,
    len_controle=BYTES_DO_CONTROLE_035,
    pos_tag_audio=0,
    len_audio=0,
    pos_audio=0,
    quadros_de_audio=0,
    pos_tag_haptico=11,
    len_haptico=BYTES_DO_BLOCO_HAPTICO,
    pos_haptico=13,
    haptico_duplo=False,
    intervalo_de_envio_s=INTERVALO_DE_ENVIO_035,
    controle_conta_quadros=True,
)


#: O RELATÓRIO COMBINADO — O-SOM-E-A-HAPTICA-NUM-RELATORIO-SO-01 (03/10/2026).
#: O ``0x36`` de 398 B com os quatro blocos num quadro só: ``0x11`` (o controle
#: de áudio, com O contador) em [2], ``0x10`` (o estado, 63 B, o ``common`` de
#: 47 B nos primeiros) em [11], ``0x12`` (a háptica, 64 B) em [76] e
#: ``0x13``/``0x16`` (o som, um quadro Opus de 200 B) em [142], CRC nos quatro
#: últimos. Layout do fork loteran do DS5Dongle (``src/audio.cpp``, a função
#: que monta o ``REPORT_ID 0x36``), lido no código; NÃO medido nesta bancada: o
#: ensaio ``scripts/ensaios/o_som_e_a_haptica_num_relatorio.py`` é quem prova.
#: A ponte de hoje segue com os dois escritores (``0x35`` e ``0x32``) até a
#: prova; este montador é a parte pura da troca.
DEGRAU_COMBINADO = 0x36
POS_TAG_CONTROLE_COMBINADO = 2
POS_TAG_ESTADO_COMBINADO = 11
LEN_ESTADO_COMBINADO = 63
POS_TAG_HAPTICO_COMBINADO = 76
POS_TAG_SOM_COMBINADO = 142


def montar_relatorio_combinado(
    *,
    seq: int,
    controle: bytes,
    common: bytes | None = None,
    haptico: bytes | None = None,
    quadro_de_som: bytes | None = None,
    tag_som: int = BLOCO_SPEAKER,
) -> bytes:
    """O ``0x36`` combinado, com o CRC no lugar. Função pura; levanta em vez de mentir.

    ``controle`` são os 7 bytes do ``0x11`` (:func:`controle_de_audio_035`,
    com o contador do quadro). Os blocos vão em CADEIA, cada um logo depois do
    anterior, na ordem ``0x11``, ``0x10``, ``0x12``, ``0x13``; com os quatro,
    as posições são as do layout (:data:`POS_TAG_ESTADO_COMBINADO` e as
    irmãs). O bloco que não veio (``None``) não entra, e os seguintes sobem:
    a cadeia não tem buraco, como no ``0x32`` e no ``0x35`` que tocaram
    (``0x11`` em [2] e o bloco seguinte em [11]). ``common`` tem os 47 B
    medidos e vai no começo dos 63 do ``0x10``; ``haptico`` tem 64 B;
    ``quadro_de_som``, até 200 B.
    """
    tamanho = TAMANHO_DO_DEGRAU[DEGRAU_COMBINADO]
    if len(controle) != BYTES_DO_CONTROLE_035:
        raise ValueError(
            f"o 0x11 tem {BYTES_DO_CONTROLE_035} B, veio com {len(controle)}"
        )
    if common is not None and len(common) != COMMON_LEN:
        raise ValueError(f"o `common` tem {COMMON_LEN} B, veio com {len(common)}")
    if haptico is not None and len(haptico) != BYTES_DO_BLOCO_HAPTICO:
        raise ValueError(
            f"o bloco háptico tem {BYTES_DO_BLOCO_HAPTICO} B, veio com {len(haptico)}"
        )
    if quadro_de_som is not None and len(quadro_de_som) > BYTES_POR_QUADRO_OPUS:
        raise ValueError(
            f"quadro de {len(quadro_de_som)} B não cabe em {BYTES_POR_QUADRO_OPUS} B"
        )
    pkt = bytearray(tamanho)
    pkt[0] = DEGRAU_COMBINADO
    pkt[1] = (int(seq) & 0x0F) << 4

    blocos: list[tuple[int, int, bytes]] = [
        (BLOCO_AUDIO_CONTROL, BYTES_DO_CONTROLE_035, controle)
    ]
    if common is not None:
        blocos.append((BLOCO_SET_STATE, LEN_ESTADO_COMBINADO, common))
    if haptico is not None:
        blocos.append((BLOCO_HAPTICS, BYTES_DO_BLOCO_HAPTICO, haptico))
    if quadro_de_som is not None:
        blocos.append((tag_som, BYTES_POR_QUADRO_OPUS, quadro_de_som))
    pos = POS_TAG_CONTROLE_COMBINADO
    for tag, tamanho_do_bloco, dados in blocos:
        pkt[pos] = tag_tlv(tag)
        pkt[pos + 1] = tamanho_do_bloco
        pkt[pos + 2 : pos + 2 + len(dados)] = dados
        pos += 2 + tamanho_do_bloco
    crc = bt_crc32(pkt[: tamanho - CRC_BYTES], seed=BT_CRC_SEED)
    pkt[tamanho - CRC_BYTES :] = crc.to_bytes(4, "little")
    return bytes(pkt)


@dataclass
class RelatorioCombinado:
    """UM escritor por controle: um contador só no ``0x11``, um relatório por quadro.

    Hoje a casa tem dois escritores por controle, o ``0x35`` do som e o
    ``0x32`` da háptica, cada um com o seu contador no ``0x11``. Este é o
    estado do escritor único: :meth:`relatorio_do_quadro` monta o quadro com o som e a
    háptica que existirem nele (e o ``0x10`` quando houver estado a mandar), e
    anda o contador e a sequência UMA vez por relatório.
    """

    com_microfone: bool = False
    contador: int = 0
    seq: int = 0

    def relatorio_do_quadro(
        self,
        *,
        quadro_de_som: bytes | None = None,
        haptico: bytes | None = None,
        common: bytes | None = None,
        tag_som: int = BLOCO_SPEAKER,
    ) -> bytes:
        """O relatório deste quadro. O contador e a sequência andam um."""
        relatorio = montar_relatorio_combinado(
            seq=self.seq,
            controle=controle_de_audio_035(
                contador_de_quadros=self.contador, com_microfone=self.com_microfone
            ),
            common=common,
            haptico=haptico,
            quadro_de_som=quadro_de_som,
            tag_som=tag_som,
        )
        self.contador = (self.contador + 1) & 0xFF
        self.seq = (self.seq + 1) & 0x0F
        return relatorio


ARRANJO_POR_NOME: dict[str, Arranjo] = {
    a.nome: a for a in (*ARRANJOS, ARRANJO_COMMON_PRIMEIRO, ARRANJO_035)
}

ARRANJO_PADRAO = ARRANJO_035


def montar_com_o_common_preservado(
    quadros: Sequence[bytes],
    common: bytes,
    *,
    degrau: int = 0x39,
    seq: int = 0,
    tag_audio: int = BLOCO_SPEAKER,
    len_audio: int = BYTES_POR_QUADRO_OPUS,
) -> bytes:
    """O corpo do degrau com o ``[2] = 0x10`` e o ``common`` em [3..49] INTACTO."""
    if len(common) != COMMON_LEN:
        raise ValueError(
            f"o `common` tem de ter {COMMON_LEN} B medidos, veio com {len(common)}"
        )
    tamanho = TAMANHO_DO_DEGRAU[degrau]
    cabe = orcamento_do_degrau(degrau)
    preciso = len(quadros) * len_audio + 2
    if preciso > cabe:
        raise ValueError(
            f"{len(quadros)} quadro(s) de {len_audio} B não cabem nos {cabe} B "
            f"livres do degrau 0x{degrau:02x}"
        )
    for quadro in quadros:
        if len(quadro) > len_audio:
            raise ValueError(f"quadro de {len(quadro)} B não cabe em {len_audio} B")
    pkt = bytearray(tamanho)
    pkt[0] = degrau
    pkt[1] = (int(seq) & 0x0F) << 4
    pkt[2] = BT_TAG
    pkt[OFFSET_DO_COMMON : OFFSET_DO_COMMON + COMMON_LEN] = common
    pkt[OFFSET_APOS_O_COMMON] = tag_tlv(tag_audio, duplo=len(quadros) > 1)
    pkt[OFFSET_APOS_O_COMMON + 1] = len_audio
    for i, quadro in enumerate(quadros):
        comeco = OFFSET_APOS_O_COMMON + 2 + i * len_audio
        pkt[comeco : comeco + len(quadro)] = quadro
    crc = bt_crc32(pkt[: tamanho - CRC_BYTES], seed=BT_CRC_SEED)
    pkt[tamanho - CRC_BYTES :] = crc.to_bytes(4, "little")
    return bytes(pkt)


VOLUME_QUE_ELA_OUVIU = 85


def common_de_audio(
    *,
    volume: int = VOLUME_QUE_ELA_OUVIU,
    rota: int = rep.SAIDA_SO_NO_ALTO_FALANTE,
    preamp: int = rep.SP_PREAMP_GAIN_PADRAO,
) -> bytes:
    """O ``common`` de 47 B que PEDE rota, volume e pré-amp. Para o ENSAIO."""
    common = bytearray(COMMON_LEN)
    common[0] = rep.VALID_FLAG0_SPEAKER_VOLUME | rep.VALID_FLAG0_AUDIO_PATH
    common[1] = rep.VALID_FLAG1_AUDIO_CONTROL2_ENABLE
    common[rep.COMMON_SPEAKER_VOLUME] = min(
        max(0, int(volume)), rep.TETO_SPEAKER_VOLUME
    )
    common[rep.COMMON_AUDIO_PATH] = rep.AUDIO_CONTROL_BASE_SEGURA | (
        (int(rota) << rep.OUTPUT_PATH_SEL_SHIFT) & rep.OUTPUT_PATH_SEL_MASK
    )
    common[rep.COMMON_AUDIO_CONTROL2] = int(preamp) & rep.SP_PREAMP_GAIN_MASK
    return bytes(common)


_MODULO_NULL_SINK = "module-null-sink"

PREFIXO_SINK_DO_SOM = "hefesto_som_"

HEX_DO_SUFIXO = 6

#: DualSense no cabo::
#:     alsa_output.usb-…DualSense…analog-surround-40       1109
#:     alsa_output.usb-…DualSense…-00.2.analog-surround-40 1109
PRIORIDADE_SESSAO_DO_SOM = 10

NOME_DO_ALTO_FALANTE_DO_CONTROLE = "Alto-falante do Controle"

_TIMEOUT_PACTL_S = 5.0

_DIRS_PIPEWIRE = (
    "/usr/lib/x86_64-linux-gnu/pipewire-0.3",
    "/usr/lib64/pipewire-0.3",
    "/usr/lib/pipewire-0.3",
)


def nome_do_sink(uniq: str) -> str:
    """``hefesto_som_<hex6>`` a partir do ``uniq`` do controle. "" se ilegível."""
    rabo = so_hex(str(uniq))
    if len(rabo) < HEX_DO_SUFIXO:
        return ""
    return f"{PREFIXO_SINK_DO_SOM}{rabo[-HEX_DO_SUFIXO:]}"


def sufixo_do_sink_do_som(nome: str) -> str:
    """Rabo hex do MAC no nome do nó de som — "" se não for um."""
    baixa = nome.lower()
    if not baixa.startswith(PREFIXO_SINK_DO_SOM):
        return ""
    resto = baixa[len(PREFIXO_SINK_DO_SOM) :]
    if len(resto) < HEX_DO_SUFIXO or so_hex(resto) != resto:
        return ""
    return resto


def propriedades_do_sink(descricao: str, controle: str | None = None) -> str:
    """O argumento ``sink_properties=`` do ``load-module`` — ENTRE ASPAS DUPLAS."""
    from hefesto_dualsense4unix.integrations.dualsense_bt_audio import campo_do_controle
    from hefesto_dualsense4unix.integrations.vestido_de_dualsense import campos_do_nome
    return (
        'sink_properties="'
        + " ".join(
            (
                f"device.description='{descricao}'",
                f"priority.session={PRIORIDADE_SESSAO_DO_SOM}",
                "device.icon_name=audio-speakers",
                *campos_do_nome(),
                *campo_do_controle(controle),
            )
        )
        + '"'
    )


def _rodar(argv: list[str]) -> str | None:
    """Roda um comando curto e devolve o stdout (None em qualquer falha)."""
    from hefesto_dualsense4unix.integrations import retrato_do_som

    resposta = retrato_do_som.responder(argv)
    if resposta is not None:
        return resposta if isinstance(resposta, str) else None
    if shutil.which(argv[0]) is None:
        return None
    try:
        proc = subprocess.run(
            argv,
            timeout=_TIMEOUT_PACTL_S,
            capture_output=True, text=True, check=False,
            env={**os.environ, "LC_ALL": "C"},
        )
    except (OSError, subprocess.SubprocessError) as exc:
        _anotar_o_prazo(argv, exc)
        return None
    finally:
        retrato_do_som.escreveu(argv)
    if proc.returncode != 0:
        return None
    _anotar_a_resposta(argv)
    return proc.stdout


def rodar_pactl(argv: list[str]) -> str | None:
    """Porta pública de :func:`_rodar`, para o ensaio perguntar ao servidor."""
    return _rodar(argv)


class SinkVirtualPipeWire:
    """O nó de saída de UM controle, publicado no PipeWire por ``pactl``."""

    def __init__(
        self,
        *,
        uniq: str,
        descricao: str | None = None,
        taxa_hz: int = TAXA_DO_ENCODER,
        canais: int = CANAIS_DO_ENCODER,
        runner: Callable[[list[str]], str | None] | None = None,
        rota: RotaDoNo | None = None,
    ) -> None:
        self.uniq = str(uniq)
        self.nome = nome_do_sink(uniq)
        self.descricao = descricao or descricao_do_alto_falante(uniq)
        self.taxa_hz = taxa_hz
        self.canais = canais
        self.runner = _com_o_recuo(runner or _rodar)
        self.rota = rota
        self._module_id: str | None = None
        self._rotas: list[str] = []


    @property
    def module_id(self) -> str | None:
        """O id do módulo carregado, ou None se o nó não está de pé."""
        return self._module_id

    def iniciar(self) -> bool:
        """Carrega o ``module-null-sink`` E a rota dele. False = não deu."""
        if self._module_id is not None:
            return True
        if not self.nome:
            logger.info("som_sem_identidade", uniq=self.uniq)
            return False
        if not _o_servidor_atende(self.runner, self.nome):
            return False
        saida = self.runner(
            [
                "pactl",
                "load-module",
                _MODULO_NULL_SINK,
                f"sink_name={self.nome}",
                "format=s16le",
                f"rate={self.taxa_hz}",
                f"channels={self.canais}",
                propriedades_do_sink(self.descricao, self.uniq),
            ]
        )
        linhas = [ln.strip() for ln in (saida or "").splitlines() if ln.strip()]
        if not linhas or not linhas[-1].isdigit():
            logger.warning("som_load_module_falhou", saida=(saida or "")[:200])
            return False
        self._module_id = linhas[-1]
        logger.info("som_sink_publicado", sink=self.nome, module_id=self._module_id)
        self._ligar_a_rota()
        return True

    def _ligar_a_rota(self) -> None:
        """Carrega os ``module-loopback`` desta rota. Silencioso quando não há."""
        rota = self.rota
        if rota is None or not rota.tem_rota:
            return
        for argv in _enquanto_o_servidor_atende(argv_das_rotas(self.nome, rota)):
            saida = self.runner(list(argv))
            linhas = [ln.strip() for ln in (saida or "").splitlines() if ln.strip()]
            if not linhas or not linhas[-1].isdigit():
                logger.info("som_rota_nao_subiu", sink=self.nome, argv=" ".join(argv))
                continue
            self._rotas.append(linhas[-1])
            logger.info("som_rota_ligada", sink=self.nome, module_id=linhas[-1])

    def religar(self, rota: RotaDoNo | None) -> bool:
        """Troca a ROTA deste nó **sem tirar o nó do lugar**. ``True`` = mexeu."""
        if rota is None or assinatura_da_rota(rota) == assinatura_da_rota(self.rota):
            return False
        if self._module_id is None:
            self.rota = rota
            return False
        anterior = self.rota
        for module_id in reversed(self._rotas):
            self.runner(["pactl", "unload-module", module_id])
        self._rotas.clear()
        self.rota = rota
        logger.info(
            "som_rota_religada",
            sink=self.nome,
            de=(anterior.fonte if anterior is not None else "?"),
            para=rota.fonte,
            por_onde=rota.por_onde,
        )
        self._ligar_a_rota()
        return True

    def parar(self) -> None:
        """Descarrega a rota e o módulo, nessa ordem. Idempotente."""
        for module_id in reversed(self._rotas):
            self.runner(["pactl", "unload-module", module_id])
        self._rotas.clear()
        if self._module_id is None:
            return
        self.runner(["pactl", "unload-module", self._module_id])
        logger.info("som_sink_removido", sink=self.nome)
        self._module_id = None


    def estado(self) -> str | None:
        """``RUNNING`` / ``IDLE`` / ``SUSPENDED`` do nó, PERGUNTADO ao servidor."""
        if self._module_id is None or _o_recuo().mudo():
            return None
        saida = self.runner(["pactl", "list", "sinks", "short"])
        for linha in (saida or "").splitlines():
            campos = linha.split("\t")
            if len(campos) > _COLUNA_DO_ESTADO and campos[1].strip() == self.nome:
                return campos[_COLUNA_DO_ESTADO].strip()
        return None

    def monitor(self) -> str:
        """O nome do monitor deste nó — de onde o PCM é lido."""
        return f"{self.nome}.monitor" if self.nome else ""

    def __enter__(self) -> SinkVirtualPipeWire:
        self.iniciar()
        return self

    def __exit__(self, *_exc: object) -> None:
        self.parar()


_COLUNA_DO_ESTADO = 4


MS_POR_QUADRO = 10

VOLTA_DA_SEQUENCIA = 16

#: **O `--raw` DO `pw-record` É O QUE FAZ O `stdout` SER SÓ PCM** — 02/10/2026,
GRAVADORES_DO_MONITOR: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "pw-record",
        ("--raw", "--target={fonte}", "--rate={taxa}", "--channels={canais}",
         "--format=s16", "--latency={latencia_ms}ms", "-P", "node.name={rotulo}",
         "-"),
    ),
    (
        "parec",
        ("--device={fonte}", "--rate={taxa}", "--channels={canais}",
         "--format=s16le", "--raw", "--latency-msec={latencia_ms}",
         "--client-name={rotulo}"),
    ),
)

LATENCIA_DO_GRAVADOR_MS = 40


def serial_do_no(nome: str) -> int | None:
    """O ``object.serial`` do nó chamado ``nome``, ou ``None``."""
    if not nome:
        return None
    alvo = nome[: -len(".monitor")] if nome.endswith(".monitor") else nome
    saida = _rodar(["pactl", "list", "sinks", "short"])
    if saida is None:
        return None
    for linha in saida.splitlines():
        campos = linha.split("\t")
        if len(campos) >= 2 and campos[1] == alvo:
            try:
                return int(campos[0])
            except ValueError:
                return None
    return None


def o_servidor_e_o_pipewire(
    runner: Callable[[list[str]], str | None] | None = None,
) -> bool:
    """Quem responde ao ``pactl`` é o ``pipewire-pulse``? ``False`` se não sei."""
    correr: Any = runner or rodar_pactl
    for linha in (correr(["pactl", "info"]) or "").splitlines():
        chave, _, valor = linha.partition(":")
        if chave.strip() == "Server Name":
            return "pipewire" in valor.lower()
    return False


def rotulo_do_gravador(*, uniq: str, papel: str = "som") -> str:
    """O nome que damos ao NOSSO nó de gravação. Único por controle E POR PAPEL."""
    from hefesto_dualsense4unix.integrations.endpoint_de_haptica import (
        marca_do_controle,
    )

    marca = marca_do_controle(uniq)
    if not marca:
        return ""
    return f"hefesto-ponte-{marca}-{papel}"


def argv_do_gravador(
    fonte: str,
    *,
    taxa: int = TAXA_DO_ENCODER,
    canais: int = CANAIS_DO_ENCODER,
    rotulo: str = "hefesto-ponte",
    propriedades: Sequence[str] = (),
) -> list[str]:
    """O comando que lê PCM cru do monitor de um nó. `[]` se não há tocador."""
    if not fonte:
        return []
    for binario, modelo in GRAVADORES_DO_MONITOR:
        if shutil.which(binario) is None:
            continue
        if binario == "pw-record":
            serial = serial_do_no(fonte) if o_servidor_e_o_pipewire() else None
            if serial is None:
                continue
            argv = [binario, *(m.format(fonte=str(serial), taxa=taxa,
                                        canais=canais, rotulo=rotulo,
                                        latencia_ms=LATENCIA_DO_GRAVADOR_MS)
                               for m in modelo)]
            if propriedades:
                indice = argv.index(f"node.name={rotulo}")
                argv[indice] = " ".join((argv[indice], *propriedades))
            return argv
        return [binario, *(m.format(fonte=fonte, taxa=taxa, canais=canais,
                                    rotulo=rotulo,
                                    latencia_ms=LATENCIA_DO_GRAVADOR_MS)
                           for m in modelo),
                *(f"--property={p}" for p in propriedades)]
    return []


def conferir_o_alvo_do_gravador(rotulo: str) -> str | None:
    """A que nó de ORIGEM o gravador chamado `rotulo` se ligou. ``None``=não sei."""
    if not rotulo:
        return None
    try:
        proc = subprocess.run(
            ["pw-dump"], capture_output=True, text=True, timeout=3.0, check=False
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if getattr(proc, "returncode", 1) != 0:
        return None
    try:
        objetos = json.loads(proc.stdout or "[]")
    except (ValueError, TypeError):
        return None

    nomes: dict[int, str] = {}
    meus: set[int] = set()
    for o in objetos:
        if o.get("type") != "PipeWire:Interface:Node":
            continue
        props = (o.get("info") or {}).get("props") or {}
        nome = str(props.get("node.name") or "")
        ident = o.get("id")
        if not isinstance(ident, int):
            continue
        nomes[ident] = nome
        if nome == rotulo:
            meus.add(ident)
    if not meus:
        return None

    for o in objetos:
        if o.get("type") != "PipeWire:Interface:Link":
            continue
        info = o.get("info") or {}
        if info.get("input-node-id") in meus:
            origem = info.get("output-node-id")
            if isinstance(origem, int):
                return nomes.get(origem) or None
    return None


FILA_CHEIA_DO_KERNEL: frozenset[int] = frozenset(
    {_errno.EAGAIN, _errno.EWOULDBLOCK, _errno.ENOBUFS}
)

TETO_DE_CEDER_S = 2.0

MOTIVO_FILA_PARADA = "o Bluetooth não drena o adaptador deste controle"


@dataclass
class ContagemDaBomba:
    """O que a bomba mediu. **Nenhum destes números é "saiu som".**"""

    pcm_lido: int = 0
    pcm_curto: int = 0
    quadros_opus: int = 0
    quadros_recusados: int = 0
    reports_montados: int = 0
    escritas_aceitas_pelo_kernel: int = 0
    escritas_recusadas: int = 0
    quadros_cedidos_por_fila_cheia: int = 0
    quadros_cedidos_ao_governador: int = 0
    bytes_escritos: int = 0
    segundos: float = 0.0
    blocos_hapticos: int = 0
    hapticos_mudos: int = 0
    pico_haptico: int = 0
    reports_calados: int = 0

    @property
    def reports_por_segundo(self) -> float:
        """A cadência REAL, medida — não a nominal de 100 Hz do encoder."""
        return (self.reports_montados / self.segundos) if self.segundos > 0 else 0.0

    @property
    def bytes_por_segundo(self) -> float:
        """A banda que este arranjo pede do rádio. É o número do D5 dela."""
        return (self.bytes_escritos / self.segundos) if self.segundos > 0 else 0.0

    def linhas(self) -> list[str]:
        """O relatório, com a ressalva colada no número que ela protege."""
        return [
            f"  PCM lido do nó ............. {self.pcm_lido} B",
            f"  leituras curtas (completadas com silêncio) {self.pcm_curto}",
            f"  quadros Opus ............... {self.quadros_opus}",
            f"  quadros que o encoder recusou {self.quadros_recusados}",
            f"  blocos hápticos ............ {self.blocos_hapticos}"
            f" ({self.hapticos_mudos} mudos, pico {self.pico_haptico}/127)",
            f"  reports montados ........... {self.reports_montados}"
            f"  ({self.reports_por_segundo:.1f}/s)",
            f"  calados por silêncio ....... {self.reports_calados}",
            f"  escritas ACEITAS PELO KERNEL {self.escritas_aceitas_pelo_kernel}",
            f"  escritas recusadas ......... {self.escritas_recusadas}",
            f"  bytes no fio ............... {self.bytes_escritos} B"
            f"  ({self.bytes_por_segundo / 1024:.1f} KiB/s)",
            "  ATENÇÃO: 'aceitas pelo kernel' NÃO é 'o firmware obedeceu', e",
            "  nada aqui é medição de som. Quem mede som é a orelha dela.",
        ]


class BombaDeSomPeloRadio:
    """Do monitor do nó ao fio: lê PCM, codifica, monta o degrau e escreve."""

    def __init__(
        self,
        *,
        arranjo: Arranjo,
        fonte: Callable[[int], bytes],
        escritor: Callable[[bytes], int] | None = None,
        codificador: Any = None,
        tag_audio: int = BLOCO_SPEAKER,
        seco: bool = True,
        common: bytes | None = None,
        com_microfone: bool | Callable[[], bool] = False,
        fonte_haptica: Callable[[int], bytes] | None = None,
        conversor: Any = None,
        vaga: Any = None,
        relogio: Callable[[], float] | None = None,
        so_com_sinal: bool = False,
        ganho_da_haptica: float | Callable[[], float] = 1.0,
    ) -> None:
        if arranjo.common_preservado and common is None:
            raise ValueError(
                f"o arranjo {arranjo.nome!r} preserva o `common` em [3..49] e "
                "a bomba não recebeu nenhum — um `common` zerado não pede rota, "
                "volume nem pré-amp, e o corpo iria ao fio pedindo NADA. Passe "
                "`common=alto_falante_bt.common_de_audio()`"
            )
        if common is not None and len(common) != COMMON_LEN:
            raise ValueError(
                f"o `common` tem de ter {COMMON_LEN} B medidos, veio com {len(common)}"
            )
        self.arranjo = arranjo
        self.fonte = fonte
        self.escritor = escritor
        self.tag_audio = tag_audio
        self.seco = bool(seco) or escritor is None
        self.common = common
        self._codificador = codificador
        self._cedendo = False
        self._cedendo_desde: float | None = None
        self._relogio = relogio or time.monotonic
        self.vaga = vaga
        self.fila_parada = False
        self._seq = 0
        self._quadros_mandados = 0
        self.com_microfone = com_microfone
        self.fonte_haptica = fonte_haptica
        self._conversor = conversor
        self.ganho_da_haptica = ganho_da_haptica
        self._blocos: list[bytes] = []
        self.so_com_sinal = bool(so_com_sinal)
        self._mandou_sinal = False
        self._calado_desde: float | None = None
        self.contagem = ContagemDaBomba()


    def quer_o_microfone(self) -> bool:
        """O bit 0 dos enables DESTE report. Nunca levanta."""
        quer = self.com_microfone
        if not callable(quer):
            return bool(quer)
        try:
            return bool(quer())
        except Exception:  # pragma: no cover - defensivo
            logger.debug("som_radio_oraculo_do_mic_ilegivel", exc_info=True)
            return False

    @property
    def bytes_de_pcm_por_report(self) -> int:
        """Quanto PCM cru um report deste arranjo consome."""
        return BYTES_DE_PCM_POR_QUADRO * self.arranjo.quadros_de_audio

    @property
    def ms_por_report(self) -> int:
        """Quantos milissegundos de som um report deste arranjo carrega."""
        return MS_POR_QUADRO * self.arranjo.quadros_de_audio

    @property
    def relogio(self) -> Callable[[], float]:
        """O relógio desta bomba: o do teto de ceder e o da linha de saída da ponte."""
        return self._relogio

    @property
    def taxa_da_fonte_hz(self) -> int:
        """A taxa em que a fonte tem de entregar para andar no ritmo deste arranjo."""
        amostras = (
            self.bytes_de_pcm_por_report // (2 * CANAIS_DO_ENCODER)
            or QUADROS_POR_BLOCO_HAPTICO
        )
        return round(amostras / self.intervalo_de_envio_s)

    def _codificar(self, pcm: bytes) -> bytes | None:
        """O quadro Opus, ou None se a libopus recusou. Encoder preguiçoso."""
        if self._codificador is None:
            self._codificador = CodificadorOpus()
        quadro = self._codificador.codificar(pcm)
        return quadro if quadro is None else bytes(quadro)


    def um_report(self) -> bytes | None:
        """Lê o PCM de UM report, codifica, monta e devolve os bytes."""
        haptico = b""
        if self.arranjo.len_haptico and self.fonte_haptica is not None:
            bloco = self._bloco_haptico()
            if bloco is None:
                return None
            haptico = bloco
        pedido = self.bytes_de_pcm_por_report
        pcm = self.fonte(pedido) if pedido else b""
        if not pcm and pedido:
            return None
        self.contagem.pcm_lido += len(pcm)
        if len(pcm) < pedido:
            self.contagem.pcm_curto += 1
            pcm = pcm + b"\x00" * (pedido - len(pcm))
        if self.so_com_sinal and not self._vale_mandar(haptico, pcm):
            self.contagem.reports_calados += 1
            return b""
        quadros: list[bytes] = []
        for i in range(self.arranjo.quadros_de_audio):
            pedaco = pcm[i * BYTES_DE_PCM_POR_QUADRO : (i + 1) * BYTES_DE_PCM_POR_QUADRO]
            quadro = self._codificar(pedaco)
            if quadro is None:
                self.contagem.quadros_recusados += 1
                return b""
            self.contagem.quadros_opus += 1
            quadros.append(quadro)
        report = self.arranjo.montar(
            quadros,
            seq=self._seq,
            tag_audio=self.tag_audio,
            common=self.common,
            controle=self._controle_deste_report(),
            haptico=haptico,
        )
        self._seq = (self._seq + 1) % VOLTA_DA_SEQUENCIA
        self._quadros_mandados += self.arranjo.quadros_de_audio or 1
        self.contagem.reports_montados += 1
        return report

    def _vale_mandar(self, haptico: bytes, pcm: bytes) -> bool:
        """Este report vai ao rádio? Sinal, ou o silêncio que fecha o último sinal.

        A-HAPTICA-DO-RADIO-OBEDECE-AO-SINAL-DO-JOGO-01, 28/09/2026. **O
        CRITÉRIO É O DO ARRANJO**: o sinal se procura nos canais que ESTE
        report leva, e não num canal fixo. No arranjo da háptica
        (:data:`ARRANJO_HAPTICA_032`) é o bloco que :mod:`haptica_bt` montou
        dos canais 3-4 do endpoint, os motores; no do alto-falante
        (:data:`ARRANJO_035`) é o PCM do nó de som, os canais 1-2. Um critério
        fixo nos motores calaria o alto-falante de todo controle em modo som.

        **SILÊNCIO É ZERO EXATO**, e isso é medido: o PRAGMATA no menu manda
        RMS e pico 0 nos quatro canais dos quatro endpoints (27/09). Um bloco
        háptico que a conversão para int8 arredonda para zero também não mexe
        o motor, e também não vai.

        **DEPOIS DO ÚLTIMO SINAL VAI UM SILÊNCIO** — os dados já são zero, e o
        report montado deles é o :func:`haptica_bt.bloco_de_silencio` no
        motor e o quadro mudo no alto-falante: o motor para no zero em vez de
        ficar no último valor, e o rádio volta a ficar livre.
        """
        if haptico.count(0) < len(haptico) or pcm.count(0) < len(pcm):
            self._mandou_sinal = True
            return True
        if self._mandou_sinal:
            self._mandou_sinal = False
            return True
        if self._cedendo and self._calado_desde is None:
            self._calado_desde = self._relogio()
        return False

    @property
    def bytes_de_pcm_da_haptica(self) -> int:
        """O PCM cru de UM bloco háptico: 512 quadros de 4 canais s16le."""
        return QUADROS_POR_BLOCO_HAPTICO * 2 * CANAIS_DA_HAPTICA

    def _bloco_haptico(self) -> bytes | None:
        """O próximo bloco de 64 B, ou None quando a fonte secou."""
        if self._conversor is None:
            from hefesto_dualsense4unix.integrations.haptica_bt import ConversorDeHaptica

            self._conversor = ConversorDeHaptica()
        while not self._blocos:
            if self.fonte_haptica is None:
                return None
            pcm = self.fonte_haptica(self.bytes_de_pcm_da_haptica)
            if not pcm:
                return None
            ganho = self.ganho_da_haptica
            with contextlib.suppress(Exception):
                self._conversor.ganho = float(ganho() if callable(ganho) else ganho)
            self._blocos.extend(self._conversor.alimentar(pcm))
        bloco = self._blocos.pop(0)
        self.contagem.blocos_hapticos += 1
        pico = max((b - 256 if b > 127 else b) for b in bloco) if bloco else 0
        pico = max(pico, -min((b - 256 if b > 127 else b) for b in bloco)) if bloco else 0
        if pico == 0:
            self.contagem.hapticos_mudos += 1
        elif pico > self.contagem.pico_haptico:
            self.contagem.pico_haptico = pico
        return bloco

    def _controle_deste_report(self) -> bytes:
        """Os bytes do bloco de controle, montados por report quando ele conta."""
        if not self.arranjo.controle_conta_quadros:
            return b""
        return controle_de_audio_035(
            contador_de_quadros=self._quadros_mandados,
            com_microfone=self.quer_o_microfone(),
        )

    @property
    def intervalo_de_envio_s(self) -> float:
        """O intervalo entre reports, em segundos — o MEDIDO quando existe."""
        medido = self.arranjo.intervalo_de_envio_s
        if medido is not None:
            return float(medido)
        return self.ms_por_report / 1000.0

    def escrever(self, report: bytes) -> bool:
        """Entrega o report ao escritor. **Seco, devolve True sem escrever.**"""
        if self.seco or self.escritor is None:
            return True
        vaga = self.vaga
        if vaga is not None:
            if vaga.derrubar:
                self.fila_parada = True
                return False
            if vaga.cedendo:
                self.contagem.quadros_cedidos_ao_governador += 1
                return True
        calado_desde, self._calado_desde = self._calado_desde, None
        if calado_desde is not None and self._cedendo_desde is not None:
            self._cedendo_desde += max(0.0, self._relogio() - calado_desde)
        try:
            escritos = int(self.escritor(report))
        except OSError as erro:
            if erro.errno in FILA_CHEIA_DO_KERNEL:
                self.contagem.quadros_cedidos_por_fila_cheia += 1
                agora = self._relogio()
                if not self._cedendo or self._cedendo_desde is None:
                    self._cedendo = True
                    self._cedendo_desde = agora
                    logger.info("som_radio_cedendo_a_fila_cheia", erro=str(erro))
                elif agora - self._cedendo_desde > TETO_DE_CEDER_S:
                    self.fila_parada = True
                    cedendo_s = round(agora - self._cedendo_desde, 3)
                    logger.warning(
                        "som_radio_fila_parada",
                        cedendo_s=cedendo_s,
                        cedidos=self.contagem.quadros_cedidos_por_fila_cheia,
                    )
                    if vaga is not None:
                        vaga.fila_parada(cedendo_s)
                    return False
                return True
            self.contagem.escritas_recusadas += 1
            logger.info("som_escrita_recusada", erro=str(erro))
            return False
        if self._cedendo:
            self._cedendo = False
            self._cedendo_desde = None
            logger.info(
                "som_radio_voltou_a_caber",
                cedidos=self.contagem.quadros_cedidos_por_fila_cheia,
            )
        self.contagem.escritas_aceitas_pelo_kernel += 1
        self.contagem.bytes_escritos += escritos
        if vaga is not None:
            vaga.contar_escrita()
        return True

    def rodar(
        self,
        *,
        segundos: float,
        agora: Callable[[], float] | None = None,
        dormir: Callable[[float], None] | None = None,
    ) -> ContagemDaBomba:
        """O laço, por `segundos` de relógio. Devolve a contagem."""
        relogio = agora or time.monotonic
        comeco = relogio()
        limite = comeco + max(0.0, float(segundos))
        while relogio() < limite:
            report = self.um_report()
            if report is None:
                break
            if report and not self.escrever(report):
                break
            if dormir is not None:
                dormir(self.intervalo_de_envio_s)
        self.contagem.segundos = relogio() - comeco
        return self.contagem


def fonte_de_arquivo(fd: int) -> Callable[[int], bytes]:
    """Uma fonte de PCM que lê de um descritor já aberto (pipe, arquivo)."""

    def _ler(quantos: int) -> bytes:
        pedacos: list[bytes] = []
        faltam = quantos
        while faltam > 0:
            try:
                pedaco = os.read(fd, faltam)
            except OSError:
                break
            if not pedaco:
                break
            pedacos.append(pedaco)
            faltam -= len(pedaco)
        return b"".join(pedacos)

    return _ler


def fonte_com_ritmo(
    fonte: Callable[[int], bytes],
    *,
    ms_por_report: float,
    agora: Callable[[], float] | None = None,
    dormir: Callable[[float], None] | None = None,
) -> Callable[[int], bytes]:
    """Dá RITMO a uma fonte que não tem — e sem ela o ensaio vira uma inundação."""
    relogio = agora or time.monotonic
    esperar = dormir or time.sleep
    intervalo = max(0.0, ms_por_report / 1000.0)
    prazo = {"t": 0.0}

    def _ler(quantos: int) -> bytes:
        if prazo["t"] == 0.0:
            prazo["t"] = relogio()
        else:
            falta = prazo["t"] - relogio()
            if falta > 0:
                esperar(falta)
        prazo["t"] += intervalo
        return fonte(quantos)

    return _ler


def escritor_de_hidraw(fd: int) -> Callable[[bytes], int]:
    """Um escritor que entrega no hidraw aberto em `fd`."""

    def _escrever(dados: bytes) -> int:
        return os.write(fd, dados)

    return _escrever


@dataclass(frozen=True)
class Diagnostico:
    """Um fato por linha. O molde do *"ausência é resposta"* da entrada."""

    controles: list[str]
    libopus: str | None
    pactl: bool
    null_sink: bool
    loopback: bool

    @property
    def pronto(self) -> bool:
        return bool(self.controles) and self.pactl and self.null_sink

    @property
    def impedimentos(self) -> list[str]:
        faltas: list[str] = []
        if not self.controles:
            faltas.append("nenhum DualSense na lista — sem controle não há nó de som")
        if not self.pactl:
            faltas.append("pactl ausente — sem PipeWire/PulseAudio não há onde publicar")
        if self.pactl and not self.null_sink:
            faltas.append(
                "module-null-sink indisponível no servidor de áudio "
                "(libpipewire-module-protocol-pulse.so)"
            )
        if not self.libopus:
            faltas.append(
                "libopus ausente — o nó sobe, mas nada pode ser codificado "
                f"para o rádio ({gesto_de_instalar('opus')})"
            )
        if self.pactl and not self.loopback:
            faltas.append(
                "libpipewire-module-loopback.so ausente — no cabo o monitor do "
                "nó não pode ser ligado ao sink do controle"
            )
        return faltas


def _tem_modulo_pulse(nome: str) -> bool:
    """O nome do módulo está na camada de compatibilidade Pulse do PipeWire?"""
    alvo = nome.encode("ascii")
    for pasta in _DIRS_PIPEWIRE:
        so = Path(pasta) / "libpipewire-module-protocol-pulse.so"
        try:
            if alvo in so.read_bytes():
                return True
        except OSError:
            continue
    return False


def _tem_so_pipewire(arquivo: str) -> bool:
    return any(Path(d).joinpath(arquivo).exists() for d in _DIRS_PIPEWIRE)


def versao_libopus() -> str | None:
    """Versão da libopus, ou None se ela não estiver no sistema."""
    try:
        lib = _carregar_libopus_encoder()
        lib.opus_get_version_string.restype = ctypes.c_char_p
        bruto = lib.opus_get_version_string()
        return str(bytes(bruto).decode("utf-8", "replace"))
    except Exception:
        return None


def diagnosticar(uniqs: Sequence[str] | None = None) -> Diagnostico:
    """Fotografa as pré-condições do nó sem mexer em nada (só leitura)."""
    if uniqs is None:
        from hefesto_dualsense4unix.integrations.dualsense_bt_audio import (
            nos_dualsense_bluetooth,
        )

        uniqs = [str(getattr(no, "uniq", "")) for no in nos_dualsense_bluetooth()]
    tem_pactl = shutil.which("pactl") is not None
    return Diagnostico(
        controles=[u for u in uniqs if u],
        libopus=versao_libopus(),
        pactl=tem_pactl,
        null_sink=tem_pactl and _tem_modulo_pulse(_MODULO_NULL_SINK),
        loopback=tem_pactl and _tem_so_pipewire("libpipewire-module-loopback.so"),
    )


#: seja o canal do sfx caindo pra cada controle"*. <!-- noqa-acento: citação literal dela -->
#: **POR QUE UM GANCHO E NÃO UMA LEITURA:** quem PERGUNTA é o `state_full`, que
_DIZEDOR_DA_FONTE: Callable[[str], str] | None = None


def registrar_dizedor_da_fonte(
    dizedor: Callable[[str], str] | None,
) -> Callable[[str], str] | None:
    """Instala quem sabe a `fonte` de um `uniq`. Devolve o anterior."""
    global _DIZEDOR_DA_FONTE
    anterior = _DIZEDOR_DA_FONTE
    _DIZEDOR_DA_FONTE = dizedor
    return anterior


def fonte_publicada(uniq: str) -> str:
    """A `fonte` deste controle para a TELA — `""` quando ninguém sabe dizer.

    `""` não é `sfx`: é *"não perguntei a ninguém"*, e a tela o traduz em
    "nenhum botão aceso" em vez de acender o padrão. Acender `sfx` sem saber
    seria a tela afirmando uma escolha que ela não fez.

    Nunca levanta: quem chama é o `state_full`.
    """
    dizedor = _DIZEDOR_DA_FONTE
    if dizedor is None or not uniq:
        return ""
    try:
        fonte = dizedor(uniq)
    except Exception:  # pragma: no cover - defensivo
        logger.debug("fonte_do_controle_ilegivel", uniq=uniq, exc_info=True)
        return ""
    return fonte if fonte in (FONTE_MIX, FONTE_SFX) else ""


FONTE_MIX = "mix"
FONTE_SFX = "sfx"

FONTE_PADRAO = FONTE_SFX


def a_ponte_do_radio_sabe_montar() -> bool:
    """O Hefesto sabe montar o pacote de áudio que o controle entende sem fio?"""
    return True


def ha_gravador_de_monitor() -> bool:
    """Existe NESTA MÁQUINA um programa capaz de ler o monitor de um nó?"""
    return any(shutil.which(binario) is not None
               for binario, _modelo in GRAVADORES_DO_MONITOR)


def a_ponte_do_radio_pode_subir() -> tuple[bool, str]:
    """Esta máquina consegue subir a ponte AGORA? `(pode, por quê não)`."""
    try:
        _carregar_libopus_encoder()
    except OpusIndisponivelError as erro:
        return False, str(erro)
    return True, ""


def sink_esta_tocando(
    nome: str,
    runner: Callable[[list[str]], str | None] | None = None,
    *,
    na_duvida: bool = False,
) -> bool:
    """O sink tem stream tocando AGORA? É por aqui que se sabe se o jogo usa."""
    if not nome:
        return False
    tocando = sinks_que_tocam([nome], runner, na_duvida=None)
    if tocando is None:
        return na_duvida
    return nome in tocando


JANELA_DO_SINAL_S = 1.0

SURDO_S = 0.5


def tem_sinal_no_pcm(pcm: bytes, *, canais: int = CANAIS_DO_ENCODER) -> bool:
    """O bloco de PCM s16le tem sinal nos canais que o controle toca?"""
    if canais != CANAIS_DA_HAPTICA:
        return pcm.count(0) < len(pcm)
    quadro = 2 * CANAIS_DA_HAPTICA
    inteiro = len(pcm) - len(pcm) % quadro
    if inteiro <= 0:
        return False
    amostras = memoryview(pcm)[:inteiro].cast("h")
    traseiros = amostras[2::4].tobytes() + amostras[3::4].tobytes()
    return traseiros.count(0) < len(traseiros)


class OuvidoDosNos:
    """O DONO de «este nó tem sinal agora?» — um só, para todo chamador."""

    def __init__(self, relogio: Callable[[], float] | None = None) -> None:
        self._relogio = relogio or time.monotonic
        self._trava = threading.Lock()
        self._ultimo_sinal: dict[str, float] = {}
        self._ultima_leitura: dict[str, float] = {}
        self._estado: dict[str, bool] = {}
        self._quem_ouve: list[Any] = []

    def escutar(self, aviso: Callable[[str], Any]) -> None:
        """Inscreve ``aviso(nó)`` para a troca de sinal. Método entra por referência fraca."""
        import weakref

        ref: Any
        try:
            ref = weakref.WeakMethod(aviso)
        except TypeError:

            def ref() -> Callable[[str], Any]:
                return aviso

        with self._trava:
            self._quem_ouve.append(ref)

    def ouvir(self, no: str, com_sinal: bool) -> None:
        """Um bloco do monitor de ``no`` foi lido. Nunca levanta."""
        if not no:
            return
        agora = self._relogio()
        with self._trava:
            self._ultima_leitura[no] = agora
            if com_sinal:
                self._ultimo_sinal[no] = agora
            ultimo = self._ultimo_sinal.get(no)
            estado = ultimo is not None and agora - ultimo < JANELA_DO_SINAL_S
            mudou = self._estado.get(no, False) != estado
            self._estado[no] = estado
            avisos = list(self._quem_ouve) if mudou else []
        vivos = []
        for ref in avisos:
            aviso = ref()
            if aviso is None:
                continue
            vivos.append(ref)
            try:
                aviso(no)
            except Exception:
                logger.debug("sinal_aviso_falhou", no=no, exc_info=True)
        if mudou:
            logger.debug("sinal_do_no_mudou", no=no, com_sinal=estado)
            with self._trava:
                self._quem_ouve = [r for r in self._quem_ouve if r() is not None]

    def tem_sinal(self, no: str) -> bool | None:
        """``True`` com sinal agora, ``False`` escutado e mudo, ``None`` ninguém escuta."""
        if not no:
            return None
        agora = self._relogio()
        with self._trava:
            lido = self._ultima_leitura.get(no)
            ultimo = self._ultimo_sinal.get(no)
        if ultimo is not None and agora - ultimo < JANELA_DO_SINAL_S:
            return True
        if lido is None or agora - lido > SURDO_S:
            return None
        return False


OUVIDO = OuvidoDosNos()


def fonte_que_ouve(
    fonte: Callable[[int], bytes], no: str, *, canais: int = CANAIS_DO_ENCODER
) -> Callable[[int], bytes]:
    """A mesma fonte, e cada bloco que ela entrega passa pelo :data:`OUVIDO`."""
    if not no:
        return fonte

    def _ler(quantos: int) -> bytes:
        pcm = fonte(quantos)
        if pcm:
            OUVIDO.ouvir(no, tem_sinal_no_pcm(pcm, canais=canais))
        return pcm

    return _ler


RECUO_PROIBIDO_DO_OUVIDO: tuple[str, ...] = (
    "node.dont-reconnect=true",
    "node.dont-fallback=true",
)

TAXA_DO_OUVIDO_DA_PLACA = 8_000


class OuvidoDaPlaca:
    """Escuta o monitor da placa de UM controle no cabo, só para o :data:`OUVIDO`."""

    def __init__(
        self,
        *,
        placa: str,
        uniq: str,
        abrir: Callable[[list[str]], Any] | None = None,
    ) -> None:
        self.placa = placa
        self.uniq = uniq
        self._abrir = abrir
        self._proc: Any = None
        self._fio: threading.Thread | None = None
        self._parar = threading.Event()
        self.motivo = ""

    @property
    def vivo(self) -> bool:
        fio = self._fio
        return fio is not None and fio.is_alive()

    def subir(self) -> bool:
        """Sobe o gravador e o fio que o lê. Idempotente; ``False`` diz o motivo."""
        if self.vivo:
            return True
        fonte, proc, motivo = fonte_do_monitor_do_no(
            self.placa,
            uniq=self.uniq,
            papel="placa",
            abrir=self._abrir,
            taxa=TAXA_DO_OUVIDO_DA_PLACA,
            canais=CANAIS_DA_HAPTICA,
            propriedades=RECUO_PROIBIDO_DO_OUVIDO,
        )
        if fonte is None:
            self.motivo = motivo
            return False
        self._proc = proc
        self._parar = threading.Event()
        ouvir = fonte_que_ouve(fonte, self.placa, canais=CANAIS_DA_HAPTICA)
        tamanho = (TAXA_DO_OUVIDO_DA_PLACA // 100) * 2 * CANAIS_DA_HAPTICA
        parar = self._parar

        def _escutar() -> None:
            try:
                while not parar.is_set():
                    if not ouvir(tamanho):
                        return
            except Exception:
                logger.debug("haptica_ouvido_da_placa_caiu", exc_info=True)

        self._fio = threading.Thread(
            target=_escutar, name="hefesto-ouvido-da-placa", daemon=True
        )
        self._fio.start()
        return True

    def descer(self) -> None:
        """Para o fio e colhe o gravador. Idempotente, nunca levanta."""
        from hefesto_dualsense4unix.integrations.filho_de_som import (
            derrubar_leitor_de_pipe,
        )

        self._parar.set()
        proc, self._proc = self._proc, None
        fio, self._fio = self._fio, None
        if proc is not None:
            with contextlib.suppress(Exception):
                derrubar_leitor_de_pipe(proc, leitor=fio)


#: O PISO DOS MOTORES no sink de 4 canais do DualSense — HAPTICA-CABO-VOLUME-01
#: os canais 3-4 são os MOTORES: a háptica do DualSense viaja como áudio nos
PISO_DOS_MOTORES = 100


def volumes_do_sink(nome: str, runner: Callable[[list[str]], str | None] | None = None
                    ) -> list[int] | None:
    """Os volumes por canal deste sink, em por cento. ``None`` = não se sabe."""
    correr: Any = runner or rodar_pactl
    saida = correr(["pactl", "list", "sinks"])
    if saida is None:
        return None
    dentro = False
    for linha in saida.splitlines():
        crua = linha.strip()
        if crua.startswith("Name:"):
            dentro = crua.split(":", 1)[1].strip() == nome
            continue
        if dentro and crua.startswith("Volume:"):
            achados = []
            for parte in crua.split(":", 1)[1].split(","):
                for pedaco in parte.split("/"):
                    pedaco = pedaco.strip()
                    if pedaco.endswith("%"):
                        with contextlib.suppress(ValueError):
                            achados.append(int(pedaco[:-1]))
                        break
            return achados or None
    return None


def garantir_motores_audiveis(
    nome: str, runner: Callable[[list[str]], str | None] | None = None
) -> bool:
    """Levanta os canais TRASEIROS do sink ao piso. True = havia o que levantar."""
    volumes = volumes_do_sink(nome, runner)
    if not volumes or len(volumes) < 4:
        return False
    frente, traseiros = volumes[:2], volumes[2:4]
    if min(traseiros) >= PISO_DOS_MOTORES:
        return False
    correr: Any = runner or rodar_pactl
    correr([
        "pactl", "set-sink-volume", nome,
        f"{frente[0]}%", f"{frente[1]}%",
        f"{PISO_DOS_MOTORES}%", f"{PISO_DOS_MOTORES}%",
    ])
    logger.info(
        "haptica_motores_levantados",
        sink=nome, eram=traseiros, agora=PISO_DOS_MOTORES, frente=frente,
    )
    return True


def sinks_com_motores(runner: Callable[[list[str]], str | None] | None = None
                      ) -> list[str]:
    """Os sinks de QUATRO canais do DualSense que estão no servidor de som.

    HAPTICA-CABO-VOLUME-01, 19/09/2026 — e esta varredura existe porque a
    primeira volta da cura chamou `nome_do_sink(uniq)`, que devolve
    ``hefesto_som_<uniq>``: o null-sink de SOM por rádio, de DOIS canais. Ele
    não tem motor nenhum, e a cura não mexeu em nada. **O nome do sink que tem
    motores não é derivável do `uniq`** — são dois, de origens diferentes:

    ===================================  ==========================================
    sink                                 quem o cria
    ===================================  ==========================================
    ``alsa_output.usb-Sony_…-00…sink``   o ALSA, quando o controle chega pelo CABO
    ``alsa_output.usb-…HEFESTO…-00…``    o produto (`EndpointDeHaptica`), para o Wine
    ===================================  ==========================================

    Perguntar ao SERVIDOR quais têm quatro canais alcança os dois sem adivinhar
    nome, e é a regra desta casa: *quando um valor tem dono, a régua pergunta ao
    dono*.
    """
    correr: Any = runner or rodar_pactl
    saida = correr(["pactl", "list", "short", "sinks"])
    if not saida:
        return []
    achados = []
    for linha in saida.splitlines():
        campos = linha.split("\t")
        if len(campos) < 5:
            continue
        nome, formato = campos[1], campos[3]
        if "4ch" not in formato:
            continue
        if "Sony" in nome or "DualSense" in nome or "HEFESTO" in nome:
            achados.append(nome)
    return achados


def sinks_que_tocam(
    nomes: Iterable[str],
    runner: Callable[[list[str]], str | None] | None = None,
    *,
    na_duvida: set[str] | None = None,
) -> set[str] | None:
    """Quais destes sinks têm stream tocando AGORA — **numa passada só**."""
    fluxos = fluxos_por_sink(nomes, runner)
    if fluxos is None:
        return na_duvida
    return {nome for nome, clientes in fluxos.items() if clientes}


SEM_CLIENTE = "-"


def fluxos_por_sink(
    nomes: Iterable[str],
    runner: Callable[[list[str]], str | None] | None = None,
) -> dict[str, tuple[str, ...]] | None:
    """``{sink: (cliente de cada fluxo que toca nele, …)}`` — numa passada de dois `pactl`."""
    alvos = {n for n in nomes if n}
    if not alvos:
        return {}
    correr: Any = runner or rodar_pactl
    sinks = correr(["pactl", "list", "short", "sinks"])
    if sinks is None:
        return None
    por_indice: dict[str, str] = {}
    for linha in sinks.splitlines():
        campos = linha.split("\t")
        if len(campos) > 1 and campos[1] in alvos:
            por_indice[campos[0].strip()] = campos[1]
    if not por_indice:
        return {}
    entradas = correr(["pactl", "list", "short", "sink-inputs"])
    if entradas is None:
        return None
    fluxos: dict[str, list[str]] = {nome: [] for nome in por_indice.values()}
    for linha in entradas.splitlines():
        campos = linha.split("\t")
        if len(campos) > 1:
            alvo = por_indice.get(campos[1].strip())
            if alvo is not None:
                cliente = campos[2].strip() if len(campos) > 2 else ""
                fluxos[alvo].append(cliente or SEM_CLIENTE)
    return {nome: tuple(clientes) for nome, clientes in fluxos.items()}


def donos_dos_fluxos(
    nomes: Iterable[str],
    runner: Callable[[list[str]], str | None] | None = None,
) -> frozenset[str] | None:
    """Os clientes do servidor que tocam nestes sinks — a partida do jogo."""
    fluxos = fluxos_por_sink(nomes, runner)
    if fluxos is None:
        return None
    return frozenset(
        cliente
        for clientes in fluxos.values()
        for cliente in clientes
        if cliente and cliente != SEM_CLIENTE
    )


def clientes_conectados(
    runner: Callable[[list[str]], str | None] | None = None,
) -> frozenset[str] | None:
    """Os índices dos clientes conectados ao servidor de som agora. ``None`` = não sei."""
    correr: Any = runner or rodar_pactl
    saida = correr(["pactl", "list", "short", "clients"])
    if saida is None:
        return None
    return frozenset(
        linha.split("\t", 1)[0].strip()
        for linha in saida.splitlines()
        if linha.strip()
    )


def fonte_do_monitor_do_no(
    id_do_no: str,
    *,
    uniq: str,
    papel: str = "som",
    abrir: Callable[[list[str]], Any] | None = None,
    taxa: int | None = None,
    canais: int = CANAIS_DO_ENCODER,
    propriedades: Sequence[str] = (),
) -> tuple[Callable[[int], bytes] | None, Any, str]:
    """`(fonte de PCM, processo, motivo)` lendo o monitor do nó DAQUELE controle."""
    from hefesto_dualsense4unix.integrations.filho_de_som import (
        derrubar_leitor_de_pipe,
        lancar_leitor,
    )

    if not id_do_no:
        return None, None, "o controle não tem nó de som publicado"
    rotulo = rotulo_do_gravador(uniq=uniq, papel=papel)
    if not rotulo:
        return None, None, "sem `uniq` não há rótulo único para o gravador"
    argv = argv_do_gravador(
        f"{id_do_no}.monitor",
        rotulo=rotulo,
        taxa=taxa_da_fonte(papel) if taxa is None else taxa,
        canais=canais,
        propriedades=propriedades,
    )
    if not argv:
        return None, None, "nem `pw-record` nem `parec` nesta máquina"
    lancar = abrir or lancar_leitor
    try:
        proc = lancar(argv)
    except OSError as erro:
        return None, None, f"não consegui abrir o gravador do monitor: {erro}"
    saida = getattr(proc, "stdout", None)
    if saida is None:
        como = derrubar_leitor_de_pipe(proc)
        logger.info(
            "som_gravador_sem_saida_colhido",
            codigo=como.codigo,
            por=como.por,
            ms=como.ms,
        )
        return None, None, "o gravador subiu sem `stdout`"

    ligado_a = conferir_o_alvo_do_gravador(rotulo)
    if ligado_a is None:
        logger.info("som_gravador_alvo_nao_conferido", no=id_do_no, rotulo=rotulo)
    elif id_do_no not in ligado_a:
        logger.warning(
            "som_gravador_no_alvo_errado",
            pedido=id_do_no,
            ligado_a=ligado_a,
            detalhe=(
                "o PipeWire deu a fonte padrão no lugar do monitor pedido; "
                "seguir tocaria essa fonte no alto-falante do controle "
                "(SOM-ECO-02)"
            ),
        )
        derrubar_leitor_de_pipe(proc)
        return None, None, (
            f"o gravador ligou-se a `{ligado_a}` e não ao monitor de `{id_do_no}`"
        )
    return fonte_de_arquivo(saida.fileno()), proc, ""


class PonteDeSomPorRadio:
    """Do monitor do nó ao alto-falante do controle, por rádio. Uma por controle."""

    def __init__(
        self,
        *,
        uniq: str,
        abrir_hidraw: Callable[[], int | None],
        fonte_de_pcm: Callable[[int], bytes],
        arranjo: Arranjo | None = None,
        rota: int = BLOCO_SPEAKER,
        com_microfone: bool | Callable[[], bool] = False,
        seco: bool = False,
        gravador: Any | None = None,
        fonte_de_haptica: Callable[[int], bytes] | None = None,
        gravador_da_haptica: Any | None = None,
        vaga: Any = None,
        so_com_sinal: bool = True,
        relogio: Callable[[], float] | None = None,
        no_do_som: str = "",
        no_da_haptica: str = "",
        ganho_da_haptica: float | Callable[[], float] = 1.0,
    ) -> None:
        self.uniq = uniq
        self.ganho_da_haptica = ganho_da_haptica
        self._no_do_som = no_do_som
        self._no_da_haptica = no_da_haptica
        self._ouvinte: threading.Thread | None = None
        self.so_com_sinal = bool(so_com_sinal)
        self._relogio = relogio
        self._vaga = vaga
        self._abrir_hidraw = abrir_hidraw
        self._fonte = fonte_de_pcm
        self._fonte_da_haptica = fonte_de_haptica
        self._gravador_da_haptica = gravador_da_haptica
        self.arranjo = arranjo or ARRANJO_PADRAO
        self.rota = rota
        self.com_microfone = com_microfone
        self._seco = bool(seco)
        self._bomba: BombaDeSomPeloRadio | None = None
        self._thread: threading.Thread | None = None
        self._gravador: Any | None = gravador
        self.como_morreu_o_gravador: Any | None = None
        self._parar: threading.Event | None = None
        self.motivo: str = ""

    def esta_de_pe(self) -> bool:
        """A ponte está no ar para ESTE controle, **e continuará**?"""
        parar = self._parar
        return self._corrida_viva() and (parar is None or not parar.is_set())

    def _corrida_viva(self) -> bool:
        """A thread da última corrida ainda respira? (Mesmo já mandada parar.)"""
        thread = self._thread
        return thread is not None and thread.is_alive()

    def subir(self) -> bool:
        """Abre o hidraw, monta a bomba e põe o laço numa thread. Idempotente."""
        if self.esta_de_pe():
            return True
        if self._corrida_viva():
            self.motivo = (
                "a ponte anterior deste controle ainda está descendo; "
                "não subo por cima dela"
            )
            logger.info("som_radio_ponte_anterior_viva", uniq=self.uniq)
            return False
        pode, porque = a_ponte_do_radio_pode_subir()
        if not pode:
            self.motivo = porque
            logger.info("som_radio_ponte_sem_opus", uniq=self.uniq, motivo=porque)
            return False
        fd = self._abrir_hidraw()
        if fd is None:
            self.motivo = "não consegui abrir o hidraw deste controle"
            logger.info("som_radio_ponte_sem_hidraw", uniq=self.uniq)
            return False
        parar = threading.Event()
        self._parar = parar
        fonte_do_som = fonte_que_ouve(self._fonte, self._no_do_som)
        fonte_da_haptica = (
            fonte_que_ouve(
                self._fonte_da_haptica, self._no_da_haptica, canais=CANAIS_DA_HAPTICA
            )
            if self._fonte_da_haptica is not None
            else None
        )
        haptica_no_ar = bool(self.arranjo.len_haptico)
        self._bomba = BombaDeSomPeloRadio(
            arranjo=self.arranjo,
            fonte=fonte_do_som,
            escritor=escritor_de_hidraw(fd),
            tag_audio=self.rota,
            seco=self._seco,
            com_microfone=self.com_microfone,
            fonte_haptica=fonte_da_haptica if haptica_no_ar else None,
            vaga=self._vaga,
            so_com_sinal=self.so_com_sinal,
            relogio=self._relogio,
            ganho_da_haptica=self.ganho_da_haptica,
        )
        self._thread = threading.Thread(
            target=self._laco,
            args=(fd, parar),
            name=f"som-radio-{self.uniq[:6]}",
            daemon=True,
        )
        self._thread.start()
        so_ouvir, tamanho = (
            (fonte_do_som if self._no_do_som else None, BYTES_DE_PCM_POR_QUADRO)
            if haptica_no_ar
            else (
                fonte_da_haptica if self._no_da_haptica else None,
                QUADROS_POR_BLOCO_HAPTICO * 2 * CANAIS_DA_HAPTICA,
            )
        )
        self._ouvinte = None
        if so_ouvir is not None:
            self._ouvinte = threading.Thread(
                target=self._escutar,
                args=(so_ouvir, tamanho, parar),
                name=f"som-ouvido-{self.uniq[:6]}",
                daemon=True,
            )
            self._ouvinte.start()
        self.motivo = ""
        if self._vaga is not None:
            self._vaga.subiu(
                "vibracao" if self.arranjo is ARRANJO_HAPTICA_032 else "som"
            )
        logger.info(
            "som_radio_ponte_de_pe",
            uniq=self.uniq,
            arranjo=self.arranjo.nome,
        )
        return True

    def _laco(self, fd: int, parar: threading.Event) -> None:
        """O laço da bomba, até mandarem parar ou a fonte secar.

        **O ritmo é o da FONTE, e o laço não dorme**: o monitor do nó entrega
        no tempo real, e pedir um report bloqueia até o nó ter tocado as
        amostras dele na taxa do gravador. É a taxa que põe a ponte na cadência
        do aparelho (:data:`TAXA_DA_FONTE_DO_SOM`, 93,75 reports/s); um
        `sleep` aqui somaria um segundo relógio ao do jogo.

        **AO SAIR, ELE DIZ O QUE FEZ** (`som_radio_ponte_saiu`): os segundos
        de pé, as leituras da fonte por segundo (os reports calados inclusive:
        é o ritmo que a fonte impôs), as escritas que o kernel aceitou e os
        quadros cedidos. É o número que a próxima bancada lê, contado pelo
        relógio da bomba.
        """
        bomba = self._bomba
        if bomba is None:
            os.close(fd)
            self._soltar_a_vaga("a ponte não montou a bomba")
            return
        por_que = "a ponte desceu"
        relogio = bomba.relogio
        comeco = relogio()
        leituras = 0
        try:
            while not parar.is_set():
                report = bomba.um_report()
                if report is None:
                    logger.info("som_radio_fonte_secou", uniq=self.uniq)
                    por_que = "a fonte do som secou"
                    break
                leituras += 1
                if report and not bomba.escrever(report):
                    if bomba.fila_parada:
                        self.motivo = MOTIVO_FILA_PARADA
                        por_que = MOTIVO_FILA_PARADA
                        logger.info("som_radio_ponte_caiu_na_fila_parada", uniq=self.uniq)
                    else:
                        por_que = "a escrita foi recusada"
                        logger.info("som_radio_escrita_recusada", uniq=self.uniq)
                    break
        finally:
            try:
                os.close(fd)
            except OSError:
                logger.debug("som_radio_fd_ja_fechado", uniq=self.uniq)
            self._dizer_o_que_fez(bomba, por_que, comeco, leituras)
            self._soltar_a_vaga(por_que)

    def _escutar(
        self, fonte: Callable[[int], bytes], tamanho: int, parar: threading.Event
    ) -> None:
        """Lê a fonte que o arranjo não leva ao rádio, só para o :data:`OUVIDO`.

        Nada vai ao fio: o escritor do controle continua sendo UM, o laço da
        bomba. Sai quando mandam parar ou quando a fonte seca (o gravador foi
        colhido no :meth:`descer`).
        """
        try:
            while not parar.is_set():
                if not fonte(tamanho):
                    break
        except Exception:  # o ouvido nunca derruba a ponte
            logger.debug("som_radio_ouvido_caiu", uniq=self.uniq, exc_info=True)

    def _dizer_o_que_fez(
        self, bomba: BombaDeSomPeloRadio, por_que: str, comeco: float, leituras: int
    ) -> None:
        """A linha de saída da ponte, com o que se contou. Nunca levanta."""
        try:
            segundos = bomba.relogio() - comeco
            contagem = bomba.contagem
            contagem.segundos = segundos
            logger.info(
                "som_radio_ponte_saiu",
                uniq=self.uniq,
                arranjo=self.arranjo.nome,
                por_que=por_que,
                segundos_de_pe=round(segundos, 3),
                leituras=leituras,
                leituras_por_segundo=round(leituras / segundos, 2) if segundos > 0 else 0.0,
                escritas_aceitas=contagem.escritas_aceitas_pelo_kernel,
                calados=contagem.reports_calados,
                cedidos=(
                    contagem.quadros_cedidos_por_fila_cheia
                    + contagem.quadros_cedidos_ao_governador
                ),
            )
        except Exception:
            logger.debug("som_radio_saida_nao_contada", uniq=self.uniq, exc_info=True)

    def _soltar_a_vaga(self, por_que: str) -> None:
        """Devolve a vaga ao governador. Idempotente, nunca levanta."""
        vaga = self._vaga
        if vaga is None:
            return
        try:
            vaga.soltar(por_que)
        except Exception:
            logger.debug("som_radio_vaga_nao_saiu", uniq=self.uniq, exc_info=True)

    def terminou_sozinha(self) -> bool:
        """A corrida acabou SEM que alguém mandasse descer?"""
        thread = self._thread
        parar = self._parar
        return (
            thread is not None
            and not thread.is_alive()
            and (parar is None or not parar.is_set())
        )

    def descer(self, *, esperar_s: float = 1.0) -> bool:
        """Para o laço e espera a thread juntar. Idempotente."""
        from hefesto_dualsense4unix.integrations.filho_de_som import (
            derrubar_leitor_de_pipe,
        )

        parar = self._parar
        if parar is not None:
            parar.set()
        gravador, self._gravador = self._gravador, None
        ouvinte = self._ouvinte
        haptica_no_ar = bool(self.arranjo.len_haptico)
        haptico, self._gravador_da_haptica = self._gravador_da_haptica, None
        if haptico is not None:
            derrubar_leitor_de_pipe(
                haptico, leitor=None if haptica_no_ar else ouvinte, junta_s=esperar_s
            )
            logger.info("haptica_radio_gravador_colhido", uniq=self.uniq)
        thread = self._thread
        if gravador is not None:
            como = derrubar_leitor_de_pipe(
                gravador, leitor=ouvinte if haptica_no_ar else thread, junta_s=esperar_s
            )
            self.como_morreu_o_gravador = como
            logger.info(
                "som_radio_gravador_colhido",
                uniq=self.uniq,
                codigo=como.codigo,
                por=como.por,
                ms=como.ms,
                insistiu=como.insistiu,
            )

        if thread is None:
            self._soltar_a_vaga("a ponte não subiu")
            return True
        if thread.is_alive() and (gravador is None or haptica_no_ar):
            thread.join(timeout=esperar_s)
        if thread.is_alive():
            logger.info(
                "som_radio_ponte_nao_desceu", uniq=self.uniq, esperou_s=esperar_s
            )
            return False
        self._thread = None
        self._parar = None
        return True

    @property
    def contagem(self) -> ContagemDaBomba | None:
        """A contagem da bomba — `None` se ela nunca subiu."""
        return self._bomba.contagem if self._bomba is not None else None


MOTIVO_NO_SEM_PONTE_NO_RADIO = (
    "o som do PC ainda não está saindo neste controle pelo rádio — o caminho "
    "existe e já foi ouvido, e o que falta é a ponte deste controle subir. "
    "Ligue-o no cabo para ouvir por ele enquanto isso."
)

MOTIVO_NO_SEM_SABER_MONTAR = (
    "o Hefesto ainda não sabe montar o pacote de áudio que este controle "
    "entende sem fio. Não é limite do aparelho: ligue-o no cabo para ouvir "
    "por ele enquanto isso."
)

MOTIVO_NO_SEM_PLACA_NO_CABO = (
    "o sistema ainda não publicou a placa de som deste controle, e sem ela não "
    "há por onde o som entrar. Reconecte o cabo do controle."
)

MOTIVO_NO_SEM_ASSENTO = (
    "este controle ainda não tem um lugar de jogador, e o alto-falante leva o "
    "número do lugar. Reconecte o controle."
)

POR_CABO = "cabo"
POR_RADIO = "radio"

TRANSPORTE_CABO = "usb"
TRANSPORTE_RADIO = "bt"

#: com os quatro DualSense dela na mesa. ``daemon/subsystems/alto_falante
#: acento); ``app/audio_saida`` diz ``"bt"`` (a palavra do ``state_full``). O
_PALAVRAS_DE_RADIO = frozenset({"bt", "radio", "rádio", "bluetooth"})


def e_radio(transporte: str) -> bool:
    """Este transporte é o rádio? Aceita as quatro palavras da casa."""
    return str(transporte or "").strip().lower() in _PALAVRAS_DE_RADIO

CANAIS_DO_ALTO_FALANTE = "front-left,front-right"


@dataclass(frozen=True)
class RotaDoNo:
    """Para onde o nó entrega — e, quando não entrega, a frase que diz por quê."""

    tem_rota: bool
    sink: str = ""
    por_onde: str = ""
    motivo: str = ""
    fonte: str = FONTE_PADRAO
    monitor_do_mix: str = ""


def assinatura_da_rota(rota: RotaDoNo | None) -> tuple[bool, str, str, str]:
    """A identidade ESTÁVEL de uma rota: mudou isto, a fiação é outra."""
    if rota is None:
        return (False, "", "", "")
    return (
        bool(rota.tem_rota),
        str(rota.por_onde or ""),
        str(rota.sink or ""),
        str(rota.fonte or ""),
    )


def _sink_proprio_vivo(uniq: str, saida_curta: str) -> str:
    """``hefesto_som_<hex6>`` deste controle, se ele estiver na lista viva."""
    nome = nome_do_sink(uniq)
    if not nome:
        return ""
    for linha in saida_curta.splitlines():
        campos = linha.split("\t")
        if len(campos) >= 2 and campos[1].strip() == nome:
            return nome
    return ""


def sink_do_controle(
    uniq: str,
    uniqs_na_mesa: Sequence[str] = (),
    *,
    runner: Callable[[list[str]], str | None] | None = None,
) -> str:
    """O sink de SAÍDA deste controle — ``""`` quando não dá para saber."""
    from hefesto_dualsense4unix.integrations.fontes_de_captura import (
        CasamentoUSB,
        escolher_sink,
        sinks_dualsense,
    )

    if not uniq:
        return ""
    if _o_recuo().mudo():
        return ""
    ler = runner if runner is not None else _rodar
    curtos = ler(["pactl", "list", "sinks", "short"]) or ""
    proprio = _sink_proprio_vivo(uniq, curtos)
    sinks = sinks_dualsense(curtos)
    if not sinks:
        return proprio
    conhecidos = list(uniqs_na_mesa) or [uniq]
    usb: CasamentoUSB | None = None
    with contextlib.suppress(Exception):
        from hefesto_dualsense4unix.integrations.usb_pai import (
            nos_e_sysfs,
            usb_pai_por_no,
            usb_pai_por_uniq,
        )

        longa = ler(["pactl", "list", "sinks"]) or ""
        if longa.strip():
            usb = CasamentoUSB(
                por_uniq=usb_pai_por_uniq(conhecidos),
                por_no=usb_pai_por_no(nos_e_sysfs(longa)),
            )
    return escolher_sink(sinks, uniq, conhecidos, usb) or proprio


def monitor_da_saida_padrao(
    *, runner: Callable[[list[str]], str | None] | None = None
) -> str:
    """O monitor da saída padrão do sistema — a fonte do «HDMI completo»."""
    if _o_recuo().mudo():
        return ""
    ler = runner if runner is not None else _rodar
    padrao = (ler(["pactl", "get-default-sink"]) or "").strip()
    if not padrao or padrao.startswith("@"):
        return ""
    return f"{padrao}.monitor"


def o_mix_fecha_laco(id_do_no: str, sink: str, monitor: str) -> bool:
    """Ligar o mix deste monitor ao nó realimentaria o próprio som? PURA.

    O «No controle e na TV» é um ``module-loopback`` do monitor da SAÍDA PADRÃO
    para o nó. Na máquina dela a saída padrão é o HDMI e o fio é inofensivo;
    numa máquina em que a saída padrão é o PRÓPRIO controle, o fio fecha um
    laço de realimentação, e não havia trava em lugar nenhum:

    * no rádio, ``hefesto_som_X.monitor → hefesto_som_X`` — a saída padrão é o
      nó (ela escolheu «Alto-falante do Controle N» nas configurações de som);
    * no cabo, ``D.monitor → hefesto_som_X → D`` — a saída padrão é a placa USB
      do controle, que o WirePlumber elege sozinho (``priority.session`` 1109,
      acima do HDMI e da placa-mãe) ou que vence quando o fone está plugado nele.

    **SÓ ESSES DOIS FECHAM CICLO**, e a trava não vai além deles: o monitor do
    nó ou da placa de OUTRO controle termina no alto-falante DESTE, sem voltar.
    Recusar ``hefesto_som_*`` ou qualquer placa de DualSense tiraria o mix de
    quem joga com a saída num controle e o som no outro.

    Inferido da leitura do código, não medido na orelha — a mesa dela não
    reproduz o caso, porque a saída padrão lá é o HDMI.
    """
    if not monitor:
        return False
    if id_do_no and monitor == f"{id_do_no}.monitor":
        return True
    return bool(sink) and monitor == f"{sink}.monitor"


_LACO_AVISADO: dict[str, str] = {}


def _mix_sem_laco(uniq: str, sink: str, monitor: str) -> str:
    """O monitor do mix, ou ``""`` quando ele fecharia laço com este nó."""
    chave = so_hex(str(uniq)) or str(uniq)
    if not o_mix_fecha_laco(nome_do_sink(uniq), sink, monitor):
        _LACO_AVISADO.pop(chave, None)
        return monitor
    if _LACO_AVISADO.get(chave) != monitor:
        _LACO_AVISADO[chave] = monitor
        logger.info(
            "som_mix_recusado_por_laco", uniq=uniq, monitor=monitor, sink=sink or None
        )
    return ""


def rota_do_no(
    uniq: str,
    transporte: str = TRANSPORTE_CABO,
    uniqs_na_mesa: Sequence[str] = (),
    *,
    fonte: str = FONTE_PADRAO,
    ponte_do_radio: Callable[[], bool] | None = None,
    runner: Callable[[list[str]], str | None] | None = None,
) -> RotaDoNo:
    """Onde este nó entrega o áudio — ou a frase de por que ele não entrega."""
    fonte = fonte if fonte in (FONTE_MIX, FONTE_SFX) else FONTE_PADRAO
    monitor = (
        monitor_da_saida_padrao(runner=runner) if fonte == FONTE_MIX else ""
    )
    if not uniq:
        return RotaDoNo(False, motivo=MOTIVO_NO_SEM_ASSENTO, fonte=fonte)
    if e_radio(transporte):
        if ponte_do_radio is not None and ponte_do_radio():
            return RotaDoNo(
                True,
                por_onde=POR_RADIO,
                fonte=fonte,
                monitor_do_mix=_mix_sem_laco(uniq, "", monitor),
            )
        motivo = (
            MOTIVO_NO_SEM_PONTE_NO_RADIO
            if a_ponte_do_radio_sabe_montar()
            else MOTIVO_NO_SEM_SABER_MONTAR
        )
        return RotaDoNo(False, motivo=motivo, fonte=fonte)
    alvo = sink_do_controle(uniq, uniqs_na_mesa, runner=runner)
    if not alvo:
        return RotaDoNo(False, motivo=MOTIVO_NO_SEM_PLACA_NO_CABO, fonte=fonte)
    return RotaDoNo(
        True,
        sink=alvo,
        por_onde=POR_CABO,
        fonte=fonte,
        monitor_do_mix=_mix_sem_laco(uniq, alvo, monitor),
    )


def argv_para_ligar_o_no(id_do_no: str, sink: str) -> tuple[str, ...]:
    """O comando que leva o que entrar no nó até o alto-falante do controle."""
    return (
        "pactl",
        "load-module",
        "module-loopback",
        f"source={id_do_no}.monitor",
        f"sink={sink}",
        f"channel_map={CANAIS_DO_ALTO_FALANTE}",
    )


def argv_para_ligar_o_mix(id_do_no: str, monitor: str) -> tuple[str, ...]:
    """O comando que faz o mix inteiro do PC cair TAMBÉM neste controle."""
    return (
        "pactl",
        "load-module",
        "module-loopback",
        f"source={monitor}",
        f"sink={id_do_no}",
    )


def argv_das_rotas(id_do_no: str, rota: RotaDoNo) -> tuple[tuple[str, ...], ...]:
    """Os ``module-loopback`` desta rota, na ordem em que sobem — () se não há."""
    if not id_do_no or not rota.tem_rota:
        return ()
    comandos: list[tuple[str, ...]] = []
    if rota.sink:
        comandos.append(argv_para_ligar_o_no(id_do_no, rota.sink))
    if (
        rota.fonte == FONTE_MIX
        and rota.monitor_do_mix
        and not o_mix_fecha_laco(id_do_no, rota.sink, rota.monitor_do_mix)
    ):
        comandos.append(argv_para_ligar_o_mix(id_do_no, rota.monitor_do_mix))
    return tuple(comandos)


def descricao_do_alto_falante(uniq: str) -> str:
    """«Alto-falante do Controle N (DualSense Wireless Controller)», sem o endereço dela.

    A forma — com o sufixo da Sony desde 23/09/2026 — é de
    :func:`rotulo_do_alto_falante`; aqui só se resolve o assento.

    Gêmea de ``dualsense_bt_audio.descricao_do_microfone``, e o gêmeo não é
    coincidência: o assento vem do MESMO numerador
    (``dualsense_bt_audio.numero_do_assento``), instalado por gancho pelo
    subsystem que estiver de pé. Escrever um segundo numerador aqui poria o
    mesmo controle no assento 2 na lista de entrada e no 3 na de saída.

    **Sem número não se inventa número.** Uma lista com dois «Alto-falante do
    Controle 1» mente sobre qual é qual; uma com dois «Alto-falante do
    Controle» só diz que o assento ainda não é sabido.

    **ISTO RESPONDE «AGORA», E O NÓ GUARDA «QUANDO NASCEU»** — e confundir as
    duas coisas foi o defeito que ela ouviu em 20/09/2026, em teste cego: o
    «Alto-falante do Controle 3» saía no Player 1. O ``device.description`` de
    um ``module-null-sink`` é fixado no ``load-module`` e **não se reescreve**
    (não há ``update-sink-proplist`` no ``pactl`` do PipeWire — medido). Quem
    mantém o rótulo do nó VIVO igual ao que esta função responde é
    ``daemon/subsystems/alto_falante.GerenciadorDeNosDeSom._o_rotulo_envelheceu``,
    que republica o nó; a regra de quando isso vale está em
    ``dualsense_bt_audio.rotulo_envelheceu``.
    """
    from hefesto_dualsense4unix.integrations.dualsense_bt_audio import (
        numero_do_assento,
    )

    numero = numero_do_assento(str(uniq or ""))
    return rotulo_do_alto_falante(numero)


def rotulo_do_alto_falante(numero: int | None) -> str:
    """A FORMA A — «Alto-falante do Controle N (DualSense Wireless Controller)».

    **Decisão dela de 23/09/2026** (A-FORJA-VALIDA-O-SOM-01, E6): o nome dela
    fica na frente, e o sufixo é o ``iProduct`` da Sony, a string que um jogo
    procura. Sob Proton esta string É o nome do endpoint
    (``winepulse.drv/pulse.c``, ``get_device_name``); sem o sufixo o nó existe e
    jogo nenhum o reconhece. A mesma forma vale para o microfone
    (``dualsense_bt_audio.descricao_do_microfone``), os quatro controles, o
    cabo e o BT.

    UM DONO da grafia: quem nomeia o nó é :func:`descricao_do_alto_falante`
    (o daemon, pelo ``uniq``). O segundo caminho, o da janela pelo assento
    (``app/audio_saida.nome_do_alto_falante``), saiu em 28/09/2026 com o plano
    que ninguém executava; duas grafias seriam dois nomes para o mesmo nó.

    ``None``, ``bool`` e número que não seja positivo valem como *"não sei o
    assento"*: sem número não se inventa número.
    """
    from hefesto_dualsense4unix.integrations.vestido_de_dualsense import (
        com_o_nome_da_sony,
    )

    base = NOME_DO_ALTO_FALANTE_DO_CONTROLE
    if isinstance(numero, int) and not isinstance(numero, bool) and numero > 0:
        base = f"{base} {numero}"
    return com_o_nome_da_sony(base)


if TYPE_CHECKING:
    from hefesto_dualsense4unix.integrations.dualsense_bt_audio import RecuoDoPactl

_SONDAGEM = ("pactl", "info")


def _o_recuo() -> RecuoDoPactl:
    """O recuo do SERVIDOR de som — o MESMO objeto do microfone, lido na hora."""
    from hefesto_dualsense4unix.integrations import dualsense_bt_audio

    return dualsense_bt_audio.PACTL


def _e_pactl(argv: Sequence[str]) -> bool:
    """O recuo é do servidor de som: só o ``pactl`` entra nele."""
    return bool(argv) and argv[0] == "pactl"


def _anotar_o_prazo(argv: Sequence[str], exc: BaseException) -> None:
    """O `_rodar` viu uma exceção: se foi o PRAZO de um `pactl`, o recuo fica sabendo."""
    if _e_pactl(argv) and isinstance(exc, subprocess.TimeoutExpired):
        _o_recuo().estourou()


def _anotar_a_resposta(argv: Sequence[str]) -> None:
    """Um `pactl` saiu com rc=0: o servidor atende, e o recuo acaba."""
    if _e_pactl(argv):
        _o_recuo().respondeu()


def _com_o_recuo(
    runner: Callable[[list[str]], str | None],
) -> Callable[[list[str]], str | None]:
    """O `runner` de um nó, contando ao recuo do servidor o que houve com cada pergunta."""

    def _perguntar(argv: list[str]) -> str | None:
        return _o_recuo().perguntar(runner, argv)

    return _perguntar


def _o_servidor_atende(runner: Callable[[list[str]], str | None], nome: str) -> bool:
    """Pode sair um `load-module` agora? O mesmo desenho do microfone."""
    if shutil.which("pactl") is None:
        logger.info("som_sem_pactl")
        return False
    recuo = _o_recuo()
    if recuo.mudo():
        logger.debug("som_pactl_mudo_nao_carrego", sink=nome, espera_s=recuo.espera_s)
        return False
    if recuo.espera_s > 0 and runner(list(_SONDAGEM)) is None:
        logger.debug("som_sondagem_sem_resposta", sink=nome, espera_s=recuo.espera_s)
        return False
    return True


def _enquanto_o_servidor_atende(
    comandos: Iterable[tuple[str, ...]],
) -> Iterator[tuple[str, ...]]:
    """Os comandos da rota, um a um, até um prazo estourado pôr o servidor em recuo."""
    for argv in comandos:
        if _o_recuo().mudo():
            logger.debug("som_rota_espera_o_pactl", argv=" ".join(argv))
            return
        yield argv


__all__ = [
    "AMOSTRAS_POR_QUADRO",
    "ARRANJOS",
    "ARRANJO_035",
    "ARRANJO_COMMON_PRIMEIRO",
    "ARRANJO_DS5DONGLE",
    "ARRANJO_PADRAO",
    "ARRANJO_POR_NOME",
    "ARRANJO_SENSHI",
    "BITRATE_DO_ENCODER",
    "BLOCO_FONE",
    "BUFFER_QUE_TOCOU",
    "BYTES_DE_PCM_POR_QUADRO",
    "BYTES_POR_QUADRO_OPUS",
    "CANAIS_DO_ALTO_FALANTE",
    "CANAIS_DO_ENCODER",
    "CRC_BYTES",
    "DEGRAU_COMBINADO",
    "DEGRAU_DO_KERNEL",
    "ENABLES_COM_MIC",
    "ENABLES_SEM_MIC",
    "ENVELOPE_BYTES",
    "FILA_CHEIA_DO_KERNEL",
    "FONTE_MIX",
    "FONTE_PADRAO",
    "FONTE_SFX",
    "GRAVADORES_DO_MONITOR",
    "HEX_DO_SUFIXO",
    "INTERVALO_DE_ENVIO_035",
    "JANELA_DO_SINAL_S",
    "LATENCIA_DO_GRAVADOR_MS",
    "MOTIVO_FILA_PARADA",
    "MOTIVO_NO_SEM_ASSENTO",
    "MOTIVO_NO_SEM_PLACA_NO_CABO",
    "MOTIVO_NO_SEM_PONTE_NO_RADIO",
    "MOTIVO_NO_SEM_SABER_MONTAR",
    "MS_POR_QUADRO",
    "NOME_DO_ALTO_FALANTE_DO_CONTROLE",
    "OFFSET_APOS_O_COMMON",
    "OFFSET_DO_COMMON",
    "ORCAMENTO_DO_DEGRAU",
    "OUVIDO",
    "POR_CABO",
    "POR_RADIO",
    "PREFIXO_SINK_DO_SOM",
    "PRIORIDADE_SESSAO_DO_SOM",
    "RECUO_PROIBIDO_DO_OUVIDO",
    "SURDO_S",
    "TAMANHO_DO_DEGRAU",
    "TAXA_DA_FONTE_DO_SOM",
    "TAXA_DA_FONTE_POR_PAPEL",
    "TAXA_DO_ENCODER",
    "TAXA_DO_OUVIDO_DA_PLACA",
    "TETO_DE_CEDER_S",
    "TRANSPORTE_CABO",
    "TRANSPORTE_RADIO",
    "VOLTA_DA_SEQUENCIA",
    "VOLUME_QUE_ELA_OUVIU",
    "Arranjo",
    "BombaDeSomPeloRadio",
    "CodificadorOpus",
    "ContagemDaBomba",
    "Diagnostico",
    "OuvidoDaPlaca",
    "OuvidoDosNos",
    "PonteDeSomPorRadio",
    "RelatorioCombinado",
    "RotaDoNo",
    "SinkVirtualPipeWire",
    "a_ponte_do_radio_pode_subir",
    "a_ponte_do_radio_sabe_montar",
    "argv_das_rotas",
    "argv_do_gravador",
    "argv_para_ligar_o_mix",
    "argv_para_ligar_o_no",
    "assinatura_da_rota",
    "common_de_audio",
    "conferir_o_alvo_do_gravador",
    "controle_de_audio_035",
    "descricao_do_alto_falante",
    "diagnosticar",
    "e_radio",
    "escritor_de_hidraw",
    "fonte_com_ritmo",
    "fonte_de_arquivo",
    "fonte_do_monitor_do_no",
    "fonte_que_ouve",
    "ha_gravador_de_monitor",
    "monitor_da_saida_padrao",
    "montar_com_o_common_preservado",
    "montar_relatorio_combinado",
    "nome_do_sink",
    "o_mix_fecha_laco",
    "o_servidor_e_o_pipewire",
    "orcamento_do_degrau",
    "propriedades_do_sink",
    "rodar_pactl",
    "rota_do_no",
    "rotulo_do_alto_falante",
    "rotulo_do_gravador",
    "serial_do_no",
    "sink_do_controle",
    "so_hex",
    "sufixo_do_sink_do_som",
    "tag_tlv",
    "taxa_da_fonte",
    "tem_sinal_no_pcm",
    "versao_libopus",
]
