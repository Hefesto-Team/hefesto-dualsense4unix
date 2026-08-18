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

RULE = "72-teste-parity.rules"

#: build_deb.sh fake no molde do real: UMA lista de globs consumida pelos DOIS
#: destinos (diretório vivo /usr/lib/udev/rules.d + espelho
#: /usr/share/hefesto-dualsense4unix/udev-rules).
_BUILD_DEB_DOIS_DESTINOS = """\
UDEV_RULES_GLOBS=(
    assets/72-*.rules
)
for rules_file in "${UDEV_RULES_GLOBS[@]}"; do
    cp "$rules_file" "${STAGING}/usr/lib/udev/rules.d/"
done
for rules_file in "${UDEV_RULES_GLOBS[@]}"; do
    install -Dm644 "$rules_file" \
        "${STAGING}/usr/share/hefesto-dualsense4unix/udev-rules/"
done
"""


def _semeia_simbolico(raiz: Path) -> None:
    """Põe no repo fake o simbólico da bandeja e a cópia do applet.

    APPLET-MONOCROMÁTICO-01 (07/08/2026): o gate passou a exigir que o
    simbólico exista e que bandeja e applet sirvam o MESMO desenho. Sem estes
    dois arquivos, todo teste de "passa" deste módulo reprovaria por uma seção
    que não é o alvo dele — e, pior, a saída começaria pela seção de udev,
    mandando quem lesse procurar no lugar errado.
    """
    desenho = '<svg viewBox="0 0 16 16"><title>fake</title></svg>\n'
    alvos = (
        raiz / "assets" / "simbolico" / "hefesto-dualsense4unix-symbolic.svg",
        raiz
        / "packaging"
        / "cosmic-applet"
        / "data"
        / "icons"
        / "hicolor"
        / "symbolic"
        / "apps"
        / "com.vitoriamaria.HefestoDualsense4Unix-symbolic.svg",
    )
    for alvo in alvos:
        alvo.parent.mkdir(parents=True, exist_ok=True)
        alvo.write_text(desenho, encoding="utf-8")


