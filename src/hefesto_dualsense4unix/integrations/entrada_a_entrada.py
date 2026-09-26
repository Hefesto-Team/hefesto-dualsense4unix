"""entrada_a_entrada.py — o motor do «Mapear Entrada a Entrada».

ENTRADA-A-ENTRADA-01 (23/09/2026), a R9 das doze decisões dela do rádio:
*ligar de verdade*. A palavra dela é a especificação:

    "A ideia é usarmos um dualsense e o USB pra sairmos de porta em porta
     mapeando conectando e removendo e falando qual entrada é qual ali. (…) E
     isso tem que ser interligado com o resto das features nossas."
                                                  — citação literal dela

A cerimônia da aba 08 era eco: três telas por âncora, zero gesto, zero campo.
Este módulo é o motor por trás delas. A fiação na página é da
TRANSPLANTE-DA-SECAO-01.

O MOTOR SERVE AS TRÊS TELAS APROVADAS (ENTRADA-A-ENTRADA-02)
-------------------------------------------------------------

A conferência da 01 achou que as três telas da âncora
``#mapear-entrada-a-entrada`` descrevem o fluxo da ``LogicaDaCalibracao``
(``app/widgets/calibrar_entradas``), e o motor da 01 perguntava a face a cada
plug. Decisão de quem coordena: **o motor serve as telas aprovadas** — a regra
da casa, implemente a imagem aprovada e não o arranjo mais barato. As telas não
mudam, e cada fase abaixo diz qual delas pinta (:data:`TELAS`):

1. **SENTADA** (``#mapear-entrada-a-entrada``) — sobre os aparelhos JÁ
   plugados que não têm lugar: «Onde fica esta entrada?», o aparelho como
   «espécie · caminho», as QUATRO respostas (:data:`FACES`), e «entrada N de
   M · sem sair da cadeira». A resposta de um HUB vale para tudo o que pende
   dele: na mesa dela, quatro toques cobriam sete aparelhos. «Não sei onde
   fica» pula sem gravar e sem perguntar de novo.
2. **FIM** (``#mapear-entrada-a-entrada-fim``) — «Acabou a parte sem
   levantar.», sem contador. Quem já tem lugar para tudo abre a janela direto
   aqui. «Vou mostrar agora» é a única porta para a fase em pé.
3. **EM PÉ** (``#mapear-entrada-a-entrada-em-pe``) — sobre as entradas VAZIAS:
   ela encaixa o DualSense numa, o motor acha. A face NÃO se pergunta: toda
   entrada aprendida de pé é gravada em «Atrás do gabinete»
   (:data:`FACE_EM_PE`). O contador «entrada N de M» é refeito pela leitura de
   AGORA, e «Não alcanço» tira uma vaga da conta DE VEZ.

«Já chega por hoje» fecha em qualquer fase, e nada se perde: cada resposta já
foi ao disco.

SÓ O DUALSENSE MARCA UMA PORTA
------------------------------

Palavra dela na R9: *«usarmos um dualsense e o USB pra sairmos de porta em
porta»*. Aceitar qualquer aparelho deixava uma re-enumeração espontânea — o
``-71``, o reset de porta da ponte root — virar «a porta que ela plugou». Na
fase em pé só um aparelho ``054c`` (:data:`_VID_DA_SONY`) confirma a entrada;
o dongle que re-enumera numa vaga não marca nada.

O VEREDITO SAI DO ``/sys``, NUNCA DA MÃO
----------------------------------------

O mesmo F-1 da janela de ontem: com o controle também pareado por rádio, o
pulso chega à mão pelo Bluetooth mesmo com o cabo inerte. Quem confirma é a
leitura dos NÓS de entrada (``entradas_do_gabinete``): um nó visto vazio que
passou a ter um DualSense.

O LUGAR, E NUNCA O ``hciN`` NEM A ORDEM DE CHEGADA
--------------------------------------------------

A chave gravada é o lugar (``utils/lugar``: o controlador PCI e a cadeia de
portas, a grafia do ``ID_PATH`` do udev), e a amarra confere o ``ID_PATH``
INTEIRO (``utils/maquina.entrada_do_lugar``). O número do barramento é ordem
de subida dos xHCI e muda entre boots.

"VÊ NO UDEV" É LER A ÁRVORE QUE O UDEV LÊ
------------------------------------------

O projeto não tem ``pyudev``. O motor relê ``/sys/bus/usb/devices`` a cada
tique (``censo_do_barramento`` e ``entradas_do_gabinete``, os donos dessa
leitura), e SÓ enquanto a cerimônia está aberta: a regra de «nunca em tique» é
da aba montada, não da janela que ela abriu de propósito.

E A LEITURA NUNCA É NO FIO DA JANELA (O-MAPEAR-NAO-CONGELA-A-JANELA-01,
26/09/2026). O censo lê ``product`` e ``bMaxPower``, e o kernel serve os dois
sob o lock do aparelho — o mesmo que ele segura enquanto enumera o DualSense
que ela acabou de encaixar. A leitura de 8 ms virava 5, 10 e 15 s, a janela
congelava e o COSMIC a derrubava: *«dá um crash feio»*. O tique pinta a última
foto (``foto_sem_esperar``) e a próxima leitura sai num fio próprio
(:class:`_VooDaLeitura`); a trava de cada dono guarda só a troca de estado,
nunca uma leitura. <!-- noqa-acento: citação literal dela -->

ONDE GRAVA — UM DONO, E ELE JÁ EXISTIA
---------------------------------------

O ``maquina.json``, pelo ``lugar_declarado.declarar_a_maquina``, sem IPC:

* ``mapa.faces`` — o número na face;
* ``mapa.portas[número]`` — o caminho de barramento e os nós do buraco (o que
  os seis leitores de hoje e o ``mapa-das-portas.html`` entendem);
* ``lugares[lugar]`` — a amarra pelo LUGAR, com a testemunha do caminho, e o
  «Não alcanço» (``fora``).

O QUE ELE NÃO FAZ
-----------------

* **Não escreve frase de tela.** A única palavra dele é o nome da porta —
  «Entrada 3», a palavra do produto (``D-A-PALAVRA-ENTRADA``) —, e o nome que
  ela der vence sempre.
* **Não fala com o daemon, nem com o rádio, nem com o BlueZ.** O ``Alias`` tem
  UM escritor, o ``bt_active_mode.sh``, que lê o nome do lugar deste mesmo
  ``maquina.json`` no tique do watchdog (ENTRADA-A-ENTRADA-02; a
  ``D-COSTURA-BLUEZ`` dela em ``docs/data/decisoes-dela.csv``).
* **O laço não inventa quinta resposta**: ele fica nas quatro; o fluxo único
  (``MapearAsPortas``) pergunta com os sete de :data:`LUGARES_DA_PORTA`.
"""

from __future__ import annotations

import re
import threading
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from hefesto_dualsense4unix.integrations.censo_do_barramento import (
    Aparelho,
    Censo,
    cadeia_de_hubs,
)
from hefesto_dualsense4unix.integrations.entradas_do_gabinete import (
    VELOCIDADE_SUPERSPEED_MBPS,
    Furo,
    NoDeEntrada,
    entrada_de,
    furos,
)
from hefesto_dualsense4unix.integrations.lugar_declarado import (
    Recibo,
    declarar_a_maquina,
)
from hefesto_dualsense4unix.utils.logging_config import get_logger
from hefesto_dualsense4unix.utils.lugar import FORMA_DO_CAMINHO
from hefesto_dualsense4unix.utils.maquina import (
    MapaDaMesa,
    MaquinaConfig,
    caminho_do_no,
    caminhos_do_lugar,
    carregar_maquina,
    chave_do_adaptador,
    entrada_do_lugar,
    entradas_do_mapa,
    lugar_da_entrada,
    lugar_de,
    lugar_do_caminho,
    lugar_do_no,
    partes_do_lugar,
)

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# As palavras e os estados
# ---------------------------------------------------------------------------

#: As QUATRO respostas de «Onde fica esta entrada?» — as do produto, e as
#: mesmas da janela de hoje (``app/widgets/calibrar_entradas.FACES``, aprovadas
#: por ela em 25/08 e com a quarta trocada por ela em 05/09). Aquele módulo é a
#: janela GTK que o gerador da aba 08 lê por AST, e ele não pode importar daqui
#: sem quebrar o gerador; por isso a lista mora nos dois, e
#: ``test_entrada_a_entrada_grava.py`` trava as duas juntas.
FACE_FRENTE = "Frente do gabinete"
FACE_ATRAS = "Atrás do gabinete"
FACE_HUB = "Num hub ou extensão"
FACE_ESCRIVANINHA = "Na escrivaninha"
FACES = (FACE_FRENTE, FACE_ATRAS, FACE_HUB, FACE_ESCRIVANINHA)

#: OS LUGARES DO GABINETE QUE A PESSOA ESCOLHE — A-08-UM-MAPEAR-SO-01
#: (25/09/2026). O fluxo único pergunta *onde fica* com uma lista que serve a
#: QUALQUER computador: a torre (frente, traseira, topo, lateral), o hub, o
#: monitor e «outro». As três que já existiam ficam com a MESMA grafia — o
#: lugar é a face do ``mapa``, e trocar a palavra deixaria órfãs as faces que
#: ela já gravou. A face que ela gravou por outro nome (a «Na escrivaninha» da
#: lista de antes, ou uma que ela escreveu no «Mapear Entradas») continua
#: aceita na revisita: é dela, e não se apaga por não estar na lista nova.
LUGAR_FRENTE = FACE_FRENTE
LUGAR_TRASEIRA = FACE_ATRAS
LUGAR_TOPO = "Topo do gabinete"
LUGAR_LATERAL = "Lateral do gabinete"
LUGAR_HUB = FACE_HUB
LUGAR_MONITOR = "No monitor"
LUGAR_OUTRO = "Outro lugar"
LUGARES_DA_PORTA = (
    LUGAR_FRENTE,
    LUGAR_TRASEIRA,
    LUGAR_TOPO,
    LUGAR_LATERAL,
    LUGAR_HUB,
    LUGAR_MONITOR,
    LUGAR_OUTRO,
)

#: A face virada para quem senta (``FaceDeclarada.perto``) e a que fica no alto
#: do rack (``FaceDeclarada.alto``) — fato físico que só ela tem, e que só
#: nasce quando ela escolhe a face. A mesma regra de ``calibrar_entradas``.
FACE_QUE_E_PERTO = FACE_FRENTE
FACE_QUE_E_ALTO = FACE_HUB

#: Em pé a face NÃO se pergunta: a dica da tela aprovada diz que *"toda entrada
#: aprendida de pé é gravada em Atrás do gabinete"*, e a janela de ontem fazia
#: o mesmo (``JanelaDeCalibrarEntradas.tique``).
FACE_EM_PE = FACE_ATRAS

#: A palavra do produto para o buraco no gabinete (``D-A-PALAVRA-ENTRADA``).
#: É o nome da porta quando ela não deu outro: «Entrada 3».
PALAVRA_DA_ENTRADA = "Entrada"

#: A FACE QUE UM HUB DECLARADO GANHA — O-MAPA-DAS-CONEXOES-NO-PRODUTO-01,
#: 26/09/2026. Ela diz no editor do mapa que a entrada 5 tem um hub, e o hub
#: vira um lugar: o desenho o mostra como face, e o Mapear o oferece em «onde
#: fica». O editor da página escreve a mesma frase enquanto ela ainda não
#: releu a página (``interface/pagina_do_mapa``); a régua confere as duas.
FACE_DO_HUB_DECLARADO = f"Hub na {PALAVRA_DA_ENTRADA} {{numero}}"

#: O que ela pode dizer que tem numa entrada, além de «Direto» (``None``), e as
#: velocidades — a gramática de ``utils/maquina.PortaDeclarada``.
LIGACOES_DECLARAVEIS = ("hub", "extensor")
VELOCIDADES_DECLARAVEIS = (2, 3)

#: A PONTA DO EXTENSOR — O-MAPA-DAS-CONEXOES-NO-PRODUTO-02, 26/09/2026. O
#: extensor declarado na entrada ``5`` desenha a entrada-filha ``5a``, a mesma
#: letra da ``15a`` que o desenho sempre teve. Só a entrada de número puro tem
#: ponta que grava: ``5aa`` não é um número de entrada que o
#: ``utils/maquina.PortaDeclarada`` aceite, e o editor da página confere a
#: mesma forma antes de mandar o gesto (``interface/pagina_do_mapa``).
LETRA_DA_PONTA = "a"
_SO_DIGITOS = re.compile(r"^[0-9]{1,3}$")

#: As fases do laço — chaves de máquina, para o piloto da aba 08.
PARADO = "parado"
SENTADA = "sentada"
FIM = "fim"
EM_PE = "em_pe"

#: Qual tela aprovada pinta cada fase: as três âncoras da aba 08. Parado não
#: tem tela — a janela está fechada.
TELAS: Mapping[str, str] = {
    SENTADA: "mapear-entrada-a-entrada",
    FIM: "mapear-entrada-a-entrada-fim",
    EM_PE: "mapear-entrada-a-entrada-em-pe",
}

#: Os motivos de uma gravação que não aconteceu, além dos do
#: ``lugar_declarado`` (``versao_estranha``, ``schema_recusou``, ``disco``).
MOTIVO_SEM_LUGAR = "sem_lugar"

#: A Sony — a família DualSense da casa. Na fase em pé, só um aparelho dela
#: marca uma entrada (ver o cabeçalho).
_VID_DA_SONY = "054c"

#: O ``connect_type`` do kernel para a entrada que se alcança de fora do
#: gabinete. As outras (``hardwired``, ``not used``, ``unknown``) são as que
#: mais provavelmente são conectores internos, e são as que o «Não alcanço»
#: tira da conta primeiro.
_ENCAIXE_DE_FORA = "hotplug"

