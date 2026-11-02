"""O ``mod de-fabrica`` anota o gesto como os outros comandos que mudam o lar.

A sprint é a O-MOD-DE-FABRICA-ANOTA-O-GESTO-COMO-OS-OUTROS-COMANDOS-01. O ``de-fabrica`` escreve
no lar por dois caminhos próprios: o ``mods-de-fabrica.json`` (as trazidas e as revistas) e o
endereço novo no ``mods.json``. Cada um anota, antes de tocar o disco, a linha
``[gesto] mod de-fabrica <id>`` com o caminho que toca, e o canário rebaixa a aviso só essa
escrita. Dois lares de mentira, como na régua do canário: ``real`` é o que o canário vigia, e o
outro é o dos testes. Extensões FALSAS, de tema e sem processo; o endereço é ``.invalid``.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.mods import de_fabrica_por_endereco as de_fabrica
from hefesto_dualsense4unix.mods import instalador
from tests.unit.test_o_canario_sabe_do_gesto_da_linha_de_comando import (
    MOD,
    PRODUTO,
    _armar,
    _diario,
    _fechar,
    _fonte,
    _mod,
    _morar_em,
    _portao,
)

ANTIGO = "https://exemplo.invalid/antigo/brilho-falso.git"
NOVO = "https://exemplo.invalid/novo/brilho-falso.git"


def _nao_instala(*_a: Any, **_k: Any) -> Any:
    raise AssertionError("o de-fabrica pediu instalação de uma extensão que já estava")


def _nao_liga(*_a: Any, **_k: Any) -> Any:
    raise AssertionError("o de-fabrica pediu para ligar uma extensão que não nasceu desligada")


def _lista(raiz: Path, **campos: Any) -> Path:
    arquivo = raiz / "de-fabrica-falsa.json"
    arquivo.write_text(json.dumps({"extensoes": [  # (noqa-acento)
        {"id": MOD, "endereco": NOVO, "ligar": False, **campos}]}), encoding="utf-8")
    return arquivo


def _trazer(lista: Path) -> list[de_fabrica.Feito]:
    return de_fabrica.trazer(arquivo=lista, instalar_=_nao_instala, ligar_=_nao_liga)


@pytest.fixture
def real(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    lar = tmp_path / "real"
    (lar / ".config" / PRODUTO / "profiles").mkdir(parents=True)
    (lar / ".local" / "state" / PRODUTO).mkdir(parents=True)
    (lar / "run").mkdir()
    _morar_em(lar, monkeypatch)
    _mod("instalar", str(_fonte(tmp_path)))
    _diario(lar).unlink(missing_ok=True)
    return lar


def _vinda_do_endereco_antigo(lar: Path) -> instalador.Lugares:
    lugares = instalador.Lugares.do_xdg()
    registro = instalador.ler_registro(lugares.registro)
    registro[MOD].origem = "comunidade"
    registro[MOD].endereco = ANTIGO
    instalador.gravar_registro(lugares.registro, registro)
    trazidas = lugares.registro.with_name(de_fabrica.TRAZIDAS)
    trazidas.write_text(json.dumps({"trazidas": [MOD], de_fabrica.REVISTAS: [MOD]}),
                        encoding="utf-8")
    return lugares


def _gestos(lar: Path) -> list[tuple[str, list[str]]]:
    linhas = _diario(lar).read_text(encoding="utf-8").splitlines() if _diario(lar).exists() else []
    return [(linha.split(" ", 2)[2].split(" → ")[0], json.loads(linha.split(" → ", 1)[1]))
            for linha in linhas]


def test_a_trazida_anota_o_gesto_com_o_arquivo_das_trazidas(
    real: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    lugares = instalador.Lugares.do_xdg()
    trazidas = lugares.registro.with_name(de_fabrica.TRAZIDAS)
    assert not trazidas.exists()
    _armar(real, monkeypatch)

    feitos = _trazer(_lista(tmp_path))

    assert [f.o_que for f in feitos] == ["ja_estava"], feitos
    assert trazidas.exists(), "instrumento inválido: o de-fabrica não gravou a trazida"
    status, saida = _fechar(capsys)
    assert status == 0 and _portao(saida) == [], saida
    assert f"gesto: [gesto] mod de-fabrica {MOD}" in saida, saida
    assert _gestos(real) == [(f"[gesto] mod de-fabrica {MOD}", [str(trazidas)])], _gestos(real)


def test_o_endereco_novo_anota_o_gesto_com_o_registro(
    real: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    lugares = _vinda_do_endereco_antigo(real)
    _armar(real, monkeypatch)

    feitos = _trazer(_lista(tmp_path, enderecos_antigos=[ANTIGO]))

    assert [f.o_que for f in feitos] == ["endereco_novo"], feitos
    assert instalador.ler_registro(lugares.registro)[MOD].endereco == NOVO
    status, saida = _fechar(capsys)
    assert status == 0 and _portao(saida) == [], saida
    assert "mods.json" in saida and f"gesto: [gesto] mod de-fabrica {MOD}" in saida, saida
    assert _gestos(real) == [(f"[gesto] mod de-fabrica {MOD}", [str(lugares.registro)])], (
        _gestos(real))


def test_o_que_nada_muda_nao_anota(real: Path, tmp_path: Path,
                                   monkeypatch: pytest.MonkeyPatch) -> None:
    _vinda_do_endereco_antigo(real)
    _armar(real, monkeypatch)

    assert [f.o_que for f in _trazer(_lista(tmp_path))] == ["ja_estava"]
    assert _gestos(real) == [], "o de-fabrica anotou um gesto sem escrever nada"


def test_cada_escrita_anota_antes_de_tocar_o_disco(
    real: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    lugares = instalador.Lugares.do_xdg()
    trazidas = lugares.registro.with_name(de_fabrica.TRAZIDAS)
    gravados: list[tuple[str, list[str]]] = []
    original = instalador.gravar_registro

    def gravar(caminho: Path, registro: dict[str, Any]) -> None:
        gravados.append(("mods.json", [g for g, _c in _gestos(real)]))
        original(caminho, registro)

    monkeypatch.setattr(de_fabrica, "gravar_registro", gravar)
    _vinda_do_endereco_antigo(real).registro.with_name(de_fabrica.TRAZIDAS).unlink()
    _diario(real).unlink(missing_ok=True)
    real_replace = Path.replace

    def trocar(self: Path, alvo: Any) -> Any:
        if Path(alvo) == trazidas:
            gravados.append((trazidas.name, [g for g, _c in _gestos(real)]))
        return real_replace(self, alvo)

    monkeypatch.setattr(Path, "replace", trocar)

    _trazer(_lista(tmp_path, enderecos_antigos=[ANTIGO]))

    gesto = f"[gesto] mod de-fabrica {MOD}"
    assert gravados == [("mods.json", [gesto]), (trazidas.name, [gesto, gesto])], gravados