@pytest.fixture
def fake_repo(tmp_path: Path) -> Path:
    """Repo fake mínimo: só o script + uma regra 72 coberta em TODO lugar.

    Sem packaging/, as seções de applet COSMIC passam vazias — aqui o alvo é
    exclusivamente a seção de paridade udev. FIX-FLATPAK-UDEV-PARITY-01: o
    check passou a exigir a regra também no manifesto Flatpak, então o repo
    fake ganha um flatpak/fake.yml cobrindo a regra obrigatória.

    OQ-6 (09/08/2026): a regra do fixture era `79-teste-parity`
    e virou `72-teste-parity`, com CONTEÚDO de regra de acesso. Motivo: o
    portão ganhou a seção "acesso da sessão aos nós de ENTRADA", que cobra que
    ALGUMA regra dê `TAG+="uaccess"` ao touchpad e aos sensores de movimento —
    e um repo com regras udev e nenhuma delas dando acesso é exatamente o
    defeito que a seção existe para acusar. O número mudou junto porque a mesma
    seção cobra `< 73`: acima disso a `73-seat-late.rules` já passou e a TAG
    nunca vira ACL. O alvo destes testes (paridade contra instaladores) não muda —
    a regra continua obrigatória e continua tendo de aparecer em todo formato.
    """
    repo_root = Path(__file__).resolve().parents[2]
    src_script = repo_root / SCRIPT_REL_PATH
    if not src_script.exists():
        pytest.skip(f"script {SCRIPT_REL_PATH} não encontrado no repo")

    (tmp_path / "scripts").mkdir()
    (tmp_path / "assets").mkdir()
    (tmp_path / "flatpak").mkdir()
    (tmp_path / "packaging" / "arch").mkdir(parents=True)
    (tmp_path / "packaging" / "fedora").mkdir(parents=True)
    dst_script = tmp_path / SCRIPT_REL_PATH
    shutil.copy2(src_script, dst_script)
    dst_script.chmod(0o755)

    # OQ-6: conteúdo de regra de ACESSO, não um comentário
    # solto — a seção nova do portão cobra `TAG+="uaccess"` no nó de touchpad e
    # no de sensores de movimento, e só linha de CÓDIGO conta.
    (tmp_path / "assets" / RULE).write_text(
        "# regra de teste\n"
        'ACTION=="add|change", SUBSYSTEM=="input", KERNEL=="event*", '
        'ATTRS{id/vendor}=="054c", ATTRS{name}=="*Motion Sensors", TAG+="uaccess"\n'
        'ACTION=="add|change", SUBSYSTEM=="input", KERNEL=="event*", '
        'ATTRS{id/vendor}=="054c", ATTRS{name}=="*Touchpad", TAG+="uaccess"\n',
        encoding="utf-8",
    )
    # Cobertura completa: nativo e host por nome; .deb por glob (como o real);
    # Flatpak por nome no manifesto. O `udevadm trigger` de input também é
    # cobrado (sem ele a regra de acesso só valeria no próximo replug).
    (tmp_path / "scripts" / "install_udev.sh").write_text(
        f'sudo install -Dm644 "$ASSETS/{RULE}" /etc/udev/rules.d/{RULE}\n'
        "sudo udevadm trigger --action=change --subsystem-match=input\n",
        encoding="utf-8",
    )
    (tmp_path / "scripts" / "install-host-udev.sh").write_text(
        f'RULES=("{RULE}")\n'
        'cmd+="udevadm trigger --action=change --subsystem-match=input; "\n',
        encoding="utf-8",
    )
    # BUG-DEB-MIRROR-RULES-INCOMPLETO-01: o .deb tem DOIS destinos (o
    # diretório vivo e o espelho /usr/share/.../udev-rules, que o
    # install-host-udev.sh prefere e exige completo). O contrato agora é uma
    # lista ÚNICA (UDEV_RULES_GLOBS) consumida pelos dois laços.
    (tmp_path / "scripts" / "build_deb.sh").write_text(
        _BUILD_DEB_DOIS_DESTINOS, encoding="utf-8"
    )
    # A cobertura de Arch e Fedora entrou no mesmo contrato (a ausência das
    # 82/83/84 nesses dois nunca reprovava — eles ficavam fora do bloco).
    (tmp_path / "packaging" / "arch" / "PKGBUILD").write_text(
        f"    assets/{RULE} \\\n", encoding="utf-8"
    )
    (tmp_path / "packaging" / "fedora" / "hefesto-dualsense4unix.spec").write_text(
        f"    assets/{RULE}\n", encoding="utf-8"
    )
    (tmp_path / "uninstall.sh").write_text(
        f"sudo rm -f /etc/udev/rules.d/{RULE}\n", encoding="utf-8"
    )
    (tmp_path / "flatpak" / "fake.yml").write_text(
        f"      - install -Dm644 assets/{RULE}\n"
        f"          /app/share/hefesto-dualsense4unix/udev-rules/{RULE}\n",
        encoding="utf-8",
    )
    _semeia_simbolico(tmp_path)
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


def test_regra_fora_do_pkgbuild_falha(fake_repo: Path) -> None:
    """Arch ficava FORA do bloco udev — é por isso que a ausência das 82/83/84
    no PKGBUILD nunca reprovou (o bloco de modprobe.d ao lado já o cobria)."""
    (fake_repo / "packaging" / "arch" / "PKGBUILD").write_text(
        "# sem nenhuma regra\n", encoding="utf-8"
    )
    result = run_check(fake_repo)
    assert result.returncode == 1
    assert f"[FAIL] {RULE}" in result.stdout
    assert "packaging/arch/PKGBUILD" in result.stdout


def test_regra_fora_do_spec_fedora_falha(fake_repo: Path) -> None:
    """Idem para o spec do Fedora — mesma assimetria."""
    (fake_repo / "packaging" / "fedora" / "hefesto-dualsense4unix.spec").write_text(
        "# sem nenhuma regra\n", encoding="utf-8"
    )
    result = run_check(fake_repo)
    assert result.returncode == 1
    assert f"[FAIL] {RULE}" in result.stdout
    assert "packaging/fedora/hefesto-dualsense4unix.spec" in result.stdout


