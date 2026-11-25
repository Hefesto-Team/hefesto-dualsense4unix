"""A barra de cada aparelho gerido mora no cartão, numa linha própria abaixo do nome (25/11/2026).

A força mais alta de uma extensão de brinquedos era uma barra só, na aba «Força», para todos os
brinquedos. Agora o manifesto declara, junto das ações dos aparelhos, uma ``barra`` por aparelho
(id, rótulo, faixa e degraus), e o estado que a extensão publica traz o valor de cada um. A janela
a desenha numa linha própria do cartão, logo abaixo da linha do nome (o nome inteiro, a bateria e
a chave), com a largura do cartão: o rótulo à esquerda, a barra e o número à direita. Na ordem do
DOM, a barra vem depois da chave, e o foco do teclado e o leitor de tela a alcançam depois do
nome. Arrastar chega à extensão pela ``extensao.acao`` com o alvo
(no compasso de 20 por segundo) e soltar grava, e a janela mostra o que a extensão publica. Sem a
declaração, nada muda para as outras extensões.

Prova da D-2511-O-TETO-DA-EXTENSAO-E-DE-CADA-BRINQUEDO.

MORDIDAS (25/11/2026, executadas sobre a cura e devolvidas):

- a barra de volta à linha do nome, entre a bateria e a chave, reprova a estrutura do cartão e,
  no WebKit, a linha própria, a largura do cartão e o nome inteiro;
- a barra sem ``display:flex`` no CSS (o rótulo numa linha e o deslizante em outra) reprova a
  linha única do rótulo, do deslizante e do número no WebKit.
"""
from __future__ import annotations

import asyncio
import copy
import json
import pathlib
import re
from html.parser import HTMLParser
from types import SimpleNamespace
from typing import Any

import pytest
from pydantic import ValidationError

from hefesto_dualsense4unix.core.events import EventBus
from hefesto_dualsense4unix.daemon.ipc_handlers import IpcHandlersMixin
from hefesto_dualsense4unix.interface import desenho_da_experimental as exp
from hefesto_dualsense4unix.interface import pacotes
from hefesto_dualsense4unix.mods import porta as porta_das_extensoes
from hefesto_dualsense4unix.mods.manifesto import Manifesto
from tests.unit.test_a_aba_lancadores_ganha_as_modificacoes import (  # noqa: F401
    ctx,
    lar,
)
from tests.unit.test_a_coluna_agora_e_o_parar_tudo_vem_do_servico import (  # noqa: F401
    _entrar,
    _porta,
    curto,
)
from tests.unit.test_a_janela_da_extensao_age_e_gere_os_aparelhos import (  # noqa: F401
    APARELHOS,
    _instalada,
    _manifesto,
    _pecas,
    _Ponte,
    _servico,
    janela,
)
from tests.unit.test_a_linha_sem_aparelho_fica_a_direita_do_parear import no_webkit
from tests.unit.test_a_lista_da_janela_configurar_nao_pula_ao_clicar_um_efeito import (  # noqa: F401
    ENDERECO,
    MOD,
    VISTAS,
    pagina_fresca,
    pecas_da_lovense,
)

TETO = {"id": "teto", "rotulo": "Teto", "minimo": 0, "maximo": 100,  # (noqa-acento)
        "passo": 1, "degraus": 20, "dica": "A força mais alta que vai a este aparelho"}
COM_O_TETO = [{**ap, "barra": 20 * n} for n, ap in enumerate(APARELHOS, 1)]
VIVO_COM_O_TETO = {"ligado": True, "nivel": 3, "perfil": "Ondas", "aparelhos": COM_O_TETO,
                   "serie": 1}


def _com_a_barra(grupo: str | None = "Aparelhos") -> dict[str, Any]:
    pecas = _pecas(grupo)
    pecas["aparelhos_acoes"]["barra"] = copy.deepcopy(TETO)  # (noqa-acento)
    return pecas


def _gestao(barra: exp.BarraDaJanela | None, aparelhos: list[dict[str, Any]], *,
            desligada: bool = False) -> exp.Gestao:
    acoes = (exp.AcaoDaJanela("ligar", "Ligar", icone="ligar"),
             exp.AcaoDaJanela("testar", "Testar", icone="testar"))
    return exp.Gestao("toque", exp.AparelhosDaJanela(acoes, "Aparelhos", barra),
                      {"aparelhos": aparelhos}, desligada=desligada)


