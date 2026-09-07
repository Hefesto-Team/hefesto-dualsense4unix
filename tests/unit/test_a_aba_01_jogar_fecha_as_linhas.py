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

import monta
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

    NOS QUATRO LUGARES DESDE 07/09/2026 (QUATRO-NA-MESA-01). A conta era DOIS,
    e dois era o defeito: o lugar vazio saía sem endereço nenhum, e o "Player 3"
    que o daemon publicava quando o terceiro controle chegava não tinha onde
    pousar. O travessão continua sendo o texto de repouso — o que muda é a
    ESTRUTURA que o gerador emite, nunca a `monta.MESA`.

    A MORDIDA: ponha os dois `data-campo` no mesmo `<b>` e o gerador REPROVA
    antes desta régua — `aba01._conferir` §10 mede as duas coisas.
    """
    doc = _pagina()
    lugares = len(monta.MESA)

    assert doc.count('data-campo="jogador-espera" data-hef-alvo="classe"'
                     ' data-hef-classe="espera"') == lugares, (
        f"os {lugares} lugares da mesa não têm o endereço do esmaecido")
    assert doc.count('<span data-campo="jogador">') == lugares, (
        "o número do jogador deixou de ser folha — a pintura apagaria os filhos")
    assert 'class="espera"' not in doc, (
        "um cartão nasce esmaecido: a cena que ela aprovou tem os dois "
        "controles recebidos pelo jogo")
    # E O LUGAR VAZIO CONTINUA MOSTRANDO SÓ O TRAVESSÃO. O endereço entrou; o
    # texto não. Sem esta linha a régua acima passaria com o desenho dizendo
    # "Player 3" num lugar onde não há controle nenhum.
    vazios = doc.split('class="cartao off"')[1:]
    assert len(vazios) == lugares - len(monta.CONECTADOS), (
        "a cena que ela aprovou deixou de ter dois lugares vazios")
    for pedaco in vazios:
        cartao = pedaco.split("</div>\n              </div>")[0]
        assert '<span data-campo="jogador">—</span>' in cartao, (
            "um lugar vazio deixou de mostrar o travessão no número do jogador"
        )
        assert '<span data-campo="identidade">—</span>' in cartao, (
            "um lugar vazio deixou de mostrar o travessão na identidade")


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


#: O SENTINELA DO DUBLÊ: *responda o que o serviço responderia*.
_ECOA = object()


class _PonteDeMentira:
    """Guarda o que foi chamado — e responde ao cadeado como o serviço responde.

    O `__getattr__` responde por QUALQUER nome, e isso é de propósito: o dublê
    não pode virar uma segunda lista das funções da ponte, que envelheceria em
    silêncio.

    **MAS O `autoswitch_lock_set` GANHOU RESPOSTA PRÓPRIA — 06/09/2026, e a
    razão é a forma de defeito que esta casa mediu três vezes em 05/09: *o dublê
    era mais frouxo que a função real*.** O `__getattr__` devolvia `True` para
    tudo; `ipc_bridge.autoswitch_lock_set` devolve **o estado que ficou
    valendo** — logo um `True` sobre um pedido de DESTRAVAR era o dublê
    afirmando o contrário do que foi pedido, e um dublê assim não tem como
    revelar o gesto que ignora a resposta.

    `cadeado=` troca essa resposta, e é por ela que as duas metades do desfecho
    entram na régua: `None` é *o serviço não respondeu* e uma exceção é *a ponte
    levantou*.
    """

    def __init__(self, cadeado: Any = _ECOA) -> None:
        self.chamadas: list[tuple[str, tuple, dict]] = []
        self.cadeado = cadeado

    def autoswitch_lock_set(self, locked: Any = None) -> Any:
        self.chamadas.append(("autoswitch_lock_set", (), {"locked": locked}))
        if isinstance(self.cadeado, BaseException):
            raise self.cadeado
        # O ECO É O QUE O DAEMON FAZ, e não uma gentileza do dublê:
        # `_handle_autoswitch_lock` responde `novo = bool(pedido)` quando o
        # `locked` vem no pedido — o toggle é só para quem não manda valor.
        return bool(locked) if self.cadeado is _ECOA else self.cadeado

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


def test_o_cadeado_confirma_em_verde() -> None:
    """O gesto PEDE o verde voltando calado — e só quando o serviço confirmou.

    **O MECANISMO É O DO PILOTO, e esta régua mede o desfecho que este gesto
    devolve a ele, não o texto do código.** `hefesto_vivo._gesto` anota
    ``"aplicou"`` no ramo sem exceção, e o `finally` leva esse desfecho ao pouso
    (`_pousou(voo, certo)`), que acende `hef-deu-certo` por `MS_DA_PISCADA`. Um
    gesto que volta sem levantar JÁ pediu o verde; um que levanta não pede.
    Quem mede a piscada no DOM, com o WebKit e a página publicada, é a
    :func:`test_o_verde_do_cadeado_no_webkit_e_do_servico`, logo abaixo.

    **A MORDIDA — e ela é a que importa:** faça a ponte devolver `None` (o
    serviço parado) e esta régua reprova, porque o gesto voltou calado e o piloto
    vai acender o verde sobre uma escrita que não aconteceu. Era o estado do
    produto até 06/09/2026: a resposta da ponte ia para o lixo.

    A SEGUNDA MORDIDA: embrulhe a chamada num `try/except` e o caminho da ponte
    que LEVANTA passa a pedir o verde do mesmo jeito — a régua reprova nas duas
    metades de baixo.
    """
    # 1. O SERVIÇO CONFIRMOU: volta calado, e é isso que acende o verde.
    p = _PonteDeMentira()
    assert aba.cadeado(_ctx([], autoswitch_locked=False),
                       {"evento": "change"}, p) is None
    assert p.chamadas, "o cadeado não chamou NADA"

    # 2. O SERVIÇO NÃO RESPONDEU (`None`): o verde não pode acender, e a frase
    #    vai para a tela dela — `RuntimeError` é o contrato do piloto para
    #    *"o produto recusou, e a frase VAI PARA A TELA"*.
    p = _PonteDeMentira(cadeado=None)
    with pytest.raises(RuntimeError) as caiu:
        aba.cadeado(_ctx([], autoswitch_locked=False), {"evento": "change"}, p)
    assert str(caiu.value) == aba.CADEADO_RECUSA, (
        f"a recusa disse {str(caiu.value)!r} — a frase é a da janela antiga, e "
        f"texto de tela novo é palavra dela")
    assert p.chamadas, "o gesto recusou sem sequer tentar escrever"

    # 3. A PONTE LEVANTOU: o gesto deixa subir. Um `try/except` aqui trocaria a
    #    recusa por uma piscada verde sobre nada.
    p = _PonteDeMentira(cadeado=RuntimeError("o socket recusou"))
    with pytest.raises(RuntimeError):
        aba.cadeado(_ctx([], autoswitch_locked=True), {"evento": "change"}, p)


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
    # A TERCEIRA FRASE — 06/09/2026, e ela nasceu com o mesmo dono. Quando o
    # serviço não responde, o gesto recusa DIZENDO, e o que ele diz é o que o
    # `_on_home_autoswitch_lock_toggled` já dizia no `resultado is None`.
    assert aba.CADEADO_RECUSA in colado, (
        f"a recusa do cadeado ({aba.CADEADO_RECUSA!r}) não é a frase que a "
        f"janela antiga põe na tela quando o `autoswitch_lock_set` volta "
        f"`None`. Texto de tela NOVO é decisão dela (PROVA-DE-TELA-01); esta "
        f"linha existe para que a tela nova não invente uma segunda maneira de "
        f"dizer o mesmo desfecho")


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


def test_o_cadeado_esta_publicado() -> None:
    """A caixa está na página que o PRODUTO abre — medido no arquivo, não na prosa.

    **O FATO QUE ESTA RÉGUA SUBSTITUI.** O fecho do gesto dizia que a caixa só
    existia no desenho da bancada e que o piloto abre o publicado — era verdade
    quando foi escrito e deixou de ser. A conclusão daquela frase (*o
    `--prova-gesto` não clica esta caixa*) continua de pé por OUTRO motivo, que
    é `PERIGOSOS`, e é esse motivo que o fonte tem de carregar.

    **A RÉGUA LÊ O ARQUIVO PUBLICADO, e é o que a impede de envelhecer igual à
    frase que ela veio corrigir.** `onde.pagina(…, publicado=True)` é o dono do
    caminho — o mesmo que o piloto abre nos seis caminhos dele —, e o número da
    linha sai da leitura, nunca digitado aqui.

    E A SEGUNDA METADE COBRA A PROSA CONTRA O FATO: com a caixa publicada, o
    docstring deste gesto não tem por que mandar ninguém procurá-la na bancada.
    A palavra é o sentinela, e não a frase inteira, pela lição de 05/09 — *citar
    literalmente o padrão que se vigia é como o aviso vira o defeito que ele
    descreve*: qualquer reformulação da afirmação morta reprova do mesmo jeito.

    A MORDIDA: ponha a frase velha de volta no fecho de :func:`a01_jogar.cadeado`
    e esta régua reprova nomeando a linha em que a caixa está publicada.
    """
    import inspect

    alvo = onde.pagina("01-jogar.html", publicado=True)
    assert alvo.exists(), f"a página que o produto abre não existe: {alvo}"
    linhas = alvo.read_text().splitlines()
    onde_esta = [n for n, linha in enumerate(linhas, 1)
                 if 'data-gesto="cadeado"' in linha]
    assert len(onde_esta) == 1, (
        f"a caixa do cadeado aparece {len(onde_esta)} vez(es) na página "
        f"publicada ({alvo}). Zero quer dizer que ela NÃO está no que o produto "
        f"renderiza — e aí o gesto está ligado a um botão que ela não tem como "
        f"clicar; mais de uma, que o clique tem dois endereços iguais")

    fonte = inspect.getsource(aba.cadeado).lower()
    assert "mockup" not in fonte, (
        f"o fonte do gesto `cadeado` ainda manda quem lê procurar a caixa na "
        f"bancada — e ela está PUBLICADA, em {alvo}:{onde_esta[0]}, que é o "
        f"arquivo que o piloto abre. Fato errado se SUBSTITUI: o que fica "
        f"escrito é a razão de o `--prova-gesto` não clicar esta caixa, que é "
        f"`PERIGOSOS` (o gesto grava preferência dela no disco)")


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

    ---

    **A LÁPIDE FOI RELIDA — 06/09/2026, ONDA5-01-02, e ela tinha DUAS metades.**

    A primeira exigia que a frase CONTINUASSE viva em `_MODE_DESCRIPTIONS`, e a
    razão escrita era *"se a frase sumir de lá, esta lápide perde o objeto"*.
    Foi essa linha que **prendeu a profecia na janela antiga por uma semana**: a
    frase já não tinha defensor nenhum, e mesmo assim uma régua desta casa
    reprovava quem a tirasse. Ela cai, com as três datas:

    * **31/08/2026** — *"qualquer coisa fora isso tá incorreta"*: o texto do
      Nativo encolheu na interface nova e a janela antiga não foi junto;
    * **04/09/2026** — a leitura de PO do oitavo conflito: a tela diz o ESTADO
      MEDIDO, nunca a consequência que ninguém mediu;
    * **05/09/2026** — *"Não me lembro disso acontecer. **E não deveria.** Mas
      caso ocorra na coluna atenção"*. É a releitura, e ela é dela.

    A segunda metade — *a frase não entra na coluna Atenção por caminho nenhum*
    — **fica, e fica mais forte**: o que a coluna diz hoje sobre o mesmo assunto
    é a linha medida da ONDA5-01-01, e a profecia continua de fora. O objeto da
    lápide deixou de ser a janela antiga e passou a ser a coluna.

    E A JANELA ANTIGA NÃO FICOU MUDA: a chave `"native"` continua existindo,
    encolhida e IGUAL à da interface nova — apagá-la escreveria string vazia na
    tela, que é trocar uma frase errada por nenhuma. Quem guarda o fonte agora é
    `test_a_frase_que_ela_baniu_nao_chega_a_tela::test_nenhuma_banida_vive_no_fonte`,
    a terceira guarda, que nasceu no mesmo dia por causa desta lápide.
    """
    from hefesto_dualsense4unix.app.actions import home_actions

    # A METADE QUE CAIU VIRA O SEU CONTRÁRIO: a janela antiga passou a dizer o
    # que a interface nova diz, palavra por palavra. Sem esta linha o passo 1
    # poderia ter apagado a chave — e `_MODE_DESCRIPTIONS.get(..., "")` escreve
    # string VAZIA, que é o defeito que a §5.4 da sprint nomeia.
    nativo = home_actions._MODE_DESCRIPTIONS["native"]
    assert nativo == (
        "Modo Nativo: o Hefesto sai do meio e o jogo fala direto com o "
        "controle."), (
        f"a descrição do Modo Nativo na janela antiga divergiu da interface "
        f"nova ({nativo!r}). Desde 06/09 as duas dizem a MESMA coisa, que é a "
        f"regra de 31/08 dela: 'Desligado põe o Nativo online', e nada além")

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


