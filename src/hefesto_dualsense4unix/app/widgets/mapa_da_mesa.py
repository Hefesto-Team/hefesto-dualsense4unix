"""A janela onde ela desenha o gabinete — clique no aparelho, clique na entrada.

CONEXÕES · MAPA 2D 01, tarefa ``MAPA-4`` (25/08/2026).

POR QUE JANELA PRÓPRIA, E NÃO DENTRO DA SEÇÃO
-----------------------------------------------

O número decide: a seção "Conexões" já pede **2465 px numa janela de 1080**
(``CONFIGURAÇÕES-FECHA-01`` §2.4). Três faces de quadrados mais a lista de
aparelhos são mais uns 350 px, e nasceriam abaixo da dobra — seria construir a
feature e escondê-la, que é a ``A-CASA-SABE-E-O-PRODUTO-NAO-FAZ`` de novo.
Dentro da seção fica uma linha e um botão; o desenho mora aqui.

POR QUE CLIQUE-EM-CLIQUE, E NÃO ARRASTAR
-----------------------------------------

Decisão de quem coordena a leva (25/08/2026), pelo que a própria sprint mediu:

* **código:** dois sinais (``toggled``, ``clicked``) contra quatro
  (``drag-begin``, ``drag-data-get``, ``drag-data-received``, ``drag-drop``)
  mais ``Gtk.TargetEntry`` e ícone de arrasto;
* **precedente:** ``Gtk.Grid`` está em dez arquivos desta casa; arrastar-e-
  soltar está em **zero** — medido, ``grep`` de ``drag_source_set`` em ``src/``
  não devolve nada;
* **teclado:** Tab e Enter funcionam de graça; arrastar é inutilizável sem
  mouse;
* **foto:** os estados são contáveis — nada escolhido, aparelho escolhido,
  entrada cheia, entrada com extensão, mesa vazia —, e um arrasto pela metade
  **não é um estado**, então o retrato de diálogos não o fotografa.

A decisão ``D-MAPA-2D`` dela diz *"desenhado e arrastado por ela"*, e a palavra
"arrastado" continua sendo dela: **ela reverte esta escolha numa frase.**

O QUE ESTA JANELA NÃO FAZ
--------------------------

**Não grava em disco.** Ela escreve no rascunho ``host._maquina_pendente``, e
quem grava é o "Aplicar" do rodapé — o mesmo gesto das outras seções. Um
desenho que se gravasse sozinho seria a única coisa da aba a não esperar o
botão, e a pessoa perderia o "desfazer" que o rascunho dá de graça.

**Não cria face nenhuma sozinha.** Um notebook declara "Esquerda: 1, 2" e
"Direita: 3", e ponto. Face inventada é a presunção que a ``ONDA0-Z7 · O
AMBIENTE PRESUMIDO`` existe para caçar. Zero faces é estado legítimo, e a
janela nasce assim para quem nunca desenhou.

**Não detecta extensão.** Cabo de extensão passivo não tem descritor USB, e
nenhuma leitura de ``/sys``, hoje ou nunca, distingue "dongle na entrada do
hub" de "dongle a três metros dali". Quem sabe é ela, pelo botão
"Tem uma extensão aqui" — e é por isso que a entrada por extensão carrega o
selo de que foi ela quem disse.

COMO A REMOÇÃO CHEGA AO DISCO — E POR QUE NÃO É "SUMIR DO RASCUNHO"
--------------------------------------------------------------------

``gravar_maquina`` funde a declaração contra o disco, e a regra do módulo é
explícita: *"``None`` presente na declaração é uma escolha ('voltei para Não
sei') e SOBRESCREVE. Só a AUSÊNCIA da chave preserva o que havia."* Logo, tirar
um aparelho de uma entrada **não pode** ser tirar a chave do rascunho: a chave
ausente é exatamente o que manda o disco preservar o que estava lá, e o
aparelho voltaria no "Aplicar" seguinte.

Tirar é escrever ``caminho: None``. O ``_podar`` da gravação tira o ``None``
antes de escrever, e a entrada **some do arquivo** — que é onde sumir importa.
"""
from __future__ import annotations

import contextlib
from collections.abc import Callable, Mapping
from typing import Any

from hefesto_dualsense4unix.integrations import arranjo_da_mesa as motor
from hefesto_dualsense4unix.integrations import mapa_das_portas
from hefesto_dualsense4unix.integrations.censo_do_barramento import Aparelho, Censo
from hefesto_dualsense4unix.utils.i18n import _
from hefesto_dualsense4unix.utils.logging_config import get_logger
from hefesto_dualsense4unix.utils.maquina import MapaDaMesa

