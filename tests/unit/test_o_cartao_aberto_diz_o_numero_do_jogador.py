#!/usr/bin/env python3
"""O CARTÃO ABERTO DIZ O NÚMERO DO JOGADOR — O-CARTAO-ABERTO-DIZ-O-NUMERO-DO-JOGADOR-01.

Pedido de 07/10/2026 (a [45]): o título do cartão aberto da aba Controles diz quem joga, o
nome que o usuário deu ao controle ou o «Pn» sem nome; o número é o VIVO (o mesmo das lâmpadas); e a
Calibrar fala a mesma língua, sem «Player N» nem «Sony».

A régua mede a BANCADA (`mockup/`, `onde.pagina(..., publicado=False)`): o `--publicar` a copia
byte a byte e é um passo à parte, então a medida vale antes e depois dele.

AS MORDIDAS (rodadas em 07/10/2026 e devolvidas):

* tirar o `data-campo="quem-joga"` do `identidade()` da `aba02.py` → a régua 1 reprova;
* tirar o `.so-aberto{display:none}` do CSS → o nome aparece no cartão fechado (régua 2);
* tirar o `max-width` do `.card-nome` aberto deixou de reprovar com o piso (20/10/2026): o pior
  caso cabe sem ele (régua 3, veja a docstring dela);
* o pacote da 02 deixar de emitir `jogador` → o número vivo some (4);
* a 08 voltar a ter uma `dono_na_linha` só dela → a identidade da função reprova (6);
* a Calibrar voltar ao «Player {jogador}» → a régua 7 reprova;
* o `.nome b` da Calibrar sem o `inline-flex`, o `.quem-nome` sem o `overflow:hidden` ou o
  `.quem-num` sem o `white-space:pre` → o «• P<n>» some ou cola no nome (régua 7, no WebKit).
"""
from __future__ import annotations

import json
import os
import pathlib
import re
import sys
from typing import Any

import pytest

from tests.conftest import exigir_gi_real

exigir_gi_real("O-CARTAO-ABERTO-DIZ-O-NUMERO-DO-JOGADOR-01 — o título do cartão medido no WebKit")

RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "scripts"))
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(RAIZ / "src/hefesto_dualsense4unix/interface"))

from hefesto_dualsense4unix.interface import monta, onde, pacotes
from hefesto_dualsense4unix.interface.pacotes import a02_controles as a02
from hefesto_dualsense4unix.interface.pacotes import a08_conexoes as a08
from hefesto_dualsense4unix.interface.pacotes import a11_calibrar_sensores as a11
from hefesto_dualsense4unix.interface.pacotes import em_fundo

P02 = "02-controles.html"
PCAL = "calibrar-sensores.html"
UNIQS = tuple(f"aa:bb:cc:00:00:0{n}" for n in (1, 2, 3, 4))
MAC_NORM = "AABBCC000001"
NOME_LONGO = "ABCDEFGHIJKLMNOPQRSTUVWX"  # 24 letras
PLASTICO_LONGO = "007 First Light Limited Edition"  # o mais longo de `cor_do_plastico.TABELA`


def _bancada(pagina: str) -> str:
    return onde.pagina(pagina, publicado=False).read_text(encoding="utf-8")


# ---------------------------------------------------------------- 1. o endereço


def test_o_cartao_aberto_tem_o_endereco_de_quem_joga_e_do_numero() -> None:
    """MORDIDA: tirar o `data-campo="quem-joga"` do gerador — o piloto não pinta o nome."""
    html = _bancada(P02)
    cartoes = re.findall(r'<div class="ctl card[^"]*" data-controle="p\d"', html)
    assert len(cartoes) == 4
    assert len(re.findall(r'data-campo="quem-joga"', html)) == 4, (
        "cada um dos quatro assentos precisa do endereço do nome no título aberto")
    # o número aparece na tira fechada E no título aberto: dois destinos do mesmo campo
    assert len(re.findall(r'data-campo="jogador" data-hef-alvo="html"', html)) >= 8


