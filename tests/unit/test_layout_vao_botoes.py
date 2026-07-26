"""VAO-01 — o vão vertical das abas vira tamanho de botão, não espaço morto.

O pedido que abriu esta entrega foi visual e direto:

> *"distribuir e aumentar os demais botões do controle pra ocuparem o espaço
> vazio que fica no fundo"*

Com a janela em 1180x830 e a fonte na escala que sai, cada coluna da aba
Gatilhos deixava **226px de cinza** entre a grade dos 19 modos e o rodapé
"Aplicar em L2". O vão não era acidente de sobra: o scroller de parâmetros era
o único filho com `vexpand`, então ele engolia toda a folga da coluna — e nos
modos sem parâmetro ele estava VAZIO. A aba Emulação tinha o gêmeo menor: 28px
empoçados abaixo da última linha.

Estes testes travam as duas metades do conserto:

* **A entrega** — com espaço disponível, a grade cresce e o vão some. Se
  alguém devolver o `vexpand` ao scroller (ou tirar o `esticar=True` do
  seletor), o vão volta e os testes de "ocupa" ficam vermelhos.
* **O limite** — crescer por `expand` NÃO muda o mínimo, e é por isso que este
  caminho foi escolhido em vez de `min-height` no CSS. No modo mais cheio (11
  parâmetros e a linha de "Efeito pronto" visível) a grade volta ao piso de
  32px da LEGIBILIDADE-01 e a aba continua cabendo na faixa. O teste do piso
  é o que impede alguém de "resolver" o vão engordando o botão fixo até
  estourar a aba mais cheia.

Por que a medição é feita AQUI e não em `test_layout_orcamento_altura.py`: a
grade dos 19 modos **não está no glade** — ela nasce em
`triggers_actions.install_triggers_tab`. O orçamento de altura aferia a aba
Gatilhos em 292px enquanto a aba real pedia 538px, e por isso não viu que o
modo `MultiPositionVibration` já pedia 646px para uma faixa de 630px, forçando
rolagem. Medir sem a grade é medir outra aba.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest

# Guarda de ambiente: na CI o `gi` IMPORTA mas os typelibs sao PARCIAIS — falta
# `Pango`, falta `Gdk`, e `Gtk` vem sem `DrawingArea`. Nesse estado
# `importorskip("gi")` NÃO protege: `require_version` levanta ValueError e o
# `from gi.repository import ...` levanta ImportError, e os dois derrubam a
# COLETA do módulo em vez de virar skip — a CI reprova em massa com erro que
# não tem nada a ver com o teste. Por isso o preambulo inteiro entra num try.
try:
    import gi as _gi

    _gi.require_version("Gtk", "3.0")
    _gi.require_version("Gdk", "3.0")
    from gi.repository import Gdk, Gtk

    if not hasattr(Gtk, "DrawingArea"):
        raise ImportError("typelib do Gtk sem DrawingArea")
except (ImportError, ValueError) as _exc:  # pragma: no cover
    pytest.skip(f"typelib parcial: {_exc}", allow_module_level=True)

from hefesto_dualsense4unix.app.actions.trigger_specs import PRESETS
from hefesto_dualsense4unix.app.actions.triggers_actions import (
    TriggersActionsMixin,
)
from hefesto_dualsense4unix.app.constants import GUI_DIR, MAIN_GLADE
from hefesto_dualsense4unix.app.draft_config import DraftConfig
from hefesto_dualsense4unix.app.theme import (
    escala_fonte,
    escalar_css,
    escalar_nome_da_fonte,
)


def _dimensao_da_janela(nome: str) -> int:
    """Lê `default-width`/`default-height` do glade (nunca duplicar o número)."""
    import xml.etree.ElementTree as ET

    arvore = ET.parse(str(MAIN_GLADE))
    for obj in arvore.iter("object"):
        if obj.get("id") != "main_window":
            continue
        for prop in obj.findall("property"):
            if prop.get("name") == nome:
                return int((prop.text or "0").strip())
    raise AssertionError(f"{nome} não encontrado em main_window")


LARGURA = _dimensao_da_janela("default-width")
ALTURA = _dimensao_da_janela("default-height")

#: Piso de alvo de clique fixado pela LEGIBILIDADE-01: 24px de caixa de
#: conteúdo + 6px de padding + 2px de borda. Nenhum botão pode ficar abaixo
#: disso, nem quando a coluna está no aperto máximo.
PISO_ALVO_PX = 32

#: Modo mais caro da aba: 11 parâmetros E a linha "Efeito pronto" visível.
MODO_MAIS_CHEIO = "MultiPositionVibration"


def _gtk_pronto() -> bool:
    try:
        return bool(Gtk.init_check()[0])
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not _gtk_pronto(), reason="sem GTK/display utilizável"
)


@pytest.fixture(autouse=True, scope="module")
def _tema_na_escala_que_sai() -> Iterator[None]:
    """Mesmos dois canais de `app.theme.apply_theme` (CSS reescrito + fonte base).

    Sem o `gtk-font-name`, ~90% da janela mediria os 13,33px do padrão do Pango
    e o vão aferido não seria o da tela dela. A restauração no fim impede que
    a fonte global vaze para outros arquivos da mesma sessão do pytest.
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


