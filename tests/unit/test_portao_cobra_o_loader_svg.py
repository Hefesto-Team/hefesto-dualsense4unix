"""LOADER-SVG-01 — o portão cobra o loader SVG em TODA forma de empacotamento.

A leva de 19/08/2026 pôs o `librsvg` nos empacotamentos, e a conferência
combinada foi *"rode o `check_packaging_parity.sh` e veja se os três
concordam"*. O portão respondeu VERDE — e estava CEGO: não havia uma linha
sobre `librsvg` naquele arquivo. **Verde por silêncio é a pior resposta que um
portão dá**, porque quem perguntou vai embora achando que mediu.

O que a seção segura, e por que cada peça está lá:

* o sintoma NÃO aponta para a causa — sem o loader,
  ``GdkPixbuf.Pixbuf.new_from_file_at_scale`` devolve ``None`` em SILÊNCIO, o
  ícone some da bandeja e os 38 glifos da interface caem junto, sem uma linha de
  erro no log (BUG-TRAY-ICONE-INVISIVEL-01);
* os NOMES DIVERGEM por família (``librsvg2-common`` no Debian, ``librsvg2`` no
  Fedora, ``librsvg`` no Arch/Nix), e o vizinho de nome parecido
  (``librsvg2-bin``/``librsvg2-tools``) é o ``rsvg-convert``, ferramenta de
  BUILD — o errado em todos eles;
* a PROSA não pode satisfazer o portão. Os quatro arquivos EXPLICAM a armadilha
  de nome em texto corrido, e a ``Description:`` do ``debian/control`` não é
  comentário: um portão que procurasse a palavra no arquivo inteiro passaria
  verde com a dependência arrancada. É a mesma armadilha que a seção do teclado
  na tela já pagou uma vez.

Técnica: a dos irmãos deste portão (`test_portao_reprova_irmao_sem_carona.py`)
— repo de mentira em ``tmp_path``, o script REAL copiado para dentro, e o
recorte da seção pela linha de cabeçalho, para não confundir um ``[FAIL]``
desta seção com o de qualquer outra.
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

REPO_RAIZ = Path(__file__).resolve().parents[2]
SCRIPT_REL_PATH = "scripts/check_packaging_parity.sh"
CABECALHO = "== loader SVG do gdk-pixbuf"

#: O arquivo que CRIA a promessa: enquanto o produto desenhar SVG em execução,
#: todo formato tem de declarar o loader.
PROMESSA_REL = "src/hefesto_dualsense4unix/gui/widgets/button_glyph.py"

CONTROL_BOM = """\
Package: hefesto-dualsense4unix
Depends: python3 (>= 3.10), python3-gi,
         libhidapi-hidraw0,
         librsvg2-common
Recommends: wvkbd | onboard
Description: Gerenciador DualSense para Linux
 librsvg2-common é o LOADER SVG do gdk-pixbuf, e por isso é Depends e não
 Recommends: sem ele o ícone da bandeja some. ARMADILHA DE NOME: o librsvg2-bin
 é o rsvg-convert, ferramenta de BUILD.
