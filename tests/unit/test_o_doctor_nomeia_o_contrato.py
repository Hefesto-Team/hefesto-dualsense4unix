"""O doctor nomeia o CONTRATO que quebrou e o comando que o confere, e ausência não é defeito."""

from __future__ import annotations

from pathlib import Path

from hefesto_dualsense4unix.integrations import contratos_de_fora as cf


def _amb(
    tmp_path: Path, saidas: dict[str, tuple[int, str]], env: dict[str, str] | None = None
) -> cf.Ambiente:
    def rodar(argv):
        return saidas.get(argv[0], cf.Falta("sem a ferramenta"))

    return cf.Ambiente(rodar=rodar, home=tmp_path / "home", env=env or {}, raiz=tmp_path / "raiz")


def test_bluez_que_nao_responde_nomeia_contrato_e_comando(tmp_path):
    amb = _amb(tmp_path, {"busctl": (1, "")})
    linhas = cf.linhas_do_doctor(amb, [c for c in cf.CONTRATOS if c.id == "bluez-dbus"])
    ((tag, msg),) = linhas
    assert tag == "[WARN]"
    assert "bluez-dbus" in msg and "busctl --system tree org.bluez" in msg


def test_bluez_que_responde_e_ok(tmp_path):
    amb = _amb(tmp_path, {"busctl": (0, "└─/org/bluez\n")})
    ((tag, _),) = cf.linhas_do_doctor(amb, [c for c in cf.CONTRATOS if c.id == "bluez-dbus"])
    assert tag == "[ OK ]"


def test_pactl_sem_json_quebra_o_contrato_do_som(tmp_path):
    amb = _amb(tmp_path, {"pactl": (0, "Server String: x\n")})
    ((tag, msg),) = cf.linhas_do_doctor(
        amb, [c for c in cf.CONTRATOS if c.id == "pipewire-pactl-json"]
    )
    assert tag == "[WARN]" and "pipewire-pactl-json" in msg and "pactl --format=json info" in msg


def test_pactl_com_json_e_ok(tmp_path):
    amb = _amb(tmp_path, {"pactl": (0, '{"server_name": "PipeWire"}')})
    ((tag, _),) = cf.linhas_do_doctor(
        amb, [c for c in cf.CONTRATOS if c.id == "pipewire-pactl-json"]
    )
    assert tag == "[ OK ]"


def test_dono_ausente_e_info_e_nao_defeito(tmp_path):
    amb = _amb(tmp_path, {})
    tags = {
        c.id: cf.linhas_do_doctor(amb, [c])[0][0]
        for c in cf.CONTRATOS
        if c.id
        in (
            "bluez-dbus",
            "pipewire-wpctl",
            "steam-localconfig",
            "proton-de-terceiros",
            "cosmic-config",
        )
    }
    assert set(tags.values()) == {"[INFO]"}


def test_nos_do_kernel_faltando_nomeia_o_no(tmp_path):
    amb = _amb(tmp_path, {})
    ((tag, msg),) = cf.linhas_do_doctor(amb, [c for c in cf.CONTRATOS if c.id == "kernel-nos"])
    assert tag == "[WARN]" and "/dev/uinput" in msg and "ls -l" in msg


def test_nos_do_kernel_presentes_e_ok(tmp_path):
    raiz = tmp_path / "raiz"
    for rel in ("dev/uinput", "dev/uhid"):
        (raiz / rel).parent.mkdir(parents=True, exist_ok=True)
        (raiz / rel).write_text("")
    (raiz / "dev/input").mkdir(parents=True, exist_ok=True)
    (raiz / "sys/class/hidraw").mkdir(parents=True, exist_ok=True)
    ((tag, _),) = cf.linhas_do_doctor(
        _amb(tmp_path, {}), [c for c in cf.CONTRATOS if c.id == "kernel-nos"]
    )
    assert tag == "[ OK ]"


def test_localconfig_sem_a_raiz_quebra(tmp_path):
    conf = tmp_path / "home/.steam/steam/userdata/1/config/localconfig.vdf"
    conf.parent.mkdir(parents=True)
    conf.write_text('"Outra"\n{\n}\n', encoding="utf-8")
    ((tag, msg),) = cf.linhas_do_doctor(
        _amb(tmp_path, {}), [c for c in cf.CONTRATOS if c.id == "steam-localconfig"]
    )
    assert tag == "[WARN]" and "steam-localconfig" in msg
    conf.write_text('"UserLocalConfigStore"\n{\n}\n', encoding="utf-8")
    ((tag, _),) = cf.linhas_do_doctor(
        _amb(tmp_path, {}), [c for c in cf.CONTRATOS if c.id == "steam-localconfig"]
    )
    assert tag == "[ OK ]"