logger = get_logger(__name__)

#: O título da janela e a frase que explica o gesto de dois tempos.
#: PROVISÓRIO — decisão dela: texto novo, e a prova de tela não fechou.
TITULO_DA_JANELA = "A minha mesa"
EXPLICACAO = (
    "Clique no aparelho, depois na entrada em que ele está. O Hefesto passa a "
    "chamar cada aparelho pelo número que você escreveu no gabinete."
)

#: Os rótulos dos gestos. Todos em "entrada", nunca "porta".
#: PROVISÓRIO — decisão dela.
ROTULO_APARELHOS = "O que o Hefesto encontrou"
ROTULO_SEM_FACE = (
    "Você ainda não criou nenhuma face. Crie uma para cada conjunto de "
    "entradas que você enxerga junto: a frente do gabinete, a traseira, o hub."
)
ROTULO_TIRAR = "Tirar daqui"
ROTULO_EXTENSAO = "Tem uma extensão aqui"
ROTULO_NOVA_ENTRADA = "Acrescentar entrada"
ROTULO_NOVA_FACE = "Acrescentar face"
ROTULO_FECHAR = "Fechar"
ROTULO_VAZIA = "vazia"
ROTULO_POR_EXTENSAO = "por extensão"
NOME_DA_FACE_EM_BRANCO = "Nome da face"

#: O rádio que não pendura em USB nenhum — o embutido do notebook. Ele é um
#: quadrado FIXO, fora das faces e nunca editável. Sem ele o dono do notebook
#: abre o mapa, não acha o Bluetooth dele em entrada nenhuma e conclui que o
#: produto está quebrado — e é o caso mais comum lá fora.
#: PROVISÓRIO — decisão dela.
ROTULO_EMBUTIDO = "Dentro da máquina"

#: A frase que diz que este desenho espera o "Aplicar", como o resto da aba.
#: PROVISÓRIO — decisão dela.
ESPERA_O_APLICAR = (
    "O desenho vale quando você clicar em Aplicar, na barra de baixo da janela."
)

#: As letras que uma entrada por extensão pode receber, na ordem. Vinte e seis
#: extensões numa entrada só é mais do que qualquer gabinete comporta, e o
#: esquema recusa a vigésima sétima — que é o teto fazendo o trabalho dele.
_LETRAS = "abcdefghijklmnopqrstuvwxyz"

#: Quantas entradas cabem numa fileira antes de quebrar para a linha seguinte.
#: Sete é a fileira do hub dela, que é a maior face desta casa.
_COLUNAS = 7

#: O cabeçalho da confissão, e a frase de cada coisa que o desenho não diz.
#: PROVISÓRIO — decisão dela: texto novo, e a prova de tela não fechou.
#:
#: O cabeçalho sai do léxico que já existe: ``calibrar_entradas.LAUDO_NAO_CONFERI``
#: é "O que eu não consegui conferir", e esta é a mesma coisa dita sobre o
#: desenho em vez de sobre a entrada.
#:
#: POR QUE ELAS EXISTEM: o motor recebe cada campo com o valor por omissão
#: quando ninguém o preencheu, e não tem como distinguir "é assim" de "ninguém
#: disse". Publicar o juízo sem publicar isto é o juízo otimista CALADO que a
#: ``D-O-PAR-DE-ENTRADAS-VEM-DO-SYSFS`` mandou acabar: *"a linha do mapa DIZ
#: isso em vez de calar"*.
CONFISSAO_ABERTURA = "O que eu não consegui conferir neste desenho:"
CONFISSAO: dict[str, str] = {
    mapa_das_portas.LACUNA_POSICAO: (
        "em que ponto da fileira cada entrada fica. Sem isso eu não conto a "
        "folga entre dois adaptadores de rádio, e duas entradas nas pontas "
        "opostas do hub recebem o mesmo juízo de duas coladas."
    ),
    mapa_das_portas.LACUNA_PAR: (
        "quais entradas ficam coladas no metal: alguma face está com um "
        "número sobrando. Eu as leio de duas em duas, na ordem em que você as "
        "desenhou."
    ),
    mapa_das_portas.LACUNA_VELOCIDADE: (
        "quais entradas são azuis. Enquanto você não passar por "
        "\"Calibrar as entradas\", eu trato todas como pretas."
    ),
    mapa_das_portas.LACUNA_REGIAO: (
        "se alguma face é do gabinete ou de um hub — nenhuma entrada dela tem "
        "aparelho declarado."
    ),
    mapa_das_portas.LACUNA_ESPECIE: (
        "o que é algum dos aparelhos da lista: o sistema não diz o que ele é, "
        "e sobre ele eu não tenho juízo nenhum."
    ),
}


