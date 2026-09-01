"""ponte_da_tela — a janela, as duas pontes e a guarda de carga. UMA VEZ, para as dez abas.

A interface nova é o mockup aprovado rodando num ``WebKit2.WebView`` dentro de
uma janela GTK3 (``D-A-INTERFACE-NOVA-E-O-MOCKUP-DENTRO-DE-UMA-JANELA-GTK``).
Até 29/08/2026 tudo isso morava DENTRO do piloto da aba Controles
(``src/hefesto_dualsense4unix/interface/controles_vivos.py``), que era ao mesmo tempo a
janela, a ponte, a pintura e a aba. **Nove cópias disso seria o defeito que esta
casa mais paga: o mesmo valor com vários donos.** Este arquivo é a parte que não
é de aba nenhuma, tirada de lá e posta onde as dez alcançam.

Ele **não sabe** o que é um controle, uma bateria ou um giroscópio. Quem sabe é
quem chama.

    from hefesto_dualsense4unix.gui.ponte_da_tela import JanelaDaAba

    janela = JanelaDaAba(
        arquivo=pathlib.Path("…/02-controles.html"),
        titulo_esperado="Hefesto — aba CONTROLES",
        ao_carregar=instalar_a_pintura,   # a página é a certa: pode começar
        ao_receber=tratar_o_gesto,        # tela → Python, já em JSON
    )
    janela.ponte.dizer("HEF.pinta", pacote)   # Python → tela, UMA chamada

POR QUE ELE MORA EM ``src/`` E NÃO EM ``src/hefesto_dualsense4unix/interface/`` NEM EM ``scripts/``
--------------------------------------------------------------------------------------
``novo-layout/`` **saiu do ``.gitignore`` em 30/08/2026**, a pedido dela
(*"pode tirar do gitignore então"*): a pasta guarda os desenhos que ela faz, uma
leva sobrescreveu um SVG recém-desenhado e não havia backup. Isso derruba metade
do argumento original desta seção — a de que nada de lá viaja para a árvore de um
agente —, mas **não muda o destino**, e por duas razões que sobreviveram:

``scripts/`` também resolveria o viajar, e é onde a RÉGUA ficou — mas a régua é
instrumento e isto é **produto**: as nove abas restantes vão rodar em cima deste
arquivo. E ``scripts/`` não é medido por portão nenhum de código
(``ruff check src/ tests/`` e ``mypy src/hefesto_dualsense4unix`` são os comandos
exatos do CI, e nenhum dos dois alcança ``scripts/``). Encanamento de produto
sem lint e sem tipo é dívida com juros.

E o destino já estava DECIDIDO por escrito antes desta leva: a sprint
``MIGRA-CONTROLES-03`` declara ``cria: src/hefesto_dualsense4unix/gui/ponte_da_tela.py``
e fecha com *"não escreva uma segunda ponte"*. Escrever noutro lugar criaria o
segundo dono no dia em que aquela sprint rodasse.

AS QUATRO ARMADILHAS DO WebKit2 4.1, TODAS JÁ PAGAS
---------------------------------------------------
Estão em :data:`AS_QUATRO_ARMADILHAS`, em código e não só em prosa, porque
quem escrever a décima aba lê daqui. O resumo:

1. ``FINISHED`` dispara DEPOIS de um ``load-failed``, com o URI ORIGINAL — e
   host recusando conexão não dispara ``load-failed`` nenhum, só troca o URI
   para ``about:blank``, calado. Nem o evento nem o URI bastam: quem confirma a
   carga é a PÁGINA, perguntada por JS (:meth:`JanelaDaAba._confirmar_a_pagina`).
2. ``get_title()`` dentro do handler de ``FINISHED`` devolve vazio — o título
   chega depois. Aqui ninguém chama ``get_title()``: pergunta-se à página.
3. ``evaluate_javascript`` não devolve Promise (``Unsupported result type
   (601)``): toda resposta assíncrona da tela volta pelo ``postMessage``.
4. Na série 4.1 o handler de ``script-message-received`` leva **um** argumento
   (na 6.0 leva dois).

E os quatro pinos de ``gi.require_version`` são obrigatórios, com o ``Gdk``
DEPOIS do ``Gtk``.

A GUARDA QUE NÃO MATA A JANELA
------------------------------
MEDIDO EM 29/08/2026, na primeira vez que ela abriu o piloto: a janela fechou
sozinha depois de ~12 s — o tempo de ela clicar em "Conexões" na tira. A tira do
mockup é ``<a href="08-conexoes.html">``, ou seja ela NAVEGA de verdade, o
``load-changed`` dispara de novo, e a guarda de carga — que existe para pegar
carga FALHA — leu navegação como erro fatal.

A guarda vale só na **primeira** carga, que é onde ela protege. Depois disso,
sair da aba não mata nada: chama ``ao_sair_da_aba`` e a pintura pausa.
"""
from __future__ import annotations

