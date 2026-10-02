"""R-04 (auditoria 23/07) — o modo do perfil é armado NO LAUNCH, não na janela."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from hefesto_dualsense4unix.daemon import launch_env as le
from hefesto_dualsense4unix.profiles.schema import (
    MatchCriteria,
    Profile,
    ProfileModeConfig,
)

APPID = 1599660


def _marker(tmp_path: Path, *, appid: int, epoch: int) -> Path:
    (tmp_path / "last_run").write_text(
        f"appid={appid}\nepoch={epoch}\npid=1\n", encoding="utf-8"
    )
    return tmp_path


def _perfil(flavor: str = "dualsense", *, suprime: bool = False) -> Profile:
    return Profile(
        name="sackboy_nativo",
        match=MatchCriteria(window_class=[f"steam_app_{APPID}"]),
        priority=80,
        mode=ProfileModeConfig(kind="gamepad", gamepad_flavor=flavor),
        suppress_desktop_emulation=suprime,
    )


class _DaemonFalso:
    def __init__(self) -> None:
        self.aplicados: list[tuple[Any, Any, str]] = []
        self.suprimidos: list[tuple[bool, Any, str]] = []
        self.config = SimpleNamespace(
            gamepad_emulation_enabled=True, gamepad_flavor="xbox"
        )
        self._gamepad_device = SimpleNamespace(backend="uinput")
        self._coop_manager = None
        self.controller = SimpleNamespace()

    def is_native_mode(self) -> bool:
        return False

    def apply_profile_mode(
        self, mode: Any, *, profile: Any = None, origin: str = "autoswitch"
    ) -> str:
        self.aplicados.append((mode, profile, origin))
        return "aplicado"

    def apply_profile_suppression(
        self, desired: bool, *, profile: Any = None, origin: str = "autoswitch"
    ) -> str:
        self.suprimidos.append((desired, profile, origin))
        return "aplicado"


@pytest.fixture
def env_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(le, "launch_env_dir", lambda ensure=False: tmp_path)
    return tmp_path


class TestArmingPeloMarker:
    def test_launch_fresco_aplica_o_modo_do_perfil(
        self, env_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """O caso dela: máscara global xbox, Sackboy com perfil dualsense."""
        _marker(env_dir, appid=APPID, epoch=1000)
        perfil = _perfil()
        monkeypatch.setattr(
            le, "_steam_profiles", lambda daemon: [(APPID, perfil)]
        )
        daemon = _DaemonFalso()

        resultado = le.arm_launch_profile(daemon, base_dir=env_dir, now=1001.0)

        assert resultado is not None and resultado["armado"] is True
        assert len(daemon.aplicados) == 1
        mode, profile, origin = daemon.aplicados[0]
        assert mode.gamepad_flavor == "dualsense"
        assert profile is perfil
        assert origin == "launch", (
            "origem 'launch' NÃO fura o lock manual (R-03): se ela mexeu na "
            "máscara nos últimos 30 s, o gesto dela é mais novo que o perfil"
        )

    def test_mesmo_launch_arma_uma_vez_so(
        self, env_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A reconciliação roda a 1 Hz — sem idempotência isso seria um apply"""
        _marker(env_dir, appid=APPID, epoch=1000)
        monkeypatch.setattr(
            le, "_steam_profiles", lambda daemon: [(APPID, _perfil())]
        )
        daemon = _DaemonFalso()

        le.arm_launch_profile(daemon, base_dir=env_dir, now=1001.0)
        le.arm_launch_profile(daemon, base_dir=env_dir, now=1002.0)
        le.arm_launch_profile(daemon, base_dir=env_dir, now=1003.0)

        assert len(daemon.aplicados) == 1

    def test_marker_velho_nao_rearma(
        self, env_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """`daemon.status` da CLI meia hora depois não pode ressuscitar o"""
        _marker(env_dir, appid=APPID, epoch=1000)
        monkeypatch.setattr(
            le, "_steam_profiles", lambda daemon: [(APPID, _perfil())]
        )
        daemon = _DaemonFalso()

        assert (
            le.arm_launch_profile(
                daemon, base_dir=env_dir, now=1000 + le.LAUNCH_ARM_WINDOW_SEC + 1
            )
            is None
        )
        assert daemon.aplicados == []

    def test_sem_marker_nao_faz_nada(self, env_dir: Path) -> None:
        daemon = _DaemonFalso()
        assert le.arm_launch_profile(daemon, base_dir=env_dir, now=1.0) is None
        assert daemon.aplicados == []

    def test_jogo_sem_perfil_nao_arma(
        self, env_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Mullet Mad Jack sem perfil próprio: nada a impor (R-02 cuida do"""
        _marker(env_dir, appid=2111190, epoch=1000)
        monkeypatch.setattr(le, "_steam_profiles", lambda daemon: [])
        monkeypatch.setattr(le, "steam_input_appids", lambda path=None: set())
        daemon = _DaemonFalso()

        resultado = le.arm_launch_profile(daemon, base_dir=env_dir, now=1001.0)

        assert resultado == {
            "appid": 2111190, "armado": False, "motivo": "sem_perfil"
        }
        assert daemon.aplicados == []

    def test_perfil_sem_secao_mode_nao_arma_modo_de_perfil_nenhum(
        self, env_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """R-02 continua de pé: perfil sem `mode` não tem opinião sobre a"""
        _marker(env_dir, appid=APPID, epoch=1000)
        sem_modo = Profile(
            name="so_cores",
            match=MatchCriteria(window_class=[f"steam_app_{APPID}"]),
            priority=10,
        )
        monkeypatch.setattr(
            le, "_steam_profiles", lambda daemon: [(APPID, sem_modo)]
        )
        daemon = _DaemonFalso()

        resultado = le.arm_launch_profile(daemon, base_dir=env_dir, now=1001.0)

        assert resultado is not None
        assert resultado["ponte_da_escada"] is True, "não é opinião do perfil"
        assert resultado["ponte_do_carimbo"] is False

    def test_appid_da_allowlist_do_steam_input_nao_e_armado(
        self, env_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Contradição 11 da §5 do plano: a allowlist é opt-in explícito de 'o"""
        _marker(env_dir, appid=2111190, epoch=1000)
        monkeypatch.setattr(le, "steam_input_appids", lambda path=None: {2111190})
        monkeypatch.setattr(
            le, "_steam_profiles", lambda daemon: [(2111190, _perfil())]
        )
        daemon = _DaemonFalso()

        resultado = le.arm_launch_profile(daemon, base_dir=env_dir, now=1001.0)

        assert resultado is not None
        assert resultado["motivo"] == "allowlist_steam_input"
        assert daemon.aplicados == []


class TestAllowlistPulaSoAMascara:
    """ALLOWLIST-SUPRESSAO-01 (auditoria 24/07)."""

    def test_allowlist_aplica_a_supressao_do_perfil(
        self, env_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _marker(env_dir, appid=2111190, epoch=1000)
        perfil = _perfil(suprime=True)
        monkeypatch.setattr(le, "steam_input_appids", lambda path=None: {2111190})
        monkeypatch.setattr(le, "_steam_profiles", lambda daemon: [(2111190, perfil)])
        daemon = _DaemonFalso()

        resultado = le.arm_launch_profile(daemon, base_dir=env_dir, now=1001.0)

        assert resultado is not None
        assert resultado["motivo"] == "allowlist_steam_input"
        assert daemon.aplicados == []
        assert daemon.suprimidos == [(True, perfil, "launch")]

    def test_supressao_vai_com_origin_launch(
        self, env_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """`origin="launch"` NÃO fura o lock manual (R-03): se ela alternou o"""
        _marker(env_dir, appid=APPID, epoch=1000)
        perfil = _perfil(suprime=True)
        monkeypatch.setattr(le, "steam_input_appids", lambda path=None: set())
        monkeypatch.setattr(le, "_steam_profiles", lambda daemon: [(APPID, perfil)])
        daemon = _DaemonFalso()

        le.arm_launch_profile(daemon, base_dir=env_dir, now=1001.0)

        assert daemon.suprimidos == [(True, perfil, "launch")]
        assert daemon.aplicados and daemon.aplicados[0][2] == "launch"

    def test_perfil_sem_modo_ainda_aplica_a_supressao(
        self, env_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Perfil só-de-cores com modo jogo ligado: nada a armar na máscara, mas"""
        _marker(env_dir, appid=APPID, epoch=1000)
        so_cores = Profile(
            name="so_cores",
            match=MatchCriteria(window_class=[f"steam_app_{APPID}"]),
            priority=10,
            suppress_desktop_emulation=True,
        )
        monkeypatch.setattr(le, "steam_input_appids", lambda path=None: set())
        monkeypatch.setattr(le, "_steam_profiles", lambda daemon: [(APPID, so_cores)])
        daemon = _DaemonFalso()

        resultado = le.arm_launch_profile(daemon, base_dir=env_dir, now=1001.0)

        assert resultado is not None
        assert daemon.suprimidos == [(True, so_cores, "launch")]

    def test_jogo_da_allowlist_sem_perfil_nao_suprime(
        self, env_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Sem perfil não há opinião nenhuma a aplicar — nem máscara, nem"""
        _marker(env_dir, appid=2111190, epoch=1000)
        monkeypatch.setattr(le, "steam_input_appids", lambda path=None: {2111190})
        monkeypatch.setattr(le, "_steam_profiles", lambda daemon: [])
        daemon = _DaemonFalso()

        resultado = le.arm_launch_profile(daemon, base_dir=env_dir, now=1001.0)

        assert resultado is not None
        assert resultado["motivo"] == "allowlist_steam_input"
        assert daemon.suprimidos == []

    def test_applier_que_explode_nao_derruba_o_arming(
        self, env_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A supressão é best-effort: falhar nela não pode custar a máscara do"""
        _marker(env_dir, appid=APPID, epoch=1000)
        perfil = _perfil(suprime=True)
        monkeypatch.setattr(le, "steam_input_appids", lambda path=None: set())
        monkeypatch.setattr(le, "_steam_profiles", lambda daemon: [(APPID, perfil)])
        daemon = _DaemonFalso()

        def _explode(*a: Any, **kw: Any) -> str:
            raise RuntimeError("supressão quebrou")

        daemon.apply_profile_suppression = _explode  # type: ignore[assignment]

        resultado = le.arm_launch_profile(daemon, base_dir=env_dir, now=1001.0)

        assert resultado is not None and resultado["armado"] is True
        assert len(daemon.aplicados) == 1


class TestFiacaoNoPollLoop:
    def test_dispatch_gamepad_dispara_a_reconciliacao_de_launch(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Sem esta fiação o arming existiria e nunca rodaria — é o defeito"""
        import hefesto_dualsense4unix.daemon.subsystems.gamepad as gp

        chamadas: list[str] = []
        monkeypatch.setattr(
            le, "arm_launch_profile", lambda daemon, **k: chamadas.append("arm")
        )
        monkeypatch.setattr(
            gp, "sync_steam_input_exception", lambda daemon, **k: chamadas.append("si")
        )
        daemon = SimpleNamespace(_gamepad_device=None)

        gp.dispatch_gamepad(daemon, SimpleNamespace(), frozenset())

        assert chamadas == ["arm", "si"]

    def test_reconciliacao_e_throttada(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """O dispatch roda a cada tick do poll loop: ler o marker do disco em"""
        import hefesto_dualsense4unix.daemon.subsystems.gamepad as gp

        chamadas: list[str] = []
        monkeypatch.setattr(
            le, "arm_launch_profile", lambda daemon, **k: chamadas.append("arm")
        )
        monkeypatch.setattr(gp, "sync_steam_input_exception", lambda daemon, **k: None)
        daemon = SimpleNamespace(_gamepad_device=None)

        for _ in range(50):
            gp.dispatch_gamepad(daemon, SimpleNamespace(), frozenset())

        assert chamadas == ["arm"]
