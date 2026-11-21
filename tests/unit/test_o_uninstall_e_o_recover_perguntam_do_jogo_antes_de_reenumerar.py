"""O uninstall e o `dsx_recover.sh` perguntam do jogo antes de reenumerar o controle.

O-UNINSTALL-E-O-RECOVER-PERGUNTAM-DO-JOGO-ANTES-DE-REENUMERAR-01: o `uninstall.sh` disparava
`udevadm trigger` de usb, hidraw e input, e o `scripts/dsx_recover.sh` o de usb da Sony, sem saber
do jogo. Os dois chamam o dono (`scripts/disparo_do_udev.sh`); o uninstall, com jogo aberto ou sem
saber, não dispara e põe o comando nas pendências do resumo.

A MORDIDA: devolva um `udevadm trigger` ao uninstall ou ao recover, ou faça o uninstall ignorar a
resposta do dono, e a régua reprova.
"""
from __future__ import annotations

import os
import shutil
import stat
import subprocess
from pathlib import Path

import pytest

from hefesto_dualsense4unix.integrations import quem_o_jogo_le

RAIZ = Path(__file__).resolve().parents[2]
UNINSTALL = RAIZ / "uninstall.sh"
RECOVER = RAIZ / "scripts" / "dsx_recover.sh"
DONO = RAIZ / "scripts" / "disparo_do_udev.sh"
LEITOR = RAIZ / "src" / "hefesto_dualsense4unix" / "integrations" / "quem_o_jogo_le.py"


def _codigo(arquivo: Path) -> str:
    linhas = arquivo.read_text(encoding="utf-8").splitlines()
    return "\n".join(ln for ln in linhas if not ln.strip().startswith("#"))


@pytest.mark.parametrize("arquivo", [UNINSTALL, RECOVER], ids=lambda p: p.name)
def test_nenhum_dos_dois_dispara_o_udev_por_conta_propria(arquivo: Path) -> None:
    """MORDIDA: devolva `udevadm trigger` a um dos dois e esta régua reprova."""
    culpadas = [ln for ln in _codigo(arquivo).splitlines() if "udevadm trigger" in ln]
    assert not culpadas, culpadas


def test_o_recover_chama_o_dono_do_lado_dele() -> None:
    texto = RECOVER.read_text(encoding="utf-8")
    funcao = texto.split("repin_and_trigger() {", 1)[1].split("\n}\n", 1)[0]
    assert 'bash "${AQUI}/disparo_do_udev.sh" --so-o-usb-da-sony' in funcao
    assert 'AQUI="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"' in texto
    assert (RECOVER.parent / "disparo_do_udev.sh").is_file()


def _o_recover(raiz: Path, *, jogo: bool, com_leitor: bool = True) -> list[str]:
    """O `repin_and_trigger` de verdade, com /sys, /proc e udevadm de mentira."""
    scripts = raiz / "arvore" / "scripts"
    scripts.mkdir(parents=True)
    shutil.copy2(DONO, scripts / DONO.name)
    if com_leitor:
        shutil.copy2(LEITOR, scripts / LEITOR.name)
    (raiz / "sys" / "bus" / "usb" / "devices").mkdir(parents=True)
    texto = RECOVER.read_text(encoding="utf-8")
    inicio = texto.index("repin_and_trigger() {")
    funcao = texto[inicio:texto.index("\n}\n", inicio) + 3].replace("/sys/", f"{raiz}/sys/")
    assert "/sys/" not in funcao.replace(f"{raiz}/sys/", "")
    bin_ = raiz / "bin"
    bin_.mkdir()
    diario = raiz / "udevadm.txt"
    falso = bin_ / "udevadm"
    falso.write_text(f'#!/bin/sh\nprintf "%s\\n" "$*" >> "{diario}"\n', encoding="utf-8")
    falso.chmod(falso.stat().st_mode | stat.S_IEXEC)
    ambiente = {**os.environ, "PATH": f"{bin_}:{os.environ['PATH']}",
                "HEFESTO_RAIZ_PROC": str(_proc(raiz, jogo=jogo))}
    feito = subprocess.run(
        ["bash", "-c", f'AQUI="{scripts}"\n{funcao}\nrepin_and_trigger'],
        env=ambiente, capture_output=True, text=True, check=False, timeout=30,
    )
    assert feito.returncode == 0, feito.stderr
    return diario.read_text(encoding="utf-8").splitlines() if diario.exists() else []


def test_o_recover_sem_jogo_dispara_so_o_usb_da_sony_como_antes(tmp_path: Path) -> None:
    """MORDIDA: chame o disparo inteiro no recover e o geral e o input entram na tempestade."""
    assert _o_recover(tmp_path, jogo=False) == [
        "trigger --subsystem-match=usb --attr-match=idVendor=054c"
    ]


@pytest.mark.parametrize(("jogo", "com_leitor"), [(True, True), (False, False)],
                         ids=["com-jogo", "sem-saber"])