class _AbaGatilhosDeVerdade(TriggersActionsMixin):
    """Hospedeiro mínimo para rodar `install_triggers_tab` DE VERDADE.

    Nada de réplica: a primeira versão deste arquivo montava o
    `SegmentedSelector` por conta própria, com os mesmos argumentos que o app
    usa. Passava — e continuava passando com o `esticar=True` arrancado do
    app, porque testava a peça e não a fiação. Aqui quem monta a grade é o
    código de produção; o hospedeiro só fornece o `builder` e o rascunho de
    perfil que o mixin espera encontrar.

    `install_triggers_tab` não toca em IPC: ele seleciona "Off" sob
    `_triggers_guard_refresh`, justamente para não disparar o live-preview ao
    abrir a janela (BUG-GUI-OPEN-OFF-TRIGGER-WRITE-01).
    """

    def __init__(self, builder: Gtk.Builder) -> None:
        self.builder = builder
        self.draft = DraftConfig.default()
        self._edit_target_uniq: str | None = None

    def escolher_modo(self, modo: str) -> None:
        """Troca o modo pelo MESMO caminho guardado que o install usa.

        Sob o guard, `_on_mode_changed` sai cedo e nenhum temporizador de
        live-preview é agendado — o que sobra é exatamente a remontagem de
        widgets que muda a geometria, que é o que se mede aqui.
        """
        for lado in ("left", "right"):
            self._triggers_guard_refresh = True
            try:
                self._trigger_mode[lado].set_active_id(modo)
            finally:
                self._triggers_guard_refresh = False
            self._rebuild_params(lado, modo)
            self._update_preset_row_visibility(lado, modo)
            self._populate_preset_combo(lado, modo)


def _montar_como_a_janela_abre(
    aba: str, modo: str | None = None
) -> tuple[Gtk.Builder, Gtk.Widget]:
    """Monta o glade e força a janela ao tamanho EXATO com que ela abre.

    Duas fidelidades importam aqui, e as duas custaram medição errada antes:

    1. **A grade dos 19 modos nasce do código de produção**
       (`install_triggers_tab`), senão a aba medida não é a aba que ela vê — e
       o teste não morde quando alguém mexe no call site.
    2. **Cada página vira filha de um `GtkScrolledWindow`**, como
       `app.app._wrap_pages_in_scrollers` faz. É isso que derruba o mínimo da
       página para ~0 e permite fixar a janela em 1180x830 — sem o embrulho, a
       `GtkOffscreenWindow` se dimensiona pela altura NATURAL e mede uma janela
       de 870px que ninguém tem.

    A única divergência deliberada em relação ao app é
    `propagate-natural-height=False` no embrulho: no app a janela real já nasce
    presa ao `default-size`, aqui é o `set_size_request` que faz esse papel.
    """
    builder = Gtk.Builder()
    builder.add_from_file(str(MAIN_GLADE))
    root = builder.get_object("root_box")
    pai = root.get_parent()
    if pai is not None:
        pai.remove(root)
    win = Gtk.OffscreenWindow()
    win.get_style_context().add_class("hefesto-dualsense4unix-window")
    win.add(root)

    hospedeiro = _AbaGatilhosDeVerdade(builder)
    hospedeiro.install_triggers_tab()
    if modo is not None:
        hospedeiro.escolher_modo(modo)

    notebook = builder.get_object("main_notebook")
    paginas = []
    while notebook.get_n_pages() > 0:
        pagina = notebook.get_nth_page(0)
        rotulo = notebook.get_tab_label(pagina)  # a ref mantém o widget vivo
        notebook.remove_page(0)
        paginas.append((pagina, rotulo))
    alvo = 0
    for indice, (pagina, rotulo) in enumerate(paginas):
        if Gtk.Buildable.get_name(pagina) == aba:
            alvo = indice
        if Gtk.Buildable.get_name(pagina) == "daemon_box":  # já tem scroll próprio
            notebook.append_page(pagina, rotulo)
            continue
        scroller = Gtk.ScrolledWindow()
        scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroller.set_propagate_natural_width(True)
        scroller.set_propagate_natural_height(False)
        scroller.add(pagina)
        notebook.append_page(scroller, rotulo)

    win.set_size_request(LARGURA, ALTURA)
    win.show_all()
    notebook.set_current_page(alvo)
    for _ in range(4):
        while Gtk.events_pending():
            Gtk.main_iteration()
    return builder, builder.get_object(aba)


