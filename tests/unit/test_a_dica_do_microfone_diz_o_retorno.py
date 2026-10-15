"""O 🎙 do Microfone diz o que faz HOJE (24/09/2026); o «?» saiu no todo de 15/10/2026."""

from __future__ import annotations

import importlib.util
import pathlib
import re
import sys

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
BANCADA = RAIZ / "mockup/02-controles.html"
PUBLICADO = RAIZ / "src/hefesto_dualsense4unix/interface/paginas/02-controles.html"

O_QUE_ELE_NAO_FAZ = (re.compile(r"🎙\W*\s*cala", re.I),
                     re.compile(r"apaga a luz vermelha", re.I))


def _a_02_esta_em_trabalho() -> bool:
    """Perguntado ao portão `desenho-aprovado` (`declaradas()`), o dono."""
    alvo = RAIZ / "scripts/check_o_desenho_aprovado.py"
    spec = importlib.util.spec_from_file_location("check_desenho_da_dica_do_mic", alvo)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules["check_desenho_da_dica_do_mic"] = mod
    spec.loader.exec_module(mod)
    return "02-controles.html" in mod.declaradas()


def _dicas_do_botao(doc: str) -> list[str]:
    """A dica de cada 🎙: `data-dica` (o todo de 15/10/2026) ou `title` (o desenho de ontem)."""
    achados = []
    for tag in re.findall(r'<button[^>]*data-gesto="mic-retorno"[^>]*>', doc):
        achados.append((re.findall(r'data-dica="([^"]*)"', tag)
                        or re.findall(r'title="([^"]*)"', tag) or [""])[0])
    return achados


@pytest.mark.parametrize("alvo", [BANCADA, PUBLICADO], ids=["bancada", "publicado"])
def test_a_dica_do_botao_do_microfone_diz_o_retorno(alvo: pathlib.Path) -> None:
    """MORDIDA: devolva «O 🎙 cala o microfone e apaga a luz vermelha» à dica do botão.

    O «?» do Microfone saiu no todo de 15/10/2026: a explicação mora na dica do próprio 🎙, e
    ela diz o que ele faz HOJE (o retorno), nunca que ele cala o microfone.
    """
    if alvo == PUBLICADO and _a_02_esta_em_trabalho():
        pytest.skip("a 02 está declarada em trabalho: o publicado é o desenho "
                    "de ontem até a publicação")
    doc = alvo.read_text(encoding="utf-8")
    dicas = _dicas_do_botao(doc)
    assert dicas, f"{alvo.name}: o 🎙 do Microfone sumiu — a régua não achou o que ler"
    for dica in dicas:
        assert dica, f"{alvo.name}: o 🎙 ficou sem dica"
        for errado in O_QUE_ELE_NAO_FAZ:
            assert not errado.search(dica), f"a dica do 🎙 diz o que ele não faz: {dica[:160]}"
        assert "voz" in dica or "retorno" in dica or "ouv" in dica, (
            f"a dica não diz o que o 🎙 faz hoje: {dica[:160]}")


@pytest.mark.parametrize("alvo", [BANCADA, PUBLICADO], ids=["bancada", "publicado"])
def test_o_microfone_nao_tem_ponto_de_interrogacao(alvo: pathlib.Path) -> None:
    """MORDIDA: devolva o `ponto_de_interrogacao` ao cabeçalho do microfone."""
    if alvo == PUBLICADO and _a_02_esta_em_trabalho():
        pytest.skip("a 02 está declarada em trabalho")
    doc = re.sub(r"<!--.*?-->", "", alvo.read_text(encoding="utf-8"), flags=re.S)
    mic = re.findall(r'data-bloco="microfone".*?data-bloco="alto-falante"', doc, flags=re.S)
    assert mic and not any('class="ajuda' in bloco for bloco in mic)
