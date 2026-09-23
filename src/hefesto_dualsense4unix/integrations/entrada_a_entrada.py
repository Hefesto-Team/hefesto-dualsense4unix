"""entrada_a_entrada.py — o motor do «Mapear Entrada a Entrada».

ENTRADA-A-ENTRADA-01 (23/09/2026), a R9 das doze decisões dela do rádio:
*ligar de verdade*. A palavra dela é a especificação:

    "A ideia é usarmos um dualsense e o USB pra sairmos de porta em porta
     mapeando conectando e removendo e falando qual entrada é qual ali. (…) E
     isso tem que ser interligado com o resto das features nossas."
                                                  — citação literal dela

Até aqui a cerimônia da aba 08 era eco: três telas por âncora, zero gesto,
zero campo, e um «Gravado na hora» que não gravava nada. Este módulo é o motor
por trás delas. A fiação na página é da TRANSPLANTE-DA-SECAO-01.

O LAÇO
------

1. ela pluga o DualSense pelo cabo numa porta;
2. o motor vê o aparelho novo no barramento e resolve o LUGAR da porta
   (``utils/maquina.lugar_de``: o controlador PCI mais a cadeia de portas, a
   grafia do ``ID_PATH`` do udev e a chave do dono do BlueZ — D3);
3. ela diz qual é, com as QUATRO respostas de hoje (:data:`FACES`);
4. o motor grava, na hora;
5. ela tira o cabo, e o motor volta a esperar a próxima porta.

**O LUGAR, E NUNCA O ``hciN`` NEM A ORDEM DE CHEGADA.** Os dois mudam entre
boots. O número do barramento também — ele é a ordem em que os dois xHCI
sobem —, e por isso a chave gravada é o lugar, e não o ``3-4.1.4``.

"VÊ NO UDEV" É LER A ÁRVORE QUE O UDEV LÊ
------------------------------------------

O projeto não tem ``pyudev``, e o ``uevent`` do kernel chega antes de o udev
terminar as regras. O motor relê ``/sys/bus/usb/devices`` (pelo
``censo_do_barramento``, o dono dessa leitura) a cada tique, e SÓ enquanto a
cerimônia está aberta: a regra de «nunca em tique» é da aba montada, não da
janela que ela abriu de propósito (``entradas_do_gabinete.listar_entradas``).
O aparelho aparece em ~3,4 s (medido em 25/08, ``calibrar_entradas``); o tique
acrescenta no máximo o intervalo dele.

ONDE GRAVA — UM DONO, E ELE JÁ EXISTIA
---------------------------------------

O ``maquina.json``. O ``mapa`` dele já é o desenho do gabinete: a face e o
número moram lá, e é lá que os seis leitores da interface e o
``mapa-das-portas.html`` os leem. O motor grava:

* ``mapa.faces`` — o número na face que ela respondeu;
* ``mapa.portas[número]`` — o caminho de barramento e os nós do buraco, a
  chave que os leitores de hoje entendem (o ``mapa`` não migra nesta leva);
* ``lugares[lugar].entrada`` — a amarra pelo LUGAR, que é o que sobrevive a um
  boot que troque a ordem dos barramentos.

Pelo ``lugar_declarado.declarar_a_maquina``, sem IPC: a cerimônia grava com o
Hefesto desligado, que é o contrato que a janela de ontem já cumpria.

O QUE ELE NÃO FAZ
-----------------

* **Não escreve frase de tela.** A única palavra dele é o nome da porta —
  «Entrada 3», a palavra do produto (``D-A-PALAVRA-ENTRADA``) —, e o nome que
  ela der vence sempre.
* **Não fala com o daemon, nem com o rádio.** O único gesto que alcança o
  BlueZ é :func:`projetar_o_nome`, e ele passa pelo dono do D-Bus
  (``apelido_do_dongle`` → ``bluez_dbus``), dentro da trava comum.
* **Não inventa quinta resposta.** As quatro são as da janela de hoje; uma
  quinta abriria uma segunda língua para a mesma pergunta.
"""

