"""A foto de cada aba mostra o que o CÓDIGO desenha, não o que o XML escreve.

P10 (23/08/2026). Cinco das onze abas não tinham host no
`scripts/gui-captura/retratar_abas.py` — Lightbar, Rumble, Sistema, Emulação e
Navegação —, e por isso o `README.md` publicava o **glade cru** delas. Não é
uma imperfeição estética: a foto AFIRMAVA coisas que o produto já tinha parado
de dizer.

O que a documentação publicava, medido no glade:

* Emulação — ``Device: Microsoft X-Box 360 pad`` e ``Buffer: 150``. Os dois são
  o default do XML, e a `BUG-EMULATION-HOTKEY-CARD-FIXO-01` os substituiu
  justamente porque afirmavam estado LIDO onde havia constante de compilação;
  hoje a tela escreve ``150 (padrão)``, que é a verdade disponível;
* Navegação — ``Formato: KEY_* (ex: KEY_C, KEY_ENTER) ou
  __OPEN_OSK__/__CLOSE_OSK__``, a legenda de jargão que a KBD-01 trocou por
  texto de gente;
* Sistema — ``Diagnóstico ao abrir a aba…`` e ``consultando…``, estados de
  ESPERA publicados como se fossem a tela;
* Lightbar — ``Aceso agora: consultando…``, idem;
* Rumble — ``Estado da vibração: —``, o rótulo que é o assunto da aba.

Custo composto, e é por ele que este portão existe: a regra desta casa manda
OLHAR A FOTO primeiro. Uma foto que mente contamina todo trabalho que vem
depois — inclusive o planejamento de quem nunca abriu a janela.

POR QUE ESTE TESTE NÃO CONTA HOSTS
-----------------------------------

Um teste que afirmasse *"o script tem onze funções `_montar_aba_*`"* mediria a
LISTA, não o efeito: bastaria um host que roda e não pinta nada para ele
continuar verde. A régua aqui é o EFEITO — o texto que só existe no XML tem de
sumir da árvore montada. Cada linha da tabela abaixo é conferida dos DOIS
lados: o teste primeiro exige que a frase esteja mesmo no `main.glade` (senão a
régua está medindo um fantasma) e só então exige que ela não sobreviva à
montagem.

A MORDIDA
---------

Arranque a chamada de qualquer um dos cinco `_montar_aba_*` do `main` — ou o
corpo de um deles — e o teste reprova nomeando a aba, a frase do XML que voltou
a ser publicada e o widget onde ela apareceu.
"""

from __future__ import annotations

from tests.conftest import exigir_gi_real

# GUARDA-GI-REAL-01: antes de qualquer import de `gi`. Contra o stub da suíte
# (`Gtk.Box = object`) a varredura de rótulos deste arquivo devolveria lista
# vazia e TODAS as asserções passariam sem que widget nenhum existisse.
exigir_gi_real("as onze abas da foto da documentação")

import ast
import importlib.util
from pathlib import Path
from typing import Any

import gi

gi.require_version("Gtk", "3.0")

from gi.repository import Gtk

RAIZ = Path(__file__).resolve().parents[2]
SCRIPT = RAIZ / "scripts" / "gui-captura" / "retratar_abas.py"
GLADE = RAIZ / "src" / "hefesto_dualsense4unix" / "gui" / "main.glade"

#: Os rótulos em que a montagem TEM de mudar o que o XML escreve.
#:
#: `(aba, id da página no glade, id do widget, o que a foto perde sem isso)`.
#:
#: **Não há frase copiada à mão nesta tabela, e isso é deliberado.** A régua lê
#: o texto do glade CRU do próprio `main.glade`, na hora, e cobra que o texto
#: da árvore MONTADA seja diferente dele. Uma tabela de frases envelheceria em
#: silêncio no dia em que alguém editasse o XML — e um portão que se apaga
#: junto com o que mede não é portão.
_ROTULOS_QUE_O_CODIGO_REESCREVE: tuple[tuple[str, str, str, str], ...] = (
    (
        "Lightbar",
        "tab_lightbar_box",
        "player_leds_estado",
        "a frase que diz QUAL desenho está aceso e por decisão de quem "
        "(o XML publica “Aceso agora: consultando…”)",
    ),
    (
        "Rumble",
        "tab_rumble_box",
        "rumble_state_label",
        "se o JOGO controla a vibração ou se ela está travada pela janela "
        "(o XML publica “Estado da vibração: —”)",
    ),
    (
        "Sistema",
        "daemon_box",
        "storm_diag_label",
        "as linhas do cartão “Saúde do sistema” (o XML publica o texto de "
        "espera “Diagnóstico ao abrir a aba…”)",
    ),
    (
        "Sistema",
        "daemon_box",
        "window_detect_diag_label",
        "se o perfil troca sozinho ao abrir o jogo, e o que está na frente "
        "(o XML publica “consultando…”)",
    ),
    (
        "Sistema",
        "daemon_box",
        "daemon_status_label",
        "a resposta da primeira pergunta da aba — o Hefesto está funcionando?",
    ),
    (
        "Emulação",
        "emulation_box",
        "emulation_device_name_label",
        "o nome do aparelho que a máscara ATIVA cria, que nem sempre é o Xbox "
        "(o XML publica “Microsoft X-Box 360 pad”)",
    ),
    (
        "Emulação",
        "emulation_box",
        "emulation_combo_buffer_label",
        'o sufixo "(padrão)", que separa fábrica de estado lido do daemon '
        "(o XML publica o número seco, indistinguível de leitura)",
    ),
    (
        "Emulação",
        "emulation_box",
        "emulation_steam_input_status_label",
        "o veredito do Steam Input, que é o assunto da linha",
    ),
    (
        "Navegação",
        "tab_navegacao_dsx",
        "key_bindings_legend",
        "a legenda em português que a KBD-01 pôs no lugar do jargão "
        "(o XML publica “Formato: KEY_* … __OPEN_OSK__”)",
    ),
)