def test_o_recover_com_jogo_ou_sem_saber_nao_dispara(
    tmp_path: Path, jogo: bool, com_leitor: bool
) -> None:
    """MORDIDA: dispare o usb da Sony sem perguntar do jogo e o recover reenumera o jogo."""
    assert _o_recover(tmp_path, jogo=jogo, com_leitor=com_leitor) == []


def _proc(raiz: Path, *, jogo: bool) -> Path:
    proc = raiz / "proc"
    (proc / "42").mkdir(parents=True)
    ambiente = b"HOME=/x\0"
    if jogo:
        ambiente += quem_o_jogo_le.ENV_DO_JOGO.encode() + b"=/compat/1234\0"
    (proc / "42" / "environ").write_bytes(ambiente)
    (proc / "self").mkdir()
    return proc


def _o_trecho_do_trigger() -> str:
    texto = UNINSTALL.read_text(encoding="utf-8")
    inicio = texto.index('        if bash "${DISPARO_DO_UDEV}" --pode-reenumerar; then')
    return texto[inicio:texto.index("\n        fi\n", inicio) + len("\n        fi\n")]


def _o_trecho_do_resumo() -> str:
    texto = UNINSTALL.read_text(encoding="utf-8")
    ponto = 'if [[ "${DRY_RUN}" -eq 1 ]]; then\n    printf \' Hefesto - DualSense4Unix: ENSAIO'
    inicio = texto.index(ponto)
    fim = texto.index('    printf \'   %s\\n\' "${_pendencias_do_udev[@]}"', inicio)
    return texto[inicio:texto.index("\nfi\n", fim) + 4]


def _o_uninstall(raiz: Path, *, jogo: bool, com_leitor: bool = True) -> tuple[list[str], str]:
    arvore = raiz / "arvore"
    (arvore / "scripts").mkdir(parents=True)
    shutil.copy2(DONO, arvore / "scripts" / DONO.name)
    if com_leitor:
        shutil.copy2(LEITOR, arvore / "scripts" / LEITOR.name)
    bin_ = raiz / "bin"
    bin_.mkdir()
    diario = raiz / "udevadm.txt"
    falso = bin_ / "udevadm"
    falso.write_text(f'#!/bin/sh\nprintf "%s\\n" "$*" >> "{diario}"\n', encoding="utf-8")
    falso.chmod(falso.stat().st_mode | stat.S_IEXEC)
    ambiente = {**os.environ, "PATH": f"{bin_}:{os.environ['PATH']}",
                "HEFESTO_RAIZ_PROC": str(_proc(raiz, jogo=jogo))}
    roteiro = "\n".join([
        f'ROOT_DIR="{arvore}"',
        'DISPARO_DO_UDEV="${ROOT_DIR}/scripts/disparo_do_udev.sh"',
        "_pendencias_do_udev=()",
        "_pendencias_da_steam=()",
        'sudo() { "$@"; }',
        _o_trecho_do_trigger(),
        "DRY_RUN=0",
        _o_trecho_do_resumo(),
    ])
    feito = subprocess.run(["bash", "-c", roteiro], env=ambiente, capture_output=True, text=True,
                           check=False, timeout=30)
    assert feito.returncode == 0, feito.stderr
    chamadas = diario.read_text(encoding="utf-8").splitlines() if diario.exists() else []
    return chamadas, feito.stdout


def _reenumerou(chamadas: list[str]) -> bool:
    alvos = ("hidraw", "idVendor=054c", "subsystem-match=usb", "subsystem-match=input")
    return any(a in c for c in chamadas for a in alvos) or "trigger" in chamadas


def test_sem_jogo_o_uninstall_reenumera_pelo_dono_e_nao_deixa_pendencia(tmp_path: Path) -> None:
    chamadas, saida = _o_uninstall(tmp_path, jogo=False)
    assert _reenumerou(chamadas)
    assert "regras do controle" not in saida
    assert "wipe completo" in saida


def test_com_jogo_o_uninstall_nao_reenumera_e_poe_a_pendencia_no_resumo(tmp_path: Path) -> None:
    """MORDIDA: faça o uninstall ignorar a resposta do dono e o jogo perde o controle."""
    chamadas, saida = _o_uninstall(tmp_path, jogo=True)
    assert chamadas == []
    assert "com pendência nas regras do controle" in saida
    assert "Falta reaplicar as regras do controle, que o jogo aberto adiou." in saida
    assert "Feche o jogo e rode:" in saida
    assert "disparo_do_udev.sh" in saida.split("rode:")[1]


def test_sem_saber_do_jogo_o_uninstall_tambem_adia(tmp_path: Path) -> None:
    chamadas, saida = _o_uninstall(tmp_path, jogo=False, com_leitor=False)
    assert chamadas == []
    assert "com pendência nas regras do controle" in saida
