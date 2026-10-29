"""A escolha da janela da extensão grava na hora: o Guardar segue apagado e o Esc fecha.

O-RASCUNHO-DA-JANELA-DA-EXTENSAO-SE-VE-NO-GUARDAR-01 (26/10/2026) acendia o Guardar com rascunho e
armava o «Descartar» no primeiro X, Cancelar ou Esc. Desde 28/10/2026
(A-ESCOLHA-DA-JANELA-DA-EXTENSAO-GRAVA-NA-HORA-01, D-2810-TODA-ESCOLHA-DA-JANELA-DA-EXTENSAO-GRAVA-
NA-HORA) cada escolha grava no gesto: não há rascunho a esperar, o Guardar fica apagado e o primeiro
X, Cancelar ou Esc fecha. O gerador ainda sabe pintar o Guardar aceso e o «Descartar» (o cartão
único, abaixo), para quem um dia tiver rascunho de verdade.

MORDIDAS (28/10/2026, executadas sobre a cura e devolvidas):

- o ``_guardar_a_opcao_da_modificacao`` tirado do ``guardar_opcao_da_modificacao`` reprova
  ``test_a_escolha_grava_na_hora_e_o_guardar_segue_apagado`` e
  ``test_depois_da_escolha_o_primeiro_cancelar_fecha``;
- o Guardar sempre aceso (``_o_rodape`` com ``aceso`` fixo) reprova o cartão único e a leitura do
  WebKit;
- a regra ``.btn.roxo.apagado`` arrancada do CSS reprova a opacidade lida no WebKit.
"""

from __future__ import annotations

import json
import pathlib
import re
from typing import Any

from tests.unit.test_a_aba_lancadores_ganha_as_modificacoes import (  # noqa: F401
    ctx,
    lar,
)
from tests.unit.test_a_janela_da_extensao_age_e_gere_os_aparelhos import (  # noqa: F401
    VIVO,
    _Ponte,
    janela,
)
from tests.unit.test_a_linha_sem_aparelho_fica_a_direita_do_parear import (  # noqa: F401
    montada,
    no_webkit,
    pagina_fresca,
)
from tests.unit.test_a_lista_da_janela_configurar_nao_pula_ao_clicar_um_efeito import (
    ENDERECO,
    MOD,
    VISTAS,
)

TOQUES = {"v": f"{MOD}:toques", "evento": "click"}


def _blocos(resposta: Any) -> dict[str, str]:
    return {k: str(v) for k, v in dict(resposta or {}).get("blocos", {}).items()
            if k.startswith("#mod-")}


def _rodape(blocos: dict[str, str]) -> str:
    if "#mod-rodape" in blocos:
        return blocos["#mod-rodape"]
    achado = re.search(r'id="mod-rodape">(.*?)</div>', blocos["#mod-janela"], re.S)
    assert achado, "a janela não tem o rodapé em pedaço próprio"
    return achado.group(1)


def _guardar(rodape: str) -> str:
    achado = re.search(r'<a class="btn roxo([^"]*)"[^>]*>Guardar</a>', rodape)
    assert achado, rodape
    return achado.group(1).strip()


def _guardado(a07: Any) -> bytes | None:
    from hefesto_dualsense4unix.mods import opcoes

    arquivo = opcoes.caminho(MOD, a07._lugares())
    return arquivo.read_bytes() if arquivo.exists() else None


def test_a_escolha_grava_na_hora_e_o_guardar_segue_apagado(janela: Any, ctx: Any) -> None:  # noqa: F811
    a07, _instalar, _abrir = janela
    html = montada(janela, VIVO)
    ponte = _Ponte(VIVO)
    assert _guardar(_rodape({"#mod-janela": html})) == "apagado"
    antes = _guardado(a07)
    mudou = _blocos(a07.guardar_opcao_da_modificacao(ctx, TOQUES, ponte))
    assert mudou["#mod-janela"] == html, "a escolha repintou a janela inteira"
    assert _guardado(a07) != antes, "a escolha esperou o Guardar"
    assert _guardar(_rodape(mudou)) == "apagado", "a escolha gravada deixou o Guardar aceso"
    assert a07._MEXIDA.rascunho == {}, "a escolha ficou no rascunho"
    voltou = _blocos(a07.guardar_opcao_da_modificacao(ctx, TOQUES, ponte))
    assert _guardar(_rodape(voltou)) == "apagado" and _guardado(a07) != antes
    alvo = re.search(rf'data-gesto="acao-da-modificacao" data-v="({MOD}:testar:[^"]+)"', html)
    assert alvo, "a janela da Lovense não tem o Testar"
    testou = _blocos(a07.acao_da_modificacao(ctx, {"v": alvo.group(1)}, ponte))
    assert [c for c in ponte.chamadas if c[0] == "mods.acao"], "o Testar não foi à extensão"
    assert _guardar(_rodape(testou)) == "apagado", "o Testar acendeu o Guardar"


