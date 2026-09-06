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
    "Não perguntar para este jogo"           gesto `nao-perguntar`, sobre
                                             `lwd.add_dismissed_appid`
    fechar a Steam por ~20 s, aplicar        gesto `consertar-fechando-a-steam`,
    e reabrir, com consentimento             sobre `slo.with_steam_closed`
    a escada de TRÊS evidências do jogo      `a_escada_do_jogo`, sobre
    (inclusive o jogo JÁ FECHADO)            `launch_env` + a wm_class do estado

O QUE CADA TESTE VIGIA, e a MORDIDA de cada um está na docstring dele. As três
que mais importam:

* troque `ha.wrapper_banner_text(state)` por um teste próprio de `wrapper_used`
  e o `test_o_aviso_e_a_decisao_da_gtk_e_nao_uma_copia` reprova — é a forma de
  defeito que esta casa persegue: a segunda cópia de uma regra que já tem dono;
* apague o `data-v` `CONFIRMO` do segundo clique (ou a janela de tempo) e o
  `test_um_clique_so_nunca_fecha_a_steam` reprova — sem os dois guardas a régua
  `--prova-gesto` fecharia a Steam DELA para provar que sabe clicar;
* devolva `steam_game_running_appid()` para o `detectar` e o
  `test_a_escada_alcanca_o_jogo_que_ela_ja_fechou` reprova.

NADA AQUI TOCA A MÁQUINA DELA. O `conftest.py` desta casa desvia `HOME` e os
quatro `XDG_*`; o que escreve em disco escreve no lar de mentira, e o que
fecharia a Steam é dublado — fechar a Steam de quem roda a suíte seria o
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

    monkeypatch.setattr(ha, "wrapper_banner_text", lambda s: "FRASE DA GTK")
    html, _ = a07.aviso_do_jogo_aberto(SEM_WRAPPER, None)
    assert "FRASE DA GTK" in html, (
        "o aviso não veio de `home_actions.wrapper_banner_text` — o pacote "
        "está decidindo por conta própria se o jogo passou pelo wrapper")


def test_o_aviso_usa_o_texto_dela_sem_redigitar(a07):
    """O texto é o `WRAPPER_MISSING_TEXT` da GTK, palavra por palavra.

    A MORDIDA: reescreva a frase no pacote e este teste reprova. Texto de tela
    é dela; uma segunda redação para o mesmo fato é o defeito que a decisão 14
    dela nomeou (*"uma frase, um dono"*).
    """
    from hefesto_dualsense4unix.app.actions import home_actions as ha

    html, _ = a07.aviso_do_jogo_aberto(SEM_WRAPPER, None)
    assert ha.WRAPPER_MISSING_TEXT in html


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


def test_o_aviso_e_o_botao_de_dispensar_chegam_ao_cartao(a07, desenho):
    """O que a função devolve tem de APARECER no cartão que a tela recebe.

    Sem esta régua o aviso poderia estar certo, ter teste unitário e **nunca
    chegar à tela** — que é o defeito que a `test_os_botoes_que_a_pintura_traz`
    da régua irmã existe para pegar, aqui aplicado ao corpo do cartão.
    """
    from hefesto_dualsense4unix.app.actions import home_actions as ha

    steam = _cartao_da_steam(a07, desenho, desenho.Leitura(com_wrapper=("1",)),
                             SEM_WRAPPER)
    assert ha.WRAPPER_MISSING_TEXT in steam.diz
    marcacao = desenho.acoes_html(steam)
    assert 'data-gesto="nao-perguntar"' in marcacao, (
        "o aviso acendeu e não veio com o botão que o dispensa — ela ficaria "
        "com um aviso que não sabe calar")
    assert 'data-v="3357650"' in marcacao, (
        "o botão de dispensar não diz QUAL jogo: ele dispensaria um appid "
        "escolhido por acaso")


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
# 2. "Não perguntar para este jogo" — a metade de ida que só a GTK escrevia
# --------------------------------------------------------------------------
def test_nao_perguntar_escreve_no_arquivo_de_verdade(a07):
    """O par completo, contra o `launch_dialog_dismissed.json` do lar de mentira.

    Não "a função foi chamada": **o arquivo mudou**, e o desfazer o desfaz.
    """
    from hefesto_dualsense4unix.app.actions import launch_wrapper_dialog as lwd

    assert "3357650" not in lwd.load_dismissed_appids(), "o lar de mentira sujo"
    _gesto("nao-perguntar")(_ctx(), {"v": "3357650"}, None)
    assert "3357650" in lwd.load_dismissed_appids(), (
        "o gesto disse que aplicou e o `launch_dialog_dismissed.json` não tem "
        "o appid")
    _gesto("voltar-a-perguntar")(_ctx(), {"v": "3357650"}, None)
    assert "3357650" not in lwd.load_dismissed_appids(), (
        "o par ficou pela metade — um gesto que só vai numa direção deixa a "
        "pessoa presa no estado em que clicou")