def test_espelho_do_deb_com_glob_proprio_defasado_falha(fake_repo: Path) -> None:
    """O FURO REAL: o build_deb.sh copiava a regra para o diretório VIVO por um
    glob e populava o ESPELHO (/usr/share/.../udev-rules, que o
    install-host-udev.sh prefere e exige COMPLETO) por um segundo glob, que
    parava na 81. O gate antigo só perguntava se "assets/NN-*.rules" aparecia em
    ALGUM lugar do arquivo — o glob do diretório vivo satisfazia e o espelho
    incompleto ficava invisível, enquanto a ativação inteira do .deb abortava.
    """
    (fake_repo / "scripts" / "build_deb.sh").write_text(
        # Destino VIVO cobre a regra...
        'for rules_file in assets/72-*.rules; do\n'
        '    cp "$rules_file" "${STAGING}/usr/lib/udev/rules.d/"\n'
        "done\n"
        # ...e o ESPELHO tem glob PRÓPRIO que a deixa de fora.
        'for rules_file in assets/70-*.rules; do\n'
        '    install -Dm644 "$rules_file" \\\n'
        '        "${STAGING}/usr/share/hefesto-dualsense4unix/udev-rules/"\n'
        "done\n",
        encoding="utf-8",
    )
    result = run_check(fake_repo)
    assert result.returncode == 1
    assert "[FAIL] scripts/build_deb.sh" in result.stdout
    assert "UDEV_RULES_GLOBS" in result.stdout


def test_espelho_do_deb_fora_da_lista_unica_falha(fake_repo: Path) -> None:
    """Com a lista única declarada, o espelho ainda pode ser desligado dela —
    e aí um dos dois destinos volta a andar sozinho. O gate cobra que os DOIS
    laços consumam a MESMA lista."""
    (fake_repo / "scripts" / "build_deb.sh").write_text(
        "UDEV_RULES_GLOBS=(\n"
        "    assets/72-*.rules\n"
        ")\n"
        'for rules_file in "${UDEV_RULES_GLOBS[@]}"; do\n'
        '    cp "$rules_file" "${STAGING}/usr/lib/udev/rules.d/"\n'
        "done\n"
        'for rules_file in assets/70-*.rules; do\n'
        '    install -Dm644 "$rules_file" \\\n'
        '        "${STAGING}/usr/share/hefesto-dualsense4unix/udev-rules/"\n'
        "done\n",
        encoding="utf-8",
    )
    result = run_check(fake_repo)
    assert result.returncode == 1
    assert "[FAIL] scripts/build_deb.sh" in result.stdout
    assert "1x" in result.stdout


def test_regra_so_no_espelho_sem_diretorio_vivo_falha(fake_repo: Path) -> None:
    """Simetria do anterior: sumir com o espelho também reprova."""
    (fake_repo / "scripts" / "build_deb.sh").write_text(
        "UDEV_RULES_GLOBS=(\n"
        "    assets/72-*.rules\n"
        ")\n"
        'for rules_file in "${UDEV_RULES_GLOBS[@]}"; do\n'
        '    cp "$rules_file" "${STAGING}/usr/lib/udev/rules.d/"\n'
        "done\n"
        'for rules_file in "${UDEV_RULES_GLOBS[@]}"; do\n'
        '    cp "$rules_file" "${STAGING}/usr/lib/udev/rules.d/"\n'
        "done\n",
        encoding="utf-8",
    )
    result = run_check(fake_repo)
    assert result.returncode == 1
    assert "espelho udev-rules ausente" in result.stdout


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
    _semeia_simbolico(tmp_path)
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
    _semeia_simbolico(tmp_path)
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


# --- Contencao BT: o TERCEIRO módulo DKMS (hid-playstation) -------------------
#
# Os dois blocos irmãos (hid-nintendo, rtw88-usb) gateiam fontes + helper +
# REMOCAO em todo formato; o hid-playstation nunca ganhou o seu, e o furo era o
# pior dos três: o dkms.conf dele tem AUTOINSTALL="yes", entao ele sobrevivia ao
# `apt remove`/`pacman -R` REGISTRADO, se reconstruia a cada kernel novo e
# vencia o in-tree para sempre. So o %preun do Fedora desregistrava.

_DKMS_REMOVE_PLAYSTATION = 'dkms remove "hefesto-hid-playstation/1.0.0" --all\n'


