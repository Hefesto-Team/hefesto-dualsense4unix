"""A moldura de uma seção da aba Configurações — o molde único das cinco.

Por que existe um módulo só para isto: em 22/08/2026 a aba Configurações foi
posta lado a lado com as outras dez, e foi a única que leu como quebrada. As
dez seguem a mesma gramática visual desde sempre — cada seção é um
``Gtk.Frame`` com o título no canto, borda fina e conteúdo recuado
(``home_actions.py:1500``, ``:1712``, ``:1756``). A Configurações tinha cinco
``Gtk.Label`` soltos, colados na borda esquerda, sem moldura nenhuma.

O defeito não era de gosto: sem a moldura não há onde o conteúdo morar, e cada
seção nova ficaria à deriva na página. Esta função é a resposta, e é ela que
todas as cinco seções usam — nenhuma monta a própria caixa.

Os números vêm do molde da aba Início, medidos lá e copiados aqui: margem
interna 10 em cima e embaixo, 12 nos lados, e 8 de espaçamento entre filhos.
"""
from __future__ import annotations

import contextlib
import weakref
from collections.abc import Iterator
from typing import Any

from hefesto_dualsense4unix.utils.i18n import _

#: A classe do sublinhado pontilhado — rótulo que esconde uma explicação.
CLASSE_TEM_DICA = "hefesto-tem-dica"

#: A classe do `?` em círculo — cabeçalho de seção e casos de canto.
CLASSE_AJUDA = "hefesto-ajuda"

#: O texto do glifo de ajuda. Uma constante porque `marcar_afordancias` PROCURA
#: por ele para dar a marca ao `?` que `secao_mesa._subcabecalho` já monta à mão.
GLIFO_DE_AJUDA = "?"

#: Containers em que já se ligou o `add`. Weak porque a aba redesenha seções
#: inteiras (`_desenhar_medidores`, `_desenhar_radios`) e os containers velhos
#: têm de poder morrer. Guardar `id()` num `set` comum seria pior que não
#: guardar nada: o CPython reaproveita `id` de objeto coletado, e um container
#: novo herdaria o "já ligado" de um morto.
_JA_LIGADOS: weakref.WeakSet[Any] = weakref.WeakSet()

#: Margens internas do conteúdo de uma seção, em pixels. Cópia do molde da aba
#: Início (`home_actions.py:2085-2088`) — não são valores novos.
MARGEM_VERTICAL = 10
MARGEM_HORIZONTAL = 12
#: Espaçamento entre filhos diretos do conteúdo de uma seção.
ESPACAMENTO = 8

#: A frase que diz quando a escolha passa a valer, para as seções DIFERIDAS.
#:
#: ELA MORA AQUI, E NÃO EM CADA SEÇÃO, POR UM DEFEITO MEDIDO EM 22/08/2026.
#: A aba nasceu com TRÊS comportamentos de salvar e só UM deles escrito na tela:
#:
#: * "Orçamento" acumula no rascunho e DIZ que espera o "Aplicar";
#: * "Os controles" e "A mesa" acumulam no mesmo rascunho e não diziam nada;
#: * "A janela" grava NA HORA (`set_pref`, `gravar_correcao_de_ambiente`) e
#:   também não dizia nada — a única frase dela, *"vale na próxima vez que você
#:   abrir"*, fala de quando o tema é aplicado, não de se a escolha foi guardada.
#:
#: Três semânticas numa tela só, duas caladas. Quem clica e não vê nada
#: acontecer conclui uma de duas coisas, e as duas são ruins: que salvou quando
#: não salvou, ou que não salvou quando já salvou. Constante compartilhada
#: porque a mesma frase em três arquivos diverge na primeira revisão de texto.
QUANDO_VALE = 'A escolha passa a valer quando você clicar em "Aplicar", no rodapé.'

#: A contraparte, para a seção que grava NA HORA. Sem ela, "A janela" seria a
#: única sem resposta à pergunta "isto ficou guardado?".
#:
#: DESDE A LEX-2/LEX-3 (25/08/2026) ELA NÃO NASCE MAIS NA PÁGINA. Ela é uma
#: EXPLICAÇÃO — diria a mesma coisa com a seção intocada e com a seção toda
#: mexida —, e a regra do léxico manda explicação para o hover: hoje ela é a
#: dica dos rótulos das duas fileiras que gravam na hora ("Tamanho do texto:" e
#: "Ambiente:"). O lugar dela na página foi tomado pelo :data:`RECIBO_GUARDADO`,
#: que é ESTADO: nasce vazio e só aparece depois do clique.
#:
#: Por que a troca: como parágrafo estático a frase estava na tela ANTES do
#: clique, então não distinguia "cliquei" de "não cliquei" — que é exatamente a
#: pergunta que ela existe para responder. Ela relatou o sintoma pelo lado de
#: fora: *"janela ok, muito bom mas os botões não funcionam"*. Os handlers
#: estavam todos lá; o que faltava era recibo.
VALE_JA = 'A escolha fica guardada na hora — não espera o "Aplicar".'

