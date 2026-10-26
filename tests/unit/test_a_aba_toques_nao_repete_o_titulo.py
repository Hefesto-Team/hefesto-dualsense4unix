"""A aba Toques não repete o título Toques.

A-ABA-TOQUES-NAO-REPETE-O-TITULO-TOQUES-01 (26/10/2026, D-2610-A-CHAVE-DO-GRUPO-E-A-BOLINHA-DA-ABA).
A opção ``ligado`` de rótulo igual ao nome do grupo é a chave da aba: sai da lista e vira a
bolinha do rótulo da aba (verde ligada, cinza desligada), e a aba desligada fica com as linhas
apagadas e ainda mexíveis. Vale para toda extensão e para o cartão único (menos de dois grupos).

MORDIDAS (26/10/2026, executadas sobre a cura e devolvidas):

- a chave de volta à lista (``chave_da_aba`` devolvendo os itens inteiros) reprova
  ``test_nenhuma_linha_repete_o_nome_da_aba``,
  ``test_vale_para_toda_extensao_e_para_o_cartao_unico`` e
  ``test_no_webkit_a_aba_tem_a_bolinha_e_apaga_as_linhas``;
- a classe ``apagada`` arrancada de ``_linhas_da_aba`` reprova
  ``test_a_chave_desligada_apaga_as_linhas_da_aba`` e a leitura do WebKit;
- a regra ``.mj-da-chave.apagada`` arrancada do CSS reprova a opacidade lida no WebKit;
- a regra do rótulo apagado (``label:has(.mj-bolinha:not(.on))``) arrancada reprova a mesma leitura.
- o ponto de volta ao próprio ``i`` (sem o ``::before``) fica com 24 px de altura, puxado pelo
  ``[data-gesto] { min-height:24px }``, e reprova a leitura da bolinha redonda.
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


def _rotulos_das_linhas(tela: str) -> list[str]:
    return [re.sub(r"<[^>]+>", "", r).strip()
            for r in re.findall(r'class="ky-rot"><span>(.*?)</span>', tela)] if tela else []


def _telas(html: str) -> dict[str, str]:
    nomes = re.findall(r'<label for="mj-aba-\d+">([^<]*)', html)
    corpos = re.split(r'<div class="mj-tela" id="mod-tela-\d+">', html)[1:]
    return dict(zip(nomes, corpos, strict=True))


def test_nenhuma_linha_repete_o_nome_da_aba(janela: Any) -> None:  # noqa: F811
    html = montada(janela, VIVO)
    telas = _telas(html)
    assert "Toques" in telas, list(telas)
    for nome, corpo in telas.items():
        corpo = corpo.split('<input type="radio"')[0]
        assert nome not in _rotulos_das_linhas(corpo), f"a aba {nome} repete o título numa linha"
    assert 'id="mod-op-toques"' not in html
    rotulo = re.search(r'<label for="mj-aba-\d+">Toques(.*?)</label>', html, re.S)
    assert rotulo and 'data-v="intiface:toques"' in rotulo.group(1), "a chave não está na aba"
    assert 'class="mj-bolinha on"' in rotulo.group(1)


def test_a_chave_desligada_apaga_as_linhas_da_aba(janela: Any, ctx: Any) -> None:  # noqa: F811
    a07, _instalar, _abrir = janela
    html = montada(janela, VIVO)
    ponte = _Ponte(VIVO)
    resposta = dict(a07.guardar_opcao_da_modificacao(
        ctx, {"v": f"{MOD}:toques", "evento": "click"}, ponte) or {})
    blocos = {k: str(v) for k, v in resposta.get("blocos", {}).items() if k.startswith("#mod-")}
    tudo = "".join(v for k, v in blocos.items() if k != "#mod-janela")
    assert blocos.get("#mod-janela") == html, "o clique na bolinha repintou a janela inteira"
    assert re.search(r'class="mj-bolinha"[^>]*aria-checked="false"', tudo), blocos.keys()
    assert re.search(r'class="mj-da-chave apagada" id="mod-da-chave-\d+"', tudo), blocos.keys()
    assert a07._MEXIDA.rascunho == {"toques": False}
    assert "<select" in tudo and "disabled" not in tudo, "a aba apagada continua mexível"
    de_volta = dict(a07.guardar_opcao_da_modificacao(
        ctx, {"v": f"{MOD}:toques", "evento": "click"}, ponte) or {})
    assert "mj-bolinha on" in "".join(str(v) for v in de_volta.get("blocos", {}).values())


def test_vale_para_toda_extensao_e_para_o_cartao_unico() -> None:
    from hefesto_dualsense4unix.interface import desenho_da_experimental as exp

    op = exp.OpcaoDaJanela
    opcoes = [op("x", "som", "Som", "ligado", False, grupo="Som"),
              op("x", "alto", "Alto", "ligado", True, grupo="Som"),
              op("x", "volume", "Volume", "deslizante", 40, grupo="Som", maximo=100)]
    html = exp.modificacao_miolo_html("X", opcoes, mod="x")
    assert 'id="mod-op-som"' not in html and 'id="mod-op-alto"' in html
    titulo = re.search(r'<span class="ac-tit">Som(.*?)</span></div>', html, re.S)
    assert titulo and 'data-v="x:som"' in titulo.group(1)
    assert 'aria-checked="false"' in titulo.group(1)
    assert 'class="mj-da-chave apagada"' in html
    duas = exp.modificacao_miolo_html(
        "X", [*opcoes, op("x", "luz", "Luz", "ligado", True, grupo="Luz"),
              op("x", "cor", "Cor", "escolha", "A", escolhas=("A", "B"), grupo="Luz")], mod="x",
        agora=("conexoes",))  # (noqa-acento)
    telas = _telas(duas)
    assert set(telas) == {"Som", "Luz"}
    assert 'id="mod-op-luz"' not in duas and 'class="mj-da-chave" id="mod-da-chave-1"' in duas
    sem_chave = exp.modificacao_miolo_html(
        "X", [op("x", "a", "Ligar o som", "ligado", True, grupo="Som")], mod="x")
    assert 'id="mod-op-a"' in sem_chave and "mj-bolinha" not in sem_chave


_ABRIR = """(function(endereco, h){
  location.hash = endereco;
  window.__hef.pintar({blocos: {'#mod-janela': h}});
  const j = document.getElementById('mod-janela');
  const rot = [...j.querySelectorAll('.mj-abas > label')].find(l => l.textContent === 'Toques');
  if (!rot) return 'sem a aba';
  rot.click();
  return 'ok';
})(%s, %s)"""
_PINTAR = "(function(b){ window.__hef.pintar({blocos: b}); return 'ok'; })(%s)"
_LER = """(function(){
  const j = document.getElementById('mod-janela');
  const tela = [...j.querySelectorAll('.mj-abas > .mj-tela')]
    .find(t => getComputedStyle(t).visibility === 'visible');
  const rot = j.querySelector('.mj-abas > input:checked + label');
  const b = rot.querySelector('.mj-bolinha'), lista = tela.querySelector('.tq-lista');
  const ponto = b ? getComputedStyle(b, '::before') : null;
  const nomes = [...j.querySelectorAll('.mj-abas > label')].map(l => l.textContent.trim());
  const linhas = [...j.querySelectorAll('.mj-tela .ky-rot span')].map(s => s.textContent.trim());
  const sel = tela.querySelector('select');
  return JSON.stringify({aba: rot.textContent, rotulo: getComputedStyle(rot).opacity,
    cor: ponto ? ponto.backgroundColor : null,
    largura: ponto ? parseFloat(ponto.width) : 0, altura: ponto ? parseFloat(ponto.height) : 0,
    alvo: b ? b.getBoundingClientRect().height : 0,
    dentro: b ? rot.contains(b) : false,
    opac: lista ? getComputedStyle(lista.closest('.mj-da-chave') || lista).opacity : null,
    repete: linhas.filter(r => nomes.includes(r)), mexivel: sel ? !sel.disabled : null});
})()"""


def test_no_webkit_a_aba_tem_a_bolinha_e_apaga_as_linhas(
        janela: Any, ctx: Any, pagina_fresca: pathlib.Path) -> None:  # noqa: F811
    from hefesto_dualsense4unix.interface import hefesto_vivo

    a07, _instalar, _abrir = janela
    html = montada(janela, VIVO)
    resposta = dict(a07.guardar_opcao_da_modificacao(
        ctx, {"v": f"{MOD}:toques", "evento": "click"}, _Ponte(VIVO)) or {})
    blocos = {k: str(v) for k, v in resposta.get("blocos", {}).items() if k.startswith("#mod-")}
    casos = {f"{w}x{h}": (w, h, [
        ["js", hefesto_vivo.BOOTSTRAP], ["js", _ABRIR % (json.dumps(ENDERECO), json.dumps(html))],
        ["espera", 0.3], ["js", _LER], ["js", _PINTAR % json.dumps(blocos)], ["espera", 0.3],
        ["js", _LER]]) for w, h in VISTAS}
    lidos = no_webkit(pagina_fresca, casos)
    print(json.dumps(lidos, ensure_ascii=False))
    for caso, (_, abriu, ligada, _p, desligada) in lidos.items():
        assert abriu == "ok", (caso, abriu)
        ligada, desligada = json.loads(ligada), json.loads(desligada)
        assert ligada["aba"] == "Toques" and ligada["dentro"], (caso, ligada)
        assert ligada["largura"] >= 6, (caso, ligada)
        assert ligada["largura"] == ligada["altura"] == 8, (caso, "a bolinha não é redonda", ligada)
        assert ligada["alvo"] >= 24, (caso, "o alvo do clique encolheu", ligada)
        assert ligada["repete"] == [] and desligada["repete"] == [], (caso, ligada["repete"])
        assert ligada["cor"] == "rgb(80, 250, 123)", (caso, ligada["cor"])
        assert desligada["cor"] != ligada["cor"], (caso, desligada["cor"])
        assert float(ligada["opac"]) == 1.0 and float(desligada["opac"]) <= 0.55, (caso, desligada)
        assert desligada["mexivel"] is True, caso
        assert float(ligada["rotulo"]) == 1.0, (caso, ligada)
        assert float(desligada["rotulo"]) < 1.0, (caso, desligada)
