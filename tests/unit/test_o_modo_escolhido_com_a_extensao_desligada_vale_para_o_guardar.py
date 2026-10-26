"""O modo escolhido com a extensão desligada vale para o Guardar.

O-MODO-ESCOLHIDO-COM-A-EXTENSAO-DESLIGADA-VALE-PARA-O-GUARDAR-01 (25/10/2026). Depois de um
arrastar, trocar «Soltar», «Segurar» ou «Repetir» manda à extensão o soltar com o modo novo. Fora
da porta ela não segura modo nenhum (volta lendo o guardado): a troca vale para o rascunho e para
a barra, sem acusar recusa, pelo mesmo dono do Cancelar fora da porta (``_Viva.sem_a_extensao``).
Na porta, a recusa de verdade continua voltando o modo e piscando.

MORDIDAS (25/10/2026, executadas sobre a cura e devolvidas):

- o gesto do modo que acusa a extensão fora da porta (sem o ``_o_modo_na_extensao``) reprova
  ``test_fora_da_porta_o_modo_trocado_depois_do_arrastar_vale_para_o_guardar`` (os três modos);
- o ``_o_modo_na_extensao`` sem o ``sem_a_extensao`` reprova o mesmo teste no «Soltar» e no
  «Repetir» (a barra fica no modo de antes) e o Cancelar fora da porta;
- o ``_o_modo_na_extensao`` que toma a recusa de verdade como fora da porta reprova
  ``test_na_porta_a_recusa_da_troca_continua_piscando`` e os três casos de recusa do Cancelar.
"""

from __future__ import annotations

from typing import Any

import pytest

from hefesto_dualsense4unix.mods.manifesto import MODOS_DO_LIVRE
from tests.unit.test_a_aba_lancadores_ganha_as_modificacoes import ctx, lar  # noqa: F401
from tests.unit.test_a_janela_da_extensao_age_e_gere_os_aparelhos import (  # noqa: F401
    VIVO,
    _Ponte,
    janela,
)
from tests.unit.test_o_cancelar_da_janela_desfaz_o_modo import _acesos, _PonteQueRecusa
from tests.unit.test_o_livre_ganha_os_modos import (  # noqa: F401
    COM_MODOS,
    _arrastar_e_soltar,
    _com,
    _livres,
    _modos_na_faixa,
    relogio,
)
from hefesto_dualsense4unix.interface.desenho_da_experimental import janela_pintada


def _guardado(lar: Any) -> Any:  # noqa: F811
    from hefesto_dualsense4unix.mods import opcoes
    from hefesto_dualsense4unix.mods.instalador import manifesto_instalado

    return opcoes.ler(manifesto_instalado("toque", lugares=lar), lar)["ao-vivo:modo"]


@pytest.mark.parametrize("modo", MODOS_DO_LIVRE)
def test_fora_da_porta_o_modo_trocado_depois_do_arrastar_vale_para_o_guardar(
        janela: Any, ctx: Any, lar: Any, relogio: list[float], modo: str) -> None:  # noqa: F811
    """Prova da D-2510-O-MODO-FORA-DA-PORTA-VALE-PARA-O-GUARDAR."""
    a07, instalar, abrir = janela
    instalar(**_com(COM_MODOS))
    ponte = _Ponte(VIVO)
    abrir(ponte)
    if modo == "soltar":
        a07.modo_do_livre_da_modificacao(ctx, {"v": "toque:ao-vivo:segurar"}, ponte)
        a07.guardar_modificacao(ctx, {"v": "toque"}, ponte)
    _arrastar_e_soltar(a07, ctx, ponte, relogio)
    ponte.rodando = False
    antes = len(_livres(ponte))
    carga = a07.modo_do_livre_da_modificacao(ctx, {"v": f"toque:ao-vivo:{modo}"}, ponte)
    assert "recado" not in carga, carga.get("recado")
    assert a07._MEXIDA.rascunho.get("ao-vivo:modo") == modo, "a troca fora da porta não ficou"
    assert _modos_na_faixa(janela_pintada(carga["blocos"])) == _acesos(modo)
    assert a07._VIVA.modo == modo, "a barra seguiu no modo de antes"
    assert len(_livres(ponte)[antes:]) <= 1
    vistos: set[float] = set()
    for _ in range(8):
        relogio[0] += 0.05
        vistos.add(a07._VIVA.ao_vivo("toque").valor)
    if modo == "repetir":
        assert len(vistos) > 1, f"a barra não tocou o trecho em laço: {vistos}"
    else:
        assert vistos == {0.0}, f"a barra não fez o «{modo.title()}» escolhido: {vistos}"
    carga = a07.guardar_modificacao(ctx, {"v": "toque"}, ponte)
    assert carga.get("recado") == "Guardado."
    assert _guardado(lar) == modo, "o Guardar não gravou o modo escolhido fora da porta"
    html = abrir(ponte)["blocos"]["#mod-janela"]
    assert _modos_na_faixa(html) == _acesos(modo), "o reabrir largou o modo guardado"


