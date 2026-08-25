"""Refresh por aba: identificação pelo WIDGET, nunca pelo índice da página.

O mapa `page_num -> refresher` era por número. Fundir "Mouse" e "Teclado" na aba
"Navegação DSX" renumerou as páginas seguintes, e um mapa por índice passaria a
chamar o refresher errado **em silêncio** — sem exceção, sem log, só a aba
mostrando dado velho. Estes testes trancam o contrato novo.
"""
from __future__ import annotations

from typing import ClassVar

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


def test_entrar_na_aba_sistema_chama_o_refresher_dela() -> None:
    """T-09 (SISTEMA-O-VIGIA-VIVO-01): a aba que declara saúde relê ao abrir.

    **Correção de fato sobre o que a sprint mediu em 23/08.** Ela dizia que
    *"arrancar a entrada `daemon_box` do mapa não deixa nada vermelho"*. Isso
    caducou: medido em 25/08, comentar a entrada reprova DOIS testes deste
    arquivo (`test_toda_pagina_do_notebook_esta_no_mapa_ou_isenta` e a mordida
    dele), porque a Z0/Z5 passou a exigir que toda página do notebook esteja
    no mapa ou declarada isenta.

    O buraco que sobrou — e que este teste fecha — é OUTRO, e mais fino: o
    portão de hoje confere que o id **está** no mapa, nunca **qual** refresher
    está atrás dele. Medido trocando `_refresh_daemon_tab_on_show` por
    `_refresh_emulation_tab` na tupla do `daemon_box`: os 13 testes deste
    arquivo passaram, e a aba Sistema passaria a rodar o refresher da
    Emulação — mostrando a foto do bootstrap para sempre, calada, que é
    exatamente o defeito F13 que o `_REFRESH_POR_ABA` existe para impedir.
    """
    app = _AppFalso()

    app._on_notebook_switch_page(None, _pagina("daemon_box"), 0)

    assert app.chamados == ["_refresh_daemon_tab_on_show"]