class LogicaDoMapa:
    """O rascunho do gabinete e os quatro gestos que o mudam — sem GTK.

    Mora fora da janela de propósito: é aqui que a decisão dela vira dado, e
    dado que só existe dentro de um widget não se testa sem display. A janela
    chama estes métodos e redesenha; ela não guarda estado nenhum.
    """

    def __init__(self, mapa: MapaDaMesa) -> None:
        bruto = mapa.model_dump(mode="json")
        #: ``perto`` e ``alto`` viajam intactos, e não é zelo: são FATO DELA
        #: (a face virada para quem senta, a face no alto do rack), só ela os
        #: tem, e a gravação SUBSTITUI a lista de faces inteira. Deixá-los cair
        #: aqui faria o primeiro "Aplicar" depois de um clique no desenho
        #: apagar do disco o que ela declarou noutra tela.
        self.faces: list[dict[str, Any]] = [
            {
                "nome": face.get("nome", ""),
                "portas": list(face.get("portas", [])),
                "perto": bool(face.get("perto", False)),
                "alto": bool(face.get("alto", False)),
            }
            for face in bruto.get("faces", [])
        ]
        self.portas: dict[str, dict[str, Any]] = {
            numero: dict(valor) for numero, valor in bruto.get("portas", {}).items()
        }
        #: O caminho do aparelho escolhido no primeiro tempo do gesto — ``""``
        #: quando nada está escolhido, que é o estado em que a janela nasce.
        self.escolhido: str = ""

    # -- leitura ------------------------------------------------------------

    def como_documento(self) -> dict[str, Any]:
        """O rascunho no formato do ``maquina.json``, pronto para o rodapé."""
        return {
            "faces": [
                {
                    "nome": face["nome"],
                    "portas": list(face["portas"]),
                    "perto": bool(face.get("perto", False)),
                    "alto": bool(face.get("alto", False)),
                }
                for face in self.faces
            ],
            "portas": {
                numero: dict(valor) for numero, valor in sorted(self.portas.items())
            },
        }

    def caminho_em(self, numero: str) -> str:
        """O caminho declarado nesta entrada, ou ``""``."""
        return str(self.portas.get(numero, {}).get("caminho") or "")

    def filhas_de(self, numero: str) -> list[str]:
        """As entradas que nascem de uma extensão plugada nesta."""
        return sorted(
            outro
            for outro, valor in self.portas.items()
            if valor.get("filha_de") == numero and outro != numero
        )

    def entrada_do_caminho(self, caminho: str) -> str:
        """Em que entrada este aparelho já está — ``""`` se em nenhuma."""
        if not caminho:
            return ""
        for numero, valor in sorted(self.portas.items()):
            if valor.get("caminho") == caminho:
                return numero
        return ""

    # -- os quatro gestos ---------------------------------------------------

    def escolher(self, caminho: str) -> None:
        """Primeiro tempo: escolhe o aparelho. Escolher de novo desescolhe."""
        self.escolhido = "" if self.escolhido == caminho else caminho

    def colocar(self, numero: str) -> bool:
        """Segundo tempo: põe o aparelho escolhido nesta entrada.

        Um aparelho está em UM lugar: pôr onde ele já não estava o tira de onde
        estava, no mesmo gesto. Sem isso o mesmo dongle apareceria em duas
        entradas e o mapa passaria a mentir de um jeito novo.
        """
        if not self.escolhido or numero not in self._todas_as_entradas():
            return False
        anterior = self.entrada_do_caminho(self.escolhido)
        if anterior and anterior != numero:
            self._esvaziar(anterior)
        entrada = self.portas.setdefault(numero, {})
        entrada["caminho"] = self.escolhido
        self.escolhido = ""
        return True

    def tirar(self, numero: str) -> bool:
        """Tira o aparelho desta entrada — escrevendo ``None``, não sumindo.

        Ver o cabeçalho do módulo: a chave AUSENTE é o que manda a gravação
        preservar o que estava no disco. Só o ``None`` explícito apaga.
        """
        if numero not in self.portas:
            return False
        if not self.portas[numero].get("caminho"):
            return False
        self._esvaziar(numero)
        return True

    def acrescentar_extensao(self, numero: str) -> str:
        """Cria a entrada-filha desta entrada — ``15`` vira ``15a``.

        A filha NÃO entra na fileira da face: ela desenha dentro do quadrado de
        quem a hospeda. Pôr a ``15a`` na fileira faria a fileira de sete do hub
        virar oito, e o desenho deixaria de bater com o metal.
        """
        if numero not in self._todas_as_entradas() or not numero.isdigit():
            return ""
        usadas = {filha[len(numero) :] for filha in self.filhas_de(numero)}
        for letra in _LETRAS:
            if letra in usadas:
                continue
            nova = f"{numero}{letra}"
            self.portas[nova] = {"caminho": None, "filha_de": numero}
            return nova
        return ""

    def acrescentar_entrada(self, indice: int) -> str:
        """Acrescenta a próxima entrada livre a esta face.

        O número é o menor inteiro que ainda não existe em face nenhuma: os
        números são do GABINETE, e dois buracos diferentes não podem receber o
        mesmo número.
        """
        if not 0 <= indice < len(self.faces):
            return ""
        usados = {
            int(numero)
            for numero in self._todas_as_entradas()
            if numero.isdigit()
        }
        proximo = 1
        while proximo in usados:
            proximo += 1
        numero = str(proximo)
        self.faces[indice]["portas"].append(numero)
        return numero

    def acrescentar_face(self, nome: str) -> bool:
        """Cria uma face com o nome que ELA escreveu. Sem nome, não cria."""
        limpo = nome.strip()
        if not limpo:
            return False
        self.faces.append(
            {"nome": limpo, "portas": [], "perto": False, "alto": False}
        )
        return True

    def tirar_face(self, indice: int) -> bool:
        """Tira uma face e as entradas dela — inclusive as por extensão."""
        if not 0 <= indice < len(self.faces):
            return False
        face = self.faces.pop(indice)
        for numero in face["portas"]:
            for filha in self.filhas_de(numero):
                self._esvaziar(filha)
            self._esvaziar(numero)
        return True

    # -- interno ------------------------------------------------------------

    def _todas_as_entradas(self) -> set[str]:
        numeros = {numero for face in self.faces for numero in face["portas"]}
        numeros.update(self.portas)
        return numeros

    def _esvaziar(self, numero: str) -> None:
        entrada = self.portas.setdefault(numero, {})
        entrada["caminho"] = None
        if "filha_de" not in entrada:
            entrada["filha_de"] = None


