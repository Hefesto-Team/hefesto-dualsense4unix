#!/usr/bin/env python3
"""a_folha_dos_ensaios.py — todos os ensaios de byte numa folha só, com os controles dela.

A ENCOMENDA É DELA, 09/09/2026: *"faz uma folha só com todos os testes, com
controles e slicers pra eu ir testando todos de uma vez"*.

E ela nasceu de um achado do mesmo dia. O `o_painel_do_brilho.py` pôs UM byte
num controle deslizante e ela viu, em dois minutos, o que a casa afirmava
errado desde 11/08: o `common[42]` não atenua a barra, atenua as lâmpadas de
numeração. A frase dela foi *"se não fosse o slicers era impossível notar"* —
e a conclusão de processo é que **o instrumento que ela dirige acha o que a
escada automática esconde**.

O DESENHO, e por que ele é uma TABELA
--------------------------------------
`ENSAIOS` declara cada medição: o byte, o bit que a autoriza, a faixa, o que
ela deve olhar e a sprint que a espera. A folha se MONTA dessa tabela. Ensaio
novo é linha nova, não painel novo — que é o que faz esta folha aguentar o
resto da fila.

O ESTADO É POR APARELHO, e isso é o que deixa combinar
-------------------------------------------------------
Cada controle físico tem UM `common` vivo aqui. Um deslizante escreve o campo
dele nesse `common`; a chave do ensaio liga o bit de autorização. Assim ela
pode acender a barra E atenuar as lâmpadas ao mesmo tempo — que foi como o
brilho dos LEDs de jogador ficou visível.

**O bit só liga quando ela liga.** Assumir a posse de tudo de uma vez briga com
o daemon em todas as frentes e emborca a medição; aqui a posse é por ensaio.

O MARTELO, e por que ele é obrigatório
---------------------------------------
Cada report do daemon reescreve o que este painel mandou. Cada aparelho tem um
martelo a 10 Hz. Se a coisa PISCAR entre dois estados, isso é um **sim** — é o
daemon e a folha disputando, e disputa só existe se o byte age.

Porta: o broker (`escrita_pelo_broker.Escritor`), com o daemon VIVO.
Escreve no aparelho? SIM — e só os campos dos ensaios que ela ligar.

USO
    a_folha_dos_ensaios.py --so-ajustes --so-falta   # só os controles do que FALTA
    a_folha_dos_ensaios.py --so-ajustes   # SÓ os controles, sem uma linha de prosa
    a_folha_dos_ensaios.py                # na tela dela
    a_folha_dos_ensaios.py --oculta       # sem tela, para régua
"""

from __future__ import annotations

import array
import math
import os
import shutil
import struct
import subprocess
import sys
import time
import wave
from dataclasses import dataclass, field
from typing import ClassVar

_AQUI = os.path.dirname(os.path.abspath(__file__))
if _AQUI not in sys.path:
    sys.path.insert(0, _AQUI)
_SRC = os.path.join(os.path.dirname(os.path.dirname(_AQUI)), "src")
if os.path.isdir(_SRC) and _SRC not in sys.path:
    sys.path.insert(0, _SRC)

# O ESCAPE É DECLARADO (TELA-DELA-02): sem `--oculta` esta folha é DELA e nasce
# na tela dela — vê-la é o ponto inteiro.
if "--oculta" not in sys.argv:
    os.environ["HEFESTO_NA_TELA"] = "1"

from hefesto_dualsense4unix.utils.tela_de_mentira import garantir_tela_de_mentira

garantir_tela_de_mentira()

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
from gi.repository import Gdk, GLib, Gtk

import hefesto_dualsense4unix.core.ds_output_report as rep
from comum import CABO
from escrita_pelo_broker import (
    Escritor,
    alvos_da_mesa,
    common_vazio,
    linha_do_caderno,
    mascarar,
)
from os_nos_de_som_por_controle import censo

HZ = 10.0

#: AS TREZE DA LINHA DE COR — decisão dela, 09/09/2026: *"deixar na tela 11 cores
#: principais (primárias e interseções) + preto + branco"*, e *"na linha de cor,
#: terão as cores apenas sem abrir essa tela"*.
#:
#: São os onze matizes do círculo andando de 30 em 30 graus, de 0° a 300° — o
#: passo que dá nomes canônicos a todos e cobre o círculo sem repetir vizinho.
#: Preto e branco entram porque não são matiz nenhum: um apaga a barra, o outro
#: é a referência de intensidade cheia.
#:
#: OS TONS SÃO PASTÉIS, e é decisão dela ao ver a primeira versão saturada:
#: *"os tons de cores pré disponíveis tem que serem na mesma pega de tons
#: pastéis"* — a mesma pegada da fileira que a aba Iluminação já mostra. Cada
#: matiz sai de HSL com saturação cheia e luminosidade 72 %; branco e preto
#: ficam como estão, porque não são matiz.
#:
#: POR QUE UMA FILEIRA E NÃO O SELETOR DO GTK: ela abriu o diálogo «Select
#: Color» e ele toma a tela inteira para escolher uma cor que o aparelho mostra
#: em cinco lâmpadas. Escolher cor aqui é um clique, não um formulário.
CORES_DA_LINHA: tuple[tuple[str, tuple[int, int, int]], ...] = (
    ("Vermelho", (255, 112, 112)),  # 0°  #FF7070
    ("Laranja", (255, 184, 112)),  # 30°  #FFB870
    ("Amarelo", (255, 255, 112)),  # 60°  #FFFF70
    ("Verde-limão", (184, 255, 112)),  # 90°  #B8FF70
    ("Verde", (112, 255, 112)),  # 120°  #70FF70
    ("Verde-água", (112, 255, 184)),  # 150°  #70FFB8
    ("Ciano", (112, 255, 255)),  # 180°  #70FFFF
    ("Azul-céu", (112, 184, 255)),  # 210°  #70B8FF
    ("Azul", (112, 112, 255)),  # 240°  #7070FF
    ("Violeta", (184, 112, 255)),  # 270°  #B870FF
    ("Magenta", (255, 112, 255)),  # 300°  #FF70FF
    ("Branco", (255, 255, 255)),
    ("Preto", (0, 0, 0)),
)

#: Onde os WAV desta corrida vivem. Fora da árvore, de propósito: é rascunho.
PASTA = os.path.join(os.environ.get("XDG_RUNTIME_DIR") or "/tmp", "hefesto-folha-dos-ensaios")

#: Quanto dura uma gravação do microfone. Três segundos é o que ela leva para
#: dizer «aaaa» sem pressa, e o pico não precisa de mais.
SEGUNDOS_DE_GRAVACAO = 3.0


def _hex_para_rgb(tom: str) -> tuple[float, float, float]:
    """`#rrggbb` em 0..1 para o cairo. Tom ruim vira cinza, nunca exceção."""
    tom = (tom or "").lstrip("#")
    if len(tom) != 6:
        return (0.75, 0.75, 0.75)
    try:
        return (int(tom[0:2], 16) / 255, int(tom[2:4], 16) / 255, int(tom[4:6], 16) / 255)
    except ValueError:
        return (0.75, 0.75, 0.75)