@pytest.fixture
def fake_repo_dkms_playstation(tmp_path: Path) -> Path:
    repo_root = Path(__file__).resolve().parents[2]
    src_script = repo_root / SCRIPT_REL_PATH
    if not src_script.exists():
        pytest.skip(f"script {SCRIPT_REL_PATH} não encontrado no repo")

    for d in (
        "scripts",
        "assets/dkms/hid-playstation",
        "packaging/arch",
        "packaging/debian",
        "packaging/fedora",
        "flatpak",
    ):
        (tmp_path / d).mkdir(parents=True)

    dst_script = tmp_path / SCRIPT_REL_PATH
    shutil.copy2(src_script, dst_script)
    dst_script.chmod(0o755)

    # Asset que ARMA a seção (a presença basta).
    (tmp_path / "assets" / "dkms" / "hid-playstation" / "dkms.conf").write_text(
        'AUTOINSTALL="yes"\n', encoding="utf-8"
    )
    fontes = "# dkms/hid-playstation + dkms_lib.sh\n"
    (tmp_path / "scripts" / "build_deb.sh").write_text(fontes, encoding="utf-8")
    (tmp_path / "packaging" / "arch" / "PKGBUILD").write_text(fontes, encoding="utf-8")
    (tmp_path / "flatpak" / "fake-dkms.yml").write_text(fontes, encoding="utf-8")
    (tmp_path / "scripts" / "install-host-udev.sh").write_text(
        "dkms_install_patched_module hefesto-hid-playstation\n", encoding="utf-8"
    )
    (tmp_path / "packaging" / "fedora" / "hefesto-dualsense4unix.spec").write_text(
        fontes + _DKMS_REMOVE_PLAYSTATION, encoding="utf-8"
    )
    (tmp_path / "packaging" / "debian" / "prerm").write_text(
        _DKMS_REMOVE_PLAYSTATION, encoding="utf-8"
    )
    (tmp_path / "packaging" / "debian" / "postrm").write_text(
        _DKMS_REMOVE_PLAYSTATION, encoding="utf-8"
    )
    (tmp_path / "packaging" / "arch" / "hefesto-dualsense4unix.install").write_text(
        _DKMS_REMOVE_PLAYSTATION, encoding="utf-8"
    )
    (tmp_path / "uninstall.sh").write_text(
        _DKMS_REMOVE_PLAYSTATION, encoding="utf-8"
    )
    _semeia_simbolico(tmp_path)
    return tmp_path


def test_dkms_playstation_coberto_em_todos_passa(
    fake_repo_dkms_playstation: Path,
) -> None:
    result = run_check(fake_repo_dkms_playstation)
    assert result.returncode == 0, result.stdout
    assert "[ OK ] dkms hid-playstation" in result.stdout


def test_dkms_playstation_sem_asset_pula_sem_falhar(tmp_path: Path) -> None:
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
    secao = result.stdout.split(
        "== paridade da cura DKMS (assets/dkms/hid-playstation", 1
    )
    assert len(secao) == 2, "seção do dkms hid-playstation ausente na saída"
    assert "[FAIL]" not in secao[1].split("== ", 1)[0]


def test_dkms_playstation_sem_remocao_no_prerm_falha(
    fake_repo_dkms_playstation: Path,
) -> None:
    """O falso-verde: prerm do .deb sem `dkms remove` do hid-playstation passava
    (o gate nunca ganhou o terceiro módulo) e o `apt remove` deixava o patchado
    registrado, com AUTOINSTALL=yes, vencendo o in-tree para sempre."""
    (fake_repo_dkms_playstation / "packaging" / "debian" / "prerm").write_text(
        "# nada\n", encoding="utf-8"
    )
    result = run_check(fake_repo_dkms_playstation)
    assert result.returncode == 1
    assert "[FAIL] dkms hid-playstation" in result.stdout
    assert "packaging/debian/prerm(remoção)" in result.stdout


def test_dkms_playstation_sem_remocao_no_postrm_falha(
    fake_repo_dkms_playstation: Path,
) -> None:
    (fake_repo_dkms_playstation / "packaging" / "debian" / "postrm").write_text(
        "# nada\n", encoding="utf-8"
    )
    result = run_check(fake_repo_dkms_playstation)
    assert result.returncode == 1
    assert "packaging/debian/postrm(remoção)" in result.stdout


def test_dkms_playstation_sem_remocao_no_install_arch_falha(
    fake_repo_dkms_playstation: Path,
) -> None:
    (
        fake_repo_dkms_playstation
        / "packaging"
        / "arch"
        / "hefesto-dualsense4unix.install"
    ).write_text("# nada\n", encoding="utf-8")
    result = run_check(fake_repo_dkms_playstation)
    assert result.returncode == 1
    assert "packaging/arch/hefesto-dualsense4unix.install(remoção)" in result.stdout


def test_dkms_playstation_parity_do_repo_real_esta_verde() -> None:
    """No repo REAL, a seção do hid-playstation não pode ter [FAIL]."""
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
        "== paridade da cura DKMS (assets/dkms/hid-playstation", 1
    )
    assert len(secao) == 2, "seção do dkms hid-playstation ausente na saída"
    assert "[FAIL]" not in secao[1].split("== ", 1)[0]


