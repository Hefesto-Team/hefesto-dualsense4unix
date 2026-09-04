#!/usr/bin/env python3
"""As duas decisões da aba Jogar que a ONDA2-01 fecha, e a que ela NÃO fecha.

04/09/2026. As quatro decisões desta aba estão em
`docs/process/sprints/2026-09-04-ONDA2-01-JOGAR-01-*.md`, e destas quatro:

* **[02] o "Player N" esmaecido** — fecha aqui. A palavra FICA (a D-04 dela
  venceu a minha recomendação); o que sai é o cartão AFIRMAR um jogador que o
  jogo ainda não recebeu;
* **[03] o cadeado da troca automática** — fecha aqui. A coluna Atenção já
  EXPLICA o cadeado desde 03/09 e nenhuma das dez abas oferece onde ligá-lo;
* **[04] mesa com mais de quatro** — morreu no conflito C-7 (a D-07 já carrega o
  ``+N``), e a `test_a01_a_mesa_vazia_fala.py` já a mede;
* **[01] as duas frases órfãs** — **fechou pela METADE, e a outra metade é
  decisão dela.** A ponte já entra na coluna Atenção
  (`test_a01_a_ponte_entra_na_coluna.py`). O aviso do Modo Nativo **não entra**,
  e esta régua é quem guarda o porquê: ver
  :func:`test_o_aviso_do_nativo_continua_fora_por_decisao_dela`.

A MORDIDA DE CADA UMA está no docstring dela, e as duas saídas — a reprovação e
a passagem — estão coladas em `docs/process/agentes/2026-09-04/ONDA2-01.md`.
"""
from __future__ import annotations

import pathlib
import shutil
import sys
from typing import Any

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
INTERFACE = RAIZ / "src" / "hefesto_dualsense4unix" / "interface"
for _caminho in (str(RAIZ / "src"), str(INTERFACE)):
    if _caminho not in sys.path:
        sys.path.insert(0, _caminho)

from hefesto_dualsense4unix.interface import onde
from pacotes import Contexto
from pacotes import a01_jogar as aba

#: O estado de um daemon vivo, no modo jogo — o mesmo esqueleto que as outras
#: réguas desta aba usam.
VIVO: dict[str, Any] = {
    "connected": True,
    "native_mode": False,
    "gamepad_emulation": {"enabled": True, "flavor": "dualsense"},
    "paused": False,
}

#: MACs da faixa FORJADA da casa (`aa:bb:cc`) — há dois portões de anonimato
#: nesta árvore, e o de fixture cobra justamente a faixa.
P1 = "aa:bb:cc:00:00:01"
P2 = "aa:bb:cc:00:00:02"


def _pagina() -> str:
    """O HTML da BANCADA — o desenho de HOJE, nunca o publicado.

    Apontar para o publicado daria **verde sobre a página congelada**, que é a
    armadilha mais cara do `COMO-OLHAR-A-TELA.md` e reincidiu quatro vezes só em
    31/08. O `onde.pagina()` já tem esse padrão; esta função existe para deixar
    a escolha escrita onde ela se lê.
    """
    return onde.pagina("01-jogar.html").read_text()


def _ctx(controles: list[dict[str, Any]], **estado: Any) -> Contexto:
    return Contexto(state={**VIVO, **estado, "controllers": controles},
                    mesa=[], conectados=controles, estados={})


