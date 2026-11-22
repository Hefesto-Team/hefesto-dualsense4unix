"""O Freestyle não se apaga e renasce de fábrica se o arquivo faltar.

O botão «Modo Freestyle» pede o `freestyle.json` no disco: a remoção se recusa na função que a
linha de comando e a janela chamam, e a semeadura o recria sem olhar a marca. A pasta de perfis
e o `session.json` são do lar de mentira do conftest.
"""
from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from hefesto_dualsense4unix.cli.app import app
from hefesto_dualsense4unix.profiles import loader
from hefesto_dualsense4unix.profiles.schema import MatchAny, Profile
from hefesto_dualsense4unix.utils import session
from hefesto_dualsense4unix.utils.xdg_paths import profiles_dir

RAIZ = Path(__file__).resolve().parents[2]
FABRICA = RAIZ / "assets" / "profiles_default"
runner = CliRunner()


@pytest.fixture
def semeadura_ligada(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(loader.SEED_SKIP_ENV_VAR, raising=False)
    monkeypatch.setattr(loader, "_seed_attempted", False)
    monkeypatch.setattr(loader, "_DEFAULT_SEED_SOURCE_DIRS", (FABRICA,))
    monkeypatch.setattr(loader, "_talvez_semear_jogos", lambda: None)


def _processo_novo(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(loader, "_seed_attempted", False)


def _arquivo() -> Path:
    return profiles_dir() / loader.ARQUIVO_DO_PADRAO


def test_apagar_o_freestyle_se_recusa_com_uma_frase(semeadura_ligada: None) -> None:
    loader.load_all_profiles()
    loader.save_profile(Profile(name="Leitura", match=MatchAny(), priority=0))
    antes = _arquivo().read_bytes()

    for nome in ("Freestyle", "freestyle"):
        with pytest.raises(loader.OFreestyleNaoSeApagaError) as erro:
            loader.delete_profile(nome)
        assert "Freestyle não se apaga" in str(erro.value)

    assert _arquivo().read_bytes() == antes


def test_o_comando_recusa_apagar_o_freestyle_com_rc_1(semeadura_ligada: None) -> None:
    loader.load_all_profiles()
    loader.save_profile(Profile(name="Leitura", match=MatchAny(), priority=0))
    session.save_freestyle_ligado(False)
    session.save_last_profile("Leitura")
    session.save_active_marker("Leitura")

    resultado = runner.invoke(app, ["profile", "delete", "Freestyle", "--yes"])

    assert resultado.exit_code == 1
    assert "Freestyle não se apaga" in resultado.output
    assert "Traceback" not in resultado.output
    assert _arquivo().is_file()


def test_o_outro_perfil_continua_se_apagando(semeadura_ligada: None) -> None:
    loader.load_all_profiles()
    loader.save_profile(Profile(name="Leitura", match=MatchAny(), priority=0))

    loader.delete_profile("Leitura")

    assert not (profiles_dir() / "leitura.json").exists()


def test_o_arquivo_que_sumiu_renasce_no_processo_novo(
    semeadura_ligada: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    loader.load_all_profiles()
    marca = profiles_dir() / loader.SEED_MARKER_NAME
    assert loader.ARQUIVO_DO_PADRAO in marca.read_text(encoding="utf-8").splitlines()
    _arquivo().unlink()
    _processo_novo(monkeypatch)

    assert loader.o_perfil_de_fora_do_jogo() == "Freestyle"
    assert _arquivo().read_bytes() == (FABRICA / loader.ARQUIVO_DO_PADRAO).read_bytes()


def test_o_arquivo_que_sumiu_renasce_na_proxima_leitura_com_o_servico_em_pe(
    semeadura_ligada: None,
) -> None:
    loader.load_all_profiles()
    _arquivo().unlink()

    assert loader.o_perfil_de_fora_do_jogo() == "Freestyle"
    assert _arquivo().read_bytes() == (FABRICA / loader.ARQUIVO_DO_PADRAO).read_bytes()

    _arquivo().unlink()
    assert loader.load_profile("Freestyle").name == "Freestyle"


def test_a_marca_nao_cresce_a_cada_processo(
    semeadura_ligada: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    loader.load_all_profiles()
    marca = profiles_dir() / loader.SEED_MARKER_NAME
    antes = marca.read_text(encoding="utf-8")
    for _ in range(3):
        _arquivo().unlink()
        _processo_novo(monkeypatch)
        loader.load_all_profiles()
    assert marca.read_text(encoding="utf-8") == antes


def test_o_freestyle_do_usuario_nao_e_sobrescrito_pela_fabrica(
    semeadura_ligada: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    loader.load_all_profiles()
    do_usuario = _arquivo().read_text(encoding="utf-8").replace('"priority": 0', '"priority": 7')
    _arquivo().write_text(do_usuario, encoding="utf-8")
    marca = profiles_dir() / loader.SEED_MARKER_NAME
    antes = marca.read_text(encoding="utf-8")
    _processo_novo(monkeypatch)

    loader.load_all_profiles()

    assert _arquivo().read_text(encoding="utf-8") == do_usuario
    assert marca.read_text(encoding="utf-8") == antes


def test_o_perfil_opcional_apagado_continua_valendo_pela_marca(
    semeadura_ligada: None, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    fonte = tmp_path / "fabrica"
    fonte.mkdir()
    bruto = (FABRICA / loader.ARQUIVO_DO_PADRAO).read_text(encoding="utf-8")
    (fonte / loader.ARQUIVO_DO_PADRAO).write_text(bruto, encoding="utf-8")
    (fonte / "opcional.json").write_text(
        bruto.replace('"Freestyle"', '"Opcional"'), encoding="utf-8")
    monkeypatch.setattr(
        loader, "ARQUIVOS_DE_FABRICA", (loader.ARQUIVO_DO_PADRAO, "opcional.json"))
    pasta = profiles_dir(ensure=True)

    assert sorted(loader.seed_default_presets(pasta, [fonte])) == [
        loader.ARQUIVO_DO_PADRAO, "opcional.json"]
    (pasta / "opcional.json").unlink()
    (pasta / loader.ARQUIVO_DO_PADRAO).unlink()

    assert loader.seed_default_presets(pasta, [fonte]) == [loader.ARQUIVO_DO_PADRAO]
    assert not (pasta / "opcional.json").exists()
