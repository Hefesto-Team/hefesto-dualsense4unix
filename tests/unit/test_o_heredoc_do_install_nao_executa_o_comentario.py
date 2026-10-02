#!/usr/bin/env python3
"""O HEREDOC SEM ASPAS DO INSTALL NÃO PODE TER CRASE — ela vira comando."""
from __future__ import annotations

import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
ROTEIROS = ("install.sh", "uninstall.sh")

_ABRE = re.compile(r"<<-?\s*(['\"]?)([A-Za-z_][A-Za-z_0-9]*)\1")


def heredocs_sem_aspas(texto: str) -> list[tuple[int, str, list[int]]]:
    """`[(linha que abre, marcador, linhas do corpo com crase)]` dos sem aspas."""
    linhas = texto.split("\n")
    achados: list[tuple[int, str, list[int]]] = []
    i = 0
    while i < len(linhas):
        abre = _ABRE.search(linhas[i])
        if abre and not linhas[i].lstrip().startswith("#"):
            aspas, fim = abre.group(1), abre.group(2)
            j = i + 1
            while j < len(linhas) and linhas[j].strip() != fim:
                j += 1
            if not aspas:
                crases = [k + 1 for k in range(i + 1, j) if "`" in linhas[k]]
                achados.append((i + 1, fim, crases))
            i = j
        i += 1
    return achados


def test_nenhum_heredoc_sem_aspas_tem_crase():
    queixas = [
        f"{nome}:{linha} <<{fim}: crase nas linhas {crases}"
        for nome in ROTEIROS
        for linha, fim, crases in heredocs_sem_aspas(
            (RAIZ / nome).read_text(encoding="utf-8"))
        if crases
    ]
    assert not queixas, (
        "heredoc SEM aspas com crase no corpo — o bash executa a palavra entre "
        "crases durante o install:\n  " + "\n  ".join(queixas))


def test_a_regua_enxerga_o_lancador():
    """A guarda de vacuidade: o `<<LAUNCH` tem de estar entre os medidos."""
    medidos = {fim for _l, fim, _c in heredocs_sem_aspas(
        (RAIZ / "install.sh").read_text(encoding="utf-8"))}
    assert "LAUNCH" in medidos, medidos


def test_a_regua_acusa_a_crase():
    """A régua sabe reprovar: um heredoc de mentira com crase é acusado."""
    falso = "cat > x <<FIM\n# chama `rm`\nFIM\ncat > y <<'OK'\n# `pode`\nOK\n"
    assert heredocs_sem_aspas(falso) == [(1, "FIM", [2])]