# ---------------------------------------------------------------------------
# [02] O "PLAYER N" ESMAECIDO ENQUANTO ESPERA
# ---------------------------------------------------------------------------
def test_o_numero_esmaece_so_enquanto_o_jogo_nao_recebeu() -> None:
    """O dano que a decisão [02] mata, com a medição que o revelou.

    02/09/2026, na mesa dela, com os dois controles::

        uniq …0003 · bt  · player 1    · player_slot 1
        uniq …00d8 · usb · player None · player_slot 2   ← "Player 2" assim mesmo

    O segundo tinha RESERVADO o lugar e o jogo ainda não o via — e o cartão
    afirmava um jogador que não existia.

    A MORDIDA: troque o corpo de `_jogador_esperando` por `return ""` e esta
    régua reprova dizendo que o cartão do P2 continua afirmando o jogador.
    """
    numerado = {"uniq": P1, "connected": True, "player_slot": 1, "player": 1}
    esperando = {"uniq": P2, "connected": True, "player_slot": 2, "player": None}

    fora = aba.pacote(_ctx([numerado, esperando]))
    cartoes = fora["cartoes"]

    assert cartoes[P1]["jogador-espera"] == "", (
        "o cartão do controle que o JOGO já recebeu (player=1) está esmaecido — "
        "a tela diria 'espere' sobre um jogador que já está jogando")
    assert cartoes[P2]["jogador-espera"] == "1", (
        "o cartão do controle que o jogo NÃO recebeu (player=None) não esmaece. "
        "É o defeito medido em 02/09 na mesa dela: 'Player 2' afirmado com o "
        "co-op mostrando UM jogador")


def test_o_esmaecido_nao_toca_a_palavra() -> None:
    """A D-04 dela venceu a minha recomendação, e ela vale.

    *"Player N, como está hoje."* — e é a gramática que ela fixou em 26/08
    (marca • player • plástico • transporte). A decisão [02] escolheu a opção
    que **guarda a palavra e o desenho** e mata só a afirmação.

    A MORDIDA: troque o `f"Player {…}"` do `pacote()` por `f"Controle {…}"` e
    esta régua reprova — que é ela defendendo uma decisão DELA contra uma
    "melhora" que ninguém pediu.
    """
    esperando = {"uniq": P2, "connected": True, "player_slot": 2, "player": None}
    cartao = aba.pacote(_ctx([esperando]))["cartoes"][P2]

    assert cartao["jogador"] == "Player 2", (
        f"o cartão escreve {cartao['jogador']!r}. A D-04 dela é "
        f"'Player N, como está hoje' — o esmaecido NÃO toca a palavra")


def test_sem_numero_nenhum_nao_ha_o_que_esmaecer() -> None:
    """Um travessão esmaecido prometeria que ALGUÉM está esperando.

    Sem `player_slot` e sem `player`, `jogador_de` devolve ``None`` e o cartão
    mostra ``Player —``. Acender a classe aí diria "o jogo ainda não recebeu
    este controle" sobre um controle que a tela nem numerou — é a diferença
    entre *não sei* e *sei, e está esperando*, que é a D-O-QUE-O-PRODUTO-DIZ-
    SEM-SABER desta casa.

    A MORDIDA: apague o `if jogador_de(c) is None: return ""` e esta régua
    reprova.
    """
    mudo = {"uniq": P1, "connected": True}
    cartao = aba.pacote(_ctx([mudo]))["cartoes"][P1]

    assert cartao["jogador"] == "Player —"
    assert cartao["jogador-espera"] == "", (
        "o cartão sem número nenhum está esmaecido — a tela prometeria um "
        "jogador a caminho onde ela nem sabe dizer o número")


def test_a_pagina_tem_os_dois_elementos_do_esmaecido() -> None:
    """A classe e o texto em elementos SEPARADOS, e o de dentro é FOLHA.

    `escrever()` num elemento com filho apaga os filhos e força layout — a
    armadilha medida do piloto da Controles. Por isso o `<b>` leva a CLASSE
    (`jogador-espera`, alvo `classe`) e o `<span>` de dentro leva o TEXTO.

    A MORDIDA: ponha os dois `data-campo` no mesmo `<b>` e o gerador REPROVA
    antes desta régua — `aba01._conferir` §10 mede as duas coisas.
    """
    doc = _pagina()

    assert doc.count('data-campo="jogador-espera" data-hef-alvo="classe"'
                     ' data-hef-classe="espera"') == 2, (
        "os dois cartões conectados não têm o endereço do esmaecido")
    assert doc.count('<span data-campo="jogador">') == 2, (
        "o número do jogador deixou de ser folha — a pintura apagaria os filhos")
    assert 'class="espera"' not in doc, (
        "um cartão nasce esmaecido: a cena que ela aprovou tem os dois "
        "controles recebidos pelo jogo")


