"""JOGO-01 — um controle físico produz exatamente UM dispositivo de jogo.

Medido ao vivo em 25/07 com o Mullet Mad Jack (`steam_app_2111190`, o único
appid da allowlist do Steam Input desta máquina) e UM DualSense no cabo:

    /dev/input/js0  ->  Hefesto Virtual DualSense P1   (o nosso gamepad virtual)
    /dev/input/js2  ->  DualSense Wireless Controller  (o controle físico dela)
    /dev/input/js4  ->  Microsoft X-Box 360 pad 0      (Steam Input)
    /dev/input/js5  ->  Microsoft X-Box 360 pad 1      (Steam Input)

O jogo dava jogador 1 ao primeiro que enumerou e jogador 2 ao seguinte, e o
relato dela descreve isso por fora: "ele muda a cor e vai pro player 2 e não
funciona". A causa não era a allowlist estar errada — era ela estar pela
metade: o ramo do `launch_env` omitia `SDL_GAMECONTROLLER_IGNORE_DEVICES` e
`PROTON_DISABLE_HIDRAW` (rótulo literal no código: "allowlist Steam Input (sem
dedup)") e o gamepad virtual CONTINUAVA DE PÉ. Cada metade estava certa
isoladamente; juntas produziam o duplicado.

A allowlist muda QUAL dispositivo o jogo vê, nunca QUANTOS. Desde 09/08/2026
(ESCONDER-EM-VEZ-DE-SAIR-01, decisão dela) o dispositivo escolhido é o virtual:
esconde-se o FÍSICO e o Hefesto fica, porque o jogador 2 é um gamepad virtual e
derrubar os virtuais o derrubava junto. A suspensão do vpad, que era a cura
antiga, saiu em 02/10/2026 (O-CODIGO-SEM-CHAMADOR-LIGA-OU-SAI-01): a borda da
marca não a chamava mais, e o flag que ela armava nunca podia ser verdade.

A borda de hoje está em `test_esconder_em_vez_de_sair_01.py`. Aqui ficam o
revive dentro do jogo marcado e a env da allowlist (`TestEnvDaAllowlist`).
"""

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
    """O mínimo que `start/stop_gamepad_emulation` toca num vpad."""

    def __init__(self, flavor: str = "dualsense", backend: str = "uhid") -> None:
        self.flavor = flavor
        self.backend = backend
        self._started = True
        self.parado = False

    def stop(self) -> None:
        self.parado = True
        self._started = False


class _CoopFalso:
    def __init__(self, jogadores: int = 0) -> None:
        self._players: dict[str, Any] = {
            f"AA:BB:CC:00:00:0{i}": SimpleNamespace(
                vpad=_VpadFalso(), player_index=i + 2
            )
            for i in range(jogadores)
        }
        self.desligado = 0
        self.syncs: list[bool] = []

    def disable(self) -> None:
        self.desligado += 1
        self._players.clear()

    def sync(self, *, force: bool = False, origem: str | None = None) -> None:
        self.syncs.append(force)


class _StoreFalso:
    def __init__(self) -> None:
        self.contadores: list[str] = []
        self.window_detect_current_class: str | None = None

    def bump(self, chave: str) -> None:
        self.contadores.append(chave)


class _DaemonFalso:
    """Daemon dublado que observa grab, broker, co-op e vpad."""

    def __init__(self, *, jogadores: int = 0, nativo: bool = False) -> None:
        self.config = SimpleNamespace(
            gamepad_emulation_enabled=True,
            gamepad_flavor="dualsense",
            rumble_active=None,
        )
        self._gamepad_device: Any = _VpadFalso()
        self._coop_manager = _CoopFalso(jogadores)
        self._motion_reader: Any = None
        self._mouse_device: Any = None
        self._tasks: list[Any] = []
        self._nativo = nativo
        self.parando = False
        self.grabs: list[bool] = []
        self.restores = 0
        self.hides: list[str] = []
        self.store = _StoreFalso()
        pai = self

        class _Evdev:
            grab_state = None

            def set_grab(self, grab: bool) -> bool:
                pai.grabs.append(grab)
                return True

        self.controller = SimpleNamespace(
            _evdev=_Evdev(),
            hidraw_path=lambda *a: "/dev/hidraw0",
            set_rumble=lambda **k: None,
            primary_uniq="AA:BB:CC:00:00:FF",
        )

    def is_native_mode(self) -> bool:
        return self._nativo

    def _is_stopping(self) -> bool:
        return self.parando


