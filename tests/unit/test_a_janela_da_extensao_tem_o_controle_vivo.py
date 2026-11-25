"""O controle vivo da janela de uma extensão (A-JANELA-DO-MODO-IMERSAO-GANHA-UM-DESENHO-VIVO-01).

O desenho é o do «Mapa dos controles» (``mapa.controle``), posto uma vez na 07 num ``<template>``;
as peças acendem pelo que a porta viu a extensão ESCREVER, por controle, há pouco.
"""

from __future__ import annotations

import asyncio
import os
import pathlib
import re
from typing import Any

import pytest

from hefesto_dualsense4unix.core.events import EventBus
from hefesto_dualsense4unix.interface import controle_vivo as cv
from hefesto_dualsense4unix.interface import desenho_da_experimental as exp
from hefesto_dualsense4unix.mods.manifesto import Manifesto
from hefesto_dualsense4unix.mods.porta import (
    ACESO_DO_AO_VIVO_S,
    CONTROLES_DO_AO_VIVO,
    Porta,
    estado_dos_acessorios,
)
from tests.unit.test_a_coluna_agora_e_o_parar_tudo_vem_do_servico import (  # noqa: F401
    P1,
    _Extensao,
    curto,
)

P2 = "aa:bb:cc:00:00:02"
DESENHO_DA_07 = pathlib.Path(__file__).resolve().parents[2] / "mockup/07-lancadores.html"


class _Relogio:
    def __init__(self) -> None:
        self.t = 1000.0

    def __call__(self) -> float:
        return self.t


async def _porta(pasta: pathlib.Path, relogio: _Relogio, jogo_escreve: set[str]) -> Porta:
    async def escritor(metodo: str, pedido: dict[str, Any]) -> Any:
        return {"status": "ok"}

    porta = Porta(pasta / "mods.sock", EventBus(), escritor=escritor,
                  o_jogo_escreve=lambda uniq, canal: canal in jogo_escreve,
                  uniq_do_posto=lambda: P1, relogio=relogio,
                  controles=lambda: [{"uniq": P1, "jogador": 1, "cor": "Cosmic Red"},
                                     {"uniq": P2, "jogador": 2, "cor": ""}])
    await porta.iniciar()
    porta.registrar("ficha", "exemplo", os.getpid(),
                    ["escrever:luz", "escrever:gatilho", "publicar:acessorios.estado"])
    return porta


def test_a_porta_anota_so_o_que_chegou_ao_controle_e_nunca_o_uniq(curto) -> None:  # noqa: F811
    """D-1611-A-JANELA-DA-EXTENSAO-MOSTRA-O-CONTROLE-DO-MAPA: a peça acende pelo que chegou."""
    relogio = _Relogio()
    jogo_escreve: set[str] = set()

    async def corrida() -> dict[str, Any]:
        porta = await _porta(curto, relogio, jogo_escreve)
        ext = _Extensao(curto / "mods.sock")
        try:
            await asyncio.to_thread(ext.pedir, "mod.ola", {"ficha": "ficha"})
            for passo in range(3):
                relogio.t = 1000.0 + passo * 0.3
                ok = await asyncio.to_thread(ext.pedir, "luz.set",
                                             {"uniq": P1, "rgb": [255, 0, 0]})
                assert "result" in ok, ok
            relogio.t = 1001.0
            await asyncio.to_thread(ext.pedir, "luz.set", {"uniq": P2, "rgb": [0, 0, 255]})
            jogo_escreve.add("gatilho")
            recusa = await asyncio.to_thread(ext.pedir, "gatilho.set", {
                "uniq": P1, "lado": "direito", "modo": "Rigid", "forcas": [0, 200]})
            assert "error" in recusa, recusa
            relogio.t = 1001.5
            sem_estado = porta.agora_de("exemplo")
            assert "ao_vivo" not in sem_estado, "sem estado, a janela não tem o que desenhar"
            ok = await asyncio.to_thread(ext.pedir, "acessorios.estado", {"ligado": True})
            assert "result" in ok, ok
            return porta.agora_de("exemplo")
        finally:
            ext.fechar()
            await porta.parar()

    agora = asyncio.run(corrida())
    ao_vivo = agora["ao_vivo"]
    assert ao_vivo["controles"] == [{"jogador": 1, "cor": "Cosmic Red"}, {"jogador": 2, "cor": ""}]
    assert ao_vivo["escritas"] == [
        {"canal": "luz", "controle": 1, "ha_ms": 500},
        {"canal": "luz", "controle": 0, "ha_ms": 900},
    ], "a última luz de cada controle, e o gatilho recusado não entra"
    assert P1 not in repr(agora) and P2 not in repr(agora)


