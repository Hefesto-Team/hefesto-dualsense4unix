"""D-2611-O-PERFIL-ILEGIVEL-APARECE-COM-O-MOTIVO-E-SE-APAGA-PELO-ARQUIVO.

O arquivo de perfil que não abre aparece na lista e no `doctor --perfis` com o motivo em uma
frase, nenhum comando de perfil termina em traceback, e o `delete` apaga o arquivo pedido
(nunca o do `name` que o conteúdo diz), ilegível ou não, com a cópia no histórico.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from click.testing import Result
from typer.testing import CliRunner

from hefesto_dualsense4unix.cli.app import app
from hefesto_dualsense4unix.profiles import loader as loader_module

runner = CliRunner()

RUINS = ("quebrado", "vazio", "lista", "binario")  # (noqa-acento)


@pytest.fixture
def pasta(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    alvo = tmp_path / "profiles"
    alvo.mkdir()

    def _profiles_dir(ensure: bool = False) -> Path:
        if ensure:
            alvo.mkdir(parents=True, exist_ok=True)
        return alvo

    monkeypatch.setattr(loader_module, "profiles_dir", _profiles_dir)
    monkeypatch.setenv(loader_module.SEED_SKIP_ENV_VAR, "1")
    from hefesto_dualsense4unix.utils import session, xdg_paths

    cfg = tmp_path / "config"
    cfg.mkdir()

    def _config_dir(ensure: bool = False) -> Path:
        if ensure:
            cfg.mkdir(parents=True, exist_ok=True)
        return cfg

    monkeypatch.setattr(xdg_paths, "config_dir", _config_dir)
    monkeypatch.setattr(session, "config_dir", _config_dir)
    import hefesto_dualsense4unix.app.ipc_bridge as bridge

    monkeypatch.setattr(bridge, "_run_call", lambda *a, **k: {"active_profile": None})
    return alvo


def _perfil(nome: str = "Corrida", cor: tuple[int, int, int] = (1, 2, 3)) -> dict[str, Any]:
    return {"name": nome, "priority": 5,
            "match": {"type": "criteria", "window_class": [nome.lower()]},
            "leds": {"lightbar": list(cor)}}


def _com_os_ruins(pasta: Path) -> None:
    (pasta / "quebrado.json").write_text('{"name": "Quebrado", "mat', encoding="utf-8")
    (pasta / "vazio.json").write_text("", encoding="utf-8")
    (pasta / "lista.json").write_text("[1, 2]", encoding="utf-8")
    (pasta / "binario.json").write_bytes(b"\xff\xfe\x00\x01")
    (pasta / "futuro.json").write_text(
        json.dumps({**_perfil("Futuro"), "version": 2}), encoding="utf-8")
    (pasta / "campo_novo.json").write_text(
        json.dumps({**_perfil("Campo novo"), "campo_do_futuro": 1}), encoding="utf-8")
    (pasta / "bom.json").write_text(json.dumps(_perfil("Bom")), encoding="utf-8")


def _sem_traceback(res: Result) -> None:
    assert res.exception is None or isinstance(res.exception, SystemExit), repr(res.exception)
    assert "Traceback" not in res.output


@pytest.mark.parametrize("comando", ["show", "activate", "restore"])
@pytest.mark.parametrize("ruim", [*RUINS, "futuro"])
def test_cada_comando_com_arquivo_ruim_sai_com_a_frase_e_rc_1(
        comando: str, ruim: str, pasta: Path) -> None:
    """D-2611-O-PERFIL-ILEGIVEL-APARECE-COM-O-MOTIVO-E-SE-APAGA-PELO-ARQUIVO: sem traceback."""
    _com_os_ruins(pasta)
    res = runner.invoke(app, ["profile", comando, ruim])
    _sem_traceback(res)
    assert res.exit_code == 1, res.output
    if comando != "restore":
        assert ruim in res.output.lower(), res.output


def test_o_apply_de_arquivo_binario_sai_com_a_frase(tmp_path: Path, pasta: Path) -> None:
    """D-2611-O-PERFIL-ILEGIVEL-APARECE-COM-O-MOTIVO-E-SE-APAGA-PELO-ARQUIVO: apply binário."""
    binario = tmp_path / "binario.json"
    binario.write_bytes(b"\xff\xfe\x00\x01")
    res = runner.invoke(app, ["profile", "apply", "--file", str(binario)])
    _sem_traceback(res)
    assert res.exit_code == 1
    assert "binario.json" in res.output


@pytest.mark.parametrize("argumentos", [
    ["show", "a/b"], ["create", "!!!"], ["delete", "a/b", "--yes"],
    ["historico", "a/b"],  # (noqa-acento)
])
def test_o_nome_que_nao_serve_sai_com_a_frase(argumentos: list[str], pasta: Path) -> None:
    """D-2611-O-PERFIL-ILEGIVEL-APARECE-COM-O-MOTIVO-E-SE-APAGA-PELO-ARQUIVO: nome torto."""
    res = runner.invoke(app, ["profile", *argumentos])
    _sem_traceback(res)
    assert res.exit_code == 1, res.output


def test_a_lista_mostra_cada_ilegivel_com_o_motivo(pasta: Path) -> None:
    """D-2611-O-PERFIL-ILEGIVEL-APARECE-COM-O-MOTIVO-E-SE-APAGA-PELO-ARQUIVO: a lista."""
    _com_os_ruins(pasta)
    res = runner.invoke(app, ["profile", "list"])
    assert res.exit_code == 0, res.output
    saida = " ".join(res.output.split())
    for ruim in RUINS:
        assert f"{ruim}.json: ilegível:" in saida, saida
    assert "cortado ou inválido" in saida and "vazio" in saida and "UTF-8" in saida
    assert "Futuro" in saida and "versão mais nova" in saida
    assert "campo_novo.json: ilegível" not in saida and "bom.json: ilegível" not in saida

    como_json = json.loads(runner.invoke(app, ["profile", "list", "--json"]).output)
    ilegiveis = {x["arquivo"]: x["motivo"] for x in como_json if x.get("ilegivel")}
    assert set(ilegiveis) == {f"{r}.json" for r in RUINS}
    assert all(ilegiveis.values())


def test_o_doctor_de_perfis_da_um_fail_por_ilegivel_e_rc_1(pasta: Path) -> None:
    """D-2611-O-PERFIL-ILEGIVEL-APARECE-COM-O-MOTIVO-E-SE-APAGA-PELO-ARQUIVO: o doctor."""
    _com_os_ruins(pasta)
    res = runner.invoke(app, ["doctor", "--perfis"])
    _sem_traceback(res)
    assert res.exit_code == 1, res.output
    falhas = [linha for linha in res.output.splitlines() if "[FAIL]" in linha]
    for ruim in RUINS:
        assert sum(f"{ruim}.json: ilegível:" in linha for linha in falhas) == 1, res.output
    assert "profile restore" in res.output and "profile delete" in res.output


def test_o_doctor_de_perfis_sem_ilegivel_nao_inventa_falha(pasta: Path) -> None:
    """D-2611-O-PERFIL-ILEGIVEL-APARECE-COM-O-MOTIVO-E-SE-APAGA-PELO-ARQUIVO: nada a acusar."""
    (pasta / "bom.json").write_text(json.dumps(_perfil("Bom")), encoding="utf-8")
    res = runner.invoke(app, ["doctor", "--perfis"])
    assert "ilegível" not in res.output


@pytest.mark.parametrize("ruim", RUINS)
def test_o_ilegivel_se_apaga_pelo_arquivo_com_a_copia_no_historico(
        ruim: str, pasta: Path) -> None:
    """D-2611-O-PERFIL-ILEGIVEL-APARECE-COM-O-MOTIVO-E-SE-APAGA-PELO-ARQUIVO: apaga o ruim."""
    _com_os_ruins(pasta)
    bom = (pasta / "bom.json").read_bytes()
    bruto = (pasta / f"{ruim}.json").read_bytes()
    res = runner.invoke(app, ["profile", "delete", ruim, "--yes"])
    _sem_traceback(res)
    assert res.exit_code == 0, res.output
    assert not (pasta / f"{ruim}.json").exists()
    assert (pasta / "bom.json").read_bytes() == bom
    guardados = list((pasta / ".historico" / ruim).glob("*.json"))
    assert guardados and guardados[0].read_bytes() == bruto
    assert f"{ruim}.json" in res.output


def test_apagar_a_copia_deixa_o_original_byte_a_byte(pasta: Path) -> None:
    """D-2611-O-PERFIL-ILEGIVEL-APARECE-COM-O-MOTIVO-E-SE-APAGA-PELO-ARQUIVO: o pedido, só ele."""
    original = pasta / "corrida.json"
    original.write_text(json.dumps(_perfil("Corrida")), encoding="utf-8")
    copia = pasta / "corrida_copia.json"
    copia.write_text(json.dumps(_perfil("Corrida", (9, 9, 9))), encoding="utf-8")
    bruto = original.read_bytes()
    res = runner.invoke(app, ["profile", "delete", "corrida_copia", "--yes"])
    assert res.exit_code == 0, res.output
    assert not copia.exists()
    assert original.read_bytes() == bruto


def test_o_delete_nao_apaga_o_estilo_de_jogo_guardado_na_subpasta(pasta: Path) -> None:
    """D-2611-O-PERFIL-ILEGIVEL-APARECE-COM-O-MOTIVO-E-SE-APAGA-PELO-ARQUIVO: só a pasta dos perfis.

    O estilo de jogo que a migração dos gêneros guardou em ``estilos-de-jogo/`` não é perfil da
    lista: o ``delete`` pelo nome dele diz que o perfil não existe e o arquivo fica.
    """
    estilos = pasta / loader_module.ESTILOS_DE_JOGO_DIR_NAME
    estilos.mkdir()
    estilo = estilos / "esportes.json"
    estilo.write_text(json.dumps(_perfil("Esportes")), encoding="utf-8")
    bruto = estilo.read_bytes()
    res = runner.invoke(app, ["profile", "delete", "esportes", "--yes"])
    _sem_traceback(res)
    assert res.exit_code == 1, res.output
    assert estilo.read_bytes() == bruto
    with pytest.raises(FileNotFoundError):
        loader_module.delete_profile("esportes")
    assert estilo.read_bytes() == bruto


def test_o_restore_cura_o_arquivo_cortado_pelo_historico(pasta: Path) -> None:
    """D-2611-O-PERFIL-ILEGIVEL-APARECE-COM-O-MOTIVO-E-SE-APAGA-PELO-ARQUIVO: a cura do doctor."""
    from hefesto_dualsense4unix.profiles.loader import load_profile, save_profile
    from hefesto_dualsense4unix.profiles.schema import Profile

    save_profile(Profile.model_validate(_perfil("Corrida")))
    save_profile(Profile.model_validate(_perfil("Corrida", (4, 5, 6))))
    (pasta / "corrida.json").write_text('{"name": "Corr', encoding="utf-8")
    res = runner.invoke(app, ["profile", "restore", "corrida"])
    assert res.exit_code == 0, res.output
    assert load_profile("corrida").name == "Corrida"
