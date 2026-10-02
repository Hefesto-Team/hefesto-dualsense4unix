"""O `uninstall.sh --dry-run` diz o plano desta máquina e não escreve nada."""

from __future__ import annotations

import hashlib
import os
import re
import shutil
import stat
import subprocess
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
UNINSTALL = RAIZ / "uninstall.sh"
BASH = shutil.which("bash") or "/bin/bash"
PATH_DO_SISTEMA = "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"

SO_ESCREVEM = [
    *("sudo", "rm", "rmdir", "mv", "cp", "install", "mkdir", "ln", "chmod", "chown"),
    *("touch", "tee", "find", "pkill", "killall", "pip", "pip3", "apt", "apt-get"),
    *("dnf", "pacman", "kernelstub", "update-desktop-database", "gtk-update-icon-cache"),
    *("update-initramfs", "gpasswd", "groupdel", "usermod", "depmod", "modprobe"),
    *("rmmod", "gsettings", "dconf", "gnome-extensions", "sysctl", "bluetoothctl"),
]

VERBOS_QUE_SO_LEEM = {
    "systemctl": "is-active is-enabled is-failed cat show status list-units "
    "list-unit-files list-timers",
    "busctl": "get-property tree introspect status list",
    "flatpak": "list info",
    "dkms": "status",
    "udevadm": "info",
    "dpkg": "-l -s -L -S --list --status",
    "btmgmt": "info",
}


