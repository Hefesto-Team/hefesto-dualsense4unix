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

``docs/data/decisoes-dela.csv``, ``D-CALIBRAR-AS-ENTRADAS``: *"APROVADO POR ELA
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

``app/widgets/mapa_da_mesa.LogicaDoMapa.como_documento`` devolve ``nome`` e
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

import contextlib
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from hefesto_dualsense4unix.app.widgets.mapa_da_mesa import rotulo_do_aparelho
from hefesto_dualsense4unix.integrations.censo_do_barramento import (
    Aparelho,
    Censo,
    cadeia_de_hubs,
)
from hefesto_dualsense4unix.integrations.entradas_do_gabinete import (
    Furo,
    NoDeEntrada,
    entrada_de,
    furo_declarado,
    vazias,
)
from hefesto_dualsense4unix.integrations.lugar_declarado import (
    Recibo,
    declarar_a_maquina,
)
from hefesto_dualsense4unix.utils.i18n import _
from hefesto_dualsense4unix.utils.logging_config import get_logger
from hefesto_dualsense4unix.utils.maquina import MapaDaMesa

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
PERGUNTA_DO_HUB = "Onde fica o hub?"
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

SENTI_VOCE = "Senti você."

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

SEM_SINAL = (
    "Não chegou nada aqui. Enquanto o computador não enxerga o aparelho, eu "
    "não tenho como avisar na sua mão — nem vibração, nem luz. Encaixe de "
    "novo, ou me diga que aqui não tem buraco nenhum."
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

MARRETA_DURACAO_S = 0.82

MARRETA_QUADROS = 6

CHAVE_DE_ANIMACAO = "gtk-enable-animations"


def _marreta_hz() -> float:
    """Quantas vezes por segundo a marreta pisca — uma batida por 0,82 s."""
    return 1.0 / MARRETA_DURACAO_S


def _quadros_da_marreta(animar: bool) -> tuple[int, ...]:
    """Os quadros da batida — **tupla vazia** quando a animação está desligada."""
    return tuple(range(MARRETA_QUADROS)) if animar else ()


def _animacao_ligada(ajustes: Any) -> bool:
    """Lê ``gtk-enable-animations`` dos ajustes do GTK. Ausente = ligada."""
    if ajustes is None:
        return True
    try:
        return bool(ajustes.get_property(CHAVE_DE_ANIMACAO))
    except Exception:
        return True


VOCABULARIO_DA_CALIBRACAO = ("cross", "circle", "dpad_up", "dpad_down")

POSSE_DA_CALIBRACAO = "calibrar_entradas"


class PosseDoVocabulario:
    """Quem é dono dos botões da janela enquanto ela tem foco — o F-3."""

    def __init__(self) -> None:
        self.dono = ""

    def tomar(self, quem: str = POSSE_DA_CALIBRACAO) -> None:
        """Declara ``quem`` dono do :data:`VOCABULARIO_DA_CALIBRACAO`."""
        self.dono = quem

    def soltar(self) -> None:
        """Devolve o vocabulário. Mora no ``focus-out`` **e** no fechamento."""
        self.dono = ""


POSSE = PosseDoVocabulario()


GESTO_CONFIRMAR = "confirmar"
GESTO_ANDAR = "andar"
GESTO_PULAR = "pular"


class NavegacaoPorControle:
    """O payload vivo do DualSense virando gesto — **sem teclado nem mouse**.

    É a resposta ao R1: durante a fase em pé a pessoa está atrás ou embaixo do
    computador, com um cabo na mão, sem ver a tela e sem alcançar teclado ou
    mouse. Se o único jeito de confirmar fosse clicar, a cerimônia seria
    impossível justamente para quem ela foi desenhada.

    **Nenhum import novo** (R3): o DualSense já é entrada da GUI —
    ``app/widgets/controller_card.py`` lê ``inputs["buttons"]`` do payload vivo,
    e o laço da janela roda a 10 Hz. Esta classe só traduz.

    **Só a BORDA de subida conta.** Segurar o botão não repete o gesto: a 10 Hz
    um botão segurado por meio segundo avançaria cinco entradas de uma vez, e
    quem está atrás do gabinete não veria nenhuma delas. É a mesma disciplina
    do anti-ghost-input do daemon.
    """

    def __init__(self, quantas: int = len(FACES)) -> None:
        self._quantas = max(1, quantas)
        self._antes: frozenset[str] = frozenset()
        self.escolha = 0

    def passo(self, inputs: Mapping[str, Any]) -> str:
        """O gesto deste tique — ``""`` quando não houve nenhum."""
        botoes = frozenset(str(b) for b in (inputs.get("buttons") or ()))
        novos = botoes - self._antes
        self._antes = botoes
        if "dpad_down" in novos:
            self.escolha = (self.escolha + 1) % self._quantas
            return GESTO_ANDAR
        if "dpad_up" in novos:
            self.escolha = (self.escolha - 1) % self._quantas
            return GESTO_ANDAR
        if "cross" in novos:
            return GESTO_CONFIRMAR
        if "circle" in novos:
            return GESTO_PULAR
        return ""


def botoes_para_o_jogo(botoes: frozenset[str] | set[str]) -> frozenset[str]:
    """Os botões que PODEM seguir para o gamepad virtual."""
    if not POSSE.dono:
        return frozenset(botoes)
    return frozenset(botoes) - set(VOCABULARIO_DA_CALIBRACAO)


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


class LogicaDaCalibracao:
    """O rascunho do mapa e os gestos da cerimônia — sem GTK."""

    def __init__(
        self,
        mapa: MapaDaMesa,
        censo: Censo,
        entradas: Sequence[NoDeEntrada] = (),
        *,
        gravar: Callable[[Mapping[str, Any]], Recibo] = declarar_a_maquina,
    ) -> None:
        bruto = mapa.model_dump(mode="json")
        self.faces: list[dict[str, Any]] = [dict(f) for f in bruto.get("faces", [])]
        self.portas: dict[str, dict[str, Any]] = {
            numero: dict(valor) for numero, valor in bruto.get("portas", {}).items()
        }
        self._censo = censo
        self._entradas = tuple(entradas)
        self._gravar_no_disco = gravar
        self.fora_da_conta: set[str] = set()
        self.ultimo_recibo: Recibo | None = None


    def como_documento(self) -> dict[str, Any]:
        """O mapa no formato do ``maquina.json``, pronto para a gravação."""
        return {
            "faces": [dict(face) for face in self.faces],
            "portas": {
                numero: dict(valor) for numero, valor in sorted(self.portas.items())
            },
        }

    def entrada_do_caminho(self, caminho: str) -> str:
        """Em que entrada este aparelho já está — ``""`` se em nenhuma."""
        if not caminho:
            return ""
        for numero, valor in sorted(self.portas.items()):
            if valor.get("caminho") == caminho:
                return numero
        return ""

    def perguntas_sentadas(self) -> tuple[Pergunta, ...]:
        """Os passos da fase sentada, na ordem do barramento."""
        sem_lugar = [
            aparelho
            for aparelho in self._censo.conectados()
            if not self.entrada_do_caminho(aparelho.nome_do_kernel)
        ]
        por_no = {aparelho.no: aparelho for aparelho in sem_lugar}
        perguntas: list[Pergunta] = []
        cobertos: set[str] = set()
        for aparelho in sem_lugar:
            if aparelho.nome_do_kernel in cobertos:
                continue
            pendentes = self._pendentes_de(aparelho, por_no)
            cobertos.update(pendentes)
            perguntas.append(
                Pergunta(
                    caminho=aparelho.nome_do_kernel,
                    rotulo=rotulo_do_aparelho(aparelho),
                    pendentes=pendentes,
                    e_hub=aparelho.e_hub,
                )
            )
        return tuple(perguntas)

    def entradas_de_agora(self) -> tuple[NoDeEntrada, ...]:
        """A última leitura que esta lógica conhece — a base do veredito."""
        return self._entradas

    def caminhada(self) -> tuple[Furo, ...]:
        """A volta da fase em pé — **só o que está vazio** (o F-2)."""
        return tuple(
            furo
            for furo in vazias(self._entradas)
            if not (set(furo.nos) & self.fora_da_conta)
        )

    def progresso(self, feitos: int, total: int) -> str:
        """"entrada 4 de 15" — os DOIS números, nunca porcentagem sozinha (R26)."""
        return _("entrada {feitos} de {total}").format(feitos=feitos, total=total)

    def laudo(self) -> Laudo:
        """O exame da mesa — quatro blocos, e o quarto nunca some."""
        bem: list[str] = []
        atencao: list[str] = []
        nao_conferi: list[str] = []

        com_excesso = [
            entrada
            for entrada in self._entradas
            if (entrada.excesso_de_corrente or 0) > 0
        ]
        if self._entradas and not com_excesso:
            bem.append(
                _("Nenhuma entrada registrou excesso de corrente: zero em {n}.").format(
                    n=len(self._entradas)
                )
            )
        for entrada in com_excesso:
            atencao.append(
                _(
                    "A entrada {no} registrou excesso de corrente {n} vez(es) — "
                    "é o sintoma de aparelho pedindo mais do que ela entrega."
                ).format(no=entrada.no, n=entrada.excesso_de_corrente)
            )

        for aparelho in self._censo.conectados():
            if aparelho.energia.declaracao_incoerente:
                atencao.append(
                    _(
                        "{nome} declara fonte própria e mesmo assim pede "
                        "{ma} mA da entrada — a declaração não se sustenta."
                    ).format(
                        nome=rotulo_do_aparelho(aparelho),
                        ma=aparelho.energia.corrente_pedida_ma,
                    )
                )

        vagas = self.caminhada()
        if vagas:
            nao_conferi.append(
                _(
                    "{n} entrada(s) nunca receberam aparelho nenhum enquanto eu "
                    "olhava. Não sei se existem no metal ou se são conectores "
                    "internos que ninguém alcança."
                ).format(n=len(vagas))
            )
        sem_painel = [e for e in self._entradas if not e.painel]
        if sem_painel:
            nao_conferi.append(
                _(
                    "A tabela da sua placa não responde onde ficam {n} das {t} "
                    "entradas que eu vejo."
                ).format(n=len(sem_painel), t=len(self._entradas))
            )
        return Laudo(
            bem=tuple(bem),
            atencao=tuple(atencao),
            nao_conferi=tuple(nao_conferi),
        )


    def responder(self, pergunta: Pergunta, face: str) -> tuple[str, ...]:
        """A resposta da fase sentada — e ela vale para TUDO que pende."""
        numeros: list[str] = []
        for caminho in pergunta.pendentes:
            numeros.append(self._colocar(caminho, face))
        self._gravar()
        return tuple(numeros)

    def aprender(self, furo: Furo, face: str) -> str:
        """A entrada VAZIA que ela acabou de mostrar vira entrada declarada."""
        numero = self._numero_novo()
        self._por_na_face(face, numero)
        entrada = self.portas.setdefault(numero, {})
        entrada["nos"] = list(furo.nos)
        self._gravar()
        return numero

    def nao_alcanco(self, furo: Furo) -> None:
        """``[Não alcanço]`` — mesmo peso de confirmar, e TIRA da conta (R22)."""
        self.fora_da_conta.update(furo.nos)

    def confirmar_entrada_nova(
        self, antes: Sequence[NoDeEntrada], agora: Sequence[NoDeEntrada]
    ) -> Furo | None:
        """O veredito, e ele sai do ``sysfs`` — nunca da mão (o F-1)."""
        vazios_antes = {entrada.no for entrada in antes if entrada.vazio}
        for entrada in agora:
            if entrada.no in vazios_antes and entrada.aparelho:
                self._entradas = tuple(agora)
                return furo_declarado([entrada.no], self._entradas)
        self._entradas = tuple(agora)
        return None

    def furo_do_aparelho(self, caminho: str) -> Furo | None:
        """Em que buraco este aparelho está, pela leitura de agora.

        Existe para a fase sentada poder gravar os ``nos`` do buraco junto com
        o caminho: entrada ocupada não precisa de caminhada porque o aparelho
        que está nela já diz qual entrada é.
        """
        if not self._entradas:
            return None
        return entrada_de(caminho, self._entradas)


    def _pendentes_de(
        self, aparelho: Aparelho, por_no: Mapping[str, Aparelho]
    ) -> tuple[str, ...]:
        """O aparelho e, se ele for hub, tudo que pende dele — sem lugar ainda."""
        if not aparelho.e_hub:
            return (aparelho.nome_do_kernel,)
        abaixo = [
            outro.nome_do_kernel
            for outro in por_no.values()
            if outro.no != aparelho.no
            and aparelho.no in cadeia_de_hubs(self._censo, outro.no)
        ]
        return (aparelho.nome_do_kernel, *sorted(abaixo))

    def _colocar(self, caminho: str, face: str) -> str:
        """Dá a este aparelho uma entrada nova na face, com os ``nos`` dela."""
        numero = self._numero_novo()
        self._por_na_face(face, numero)
        entrada = self.portas.setdefault(numero, {})
        entrada["caminho"] = caminho
        furo = self.furo_do_aparelho(caminho)
        if furo is not None and furo.nos:
            entrada["nos"] = list(furo.nos)
        return numero

    def _por_na_face(self, face: str, numero: str) -> None:
        """Acha ou cria a face e põe o número no fim da fileira dela."""
        for existente in self.faces:
            if existente.get("nome") == face:
                existente.setdefault("portas", []).append(numero)
                return
        self.faces.append(
            {
                "nome": face,
                "portas": [numero],
                "perto": face == FACE_QUE_E_PERTO,
                "alto": face == FACE_QUE_E_ALTO,
            }
        )

    def _numero_novo(self) -> str:
        """O menor inteiro que ainda não é entrada de face nenhuma."""
        usados = {
            int(numero)
            for numero in self._todas_as_entradas()
            if numero.isdigit()
        }
        proximo = 1
        while proximo in usados:
            proximo += 1
        return str(proximo)

    def _todas_as_entradas(self) -> set[str]:
        numeros = {
            numero for face in self.faces for numero in face.get("portas", [])
        }
        numeros.update(self.portas)
        return numeros

    def _gravar(self) -> None:
        """Ao disco, agora, sem IPC — o CAL-2."""
        recibo = self._gravar_no_disco({"mapa": self.como_documento()})
        self.ultimo_recibo = recibo
        if not recibo.gravou:
            logger.warning("calibracao_nao_gravou", motivo=recibo.motivo)


def _nome_acessivel_do_cartao(numero: str, face: str) -> str:
    """A frase de confirmação — e ela **é** o nome acessível do cartão (R14)."""
    return _("{palavra} {numero} · {face}").format(
        palavra=_(PALAVRA_DA_ENTRADA), numero=numero, face=_(face)
    )


try:
    import gi

    gi.require_version("Gtk", "3.0")
    from gi.repository import GLib, Gtk

    _GTK_DISPONIVEL = True
except (ImportError, ValueError):  # pragma: no cover - ambiente sem PyGObject
    _GTK_DISPONIVEL = False


if _GTK_DISPONIVEL:

    class JanelaDeCalibrarEntradas(Gtk.Window):  # type: ignore[misc]
        """A cerimônia inteira. Todo estado mora na :class:`LogicaDaCalibracao`.

        **Não existe tela de boas-vindas** (R27): começar é o passo mais
        difícil, e o primeiro toque já é trabalho útil. A janela nasce na
        primeira pergunta — ou no fim da fase sentada, quando não há pergunta
        nenhuma.

        **Um passo por vez** (R25): uma entrada na tela, nunca uma grade de 15
        para preencher.
        """

        def __init__(
            self,
            host: Any,
            mapa: MapaDaMesa,
            censo: Censo,
            entradas: Sequence[NoDeEntrada] = (),
            *,
            gravar: Callable[[Mapping[str, Any]], Recibo] = declarar_a_maquina,
        ) -> None:
            Gtk.Window.__init__(self, title=_(TITULO_DA_JANELA))
            self._host = host
            self.logica = LogicaDaCalibracao(mapa, censo, entradas, gravar=gravar)
            self._perguntas = list(self.logica.perguntas_sentadas())
            self._passo = 0
            self.quadros_batidos = 0
            self.botoes_de_face: dict[str, Any] = {}

            self.set_default_size(640, 420)
            with contextlib.suppress(Exception):
                self.set_transient_for(getattr(host, "window", None))
            self.connect("delete-event", self._ao_fechar)
            self.connect("focus-in-event", self._ao_ganhar_foco)
            self.connect("focus-out-event", self._ao_perder_foco)

            self._raiz = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
            for lado in ("start", "end", "top", "bottom"):
                getattr(self._raiz, f"set_margin_{lado}")(12)
            self.add(self._raiz)

            self.navegacao = NavegacaoPorControle(len(FACES))
            self.em_pe = False
            self._aprendidas = 0
            self._antes_do_encaixe: tuple[NoDeEntrada, ...] = tuple(entradas)
            self._cartao = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
            self._botoes = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            self._montar()
            self.redesenhar()


        def _montar(self) -> None:
            self.rotulo_pergunta = self._etiqueta("", tamanho=84)
            self.rotulo_contador = self._etiqueta("", tamanho=48)
            self.rotulo_quem = self._etiqueta("", tamanho=84)
            self._cartao.pack_start(self.rotulo_pergunta, False, False, 0)
            self._cartao.pack_start(self.rotulo_contador, False, False, 0)
            self._cartao.pack_start(self.rotulo_quem, False, False, 0)
            self._raiz.pack_start(self._cartao, False, False, 0)
            self._raiz.pack_start(self._botoes, False, False, 0)

            self.rotulo_relogios = self._etiqueta(_(OS_DOIS_RELOGIOS), tamanho=84)
            self._raiz.pack_start(self.rotulo_relogios, False, False, 0)

            rodape = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            self.botao_nao_sei = Gtk.Button(label=_(ROTULO_NAO_SEI))
            self.botao_nao_sei.connect("clicked", self._ao_pular)
            rodape.pack_start(self.botao_nao_sei, False, False, 0)
            self.botao_ja_chega = Gtk.Button(label=_(ROTULO_JA_CHEGA))
            self.botao_ja_chega.connect("clicked", lambda *_a: self._fechar())
            rodape.pack_end(self.botao_ja_chega, False, False, 0)
            self._raiz.pack_start(rodape, False, False, 0)

        def _etiqueta(self, texto: str, *, tamanho: int) -> Any:
            """Um ``Gtk.Label`` que nasce ``can_focus=False`` — R12, MEDIDO."""
            etiqueta = Gtk.Label(label=texto)
            etiqueta.set_xalign(0.0)
            etiqueta.set_halign(Gtk.Align.START)
            etiqueta.set_line_wrap(True)
            etiqueta.set_max_width_chars(tamanho)
            etiqueta.set_can_focus(False)
            return etiqueta


        def redesenhar(self) -> None:
            """Um passo por vez. Sem grade, sem tela intermediária."""
            for filho in list(self._botoes.get_children()):
                self._botoes.remove(filho)
            self.botoes_de_face.clear()

            if self.em_pe:
                self._desenhar_a_volta()
                return
            if self._passo >= len(self._perguntas):
                self._desenhar_o_fim()
                return

            pergunta = self._perguntas[self._passo]
            self.rotulo_pergunta.set_text(
                _(PERGUNTA_DO_HUB) if pergunta.e_hub else _(PERGUNTA_SENTADA)
            )
            self.rotulo_contador.set_text(
                self.logica.progresso(self._passo + 1, len(self._perguntas))
                + f" · {_(SEM_SAIR_DA_CADEIRA)}"
            )
            self.rotulo_quem.set_text(pergunta.rotulo)
            for face in FACES:
                botao = Gtk.Button(label=_(face))
                botao.set_size_request(-1, 30)
                botao.connect("clicked", self._ao_responder, face)
                self._botoes.pack_start(botao, False, False, 0)
                self.botoes_de_face[face] = botao
            self._botoes.show_all()
            with contextlib.suppress(Exception):
                self.botoes_de_face[FACE_FRENTE].grab_focus()

        def _desenhar_o_fim(self) -> None:
            """O fim da fase sentada, e ele é um fim de verdade (R31)."""
            self.rotulo_pergunta.set_text(_(FIM_DA_FASE_SENTADA))
            self.rotulo_contador.set_text("")
            self.rotulo_quem.set_text(_(CONVITE_EM_PE))
            self.botao_vou_mostrar = Gtk.Button(label=_(ROTULO_VOU_MOSTRAR))
            self.botao_vou_mostrar.set_size_request(-1, 30)
            self.botao_vou_mostrar.connect("clicked", self._ao_levantar)
            self._botoes.pack_start(self.botao_vou_mostrar, False, False, 0)
            depois = Gtk.Button(label=_(ROTULO_DEIXAR_PARA_DEPOIS))
            depois.connect("clicked", lambda *_a: self._fechar())
            self._botoes.pack_start(depois, False, False, 0)
            self._botoes.show_all()

        def _desenhar_a_volta(self) -> None:
            """A fase em pé — e ela nunca manda ninguém a um buraco ocupado."""
            vagas = self.logica.caminhada()
            if not vagas:
                self._desenhar_o_fim()
                return
            self.rotulo_pergunta.set_text(_(CONVITE_DO_ENCAIXE))
            self.rotulo_contador.set_text(
                self.logica.progresso(self._aprendidas + 1, len(vagas) + self._aprendidas)
            )
            self.rotulo_quem.set_text(_(PROCURANDO))
            nao_alcanco = Gtk.Button(label=_(ROTULO_NAO_ALCANCO))
            nao_alcanco.set_size_request(-1, 30)
            nao_alcanco.connect("clicked", self._ao_nao_alcancar)
            self._botoes.pack_start(nao_alcanco, False, False, 0)
            self.botao_nao_alcanco = nao_alcanco
            self._botoes.show_all()
            with contextlib.suppress(Exception):
                nao_alcanco.grab_focus()

        def _ao_levantar(self, _botao: Any) -> None:
            self.em_pe = True
            self._antes_do_encaixe = tuple(self.logica.entradas_de_agora())
            self.redesenhar()

        def _ao_nao_alcancar(self, _botao: Any) -> None:
            """`[Não alcanço]` — mesmo peso de confirmar, e tira da conta."""
            vagas = self.logica.caminhada()
            if vagas:
                self.logica.nao_alcanco(vagas[0])
            self.redesenhar()

        def tique(self, agora: Sequence[NoDeEntrada]) -> str:
            """Um tique da fase em pé — ``""`` quando ainda não achou nada."""
            furo = self.logica.confirmar_entrada_nova(self._antes_do_encaixe, agora)
            if furo is None:
                return ""
            numero = self.logica.aprender(furo, FACE_ATRAS)
            self._aprendidas += 1
            self._antes_do_encaixe = tuple(agora)
            self.bater_a_marreta(_nome_acessivel_do_cartao(numero, FACE_ATRAS))
            self.redesenhar()
            return numero


        def _ao_responder(self, _botao: Any, face: str) -> None:
            pergunta = self._perguntas[self._passo]
            numeros = self.logica.responder(pergunta, face)
            if numeros:
                self.bater_a_marreta(_nome_acessivel_do_cartao(numeros[0], face))
            self._passo += 1
            self.redesenhar()

        def ao_payload_do_controle(self, inputs: Mapping[str, Any]) -> str:
            """O tique de 10 Hz da GUI, traduzido em gesto — o R1 e o R9."""
            gesto = self.navegacao.passo(inputs)
            if gesto == GESTO_ANDAR:
                self._focar_a_escolha()
            elif gesto == GESTO_CONFIRMAR:
                face = FACES[self.navegacao.escolha]
                botao = self.botoes_de_face.get(face)
                if botao is not None:
                    botao.clicked()
            elif gesto == GESTO_PULAR:
                self._ao_pular(None)
            return gesto

        def _focar_a_escolha(self) -> None:
            """Mover o FOCO é o anúncio (R13) — não há live region no GTK 3."""
            botao = self.botoes_de_face.get(FACES[self.navegacao.escolha])
            if botao is not None:
                with contextlib.suppress(Exception):
                    botao.grab_focus()

        def _ao_pular(self, _botao: Any) -> None:
            """"Não sei onde fica" anda sem gravar — e sem cobrar depois."""
            self._passo += 1
            self.redesenhar()

        def bater_a_marreta(self, nome_acessivel: str) -> None:
            """A batida — e ela respeita ``gtk-enable-animations`` (R35)."""
            with contextlib.suppress(Exception):
                self.rotulo_pergunta.get_accessible().set_name(nome_acessivel)
            self.rotulo_pergunta.set_text(f"{_(SENTI_VOCE)} {nome_acessivel}")
            quadros = _quadros_da_marreta(
                _animacao_ligada(Gtk.Settings.get_default())
            )
            if not quadros:
                return
            intervalo = int(MARRETA_DURACAO_S * 1000 / len(quadros))
            for quadro in quadros:
                GLib.timeout_add(intervalo * (quadro + 1), self._um_quadro)

        def _um_quadro(self) -> bool:
            self.quadros_batidos += 1
            return False


        def _ao_ganhar_foco(self, *_a: Any) -> bool:
            POSSE.tomar()
            return False

        def _ao_perder_foco(self, *_a: Any) -> bool:
            POSSE.soltar()
            return False

        def _ao_fechar(self, *_a: Any) -> bool:
            POSSE.soltar()
            return False

        def _fechar(self) -> None:
            """Sair não pede confirmação e não mostra o que faltou (R30)."""
            POSSE.soltar()
            with contextlib.suppress(Exception):
                self.destroy()


__all__ = [
    "FACES",
    "FACE_ATRAS",
    "FACE_FRENTE",
    "FACE_HUB",
    "FACE_MESA",
    "GESTO_ANDAR",
    "GESTO_CONFIRMAR",
    "GESTO_PULAR",
    "MARRETA_DURACAO_S",
    "POSSE",
    "VOCABULARIO_DA_CALIBRACAO",
    "Laudo",
    "LogicaDaCalibracao",
    "NavegacaoPorControle",
    "Pergunta",
    "PosseDoVocabulario",
    "botoes_para_o_jogo",
]

if _GTK_DISPONIVEL:
    __all__.append("JanelaDeCalibrarEntradas")
