#!/usr/bin/env python3
"""A RÉGUA DA PARIDADE DA ABA 07 — o que a GTK faz VIVO e o HTML jogava fora.

POR QUE ELA NASCEU, e o número é de 03/09/2026: das 30 features medidas na área
de lançadores, **13 faltavam no HTML** e o padrão era um só nas dez abas — *o
que tem GESTO migrou; o que é LEITURA AO VIVO não*. Esta régua cobra as quatro
que esta frente fechou, e cada uma delas é PONTE: a função já existia na GTK e
a interface nova não a chamava.

    o que a GTK faz                         quem responde agora no HTML
    -------------------------------------   ----------------------------------
    banner "o jogo aberto não passou pelo    `aviso_do_jogo_aberto`, sobre
    wrapper", sem clique (2 abas)            `home_actions.wrapper_banner_text`
    "Não perguntar para este jogo" e         SAÍRAM em 21/09/2026, com os outros
    fechar a Steam por ~20 s                 botões que só a Steam tinha — o
                                             reparo é do vigia; o «Voltar a
                                             perguntar» desfaz o que já foi dito
    a escada de TRÊS evidências do jogo      `a_escada_do_jogo`, sobre
    (inclusive o jogo JÁ FECHADO)            `launch_env` + a wm_class do estado

O QUE CADA TESTE VIGIA, e a MORDIDA de cada um está na docstring dele. As três
que mais importam:

* troque `ha.wrapper_banner_text(state)` por um teste próprio de `wrapper_used`
  e o `test_o_aviso_e_a_decisao_da_gtk_e_nao_uma_copia` reprova — é a forma de
  defeito que esta casa persegue: a segunda cópia de uma regra que já tem dono;
* apague o `remove_dismissed_appid` do `voltar-a-perguntar` e o
  `test_voltar_a_perguntar_tira_do_arquivo_de_verdade` reprova;
* devolva `steam_game_running_appid()` para o `detectar` e o
  `test_a_escada_alcanca_o_jogo_que_ela_ja_fechou` reprova.

NADA AQUI TOCA A MÁQUINA DELA. O `conftest.py` desta casa desvia `HOME` e os
quatro `XDG_*`; o que escreve em disco escreve no lar de mentira, e o que
abriria a Steam é dublado — mexer na Steam de quem roda a suíte seria o
instrumento brigando com o produto, que é a armadilha 3 desta casa.
"""
from __future__ import annotations

import pathlib
import sys
from typing import Any

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
INTERFACE = RAIZ / "src" / "hefesto_dualsense4unix" / "interface"
sys.path.insert(0, str(INTERFACE))

PAGINA = "07-lancadores.html"

#: O `state_full` que o daemon publica quando HÁ jogo aberto e ele **não**
#: passou pelo wrapper. É o único payload que acende o aviso — ver
#: `home_actions.wrapper_banner_text`, que só reage ao `False` LITERAL.
SEM_WRAPPER: dict[str, Any] = {
    "gamepad_emulation": {"enabled": True, "wrapper_used": False},
    "window_detect_last_class": "steam_app_3357650",
}


@pytest.fixture(scope="module")
def a07():
    """O módulo que os GESTOS REGISTRADOS habitam — e não outro com o mesmo nome.

    A ARMADILHA, e ela custou três reprovações desta régua: esta casa alcança o
    pacote por DOIS caminhos — `hefesto_dualsense4unix.interface.pacotes.
    a07_lancadores` e `pacotes.a07_lancadores`, este pelo `sys.path.insert` que
    o `pacotes/__init__.py` faz. **São dois objetos de módulo**, com dois jogos
    de estado de módulo: um `monkeypatch.setattr` num deles não é visto pelo
    gesto que vive no outro, e o teste reprova falando de uma cura que existe.

    Perguntar ao registro em vez de importar por um nome fecha a porta: o
    módulo que sai daqui é, por construção, o mesmo que o piloto chama.
    """
    import pacotes

    fn = pacotes.gesto_da_pagina(PAGINA, "procurar")
    assert fn is not None, f"{PAGINA}:procurar não tem dono — a régua ficaria cega"
    return sys.modules[fn.__module__]


@pytest.fixture(scope="module")
def desenho():
    from hefesto_dualsense4unix.interface import desenho_dos_lancadores as dl

    return dl


def _ctx(state: dict[str, Any] | None = None):
    import pacotes

    return pacotes.Contexto(state=state or {}, mesa=[], conectados=[], estados={})