def test_a_escrita_velha_apaga_a_peca(curto) -> None:  # noqa: F811
    relogio = _Relogio()

    async def corrida() -> tuple[list[Any], list[Any]]:
        porta = await _porta(curto, relogio, set())
        ext = _Extensao(curto / "mods.sock")
        try:
            await asyncio.to_thread(ext.pedir, "mod.ola", {"ficha": "ficha"})
            await asyncio.to_thread(ext.pedir, "luz.set", {"uniq": P1, "rgb": [1, 2, 3]})
            relogio.t += ACESO_DO_AO_VIVO_S - 0.5
            antes = porta.ao_vivo_de("exemplo")["escritas"]
            relogio.t += 1
            return antes, porta.ao_vivo_de("exemplo")["escritas"]
        finally:
            ext.fechar()
            await porta.parar()

    antes, depois = asyncio.run(corrida())
    assert len(antes) == 1 and depois == []


def test_a_memoria_guarda_so_a_ultima_de_cada_canal_de_no_maximo_quatro(
        tmp_path: pathlib.Path) -> None:
    async def escritor(metodo: str, pedido: dict[str, Any]) -> Any:
        return {"status": "ok"}

    relogio = _Relogio()
    uniqs = [f"aa:bb:cc:00:00:0{n}" for n in range(1, 6)]
    porta = Porta(tmp_path / "x.sock", EventBus(), escritor=escritor,
                  o_jogo_escreve=lambda uniq, canal: False, uniq_do_posto=lambda: P1,
                  relogio=relogio,
                  controles=lambda: [{"uniq": u, "jogador": n} for n, u in enumerate(uniqs, 1)])
    for passo in range(600):
        relogio.t += 0.001
        porta._anotar_a_escrita("exemplo", "luz" if passo % 2 else "som", uniqs[0])
    for uniq in [*uniqs[1:], ""]:
        relogio.t += 0.001
        porta._anotar_a_escrita("exemplo", "mira", uniq)
    guardadas = porta._escritas["exemplo"]
    assert sum(1 for u in guardadas if u) == CONTROLES_DO_AO_VIVO and "" in guardadas
    assert uniqs[0] not in guardadas, "o quinto controle tira o que escreveu há mais tempo"
    assert all(len(canais) == 1 for canais in guardadas.values()), "uma escrita por canal"
    escritas = porta.ao_vivo_de("exemplo")["escritas"]
    assert sorted((e["controle"] is None, e["controle"] or 0) for e in escritas) == [
        (False, 1), (False, 2), (False, 3), (False, 4), (True, 0)]
    assert [e for e in escritas if e.get("todos")] == [
        {"canal": "mira", "controle": None, "ha_ms": 0, "todos": True}]