def _ferramenta(*candidatas: str) -> str:
    """A primeira que existir no PATH. PipeWire e PulseAudio nomeiam diferente."""
    for c in candidatas:
        if shutil.which(c):
            return c
    return ""


#: O caderno. É dele que sai o que já foi respondido — a lista NÃO se digita.
#: Digitar quem já respondeu é a família de defeito que esta casa mais pagou:
#: a régua envelhece no dia seguinte e passa a esconder o que voltou a faltar.
CADERNO = os.path.join(
    os.path.dirname(os.path.dirname(_AQUI)), "docs", "data", "ensaios.csv"
)

#: As fontes que contam como «respondido por esta bancada». Uma medição antiga,
#: de outro instrumento, não fecha um ensaio desta folha.
FONTES_DESTA_BANCADA = (
    "scripts/ensaios/a_folha_dos_ensaios.py",
    "scripts/ensaios/o_painel_do_brilho.py",
    "scripts/ensaios/o_brilho_de_hardware_da_barra.py",
)


def respondidos() -> set[str]:
    """As `linha_id` que esta bancada já fechou, LIDAS do caderno."""
    import csv

    try:
        with open(CADERNO, encoding="utf-8", newline="") as f:
            return {
                r["linha_id"]
                for r in csv.DictReader(f)
                if (r.get("resultado") or "").strip()
                and (r.get("fonte") or "") in FONTES_DESTA_BANCADA
            }
    except (OSError, KeyError):
        return set()


GRAVADOR = _ferramenta("pw-record", "parec")
TOCADOR = _ferramenta("pw-play", "paplay")


