"""O portão do LÉXICO da aba Configurações — a régua da leva CONFIGURAÇÕES-O-LÉXICO-01."""
from __future__ import annotations

import ast
import contextlib
from pathlib import Path
from typing import Any

from tests.conftest import exigir_gi_real

exigir_gi_real("o léxico da aba Configurações")

import pytest

_gi = pytest.importorskip("gi", reason="precisa de PyGObject")
_gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

from hefesto_dualsense4unix.app import ipc_bridge
from hefesto_dualsense4unix.app.actions.config import secao_janela, secao_mesa
from hefesto_dualsense4unix.app.actions.config.secoes import SECOES_DA_ABA
from hefesto_dualsense4unix.app.actions.config.moldura import RECIBO_GUARDADO, VALE_JA
from tests.unit.aba_config_sem_a_janela import aba_config_montada
from hefesto_dualsense4unix.app.widgets import external_card
from hefesto_dualsense4unix.app.widgets.campo_de_busca import CampoDeBusca

RAIZ = Path(__file__).resolve().parents[2]
FONTE = RAIZ / "src" / "hefesto_dualsense4unix" / "app"


_TAMANHO_DE_PARAGRAFO = 60

PARAGRAFOS_QUE_FICAM: dict[str, str] = {
    "Nenhum controle ligado agora.": (
        "seção VAZIA: só existe quando não há controle nenhum, logo é o próprio "
        "estado dos controles. `secao_controles`. A frase dizia `na mesa` até "
        "05/09/2026, quando ela mandou tirar a palavra da interface."
    ),
    "Não sei quem está no rádio": (
        "estado do daemon: só aparece quando ele não respondeu. `secao_orcamento`."
    ),
    "Você ainda não mapeou as suas entradas.": (
        "estado da declaração dela: some no instante em que o mapa é desenhado. "
        "`secao_mesa`. A frase dizia `Você ainda não desenhou a sua mesa.` até "
        "05/09/2026, e a razão escrita aqui era que a palavra FICAVA — por ser "
        "a mesa FÍSICA, a escrivaninha e as entradas USB. **Ela derrubou esse "
        "juízo no mesmo dia**: *\"muda o termo pra objeto e sinônimos nesses "
        "casos\"*. O verbo acompanhou o botão ao lado, que é o \"o que fazer\" "
        "desta frase e passou a chamar-se `Mapear Entradas`."
    ),
    "A sessão não diz qual é o ambiente.": (
        "estado da SESSÃO: `app/ambiente.frase_do_detectado` só a escreve quando "
        "a sessão não declara ambiente nenhum; com um declarado, a linha é o "
        "curto «Detectado: …». Numa sessão gráfica ela nunca aparece, e por isso "
        "a régua só a viu no job `gtk-real` do CI, que roda sem sessão "
        "(corrida 36119169814, 25/09/2026)."
    ),
}

AINDA_NA_PAGINA: dict[str, str] = {
    "Com o microfone ligado, um controle no BT troca": (
        "LEX-2, item 2 — `secao_controles.montar`. BLOQUEADO EM 26/08/2026, e a "
        "medição é esta: `test_o_interruptor_do_microfone_na_aba_configuracoes"
        ".py::test_a_frase_aparece_uma_unica_vez_na_secao` (`:445-452`) exige "
        "`_rotulos(caixa).count(frase) == 1`, e o `_rotulos` daquele arquivo "
        "(`:139-151`) colhe SÓ `get_label()` — nunca dica. Mover a frase para o "
        "hover deixa a contagem em zero e reprova. O conserto é o mesmo que a "
        "G9 já fez no `_textos` -> `_falas` de "
        "`test_a_aba_diz_quando_a_escolha_fica_guardada.py`: o coletor passa a "
        "colher `get_tooltip_text()` junto. Aquele arquivo não está na posse "
        "da LEVA-4-A (R-A), então a frente relata em vez de editar.\n"
        "Ela também é a única casa da `QUANDO_VALE` em `secao_controles`: numa "
        "mesa sem controle nenhum, o interruptor que a frase explica não "
        "existe. Quem mover a frase move a dica junto."
    ),
}

