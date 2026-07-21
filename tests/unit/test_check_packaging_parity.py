"""Testes de regressão da seção udev do scripts/check_packaging_parity.sh.

FIX-PACKAGING-SEED-PARITY-01: a checagem garante que CADA assets/NN-*.rules
está coberta pelos instaladores (install_udev.sh, install-host-udev.sh,
build_deb.sh) e pelo uninstall.sh — uma regra nova (como a 78) não pode
sumir de um instalador sem ninguém notar.

Mesmo padrão de tests/unit/test_check_anonymity.py: pytest + subprocess num
repo fake em tmp_path (sem bats-core, sem depender do estado do repo real).
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

SCRIPT_REL_PATH = "scripts/check_packaging_parity.sh"

RULE = "79-teste-parity.rules"


@pytest.fixture
def fake_repo(tmp_path: Path) -> Path:
    """Repo fake mínimo: só o script + uma regra 79 coberta em TODO lugar.

    Sem packaging/, as seções de applet COSMIC passam vazias — aqui o alvo é
    exclusivamente a seção de paridade udev. FIX-FLATPAK-UDEV-PARITY-01: o
    check passou a exigir a regra também no manifesto Flatpak, então o repo
    fake ganha um flatpak/fake.yml cobrindo a regra obrigatória.
    """
    repo_root = Path(__file__).resolve().parents[2]
    src_script = repo_root / SCRIPT_REL_PATH
    if not src_script.exists():
        pytest.skip(f"script {SCRIPT_REL_PATH} não encontrado no repo")

    (tmp_path / "scripts").mkdir()
    (tmp_path / "assets").mkdir()
    (tmp_path / "flatpak").mkdir()
    dst_script = tmp_path / SCRIPT_REL_PATH
    shutil.copy2(src_script, dst_script)
    dst_script.chmod(0o755)

    (tmp_path / "assets" / RULE).write_text("# regra de teste\n", encoding="utf-8")
    # Cobertura completa: nativo e host por nome; .deb por glob (como o real);
    # Flatpak por nome no manifesto.
    (tmp_path / "scripts" / "install_udev.sh").write_text(
        f'sudo install -Dm644 "$ASSETS/{RULE}" /etc/udev/rules.d/{RULE}\n',
        encoding="utf-8",
    )
    (tmp_path / "scripts" / "install-host-udev.sh").write_text(
        f'RULES=("{RULE}")\n', encoding="utf-8"
    )
    (tmp_path / "scripts" / "build_deb.sh").write_text(
        'for rules_file in assets/79-*.rules; do cp "$rules_file" x; done\n',
        encoding="utf-8",
    )
    (tmp_path / "uninstall.sh").write_text(
        f"sudo rm -f /etc/udev/rules.d/{RULE}\n", encoding="utf-8"
    )
    (tmp_path / "flatpak" / "fake.yml").write_text(
        f"      - install -Dm644 assets/{RULE}\n"
        f"          /app/share/hefesto-dualsense4unix/udev-rules/{RULE}\n",
        encoding="utf-8",
    )
    return tmp_path


def run_check(repo: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", SCRIPT_REL_PATH],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
    )


def test_regra_coberta_em_todos_passa(fake_repo: Path) -> None:
    result = run_check(fake_repo)
    assert result.returncode == 0, result.stdout
    assert f"[ OK ] {RULE}" in result.stdout


def test_regra_fora_do_install_host_falha_nomeando_o_furado(fake_repo: Path) -> None:
    (fake_repo / "scripts" / "install-host-udev.sh").write_text(
        'RULES=("70-outra.rules")\n', encoding="utf-8"
    )
    result = run_check(fake_repo)
    assert result.returncode == 1
    assert f"[FAIL] {RULE}" in result.stdout
    assert "scripts/install-host-udev.sh" in result.stdout


def test_regra_fora_do_build_deb_falha(fake_repo: Path) -> None:
    (fake_repo / "scripts" / "build_deb.sh").write_text(
        "# sem nenhuma regra\n", encoding="utf-8"
    )
    result = run_check(fake_repo)
    assert result.returncode == 1
    assert "scripts/build_deb.sh" in result.stdout


def test_regra_fora_do_uninstall_falha(fake_repo: Path) -> None:
    (fake_repo / "uninstall.sh").write_text("# nada\n", encoding="utf-8")
    result = run_check(fake_repo)
    assert result.returncode == 1
    assert "uninstall.sh" in result.stdout


def test_regra_opt_in_so_exige_uninstall(fake_repo: Path) -> None:
    """A 75 (opt-in) dispensa cobertura de instalação, mas exige uninstall."""
    optional = "75-ps5-controller-disable-usb-audio.rules"
    (fake_repo / "assets" / optional).write_text("# opt-in\n", encoding="utf-8")
    (fake_repo / "uninstall.sh").write_text(
        f"sudo rm -f /etc/udev/rules.d/{RULE} /etc/udev/rules.d/{optional}\n",
        encoding="utf-8",
    )
    result = run_check(fake_repo)
    assert result.returncode == 0, result.stdout
    assert f"[ OK ] {optional}" in result.stdout


def test_udev_parity_do_repo_real_esta_verde() -> None:
    """No repo REAL, a seção udev não pode ter [FAIL] (regressão de paridade).

    Não exige exit 0 do script inteiro: outras seções (applet COSMIC) têm
    achados próprios fora do escopo desta guarda.
    """
    repo_root = Path(__file__).resolve().parents[2]
    if not (repo_root / SCRIPT_REL_PATH).exists():
        pytest.skip(f"script {SCRIPT_REL_PATH} não encontrado no repo")
    result = subprocess.run(
        ["bash", SCRIPT_REL_PATH],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )
    udev_section = result.stdout.split("== paridade das regras udev", 1)
    assert len(udev_section) == 2, "seção udev ausente na saída do script"
    assert "[FAIL]" not in udev_section[1].split("═", 1)[0].split("─", 1)[0]


# --- BROKER-01 (Onda S — fd-injection, achado #21): paridade do broker ------
#
# Purge/remoção não pode deixar a unit ROOT do broker órfã habilitada em
# nenhuma forma de empacotamento. `_seed_broker_parity` monta um repo fake
# mínimo com o asset canônico presente (o que ARMA a checagem — sem ele a
# seção fica silenciosa, ver test_broker_sem_asset_pula_sem_falhar) e as 5
# formas + uninstall.sh cobrindo `hefesto-hidraw-broker`.

BROKER_TXT = "hefesto-hidraw-broker (broker root hide-hidraw)"


@pytest.fixture
def fake_repo_broker(tmp_path: Path) -> Path:
    repo_root = Path(__file__).resolve().parents[2]
    src_script = repo_root / SCRIPT_REL_PATH
    if not src_script.exists():
        pytest.skip(f"script {SCRIPT_REL_PATH} não encontrado no repo")

    for d in (
        "scripts",
        "assets/systemd",
        "packaging/arch",
        "packaging/debian",
        "packaging/fedora",
        "flatpak",
    ):
        (tmp_path / d).mkdir(parents=True)

    dst_script = tmp_path / SCRIPT_REL_PATH
    shutil.copy2(src_script, dst_script)
    dst_script.chmod(0o755)

    # Asset canônico: só a PRESENÇA importa para o gate da seção — o
    # conteúdo real vive em B1 (fora do escopo deste teste de paridade).
    (tmp_path / "assets" / "systemd" / "hefesto-hidraw-broker.service").write_text(
        "# unit de teste\n", encoding="utf-8"
    )

    (tmp_path / "scripts" / "build_deb.sh").write_text(
        f"echo '{BROKER_TXT}'\n", encoding="utf-8"
    )
    (tmp_path / "packaging" / "arch" / "PKGBUILD").write_text(
        f"# {BROKER_TXT}\n", encoding="utf-8"
    )
    (tmp_path / "packaging" / "fedora" / "hefesto-dualsense4unix.spec").write_text(
        f"# {BROKER_TXT}\n", encoding="utf-8"
    )
    (tmp_path / "flatpak" / "fake-broker.yml").write_text(
        f"# {BROKER_TXT}\n", encoding="utf-8"
    )
    (tmp_path / "scripts" / "install-host-udev.sh").write_text(
        f"echo '{BROKER_TXT}'\n", encoding="utf-8"
    )
    (tmp_path / "uninstall.sh").write_text(
        f"echo '{BROKER_TXT}'\n", encoding="utf-8"
    )
    # Achados Onda S #2/#8: o lado de REMOÇÃO do caminho Debian — prerm e
    # postrm precisam do teardown do broker (o build_deb.sh só EMPACOTA).
    (tmp_path / "packaging" / "debian" / "prerm").write_text(
        f"# {BROKER_TXT}\n", encoding="utf-8"
    )
    (tmp_path / "packaging" / "debian" / "postrm").write_text(
        f"# {BROKER_TXT}\n", encoding="utf-8"
    )
    return tmp_path


def test_broker_coberto_em_todos_passa(fake_repo_broker: Path) -> None:
    result = run_check(fake_repo_broker)
    assert result.returncode == 0, result.stdout
    assert "[ OK ] hefesto-hidraw-broker" in result.stdout


def test_broker_sem_asset_pula_sem_falhar(tmp_path: Path) -> None:
    """Sem o asset canônico (repo/fixture que não conhece a onda S), a seção
    fica silenciosa — nunca [FAIL] por ausência do que não existe."""
    repo_root = Path(__file__).resolve().parents[2]
    src_script = repo_root / SCRIPT_REL_PATH
    if not src_script.exists():
        pytest.skip(f"script {SCRIPT_REL_PATH} não encontrado no repo")
    (tmp_path / "scripts").mkdir()
    (tmp_path / "assets").mkdir()
    dst_script = tmp_path / SCRIPT_REL_PATH
    shutil.copy2(src_script, dst_script)
    dst_script.chmod(0o755)

    result = run_check(tmp_path)
    assert "hefesto-hidraw-broker" not in "\n".join(
        line for line in result.stdout.splitlines() if "[FAIL]" in line
    )
    broker_section = result.stdout.split("== paridade do broker hide-hidraw", 1)
    assert len(broker_section) == 2, "seção do broker ausente na saída do script"
    assert "[ OK ]" in broker_section[1].split("═", 1)[0].split("─", 1)[0]


def test_broker_fora_do_build_deb_falha_nomeando_o_furado(fake_repo_broker: Path) -> None:
    (fake_repo_broker / "scripts" / "build_deb.sh").write_text("# nada\n", encoding="utf-8")
    result = run_check(fake_repo_broker)
    assert result.returncode == 1
    assert "[FAIL] hefesto-hidraw-broker" in result.stdout
    assert "scripts/build_deb.sh" in result.stdout


def test_broker_fora_do_pkgbuild_falha(fake_repo_broker: Path) -> None:
    (fake_repo_broker / "packaging" / "arch" / "PKGBUILD").write_text(
        "# nada\n", encoding="utf-8"
    )
    result = run_check(fake_repo_broker)
    assert result.returncode == 1
    assert "packaging/arch/PKGBUILD" in result.stdout


def test_broker_fora_do_spec_falha(fake_repo_broker: Path) -> None:
    (fake_repo_broker / "packaging" / "fedora" / "hefesto-dualsense4unix.spec").write_text(
        "# nada\n", encoding="utf-8"
    )
    result = run_check(fake_repo_broker)
    assert result.returncode == 1
    assert "packaging/fedora/hefesto-dualsense4unix.spec" in result.stdout


def test_broker_fora_do_flatpak_falha(fake_repo_broker: Path) -> None:
    (fake_repo_broker / "flatpak" / "fake-broker.yml").write_text(
        "# nada\n", encoding="utf-8"
    )
    result = run_check(fake_repo_broker)
    assert result.returncode == 1
    assert "flatpak/*.yml" in result.stdout


def test_broker_fora_do_install_host_udev_falha(fake_repo_broker: Path) -> None:
    (fake_repo_broker / "scripts" / "install-host-udev.sh").write_text(
        "# nada\n", encoding="utf-8"
    )
    result = run_check(fake_repo_broker)
    assert result.returncode == 1
    assert "scripts/install-host-udev.sh" in result.stdout


def test_broker_fora_do_uninstall_falha(fake_repo_broker: Path) -> None:
    (fake_repo_broker / "uninstall.sh").write_text("# nada\n", encoding="utf-8")
    result = run_check(fake_repo_broker)
    assert result.returncode == 1
    assert "uninstall.sh" in result.stdout


def test_broker_fora_do_prerm_debian_falha(fake_repo_broker: Path) -> None:
    """Achados Onda S #2/#8: o gate dava falso-verde com o purge do .deb sem
    NENHUM teardown do broker — ele só olhava o build_deb.sh (que menciona o
    broker para EMPACOTAR, não para remover). prerm sem broker = FAIL."""
    (fake_repo_broker / "packaging" / "debian" / "prerm").write_text(
        "# nada\n", encoding="utf-8"
    )
    result = run_check(fake_repo_broker)
    assert result.returncode == 1
    assert "[FAIL] hefesto-hidraw-broker" in result.stdout
    assert "packaging/debian/prerm" in result.stdout


def test_broker_fora_do_postrm_debian_falha(fake_repo_broker: Path) -> None:
    (fake_repo_broker / "packaging" / "debian" / "postrm").write_text(
        "# nada\n", encoding="utf-8"
    )
    result = run_check(fake_repo_broker)
    assert result.returncode == 1
    assert "packaging/debian/postrm" in result.stdout


def test_broker_parity_do_repo_real_esta_verde() -> None:
    """No repo REAL, a seção do broker não pode ter [FAIL] — regressão."""
    repo_root = Path(__file__).resolve().parents[2]
    if not (repo_root / SCRIPT_REL_PATH).exists():
        pytest.skip(f"script {SCRIPT_REL_PATH} não encontrado no repo")
    result = subprocess.run(
        ["bash", SCRIPT_REL_PATH],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )
    broker_section = result.stdout.split("== paridade do broker hide-hidraw", 1)
    assert len(broker_section) == 2, "seção do broker ausente na saída do script"
    assert "[FAIL]" not in broker_section[1].split("═", 1)[0].split("─", 1)[0]


# --- Corretor final (interação T x W): remoção do DKMS hid-nintendo ------------
#
# O bloco da Onda W (rtw88-usb) gateia a REMOÇÃO (prerm/postrm/.install/%preun
# /uninstall), mas o bloco irmão da Onda T (hid-nintendo) não gateava — apagar
# o `dkms remove` do hid-nintendo de um hook de pacote passava verde
# (falso-verde reproduzido ao vivo) e o `apt purge` deixava o módulo
# `hefesto-hid-nintendo` órfão registrado no DKMS para sempre. Estes testes
# pinam o contrato simétrico ao do rtw88-usb.

_DKMS_REMOVE_NINTENDO = 'dkms remove "hefesto-hid-nintendo/1.0.0" --all\n'


@pytest.fixture
def fake_repo_dkms_nintendo(tmp_path: Path) -> Path:
    repo_root = Path(__file__).resolve().parents[2]
    src_script = repo_root / SCRIPT_REL_PATH
    if not src_script.exists():
        pytest.skip(f"script {SCRIPT_REL_PATH} não encontrado no repo")

    for d in (
        "scripts",
        "assets/dkms/hid-nintendo",
        "packaging/arch",
        "packaging/debian",
        "packaging/fedora",
        "flatpak",
    ):
        (tmp_path / d).mkdir(parents=True)

    dst_script = tmp_path / SCRIPT_REL_PATH
    shutil.copy2(src_script, dst_script)
    dst_script.chmod(0o755)

    # Asset que ARMA a seção (a presença basta; o conteúdo real é da Onda T).
    (tmp_path / "assets" / "dkms" / "hid-nintendo" / "dkms.conf").write_text(
        "# dkms de teste\n", encoding="utf-8"
    )
    # Fontes + lib em todos os formatos.
    fontes = "# dkms/hid-nintendo + dkms_lib.sh\n"
    (tmp_path / "scripts" / "build_deb.sh").write_text(fontes, encoding="utf-8")
    (tmp_path / "packaging" / "arch" / "PKGBUILD").write_text(
        fontes, encoding="utf-8"
    )
    (tmp_path / "flatpak" / "fake-dkms.yml").write_text(fontes, encoding="utf-8")
    (tmp_path / "scripts" / "install-host-udev.sh").write_text(
        "dkms_install_patched_module hefesto-hid-nintendo\n", encoding="utf-8"
    )
    # Remoção desregistra em todos os hooks de pacote + uninstall nativo.
    (tmp_path / "packaging" / "fedora" / "hefesto-dualsense4unix.spec").write_text(
        fontes + _DKMS_REMOVE_NINTENDO, encoding="utf-8"
    )
    (tmp_path / "packaging" / "debian" / "prerm").write_text(
        _DKMS_REMOVE_NINTENDO, encoding="utf-8"
    )
    (tmp_path / "packaging" / "debian" / "postrm").write_text(
        _DKMS_REMOVE_NINTENDO, encoding="utf-8"
    )
    (tmp_path / "packaging" / "arch" / "hefesto-dualsense4unix.install").write_text(
        _DKMS_REMOVE_NINTENDO, encoding="utf-8"
    )
    (tmp_path / "uninstall.sh").write_text(
        _DKMS_REMOVE_NINTENDO, encoding="utf-8"
    )
    return tmp_path


def test_dkms_nintendo_coberto_em_todos_passa(fake_repo_dkms_nintendo: Path) -> None:
    result = run_check(fake_repo_dkms_nintendo)
    assert result.returncode == 0, result.stdout
    assert "[ OK ] dkms hid-nintendo" in result.stdout


def test_dkms_nintendo_sem_remocao_no_postrm_falha(
    fake_repo_dkms_nintendo: Path,
) -> None:
    """O falso-verde reproduzido: postrm sem o `dkms remove` do hid-nintendo
    passava enquanto a mutação idêntica no rtw88-usb falhava."""
    (fake_repo_dkms_nintendo / "packaging" / "debian" / "postrm").write_text(
        "# nada\n", encoding="utf-8"
    )
    result = run_check(fake_repo_dkms_nintendo)
    assert result.returncode == 1
    assert "[FAIL] dkms hid-nintendo" in result.stdout
    assert "packaging/debian/postrm(remoção)" in result.stdout


def test_dkms_nintendo_sem_remocao_no_prerm_falha(
    fake_repo_dkms_nintendo: Path,
) -> None:
    (fake_repo_dkms_nintendo / "packaging" / "debian" / "prerm").write_text(
        "# nada\n", encoding="utf-8"
    )
    result = run_check(fake_repo_dkms_nintendo)
    assert result.returncode == 1
    assert "packaging/debian/prerm(remoção)" in result.stdout


def test_dkms_nintendo_sem_remocao_no_install_arch_falha(
    fake_repo_dkms_nintendo: Path,
) -> None:
    (
        fake_repo_dkms_nintendo
        / "packaging"
        / "arch"
        / "hefesto-dualsense4unix.install"
    ).write_text("# nada\n", encoding="utf-8")
    result = run_check(fake_repo_dkms_nintendo)
    assert result.returncode == 1
    assert "packaging/arch/hefesto-dualsense4unix.install(remoção)" in result.stdout


def test_dkms_nintendo_fora_do_uninstall_falha(
    fake_repo_dkms_nintendo: Path,
) -> None:
    (fake_repo_dkms_nintendo / "uninstall.sh").write_text(
        "# nada\n", encoding="utf-8"
    )
    result = run_check(fake_repo_dkms_nintendo)
    assert result.returncode == 1
    assert "uninstall.sh" in result.stdout


def test_dkms_nintendo_parity_do_repo_real_esta_verde() -> None:
    """No repo REAL, a seção do hid-nintendo não pode ter [FAIL] — regressão."""
    repo_root = Path(__file__).resolve().parents[2]
    if not (repo_root / SCRIPT_REL_PATH).exists():
        pytest.skip(f"script {SCRIPT_REL_PATH} não encontrado no repo")
    result = subprocess.run(
        ["bash", SCRIPT_REL_PATH],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )
    secao = result.stdout.split(
        "== paridade da cura DKMS (assets/dkms/hid-nintendo", 1
    )
    assert len(secao) == 2, "seção do dkms hid-nintendo ausente na saída"
    assert "[FAIL]" not in secao[1].split("== ", 1)[0]
