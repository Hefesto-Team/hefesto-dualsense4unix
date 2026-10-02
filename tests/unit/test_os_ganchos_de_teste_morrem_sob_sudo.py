"""Sob sudo, os ganchos de teste dos scripts de root não existem."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]

SCRIPTS_DE_ROOT = {
    "bt_active_mode.sh": {"HEFESTO_BT_LOG_DEST"},
    "bt_health_watchdog.sh": {"HEFESTO_BT_LOG_DEST"},
    "bt_ponte_privilegiada.sh": set(),
    "bt_rebind_orphans.sh": {"HEFESTO_BT_LOG_DEST"},
}

_GUARDA = re.compile(
    r'if \[\[ -n "\$\{SUDO_UID:-\}" \|\| -n "\$\{SUDO_USER:-\}" \]\]; then\n'
    r"(?P<corpo>(?:[^\n]*\n)+?)fi\n"
)


def _apagados(corpo: str) -> set[str]:
    """Os ganchos que a guarda APAGA — os argumentos de um `unset`, e só eles."""
    nomes: set[str] = set()
    for linha in re.sub(r"\\\n[ \t]*", " ", corpo).splitlines():
        partes = linha.split()
        if partes[:1] == ["unset"]:
            nomes |= {p for p in partes[1:] if re.fullmatch(r"HEFESTO_[A-Z0-9_]+", p)}
    return nomes


def _codigo(texto: str) -> str:
    """O texto com cada linha de comentário em branco (as posições ficam)."""
    return "\n".join(
        "" if linha.lstrip().startswith("#") else linha for linha in texto.splitlines()
    ) + "\n"


@pytest.mark.parametrize("nome", sorted(SCRIPTS_DE_ROOT))
def test_todo_gancho_lido_morre_sob_sudo(nome: str) -> None:
    codigo = _codigo((RAIZ / "scripts" / nome).read_text(encoding="utf-8"))
    guarda = _GUARDA.search(codigo)
    assert guarda, f"{nome} não tem a guarda do sudo (SUDO_UID/SUDO_USER → unset)"
    apagados = _apagados(guarda.group("corpo"))
    todas = list(re.finditer(r"\$\{(HEFESTO_[A-Z0-9_]+)", codigo))
    leituras = {m.group(1): m.start() for m in reversed(todas)}
    assert leituras, f"controle: {nome} não lê gancho nenhum — a régua não mede nada"
    faltam = sorted(set(leituras) - apagados - SCRIPTS_DE_ROOT[nome])
    assert not faltam, (
        f"{nome} lê {faltam} e não os apaga sob sudo: o root usaria um caminho "
        "vindo do ambiente de quem chamou"
    )
    antes = sorted(g for g, pos in leituras.items() if pos < guarda.start())
    assert not antes, f"{nome} lê {antes} ANTES da guarda do sudo"