# ---------------------------------------------------------------------------
# JOGAR-O-QUE-FALTA-01 — as quatro linhas de 06/09/2026
# ---------------------------------------------------------------------------
def test_o_marcador_do_primario_anda_e_o_alvo_da_fita_nao() -> None:
    """Passo 3 — dois controles, um primário; troque e o marcador muda de cartão.

    Linha 18 do CSV: *"`is_primary` não é lido em `interface/pacotes/`; a classe
    `.cartao.alvo` existe mas responde a outra pergunta (o alvo de edição da
    fita)"*. A régua mede as DUAS metades: o marcador anda **e** o alvo não vai
    junto.

    **POR QUE O ALVO ENTRA NESTA RÉGUA:** se alguém reusar `.cartao.alvo` para o
    primário, o defeito só aparece no dia em que ela editar a fita com um
    controle que não é o primário — tarde, e na tela dela. Aqui aparece agora: o
    pacote não emite `alvo` nenhum, e quem o escreve é o piloto.

    A MORDIDA: troque `_e_o_primario` por `return "1"` e as duas primeiras
    afirmações reprovam (os dois cartões acendem); troque por `return ""` e a
    terceira reprova.
    """
    c1 = {"uniq": P1, "connected": True, "player_slot": 1, "player": 1,
          "is_primary": True, "transport": "usb"}
    c2 = {"uniq": P2, "connected": True, "player_slot": 2, "player": 2,
          "is_primary": False, "transport": "bt"}

    assert aba._e_o_primario(c1) == "1", "o primário não foi marcado"
    assert aba._e_o_primario(c2) == "", "um cartão que não é o primário acendeu"

    # O PRIMÁRIO ANDA: a MESMA mesa, com o `is_primary` do outro lado.
    assert aba._e_o_primario({**c1, "is_primary": False}) == ""
    assert aba._e_o_primario({**c2, "is_primary": True}) == "1"

    # E O PACOTE NÃO EMITE `alvo`: quem escolhe o alvo de edição da fita é o
    # piloto (`hefesto_vivo`, `carga["alvo"]`), e um pacote que o emitisse aqui
    # seria o segundo dono de uma escolha DELA.
    fora = aba.pacote(_ctx([c1, c2]))
    for uniq, campos in (fora["cartoes"] or {}).items():
        assert "alvo" not in campos, (
            f"o cartão {uniq} passou a emitir `alvo` — o alvo de edição da fita "
            "é escolha dela, escrita pelo piloto, e não fato do serviço")


