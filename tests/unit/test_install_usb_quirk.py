"""Contrato do scripts/install_usb_quirk.sh (Opção D — quirk que PRESERVA o áudio).

FEAT-DSX-DEFINITIVE-FIX-01 §7.5. O quirk `usbcore.quirks=054c:0ce6:gn`
(g=DELAY_INIT, n=DELAY_CTRL_MSG) ESPAÇA a rajada de control-transfers do probe do
`snd-usb-audio` para ela não tombar o link — mitiga o storm -71 PRESERVANDO o mic e
o fone do jack do DualSense. É a ALTERNATIVA à regra 75 (áudio-off).

IMPORTANTE: é um PARÂMETRO DE CMDLINE do kernel, NÃO uma regra udev — uma regra udev
não consegue alterar o próprio enumeramento do device. Por isso é empacotado como
script de install ciente do bootloader, e não como assets/*.rules.

Estes testes são leves: SEM root e SEM tocar /etc — validam que o script existe e é
executável, que `--status`/`--check` rodam read-only, e que a string do quirk é
EXATAMENTE `usbcore.quirks=054c:0ce6:gn`. Espelha o estilo de
tests/unit/test_udev_rule_75_disable_usb_audio.py.

A MIGRAÇÃO de 14/10/2026 (o `054c:0df2:gn` do pad virtual sai) roda contra um
`/etc` e um `/sys` de mentira (`HEFESTO_QUIRK_*`), com `sudo`, `kernelstub` e
`update-grub` de mentira num PATH que só tem o que o script usa. Desde
O-CMDLINE-DO-DUALSENSE-SO-SE-ESCREVE-NO-KERNELSTUB-01 quem escreve é o
`integrations/kernel_cmdline.py`: o token de terceiro é fundido, e o `/etc/kernel/cmdline`
do systemd-boot entra na conta.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPO_ROOT / "scripts" / "install_usb_quirk.sh"

EXPECTED_QUIRK = "usbcore.quirks=054c:0ce6:gn"
TOKEN_VELHO = "usbcore.quirks=054c:0ce6:gn,054c:0df2:gn"


@pytest.fixture(scope="module")
def script_text() -> str:
    return SCRIPT_PATH.read_text(encoding="utf-8")


def test_arquivo_existe() -> None:
    assert SCRIPT_PATH.is_file(), f"script ausente em {SCRIPT_PATH}"


def test_arquivo_executavel() -> None:
    import os

    assert os.access(SCRIPT_PATH, os.X_OK), f"{SCRIPT_PATH} não é executável (chmod +x)"


def test_string_do_quirk_exata(script_text: str) -> None:
    assert f'QUIRK="{EXPECTED_QUIRK}"' in script_text, (
        f"constante QUIRK não bate exatamente: esperado QUIRK=\"{EXPECTED_QUIRK}\""
    )


def test_sintaxe_bash_valida() -> None:
    result = subprocess.run(
        ["bash", "-n", str(SCRIPT_PATH)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, f"erro de sintaxe bash:\n{result.stderr}"


def test_status_roda_sem_root() -> None:
    result = subprocess.run(
        ["bash", str(SCRIPT_PATH), "--status"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, f"--status falhou (rc={result.returncode}):\n{result.stderr}"
    assert EXPECTED_QUIRK in result.stdout, "--status não imprime o quirk alvo"


def test_check_eh_alias_de_status() -> None:
    result = subprocess.run(
        ["bash", str(SCRIPT_PATH), "--check"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, f"--check falhou (rc={result.returncode}):\n{result.stderr}"


def test_nao_e_regra_udev_no_header(script_text: str) -> None:
    lowered = script_text.lower()
    assert "não é uma regra udev" in lowered or "não é regra udev" in lowered, (
        "header precisa esclarecer que NÃO é regra udev (é cmdline do kernel)"
    )


def test_single_token_documentado(script_text: str) -> None:
    assert "só um token" in script_text.lower() or "só UM token".lower() in script_text.lower()


def test_modos_de_reversao_e_runtime_existem(script_text: str) -> None:
    for flag in ("--remove", "--runtime", "--status"):
        assert flag in script_text, f"flag {flag} ausente no dispatch do script"


_KERNELSTUB_DE_MENTIRA = """#!/usr/bin/env python3
import json, sys
conf = sys.argv[0].rsplit("/", 2)[0] + "/etc/kernelstub/configuration"
with open(conf) as fh:
    data = json.load(fh)