def _script() -> Any:
    """Importa o retrato como módulo, sem rodar o `main` (nenhuma foto sai)."""
    assert SCRIPT.is_file(), f"{SCRIPT} sumiu — o retrato das abas é rotina desta casa"
    spec = importlib.util.spec_from_file_location("_retratar_abas_sob_p10", SCRIPT)
    assert spec is not None and spec.loader is not None
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def _rotulos(raiz: Any) -> list[Any]:
    """Todo `Gtk.Label` abaixo de `raiz`, em qualquer profundidade."""
    achados: list[Any] = []
    if isinstance(raiz, Gtk.Label):
        achados.append(raiz)
    if isinstance(raiz, Gtk.Container):
        for filho in raiz.get_children():
            achados.extend(_rotulos(filho))
    return achados


def _janela_montada() -> tuple[Any, Any]:
    """Monta as onze abas como o `main` monta, offscreen, sem gravar PNG.

    A ordem é a do `main` — a Emulação antes da Navegação, porque a chave do
    teclado emulado desenha numa aba e é montada pelo mixin da outra.
    """
    modulo = _script()
    builder = Gtk.Builder()
    builder.add_from_file(str(modulo.GLADE))
    notebook = builder.get_object("main_notebook")
    assert notebook is not None, "`main_notebook` sumiu do glade"

    janela = Gtk.OffscreenWindow()
    pai = notebook.get_parent()
    if pai is not None:
        pai.remove(notebook)
    janela.add(notebook)
    janela.set_size_request(modulo.LARGURA, modulo.ALTURA)
    janela.show_all()

    modulo._injetar_card(builder)
    modulo._injetar_modos_de_gatilho(builder)
    modulo._montar_aba_inicio(builder)
    modulo._montar_aba_no_jogo(builder)
    modulo._montar_aba_perfis(builder)
    modulo._montar_aba_configuracoes(builder)
    modulo._montar_aba_lightbar(builder)
    modulo._montar_aba_rumble(builder)
    modulo._montar_aba_sistema(builder)
    modulo._montar_aba_emulacao(builder)
    modulo._montar_aba_navegacao(builder)
    modulo._assentar()
    return modulo, builder


def _janela_crua() -> Any:
    """O glade CRU, sem montagem nenhuma — é o que a foto publicava antes.

    É a outra metade da régua, e ela vale mais que uma lista de frases: o texto
    de comparação sai do `main.glade` na hora, então editar o XML não deixa
    este portão medindo um fantasma.
    """
    builder = Gtk.Builder()
    builder.add_from_file(str(GLADE))
    return builder


def test_a_regua_tem_o_que_medir_no_glade_cru() -> None:
    """Ancora a premissa: cada rótulo da tabela EXISTE e tem texto no XML.

    Sem esta âncora, um widget renomeado (ou um rótulo que nasceu vazio no
    glade) deixaria a comparação abaixo verde sem medir montagem nenhuma.
    """
    cru = _janela_crua()
    problemas: list[str] = []
    for aba, _pagina, widget, _perda in _ROTULOS_QUE_O_CODIGO_REESCREVE:
        alvo = cru.get_object(widget)
        if alvo is None:
            problemas.append(f"{aba}: `{widget}` não existe mais no glade")
        elif not alvo.get_text().strip():
            problemas.append(f"{aba}: `{widget}` nasce vazio no glade")
    assert not problemas, (
        "a régua deste portão perdeu o que ela mede: "
        + "; ".join(problemas)
        + ". Se o widget mudou de nome, atualize a tabela; se morreu, tire a "
        "linha — nunca deixe a linha apontando para o nada."
    )