BARRA = exp.BarraDaJanela("teto", "Teto", 0, 100, 1, 20, "A força mais alta")


def _cartao(html: str, alvo: str) -> str:
    cartao = re.search(rf'data-alvo="{alvo}".*?(?=data-alvo="|$)', html, re.S)
    assert cartao, f"o aparelho {alvo} não tem cartão"
    return cartao.group(0)


@pytest.fixture
def barras(janela: Any, monkeypatch: pytest.MonkeyPatch) -> Any:  # noqa: F811
    a07 = janela[0]
    monkeypatch.setattr(a07, "_BARRAS", a07._Barras())
    return janela


def test_o_manifesto_declara_uma_barra_por_aparelho_e_a_confere() -> None:
    m = Manifesto.model_validate(_manifesto(**_com_a_barra()))
    assert m.aparelhos_acoes is not None and m.aparelhos_acoes.barra is not None
    assert m.aparelhos_acoes.ids == ("ligar", "testar", "teto")
    sem_grupo = _com_a_barra(grupo=None)
    with pytest.raises(ValidationError, match="pede o grupo"):
        Manifesto.model_validate(_manifesto(**sem_grupo))
    repetida = _com_a_barra()
    repetida["aparelhos_acoes"]["barra"]["id"] = "testar"  # (noqa-acento)
    with pytest.raises(ValidationError, match="repete o id da ação testar"):
        Manifesto.model_validate(_manifesto(**repetida))
    torta = _com_a_barra()
    torta["aparelhos_acoes"]["barra"]["maximo"] = 0  # (noqa-acento)
    with pytest.raises(ValidationError, match="faixa fora de ordem"):
        Manifesto.model_validate(_manifesto(**torta))
    assert Manifesto.model_validate(_manifesto(**_pecas())).aparelhos_acoes.barra is None  # type: ignore[union-attr]


def test_o_estado_leva_o_valor_da_barra_de_cada_aparelho() -> None:
    aparelho = porta_das_extensoes._aparelho({"id": "ap-1", "nome": "Lush", "barra": 80})
    assert aparelho["barra"] == 80.0
    assert "barra" not in porta_das_extensoes._aparelho({"id": "ap-1", "nome": "Lush"})
    for torto in ({"id": "ap-1", "nome": "Lush", "barra": "80"},
                  {"id": "ap-1", "nome": "Lush", "barra": True},
                  {"nome": "Lush", "barra": 80}):
        with pytest.raises(porta_das_extensoes.RecusaError, match="barra de um aparelho"):
            porta_das_extensoes._aparelho(torto)


class _Arvore(HTMLParser):
    """A árvore dos elementos de um pedaço de HTML: cada nó é (tag, classes, atributos, filhos)."""

    VAZIOS = frozenset({"input", "br", "img", "hr", "meta", "link", "source", "path", "circle",
                        "rect", "line", "polyline", "polygon", "ellipse", "use"})

    def __init__(self) -> None:
        super().__init__()
        self.raiz: dict[str, Any] = {"tag": "", "classes": (), "attrs": {}, "filhos": [],
                                     "texto": ""}
        self.pilha = [self.raiz]

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        mapa = {k: v or "" for k, v in attrs}
        no = {"tag": tag, "classes": tuple(mapa.get("class", "").split()), "attrs": mapa,
              "filhos": [], "texto": ""}
        self.pilha[-1]["filhos"].append(no)
        if tag not in self.VAZIOS:
            self.pilha.append(no)

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)
        if tag not in self.VAZIOS:
            self.pilha.pop()

    def handle_endtag(self, tag: str) -> None:
        while len(self.pilha) > 1:
            if self.pilha.pop()["tag"] == tag:
                break

    def handle_data(self, data: str) -> None:
        for no in self.pilha:
            no["texto"] += data


def _cartoes(html: str) -> dict[str, dict[str, Any]]:
    arvore = _Arvore()
    arvore.feed(html)
    return {no["attrs"]["data-alvo"]: no for no in arvore.raiz["filhos"]
            if "mj-ap" in no["classes"]}


