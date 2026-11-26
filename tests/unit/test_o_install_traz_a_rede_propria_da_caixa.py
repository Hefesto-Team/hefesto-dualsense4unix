"""O install e os pacotes trazem a rede própria da caixa das extensões.

O-INSTALL-TRAZ-A-REDE-PROPRIA-DA-CAIXA-01. A caixa das extensões só tem espaço de rede próprio com o
`pasta` (pacote `passt`), e a extensão com Bluetooth só abre com o `xdg-dbus-proxy`. Nenhum caminho
de instalação pedia os dois: a caixa com rede ficava no espaço de rede do serviço, com os soquetes
da casa à vista. O censo do `install.sh` e cada pacote de distribuição passam a pedir os três
programas da caixa (`bubblewrap`, `passt`, `xdg-dbus-proxy`).
"""
from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
INSTALL = RAIZ / "install.sh"
SUPERVISOR = RAIZ / "src" / "hefesto_dualsense4unix" / "mods" / "supervisor.py"
PKGBUILD = RAIZ / "packaging" / "arch" / "PKGBUILD"
CONTROL = RAIZ / "packaging" / "debian" / "control"
SPEC = RAIZ / "packaging" / "fedora" / "hefesto-dualsense4unix.spec"
NIX = RAIZ / "packaging" / "nix" / "package.nix"
BASH = shutil.which("bash") or "bash"

OS_TRES = ("bubblewrap", "passt", "xdg-dbus-proxy")
LINHAS_DO_CENSO = {
    "passt": (
        "passt|importante|cmd:pasta|as extensões com rede alcançam os serviços deste computador"
    ),
    "xdg-dbus-proxy": (
        "xdg-dbus-proxy|importante|cmd:xdg-dbus-proxy|a extensão com Bluetooth não abre"
    ),
}


def _funcao(nome: str) -> str:
    texto = INSTALL.read_text(encoding="utf-8")
    inicio = re.search(rf"^{re.escape(nome)}\(\) \{{\n", texto, re.MULTILINE)
    assert inicio is not None, f"{nome}() sumiu do install.sh"
    fim = re.search(r"^\}\n", texto[inicio.end():], re.MULTILINE)
    assert fim is not None
    return texto[inicio.start():inicio.end() + fim.end()]


def _censo() -> list[str]:
    texto = INSTALL.read_text(encoding="utf-8")
    achado = re.search(r"_DEPS_DE_SISTEMA=\((.*?)\n\)", texto, re.S)
    assert achado, "o censo _DEPS_DE_SISTEMA sumiu do install.sh"
    return re.findall(r'"([^"]*\|[^"]*)"', achado.group(1))


@pytest.mark.parametrize("familia", ["apt", "dnf", "pacman"])
@pytest.mark.parametrize("canonico", ["passt", "xdg-dbus-proxy"])
def test_o_install_da_nome_ao_pacote_nas_tres_familias(familia: str, canonico: str) -> None:
    """A tabela de nomes conhece `passt` e `xdg-dbus-proxy` em apt, dnf e pacman."""
    saida = subprocess.run(
        [BASH, "-c", f"{_funcao('_pkg_nome')}\n_pkg_nome {canonico} {familia}"],
        capture_output=True, text=True, check=True,
    ).stdout.strip()
    assert saida == canonico


@pytest.mark.parametrize("canonico", ["passt", "xdg-dbus-proxy"])
def test_o_censo_cobra_o_programa_com_a_frase_de_quem_usa(canonico: str) -> None:
    """A linha do censo é «importante», confere o comando que o produto procura e diz o custo."""
    assert LINHAS_DO_CENSO[canonico] in _censo()


def test_o_comando_que_o_censo_confere_e_o_que_o_produto_procura() -> None:
    """`cmd:pasta` e `cmd:xdg-dbus-proxy` são os nomes que o supervisor procura no PATH."""
    codigo = SUPERVISOR.read_text(encoding="utf-8")
    assert 'shutil.which("pasta")' in codigo
    assert 'shutil.which("xdg-dbus-proxy")' in codigo
    comandos = {linha.split("|")[2] for linha in _censo()}
    assert {"cmd:bwrap", "cmd:pasta", "cmd:xdg-dbus-proxy"} <= comandos


@pytest.mark.parametrize("comando", ["pasta", "xdg-dbus-proxy"])
def test_o_censo_ve_a_falta_e_a_presenca_do_comando(tmp_path: Path, comando: str) -> None:
    """Sem o comando no PATH o censo o dá por faltando; com ele, presente."""
    corpo = f'VENV_DIR=/naoexiste\n{_funcao("_dep_presente")}\n_dep_presente cmd:{comando}\n'
    vazio = tmp_path / "vazio"
    vazio.mkdir()
    falta = subprocess.run([BASH, "-c", corpo], capture_output=True, env={"PATH": str(vazio)})
    assert falta.returncode != 0
    (vazio / comando).symlink_to("/bin/true")
    veio = subprocess.run([BASH, "-c", corpo], capture_output=True, env={"PATH": str(vazio)})
    assert veio.returncode == 0


def _depends_do_arch() -> str:
    texto = PKGBUILD.read_text(encoding="utf-8")
    return re.search(r"^depends=\((.*?)^\)", texto, re.M | re.S).group(1)


def _pedidos_do_deb() -> str:
    texto = CONTROL.read_text(encoding="utf-8")
    campos = re.findall(r"^(?:Depends|Recommends):.*?(?=^\S)", texto, re.M | re.S)
    return "\n".join(campos)


@pytest.mark.parametrize("programa", OS_TRES)
def test_cada_pacote_de_distribuicao_pede_os_tres_programas_da_caixa(programa: str) -> None:
    """Arch, deb, RPM e Nix levam `bubblewrap`, `passt` e `xdg-dbus-proxy`."""
    assert f"'{programa}'" in _depends_do_arch(), "PKGBUILD"
    assert re.search(rf"\b{re.escape(programa)}\b", _pedidos_do_deb()), "debian/control"
    assert re.search(
        rf"^Requires:\s+{re.escape(programa)}\s*$", SPEC.read_text(encoding="utf-8"), re.M
    ), "spec"
    nix = NIX.read_text(encoding="utf-8")
    assert re.search(rf"^, {re.escape(programa)}$", nix, re.M), "argumento do package.nix"
    assert re.search(
        r'--suffix PATH : "\$\{lib\.makeBinPath \[ [^\]]*\b' + re.escape(programa) + r"\b", nix
    ), "PATH do wrapper do Nix"


def test_a_falta_do_passt_no_deb_nao_impede_a_instalacao() -> None:
    """No deb o `passt` e o `xdg-dbus-proxy` são recomendados: a distro sem eles instala igual."""
    texto = CONTROL.read_text(encoding="utf-8")
    depende = re.search(r"^Depends:.*?(?=^\S)", texto, re.M | re.S).group(0)
    assert "bubblewrap" in depende
    assert "passt" not in depende and "xdg-dbus-proxy" not in depende
