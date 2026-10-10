"""A fábrica nova do Freestyle alcança a cópia de fábrica de ontem.

A-FABRICA-NOVA-DO-FREESTYLE-ALCANCA-A-COPIA-DE-FABRICA-DE-ONTEM-01 (09/10/2026). A migração
``o_freestyle_de_fabrica_nasce_ligado`` só trocava o ``freestyle.json`` que fosse igual a uma
fábrica de uma tupla escrita à mão, e a fábrica entregue hoje não está nela: na próxima mudança do
asset, a cópia intocada de hoje ficaria velha para sempre. A marca já guarda a impressão da fábrica
que esta máquina recebeu; agora a migração a compara com o arquivo.

TUDO É DE MENTIRA: as duas fábricas moram em ``tmp_path`` e o diretório de perfis é o do lar
isolado do conftest.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.profiles import loader
from hefesto_dualsense4unix.utils.xdg_paths import profiles_dir

ASSET_DE_HOJE = Path(__file__).resolve().parents[2] / "assets" / "profiles_default" / (
    "freestyle.json"
)


def _fabrica(pasta: Path, dados: dict[str, Any]) -> bytes:
    pasta.mkdir(parents=True, exist_ok=True)
    bruto = (json.dumps(dados, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    (pasta / loader.ARQUIVO_DO_PADRAO).write_bytes(bruto)
    return bruto


@pytest.fixture
def fabricas(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """A fábrica A (a de hoje) e a B (a próxima, com o brilho da barra mudado)."""
    hoje = json.loads(ASSET_DE_HOJE.read_text(encoding="utf-8"))
    proxima = json.loads(json.dumps(hoje))
    proxima["leds"]["lightbar_brightness"] = 0.5
    assert proxima != hoje
    monkeypatch.delenv(loader.SEED_SKIP_ENV_VAR, raising=False)
    monkeypatch.setattr(loader, "_talvez_semear_jogos", lambda: None)
    return {
        "A": (tmp_path / "fabrica-a", _fabrica(tmp_path / "fabrica-a", hoje)),
        "B": (tmp_path / "fabrica-b", _fabrica(tmp_path / "fabrica-b", proxima)),
        "mp": monkeypatch,
    }


def _carregar_com(fabricas: dict[str, Any], qual: str) -> list[str]:
    """Uma carga do processo novo, com a fábrica ``qual`` instalada."""
    mp: pytest.MonkeyPatch = fabricas["mp"]
    mp.setattr(loader, "_DEFAULT_SEED_SOURCE_DIRS", (fabricas[qual][0],))
    mp.setattr(loader, "_seed_attempted", False)
    return [p.name for p in loader.load_all_profiles()]


def _copias(pasta: Path) -> list[bytes]:
    historico = pasta / loader.HISTORICO_DIR_NAME / loader.SLUG_DO_PADRAO
    return [c.read_bytes() for c in sorted(historico.glob("*.json"))]


def test_a_fabrica_de_hoje_nao_esta_na_tupla_e_a_tupla_nao_cresce() -> None:
    hoje = json.loads(ASSET_DE_HOJE.read_text(encoding="utf-8"))
    assert hoje not in loader._FABRICAS_ANTERIORES_DO_FREESTYLE
    assert len(loader._FABRICAS_ANTERIORES_DO_FREESTYLE) == 6


def test_a_copia_intocada_da_fabrica_a_vira_a_fabrica_b(fabricas: dict[str, Any]) -> None:
    pasta = profiles_dir(ensure=True)
    _, bruto_a = fabricas["A"]
    _, bruto_b = fabricas["B"]

    assert _carregar_com(fabricas, "A") == [loader.NOME_DO_PADRAO]
    assert (pasta / loader.ARQUIVO_DO_PADRAO).read_bytes() == bruto_a

    assert _carregar_com(fabricas, "B") == [loader.NOME_DO_PADRAO]
    assert (pasta / loader.ARQUIVO_DO_PADRAO).read_bytes() == bruto_b
    assert _copias(pasta) == [bruto_a]

    assert _carregar_com(fabricas, "B") == [loader.NOME_DO_PADRAO]
    assert (pasta / loader.ARQUIVO_DO_PADRAO).read_bytes() == bruto_b
    assert _copias(pasta) == [bruto_a], "a segunda volta não faz nada"


def test_o_freestyle_com_um_ajuste_dela_fica_intocado(fabricas: dict[str, Any]) -> None:
    pasta = profiles_dir(ensure=True)
    _carregar_com(fabricas, "A")
    alvo = pasta / loader.ARQUIVO_DO_PADRAO
    dela = json.loads(alvo.read_text(encoding="utf-8"))
    dela["leds"]["lightbar"] = [255, 0, 128]
    bruto_dela = (json.dumps(dela, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    alvo.write_bytes(bruto_dela)

    _carregar_com(fabricas, "B")

    assert alvo.read_bytes() == bruto_dela
    assert _copias(pasta) == []


def test_a_copia_reformatada_da_fabrica_a_ainda_e_de_fabrica(fabricas: dict[str, Any]) -> None:
    """A impressão é do JSON lido: a mesma fábrica noutra formatação segue sendo a fábrica."""
    pasta = profiles_dir(ensure=True)
    _carregar_com(fabricas, "A")
    alvo = pasta / loader.ARQUIVO_DO_PADRAO
    alvo.write_text(json.dumps(json.loads(alvo.read_text(encoding="utf-8"))), encoding="utf-8")

    _carregar_com(fabricas, "B")

    assert alvo.read_bytes() == fabricas["B"][1]


def test_a_marca_de_antes_da_impressao_so_reconhece_a_tupla(fabricas: dict[str, Any]) -> None:
    """Marca ``done`` não guarda fábrica nenhuma: só a tupla diz o que é de fábrica."""
    pasta = profiles_dir(ensure=True)
    _carregar_com(fabricas, "A")
    (pasta / loader._FREESTYLE_DE_FABRICA_NASCE_LIGADO_MARKER).write_text(
        "done\n", encoding="utf-8")
    bruto = (pasta / loader.ARQUIVO_DO_PADRAO).read_bytes()

    _carregar_com(fabricas, "B")

    assert (pasta / loader.ARQUIVO_DO_PADRAO).read_bytes() == bruto
    assert _copias(pasta) == []
