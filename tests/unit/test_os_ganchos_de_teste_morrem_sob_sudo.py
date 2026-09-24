"""Sob sudo, os ganchos de teste dos scripts de root não existem.

INSTALL-E-UNINSTALL-DO-RADIO-01 (23/09/2026), o pedido P-12: a trava do rádio
(MOVER-UM-POR-VEZ-01) deu ao `bt_active_mode.sh` e ao watchdog um gancho novo,
`HEFESTO_RADIO_TRAVA`, e nenhum dos dois o apagava sob sudo. O root ABRE o
arquivo da trava e escreve nele quem a segura: numa máquina com o `env_reset`
desligado, o caminho vindo do ambiente de quem chamou o sudo viraria uma escrita
de root onde ela quisesse. O watchdog nem tinha a guarda.

A régua é por FORMA, e não por lista: todo `${HEFESTO_*}` que o código de um
destes scripts lê tem de estar no `unset` da guarda do sudo, e a guarda tem de
vir antes da primeira leitura. Um gancho novo amanhã reprova aqui sem ninguém
lembrar de acrescentá-lo. A exceção é a declarada no próprio script: o de LOG,
que só muda onde se escreve o diário, fica no `bt_active_mode.sh` e no watchdog.

A MORDIDA, medida: tirar o `HEFESTO_RADIO_TRAVA` do `unset` do
`bt_active_mode.sh` reprova o caso dele; tirar a guarda do watchdog reprova o
dele; trocar o `unset` do watchdog por `:`, com os nomes no lugar, também; e a
ponte reprovava antes desta sprint, pelo `HEFESTO_SYSFS_BLUETOOTH` que ela lia
e não apagava.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]

#: script -> ganchos que ficam sob sudo, com a razão no próprio script.
SCRIPTS_DE_ROOT = {
    "bt_active_mode.sh": {"HEFESTO_BT_LOG_DEST"},
    "bt_health_watchdog.sh": {"HEFESTO_BT_LOG_DEST"},
    "bt_ponte_privilegiada.sh": set(),
}

_GUARDA = re.compile(
    r'if \[\[ -n "\$\{SUDO_UID:-\}" \|\| -n "\$\{SUDO_USER:-\}" \]\]; then\n'
    r"(?P<corpo>(?:[^\n]*\n)+?)fi\n"
)


def _apagados(corpo: str) -> set[str]:
    """Os ganchos que a guarda APAGA — os argumentos de um `unset`, e só eles.

    Conferência da INSTALL-E-UNINSTALL-DO-RADIO-01: a régua colhia todo
    `HEFESTO_*` escrito dentro da guarda, e trocar o `unset` por `:` (ou por
    um `echo`) deixava os nomes no texto e a régua verde, com o gancho vivo sob
    sudo. É a régua lendo a PALAVRA em vez do ATO.
    """
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
    #: gancho -> a posição da PRIMEIRA leitura (o reversed deixa a primeira por último).
    leituras = {m.group(1): m.start() for m in reversed(todas)}
    assert leituras, f"controle: {nome} não lê gancho nenhum — a régua não mede nada"
    faltam = sorted(set(leituras) - apagados - SCRIPTS_DE_ROOT[nome])
    assert not faltam, (
        f"{nome} lê {faltam} e não os apaga sob sudo: o root usaria um caminho "
        "vindo do ambiente de quem chamou"
    )
    antes = sorted(g for g, pos in leituras.items() if pos < guarda.start())
    assert not antes, f"{nome} lê {antes} ANTES da guarda do sudo"