def bancada_do_rascunho(logica: LogicaDoMapa, censo: Censo) -> mapa_das_portas.Bancada:
    """A mesa do motor montada a partir do RASCUNHO — não do disco.

    Do rascunho porque é ele que está na frente dela: assim o juízo de cada
    quadrado responde ao clique que ela acabou de dar, e não ao que o
    "Aplicar" ainda não gravou. Um mapa que só julgasse depois do botão faria
    a pessoa aplicar para descobrir se o lugar era bom.
    """
    return mapa_das_portas.mesa_do_motor(
        MapaDaMesa.model_validate(logica.como_documento()), censo
    )


def classe_do_escolhido(bancada: mapa_das_portas.Bancada, caminho: str) -> str:
    """A classe que o motor julga para o aparelho na mão — ``""`` se ele não a tem.

    ``""`` acontece de verdade e não é borda: o Archer T3U desta bancada
    declina de se classificar e o DualSense por cabo é HID sem protocolo de
    arranque. Para eles não há regra no motor, e o quadrado cala em vez de
    julgar pelo aparelho errado.
    """
    if not caminho:
        return ""
    for aparelho in bancada.mesa.aparelhos:
        if aparelho.id == caminho:
            return aparelho.classe
    return ""


def veredito_do_quadrado(
    bancada: mapa_das_portas.Bancada, numero: str, escolhido: str
) -> motor.Veredito | None:
    """O que este quadrado diz sobre o aparelho que está na mão dela.

    ``None`` quando não há nada a dizer — e é a maioria das vezes, porque
    ``None`` é o que o motor devolve para uma entrada vazia sem aparelho na
    mão. Publicar o veredito só no gesto de dois tempos é o mesmo desenho do
    resto da janela: ela clica no aparelho, e aí cada entrada responde.
    """
    entrada = motor.por_num(bancada.mesa.faces, numero)
    if entrada is None:
        return None
    return motor.julgar(
        entrada,
        classe_do_escolhido(bancada, escolhido) or None,
        bancada.mesa,
        escolhido or None,
    )


