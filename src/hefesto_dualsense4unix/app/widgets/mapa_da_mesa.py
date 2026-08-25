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


class LogicaDoMapa:
    """O rascunho do gabinete e os quatro gestos que o mudam — sem GTK.

    Mora fora da janela de propósito: é aqui que a decisão dela vira dado, e
    dado que só existe dentro de um widget não se testa sem display. A janela
    chama estes métodos e redesenha; ela não guarda estado nenhum.
    """

    def __init__(self, mapa: MapaDaMesa) -> None:
        bruto = mapa.model_dump(mode="json")
        self.faces: list[dict[str, Any]] = [
            {"nome": face.get("nome", ""), "portas": list(face.get("portas", []))}
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
                {"nome": face["nome"], "portas": list(face["portas"])}
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
        self.faces.append({"nome": limpo, "portas": []})
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
            self._desenhar_aparelhos()
            self._desenhar_faces()
            self.botao_tirar.set_sensitive(
                bool(self._em_foco) and bool(self.logica.caminho_em(self._em_foco))
            )
            self.botao_extensao.set_sensitive(
                bool(self._em_foco) and self._em_foco.isdigit()
            )
            self.show_all()

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
            botao = Gtk.Button(label=f"{numero}\n{corpo}")
            with contextlib.suppress(Exception):
                botao.get_child().set_justify(Gtk.Justification.CENTER)
            botao.set_size_request(84, 56)
            if extensao:
                botao.set_tooltip_text(
                    _(
                        "Foi você quem disse que há uma extensão aqui. Nenhuma "
                        "leitura do sistema distingue isto de um aparelho na "
                        "própria entrada do hub."
                    )
                )
            elif caminho:
                botao.set_tooltip_text(
                    _("O sistema enumera este aparelho como {c}.").format(c=caminho)
                )
            botao.connect("clicked", self._ao_clicar_na_entrada, numero)
            self.quadrados[numero] = botao
            return botao

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
    "rotulo_do_aparelho",
]
