"""LARGURA-01/E2, E4 e E5 — *"usarmos a largura igual nas demais abas"*.

A frase é dela, olhando a aba Status entregue pela SOM-01 com a janela
maximizada em 1920. Esta bancada cobra as três entregas que a sprint mediu:

* **E2** — o miolo do frame "Estado". O teto da SOM-01 parava no frame: dentro
  dele, a coluna de valores recebia 1242px para 112px de maior tinta e a
  `status_battery_bar` pintava os mesmos 1242px para dizer um número de dois
  dígitos.
* **E4** — o teto elástico nas duas abas de coluna única (Início e Rumble).
* **E5** — o mesmo nas quatro de duas colunas (Gatilhos, Lightbar, Perfis e
  Navegação).

E cobra também, pelo avesso, o que ficou **de fora por escrito**: a aba Sistema
não pode ganhar teto nenhum, porque a linha mais longa do log pede 1400px
exatos, o `daemon_log_scroll` tem `hscrollbar-policy: never` e o
`daemon_status_text` quebra por palavra — um teto de 1400px na página partiria
essa linha em duas. É o único aceite desta sprint que pede o CONTRÁRIO do teto.

Duas armadilhas de medição já pagas nesta casa, e as duas valem aqui:

* **Teto no GTK3 não é `width-request`.** Pedido de tamanho é MÍNIMO, nunca
  máximo (`app/widgets/controller_card.py:314`), e um mínimo declarado com
  `halign=center` TRAVA o widget no número exato. Por isso o teto de página vem
  de fora, pela `CaixaDeTetoElastico`, e o das barras vem do par
  `halign=start` + `width-request`.
* **Widget sem alocação devolve 1x1 em tudo.** Toda medida daqui é de
  `get_allocation()` depois de montar a janela, mostrar e rodar o laço — e
  passando por TODAS as páginas, porque o `GtkNotebook` só aloca a que está à
  vista. Um teste de geometria sobre widget não alocado passa com qualquer
  layout.

Nada aqui compara posição VERTICAL de widgets em `GtkScrolledWindow`
diferentes: cada rolador tem `GdkWindow` própria e as coordenadas mentem. As
comparações horizontais são todas entre pai e filho da mesma página.
"""
from __future__ import annotations

from tests.conftest import exigir_gi_real

# GUARDA-GI-REAL-01: antes de qualquer import de `gi`. `importorskip("gi")`
# aceitaria o stub que outro arquivo planta em sys.modules; sem guarda nenhuma
# este módulo derrubaria a COLETA no CI headless em vez de pular.
exigir_gi_real("largura a mesma em todas as abas")

from collections.abc import Iterator
from typing import Any

import pytest

_gi = pytest.importorskip("gi", reason="precisa de PyGObject")
_gi.require_version("Gtk", "3.0")
_gi.require_version("Gdk", "3.0")
from gi.repository import Gdk, Gtk

from hefesto_dualsense4unix.app.actions.home_actions import id_da_pagina
from hefesto_dualsense4unix.app.app import HefestoApp
from hefesto_dualsense4unix.app.constants import GUI_DIR, MAIN_GLADE
from hefesto_dualsense4unix.app.theme import (
    escala_fonte,
    escalar_css,
    escalar_nome_da_fonte,
)
from hefesto_dualsense4unix.app.widgets.controller_card import (
    LARGURA_CARD_ELASTICA,
    CaixaDeTetoElastico,
)

#: A tela dela, maximizada. É onde o vão aparece.
LARGURA_MAXIMIZADA = 1920

#: O tamanho com que a janela abre. Aqui o teto NÃO pode entrar em ação — foi a
#: promessa da sprint, e é o tamanho em que o orçamento de altura é cobrado.
LARGURA_DE_PROJETO = 1180

#: E2 — quantas vezes a maior tinta de valor a coluna pode medir. O número é da
#: sprint: com 112px de maior tinta ("Consultando..."), o teto fica em ~340px.
FATOR_DA_COLUNA_DE_VALORES = 3