def test_nao_perguntar_sem_appid_recusa_e_nao_escreve(a07, monkeypatch):
    """Um clique sem `data-v` dispensaria um jogo escolhido por acaso."""
    from hefesto_dualsense4unix.app.actions import launch_wrapper_dialog as lwd

    def _nunca(*a: Any, **kw: Any) -> Any:
        raise AssertionError("escreveu no arquivo com o clique recusado")

    monkeypatch.setattr(lwd, "add_dismissed_appid", _nunca)
    with pytest.raises(ValueError):
        _gesto("nao-perguntar")(_ctx(), {"texto": "x"}, None)


def test_nao_perguntar_recusa_dizendo_quando_o_disco_engole(a07, monkeypatch):
    """`add_dismissed_appid` ENGOLE a exceção — quem confere é a releitura.

    A MORDIDA: apague o `if appid not in lwd.load_dismissed_appids()` e este
    teste reprova. Sem ele o gesto diria "aplicou" com o disco cheio, o aviso
    voltaria no tique seguinte e o segundo clique pareceria o primeiro.
    """
    from hefesto_dualsense4unix.app.actions import launch_wrapper_dialog as lwd

    monkeypatch.setattr(lwd, "add_dismissed_appid", lambda a: None)
    monkeypatch.setattr(lwd, "load_dismissed_appids", set)
    with pytest.raises(RuntimeError, match="dispensados"):
        _gesto("nao-perguntar")(_ctx(), {"v": "4242"}, None)


# --------------------------------------------------------------------------
# 3. fechar a Steam por ~20 s — a parede que o HTML tinha reerguido
# --------------------------------------------------------------------------
def _com_reparavel(a07, desenho, monkeypatch, *, steam_aberta=True,
                   jogo_aberto=False):
    """A leitura de um disco com UM jogo a repor, e os portões do censo."""
    lida = desenho.Leitura(com_wrapper=("1",),
                           reparaveis=(("2", "Um jogo", "perdeu"),),
                           instalados=3, frase="alguma frase")
    monkeypatch.setattr(a07, "PORTOES",
                        a07._Portoes(jogo_aberto=jogo_aberto,
                                     steam_aberta=steam_aberta))
    return lida


def test_o_botao_de_fechar_a_steam_so_aparece_onde_ele_funciona(
        a07, desenho, monkeypatch):
    """Com jogo aberto o produto não fecha a Steam por NADA.

    `stop_steam` com jogo aberto mataria o jogo e o progresso não salvo — então
    oferecer o botão ali seria oferecer uma recusa. E com a Steam já fechada o
    `Consertar` basta.

    A MORDIDA: tire o `and not PORTOES.jogo_aberto` e o segundo caso reprova.
    """
    lida = _com_reparavel(a07, desenho, monkeypatch)
    aberto = desenho.acoes_html(_cartao_da_steam(a07, desenho, lida, None))
    assert f'data-gesto="{a07.FECHAR}"' in aberto
    assert a07.PERGUNTA_DA_STEAM in aberto, (
        "o rótulo não é o do diálogo da GTK — o texto de tela tem um dono")

    _com_reparavel(a07, desenho, monkeypatch, jogo_aberto=True)
    com_jogo = desenho.acoes_html(_cartao_da_steam(a07, desenho, lida, None))
    assert f'data-gesto="{a07.FECHAR}"' not in com_jogo, (
        "o botão que fecha a Steam apareceu com um jogo aberto")

    _com_reparavel(a07, desenho, monkeypatch, steam_aberta=False)
    fechada = desenho.acoes_html(_cartao_da_steam(a07, desenho, lida, None))
    assert f'data-gesto="{a07.FECHAR}"' not in fechada, (
        "o botão apareceu com a Steam já fechada — não há o que fechar")


def test_sem_o_que_repor_o_botao_de_fechar_a_steam_nao_aparece(
        a07, desenho, monkeypatch):
    """Fechar a Steam de quem não tem nada a repor é custo puro."""
    monkeypatch.setattr(a07, "PORTOES", a07._Portoes(steam_aberta=True))
    lida = desenho.Leitura(com_wrapper=("1",), instalados=1)
    html = desenho.acoes_html(_cartao_da_steam(a07, desenho, lida, None))
    assert f'data-gesto="{a07.FECHAR}"' not in html


