"""O-ARME-DO-LANCAMENTO-CONTA-O-PAD-QUE-ESTA-NASCENDO-01 (19/11/2026).

No diário de 12/11 a 19/11, seis `launch_arm_mascara_nao_convergiu` com
`perfil_dualsense_vs_vivo_sem_emulacao`: o arme lê o `_snapshot` logo depois do applier, e o
applier que troca a roupa para o pad do P1 e o pede ao fio do nascimento; até o fio entregar,
`gamepad_emulation_enabled` é falso e não há `_gamepad_device`. Agora o pad do P1 em voo conta
como emulação viva, com a máscara e o canal pedidos; o fio que falha o tira da conta.

MORDIDA: sem o ramo do `o_p1_que_nasce` no `_snapshot`, o primeiro caso reprova com
`perfil_xbox_vs_vivo_sem_emulacao`.
"""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

import hefesto_dualsense4unix.daemon.launch_env as le
from hefesto_dualsense4unix.daemon.subsystems import gamepad
from hefesto_dualsense4unix.daemon.subsystems.coop import CoopManager
from hefesto_dualsense4unix.daemon.subsystems.gamepad import OP1QueNasce
from hefesto_dualsense4unix.integrations import uhid_gamepad, virtual_pad

APPID = 9949958


class _Pedido:
    def __init__(self) -> None:
        self.pronto = False
        self.pad: Any = None
        self.ms: float | None = None
        self.descartado = False

    def descartar(self) -> None:
        self.descartado = True


class _Fio:
    def __init__(self) -> None:
        self.pedidos: list[_Pedido] = []

    def pedir(self, _flavor: Any, **_kw: Any) -> _Pedido:
        pedido = _Pedido()
        self.pedidos.append(pedido)
        return pedido


def _perfil(mascara: str) -> SimpleNamespace:
    return SimpleNamespace(
        name="Jogo",
        mode=SimpleNamespace(kind="gamepad", gamepad_flavor=mascara),
        match=SimpleNamespace(
            window_class=[f"steam_app_{APPID}"], window_title_regex=None, process_name=[],
        ),
    )


def _o_p1_que_nasce(mascara: str) -> OP1QueNasce:
    return OP1QueNasce(
        key=mascara, flavor=mascara, identity=None, mascara_do_p1=mascara, caminho=None,
        caminho_pedido=None, caminho_e_escolha=True, origin="gesto_de_perfil", carta=1,
        kwargs={"allow_uhid": True},
    )


def _mesa(fio: _Fio) -> SimpleNamespace:
    """O P1 de pé em `dualsense`; o applier troca a roupa e pede o pad novo ao fio."""
    daemon = SimpleNamespace(
        is_native_mode=lambda: False,
        config=SimpleNamespace(gamepad_emulation_enabled=True, gamepad_flavor="dualsense"),
        _gamepad_device=SimpleNamespace(backend="uhid", flavor="dualsense"),
        controller=SimpleNamespace(),
        store=SimpleNamespace(window_detect_current_class=None),
    )
    coop = CoopManager(daemon)  # type: ignore[arg-type]
    daemon._coop_manager = coop

    def _applier(mode: Any, *, profile: Any, origin: str) -> bool:
        daemon._gamepad_device = None
        daemon.config.gamepad_emulation_enabled = False
        coop.pedir_o_p1(_o_p1_que_nasce(str(mode.gamepad_flavor)))
        return True

    daemon.apply_profile_mode = _applier
    return daemon


@pytest.fixture
def mesa(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[SimpleNamespace, _Fio]:
    monkeypatch.setattr(le, "launch_env_dir", lambda ensure=False: tmp_path)
    monkeypatch.setattr(le, "steam_input_appids", lambda path=None: set())
    monkeypatch.setattr(le, "_permite_uhid", lambda daemon: True)
    monkeypatch.setattr(le, "_steam_profiles", lambda daemon: [(APPID, _perfil("xbox"))])
    monkeypatch.setattr(uhid_gamepad, "uhid_available", lambda: True)
    fio = _Fio()
    monkeypatch.setattr(virtual_pad, "o_fio_de_nascimento", lambda daemon: fio)
    (tmp_path / "last_run").write_text(f"appid={APPID}\nepoch=1000\npid=1\n", encoding="utf-8")
    return _mesa(fio), fio


def test_o_pad_em_voo_conta_como_emulacao_viva(mesa: tuple[SimpleNamespace, _Fio]) -> None:
    """D-1911-O-ARME-CONTA-O-PAD-QUE-NASCE: o pedido em voo não publica divergência."""
    daemon, fio = mesa
    resultado = le.arm_launch_profile(daemon, base_dir=Path(le.launch_env_dir()), now=1001.0)

    assert fio.pedidos and not fio.pedidos[0].pronto
    assert resultado is not None
    assert resultado["divergente"] is None, resultado
    assert resultado["convergiu"] is True
    assert le.divergencias_publicadas(daemon) == []


def test_o_fio_que_falha_devolve_a_divergencia(
    mesa: tuple[SimpleNamespace, _Fio], monkeypatch: pytest.MonkeyPatch
) -> None:
    """D-1911-O-ARME-CONTA-O-PAD-QUE-NASCE: o pad que não nasce volta a divergir."""
    daemon, fio = mesa
    le.arm_launch_profile(daemon, base_dir=Path(le.launch_env_dir()), now=1001.0)
    instalados: list[Any] = []
    monkeypatch.setattr(
        gamepad, "instalar_o_p1", lambda d, pad, contexto, ms: instalados.append(pad) or "falhou"
    )

    fio.pedidos[0].pronto = True
    daemon._coop_manager._andar_a_fila()
    le.materialize_launch_env(daemon)

    assert instalados == [None]
    assert daemon._coop_manager.o_p1_que_nasce() is None
    motivos = {item["motivo"] for item in le.divergencias_publicadas(daemon)}
    assert motivos == {"perfil_xbox_vs_vivo_sem_emulacao"}
