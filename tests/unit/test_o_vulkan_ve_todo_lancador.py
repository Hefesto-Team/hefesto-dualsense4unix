"""O-VULKAN-VE-TODO-LANCADOR-E-DIZ-O-ESTADO-01 — as duas perguntas de produto."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from tests.conftest import exigir_gi_real

exigir_gi_real("importa `interface.pacotes`, que carrega o GTK")

from hefesto_dualsense4unix.integrations import camadas_vulkan as cv
from hefesto_dualsense4unix.interface.pacotes.a09_sistema import (
    SELO_INFORMATIVO,
    linha_da_sobreposicao_vulkan,
)


def _prefixo(raiz: Path, *partes: str) -> Path:
    alvo = raiz.joinpath(*partes)
    (alvo / "pfx").mkdir(parents=True)
    (alvo / "pfx" / "system.reg").write_text("", encoding="utf-8")
    return alvo


def test_o_prefixo_do_lutris_entra_na_varredura(tmp_path: Path) -> None:
    """ARRANQUE a varredura por forma e este teste reprova."""
    nativo = _prefixo(tmp_path, ".local", "share", "lutris", "Um Jogo")
    flatpak = _prefixo(
        tmp_path, ".var", "app", "net.lutris.Lutris", "data", "lutris", "Outro")
    padrao = _prefixo(tmp_path, "Games", "Jogo na Raiz")
    achados = set(cv.prefixos_dos_lancadores(tmp_path))
    assert {nativo, flatpak, padrao} <= achados, (
        f"a varredura achou {achados} — faltou "
        f"{ {nativo, flatpak, padrao} - achados}")


def test_pasta_sem_pfx_nao_vira_prefixo(tmp_path: Path) -> None:
    """ARRANQUE o `is_file()` do `system.reg` e este teste reprova: metade de"""
    (tmp_path / "Games" / "uma pasta qualquer").mkdir(parents=True)
    (tmp_path / "Games" / "um arquivo solto.txt").write_text("", encoding="utf-8")
    assert cv.prefixos_dos_lancadores(tmp_path) == []


def test_o_mesmo_prefixo_nao_entra_duas_vezes(tmp_path: Path) -> None:
    """O Heroic declara o prefixo na config E ele mora sob `~/Games`: as duas"""
    import json

    alvo = _prefixo(tmp_path, "Games", "Heroic", "Prefixes", "O Jogo")
    conf = tmp_path / ".config" / "heroic" / "GamesConfig"
    conf.mkdir(parents=True)
    (conf / "x.json").write_text(
        json.dumps({"x": {"winePrefix": str(alvo)}}), encoding="utf-8")
    (tmp_path / ".config" / "heroic" / "config.json").write_text("{}", encoding="utf-8")
    achados = cv.prefixos_dos_lancadores(tmp_path)
    assert achados.count(alvo) <= 1, f"o prefixo entrou {achados.count(alvo)} vezes"


def test_a_varredura_nao_levanta_em_disco_hostil(tmp_path: Path) -> None:
    """NUNCA LEVANTA é contrato da função: ela roda no caminho do lançamento."""
    assert cv.prefixos_dos_lancadores(tmp_path / "nao-existe") == []


def test_a_raiz_gigante_nao_custa_o_censo(tmp_path: Path) -> None:
    """ARRANQUE o `_MAXIMO_DE_FILHOS_POR_RAIZ` e este teste reprova: uma pasta"""
    raiz = tmp_path / "Games"
    raiz.mkdir(parents=True)
    for n in range(cv._MAXIMO_DE_FILHOS_POR_RAIZ + 50):
        (raiz / f"{n:05d}.txt").write_text("", encoding="utf-8")
    assert cv.prefixos_dos_lancadores(tmp_path) == []
    assert cv._MAXIMO_DE_FILHOS_POR_RAIZ < 10_000


def _a_steam_instalou(casa: Path) -> None:
    """O manifesto que a Steam instala na pasta de camadas do usuário."""
    pasta = casa / "vulkan" / "implicit_layer.d"
    pasta.mkdir(parents=True, exist_ok=True)
    (pasta / "steamoverlay_x86_64.json").write_text("{}", encoding="utf-8")


def _texto() -> str | None:
    linha = linha_da_sobreposicao_vulkan()
    if linha is None:
        return None
    selo, texto = linha
    assert selo == SELO_INFORMATIVO, (
        "a linha não é informativa — um selo de falha sobre um FATO da máquina "
        "ensina que existia algo a corrigir")
    return texto


def test_a_linha_diz_a_escolha_que_chega_ao_jogo(tmp_path: Path) -> None:
    """ARRANQUE o `vulkan_corrigido()` da linha e este teste reprova."""
    import os

    _a_steam_instalou(Path(os.environ["XDG_DATA_HOME"]))
    cv.gravar_camadas_da_steam_fora(False)
    assert _texto() == cv.frase_do_estado(False)
    cv.gravar_camadas_da_steam_fora(True)
    assert _texto() == cv.frase_do_estado(True)
    assert cv.frase_do_estado(True) != cv.frase_do_estado(False)


def test_sem_as_camadas_da_steam_a_linha_nao_sai() -> None:
    """Sem a Steam neste computador, o botão não tem o que tirar — nada a dizer."""
    assert cv.a_steam_instalou_as_camadas() is False
    assert _texto() is None


def test_a_frase_da_linha_tem_um_dono_so(monkeypatch: pytest.MonkeyPatch) -> None:
    """ARRANQUE o `cv.frase_do_estado` da linha e este teste reprova."""
    monkeypatch.setattr(cv, "a_steam_instalou_as_camadas", lambda home=None: True)
    monkeypatch.setattr(cv, "frase_do_estado", lambda fora: f"DONO {fora}")
    assert _texto() == "DONO False"


def test_o_exame_nao_cai_por_causa_de_um_vulkan(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """ARRANQUE o `try/except` e este teste reprova: um disco hostil"""
    def explode(*a: Any, **k: Any) -> Any:
        raise OSError("disco hostil")

    monkeypatch.setattr(cv, "a_steam_instalou_as_camadas", explode)
    assert linha_da_sobreposicao_vulkan() is None


def test_a_linha_entra_no_exame() -> None:
    """A régua de LIGAÇÃO: uma linha que ninguém soma é trabalho que não chega"""
    import inspect

    from hefesto_dualsense4unix.interface.pacotes import a09_sistema

    fonte = inspect.getsource(a09_sistema._achados)
    assert "linha_da_sobreposicao_vulkan" in fonte, (
        "a linha existe e o exame não a soma")