#: E2 — distância máxima entre o texto da barra de bateria e a borda dela. É o
#: mesmo `VAO_MAXIMO_ENTRE_BLOCOS` de `test_status_faixa_blocos.py`, medido na
#: tela dela.
VAO_MAXIMO = 200

#: E6 fica de fora POR ESCRITO: a linha mais longa do log pede 1400px exatos, e
#: este é o piso com folga que a sprint escreveu para o widget do log.
PISO_DO_LOG = 1440

#: As seis páginas que ganham o teto — E4 (coluna única) e E5 (duas colunas).
PAGINAS_COM_TETO = (
    "tab_home_box",
    "tab_rumble_box",
    "tab_triggers_box",
    "tab_lightbar_box",
    "profiles_paned",
    "tab_navegacao_dsx",
)

#: As páginas que NÃO ganham teto, e o motivo medido de cada uma. `tab_status_box`
#: não está aqui porque o teto dela é do frame, não da página
#: (`_envolver_estado_em_teto_elastico`).
PAGINAS_SEM_TETO = {
    "daemon_box": "o log usa a largura inteira e a linha mais longa pede 1400px",
    "emulation_box": "o vão é ENTRE os dois cartões, que já param no natural",
}

#: As propriedades de empacotamento de um filho de `GtkBox`. Mudar qualquer uma
#: delas ao mudar o filho de casa muda o desenho da aba por efeito colateral.
EMPACOTAMENTO = ("expand", "fill", "padding", "pack-type")


def _gtk_pronto() -> bool:
    try:
        return bool(Gtk.init_check()[0])
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not _gtk_pronto(), reason="sem GTK/display utilizável"
)


class _Montagem:
    """Só o `builder` — é o único atributo que os envolvedores usam.

    Os métodos vêm da classe REAL: a bancada mede o que o app faz na montagem,
    não uma imitação dele que pode divergir sem ninguém notar.
    """

    _envolver_estado_em_teto_elastico = HefestoApp._envolver_estado_em_teto_elastico
    _envolver_paginas_em_teto_elastico = HefestoApp._envolver_paginas_em_teto_elastico
    _PAGINAS_COM_TETO_ELASTICO = HefestoApp._PAGINAS_COM_TETO_ELASTICO

    def __init__(self, builder: Any) -> None:
        self.builder = builder


@pytest.fixture(autouse=True, scope="module")
def _tema_na_escala_que_sai() -> Iterator[None]:
    """Aplica o tema pelos DOIS canais de `app.theme.apply_theme`, e desfaz.

    Sem o `gtk-font-name`, quase toda a janela mediria os 13,33px padrão do
    Pango e os números não seriam os da tela dela. A restauração impede que a
    escala vaze para outros arquivos da mesma sessão do pytest.
    """
    delta = escala_fonte()
    tela = Gdk.Screen.get_default()
    provider = Gtk.CssProvider()
    bruto = (GUI_DIR / "theme.css").read_text(encoding="utf-8")
    provider.load_from_data(escalar_css(bruto, delta).encode("utf-8"))
    if tela is not None:
        Gtk.StyleContext.add_provider_for_screen(
            tela, provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )
    settings = Gtk.Settings.get_default()
    anterior = None
    if settings is not None and delta:
        anterior = settings.get_property("gtk-font-name")
        settings.set_property(
            "gtk-font-name", escalar_nome_da_fonte(anterior or "", delta)
        )
    yield
    if settings is not None and anterior is not None:
        settings.set_property("gtk-font-name", anterior)
    if tela is not None:
        Gtk.StyleContext.remove_provider_for_screen(tela, provider)


