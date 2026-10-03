"""LOADER-SVG-NOS-EMPACOTAMENTOS-01 — o `.deb`, o `.rpm`, o Arch e o Nix"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]

LOADER = {
    "packaging/debian/control": "librsvg2-common",
    "packaging/fedora/hefesto-dualsense4unix.spec": "librsvg2",
    "packaging/arch/PKGBUILD": "librsvg",
    "packaging/nix/package.nix": "librsvg",
}

FERRAMENTAS_DE_BUILD = ("librsvg2-bin", "librsvg2-tools")


def _campo_deb(texto: str, campo: str) -> str:
    """Devolve UM campo do ``DEBIAN/control``, com as continuações."""
    linhas = texto.splitlines()
    coletando = False
    pedacos: list[str] = []
    for linha in linhas:
        if coletando:
            if linha.startswith((" ", "\t")):
                pedacos.append(linha.strip())
                continue
            break
        if linha.startswith(f"{campo}:"):
            coletando = True
            pedacos.append(linha.split(":", 1)[1].strip())
    return " ".join(pedacos)


def _sem_comentarios(texto: str, marca: str = "#") -> str:
    """Tira as linhas de comentário — um comentário que EXPLICA a regra não"""
    return "\n".join(
        linha
        for linha in texto.splitlines()
        if not linha.lstrip().startswith(marca)
    )


def _bloco(texto: str, abertura: str, fechamento: str) -> str:
    """Recorta o bloco entre ``abertura`` e o primeiro ``fechamento``."""
    limpo = _sem_comentarios(texto)
    inicio = limpo.find(abertura)
    if inicio < 0:
        return ""
    fim = limpo.find(fechamento, inicio)
    return limpo[inicio : fim if fim >= 0 else len(limpo)]


def _campo_de_execucao(caminho: str) -> str:
    """O trecho que o gerenciador de pacotes LÊ como dependência dura."""
    texto = (RAIZ / caminho).read_text(encoding="utf-8")
    if caminho.endswith("debian/control"):
        return _campo_deb(texto, "Depends")
    if caminho.endswith(".spec"):
        return "\n".join(
            linha
            for linha in _sem_comentarios(texto).splitlines()
            if linha.startswith("Requires:")
        )
    if caminho.endswith("PKGBUILD"):
        return _bloco(texto, "depends=(", ")")
    if caminho.endswith("package.nix"):
        return _bloco(texto, "buildInputs = [", "];")
    raise AssertionError(f"formato sem régua: {caminho}")


@pytest.mark.parametrize(("caminho", "pacote"), sorted(LOADER.items()))
def test_cada_empacotamento_declara_o_loader_svg(caminho: str, pacote: str) -> None:
    """Os quatro declaram o loader — no campo, não na prosa nem no comentário."""
    campo = _campo_de_execucao(caminho)
    assert re.search(rf"(?<![\w-]){re.escape(pacote)}(?![\w-])", campo), (
        f"{caminho} não declara o loader SVG no campo que o gerenciador lê "
        f"(esperado: {pacote}). Sem ele o ícone da bandeja some "
        f"— BUG-TRAY-ICONE-INVISIVEL-01."
    )


@pytest.mark.parametrize("caminho", sorted(LOADER))
def test_nenhum_empacotamento_pede_a_ferramenta_de_build(caminho: str) -> None:
    """O ``rsvg-convert`` não é dependência de execução."""
    campo = _campo_de_execucao(caminho)
    for ferramenta in FERRAMENTAS_DE_BUILD:
        assert not re.search(rf"(?<![\w-]){re.escape(ferramenta)}(?![\w-])", campo), (
            f"{caminho} pede {ferramenta} como dependência de EXECUÇÃO — esse é "
            f"o rsvg-convert, ferramenta de build. Quem desenha na tela é "
            f"{LOADER[caminho]}."
        )


def test_o_loader_e_dependencia_dura_e_nao_fraca() -> None:
    """Nada de ``Recommends``/``Suggests``/``optdepends`` para o loader."""
    control = (RAIZ / "packaging/debian/control").read_text(encoding="utf-8")
    for campo in ("Recommends", "Suggests"):
        assert "librsvg" not in _campo_deb(control, campo), (
            f"packaging/debian/control declara o loader SVG em {campo} — "
            "é dependência dura: sem ele o ícone da bandeja some."
        )

    spec = _sem_comentarios(
        (RAIZ / "packaging/fedora/hefesto-dualsense4unix.spec").read_text(
            encoding="utf-8"
        )
    )
    assert not re.search(r"^(Recommends|Suggests):\s*librsvg", spec, re.MULTILINE), (
        "o .spec declara o loader SVG como dependência fraca — no RPM a fraca é "
        "IGNORADA em silêncio quando o pacote não está nos repositórios "
        "habilitados, e o defeito volta calado."
    )

    pkgbuild = (RAIZ / "packaging/arch/PKGBUILD").read_text(encoding="utf-8")
    assert "librsvg" not in _bloco(pkgbuild, "optdepends=(", ")"), (
        "o PKGBUILD declara o loader SVG em optdepends — é dependência dura."
    )


def test_flatpak_se_salva_pelo_runtime_e_isso_fica_registrado() -> None:
    """O Flatpak NÃO declara o loader, e está certo: o runtime já o traz."""
    manifesto = RAIZ / "flatpak/io.github.hefesto_team.hefesto_dualsense4unix.yml"
    texto = _sem_comentarios(manifesto.read_text(encoding="utf-8"))
    casamento = re.search(r"^runtime:\s*(\S+)", texto, re.MULTILINE)
    assert casamento, "o manifesto Flatpak não declara runtime"
    runtime = casamento.group(1).strip("\"'")
    assert runtime in ("org.gnome.Platform", "org.freedesktop.Platform"), (
        f"o Flatpak passou a usar o runtime {runtime}, e a isenção do loader "
        "SVG estava medida contra org.gnome.Platform//47 e "
        "org.freedesktop.Platform (19/08/2026). Meça o novo — "
        "`ls .../gdk-pixbuf-2.0/2.10.0/loaders/ | grep svg` — ou bundle o "
        "loader como módulo, do jeito que o wvkbd é bundlado."
    )


def test_o_nome_do_loader_casa_o_do_install_nativo() -> None:
    """Os empacotamentos e o instalador nativo pedem o MESMO pacote."""
    install = (RAIZ / "install.sh").read_text(encoding="utf-8")
    bloco = _bloco(install, '_apt="librsvg2-common"', "\n\n")
    assert bloco, (
        "install.sh não tem mais a linha do loader SVG na tabela de pacotes — "
        "se a tabela mudou de forma, esta régua tem de mudar junto, e não sumir."
    )
    esperado = {
        "_apt": LOADER["packaging/debian/control"],
        "_dnf": LOADER["packaging/fedora/hefesto-dualsense4unix.spec"],
        "_pacman": LOADER["packaging/arch/PKGBUILD"],
    }
    for variavel, pacote in esperado.items():
        casamento = re.search(rf'{variavel}="([^"]*)"', bloco)
        assert casamento and casamento.group(1) == pacote, (
            f"install.sh instala {casamento.group(1) if casamento else 'nada'} "
            f"para {variavel} e o empacotamento declara {pacote} — o instalador "
            "nativo e o pacote têm de pedir a mesma coisa."
        )
