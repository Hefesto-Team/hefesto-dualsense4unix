"""AFORDÂNCIA — nenhuma dica da aba Configurações fica invisível.

O DEFEITO, medido em 23/08/2026 na aba montada de verdade, com a bancada viva
(2 DualSense no rádio, 3 adaptadores Bluetooth):

    pontos de dica montados na aba: 33
    Counter({'Label': 25, 'Button': 4, 'RadioButton': 4})
    ... e NENHUM dos 25 rótulos com marca visual nenhuma.

A leva da aba Configurações escreveu ~110 textos de dica, revisou-os e pôs cada
um no lugar certo. O inventário dela
(`docs/process/sprints/2026-08-21-ABA-CONFIGURACOES/TOOLTIPS.md`) fixou DUAS
marcas de afordância — sublinhado pontilhado em rótulo, `?` em cabeçalho — e
**nenhuma das duas existia no produto**: `grep dotted` no `theme.css` voltava
vazio, e os títulos das seções carregavam a dica em silêncio.

O texto estava certo e ninguém o via. Quem não sabe que há explicação não passa
o mouse para procurá-la — uma leva inteira de redação não chegava a ninguém.

## Por que este arquivo mede o EFEITO, e não a linha de código

Um teste que contasse chamadas de `add_class` no fonte passaria com a folha de
estilo arrancada, com a classe escrita errada, e com a regra CSS recusada pelo
parser do GTK — que foi exatamente o que quase aconteceu aqui. O GTK 3.24.41
**recusa** `text-decoration-style: dotted` ("unknown value for property") e lê
`text-decoration: underline dotted` como cor inválida; a pontilhada só existe
por `border-bottom`. Uma marca que o parser recusa é uma marca invisível, que é
o defeito que este arquivo existe para pegar. Por isso há duas medidas:

1. a classe está no **contexto de estilo do widget** da aba montada;
2. a folha faz a borda chegar **pontilhada** no widget, medida por
   `Gtk.StyleContext.get_border` e `border-bottom-style`.

## A régua é INDEPENDENTE da produção, de propósito

Este arquivo **não importa** `merece_sublinhado`. Se importasse, arrancar a cura
pelo predicado — fazê-lo devolver `False` — deixaria o teste sem nenhum alvo a
afirmar: zero rótulos encontrados, zero falhas, verde. É a armadilha que a casa
já pagou ("o portão que não mede o que promete", 19/08). A régua daqui é
reescrita do zero, em `_precisa_de_marca`, e `NUNCA_MENOS_QUE` garante que ela
continua encontrando alvos.

## As duas armadilhas de medição já pagas nesta casa

* **`Gtk.OffscreenWindow`, nunca `Gtk.Window`** — sob Xvfb não há gerenciador de
  janelas e uma `Gtk.Window` fica 1x1 para sempre
  (`docs/process/COMO-OLHAR-A-TELA.md`).
* **A folha tem de ser aplicada pela tela** — sem `add_provider_for_screen` a
  medida 2 leria os zeros do tema do sistema e reprovaria uma cura sã.
"""
from __future__ import annotations

from tests.conftest import exigir_gi_real

# GUARDA-GI-REAL-01: antes de qualquer import de `gi`. `importorskip("gi")`
# aceitaria o stub que outro arquivo planta em sys.modules.
exigir_gi_real("afordância das dicas da aba Configurações")

from collections.abc import Iterator
from typing import Any

import pytest

_gi = pytest.importorskip("gi", reason="precisa de PyGObject")
_gi.require_version("Gtk", "3.0")
_gi.require_version("Gdk", "3.0")
from gi.repository import Gdk, Gtk

from hefesto_dualsense4unix.app.actions.config.mixin import ConfigActionsMixin
from hefesto_dualsense4unix.app.actions.config.moldura import (
    CLASSE_AJUDA,
    CLASSE_TEM_DICA,
)
from hefesto_dualsense4unix.app.actions.config.secoes import SECOES_DA_ABA
from hefesto_dualsense4unix.app.constants import GUI_DIR, MAIN_GLADE

#: Piso de alvos que a régua tem de encontrar na aba montada.
#:
#: DE ONDE VEM O NÚMERO: a aba mediu 25 rótulos com dica na bancada de
#: 23/08/2026 (2 controles, 3 adaptadores). Boa parte deles é por aparelho — uma
#: bancada mais magra monta menos linhas —, então o piso fica BEM abaixo do
#: medido, em 12. Ele não existe para conferir a contagem: existe para que um
#: dia em que a régua pare de achar qualquer coisa reprove, em vez de passar
#: verde afirmando o vazio.
NUNCA_MENOS_QUE = 12


def _gtk_pronto() -> bool:
    try:
        return bool(Gtk.init_check()[0])
    except Exception:
        return False


pytestmark = pytest.mark.skipif(not _gtk_pronto(), reason="sem GTK/display utilizável")