# ---------------------------------------------------------------------------
# [03] O CADEADO DA TROCA AUTOMÁTICA
# ---------------------------------------------------------------------------
def test_o_cadeado_diz_o_que_o_daemon_guardou() -> None:
    """A caixa mostra o estado do daemon, não o último clique.

    A MORDIDA: troque `state.get("autoswitch_locked") is True` por `False` e
    esta régua reprova nas duas direções — a caixa marcada com o cadeado solto,
    e solta com ele preso.
    """
    assert aba._cadeado({**VIVO, "autoswitch_locked": True}) == "sim"
    assert aba._cadeado({**VIVO, "autoswitch_locked": False}) == ""


def test_sem_daemon_a_caixa_nao_afirma_uma_escolha_dela() -> None:
    """Sem estado, a caixa DESMARCA — e a escolha está declarada.

    Um checkbox tem dois estados e o produto tem três. A aba inteira já resolve
    isso do mesmo jeito (`_estado_da_tela` devolve `""` e o interruptor apaga as
    duas posições): sem daemon não se afirma nada. Marcar sobre um estado que
    ninguém leu diria que ELA ligou o cadeado.

    E SÓ O ``True`` LITERAL LIGA — a mesma disciplina do `wrapper_used`: um
    daemon antigo, sem a chave, não pode acender a caixa.
    """
    assert aba._cadeado({}) == ""
    assert aba._cadeado({**VIVO}) == "", "daemon sem a chave marcou a caixa"
    assert aba._cadeado({**VIVO, "autoswitch_locked": "sim"}) == "", (
        "uma string ligou o cadeado — só o `True` literal pode")


class _PonteDeMentira:
    """Guarda o que foi chamado. O mesmo dublê da régua dos botões."""

    def __init__(self) -> None:
        self.chamadas: list[tuple[str, tuple, dict]] = []

    def __getattr__(self, nome: str):
        def registrar(*args, **kwargs):
            self.chamadas.append((nome, args, kwargs))
            return True
        return registrar


def test_o_cadeado_manda_o_valor_absoluto_e_nunca_um_toggle() -> None:
    """O clique manda a escolha DELA, não um "inverta o que você tiver".

    **É a metade que decide, e a razão é medida:** um clique chega DUAS vezes ao
    ouvinte único do piloto — ele está em `click` **e** em `change`
    (`hefesto_vivo.BOOTSTRAP`), e um `<input type="checkbox">` dispara os dois.
    Com `locked=None` (o toggle que a ponte aceita) os dois se cancelariam: ela
    clicaria e NADA aconteceria, que é a queixa dela em estado puro.

    A MORDIDA: troque `locked=…` por `locked=None` e esta régua reprova dizendo
    que o gesto mandou um toggle.
    """
    for guardado, pedido in ((False, True), (True, False)):
        p = _PonteDeMentira()
        aba.cadeado(_ctx([], autoswitch_locked=guardado),
                    {"evento": "change"}, p)
        assert p.chamadas, "o cadeado não chamou NADA"
        nome, _, kwargs = p.chamadas[0]
        assert nome == "autoswitch_lock_set", (
            f"o cadeado chamou {nome!r} — o escritor é o da janela antiga")
        assert kwargs.get("locked") is pedido, (
            f"com o cadeado guardado em {guardado} o clique pediu "
            f"{kwargs.get('locked')!r}, esperava {pedido!r}. `None` é TOGGLE, e "
            f"dois toggles num clique são um no-op")