#: O RECIBO: a frase curta que aparece DEPOIS do clique, em verde, ao lado da
#: fileira que recebeu o gesto. Some no clique seguinte em outra fileira.
#:
#: Curta de propósito. A frase longa continua existindo e explica o mecanismo
#: (:data:`VALE_JA`, agora no hover); o recibo não explica nada — ele CONFIRMA,
#: e confirmação que ocupa duas linhas deixa de ser confirmação e vira mais um
#: parágrafo de apoio, que é o defeito que esta leva está pagando.
#:
#: PROVISÓRIO — decisão dela (PROVA-DE-TELA-01). Texto novo de tela; entra na
#: lista de `docs/process/2026-08-25-AS-FRASES-DE-TELA-QUE-ESPERAM-ELA.md`.
RECIBO_GUARDADO = "Guardado."


def _descer(widget: Any) -> Iterator[Any]:
    """Todo widget da subárvore, o topo incluído."""
    from gi.repository import Gtk

    yield widget
    if isinstance(widget, Gtk.Container):
        for filho in widget.get_children():
            yield from _descer(filho)


def merece_sublinhado(widget: Any) -> bool:
    """Se este widget é um rótulo que esconde explicação e não se anuncia.

    O inventário da leva
    (`docs/process/sprints/2026-08-21-ABA-CONFIGURACOES/TOOLTIPS.md`) fixa duas
    marcas — sublinhado pontilhado para "rótulo que tem explicação", `?` para
    "cabeçalho de seção e casos de canto" — e a repartição entre elas é a última
    recusa desta lista: quem já tem `?` ao lado não ganha sublinhado. Escrita
    como pergunta sobre o IRMÃO, e não como lista de classes de cabeçalho, ela
    vale para o sub-cabeçalho que `secao_mesa` já tinha e para qualquer par
    rótulo+`?` que apareça depois, sem lista a manter.

    As quatro recusas, cada uma por um motivo diferente:

    * **não é `Gtk.Label`** — um `Gtk.Entry` já tem moldura de campo e um
      sublinhado dentro dela vira sujeira; um `Gtk.Button` já se anuncia.
    * **não tem dica** — não há o que anunciar.
    * **está dentro de um botão** — o rótulo interno de um `Gtk.Button`, de um
      `Gtk.CheckButton` ou de um segmento do `SegmentedSelector` (que é
      `Gtk.RadioButton` em modo toggle). Quem já parece clicável não precisa de
      marca, e o sublinhado dentro de um botão leria como link quebrado.
    * **já tem um `?` ao lado** — a marca dele é o `?`; as duas juntas seriam a
      mesma informação dita duas vezes.

    O próprio `?` cai fora pela última condição, e também porque
    `marcar_afordancias` o pega antes, pelo texto.
    """
    from gi.repository import Gtk

    if not isinstance(widget, Gtk.Label):
        return False
    if not (widget.get_tooltip_text() or "").strip():
        return False
    if widget.get_ancestor(Gtk.Button) is not None:
        return False
    if _e_glifo_de_ajuda(widget):
        return False
    return not _tem_ajuda_ao_lado(widget)


def _tem_ajuda_ao_lado(widget: Any) -> bool:
    """Se algum irmão deste widget é o `?` de ajuda."""
    pai = widget.get_parent()
    if pai is None:
        return False
    return any(
        irmao is not widget and _e_glifo_de_ajuda(irmao)
        for irmao in pai.get_children()
    )


