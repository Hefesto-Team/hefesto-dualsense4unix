#!/usr/bin/env python3
"""Falha se uma faixa de MAC SINTÉTICA de teste aparecer no `config_dir()` real.

T-06 (ONDA0-Z7 · O AMBIENTE PRESUMIDO 01, 24/08/2026). Medido na bancada dela
em 23/08/2026: quatro registros com endereços da faixa `aabbcc` vazaram para
`~/.config/hefesto-dualsense4unix/controllers.json` — a mesa de produção dela,
não um fixture — empurrando os quatro DualSense REAIS dela das posições 1-4
para 1, 6, 7 e 8. `grep -rl aabbcc tests/ | wc -l` achou 91 arquivos de teste
usando a faixa; algum deles escreveu no disco dela em vez de num diretório
isolado (T-06 também rastreia a CAUSA — ver `docs/process/agentes/` da leva).

As faixas sintéticas da casa (CLAUDE.md, `scripts/check_test_data.sh`),
verificadas nas duas grafias — com `:` e sem:

  aabbcc  / aa:bb:cc
  02fe00  / 02:fe:00
  e8473a  / e8:47:3a

Uso (CI, e à mão):
    python3 scripts/check_faixa_sintetica.py
    python3 scripts/check_faixa_sintetica.py --config-dir /algum/lugar   # testes
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

# As três faixas sintéticas da casa. Cada uma casa nas DUAS grafias: com ':'
# entre os três primeiros octetos (aa:bb:cc...) e sem (aabbcc...) — o
# `controllers.json` medido em 23/08 usava a grafia sem ':'.
FAIXAS_SINTETICAS = ("aabbcc", "02fe00", "e8473a")


def _padrao_para(faixa: str) -> re.Pattern[str]:
    """Um regex por faixa, casando as duas grafias, sem diferenciar maiúscula."""
    a, b, c = faixa[0:2], faixa[2:4], faixa[4:6]
    return re.compile(rf"(?i){a}:?{b}:?{c}(?::?[0-9a-f]{{2}}){{0,3}}")


_PADROES = {faixa: _padrao_para(faixa) for faixa in FAIXAS_SINTETICAS}

#: Extensões que fazem sentido varrer — o `config_dir()` do Hefesto só guarda
#: JSON, texto e (raramente) log; nada binário mora lá por contrato.
_EXTENSOES_VARRIDAS = {".json", ".txt", ".log", ".conf", ".ini", ""}


def _config_dir() -> Path:
    from hefesto_dualsense4unix.utils.xdg_paths import config_dir

    return config_dir()


def achados(diretorio: Path) -> list[str]:
    """Varre o diretório e devolve uma linha por ocorrência: arquivo:linha: valor."""
    linhas: list[str] = []
    if not diretorio.is_dir():
        return linhas
    for caminho in sorted(diretorio.rglob("*")):
        if not caminho.is_file():
            continue
        if caminho.suffix.lower() not in _EXTENSOES_VARRIDAS:
            continue
        try:
            texto = caminho.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for numero, linha_texto in enumerate(texto.splitlines(), start=1):
            for faixa, padrao in _PADROES.items():
                for m in padrao.finditer(linha_texto):
                    linhas.append(
                        f"  {caminho}:{numero}: faixa sintética '{faixa}' -> {m.group(0)!r}"
                    )
    return linhas


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config-dir",
        type=Path,
        default=None,
        help="diretório a varrer (default: config_dir() resolvido de verdade)",
    )
    args = parser.parse_args(argv)

    diretorio = args.config_dir if args.config_dir is not None else _config_dir()
    encontrados = achados(diretorio)

    if encontrados:
        print(f"FAIL: faixa sintética de teste encontrada em '{diretorio}':")
        print("\n".join(encontrados))
        print(
            "  Isto é a mesa de produção, não um fixture de teste. Um teste que "
            "escreveu aqui não está isolado do ambiente real — corrija o teste "
            "para usar um config_dir() dublê (tmp_path + XDG_CONFIG_HOME), não "
            "apague o achado às cegas: a decisão sobre o que já está gravado é "
            "de quem é dono da máquina."
        )
        return 1

    print(f"OK: nenhuma faixa sintética em '{diretorio}'.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
