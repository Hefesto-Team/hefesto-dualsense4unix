"""Flavors do gamepad virtual (FEAT-DSX-GAMEPAD-FLAVOR-01).

Prova a "máscara": `for_flavor` configura VID/PID/nome certos, `normalize_flavor`
resolve sinônimos e cai no default, e a persistência roundtrip (liga+flavor).
"""
from __future__ import annotations

from pathlib import Path

import pytest

from hefesto_dualsense4unix.integrations import uinput_gamepad as ug
from hefesto_dualsense4unix.utils import session


class TestNormalizeFlavor:
    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("dualsense", "dualsense"),
            ("DualSense", "dualsense"),
            ("ps", "dualsense"),
            ("playstation", "dualsense"),
            ("ds", "dualsense"),
            ("xbox", "xbox"),
            ("xbox360", "xbox"),
            ("x360", "xbox"),
            ("xinput", "xbox"),
            # SPRINT-GAME-RUMBLE-01: default é xbox (a máscara que vibra em jogo).
            (None, "xbox"),
            ("lixo-desconhecido", "xbox"),
            ("  XBOX  ", "xbox"),
        ],
    )
    def test_normalize(self, raw: str | None, expected: str) -> None:
        assert ug.normalize_flavor(raw) == expected


class TestForFlavor:
    def test_dualsense_usa_vidpid_sony(self) -> None:
        gp = ug.UinputGamepad.for_flavor("dualsense")
        assert gp.vendor == ug.DUALSENSE_VENDOR == 0x054C
        assert gp.product == ug.DUALSENSE_PRODUCT == 0x0CE6
        assert gp.flavor == "dualsense"
        assert "DualSense" in gp.name

    def test_xbox_usa_vidpid_microsoft(self) -> None:
        gp = ug.UinputGamepad.for_flavor("xbox")
        assert gp.vendor == ug.XBOX360_VENDOR == 0x045E
        assert gp.product == ug.XBOX360_PRODUCT == 0x028E
        assert gp.flavor == "xbox"

    def test_default_e_xbox(self) -> None:
        # SPRINT-GAME-RUMBLE-01: o default é xbox — a máscara DualSense faz o jogo
        # ignorar o vpad (rumble morto) e duplicar o controle. Decisão de produto.
        assert ug.DEFAULT_FLAVOR == "xbox"
        gp = ug.UinputGamepad.for_flavor()
        assert gp.flavor == "xbox"

    def test_flavor_desconhecido_cai_no_default(self) -> None:
        gp = ug.UinputGamepad.for_flavor("nintendo64")
        assert gp.flavor == "xbox"

    def test_bustype_usb_para_match_sdl(self) -> None:
        # BUS_USB ajuda o GUID da SDL a casar no gamecontrollerdb.
        assert ug.BUS_USB == 0x03
        assert ug.UinputGamepad.for_flavor("dualsense").bustype == 0x03


class TestGamepadPersist:
    @pytest.fixture()
    def tmp_config(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
        monkeypatch.setattr(session, "config_dir", lambda ensure=False: tmp_path)
        return tmp_path

    def test_roundtrip_liga_com_flavor(self, tmp_config: Path) -> None:
        assert session.load_gamepad_emulation() == (False, None)
        session.save_gamepad_emulation(True, "xbox")
        assert (tmp_config / "gamepad_emulation.flag").exists()
        assert session.load_gamepad_emulation() == (True, "xbox")
        session.save_gamepad_emulation(False)
        assert not (tmp_config / "gamepad_emulation.flag").exists()
        assert session.load_gamepad_emulation() == (False, None)

    def test_default_flavor_quando_ligado_sem_texto(self, tmp_config: Path) -> None:
        # Flag presente mas vazia → ligado, flavor None (caller normaliza).
        (tmp_config / "gamepad_emulation.flag").write_text("\n", encoding="utf-8")
        enabled, flavor = session.load_gamepad_emulation()
        assert enabled is True
        assert flavor is None

    def test_save_best_effort_nao_propaga(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def _boom(*_a: object, **_k: object) -> Path:
            raise OSError("indisponível")

        monkeypatch.setattr(session, "config_dir", _boom)
        session.save_gamepad_emulation(True, "dualsense")  # não deve lançar
        assert session.load_gamepad_emulation() == (False, None)
