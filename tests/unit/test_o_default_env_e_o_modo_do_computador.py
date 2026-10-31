"""O ``default.env`` é o modo do computador, e o fim do jogo devolve esse modo ao pad.

Sprint O-DEFAULT-ENV-E-O-MODO-DO-COMPUTADOR-E-NAO-O-DO-ULTIMO-JOGO-01.

O arme de um jogo com perfil em outro modo muda o par que o pad veste; o ``default.env`` sai do par
de antes do arme (``launch_env.modo_do_computador``), e o ``JOGO_FECHOU`` desse jogo pede o par de
volta pelo escritor único (``launch_env.o_fim_do_jogo_devolve_o_modo``). A escolha à mão durante o
jogo apaga o par guardado e passa a ser o modo do computador.

As provas (2) e (3) usam os métodos REAIS do ``lifecycle.Daemon`` com um ``CoopManager`` REAL e o
P2 e o P3 na mesa (o ensaio de ``test_a_mascara_do_cartao_vale_com_o_vpad_de_pe.py``).
"""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
import structlog

from hefesto_dualsense4unix.core.events import EventBus, EventTopic
from hefesto_dualsense4unix.daemon import launch_env as le
from hefesto_dualsense4unix.daemon import lifecycle
from hefesto_dualsense4unix.daemon.subsystems import gamepad as gp
from hefesto_dualsense4unix.daemon.subsystems.coop import CoopManager
from hefesto_dualsense4unix.profiles import loader
from hefesto_dualsense4unix.profiles.schema import (
    MatchAny,
    MatchCriteria,
    Profile,
    ProfileModeConfig,
)
from tests.unit.test_a_mascara_do_cartao_vale_com_o_vpad_de_pe import (
    P2,
    P3,
    PERFIL,
    _Daemon,
    _ensaio,
    _vpad_do,
)
from tests.unit.test_o_jogo_so_nasce_com_o_ambiente_do_proprio_arme import (
    APPID,
    _a_mesa_do_lancamento,
    _marker,
)

__all__ = ["_ensaio"]

_CANAL = {"dualsense": "uhid", "xbox": "uinput", "nintendo": "uinput"}
_CAMINHO: dict[str, str | None] = {"dualsense": "dualsense", "xbox": "xbox", "nintendo": None}
_MODOS = ("dualsense", "xbox", "nintendo", "navegacao")


def _perfil(flavor: str) -> Profile:
    return Profile(
        name="Jogo da Régua",
        match=MatchCriteria(window_class=[f"steam_app_{APPID}"]),
        priority=90,
        mode=ProfileModeConfig(kind="gamepad", gamepad_flavor=flavor),
    )


class _Computador:
    """O daemon num modo do computador, com ``controles`` DualSense e o co-op ligado com mais de um.

    O modo do perfil, aplicado pelo arme, veste todos os vpads da máscara pedida.
    """

    def __init__(self, modo: str, controles: int = 1) -> None:
        navega = modo == "navegacao"
        mascara = "dualsense" if navega else modo
        self.config = SimpleNamespace(
            gamepad_emulation_enabled=not navega, gamepad_flavor=mascara,
            gamepad_caminho=_CAMINHO[mascara], coop_enabled=controles > 1,
        )
        self.controles = controles
        self.controller = SimpleNamespace(
            describe_controllers=lambda: [{"connected": True}] * self.controles)
        self.store = None
        self.bus = EventBus()
        self._native_mode = False
        self._gamepad_device: Any = None
        self._coop_manager: Any = None
        self._vestir(None if navega else mascara)

    def _vestir(self, mascara: str | None) -> None:
        if mascara is None:
            self._gamepad_device = self._coop_manager = None
            return
        self._gamepad_device = SimpleNamespace(backend=_CANAL[mascara], flavor=mascara)
        self._coop_manager = SimpleNamespace(_players={
            n: SimpleNamespace(vpad=SimpleNamespace(backend=_CANAL[mascara], flavor=mascara))
            for n in range(2, self.controles + 1)
        })

    def is_native_mode(self) -> bool:
        return self._native_mode

    def is_paused(self) -> bool:
        return False

    def set_native_mode(self, enabled: bool, **_kw: Any) -> bool:
        self._native_mode = bool(enabled)
        return self._native_mode

    def set_gamepad_emulation_desfecho(
        self, enabled: bool, flavor: str | None = None, *, origin: str,
        caminho: str | None = None, caminho_e_escolha: bool = True, grava_o_modo: Any = False,
    ) -> str:
        if not enabled:
            self.config.gamepad_emulation_enabled = False
            self._vestir(None)
            return gp.EMU_DESLIGADO
        mascara = flavor or self.config.gamepad_flavor
        self.config.gamepad_flavor = mascara
        self.config.gamepad_caminho = caminho or _CAMINHO[mascara]
        self.config.gamepad_emulation_enabled = True
        self._vestir(mascara)
        return gp.EMU_APLICADO

    def apply_profile_mode(self, mode: Any, *, profile: Any = None, origin: str = "") -> str:
        self.set_gamepad_emulation_desfecho(True, mode.gamepad_flavor, origin="profile")
        return lifecycle.APLICADO

    def apply_profile_suppression(
        self, desired: bool, *, profile: Any = None, origin: str = ""
    ) -> str:
        return lifecycle.APLICADO


