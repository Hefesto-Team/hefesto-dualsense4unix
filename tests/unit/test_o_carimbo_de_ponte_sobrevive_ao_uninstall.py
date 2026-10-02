"""PONTE-CONFIRMADA-01 no ciclo `uninstall` -> `install`: o que o produto"""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

import pytest

from hefesto_dualsense4unix.profiles.schema import (
    MatchManual,
    PonteConfirmada,
    Profile,
    ProfileModeConfig,
)

RAIZ = Path(__file__).resolve().parents[2]
UNINSTALL = RAIZ / "uninstall.sh"
INSTALL_PROFILES = RAIZ / "scripts" / "install_profiles.sh"

ANCORA_INICIO = "# Configs e dados do user. PRESERVADOS por padrão"

CARIMBO = {
    "kind": "gamepad",
    "gamepad_flavor": "xbox",
    "steam_input": True,
    "confirmada_em": "2026-08-19T21:30:00-03:00",
    "confirmada_por": "gesto",
}


def _bloco_de_config() -> str:
    """Recorta o bloco REAL que decide o destino da config no uninstall."""
    texto = UNINSTALL.read_text(encoding="utf-8")
    inicio = texto.find(ANCORA_INICIO)
    assert inicio != -1, (
        "o bloco de config do uninstall.sh mudou de cabeçalho — a âncora "
        f"{ANCORA_INICIO!r} sumiu. Reaponte este teste antes de confiar nele."
    )
    fim = re.search(r"^fi$", texto[inicio:], re.MULTILINE)
    assert fim is not None, "fim do bloco de config não encontrado em uninstall.sh"
    bloco = texto[inicio : inicio + fim.end()]
    assert "rm -rf" in bloco, (
        "o bloco recortado não tem mais o `rm -rf` da config — ou a âncora pegou "
        f"o pedaço errado, ou a remoção mudou de lugar:\n{bloco}"
    )
    return bloco


def _um_nome_de_preset() -> str:
    """Um nome que o `install_profiles.sh` de fato tentaria copiar."""
    presets = sorted(
        p.stem for p in (RAIZ / "assets" / "profiles_default").glob("*.json")
    )
    assert presets, "assets/profiles_default/ sem preset nenhum"
    return presets[0]


def _grava_perfil(home: Path, nome: str) -> Path:
    """Um perfil DE VERDADE (pelo esquema do produto) com o carimbo dentro."""
    destino = home / ".config" / "hefesto-dualsense4unix" / "profiles"
    destino.mkdir(parents=True, exist_ok=True)
    perfil = Profile(name=nome, match=MatchManual(type="manual"))
    perfil.mode = ProfileModeConfig(kind="gamepad", gamepad_flavor="xbox")
    perfil.ponte = PonteConfirmada(**CARIMBO)
    alvo = destino / f"{nome}.json"
    alvo.write_text(perfil.model_dump_json(indent=2), encoding="utf-8")
    return alvo


def _roda_bloco(home: Path, *, keep_config: int) -> subprocess.CompletedProcess[str]:
    """Roda o bloco do uninstall com o ``HOME`` de mentira."""
    script = (
        "set -euo pipefail\n"
        'log() { printf "[uninstall] %s\\n" "$*"; }\n'
        f"KEEP_CONFIG={keep_config}\n"
        f"{_bloco_de_config()}\n"
    )
    return subprocess.run(
        ["bash", "-c", script],
        env={"HOME": str(home), "PATH": "/usr/bin:/bin"},
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )


def _carimbo_de(caminho: Path) -> dict[str, object] | None:
    dados = json.loads(caminho.read_text(encoding="utf-8"))
    valor = dados.get("ponte")
    return valor if isinstance(valor, dict) else None


class TestOCarimboSobreviveAoUninstall:
    def test_o_padrao_preserva_o_carimbo_inteiro(self, tmp_path: Path) -> None:
        """O caminho que ela vai percorrer: `./uninstall.sh` sem flag nenhuma."""
        alvo = _grava_perfil(tmp_path, "jogo_de_teste")

        r = _roda_bloco(tmp_path, keep_config=1)

        assert r.returncode == 0, f"o bloco morreu: {r.returncode}\n{r.stderr}"
        assert alvo.is_file(), (
            "o uninstall padrão APAGOU o perfil — o carimbo de ponte de todo jogo "
            "morreria numa reinstalação, e a escada recomeçaria do zero."
        )
        assert _carimbo_de(alvo) == CARIMBO, (
            "o perfil sobreviveu mas o carimbo não voltou igual: "
            f"{_carimbo_de(alvo)!r}"
        )
        relido = Profile.model_validate_json(alvo.read_text(encoding="utf-8"))
        assert relido.ponte is not None
        assert relido.ponte.confirmada_por == "gesto"
        assert relido.ponte.steam_input is True

    def test_a_allowlist_do_steam_input_sobrevive_junto(self, tmp_path: Path) -> None:
        """O terceiro termo do carimbo não mora no perfil."""
        lista = tmp_path / ".config" / "hefesto-dualsense4unix" / "steam_input_apps.txt"
        lista.parent.mkdir(parents=True, exist_ok=True)
        lista.write_text("2497900\n2542020\n", encoding="utf-8")

        r = _roda_bloco(tmp_path, keep_config=1)

        assert r.returncode == 0, r.stderr
        assert lista.is_file(), "o uninstall padrão levou a allowlist do Steam Input"
        assert lista.read_text(encoding="utf-8").split() == ["2497900", "2542020"]

    def test_o_purge_e_destrutivo_mas_deixa_backup(self, tmp_path: Path) -> None:
        """`--purge-config` APAGA — e é para apagar. O que ele não pode é apagar"""
        _grava_perfil(tmp_path, "jogo_de_teste")

        r = _roda_bloco(tmp_path, keep_config=0)

        assert r.returncode == 0, r.stderr
        vivo = tmp_path / ".config" / "hefesto-dualsense4unix" / "profiles"
        assert not vivo.exists(), "--purge-config não apagou: a flag virou no-op"

        copias = list(tmp_path.glob(".config/*.backup-*/**/jogo_de_teste.json"))
        assert copias, (
            "--purge-config apagou o perfil e NÃO deixou backup — o carimbo de "
            "ponte de todos os jogos some sem volta."
        )
        assert _carimbo_de(copias[0]) == CARIMBO


class TestOInstallNaoPassaPorCimaDoCarimbo:
    """A outra metade do ciclo: reinstalar não pode reescrever o que aprendeu."""

    @pytest.mark.parametrize("e_preset", [True, False], ids=["preset", "so_dela"])
    def test_install_profiles_preserva_o_perfil_que_ja_existe(
        self, tmp_path: Path, e_preset: bool
    ) -> None:
        """O caso `preset` é o perigoso, e o nome sai da FONTE, não daqui."""
        nome = _um_nome_de_preset() if e_preset else "jogo_dela_sem_preset"
        alvo = _grava_perfil(tmp_path, nome)

        r = subprocess.run(
            ["bash", str(INSTALL_PROFILES), str(RAIZ)],
            env={"HOME": str(tmp_path), "PATH": "/usr/bin:/bin"},
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )

        assert r.returncode == 0, f"install_profiles.sh falhou:\n{r.stderr}"
        assert _carimbo_de(alvo) == CARIMBO, (
            f"o passo de perfis do install passou por cima de {nome}.json e levou "
            f"o carimbo junto: {_carimbo_de(alvo)!r}"
        )