def _gesto(nome: str):
    import pacotes

    fn = pacotes.gesto_da_pagina(PAGINA, nome)
    assert fn is not None, f"{PAGINA}:{nome} não tem dono"
    return fn


def _cartao_da_steam(a07, desenho, lida, state):
    """O cartão da Steam depois do que só o produto vivo sabe acrescentar."""
    return a07.com_o_que_o_daemon_diz(desenho.cartoes(lida), state, lida)[0]


# --------------------------------------------------------------------------
# 1. o aviso vivo — a chave que o daemon publicava e a interface jogava fora
# --------------------------------------------------------------------------
def test_o_aviso_e_a_decisao_da_gtk_e_nao_uma_copia(a07, monkeypatch):
    """Quem decide é `home_actions.wrapper_banner_text`. Ponto.

    A MORDIDA: escreva aqui um `state["gamepad_emulation"]["wrapper_used"] is
    False` em vez de chamar a função da GTK e este teste passa a reprovar —
    porque ele DUBLA a função e exige que o aviso siga o dublê. Uma cópia da
    regra sobreviveria a este teste só enquanto as duas concordassem, que é
    exatamente o dia em que a cópia deixa de importar.
    """
    from hefesto_dualsense4unix.app.actions import home_actions as ha

    # O QUE ESTA RÉGUA CASA MUDOU EM 13/09/2026 — TELA-CALADA-02. O cartão
    # deixou de escrever a frase do dono e escreve um rótulo de estado
    # (`a07.JOGO_ABERTO_SEM_O_ATALHO`); por isso o dublê já não aparece no
    # texto. O que a régua cobra continua: quem decide SE acende é o dono — o
    # dublê que diz "não" apaga o aviso num `state` que o acenderia.
    monkeypatch.setattr(ha, "wrapper_banner_text", lambda s: "FRASE DA GTK")
    html, _ = a07.aviso_do_jogo_aberto({}, None)
    assert a07.JOGO_ABERTO_SEM_O_ATALHO in html, (
        "o aviso não veio de `home_actions.wrapper_banner_text` — o pacote "
        "está decidindo por conta própria se o jogo passou pelo wrapper")
    monkeypatch.setattr(ha, "wrapper_banner_text", lambda s: "")
    assert a07.aviso_do_jogo_aberto(SEM_WRAPPER, None) == ("", ""), (
        "o dono disse que não há aviso e o pacote acendeu assim mesmo")


def test_o_aviso_usa_o_texto_dela_sem_redigitar(a07):
    """O cartão escreve o RÓTULO de estado, e não uma segunda redação da frase.

    **O CONTRATO MUDOU EM 13/09/2026 — TELA-CALADA-02.** Até aqui esta régua
    exigia o `WRAPPER_MISSING_TEXT` da GTK, palavra por palavra, dentro do
    cartão. A palavra dela sobre as frases de status é *"em todas as abas da
    interface"*: a frase saiu, e o cartão diz `a07.JOGO_ABERTO_SEM_O_ATALHO`.
    O que sobra da decisão 14 (*"uma frase, um dono"*) é a outra metade: a aba
    não redige a frase do dono — nem inteira, nem um pedaço dela.

    A MORDIDA: devolva `_texto(texto)` ao retorno de `aviso_do_jogo_aberto` e
    este teste reprova.
    """
    from hefesto_dualsense4unix.app.actions import home_actions as ha

    html, _ = a07.aviso_do_jogo_aberto(SEM_WRAPPER, None)
    assert ha.WRAPPER_MISSING_TEXT not in html
    assert a07.JOGO_ABERTO_SEM_O_ATALHO in html


def test_sem_jogo_aberto_o_aviso_nao_acende(a07):
    """`None`/ausente NUNCA acende — nada de alarme falso por payload incompleto."""
    for state in (None, {}, {"gamepad_emulation": {}},
                  {"gamepad_emulation": {"wrapper_used": None}},
                  {"gamepad_emulation": {"wrapper_used": True}}):
        html, appid = a07.aviso_do_jogo_aberto(state, None)
        assert (html, appid) == ("", ""), f"acendeu com {state!r}"