# --- PACKAGING-ICON-NAME-MISMATCH-01: Icon= do .desktop do APLICATIVO ---------
#
# O bloco de Icon= do gate só olhava applet COSMIC: o
# `grep -q '^X-CosmicApplet=true' || continue` PULAVA justamente o .desktop do
# aplicativo principal. Resultado: ele pede `Icon=hefesto` e três dos cinco
# formatos instalavam o PNG como hefesto-dualsense4unix.png — lancador sem
# icone, e nenhum gate reprovava.

_DESKTOP_APP = (
    "[Desktop Entry]\n"
    "Name=Hefesto - Dualsense4Unix\n"
    "Exec=/usr/bin/hefesto-dualsense4unix-gui\n"
    "Icon=hefesto\n"
    "Type=Application\n"
)


@pytest.fixture
def fake_repo_icone(tmp_path: Path) -> Path:
    repo_root = Path(__file__).resolve().parents[2]
    src_script = repo_root / SCRIPT_REL_PATH
    if not src_script.exists():
        pytest.skip(f"script {SCRIPT_REL_PATH} não encontrado no repo")

    for d in ("scripts", "assets", "packaging/arch", "packaging/fedora", "packaging/nix"):
        (tmp_path / d).mkdir(parents=True)
    dst_script = tmp_path / SCRIPT_REL_PATH
    shutil.copy2(src_script, dst_script)
    dst_script.chmod(0o755)

    (tmp_path / "packaging" / "hefesto-dualsense4unix.desktop").write_text(
        _DESKTOP_APP, encoding="utf-8"
    )
    ok = "install -Dm644 icone.png /usr/share/icons/hicolor/256x256/apps/hefesto.png\n"
    (tmp_path / "scripts" / "build_deb.sh").write_text(ok, encoding="utf-8")
    (tmp_path / "packaging" / "arch" / "PKGBUILD").write_text(ok, encoding="utf-8")
    (tmp_path / "packaging" / "fedora" / "hefesto-dualsense4unix.spec").write_text(
        ok, encoding="utf-8"
    )
    (tmp_path / "packaging" / "nix" / "package.nix").write_text(ok, encoding="utf-8")
    _semeia_simbolico(tmp_path)
    return tmp_path


def test_icone_alinhado_em_todos_os_formatos_passa(fake_repo_icone: Path) -> None:
    result = run_check(fake_repo_icone)
    assert result.returncode == 0, result.stdout
    assert "Icon=hefesto casa o PNG de todos os formatos" in result.stdout


def test_icone_com_nome_diferente_no_pkgbuild_falha(fake_repo_icone: Path) -> None:
    """O furo medido: PKGBUILD instalava apps/${pkgname}.png com o .desktop
    pedindo Icon=hefesto."""
    (fake_repo_icone / "packaging" / "arch" / "PKGBUILD").write_text(
        "install -Dm644 icone.png "
        "/usr/share/icons/hicolor/256x256/apps/hefesto-dualsense4unix.png\n",
        encoding="utf-8",
    )
    result = run_check(fake_repo_icone)
    assert result.returncode == 1
    assert "sem apps/hefesto.png" in result.stdout
    assert "packaging/arch/PKGBUILD" in result.stdout


def test_icone_com_nome_diferente_no_spec_falha(fake_repo_icone: Path) -> None:
    (fake_repo_icone / "packaging" / "fedora" / "hefesto-dualsense4unix.spec").write_text(
        "install -Dm644 icone.png "
        "/usr/share/icons/hicolor/256x256/apps/hefesto-dualsense4unix.png\n",
        encoding="utf-8",
    )
    result = run_check(fake_repo_icone)
    assert result.returncode == 1
    assert "packaging/fedora/hefesto-dualsense4unix.spec" in result.stdout


def test_icone_com_nome_diferente_no_nix_falha(fake_repo_icone: Path) -> None:
    (fake_repo_icone / "packaging" / "nix" / "package.nix").write_text(
        "install -Dm644 icone.png "
        "$out/share/icons/hicolor/256x256/apps/hefesto-dualsense4unix.png\n",
        encoding="utf-8",
    )
    result = run_check(fake_repo_icone)
    assert result.returncode == 1
    assert "packaging/nix/package.nix" in result.stdout


def test_icone_do_repo_real_esta_verde() -> None:
    """No repo REAL, o Icon= do .desktop compartilhado casa o PNG dos formatos."""
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
    secao = result.stdout.split("== Icon dos .desktop de aplicativo", 1)
    assert len(secao) == 2, "seção de Icon do aplicativo ausente na saída"
    assert "[FAIL]" not in secao[1].split("== ", 1)[0]


