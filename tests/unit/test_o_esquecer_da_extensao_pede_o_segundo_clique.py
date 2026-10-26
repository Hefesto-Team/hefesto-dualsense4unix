"""O Esquecer da janela da extensão pede o segundo clique.

O-ESQUECER-DA-JANELA-DA-EXTENSAO-PEDE-O-SEGUNDO-CLIQUE-01 (26/10/2026). Toda ação com o glifo
``esquecer``, no aparelho ou na janela, pede o segundo clique, como o «Remover»: o primeiro troca o
rótulo por «Confirmar» e não manda nada; o segundo manda; trocar de aba, fechar a janela ou outro
gesto desarma. A ação armada é do Hefesto, por aparelho, sem campo novo no manifesto.

MORDIDAS (26/10/2026, executadas sobre a cura e devolvidas):

- o desarme do ``acao_da_modificacao`` arrancado reprova os dois casos do primeiro clique e
  ``test_outra_acao_desarma``;
- o rádio da aba sem o gesto (``_radio_da_aba`` sem ``data-gesto``) reprova a leitura do WebKit;
- o primeiro clique mandando direto (``_pede_o_segundo_clique`` devolvendo falso) reprova cinco;
- o desarme do ``aba_da_modificacao`` arrancado reprova
  ``test_trocar_de_aba_fechar_ou_mexer_desarma`` e a leitura do WebKit;
- a cor da ação armada arrancada do CSS reprova a leitura do WebKit;
- o ``limpar`` (fechar a janela) sem o desarme reprova
  ``test_trocar_de_aba_fechar_ou_mexer_desarma``.
"""

from __future__ import annotations

import json
import pathlib
import re
from typing import Any

import pytest

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
    no_webkit,
    pagina_fresca,
)
from tests.unit.test_a_lista_da_janela_configurar_nao_pula_ao_clicar_um_efeito import (
    ENDERECO,
    MOD,
    VISTAS,
    pecas_da_lovense,
)

ESQUECER = {"id": "esquecer", "rotulo": "Esquecer", "icone": "esquecer"}
LIMPAR = {"id": "limpar", "rotulo": "Esquecer todos", "grupo": "Brinquedos", "icone": "esquecer"}
ACAO = "mods.acao"


def _pecas(onde: str) -> dict[str, Any]:
    pecas = pecas_da_lovense()
    geridos = pecas["aparelhos_acoes"]
    geridos = {**geridos, "acoes": [*geridos["acoes"], ESQUECER]}  # (noqa-acento)
    if onde == "coluna":
        geridos.pop("grupo")
    da_janela = [*pecas["acoes"], LIMPAR]  # (noqa-acento)
    return {**pecas, "acoes": da_janela, "aparelhos_acoes": geridos}  # (noqa-acento)


def _abrir(janela: Any, onde: str = "aba") -> tuple[Any, _Ponte, str]:  # noqa: F811
    a07, instalar, abrir = janela
    instalar(mod_id=MOD, **_pecas(onde))
    a07._MEXIDA.limpar()
    ponte = _Ponte(VIVO)
    html = str(abrir(ponte, mod_id=MOD)["blocos"]["#mod-janela"])
    ponte.chamadas.clear()
    return a07, ponte, html


def _clicar(a07: Any, ctx: Any, ponte: _Ponte, v: str) -> dict[str, Any]:  # noqa: F811
    return dict(a07.acao_da_modificacao(ctx, {"v": f"{MOD}:{v}", "evento": "click"}, ponte) or {})


def _enviadas(ponte: _Ponte) -> list[tuple[str, str]]:
    return [(c["acao"], c.get("alvo", "")) for m, c in ponte.chamadas if m == ACAO]  # (noqa-acento)


def _botao(blocos: dict[str, Any], v: str) -> str:
    """O botão no pedaço repintado; a base (``#mod-janela``) só quando nenhum pedaço o traz."""
    pedacos = [k for k in blocos if k.startswith("#mod-") and k != "#mod-janela"]
    html = "".join(str(blocos[k]) for k in [*pedacos, "#mod-janela"] if k in blocos)
    achado = re.search(rf'<button class="([^"]*)" data-gesto="acao-da-modificacao" '
                       rf'data-v="{re.escape(MOD)}:{re.escape(v)}"[^>]*>(.*?)</button>', html, re.S)
    assert achado, f"sem o botão {v}"
    return f'{achado.group(1)}|{re.sub(r"<[^>]+>", "", achado.group(2))}'


