"""O Secure Boot se lê sem o `mokutil`, e sem a chave o DKMS não entra — B4.

``O-PRODUTO-EM-QUALQUER-MAQUINA-01`` (28/09/2026), a L5 do estudo
``2026-09-27-o-basico-e-os-jogos/03-qualquer-maquina.md``: o aviso de Secure
Boot só falava se o ``mokutil`` existisse (``dkms_lib.sh`` e o reconhecimento
do ``install.sh``), então nesta casa ele nunca rodou. E ele só AVISAVA: com
Secure Boot e sem a chave do DKMS inscrita, o kernel recusa o ``.ko`` de
``updates/dkms`` no boot e NÃO volta ao de fábrica — o DualSense fica sem
driver. As frases falavam de «um controle Nintendo».

A cura: a efivars diz o Secure Boot (o último byte da ``SecureBoot-*``); a
chave (a que o ``dkms`` usa para assinar, resolvida como ele resolve) se
confere pelo ``mokutil`` quando ele existe e, sem ele, pelos bytes da chave na
lista que o shim expõe; e sem a chave o
``dkms_install_patched_module`` NÃO instala — o de fábrica fica, e o aviso diz
o passo da MOK com o DualSense no nome.

Tudo de mentira: a efivars, a chave, a lista do shim, o ``sudo`` e o ``dkms``.
O ``PATH`` tem só as ferramentas que a lib usa, e nenhum ``mokutil``.

A MORDIDA, feita em 28/09/2026: voltar o ``dkms_warn_secureboot_once`` e o
portão ao ``command -v mokutil`` de antes (sem a efivars) faz
``test_sem_a_chave_o_dkms_nao_instala_nada`` e
``test_o_reconhecimento_avisa_sem_mokutil`` reprovarem. Devolvido, md5 conferido.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

from tests.unit.dkms_de_mentira import ko_do_dkms

BASH = shutil.which("bash") or "/bin/bash"
RAIZ = Path(__file__).resolve().parents[2]
LIB = RAIZ / "scripts" / "dkms_lib.sh"
INSTALL = (RAIZ / "install.sh").read_text(encoding="utf-8")
SECURE_BOOT = "SecureBoot-8be4df61-93ca-11d2-aa0d-00e098032b8c"
CHAVE = b"0\x82\x03\x1bCHAVE-DE-MENTIRA-DO-DKMS\x00\x01\x02"
MOK_NEW = "MokNew-605dab50-e046-4300-abb6-3dd810dd8b23"


def _bin(tmp_path: Path) -> Path:
    """Um PATH só com o que a lib usa — e sem `mokutil`, de propósito."""
    pasta = tmp_path / "bin"
    pasta.mkdir()
    for nome in ("od", "awk", "python3", "cat", "sed", "diff", "cp", "rm", "install"):
        real = shutil.which(nome)
        if real is None:  # pragma: no cover
            pytest.skip(f"sem {nome} nesta máquina")
        os.symlink(real, pasta / nome)
    return pasta


def _efivars(tmp_path: Path, ligado: bool | None) -> Path:
    pasta = tmp_path / "efivars"
    pasta.mkdir()
    if ligado is not None:
        (pasta / SECURE_BOOT).write_bytes(b"\x06\x00\x00\x00" + (b"\x01" if ligado else b"\x00"))
    return pasta


def _mok(tmp_path: Path, *, gerada: bool, inscrita: bool) -> dict[str, str]:
    pub = tmp_path / "mok.pub"
    if gerada:
        pub.write_bytes(CHAVE)
    lista = tmp_path / "MokListRT"
    lista.write_bytes(b"\xa1\x59\xc0\xa5" + (CHAVE if inscrita else b"outra-chave") + b"\x00")
    return {"HEFESTO_DKMS_MOK_PUB": str(pub), "HEFESTO_MOK_LISTAS": str(lista)}


def _lib(
    tmp_path: Path, script: str, env_extra: dict[str, str]
) -> subprocess.CompletedProcess[str]:
    env = {"PATH": str(_bin(tmp_path)), "HOME": str(tmp_path), "LC_ALL": "C.UTF-8",
           "HEFESTO_SYS_MODULE": str(tmp_path / "sem-sys-module")}
    env.update(env_extra)
    return subprocess.run(
        [BASH, "-c", f"set -euo pipefail\nsource '{LIB}'\n{script}\n"],
        capture_output=True, text=True, timeout=60, check=False, env=env,
    )


@pytest.mark.parametrize(("ligado", "esperado"), [(True, "sim"), (False, "não"), (None, "não")])
def test_o_secure_boot_se_le_pela_efivars(
    tmp_path: Path, ligado: bool | None, esperado: str
) -> None:
    r = _lib(
        tmp_path,
        "if dkms_secure_boot_ligado; then echo sim; else echo não; fi",
        {"HEFESTO_EFIVARS_ROOT": str(_efivars(tmp_path, ligado))},
    )
    assert r.stdout.strip() == esperado, (r.stdout, r.stderr)


@pytest.mark.parametrize(
    ("gerada", "inscrita", "esperado"),
    [(True, True, "sim"), (True, False, "não"), (False, False, "não")],
)
def test_a_chave_se_confere_sem_mokutil(
    tmp_path: Path, gerada: bool, inscrita: bool, esperado: str
) -> None:
    r = _lib(
        tmp_path,
        "if dkms_chave_mok_inscrita; then echo sim; else echo não; fi",
        _mok(tmp_path, gerada=gerada, inscrita=inscrita),
    )
    assert r.stdout.strip() == esperado, (r.stdout, r.stderr)


@pytest.mark.parametrize(
    ("gerada", "inscrita", "esperado"),
    [(True, True, "inscrita"), (True, False, "fora"), (False, False, "nao-sei")],
)
def test_a_chave_tem_tres_respostas(
    tmp_path: Path, gerada: bool, inscrita: bool, esperado: str
) -> None:
    """D-2111-A-CHAVE-QUE-NAO-SE-LE-NAO-TIRA-O-MODULO: só a lista lida sem a chave diz «fora»."""
    r = _lib(tmp_path, "dkms_estado_da_chave", _mok(tmp_path, gerada=gerada, inscrita=inscrita))
    assert r.stdout == esperado, (r.stdout, r.stderr)


def test_sem_lista_que_se_leia_a_chave_e_nao_sei(tmp_path: Path) -> None:
    env = _mok(tmp_path, gerada=True, inscrita=False)
    env["HEFESTO_MOK_LISTAS"] = str(tmp_path / "nao-existe")
    r = _lib(tmp_path, "dkms_estado_da_chave", env)
    assert r.stdout == "nao-sei", (r.stdout, r.stderr)
    (tmp_path / "passo").mkdir()
    r = _lib(tmp_path / "passo", "dkms_passo_para_ler_a_chave", env)
    assert "instale o mokutil" in r.stdout, (r.stdout, r.stderr)


def test_com_a_lista_lida_o_passo_e_inscrever_a_chave(tmp_path: Path) -> None:
    r = _lib(tmp_path, "dkms_passo_para_ler_a_chave", _mok(tmp_path, gerada=True, inscrita=False))
    assert "mokutil --import" in r.stdout and "instale o mokutil" not in r.stdout, r.stdout


_POP = 'NAME="Pop!_OS"\nID=pop\nID_LIKE="ubuntu debian"\n'
_UBUNTU = "NAME=Ubuntu\nID=ubuntu\nID_LIKE=debian\n"
_MINT = 'ID=linuxmint\nID_LIKE="ubuntu debian"\n'
_DEBIAN = "ID=debian\n"
_FEDORA = "ID=fedora\n"
_ARCH = "ID=arch\n"
_SO_COMENTADO = "# mok_signing_key=/var/lib/dkms/mok.key\n# mok_certificate=/var/lib/dkms/mok.pub\n"
_CHAVE_PROPRIA = 'mok_signing_key="/root/chave.priv"\nmok_certificate="/root/chave.der"\n'
_SO_A_CHAVE = "mok_signing_key=/root/chave.priv\n"


@pytest.mark.parametrize(
    ("os_release", "framework", "esperado"),
    [
        (_POP, _SO_COMENTADO, "/var/lib/shim-signed/mok/MOK.der"),
        (_UBUNTU, _SO_COMENTADO, "/var/lib/shim-signed/mok/MOK.der"),
        (_MINT, "", "/var/lib/shim-signed/mok/MOK.der"),
        (_DEBIAN, _SO_COMENTADO, "/var/lib/dkms/mok.pub"),
        (_FEDORA, "", "/var/lib/dkms/mok.pub"),
        (_ARCH, "", "/var/lib/dkms/mok.pub"),
        (_POP, _CHAVE_PROPRIA, "/root/chave.der"),
        (_FEDORA, _CHAVE_PROPRIA, "/root/chave.der"),
        (_UBUNTU, _SO_A_CHAVE, "/var/lib/dkms/mok.pub"),
    ],
    ids=["pop", "ubuntu", "mint", "debian", "fedora", "arch", "pop-propria",
         "fedora-propria", "ubuntu-so-a-chave"],
)
def test_a_chave_conferida_e_a_que_o_dkms_assina(
    tmp_path: Path, os_release: str, framework: str, esperado: str
) -> None:
    (tmp_path / "os-release").write_text(os_release, encoding="utf-8")
    conf = tmp_path / "framework.conf"
    conf.write_text(framework, encoding="utf-8")
    r = _lib(
        tmp_path,
        "_dkms_mok_pub",
        {
            "HEFESTO_OS_RELEASE": str(tmp_path / "os-release"),
            "HEFESTO_DKMS_FRAMEWORK_CONFS": f"{conf} {tmp_path / 'conf.d-vazio'}/*.conf",
        },
    )
    assert r.stdout == esperado, (r.stdout, r.stderr)


def test_o_passo_da_mok_gera_a_chave_com_quem_o_dkms_usa(tmp_path: Path) -> None:
    """No Pop!_OS o `dkms generate_mok` não existe (dkms 3.0): quem gera é o"""
    (tmp_path / "os-release").write_text(_POP, encoding="utf-8")
    conf = tmp_path / "framework.conf"
    conf.write_text(_SO_COMENTADO, encoding="utf-8")
    env = {
        "HEFESTO_OS_RELEASE": str(tmp_path / "os-release"),
        "HEFESTO_DKMS_FRAMEWORK_CONFS": str(conf),
    }
    (tmp_path / "pop").mkdir()
    r = _lib(tmp_path / "pop", "dkms_passo_da_mok", env)
    assert "update-secureboot-policy --new-key" in r.stdout, r.stdout
    assert "generate_mok" not in r.stdout, r.stdout
    assert "mokutil --import /var/lib/shim-signed/mok/MOK.der" in r.stdout, r.stdout
    (tmp_path / "os-release").write_text(_FEDORA, encoding="utf-8")
    (tmp_path / "fedora").mkdir()
    r = _lib(tmp_path / "fedora", "dkms_passo_da_mok", env)
    assert "sudo dkms generate_mok" in r.stdout, r.stdout
    assert "mokutil --import /var/lib/dkms/mok.pub" in r.stdout, r.stdout


def _instalar(tmp_path: Path, *, ligado: bool, inscrita: bool) -> tuple[str, str]:
    """Roda `dkms_install_patched_module` com `sudo` e `dkms` que só anotam."""
    bin_ = _bin(tmp_path)
    registro = tmp_path / "chamadas.log"
    for nome in ("sudo", "dkms", "modinfo", "chown", "chmod"):
        (bin_ / nome).write_text(
            f'#!/bin/sh\necho "{nome} $*" >> "{registro}"\n'
            + ('exec "$@"\n' if nome == "sudo" else "exit 0\n"),
            encoding="utf-8",
        )
        (bin_ / nome).chmod(0o755)
    modulos = tmp_path / "lib-modules"
    (modulos / "7.1.5-76070105-generic" / "build").mkdir(parents=True)
    fonte = tmp_path / "hid-playstation"
    fonte.mkdir()
    (fonte / "dkms.conf").write_text('PACKAGE_VERSION="1.0.0"\n', encoding="utf-8")
    env = {
        "PATH": str(bin_),
        "HOME": str(tmp_path),
        "LC_ALL": "C.UTF-8",
        "HEFESTO_EFIVARS_ROOT": str(_efivars(tmp_path, ligado)),
        "HEFESTO_DKMS_MODULES_ROOT": str(modulos),
        "HEFESTO_DKMS_SRC_ROOT": str(tmp_path / "usr-src"),
        "HEFESTO_SYS_MODULE": str(tmp_path / "sem-sys-module"),
        **_mok(tmp_path, gerada=True, inscrita=inscrita),
    }
    r = subprocess.run(
        [
            BASH, "-c",
            f"source '{LIB}'\nuname() {{ echo 7.1.5-76070105-generic; }}\n"
            f"dkms_install_patched_module hefesto-hid-playstation 1.0.0 '{fonte}' hid-playstation",
        ],
        capture_output=True, text=True, timeout=60, check=False, env=env,
    )
    assert r.returncode == 0, r.stderr
    chamadas = registro.read_text(encoding="utf-8") if registro.exists() else ""
    return r.stdout + r.stderr, chamadas


def test_sem_a_chave_o_dkms_nao_instala_nada(tmp_path: Path) -> None:
    saida, chamadas = _instalar(tmp_path, ligado=True, inscrita=False)
    assert "dkms add" not in chamadas and "dkms build" not in chamadas, chamadas
    assert "dkms install" not in chamadas, chamadas
    assert "DualSense" in saida and "mokutil --import" in saida, saida
    assert "Enroll MOK" in saida, saida


def test_com_a_chave_o_dkms_segue(tmp_path: Path) -> None:
    _saida, chamadas = _instalar(tmp_path, ligado=True, inscrita=True)
    assert "dkms add" in chamadas, chamadas


def test_sem_secure_boot_o_dkms_segue(tmp_path: Path) -> None:
    _saida, chamadas = _instalar(tmp_path, ligado=False, inscrita=False)
    assert "dkms add" in chamadas, chamadas


def _com_o_modulo_carregado(tmp_path: Path, bin_: Path, arvore: Path) -> str:
    """O hid-playstation da casa carregado agora: ``modinfo`` de mentira e o ``/sys/module``."""
    ko = ko_do_dkms(tmp_path, arvore, "hefesto-hid-playstation", "hid-playstation.ko.zst")
    sysmod = tmp_path / "sysmod"
    (sysmod / "hid_playstation").mkdir(parents=True)
    (sysmod / "hid_playstation" / "srcversion").write_text("SRC123\n", encoding="ascii")
    modinfo = bin_ / "modinfo"
    modinfo.write_text(
        f'#!/bin/sh\ncase "$*" in *filename*) echo "{ko}";; *srcversion*) echo SRC123;; esac\n',
        encoding="utf-8",
    )
    modinfo.chmod(0o755)
    cmp_ = shutil.which("cmp")
    if cmp_ and not (bin_ / "cmp").exists():
        os.symlink(cmp_, bin_ / "cmp")
    return str(sysmod)


def _reconhecimento() -> str:
    inicio = INSTALL.index("_reconhecimento() {\n")
    fim = INSTALL.index("\n}\n", inicio) + 3
    return INSTALL[inicio:fim]


def _rodar_reconhecimento(
    tmp_path: Path, *, ligado: bool, pedida: bool = False, carregado: bool = False
) -> str:
    script = "\n".join(
        (
            "set -euo pipefail",
            f"ROOT_DIR='{RAIZ}'",
            "NO_DKMS=0",
            'warn() { printf "WARN: %s\\n" "$*"; }',
            "_familia_pacotes() { echo apt; }",
            _reconhecimento(),
            "_reconhecimento",
        )
    )
    env = {
        "PATH": str(_bin(tmp_path)),
        "HOME": str(tmp_path),
        "LC_ALL": "C.UTF-8",
        "HEFESTO_EFIVARS_ROOT": str(_efivars(tmp_path, ligado)),
        "HEFESTO_SYS_MODULE": str(tmp_path / "sem-sys-module"),
        **_mok(tmp_path, gerada=True, inscrita=False),
    }
    if pedida:
        (Path(env["HEFESTO_EFIVARS_ROOT"]) / MOK_NEW).write_bytes(b"\x07\x00\x00\x00" + CHAVE)
    if carregado:
        arvore = tmp_path / "arvore-do-dkms"
        env["HEFESTO_SYS_MODULE"] = _com_o_modulo_carregado(
            tmp_path, Path(env["PATH"]), arvore)
        env["HEFESTO_DKMS_TREE"] = str(arvore)
    r = subprocess.run(
        [BASH, "-c", script], capture_output=True, text=True, timeout=60, check=False, env=env
    )
    assert r.returncode == 0, r.stderr
    return r.stdout


def test_o_reconhecimento_avisa_sem_mokutil(tmp_path: Path) -> None:
    saida = _rodar_reconhecimento(tmp_path, ligado=True)
    assert "WARN: Secure Boot ligado" in saida, saida
    assert "DualSense" in saida and "microfone pelo rádio" in saida, saida
    assert "Nintendo pode sumir" not in saida


def test_o_reconhecimento_com_a_inscricao_pedida_diz_o_reinicio(tmp_path: Path) -> None:
    """D-2111-A-INSCRICAO-PEDIDA-ESPERA-O-REINICIO: o install diz o mesmo estado que a lib."""
    saida = _rodar_reconhecimento(tmp_path, ligado=True, pedida=True)
    assert "espera o reinício" in saida and "Enroll MOK" in saida, saida
    assert "mokutil --import" not in saida and "não consegui ler" not in saida, saida


def test_o_reconhecimento_diz_que_o_modulo_carregado_segue_como_esta(tmp_path: Path) -> None:
    """D-2111-O-AVISO-DA-CHAVE-NOMEIA-O-MODULO-E-LE-UMA-VEZ: o carregado fica, os outros saem."""
    saida = _rodar_reconhecimento(tmp_path, ligado=True, carregado=True)
    assert "saem e o driver de fábrica volta" in saida, saida
    assert "O módulo hid-playstation do Hefesto carregado agora segue como está." in saida, saida


def test_o_reconhecimento_calado_sem_secure_boot(tmp_path: Path) -> None:
    saida = _rodar_reconhecimento(tmp_path, ligado=False)
    assert "Secure Boot" not in saida.replace("distro, bluez e Secure Boot", ""), saida


DOCTOR = RAIZ / "scripts" / "doctor.sh"


def _doctor(
    tmp_path: Path, script: str, *, ligado: bool, inscrita: bool, pedida: bool = False,
    carregado: bool = False, mokutil: str = "exit 1",
) -> str:
    arvore = tmp_path / "arvore-do-dkms"
    ko_do_dkms(tmp_path, arvore, "hefesto-hid-playstation", "hid-playstation.ko.zst")
    bin_ = _bin(tmp_path)
    (bin_ / "mokutil").write_text(f"#!/bin/sh\n{mokutil}\n", encoding="utf-8")
    (bin_ / "mokutil").chmod(0o755)
    env = {
        "PATH": f"{bin_}:/usr/bin:/bin",
        "HOME": str(tmp_path),
        "LC_ALL": "C.UTF-8",
        "HEFESTO_EFIVARS_ROOT": str(_efivars(tmp_path, ligado)),
        "HEFESTO_DKMS_TREE": str(arvore),
        "HEFESTO_SYS_MODULE": str(tmp_path / "sem-sys-module"),
        **_mok(tmp_path, gerada=True, inscrita=inscrita),
    }
    if pedida:
        (Path(env["HEFESTO_EFIVARS_ROOT"]) / MOK_NEW).write_bytes(b"\x07\x00\x00\x00" + CHAVE)
    if carregado:
        env["HEFESTO_SYS_MODULE"] = _com_o_modulo_carregado(tmp_path, bin_, arvore)
    r = subprocess.run(
        [BASH, "-c", f"source '{DOCTOR}'\nuname() {{ echo k; }}\n{script}\n"],
        capture_output=True, text=True, timeout=60, check=False, env=env,
    )
    return r.stdout + r.stderr


def test_o_doctor_avisa_o_secure_boot_sem_mokutil(tmp_path: Path) -> None:
    saida = _doctor(tmp_path, "_check_dkms_secureboot", ligado=True, inscrita=False)
    assert "[WARN]" in saida and "Secure Boot ligado" in saida, saida
    assert "DualSense" in saida and "mokutil --import" in saida, saida


def test_o_doctor_com_a_inscricao_pedida_diz_o_reinicio(tmp_path: Path) -> None:
    """D-2111-A-INSCRICAO-PEDIDA-ESPERA-O-REINICIO: o doctor não manda inscrever de novo."""
    saida = _doctor(tmp_path, "_check_dkms_secureboot", ligado=True, inscrita=False, pedida=True)
    assert "[WARN]" in saida and "espera o reinício" in saida and "Enroll MOK" in saida, saida
    assert "mokutil --import" not in saida and "não consegui ler" not in saida, saida


def test_o_doctor_diz_que_o_modulo_carregado_segue_como_esta(tmp_path: Path) -> None:
    """D-2111-O-AVISO-DA-CHAVE-NOMEIA-O-MODULO-E-LE-UMA-VEZ."""
    saida = _doctor(tmp_path, "_check_dkms_secureboot", ligado=True, inscrita=False, carregado=True)
    assert "O módulo hid-playstation do Hefesto carregado agora segue como está." in saida, saida
    assert "mokutil --import" in saida, saida


def test_o_doctor_le_a_chave_uma_vez(tmp_path: Path) -> None:
    """D-2111-O-AVISO-DA-CHAVE-NOMEIA-O-MODULO-E-LE-UMA-VEZ: um `mokutil` por execução."""
    contador = tmp_path / "mokutil.log"
    saida = _doctor(
        tmp_path, "_check_dkms_secureboot", ligado=True, inscrita=False,
        mokutil=f'echo x >> "{contador}"\necho "chave is not enrolled"\nexit 1',
    )
    assert "[WARN]" in saida, saida
    assert len(contador.read_text(encoding="utf-8").split()) == 1, saida


def test_o_doctor_calado_com_a_chave_inscrita(tmp_path: Path) -> None:
    saida = _doctor(tmp_path, "_check_dkms_secureboot", ligado=True, inscrita=True)
    assert "Secure Boot" not in saida, saida


def test_o_check_do_dualsense_diz_o_passo_da_mok(tmp_path: Path) -> None:
    """Carregado sem a guarda, nada staged, kernel conferido: a cura é a MOK."""
    sys_module = tmp_path / "sys-module"
    (sys_module / "hid_playstation").mkdir(parents=True)
    (sys_module / "hid_playstation" / "srcversion").write_text(
        "A74F93FE20FF36683AF7614\n", encoding="ascii"
    )
    saida = _doctor(
        tmp_path,
        f"HEFESTO_SYS_MODULE='{sys_module}' HEFESTO_DOCTOR_KERNEL=7.1.5-76070105-generic"
        " check_hefesto_hid_playstation_dkms",
        ligado=True, inscrita=False,
    )
    assert "[WARN]" in saida and "Secure Boot ligado" in saida, saida
    assert "mokutil --import" in saida, saida