def test_o_refresher_da_aba_sistema_rele_as_tres_coisas_que_ela_mostra() -> None:
    """O nome no mapa só vale se o que está atrás dele fizer o trabalho.

    A aba Sistema mostra TRÊS coisas que envelhecem por caminhos diferentes:

    * o status do daemon — que sobe e cai por fora, pela CLI ou pelo systemd
      (BUG-DAEMON-TAB-STALE-01);
    * o cartão anti-storm — que antes só era populado no bootstrap da aba, e
      ficava obsoleto a sessão inteira quando a cura era instalada por fora;
    * o diagnóstico do detector de janela — que CEGA e VOLTA a ver conforme a
      janela em foco (`window_detect_seeing` decai e volta, JANELA-CEGA-01).

    Sem esta mordida, `_refresh_daemon_tab_on_show` podia perder qualquer uma
    das três e nenhum teste notava.
    """
    from hefesto_dualsense4unix.app.actions.daemon_actions import DaemonActionsMixin

    chamados: list[str] = []

    class _AbaSistemaFalsa:
        _refresh_daemon_tab_on_show = DaemonActionsMixin._refresh_daemon_tab_on_show

        def _refresh_daemon_view_async(self) -> None:
            chamados.append("_refresh_daemon_view_async")

        def _refresh_storm_diag(self) -> None:
            chamados.append("_refresh_storm_diag")

        def _refresh_window_detect_diag(self) -> None:
            chamados.append("_refresh_window_detect_diag")

    _AbaSistemaFalsa()._refresh_daemon_tab_on_show()

    assert chamados == [
        "_refresh_daemon_view_async",
        "_refresh_storm_diag",
        "_refresh_window_detect_diag",
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


# ---------------------------------------------------------------------------
# ONDA0-Z5/T8 — o portão glade→mapa, que faltava
# ---------------------------------------------------------------------------


def _paginas_do_main_notebook_desembrulhadas() -> list[str]:
    """Os ids de Glade das páginas do `main_notebook`, na MESMA forma que
    `_on_notebook_switch_page` vê em runtime — desembrulhando
    `GtkScrolledWindow`/`GtkViewport` como `home_actions.id_da_pagina` faz,
    mas lendo o XML direto (sem montar GTK)."""
    import xml.etree.ElementTree as ET

    from hefesto_dualsense4unix.app.constants import MAIN_GLADE

    def _id_desembrulhado(obj: ET.Element) -> str | None:
        if obj.get("class") in ("GtkScrolledWindow", "GtkViewport"):
            for filho in obj.findall("child"):
                interno = filho.find("object")
                if interno is not None:
                    return _id_desembrulhado(interno)
            return None
        return obj.get("id")

    arvore = ET.parse(str(MAIN_GLADE))
    for nb in arvore.getroot().iter("object"):
        if nb.get("class") == "GtkNotebook" and nb.get("id") == "main_notebook":
            paginas = []
            for filho in nb.findall("child"):
                if filho.get("type") == "tab":
                    continue
                obj = filho.find("object")
                if obj is not None:
                    nome = _id_desembrulhado(obj)
                    if nome is not None:
                        paginas.append(nome)
            return paginas
    raise AssertionError("main_notebook não encontrado no glade")


def test_toda_pagina_do_notebook_esta_no_mapa_ou_isenta() -> None:
    """O lado que faltava (ONDA0-Z5 §2.6): tirar uma aba do mapa não mexia
    em `set(_REFRESH_POR_ABA) - ids_no_glade` (o teste que já existia) — esse
    conjunto só encolhe quando uma aba SAI do glade, nunca quando ela sai do
    mapa. Este teste compara o glade CONTRA o mapa, o lado que faltava.

    Hoje reprova nomeando `tab_status_box` e `tab_no_jogo_box` SE elas não
    estiverem na lista de isenção (`_ISENTAS_DO_REFRESH_POR_ABA`) — as duas
    têm pulso próprio/emprestado (§2.5) e por isso são as isenções vigentes.
    """
    paginas = _paginas_do_main_notebook_desembrulhadas()
    no_mapa = set(HefestoApp._REFRESH_POR_ABA)
    isentas = set(HefestoApp._ISENTAS_DO_REFRESH_POR_ABA)

    sem_dono = [p for p in paginas if p not in no_mapa and p not in isentas]
    assert not sem_dono, (
        f"páginas do notebook fora do mapa de refresh E fora da lista de "
        f"isenção (sem motivo escrito): {sem_dono}. Ou entram em "
        "`_REFRESH_POR_ABA`, ou ganham uma linha nomeada em "
        "`_ISENTAS_DO_REFRESH_POR_ABA` com o motivo — nunca ficam de fora "
        "caladas."
    )

    # Toda isenção declarada precisa de motivo não-vazio — isenção muda ISSO
    # (é uma frase no fonte, não uma ausência).
    for aba, motivo in HefestoApp._ISENTAS_DO_REFRESH_POR_ABA.items():
        assert motivo and motivo.strip(), f"isenção de '{aba}' sem motivo escrito"


def test_mordida_tirar_uma_aba_do_mapa_reprova_nomeando_ela() -> None:
    """A MORDIDA (ONDA0-Z5/T8): tire `tab_lightbar_box` do mapa (sem isentar)
    e o portão tem de reprovar DIZENDO "Lightbar" — a mensagem é o produto
    desta tarefa, não só o booleano."""
    paginas = _paginas_do_main_notebook_desembrulhadas()
    no_mapa_sem_lightbar = set(HefestoApp._REFRESH_POR_ABA) - {"tab_lightbar_box"}
    isentas = set(HefestoApp._ISENTAS_DO_REFRESH_POR_ABA)

    sem_dono = [
        p for p in paginas if p not in no_mapa_sem_lightbar and p not in isentas
    ]
    assert sem_dono == ["tab_lightbar_box"], (
        f"esperava reprovar nomeando 'tab_lightbar_box', achou {sem_dono!r} — "
        "quem lê a falha tem de saber qual aba parou de atualizar"
    )


# ---------------------------------------------------------------------------
# ONDA0-Z5/T9 — um refresher que levanta não cala os outros da mesma aba
# ---------------------------------------------------------------------------


class _AppComRefresherQueLevanta:
    """Dois refreshers na MESMA aba, o primeiro levanta — o dublê que sabe
    RECUSAR (armadilha A2 do COMO-REGER-AGENTES): sem o `try`/`except` do T9,
    o segundo NUNCA roda."""

    _REFRESH_POR_ABA: ClassVar[dict[str, tuple[str, ...]]] = {
        "tab_qualquer_box": ("_primeiro_levanta", "_segundo_roda")
    }
    _ISENTAS_DO_REFRESH_POR_ABA: ClassVar[dict[str, str]] = {}
    _ABA_STATUS = "tab_status_box"
    _on_notebook_switch_page = HefestoApp._on_notebook_switch_page

    def __init__(self) -> None:
        self.segundo_rodou = False

    def _primeiro_levanta(self) -> None:
        raise RuntimeError("refresher quebrado de propósito (T9)")

    def _segundo_roda(self) -> None:
        self.segundo_rodou = True


def test_refresher_que_levanta_nao_cala_o_seguinte_da_mesma_aba(
    caplog: pytest.LogCaptureFixture,
) -> None:
    app = _AppComRefresherQueLevanta()

    # Não pode propagar — a troca de aba não pode quebrar a janela.
    app._on_notebook_switch_page(None, _pagina("tab_qualquer_box"), 0)

    assert app.segundo_rodou is True, (
        "o segundo refresher NÃO rodou — um levantando calou os seguintes "
        "da mesma aba (F13), exatamente o que o try/except do T9 impede"
    )


def test_mordida_sem_o_try_o_segundo_refresher_fica_calado() -> None:
    """A mordida do T9, literal: chama o MESMO laço sem o `try`/`except` (a
    forma de antes) e prova que o segundo refresher realmente dependia dele.
    """
    app = _AppComRefresherQueLevanta()

    with pytest.raises(RuntimeError, match="refresher quebrado"):
        for atributo in app._REFRESH_POR_ABA["tab_qualquer_box"]:
            getattr(app, atributo)()  # SEM try/except — a forma antiga

    assert app.segundo_rodou is False, (
        "sem o try/except, o segundo refresher não deveria rodar — se rodou, "
        "este teste parou de provar o que o T9 mudou"
    )
