"""O `uninstall.sh --dry-run` diz o plano desta máquina e não escreve nada.

INSTALL-E-UNINSTALL-DO-RADIO-01 (23/09/2026): a sprint pede o ensaio dos DOIS
instaladores num lar de mentira, e o uninstall não tinha ensaio — `--dry-run`
abortava como argumento desconhecido, e rodá-lo de verdade mata os processos
do Hefesto por `pkill` e tira o /etc inteiro. O ensaio nasceu dublando, dentro
do próprio script, cada comando que muda a máquina.

O alcance do ensaio é uma LISTA de dublês, e uma lista esquece. Esta régua é a
segunda linha, independente da primeira: roda o ensaio com um lar de mentira
(HOME e os cinco XDG_* desviados, sem barramento de sessão) e com um PATH cujo
começo tem um dublê para TODO binário que muda máquina. Cada dublê anota no
diário e sai sem fazer nada; os que também LEEM (`systemctl is-active`,
`dkms status`, `busctl get-property`…) repassam a leitura ao binário real e só
anotam a escrita. Um comando novo que o ensaio esqueceu de dublar chega aqui e
reprova — e a casa de mentira tem de sair byte a byte igual.

A MORDIDA, medida: tirar o `rm` do laço de dublês do ensaio faz o `rm` real
ser chamado (o dublê do PATH o anota) e o teste reprova; tirar o dublê do
`sudo`, o mesmo, pelo `sudo` do PATH.
"""

from __future__ import annotations

import hashlib
import os
import shutil
import stat
import subprocess
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
UNINSTALL = RAIZ / "uninstall.sh"
BASH = shutil.which("bash") or "/bin/bash"
PATH_DO_SISTEMA = "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"

# Só escrevem: o dublê anota e sai 0.
SO_ESCREVEM = [
    *("sudo", "rm", "rmdir", "mv", "cp", "install", "mkdir", "ln", "chmod", "chown"),
    *("touch", "tee", "find", "pkill", "killall", "pip", "pip3", "apt", "apt-get"),
    *("dnf", "pacman", "kernelstub", "update-desktop-database", "gtk-update-icon-cache"),
    *("update-initramfs", "gpasswd", "groupdel", "usermod", "depmod", "modprobe"),
    *("rmmod", "gsettings", "dconf", "gnome-extensions", "sysctl", "bluetoothctl", "btmgmt"),
]

# Leem e escrevem: o dublê repassa a leitura (o verbo na lista) ao real.
VERBOS_QUE_SO_LEEM = {
    "systemctl": "is-active is-enabled is-failed cat show status list-units "
    "list-unit-files list-timers",
    "busctl": "get-property tree introspect status list",
    "flatpak": "list info",
    "dkms": "status",
    "udevadm": "info",
    "dpkg": "-l -s -L -S --list --status",
}


def _dublar(pasta: Path, diario: Path) -> None:
    pasta.mkdir()
    for nome in SO_ESCREVEM:
        (pasta / nome).write_text(
            f'#!/bin/sh\nprintf "%s\\n" "{nome} $*" >> "{diario}"\nexit 0\n',
            encoding="utf-8",
        )
    for nome, verbos in VERBOS_QUE_SO_LEEM.items():
        real = shutil.which(nome, path=PATH_DO_SISTEMA)
        if real is None:
            continue  # ausente na máquina: um esquecido dá «command not found», não escreve
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
    # `python3 -` e `python3 -I -c` são as leituras do uninstall (o plano do
    # usbcore.quirks e os nomes do maquina.json); rodar um .py é escrita.
    (pasta / "python3").write_text(
        "#!/bin/sh\n"
        'if [ "$1" = "-" ] || { [ "$1" = "-I" ] && [ "$2" = "-c" ]; }; then\n'
        f'  PATH="{PATH_DO_SISTEMA}" exec "{real_py}" "$@"\nfi\n'
        f'printf "%s\\n" "python3 $*" >> "{diario}"\nexit 0\n',
        encoding="utf-8",
    )
    real_hci = shutil.which("hciconfig", path=PATH_DO_SISTEMA)
    if real_hci is not None:
        (pasta / "hciconfig").write_text(
            "#!/bin/sh\n"
            f'if [ "$#" -le 1 ]; then PATH="{PATH_DO_SISTEMA}" exec "{real_hci}" "$@"; fi\n'
            f'printf "%s\\n" "hciconfig $*" >> "{diario}"\nexit 0\n',
            encoding="utf-8",
        )
    # `bash` do PATH: o uninstall só o chama para rodar scripts que escrevem.
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


def _ensaiar(tmp_path: Path, *flags: str) -> tuple[subprocess.CompletedProcess[str], str, bool]:
    lar = tmp_path / "lar"
    xdg = {
        "XDG_CONFIG_HOME": lar / "config",
        "XDG_DATA_HOME": lar / "data",
        "XDG_STATE_HOME": lar / "state",
        "XDG_CACHE_HOME": lar / "cache",
        "XDG_RUNTIME_DIR": lar / "run",
    }
    casa = lar / "casa"
    # O `dkms status` de verdade larga temporários quando a leitura é cortada
    # por um `grep -q`; eles caem no berço do teste, não no /tmp da máquina.
    temporarios = tmp_path / "tmp"
    temporarios.mkdir()
    for pasta in (casa, *xdg.values()):
        pasta.mkdir(parents=True)
    xdg["XDG_RUNTIME_DIR"].chmod(0o700)
    _semear(casa, xdg["XDG_STATE_HOME"])
    diario = tmp_path / "dubles-chamados.log"
    _dublar(tmp_path / "dubles", diario)
    env = {
        "HOME": str(casa),
        "PATH": f"{tmp_path / 'dubles'}:{PATH_DO_SISTEMA}",
        "LANG": "C.UTF-8",
        "TMPDIR": str(temporarios),
        **{k: str(v) for k, v in xdg.items()},
    }
    assert not env["HOME"].startswith("/home/"), "o lar de mentira caiu numa casa de verdade"
    # O `flatpak list` de verdade cria o repositório do usuário na primeira
    # leitura; numa casa de verdade ele já existe. Ele nasce ANTES do retrato,
    # para a régua medir o uninstall, não o flatpak.
    flatpak = shutil.which("flatpak", path=PATH_DO_SISTEMA)
    if flatpak is not None:
        subprocess.run(
            [flatpak, "--user", "list"], env=env, capture_output=True, timeout=60, check=False
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
    ids=["padrao", "purge-e-restore", "so-o-applet"],
)
def test_o_ensaio_nao_chama_binario_que_escreve(tmp_path: Path, flags: tuple[str, ...]) -> None:
    r, chamados, _ = _ensaiar(tmp_path, *flags)
    assert r.returncode == 0, r.stdout[-3000:] + r.stderr[-3000:]
    assert chamados == "", (
        "o ensaio chamou binário que escreve — falta um dublê em uninstall.sh "
        "(«O ENSAIO»):\n" + chamados
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