#: QUANTO A LEITURA DO ``/sys`` PODE DEMORAR ANTES DE A FOTO DIZER «procurando»
#: (O-MAPEAR-NAO-CONGELA-A-JANELA-01). Em repouso a leitura inteira custa 8 ms,
#: medido; enquanto o kernel enumera o controle que acabou de chegar, ela
#: espera o lock do aparelho por 3 a 15 s. Um segundo separa os dois com folga,
#: e é o que impede a tela de mostrar a porta de ANTES como a da vez enquanto
#: o controle já está noutra.
FOLEGO_DA_LEITURA_S = 1.0


# ---------------------------------------------------------------------------
# A leitura fora do fio da janela
# ---------------------------------------------------------------------------


def _num_fio_proprio(trabalho: Callable[[], None], nome: str) -> None:
    threading.Thread(target=trabalho, name=nome, daemon=True).start()


class _VooDaLeitura:
    """UMA leitura do ``/sys`` de cada vez, num fio próprio — quem pede não espera.

    O MOLDE É O ``LeitorDeCor.disparar`` (``interface/mesa_viva.py``): reserva,
    fio ``daemon=True``, e a volta — dê certo ou não — solta o voo. O tique
    chama :meth:`disparar` a cada volta; com uma leitura no ar ele não pede
    outra, e a fila não cresce enquanto o kernel segura o aparelho.

    ``fio`` é quem põe o trabalho para correr; o default abre a thread.
    """

    def __init__(
        self,
        ler: Callable[[], object],
        *,
        nome: str,
        fio: Callable[[Callable[[], None], str], None] | None = None,
    ) -> None:
        self._ler = ler
        self._nome = nome
        self._fio = fio or _num_fio_proprio
        self._trava = threading.Lock()
        #: Quando a leitura em voo saiu — ``None`` é nenhuma no ar.
        self._desde: float | None = None

    def disparar(self) -> bool:
        """Pede a próxima leitura. ``False`` quando uma já está no ar."""
        with self._trava:
            if self._desde is not None:
                return False
            self._desde = time.monotonic()
        try:
            self._fio(self._voar, self._nome)
        except Exception:  # defensivo — sem fio não há leitura, e o voo se solta
            logger.debug("leitura_de_fundo_nao_saiu", nome=self._nome, exc_info=True)
            self._pousar()
            return False
        return True

    def no_ar(self) -> bool:
        return self._desde is not None

    def demorando(self) -> bool:
        """A leitura no ar passou do fôlego? É o kernel segurando o aparelho."""
        desde = self._desde
        return desde is not None and time.monotonic() - desde >= FOLEGO_DA_LEITURA_S

    def _voar(self) -> None:
        try:
            self._ler()
        except Exception:  # defensivo — a leitura nunca derruba o fio
            logger.debug("leitura_de_fundo_falhou", nome=self._nome, exc_info=True)
        finally:
            self._pousar()

    def _pousar(self) -> None:
        with self._trava:
            self._desde = None


# ---------------------------------------------------------------------------
# O que a tela recebe
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PortaVista:
    """Um aparelho num lugar — e o que já se sabe daquele lugar.

    ``lugar`` é a chave (D3). ``caminho`` é o nome do kernel DESTE boot, e
    existe para a tela mostrar («espécie · caminho») e para o ``mapa`` de hoje
    entender — nunca para chavear. ``entrada``, ``face`` e ``nome`` vêm
    preenchidos quando ela já disse algo sobre este lugar.
    """

    lugar: str
    caminho: str
    vid: str = ""
    pid: str = ""
    especie: str = ""
    produto: str = ""
    e_dualsense: bool = False
    e_bluetooth: bool = False
    e_hub: bool = False
    entrada: str | None = None
    face: str | None = None
    nome: str | None = None

    def como_dicionario(self) -> dict[str, Any]:
        return {
            "lugar": self.lugar,
            "caminho": self.caminho,
            "vid": self.vid,
            "pid": self.pid,
            "especie": self.especie,  # noqa-acento: chave de máquina, ASCII por contrato
            "produto": self.produto,
            "e_dualsense": self.e_dualsense,
            "e_bluetooth": self.e_bluetooth,
            "e_hub": self.e_hub,
            "entrada": self.entrada,
            "face": self.face,
            "nome": self.nome,
        }


@dataclass(frozen=True)
class Pergunta:
    """Um passo da fase sentada — uma pergunta, um toque.

    ``pendentes`` é o que ganha lugar JUNTO: para um HUB, tudo o que pende dele
    e ainda não tem lugar. É essa lista que faz um toque valer quatro.
    """

    porta: PortaVista
    pendentes: tuple[PortaVista, ...] = ()

    def lugares(self) -> tuple[str, ...]:
        return (self.porta.lugar, *(p.lugar for p in self.pendentes))

    def como_dicionario(self) -> dict[str, Any]:
        return {
            **self.porta.como_dicionario(),
            "pendentes": [p.caminho for p in self.pendentes],
        }


@dataclass(frozen=True)
class Gravacao:
    """O que um gesto dela fez no disco. ``motivo`` é ``""`` quando gravou.

    ``entradas`` são TODOS os números que ganharam dono na resposta — o do
    aparelho e os do que pende dele; ``entrada`` é o do próprio aparelho.
    """

    lugar: str
    entrada: str
    face: str
    gravou: bool
    motivo: str = ""
    entradas: tuple[str, ...] = ()

    def como_dicionario(self) -> dict[str, Any]:
        return {
            "lugar": self.lugar,
            "entrada": self.entrada,
            "face": self.face,
            "gravou": self.gravou,
            "motivo": self.motivo,
            "entradas": list(self.entradas),
        }


@dataclass(frozen=True)
class NomeDado:
    """O que :func:`dar_nome` fez (ou :func:`dar_nome_ao_adaptador`, e aí
    ``lugar`` é a chave do endereço): o nome no disco."""

    lugar: str
    nome: str | None
    gravou: bool
    motivo: str = ""


@dataclass(frozen=True)
class _Vaga:
    """Uma entrada VAZIA da fase em pé — o buraco, o lugar dele e se é de fora."""

    furo: Furo
    lugar: str
    de_fora: bool


# ---------------------------------------------------------------------------
# O laço
# ---------------------------------------------------------------------------