def test_so_o_true_literal_acende_o_marcador() -> None:
    """Chave ausente não é "não é o primário" — é *não sei*, e não se afirma.

    Mesma disciplina do `_cadeado` e do `wrapper_used`: um daemon antigo (sem a
    chave) ou um payload de outro tipo não podem acender uma palavra sobre um
    controle.

    A MORDIDA: troque `is True` por um `bool(...)` e as três últimas reprovam.
    """
    assert aba._e_o_primario({}) == "", "sem a chave, o cartão afirmou"
    assert aba._e_o_primario({"is_primary": None}) == ""
    assert aba._e_o_primario({"is_primary": 1}) == "", "um `1` inteiro acendeu"
    assert aba._e_o_primario({"is_primary": "sim"}) == ""


def test_a_palavra_do_primario_e_a_que_ela_ja_leu() -> None:
    """A palavra do marcador é a da janela antiga — a régua LÊ, não digita.

    O dono é `home_actions._format_controller_subtitle`, que monta a linha
    secundária do card e acrescenta exatamente a palavra quando `is_primary`.

    A MORDIDA: mude uma letra de `MARCA_DO_PRIMARIO` e esta régua reprova.
    """
    fonte = (RAIZ / "src/hefesto_dualsense4unix/app/actions/home_actions.py"
             ).read_text()
    assert f'parts.append("{aba.MARCA_DO_PRIMARIO}")' in fonte, (
        f"a palavra {aba.MARCA_DO_PRIMARIO!r} não é a que a janela antiga põe na "
        f"linha secundária do card. Texto de tela novo é decisão DELA, e este "
        f"devia ser texto que ela já leu")


def test_a_marca_da_degradacao_tem_as_duas_condicoes() -> None:
    """Passo 4 — backend degradado **E** motivo. Uma só acende alarme sobre nada.

    Linha 32 do CSV: *"o `backend` não é lido pelo pacote da 01;
    `pacotes.degradacao_de` existe e não é chamada por esta aba"*.

    **O DONO DECIDE, e a régua prova que esta aba PERGUNTA a ele.** A máscara
    Xbox é `uinput` POR DESENHO (motivo `None`) e não é degradação nenhuma;
    controle sem gamepad virtual próprio idem. Reescrever essas duas condições
    aqui seria a segunda lista de motivos desta casa.

    A MORDIDA: com o motivo vazio o campo tem de vir `""` — e o alvo `atributo`
    do piloto REMOVE o `title`, que é o que apaga a marca.
    """
    base = {"uniq": P1, "connected": True, "player_slot": 1, "player": 1,
            "transport": "usb"}
    degradado = {**base, "vpad_backend": "uinput",
                 "vpad_motivo": "uhid_indisponivel"}

    fora = aba.pacote(_ctx([degradado]))
    marca = (fora["cartoes"] or {})[P1]["degradou-cartao"]
    assert marca, "a marca não acendeu com backend degradado E motivo"

    # DUAS CONDIÇÕES, E CADA UMA SOZINHA É SILÊNCIO.
    so_backend = {**base, "vpad_backend": "uinput"}
    assert aba.pacote(_ctx([so_backend]))["cartoes"][P1]["degradou-cartao"] == "", (
        "a marca acendeu com o backend `uinput` e SEM motivo — é a máscara Xbox "
        "por desenho, e alarme sem medição é o que ela baniu em 31/08")
    so_motivo = {**base, "vpad_motivo": "uhid_indisponivel"}
    assert aba.pacote(_ctx([so_motivo]))["cartoes"][P1]["degradou-cartao"] == "", (
        "a marca acendeu sem o backend degradado")

    # E A FRASE É INTEIRA DO DONO — não uma segunda tradução do motivo.
    from hefesto_dualsense4unix.app.widgets.controller_card import texto_degradacao

    assert marca == texto_degradacao(degradado), (
        "a frase da marca se afastou da do dono (`controller_card."
        "texto_degradacao`) — duas traduções do mesmo motivo é o defeito que "
        "o `_do_exame` já custou a esta aba")


