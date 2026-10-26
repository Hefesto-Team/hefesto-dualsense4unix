"""As linhas da janela «Configurar» usam o glifo do mapa do controle.

AS-LINHAS-DA-JANELA-CONFIGURAR-USAM-O-GLIFO-DO-MAPA-DO-CONTROLE-01 (26/10/2026).
"""

from __future__ import annotations

import csv
import json
import os
import pathlib
import re
import subprocess
import sys
from typing import Any

import pytest

from hefesto_dualsense4unix.interface import desenho_da_experimental as exp
from hefesto_dualsense4unix.interface.desenho_da_experimental import (
    GLIFO_DA_ENTRADA,
    PREFIXO_DA_ENTRADA,
    OpcaoDaJanela,
    pedacos_da_janela,
)
from tests.unit.test_a_aba_lancadores_ganha_as_modificacoes import (  # noqa: F401
    ctx,
    lar,
)
from tests.unit.test_a_janela_da_extensao_age_e_gere_os_aparelhos import (  # noqa: F401
    VIVO,
    _Ponte,
    janela,
)
from tests.unit.test_a_lista_da_janela_configurar_nao_pula_ao_clicar_um_efeito import (
    ENDERECO,
    ENTRADAS,
    MOD,
    pecas_da_lovense,
)

RAIZ = pathlib.Path(__file__).resolve().parents[2]
DESENHO = RAIZ / "mockup" / "07-lancadores.html"
PECAS = RAIZ / "docs" / "data" / "pecas-do-dualsense.csv"
VISTAS = ((1918, 840), (1212, 809))


def _glifos_do_mapa() -> set[str]:
    linhas = [li for li in PECAS.read_text(encoding="utf-8").splitlines()
              if li and not li.startswith("#")]
    return {p["glifo"] for p in csv.DictReader(linhas)}


def _montada(janela: Any) -> str:  # noqa: F811
    _a07, instalar, abrir = janela
    instalar(mod_id=MOD, **pecas_da_lovense())
    return str(abrir(_Ponte(VIVO), mod_id=MOD)["blocos"]["#mod-janela"])


def _sem_glifo(html: str) -> list[str]:
    """As linhas de entrada do controle (``#mod-op-entrada_…``) sem o glifo do mapa, pelo nome."""
    _, pedacos = pedacos_da_janela(html)
    faltam = []
    for ident, pedaco in pedacos.items():
        chave = ident.removeprefix(f"{exp.PEDACO}op-{PREFIXO_DA_ENTRADA}")
        if chave == ident:
            continue
        uso = re.search(r'<svg class="tq-gl"[^>]*><use href="#en-([^"]+)"/></svg>', pedaco.miolo)
        if uso is None or uso.group(1) != chave or chave not in GLIFO_DA_ENTRADA:
            faltam.append(f"{PREFIXO_DA_ENTRADA}{chave}")
    return faltam


def test_toda_linha_de_entrada_do_controle_tem_o_glifo_do_mapa(janela: Any) -> None:  # noqa: F811
    html = _montada(janela)
    faltam = _sem_glifo(html)
    assert not faltam, f"as entradas sem o glifo do mapa: {faltam}"
    for ident, rotulo in ENTRADAS:
        linha = re.search(rf'<div class="tql" id="mod-op-{ident}"([^>]*)>(.*?)</select></div>',
                          html, re.S)
        assert linha is not None, f"{ident}: a linha não está no arranjo dos botões"
        assert f'data-dica="{rotulo}"' in linha.group(1), f"{ident}: o rótulo não virou dica"
        assert rotulo not in re.sub(r"<[^>]+>", " ", linha.group(2).split("<select")[0]), (
            f"{ident}: o rótulo ainda aparece escrito na linha")


def test_o_glifo_e_a_peca_do_mapa_e_vem_do_dono_unico() -> None:
    mapa = _glifos_do_mapa()
    fora = {k: g for k, g in GLIFO_DA_ENTRADA.items() if g not in mapa}
    assert not fora, f"glifos que não são peças do mapa do controle: {fora}"
    pagina = DESENHO.read_text(encoding="utf-8")
    for chave, glifo in GLIFO_DA_ENTRADA.items():
        simbolo = exp._simbolo_do_glifo(f"en-{chave}", glifo)
        assert simbolo in pagina, f"en-{chave}: o desenho não tem o glifo {glifo} do dono"