def _filho(no: dict[str, Any], classe: str) -> dict[str, Any] | None:
    return next((f for f in no["filhos"] if classe in f["classes"]), None)


def _descendentes(no: dict[str, Any]) -> list[dict[str, Any]]:
    saida = []
    for f in no["filhos"]:
        saida += [f, *_descendentes(f)]
    return saida


def test_a_barra_mora_numa_linha_propria_logo_abaixo_da_linha_do_nome() -> None:
    """O cartão, filho a filho: a linha do nome (nome, bateria e chave, sem a barra), a linha da
    barra, a onda e o rodapé. A barra vem no DOM depois da chave, na ordem em que se lê."""
    cartoes = _cartoes(exp.aparelhos_geridos_html(_gestao(BARRA, COM_O_TETO)))
    assert sorted(cartoes) == ["ap-1", "ap-2", "ap-3", "ap-4"], "uma barra em cada cartão"
    for alvo, cartao in cartoes.items():
        linhas = [next((c for c in f["classes"] if c.startswith("mj-ap-")), f["tag"])
                  for f in cartao["filhos"]]
        assert linhas == ["mj-ap-cab", "mj-ap-barra", "mj-ap-meio", "mj-ap-pe"], (alvo, linhas)
        cab, barra = _filho(cartao, "mj-ap-cab"), _filho(cartao, "mj-ap-barra")
        assert cab is not None and barra is not None
        na_cab = [next((c for c in ("mj-ap-nome", "mj-pct", "mj-chave") if c in d["classes"]), "")
                  for d in _descendentes(cab)]
        assert [c for c in na_cab if c] == ["mj-ap-nome", "mj-pct", "mj-chave"], (alvo, na_cab)
        assert not [d for d in _descendentes(cab) if d["tag"] == "input"], \
            f"{alvo}: a linha do nome ainda leva a barra"
        rotulo = barra["filhos"][0]
        assert "mj-ap-barra-rot" in rotulo["classes"] and rotulo["texto"] == "Teto", alvo
        entradas = [d for d in _descendentes(barra) if d["tag"] == "input"]
        numeros = [d for d in _descendentes(barra) if d["tag"] == "b"]
        assert len(entradas) == 1 and entradas[0]["attrs"]["type"] == "range", alvo
        assert len(numeros) == 1 and _descendentes(barra).index(numeros[0]) > \
            _descendentes(barra).index(entradas[0]), f"{alvo}: o número fica à direita da barra"
    barra_4 = _filho(cartoes["ap-4"], "mj-ap-barra")
    assert barra_4 is not None
    entrada = next(d for d in _descendentes(barra_4) if d["tag"] == "input")["attrs"]
    assert (entrada["value"], entrada["min"], entrada["max"]) == ("80", "0", "100")
    assert entrada["data-gesto"] == exp.GESTO_DE_SOLTAR_A_BARRA
    assert entrada["data-hef-vivo"] == exp.GESTO_DA_BARRA_VIVA
    assert entrada["data-v"] == "toque:teto:ap-4", "a barra leva o aparelho do cartão"
    numero = next(d for d in _descendentes(barra_4) if d["tag"] == "b")
    assert numero["texto"] == "16/20", "o número (degrau) ao lado"


def test_sem_a_barra_declarada_ou_sem_o_valor_nada_muda() -> None:
    sem_barra = exp.aparelhos_geridos_html(_gestao(None, COM_O_TETO))
    assert "mj-ap-barra" not in sem_barra and 'type="range"' not in sem_barra
    sem_valor = exp.aparelhos_geridos_html(_gestao(BARRA, APARELHOS))
    assert "mj-ap-barra" not in sem_valor, "a janela inventou um valor que a extensão não publicou"
    assert sem_barra == sem_valor


def test_com_a_chave_desligada_a_barra_fica_a_vista_e_parada() -> None:
    html = exp.aparelhos_geridos_html(_gestao(BARRA, COM_O_TETO, desligada=True))
    assert html.count('class="mj-ap-barra"') == 4
    assert exp.GESTO_DA_BARRA_VIVA not in html and exp.GESTO_DE_SOLTAR_A_BARRA not in html
    assert html.count('type="range"') == html.count(" disabled aria-disabled") == 4


