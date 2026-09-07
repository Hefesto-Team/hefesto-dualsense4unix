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
import os
import shutil
import subprocess
import threading
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

from hefesto_dualsense4unix.core.ds_output_report import (
    BT_CRC_SEED,
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
                "libopus não encontrada (instale libopus0 — ver install.sh)"
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
        # uma assinatura por request, e ctypes já passa int como int no ABI
        # desta plataforma. Só o retorno é fixado.
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
        self._lib.opus_encoder_ctl(ponteiro, OPUS_SET_VBR_REQUEST, ctypes.c_int32(0))
        self._lib.opus_encoder_ctl(
            ponteiro, OPUS_SET_BITRATE_REQUEST, ctypes.c_int32(bitrate_bps)
        )
        self._saida = ctypes.create_string_buffer(4000)

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
        # Háptico (dois sub-blocos do tamanho declarado).
        pkt[self.pos_tag_haptico] = tag_tlv(BLOCO_HAPTICS, duplo=True)
        pkt[self.pos_tag_haptico + 1] = self.len_haptico
        corpo = haptico[: self.len_haptico * 2]
        pkt[self.pos_haptico : self.pos_haptico + len(corpo)] = corpo
        # Áudio.
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

ARRANJO_POR_NOME: dict[str, Arranjo] = {a.nome: a for a in ARRANJOS}


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

#: PROVISÓRIO — decisão dela. O rótulo que aparece na lista de saída do
#: sistema é da **O-ALTO-FALANTE-VIRTUAL-01** (*"o nó com nome de gente"*), que
#: é a sprint da SUPERFÍCIE. Esta é o MOTOR. Até ela decidir, o nó nasce com um
#: rótulo neutro que diz o aparelho e o controle, e nada mais.
DESCRICAO_PROVISORIA = "Alto-falante do controle"

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

    Nunca ``shell=True`` (invariante do projeto) e sempre com timeout — um
    ``pactl`` pendurado num PipeWire morto não pode segurar o nó.

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
            capture_output=True,
            text=True,
            check=False,
            env={**os.environ, "LC_ALL": "C"},
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if proc.returncode != 0:
        return None
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
    ) -> None:
        self.uniq = str(uniq)
        self.nome = nome_do_sink(uniq)
        self.descricao = descricao or DESCRICAO_PROVISORIA
        self.taxa_hz = taxa_hz
        self.canais = canais
        self.runner = runner or _rodar
        self._module_id: str | None = None

    # -- ciclo de vida ----------------------------------------------------

    @property
    def module_id(self) -> str | None:
        """O id do módulo carregado, ou None se o nó não está de pé."""
        return self._module_id

    def iniciar(self) -> bool:
        """Carrega o ``module-null-sink``. False = não deu (e nada ficou de pé).

        Recusa sem nome: um ``uniq`` ilegível não vira nó. Ausência é resposta.
        """
        if self._module_id is not None:
            return True
        if not self.nome:
            logger.info("som_sem_identidade", uniq=self.uniq)
            return False
        if shutil.which("pactl") is None:
            logger.info("som_sem_pactl")
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
        return True

    def parar(self) -> None:
        """Descarrega o módulo. Idempotente."""
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
        if self._module_id is None:
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
                "para o rádio (instale libopus0, ver install.sh)"
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


__all__ = [
    "AMOSTRAS_POR_QUADRO",
    "ARRANJOS",
    "ARRANJO_DS5DONGLE",
    "ARRANJO_POR_NOME",
    "ARRANJO_SENSHI",
    "BITRATE_DO_ENCODER",
    "BLOCO_FONE",
    "BYTES_DE_PCM_POR_QUADRO",
    "BYTES_POR_QUADRO_OPUS",
    "CANAIS_DO_ENCODER",
    "CRC_BYTES",
    "DEGRAU_DO_KERNEL",
    "DESCRICAO_PROVISORIA",
    "ENVELOPE_BYTES",
    "HEX_DO_SUFIXO",
    "OFFSET_DO_COMMON",
    "ORCAMENTO_DO_DEGRAU",
    "PREFIXO_SINK_DO_SOM",
    "PRIORIDADE_SESSAO_DO_SOM",
    "TAMANHO_DO_DEGRAU",
    "TAXA_DO_ENCODER",
    "Arranjo",
    "CodificadorOpus",
    "Diagnostico",
    "SinkVirtualPipeWire",
    "degrau_para_payload",
    "diagnosticar",
    "montar_pelos_dois_arranjos",
    "nome_do_sink",
    "orcamento_do_degrau",
    "propriedades_do_sink",
    "rodar_pactl",
    "so_hex",
    "sufixo_do_sink_do_som",
    "tag_tlv",
    "versao_libopus",
]
