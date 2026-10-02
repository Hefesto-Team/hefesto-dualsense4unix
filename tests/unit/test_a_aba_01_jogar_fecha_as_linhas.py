#!/usr/bin/env python3
"""As duas decisões da aba Jogar que a ONDA2-01 fecha, e a que ela NÃO fecha."""
from __future__ import annotations

import pathlib
import shutil
import sys
from typing import Any

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
INTERFACE = RAIZ / "src" / "hefesto_dualsense4unix" / "interface"

from tests.conftest import exigir_gi_real

exigir_gi_real("importa `interface.pacotes`, que carrega o GTK")

for _caminho in (str(RAIZ / "src"), str(INTERFACE)):
    if _caminho not in sys.path:
        sys.path.insert(0, _caminho)

import monta
from hefesto_dualsense4unix.interface import onde
from pacotes import TRAVESSAO, Contexto
from pacotes import a01_jogar as aba

VIVO: dict[str, Any] = {
    "connected": True,
    "native_mode": False,
    "gamepad_emulation": {"enabled": True, "flavor": "dualsense"},
    "paused": False,
}

P1 = "aa:bb:cc:00:00:01"
P2 = "aa:bb:cc:00:00:02"


def _pagina() -> str:
    """O HTML da BANCADA — o desenho de HOJE, nunca o publicado."""
    return onde.pagina("01-jogar.html").read_text()


def _ctx(controles: list[dict[str, Any]], **estado: Any) -> Contexto:
    return Contexto(state={**VIVO, **estado, "controllers": controles},
                    mesa=[], conectados=controles, estados={})


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
    """A D-04 dela venceu a minha recomendação, e ela vale."""
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
    """A classe e o texto em elementos SEPARADOS, e o de dentro é FOLHA."""
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


def test_o_cadeado_diz_o_que_o_daemon_guardou() -> None:
    """A trava mostra o estado do daemon, não o último clique."""
    assert aba._cadeado({**VIVO, "freestyle_ligado": True}) == aba.CADEADO_LIGADO
    assert (aba._cadeado({**VIVO, "freestyle_ligado": False})
            == aba.CADEADO_DESLIGADO)
    assert aba.CADEADO_LIGADO != aba.CADEADO_DESLIGADO, (
        "as duas palavras do interruptor ficaram iguais — a pílula não teria "
        "como dizer travado de destravado")


def test_sem_daemon_a_caixa_nao_afirma_uma_escolha_dela() -> None:
    """Sem estado, a trava fica no TRAVESSÃO — nem acesa, nem apagada."""
    assert aba._cadeado({}) == TRAVESSAO
    assert aba._cadeado({**VIVO}) == TRAVESSAO, "daemon sem a chave acendeu a trava"
    assert aba._cadeado({**VIVO, "freestyle_ligado": "sim"}) == TRAVESSAO, (
        "uma string ligou o cadeado — só o `True` literal pode")
    assert TRAVESSAO not in (aba.CADEADO_LIGADO, aba.CADEADO_DESLIGADO), (
        "o travessão virou uma das duas palavras do interruptor — o 'não sei' "
        "passaria a acender ou a apagar a pílula, que é a afirmação que ele "
        "existe para não fazer")


_ECOA = object()


class _PonteDeMentira:
    """Guarda o que foi chamado — e responde ao cadeado como o serviço responde."""

    def __init__(self, cadeado: Any = _ECOA) -> None:
        self.chamadas: list[tuple[str, tuple, dict]] = []
        self.cadeado = cadeado

    def freestyle_set(self, ligado: Any = None) -> Any:
        self.chamadas.append(("freestyle_set", (), {"ligado": ligado}))
        if isinstance(self.cadeado, BaseException):
            raise self.cadeado
        return bool(ligado) if self.cadeado is _ECOA else self.cadeado

    def __getattr__(self, nome: str):
        def registrar(*args, **kwargs):
            self.chamadas.append((nome, args, kwargs))
            return True
        return registrar


