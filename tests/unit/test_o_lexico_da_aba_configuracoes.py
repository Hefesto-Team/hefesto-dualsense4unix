"""O portão do LÉXICO da aba Configurações — a régua da leva CONFIGURAÇÕES-O-LÉXICO-01.

A REGRA QUE ESTE ARQUIVO GUARDA, e ela é o produto da leva:

    Fica na página o que MUDA — estado, medição, resposta, seção vazia.
    Vai para o hover o que EXPLICA — por quê, quando vale, de onde veio.

    O teste: *este parágrafo diria a mesma coisa com a mesa vazia e com a mesa
    cheia?* Se sim, é explicação; cola no widget que ele explica, e o widget já
    ganha a marca por `moldura.marcar_afordancias`.

O DEFEITO MEDIDO EM 24/08/2026: doze parágrafos de apoio ocupavam a página
inteira da aba com texto que nunca muda, e TRÊS deles eram a mesma frase,
palavra por palavra. Ela: *"tudo isso em azul deveria ser tooltip, não deveria
poluir a interface"*. Em altura, ≈520px numa foto de 2505px — um quinto da
página, numa janela de 1080.

O QUE ESTE ARQUIVO COBRA, e cada dente tem a mordida escrita no docstring dele:

1. **parágrafo de apoio novo reprova** — a lista do que fica é explícita, e o
   que ainda não saiu está declarado como DÍVIDA, com o número da tarefa e o
   arquivo de quem a paga;
2. **o recibo responde ao clique** — os dois controles de "A janela" que gravam
   na hora escrevem "Guardado." e não dependem um do outro;
3. **o botão que ela mandou tirar não volta**;
4. **a busca não vira popup** — nem `Gtk.ComboBox` nem `Gtk.EntryCompletion` em
   `app/widgets/` ou `app/actions/config/`;
5. **o card do rádio não é mais alto que o card do cabo**;
6. **o rodapé não guarda cópia do título da seção**.

Bancada: nenhum aparelho, nenhum MAC. Sob `Gtk.OffscreenWindow` onde há medição
de altura — **nunca `Gtk.Window`**, que sob Xvfb fica 1x1 para sempre
(`COMO-OLHAR-A-TELA.md`).
"""
from __future__ import annotations

import ast
import contextlib
from pathlib import Path
from typing import Any

from tests.conftest import exigir_gi_real

# GUARDA-GI-REAL-01: antes de qualquer import de `gi`.
exigir_gi_real("o léxico da aba Configurações")

import pytest

_gi = pytest.importorskip("gi", reason="precisa de PyGObject")
_gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

from hefesto_dualsense4unix.app import ipc_bridge
from hefesto_dualsense4unix.app.actions.config import ABA_CONFIG, ConfigActionsMixin
from hefesto_dualsense4unix.app.actions.config import secao_janela, secao_mesa
from hefesto_dualsense4unix.app.actions.config.moldura import RECIBO_GUARDADO, VALE_JA
from hefesto_dualsense4unix.app.constants import MAIN_GLADE
from hefesto_dualsense4unix.app.widgets import external_card
from hefesto_dualsense4unix.app.widgets.campo_de_busca import CampoDeBusca

RAIZ = Path(__file__).resolve().parents[2]
FONTE = RAIZ / "src" / "hefesto_dualsense4unix" / "app"


# ---------------------------------------------------------------------------
# Dente 1 — parágrafo de apoio novo reprova
# ---------------------------------------------------------------------------

#: O que um "parágrafo de apoio" é, na régua deste portão: rótulo esmaecido,
#: com quebra de linha, e comprido. Os três juntos, porque cada um sozinho pega
#: coisa demais — um rótulo de fileira também é `Gtk.Label`, e um selo esmaecido
#: também tem `dim-label`.
_TAMANHO_DE_PARAGRAFO = 60

#: Os parágrafos que FICAM na página, e o motivo de cada um. Todos são ESTADO —
#: mudam com a máquina, com a mesa ou com a resposta do daemon.
PARAGRAFOS_QUE_FICAM: dict[str, str] = {
    "Nenhum controle na mesa agora.": (
        "seção VAZIA: só existe quando não há controle nenhum, logo é o próprio "
        "estado da mesa. `secao_controles`."
    ),
    "Não sei quem está no rádio": (
        "estado do daemon: só aparece quando ele não respondeu. `secao_orcamento`."
    ),
    "Você ainda não desenhou a sua mesa.": (
        "estado da declaração dela: some no instante em que o mapa é desenhado. "
        "`secao_mesa`."
    ),
}

