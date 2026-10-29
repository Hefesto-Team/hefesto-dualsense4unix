"""O pad do P1 renasce com o mesmo MAC e o mesmo serial depois que o daemon reinicia.

O-PAD-VIRTUAL-GUARDA-O-SERIAL-ENTRE-VIDAS-DO-DAEMON-01: em 28/10, depois do reinício das
01:26, o pad nasceu com `identity=None` e `mac=02:fe:00:00:00:01` (o `player_mac(1)`), e o
jogo viu um controle de serial novo. No começo do daemon o `primary_uniq` ainda é vazio.

A MORDIDA: faça `gamepad.a_identidade_do_p1_que_nasce` devolver só o `primary_identity`, e a
segunda vida volta a `02:fe:00:00:00:01`.
"""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from hefesto_dualsense4unix.daemon.lifecycle import Daemon, DaemonConfig
from hefesto_dualsense4unix.daemon.subsystems import gamepad as gp
from hefesto_dualsense4unix.integrations import pad_usb
from hefesto_dualsense4unix.integrations.uhid_gamepad import player_mac, vpad_mac
from hefesto_dualsense4unix.testing.fake_controller import FakeController
from hefesto_dualsense4unix.utils import session as session_mod

DONO = "aa:bb:cc:00:00:01"


class _Pad:
    def __init__(self, flavor: str, identity: str | None) -> None:
        self.flavor = flavor
        self.identity = identity
        self.mac = vpad_mac(identity, 1)
        self.serial = pad_usb.serial_do_pad(self.mac, 1)
        self.backend = "uhid"
        self.caminho = None

    def stop(self) -> None:
        return None


@pytest.fixture(autouse=True)
def _hermetico(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> list[_Pad]:
    from hefesto_dualsense4unix.utils import xdg_paths

    alvo = tmp_path / "config"

    def _config_dir(ensure: bool = False) -> Path:
        if ensure:
            alvo.mkdir(parents=True, exist_ok=True)
        return alvo

    monkeypatch.setattr(xdg_paths, "config_dir", _config_dir)
    monkeypatch.setattr(session_mod, "config_dir", _config_dir)
    monkeypatch.setenv(gp.DONO_DO_P1_ENV, str(tmp_path / "run" / "dono-do-p1"))
    nascidos: list[_Pad] = []

    def _fazer(flavor: str, **kw: Any) -> _Pad:
        nascidos.append(_Pad(flavor, kw.get("identity")))
        return nascidos[-1]

    monkeypatch.setattr(
        "hefesto_dualsense4unix.integrations.virtual_pad.make_virtual_pad", _fazer)
    monkeypatch.setattr(
        "hefesto_dualsense4unix.daemon.launch_env.materialize_launch_env", lambda _d: None)
    monkeypatch.setattr(gp, "_set_controller_grab", lambda *_a: None)
    return nascidos


def _vida(transporte: str, primary_uniq: str) -> Any:
    d = Daemon(
        controller=FakeController(transport=transporte),
        config=DaemonConfig(ipc_enabled=False, udp_enabled=False),
    )
    d.controller.primary_uniq = primary_uniq
    d._coop_manager = SimpleNamespace(
        sync=lambda **_k: None, disable=lambda: None, player_count=lambda: 1,
        algum_boneco_ficou_para_tras=lambda: False,
    )
    d._game_signal = SimpleNamespace(authority="daemon")
    return d


@pytest.mark.parametrize("transporte", ["usb", "bt"])
@pytest.mark.parametrize("mascara", ["dualsense", "xbox"])
def test_a_segunda_vida_sem_primary_uniq_nasce_com_o_mesmo_serial(
    _hermetico: list[_Pad], transporte: str, mascara: str
) -> None:
    gp.start_gamepad_emulation(_vida(transporte, DONO), mascara, origin="profile")
    gp.start_gamepad_emulation(_vida(transporte, ""), mascara, origin="profile")
    primeira, segunda = _hermetico
    assert primeira.mac != player_mac(1), "premissa: a primeira vida tinha dono"
    assert segunda.mac == primeira.mac
    assert segunda.serial == primeira.serial


def test_o_ancorar_lembra_o_dono_que_chega_depois(_hermetico: list[_Pad]) -> None:
    d = _vida("bt", "")
    gp.start_gamepad_emulation(d, "dualsense", origin="profile")
    assert _hermetico[0].mac == player_mac(1), "premissa: sem dono nenhum, o do número"
    d.controller.primary_uniq = DONO
    gp.ancorar_o_p1_no_aparelho(d)
    gp.start_gamepad_emulation(_vida("bt", ""), "dualsense", origin="profile")
    assert _hermetico[-1].mac == vpad_mac(DONO, 1)


@pytest.mark.parametrize("lixo", ["", "nao-e-mac", "aa:bb:cc", "zz:zz:zz:zz:zz:zz"])
def test_a_memoria_torta_vale_como_nenhuma(tmp_path: Path, lixo: str) -> None:
    arquivo = Path(gp._arquivo_do_dono_do_p1())
    arquivo.parent.mkdir(parents=True, exist_ok=True)
    arquivo.write_text(lixo, encoding="ascii")
    assert gp.o_dono_lembrado_do_p1() is None
