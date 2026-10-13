"""O perfil feito fora da janela vale inteiro (O-PERFIL-FEITO-FORA-DA-JANELA-VALE-INTEIRO-01).

Duas réguas, as duas em lar de mentira (o ``conftest`` desvia ``HOME`` e ``XDG_*``):

1. ``profile create`` grava o perfil enxuto — nome, alvo e prioridade — e o
   que o perfil não diz herda o padrão do computador. Mordida: devolvido o
   ``TriggerConfig(mode="Off")`` / a luz apagada, o computador deixa de valer.
2. A assinatura da mesa, que o vigia compara, enxerga o perfil gravado por outro
   processo; depois do sossego o ``steam_app_<appid>.env`` do jogo novo nasce.
   Mordida: tirado o selo da assinatura, o arquivo não nasce.
"""
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from typer.testing import CliRunner

from hefesto_dualsense4unix.cli.app import app
from hefesto_dualsense4unix.daemon import launch_env as le
from hefesto_dualsense4unix.profiles import o_padrao_do_computador as opc
from hefesto_dualsense4unix.profiles.loader import save_profile
from hefesto_dualsense4unix.profiles.schema import MatchCriteria, Profile, ProfileModeConfig
from hefesto_dualsense4unix.utils import maquina as m
from hefesto_dualsense4unix.utils.xdg_paths import profiles_dir

APPID_NOVO = 4242001
runner = CliRunner()


def _computador_declarado() -> None:
    assert m.gravar_o_computador({
        "global": {
            "leds": {"lightbar": [10, 20, 200]},
            "rumble": {"policy": "max"},
        },
    })


class TestOPerfilDoTerminalHerdaOComputador:
    def test_o_json_gravado_so_tem_nome_alvo_e_prioridade(self) -> None:
        r = runner.invoke(app, ["profile", "create", "Meu Jogo", "--match-class", "meujogo"])
        assert r.exit_code == 0, r.output
        gravado = json.loads((profiles_dir() / "meu_jogo.json").read_text(encoding="utf-8"))
        assert set(gravado) == {"name", "match", "priority"}, (
            f"o perfil do terminal nasceu com campos explícitos: {sorted(gravado)}"
        )

    def test_o_perfil_vale_com_a_luz_e_a_vibracao_do_computador(self) -> None:
        _computador_declarado()
        r = runner.invoke(app, ["profile", "create", "Meu Jogo", "--match-class", "meujogo"])
        assert r.exit_code == 0, r.output
        vale = opc.carregar_o_que_vale("Meu Jogo")
        assert vale.leds.lightbar == (10, 20, 200), "a barra apagada venceu o computador"
        assert vale.rumble.policy == "max", "a vibração sem política venceu o computador"
        assert vale.triggers.left.mode != "Off", "o gatilho nasceu desligado"
        assert vale.triggers.right.mode != "Off"

    def test_o_fallback_e_o_manual_tambem_nascem_enxutos(self) -> None:
        for nome, flag in (("Reserva", "--fallback"), ("Avulso", "--manual")):
            r = runner.invoke(app, ["profile", "create", nome, flag])
            assert r.exit_code == 0, r.output
        for arquivo in ("reserva.json", "avulso.json"):
            gravado = json.loads((profiles_dir() / arquivo).read_text(encoding="utf-8"))
            assert set(gravado) == {"name", "match", "priority"}

    def test_a_ajuda_diz_que_herda_o_computador(self) -> None:
        r = runner.invoke(app, ["profile", "create", "--help"])
        assert "herda" in " ".join(r.output.split()), r.output


def _daemon() -> Any:
    return SimpleNamespace(
        is_native_mode=lambda: False,
        config=SimpleNamespace(gamepad_emulation_enabled=True, gamepad_flavor="dualsense"),
        _gamepad_device=SimpleNamespace(backend="uhid"),
        _coop_manager=SimpleNamespace(_players={}),
        controller=SimpleNamespace(describe_controllers=lambda: [{"connected": True}]),
    )


@pytest.fixture
def mesa(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(le, "launch_env_dir", lambda ensure=False: tmp_path)
    monkeypatch.setattr(le, "_permite_uhid", lambda daemon: True)
    return tmp_path


def _perfil_do_jogo_novo() -> Profile:
    """Um perfil de jogo com opinião sobre o modo — é o que ganha ``steam_app_<appid>.env``."""
    return Profile(
        name="Jogo Novo",
        match=MatchCriteria(window_class=[f"steam_app_{APPID_NOVO}"]),
        priority=80,
        mode=ProfileModeConfig(kind="gamepad", gamepad_flavor="dualsense"),
    )


class TestOVigiaEnxergaOPerfilGravadoPorFora:
    def test_perfil_novo_muda_a_assinatura_e_o_env_do_jogo_nasce(self, mesa: Path) -> None:
        daemon = _daemon()
        le.materialize_launch_env(daemon)
        assert not (mesa / f"steam_app_{APPID_NOVO}.env").exists()
        antes = le._assinatura_da_mesa(daemon)

        save_profile(_perfil_do_jogo_novo())  # outro processo: o terminal, ou o JSON à mão

        assert le._assinatura_da_mesa(daemon) != antes, "a assinatura não viu o perfil novo"
        le.vigiar_a_mesa(daemon, agora=100.0)
        assert daemon._launch_env_sossego_em == 100.0 + le.JANELA_DE_SOSSEGO_SEC
        assert le.rematerializar_se_sossegou(
            daemon, agora=100.0 + le.JANELA_DE_SOSSEGO_SEC
        ) is True
        assert (mesa / f"steam_app_{APPID_NOVO}.env").exists(), (
            "o jogo novo abriria sem o arquivo de antecipação"
        )

    def test_perfil_editado_ou_apagado_tambem_muda_a_assinatura(self, mesa: Path) -> None:
        daemon = _daemon()
        caminho = save_profile(_perfil_do_jogo_novo())
        base = le._assinatura_da_mesa(daemon)
        caminho.write_text(caminho.read_text(encoding="utf-8") + "\n", encoding="utf-8")
        editado = le._assinatura_da_mesa(daemon)
        assert editado != base
        caminho.unlink()
        assert le._assinatura_da_mesa(daemon) not in (base, editado)

    def test_pasta_parada_nao_regrava_nada(self, mesa: Path) -> None:
        daemon = _daemon()
        save_profile(_perfil_do_jogo_novo())
        le.materialize_launch_env(daemon)
        antes = {p.name: p.read_bytes() for p in mesa.iterdir() if p.is_file()}

        le.vigiar_a_mesa(daemon, agora=10.0)
        assert getattr(daemon, "_launch_env_sossego_em", None) is None, (
            "armou sem a pasta de perfis ter mudado"
        )
        assert le.rematerializar_se_sossegou(daemon, agora=10.0 + 1e6) is False
        assert {p.name: p.read_bytes() for p in mesa.iterdir() if p.is_file()} == antes

    def test_o_recibo_da_materializacao_e_a_assinatura_do_vigia(self, mesa: Path) -> None:
        """Duas contas diferentes fariam o vigia regravar a cada tique."""
        daemon = _daemon()
        save_profile(_perfil_do_jogo_novo())
        le.materialize_launch_env(daemon)
        assert daemon._launch_env_assinatura == le._assinatura_da_mesa(daemon)
