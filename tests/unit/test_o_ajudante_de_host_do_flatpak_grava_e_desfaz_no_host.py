"""O ajudante de host do Flatpak roda no host: grava pelo arquivo que o Flatpak deixou e desfaz.

D-2211-O-AJUDANTE-DE-HOST-DO-FLATPAK-RODA-NO-HOST: dentro do sandbox o ajudante só
imprime o comando do host; no host ele acha os arquivos pela pasta `../share` do próprio
script, grava, e `--remover` devolve a raiz como estava. O manifesto não ganha permissão.

Instrumento: o script de verdade, copiado para uma árvore `files/bin` montada pelo
próprio manifesto (cada `install` dele vira um arquivo), com os caminhos do sistema
trocados por uma raiz de mentira e um PATH sem `pkexec` nem `sudo`.
"""

from __future__ import annotations

import os
import re
import shlex
import shutil
import stat
import subprocess
from pathlib import Path

import pytest
import yaml

RAIZ = Path(__file__).resolve().parents[2]
SCRIPT = RAIZ / "scripts" / "install-host-udev.sh"
MANIFESTO = RAIZ / "flatpak" / "io.github.hefesto_team.hefesto_dualsense4unix.yml"
PAGINA = RAIZ / "docs" / "usage" / "flatpak.md"
INSTALACAO = RAIZ / "docs" / "usage" / "instalacao.md"
ID_DO_APP = "io.github.hefesto_team.hefesto_dualsense4unix"
COMANDO_DO_HOST = (
    f'sudo bash "$(flatpak info --show-location {ID_DO_APP})/files/bin/install-host-udev.sh"'
)
SHARE = "/app/share/hefesto-dualsense4unix/"
FERRAMENTAS = (
    "bash",
    "sh",
    "install",
    "mkdir",
    "rm",
    "rmdir",
    "sed",
    "awk",
    "grep",
    "cat",
    "mktemp",
    "dirname",
    "basename",
    "printf",
    "tee",
    "cp",
    "ls",
    "find",
    "sort",
    "head",
    "tr",
    "readlink",
    "env",
    "uname",
    "cut",
    "chmod",
    "touch",
    "mv",
    "wc",
    "date",
    "tail",
)
PREFIXOS_DO_SISTEMA = (
    "/etc/",
    "/var/lib/hefesto",
    "/usr/local/lib/hefesto",
    "/sys/module",
    "/tmp/hefesto",
)


def _comandos_do_manifesto() -> list[list[str]]:
    manifesto = yaml.safe_load(MANIFESTO.read_text(encoding="utf-8"))
    achados = []
    for modulo in manifesto["modules"]:
        for comando in modulo.get("build-commands", []):
            partes = shlex.split(comando)
            if partes[:1] == ["install"]:
                achados.append(partes)
    return achados


def _arquivos_do_manifesto() -> dict[str, Path]:
    """Destino no sandbox -> fonte no repositório, de cada `install` do manifesto."""
    mapa: dict[str, Path] = {}
    for partes in _comandos_do_manifesto():
        args = [p for p in partes[1:] if not p.startswith("-") or p == "-t"]
        if "-t" in args:
            i = args.index("-t")
            pasta = args[i + 1]
            for fonte in args[:i] + args[i + 2 :]:
                mapa[f"{pasta.rstrip('/')}/{Path(fonte).name}"] = RAIZ / fonte
        else:
            *fontes, destino = args
            for fonte in fontes:
                mapa[destino] = RAIZ / fonte
    return mapa


def _montar_o_flatpak(tmp: Path, com_dkms: bool) -> Path:
    """`files/` do Flatpak como o host o vê: /app/bin e /app/share viram files/bin e files/share."""
    files = tmp / "location" / "files"
    for destino, fonte in _arquivos_do_manifesto().items():
        if not destino.startswith(("/app/bin/", SHARE)) or not fonte.is_file():
            continue
        alvo = files / destino.removeprefix("/app/")
        alvo.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(fonte, alvo)
    broker = files / "share" / "hefesto-dualsense4unix" / "broker" / "hidraw_broker.py"
    broker.write_text('#!/bin/sh\necho "broker $*" >> "$HEFESTO_REGISTRO"\n', encoding="utf-8")
    broker.chmod(0o755)
    if com_dkms:
        for conf in sorted((RAIZ / "assets" / "dkms").glob("*/dkms.conf")):
            alvo = files / "share" / "hefesto-dualsense4unix" / "dkms" / conf.parent.name
            alvo.mkdir(parents=True)
            shutil.copy2(conf, alvo / "dkms.conf")
    return files