def test_o_cadeado_manda_o_valor_absoluto_e_nunca_um_toggle() -> None:
    """O clique manda a escolha DELA, não um "inverta o que você tiver"."""
    for guardado, pedido in ((False, True), (True, False)):
        p = _PonteDeMentira()
        aba.cadeado(_ctx([], freestyle_ligado=guardado),
                    {"evento": "click"}, p)
        assert p.chamadas, "o cadeado não chamou NADA"
        nome, _, kwargs = p.chamadas[0]
        assert nome == "freestyle_set", (
            f"o cadeado chamou {nome!r} — o escritor é o da janela antiga")
        assert kwargs.get("ligado") is pedido, (
            f"com o cadeado guardado em {guardado} o clique pediu "
            f"{kwargs.get('ligado')!r}, esperava {pedido!r}. `None` é TOGGLE, e "
            f"dois toggles num clique são um no-op")


def test_um_clique_grava_uma_vez_so_no_disco_dela() -> None:
    """O ouvinte do piloto está em dois eventos; só um pode virar escrita."""
    p = _PonteDeMentira()
    ctx = _ctx([], freestyle_ligado=False)
    aba.cadeado(ctx, {"evento": "change"}, p)
    assert p.chamadas == [], (
        "o `change` gravou: um gesto na trava grava DUAS vezes no disco dela se "
        "a caixa voltar, e o filtro é a única coisa entre ela e as duas")

    aba.cadeado(ctx, {"evento": "click"}, p)
    assert len(p.chamadas) == 1, (
        "o `click` NÃO gravou — e é o único evento que um `<button>` emite. O "
        "filtro ficou no `change`, e a trava virou enfeite")

    aba.cadeado(ctx, {}, p)
    assert len(p.chamadas) == 2, (
        "um clique sem `evento` foi engolido — o padrão tem de ser `click`")


def test_o_cadeado_confirma_em_verde() -> None:
    """O gesto PEDE o verde voltando calado — e só quando o serviço confirmou."""
    p = _PonteDeMentira()
    assert aba.cadeado(_ctx([], freestyle_ligado=False),
                       {"evento": "click"}, p) is None
    assert p.chamadas, "o cadeado não chamou NADA"

    p = _PonteDeMentira(cadeado=None)
    with pytest.raises(RuntimeError) as caiu:
        aba.cadeado(_ctx([], freestyle_ligado=False), {"evento": "click"}, p)
    assert str(caiu.value) == aba.CADEADO_RECUSA, (
        f"a recusa disse {str(caiu.value)!r} — a frase é a da janela antiga, e "
        f"texto de tela novo é palavra dela")
    assert p.chamadas, "o gesto recusou sem sequer tentar escrever"

    p = _PonteDeMentira(cadeado=RuntimeError("o socket recusou"))
    with pytest.raises(RuntimeError):
        aba.cadeado(_ctx([], freestyle_ligado=True), {"evento": "click"}, p)


def test_a_palavra_do_cadeado_e_a_que_ela_ja_leu() -> None:
    """O rótulo e a dica são da janela antiga, palavra por palavra."""
    import re

    fonte = (RAIZ / "src/hefesto_dualsense4unix/app/actions/home_actions.py"
             ).read_text()
    colado = re.sub(r'"\s*\n\s*"', "", fonte)

    assert f'label="{aba.CADEADO_ROTULO}"' in colado, (
        f"o rótulo {aba.CADEADO_ROTULO!r} não é o do `Gtk.CheckButton` da "
        f"janela antiga — texto de tela novo é decisão DELA, e este devia ser "
        f"texto que ela já leu")
    assert aba.CADEADO_DICA in colado, (
        "a dica do cadeado se afastou da da janela antiga. As duas dizem a "
        "mesma coisa para a mesma pessoa; duas versões vivas é o defeito que a "
        "regra do fato-errado existe para matar")
    assert aba.CADEADO_RECUSA in colado, (
        f"a recusa do cadeado ({aba.CADEADO_RECUSA!r}) não é a frase que a "
        f"janela antiga põe na tela quando o `freestyle_set` volta "
        f"`None`. Texto de tela NOVO é decisão dela (PROVA-DE-TELA-01); esta "
        f"linha existe para que a tela nova não invente uma segunda maneira de "
        f"dizer o mesmo desfecho")


