"""A faixa de força anda de 1 em 1 e o número ao lado mostra o degrau que o brinquedo faz.

Prova da D-2810-A-FORCA-SOBE-AO-DEGRAU-DO-BRINQUEDO (a escolha de 29/10/2026, «Livre,
mostrando o degrau»). O ``deslizante`` com ``degraus`` mostra ``k/N`` ao lado: a fração da faixa em
``N`` degraus, arredondada para cima, e o degrau 1 em toda posição acima do mínimo. O número que
nasce (:func:`degrau_da_faixa`, em Python) e o do arrastar (o ``oninput``, em JavaScript) são a
mesma conta, posição por posição; a régua da extensão compara o mesmo número com o degrau que sai
a cada brinquedo.

MORDIDAS (29/10/2026, executadas sobre a cura e devolvidas):

- o ``Math.ceil`` do JavaScript trocado por ``Math.round`` reprova
  ``test_o_arrastar_e_o_numero_que_nasce_sao_a_mesma_conta`` e o arrastar no WebKit;
- o piso do degrau 1 arrancado de :func:`degrau_da_faixa` (``max(0, …)``) reprova
  ``test_o_numero_e_o_degrau_de_cima_e_nunca_abaixo_de_1`` e a mesma conta;
- o ``degraus`` esquecido na janela (``degraus=0`` no ``a07``) reprova
  ``test_a_janela_mostra_o_degrau_da_forca`` e o arrastar no WebKit;
- a recusa do ``degraus`` fora do ``deslizante`` arrancada reprova
  ``test_o_manifesto_recusa_os_degraus_fora_do_lugar``.
"""

from __future__ import annotations

import html
import json
import pathlib
import shutil
import subprocess
from typing import Any

import pytest
from pydantic import ValidationError

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

FORCAS = ("forca_dos_toques", "cena_do_jogo", "teto")


def _deslizante(**extra: Any) -> dict[str, Any]:
    return {"id": "forca", "rotulo": "Força", "tipo": "deslizante",
            "minimo": 0,  # (noqa-acento)
            "maximo": 100, "passo": 1, "padrao": 60, **extra}  # (noqa-acento)


def test_os_degraus_passam_no_deslizante() -> None:
    from hefesto_dualsense4unix.mods.manifesto import Opcao

    assert Opcao(**_deslizante(degraus=20)).degraus == 20


@pytest.mark.parametrize("campos", [
    {"id": "forca", "rotulo": "Força", "tipo": "ligado", "degraus": 20},
    _deslizante(degraus=20, unidade="%"),
    _deslizante(degraus=0),
])
def test_o_manifesto_recusa_os_degraus_fora_do_lugar(campos: dict[str, Any]) -> None:
    from hefesto_dualsense4unix.mods.manifesto import Opcao

    with pytest.raises(ValidationError):
        Opcao(**campos)


@pytest.mark.parametrize(("valor", "degraus", "numero"), [
    (0, 20, "0/20"), (0.000001, 20, "1/20"), (1, 20, "1/20"), (5, 20, "1/20"), (6, 20, "2/20"),
    (35, 20, "7/20"), (36, 20, "8/20"), (99, 20, "20/20"), (100, 20, "20/20"),
    (0, 3, "0/3"), (1, 3, "1/3"), (33, 3, "1/3"), (34, 3, "2/3"), (66, 3, "2/3"), (67, 3, "3/3"),
])
def test_o_numero_e_o_degrau_de_cima_e_nunca_abaixo_de_1(valor: int, degraus: int,
                                                       numero: str) -> None:
    from hefesto_dualsense4unix.interface import desenho_da_experimental as exp

    assert exp.numero_do_deslizante(valor, degraus=degraus, minimo=0, maximo=100) == numero


_NO_NODE = """const casos = %s, saida = [];
for (const [v, n, lo, hi] of casos) {
  const el = {value: String(v), min: String(lo), max: String(hi),
              nextElementSibling: {dataset: {degraus: String(n), zero: '', unidade: ''},
                                   textContent: ''}};
  (function () { %s }).call(el);
  saida.push(el.nextElementSibling.textContent);
}
process.stdout.write(JSON.stringify(saida));"""


