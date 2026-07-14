#!/usr/bin/env python3
"""Falha se algum alvo versionado não reflete a versão canônica de pyproject.toml.

Fonte de verdade: `pyproject.toml` ([project].version).
Alvos verificados (M12 da auditoria — antes só o README era checado, e os pacotes
Arch/Fedora/Nix/debian ficaram defasados em 3.4.0, instalando versões antigas em
silêncio via makepkg/rpmbuild):
  - README.md            linha `Versão: X.Y.Z`
  - src/.../__init__.py  fallback `__version__ = "X.Y.Z"`
  - packaging/arch/PKGBUILD          `pkgver=X.Y.Z`
  - packaging/fedora/*.spec          `Version:        X.Y.Z`
  - packaging/nix/package.nix        `version = "X.Y.Z";`
  - packaging/debian/control         `Version: X.Y.Z`

Uso (CI):
    python scripts/check_version_consistency.py
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

try:
    import tomllib  # stdlib Python 3.11+
except ImportError:  # pragma: no cover — fallback para 3.10
    import tomli as tomllib  # type: ignore[no-redef]


ROOT = Path(__file__).resolve().parent.parent
PYPROJECT = ROOT / "pyproject.toml"

#: (label, path relativo, regex com 1 grupo = versão). Path ausente é ignorado
#: (o alvo pode não existir em todos os checkouts); só falha em MISMATCH.
_TARGETS: list[tuple[str, str, str]] = [
    ("README.md", "README.md", r"Versão:\s*(\S+)"),
    ("__init__ fallback", "src/hefesto_dualsense4unix/__init__.py",
     r'__version__\s*=\s*"([^"]+)"'),
    ("PKGBUILD", "packaging/arch/PKGBUILD", r"^pkgver=(\S+)"),
    ("fedora spec", "packaging/fedora/hefesto-dualsense4unix.spec",
     r"^Version:\s*(\S+)"),
    ("nix package", "packaging/nix/package.nix", r'version\s*=\s*"([^"]+)";'),
    ("debian control", "packaging/debian/control", r"^Version:\s*(\S+)"),
]


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
        if actual != expected:
            failures.append(f"  {label} ({relpath}): '{actual}' != '{expected}'")

    if failures:
        print(f"FAIL: versão canônica é '{expected}', mas divergem:")
        print("\n".join(failures))
        print("  Atualize os arquivos acima para a versão canônica.")
        return 1

    print(f"OK: {checked} alvo(s) versionado(s) em {expected}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