# ---------------------------------------------------------------------------
# A REGRA DE PAR do BlueZ olhava o arquivo ERRADO no Flatpak
#
# Achado de 06/08/2026, MEDIDO: a lista de empacotadores trazia
# `scripts/build_flatpak.sh`, que é um INVÓLUCRO de 120 linhas — chama o
# `flatpak-builder` e não lista arquivo nenhum. Quem declara o conteúdo do
# pacote é o MANIFESTO `flatpak/br.andrefarias.Hefesto.yml`, que não estava em
# lista nenhuma. Como o invólucro não cita `doctor.sh`, o `continue` disparava e
# a regra de PAR NUNCA alcançava o Flatpak: pôr o doctor no manifesto sem o
# `bluez_config.sh` passava VERDE — e o detector empacotado fica CEGO, porque lê
# exclusivamente pelo dono único em `${ROOT_DIR}/scripts/bluez_config.sh`.
# ---------------------------------------------------------------------------

_MANIFESTO = "flatpak/br.andrefarias.Hefesto.yml"


@pytest.fixture
def fake_repo_bluez(tmp_path: Path) -> Path:
    """O mínimo para a seção do BlueZ rodar: o asset que a abre + o manifesto."""
    repo_root = Path(__file__).resolve().parents[2]
    origem = repo_root / SCRIPT_REL_PATH
    if not origem.exists():
        pytest.skip(f"script {SCRIPT_REL_PATH} não encontrado no repo")
    (tmp_path / "scripts").mkdir()
    shutil.copy2(origem, tmp_path / SCRIPT_REL_PATH)
    (tmp_path / "flatpak").mkdir()
    (tmp_path / "assets" / "bluetooth").mkdir(parents=True)
    (tmp_path / "assets" / "bluetooth" / "hefesto-bt.block").write_text(
        "# >>> hefesto bluetooth >>>\n", encoding="utf-8"
    )
    return tmp_path


def _mensagem_de_par(saida: str) -> bool:
    return f"{_MANIFESTO} empacota doctor.sh e deixa bluez_config.sh para trás" in saida


def test_manifesto_flatpak_com_doctor_sem_o_dono_reprova(fake_repo_bluez: Path) -> None:
    """O caso que passava verde: o doctor viaja, o dono único fica para trás."""
    (fake_repo_bluez / _MANIFESTO).write_text(
        "modules:\n"
        "  - name: hefesto\n"
        "    build-commands:\n"
        "      - install -Dm755 scripts/doctor.sh /app/share/hefesto/scripts/doctor.sh\n",
        encoding="utf-8",
    )

    resultado = run_check(fake_repo_bluez)

    assert resultado.returncode == 1
    assert _mensagem_de_par(resultado.stdout), (
        "o portão não alcançou o MANIFESTO do Flatpak — enquanto ele enumerava "
        "o invólucro build_flatpak.sh, um doctor.sh sem o bluez_config.sh no "
        f"pacote passava verde. Saída:\n{resultado.stdout}"
    )


def test_manifesto_flatpak_com_o_par_completo_passa(fake_repo_bluez: Path) -> None:
    """A linha de base: com o dono junto, a regra de PAR se cala."""
    (fake_repo_bluez / _MANIFESTO).write_text(
        "modules:\n"
        "  - name: hefesto\n"
        "    build-commands:\n"
        "      - install -Dm755 scripts/doctor.sh /app/share/hefesto/scripts/doctor.sh\n"
        "      - install -Dm755 scripts/bluez_config.sh"
        " /app/share/hefesto/scripts/bluez_config.sh\n",
        encoding="utf-8",
    )

    resultado = run_check(fake_repo_bluez)

    assert not _mensagem_de_par(resultado.stdout), resultado.stdout


def test_comentario_do_manifesto_nao_satisfaz_a_regra_de_par(
    fake_repo_bluez: Path,
) -> None:
    """Só linha de CÓDIGO conta — o manifesto é YAML e comenta com `#`.

    Foi assim que a primeira versão desta regra passou verde no `build_deb.sh`
    com a cópia arrancada: o próprio comentário que EXPLICA a regra a satisfazia.
    """
    (fake_repo_bluez / _MANIFESTO).write_text(
        "modules:\n"
        "  - name: hefesto\n"
        "    build-commands:\n"
        "      # o scripts/bluez_config.sh viaja junto (não viaja)\n"
        "      - install -Dm755 scripts/doctor.sh /app/share/hefesto/scripts/doctor.sh\n",
        encoding="utf-8",
    )

    resultado = run_check(fake_repo_bluez)

    assert _mensagem_de_par(resultado.stdout), (
        "um COMENTÁRIO no manifesto satisfez a regra de PAR"
    )


