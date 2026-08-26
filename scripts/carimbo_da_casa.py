"""carimbo_da_casa.py — o MESMO rodapé nos quatro instrumentos HTML desta casa.

Este módulo nasceu em 25/08/2026, irmão do ``paleta_da_casa.py`` e pelo mesmo
motivo: o que os quatro artefatos dividem precisa ter **um dono**. A paleta dá a
eles a mesma cara; o carimbo dá a eles a mesma **procedência**.

O defeito que ele cura (HTML-2 da sprint ``A-CASA-ARRUMADA-01``): três páginas
que se dizem irmãs não tinham como dizer se estavam em dia **ao mesmo tempo**.
Uma gerada hoje e outra de três commits atrás pareciam iguais, e a diferença só
aparecia quando alguém acreditasse num número velho. Com o carimbo, duas páginas
que discordam **declaram isso no próprio rodapé**, lado a lado, em vez de a
divergência ser descoberta por acidente.

Quem lê daqui:

  - ``scripts/gerar-mapa.py``           → ``html/specs.html``
  - ``scripts/gerar-painel.py``         → ``html/painel.html``
  - ``scripts/gerar-frases-de-tela.py`` → ``html/frases-de-tela.html``
  - ``scripts/gerar-indice-html.py``    → ``html/index.html``

**A REGRA DOS IRMÃOS VALE AQUI TAMBÉM: nada de rede.** O carimbo sai de ``git``
local; se o ``git`` não responder, ele diz ``?`` em vez de inventar — ausência
de medição é declarada, nunca preenchida.

O CARIMBO NÃO ENTRA NO ``--check``, E ISSO É DE PROPÓSITO
=========================================================
O commit e a hora mudam a cada geração. Se o comparador de conteúdo os visse,
todo ``--check`` reprovaria pelo relógio — que é exatamente o defeito de onde o
``gerar-mapa.py`` já saiu uma vez (ver o ``SELO`` de lá). Por isso a linha
carrega a marca ``data-carimbo``, e ``sem_carimbo()`` é o que os quatro
``--check`` usam para tirá-la antes de comparar.
"""
from __future__ import annotations

import subprocess
from datetime import datetime
from html import escape
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]

#: A pasta única dos instrumentos, relativa à raiz do repositório.
PASTA = "html"

#: A marca que identifica a linha do carimbo em qualquer uma das quatro páginas.
#: É por ela que ``sem_carimbo()`` acha o que tirar, e é por ela que o teste da
#: sprint confere que os quatro carimbaram.
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
    """Commit, branch e sujeira da árvore — o que o carimbo declara.

    ``sujos`` conta arquivos com mudança não commitada. Ele existe porque o
    commit sozinho MENTE numa árvore suja: a página pode ter sido gerada de um
    dado que ainda não está em commit nenhum.
    """
    sujos = [ln for ln in _git("status", "--porcelain", raiz=raiz).splitlines() if ln.strip()]
    return {
        "commit": _git("rev-parse", "--short", "HEAD", raiz=raiz) or "?",
        "branch": _git("rev-parse", "--abbrev-ref", "HEAD", raiz=raiz) or "?",
        "sujos": str(len(sujos)),
    }


def agora() -> str:
    """A hora da geração, no fuso de quem gerou, no formato que a casa usa."""
    return datetime.now().astimezone().strftime("%d/%m/%Y às %H:%M")


def carimbo(gerador: str, *, indice: bool = True, raiz: Path = RAIZ) -> str:
    """A linha de rodapé, IDÊNTICA nas quatro páginas.

    ``gerador`` é o caminho do script que escreveu a página, para quem olhar o
    rodapé saber onde ficar reclamando. ``indice=False`` no próprio
    ``index.html``, que não precisa de um link para si mesmo.
    """
    p = procedencia(raiz)
    sujeira = (
        ""
        if p["sujos"] == "0"
        else f" · árvore com {escape(p['sujos'])} mudança(s) não commitada(s)"
    )
    volta = ' · <a href="index.html">índice dos instrumentos</a>' if indice else ""
    return (
        f'<p class="carimbo" {MARCA}="1">gerado em {escape(agora())} · '
        f'commit <code>{escape(p["commit"])}</code> na branch '
        f'<code>{escape(p["branch"])}</code>{sujeira} · por '
        f'<code>{escape(gerador)}</code>{volta}</p>'
    )


def sem_carimbo(pagina: str) -> list[str]:
    """As linhas da página SEM a linha do carimbo — o que o ``--check`` compara.

    Um ``--check`` que enxergasse o carimbo reprovaria a cada commit e a cada
    minuto do relógio, e portão que reprova sempre é desligado na semana
    seguinte.
    """
    return [linha for linha in pagina.splitlines() if MARCA not in linha]


#: O estilo da linha, para entrar no ``<style>`` de cada página. Usa só tokens
#: do ``paleta_da_casa.py`` — o carimbo tem de parecer parte de cada página, não
#: um adesivo colado nelas.
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
