"""O emblema de versão da capa do README é alvo do portão de versão.

O README tem dois literais de versão: a linha `Versão: X` e o emblema do
shields.io. O `scripts/check_version_consistency.py` precisa de um alvo para
cada um, porque a régua é um regex por alvo; com um alvo só, o emblema (a
primeira coisa que se vê na página) envelhecia fora do portão.

O emblema de contagem de testes saiu da capa: o número não serve a quem usa o
produto, e o estado da suíte já aparece no emblema do CI.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
README = REPO / "README.md"
GATE_REL = "scripts/check_version_consistency.py"

#: O emblema de versão, com `versão` percent-encoded pelo shields.io.
_RE_EMBLEMA_VERSAO = re.compile(r"img\.shields\.io/badge/vers%C3%A3o-([0-9][^%-]*)")


def _versao_canonica() -> str:
    try:
        import tomllib
    except ImportError:  # pragma: no cover — 3.10
        import tomli as tomllib  # type: ignore[no-redef]
    dados = tomllib.loads((REPO / "pyproject.toml").read_text(encoding="utf-8"))
    return str(dados["project"]["version"])


def _targets_do_portao() -> list[tuple[str, str, str]]:
    """Lê `_TARGETS` do portão real sem executá-lo (molde do
    tests/unit/test_versoes_rancosas_e_seed_flatpak.py)."""
    sys.path.insert(0, str(REPO / "scripts"))
    try:
        import check_version_consistency as gate
    finally:
        sys.path.pop(0)
    return list(gate._TARGETS)


def _texto_do_readme() -> str:
    return README.read_text(encoding="utf-8")


# --------------------------------------------------------------------------
# 1) O emblema de versão é alvo do portão — e está em dia.
# --------------------------------------------------------------------------


def test_emblema_de_versao_e_alvo_do_portao_de_versao() -> None:
    """Sem alvo próprio, o emblema passa por baixo da régua da prosa."""
    alvos_do_readme = [alvo for alvo in _targets_do_portao() if alvo[1] == "README.md"]
    assert len(alvos_do_readme) >= 2, (
        "o README voltou a ter um alvo só em "
        f"{GATE_REL}: a linha em prosa. O emblema da capa é um segundo literal "
        "no mesmo arquivo e precisa do próprio regex."
    )
    texto = _texto_do_readme()
    casando = [
        alvo
        for alvo in alvos_do_readme
        if (achado := re.search(alvo[2], texto, re.MULTILINE)) is not None
        and "shields.io" in achado.group(0)
    ]
    assert casando, (
        "nenhum alvo do portão casa a URL do shields.io no README — o emblema "
        "de versão voltou a ser invisível ao portão"
    )


def test_emblema_de_versao_bate_com_o_pyproject() -> None:
    """A mordida no arquivo real: repintar o emblema para 0.4.0 derruba isto
    e derruba o `python scripts/check_version_consistency.py` junto."""
    achado = _RE_EMBLEMA_VERSAO.search(_texto_do_readme())
    assert achado is not None, "o emblema de versão sumiu da capa do README"
    assert achado.group(1) == _versao_canonica(), (
        f"a capa anuncia a versão {achado.group(1)!r} e o pyproject.toml diz "
        f"{_versao_canonica()!r}"
    )


def test_prosa_e_emblema_do_readme_dizem_a_mesma_versao() -> None:
    """Os dois literais do mesmo arquivo já divergiram: a prosa foi para a
    0.5.0 no bump e o emblema ficou na 0.4.0."""
    texto = _texto_do_readme()
    prosa = re.search(r"Versão:\s*(\S+)", texto)
    emblema = _RE_EMBLEMA_VERSAO.search(texto)
    assert prosa is not None and emblema is not None
    assert prosa.group(1) == emblema.group(1)
