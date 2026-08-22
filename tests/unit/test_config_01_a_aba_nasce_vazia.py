"""CONFIG-01 — a décima primeira aba existe, nasce vazia e não custa largura.

O portão da leva da aba Configurações. Enquanto ele não estiver verde, nenhuma
das outras sprints tem onde morar.

O que ele cobra, e por que cada coisa:

1. **A página existe no Glade, com id no box interno.** Medido em 21/08,
   arrancando o id: `id_da_pagina` NÃO devolve `None` — devolve algo como
   `___object_142___`, o nome que o GtkBuilder inventa a partir da POSIÇÃO do
   objeto no arquivo. A página atravessa inteira o `assert None not in nomes`
   de `test_toda_aba_continua_sendo_reconhecida_pelo_id_do_glade` e muda de
   identidade em silêncio no dia em que alguém inserir um objeto antes dela.
   Este é o único teste que cobra o id.
2. **`install_config_tab()` é chamado nos DOIS caminhos de abertura.** A janela
   sobe visível (`show`) ou minimizada na bandeja (`run`, com `start_hidden`),
   e o segundo é o caminho de quem tem autostart. O
   BUG-HOME-TAB-HIDDEN-INSTALL-01 já foi pago uma vez exatamente assim: a aba
   abria em branco para quem começa na bandeja. Não havia teste guardando as
   duas listas; este é ele.
3. **O mixin está na MRO.** Sem a base, `install_config_tab` não existe no
   objeto e o `show()` estoura.
4. **A fita de alvo esmaece nesta aba e VOLTA nas outras.** O seletor de
   controle do cabeçalho não tem sentido aqui — o que se declara nesta aba vale
   para a mesa inteira. Esmaecer e nunca devolver seria pior que não esmaecer.
5. **A aba montada PELO MIXIN cabe na janela.**
   `tests/unit/test_layout_orcamento_altura.py` carrega o `main.glade` CRU e não
   roda `install_*_tab` nenhum: ele não veria uma linha sequer do que esta aba
   monta em código. Um portão que olha para o lugar errado é pior que portão
   nenhum, porque encerra a busca. Aqui a aba é MONTADA e só então medida.
"""
from __future__ import annotations

from tests.conftest import exigir_gi_real

# GUARDA-GI-REAL-01: vem antes de qualquer import de `gi` de propósito.
# `pytest.importorskip("gi")` ACEITA o stub que outro arquivo planta em
# sys.modules; e sem guarda nenhuma este módulo derruba a COLETA inteira
# no CI headless, em vez de pular.
exigir_gi_real("aba configurações")

import ast
import inspect
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

_gi = pytest.importorskip("gi", reason="precisa de PyGObject")
_gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

from hefesto_dualsense4unix.app.actions.config_actions import (
    ABA_CONFIG,
    SECOES,
    ConfigActionsMixin,
)
from hefesto_dualsense4unix.app.constants import MAIN_GLADE

#: O rótulo da aba, como a pessoa o lê na tira.
ROTULO_DA_ABA = "Configurações"


def _largura_da_janela() -> int:
    """A `default-width` do próprio glade — nunca uma constante copiada.

    Mesma disciplina de `test_layout_orcamento_altura._dimensao_da_janela`: um
    número duplicado aqui viraria mentira no dia em que a janela mudasse de
    tamanho, e o teste seguiria verde medindo contra uma largura morta.
    """
    arvore = ET.parse(str(MAIN_GLADE))
    for obj in arvore.iter("object"):
        if obj.get("id") != "main_window":
            continue
        for prop in obj.findall("property"):
            if prop.get("name") == "default-width":
                return int((prop.text or "0").strip())
    raise AssertionError("default-width não encontrado em main_window")


def _arvore_do_app() -> ast.Module:
    """O `app.py` lido como árvore de sintaxe, sem importar a janela."""
    from hefesto_dualsense4unix.app import app as modulo_app

    fonte = Path(inspect.getfile(modulo_app)).read_text(encoding="utf-8")
    return ast.parse(fonte)