def marcar_afordancias(raiz: Any) -> int:
    """Dá a marca visual a todo ponto de dica da subárvore. Devolve quantos.

    POR QUE ISTO É UMA VARREDURA, E NÃO UMA LINHA EM CADA SEÇÃO.

    Os pontos de dica nascem espalhados por cinco módulos de seção, e vários
    deles nascem DEPOIS da montagem: o exame reescreve as cinco linhas quando o
    worker responde, e a mesa redesenha medidores e rádios a cada releitura.
    Uma chamada por ponto teria de ser escrita em cada um desses lugares e
    lembrada em cada ponto novo — e o defeito que esta função cura é exatamente
    o de dica que ninguém lembrou de anunciar. A varredura não tem como
    esquecer: quem põe `set_tooltip_text` ganha a marca sem saber que ela
    existe.

    É idempotente — `add_class` numa classe que já está não faz nada.
    """
    marcados = 0
    for widget in _descer(raiz):
        with contextlib.suppress(Exception):
            if _e_glifo_de_ajuda(widget):
                widget.get_style_context().add_class(CLASSE_AJUDA)
                marcados += 1
            elif merece_sublinhado(widget):
                widget.get_style_context().add_class(CLASSE_TEM_DICA)
                marcados += 1
        _ligar_o_add(widget)
    return marcados


def _e_glifo_de_ajuda(widget: Any) -> bool:
    """O `?` de ajuda: rótulo cujo texto é só `?` e que carrega uma dica.

    Existe para CONVERGIR a gramática, não para criar outra. O
    `secao_mesa._subcabecalho` já montava um `?` à mão antes desta função, e
    ele é o desenho que a casa seguiu; o que faltava era a marca visual. Achá-lo
    pelo texto dá a ele o mesmo círculo que o `?` dos títulos de seção recebe,
    sem tocar em `secao_mesa.py`.

    Exigir a dica é o que separa o glifo de ajuda de um `?` que é CONTEÚDO — o
    `GLIFO.get(selo, "?")` do selo do exame, por exemplo, que é o desenho de
    "não sei" e não tem dica nenhuma.
    """
    from gi.repository import Gtk

    if not isinstance(widget, Gtk.Label):
        return False
    if (widget.get_text() or "").strip() != GLIFO_DE_AJUDA:
        return False
    return bool((widget.get_tooltip_text() or "").strip())


def _ligar_o_add(widget: Any) -> None:
    """Reagenda a varredura quando algo novo entra neste container.

    A dica costuma ser posta no widget ANTES de ele ser empacotado, mas nem
    sempre — `secao_mesa` monta a grade dos adaptadores e só depois põe a dica
    no cabeçalho da coluna. Por isso a revarredura vai para o `idle`: quando o
    GTK atende, a pilha que montou aquele pedaço já terminou e as dicas
    tardias já estão no lugar.
    """
    from gi.repository import GLib, Gtk

    if not isinstance(widget, Gtk.Container) or widget in _JA_LIGADOS:
        return
    _JA_LIGADOS.add(widget)

    def _ao_adicionar(container: Any, _filho: Any) -> None:
        ref = weakref.ref(container)

        def _revarrer() -> bool:
            vivo = ref()
            if vivo is not None:
                with contextlib.suppress(Exception):
                    marcar_afordancias(vivo)
            return False  # `True` faria o GTK repetir para sempre.

        GLib.idle_add(_revarrer)

    with contextlib.suppress(Exception):
        widget.connect("add", _ao_adicionar)