def test_o_servico_calado_diz_e_para_de_afirmar() -> None:
    """Passo 5 — com o estado vazio a coluna DIZ, e nada mais é afirmado.

    Linha 38 do CSV, e é o passo que mais vale: *"o tique imprime `[daemon mudo]`
    no stderr e retorna sem pintar nada — a tela fica com os últimos valores"*.

    **A OMISSÃO ERA A MENTIRA, e ela tinha número:** medido antes desta cura, com
    o estado vazio, a coluna emitia ``atencao-conta = "nenhum aviso"`` e seis
    linhas em branco. *"Nenhum aviso"* é uma AFIRMAÇÃO — quer dizer "perguntei e
    não há nada".

    A MORDIDA: troque `_aviso_do_servico_calado` por `return None` e esta régua
    reprova nas duas primeiras afirmações.
    """
    fora = aba.pacote(Contexto(state={}, mesa=[], conectados=[], estados={}))

    assert aba.SELO_DO_SERVICO in fora["aviso-selo"], (
        "a coluna Atenção ficou calada com o serviço calado — e a conta ao lado "
        "diz 'nenhum aviso', que é a tela afirmando sobre um estado que ninguém "
        "leu")
    i = list(fora["aviso-selo"]).index(aba.SELO_DO_SERVICO)
    assert fora["aviso-texto"][i] == aba.SERVICO_CALADO
    assert fora["atencao-conta"] != _painel_do_produto().texto_da_conta(0), (
        "a conta continuou dizendo 'nenhum aviso' com a linha do serviço acesa")

    # E NADA MAIS É AFIRMADO: as outras respostas da aba continuam mudas.
    assert fora["hef-posicao"] == "", "o interruptor acendeu sem estado"
    assert fora["modo-aceso"] == "", "um chip da fileira acendeu sem estado"
    assert fora["cadeado"] == "", "o cadeado afirmou uma escolha dela"
    assert fora["mesa-frase"] == "", (
        "a frase da mesa vazia apareceu — 'nenhum controle na mesa' sobre um "
        "tique sem resposta é a tela afirmando o que não leu")
    assert not fora["cartoes"], "um cartão foi afirmado sem estado"


def test_com_o_servico_vivo_a_linha_do_servico_nao_existe() -> None:
    """E ela SOME sozinha quando o serviço volta — sem clique nenhum.

    É a outra metade da promessa que a própria frase faz (*"ela volta sozinha
    quando o serviço responder"*). Uma linha que ficasse acesa com o daemon vivo
    seria pior que o silêncio que ela veio curar.

    A MORDIDA: troque a guarda por `return {...}` incondicional e esta régua
    reprova.
    """
    c1 = {"uniq": P1, "connected": True, "player_slot": 1, "player": 1,
          "is_primary": True, "transport": "usb"}
    fora = aba.pacote(_ctx([c1]))
    assert aba.SELO_DO_SERVICO not in fora["aviso-selo"], (
        "a linha do serviço calado continuou na coluna com o daemon vivo")


def test_o_selo_do_servico_abre_a_escada_da_gravidade() -> None:
    """Com o serviço calado, TODA outra linha descreveria o que ninguém leu.

    O critério da escada é *o que invalida o quê*, e está escrito na tupla. A
    ``PAUSA`` já vinha primeiro por isso; o serviço calado é um degrau acima —
    com ele, nem a pausa se sabe.

    A MORDIDA: tire ``SERVIÇO`` de `ORDEM_DA_GRAVIDADE` e ele cai para DEPOIS de
    tudo (`posto.get(..., fim)`), onde a coluna cheia o esconde atrás do ``+N``.
    """
    assert aba.ORDEM_DA_GRAVIDADE[0] == aba.SELO_DO_SERVICO, (
        "o selo do serviço saiu da frente da escada")
    selos, _ = aba._coluna_de_avisos([
        {"selo": "PERFIL", "texto": "a"}, {"selo": "PAUSA", "texto": "b"},
        {"selo": aba.SELO_DO_SERVICO, "texto": "c"},
    ])
    assert selos[0] == aba.SELO_DO_SERVICO, f"a coluna ordenou {selos!r}"


def test_a_frase_do_servico_e_a_que_ela_ja_leu() -> None:
    """A primeira frase é a da janela GTK, palavra por palavra — a régua LÊ.

    `home_actions._render_home` escreve ``set_text("O Hefesto está desligado.")``
    no ramo `offline`, e o `validar-palavra-de-tela` já a declara como a
    tradução de "daemon offline".

    A MORDIDA: mude uma letra de `SERVICO_DESLIGADO` e esta régua reprova.
    """
    fonte = (RAIZ / "src/hefesto_dualsense4unix/app/actions/home_actions.py"
             ).read_text()
    assert f'set_text("{aba.SERVICO_DESLIGADO}")' in fonte, (
        f"{aba.SERVICO_DESLIGADO!r} não é a frase que a janela antiga escreve "
        f"com o daemon fora do ar — texto de tela novo é decisão DELA")
    assert aba.SERVICO_CALADO.startswith(aba.SERVICO_DESLIGADO), (
        "a frase da coluna deixou de começar pela frase do dono")