def _montar(largura: int) -> Gtk.Builder:
    """Janela inteira numa `Gtk.OffscreenWindow`, montada pelo código real."""
    builder = Gtk.Builder()
    builder.add_from_file(str(MAIN_GLADE))
    root = builder.get_object("root_box")
    pai = root.get_parent()
    if pai is not None:
        pai.remove(root)
    win = Gtk.OffscreenWindow()
    win.get_style_context().add_class("hefesto-dualsense4unix-window")
    win.add(root)

    montagem = _Montagem(builder)
    montagem._wrap_notebook_pages_in_scroll = (
        lambda: HefestoApp._wrap_notebook_pages_in_scroll(montagem)
    )
    montagem._wrap_notebook_pages_in_scroll()
    montagem._envolver_paginas_em_teto_elastico()

    win.set_size_request(largura, 1080)
    win.show_all()
    # O `GtkNotebook` só ALOCA a página visível — sem passar por todas, oito das
    # nove devolveriam 1x1 e o teste passaria sem medir nada.
    notebook = builder.get_object("main_notebook")
    for indice in range(notebook.get_n_pages()):
        notebook.set_current_page(indice)
        for _ in range(600):
            if not Gtk.events_pending():
                break
            Gtk.main_iteration()
    return builder


@pytest.fixture(scope="module")
def maximizada() -> Gtk.Builder:
    return _montar(LARGURA_MAXIMIZADA)


@pytest.fixture(scope="module")
def de_projeto() -> Gtk.Builder:
    return _montar(LARGURA_DE_PROJETO)


def _caixa_da_pagina(builder: Gtk.Builder, nome: str) -> Any:
    pagina = builder.get_object(nome)
    assert pagina is not None, f"{nome} saiu do main.glade"
    filhos = pagina.get_children()
    assert len(filhos) == 1 and isinstance(filhos[0], CaixaDeTetoElastico), (
        f"{nome} não está dentro de uma CaixaDeTetoElastico (filhos: "
        f"{[type(f).__name__ for f in filhos]}). Provavelmente alguém tirou a "
        "página de `_PAGINAS_COM_TETO_ELASTICO` ou a chamada de "
        "`_envolver_paginas_em_teto_elastico` saiu do `show()`."
    )
    return pagina, filhos[0]


# --- E4 e E5: o teto elástico nas seis abas --------------------------------


@pytest.mark.parametrize("nome", PAGINAS_COM_TETO)
def test_a_aba_para_no_teto_e_fica_centrada(
    nome: str, maximizada: Gtk.Builder
) -> None:
    """Com a janela em 1920 o conteúdo mede 1400px e a sobra vira margem.

    Mordida: tirar o nome de `_PAGINAS_COM_TETO_ELASTICO` devolve a página aos
    ~1894px que a sprint mediu, e o `_caixa_da_pagina` reprova antes mesmo da
    comparação de largura.
    """
    pagina, caixa = _caixa_da_pagina(maximizada, nome)
    alocada = caixa.get_allocation()

    assert alocada.width == LARGURA_CARD_ELASTICA, (
        f"{nome} recebeu {alocada.width}px de conteúdo numa janela de "
        f"{LARGURA_MAXIMIZADA} (teto {LARGURA_CARD_ELASTICA}). O corte fica no "
        "`do_size_allocate` da caixa, nunca num `set_size_request`: pedido de "
        "tamanho no GTK3 é MÍNIMO, e um mínimo de 1400 subiria intacto até a "
        "janela."
    )

    da_pagina = pagina.get_allocation()
    esquerda = alocada.x - da_pagina.x
    direita = (da_pagina.x + da_pagina.width) - (alocada.x + alocada.width)
    assert esquerda > 0 and abs(esquerda - direita) <= 2, (
        f"{nome} não ficou centrada: {esquerda}px de margem à esquerda e "
        f"{direita}px à direita. A sobra tem de se repartir nos dois lados — "
        "encostada num deles ela vira vão, que é o defeito que esta sprint ataca."
    )


@pytest.mark.parametrize("nome", PAGINAS_COM_TETO)
def test_no_tamanho_de_projeto_o_teto_nao_entra_em_acao(
    nome: str, de_projeto: Gtk.Builder
) -> None:
    """Com a janela em 1180 nada muda — a aba usa a largura inteira.

    É a promessa que sustenta o orçamento de altura: o pior caso continua sendo
    a janela pequena, e nela o teto de 1400px nem chega a ser alcançado.
    """
    pagina, caixa = _caixa_da_pagina(de_projeto, nome)

    assert caixa.get_allocation().width == pagina.get_allocation().width, (
        f"{nome} foi cortada com a janela em {LARGURA_DE_PROJETO}: a página tem "
        f"{pagina.get_allocation().width}px e o conteúdo ficou com "
        f"{caixa.get_allocation().width}px. Abaixo de "
        f"{LARGURA_CARD_ELASTICA}px o teto tem de ser inerte."
    )