@pytest.mark.parametrize("onde", ["aba", "coluna"])
def test_o_primeiro_clique_arma_e_o_segundo_manda(janela: Any, ctx: Any,  # noqa: F811
                                                  onde: str) -> None:
    """Prova da D-2610-O-ESQUECER-PEDE-O-SEGUNDO-CLIQUE."""
    a07, ponte, _html = _abrir(janela, onde)
    primeiro = _clicar(a07, ctx, ponte, "esquecer:ap-1")
    assert _enviadas(ponte) == [], "o primeiro clique mandou o Esquecer"
    assert _botao(primeiro["blocos"], "esquecer:ap-1").endswith("armada|Confirmar")
    assert "armada" not in _botao(primeiro["blocos"], "esquecer:ap-2"), "armou outro aparelho"
    assert a07._MEXIDA.armada == (MOD, "esquecer", "ap-1")
    _clicar(a07, ctx, ponte, "esquecer:ap-1")
    assert _enviadas(ponte) == [("esquecer", "ap-1")]
    assert a07._MEXIDA.armada == ()


def test_vale_por_aparelho_e_para_a_acao_da_janela(janela: Any, ctx: Any) -> None:  # noqa: F811
    a07, ponte, html = _abrir(janela)
    assert _botao({"#mod-janela": html}, "limpar").endswith("|Esquecer todos")
    _clicar(a07, ctx, ponte, "esquecer:ap-1")
    segundo = _clicar(a07, ctx, ponte, "esquecer:ap-2")
    assert _enviadas(ponte) == [], "o Esquecer de outro aparelho mandou no primeiro clique"
    assert a07._MEXIDA.armada == (MOD, "esquecer", "ap-2")
    assert "armada" not in _botao(segundo["blocos"], "esquecer:ap-1")
    janela_ = _clicar(a07, ctx, ponte, "limpar")
    assert _enviadas(ponte) == []
    assert _botao(janela_["blocos"], "limpar").endswith("armada|Confirmar")
    _clicar(a07, ctx, ponte, "limpar")
    assert _enviadas(ponte) == [("limpar", "")]


def test_a_acao_sem_o_glifo_manda_no_primeiro(janela: Any, ctx: Any) -> None:  # noqa: F811
    a07, ponte, _html = _abrir(janela)
    _clicar(a07, ctx, ponte, "testar:ap-2")
    _clicar(a07, ctx, ponte, "parear")
    assert _enviadas(ponte) == [("testar", "ap-2"), ("parear", "")]


def test_outra_acao_desarma(janela: Any, ctx: Any) -> None:  # noqa: F811
    a07, ponte, _html = _abrir(janela)
    _clicar(a07, ctx, ponte, "esquecer:ap-1")
    depois = _clicar(a07, ctx, ponte, "testar:ap-2")
    assert _enviadas(ponte) == [("testar", "ap-2")]
    assert _botao(depois["blocos"], "esquecer:ap-1").endswith("|Esquecer")
    _clicar(a07, ctx, ponte, "esquecer:ap-1")
    assert _enviadas(ponte) == [("testar", "ap-2")], "o clique depois do desarme mandou"


def test_trocar_de_aba_fechar_ou_mexer_desarma(janela: Any, ctx: Any) -> None:  # noqa: F811
    a07, ponte, _html = _abrir(janela)
    _clicar(a07, ctx, ponte, "esquecer:ap-1")
    aba = {"v": f"{MOD}:Toques", "evento": "click"}
    assert a07.aba_da_modificacao(ctx, aba, ponte) is None
    assert a07._MEXIDA.armada, "o clique que precede o change desarmou"
    trocou = dict(a07.aba_da_modificacao(ctx, {**aba, "evento": "change"}, ponte) or {})
    assert a07._MEXIDA.armada == () and a07._MEXIDA.aba == "Toques"
    assert _botao(trocou["blocos"], "esquecer:ap-1").endswith("|Esquecer")
    for gesto_, o in (
            ("guardar_opcao_da_modificacao", {"v": f"{MOD}:toques", "evento": "click"}),
            ("cancelar_modificacao", {"v": MOD})):
        _clicar(a07, ctx, ponte, "esquecer:ap-1")
        getattr(a07, gesto_)(ctx, o, ponte)
        assert a07._MEXIDA.armada == (), f"{gesto_} não desarmou"
    _clicar(a07, ctx, ponte, "esquecer:ap-1")
    a07._MEXIDA.limpar()
    assert a07._MEXIDA.armada == ()
    assert _enviadas(ponte) == []