def test_a_memoria_se_zera_quando_a_extensao_desliga_e_quando_sai(curto) -> None:  # noqa: F811
    relogio = _Relogio()

    async def corrida() -> tuple[int, int, int]:
        porta = await _porta(curto, relogio, set())
        ext = _Extensao(curto / "mods.sock")
        try:
            await asyncio.to_thread(ext.pedir, "mod.ola", {"ficha": "ficha"})
            await asyncio.to_thread(ext.pedir, "luz.set", {"uniq": P1, "rgb": [1, 2, 3]})
            antes = len(porta.ao_vivo_de("exemplo")["escritas"])
            await asyncio.to_thread(ext.pedir, "acessorios.estado", {"ligado": False})
            desligada = len(porta.ao_vivo_de("exemplo")["escritas"])
            await asyncio.to_thread(ext.pedir, "luz.set", {"uniq": P1, "rgb": [1, 2, 3]})
        finally:
            ext.fechar()
        for _ in range(100):
            if not porta.vivas():
                break
            await asyncio.sleep(0.02)
        saiu = len(porta.ao_vivo_de("exemplo")["escritas"])
        await porta.parar()
        return antes, desligada, saiu

    assert asyncio.run(corrida()) == (1, 0, 0)


@pytest.mark.parametrize(("limiar", "vale"), [(0, True), (10, True), (11, False), (True, False)])
def test_o_estado_leva_o_limiar_do_clima_de_0_a_10(limiar: Any, vale: bool) -> None:
    if vale:
        assert estado_dos_acessorios("x", {"ligado": True, "limiar": limiar})["limiar"] == limiar
        return
    with pytest.raises(Exception, match="limiar"):
        estado_dos_acessorios("x", {"ligado": True, "limiar": limiar})


def _manifesto(**extra: Any) -> Manifesto:
    return Manifesto.model_validate({
        "id": "exemplo", "nome": "Exemplo", "api": ">=2,<3", "versao": "1.0",  # (noqa-acento)
        "licenca": "MIT", "tipos": ["processo"], "processo": {"executar": ["true"]},
        "permissoes": ["publicar:acessorios.estado"], **extra})  # (noqa-acento)


def test_o_manifesto_aceita_o_controle_vivo_o_cartao_o_canal_e_a_ordem_das_abas() -> None:
    m = _manifesto(agora=["controle", "nivel", "clima"], abas=["B", "A"], opcoes=[
        {"id": "a", "rotulo": "Coração", "tipo": "ligado", "grupo": "A", "cartao": "Coração",
         "canal": "haptica"}])
    assert (m.agora, m.abas, m.opcoes[0].cartao, m.opcoes[0].canal) == (
        ["controle", "nivel", "clima"], ["B", "A"], "Coração", "haptica")
    with pytest.raises(ValueError):
        _manifesto(opcoes=[{"id": "a", "rotulo": "A", "tipo": "ligado", "canal": "teclado"}])
    with pytest.raises(ValueError, match="ao_vivo"):
        _manifesto(agora=["ao_vivo"])


def _vivo(escolhido: int | None = None) -> cv.Vivo:
    estado = {"ligado": True, "nivel": 6, "limiar": 4, "ao_vivo": {
        "controles": [{"jogador": 1, "cor": "Starlight Blue"}, {"jogador": 2, "cor": "White"}],
        "escritas": [{"canal": "gatilho", "controle": 0, "ha_ms": 300},
                     {"canal": "luz", "controle": 1, "ha_ms": 200},
                     {"canal": "som", "controle": 0, "ha_ms": 1900}]}}
    return cv.vivo_de(estado, escolhido, [1, 3, 6])


def test_o_desenho_acende_so_o_que_a_extensao_escreveu_ha_pouco_no_controle_escolhido() -> None:
    um, dois = _vivo(), _vivo(1)
    assert (um.escolhido, um.acesos) == (0, frozenset({"gatilho"}))
    assert (dois.escolhido, dois.acesos) == (1, frozenset({"luz"}))
    assert _vivo(7).escolhido == 0, "o controle que saiu devolve o desenho ao primeiro"
    assert [c.colorway for c in um.controles] == ["starlight-blue", "white"]
    lugar = cv.lugar_html(dois)
    assert 'data-acesos="luz"' in lugar and "--z-casca:" in lugar
    assert cv.lugar_html(cv.Vivo()).startswith('<div class="cv-lugar" data-acesos=""')


