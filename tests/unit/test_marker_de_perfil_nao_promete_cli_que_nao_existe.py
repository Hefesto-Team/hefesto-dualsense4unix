"""ONDA0-Z5/T14 — o consumidor que não existe mais sai do cabeçalho.

Fato substituído, e substituído em TODOS os lugares onde aparecia
(`utils/session.py`, duas ocorrências; `daemon/ipc_handlers.py`, uma):
`active_profile.txt` NÃO é lido por um subcomando `profile current` da CLI —
medido (ONDA0-Z5 §2.8): esse verbo não existe (`typer` sugere `create` no
lugar). O consumidor real é `cli/cmd_profile.py:402`
(`profile save --from-active`).

A régua é a mesma que a sprint mandou rodar ANTES de acreditar nela — contra
`utils/session.py`, que se sabe que continha pelo menos uma ocorrência antes
da leva de 24/08.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def _grep_profile_current() -> str:
    resultado = subprocess.run(
        ["grep", "-rn", "profile current", "src/", "README.md"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    return resultado.stdout


def test_a_regua_volta_vazia_hoje() -> None:
    achados = _grep_profile_current()
    assert achados == "", (
        f"'profile current' ainda aparece em src/ ou README.md, prometendo "
        f"um subcomando que não existe:\n{achados}"
    )


def test_a_regua_sabe_acusar_quando_o_fato_errado_volta() -> None:
    """A mordida: sem esta régua saber ACUSAR, ela não prova nada — só que
    nunca encontra nada (§4 do COMO-EXECUTAR-UMA-SPRINT.md)."""
    caminho = REPO_ROOT / "src" / "hefesto_dualsense4unix" / "utils" / "session.py"
    original = caminho.read_text(encoding="utf-8")
    contaminado = original + "\n# profile current — reintroduzido para a mordida\n"
    caminho.write_text(contaminado, encoding="utf-8")
    try:
        achados = _grep_profile_current()
        assert "profile current" in achados, (
            "a régua não acusou uma ocorrência que eu ACABEI de inserir — "
            "régua que só sabe passar não é régua"
        )
    finally:
        caminho.write_text(original, encoding="utf-8")

    # Devolvido: a régua volta a ficar limpa.
    assert _grep_profile_current() == ""
