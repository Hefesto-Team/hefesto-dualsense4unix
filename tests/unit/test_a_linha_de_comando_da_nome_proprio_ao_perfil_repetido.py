"""D-2611-A-LINHA-DE-COMANDO-PERGUNTA-AO-MESMO-DONO-SE-O-NOME-DO-PERFIL-ESTA-LIVRE.

`profile create|apply|save` perguntam a `loader.nome_ocupado` (o critério do `nome_livre` da
janela): o perfil legível e o arquivo ilegível do mesmo nome ocupam o nome. O `apply` de nome
repetido e conteúdo diferente grava em «Nome 2»; só o `--force` grava por cima.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from hefesto_dualsense4unix.cli.app import app
from hefesto_dualsense4unix.profiles import loader as loader_module

runner = CliRunner()


@pytest.fixture
def pasta(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    alvo = tmp_path / "profiles"
    alvo.mkdir()

    def _profiles_dir(ensure: bool = False) -> Path:
        if ensure:
            alvo.mkdir(parents=True, exist_ok=True)
        return alvo

    monkeypatch.setattr(loader_module, "profiles_dir", _profiles_dir)
    from hefesto_dualsense4unix.utils import session, xdg_paths

    cfg = tmp_path / "config"
    cfg.mkdir()

    def _config_dir(ensure: bool = False) -> Path:
        if ensure:
            cfg.mkdir(parents=True, exist_ok=True)
        return cfg

    monkeypatch.setattr(xdg_paths, "config_dir", _config_dir)
    monkeypatch.setattr(session, "config_dir", _config_dir)
    return alvo


@pytest.fixture
def ipc(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, dict[str, Any]]]:
    chamadas: list[tuple[str, dict[str, Any]]] = []

    def _run_call(method: str, params: dict[str, Any] | None = None,
                  timeout: float | None = None) -> Any:
        chamadas.append((method, dict(params or {})))
        return {"active_profile": (params or {}).get("name")}

    import hefesto_dualsense4unix.app.ipc_bridge as bridge

    monkeypatch.setattr(bridge, "_run_call", _run_call)
    return chamadas


def _perfil(cor: list[int], nome: str = "Corrida") -> dict[str, Any]:
    return {"name": nome, "priority": 5, "match": {"type": "criteria", "window_class": ["corrida"]},
            "leds": {"lightbar": cor}}


def _escreve(caminho: Path, dados: dict[str, Any]) -> Path:
    caminho.write_text(json.dumps(dados), encoding="utf-8")
    return caminho


def _original(pasta: Path) -> tuple[Path, bytes]:
    arquivo = _escreve(pasta / "corrida.json", _perfil([1, 2, 3]))
    return arquivo, arquivo.read_bytes()


def test_o_apply_de_nome_repetido_e_conteudo_diferente_ganha_nome_proprio(
        tmp_path: Path, pasta: Path, ipc: list[tuple[str, dict[str, Any]]]) -> None:
    """D-2611-A-LINHA-DE-COMANDO-PERGUNTA-AO-MESMO-DONO-SE-O-NOME-DO-PERFIL-ESTA-LIVRE: «Nome 2»."""
    arquivo, antes = _original(pasta)
    novo = _escreve(tmp_path / "novo.json", _perfil([9, 9, 9]))
    res = runner.invoke(app, ["profile", "apply", "--file", str(novo)])
    assert res.exit_code == 0, res.output
    assert arquivo.read_bytes() == antes
    copia = json.loads((pasta / "corrida_2.json").read_text(encoding="utf-8"))
    assert copia["name"] == "Corrida 2" and copia["leds"]["lightbar"] == [9, 9, 9]
    assert ipc == [("profile.switch", {"name": "Corrida 2"})]


def test_o_apply_com_force_grava_por_cima(
        tmp_path: Path, pasta: Path, ipc: list[tuple[str, dict[str, Any]]]) -> None:
    """D-2611-A-LINHA-DE-COMANDO-PERGUNTA-AO-MESMO-DONO-SE-O-NOME-DO-PERFIL-ESTA-LIVRE: --force."""
    arquivo, antes = _original(pasta)
    novo = _escreve(tmp_path / "novo.json", _perfil([9, 9, 9]))
    res = runner.invoke(app, ["profile", "apply", "--file", str(novo), "--force"])
    assert res.exit_code == 0, res.output
    assert arquivo.read_bytes() != antes
    assert json.loads(arquivo.read_text(encoding="utf-8"))["leds"]["lightbar"] == [9, 9, 9]
    assert not (pasta / "corrida_2.json").exists()


def test_o_apply_do_perfil_igual_ao_do_disco_nao_cria_copia(
        tmp_path: Path, pasta: Path, ipc: list[tuple[str, dict[str, Any]]]) -> None:
    """D-2611-A-LINHA-DE-COMANDO-PERGUNTA-AO-MESMO-DONO-SE-O-NOME-DO-PERFIL-ESTA-LIVRE: igual."""
    arquivo, antes = _original(pasta)
    igual = _escreve(tmp_path / "igual.json", _perfil([1, 2, 3]))
    res = runner.invoke(app, ["profile", "apply", "--file", str(igual)])
    assert res.exit_code == 0, res.output
    assert arquivo.read_bytes() == antes
    assert not (pasta / "corrida_2.json").exists()
    assert ipc == [("profile.switch", {"name": "Corrida"})]


def test_o_arquivo_ilegivel_do_mesmo_nome_ocupa_o_nome(
        tmp_path: Path, pasta: Path, ipc: list[tuple[str, dict[str, Any]]]) -> None:
    """D-2611-A-LINHA-DE-COMANDO-PERGUNTA-AO-MESMO-DONO-SE-O-NOME-DO-PERFIL-ESTA-LIVRE: ilegível."""
    quebrado = pasta / "corrida.json"
    quebrado.write_text('{"name": "Corrida", "mat', encoding="utf-8")
    antes = quebrado.read_bytes()

    res = runner.invoke(app, ["profile", "create", "Corrida", "--manual"])
    assert res.exit_code == 1, res.output
    assert quebrado.read_bytes() == antes

    novo = _escreve(tmp_path / "novo.json", _perfil([9, 9, 9]))
    res = runner.invoke(app, ["profile", "apply", "--file", str(novo)])
    assert res.exit_code == 0, res.output
    assert quebrado.read_bytes() == antes
    assert (pasta / "corrida_2.json").exists()

    res = runner.invoke(app, ["profile", "create", "Corrida", "--manual", "--force"])
    assert res.exit_code == 0, res.output
    assert quebrado.read_bytes() != antes


def test_o_create_por_cima_do_perfil_de_mesmo_nome_pede_force(pasta: Path) -> None:
    """D-2611-A-LINHA-DE-COMANDO-PERGUNTA-AO-MESMO-DONO-SE-O-NOME-DO-PERFIL-ESTA-LIVRE: create."""
    arquivo, antes = _original(pasta)
    res = runner.invoke(app, ["profile", "create", "Corrida", "--manual"])
    assert res.exit_code == 1, res.output
    assert arquivo.read_bytes() == antes
    res = runner.invoke(app, ["profile", "create", "Corrida", "--manual", "--force"])
    assert res.exit_code == 0, res.output
    assert arquivo.read_bytes() != antes


def test_o_save_do_perfil_de_mesmo_nome_segue_atualizando(
        pasta: Path, ipc: list[tuple[str, dict[str, Any]]]) -> None:
    """D-2611-A-LINHA-DE-COMANDO-PERGUNTA-AO-MESMO-DONO-SE-O-NOME-DO-PERFIL-ESTA-LIVRE: save."""
    _original(pasta)
    from hefesto_dualsense4unix.utils import xdg_paths

    (xdg_paths.config_dir(ensure=True) / "active_profile.txt").write_text(
        "Corrida\n", encoding="utf-8")
    res = runner.invoke(app, ["profile", "save", "Corrida", "--from-active"])
    assert res.exit_code == 0, res.output

    ilegivel = pasta / "outro.json"
    ilegivel.write_text("{", encoding="utf-8")
    res = runner.invoke(app, ["profile", "save", "outro", "--from-active"])
    assert res.exit_code == 1, res.output
    assert ilegivel.read_text(encoding="utf-8") == "{"