@pytest.fixture(scope="module")
def _folha_na_tela() -> Iterator[None]:
    """A `theme.css` de verdade, aplicada pela tela, e desfeita no fim.

    Sem a restauração a folha vazaria para os outros arquivos da mesma sessão do
    pytest.
    """
    tela = Gdk.Screen.get_default()
    provider = Gtk.CssProvider()
    provider.load_from_data((GUI_DIR / "theme.css").read_bytes())
    if tela is not None:
        Gtk.StyleContext.add_provider_for_screen(
            tela, provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )
    yield
    if tela is not None:
        Gtk.StyleContext.remove_provider_for_screen(tela, provider)


class _HospedeiroDaAba(ConfigActionsMixin):
    def __init__(self, builder: Gtk.Builder) -> None:
        self.builder = builder


def _descer(widget: Any) -> Iterator[Any]:
    yield widget
    if isinstance(widget, Gtk.Container):
        for filho in widget.get_children():
            yield from _descer(filho)


def _girar(vezes: int = 5000) -> None:
    """Esvazia a fila do GTK — inclusive os `idle` da revarredura."""
    for _ in range(vezes):
        if not Gtk.events_pending():
            break
        Gtk.main_iteration()


@pytest.fixture(scope="module")
def aba_montada(_folha_na_tela: None) -> Any:
    """A aba de VERDADE, montada pelo mixin, numa janela mostrada."""
    builder = Gtk.Builder()
    builder.add_from_file(str(MAIN_GLADE))
    _HospedeiroDaAba(builder).install_config_tab()

    pagina = builder.get_object("scroll_tab_config_box")
    pai = pagina.get_parent()
    if pai is not None:
        pai.remove(pagina)
    janela = Gtk.OffscreenWindow()
    janela.get_style_context().add_class("hefesto-dualsense4unix-window")
    janela.add(pagina)
    janela.set_size_request(1180, 1000)
    janela.show_all()
    _girar()
    return pagina


def _tem_dica(widget: Any) -> bool:
    return bool((widget.get_tooltip_text() or "").strip())


def _classes(widget: Any) -> set[str]:
    return set(widget.get_style_context().list_classes())


def _precisa_de_marca(widget: Any) -> bool:
    """A régua deste arquivo, escrita sem olhar para a da produção.

    Um rótulo que esconde explicação e não é um controle. Botão, caixa de marcar
    e segmento do orçamento ficam de fora porque já se anunciam clicáveis — e
    ficam de fora aqui pelo MESMO motivo que na produção, mas por um caminho
    escrito à parte.
    """
    return (
        isinstance(widget, Gtk.Label)
        and _tem_dica(widget)
        and widget.get_ancestor(Gtk.Button) is None
    )


def _marcado(widget: Any) -> bool:
    """Tem marca própria, ou tem um `?` ao lado que fala por ele.

    O cabeçalho de seção é o segundo caso: a dica mora no título, e a marca é o
    `?` irmão. Exigir a marca no próprio título transformaria o teste numa
    afirmação sobre qual das duas afordâncias foi escolhida — e as duas são
    válidas, foi o inventário que repartiu.
    """
    if _classes(widget) & {CLASSE_TEM_DICA, CLASSE_AJUDA}:
        return True
    pai = widget.get_parent()
    if pai is None:
        return False
    return any(
        irmao is not widget and CLASSE_AJUDA in _classes(irmao)
        for irmao in pai.get_children()
    )


def _descrever(widget: Any) -> str:
    return f"{type(widget).__name__}({(widget.get_text() or '')[:44]!r})"


def test_a_regua_encontra_alvos(aba_montada: Any) -> None:
    """Sem isto, todo teste abaixo pode passar afirmando o vazio."""
    alvos = [w for w in _descer(aba_montada) if _precisa_de_marca(w)]
    assert len(alvos) >= NUNCA_MENOS_QUE, (
        f"a régua achou só {len(alvos)} rótulo(s) com dica na aba montada; "
        "abaixo deste piso o arquivo inteiro passa sem afirmar nada"
    )


def test_nenhum_rotulo_com_dica_fica_invisivel(aba_montada: Any) -> None:
    """A MORDIDA. Rótulo que esconde explicação e não a anuncia reprova."""
    mudos = [w for w in _descer(aba_montada) if _precisa_de_marca(w) and not _marcado(w)]
    assert not mudos, (
        f"{len(mudos)} rótulo(s) da aba Configurações têm dica e NENHUMA marca "
        "visual — quem não sabe que há explicação não passa o mouse para "
        "procurá-la:\n  " + "\n  ".join(_descrever(w) for w in mudos)
    )


def test_todo_titulo_de_secao_com_dica_ganha_a_marca() -> None:
    """O título que esconde dica é sublinhado; o que não esconde, não.

    Conta contra `SECOES_DA_ABA`, que é a fonte de quantas seções há e de quais
    declaram `DICA`. Hoje são quatro de cinco: "A janela" tem `DICA = None`, e
    marca que abre vazio é pior que marca nenhuma — ensina a pessoa a não
    confiar na marca.
    """
    from hefesto_dualsense4unix.app.actions.config.moldura import moldura_de_secao

    esperadas = [s for s in SECOES_DA_ABA if getattr(s, "DICA", None)]
    assert esperadas, "nenhuma seção declara DICA — a régua perdeu o alvo"

    for secao in SECOES_DA_ABA:
        dica = getattr(secao, "DICA", None)
        frame, _caixa = moldura_de_secao(secao.TITULO, dica)
        rotulo = frame.get_label_widget()
        assert CLASSE_TEM_DICA in _classes(rotulo) if dica else True, (
            f'o título da seção "{secao.TITULO}" carrega a dica em silêncio'
        )
        if not dica:
            assert CLASSE_TEM_DICA not in _classes(rotulo), (
                f'a seção "{secao.TITULO}" não tem dica e ganhou marca mesmo '
                "assim — a marca deixa de significar que há explicação"
            )