def _env(caminho: Path) -> list[str]:
    return [
        linha for linha in caminho.read_text(encoding="utf-8").splitlines()
        if linha and not linha.startswith("#")
    ]


def _armar(env_dir: Path, monkeypatch: pytest.MonkeyPatch, daemon: Any, flavor: str) -> None:
    _a_mesa_do_lancamento(env_dir, monkeypatch, _perfil(flavor), em_disco=[], lenta_s=0.0)
    monkeypatch.setattr(le, "_ESCREVENTE", None)
    _marker(env_dir)
    le.arm_launch_profile(daemon)


def test_o_default_env_segue_no_dualsense_com_o_jogo_em_xbox_armado(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A prova (1): o computador em DualSense e o jogo com perfil em Xbox armado."""
    daemon = _Computador("dualsense")
    _armar(tmp_path, monkeypatch, daemon, "xbox")
    assert daemon._gamepad_device.flavor == "xbox", "premissa: o arme vestiu o Xbox"
    le.materialize_launch_env(daemon)
    padrao = _env(tmp_path / "default.env")
    do_jogo = _env(tmp_path / f"steam_app_{APPID}.env")
    assert "SDL_JOYSTICK_HIDAPI=0" in do_jogo, do_jogo
    assert "SDL_JOYSTICK_HIDAPI=0" not in padrao, f"o default.env herdou o Xbox do jogo: {padrao}"
    assert any(linha.startswith("PROTON_DISABLE_HIDRAW=") for linha in padrao), padrao


@pytest.mark.parametrize("controles", [1, 4])
@pytest.mark.parametrize("modo", _MODOS)
def test_os_quatro_modos_como_modo_do_computador(
    modo: str, controles: int, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A prova (4): o ``default.env`` depois do arme é o de antes, em todo modo do computador."""
    _a_mesa_do_lancamento(tmp_path, monkeypatch, None, em_disco=[], lenta_s=0.0)  # type: ignore[arg-type]
    monkeypatch.setattr(le, "_ESCREVENTE", None)
    monkeypatch.setattr(le, "_steam_profiles", lambda _daemon: [])
    daemon = _Computador(modo, controles)
    le.materialize_launch_env(daemon)
    antes = _env(tmp_path / "default.env")
    do_jogo = "xbox" if modo in ("dualsense", "navegacao") else "dualsense"
    _armar(tmp_path, monkeypatch, daemon, do_jogo)
    assert daemon._gamepad_device.flavor == do_jogo, "premissa: o arme mudou o modo"
    le.materialize_launch_env(daemon)
    assert _env(tmp_path / "default.env") == antes
    assert _env(tmp_path / f"steam_app_{APPID}.env") != antes, "o jogo não mudou o ambiente"


class _ComOJogo(_Daemon):
    """O ensaio do cartão com o barramento, e o arme que veste o modo do perfil em todos."""

    def __init__(self) -> None:
        super().__init__("dualsense")
        self.bus = EventBus()

    def is_native_mode(self) -> bool:
        return bool(self._native_mode)

    def is_paused(self) -> bool:
        return False

    def apply_profile_mode(self, mode: Any, *, profile: Any = None, origin: str = "") -> str:
        desfecho = self.set_gamepad_emulation_desfecho(
            True, mode.gamepad_flavor, origin="gesto_de_perfil", caminho=mode.gamepad_flavor)
        return lifecycle.APLICADO if desfecho in gp.DESFECHOS_EMULACAO_ATIVA else desfecho

    def apply_profile_suppression(
        self, desired: bool, *, profile: Any = None, origin: str = ""
    ) -> str:
        return lifecycle.APLICADO


def _todos(d: Any) -> list[tuple[str, str]]:
    return [(v.flavor, v.backend) for v in (d._gamepad_device, _vpad_do(P2), _vpad_do(P3))]


def _o_jogo_em_xbox(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> _ComOJogo:
    """P1, P2 e P3 no DualSense, o jogo com perfil em Xbox armado e aberto."""
    loader.save_profile(
        Profile(name=PERFIL, match=MatchAny(),
                mode=ProfileModeConfig(kind="gamepad", gamepad_flavor="dualsense")),
        origem="teste",
    )
    d = _ComOJogo()
    d.store = SimpleNamespace(active_profile=PERFIL)
    assert gp.start_gamepad_emulation_desfecho(
        d, None, origin="manual", caminho="dualsense") == gp.EMU_APLICADO
    d._coop_manager = CoopManager(d)  # type: ignore[arg-type]
    d._coop_manager.sync(force=True)
    computador = _todos(d)
    assert [m for m, _ in computador] == ["dualsense"] * 3, "premissa"
    _armar(tmp_path, monkeypatch, d, "xbox")
    d.display_authority = "game"
    assert [m for m, _ in _todos(d)] == ["xbox"] * 3, "premissa: o arme vestiu o Xbox nos três"
    return d


def _o_jogo_fecha(d: _ComOJogo) -> None:
    d.bus.publish(EventTopic.JOGO_FECHOU, {"appid": APPID, "t": 0.0})


def test_o_jogo_que_fecha_devolve_o_dualsense_ao_p1_e_aos_secundarios(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A prova (2): o ``JOGO_FECHOU`` do appid devolve o par do DualSense, e o diário diz uma vez.

    Enquanto o pad segue travado pelo lançamento, a volta é recusada e espera o tique seguinte.
    """
    d = _o_jogo_em_xbox(tmp_path, monkeypatch)
    computador = ("dualsense", "dualsense")
    with structlog.testing.capture_logs() as registros:
        _o_jogo_fecha(d)
        assert le.o_fim_do_jogo_devolve_o_modo(d) == gp.EMU_BLOQUEADO_POR_JOGO
        assert [m for m, _ in _todos(d)] == ["xbox"] * 3
        lifecycle._soltar_o_pad_do_lancamento(d, lifecycle.MOTIVO_DA_AUTORIDADE)  # type: ignore[arg-type]
        d.display_authority = "daemon"
        for _ in range(3):
            le.arm_launch_profile(d)
    assert [m for m, _ in _todos(d)] == ["dualsense"] * 3, "o fim do jogo não devolveu o modo"
    assert (d.config.gamepad_flavor, d.config.gamepad_caminho) == computador
    voltas = [r for r in registros if r["event"] == "modo_do_computador_devolvido"]
    assert len(voltas) == 1, voltas
    assert (voltas[0]["de"], voltas[0]["para"]) == ("xbox", "dualsense")


def test_o_modo_escolhido_a_mao_no_jogo_fica_depois_do_fim(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A prova (3): a escolha à mão durante o jogo é o modo do computador; o fim não a desfaz."""
    d = _o_jogo_em_xbox(tmp_path, monkeypatch)
    d.escolher_o_modo_unico("nintendo", porta="controle")
    assert [m for m, _ in _todos(d)] == ["nintendo"] * 3, "premissa"
    lifecycle._soltar_o_pad_do_lancamento(d, lifecycle.MOTIVO_DA_AUTORIDADE)  # type: ignore[arg-type]
    d.display_authority = "daemon"
    with structlog.testing.capture_logs() as registros:
        _o_jogo_fecha(d)
        for _ in range(3):
            le.arm_launch_profile(d)
    assert [m for m, _ in _todos(d)] == ["nintendo"] * 3, "o fim do jogo desfez a escolha à mão"
    assert not [r for r in registros if r["event"] == "modo_do_computador_devolvido"]
    le.materialize_launch_env(d)
    assert "SDL_JOYSTICK_HIDAPI=0" in _env(tmp_path / "default.env"), "o computador é o Nintendo"