def test_um_clique_so_nunca_fecha_a_steam(a07, monkeypatch):
    """O consentimento que `with_steam_closed` EXIGE de quem a chama.

    O primeiro clique ARMA e devolve o cartão; nada foi fechado. É o que impede
    a régua automática (`--prova-gesto`) de derrubar a Steam DELA para provar
    que sabe clicar.

    A MORDIDA: faça o gesto chamar `with_steam_closed` no primeiro clique e
    este teste reprova.
    """
    from hefesto_dualsense4unix.integrations import steam_launch_options as slo

    def _nunca(*a: Any, **kw: Any) -> Any:
        raise AssertionError("fechou a Steam com UM clique")

    monkeypatch.setattr(slo, "with_steam_closed", _nunca)
    monkeypatch.setattr(a07.VIGIA, "agora", lambda: None)
    carga = _gesto(a07.FECHAR)(_ctx(), {"v": "steam"}, None)
    assert "blocos" in carga and "mesa" in carga


def test_o_segundo_clique_precisa_do_data_v_que_so_o_cartao_armado_tem(
        a07, desenho, monkeypatch):
    """O `data-v` do confirmar SÓ existe depois de um clique de verdade.

    A MORDIDA: emita o `CONFIRMO` no botão não-armado e este teste reprova —
    a régua leria o DOM, clicaria uma vez e fecharia a Steam dela.
    """
    lida = _com_reparavel(a07, desenho, monkeypatch)
    a07._desarmar()
    desarmado = desenho.acoes_html(_cartao_da_steam(a07, desenho, lida, None))
    assert f'data-v="{a07.CONFIRMO}"' not in desarmado

    a07._armar(a07.FECHAR)
    armado = desenho.acoes_html(_cartao_da_steam(a07, desenho, lida, None))
    assert f'data-v="{a07.CONFIRMO}"' in armado
    assert a07.CONFIRMA_A_STEAM in armado, (
        "o rótulo do confirmar não é o `rotulo_ok` do diálogo da GTK")


def test_a_confirmacao_expirada_nao_fecha_a_steam(a07, monkeypatch):
    """Ela armou, saiu para o almoço e voltou. Ninguém fecha nada.

    A MORDIDA: tire o `if not _armado()` e este teste reprova.
    """
    from hefesto_dualsense4unix.integrations import steam_launch_options as slo

    def _nunca(*a: Any, **kw: Any) -> Any:
        raise AssertionError("fechou a Steam com a confirmação vencida")

    monkeypatch.setattr(slo, "with_steam_closed", _nunca)
    a07._desarmar()
    with pytest.raises(RuntimeError, match="segundos"):
        _gesto(a07.FECHAR)(_ctx(), {"v": a07.CONFIRMO}, None)


def test_o_segundo_clique_desce_pelo_with_steam_closed(a07, monkeypatch):
    """O motor é o da GTK, e o gesto NÃO reimplementa fechar/aplicar/reabrir.

    A MORDIDA: troque o `with_steam_closed` por um `stop_steam` + `apply` +
    `reopen_steam` escritos aqui e este teste reprova por não ver a chamada.
    """
    from hefesto_dualsense4unix.integrations import sentinela_do_wrapper as sw
    from hefesto_dualsense4unix.integrations import steam_launch_options as slo

    chamadas: list[str] = []

    def _janela(tarefa, **kw: Any):
        chamadas.append("with_steam_closed")
        return slo.STEAM_JANELA_OK, tarefa()

    monkeypatch.setattr(slo, "with_steam_closed", _janela)
    monkeypatch.setattr(
        sw, "reparar_ou_adiar",
        lambda *a, **kw: (sw.REPARO_FEITO, sw.Censo(), {"applied": []}))
    monkeypatch.setattr(a07.VIGIA, "ler", lambda: None)
    a07._armar(a07.FECHAR)
    carga = _gesto(a07.FECHAR)(_ctx(), {"v": a07.CONFIRMO}, None)
    assert chamadas == ["with_steam_closed"]
    assert "blocos" in carga


