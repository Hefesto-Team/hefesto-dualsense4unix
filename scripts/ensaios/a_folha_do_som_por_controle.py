#!/usr/bin/env python3
"""a_folha_do_som_por_controle.py — o SOM nos dois transportes, lado a lado.

A ENCOMENDA É DELA, 09/09/2026, com o produto instalado e os controles na mão:

    *"materializa o teste pensando em dois controles. um com cabo e o da direita
     via bt. vou desconectar os demais. Faz eles estilo o que fizemos hoje mais
     cedo. (…) com os controles pra eu poder ver e tal."*

*"Estilo o que fizemos hoje mais cedo"* é a `a_folha_dos_ensaios.py`, e o
critério dela é uma frase da mesma manhã: *"se não fosse o slicers era
impossível notar"*. Daqui sai o mesmo desenho — tabela declarativa, um controle
por pergunta, a posse por linha, o martelo dito na tela.

A PERGUNTA QUE ELA DECIDE (ensaio 13 do índice do rádio; SOM-POR-CONTROLE-01 §2)
--------------------------------------------------------------------------------
**O som do PC chega ao alto-falante do controle pelo RÁDIO?**

O estado medido, e é ele que torna esta folha necessária:

    cabo ..... FUNCIONA. `audio.alto_falante.rota` e `.volume` são `aciona=sim`
               nos dois transportes, e no cabo o controle tem placa USB própria.
    rádio .... `aciona=não · dívida`. SEIS passadas de bancada em 08/09,
               silêncio nas seis. O CONTEÚDO já variou de todas as formas que o
               mapa conhece (Opus, 200 B por quadro, os dois arranjos de TLV, a
               escada `0x32`-`0x39`). **O que nunca variou foi o ENVELOPE.**

O CABO É O CONTROLE POSITIVO, e é o coração deste desenho
----------------------------------------------------------
Pôr os dois lado a lado na MESMA folha é o que transforma *"não ouvi nada"* em
prova: ela aperta o do cabo, ouve, aperta o do rádio, e a diferença é o
resultado. Sem o positivo ao lado, silêncio no rádio não distingue *"o aparelho
não aceita"* de *"o meu tom está mudo"*.

E o tom é literalmente O MESMO: o WAV que o cabo toca é escrito com os MESMOS
bytes de PCM que o rádio codifica em Opus (:func:`quadros_de_pcm`). Um tom por
caminho seria uma segunda variável escondida dentro do controle positivo.

O DESENHO — uma COLUNA por controle, uma LINHA por pergunta
------------------------------------------------------------
`LINHAS` declara cada pergunta. A folha se MONTA dessa tabela, e ela não é
digitada: as seis linhas de rádio são o PRODUTO CARTESIANO de
`af.ARRANJO_POR_NOME` por `ENVELOPES`. Arranjo novo no produto é linha nova
aqui, sem que ninguém precise lembrar.

**SÃO SEIS CRUZAMENTOS, e não os quatro do enunciado.** Medido antes de aceitar
o desenho: `af.ARRANJO_POR_NOME` tem TRÊS arranjos, não dois — o terceiro é o
`common-preservado`, e ele não é leitura de fonte externa nenhuma; é o envelope
que ESTA bancada mediu obedecendo por rádio. Uma folha que ela dirige e que
alcança MENOS que a linha de comando de que ela é a cara seria um instrumento
pior que o instrumento que substitui.

**DEFEITO ACHADO AO LER, e é por isso que esta folha não chama
`montar_pelos_dois_arranjos`:** aquela função devolve só os dois de `ARRANJOS`,
enquanto `o_envelope_do_som_no_radio.py` valida `--arranjo` contra
`ARRANJO_POR_NOME`, que tem três — então `--arranjo common-preservado` passa na
validação e morre de `KeyError` na montagem. Aqui a montagem é
`ARRANJO_POR_NOME[nome].montar(...)`, que é o MESMO código do produto e alcança
os três. (O defeito é do outro arquivo e não foi tocado nesta tarefa.)

O NEGATIVO É UM BOTÃO, e não uma bandeira global
-------------------------------------------------
Na linha de comando o negativo é `--crc-errado`, que vale para a corrida
inteira. Aqui ele é o botão AO LADO do positivo, em cada linha — porque um MODO
que muda em silêncio o que todos os botões fazem é a família de defeito que
esta casa mais paga. Ela aperta «Tocar», ouve; aperta «Tocar · CRC errado», e
o silêncio ao lado do som é a prova de que o som veio de onde a gente pensa.

O QUE É DO PRODUTO, e o que é daqui
------------------------------------
Do PRODUTO: o Opus (`af.CodificadorOpus`), o corpo dos degraus
(`Arranjo.montar`, com CRC, tag e offsets), o `common` de áudio
(`af.common_de_audio` — volume, rota e pré-amplificador, sem UM offset digitado
aqui), o report de cada transporte (`escrita_pelo_broker.report_para`), o sink
do controle no cabo (`af.rota_do_no`, que resolve por IDENTIDADE) e o mapa de
canais do alto-falante (`af.CANAIS_DO_ALTO_FALANTE`).
Do ensaio irmão `o_envelope_do_som_no_radio.py`: o `HIDIOCSOUTPUT`, o envio por
envelope, o `0x31` de cor do passo 0, a corrupção de CRC e o PCM do tom.
Daqui é só a FOLHA: as colunas, os botões, o martelo e a proposta de caderno.

A MORDIDA
---------
Três, e as três estão nos botões, não num relatório:

1. **o positivo do CAMINHO** — o tom pelo cabo. Se ela não ouvir aqui, a sessão
   para: o problema não é o rádio.
2. **o positivo do ENVELOPE** — o `0x31` de COR pelo canal de controle. Se a
   barra acender por SET_REPORT, o envelope CHEGA ao firmware, e o silêncio do
   áudio por ele passa a ser do ÁUDIO. **Sem este passo, "silêncio nos dois"
   não diz nada.**
3. **o negativo** — o CRC corrompido. Nenhum envelope pode dar som com ele.

E a régua desta folha, em `tests/unit/test_a_folha_do_som_por_controle.py`,
morde ONZE vezes no que já enganou esta casa: o tom do cabo deixando de ser o
mesmo do rádio, um arranjo do produto sumindo das linhas, o negativo sem par ou
saindo com o CRC certo, o `common` da condição digitado à mão, a coluna que
recusa em silêncio, a rajada trocando de envelope no meio ou insistindo depois
do «não» do kernel, a chave de posse ficando ligada sobre coluna já devolvida, e
`--listar`/`--oculta` abrindo porta no aparelho.

A MESA É DE DOIS, e o instrumento a DESCOBRE
---------------------------------------------
Um no CABO e um no RÁDIO. Nenhum MAC é digitado — a mesa vem de
`escrita_pelo_broker.alvos_da_mesa()`, e todo endereço sai mascarado. Com
quatro na mesa ele mostra quatro colunas; quando falta o par que ele precisa,
ele diz com todas as letras qual metade falta, em vez de medir meia mesa em
silêncio.

O MARTELO, e a posse POR LINHA
-------------------------------
O daemon reescreve volume, rota e pré-amplificador a cada report dele. A linha
da CONDIÇÃO tem chave de «Assumir» por controle: enquanto ligada, esta folha
repete o `common` do produto a 10 Hz. **Ele não é enfeite nesta folha, é
pré-requisito:** os arranjos `ds5dongle` e `senshi` levam o áudio num bloco TLV
e NÃO carregam o `common` — o volume que valer para eles é o do último `0x31`.
Só o `common-preservado` leva a condição dentro do próprio report de áudio.

**A posse é por LINHA, e ela só liga quando ela liga.** Assumir tudo de uma vez
briga com o daemon em todas as frentes e emborca a medição.

Porta: o broker (`comum.abrir_no_hidraw`), com o daemon VIVO — e ela abre na
PRIMEIRA escrita, nunca antes.
Escreve no aparelho? SIM, e só quando ela aperta: os reports de áudio, o `0x31`
de cor, e o `common` de condição enquanto a chave estiver ligada.
`--listar` e `--oculta` NÃO abrem porta e NÃO escrevem byte nenhum.

USO
    a_folha_do_som_por_controle.py --listar     # só lê: a mesa, as rotas, as linhas
    a_folha_do_som_por_controle.py              # na tela dela
    a_folha_do_som_por_controle.py --so-ajustes # só os controles, sem prosa
    a_folha_do_som_por_controle.py --oculta     # sem tela, para régua
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import time
import wave
from dataclasses import dataclass, field
from functools import lru_cache

_AQUI = os.path.dirname(os.path.abspath(__file__))
if _AQUI not in sys.path:
    sys.path.insert(0, _AQUI)
_SRC = os.path.join(os.path.dirname(os.path.dirname(_AQUI)), "src")
if os.path.isdir(_SRC) and _SRC not in sys.path:
    sys.path.insert(0, _SRC)

# O ESCAPE É DECLARADO (TELA-DELA-02): sem `--oculta` esta folha é DELA e nasce
# na tela dela — vê-la é o ponto inteiro. Com `--oculta` a guarda desvia para um
# Xvfb próprio, que é o que a régua usa.
if "--oculta" not in sys.argv:
    os.environ["HEFESTO_NA_TELA"] = "1"

from hefesto_dualsense4unix.utils.tela_de_mentira import garantir_tela_de_mentira

garantir_tela_de_mentira()

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
from gi.repository import GLib, Gtk

import hefesto_dualsense4unix.core.ds_output_report as rep
from comum import (
    CABO,
    RADIO,
    Aparelho,
    abrir_no_hidraw,
    cabecalho_do_instrumento,
    pintar_fundo_solido,
    resumo,
)
from escrita_pelo_broker import (
    alvos_da_mesa,
    linha_do_caderno,
    listar,
    mascarar,
    report_para,
)
from hefesto_dualsense4unix.integrations import alto_falante_bt as af
from o_envelope_do_som_no_radio import (
    ENVELOPES,
    TAXA,
    corromper_crc,
    enviar,
    pcm_do_tom,
    report_de_cor,
)

#: A frequência do tom. Uma só, e a MESMA nos dois caminhos — ver `wav_do_tom`.
TOM_HZ = 440.0

#: Quanto dura cada aperto. Três segundos é o que ela leva para dizer «não saiu
#: nada» sem pressa, e é o mesmo padrão do ensaio de linha de comando.
SEGUNDOS_DE_TOM = 3.0

#: O martelo da linha da CONDIÇÃO. O mesmo 10 Hz da folha irmã.
HZ_DO_MARTELO = 10.0

#: Onde o WAV desta corrida vive. Fora da árvore, de propósito: é rascunho.
PASTA = os.path.join(os.environ.get("XDG_RUNTIME_DIR") or "/tmp", "hefesto-folha-do-som")

#: O nome de cada envelope na tela. `ENVELOPES` é do ensaio irmão — aqui só se
#: escreve o que ela lê, e a frase diz o CANAL, que é a variável do ensaio.
NOME_DO_ENVELOPE = {
    "data": "DATA · write() no hidraw, canal de interrupção",
    "set_report": "SET_REPORT · ioctl HIDIOCSOUTPUT, canal de controle",
}

#: A cor do passo 0. Azul porque é o que a barra do DualSense não mostra em
#: repouso nesta casa — vermelho e branco disputam com o daemon e com a carga.
COR_DO_PASSO_0 = (0, 0, 255)


# ---------------------------------------------------------------------------
# O tom — um só, nos dois caminhos
# ---------------------------------------------------------------------------


@lru_cache(maxsize=4)
def quadros_de_pcm(segundos: float) -> tuple[bytes, ...]:
    """O tom em quadros de 10 ms, do ensaio irmão. É a ÚNICA fonte do som daqui."""
    return tuple(pcm_do_tom(segundos, TOM_HZ))


def wav_do_tom(segundos: float) -> str:
    """O MESMO PCM num WAV, para o cabo tocar pelo caminho do produto.

    **Byte a byte o mesmo som que vai pelo rádio**, e não um segundo tom
    gerado ao lado. Um tom por caminho poria uma variável escondida dentro do
    controle positivo: ela ouviria o do cabo, não ouviria o do rádio, e não
    haveria como saber se a diferença é o transporte ou a amplitude.
    """
    caminho = os.path.join(PASTA, f"tom-{TOM_HZ:g}hz-{segundos:g}s.wav")
    if os.path.exists(caminho):
        return caminho
    os.makedirs(PASTA, exist_ok=True)
    with wave.open(caminho, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(TAXA)
        w.writeframes(b"".join(quadros_de_pcm(segundos)))
    return caminho


@lru_cache(maxsize=4)
def quadros_opus(segundos: float) -> tuple[bytes, ...]:
    """O mesmo tom codificado pelo encoder DO PRODUTO. Levanta em vez de mentir."""
    with af.CodificadorOpus() as codificador:
        saida = []
        for pcm in quadros_de_pcm(segundos):
            quadro = codificador.codificar(pcm)
            if quadro is None:
                raise RuntimeError("a libopus recusou um quadro — nada a montar")
            saida.append(quadro)
    return tuple(saida)


def pacotes_do_tom(
    arranjo_nome: str,
    *,
    segundos: float,
    common: bytes,
    crc_errado: bool = False,
    seq0: int = 0,
) -> list[bytes]:
    """A rajada inteira já montada, pelo arranjo pedido. Nada é digitado aqui.

    O corpo do degrau, o CRC, a tag e os offsets saem de `Arranjo.montar` — o
    produto. O `common` vem de fora porque ele é a CONDIÇÃO que ela dirige, e
    só o arranjo `common-preservado` o carrega dentro do report de áudio.
    """
    arranjo = af.ARRANJO_POR_NOME[arranjo_nome]
    por_report = max(1, int(arranjo.quadros_de_audio))
    quadros = quadros_opus(segundos)
    pacotes: list[bytes] = []
    seq = seq0
    for i in range(0, len(quadros) - por_report + 1, por_report):
        seq = (seq + 1) & 0x0F
        pacote = arranjo.montar(quadros[i : i + por_report], seq=seq, common=common)
        pacotes.append(corromper_crc(pacote) if crc_errado else pacote)
    return pacotes


def ms_por_report(arranjo_nome: str) -> float:
    """O ritmo do arranjo — o MEDIDO quando existe, o nominal quando não.

    **O nominal está errado para o `0x35`, e a folha o anunciava.** Um quadro
    Opus carrega 10 ms de som, mas o aparelho o consome a cada 10,667 ms
    (512/48000): a folha dizia *"um report a cada 10 ms"* na tela dela, que é a
    taxa de estouro pela qual esta casa passou nove vezes.
    """
    arranjo = af.ARRANJO_POR_NOME[arranjo_nome]
    medido = getattr(arranjo, "intervalo_de_envio_s", None)
    if medido:
        return round(float(medido) * 1000.0, 3)
    return float(max(1, int(arranjo.quadros_de_audio)) * af.MS_POR_QUADRO)


def rota_do_controle(alvo: Aparelho, uniqs: tuple[str, ...]) -> af.RotaDoNo:
    """Pergunta AO PRODUTO para onde o som deste controle vai.

    Uma segunda regra de atribuição aqui daria ao alto-falante do P1 o som do
    P2 assim que houvesse dois no cabo — é o que a docstring de
    `af.sink_do_controle` avisa, e é por isso que esta função só encaminha.
    """
    return af.rota_do_no(alvo.mac, alvo.transporte, uniqs)


# ---------------------------------------------------------------------------
# A TABELA — uma linha por pergunta
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Campo:
    """Um controle da condição. `atributo` é o parâmetro de `af.common_de_audio`."""

    rotulo: str
    atributo: str
    linha_do_mapa: str
    forma: str = "escala"  # escala | escolha
    minimo: int = 0
    maximo: int = 255
    marcas: tuple[tuple[int, str], ...] = ()
    escolhas: tuple[tuple[int, str], ...] = ()


@dataclass(frozen=True)
class Botao:
    """Um ato. O byte muda a condição; o ATO é o que ela ouve ou vê."""

    rotulo: str
    acao: str  # tom-no-sink | luz | audio
    envelope: str = ""
    arranjo: str = ""
    crc_errado: bool = False


@dataclass(frozen=True)
class Linha:
    """Uma pergunta da folha, com os controles e os atos de cada coluna."""

    id: str
    titulo: str
    pergunta: str
    olhar: str
    linha_do_mapa: str
    sprint: str
    campos: tuple[Campo, ...] = ()
    botoes: tuple[Botao, ...] = ()
    #: "" = as duas colunas. Senão, a coluna do outro transporte RECUSA DIZENDO.
    so_transporte: str = ""
    recusa: str = ""
    #: Esta linha tem chave de posse e martelo?
    assumir: bool = False
    #: A coluna `presente` do caderno: o suspeito estava presente nesta medição?
    presente: str = "sim"


CONDICAO = Linha(
    id="condicao-do-alto-falante",
    titulo="A condição do alto-falante — volume · rota · pré-amplificador",
    pergunta="o alto-falante está em condição de tocar, ou o silêncio é volume zero?",
    olhar="Nada aqui faz som sozinho: é a condição que as linhas de baixo pedem. "
    "Com «Assumir» ligada esta folha repete o pedido a 10 Hz — se o valor piscar, "
    "é o daemon disputando, e disputa só existe se o byte age.",
    linha_do_mapa="audio.alto_falante.volume@dualsense",
    sprint="SOM-POR-CONTROLE-01",
    assumir=True,
    campos=(
        Campo(
            "Volume",
            "volume",
            "audio.alto_falante.volume@dualsense",
            maximo=rep.TETO_SPEAKER_VOLUME,
            marcas=(
                (0, "0"),
                (38, "38 · mudo abaixo"),
                (af.VOLUME_QUE_ELA_OUVIU, f"{af.VOLUME_QUE_ELA_OUVIU} · produto"),
                (102, "102 · satura"),
                (rep.TETO_SPEAKER_VOLUME, "255"),
            ),
        ),
        Campo(
            "Rota",
            "rota",
            "audio.alto_falante.rota@dualsense",
            forma="escolha",
            escolhas=(
                (rep.SAIDA_SO_NO_ALTO_FALANTE, "só no alto-falante"),
                (rep.SAIDA_L_FONE_R_ALTO_FALANTE, "L no fone, R no alto-falante"),
                (rep.SAIDA_MONO_NO_FONE, "mono no fone"),
                (rep.SAIDA_ESTEREO_NO_FONE, "estéreo no fone"),
            ),
        ),
        Campo(
            "Pré-amplificador",
            "preamp",
            "audio.alto_falante.preamp@dualsense",
            maximo=rep.SP_PREAMP_GAIN_MASK,
            marcas=(
                (0, "0"),
                (rep.SP_PREAMP_GAIN_PADRAO, "kernel"),
                (rep.SP_PREAMP_GAIN_MASK, str(rep.SP_PREAMP_GAIN_MASK)),
            ),
        ),
    ),
)

TOM_PELO_CABO = Linha(
    id="tom-pelo-cabo",
    titulo="O tom pelo CABO — O CONTROLE POSITIVO",
    pergunta="o som do PC chega ao alto-falante deste controle pelo caminho do produto?",
    olhar="O alto-falante do controle NO CABO. Se você não ouvir AQUI, pare a sessão: "
    "o problema não é o rádio, e nada abaixo desta linha vai significar coisa alguma.",
    linha_do_mapa="audio.alto_falante@dualsense",
    sprint="SOM-POR-CONTROLE-01",
    so_transporte=CABO,
    recusa="no rádio não há placa de som — é exatamente o que as linhas abaixo investigam.",
    botoes=(Botao(f"Tocar {TOM_HZ:g} Hz no controle", "tom-no-sink"),),
)


def _linha_da_luz(envelope: str) -> Linha:
    """O passo 0: o envelope CHEGA ao firmware? Sem ele, "silêncio nos dois" não diz nada."""
    return Linha(
        id=f"a-luz-por-{envelope}",
        titulo=f"A luz por {NOME_DO_ENVELOPE[envelope]} — o positivo do ENVELOPE",
        pergunta="este envelope chega ao firmware pelo rádio? (a barra azul responde)",
        olhar="A barra de luz. Ela fica AZUL por um segundo e volta ao daemon. "
        "Se acender, o envelope chega — e o silêncio do áudio por ele passa a ser do ÁUDIO.",
        linha_do_mapa="plataforma.escada_de_output@dualsense",
        sprint="SOM-POR-CONTROLE-01",
        so_transporte=RADIO,
        # O envelope é pergunta do RÁDIO. Por cabo o descritor de 289 B declara
        # UM único OUTPUT — o `0x02` (mapa, `plataforma.escada_de_output`) — e
        # não há escada nenhuma a testar.
        recusa="o envelope é pergunta do RÁDIO: por cabo o descritor declara um único OUTPUT.",
        presente="sim" if envelope == "set_report" else "não",
        botoes=(
            Botao("Azul", "luz", envelope=envelope),
            Botao("Azul · CRC errado", "luz", envelope=envelope, crc_errado=True),
        ),
    )


def _linha_do_cruzamento(arranjo_nome: str, envelope: str) -> Linha:
    """Um dos cruzamentos arranjo × envelope, tocando o MESMO tom do cabo."""
    arranjo = af.ARRANJO_POR_NOME[arranjo_nome]
    return Linha(
        id=f"audio-{arranjo_nome}-por-{envelope}",
        titulo=f"O tom pelo RÁDIO — arranjo {arranjo_nome} × {NOME_DO_ENVELOPE[envelope]}",
        pergunta="saiu som do alto-falante do controle por este arranjo neste envelope?",
        olhar=f"O alto-falante do controle no rádio. {arranjo.quadros_de_audio} quadro(s) "
        f"de Opus por report de {arranjo.tamanho} B, um report a cada "
        f"{ms_por_report(arranjo_nome)} ms. Procedência do arranjo: {arranjo.de_onde_sei}",
        linha_do_mapa="audio.alto_falante@dualsense",
        sprint="SOM-POR-CONTROLE-01",
        so_transporte=RADIO,
        recusa="no cabo o som tem placa própria e não passa por aqui.",
        presente="sim" if envelope == "set_report" else "não",
        botoes=(
            Botao("Tocar", "audio", envelope=envelope, arranjo=arranjo_nome),
            Botao(
                "Tocar · CRC errado",
                "audio",
                envelope=envelope,
                arranjo=arranjo_nome,
                crc_errado=True,
            ),
        ),
    )


#: A FOLHA INTEIRA. As linhas de rádio NÃO são digitadas: são o produto
#: cartesiano das tabelas do PRODUTO (`af.ARRANJO_POR_NOME`) pelos envelopes do
#: ensaio irmão (`ENVELOPES`). Arranjo novo no produto vira linha nova aqui —
#: que é o que faz esta folha aguentar o resto da fila do rádio.
LINHAS: tuple[Linha, ...] = (
    CONDICAO,
    TOM_PELO_CABO,
    *(_linha_da_luz(envelope) for envelope in ENVELOPES),
    *(
        _linha_do_cruzamento(arranjo, envelope)
        for arranjo in af.ARRANJO_POR_NOME
        for envelope in ENVELOPES
    ),
)


# ---------------------------------------------------------------------------
# A COLUNA — um controle físico
# ---------------------------------------------------------------------------


@dataclass
class Coluna:
    """Um controle da mesa: a condição que ela pediu, a porta, e o que já saiu."""

    alvo: Aparelho
    rota_do_produto: af.RotaDoNo | None = None
    #: Os TRÊS parâmetros de `af.common_de_audio` — nenhum offset mora aqui.
    volume: int = af.VOLUME_QUE_ELA_OUVIU
    rota: int = rep.SAIDA_SO_NO_ALTO_FALANTE
    preamp: int = rep.SP_PREAMP_GAIN_PADRAO
    assumido: bool = False
    escritas: int = 0
    erro: str = ""
    _no: object | None = field(default=None, repr=False)
    _seq: int = 0
    #: A rajada em voo, para que dois apertos não se atropelem no mesmo fio.
    rajada_em_voo: str = ""
    #: O que REALMENTE saiu, por linha. É isto que vai para a nota do caderno —
    #: nunca a intenção do botão.
    feito: dict[str, list[str]] = field(default_factory=dict)

    @property
    def nome(self) -> str:
        return ("CABO" if self.alvo.transporte == CABO else "RÁDIO") + " · " + mascarar(self.alvo.mac)

    @property
    def curto(self) -> str:
        return "cabo" if self.alvo.transporte == CABO else "radio"

    def common(self) -> bytes:
        """O `common` de 47 B do PRODUTO, com os três valores que ela mexeu."""
        return af.common_de_audio(volume=self.volume, rota=self.rota, preamp=self.preamp)

    def fd(self) -> int | None:
        """Abre a porta NA PRIMEIRA ESCRITA, e nunca antes.

        É o que faz `--listar` e `--oculta` não tocarem no aparelho: sem aperto
        não há porta aberta. Uma porta aberta na construção seria uma escrita
        de devolução no fim de toda corrida de régua.
        """
        if self._no is None and not self.erro:
            try:
                self._no = abrir_no_hidraw(self.alvo.caminho_hidraw, escrita=True)
            except Exception as erro:
                self.erro = str(erro)
        return None if self._no is None else int(self._no.fd)

    def escrever(self, pacote: bytes, envelope: str = "data") -> str:
        """Um report pelo envelope pedido. Devolve "" ou o motivo da recusa."""
        fd = self.fd()
        if fd is None:
            return self.erro or "sem porta para este controle"
        try:
            enviar(fd, pacote, envelope)
        except OSError as erro:
            return f"o kernel recusou: {erro}"
        self.escritas += 1
        return ""

    def proximo_seq(self) -> int:
        self._seq = (self._seq + 1) & 0x0F
        return self._seq

    def bater(self) -> None:
        """O martelo da condição. Só bate quando ELA assumiu esta coluna."""
        if not self.assumido:
            return
        self.escrever(report_para(self.alvo.transporte, self.common(), self.proximo_seq()))

    def anotar(self, linha_id: str, texto: str) -> None:
        self.feito.setdefault(linha_id, []).append(texto)

    def devolver(self) -> None:
        """Devolve a posse ao daemon — e SÓ se alguma porta chegou a abrir."""
        self.assumido = False
        if self._no is None:
            return
        self.escrever(report_para(self.alvo.transporte, bytes(rep.COMMON_LEN), self.proximo_seq()))

    def fechar(self) -> None:
        self.devolver()
        if self._no is not None:
            fechar = getattr(self._no, "fechar", None)
            if callable(fechar):
                fechar()
            self._no = None


def mesa_incompleta(colunas: list[Coluna]) -> str:
    """A frase que falta, com todas as letras — ou "" quando o par está lá.

    Um instrumento que rodasse com dois no cabo e não dissesse nada deixaria
    quem lê achar que comparou transportes quando comparou um só.
    """
    no_cabo = [c for c in colunas if c.alvo.transporte == CABO]
    no_radio = [c for c in colunas if c.alvo.transporte == RADIO]
    if no_cabo and no_radio:
        return ""
    achei = f"achei {len(no_cabo)} no cabo e {len(no_radio)} no rádio"
    if not no_cabo and not no_radio:
        return "preciso de um controle no cabo e um no rádio; não achei nenhum DualSense físico"
    if not no_cabo:
        return (
            f"preciso de um no CABO e um no rádio; {achei}. "
            "Sem o do cabo não há controle POSITIVO, e silêncio no rádio não vai "
            "distinguir «o aparelho não aceita» de «o meu tom está mudo»."
        )
    return (
        f"preciso de um no cabo e um no RÁDIO; {achei}. "
        "Sem o do rádio não há o que medir: a pergunta desta folha é do rádio."
    )


# ---------------------------------------------------------------------------
# A FOLHA
# ---------------------------------------------------------------------------


class Folha:
    def __init__(self, colunas: list[Coluna], *, enxuta: bool = False,
                 segundos: float = SEGUNDOS_DE_TOM) -> None:
        self.colunas = colunas
        self.enxuta = enxuta
        self.segundos = segundos
        #: UMA NOTA POR (linha, coluna). Uma por linha faria o que ela viu no
        #: CABO sair escrito também na linha do RÁDIO — a régua que afirma
        #: sobre o que não mediu é a família de defeito mais cara desta casa.
        self.notas: dict[tuple[str, str], Gtk.Entry] = {}
        self.recados: dict[tuple[str, str], Gtk.Label] = {}
        self.contadores: list[tuple[Coluna, Gtk.Label]] = []
        #: As chaves de posse. O «Devolver TUDO» tem de DESLIGÁ-LAS, e não só
        #: devolver por baixo: uma chave que fica ligada sobre uma coluna já
        #: devolvida é a tela mentindo sobre quem manda no byte.
        self.chaves: list[Gtk.Switch] = []

        self.janela = Gtk.Window(title="Som do controle — cabo e rádio lado a lado")
        self.janela.set_default_size(1000, 760)
        self.janela.connect("destroy", self._fechar)
        self._fundo_opaco()

        raiz = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.janela.add(raiz)
        raiz.pack_start(self._topo(), False, False, 0)

        rolagem = Gtk.ScrolledWindow()
        rolagem.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        corpo = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        corpo.set_margin_top(10)
        corpo.set_margin_bottom(16)
        corpo.set_margin_start(14)
        corpo.set_margin_end(14)
        for linha in LINHAS:
            corpo.pack_start(self._secao(linha), False, False, 0)
        rolagem.add(corpo)
        raiz.pack_start(rolagem, True, True, 0)

        GLib.timeout_add(int(1000 / HZ_DO_MARTELO), self._tique)

    # ------------------------------------------------------------------ tema
    def _fundo_opaco(self) -> None:
        """Um fundo SÓLIDO — razão dela, na folha irmã: *"o fundo tá muito transparente"*."""
        # O DONO É `comum.pintar_fundo_solido` DESDE 10/09/2026, e a razão está
        # lá: estas três folhas decidiam o tema por `prefer-dark`, que é False
        # na máquina dela sob um tema ESCURO — e o rótulo do botão sumia dentro
        # do próprio botão. *"nao deu pra ler nada nos botoes"*.  # (noqa-acento: citação literal dela)
        pintar_fundo_solido(self.janela)

    # ------------------------------------------------------------------ topo
    def _topo(self) -> Gtk.Widget:
        caixa = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        caixa.set_margin_top(10)
        caixa.set_margin_start(14)
        caixa.set_margin_end(14)

        falta = mesa_incompleta(self.colunas)
        if falta:
            aviso = Gtk.Label()
            aviso.set_markup(f"<span foreground='#c01c28'><b>MESA INCOMPLETA — {falta}</b></span>")
            aviso.set_xalign(0.0)
            aviso.set_line_wrap(True)
            caixa.pack_start(aviso, False, False, 0)

        for coluna in self.colunas:
            rota = coluna.rota_do_produto
            if rota is None:
                onde = "rota: NÃO PERGUNTEI ao produto"
            elif rota.tem_rota:
                onde = f"rota: {rota.por_onde} → {rota.sink or 'a ponte do rádio'}"
            else:
                onde = f"rota: NÃO — {rota.motivo}"
            rot = Gtk.Label()
            rot.set_markup(f"<b>{coluna.nome}</b>  <span size='small'>{_escapar(onde)}</span>")
            rot.set_xalign(0.0)
            rot.set_line_wrap(True)
            caixa.pack_start(rot, False, False, 0)

        if not self.enxuta:
            dica = Gtk.Label(
                label="A ORDEM: 1) ajuste a condição e ligue «Assumir». 2) toque no CABO e OUÇA "
                "— se não ouvir, pare. 3) o passo 0 da luz. 4) os cruzamentos. 5) o CRC errado, "
                f"que não pode dar som. Cada aperto dura {self.segundos:g} s."
            )
            dica.set_xalign(0.0)
            dica.set_line_wrap(True)
            dica.get_style_context().add_class("dim-label")
            caixa.pack_start(dica, False, False, 0)

        linha = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        for coluna in self.colunas:
            conta = Gtk.Label()
            conta.get_style_context().add_class("dim-label")
            self.contadores.append((coluna, conta))
            linha.pack_start(conta, False, False, 0)
        tudo = Gtk.Button(label="Devolver TUDO ao daemon")
        tudo.connect("clicked", self._devolver_tudo)
        linha.pack_end(tudo, False, False, 0)
        caixa.pack_start(linha, False, False, 0)
        caixa.pack_start(Gtk.Separator(), False, False, 6)
        return caixa

    # ----------------------------------------------------------------- seção
    def _secao(self, linha: Linha) -> Gtk.Widget:
        moldura = Gtk.Frame()
        dentro = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        dentro.set_margin_top(10)
        dentro.set_margin_bottom(10)
        dentro.set_margin_start(12)
        dentro.set_margin_end(12)

        titulo = Gtk.Label()
        titulo.set_markup(
            f"<b>{_escapar(linha.titulo)}</b>"
            + ("" if self.enxuta else f"   <span size='small'>{linha.sprint}</span>")
        )
        titulo.set_xalign(0.0)
        titulo.set_line_wrap(True)
        dentro.pack_start(titulo, False, False, 0)

        if not self.enxuta:
            for texto, classe in ((linha.pergunta, None), (f"OLHE: {linha.olhar}", "dim-label")):
                rot = Gtk.Label(label=texto)
                rot.set_xalign(0.0)
                rot.set_line_wrap(True)
                if classe:
                    rot.get_style_context().add_class(classe)
                dentro.pack_start(rot, False, False, 0)

        colunas = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=18)
        colunas.set_homogeneous(True)
        colunas.set_margin_top(6)
        for coluna in self.colunas:
            colunas.pack_start(self._coluna(linha, coluna), True, True, 0)
        dentro.pack_start(colunas, False, False, 0)

        if not self.enxuta:
            gravar = Gtk.Button(label="Gravar o que eu ouvi")
            gravar.connect("clicked", lambda _b, ln=linha: self.propor(ln))
            gravar.set_margin_top(6)
            dentro.pack_start(gravar, False, False, 0)

        moldura.add(dentro)
        return moldura

    def _coluna(self, linha: Linha, coluna: Coluna) -> Gtk.Widget:
        caixa = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        cabeca = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        nome = Gtk.Label()
        nome.set_markup(f"<small>{coluna.nome}</small>")
        nome.set_xalign(0.0)
        cabeca.pack_start(nome, False, False, 0)
        if linha.assumir:
            chave = Gtk.Switch()
            chave.set_tooltip_text(
                "Assumir a condição deste controle: começa a repetir o pedido a "
                f"{HZ_DO_MARTELO:g} Hz, disputando com o daemon."
            )
            chave.connect("notify::active", self._assumir, coluna)
            self.chaves.append(chave)
            cabeca.pack_end(chave, False, False, 0)
            cabeca.pack_end(Gtk.Label(label="Assumir"), False, False, 0)
        caixa.pack_start(cabeca, False, False, 0)

        if linha.so_transporte and coluna.alvo.transporte != linha.so_transporte:
            # RECUSAR DIZENDO: uma coluna muda leria como "não fizeram nada".
            recusa = Gtk.Label(label=linha.recusa or "esta pergunta não é deste transporte.")
            recusa.set_xalign(0.0)
            recusa.set_line_wrap(True)
            recusa.get_style_context().add_class("dim-label")
            caixa.pack_start(recusa, False, False, 4)
            return caixa

        for campo in linha.campos:
            caixa.pack_start(self._campo(campo, coluna), False, False, 0)

        recado = Gtk.Label()
        recado.set_xalign(0.0)
        recado.set_line_wrap(True)
        recado.get_style_context().add_class("dim-label")
        self.recados[(linha.id, coluna.alvo.mac)] = recado

        if linha.botoes:
            fileira = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
            for botao in linha.botoes:
                widget = Gtk.Button(label=botao.rotulo)
                if botao.crc_errado:
                    widget.set_tooltip_text(
                        "O NEGATIVO: o mesmo report com o CRC corrompido. Se sair som "
                        "daqui, o que você ouviu não veio de onde a gente pensa."
                    )
                widget.connect("clicked", self._apertar, botao, linha, coluna)
                fileira.pack_start(widget, True, True, 0)
            caixa.pack_start(fileira, False, False, 4)
        caixa.pack_start(recado, False, False, 0)

        if not self.enxuta:
            nota = Gtk.Entry()
            nota.set_placeholder_text(f"O que eu ouvi no {coluna.curto.upper()}")
            nota.set_hexpand(True)
            self.notas[(linha.id, coluna.alvo.mac)] = nota
            caixa.pack_start(nota, False, False, 4)
        return caixa

    def _campo(self, campo: Campo, coluna: Coluna) -> Gtk.Widget:
        caixa = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        if campo.forma == "escolha":
            fileira = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            fileira.pack_start(Gtk.Label(label=campo.rotulo), False, False, 0)
            combo = Gtk.ComboBoxText()
            for valor, texto in campo.escolhas:
                combo.append(str(valor), texto)
            combo.set_active_id(str(getattr(coluna, campo.atributo)))
            combo.connect("changed", self._mudar_escolha, campo, coluna)
            fileira.pack_end(combo, True, True, 0)
            caixa.pack_start(fileira, False, False, 0)
            return caixa

        rot = Gtk.Label(label=campo.rotulo)
        rot.set_xalign(0.0)
        rot.get_style_context().add_class("dim-label")
        caixa.pack_start(rot, False, False, 0)
        ajuste = Gtk.Adjustment(
            value=getattr(coluna, campo.atributo),
            lower=campo.minimo,
            upper=campo.maximo,
            step_increment=1,
            page_increment=max(1, campo.maximo // 8),
        )
        escala = Gtk.Scale(orientation=Gtk.Orientation.HORIZONTAL, adjustment=ajuste)
        escala.set_digits(0)
        escala.set_round_digits(0)
        escala.set_value_pos(Gtk.PositionType.RIGHT)
        escala.set_hexpand(True)
        for valor, texto in campo.marcas:
            escala.add_mark(valor, Gtk.PositionType.BOTTOM, texto)
        escala.connect("value-changed", self._mudar_escala, campo, coluna)
        caixa.pack_start(escala, False, False, 0)
        return caixa

    # ----------------------------------------------------------------- atos
    def _devolver_tudo(self, *_: object) -> None:
        for chave in self.chaves:
            chave.set_active(False)  # dispara `_assumir`, que devolve
        for coluna in self.colunas:
            coluna.devolver()

    def _assumir(self, chave: Gtk.Switch, _p: object, coluna: Coluna) -> None:
        coluna.assumido = chave.get_active()
        if not coluna.assumido:
            coluna.devolver()

    def _mudar_escala(self, escala: Gtk.Scale, campo: Campo, coluna: Coluna) -> None:
        setattr(coluna, campo.atributo, round(escala.get_value()))

    def _mudar_escolha(self, combo: Gtk.ComboBoxText, campo: Campo, coluna: Coluna) -> None:
        setattr(coluna, campo.atributo, int(combo.get_active_id() or 0))

    def _apertar(self, _widget: Gtk.Button, botao: Botao, linha: Linha, coluna: Coluna) -> None:
        recado = self.recados[(linha.id, coluna.alvo.mac)]
        if botao.acao == "tom-no-sink":
            motivo = self._tocar_no_sink(coluna, linha, recado)
        elif botao.acao == "luz":
            motivo = self._acender(coluna, linha, botao, recado)
        elif botao.acao == "audio":
            motivo = self._bombear(coluna, linha, botao, recado)
        else:  # pragma: no cover — a tabela é fechada
            motivo = f"ato desconhecido: {botao.acao}"
        if motivo:
            recado.set_markup(f"<span foreground='#c01c28'>{_escapar(motivo)}</span>")

    def _tocar_no_sink(self, coluna: Coluna, linha: Linha, recado: Gtk.Label) -> str:
        """O tom pelo caminho do produto: o sink que `af.rota_do_no` resolveu."""
        rota = coluna.rota_do_produto
        if rota is None:
            return "não perguntei ao produto para onde o som deste controle vai"
        if not rota.tem_rota or not rota.sink:
            return rota.motivo or "o produto não sabe para onde mandar o som deste controle"
        if not shutil.which("paplay"):
            return "não há paplay nesta máquina — sem ele não sei tocar no sink do controle"
        os.makedirs(PASTA, exist_ok=True)
        registro = os.path.join(PASTA, f"paplay-{coluna.curto}.err")
        argv = [
            "paplay",
            f"--device={rota.sink}",
            f"--channel-map={af.CANAIS_DO_ALTO_FALANTE}",
            wav_do_tom(self.segundos),
        ]
        saida = open(registro, "wb")  # noqa: SIM115 — fechado no `conferir`
        try:
            proc = subprocess.Popen(argv, stdout=subprocess.DEVNULL, stderr=saida)
        except OSError as erro:
            saida.close()
            return str(erro)
        recado.set_text(f"tocando {TOM_HZ:g} Hz em {rota.sink}")
        coluna.anotar(linha.id, f"paplay em {rota.sink} ({af.CANAIS_DO_ALTO_FALANTE})")

        def conferir() -> bool:
            """O `paplay` que morre é o silêncio que se leria como «o aparelho não faz»."""
            saida.close()
            codigo = proc.poll()
            if codigo not in (None, 0):
                try:
                    with open(registro, encoding="utf-8", errors="replace") as f:
                        texto = f.read().strip().splitlines()[-1:] or ["sem texto"]
                except OSError:
                    texto = ["sem texto"]
                recado.set_markup(
                    f"<span foreground='#c01c28'>o paplay saiu {codigo}: "
                    f"{_escapar(texto[0])}</span>"
                )
                coluna.anotar(linha.id, f"paplay RECUSOU (rc={codigo})")
            return False

        GLib.timeout_add(int(self.segundos * 1000) + 800, conferir)
        return ""

    def _acender(self, coluna: Coluna, linha: Linha, botao: Botao, recado: Gtk.Label) -> str:
        """O passo 0: um `0x31` de COR pelo envelope, e a devolução por DATA."""
        pacote = report_de_cor(*COR_DO_PASSO_0, seq=coluna.proximo_seq())
        if botao.crc_errado:
            pacote = corromper_crc(pacote)
        motivo = coluna.escrever(pacote, botao.envelope)
        if motivo:
            coluna.anotar(linha.id, f"{botao.envelope}: RECUSADO ({motivo})")
            return motivo
        marca = " com CRC ERRADO" if botao.crc_errado else ""
        recado.set_text(f"azul por {botao.envelope}{marca} — olhe a barra")
        coluna.anotar(linha.id, f"{botao.envelope}{marca}: 0x31 de cor enviado")

        def apagar() -> bool:
            # A devolução é um `common` VAZIO — nenhum bit de validação, logo
            # o firmware volta a obedecer ao daemon, que repinta em ~100 ms.
            # E ela vai sempre por DATA, o envelope que já se sabe chegar:
            # devolver pelo envelope EM TESTE deixaria a barra acesa justamente
            # quando ele for o que não funciona.
            coluna.escrever(
                report_para(coluna.alvo.transporte, bytes(rep.COMMON_LEN), coluna.proximo_seq())
            )
            return False

        GLib.timeout_add(1200, apagar)
        return ""

    def _bombear(self, coluna: Coluna, linha: Linha, botao: Botao, recado: Gtk.Label) -> str:
        """A rajada de áudio, bombeada pelo laço do GTK para a folha não congelar."""
        if coluna.rajada_em_voo:
            return f"este controle já está tocando ({coluna.rajada_em_voo}) — espere terminar"
        try:
            pacotes = pacotes_do_tom(
                botao.arranjo,
                segundos=self.segundos,
                common=coluna.common(),
                crc_errado=botao.crc_errado,
                seq0=coluna._seq,
            )
        except af.OpusIndisponivelError as erro:
            return f"o produto não codifica Opus nesta máquina: {erro}"
        except (RuntimeError, ValueError) as erro:
            return str(erro)
        if not pacotes:
            return "o tom é curto demais para um report deste arranjo"
        # O nibble de sequência é do CONTROLE, não da rajada: sem adiantá-lo o
        # martelo da condição repetiria números que a rajada já gastou, e o
        # firmware tem o direito de descartar report com seq repetido.
        coluna._seq = (coluna._seq + len(pacotes)) & 0x0F
        if coluna.fd() is None:
            return coluna.erro or "sem porta para este controle"

        marca = " · CRC ERRADO" if botao.crc_errado else ""
        coluna.rajada_em_voo = f"{botao.arranjo} × {botao.envelope}{marca}"
        estado = {"i": 0, "enviados": 0, "recusas": 0, "erro": ""}
        condicao = (
            f"volume {coluna.volume}, rota {coluna.rota}, pré-amp {coluna.preamp}"
            f"{'' if coluna.assumido else ' (NÃO assumida — quem manda é o daemon)'}"
        )

        def bombear() -> bool:
            if estado["i"] >= len(pacotes):
                recado.set_markup(
                    f"<b>{estado['enviados']} report(s) de {len(pacotes[0])} B</b> por "
                    f"{botao.envelope}{marca}, {estado['recusas']} recusa(s) · {condicao}"
                )
                coluna.anotar(
                    linha.id,
                    f"{botao.arranjo} × {botao.envelope}{marca}: {estado['enviados']} report(s) "
                    f"de {len(pacotes[0])} B, {estado['recusas']} recusa(s); {condicao}"
                    + (f"; {estado['erro']}" if estado["erro"] else ""),
                )
                coluna.rajada_em_voo = ""
                return False
            motivo = coluna.escrever(pacotes[estado["i"]], botao.envelope)
            estado["i"] += 1
            if motivo:
                estado["recusas"] += 1
                if not estado["erro"]:
                    estado["erro"] = motivo
                    recado.set_markup(f"<span foreground='#c01c28'>{_escapar(motivo)}</span>")
                    # Um kernel sem HIDIOCSOUTPUT recusa TODOS: insistir 150
                    # vezes só enche o log e atrasa a resposta na tela.
                    estado["i"] = len(pacotes)
            else:
                estado["enviados"] += 1
            return True

        recado.set_text(f"tocando por {botao.envelope}{marca}… ({len(pacotes)} reports)")
        GLib.timeout_add(ms_por_report(botao.arranjo), bombear)
        return ""

    # ---------------------------------------------------------------- laço
    def _tique(self) -> bool:
        for coluna in self.colunas:
            coluna.bater()
        for coluna, conta in self.contadores:
            if coluna.erro:
                conta.set_markup(
                    f"<span foreground='#c01c28'>{coluna.curto}: {_escapar(coluna.erro)}</span>"
                )
            else:
                posse = "assumido" if coluna.assumido else "do daemon"
                conta.set_text(f"{coluna.curto}: {posse}, {coluna.escritas} escritas")
        return True

    # ------------------------------------------------------------- proposta
    def propor(self, linha: Linha, *, exigir_nota: bool = True) -> None:
        """A folha NÃO conclui: imprime as linhas, e quem coordena as escreve."""
        print(f"\nLINHAS PROPOSTAS — {linha.titulo} (docs/data/ensaios.csv):")
        for coluna in self.colunas:
            if linha.so_transporte and coluna.alvo.transporte != linha.so_transporte:
                continue
            caixa = self.notas.get((linha.id, coluna.alvo.mac))
            nota = caixa.get_text().strip() if caixa is not None else ""
            if not nota and exigir_nota:
                print(f"  (o {coluna.nome} ficou sem resposta — nada a propor por ele)")
                continue
            feito = "; ".join(coluna.feito.get(linha.id, [])) or "nada apertado nesta linha"
            # A linha da CONDIÇÃO tem posse: o «suspeito presente» dela é a
            # chave ligada, não uma constante da tabela.
            presente = ("sim" if coluna.assumido else "não") if linha.assumir else linha.presente
            campos = linha.campos or (None,)
            for campo in campos:
                sufixo = "" if campo is None else "-" + _sem_acento(campo.rotulo)
                valor = "" if campo is None else f"{campo.rotulo}={getattr(coluna, campo.atributo)}; "
                print(
                    linha_do_caderno(
                        id=f"som-{linha.id}{sufixo}-{coluna.curto}-{time.strftime('%d%m')}",
                        linha_id=(campo.linha_do_mapa if campo is not None else linha.linha_do_mapa),
                        transporte=coluna.curto,
                        suspeito=linha.pergunta,
                        presente=presente,
                        resultado="",
                        observado_por="olho-dela",
                        fonte="scripts/ensaios/a_folha_do_som_por_controle.py",
                        nota=f"{valor}{feito}; martelo "
                        f"{HZ_DO_MARTELO:g} Hz {'ligado' if coluna.assumido else 'desligado'}; "
                        f"ela: {nota or '(sem resposta — esta linha é a FORMA, não uma medição)'}",
                    )
                )
        sys.stdout.flush()

    def _fechar(self, *_: object) -> None:
        for coluna in self.colunas:
            coluna.fechar()
        if Gtk.main_level() > 0:
            Gtk.main_quit()

    def abrir(self) -> None:
        self.janela.show_all()
        Gtk.main()


def _sem_acento(texto: str) -> str:
    """O rótulo virando pedaço de `id` do caderno: sem acento e sem espaço.

    O `id` é chave de linha num CSV que scripts leem; «pré-amplificador» com
    acento é legítimo em prosa e ruim como chave. O texto QUE ELA LÊ continua
    acentuado — só o identificador é dobrado.
    """
    import unicodedata

    cru = unicodedata.normalize("NFKD", texto or "")
    limpo = "".join(c for c in cru if not unicodedata.combining(c))
    return "".join(c if c.isalnum() else "-" for c in limpo.lower()).strip("-")


def _escapar(texto: str) -> str:
    """Markup do Pango não engole `&` nem `<` crus — e um `&` de mensagem de erro
    faz o rótulo inteiro sumir, que é o recado de recusa quebrando a tela que
    vinha explicar."""
    return (texto or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


# ---------------------------------------------------------------------------
# A porta de entrada
# ---------------------------------------------------------------------------

PERGUNTA = "o som do PC chega ao alto-falante do controle pelo RÁDIO, como já chega pelo cabo?"


def montar_colunas(alvos: list[Aparelho]) -> list[Coluna]:
    """As colunas na ordem do desenho: o CABO primeiro, porque é o positivo."""
    uniqs = tuple(a.mac for a in alvos)
    ordenados = sorted(alvos, key=lambda a: (a.transporte != CABO, a.hidraw))
    colunas = []
    for alvo in ordenados:
        coluna = Coluna(alvo=alvo)
        try:
            coluna.rota_do_produto = rota_do_controle(alvo, uniqs)
        except Exception as erro:  # o produto pode não responder; dizer é o dever
            coluna.rota_do_produto = af.RotaDoNo(False, motivo=f"não consegui perguntar: {erro}")
        colunas.append(coluna)
    return colunas


def imprimir_o_que_se_le(colunas: list[Coluna], alvos: list[Aparelho]) -> None:
    """O que `--listar` mostra. LEITURA PURA: nenhuma porta abre aqui."""
    print(
        cabecalho_do_instrumento(
            "a_folha_do_som_por_controle",
            PERGUNTA,
            bibliotecas=["hefesto_dualsense4unix.integrations.alto_falante_bt"],
            escreve_no_aparelho=False,
        )
    )
    print("\na mesa que este instrumento ENCONTROU:")
    print(listar(alvos))
    falta = mesa_incompleta(colunas)
    if falta:
        print(f"\n  MESA INCOMPLETA — {falta}")
    else:
        print("\n  o par está na mesa: um no cabo (o positivo) e um no rádio (a pergunta).")

    print("\npara onde o PRODUTO manda o som de cada um (af.rota_do_no, leitura pura):")
    for coluna in colunas:
        rota = coluna.rota_do_produto
        if rota is None:
            print(f"  {coluna.nome:<28} NÃO PERGUNTEI")
        elif rota.tem_rota:
            print(f"  {coluna.nome:<28} {rota.por_onde} → {rota.sink or 'a ponte do rádio'}")
        else:
            print(f"  {coluna.nome:<28} NÃO — {rota.motivo}")
        no = af.nome_do_sink(coluna.alvo.mac)
        rotas = af.argv_das_rotas(no, rota) if (no and rota is not None) else ()
        for argv in rotas:
            print(f"  {'':<28} o produto ligaria: {' '.join(argv)}")
        if no and not rotas:
            print(f"  {'':<28} nenhum module-loopback a subir para «{no}»")

    print(f"\nas {len(LINHAS)} linhas desta folha:")
    for linha in LINHAS:
        onde = linha.so_transporte or "cabo+rádio"
        atos = ", ".join(b.rotulo for b in linha.botoes) or ", ".join(c.rotulo for c in linha.campos)
        print(f"  {linha.id:<34} {onde:<7} {atos}")
    print(
        f"\narranjos do produto: {', '.join(af.ARRANJO_POR_NOME)}"
        f"   ·   envelopes: {', '.join(ENVELOPES)}"
    )
    print(
        resumo(
            "leitura pura — nenhum nó hidraw aberto, nenhum byte escrito no aparelho. "
            "A medição é ela apertando os botões, com os controles na mão."
        )
    )


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--listar", action="store_true", help="só lê: a mesa, as rotas e as linhas")
    ap.add_argument("--oculta", action="store_true", help="sem tela, para régua")
    ap.add_argument("--so-ajustes", action="store_true", help="só os controles, sem prosa")
    ap.add_argument("--segundos", type=float, default=SEGUNDOS_DE_TOM,
                    help="quanto dura cada aperto")
    args = ap.parse_args(argv)

    alvos = alvos_da_mesa()
    colunas = montar_colunas(alvos)

    if args.listar:
        imprimir_o_que_se_le(colunas, alvos)
        return 1 if mesa_incompleta(colunas) else 0

    falta = mesa_incompleta(colunas)
    if falta:
        print(f"MESA INCOMPLETA — {falta}")
    print(f"colunas: {', '.join(c.nome for c in colunas) or '(nenhuma)'}")
    print(f"linhas na folha: {len(LINHAS)}")

    folha = Folha(colunas, enxuta=args.so_ajustes, segundos=args.segundos)
    if args.oculta:
        for linha in LINHAS:
            folha.propor(linha, exigir_nota=False)
        folha._fechar()
        return 1 if falta else 0
    folha.abrir()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