def test_nenhuma_das_frases_novas_fala_de_maquina() -> None:
    """As palavras proibidas do glossário não entram em texto de tela.

    `uinput`, `hidraw`, `vpad`, `evdev`, `MAC`, `uniq` e "mesa" são proibidos, e
    a régua olha as frases que ESTA aba escreve. A da ponte entra aqui porque é
    a que a sprint manda medir: *"três dublês, três pontes, três frases; nenhuma
    com palavra proibida"*.

    **A MARCA DA DEGRADAÇÃO É A EXCEÇÃO DECLARADA, e não um esquecimento:** ela
    não é texto de tela em linha — é `title`, a DICA, que é onde o glossário põe
    a explicação (§3), e a frase inteira é do dono na janela GTK. A mesma
    escolha do cartão da aba 02, que a publica desde 04/09.

    A MORDIDA: escreva `uinput` em `SERVICO_CALADO` e esta régua reprova.
    """
    from hefesto_dualsense4unix.app.actions import home_actions

    #: AS PALAVRAS DE MÁQUINA — as quatro que a sprint nomeia, mais o `uniq`.
    de_maquina = ("uinput", "hidraw", "vpad", "evdev", "uniq")
    #: AS FRASES DESTA POSSE.
    minhas = [aba.SERVICO_CALADO, aba.SERVICO_DESLIGADO, aba.PRIMARIO_DICA,
              aba.MARCA_DO_PRIMARIO]
    #: AS CINCO PONTES, uma por dublê — as duas primeiras chegam à coluna
    #: Atenção (má notícia), as três últimas não, e as cinco passam por aqui.
    #: O MARKUP FICA, e não é descuido: quem o tira é `gui.aba_sistema.sem_markup`,
    #: e a janela GTK está sendo aposentada (D-0609-GTK-LEVA-INTEIRA) — uma
    #: citação nova para ela reprova no portão `nada-aponta-para-a-janela`. Para
    #: esta medida o markup não atrapalha: `<span foreground="#50fa7b">` não tem
    #: palavra de máquina nenhuma, e o que se procura é a palavra DENTRO da
    #: frase. Quem tira o markup de verdade, no produto, é `_aviso_da_ponte`.
    da_ponte = [
        home_actions.texto_da_ponte(cena)
        for cena in (
            {"connected": True, "native_mode": False,
             "gamepad_emulation": {"enabled": False, "flavor": "dualsense"}},
            {"connected": True, "native_mode": False, "controllers": [],
             "gamepad_emulation": {"enabled": True, "flavor": "dualsense"}},
            {"connected": True, "native_mode": False,
             "gamepad_emulation": {"enabled": True, "flavor": "dualsense"},
             "controllers": [{"uniq": P1, "connected": True, "player_slot": 1}]},
            {"connected": True, "native_mode": True,
             "gamepad_emulation": {"enabled": False, "flavor": "dualsense"},
             "controllers": [{"uniq": P1, "connected": True, "player_slot": 1}]},
            None,
        )
    ]
    assert len(set(da_ponte)) == 5, (
        f"as cinco pontes deixaram de ser cinco frases distintas: {da_ponte!r}")

    for frase in minhas + da_ponte:
        baixa = f" {frase.lower()} "
        for palavra in de_maquina:
            assert palavra not in baixa, (
                f"a palavra {palavra!r} chegou a texto de tela: {frase!r}. O "
                f"glossário (`docs/A-LINGUA-DESTA-CASA`) a proíbe")

    # A PALAVRA "mesa" É MEDIDA SÓ NAS FRASES DESTA POSSE, e a razão é um ACHADO
    # que esta régua fez e não pode curar — está no relato desta sprint:
    #
    #     home_actions.py:1342  "…não há nenhum controle na mesa para alimentá-lo"
    #     home_actions.py:1697  f"{total} controles na mesa: …"
    #
    # A primeira é a ponte *"de pé, e vazia"*, e ela CHEGA à coluna Atenção
    # desta aba desde 04/09 — logo a palavra banida está na tela dela hoje. Quem
    # tira a palavra é a `A-PALAVRA-MESA-SAI-01`, e ela **não alcança**:
    # `src/hefesto_dualsense4unix/app/` está no `nao_toca` daquele frontmatter, e
    # ela roda DEPOIS desta. Medir aqui as frases de outra posse deixaria esta
    # régua vermelha por um defeito que ela não pode fechar — e régua vermelha
    # por dívida alheia é a que alguém desliga.
    for frase in minhas:
        assert " mesa " not in f" {frase.lower()} ", (
            f'a palavra "mesa" entrou numa frase desta aba: {frase!r}. Decisão '
            f"dela, 06/09: o termo sai da tela e entra o simples")


def test_o_modo_clicado_entra_no_perfil_ativo(tmp_path, monkeypatch) -> None:
    """Passo 1 — a máscara clicada na 01 é o que a aba 10 lê. UM dono, duas telas.

    Linha 5 do CSV: *"nada. `_ESCOLHA`/`_ROTULO` são dicionários de módulo lidos
    só dentro do próprio arquivo"*, e a consequência: *"ela escolhe 'Xbox' na 01,
    clica em 'Salvar Perfil' na 10, e o perfil grava a máscara que estava no
    disco — a escolha dela não entra."*

    **A LEITURA DE VOLTA É PELO CAMINHO DA ABA 10**, e é o que faz esta régua
    valer: `perfis_web._pacote_do_editor` é o que o quadro «Modo» daquela aba
    mostra (PERFIL-MODO-01). Ler o `.json` direto provaria só que alguém gravou
    um arquivo; ler por aqui prova que **a outra tela vê**.

    A MORDIDA: arranque a chamada de `_gravar_o_modo_do_chip` do gesto
    `modo_xbox` e esta régua reprova dizendo que a aba 10 continua sem modo.
    """
    from hefesto_dualsense4unix.app.actions import perfis_web
    from hefesto_dualsense4unix.profiles import loader
    from hefesto_dualsense4unix.profiles.schema import MatchAny, Profile

    monkeypatch.setattr("hefesto_dualsense4unix.utils.xdg_paths.profiles_dir",
                        lambda: tmp_path)
    monkeypatch.setattr(loader, "_profiles_dir", lambda: tmp_path, raising=False)
    nome = "Régua do Modo"
    loader.save_profile(Profile(name=nome, match=MatchAny(), priority=40),
                        origem="régua")

    ctx = _ctx([], active_profile=nome)
    assert perfis_web._pacote_do_editor(loader.load_profile(nome))["modo"] == (
        perfis_web.MODO_SEM_OPINIAO), "o perfil da régua já nasceu com modo"

    class _Ponte:
        def chamar(self, *a: Any, **kw: Any) -> bool:
            return True

    aba.modo_xbox(ctx, {"texto": "Xbox"}, _Ponte())

    lido = perfis_web._pacote_do_editor(loader.load_profile(nome))["modo"]
    assert lido == "gamepad", (
        f"a aba 10 continua vendo {lido!r} depois de o chip Xbox ser clicado na "
        f"01 — a escolha dela não atravessou as duas telas")
    modo = loader.load_profile(nome).mode
    assert modo is not None and modo.gamepad_flavor == "xbox", (
        f"a máscara não entrou na seção `mode`: {modo!r}")