#: O que AINDA está na página e devia ter saído — a dívida desta leva, com nome
#: e endereço. Não é perdão: é o que permite este portão entrar HOJE sem
#: derrubar o vermelho por um trabalho que é de outra frente.
#:
#: A frente G9 é dona de `secao_janela.py`, `moldura.py`, `external_card.py`,
#: `external_controllers.py` e `ipc_bridge.py`. As três seções abaixo são de
#: frentes que rodam ao lado; editá-las daqui desfaria o trabalho delas em
#: silêncio (R1). Apague a entrada no commit que tirar o parágrafo.
AINDA_NA_PAGINA: dict[str, str] = {
    'A escolha passa a valer quando você clicar em "Aplicar", no rodapé.': (
        "LEX-2, itens 3/4/5 — a MESMA frase em três seções ao mesmo tempo "
        "(`secao_mesa`, `secao_controles`, `secao_orcamento`). Vira dica do "
        "título de cada uma. Nenhum dos três arquivos é da G9."
    ),
    "Este exame olha a mesa": (
        "LEX-2, item 1 — `secao_exame.py:261` (`ESCOPO`). Vira dica do título "
        '"Está tudo certo?". Arquivo da frente B.'
    ),
    "Com o microfone ligado, um controle no rádio troca": (
        "LEX-2, item 2 — `secao_controles.py:635`. CEDIDO à frente C: a frase "
        "acompanha a caixinha do microfone quando ela se muda para Desempenho."
    ),
    "Por enquanto o teto alcança": (
        "LEX-2, item 8 — `secao_orcamento.py:226` (`ALCANCE_DE_HOJE`). Vira "
        'dica da DICA de "Desempenho". Arquivo da frente C.'
    ),
    "Um controle no rádio ocupa": (
        "LEX-2 — `secao_orcamento.py`, a conta de fatias como parágrafo fixo. "
        "É explicação: diz o mesmo com a mesa vazia e com a mesa cheia. "
        "Arquivo da frente C."
    ),
}

#: O PISO da régua. Zero parágrafos achados é REPROVAÇÃO, não aprovação — é a
#: armadilha de 19/08 (`o-portao-que-nao-mede-o-que-promete`), e o
#: `test_afordancia_de_dica_na_aba_configuracoes.py:203` já a paga do mesmo
#: jeito. Sem este piso, quebrar o coletor deixaria o portão verde e mudo.
#:
#: O número é baixo de propósito: a aba LÊ O BARRAMENTO REAL da máquina, então
#: numa bancada sem adaptador nenhum algumas seções não desenham as fileiras que
#: carregam parágrafo. Medido em 25/08/2026 nesta árvore, sem DualSense e sem
#: dongle: 8 parágrafos únicos, 10 no total.
NUNCA_MENOS_QUE = 4


def _aba_montada() -> Any:
    """Carrega o Glade, roda o mixin e devolve a caixa da aba.

    Molde de `test_config_a_palavra_de_tela_da_aba_montada.py:73` — a aba de
    verdade, não um dublê: o defeito que esta leva paga só existe na aba
    montada, porque é lá que os doze parágrafos se somam.
    """

    class _Host(ConfigActionsMixin):
        def __init__(self, builder: Gtk.Builder) -> None:
            self.builder = builder

    builder = Gtk.Builder()
    builder.add_from_file(str(MAIN_GLADE))
    _Host(builder).install_config_tab()
    return builder.get_object(ABA_CONFIG)


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
    """O texto casa com alguma entrada declarada, por PREFIXO ou por trecho.

    Por trecho e não por igualdade porque metade destes parágrafos é composta em
    tempo de execução — a frase do microfone traz `260,4` e `276,7`, que são
    contas, e prendê-las na lista faria o portão reprovar no dia em que a conta
    mudasse. O que se prende é a frase, não o número.
    """
    return any(
        chave in texto
        for chave in (*PARAGRAFOS_QUE_FICAM, *AINDA_NA_PAGINA)
    )