from __future__ import annotations

import threading
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, replace
from typing import Any

from hefesto_dualsense4unix.integrations.censo_do_barramento import (
    Aparelho,
    Censo,
)
from hefesto_dualsense4unix.integrations.lugar_declarado import (
    Recibo,
    declarar_a_maquina,
)
from hefesto_dualsense4unix.utils.logging_config import get_logger
from hefesto_dualsense4unix.utils.maquina import (
    MapaDaMesa,
    MaquinaConfig,
    caminhos_do_lugar,
    carregar_maquina,
    entrada_do_lugar,
    entradas_do_mapa,
    lugar_da_entrada,
    lugar_de,
    lugar_do_caminho,
    partes_do_lugar,
)

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# As palavras e os estados
# ---------------------------------------------------------------------------

#: As QUATRO respostas de «Onde fica esta entrada?» — as mesmas da janela de
#: hoje (``app/widgets/calibrar_entradas.FACES``, aprovadas por ela em 25/08 e
#: com a quarta trocada por ela em 05/09). Aquele módulo é a janela GTK que o
#: gerador da aba 08 lê por AST, e ele não pode importar daqui sem quebrar o
#: gerador; por isso a lista mora nos dois, e
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

#: A palavra do produto para o buraco no gabinete (``D-A-PALAVRA-ENTRADA``).
#: É o nome da porta quando ela não deu outro: «Entrada 3».
PALAVRA_DA_ENTRADA = "Entrada"

#: Os estados do laço — chaves de máquina, para o piloto da aba 08.
PARADO = "parado"
ESPERANDO = "esperando"
VISTA = "vista"
GRAVADA = "gravada"

#: Os motivos de uma gravação que não aconteceu, além dos do
#: ``lugar_declarado`` (``versao_estranha``, ``schema_recusou``, ``disco``).
MOTIVO_SEM_LUGAR = "sem_lugar"

#: A Sony. Quando dois aparelhos chegam juntos em lugares diferentes, o
#: DualSense é o escolhido: é ele que ela tem na mão (a palavra dela), e é o
#: que avisa na mão dela.
_VID_DA_SONY = "054c"


# ---------------------------------------------------------------------------
# O que a tela recebe
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PortaVista:
    """A porta em que o cabo acabou de entrar — e o que já se sabe dela.

    ``lugar`` é a chave (D3). ``caminho`` é o nome do kernel DESTE boot, e
    existe para a tela mostrar e para o ``mapa`` de hoje entender — nunca para
    chavear. ``entrada``, ``face`` e ``nome`` vêm preenchidos quando ela já
    mapeou esta porta antes: plugar de novo numa porta conhecida mostra o que
    ela respondeu da outra vez.
    """

    lugar: str
    caminho: str
    vid: str = ""
    pid: str = ""
    especie: str = ""
    produto: str = ""
    e_dualsense: bool = False
    e_bluetooth: bool = False
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
            "entrada": self.entrada,
            "face": self.face,
            "nome": self.nome,
        }


@dataclass(frozen=True)
class Gravacao:
    """O que a resposta dela fez no disco. ``motivo`` é ``""`` quando gravou."""

    lugar: str
    entrada: str
    face: str
    gravou: bool
    motivo: str = ""


@dataclass(frozen=True)
class NomeDado:
    """O que :func:`dar_nome` fez: o nome no disco e a projeção no BlueZ.

    ``projetado`` é ``None`` quando não havia adaptador naquela porta (não há o
    que projetar), ``True`` quando o dono do D-Bus gravou o ``Alias``, e
    ``False`` quando tentou e o BlueZ ou a trava recusaram — ou quando o BlueZ
    não respondeu, e então não se sabe se havia adaptador ali.
    """

    lugar: str
    nome: str | None
    gravou: bool
    motivo: str = ""
    projetado: bool | None = None


# ---------------------------------------------------------------------------
# O laço
# ---------------------------------------------------------------------------