def test_a_janela_desenha_o_controle_o_clima_a_fileira_e_os_cartoes_na_ordem_das_abas() -> None:
    opcoes = [exp.OpcaoDaJanela("imersao", "forca", "Força", "deslizante", 100, grupo="Geral",
                                maximo=100),
              exp.OpcaoDaJanela("imersao", "batida", "Coração", "deslizante", 80, grupo="Efeitos",
                                maximo=100, cartao="Coração", canal="haptica"),
              exp.OpcaoDaJanela("imersao", "tipo", "Tipo", "escolha", "Batida", ("Batida", "Onda"),
                                grupo="Efeitos", cartao="Coração"),
              exp.OpcaoDaJanela("imersao", "susto", "Tato", "ligado", True, grupo="Efeitos",
                                cartao="Susto"),
              exp.OpcaoDaJanela("imersao", "c1", "Motores", "ligado", True, grupo="Efeitos",
                                cartao="Canais", canal="vibracao"),
              exp.OpcaoDaJanela("imersao", "c2", "Gatilhos", "ligado", False, grupo="Efeitos",
                                cartao="Canais", canal="gatilho")]
    acoes = (exp.AcaoDaJanela("testar", "Testar", "Efeitos"),)
    html = exp.modificacao_miolo_html(
        "Modo imersão", opcoes, mod="imersao", agora=("controle", "nivel", "clima"),
        estado={"ligado": True, "nivel": 6}, acoes=acoes, vivo=_vivo(), abas=("Geral", "Efeitos"))
    assert html.count('class="cv-lugar"') == 1 and 'data-agora="clima"' in html
    assert 'data-gesto="controle-vivo-da-modificacao" data-v="imersao:1"' in html
    assert "cv-faixa" not in html and "mod-ao-vivo" not in html, "a faixa «Ao vivo» saiu"
    assert html.count('class="mj-fileira"') == 1, "o cartão só de chaves vira uma fileira"
    assert re.search(r'<span class="mj-fc on" id="mod-op-c1" data-canal="vibracao"[^>]*'
                     r'data-gesto="guardar-opcao-da-modificacao" data-v="imersao:c1" '
                     r'data-ligado="0">Motores<', html), "a chave ligada pede desligar"
    assert re.search(r'<span class="mj-fc" id="mod-op-c2"[^>]*aria-checked="false"[^>]*'
                     r'data-v="imersao:c2" data-ligado="1">Gatilhos<', html), \
        "a chave desligada pede ligar"
    assert re.findall(r'<label for="mj-aba-\d+">([^<]+)<', html) == ["Geral", "Efeitos"]
    assert exp.acoes_por_aba(opcoes, acoes, None, abas=("Geral", "Efeitos")) == {1: acoes}
    assert html.count('class="mj-cartao') == 2 and html.count('class="mj-cartao" data-canal') == 1
    assert 'class="ky-linha mj-ct-cabeca" id="mod-op-batida" data-canal="haptica"' in html
    assert '<div class="mj-ct-tit">Susto</div>' in html


def test_o_molde_e_o_desenho_do_mapa_com_cada_peca_marcada_e_sem_cor_de_modelo() -> None:
    import aba07

    molde = cv.molde_html()
    for canal, pecas in cv.PECAS_DO_CANAL.items():
        for peca in pecas:
            assert re.search(rf'<g id="mp-{peca}"[^>]*data-canal="{canal}"', molde), peca
    assert 'id="mp-glifo-cross"' in molde, "os glifos do Mapa vieram junto"
    assert not re.search(r"data-campo=|data-hef-", molde), "o pintor da 07 pintaria dentro do molde"
    assert aba07.identidade_congelada(molde + cv.css_do_molde()) == []
    variaveis, _claros, defs = cv.pintura_do_modelo("spider-man-2")
    assert "url(#mp-casca-spider-man-2)" in variaveis and 'id="mp-casca-spider-man-2"' in defs
    assert cv.pintura_do_modelo("white")[1], "o glifo da tecla branca fica escuro"