NUNCA_MENOS_QUE = 3


def _aba_montada() -> Any:
    """Monta a aba em CÓDIGO e devolve a caixa da aba."""
    return aba_config_montada()


def _descer(raiz: Any) -> list[Any]:
    """Todo widget da subárvore, o título de `Gtk.Frame` incluído."""
    achados: list[Any] = []
    pilha = [raiz]
    while pilha:
        widget = pilha.pop()
        achados.append(widget)
        if isinstance(widget, Gtk.Frame):
            rotulo = widget.get_label_widget()
            if rotulo is not None:
                pilha.append(rotulo)
        filhos = getattr(widget, "get_children", None)
        if filhos is not None:
            pilha.extend(filhos())
    return achados


def _paragrafos_de_apoio(raiz: Any) -> list[str]:
    """Os textos que a régua considera parágrafo de apoio."""
    achados: list[str] = []
    for widget in _descer(raiz):
        if not isinstance(widget, Gtk.Label):
            continue
        esmaecido = False
        with contextlib.suppress(Exception):
            esmaecido = widget.get_style_context().has_class("dim-label")
        if not (esmaecido and widget.get_line_wrap()):
            continue
        texto = widget.get_text() or ""
        if len(texto) > _TAMANHO_DE_PARAGRAFO:
            achados.append(texto)
    return achados


def _conhecido(texto: str) -> bool:
    """O texto casa com alguma entrada declarada, por PREFIXO ou por trecho."""
    return any(
        chave in texto
        for chave in (*PARAGRAFOS_QUE_FICAM, *AINDA_NA_PAGINA)
    )


def test_nenhum_paragrafo_de_apoio_novo_na_pagina() -> None:
    """Explicação nova nasce no hover, nunca na página."""
    achados = [
        texto for texto in _paragrafos_de_apoio(_aba_montada()) if not _conhecido(texto)
    ]
    assert not achados, (
        "parágrafo de apoio na PÁGINA que não está declarado:\n  "
        + "\n  ".join(sorted(set(achados)))
        + "\n\nA regra do léxico: fica na página o que MUDA, vai para o hover o "
        "que EXPLICA. Se este texto explica, cole-o como dica do widget que ele "
        "explica — `marcar_afordancias` dá a marca sozinho. Se ele é ESTADO, "
        "declare em `PARAGRAFOS_QUE_FICAM` com o motivo."
    )


def test_a_regua_continua_achando_o_que_promete_achar() -> None:
    """Zero achados é reprovação, não aprovação."""
    achados = _paragrafos_de_apoio(_aba_montada())
    assert len(achados) >= NUNCA_MENOS_QUE, (
        f"a régua achou {len(achados)} parágrafo(s) de apoio na aba, e o piso é "
        f"{NUNCA_MENOS_QUE}. Ou a leva do léxico terminou (e então este piso "
        "desce junto, no mesmo commit), ou o coletor quebrou e o dente 1 está "
        "verde sem medir nada."
    )


class _HospedeiroVazio:
    """Sem builder, sem mesa, sem daemon — o dublê mínimo de "A janela"."""

    def __init__(self) -> None:
        self.builder = None
        self.interruptor = Gtk.Switch()

    def _get(self, nome: str) -> Any:
        return self.interruptor if nome == "daemon_autostart_switch" else None


def _janela_montada() -> tuple[Any, Any]:
    """`(host, caixa)` com a seção "A janela" montada de verdade."""
    host = _HospedeiroVazio()
    caixa = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
    secao_janela.montar(host, caixa)
    return host, caixa


