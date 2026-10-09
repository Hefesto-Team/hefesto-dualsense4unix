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


def test_os_tres_mapas_entram_na_leitura(tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch,
                                         capsys: pytest.CaptureFixture[str]) -> None:
    """«Mapear Entradas» devolvido a uma cópia do mapa do rádio reprova o `main`.

    MORDIDA: tire `mapas` de `paginas` no `main` da régua — este caso reprova.
    """
    bancada = tmp_path / "mockup"
    bancada.mkdir()
    for p in [*_dez(regua.BANCADA), *(regua.BANCADA / m for m in regua.MAPAS)]:
        shutil.copy(p, bancada / p.name)
    monkeypatch.setattr(regua, "BANCADA", bancada)
    monkeypatch.setattr(regua, "RAIZ", tmp_path)
    assert regua.main(["--bancada"]) == 0, capsys.readouterr()

    alvo = bancada / "mapa-do-radio.html"
    texto = alvo.read_text(encoding="utf-8")
    assert "Mapear entradas</a>" in texto
    alvo.write_text(texto.replace("Mapear entradas</a>", "Mapear Entradas</a>"), encoding="utf-8")

    assert regua.main(["--bancada"]) == 1
    assert "mapa-do-radio.html" in capsys.readouterr().out


def test_o_mapa_com_o_js_da_maiuscula_em_toda_palavra_reprova(tmp_path: pathlib.Path) -> None:
    """O JS de 26/09 (`emTitulo`) devolvido a uma cópia do mapa das portas é acusado.

    O texto parado da página não mostra o que o JS faz na pintura: a régua procura o JS.
    MORDIDA: esvazie `TITULO_EM_TODA_PALAVRA` (`re.compile(r"(?!)")`) — este caso reprova.
    """
    alvo = tmp_path / "mapa-das-portas.html"
    texto = (regua.BANCADA / "mapa-das-portas.html").read_text(encoding="utf-8")
    assert regua.titulo_em_toda_palavra([regua.BANCADA / "mapa-das-portas.html"]) == []
    alvo.write_text(texto.replace(
        "</script>", "function emTitulo(raiz) { if (!raiz) return; }\n</script>", 1),
        encoding="utf-8")
    assert regua.titulo_em_toda_palavra([alvo]) == ["mapa-das-portas.html"]