def test_o_desenho_da_07_leva_o_molde_uma_vez_e_o_script_que_o_veste() -> None:
    pagina = DESENHO_DA_07.read_text(encoding="utf-8")
    assert pagina.count(f'<template id="{cv.ID_DO_MOLDE}">') == 1
    assert "molde.content.firstElementChild" in pagina and "cv-aceso" in pagina


def test_o_controle_de_fora_nao_acende_e_o_de_todos_acende_em_qualquer_um() -> None:
    """A escrita a um controle que a lista não traz (o de fora, sem este desenho) não acende o
    DualSense desenhado; a de todos (a mira em todos) acende em qualquer um."""
    estado = {"ligado": True, "ao_vivo": {
        "controles": [{"jogador": None, "cor": ""}, {"jogador": None, "cor": "White"}],
        "escritas": [{"canal": "vibracao", "controle": None, "ha_ms": 100},
                     {"canal": "mira", "controle": None, "todos": True, "ha_ms": 100},
                     {"canal": "luz", "controle": 1, "ha_ms": 100}]}}
    primeiro, segundo = (cv.vivo_de(estado, n) for n in (0, 1))
    assert primeiro.acesos == frozenset({"mira"})
    assert segundo.acesos == frozenset({"mira", "luz"}), "sem número de jogador, o chip escolhe"
    chips = cv.chips_html(segundo, "g", "m")
    assert chips.count('data-v="m:1"') == 1 and chips.count(" on") == 1


def test_a_conexao_curta_da_extensao_nao_apaga_o_controle_e_a_saida_sem_estado_limpa_tudo(
        curto) -> None:  # noqa: F811
    """A segunda conexão da mesma extensão (a curta do ``aparelho.abrir``) que fecha não zera a
    memória do controle aceso; e a conexão que sai sem nunca ter dado o estado sai inteira."""
    relogio = _Relogio()

    async def corrida() -> tuple[int, int, bool]:
        porta = await _porta(curto, relogio, set())
        porta.registrar("ficha", "exemplo", os.getpid(),
                        ["escrever:luz", "ler:acessorios.gesto"])
        ext, curta = _Extensao(curto / "mods.sock"), _Extensao(curto / "mods.sock")
        try:
            await asyncio.to_thread(ext.pedir, "mod.ola", {"ficha": "ficha"})
            await asyncio.to_thread(curta.pedir, "mod.ola", {"ficha": "ficha"})
            await asyncio.to_thread(ext.pedir, "luz.set", {"uniq": P1, "rgb": [1, 2, 3]})
            curta.fechar()
            for _ in range(100):
                if len(porta._conexoes) == 1:
                    break
                await asyncio.sleep(0.02)
            depois_da_curta = len(porta.ao_vivo_de("exemplo")["escritas"])
        finally:
            ext.fechar()
        for _ in range(100):
            if not porta._conexoes:
                break
            await asyncio.sleep(0.02)
        saiu = len(porta.ao_vivo_de("exemplo")["escritas"])
        limpa = not porta._conexoes
        await porta.parar()
        return depois_da_curta, saiu, limpa

    assert asyncio.run(corrida()) == (1, 0, True)


@pytest.mark.parametrize("deu_o_estado", [False, True])
def test_a_extensao_que_sai_limpa_a_porta_mesmo_com_um_passo_que_falha(
        curto, deu_o_estado: bool) -> None:  # noqa: F811
    """A extensão que sai, com ou sem ter dado o estado, sai inteira da porta: o passo que falha
    (aqui o aviso do estado vazio no barramento) não pula a conexão nem a memória das escritas."""
    relogio = _Relogio()

    async def corrida() -> tuple[bool, bool]:
        porta = await _porta(curto, relogio, set())
        porta.registrar("ficha", "exemplo", os.getpid(),
                        ["escrever:luz", "ler:acessorios.gesto"])

        def publicar_que_quebra(*_a: Any, **_k: Any) -> None:
            raise RuntimeError("o barramento caiu")

        porta.bus.publish = publicar_que_quebra  # type: ignore[method-assign]
        ext = _Extensao(curto / "mods.sock")
        try:
            await asyncio.to_thread(ext.pedir, "mod.ola", {"ficha": "ficha"})
            await asyncio.to_thread(ext.pedir, "luz.set", {"uniq": P1, "rgb": [1, 2, 3]})
            if deu_o_estado:
                porta._conexoes.copy().pop().deu_o_estado = True
        finally:
            ext.fechar()
        for _ in range(100):
            if not porta._conexoes:
                break
            await asyncio.sleep(0.02)
        limpa = not porta._conexoes and "exemplo" not in porta._escritas
        await porta.parar()
        return limpa, deu_o_estado

    assert asyncio.run(corrida()) == (True, deu_o_estado)