def test_a_entrada_sem_glifo_conhecido_fica_como_esta_e_a_regua_a_lista() -> None:
    estranha = OpcaoDaJanela("ext", f"{PREFIXO_DA_ENTRADA}pedal", "Pedal", "escolha", "Nenhum",
                             ("Nenhum", "Direto"), "Toques")
    conhecida = estranha._replace(id=f"{PREFIXO_DA_ENTRADA}l2", rotulo="Gatilho esquerdo (L2)")
    html = f'<div id="mod-janela">{exp._linhas_das_opcoes([conhecida, estranha])}</div>'
    assert '<div class="ky-linha" id="mod-op-entrada_pedal"><div class="ky-rot"><span>Pedal' in html
    assert re.findall(r'class="tql" id="mod-op-(\w+)"', html) == ["entrada_l2"]
    assert _sem_glifo(html) == ["entrada_pedal"]


_ABRIR = """(function(endereco, h){
  location.hash = endereco;
  window.__hef.pintar({blocos: {'#mod-janela': h}});
  const j = document.getElementById('mod-janela');
  const rot = [...j.querySelectorAll('.mj-abas > label')].find(l => l.textContent === 'Toques');
  if (!rot) return 'sem a aba';
  rot.click();
  return 'ok';
})(%s, %s)"""
_LER = """(function(){
  const j = document.getElementById('mod-janela'), lista = j.querySelector('.ja-opcoes');
  const linhas = [...j.querySelectorAll('[id^="mod-op-entrada_"]')].map(l => {
    const u = l.querySelector('svg.tq-gl use'), r = l.getBoundingClientRect();
    return {id: l.id, desenho: u ? Math.round(u.getBBox().width) : 0,
            y: Math.round(r.top), x: Math.round(r.left), alto: Math.round(r.height)};
  });
  return JSON.stringify({altura: lista.scrollHeight, linhas: linhas});
})()"""


def test_as_entradas_desenham_o_glifo_em_duas_colunas_sem_rolagem_nova(
        janela: Any, monkeypatch: pytest.MonkeyPatch) -> None:  # noqa: F811
    from hefesto_dualsense4unix.interface import hefesto_vivo
    from tests.unit.test_o_aparelho_da_extensao_diz_os_controles_dele import SONDA

    com_glifo = _montada(janela)
    monkeypatch.setattr(exp, "GLIFO_DA_ENTRADA", {})
    exp.pedacos_da_janela.cache_clear()
    a07 = janela[0]
    a07._MEXIDA.limpar()
    so_texto = str(janela[2](_Ponte(VIVO), mod_id=MOD)["blocos"]["#mod-janela"])
    assert "tq-gl\"><use href=\"#en-" not in so_texto
    casos = {f"{nome}@{w}x{h}": (w, h, [
        ["js", hefesto_vivo.BOOTSTRAP],
        ["js", _ABRIR % (json.dumps(ENDERECO), json.dumps(html))], ["espera", 0.3], ["js", _LER]])
        for nome, html in (("glifo", com_glifo), ("texto", so_texto)) for w, h in VISTAS}
    filho = subprocess.run([sys.executable, "-c", SONDA, str(DESENHO)], input=json.dumps(casos),
                           env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"),
                           capture_output=True, text=True, timeout=600)
    if filho.returncode != 0:
        pytest.skip(f"o WebKit não subiu na tela de mentira: {filho.stderr.strip()[-300:]}")
    medidas = json.loads(filho.stdout.strip().splitlines()[-1])
    print(json.dumps(medidas, ensure_ascii=False))
    falhas = []
    for w, h in VISTAS:
        _, abriu, lido = medidas[f"glifo@{w}x{h}"]
        _, _, texto = medidas[f"texto@{w}x{h}"]
        assert abriu == "ok", abriu
        lido, texto = json.loads(lido), json.loads(texto)
        linhas = lido["linhas"]
        assert len(linhas) == len(ENTRADAS), linhas
        falhas += [f"{w}x{h} {li['id']}: o glifo não desenha" for li in linhas
                   if li["desenho"] <= 0]
        pares = [(a, b) for a, b in zip(linhas[::2], linhas[1::2], strict=False)]
        falhas += [f"{w}x{h} {a['id']} e {b['id']} não dividem a linha" for a, b in pares
                   if a["y"] != b["y"] or a["x"] >= b["x"]]
        if lido["altura"] >= texto["altura"]:
            falhas.append(f"{w}x{h}: a lista ficou com {lido['altura']}px, "
                          f"e com as linhas escritas tinha {texto['altura']}px")
    assert not falhas, "\n".join(falhas)