@pytest.mark.parametrize("aba", [P02])
def test_o_lugar_vazio_do_desenho_da_o_numero_do_assento(
        aba: str, monkeypatch: pytest.MonkeyPatch) -> None:
    """A régua 5 da sprint: o molde do lugar vazio, lido sobre a bancada, dá o número do assento.

    No produto o assento vazio é pintado pelo molde; sem a chave `jogador` nele, o número
    cai no «—».
    MORDIDA: o endereço sem `data-hef-alvo="html"` — a chave some do molde.
    """
    real = onde.pagina
    monkeypatch.setattr(
        onde, real.__name__, lambda p, publicado=True, **k: real(p, publicado=False, **k))
    monkeypatch.setattr(pacotes, "_DESENHO_DO_VAZIO", {})
    molde = pacotes.o_que_o_desenho_diz_do_lugar_vazio(aba)
    assert {p: c.get("jogador") for p, c in molde.items()} == {
        "p1": "1", "p2": "2", "p3": "3", "p4": "4"}, molde


# ---------------------------------------------------------------- 2/3/5. no WebKit


def _pior_caso() -> str:
    return (
        "(function(){var f=document.querySelector('.ctl[data-controle=\"p1\"] > .faixa');"
        "var cs=Array.prototype.map.call(f.children,function(e){var r=e.getBoundingClientRect();"
        "return {c:e.className,top:Math.round(r.top),alt:Math.round(r.height),"
        "larg:Math.round(r.width),"
        "d:getComputedStyle(e).display}});"
        "return {alt:Math.round(f.getBoundingClientRect().height),itens:cs}})()"
    )


@pytest.fixture(scope="module")
def medido() -> dict[str, Any]:
    """Abre a bancada da 02 e lê o título de cada cartão nas cenas que a sprint pede."""
    if not (os.environ.get("WAYLAND_DISPLAY") or os.environ.get("DISPLAY")):
        pytest.skip("sem servidor gráfico — o WebKit não abre")
    try:
        import regua_de_tela
        from hefesto_dualsense4unix.interface.folha_da_casa import FOLHA_DA_CASA
        from hefesto_dualsense4unix.interface.janela import (
            ALTURA_DO_DESENHO,
            LARGURA_DO_DESENHO,
        )
    except (ImportError, ValueError) as erro:  # pragma: no cover
        pytest.skip(f"a régua de tela não importou ({erro})")

    por_a_folha = (
        "(function(){var s=document.createElement('style');"
        "s.textContent=" + json.dumps(FOLHA_DA_CASA)
        + ";document.head.appendChild(s);return 1;})()"
    )

    def titulo(tela: Any, p: str) -> str:
        return str(tela._cru(
            "(function(){var e=document.querySelector("
            f"'.ctl[data-controle=\"{p}\"] .card-nome');return e?e.innerText:null}})()"))

    def escrever(tela: Any, p: str, campo: str, texto: str) -> None:
        tela.executar(
            f"document.querySelectorAll('.ctl[data-controle=\"{p}\"] [data-campo=\"{campo}\"]')"
            f".forEach(function(e){{e.textContent={json.dumps(texto)}}})")

    def abrir(tela: Any, id_: str) -> None:
        tela.executar(f"document.getElementById('{id_}').checked=true")

    fora: dict[str, Any] = {}
    with regua_de_tela.Tela(onde.pagina(P02, publicado=False), titulo_esperado="Hefesto",
                            largura=LARGURA_DO_DESENHO, altura=ALTURA_DO_DESENHO) as tela:
        tela.executar(por_a_folha)
        fora["sem_nome_p1_aberto"] = titulo(tela, "p1")
        fora["sem_nome_p2_fechado"] = titulo(tela, "p2")
        escrever(tela, "p2", "quem-joga", "Vitória")
        abrir(tela, "c-p2")
        fora["com_nome_p2_aberto"] = titulo(tela, "p2")
        fora["com_nome_p1_fechado"] = titulo(tela, "p1")
        abrir(tela, "c-todos")
        fora["todos"] = [titulo(tela, p) for p in ("p1", "p2", "p3", "p4")]
        abrir(tela, "c-p1")
        fora["fechado_depois"] = titulo(tela, "p2")
        fora["vazio_so_aberto"] = tela._cru(
            "getComputedStyle(document.querySelector("
            "'.ctl[data-controle=\"p3\"] .so-aberto')).display")
        fora["normal"] = tela._cru(_pior_caso())
        escrever(tela, "p1", "quem-joga", NOME_LONGO)
        escrever(tela, "p1", "peca", PLASTICO_LONGO)
        fora["pior"] = tela._cru(_pior_caso())
        fora["pior_titulo"] = titulo(tela, "p1")
    return fora