def _metodos_de(nome_da_classe: str, arvore: ast.Module) -> dict[str, ast.FunctionDef]:
    for no in arvore.body:
        if isinstance(no, ast.ClassDef) and no.name == nome_da_classe:
            return {
                filho.name: filho
                for filho in no.body
                if isinstance(filho, ast.FunctionDef)
            }
    raise AssertionError(f"classe {nome_da_classe} não encontrada em app.py")


def _chama(metodo: ast.FunctionDef, nome: str) -> bool:
    """Este trecho de código chama ``self.<nome>()`` em algum ponto?"""
    for no in ast.walk(metodo):
        if not isinstance(no, ast.Call):
            continue
        alvo = no.func
        if isinstance(alvo, ast.Attribute) and alvo.attr == nome:
            return True
    return False


# --- 1. A página existe no Glade -------------------------------------------


def test_a_pagina_existe_no_glade_com_id_no_box_interno() -> None:
    """O box de conteúdo tem id, e a aba tem rótulo.

    Mordida: apagar o `id="tab_config_box"` do glade.
    """
    arvore = ET.parse(str(MAIN_GLADE))
    ids = {obj.get("id") for obj in arvore.iter("object")}

    assert ABA_CONFIG in ids, (
        f"nenhum objeto com id={ABA_CONFIG!r} no glade. Sem id no box interno "
        "a página NÃO vira `None` para `id_da_pagina` — vira um nome inventado "
        "a partir da posição no arquivo (`___object_NNN___`), que muda sozinho "
        "quando alguém insere um objeto antes dela. Os pollers passariam a "
        "perguntar por uma aba que não existe mais, em silêncio."
    )
    assert "scroll_tab_config_box" in ids, (
        "a página precisa do rolador próprio, como a aba Início: é ele que faz "
        "`_wrap_notebook_pages_in_scroll` pular esta página em vez de "
        "embrulhá-la de novo."
    )


def test_a_aba_tem_rotulo_na_tira() -> None:
    """Existe um `<child type="tab">` com o rótulo Configurações.

    Mordida: trocar o texto do rótulo no glade.
    """
    arvore = ET.parse(str(MAIN_GLADE))
    rotulos = {
        (prop.text or "").strip()
        for filho in arvore.iter("child")
        if filho.get("type") == "tab"
        for obj in filho.iter("object")
        for prop in obj.findall("property")
        if prop.get("name") == "label"
    }

    assert ROTULO_DA_ABA in rotulos, (
        f"nenhuma aba rotulada {ROTULO_DA_ABA!r} na tira: {sorted(rotulos)}"
    )


def test_a_aba_nova_e_a_ultima_da_tira() -> None:
    """A ordem importa: a aba nasce no FIM, depois de Navegação.

    Mordida: mover o bloco da página para antes de outra aba.
    """
    builder = Gtk.Builder()
    builder.add_from_file(str(MAIN_GLADE))
    notebook = builder.get_object("main_notebook")
    rotulos = [
        notebook.get_tab_label_text(notebook.get_nth_page(i))
        for i in range(notebook.get_n_pages())
    ]

    assert rotulos[-1] == ROTULO_DA_ABA, (
        f"a aba nova tem de ser a última da tira; hoje: {rotulos}"
    )


# --- 2. Os DOIS caminhos de abertura ---------------------------------------


@pytest.mark.parametrize("caminho", ["show", "run"])
def test_a_aba_e_instalada_nos_dois_caminhos_de_abertura(caminho: str) -> None:
    """`show()` E `run()` chamam `install_config_tab`.

    O `run()` é o caminho de quem sobe minimizado na bandeja. Esquecer a
    segunda chamada repete o BUG-HOME-TAB-HIDDEN-INSTALL-01: a janela abre com
    a aba em branco, e nada acusa.

    Mordida: apagar `self.install_config_tab()` de um dos dois blocos.
    """
    metodos = _metodos_de("HefestoApp", _arvore_do_app())

    assert caminho in metodos, f"HefestoApp não tem mais o método {caminho!r}"
    assert _chama(metodos[caminho], "install_config_tab"), (
        f"`{caminho}()` não chama `install_config_tab()`. As duas listas de "
        "`install_*` têm de andar juntas: a visível e a da bandeja."
    )