def tom_de_teste() -> str:
    """Um WAV de três tons, gerado uma vez. É o som que sai NO controle."""
    caminho = os.path.join(PASTA, "tom-de-teste.wav")
    if os.path.exists(caminho):
        return caminho
    os.makedirs(PASTA, exist_ok=True)
    taxa, quadros = 48000, []
    for hz, dur in ((440.0, 0.6), (880.0, 0.6), (440.0, 0.6)):
        for i in range(int(taxa * dur)):
            v = int(18000 * math.sin(2 * math.pi * hz * i / taxa))
            quadros.append(struct.pack("<hh", v, v))
    with wave.open(caminho, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(taxa)
        w.writeframes(b"".join(quadros))
    return caminho


def pico_do_wav(caminho: str) -> float:
    """O pico em 0..1. É ele que decide, não o ouvido — o ouvido esquece o passo anterior."""
    try:
        with wave.open(caminho, "rb") as w:
            if w.getsampwidth() != 2:
                return -1.0
            dados = w.readframes(w.getnframes())
    except (OSError, wave.Error):
        return -1.0
    if not dados:
        return 0.0
    amostras = array.array("h")
    amostras.frombytes(dados[: len(dados) // 2 * 2])
    return max(abs(min(amostras)), abs(max(amostras))) / 32768.0

#: `common[7]` carrega a rota (bits 4-5) E o caminho do microfone. Escrever o
#: byte cru apaga o mic em silêncio — a casa já pagou por isso (SOM-CANAL-01).
BASE_DO_BYTE_7 = rep.AUDIO_CONTROL_BASE_SEGURA


@dataclass
class Campo:
    """Um controle da folha: o byte que ele escreve e como ela o mexe."""

    rotulo: str
    offset: int
    forma: str = "escala"  # escala | cor | escolha
    minimo: int = 0
    maximo: int = 255
    marcas: tuple[tuple[int, str], ...] = ()
    inicial: int = 0
    escolhas: tuple[tuple[int, str], ...] = ()
    #: `common[7]` precisa preservar o meio-byte do microfone.
    desloca: int = 0
    base: int = 0
    #: O dono deste campo no mapa de canais. Vazio = herda o do ensaio. Existe
    #: porque um ensaio pode tocar DUAS linhas do mapa — os dois motores de
    #: vibração são uma chave cada, e uma linha de caderno que some os dois não
    #: responde a nenhuma das duas.
    linha_do_mapa: str = ""


@dataclass
class Ensaio:
    """Uma medição: os campos que ela mexe, e o bit que os autoriza."""

    id: str
    titulo: str
    pergunta: str
    olhar: str
    sprint: str
    linha_do_mapa: str
    campos: tuple[Campo, ...]
    #: OS BITS QUE AUTORIZAM, como `(offset do flag, bit)`. É uma LISTA porque
    #: um ensaio pode precisar de mais de um, e a casa pagou por supor que não:
    #: a vibração ficou muda na primeira folha com só o `COMPATIBLE_VIBRATION`
    #: ligado — ela reportou *"não funciona, mas na interface isso funciona"*, e
    #: o produto liga QUATRO (`backend_pydualsense.py:1283-1304`).
    autorizacoes: tuple[tuple[int, int], ...]
    flag_nome: str
    estado: str = "aberto"
    #: Os botões deste ensaio. O byte muda a condição; o ATO é o que ela ouve
    #: ou sente. Pedido dela, 09/09: *"um botão pra gravar e reproduzir por
    #: cada controle. fone, autofalante, pre amplificador e todos os demais"*.
    acoes: tuple[str, ...] = ()


ENSAIOS: tuple[Ensaio, ...] = (
    Ensaio(
        id="brilho-dos-leds-de-jogador",
        titulo="Brilho das lâmpadas de numeração",
        pergunta="os três degraus atenuam as lâmpadas P1/P2, e sem o bit nada acontece?",
        olhar="As lâmpadas de numeração, não a barra.",
        sprint="BRILHO-DE-HARDWARE-01",
        linha_do_mapa="luz.led_jogador.brilho@dualsense",
        estado="RESPONDIDO em 09/09 — fica como regressão",
        campos=(
            Campo("Brilho", 42, minimo=0, maximo=2,
                  marcas=((0, "ALTO"), (1, "MÉDIO"), (2, "BAIXO"))),
        ),
        autorizacoes=((rep.COMMON_VALID_FLAG2, rep.VALID_FLAG2_LED_BRIGHTNESS_CONTROL_ENABLE),),
        flag_nome="flag2 bit0 · SET_PLAYER_LED_BRIGHTNESS",
    ),
    Ensaio(
        id="volume-do-microfone",
        acoes=("gravar", "reproduzir"),
        titulo="Volume do microfone",
        pergunta="o byte do aparelho muda a captura, ou quem manda é só a fonte do sistema?",
        olhar="Fale «aaaa» em cada parada. O pico da gravação decide, não o ouvido.",
        sprint="MIC-VOLUME-02",
        linha_do_mapa="audio.microfone.volume@dualsense",
        campos=(
            Campo("Volume", rep.COMMON_MIC_VOLUME, minimo=0, maximo=rep.TETO_MIC_VOLUME,
                  inicial=rep.TETO_MIC_VOLUME,
                  marcas=((0, "0"), (0x20, "meio"), (rep.TETO_MIC_VOLUME, "teto 0x40"))),
        ),
        autorizacoes=((0, rep.VALID_FLAG0_MIC_VOLUME),),
        flag_nome="flag0 0x40 · SET_MICROPHONE_VOLUME",
    ),
    Ensaio(
        id="volume-do-fone",
        acoes=("tocar",),
        titulo="Volume do fone (a segunda saída)",
        pergunta="o fone tem volume próprio, separado do alto-falante do controle?",
        olhar="Fone plugado no controle. Mexa só este e ouça.",
        sprint="FONE-01",
        linha_do_mapa="audio.jack.volume@dualsense",
        campos=(
            Campo("Volume", rep.COMMON_HEADPHONE_VOLUME, minimo=0,
                  maximo=rep.TETO_HEADPHONE_VOLUME, inicial=0x40,
                  marcas=((0, "0"), (0x40, "meio"), (rep.TETO_HEADPHONE_VOLUME, "teto 0x7F"))),
        ),
        autorizacoes=((0, rep.VALID_FLAG0_HEADPHONE_VOLUME),),
        flag_nome="flag0 0x10 · SET_HEADPHONE_VOLUME",
    ),
    Ensaio(
        id="volume-do-alto-falante",
        acoes=("tocar",),
        titulo="Volume do alto-falante do controle",
        pergunta="o curso inteiro do byte é útil, ou ele satura antes do teto?",
        olhar="O alto-falante do controle. Ela mediu em 01/08: mudo até 38, satura em 102.",
        sprint="SOM-POR-CONTROLE-01",
        linha_do_mapa="audio.alto_falante.volume@dualsense",
        campos=(
            Campo("Volume", rep.COMMON_SPEAKER_VOLUME, minimo=0, maximo=255, inicial=0x80,
                  marcas=((0, "0"), (38, "38"), (102, "102"), (255, "255"))),
        ),
        autorizacoes=((0, rep.VALID_FLAG0_SPEAKER_VOLUME),),
        flag_nome="flag0 0x20 · SET_AUDIO_VOLUME",
    ),
    Ensaio(
        id="pre-amp-do-alto-falante",
        acoes=("tocar",),
        titulo="Pré-amplificador do alto-falante",
        pergunta="o ganho é a peça que faltava para o curso do volume valer inteiro?",
        olhar="O alto-falante. O kernel 6.18 escolhe o degrau 2.",
        sprint="SOM-ROTA-01",
        linha_do_mapa="audio.alto_falante.preamp@dualsense",
        campos=(
            Campo("Ganho", rep.COMMON_AUDIO_CONTROL2, minimo=0, maximo=rep.SP_PREAMP_GAIN_MASK,
                  inicial=rep.SP_PREAMP_GAIN_PADRAO,
                  marcas=((0, "0"), (rep.SP_PREAMP_GAIN_PADRAO, "kernel"), (7, "7"))),
        ),
        autorizacoes=((1, rep.VALID_FLAG1_AUDIO_CONTROL2_ENABLE),),
        flag_nome="flag1 0x80 · AUDIO_CONTROL2",
    ),
    Ensaio(
        id="rota-da-saida",
        acoes=("tocar",),
        titulo="Para onde o som vai",
        pergunta="as quatro rotas fazem o que o nome delas diz?",
        olhar="Onde o som sai: fone, alto-falante do controle, ou os dois divididos.",
        sprint="SOM-POR-CONTROLE-01",
        linha_do_mapa="audio.alto_falante.rota@dualsense",
        campos=(
            # REDUZIDAS ÀS QUE FUNCIONAM — decisão dela, 09/09/2026: *"reduzir
            # pras que funcionam"*, depois de medir as quatro e achar
            # *"NA REAL TODOS SÃO MONO NO FONE, O DO ALTO FALANTE NÃO FUNCIONA
            # AQUI MAS FUNCIONOU NO SOM DO CONTROLE"*.
            #
            # Ficam as DUAS que fazem o que o nome diz. As outras continuam no
            # `ds_output_report` — o firmware as aceita, e apagá-las de lá seria
            # apagar protocolo. O que sai é a OFERTA: a tela não nomeia por
            # consequência três rotas que produzem a mesma coisa.
            #
            # A CONTRADIÇÃO MEDIDA, e ela pede uma segunda passada: «só no
            # alto-falante» não saiu por esta rota, mas o alto-falante TOCA pelo
            # ensaio de volume. Ou a rota não é o caminho, ou o valor 3 não é o
            # que a fonte externa diz. Enquanto não se medir, ela fica na oferta
            # com o nome que o ensaio sustenta.
            Campo("Rota", rep.COMMON_AUDIO_PATH, forma="escolha",
                  desloca=rep.OUTPUT_PATH_SEL_SHIFT, base=BASE_DO_BYTE_7,
                  escolhas=(
                      (rep.SAIDA_ESTEREO_NO_FONE, "estéreo no fone"),
                      (rep.SAIDA_SO_NO_ALTO_FALANTE, "só no alto-falante (a conferir)"),
                  )),
        ),
        autorizacoes=((0, rep.VALID_FLAG0_AUDIO_PATH),),
        flag_nome="flag0 0x80 · SET_AUDIO_PATH",
    ),
    Ensaio(
        id="forca-por-motor",
        acoes=("vibrar",),
        titulo="Força de cada motor de vibração",
        pergunta="os dois motores respondem ao byte, e um degrau de 150% chega mesmo ao motor?",
        olhar="A vibração na sua mão, motor por motor.",
        sprint="VIBRA-MULT-01",
        linha_do_mapa="vibracao.rumble.direito@dualsense",
        campos=(
            Campo("Motor direito", 2, minimo=0, maximo=255,
                  marcas=((0, "0"), (128, "meio"), (255, "255")),
                  linha_do_mapa="vibracao.rumble.direito@dualsense"),
            Campo("Motor esquerdo", 3, minimo=0, maximo=255,
                  marcas=((0, "0"), (128, "meio"), (255, "255")),
                  linha_do_mapa="vibracao.rumble.esquerdo@dualsense"),
        ),
        autorizacoes=(
            (0, rep.VALID_FLAG0_COMPATIBLE_VIBRATION),
            (0, rep.VALID_FLAG0_HAPTICS_SELECT),
            (1, rep.VALID_FLAG1_MOTOR_POWER),
            (rep.COMMON_VALID_FLAG2, rep.VALID_FLAG2_COMPATIBLE_VIBRATION2),
        ),
        flag_nome="os QUATRO do produto: COMPATIBLE_VIBRATION + HAPTICS_SELECT "
                  "+ MOTOR_POWER + COMPATIBLE_VIBRATION2",
    ),
    Ensaio(
        id="lampadas-de-numeracao",
        titulo="Quais lâmpadas acendem",
        pergunta="o desenho das cinco lâmpadas obedece ao bitmap?",
        olhar="As cinco lâmpadas embaixo do touchpad.",
        sprint="—",
        linha_do_mapa="luz.led_jogador@dualsense",
        campos=(
            Campo("Desenho", 43, minimo=0, maximo=31,
                  marcas=((0, "nenhuma"), (4, "P1"), (10, "P2"), (21, "P3"), (27, "P4"), (31, "todas"))),
        ),
        autorizacoes=((1, rep.VALID_FLAG1_PLAYER_INDICATOR_CONTROL_ENABLE),),
        flag_nome="flag1 0x10 · PLAYER_INDICATOR",
    ),
    Ensaio(
        id="led-do-microfone",
        titulo="LED do botão do microfone",
        pergunta="quantos níveis o LED aceita — só aceso e apagado, ou há um fraco no meio?",
        olhar="A luz do botão do microfone.",
        sprint="MIC-OS-QUATRO-01",
        linha_do_mapa="luz.led_microfone@dualsense",
        campos=(
            Campo("Nível", 8, minimo=0, maximo=2,
                  marcas=((0, "apagado"), (1, "aceso"), (2, "pulso"))),
        ),
        autorizacoes=((1, rep.VALID_FLAG1_MIC_MUTE_LED_CONTROL_ENABLE),),
        flag_nome="flag1 0x01 · TOGGLE_MIC_BUTTON_LED",
    ),
    Ensaio(
        id="cor-da-barra",
        titulo="Cor da barra de luz",
        pergunta="a cor obedece sem depender de nenhum outro bit? (a regressão do caminho da cor)",
        olhar="A barra. Ela NÃO deve depender da autorização de brilho.",
        sprint="—",
        linha_do_mapa="luz.lightbar.cor@dualsense",
        campos=(
            Campo("Cor", 44, forma="cor"),
            Campo("Intensidade", 44, forma="intensidade", minimo=0, maximo=100, inicial=100,
                  marcas=((0, "apagada"), (30, "30%"), (60, "60%"), (100, "cheia"))),
        ),
        autorizacoes=((1, rep.VALID_FLAG1_LIGHTBAR_CONTROL_ENABLE),),
        flag_nome="flag1 0x04 · LIGHTBAR_CONTROL",
    ),
)


@dataclass
class Aparelho:
    """Um controle físico: o `common` vivo, a porta e o martelo."""

    alvo: object
    common: bytearray = field(default_factory=common_vazio)
    ligados: set = field(default_factory=set)
    escritas: int = 0
    erro: str | None = None
    escritor: Escritor = None  # type: ignore[assignment]
    #: Os nós de som DESTE controle, do censo. Vazio quando não há — e aí o
    #: botão diz por quê, em vez de ficar mudo: recusar dizendo é obrigatório.
    sink_fisico: str = ""
    fonte_fisica: str = ""
    ultimo_wav: str = ""
    gravando: subprocess.Popen | None = None
    #: A cor pedida e o quanto dela sai. A barra NÃO tem brilho de hardware —
    #: medido por ela em 09/09 — então a única intensidade que existe é esta:
    #: multiplicar o RGB antes de mandar, que é o que o produto faz em
    #: `led.set {brightness}`. Ela viu isso na paleta do seletor de cor, onde a
    #: coluna de tons do mesmo verde É a escada de intensidade.
    cor_base: tuple[int, int, int] = (255, 255, 255)
    intensidade: float = 1.0
    #: O tom do PLÁSTICO deste controle, perguntado a ELE. É a borda que marca
    #: a cor escolhida, e o X que marca a cor tomada na coluna do vizinho.
    #: Vazio = não sei, e aí a borda é neutra em vez de mentir uma cor.
    tom_do_plastico: str = ""
    nome_do_plastico: str = ""

    def __post_init__(self) -> None:
        self.ler_o_plastico()
        self.escritor = Escritor(self.alvo)

    def ler_o_plastico(self) -> None:
        """Pergunta a cor do plástico AO APARELHO, pelo caminho do produto.

        `ler_pelo_cabo` monta o `SET_FEATURE 0x80` e decodifica o serial. Não
        responder é caso comum, e falhar em silêncio pintaria uma borda
        inventada: sem resposta o tom fica vazio e a borda vira neutra.
        """
        try:
            from hefesto_dualsense4unix.integrations.cor_do_plastico import ler_pelo_cabo

            cor = ler_pelo_cabo(self.alvo.mac)
        except Exception:
            cor = None
        if cor is not None:
            self.tom_do_plastico = cor.tom
            self.nome_do_plastico = cor.nome
        try:
            self.escritor.abrir()
        except Exception as erro:
            self.erro = str(erro)

    @property
    def nome(self) -> str:
        return ("CABO" if self.alvo.transporte == CABO else "RÁDIO") + " · " + mascarar(self.alvo.mac)

    def por_o_bit(self, ensaio: Ensaio, ligado: bool) -> None:
        for offset, bit in ensaio.autorizacoes:
            if ligado:
                self.common[offset] |= bit
            else:
                self.common[offset] &= ~bit & 0xFF
        if ligado:
            self.ligados.add(ensaio.id)
        else:
            self.ligados.discard(ensaio.id)

    def escrever_campo(self, campo: Campo, valor: int) -> None:
        if campo.desloca or campo.base:
            self.common[campo.offset] = (campo.base | ((valor << campo.desloca) & 0xFF)) & 0xFF
        else:
            self.common[campo.offset] = valor & 0xFF

    def escrever_cor(self, rgb: tuple[int, int, int] | None = None,
                     intensidade: float | None = None) -> None:
        """A cor VEZES a intensidade. É a mesma conta do produto, num deslizante."""
        if rgb is not None:
            self.cor_base = rgb
        if intensidade is not None:
            self.intensidade = max(0.0, min(1.0, intensidade))
        saida = tuple(round(v * self.intensidade) for v in self.cor_base)
        self.common[44], self.common[45], self.common[46] = (v & 0xFF for v in saida)

    def bater(self) -> None:
        if self.erro is not None or not self.ligados:
            return
        try:
            self.escritor.escrever(self.common)
            self.escritas += 1
        except Exception as erro:
            self.erro = str(erro)

    def devolver(self) -> None:
        self.common = common_vazio()
        self.ligados.clear()
        if self.erro is None:
            try:
                self.escritor.escrever(self.common)
            except Exception as erro:
                self.erro = str(erro)

    def fechar(self) -> None:
        self.parar_de_gravar()
        self.devolver()
        self.escritor.fechar()

    # -- os ATOS: o que ela ouve e sente, não o que o byte diz ---------------
    @property
    def curto(self) -> str:
        return "cabo" if self.alvo.transporte == CABO else "radio"

    def gravar(self, ao_terminar) -> str | None:
        """Grava o microfone DESTE controle. Devolve o motivo quando não dá."""
        if not self.fonte_fisica:
            return "este controle não publica microfone (o rádio ainda não tem nó de áudio)"
        if not GRAVADOR and not shutil.which("parec"):
            return "não há parec nem pw-record nesta máquina"
        os.makedirs(PASTA, exist_ok=True)
        cru = os.path.join(PASTA, f"mic-{self.curto}.raw")
        self.ultimo_wav = os.path.join(PASTA, f"mic-{self.curto}.wav")
        try:
            saida = open(cru, "wb")  # noqa: SIM115 — fechado em `encerrar`
            self.gravando = subprocess.Popen(
                ["parec", f"--device={self.fonte_fisica}", "--rate=48000",
                 "--channels=1", "--format=s16le"],
                stdout=saida, stderr=subprocess.DEVNULL,
            )
        except OSError as erro:
            return str(erro)

        def encerrar() -> bool:
            self.parar_de_gravar()
            saida.close()
            self._cru_para_wav(cru, self.ultimo_wav)
            ao_terminar(pico_do_wav(self.ultimo_wav))
            return False

        GLib.timeout_add(int(SEGUNDOS_DE_GRAVACAO * 1000), encerrar)
        return None

    def parar_de_gravar(self) -> None:
        """Termina pelo objeto do processo — nunca por padrão de linha de comando."""
        if self.gravando is not None and self.gravando.poll() is None:
            self.gravando.terminate()
            try:
                self.gravando.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self.gravando.kill()
        self.gravando = None

    @staticmethod
    def _cru_para_wav(cru: str, destino: str) -> None:
        """O `parec` não fecha header nenhum quando morre — o WAV se monta aqui."""
        try:
            with open(cru, "rb") as f:
                dados = f.read()
        except OSError:
            return
        with wave.open(destino, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(48000)
            w.writeframes(dados[: len(dados) // 2 * 2])

    def reproduzir(self) -> str | None:
        """Toca de volta o que o microfone deste controle captou."""
        if not self.ultimo_wav or not os.path.exists(self.ultimo_wav):
            return "grave antes — não há nada deste controle para reproduzir"
        if not TOCADOR:
            return "não há paplay nem pw-play nesta máquina"
        subprocess.Popen([TOCADOR, self.ultimo_wav],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return None

    def tocar_no_controle(self) -> str | None:
        """O tom de teste NO alto-falante deste controle."""
        if not self.sink_fisico:
            return "este controle não publica saída de áudio (o rádio ainda não tem nó)"
        if not shutil.which("paplay"):
            return "não há paplay nesta máquina"
        subprocess.Popen(["paplay", f"--device={self.sink_fisico}", tom_de_teste()],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return None

    def vibrar(self, ensaio) -> str | None:
        """Um PULSO de 1 s com a força dos deslizantes. Martelar força contínua
        deixa o controle tremendo até ela desligar, e ninguém mede assim."""
        antes = ensaio.id in self.ligados
        self.por_o_bit(ensaio, True)

        def parar() -> bool:
            if not antes:
                self.por_o_bit(ensaio, False)
            return False

        GLib.timeout_add(1000, parar)
        return None


class Folha:
    def __init__(self, aparelhos: list[Aparelho], enxuta: bool = False,
                 so_falta: bool = False) -> None:
        self.aparelhos = aparelhos
        self.fechados = respondidos() if so_falta else set()
        self.escondidos = 0
        #: `--so-ajustes`, pedido dela: só os controles, sem uma linha de prosa.
        #: A folha completa continua existindo; esta é a MESMA tabela sem o
        #: texto — quem já sabe o que está medindo não relê a pergunta a cada
        #: ensaio, e a rolagem encolhe.
        self.enxuta = enxuta
        #: UMA NOTA POR (ensaio, aparelho). Era uma por ensaio até 09/09 e o
        #: defeito apareceu na primeira leva dela: o que ela viu NO CABO saiu
        #: escrito também na linha do RÁDIO — que nem nó de áudio tem. Régua
        #: que afirma sobre o que não mediu é a família de defeito mais cara
        #: desta casa.
        self.notas: dict[tuple[str, str], Gtk.Entry] = {}
        #: As escadas de tom, redesenhadas no tique. Decisão dela, 09/09/2026:
        #: *"na linha de brilho vamos fazer a ilusão de que o slicer funciona.
        #: Subindo tons ou diminuindo eles"* — e a palavra ILUSÃO é exata: a
        #: barra não tem brilho de hardware (medido de manhã), então o que sobe
        #: e desce é o RGB multiplicado, que é a mesma conta do produto.
        self.escadas: list[tuple[Gtk.DrawingArea, Aparelho]] = []
        #: As amostras de cor, redesenhadas no tique: o X de uma depende do que
        #: o OUTRO controle escolheu, e isso muda por fora dela.
        self.amostras: list[Gtk.DrawingArea] = []
        self.recados_de_cor: dict[str, Gtk.Label] = {}
        self.contadores: list[tuple[Aparelho, Gtk.Label]] = []

        self.janela = Gtk.Window(title="Ajustes do controle" if enxuta else "Ensaios do controle")
        self.janela.set_default_size(880, 700 if enxuta else 780)
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
        for ensaio in ENSAIOS:
            donos = {c.linha_do_mapa or ensaio.linha_do_mapa for c in ensaio.campos}
            if self.fechados and donos <= self.fechados:
                self.escondidos += 1
                continue
            corpo.pack_start(self._secao(ensaio), False, False, 0)
        rolagem.add(corpo)
        raiz.pack_start(rolagem, True, True, 0)

        GLib.timeout_add(int(1000 / HZ), self._tique)

    def _fundo_opaco(self) -> None:
        """Um fundo SÓLIDO, e a razão é dela: *"o fundo tá muito transparente"*.

        Uma `Gtk.Window` sem widget de fundo herda o do compositor, e sob o
        COSMIC isso vira uma folha translúcida com o desktop dela atravessando
        — que é o pior fundo possível para um instrumento onde ela olha uma
        lâmpada acender. A cor sai do tema (`prefer-dark` na máquina dela), com
        alfa 1 escrito à mão: o que não pode é herdar transparência.
        """
        ajustes = Gtk.Settings.get_default()
        escuro = bool(ajustes and ajustes.get_property("gtk-application-prefer-dark-theme"))
        fundo, letra, moldura = (
            ("#1f1f1f", "#f2f2f2", "#2a2a2a") if escuro else ("#f6f5f4", "#1b1b1b", "#ffffff")
        )
        css = (
            f"window, window.background {{ background-color: {fundo}; color: {letra}; }}"
            f"frame {{ background-color: {moldura}; border-radius: 6px; }}"
            f"scrolledwindow {{ background-color: {fundo}; }}"
        )
        provedor = Gtk.CssProvider()
        provedor.load_from_data(css.encode("utf-8"))
        Gtk.StyleContext.add_provider_for_screen(
            Gdk.Screen.get_default(), provedor, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )
        self.janela.set_app_paintable(False)

    # ------------------------------------------------------------------ topo
    def _topo(self) -> Gtk.Widget:
        caixa = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        caixa.set_margin_top(10)
        caixa.set_margin_start(14)
        caixa.set_margin_end(14)
        quem = Gtk.Label()
        quem.set_markup("<b>" + "</b>   ·   <b>".join(a.nome for a in self.aparelhos) + "</b>")
        quem.set_xalign(0.0)
        caixa.pack_start(quem, False, False, 0)
        if self.escondidos:
            fora = Gtk.Label(
                label=f"{self.escondidos} ensaio(s) fora daqui: já têm veredito no caderno. "
                      "Sem --so-falta eles voltam."
            )
            fora.set_xalign(0.0)
            fora.get_style_context().add_class("dim-label")
            caixa.pack_start(fora, False, False, 0)
        if not self.enxuta:
            dica = Gtk.Label(
                label="Ligue «Assumir» no ensaio, mexa, e olhe o aparelho. "
                      "Se piscar entre dois estados, o byte age — é o daemon disputando."
            )
            dica.set_xalign(0.0)
            dica.get_style_context().add_class("dim-label")
            caixa.pack_start(dica, False, False, 0)

        linha = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        for aparelho in self.aparelhos:
            conta = Gtk.Label()
            conta.get_style_context().add_class("dim-label")
            self.contadores.append((aparelho, conta))
            linha.pack_start(conta, False, False, 0)
        tudo = Gtk.Button(label="Devolver TUDO ao daemon")
        tudo.connect("clicked", lambda *_: [a.devolver() for a in self.aparelhos])
        linha.pack_end(tudo, False, False, 0)
        caixa.pack_start(linha, False, False, 0)
        caixa.pack_start(Gtk.Separator(), False, False, 6)
        return caixa

    # ----------------------------------------------------------------- seção
    def _secao(self, ensaio: Ensaio) -> Gtk.Widget:
        moldura = Gtk.Frame()
        dentro = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        dentro.set_margin_top(10)
        dentro.set_margin_bottom(10)
        dentro.set_margin_start(12)
        dentro.set_margin_end(12)

        titulo = Gtk.Label()
        titulo.set_markup(f"<b>{ensaio.titulo}</b>"
                          + ("" if self.enxuta else f"   <span size='small'>{ensaio.sprint}</span>"))
        titulo.set_xalign(0.0)
        dentro.pack_start(titulo, False, False, 0)

        if not self.enxuta:
            for texto, classe in ((ensaio.pergunta, None), (f"OLHE: {ensaio.olhar}", "dim-label"),
                                  (f"autorização: {ensaio.flag_nome}", "dim-label")):
                rot = Gtk.Label(label=texto)
                rot.set_xalign(0.0)
                rot.set_line_wrap(True)
                if classe:
                    rot.get_style_context().add_class(classe)
                dentro.pack_start(rot, False, False, 0)
            if ensaio.estado != "aberto":
                selo = Gtk.Label()
                selo.set_markup(f"<span foreground='#2ec27e'>{ensaio.estado}</span>")
                selo.set_xalign(0.0)
                dentro.pack_start(selo, False, False, 0)

        colunas = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=18)
        colunas.set_homogeneous(True)
        colunas.set_margin_top(6)
        for aparelho in self.aparelhos:
            colunas.pack_start(self._coluna(ensaio, aparelho), True, True, 0)
        dentro.pack_start(colunas, False, False, 0)

        if not self.enxuta:
            gravar = Gtk.Button(label="Gravar o que eu vi")
            gravar.connect("clicked", lambda _b, e=ensaio: self.propor(e))
            gravar.set_margin_top(6)
            dentro.pack_start(gravar, False, False, 0)

        moldura.add(dentro)
        return moldura

    def _coluna(self, ensaio: Ensaio, aparelho: Aparelho) -> Gtk.Widget:
        caixa = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        cabeca = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        nome = Gtk.Label()
        nome.set_markup(f"<small>{aparelho.nome}</small>")
        nome.set_xalign(0.0)
        cabeca.pack_start(nome, False, False, 0)
        chave = Gtk.Switch()
        chave.set_tooltip_text("Assumir este ensaio: liga o bit de autorização e começa a martelar.")
        chave.connect("notify::active",
                      lambda c, _p, e=ensaio, a=aparelho: a.por_o_bit(e, c.get_active()))
        cabeca.pack_end(chave, False, False, 0)
        cabeca.pack_end(Gtk.Label(label="Assumir"), False, False, 0)
        caixa.pack_start(cabeca, False, False, 0)

        for campo in ensaio.campos:
            caixa.pack_start(self._campo(campo, aparelho), False, False, 0)
        if ensaio.acoes:
            caixa.pack_start(self._atos(ensaio, aparelho), False, False, 4)
        if not self.enxuta:
            nota = Gtk.Entry()
            nota.set_placeholder_text(f"O que eu vi no {aparelho.nome.split(' ·')[0]}")
            nota.set_hexpand(True)
            self.notas[(ensaio.id, aparelho.alvo.mac)] = nota
            caixa.pack_start(nota, False, False, 4)
        return caixa

    #: O rótulo de cada botão, e o que ele faz. A tabela existe para o botão
    #: novo nascer aqui, e não espalhado por dez `if`.
    _ATOS: ClassVar[dict[str, str]] = {
        "gravar": "Gravar 3 s",
        "reproduzir": "Reproduzir",
        "tocar": "Tocar no controle",
        "vibrar": "Vibrar 1 s",
    }

    def _atos(self, ensaio: Ensaio, aparelho: Aparelho) -> Gtk.Widget:
        caixa = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        linha = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        recado = Gtk.Label()
        recado.set_xalign(0.0)
        recado.set_line_wrap(True)
        recado.get_style_context().add_class("dim-label")
        for acao in ensaio.acoes:
            botao = Gtk.Button(label=self._ATOS[acao])
            botao.connect("clicked", lambda _b, a=acao, ap=aparelho, e=ensaio, r=recado:
                          self._fazer(a, ap, e, r))
            linha.pack_start(botao, True, True, 0)
        caixa.pack_start(linha, False, False, 0)
        caixa.pack_start(recado, False, False, 0)
        return caixa

    @staticmethod
    def _valor(campo: Campo, aparelho: Aparelho) -> str:
        """O que a linha do caderno registra. A intensidade é %, não byte."""
        if campo.forma == "intensidade":
            return f"{round(aparelho.intensidade * 100)}%"
        return str(aparelho.common[campo.offset])

    def _amostra(self, nome: str, rgb: tuple[int, int, int], aparelho: Aparelho) -> Gtk.Widget:
        """Um quadrado da cor, desenhado — porque ele carrega TRÊS estados.

        Livre; ESCOLHIDO por este controle (borda da cor do plástico dele); ou
        TOMADO por outro (um X na cor do plástico do outro, e o clique recusa
        dizendo de quem é). Decisão dela, 09/09/2026: *"onde eu escolher uma
        cor, em volta dela fica a borda da cor do plastico do controle e um X
        na cor selecionada por mim de forma que me impeça de setar alguma cor
        de um coleguinha"*.
        """
        area = Gtk.DrawingArea()
        area.set_size_request(-1, 26)
        area.connect("draw", self._pintar_amostra, rgb, aparelho)
        caixa = Gtk.EventBox()
        caixa.add(area)
        caixa.set_tooltip_text(nome)
        caixa.connect("button-press-event", self._clicar_cor, rgb, aparelho, nome)
        self.amostras.append(area)
        return caixa

    def _dono_da_cor(self, rgb: tuple[int, int, int], menos: Aparelho) -> Aparelho | None:
        """Qual OUTRO controle está com esta cor. `None` = livre."""
        for outro in self.aparelhos:
            if outro is not menos and outro.cor_base == rgb:
                return outro
        return None

    def _pintar_amostra(self, area: Gtk.DrawingArea, cr, rgb: tuple[int, int, int],
                        aparelho: Aparelho) -> bool:
        largura, altura = area.get_allocated_width(), area.get_allocated_height()
        r, g, b = rgb
        cr.set_source_rgb(r / 255, g / 255, b / 255)
        cr.rectangle(2, 2, largura - 4, altura - 4)
        cr.fill()

        dono = self._dono_da_cor(rgb, aparelho)
        if aparelho.cor_base == rgb:
            # A ESCOLHIDA: a borda é a cor do plástico DESTE controle.
            cr.set_source_rgb(*_hex_para_rgb(aparelho.tom_do_plastico or "#c0c0c0"))
            cr.set_line_width(3.0)
            cr.rectangle(1.5, 1.5, largura - 3, altura - 3)
            cr.stroke()
        elif dono is not None:
            # TOMADA: o X na cor do plástico de quem a tem.
            cr.set_source_rgb(*_hex_para_rgb(dono.tom_do_plastico or "#101010"))
            cr.set_line_width(3.0)
            cr.move_to(5, 5)
            cr.line_to(largura - 5, altura - 5)
            cr.move_to(largura - 5, 5)
            cr.line_to(5, altura - 5)
            cr.stroke()
        else:
            cr.set_source_rgb(0.55, 0.55, 0.55)
            cr.set_line_width(1.0)
            cr.rectangle(2.5, 2.5, largura - 5, altura - 5)
            cr.stroke()
        return False

    def _clicar_cor(self, _caixa, _evento, rgb: tuple[int, int, int],
                    aparelho: Aparelho, nome: str) -> bool:
        """RECUSAR DIZENDO: a cor de outro controle não se toma em silêncio."""
        recado = self.recados_de_cor.get(aparelho.alvo.mac)
        dono = self._dono_da_cor(rgb, aparelho)
        if dono is not None:
            if recado is not None:
                de_quem = dono.nome.split(" ·")[0]
                plastico = f" ({dono.nome_do_plastico})" if dono.nome_do_plastico else ""
                recado.set_markup(
                    f"<span foreground='#e5a50a'>{nome} já é do {de_quem}{plastico} — "
                    "escolha outra, ou troque a dele primeiro.</span>"
                )
            return True
        aparelho.escrever_cor(rgb=rgb)
        if recado is not None:
            plastico = aparelho.nome_do_plastico or "plástico não lido"
            recado.set_text(f"{nome} · a borda é a cor do aparelho ({plastico})")
        return True


    def _fazer(self, acao: str, aparelho: Aparelho, ensaio: Ensaio, recado: Gtk.Label) -> None:
        """Um ato. Quando o produto não faz, o motivo VAI PARA A TELA."""
        def recusa(motivo: str | None, feito: str) -> None:
            if motivo:
                recado.set_markup(f"<span foreground='#c01c28'>{motivo}</span>")
            else:
                recado.set_text(feito)

        if acao == "gravar":
            recado.set_text("gravando 3 s — fale «aaaa» agora")
            motivo = aparelho.gravar(
                lambda pico: recado.set_markup(
                    f"<b>pico {pico:.4f}</b>  ·  é ele que decide, não o ouvido"
                    if pico >= 0 else "gravou, mas o WAV não abriu"
                )
            )
            if motivo:
                recusa(motivo, "")
        elif acao == "reproduzir":
            recusa(aparelho.reproduzir(), "tocando o que foi gravado")
        elif acao == "tocar":
            recusa(aparelho.tocar_no_controle(), "tocando no alto-falante do controle")
        elif acao == "vibrar":
            recusa(aparelho.vibrar(ensaio), "pulso de 1 s com a força dos deslizantes")

    def _campo(self, campo: Campo, aparelho: Aparelho) -> Gtk.Widget:
        caixa = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        if campo.forma == "cor":
            rot = Gtk.Label(label=campo.rotulo)
            rot.set_xalign(0.0)
            rot.get_style_context().add_class("dim-label")
            caixa.pack_start(rot, False, False, 0)
            aparelho.escrever_cor((255, 255, 255))
            fileira = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=3)
            for nome, rgb in CORES_DA_LINHA:
                fileira.pack_start(self._amostra(nome, rgb, aparelho), True, True, 0)
            caixa.pack_start(fileira, False, False, 0)
            recado = Gtk.Label()
            recado.set_xalign(0.0)
            recado.set_line_wrap(True)
            recado.get_style_context().add_class("dim-label")
            self.recados_de_cor[aparelho.alvo.mac] = recado
            caixa.pack_start(recado, False, False, 0)
            return caixa

        if campo.forma == "intensidade":
            rot = Gtk.Label(label=campo.rotulo + " — multiplicação do RGB, a única que a barra tem")
            rot.set_xalign(0.0)
            rot.set_line_wrap(True)
            rot.get_style_context().add_class("dim-label")
            caixa.pack_start(rot, False, False, 0)
            ajuste = Gtk.Adjustment(value=campo.inicial, lower=campo.minimo, upper=campo.maximo,
                                    step_increment=1, page_increment=10)
            escala = Gtk.Scale(orientation=Gtk.Orientation.HORIZONTAL, adjustment=ajuste)
            escala.set_digits(0)
            escala.set_round_digits(0)
            escala.set_value_pos(Gtk.PositionType.RIGHT)
            escala.set_hexpand(True)
            for valor, texto in campo.marcas:
                escala.add_mark(valor, Gtk.PositionType.BOTTOM, texto)
            escala.connect("value-changed",
                           lambda sc, a=aparelho: a.escrever_cor(intensidade=sc.get_value() / 100.0))
            caixa.pack_start(escala, False, False, 0)
            escada = Gtk.DrawingArea()
            escada.set_size_request(-1, 22)
            escada.connect("draw", self._pintar_escada, aparelho)
            escada.set_tooltip_text(
                "Os degraus da cor escolhida. O quadro aceso é o que a barra está mostrando."
            )
            self.escadas.append((escada, aparelho))
            caixa.pack_start(escada, False, False, 0)
            return caixa


        if campo.forma == "escolha":
            linha = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            linha.pack_start(Gtk.Label(label=campo.rotulo), False, False, 0)
            combo = Gtk.ComboBoxText()
            for valor, texto in campo.escolhas:
                combo.append(str(valor), texto)
            combo.set_active(0)
            aparelho.escrever_campo(campo, campo.escolhas[0][0])
            combo.connect(
                "changed",
                lambda c, ca=campo, a=aparelho: a.escrever_campo(ca, int(c.get_active_id() or 0)),
            )
            linha.pack_end(combo, True, True, 0)
            caixa.pack_start(linha, False, False, 0)
            return caixa

        rot = Gtk.Label(label=campo.rotulo)
        rot.set_xalign(0.0)
        rot.get_style_context().add_class("dim-label")
        caixa.pack_start(rot, False, False, 0)
        ajuste = Gtk.Adjustment(value=campo.inicial, lower=campo.minimo, upper=campo.maximo,
                                step_increment=1, page_increment=max(1, campo.maximo // 8))
        escala = Gtk.Scale(orientation=Gtk.Orientation.HORIZONTAL, adjustment=ajuste)
        escala.set_digits(0)
        escala.set_round_digits(0)
        escala.set_value_pos(Gtk.PositionType.RIGHT)
        escala.set_hexpand(True)
        for valor, texto in campo.marcas:
            escala.add_mark(valor, Gtk.PositionType.BOTTOM, texto)
        aparelho.escrever_campo(campo, campo.inicial)
        escala.connect("value-changed",
                       lambda s, ca=campo, a=aparelho: a.escrever_campo(ca, round(s.get_value())))
        caixa.pack_start(escala, False, False, 0)
        return caixa


    #: Quantos degraus a escada mostra. Onze é o mesmo número dos matizes da
    #: linha de cor — de 0 a 100 % de dez em dez.
    DEGRAUS_DA_ESCADA: ClassVar[int] = 11

    def _pintar_escada(self, area: Gtk.DrawingArea, cr, aparelho: Aparelho) -> bool:
        """A cor escolhida em onze degraus, com o atual destacado."""
        largura = area.get_allocated_width()
        altura = area.get_allocated_height()
        passo = largura / self.DEGRAUS_DA_ESCADA
        atual = round(aparelho.intensidade * (self.DEGRAUS_DA_ESCADA - 1))
        r, g, b = aparelho.cor_base
        for i in range(self.DEGRAUS_DA_ESCADA):
            fracao = i / (self.DEGRAUS_DA_ESCADA - 1)
            cr.set_source_rgb(r / 255 * fracao, g / 255 * fracao, b / 255 * fracao)
            cr.rectangle(i * passo + 1, 0, passo - 2, altura)
            cr.fill()
            if i == atual:
                cr.set_source_rgb(1.0, 1.0, 1.0)
                cr.set_line_width(2.0)
                cr.rectangle(i * passo + 2, 1, passo - 4, altura - 2)
                cr.stroke()
        return False

    # ---------------------------------------------------------------- laço
    def _tique(self) -> bool:
        for aparelho in self.aparelhos:
            aparelho.bater()
        for escada, _ in self.escadas:
            escada.queue_draw()
        for amostra in self.amostras:
            amostra.queue_draw()
        for aparelho, conta in self.contadores:
            if aparelho.erro:
                conta.set_markup(f"<span foreground='#c01c28'>{aparelho.nome}: {aparelho.erro}</span>")
            else:
                conta.set_text(f"{aparelho.nome}: {len(aparelho.ligados)} assumido(s), "
                               f"{aparelho.escritas} escritas")
        return True

    def propor(self, ensaio: Ensaio) -> None:
        """A folha NÃO conclui: imprime as linhas, e quem coordena as escreve."""
        print(f"\nLINHAS PROPOSTAS — {ensaio.titulo} (docs/data/ensaios.csv):")
        for aparelho in self.aparelhos:
            caixa = self.notas.get((ensaio.id, aparelho.alvo.mac))
            nota = caixa.get_text().strip() if caixa is not None else ""
            if not nota:
                print(f"  (o {aparelho.nome} ficou sem resposta — nada a propor por ele)")
                continue
            transporte = "cabo" if aparelho.alvo.transporte == CABO else "radio"
            assumido = ensaio.id in aparelho.ligados
            for campo in ensaio.campos:
                sufixo = "" if len(ensaio.campos) == 1 else "-" + campo.rotulo.lower().replace(" ", "-")
                print(linha_do_caderno(
                    id=f"folha-{ensaio.id}{sufixo}-{transporte}-{time.strftime('%d%m')}",
                    linha_id=campo.linha_do_mapa or ensaio.linha_do_mapa,
                    transporte=transporte,
                    suspeito=ensaio.pergunta,
                    presente="sim" if assumido else "não",
                    resultado="",
                    observado_por="olho-dela",
                    fonte="scripts/ensaios/a_folha_dos_ensaios.py",
                    nota=f"{campo.rotulo}={self._valor(campo, aparelho)}; "
                         f"autorização {ensaio.flag_nome} "
                         f"{'ligada' if assumido else 'desligada'}; "
                         f"martelo {HZ:g} Hz; ela: {nota or '(sem resposta)'}",
                ))
        sys.stdout.flush()

    def _fechar(self, *_) -> None:
        for aparelho in self.aparelhos:
            aparelho.fechar()
        if Gtk.main_level() > 0:
            Gtk.main_quit()

    def abrir(self) -> None:
        self.janela.show_all()
        Gtk.main()


def main() -> int:
    alvos = alvos_da_mesa()
    if not alvos:
        print("nenhum DualSense físico encontrado. Plugue ou pareie e rode de novo.")
        return 1
    aparelhos = [Aparelho(a) for a in alvos]
    # OS NÓS DE SOM VÊM DO CENSO, não de um `pactl` próprio: um segundo parser
    # da mesma lista é a segunda régua que diverge da primeira em silêncio.
    try:
        for no in censo(alvos):
            for aparelho in aparelhos:
                if mascarar(aparelho.alvo.mac) == no.mac:
                    aparelho.sink_fisico = no.sink_fisico
                    aparelho.fonte_fisica = no.fonte_fisica
    except Exception as erro:
        print(f"censo de som indisponível ({erro}) — os botões de som dirão por quê")
    print(f"aparelhos: {', '.join(a.nome for a in aparelhos)}")
    print(f"ensaios na folha: {len(ENSAIOS)}")
    folha = Folha(aparelhos, enxuta="--so-ajustes" in sys.argv,
                  so_falta="--so-falta" in sys.argv)
    if "--oculta" in sys.argv:
        folha._tique()
        for ensaio in ENSAIOS:
            folha.propor(ensaio)
        folha._fechar()
        return 0
    folha.abrir()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