class LacoDaEntrada:
    """O «Mapear Entrada a Entrada», de porta em porta. Sem GTK e sem IPC.

    Todas as leituras entram por argumento — o barramento (``ler``), os nós do
    buraco (``nos_do_furo``), o ``maquina.json`` (``carregar``) e a gravação
    (``gravar``). O default de cada um é o do sistema; a régua troca todos, e
    nenhum caminho de ``/sys`` dela é tocado.

    UMA TRAVA, porque o tique do piloto lê o barramento num fio próprio (desde
    15/09 a janela não segura o laço do GTK) e o gesto dela chega pelo laço do
    GTK: sem a trava, um ``responder`` no meio de um ``olhar`` gravaria a porta
    que acabou de sair.
    """

    def __init__(
        self,
        *,
        ler: Callable[[], Censo] | None = None,
        nos_do_furo: Callable[[str], Sequence[str]] | None = None,
        carregar: Callable[[], MaquinaConfig] | None = None,
        gravar: Callable[[Mapping[str, Any]], Recibo] | None = None,
        projetar: Callable[[str, str], Any] | None = None,
    ) -> None:
        self._ler = ler or _ler_o_barramento
        self._nos_do_furo = nos_do_furo or _nos_do_furo_no_sistema
        self._carregar = carregar or carregar_maquina
        self._gravar = gravar or declarar_a_maquina
        self._projetar = projetar or projetar_o_nome
        self._trava = threading.Lock()
        self._estado = PARADO
        #: Os aparelhos presentes que NÃO contam como chegada: os que já
        #: estavam quando o laço começou, e os que já viraram porta vista.
        #: Quem sai do barramento sai daqui — plugar de novo é chegar de novo.
        self._vistos: set[str] = set()
        self._porta: PortaVista | None = None
        self._ultima: Gravacao | None = None
        self._feitas = 0

    # -- os gestos -----------------------------------------------------------

    def comecar(self) -> dict[str, Any]:
        """Abre a cerimônia: o que está plugado agora não é chegada."""
        with self._trava:
            self._vistos = set(self._presentes())
            self._estado = ESPERANDO
            self._porta = None
            self._ultima = None
            self._feitas = 0
            return self._foto()

    def olhar(self) -> dict[str, Any]:
        """Um tique: relê o barramento e anda o laço. Parado, não lê nada."""
        with self._trava:
            if self._estado == PARADO:
                return self._foto()
            presentes = self._presentes()
            self._vistos &= set(presentes)
            porta = self._porta
            if self._estado == VISTA:
                if porta is not None and porta.caminho not in presentes:
                    # Ela tirou o cabo sem responder: nada se grava.
                    self._estado = ESPERANDO
                    self._porta = None
                return self._foto()
            if self._estado == GRAVADA and porta is not None and porta.caminho not in presentes:
                self._estado = ESPERANDO
                self._porta = None
            novos = [a for nome, a in presentes.items() if nome not in self._vistos]
            chegou = _o_que_chegou(novos)
            if chegou is not None:
                self._vistos.update(a.nome_do_kernel for a in novos)
                self._porta = _porta_vista(chegou, self._carregar())
                self._estado = VISTA
            return self._foto()

    def responder(self, face: str) -> Gravacao:
        """A resposta dela para a porta vista — grava na hora.

        Levanta ``ValueError`` para uma face fora das quatro e ``RuntimeError``
        sem porta vista: são os dois jeitos de o gesto chegar errado, e o
        tratador da aba os devolve como recusa (a piscada), nunca como recado.
        """
        nome = None
        with self._trava:
            porta = self._porta
            if self._estado != VISTA or porta is None:
                raise RuntimeError("não há porta vista para responder")
            maquina = self._carregar()
            gravacao = _gravar_a_porta(
                porta,
                face,
                maquina=maquina,
                nos=tuple(self._nos_do_furo(porta.caminho)),
                gravar=self._gravar,
            )
            self._ultima = gravacao
            if gravacao.gravou:
                self._feitas += 1
                self._estado = GRAVADA
                self._porta = replace(porta, entrada=gravacao.entrada, face=gravacao.face)
                if porta.e_bluetooth:
                    nome = _nome_declarado(maquina, porta.lugar)
        if nome:
            # D3: o adaptador plugado numa porta com nome herda o nome. FORA da
            # trava do laço: a projeção espera a trava comum do rádio (até
            # 30 s com o watchdog segurando), e o tique não pode esperar junto.
            self._projetar(porta.lugar, nome)
        return gravacao

    def pular(self) -> dict[str, Any]:
        """«Não sei onde fica»: não grava, e não pergunta de novo pela mesma.

        A porta fica entre os vistos até o cabo sair, então o próximo tique não
        a devolve como chegada.
        """
        with self._trava:
            if self._estado == VISTA:
                self._estado = ESPERANDO
                self._porta = None
            return self._foto()

    def parar(self) -> None:
        """«Já chega por hoje»: fecha, e nada se perde — cada resposta já foi."""
        with self._trava:
            self._estado = PARADO
            self._vistos = set()
            self._porta = None

    def estado(self) -> dict[str, Any]:
        """O que o piloto da aba 08 pinta. Não lê nada."""
        with self._trava:
            return self._foto()

    # -- interno -------------------------------------------------------------

    def _presentes(self) -> dict[str, Aparelho]:
        try:
            censo = self._ler()
        except Exception:  # defensivo — a leitura some sob a mão
            logger.debug("entrada_a_entrada_leitura_falhou", exc_info=True)
            return {}
        return _presentes_com_lugar(censo)

    def _foto(self) -> dict[str, Any]:
        return {
            "estado": self._estado,
            "feitas": self._feitas,
            "porta": None if self._porta is None else self._porta.como_dicionario(),
            "gravou": None if self._ultima is None else self._ultima.gravou,
        }