def test_um_clique_grava_uma_vez_so_no_disco_dela() -> None:
    """`click` e `change` chegam os dois; só um pode virar escrita.

    `autoswitch.lock` chama `save_autoswitch_locked` (`ipc_handlers.py:2536`) —
    é disco dela. Duas entregas do mesmo clique seriam duas gravações e duas
    linhas de log para um ato só.

    O `change` É O ESCOLHIDO porque é o único que só dispara quando a caixa de
    fato MUDOU: clique no rótulo, tecla de espaço e o `el.click()` sintético da
    régua passam pelos três caminhos e todos produzem `change`.

    A MORDIDA: apague a linha `if str(o.get("evento") …) != "change": return` e
    esta régua reprova dizendo que o `click` também gravou.
    """
    p = _PonteDeMentira()
    ctx = _ctx([], autoswitch_locked=False)
    aba.cadeado(ctx, {"evento": "click"}, p)
    assert p.chamadas == [], (
        "o `click` gravou: um clique na caixa grava DUAS vezes no disco dela")

    aba.cadeado(ctx, {"evento": "change"}, p)
    assert len(p.chamadas) == 1, "o `change` não gravou"

    # E UM RECADO SEM `evento` CONTINUA VALENDO: a régua dos botões monta o
    # clique à mão, e um gesto que só funcionasse com a chave presente estaria
    # medindo o instrumento, não o produto.
    aba.cadeado(ctx, {}, p)
    assert len(p.chamadas) == 2, (
        "um clique sem `evento` foi engolido — o padrão tem de ser `change`")


def test_a_palavra_do_cadeado_e_a_que_ela_ja_leu() -> None:
    """O rótulo e a dica são da janela antiga, palavra por palavra.

    **A RÉGUA LÊ, NÃO DIGITA** — esta casa pagou onze vezes em 26/08 por réguas
    que digitavam o que deviam ler. O dono das duas frases é o `Gtk.CheckButton`
    de `home_actions._build_home`, e ele não pode ser lido em tempo de execução
    sem montar a GTK dentro do pacote das dez abas. Então o pacote DECLARA e
    esta régua confere contra o fonte: no dia em que a janela antiga trocar a
    palavra, a tela nova não fica falando sozinha.

    A MORDIDA: mude uma letra de `CADEADO_ROTULO` e esta régua reprova.
    """
    import re

    fonte = (RAIZ / "src/hefesto_dualsense4unix/app/actions/home_actions.py"
             ).read_text()
    # OS LITERAIS ADJACENTES SÃO COLADOS ANTES DE MEDIR — o rótulo e a dica
    # viajam quebrados em três pedaços no fonte da GTK, e uma régua que
    # procurasse a frase inteira reprovaria a cada reformatação em vez de a cada
    # mudança de PALAVRA. É a mesma cirurgia que o `_conferir` faz ao tirar os
    # comentários HTML antes de contar: medir o que a tela diz, não como o
    # arquivo está quebrado.
    colado = re.sub(r'"\s*\n\s*"', "", fonte)

    assert f'label="{aba.CADEADO_ROTULO}"' in colado, (
        f"o rótulo {aba.CADEADO_ROTULO!r} não é o do `Gtk.CheckButton` da "
        f"janela antiga — texto de tela novo é decisão DELA, e este devia ser "
        f"texto que ela já leu")
    assert aba.CADEADO_DICA in colado, (
        "a dica do cadeado se afastou da da janela antiga. As duas dizem a "
        "mesma coisa para a mesma pessoa; duas versões vivas é o defeito que a "
        "regra do fato-errado existe para matar")


def test_o_cadeado_esta_na_pagina_com_os_dois_lados() -> None:
    """Endereço de pintura E endereço de clique — um sem o outro é meio botão.

    Sem o `data-campo`, a caixa deixa mudar e não mostra o que o daemon
    guardou; sem o `data-gesto`, ela muda de marca e não muda nada no produto —
    que é o defeito que o `BOTOES_SEM_DONO` desta aba existe para nomear.

    A MORDIDA: tire um dos dois do gerador e ele REPROVA antes desta régua
    (`aba01._conferir` §11).
    """
    doc = _pagina()

    assert doc.count('data-campo="cadeado" data-hef-alvo="marcado"') == 1
    assert doc.count('data-gesto="cadeado"') == 1
    assert aba.CADEADO_ROTULO in doc, "o rótulo do cadeado não está na tela"
    assert aba.CADEADO_DICA in doc, "o cadeado está sem a razão na dica"


@pytest.mark.skipif(not pathlib.Path("/usr/bin/google-chrome").exists()
                    or shutil.which("python3") is None,
                    reason="sem o Chrome do sistema não há tela a ler")