import json
import pathlib
import sys
from collections.abc import Callable
from typing import Any

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
gi.require_version("GdkPixbuf", "2.0")
gi.require_version("WebKit2", "4.1")

from gi.repository import GLib, Gtk, WebKit2  # noqa: E402

#: As quatro armadilhas, em código. Cada uma custou uma sessão desta casa, e a
#: forma de não as redescobrir é elas viajarem com o módulo que as paga — não
#: numa página de documentação que ninguém abre no meio de um transplante.
AS_QUATRO_ARMADILHAS: tuple[str, ...] = (
    "FINISHED dispara DEPOIS de um load-failed, com o URI ORIGINAL: arquivo "
    "inexistente dá DOIS FINISHED e o segundo é indistinguível de sucesso. E "
    "host recusando conexão não dispara load-failed nenhum — só troca o URI "
    "para about:blank, calado. Quem confirma a carga é a PÁGINA, perguntada "
    "por JS, e custa 0,04 ms",
    "get_title() dentro do handler de FINISHED devolve vazio — o título chega "
    "depois. Este módulo não chama get_title() em lugar nenhum",
    "evaluate_javascript não devolve Promise (Unsupported result type 601): "
    "toda resposta assíncrona da tela volta pelo postMessage, nunca pelo "
    "retorno da avaliação",
    "na série 4.1 o handler de script-message-received leva UM argumento; na "
    "6.0 leva dois. Escrever a forma da 6.0 aqui faz o gesto sumir calado",
)

#: A folha de usuário da casa, e ela é do MÓDULO — não de uma aba.
#:
#: ``.nota{display:none}`` tira os bilhetes de projeto que o mockup carrega para
#: quem o lê no navegador; eles não são produto.
#:
#: ``select{appearance:none}`` é a cura sem a qual o WebKitGTK ignora as cores
#: do autor e desenha a caixa BRANCA do tema do sistema. São **117** ``<select>``
#: nas dez abas, e a aba Controles não tem nenhum: aqui a cura não se prova pelo
#: olho, ela viaja no módulo para as outras nove.
FOLHA_DA_CASA = ".nota{display:none !important}select{appearance:none;-webkit-appearance:none}"

#: O nome do canal de mensagens. A página o pronuncia em
#: ``window.webkit.messageHandlers.<canal>.postMessage``.
CANAL_PADRAO = "hefesto"

#: O tamanho da janela na tela dela, e o da janela oculta. São diferentes de
#: propósito: com barra de título o compositor come a diferença, e uma foto
#: precisa da altura inteira do desenho.
TAMANHO_NA_TELA = (1180, 757)
TAMANHO_OCULTA = (1180, 900)


def literal_js(valor: object) -> str:
    """Um valor Python virando literal JavaScript, por JSON e só por JSON.

    **O valor nunca é interpolado como texto.** Um nome de plástico com
    apóstrofo — e o CSV desta casa tem 28 modelos — quebraria o script inteiro,
    calado. ``json.dumps`` escapa a aspa, a barra e o caractere de controle.

    E o ``ensure_ascii`` fica no padrão (ligado) DE PROPÓSITO: ele escapa todo
    não-ASCII para ``\\uXXXX``, o que também mata U+2028/U+2029 — que são texto
    legítimo dentro de uma string JSON e **terminador de linha** dentro de um
    script JavaScript. Desligá-lo para "economizar bytes" reabre esse buraco.
    """
    return json.dumps(valor)