def confissao_do_desenho(bancada: mapa_das_portas.Bancada) -> tuple[str, ...]:
    """As frases do que o desenho não diz, na ordem das chaves.

    Vazio quando o desenho responde por tudo. Chave sem frase não some calada:
    ela sai com o próprio nome, para que a próxima pessoa veja que falta a
    palavra em vez de ver o silêncio.
    """
    return tuple(
        _(CONFISSAO[chave]) if chave in CONFISSAO else chave
        for chave in bancada.lacunas
    )


def aparelhos_para_colocar(censo: Censo) -> tuple[Aparelho, ...]:
    """Tudo que o censo achou, menos os hubs-raiz — na ordem do barramento.

    Os hubs de bancada FICAM na lista, e é de propósito: o cabo do hub dela
    ocupa uma entrada da traseira, e é justamente essa amarração que ensina o
    produto a não acusar as entradas do hub de não pendurarem em lugar nenhum.
    """
    return censo.conectados()


def rotulo_do_aparelho(aparelho: Aparelho) -> str:
    """A palavra de tela de um aparelho da lista — espécie e caminho.

    O caminho fica visível porque ele é a única coisa que distingue dois
    aparelhos idênticos: os dois adaptadores Bluetooth desta bancada são o
    mesmo ``2357:0604``, e uma lista que só mostrasse a espécie ofereceria dois
    itens iguais para dois aparelhos diferentes.
    """
    return f"{aparelho.especie} · {aparelho.nome_do_kernel}"


# ---------------------------------------------------------------------------
# Resolução condicional de GTK (mesmo padrão de segmented_selector)
# ---------------------------------------------------------------------------

try:
    import gi

    gi.require_version("Gtk", "3.0")
    from gi.repository import Gtk

    _GTK_DISPONIVEL = True
except (ImportError, ValueError):  # pragma: no cover - ambiente sem PyGObject
    _GTK_DISPONIVEL = False