def test_o_arrastar_e_o_numero_que_nasce_sao_a_mesma_conta(tmp_path: pathlib.Path) -> None:
    """Prova da D-2810-A-FORCA-SOBE-AO-DEGRAU-DO-BRINQUEDO."""
    from hefesto_dualsense4unix.interface import desenho_da_experimental as exp

    node = shutil.which("node") or shutil.which("nodejs")
    assert node, "sem o node, a conta do arrastar não se mede fora do WebKit"
    casos = [(v, n, 0, 100) for n in (20, 3, 7, 1) for v in range(101)]
    casos += [(v, 20, 1, 30) for v in range(1, 31)]
    casos += [(0.000001, 20, 0, 100), (0.000001, 3, 0, 100)]
    roteiro = tmp_path / "conta.js"
    roteiro.write_text(_NO_NODE % (json.dumps(casos), html.unescape(exp._NUMERO_AO_ARRASTAR)),
                       encoding="utf-8")
    lidos = json.loads(subprocess.run([node, str(roteiro)], capture_output=True, text=True,
                                      check=True, timeout=30).stdout)
    esperados = [exp.numero_do_deslizante(v, degraus=n, minimo=lo, maximo=hi)
                 for v, n, lo, hi in casos]
    assert lidos == esperados


def _pecas() -> dict[str, Any]:
    pecas = pecas_da_lovense()
    lista = [{**o, "passo": 1, "degraus": 20} if o["id"] in FORCAS else o
             for o in pecas["opcoes"]]  # (noqa-acento)
    return {**pecas, "opcoes": lista}  # (noqa-acento)


def _montada(janela: Any) -> str:  # noqa: F811
    a07, instalar, abrir = janela
    instalar(mod_id=MOD, **_pecas())
    a07._MEXIDA.limpar()
    return str(abrir(_Ponte(VIVO), mod_id=MOD)["blocos"]["#mod-janela"])


def test_a_janela_mostra_o_degrau_da_forca(janela: Any) -> None:  # noqa: F811
    html_ = _montada(janela)
    for opcao in FORCAS:
        trecho = html_.split(f'data-v="{MOD}:{opcao}"', 1)[1].split("</span>", 1)[0]
        assert 'data-degraus="20">10/20</b>' in trecho, (opcao, trecho)
    assert 'step="1"' in html_.split(f'data-v="{MOD}:teto"', 1)[0].rsplit("<input", 1)[1]


_ABRIR = """(function(endereco, h){
  location.hash = endereco;
  window.__hef.pintar({blocos: {'#mod-janela': h}});
  const j = document.getElementById('mod-janela');
  const rot = [...j.querySelectorAll('.mj-abas > label')].find(l => l.textContent === 'Força');
  if (!rot) return 'sem a aba';
  rot.click();
  return 'ok';
})(%s, %s)"""
_ARRASTAR = """(function(id, valor){
  const j = document.getElementById('mod-janela');
  const s = j.querySelector('[data-v="intiface:' + id + '"]');
  s.value = valor;
  s.dispatchEvent(new Event('input', {bubbles: true}));
  return JSON.stringify({numero: s.nextElementSibling.textContent, valor: s.value,
    cabe: s.nextElementSibling.scrollWidth <= s.nextElementSibling.clientWidth + 1});
})(%s, %s)"""


def test_no_webkit_o_numero_segue_o_degrau_ao_arrastar_de_1_em_1(
        janela: Any, pagina_fresca: pathlib.Path) -> None:  # noqa: F811
    """Prova da D-2810-A-FORCA-SOBE-AO-DEGRAU-DO-BRINQUEDO."""
    from hefesto_dualsense4unix.interface import hefesto_vivo

    html_ = _montada(janela)
    valores = ["1", "4", "5", "6", "35", "36", "100", "0"]
    casos = {f"{w}x{h}": (w, h, [
        ["js", hefesto_vivo.BOOTSTRAP], ["js", _ABRIR % (json.dumps(ENDERECO), json.dumps(html_))],
        ["espera", 0.3], *(["js", _ARRASTAR % (json.dumps("teto"), json.dumps(v))]
                           for v in valores)])
        for w, h in VISTAS}
    lidos = no_webkit(pagina_fresca, casos)
    print(json.dumps(lidos, ensure_ascii=False))
    for caso, (_, abriu, *arrastos) in lidos.items():
        assert abriu == "ok", (caso, abriu)
        lidos_ = [json.loads(x) for x in arrastos]
        assert [x["valor"] for x in lidos_] == valores, caso
        assert [x["numero"] for x in lidos_] == [
            "1/20", "1/20", "1/20", "2/20", "7/20", "8/20", "20/20", "0/20"], caso
        assert all(x["cabe"] for x in lidos_), (caso, lidos_)