class LacoDaEntrada:
    """O «Mapear Entrada a Entrada», nas três telas aprovadas. Sem GTK e sem IPC.

    Todas as leituras entram por argumento — o barramento (``ler``), os nós de
    entrada (``entradas``), o ``maquina.json`` (``carregar``) e a gravação
    (``gravar``). O default de cada um é o do sistema; a régua troca todos, e
    nenhum caminho de ``/sys`` dela é tocado.

    UMA TRAVA, porque o olhar corre num fio próprio e o gesto dela chega por
    outro: sem a trava, um ``responder`` no meio de um ``olhar`` gravaria a
    pergunta que acabou de mudar. **A TRAVA NUNCA SEGURA UMA LEITURA DO
    ``/sys``** (O-MAPEAR-NAO-CONGELA-A-JANELA-01): cada gesto lê antes de
    tomá-la, e ela guarda só a troca de estado. ESTA FRASE DIZIA *"o tique do
    piloto lê o barramento num fio próprio (desde 15/09 a janela não segura o
    laço do GTK)"*, e era fato errado: o fio de 15/09 era o do IPC; o tique da
    aba 08 chamava ``olhar`` no fio da janela até esta sprint.

    O TIQUE CHAMA :meth:`foto_sem_esperar`, que não lê nada nem toma a trava:
    pinta a última foto e pede a próxima leitura num fio próprio.
    """

    def __init__(
        self,
        *,
        ler: Callable[[], Censo] | None = None,
        entradas: Callable[[], Sequence[NoDeEntrada]] | None = None,
        carregar: Callable[[], MaquinaConfig] | None = None,
        gravar: Callable[[Mapping[str, Any]], Recibo] | None = None,
        fio: Callable[[Callable[[], None], str], None] | None = None,
    ) -> None:
        self._ler = ler or _ler_o_barramento
        self._entradas = entradas or _listar_as_entradas
        self._carregar = carregar or carregar_maquina
        self._gravar = gravar or declarar_a_maquina
        self._trava = threading.Lock()
        #: A sessão da cerimônia: cada começar e cada parar a trocam, e a
        #: leitura que voltar de outra sessão não anda nada.
        self._sessao = 0
        self._zerar(PARADO)
        #: A última foto — o que o tique pinta sem esperar.
        self._pintada: dict[str, Any] = self._foto()
        self._voo = _VooDaLeitura(self.olhar, nome="entrada-a-entrada", fio=fio)

    def _zerar(self, fase: str) -> None:
        self._sessao += 1
        self._fase = fase
        # -- sentada --
        #: Os lugares das perguntas, na ordem em que apareceram: a pergunta da
        #: vez não muda sob o dedo dela quando um aparelho novo chega.
        self._ordem: list[str] = []
        self._perguntas: tuple[Pergunta, ...] = ()
        #: Respondidas e puladas — o N de «entrada N de M».
        self._andadas = 0
        #: Os lugares que já foram pergunta nesta sessão: «sem perguntar de novo».
        self._ja_perguntados: set[str] = set()
        self._primeiro: str | None = None
        # -- em pé --
        #: Os nós vistos VAZIOS desde que ela levantou — é contra eles que o
        #: veredito do ``/sys`` é medido.
        self._referencia: set[str] = set()
        #: Os nós tirados da conta nesta sessão, sem gravar («Não sei onde
        #: fica» em pé, e o «Não alcanço» de uma vaga sem lugar).
        self._fora_hoje: set[str] = set()
        self._aprendidas = 0
        self._vagas: tuple[_Vaga, ...] = ()
        # -- comum --
        self._ultima: Gravacao | None = None
        self._feitas = 0

    # -- os gestos -----------------------------------------------------------

    def comecar(self, lugar: str | None = None) -> dict[str, Any]:
        """Abre a cerimônia na fase sentada — ou direto no fim, sem pergunta.

        ``lugar`` é o atalho «Onde fica?» de um cartão (o ``data-alvo`` do
        ``mapa-do-radio.html``): a pergunta que cobre aquele lugar vem primeiro.

        O «Já chega por hoje» que chegar durante a leitura vence: os dois
        gestos vieram nessa ordem, e a leitura presa no kernel não reabre a
        cerimônia que ela fechou.
        """
        with self._trava:
            sessao = self._sessao
        censo = self._ler_o_censo()
        with self._trava:
            if self._sessao != sessao:
                return self._pintar()
            self._zerar(SENTADA)
            self._primeiro = lugar or None
            self._andar_sentada(censo)
            return self._pintar()

    def olhar(self) -> dict[str, Any]:
        """Um tique: relê o que a fase precisa e anda o laço. Parado e no fim,
        não lê nada.

        A leitura que não respondeu é "não sei", e "não sei" não anda o laço:
        ``Censo()`` sem hub-raiz nenhum (o ``OSError`` de
        ``ler_o_barramento``) ou nenhum nó de entrada lido diriam "nenhuma
        pergunta" e "nenhuma vaga", e a fase pularia para o fim por um tique
        que não viu nada.

        A LEITURA É FORA DA TRAVA, e a que voltar com a fase ou a sessão
        trocadas (ela fechou, respondeu a última, levantou) não anda nada.
        """
        with self._trava:
            fase, sessao = self._fase, self._sessao
            if fase not in (SENTADA, EM_PE):
                return self._pintar()
        censo = self._ler_o_censo()
        lidas = self._ler_as_entradas() if fase == EM_PE else ()
        with self._trava:
            if self._sessao == sessao and self._fase == fase and not _nao_sei(censo):
                if fase == SENTADA:
                    self._andar_sentada(censo)
                elif lidas:
                    self._andar_em_pe(censo, lidas)
            return self._pintar()

    def foto_sem_esperar(self) -> dict[str, Any]:
        """O que o TIQUE pinta: a última foto, sem ler nada e sem tomar a trava.

        Com a cerimônia aberta numa fase que lê, a próxima leitura sai num fio
        próprio (:class:`_VooDaLeitura`) — uma de cada vez.
        """
        if self._fase in (SENTADA, EM_PE):
            self._voo.disparar()
        return self._pintada

    def responder(self, face: str) -> Gravacao:
        """A resposta dela para a pergunta da vez — grava na hora, e vale para o
        que pende do hub.

        Levanta ``ValueError`` para uma face fora das quatro e ``RuntimeError``
        sem pergunta: são os dois jeitos de o gesto chegar errado, e o tratador
        da aba os devolve como recusa (a piscada), nunca como recado. O disco
        que recusa deixa a pergunta onde está.

        A PERGUNTA É A DO CLIQUE, e não a da vez quando a leitura volta: com o
        kernel segurando o ``/sys``, um «Não sei onde fica» ou um «Já chega por
        hoje» clicado depois passa na frente, e a face dela iria para a
        pergunta seguinte — ou se perderia. Ela vale para o que ela respondeu,
        e nada se perde; só a sessão que continua aberta anda.
        """
        if face not in FACES:
            raise ValueError(f"{face!r} não é uma das quatro respostas")
        with self._trava:
            if self._fase != SENTADA or not self._perguntas:
                raise RuntimeError("não há pergunta para responder")
            sessao, clicada = self._sessao, self._perguntas[0]
        censo, lidas = self._ler_o_censo(), self._ler_as_entradas()
        with self._trava:
            aberta = self._sessao == sessao
            # a mesma pergunta como está agora (os pendentes do hub podem ter
            # crescido); se ela já saiu da fila, a do clique
            agora = [p for p in self._perguntas if p.porta.lugar == clicada.porta.lugar]
            da_vez = aberta and bool(agora)
            pergunta = agora[0] if da_vez else clicada
            if _nao_sei(censo):
                # A leitura não respondeu: "não sei" não é "o aparelho saiu", e
                # a pergunta da vez fica onde está.
                raise RuntimeError("o barramento não respondeu")
            presentes = {aparelho.nome_do_kernel for aparelho in censo.conectados()}
            if pergunta.porta.caminho not in presentes:
                # O aparelho saiu entre o tique e o toque: gravar agora poria a
                # resposta dela num buraco vazio. A pergunta da vez anda.
                if aberta and self._fase == SENTADA:
                    self._andar_sentada(censo)
                    self._pintar()
                raise RuntimeError("o aparelho da pergunta saiu do barramento")
            gravacao = _gravar_as_portas(
                [
                    (porta, _nos_do_aparelho(porta.caminho, lidas))
                    for porta in (pergunta.porta, *pergunta.pendentes)
                    if porta.caminho in presentes
                ],
                face,
                maquina=self._carregar(),
                gravar=self._gravar,
                controladores=_controladores(censo),
            )
            if not aberta:
                # ela fechou durante a leitura: a resposta foi ao disco, e a
                # cerimônia fechada continua fechada
                return gravacao
            self._ultima = gravacao
            if gravacao.gravou:
                self._feitas += len(gravacao.entradas)
                self._ja_perguntados.update(pergunta.lugares())
                if da_vez:
                    self._andadas += 1
                    lugar = pergunta.porta.lugar
                    self._perguntas = tuple(
                        p for p in self._perguntas if p.porta.lugar != lugar
                    )
                    if not self._perguntas and self._fase == SENTADA:
                        self._fase = FIM
            self._pintar()
            return gravacao

    def pular(self) -> dict[str, Any]:
        """«Não sei onde fica»: não grava, e não pergunta de novo nesta sessão.

        Sentada, pula a pergunta da vez (e o que pende dela). Em pé, tira da
        conta a vaga da vez, sem gravar — o «Não alcanço» é que é de vez. No
        fim, não há o que pular.
        """
        with self._trava:
            if self._fase == SENTADA and self._perguntas:
                self._ja_perguntados.update(self._perguntas[0].lugares())
                self._perguntas = self._perguntas[1:]
                self._andadas += 1
                if not self._perguntas:
                    self._fase = FIM
            elif self._fase == EM_PE and self._vagas:
                self._fora_hoje.update(self._vagas[0].furo.nos)
                self._tirar_a_vaga_da_vez()
            return self._pintar()

    def levantar(self) -> dict[str, Any]:
        """«Vou mostrar agora»: guarda a leitura de agora como referência e
        entra na fase em pé. É a única porta para ela — só do fim."""
        with self._trava:
            if self._fase != FIM:
                raise RuntimeError("a fase em pé só começa no fim da fase sentada")
        censo, lidas = self._ler_o_censo(), self._ler_as_entradas()
        with self._trava:
            if self._fase != FIM:
                raise RuntimeError("a fase em pé só começa no fim da fase sentada")
            self._fase = EM_PE
            self._referencia = set()
            self._andar_em_pe(censo, lidas)
            return self._pintar()

    def nao_alcanco(self) -> dict[str, Any]:
        """«Não alcanço»: tira a vaga da vez da conta DE VEZ.

        Grava ``lugares[lugar].fora`` — *"não vira dívida, não vira aviso, e o
        Hefesto não volta a perguntar"* — e diminui o TOTAL do contador, não o
        feito. A vaga tirada é a que o kernel menos diz ser de fora
        (``connect_type``), porque a tela não aponta uma: as que sobram são
        conectores internos que ninguém alcança. Se ela encaixar o DualSense
        numa vaga tirada, a leitura vence e a entrada é aprendida.
        """
        with self._trava:
            if self._fase != EM_PE or not self._vagas:
                raise RuntimeError("não há vaga para tirar da conta")
            vaga = self._vagas[0]
            if vaga.lugar:
                recibo = _gravar_no_mapa(
                    self._gravar, {"lugares": {vaga.lugar: {"fora": True}}}
                )
                self._ultima = Gravacao(vaga.lugar, "", "", recibo.gravou, recibo.motivo)
                if not recibo.gravou:
                    logger.warning("entrada_a_entrada_fora_nao_gravou", motivo=recibo.motivo)
            else:
                # Sem lugar não há o que gravar: sai da conta desta sessão.
                self._ultima = Gravacao("", "", "", False, MOTIVO_SEM_LUGAR)
            self._fora_hoje.update(vaga.furo.nos)
            self._tirar_a_vaga_da_vez()
            return self._pintar()

    def parar(self) -> None:
        """«Já chega por hoje»: fecha, e nada se perde — cada resposta já foi."""
        with self._trava:
            self._zerar(PARADO)
            self._pintar()

    def estado(self) -> dict[str, Any]:
        """O que o piloto da aba 08 pinta. Não lê nada."""
        with self._trava:
            return self._foto()

    # -- a fase sentada ------------------------------------------------------

    def _andar_sentada(self, censo: Censo) -> None:
        perguntas = _perguntas_sentadas(
            censo,
            self._carregar(),
            _controladores(censo),
            ja_perguntados=self._ja_perguntados,
        )
        por_lugar = {p.porta.lugar: p for p in perguntas}
        for lugar in por_lugar:
            if lugar not in self._ordem:
                self._ordem.append(lugar)
        if self._primeiro is not None:
            dona = next((p for p in perguntas if self._primeiro in p.lugares()), None)
            if dona is not None:
                self._ordem.remove(dona.porta.lugar)
                self._ordem.insert(0, dona.porta.lugar)
            self._primeiro = None
        self._perguntas = tuple(por_lugar[lugar] for lugar in self._ordem if lugar in por_lugar)
        if not self._perguntas:
            self._fase = FIM

    # -- a fase em pé --------------------------------------------------------

    def _andar_em_pe(self, censo: Censo, lidas: Sequence[NoDeEntrada]) -> None:
        maquina = self._carregar()
        controladores = _controladores(censo)
        buracos = furos(lidas)

        # 1. o veredito, contra a referência dos tiques de antes
        for furo in buracos:
            if not set(furo.nos) & self._referencia:
                continue
            dualsense = _o_dualsense_no_furo(furo, censo)
            if dualsense is None or _o_furo_e_conhecido(furo, maquina, controladores):
                continue
            porta = _porta_vista(dualsense, maquina, controladores)
            gravacao = _gravar_as_portas(
                [(porta, furo.nos)],
                FACE_EM_PE,
                maquina=maquina,
                gravar=self._gravar,
                controladores=controladores,
            )
            self._ultima = gravacao
            self._referencia -= set(furo.nos)
            if gravacao.gravou:
                self._aprendidas += 1
                self._feitas += 1
                maquina = self._carregar()
            break

        # 2. a referência cresce com o que está vazio AGORA
        vazios = [
            furo
            for furo in buracos
            if furo.vazio and not _o_furo_e_conhecido(furo, maquina, controladores)
        ]
        for furo in vazios:
            self._referencia.update(furo.nos)

        # 3. a conta, refeita pela leitura de agora
        vagas: list[_Vaga] = []
        for furo in vazios:
            if set(furo.nos) & self._fora_hoje:
                continue
            lugar = _lugar_do_furo(furo, controladores)
            declarado = maquina.lugares.get(lugar) if lugar else None
            if declarado is not None and declarado.fora:
                continue
            vagas.append(_Vaga(furo, lugar, furo.tipo_de_encaixe == _ENCAIXE_DE_FORA))
        # As que o kernel não diz serem de fora vêm primeiro: o «Não alcanço» e
        # o «Não sei onde fica» tiram a vaga da vez, e a tela não aponta uma.
        self._vagas = tuple(sorted(vagas, key=lambda v: v.de_fora))
        if not self._vagas:
            self._fase = FIM

    def _tirar_a_vaga_da_vez(self) -> None:
        self._vagas = self._vagas[1:]
        if not self._vagas:
            self._fase = FIM

    # -- interno -------------------------------------------------------------

    def _ler_o_censo(self) -> Censo:
        try:
            return self._ler()
        except Exception:  # defensivo — a leitura some sob a mão
            logger.debug("entrada_a_entrada_leitura_falhou", exc_info=True)
            return Censo()

    def _ler_as_entradas(self) -> tuple[NoDeEntrada, ...]:
        try:
            return tuple(self._entradas())
        except Exception:  # defensivo — o sysfs some sob a mão
            logger.debug("entrada_a_entrada_nos_falharam", exc_info=True)
            return ()

    def _pintar(self) -> dict[str, Any]:
        """A foto de agora vira a que o tique pinta. Chamada sob a trava."""
        self._pintada = self._foto()
        return self._pintada

    def _foto(self) -> dict[str, Any]:
        fase = self._fase
        pergunta = self._perguntas[0] if fase == SENTADA and self._perguntas else None
        passo: int | None = None
        total: int | None = None
        if fase == SENTADA:
            passo, total = self._andadas + 1, self._andadas + len(self._perguntas)
        elif fase == EM_PE:
            passo, total = self._aprendidas + 1, self._aprendidas + len(self._vagas)
        ultima = None if self._ultima is None else self._ultima.como_dicionario()
        return {
            "estado": fase,
            "tela": TELAS.get(fase),
            "passo": passo,
            "total": total,
            "pergunta": None if pergunta is None else pergunta.como_dicionario(),
            "face": FACE_EM_PE if fase == EM_PE else None,
            "feitas": self._feitas,
            "gravou": None if self._ultima is None else self._ultima.gravou,
            "ultima": ultima,  # (noqa-acento) chave de máquina, ASCII por contrato
        }


# ---------------------------------------------------------------------------
# As peças do laço — privadas: quem está de fora fala com o laço
# ---------------------------------------------------------------------------


def _perguntas_sentadas(
    censo: Censo,
    maquina: MaquinaConfig,
    controladores: Mapping[int, str],
    *,
    ja_perguntados: set[str],
) -> tuple[Pergunta, ...]:
    """As perguntas da fase sentada, na ordem do barramento.

    * **um lugar, uma pergunta** — os dois lados de um buraco USB 3 chegam em
      dois barramentos com o MESMO lugar; a cara é o lado 2.0;
    * **só o que não tem lugar** — a amarra pelo lugar ou o desenho de hoje já
      dão número a quem tem;
    * **o hub leva o que pende dele** — quem pende de um hub sem lugar não vira
      pergunta própria: viaja nos ``pendentes`` do hub mais alto sem lugar
      (pela ``cadeia_de_hubs``, e não pelo pai: medido em 22/08, os três
      adaptadores desta casa têm dois pais e um hub em comum).

    Hub-raiz não é aparelho (``Censo.conectados``); aparelho sem controlador
    PCI legível não tem lugar, e sem lugar não há o que gravar.
    """
    grupos: dict[str, list[Aparelho]] = {}
    for aparelho in censo.conectados():
        if not (aparelho.nome_do_kernel and aparelho.devpath and aparelho.controlador_pci):
            continue
        grupos.setdefault(lugar_de(aparelho.controlador_pci, aparelho.devpath), []).append(
            aparelho
        )

    sem_lugar: dict[str, tuple[PortaVista, list[Aparelho]]] = {}
    for lugar, membros in grupos.items():
        if lugar in ja_perguntados:
            continue
        porta = _porta_vista(
            _o_lado_20(membros),
            maquina,
            controladores,
            e_hub=any(m.e_hub for m in membros),
        )
        if porta.entrada is None:
            sem_lugar[lugar] = (porta, membros)

    lugar_do_no_de = {m.no: lugar for lugar, (_, membros) in sem_lugar.items() for m in membros}

    def acima(lugar: str) -> set[str]:
        return {
            lugar_do_no_de[hub]
            for membro in sem_lugar[lugar][1]
            for hub in cadeia_de_hubs(censo, membro.no)
            if hub in lugar_do_no_de and lugar_do_no_de[hub] != lugar
        }

    cabeca: dict[str, str] = {}
    for lugar in sem_lugar:
        hubs = acima(lugar)
        cabeca[lugar] = next((h for h in hubs if not acima(h)), lugar) if hubs else lugar

    return tuple(
        Pergunta(
            porta=porta,
            pendentes=tuple(
                sem_lugar[outro][0]
                for outro in sem_lugar
                if outro != lugar and cabeca[outro] == lugar
            ),
        )
        for lugar, (porta, _) in sem_lugar.items()
        if cabeca[lugar] == lugar
    )


def _o_lado_20(membros: Sequence[Aparelho]) -> Aparelho:
    """Dos dois lados do mesmo buraco, o 2.0 — onde o DualSense enumera."""
    return min(membros, key=lambda a: (a.velocidade_mbps, a.busnum))


def _o_dualsense_no_furo(furo: Furo, censo: Censo) -> Aparelho | None:
    """O DualSense encaixado neste buraco — ``None`` para qualquer outro aparelho.

    SÓ O DUALSENSE MARCA UMA PORTA (ENTRADA-A-ENTRADA-02): o dongle que
    re-enumera numa vaga (o ``-71``, o reset de porta da ponte root) não é «a
    porta que ela plugou».
    """
    nomes = {entrada.aparelho for entrada in furo.entradas if entrada.aparelho}
    for aparelho in censo.conectados():
        if (
            aparelho.nome_do_kernel in nomes
            and aparelho.vid.lower() == _VID_DA_SONY
            and aparelho.controlador_pci
            and aparelho.devpath
        ):
            return aparelho
    return None


def _lugar_do_furo(furo: Furo, controladores: Mapping[int, str]) -> str:
    """O lugar de um buraco: o do lado 2.0, onde o DualSense enumera.

    Os dois nós de um buraco USB 3 NÃO dão o mesmo lugar quando o controlador
    numera as duas raízes de jeitos diferentes. Medido na mesa dela em 23/09:
    no ``0000:02:00.0``, ``usb1-port6`` é o par de ``usb2-port2``, e os dois
    lados são ``…-usb-0:6`` e ``…-usb-0:2`` (o udev publica o mesmo ``ID_PATH``
    para ``usb1-port2`` e ``usb2-port2`` — por isso existe o
    ``ID_PATH_WITH_USB_REVISION``). Exigir que os dois concordassem devolvia
    "não sei" para esses buracos: o «Não alcanço» não ia ao disco e a entrada
    aprendida voltava para a conta ao sair o cabo.

    O lado 2.0 é o de barramento MENOR: o xHCI registra a raiz 2.0 antes da
    3.x. É o lugar que o DualSense ganha ali (``_porta_vista``), e o único que
    não colide com o buraco vizinho.
    """
    nos = sorted(
        (no for no in furo.nos if caminho_do_no(no)),
        key=lambda no: int(caminho_do_no(no).partition("-")[0]),
    )
    return lugar_do_no(nos[0], controladores) if nos else ""