def test_nenhuma_aba_e_fotografada_com_o_texto_do_glade_cru() -> None:
    """O EFEITO: o texto da árvore montada é DIFERENTE do texto do XML.

    Mordida: arranque `_montar_aba_navegacao` (ou qualquer um dos outros
    quatro) do `main` do retrato, ou o corpo dele, e esta asserção reprova
    dizendo a aba, o widget, a frase que voltou ao README e o que a foto perde.
    """
    cru = _janela_crua()
    _modulo, builder = _janela_montada()

    sobreviventes: list[str] = []
    for aba, pagina, widget, perda in _ROTULOS_QUE_O_CODIGO_REESCREVE:
        alvo = builder.get_object(widget)
        assert alvo is not None, f"`{widget}` sumiu do glade (aba {aba})"
        do_xml = cru.get_object(widget).get_text()
        if alvo.get_text() == do_xml:
            sobreviventes.append(
                f"{aba}: `{widget}` foi fotografado com o texto do XML "
                f"({do_xml!r}) — a foto perde {perda}"
            )
            continue
        # A segunda metade da régua: o host pode ter pintado o widget certo e
        # deixado a frase viva em OUTRO rótulo VISÍVEL da mesma página (um
        # `_get` que resolveu o id errado, um rótulo duplicado no glade). Uma
        # foto com a frase em qualquer lugar da página continua publicando o
        # XML.
        #
        # Só vale para texto DISTINTIVO, e o critério sai do próprio XML: se a
        # página crua já repete aquele texto (o "—" neutro de "ainda não sei"
        # mora em quatro rótulos da Emulação), ele não identifica widget nenhum
        # e a varredura acusaria quem fez a coisa certa. Portão que reprova o
        # acerto ensina a próxima pessoa a desligá-lo — esta casa já pagou isso
        # em 13/08.
        caixa_crua = cru.get_object(pagina)
        assert caixa_crua is not None, f"`{pagina}` sumiu do glade (aba {aba})"
        if sum(1 for r in _rotulos(caixa_crua) if r.get_text() == do_xml) > 1:
            continue
        caixa = builder.get_object(pagina)
        assert caixa is not None, f"`{pagina}` sumiu do glade (aba {aba})"
        eco = [
            rotulo
            for rotulo in _rotulos(caixa)
            if rotulo.get_text() == do_xml and rotulo.get_visible()
        ]
        if eco:
            sobreviventes.append(
                f"{aba}: o texto do XML ({do_xml!r}) sobreviveu em outro rótulo "
                f"visível da página `{pagina}` — a foto perde {perda}"
            )

    assert not sobreviventes, (
        "a foto da documentação voltou a publicar o glade cru:\n  "
        + "\n  ".join(sobreviventes)
        + "\n\nA regra desta casa manda OLHAR A FOTO primeiro; uma foto que "
        "mente contamina todo trabalho que vem depois dela."
    )


def test_o_main_monta_as_onze_abas() -> None:
    """As cinco funções podem existir e não ser chamadas — foi assim por meses.

    Verificação sobre o AST do `main`: uma menção em comentário ou em docstring
    não monta aba nenhuma. É o irmão do
    `test_a_aba_perfis_na_foto.test_o_main_monta_a_aba_perfis`, e nasce da mesma
    história — a função da aba Perfis existiu antes de ser chamada.
    """
    arvore = ast.parse(SCRIPT.read_text(encoding="utf-8"))
    main = next(
        (
            no
            for no in arvore.body
            if isinstance(no, ast.FunctionDef) and no.name == "main"
        ),
        None,
    )
    assert main is not None, "o `main` sumiu do `retratar_abas.py`"

    chamadas = {
        no.func.id
        for no in ast.walk(main)
        if isinstance(no, ast.Call) and isinstance(no.func, ast.Name)
    }
    esperadas = {
        "_montar_aba_lightbar": "Lightbar",
        "_montar_aba_rumble": "Rumble",
        "_montar_aba_sistema": "Sistema",
        "_montar_aba_emulacao": "Emulação",
        "_montar_aba_navegacao": "Navegação",
    }
    faltando = {f: aba for f, aba in esperadas.items() if f not in chamadas}
    assert not faltando, (
        "o `main` do retrato parou de montar estas abas, e elas voltam ao "
        "README como glade cru: "
        + "; ".join(f"{aba} ({f})" for f, aba in faltando.items())
    )


def test_a_aba_navegacao_nasce_com_as_duas_colunas_de_atalho() -> None:
    """A lista de atalhos é montada em CÓDIGO — sem host ela sai sem coluna.

    O glade traz o `key_bindings_treeview` VAZIO: quem cria as duas colunas e
    quem enche o modelo é `_install_key_bindings_treeview`. Uma foto da lista
    sem coluna nenhuma não ensina que a aba serve para trocar atalho.
    """
    _modulo, builder = _janela_montada()
    tree = builder.get_object("key_bindings_treeview")
    assert tree is not None, "`key_bindings_treeview` sumiu do glade"

    colunas = tree.get_columns()
    store = tree.get_model()
    linhas = 0 if store is None else len(store)

    assert len(colunas) == 2, (
        f"a lista de atalhos da foto saiu com {len(colunas)} coluna(s) e o "
        "produto tem 2 (“Botão do controle” e “Tecla do teclado”)."
    )
    assert linhas > 0, (
        "a lista de atalhos da foto saiu VAZIA. Os atalhos de fábrica "
        "(`DEFAULT_BUTTON_BINDINGS`) são o que ela vê ao abrir a janela sem "
        "perfil carregado — uma lista vazia documenta um produto sem atalho."
    )
