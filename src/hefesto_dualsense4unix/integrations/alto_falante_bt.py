"""O motor do alto-falante virtual — o encoder, o sink e os DOIS arranjos.

SOM-QUE-SAI-01, rota corrigida em 06/09/2026. Espelho de saída do
:mod:`integrations.dualsense_bt_audio`, que é a metade de ENTRADA e **não é
tocada por este módulo** — ele importa dela, nunca a edita.

A FRASE QUE ESTE ARQUIVO NÃO PODE ESCREVER
-------------------------------------------
O mapa de canais proíbe, com todas as letras
(``audio.saida_dedicada.payload_do_degrau@dualsense``.radio_ressalva):

    *"NÃO ESCREVER, EM LUGAR NENHUM, que 'descobrimos o áudio por Bluetooth'
    ou que a ponte funciona. Não funciona, e não há ponte: há um canal que
    responde. FALÁCIA DO CANAL QUE RESPONDE — concluir que, porque um canal
    responde, ele FAZ o que a gente esperava dele."*

O honesto, hoje e até o ensaio de bancada rodar, é o par:
**o canal responde, e o conteúdo vai pelos DOIS arranjos candidatos.**
Nada neste módulo afirma que som saiu de aparelho nenhum, porque ninguém
desta casa mandou um byte de áudio por rádio.

O QUE FALTAVA, E ERA NOMEADO PELO PRÓPRIO MAPA
-----------------------------------------------
``audio.alto_falante@dualsense``.radio_codigo_ref listava três dívidas com
endereço, e são exatamente as três peças deste arquivo:

1. **o ENCODER** — ``dualsense_bt_audio.py`` prototipa só o decodificador;
   ``opus_encoder_create`` e ``opus_encode`` não apareciam em linha nenhuma
   de ``src/``. Ver :class:`CodificadorOpus`;
2. **o SINK** — a ponte de entrada publica uma SOURCE de captura
   (``module-pipe-source``) e não existia caminho de SAÍDA nenhum. Ver
   :class:`SinkVirtualPipeWire`;
3. **o ARRANJO** do corpo do ``0x39``, sobre o qual as duas fontes publicadas
   DIVERGEM. Ver :data:`ARRANJOS`, e leia o parágrafo abaixo antes de
   escolher um.

OS DOIS ARRANJOS, E POR QUE ESTE MÓDULO NÃO ESCOLHE
----------------------------------------------------
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
arranjo. Escolher um aqui seria inventar o caminho. O módulo monta os dois a
partir do MESMO PCM, e quem escolhe é o ensaio de bancada com a orelha dela
(ensaio 1 da MESA-DE-QUATRO-01; `scripts/ensaios/o_som_que_sai.py` monta os
dois lado a lado).

AS TRÊS RESSALVAS QUE VIAJAM COM O ACHADO
------------------------------------------
Do mapa, ``audio.alto_falante@dualsense``.radio_ressalva, e nenhuma é enfeite:

(a) **o alto-falante interno é MONO**, medido em 16/08/2026 no ensaio
    ``sfx-tres-saidas-quatro-canais``: canal 0 → fone L, canal 1 → fone R ou
    alto-falante interno sem fone, canais 2 e 3 → nada. O encoder do
    DS5Dongle é ESTÉREO (``opus_encoder_create(48000, 2, …)``), e o estéreo
    casa com a rota de FONE (tag ``0x16``), não com o alto-falante interno
    (tag ``0x13``). Por isso :data:`CANAIS_DO_ENCODER` é 2 **e a tag é
    argumento**: os 200 bytes por quadro são o que o formato exige; qual
    saída os recebe é outra pergunta, e ela é do ensaio;
(b) **o byte [2] tem três leituras** — o DS5Dongle o lê como tag TLV
    ``0x11|0x80`` (= 0x91), e ``plataforma.escada_de_output@dualsense`` mediu
    o ``common`` de 47 B obedecendo em [3..49] com ``report[2] = 0x10``, SEM
    o bit 7. A disputa continua aberta, e este módulo não a resolve: ele
    monta a gramática TLV dos dois arranjos e deixa o ``common`` fora dela;
(c) **o DS5Dongle é um DONGLE** — fala L2CAP direto e nunca toca
    ``/dev/hidraw``. Ele prova "report HID de saída", não "hidraw".

O QUE ESTE MÓDULO **NÃO** FAZ, E TEM DONO
------------------------------------------
* **não escreve no aparelho.** Ele MONTA bytes; quem escreve é o ensaio, com
  a bancada reservada e o MAC conferido;
* **não mexe em rota, volume nem pré-amplificador** — isso é de
  ``core/backend_pydualsense.py`` e de ``app/audio_saida.py``, e o segundo
  está em ``nao_toca:`` desta sprint. O nó virtual é **por onde o áudio
  entra**; o que o firmware faz com ele depois tem dono, e não é este;
* **não escolhe o degrau para regime.** ``0x32`` a ~100 Hz contra ``0x39`` a
  ~15 Hz é latência contra fôlego, e a decisão dela
  (``D-0609-O-NO-DE-SOM-VIVE-COM-O-CONTROLE``) é explícita: *só depois do
  D5*, com o número de banda na mesa. :func:`degrau_para_payload` existe para
  o tamanho, não para o regime.
"""

from __future__ import annotations

import contextlib
import ctypes
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
    BLOCO_SPEAKER,
    MIC_TAXA_HZ,
    OpusIndisponivelError,
)
from hefesto_dualsense4unix.integrations.fontes_de_captura import so_hex
from hefesto_dualsense4unix.integrations.storm_doctor import gesto_de_instalar
from hefesto_dualsense4unix.utils.logging_config import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# A escada de output por rádio — uma TABELA, e nunca aritmética
# ---------------------------------------------------------------------------

#: Tamanho TOTAL do report (com o byte de id em [0]) de cada degrau da escada
#: de output por Bluetooth.
#:
#: LIDO DO DESCRITOR do aparelho dela em 11/08/2026, e com testemunha externa
#: desde 31/08: a suíte de regressão do kernel (bentiss/hid-tools,
#: ``hidtools/device/sony_gamepad.py:1733-1770``) declara os mesmos nove
#: números. Ver ``audio.alto_falante@dualsense``.radio_evidencia.
#:
#: **A ESCADA NÃO É UNIFORME, e é aqui que a aritmética mata.** São oito
#: passos de +64 e **um último de +21**. Quem escrever
#: ``78 + 64 * (id - 0x31)`` — que é a fórmula que a palavra "escada" convida
#: a escrever — obtém **590 bytes para o 0x39, contra os 547 declarados**.
#: O report sai 43 bytes maior, o CRC-32 cai fora do lugar, e o firmware
#: descarta CALADO: sem erro, sem log, sem retorno. *"Não faz nada e não
#: reclama"* é o sintoma mais caro de depurar desta casa, e ele é
#: indistinguível de *"o protocolo está errado"*.
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

#: O ``0x31`` é do KERNEL — ele é o único degrau que declara Output E Input
#: (``0x91,0x02`` seguido de ``0x81,0x02``), e é por ele que o
#: ``hid-playstation`` fala. A disciplina do nibble de sequência da metade de
#: entrada é estrutural pela mesma razão: nós usamos OUTRO id. E a saída
#: escreve MUITO mais que a entrada, então a razão vale ainda mais aqui.
DEGRAU_DO_KERNEL = 0x31

#: Os três bytes de envelope: [0] id, [1] seq<<4, [2] seletor de bloco.
ENVELOPE_BYTES = 3

#: O CRC-32 mora nos QUATRO ÚLTIMOS bytes do report, seja ele de 78 ou de 547.
CRC_BYTES = 4

#: Onde o ``common`` de 47 bytes mora quando ele está presente: [3..49].
#: MEDIDO em 15/08/2026 (``plataforma.escada_de_output@dualsense``): o mesmo
#: ``common`` mandado por 0x31, 0x32 e 0x39 acendeu a cor pedida na lightbar,
#: com o olho dela, por rádio. É a única parte do corpo do degrau que esta
#: casa mediu.
OFFSET_DO_COMMON = 3

#: Onde o áudio começa quando o ``common`` de 47 B é PRESERVADO: logo depois
#: dele. Derivado, nunca digitado — ver :func:`montar_com_o_common_preservado`.
OFFSET_APOS_O_COMMON = OFFSET_DO_COMMON + COMMON_LEN


def orcamento_do_degrau(degrau: int) -> int:
    """Quantos bytes de payload cabem NESTE degrau depois do ``common``.

    Total menos os 3 de envelope, os 47 do ``common`` e os 4 do CRC. Dá 24 no
    ``0x31``, 88 no ``0x32`` e **493** no ``0x39``.

    Levanta ``KeyError`` para degrau que não existe — de propósito. Um degrau
    inventado devolvendo um número plausível é como se monta um report que o
    firmware descarta em silêncio.
    """
    return TAMANHO_DO_DEGRAU[degrau] - ENVELOPE_BYTES - COMMON_LEN - CRC_BYTES


#: O orçamento de cada degrau, derivado da tabela — nunca digitado à mão.
ORCAMENTO_DO_DEGRAU: dict[int, int] = {
    degrau: orcamento_do_degrau(degrau) for degrau in TAMANHO_DO_DEGRAU
}


def degrau_para_payload(bytes_de_payload: int) -> int | None:
    """O MENOR degrau cujo orçamento comporta este payload. None se não cabe.

    A regra é de TABELA, e a leitura é ordenada pelo id. O ``0x31`` fica fora
    dos candidatos porque ele é do kernel (:data:`DEGRAU_DO_KERNEL`).

    **A mordida desta função:** peça 89 bytes e ela tem de devolver ``0x33``.
    Se devolver ``0x32`` (88 B de orçamento) o CRC cai fora do lugar e o
    firmware descarta calado.
    """
    if bytes_de_payload < 0:
        return None
    for degrau in sorted(TAMANHO_DO_DEGRAU):
        if degrau == DEGRAU_DO_KERNEL:
            continue
        if ORCAMENTO_DO_DEGRAU[degrau] >= bytes_de_payload:
            return degrau
    return None


# ---------------------------------------------------------------------------
# O codificador Opus — o mesmo .so, o mesmo ctypes, zero pacote novo
# ---------------------------------------------------------------------------

#: MEDIDO nesta árvore em 06/09/2026: a ``libopus 1.4`` do sistema exporta
#: ``opus_encoder_create``, ``opus_encode``, ``opus_encoder_ctl`` e
#: ``opus_encoder_destroy``. O codificador é o MESMO ``.so`` que o
#: decodificador da metade de entrada já usa — nenhuma dependência nova.
_SONAMES_OPUS = ("libopus.so.0", "libopus.so")

#: ``opus_defines.h``. ``AUDIO`` (e não ``VOIP``) porque o que passa por aqui
#: é som de jogo, não voz — o encoder da entrada é problema do firmware, este
#: é nosso.
OPUS_APPLICATION_AUDIO = 2049
OPUS_SET_BITRATE_REQUEST = 4002
OPUS_SET_VBR_REQUEST = 4006
OPUS_OK = 0

#: 48 kHz, o mesmo da metade de entrada (``MIC_TAXA_HZ``) e o que a referência
#: canônica descreve da porta dedicada do PS5.
TAXA_DO_ENCODER = MIC_TAXA_HZ

#: DOIS canais, e não é detalhe. A rota do firmware é POR CANAL:
#: ``OUTPUT_PATH_SEL`` tem o valor 2 = *"L → fone, R → alto-falante"*, o caso
#: que ela descreveu (som do jogo no fone, efeito no alto-falante), e a rota 2
#: obedeceu em 15/08/2026 (ensaio ``sfx-rota2-sem-fone``, com a orelha dela).
#: **Com um nó mono esse caso é inexprimível.** Ver a ressalva (a) do
#: cabeçalho: o alto-falante INTERNO é mono e come o canal R; quem é estéreo é
#: a rota de fone.
CANAIS_DO_ENCODER = 2

#: Quadro de 10 ms, igual ao da entrada: 480 amostras a 48 kHz.
AMOSTRAS_POR_QUADRO = 480

#: PCM de um quadro: 480 x 2 canais x 2 bytes = 1920 bytes.
BYTES_DE_PCM_POR_QUADRO = AMOSTRAS_POR_QUADRO * CANAIS_DO_ENCODER * 2

#: **160 kbps em CBR, e o número não é gosto: ele é o que fecha a conta.**
#: 160000 bits/s x 10 ms / 8 = **exatamente 200 bytes**, que é o ``len`` que
#: as DUAS fontes declaram para o bloco de áudio do ``0x39``. É a mesma
#: configuração lida no DS5Dongle (``src/audio.cpp:473-481``: estéreo, quadro
#: de 10 ms, CBR 160 kbps). Trocar por VBR faria o quadro variar de tamanho e
#: o bloco de 200 bytes deixaria de fechar — o formato é de tamanho fixo.
BITRATE_DO_ENCODER = 160000

#: O tamanho do quadro Opus que os dois arranjos exigem.
BYTES_POR_QUADRO_OPUS = 200

_LIB_OPUS_ENC: ctypes.CDLL | None = None
_LOCK_OPUS_ENC = threading.Lock()


def _carregar_libopus_encoder() -> ctypes.CDLL:
    """Carrega e prototipa os símbolos de ENCODER da libopus, uma vez.

    **Handle próprio, e de propósito.** ``dualsense_bt_audio._carregar_libopus``
    prototipa só o decodificador, e aquele módulo está fora da posse desta
    sprint. Um ``ctypes.CDLL`` novo é outro objeto Python sobre a MESMA ``.so``
    já mapeada pelo processo: os ``argtypes`` moram no objeto, então nenhum
    dos dois escreve por cima do outro. É o mesmo cuidado que o lock daquele
    módulo documenta, do outro lado.
    """
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
        # `opus_encoder_ctl` é VARIÁDICA: prototipar `argtypes` aqui obrigaria
        # uma assinatura por request, então só o retorno é fixado.
        #
        # A FRASE QUE ESTAVA AQUI ERA FALSA, E ELA MATAVA O DAEMON — medido em
        # 10/09/2026. Ela dizia *"ctypes já passa int como int no ABI desta
        # plataforma"*. **Sem `argtypes`, ctypes passa um `int` do Python como
        # C `int` de 32 BITS** — e `opus_encoder_create` devolve um `c_void_p`,
        # que chega ao Python como um `int` de 64.
        #
        # Na thread PRINCIPAL isso passa por sorte: o heap do `brk` fica abaixo
        # de 4 GB e a truncagem não perde byte nenhum. **Numa thread de
        # trabalho, não**: o glibc aloca numa arena própria, acima de 4 GB.
        # Medido nesta máquina::
        #
        #     thread principal  0x00001ac2da40 -> 0x1ac2da40   (cabe)
        #     thread de trabalho 0x706a50000ba0 -> 0x50000ba0   (PERDE)
        #
        # O ponteiro morto chega em C e o processo INTEIRO cai com
        # `Segmentation fault`. Ninguém tinha visto porque, até 10/09, todo
        # `CodificadorOpus` desta casa nascia na thread principal — a
        # `PonteDeSomPorRadio` é a primeira a construí-lo dentro de uma thread.
        #
        # A cura é envelopar o ponteiro em `ctypes.c_void_p` em TODA chamada
        # variádica; ver `CodificadorOpus._ctl`. Régua:
        # `tests/unit/test_o_ponteiro_do_opus_atravessa_a_thread.py`.
        lib.opus_encoder_ctl.restype = ctypes.c_int
        _LIB_OPUS_ENC = lib
        return lib