def _script_com_raiz_de_mentira(files: Path, raiz: Path, texto: str | None = None) -> Path:
    texto = texto if texto is not None else SCRIPT.read_text(encoding="utf-8")
    for prefixo in PREFIXOS_DO_SISTEMA:
        texto = texto.replace(prefixo, f"{raiz}{prefixo}")
    destino = files / "bin" / "install-host-udev.sh"
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(texto, encoding="utf-8")
    destino.chmod(0o755)
    return destino


def _falso(pasta: Path, nome: str, corpo: str) -> None:
    arquivo = pasta / nome
    arquivo.write_text(f"#!/bin/bash\n{corpo}\n", encoding="utf-8")
    arquivo.chmod(arquivo.stat().st_mode | stat.S_IXUSR)


def _bin_sem_elevacao(tmp: Path, dkms_estado: Path) -> Path:
    """PATH com as ferramentas de arquivo de verdade e o resto de mentira; sem pkexec nem sudo."""
    pasta = tmp / "bin"
    pasta.mkdir()
    for nome in FERRAMENTAS:
        achado = shutil.which(nome)
        if achado:
            (pasta / nome).symlink_to(achado)
    _falso(
        pasta,
        "id",
        f'if [ "${{1:-}}" = "-u" ]; then echo 0; else exec {shutil.which("id")} "$@"; fi',
    )
    for nome in ("groupadd", "usermod", "modprobe", "udevadm", "systemctl", "depmod"):
        _falso(pasta, nome, f'echo "{nome} $*" >> "$HEFESTO_REGISTRO"')
    _falso(
        pasta,
        "dkms",
        'echo "dkms $*" >> "$HEFESTO_REGISTRO"\n'
        f'marca="{dkms_estado}/${{2//\\//_}}"\n'
        'case "$1" in\n'
        '  status) [ -e "$marca" ] && echo "$2, 6.8, x86_64: installed"; true ;;\n'
        '  remove) rm -f "$marca" ;;\n'
        "esac",
    )
    return pasta


class _Cena:
    def __init__(self, tmp: Path, com_dkms: bool = False, texto: str | None = None) -> None:
        self.tmp = tmp
        self.raiz = tmp / "raiz"
        for pasta in ("etc/udev/rules.d", "etc/modprobe.d", "usr/src", "tmp"):
            (self.raiz / pasta).mkdir(parents=True)
        self.registro = tmp / "registro.txt"
        self.registro.write_text("", encoding="utf-8")
        self.dkms_estado = tmp / "dkms-estado"
        self.dkms_estado.mkdir()
        self.files = _montar_o_flatpak(tmp, com_dkms)
        self.script = _script_com_raiz_de_mentira(self.files, self.raiz, texto)
        self.bin = _bin_sem_elevacao(tmp, self.dkms_estado)
        (tmp / "t").mkdir()
        self.env = {
            "PATH": str(self.bin),
            "HEFESTO_REGISTRO": str(self.registro),
            "HEFESTO_DKMS_SRC_ROOT": str(self.raiz / "usr" / "src"),
            "HEFESTO_RAIZ_PROC": str(tmp / "proc"),
            "HEFESTO_MARCA_SANDBOX": str(tmp / "nao-existe"),
            "SUDO_UID": str(os.getuid()),
            "TMPDIR": str(tmp / "t"),
            "LC_ALL": "C.UTF-8",
            "HOME": str(tmp / "home"),
        }

    def rodar(
        self, *args: str, env: dict[str, str] | None = None
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [str(self.bin / "bash"), str(self.script), *args],
            capture_output=True,
            text=True,
            env=env or self.env,
            timeout=120,
            check=False,
            cwd=str(self.tmp),
        )

    def arquivos(self) -> set[str]:
        return {str(p.relative_to(self.raiz)) for p in self.raiz.rglob("*") if p.is_file()}

    def chamadas(self) -> list[str]:
        return self.registro.read_text(encoding="utf-8").splitlines()


def _regras_do_script() -> list[str]:
    texto = SCRIPT.read_text(encoding="utf-8")
    bloco = re.search(r"^RULES=\((.*?)^\)", texto, re.M | re.S)
    assert bloco
    return re.findall(r'"([^"]+\.rules)"', bloco.group(1))


def test_o_manifesto_monta_o_que_o_ajudante_procura_ao_lado_dele() -> None:
    """O script vai em /app/bin e os arquivos em /app/share: o `../share` do script os acha."""
    destinos = set(_arquivos_do_manifesto())
    assert "/app/bin/install-host-udev.sh" in destinos
    assert f"{SHARE}udev-rules/73-hefesto-ps5-controller.rules" in destinos
    assert f"{SHARE}scripts/disparo_do_udev.sh" in destinos
    assert f"{SHARE}broker/hidraw_broker.py" in destinos