def test_o_cadeado_esta_na_pagina_com_os_dois_lados() -> None:
    """Endereço de pintura E endereço de clique — um sem o outro é meio botão."""
    doc = _pagina()

    assert doc.count('data-campo="cadeado" data-hef-alvo="classe"') == 1
    assert doc.count('data-hef-classe="ligada" '
                     f'data-hef-quando="{aba.CADEADO_LIGADO}"') == 1, (
        "a pílula da trava perdeu a classe ou a palavra que a acende. Sem a "
        "classe o piloto acende `on`, que folha nenhuma pinta; sem o `quando` o "
        "alvo `classe` vira BOOLEANO e a trava acende também no DESLIGADO e no "
        "travessão")
    assert doc.count('data-gesto="cadeado"') == 1
    assert aba.CADEADO_ROTULO in doc, "o rótulo do cadeado não está na tela"
    assert aba.CADEADO_DICA in doc, "o cadeado está sem a razão na dica"


def test_o_cadeado_esta_publicado() -> None:
    """A caixa está na página que o PRODUTO abre — medido no arquivo, não na prosa."""
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
    duas. Uma trava aninhada dentro de uma delas sumiria na outra posição — e
    sumiria em SILÊNCIO: nenhuma contagem de `data-campo` vê isso, porque o
    endereço continua no arquivo.

    **É a diferença entre a ordem no arquivo e o aninhamento no DOM**, e só o
    navegador responde por ela: a régua pergunta ao `getComputedStyle` nas DUAS
    posições do interruptor.

    **O SELETOR PERDEU A TAG EM 19/09** (`TRAVA-PILULA-01`): ele dizia
    `label.cadeado`, e a trava virou `<button class="cadeado">`. Um seletor com
    a tag velha casa ZERO elemento, e a régua passou a reprovar pela guarda de
    vácuo logo abaixo — que é exatamente o que ela existe para fazer. A classe
    é o endereço; a tag, não.

    A MORDIDA: mova o `<button class="cadeado">` para dentro do
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
            const c = document.querySelector('.cadeado');
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
    assert medido["ligado"]["ligado"] and not medido["ligado"]["desligado"], (
        "o interruptor não trocou as seções — a régua está medindo o próprio "
        "instrumento")
    assert medido["desligado"]["desligado"] and not medido["desligado"]["ligado"]

    assert medido["ligado"]["cadeado"], "o cadeado sumiu com o Hefesto LIGADO"
    assert medido["desligado"]["cadeado"], (
        "o cadeado sumiu com o Hefesto DESLIGADO — ele foi aninhado dentro de "
        "uma seção do interruptor, e a troca automática de perfil vale nos dois")

    assert medido["cor"]["antes"] == medido["cor"]["p1"], (
        "os dois cartões já nascem com cores diferentes — a régua está medindo "
        "outra coisa")
    assert medido["cor"]["depois"] != medido["cor"]["antes"], (
        f"o número do jogador ficou na mesma cor com a classe `espera` acesa "
        f"({medido['cor']['depois']}) — a classe pinta e a folha não responde")
    assert medido["cor"]["texto"] == "Player 2", (
        f"a pintura trocou a PALAVRA para {medido['cor']['texto']!r}. A D-04 "
        f"dela é 'Player N, como está hoje' — o esmaecido só muda a cor")


def test_o_aviso_do_nativo_continua_fora_por_decisao_dela() -> None:
    """A decisão [01] pede uma frase que ELA MANDOU TIRAR — e ela ganha."""
    from hefesto_dualsense4unix.app.actions import home_actions

    nativo = home_actions._MODE_DESCRIPTIONS["native"]
    assert nativo == (
        "Modo Nativo: o Hefesto sai do meio e o jogo fala direto com o "
        "controle."), (
        f"a descrição do Modo Nativo na janela antiga divergiu da interface "
        f"nova ({nativo!r}). Desde 06/09 as duas dizem a MESMA coisa, que é a "
        f"regra de 31/08 dela: 'Desligado põe o Nativo online', e nada além")

    ctx = _ctx([], native_mode=True,
               gamepad_emulation={"enabled": False, "flavor": "dualsense"})
    textos = [str(a.get("texto") or "") for a in aba._avisos(ctx)]
    assert not any("derrubam o controle" in t for t in textos), (
        "o aviso do Modo Nativo entrou na coluna Atenção. Ela mandou tirá-lo "
        "desta aba em 31/08 — 'qualquer coisa fora isso tá incorreta' — e "
        "ensaio nenhum desta casa mede quantos jogos derrubam o controle. "
        "Se a decisão mudou, ela muda com o olho DELA, não por baixo do gerador")


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

    fora = aba.pacote(_ctx([c1, c2]))
    for uniq, campos in (fora["cartoes"] or {}).items():
        assert "alvo" not in campos, (
            f"o cartão {uniq} passou a emitir `alvo` — o alvo de edição da fita "
            "é escolha dela, escrita pelo piloto, e não fato do serviço")


