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
import time
from collections.abc import Callable
from typing import Any

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
gi.require_version("GdkPixbuf", "2.0")
gi.require_version("WebKit2", "4.1")

from gi.repository import GLib, Gtk, WebKit2  # noqa: E402

from hefesto_dualsense4unix.app import theme as tema  # noqa: E402
from hefesto_dualsense4unix.interface.folha_da_casa import FOLHA_DA_CASA  # noqa: E402

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

#: A FOLHA DE USUÁRIO DA CASA — reexportada, e o dono dela mora ao lado.
#:
#: Ela saiu deste módulo em 06/09/2026 e foi para
#: :mod:`hefesto_dualsense4unix.interface.folha_da_casa`, que não importa `gi`: a régua
#: da palavra precisa saber o que o produto ESCONDE (`.nota{display:none}`) e
#: uma régua sem tela não pode exigir PyGObject para perguntar. O porquê inteiro,
#: com o número que o instrumento errava, está no docstring de lá.
#:
#: O NOME FICA AQUI porque `docs/` e
#: `tests/unit/test_a_janela_estreita_nao_engole_o_desenho.py` citam
#: `ponte_da_tela.FOLHA_DA_CASA`, e mudar o endereço de um valor do produto por
#: causa de uma régua seria a régua mandando no produto.

#: QUANTO O PILOTO ESPERA ANTES DE RECARREGAR a página cujo processo web morreu.
#:
#: Não é zero porque o sinal chega DENTRO do handler do WebKit, e recarregar de
#: lá é reentrar no que acabou de cair. Um tique de laço basta.
MS_ANTES_DE_RECARREGAR = 250

#: O TETO DE RECARGAS SEGUIDAS, e ele é a diferença entre uma cura e um laço.
#:
#: Uma página que mate o processo web a cada carga viraria recarga infinita — e
#: um laço comendo CPU na máquina dela é pior que a tela congelada, porque não
#: para sozinho. Depois do teto o piloto **para e diz** em vez de insistir.
RECARGAS_SEGUIDAS = 3

#: Quanto tempo de página VIVA zera a conta acima. Um crash hoje e outro daqui a
#: uma hora não são "seguidos" — e tratá-los como tal deixaria a janela sem cura
#: no segundo dia de uso.
SEGUNDOS_PARA_ESQUECER_O_CRASH = 60.0

#: O nome do canal de mensagens. A página o pronuncia em
#: ``window.webkit.messageHandlers.<canal>.postMessage``.
CANAL_PADRAO = "hefesto"

#: O QUE O DESENHO PEDE, em pixels, e cada parcela tem dono no CSS:
#:
#:     .janela{width:1180px; height:var(--alt-janela)}   `interface/topo.html:147`
#:     --alt-janela:777px                                `interface/topo.html:567`
#:     body{padding:16px}                                `interface/topo.html:122`
#:
#: Logo o documento ocupa ``16+1180+16 = 1212`` por ``16+777+16 = 809``.
LARGURA_DO_DESENHO = 1212
ALTURA_DO_DESENHO = 809

#: A ``Gtk.HeaderBar`` desta janela, medida (04/09/2026, GTK3 + adw-gtk3-dark):
#: **46 px**. Ela fica FORA do miolo, então a janela na tela precisa pedir a
#: altura do desenho MAIS ela.
ALTURA_DA_BARRA = 46

#: O tamanho da janela na tela dela, e o da janela oculta. São diferentes de
#: propósito: a janela na tela carrega a ``HeaderBar``, a oculta
#: (``Gtk.OffscreenWindow``) não tem barra nenhuma.
#:
#: NÚMEROS ERRADOS, SUBSTITUÍDOS EM 04/09/2026. Eram ``(1180, 757)`` e
#: ``(1180, 900)``, e o comentário dizia que *"com barra de título o compositor
#: come a diferença"* — o que trocava a conta por uma esperança. A conta é esta:
#:
#: ===============  =========  ==========  ====================================
#: o que                largura    altura   sobra para a página
#: ===============  =========  ==========  ====================================
#: pedia antes           1180        757   757 menos 46 = **711** de miolo
#: o desenho pede        1212        809   —
#: faltava                 -32        -98   e o rodapé nascia abaixo da dobra
#: ===============  =========  ==========  ====================================
#:
#: Era este o *"tela do layout quebra direto"* que ela fotografou: 32 px cortados
#: na largura e 98 na altura, com ``.janela{overflow:hidden}`` — que **não corta
#: nem rola: some**. E a largura piora ao encolher, porque as colunas do miolo
#: são declaradas em px; por isso a janela também ganhou um MÍNIMO (o
#: ``set_size_request`` lá embaixo), sem o qual ela pode ser arrastada até
#: engolir o desenho em silêncio.
TAMANHO_NA_TELA = (LARGURA_DO_DESENHO, ALTURA_DO_DESENHO + ALTURA_DA_BARRA)
TAMANHO_OCULTA = (LARGURA_DO_DESENHO, ALTURA_DO_DESENHO)

