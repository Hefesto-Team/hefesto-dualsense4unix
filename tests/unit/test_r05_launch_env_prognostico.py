"""R-05 (auditoria 23/07) — o `.env` por appid prognostica o backend do PERFIL.

`_env_for_profile` recebia os `backends` do vpad VIGENTE. Quando o perfil pede
uma máscara DIFERENTE da atual, esses backends descrevem outro flavor e não
dizem nada sobre o que vai existir quando o perfil ativar.

Caso medido na configuração dela: máscara global `xbox` (vpad uinput) e o
Sackboy com perfil `dualsense`. O `steam_app_1599660.env` saía SEM
`SDL_GAMECONTROLLER_IGNORE_DEVICES` e SEM `PROTON_DISABLE_HIDRAW` — porque
"uinput" não autoriza o dedup. O arquivo por-appid ficava estritamente PIOR que
o `default.env`, e o jogo abria vendo o DualSense físico junto com o virtual.

A assimetria de risco favorece o prognóstico: errando, o vpad cai para uinput
Edge `0x0DF2`, que NÃO está na lista do IGNORE (`0x054c/0x0ce6`) — o pior caso é
mapeamento SDL menos validado, nunca "zero controles".
"""

from __future__ import annotations

from typing import Any

import pytest

from hefesto_dualsense4unix.daemon import launch_env as le
from hefesto_dualsense4unix.profiles.schema import (
    MatchCriteria,
    Profile,
    ProfileModeConfig,
)


def _perfil(flavor: str) -> Profile:
    return Profile(
        name="sackboy_nativo",
        match=MatchCriteria(window_class=["steam_app_1599660"]),
        priority=80,
        mode=ProfileModeConfig(kind="gamepad", gamepad_flavor=flavor, coop=True),
    )


class TestPrognosticoDeBackend:
    def test_flavor_diferente_prognostica_uhid(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """O caso dela: global xbox/uinput, perfil pede dualsense."""
        monkeypatch.setattr(
            "hefesto_dualsense4unix.integrations.uhid_gamepad.uhid_available",
            lambda: True,
        )
        env, motivo = le._env_for_profile(
            _perfil("dualsense"),
            flavor_atual="xbox",
            backends=["uinput"],
            permite_uhid=True,
        )
        assert "SDL_GAMECONTROLLER_IGNORE_DEVICES" in env, (
            "sem o IGNORE o jogo abre vendo o DualSense físico E o virtual — "
            "o arquivo por-appid ficava PIOR que o default.env"
        )
        assert "PROTON_DISABLE_HIDRAW" in env
        assert "prognóstico uhid" in motivo

    def test_sem_uhid_no_sistema_fica_conservador(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            "hefesto_dualsense4unix.integrations.uhid_gamepad.uhid_available",
            lambda: False,
        )
        env, motivo = le._env_for_profile(
            _perfil("dualsense"),
            flavor_atual="xbox",
            backends=["uinput"],
            permite_uhid=True,
        )
        assert "SDL_GAMECONTROLLER_IGNORE_DEVICES" not in env
        assert "conservador" in motivo

    def test_gate_vpad08_veta_o_prognostico(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """VPAD-08: o modo fake não pode plantar um Edge real no kernel."""
        monkeypatch.setattr(
            "hefesto_dualsense4unix.integrations.uhid_gamepad.uhid_available",
            lambda: True,
        )
        env, motivo = le._env_for_profile(
            _perfil("dualsense"),
            flavor_atual="xbox",
            backends=["uinput"],
            permite_uhid=False,
        )
        assert "SDL_GAMECONTROLLER_IGNORE_DEVICES" not in env
        assert "conservador" in motivo

    def test_mesmo_flavor_com_vpad_vivo_usa_os_backends_reais(self) -> None:
        """Sem troca de máscara, o estado atual É a verdade — nada a prognosticar."""
        env, motivo = le._env_for_profile(
            _perfil("dualsense"),
            flavor_atual="dualsense",
            backends=["uhid"],
            permite_uhid=True,
        )
        assert "SDL_GAMECONTROLLER_IGNORE_DEVICES" in env
        assert "backends reais" in motivo

    def test_xbox_segue_intocado(self) -> None:
        """Invariante VPAD-06: o vpad Xbox é uinput 045e por design."""
        env, motivo = le._env_for_profile(
            _perfil("xbox"), flavor_atual="dualsense", backends=["uhid"]
        )
        assert motivo == "perfil gamepad xbox"


class TestGateTolerante:
    def test_permite_uhid_com_daemon_dublado_e_false(self) -> None:
        """Na dúvida, conservador — nunca explode no meio da materialização."""
        assert le._permite_uhid(object()) is False
        assert le._permite_uhid(None) is False
