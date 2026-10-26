"""A opção da extensão tem dica e unidade.

A-OPCAO-DA-EXTENSAO-TEM-DICA-E-UNIDADE-01 (26/10/2026). A opção do manifesto ganha ``dica``,
``unidade`` (só no ``deslizante``) e ``zero`` (só no ``deslizante`` de mínimo 0); a janela põe a
dica na linha, a unidade no número (também ao arrastar) e o texto do zero no 0.

MORDIDAS (26/10/2026, executadas sobre a cura e devolvidas):

- a ``dica`` ignorada na linha (``_dica_da_linha`` devolvendo vazio) reprova
  ``test_a_janela_mostra_a_dica_a_unidade_e_o_zero`` e a leitura do WebKit;
- a ``unidade`` e o ``zero`` ignorados no número que nasce (``numero_do_deslizante``) reprovam
  ``test_a_janela_mostra_a_dica_a_unidade_e_o_zero``;
- o ``oninput`` de antes (só ``this.value``) reprova o arrastar no WebKit;
- a recusa do ``zero`` com mínimo diferente de 0 arrancada reprova
  ``test_o_manifesto_recusa_o_campo_fora_do_lugar_com_o_id``.
"""

from __future__ import annotations

import json
import pathlib
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

DICA = "Para sozinho depois desse tempo"


def _deslizante(**extra: Any) -> dict[str, Any]:
    return {"id": "tempo", "rotulo": "Tempo máximo", "tipo": "deslizante",
            "minimo": 0,  # (noqa-acento)
            "maximo": 600, "passo": 30, "padrao": 0, **extra}  # (noqa-acento)


def test_os_tres_campos_passam() -> None:
    from hefesto_dualsense4unix.mods.manifesto import Opcao

    o = Opcao(**_deslizante(unidade="s", zero="Sem limite", dica=DICA))
    assert (o.unidade, o.zero, o.dica) == ("s", "Sem limite", DICA)
    assert Opcao(id="som", rotulo="Som", tipo="ligado", dica="Liga o som").dica == "Liga o som"


@pytest.mark.parametrize("campos", [
    {"id": "luz", "rotulo": "Luz", "tipo": "ligado", "unidade": "%"},
    {"id": "luz", "rotulo": "Luz", "tipo": "escolha", "escolhas": ["A"], "zero": "Nada"},
    {**_deslizante(minimo=5, padrao=5, zero="Sem limite"), "id": "luz"},
])
def test_o_manifesto_recusa_o_campo_fora_do_lugar_com_o_id(campos: dict[str, Any]) -> None:
    from hefesto_dualsense4unix.mods.manifesto import Opcao

    with pytest.raises(ValidationError, match="luz"):
        Opcao(**campos)


def test_a_unidade_tem_ate_quatro_letras() -> None:
    from hefesto_dualsense4unix.mods.manifesto import Opcao

    with pytest.raises(ValidationError):
        Opcao(**_deslizante(unidade="minutos"))


def _pecas() -> dict[str, Any]:
    pecas = pecas_da_lovense()
    lista = []
    for o in pecas["opcoes"]:  # (noqa-acento)
        if o["id"] == "forca_dos_toques":
            o = {**o, "unidade": "%"}
        if o["id"] == "teto":
            o = {**o, "dica": "O máximo que chega ao brinquedo", "unidade": "%"}
        lista.append(o)
        if o["id"] == "teto":
            lista.append({**_deslizante(unidade="s", zero="Sem limite", dica=DICA),
                           "grupo": "Força"})
    return {**pecas, "opcoes": lista}  # (noqa-acento)


def _montada(janela: Any) -> str:  # noqa: F811
    a07, instalar, abrir = janela
    instalar(mod_id=MOD, **_pecas())
    a07._MEXIDA.limpar()
    return str(abrir(_Ponte(VIVO), mod_id=MOD)["blocos"]["#mod-janela"])


def test_a_janela_mostra_a_dica_a_unidade_e_o_zero(janela: Any) -> None:  # noqa: F811
    html = _montada(janela)
    assert f'id="mod-op-tempo" data-dica="{DICA}"' in html
    assert 'id="mod-op-teto" data-dica="O máximo que chega ao brinquedo"' in html
    assert 'data-unidade="s" data-zero="Sem limite">Sem limite</b>' in html
    assert 'data-unidade="%" data-zero="">50 %</b>' in html
    assert 'id="mod-op-cena_do_jogo" data-dica' not in html


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
  const linha = document.getElementById('mod-op-' + id);
  return JSON.stringify({numero: s.nextElementSibling.textContent, dica: linha.dataset.dica || '',
    cabe: s.nextElementSibling.scrollWidth <= s.nextElementSibling.clientWidth + 1});
})(%s, %s)"""


def test_no_webkit_o_numero_diz_a_unidade_e_o_zero_ao_arrastar(
        janela: Any, pagina_fresca: pathlib.Path) -> None:  # noqa: F811
    from hefesto_dualsense4unix.interface import hefesto_vivo

    html = _montada(janela)
    passos = [["tempo", "0"], ["tempo", "120"], ["tempo", "0"], ["teto", "35"]]
    casos = {f"{w}x{h}": (w, h, [
        ["js", hefesto_vivo.BOOTSTRAP], ["js", _ABRIR % (json.dumps(ENDERECO), json.dumps(html))],
        ["espera", 0.3], *(["js", _ARRASTAR % (json.dumps(i), json.dumps(v))] for i, v in passos)])
        for w, h in VISTAS}
    lidos = no_webkit(pagina_fresca, casos)
    print(json.dumps(lidos, ensure_ascii=False))
    for caso, (_, abriu, *arrastos) in lidos.items():
        assert abriu == "ok", (caso, abriu)
        lidos_ = [json.loads(x) for x in arrastos]
        assert [x["numero"] for x in lidos_] == ["Sem limite", "120 s", "Sem limite", "35 %"], caso
        assert lidos_[0]["dica"] == DICA, caso
        assert all(x["cabe"] for x in lidos_), (caso, lidos_)
