#!/usr/bin/env python3
"""conferir-as-citacoes-da-07-na-paridade.py — a citação da 07 na paridade aponta o sinal.

A célula `html_onde` de `docs/data/paridade-gtk-html.csv` guarda `a07_lancadores.py:N`, só o
número. O `validar-citacoes-de-linha.py` confere que a linha existe; o `reapontar-citacoes.py`
leva o número quando o código anda. Nenhum dos dois sabe PARA ONDE a citação devia apontar: uma
varredura em massa a reescreveu sem olhar o conteúdo, e o desvio ficou verde.

Aqui a pergunta é a da própria linha do CSV: o `sinal` dela (o símbolo que a feature descreve)
está a até ``JANELA`` linhas da linha citada? Só entram as linhas cujo `sinal_escopo` é o
`a07_lancadores.py`: citar a 07 numa linha cujo sinal mora em outro arquivo não tem contra o que
conferir, e é erro (a citação sai e a célula diz o símbolo).

    scripts/conferir-as-citacoes-da-07-na-paridade.py --conferir
    scripts/conferir-as-citacoes-da-07-na-paridade.py --conferir --csv X.csv --arquivo Y.py

Saída 0 se nenhuma citação cai fora; 1 com a lista; 2 se o CSV ou o arquivo não abre.
"""
from __future__ import annotations

import argparse
import csv
import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
CSV = RAIZ / "docs" / "data" / "paridade-gtk-html.csv"
ARQUIVO = "src/hefesto_dualsense4unix/interface/pacotes/a07_lancadores.py"
JANELA = 3

CITACAO = re.compile(r"(?P<arq>[A-Za-z0-9_./-]*a07_lancadores\.py):(?P<a>\d+)(?:-(?P<b>\d+))?")
IDENTIFICADOR = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


def chave_do_sinal(sinal: str) -> str:
    """O último identificador do sinal: `pdj.jogos_instalados()` -> `jogos_instalados`."""
    achados = IDENTIFICADOR.findall(sinal)
    return achados[-1] if achados else ""


def conferir(csv_: Path, arquivo: Path) -> tuple[list[str], int]:
    """``(falhas, quantas citações da 07 foram conferidas)``."""
    corpo = arquivo.read_text(encoding="utf-8").split("\n")
    with csv_.open(encoding="utf-8", newline="") as f:
        linhas = list(csv.DictReader(f))
    falhas: list[str] = []
    conferidas = 0
    for n_csv, linha in enumerate(linhas, start=2):
        citacoes = [c for c in CITACAO.finditer(linha.get("html_onde", ""))]
        if not citacoes:
            continue
        onde = f"{csv_.name} registro {n_csv} ({linha['aba']}: {linha['feature'][:50]})"
        sinal = linha.get("sinal", "")
        chave = chave_do_sinal(sinal)
        no_arquivo = linha.get("sinal_escopo", "").endswith("a07_lancadores.py")
        achar = re.compile(rf"(?<![A-Za-z0-9_]){re.escape(chave)}(?![A-Za-z0-9_])") if chave else None
        lugares = [i for i, t in enumerate(corpo, start=1) if achar and achar.search(t)]
        for c in citacoes:
            conferidas += 1
            citada = c.group(0)
            if not no_arquivo:
                falhas.append(
                    f"sem-sinal: {onde}\n    cita {citada}, mas o sinal {sinal!r} mora em "
                    f"{linha.get('sinal_escopo')!r}: a citação não tem contra o que ser conferida.")
                continue
            primeira = int(c.group("a"))
            ultima = int(c.group("b") or primeira)
            if not any(primeira - JANELA <= i <= ultima + JANELA for i in lugares):
                falhas.append(
                    f"longe-do-sinal: {onde}\n    cita {citada}, e `{chave}` (do sinal {sinal!r}) "
                    f"não está a {JANELA} linhas dela; mora em "
                    f"{', '.join(map(str, lugares)) or 'lugar nenhum do arquivo'}.")
    return falhas, conferidas


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--conferir", action="store_true", help="confere e sai com 1 se alguma cai fora")
    ap.add_argument("--csv", type=Path, default=CSV)
    ap.add_argument("--arquivo", type=Path, default=RAIZ / ARQUIVO)
    args = ap.parse_args()
    if not args.conferir:
        ap.print_usage(sys.stderr)
        return 2
    try:
        falhas, conferidas = conferir(args.csv, args.arquivo)
    except OSError as erro:
        print(f"conferir-as-citacoes-da-07: não abriu {erro.filename}: {erro.strerror}", file=sys.stderr)
        return 2
    for f in falhas:
        print(f)
    print(f"citações da 07 na paridade: {len(falhas)} de {conferidas} fora do sinal")
    return 1 if falhas else 0


if __name__ == "__main__":
    sys.exit(main())
