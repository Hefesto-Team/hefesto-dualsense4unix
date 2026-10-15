"""O install em qualquer distro: a que é somente leitura também (13/10/2026).

Bazzite (`ID_LIKE=fedora`), Silverblue (`ID=fedora`) e SteamOS (`ID_LIKE=arch`)
parecem dnf e pacman pelo os-release, mas a imagem do sistema não aceita pacote
solto nem módulo DKMS. A família `imutavel` sai ANTES do `ID_LIKE`, pela marca do
sistema (`/run/ostree-booted`, `steamos-readonly status`), e nessa família o
install não chama gerente de pacotes nem DKMS, diz o efeito de cada item que
fica de fora e segue com a casa do usuário e o /etc.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

from tests.unit.test_haptica_nativa_01_o_ucm_do_dualsense import (
    _ganchos,
    _mesa,
    _rodar,
)
from tests.unit.test_install_garante_deps_em_qualquer_familia import (
    BASH,
    PRELUDO,
    _roda,
)
from tests.unit.test_install_universal_02_o_ucm_que_o_doctor_cura import (
    _findmnt_de_mentira,
    _rodar_com_path,
)
from tests.unit.test_o_ensaio_do_install_nao_escreve import (
    INSTALL_PATH,
    RAIZ,
    _bancada,
)

BAZZITE = 'ID=bazzite\nID_LIKE="fedora"\nVARIANT_ID=kinoite\n'
SILVERBLUE = "ID=fedora\nVARIANT_ID=silverblue\n"
STEAMOS = "ID=steamos\nID_LIKE=arch\n"
FEDORA = "ID=fedora\nVARIANT_ID=workstation\n"

CAMADA = RAIZ / "scripts" / "lib" / "camada_de_maquina.sh"


def _marca(tmp_path: Path, *, presente: bool) -> str:
    """O arquivo que o rpm-ostree cria no boot; ausente, é uma distro comum."""
    alvo = tmp_path / "run-ostree-booted"
    if presente:
        alvo.write_text("", encoding="utf-8")
    return str(alvo)


def _steamos_readonly(tmp_path: Path, estado: str) -> str:
    """Um `steamos-readonly` que responde o estado pedido; devolve o PATH."""
    binario = tmp_path / "bin-steamos"
    binario.mkdir(exist_ok=True)
    falso = binario / "steamos-readonly"
    falso.write_text(f"#!/bin/sh\nprintf '%s\\n' '{estado}'\n", encoding="utf-8")
    falso.chmod(0o755)
    return f"{binario}:{os.environ.get('PATH', '/usr/bin:/bin')}"


def _familia(tmp_path: Path, os_release: str, *, marca: bool, caminho: str | None = None) -> str:
    arquivo = tmp_path / "os-release"
    arquivo.write_text(os_release, encoding="utf-8")
    env = {
        "HEFESTO_OS_RELEASE": str(arquivo),
        "HEFESTO_OSTREE_MARCA": _marca(tmp_path, presente=marca),
    }
    if caminho:
        env["PATH"] = caminho
    proc = _roda("_familia_pacotes", env=env)
    assert proc.returncode == 0, proc.stderr
    return str(proc.stdout).strip()


# --- 1. a pergunta da família ------------------------------------------------


@pytest.mark.parametrize("os_release", [BAZZITE, SILVERBLUE])
def test_a_marca_do_ostree_vence_o_id_like(tmp_path: Path, os_release: str) -> None:
    """A MORDIDA: tire a pergunta de `/run/ostree-booted` e o Bazzite volta a ser dnf."""
    assert _familia(tmp_path, os_release, marca=True) == "imutavel"


@pytest.mark.parametrize("os_release", [BAZZITE, SILVERBLUE, FEDORA])
def test_sem_a_marca_o_os_release_decide_como_antes(tmp_path: Path, os_release: str) -> None:
    assert _familia(tmp_path, os_release, marca=False) == "dnf"


def test_o_steamos_com_o_sistema_travado_e_imutavel(tmp_path: Path) -> None:
    """A MORDIDA: tire a pergunta do `steamos-readonly` e o SteamOS volta a ser pacman."""
    caminho = _steamos_readonly(tmp_path, "enabled")
    assert _familia(tmp_path, STEAMOS, marca=False, caminho=caminho) == "imutavel"


def test_o_steamos_destravado_pelo_dono_e_pacman(tmp_path: Path) -> None:
    caminho = _steamos_readonly(tmp_path, "disabled")
    assert _familia(tmp_path, STEAMOS, marca=False, caminho=caminho) == "pacman"


def test_o_gancho_da_familia_continua_mandando(tmp_path: Path) -> None:
    proc = _roda(
        "_familia_pacotes",
        env={
            "HEFESTO_FAMILIA_PACOTES": "apt",
            "HEFESTO_OSTREE_MARCA": _marca(tmp_path, presente=True),
        },
    )
    assert proc.stdout.strip() == "apt"


def test_o_run_pkg_da_familia_imutavel_nao_chama_gerente(tmp_path: Path) -> None:
    """A MORDIDA: tire o ramo `imutavel` do `run_pkg` e ele devolve 0 sem dizer nada
    (ensaio) ou tenta o `sudo` (real)."""
    log = tmp_path / "sudo.log"
    binario = tmp_path / "bin"
    binario.mkdir()
    sudo = binario / "sudo"
    sudo.write_text(f'#!/bin/sh\necho "$*" >> {log}\nexit 0\n', encoding="utf-8")
    sudo.chmod(0o755)
    proc = _roda(
        "DRY_RUN=0; run_pkg gtk3 || echo RC=$?",
        preludo=PRELUDO,
        env={
            "HEFESTO_FAMILIA_PACOTES": "imutavel",
            "PATH": f"{binario}:{os.environ.get('PATH', '/usr/bin:/bin')}",
        },
    )
    assert "RC=1" in proc.stdout, proc.stdout + proc.stderr
    assert "somente leitura" in proc.stdout
    assert not log.exists(), "o run_pkg chamou o sudo numa distro somente leitura"


def test_o_comando_manual_da_familia_imutavel_nao_manda_um_gerente(tmp_path: Path) -> None:
    proc = _roda("comando_manual_pkg gtk3", env={"HEFESTO_FAMILIA_PACOTES": "imutavel"})
    assert proc.returncode == 0, proc.stderr
    saida = proc.stdout
    assert "imagem do sistema" in saida
    assert "sudo apt" not in saida
    assert "sudo dnf" not in saida
    assert "sudo pacman" not in saida


# --- 2. o ensaio inteiro -----------------------------------------------------


def _ensaio(tmp_path: Path, os_release: str, *, marca: bool) -> tuple[str, str]:
    _lar, diario, ambiente = _bancada(tmp_path)
    arquivo = tmp_path / "os-release"
    arquivo.write_text(os_release, encoding="utf-8")
    ambiente["HEFESTO_OS_RELEASE"] = str(arquivo)
    ambiente["HEFESTO_OSTREE_MARCA"] = _marca(tmp_path, presente=marca)
    resultado = subprocess.run(
        [BASH, str(INSTALL_PATH), "--dry-run", "--yes"],
        capture_output=True,
        text=True,
        check=False,
        env=ambiente,
        cwd=str(RAIZ),
        timeout=120,
    )
    assert resultado.returncode == 0, resultado.stdout[-2000:] + resultado.stderr
    chamadas = diario.read_text(encoding="utf-8") if diario.exists() else ""
    return resultado.stdout, chamadas


def test_o_ensaio_da_distro_somente_leitura_nao_planeja_pacote_nem_dkms(tmp_path: Path) -> None:
    """A MORDIDA: devolva o DKMS à família `imutavel` (ou a tire do `_ensaio_camada`) e o
    plano volta a prometer módulo que a imagem não aceita."""
    saida, chamadas = _ensaio(tmp_path, BAZZITE, marca=True)
    assert "FARIA" in saida
    # nenhum pacote, nenhum módulo, nenhum initramfs no plano:
    assert "instalar pacote(s) com" not in saida
    assert "compilar e instalar o módulo DKMS" not in saida
    assert "update-initramfs" not in saida
    assert "Os três módulos de kernel do Hefesto precisam compilar" not in saida
    for gerente in ("dnf", "apt-get", "pacman", "dkms", "update-initramfs"):
        assert f"{gerente} " not in chamadas, f"o ensaio chamou {gerente}: {chamadas}"
    # uma linha por item, com o efeito:
    assert "distro somente leitura" in saida
    assert "não há gerente de pacotes nem DKMS a chamar. O que fica de fora:" in saida
    assert "o microfone do DualSense pelo rádio fica desligado" in saida
    assert "o controle da Nintendo pode não subir pelo rádio" in saida
    assert "o dongle Wi-Fi USB não ganha a cura do fantasma USB" in saida
    assert "módulo DKMS hefesto-usb-f-hid (distro somente leitura)" in saida
    assert "a vibração dos jogos da Sony pelo cabo depende do perfil UCM" in saida
    # e o resto segue: udev e a casa do usuário continuam no plano.
    assert "regras udev" in saida


def test_o_ensaio_de_uma_distro_comum_continua_planejando_o_dkms(tmp_path: Path) -> None:
    """O controle da régua acima: sem a marca, o plano é o de sempre."""
    saida, _ = _ensaio(tmp_path, FEDORA, marca=False)
    assert "compilar e instalar o módulo DKMS hefesto-hid-playstation" in saida
    assert "distro somente leitura" not in saida


def test_o_reconhecimento_diz_a_familia_imutavel(tmp_path: Path) -> None:
    """A MORDIDA: tire o ramo `imutavel` do `_reconhecimento` e o aviso diz que o
    install «usa imutavel» como se fosse um gerente."""
    saida, _ = _ensaio(tmp_path, SILVERBLUE, marca=True)
    assert "distro somente leitura (Bazzite, Silverblue, SteamOS ou parente)" in saida
    assert "o install usa imutavel" not in saida


# --- 3. as funções de host ---------------------------------------------------


@pytest.mark.parametrize(
    ("rotina", "efeito"),
    [
        ("install_dkms_hid_playstation_host", "o microfone do DualSense pelo rádio"),
        ("install_dkms_hid_nintendo_host", "o controle da Nintendo"),
        ("install_dkms_rtw88_usb_host", "o dongle Wi-Fi USB"),
        ("install_dkms_usb_f_hid_host", "o usb_f_hid de fábrica segue"),
        ("install_ucm_dualsense_host", "a vibração dos jogos da Sony pelo cabo"),
    ],
)
def test_a_cura_de_host_pula_dizendo_o_efeito(tmp_path: Path, rotina: str, efeito: str) -> None:
    """A MORDIDA: tire o `_pula_por_so_leitura` da função e ela tenta o `sudo`."""
    corpo = (
        "set -euo pipefail\n"
        "NO_DKMS=0; NO_UCM=0; SKIP_UDEV=0; COM_UHID_CONTRAPRESSAO=0\n"
        f'ROOT_DIR="{RAIZ}"\n'
        'warn() { printf "aviso: %s\\n" "$*" >&2; }\n'
        "_familia_pacotes() { echo imutavel; }\n"
        f'source "{CAMADA}"\n'
        'sudo() { echo "SUDO-CHAMADO" >&2; return 1; }\n'
        f"{rotina}\n"
    )
    proc = subprocess.run(
        [BASH, "-c", corpo], capture_output=True, text=True, timeout=60, check=False
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "pulado (distro somente leitura)" in proc.stdout
    assert efeito in proc.stdout
    assert "SUDO-CHAMADO" not in proc.stderr


def test_a_cura_de_host_de_uma_distro_comum_nao_pula_por_so_leitura(tmp_path: Path) -> None:
    corpo = (
        "set -euo pipefail\n"
        "NO_DKMS=0; SKIP_UDEV=0\n"
        f'ROOT_DIR="{RAIZ}"\n'
        'warn() { printf "aviso: %s\\n" "$*" >&2; }\n'
        "_familia_pacotes() { echo dnf; }\n"
        f'source "{CAMADA}"\n'
        'sudo() { echo "SUDO-CHAMADO" >&2; return 1; }\n'
        "install_dkms_hid_playstation_host\n"
    )
    proc = subprocess.run(
        [BASH, "-c", corpo], capture_output=True, text=True, timeout=60, check=False
    )
    assert "distro somente leitura" not in proc.stdout


# --- 4. o roteiro do UCM na raiz somente leitura -----------------------------


def test_o_ucm_em_raiz_somente_leitura_sai_limpo_dizendo_o_efeito(tmp_path: Path) -> None:
    """A MORDIDA: tire a linha `efeito:` do roteiro e a distro imutável fica sem
    saber o que perde."""
    sysfs, ucm = _mesa(tmp_path)
    antes = _ganchos(ucm)
    r = _rodar_com_path(ucm, sysfs, _findmnt_de_mentira(tmp_path, "ro,relatime"))
    assert r.returncode == 0, r.stdout + r.stderr
    assert "só de leitura" in r.stdout
    assert "efeito: a vibração dos jogos da Sony pelo cabo" in r.stdout
    assert _ganchos(ucm) == antes


def test_o_remover_em_raiz_somente_leitura_nao_tenta_apagar(tmp_path: Path) -> None:
    """A MORDIDA: tire a guarda do `do_remover` e o `rm` falha com `set -e`."""
    sysfs, ucm = _mesa(tmp_path)
    assert _rodar(ucm, sysfs).returncode == 0
    gravados = _ganchos(ucm)
    caminho = _findmnt_de_mentira(tmp_path, "ro,relatime")
    r = subprocess.run(
        [
            "bash",
            str(RAIZ / "scripts" / "install_ucm_dualsense.sh"),
            "--raiz-ucm",
            str(ucm),
            "--sysfs",
            str(sysfs),
            "--remover",
        ],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
        env={**os.environ, "PATH": caminho},
    )
    assert r.returncode == 0, r.stdout + r.stderr
    assert "nada removido" in r.stdout
    assert _ganchos(ucm) == gravados