def test_o_duble_monta_a_fileira_do_espelho() -> None:
    """A régua dos dois testes abaixo tem de estar OLHANDO para a fileira."""
    _host, caixa = _janela_montada()
    rotulos = [
        widget.get_text()
        for widget in _descer(caixa)
        if isinstance(widget, Gtk.Label)
    ]
    assert any("Ligar junto com o computador" in texto for texto in rotulos), (
        "a fileira do espelho de autostart não foi montada no dublê — os "
        "portões do botão e da dica abaixo estariam medindo o vazio"
    )


def test_o_tamanho_do_texto_escreve_recibo_ao_clicar(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """O clique que não muda um pixel do tema tem de dizer que chegou."""
    gravados: list[tuple[str, Any]] = []
    monkeypatch.setattr(
        secao_janela, "set_pref", lambda chave, valor: gravados.append((chave, valor))
    )
    host, _caixa = _janela_montada()
    recibo = host._config_recibo_do_tamanho
    assert recibo.get_text() == "", "o recibo tem de NASCER vazio"

    host._config_escala_seletor.set_active_id("grande")

    assert gravados, "o clique nem gravou — a mordida está no lugar errado"
    assert recibo.get_text() == RECIBO_GUARDADO, (
        "o clique gravou e a tela não disse nada. Sem recibo, um controle que "
        "não reaplica o tema é indistinguível de um controle quebrado."
    )


def test_o_ambiente_escreve_recibo_mesmo_com_a_bandeja_dizendo_o_mesmo(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """O caso DELA: trocar o ambiente não muda a frase da bandeja, e assim mesmo"""
    monkeypatch.setattr(
        secao_janela, "gravar_correcao_de_ambiente", lambda _escolha: None
    )
    monkeypatch.setattr(
        secao_janela,
        "mensagem_da_bandeja",
        lambda _ambiente, _presente: "A barra do sistema desta sessão recebe o ícone.",
    )
    host, _caixa = _janela_montada()
    recibo = host._config_recibo_do_ambiente
    assert recibo.get_text() == ""

    seletor = host._config_ambiente_seletor
    atual = seletor.get_active_id()
    outro = next(
        ident
        for ident, _rotulo in seletor._items
        if ident != atual
    )
    seletor.set_active_id(outro)

    assert recibo.get_text() == RECIBO_GUARDADO, (
        "trocar o ambiente não escreveu recibo. Na máquina dela a frase da "
        "bandeja é a mesma nos três ambientes, então sem recibo o clique não "
        "tem NENHUMA consequência visível."
    )


def test_o_recibo_de_uma_fileira_apaga_o_da_outra(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Dois recibos verdes diriam que dois gestos acabaram de acontecer."""
    monkeypatch.setattr(secao_janela, "set_pref", lambda _chave, _valor: None)
    monkeypatch.setattr(
        secao_janela, "gravar_correcao_de_ambiente", lambda _escolha: None
    )
    host, _caixa = _janela_montada()

    host._config_escala_seletor.set_active_id("grande")
    assert host._config_recibo_do_tamanho.get_text() == RECIBO_GUARDADO

    seletor = host._config_ambiente_seletor
    outro = next(
        ident for ident, _rotulo in seletor._items if ident != seletor.get_active_id()
    )
    seletor.set_active_id(outro)

    assert host._config_recibo_do_ambiente.get_text() == RECIBO_GUARDADO
    assert host._config_recibo_do_tamanho.get_text() == "", (
        "o recibo velho ficou na tela ao lado do novo — a seção passa a afirmar "
        "dois gestos onde houve um"
    )


def test_as_duas_fileiras_que_gravam_na_hora_dizem_isso_no_hover() -> None:
    """A `VALE_JA` saiu da página, mas não pode ter sumido — e são DUAS fileiras.

    Ela responde "isto ficou guardado?" para quem procura ANTES de clicar, e o
    recibo só responde DEPOIS. Tirar as duas deixaria a seção muda de novo.

    POR FILEIRA, e não "em algum lugar da seção": as duas gravam na hora, e uma
    régua que aceitasse a frase em qualquer canto ficaria verde com a dica só na
    outra — medido em 25/08/2026, quando a primeira versão deste teste passou
    com a mordida aplicada em uma das duas.

    MORDIDA: tire a `VALE_JA` da dica de "Tamanho do texto:" — reprova nomeando
    essa fileira. Tire a de "Ambiente:" — reprova nomeando a outra.
    """
    _host, caixa = _janela_montada()
    dica_por_rotulo = {
        widget.get_text(): (widget.get_tooltip_text() or "")
        for widget in _descer(caixa)
        if isinstance(widget, Gtk.Label)
    }
    mudas = [
        rotulo
        for rotulo in ("Tamanho do texto:", "Ambiente:")
        if VALE_JA not in dica_por_rotulo.get(rotulo, "")
    ]
    assert not mudas, (
        f"estas fileiras gravam no próprio clique e não dizem isso em lugar "
        f"nenhum: {mudas}. A frase saiu da página na LEX-2 e tem de estar na "
        "dica do rótulo que ela explica."
    )


def test_a_janela_nao_tem_botao_de_abrir_a_aba_sistema() -> None:
    """Ela, literal: *"não deveriam ter o botão de abrir aba sistema"*."""
    _host, caixa = _janela_montada()
    botoes = [
        widget.get_label() or ""
        for widget in _descer(caixa)
        if isinstance(widget, Gtk.Button) and not isinstance(widget, Gtk.RadioButton)
    ]
    achados = [rotulo for rotulo in botoes if "aba Sistema" in rotulo]
    assert not achados, f"o botão que ela mandou tirar voltou: {achados}"


POPUPS_PROIBIDOS = frozenset({"ComboBox", "ComboBoxText", "EntryCompletion"})

PASTAS_SEM_POPUP = ("widgets", "actions/config")


def test_nenhum_popup_nos_widgets_da_aba_configuracoes() -> None:
    """Por AST, e não por `grep`: um comentário citando o nome não é um uso."""
    achados: list[str] = []
    for pasta in PASTAS_SEM_POPUP:
        for caminho in sorted((FONTE / pasta).glob("*.py")):
            arvore = ast.parse(caminho.read_text(encoding="utf-8"))
            for no in ast.walk(arvore):
                if isinstance(no, ast.Attribute) and no.attr in POPUPS_PROIBIDOS:
                    achados.append(
                        f"{caminho.relative_to(RAIZ)}:{no.lineno}: {no.attr}"
                    )
                elif isinstance(no, ast.Name) and no.id in POPUPS_PROIBIDOS:
                    achados.append(
                        f"{caminho.relative_to(RAIZ)}:{no.lineno}: {no.id}"
                    )
    assert not achados, (
        "popup na aba Configurações:\n  "
        + "\n  ".join(achados)
        + "\n\nO cosmic-comp rouba o foco no clique e FECHA o popup "
        "(cosmic-epoch#2497), e o contorno — forçar XWayland — foi medido em "
        "24/08/2026 e faz a janela NÃO ABRIR. A lista tem de morar dentro do "
        "card, como em `app/widgets/campo_de_busca.py`."
    )


def test_a_busca_acha_pelo_meio_do_nome_e_sem_acento() -> None:
    """Quem procura "cosmic" acha "Cosmic Red"; quem digita sem acento também."""
    busca = CampoDeBusca()
    busca.set_items([("02", "Cosmic Red"), ("04", "Galactic Purple"), ("Z3", "Astro Bot")])

    assert [ident for ident, _n in busca.filtrados("cosmic")] == ["02"]
    assert [ident for ident, _n in busca.filtrados("PURPLE")] == ["04"]
    assert busca.filtrados("") == [], "campo vazio não abre a lista inteira"
    assert busca.filtrados("   ") == [], "só espaço também não abre"
    assert busca.filtrados("zzzz") == [], "letras que não casam não inventam linha"


def test_quem_so_sabe_que_e_vermelho_continua_achando() -> None:
    """A regressão que a busca criaria sem os sinônimos."""
    dados = external_card.DadosDoControle(
        chave="dublê", titulo="Jogador 1", subtitulo="DualSense · Rádio"
    )
    card = external_card.ExternalCard(dados)
    buscas = [
        widget for widget in _descer(card) if isinstance(widget, CampoDeBusca)
    ]
    assert buscas, "o card não montou a busca de cor"
    busca = buscas[0]

    achados = dict(busca.filtrados("vermelho"))
    assert "02" in achados, (
        'digitar "vermelho" não achou a Cosmic Red — os sinônimos em português '
        "sumiram, e com eles o caminho de quem não sabe o nome de fábrica"
    )
    assert achados["02"] == "Cosmic Red", (
        "a linha passou a mostrar a palavra em português; o que a tela diz tem "
        "de continuar sendo o nome que está escrito na caixa do aparelho"
    )
    assert "02" in dict(busca.filtrados("cosmic")), (
        "o sinônimo comeu a busca pelo nome de fábrica, que é o gesto que ela "
        "descreveu"
    )


def test_clicar_numa_linha_escolhe_aquela_linha() -> None:
    """O gesto inteiro: digitar, ver duas sugestões, clicar na SEGUNDA."""
    busca = CampoDeBusca()
    busca.set_items(
        [("00", "White"), ("02", "Cosmic Red"), ("07", "Volcanic Red")]
    )
    emitidos: list[str | None] = []
    busca.connect("changed", lambda w: emitidos.append(w.get_active_id()))

    janela = Gtk.OffscreenWindow()
    janela.add(busca)
    janela.show_all()
    try:
        busca.get_entrada().set_text("red")
        linhas = busca.get_lista().get_children()
        assert len(linhas) == 2, f"a lista desenhou {len(linhas)} linha(s), não 2"

        busca.get_lista().emit("row-activated", linhas[1])
        assert busca.get_active_id() == "07", (
            "clicar na segunda linha escolheu outra coisa — o id da linha e a "
            "lista desenhada saíram de sincronia"
        )
        assert emitidos == ["07"]
        assert busca.get_entrada().get_text() == "Volcanic Red"
        assert not busca.lista_visivel(), "a lista ficou aberta depois da escolha"

        busca.get_entrada().set_text("zzzz")
        mortas = busca.get_lista().get_children()
        assert len(mortas) == 1, "o beco sem saída tem de desenhar UMA linha"
        busca.get_lista().emit("row-activated", mortas[0])
        assert busca.get_active_id() == "07", "a linha de 'não achei' foi escolhida"
        assert emitidos == ["07"], "a linha de 'não achei' emitiu um gesto"
    finally:
        janela.remove(busca)
        janela.destroy()


def test_a_busca_nao_grava_sozinha_o_que_ninguem_escolheu() -> None:
    """`set_active_id` de um id ausente é no-op, e não emite."""
    emitidos: list[str | None] = []
    busca = CampoDeBusca()
    busca.set_items([("02", "Cosmic Red")])
    busca.connect("changed", lambda w: emitidos.append(w.get_active_id()))

    busca.set_active_id("nao-existe")
    assert emitidos == [], "emitiu por um id que não está na lista"

    busca.set_active_id("02")
    assert emitidos == ["02"]

    busca.set_active_id("02")
    assert emitidos == ["02"], "o mesmo id duas vezes não é um segundo gesto"


def _card(*, no_cabo: bool) -> Any:
    """Um card de DualSense adotado, no cabo ou no rádio.

    A diferença entre os dois é só a leitura da cor: no cabo o aparelho responde
    (`docs/data/mapa-controles.csv:111`, `cabo_aciona=sim`), no rádio o firmware
    recusa com `EIO` (`radio_aciona=não`). É essa recusa que, antes da LEX-5,
    fazia o card do rádio mostrar oito botões em três fileiras.
    """
    return external_card.ExternalCard(
        external_card.DadosDoControle(
            chave="dublê",
            titulo="Jogador 1",
            subtitulo="DualSense · Cabo" if no_cabo else "DualSense · Rádio",
            uniq="00:00:00:00:00:00",
            slot=1,
            adotado=True,
            cor_lida="Cosmic Red" if no_cabo else "",
            tom="#da244b" if no_cabo else "",
            no_cabo=no_cabo,
            endereco="000000000000",
        )
    )


def _altura(widget: Any) -> int:
    """A altura pedida pelo widget, medida sob `Gtk.OffscreenWindow`."""
    janela = Gtk.OffscreenWindow()
    janela.add(widget)
    janela.show_all()
    _minima, natural = widget.get_preferred_height()
    janela.remove(widget)
    janela.destroy()
    return int(natural)


def test_o_card_no_radio_nao_e_mais_alto_que_o_card_no_cabo() -> None:
    """A grade de oito botões encarecia a FILEIRA inteira de cards."""
    no_cabo = _altura(_card(no_cabo=True))
    no_radio = _altura(_card(no_cabo=False))
    assert no_radio <= no_cabo, (
        f"o card no rádio pede {no_radio}px e o card no cabo pede {no_cabo}px "
        f"— {no_radio - no_cabo}px de diferença. Como o grid da seção iguala as "
        "fileiras, essa diferença é paga por TODOS os cards da mesma linha."
    )


def test_o_rodape_nomeia_a_secao_lendo_o_titulo_dela(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Renomear a seção renomeia a frase do rodapé, sem tocar em `ipc_bridge`."""
    monkeypatch.setattr(secao_mesa, "TITULO", "Conexões (dublê)")
    rotulos = ipc_bridge._rotulos_dos_campos()
    assert rotulos["mesa"] == "Conexões (dublê)", (
        "o rodapé continuou dizendo "
        f"{rotulos['mesa']!r} depois de a seção ser renomeada — a cópia voltou"
    )
    assert ipc_bridge._CAMPOS_DA_MAQUINA["mesa"] == "Conexões (dublê)", (
        "o nome público `_CAMPOS_DA_MAQUINA` deixou de acompanhar a derivação"
    )


def test_o_rodape_nao_perde_o_campo_que_nao_tem_secao() -> None:
    """`mapa` não é `TITULO` de seção nenhuma, e mesmo assim tem rótulo."""
    fundidos = ipc_bridge._rotulos_dos_campos()
    assert fundidos["mapa"] == ipc_bridge._ROTULOS_SEM_SECAO["mapa"]
    assert fundidos["mapa"] != "mapa", (
        "o campo sem seção caiu no nome cru — a fusão perdeu `_ROTULOS_SEM_SECAO`"
    )


RENOMES_DA_LEX_1: dict[str, str] = {
    "A mesa": "Conexões",
    "Orçamento": "Desempenho",
}


def test_as_duas_secoes_renomeadas_dizem_a_palavra_dela() -> None:
    """"A mesa" virou "Conexões" e "Orçamento" virou "Desempenho"."""
    titulos = {
        secao.__name__.rsplit(".", 1)[-1]: secao.TITULO for secao in SECOES_DA_ABA
    }
    velhas = {
        modulo: titulo
        for modulo, titulo in titulos.items()
        if titulo in RENOMES_DA_LEX_1
    }
    assert not velhas, (
        "estas seções voltaram ao nome velho: "
        + ", ".join(
            f"{modulo} diz {titulo!r} e devia dizer "
            f"{RENOMES_DA_LEX_1[titulo]!r}"
            for modulo, titulo in sorted(velhas.items())
        )
    )
    assert titulos["secao_mesa"] == "Conexões"
    assert titulos["secao_orcamento"] == "Desempenho"


JARGAO_DAS_DUAS_PERGUNTAS = ("antena", "visada")

VALORES_QUE_NAO_MUDAM: dict[str, dict[str, str]] = {
    "altura_da_antena": {"Sim": "acima", "Não": "abaixo", "Não sei": "nao_sei"},
    "linha_de_visada": {"Sim": "com_gente", "Não": "livre", "Não sei": "nao_sei"},
}


class _HospedeiroDaMesa:
    """O mínimo que a seção da mesa toca: o rascunho, e nada mais."""

    def __init__(self) -> None:
        self._maquina_pendente: dict[str, Any] | None = None


def _declaracoes_montadas() -> tuple[Any, Any]:
    """`(host, caixa)` com as duas perguntas desenhadas, sem tocar o `/sys`."""
    from hefesto_dualsense4unix.integrations.censo_do_barramento import Censo
    from hefesto_dualsense4unix.integrations.mesa_de_radio import Mesa

    host = _HospedeiroDaMesa()
    painel = secao_mesa._PainelDaMesa(host)
    painel._ler = lambda: Mesa()  # type: ignore[method-assign]
    painel._ler_o_censo = lambda: Censo()  # type: ignore[method-assign]
    painel._pedir_o_estado = lambda: None  # type: ignore[method-assign]
    return host, painel._declaracoes()


def test_as_duas_perguntas_de_radio_nao_falam_antena_nem_visada() -> None:
    """A redação da `D-REDACAO-DAS-DUAS-PERGUNTAS-DE-RADIO`, na tela."""
    _host, caixa = _declaracoes_montadas()
    falados = [
        texto
        for widget in _descer(caixa)
        if isinstance(widget, Gtk.Label)
        for texto in (widget.get_text() or "",)
        if texto
    ]
    assert falados, "a caixa das declarações não desenhou rótulo nenhum"
    culpados = [
        texto
        for texto in falados
        for palavra in JARGAO_DAS_DUAS_PERGUNTAS
        if palavra in texto.lower()
    ]
    assert not culpados, (
        "as duas perguntas de rádio voltaram ao jargão que ela disse não "
        "entender: " + "; ".join(sorted(set(culpados)))
    )
    assert any(texto.endswith("?") for texto in falados), (
        "nenhuma das fileiras é uma pergunta — a gramática das duas é a de "
        f'"Está tudo certo?". Textos: {falados}'
    )


def test_a_redacao_nova_grava_os_mesmos_valores_de_esquema() -> None:
    """Trocar a palavra do botão não pode trocar o valor que vai ao disco."""
    from hefesto_dualsense4unix.app.widgets.segmented_selector import (
        SegmentedSelector,
    )

    for chave, esperado in VALORES_QUE_NAO_MUDAM.items():
        _host, caixa = _declaracoes_montadas()
        fileiras = list(caixa.get_children())
        assert len(fileiras) == len(VALORES_QUE_NAO_MUDAM), (
            f"a caixa das declarações tem {len(fileiras)} fileira(s) e as "
            f"perguntas são {len(VALORES_QUE_NAO_MUDAM)}"
        )
        fileira = fileiras[list(VALORES_QUE_NAO_MUDAM).index(chave)]
        seletores = [
            widget
            for widget in fileira.get_children()
            if isinstance(widget, SegmentedSelector)
        ]
        assert len(seletores) == 1, f"a fileira de {chave!r} não tem um seletor"
        ids = {rotulo: ident for ident, rotulo in seletores[0]._items}
        for palavra, valor in esperado.items():
            assert ids.get(palavra) == valor, (
                f'o botão "{palavra}" da pergunta {chave!r} grava '
                f"{ids.get(palavra)!r} e tem de gravar {valor!r} — o "
                "`Literal` de `MesaDeclarada` não mudou, e um valor novo faz "
                "o pydantic recusar o documento inteiro dela"
            )