class PonteDaTela:
    """As duas pontes, e nada mais: Python → página e página → Python.

    São as **31 linhas medidas** que decidiram a tecnologia da interface — contra
    as 500 a 700 linhas **por aba** da rota que emitia GTK à mão. Elas nascem uma
    vez e as dez abas as herdam.

    :param canal: nome do ``messageHandler``.
    :param ao_receber: chamado com o objeto JSON de cada gesto que a página
        mandar. Recebe ``dict`` — mensagem que não for objeto JSON é RECUSADA
        antes de chegar aqui.
    :param ao_recusar: chamado com o motivo e o texto cru de cada mensagem
        malformada. Se for ``None``, a recusa ainda é registrada em
        :attr:`recusas` e impressa no ``stderr`` — **nunca engolida**.
    :param folha: a folha de usuário; ``None`` para nenhuma.
    """

    def __init__(
        self,
        *,
        canal: str = CANAL_PADRAO,
        ao_receber: Callable[[dict[str, Any]], None] | None = None,
        ao_recusar: Callable[[str, str], None] | None = None,
        folha: str | None = FOLHA_DA_CASA,
    ) -> None:
        self.canal = canal
        self._ao_receber = ao_receber
        self._ao_recusar = ao_recusar
        #: Toda mensagem malformada, com o motivo. Uma lista vazia é a única
        #: forma honesta de dizer "nenhuma foi recusada"; ausência de notícia
        #: sendo lida como sucesso é o defeito que esta casa nomeou em 22/08.
        self.recusas: list[tuple[str, str]] = []
        #: Quantas chamadas atravessaram a fronteira Python → página. É a régua
        #: do contrato "uma chamada por TIQUE, não por valor".
        self.chamadas = 0

        ucm = WebKit2.UserContentManager()
        # ARMADILHA 4: na série 4.1 isto leva UM argumento. A forma da 6.0
        # (dois) não levanta erro aqui — ela faz o gesto nunca chegar.
        ucm.register_script_message_handler(canal)
        ucm.connect(f"script-message-received::{canal}", self._da_tela)
        if folha:
            ucm.add_style_sheet(
                WebKit2.UserStyleSheet(
                    folha,
                    WebKit2.UserContentInjectedFrames.TOP_FRAME,
                    WebKit2.UserStyleLevel.USER,
                    None,
                    None,
                )
            )
        self.ucm = ucm
        self.view = WebKit2.WebView.new_with_user_content_manager(ucm)

    # -- Python → página ---------------------------------------------------
    def dizer(self, funcao: str, *argumentos: object) -> None:
        """Chama uma função da página com os argumentos serializados em JSON.

        UMA chamada por TIQUE, não por valor: quem chama monta um objeto com
        tudo o que mudou e a página distribui. Com 29 valores por controle e
        quatro controles na mesa, uma chamada por valor seriam 1.160 travessias
        de fronteira por segundo.
        """
        crus = ", ".join(literal_js(a) for a in argumentos)
        self.rodar(f"{funcao}({crus})")

    def rodar(self, script: str) -> None:
        """JavaScript solto, sem esperar resposta — instalar o bootstrap, mexer
        no DOM. Para ter a resposta de volta, :meth:`perguntar`."""
        self.chamadas += 1
        self.view.evaluate_javascript(script, -1, None, None, None, None, None)

    def perguntar(
        self,
        js: str,
        resposta: Callable[[str | None, Exception | None], None],
    ) -> None:
        """Avalia o ``js`` e devolve o resultado como texto ao callback.

        ARMADILHA 3: ``evaluate_javascript`` **não** devolve Promise. O que
        atravessa aqui é o valor síncrono da expressão; qualquer coisa que
        dependa de tempo volta pelo ``postMessage``, isto é, pela outra ponte.

        O callback recebe ``(valor, None)`` ou ``(None, erro)``. As duas pernas
        existem porque a página que não responde é justamente o caso da guarda
        de carga, e engoli-lo seria o instrumento mentindo.
        """
        self.chamadas += 1

        def terminou(view: Any, res: Any, _u: Any = None) -> None:
            try:
                valor = view.evaluate_javascript_finish(res)
            except Exception as erro:  # a exceção É a resposta desta ponte
                resposta(None, erro)
                return
            resposta(None if valor is None else valor.to_string(), None)

        self.view.evaluate_javascript(js, -1, None, None, None, terminou, None)

    # -- página → Python ---------------------------------------------------
    def _da_tela(self, _ucm: Any, resultado: Any) -> None:
        """ARMADILHA 4: na 4.1 este handler leva UM argumento além do ``ucm``.

        Toda mensagem chega como TEXTO e é lida como JSON. O que não casar com a
        forma declarada é **recusado com motivo**, nunca engolido — e nunca
        avaliado: aqui não há ``eval`` nem despacho por nome vindo de fora.
        """
        valor = resultado.get_js_value() if hasattr(resultado, "get_js_value") else resultado
        try:
            bruto = valor.to_string()
        except Exception as erro:  # defesa: a mensagem vem de fora
            self._recusar("a mensagem não virou texto", repr(erro))
            return
        self.receber_texto(bruto)

    def receber_texto(self, bruto: str) -> None:
        """A metade da ponte que NÃO precisa de WebView: o texto vira gesto.

        Está separada de :meth:`_da_tela` para que uma régua possa alimentar a
        ponte sem montar janela — e para que a régua meça a recusa DE VERDADE,
        em vez de uma cópia dela escrita no teste.
        """
        try:
            objeto = json.loads(bruto)
        except (TypeError, ValueError) as erro:
            self._recusar(f"não é JSON ({erro})", str(bruto))
            return
        if not isinstance(objeto, dict):
            self._recusar(f"JSON válido, mas não é objeto (veio {type(objeto).__name__})", bruto)
            return
        if self._ao_receber is not None:
            self._ao_receber(objeto)

    def _recusar(self, motivo: str, bruto: str) -> None:
        self.recusas.append((motivo, bruto[:200]))
        if self._ao_recusar is not None:
            self._ao_recusar(motivo, bruto)
        else:
            print(f"ponte: gesto RECUSADO — {motivo}: {bruto[:200]!r}", file=sys.stderr)