if _GTK_DISPONIVEL:

    class JanelaDoMapaDaMesa(Gtk.Window):  # type: ignore[misc]
        """A janela do desenho. Todo estado mora na :class:`LogicaDoMapa`."""

        def __init__(
            self,
            host: Any,
            mapa: MapaDaMesa,
            censo: Censo,
            *,
            ao_fechar: Callable[[], None] | None = None,
        ) -> None:
            Gtk.Window.__init__(self, title=_(TITULO_DA_JANELA))
            self._host = host
            self._censo = censo
            self._ao_fechar = ao_fechar
            self.logica = LogicaDoMapa(mapa)
            #: A entrada em que ela clicou por último, para os gestos que agem
            #: sobre uma entrada ("Tirar daqui", "Tem uma extensão aqui").
            self._em_foco = ""
            #: `número -> botão`, para o teste e para o retrato alcançarem um
            #: quadrado sem varrer a árvore de widgets.
            self.quadrados: dict[str, Any] = {}
            self.aparelhos: dict[str, Any] = {}
            #: `número -> veredito`, o juízo publicado no último redesenho. Fica
            #: aqui pelo mesmo motivo de `quadrados`: para o teste e o retrato
            #: alcançarem o que a tela diz sem varrer a árvore de widgets.
            self.vereditos: dict[str, motor.Veredito] = {}
            #: As frases do que o desenho não diz, no último redesenho.
            self.confissao: tuple[str, ...] = ()
            self._bancada = mapa_das_portas.Bancada(
                mesa=motor.Mesa(aparelhos=(), faces=(), mapa={}, leitura={})
            )

            self.set_default_size(720, 520)
            with contextlib.suppress(Exception):
                self.set_transient_for(getattr(host, "window", None))
            self.connect("delete-event", self._ao_fechar_a_janela)

            self._raiz = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
            self._raiz.set_margin_start(12)
            self._raiz.set_margin_end(12)
            self._raiz.set_margin_top(12)
            self._raiz.set_margin_bottom(12)
            self.add(self._raiz)

            self._caixa_aparelhos = Gtk.Box(
                orientation=Gtk.Orientation.VERTICAL, spacing=4
            )
            self._caixa_faces = Gtk.Box(
                orientation=Gtk.Orientation.VERTICAL, spacing=8
            )
            self._caixa_confissao = Gtk.Box(
                orientation=Gtk.Orientation.VERTICAL, spacing=2
            )
            self._montar()
            self._redesenhar()

        # -- montagem ------------------------------------------------------

        def _montar(self) -> None:
            explicacao = Gtk.Label(label=_(EXPLICACAO))
            explicacao.set_xalign(0.0)
            explicacao.set_halign(Gtk.Align.START)
            explicacao.set_line_wrap(True)
            explicacao.set_max_width_chars(84)
            self._raiz.pack_start(explicacao, False, False, 0)

            corpo = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=16)
            esquerda = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
            titulo = Gtk.Label(label=_(ROTULO_APARELHOS))
            titulo.set_xalign(0.0)
            esquerda.pack_start(titulo, False, False, 0)
            esquerda.pack_start(self._caixa_aparelhos, False, False, 0)
            corpo.pack_start(esquerda, False, False, 0)
            corpo.pack_start(self._caixa_faces, True, True, 0)
            self._raiz.pack_start(corpo, True, True, 0)
            self._raiz.pack_start(self._caixa_confissao, False, False, 0)

            acoes = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            self.botao_tirar = Gtk.Button(label=_(ROTULO_TIRAR))
            self.botao_tirar.connect("clicked", self._ao_tirar)
            acoes.pack_start(self.botao_tirar, False, False, 0)
            self.botao_extensao = Gtk.Button(label=_(ROTULO_EXTENSAO))
            self.botao_extensao.connect("clicked", self._ao_acrescentar_extensao)
            acoes.pack_start(self.botao_extensao, False, False, 0)
            self._raiz.pack_start(acoes, False, False, 0)

            nova_face = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            self.campo_da_face = Gtk.Entry()
            self.campo_da_face.set_placeholder_text(_(NOME_DA_FACE_EM_BRANCO))
            self.campo_da_face.set_width_chars(16)
            nova_face.pack_start(self.campo_da_face, False, False, 0)
            botao_face = Gtk.Button(label=_(ROTULO_NOVA_FACE))
            botao_face.connect("clicked", self._ao_acrescentar_face)
            nova_face.pack_start(botao_face, False, False, 0)
            self._raiz.pack_start(nova_face, False, False, 0)

            espera = Gtk.Label(label=_(ESPERA_O_APLICAR))
            espera.set_xalign(0.0)
            espera.set_line_wrap(True)
            espera.set_max_width_chars(84)
            with contextlib.suppress(Exception):
                espera.get_style_context().add_class("dim-label")
            self._raiz.pack_start(espera, False, False, 0)

            rodape = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            fechar = Gtk.Button(label=_(ROTULO_FECHAR))
            fechar.connect("clicked", lambda _b: self.close())
            rodape.pack_end(fechar, False, False, 0)
            self._raiz.pack_start(rodape, False, False, 0)

        # -- desenho -------------------------------------------------------

        def _redesenhar(self) -> None:
            """Redesenha a lista e as faces a partir do rascunho."""
            self._remontar_a_bancada()
            self._desenhar_aparelhos()
            self._desenhar_faces()
            self._desenhar_confissao()
            self.botao_tirar.set_sensitive(
                bool(self._em_foco) and bool(self.logica.caminho_em(self._em_foco))
            )
            self.botao_extensao.set_sensitive(
                bool(self._em_foco) and self._em_foco.isdigit()
            )
            self.show_all()

        def _remontar_a_bancada(self) -> None:
            """A mesa do motor, refeita a cada gesto — o desenho mudou de forma.

            Refazer inteiro em vez de remendar: acrescentar uma entrada muda o
            pareamento da face toda (as irmãs saem de duas em duas), e um
            pareamento remendado seria a segunda verdade que este produto mais
            paga para matar.
            """
            try:
                self._bancada = bancada_do_rascunho(self.logica, self._censo)
            except Exception:
                # Rascunho que ainda não passa no esquema (uma face sem nome
                # recém-criada, por exemplo): o desenho continua na tela e o
                # juízo cala até o rascunho voltar a ser válido.
                logger.debug("o rascunho do mapa ainda não monta a mesa", exc_info=True)

        def _desenhar_confissao(self) -> None:
            """O que o desenho não diz, escrito — nunca calado."""
            for filho in self._caixa_confissao.get_children():
                self._caixa_confissao.remove(filho)
            self.confissao = confissao_do_desenho(self._bancada)
            if not self.confissao:
                return
            for texto in (_(CONFISSAO_ABERTURA), *self.confissao):
                linha = Gtk.Label(label=texto)
                linha.set_xalign(0.0)
                linha.set_line_wrap(True)
                linha.set_max_width_chars(84)
                with contextlib.suppress(Exception):
                    linha.get_style_context().add_class("dim-label")
                self._caixa_confissao.pack_start(linha, False, False, 0)

        def _desenhar_aparelhos(self) -> None:
            for filho in self._caixa_aparelhos.get_children():
                self._caixa_aparelhos.remove(filho)
            self.aparelhos = {}
            for aparelho in aparelhos_para_colocar(self._censo):
                botao = Gtk.ToggleButton(label=rotulo_do_aparelho(aparelho))
                botao.set_active(self.logica.escolhido == aparelho.nome_do_kernel)
                onde = self.logica.entrada_do_caminho(aparelho.nome_do_kernel)
                if onde:
                    botao.set_tooltip_text(
                        _("Você já colocou este aparelho na entrada {n}.").format(
                            n=onde
                        )
                    )
                botao.connect("clicked", self._ao_escolher, aparelho.nome_do_kernel)
                self._caixa_aparelhos.pack_start(botao, False, False, 0)
                self.aparelhos[aparelho.nome_do_kernel] = botao

        def _desenhar_faces(self) -> None:
            for filho in self._caixa_faces.get_children():
                self._caixa_faces.remove(filho)
            self.quadrados = {}
            self.vereditos = {}
            if not self.logica.faces:
                vazio = Gtk.Label(label=_(ROTULO_SEM_FACE))
                vazio.set_xalign(0.0)
                vazio.set_line_wrap(True)
                vazio.set_max_width_chars(60)
                self._caixa_faces.pack_start(vazio, False, False, 0)
                return
            for indice, face in enumerate(self.logica.faces):
                self._caixa_faces.pack_start(
                    self._desenhar_uma_face(indice, face), False, False, 0
                )

        def _desenhar_uma_face(self, indice: int, face: dict[str, Any]) -> Any:
            caixa = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
            cabecalho = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            nome = Gtk.Label(label=face["nome"])
            nome.set_xalign(0.0)
            cabecalho.pack_start(nome, False, False, 0)
            mais = Gtk.Button(label=_(ROTULO_NOVA_ENTRADA))
            mais.connect("clicked", self._ao_acrescentar_entrada, indice)
            cabecalho.pack_start(mais, False, False, 0)
            caixa.pack_start(cabecalho, False, False, 0)

            grade = Gtk.Grid()
            grade.set_column_spacing(4)
            grade.set_row_spacing(4)
            for posicao, numero in enumerate(face["portas"]):
                grade.attach(
                    self._quadrado(numero),
                    posicao % _COLUNAS,
                    posicao // _COLUNAS,
                    1,
                    1,
                )
            caixa.pack_start(grade, False, False, 0)
            return caixa

        def _quadrado(self, numero: str) -> Any:
            """Um quadrado da fileira, com as filhas por extensão dentro dele."""
            caixa = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
            caixa.pack_start(self._botao_de_entrada(numero), False, False, 0)
            for filha in self.logica.filhas_de(numero):
                caixa.pack_start(
                    self._botao_de_entrada(filha, extensao=True), False, False, 0
                )
            return caixa

        def _botao_de_entrada(self, numero: str, *, extensao: bool = False) -> Any:
            caminho = self.logica.caminho_em(numero)
            corpo = self._o_que_esta_em(caminho)
            if extensao:
                corpo = f"{corpo}\n{_(ROTULO_POR_EXTENSAO)}"
            veredito = self._veredito_em(numero)
            if veredito is not None:
                corpo = f"{corpo}\n{veredito.texto}"
            botao = Gtk.Button(label=f"{numero}\n{corpo}")
            with contextlib.suppress(Exception):
                botao.get_child().set_justify(Gtk.Justification.CENTER)
            botao.set_size_request(84, 56)
            dizeres: list[str] = []
            if extensao:
                dizeres.append(
                    _(
                        "Foi você quem disse que há uma extensão aqui. Nenhuma "
                        "leitura do sistema distingue isto de um aparelho na "
                        "própria entrada do hub."
                    )
                )
            elif caminho:
                dizeres.append(
                    _("O sistema enumera este aparelho como {c}.").format(c=caminho)
                )
            if veredito is not None and veredito.porque:
                dizeres.append(veredito.porque)
            if dizeres:
                botao.set_tooltip_text("\n".join(dizeres))
            botao.connect("clicked", self._ao_clicar_na_entrada, numero)
            self.quadrados[numero] = botao
            return botao

        def _veredito_em(self, numero: str) -> motor.Veredito | None:
            """O juízo do motor sobre esta entrada, guardado para quem olhar.

            Sem aparelho escolhido não há juízo a publicar: a pergunta que o
            motor responde é *"e para ESTE aparelho, aqui serve?"*, e sem a
            primeira metade do gesto ela não tem sujeito.
            """
            if not self.logica.escolhido:
                return None
            veredito = veredito_do_quadrado(
                self._bancada, numero, self.logica.escolhido
            )
            if veredito is not None:
                self.vereditos[numero] = veredito
            return veredito

        def _o_que_esta_em(self, caminho: str) -> str:
            if not caminho:
                return _(ROTULO_VAZIA)
            for aparelho in self._censo.conectados():
                if aparelho.nome_do_kernel == caminho:
                    return aparelho.especie
            # Declarado e ausente: ela colocou, o aparelho saiu. O mapa continua
            # valendo, e a tela diz o caminho em vez de fingir que está vazia.
            return caminho

        # -- gestos --------------------------------------------------------

        def _ao_escolher(self, _botao: Any, caminho: str) -> None:
            self.logica.escolher(caminho)
            self._redesenhar()

        def _ao_clicar_na_entrada(self, _botao: Any, numero: str) -> None:
            self._em_foco = numero
            if self.logica.escolhido:
                self.logica.colocar(numero)
                self._acumular()
            self._redesenhar()

        def _ao_tirar(self, _botao: Any) -> None:
            if self._em_foco and self.logica.tirar(self._em_foco):
                self._acumular()
            self._redesenhar()

        def _ao_acrescentar_extensao(self, _botao: Any) -> None:
            if self._em_foco and self.logica.acrescentar_extensao(self._em_foco):
                self._acumular()
            self._redesenhar()

        def _ao_acrescentar_entrada(self, _botao: Any, indice: int) -> None:
            if self.logica.acrescentar_entrada(indice):
                self._acumular()
            self._redesenhar()

        def _ao_acrescentar_face(self, _botao: Any) -> None:
            if self.logica.acrescentar_face(self.campo_da_face.get_text()):
                self.campo_da_face.set_text("")
                self._acumular()
            self._redesenhar()

        def _ao_fechar_a_janela(self, *_args: Any) -> bool:
            if self._ao_fechar is not None:
                with contextlib.suppress(Exception):
                    self._ao_fechar()
            return False

        def _acumular(self) -> None:
            acumular_no_rascunho(self._host, self.logica)