opts = data["user"]["kernel_options"]
gesto, token = sys.argv[1], sys.argv[2]
if gesto == "--delete-options":
    opts[:] = [o for o in opts if o != token]
elif gesto == "--add-options":
    opts.append(token)
with open(conf, "w") as fh:
    json.dump(data, fh)
"""

_SUDO_DE_MENTIRA = '#!/bin/bash\nexec "$@"\n'
_UPDATE_GRUB_DE_MENTIRA = '#!/bin/bash\necho regenerou >> "${0%/*}/../update-grub.log"\n'


def _bancada(tmp_path: Path, *, com_kernelstub: bool) -> tuple[Path, dict[str, str]]:
    """Um lar de mentira: bin/ só com o que o script usa, etc/ e sys/ próprios."""
    import json
    import shutil

    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    for ferramenta in ("grep", "sed", "cat", "tee", "id", "sort", "python3", "env"):
        alvo = shutil.which(ferramenta)
        assert alvo, ferramenta
        (bin_dir / ferramenta).symlink_to(alvo)
    for nome, corpo in (("sudo", _SUDO_DE_MENTIRA), ("update-grub", _UPDATE_GRUB_DE_MENTIRA)):
        (bin_dir / nome).write_text(corpo, encoding="utf-8")
        (bin_dir / nome).chmod(0o755)
    kstub = tmp_path / "etc" / "kernelstub" / "configuration"
    kstub.parent.mkdir(parents=True)
    if com_kernelstub:
        (bin_dir / "kernelstub").write_text(_KERNELSTUB_DE_MENTIRA, encoding="utf-8")
        (bin_dir / "kernelstub").chmod(0o755)
        kstub.write_text(json.dumps({"user": {"kernel_options": [
            "quiet", TOKEN_VELHO, "splash"]}}), encoding="utf-8")
    grub = tmp_path / "etc" / "default" / "grub"
    grub.parent.mkdir(parents=True)
    grub.write_text(f'GRUB_TIMEOUT=5\nGRUB_CMDLINE_LINUX_DEFAULT="quiet {TOKEN_VELHO} splash"\n',
                    encoding="utf-8")
    sysfs = tmp_path / "sys" / "quirks"
    sysfs.parent.mkdir(parents=True)
    sysfs.write_text("054c:0ce6:gn,054c:0df2:gn", encoding="utf-8")
    env = {
        "PATH": str(bin_dir),
        "HOME": str(tmp_path),
        "HEFESTO_QUIRK_KERNELSTUB_CONF": str(kstub),
        "HEFESTO_QUIRK_GRUB_CONF": str(grub),
        "HEFESTO_QUIRK_SYSFS": str(sysfs),
        "HEFESTO_QUIRK_KERNEL_CMDLINE": str(tmp_path / "etc" / "kernel" / "cmdline"),
    }
    return tmp_path, env


def _roda(env: dict[str, str], *args: str) -> subprocess.CompletedProcess[str]:
    import shutil

    bash = shutil.which("bash")
    assert bash
    return subprocess.run([bash, str(SCRIPT_PATH), *args], capture_output=True,
                          text=True, check=False, env=env, timeout=60)


def test_o_kernelstub_com_o_token_velho_migra(tmp_path: Path) -> None:
    import json

    raiz, env = _bancada(tmp_path, com_kernelstub=True)
    r = _roda(env)
    assert r.returncode == 0, r.stderr
    conf = json.loads((raiz / "etc/kernelstub/configuration").read_text(encoding="utf-8"))
    opcoes = conf["user"]["kernel_options"]
    assert TOKEN_VELHO not in opcoes, r.stdout
    assert opcoes.count(EXPECTED_QUIRK) == 1, opcoes
    assert (raiz / "sys/quirks").read_text(encoding="utf-8") == "054c:0ce6:gn"
    segunda = _roda(env)
    assert segunda.returncode == 0, segunda.stderr
    assert "migrando" not in segunda.stdout, "a segunda volta tem de ser no-op"


def test_o_grub_com_o_token_velho_migra(tmp_path: Path) -> None:
    raiz, env = _bancada(tmp_path, com_kernelstub=False)
    r = _roda(env)
    assert r.returncode == 0, r.stderr
    grub = (raiz / "etc/default/grub").read_text(encoding="utf-8")
    assert f'GRUB_CMDLINE_LINUX_DEFAULT="quiet {EXPECTED_QUIRK} splash"' in grub, grub
    assert "0df2" not in grub
    assert (raiz / "update-grub.log").is_file(), "o grub.cfg não foi regenerado"


def test_o_terceiro_no_mesmo_token_fica(tmp_path: Path) -> None:
    raiz, env = _bancada(tmp_path, com_kernelstub=False)
    grub = raiz / "etc/default/grub"
    grub.write_text('GRUB_CMDLINE_LINUX_DEFAULT="usbcore.quirks=0bda:8153:k,'
                    '054c:0ce6:gn,054c:0df2:gn"\n', encoding="utf-8")
    r = _roda(env)
    assert r.returncode == 0, r.stderr
    assert 'GRUB_CMDLINE_LINUX_DEFAULT="usbcore.quirks=0bda:8153:k,054c:0ce6:gn"' in (
        grub.read_text(encoding="utf-8"))


def test_o_remove_tira_o_velho_e_o_novo(tmp_path: Path) -> None:
    raiz, env = _bancada(tmp_path, com_kernelstub=False)
    r = _roda(env, "--remove")
    assert r.returncode == 0, r.stderr
    grub = (raiz / "etc/default/grub").read_text(encoding="utf-8")
    assert 'GRUB_CMDLINE_LINUX_DEFAULT="quiet splash"' in grub, grub


def test_o_status_aponta_o_defeito(tmp_path: Path) -> None:
    _, env = _bancada(tmp_path, com_kernelstub=False)
    r = _roda(env, "--status")
    assert r.returncode == 0, r.stderr
    assert "[DEFEITO] 054c:0df2:gn" in r.stdout, r.stdout


def test_o_token_de_terceiro_e_fundido_e_nao_duplicado(tmp_path: Path) -> None:
    raiz, env = _bancada(tmp_path, com_kernelstub=False)
    grub = raiz / "etc/default/grub"
    grub.write_text('GRUB_CMDLINE_LINUX_DEFAULT="quiet usbcore.quirks=0bda:8153:k"\n',
                    encoding="utf-8")
    r = _roda(env)
    assert r.returncode == 0, r.stderr
    assert grub.read_text(encoding="utf-8") == (
        'GRUB_CMDLINE_LINUX_DEFAULT="quiet usbcore.quirks=0bda:8153:k,054c:0ce6:gn"\n')


def test_o_systemd_boot_ganha_o_quirk_no_etc_kernel_cmdline(tmp_path: Path) -> None:
    raiz, env = _bancada(tmp_path, com_kernelstub=False)
    (raiz / "etc/default/grub").unlink()
    cmdline = raiz / "etc/kernel/cmdline"
    cmdline.parent.mkdir(parents=True)
    cmdline.write_text("root=UUID=0000-forjado rw quiet\n", encoding="utf-8")
    r = _roda(env)
    assert r.returncode == 0, r.stderr
    assert cmdline.read_text(encoding="utf-8") == (
        f"root=UUID=0000-forjado rw quiet {EXPECTED_QUIRK}\n")
    assert "kernel-install" in r.stderr, "sem kernel-install, o aviso tem de dizer o que falta"
    status = _roda(env, "--status")
    assert "(systemd-boot)" in status.stdout, status.stdout
    assert _roda(env, "--remove").returncode == 0
    assert cmdline.read_text(encoding="utf-8") == "root=UUID=0000-forjado rw quiet\n"


def test_sem_carregador_conhecido_o_token_exato_vai_para_a_tela(tmp_path: Path) -> None:
    raiz, env = _bancada(tmp_path, com_kernelstub=False)
    (raiz / "etc/default/grub").unlink()
    r = _roda(env)
    assert r.returncode == 0, r.stderr
    assert f"adicione MANUALMENTE este token ao cmdline do seu bootloader: {EXPECTED_QUIRK}" in (
        r.stdout)