def test_o_cartao_do_aparelho_rotula_as_escolhas_so_quando_ha_mais_de_uma() -> None:
    """Duas escolhas de 0 a 100 % no cartão do controle seriam iguais sem o rótulo; uma só, não."""
    def cartao(*ids: str) -> str:
        estado = {"ligado": True, "aparelhos": [{"id": "jogador-1", "nome": "White", "ligado": True,
                                                  "controles": [
            {"id": i, "tipo": "escolha", "rotulo": i.title(), "valor": "100",
             "opcoes": [{"id": "100", "rotulo": "100%"}]} for i in ids]}]}  # (noqa-acento)
        gestao = exp.Gestao("imersao", exp.AparelhosDaJanela((), "Jogo"), estado, frozenset(), (),
                            False, True)
        return exp.aparelhos_geridos_html(gestao)

    assert cartao("forca", "volume").count('class="mj-ap-cc-rot"') == 2
    assert 'class="mj-ap-cc-rot"' not in cartao("forca")


def test_o_desenho_da_janela_do_modo_imersao_e_o_que_o_gerador_escreve() -> None:
    """O `mockup/janela-do-modo-imersao.html` sai do `janela_do_imersao.py`, do mesmo
    `modificacao_miolo_html` do produto: o HTML à mão que diverge do gerador reprova aqui."""
    import janela_do_imersao as gerador

    gravada = (pathlib.Path(__file__).resolve().parents[2] / "mockup" / gerador.NOME).read_text(
        encoding="utf-8")
    assert gravada == "\n".join(linha.rstrip() for linha in gerador.pagina().split("\n"))
    assert "cv-faixa" not in gravada and gravada.count('class="tela-nova"') == 1
    assert re.findall(r'<label for="mj-aba-\d+">([^<]+)<', gravada) == [
        "Sentir", "Efeitos", "Controles"]


def test_na_aba_com_linhas_e_cartoes_as_linhas_vem_antes_dos_cartoes() -> None:
    """Na aba que tem linhas e também cartões, a ordem é a ação, as linhas e, embaixo, os
    cartões; na aba só de ação e aparelhos, os dois seguem juntos na caixa ``.mj-sec``."""
    estado = {"ligado": True, "aparelhos": [{"id": "jogador-1", "nome": "White", "ligado": True}]}
    procurar = exp.AcaoDaJanela("procurar", "Procurar receitas", "Jogo")
    receita = exp.OpcaoDaJanela("imersao", "receita", "Receita", "ligado", True, grupo="Jogo")
    gestao = exp.Gestao("imersao", exp.AparelhosDaJanela((), "Jogo"), estado, controles=True)

    com_linhas = exp._abas_com_as_pecas([receita], "Jogo", mod="imersao", acoes=[procurar],
                                        gestao=gestao)
    assert (com_linhas.index('data-v="imersao:procurar"') < com_linhas.index("mod-op-receita")
            < com_linhas.index('id="mod-aparelhos"'))
    assert 'class="mj-sec"' not in com_linhas

    sem_linhas = exp._abas_com_as_pecas([], "Jogo", mod="imersao", acoes=[procurar],
                                        gestao=gestao)
    assert '<div class="mj-sec"><div class="mj-acoes"' in sem_linhas