class CodificadorOpus:
    """PCM ``s16le`` de 10 ms → um quadro Opus de tamanho FIXO.

    Levanta :class:`OpusIndisponivelError` na construção quando a ``libopus``
    não está no sistema (o mesmo contrato do decodificador da entrada): quem
    chama trata isso como *"o nó não sobe"*, nunca como exceção a propagar
    para a interface.

    **O tamanho fixo é o contrato, e é ele que faz o bloco de 200 bytes
    fechar.** Ver :data:`BITRATE_DO_ENCODER`.
    """

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
        # CBR: `OPUS_SET_VBR(0)` ANTES do bitrate. Com VBR ligado o quadro
        # varia de tamanho e o bloco de 200 bytes deixa de fechar.
        self._ctl(OPUS_SET_VBR_REQUEST, 0)
        self._ctl(OPUS_SET_BITRATE_REQUEST, bitrate_bps)
        self._saida = ctypes.create_string_buffer(4000)

    def _ctl(self, request: int, valor: int) -> int:
        """`opus_encoder_ctl` com o ponteiro ENVELOPADO — dono único da chamada.

        **O envelope é a cura, não estilo.** `opus_encoder_ctl` é variádica e
        não tem `argtypes`; sem `ctypes.c_void_p` em volta, o ponteiro do
        encoder vai como C `int` de 32 bits e perde os bytes altos quando o
        glibc aloca acima de 4 GB — que é o que acontece em toda thread de
        trabalho. O processo cai com `Segmentation fault`.

        Ter UM lugar que faz esta chamada é o que impede a próxima pessoa de
        acrescentar um `ctl` cru e reintroduzir a falha em silêncio.
        """
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
        """Um quadro de PCM → um quadro Opus. None quando a libopus recusa.

        Recusa também PCM de tamanho errado, e isso é a cura de um modo de
        falha real: ``opus_encode`` recebe o número de AMOSTRAS, não de bytes,
        e passar um buffer curto com a contagem certa faria a libopus ler
        memória fora do buffer. O tamanho é conferido aqui, uma vez, em vez de
        confiar em quem chama.
        """
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


# ---------------------------------------------------------------------------
# Os DOIS arranjos do corpo do 0x39 — registrados, não escolhidos
# ---------------------------------------------------------------------------

#: Tag TLV do bloco de FONE. O bloco de alto-falante interno (``0x13``) já
#: tinha nome em ``dualsense_bt_audio.BLOCO_SPEAKER``, declarado desde 25/07 e
#: **sem um único caminho de escrita** — este módulo é o primeiro. O do fone
#: nasce aqui porque a ressalva (a) o exige: o encoder estéreo casa com esta
#: tag, não com a do alto-falante interno.
BLOCO_FONE = 0x16


def tag_tlv(tag: int, *, duplo: bool = False) -> int:
    """O byte de tag da cadeia TLV: ``tag | presente [| duplo]``.

    ``BLOCO_PRESENTE`` (bit 7) e ``BLOCO_DUPLO`` (bit 6) vêm da metade de
    ENTRADA — dono único, nunca redigitados. Confere com o que o mapa registra
    do Senshi: o bloco háptico dele é ``0xD2|0x40``, e ``0x12 | 0x80 | 0x40``
    é exatamente ``0xD2``.
    """
    valor = tag | BLOCO_PRESENTE
    if duplo:
        valor |= BLOCO_DUPLO
    return valor


@dataclass(frozen=True)
class Arranjo:
    """Um dos dois candidatos ao corpo do ``0x39``, com a procedência colada.

    Os offsets são LEITURA DE FONTE EXTERNA, não medição desta bancada — é o
    que ``de_onde_sei`` diz, e ele viaja com o objeto para que nenhum relatório
    possa citar um destes números sem citar de onde ele veio.
    """

    nome: str
    fonte: str
    degrau: int
    #: [n] da tag do bloco AudioControl e o ``len`` que a fonte declara.
    pos_tag_controle: int
    len_controle: int
    #: [n] da tag do bloco de áudio, o ``len`` de cada quadro e onde eles vão.
    pos_tag_audio: int
    len_audio: int
    pos_audio: int
    quadros_de_audio: int
    #: [n] da tag do bloco háptico e onde os dois sub-blocos de 64 B vão.
    pos_tag_haptico: int
    len_haptico: int
    pos_haptico: int
    de_onde_sei: str = "leitura de fonte externa — NÃO medido nesta bancada"
    #: A cadência de ENVIO **medida**, em segundos. `None` = ninguém mediu, e o
    #: chamador cai no nominal (:attr:`quadros_de_audio` x 10 ms). Ela existe
    #: porque o nominal ESTAVA ERRADO: o `0x35` carrega um quadro de 10 ms mas
    #: o aparelho o consome a cada **10,667 ms** (512/48000), e alimentá-lo a
    #: 10 ms daria 100 quadros/s num aparelho que come 93,75.
    intervalo_de_envio_s: float | None = None
    #: O valor do bloco de controle deste arranjo leva um CONTADOR DE QUADROS
    #: que o chamador tem de avançar (o `[10]` do `0x35`). Quando `True`,
    #: :class:`BombaDeSomPeloRadio` monta o bloco a cada report em vez de
    #: mandar o mesmo `controle` fixo — sem isso o contador ficaria em zero e o
    #: firmware perderia a conta dos quadros.
    controle_conta_quadros: bool = False
    #: O bloco háptico vai com a tag DUPLA (dois sub-blocos de
    #: :attr:`len_haptico`) ou com a simples (um bloco de :attr:`len_haptico`)?
    #: As duas fontes externas descrevem o dobro; **o que VIBROU nesta bancada
    #: em 18/09/2026 foi o simples** — tag ``0x92``, ``len`` 64, 64 bytes. Quem
    #: mede ganha o default do seu arranjo, não do campo.
    haptico_duplo: bool = True
    #: Este corpo PRESERVA o ``common`` em [3..49] e o ``[2] = 0x10``, em vez de
    #: pôr a tag do AudioControl no byte [2]. Ver
    #: :func:`montar_com_o_common_preservado` — e note que ele não é leitura de
    #: fonte externa nenhuma: é o envelope que ESTA bancada mediu.
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
        """O report inteiro, com o CRC-32 já no lugar. Levanta em vez de mentir.

        ``quadros`` são os quadros Opus, um por sub-bloco. Cada um é copiado
        para a sua janela e o resto dela fica em zero — um quadro CBR fecha
        exatos :data:`BYTES_POR_QUADRO_OPUS` bytes, e um menor é aceito com o
        resto zerado para que o ensaio possa montar report com PCM curto sem
        precisar de outro caminho de código.

        **O CRC é o do PRODUTO** (``bt_crc32``, semente ``0xA2``), nunca uma
        tabela montada à mão. E ele bate com a fonte: o DS5Dongle semeia o
        CRC dele com ``0xEADA2D49``, que é ``zlib.crc32(b"\\xa2")`` —
        conferido nesta árvore em 06/09/2026.
        """
        if len(quadros) != self.quadros_de_audio:
            raise ValueError(
                f"{self.nome} quer {self.quadros_de_audio} quadros, veio {len(quadros)}"
            )
        if self.common_preservado:
            # UM DONO SÓ para este corpo: a função é a implementação, e este
            # ramo só a chama. Uma segunda montagem aqui seria a régua paralela
            # que esta casa já pagou onze vezes.
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
        # AudioControl.
        pkt[self.pos_tag_controle] = tag_tlv(BLOCO_AUDIO_CONTROL)
        pkt[self.pos_tag_controle + 1] = self.len_controle
        valor = controle[: self.len_controle]
        pkt[self.pos_tag_controle + 2 : self.pos_tag_controle + 2 + len(valor)] = valor
        # Háptico (dois sub-blocos do tamanho declarado) — SÓ SE O ARRANJO O
        # DECLARAR. A guarda nasceu com o `ARRANJO_035` em 10/09/2026: um
        # arranjo sem háptico traz `pos_tag_haptico=0`, e escrever a tag ali
        # sobrescreveria o BYTE DE ID em [0] com `0xD2`. O report sairia com o
        # id errado, o firmware o descartaria calado, e o sintoma seria o
        # silêncio de sempre — indistinguível de payload errado.
        if self.len_haptico:
            pkt[self.pos_tag_haptico] = tag_tlv(BLOCO_HAPTICS, duplo=self.haptico_duplo)
            pkt[self.pos_tag_haptico + 1] = self.len_haptico
            quantos = 2 if self.haptico_duplo else 1
            corpo = haptico[: self.len_haptico * quantos]
            pkt[self.pos_haptico : self.pos_haptico + len(corpo)] = corpo
        # Áudio — SÓ SE O ARRANJO O DECLARAR, pela mesma razão da guarda do
        # háptico: um arranjo sem áudio traz `pos_tag_audio=0`, e escrever a
        # tag ali sobrescreveria o BYTE DE ID em [0]. O report sairia com o id
        # errado, o firmware o descartaria calado, e o sintoma seria o silêncio
        # — indistinguível de payload errado. O arranjo da háptica (0x32) é o
        # primeiro que não leva áudio nenhum.
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


#: (A) awalol/DS5Dongle@17385f8beeef17129f0b39d9e5fc2195ea89b322 —
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

#: (B) TechAntohere/Senshi@1de83a58f5ea29d12d06c2a38d4d7641090d49ff —
#: ``…/settings/DualSenseBtReportBuilder.kt:959-1014``. O MESMO id, o MESMO
#: tamanho, o MESMO CRC — e o arranjo interno ESPELHADO: o áudio vem primeiro
#: e o háptico vai para o fim. Diverge também no ``len`` do AudioControl (7,
#: contra 6). **Não é testemunha independente:** cita o DS5Dongle em ``:76``.
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

#: Os dois, na ordem em que o mapa os registra. **Registrados sem escolher** —
#: quem escolhe é a orelha dela no ensaio de bancada.
ARRANJOS: tuple[Arranjo, ...] = (ARRANJO_DS5DONGLE, ARRANJO_SENSHI)

#: (C) O TERCEIRO CORPO, e ele **não entra em** :data:`ARRANJOS` de propósito.
#: Aquela tupla é *"os candidatos de fonte externa, registrados sem escolher"*;
#: este aqui não é leitura de código alheio nenhum — é o ENVELOPE QUE ESTA
#: BANCADA MEDIU obedecendo por rádio (o `common` de 47 B por 0x32 e 0x39
#: acendendo a cor na lightbar, com o olho dela, 15/08/2026), com o Opus
#: pendurado nos 493 bytes que sobram. Misturá-lo com os outros dois apagaria
#: a diferença de procedência que este módulo inteiro existe para proteger.
#:
#: **ELE É A METADE *COM* DE UM PAR COM/SEM**, e a razão está em
#: :func:`montar_com_o_common_preservado`: as seis passadas do ensaio variaram
#: a TAG e o ARRANJO, e nenhuma variou o byte [2] — que é a única parte do
#: corpo do degrau que esta casa mediu importar.
ARRANJO_COMMON_PRIMEIRO = Arranjo(
    nome="common-preservado",
    fonte=(
        "esta bancada — plataforma.escada_de_output@dualsense, 15/08/2026: o "
        "`common` de 47 B por 0x32 e 0x39 acendeu a cor na lightbar por rádio, "
        "com o olho dela. NÃO é leitura de fonte externa."
    ),
    degrau=0x39,
    # [2] é o tag obrigatório 0x10, e NÃO uma tag de AudioControl: o valor do
    # bloco de controle viaja DENTRO do common (volume em [4..7], pré-amp em
    # [37]), que é como o 0x31 do produto já o manda.
    pos_tag_controle=2,
    len_controle=0,
    pos_tag_audio=OFFSET_APOS_O_COMMON,
    len_audio=BYTES_POR_QUADRO_OPUS,
    pos_audio=OFFSET_APOS_O_COMMON + 2,
    quadros_de_audio=2,
    # Sem bloco háptico: ele é o que os dois arranjos externos declaram, e
    # acrescentá-lo aqui introduziria uma segunda variável no par.
    pos_tag_haptico=0,
    len_haptico=0,
    pos_haptico=0,
    de_onde_sei=(
        "MEDIDO nesta bancada quanto ao envelope ([2]=0x10 e o common em "
        "[3..49]); a POSIÇÃO DO OPUS depois dele é hipótese não medida"
    ),
    common_preservado=True,
)

# ---------------------------------------------------------------------------
# (D) O ARRANJO QUE TOCA — e ele não é candidato: é o MEDIDO
# ---------------------------------------------------------------------------

#: Os SETE bytes do valor do bloco `0x11` (AudioControl) do `0x35`, em [4..10].
#: O `len_controle` do arranjo é 7 porque são estes: um de enables, cinco de
#: `audio_buffer_length`, um de contador de quadros.
BYTES_DO_CONTROLE_035 = 7

#: Os 64 bytes do bloco háptico: 32 amostras por canal, int8, estéreo, a 3 kHz.
#: O dono da CONTA que os produz é :mod:`integrations.haptica_bt`; aqui só o
#: tamanho, porque é ele que dimensiona o report.
BYTES_DO_BLOCO_HAPTICO = 64

#: Os quadros de 48 kHz que um bloco de 3 kHz consome: 512, os mesmos 10,667 ms
#: do quadro Opus. É a conta de :mod:`integrations.haptica_bt` (FATOR vezes 32).
QUADROS_POR_BLOCO_HAPTICO = 512
#: O endpoint da háptica tem QUATRO canais: 1-2 a voz, 3-4 os motores.
CANAIS_DA_HAPTICA = 4

#: O primeiro byte do bloco `0x11`: sete bits de enable. **O bit 0 é o
#: MICROFONE** — `0xFE` o deixa de fora, `0xFF` o liga junto. Medido em
#: 10/09/2026: com `0xFF` o microfone entra no mesmo report que leva o som.
ENABLES_SEM_MIC = 0xFE
ENABLES_COM_MIC = 0xFF

#: O `audio_buffer_length` que TOCOU. O outro valor que as fontes mostram
#: (`40 40 40 40 40`) não foi medido nesta bancada.
BUFFER_QUE_TOCOU = bytes((0x00, 0x00, 0x00, 0x00, 0xFF))

#: A CADÊNCIA MEDIDA, em segundos: 512 amostras a 48 kHz. **Não são 10 ms nem
#: 20 ms**, e a diferença é o defeito que segurou esta casa por nove passadas —
#: o aparelho consome 93,75 quadros/s, e 20 ms alimentam 100.
INTERVALO_DE_ENVIO_035 = 512 / 48_000


def controle_de_audio_035(
    *,
    contador_de_quadros: int,
    com_microfone: bool = False,
    buffer: bytes = BUFFER_QUE_TOCOU,
) -> bytes:
    """Os sete bytes do bloco `0x11` do `0x35`, prontos para `Arranjo.montar`.

    ``contador_de_quadros`` conta **QUADROS de áudio**, não reports — e a
    distinção não é preciosismo: um report do `0x35` leva um quadro, mas um
    arranjo de dois quadros avançaria o contador de dois em dois. Contar
    reports aqui daria a metade do valor, e o firmware perderia a conta.
    """
    if len(buffer) != 5:
        raise ValueError(f"o audio_buffer_length tem 5 bytes, veio {len(buffer)}")
    return bytes(
        (ENABLES_COM_MIC if com_microfone else ENABLES_SEM_MIC, *buffer,
         int(contador_de_quadros) & 0xFF)
    )


#: (D) **O ARRANJO QUE FEZ O SOM SAIR** — 10/09/2026, na bancada dela: setenta
#: segundos contínuos pelo alto-falante do DualSense, por rádio, sem um corte, e
#: com a mordida do CRC provando que o som veio deste report.
#:
#: **ELE NÃO ENTRA EM** :data:`ARRANJOS`, e a razão é a mesma do
#: `common-preservado`: aquela tupla é *"os candidatos de fonte externa,
#: registrados sem escolher"*. Este aqui não é candidato — **é o medido**, e
#: misturá-lo apagaria a diferença de procedência que este módulo protege.
#:
#: **AS DUAS FONTES EXTERNAS ESTAVAM AS DUAS ERRADAS.** O DS5Dongle e o Senshi
#: descrevem o `0x39` de 547 B com DOIS quadros; o que toca é o `0x35` de 334 B
#: com UM. As nove passadas de áudio desta casa bateram todas no `0x39`.
#:
#: **O layout encaixa no** :class:`Arranjo` **genérico sem exceção nenhuma:**
#: `pos_tag_controle=2` põe a tag em [2], o `len` 7 em [3] e os sete bytes do
#: valor em [4..10] — que são exatamente enables, `audio_buffer_length` e o
#: contador de quadros. A tag de áudio cai em [11], o `len` 200 em [12] e o
#: quadro em [13..212]. Nada é caso especial.
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
    # SEM bloco háptico. `Arranjo.montar` tem guarda para isto desde 10/09 —
    # sem ela, `pos_tag_haptico=0` sobrescreveria o byte de id.
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

