"""O rascunho da janela da extensão se vê no Guardar, e o Esc não o perde calado.

O-RASCUNHO-DA-JANELA-DA-EXTENSAO-SE-VE-NO-GUARDAR-01 (26/10/2026). O Guardar fica apagado sem
rascunho e aceso com ele, num pedaço próprio da pintura; com rascunho, o primeiro X, Cancelar ou Esc
só troca o Cancelar por «Descartar» e a janela fica, e o segundo descarta. O que age na hora (o
Testar) não acende o Guardar. Vale para toda extensão: a regra mora no gerador e no gesto.

MORDIDAS (26/10/2026, executadas sobre a cura e devolvidas):

- o Guardar sempre aceso (``_o_rodape`` com ``aceso`` fixo) reprova
  ``test_o_guardar_acende_com_o_rascunho_e_apaga_sem_ele``, o cartão único e a leitura do WebKit;
- o Esc que fecha direto (``cancelar_modificacao`` sem o armar do «Descartar») reprova
  ``test_com_rascunho_o_primeiro_cancelar_arma_e_o_segundo_descarta`` e o WebKit;
- o X com ``href`` mesmo com rascunho (``_href_do_fecho`` sempre ``href="#"``) reprova o
  cancelar, o cartão único e o WebKit, em que o primeiro Esc fecha a janela;
- a comparação com o guardado arrancada (``pendente`` = rascunho não vazio) reprova a volta ao
  valor guardado, que deixaria o Guardar aceso sem nada a gravar;
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


def test_o_guardar_acende_com_o_rascunho_e_apaga_sem_ele(janela: Any, ctx: Any) -> None:  # noqa: F811
    a07, _instalar, _abrir = janela
    html = montada(janela, VIVO)
    ponte = _Ponte(VIVO)
    assert _guardar(_rodape({"#mod-janela": html})) == "apagado"
    mudou = _blocos(a07.guardar_opcao_da_modificacao(ctx, TOQUES, ponte))
    assert mudou["#mod-janela"] == html, "acender o Guardar repintou a janela inteira"
    assert _guardar(_rodape(mudou)) == "aceso", mudou.keys()
    voltou = _blocos(a07.guardar_opcao_da_modificacao(ctx, TOQUES, ponte))
    assert _guardar(_rodape(voltou)) == "apagado", "o valor de volta ao guardado não é rascunho"
    a07.guardar_opcao_da_modificacao(ctx, TOQUES, ponte)
    antes = _guardado(a07)
    gravou = _blocos(a07.guardar_modificacao(ctx, {"v": MOD}, ponte))
    assert _guardar(_rodape(gravou)) == "apagado" and _guardado(a07) != antes
    alvo = re.search(rf'data-gesto="acao-da-modificacao" data-v="({MOD}:testar:[^"]+)"', html)
    assert alvo, "a janela da Lovense não tem o Testar"
    testou = _blocos(a07.acao_da_modificacao(ctx, {"v": alvo.group(1)}, ponte))
    assert [c for c in ponte.chamadas if c[0] == "mods.acao"], "o Testar não foi à extensão"
    assert _guardar(_rodape(testou)) == "apagado", "o Testar acendeu o Guardar"


def test_com_rascunho_o_primeiro_cancelar_arma_e_o_segundo_descarta(
        janela: Any, ctx: Any) -> None:  # noqa: F811
    a07, _instalar, _abrir = janela
    html = montada(janela, VIVO)
    ponte = _Ponte(VIVO)
    sem = _rodape({"#mod-janela": html})
    assert re.search(r'<a class="btn" href="#"[^>]*>Cancelar</a>', sem), "sem rascunho fecha"
    assert 'class="tn-x" href="#"' in html
    antes = _guardado(a07)
    mudou = _blocos(a07.guardar_opcao_da_modificacao(ctx, TOQUES, ponte))
    assert 'href="#"' not in mudou["#mod-fecho"], "com rascunho o primeiro X fecha"
    assert re.search(r'<a class="btn" role="button"[^>]*>Cancelar</a>', _rodape(mudou))
    resposta = a07.cancelar_modificacao(ctx, {"v": MOD}, ponte)
    armou = _blocos(resposta)
    assert resposta.get("armou") is True, "o primeiro gesto pisca como feito"
    assert a07._MEXIDA.rascunho == {"toques": False}, "o primeiro gesto descartou"
    assert re.search(r'<a class="btn vermelho" href="#"[^>]*>Descartar</a>', _rodape(armou))
    assert 'href="#"' in armou["#mod-fecho"]
    a07.cancelar_modificacao(ctx, {"v": MOD}, ponte)
    assert a07._MEXIDA.rascunho == {} and _guardado(a07) == antes, "o descarte gravou"
    a07.guardar_opcao_da_modificacao(ctx, TOQUES, ponte)
    a07.cancelar_modificacao(ctx, {"v": MOD}, ponte)
    desarmou = _blocos(a07.guardar_opcao_da_modificacao(
        ctx, {"v": f"{MOD}:entrada_r2", "evento": "change", "valor": "Suave"}, ponte))
    assert _guardar(_rodape(desarmou)) == "aceso"
    assert "Descartar" not in _rodape(desarmou), "mudar o rascunho não desarmou o Descartar"
    de_novo = _blocos(a07.cancelar_modificacao(ctx, {"v": MOD}, ponte))
    assert "Descartar" in _rodape(de_novo) and a07._MEXIDA.rascunho, "o desarmado descartou"


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
_POUSAR = "(function(){ return window.__hef.voltouDoVoo(window.__hef.voo, null); })()"
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


def test_no_webkit_o_guardar_acende_e_o_primeiro_esc_nao_fecha(
        janela: Any, ctx: Any, pagina_fresca: pathlib.Path) -> None:  # noqa: F811
    from hefesto_dualsense4unix.interface import hefesto_vivo

    a07, _instalar, _abrir = janela
    html = montada(janela, VIVO)
    ponte = _Ponte(VIVO)
    mudou = _blocos(a07.guardar_opcao_da_modificacao(ctx, TOQUES, ponte))
    armou = _blocos(a07.cancelar_modificacao(ctx, {"v": MOD}, ponte))
    casos = {f"{w}x{h}": (w, h, [
        ["js", hefesto_vivo.BOOTSTRAP], ["js", _ABRIR % (json.dumps(ENDERECO), json.dumps(html))],
        ["espera", 0.3], ["js", _LER], ["js", _PINTAR % json.dumps(mudou)], ["espera", 0.3],
        ["js", _LER], ["js", _ESC], ["espera", 0.3], ["js", _LER],
        ["js", _POUSAR], ["js", _PINTAR % json.dumps(armou)], ["espera", 0.3], ["js", _LER],
        ["js", _ESC],
        ["espera", 0.3], ["js", _LER]]) for w, h in VISTAS}
    lidos = no_webkit(pagina_fresca, casos)
    print(json.dumps(lidos, ensure_ascii=False))
    for caso, passos in lidos.items():
        assert passos[1] == "ok", (caso, passos[1])
        vazio, aceso, um_esc, armado, dois_esc = (json.loads(passos[i]) for i in (2, 4, 6, 9, 11))
        assert vazio["guardar"]["opac"] <= 0.5 and aceso["guardar"]["opac"] == 1.0, (caso, aceso)
        assert aceso["guardar"]["fundo"] != vazio["guardar"]["fundo"], (caso, aceso["guardar"])
        assert aceso["guardar"]["borda"] == "rgb(189, 147, 249)", (caso, aceso["guardar"])
        assert vazio["x"] == aceso["x"] and aceso["x"]["w"] == 26, (caso, "o X mudou de lugar")
        assert um_esc["aberta"] is True, (caso, "o primeiro Esc fechou com rascunho", um_esc)
        assert um_esc["vistos"] == ["cancelar-modificacao"], (caso, um_esc["vistos"])
        assert armado["cancelar"] == "Descartar" and armado["aberta"], (caso, armado)
        assert armado["cor"] == "rgb(255, 85, 85)", (caso, armado["cor"])
        assert dois_esc["aberta"] is False, (caso, "o segundo Esc não fechou", dois_esc)
        assert dois_esc["vistos"] == ["cancelar-modificacao"] * 2, (caso, dois_esc["vistos"])
