"""ESCONDER-EM-VEZ-DE-SAIR-01 — a marca esconde o FÍSICO e deixa o co-op vivo."""

from __future__ import annotations

import asyncio
import contextlib
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

import hefesto_dualsense4unix.daemon.subsystems.gamepad as gp
from hefesto_dualsense4unix.daemon import launch_env as le

MMJ = 2111190

_IGNORE = "SDL_GAMECONTROLLER_IGNORE_DEVICES"


class _VpadFalso:
    def __init__(self, flavor: str = "dualsense", backend: str = "uhid") -> None:
        self.flavor = flavor
        self.backend = backend
        self._started = True
        self.parado = False

    def stop(self) -> None:
        self.parado = True
        self._started = False


class _CoopFalso:
    """Co-op com N secundários de pé, contando quem manda derrubá-los."""

    def __init__(self, jogadores: int) -> None:
        self._players: dict[str, Any] = {
            f"AA:BB:CC:00:00:0{i}": SimpleNamespace(
                vpad=_VpadFalso(), player_index=i + 2
            )
            for i in range(jogadores)
        }
        self.desligado = 0

    def disable(self) -> None:
        self.desligado += 1
        self._players.clear()

    def sync(self, *, force: bool = False, origem: str | None = None) -> None:
        return None


class _DaemonFalso:
    """O mínimo que a borda da exceção toca — grab, broker, vpad e co-op."""

    def __init__(self, *, jogadores: int = 0, nativo: bool = False) -> None:
        self.config = SimpleNamespace(
            gamepad_emulation_enabled=True,
            gamepad_flavor="dualsense",
            rumble_active=None,
        )
        self._gamepad_device: Any = _VpadFalso()
        self._coop_manager = _CoopFalso(jogadores)
        self._tasks: list[Any] = []
        self._nativo = nativo
        self.grabs: list[bool] = []
        self.restores = 0
        self.hides: list[str] = []
        self.store = SimpleNamespace(
            window_detect_current_class=None, bump=lambda chave: None
        )
        pai = self

        class _Evdev:
            grab_state = None

            def set_grab(self, grab: bool) -> bool:
                pai.grabs.append(grab)
                return True

        def _hidraw(identity: str | None = None) -> str:
            if identity is None:
                return "/dev/hidraw0"
            return f"/dev/hidraw{1 + int(identity[-1])}"

        self.controller = SimpleNamespace(
            _evdev=_Evdev(),
            hidraw_path=_hidraw,
            set_rumble=lambda **k: None,
            primary_uniq="AA:BB:CC:00:00:FF",
        )

    def is_native_mode(self) -> bool:
        return self._nativo

    def _is_stopping(self) -> bool:
        return False


@pytest.fixture()
def _broker_falso(monkeypatch: pytest.MonkeyPatch) -> None:
    """Cliente do broker dublado — nenhum socket real, nenhum chmod real."""
    import hefesto_dualsense4unix.integrations.hidraw_broker_client as bc

    def _client_for(daemon: Any) -> Any:
        class _C:
            def hide(self, node: str) -> None:
                daemon.hides.append(node)

            def restore(self, node: str) -> None:
                daemon.restores += 1

            def restore_all(self) -> None:
                daemon.restores += 1

        return _C()

    monkeypatch.setattr(bc, "broker_client_for", _client_for)
    monkeypatch.setattr(bc, "broker_call_nonblocking", lambda daemon, fn: fn())


@pytest.fixture()
def _sem_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """A borda regrava a `.env` do wrapper; aqui isso não pode tocar o disco."""
    monkeypatch.setattr(gp, "_materialize_launch_env", lambda daemon: None)


