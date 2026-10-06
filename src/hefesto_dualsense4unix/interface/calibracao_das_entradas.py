"""A janela que ensina ao produto as entradas USB — inclusive as VAZIAS.

``CALIBRAR-AS-ENTRADAS-01``, tarefas ``CAL-2`` a ``CAL-7`` (26/08/2026).

O DEFEITO, EM UMA FRASE
------------------------

Uma entrada USB vazia não tem aparelho, logo não tem nó de dispositivo — e o
desenho à mão da ``MAPA-4`` nunca a alcança, porque não há o que arrastar.
Metade do mapa dela fica sem número, e o motor do arranjo
(``integrations/arranjo_da_mesa``) publica juízo otimista onde deveria dizer
"aqui não".

O que torna esta tela possível é uma medição de 25/08/2026: **o nó da ENTRADA
existe com a entrada vazia** (``state = not attached``). ``entradas_do_gabinete``
é quem lê; esta janela é quem pergunta.

AS DUAS FASES TÊM PREÇOS MUITO DIFERENTES, E POR ISSO SÃO DUAS
---------------------------------------------------------------

* a **fase sentada** paga primeiro e ninguém levanta: um toque por aparelho,
  e o toque no HUB resolve tudo o que pende dele. Na mesa dela, quatro toques
  cobriam sete aparelhos;
* a **fase em pé** é opcional e visita **só as vazias** (o F-2 da sprint):
  mandar alguém ao fundo do gabinete para ensinar uma entrada que o computador
  já sabe é caminhada por dado que a máquina tem.

A fase sentada tem **fim próprio** — não é preâmbulo da outra (R31).

O QUE ESTA JANELA APROVOU E O QUE ELA NÃO APROVOU
--------------------------------------------------

``docs/data/decisoes-de-produto.csv``, ``D-CALIBRAR-AS-ENTRADAS``: *"APROVADO POR ELA
em 25/08/2026, às ~03h55, VENDO o mockup"*. O carimbo cobre nominalmente as
duas fases, a pergunta única do hub, os dois relógios, o ``[Não alcanço]`` como
saída de primeira classe, a marreta batendo UMA vez em 0,82 s e as quatro
palavras das faces — que por isso entram aqui **verbatim** e não levam selo de
provisório.

**O que ele NÃO aprova:** a tela GTK real, que pede foto antes e depois quando
existir. Aprovar o desenho não é aprovar a tela.

O VEREDITO SAI DO ``sysfs``, NUNCA DA MÃO (o F-1)
--------------------------------------------------

*"o controle vibrou, logo a entrada é boa"* é **falso** sempre que o mesmo
controle também está pareado por Bluetooth — que é o caso normal dela. Com dois
nós do mesmo aparelho, o pulso sai pelo **rádio** e chega à mão mesmo que o cabo
não tenha feito nada. Aqui, o pulso quer dizer **"senti você"**; quem confirma é
:meth:`LogicaDaCalibracao.confirmar_entrada_nova`, comparando a leitura de antes
com a de agora.

GRAVA A CADA RESPOSTA, E NÃO ESPERA O "APLICAR" (o CAL-2)
-----------------------------------------------------------

A cerimônia é abandonável — ``[Já chega por hoje]`` em todo passo, ``Esc``
fazendo o mesmo, sem "tem certeza?" e sem resumo do que faltou (§4.4). Isso só é
honesto se **nenhuma saída perder trabalho**, logo cada resposta vai ao disco na
hora (R28), por ``integrations/lugar_declarado.declarar_a_maquina`` — que não
passa por IPC nenhum e por isso grava com o Hefesto DESLIGADO.

É a porta LARGA de propósito. ``declarar_a_mesa`` é escopada à seção ``mesa`` do
documento, e o mapa não mora lá: mandar o mapa por ela gravaria a mesa e
perderia calado o resto.

POR QUE ESTA JANELA NÃO REUSA A ``LogicaDoMapa``
--------------------------------------------------

``interface/logica_do_mapa.LogicaDoMapa.como_documento`` devolve ``nome`` e
``portas`` de cada face, e **só**. Os campos ``perto`` e ``alto``, que a frente
G3 acrescentou à ``FaceDeclarada`` em 25/08/2026 e que o motor do arranjo lê,
não sobrevivem à volta — e ``faces`` é uma LISTA, que ``fundir_declaracao``
substitui inteira. Passar por lá apagaria o único fato que só ela tem. Aqui a
face viaja como dicionário completo, e o que esta janela não conhece ela
preserva.

**O defeito daquela janela fica relatado, não consertado:** ``mapa_da_mesa.py``
não é posse desta frente (R-A).

O QUE ESTA JANELA NÃO FAZ
--------------------------

**Não cria face nenhuma sozinha.** As quatro palavras são as respostas
possíveis; a face só nasce quando ela toca uma delas.

**Não conserta a HARM-16** (o F-4: ``rumble_active=(0,0)`` desarma a
``zero_motors_on_mode_exit``). É da Onda 9 · Rumble, e o pulso desta tela sai
por quem já tem a posse do rumble — esta janela não escreve no aparelho.

**Não decide a redação final** de frase nenhuma: a dona única do texto da aba é
a ``CONFIGURACOES-O-LEXICO-01``. Todo texto sem carimbo dela vai marcado
``PROVISÓRIO``.
"""
from __future__ import annotations