"""

SPEC_BOM = """\
Name:           hefesto-dualsense4unix
# ARMADILHA DE NOME: no Fedora quem entrega o módulo é o librsvg2.
Requires:       librsvg2
Requires:       python3-pydantic >= 2.0
"""

PKGBUILD_BOM = """\
pkgname=hefesto-dualsense4unix
depends=(
    'hidapi'
    # ARMADILHA DE NOME: no Arch o pacote librsvg traz as duas coisas.
    'librsvg'
)
"""

NIX_BOM = """\
# Paridade com librsvg2-common (.deb), librsvg2 (RPM) e librsvg (Arch).
{ lib, gtk3, librsvg }:
stdenv.mkDerivation {
  buildInputs = [
    gtk3
    librsvg
  ];
}
"""

FLATPAK_BOM = """\
app-id: br.andrefarias.Hefesto
runtime: org.gnome.Platform
runtime-version: "47"
sdk: org.gnome.Sdk
"""

INSTALL_BOM = """\
#!/usr/bin/env bash
_pkg_nome() {
    case "${_canon}" in
        svg-loader)
            _apt="librsvg2-common";   _dnf="librsvg2"
            _pacman="librsvg" ;;
    esac
}
_DEPS_DE_SISTEMA=(
    "svg-loader|obrigatoria|svg|o ícone da bandeja some e todo glifo SVG da interface cai junto"
)
"""


def _semeia_simbolico(raiz: Path) -> None:
    """O par de simbólicos que a seção do applet exige — sem ele a saída
    começaria a acusar numa seção que não é o alvo daqui."""
    desenho = '<svg viewBox="0 0 16 16"><title>fake</title></svg>\n'
    for alvo in (
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
    ):
        alvo.parent.mkdir(parents=True, exist_ok=True)
        alvo.write_text(desenho, encoding="utf-8")


def escreve(repo: Path, rel: str, conteudo: str) -> None:
    alvo = repo / rel
    alvo.parent.mkdir(parents=True, exist_ok=True)
    alvo.write_text(conteudo, encoding="utf-8")


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """Repo de mentira COMPLETO do ponto de vista desta seção: a promessa viva
    e os cinco declarantes em ordem. Cada teste arranca UMA peça."""
    src_script = REPO_RAIZ / SCRIPT_REL_PATH
    if not src_script.exists():
        pytest.skip(f"script {SCRIPT_REL_PATH} não encontrado no repo")

    (tmp_path / "scripts").mkdir()
    dst = tmp_path / SCRIPT_REL_PATH
    shutil.copy2(src_script, dst)
    dst.chmod(0o755)

    escreve(tmp_path, "uninstall.sh", "# removedor de mentira\n")
    escreve(tmp_path, "install.sh", INSTALL_BOM)
    escreve(
        tmp_path,
        PROMESSA_REL,
        "pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(caminho, 24, 24, True)\n",
    )
    escreve(tmp_path, "packaging/debian/control", CONTROL_BOM)
    escreve(tmp_path, "packaging/fedora/hefesto-dualsense4unix.spec", SPEC_BOM)
    escreve(tmp_path, "packaging/arch/PKGBUILD", PKGBUILD_BOM)
    escreve(tmp_path, "packaging/nix/package.nix", NIX_BOM)
    escreve(tmp_path, "flatpak/br.andrefarias.Hefesto.yml", FLATPAK_BOM)
    # A lacuna declarada aponta para este arquivo; sem ele a seção reprovaria
    # por "lacuna que já não vale", que é outro assunto.
    escreve(tmp_path, "scripts/build_appimage_gui.sh", "# empacotador de mentira\n")
    _semeia_simbolico(tmp_path)
    return tmp_path


def roda(repo: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", SCRIPT_REL_PATH],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
    )


def secao(saida: str) -> str:
    partes = saida.split(CABECALHO, 1)
    assert len(partes) == 2, f"seção ausente na saída do script:\n{saida}"
    return partes[1].split("─", 1)[0]


class TestASecaoAprovaQuemEstaCerto:
    def test_com_os_cinco_declarantes_a_secao_passa(self, repo: Path) -> None:
        """Um portão que grita com quem está certo é desligado na primeira
        semana. Este caso é o que impede isso."""
        s = secao(roda(repo).stdout)
        assert "[ OK ]" in s, s
        assert "[FAIL]" not in s, s

    def test_sem_a_promessa_a_secao_cala(self, repo: Path) -> None:
        """A âncora é a promessa, não o pacote: se o produto deixar de desenhar
        SVG em execução, cobrar o loader seria cobrar por nada."""
        (repo / PROMESSA_REL).unlink()
        s = secao(roda(repo).stdout)
        assert "nada a checar" in s, s
        assert "[FAIL]" not in s, s


class TestASecaoMorde:
    def test_deb_sem_librsvg2_common_no_depends(self, repo: Path) -> None:
        """E a PROSA da Description fica de pé — é o caso que engana."""
        escreve(
            repo,
            "packaging/debian/control",
            CONTROL_BOM.replace("         librsvg2-common\n", ""),
        )
        s = secao(roda(repo).stdout)
        assert "[FAIL]" in s and "debian/control" in s, s
        assert "Description NÃO instala nada" in s, s

    def test_deb_com_o_pacote_de_build_no_lugar_do_de_execucao(
        self, repo: Path
    ) -> None:
        """`librsvg2-bin` é o `rsvg-convert`. Instalá-lo não desenha um pixel."""
        escreve(
            repo,
            "packaging/debian/control",
            CONTROL_BOM.replace("librsvg2-common\n", "librsvg2-bin\n"),
        )
        s = secao(roda(repo).stdout)
        assert "[FAIL]" in s and "debian/control" in s, s

    def test_spec_sem_o_requires(self, repo: Path) -> None:
        escreve(
            repo,
            "packaging/fedora/hefesto-dualsense4unix.spec",
            SPEC_BOM.replace("Requires:       librsvg2\n", ""),
        )
        s = secao(roda(repo).stdout)
        assert "[FAIL]" in s and ".spec" in s, s

    def test_pkgbuild_sem_o_librsvg(self, repo: Path) -> None:
        escreve(repo, "packaging/arch/PKGBUILD", PKGBUILD_BOM.replace("    'librsvg'\n", ""))
        s = secao(roda(repo).stdout)
        assert "[FAIL]" in s and "PKGBUILD" in s, s

    def test_nix_sem_o_librsvg_nos_build_inputs(self, repo: Path) -> None:
        """O comentário do topo cita `librsvg` três vezes e continua lá: só o
        `buildInputs` monta o `GDK_PIXBUF_MODULE_FILE` do wrapper."""
        escreve(repo, "packaging/nix/package.nix", NIX_BOM.replace("    librsvg\n", ""))
        s = secao(roda(repo).stdout)
        assert "[FAIL]" in s and "package.nix" in s, s

    def test_flatpak_que_troca_de_runtime_perde_a_isencao(self, repo: Path) -> None:
        """O Flatpak não declara porque o `org.gnome.Platform` já traz o loader.
        Trocar de runtime derruba a premissa, e a isenção morre junto."""
        escreve(
            repo,
            "flatpak/br.andrefarias.Hefesto.yml",
            FLATPAK_BOM.replace("org.gnome.Platform", "org.freedesktop.Platform"),
        )
        s = secao(roda(repo).stdout)
        assert "[FAIL]" in s and "isenção caducou" in s, s

    def test_flatpak_de_outro_runtime_que_bundla_continua_valendo(
        self, repo: Path
    ) -> None:
        """Trocar de runtime não é proibido — ficar sem o loader é."""
        escreve(
            repo,
            "flatpak/br.andrefarias.Hefesto.yml",
            FLATPAK_BOM.replace("org.gnome.Platform", "org.freedesktop.Platform")
            + "modules:\n  - name: librsvg\n",
        )
        s = secao(roda(repo).stdout)
        assert "[FAIL]" not in s, s

    def test_install_que_rebaixa_o_loader_a_importante(self, repo: Path) -> None:
        """`importante` só avisa e segue. Sem o loader a interface não desenha —
        isso é `obrigatoria`, e a diferença é quem morre: o passo ou a tela."""
        escreve(
            repo,
            "install.sh",
            INSTALL_BOM.replace("svg-loader|obrigatoria|svg|", "svg-loader|importante|svg|"),
        )
        s = secao(roda(repo).stdout)
        assert "[FAIL]" in s and "obrigatória" in s, s

    def test_install_que_pergunta_pelo_nome_em_vez_do_efeito(self, repo: Path) -> None:
        """A checagem `svg` pergunta se o gdk-pixbuf LÊ SVG. Trocá-la pelo nome
        de um pacote quebraria a régua nas outras duas famílias no mesmo dia."""
        escreve(
            repo,
            "install.sh",
            INSTALL_BOM.replace(
                "svg-loader|obrigatoria|svg|", "svg-loader|obrigatoria|cmd:rsvg-convert|"
            ),
        )
        s = secao(roda(repo).stdout)
        assert "[FAIL]" in s and "EFEITO" in s, s

    def test_install_que_perde_o_nome_de_uma_familia(self, repo: Path) -> None:
        """O `_pkg_nome` é a tradução por família. Perder uma linha deixa quem
        instala naquela distro sem o loader e sem mensagem que o diga."""
        escreve(repo, "install.sh", INSTALL_BOM.replace('_dnf="librsvg2"', '_dnf=""'))
        s = secao(roda(repo).stdout)
        assert "[FAIL]" in s and "_pkg_nome" in s, s


class TestALacunaDeclaradaNaoEnvelheceCalada:
    def test_lacuna_que_aponta_para_arquivo_morto_reprova(self, repo: Path) -> None:
        """Lacuna que sobrevive ao próprio defeito vira paisagem — e a próxima
        pessoa lê a lista como se fosse a verdade de hoje."""
        (repo / "scripts" / "build_appimage_gui.sh").unlink()
        s = secao(roda(repo).stdout)
        assert "[FAIL]" in s and "lacuna declarada que já não vale" in s, s
