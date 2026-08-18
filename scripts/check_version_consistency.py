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

Alvos acrescentados em 30/07 (VERSOES-RANCOSAS-01) — os três artefatos que
ninguém checava e que estavam TODOS defasados ao mesmo tempo, cada um com uma
sintaxe diferente:
  - assets/appimage/entrypoint.sh    `HEFESTO_VERSION_FALLBACK="X.Y.Z"` (shell)
  - flatpak/*.metainfo.xml           PRIMEIRA `<release version="X.Y.Z"`
  - packaging/cosmic-applet/Cargo.toml `version = "X.Y.Z"` (semver simples)
O entrypoint anunciava v3.0.0 e mandava instalar um .deb com nome que não existe
mais; o metainfo anunciava 3.13.3 de 14/07 para a loja; o Cargo.toml do applet
estava em 0.1.0. Nenhum era visível a portão nenhum.

Alvo acrescentado em 31/07 (PUBLICAÇÃO-FIEL-01):
  - docs/usage/instalacao.md         `git checkout vX.Y.Z`
Ela é a página canônica de instalação (o README aponta para ela duas vezes) e
ficou uma release inteira para trás: mandava `git checkout v0.3.0` com a 0.4.0
publicada, enquanto quickstart e flatpak já diziam v0.4.0.

Conferência de DATA acrescentada em 31/07 (PUBLICAÇÃO-FIEL-01): a régua acima
compara NÚMERO, e só. O buraco por onde a v0.4.0 passou foi esse — o commit do
bump trocou `version="0.3.0"` por `version="0.4.0"` na entrada que já existia do
metainfo e não mexeu em mais nada, então a loja anunciou a 0.4.0 com a data e o
texto da 0.3.0, e a 0.3.0 sumiu da série. Trocar o número era a menor edição
possível que deixava este portão verde: a régua desenhou o conserto. Agora a
data da primeira <release> é conferida contra a seção correspondente do
CHANGELOG.md, que é a fonte de verdade das notas de versão.

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
    # O banner do AppImage deriva a versão do metadata do pacote embutido; este
    # literal é só o fallback de quando a consulta falha (mesmo papel do
    # `__version__` do __init__.py). Ancorado em `^` para não casar comentário.
    ("entrypoint AppImage (fallback)", "assets/appimage/entrypoint.sh",
     r'^HEFESTO_VERSION_FALLBACK="([^"]+)"'),
    # AppStream: a PRIMEIRA <release> do bloco é a que a loja mostra como atual.
    # `re.search` para o primeiro casamento é exatamente o que se quer aqui.
    ("metainfo Flatpak (release mais recente)",
     "flatpak/br.andrefarias.Hefesto.metainfo.xml",
     r'<release\s+version="([^"]+)"'),
    # Cargo: `^version` ancorado no início da linha é obrigatório — sem a âncora
    # o regex casaria o `version = "1"` do tokio dentro de [dependencies].
    ("Cargo applet COSMIC", "packaging/cosmic-applet/Cargo.toml",
     r'^version\s*=\s*"([^"]+)"'),
    # Página canônica de instalação: o alvo é a TAG do comando de clone, que é
    # o que alguém copia e executa. A frase em prosa da mesma página cita a
    # versão de novo e não cabe nesta régua (um regex por alvo); ela é conferida
    # em tests/unit/test_versao_publicada_data_e_paginas_de_uso.py.
    ("página de instalação (git checkout)", "docs/usage/instalacao.md",
     r"^git checkout v(\S+)"),
]

#: Conferência de data: a primeira <release> do metainfo contra a seção
#: correspondente do CHANGELOG.md.
_METAINFO_REL = "flatpak/br.andrefarias.Hefesto.metainfo.xml"
_CHANGELOG_REL = "CHANGELOG.md"

#: `version` e `date` na ordem em que o arquivo os escreve. Exigir os dois no
#: mesmo casamento é de propósito: entrada sem data não pode passar calada.
_RE_PRIMEIRA_RELEASE = re.compile(
    r'<release\s+version="(?P<numero>[^"]+)"\s+date="(?P<data>[^"]+)"'
)


def _data_no_changelog(texto: str, numero: str) -> str | None:
    """Data da seção `## [X.Y.Z] — AAAA-MM-DD`, se ela existir e for datada.

    O travessão da casa é `—`, mas `-` é aceito para não reprovar por tipografia.
    Seção sem data (a `## [0.1.2] — RETIRADA`) não casa, de propósito.
    """
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
        if actual != expected:
            failures.append(f"  {label} ({relpath}): '{actual}' != '{expected}'")

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