def test_so_o_true_literal_acende_o_marcador() -> None:
    """Chave ausente não é "não é o primário" — é *não sei*, e não se afirma."""
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


def test_o_servico_calado_diz_e_para_de_afirmar() -> None:
    """Passo 5 — com o estado vazio a coluna DIZ, e nada mais é afirmado."""
    ctx = Contexto(state={}, mesa=[], conectados=[], estados={})
    canal = aba._avisos(ctx)
    fora = aba.pacote(ctx)

    selos = [a["selo"] for a in canal]
    assert aba.SELO_DO_SERVICO in selos, (
        "o canal ficou calado com o serviço calado — a tela afirmando sobre um "
        "estado que ninguém leu")
    assert canal[selos.index(aba.SELO_DO_SERVICO)]["texto"] == aba.SERVICO_CALADO

    assert fora["hef-posicao"] == "", "o interruptor acendeu sem estado"
    assert fora["modo-aceso"] == "", "um chip da fileira acendeu sem estado"
    assert fora["cadeado"] == TRAVESSAO, "o cadeado afirmou uma escolha dela"
    assert fora["mesa-frase"] == "", (
        "a frase da mesa vazia apareceu — 'nenhum controle na mesa' sobre um "
        "tique sem resposta é a tela afirmando o que não leu")
    assert not fora["cartoes"], "um cartão foi afirmado sem estado"


def test_com_o_servico_vivo_a_linha_do_servico_nao_existe() -> None:
    """E ela SOME sozinha quando o serviço volta — sem clique nenhum."""
    c1 = {"uniq": P1, "connected": True, "player_slot": 1, "player": 1,
          "is_primary": True, "transport": "usb"}
    fora = aba._avisos(_ctx([c1]))
    assert aba.SELO_DO_SERVICO not in [a["selo"] for a in fora], (
        "a linha do serviço calado continuou na coluna com o daemon vivo")


def test_o_selo_do_servico_abre_a_escada_da_gravidade() -> None:
    """Com o serviço calado, TODA outra linha descreveria o que ninguém leu."""
    assert aba.ORDEM_DA_GRAVIDADE[0] == aba.SELO_DO_SERVICO, (
        "o selo do serviço saiu da frente da escada")
    selos = [a["selo"] for a in aba._em_ordem([
        {"selo": "PERFIL", "texto": "a"}, {"selo": "PAUSA", "texto": "b"},
        {"selo": aba.SELO_DO_SERVICO, "texto": "c"},
    ])]
    assert selos[0] == aba.SELO_DO_SERVICO, f"o canal ordenou {selos!r}"


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
    """As palavras proibidas do glossário não entram em texto de tela."""
    from hefesto_dualsense4unix.app.actions import home_actions

    de_maquina = ("uinput", "hidraw", "vpad", "evdev", "uniq")
    minhas = [aba.SERVICO_CALADO, aba.SERVICO_DESLIGADO, aba.PRIMARIO_DICA,
              aba.MARCA_DO_PRIMARIO]
    #: O MARKUP FICA, e não é descuido: quem o tira é `interface.sistema.sem_markup`,
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

    for frase in minhas:
        assert " mesa " not in f" {frase.lower()} ", (
            f'a palavra "mesa" entrou numa frase desta aba: {frase!r}. Decisão '
            f"dela, 06/09: o termo sai da tela e entra o simples")


def _daemon_que_grava(ativo: str | None) -> Any:
    """O escritor REAL do daemon, sobre um objeto que só sabe o perfil ativo.

    `Daemon.gravar_o_modo_escolhido` lê do daemon só o `store.active_profile`;
    o resto (o perfil que recebe e a regra da seção) é do dono, em
    `profiles.manager`. Subir um `Daemon` inteiro aqui mediria o co-op e o
    vpad, e esta régua mede o CAMINHO da escolha até a outra tela.
    """
    from types import SimpleNamespace

    return SimpleNamespace(store=SimpleNamespace(active_profile=ativo))