def test_o_aviso_respeita_a_dispensa_dela(a07, desenho):
    """Se ela mandou não perguntar, o aviso não volta para aquele jogo.

    É a metade que faz o par existir: sem isto o botão "Não perguntar para este
    jogo" gravaria no disco e a tela continuaria igual — o botão que aceita o
    clique e não faz nada.

    A MORDIDA: apague o `if appid ... in lida.dispensados` e este teste reprova.
    """
    lida = desenho.Leitura(dispensados=(("3357650", "Um jogo"),))
    html, appid = a07.aviso_do_jogo_aberto(SEM_WRAPPER, lida)
    assert (html, appid) == ("", ""), (
        "o aviso voltou para um jogo que ela dispensou — o clique dela não "
        "produziu efeito nenhum na tela")
    # e continua acendendo para OUTRO jogo, senão a dispensa seria global
    outro = desenho.Leitura(dispensados=(("999", "Outro"),))
    assert a07.aviso_do_jogo_aberto(SEM_WRAPPER, outro)[0], (
        "a dispensa de um jogo calou o aviso de todos os outros")


def test_o_aviso_chega_ao_cartao(a07, desenho):
    """O que a função devolve tem de APARECER no cartão que a tela recebe.

    Sem esta régua o aviso poderia estar certo, ter teste unitário e **nunca
    chegar à tela** — que é o defeito que a `test_os_botoes_que_a_pintura_traz`
    da régua irmã existe para pegar, aqui aplicado ao corpo do cartão.

    O BOTÃO DE DISPENSAR SAIU EM 21/09/2026 com os outros que só a Steam tinha
    (*"a ideia é termos os mesmos botões pra todos os lançadores. sempre."*).
    """
    from hefesto_dualsense4unix.app.actions import home_actions as ha

    steam = _cartao_da_steam(a07, desenho, desenho.Leitura(com_wrapper=("1",)),
                             SEM_WRAPPER)
    # O QUE CHEGA AO CARTÃO É O RÓTULO — TELA-CALADA-02, 13/09/2026: a frase
    # longa do dono saiu do corpo, e o estado ficou.
    assert a07.JOGO_ABERTO_SEM_O_ATALHO in steam.diz
    assert ha.WRAPPER_MISSING_TEXT not in steam.diz
    assert 'data-gesto="nao-perguntar"' not in desenho.acoes_html(steam), (
        "o «Não perguntar» voltou ao cartão — um botão que os outros sete não têm")


def test_sem_appid_o_aviso_fica_e_o_botao_some(a07, desenho):
    """O daemon afirmou que HÁ jogo sem o wrapper; calar seria pior.

    Quando a `window_detect_last_class` ainda não casou, o produto sabe que há
    um jogo aberto sem o atalho e **não sabe qual**. O aviso é verdadeiro e
    fica; o que some é o botão, que sem appid não teria sobre o que agir.
    """
    state = {"gamepad_emulation": {"wrapper_used": False},
             "window_detect_last_class": "Hefesto-Dualsense4Unix"}
    html, appid = a07.aviso_do_jogo_aberto(state, None)
    assert html and appid == ""
    steam = _cartao_da_steam(a07, desenho, desenho.Leitura(com_wrapper=("1",)),
                             state)
    assert 'data-gesto="nao-perguntar"' not in desenho.acoes_html(steam)


def test_a_pintura_do_aviso_nao_toca_o_disco(a07, monkeypatch):
    """O aviso roda no TIQUE — 2 Hz. Disco ali é o defeito que a vigia cura.

    A MORDIDA: troque a segunda evidência por `launch_session_appid()` ou por
    `slo.rotulo_do_jogo(appid)` dentro do aviso e este teste reprova.
    """
    from hefesto_dualsense4unix.daemon import launch_env
    from hefesto_dualsense4unix.integrations import steam_launch_options as slo

    def _nunca(*a: Any, **kw: Any) -> Any:
        raise AssertionError("a pintura foi ao disco")

    monkeypatch.setattr(launch_env, "launch_session_appid", _nunca)
    monkeypatch.setattr(launch_env, "read_last_run_marker", _nunca)
    monkeypatch.setattr(slo, "rotulo_do_jogo", _nunca)
    monkeypatch.setattr(slo, "steam_game_running_appid", _nunca)
    assert a07.aviso_do_jogo_aberto(SEM_WRAPPER, None)[1] == "3357650"


# --------------------------------------------------------------------------
# 2. "Voltar a perguntar" — o desfazer do que ela já dispensou
#
# O «NÃO PERGUNTAR» E O «FECHAR A STEAM» SAÍRAM EM 21/09/2026, e as réguas
# deles com eles. A lista de dispensados continua lida (`calados`), e quem já
# dispensou um jogo continua tendo por onde desfazer.
# --------------------------------------------------------------------------
def test_voltar_a_perguntar_tira_do_arquivo_de_verdade(a07):
    """Contra o `launch_dialog_dismissed.json` do lar de mentira: o arquivo muda.

    A MORDIDA: troque o `remove_dismissed_appid` do gesto por um `True` e este
    teste reprova — o gesto diria que desfez e o jogo ficaria dispensado.
    """
    from hefesto_dualsense4unix.app.actions import launch_wrapper_dialog as lwd

    lwd.add_dismissed_appid("3357650")
    assert "3357650" in lwd.load_dismissed_appids(), "o lar de mentira não gravou"
    _gesto("voltar-a-perguntar")(_ctx(), {"v": "3357650"}, None)
    assert "3357650" not in lwd.load_dismissed_appids(), (
        "o gesto disse que desfez e o `launch_dialog_dismissed.json` continua "
        "com o appid")