def test_proton_sem_executavel_quebra(tmp_path):
    pasta = tmp_path / "home/.steam/steam/compatibilitytools.d/GE-Proton11-8"
    pasta.mkdir(parents=True)
    (pasta / "compatibilitytool.vdf").write_text("x")
    ((tag, msg),) = cf.linhas_do_doctor(
        _amb(tmp_path, {}), [c for c in cf.CONTRATOS if c.id == "proton-de-terceiros"]
    )
    assert tag == "[WARN]" and "GE-Proton11-8" in msg
    (pasta / "proton").write_text("#!/bin/sh\n")
    ((tag, _),) = cf.linhas_do_doctor(
        _amb(tmp_path, {}), [c for c in cf.CONTRATOS if c.id == "proton-de-terceiros"]
    )
    assert tag == "[ OK ]"


def test_cosmic_so_pergunta_na_sessao_cosmic(tmp_path):
    ((tag, _),) = cf.linhas_do_doctor(
        _amb(tmp_path, {}, {"XDG_CURRENT_DESKTOP": "GNOME"}),
        [c for c in cf.CONTRATOS if c.id == "cosmic-config"],
    )
    assert tag == "[INFO]"
    ((tag, _),) = cf.linhas_do_doctor(
        _amb(tmp_path, {}, {"XDG_CURRENT_DESKTOP": "COSMIC"}),
        [c for c in cf.CONTRATOS if c.id == "cosmic-config"],
    )
    assert tag == "[WARN]"


def test_nenhuma_sonda_escreve_nem_compara_versao():
    fonte = Path(cf.__file__).read_text(encoding="utf-8")
    for proibido in (
        'busctl", "call',
        "bluetoothctl",
        "sudo",
        'pactl", "load',
        "--version",
        "write_text",
        'systemctl", "--user", "start',
    ):
        assert proibido not in fonte


def test_o_doctor_imprime_o_bloco(capsys, monkeypatch):
    from hefesto_dualsense4unix.cli import cmd_doctor

    monkeypatch.setattr(
        cf, "linhas_do_doctor", lambda *a, **k: [("[WARN]", "o contrato x-y quebrou")]
    )
    cmd_doctor._print_bloco_contratos()
    saida = capsys.readouterr().out
    assert "contratos de fora" in saida and "o contrato x-y quebrou" in saida


def test_ferramenta_que_nao_existe_e_falta_com_motivo_e_nao_silencio():
    saida = cf.rodar_de_verdade(["ferramenta-que-nao-existe-hefesto"])
    assert isinstance(saida, cf.Falta) and saida.motivo


def test_pactl_com_rc_diferente_de_zero_diz_o_rc(tmp_path):
    amb = _amb(tmp_path, {"pactl": (3, "")})
    ((tag, msg),) = cf.linhas_do_doctor(
        amb, [c for c in cf.CONTRATOS if c.id == "pipewire-pactl-json"]
    )
    assert tag == "[WARN]" and "rc=3" in msg


def test_ferramenta_que_existe_e_nao_responde_quebra_e_nao_e_ausencia(tmp_path):
    """O tempo esgotado do busctl é o BlueZ travado, não uma máquina sem BlueZ."""

    def rodar(argv):
        return cf.Falta("TimeoutExpired: 3 s", ausente=False)

    amb = cf.Ambiente(rodar=rodar, home=tmp_path, env={}, raiz=tmp_path)
    for ident in ("bluez-dbus", "pipewire-pactl-json", "pipewire-wpctl", "systemd-usuario"):
        ((tag, msg),) = cf.linhas_do_doctor(amb, [c for c in cf.CONTRATOS if c.id == ident])
        assert tag == "[WARN]" and ident in msg and "TimeoutExpired" in msg


def test_rodar_de_verdade_separa_ausente_de_quem_nao_responde(monkeypatch):
    monkeypatch.setattr(cf, "ESPERA_S", 0.2)
    sem = cf.rodar_de_verdade(["ferramenta-que-nao-existe-hefesto"])
    assert isinstance(sem, cf.Falta) and sem.ausente
    lenta = cf.rodar_de_verdade(["sleep", "10"])
    assert isinstance(lenta, cf.Falta) and not lenta.ausente


def _sony(tmp_path, saidas):
    return cf.linhas_do_doctor(
        _amb(tmp_path, saidas), [c for c in cf.CONTRATOS if c.id == "kernel-driver-sony"]
    )[0]


def test_driver_sony_sem_controle_desde_o_boot_e_ok_se_o_kernel_o_tem(tmp_path):
    """O módulo só carrega quando o primeiro controle chega: pasta ausente não é defeito."""
    ko = "/lib/modules/x/kernel/drivers/hid/hid-playstation.ko.zst\n"
    tag, _ = _sony(tmp_path, {"modinfo": (0, ko)})
    assert tag == "[ OK ]"
    tag, msg = _sony(tmp_path, {"modinfo": (1, "")})
    assert tag == "[WARN]" and "kernel-driver-sony" in msg and "modinfo" in msg
    tag, _ = _sony(tmp_path, {})
    assert tag == "[INFO]"
    (tmp_path / "raiz/sys/bus/hid/drivers/playstation").mkdir(parents=True)
    tag, _ = _sony(tmp_path, {"modinfo": (1, "")})
    assert tag == "[ OK ]"
