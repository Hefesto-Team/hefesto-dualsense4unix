"""Refresh por aba: identificação pelo WIDGET, nunca pelo índice da página.

O mapa `page_num -> refresher` era por número. Fundir "Mouse" e "Teclado" na aba
"Navegação DSX" renumerou as páginas seguintes, e um mapa por índice passaria a
chamar o refresher errado **em silêncio** — sem exceção, sem log, só a aba
mostrando dado velho. Estes testes trancam o contrato novo.
"""
from __future__ import annotations

from tests.conftest import exigir_gi_real

# GUARDA-GI-REAL-01: vem antes de qualquer import de `gi` de propósito.
# `pytest.importorskip("gi")` ACEITA o stub que outro arquivo planta em
# sys.modules; e sem guarda nenhuma este módulo derruba a COLETA inteira
# no CI headless, em vez de pular.
exigir_gi_real("notebook switch page")

import pytest

_gi = pytest.importorskip("gi", reason="precisa de PyGObject")
_gi.require_version("Gtk", "3.0")
# CI-TYPELIB-PARCIAL-01: `importorskip("gi")` não basta. O módulo `gi` pode
# existir sem as TYPELIBS que o app usa — é o estado do runner do GitHub, onde
# `import gi` funciona e `from gi.repository import GdkPixbuf` estoura
# `ImportError: unknown location`. Como o erro acontece na COLETA, ele não vira
# skip: derruba a suíte inteira com "errors during collection" e reprovou o
# release da v0.1.1. Pular exige checar a typelib que este módulo puxa de
# verdade, e `app.py` importa GdkPixbuf.
pytest.importorskip(
    "gi.repository.GdkPixbuf", reason="precisa da typelib GdkPixbuf"
)
from gi.repository import Gtk

from hefesto_dualsense4unix.app.app import HefestoApp



class _AppFalso:
    """Só o suficiente para exercitar `_on_notebook_switch_page` sem GUI real."""

    _REFRESH_POR_ABA = HefestoApp._REFRESH_POR_ABA
    _ABA_STATUS = HefestoApp._ABA_STATUS
    _on_notebook_switch_page = HefestoApp._on_notebook_switch_page

    def __init__(self) -> None:
        self.chamados: list[str] = []
        self.status_visivel: list[bool] = []
        for nomes in self._REFRESH_POR_ABA.values():
            for nome in nomes:
                setattr(self, nome, lambda n=nome: self.chamados.append(n))

    def set_status_tab_visivel(self, visivel: bool) -> None:
        self.status_visivel.append(visivel)


def _pagina(nome: str) -> Gtk.Widget:
    page = Gtk.Box()
    Gtk.Buildable.set_name(page, nome)
    return page


def test_aba_unificada_roda_os_tres_refreshers() -> None:
    """"Navegação DSX" herda o de Mouse, o de Teclado e o interruptor do teclado.

    O terceiro entrou em 22/08/2026 (SEGUNDO-ESCRITOR-01): o gesto PS + R3 da
    ponte mouse+teclado chama `set_keyboard_emulation` em processo
    (`daemon/subsystems/hotkey.py`, `_aplicar_ponte`) e persiste a escolha, então
    o interruptor que DESENHA nesta aba passou a poder estar virado quando ela
    entra. Enquanto esta janela era o único escritor da flag, relê-lo aqui não
    corrigia staleness nenhuma — e a lista tinha dois nomes por essa razão
    medida, não por esquecimento.

    Mordida: tirei `_refresh_keyboard_switch` da tupla em `app.py` e este teste
    reprovou com a lista de dois. Quem guarda o POR QUÊ — que existe um segundo
    escritor da flag — é o portão do gesto em
    `tests/unit/test_fiacao_da_janela_teclado_e_detector.py`, que reprovou junto.
    """
    app = _AppFalso()

    app._on_notebook_switch_page(None, _pagina("tab_navegacao_dsx"), 8)

    assert app.chamados == [
        "_refresh_mouse_tab",
        "_refresh_key_bindings_from_draft",
        "_refresh_keyboard_switch",
    ]


def test_entrar_na_aba_perfis_rele_a_caixinha_do_steam_input() -> None:
    """DUAS-ABAS-UM-ARQUIVO-01: a allowlist tem escritores fora da aba Perfis.

    A caixinha do Steam Input desenha um arquivo que o botão "Este jogo não
    funciona" (`daemon_actions.on_steam_game_broken`) e o `gamepad steam-input
    remove` (`cli/cmd_steam.py`) escrevem sem passar por esta aba. Ela só se
    sincronizava ao ABRIR o editor, então com o editor já aberto a caixa
    continuava mostrando o arquivo de antes — e o tooltip do botão da aba
    Sistema manda desmarcar justamente ali.

    Mordida: tirei `_sincronizar_caixa_do_steam_input` da tupla de
    `profiles_paned` e este teste reprovou com a lista de um nome só. O efeito
    na tela — a caixa virando sozinha depois de uma escrita por fora — é medido
    com widget de verdade em
    `tests/unit/test_a_caixinha_que_tira_do_steam_input.py`.
    """
    app = _AppFalso()

    app._on_notebook_switch_page(None, _pagina("profiles_paned"), 0)

    assert app.chamados == [
        "_sync_selection_with_active_profile",
        "_sincronizar_caixa_do_steam_input",
    ]