# ---------------------------------------------------------------------------
# APPLET-MONOCROMÁTICO-01 (07/08/2026) — o simbólico do painel
# ---------------------------------------------------------------------------


def test_simbolico_ausente_falha(fake_repo: Path) -> None:
    """Sem o arquivo, a bandeja dela cai no ícone colorido — e ninguém vê."""
    (fake_repo / "assets" / "simbolico" / "hefesto-dualsense4unix-symbolic.svg").unlink()
    result = run_check(fake_repo)
    assert result.returncode == 1
    assert "não existe" in result.stdout
    assert "assets/simbolico/hefesto-dualsense4unix-symbolic.svg" in result.stdout


def test_simbolico_do_applet_divergente_falha(fake_repo: Path) -> None:
    """Dois nomes, um desenho só: se divergirem, a mesma aplicação aparece com
    ícones diferentes conforme a superfície — que é o defeito desta sprint."""
    alvo = (
        fake_repo
        / "packaging"
        / "cosmic-applet"
        / "data"
        / "icons"
        / "hicolor"
        / "symbolic"
        / "apps"
        / "com.vitoriamaria.HefestoDualsense4Unix-symbolic.svg"
    )
    alvo.write_text('<svg viewBox="0 0 16 16"><title>outro</title></svg>\n', encoding="utf-8")
    result = run_check(fake_repo)
    assert result.returncode == 1
    assert "DIVERGIRAM" in result.stdout


# ---------------------------------------------------------------------------
# CORRIDA-DO-PIPEFAIL-01 (13/08/2026) — `produtor | grep -q` sob `pipefail`
#
# O comentário no topo do `check_packaging_parity.sh` já contava a história: o
# `grep -q` SAI no primeiro casamento, o produtor a montante morre de SIGPIPE,
# e o `pipefail` faz o pipe INTEIRO devolver 141 mesmo tendo o grep achado o
# que procurava. O veredito pendurado nesse status inverte.
#
# É CORRIDA — e por isso os testes abaixo não torcem por ela: eles a FORÇAM,
# dando ao produtor mais bytes do que cabem no buffer do pipe. Com o produtor
# obrigado a escrever depois da saída do grep, o SIGPIPE deixa de ser sorte e
# vira certeza, na máquina dela como no runner.
# ---------------------------------------------------------------------------

#: Nomes bastantes para estourar com folga o buffer do pipe (4 KiB nesta
#: máquina, 64 KiB no Linux por padrão desde 2.6.11).
_PRODUTOR_LONGO = 4000


def _fake_repo_minimo(tmp_path: Path) -> Path:
    """Repo de mentira só com o script — as seções sem asset ficam quietas."""
    (tmp_path / "scripts").mkdir()
    shutil.copy2(
        Path(__file__).resolve().parents[2] / SCRIPT_REL_PATH,
        tmp_path / SCRIPT_REL_PATH,
    )
    (tmp_path / SCRIPT_REL_PATH).chmod(0o755)
    return tmp_path


def test_icone_de_applet_com_muitos_arquivos_nao_e_acusado_de_faltar(
    tmp_path: Path,
) -> None:
    """O ícone EXISTE; o portão não pode dizer que falta porque o find era longo.

    Sítio curado: o `find ... | grep -q .` da seção de Icon dos applets. O
    veredito está num `if`, então o 141 do pipe cai no `else` e o portão
    imprime "[FAIL] ...: Icon=... sem arquivo de ícone" sobre um diretório que
    tem o ícone milhares de vezes.
    """
    repo = _fake_repo_minimo(tmp_path)
    applet = repo / "packaging" / "corrida-applet"
    apps = applet / "data" / "icons" / "hicolor" / "scalable" / "apps"
    apps.mkdir(parents=True)
    (applet / "corrida.desktop").write_text(
        "[Desktop Entry]\n"
        "X-CosmicApplet=true\n"
        "Icon=hefesto-corrida-do-pipefail\n",
        encoding="utf-8",
    )
    for n in range(_PRODUTOR_LONGO):
        (apps / f"hefesto-corrida-do-pipefail.{n:05d}.svg").write_text("<svg/>\n")

    result = run_check(repo)
    assert "sem arquivo de ícone" not in result.stdout, (
        "o portão acusou um ícone que existe 4000 vezes: o `find` voltou para "
        f"dentro de um pipe com `grep -q`.\nsaída:\n{result.stdout}"
    )
    assert "Icon=hefesto-corrida-do-pipefail tem arquivo versionado" in result.stdout