def test_a_escrita_no_perfil_nunca_levanta(monkeypatch) -> None:
    """Ela é efeito colateral de um gesto que já foi ao daemon — e não pode falhar.

    Uma exceção aqui transformaria uma troca de modo bem-sucedida em tarja de
    recusa. É a mesma política de `perfil.com_a_carona`.

    A MORDIDA: tire o `try` de `perfil.gravar_o_modo_no_ativo` e esta régua
    reprova com o `OSError` do dublê.
    """
    from hefesto_dualsense4unix.interface.pacotes import perfil as _perfil

    def _explode(*_a: Any, **_kw: Any) -> Any:
        raise OSError("o disco recusou")

    monkeypatch.setattr(_perfil, "nome_do_ativo", lambda *_a: "Qualquer")
    monkeypatch.setattr(_perfil, "_com_o_src", _explode)
    assert _perfil.gravar_o_modo_no_ativo({}, "gamepad", "xbox") == "", (
        "a gravação levantou — o gesto viraria tarja de recusa sobre um modo "
        "que o daemon já aplicou")


def test_sem_perfil_ativo_nao_se_inventa_um(monkeypatch) -> None:
    """Sem perfil valendo, não há onde gravar — e não se cria um.

    A MORDIDA: faça `gravar_o_modo_no_ativo` cair num nome padrão e esta régua
    reprova.
    """
    from hefesto_dualsense4unix.interface.pacotes import perfil as _perfil

    monkeypatch.setattr(_perfil, "nome_do_ativo", lambda *_a: "")
    assert _perfil.gravar_o_modo_no_ativo({}, "gamepad", "xbox") == ""


def test_a_secao_do_modo_e_a_regra_do_dono() -> None:
    """"none" REMOVE a seção, e a máscara não é inventada fora do modo jogo.

    A regra é a de `profiles_actions._mode_section_from_editor`, e a cicatriz é
    ESCOLHA-DELA-VENCE-01/E1: havia um ``or "xbox"`` no Salvar da janela
    estável, e bastava salvar um perfil para ele passar a EXIGIR Xbox.

    A MORDIDA: troque o `elif flavor:` por um `campos["gamepad_flavor"] = flavor`
    incondicional e a terceira afirmação reprova.
    """
    from hefesto_dualsense4unix.interface.pacotes import perfil as _perfil
    from hefesto_dualsense4unix.profiles.schema import ProfileModeConfig

    assert _perfil.secao_do_modo(None, "none") is None
    antes = ProfileModeConfig(kind="gamepad", gamepad_flavor="xbox")
    assert _perfil.secao_do_modo(antes, "none") is None

    # FORA DO MODO JOGO A MÁSCARA É ZERADA — "JSON limpo, sem sobras".
    fora = _perfil.secao_do_modo(antes, "native")
    assert fora is not None and fora.gamepad_flavor is None

    # E DENTRO DELE, SEM ESCOLHA, O DISCO É PRESERVADO.
    fica = _perfil.secao_do_modo(antes, "gamepad")
    assert fica is not None and fica.gamepad_flavor == "xbox", (
        "a máscara do disco foi apagada por um clique que não a escolheu — é a "
        "cicatriz do `or \"xbox\"` pelo avesso")


def _painel_do_produto() -> Any:
    from hefesto_dualsense4unix.app.actions.jogar import painel

    return painel


# ---------------------------------------------------------------------------
# O VERDE DO CADEADO, MEDIDO NO DOM — o piloto do produto, a página publicada
# ---------------------------------------------------------------------------
#
# POR QUE ESTA RÉGUA ABRE UM WebKit DE VERDADE: porque a forma de defeito mais
# cara desta casa é *alguém curar o caminho e provar a cura num caminho que ela
# não usa*. As três medições acima provam o desfecho que o gesto DEVOLVE; esta
# prova o pixel — a caixa que ela clica, na página que o produto renderiza, com
# o `BOOTSTRAP` vivo e o pouso do piloto decidindo a cor.
#
# E ELA NÃO TOCA NO DISCO DELA. O dublê entra em `hefesto_vivo.ponte`, um degrau
# ANTES do socket: nenhum `autoswitch.lock` sai, nenhum
# `save_autoswitch_locked` roda. É o que torna medível um gesto que está em
# `PERIGOSOS` — a régua de clique do piloto continua, e deve continuar, sem
# clicar esta caixa.

#: A MESA DUBLÊ desta medição. `autoswitch_locked: False` é o que faz o clique
#: pedir `locked=True` — a mesma direção da prova declarada em `PROVAS`.
_ESTADO_DO_WEBKIT: dict[str, Any] = {
    "active_profile": "regua",
    "gamepad_emulation": {"flavor": "dualsense"},
    "autoswitch_locked": False,
    "controllers": [
        {"uniq": P1, "connected": True, "transport": "usb", "player": 1},
        {"uniq": P2, "connected": True, "transport": "bt", "player": 2},
    ],
}

