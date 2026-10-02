"""BTMGMT-QUE-NAO-VOLTA-01: nenhuma chamada a `btmgmt` pode ficar sem teto."""

from __future__ import annotations

import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]

ARQUIVOS = sorted(
    p
    for p in [*RAIZ.rglob("*.sh"), RAIZ / "install.sh", RAIZ / "uninstall.sh"]
    if p.is_file() and ".git" not in p.parts and "node_modules" not in p.parts
)

INVOCACAO = re.compile(r"(?:^|[(|;&]|\$\()\s*btmgmt\s+\w")
JA_TEM_TETO = re.compile(r"timeout\s+[\d.]+\s+btmgmt\s")


def test_toda_chamada_a_btmgmt_tem_teto_de_tempo() -> None:
    nuas: list[str] = []
    for arq in ARQUIVOS:
        for n, linha in enumerate(arq.read_text(encoding="utf-8").splitlines(), 1):
            sem_comentario = linha.split("#", 1)[0]
            if "command -v btmgmt" in sem_comentario:
                continue
            if not INVOCACAO.search(sem_comentario):
                continue
            if JA_TEM_TETO.search(sem_comentario):
                continue
            nuas.append(f"{arq.relative_to(RAIZ)}:{n}: {linha.strip()}")

    assert not nuas, (
        "chamada a `btmgmt` SEM teto de tempo — numa máquina sem adaptador ela "
        "não volta, e o install trava para sempre sem dizer por quê:\n  "
        + "\n  ".join(nuas)
        + "\n\nUse `timeout 5 btmgmt ...`. Ver BTMGMT-QUE-NAO-VOLTA-01."
    )


def test_o_portao_enxerga_os_quatro_pontos_conhecidos() -> None:
    """Guarda contra o portão ficar cego — o defeito mais caro desta casa."""
    com_teto = sum(
        len(JA_TEM_TETO.findall(arq.read_text(encoding="utf-8"))) for arq in ARQUIVOS
    )
    assert com_teto >= 4, (
        f"o portão só enxerga {com_teto} chamada(s) com teto, e a migração do "
        "BlueZ deixou 4 (bt_active_mode duas vezes, uninstall, doctor). Portão que não "
        "vê nada passa sempre."
    )
