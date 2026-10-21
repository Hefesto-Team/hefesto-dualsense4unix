"""O `profile delete` recusa o perfil que está valendo, com a frase da aba Perfis.

A O-PERFIL-ATIVO-APAGADO-SOLTA-O-REMAP-E-O-ROTEADOR-01 (17/10/2026): a linha de comando apagava o
arquivo do perfil ativo com o daemon no ar, e o daemon seguia aplicando o remap e o roteador dele
até a próxima troca. A tela já recusava (`a10_perfis.remover`); agora as duas passam pelo mesmo
dono, `profiles_actions.frase_da_remocao_do_perfil_ativo`.

MORDIDA: tire a pergunta (`aviso = ...` e o `if aviso`) do `cmd_delete` e o primeiro e o segundo
testes reprovam (o arquivo some e a saída é 0).
"""
from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from tests.conftest import exigir_gi_real

exigir_gi_real("importa a linha de comando e o `app.actions`, e um deles carrega o GTK")

from hefesto_dualsense4unix.app.actions.profiles_actions import _AVISO_DA_REMOCAO_DO_ATIVO
from hefesto_dualsense4unix.cli import cmd_profile
from hefesto_dualsense4unix.cli.app import app
from hefesto_dualsense4unix.profiles import loader as loader_module
from hefesto_dualsense4unix.profiles.loader import save_profile
from hefesto_dualsense4unix.profiles.schema import MatchCriteria, Profile
from hefesto_dualsense4unix.utils import session

runner = CliRunner()


@pytest.fixture
def perfis(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    alvo = tmp_path / "profiles"
    alvo.mkdir()
    monkeypatch.setattr(loader_module, "profiles_dir", lambda ensure=False: alvo)
    monkeypatch.setenv(loader_module.SEED_SKIP_ENV_VAR, "1")
    for nome in ("ativo", "outro"):
        save_profile(Profile(name=nome, match=MatchCriteria(window_class=[nome])))
    return alvo


def _daemon_de_papel(monkeypatch: pytest.MonkeyPatch, ativo: str | None) -> None:
    estado = None if ativo is None else {"active_profile": ativo}
    monkeypatch.setattr(cmd_profile, "_estado_do_daemon", lambda: estado)


def _primeira_linha_do_aviso() -> str:
    return _AVISO_DA_REMOCAO_DO_ATIVO.splitlines()[0]


def test_com_o_daemon_no_ar_o_ativo_e_recusado(
    perfis: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    _daemon_de_papel(monkeypatch, "ativo")
    saida = runner.invoke(app, ["profile", "delete", "ativo", "--yes"])
    assert saida.exit_code == 1
    assert _primeira_linha_do_aviso() in saida.output
    assert (perfis / "ativo.json").exists()


def test_sem_resposta_o_marcador_em_disco_tambem_recusa(
    perfis: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Daemon fora do ar: o marcador diz quem vale, como na tela."""
    _daemon_de_papel(monkeypatch, None)
    session.gravar_a_escolha("ativo")
    saida = runner.invoke(app, ["profile", "delete", "ativo", "--yes"])
    assert saida.exit_code == 1
    assert (perfis / "ativo.json").exists()


def test_o_outro_perfil_apaga_e_sai_da_memoria(
    perfis: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    _daemon_de_papel(monkeypatch, "ativo")
    session.lembrar_o_ultimo_jogo("outro")
    saida = runner.invoke(app, ["profile", "delete", "outro", "--yes"])
    assert saida.exit_code == 0, saida.output
    assert not (perfis / "outro.json").exists()
    assert session._ultimo_jogo_cru() is None