else:  # pragma: no cover - ambiente sem PyGObject

    class JanelaDoMapaDaMesa:  # type: ignore[no-redef]
        """Sem GTK não há janela — e quem chama não pode cair por isso."""

        def __init__(self, *_args: Any, **_kwargs: Any) -> None:
            raise RuntimeError("PyGObject não está disponível nesta máquina")


def acumular_no_rascunho(host: Any, logica: LogicaDoMapa) -> None:
    """Escreve o mapa inteiro em ``host._maquina_pendente``, sob a chave ``mapa``.

    **Substituição, não fusão**, e é o oposto do que as outras seções fazem —
    de propósito. Aquelas mandam pedaços de campos independentes; esta janela é
    a ÚNICA editora do mapa inteiro, e fundir faria uma entrada tirada
    ressuscitar dentro do próprio rascunho. As outras chaves de topo do
    rascunho (``mesa``, ``controles``, ``orcamento``) são preservadas intactas:
    a substituição alcança ``mapa`` e nada mais.

    Não chama ``machine.declare``: quem grava é o "Aplicar" do rodapé.
    """
    with contextlib.suppress(Exception):
        pendente = getattr(host, "_maquina_pendente", None)
        documento: dict[str, Any] = (
            dict(pendente) if isinstance(pendente, Mapping) else {}
        )
        documento["mapa"] = logica.como_documento()
        host._maquina_pendente = documento
    marcar = getattr(host, "_marcar_declaracao_por_aplicar", None)
    if marcar is not None:
        with contextlib.suppress(Exception):
            marcar()


__all__ = [
    "JanelaDoMapaDaMesa",
    "LogicaDoMapa",
    "acumular_no_rascunho",
    "aparelhos_para_colocar",
    "bancada_do_rascunho",
    "classe_do_escolhido",
    "confissao_do_desenho",
    "rotulo_do_aparelho",
    "veredito_do_quadrado",
]