def test_o_cadeado_continua_na_tela_com_o_hefesto_desligado() -> None:
    """A régua que LÊ A TELA, e é a única que pega este defeito.

    O quadro **Modo** tem duas seções que se trocam com o interruptor
    (`.so-ligado` e `.so-desligado`), e a troca automática de PERFIL vale nas
    duas. Uma caixa aninhada dentro de uma delas sumiria na outra posição — e
    sumiria em SILÊNCIO: nenhuma contagem de `data-campo` vê isso, porque o
    endereço continua no arquivo.

    **É a diferença entre a ordem no arquivo e o aninhamento no DOM**, e só o
    navegador responde por ela: a régua pergunta ao `getComputedStyle` nas DUAS
    posições do interruptor.

    A MORDIDA: mova o `<label class="cadeado">` para dentro do
    `<div class="hef-modo so-ligado">`, gere de novo e esta régua reprova na
    posição Desligado.
    """
    playwright = pytest.importorskip("playwright.sync_api")

    alvo = onde.pagina("01-jogar.html")
    with playwright.sync_playwright() as pw:
        b = pw.chromium.launch(executable_path="/usr/bin/google-chrome",
                               args=["--no-sandbox"])
        pg = b.new_page(viewport={"width": 1920, "height": 1080})
        pg.goto(f"file://{alvo}")
        pg.wait_for_load_state("load")
        medido = pg.evaluate("""(() => {
          const ler = () => {
            const c = document.querySelector('label.cadeado');
            const l = document.querySelector('.hef-modo.so-ligado');
            const d = document.querySelector('.hef-modo.so-desligado');
            if(!c || !l || !d) return null;
            const vis = (el) => getComputedStyle(el).display !== 'none'
                                && el.getBoundingClientRect().height > 0;
            return {cadeado: vis(c), ligado: vis(l), desligado: vis(d)};
          };
          const fora = {ligado: ler()};
          document.getElementById('hef-desligado').checked = true;
          fora.desligado = ler();
          // E A COR DO "PLAYER N", medida ANTES e DEPOIS da classe — a folha do
          // esmaecido é o que nenhuma contagem de endereço alcança.
          const p1 = document.querySelector(
            '[data-controle="p1"] b[data-campo="jogador-espera"]');
          const p2 = document.querySelector(
            '[data-controle="p2"] b[data-campo="jogador-espera"]');
          const cor = {p1: getComputedStyle(p1).color,
                       antes: getComputedStyle(p2).color};
          p2.classList.add('espera');
          cor.depois = getComputedStyle(p2).color;
          cor.texto = p2.querySelector('[data-campo="jogador"]').textContent;
          fora.cor = cor;
          return fora;
        })()""")
        b.close()

    assert medido["ligado"] and medido["desligado"], (
        "a régua não achou o cadeado nem as duas seções — seletor que casa ZERO "
        "elemento é ERRO, nunca medida")
    # A PROVA DE QUE A RÉGUA NÃO É VÁCUA: o interruptor de fato trocou as seções.
    # Sem esta linha, um CSS que deixasse as duas visíveis daria verde sobre uma
    # tela que não muda.
    assert medido["ligado"]["ligado"] and not medido["ligado"]["desligado"], (
        "o interruptor não trocou as seções — a régua está medindo o próprio "
        "instrumento")
    assert medido["desligado"]["desligado"] and not medido["desligado"]["ligado"]

    assert medido["ligado"]["cadeado"], "o cadeado sumiu com o Hefesto LIGADO"
    assert medido["desligado"]["cadeado"], (
        "o cadeado sumiu com o Hefesto DESLIGADO — ele foi aninhado dentro de "
        "uma seção do interruptor, e a troca automática de perfil vale nos dois")

    # E O ESMAECIDO É COR NA TELA, não uma classe no atributo. Um `data-campo`
    # certo com a regra de folha faltando acende a classe e não muda um pixel —
    # e nenhuma contagem de endereço vê isso. Por isso a medida é `color`.
    assert medido["cor"]["antes"] == medido["cor"]["p1"], (
        "os dois cartões já nascem com cores diferentes — a régua está medindo "
        "outra coisa")
    assert medido["cor"]["depois"] != medido["cor"]["antes"], (
        f"o número do jogador ficou na mesma cor com a classe `espera` acesa "
        f"({medido['cor']['depois']}) — a classe pinta e a folha não responde")
    assert medido["cor"]["texto"] == "Player 2", (
        f"a pintura trocou a PALAVRA para {medido['cor']['texto']!r}. A D-04 "
        f"dela é 'Player N, como está hoje' — o esmaecido só muda a cor")


