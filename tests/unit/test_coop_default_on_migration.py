"""LEIGO-01 — cada controle é um jogador, e nenhum perfil desliga isso.

O checkbox "Cada controle é um jogador" saiu da tela. Ele era o opt-out VISÍVEL
de um estado que os perfis desligavam pelas costas: `ProfileModeConfig.coop`
nascia False, então TODO perfil salvo pela GUI gravava `"coop": false` e o
desligava ao ativar. Tirar o checkbox sem fechar essa porta deixaria a usuária
com o co-op morto e sem como religar.

Trocar o default no esquema não basta — os `false` JÁ GRAVADOS continuam no
disco. Estes testes cobrem as duas metades: o novo default e a migração dos
perfis que a GUI antiga escreveu.
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any

from hefesto_dualsense4unix.profiles.loader import migrate_profiles_coop_default
from hefesto_dualsense4unix.profiles.schema import Profile, ProfileModeConfig

_REPO_ROOT = Path(__file__).resolve().parents[2]
_PRESETS_DIR = _REPO_ROOT / "assets" / "profiles_default"


def _escrever(directory: Path, nome: str, mode: dict[str, Any] | None) -> Path:
    data: dict[str, Any] = {
        "name": nome,
        "version": 1,
        "match": {"type": "any"},
        "priority": 0,
    }
    if mode is not None:
        data["mode"] = mode
    path = directory / f"{nome}.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


class TestDefaultDoEsquema:
    def test_coop_nasce_ligado(self) -> None:
        """A queixa literal: ninguém pluga dois controles esperando um jogador."""
        assert ProfileModeConfig(kind="gamepad").coop is True

    def test_perfil_de_jogo_sem_o_campo_liga_o_coop(self) -> None:
        profile = Profile.model_validate(
            {
                "name": "jogo",
                "version": 1,
                "match": {"type": "any"},
                "mode": {"kind": "gamepad", "gamepad_flavor": "xbox"},
            }
        )
        assert profile.mode is not None
        assert profile.mode.coop is True


class TestMigracaoDosPerfisJaSalvos:
    def test_coop_false_da_gui_antiga_volta_a_herdar_o_default(self) -> None:
        d = Path(tempfile.mkdtemp())
        _escrever(d, "meu_jogo", {"kind": "gamepad", "gamepad_flavor": "xbox",
                                  "coop": False})

        assert migrate_profiles_coop_default(d) == ["meu_jogo.json"]

        got = json.loads((d / "meu_jogo.json").read_text(encoding="utf-8"))
        # A chave é APAGADA (não reescrita como true): o perfil volta a herdar
        # o default, então um default futuro vale sem nova migração.
        assert "coop" not in got["mode"]
        profile = Profile.model_validate(got)
        assert profile.mode is not None
        assert profile.mode.coop is True

    def test_perfil_migrado_nao_desliga_mais_o_coop_ao_ativar(self) -> None:
        """O efeito que interessa: ativar o perfil antigo deixou de ser um opt-out."""
        d = Path(tempfile.mkdtemp())
        _escrever(d, "antigo", {"kind": "gamepad", "gamepad_flavor": "xbox",
                                "coop": False})
        antes = Profile.model_validate(
            json.loads((d / "antigo.json").read_text(encoding="utf-8"))
        )
        assert antes.mode is not None
        assert antes.mode.coop is False  # o defeito, ainda no disco

        migrate_profiles_coop_default(d)

        depois = Profile.model_validate(
            json.loads((d / "antigo.json").read_text(encoding="utf-8"))
        )
        assert depois.mode is not None
        assert depois.mode.coop is True

    def test_idempotente_via_marker(self) -> None:
        d = Path(tempfile.mkdtemp())
        _escrever(d, "meu_jogo", {"kind": "gamepad", "coop": False})

        assert migrate_profiles_coop_default(d) == ["meu_jogo.json"]
        assert migrate_profiles_coop_default(d) == []

    def test_preset_com_coop_true_explicito_fica_intocado(self) -> None:
        """`sackboy_nativo.json` já ship com "coop": true — não pode ser mexido."""
        d = Path(tempfile.mkdtemp())
        _escrever(d, "sackboy_nativo", {"kind": "gamepad",
                                        "gamepad_flavor": "xbox", "coop": True})

        assert migrate_profiles_coop_default(d) == []

        got = json.loads((d / "sackboy_nativo.json").read_text(encoding="utf-8"))
        assert got["mode"]["coop"] is True

    def test_nao_toca_kinds_que_nao_leem_o_campo(self) -> None:
        """Só `kind == "gamepad"` desliga o co-op ao ativar — o resto fica como está."""
        d = Path(tempfile.mkdtemp())
        _escrever(d, "navegador", {"kind": "desktop", "coop": False})

        assert migrate_profiles_coop_default(d) == []

        got = json.loads((d / "navegador.json").read_text(encoding="utf-8"))
        assert got["mode"]["coop"] is False

    def test_perfil_sem_secao_de_modo_sobrevive(self) -> None:
        d = Path(tempfile.mkdtemp())
        _escrever(d, "sem_opiniao", None)

        assert migrate_profiles_coop_default(d) == []

        assert Profile.model_validate(
            json.loads((d / "sem_opiniao.json").read_text(encoding="utf-8"))
        ).mode is None

    def test_json_corrompido_nao_derruba_a_migracao(self) -> None:
        """Um perfil quebrado não pode impedir a cura dos demais."""
        d = Path(tempfile.mkdtemp())
        (d / "quebrado.json").write_text("{ nao é json", encoding="utf-8")
        _escrever(d, "meu_jogo", {"kind": "gamepad", "coop": False})

        assert migrate_profiles_coop_default(d) == ["meu_jogo.json"]


class TestPresetsShipados:
    def test_nenhum_preset_de_jogo_ship_com_coop_desligado(self) -> None:
        """Um preset shipado nunca pode ser o caminho que desliga o co-op."""
        ofensores = []
        for path in sorted(_PRESETS_DIR.glob("*.json")):
            data = json.loads(path.read_text(encoding="utf-8"))
            mode = data.get("mode")
            if (
                isinstance(mode, dict)
                and mode.get("kind") == "gamepad"
                and mode.get("coop") is False
            ):
                ofensores.append(path.name)
        assert not ofensores, (
            "presets de jogo não podem shipar com coop:false — ativá-los faria "
            f"dois controles virarem o mesmo jogador: {ofensores}"
        )