# ---------------------------------------------------------------------------
# As peças do laço — privadas: quem está de fora fala com o laço
# ---------------------------------------------------------------------------


def _presentes_com_lugar(censo: Censo) -> dict[str, Aparelho]:
    """``{caminho: aparelho}`` do que está plugado e TEM lugar.

    Hub-raiz não é aparelho (``Censo.conectados``); aparelho sem controlador
    PCI legível não tem lugar, e sem lugar não há o que gravar.
    """
    return {
        a.nome_do_kernel: a
        for a in censo.conectados()
        if a.nome_do_kernel and a.devpath and a.controlador_pci
    }


def _o_que_chegou(novos: Sequence[Aparelho]) -> Aparelho | None:
    """Qual dos aparelhos novos é a PORTA — ``None`` quando não dá para dizer.

    * o que pendura em outro aparelho novo não é a porta: é o que veio junto
      com um hub (o hub é que está no buraco);
    * os dois lados de um hub USB 3 chegam juntos, em dois barramentos, e têm
      o MESMO lugar — fica o do lado 2.0, onde o DualSense enumera;
    * dois lugares diferentes ao mesmo tempo: o DualSense, se for um só. Senão,
      "não sei", e o laço espera um deles sair — chutar gravaria o nome dela
      na porta errada.
    """
    topo = [
        a
        for a in novos
        if not any(b is not a and _pendura_em(a, b) for b in novos)
    ]
    if not topo:
        return None
    lugares = {lugar_de(a.controlador_pci, a.devpath) for a in topo}
    if len(lugares) == 1:
        return min(topo, key=lambda a: (a.velocidade_mbps, a.busnum))
    sony = [a for a in topo if a.vid.lower() == _VID_DA_SONY]
    if len({lugar_de(a.controlador_pci, a.devpath) for a in sony}) == 1:
        return min(sony, key=lambda a: (a.velocidade_mbps, a.busnum))
    return None