class JanelaDaAba:
    """A janela que hospeda uma aba do mockup, com a guarda de carga que não mata.

    :param arquivo: o HTML da aba, no disco.
    :param titulo_esperado: o que a PÁGINA tem de dizer que é. É o único sinal
        que sobrevive às armadilhas 1 e 2.
    :param ao_carregar: chamado quando a página confirmou ser a certa. É onde
        quem chama instala a sua ponte de pintura e liga o tique.
    :param ao_receber: repassado à :class:`PonteDaTela`.
    :param ao_sair_da_aba: chamado com o título da página nova quando ela navega
        para FORA da aba (clicou na tira). ``None`` → só imprime. **Nunca mata a
        janela**: isso é navegação legítima, não erro.
    :param ao_falhar: chamado com o motivo quando a PRIMEIRA carga falha.
        ``None`` → imprime no ``stderr`` e ``Gtk.main_quit()``.
    :param oculta: ``Gtk.OffscreenWindow`` — nada aparece na tela dela.
    """

    def __init__(
        self,
        *,
        arquivo: pathlib.Path,
        titulo_esperado: str,
        ao_carregar: Callable[[], None],
        ao_receber: Callable[[dict[str, Any]], None] | None = None,
        ao_recusar: Callable[[str, str], None] | None = None,
        ao_sair_da_aba: Callable[[str], None] | None = None,
        ao_falhar: Callable[[str], None] | None = None,
        oculta: bool = False,
        titulo: str = "Hefesto",
        subtitulo: str = "",
        canal: str = CANAL_PADRAO,
        folha: str | None = FOLHA_DA_CASA,
        tamanho: tuple[int, int] | None = None,
    ) -> None:
        self.arquivo = arquivo
        self.titulo_esperado = titulo_esperado
        self._ao_carregar = ao_carregar
        self._ao_sair_da_aba = ao_sair_da_aba
        self._ao_falhar = ao_falhar
        self.oculta = oculta
        #: A guarda vale só na PRIMEIRA carga. Depois disso, sair da aba pausa.
        self.primeira_carga = True
        #: Se a página à vista AGORA é a aba desta janela.
        self.na_aba = False

        self.ponte = PonteDaTela(
            canal=canal, ao_receber=ao_receber, ao_recusar=ao_recusar, folha=folha
        )
        self.view = self.ponte.view
        self.view.connect("load-changed", self._carregou)

        if oculta:
            self.janela: Any = Gtk.OffscreenWindow()
            self.janela.set_default_size(*(tamanho or TAMANHO_OCULTA))
        else:
            self.janela = Gtk.Window(title=f"{titulo} — {subtitulo}" if subtitulo else titulo)
            self.janela.set_default_size(*(tamanho or TAMANHO_NA_TELA))
            # SEM A HeaderBar OS BOTÕES SAEM DO LADO ERRADO NO COSMIC. Não é
            # enfeite: a barra de título do sistema não segue a decoração do
            # tema, e a janela nasce com fechar/minimizar espelhados.
            barra = Gtk.HeaderBar()
            barra.set_show_close_button(True)
            barra.set_title(titulo)
            if subtitulo:
                barra.set_subtitle(subtitulo)
            self.janela.set_titlebar(barra)
            self.janela.connect("destroy", Gtk.main_quit)
        self.janela.add(self.view)
        self.janela.show_all()
        self.view.load_uri(arquivo.as_uri())

    # -- a guarda de carga -------------------------------------------------
    def _carregou(self, _view: Any, evento: Any) -> None:
        if evento != WebKit2.LoadEvent.FINISHED:
            return
        self._confirmar_a_pagina()

    def _confirmar_a_pagina(self) -> None:
        """Quem diz que a carga deu certo é a PÁGINA, não o evento nem o URI.

        ARMADILHAS 1 e 2, as duas de uma vez: o evento mente (``FINISHED`` vem
        depois de falhar, com o URI original) e ``get_title()`` no handler
        devolve vazio. Perguntar à página é o único sinal que sobrevive aos
        dois, e custa 0,04 ms.
        """

        def respondeu(titulo: str | None, erro: Exception | None) -> None:
            if erro is not None:
                self._morrer(f"a página não respondeu: {erro}")
                return
            if self.titulo_esperado not in (titulo or ""):
                if self.primeira_carga:
                    self._morrer(f"carregou OUTRA página: título {titulo!r}")
                else:
                    self._saiu_da_aba(titulo or "(sem título)")
                return
            self.primeira_carga = False
            self.na_aba = True
            self._ao_carregar()

        self.ponte.perguntar("document.title", respondeu)

    def _saiu_da_aba(self, titulo: str) -> None:
        """Ela clicou na tira. Isso é LEGÍTIMO, e matar a janela por isso é bug."""
        if not self.na_aba:
            return
        self.na_aba = False
        if self._ao_sair_da_aba is not None:
            self._ao_sair_da_aba(titulo)
        else:
            print(f"[fora da aba] {titulo} — o mockup estático; a pintura pausou.")

    def _morrer(self, motivo: str) -> None:
        if self._ao_falhar is not None:
            self._ao_falhar(motivo)
            return
        print(f"ERRO DE CARGA: {motivo}", file=sys.stderr)
        Gtk.main_quit()

    # -- conveniências -----------------------------------------------------
    def agendar_saida(self, segundos: float, antes: Callable[[], None] | None = None) -> None:
        """Fecha a janela daqui a N segundos. ``0`` (ou menos) não agenda nada."""
        if segundos <= 0:
            return

        def sair() -> bool:
            if antes is not None:
                antes()
            Gtk.main_quit()
            return False

        GLib.timeout_add(int(segundos * 1000), sair)

    def fotografar(self, destino: str) -> bool:
        """O PNG da janela oculta. Devolve se a foto saiu.

        Só a ``Gtk.OffscreenWindow`` tem ``get_pixbuf``; fotografar a janela na
        tela dela exigiria capturar a TELA dela, que é o que esta casa não faz
        por conta própria.
        """
        if not isinstance(self.janela, Gtk.OffscreenWindow):
            print("foto: só a janela OCULTA se fotografa (use --oculta)", file=sys.stderr)
            return False
        pix = self.janela.get_pixbuf()
        if pix is None:
            print("foto: a janela oculta ainda não tem pixbuf", file=sys.stderr)
            return False
        pix.savev(destino, "png", [], [])
        print(f"foto: {destino}")
        return True