def test_o_cartao_aberto_sem_nome_diz_so_o_numero(medido: dict[str, Any]) -> None:
    assert medido["sem_nome_p1_aberto"].startswith("P1 "), medido["sem_nome_p1_aberto"]


def test_o_cartao_aberto_com_nome_diz_o_nome(medido: dict[str, Any]) -> None:
    """MORDIDA: tirar o `.so-aberto`/o `quem` do título — o nome não chega ao aberto."""
    t = medido["com_nome_p2_aberto"]
    assert t.startswith("Vitória"), t
    assert "Starlight Blue" in t and "BT" in t, t


def test_o_cartao_fechado_nao_ganha_o_nome(medido: dict[str, Any]) -> None:
    """MORDIDA: tirar o `.so-aberto{display:none}` — o nome aparece também na tira fechada."""
    assert medido["com_nome_p1_fechado"].startswith("P1 "), medido["com_nome_p1_fechado"]
    assert medido["fechado_depois"].startswith("P2 "), medido["fechado_depois"]
    assert "Vitória" not in medido["fechado_depois"]


def test_em_todos_os_conectados_dizem_quem_joga_e_os_vazios_nao(medido: dict[str, Any]) -> None:
    """No «Todos» os conectados estão abertos (nome ou «Pn»); os lugares vazios ficam no «Pn •»."""
    p1, p2, p3, p4 = (t.split(" ")[0] for t in medido["todos"])
    assert (p1, p2) == ("P1", "Vitória"), medido["todos"]
    assert (p3, p4) == ("Player", "Player"), medido["todos"]
    # r4-02-18, aprovado em 20/10: o lugar vazio diz só o número e «Desconectado»
    assert [t.strip() for t in medido["todos"][2:]] == [
        "Player 3 • Desconectado", "Player 4 • Desconectado"], medido["todos"]


def test_o_lugar_vazio_nao_mostra_o_nome(medido: dict[str, Any]) -> None:
    assert medido["vazio_so_aberto"] == "none"


def test_o_nome_de_24_letras_nao_quebra_a_faixa(medido: dict[str, Any]) -> None:
    """O preço do nome: a faixa não ganha segunda linha, e a bateria fica onde estava.

    Sem mordida pelo CSS desde o piso (medido em 20/10/2026): o pior caso, 24 letras e o plástico
    mais longo da tabela, mede 421 px e cabe na faixa a 1212 px mesmo sem o `max-width` do
    `.card-nome` aberto, e sem o `overflow`/`nowrap` dele. O teto de 340 px virou folga; a régua
    segue de comportamento, e reprova se um item da faixa crescer até a bateria cair de linha.
    """
    normal, pior = medido["normal"], medido["pior"]
    assert pior["alt"] == normal["alt"], f"a faixa cresceu: {normal['alt']} -> {pior['alt']}"
    visiveis = [i for i in pior["itens"] if i["d"] != "none"]
    # o piso de 24 px deixa os itens com alturas diferentes na MESMA linha: o que separa uma linha
    # da outra é o centro, não o topo
    centros = [i["top"] + i["alt"] / 2 for i in visiveis]
    assert max(centros) - min(centros) <= 2, f"itens em linhas diferentes: {visiveis}"


def test_o_nome_cortado_leva_a_linha_inteira_no_title(medido: dict[str, Any]) -> None:
    """O corte é por reticência; a linha inteira mora no `title` do `.card-nome` (`card-vpad`)."""
    html = _bancada(P02)
    assert re.search(
        r'<span class="card-nome" data-campo="card-vpad" data-hef-alvo="atributo"'
        r' data-hef-atributo="title"', html)
    assert medido["pior_titulo"].startswith("ABCDEFGHIJ")


# ---------------------------------------------------------------- 4. o número é o vivo


