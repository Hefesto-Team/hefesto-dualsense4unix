"""R-10 (auditoria 23/07) — o CLI também gravava por cima do perfil errado.

`save_profile` grava `<slugify(name)>.json`: "Navegacao" e "Navegação" são o
MESMO arquivo. `profile create`/`profile save --from-active`/`profile apply`
chamavam `save_profile` direto, então o perfil acentuado da usuária era
substituído e o comando imprimia "perfil criado" em VERDE.

Cobre também a densificação do clone (`profile save --from-active`), o mesmo
defeito que a aba Perfis tinha em R-09: `model_dump()` perde o
`model_fields_set` e um override por-controle PARCIAL (só brilho) vira
`lightbar:[0,0,0]` — a lightbar daquele controle APAGA no clone.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from hefesto_dualsense4unix.cli.app import app
from hefesto_dualsense4unix.profiles import loader as loader_module
from hefesto_dualsense4unix.profiles.loader import save_profile
from hefesto_dualsense4unix.profiles.schema import (
    ControllerOverrides,
    LedsConfig,
    MatchCriteria,
    Profile,
)

runner = CliRunner()

MAC = "aabbcc000002"


@pytest.fixture
def isolated_profiles_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    target = tmp_path / "profiles"
    target.mkdir()

    def fake_profiles_dir(ensure: bool = False) -> Path:
        if ensure:
            target.mkdir(parents=True, exist_ok=True)
        return target

    monkeypatch.setattr(loader_module, "profiles_dir", fake_profiles_dir)
    # Semeadura desligada: o teste é sobre os perfis que ELE cria.
    monkeypatch.setenv(loader_module.SEED_SKIP_ENV_VAR, "1")

    from hefesto_dualsense4unix.utils import xdg_paths

    fake_cfg = tmp_path / "config"
    fake_cfg.mkdir()
    monkeypatch.setattr(
        xdg_paths, "config_dir", lambda ensure=False: fake_cfg
    )
    return target


def _navegacao() -> Profile:
    return Profile(
        name="Navegação",
        match=MatchCriteria(window_class=["firefox"]),
        priority=50,
    )


class TestGuardaDeSlugNoCreate:
    def test_create_com_nome_sem_acento_recusa(
        self, isolated_profiles_dir: Path
    ) -> None:
        save_profile(_navegacao())

        result = runner.invoke(app, ["profile", "create", "Navegacao"])

        assert result.exit_code == 1
        assert "MESMO arquivo" in result.stdout
        assert "Navegação" in result.stdout
        # O arquivo continua sendo o da usuária.
        raw = json.loads(
            (isolated_profiles_dir / "navegacao.json").read_text(encoding="utf-8")
        )
        assert raw["name"] == "Navegação"
        assert raw["match"]["window_class"] == ["firefox"]

    def test_force_ainda_permite_sobrescrever(
        self, isolated_profiles_dir: Path
    ) -> None:
        save_profile(_navegacao())

        result = runner.invoke(app, ["profile", "create", "Navegacao", "--force"])

        assert result.exit_code == 0
        raw = json.loads(
            (isolated_profiles_dir / "navegacao.json").read_text(encoding="utf-8")
        )
        assert raw["name"] == "Navegacao"

    def test_nome_livre_continua_criando(self, isolated_profiles_dir: Path) -> None:
        result = runner.invoke(app, ["profile", "create", "Jogos"])
        assert result.exit_code == 0
        assert (isolated_profiles_dir / "jogos.json").exists()

    def test_mesmo_nome_e_edicao_in_place(self, isolated_profiles_dir: Path) -> None:
        """Recriar com o nome IDÊNTICO é o comportamento de sempre."""
        save_profile(_navegacao())
        result = runner.invoke(app, ["profile", "create", "Navegação"])
        assert result.exit_code == 0


class TestCloneDoPerfilAtivo:
    def test_clone_recusa_colisao_de_slug(
        self, isolated_profiles_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        save_profile(_navegacao())
        save_profile(
            Profile(name="ativo", match=MatchCriteria(window_class=["x"]))
        )
        from hefesto_dualsense4unix.cli import cmd_profile

        monkeypatch.setattr(cmd_profile, "read_active_marker", lambda: "ativo")

        result = runner.invoke(
            app, ["profile", "save", "Navegacao", "--from-active"]
        )

        assert result.exit_code == 1
        raw = json.loads(
            (isolated_profiles_dir / "navegacao.json").read_text(encoding="utf-8")
        )
        assert raw["name"] == "Navegação"

    def test_clone_preserva_override_parcial_por_controle(
        self, isolated_profiles_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """R-09 no CLI: `model_dump()` densificaria e apagaria a lightbar."""
        save_profile(
            Profile(
                name="ativo",
                match=MatchCriteria(window_class=["x"]),
                leds=LedsConfig(lightbar=(200, 20, 20)),
                controllers={
                    MAC: ControllerOverrides(
                        leds=LedsConfig(lightbar_brightness=0.5)
                    )
                },
            )
        )
        from hefesto_dualsense4unix.cli import cmd_profile

        monkeypatch.setattr(cmd_profile, "read_active_marker", lambda: "ativo")

        result = runner.invoke(app, ["profile", "save", "copia", "--from-active"])
        assert result.exit_code == 0

        raw = json.loads(
            (isolated_profiles_dir / "copia.json").read_text(encoding="utf-8")
        )
        override = raw["controllers"][MAC]["leds"]
        assert override.get("lightbar_brightness") == 0.5
        assert "lightbar" not in override, (
            "o clone densificado gravava lightbar:[0,0,0] e APAGAVA a cor "
            "daquele controle, além de matar a herança do global"
        )