#: Os três por nome — é este dicionário que o ensaio consulta em `--arranjo`.
#: O terceiro entra AQUI e não em :data:`ARRANJOS` para que `--arranjo
#: common-preservado` exista sem que `montar_pelos_dois_arranjos` deixe de ser
#: sobre os dois.
#: (E) **O ARRANJO QUE FEZ O MOTOR VIBRAR PELO RÁDIO** — 18/09/2026, com a mão
#: dela: primeiro com senoide, depois com o PCM do PRAGMATA saindo do endpoint
#: de 4 canais ("se eu atirei x vezes vibrou x vezes", 2161 reports, zero
#: recusas).
#:
#: **ELE NÃO ENTRA EM** :data:`ARRANJOS` pela mesma razão do `0x35`: aquela
#: tupla guarda os candidatos de fonte externa registrados sem escolher. Este é
#: o medido.
#:
#: O layout, byte a byte: ``[0]`` id `0x32`, ``[1]`` seq<<4, ``[2]`` tag `0x91`
#: com ``len`` 7 e os sete bytes do AudioControl em [4..10], ``[11]`` tag
#: `0x92` com ``len`` 64 e o bloco em [13..76], CRC-32 nos quatro últimos.
#:
#: **SEM O BLOCO `0x91` NÃO VIBRA** — medido na mesma bancada, e é por isso que
#: o arranjo declara o controle. E o bloco háptico é o SIMPLES (64 bytes), não
#: o dobrado que as duas fontes externas descrevem.
#:
#: **ELE NÃO LEVA ÁUDIO, e isso é uma limitação declarada:** pôr voz e vibração
#: no MESMO report do rádio é coisa que esta casa ainda não mediu. Pelo cabo os
#: dois viajam juntos (é um stream de quatro canais); pelo rádio, enquanto
#: ninguém medir, o escritor manda um ou outro.
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


ARRANJO_POR_NOME: dict[str, Arranjo] = {
    a.nome: a for a in (*ARRANJOS, ARRANJO_COMMON_PRIMEIRO, ARRANJO_035)
}

#: **O ARRANJO PADRÃO DO PRODUTO desde 10/09/2026.** Quem manda som por rádio
#: sem dizer qual arranjo quer recebe o que TOCA, não um dos candidatos. Os
#: outros três continuam alcançáveis por nome, para ensaio.
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
    """O corpo do degrau com o ``[2] = 0x10`` e o ``common`` em [3..49] INTACTO.

    **NÃO É UM TERCEIRO CANDIDATO DE FONTE EXTERNA, e a diferença é o ponto
    inteiro desta função.** Os dois de :data:`ARRANJOS` são leitura de código
    alheio; este corpo é o ENVELOPE QUE ESTA BANCADA MEDIU obedecendo por
    rádio, com o Opus pendurado depois dele.

    **A VARIÁVEL QUE NINGUÉM TINHA VARIADO, medida em 08/09/2026.** As seis
    passadas do ensaio variaram a TAG (0x13/0x16) e o ARRANJO
    (ds5dongle/senshi) e não variaram o byte [2] — que é a única parte do corpo
    do degrau que esta casa mediu importar::

        0x31 do produto           : [2]=0x10   <- o ÚNICO valor medido obedecendo
        0x39 ds5dongle 0x13 e 0x16: [2]=0x91
        0x39 senshi    0x13 e 0x16: [2]=0x91

    :data:`OFFSET_DO_COMMON` diz, citando a medição de 15/08/2026, que o
    ``common`` de 47 bytes mora em [3..49] — e para ele cair ali o [2] tem de
    ser ``0x10``. Os dois arranjos escrevem a tag do AudioControl (``0x91``)
    exatamente nesse byte, **sobrescrevendo o único valor que esta bancada já
    viu o firmware aceitar**. O kernel aceita a escrita de qualquer jeito (ele
    não lê o corpo): 251 reports, zero recusa, silêncio — sintoma idêntico ao
    das seis passadas. É a ressalva (b) do mapa, aberta desde 31/08/2026.

    **ISTO NÃO PROVA NADA SOZINHO — ele é a metade COM de um par com/sem.**
    Rodado contra as passadas de ``[2] = 0x91``, é o que separa *"o arranjo
    está errado"* de *"o aparelho não faz"*. Só a orelha dela decide, e o
    ensaio (`scripts/ensaios/o_som_que_sai.py`) continua parando em ``rc=3``
    sem ``--eu-estou-ouvindo``.

    **E ELE NÃO ESCREVE NADA.** Monta bytes e devolve; quem põe no fio é a
    bomba, que nasce seca.

    O ``common`` vem de fora de propósito, e quem o monta para o ENSAIO é
    :func:`common_de_audio` — cujos offsets e bits saem todos de
    :mod:`~hefesto_dualsense4unix.core.ds_output_report`, o dono deles.

    **FATO SUBSTITUÍDO — 08/09/2026.** Esta linha dizia *"quem o monta é
    `build_bt_report`, o dono dele"*, e era falso nos dois sentidos:
    ``build_bt_report`` **envolve** um ``common`` que recebe pronto, não o
    monta, e o caminho que ela vai rodar (``BombaDeSomPeloRadio._montar``) não
    passava ``common`` nenhum — o corpo saía com **47 zeros**, medido. Ver
    :func:`common_de_audio` e :class:`BombaDeSomPeloRadio`.
    """
    if len(common) != COMMON_LEN:
        raise ValueError(
            f"o `common` tem de ter {COMMON_LEN} B medidos, veio com {len(common)}"
        )
    tamanho = TAMANHO_DO_DEGRAU[degrau]
    cabe = orcamento_do_degrau(degrau)
    preciso = len(quadros) * len_audio + 2  # +2: a tag e o `len` do bloco
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


#: O volume de alto-falante que ela OUVIU, com a orelha dela, em 15/08/2026:
#: `speaker volume 85` = *"bep bep bep"*; `speaker volume 0` = *"mudo"*. Não é
#: escolha nossa — é o único número desta bancada com veredito de orelha.
VOLUME_QUE_ELA_OUVIU = 85


def common_de_audio(
    *,
    volume: int = VOLUME_QUE_ELA_OUVIU,
    rota: int = rep.SAIDA_SO_NO_ALTO_FALANTE,
    preamp: int = rep.SP_PREAMP_GAIN_PADRAO,
) -> bytes:
    """O ``common`` de 47 B que PEDE rota, volume e pré-amp. Para o ENSAIO.

    **POR QUE ELE EXISTE, e o defeito que ele fecha é de 08/09/2026.** O
    terceiro corpo dizia carregar *"o `common` de 47 B idêntico ao do 0x31 do
    produto em [3..49]"*, e isso valia só para a chamada DIRETA que as réguas
    fazem — elas passam o ``common`` na mão. O caminho do ensaio vai por
    :meth:`BombaDeSomPeloRadio.um_report`, que chamava ``arranjo.montar`` **sem
    `common`**, e o ramo ``common_preservado`` caía no
    ``bytes(COMMON_LEN)`` do valor omitido. Medido: ``[3..49]`` saía com
    **47 zeros**::

        common no 0x31 do produto : flag0 e flag1 ligados, volume e rota pedidos
        common no corpo do ensaio : todos os 47 bytes em zero — pede NADA

    Um ``common`` zerado tem os bits de validação em zero, então ele **não pede
    nada** — e sair pedindo nada é o pior desfecho possível para um par
    com/sem: se ela não ouvir, ninguém saberá dizer se o firmware sequer
    entendeu o corpo. O terceiro corpo existe para separar *"o arranjo está
    errado"* de *"o aparelho não faz"*, e um envelope inerte não separa nada.

    **O QUE O MAPA JÁ SABIA, e o ensaio ignorava** (``audio.alto_falante*``):
    são TRÊS campos, não um — rota (``common[7]``), volume (``common[5]``) e
    pré-amp (``common[37]``) —, e **por rádio o kernel nunca escreve nenhum
    deles** (o gatilho é USB-only, ``hid-playstation.c``). Quem não os mandar
    no próprio report não os tem.

    **NENHUM OFFSET E NENHUM BIT É DIGITADO AQUI.** Os cinco saem de
    :mod:`~hefesto_dualsense4unix.core.ds_output_report`, que é o dono deles —
    a regra da casa: *o nome mora com quem o lê, e quem o escreve LÊ de lá*. É
    por isso que este envelope é o mesmo que o produto pede pelos mesmos
    valores, e é isso que a régua confere.

    **O ``common[7]`` NÃO É ESCRITO INTEIRO**, e a cicatriz é de 02/08/2026:
    ele carrega a rota (bits 4-5) **e o caminho do microfone**, e escrever o
    byte com base zero fez o `parec` do microfone dela cair de 131.072 bytes
    para **zero**. A base é :data:`~…ds_output_report.AUDIO_CONTROL_BASE_SEGURA`.

    **NÃO ESCREVE NADA.** Monta 47 bytes e devolve.
    """
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


def montar_pelos_dois_arranjos(
    quadros: Sequence[bytes],
    *,
    seq: int = 0,
    tag_audio: int = BLOCO_SPEAKER,
) -> dict[str, bytes]:
    """O MESMO PCM já codificado, montado pelos DOIS arranjos candidatos.

    É esta função que a rota corrigida da sprint pede: *"mandam o MESMO PCM
    pelos DOIS arranjos, cada um com a sua régua"*. Devolver os dois de uma
    vez é o que impede que alguém meça um e conclua sobre o outro.
    """
    return {a.nome: a.montar(quadros, seq=seq, tag_audio=tag_audio) for a in ARRANJOS}


# ---------------------------------------------------------------------------
# O sink virtual do PipeWire — um nó por controle, e o nome NÃO tem transporte
# ---------------------------------------------------------------------------

#: ``module-null-sink`` e não ``module-pipe-sink``, e a razão não é elegância.
#: Com o null-sink, no CABO o monitor do nó pode ser ligado direto ao sink USB
#: do controle (``libpipewire-module-loopback.so``, presente nesta máquina) e
#: **nenhum byte de áudio entra no Python**. O pipe-sink obrigaria o PCM dela a
#: dar uma volta pelo nosso processo inclusive no cabo, onde o caminho nativo
#: já é bom — latência e risco de subcorrida comprados por nada.
#:
#: MEDIDO nesta máquina em 06/09/2026: ``module-null-sink``, ``module-pipe-sink``
#: e ``module-pipe-source`` estão os três na camada de compatibilidade Pulse do
#: PipeWire (``libpipewire-module-protocol-pulse.so``), e a
#: ``libpipewire-module-loopback.so`` existe.
_MODULO_NULL_SINK = "module-null-sink"

#: Prefixo do nome do nó: ``hefesto_som_<hex6>``, onde ``<hex6>`` são os SEIS
#: últimos dígitos hex do MAC do controle.
#:
#: **O NOME NÃO PODE CARREGAR O TRANSPORTE, e é a sprint inteira.** O defeito
#: que este nó existe para matar é: ela tira o cabo no meio da partida e o
#: dispositivo de saída que o jogo escolheu DESAPARECE do sistema. Um nome com
#: "usb" ou "bt" dentro reintroduz o defeito com outra roupa — o mesmo
#: controle mudaria de nó ao trocar de braço. É a mesma lição que
#: ``PREFIXO_SOURCE_CANAL_DO_MIC`` já pagou do lado do microfone.
#:
#: E ele é DIFERENTE do prefixo do microfone de propósito: ``hefesto_mic_`` é
#: um nó de captura, este é de saída, e ``fontes_de_captura.sinks_dualsense``
#: nunca deve devolver um pelo outro.
PREFIXO_SINK_DO_SOM = "hefesto_som_"

#: Seis dígitos hex — os três últimos octetos do MAC. Mesma régua de
#: identidade do canal do microfone.
HEX_DO_SUFIXO = 6

#: ``priority.session`` BAIXA: o controle **não** vira a saída padrão do
#: sistema sozinho. É decisão dela, tomada por delegação em 06/09/2026
#: (``D-0609-O-NO-DE-SOM-VIVE-COM-O-CONTROLE``: *"no cabo não vira saída
#: padrão"*), e é o mesmo princípio que a entrada já segue — *"o controle fica
#: mexendo no microfone"* foi sintoma real.
#:
#: MEDIDO nesta máquina em 06/09/2026 (``LC_ALL=C pactl list sinks``), com dois
#: DualSense no cabo::
#:
#:     alsa_output.pci-…hdmi-stereo                        696
#:     alsa_output.pci-…iec958-stereo                      736
#:     alsa_output.usb-…DualSense…analog-surround-40       1109
#:     alsa_output.usb-…DualSense…-00.2.analog-surround-40 1109
#:
#: O menor sink REAL desta máquina é 696. O invariante é que o nó virtual
#: nunca ganhe do menor deles, e 10 está uma ordem de grandeza abaixo de
#: qualquer saída plausível — não é um número mágico, é o piso.
PRIORIDADE_SESSAO_DO_SOM = 10

#: **FATO SUBSTITUÍDO em 09/09/2026.** Esta constante se chamava
#: ``DESCRICAO_PROVISORIA`` e valia ``"Alto-falante do controle"`` — um rótulo
#: neutro, "até ela decidir". **Ela decidiu** (*"4a"*,
#: ``D-0909-OS-NOS-SE-CHAMAM-ALTO-FALANTE-E-MICROFONE-DO-CONTROLE-N``), e o
#: provisório virou o nome: «Alto-falante do Controle N», com o número do
#: ASSENTO. Quem monta o rótulo com número é :func:`descricao_do_alto_falante`,
#: no fim deste módulo; esta constante é a metade SEM número, que é a resposta
#: honesta quando ninguém sabe dizer o assento.
#:
#: O par com «Microfone do Controle N»
#: (``dualsense_bt_audio.NOME_DO_MICROFONE_DO_CONTROLE``) está em
#: ``docs/A-LINGUA-DESTA-CASA-o-glossario-que-a-tela-e-o-codigo-falam.md``.
NOME_DO_ALTO_FALANTE_DO_CONTROLE = "Alto-falante do Controle"

_TIMEOUT_PACTL_S = 5.0

_DIRS_PIPEWIRE = (
    "/usr/lib/x86_64-linux-gnu/pipewire-0.3",
    "/usr/lib64/pipewire-0.3",
    "/usr/lib/pipewire-0.3",
)


def nome_do_sink(uniq: str) -> str:
    """``hefesto_som_<hex6>`` a partir do ``uniq`` do controle. "" se ilegível.

    **A identidade vem do CONTROLE, nunca do transporte nem do nó ``hidrawN``.**
    O ``uniq`` é o que sobrevive a hotplug, a renumeração de jogador e à troca
    do ``hidrawN``; o transporte não sobrevive a tirar o cabo, que é o gesto
    que esta sprint existe para não quebrar.

    "" quando o ``uniq`` não tem hex bastante: sem endereço não há de quem seja
    o nó, e publicar um nó anônimo seria pior que não publicar — dois controles
    disputariam o mesmo nome.
    """
    rabo = so_hex(str(uniq))
    if len(rabo) < HEX_DO_SUFIXO:
        return ""
    return f"{PREFIXO_SINK_DO_SOM}{rabo[-HEX_DO_SUFIXO:]}"


def sufixo_do_sink_do_som(nome: str) -> str:
    """Rabo hex do MAC no nome do nó de som — "" se não for um.

    Recorta o prefixo ANTES de filtrar hex, e a ordem não é detalhe: o próprio
    ``hefesto_som_`` tem letras hex dentro (``e``, ``f``), e passar o nome
    inteiro por :func:`so_hex` produziria um "MAC" com lixo do prefixo grudado
    na frente — casamento por acaso, que é o defeito que a régua do microfone
    já documenta.
    """
    baixa = nome.lower()
    if not baixa.startswith(PREFIXO_SINK_DO_SOM):
        return ""
    resto = baixa[len(PREFIXO_SINK_DO_SOM) :]
    if len(resto) < HEX_DO_SUFIXO or so_hex(resto) != resto:
        return ""
    return resto


def propriedades_do_sink(descricao: str) -> str:
    """O argumento ``sink_properties=`` do ``load-module`` — ENTRE ASPAS DUPLAS.

    **AS ASPAS SÃO A CURA**, e a lição é da metade de entrada, paga em
    06/09/2026: o parser do ``pipewire-pulse`` corta o valor no primeiro ESPAÇO
    quando ele não vem entre aspas duplas, e este argumento tem três
    propriedades separadas por espaço — só a primeira chegava, pela metade. O
    efeito medido lá foi a ``priority.session`` NUNCA chegar ao nó, com a régua
    dando verde porque lia o argv em vez do nó.

    Aqui a mesma armadilha seria pior: sem a prioridade, o nó nasceria com o
    padrão do servidor (2000 medido lá) e o alto-falante do controle poderia
    virar a saída do sistema sozinho — exatamente o que a decisão dela recusa.
    """
    return (
        'sink_properties="'
        + " ".join(
            (
                f"device.description='{descricao}'",
                f"priority.session={PRIORIDADE_SESSAO_DO_SOM}",
                "device.icon_name=audio-speakers",
            )
        )
        + '"'
    )