def test_os_gestos_da_barra_sao_da_aba_e_o_vivo_nao_grava() -> None:
    for gesto in (exp.GESTO_DA_BARRA_VIVA, exp.GESTO_DE_SOLTAR_A_BARRA):
        assert pacotes.gesto_da_pagina("07-lancadores.html", gesto) is not None, gesto
    grava = (pacotes.GESTOS_QUE_MEXEM.get(("07-lancadores.html", exp.GESTO_DA_BARRA_VIVA))
             or pacotes.GESTOS_QUE_MEXEM.get(("*", exp.GESTO_DA_BARRA_VIVA)))
    assert not grava, "o gesto vivo declara gravação e o piloto o recusa"


def test_o_ipc_leva_a_barra_na_faixa_com_o_soltou(lar: Any) -> None:  # noqa: F811
    _instalada(lar, **_com_a_barra())
    levadas: list[tuple[Any, ...]] = []

    def barra(mod: str, barra_id: str, alvo: str, valor: float, *, soltou: bool) -> bool:
        levadas.append((mod, barra_id, alvo, valor, soltou))
        return True

    servico = _servico(SimpleNamespace(lugares=lar, porta=SimpleNamespace(barra=barra)))

    def pedir(**params: Any) -> Any:
        return asyncio.run(IpcHandlersMixin._handle_mods_acao(servico, {"mod": "toque", **params}))

    assert pedir(acao="teto", alvo="ap-1", valor=35, soltou=False) == {"enviada": True}
    assert pedir(acao="teto", alvo="ap-1", valor=40, soltou=True) == {"enviada": True}
    with pytest.raises(ValueError, match="vai de 0 a 100"):
        pedir(acao="teto", alvo="ap-1", valor=101, soltou=True)
    with pytest.raises(ValueError, match="vai de 0 a 100"):
        pedir(acao="teto", alvo="ap-1", valor=True, soltou=True)
    with pytest.raises(ValueError, match="soltou da barra"):
        pedir(acao="teto", alvo="ap-1", valor=40)
    with pytest.raises(ValueError, match="verdadeiro, falso ou o id"):
        pedir(acao="testar", alvo="ap-1", valor=40)
    assert levadas == [("toque", "teto", "ap-1", 35.0, False),
                       ("toque", "teto", "ap-1", 40.0, True)]


def test_o_arrastar_sai_no_compasso_e_o_soltar_na_hora_so_a_dona(
        curto: pathlib.Path) -> None:  # noqa: F811
    """MORDIDA: sem o soltar tirar o arrastar que esperava, ele sai depois e desfaz o soltar."""
    async def corrida() -> tuple[list[dict[str, Any]], bool]:
        porta = await _porta(curto, EventBus())
        a = await _entrar(curto, "ficha-a", {"ligado": True})
        b = await _entrar(curto, "ficha-b", {"ligado": True})
        try:
            for n in range(30):
                assert porta.barra("acessorios", "teto", "ap-1", n, soltou=False) is True
                await asyncio.sleep(1 / 60)
            assert porta.barra("acessorios", "teto", "ap-1", 32, soltou=False) is True
            assert porta.barra("acessorios", "teto", "ap-1", 33, soltou=True) is True
            await asyncio.sleep(0.3)
            chegaram = []
            while (evento := await asyncio.to_thread(a.esperar_evento, 0.2)) is not None:
                chegaram.append(evento["params"])
            vazou = await asyncio.to_thread(b.esperar_evento, 0.2) is not None
            assert porta.barra("ninguem", "teto", "ap-1", 3, soltou=True) is False
            return chegaram, vazou
        finally:
            a.fechar()
            b.fechar()
            await porta.parar()

    chegaram, vazou = asyncio.run(corrida())
    assert not vazou, "a outra extensão recebeu a barra"
    assert {c["nome"] for c in chegaram} == {"extensao.acao"}
    assert 3 <= len(chegaram) <= 12, f"{len(chegaram)} eventos em meio segundo de arrastar"
    ultimo = {"mod": "acessorios", "acao": "teto", "alvo": "ap-1",  # (noqa-acento)
              "valor": 33, "soltou": True}
    assert chegaram[-1]["dados"] == ultimo, "o soltar sai por último"
    assert all(c["dados"]["soltou"] is False for c in chegaram[:-1])
    assert 32 not in [c["dados"]["valor"] for c in chegaram], \
        "o arrastar que esperava o compasso saiu depois do soltar"