#: A LEITURA. A cor vem do CSSOM e não da classe, pela mesma razão da régua do
#: recado: a classe diz que a regra foi ESCRITA, o CSSOM diz que ela PEGOU — a
#: piscada é `outline`, e um `!important` arrancado a deixaria muda justamente
#: nos campos que declaram cor própria.
_LER_O_CADEADO = r"""
(function(){
  const c = document.querySelector('input[data-gesto="cadeado"]');
  if(!c) return JSON.stringify({achou: false});
  const cs = getComputedStyle(c);
  return JSON.stringify({
    achou: true,
    verde: c.classList.contains('hef-deu-certo'),
    em_voo: c.classList.contains('hef-em-voo'),
    contorno: cs.outlineColor,
    contorno_larg: cs.outlineWidth,
  });
})()
"""

#: O CLIQUE, na caixa do produto. Clicar por coordenada é a armadilha que esta
#: casa já pagou duas vezes.
_CLICAR_NO_CADEADO = r"""
(function(){
  const c = document.querySelector('input[data-gesto="cadeado"]');
  if(!c) return 'NAO ACHEI A CAIXA DO CADEADO NA PAGINA PUBLICADA';
  c.click();
  return 'cliquei';
})()
"""


@pytest.fixture(scope="module")
def no_webkit() -> dict:
    """Abre o piloto DE VERDADE, oculto, e clica a caixa nos TRÊS desfechos."""
    gi = pytest.importorskip("gi", reason="a GUI precisa do PyGObject do sistema")
    gi.require_version("Gtk", "3.0")
    gi.require_version("WebKit2", "4.1")
    from gi.repository import GLib, Gtk

    if not Gtk.init_check(None)[0]:
        pytest.skip("sem sessão gráfica — o WebKit não abre")

    import argparse
    import json
    import time as _time

    import hefesto_vivo as hv

    # OS DUBLÊS SÃO DEVOLVIDOS NO FIM: `mesa_viva` e `pacotes.ponte` são módulos
    # COMPARTILHADOS do produto, e deixá-los sujos entrega uma mesa de mentira a
    # todo vizinho que abrir um `Piloto` depois, no mesmo processo.
    guardado = (hv.mesa_viva.estado_do_daemon, hv.ponte.autoswitch_lock_set)
    da_piscada_ms = int(hv.MS_DA_PISCADA)
    hv.mesa_viva.estado_do_daemon = (  # type: ignore[assignment]
        lambda *a, **k: _ESTADO_DO_WEBKIT)

    # O QUE A PONTE RESPONDE, trocado a cada etapa. O primeiro é o ECO do
    # serviço vivo (`_handle_autoswitch_lock` responde `bool(pedido)`).
    resposta: dict[str, Any] = {"como": "eco"}

    def _ponte_do_cadeado(locked: Any = None) -> Any:
        if resposta["como"] == "levanta":
            raise RuntimeError("o socket recusou o autoswitch.lock")
        return bool(locked) if resposta["como"] == "eco" else None

    hv.ponte.autoswitch_lock_set = _ponte_do_cadeado  # type: ignore[assignment]

    args = argparse.Namespace(
        oculta=True, segundos=0.0, passear=False, parada=900, foto="",
        abre="01-jogar.html", prova_no_aparelho=False, entre=2500,
        espera=1200, incluir_perigosos=False, prova_clique="", sem_cor=True,
        prova_de_mockup=False, voltas_por_aba=8, teto_de_mockup=-1,
        sem_cravado=False, sem_selo=False,
    )
    piloto = hv.Piloto(args)
    fora: dict[str, Any] = {"piscada_ms": da_piscada_ms}

    def ler(rotulo: str):
        def _leu(valor, erro):
            fora[rotulo] = (f"ERRO {erro}" if erro is not None
                            else json.loads(str(valor)))
        return _leu

    def anotar(rotulo: str):
        def _leu(valor, erro):
            fora[rotulo] = f"ERRO {erro}" if erro is not None else str(valor)
        return _leu

    def comeco() -> bool:
        # A PÁGINA TEM DE ESTAR PRONTA, e não "já deve ter carregado": sem o
        # bootstrap o `el.click()` acha a caixa sem ouvinte que responda — o
        # clique some, calado, e a régua fica verde sobre nada.
        if not piloto.pronto:
            return True
        piloto.ponte.perguntar(_LER_O_CADEADO, ler("antes"))
        piloto.ponte.perguntar(_CLICAR_NO_CADEADO, anotar("clique-1"))
        GLib.timeout_add(700, no_verde)
        return False

    def no_verde() -> bool:
        piloto.ponte.perguntar(_LER_O_CADEADO, ler("confirmou"))
        GLib.timeout_add(da_piscada_ms + 500, apagou)
        return False

    def apagou() -> bool:
        piloto.ponte.perguntar(_LER_O_CADEADO, ler("depois-da-piscada"))
        GLib.timeout_add(200, sem_resposta)
        return False

    def sem_resposta() -> bool:
        # O SERVIÇO PARADO: a ponte devolve `None`, e é o caminho que fazia a
        # tela piscar verde sobre uma escrita que não aconteceu.
        resposta["como"] = "none"
        piloto.ponte.perguntar(_CLICAR_NO_CADEADO, anotar("clique-2"))
        GLib.timeout_add(700, leu_sem_resposta)
        return False

    def leu_sem_resposta() -> bool:
        piloto.ponte.perguntar(_LER_O_CADEADO, ler("sem-resposta"))
        # O DEPÓSITO É LIDO AQUI, e não no fim — a chave é o `uniq`, e a caixa
        # não mora em coluna de controle nenhuma: as duas recusas pousam na
        # MESMA chave (a tarja de rodapé), e a terceira apagaria esta.
        fora["recados-sem-resposta"] = {
            k: [v[0], v[2]] for k, v in piloto._recados.items()}
        GLib.timeout_add(da_piscada_ms + 500, levanta)
        return False

    def levanta() -> bool:
        resposta["como"] = "levanta"
        piloto.ponte.perguntar(_CLICAR_NO_CADEADO, anotar("clique-3"))
        GLib.timeout_add(700, leu_o_levante)
        return False

    def leu_o_levante() -> bool:
        piloto.ponte.perguntar(_LER_O_CADEADO, ler("levantou"))
        GLib.timeout_add(400, fim)
        return False

    def fim() -> bool:
        fora["desfechos"] = {k: list(v) for k, v in piloto.desfechos.items()}
        fora["recados"] = {k: [v[0], v[2]] for k, v in piloto._recados.items()}
        Gtk.main_quit()
        return False

    GLib.timeout_add(400, lambda: piloto._ir(args.abre))
    GLib.timeout_add(1500, comeco)
    # O RELÓGIO DE SEGURANÇA É DESARMADO NO `finally`: um `timeout_add` pendente
    # depois da fixture dispara DENTRO do laço do PRÓXIMO teste de GUI do mesmo
    # processo. Já matou onze medições de um vizinho.
    guarda = GLib.timeout_add(60000, Gtk.main_quit)
    try:
        # O LAÇO REENTRA ATÉ O ROTEIRO ACABAR, e a condição é o ÚLTIMO passo: um
        # `Gtk.main_quit` pendente de outro teste de GUI do mesmo processo cai
        # dentro deste `Gtk.main()` e o encerra no meio.
        limite = _time.monotonic() + 60.0
        while "desfechos" not in fora and _time.monotonic() < limite:
            Gtk.main()
    finally:
        GLib.source_remove(guarda)
        piloto.pronto = False
        piloto.tela.janela.destroy()
        (hv.mesa_viva.estado_do_daemon,
         hv.ponte.autoswitch_lock_set) = guardado  # type: ignore[assignment]
    assert "desfechos" in fora, (
        f"o roteiro não chegou ao fim — o que voltou foi {sorted(fora)}. Quem "
        f"guarda os `desfechos` é o último passo, e esperar por qualquer outro "
        f"deixa a régua verde sobre uma medição pela metade")
    return fora