def test_o_modo_clicado_entra_no_perfil_ativo(tmp_path, monkeypatch) -> None:
    """Passo 1 — o caminho clicado na 01 é o que a aba 10 lê. UM dono, duas telas.

    Linha 5 do CSV: *"nada. `_ESCOLHA`/`_ROTULO` são dicionários de módulo lidos
    só dentro do próprio arquivo"*, e a consequência: *"ela escolhe 'Xbox' na 01,
    clica em 'Salvar Perfil' na 10, e o perfil grava a máscara que estava no
    disco — a escolha dela não entra."*

    **QUEM GRAVA É O DAEMON** desde a O-MODO-SE-GRAVA-ONDE-ELE-MUDA-01
    (29/09/2026): a janela gravava depois da resposta, e com quatro controles a
    troca passava do teto dela. As duas metades da estrada, medidas aqui:

    1. o chip «Xbox» pede o caminho à porta que grava — `gamepad.emulation.set`
       com `origin: "manual"`, que o handler traduz em `grava_o_modo="ipc"`;
    2. o escritor do daemon, `Daemon.gravar_o_modo_escolhido`, põe o caminho na
       seção `mode` do perfil ativo, e a aba 10 o LÊ por
       `perfis_web._pacote_do_editor`, que é o que o quadro «Modo» daquela aba
       mostrava. Ler o `.json` direto provaria só que alguém gravou um arquivo;
       ler por aqui prova que **a outra tela vê**.

    A MORDIDA: tire o `origin: "manual"` do passo `gamepad.emulation.set` do
    plano (`mode_transition.plan_mode_transition`) e a primeira metade
    reprova; faça o escritor do daemon gravar em outro perfil
    (`nome_do_perfil_que_grava(None)`) e a segunda reprova, com a aba 10 sem
    modo. A régua 1 de `test_o_modo_se_grava_onde_ele_muda.py` mede o setter
    chamando o escritor depois do aparelho.
    """
    from hefesto_dualsense4unix.app.actions import perfis_web
    from hefesto_dualsense4unix.daemon.lifecycle import Daemon
    from hefesto_dualsense4unix.profiles import loader
    from hefesto_dualsense4unix.profiles.schema import MatchAny, Profile

    monkeypatch.setattr("hefesto_dualsense4unix.utils.xdg_paths.profiles_dir",
                        lambda: tmp_path)
    monkeypatch.setattr(loader, "_profiles_dir", lambda: tmp_path, raising=False)
    nome = "Régua do Modo"
    loader.save_profile(Profile(name=nome, match=MatchAny(), priority=40),
                        origem="régua")
    assert perfis_web._pacote_do_editor(loader.load_profile(nome))["modo"] == (
        perfis_web.MODO_SEM_OPINIAO), "o perfil da régua já nasceu com modo"

    passos = dict(aba._plano_do_chip("xbox"))
    pedido = passos.get("gamepad.emulation.set")
    assert pedido == {"enabled": True, "origin": "manual", "caminho": "xbox"}, (
        f"o chip «Xbox» não pede o caminho à porta que grava: {passos}")

    Daemon.gravar_o_modo_escolhido(
        _daemon_que_grava(nome), "gamepad", caminho="xbox", porta="ipc")

    lido = perfis_web._pacote_do_editor(loader.load_profile(nome))["modo"]
    assert lido == "gamepad", (
        f"a aba 10 continua vendo {lido!r} depois de o daemon gravar o «Xbox» — "
        f"a escolha dela não atravessou as duas telas")
    modo = loader.load_profile(nome).mode
    assert modo is not None and modo.caminho == "xbox", (
        f"o caminho não entrou na seção `mode`: {modo!r}")
    assert modo.gamepad_flavor is None, (
        f"o escritor do modo escreveu a máscara do perfil: {modo!r}")


def test_a_escrita_no_perfil_nunca_levanta(monkeypatch) -> None:
    """Ela vem DEPOIS de o aparelho trocar — e não pode falhar.

    Uma exceção aqui transformaria uma troca de modo bem-sucedida em recusa:
    o setter do daemon devolveria erro sobre um vpad que já trocou.

    A MORDIDA: tire o `try` de `Daemon.gravar_o_modo_escolhido` e esta régua
    reprova com o `OSError` do dublê.
    """
    from hefesto_dualsense4unix.daemon.lifecycle import Daemon
    from hefesto_dualsense4unix.profiles import manager

    def _explode(*_a: Any, **_kw: Any) -> Any:
        raise OSError("o disco recusou")

    monkeypatch.setattr(manager, "gravar_o_modo_no_perfil_ativo", _explode)
    assert Daemon.gravar_o_modo_escolhido(
        _daemon_que_grava("Qualquer"), "gamepad", caminho="xbox", porta="ipc"
    ) is None, (
        "a gravação levantou — o setter devolveria recusa sobre um modo que o "
        "aparelho já aplicou")