def test_nenhum_paragrafo_de_apoio_novo_na_pagina() -> None:
    """Explicação nova nasce no hover, nunca na página.

    MORDIDA (rodada em 25/08/2026, não presumida): pus
    `caixa.pack_start(rotulo_de_apoio("Este texto explica algo e nunca muda, "
    "então não deveria estar aqui na página ocupando espaço."), False, False, 0)`
    em `secao_janela.montar` e este teste reprovou nomeando o texto inteiro.
    Desfeito em seguida.
    """
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
    """Zero achados é reprovação, não aprovação.

    MORDIDA: trocar `has_class("dim-label")` por `has_class("nao-existe")` no
    `_paragrafos_de_apoio` — o dente 1 fica verde e MUDO, e este reprova.
    """
    achados = _paragrafos_de_apoio(_aba_montada())
    assert len(achados) >= NUNCA_MENOS_QUE, (
        f"a régua achou {len(achados)} parágrafo(s) de apoio na aba, e o piso é "
        f"{NUNCA_MENOS_QUE}. Ou a leva do léxico terminou (e então este piso "
        "desce junto, no mesmo commit), ou o coletor quebrou e o dente 1 está "
        "verde sem medir nada."
    )


# ---------------------------------------------------------------------------
# Dente 2 — o recibo responde ao clique (LEX-3)
# ---------------------------------------------------------------------------


class _HospedeiroVazio:
    """Sem builder, sem mesa, sem daemon — o dublê mínimo de "A janela".

    ELE PRECISA TER O INTERRUPTOR DE AUTOSTART, e a linha não é enfeite: sem
    ele, `_fileira_do_autostart` devolve `None` de propósito (espelho sem
    original é um rótulo que nunca fica certo) e a fileira inteira **não é
    montada**. Um portão que procurasse o botão "Abrir a aba Sistema" nesse
    dublê ficaria verde para sempre, medindo uma seção sem a fileira onde o
    botão morava — medido em 25/08/2026, quando a mordida deste próprio arquivo
    passou com o botão de volta na tela.
    """

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
    """A régua dos dois testes abaixo tem de estar OLHANDO para a fileira.

    Sem esta linha, `_fileira_do_autostart` devolveria `None`, a fileira não
    seria montada e o portão do botão ficaria verde sem medir nada. É a mesma
    armadilha de 19/08 (`o-portao-que-nao-mede-o-que-promete`), paga aqui do
    jeito barato: uma asserção sobre a existência do que se vai vigiar.
    """
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
    """O clique que não muda um pixel do tema tem de dizer que chegou.

    Ela: *"janela ok, muito bom mas os botões não funcionam"*. O handler sempre
    esteve lá; o que faltava era recibo — e a frase que responderia estava na
    página ANTES do clique, logo não distinguia "cliquei" de "não cliquei".

    MORDIDA: arranque o `_escrever_o_recibo(...)` do fim de
    `_ao_trocar_o_tamanho` — reprova dizendo que o recibo continuou vazio.
    """
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
    """O caso DELA: trocar o ambiente não muda a frase da bandeja, e assim mesmo
    o gesto tem de ter resposta.

    `ambiente.mensagem_da_bandeja` devolve a MESMA frase para os três ambientes
    quando o ícone sobe (`ambiente.py:143-144`), que é a máquina dela. Antes da
    LEX-3, repintar a bandeja era a ÚNICA consequência visível do clique — e
    nessa máquina não havia consequência visível nenhuma.

    MORDIDA, e ela tem duas metades de propósito: arrancar só o repintar da
    bandeja NÃO pode fazer este teste passar a depender dele. Aqui a bandeja é
    forçada a devolver sempre a mesma frase, e o recibo tem de aparecer assim
    mesmo.
    """
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
    """Dois recibos verdes diriam que dois gestos acabaram de acontecer.

    MORDIDA: tirar o laço que apaga os outros em `_escrever_o_recibo`.
    """
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


# ---------------------------------------------------------------------------
# Dente 3 — o botão que ela mandou tirar (LEX-4)
# ---------------------------------------------------------------------------


def test_a_janela_nao_tem_botao_de_abrir_a_aba_sistema() -> None:
    """Ela, literal: *"não deveriam ter o botão de abrir aba sistema"*.

    Ele funcionava — a busca era por id, nunca por índice. O problema era outro:
    numa fileira que é ESPELHO, um botão de navegação é o único elemento
    clicável, e lê como o controle que muda o estado ao lado.

    MORDIDA: devolva o `Gtk.Button(label=_("Abrir a aba Sistema"))` a
    `_fileira_do_autostart` — reprova nomeando o rótulo.
    """
    _host, caixa = _janela_montada()
    botoes = [
        widget.get_label() or ""
        for widget in _descer(caixa)
        if isinstance(widget, Gtk.Button) and not isinstance(widget, Gtk.RadioButton)
    ]
    achados = [rotulo for rotulo in botoes if "aba Sistema" in rotulo]
    assert not achados, f"o botão que ela mandou tirar voltou: {achados}"