def test_na_porta_a_recusa_da_troca_continua_piscando(
        janela: Any, ctx: Any, lar: Any, relogio: list[float]) -> None:  # noqa: F811
    a07, instalar, abrir = janela
    instalar(**_com(COM_MODOS))
    ponte = _PonteQueRecusa(VIVO)
    abrir(ponte)
    _arrastar_e_soltar(a07, ctx, ponte, relogio)
    ponte.recusa = "A extensão recusou o modo."
    with pytest.raises(RuntimeError, match=r"A extensão recusou o modo\."):
        a07.modo_do_livre_da_modificacao(ctx, {"v": "toque:ao-vivo:repetir"}, ponte)
    assert "ao-vivo:modo" not in a07._MEXIDA.rascunho, "o modo recusado ficou no rascunho"
    assert a07._VIVA.modo == "soltar", "o modo recusado ficou valendo na barra"
    a07.guardar_modificacao(ctx, {"v": "toque"}, ponte)
    assert _guardado(lar) == "soltar", "o Guardar gravou o modo que a extensão recusou"


_GUARDAR = """(function(h){
  const j = document.getElementById('mod-janela');
  j.innerHTML = h;
  location.hash = '#' + j.closest('.tela-nova').id;
  const aceso = [...j.querySelectorAll('.mj-modos button.on')].map(b => b.dataset.modo);
  const vistos = [];
  const ouvir = e => { const g = e.target.closest && e.target.closest('[data-gesto]');
    vistos.push(g ? g.dataset.gesto + '|' + g.dataset.v : ''); };
  document.addEventListener('click', ouvir, true);
  [...j.querySelectorAll('a.btn')].find(a => a.textContent.trim() === 'Guardar').click();
  document.removeEventListener('click', ouvir, true);
  return JSON.stringify({aceso: aceso, vistos: vistos});
})(%s)"""


def test_no_webkit_o_modo_trocado_fora_da_porta_acende_e_o_guardar_leva_o_gesto(
        janela: Any, ctx: Any, relogio: list[float]) -> None:  # noqa: F811
    import json

    from tests.unit.test_o_aparelho_da_extensao_diz_os_controles_dele import VISTAS, rodar_no_webkit

    a07, instalar, abrir = janela
    instalar(**_com(COM_MODOS))
    ponte = _Ponte(VIVO)
    abrir(ponte)
    _arrastar_e_soltar(a07, ctx, ponte, relogio)
    ponte.rodando = False
    carga = a07.modo_do_livre_da_modificacao(ctx, {"v": "toque:ao-vivo:repetir"}, ponte)
    w, h = VISTAS[1]
    passos = [["js", _GUARDAR % json.dumps(janela_pintada(carga["blocos"]))]]
    lido = json.loads(rodar_no_webkit({"janela": (w, h, passos)})["janela"][0])
    assert lido["aceso"] == ["repetir"], lido
    assert lido["vistos"] == ["guardar-modificacao|toque"], lido
