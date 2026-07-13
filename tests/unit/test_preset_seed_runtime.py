"""Testes da semeadura runtime de presets default (FIX-PACKAGING-SEED-PARITY-01).

`profiles.loader.seed_default_presets` replica scripts/install_profiles.sh
(copy-if-absent + marker `.seeded_presets` que respeita deleção proposital)
para os caminhos .deb/AppImage, onde o shell script não roda — o postinst
executa como root e não conhece o usuário, então a semeadura acontece na
primeira carga de perfis (GUI/daemon/CLI).

Tudo hermético: fontes e destino injetados por argumento ou monkeypatch;
nenhum teste toca o config real nem os assets do repo como destino.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from hefesto_dualsense4unix.profiles import loader

REPO_ROOT = Path(__file__).resolve().parents[2]


def _make_source(base: Path, names: list[str]) -> Path:
    """Cria um diretório-fonte com presets JSON válidos (schema mínimo)."""
    src = base / "fonte" / "profiles_default"
    src.mkdir(parents=True, exist_ok=True)
    for name in names:
        payload = {"name": name.removesuffix(".json"), "match": {"type": "any"}}
        (src / name).write_text(json.dumps(payload), encoding="utf-8")
    return src


def _marker_lines(dest: Path) -> list[str]:
    marker = dest / loader.SEED_MARKER_NAME
    assert marker.exists(), "marker .seeded_presets deveria existir após a semeadura"
    return [line for line in marker.read_text(encoding="utf-8").splitlines() if line]


# =============================================================================
# Semântica copy-if-absent + marker (paridade com scripts/install_profiles.sh)
# =============================================================================

def test_primeira_carga_copia_todos_os_presets(tmp_path: Path) -> None:
    src = _make_source(tmp_path, ["acao.json", "fps.json"])
    dest = tmp_path / "perfis"

    copied = loader.seed_default_presets(dest_dir=dest, source_dirs=[src])

    assert copied == ["acao.json", "fps.json"]
    assert (dest / "acao.json").exists()
    assert (dest / "fps.json").exists()
    assert sorted(_marker_lines(dest)) == ["acao.json", "fps.json"]


def test_nao_sobrescreve_perfil_editado(tmp_path: Path) -> None:
    """Perfil já presente na 1ª execução: registrado no marker SEM cópia."""
    src = _make_source(tmp_path, ["acao.json", "fps.json"])
    dest = tmp_path / "perfis"
    dest.mkdir()
    editado = json.dumps({"name": "Ação editada", "match": {"type": "any"}})
    (dest / "acao.json").write_text(editado, encoding="utf-8")

    copied = loader.seed_default_presets(dest_dir=dest, source_dirs=[src])

    assert copied == ["fps.json"]
    # A edição da usuária sobreviveu intacta…
    assert (dest / "acao.json").read_text(encoding="utf-8") == editado
    # …e o preset foi registrado (deleções futuras serão respeitadas).
    assert sorted(_marker_lines(dest)) == ["acao.json", "fps.json"]


def test_delecao_proposital_nao_ressuscita(tmp_path: Path) -> None:
    """Preset no marker + ausente no disco = usuária deletou → NÃO volta."""
    src = _make_source(tmp_path, ["acao.json", "fps.json"])
    dest = tmp_path / "perfis"
    dest.mkdir()
    (dest / loader.SEED_MARKER_NAME).write_text("acao.json\n", encoding="utf-8")

    copied = loader.seed_default_presets(dest_dir=dest, source_dirs=[src])

    assert copied == ["fps.json"]
    assert not (dest / "acao.json").exists()


def test_preset_novo_chega_em_upgrade(tmp_path: Path) -> None:
    """Marker antigo + preset novo na fonte → só o novo é copiado."""
    src = _make_source(tmp_path, ["acao.json", "point_and_click.json"])
    dest = tmp_path / "perfis"
    dest.mkdir()
    (dest / "acao.json").write_text("{}", encoding="utf-8")
    (dest / loader.SEED_MARKER_NAME).write_text("acao.json\n", encoding="utf-8")

    copied = loader.seed_default_presets(dest_dir=dest, source_dirs=[src])

    assert copied == ["point_and_click.json"]
    assert (dest / "point_and_click.json").exists()
    assert sorted(_marker_lines(dest)) == ["acao.json", "point_and_click.json"]


def test_reexecucao_e_idempotente(tmp_path: Path) -> None:
    src = _make_source(tmp_path, ["acao.json"])
    dest = tmp_path / "perfis"

    assert loader.seed_default_presets(dest_dir=dest, source_dirs=[src]) == ["acao.json"]
    assert loader.seed_default_presets(dest_dir=dest, source_dirs=[src]) == []


def test_sem_fonte_existente_e_noop(tmp_path: Path) -> None:
    dest = tmp_path / "perfis"

    copied = loader.seed_default_presets(
        dest_dir=dest,
        source_dirs=[tmp_path / "nao-existe-a", tmp_path / "nao-existe-b"],
    )

    assert copied == []
    assert not dest.exists(), "sem fonte, o destino não deve nem ser criado"


def test_fallback_de_fontes_usa_a_primeira_existente(tmp_path: Path) -> None:
    """Ordem repo-assets → /usr/share: a primeira EXISTENTE vence."""
    usr_share = _make_source(tmp_path, ["fps.json"])
    dest = tmp_path / "perfis"

    copied = loader.seed_default_presets(
        dest_dir=dest,
        source_dirs=[tmp_path / "repo-inexistente", usr_share],
    )

    assert copied == ["fps.json"]


def test_marker_criado_mesmo_sem_nada_a_copiar(tmp_path: Path) -> None:
    """Espelha o `touch` do shell script: fonte vazia ainda registra a passada."""
    src = tmp_path / "fonte" / "profiles_default"
    src.mkdir(parents=True)
    dest = tmp_path / "perfis"

    assert loader.seed_default_presets(dest_dir=dest, source_dirs=[src]) == []
    assert (dest / loader.SEED_MARKER_NAME).exists()


# =============================================================================
# Gatilho automático na primeira carga (load_all_profiles / load_profile)
# =============================================================================

@pytest.fixture
def _auto_seed(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """Re-habilita a semeadura automática (desligada globalmente no conftest)
    apontando a fonte default para um tmp injetado."""
    src = _make_source(tmp_path, ["semeado.json"])
    monkeypatch.delenv(loader.SEED_SKIP_ENV_VAR, raising=False)
    monkeypatch.setattr(loader, "_seed_attempted", False)
    monkeypatch.setattr(loader, "_DEFAULT_SEED_SOURCE_DIRS", (src,))
    return src


def test_load_all_profiles_semeia_na_primeira_carga(_auto_seed: Path) -> None:
    profiles = loader.load_all_profiles()
    assert "semeado" in [p.name for p in profiles]


def test_load_profile_semeia_na_primeira_carga(_auto_seed: Path) -> None:
    profile = loader.load_profile("semeado")
    assert profile.name == "semeado"


def test_gatilho_roda_uma_vez_por_processo(_auto_seed: Path) -> None:
    """Segunda carga NÃO re-semeia: preset deletado após a 1ª fica deletado."""
    assert "semeado" in [p.name for p in loader.load_all_profiles()]
    from hefesto_dualsense4unix.utils.xdg_paths import profiles_dir

    (profiles_dir() / "semeado.json").unlink()
    assert "semeado" not in [p.name for p in loader.load_all_profiles()]


def test_env_var_de_skip_desliga_o_gatilho(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    src = _make_source(tmp_path, ["semeado.json"])
    monkeypatch.setattr(loader, "_seed_attempted", False)
    monkeypatch.setattr(loader, "_DEFAULT_SEED_SOURCE_DIRS", (src,))
    monkeypatch.setenv(loader.SEED_SKIP_ENV_VAR, "1")

    assert loader.load_all_profiles() == []


def test_falha_na_semeadura_nao_impede_a_carga(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Contrato best-effort: erro na semeadura loga warning e a carga segue."""
    monkeypatch.delenv(loader.SEED_SKIP_ENV_VAR, raising=False)
    monkeypatch.setattr(loader, "_seed_attempted", False)

    def _boom() -> list[str]:
        raise OSError("disco cheio")

    monkeypatch.setattr(loader, "seed_default_presets", _boom)
    assert loader.load_all_profiles() == []


