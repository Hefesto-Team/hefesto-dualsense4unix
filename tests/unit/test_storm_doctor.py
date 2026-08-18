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


def test_storm_report_agrega_todos(tmp_path: Path) -> None:
    rows = sd.storm_report(
        tmp_path,
        quirks_text="",
        dropin_dir=tmp_path,
        rules_dir=tmp_path,
        snd_quirk_text="",
        snd_conf_path=tmp_path / "ausente.conf",
        cards_text="",
    )
    # SPRINT-GAME-RUMBLE-01: agora 6 checks (cura de raiz + áudio saudável novos).
    assert len(rows) == 6
    assert all(isinstance(t, str) and isinstance(m, str) for t, m in rows)


def test_check_snd_quirk_ativo_agendado_ausente(tmp_path: Path) -> None:
    # Ativo na sessão (sysfs com o quirk).
    tag, _ = sd.check_snd_quirk(
        quirk_flags_text="054c:0ce6:ignore_ctl_error|ctl_msg_delay_1m",
        conf_path=tmp_path / "x.conf",
    )
    assert tag == sd.OK
    # Só persistido (drop-in presente, sysfs vazio) = agendado.
    conf = tmp_path / "hefesto-dualsense-storm.conf"
    conf.write_text("options snd_usb_audio quirk_flags=054c:0ce6:ignore_ctl_error")
    tag, _ = sd.check_snd_quirk(quirk_flags_text="", conf_path=conf)
    assert tag == sd.INFO
    # Ausente dos dois = warn.
    tag, _ = sd.check_snd_quirk(quirk_flags_text="", conf_path=tmp_path / "nada.conf")
    assert tag == sd.WARN


def test_check_snd_audio_healthy(tmp_path: Path) -> None:
    tag, _ = sd.check_snd_audio_healthy(
        cards_text="1 [Controller]: USB-Audio - DualSense Wireless Controller"
    )
    assert tag == sd.OK
    tag, _ = sd.check_snd_audio_healthy(cards_text="0 [Generic]: HDA-Intel")
    assert tag == sd.INFO