_ABRIR = """(function(endereco, h){
  location.hash = endereco;
  window.__hef.pintar({blocos: {'#mod-janela': h}});
  window.__trocas = [];
  document.addEventListener('change', ev => {
    const g = ev.target.closest('[data-gesto]');
    if (g) window.__trocas.push(g.dataset.gesto + ' ' + g.dataset.v);
  }, true);
  const j = document.getElementById('mod-janela');
  const rot = [...j.querySelectorAll('.mj-abas > label')]
    .find(l => l.textContent.trim() === 'Brinquedos');
  if (!rot) return 'sem a aba';
  rot.click();
  return 'ok';
})(%s, %s)"""
_PINTAR = "(function(b){ window.__hef.pintar({blocos: b}); return 'ok'; })(%s)"
_LER = """(function(){
  const b = document.querySelector('[data-v="intiface:esquecer:ap-1"]');
  const outro = document.querySelector('[data-v="intiface:esquecer:ap-2"]');
  const r = b.getBoundingClientRect(), x = r.left + r.width / 2, y = r.top + r.height / 2;
  return JSON.stringify({texto: b.textContent.trim(), outro: outro.textContent.trim(),
    cor: getComputedStyle(b).color, borda: getComputedStyle(b).borderColor,
    cabe: b.scrollWidth <= b.clientWidth + 1, alcancavel: document.elementFromPoint(x, y) === b
      || b.contains(document.elementFromPoint(x, y))});
})()"""
_TROCAR = """(function(){
  const j = document.getElementById('mod-janela');
  [...j.querySelectorAll('.mj-abas > label')].find(l => l.textContent.trim() === 'Toques').click();
  return JSON.stringify(window.__trocas);
})()"""


def test_no_webkit_o_armado_diz_confirmar_e_a_aba_avisa(
        janela: Any, ctx: Any, pagina_fresca: pathlib.Path) -> None:  # noqa: F811
    from hefesto_dualsense4unix.interface import hefesto_vivo

    a07, ponte, html = _abrir(janela)
    armado = {k: str(v) for k, v in _clicar(a07, ctx, ponte, "esquecer:ap-1")["blocos"].items()
              if k.startswith("#mod-") and k != "#mod-janela"}
    trocou = dict(a07.aba_da_modificacao(
        ctx, {"v": f"{MOD}:Toques", "evento": "change"}, ponte) or {})
    desarmado = {k: str(v) for k, v in trocou["blocos"].items()
                 if k.startswith("#mod-") and k != "#mod-janela"}
    assert "Confirmar" in "".join(armado.values())
    assert "Confirmar" not in "".join(desarmado.values())
    casos = {f"{w}x{h}": (w, h, [
        ["js", hefesto_vivo.BOOTSTRAP], ["js", _ABRIR % (json.dumps(ENDERECO), json.dumps(html))],
        ["espera", 0.3], ["js", _LER], ["js", _PINTAR % json.dumps(armado)], ["espera", 0.2],
        ["js", _LER], ["js", _TROCAR], ["js", _PINTAR % json.dumps(desarmado)], ["espera", 0.2],
        ["js", _LER]]) for w, h in VISTAS}
    lidos = no_webkit(pagina_fresca, casos)
    print(json.dumps(lidos, ensure_ascii=False))
    for caso, (_, abriu, antes, _p, armada, trocas, _p2, depois) in lidos.items():
        assert abriu == "ok", (caso, abriu)
        antes, armada, depois = json.loads(antes), json.loads(armada), json.loads(depois)
        assert antes["texto"] == "Esquecer" and depois["texto"] == "Esquecer", (caso, depois)
        assert armada["texto"] == "Confirmar" and armada["outro"] == "Esquecer", (caso, armada)
        assert armada["cor"] != antes["cor"] and armada["borda"] != antes["borda"], (caso, armada)
        assert armada["cabe"] and armada["alcancavel"], (caso, armada)
        assert f"aba-da-modificacao {MOD}:Toques" in json.loads(trocas), (caso, trocas)