@pytest.fixture()
def _jogo_marcado_na_frente(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(le, "steam_input_exception_appid", lambda d, **k: MMJ)


async def _encerrar_vigia(daemon: Any) -> Any:
    """Cancela a task-vigia (se nasceu) e a DEVOLVE para inspeção."""
    vigia = getattr(daemon, "_steam_input_vigia", None)
    if vigia is not None:
        vigia.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await vigia
    return vigia


async def test_com_dois_controles_a_marca_nao_derruba_o_jogador_2(
    _broker_falso: None, _sem_env: None, _jogo_marcado_na_frente: None
) -> None:
    """A MORDIDA: faça a borda de entrada da marca desligar o co-op ou parar o P1."""
    daemon = _DaemonFalso(jogadores=1)
    vpad_do_p1 = daemon._gamepad_device

    assert gp.sync_steam_input_exception(daemon) is True
    vigia = await _encerrar_vigia(daemon)

    assert daemon._gamepad_device is vpad_do_p1, "o vpad do P1 tem de ficar de pé"
    assert vpad_do_p1.parado is False
    assert daemon._coop_manager.desligado == 0, (
        "o co-op foi desligado — é este teardown que derrubava o jogador 2"
    )
    assert len(daemon._coop_manager._players) == 1, "o jogador 2 saiu da mesa"
    assert vigia is None, (
        "nasceu a task-vigia da suspensão — ela só existe para desfazer uma "
        "suspensão, e a marca não suspende mais nada"
    )


async def test_a_marca_nao_arma_vigia_porque_nao_ha_o_que_devolver(
    _broker_falso: None, _sem_env: None, _jogo_marcado_na_frente: None
) -> None:
    """Sem suspensão não nasce task-vigia — e isso é a prova de que a borda"""
    daemon = _DaemonFalso(jogadores=1)

    assert gp.sync_steam_input_exception(daemon) is True
    vigia = await _encerrar_vigia(daemon)

    assert vigia is None
    assert daemon._tasks == [], "a marca pendurou task no daemon dela"
    assert daemon._gamepad_device is not None


def test_o_perfil_do_jogo_marcado_volta_a_poder_criar_o_vpad(
    _broker_falso: None, _sem_env: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A MORDIDA: devolva `if origin != "manual": return False` ao gate de"""
    import hefesto_dualsense4unix.integrations.virtual_pad as vp

    monkeypatch.setattr(vp, "make_virtual_pad", lambda key, **kw: _VpadFalso(flavor=key))
    monkeypatch.setattr(gp, "start_motion_reader", lambda daemon, device: None)
    daemon = _DaemonFalso()
    daemon._gamepad_device = None
    daemon._steam_input_excecao = True

    assert gp.start_gamepad_emulation(daemon, "dualsense", origin="profile") is True
    assert daemon._gamepad_device is not None


def test_a_rede_de_seguranca_do_vpad_vale_dentro_do_jogo_marcado(
    _broker_falso: None, _sem_env: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """VPAD-09 dispara na reconexão BT — o evento mais frequente desta máquina."""
    monkeypatch.setattr(gp, "controller_allows_uhid", lambda d: True)
    monkeypatch.setattr(gp, "start_gamepad_emulation", lambda *a, **k: True)
    daemon = _DaemonFalso()
    daemon._gamepad_device = None
    daemon._steam_input_excecao = True

    assert gp.upgrade_primary_vpad_to_uhid(daemon) is True


def test_entrar_no_jogo_marcado_esconde_o_fisico_em_vez_de_expor(
    _broker_falso: None, _sem_env: None, _jogo_marcado_na_frente: None
) -> None:
    """A MORDIDA: troque a chamada de `esconder_o_fisico_para_o_jogo` pelo par"""
    daemon = _DaemonFalso()

    assert gp.sync_steam_input_exception(daemon) is True

    assert daemon.grabs == [True], "soltar o grab é o jogo vendo o físico de novo"
    assert daemon.hides == ["/dev/hidraw0"], "o hidraw do físico tem de sumir"
    assert daemon.restores == 0, "`restore_all` é a direção contrária da decisão dela"


def test_com_dois_controles_esconde_os_dois_fisicos(
    _broker_falso: None, _sem_env: None, _jogo_marcado_na_frente: None
) -> None:
    """Um vpad vivo por controle ⇒ um hidraw escondido por controle."""
    daemon = _DaemonFalso(jogadores=1)

    gp.sync_steam_input_exception(daemon)

    assert daemon.hides == ["/dev/hidraw0", "/dev/hidraw1"]


def test_a_reconciliacao_online_reesconde_no_meio_da_partida(
    _broker_falso: None, _sem_env: None
) -> None:
    """A MORDIDA: devolva o `if steam_input_excecao_ativa(daemon): return` a"""
    daemon = _DaemonFalso()
    daemon._steam_input_excecao = True

    gp.rehide_physical_hidraw(daemon)

    assert daemon.hides == ["/dev/hidraw0"]


def test_sair_do_jogo_marcado_mantem_o_estado_canonico(
    _broker_falso: None, _sem_env: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Reversibilidade: a saída não pode deixar nada pendurado nem estragado."""
    daemon = _DaemonFalso()
    daemon._steam_input_excecao = True
    monkeypatch.setattr(le, "steam_input_exception_appid", lambda d, **k: None)

    assert gp.sync_steam_input_exception(daemon) is False

    assert gp.steam_input_excecao_ativa(daemon) is False
    assert daemon.grabs == [True] and daemon.hides == ["/dev/hidraw0"]
    assert daemon._gamepad_device is not None


@pytest.mark.parametrize(
    ("preparar", "motivo"),
    [
        (lambda d: setattr(d, "_nativo", True), "modo_nativo"),
        (
            lambda d: setattr(d.config, "gamepad_emulation_enabled", False),
            "emulacao_desligada",
        ),
        (lambda d: setattr(d, "_gamepad_device", None), "sem_vpad_vivo"),
    ],
)
def test_sem_vpad_para_devolver_o_controle_a_marca_nao_esconde_nada(
    preparar: Any,
    motivo: str,
    _broker_falso: None,
    _sem_env: None,
    _jogo_marcado_na_frente: None,
) -> None:
    """Esconder o físico sem um virtual vivo é ZERO controles na mão do usuário."""
    daemon = _DaemonFalso()
    preparar(daemon)

    gp.sync_steam_input_exception(daemon)

    assert daemon.hides == []
    assert daemon.grabs == []


def test_o_vpad_morto_nao_autoriza_esconder(
    _broker_falso: None, _sem_env: None, _jogo_marcado_na_frente: None
) -> None:
    """VIDA do vpad, não existência (lição 6/#17): um uhid derrubado por"""
    daemon = _DaemonFalso()
    daemon._gamepad_device._started = False

    gp.sync_steam_input_exception(daemon)

    assert daemon.hides == []


def test_o_jogo_marcado_recebe_a_mesma_env_de_qualquer_outro(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A MORDIDA: devolva o laço da allowlist a `materialize_launch_env`."""
    monkeypatch.setattr(le, "launch_env_dir", lambda ensure=False: tmp_path)
    monkeypatch.setattr(le, "_steam_profiles", lambda daemon: [])
    monkeypatch.setattr(le, "steam_input_appids", lambda path=None: {MMJ})
    monkeypatch.setattr(le, "_fisicos_na_mesa", lambda daemon: 1)

    le.materialize_launch_env(_DaemonFalso())

    assert not (tmp_path / f"steam_app_{MMJ}.env").exists(), (
        "o jogo marcado ganhou env própria de novo — a marca não é mais um "
        "desvio do lançamento"
    )
    assert _IGNORE in (tmp_path / "default.env").read_text(encoding="utf-8")


def test_a_env_velha_do_appid_marcado_e_apagada_sozinha(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Nada à mão (regra de 08/08): o arquivo sem dedup que as versões antigas"""
    monkeypatch.setattr(le, "launch_env_dir", lambda ensure=False: tmp_path)
    monkeypatch.setattr(le, "_steam_profiles", lambda daemon: [])
    monkeypatch.setattr(le, "steam_input_appids", lambda path=None: {MMJ})
    velho = tmp_path / f"steam_app_{MMJ}.env"
    velho.write_text(
        f"# estado: {le.ESTADO_ALLOWLIST_STEAM_INPUT}\n__GL_SHADER_DISK_CACHE=1\n",
        encoding="utf-8",
    )

    le.materialize_launch_env(_DaemonFalso())

    assert not velho.exists()