# ---------------------------------------------------------------------------
# Dente 4 — a busca não vira popup (LEX-5)
# ---------------------------------------------------------------------------

#: Os dois nomes que trariam o popup de volta. `Gtk.ComboBox` está proibido
#: nesta casa desde o cosmic-epoch#2497; `Gtk.EntryCompletion` É um popup e
#: cairia no MESMO bug por outro caminho — foi por isso que a LEX-5 desenhou a
#: lista dentro do card em vez de usar o widget pronto.
POPUPS_PROIBIDOS = frozenset({"ComboBox", "ComboBoxText", "EntryCompletion"})

#: Onde a proibição vale. São as duas pastas em que a aba Configurações monta
#: widget; o resto de `app/` tem a própria história e não é desta leva.
PASTAS_SEM_POPUP = ("widgets", "actions/config")


def test_nenhum_popup_nos_widgets_da_aba_configuracoes() -> None:
    """Por AST, e não por `grep`: um comentário citando o nome não é um uso.

    MORDIDA: escreva `Gtk.ComboBoxText()` em `app/widgets/campo_de_busca.py` —
    reprova nomeando arquivo e linha.
    """
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
    """Quem procura "cosmic" acha "Cosmic Red"; quem digita sem acento também.

    E ela sabe RECUSAR: campo vazio não devolve a lista inteira, e letras que
    não casam com nada devolvem lista vazia. Régua que só sabe passar não é
    régua.
    """
    busca = CampoDeBusca()
    busca.set_items([("02", "Cosmic Red"), ("04", "Galactic Purple"), ("Z3", "Astro Bot")])

    assert [ident for ident, _n in busca.filtrados("cosmic")] == ["02"]
    assert [ident for ident, _n in busca.filtrados("PURPLE")] == ["04"]
    assert busca.filtrados("") == [], "campo vazio não abre a lista inteira"
    assert busca.filtrados("   ") == [], "só espaço também não abre"
    assert busca.filtrados("zzzz") == [], "letras que não casam não inventam linha"


def test_quem_so_sabe_que_e_vermelho_continua_achando() -> None:
    """A regressão que a busca criaria sem os sinônimos.

    A lista de botões que ela substituiu mostrava seis rótulos EM PORTUGUÊS, e
    os vinte e um nomes de fábrica são todos em inglês. Trocar uma pela outra
    sem os sinônimos teria tirado da tela a única palavra em português que a cor
    tinha — e quem só sabe que *é vermelho* ficaria sem caminho.

    A linha continua dizendo "Cosmic Red": o sinônimo ACHA, nunca aparece.

    MORDIDA: tire o `busca.set_sinonimos(...)` de `_busca_da_cor`, ou o ramo do
    sinônimo em `_BuscaLogic.filtrados` — reprova.
    """
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


def test_clicar_numa_linha_escolhe_AQUELA_linha() -> None:
    """O gesto inteiro: digitar, ver duas sugestões, clicar na SEGUNDA.

    A segunda e não a primeira de propósito: uma implementação que sempre
    devolvesse o primeiro achado passaria num teste de uma linha só, e essa
    implementação existiu aqui — a primeira versão pendurava o id num atributo
    do `Gtk.ListBoxRow`, e a segunda passou a lê-lo pelo `get_index()` contra a
    lista desenhada.

    Depois do clique: o campo mostra o nome escolhido e a lista FECHA. Lista que
    fica aberta depois da escolha continua empurrando o card para baixo, que é a
    altura que este widget nasceu para devolver.

    MORDIDAS RODADAS (25/08/2026): trocar `self._visiveis[indice]` por
    `self._visiveis[0]` reprova na primeira asserção; arrancar o `_fechar()`
    reprova na lista aberta.

    A ÚLTIMA ASSERÇÃO É CONTRATO, NÃO MORDIDA, e a distinção está escrita porque
    esconder isso seria a régua se gabando. A linha de "não achei" é protegida
    por DUAS coisas — ela nasce `set_activatable(False)`, e `_ao_ativar_linha`
    confere o índice contra a lista desenhada. Arrancar qualquer uma das duas
    sozinha **não** muda o que este teste observa: sem a primeira, a segunda
    barra; sem a segunda, o `IndexError` é engolido pelo GObject e o id não muda
    de qualquer jeito. A asserção fica porque o CONTRATO ("a linha morta não é
    uma escolha") é o que importa; ela só não é o dente que prova a cura.
    """
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
    """`set_active_id` de um id ausente é no-op, e não emite.

    É a mesma semântica do `GtkComboBox` que o `SegmentedSelector` espelha, e a
    razão é medida: com o handler já ligado, um `set_active_id` que emitisse à
    toa faria a abertura da janela gravar sozinha.
    """
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