def test_a_janela_arrasta_vivo_solta_e_mostra_o_que_a_extensao_publica(
        barras: Any, ctx: Any) -> None:  # noqa: F811
    """O arrastar manda o valor sem gravar e segura a lista sob o dedo; o soltar manda o
    ``soltou``, e a barra mostra o valor pedido até a extensão publicar o estado novo, e então o
    que a extensão publicou. MORDIDA: sem a barra no cartão, o cartão não a tem."""
    a07, instalar, abrir = barras
    instalar(**_com_a_barra())
    ponte = _Ponte(VIVO_COM_O_TETO)
    html = abrir(ponte)["blocos"]["#mod-janela"]
    assert 'data-v="toque:teto:ap-2"' in html and 'value="40"' in html

    def arrastar(valor: int, carimbo: float) -> Any:
        return a07.arrastar_a_barra_do_aparelho(
            ctx, {"v": "toque:teto:ap-2", "valor": str(valor), "carimbo": str(carimbo),
                  "evento": "input"}, ponte)

    assert arrastar(55, 100.0) == {}, "o gesto vivo pintou"
    assert arrastar(50, 99.0) == {}
    assert arrastar(60, 101.0) == {}
    a07._AGORA.ler("toque", ponte)
    assert "#mod-aparelhos" not in a07._com_os_aparelhos({"blocos": {}})["blocos"], \
        "o tique trocou a barra sob o dedo"
    assert a07.soltar_a_barra_do_aparelho(
        ctx, {"v": "toque:teto:ap-2", "valor": "60", "carimbo": "102", "evento": "click"},
        ponte) is None, "o clique na barra não é o soltar"
    a07.soltar_a_barra_do_aparelho(
        ctx, {"v": "toque:teto:ap-2", "valor": "60", "carimbo": "103", "evento": "change"}, ponte)
    feitas = [(p["valor"], p["soltou"]) for m, p in ponte.chamadas
              if m == "mods.acao" and p.get("acao") == "teto"]  # (noqa-acento)
    assert feitas == [(55, False), (60, False), (60, True)], feitas
    a07._AGORA.ler("toque", ponte)
    bloco = a07._com_os_aparelhos({"blocos": {}})["blocos"]["#mod-aparelhos"]
    assert 'value="60"' in _cartao(bloco, "ap-2"), \
        "a barra voltou ao valor de antes enquanto a extensão gravava"
    ponte.estado = {**VIVO_COM_O_TETO, "serie": 2, "aparelhos": [
        {**ap, "barra": 55} if ap["id"] == "ap-2" else ap for ap in COM_O_TETO]}
    a07._AGORA.ler("toque", ponte)
    bloco = a07._com_os_aparelhos({"blocos": {}})["blocos"]["#mod-aparelhos"]
    assert 'value="55"' in _cartao(bloco, "ap-2"), "a barra mostra o que a extensão publica"


def test_o_soltar_que_nao_chega_devolve_a_barra_ao_que_vale(barras: Any, ctx: Any) -> None:  # noqa: F811
    a07, instalar, abrir = barras
    instalar(**_com_a_barra())
    ponte = _Ponte(VIVO_COM_O_TETO, rodando=False)
    abrir(ponte)
    a07._AGORA.ler("toque", ponte)
    antes = a07._com_os_aparelhos({"blocos": {}})["blocos"]["#mod-aparelhos"]
    with pytest.raises(RuntimeError, match="não está rodando"):
        a07.soltar_a_barra_do_aparelho(
            ctx, {"v": "toque:teto:ap-2", "valor": "90", "carimbo": "5", "evento": "change"},
            ponte)
    a07._AGORA.ler("toque", ponte)
    depois = a07._com_os_aparelhos({"blocos": {}})["blocos"]["#mod-aparelhos"]
    assert 'value="40"' in _cartao(depois, "ap-2"), "a barra ficou no valor que não valeu"
    assert depois != antes, "a barra não se repinta, e a tela segue no valor arrastado"