@pytest.mark.parametrize("nome", PAGINAS_COM_TETO)
def test_a_altura_informada_cobre_o_conteudo_ja_cortado(
    nome: str, maximizada: Gtk.Builder
) -> None:
    """A altura pedida tem de ser a da largura CORTADA, não a da largura cheia.

    Um parágrafo que cabe em duas linhas com 1894px passa a ocupar três com
    1400px. Se a página seguir respondendo pela largura cheia, ela informa ao
    rolador uma altura menor que a real — medido na Lightbar: 440px informados
    contra 484px necessários. Numa janela larga e BAIXA (o tiling do COSMIC,
    que é a razão de as páginas serem roláveis) esses 44px ficam abaixo do
    corte e a barra de rolagem não chega até eles.

    Mordida: arrancar o `do_get_preferred_height_for_width` da
    `CaixaDeTetoDePagina` faz a Lightbar reprovar aqui.
    """
    pagina, caixa = _caixa_da_pagina(maximizada, nome)
    miolo = caixa.get_child()

    informada = pagina.get_preferred_height_for_width(
        pagina.get_allocation().width
    )[1]
    necessaria = miolo.get_preferred_height_for_width(
        caixa.get_allocation().width
    )[1]

    assert informada >= necessaria, (
        f"{nome} informa {informada}px de altura e o conteúdo cortado em "
        f"{caixa.get_allocation().width}px precisa de {necessaria}px: "
        f"{necessaria - informada}px ficam abaixo do corte, sem barra de "
        "rolagem que alcance."
    )


@pytest.mark.parametrize("nome", PAGINAS_COM_TETO)
def test_os_filhos_mudaram_de_casa_com_o_mesmo_empacotamento(
    nome: str, maximizada: Gtk.Builder
) -> None:
    """Nenhum filho se perdeu nem trocou de regra ao entrar na caixa.

    A comparação é contra um segundo builder do MESMO glade, sem montagem
    nenhuma — assim o teste não repete à mão uma lista que o glade já declara e
    não vira mentira no dia em que a aba ganhar um bloco novo.

    Mordida: empacotar tudo com `pack_start(filho, True, True, 0)` faz esta
    comparação reprovar em qualquer aba que tenha um filho com `expand=False`.
    """
    intocado = Gtk.Builder()
    intocado.add_from_file(str(MAIN_GLADE))
    original = intocado.get_object(nome)

    _pagina, caixa = _caixa_da_pagina(maximizada, nome)
    miolo = caixa.get_child()

    def retrato(caixa_box: Any) -> list[tuple[Any, ...]]:
        saida = []
        for filho in caixa_box.get_children():
            nome_do_filho = Gtk.Buildable.get_name(filho) or type(filho).__name__
            saida.append(
                (
                    nome_do_filho,
                    *(
                        caixa_box.child_get_property(filho, chave)
                        for chave in EMPACOTAMENTO
                    ),
                )
            )
        return saida

    assert retrato(miolo) == retrato(original), (
        f"o miolo de {nome} não é mais o que o glade declara. Ordem, "
        f"{'/'.join(EMPACOTAMENTO)} — tudo tem de atravessar a mudança de casa "
        "intacto, senão o teto muda o desenho da aba por efeito colateral."
    )