def _o_furo_e_conhecido(
    furo: Furo, maquina: MaquinaConfig, controladores: Mapping[int, str]
) -> bool:
    """Este buraco já é uma entrada dela? Pela amarra, pelos nós ou pelo caminho.

    A amarra pelo lugar é a resposta que sobrevive ao boot. Os nós e o caminho
    são o que a outra janela (e a janela de ontem) gravaram no ``mapa``, e os
    dois carregam o número do barramento: valem SÓ para a entrada que ainda
    não tem amarra. Com amarra, o nó gravado é de um boot que talvez não seja
    este — ``usb1-port2`` do primeiro boot é a porta 2 do OUTRO controlador no
    segundo, e o buraco errado sairia da conta.
    """
    lugar = _lugar_do_furo(furo, controladores)
    if lugar and _numero_conhecido(maquina, lugar, "", controladores) is not None:
        return True
    amarradas = {dele.entrada for dele in maquina.lugares.values() if dele.entrada}
    nos = set(furo.nos)
    return any(
        nos & set(porta.nos)
        for numero, porta in maquina.mapa.portas.items()
        if numero not in amarradas
    ) or any(
        _entrada_do_caminho(maquina, caminho_do_no(no), lugar, controladores) is not None
        for no in furo.nos
    )


def _nos_do_aparelho(caminho: str, lidas: Sequence[NoDeEntrada]) -> tuple[str, ...]:
    """Os nós do buraco onde este aparelho está, pela leitura que já está na mão.

    ``entrada_de`` com um ``real`` que não segue link: o índice invertido da
    leitura responde sem tocar o ``/sys`` de novo (``NoDeEntrada.aparelho`` é o
    próprio nó dizendo o que tem dentro).
    """
    furo = entrada_de(caminho, lidas, real=_sem_link)
    return () if furo is None else tuple(furo.nos)


def _sem_link(_caminho: str) -> str:
    return ""


def _porta_vista(
    aparelho: Aparelho,
    maquina: MaquinaConfig,
    controladores: Mapping[int, str],
    *,
    e_hub: bool | None = None,
) -> PortaVista:
    """O aparelho, com o que ela já disse sobre aquele lugar.

    O número vem da mesma pergunta que a gravação faz
    (:func:`_numero_conhecido`), para a tela mostrar o número que a resposta
    vai gravar.
    """
    lugar = lugar_de(aparelho.controlador_pci, aparelho.devpath)
    entrada = _numero_conhecido(maquina, lugar, aparelho.nome_do_kernel, controladores)
    return PortaVista(
        lugar=lugar,
        caminho=aparelho.nome_do_kernel,
        vid=aparelho.vid,
        pid=aparelho.pid,
        especie=aparelho.especie,
        produto=aparelho.produto,
        e_dualsense=aparelho.vid.lower() == _VID_DA_SONY,
        e_bluetooth=(aparelho.classe, aparelho.subclasse, aparelho.protocolo)
        == ("e0", "01", "01"),
        e_hub=aparelho.e_hub if e_hub is None else e_hub,
        entrada=entrada,
        face=None if entrada is None else _face_da_entrada(maquina.mapa, entrada),
        nome=_nome_declarado(maquina, lugar),
    )


def _numero_conhecido(
    maquina: MaquinaConfig,
    lugar: str,
    caminho: str,
    controladores: Mapping[int, str],
) -> str | None:
    """O número que este lugar JÁ tem — ``None`` quando não tem nenhum.

    1. a amarra pelo lugar (``utils/maquina.entrada_do_lugar``, pelo
       ``ID_PATH`` inteiro);
    2. sem ela, o desenho de hoje pelos caminhos deste lugar NESTE boot — os
       dois lados do buraco, e o caminho que o aparelho tem agora. Dois
       números para o mesmo lugar é "não sei".
    """
    numero = entrada_do_lugar(maquina, lugar, controladores)
    if numero is not None:
        return numero
    caminhos = {caminho, *caminhos_do_lugar(lugar, controladores)} - {""}
    achados = {
        achado
        for um in caminhos
        if (achado := _entrada_do_caminho(maquina, um, lugar, controladores)) is not None
    }
    return achados.pop() if len(achados) == 1 else None


def _gravar_as_portas(
    portas: Sequence[tuple[PortaVista, Sequence[str]]],
    face: str,
    *,
    maquina: MaquinaConfig,
    gravar: Callable[[Mapping[str, Any]], Recibo] = declarar_a_maquina,
    controladores: Mapping[int, str],
    nome: str | None = None,
) -> Gravacao:
    """A resposta dela vira desenho e amarra — numa gravação só, o hub e o que
    pende dele juntos.

    ``nome`` é o nome que ela deu à PRIMEIRA porta (a do aparelho), no mesmo
    gesto (A-08-UM-MAPEAR-SO-01): ``None`` não toca o nome que o lugar já
    tinha, texto grava, e texto vazio apaga.

    O NÚMERO de cada porta, nesta ordem:

    1. o que este LUGAR já tem (:func:`_numero_conhecido`) — a entrada que ela
       numerou na outra janela ganha a amarra, e não um número novo;
    2. o menor inteiro que ainda não é entrada de face nenhuma — a regra do
       gabinete (``LogicaDoMapa.acrescentar_entrada``).

    Um número é de UM lugar: outro lugar que dizia ser esta entrada perde a
    amarra (o nome dele fica), e outra entrada que apontava para este mesmo
    caminho fica vazia — um aparelho está em um lugar só. A amarra leva a
    TESTEMUNHA do caminho (``LugarDeclarado.caminho``) e desfaz o «Não
    alcanço»: o cabo provou que ela alcança.
    """
    if not _face_aceita(face, maquina):
        raise ValueError(f"{face!r} não é um lugar do gabinete que o produto conhece")
    validas = [
        (porta, nos)
        for porta, nos in portas
        if (partes := partes_do_lugar(porta.lugar)) is not None and partes[1]
    ]
    if not validas:
        lugar = portas[0][0].lugar if portas else ""
        return Gravacao(lugar, "", face, False, MOTIVO_SEM_LUGAR)

    mapa = maquina.mapa
    faces = [face_.model_dump(mode="json") for face_ in mapa.faces]
    usados = set(entradas_do_mapa(mapa))
    numeros: list[str] = []
    declaracao_das_portas: dict[str, Any] = {}
    declaracao_dos_lugares: dict[str, Any] = {}
    face_final = face
    for indice, (porta, nos) in enumerate(validas):
        numero = _numero_conhecido(maquina, porta.lugar, porta.caminho, controladores)
        if numero is None or numero in numeros:
            numero = _menor_livre(usados | set(numeros))
        numeros.append(numero)
        declarada = mapa.portas.get(numero)
        if declarada is not None and declarada.filha_de is not None:
            # A entrada que nasce de uma extensão desenha dentro do quadrado de
            # quem a hospeda e NÃO entra em fileira nenhuma (``FaceDeclarada``).
            if indice == 0:
                face_final = _face_da_entrada(mapa, numero) or face
        else:
            _por_na_face(faces, face, numero)

        declaracao_das_portas[numero] = {"caminho": porta.caminho}
        if nos:
            declaracao_das_portas[numero]["nos"] = list(nos)
        for outro, dela in mapa.portas.items():
            if outro not in numeros and dela.caminho == porta.caminho:
                declaracao_das_portas[outro] = {"caminho": None}

        declaracao_dos_lugares[porta.lugar] = {
            "entrada": numero,
            "caminho": porta.caminho,
            "fora": None,
        }
        if indice == 0 and nome is not None:
            declaracao_dos_lugares[porta.lugar]["nome"] = nome.strip() or None
        for outro, dele in maquina.lugares.items():
            if outro not in declaracao_dos_lugares and dele.entrada == numero:
                declaracao_dos_lugares[outro] = {"entrada": None}

    recibo = _gravar_no_mapa(
        gravar,
        {
            "mapa": {"faces": faces, "portas": declaracao_das_portas},
            "lugares": declaracao_dos_lugares,
        },
    )
    if not recibo.gravou:
        logger.warning("entrada_a_entrada_nao_gravou", motivo=recibo.motivo)
    return Gravacao(
        validas[0][0].lugar,
        numeros[0],
        face_final,
        recibo.gravou,
        recibo.motivo,
        tuple(numeros),
    )


def _face_aceita(face: str, maquina: MaquinaConfig) -> bool:
    """A face é uma das respostas do produto, uma que ela JÁ tem no mapa, ou
    a de um hub que ela declarou (:func:`faces_dos_hubs`)."""
    if face in FACES or face in LUGARES_DA_PORTA:
        return True
    if face in faces_dos_hubs(maquina.mapa).values():
        return True
    return any(existente.nome == face for existente in maquina.mapa.faces)


def _gravar_no_mapa(
    gravar: Callable[[Mapping[str, Any]], Recibo], declaracao: Mapping[str, Any]
) -> Recibo:
    """O ÚNICO ponto deste módulo que escreve no disco — A-08-UM-MAPEAR-SO-01.

    Toda gravação do mapa das portas passa por aqui: a porta que o controle
    mostrou, o nome e o lugar da revisita, o «Não alcanço» e o
    ``dar_nome_ao_adaptador``.
    A régua (``tests/unit/test_a_08_um_mapear_so.py``) conta as chamadas ao
    gravador no fonte, e um segundo escritor reprova. O gravador é o
    ``lugar_declarado.declarar_a_maquina`` (sem IPC, a mesma porta de antes),
    ou o dublê da régua.
    """
    return gravar(declaracao)


def _por_na_face(faces: list[dict[str, Any]], face: str, numero: str) -> None:
    """O número sai de toda outra face e entra no fim da fileira desta.

    A ORDEM DA FILEIRA É O DESENHO DELA: confirmar a mesma face de uma porta já
    mapeada não a manda para o fim (conferência, 23/09/2026). ``perto`` e
    ``alto`` nascem aqui, quando a face nasce — fato físico que só ela tem.
    """
    alvo = next((f for f in faces if f["nome"] == face), None)
    for existente in faces:
        if existente is not alvo:
            existente["portas"] = [n for n in existente["portas"] if n != numero]
    if alvo is None:
        alvo = {
            "nome": face,
            "portas": [],
            "perto": face == FACE_QUE_E_PERTO,
            "alto": face == FACE_QUE_E_ALTO,
        }
        faces.append(alvo)
    if numero not in alvo["portas"]:
        alvo["portas"].append(numero)


def _face_da_entrada(mapa: MapaDaMesa, numero: str) -> str | None:
    """A face em que este número está — a da entrada que hospeda, se extensão."""
    for face in mapa.faces:
        if numero in face.portas:
            return face.nome
    declarada = mapa.portas.get(numero)
    if declarada is not None and declarada.filha_de:
        for face in mapa.faces:
            if declarada.filha_de in face.portas:
                return face.nome
    return None


# ---------------------------------------------------------------------------
# O nome da porta — interligado com o resto (a palavra dela)
# ---------------------------------------------------------------------------


def nome_do_lugar(
    lugar: str,
    *,
    maquina: MaquinaConfig | None = None,
    controladores: Mapping[int, str] | None = None,
) -> str | None:
    """O nome desta porta: o que ela deu, ou «Entrada 3». ``None`` = não sei.

    É o que a seção nova põe no lugar do «Entrada 4.1.4» e o que o conselho de
    porta do vigia diz. O adaptador plugado nela NÃO herda este nome desde
    26/09/2026 (ver ``utils/maquina.AdaptadorDeclarado``).

    Sem amarra pelo lugar, vale o número que o desenho de hoje dá a um dos
    caminhos deste lugar NESTE boot (``utils/lugar.caminhos_do_lugar``). Dois
    números para o mesmo lugar é "não sei".
    """
    documento = maquina if maquina is not None else carregar_maquina()
    nome = _nome_declarado(documento, lugar)
    if nome:
        return nome
    numero = entrada_do_lugar(documento, lugar, controladores)
    if numero is None:
        barramentos = (
            controladores if controladores is not None else _controladores_do_sistema()
        )
        numero = _numero_conhecido(documento, lugar, "", barramentos)
    return None if numero is None else f"{PALAVRA_DA_ENTRADA} {numero}"


def nome_da_porta(
    chave: str,
    *,
    maquina: MaquinaConfig | None = None,
    controladores: Mapping[int, str] | None = None,
    so_o_declarado: bool = False,
) -> str | None:
    """O nome da porta por QUALQUER das duas chaves da casa.

    ``chave`` é o lugar (``pci-…-usb-0:4.1.4``, o do dono do BlueZ) ou o
    caminho de barramento (``3-4.1.4``, o que a ponte root e o ``mapa``
    escrevem). O caminho é traduzido pelo ``utils/lugar.lugar_do_caminho``
    com os barramentos DESTE boot; e, se o lugar não tem amarra, vale o número
    que o desenho de hoje dá a este caminho — o ``mapa`` não migrou.

    SEM NOME E SEM NÚMERO, A PORTA SE CHAMA COMO O DESENHO APROVADO MOSTRA —
    «Entrada 4.1.4», o ``devpath`` (TRANSPLANTE-DA-SECAO-01, item 4 de quem
    coordena). Com o mapa dela vazio, a frase da recusa caía para «Este
    adaptador já tem…» e a seção nova não tinha como dizer ONDE. ``None`` fica
    para o que não é porta: chave vazia, fora das duas formas, ou o lugar do
    adaptador embutido, que não pendura em entrada nenhuma. E a entrada do
    próprio computador, numa máquina com dois controladores USB, leva o
    barramento — «Entrada 1-4» e «Entrada 3-4», e não duas «Entrada 4»
    (:func:`_rotulo_de_reserva`, STORM-USB-02).

    ``so_o_declarado=True`` devolve ``None`` em vez do ``devpath``: é para quem
    tem um texto próprio e mais rico para a porta sem nome — a coluna «Onde
    está» da ``secao_mesa`` diz «Barramento 3, porta 1.2 · Direita».
    """
    if not chave:
        return None
    documento = maquina if maquina is not None else carregar_maquina()
    partes = partes_do_lugar(chave)
    if partes is not None:
        nome = nome_do_lugar(chave, maquina=documento, controladores=controladores)
        if nome or so_o_declarado:
            return nome
        return _rotulo_de_reserva(
            partes[0],
            partes[1],
            controladores if controladores is not None else _controladores_do_sistema(),
        )
    barramentos = (
        controladores if controladores is not None else _controladores_do_sistema()
    )
    lugar = lugar_do_caminho(chave, barramentos)
    if lugar:
        nome = nome_do_lugar(lugar, maquina=documento, controladores=barramentos)
        if nome:
            return nome
    numero = _entrada_do_caminho(documento, chave, lugar, barramentos)
    if numero is not None:
        return f"{PALAVRA_DA_ENTRADA} {numero}"
    if so_o_declarado or not FORMA_DO_CAMINHO.match(chave):
        return None
    busnum, _, devpath = chave.partition("-")
    return _rotulo_de_reserva(barramentos.get(int(busnum), ""), devpath, barramentos)