NOMES = ("Hush", "Nora", "Lush 3",
         "Gravity com um nome comprido demais para caber na linha do cartão")
NA_TELA = [{**ap, "nome": nome} for ap, nome in zip(COM_O_TETO, NOMES, strict=True)]
_ABRIR_A_ABA = """(function(endereco, h){
  if (!document.getElementById('mod-janela')) return 'a página não tem a janela #mod-janela';
  location.hash = endereco;
  window.__hef.pintar({blocos: {'#mod-janela': h}});
  const j = document.getElementById('mod-janela');
  const rot = [...j.querySelectorAll('.mj-abas > label')].find(l => l.textContent === 'Brinquedos');
  if (!rot) return 'sem a aba';
  rot.click();
  return 'ok';
})(%s, %s)"""
_PINTAR_OS_CARTOES = """(function(h){
  window.__hef.pintar({blocos: {'#mod-aparelhos': h}});
  return 'ok';
})(%s)"""
_MEDIR_OS_CARTOES = """(function(){
  const r = e => { if (!e) return null; const x = e.getBoundingClientRect();
    return {x: x.left, y: x.top, d: x.right, b: x.bottom}; };
  const depois = (a, b) => !!(a && b && (a.compareDocumentPosition(b) & 4));
  return JSON.stringify([...document.querySelectorAll('#mod-aparelhos > .mj-ap')].map(c => {
    const cs = getComputedStyle(c), cab = c.querySelector('.mj-ap-cab');
    const nome = c.querySelector('.mj-ap-nome'), chave = cab.querySelector('.mj-chave');
    const barra = c.querySelector('.mj-ap-barra');
    const entrada = barra && barra.querySelector('input[type=range]');
    const dentro = c.getBoundingClientRect().left + c.clientLeft;
    return {alvo: c.dataset.alvo, cartao: r(c),
      miolo: {x: dentro + parseFloat(cs.paddingLeft),
                 d: dentro + c.clientWidth - parseFloat(cs.paddingRight)},
      cab: r(cab), nome: r(nome), nome_inteiro: nome.scrollWidth <= nome.clientWidth,
      antes_da_chave: r(chave.previousElementSibling), chave: r(chave),
      vao: parseFloat(getComputedStyle(cab).columnGap) || 0,
      barra: r(barra), rotulo: r(barra && barra.querySelector('.mj-ap-barra-rot')),
      entrada: r(entrada), numero: r(barra && barra.querySelector('b')),
      meio: r(c.querySelector('.mj-ap-meio')),
      ordem: depois(nome, chave) && depois(chave, entrada),
      parada: !!(entrada && entrada.disabled)};
  }));
})()"""