# =============================================================================
# Interop com scripts/install_profiles.sh (contrato do marker compartilhado)
# =============================================================================

def test_marker_do_shell_script_e_respeitado(tmp_path: Path) -> None:
    """install_profiles.sh semeia primeiro; o semeador Python não re-copia nada.

    Prova o contrato compartilhado do marker (um filename por linha): uma
    instalação nativa seguida da primeira carga runtime não duplica trabalho
    nem ressuscita deleções.
    """
    script = REPO_ROOT / "scripts" / "install_profiles.sh"
    if not script.exists():
        pytest.skip("scripts/install_profiles.sh não encontrado")

    fake_root = tmp_path / "repo"
    src = fake_root / "assets" / "profiles_default"
    src.mkdir(parents=True)
    for name in ("acao.json", "fps.json"):
        payload = {"name": name.removesuffix(".json"), "match": {"type": "any"}}
        (src / name).write_text(json.dumps(payload), encoding="utf-8")

    home = tmp_path / "home"
    home.mkdir()
    result = subprocess.run(
        ["bash", str(script), str(fake_root)],
        env={"HOME": str(home), "PATH": "/usr/bin:/bin"},
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr

    dest = home / ".config" / "hefesto-dualsense4unix" / "profiles"
    assert sorted(_marker_lines(dest)) == ["acao.json", "fps.json"]

    # A usuária deleta um preset semeado pelo shell…
    (dest / "acao.json").unlink()
    # …e a semeadura runtime respeita o marker escrito pelo shell.
    copied = loader.seed_default_presets(dest_dir=dest, source_dirs=[src])
    assert copied == []
    assert not (dest / "acao.json").exists()