def test_o_manifesto_nao_ganha_permissao_para_falar_com_o_host() -> None:
    """A cura não abre `flatpak-spawn --host`: o comando do host roda fora do sandbox."""
    texto = MANIFESTO.read_text(encoding="utf-8")
    manifesto = yaml.safe_load(texto)
    permissoes = [str(p) for p in manifesto["finish-args"]]
    assert not any("org.freedesktop.Flatpak" in p for p in permissoes), permissoes
    assert "pkexec" not in texto, "o manifesto ainda promete o pkexec"


def test_dentro_do_sandbox_so_imprime_o_comando_do_host(tmp_path: Path) -> None:
    cena = _Cena(tmp_path)
    marca = tmp_path / "flatpak-info"
    marca.write_text("[Application]\n", encoding="utf-8")
    dentro = dict(cena.env, HEFESTO_MARCA_SANDBOX=str(marca))
    for args, final in (((), ""), (("--remover",), " --remover")):
        r = cena.rodar(*args, env=dentro)
        assert r.returncode == 1, r.stderr
        saida = r.stdout + r.stderr
        comando = (
            f'sudo bash "$(flatpak info --show-location {ID_DO_APP})'
            f'/files/bin/install-host-udev.sh"{final}'
        )
        assert comando in saida, saida
        assert "/app/" not in saida, saida
        assert "pkexec" not in saida
    assert cena.arquivos() == set()
    assert cena.chamadas() == []


def test_o_comando_impresso_chega_aos_arquivos_e_grava_na_raiz(tmp_path: Path) -> None:
    """De ponta a ponta: o comando impresso, com `flatpak` e `sudo` de mentira, grava na raiz."""
    cena = _Cena(tmp_path)
    marca = tmp_path / "flatpak-info"
    marca.write_text("[Application]\n", encoding="utf-8")
    impresso = cena.rodar(env=dict(cena.env, HEFESTO_MARCA_SANDBOX=str(marca))).stdout
    comando = next(
        linha.strip() for linha in impresso.splitlines() if linha.strip().startswith("sudo bash")
    )
    _falso(cena.bin, "flatpak", f'echo "{cena.files.parent}"')
    _falso(cena.bin, "sudo", 'exec "$@"')
    r = subprocess.run(
        [str(cena.bin / "bash"), "-c", comando],
        capture_output=True,
        text=True,
        env=cena.env,
        timeout=120,
        check=False,
        cwd=str(tmp_path),
    )
    assert r.returncode == 0, r.stdout + r.stderr
    regras = cena.raiz / "etc" / "udev" / "rules.d"
    assert (regras / "73-hefesto-ps5-controller.rules").is_file()
    assert (regras / "71-uinput.rules").is_file()
    assert "Regras instaladas com sucesso." in r.stdout


def test_instalar_grava_tudo_pelos_arquivos_do_flatpak_e_remover_devolve_a_raiz(
    tmp_path: Path,
) -> None:
    """D-2211-O-AJUDANTE-DE-HOST-DO-FLATPAK-RODA-NO-HOST."""
    cena = _Cena(tmp_path)
    estranho = cena.raiz / "etc" / "udev" / "rules.d" / "99-de-outro.rules"
    estranho.write_text("# de outro dono\n", encoding="utf-8")
    ida = cena.rodar()
    assert ida.returncode == 0, ida.stdout + ida.stderr
    gravados = cena.arquivos()
    for regra in _regras_do_script():
        assert f"etc/udev/rules.d/{regra}" in gravados, regra
    for esperado in (
        "etc/modules-load.d/hefesto-dualsense4unix.conf",
        "etc/modprobe.d/hefesto-dualsense-storm.conf",
        "etc/modprobe.d/hefesto-btusb-no-autosuspend.conf",
        "etc/modprobe.d/hefesto-hid-nintendo.conf",
        "etc/modprobe.d/hefesto-hid-playstation.conf",
        "etc/systemd/system/hefesto-hidraw-broker.service",
        "etc/systemd/system/hefesto-hidraw-broker.socket",
        "etc/systemd/system/hefesto-bt-bonds-snapshot.service",
        "usr/local/lib/hefesto-dualsense4unix/hefesto-hidraw-broker",
        "usr/local/lib/hefesto-dualsense4unix/bt_nosniff_now.sh",
        "usr/local/lib/hefesto-dualsense4unix/bt_bonds_snapshot.sh",
        "usr/local/lib/hefesto-dualsense4unix/bt_active_mode.sh",
        "usr/local/lib/hefesto-dualsense4unix/bt_ponte_privilegiada.sh",
    ):
        assert esperado in gravados, esperado
    assert (cena.raiz / "var/lib/hefesto-dualsense4unix/bt-bonds").is_dir()

    volta = cena.rodar("--remover")
    assert volta.returncode == 0, volta.stdout + volta.stderr
    restos = cena.arquivos() - {"etc/udev/rules.d/99-de-outro.rules"}
    assert restos == set(), sorted(restos)
    assert estranho.is_file(), "a volta apagou regra que não era do Hefesto"
    assert not (cena.raiz / "usr/local/lib/hefesto-dualsense4unix").exists()
    assert not (cena.raiz / "var/lib/hefesto-dualsense4unix").exists()
    chamadas = "\n".join(cena.chamadas())
    assert "systemctl disable --now hefesto-hidraw-broker.socket" in chamadas
    assert "broker --restore-all-and-exit" in chamadas


