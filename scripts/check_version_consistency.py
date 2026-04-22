#!/usr/bin/env python3
"""Falha se README.md não reflete a versão canônica de pyproject.toml.

Fonte de verdade: `pyproject.toml` ([project].version).
Alvo verificado: linha `Versão: X.Y.Z` em `README.md`.

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
README = ROOT / "README.md"


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

    readme_text = README.read_text(encoding="utf-8")
    match = re.search(r"Versão:\s*(\S+)", readme_text)
    actual = match.group(1) if match else None
    if actual != expected:
        print(
            f"FAIL: README versão '{actual}' != pyproject '{expected}'.\n"
            f"  Atualize README.md linha 'Versão: X.Y.Z' para '{expected}'."
        )
        return 1

    print(f"OK: README e pyproject.toml em {expected}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
