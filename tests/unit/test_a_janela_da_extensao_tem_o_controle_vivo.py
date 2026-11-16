"""O controle vivo da janela de uma extensão (A-JANELA-DO-MODO-IMERSAO-GANHA-UM-DESENHO-VIVO-01).

O desenho é o do «Mapa dos controles» (``mapa.controle``), posto uma vez na 07 num ``<template>``;
as peças acendem pelo que a porta viu a extensão ESCREVER, por controle, e a faixa «Ao vivo» mostra
os últimos 30 s, um canal por linha, na cor do plástico de cada controle.
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
from hefesto_dualsense4unix.mods.porta import JANELA_DO_AO_VIVO_S, Porta, estado_dos_acessorios
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
            relogio.t = 1005.0
            await asyncio.to_thread(ext.pedir, "luz.set", {"uniq": P2, "rgb": [0, 0, 255]})
            jogo_escreve.add("gatilho")
            recusa = await asyncio.to_thread(ext.pedir, "gatilho.set", {
                "uniq": P1, "lado": "direito", "modo": "Rigid", "forcas": [0, 200]})
            assert "error" in recusa, recusa
            relogio.t = 1006.0
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
    assert ao_vivo["trechos"] == [
        {"canal": "luz", "jogador": 2, "de_ms": 1000, "ate_ms": 1000},
        {"canal": "luz", "jogador": 1, "de_ms": 6000, "ate_ms": 5400},
    ], "as três luzes do P1 a 0,3 s uma da outra são um trecho só, e o gatilho recusado não entra"
    assert P1 not in repr(agora) and P2 not in repr(agora)


def test_a_escrita_de_mais_de_30_s_sai_da_faixa(curto) -> None:  # noqa: F811
    relogio = _Relogio()

    async def corrida() -> tuple[list[Any], list[Any]]:
        porta = await _porta(curto, relogio, set())
        ext = _Extensao(curto / "mods.sock")
        try:
            await asyncio.to_thread(ext.pedir, "mod.ola", {"ficha": "ficha"})
            await asyncio.to_thread(ext.pedir, "luz.set", {"uniq": P1, "rgb": [1, 2, 3]})
            relogio.t += JANELA_DO_AO_VIVO_S - 1
            antes = porta.ao_vivo_de("exemplo")["trechos"]
            relogio.t += 2
            return antes, porta.ao_vivo_de("exemplo")["trechos"]
        finally:
            ext.fechar()
            await porta.parar()

    antes, depois = asyncio.run(corrida())
    assert len(antes) == 1 and depois == []


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
    m = _manifesto(agora=["controle", "nivel", "clima", "ao_vivo"], abas=["B", "A"], opcoes=[
        {"id": "a", "rotulo": "Coração", "tipo": "ligado", "grupo": "A", "cartao": "Coração",
         "canal": "haptica"}])
    assert (m.agora, m.abas, m.opcoes[0].cartao, m.opcoes[0].canal) == (
        ["controle", "nivel", "clima", "ao_vivo"], ["B", "A"], "Coração", "haptica")
    with pytest.raises(ValueError):
        _manifesto(opcoes=[{"id": "a", "rotulo": "A", "tipo": "ligado", "canal": "teclado"}])


def _vivo(escolhido: int | None = None) -> cv.Vivo:
    estado = {"ligado": True, "nivel": 6, "limiar": 4, "ao_vivo": {
        "controles": [{"jogador": 1, "cor": "Starlight Blue"}, {"jogador": 2, "cor": "White"}],
        "trechos": [{"canal": "gatilho", "jogador": 1, "de_ms": 900, "ate_ms": 300},
                    {"canal": "luz", "jogador": 2, "de_ms": 800, "ate_ms": 200},
                    {"canal": "som", "jogador": 1, "de_ms": 9000, "ate_ms": 8000}]}}
    return cv.vivo_de(estado, ["som", "luz", "gatilho", "haptica"], escolhido, [1, 3, 6])


def test_o_desenho_acende_so_o_que_a_extensao_escreveu_ha_pouco_no_controle_escolhido() -> None:
    um, dois = _vivo(), _vivo(2)
    assert (um.escolhido, um.acesos) == (1, frozenset({"gatilho"}))
    assert (dois.escolhido, dois.acesos) == (2, frozenset({"luz"}))
    assert [c.colorway for c in um.controles] == ["starlight-blue", "white"]
    assert um.canais == ("haptica", "gatilho", "luz", "som"), "a faixa segue a ordem dos canais"
    lugar = cv.lugar_html(dois)
    assert 'data-acesos="luz"' in lugar and "--z-casca:" in lugar
    assert cv.lugar_html(cv.Vivo()).startswith('<div class="cv-lugar" data-acesos=""')


def test_a_janela_desenha_o_controle_o_clima_a_faixa_e_os_cartoes_na_ordem_das_abas() -> None:
    opcoes = [exp.OpcaoDaJanela("imersao", "forca", "Força", "deslizante", 100, grupo="Geral",
                                maximo=100),
              exp.OpcaoDaJanela("imersao", "batida", "Coração", "deslizante", 80, grupo="Efeitos",
                                maximo=100, cartao="Coração", canal="haptica"),
              exp.OpcaoDaJanela("imersao", "tipo", "Tipo", "escolha", "Batida", ("Batida", "Onda"),
                                grupo="Efeitos", cartao="Coração"),
              exp.OpcaoDaJanela("imersao", "susto", "Tato", "ligado", True, grupo="Efeitos",
                                cartao="Susto")]
    acoes = (exp.AcaoDaJanela("testar", "Testar", "Efeitos"),)
    html = exp.modificacao_miolo_html(
        "Modo imersão", opcoes, mod="imersao", agora=("controle", "nivel", "clima", "ao_vivo"),
        estado={"ligado": True, "nivel": 6}, acoes=acoes, vivo=_vivo(), abas=("Geral", "Efeitos"))
    assert html.count('class="cv-lugar"') == 1 and 'data-agora="clima"' in html
    assert 'data-gesto="controle-vivo-da-modificacao" data-v="imersao:2"' in html
    assert html.count('class="cv-mk"') == 3 and 'id="mod-ao-vivo"' in html
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