def test_a_fita_de_alvo_e_avisada_a_cada_troca_de_aba() -> None:
    """O gancho mora em `_on_notebook_switch_page`, não no mapa de refresh.

    `_REFRESH_POR_ABA` só dispara ao ENTRAR na aba destino — pendurar o gancho
    ali deixaria a fita esmaecida para sempre depois da primeira visita.

    Mordida: mover a chamada para dentro de `_REFRESH_POR_ABA`.
    """
    metodos = _metodos_de("HefestoApp", _arvore_do_app())

    assert "_on_notebook_switch_page" in metodos
    assert _chama(metodos["_on_notebook_switch_page"], "get"), (
        "instrumento inválido: este método deveria ler `_REFRESH_POR_ABA`"
    )
    fonte = ast.dump(metodos["_on_notebook_switch_page"])
    assert "set_alvo_inativo" in fonte, (
        "`_on_notebook_switch_page` não avisa a fita de alvo. Sem isso a fita "
        "nunca esmaece — ou, pior, esmaece uma vez e nunca volta."
    )


# --- 3. O mixin está na MRO ------------------------------------------------


def test_o_mixin_esta_na_mro_do_app() -> None:
    """Sem a base, `install_config_tab` não existe no objeto e o `show()` estoura.

    Mordida: tirar `ConfigActionsMixin` da lista de bases de `HefestoApp`.
    """
    from hefesto_dualsense4unix.app.app import HefestoApp

    assert ConfigActionsMixin in HefestoApp.__mro__, (
        "ConfigActionsMixin fora da MRO de HefestoApp: "
        f"{[base.__name__ for base in HefestoApp.__mro__]}"
    )
    assert callable(getattr(HefestoApp, "install_config_tab", None))


# --- 4. A fita de alvo esmaece e VOLTA -------------------------------------


class _HospedeiroDaFita(ConfigActionsMixin):
    """Hospedeiro mínimo: só a fita do cabeçalho, dentro de um pai de verdade.

    O rótulo da razão nasce ao LADO da fita, e para isso precisa de um pai —
    daí o cabeçalho.
    """

    def __init__(self) -> None:
        self.cabecalho = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        faixa = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.cabecalho.pack_end(faixa, False, False, 0)
        self._target_strip = faixa


def test_a_fita_esmaece_na_aba_e_volta_fora_dela() -> None:
    """Ida E volta, no mesmo teste — esmaecer sem devolver é o defeito.

    Mordida: trocar o argumento de `set_alvo_inativo` por um `True` fixo.
    """
    host = _HospedeiroDaFita()
    faixa = host._target_strip

    assert faixa.get_sensitive(), "instrumento inválido: a fita já nasceu inerte"

    host.set_alvo_inativo(True)
    assert not faixa.get_sensitive(), (
        "a fita continuou respondendo na aba Configurações"
    )

    host.set_alvo_inativo(False)
    assert faixa.get_sensitive(), (
        "a fita não voltou ao sair da aba — o seletor de controle das outras "
        "abas ficaria morto até reabrir a janela"
    )


def test_a_razao_aparece_junto_com_o_esmaecimento() -> None:
    """Um widget que não responde sem dizer por quê é defeito, não desenho.

    Mordida: apagar o `razao.show()` do mixin.
    """
    host = _HospedeiroDaFita()

    host.set_alvo_inativo(True)
    razao = host._alvo_inativo_label
    assert razao is not None, "nenhum rótulo de razão foi criado"
    assert razao.get_visible(), "a razão não apareceu junto com o esmaecimento"
    assert razao.get_parent() is host.cabecalho, (
        "a razão nasceu DENTRO da fita: ela sairia esmaecida junto com aquilo "
        "que explica"
    )

    host.set_alvo_inativo(False)
    assert not razao.get_visible(), "a razão ficou na tela fora da aba"


