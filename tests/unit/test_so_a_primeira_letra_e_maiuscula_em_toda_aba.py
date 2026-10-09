#!/usr/bin/env python3
"""Só a primeira letra é maiúscula, em toda aba — e a régua MORDE.

SO-A-PRIMEIRA-LETRA-E-MAIUSCULA-EM-TODA-ABA-01 (09/10/2026), escolha dela: «Só a 1ª
maiúscula». No meio da frase ou do rótulo, maiúscula só em nome próprio e marca
(DualSense, Steam, Hefesto, Linux, Proton, Xbox, Freestyle...). A régua é
`scripts/check_so_a_primeira_letra.py`, nas dez publicadas e nas dez do `mockup/`.

AS MORDIDAS: «Salvar Perfil» devolvido a uma cópia do mockup reprova; um rótulo citado
que nenhuma página mostra reprova; uma linha da `DIVIDA` que nenhuma página escreve
reprova; e o valor do selo da 08 (`<b>` no `.est`, que é item de flex) é peça própria,
como a régua irmã da primeira letra o lê.
"""
from __future__ import annotations

import importlib.util
import pathlib
import shutil
import sys

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
for _p in (str(RAIZ / "src"), str(RAIZ / "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

_SPEC = importlib.util.spec_from_file_location(
    "_regua_da_primeira_letra", RAIZ / "scripts" / "check_so_a_primeira_letra.py")
assert _SPEC and _SPEC.loader
regua = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(regua)


def _dez(raiz: pathlib.Path) -> list[pathlib.Path]:
    paginas = sorted(p for p in raiz.glob("*.html") if regua.E_ABA.match(p.name))
    assert len(paginas) == 10, f"as dez abas viraram {len(paginas)} em {raiz}"
    return paginas


def test_as_dez_publicadas_passam(capsys: pytest.CaptureFixture[str]) -> None:
    assert regua.main([]) == 0, capsys.readouterr()


def test_as_dez_do_mockup_passam(capsys: pytest.CaptureFixture[str]) -> None:
    assert regua.main(["--bancada"]) == 0, capsys.readouterr()


@pytest.mark.parametrize("frase", ["Salvar perfil", "Abrir a Steam", "Modo Freestyle",
                                   "O DualSense no Linux"])
def test_aceita_a_primeira_e_o_nome_proprio(frase: str) -> None:
    assert regua.maiusculas_no_meio(frase, []) == []


@pytest.mark.parametrize(("frase", "acusada"), [("Salvar Perfil", "Perfil"),
                                                 ("Mapa das Conexões", "Conexões"),
                                                 ("Gestão de Controles", "Controles")])
def test_recusa_a_maiuscula_no_meio(frase: str, acusada: str) -> None:
    assert regua.maiusculas_no_meio(frase, []) == [acusada]


def test_salvar_perfil_devolvido_ao_mockup_reprova(tmp_path: pathlib.Path) -> None:
    """A mordida na página: a cópia do mockup com «Salvar Perfil» de volta é acusada."""
    for p in _dez(regua.BANCADA):
        shutil.copy(p, tmp_path / p.name)
    alvo = tmp_path / "10-perfis.html"
    texto = alvo.read_text(encoding="utf-8")
    assert "Salvar perfil" in texto
    alvo.write_text(texto.replace("Salvar perfil", "Salvar Perfil"), encoding="utf-8")

    achados = regua.censo(_dez(tmp_path))

    assert ("Perfil" in {palavra for nome, _, palavra, _ in achados
                         if nome == "10-perfis.html"}), achados


def test_o_rotulo_citado_que_nenhuma_pagina_mostra_reprova(
        monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(regua, "ROTULOS_CITADOS", [*regua.ROTULOS_CITADOS, "Rótulo Fantasma"])
    assert regua.rotulos_fantasmas(_dez(regua.PUBLICADO)) == ["Rótulo Fantasma"]


def test_a_divida_que_nenhuma_pagina_escreve_reprova(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(regua, "DIVIDA", {**regua.DIVIDA, "Linha Curada": "teste"})
    assert regua.dividas_mortas(_dez(regua.PUBLICADO)) == ["Linha Curada"]


def test_o_valor_do_selo_da_08_e_peca_propria() -> None:
    """«Analógico virtual <b>Apagado</b>»: o `<b>` do `.est` abre bloco (flex), e a régua
    irmã (`test_todo_texto_que_abre_uma_linha_comeca_com_maiuscula`) exige a maiúscula."""
    pagina = (regua.PUBLICADO / "08-conexoes.html").read_text(encoding="utf-8")
    assert "Analógico virtual <b>Apagado</b>" in pagina
    lidas = [f for _, f in regua.frases(pagina)]
    assert "Apagado" in lidas, [f for f in lidas if "Apagado" in f]
