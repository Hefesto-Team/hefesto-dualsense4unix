"""A escolha da janela da extensão grava na hora, e a janela fecha pelo X, sem Guardar.

O-RASCUNHO-DA-JANELA-DA-EXTENSAO-SE-VE-NO-GUARDAR-01 (26/10/2026) acendia o Guardar com rascunho e
armava o «Descartar» no primeiro X, Cancelar ou Esc. Desde 28/10/2026
(D-2810-TODA-ESCOLHA-DA-JANELA-DA-EXTENSAO-GRAVA-NA-HORA) cada escolha grava no gesto, e o rodapé
de Cancelar e Guardar saiu com o rascunho: o X (e o Esc, que o clica) fecha no primeiro gesto.

MORDIDAS (28/10/2026, executadas sobre a cura e devolvidas):

- o ``_guardar_a_opcao_da_modificacao`` tirado do ``guardar_opcao_da_modificacao`` reprova
  ``test_a_escolha_grava_na_hora_e_a_janela_nao_tem_guardar`` e
  ``test_depois_da_escolha_o_x_fecha_sem_desfazer``;
- o rodapé de volta no ``modificacao_miolo_html`` reprova o cartão único e a leitura do WebKit.
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


def _sem_rodape(html: str) -> None:
    assert 'id="mod-rodape"' not in html and "tn-rod" not in html, "a janela tem rodapé"
    assert ">Guardar</a>" not in html and ">Cancelar</a>" not in html, "o Guardar voltou"
    assert "guardar-modificacao" not in html


def _guardado(a07: Any) -> bytes | None:
    from hefesto_dualsense4unix.mods import opcoes

    arquivo = opcoes.caminho(MOD, a07._lugares())
    return arquivo.read_bytes() if arquivo.exists() else None


def test_a_escolha_grava_na_hora_e_a_janela_nao_tem_guardar(janela: Any, ctx: Any) -> None:  # noqa: F811
    a07, _instalar, _abrir = janela
    html = montada(janela, VIVO)
    ponte = _Ponte(VIVO)
    _sem_rodape(html)
    antes = _guardado(a07)
    mudou = _blocos(a07.guardar_opcao_da_modificacao(ctx, TOQUES, ponte))
    assert mudou["#mod-janela"] == html, "a escolha repintou a janela inteira"
    assert _guardado(a07) != antes, "a escolha não gravou na hora"
    assert not hasattr(a07._MEXIDA, "rascunho"), "o rascunho voltou"
    alvo = re.search(rf'data-gesto="acao-da-modificacao" data-v="({MOD}:testar:[^"]+)"', html)
    assert alvo, "a janela da Lovense não tem o Testar"
    testou = _blocos(a07.acao_da_modificacao(ctx, {"v": alvo.group(1)}, ponte))
    assert [c for c in ponte.chamadas if c[0] == "mods.acao"], "o Testar não foi à extensão"
    for pintado in testou.values():
        _sem_rodape(pintado)


def test_depois_da_escolha_o_x_fecha_sem_desfazer(janela: Any, ctx: Any) -> None:  # noqa: F811
    a07, _instalar, _abrir = janela
    html = montada(janela, VIVO)
    ponte = _Ponte(VIVO)
    assert 'class="tn-x" href="#"' in html
    mudou = _blocos(a07.guardar_opcao_da_modificacao(ctx, TOQUES, ponte))
    gravado = _guardado(a07)
    assert 'href="#"' in mudou.get("#mod-fecho", 'href="#"'), "o X deixou de fechar"
    resposta = a07.cancelar_modificacao(ctx, {"v": MOD}, ponte)
    assert "armou" not in resposta, "o X armou um Descartar"
    assert _guardado(a07) == gravado, "o X desfez a escolha já gravada"


def test_vale_para_toda_extensao_e_para_o_cartao_unico() -> None:
    from hefesto_dualsense4unix.interface import desenho_da_experimental as exp

    opcoes = [exp.OpcaoDaJanela("x", "som", "Som", "ligado", True)]
    for agora in ((), ("conexoes",)):  # (noqa-acento)
        html = exp.modificacao_miolo_html("X", opcoes, mod="x", agora=agora)
        _sem_rodape(html)
        assert 'id="mod-fecho"><a class="tn-x" href="#"' in html, agora
    desenho = exp.modificacao_miolo_html("X", opcoes)
    _sem_rodape(desenho)
    assert 'class="tn-x" href="#"' in desenho


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
  const x = j.querySelector('.tn-topo .tn-x');
  const cx = x.getBoundingClientRect();
  const tit = j.querySelector('.tn-topo .tn-tit').getBoundingClientRect();
  return JSON.stringify({aberta: getComputedStyle(tela).display !== 'none',
    rodape: j.querySelectorAll('.tn-rod, [data-gesto="guardar-modificacao"]').length,
    x: {w: cx.width, d: Math.round(cx.right), topo: Math.round(cx.top), tit: Math.round(tit.top)},
    vistos: window.__vistos.slice()});
})()"""


def test_no_webkit_a_escolha_deixa_a_janela_aberta_e_o_primeiro_esc_fecha(
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
        assert vazio["rodape"] == mudado["rodape"] == 0, (caso, "a janela tem rodapé")
        assert mudado["aberta"], (caso, "a escolha fechou a janela")
        assert vazio["x"] == mudado["x"] and mudado["x"]["w"] == 26, (caso, "o X mudou de lugar")
        assert um_esc["aberta"] is False, (caso, "o primeiro Esc não fechou", um_esc)
        assert um_esc["vistos"] == ["cancelar-modificacao"], (caso, um_esc["vistos"])