def rotulo_do_numero(numero: str) -> str | None:
    """«Entrada 3», ou «Entrada 4.1.4» para quem ela ainda não nomeou nem
    numerou — a palavra do dono diante do número (ou do ``devpath``).

    PÚBLICA PARA QUE NINGUÉM MAIS COMPONHA A PALAVRA: o gerador da aba 08 põe
    o número do desenho aprovado no cartão, e compor ali seria o segundo dono
    que a ``test_a_costura_da_onda_2`` recusa (TRANSPLANTE-DA-SECAO-01).
    """
    return f"{PALAVRA_DA_ENTRADA} {numero}" if numero else None


def _rotulo_de_reserva(
    controlador: str, devpath: str, controladores: Mapping[int, str]
) -> str | None:
    """O rótulo da porta sem nome e sem número — e o DESEMPATE — STORM-USB-02.

    O rótulo de reserva é o ``devpath``, como o desenho aprovado mostra
    («Entrada 4.1.4», TRANSPLANTE-DA-SECAO-01). Mas a entrada do PRÓPRIO
    computador — o ``devpath`` de um número só — se repete em todo controlador
    USB: cada hub-raiz numera as entradas dele a partir de 1. Na mesa dela, com
    dois controladores, o ``1-4`` (o adaptador do rádio) e o ``3-4`` (o hub)
    saíam os dois «Entrada 4», no doctor e na seção do rádio.

    O DONO DO NOME DESEMPATA: numa máquina com mais de um controlador, a entrada
    do computador leva o barramento na frente — «Entrada 1-4», «Entrada 3-4»,
    o caminho que o kernel dá (o do lado 2.0, onde o DualSense e os adaptadores
    enumeram: o ``4-4`` do lado 3.x é a mesma entrada que o ``3-4``). Atrás de
    um hub a cadeia já separa, e o rótulo continua o do desenho. Com UM
    controlador, ou sem saber de qual é, nada muda.
    """
    if not devpath:
        return None
    if "." not in devpath and len(set(controladores.values())) > 1:
        barramentos = sorted(n for n, dono in controladores.items() if dono == controlador)
        if barramentos:
            return rotulo_do_numero(f"{barramentos[0]}-{devpath}")
    return rotulo_do_numero(devpath)


def rotulo_da_entrada(
    lugar: str,
    *,
    maquina: MaquinaConfig | None = None,
    controladores: Mapping[int, str] | None = None,
) -> str | None:
    """«Entrada 3», ou «Entrada 4.1.4» — o rótulo da porta SEM o nome dela.

    É o que a seção do rádio põe ao lado do nome que ela deu (o campo editável
    mostra o nome; a marca da face mostra a entrada). ``None`` = não é porta:
    o lugar do adaptador embutido, que não pendura em entrada nenhuma. O
    rótulo de reserva desempata como o do :func:`nome_da_porta`.
    """
    partes = partes_do_lugar(lugar)
    if partes is None:
        return None
    documento = maquina if maquina is not None else carregar_maquina()
    barramentos = controladores if controladores is not None else _controladores_do_sistema()
    numero = _numero_conhecido(documento, lugar, "", barramentos)
    if numero is not None:
        return f"{PALAVRA_DA_ENTRADA} {numero}"
    return _rotulo_de_reserva(partes[0], partes[1], barramentos)


def face_do_lugar(
    lugar: str,
    *,
    maquina: MaquinaConfig | None = None,
    controladores: Mapping[int, str] | None = None,
) -> str | None:
    """A face do gabinete em que esta porta está («Atrás do gabinete»), ou ``None``.

    Sai do ``mapa`` dela, pelo número que o lugar tem: sem número, não se sabe
    a face — e a tela oferece o «Onde fica?».
    """
    if partes_do_lugar(lugar) is None:
        return None
    documento = maquina if maquina is not None else carregar_maquina()
    barramentos = controladores if controladores is not None else _controladores_do_sistema()
    numero = _numero_conhecido(documento, lugar, "", barramentos)
    if numero is None:
        return None
    return next((f.nome for f in documento.mapa.faces if numero in f.portas), None)


def com_o_nome_dela(
    linha: Mapping[str, Any],
    *,
    maquina: MaquinaConfig | None = None,
    controladores: Mapping[int, str] | None = None,
) -> dict[str, Any]:
    """Uma linha do diário do rádio com o nome que ela deu à porta.

    O conselho de porta do vigia sai de quem não tem como saber o nome dela —
    a ponte root escreve ``"porta": "3-4.1.4"`` e «O adaptador da porta
    3-4.1.4 travou de novo.»; o dono do BlueZ escreve o lugar. Quem LÊ o
    diário (o sino) passa a linha por aqui: ganha ``porta_nome``, e a frase
    troca o caminho do sistema pelo nome dela. Sem nome conhecido, a linha
    volta como veio.
    """
    saida = dict(linha)
    porta = str(linha.get("porta") or "")
    nome = nome_da_porta(porta, maquina=maquina, controladores=controladores)
    if not nome:
        return saida
    saida["porta_nome"] = nome
    frase = saida.get("frase")
    if isinstance(frase, str) and porta in frase:
        saida["frase"] = frase.replace(f"porta {porta}", nome).replace(porta, nome)
    return saida


# ---------------------------------------------------------------------------
# O nome que ela dá a um lugar
# ---------------------------------------------------------------------------


def dar_nome_ao_adaptador(
    endereco: str,
    nome: str,
    *,
    gravar: Callable[[Mapping[str, Any]], Recibo] = declarar_a_maquina,
) -> NomeDado:
    """Grava o nome do ADAPTADOR, pelo endereço dele. Nome vazio apaga o nome.

    O ``Alias`` do BlueZ é a projeção deste campo, escrita pelo
    ``bt_active_mode.sh`` no próximo tique do watchdog — o escritor é um só,
    como o nome da entrada, que o Mapear grava.
    """
    chave = chave_do_adaptador(endereco)
    if chave is None:
        raise ValueError(f"{endereco!r} não é endereço de adaptador")
    limpo = nome.strip() or None
    recibo = _gravar_no_mapa(gravar, {"adaptadores": {chave: {"nome": limpo}}})
    return NomeDado(chave, limpo, recibo.gravou, recibo.motivo)


# ---------------------------------------------------------------------------
# O que tem na entrada, e a velocidade dela (O-MAPA-DAS-CONEXOES-NO-PRODUTO-01)
# ---------------------------------------------------------------------------
#
# O editor do mapa das conexões, 26/09/2026. Pedido dela: *«ao clicar em um
# desses usb mapeados eu pudesse setar que tem tal coisa lá. no caso o hub ou
# afins»*; e a velocidade, porque o firmware da placa erra (ver
# ``mapa_das_portas.velocidade_da_entrada``). As duas vão ao ``maquina.json``
# dela, ao lado do caminho e dos nós da entrada, pelo gravador único deste
# módulo. <!-- noqa-acento: citação literal dela -->


def declarar_a_ligacao(
    numero: str,
    liga: str | None,
    *,
    maquina: MaquinaConfig | None = None,
    gravar: Callable[[Mapping[str, Any]], Recibo] = declarar_a_maquina,
) -> Recibo:
    """«Direto» (``None``), «Hub» ou «Extensor» na entrada ``numero``."""
    if liga is not None and liga not in LIGACOES_DECLARAVEIS:
        raise ValueError(f"{liga!r} não é o que se declara numa entrada")
    return _declarar_na_entrada(numero, {"liga": liga}, maquina=maquina, gravar=gravar)


def declarar_a_velocidade(
    numero: str,
    usb: int,
    *,
    maquina: MaquinaConfig | None = None,
    gravar: Callable[[Mapping[str, Any]], Recibo] = declarar_a_maquina,
) -> Recibo:
    """USB 2.0 (``2``) ou USB 3.0 (``3``) na entrada ``numero`` — vence o firmware."""
    if usb not in VELOCIDADES_DECLARAVEIS:
        raise ValueError(f"{usb!r} não é uma velocidade que se declara")
    return _declarar_na_entrada(numero, {"usb": usb}, maquina=maquina, gravar=gravar)


def _declarar_na_entrada(
    numero: str,
    campos: Mapping[str, Any],
    *,
    maquina: MaquinaConfig | None,
    gravar: Callable[[Mapping[str, Any]], Recibo],
) -> Recibo:
    """Os campos na ``mapa.portas[numero]``, se a entrada é do mapa dela — ou é
    a PONTA de um extensor que ela declarou numa entrada do mapa.

    A PONTA GRAVA desde a O-MAPA-DAS-CONEXOES-NO-PRODUTO-02 (26/09/2026): o que
    ela dizia ali sumia ao reler, sem aviso. Ela vai ao disco como a
    entrada-filha que o ``PortaDeclarada.filha_de`` sempre descreveu, e daí o
    motor a desenha sozinho (``mapa_das_portas.filhas_de``). Quando a entrada
    deixa de ser extensor, a ponta que só o editor escreveu sai junto: sem
    isso ela continuaria desenhada como filha de uma entrada «Direto».

    AS ENTRADAS DO HUB DESENHADO (``5.1``…) NÃO GRAVAM: o ponto não cabe no
    número de entrada que o ``utils/maquina`` aceita, e o exemplo da página não
    é o gabinete de ninguém. Declarar sobre eles gravaria uma entrada que ela
    nunca mapeou; o editor da página nem manda o gesto.
    """
    documento = maquina if maquina is not None else carregar_maquina()
    mapa = documento.mapa
    if numero in entradas_do_mapa(mapa):
        declaracao: dict[str, Any] = {numero: dict(campos)}
    elif (mae := _mae_da_ponta(mapa, numero)) is not None:
        declaracao = {numero: {"filha_de": mae, **campos}}
    else:
        raise ValueError(f"a entrada {numero!r} não está no mapa desta máquina")
    ponta = ponta_do_extensor(numero)
    dela = mapa.portas.get(ponta) if ponta else None
    if (
        ponta
        and "liga" in campos
        and campos["liga"] != "extensor"
        and dela is not None
        and dela.filha_de == numero
        and not dela.caminho
        and not dela.nos
    ):
        declaracao[ponta] = {"filha_de": None, "liga": None, "usb": None}
    recibo = _gravar_no_mapa(gravar, {"mapa": {"portas": declaracao}})
    if not recibo.gravou:
        logger.warning("entrada_declarada_nao_gravou", motivo=recibo.motivo)
    return recibo


def ponta_do_extensor(numero: str) -> str | None:
    """A entrada-filha que um extensor na entrada ``numero`` desenha, ou ``None``.

    ``None`` para a entrada que já é ponta ou é do hub desenhado: a ponta dela
    não é um número que o disco aceite (ver :data:`LETRA_DA_PONTA`).
    """
    return f"{numero}{LETRA_DA_PONTA}" if _SO_DIGITOS.match(numero) else None


def _mae_da_ponta(mapa: MapaDaMesa, numero: str) -> str | None:
    """A entrada do mapa com extensor declarado cuja ponta é ``numero``."""
    for mae in entradas_do_mapa(mapa):
        porta = mapa.portas.get(mae)
        if porta is not None and porta.liga == "extensor" and ponta_do_extensor(mae) == numero:
            return mae
    return None


def faces_dos_hubs(mapa: MapaDaMesa) -> dict[str, str]:
    """``número da entrada -> nome da face`` de cada hub declarado, na ordem do desenho."""
    return {
        numero: FACE_DO_HUB_DECLARADO.format(numero=numero)
        for numero in _numeros_do_mapa(mapa)
        if (porta := mapa.portas.get(numero)) is not None and porta.liga == "hub"
    }


def _usb_da_porta(
    medido: Any, declarada: int | None, censo: Censo | None
) -> tuple[str, str]:
    """``(USB 3.0 | USB 2.0 | "", de onde)`` de uma porta do Mapear.

    A precedência é de ``mapa_das_portas.velocidade_da_entrada``: o aparelho
    que enumerou a 5000M+ nela, depois o que ela declarou, depois a placa (o
    ``medido.usb``, lido dos hubs que hospedam os nós do buraco).
    """
    from hefesto_dualsense4unix.integrations import mapa_das_portas as junta

    placa = {junta.USB_3: True, junta.USB_2: False}.get(medido.usb)
    dentro = (
        next((a for a in censo.aparelhos if a.nome_do_kernel == medido.aparelho), None)
        if censo is not None and medido.aparelho
        else None
    )
    rapido, de_onde = junta.velocidade_da_entrada(
        placa,
        declarada,
        dentro is not None and dentro.velocidade_mbps >= VELOCIDADE_SUPERSPEED_MBPS,
    )
    if rapido is None:
        return "", de_onde
    return (junta.USB_3 if rapido else junta.USB_2), de_onde


