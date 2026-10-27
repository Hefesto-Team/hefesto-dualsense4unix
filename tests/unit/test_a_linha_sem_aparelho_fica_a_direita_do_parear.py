"""A linha sem aparelho fica à direita do Parear.

A-LINHA-SEM-APARELHO-FICA-A-DIREITA-DO-PAREAR-01 (26/10/2026). Na aba dos aparelhos da janela
«Configurar», o aviso «Nenhum aparelho por aqui ainda.» ficava numa linha abaixo do botão Parear;
agora divide a linha dele, à direita, e a fileira não muda de altura quando o primeiro aparelho
chega.

MORDIDAS (26/10/2026, executadas sobre a cura e devolvidas):

- a ``.mj-sec`` sem a regra ``:has(> .mj-ap-vazio)`` do CSS (o aviso volta à linha de baixo)
  reprova ``test_o_aviso_divide_a_linha_com_o_parear_a_direita_dele``;
- o ``.mj-sec`` tirado do ``_abas_com_as_pecas`` (os dois blocos soltos) reprova
  ``test_o_aviso_divide_a_linha_com_o_parear_a_direita_dele`` e
  ``test_o_aviso_e_o_botao_moram_juntos_so_na_aba_que_tem_os_dois``;
- o ``align-items:center`` trocado por ``start`` na ``.mj-sec`` reprova o alinhamento ao centro do
  botão;
- os cartões na segunda coluna (``grid-column:2`` no lugar de ``1 / -1``) reprovam
  ``test_a_fileira_do_parear_nao_pula_quando_o_primeiro_aparelho_chega``.
"""

from __future__ import annotations

import json
import os
import pathlib
import subprocess
import sys
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
from tests.unit.test_a_lista_da_janela_configurar_nao_pula_ao_clicar_um_efeito import (  # noqa: F401
    ENDERECO,
    MOD,
    VISTAS,
    pagina_fresca,
    pecas_da_lovense,
)

RAIZ = pathlib.Path(__file__).resolve().parents[2]
SEM_APARELHOS = {**VIVO, "aparelhos": []}


def no_webkit(pagina: pathlib.Path, casos: dict[str, tuple[int, int, list[list[Any]]]]
              ) -> dict[str, list[Any]]:
    """Os passos de cada caso no desenho, num WebKit de verdade na tela de mentira; sem WebKit,
    o teste é pulado (e pulo não é verde: a suíte roda isto em ``xvfb-run``)."""
    from tests.unit.test_o_aparelho_da_extensao_diz_os_controles_dele import SONDA

    filho = subprocess.run([sys.executable, "-c", SONDA, str(pagina)], input=json.dumps(casos),
                           env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"),
                           capture_output=True, text=True, timeout=600)
    if filho.returncode != 0:
        pytest.skip(f"o WebKit não subiu na tela de mentira: {filho.stderr.strip()[-300:]}")
    return dict(json.loads(filho.stdout.strip().splitlines()[-1]))


def montada(janela: Any, estado: dict[str, Any]) -> str:  # noqa: F811
    a07, instalar, abrir = janela
    instalar(mod_id=MOD, **pecas_da_lovense())
    a07._MEXIDA.limpar()
    return str(abrir(_Ponte(estado), mod_id=MOD)["blocos"]["#mod-janela"])


_ABRIR = """(function(endereco, h){
  location.hash = endereco;
  window.__hef.pintar({blocos: {'#mod-janela': h}});
  const j = document.getElementById('mod-janela');
  const rot = [...j.querySelectorAll('.mj-abas > label')].find(l => l.textContent === 'Brinquedos');
  if (!rot) return 'sem a aba';
  rot.click();
  return 'ok';
})(%s, %s)"""
_LER = """(function(){
  const j = document.getElementById('mod-janela');
  const r = e => { if (!e) return null; const x = e.getBoundingClientRect();
    return {x: x.left, y: x.top, d: x.right, b: x.bottom}; };
  const fileira = j.querySelector('FILEIRA');
  return JSON.stringify({botao: r(fileira.querySelector('.mj-acao')), fileira: r(fileira),
    aviso: r(j.querySelector('.mj-ap-vazio')), lista: r(j.querySelector('#mod-aparelhos')),
    cartoes: j.querySelectorAll('#mod-aparelhos .mj-ap').length});
})()""".replace("FILEIRA", '[id^="mod-acoes-"]')


