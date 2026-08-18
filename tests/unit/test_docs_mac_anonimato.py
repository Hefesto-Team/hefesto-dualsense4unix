"""Guarda de anonimato de hardware: MAC real NUNCA sai inteiro no repo.

Corretor final (interação entre ondas, achado #4): o desenho da Onda S vazou
os 6 octetos REAIS do adaptador BT e de um controle, quebrando a convenção que
todas as outras ondas seguiram — MAC de hardware real é citado com os 3
últimos octetos mascarados (forma ``OUI:00:00:NN``; nenhum exemplo literal
aqui de propósito — o irmão test_anonimato_de_fixtures proíbe MAC-forma em
tests/ fora das faixas forjadas).
O ``check_anonymity.sh`` é cego a MAC (só caça menções a provedores de IA e
exclui ``docs/process/**``), então este teste é o gate que faltava.

O contrato: qualquer MAC completo (6 octetos) cujo prefixo seja um OUI de
hardware REAL desta bancada precisa ter os octetos 4 e 5 zerados (a máscara).
Os OUIs em si já são públicos no repo (docs mascarados citam todos) — o que
identifica o aparelho é o SUFIXO, e é ele que este teste bloqueia.
MACs forjados (``aa:bb:cc:*``, ``02:fe:*`` do vpad) ficam fora do contrato.
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

#: OUIs de hardware REAL desta bancada (adaptador BT, DualSense, 8BitDo,
#: Nintendo, roteador) — prefixos já públicos nos docs mascarados.
OUIS_REAIS = (
    "d8[:_-]44[:_-]89",
    "a0[:_-]fa[:_-]9c",
    "e4[:_-]17[:_-]d8",
    "e0[:_-]f6[:_-]b5",
    "48[:_-]b2[:_-]5d",
)

MAC_COMPLETO_RE = re.compile(
    r"(?i)\b(" + "|".join(OUIS_REAIS) + r")"
    r"[:_-]([0-9a-f]{2})[:_-]([0-9a-f]{2})[:_-]([0-9a-f]{2})\b"
)

#: Extensões binárias/geradas — sem texto a auditar.
_SKIP_SUFFIXES = {".png", ".svg", ".mo", ".ico", ".gif", ".jpg", ".jpeg"}


def _tracked_files(repo_root: Path) -> list[Path]:
    out = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    return [
        repo_root / nome
        for nome in out.split("\0")
        if nome and Path(nome).suffix.lower() not in _SKIP_SUFFIXES
    ]


def test_nenhum_mac_real_completo_sem_mascara_no_repo() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    violacoes: list[str] = []
    for path in _tracked_files(repo_root):
        try:
            texto = path.read_text(encoding="utf-8", errors="ignore")
        except (OSError, IsADirectoryError):  # deletado no working tree etc.
            continue
        for num, linha in enumerate(texto.splitlines(), start=1):
            for m in MAC_COMPLETO_RE.finditer(linha):
                # Máscara da casa: octetos 4 e 5 zerados (OUI:00:00:NN).
                if m.group(2) == "00" and m.group(3) == "00":
                    continue
                violacoes.append(
                    f"{path.relative_to(repo_root)}:{num}: "
                    f"MAC real sem máscara ({m.group(1)}:xx:xx:xx)"
                )
    assert not violacoes, (
        "MAC de hardware REAL com sufixo exposto — mascare os 3 últimos "
        "octetos (convenção OUI:00:00:NN dos estudos):\n" + "\n".join(violacoes)
    )