def test_sem_perfil_ativo_nao_se_inventa_um() -> None:
    """Sem perfil valendo, não há onde gravar — e não se escolhe um.

    Sem o nome no daemon e sem o perfil do boot no disco, o dono
    (`manager.nome_do_perfil_que_grava`) responde `None`, e nenhum `.json`
    muda nem nasce.

    O FREESTYLE ESTÁ NO DISCO DE PROPÓSITO: é o nome padrão que um escritor
    que «cai num nome» escolheria. A régua lê a pasta que o `loader` usa (a do
    lar de mentira do conftest), e não uma pasta que nenhum escritor alcança.
    Até 29/09 ela olhava um `tmp_path` que o `loader` nunca via (ele importa
    `profiles_dir` por nome, e o desvio no módulo de origem não o alcança), e
    passava com o escritor gravando no Freestyle.

    A MORDIDA: faça `Daemon.gravar_o_modo_escolhido` cair num nome padrão
    (`nome_do_perfil_que_grava(...) or "Freestyle"`) e esta régua reprova com
    o Freestyle regravado.
    """
    import hashlib

    from hefesto_dualsense4unix.daemon.lifecycle import Daemon
    from hefesto_dualsense4unix.profiles import loader
    from hefesto_dualsense4unix.profiles.schema import MatchAny, Profile
    from hefesto_dualsense4unix.utils.session import resolve_boot_profile

    loader.save_profile(Profile(name=loader.NOME_DO_PADRAO, match=MatchAny()),
                        origem="régua")
    assert resolve_boot_profile() is None, "premissa: nenhum perfil do boot no disco"
    pasta = loader.profiles_dir()

    def _retrato() -> dict[str, str]:
        return {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                for p in sorted(pasta.glob("*.json"))}

    antes = _retrato()
    assert antes, "premissa: o Freestyle da régua está na pasta que o loader lê"
    assert Daemon.gravar_o_modo_escolhido(
        _daemon_que_grava(None), "gamepad", caminho="xbox", porta="ipc"
    ) is None
    assert _retrato() == antes, (
        "o escritor escolheu um perfil para receber o modo sem ninguém valendo")


def test_a_secao_do_modo_e_a_regra_do_dono() -> None:
    """A máscara não é do modo, e não é inventada fora dele."""
    from hefesto_dualsense4unix.profiles.manager import secao_do_modo_com_o_caminho
    from hefesto_dualsense4unix.profiles.schema import ProfileModeConfig

    antes = ProfileModeConfig(kind="gamepad", gamepad_flavor="xbox")
    fora = secao_do_modo_com_o_caminho(antes, kind="native")
    assert fora.kind == "native" and fora.gamepad_flavor == "xbox", (
        "o modo apagou a máscara padrão do perfil — a máscara não é do modo")

    fica = secao_do_modo_com_o_caminho(antes, kind="gamepad")
    assert fica.gamepad_flavor == "xbox", (
        "a máscara do disco foi apagada por um clique que não a escolheu — é a "
        "cicatriz do `or \"xbox\"` pelo avesso")
    do_zero = secao_do_modo_com_o_caminho(None, kind="gamepad", caminho="xbox")
    assert do_zero.gamepad_flavor is None, (
        "a regra inventou uma máscara — `None` quer dizer «mantém a atual»")


def _painel_do_produto() -> Any:
    from hefesto_dualsense4unix.app.actions.jogar import painel

    return painel


_ESTADO_DO_WEBKIT: dict[str, Any] = {
    "active_profile": "regua",
    "gamepad_emulation": {"flavor": "dualsense"},
    "freestyle_ligado": False,
    "controllers": [
        {"uniq": P1, "connected": True, "transport": "usb", "player": 1},
        {"uniq": P2, "connected": True, "transport": "bt", "player": 2},
    ],
}

