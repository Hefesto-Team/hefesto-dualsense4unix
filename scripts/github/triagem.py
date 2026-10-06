#!/usr/bin/env python3
"""A triagem das issues: a de formulário sem a saída do `doctor` ganha o rótulo e o comando.

  triagem.py --evento EVENTO.json --repo DONO/NOME             diz o que faria (JSON numa linha)
  triagem.py --evento EVENTO.json --repo DONO/NOME --aplicar   faz, pelo `gh` (o `GH_TOKEN` vem do fluxo)

Quem a chama é `.github/workflows/rotulos.yml`, a cada issue aberta ou editada. A decisão é uma
função pura (`decidir`): o corpo da issue e os rótulos dela entram, e sai o que pôr, o que tirar e
se há o que comentar.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

# O título do campo nos formulários `bug.yml` e `jogo.yml`: o GitHub o escreve como `### Título` no corpo.
CAMPO = "Saída do doctor"
ROTULO = "precisa do doctor"
# Os formulários que pedem a saída: o rótulo de cada um (o `labels:` do formulário).
ROTULOS_QUE_PEDEM = ("bug", "jogo ou emulador")
SEM_RESPOSTA = {"", "_no response_", "n/a", "na", "nada", "-"}
# O mínimo para uma saída de `doctor` não ser só uma palavra solta.
MINIMO_DE_LETRAS = 20
COMENTARIO = (
    "Obrigado pelo relato. Para a gente conseguir repetir o problema, falta a saída do comando abaixo. "
    "Rode no terminal, edite a issue e cole o resultado no campo «Saída do doctor»:\n\n"
    "```\nhefesto-dualsense4unix doctor\n```\n"
)


def saida_do_campo(corpo: str) -> str | None:
    """O que a pessoa escreveu no campo do `doctor` (None quando o corpo não tem o campo)."""
    achou = re.search(
        rf"^### {re.escape(CAMPO)}[ \t]*\n(.*?)(?=^### |\Z)", corpo or "", re.DOTALL | re.MULTILINE)
    if achou is None:
        return None
    # o formulário embrulha o texto de um campo `render: shell` em uma cerca de código
    texto = re.sub(r"^```\w*\n?|\n?```\s*$", "", achou.group(1).strip())
    return texto.strip()


def decidir(corpo: str, rotulos: list[str], acao: str) -> dict[str, Any]:
    """O que fazer com a issue: `adicionar`, `remover` e `comentar` (só ao abrir)."""
    pede = any(r in rotulos for r in ROTULOS_QUE_PEDEM) or saida_do_campo(corpo) is not None
    if not pede:
        return {"adicionar": [], "remover": [], "comentar": False}
    saida = saida_do_campo(corpo)
    falta = saida is None or saida.lower() in SEM_RESPOSTA or len(saida) < MINIMO_DE_LETRAS
    if falta and ROTULO not in rotulos:
        return {"adicionar": [ROTULO], "remover": [], "comentar": acao == "opened"}
    if not falta and ROTULO in rotulos:
        return {"adicionar": [], "remover": [ROTULO], "comentar": False}
    return {"adicionar": [], "remover": [], "comentar": False}


def _gh(*args: str) -> None:
    subprocess.run(["gh", *args], check=True)


def principal(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").split("\n", 1)[0])
    ap.add_argument("--evento", type=Path, required=True)
    ap.add_argument("--repo", required=True)
    ap.add_argument("--aplicar", action="store_true")
    a = ap.parse_args(argv)
    evento = json.loads(a.evento.read_text(encoding="utf-8"))
    issue = evento["issue"]
    if "pull_request" in issue:
        print("triagem: é um PR, não uma issue; nada a fazer")
        return 0
    rotulos = [x["name"] for x in issue.get("labels", [])]
    d = decidir(issue.get("body") or "", rotulos, evento.get("action", ""))
    print(json.dumps(d, ensure_ascii=False))
    if not a.aplicar:
        return 0
    numero = str(issue["number"])
    for r in d["adicionar"]:
        _gh("issue", "edit", numero, "--repo", a.repo, "--add-label", r)
    for r in d["remover"]:
        _gh("issue", "edit", numero, "--repo", a.repo, "--remove-label", r)
    if d["comentar"]:
        _gh("issue", "comment", numero, "--repo", a.repo, "--body", COMENTARIO)
    return 0


if __name__ == "__main__":
    sys.exit(principal())