def test_a_fita_ausente_nao_derruba_nada() -> None:
    """Saída cedo tolerante: hospedeiro sem fita não pode levantar.

    Mordida: tirar a guarda `if faixa is None: return`.
    """

    class _SemFita(ConfigActionsMixin):
        pass

    _SemFita().set_alvo_inativo(True)


# --- 5. A aba MONTADA cabe na janela ---------------------------------------


def _montar_a_aba() -> tuple[Gtk.Builder, Gtk.Widget]:
    """Carrega o glade e roda o mixin — é a aba de VERDADE que se mede aqui."""

    class _HospedeiroDaAba(ConfigActionsMixin):
        def __init__(self, builder: Gtk.Builder) -> None:
            self.builder = builder

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
    janela.show_all()
    while Gtk.events_pending():
        Gtk.main_iteration()
    return builder, pagina


def test_a_aba_nasce_com_as_cinco_secoes_e_nada_mais() -> None:
    """Vazia é o aceite: cinco títulos, zero widget de conteúdo.

    Mordida: acrescentar qualquer widget ao `install_config_tab`.
    """
    builder, _pagina = _montar_a_aba()
    caixa = builder.get_object(ABA_CONFIG)
    filhos = caixa.get_children()

    assert len(filhos) == len(SECOES), (
        f"a aba nasceu com {len(filhos)} widgets e as seções são "
        f"{len(SECOES)}. Nesta entrega a aba é VAZIA: só os títulos."
    )
    assert [f.get_text() for f in filhos] == [titulo for titulo, _ in SECOES]
    assert all(isinstance(f, Gtk.Label) for f in filhos), (
        "conteúdo entrou na aba antes da hora"
    )


def test_a_instalacao_e_idempotente() -> None:
    """Chamar duas vezes não duplica seção.

    Os dois caminhos de abertura podem, em tese, se cruzar. E o `show()` roda
    depois do `run()` no ramo da bandeja.

    Mordida: apagar o `getattr(self, "_config_installed", False)` da guarda.
    """

    class _Hospedeiro(ConfigActionsMixin):
        def __init__(self, builder: Gtk.Builder) -> None:
            self.builder = builder

    builder = Gtk.Builder()
    builder.add_from_file(str(MAIN_GLADE))
    host = _Hospedeiro(builder)
    host.install_config_tab()
    host.install_config_tab()

    assert len(builder.get_object(ABA_CONFIG).get_children()) == len(SECOES)


def test_a_aba_montada_cabe_na_largura_da_janela() -> None:
    """A medição que o portão de layout não faz: a aba MONTADA, não o glade cru.

    A largura é o recurso escasso: a rolagem horizontal é `never`, então o
    mínimo da página mais larga vira o mínimo da janela, sem escape.

    Mordida: pôr um rótulo de uma linha só, sem quebra, com um parágrafo
    inteiro dentro.
    """
    _builder, pagina = _montar_a_aba()
    largura_da_janela = _largura_da_janela()

    largura, _natural = pagina.get_preferred_width()

    assert largura <= largura_da_janela, (
        f"a aba Configurações pede {largura}px de largura mínima e a janela "
        f"abre com {largura_da_janela}px ({largura - largura_da_janela}px a "
        "mais). Sem rolagem horizontal, esse mínimo sobe intacto até a janela."
    )


def test_nenhum_titulo_promete_numero() -> None:
    """Rótulo estático é honesto; valor inventado não é.

    A aba nasce sem uma única medição feita. Um número na tela agora seria
    ilustração se passando por leitura — exatamente o que o desenho avisa sobre
    os endereços e os `831 / 1600` do mockup.

    Mordida: escrever um número em qualquer título de seção.
    """
    for titulo, dica in SECOES:
        assert not any(caractere.isdigit() for caractere in titulo), (
            f"o título {titulo!r} promete um número que ninguém mediu"
        )
        if dica is not None:
            assert not any(caractere.isdigit() for caractere in dica), (
                f"a dica de {titulo!r} promete um número que ninguém mediu"
            )
