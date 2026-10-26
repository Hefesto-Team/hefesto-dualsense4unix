"""Os modos do Ao vivo são glifos com dica.

OS-MODOS-DO-AO-VIVO-SAO-GLIFOS-COM-DICA-01 (26/10/2026). «Soltar», «Segurar» e «Repetir» não
diziam o que a barra faz ao soltar o dedo; viram três glifos (seta para a base, cadeado e laço),
e a frase do efeito mora na dica e no ``aria-label``. O valor gravado, o ``data-modo`` e o gesto
não mudam.

MORDIDAS (26/10/2026, executadas sobre a cura e devolvidas): o texto «Soltar» devolvido ao botão
reprova ``test_o_botao_nao_tem_palavra_so_o_glifo``; a dica de um modo trocada pela de outro
reprova ``test_cada_modo_diz_o_efeito_na_dica_e_no_aria_label``; o ``data-modo`` mudado reprova
``test_o_valor_gravado_e_o_gesto_nao_mudam``; o traço do glifo apagado no CSS reprova o teste do
WebKit.
"""

from __future__ import annotations

import json
import re
from typing import Any

import pytest

from tests.unit.test_a_aba_lancadores_ganha_as_modificacoes import (  # noqa: F401
    ctx,
    lar,
)
from tests.unit.test_a_janela_da_extensao_age_e_gere_os_aparelhos import (  # noqa: F401
    VIVO,
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
    VISTAS,
)

EFEITOS = {"soltar": "Volta a zero ao soltar", "segurar": "Fica onde parou",
           "repetir": "Repete o que você desenhou"}
PALAVRAS_VELHAS = ("Soltar", "Segurar", "Repetir")

_BOTAO = re.compile(r"<button\b([^>]*\bdata-modo=\"(\w+)\"[^>]*)>(.*?)</button>", re.S)


def botoes_do_html(html: str) -> dict[str, tuple[str, str]]:
    grupo = re.search(r'<span class="seg mj-modos"[^>]*>(.*?)</span>\s*<button', html, re.S)
    assert grupo is not None, "a faixa não desenhou os modos"
    return {m.group(2): (m.group(1), m.group(3)) for m in _BOTAO.finditer(grupo.group(1))}


def test_o_botao_nao_tem_palavra_so_o_glifo(janela: Any) -> None:  # noqa: F811
    botoes = botoes_do_html(montada(janela, VIVO))
    assert list(botoes) == ["soltar", "segurar", "repetir"], botoes
    for modo, (_, miolo) in botoes.items():
        assert "<svg" in miolo, f"{modo}: o botão não tem glifo"
        texto = re.sub(r"<[^>]+>", "", miolo).strip()
        assert texto == "", f"{modo}: sobrou a palavra «{texto}» no botão"
    desenhos = {re.sub(r"\s+", " ", m) for _, m in botoes.values()}
    assert len(desenhos) == 3, "os três modos têm de ter glifos diferentes"


def test_cada_modo_diz_o_efeito_na_dica_e_no_aria_label(janela: Any) -> None:  # noqa: F811
    """Prova da D-2610-OS-MODOS-DO-AO-VIVO-SAO-GLIFOS-COM-DICA."""
    botoes = botoes_do_html(montada(janela, VIVO))
    for modo, frase in EFEITOS.items():
        atributos = botoes[modo][0]
        assert f'data-dica="{frase}"' in atributos, f"{modo}: a dica não é «{frase}»"
        assert f'aria-label="{frase}"' in atributos, f"{modo}: o aria-label não é «{frase}»"
    for velha in PALAVRAS_VELHAS:
        assert all(velha not in atributos for atributos, _ in botoes.values()), velha


def test_o_valor_gravado_e_o_gesto_nao_mudam(janela: Any) -> None:  # noqa: F811
    botoes = botoes_do_html(montada(janela, VIVO))
    for modo, (atributos, _) in botoes.items():
        assert 'data-gesto="modo-do-livre-da-modificacao"' in atributos, modo
        assert re.search(rf'data-v="intiface:ao_vivo:{modo}"', atributos), (modo, atributos)
        assert 'aria-pressed="' in atributos, modo
    aceso = [m for m, (atributos, _) in botoes.items() if re.search(r'class="on"', atributos)]
    assert len(aceso) == 1, aceso


_LER = """(function(endereco, h){
  location.hash = endereco;
  window.__hef.pintar({blocos: {'#mod-janela': h}});
  const bs = [...document.querySelectorAll('#mod-janela .mj-modos button')];
  const medir = b => { const r = b.getBoundingClientRect(), s = b.querySelector('svg'),
      sr = s ? s.getBoundingClientRect() : null;
    b.dispatchEvent(new MouseEvent('mouseover', {bubbles: true}));
    const d = document.getElementById('hef-dica');
    const cor = s ? getComputedStyle(s).stroke : '';
    return {modo: b.dataset.modo, w: r.width, h: r.height,
      glifo: sr ? [sr.width, sr.height, sr.left >= r.left - 0.5 && sr.right <= r.right + 0.5,
                   sr.top >= r.top - 0.5 && sr.bottom <= r.bottom + 0.5] : null,
      cor: cor, dica: d ? d.textContent : null,
      visivel: d ? d.classList.contains('visivel') : false,
      texto: b.textContent.trim()}; };
  return JSON.stringify(bs.map(medir));
})(%s, %s)"""


@pytest.fixture
def medidos(janela: Any, pagina_fresca: Any) -> dict[str, list[dict[str, Any]]]:  # noqa: F811
    from hefesto_dualsense4unix.interface import hefesto_vivo

    html = montada(janela, SEM_APARELHOS)
    casos = {f"{w}x{h}": (w, h, [["js", hefesto_vivo.BOOTSTRAP],
                                 ["js", _LER % (json.dumps(ENDERECO), json.dumps(html))]])
             for w, h in VISTAS}
    lidos = no_webkit(pagina_fresca, casos)
    saida = {caso: json.loads(r[1]) for caso, r in lidos.items()}
    print(json.dumps(saida, ensure_ascii=False))
    return saida


def test_no_webkit_o_glifo_cabe_no_botao_e_a_dica_aparece(
        medidos: dict[str, list[dict[str, Any]]]) -> None:
    falhas = []
    for caso, botoes in medidos.items():
        assert [b["modo"] for b in botoes] == ["soltar", "segurar", "repetir"], (caso, botoes)
        for b in botoes:
            if b["glifo"] is None or b["glifo"][0] < 12 or b["glifo"][1] < 12:
                falhas.append(f"{caso} · {b['modo']}: o glifo não aparece ({b['glifo']})")
            elif not (b["glifo"][2] and b["glifo"][3]):
                falhas.append(f"{caso} · {b['modo']}: o glifo sai do botão")
            if b["w"] < 28 or b["h"] < 28:
                falhas.append(f"{caso} · {b['modo']}: o botão é pequeno para o dedo "
                              f"({b['w']:.0f}x{b['h']:.0f})")
            if b["texto"]:
                falhas.append(f"{caso} · {b['modo']}: o botão ainda diz «{b['texto']}»")
            if b["cor"] in ("", "none"):
                falhas.append(f"{caso} · {b['modo']}: o glifo não tem traço")
            if not b["visivel"] or b["dica"] != EFEITOS[b["modo"]]:
                falhas.append(f"{caso} · {b['modo']}: a dica mostrada é «{b['dica']}» "
                              f"(visível={b['visivel']})")
    assert not falhas, "\n".join(falhas)