def test_toda_aba_continua_sendo_reconhecida_pelo_id_do_glade(
    maximizada: Gtk.Builder,
) -> None:
    """O teto entra DENTRO da página — e este é o teste que cobra isso.

    `id_da_pagina` reconhece a aba pelo nome de Buildable do widget que o
    notebook devolve, desembrulhando o rolador. Um `Gtk.Bin` nosso não tem nome
    de Buildable: medido, `Gtk.Buildable.get_name` devolve `None` mesmo depois
    de `set_name`. Envolver a página POR FORA faria `_on_notebook_switch_page`
    e os pollers de Início e Status pararem de reconhecer qualquer aba **em
    silêncio** — sem exceção, sem log, só o refresh que nunca mais roda.

    Mordida: trocar o `pagina.pack_start(caixa, ...)` por envolver a página na
    caixa e devolvê-la ao rolador faz as nove virarem `None` aqui.
    """
    notebook = maximizada.get_object("main_notebook")
    nomes = [
        id_da_pagina(notebook.get_nth_page(i))
        for i in range(notebook.get_n_pages())
    ]

    assert None not in nomes, f"aba sem id reconhecível: {nomes}"
    for nome in (*PAGINAS_COM_TETO, *PAGINAS_SEM_TETO, "tab_status_box"):
        assert nome in nomes, f"{nome} deixou de ser reconhecida: {nomes}"


# --- O que ficou de fora, por escrito --------------------------------------


@pytest.mark.parametrize("nome", sorted(PAGINAS_SEM_TETO))
def test_a_aba_que_fica_de_fora_continua_com_a_largura_inteira(
    nome: str, maximizada: Gtk.Builder
) -> None:
    """Duas abas não podem ganhar teto, e o motivo de cada uma está medido.

    Mordida: acrescentar `daemon_box` ou `emulation_box` a
    `_PAGINAS_COM_TETO_ELASTICO` derruba este teste.
    """
    pagina = maximizada.get_object(nome)
    largura = pagina.get_allocation().width

    assert largura > LARGURA_CARD_ELASTICA, (
        f"{nome} ficou com {largura}px: {PAGINAS_SEM_TETO[nome]}."
    )


def test_o_log_do_sistema_recebe_mais_do_que_a_linha_mais_longa_pede(
    maximizada: Gtk.Builder,
) -> None:
    """O único aceite desta sprint que pede o CONTRÁRIO de um teto.

    A linha mais longa do log tem 175 caracteres e a fonte monoespaçada mede
    8px por caractere: 1400px exatos. O `daemon_log_scroll` tem
    `hscrollbar-policy: never` e o `daemon_status_text` quebra por palavra —
    com um teto de 1400px na página sobrariam ~1370px úteis e essa linha
    apareceria partida em duas.
    """
    texto = maximizada.get_object("daemon_status_text")
    largura = texto.get_allocation().width

    assert largura >= PISO_DO_LOG, (
        f"o `daemon_status_text` recebeu {largura}px numa janela de "
        f"{LARGURA_MAXIMIZADA} (piso {PISO_DO_LOG}): a linha mais longa do log "
        "passa a quebrar em duas. A aba Sistema fica FORA do teto por escrito."
    )


# --- E2: o miolo do frame "Estado" -----------------------------------------


def _coluna_de_valores(builder: Gtk.Builder) -> tuple[int, int]:
    """(largura alocada da coluna de valores, maior tinta de valor)."""
    valores = (
        "status_connection",
        "status_transport",
        "status_active_profile",
        "status_daemon",
    )
    alocadas, tintas = [], []
    for nome in valores:
        widget = builder.get_object(nome)
        assert widget is not None, f"{nome} saiu do main.glade"
        alocadas.append(widget.get_allocation().width)
        tintas.append(widget.get_preferred_width()[1])
    return max(alocadas), max(tintas)


def test_a_coluna_de_valores_do_estado_para_perto_da_tinta(
    maximizada: Gtk.Builder,
) -> None:
    """O teto da SOM-01 parava no frame e não alcançava o miolo dele.

    Medido antes desta entrega, com a janela em 1920 e o frame já em 1400: a
    coluna de valores recebia 1242px para 112px de maior tinta.

    Mordida: devolver `hexpand=True` à `status_battery_bar` faz a coluna inteira
    voltar a 1242px — num `GtkGrid` o `hexpand` de UM filho expande a COLUNA.
    """
    coluna, tinta = _coluna_de_valores(maximizada)

    assert coluna <= FATOR_DA_COLUNA_DE_VALORES * tinta, (
        f"a coluna de valores do `status_grid` recebeu {coluna}px para {tinta}px "
        f"de maior tinta ({coluna / tinta:.1f}x; o teto é "
        f"{FATOR_DA_COLUNA_DE_VALORES}x). Procure `hexpand` em algum filho da "
        "coluna: num GtkGrid ele expande a coluna inteira, não só o filho."
    )