def _grade_de_modos(builder: Gtk.Builder, lado: str = "left") -> Gtk.Grid:
    """O `GtkGrid` de 3 colunas dentro do `SegmentedSelector` do lado pedido."""
    seletor = builder.get_object(f"trigger_{lado}_mode_slot").get_children()[0]
    return seletor.get_children()[0]


def _teto_por_aba(builder: Gtk.Builder) -> int:
    """Mesma conta DERIVADA do orçamento de altura: nada de número fixo aqui."""
    notebook = builder.get_object("main_notebook")
    fora = sum(
        builder.get_object(nome).get_preferred_height_for_width(LARGURA)[0]
        for nome in ("header_bar", "footer_box")
    )
    maior = max(
        notebook.get_nth_page(i).get_preferred_height_for_width(LARGURA - 20)[0]
        for i in range(notebook.get_n_pages())
    )
    cromo = notebook.get_preferred_height_for_width(LARGURA)[0] - maior
    return ALTURA - fora - cromo


# ---------------------------------------------------------------------------
# A entrega: o vão vira botão
# ---------------------------------------------------------------------------


def test_a_grade_de_modos_ocupa_o_vao_em_vez_de_deixa_lo_vazio() -> None:
    """Sem parâmetros na tela, os 19 botões tomam a altura que sobrava.

    Antes: a grade ficava presa em 268px (botões de 32px, os de rótulo em duas
    linhas com 48px) e o scroller VAZIO de parâmetros ficava com 226px. Depois:
    a grade recebe 448px e o menor botão passa de 32px para 57px.

    O piso de 48px cobrado aqui é folgado de propósito — o que se prova é que a
    grade cresceu ALÉM do mínimo, não o número exato, que varia com o tema do
    sistema. Antes da correção o menor botão tinha exatamente o piso de 32px.
    """
    builder, _aba = _montar_como_a_janela_abre("tab_triggers_box")
    grade = _grade_de_modos(builder)

    alturas = sorted(b.get_allocated_height() for b in grade.get_children())

    assert len(alturas) == len(PRESETS) == 19
    assert alturas[0] >= 48, (
        f"o menor dos 19 botões de modo tem {alturas[0]}px: a grade voltou a "
        f"ficar no mínimo ({PISO_ALVO_PX}px) e o vão da coluna voltou a ser "
        "espaço morto. Procure quem recuperou o `vexpand` do scroller de "
        "parâmetros ou perdeu o `esticar=True` do SegmentedSelector."
    )


def test_nao_sobra_vao_entre_a_grade_de_modos_e_o_rodape_da_coluna() -> None:
    """A medida direta do que ela apontou: o cinza entre a grade e o "Aplicar".

    Medido antes: 290px. Medido depois: 102px, e esses 102 têm dono — 46px são
    o piso que um `GtkScrolledWindow` vazio cobra do próprio GTK (não é folga
    nossa: some assim que o modo tem parâmetros), 26px são o rótulo de
    descrição e o resto são os dois espaçamentos de 8px da coluna.
    """
    builder, _aba = _montar_como_a_janela_abre("tab_triggers_box")
    grade = _grade_de_modos(builder)
    aplicar = builder.get_object("trigger_left_apply")

    fim_da_grade = grade.get_allocation().y + grade.get_allocated_height()
    vao = aplicar.get_allocation().y - fim_da_grade

    assert vao <= 130, (
        f"sobram {vao}px de espaço morto entre a grade de modos e o botão "
        "'Aplicar em L2'. Era esse o vão da queixa; ele volta se o scroller de "
        "parâmetros voltar a ser o filho que expande."
    )