def test_a_recusa_de_fechar_e_a_frase_da_gtk(a07, monkeypatch):
    """A frase da recusa tem UM dono: `format_steam_janela_recusa`.

    A MORDIDA: redija a recusa aqui e este teste reprova. Ela já diz, nos dois
    casos que importam, que **nada foi mudado** — e é a mesma que a janela
    velha mostra, para as duas telas não divergirem sobre o mesmo desfecho.
    """
    from hefesto_dualsense4unix.app.actions.daemon_actions import (
        format_steam_janela_recusa,
    )
    from hefesto_dualsense4unix.integrations import steam_launch_options as slo

    for janela in (slo.STEAM_JANELA_JOGO_ABERTO, slo.STEAM_JANELA_NAO_FECHOU):
        monkeypatch.setattr(slo, "with_steam_closed",
                            lambda t, j=janela, **kw: (j, None))
        a07._armar(a07.FECHAR)
        with pytest.raises(RuntimeError) as erro:
            _gesto(a07.FECHAR)(_ctx(), {"v": a07.CONFIRMO}, None)
        assert str(erro.value) == format_steam_janela_recusa(janela)


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


# --------------------------------------------------------------------------
# 5. os portões do censo, que decidem qual botão o cartão oferece
# --------------------------------------------------------------------------
def test_um_censo_que_falha_desarma_o_botao_que_fecha_a_steam(a07, monkeypatch,
                                                              tmp_path):
    """Sem censo não há resposta sobre a Steam — e o padrão é não oferecer.

    A MORDIDA: tire o `PORTOES = _Portoes()` do ramo de erro do `_ler_do_disco`
    e este teste reprova: um `steam_aberta=True` de uma leitura ANTERIOR
    acenderia o botão que fecha a Steam dela com base num censo que falhou.
    """
    from hefesto_dualsense4unix.integrations import jogos_locais as jl
    from hefesto_dualsense4unix.integrations import sentinela_do_wrapper as sw

    monkeypatch.setattr(a07, "PORTOES", a07._Portoes(steam_aberta=True))
    monkeypatch.setattr(jl, "pastas_de_atalhos", lambda: [tmp_path])

    def _explode(**kw: Any) -> Any:
        raise OSError("vdf ilegível")

    monkeypatch.setattr(sw, "censo_do_wrapper", _explode)
    lida = a07._ler_do_disco()
    assert lida.erros, "a régua mediria o caminho feliz"
    padrao = a07._Portoes()
    assert padrao == a07.PORTOES, (
        "os portões ficaram com o valor de uma leitura que falhou")


def test_o_censo_de_verdade_responde_pelos_dois_portoes():
    """O `getattr` do `_ler_do_disco` tolera DUBLÊ, nunca um motor que renomeou.

    POR QUE ESTE TESTE EXISTE, e sem ele a tolerância seria uma morte em
    silêncio: as réguas desta casa montam censos de mentira com os campos que
    cada uma precisa, e por isso o `_ler_do_disco` lê os dois portões com
    `getattr(..., False)`. No dia em que `sentinela_do_wrapper.Censo` renomeasse
    `steam_aberta`, o `getattr` responderia `False` **para sempre** — o botão
    que fecha a Steam nunca mais apareceria, e nada acusaria. Este teste é o
    que acusa.
    """
    from hefesto_dualsense4unix.integrations import sentinela_do_wrapper as sw

    censo = sw.Censo()
    for campo in ("jogo_aberto", "steam_aberta"):
        assert hasattr(censo, campo), (
            f"`sentinela_do_wrapper.Censo` não tem mais `{campo}` — o "
            "`getattr` do `_ler_do_disco` passaria a responder False sempre, e "
            "o botão que fecha a Steam sumiria da tela sem nada acusar.")


def test_os_portoes_saem_do_mesmo_censo_que_a_leitura(a07, monkeypatch,
                                                      tmp_path):
    """Uma passada, dois resultados — nunca duas medições que discordam."""
    from types import SimpleNamespace

    from hefesto_dualsense4unix.integrations import jogos_locais as jl
    from hefesto_dualsense4unix.integrations import prontuario_dos_jogos as pdj
    from hefesto_dualsense4unix.integrations import sentinela_do_wrapper as sw

    censo = SimpleNamespace(com_wrapper=["7"], reparaveis=[], intocaveis=[],
                            recusados=[], erros=[], jogo_aberto=True,
                            steam_aberta=True)
    monkeypatch.setattr(jl, "pastas_de_atalhos", lambda: [tmp_path])
    monkeypatch.setattr(sw, "censo_do_wrapper", lambda **kw: censo)
    monkeypatch.setattr(sw, "frase_do_aviso", lambda c: "")
    monkeypatch.setattr(pdj, "jogos_instalados", list)
    monkeypatch.setattr(pdj, "pontes_confirmadas", list)
    lida = a07._ler_do_disco()
    assert lida.com_wrapper == ("7",)
    esperado = a07._Portoes(jogo_aberto=True, steam_aberta=True)
    assert esperado == a07.PORTOES
