"""R-06 (auditoria 23/07) — a allowlist do Steam Input deixa de ser inerte.

`steam_input_apps.txt` (com o appid 2111190 do Mullet Mad Jack) era respeitada
SÓ pelo guard de VDF. Nada no caminho de LANÇAMENTO a consultava — o jogo caía
no `default.env`, que carrega o dedup (`SDL_GAMECONTROLLER_IGNORE_DEVICES` +
`PROTON_DISABLE_HIDRAW`) — e o daemon continuava fazendo EVIOCGRAB no evdev e
mandando o broker esconder o hidraw do controle físico. Ou seja: o jogo cuja
via oficial de DualSense é a API Steamworks (`SetDualSenseTriggerEffect`, que
só funciona com o Steam Input DAQUELE jogo ligado) não achava controle nenhum
da Sony, e a exceção que ela configurou não mudava absolutamente nada.

Contradição 11 da §5 do plano: R-05 empurra o dedup para os `.env` por appid;
R-06 exige `.env` SEM dedup para os appids da allowlist. A allowlist é opt-in
EXPLÍCITO e VENCE para os appids listados; para todos os outros vale o R-05.

Preço aceito e documentado: para esses appids o jogo passa a ver o físico E o
vpad. É o que "opt-in" significa; a alternativa é a exceção não existir.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

import hefesto_dualsense4unix.daemon.subsystems.gamepad as gp
from hefesto_dualsense4unix.daemon import launch_env as le

MMJ = 2111190
_IGNORE = "SDL_GAMECONTROLLER_IGNORE_DEVICES"
_DISABLE = "PROTON_DISABLE_HIDRAW"


def _env_do_arquivo(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    for linha in path.read_text(encoding="utf-8").splitlines():
        if linha.startswith("#") or "=" not in linha:
            continue
        chave, valor = linha.split("=", 1)
        out[chave] = valor
    return out


def _daemon_falso() -> SimpleNamespace:
    return SimpleNamespace(
        is_native_mode=lambda: False,
        config=SimpleNamespace(
            gamepad_emulation_enabled=True, gamepad_flavor="dualsense"
        ),
        _gamepad_device=SimpleNamespace(backend="uhid", _started=True),
        _coop_manager=None,
        controller=SimpleNamespace(),
        store=SimpleNamespace(window_detect_current_class=None),
    )


class TestAllowlistNoArquivo:
    def test_le_appids_do_arquivo_xdg(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        (tmp_path / "steam_input_apps.txt").write_text(
            "# comentário\n2111190\n\nlixo\n620 \n", encoding="utf-8"
        )
        monkeypatch.setattr(
            "hefesto_dualsense4unix.utils.xdg_paths.config_dir",
            lambda ensure=False: tmp_path,
        )
        assert le.steam_input_appids() == {MMJ, 620}

    def test_arquivo_ausente_nao_levanta(self, tmp_path: Path) -> None:
        assert le.steam_input_appids(tmp_path / "nao-existe.txt") == set()


class TestEnvPorAppidDaAllowlist:
    def test_appid_da_allowlist_ganha_env_sem_dedup_mesmo_sem_perfil(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Era o buraco: sem perfil, o MMJ caía no `default.env` COM dedup e o
        físico ficava escondido do jogo que precisa vê-lo."""
        monkeypatch.setattr(le, "launch_env_dir", lambda ensure=False: tmp_path)
        monkeypatch.setattr(le, "_steam_profiles", lambda daemon: [])
        monkeypatch.setattr(le, "steam_input_appids", lambda path=None: {MMJ})

        le.materialize_launch_env(_daemon_falso())

        env = _env_do_arquivo(tmp_path / f"steam_app_{MMJ}.env")
        assert _IGNORE not in env, "o dedup mata a via oficial de DualSense do jogo"
        assert _DISABLE not in env
        assert env["__GL_SHADER_DISK_CACHE"] == "1"  # o preload inócuo segue
        # E o default.env continua com o dedup — a exceção é POR APPID.
        assert _IGNORE in _env_do_arquivo(tmp_path / "default.env")

    def test_allowlist_vence_o_perfil_do_mesmo_appid(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Contradição 11: opt-in explícito vence o prognóstico do R-05."""
        monkeypatch.setattr(le, "launch_env_dir", lambda ensure=False: tmp_path)
        perfil = SimpleNamespace(
            name="mmj",
            mode=SimpleNamespace(kind="gamepad", gamepad_flavor="xbox"),
        )
        monkeypatch.setattr(le, "_steam_profiles", lambda daemon: [(MMJ, perfil)])
        monkeypatch.setattr(le, "steam_input_appids", lambda path=None: {MMJ})

        le.materialize_launch_env(_daemon_falso())

        env = _env_do_arquivo(tmp_path / f"steam_app_{MMJ}.env")
        assert _IGNORE not in env
        assert _DISABLE not in env


class TestSessaoDaExcecao:
    def test_marker_do_wrapper_liga_a_excecao(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        (tmp_path / "last_run").write_text(
            f"appid={MMJ}\nepoch=1000\npid=1\n", encoding="utf-8"
        )
        monkeypatch.setattr(le, "pid_is_alive", lambda pid: True)
        assert (
            le.steam_input_exception_appid(
                _daemon_falso(), base_dir=tmp_path, now=1010.0, allowlist={MMJ}
            )
            == MMJ
        )

    def test_janela_em_foco_liga_a_excecao_sem_wrapper(
        self, tmp_path: Path
    ) -> None:
        """Jogo aberto sem as LaunchOptions do Hefesto também conta."""
        daemon = _daemon_falso()
        daemon.store.window_detect_current_class = f"steam_app_{MMJ}"
        assert (
            le.steam_input_exception_appid(
                daemon, base_dir=tmp_path, now=1.0, allowlist={MMJ}
            )
            == MMJ
        )

    def test_jogo_fora_da_allowlist_nao_liga(self, tmp_path: Path) -> None:
        daemon = _daemon_falso()
        daemon.store.window_detect_current_class = "steam_app_1599660"
        assert (
            le.steam_input_exception_appid(
                daemon, base_dir=tmp_path, now=1.0, allowlist={MMJ}
            )
            is None
        )

    def test_allowlist_vazia_nunca_liga(self, tmp_path: Path) -> None:
        daemon = _daemon_falso()
        daemon.store.window_detect_current_class = f"steam_app_{MMJ}"
        assert (
            le.steam_input_exception_appid(
                daemon, base_dir=tmp_path, now=1.0, allowlist=set()
            )
            is None
        )


class _DaemonComGrab:
    """Daemon falso que observa grab do evdev e chamadas ao broker."""

    def __init__(self, *, appid_ativo: int | None) -> None:
        self.grabs: list[bool] = []
        self.restores = 0
        self.hides: list[str] = []
        self._appid_ativo = appid_ativo
        self.config = SimpleNamespace(
            gamepad_emulation_enabled=True, gamepad_flavor="dualsense"
        )
        self._gamepad_device = SimpleNamespace(backend="uhid", _started=True)
        self._coop_manager = None
        pai = self

        class _Evdev:
            grab_state = None

            def set_grab(self, grab: bool) -> bool:
                pai.grabs.append(grab)
                return True

        self.controller = SimpleNamespace(
            _evdev=_Evdev(), hidraw_path=lambda *a: "/dev/hidraw0"
        )

    def is_native_mode(self) -> bool:
        return False


@pytest.fixture
def _broker_falso(monkeypatch: pytest.MonkeyPatch) -> None:
    """Substitui o cliente do broker; nada de socket real no teste."""
    import hefesto_dualsense4unix.integrations.hidraw_broker_client as bc

    def _client_for(daemon: Any) -> Any:
        class _C:
            def hide(self, node: str) -> None:
                daemon.hides.append(node)

            def restore_all(self) -> None:
                daemon.restores += 1

        return _C()

    monkeypatch.setattr(bc, "broker_client_for", _client_for)
    monkeypatch.setattr(
        bc, "broker_call_nonblocking", lambda daemon, fn: fn()
    )


class TestModoNativoPorAppid:
    def test_entrar_na_excecao_solta_grab_e_expoe_o_hidraw(
        self, monkeypatch: pytest.MonkeyPatch, _broker_falso: None
    ) -> None:
        daemon = _DaemonComGrab(appid_ativo=MMJ)
        monkeypatch.setattr(
            le, "steam_input_exception_appid", lambda d, **k: MMJ
        )

        assert gp.sync_steam_input_exception(daemon) is True

        assert daemon.grabs == [False], "o jogo tem de ver o evdev do físico"
        assert daemon.restores == 1, "o hidraw escondido é o que matava a exceção"
        assert gp.steam_input_excecao_ativa(daemon) is True

    def test_com_excecao_ativa_o_broker_nao_reesconde(
        self, monkeypatch: pytest.MonkeyPatch, _broker_falso: None
    ) -> None:
        """Sem este gate a reconciliação online (≤30 s) desfaria a exceção no
        meio do jogo — o físico voltaria a 0600."""
        daemon = _DaemonComGrab(appid_ativo=MMJ)
        daemon._steam_input_excecao = True

        gp._broker_sync_grab(daemon, True)
        gp.rehide_physical_hidraw(daemon)
        gp._set_controller_grab(daemon, True)

        assert daemon.hides == []
        assert daemon.grabs == []

    def test_sem_excecao_o_hide_e_o_grab_seguem_iguais(
        self, monkeypatch: pytest.MonkeyPatch, _broker_falso: None
    ) -> None:
        """Sanidade: o gate não pode desligar o comportamento default."""
        daemon = _DaemonComGrab(appid_ativo=None)

        gp._set_controller_grab(daemon, True)

        assert daemon.grabs == [True]
        assert daemon.hides == ["/dev/hidraw0"]

    def test_sair_da_excecao_retoma_grab_e_hide(
        self, monkeypatch: pytest.MonkeyPatch, _broker_falso: None
    ) -> None:
        daemon = _DaemonComGrab(appid_ativo=None)
        daemon._steam_input_excecao = True
        monkeypatch.setattr(
            le, "steam_input_exception_appid", lambda d, **k: None
        )

        assert gp.sync_steam_input_exception(daemon) is False

        assert daemon.grabs == [True]
        assert daemon.hides == ["/dev/hidraw0"]

    def test_sem_borda_nao_toca_em_nada(
        self, monkeypatch: pytest.MonkeyPatch, _broker_falso: None
    ) -> None:
        """A reconciliação roda a 1 Hz: sem borda tem de ser uma comparação."""
        daemon = _DaemonComGrab(appid_ativo=None)
        monkeypatch.setattr(
            le, "steam_input_exception_appid", lambda d, **k: None
        )

        gp.sync_steam_input_exception(daemon)
        gp.sync_steam_input_exception(daemon)

        assert daemon.grabs == []
        assert daemon.hides == []
        assert daemon.restores == 0