def _falhas_da_geometria(caso: str, cartoes: list[dict[str, Any]], parada: bool) -> list[str]:
    falhas: list[str] = []
    if len(cartoes) != 4:
        return [f"{caso}: {len(cartoes)} cartões"]
    if abs(cartoes[0]["cartao"]["y"] - cartoes[1]["cartao"]["y"]) > 0.5 or \
            cartoes[0]["cartao"]["d"] > cartoes[1]["cartao"]["x"]:
        falhas.append(f"{caso}: os cartões não seguem dois por fileira")
    for c in cartoes:
        onde = f"{caso} {c['alvo']}"
        cab, barra, miolo = c["cab"], c["barra"], c["miolo"]
        if barra is None or c["entrada"] is None:
            falhas.append(f"{onde}: sem a barra")
            continue
        if barra["y"] < cab["b"] - 0.5:
            falhas.append(f"{onde}: a barra começa em {barra['y']:.1f}, na linha do nome "
                          f"(que acaba em {cab['b']:.1f})")
        if barra["b"] > c["meio"]["y"] + 0.5:
            falhas.append(f"{onde}: a barra invade a linha da onda")
        if abs(barra["x"] - miolo["x"]) > 1 or abs(barra["d"] - miolo["d"]) > 1:
            falhas.append(f"{onde}: a barra vai de {barra['x']:.1f} a {barra['d']:.1f}, e o "
                          f"cartão de {miolo['x']:.1f} a {miolo['d']:.1f}")
        largura = barra["d"] - barra["x"]
        entrada = c["entrada"]["d"] - c["entrada"]["x"]
        if entrada < 0.6 * largura:
            falhas.append(f"{onde}: o deslizante tem {entrada:.0f} de {largura:.0f} px da linha")
        if abs(c["rotulo"]["x"] - barra["x"]) > 1 or abs(c["numero"]["d"] - barra["d"]) > 1:
            falhas.append(f"{onde}: o rótulo não fica à esquerda e o número à direita")
        centros = [(c[k]["y"] + c[k]["b"]) / 2 for k in ("rotulo", "entrada", "numero")]
        if max(centros) - min(centros) > 1.5 or not (
                c["rotulo"]["d"] <= c["entrada"]["x"] + 0.5 <= c["numero"]["x"] + 1):
            falhas.append(f"{onde}: o rótulo, o deslizante e o número não dividem uma linha só")
        if abs(c["chave"]["d"] - cab["d"]) > 1:
            falhas.append(f"{onde}: a chave não fica à direita da linha do nome")
        sobra = c["chave"]["x"] - c["antes_da_chave"]["d"] - c["vao"]
        if not c["nome_inteiro"] and sobra > 1:
            falhas.append(f"{onde}: o nome se corta com {sobra:.0f} px sobrando na linha")
        if c["alvo"] != "ap-4" and not c["nome_inteiro"]:
            falhas.append(f"{onde}: o nome curto saiu cortado")
        if not c["ordem"]:
            falhas.append(f"{onde}: no DOM, a barra não vem depois do nome e da chave")
        if c["parada"] != parada:
            falhas.append(f"{onde}: a barra parada={c['parada']}, esperado {parada}")
    return falhas


def test_no_webkit_a_barra_tem_linha_propria_com_a_largura_do_cartao_e_o_nome_inteiro(
        barras: Any, pagina_fresca: pathlib.Path) -> None:  # noqa: F811
    """Num WebKit de verdade, nas duas vistas, na janela da forma da Lovense (a coluna «Agora» à
    esquerda e dois cartões por fileira, a largura em que o nome saía cortado): a barra numa linha
    abaixo da linha do nome, da borda esquerda à direita do conteúdo do cartão, o rótulo à
    esquerda e o número à direita; o nome curto inteiro, e o comprido só se corta sem espaço
    sobrando; a chave à direita. Vale também com a chave da extensão desligada (a barra parada)."""
    from hefesto_dualsense4unix.interface import hefesto_vivo

    _, instalar, abrir = barras
    pecas = pecas_da_lovense()
    pecas["aparelhos_acoes"]["barra"] = {**TETO, "id": "limite"}  # (noqa-acento)
    instalar(mod_id=MOD, **pecas)
    html = abrir(_Ponte({**VIVO_COM_O_TETO, "aparelhos": NA_TELA}),
                 mod_id=MOD)["blocos"]["#mod-janela"]
    assert html.count(f'data-v="{MOD}:limite:') == 4, "a janela da Lovense sem a barra"
    parada = exp.aparelhos_geridos_html(_gestao(BARRA, NA_TELA, desligada=True))
    passos: list[list[Any]] = [["js", hefesto_vivo.BOOTSTRAP],
                               ["js", _ABRIR_A_ABA % (json.dumps(ENDERECO), json.dumps(html))],
                               ["espera", 0.3], ["js", _MEDIR_OS_CARTOES],
                               ["js", _PINTAR_OS_CARTOES % json.dumps(parada)],
                               ["espera", 0.3], ["js", _MEDIR_OS_CARTOES]]
    lidos = no_webkit(pagina_fresca, {f"{w}x{h}": (w, h, passos) for w, h in VISTAS})
    print(json.dumps(lidos, ensure_ascii=False))
    falhas: list[str] = []
    for caso, (_, abriu, ligada, pintou, desligada) in lidos.items():
        assert abriu == "ok" and pintou == "ok", (caso, abriu, pintou)
        falhas += _falhas_da_geometria(caso, json.loads(ligada), parada=False)
        falhas += _falhas_da_geometria(f"{caso} desligada", json.loads(desligada), parada=True)
    assert not falhas, "\n".join(falhas)