# ---------------------------------------------------------------------------
# O MAPA DAS PORTAS — um fluxo, uma gravação, um nome (A-08-UM-MAPEAR-SO-01)
# ---------------------------------------------------------------------------
#
# Pedido dela, 25/09/2026: *«Dava pra ser um botão só né?»*. O «Mapear
# Entradas» (o rascunho da aba, que manda o ``mapa`` inteiro pelo IPC) e o
# «Mapear Entrada a Entrada» (o laço acima) viram UM fluxo: ela leva o MESMO
# DualSense de porta em porta; a porta que ele acabou de mostrar chega com o
# que se mediu dela; ela dá o nome e escolhe onde fica. A primeira vez e a
# revisita são o mesmo gesto — na revisita a porta já chega com o número, o
# nome e o lugar de antes, e gravar de novo só troca o que ela trocou.
#
# UMA GRAVAÇÃO: :func:`_gravar_no_mapa`, a mesma do laço. UM NOME PARA LER:
# :func:`ler_o_mapa`, que devolve cada porta com o declarado (número, nome,
# lugar no gabinete) e o medido agora (USB 2.0/3.0, controlador, hub, -71,
# Bluetooth da placa ou dongle). O medido NÃO vai ao disco: ver
# ``mapa_das_portas.fatos_do_buraco``.

#: As fases do fluxo único. ``PARADO`` é o mesmo do laço.
ESPERANDO = "esperando"
NA_PORTA = "porta"

#: A chave da última gravação na foto — a mesma do laço, ASCII por contrato.
_CHAVE_DA_ULTIMA = "ultima"  # (noqa-acento) chave de máquina

#: O ``/sys/class/bluetooth`` do sistema — desviável, como a raiz do USB.
RAIZ_BT_PADRAO = "/sys/class/bluetooth"


@dataclass(frozen=True)
class PortaDoMapa:
    """Uma porta do mapa: o que ela declarou e o que o ``/sys`` diz agora.

    ``chave`` é o que a tela devolve em :meth:`MapearAsPortas.gravar`: o
    número quando a porta já tem um, e o lugar (``pci-…-usb-0:4.1``) quando
    ainda não. ``rotulo`` é o nome que ela deu, ou «Entrada 3» — a palavra do
    dono (:func:`nome_da_porta`). ``lugar_no_gabinete`` é a face do mapa
    («Frente do gabinete»). Os campos medidos são os de
    ``mapa_das_portas.FatosDoBuraco``, e ``""``/``None`` neles é "não sei".
    """

    chave: str
    numero: str | None = None
    nome: str | None = None
    rotulo: str | None = None
    lugar_no_gabinete: str | None = None
    lugar: str = ""
    caminho: str = ""
    nos: tuple[str, ...] = ()
    fora: bool = False
    usb: str = ""
    #: De onde veio o ``usb`` — ``mapa_das_portas.USB_PELO_APARELHO``,
    #: ``USB_DECLARADA`` ou ``USB_PELA_PLACA``; ``""`` quando não se sabe.
    usb_de: str = ""
    controlador: str = ""
    hub: str = ""
    hub_produto: str = ""
    encaixe: str = ""
    ocupada: bool | None = None
    aparelho: str = ""
    especie: str = ""
    produto: str = ""
    e_dualsense: bool = False
    e_bluetooth: bool = False
    bluetooth: str = ""
    storm: int | None = None

    def como_dicionario(self) -> dict[str, Any]:
        from dataclasses import asdict

        saida = asdict(self)
        saida["nos"] = list(self.nos)
        return saida


@dataclass(frozen=True)
class MapaDasPortas:
    """O mapa inteiro, pelo nome único que todo leitor pede.

    ``bluetooth_sem_porta`` conta os adaptadores Bluetooth que não penduram em
    porta USB nenhuma — o rádio da placa por SDIO/UART/PCIe. O da placa que
    pendura num conector USB interno aparece como porta, com
    ``bluetooth="placa"``.
    """

    portas: tuple[PortaDoMapa, ...] = ()
    bluetooth_sem_porta: int = 0
    lugares: tuple[str, ...] = LUGARES_DA_PORTA

    def porta(self, chave: str) -> PortaDoMapa | None:
        """A porta pela chave, pelo número ou pelo lugar — ``None`` se nenhuma."""
        if not chave:
            return None
        return next(
            (p for p in self.portas if chave in (p.chave, p.numero, p.lugar)), None
        )

    def como_dicionario(self) -> dict[str, Any]:
        return {
            "portas": [p.como_dicionario() for p in self.portas],
            "bluetooth_sem_porta": self.bluetooth_sem_porta,
            "lugares": list(self.lugares),
        }


def ler_o_mapa(
    *,
    maquina: MaquinaConfig | None = None,
    censo: Censo | None = None,
    entradas: Sequence[NoDeEntrada] | None = None,
    raiz_usb: str | None = None,
    adaptadores: Sequence[Any] | None = None,
    raiz_bt: str = RAIZ_BT_PADRAO,
    storm: Mapping[str, int] | None = None,
    medir_storm: bool = True,
    incluir: Sequence[Sequence[str]] = (),
) -> MapaDasPortas:
    """O MAPA DAS PORTAS — o nome único que a tela, o Check-up, Rádio e
    Adaptadores e o exame pedem.

    Cada entrada numerada do ``mapa`` (na ordem das faces) e cada buraco
    OCUPADO agora que ainda não tem número, com o que o ``/sys`` diz dele.
    ``incluir`` são buracos (pelos nós) que entram mesmo vazios — a porta que
    o controle mostrou e de que ela já o tirou.

    Tudo o que lê entra por argumento, com o default do sistema: ``raiz_usb``
    desvia as duas leituras do barramento (a régua monta um ``/sys`` de
    mentira), ``adaptadores`` e ``raiz_bt`` o Bluetooth, e ``storm`` o -71
    (``{caminho do kernel: quantos}``). Sem ``storm``, e com a raiz do
    sistema, o -71 sai do log do kernel-watch (``exame_da_mesa``); com outra
    raiz o log não é daquela máquina, e o -71 fica ``None`` — não medido.
    """
    from hefesto_dualsense4unix.integrations import mapa_das_portas as junta

    documento = maquina if maquina is not None else carregar_maquina()
    if raiz_usb is None:
        lido = censo if censo is not None else _ler_o_barramento()
        lidas = tuple(entradas) if entradas is not None else _listar_as_entradas()
        do_sistema = True
    else:
        from hefesto_dualsense4unix.integrations.censo_do_barramento import (
            ler_o_barramento,
        )
        from hefesto_dualsense4unix.integrations.entradas_do_gabinete import (
            listar_entradas,
        )

        lido = censo if censo is not None else ler_o_barramento(raiz_usb=raiz_usb)
        lidas = (
            tuple(entradas) if entradas is not None else listar_entradas(raiz_usb=raiz_usb)
        )
        do_sistema = False
    if storm is None and medir_storm and do_sistema:
        storm = _storm_do_log()
    controladores = _controladores(lido)
    buracos = furos(lidas)

    def fatos(nos: Sequence[str]) -> Any:
        return junta.fatos_do_buraco(nos, lidas, lido, controladores, storm=storm)

    portas: list[PortaDoMapa] = []
    vistos: set[tuple[str, ...]] = set()
    for numero in _numeros_do_mapa(documento.mapa):
        furo = _furo_da_entrada(numero, documento, buracos, controladores)
        declarada = documento.mapa.portas.get(numero)
        amarrado = lugar_da_entrada(documento, numero, controladores)
        lugar = amarrado or (_lugar_do_furo(furo, controladores) if furo else "")
        nos = tuple(furo.nos) if furo else tuple(declarada.nos if declarada else ())
        medido = fatos(nos)
        if furo is not None:
            vistos.add(tuple(furo.nos))
        dele = documento.lugares.get(lugar) if lugar else None
        nome = dele.nome if dele is not None else None
        portas.append(
            _porta_do_mapa(
                numero,
                numero=numero,
                nome=nome,
                rotulo=nome or rotulo_do_numero(numero),
                face=_face_da_entrada(documento.mapa, numero),
                lugar=lugar,
                caminho=medido.aparelho or (declarada.caminho if declarada else "") or "",
                nos=nos,
                fora=bool(dele is not None and dele.fora),
                medido=medido,
                usb=_usb_da_porta(medido, declarada.usb if declarada else None, lido),
            )
        )

    extras = {tuple(nos) for nos in incluir if nos}
    for furo in buracos:
        chave_do_furo = tuple(furo.nos)
        if chave_do_furo in vistos:
            continue
        if not furo.aparelho and not (set(chave_do_furo) & {n for e in extras for n in e}):
            continue
        lugar = _lugar_do_furo(furo, controladores)
        if not lugar:
            continue
        vistos.add(chave_do_furo)
        medido = fatos(chave_do_furo)
        dele = documento.lugares.get(lugar)
        nome = dele.nome if dele is not None else None
        portas.append(
            _porta_do_mapa(
                lugar,
                numero=None,
                nome=nome,
                rotulo=nome
                or rotulo_da_entrada(lugar, maquina=documento, controladores=controladores),
                face=None,
                lugar=lugar,
                caminho=medido.aparelho,
                nos=chave_do_furo,
                fora=bool(dele is not None and dele.fora),
                medido=medido,
            )
        )

    # O QUE ELA JÁ IDENTIFICOU SEM NÚMERO também é do mapa: o nome que ela deu
    # à entrada (o de antes de 26/09/2026 também vinha de Rádio e Adaptadores)
    # e o «Não alcanço» moram no lugar,
    # e a revisita renomeia «as entradas já mapeadas ou identificadas» — com o
    # dongle fora da porta, ela continua sendo dela.
    listados = {p.lugar for p in portas if p.lugar}
    numerados = {p.numero for p in portas if p.numero}
    for lugar, dele in sorted(documento.lugares.items()):
        partes = partes_do_lugar(lugar)
        if (
            lugar in listados
            or not (dele.nome or dele.fora)
            or (dele.entrada is not None and dele.entrada in numerados)
            or partes is None
            or not partes[1]
        ):
            continue
        furo_do_lugar = next(
            (
                f
                for f in buracos
                if tuple(f.nos) not in vistos and _lugar_do_furo(f, controladores) == lugar
            ),
            None,
        )
        nos_do_lugar = tuple(furo_do_lugar.nos) if furo_do_lugar is not None else ()
        if nos_do_lugar:
            vistos.add(nos_do_lugar)
        medido = fatos(nos_do_lugar)
        portas.append(
            _porta_do_mapa(
                lugar,
                numero=None,
                nome=dele.nome,
                rotulo=dele.nome
                or rotulo_da_entrada(lugar, maquina=documento, controladores=controladores),
                face=None,
                lugar=lugar,
                caminho=medido.aparelho or dele.caminho or "",
                nos=nos_do_lugar,
                fora=bool(dele.fora),
                medido=medido,
            )
        )

    if adaptadores is None:
        adaptadores = _adaptadores_do_sistema(raiz_bt)
    sem_porta = sum(1 for a in adaptadores if not str(getattr(a, "no", "") or ""))
    # Os lugares que a tela oferece: os sete universais e, depois, as faces que
    # ela JÁ tem com outro nome — a escolha dela continua escolhível — e o hub
    # que ela declarou no mapa das conexões, que vira lugar para as entradas dele.
    dela = tuple(
        dict.fromkeys(
            [f.nome for f in documento.mapa.faces if f.nome not in LUGARES_DA_PORTA]
            + list(faces_dos_hubs(documento.mapa).values())
        )
    )
    return MapaDasPortas(
        portas=tuple(portas),
        bluetooth_sem_porta=sem_porta,
        lugares=LUGARES_DA_PORTA + dela,
    )