def test_a_emulacao_nao_deixa_folga_empocada_no_rodape_da_aba() -> None:
    """A aba Emulação repartia 28px entre nada; agora eles viram alvo de clique.

    A folga é medida onde ela aparecia: entre o fim do último filho da aba e o
    fim da área que a aba recebeu. As quatro linhas de escolha (máscara, modo
    jogo, Steam Input, microfone) passaram a expandir e consomem esses pixels.
    """
    _builder, aba = _montar_como_a_janela_abre("emulation_box")

    ultimo = aba.get_children()[-1]
    fim_do_conteudo = (
        ultimo.get_allocation().y + ultimo.get_allocated_height()
    )
    fim_da_aba = aba.get_allocation().y + aba.get_allocated_height()
    folga = fim_da_aba - fim_do_conteudo

    assert folga <= 12, (
        f"sobram {folga}px empoçados no rodapé da aba Emulação. As quatro "
        "linhas de escolha deveriam repartir essa folga entre si — confira se "
        "alguma voltou a `expand=False` no glade."
    )


# ---------------------------------------------------------------------------
# O limite: crescer não pode estourar a aba nem furar o piso de clique
# ---------------------------------------------------------------------------


def test_no_modo_mais_cheio_os_botoes_voltam_ao_piso_mas_nunca_abaixo() -> None:
    """Com 11 parâmetros na tela a grade cede o espaço — até o piso, não além.

    É a prova de que o crescimento é por `expand` e não por altura fixa: altura
    fixa não sabe recuar, e neste modo não há de onde tirar os pixels. O piso
    de 32px da LEGIBILIDADE-01 continua valendo no aperto máximo.
    """
    builder, _aba = _montar_como_a_janela_abre(
        "tab_triggers_box", MODO_MAIS_CHEIO
    )
    grade = _grade_de_modos(builder)

    alturas = sorted(b.get_allocated_height() for b in grade.get_children())

    assert alturas[0] >= PISO_ALVO_PX, (
        f"no modo {MODO_MAIS_CHEIO} o menor botão de modo caiu para "
        f"{alturas[0]}px, abaixo do piso de alvo de clique de "
        f"{PISO_ALVO_PX}px que a LEGIBILIDADE-01 fixou"
    )


def test_a_aba_gatilhos_com_a_grade_de_modos_cabe_no_orcamento() -> None:
    """O buraco que este arquivo existe para fechar.

    `test_layout_orcamento_altura.py` mede o glade puro, e a grade dos 19 modos
    não está no glade: ele via a aba Gatilhos com 292px enquanto a aba real
    pedia 538px — e 646px no modo mais cheio, ACIMA da faixa de 630px que ela
    recebe. Aferido com a grade montada e no modo mais caro.
    """
    builder, aba = _montar_como_a_janela_abre(
        "tab_triggers_box", MODO_MAIS_CHEIO
    )

    teto = _teto_por_aba(builder)
    pedido, _ = aba.get_preferred_height_for_width(LARGURA - 20)

    assert pedido <= teto, (
        f"a aba Gatilhos no modo {MODO_MAIS_CHEIO} pede {pedido}px para um "
        f"teto de {teto}px ({pedido - teto}px a mais): o notebook adota o "
        "MAIOR mínimo entre as páginas, então a barra de rolagem volta em "
        "TODAS as abas"
    )


def test_o_crescimento_dos_botoes_nao_mexe_no_minimo_da_aba() -> None:
    """A regra que torna esta entrega segura, escrita como teste.

    `expand`/`vexpand` só reparte a sobra da ALOCAÇÃO; quem sobe o mínimo é
    altura fixa (`min-height` no CSS, `set_size_request`). Se um dia alguém
    trocar o mecanismo, o mínimo da aba sem modo escolhido — onde os botões
    ficam MAIORES na tela — subiria junto, e é isso que este teste pega.

    Medido: 474px sem modo escolhido, exatamente o mesmo mínimo com o modo mais
    cheio descontado o que o conteúdo dele acrescenta. Aqui basta a comparação
    contra o teto, que é derivado.
    """
    builder, aba = _montar_como_a_janela_abre("tab_triggers_box")
    grade = _grade_de_modos(builder)

    teto = _teto_por_aba(builder)
    pedido, _ = aba.get_preferred_height_for_width(LARGURA - 20)
    alocado_pela_grade = grade.get_allocated_height()
    minimo_da_grade = grade.get_preferred_height_for_width(
        grade.get_allocated_width()
    )[0]

    assert alocado_pela_grade > minimo_da_grade, (
        f"a grade recebeu {alocado_pela_grade}px e pede {minimo_da_grade}px de "
        "mínimo: ela não está crescendo por alocação — se o tamanho novo veio "
        "de altura fixa, o mínimo da aba subiu junto e a aba mais cheia "
        "estoura"
    )
    assert pedido <= teto, (
        f"a aba Gatilhos pede {pedido}px de mínimo para um teto de {teto}px"
    )