def _rodar(argv: list[str]) -> str | None:
    """Roda um comando curto e devolve o stdout (None em qualquer falha).

    Nunca ``shell=True`` e sempre com prazo: um ``pactl`` pendurado não segura o
    nó, e o prazo estourado põe o SERVIDOR em recuo (:func:`_o_recuo`).

    ``LC_ALL=C`` porque o ``pactl`` desta máquina TRADUZ, e esta casa já
    respondeu *"nenhum controle com placa de áudio"* sobre um sistema que tinha
    uma, em 15/08/2026, exatamente por ler saída traduzida.
    """
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
    if proc.returncode != 0:
        return None
    _anotar_a_resposta(argv)
    return proc.stdout


def rodar_pactl(argv: list[str]) -> str | None:
    """Porta pública de :func:`_rodar`, para o ensaio perguntar ao servidor.

    O ensaio precisa LER o nó (``pactl list sinks``, ``get-default-sink``) para
    conferir o que de fato chegou lá. Ele podia montar o próprio ``subprocess``
    — e aí teria a própria política de idioma, de timeout e de ``shell``, que é
    como esta casa fabrica um segundo dono para a mesma pergunta. Uma porta é
    mais barata que uma segunda régua.
    """
    return _rodar(argv)


class SinkVirtualPipeWire:
    """O nó de saída de UM controle, publicado no PipeWire por ``pactl``.

    Molde: :class:`~integrations.dualsense_bt_audio.SourceVirtualPipeWire`, a
    irmã de ENTRADA, virada ao contrário. Ciclo de vida idêntico,
    ``load-module``/``unload-module``, e a mesma armadilha do ``wireplumber``
    parado do outro lado.

    **O nó não sabe o que é transporte, e é esse o contrato inteiro.** O nome
    vem do ``uniq``; o cabo, o rádio e o "não tem para onde ir" acontecem por
    baixo dele. É o mesmo contrato do gamepad virtual, que é o precedente que
    ela citou: o jogo escolhe um dispositivo, não um transporte.
    """

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
        #: Para onde este nó entrega, e a frase quando não entrega. ``None`` é
        #: *"ninguém resolveu a rota"* e vale como recusa — nunca como "entrega
        #: em algum lugar". Ver :meth:`iniciar`.
        self.rota = rota
        self._module_id: str | None = None
        #: Os ids dos ``module-loopback`` que ESTE nó carregou, na ordem em que
        #: subiram. Descarregados na ordem INVERSA, e só os que ele carregou:
        #: derrubar um loopback alheio é derrubar o som de outra pessoa.
        self._rotas: list[str] = []

    # -- ciclo de vida ----------------------------------------------------

    @property
    def module_id(self) -> str | None:
        """O id do módulo carregado, ou None se o nó não está de pé."""
        return self._module_id

    def iniciar(self) -> bool:
        """Carrega o ``module-null-sink`` E a rota dele. False = não deu.

        Recusa sem nome: um ``uniq`` ilegível não vira nó. Ausência é resposta.

        **O NÓ SOBE MESMO SEM ROTA, e é decisão DELA de 08/09/2026**
        (``D-0809-O-NO-DE-SOM-POR-CONTROLE-VIVE-SEMPRE``, palavra dela
        *"concordo com as 5"*): *"nó que some quebra o jogo que o escolheu"*. O
        que vai e volta é a ROTA, não o nó. **FATO SUBSTITUÍDO:** até 07/09 a
        casa escrevia o contrário — *"sem rota não se carrega módulo nenhum"*
        (a invariante 4 de ``app/audio_saida.PlanoDoNo``, e a régua
        ``tests/unit/test_o_no_de_som_nao_nasce_sumidouro.py``) — porque a
        decisão então valendo era a de 06/09, *"o nó vive só enquanto há
        controle"*, tomada por DELEGAÇÃO e declarada reversível numa frase. Ela
        reverteu. O que sobra da invariante 4, e continua de pé, é a metade que
        importa: **um nó sem rota tem de DIZER que não tem para onde ir** —
        :attr:`rota` carrega a frase, e quem a mostra é a tela.
        """
        if self._module_id is not None:
            return True
        if not self.nome:
            logger.info("som_sem_identidade", uniq=self.uniq)
            return False
        # Sem `pactl`, com o servidor em recuo, ou com a sondagem sem resposta: nada sai.
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
                propriedades_do_sink(self.descricao),
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
        """Carrega os ``module-loopback`` desta rota. Silencioso quando não há.

        São até DOIS, e eles respondem a perguntas diferentes:

        * **a saída** — o monitor do nó para o alto-falante DAQUELE controle. É
          o que faz o som que entra no nó sair no plástico;
        * **a fonte «mix»** — o monitor da saída padrão do sistema PARA o nó. É
          o *«HDMI completo»* dela: o que a TV recebe, o controle recebe junto.
          Em ``sfx`` este segundo não existe, e o nó fica livre para a corrente
          que o jogo mandar — que é o padrão do cabo por decisão dela
          (``D-0809-NO-CABO-O-PADRAO-DO-SOM-E-SFX``).

        Um loopback que não sobe **não derruba o nó**: o nó publicado com o som
        do jogo mudo ainda é o dispositivo que o jogo escolheu, e derrubá-lo
        aqui traria de volta exatamente o defeito que ele existe para matar.
        """
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
        """Troca a ROTA deste nó **sem tirar o nó do lugar**. ``True`` = mexeu.

        É ``D-0809-O-NO-DE-SOM-POR-CONTROLE-VIVE-SEMPRE`` escrita em código:
        *"o que vai e volta é a ROTA, e o nó fica"*. O ``module-null-sink`` não
        é tocado — ele guarda o nome, o id e o lugar na lista de saída dela —,
        e o que desce e sobe são os ``module-loopback``.

        **POR QUE NÃO DERRUBAR E REFAZER O NÓ**, que seria uma linha mais
        curta: o jogo escolheu ``hefesto_som_<hex6>``. Tirá-lo do servidor por
        um instante é tirar o dispositivo debaixo dele — o defeito que este
        módulo inteiro existe para matar. Quem chama isto é a varredura, de 5
        em 5 s; um nó que renasce a cada varredura é pior que a escolha presa
        que este método existe para soltar.

        **A COMPARAÇÃO É POR :func:`assinatura_da_rota`**, e o que ela deixa de
        fora é metade do valor — leia lá. Rota de assinatura igual não mexe em
        nada, e é por isso que a varredura pode chamar isto sempre.

        Com o nó ainda no chão a rota só é GUARDADA: :meth:`iniciar` a liga
        quando ele subir, e carregar um ``module-loopback`` para um sink que
        não existe é o ``paplay --device=`` que esta casa já pagou.
        """
        if rota is None or assinatura_da_rota(rota) == assinatura_da_rota(self.rota):
            return False
        if self._module_id is None:
            self.rota = rota
            return False
        anterior = self.rota
        # A rota velha cai ANTES da nova subir, e só a que ESTE nó carregou —
        # a mesma regra de `parar`. Deixar as duas de pé somaria o mix ao mix.
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
        """Descarrega a rota e o módulo, nessa ordem. Idempotente.

        **A rota cai ANTES do nó**, e não é estética: um ``module-loopback``
        cuja ponta some é um módulo órfão no servidor de áudio dela, e foi
        assim que 52 sinks fantasma entraram no PipeWire dela em 07/09.
        """
        for module_id in reversed(self._rotas):
            self.runner(["pactl", "unload-module", module_id])
        self._rotas.clear()
        if self._module_id is None:
            return
        self.runner(["pactl", "unload-module", self._module_id])
        logger.info("som_sink_removido", sink=self.nome)
        self._module_id = None

    # -- leitura ----------------------------------------------------------

    def estado(self) -> str | None:
        """``RUNNING`` / ``IDLE`` / ``SUSPENDED`` do nó, PERGUNTADO ao servidor.

        None = não deu para saber. **"Não sei" não é "ninguém está tocando"**,
        e quem chama trata os dois diferente.

        Lê, nunca lembra: o estado tem UM dono — o servidor de som —, e guardar
        aqui o que se pediu como se fosse o que está valendo é o hábito que já
        fez esta tela parecer mentirosa quando ela nunca mentiu.
        """
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


#: A quinta coluna de ``pactl list sinks short``, separada por TAB. Medido do
#: lado da entrada e vale igual aqui: o campo de formato tem ESPAÇOS dentro
#: (``s16le 2ch 48000Hz``), então quebrar a linha por espaço em branco devolve
#: ``2ch`` no lugar do estado.
_COLUNA_DO_ESTADO = 4


# ---------------------------------------------------------------------------
# A BOMBA — o que faltava entre o nó e o fio, e ela não afirma som nenhum
# ---------------------------------------------------------------------------

#: Quantos quadros Opus um report do arranjo escolhido carrega vezes 10 ms.
#: Não é constante: sai do arranjo (`Arranjo.quadros_de_audio`), porque os dois
#: candidatos carregam dois quadros e um terceiro arranjo poderia carregar
#: outro número. Fica aqui só como nome do que a conta significa.
MS_POR_QUADRO = 10

#: O nibble de sequência do envelope de rádio dá a volta em 16. **Ele não é
#: enfeite**, e o preço de errar já foi pago nesta casa por escrito
#: (`core/backend_pydualsense.writeReport`): *"o firmware descarta o report
#: fora de sequência e o log diz 'escrito'"*. Um fluxo de áudio escreve ~100
#: reports por segundo — sem rotação, do segundo em diante todos repetiriam o
#: mesmo `seq` e o aparelho jogaria fora tudo menos o primeiro, com o nosso
#: lado contando 100 "escritas aceitas" por segundo.
VOLTA_DA_SEQUENCIA = 16

