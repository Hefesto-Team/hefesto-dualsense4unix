"""Testes do caminho de ATIVACAO dos pacotes (.deb, Arch, Fedora, Nix).

A leva de restauro de 2026-07-29 achou o caminho de ativação do .deb MORTO e
três pacotes incompletos. Cada teste aqui pina uma dessas curas:

(A) BUG-DEB-MIRROR-RULES-INCOMPLETO-01 — o build_deb.sh copiava as regras udev
    para DOIS destinos: o diretório VIVO (/usr/lib/udev/rules.d) e o ESPELHO
    (/usr/share/hefesto-dualsense4unix/udev-rules), que o install-host-udev.sh
    PREFERE como origem. O espelho tinha um glob próprio que parava na 81, e o
    pre-flight do helper exige TODAS as regras com exit 1 -> o postinst mandava
    rodar o helper e ele ABORTAVA antes de tudo: usuário de .deb ficava sem o
    grupo hefesto, sem broker e sem nenhum dos três módulos DKMS.
(D) O TERCEIRO módulo DKMS (hid-playstation) sobrevivia ao apt remove/pacman -R
    registrado — e o dkms.conf dele tem AUTOINSTALL="yes", logo se reconstruía a
    cada kernel novo e vencia o in-tree para sempre.
(E) O spec do Fedora não compilava: instalava dkms/hid-playstation/ e não o
    listava em %files (rpmbuild aborta com "Installed (but unpackaged) file(s)").
(F) O package.nix instalava as regras 73/74, REMOVIDAS do repo em 2026-07-18.
(G) PACKAGING-ICON-NAME-MISMATCH-01 — o .desktop compartilhado pede
    Icon=hefesto e três dos cinco formatos instalavam o PNG com outro nome.
(H) PACKAGING-EPOCH-DOWNGRADE-01 — a numeração voltou de 4.0.0 para 0.1.0 em
    2026-07-24; sem epoch, apt/dnf/pacman tratam 0.3.0 como DOWNGRADE e RECUSAM
    o upgrade.
(I) O prerm do .deb matava 'hefesto\\.app\\.main', módulo que não existe desde o
    rebrand da v3.0.0 (hefesto_dualsense4unix.app.main).
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]

BUILD_DEB = ROOT / "scripts" / "build_deb.sh"
INSTALL_HOST_UDEV = ROOT / "scripts" / "install-host-udev.sh"
PKGBUILD = ROOT / "packaging" / "arch" / "PKGBUILD"
ARCH_INSTALL = ROOT / "packaging" / "arch" / "hefesto-dualsense4unix.install"
SPEC = ROOT / "packaging" / "fedora" / "hefesto-dualsense4unix.spec"
NIX = ROOT / "packaging" / "nix" / "package.nix"
DEB_CONTROL = ROOT / "packaging" / "debian" / "control"
DEB_PRERM = ROOT / "packaging" / "debian" / "prerm"
DEB_POSTRM = ROOT / "packaging" / "debian" / "postrm"
DESKTOP = ROOT / "packaging" / "hefesto-dualsense4unix.desktop"

MIRROR_DIR = "usr/share/hefesto-dualsense4unix/udev-rules"


def _ler(path: Path) -> str:
    if not path.is_file():
        pytest.skip(f"{path.relative_to(ROOT)} ausente neste checkout")
    return path.read_text(encoding="utf-8")


def _regras_exigidas_pelo_helper() -> list[str]:
    """Nomes do array RULES=() do install-host-udev.sh (o pre-flight com exit 1)."""
    texto = _ler(INSTALL_HOST_UDEV)
    bloco = re.search(r"^RULES=\((.*?)^\)", texto, re.MULTILINE | re.DOTALL)
    assert bloco, "array RULES=() não encontrado no install-host-udev.sh"
    nomes = re.findall(r'"([0-9]{2}-[^"]+\.rules)"', bloco.group(1))
    assert nomes, "nenhuma regra no array RULES=()"
    return nomes


def _globs_do_build_deb() -> list[str]:
    """Itens da lista ÚNICA UDEV_RULES_GLOBS=() do build_deb.sh."""
    texto = _ler(BUILD_DEB)
    bloco = re.search(
        r"^UDEV_RULES_GLOBS=\((.*?)^\)", texto, re.MULTILINE | re.DOTALL
    )
    assert bloco, (
        "build_deb.sh sem a lista única UDEV_RULES_GLOBS=() — os dois destinos "
        "(diretório vivo + espelho) tem de sair da MESMA lista"
    )
    return re.findall(r"(assets/\S+\.rules)", bloco.group(1))


# --- (A) o espelho do .deb recebe as MESMAS regras que o diretório vivo -------


def test_espelho_do_deb_cobre_todas_as_regras_do_preflight() -> None:
    """Cada regra que o install-host-udev.sh EXIGE tem de nascer da lista única
    do build_deb.sh — senão o espelho fica incompleto e o helper aborta,
    derrubando a ativação inteira do .deb (grupo, broker e os três DKMS)."""
    exigidas = set(_regras_exigidas_pelo_helper())
    empacotadas: set[str] = set()
    for glob in _globs_do_build_deb():
        empacotadas.update(p.name for p in ROOT.glob(glob))
    faltando = sorted(exigidas - empacotadas)
    assert not faltando, (
        "regras exigidas pelo pre-flight do install-host-udev.sh e ausentes da "
        f"lista do build_deb.sh: {faltando}"
    )


def test_build_deb_popula_os_dois_destinos_da_mesma_lista() -> None:
    """O diretório vivo E o espelho iteram UDEV_RULES_GLOBS — uma fonte de
    verdade. Foi a divergência entre os dois globs que matou a ativação."""
    texto = _ler(BUILD_DEB)
    usos = texto.count("UDEV_RULES_GLOBS[@]")
    assert usos >= 2, (
        f"UDEV_RULES_GLOBS usada {usos}x — esperado >= 2 (diretório vivo + espelho)"
    )
    assert "usr/lib/udev/rules.d" in texto
    assert MIRROR_DIR in texto
    # O espelho não pode ter glob próprio: nenhuma linha `for rules_file in
    # assets/...` fora da lista única.
    lacos_com_glob_literal = [
        linha
        for linha in texto.splitlines()
        if linha.lstrip().startswith("for rules_file in")
        and "UDEV_RULES_GLOBS" not in linha
    ]
    assert not lacos_com_glob_literal, (
        f"laço de regras com glob próprio (fora da lista única): {lacos_com_glob_literal}"
    )


# --- (C) as 82/83/84 nos formatos que ficavam fora do gate -------------------


@pytest.mark.parametrize(
    "regra",
    [
        "82-nintendo-pro-nosniff.rules",
        "83-hefesto-bond-snapshot.rules",
        "84-nintendo-pro-variant.rules",
    ],
)
def test_regras_novas_no_pkgbuild_e_no_spec(regra: str) -> None:
    assert regra in _ler(PKGBUILD), f"{regra} ausente do PKGBUILD"
    spec = _ler(SPEC)
    assert f"assets/{regra}" in spec, f"{regra} não instalada pelo spec"
    assert f"%{{_udevrulesdir}}/{regra}" in spec, f"{regra} fora da seção %files"


# --- (D) o terceiro módulo DKMS morre no remove de TODO formato ---------------


@pytest.mark.parametrize(
    "hook", [DEB_PRERM, DEB_POSTRM, ARCH_INSTALL, SPEC], ids=lambda p: p.name
)
def test_remocao_desregistra_o_hid_playstation(hook: Path) -> None:
    """AUTOINSTALL="yes" no dkms.conf: sem o `dkms remove` em cada hook de
    pacote, o patchado se reconstrói a cada kernel e vence o in-tree para
    sempre numa máquina que removeu o app."""
    texto = _ler(hook)
    assert "hefesto-hid-playstation" in texto, (
        f"{hook.name} não menciona o módulo hefesto-hid-playstation"
    )
    assert re.search(
        r'dkms remove "hefesto-hid-playstation/', texto
    ), f"{hook.name} não desregistra o hefesto-hid-playstation do DKMS"


# --- (E) o spec do Fedora compila (nada instalado fora de %files) -------------


def test_spec_lista_o_dkms_hid_playstation_em_files() -> None:
    spec = _ler(SPEC)
    assert "dkms/hid-playstation" in spec
    _corpo, _, files = spec.partition("\n%files")
    assert files, "seção %files não encontrada no spec"
    assert "%{_datadir}/%{app_id}/dkms/hid-playstation/" in files, (
        "dkms/hid-playstation instalado e NAO empacotado — com "
        "%_unpackaged_files_terminate_build no default o rpmbuild aborta"
    )


# --- (F) o package.nix não instala regra que não existe mais ------------------


def test_nix_instala_apenas_regras_que_existem() -> None:
    nix = _ler(NIX)
    referidas = sorted(set(re.findall(r"assets/([0-9]{2}-\S+\.rules)", nix)))
    assert referidas, "package.nix não instala nenhuma regra udev"
    ausentes = [r for r in referidas if not (ROOT / "assets" / r).is_file()]
    assert not ausentes, (
        f"package.nix instala regra inexistente em assets/: {ausentes} "
        "(as 73/74 foram removidas do repo em 2026-07-18)"
    )


# --- (G) o nome do arquivo de icone casa o Icon= do .desktop -----------------


@pytest.mark.parametrize(
    "formato", [BUILD_DEB, PKGBUILD, SPEC, NIX], ids=lambda p: p.name
)
def test_icone_instalado_casa_o_desktop(formato: Path) -> None:
    desktop = _ler(DESKTOP)
    icone = re.search(r"^Icon=(\S+)$", desktop, re.MULTILINE)
    assert icone, "o .desktop compartilhado não tem linha Icon="
    esperado = f"apps/{icone.group(1)}.png"
    assert esperado in _ler(formato), (
        f"{formato.name} não instala {esperado} — o lancador fica SEM ICONE"
    )


# --- (H) epoch em apt, dnf e pacman ------------------------------------------


def test_deb_compoe_version_com_epoch() -> None:
    """No mundo Debian o epoch vive DENTRO do campo Version (`1:0.3.0`), e não
    pode ficar hardcoded no control (o check_version_consistency.py cobra
    `Version:` == versão canonica do pyproject). Por isso ele e declarado em
    campo próprio e COMPOSTO pelo build_deb.sh."""
    control = _ler(DEB_CONTROL)
    epoch = re.search(r"^X-Hefesto-Deb-Epoch:\s*(\d+)$", control, re.MULTILINE)
    assert epoch, "packaging/debian/control sem X-Hefesto-Deb-Epoch"
    assert int(epoch.group(1)) >= 1, "epoch tem de ser >= 1 para vencer a serie 4.0"
    deb = _ler(BUILD_DEB)
    assert "X-Hefesto-Deb-Epoch" in deb, "build_deb.sh ignora o epoch do control"
    assert 'Version: ${DEB_EPOCH}:${VERSION}' in deb, (
        "build_deb.sh não compoe `Version: <epoch>:<versão>` — sem isso o apt "
        "RECUSA o upgrade de qualquer 3.x/4.0 instalado"
    )
    assert "/^X-Hefesto-Deb-Epoch:/d" in deb, (
        "o campo auxiliar tem de sair do control final (o dpkg não o conhece)"
    )


def test_pkgbuild_tem_epoch() -> None:
    assert re.search(r"^epoch=[1-9]", _ler(PKGBUILD), re.MULTILINE), (
        "PKGBUILD sem epoch= — para o vercmp do pacman 0.3.0 e downgrade de 3.x"
    )


def test_spec_tem_epoch_e_changelog_coerente() -> None:
    spec = _ler(SPEC)
    epoch = re.search(r"^Epoch:\s*([1-9]\d*)$", spec, re.MULTILINE)
    assert epoch, "spec sem linha Epoch: — o dnf RECUSA o upgrade"
    versao_spec = re.search(r"^Version:\s*(\S+)$", spec, re.MULTILINE)
    assert versao_spec, "spec sem linha Version:"
    topo = re.search(r"^%changelog\n\*[^\n]*?-\s*(\S+)\s*$", spec, re.MULTILINE)
    assert topo, "entrada mais recente do %changelog não encontrada"
    esperado = f"{epoch.group(1)}:{versao_spec.group(1)}-"
    assert topo.group(1).startswith(esperado), (
        f"topo do %changelog em '{topo.group(1)}', esperado começar em "
        f"'{esperado}' (estava em 3.4.0-1, ACIMA do Version do próprio arquivo)"
    )


# --- (I) o prerm mata o módulo que existe de verdade -------------------------


def test_prerm_usa_o_nome_real_do_modulo_da_gui() -> None:
    """O padrão era 'hefesto\\.app\\.main' e NUNCA casou — o módulo se chama
    hefesto_dualsense4unix.app.main desde o rebrand da v3.0.0."""
    prerm = _ler(DEB_PRERM)
    assert r"hefesto_dualsense4unix\.app\.main" in prerm, (
        "prerm não sinaliza o módulo real da GUI"
    )
    padroes_pkill = re.findall(r"pkill\s+-TERM\s+-f\s+'([^']+)'", prerm)
    assert padroes_pkill, "nenhum pkill -TERM -f no prerm"
    for padrao_pkill in padroes_pkill:
        alvo = padrao_pkill.replace("\\", "")
        assert alvo in (
            "hefesto_dualsense4unix.app.main",
            "hefesto-dualsense4unix daemon start",
        ), f"prerm mata padrão que não casa processo nenhum: {padrao_pkill}"
