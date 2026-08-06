"""CLI do histórico de perfis e do `doctor --perfis`.

PERFIL-SEM-RASTRO-01 (histórico/restauração) e PERFIL-NASCE-CERTO-01/E4 (o
detector de armadilha). Um backup que ela não consegue restaurar sozinha não é
backup; um detector que não aparece em lugar nenhum não detecta nada.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from hefesto_dualsense4unix.cli import cmd_doctor
from hefesto_dualsense4unix.cli.app import app
from hefesto_dualsense4unix.profiles import loader as loader_module
from hefesto_dualsense4unix.profiles.loader import listar_historico, save_profile
from hefesto_dualsense4unix.profiles.schema import (
    LedsConfig,
    Match,
    MatchAny,
    MatchCriteria,
    Profile,
)

runner = CliRunner()


@pytest.fixture
def dir_perfis(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    alvo = tmp_path / "profiles"
    alvo.mkdir()

    def _falso_profiles_dir(ensure: bool = False) -> Path:
        if ensure:
            alvo.mkdir(parents=True, exist_ok=True)
        return alvo

    monkeypatch.setattr(loader_module, "profiles_dir", _falso_profiles_dir)
    return alvo


def _perfil(nome: str = "pragmata", *, match: Match | None = None, priority: int = 10) -> Profile:
    return Profile(
        name=nome,
        match=match if match is not None else MatchCriteria(window_class=["pragmata"]),
        priority=priority,
        leds=LedsConfig(lightbar=(0, 0, 0)),
    )


# ---------------------------------------------------------------------------
# `profile historico` / `profile restore`  (noqa-acento: nomes de subcomando)
# ---------------------------------------------------------------------------


def test_historico_lista_as_versoes_com_match_e_prioridade(dir_perfis: Path) -> None:
    """A tabela mostra o que mudou entre as versões, não só nomes de arquivo."""
    save_profile(_perfil(priority=10))
    save_profile(_perfil(priority=191, match=MatchAny()))
    save_profile(_perfil(priority=20))

    resultado = runner.invoke(app, ["profile", "historico", "pragmata"])  # (noqa-acento)
    assert resultado.exit_code == 0, resultado.output
    saida = resultado.output
    assert "criteria" in saida
    assert "any" in saida
    assert "191" in saida


def test_historico_de_perfil_sem_versoes_explica(dir_perfis: Path) -> None:
    save_profile(_perfil())
    resultado = runner.invoke(app, ["profile", "historico", "pragmata"])  # (noqa-acento)
    assert resultado.exit_code == 0
    assert "sem histórico" in resultado.output


def test_restore_devolve_o_perfil_pela_linha_de_comando(dir_perfis: Path) -> None:
    """MORDIDA: sem o comando `restore`, o exit code vira 2 (comando ausente)."""
    save_profile(_perfil(priority=10))
    original = (dir_perfis / "pragmata.json").read_bytes()
    save_profile(_perfil(priority=191, match=MatchAny()))

    resultado = runner.invoke(app, ["profile", "restore", "pragmata"])
    assert resultado.exit_code == 0, resultado.output
    assert "restaurado" in resultado.output
    assert (dir_perfis / "pragmata.json").read_bytes() == original


def test_restore_em_versao_especifica(dir_perfis: Path) -> None:
    save_profile(_perfil(priority=10))
    save_profile(_perfil(priority=20))
    save_profile(_perfil(priority=30))
    primeira = listar_historico("pragmata")[0]

    resultado = runner.invoke(
        app, ["profile", "restore", "pragmata", "--em", primeira.name]
    )
    assert resultado.exit_code == 0, resultado.output
    dados = json.loads((dir_perfis / "pragmata.json").read_text(encoding="utf-8"))
    assert dados["priority"] == 10


def test_restore_sem_historico_sai_com_erro_e_aponta_o_caminho(dir_perfis: Path) -> None:
    save_profile(_perfil())
    resultado = runner.invoke(app, ["profile", "restore", "pragmata"])
    assert resultado.exit_code == 1
    assert "profile historico pragmata" in resultado.output  # (noqa-acento)


# ---------------------------------------------------------------------------
# `doctor --perfis`
# ---------------------------------------------------------------------------


def test_doctor_perfis_acusa_o_arranjo_corrompido(dir_perfis: Path) -> None:
    """O detector chega à tela, e o comando SAI 1 quando o achado é grave.

    MORDIDA: arrancar `_print_bloco_perfis` (ou o `raise typer.Exit`) faz o
    comando sair 0 num diretório em que o catch-all vence o perfil do jogo.
    """
    save_profile(_perfil("desktop_dela", match=MatchAny(), priority=100))
    save_profile(_perfil("pragmata", priority=80))

    resultado = runner.invoke(app, ["doctor", "--perfis"])
    assert resultado.exit_code == 1, resultado.output
    assert "[FAIL]" in resultado.output
    assert "desktop_dela" in resultado.output


def test_doctor_perfis_sai_zero_no_disco_saudavel(dir_perfis: Path) -> None:
    save_profile(_perfil("fallback", match=MatchAny(), priority=0))
    save_profile(_perfil("pragmata", priority=80))

    resultado = runner.invoke(app, ["doctor", "--perfis"])
    assert resultado.exit_code == 0, resultado.output
    assert "[ OK ]" in resultado.output


def test_doctor_perfis_nao_chama_o_doctor_sh_nem_o_ipc(
    dir_perfis: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`--perfis` é o caminho RÁPIDO: sem script de infra, sem daemon.

    MORDIDA: deixar o `--perfis` cair no fluxo completo faz o `subprocess.run`
    ser chamado e este teste reprova.
    """

    def _proibido(*_a: object, **_k: object) -> object:
        raise AssertionError("doctor --perfis não pode rodar subprocesso")

    monkeypatch.setattr(cmd_doctor.subprocess, "run", _proibido)
    save_profile(_perfil("pragmata", priority=80))

    resultado = runner.invoke(app, ["doctor", "--perfis"])
    assert resultado.exit_code == 0, resultado.output


def test_bloco_de_perfis_sobrevive_a_diretorio_ilegivel(
    dir_perfis: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Falha de leitura vira WARN — o doctor não pode explodir no meio."""

    def _explode() -> list[Profile]:
        raise OSError("permissão negada")

    monkeypatch.setattr(loader_module, "load_all_profiles", _explode)
    linhas, houve_erro = cmd_doctor._linhas_perfis()
    assert houve_erro is False
    assert linhas and linhas[0][0] == "[WARN]"