#: Tocadores de leitura crua do monitor de um nó, na ordem de preferência, com
#: o modelo de argumentos. Os dois entregam **s16le, estéreo, 48 kHz** em
#: `stdout`, que é exatamente o que :class:`CodificadorOpus` come — nenhuma
#: conversão nossa no meio, e por isso nenhuma segunda régua de formato.
#:
#: `pw-record` primeiro por ser o nativo do PipeWire (o `parec` passa pela
#: camada de compatibilidade Pulse e já mordeu esta casa uma vez, no
#: `sink_properties` cortado no espaço).
GRAVADORES_DO_MONITOR: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "pw-record",
        ("--target={fonte}", "--rate={taxa}", "--channels={canais}",
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

#: A LATÊNCIA QUE SE PEDE AO GRAVADOR DO MONITOR — medida em 18/09/2026, com os
#: três controles no rádio e o tom tocando num nó só, pelas escritas do daemon:
#:
#:     parec sem --latency-msec  → o som sai no rádio 1,79 a 2,04 s depois do jogo
#:
#: É o fragmento padrão do `parec` (quase dois segundos), o mesmo que a casa
#: mediu no microfone em 06/09 (`canal_do_microfone._LATENCIA_DO_ALIMENTADOR_MS`).
#: Num jogo, o tiro soava dois segundos depois do tiro, e a vibração por áudio
#: passa por esta mesma tabela. O `pw-record` nasce com 100 ms, e o número vai
#: explícito nos dois para que o caminho escolhido não mude o atraso.
LATENCIA_DO_GRAVADOR_MS = 40


def serial_do_no(nome: str) -> int | None:
    """O ``object.serial`` do nó chamado ``nome``, ou ``None``.

    SOM-ECO-02 (16/09/2026) — e é o número que faz o ``pw-record`` acertar o
    alvo. O ``object.serial`` é o mesmo índice que o ``pactl`` publica na
    coluna 1 de ``list sinks short``: medido nesta máquina, o sink
    ``hefesto_som_…`` tem ``id=46`` e ``object.serial=75833``, e é o 75833 que
    o ``pactl`` mostra. **O ``id`` NÃO serve** — ver a tabela em
    :func:`argv_do_gravador`.

    Aceita o nome do SINK ou o do monitor dele (``<sink>.monitor``): o serial é
    o do sink nos dois casos, e o ``pw-record`` mirado nele entrega o monitor.

    Best-effort e silenciosa: sem ``pactl``, com o servidor em recuo ou com o nó
    ausente, devolve ``None`` — e o chamador cai no gravador que acerta pelo
    NOME. Ausência aqui nunca vira "use a fonte padrão".
    """
    if not nome:
        return None
    alvo = nome[: -len(".monitor")] if nome.endswith(".monitor") else nome
    try:
        proc = subprocess.run(
            ["pactl", "list", "sinks", "short"],
            capture_output=True, text=True, timeout=2.0, check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if getattr(proc, "returncode", 1) != 0:
        return None
    for linha in (proc.stdout or "").splitlines():
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
    """Quem responde ao ``pactl`` é o ``pipewire-pulse``? ``False`` se não sei.

    INSTALL-UNIVERSAL (18/09/2026). :func:`serial_do_no` lê o índice da coluna 1
    do ``pactl`` e o entrega ao ``pw-record`` como ``object.serial`` — o que só
    é verdade no ``pipewire-pulse``. Numa máquina com PulseAudio no som e o
    PipeWire rodando ao lado para a tela, com o ``pw-record`` instalado (arranjo
    plausível de distro LTS; NÃO medido nesta casa), o índice do PulseAudio
    mira um nó qualquer do grafo do PipeWire, ou nenhum — e alvo que não
    resolve cai na fonte PADRÃO, que é a forma exata do eco da SOM-ECO-02. Ali
    o ``parec`` acerta pelo nome.

    Pergunta em ``LC_ALL=C`` (o :func:`rodar_pactl` garante): a chave
    ``Server Name`` é traduzida. Sem resposta é ``False``, e o ``parec`` assume.
    """
    correr: Any = runner or rodar_pactl
    for linha in (correr(["pactl", "info"]) or "").splitlines():
        chave, _, valor = linha.partition(":")
        if chave.strip() == "Server Name":
            return "pipewire" in valor.lower()
    return False


def rotulo_do_gravador(*, uniq: str, papel: str = "som") -> str:
    """O nome que damos ao NOSSO nó de gravação. Único por controle E POR PAPEL.

    **O `id_do_no` SAIU DA ASSINATURA em 20/09/2026, e ele era o defeito.**
    A redação anterior recebia o nome do nó e fazia
    ``id_do_no.rsplit("_", 1)[-1]`` — regra escrita quando o único nome que
    passava por aqui era ``hefesto_som_<hex6>``, onde o último pedaço É o
    hex6. Dois dias depois a ponte da háptica começou a mandar pela mesma
    porta o nome do ENDPOINT, que termina em ``...HiFi__Speaker__sink``: o
    último pedaço virou literalmente ``sink``, e os três controles do rádio
    passaram a publicar o MESMO ``node.name`` — ``hefesto-ponte-sink``.

    O preço foi medido no aparelho, com o PRAGMATA aberto e a mesa de quatro:
    a conferência desta mesma casa junta todo nó com aquele nome, devolve o
    Link do mais velho, vê "nó errado" e mata o gravador certo. Em 4 min 37 s,
    **270 execuções por controle** — e só o primeiro a subir vibrou, porque no
    instante em que ELE foi conferido ainda não havia Link e a resposta foi
    "não sei", que passa. A mão dela leu isso como *"só mandou pro player 3"*.

    **Por isso o dono agora é o `uniq`, e não o texto do nome.** É a regra
    desta casa — *quando um valor tem dono, pergunte ao dono* —, e a mesma
    que o `casar-no-com-controle-por-rotulo-e-cura-errada` já cobrava. O
    ``papel`` separa os dois gravadores do MESMO controle: a ponte do rádio
    sobe um para o som e outro para a háptica, e sem ele os dois colidiriam
    pelo mesmo caminho que acabou de custar a vibração de dois controles.

    SOM-ECO-02 — ele existe para a conferência ter por onde pegar. O PipeWire
    **não expõe o PID** do processo (medido: `application.process.id` vem
    `None` para o `pw-record`, e nenhuma outra chave do `pw-dump` carrega o
    número), então casar o gravador pelo processo é impossível por esse
    caminho. Casar pelo NOME DO BINÁRIO seria pior: numa mesa de quatro há um
    `pw-record` por controle, e a conferência devolveria o alvo do vizinho — a
    mesma família do `casar-no-com-controle-por-rotulo-e-cura-errada`.

    Então o identificador é NOSSO, e carrega o nó do controle: um rótulo por
    peça, que o `pw-dump` devolve em `node.name`. Medido nos dois gravadores —
    `pw-record -P node.name=…` e `parec --client-name=…` publicam o mesmo nome.
    """
    from hefesto_dualsense4unix.integrations.endpoint_de_haptica import (
        marca_do_controle,
    )

    marca = marca_do_controle(uniq)
    # AUSÊNCIA É RESPOSTA: sem `uniq` não há identidade, e devolver um nome
    # genérico recriaria a colisão que esta função existe para matar. O
    # chamador trata o vazio como "não subo gravador".
    if not marca:
        return ""
    return f"hefesto-ponte-{marca}-{papel}"


def argv_do_gravador(
    fonte: str,
    *,
    taxa: int = TAXA_DO_ENCODER,
    canais: int = CANAIS_DO_ENCODER,
    rotulo: str = "hefesto-ponte",
) -> list[str]:
    """O comando que lê PCM cru do monitor de um nó. `[]` se não há tocador.

    A fonte vai como ARGUMENTO próprio e nunca por texto de comando (nada de
    ``shell=True``, invariante do projeto), e ela vai **explícita e não
    vazia**: `--target=` vazio no `pw-record` cai na fonte padrão do sistema, e
    o instrumento leria o som da máquina inteira achando que lia o do nó.

    **A GUARDA ACIMA COBRIA O CASO ERRADO — SOM-ECO-02, 16/09/2026.**

    ``if not fonte`` pega a string VAZIA. Não pega o nome que o PipeWire **não
    resolve para um nó ativo** — e o resultado é o mesmo, sem aviso nenhum.
    Medido nesta máquina, com o sink do controle em ``suspended`` (que é o
    estado normal quando ninguém está tocando som):

        pw-record --target=hefesto_som_…       -> hefesto_mic_…:capture_MONO
        pw-record --target=hefesto_som_….monitor -> hefesto_mic_…:capture_MONO
        pw-record --target=46      (o `id`)    -> hefesto_mic_…:capture_MONO
        pw-record --target=75833   (o serial)  -> hefesto_som_…:monitor_FL   OK
        parec     --device=hefesto_som_….monitor -> hefesto_som_…:monitor_FL OK

    **O QUE ISSO CUSTOU A ELA:** a fonte padrão desta máquina é o microfone do
    controle, então a ponte de som pelo rádio vinha lendo a VOZ DELA e mandando
    ao alto-falante do próprio controle. Era o eco que ela relatou — *"o que eu
    falo a caixa de som repete e dá eco"* —, com o atraso da ida e volta pela
    ponte. E era por isso que no CABO não havia eco: no cabo não existe esta
    ponte. O ``ECHO_CANCEL`` do firmware (`SOM-ECO-01`, hoje de manhã) cancelava
    só o SEGUNDO salto — o que saía do alto-falante e reentrava no microfone —,
    e por isso ela mediu *"melhorou mas ainda existe"*.

    A cura é o ARGUMENTO, não o programa: o ``pw-record`` continua sendo o
    primeiro (é o nativo do PipeWire), agora mirado pelo ``object.serial``. Sem
    serial, o ``parec`` assume — ele acerta pelo nome, e um gravador que acerta
    vale mais que a preferência por qual camada ele usa.

    **Isto NÃO basta sozinho**, e a outra metade está em
    :func:`conferir_o_alvo_do_gravador`: o serial é resolvido antes de o
    processo subir, e o nó pode sumir no meio. Pedir sem conferir o que veio é a
    mesma forma do defeito que esta função acabou de curar.
    """
    if not fonte:
        return []
    for binario, modelo in GRAVADORES_DO_MONITOR:
        if shutil.which(binario) is None:
            continue
        # `pw-record` SÓ com o serial; sem ele, deixa o `parec` assumir. E o
        # serial SÓ quando quem responde ao `pactl` é o `pipewire-pulse`: o
        # índice do `pactl` é o `object.serial` do PipeWire ali e em nenhum
        # outro lugar — ver :func:`o_servidor_e_o_pipewire`.
        if binario == "pw-record":
            serial = serial_do_no(fonte) if o_servidor_e_o_pipewire() else None
            if serial is None:
                continue
            return [binario, *(m.format(fonte=str(serial), taxa=taxa,
                                        canais=canais, rotulo=rotulo,
                                        latencia_ms=LATENCIA_DO_GRAVADOR_MS)
                               for m in modelo)]
        return [binario, *(m.format(fonte=fonte, taxa=taxa, canais=canais,
                                    rotulo=rotulo,
                                    latencia_ms=LATENCIA_DO_GRAVADOR_MS)
                           for m in modelo)]
    return []


def conferir_o_alvo_do_gravador(rotulo: str) -> str | None:
    """A que nó de ORIGEM o gravador chamado `rotulo` se ligou. ``None``=não sei.

    SOM-ECO-02, a metade que morde. O :func:`argv_do_gravador` resolve o
    ``object.serial`` ANTES de o processo subir, e entre resolver e conectar o
    nó pode sumir, mudar de serial ou nascer outro com o mesmo nome. Quando o
    alvo não resolve, o PipeWire liga o gravador à FONTE PADRÃO **sem erro
    nenhum** — e a fonte padrão da máquina dela é o microfone do controle. Foi
    assim que a ponte passou a mandar a voz dela ao alto-falante do próprio
    controle. **Pedir sem conferir o que veio é a forma exata do defeito que
    esta cura desfaz.**

    O casamento é pelo `rotulo` que NÓS demos ao nó (ver
    :func:`rotulo_do_gravador`), porque o PipeWire não expõe o PID e o nome do
    binário se repete por controle.

    A ligação sai do `Link`, e os campos vêm do ``info`` e não do ``props`` —
    medido no `pw-dump` desta máquina: um Link traz ``input-node-id`` e
    ``output-node-id`` prontos, e ler pelas PORTAS custaria um segundo
    cruzamento para chegar ao mesmo lugar.

    ``None`` nunca quer dizer "está certo": sem ``pw-dump``, com ele em recuo ou
    com a saída ilegível, quem chama trata como **não conferido** e diz isso no
    journal. Derrubar a ponte por não ter conseguido OLHAR trocaria um defeito
    raro por um mudo garantido.
    """
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


@dataclass
class ContagemDaBomba:
    """O que a bomba mediu. **Nenhum destes números é "saiu som".**

    A distinção que dá nome ao campo mais importante está no mapa
    (``audio.saida_dedicada.payload_do_degrau@dualsense``) e é a razão de este
    dataclass existir em vez de um contador solto:

        ``os.write()`` num hidraw devolve sucesso quando o **KERNEL** aceita a
        entrega; ele NÃO espera veredito do firmware. Em 15/08 o kernel aceitou
        até um pacote de tamanho errado que era o controle negativo.

    Por isso o campo se chama :attr:`escritas_aceitas_pelo_kernel`, e não
    "reports entregues": quem lê o relatório tem de tropeçar na ressalva antes
    de conseguir citar o número.
    """

    pcm_lido: int = 0
    pcm_curto: int = 0
    quadros_opus: int = 0
    quadros_recusados: int = 0
    reports_montados: int = 0
    escritas_aceitas_pelo_kernel: int = 0
    escritas_recusadas: int = 0
    bytes_escritos: int = 0
    segundos: float = 0.0
    #: Blocos hápticos montados, e quantos deles saíram MUDOS (todas as
    #: amostras em zero). A distinção é o que separa *"a ponte não roda"* de
    #: *"o jogo não mandou vibração"* — os dois se leem como "não vibrou".
    blocos_hapticos: int = 0
    hapticos_mudos: int = 0
    #: O maior valor absoluto que já foi para um motor, em int8 (0..127).
    pico_haptico: int = 0

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
            f"  escritas ACEITAS PELO KERNEL {self.escritas_aceitas_pelo_kernel}",
            f"  escritas recusadas ......... {self.escritas_recusadas}",
            f"  bytes no fio ............... {self.bytes_escritos} B"
            f"  ({self.bytes_por_segundo / 1024:.1f} KiB/s)",
            "  ATENÇÃO: 'aceitas pelo kernel' NÃO é 'o firmware obedeceu', e",
            "  nada aqui é medição de som. Quem mede som é a orelha dela.",
        ]


class BombaDeSomPeloRadio:
    """Do monitor do nó ao fio: lê PCM, codifica, monta o degrau e escreve.

    **É a peça que faltava entre as duas metades que já existiam.** O encoder
    (:class:`CodificadorOpus`) e o nó (:class:`SinkVirtualPipeWire`) nasceram
    na SOM-QUE-SAI-01 de 06/09; o arranjo (:class:`Arranjo`) monta o report.
    Ninguém, até aqui, ligava os três em regime — e sem isso o nó publicado é
    um sumidouro, que é o defeito que
    ``tests/unit/test_o_no_de_som_nao_nasce_sumidouro.py`` trava.

    O QUE ELA **NÃO** DECIDE, e a lista é o valor de ler isto
    ---------------------------------------------------------
    * **não escolhe o arranjo.** Ele é argumento obrigatório. As duas fontes
      publicadas divergem sobre onde o áudio mora dentro do ``0x39``, e uma
      delas cita a outra — escolher aqui seria inventar o caminho. Quem escolhe
      é a orelha dela, no ensaio de bancada;
    * **não escolhe o degrau para regime.** O degrau sai do arranjo. A decisão
      dela (``D-0609-O-NO-DE-SOM-VIVE-COM-O-CONTROLE``) é *só depois do D5*,
      com o número de banda na mesa — e :attr:`ContagemDaBomba.bytes_por_segundo`
      é justamente esse número, que é para o que ela serve;
    * **não afirma que saiu som.** Ver :class:`ContagemDaBomba`.

    E ELA NASCE SECA (``seco=True``), que é o padrão
    ------------------------------------------------
    Seca, ela faz a conta inteira — lê, codifica, monta, conta — e **não
    escreve um byte no aparelho**. É o modo em que a bomba pode ser medida com
    ela na bancada sem que nada saia no fio, e é o modo em que a suíte roda.
    Molhar exige um `escritor` explícito de quem chama: sem ele, mesmo
    ``seco=False`` não escreve, porque não há para onde.
    """

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
    ) -> None:
        # O `common` É OBRIGATÓRIO PARA O CORPO QUE O PRESERVA — 08/09/2026.
        #
        # Sem ele o ramo `common_preservado` de `Arranjo.montar` caía no
        # `bytes(COMMON_LEN)` do valor omitido e o corpo saía com 47 ZEROS,
        # medido. Um `common` zerado tem os bits de validação apagados, logo
        # não pede rota, não pede volume e não pede pré-amp — e o mapa diz que
        # por rádio o kernel não escreve nenhum dos três. O corpo ia ao fio
        # pedindo NADA, num ensaio cujo desfecho é a orelha dela.
        #
        # Recusar é a regra da casa: *ausência é resposta*. Deixar o padrão
        # zerado passar seria um instrumento dando VERMELHO sobre nada — a
        # mesma família dos que dão verde, com o sinal trocado, e mais cara,
        # porque quem paga é a orelha dela numa passada que não mediu nada.
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
        #: O envelope de [3..49]. `None` = o arranjo não o preserva e o corpo
        #: dele põe a tag do AudioControl no byte [2].
        self.common = common
        self._codificador = codificador
        self._seq = 0
        #: QUADROS de áudio já mandados — não reports. O `[10]` do `0x35` conta
        #: quadros, e um arranjo de dois quadros avança de dois em dois.
        self._quadros_mandados = 0
        #: O bit 0 dos enables. Ligado, o microfone entra no MESMO report que
        #: leva o som — medido em 10/09/2026.
        #:
        #: **ELE É PERGUNTADO A CADA REPORT, e não congelado na construção** —
        #: 10/09/2026, queixa dela. Um `bool` fixo aqui vale para sempre, e o
        #: estado do microfone muda ENQUANTO a ponte está de pé: ela aperta o
        #: botão, e daí em diante todo report do som contradiz o gesto. Com
        #: 93,75 reports por segundo, um `0xFE` congelado é o microfone sendo
        #: desligado noventa e três vezes por segundo.
        self.com_microfone = com_microfone
        #: A fonte do PCM da HÁPTICA — o monitor do endpoint de quatro canais
        #: que o jogo abre. Separada da fonte do som de propósito: são dois
        #: nós diferentes, com donos diferentes (a saída da máquina para o
        #: controle CONTRA o alto-falante que o JOGO enxerga).
        self.fonte_haptica = fonte_haptica
        #: O conversor 48 kHz/4 canais → bloco de 64 B. Preguiçoso: uma bomba
        #: montada e nunca rodada não precisa dele.
        self._conversor = conversor
        self._blocos: list[bytes] = []
        self.contagem = ContagemDaBomba()

    # -- a conta ----------------------------------------------------------

    def quer_o_microfone(self) -> bool:
        """O bit 0 dos enables DESTE report. Nunca levanta.

        Aceita as duas formas de :attr:`com_microfone` — o `bool` de quem já
        sabe, e o chamável de quem PERGUNTA a cada report. O segundo é o do
        produto: quem responde é o subsystem do microfone, e a resposta muda
        no meio da ponte.

        Uma exceção aqui não pode calar o som: quem chama está no laço de
        envio, a 93,75 reports por segundo, e um oráculo que explodiu é um
        *"não sei"* — que vale `False`, o estado em que o aparelho já estava.
        """
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

    def _codificar(self, pcm: bytes) -> bytes | None:
        """O quadro Opus, ou None se a libopus recusou. Encoder preguiçoso.

        Preguiçoso porque construir o :class:`CodificadorOpus` carrega a
        `libopus` por `ctypes`: uma bomba montada e nunca rodada — a da suíte,
        e a do dublê — não pode exigir a biblioteca da máquina.
        """
        if self._codificador is None:
            self._codificador = CodificadorOpus()
        quadro = self._codificador.codificar(pcm)
        return quadro if quadro is None else bytes(quadro)

    # -- o ciclo ----------------------------------------------------------

    def um_report(self) -> bytes | None:
        """Lê o PCM de UM report, codifica, monta e devolve os bytes.

        `None` quando a fonte secou (leitura vazia) — é assim que o laço para
        sem exceção quando o gravador morre ou o arquivo acaba.

        **Leitura curta não é descartada, é completada com silêncio e CONTADA.**
        Descartar faria o fim de todo fluxo sumir sem número; completar em
        silêncio, sem contar, faria a bomba parecer sã com a fonte agonizando.
        """
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
        quadros: list[bytes] = []
        for i in range(self.arranjo.quadros_de_audio):
            pedaco = pcm[i * BYTES_DE_PCM_POR_QUADRO : (i + 1) * BYTES_DE_PCM_POR_QUADRO]
            quadro = self._codificar(pedaco)
            if quadro is None:
                self.contagem.quadros_recusados += 1
                return b""
            self.contagem.quadros_opus += 1
            quadros.append(quadro)
        # O `common` ATRAVESSA — e é isto que faz o corpo do ensaio ser o
        # mesmo que as réguas medem. Sem esta linha o `common=` do construtor
        # ficaria guardado e nunca chegaria ao fio: a cura pela metade, que é
        # como o defeito de 08/09 nasceu (a afirmação valia na chamada direta
        # e não no caminho que ela roda).
        report = self.arranjo.montar(
            quadros,
            seq=self._seq,
            tag_audio=self.tag_audio,
            common=self.common,
            controle=self._controle_deste_report(),
            haptico=haptico,
        )
        self._seq = (self._seq + 1) % VOLTA_DA_SEQUENCIA
        # Sem áudio, o contador do bloco `0x11` anda por REPORT: ele existe
        # para o firmware não perder a conta dos quadros que consome, e no
        # arranjo da háptica cada report É um quadro de 10,667 ms.
        self._quadros_mandados += self.arranjo.quadros_de_audio or 1
        self.contagem.reports_montados += 1
        return report

    @property
    def bytes_de_pcm_da_haptica(self) -> int:
        """O PCM cru de UM bloco háptico: 512 quadros de 4 canais s16le."""
        return QUADROS_POR_BLOCO_HAPTICO * 2 * CANAIS_DA_HAPTICA

    def _bloco_haptico(self) -> bytes | None:
        """O próximo bloco de 64 B, ou None quando a fonte secou.

        **A FONTE DA HÁPTICA É O RELÓGIO QUANDO NÃO HÁ ÁUDIO**, e isso não é
        detalhe de implementação: a leitura do monitor bloqueia até existirem
        512 quadros, que são os 10,667 ms de um report. Quem dá o ritmo é o
        jogo. Um `sleep` nosso em cima disso só acrescentaria deriva.
        """
        if self._conversor is None:
            from hefesto_dualsense4unix.integrations.haptica_bt import ConversorDeHaptica

            self._conversor = ConversorDeHaptica()
        while not self._blocos:
            if self.fonte_haptica is None:
                return None
            pcm = self.fonte_haptica(self.bytes_de_pcm_da_haptica)
            if not pcm:
                return None
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
        """Os bytes do bloco de controle, montados por report quando ele conta.

        Vazio para os arranjos que não contam quadros — é o que eles já
        recebiam, e mudar isso mexeria no corpo que as réguas deles medem.
        """
        if not self.arranjo.controle_conta_quadros:
            return b""
        return controle_de_audio_035(
            contador_de_quadros=self._quadros_mandados,
            com_microfone=self.quer_o_microfone(),
        )

    @property
    def intervalo_de_envio_s(self) -> float:
        """O intervalo entre reports, em segundos — o MEDIDO quando existe.

        **O nominal está errado para o `0x35`, e essa é a razão deste caminho.**
        Um quadro Opus carrega 10 ms de som, mas o aparelho o consome a cada
        10,667 ms (512/48000): alimentá-lo pelo nominal daria 100 quadros/s num
        aparelho que come 93,75, que é a taxa de estouro pela qual esta casa
        passou nove vezes.
        """
        medido = self.arranjo.intervalo_de_envio_s
        if medido is not None:
            return float(medido)
        return self.ms_por_report / 1000.0

    def escrever(self, report: bytes) -> bool:
        """Entrega o report ao escritor. **Seco, devolve True sem escrever.**

        O `True` do modo seco não é mentira e não polui a contagem: ele diz *"a
        bomba seguiu"*, e o número que a pessoa vai citar é
        :attr:`ContagemDaBomba.escritas_aceitas_pelo_kernel`, que só sobe
        quando um byte de verdade saiu.
        """
        if self.seco or self.escritor is None:
            return True
        try:
            escritos = int(self.escritor(report))
        except OSError as erro:
            self.contagem.escritas_recusadas += 1
            logger.info("som_escrita_recusada", erro=str(erro))
            return False
        self.contagem.escritas_aceitas_pelo_kernel += 1
        self.contagem.bytes_escritos += escritos
        return True

    def rodar(
        self,
        *,
        segundos: float,
        agora: Callable[[], float] | None = None,
        dormir: Callable[[float], None] | None = None,
    ) -> ContagemDaBomba:
        """O laço, por `segundos` de relógio. Devolve a contagem.

        **O ritmo é o da FONTE, e não um `sleep` nosso.** `pw-record` entrega
        no tempo real do nó: pedir 1920 bytes bloqueia até haver 10 ms de som.
        Um `sleep` por cima disso somaria dois relógios e produziria
        subcorrida — a mesma classe de defeito do lado da entrada. O `dormir`
        existe só para a fonte que NÃO tem ritmo próprio (um arquivo, um
        dublê), e por omissão ele não é chamado.
        """
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
    """Uma fonte de PCM que lê de um descritor já aberto (pipe, arquivo).

    Lê **até completar** o pedido, e só devolve curto quando o descritor
    realmente acabou: um `read()` de pipe devolve o que já chegou, e um único
    `read` por report cortaria todo quadro em pedaços de tamanho variável — o
    encoder recusaria cada um deles e a bomba contaria 100% de recusa sobre uma
    fonte sã.
    """

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
    ms_por_report: int,
    agora: Callable[[], float] | None = None,
    dormir: Callable[[float], None] | None = None,
) -> Callable[[int], bytes]:
    """Dá RITMO a uma fonte que não tem — e sem ela o ensaio vira uma inundação.

    **O DEFEITO QUE ELA MATA, medido em 07/09/2026 antes de qualquer escrita.**
    A bomba anda no ritmo da fonte, e isso é certo para o monitor de um nó do
    PipeWire: pedir 20 ms de som bloqueia 20 ms. Uma fonte SINTÉTICA (o timbre
    do ensaio de bancada, um arquivo já em memória) não bloqueia nada — ela
    devolve na hora. Medido nesta árvore: a montagem fecha **2.660 reports por
    segundo**, contra os **50/s** que o degrau ``0x39`` pede. Sem ritmo, quatro
    segundos de ensaio jogariam ~10.600 reports e ~5,8 MB no enlace de rádio —
    **53 vezes** o necessário, num rádio que carrega os outros controles dela.

    Isso não seria um ensaio: seria uma inundação medindo a fila do kernel.

    **O RELÓGIO É DE PRAZO, NÃO DE SONO.** Dormir ``ms_por_report`` depois de
    cada quadro soma o tempo de codificar e escrever ao intervalo, e o fluxo
    atrasa um pouco a cada volta — 2.660/s vira algo abaixo de 50/s, com deriva
    que cresce. Aqui cada quadro tem um PRAZO absoluto e o sono é o que falta
    para ele; quadro atrasado não dorme nada, e o próximo prazo não se perde.
    """
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
    """Um escritor que entrega no hidraw aberto em `fd`.

    Ele existe para que :class:`BombaDeSomPeloRadio` **não conheça o hidraw**:
    quem abre o nó (e quem decide se abre pelo broker ou por `os.open`) é o
    ensaio, que é onde moram a recusa por transporte e a conferência do MAC.
    """

    def _escrever(dados: bytes) -> int:
        return os.write(fd, dados)

    return _escrever