from dataclasses import dataclass

from hefesto_dualsense4unix.utils.logging_config import get_logger

logger = get_logger(__name__)


FACE_FRENTE = "Frente do gabinete"
FACE_ATRAS = "Atrás do gabinete"
FACE_HUB = "Num hub ou extensão"
FACE_MESA = "Na escrivaninha"

FACES = (FACE_FRENTE, FACE_ATRAS, FACE_HUB, FACE_MESA)

FACE_QUE_E_PERTO = FACE_FRENTE

FACE_QUE_E_ALTO = FACE_HUB

TITULO_DA_JANELA = "Mapear Entrada a Entrada"
PERGUNTA_SENTADA = "Onde fica esta entrada?"
SEM_SAIR_DA_CADEIRA = "sem sair da cadeira"

ROTULO_JA_CHEGA = "Já chega por hoje"
ROTULO_NAO_SEI = "Não sei onde fica"

ROTULO_NAO_ALCANCO = "Não alcanço"

FIM_DA_FASE_SENTADA = "Acabou a parte sem levantar."

CONVITE_EM_PE = (
    "Falta o que está vazio, e essa parte eu não consigo adivinhar. O sistema "
    "me lista mais entradas do que existem no seu gabinete — as que sobram são "
    "conectores internos que ninguém alcança. Se você me mostrar quais existem "
    "de verdade, eu paro de contar as que não existem."
)
ROTULO_VOU_MOSTRAR = "Vou mostrar agora"
ROTULO_DEIXAR_PARA_DEPOIS = "Deixar para quando eu precisar"

#: DualSense": ``state`` é atributo do NÓ, e qualquer coisa que enumere ensina a
CONVITE_DO_ENCAIXE = (
    "Pegue o DualSense e o cabo e encaixe numa entrada vazia. Qualquer "
    "aparelho que o computador reconheça serve — o DualSense é o melhor porque "
    "ele avisa na sua mão. Eu aviso quando achar."
)

PROCURANDO = "Procurando"


SEGUNDOS_ATE_O_NO = 3.4
SEGUNDOS_ATE_A_VIBRACAO = (10.3, 15.6)

def _virgula(numero: float) -> str:
    """``3.4`` vira ``"3,4"`` — o separador decimal desta casa é a vírgula."""
    return f"{numero:.1f}".replace(".", ",")


OS_DOIS_RELOGIOS = (
    f"A entrada aparece para mim em ~{_virgula(SEGUNDOS_ATE_O_NO)} s. O "
    f"controle só consegue vibrar por volta de "
    f"{_virgula(SEGUNDOS_ATE_A_VIBRACAO[0])} a "
    f"{_virgula(SEGUNDOS_ATE_A_VIBRACAO[1])} s — e essa demora é uma correção "
    "que o próprio Hefesto instala para ele não falhar. Não é você, e não é o "
    "seu cabo."
)


LAUDO_BEM = "O que está bem"
LAUDO_ATENCAO = "O que merece atenção"
LAUDO_NAO_CONFERI = "O que eu não consegui conferir"
LAUDO_NAO_MECO = "O que eu não meço"

O_QUE_EU_NAO_MECO = (
    "Se um rádio está atrapalhando o outro. Eu vejo quem divide caminho; "
    "interferência eu não meço, e não vou fingir que meço.",
    "Quanto de bateria cada ajuste custa. Ninguém mediu ainda nesta casa.",
)

PALAVRA_DA_ENTRADA = "Entrada"


POSSE_DA_CALIBRACAO = "calibrar_entradas"


GESTO_CONFIRMAR = "confirmar"
GESTO_ANDAR = "andar"
GESTO_PULAR = "pular"


@dataclass(frozen=True)
class Pergunta:
    """Um passo da fase sentada — uma pergunta, um toque."""

    caminho: str
    rotulo: str
    pendentes: tuple[str, ...]
    e_hub: bool = False


@dataclass(frozen=True)
class Laudo:
    """Os quatro blocos do exame, **sempre os quatro**."""

    bem: tuple[str, ...] = ()
    atencao: tuple[str, ...] = ()
    nao_conferi: tuple[str, ...] = ()
    nao_meco: tuple[str, ...] = O_QUE_EU_NAO_MECO

    def blocos(self) -> tuple[tuple[str, tuple[str, ...]], ...]:
        """Os quatro pares título/linhas, na ordem em que vão para a tela."""
        return (
            (LAUDO_BEM, self.bem),
            (LAUDO_ATENCAO, self.atencao),
            (LAUDO_NAO_CONFERI, self.nao_conferi),
            (LAUDO_NAO_MECO, self.nao_meco),
        )


__all__ = [
    "FACES",
    "FACE_ATRAS",
    "FACE_FRENTE",
    "FACE_HUB",
    "FACE_MESA",
    "GESTO_ANDAR",
    "GESTO_CONFIRMAR",
    "GESTO_PULAR",
    "Laudo",
    "Pergunta",
]