def test_bluez_com_empacotador_longo_nao_acusa_par_desfeito(tmp_path: Path) -> None:
    """Controle: com o par inteiro, o portão cala — antes e depois da cura.

    MEDIDO em 13/08/2026, e a medição corrigiu a expectativa: neste sítio a
    corrida NÃO produz falso positivo. O primeiro `grep -qF` da dupla termina
    em `|| continue`, então o 141 do pipe faz o laço PULAR o empacotador
    inteiro — a checagem do par nunca chega a rodar. Silêncio, não alarme.

    Por isso este teste é o controle e não a mordida: ele passa dos dois lados.
    Quem morde é o gêmeo logo abaixo, que exige a acusação quando ela é devida.
    """
    repo = _fake_repo_minimo(tmp_path)
    (repo / "assets" / "bluetooth").mkdir(parents=True)
    (repo / "assets" / "bluetooth" / "hefesto-bt.block").write_text("bloco\n")
    enchimento = "\n".join(
        f"echo linha-de-enchimento-numero-{n:05d}" for n in range(_PRODUTOR_LONGO)
    )
    (repo / "scripts" / "build_deb.sh").write_text(
        "bash scripts/doctor.sh\n"
        "bash scripts/bluez_config.sh aplicar\n" + enchimento + "\n",
        encoding="utf-8",
    )

    result = run_check(repo)
    assert "deixa bluez_config.sh para trás" not in result.stdout, (
        "o portão acusou o empacotador de esquecer o bluez_config.sh, que está "
        f"na segunda linha dele.\nsaída:\n{result.stdout}"
    )


def test_bluez_empacotador_longo_que_esquece_o_dono_continua_reprovando(
    tmp_path: Path,
) -> None:
    """O outro lado da régua: sem o `bluez_config.sh`, a acusação tem de vir.

    Sem este teste a cura acima seria indistinguível de desligar a checagem —
    um portão que nunca acusa também "não dá falso positivo".
    """
    repo = _fake_repo_minimo(tmp_path)
    (repo / "assets" / "bluetooth").mkdir(parents=True)
    (repo / "assets" / "bluetooth" / "hefesto-bt.block").write_text("bloco\n")
    enchimento = "\n".join(
        f"echo linha-de-enchimento-numero-{n:05d}" for n in range(_PRODUTOR_LONGO)
    )
    (repo / "scripts" / "build_deb.sh").write_text(
        "bash scripts/doctor.sh\n" + enchimento + "\n", encoding="utf-8"
    )

    result = run_check(repo)
    assert "deixa bluez_config.sh para trás" in result.stdout, (
        "o empacotador leva o doctor.sh e NÃO leva o bluez_config.sh, e o "
        f"portão calou.\nsaída:\n{result.stdout}"
    )


def test_nenhum_produtor_entra_num_pipe_com_grep_q() -> None:
    """A contagem que o comentário do topo promete: ZERO `| grep -q` no código.

    Estrutural de propósito. Os dois testes acima forçam a corrida em DOIS dos
    onze sítios; forçá-la nos onze exigiria montar onze repos de mentira, e o
    que importa é a FORMA — `| grep -q` é a armadilha, esteja ela onde estiver.
    Comentário citando a forma não conta: o portão não pode reprovar a própria
    explicação de por que ela é proibida.
    """
    alvo = Path(__file__).resolve().parents[2] / SCRIPT_REL_PATH
    culpadas = [
        (n, linha)
        for n, linha in enumerate(alvo.read_text(encoding="utf-8").splitlines(), 1)
        if "| grep -q" in linha and not linha.lstrip().startswith("#")
    ]
    assert not culpadas, (
        "voltou `produtor | grep -q` ao check_packaging_parity.sh:\n"
        + "".join(f"  :{n}  {linha.strip()}\n" for n, linha in culpadas)
        + "Use here-string: guarde o produtor numa variável e faça "
        "`grep -q ... <<< \"${var}\"`. O porquê está no comentário "
        "CORRIDA-DO-PIPEFAIL-01, no topo do arquivo."
    )