# --------------------------------------------------------------------------
# 4. a escada de três evidências — o jogo que ela JÁ FECHOU
# --------------------------------------------------------------------------
def test_a_escada_alcanca_o_jogo_que_ela_ja_fechou(a07, monkeypatch):
    """O caso REAL do botão: o jogo não funcionou, ela fechou, e só então veio.

    A MORDIDA: devolva o `slo.steam_game_running_appid()` sozinho ao `detectar`
    e este teste reprova — sem o terceiro degrau o produto responde "não achei
    jogo nenhum" exatamente no caso comum.
    """
    from hefesto_dualsense4unix.daemon import launch_env

    monkeypatch.setattr(launch_env, "launch_session_appid", lambda **kw: None)
    monkeypatch.setattr(launch_env, "read_last_run_marker",
                        lambda *a, **kw: (3357650, 1))
    assert a07.a_escada_do_jogo({}) == (3357650, a07.FECHADO)


def test_a_escada_prefere_a_evidencia_mais_forte(a07, monkeypatch):
    """A ordem é a da GTK: marker+pid vivo, wm_class, marker cru."""
    from hefesto_dualsense4unix.daemon import launch_env

    monkeypatch.setattr(launch_env, "read_last_run_marker",
                        lambda *a, **kw: (111, 1))
    monkeypatch.setattr(launch_env, "launch_session_appid", lambda **kw: 999)
    assert a07.a_escada_do_jogo(SEM_WRAPPER) == (999, a07.ABERTO)

    monkeypatch.setattr(launch_env, "launch_session_appid", lambda **kw: None)
    assert a07.a_escada_do_jogo(SEM_WRAPPER) == (3357650, a07.ABERTO)


def test_um_degrau_que_explode_nao_come_os_outros(a07, monkeypatch):
    """Os três leem disco, e disco falha. Cada um no seu `try`."""
    from hefesto_dualsense4unix.daemon import launch_env

    def _explode(*a: Any, **kw: Any) -> Any:
        raise OSError("marker ilegível")

    monkeypatch.setattr(launch_env, "launch_session_appid", _explode)
    monkeypatch.setattr(launch_env, "read_last_run_marker",
                        lambda *a, **kw: (3357650, 1))
    assert a07.a_escada_do_jogo({}) == (3357650, a07.FECHADO)


def test_sem_evidencia_nenhuma_a_escada_recusa(a07, monkeypatch):
    """Nada de palpite: sem os três degraus a resposta é `None`."""
    from hefesto_dualsense4unix.daemon import launch_env

    monkeypatch.setattr(launch_env, "launch_session_appid", lambda **kw: None)
    monkeypatch.setattr(launch_env, "read_last_run_marker", lambda *a, **kw: None)
    assert a07.a_escada_do_jogo({}) == (None, a07.FECHADO)
    with pytest.raises(RuntimeError, match="jogo"):
        _gesto("detectar")(_ctx(), {}, None)


def test_o_detectar_nao_diz_aberto_sobre_um_jogo_fechado(a07, monkeypatch):
    """A tela não afirma o que o produto não mediu — nem por reaproveitar frase.

    A MORDIDA: use a mesma frase nos dois casos e este teste reprova.
    """
    from hefesto_dualsense4unix.daemon import launch_env
    from hefesto_dualsense4unix.integrations import steam_launch_options as slo

    monkeypatch.setattr(launch_env, "launch_session_appid", lambda **kw: None)
    monkeypatch.setattr(launch_env, "read_last_run_marker",
                        lambda *a, **kw: (3357650, 1))
    monkeypatch.setattr(slo, "rotulo_do_jogo", lambda a: "Um Jogo")
    monkeypatch.setattr(a07.VIGIA, "agora", lambda: None)
    diz = _gesto("detectar")(_ctx(), {}, None)["mesa"]["steam-diz"]
    assert "está aberto agora" not in diz, (
        "o produto disse que um jogo FECHADO está aberto agora")
    assert "já fechou" in diz and "Um Jogo" in diz