class MapearAsPortas:
    """O fluxo ÚNICO do mapa das portas — a primeira vez e a revisita.

    Sem GTK e sem IPC, como o laço: tudo o que lê entra por argumento, com o
    default do sistema, e a gravação é :func:`_gravar_no_mapa`.

    O GESTO DELA: ``abrir`` → ela encaixa o DualSense numa porta → o tique
    (``foto_sem_esperar``, que pede o ``olhar`` num fio próprio) acha a porta
    que ele acabou de mostrar e ela vira a PORTA DA VEZ, com o medido e o que
    já se sabe dela → ``gravar(nome=…, lugar=…)`` → ela leva o controle para
    a próxima. ``gravar(chave=…)`` é o mesmo gesto para uma porta da lista
    (renomear e reposicionar sem encaixar nada). ``comecar`` é o ``abrir`` com
    a primeira leitura na hora, para quem pode esperar o ``/sys``.

    SÓ O DUALSENSE MOSTRA UMA PORTA, pela mesma razão do laço: um dongle que
    re-enumera (o -71) não é «a porta que ela plugou». E a porta da vez é a
    que APARECEU: com dois controles já no cabo (a mesa de quatro), o que
    estava encaixado antes de ela começar não conta — só se for o único.

    O TIQUE NÃO ESPERA O ``/sys`` (O-MAPEAR-NAO-CONGELA-A-JANELA-01, queixa
    dela de 26/09: *«o mapear entradas toda hora tá fechando o app»*). Trocar
    o controle de entrada com a tela aberta fazia o kernel segurar o lock do
    aparelho enquanto enumerava, o censo esperava o lock no ``bMaxPower``, e a
    janela esperava o censo: 5, 10 e 15 s. Agora a leitura é de um fio próprio
    e a trava guarda só a troca de estado — um «Terminar» nunca espera o
    ``/sys``. <!-- noqa-acento: citação literal dela -->
    """

    def __init__(
        self,
        *,
        ler: Callable[[], Censo] | None = None,
        entradas: Callable[[], Sequence[NoDeEntrada]] | None = None,
        carregar: Callable[[], MaquinaConfig] | None = None,
        gravar: Callable[[Mapping[str, Any]], Recibo] | None = None,
        storm: Mapping[str, int] | None = None,
        adaptadores: Callable[[], Sequence[Any]] | None = None,
        fio: Callable[[Callable[[], None], str], None] | None = None,
    ) -> None:
        self._ler = ler or _ler_o_barramento
        self._entradas = entradas or _listar_as_entradas
        self._carregar = carregar or carregar_maquina
        self._gravar = gravar or declarar_a_maquina
        self._storm_dado = storm
        self._adaptadores = adaptadores or (lambda: _adaptadores_do_sistema(RAIZ_BT_PADRAO))
        self._trava = threading.Lock()
        self._fase = PARADO
        self._antes: frozenset[tuple[str, ...]] = frozenset()
        self._da_vez: tuple[str, ...] = ()
        self._storm: Mapping[str, int] | None = None
        #: O log do -71 já foi lido nesta sessão? É dele, e não da primeira
        #: leitura do barramento: o Salvar que chegar antes da primeira foto
        #: gasta a primeira sem ler o log, e o -71 sumiria da sessão inteira.
        self._storm_lido = False
        self._ultima: Gravacao | None = None
        self._feitas = 0
        #: A sessão do fluxo: cada abrir e cada parar a trocam, e a leitura que
        #: voltar de outra sessão não anda nada.
        self._sessao = 0
        #: A próxima leitura é a PRIMEIRA da sessão: é ela que diz o que já
        #: estava encaixado quando ela abriu a tela.
        self._primeira = False
        #: A última foto que um fio tirou nesta sessão — ``None`` enquanto a
        #: primeira não voltou.
        self._pintada: dict[str, Any] | None = None
        self._voo = _VooDaLeitura(self.olhar, nome="mapear-as-portas", fio=fio)

    # -- os gestos -----------------------------------------------------------

    def abrir(self) -> None:
        """Abre o fluxo SEM ler nada — o gesto da tela. A primeira leitura
        (o log do -71 e o barramento) sai no fio do tique, e até ela voltar a
        foto diz ``procurando``."""
        with self._trava:
            self._fase = ESPERANDO
            self._da_vez = ()
            self._antes = frozenset()
            self._ultima = None
            self._feitas = 0
            self._storm = None
            self._storm_lido = False
            self._primeira = True
            self._sessao += 1
            self._pintada = None

    def comecar(self) -> dict[str, Any]:
        """Abre o fluxo e lê na hora. Se UM DualSense já está numa porta, ela é
        a da vez. Quem chama espera o ``/sys``; a tela usa :meth:`abrir`."""
        self.abrir()
        return self.olhar()

    def olhar(self) -> dict[str, Any]:
        """Um tique: a porta em que o DualSense acabou de aparecer vira a da vez.

        Parado, não lê nada. A leitura que não respondeu não anda o fluxo —
        "não sei" não é "o controle saiu". A leitura é FORA da trava, e a que
        voltar de outra sessão (ela fechou ou reabriu no meio) não anda nada.
        """
        with self._trava:
            if self._fase == PARADO:
                return self._foto_parada()
            sessao, ler_o_log = self._sessao, not self._storm_lido
        storm = self._ler_o_storm() if ler_o_log else None
        censo, lidas, adaptadores = self._ler_o_sys()
        with self._trava:
            if self._sessao != sessao or self._fase == PARADO:
                return self._foto_de_agora()
            if ler_o_log and not self._storm_lido:
                self._storm, self._storm_lido = storm, True
            self._andar(censo, lidas)
            self._pintada = self._foto(censo, lidas, adaptadores)
            return self._pintada

    def gravar(
        self,
        *,
        chave: str | None = None,
        nome: str | None = None,
        lugar: str | None = None,
    ) -> Gravacao:
        """Grava o nome e o lugar no gabinete da porta — numa gravação só.

        ``chave`` ``None`` é a porta da vez; senão, a ``chave`` (ou o número,
        ou o lugar) de uma porta de :func:`ler_o_mapa`. ``nome`` ``None`` não
        mexe no nome, ``""`` apaga; ``lugar`` ``None`` mantém o lugar que a
        porta já tinha. Só o nome, numa porta sem lugar no gabinete, grava só
        o nome: o número e a face nascem quando ela disser onde fica.

        A PORTA DA VEZ É A DA LEITURA DESTE GESTO, e não a da última foto: com
        o ``/sys`` lento (o kernel enumerando o controle que ela acabou de
        mudar de porta), a tela pode ainda mostrar a porta de antes quando ela
        salva. O gesto lê de novo e anda o fluxo antes de escolher — o nome vai
        para onde o DualSense está. E o «Terminar» que chegar durante essa
        leitura não apaga o Salvar que ela clicou antes: vale a porta da vez do
        clique, e nada se perde.

        Levanta ``ValueError`` quando o gesto chega errado (nada a gravar, um
        lugar que o produto não conhece) e
        ``RuntimeError`` quando não há porta (nenhuma da vez, chave que não
        existe): o tratador da aba devolve os dois como recusa.
        """
        if nome is None and lugar is None:
            raise ValueError("nada a gravar: nem nome nem lugar")
        with self._trava:
            sessao, da_vez = self._sessao, self._da_vez
        censo, lidas, adaptadores = self._ler_o_sys()
        with self._trava:
            maquina = self._carregar()
            if lugar is not None and not _face_aceita(lugar, maquina):
                raise ValueError(f"{lugar!r} não é um lugar do gabinete que o produto conhece")
            aberto = self._sessao == sessao and self._fase != PARADO
            if chave is None and aberto:
                self._andar(censo, lidas)
            if aberto:
                da_vez = self._da_vez
            mapa = ler_o_mapa(
                maquina=maquina,
                censo=censo,
                entradas=lidas,
                adaptadores=(),
                storm={},
                incluir=(da_vez,) if da_vez else (),
            )
            if chave is None:
                if not da_vez:
                    raise RuntimeError("não há porta da vez: encaixe o controle numa porta")
                porta = next((p for p in mapa.portas if set(p.nos) & set(da_vez)), None)
            else:
                porta = mapa.porta(chave)
            if porta is None:
                raise RuntimeError("não achei essa porta no mapa")
            face = lugar if lugar is not None else porta.lugar_no_gabinete
            gravacao = _gravar_a_porta(
                porta,
                face,
                nome,
                maquina=maquina,
                lidas=lidas,
                gravar=self._gravar,
                controladores=_controladores(censo),
                da_vez=chave is None,
            )
            self._ultima = gravacao
            if gravacao.gravou:
                self._feitas += 1
            if aberto:
                # O que ela acabou de salvar aparece no tique seguinte, e não
                # só quando a próxima leitura do fio voltar.
                self._pintada = self._foto(censo, lidas, adaptadores)
            return gravacao

    def parar(self) -> None:
        """Fecha. Nada se perde: cada porta já foi ao disco quando ela gravou.

        Nunca espera o ``/sys``: a leitura em voo é de outra sessão quando
        voltar, e não anda nada."""
        with self._trava:
            self._fase = PARADO
            self._da_vez = ()
            self._antes = frozenset()
            self._primeira = False
            self._sessao += 1
            self._pintada = None

    def estado(self) -> dict[str, Any]:
        """O que a tela pintaria, relendo o mapa agora (o fluxo aberto é de
        propósito) — sem andar o fluxo. Quem chama espera o ``/sys``; o tique
        usa :meth:`foto_sem_esperar`."""
        with self._trava:
            if self._fase == PARADO:
                return self._foto_parada()
            sessao = self._sessao
        censo, lidas, adaptadores = self._ler_o_sys()
        with self._trava:
            if self._sessao != sessao or self._fase == PARADO:
                return self._foto_de_agora()
            return self._foto(censo, lidas, adaptadores)

    def foto_sem_esperar(self) -> dict[str, Any]:
        """O que o TIQUE pinta — não lê o ``/sys`` e não toma a trava.

        Com o fluxo aberto, a próxima leitura sai num fio próprio
        (:class:`_VooDaLeitura`, uma de cada vez), e a foto é a última que um
        fio tirou. Ela vem com ``procurando`` enquanto a primeira da sessão
        não voltou, e quando a leitura no ar passa do fôlego
        (:data:`FOLEGO_DA_LEITURA_S`) — aí sem a porta da vez, que pode ser a
        de antes.
        """
        if self._fase == PARADO:
            return self._foto_parada()
        self._voo.disparar()
        return self._foto_de_agora()

    # -- interno -------------------------------------------------------------

    def _andar(self, censo: Censo, lidas: Sequence[NoDeEntrada]) -> None:
        """Um passo do fluxo com uma leitura nova. Chamada sob a trava."""
        if _nao_sei(censo) or not lidas:
            return
        agora = _buracos_com_dualsense(censo, lidas)
        if self._primeira:
            self._primeira = False
            if len(agora) == 1:
                self._da_vez = agora[0]
                self._fase = NA_PORTA
        else:
            novos = [nos for nos in agora if nos not in self._antes]
            if novos:
                self._da_vez = novos[0]
                self._fase = NA_PORTA
        self._antes = frozenset(agora)

    def _foto_de_agora(self) -> dict[str, Any]:
        """A foto sem leitura nenhuma: a parada, a última, ou a que procura."""
        if self._fase == PARADO:
            return self._foto_parada()
        foto = self._pintada
        if foto is not None and not self._voo.demorando():
            return foto
        base = foto if foto is not None else {
            "estado": self._fase,
            "portas": None,
            "lugares": list(LUGARES_DA_PORTA),
            "bluetooth_sem_porta": 0,
            "feitas": self._feitas,
            _CHAVE_DA_ULTIMA: self._ultima_gravada(),
        }
        return {**base, "porta": None, "procurando": True}

    def _ler_o_storm(self) -> Mapping[str, int] | None:
        return self._storm_dado if self._storm_dado is not None else _storm_do_log()

    def _ler_o_sys(self) -> tuple[Censo, tuple[NoDeEntrada, ...], tuple[Any, ...]]:
        """O barramento, os nós de entrada e os adaptadores — sempre FORA da trava."""
        censo, lidas = self._ler_o_censo(), self._ler_as_entradas()
        try:
            adaptadores = tuple(self._adaptadores())
        except Exception:  # defensivo — o /sys/class/bluetooth some sob a mão
            adaptadores = ()
        return censo, lidas, adaptadores

    def _ler_o_censo(self) -> Censo:
        try:
            return self._ler()
        except Exception:  # defensivo — a leitura some sob a mão
            logger.debug("mapa_das_portas_leitura_falhou", exc_info=True)
            return Censo()

    def _ler_as_entradas(self) -> tuple[NoDeEntrada, ...]:
        try:
            return tuple(self._entradas())
        except Exception:  # defensivo — o sysfs some sob a mão
            logger.debug("mapa_das_portas_nos_falharam", exc_info=True)
            return ()

    def _ultima_gravada(self) -> dict[str, Any] | None:
        return None if self._ultima is None else self._ultima.como_dicionario()

    def _foto_parada(self) -> dict[str, Any]:
        return {
            "estado": PARADO,
            "porta": None,
            "portas": [],
            "lugares": list(LUGARES_DA_PORTA),
            "bluetooth_sem_porta": 0,
            "feitas": self._feitas,
            _CHAVE_DA_ULTIMA: self._ultima_gravada(),
        }

    def _foto(
        self, censo: Censo, lidas: Sequence[NoDeEntrada], adaptadores: Sequence[Any]
    ) -> dict[str, Any]:
        """A foto da leitura que já está na mão. Chamada sob a trava: o
        ``maquina.json`` é lido aqui, depois de qualquer gravação."""
        mapa = ler_o_mapa(
            maquina=self._carregar(),
            censo=censo,
            entradas=lidas,
            adaptadores=adaptadores,
            storm=self._storm,
            medir_storm=False,
            incluir=(self._da_vez,) if self._da_vez else (),
        )
        da_vez = (
            next((p for p in mapa.portas if set(p.nos) & set(self._da_vez)), None)
            if self._da_vez
            else None
        )
        return {
            "estado": self._fase,
            "porta": None if da_vez is None else da_vez.como_dicionario(),
            "portas": [p.como_dicionario() for p in mapa.portas],
            "lugares": list(mapa.lugares),
            "bluetooth_sem_porta": mapa.bluetooth_sem_porta,
            "feitas": self._feitas,
            _CHAVE_DA_ULTIMA: self._ultima_gravada(),
        }