def test_remover_guarda_as_copias_dos_pareamentos(tmp_path: Path) -> None:
    cena = _Cena(tmp_path)
    assert cena.rodar().returncode == 0
    copia = cena.raiz / "var/lib/hefesto-dualsense4unix/bt-bonds/aa-bb-cc.tar"
    copia.write_text("pareamento\n", encoding="utf-8")
    assert cena.rodar("--remover").returncode == 0
    assert copia.is_file(), "a volta apagou os pareamentos que o timer copiou"


@pytest.mark.parametrize(
    "item",
    [
        "bt_ponte_privilegiada.sh",
        "hefesto-bt-bonds-snapshot.service",
        "hefesto-hid-playstation.conf",
    ],
)
def test_a_regua_morde_a_volta_que_esquece_um_arquivo(tmp_path: Path, item: str) -> None:
    """Arranca da lista da volta (só na cópia) um item que a ida grava: sobra arquivo."""
    texto = SCRIPT.read_text(encoding="utf-8")
    linha = f'        "{item}"\n'
    assert linha in texto, item
    cena = _Cena(tmp_path, texto=texto.replace(linha, "", 1))
    assert cena.rodar().returncode == 0
    assert cena.rodar("--remover").returncode == 0
    assert cena.arquivos() != set(), "a régua não percebeu a volta incompleta"


def test_remover_tira_os_modulos_dkms_que_a_pasta_do_dono_declara(tmp_path: Path) -> None:
    cena = _Cena(tmp_path, com_dkms=True)
    pacotes = {}
    for conf in sorted((RAIZ / "assets" / "dkms").glob("*/dkms.conf")):
        texto = conf.read_text(encoding="utf-8")
        nome = re.search(r'^PACKAGE_NAME="(.*)"$', texto, re.M)
        versao = re.search(r'^PACKAGE_VERSION="(.*)"$', texto, re.M)
        assert nome and versao
        pacotes[nome.group(1)] = versao.group(1)
        (cena.dkms_estado / f"{nome.group(1)}_{versao.group(1)}").write_text("", encoding="utf-8")
    assert len(pacotes) == 5, pacotes
    r = cena.rodar("--remover")
    assert r.returncode == 0, r.stdout + r.stderr
    chamadas = cena.chamadas()
    for pacote, ver in pacotes.items():
        assert f"dkms remove {pacote}/{ver} --all" in chamadas, (pacote, chamadas)
    assert list(cena.dkms_estado.iterdir()) == []


def test_opcao_desconhecida_recusa_sem_gravar(tmp_path: Path) -> None:
    cena = _Cena(tmp_path)
    r = cena.rodar("--apagar-tudo")
    assert r.returncode == 2
    assert cena.arquivos() == set()


def _secao(pagina: str, titulo: str) -> str:
    achado = re.search(rf"^#+ {re.escape(titulo)}\n(.*?)(?=^#+ |\Z)", pagina, re.M | re.S)
    assert achado, f"a página perdeu a seção {titulo!r}"
    return achado.group(1)


def test_as_paginas_dao_o_comando_do_host_e_listam_o_que_se_grava() -> None:
    pagina = PAGINA.read_text(encoding="utf-8")
    instalacao = INSTALACAO.read_text(encoding="utf-8")
    for texto in (pagina, instalacao):
        assert "flatpak run --command=install-host-udev.sh" not in texto
        assert "pkexec" not in texto
        assert COMANDO_DO_HOST in texto
    desinstalar = _secao(pagina, "Desinstalar")
    assert 'install-host-udev.sh" --remover' in desinstalar
    gravado = _secao(pagina, "O que o ajudante grava no sistema")
    for regra in _regras_do_script():
        assert regra in gravado, f"a página não lista {regra}"
    for item in (
        "hefesto-dualsense4unix.conf",
        "hefesto-dualsense-storm.conf",
        "hefesto-btusb-no-autosuspend.conf",
        "hefesto-hid-nintendo.conf",
        "hefesto-hid-playstation.conf",
        "hefesto-hidraw-broker.socket",
        "hefesto-bt-bonds-snapshot.service",
        "/usr/local/lib/hefesto-dualsense4unix/",
        "/var/lib/hefesto-dualsense4unix/bt-bonds/",
        "hefesto-hid-nintendo",
        "hefesto-usb-f-hid",
    ):
        assert item in gravado, f"a página não diz {item}"
    assert "/app/share" not in _secao(pagina, "As regras udev, uma vez só")
