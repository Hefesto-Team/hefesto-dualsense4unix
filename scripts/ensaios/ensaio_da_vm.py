#!/usr/bin/env python3
"""A montagem da rodada do Proton fora da máquina de quem joga: o que o runner sustenta, por perna.

Cumpre o `Ensaio` de `a_rodada_do_proton_candidato.py`. O que o runner sustenta vem da
`sonda.txt` do banco de prova (`scripts/banco_de_prova/sonda.sh`): o `casa_radio`, o `casa_cabo`
e o servidor de som que o endpoint de háptica e a fonte do microfone pedem. A perna a que falta
uma peça sai do recibo como «não medida», com o nome da peça, e nunca como «passou».
"""
from __future__ import annotations

import subprocess
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from a_rodada_do_proton_candidato import Caso, MedidaDoOutroLado

NO_RUNNER = "no_runner"

MONTAGEM_DAS_PROVAS = (
    "a montagem das três provas (o plástico que grava o report 0x02, o endpoint ancorado no "
    "pad e a fonte vestida) ainda não se monta: espera a medida do passo 0"
)

Rodar = Callable[[Sequence[str]], int]


def rodar_de_verdade(argv: Sequence[str]) -> int:
    """O código de saída do comando; o que não existe ou não responde a tempo é ``127``."""
    try:
        return subprocess.run(list(argv), capture_output=True, timeout=10, check=False).returncode
    except (OSError, subprocess.TimeoutExpired):
        return 127


def ler_a_medida(caminho: Path | None) -> dict[str, str]:
    """As linhas ``chave=valor`` da `sonda.txt`; sem o arquivo, nada foi medido."""
    if caminho is None or not caminho.is_file():
        return {}
    medida: dict[str, str] = {}
    for linha in caminho.read_text(encoding="utf-8", errors="replace").splitlines():
        chave, igual, valor = linha.partition("=")
        if igual:
            medida[chave.strip()] = valor.strip()
    return medida


class EnsaioDaVm:
    """O ensaio do runner: diz por perna o que falta, e só monta o que a medida sustenta."""

    def __init__(self, medida: Path | None = None, rodar: Rodar = rodar_de_verdade) -> None:
        self.medida = ler_a_medida(medida)
        self.som = rodar(("pactl", "info")) == 0

    def sustenta(self, caso: Caso) -> str | None:
        """``None`` quando a perna se mede neste runner; senão a peça que falta."""
        if not self.medida:
            return "sem a sonda.txt do banco de prova: o runner não foi medido"
        chave = "casa_radio" if caso.transporte == "radio" else "casa_cabo"
        if self.medida.get(chave) != NO_RUNNER:
            medido = self.medida.get(chave, "")
            return f"o {caso.transporte} não se monta neste runner ({chave}={medido})"
        if not self.som:
            return "sem servidor de som para o endpoint de háptica e a fonte do microfone"
        return MONTAGEM_DAS_PROVAS

    def montar(self, caso: Caso) -> dict[str, str]:
        raise RuntimeError(self.sustenta(caso) or MONTAGEM_DAS_PROVAS)

    def medir(self) -> MedidaDoOutroLado:
        raise RuntimeError(MONTAGEM_DAS_PROVAS)

    def desmontar(self) -> None:
        return None