_LER_O_CADEADO = r"""
(function(){
  const c = document.querySelector('[data-gesto="cadeado"]');
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

_CLICAR_NO_CADEADO = r"""
(function(){
  const c = document.querySelector('[data-gesto="cadeado"]');
  if(!c) return 'NAO ACHEI O CADEADO NA PAGINA PUBLICADA';
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

    guardado = (hv.mesa_viva.estado_do_daemon, hv.ponte.freestyle_set)
    da_piscada_ms = int(hv.MS_DA_PISCADA)
    hv.mesa_viva.estado_do_daemon = (  # type: ignore[assignment]
        lambda *a, **k: _ESTADO_DO_WEBKIT)

    resposta: dict[str, Any] = {"como": "eco"}

    def _ponte_do_cadeado(ligado: Any = None) -> Any:
        if resposta["como"] == "levanta":
            raise RuntimeError("o socket recusou o freestyle.set")
        return bool(ligado) if resposta["como"] == "eco" else None

    hv.ponte.freestyle_set = _ponte_do_cadeado  # type: ignore[assignment]

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
        resposta["como"] = "none"
        piloto.ponte.perguntar(_CLICAR_NO_CADEADO, anotar("clique-2"))
        GLib.timeout_add(700, leu_sem_resposta)
        return False

    def leu_sem_resposta() -> bool:
        piloto.ponte.perguntar(_LER_O_CADEADO, ler("sem-resposta"))
        fora["desfecho-sem-resposta"] = list(
            piloto.desfechos.get("01-jogar.html:cadeado", ()))
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
        Gtk.main_quit()
        return False

    GLib.timeout_add(400, lambda: piloto._ir(args.abre))
    GLib.timeout_add(1500, comeco)
    guarda = GLib.timeout_add(60000, Gtk.main_quit)
    try:
        limite = _time.monotonic() + 60.0
        while "desfechos" not in fora and _time.monotonic() < limite:
            Gtk.main()
    finally:
        GLib.source_remove(guarda)
        piloto.pronto = False
        piloto.tela.janela.destroy()
        (hv.mesa_viva.estado_do_daemon,
         hv.ponte.freestyle_set) = guardado  # type: ignore[assignment]
    assert "desfechos" in fora, (
        f"o roteiro não chegou ao fim — o que voltou foi {sorted(fora)}. Quem "
        f"guarda os `desfechos` é o último passo, e esperar por qualquer outro "
        f"deixa a régua verde sobre uma medição pela metade")
    return fora


def test_o_verde_do_cadeado_no_webkit_e_do_servico(no_webkit: dict) -> None:
    """A piscada acende quando o serviço confirmou — e SÓ então."""
    assert no_webkit["clique-1"] == "cliquei", no_webkit["clique-1"]
    antes, certo = no_webkit["antes"], no_webkit["confirmou"]
    assert antes["achou"], "a caixa do cadeado não está na página que o piloto abriu"

    assert not antes["verde"], "a caixa já estava piscando ANTES do clique"

    assert certo["verde"], (
        "o serviço confirmou e a caixa não piscou — é o gesto desta aba cujo "
        "efeito não aparece em lugar nenhum da tela, e sem a piscada ele "
        "responde ao clique dela com nada")
    assert certo["contorno_larg"] != "0px", (
        f"a classe entrou e a folha não pegou: `outline-width` "
        f"{certo['contorno_larg']!r}. É a diferença entre a régua verde e o "
        f"olho dela vendo alguma coisa")

    assert not no_webkit["depois-da-piscada"]["verde"], (
        f"a piscada não apagou depois de {no_webkit['piscada_ms']} ms")


def test_o_cadeado_nao_pisca_sobre_o_que_nao_foi_guardado(no_webkit: dict) -> None:
    """O serviço não respondeu — e a tela NÃO pode dizer que guardou."""
    assert no_webkit["clique-2"] == "cliquei", no_webkit["clique-2"]
    assert not no_webkit["sem-resposta"]["verde"], (
        "a caixa piscou VERDE com o serviço sem responder — o verde é o recibo "
        "de uma escrita que não aconteceu")

    classe, frase = no_webkit["desfecho-sem-resposta"]
    assert classe == "recusou dizendo" and aba.CADEADO_RECUSA in frase, (
        f"o gesto não recusou com a frase do dono — o desfecho foi "
        f"{classe!r}: {frase!r}. Um gesto que não pisca e não diz nada ao "
        f"diário é o clique que some calado")

    assert no_webkit["clique-3"] == "cliquei", no_webkit["clique-3"]
    assert not no_webkit["levantou"]["verde"], (
        "a ponte levantou e a caixa piscou VERDE mesmo assim")