# ---------------------------------------------------------------------------
# [01] A METADE QUE NÃO FECHA, e é decisão DELA
# ---------------------------------------------------------------------------
def test_o_aviso_do_nativo_continua_fora_por_decisao_dela() -> None:
    """A decisão [01] pede uma frase que ELA MANDOU TIRAR — e ela ganha.

    A decisão [01] desta sprint é *"na coluna Atenção, só má notícia: o aviso do
    Modo Nativo enquanto ele vigora"*, e a frase que a lista da aba nomeia é a
    do `_MODE_DESCRIPTIONS["native"]`: *"Alguns jogos derrubam o controle no
    meio da partida neste modo"*.

    **ESSA FRASE SAIU DESTA ABA POR ORDEM DELA, em 31/08/2026**, e o gerador tem
    régua para ela desde então (`aba01._conferir` §6-bis): *"NENHUM ALARME SEM
    MEDIÇÃO. Ela, 31/08: 'qualquer coisa fora isso tá incorreta' — a regra do
    Nativo é só 'Desligado põe o Nativo online'."* Ensaio nenhum deste
    repositório mede quantos jogos derrubam o controle no Modo Nativo.

    **É UM OITAVO CONFLITO**, da mesma família dos sete que o
    `2026-09-04-O-PO-DECIDE-as-54-e-os-sete-conflitos.md` §1 nomeia: a lista
    desta aba nasceu no mesmo dia que as dezesseis decisões dela e reconciliou
    contra ELAS — não contra as de 31/08, que vivem numa régua de gerador. A
    regra do próprio documento decide: *"Onde contradiz, ela ganha."*

    E A SEGUNDA METADE DA DECISÃO [01] FECHOU: a linha "Ponte com o jogo" entra
    na coluna Atenção nos dois desfechos ruins, e quem a mede é
    `test_a01_a_ponte_entra_na_coluna.py`.

    ESTA RÉGUA É UMA LÁPIDE COM MEDIÇÃO. Ela reprova no dia em que alguém puser
    a frase na coluna sem passar pelo olho dela — inclusive por baixo do
    gerador, que é o caminho que a régua §6-bis **não** cobre: o `_conferir` lê
    o HTML estático, e a coluna Atenção é escrita em tempo de execução.
    """
    from hefesto_dualsense4unix.app.actions import home_actions

    # O ALARME EXISTE NO PRODUTO ANTIGO, e é o que faz esta régua não ser vácua:
    # se a frase sumir de lá, esta lápide perde o objeto e tem de ser relida.
    nativo = home_actions._MODE_DESCRIPTIONS["native"]
    assert "derrubam o controle" in nativo, (
        "a frase do Modo Nativo sumiu da janela antiga — esta lápide ficou sem "
        "objeto e a decisão [01] precisa ser relida com ela")

    # E ELE NÃO CHEGA À COLUNA POR NENHUM CAMINHO — nem no Modo Nativo, que é
    # exatamente o estado em que a decisão [01] o pediria.
    ctx = _ctx([], native_mode=True,
               gamepad_emulation={"enabled": False, "flavor": "dualsense"})
    textos = [str(a.get("texto") or "") for a in aba._avisos(ctx)]
    assert not any("derrubam o controle" in t for t in textos), (
        "o aviso do Modo Nativo entrou na coluna Atenção. Ela mandou tirá-lo "
        "desta aba em 31/08 — 'qualquer coisa fora isso tá incorreta' — e "
        "ensaio nenhum desta casa mede quantos jogos derrubam o controle. "
        "Se a decisão mudou, ela muda com o olho DELA, não por baixo do gerador")