def moldura_de_secao(titulo: str, dica: str | None = None) -> tuple[Any, Any]:
    """Devolve ``(frame, caixa)`` — a moldura e a caixa onde a seção monta.

    O título vai num ``label_widget`` próprio, e não na propriedade ``label``
    do frame, por um motivo prático: assim a dica pousa no TÍTULO e não na
    moldura inteira. Dica em moldura inteira dispara ao passar o mouse em
    qualquer canto da seção, inclusive sobre um botão que tem dica própria — e
    a dica errada aparece por cima da certa.

    Quem chama empacota o ``frame`` na página e monta dentro do ``caixa``.
    """
    from gi.repository import Gtk

    frame = Gtk.Frame()
    rotulo = Gtk.Label(label=_(titulo))
    with contextlib.suppress(Exception):
        rotulo.get_style_context().add_class("hefesto-titulo-secao")
    if dica is not None:
        rotulo.set_tooltip_text(_(dica))
        # O título ganha o SUBLINHADO, e não o `?`. A decisão é de 23/08/2026 e
        # tem uma razão medida, não de gosto.
        #
        # O desenho original desta cura punha o `?` ao lado do título, com a
        # mesma gramática do `secao_mesa._subcabecalho` — caixa horizontal,
        # `spacing=4`, o `?` com a mesma dica. Para isso o `label_widget` do
        # frame tem de deixar de ser um `Gtk.Label` e virar um `Gtk.Box`, e é
        # aí que a conta não fecha: **`get_label_widget().get_text()` é como
        # SEIS arquivos de teste acham a seção pelo título**
        # (`test_config_selo_de_saude.py:71`, `test_config_a_janela_na_tela.py:262`,
        # `test_config_01_a_aba_nasce_vazia.py:369`, e mais três). Medido: 13
        # testes reprovaram com `'Box' object has no attribute 'get_text'`.
        # Pôr o `?` no texto do rótulo por markup dá no mesmo por outro caminho
        # — `get_text()` passaria a devolver "Orçamento ?" e as comparações com
        # o TÍTULO quebrariam igual.
        #
        # E o sublinhado não é um consolo: o título de seção É um "rótulo que
        # tem explicação", que é literalmente a linha do inventário para esta
        # marca. As duas marcas entregam a MESMA coisa aqui — dica no hover, sem
        # foco de teclado —, porque um `Gtk.Label` solto não recebe foco no
        # GTK3 de qualquer jeito. Escolher a que quebra treze testes de outras
        # frentes para entregar o mesmo seria pagar caro por nada.
        #
        # O `?` continua sendo a marca de sub-cabeçalho e de caso de canto, que
        # é onde ele já morava — e `marcar_afordancias` é quem lhe dá o círculo.
        with contextlib.suppress(Exception):
            rotulo.get_style_context().add_class(CLASSE_TEM_DICA)
    rotulo.show()
    frame.set_label_widget(rotulo)

    # A varredura roda no `map`, e não aqui, por dois motivos que apontam para o
    # mesmo lado: nesta linha o conteúdo da seção ainda não foi montado (quem
    # chama monta DEPOIS, dentro do `caixa`), e uma aba que o notebook mostra de
    # novo revarre sozinha o que tiver mudado enquanto estava escondida.
    with contextlib.suppress(Exception):
        frame.connect("map", lambda w: marcar_afordancias(w))

    # A seção NUNCA estica verticalmente, e a linha abaixo é o que garante isso.
    #
    # O GTK3 propaga `vexpand` de baixo para cima: um espaçador expansível lá no
    # fundo — o que ancora o seletor de jogador no rodapé de todo card, para os
    # cards terem a mesma altura — faz o `Gtk.Frame` inteiro pedir expansão, e a
    # página entrega a ele toda a folga que sobrar. Medido em 22/08/2026: a
    # seção "Os controles" saía com `compute_expand(VERTICAL) = True` e a aba
    # ficava com um vão vazio de mais de cem pixels embaixo dos cards.
    #
    # A folga vertical desta aba é da PÁGINA, que rola. Nenhuma seção cresce
    # para ocupá-la — se crescesse, a última seção afundaria para longe das
    # outras a cada janela mais alta.
    frame.set_vexpand(False)

    caixa = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=ESPACAMENTO)
    caixa.set_margin_top(MARGEM_VERTICAL)
    caixa.set_margin_bottom(MARGEM_VERTICAL)
    caixa.set_margin_start(MARGEM_HORIZONTAL)
    caixa.set_margin_end(MARGEM_HORIZONTAL)
    frame.add(caixa)
    return frame, caixa


def rotulo_de_apoio(texto: str, *, largura_max: int = 92) -> Any:
    """Rótulo explicativo no padrão da casa: alinhado à esquerda e com quebra.

    As quatro chamadas de ``set_`` são a regra 5 do roteiro da leva, e ela nasceu
    de um defeito medido: um título de 198 caracteres sem quebra pediu 1295px
    numa janela que abre com 1180 e não tem rolagem horizontal.

    ``xalign`` e ``halign`` NÃO são a mesma coisa, e faltar o segundo torna o
    ``max_width_chars`` inerte — medido em 23/08/2026, com a janela em 1868px:
    os onze rótulos de apoio da aba saíam com 1818px cada um, uma frase de ~215
    caracteres atravessando a janela inteira numa linha só. ``xalign`` alinha o
    TEXTO dentro do rótulo; ``halign`` é o que impede o RÓTULO de se esticar
    para a largura do pai. E ``max_width_chars`` limita apenas a largura
    NATURAL pedida — com a largura toda entregue pelo pai, ele nunca entra em
    ação.
    """
    from gi.repository import Gtk

    rotulo = Gtk.Label(label=_(texto))
    rotulo.set_xalign(0.0)
    rotulo.set_halign(Gtk.Align.START)
    rotulo.set_line_wrap(True)
    rotulo.set_max_width_chars(largura_max)
    with contextlib.suppress(Exception):
        rotulo.get_style_context().add_class("dim-label")
    return rotulo
