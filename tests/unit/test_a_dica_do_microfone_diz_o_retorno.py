"""O «?» do Microfone diz o que o 🎙 faz HOJE — acrescentado em 24/09/2026."""

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


def _texto(html: str) -> str:
    return " ".join(re.sub(r"<[^>]+>", " ", html).split())


def _dicas_do_microfone(doc: str) -> list[str]:
    """O texto do «?» de cada rótulo Microfone, como a pessoa o lê."""
    doc = re.sub(r"<!--.*?-->", "", doc, flags=re.S)
    dicas = re.findall(
        r'<div class="rot rot-linha">Microfone.*?<span class="dica">(.*?)</span></span>',
        doc, flags=re.S)
    return [_texto(d) for d in dicas]


def _titulos_do_botao(doc: str) -> list[str]:
    return re.findall(r'<button[^>]*data-gesto="mic-retorno"[^>]*title="([^"]*)"', doc)


@pytest.mark.parametrize("alvo", [BANCADA, PUBLICADO], ids=["bancada", "publicado"])
def test_o_interrogacao_do_microfone_diz_o_retorno(alvo: pathlib.Path) -> None:
    """MORDIDA: devolva «O 🎙 cala o microfone e apaga a luz vermelha do"""
    if alvo == PUBLICADO and _a_02_esta_em_trabalho():
        pytest.skip("a 02 está declarada em trabalho: o publicado é o desenho "
                    "de ontem até a publicação")
    doc = alvo.read_text(encoding="utf-8")
    dicas = _dicas_do_microfone(doc)
    assert dicas, f"{alvo.name}: o «?» do Microfone sumiu — a régua não achou o que ler"

    for dica in dicas:
        for errado in O_QUE_ELE_NAO_FAZ:
            assert not errado.search(dica), (
                f"o «?» do Microfone ainda diz que o 🎙 cala o microfone: {dica[:160]}")
        assert "retorno" in dica, f"o «?» não diz o que o 🎙 faz hoje: {dica[:160]}"
        assert "botão do próprio controle" in dica, (
            f"o «?» não diz quem cala o microfone agora: {dica[:160]}")


@pytest.mark.parametrize("alvo", [BANCADA, PUBLICADO], ids=["bancada", "publicado"])
def test_o_interrogacao_e_o_botao_contam_a_mesma_historia(alvo: pathlib.Path) -> None:
    """As duas falas do MESMO botão, uma contra a outra: o `title` do 🎙 diz"""
    if alvo == PUBLICADO and _a_02_esta_em_trabalho():
        pytest.skip("a 02 está declarada em trabalho")
    doc = alvo.read_text(encoding="utf-8")
    titulos = _titulos_do_botao(doc)
    dicas = _dicas_do_microfone(doc)
    assert titulos and len(titulos) == len(dicas), (titulos, dicas)
    for titulo, dica in zip(titulos, dicas, strict=True):
        for fato in ("retorno", "botão do próprio controle"):
            assert (fato in titulo) == (fato in dica), (
                f"o botão e o «?» discordam sobre {fato!r}:\n  title: {titulo}\n"
                f"  «?»: {dica[:160]}")