def test_depois_da_escolha_o_primeiro_cancelar_fecha(janela: Any, ctx: Any) -> None:  # noqa: F811
    a07, _instalar, _abrir = janela
    html = montada(janela, VIVO)
    ponte = _Ponte(VIVO)
    assert 'class="tn-x" href="#"' in html
    mudou = _blocos(a07.guardar_opcao_da_modificacao(ctx, TOQUES, ponte))
    gravado = _guardado(a07)
    assert 'href="#"' in mudou.get("#mod-fecho", 'href="#"'), "o X deixou de fechar"
    assert re.search(r'<a class="btn" href="#"[^>]*>Cancelar</a>', _rodape(mudou))
    resposta = a07.cancelar_modificacao(ctx, {"v": MOD}, ponte)
    assert resposta.get("armou") is not True, "o Cancelar armou um Descartar sem nada a descartar"
    assert "Descartar" not in _rodape(_blocos(resposta) or {"#mod-janela": html})
    assert _guardado(a07) == gravado, "o Cancelar desfez a escolha já gravada"


def test_vale_para_toda_extensao_e_para_o_cartao_unico() -> None:
    from hefesto_dualsense4unix.interface import desenho_da_experimental as exp

    opcoes = [exp.OpcaoDaJanela("x", "som", "Som", "ligado", True)]
    for agora in ((), ("conexoes",)):  # (noqa-acento)
        vazio = exp.modificacao_miolo_html("X", opcoes, mod="x", agora=agora)
        cheio = exp.modificacao_miolo_html("X", opcoes, mod="x", agora=agora,
                                           rascunho=exp.Rascunho(True))
        armado = exp.modificacao_miolo_html("X", opcoes, mod="x", agora=agora,
                                            rascunho=exp.Rascunho(True, True))
        assert _guardar(_rodape({"#mod-janela": vazio})) == "apagado", agora
        assert _guardar(_rodape({"#mod-janela": cheio})) == "aceso", agora
        assert 'id="mod-fecho"><a class="tn-x" role="button"' in cheio, agora
        assert f">{exp.DESCARTAR}</a>" in armado
        assert "Cancelar" not in _rodape({"#mod-janela": armado})
    desenho = exp.modificacao_miolo_html("X", opcoes)
    assert 'id="mod-rodape"' not in desenho and 'class="tn-x" href="#"' in desenho


_ABRIR = """(function(endereco, h){
  location.hash = endereco;
  window.__hef.pintar({blocos: {'#mod-janela': h}});
  window.__vistos = [];
  document.addEventListener('click', e => {
    const g = e.target.closest && e.target.closest('[data-gesto]');
    if (g) window.__vistos.push(g.dataset.gesto); }, true);
  return 'ok';
})(%s, %s)"""
_PINTAR = "(function(b){ window.__hef.pintar({blocos: b}); return 'ok'; })(%s)"
_ESC = """(function(){
  document.dispatchEvent(new KeyboardEvent('keydown', {key: 'Escape', bubbles: true}));
  return 'esc';
})()"""
_LER = """(function(){
  const j = document.getElementById('mod-janela');
  const tela = j.closest('.tela-nova');
  const g = j.querySelector('.tn-rod [data-gesto="guardar-modificacao"]');
  const c = [...j.querySelectorAll('.tn-rod .btn')].find(b => b !== g);
  const x = j.querySelector('.tn-topo .tn-x'), cg = getComputedStyle(g);
  const cx = x.getBoundingClientRect();
  const tit = j.querySelector('.tn-topo .tn-tit').getBoundingClientRect();
  return JSON.stringify({aberta: getComputedStyle(tela).display !== 'none',
    guardar: {opac: parseFloat(cg.opacity), fundo: cg.backgroundColor, borda: cg.borderTopColor},
    cancelar: c.textContent.trim(), cor: getComputedStyle(c).color,
    x: {w: cx.width, d: Math.round(cx.right), topo: Math.round(cx.top), tit: Math.round(tit.top)},
    vistos: window.__vistos.slice()});
})()"""


def test_no_webkit_a_escolha_deixa_o_guardar_apagado_e_o_primeiro_esc_fecha(
        janela: Any, ctx: Any, pagina_fresca: pathlib.Path) -> None:  # noqa: F811
    from hefesto_dualsense4unix.interface import hefesto_vivo

    a07, _instalar, _abrir = janela
    html = montada(janela, VIVO)
    ponte = _Ponte(VIVO)
    mudou = _blocos(a07.guardar_opcao_da_modificacao(ctx, TOQUES, ponte))
    casos = {f"{w}x{h}": (w, h, [
        ["js", hefesto_vivo.BOOTSTRAP], ["js", _ABRIR % (json.dumps(ENDERECO), json.dumps(html))],
        ["espera", 0.3], ["js", _LER], ["js", _PINTAR % json.dumps(mudou)], ["espera", 0.3],
        ["js", _LER], ["js", _ESC], ["espera", 0.3], ["js", _LER]]) for w, h in VISTAS}
    lidos = no_webkit(pagina_fresca, casos)
    print(json.dumps(lidos, ensure_ascii=False))
    for caso, passos in lidos.items():
        assert passos[1] == "ok", (caso, passos[1])
        vazio, mudado, um_esc = (json.loads(passos[i]) for i in (2, 4, 6))
        assert vazio["guardar"]["opac"] <= 0.5, (caso, vazio)
        assert mudado["guardar"] == vazio["guardar"], (caso, "a escolha acendeu o Guardar")
        assert mudado["cancelar"] == "Cancelar" and mudado["aberta"], (caso, mudado)
        assert vazio["x"] == mudado["x"] and mudado["x"]["w"] == 26, (caso, "o X mudou de lugar")
        assert um_esc["aberta"] is False, (caso, "o primeiro Esc não fechou", um_esc)
        assert um_esc["vistos"] == ["cancelar-modificacao"], (caso, um_esc["vistos"])
