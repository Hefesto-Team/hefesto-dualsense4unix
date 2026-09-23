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
* **Não inventa quinta resposta.** As quatro são as do produto; a «Traseira»
  do ``mapa-do-radio.html`` é a mesma pergunta em outra língua.
"""

from __future__ import annotations

import threading
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from hefesto_dualsense4unix.integrations.censo_do_barramento import (
    Aparelho,
    Censo,
    cadeia_de_hubs,
)
from hefesto_dualsense4unix.integrations.entradas_do_gabinete import (
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
    """O que :func:`dar_nome` fez: o nome do lugar no disco."""

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

    UMA TRAVA, porque o tique do piloto lê o barramento num fio próprio (desde
    15/09 a janela não segura o laço do GTK) e o gesto dela chega pelo laço do
    GTK: sem a trava, um ``responder`` no meio de um ``olhar`` gravaria a
    pergunta que acabou de mudar.
    """

    def __init__(
        self,
        *,
        ler: Callable[[], Censo] | None = None,
        entradas: Callable[[], Sequence[NoDeEntrada]] | None = None,
        carregar: Callable[[], MaquinaConfig] | None = None,
        gravar: Callable[[Mapping[str, Any]], Recibo] | None = None,
    ) -> None:
        self._ler = ler or _ler_o_barramento
        self._entradas = entradas or _listar_as_entradas
        self._carregar = carregar or carregar_maquina
        self._gravar = gravar or declarar_a_maquina
        self._trava = threading.Lock()
        self._zerar(PARADO)

    def _zerar(self, fase: str) -> None:
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
        """
        with self._trava:
            self._zerar(SENTADA)
            self._primeiro = lugar or None
            self._andar_sentada(self._ler_o_censo())
            return self._foto()

    def olhar(self) -> dict[str, Any]:
        """Um tique: relê o que a fase precisa e anda o laço. Parado e no fim,
        não lê nada.

        A leitura que não respondeu é "não sei", e "não sei" não anda o laço:
        ``Censo()`` sem hub-raiz nenhum (o ``OSError`` de
        ``ler_o_barramento``) ou nenhum nó de entrada lido diriam "nenhuma
        pergunta" e "nenhuma vaga", e a fase pularia para o fim por um tique
        que não viu nada.
        """
        with self._trava:
            if self._fase == SENTADA:
                censo = self._ler_o_censo()
                if not _nao_sei(censo):
                    self._andar_sentada(censo)
            elif self._fase == EM_PE:
                censo, lidas = self._ler_o_censo(), self._ler_as_entradas()
                if not _nao_sei(censo) and lidas:
                    self._andar_em_pe(censo, lidas)
            return self._foto()

    def responder(self, face: str) -> Gravacao:
        """A resposta dela para a pergunta da vez — grava na hora, e vale para o
        que pende do hub.

        Levanta ``ValueError`` para uma face fora das quatro e ``RuntimeError``
        sem pergunta: são os dois jeitos de o gesto chegar errado, e o tratador
        da aba os devolve como recusa (a piscada), nunca como recado. O disco
        que recusa deixa a pergunta onde está.
        """
        if face not in FACES:
            raise ValueError(f"{face!r} não é uma das quatro respostas")
        with self._trava:
            if self._fase != SENTADA or not self._perguntas:
                raise RuntimeError("não há pergunta para responder")
            pergunta = self._perguntas[0]
            censo = self._ler_o_censo()
            if _nao_sei(censo):
                # A leitura não respondeu: "não sei" não é "o aparelho saiu", e
                # a pergunta da vez fica onde está.
                raise RuntimeError("o barramento não respondeu")
            presentes = {aparelho.nome_do_kernel for aparelho in censo.conectados()}
            if pergunta.porta.caminho not in presentes:
                # O aparelho saiu entre o tique e o toque: gravar agora poria a
                # resposta dela num buraco vazio. A pergunta da vez anda.
                self._andar_sentada(censo)
                raise RuntimeError("o aparelho da pergunta saiu do barramento")
            lidas = self._ler_as_entradas()
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
            self._ultima = gravacao
            if gravacao.gravou:
                self._feitas += len(gravacao.entradas)
                self._andadas += 1
                self._ja_perguntados.update(pergunta.lugares())
                self._perguntas = self._perguntas[1:]
                if not self._perguntas:
                    self._fase = FIM
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
            return self._foto()

    def levantar(self) -> dict[str, Any]:
        """«Vou mostrar agora»: guarda a leitura de agora como referência e
        entra na fase em pé. É a única porta para ela — só do fim."""
        with self._trava:
            if self._fase != FIM:
                raise RuntimeError("a fase em pé só começa no fim da fase sentada")
            self._fase = EM_PE
            self._referencia = set()
            self._andar_em_pe(self._ler_o_censo(), self._ler_as_entradas())
            return self._foto()

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
                recibo = self._gravar({"lugares": {vaga.lugar: {"fora": True}}})
                self._ultima = Gravacao(vaga.lugar, "", "", recibo.gravou, recibo.motivo)
                if not recibo.gravou:
                    logger.warning("entrada_a_entrada_fora_nao_gravou", motivo=recibo.motivo)
            else:
                # Sem lugar não há o que gravar: sai da conta desta sessão.
                self._ultima = Gravacao("", "", "", False, MOTIVO_SEM_LUGAR)
            self._fora_hoje.update(vaga.furo.nos)
            self._tirar_a_vaga_da_vez()
            return self._foto()

    def parar(self) -> None:
        """«Já chega por hoje»: fecha, e nada se perde — cada resposta já foi."""
        with self._trava:
            self._zerar(PARADO)

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
) -> Gravacao:
    """A resposta dela vira desenho e amarra — numa gravação só, o hub e o que
    pende dele juntos.

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
    if face not in FACES:
        raise ValueError(f"{face!r} não é uma das quatro respostas")
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
        for outro, dele in maquina.lugares.items():
            if outro not in declaracao_dos_lugares and dele.entrada == numero:
                declaracao_dos_lugares[outro] = {"entrada": None}

    recibo = gravar(
        {
            "mapa": {"faces": faces, "portas": declaracao_das_portas},
            "lugares": declaracao_dos_lugares,
        }
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

    É o que a seção nova põe no lugar do «Entrada 4.1.4», o que o conselho de
    porta do vigia diz, e o nome que o adaptador plugado nesta porta herda.

    Sem amarra pelo lugar, vale o número que o desenho de hoje dá a um dos
    caminhos deste lugar NESTE boot (``utils/lugar.caminhos_do_lugar``): a
    entrada que ela numerou na outra janela também dá nome ao adaptador que
    está nela. Dois números para o mesmo lugar é "não sei".
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
    adaptador embutido, que não pendura em entrada nenhuma.

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
        return rotulo_do_numero(partes[1])
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
    return rotulo_do_numero(chave.partition("-")[2])


def rotulo_do_numero(numero: str) -> str | None:
    """«Entrada 3», ou «Entrada 4.1.4» para quem ela ainda não nomeou nem
    numerou — a palavra do dono diante do número (ou do ``devpath``).

    PÚBLICA PARA QUE NINGUÉM MAIS COMPONHA A PALAVRA: o gerador da aba 08 põe
    o número do desenho aprovado no cartão, e compor ali seria o segundo dono
    que a ``test_a_costura_da_onda_2`` recusa (TRANSPLANTE-DA-SECAO-01).
    """
    return f"{PALAVRA_DA_ENTRADA} {numero}" if numero else None


def rotulo_da_entrada(
    lugar: str,
    *,
    maquina: MaquinaConfig | None = None,
    controladores: Mapping[int, str] | None = None,
) -> str | None:
    """«Entrada 3», ou «Entrada 4.1.4» — o rótulo da porta SEM o nome dela.

    É o que a seção do rádio põe ao lado do nome que ela deu (o campo editável
    mostra o nome; a marca da face mostra a entrada). ``None`` = não é porta:
    o lugar do adaptador embutido, que não pendura em entrada nenhuma.
    """
    partes = partes_do_lugar(lugar)
    if partes is None:
        return None
    documento = maquina if maquina is not None else carregar_maquina()
    barramentos = controladores if controladores is not None else _controladores_do_sistema()
    numero = _numero_conhecido(documento, lugar, "", barramentos)
    if numero is not None:
        return f"{PALAVRA_DA_ENTRADA} {numero}"
    return rotulo_do_numero(partes[1])


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


def nome_do_adaptador(
    adaptador: Any,
    *,
    maquina: MaquinaConfig | None = None,
    controladores: Mapping[int, str] | None = None,
) -> str | None:
    """D3: o adaptador herda o nome da porta em que está.

    Serve ao ``bluez_dbus.AdaptadorDoBluez`` e ao ``mesa_de_radio.Adaptador``
    — os dois têm ``lugar``. Pelo lugar e nunca pelo ``hciN``: o índice
    inverte entre boots, e o nome iria junto para o outro dongle.
    """
    lugar = str(getattr(adaptador, "lugar", "") or "")
    if not lugar:
        return None
    return nome_do_lugar(lugar, maquina=maquina, controladores=controladores)


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


def dar_nome(
    lugar: str,
    nome: str,
    *,
    gravar: Callable[[Mapping[str, Any]], Recibo] = declarar_a_maquina,
) -> NomeDado:
    """Grava o nome do lugar no ``maquina.json``. Nome vazio apaga o nome.

    O nome é NOSSO e mora no ``maquina.json`` (D3). O ``Alias`` do BlueZ é a
    projeção dele, e tem UM escritor: o ``bt_active_mode.sh`` lê este campo e
    escreve o ``Alias`` do adaptador que estiver neste lugar, no próximo tique
    do watchdog (ENTRADA-A-ENTRADA-02). O motor não escreve no BlueZ: dois
    escritores do mesmo ``Alias`` é a duplicidade que o commit ``e5376a0``
    desfez em 22/08 (``D-COSTURA-BLUEZ``).
    """
    if partes_do_lugar(lugar) is None:
        raise ValueError(f"{lugar!r} não é um lugar")
    limpo = nome.strip() or None
    recibo = gravar({"lugares": {lugar: {"nome": limpo}}})
    return NomeDado(lugar, limpo, recibo.gravou, recibo.motivo)


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
    "FACES",
    "FACE_ATRAS",
    "FACE_EM_PE",
    "FACE_ESCRIVANINHA",
    "FACE_FRENTE",
    "FACE_HUB",
    "FACE_QUE_E_ALTO",
    "FACE_QUE_E_PERTO",
    "FIM",
    "PALAVRA_DA_ENTRADA",
    "PARADO",
    "SENTADA",
    "TELAS",
    "Gravacao",
    "LacoDaEntrada",
    "NomeDado",
    "Pergunta",
    "PortaVista",
    "com_o_nome_dela",
    "dar_nome",
    "face_do_lugar",
    "nome_da_porta",
    "nome_do_adaptador",
    "nome_do_lugar",
    "o_laco",
    "rotulo_da_entrada",
    "rotulo_do_numero",
]
