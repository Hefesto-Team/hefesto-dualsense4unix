"""O efeito «Direto» e «Suave» tem o desenho da onda.

O-EFEITO-DIRETO-E-SUAVE-TEM-O-DESENHO-DA-ONDA-01 (26/10/2026). Nas linhas das entradas contínuas
(L2, R2, os analógicos, o touchpad, o Sacudir, o Inclinar) o lugar do desenho do efeito ficava
vazio com «Direto» e «Suave». Agora cada valor que o seletor oferece tem o seu desenho, no mesmo
lugar e no mesmo traço da onda dos toques: o pontilhado do «Nenhum», a rampa reta do «Direto» e a
curva ao quadrado do «Suave», que é como a extensão o aplica. O desenho vem no pedaço da própria
linha, sem repintar a lista.

MORDIDAS (26/10/2026, executadas sobre a cura e devolvidas): a onda tirada da
``_linha_da_entrada`` (o estado de antes) reprova quatro testes e quebra a fixture do WebKit; a
curva do «Suave» igual à rampa reprova o desenho próprio de cada valor e a curva ao quadrado; o
tamanho do desenho mudado reprova o lugar vazio e a geometria no WebKit; o «Nenhum» sem o pontilhado
reprova o desenho próprio e a geometria.
"""

from __future__ import annotations

import itertools
import json
import re
from typing import Any

import pytest

from hefesto_dualsense4unix.interface import desenho_da_experimental as exp
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
    SEM_APARELHOS,
    montada,
    no_webkit,
    pagina_fresca,
)
from tests.unit.test_a_lista_da_janela_configurar_nao_pula_ao_clicar_um_efeito import (
    ENDERECO,
    ENTRADAS,
    MOD,
    VISTAS,
    pecas_da_lovense,
)

VALORES = ("Nenhum", "Direto", "Suave")


def linha(id_: str, rotulo: str, valor: str, escolhas: tuple[str, ...] = VALORES) -> str:
    o = exp.OpcaoDaJanela(MOD, id_, rotulo, "escolha", valor, escolhas, "Toques")
    return exp._linha_da_entrada(o)


def onda_de(html: str) -> str:
    achado = re.search(r'<svg class="onda".*?</svg>', html, re.S)
    assert achado is not None, f"a linha não tem o desenho do efeito: {html[:200]}"
    return achado.group(0)


def test_cada_valor_do_seletor_tem_um_desenho_proprio() -> None:
    for id_, rotulo in ENTRADAS:
        ondas = {v: onda_de(linha(id_, rotulo, v)) for v in VALORES}
        assert 'class="onda-zero"' in ondas["Nenhum"], id_
        assert ondas["Direto"].count("<rect") >= 6, id_
        assert ondas["Suave"].count("<rect") >= 6, id_
        assert len(set(ondas.values())) == 3, f"{id_}: dois valores com o mesmo desenho"


def test_o_direto_sobe_em_reta_e_o_suave_ao_quadrado() -> None:
    def alturas(valor: str) -> list[float]:
        return [float(h) for h in re.findall(r'height="([\d.]+)" rx', onda_de(
            linha("entrada_l2", "Gatilho esquerdo (L2)", valor)))]

    reta, curva = alturas("Direto"), alturas("Suave")
    assert len(reta) == len(curva) >= 6
    passos = [b - a for a, b in itertools.pairwise(reta)]
    assert max(passos) - min(passos) < 0.3, f"o Direto não sobe em reta: {reta}"
    assert reta == sorted(reta) and curva == sorted(curva)
    assert abs(curva[-1] - reta[-1]) < 0.3, (reta, curva)
    assert all(c < r for c, r in zip(curva[1:-1], reta[1:-1], strict=True)), (
        f"o Suave não começa leve (a extensão o aplica ao quadrado): {reta} contra {curva}")
    meio = len(reta) // 2
    assert curva[meio] < reta[meio] * 0.6, (reta, curva)


def test_valor_sem_desenho_deixa_o_lugar_vazio_do_mesmo_tamanho() -> None:
    vazia = onda_de(linha("entrada_l2", "Gatilho esquerdo (L2)", "Pulso",
                          (*VALORES, "Pulso")))
    assert "<rect" not in vazia and "<line" not in vazia
    assert 'width="52" height="14"' in vazia


