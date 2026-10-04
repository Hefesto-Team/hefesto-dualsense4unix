"""O-DESLIGADO-DEIXA-O-JOGO-DECIDIR-01 — o gatilho: UMA entrada, e ela diz o que faz.

A foto dela, 03/10/2026 ~18h20 (aba Gatilhos, P1, L2): a lista do modo oferecia
`—` e `Desligado`, que pareciam a mesma entrada. A regra dela, ~18h15:
*«o certo seria os controles obedecerem quando o jogo manda e na
ausencia disso o perfil ganha»*  (noqa-acento: citação dela) — então o «Desligado» do gatilho é «O jogo decide»: sem jogo pintando, o
gatilho fica como o controle vem de fábrica (`trigger.reset`), e o que o jogo
pintar chega. A chave no perfil continua `Off` (a forma do perfil não muda); o
lado do daemon, que não trava o campo quando ele é `Off`, é do conjunto Microfone.

AS MORDIDAS:

* devolva o rótulo «Desligado» ao `Off` (`_ROTULO_DA_TELA` do `aba03`) →
  `test_ha_uma_entrada_de_o_jogo_decide_e_nenhuma_de_desligado` reprova;
* tire o `hidden` do `—` (`_op_vazio`) → `test_o_travessao_nao_e_uma_linha_da_lista`
  reprova, nos oito campos e na lista que o pacote monta;
* troque o `Off` do gesto por `trigger_set` → a prova do gesto em `a03.PROVAS`
  (`test_os_botoes_tem_dono`) reprova.
"""
from __future__ import annotations

import pathlib
import re
import sys

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(RAIZ / "src/hefesto_dualsense4unix/interface"))

_SELECT = re.compile(r'<select[^>]*class="modo"[^>]*>(?P<dentro>.*?)</select>', re.S)
_OPCAO = re.compile(r"<option(?P<attrs>[^>]*)>(?P<texto>[^<]*)</option>")


def _listas_da_bancada() -> list[str]:
    from hefesto_dualsense4unix.interface import onde

    doc = onde.pagina("03-gatilhos.html").read_text(encoding="utf-8")
    return [m.group("dentro") for m in _SELECT.finditer(doc)]


def _listas_do_pacote() -> list[str]:
    import pacotes  # noqa: F401  (registra os dez)
    from pacotes import a03_gatilhos

    return [a03_gatilhos.html_das_opcoes_de_modo()]


def _visiveis(dentro: str) -> list[str]:
    """O que a lista MOSTRA: as opções sem `hidden`."""
    return [m.group("texto") for m in _OPCAO.finditer(dentro)
            if "hidden" not in m.group("attrs")]


@pytest.mark.parametrize("fonte", [_listas_da_bancada, _listas_do_pacote])
def test_ha_uma_entrada_de_o_jogo_decide_e_nenhuma_de_desligado(fonte) -> None:
    listas = fonte()
    assert listas, "nenhuma lista de modo encontrada"
    for dentro in listas:
        vistas = _visiveis(dentro)
        assert vistas.count("O jogo decide") == 1, vistas
        assert "Desligado" not in vistas, (
            "o «Desligado» voltou à lista: o gatilho tem duas palavras para a mesma coisa")


@pytest.mark.parametrize("fonte", [_listas_da_bancada, _listas_do_pacote])
def test_o_travessao_nao_e_uma_linha_da_lista(fonte) -> None:
    """O `—` fica no `<select>` (o piloto o escreve no lugar vazio), mas escondido."""
    for dentro in fonte():
        travessoes = [m for m in _OPCAO.finditer(dentro) if m.group("texto") == "—"]
        assert len(travessoes) == 1
        atributos = travessoes[0].group("attrs")
        assert "hidden" in atributos and "disabled" in atributos, atributos
        assert "—" not in _visiveis(dentro)


def test_o_gesto_e_o_rotulo_falam_a_mesma_coisa() -> None:
    import pacotes  # noqa: F401
    from pacotes import a03_gatilhos

    assert a03_gatilhos._rotulo_do_modo("Off") == a03_gatilhos.ROTULO_DO_JOGO_DECIDE
    assert "Desligado" not in a03_gatilhos.DICA_DO_MODO["Off"]
    assert a03_gatilhos._rotulo_do_modo("Rigid") == "Rígido"