def test_o_titulo_de_secao_continua_um_rotulo_com_texto() -> None:
    """A regressão de 23/08/2026, e ela custou 13 testes de outras frentes.

    O desenho que punha o `?` ao lado do título trocava o `label_widget` do
    frame por um `Gtk.Box`, e SEIS arquivos de teste acham a seção fazendo
    `frame.get_label_widget().get_text()`. O sintoma foi
    `'Box' object has no attribute 'get_text'`, treze vezes.

    Este teste é o que impede a troca de voltar sem que alguém veja o preço.
    """
    from hefesto_dualsense4unix.app.actions.config.moldura import moldura_de_secao

    for secao in SECOES_DA_ABA:
        rotulo = moldura_de_secao(secao.TITULO, getattr(secao, "DICA", None))[
            0
        ].get_label_widget()
        assert isinstance(rotulo, Gtk.Label), (
            f'o `label_widget` da seção "{secao.TITULO}" virou '
            f"{type(rotulo).__name__} — seis arquivos de teste chamam "
            "`.get_text()` nele"
        )
        assert rotulo.get_text() == secao.TITULO, (
            f"o texto do título saiu {rotulo.get_text()!r}, e não "
            f"{secao.TITULO!r} — as buscas por título deixam de achar a seção"
        )


def test_o_ponto_de_interrogacao_da_mesa_converge(aba_montada: Any) -> None:
    """O `?` que `secao_mesa` já montava à mão ganha o MESMO círculo.

    `secao_mesa._subcabecalho` desenhava um `?` antes de esta cura existir. Se
    ele ficasse de fora, a aba teria duas gramáticas para a mesma ideia — um `?`
    em círculo nos títulos e um `?` solto no sub-cabeçalho. A varredura o acha
    pelo texto, e é por isso que ela não precisou editar `secao_mesa.py`.
    """
    glifos = [
        w
        for w in _descer(aba_montada)
        if isinstance(w, Gtk.Label) and (w.get_text() or "").strip() == "?" and _tem_dica(w)
    ]
    assert glifos, "nenhum `?` de ajuda na aba montada — a régua perdeu o alvo"
    sem_circulo = [w for w in glifos if CLASSE_AJUDA not in _classes(w)]
    assert not sem_circulo, (
        f"{len(sem_circulo)} `?` da aba ficaram sem a classe `{CLASSE_AJUDA}` — "
        "duas gramáticas para a mesma ideia na mesma tela"
    )


def test_o_sublinhado_chega_pontilhado_no_widget(_folha_na_tela: None) -> None:
    """A folha faz a marca EXISTIR na tela, não só passar pelo parser.

    Esta é a metade da mordida que a contagem de classes não cobre: com a regra
    CSS apagada, escrita para outro seletor, ou escrita com o
    `text-decoration-style: dotted` que o GTK3 recusa, todo teste acima continua
    verde e a tela continua sem marca nenhuma.
    """
    janela = Gtk.OffscreenWindow()
    janela.get_style_context().add_class("hefesto-dualsense4unix-window")
    caixa = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
    janela.add(caixa)

    nu = Gtk.Label(label="Configurações")
    marcado = Gtk.Label(label="Configurações")
    marcado.get_style_context().add_class(CLASSE_TEM_DICA)
    caixa.pack_start(nu, False, False, 0)
    caixa.pack_start(marcado, False, False, 0)
    janela.show_all()
    _girar(2000)

    contexto = marcado.get_style_context()
    estado = contexto.get_state()
    borda = contexto.get_border(estado)
    estilo = contexto.get_property("border-bottom-style", estado)

    assert borda.bottom >= 1, (
        "o rótulo com a classe de afordância não tem borda inferior nenhuma — a "
        "regra CSS não chegou ao widget"
    )
    assert estilo.value_nick == "dotted", (
        f"a borda inferior saiu `{estilo.value_nick}`, não `dotted` — a marca do "
        "inventário é o sublinhado PONTILHADO"
    )
    # O rótulo sem a classe continua limpo: a regra não vaza para a aba inteira.
    assert nu.get_style_context().get_border(estado).bottom == 0, (
        "rótulo SEM a classe também ganhou borda — o seletor está largo demais e "
        "a marca deixa de significar 'aqui há explicação'"
    )
    # E a marca custa altura, que é o preço declarado desta cura.
    assert marcado.get_allocation().height > nu.get_allocation().height, (
        "a marca não mudou a altura do rótulo, sinal de que não está sendo "
        "desenhada"
    )