def test_o_desenho_vem_no_pedaco_da_linha_e_nao_repinta_a_lista(
        janela: Any, ctx: Any) -> None:  # noqa: F811
    a07, instalar, abrir = janela
    instalar(mod_id=MOD, **pecas_da_lovense())
    ponte = _Ponte(VIVO)
    abrir(ponte, mod_id=MOD)
    for valor, esperado in (("Suave", "Suave"), ("Direto", "Direto"), ("Nenhum", "Nenhum")):
        o = {"v": f"{MOD}:entrada_r2", "evento": "change", "valor": valor}
        resposta = dict(a07.guardar_opcao_da_modificacao(ctx, o, ponte) or {})
        pedaco = str(resposta["blocos"]["#mod-op-entrada_r2"])
        assert onda_de(pedaco) == onda_de(linha("entrada_r2", "Gatilho direito (R2)", esperado)), (
            valor)
        assert "<option selected>" + esperado in pedaco


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
  const r = e => { const x = e.getBoundingClientRect();
    return {x: x.left, y: x.top, d: x.right, b: x.bottom, w: x.width, h: x.height}; };
  const medir = l => { const o = l.querySelector('svg.onda'), g = l.querySelector('svg.tq-gl'),
      s = l.querySelector('select');
    const barras = [...o.querySelectorAll('rect,line')].map(e => e.getBoundingClientRect());
    return {id: l.id, linha: r(l), glifo: r(g), onda: r(o), lista: r(s), n: barras.length,
      cor: barras.length ? getComputedStyle(o.querySelector('rect,line')).fill : '',
      traco: barras.length ? getComputedStyle(o.querySelector('rect,line')).stroke : '',
      zero: !!o.querySelector('.onda-zero'),
      maior: barras.reduce((m, b) => Math.max(m, b.height), 0)}; };
  const toque = j.querySelector('.tq-lista .tql svg.onda');
  const linhas = [...j.querySelectorAll('.tql[id^="mod-op-entrada_"]')];
  return JSON.stringify({entradas: linhas.map(medir),
    toque: toque ? r(toque) : null,
    toque_cor: toque ? getComputedStyle(toque.querySelector('rect,line')).fill : ''});
})()"""


@pytest.fixture
def lidas(janela: Any, ctx: Any,  # noqa: F811
          pagina_fresca: Any,  # noqa: F811
          ) -> dict[str, list[dict[str, Any]]]:
    from hefesto_dualsense4unix.interface import hefesto_vivo

    a07, instalar, abrir = janela
    instalar(mod_id=MOD, **pecas_da_lovense())
    ponte = _Ponte(SEM_APARELHOS)
    inicial = str(abrir(ponte, mod_id=MOD)["blocos"]["#mod-janela"])
    passos: list[list[Any]] = [["js", hefesto_vivo.BOOTSTRAP],
                               ["js", _ABRIR % (json.dumps(ENDERECO), json.dumps(inicial))],
                               ["espera", 0.3], ["js", _LER]]
    for valor in ("Direto", "Suave", "Nenhum"):
        blocos = {}
        for id_, _rotulo in ENTRADAS:
            o = {"v": f"{MOD}:{id_}", "evento": "change", "valor": valor}
            resposta = dict(a07.guardar_opcao_da_modificacao(ctx, o, ponte) or {})
            blocos[f"#mod-op-{id_}"] = str(resposta["blocos"][f"#mod-op-{id_}"])
        passos += [["js", _PINTAR % json.dumps(blocos)], ["espera", 0.2], ["js", _LER]]
    lidos = no_webkit(pagina_fresca, {f"{w}x{h}": (w, h, passos) for w, h in VISTAS})
    saida = {}
    for caso, r in lidos.items():
        assert r[1] == "ok", (caso, r[1])
        saida[caso] = [json.loads(r[i]) for i in (2, 4, 6, 8)]
    print(json.dumps(saida, ensure_ascii=False))
    return saida


def test_a_onda_da_entrada_tem_o_lugar_e_o_traco_da_onda_dos_toques(
        lidas: dict[str, list[dict[str, Any]]]) -> None:
    falhas = []
    for caso, estados in lidas.items():
        for nome, estado in zip(("Nenhum", "Direto", "Suave", "Nenhum"), estados, strict=True):
            toque = estado["toque"]
            assert len(estado["entradas"]) == len(ENTRADAS), (caso, nome, estado["entradas"])
            for e in estado["entradas"]:
                tag = f"{caso} · {e['id']} · {nome}"
                if (e["onda"]["w"], e["onda"]["h"]) != (toque["w"], toque["h"]):
                    falhas.append(f"{tag}: o desenho é {e['onda']['w']:.0f}x{e['onda']['h']:.0f}, "
                                  f"o dos toques é {toque['w']:.0f}x{toque['h']:.0f}")
                if not (e["glifo"]["d"] <= e["onda"]["x"] + 0.5
                        and e["onda"]["d"] <= e["lista"]["x"] + 0.5):
                    falhas.append(f"{tag}: o desenho não fica entre o glifo e a lista")
                if abs((e["onda"]["y"] + e["onda"]["b"]) / 2
                       - (e["lista"]["y"] + e["lista"]["b"]) / 2) > 2:
                    falhas.append(f"{tag}: o desenho não está no centro da linha")
                if e["n"] == 0:
                    falhas.append(f"{tag}: sem traço")
                if not e["zero"] and e["cor"] != estado["toque_cor"]:
                    falhas.append(f"{tag}: cor {e['cor']} contra {estado['toque_cor']} nos toques")
                if e["zero"] and e["traco"] in ("", "none"):
                    falhas.append(f"{tag}: o pontilhado do Nenhum não tem traço")
    assert not falhas, "\n".join(falhas)


def test_a_linha_nao_pula_quando_o_efeito_muda(
        lidas: dict[str, list[dict[str, Any]]]) -> None:
    falhas = []
    for caso, estados in lidas.items():
        base = {e["id"]: e["linha"] for e in estados[0]["entradas"]}
        for nome, estado in zip(("Nenhum", "Direto", "Suave", "Nenhum"), estados, strict=True):
            for e in estado["entradas"]:
                for k in ("x", "y", "w", "h"):
                    if abs(e["linha"][k] - base[e["id"]][k]) > 0.5:
                        falhas.append(f"{caso} · {e['id']} · {nome}: linha.{k} "
                                      f"{base[e['id']][k]:.1f} -> {e['linha'][k]:.1f}")
        direto = {e["id"]: e["maior"] for e in estados[1]["entradas"]}
        zero = {e["id"]: e["maior"] for e in estados[0]["entradas"]}
        for id_, altura in direto.items():
            if altura <= zero[id_] + 3:
                falhas.append(f"{caso} · {id_}: o Direto não desenhou a rampa ({altura:.1f})")
    assert not falhas, "\n".join(falhas)
