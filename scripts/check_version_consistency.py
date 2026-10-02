#!/usr/bin/env python3
"""Falha se algum alvo versionado não reflete a versão canônica de pyproject.toml."""
from __future__ import annotations

import re
import sys
from collections.abc import Callable
from pathlib import Path

try:
    import tomllib  # stdlib Python 3.11+
except ImportError:  # pragma: no cover — fallback para 3.10
    import tomli as tomllib  # type: ignore[no-redef]


ROOT = Path(__file__).resolve().parent.parent
PYPROJECT = ROOT / "pyproject.toml"

_TARGETS: list[tuple[str, str, str]] = [
    ("README.md", "README.md", r"Versão:\s*(\S+)"),
    ("README.md (emblema de versão)", "README.md",
     r"shields\.io/badge/vers%C3%A3o-([0-9][^%-]*)"),
    ("__init__ fallback", "src/hefesto_dualsense4unix/__init__.py",
     r'__version__\s*=\s*"([^"]+)"'),
    ("PKGBUILD", "packaging/arch/PKGBUILD", r"^pkgver=(\S+)"),
    ("fedora spec", "packaging/fedora/hefesto-dualsense4unix.spec",
     r"^Version:\s*(\S+)"),
    ("nix package", "packaging/nix/package.nix", r'version\s*=\s*"([^"]+)";'),
    ("debian control", "packaging/debian/control", r"^Version:\s*(\S+)"),
    ("entrypoint AppImage (fallback)", "assets/appimage/entrypoint.sh",
     r'^HEFESTO_VERSION_FALLBACK="([^"]+)"'),
    ("metainfo Flatpak (release mais recente)",
     "flatpak/io.github.hefesto_team.hefesto_dualsense4unix.metainfo.xml",
     r'<release\s+version="([^"]+)"'),
    ("Cargo applet COSMIC", "packaging/cosmic-applet/Cargo.toml",
     r'^version\s*=\s*"([^"]+)"'),
    ("Cargo.lock do applet", "packaging/cosmic-applet/Cargo.lock",
     r'^name = "hefesto-dualsense4unix-applet"\nversion = "([^"]+)"'),
]

def versao_para_cargo(canonica: str) -> str:
    """A canônica na forma que o Cargo aceita — `X.Y.Z.W` vira `X.Y.Z+W`."""
    partes = canonica.split(".")
    if len(partes) <= 3:
        return canonica
    return ".".join(partes[:3]) + "+" + ".".join(partes[3:])


_TRADUTORES: dict[str, Callable[[str], str]] = {
    "packaging/cosmic-applet/Cargo.toml": versao_para_cargo,
    "packaging/cosmic-applet/Cargo.lock": versao_para_cargo,
}


_METAINFO_REL = "flatpak/io.github.hefesto_team.hefesto_dualsense4unix.metainfo.xml"
_CHANGELOG_REL = "CHANGELOG.md"

_RE_PRIMEIRA_RELEASE = re.compile(
    r'<release\s+version="(?P<numero>[^"]+)"\s+date="(?P<data>[^"]+)"'
)


def _data_no_changelog(texto: str, numero: str) -> str | None:
    """Data da seção `## [X.Y.Z] — AAAA-MM-DD`, se ela existir e for datada."""
    padrao = rf"^##\s*\[{re.escape(numero)}\]\s*[—-]\s*(\d{{4}}-\d{{2}}-\d{{2}})\s*$"
    achado = re.search(padrao, texto, re.MULTILINE)
    return achado.group(1) if achado else None


def _conferir_data_da_release(root: Path) -> tuple[bool, list[str]]:
    """Devolve (conferiu, falhas). Arquivo ausente é ignorado, como nos alvos."""
    metainfo = root / _METAINFO_REL
    changelog = root / _CHANGELOG_REL
    if not metainfo.is_file() or not changelog.is_file():
        return False, []

    achado = _RE_PRIMEIRA_RELEASE.search(metainfo.read_text(encoding="utf-8"))
    if achado is None:
        return True, [
            f"  metainfo ({_METAINFO_REL}): a primeira <release> não traz "
            "version e date no mesmo elemento"
        ]

    numero = achado.group("numero")
    data_metainfo = achado.group("data")
    data_changelog = _data_no_changelog(
        changelog.read_text(encoding="utf-8"), numero
    )
    if data_changelog is None:
        return True, [
            f"  metainfo x CHANGELOG: a {numero} que o AppStream anuncia não tem "
            f"seção datada em {_CHANGELOG_REL}"
        ]
    if data_metainfo != data_changelog:
        return True, [
            f"  metainfo x CHANGELOG ({numero}): o AppStream diz "
            f"'{data_metainfo}' e o {_CHANGELOG_REL} diz '{data_changelog}'"
        ]
    return True, []


def main() -> int:
    try:
        cfg = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))
    except FileNotFoundError:
        print(f"FAIL: pyproject.toml não encontrado em {PYPROJECT}")
        return 1
    expected = cfg.get("project", {}).get("version")
    if not expected:
        print("FAIL: [project].version ausente em pyproject.toml")
        return 1

    failures: list[str] = []
    checked = 0
    for label, relpath, pattern in _TARGETS:
        path = ROOT / relpath
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        match = re.search(pattern, text, re.MULTILINE)
        actual = match.group(1) if match else None
        checked += 1
        alvo_esperado = _TRADUTORES.get(relpath, lambda v: v)(expected)
        if actual != alvo_esperado:
            failures.append(
                f"  {label} ({relpath}): '{actual}' != '{alvo_esperado}'"
            )

    conferiu_data, falhas_de_data = _conferir_data_da_release(ROOT)
    failures.extend(falhas_de_data)

    if failures:
        print(f"FAIL: versão canônica é '{expected}', mas divergem:")
        print("\n".join(failures))
        print("  Atualize os arquivos acima para a versão canônica.")
        return 1

    sufixo = (
        " Data da release corrente confere com o CHANGELOG." if conferiu_data else ""
    )
    print(f"OK: {checked} alvo(s) versionado(s) em {expected}.{sufixo}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