# ---------------------------------------------------------------------------
# Diagnóstico — por que o nó sobe, ou por que não sobe
# ---------------------------------------------------------------------------


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
    """O nome do módulo está na camada de compatibilidade Pulse do PipeWire?

    ``pactl list modules short`` só lista o que está CARREGADO; carregar um
    módulo só para descobrir se ele existe seria mexer no som dela para
    responder uma pergunta de diagnóstico. Procurar o nome dentro do ``.so`` é
    a mesma técnica que a entrada usa para o ``module-pipe-source``.
    """
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
        # Inclui `OpusIndisponivelError` e qualquer .so exótica que não exporte
        # o símbolo: um diagnóstico nunca derruba quem o chama.
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


# ---------------------------------------------------------------------------
# A ROTA DO NÓ — «onde este nó entrega?», e a pergunta tem UM dono
#
# POR QUE ELA MORA AQUI E NÃO EM `app/audio_saida.py`, onde nasceu:
# **o daemon não importa nada de `app/`**, e a régua é `grep -r "from
# hefesto_dualsense4unix.app" src/…/daemon/` devolvendo zero
# (`integrations/fontes_de_captura.py`, que fez este mesmo movimento em
# 01/09). Quem precisa da rota é o `AltoFalanteSubsystem`; deixar a resposta
# em `app/` obrigaria o daemon a escrever a SEGUNDA, e duas verdades sobre a
# mesma pergunta é como esta casa fabrica divergência silenciosa. O molde é o
# `app/usb_pai.py` → `integrations/usb_pai.py`: o dono muda de endereço e
# `app/audio_saida.py` REEXPORTA tudo, byte a byte da mesma resposta.
#
# ESTE BLOCO FICA NO FIM DO MÓDULO DE PROPÓSITO: o `docs/data/mapa-controles.csv`
# cita este arquivo por `arquivo:LINHA` (`:268`, `:455`, `:523`), e código novo
# enfiado acima daquelas linhas envelhece a citação inteira. Há portão que
# reprova: `citacoes-de-linha`.
# ---------------------------------------------------------------------------

#: As duas FONTES que ela nomeou em 08/09/2026: *"os somns seja hdmi completo
#: seja o canal do sfx caindo pra cada controle"*. <!-- noqa-acento: citação literal dela -->
#:
#: * ``mix`` — o *«HDMI completo»*: o mix inteiro da saída padrão do sistema
#:   cai também no controle, por um ``module-loopback`` do monitor dela;
#: * ``sfx`` — só o que o jogo mandar para o nó DAQUELE controle. O nó fica
#:   livre, e nenhum loopback de entrada é carregado.
#: Quem sabe dizer a `fonte` (`mix`/`sfx`) de um controle. O
#: `AltoFalanteSubsystem` o instala ao subir e o retira ao descer, no mesmo
#: padrão de gancho do numerador de assento e do ouvinte do microfone.
#:
#: **POR QUE UM GANCHO E NÃO UMA LEITURA:** quem PERGUNTA é o `state_full`, que
#: roda a cada tique; quem SABE lê o perfil ativo do disco e mantém cache por
#: `(nome, mtime)`. Uma segunda leitura de perfil no laço do IPC seria a
#: tempestade de syscalls que esta casa já pagou uma vez — e, pior, um segundo
#: dono da mesma resposta.
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

#: O padrão quando o perfil não diz nada. **Decisão DELA, 08/09/2026**
#: (``D-0809-NO-CABO-O-PADRAO-DO-SOM-E-SFX``, palavra dela: *"concordo com as
#: 5"*): com ``mix`` por padrão o controle viraria saída de todo o som do PC
#: sozinho, que é a regra que esta casa já recusou.
FONTE_PADRAO = FONTE_SFX

# ---------------------------------------------------------------------------
# A PONTE HOST -> CONTROLE POR RÁDIO — uma por controle
# ---------------------------------------------------------------------------


def a_ponte_do_radio_sabe_montar() -> bool:
    """O Hefesto sabe montar o pacote de áudio que o controle entende sem fio?

    **SIM DESDE 10/09/2026**, e esta função existe porque a resposta mudou.
    Até então o produto respondia *não* em três lugares — a frase da tela, a
    recusa de :func:`rota_do_no` e a célula do mapa —, e a razão era verdadeira:
    ninguém sabia qual dos nove degraus carregava áudio.

    Agora sabe: :data:`ARRANJO_035`, medido com som audível por 70 s.

    **Ela não pergunta se a ponte SOBE** — isso depende da `libopus`, do hidraw
    e do controle estar na mesa. Pergunta se o CONHECIMENTO existe, que é outra
    coisa e era exatamente o que faltava.
    """
    return True


def a_ponte_do_radio_pode_subir() -> tuple[bool, str]:
    """Esta máquina consegue subir a ponte AGORA? `(pode, por quê não)`.

    Separada de :func:`a_ponte_do_radio_sabe_montar` de propósito: *"não sei
    montar"* e *"sei, mas falta a libopus nesta máquina"* pedem recados
    diferentes, e juntá-las foi o que fez a tela dizer, por semanas, que o
    aparelho não podia — quando quem não podia éramos nós.
    """
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
    """O sink tem stream tocando AGORA? É por aqui que se sabe se o jogo usa.

    O endpoint da háptica fica publicado o tempo todo — nó que some quebra o
    jogo que o escolheu, decisão dela de 08/09 —, mas o escritor do controle é
    UM SÓ: enquanto o jogo não estiver tocando nele, quem manda no fio é o
    caminho do alto-falante.

    **QUEM TOCA É UM SINK-INPUT, NÃO O ESTADO DO SINK — 18/09/2026.** A
    pergunta era o `RUNNING` do sink, e no PipeWire um LEITOR segura o nó em
    `RUNNING` — a casa mediu isso com o `parec` na source do cabo
    (`canal_do_microfone`), e o monitor de um sink é lido do mesmo jeito. No
    modo háptica a própria ponte lê o monitor deste endpoint: fechado o jogo, o
    sink seguia `RUNNING` por nossa causa, a ponte nunca voltava ao som e o
    alto-falante do controle ficava mudo até reconectar. O nosso gravador é
    source-output; stream TOCANDO no sink é sink-input, e só o jogo o cria. A
    coluna 2 de `list short sink-inputs` é o índice do sink, o mesmo da coluna
    1 de `list short sinks`, no `pipewire-pulse` e no PulseAudio.

    **SERVIDOR MUDO NÃO É "NINGUÉM TOCA".** O ``None`` do runner é o prazo
    estourado ou o `pactl` que falhou: não se sabe. ``na_duvida`` é a
    resposta nesse caso. O modo da ponte usa o padrão, ``False``: na dúvida, o
    fio volta ao alto-falante. Quem pergunta para DERRUBAR o nó (a reancoragem
    do subsystem) passa ``True``: na dúvida, o nó fica, porque derrubá-lo com o
    jogo aberto nele é o que a decisão de 08/09 proíbe. Resposta VAZIA não é
    dúvida: o servidor respondeu que não há sink ou que não há stream.
    """
    if not nome:
        return False
    tocando = sinks_que_tocam([nome], runner, na_duvida=None)
    if tocando is None:
        return na_duvida
    return nome in tocando


#: O PISO DOS MOTORES no sink de 4 canais do DualSense — HAPTICA-CABO-VOLUME-01
#: (Z2), medido no aparelho dela em 19/09/2026 com o controle NO CABO:
#:
#:     repouso            tremor =   20
#:     40% (como nasce)   tremor =   67
#:     100%               tremor = 1093     <- 16x mais forte
#:
#: O WirePlumber dá **40% nos quatro canais** a todo sink novo (-23,88 dB), e
#: os canais 3-4 são os MOTORES: a háptica do DualSense viaja como áudio nos
#: traseiros. Nenhuma linha do produto pedia outra coisa, então a vibração dos
#: jogos da Sony saía 16x mais fraca — **em qualquer computador**, porque o
#: valor vem do servidor de som e não do nosso código.
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
    """Levanta os canais TRASEIROS do sink ao piso. True = havia o que levantar.

    HAPTICA-CABO-VOLUME-01 (Z2), 19/09/2026 — o espelho de
    `audio_saida.garantir_saida_audivel`, que faz o mesmo para o MUTE e nasceu
    do mesmo tipo de achado: o produto obedecia e o servidor de som calava.

    **SÓ OS TRASEIROS, E OS DA FRENTE NUNCA SÃO TOCADOS**, e a razão não é
    cautela — é que são coisas diferentes:

    ===============  ==========================  =============================
    canais           o que são                   quem escolhe o valor
    ===============  ==========================  =============================
    1-2 (frente)     o alto-falante do controle  **ELA**, e o produto respeita
    3-4 (traseiros)  os MOTORES da vibração      a aba Vibração, por HID
    ===============  ==========================  =============================

    Ninguém escolhe "o volume dos motores" no mixer do sistema: a intensidade
    da vibração tem dono próprio no produto. Levantar os traseiros não atropela
    escolha nenhuma — é o mesmo raciocínio do mute de 04/08, onde um estado
    herdado de outra sessão não é uma opinião sobre o pedido de agora.

    **NÃO É IDEMPOTENTE POR TEIMOSIA:** só escreve quando algum traseiro está
    ABAIXO do piso. O valor persiste no WirePlumber, então age uma vez por
    sink e cala. Sem essa guarda, uma reconciliação a cada 5 s viraria uma
    escrita a cada 5 s.
    """
    volumes = volumes_do_sink(nome, runner)
    if not volumes or len(volumes) < 4:
        return False  # sink estéreo ou servidor mudo: não é caso deste piso
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
    """Quais destes sinks têm stream tocando AGORA — **numa passada só**.

    HAPTICA-RADIO-INICIO-01, 19/09/2026. Esta é a forma plural de
    :func:`sink_esta_tocando`, e ela existe por um número: cada resposta custa
    DOIS `pactl` (`list short sinks` e `list short sink-inputs`), medidos em
    2,9 ms e 2,6 ms nesta máquina. Perguntando um por um, a volta de quatro
    controles gasta OITO subprocessos; perguntando de uma vez, gasta DOIS — o
    custo deixa de crescer com o número de controles na mesa.

    É isso que torna o vigia de modo possível sem multiplicar as chamadas ao
    servidor de som, que é a ressalva escrita na sprint.

    ``None`` = **não se sabe** (prazo estourado, `pactl` que falhou), e é
    diferente de conjunto vazio, que é o servidor respondendo *"ninguém toca"*.
    Quem chama decide o que fazer com a dúvida — `sink_esta_tocando` devolve o
    ``na_duvida`` dele, e o vigia do modo NÃO MEXE em ponte nenhuma.
    """
    alvos = {n for n in nomes if n}
    if not alvos:
        return set()
    correr: Any = runner or rodar_pactl
    sinks = correr(["pactl", "list", "short", "sinks"])
    if sinks is None:
        return na_duvida
    #: índice do sink -> nome, só para os alvos. A coluna 2 de `sink-inputs` é
    #: o índice do sink, o mesmo da coluna 1 de `sinks` — no `pipewire-pulse`
    #: e no PulseAudio.
    por_indice: dict[str, str] = {}
    for linha in sinks.splitlines():
        campos = linha.split("\t")
        if len(campos) > 1 and campos[1] in alvos:
            por_indice[campos[0].strip()] = campos[1]
    if not por_indice:
        return set()
    entradas = correr(["pactl", "list", "short", "sink-inputs"])
    if entradas is None:
        return na_duvida
    tocando: set[str] = set()
    for linha in entradas.splitlines():
        campos = linha.split("\t")
        if len(campos) > 1:
            alvo = por_indice.get(campos[1].strip())
            if alvo is not None:
                tocando.add(alvo)
    return tocando