@pytest.fixture
def medidas(janela: Any, pagina_fresca: pathlib.Path) -> dict[str, dict[str, Any]]:  # noqa: F811
    from hefesto_dualsense4unix.interface import hefesto_vivo

    casos = {}
    for nome, estado in (("sem", SEM_APARELHOS), ("com", VIVO)):
        html = montada(janela, estado)
        for w, h in VISTAS:
            casos[f"{nome}@{w}x{h}"] = (w, h, [
                ["js", hefesto_vivo.BOOTSTRAP],
                ["js", _ABRIR % (json.dumps(ENDERECO), json.dumps(html))],
                ["espera", 0.3], ["js", _LER]])
    lidos = no_webkit(pagina_fresca, casos)
    saida = {}
    for caso, (_, abriu, lido) in lidos.items():
        assert abriu == "ok", (caso, abriu)
        saida[caso] = json.loads(lido)
    print(json.dumps(saida, ensure_ascii=False))
    return saida


def test_o_aviso_divide_a_linha_com_o_parear_a_direita_dele(
        medidas: dict[str, dict[str, Any]]) -> None:
    falhas = []
    for w, h in VISTAS:
        lido = medidas[f"sem@{w}x{h}"]
        botao, aviso = lido["botao"], lido["aviso"]
        assert aviso is not None and lido["cartoes"] == 0, f"{w}x{h}: sem aviso: {lido}"
        if aviso["x"] < botao["d"] - 0.5:
            falhas.append(f"{w}x{h}: o aviso começa em {aviso['x']:.0f}, antes do fim do botão "
                          f"({botao['d']:.0f})")
        if aviso["y"] >= botao["b"] - 0.5:
            falhas.append(f"{w}x{h}: o aviso está abaixo do botão ({aviso['y']:.0f} >= "
                          f"{botao['b']:.0f})")
        centro_botao = (botao["y"] + botao["b"]) / 2
        centro_aviso = (aviso["y"] + aviso["b"]) / 2
        if abs(centro_botao - centro_aviso) > 1.5:
            falhas.append(f"{w}x{h}: o aviso não está no centro do botão "
                          f"({centro_aviso:.1f} contra {centro_botao:.1f})")
    assert not falhas, "\n".join(falhas)


def test_a_fileira_do_parear_nao_pula_quando_o_primeiro_aparelho_chega(
        medidas: dict[str, dict[str, Any]]) -> None:
    falhas = []
    for w, h in VISTAS:
        sem, com = medidas[f"sem@{w}x{h}"], medidas[f"com@{w}x{h}"]
        assert com["aviso"] is None and com["cartoes"] > 0, f"{w}x{h}: {com}"
        for chave in ("botao", "fileira"):
            for lado in ("x", "y", "d", "b"):
                if abs(sem[chave][lado] - com[chave][lado]) > 0.5:
                    falhas.append(f"{w}x{h}: {chave}.{lado} {sem[chave][lado]:.1f} -> "
                                  f"{com[chave][lado]:.1f} com o aparelho")
        if com["lista"]["y"] < com["botao"]["b"] - 0.5:
            falhas.append(f"{w}x{h}: os cartões não ficam abaixo do botão: {com}")
    assert not falhas, "\n".join(falhas)


def test_o_aviso_e_o_botao_moram_juntos_so_na_aba_que_tem_os_dois(janela: Any) -> None:  # noqa: F811
    """Sem ação na aba, a lista dos aparelhos não ganha a caixa que divide a linha."""
    from hefesto_dualsense4unix.interface import desenho_da_experimental as exp

    html = montada(janela, SEM_APARELHOS)
    assert html.count('class="mj-sec"') == 1, "a aba do Parear e dos aparelhos é uma caixa só"
    so_aparelhos = exp.modificacao_miolo_html(
        "X", [], mod="x", agora=(), estado=SEM_APARELHOS,
        aparelhos=exp.AparelhosDaJanela((exp.AcaoDaJanela("ligar", "Ligar"),), "Aparelhos"))
    assert 'class="mj-sec"' not in so_aparelhos
    assert exp.SEM_APARELHOS in so_aparelhos