@pytest.fixture()
def _broker_falso(monkeypatch: pytest.MonkeyPatch) -> None:
    """Cliente do broker dublado — nenhum socket real no teste."""
    import hefesto_dualsense4unix.integrations.hidraw_broker_client as bc

    def _client_for(daemon: Any) -> Any:
        class _C:
            def hide(self, node: str) -> None:
                daemon.hides.append(node)

            def restore_all(self) -> None:
                daemon.restores += 1

        return _C()

    monkeypatch.setattr(bc, "broker_client_for", _client_for)
    monkeypatch.setattr(bc, "broker_call_nonblocking", lambda daemon, fn: fn())


@pytest.fixture()
def _sem_disco(monkeypatch: pytest.MonkeyPatch) -> list[Any]:
    """Isola o ciclo do vpad de disco, kernel e threads."""
    import hefesto_dualsense4unix.integrations.virtual_pad as vp
    import hefesto_dualsense4unix.utils.session as session

    salvos: list[Any] = []
    monkeypatch.setattr(gp, "_materialize_launch_env", lambda daemon: None)
    monkeypatch.setattr(gp, "start_motion_reader", lambda daemon, device: None)
    monkeypatch.setattr(
        vp, "make_virtual_pad", lambda key, **kwargs: _VpadFalso(flavor=key)
    )
    monkeypatch.setattr(
        session,
        "save_gamepad_emulation",
        lambda *a, **k: salvos.append((a, k)),
    )
    return salvos


async def _encerrar_vigia(daemon: Any) -> Any:
    """Cancela a task-vigia (se houver) e devolve a task para inspeção."""
    vigia = getattr(daemon, "_steam_input_vigia", None)
    if vigia is not None:
        vigia.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await vigia
    return vigia


class TestQuemTentaLevantarOVpadDeVolta:
    """NOTA DATADA — 09/08/2026: os dois gates que protegiam a suspensão caíram."""


    def test_revive_pos_falha_total_vale_dentro_do_jogo_marcado(
        self, _broker_falso: None, _sem_disco: list[Any], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """VPAD-09 dispara em borda de CONEXÃO — a mais frequente desta máquina"""
        monkeypatch.setattr(gp, "controller_allows_uhid", lambda d: True)
        daemon = _DaemonFalso()
        daemon._gamepad_device = None
        daemon._steam_input_excecao = True

        assert gp.upgrade_primary_vpad_to_uhid(daemon) is True
        assert daemon._gamepad_device is not None


class TestEnvDaAllowlist:
    def test_o_appid_marcado_deixou_de_ter_env_propria(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """NOTA DATADA — 09/08/2026: o rótulo virou obituário."""
        monkeypatch.setattr(le, "launch_env_dir", lambda ensure=False: tmp_path)
        monkeypatch.setattr(le, "_steam_profiles", lambda daemon: [])
        monkeypatch.setattr(le, "steam_input_appids", lambda path=None: {MMJ})
        daemon = _DaemonFalso()

        le.materialize_launch_env(daemon)

        assert not (tmp_path / f"steam_app_{MMJ}.env").exists()
        texto = (tmp_path / "default.env").read_text(encoding="utf-8")
        assert _IGNORE in texto
        assert le.ESTADO_ALLOWLIST_STEAM_INPUT not in texto, (
            "o rótulo do desvio antigo voltou a ser escrito em algum arquivo"
        )