#: A TRAVA DA TELA DELA — 02/09/2026, e ela nasceu de uma foto.
#:
#: Com treze frentes de agente em voo, oito cópias da MESMA janela nasceram
#: empilhadas na tela dela, em cima do que ela estava fazendo. Ela fotografou e
#: perguntou *"pq sempre abre essas inúmeras abas da mesma tela?"*.
#:
#: O `--oculta` do piloto sempre existiu e a regra da casa sempre foi usá-lo.
#: **Isso não bastou, e a razão é estrutural:** a regra vivia no PROMPT de quem
#: abre. Todo caminho novo — um teste, um script de ensaio, um visor antigo,
#: uma frente com pressa — nasce sem ela, e o custo cai na tela DELA, que é uma
#: só. Uma regra que depende de quem chama lembrar dela não é regra; é sorte.
#:
#: Então a trava mora AQUI, no dono ÚNICO da criação de janela desta casa, e é
#: do ambiente: quem exporta ``HEFESTO_SEM_JANELA`` não consegue abrir janela
#: visível nem querendo. O briefing de toda leva de agente a exporta.
#:
#: O QUE ELA NÃO FAZ, de propósito: ela não some com a janela do PRODUTO. Sem a
#: variável, o comportamento é exatamente o de antes — ela abre para quem a
#: chamou. A trava é para quem trabalha na máquina dela, não para quem usa.
SEM_JANELA_NA_TELA = "HEFESTO_SEM_JANELA"