def fonte_do_monitor_do_no(
    id_do_no: str,
    *,
    uniq: str,
    papel: str = "som",
    abrir: Callable[[list[str]], Any] | None = None,
    taxa: int = TAXA_DO_ENCODER,
    canais: int = CANAIS_DO_ENCODER,
) -> tuple[Callable[[int], bytes] | None, Any, str]:
    """`(fonte de PCM, processo, motivo)` lendo o monitor do nó DAQUELE controle.

    A fonte é o `.monitor` do `module-null-sink` que o `SinkVirtualPipeWire`
    publica — ou seja, **o que o jogo mandou para aquele controle**, e nada
    mais. Um `--target` vazio cairia na saída padrão do sistema e o controle
    tocaria o som da máquina inteira; `argv_do_gravador` recusa isso.

    O processo volta junto porque quem sobe tem de poder derrubar: um
    `pw-record` órfão continua lendo o monitor depois de a ponte cair.

    **ELE NASCE PRESO AO PAI e o ramo sem `stdout` o COLHE — SOM-TRAVA-NA-
    QUEDA-01, 13/09/2026.** O lançamento é o do dono único,
    :func:`~hefesto_dualsense4unix.integrations.filho_de_som.lancar_leitor`,
    com `PR_SET_PDEATHSIG`: sem ele, um daemon morto por SIGKILL com o gravador
    ocioso deixava o `pw-record` com `ppid 1`. E um gravador sem `stdout` não
    tem quem o leia nem quem o derrube: ele é colhido aqui, antes de voltar.
    """
    from hefesto_dualsense4unix.integrations.filho_de_som import (
        derrubar_leitor_de_pipe,
        lancar_leitor,
    )

    if not id_do_no:
        return None, None, "o controle não tem nó de som publicado"
    rotulo = rotulo_do_gravador(uniq=uniq, papel=papel)
    if not rotulo:
        return None, None, "sem `uniq` não há rótulo único para o gravador"
    argv = argv_do_gravador(f"{id_do_no}.monitor", rotulo=rotulo, taxa=taxa, canais=canais)
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

    # SOM-ECO-02 (16/09/2026) — A CONFERÊNCIA, e ela é a metade que morde.
    #
    # `argv_do_gravador` resolve o `object.serial` ANTES de o processo subir, e
    # entre resolver e conectar o nó pode sumir. Quando o alvo não resolve, o
    # PipeWire liga o gravador à FONTE PADRÃO **sem erro nenhum** — e a fonte
    # padrão desta máquina é o microfone do controle. Foi assim que a ponte
    # passou a mandar a VOZ DELA para o alto-falante do próprio controle.
    #
    # Então não basta pedir certo: tem de conferir o que veio. Um gravador
    # ligado ao nó errado é DERRUBADO aqui — som nenhum é melhor que a voz dela
    # voltando, e o caminho de cima já sabe seguir sem ponte.
    #
    # `None` do conferidor é "não conferido", NUNCA "está certo": sem `pw-link`,
    # com ele em recuo ou com a saída ilegível, a ponte SOBE e o journal diz que
    # ninguém olhou. Derrubar a ponte por não ter conseguido olhar trocaria um
    # defeito raro por um mudo garantido.
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
    """Do monitor do nó ao alto-falante do controle, por rádio. Uma por controle.

    **É a peça que faltava**, e a lista do que já existia mostra o tamanho dela:
    :class:`CodificadorOpus` codifica desde 06/09, :class:`SinkVirtualPipeWire`
    publica o nó desde 06/09, :class:`BombaDeSomPeloRadio` monta e escreve, e
    :data:`ARRANJO_035` diz o layout desde 10/09. Ninguém ligava os quatro por
    controle — e sem isso o nó publicado era um sumidouro.

    **A IDENTIDADE É O ``uniq``, NUNCA O ``hidrawN``.** O número do nó muda a
    cada reconexão; o endereço do controle não. É a mesma regra que
    :func:`sink_do_controle` já segue no cabo.

    Ela **não decide** se deve subir: quem decide é o subsystem, com a lista de
    controles na mão. Ela sobe, roda e desce.
    """

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
    ) -> None:
        self.uniq = uniq
        self._abrir_hidraw = abrir_hidraw
        self._fonte = fonte_de_pcm
        #: A fonte da HÁPTICA, quando este controle tem endpoint publicado. Ela
        #: entra na MESMA bomba de propósito: dois escritores no mesmo controle
        #: disputam o nibble de sequência e os enables, e foi assim que o
        #: microfone ficou desligado 93 vezes por segundo em 10/09.
        self._fonte_da_haptica = fonte_de_haptica
        #: O `pw-record` do monitor da háptica, colhido junto com o do som.
        self._gravador_da_haptica = gravador_da_haptica
        self.arranjo = arranjo or ARRANJO_PADRAO
        self.rota = rota
        #: Repassado à bomba sem `bool()`: um chamável tem de chegar VIVO lá,
        #: senão `bool(f)` o congela em `True` — a função existe, logo é
        #: verdadeira — e o microfone ficaria ligado para sempre.
        self.com_microfone = com_microfone
        self._seco = bool(seco)
        self._bomba: BombaDeSomPeloRadio | None = None
        self._thread: threading.Thread | None = None
        #: O `pw-record` do monitor, quando a fonte veio de um. Ele morre com a
        #: ponte: um gravador órfão continua lendo o monitor do nó depois de a
        #: ponte cair, e o próximo `subir()` acharia a fonte já consumida.
        self._gravador: Any | None = gravador
        #: Como o gravador morreu no último `descer()` (`filho_de_som.ComoMorreu`),
        #: para o diário e para a régua. `None` = ainda não desceu com gravador.
        self.como_morreu_o_gravador: Any | None = None
        #: O SINAL É POR CORRIDA, NUNCA REUSADO — cura de 10/09/2026. Um
        #: `Event` só, com `clear()` no `subir()`, RESSUSCITA a thread da
        #: corrida anterior que ainda não morreu: ela testa `not
        #: _parar.is_set()` e volta a bombear, no fd da corrida NOVA.
        self._parar: threading.Event | None = None
        #: Por que a ponte não subiu. Vazio enquanto ela está de pé — a tela e
        #: o log leem daqui em vez de adivinhar.
        self.motivo: str = ""

    def esta_de_pe(self) -> bool:
        """A ponte está no ar para ESTE controle, **e continuará**?

        É este o callable que :func:`rota_do_no` recebe em ``ponte_do_radio``,
        e é ele que decide se o nó do PipeWire publica rota.

        **DESCENDO NÃO É DE PÉ — 10/09/2026.** A thread viva não basta: depois
        de um `descer()` cujo `join` estourou, ela ainda respira mas já foi
        mandada parar, e vai sair no próximo tique. Responder *de pé* ali fazia
        duas coisas erradas de uma vez: o nó publicava rota para um som que não
        vai mais sair, e `subir()` devolvia `True` sem subir nada — a chamada
        parava no atalho do topo e a corrida morria em seguida, calada.

        Quem precisa saber se a THREAD ainda respira — para não abrir um fd por
        cima dela — pergunta a `_corrida_viva`, e é o que `subir()` faz.
        """
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
        # A CORRIDA ANTERIOR AINDA ESTÁ MORRENDO — 10/09/2026, e subir por cima
        # dela é o defeito. `descer()` desiste do `join` depois do prazo, e uma
        # thread presa num `read` bloqueante da fonte continua viva: abrir um fd
        # novo aqui dava ao kernel o MESMO número recém-liberado, e as duas
        # corridas passavam a escrever no mesmo descritor, ao dobro da cadência.
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
        self._bomba = BombaDeSomPeloRadio(
            arranjo=self.arranjo,
            fonte=self._fonte,
            escritor=escritor_de_hidraw(fd),
            tag_audio=self.rota,
            seco=self._seco,
            com_microfone=self.com_microfone,
            fonte_haptica=self._fonte_da_haptica,
        )
        # O fd e o sinal VÃO COM A THREAD, e é isso que impede a corrida velha
        # de escrever (ou de fechar) o descritor da corrida nova.
        self._thread = threading.Thread(
            target=self._laco,
            args=(fd, parar),
            name=f"som-radio-{self.uniq[:6]}",
            daemon=True,
        )
        self._thread.start()
        self.motivo = ""
        logger.info(
            "som_radio_ponte_de_pe",
            uniq=self.uniq,
            arranjo=self.arranjo.nome,
            reports_por_segundo=round(1.0 / self._bomba.intervalo_de_envio_s, 2),
        )
        return True

    def _laco(self, fd: int, parar: threading.Event) -> None:
        """O laço da bomba, até mandarem parar ou a fonte secar.

        **O ritmo é o da FONTE**, como em :meth:`BombaDeSomPeloRadio.rodar`: o
        monitor do nó entrega no tempo real. O `dormir` só entra para fonte sem
        ritmo próprio, e aí ele usa a cadência MEDIDA do arranjo.
        """
        bomba = self._bomba
        if bomba is None:
            os.close(fd)
            return
        try:
            while not parar.is_set():
                report = bomba.um_report()
                if report is None:
                    logger.info("som_radio_fonte_secou", uniq=self.uniq)
                    break
                if report and not bomba.escrever(report):
                    logger.info("som_radio_escrita_recusada", uniq=self.uniq)
                    break
        finally:
            # O FD É DESTA CORRIDA, e ela fecha o DELA. Fechar `self._fd` aqui
            # era o quarto elo do defeito de 10/09: a thread velha, ao sair,
            # fechava o descritor que a ponte NOVA tinha acabado de abrir.
            try:
                os.close(fd)
            except OSError:
                logger.debug("som_radio_fd_ja_fechado", uniq=self.uniq)

    def descer(self, *, esperar_s: float = 1.0) -> bool:
        """Para o laço e espera a thread juntar. Idempotente.

        Devolve `True` se a corrida acabou de verdade. `False` diz que a thread
        NÃO morreu no prazo — e aí a ponte continua se declarando de pé, de
        propósito: `esta_de_pe()` lendo `is_alive()` é o que impede um `subir()`
        seguinte de abrir um fd por cima de uma corrida ainda viva.

        **QUEM FECHA O FD É A THREAD**, no `finally` do laço. Fechá-lo aqui,
        depois de um `join` que estourou, entregava ao kernel um número que a
        corrida viva ainda usava — e o próximo `open` de qualquer parte do
        daemon receberia esse mesmo número, com os 334 B do report indo para
        dentro dele.

        **O GRAVADOR É COLHIDO AQUI, e não só avisado — SOM-TRAVA-NA-QUEDA-01,
        13/09/2026.** Até esta data este método só mandava `terminate` ao
        `pw-record`. Na queda do controle o laço já saiu (a escrita no hidraw
        foi recusada), ninguém lê o cano, ele enche em 0,34 s, e o SIGTERM fica
        pendente para sempre: medido no estudo da sprint, este método voltava
        em 0 ms com o gravador vivo, e o gravador sobrevivia ao nó. Quem
        derruba agora é
        :func:`~hefesto_dualsense4unix.integrations.filho_de_som.derrubar_leitor_de_pipe`,
        na ordem medida: TERM, `join` desta thread com `esperar_s`, o `stdout`
        fechado SÓ com o laço já parado (SIGPIPE em 1,1 ms), `wait`, KILL,
        `join` de novo. Com o laço vivo o `stdout` não fecha, pela mesma razão
        do fd do hidraw acima. Como ele morreu vai para o diário.
        """
        from hefesto_dualsense4unix.integrations.filho_de_som import (
            derrubar_leitor_de_pipe,
        )

        parar = self._parar
        if parar is not None:
            parar.set()
        gravador, self._gravador = self._gravador, None
        # O GRAVADOR DA HÁPTICA MORRE JUNTO, e pela mesma razão do outro: um
        # `pw-record` órfão continua lendo o monitor depois de a ponte cair, e
        # o próximo `subir()` acharia a fonte já consumida. Ele é colhido
        # ANTES, porque quem segura a thread é a leitura bloqueante — e no
        # arranjo da háptica a fonte que bloqueia é esta.
        haptico, self._gravador_da_haptica = self._gravador_da_haptica, None
        if haptico is not None:
            derrubar_leitor_de_pipe(haptico, junta_s=esperar_s)
            logger.info("haptica_radio_gravador_colhido", uniq=self.uniq)
        thread = self._thread
        if gravador is not None:
            como = derrubar_leitor_de_pipe(gravador, leitor=thread, junta_s=esperar_s)
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
            return True
        if thread.is_alive() and gravador is None:
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


#: Rádio, e a ponte host→controle não está de pé NESTE MOMENTO. **Não é falha
#: do aparelho** — o alto-falante existe, ela já o OUVIU pelo cabo (rota 3,
#: orelha dela, 02/08/2026) e **pelo rádio** (70 s contínuos, 10/09/2026).
#:
#: **A FRASE ANTERIOR CADUCOU EM 10/09/2026, e ela dizia uma coisa falsa.** O
#: texto era: *"o Hefesto sabe por qual canal mandar, mas ainda não sabe montar
#: o pacote de áudio que o controle entende sem fio"*. **Ele sabe** — é o
#: :data:`ARRANJO_035`, medido com som audível. Enquanto a frase viveu, a tela
#: dela atribuía ao aparelho um limite que era nosso.
#:
#: A frase de hoje diz o que é verdade: o caminho existe, e a ponte deste
#: controle não está no ar agora. Quando a razão for conhecida (falta a
#: `libopus`, o hidraw não abriu), quem a tem é
#: :attr:`PonteDeSomPorRadio.motivo` — e ela é mais precisa que este texto.
MOTIVO_NO_SEM_PONTE_NO_RADIO = (
    "o som do PC ainda não está saindo neste controle pelo rádio — o caminho "
    "existe e já foi ouvido, e o que falta é a ponte deste controle subir. "
    "Ligue-o no cabo para ouvir por ele enquanto isso."
)

#: E O CASO EM QUE O CONHECIMENTO NÃO EXISTISSE — a frase que a tela mostraria
#: se :func:`a_ponte_do_radio_sabe_montar` voltasse a responder `False`. Ela é
#: a frase que viveu até 10/09/2026, guardada aqui com a razão certa: *não é o
#: aparelho que não pode; somos nós que não sabemos*. Enquanto ela existir
#: como constante, ninguém precisa redigitá-la de memória — e a diferença
#: entre os dois recados fica ONDE ela pertence, que é no código que decide.
MOTIVO_NO_SEM_SABER_MONTAR = (
    "o Hefesto ainda não sabe montar o pacote de áudio que este controle "
    "entende sem fio. Não é limite do aparelho: ligue-o no cabo para ouvir "
    "por ele enquanto isso."
)

#: Cabo, e o sistema não publicou placa de som atribuível a este controle. É o
#: caso do controle recém-ligado, e o do cabo que só alimenta.
MOTIVO_NO_SEM_PLACA_NO_CABO = (
    "o sistema ainda não publicou a placa de som deste controle, e sem ela não "
    "há por onde o som entrar. Reconecte o cabo do controle."
)

#: Nem assento nem controle: não há nó nenhum de que falar.
MOTIVO_NO_SEM_ASSENTO = (
    "este controle ainda não tem um lugar de jogador, e o alto-falante leva o "
    "número do lugar. Reconecte o controle."
)

#: Por onde o nó entrega, quando entrega. ``""`` é "não entrega".
POR_CABO = "cabo"
POR_RADIO = "radio"

#: Os dois transportes, com a palavra do sysfs (a da TELA é *cabo* e *rádio*).
TRANSPORTE_CABO = "usb"
TRANSPORTE_RADIO = "bt"

#: Toda palavra que esta casa usa para dizer *"este controle está no ar"* —
#: e são QUATRO, escritas em lugares diferentes por gente diferente.
#:
#: **ISTO NASCEU DE UM DEFEITO MEDIDO EM 09/09/2026**, na primeira passada seca
#: com os quatro DualSense dela na mesa. ``daemon/subsystems/alto_falante
#: .ControleNaLista.transporte`` diz ``"rádio"`` (a palavra da TELA, com
#: acento); ``app/audio_saida`` diz ``"bt"`` (a palavra do ``state_full``). O
#: ``rota_do_no`` comparava com UMA delas, então os dois controles do rádio
#: caíam no ramo do CABO e recebiam a frase errada:
#:
#:     "o sistema ainda não publicou a placa de som deste controle (…)
#:      Reconecte o cabo do controle."
#:
#: — mandando ela mexer num cabo que não existe, quando a verdade é que a ponte
#: de rádio ainda não monta o pacote de áudio. **A frase certa é a metade do
#: valor do nó sem rota**, e uma comparação de texto a trocava em silêncio.
_PALAVRAS_DE_RADIO = frozenset({"bt", "radio", "rádio", "bluetooth"})