def _ctx(jogadores: tuple[int, ...]) -> pacotes.Contexto:
    conectados, mesa = [], []
    for i, n in enumerate(jogadores):
        uniq = UNIQS[i]
        conectados.append({"uniq": uniq, "player": n, "player_slot": n, "connected": True,
                           "transport": "bt", "battery_pct": 90, "is_primary": i == 0,
                           "inputs": {}})
        mesa.append({"pref": f"p{i + 1}", "jogador": n, "uniq": uniq, "nome": f"DualSense {n}",
                     "via": "BT", "transporte": "bt", "cor": "starlight-blue",
                     "conectado": True})
    return pacotes.Contexto(state={"active_profile": "x"}, mesa=mesa,
                            conectados=conectados, estados={})


@pytest.fixture
def com_a_bancada(monkeypatch: pytest.MonkeyPatch) -> None:
    """O pacote filtra pelo publicado; na régua o que vale é a bancada (antes do `--publicar`)."""
    doc = _bancada(P02)
    monkeypatch.setattr(a02, "_ENDERECOS", frozenset(re.findall(r'data-campo="([^"]+)"', doc)))


def test_o_numero_vivo_vai_para_o_cartao_e_a_posicao_nao_manda(
    com_a_bancada: None, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """MORDIDA: o pacote deixar de emitir `jogador` — o número volta ao do desenho.

    O jogador 5 no 4º assento: o número é o do daemon, não a posição do assento.
    """
    monkeypatch.setattr(a02, "nomes_de_quem_joga", lambda: {})
    cards = a02.pacote(_ctx((1, 2, 3, 5)))["cards"]
    assert cards[UNIQS[3]]["jogador"] == "5"
    assert cards[UNIQS[0]]["jogador"] == "1"
    assert cards[UNIQS[3]]["quem-joga"] == (
        'P<span data-campo="jogador" data-hef-alvo="html">5</span>')


def test_o_nome_dela_chega_escapado_ao_cartao(
    com_a_bancada: None, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(a02, "nomes_de_quem_joga", lambda: {MAC_NORM: "Vi <b>&"})
    cards = a02.pacote(_ctx((1, 2)))["cards"]
    assert cards[UNIQS[0]]["quem-joga"] == "Vi &lt;b&gt;&amp;"
    assert "quem-joga" in cards[UNIQS[1]]  # o outro, sem nome, fica no «Pn»


def test_o_lugar_vazio_nao_recebe_quem_joga(
    com_a_bancada: None, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Só os conectados ganham campos: o assento vazio não tem chave nos `cards`."""
    monkeypatch.setattr(a02, "nomes_de_quem_joga", lambda: {})
    cards = a02.pacote(_ctx((1,)))["cards"]
    assert set(cards) == {UNIQS[0]}


def test_o_nome_chega_a_02_pelo_alias_que_a_08_le(
    com_a_bancada: None, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """O nome da 02 vem do mesmo leitor da 04 e da 05 (`nome_do_jogador`), dublado no `Alias`.

    MORDIDA: a 02 ler o nome de outro lugar (um `{}` no `nomes_de_quem_joga`) — o nome some.
    """
    import time
    import types

    from hefesto_dualsense4unix.interface.pacotes import nome_do_jogador

    aparelho = types.SimpleNamespace(nome="Vitória", endereco=UNIQS[0].upper(), conectado=True,
                                     icone="input-gaming", classe=None, modalias="")
    monkeypatch.setattr(em_fundo, "_FUNDO", {"bluez": (time.monotonic() + 1e6, ((), (aparelho,)))})
    monkeypatch.setattr(em_fundo, "_FUNDO_EM_VOO", set())
    assert a02.nomes_de_quem_joga() == nome_do_jogador.nomes_dos_donos() == {MAC_NORM: "Vitória"}
    cards = a02.pacote(_ctx((1, 2)))["cards"]
    assert cards[UNIQS[0]]["quem-joga"] == "Vitória"
    assert cards[UNIQS[1]]["quem-joga"].startswith("P<span")


# ---------------------------------------------------------------- 6. a regra é uma só


def test_a_08_e_a_02_usam_a_mesma_regra_de_quem_joga() -> None:
    """MORDIDA: a 08 voltar a ter a `dono_na_linha` dela — o nome diria uma coisa em cada aba."""
    assert vars(a08)["dono_na_linha"] is monta.dono_na_linha
    assert vars(a02)["dono_na_linha"] is monta.dono_na_linha


def test_a_regra_do_nome_ou_do_pn() -> None:
    nomes = {MAC_NORM: "Vitória"}
    assert monta.dono_na_linha(nomes, "aa:bb:cc:00:00:01", 2) == "Vitória"
    assert monta.dono_na_linha(nomes, "AA-BB-CC-00-00-01", 2) == "Vitória"
    assert monta.dono_na_linha({}, "aa:bb:cc:00:00:01", 2) == "P2"
    assert monta.dono_na_linha({}, "aa:bb:cc:00:00:01", None) == ""
    assert monta.dono_na_linha({}, "aa:bb:cc:00:00:01", True) == ""
    escapado = monta.dono_na_linha({MAC_NORM: "<i>"}, "aa:bb:cc:00:00:01", 1, em_html=True)
    assert escapado == "&lt;i&gt;"
    assert monta.dono_na_linha({}, "x", 3, em_html=True) == (
        'P<span data-campo="jogador" data-hef-alvo="html">3</span>')


# ---------------------------------------------------------------- 7. a Calibrar


def test_a_calibrar_nao_diz_mais_player_nem_sony() -> None:
    """MORDIDA: voltar o «Player {jogador}» e o «Sony •» ao `calibrar.py`."""
    html = _bancada(PCAL)
    assert "Player " not in html and "Sony <span" not in html and "Sony •" not in html
    assert len(re.findall(r'data-campo="quem-joga"', html)) == 4  # 2 cartões + 2 miras


def test_a_calibrar_diz_o_nome_e_o_numero_ou_so_o_numero(monkeypatch: pytest.MonkeyPatch) -> None:
    doc = _bancada(PCAL)
    monkeypatch.setattr(a11, "_TEM_A_MIRA", True, raising=False)
    monkeypatch.setattr(a11, "nomes_de_quem_joga", lambda: {MAC_NORM: "Vitória"})
    mesa = _ctx((1, 2)).mesa
    carga = a11.pacote(_ctx((1, 2)))
    assert carga is not None
    blocos = "".join(str(b) for b in carga["blocos"].values())
    num1 = '<span data-campo="jogador" data-hef-alvo="html">1</span>'
    num2 = '<span data-campo="jogador" data-hef-alvo="html">2</span>'
    assert re.sub(r"<[^>]+>", "", blocos).count("Vitória • P1") >= 1, blocos[:400]
    assert f'title="Vitória">Vitória</span><span class="quem-num">{monta.SEPARADOR}P{num1}' in (
        blocos), blocos[:400]
    assert f">P{num2}<" in blocos or f"P{num2}</b>" in blocos
    assert "Player " not in blocos and "Sony <span" not in blocos
    assert mesa and doc  # a bancada e a mesa existem; o resto é do que o pacote devolveu


def test_o_texto_de_quem_joga_com_o_numero() -> None:
    com_nome = monta.quem_joga_com_o_numero({MAC_NORM: "Vi <b>"}, "aa:bb:cc:00:00:01", 1)
    assert com_nome.startswith(
        '<span class="quem-nome" title="Vi &lt;b&gt;">Vi &lt;b&gt;</span>'
        f'<span class="quem-num">{monta.SEPARADOR}P'), com_nome
    assert re.sub(r"<[^>]+>", "", com_nome) == "Vi &lt;b&gt; • P1"
    assert monta.quem_joga_com_o_numero({}, "aa:bb:cc:00:00:01", 1).startswith("P")
    assert "•" not in monta.quem_joga_com_o_numero({}, "aa:bb:cc:00:00:01", 1)
    assert monta.quem_joga_com_o_numero({}, "x", None) == ""


@pytest.fixture(scope="module")
def calibrar_medida() -> dict[str, Any]:
    """Abre a bancada da Calibrar e põe no 1º cartão o «<nome> • P3» que o pacote manda."""
    if not (os.environ.get("WAYLAND_DISPLAY") or os.environ.get("DISPLAY")):
        pytest.skip("sem servidor gráfico — o WebKit não abre")
    try:
        import regua_de_tela

        from hefesto_dualsense4unix.interface.folha_da_casa import FOLHA_DA_CASA
        from hefesto_dualsense4unix.interface.janela import (
            ALTURA_DO_DESENHO,
            LARGURA_DO_DESENHO,
        )
    except (ImportError, ValueError) as erro:  # pragma: no cover
        pytest.skip(f"a régua de tela não importou ({erro})")

    por_a_folha = (
        "(function(){var s=document.createElement('style');"
        "s.textContent=" + json.dumps(FOLHA_DA_CASA)
        + ";document.head.appendChild(s);return 1;})()"
    )
    medir = (
        "(function(){var c=document.querySelector('.ctr');var n=c.querySelector('.nome');"
        "var b=n.querySelector('b');var q=b.querySelector('.quem-num');"
        "var t=c.querySelector('.ctr-topo').getBoundingClientRect();"
        "var rn=n.getBoundingClientRect();var rq=q?q.getBoundingClientRect():null;"
        "var pt=q&&q.querySelector('.pt');var qn=b.querySelector('.quem-nome');"
        "var vao=(pt&&qn)?pt.getBoundingClientRect().left-qn.getBoundingClientRect().right:null;"
        "return {num:q?q.innerText:null,num_dir:rq?rq.right:null,nome_dir:rn.right,vao:vao,"
        "alt_b:Math.round(b.getBoundingClientRect().height),alt_topo:Math.round(t.height)}})()"
    )
    fora: dict[str, Any] = {}
    with regua_de_tela.Tela(onde.pagina(PCAL, publicado=False), titulo_esperado="Hefesto",
                            largura=LARGURA_DO_DESENHO, altura=ALTURA_DO_DESENHO) as tela:
        tela.executar(por_a_folha)
        # A cena do desenho tem dois cartões; com quatro controles cada um tem 1/4 da fila, e é
        # aí que o nome comum já não cabe. Os dois que faltam são cópias do segundo.
        tela.executar(
            "(function(){var cs=document.querySelectorAll('.ctr');var u=cs[cs.length-1];"
            "for(var i=cs.length;i<4;i++){u.parentNode.appendChild(u.cloneNode(true))}})()")
        fora["cartoes"] = tela._cru("document.querySelectorAll('.ctr').length")
        fora["sem_nome_topo"] = tela._cru(
            "Math.round(document.querySelector('.ctr .ctr-topo').getBoundingClientRect().height)")
        for rotulo, nome in (("comum", "Vitória Maria"), ("longo", NOME_LONGO)):
            quem = monta.quem_joga_com_o_numero({MAC_NORM: nome}, UNIQS[0], 3)
            tela.executar("document.querySelector('.ctr .nome b').innerHTML=" + json.dumps(quem))
            fora[rotulo] = tela._cru(medir)
    return fora


@pytest.mark.parametrize("rotulo", ["comum", "longo"])
def test_a_calibrar_mostra_o_numero_mesmo_com_o_nome_longo(
        calibrar_medida: dict[str, Any], rotulo: str) -> None:
    """O cartão da Calibrar é de uma linha: quem encolhe é o NOME, e o «• P<n>» fica à vista.

    Medido em 07/10/2026 pelo conferente final: num texto só, «Vitória Maria • P3» virava
    «Vitória Maria …», sem o número.
    MORDIDAS (`calibrar.py`, rodadas em 07/10/2026): tirar o `display:inline-flex` do `.nome b`
    (o texto volta a ser um só, e o corte do `.nome` come o «• P3»), ou o `overflow:hidden` do
    `.quem-nome` (o nome deixa de encolher e empurra o número para fora), ou o `white-space:pre`
    do `.quem-num` (o espaço antes do «•» some, e ele cola no nome).
    """
    assert calibrar_medida["cartoes"] == 4, calibrar_medida
    m = calibrar_medida[rotulo]
    assert m["num"] is not None and m["num"].strip().endswith("P3"), m
    assert m["num_dir"] <= m["nome_dir"] + 0.5, f"o «• P3» passou da caixa do nome: {m}"
    assert m["vao"] is not None and m["vao"] >= 2, f"o «•» colou no nome, sem o espaço: {m}"
    assert m["alt_topo"] == calibrar_medida["sem_nome_topo"], (
        f"o nome mudou a altura do topo do cartão: {m}")