def _dublar(pasta: Path, diario: Path, sistema: str = PATH_DO_SISTEMA) -> None:
    """Os dublês do PATH; `sistema` é onde moram os binários a que as leituras"""
    pasta.mkdir()
    for nome in SO_ESCREVEM:
        (pasta / nome).write_text(
            f'#!/bin/sh\nprintf "%s\\n" "{nome} $*" >> "{diario}"\nexit 0\n',
            encoding="utf-8",
        )
    for nome, verbos in VERBOS_QUE_SO_LEEM.items():
        real = shutil.which(nome, path=sistema)
        if real is None:
            continue
        casos = "|".join(verbos.split())
        (pasta / nome).write_text(
            "#!/bin/sh\n"
            + (
                'v="$1"\n'
                if nome == "dpkg"
                else 'v=""\nfor a in "$@"; do case "$a" in -*) continue ;; esac; '
                'v="$a"; break; done\n'
            )
            + f'case "$v" in {casos}) PATH="{PATH_DO_SISTEMA}" exec "{real}" "$@" ;; esac\n'
            f'printf "%s\\n" "{nome} $*" >> "{diario}"\nexit 0\n',
            encoding="utf-8",
        )
    real_py = shutil.which("python3", path=PATH_DO_SISTEMA) or "/usr/bin/python3"
    (pasta / "python3").write_text(
        "#!/bin/sh\n"
        'if [ "$1" = "-" ] || { [ "$1" = "-I" ] && [ "$2" = "-c" ]; }; then\n'
        f'  PATH="{PATH_DO_SISTEMA}" exec "{real_py}" "$@"\nfi\n'
        f'printf "%s\\n" "python3 $*" >> "{diario}"\nexit 0\n',
        encoding="utf-8",
    )
    real_hci = shutil.which("hciconfig", path=sistema)
    if real_hci is not None:
        (pasta / "hciconfig").write_text(
            "#!/bin/sh\n"
            f'if [ "$#" -le 1 ]; then PATH="{PATH_DO_SISTEMA}" exec "{real_hci}" "$@"; fi\n'
            f'printf "%s\\n" "hciconfig $*" >> "{diario}"\nexit 0\n',
            encoding="utf-8",
        )
    (pasta / "bash").write_text(
        f'#!/bin/sh\nprintf "%s\\n" "bash $*" >> "{diario}"\nexit 0\n', encoding="utf-8"
    )
    for arq in pasta.iterdir():
        arq.chmod(arq.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def _semear(casa: Path, estado: Path) -> list[Path]:
    """Artefatos que o uninstall de verdade apagaria desta casa."""
    app = "hefesto-dualsense4unix"
    semeados = [
        casa / ".local/share/applications" / f"{app}.desktop",
        casa / ".local/bin" / f"{app}-gui",
        casa
        / ".config/wireplumber/wireplumber.conf.d"
        / "54-hefesto-dualsense-alto-falante-nunca-dorme.conf",
        casa / ".config/systemd/user" / f"{app}-storm-watch.service",
        casa / ".local/share" / app / "scripts/storm_watch.sh",
        casa / ".config" / app / "profiles/meu_perfil.json",
        casa / ".cache" / app / "bluez-obra/Makefile",
        estado / app / "radio-diario.jsonl",
    ]
    for arq in semeados:
        arq.parent.mkdir(parents=True, exist_ok=True)
        arq.write_text(f"semeado: {arq.name}\n", encoding="utf-8")
    (casa / ".local/bin" / app).symlink_to(casa / ".local/bin" / f"{app}-gui")
    return semeados


def _retrato(raiz: Path) -> dict[str, tuple[str, int, str]]:
    retrato: dict[str, tuple[str, int, str]] = {}
    for dirpath, dirnames, filenames in os.walk(raiz):
        for nome in sorted(dirnames + filenames):
            caminho = Path(dirpath) / nome
            st = caminho.lstat()
            if stat.S_ISLNK(st.st_mode):
                conteudo = "->" + os.readlink(caminho)
            elif stat.S_ISREG(st.st_mode):
                conteudo = hashlib.sha256(caminho.read_bytes()).hexdigest()
            else:
                conteudo = "dir"
            retrato[str(caminho.relative_to(raiz))] = (conteudo, st.st_mode, str(st.st_mtime_ns))
    return retrato


def _ensaiar(
    tmp_path: Path,
    *flags: str,
    sistema: str = PATH_DO_SISTEMA,
    env_extra: dict[str, str] | None = None,
) -> tuple[subprocess.CompletedProcess[str], str, bool]:
    lar = tmp_path / "lar"
    xdg = {
        "XDG_CONFIG_HOME": lar / "config",
        "XDG_DATA_HOME": lar / "data",
        "XDG_STATE_HOME": lar / "state",
        "XDG_CACHE_HOME": lar / "cache",
        "XDG_RUNTIME_DIR": lar / "run",
    }
    casa = lar / "casa"
    temporarios = tmp_path / "tmp"
    temporarios.mkdir()
    for pasta in (casa, *xdg.values()):
        pasta.mkdir(parents=True)
    xdg["XDG_RUNTIME_DIR"].chmod(0o700)
    _semear(casa, xdg["XDG_STATE_HOME"])
    diario = tmp_path / "dubles-chamados.log"
    _dublar(tmp_path / "dubles", diario, sistema)
    env = {
        "HOME": str(casa),
        "PATH": f"{tmp_path / 'dubles'}:{sistema}",
        "LANG": "C.UTF-8",
        "TMPDIR": str(temporarios),
        **{k: str(v) for k, v in xdg.items()},
        **(env_extra or {}),
    }
    assert not env["HOME"].startswith("/home/"), "o lar de mentira caiu numa casa de verdade"
    flatpak = tmp_path / "dubles" / "flatpak"
    if flatpak.is_file():
        subprocess.run(
            [str(flatpak), "--user", "list"], env=env, capture_output=True, timeout=60,
            check=False,
        )
    antes = _retrato(lar)
    r = subprocess.run(
        [BASH, str(UNINSTALL), "--dry-run", *flags],
        env=env,
        capture_output=True,
        text=True,
        timeout=240,
        check=False,
    )
    chamados = diario.read_text(encoding="utf-8") if diario.exists() else ""
    return r, chamados, _retrato(lar) == antes


@pytest.mark.parametrize(
    "flags",
    [(), ("--purge-config", "--restore-bluez"), ("--so-o-applet",)],
    ids=["sem-flag", "purge-e-restore", "so-o-applet"],
)
def test_o_ensaio_nao_chama_binario_que_escreve(tmp_path: Path, flags: tuple[str, ...]) -> None:
    r, chamados, _ = _ensaiar(tmp_path, *flags)
    assert r.returncode == 0, r.stdout[-3000:] + r.stderr[-3000:]
    assert chamados == "", (
        "o ensaio chamou binário que escreve — falta um dublê em uninstall.sh "
        "(«O ENSAIO»):\n" + chamados
    )


def test_sem_adaptador_no_sysfs_nem_no_barramento_o_ensaio_pergunta_ao_btmgmt(
    tmp_path: Path,
) -> None:
    """O `btmgmt info` é leitura, e o ensaio o faz de verdade."""
    sistema = tmp_path / "sistema"
    sistema.mkdir()
    (sistema / "btmgmt").write_text(
        '#!/bin/sh\n[ "$1" = "info" ] && printf "hci7:\\tPrimary controller\\n"\nexit 0\n',
        encoding="utf-8",
    )
    (sistema / "busctl").write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
    (sistema / "hciconfig").write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    for arq in sistema.iterdir():
        arq.chmod(0o755)
    (tmp_path / "sys-bluetooth").mkdir()
    r, chamados, _ = _ensaiar(
        tmp_path,
        sistema=f"{sistema}:{PATH_DO_SISTEMA}",
        env_extra={"HEFESTO_SYSFS_BLUETOOTH": str(tmp_path / "sys-bluetooth")},
    )
    assert r.returncode == 0, r.stdout[-3000:] + r.stderr[-3000:]
    assert chamados == "", "o ensaio chamou binário que escreve:\n" + chamados
    assert re.search(r"FARIA: .*hci7", r.stdout), (
        "o adaptador que só o `btmgmt info` conhece não chegou ao plano:\n" + r.stdout[-3000:]
    )


def test_o_ensaio_deixa_a_casa_byte_a_byte(tmp_path: Path) -> None:
    r, _, igual = _ensaiar(tmp_path, "--purge-config")
    assert r.returncode == 0, r.stderr[-3000:]
    assert igual, "o ensaio mudou a casa de mentira"


def test_o_ensaio_diz_o_que_faria_nesta_casa(tmp_path: Path) -> None:
    r, _, _ = _ensaiar(tmp_path)
    saida = r.stdout
    assert "[uninstall · ensaio] ENSAIO:" in saida, saida[:2000]
    assert "ENSAIO — nada foi removido" in saida, saida[-1500:]
    assert "desinstalado (wipe" not in saida, saida[-1500:]
    faria = [linha for linha in saida.splitlines() if "FARIA:" in linha]
    assert faria, "o ensaio não disse nenhuma linha FARIA:\n" + saida[-3000:]
    assert any(
        "hefesto-dualsense4unix.desktop" in linha and " rm " in f" {linha} " for linha in faria
    ), "o .desktop semeado não aparece no plano:\n" + "\n".join(faria)
    assert any("bluez-obra" in linha for linha in faria), (
        "a obra do backport semeada não aparece no plano:\n" + "\n".join(faria)
    )


def test_o_ensaio_esta_na_ajuda() -> None:
    r = subprocess.run(
        [BASH, str(UNINSTALL), "--help"],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
        env={"PATH": PATH_DO_SISTEMA, "HOME": "/nonexistent"},
    )
    assert r.returncode == 0 and "--dry-run" in r.stdout, r.stdout
