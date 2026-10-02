"""carimbo_da_casa.py — o MESMO rodapé nas páginas HTML geradas desta casa."""
from __future__ import annotations

import subprocess
from datetime import datetime
from html import escape
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]

PASTA = "html"

MARCA = "data-carimbo"


def _git(*args: str, raiz: Path = RAIZ) -> str:
    """Uma resposta do ``git`` local, ou string vazia quando ele não responde."""
    try:
        pronto = subprocess.run(
            ["git", *args], cwd=raiz, capture_output=True, text=True, timeout=20
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    return pronto.stdout.strip() if pronto.returncode == 0 else ""


def procedencia(raiz: Path = RAIZ) -> dict[str, str]:
    """O commit — a única coisa que o carimbo declara sobre a FONTE da página."""
    return {"commit": _git("rev-parse", "--short", "HEAD", raiz=raiz) or "?"}


def agora() -> str:
    """A hora da geração, no fuso de quem gerou, no formato que a casa usa."""
    return datetime.now().astimezone().strftime("%d/%m/%Y às %H:%M")


def carimbo(gerador: str, *, indice: bool = True, raiz: Path = RAIZ) -> str:
    """A linha de rodapé, IDÊNTICA em toda página gerada."""
    p = procedencia(raiz)
    volta = ' · <a href="index.html">índice dos instrumentos</a>' if indice else ""
    return (
        f'<p class="carimbo" {MARCA}="1">gerado em {escape(agora())} · '
        f'commit <code>{escape(p["commit"])}</code> · por '
        f'<code>{escape(gerador)}</code>{volta}</p>'
    )


def sem_carimbo(pagina: str) -> list[str]:
    """As linhas da página SEM a linha do carimbo — o que o ``--check`` compara."""
    return [linha for linha in pagina.splitlines() if MARCA not in linha]


CSS = """
/* ── o carimbo da casa · scripts/carimbo_da_casa.py ──────────── */
.carimbo { font-family: var(--font-dado); font-size: var(--text-xs);
           color: var(--color-ink-faint); margin: var(--space-md) 0 0;
           padding-top: var(--space-2xs);
           border-top: var(--rule-hair) solid var(--color-rule); }
.carimbo code { color: var(--color-ink-quiet); font-family: inherit; }
.carimbo a { color: var(--color-accent); }
"""

__all__ = ["CSS", "MARCA", "PASTA", "agora", "carimbo", "procedencia", "sem_carimbo"]