def _gravar_a_porta(
    porta: PortaDoMapa,
    face: str | None,
    nome: str | None,
    *,
    maquina: MaquinaConfig,
    lidas: Sequence[NoDeEntrada],
    gravar: Callable[[Mapping[str, Any]], Recibo],
    controladores: Mapping[int, str],
    da_vez: bool = False,
) -> Gravacao:
    """A gravação da porta do fluxo único — pelo mesmo compositor do laço.

    Sem lugar no gabinete (``face`` ``None``), só o nome vai ao disco. A porta
    SEM número, com o buraco lido (os nós dela estão no ``/sys`` de agora), e
    a porta da vez (o DualSense acabou de prová-la) passam pelo
    :func:`_gravar_as_portas` de sempre: o número que o lugar já tem (ou o
    menor livre), a face, os nós, a amarra e o nome, juntos. A porta numerada
    tocada PELA LISTA é revisita pura: a face e o nome, e nada do que a
    primeira vez gravou sai — nem a testemunha do caminho, que o aparelho que
    estiver nela agora (um pendrive no lado 3.x) trocaria.
    """
    if face is None:
        # SÓ O NOME, numa porta que ainda não tem lugar no gabinete (a porta
        # da vez sem o «onde fica», ou a que perdeu a face): o nome vai para o
        # lugar, e o produto não inventa face nem número por ela.
        if nome is None:
            raise ValueError("nada a gravar: nem nome nem lugar")
        if not porta.lugar:
            return Gravacao("", porta.numero or "", "", False, MOTIVO_SEM_LUGAR)
        recibo = _gravar_no_mapa(
            gravar, {"lugares": {porta.lugar: {"nome": nome.strip() or None}}}
        )
        if not recibo.gravou:
            logger.warning("mapa_das_portas_nao_gravou", motivo=recibo.motivo)
        return Gravacao(
            porta.lugar,
            porta.numero or "",
            "",
            recibo.gravou,
            recibo.motivo,
            (porta.numero,) if porta.numero else (),
        )
    lidos = {e.no for e in lidas}
    no_sys = bool(porta.lugar and porta.nos and set(porta.nos) & lidos)
    if no_sys and (porta.numero is None or da_vez):
        # A testemunha é o caminho do lado 2.0, o mesmo de que sai o lugar
        # (:func:`_lugar_do_furo`) e onde o DualSense enumera — nunca o de um
        # aparelho que só existe no lado 3.x.
        caminho = _caminho_do_lado_20(porta.nos) or porta.aparelho
        if not caminho:
            return Gravacao(porta.lugar, "", face, False, MOTIVO_SEM_LUGAR)
        vista = PortaVista(lugar=porta.lugar, caminho=caminho)
        return _gravar_as_portas(
            [(vista, porta.nos)],
            face,
            maquina=maquina,
            gravar=gravar,
            controladores=controladores,
            nome=nome,
        )
    if porta.numero is None:
        return Gravacao(porta.lugar, "", face, False, MOTIVO_SEM_LUGAR)
    declaracao: dict[str, Any] = {}
    face_final = face
    declarada = maquina.mapa.portas.get(porta.numero)
    if declarada is None or declarada.filha_de is None:
        faces = [f.model_dump(mode="json") for f in maquina.mapa.faces]
        _por_na_face(faces, face, porta.numero)
        declaracao["mapa"] = {"faces": faces}
    else:
        face_final = _face_da_entrada(maquina.mapa, porta.numero) or face
    if nome is not None:
        if not porta.lugar:
            return Gravacao("", porta.numero, face_final, False, MOTIVO_SEM_LUGAR)
        declaracao["lugares"] = {porta.lugar: {"nome": nome.strip() or None}}
    if not declaracao:
        return Gravacao(porta.lugar, porta.numero, face_final, True, "", (porta.numero,))
    recibo = _gravar_no_mapa(gravar, declaracao)
    if not recibo.gravou:
        logger.warning("mapa_das_portas_nao_gravou", motivo=recibo.motivo)
    return Gravacao(
        porta.lugar, porta.numero, face_final, recibo.gravou, recibo.motivo, (porta.numero,)
    )


def _porta_do_mapa(
    chave: str,
    *,
    numero: str | None,
    nome: str | None,
    rotulo: str | None,
    face: str | None,
    lugar: str,
    caminho: str,
    nos: tuple[str, ...],
    fora: bool,
    medido: Any,
    usb: tuple[str, str] | None = None,
) -> PortaDoMapa:
    """``usb`` é ``(velocidade, de onde)`` quando a porta tem declaração — ver
    :func:`_usb_da_porta`; sem ele vale o que o ``/sys`` mediu."""
    velocidade, de_onde = usb if usb is not None else _usb_da_porta(medido, None, None)
    return PortaDoMapa(
        chave=chave,
        numero=numero,
        nome=nome,
        rotulo=rotulo,
        lugar_no_gabinete=face,
        lugar=lugar,
        caminho=caminho,
        nos=nos,
        fora=fora,
        usb=velocidade,
        usb_de=de_onde,
        controlador=medido.controlador,
        hub=medido.hub,
        hub_produto=medido.hub_produto,
        encaixe=medido.encaixe,
        ocupada=medido.ocupada,
        aparelho=medido.aparelho,
        especie=medido.especie,
        produto=medido.produto,
        e_dualsense=medido.e_dualsense,
        e_bluetooth=medido.e_bluetooth,
        bluetooth=medido.bluetooth,
        storm=medido.storm,
    )


def _numeros_do_mapa(mapa: MapaDaMesa) -> tuple[str, ...]:
    """Os números do desenho: os das faces, na ordem dela, e depois o resto."""
    achados: list[str] = []
    for face in mapa.faces:
        for numero in face.portas:
            if numero not in achados:
                achados.append(numero)
                achados.extend(
                    filha
                    for filha, porta in sorted(mapa.portas.items())
                    if porta.filha_de == numero and filha not in achados
                )
    achados.extend(numero for numero in sorted(mapa.portas) if numero not in achados)
    return tuple(achados)


def _furo_da_entrada(
    numero: str,
    maquina: MaquinaConfig,
    buracos: Sequence[Furo],
    controladores: Mapping[int, str],
) -> Furo | None:
    """O buraco de agora que é esta entrada — pela amarra, pelos nós, pelo caminho.

    A mesma escada de :func:`_o_furo_e_conhecido`, do outro lado: a amarra
    pelo lugar sobrevive ao boot; os nós e o caminho carregam o número do
    barramento e valem só para a entrada que ainda não tem amarra.
    """
    lugar = lugar_da_entrada(maquina, numero, controladores)
    if lugar:
        achado = next((f for f in buracos if _lugar_do_furo(f, controladores) == lugar), None)
        if achado is not None:
            return achado
    declarada = maquina.mapa.portas.get(numero)
    if declarada is None:
        return None
    if declarada.nos and not lugar:
        achado = next((f for f in buracos if set(f.nos) & set(declarada.nos)), None)
        if achado is not None:
            return achado
    if declarada.caminho and not lugar:
        return next(
            (
                f
                for f in buracos
                if f.aparelho == declarada.caminho
                or declarada.caminho in {caminho_do_no(no) for no in f.nos}
            ),
            None,
        )
    return None


def _buracos_com_dualsense(
    censo: Censo, lidas: Sequence[NoDeEntrada]
) -> list[tuple[str, ...]]:
    """Os buracos (pelos nós) em que há um DualSense agora, na ordem do ``/sys``."""
    return [
        tuple(furo.nos)
        for furo in furos(lidas)
        if _o_dualsense_no_furo(furo, censo) is not None
    ]


def _caminho_do_lado_20(nos: Sequence[str]) -> str:
    """O caminho que um aparelho 2.0 teria neste buraco — o lado de barramento menor."""
    caminhos = sorted(
        (caminho_do_no(no) for no in nos if caminho_do_no(no)),
        key=lambda caminho: int(caminho.partition("-")[0]),
    )
    return caminhos[0] if caminhos else ""


def _storm_do_log() -> dict[str, int] | None:
    """``{caminho do kernel: quantos -71}`` dos últimos 7 dias — ``None`` sem log.

    O dono da leitura é o ``exame_da_mesa.storm_por_porta``; aqui só se conta.
    Sem o log do kernel-watch não há medição, e ``None`` não é zero.
    """
    try:
        from hefesto_dualsense4unix.integrations import exame_da_mesa

        log = exame_da_mesa.log_do_kernel_watch()
        if log is None:
            return None
        laudo = exame_da_mesa.storm_por_porta(log=log, nomear=exame_da_mesa._sem_nome)
    except Exception:  # defensivo — o -71 nunca derruba o mapa
        logger.debug("mapa_das_portas_storm_falhou", exc_info=True)
        return None
    if laudo.porque_nao:
        return None
    return {porta.porta: porta.quantos for porta in laudo.portas}


def _adaptadores_do_sistema(raiz_bt: str) -> tuple[Any, ...]:
    try:
        from hefesto_dualsense4unix.integrations.mesa_de_radio import (
            adaptadores_bluetooth,
        )

        return tuple(adaptadores_bluetooth(raiz_bt=raiz_bt))
    except Exception:  # defensivo — sem Bluetooth é resposta, não defeito
        return ()


# ---------------------------------------------------------------------------
# O dono do laço no processo da janela
# ---------------------------------------------------------------------------

_O_LACO: LacoDaEntrada | None = None
_TRAVA_DO_LACO = threading.Lock()


def o_laco() -> LacoDaEntrada:
    """O laço do processo — um só, como o rascunho do mapa da aba 08."""
    global _O_LACO
    with _TRAVA_DO_LACO:
        if _O_LACO is None:
            _O_LACO = LacoDaEntrada()
        return _O_LACO


_O_MAPA: MapearAsPortas | None = None


def o_mapa() -> MapearAsPortas:
    """O fluxo único do processo — um só, como o laço (A-08-UM-MAPEAR-SO-01)."""
    global _O_MAPA
    with _TRAVA_DO_LACO:
        if _O_MAPA is None:
            _O_MAPA = MapearAsPortas()
        return _O_MAPA


# ---------------------------------------------------------------------------
# Interno
# ---------------------------------------------------------------------------


def _controladores(censo: Censo) -> dict[int, str]:
    """``{busnum: controlador PCI}`` pelos hubs-raiz do censo que já está na mão.

    A mesma resposta de ``mesa_de_radio.controladores_dos_barramentos``, sem
    uma segunda leitura do ``/sys`` no mesmo tique.
    """
    return {
        aparelho.busnum: aparelho.controlador_pci
        for aparelho in censo.aparelhos
        if aparelho.e_raiz and aparelho.controlador_pci
    }


def _nao_sei(censo: Censo) -> bool:
    """A leitura do barramento não respondeu? Sem hub-raiz nenhum, é "não sei".

    Toda máquina com USB tem hub-raiz, e ``ler_o_barramento`` devolve
    ``Censo()`` vazio quando o ``/sys`` não se deixa ler. Ler isso como "nenhum
    aparelho" é responder "não sei" com zero.
    """
    return not any(aparelho.e_raiz for aparelho in censo.aparelhos)


def _nome_declarado(maquina: MaquinaConfig, lugar: str) -> str | None:
    declarado = maquina.lugares.get(lugar)
    return None if declarado is None else declarado.nome


def _entrada_do_caminho(
    maquina: MaquinaConfig,
    caminho: str,
    lugar: str,
    controladores: Mapping[int, str] | None = None,
) -> str | None:
    """O número que o desenho dá a este caminho — se ele não é de outro lugar.

    É a ponte com o ``mapa`` que não migrou: a entrada que ela numerou na outra
    janela vale para esta porta, a menos que já esteja amarrada a outro lugar
    — aí o caminho gravado é de outro boot, e reaproveitar o número juntaria
    dois buracos.
    """
    if not caminho:
        return None
    for numero, porta in sorted(maquina.mapa.portas.items()):
        if porta.caminho != caminho:
            continue
        dono = lugar_da_entrada(maquina, numero, controladores)
        if dono == lugar or (
            dono is None and not _outro_pode_ser_o_dono(maquina, numero, caminho, lugar)
        ):
            return numero
    return None


def _outro_pode_ser_o_dono(
    maquina: MaquinaConfig, numero: str, caminho: str, lugar: str
) -> bool:
    """Outro lugar diz ser este número, e nada prova que não é?

    A amarra SEM testemunha que a tradução deste boot não confirma não vale
    (``utils/maquina.entrada_do_lugar``), mas também não se desmente quando o
    ``devpath`` bate: o caminho pode ser dela noutro boot, com os barramentos
    na outra ordem. Aí o número é "não sei" para os dois — dar a este lugar
    juntaria dois buracos. Com o ``devpath`` diferente, a amarra velha é de
    outro buraco com certeza, e não segura nada.
    """
    devpath = caminho.partition("-")[2]
    for outro, dele in maquina.lugares.items():
        if outro == lugar or dele.entrada != numero or dele.caminho is not None:
            continue
        partes = partes_do_lugar(outro)
        if partes is not None and partes[1] == devpath:
            return True
    return False


def _menor_livre(usados: set[str]) -> str:
    """O menor inteiro que ainda não é entrada do desenho."""
    ocupados = {int(n) for n in usados if n.isdigit()}
    proximo = 1
    while proximo in ocupados:
        proximo += 1
    return str(proximo)


def _ler_o_barramento() -> Censo:
    from hefesto_dualsense4unix.integrations.censo_do_barramento import (
        ler_o_barramento,
    )

    return ler_o_barramento()


def _listar_as_entradas() -> tuple[NoDeEntrada, ...]:
    from hefesto_dualsense4unix.integrations.entradas_do_gabinete import (
        listar_entradas,
    )

    return listar_entradas()


def _controladores_do_sistema() -> dict[int, str]:
    from hefesto_dualsense4unix.integrations.mesa_de_radio import (
        controladores_dos_barramentos,
    )

    return controladores_dos_barramentos()


__all__ = [
    "EM_PE",
    "ESPERANDO",
    "FACES",
    "FACE_ATRAS",
    "FACE_DO_HUB_DECLARADO",
    "FACE_EM_PE",
    "FACE_ESCRIVANINHA",
    "FACE_FRENTE",
    "FACE_HUB",
    "FACE_QUE_E_ALTO",
    "FACE_QUE_E_PERTO",
    "FIM",
    "FOLEGO_DA_LEITURA_S",
    "LETRA_DA_PONTA",
    "LIGACOES_DECLARAVEIS",
    "LUGARES_DA_PORTA",
    "LUGAR_FRENTE",
    "LUGAR_HUB",
    "LUGAR_LATERAL",
    "LUGAR_MONITOR",
    "LUGAR_OUTRO",
    "LUGAR_TOPO",
    "LUGAR_TRASEIRA",
    "NA_PORTA",
    "PALAVRA_DA_ENTRADA",
    "PARADO",
    "SENTADA",
    "TELAS",
    "VELOCIDADES_DECLARAVEIS",
    "Gravacao",
    "LacoDaEntrada",
    "MapaDasPortas",
    "MapearAsPortas",
    "NomeDado",
    "Pergunta",
    "PortaDoMapa",
    "PortaVista",
    "com_o_nome_dela",
    "dar_nome_ao_adaptador",
    "declarar_a_ligacao",
    "declarar_a_velocidade",
    "face_do_lugar",
    "faces_dos_hubs",
    "ler_o_mapa",
    "nome_da_porta",
    "nome_do_lugar",
    "o_laco",
    "o_mapa",
    "ponta_do_extensor",
    "rotulo_da_entrada",
    "rotulo_do_numero",
]
