"""O-ARQUIVO-DE-MASCARAS-ILEGIVEL-NAO-SE-SOBRESCREVE-CALADO-01.

O ``controller_masks.json`` que existe e não se lê (truncado, bytes que não são
texto, documento que não é objeto) não vale como ausente: a carga avisa no
diário, e a primeira escrita guarda o original ao lado
(``controller_masks.json.ilegivel-<data>``) antes de gravar a escolha nova. O
arquivo ausente continua sendo o começo limpo, sem aviso.

Tudo num ``config_dir`` de mentira em ``tmp_path``.
"""
from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
import structlog

from hefesto_dualsense4unix.daemon.subsystems import external_mask as em
from hefesto_dualsense4unix.daemon.subsystems.external_mask import (
    FLAVOR_FIELD,
    IDENTITY_FIELD,
    MASKS_FIELD,
    SUFIXO_DO_ILEGIVEL,
    ExternalMaskRegistry,
)

MAC_1 = "aa:bb:cc:00:00:01"
MAC_2 = "aa:bb:cc:00:00:02"
MAC_3 = "aa:bb:cc:00:00:03"


@pytest.fixture
def casa(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """O ``config_dir`` de mentira, com a guarda que sai se ele escapar do tmp."""
    from hefesto_dualsense4unix.utils import xdg_paths

    alvo = tmp_path / "config"

    def _config_dir(ensure: bool = False) -> Path:
        if ensure:
            alvo.mkdir(parents=True, exist_ok=True)
        return alvo

    monkeypatch.setattr(xdg_paths, "config_dir", _config_dir)
    if not str(ExternalMaskRegistry._path()).startswith(str(tmp_path)):
        pytest.exit("a régua ia escrever no config_dir de verdade", returncode=3)
    em._zerar_registro_de_mascaras()
    return alvo


def _arquivo(casa: Path) -> Path:
    return casa / "controller_masks.json"


def _guardados(casa: Path) -> list[Path]:
    return sorted(p for p in casa.iterdir() if SUFIXO_DO_ILEGIVEL in p.name)


def _avisos(logs: Iterable[Mapping[str, Any]]) -> list[Any]:
    return [e["event"] for e in logs if e.get("log_level") == "warning"]


def _o_arquivo_com_duas_escolhas(casa: Path) -> str:
    r = ExternalMaskRegistry()
    assert r.set_mask(MAC_1, "dualsense")
    assert r.set_mask(MAC_2, "nintendo")
    return _arquivo(casa).read_text(encoding="utf-8")


def _a_escolha_seguinte(casa: Path) -> tuple[ExternalMaskRegistry, list[Any]]:
    with structlog.testing.capture_logs() as logs:
        r = ExternalMaskRegistry()
        r.load()
        assert r.set_mask(MAC_3, "xbox")
    return r, _avisos(logs)


def test_o_arquivo_truncado_avisa_e_o_original_fica_guardado_ao_lado(casa: Path) -> None:
    inteiro = _o_arquivo_com_duas_escolhas(casa)
    truncado = inteiro[: len(inteiro) // 2]
    _arquivo(casa).write_text(truncado, encoding="utf-8")

    r, avisos = _a_escolha_seguinte(casa)

    assert "external_mascaras_ilegivel" in avisos, f"a carga não avisou: {avisos}"
    assert "external_mascaras_ilegivel_guardado" in avisos, f"a escrita não avisou: {avisos}"
    guardados = _guardados(casa)
    assert len(guardados) == 1, (
        f"o original não ficou ao lado: {sorted(p.name for p in casa.iterdir())}"
    )
    assert guardados[0].read_text(encoding="utf-8") == truncado, "o original mudou ao ser guardado"

    novo = json.loads(_arquivo(casa).read_text(encoding="utf-8"))
    entradas = {e[IDENTITY_FIELD]: e[FLAVOR_FIELD] for e in novo[MASKS_FIELD]}
    assert entradas == {"aabbcc000003": "xbox"}, "a escolha nova não foi gravada"
    assert r.snapshot() == {"aabbcc000003": "xbox"}


def test_o_documento_que_nao_e_objeto_e_ilegivel_e_fica_guardado(casa: Path) -> None:
    casa.mkdir(parents=True, exist_ok=True)
    _arquivo(casa).write_text('["aabbcc000001", "dualsense"]', encoding="utf-8")

    _, avisos = _a_escolha_seguinte(casa)

    assert "external_mascaras_ilegivel" in avisos
    guardados = _guardados(casa)
    assert [g.read_text(encoding="utf-8") for g in guardados] == [
        '["aabbcc000001", "dualsense"]'
    ]


def test_os_bytes_que_nao_sao_texto_ficam_guardados(casa: Path) -> None:
    casa.mkdir(parents=True, exist_ok=True)
    _arquivo(casa).write_bytes(b"\xff\xfe\x00{")

    _, avisos = _a_escolha_seguinte(casa)

    assert "external_mascaras_ilegivel" in avisos
    assert [g.read_bytes() for g in _guardados(casa)] == [b"\xff\xfe\x00{"]


def test_dois_ilegiveis_no_mesmo_segundo_nao_se_apagam(
    casa: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    relogio_parado = SimpleNamespace(strftime=lambda _fmt: "20261010-120000")
    monkeypatch.setattr(em, "time", relogio_parado)
    casa.mkdir(parents=True, exist_ok=True)
    for conteudo in ("{um", "{dois"):
        _arquivo(casa).write_text(conteudo, encoding="utf-8")
        _a_escolha_seguinte(casa)

    assert sorted(g.read_text(encoding="utf-8") for g in _guardados(casa)) == ["{dois", "{um"]


def test_sem_poder_guardar_o_ilegivel_nada_se_escreve(
    casa: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    casa.mkdir(parents=True, exist_ok=True)
    _arquivo(casa).write_text("{quebrado", encoding="utf-8")

    def _recusa(_caminho: Path) -> Path:
        raise PermissionError("somente leitura")

    monkeypatch.setattr(ExternalMaskRegistry, "_guardar_o_ilegivel", staticmethod(_recusa))
    _, avisos = _a_escolha_seguinte(casa)

    assert "external_mascaras_ilegivel_nao_guardado" in avisos
    assert _arquivo(casa).read_text(encoding="utf-8") == "{quebrado"


def test_o_arquivo_ausente_e_o_comeco_limpo_sem_aviso(casa: Path) -> None:
    _, avisos = _a_escolha_seguinte(casa)

    assert avisos == []
    assert _guardados(casa) == []
    novo = json.loads(_arquivo(casa).read_text(encoding="utf-8"))
    assert [e[IDENTITY_FIELD] for e in novo[MASKS_FIELD]] == ["aabbcc000003"]