def _porta_vista(aparelho: Aparelho, maquina: MaquinaConfig) -> PortaVista:
    """O aparelho que chegou, com o que ela já disse sobre aquele lugar.

    O número vem da amarra pelo lugar e, sem ela, do desenho de hoje pelo
    caminho DESTE boot — a mesma ordem de :func:`_gravar_a_porta`, para a tela
    mostrar o número que a resposta vai gravar.
    """
    lugar = lugar_de(aparelho.controlador_pci, aparelho.devpath)
    entrada = entrada_do_lugar(maquina, lugar) or _entrada_do_caminho(
        maquina, aparelho.nome_do_kernel, lugar
    )
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
        entrada=entrada,
        face=None if entrada is None else _face_da_entrada(maquina.mapa, entrada),
        nome=_nome_declarado(maquina, lugar),
    )


def _gravar_a_porta(
    porta: PortaVista,
    face: str,
    *,
    maquina: MaquinaConfig,
    nos: Sequence[str] = (),
    gravar: Callable[[Mapping[str, Any]], Recibo] = declarar_a_maquina,
) -> Gravacao:
    """A resposta dela vira desenho e amarra — numa gravação só.

    O NÚMERO, nesta ordem:

    1. o que este LUGAR já tem (``lugares``), se a amarra ainda vale;
    2. o que o desenho de hoje já deu a este caminho — a entrada que ela
       numerou na outra janela ganha a amarra, e não um número novo;
    3. o menor inteiro que ainda não é entrada de face nenhuma — a regra do
       gabinete (``LogicaDoMapa.acrescentar_entrada``).

    Um número é de UM lugar: outro lugar que dizia ser esta entrada perde a
    amarra (o nome dele fica), e outra entrada que apontava para este mesmo
    caminho fica vazia — um aparelho está em um lugar só.
    """
    if face not in FACES:
        raise ValueError(f"{face!r} não é uma das quatro respostas")
    partes = partes_do_lugar(porta.lugar)
    if partes is None or not partes[1]:
        return Gravacao(porta.lugar, "", face, False, MOTIVO_SEM_LUGAR)

    mapa = maquina.mapa
    numero = (
        entrada_do_lugar(maquina, porta.lugar)
        or _entrada_do_caminho(maquina, porta.caminho, porta.lugar)
        or _numero_novo(mapa)
    )
    declarada = mapa.portas.get(numero)
    e_extensao = declarada is not None and declarada.filha_de is not None

    faces = [face_.model_dump(mode="json") for face_ in mapa.faces]
    if not e_extensao:
        # A entrada que nasce de uma extensão desenha dentro do quadrado de
        # quem a hospeda e NÃO entra em fileira nenhuma (``FaceDeclarada``).
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
        # A ORDEM DA FILEIRA É O DESENHO DELA: confirmar a mesma face de uma
        # porta já mapeada não a manda para o fim (conferência, 23/09/2026).
        if numero not in alvo["portas"]:
            alvo["portas"].append(numero)

    portas: dict[str, Any] = {numero: {"caminho": porta.caminho}}
    if nos:
        portas[numero]["nos"] = list(nos)
    for outro, dela in mapa.portas.items():
        if outro != numero and dela.caminho == porta.caminho:
            portas[outro] = {"caminho": None}

    lugares: dict[str, Any] = {porta.lugar: {"entrada": numero}}
    for outro, dele in maquina.lugares.items():
        if outro != porta.lugar and dele.entrada == numero:
            lugares[outro] = {"entrada": None}

    recibo = gravar({"mapa": {"faces": faces, "portas": portas}, "lugares": lugares})
    face_final = _face_da_entrada(mapa, numero) if e_extensao else face
    if not recibo.gravou:
        logger.warning("entrada_a_entrada_nao_gravou", motivo=recibo.motivo)
    return Gravacao(porta.lugar, numero, face_final or face, recibo.gravou, recibo.motivo)


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
    caminhos deste lugar NESTE boot (``utils/maquina.caminhos_do_lugar``): a
    entrada que ela numerou na outra janela também dá nome ao adaptador que
    está nela. Dois números para o mesmo lugar é "não sei".
    """
    documento = maquina if maquina is not None else carregar_maquina()
    nome = _nome_declarado(documento, lugar)
    if nome:
        return nome
    numero = entrada_do_lugar(documento, lugar)
    if numero is None:
        barramentos = (
            controladores if controladores is not None else _controladores_do_sistema()
        )
        achados = {
            achado
            for caminho in caminhos_do_lugar(lugar, barramentos)
            if (achado := _entrada_do_caminho(documento, caminho, lugar)) is not None
        }
        numero = achados.pop() if len(achados) == 1 else None
    return None if numero is None else f"{PALAVRA_DA_ENTRADA} {numero}"


def nome_da_porta(
    chave: str,
    *,
    maquina: MaquinaConfig | None = None,
    controladores: Mapping[int, str] | None = None,
) -> str | None:
    """O nome da porta por QUALQUER das duas chaves da casa.

    ``chave`` é o lugar (``pci-…-usb-0:4.1.4``, o do dono do BlueZ) ou o
    caminho de barramento (``3-4.1.4``, o que a ponte root e o ``mapa``
    escrevem). O caminho é traduzido pelo ``utils/maquina.lugar_do_caminho``
    com os barramentos DESTE boot; e, se o lugar não tem amarra, vale o número
    que o desenho de hoje dá a este caminho — o ``mapa`` não migrou.
    """
    if not chave:
        return None
    documento = maquina if maquina is not None else carregar_maquina()
    if partes_do_lugar(chave) is not None:
        return nome_do_lugar(chave, maquina=documento, controladores=controladores)
    barramentos = (
        controladores if controladores is not None else _controladores_do_sistema()
    )
    lugar = lugar_do_caminho(chave, barramentos)
    if lugar:
        nome = nome_do_lugar(lugar, maquina=documento, controladores=barramentos)
        if nome:
            return nome
    numero = _entrada_do_caminho(documento, chave, lugar)
    return None if numero is None else f"{PALAVRA_DA_ENTRADA} {numero}"


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
# O nome que ela dá a um lugar, e a projeção no BlueZ
# ---------------------------------------------------------------------------


def dar_nome(
    lugar: str,
    nome: str,
    *,
    gravar: Callable[[Mapping[str, Any]], Recibo] = declarar_a_maquina,
    projetar: Callable[[str, str], Any] | None = None,
) -> NomeDado:
    """Grava o nome do lugar e o projeta no adaptador que estiver nele.

    O nome é NOSSO e mora no ``maquina.json`` (D3); o ``Alias`` do BlueZ é a
    projeção, escrita pelo dono do D-Bus. Nome vazio apaga o nome do lugar e
    NÃO mexe no ``Alias``: tirar uma palavra do BlueZ que ela escreveu um dia
    é pior que deixar uma a mais (``apelido_do_dongle.limpar_o_nome``).
    """
    if partes_do_lugar(lugar) is None:
        raise ValueError(f"{lugar!r} não é um lugar")
    limpo = nome.strip() or None
    recibo = gravar({"lugares": {lugar: {"nome": limpo}}})
    if not recibo.gravou or limpo is None:
        return NomeDado(lugar, limpo, recibo.gravou, recibo.motivo)
    renomeacao = (projetar or projetar_o_nome)(lugar, limpo)
    projetado = None if renomeacao is None else bool(getattr(renomeacao, "aplicado", False))
    return NomeDado(lugar, limpo, True, projetado=projetado)


def projetar_o_nome(
    lugar: str,
    nome: str,
    *,
    adaptadores: Callable[[], Iterable[Any] | None] | None = None,
    renomear: Callable[[str, str], Any] | None = None,
) -> Any:
    """O ``Alias`` do adaptador que está NESTE lugar passa a ser o nome dele.

    Acha o adaptador pelo lugar (``AdaptadorDoBluez.lugar``) e pede ao
    ``apelido_do_dongle.renomear_o_dongle`` — que costura o prefixo Nintendo e
    escreve pelo ``bluez_dbus``, dentro da trava comum do rádio. ``None``
    quando não há adaptador neste lugar: não há o que projetar.

    O dono devolve ``None`` quando NÃO DEU PARA PERGUNTAR, e isso não é "não
    há adaptador": a volta é uma recusa (``aplicado=False``), para quem chama
    saber que o ``Alias`` ficou com o nome velho (conferência, 23/09/2026).
    """
    lidos = adaptadores() if adaptadores is not None else _adaptadores_do_dono()
    if lidos is None:
        return _SemLeitura(lugar=lugar, nome=nome)
    alvo = next((a for a in lidos if getattr(a, "lugar", "") == lugar), None)
    if alvo is None:
        return None
    if renomear is not None:
        return renomear(alvo.endereco, nome)
    from hefesto_dualsense4unix.integrations.apelido_do_dongle import renomear_o_dongle

    return renomear_o_dongle(alvo.endereco, nome)


def _adaptadores_do_dono() -> Iterable[Any] | None:
    """Os adaptadores pelo dono do D-Bus — ``None`` = não deu para perguntar."""
    from hefesto_dualsense4unix.integrations import bluez_dbus

    return bluez_dbus.dono().adaptadores()


@dataclass(frozen=True)
class _SemLeitura:
    """A projeção que não aconteceu porque o BlueZ não respondeu."""

    lugar: str
    nome: str
    aplicado: bool = False


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


def _pendura_em(filho: Aparelho, pai: Aparelho) -> bool:
    """``3-4.2`` pendura em ``3-4``: mesmo barramento, e o devpath começa nele."""
    return filho.busnum == pai.busnum and filho.devpath.startswith(pai.devpath + ".")


def _nome_declarado(maquina: MaquinaConfig, lugar: str) -> str | None:
    declarado = maquina.lugares.get(lugar)
    return None if declarado is None else declarado.nome


def _entrada_do_caminho(maquina: MaquinaConfig, caminho: str, lugar: str) -> str | None:
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
        dono = lugar_da_entrada(maquina, numero)
        if dono is None or dono == lugar:
            return numero
    return None


def _numero_novo(mapa: MapaDaMesa) -> str:
    """O menor inteiro que ainda não é entrada do desenho."""
    usados = {int(n) for n in entradas_do_mapa(mapa) if n.isdigit()}
    proximo = 1
    while proximo in usados:
        proximo += 1
    return str(proximo)


def _ler_o_barramento() -> Censo:
    from hefesto_dualsense4unix.integrations.censo_do_barramento import (
        ler_o_barramento,
    )

    return ler_o_barramento()


def _nos_do_furo_no_sistema(caminho: str) -> tuple[str, ...]:
    """Os nós do buraco onde este aparelho está (``entradas_do_gabinete``)."""
    from hefesto_dualsense4unix.integrations.entradas_do_gabinete import (
        entrada_de,
        listar_entradas,
    )

    try:
        furo = entrada_de(caminho, listar_entradas())
    except Exception:  # defensivo — o sysfs some sob a mão
        return ()
    return () if furo is None else tuple(furo.nos)


def _controladores_do_sistema() -> dict[int, str]:
    from hefesto_dualsense4unix.integrations.mesa_de_radio import (
        controladores_dos_barramentos,
    )

    return controladores_dos_barramentos()


__all__ = [
    "ESPERANDO",
    "FACES",
    "FACE_ATRAS",
    "FACE_ESCRIVANINHA",
    "FACE_FRENTE",
    "FACE_HUB",
    "FACE_QUE_E_ALTO",
    "FACE_QUE_E_PERTO",
    "GRAVADA",
    "PALAVRA_DA_ENTRADA",
    "PARADO",
    "VISTA",
    "Gravacao",
    "LacoDaEntrada",
    "NomeDado",
    "PortaVista",
    "com_o_nome_dela",
    "dar_nome",
    "nome_da_porta",
    "nome_do_adaptador",
    "nome_do_lugar",
    "o_laco",
    "projetar_o_nome",
]