def test_a_coluna_de_valores_nao_cresce_quando_a_janela_cresce(
    maximizada: Gtk.Builder, de_projeto: Gtk.Builder
) -> None:
    """A garantia mais funda, e a que não depende da escala de fonte.

    Se a coluna acompanha a janela, ela não tem teto nenhum — tem só um número
    grande o bastante para o teste do lado passar naquela tela.
    """
    larga, _ = _coluna_de_valores(maximizada)
    estreita, _ = _coluna_de_valores(de_projeto)

    assert larga == estreita, (
        f"a coluna de valores mede {estreita}px com a janela em "
        f"{LARGURA_DE_PROJETO} e {larga}px com a janela em "
        f"{LARGURA_MAXIMIZADA}: ela acompanha a janela, e o vão volta junto."
    )


def test_o_numero_da_bateria_nao_boia_no_meio_da_barra(
    maximizada: Gtk.Builder,
) -> None:
    """A barra pintava 1242px para dizer dois dígitos.

    O `— %` era desenhado CENTRADO na barra, então a distância dele até cada
    borda era metade do que sobrava. Medido antes: 1242px de barra para 26px
    de texto — 608px de vazio de cada lado.

    **ESTADO-TRES-LINHAS-01 (01/08) curou a causa, e a cura mudou o que este
    teste tem de medir.** Ela pediu a barra ocupando a largura inteira, e com
    o texto DENTRO isso é o defeito garantido: um GtkProgressBar centra o
    texto, então quanto mais larga a barra, mais longe o número fica das duas
    pontas. Encolher a barra deixou de ser opção.

    O número saiu de dentro da barra e virou um rótulo ao lado
    (`status_battery_pct`, espelhado por `_set_battery_text`). A distância que
    importa passou a ser entre o FIM da barra e o número — e essa não cresce
    com a janela, porque os dois são vizinhos numa GtkBox.

    Mordida: devolver `show-text=True` à barra faz o texto voltar para o meio
    dela e a primeira asserção cai; tirar o rótulo do glade faz cair a segunda.
    """
    barra = maximizada.get_object("status_battery_bar")
    assert barra is not None, "status_battery_bar saiu do main.glade"
    rotulo = maximizada.get_object("status_battery_pct")
    assert rotulo is not None, (
        "status_battery_pct saiu do main.glade: o número da bateria não tem "
        "mais onde aparecer, porque a barra não desenha o próprio texto"
    )

    assert barra.get_show_text() is False, (
        "a barra voltou a desenhar o próprio texto. Centrado numa barra que "
        "ocupa a largura toda, o número fica a ~600px de cada borda — o mesmo "
        "defeito que ela apontou nas barras de L2/R2 dentro do card."
    )

    fim_da_barra = barra.get_allocation().x + barra.get_allocation().width
    inicio_do_numero = rotulo.get_allocation().x
    distancia = inicio_do_numero - fim_da_barra

    assert 0 <= distancia < VAO_MAXIMO, (
        f"o número da bateria está a {distancia}px do fim da barra (o vão "
        f"máximo desta casa é {VAO_MAXIMO}px): ele deixou de ler como o valor "
        "daquela barra."
    )


def test_a_barra_de_bateria_continua_uma_barra_e_nao_um_toco(
    maximizada: Gtk.Builder,
) -> None:
    """O outro lado do teto: ela ainda tem de LER como medidor de carga.

    Um `halign=start` sem `width-request` deixaria a barra no natural, estreita
    demais para mostrar proporção — teto cumprido e informação perdida.
    """
    largura = maximizada.get_object("status_battery_bar").get_allocation().width

    assert largura >= 200, (
        f"a barra de bateria ficou com {largura}px: o teto é para devolver "
        "espaço, não para transformar o medidor num toco."
    )