def test_pagina_dentro_de_scrolledwindow_ainda_e_reconhecida() -> None:
    """`_wrap_notebook_pages_in_scroll` embrulha cada página; o id fica no filho.

    Sem desembrulhar, NENHUMA aba dispararia refresh — o widget que chega no
    handler seria o scroller anônimo.
    """
    app = _AppFalso()
    scroller = Gtk.ScrolledWindow()
    scroller.add(_pagina("tab_triggers_box"))

    app._on_notebook_switch_page(None, scroller, 2)

    assert app.chamados == ["_refresh_triggers_from_draft"]


def test_aba_sem_refresher_nao_quebra() -> None:
    """Status não tem refresher no mapa (ele roda por polling próprio)."""
    app = _AppFalso()

    app._on_notebook_switch_page(None, _pagina("tab_status_box"), 1)

    assert app.chamados == []


def test_entrar_no_status_liga_a_captura_do_microfone() -> None:
    """S2: o medidor de mic só captura com a aba Status à vista."""
    app = _AppFalso()

    app._on_notebook_switch_page(None, _pagina("tab_status_box"), 1)

    assert app.status_visivel == [True]


def test_sair_do_status_desliga_a_captura() -> None:
    """Sem isto, um `parec` por controle seguiria segurando o microfone da
    usuária com a janela em qualquer outra aba — o incidente de busy-loop da
    v3.8.1 com outra roupa."""
    app = _AppFalso()
    app._on_notebook_switch_page(None, _pagina("tab_status_box"), 1)

    app._on_notebook_switch_page(None, _pagina("tab_triggers_box"), 2)

    assert app.status_visivel == [True, False]


def test_id_da_aba_status_existe_no_glade() -> None:
    """O gate do microfone casa por id de Glade; id errado erra em silêncio."""
    import xml.etree.ElementTree as ET

    from hefesto_dualsense4unix.app.constants import MAIN_GLADE

    arvore = ET.parse(str(MAIN_GLADE))
    ids = {obj.get("id") for obj in arvore.iter("object") if obj.get("id")}

    assert HefestoApp._ABA_STATUS in ids


def test_todo_id_do_mapa_existe_no_glade() -> None:
    """Um id errado no mapa falha em SILÊNCIO — é o bug que isto previne."""
    import xml.etree.ElementTree as ET

    from hefesto_dualsense4unix.app.constants import MAIN_GLADE

    arvore = ET.parse(str(MAIN_GLADE))
    ids_no_glade = {
        obj.get("id") for obj in arvore.iter("object") if obj.get("id")
    }

    faltando = set(HefestoApp._REFRESH_POR_ABA) - ids_no_glade
    assert not faltando, (
        f"ids no mapa de refresh que não existem no glade: {sorted(faltando)}"
    )


def test_nenhuma_aba_aparece_duas_vezes_no_mapa_de_refresh() -> None:
    """Chave repetida no literal some em silêncio, e cinco frentes disputam uma.

    Um dicionário literal com a mesma chave duas vezes NÃO é erro em Python: o
    interpretador fica com a última e descarta a primeira sem uma palavra. Na
    leva da aba Configurações isso quase aconteceu — cinco sprints precisavam
    pendurar um refresher em `tab_config_box`, e a segunda a chegar teria
    apagado a primeira. O sintoma seria uma seção que simplesmente não atualiza
    ao entrar na aba, sem erro, sem log, sem teste vermelho.

    O mapa em memória não guarda a duplicata — ela já se perdeu no parse. Por
    isso este teste lê o FONTE e conta as chaves escritas.

    Mordida: escrevi `ABA_CONFIG: ("_reexaminar_a_mesa",)` uma segunda vez
    dentro do literal e o teste reprovou apontando a chave; sem ele, a suíte
    inteira segue verde e o exame da mesa para de rodar.
    """
    import ast
    from pathlib import Path

    fonte = Path(__file__).resolve().parents[2] / (
        "src/hefesto_dualsense4unix/app/app.py"
    )
    arvore = ast.parse(fonte.read_text(encoding="utf-8"))

    literais = [
        no.value
        for no in ast.walk(arvore)
        if isinstance(no, ast.AnnAssign)
        and isinstance(no.target, ast.Name)
        and no.target.id == "_REFRESH_POR_ABA"
        and isinstance(no.value, ast.Dict)
    ]
    assert literais, "não achei o literal de `_REFRESH_POR_ABA` em `app.py`"

    escritas = [
        chave.value if isinstance(chave, ast.Constant) else ast.unparse(chave)
        for chave in literais[0].keys
        if chave is not None
    ]
    repetidas = sorted({c for c in escritas if escritas.count(c) > 1})

    assert not repetidas, (
        f"chave repetida em `_REFRESH_POR_ABA`: {repetidas}. Python fica com a "
        "última e descarta as anteriores sem erro — junte os refreshers numa "
        "tupla só."
    )
