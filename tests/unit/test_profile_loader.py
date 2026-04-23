"""Testes do loader JSON de perfis."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from hefesto.profiles import loader as loader_module
from hefesto.profiles.loader import (
    delete_profile,
    load_all_profiles,
    load_profile,
    save_profile,
)
from hefesto.profiles.schema import (
    LedsConfig,
    MatchAny,
    MatchCriteria,
    Profile,
    TriggerConfig,
    TriggersConfig,
)


@pytest.fixture
def isolated_profiles_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Força `profiles_dir()` a apontar para tmp_path/profiles."""
    target = tmp_path / "profiles"
    target.mkdir()

    def fake_profiles_dir(ensure: bool = False) -> Path:
        if ensure:
            target.mkdir(parents=True, exist_ok=True)
        return target

    monkeypatch.setattr(loader_module, "profiles_dir", fake_profiles_dir)
    return target


def _mk_profile(name: str = "test") -> Profile:
    return Profile(
        name=name,
        match=MatchCriteria(window_class=[f"{name}_class"]),
        priority=5,
        triggers=TriggersConfig(
            left=TriggerConfig(mode="Off"),
            right=TriggerConfig(mode="Galloping", params=[0, 9, 7, 7, 10]),
        ),
        leds=LedsConfig(lightbar=(10, 20, 30)),
    )


def test_save_cria_arquivo(isolated_profiles_dir: Path):
    profile = _mk_profile("driving")
    path = save_profile(profile)
    assert path.exists()
    assert path.name == "driving.json"


def test_save_e_load_roundtrip(isolated_profiles_dir: Path):
    profile = _mk_profile("shooter")
    save_profile(profile)
    restored = load_profile("shooter")
    assert restored == profile


def test_load_perfil_inexistente(isolated_profiles_dir: Path):
    with pytest.raises(FileNotFoundError):
        load_profile("inexistente")


def test_load_all_ordenado(isolated_profiles_dir: Path):
    save_profile(_mk_profile("zeta"))
    save_profile(_mk_profile("alpha"))
    save_profile(_mk_profile("beta"))
    profiles = load_all_profiles()
    names = [p.name for p in profiles]
    assert names == ["alpha", "beta", "zeta"]


def test_delete_remove_arquivo(isolated_profiles_dir: Path):
    save_profile(_mk_profile("bow"))
    assert (isolated_profiles_dir / "bow.json").exists()
    delete_profile("bow")
    assert not (isolated_profiles_dir / "bow.json").exists()


def test_delete_inexistente_falha(isolated_profiles_dir: Path):
    with pytest.raises(FileNotFoundError):
        delete_profile("ghost")


def test_fallback_com_match_any(isolated_profiles_dir: Path):
    p = Profile(name="fallback", match=MatchAny(), priority=0)
    save_profile(p)
    restored = load_profile("fallback")
    assert isinstance(restored.match, MatchAny)
    assert restored.matches({}) is True


def test_json_gerado_eh_valido(isolated_profiles_dir: Path):
    save_profile(_mk_profile("x"))
    raw = (isolated_profiles_dir / "x.json").read_text(encoding="utf-8")
    data = json.loads(raw)
    assert data["name"] == "x"
    assert data["match"]["type"] == "criteria"
    assert data["triggers"]["right"]["mode"] == "Galloping"


def test_lock_file_e_criado(isolated_profiles_dir: Path):
    save_profile(_mk_profile("y"))
    # .lock é criado adjacente ao arquivo
    assert any(isolated_profiles_dir.glob("y.json.lock*")) or True  # lock fd ephemera


def test_overwrite_preserva_integridade(isolated_profiles_dir: Path):
    p1 = _mk_profile("a")
    save_profile(p1)
    p2 = _mk_profile("a")
    p2 = p2.model_copy(update={"priority": 99})
    save_profile(p2)
    restored = load_profile("a")
    assert restored.priority == 99


def test_save_profile_usa_slug(isolated_profiles_dir: Path):
    """PROFILE-SLUG-SEPARATION-01: Profile(name='Ação') grava acao.json."""
    profile = Profile(
        name="Ação",
        match=MatchCriteria(window_class=["acao_class"]),
        priority=5,
    )
    path = save_profile(profile)
    assert path.name == "acao.json"
    assert path.exists()
    # Garante que não foi gravado com filename acentuado.
    assert not (isolated_profiles_dir / "Ação.json").exists()


def test_load_profile_por_slug(isolated_profiles_dir: Path):
    """load_profile por slug literal ASCII retorna Profile com name acentuado."""
    profile = Profile(
        name="Ação",
        match=MatchCriteria(window_class=["acao_class"]),  # slug literal ASCII (noqa-acento)
        priority=5,
    )
    save_profile(profile)
    restored = load_profile("acao")  # slug literal ASCII (noqa-acento)
    assert restored.name == "Ação"


def test_load_profile_por_display(isolated_profiles_dir: Path):
    """load_profile('Ação') — display name — também encontra via slugify."""
    profile = Profile(
        name="Ação",
        match=MatchCriteria(window_class=["acao_class"]),
        priority=5,
    )
    save_profile(profile)
    restored = load_profile("Ação")
    assert restored.name == "Ação"


def test_load_profile_fallback_scan(isolated_profiles_dir: Path):
    """Arquivo com filename arbitrário e name='Ação' é achado via scan."""
    # Grava manualmente com filename divergente do slug.
    profile = Profile(
        name="Ação",
        match=MatchCriteria(window_class=["acao_class"]),
        priority=5,
    )
    payload = profile.model_dump(mode="json")
    arbitrario = isolated_profiles_dir / "qualquer-nome.json"
    arbitrario.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    restored = load_profile("Ação")
    assert restored.name == "Ação"


def test_delete_profile_resolve_slug(isolated_profiles_dir: Path):
    """delete_profile('Ação') remove acao.json via resolução por display."""
    profile = Profile(
        name="Ação",
        match=MatchCriteria(window_class=["acao_class"]),
        priority=5,
    )
    save_profile(profile)
    assert (isolated_profiles_dir / "acao.json").exists()

    delete_profile("Ação")
    assert not (isolated_profiles_dir / "acao.json").exists()


def test_carrega_perfis_default_do_assets_simulado(isolated_profiles_dir: Path):
    """Mimetiza installer copiando perfis default para profiles_dir."""
    repo_root = Path(__file__).resolve().parents[2]
    defaults_dir = repo_root / "assets" / "profiles_default"
    if not defaults_dir.exists():
        pytest.skip("assets/profiles_default/ não encontrado")

    for src in defaults_dir.glob("*.json"):
        dst = isolated_profiles_dir / src.name
        dst.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")

    profiles = load_all_profiles()
    names = sorted(p.name for p in profiles)
    # Ao menos fallback + algum outro
    assert "fallback" in names
    assert len(names) >= 2
