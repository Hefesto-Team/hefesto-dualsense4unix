"""FEAT-DSX-UNIFY-01 — diagnóstico storm read-only (integrations/storm_doctor)."""
from __future__ import annotations

from pathlib import Path

from hefesto_dualsense4unix.integrations import storm_doctor as sd


def test_quirk_presente_e_ausente() -> None:
    tag, _ = sd.check_quirk("054c:0ce6:gn,054c:0df2:gn")
    assert tag == sd.OK
    tag2, _ = sd.check_quirk("")
    assert tag2 == sd.WARN


def test_steam_input_ligado_desligado_ausente(tmp_path: Path) -> None:
    # Sem nenhum vdf → INFO.
    tag, _ = sd.check_steam_input(tmp_path)
    assert tag == sd.INFO

    # vdf com PSSupport="2" → WARN (ligado).
    vdf = tmp_path / ".steam/steam/userdata/123/config/localconfig.vdf"
    vdf.parent.mkdir(parents=True)
    vdf.write_text('\t\t\t\t"SteamController_PSSupport"\t\t"2"\n', encoding="utf-8")
    tag2, msg2 = sd.check_steam_input(tmp_path)
    assert tag2 == sd.WARN
    assert "LIGADO" in msg2

    # vdf com "0" → desligado (OK).
    vdf.write_text('\t\t\t\t"SteamController_PSSupport"\t\t"0"\n', encoding="utf-8")
    tag3, _ = sd.check_steam_input(tmp_path)
    assert tag3 == sd.OK


def test_wireplumber_dropin(tmp_path: Path) -> None:
    tag, _ = sd.check_wireplumber(tmp_path)
    assert tag == sd.INFO  # sem drop-in
    (tmp_path / "51-hefesto-dualsense-no-default-source.conf").write_text("x")
    tag2, _ = sd.check_wireplumber(tmp_path)
    assert tag2 == sd.OK


def test_authorized_rule(tmp_path: Path) -> None:
    tag, msg = sd.check_authorized_rule(tmp_path)
    assert tag == sd.INFO and "inativa" in msg
    (tmp_path / "75-ps5-controller-disable-usb-audio.rules").write_text("x")
    tag2, msg2 = sd.check_authorized_rule(tmp_path)
    assert tag2 == sd.INFO and "ATIVA" in msg2


def test_find_localconfig_dedup(tmp_path: Path) -> None:
    vdf = tmp_path / ".local/share/Steam/userdata/42/config/localconfig.vdf"
    vdf.parent.mkdir(parents=True)
    vdf.write_text("x")
    found = sd.find_localconfig_vdfs(tmp_path)
    assert vdf.resolve() in found


def test_storm_report_agrega_quatro(tmp_path: Path) -> None:
    rows = sd.storm_report(
        tmp_path, quirks_text="", dropin_dir=tmp_path, rules_dir=tmp_path
    )
    assert len(rows) == 4
    assert all(isinstance(t, str) and isinstance(m, str) for t, m in rows)