def janela_proibida_na_tela() -> bool:
    """O ambiente proíbe abrir janela visível nesta máquina?

    Lê a cada chamada, e não uma vez na importação: um teste que exporta a
    variável no meio da sessão precisa ser obedecido, e um que a remove também.
    """
    import os

    return bool(os.environ.get(SEM_JANELA_NA_TELA, "").strip())


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
    :param ao_morrer_a_pagina: chamado com o motivo quando o processo web do
        WebKit termina. A janela **recarrega sozinha** de qualquer jeito; este
        gancho existe para quem quiser DIZER na tela que isso aconteceu.
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
        ao_morrer_a_pagina: Callable[[str], None] | None = None,
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
        self._ao_morrer_a_pagina = ao_morrer_a_pagina
        #: O motivo da morte da carga, ou ``None``. Ver :meth:`_morrer`.
        self.morreu: str | None = None
        self.oculta = oculta
        #: A guarda vale só na PRIMEIRA carga. Depois disso, sair da aba pausa.
        self.primeira_carga = True
        #: Se a página à vista AGORA é a aba desta janela.
        self.na_aba = False
        #: Toda morte do processo web, com o motivo, na ordem. Lista vazia é a
        #: única forma honesta de dizer "não morreu nenhuma vez" — ausência de
        #: notícia lida como sucesso é o defeito que esta casa nomeou em 22/08.
        self.mortes: list[str] = []
        #: Quantas recargas seguidas já foram gastas, e desde quando esta página
        #: está viva. Ver :data:`RECARGAS_SEGUIDAS`.
        self.recargas = 0
        self._viva_desde = time.monotonic()

        self.ponte = PonteDaTela(
            canal=canal, ao_receber=ao_receber, ao_recusar=ao_recusar, folha=folha
        )
        self.view = self.ponte.view
        self.view.connect("load-changed", self._carregou)
        # A QUINTA ARMADILHA, e ela é a que ela FOTOGRAFOU. Ver `_morreu_a_pagina`.
        self.view.connect("web-process-terminated", self._morreu_a_pagina)

        # A TRAVA DA TELA DELA vem ANTES do `if`, e é de propósito: ela não
        # avisa e segue, ela DECIDE. Ver `SEM_JANELA_NA_TELA`, no topo.
        if not oculta and janela_proibida_na_tela():
            print(
                f"[janela] {SEM_JANELA_NA_TELA} está no ambiente: abrindo "
                f"OCULTA em vez de na tela dela ({titulo}).",
                file=sys.stderr,
            )
            oculta = True
            self.oculta = True

        # O TEMA DELA, ANTES DE QUALQUER WIDGET NASCER. O popup de um `<select>`
        # é desenhado pelo WebKit FORA da página: nem o CSS do autor nem
        # `color-scheme: dark` o alcançam, e `prefer-dark` também não — medido
        # nos três, WebKitGTK 2.52.6. Quem decide a cor dele é o `gtk-theme-name`
        # do processo, e sob o `GDK_BACKEND=x11` que o `.desktop` força esse nome
        # se perde: o GTK espera um XSettings que o COSMIC não tem. Sem estas
        # duas linhas ela abre a aba Gatilhos, clica num efeito pronto, e o menu
        # nasce BRANCO com a linha azul no meio da interface escura — fotografado
        # por ela em 04/09/2026. A razão inteira está em `theme.adotar_o_tema_da_sessao`.
        tema.adotar_o_tema_da_sessao()
        tema.pedir_a_variante_escura()
        # OS BOTÕES DO LADO DO SISTEMA — queixa 2 dela, 04/09/2026, e a única
        # das quinze que tinha ficado aberta. Vem junto do tema porque é a mesma
        # forma de cura: o produto se ajusta à sessão DENTRO do próprio
        # processo, em vez de exigir que a sessão se ajuste a ele. A razão de
        # não ser uma leitura do `button-layout` — e a medição que derrubou essa
        # premissa — está em `theme.barra_que_o_sistema_usa`.
        tema.adotar_a_barra_da_sessao()

        if oculta:
            self.janela: Any = Gtk.OffscreenWindow()
            self.janela.set_default_size(*(tamanho or TAMANHO_OCULTA))
        else:
            self.janela = Gtk.Window(title=f"{titulo} — {subtitulo}" if subtitulo else titulo)
            self.janela.set_default_size(*(tamanho or TAMANHO_NA_TELA))
            # O PISO DA JANELA, e ele é o desenho inteiro. `set_size_request` é
            # MÍNIMO, nunca máximo (armadilha que o COMO-OLHAR-A-TELA já lista):
            # a janela continua crescendo, e deixa de encolher até engolir o que
            # ela veio ver.
            #
            # SEM ELE O CSS É A ÚNICA DEFESA, E ELE PERDE: `.janela` tem
            # `max-width:100%` com `overflow:hidden` e colunas em px, então
            # abaixo de 1212 o conteúdo não corta nem rola — **some**. Nos 940 px
            # da foto dela, 272 px do desenho desapareciam sem afordância.
            #
            # ESTA LINHA ERA UMA PROMESSA POR ESCRITO E NÃO EXISTIA. O comentário
            # de `TAMANHO_NA_TELA` dizia *"por isso a janela também ganhou um
            # MÍNIMO (o `set_size_request` lá embaixo)"* e `grep` no arquivo
            # devolvia só aquela frase — achado da régua de janela estreita, em
            # 04/09/2026, no mesmo dia em que a frase foi escrita. Comentário que
            # descreve código inexistente é pior que comentário nenhum: ele faz a
            # próxima pessoa parar de procurar.
            self.janela.set_size_request(LARGURA_DO_DESENHO, ALTURA_DO_DESENHO + ALTURA_DA_BARRA)
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
            # A CONTA DE RECARGAS ZERA QUANDO UMA PÁGINA CONFIRMA, e o relógio
            # recomeça: é o que separa "morreu três vezes seguidas" de "morreu
            # três vezes no dia". Ver `SEGUNDOS_PARA_ESQUECER_O_CRASH`.
            self._viva_desde = time.monotonic()
            self._ao_carregar()

        self.ponte.perguntar("document.title", respondeu)

    # -- a página que morreu -----------------------------------------------
    def _morreu_a_pagina(self, _view: Any, motivo: Any) -> None:
        """O processo web do WebKit terminou. A janela RECARREGA — e diz.

        **A QUINTA ARMADILHA DO WebKit2 4.1**, e é a que ela fotografou em
        04/09/2026 (*"interface quebrou sozinha oxi"*): quando o
        ``WebKitWebProcess`` morre, a ``WebView`` **não avisa a quem a usa e não
        volta sozinha**. Ela fica com o último quadro na tela e todo JavaScript
        passa a falhar, para sempre, com a mesma linha.

        MEDIDO nesta máquina em 04/09/2026, matando o processo filho por PID
        conferido com ``ps -o pid,ppid,cmd`` (nunca por padrão de nome — um
        ``pkill -f`` já derrubou o compositor dela no mesmo dia):

        =========================================  =============================
        depois da morte do ``WebKitWebProcess``    o que a janela faz
        =========================================  =============================
        sem esta cura                              ``evaluate_javascript`` devolve
                                                   ``WebKitJavascriptError:
                                                   Unsupported result type (601)``
                                                   em **todo** tique, para sempre;
                                                   o piloto imprime "a pintura
                                                   falhou" a cada 100 ms e a tela
                                                   fica congelada
        com esta cura (``view.reload()``)          a página volta inteira —
                                                   ``backgroundColor
                                                   rgb(17, 18, 26)``, ``padding
                                                   16px``, as 64.910 letras de
                                                   estilo, e o bootstrap
                                                   reinstalado sozinho
        =========================================  =============================

        **E O SINAL EXISTIA O TEMPO TODO:** ``web-process-terminated`` dispara
        com ``crashed``. Ninguém o ouvia — a janela tinha o aviso na mão e não o
        lia, que é a forma de defeito que esta casa chama de *a casa sabe e o
        produto não faz*.

        DUAS HIPÓTESES DA SPRINT CAÍRAM AQUI, e ficam escritas para ninguém as
        remedir: matar o ``WebKitNetworkProcess`` e recarregar **não** deixa a
        página nua (a folha é inline; o ``<link>`` do Google só traz fonte), e as
        dez páginas publicadas não foram reescritas no disco no dia da foto.
        """
        nome = getattr(motivo, "value_nick", None) or str(motivo)
        self.mortes.append(str(nome))
        self.na_aba = False
        print(f"[página morreu] o processo web do WebKit terminou ({nome})",
              file=sys.stderr)
        if self._ao_morrer_a_pagina is not None:
            self._ao_morrer_a_pagina(str(nome))
        if time.monotonic() - self._viva_desde >= SEGUNDOS_PARA_ESQUECER_O_CRASH:
            self.recargas = 0
        if self.recargas >= RECARGAS_SEGUIDAS:
            print(f"[página morreu] {self.recargas} recargas seguidas sem a "
                  f"página parar de pé — não recarrego de novo.", file=sys.stderr)
            return
        self.recargas += 1
        self._viva_desde = time.monotonic()
        # O TIQUE DE LAÇO ANTES DE RECARREGAR: o sinal chega DENTRO do handler
        # do WebKit, e recarregar de lá é reentrar no que acabou de cair.
        GLib.timeout_add(MS_ANTES_DE_RECARREGAR, self._recarregar)

    def _recarregar(self) -> bool:
        """Traz a página de volta. ``load_uri`` quando nunca houve carga boa.

        ``reload()`` repete a URI à vista, que é o certo: ela pode ter navegado
        para outra aba antes do crash, e recarregar a PRIMEIRA a tiraria de onde
        ela estava. Só quando nenhuma carga confirmou é que não há o que repetir
        — aí vale o arquivo com que a janela nasceu.
        """
        print(f"[página morreu] recarregando ({self.recargas}/{RECARGAS_SEGUIDAS})",
              file=sys.stderr)
        if self.primeira_carga:
            self.view.load_uri(self.arquivo.as_uri())
        else:
            self.view.reload()
        return False

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
        # O MOTIVO FICA GUARDADO, e é o que faltava para uma régua não mentir.
        # MEDIDO EM 04/09/2026: `hefesto_vivo --prova-de-mockup` imprimia
        # `ERRO DE CARGA` e saía **rc=0 sem medir nada** — verde sobre o vazio,
        # que é a família de defeito que esta casa persegue acima de todas.
        # Quem constrói a janela decide o que fazer com isto; a janela só
        # garante que a informação exista.
        self.morreu = motivo
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