# ---------------------------------------------------------------------------
# Dente 5 — o card do rádio não é mais alto que o card do cabo (LEX-5)
# ---------------------------------------------------------------------------


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
    """A altura pedida pelo widget, medida sob `Gtk.OffscreenWindow`.

    **Nunca `Gtk.Window`**: sob Xvfb não há gerenciador de janelas, e uma
    `Gtk.Window` fica 1x1 para sempre (`COMO-OLHAR-A-TELA.md`, armadilha 2). A
    offscreen aloca de verdade e devolve a medida de verdade.
    """
    janela = Gtk.OffscreenWindow()
    janela.add(widget)
    janela.show_all()
    _minima, natural = widget.get_preferred_height()
    janela.remove(widget)
    janela.destroy()
    return int(natural)


def test_o_card_no_radio_nao_e_mais_alto_que_o_card_no_cabo() -> None:
    """A grade de oito botões encarecia a FILEIRA inteira de cards.

    `grade.set_row_homogeneous(True)` (`secao_controles.py:945`) iguala as
    fileiras: um card com três fileiras de botões de cor puxa para cima a altura
    de todos os cards da mesma linha. Medido a olho na foto de 24/08, a barra "A
    luz não acende" nascia ≈79px mais baixa nos cards do rádio.

    MORDIDA: devolva o `SegmentedSelector(wrap=True)` de oito itens ao ramo sem
    leitura de `_linha_da_cor` — reprova, e a mensagem imprime os dois números,
    que é a medição exata que a sprint deixou aproximada.
    """
    no_cabo = _altura(_card(no_cabo=True))
    no_radio = _altura(_card(no_cabo=False))
    assert no_radio <= no_cabo, (
        f"o card no rádio pede {no_radio}px e o card no cabo pede {no_cabo}px "
        f"— {no_radio - no_cabo}px de diferença. Como o grid da seção iguala as "
        "fileiras, essa diferença é paga por TODOS os cards da mesma linha."
    )


# ---------------------------------------------------------------------------
# Dente 6 — o rodapé não guarda cópia do título da seção (LEX-1)
# ---------------------------------------------------------------------------


def test_o_rodape_nomeia_a_secao_lendo_o_titulo_dela(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Renomear a seção renomeia a frase do rodapé, sem tocar em `ipc_bridge`.

    Até 25/08/2026 `_CAMPOS_DA_MAQUINA` guardava os rótulos por CÓPIA, com um
    comentário dizendo que eles eram os `TITULO` de `app/actions/config/`. Eram,
    mas por cópia — e as duas metades passavam em separado, então nenhum portão
    via a divergência. Renomear "A mesa" sem tocar aqui faria o rodapé acusar a
    perda de uma seção que a aba não tem.

    MORDIDA (rodada em 25/08/2026): devolvi o dicionário literal
    `{"mesa": "A mesa", ...}` a `ipc_bridge` — reprova dizendo que o rodapé
    nomeia "A mesa" numa aba cuja seção se chama outra coisa.
    """
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
    """`mapa` não é `TITULO` de seção nenhuma, e mesmo assim tem rótulo.

    Ele mora numa janela que abre de dentro de "A mesa", e o rótulo nomeia o que
    se PERDE — o desenho do gabinete —, não a seção de onde ele é aberto.

    MORDIDA: tire `_ROTULOS_SEM_SECAO` da fusão em `_rotulos_dos_campos` — o
    campo cai no nome cru `mapa` e o portão de cobertura do schema reprova.
    """
    assert ipc_bridge._rotulos_dos_campos()["mapa"] == "O desenho da mesa"