def test_o_verde_do_cadeado_no_webkit_e_do_servico(no_webkit: dict) -> None:
    """A piscada acende quando o serviço confirmou — e SÓ então.

    **As três metades, no mesmo DOM e no mesmo minuto:**

    ==========================  ==============================================
    a ponte responde            a caixa
    ==========================  ==============================================
    o estado que ficou valendo  pisca VERDE por `MS_DA_PISCADA` e volta sozinha
    `None` (serviço parado)     **não pisca** — e a frase vai para a tela
    levanta                     **não pisca**
    ==========================  ==============================================

    A MORDIDA QUE IMPORTA é a linha do meio, e ela é a que separa *o produto
    confirmou* de *a tela pintou sozinha*: arranque o `is None` do gesto e a
    caixa pisca verde no exato clique em que nada foi guardado — com o
    desmarcar chegando 100 ms depois, pelo tique.

    A COR VEM DO CSSOM: a classe diz que a regra foi escrita, o `outlineColor`
    diz que ela pegou.
    """
    assert no_webkit["clique-1"] == "cliquei", no_webkit["clique-1"]
    antes, certo = no_webkit["antes"], no_webkit["confirmou"]
    assert antes["achou"], "a caixa do cadeado não está na página que o piloto abriu"

    # A LINHA DE BASE: sem ela, uma caixa que já nascesse verde daria o mesmo
    # verde depois do clique.
    assert not antes["verde"], "a caixa já estava piscando ANTES do clique"

    assert certo["verde"], (
        "o serviço confirmou e a caixa não piscou — é o gesto desta aba cujo "
        "efeito não aparece em lugar nenhum da tela, e sem a piscada ele "
        "responde ao clique dela com nada")
    assert certo["contorno_larg"] != "0px", (
        f"a classe entrou e a folha não pegou: `outline-width` "
        f"{certo['contorno_larg']!r}. É a diferença entre a régua verde e o "
        f"olho dela vendo alguma coisa")

    # E ELA VOLTA SOZINHA. Um campo verde para sempre afirmaria um clique de dez
    # minutos atrás — a mesma doença do botão que fica em voo.
    assert not no_webkit["depois-da-piscada"]["verde"], (
        f"a piscada não apagou depois de {no_webkit['piscada_ms']} ms")


def test_o_cadeado_nao_pisca_sobre_o_que_nao_foi_guardado(no_webkit: dict) -> None:
    """O serviço não respondeu — e a tela NÃO pode dizer que guardou.

    **É a metade que esta sprint existe para fechar.** Até 06/09/2026 a resposta
    de `autoswitch_lock_set` ia para o lixo: com o serviço parado o gesto voltava
    calado, o piloto anotava `"aplicou"` e a caixa piscava VERDE — e desmarcava
    no tique seguinte, porque `_cadeado` sem `autoswitch_locked` devolve `""`. A
    tela dizia *guardei* e *não está guardado* com 100 ms entre as duas.

    A MORDIDA: devolva o corpo do gesto ao `p.autoswitch_lock_set(...)` sem
    guarda e esta régua reprova na primeira asserção.

    A SEGUNDA: embrulhe a chamada num `try/except` e a última asserção reprova —
    a ponte que LEVANTA passaria a pedir o verde do mesmo jeito.
    """
    assert no_webkit["clique-2"] == "cliquei", no_webkit["clique-2"]
    assert not no_webkit["sem-resposta"]["verde"], (
        "a caixa piscou VERDE com o serviço sem responder — o verde é o recibo "
        "de uma escrita que não aconteceu")

    # E A RECUSA FALA: `RuntimeError` é o contrato do piloto para *o produto
    # recusou, e a frase VAI PARA A TELA*.
    #
    # ONDE ELA POUSA, MEDIDO E NÃO SUPOSTO: no cartão do controle que a FITA
    # desta aba tem escolhido. A caixa não mora em coluna de controle nenhuma,
    # então o ouvinte cai no `window.__hef.alvoPadrao`, que a `01` preenche
    # (`hefesto_vivo`, `carga["alvo"]` — só as abas cuja fita ESCOLHE o fazem).
    # O depósito é lido NO INSTANTE desta etapa porque a chave é uma só: a
    # recusa seguinte escreveria por cima desta.
    frases = [v[0] for v in no_webkit["recados-sem-resposta"].values()]
    assert aba.CADEADO_RECUSA in frases, (
        f"a recusa não chegou à tela — o que está depositado é {frases}. Um "
        f"gesto que não pisca e não fala é o clique que some calado")

    assert no_webkit["clique-3"] == "cliquei", no_webkit["clique-3"]
    assert not no_webkit["levantou"]["verde"], (
        "a ponte levantou e a caixa piscou VERDE mesmo assim")