def e_radio(transporte: str) -> bool:
    """Este transporte é o rádio? Aceita as quatro palavras da casa.

    Peneira e não tabela de tradução de propósito: a pergunta que esta camada
    faz é binária, e uma tabela convidaria alguém a guardar a palavra traduzida
    — que é como o transporte entra na identidade do nó, o defeito que ele
    existe para não ter.
    """
    return str(transporte or "").strip().lower() in _PALAVRAS_DE_RADIO

#: Os canais do sink do controle por onde o alto-falante interno toca. O mapa
#: (``docs/data/mapa-controles.csv``, ``audio.alto_falante@dualsense``,
#: ``cabo_canal``) registra: *canais 1-2 do sink
#: ``alsa_output.usb-...analog-surround-40``*. Numa placa ``surround-40`` os
#: canais 1 e 2 são ``front-left`` e ``front-right`` — é este o nome que o
#: PipeWire entende, e por isso o número da célula vira nome aqui, sem virar
#: uma segunda verdade.
CANAIS_DO_ALTO_FALANTE = "front-left,front-right"


@dataclass(frozen=True)
class RotaDoNo:
    """Para onde o nó entrega — e, quando não entrega, a frase que diz por quê.

    NÃO É ``bool``: um ``False`` cru vira "não aconteceu nada" na tela, que é o
    silêncio que ela reclamou.
    """

    tem_rota: bool
    sink: str = ""
    por_onde: str = ""
    motivo: str = ""
    fonte: str = FONTE_PADRAO
    monitor_do_mix: str = ""


def assinatura_da_rota(rota: RotaDoNo | None) -> tuple[bool, str, str, str]:
    """A identidade ESTÁVEL de uma rota: mudou isto, a fiação é outra.

    Quem a usa é :meth:`SinkVirtualPipeWire.religar`, para responder *"o que
    está ligado ainda é o que o perfil pede?"* sem tocar no nó quando a
    resposta é sim.

    **O QUE FICA DE FORA É METADE DO VALOR DESTA FUNÇÃO.**

    ``monitor_do_mix`` fica de fora, e a razão é medida: ele é o monitor da
    SAÍDA PADRÃO do sistema. Muda quando ela troca o som da TV para o fone, e
    vira ``""`` sempre que o servidor de som hesita
    (:func:`monitor_da_saida_padrao` recusa em recuo). Compará-lo poria a
    varredura a religar o nó a cada troca de saída dela — e, com o servidor
    soluçando, a derrubar o ``module-loopback`` que estava funcionando por
    causa de um ``""`` de dois segundos.

    ``motivo`` fica de fora pela mesma família: é TEXTO para a tela, e frase
    nova não é fiação nova.

    **O QUE ISSO DEIXA ABERTO, escrito para ninguém descobrir sozinho:** um nó
    que nasceu em ``mix`` com o servidor mudo não achou monitor, logo não ligou
    o loopback do mix, e a assinatura dele já diz ``mix`` — a varredura não vai
    religá-lo. Ele espera a próxima troca dela. O preço do contrário seria
    religar a cada soluço do servidor, que custa o som que está tocando.
    """
    if rota is None:
        return (False, "", "", "")
    return (
        bool(rota.tem_rota),
        str(rota.por_onde or ""),
        str(rota.sink or ""),
        str(rota.fonte or ""),
    )


def _sink_proprio_vivo(uniq: str, saida_curta: str) -> str:
    """``hefesto_som_<hex6>`` deste controle, se ele estiver na lista viva.

    Lê a MESMA saída de ``pactl list sinks short`` que o chamador já pediu — não
    há segunda leitura do servidor. O nome vem de :func:`nome_do_sink`, o dono
    único, e a conferência é por campo exato: um ``in`` na string casaria
    ``hefesto_som_c311f0`` dentro de ``hefesto_som_c311f0.monitor`` de uma lista
    de sources, e o monitor não é lugar para onde se manda som.
    """
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
    """O sink de SAÍDA deste controle — ``""`` quando não dá para saber.

    Quem DECIDE é ``fontes_de_captura.escolher_sink``; aqui só se juntam os
    ingredientes (a lista viva de sinks e o casamento por dispositivo USB).
    Escrever uma segunda regra de atribuição seria dar ao alto-falante do
    controle errado o som do PC.

    ``""`` é resposta honesta e frequente: é o RÁDIO.
    """
    from hefesto_dualsense4unix.integrations.fontes_de_captura import (
        CasamentoUSB,
        escolher_sink,
        sinks_dualsense,
    )

    if not uniq:
        return ""
    if _o_recuo().mudo():  # o servidor em recuo: o «não sei» vem sem esperar o prazo
        return ""
    ler = runner if runner is not None else _rodar
    curtos = ler(["pactl", "list", "sinks", "short"]) or ""
    # O NÓ QUE ESTA CASA PUBLICA CONTA COMO PLACA — 10/09/2026, queixa dela.
    # Antes desta linha a resposta pelo RÁDIO era `""` *enquanto o som do PC
    # saía pelo controle*: a ponte 0x35 lê o monitor de `hefesto_som_<hex6>`,
    # que o `AltoFalanteSubsystem` cria por controle, e três lugares que
    # perguntam "qual é o sink deste controle?" só sabiam dos `alsa_output` da
    # Sony. Daí a frase «este controle não publica placa de som» na tela dela
    # com a música tocando, o "Todo o som do PC" recusando e a onda do
    # alto-falante sem leitura — tudo pela mesma pergunta mal respondida.
    #
    # É RECUO, e não preferência: no CABO quem manda continua sendo
    # `escolher_sink` sobre as placas de verdade, porque lá o nó do Hefesto é
    # só a boca de um `module-loopback` que termina naquela mesma placa.
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
    """O monitor da saída padrão do sistema — a fonte do «HDMI completo».

    ``""`` quando o servidor não responde, e o ``""`` é recusa: ligar um
    loopback com origem vazia é o mesmo defeito do ``paplay --device=`` que
    este produto já pagou — o comando é aceito e o som vai para outro lugar.
    """
    if _o_recuo().mudo():  # o servidor em recuo: a mesma recusa, sem esperar o prazo
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


#: O último monitor recusado por laço, por controle. Existe só para o aviso sair
#: UMA vez por mudança: :func:`rota_do_no` roda a cada varredura de nó vivo
#: (``RECONCILIA_S``), e a mesma linha a cada cinco segundos enterraria o resto
#: do journal enquanto a saída padrão dela continuar sendo o controle.
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
    """Onde este nó entrega o áudio — ou a frase de por que ele não entrega.

    **No cabo** ele entrega nos canais 1-2 do sink USB DAQUELE controle, e quem
    resolve o sink é :func:`sink_do_controle` — pela identidade, nunca pelo
    texto do nome. Um ``startswith("alsa_output.usb-")`` aqui entrega o som do
    P2 no alto-falante do P1 assim que há dois no cabo.

    **No rádio** ele entrega à ponte host→controle quando ela existir —
    ``ponte_do_radio`` é quem responde se ela está de pé. ``None`` é o estado
    de hoje e o padrão de propósito: enquanto o payload dos degraus de OUTPUT
    por rádio não estiver identificado, quem chamar sem passar nada recebe a
    recusa honesta, e não um silêncio.
    """
    fonte = fonte if fonte in (FONTE_MIX, FONTE_SFX) else FONTE_PADRAO
    monitor = (
        monitor_da_saida_padrao(runner=runner) if fonte == FONTE_MIX else ""
    )
    if not uniq:
        return RotaDoNo(False, motivo=MOTIVO_NO_SEM_ASSENTO, fonte=fonte)
    if e_radio(transporte):
        if ponte_do_radio is not None and ponte_do_radio():
            # O mix que fecharia laço sai daqui com o monitor VAZIO e um aviso
            # no log, sem frase nova para a tela: `motivo` é texto dela. Ver
            # `o_mix_fecha_laco`, e a limitação herdada em `argv_das_rotas`.
            return RotaDoNo(
                True,
                por_onde=POR_RADIO,
                fonte=fonte,
                monitor_do_mix=_mix_sem_laco(uniq, "", monitor),
            )
        # DOIS «NÃO» DIFERENTES, E A TELA TEM DE SABER QUAL É — 10/09/2026.
        # *"não sei montar o pacote"* e *"sei, e a ponte deste controle não
        # está no ar"* pedem recados diferentes: o primeiro é limite NOSSO, o
        # segundo é estado de agora. Juntá-los foi o que fez a tela dela
        # atribuir ao aparelho, por semanas, um limite que era do produto.
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
    """O comando que faz o mix inteiro do PC cair TAMBÉM neste controle.

    É o *«HDMI completo»* dela: a origem é o monitor da SAÍDA PADRÃO, e o
    destino é o nó do controle. O sentido é o contrário do de
    :func:`argv_para_ligar_o_no`, e trocar os dois manda o som do controle para
    a televisão dela.
    """
    return (
        "pactl",
        "load-module",
        "module-loopback",
        f"source={monitor}",
        f"sink={id_do_no}",
    )


def argv_das_rotas(id_do_no: str, rota: RotaDoNo) -> tuple[tuple[str, ...], ...]:
    """Os ``module-loopback`` desta rota, na ordem em que sobem — () se não há.

    A SAÍDA primeiro e a FONTE depois, e a ordem é medida em consequência: com
    o mix entrando antes de haver por onde sair, o PCM do sistema inteiro fica
    parado no nó por um instante. Sem rota, tupla vazia — o nó existe e não
    engole nada de ninguém.

    **A TRAVA DO LAÇO MORA AQUI**, e não só em :func:`rota_do_no`: esta é a
    função pura por onde passam os DOIS chamadores — o daemon
    (:meth:`SinkVirtualPipeWire._ligar_a_rota`) e o plano da janela
    (``app/audio_saida.plano_de_publicacao``) —, e uma ``RotaDoNo`` montada à
    mão chega aqui sem ter passado por lá. Ver :func:`o_mix_fecha_laco`.

    **A LIMITAÇÃO HERDADA, escrita para ninguém descobrir sozinho:**
    :func:`assinatura_da_rota` ignora ``monitor_do_mix``, então um nó que foi
    religado com o mix recusado por laço não religa sozinho quando ela devolve a
    saída padrão à TV — ele espera a próxima troca de fonte dela. É o mesmo
    caso, já documentado lá, do nó que nasceu em ``mix`` com o servidor mudo.
    """
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
    """«Alto-falante do Controle N» — e SEM o endereço dela, com número ou sem.

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
    if numero is None:
        return NOME_DO_ALTO_FALANTE_DO_CONTROLE
    return f"{NOME_DO_ALTO_FALANTE_DO_CONTROLE} {numero}"


# ---------------------------------------------------------------------------
# O RECUO DO SERVIDOR — SOM-RECUO-01 (13/09/2026)
#
# NO FIM DO MÓDULO de propósito: o mapa e o `docs/data/ensaios.csv` citam
# linhas deste arquivo, e código novo enfiado lá em cima envelhece as citações.
# ---------------------------------------------------------------------------

if TYPE_CHECKING:
    from hefesto_dualsense4unix.integrations.dualsense_bt_audio import RecuoDoPactl

#: A SONDAGEM do som: a pergunta mais barata que o ``pipewire-pulse`` responde,
#: e a mesma com que quem coordena mediu o travamento de 13/09/2026 (``pactl
#: info`` com rc=124). Só sai quando um recuo VENCEU sem resposta desde então —
#: ver :func:`_o_servidor_atende`.
_SONDAGEM = ("pactl", "info")


def _o_recuo() -> RecuoDoPactl:
    """O recuo do SERVIDOR de som — o MESMO objeto do microfone, lido na hora.

    **Ser o mesmo é a cura.** O servidor é um só: um recuo só do microfone
    deixava o som batendo na mesma porta a cada 10 s (os números estão em
    ``dualsense_bt_audio.RecuoDoPactl``). Um prazo estourado aqui cala o
    microfone no ciclo seguinte, e o dele cala este.

    Lido NA HORA, nunca copiado para um global deste módulo: a régua troca o
    ``dualsense_bt_audio.PACTL`` por um de relógio de mentira, e um ``from …
    import PACTL`` no topo congelaria o objeto de antes.
    """
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
    """O `runner` de um nó, contando ao recuo do servidor o que houve com cada pergunta.

    O contrato mora em ``RecuoDoPactl.perguntar``, e o recuo é o de
    :func:`_o_recuo`, lido a cada pergunta.
    """

    def _perguntar(argv: list[str]) -> str | None:
        return _o_recuo().perguntar(runner, argv)

    return _perguntar


def _o_servidor_atende(runner: Callable[[list[str]], str | None], nome: str) -> bool:
    """Pode sair um `load-module` agora? O mesmo desenho do microfone.

    Três recusas, nesta ordem: sem ``pactl`` no sistema; o recuo em curso (nem
    se pergunta); e, com um recuo VENCIDO sem resposta desde então, a
    :data:`_SONDAGEM` que não respondeu. Sem recuo nenhum não há sondagem: o
    caminho de todo dia não ganha pergunta a mais.

    **O `parar()` NÃO passa por aqui, e é decisão:** o microfone deixa o módulo
    para ``VarredorDeCanaisOrfaos`` quando o servidor está mudo, e o som não
    tem varredor. Um ``module-null-sink`` deixado para trás é o fantasma de
    07/09/2026, e o prazo do descarregamento se paga uma vez por queda, não por
    ciclo.
    """
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
    """Os comandos da rota, um a um, até um prazo estourado pôr o servidor em recuo.

    O nó já subiu quando a rota começa. Um `module-loopback` que estoura o prazo
    não pode ser seguido pelo segundo, que esperaria mais 5 s na mesma fila.
    """
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
    "DEGRAU_DO_KERNEL",
    "ENABLES_COM_MIC",
    "ENABLES_SEM_MIC",
    "ENVELOPE_BYTES",
    "FONTE_MIX",
    "FONTE_PADRAO",
    "FONTE_SFX",
    "GRAVADORES_DO_MONITOR",
    "HEX_DO_SUFIXO",
    "INTERVALO_DE_ENVIO_035",
    "LATENCIA_DO_GRAVADOR_MS",
    "MOTIVO_NO_SEM_ASSENTO",
    "MOTIVO_NO_SEM_PLACA_NO_CABO",
    "MOTIVO_NO_SEM_PONTE_NO_RADIO",
    "MOTIVO_NO_SEM_SABER_MONTAR",
    "MS_POR_QUADRO",
    "NOME_DO_ALTO_FALANTE_DO_CONTROLE",
    "OFFSET_APOS_O_COMMON",
    "OFFSET_DO_COMMON",
    "ORCAMENTO_DO_DEGRAU",
    "POR_CABO",
    "POR_RADIO",
    "PREFIXO_SINK_DO_SOM",
    "PRIORIDADE_SESSAO_DO_SOM",
    "TAMANHO_DO_DEGRAU",
    "TAXA_DO_ENCODER",
    "TRANSPORTE_CABO",
    "TRANSPORTE_RADIO",
    "VOLTA_DA_SEQUENCIA",
    "VOLUME_QUE_ELA_OUVIU",
    "Arranjo",
    "BombaDeSomPeloRadio",
    "CodificadorOpus",
    "ContagemDaBomba",
    "Diagnostico",
    "PonteDeSomPorRadio",
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
    "degrau_para_payload",
    "descricao_do_alto_falante",
    "diagnosticar",
    "e_radio",
    "escritor_de_hidraw",
    "fonte_com_ritmo",
    "fonte_de_arquivo",
    "fonte_do_monitor_do_no",
    "monitor_da_saida_padrao",
    "montar_com_o_common_preservado",
    "montar_pelos_dois_arranjos",
    "nome_do_sink",
    "o_mix_fecha_laco",
    "o_servidor_e_o_pipewire",
    "orcamento_do_degrau",
    "propriedades_do_sink",
    "rodar_pactl",
    "rota_do_no",
    "rotulo_do_gravador",
    "serial_do_no",
    "sink_do_controle",
    "so_hex",
    "sufixo_do_sink_do_som",
    "tag_tlv",
    "versao_libopus",
]
