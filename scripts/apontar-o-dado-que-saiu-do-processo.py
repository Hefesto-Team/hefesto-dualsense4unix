#!/usr/bin/env python3
"""O ponteiro que fica onde o dado morava — 20/09/2026."""

from __future__ import annotations

import argparse
import pathlib
import sys

RAIZ = pathlib.Path(__file__).resolve().parents[1]

OS_QUE_SAIRAM: dict[str, str] = {
    "METODO-DE-ISOLAMENTO.md": "",
    "COMO-OLHAR-A-TELA.md": "",
    "POLITICA-core-nunca-sai-da-maquina.md": "",
    "2026-08-29-A-REGUA-DE-TELA-como-se-prova-a-interface.md": "",
    "2026-09-03-O-TERCEIRO-NUMERO-a-paridade-com-a-gtk.md": "",
    "2026-09-07-O-COMO-DAS-21-o-gesto-exato-de-cada-linha.md":
        "sprints/arquivados",
    "2026-09-07-O-COMO-DO-MAPA-o-gesto-das-178-celulas.md":
        "sprints/arquivados",
}

MARCA = "ESTE ARQUIVO MUDOU DE CASA"


def folha(nome: str) -> str:
    """O ponteiro de um arquivo: onde ele está agora e por que saiu."""
    return (
        f"# {nome} — {MARCA}\n"
        "\n"
        f"Ele virou dado versionado em 20/09/2026 e mora em `docs/method/{nome}`.\n"
        "\n"
        "A razão é a ordem dela do mesmo dia, escolhida entre três: *\"mover o que\n"
        "as réguas precisam\"*. Régua lê este arquivo; `docs/process/` é\n"
        "`.gitignore:178`; e o que a régua lê tem de viajar no clone, senão ele\n"
        "some em toda máquina que não é a dela — que foi o que derrubou o\n"
        "`release.yml` e o gesto de 199 testes.\n"
        "\n"
        "Não edite esta folha: ela é um ponteiro. O conteúdo está no arquivo novo.\n"
    )


def alvos() -> list[tuple[pathlib.Path, str]]:
    """Os pares (caminho velho, texto do ponteiro)."""
    fora = []
    for nome, sub in OS_QUE_SAIRAM.items():
        velho = RAIZ / "docs" / "process"
        if sub:
            velho = velho / sub
        fora.append((velho / nome, folha(nome)))
    return fora


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--escrever", action="store_true",
                        help="escreve os ponteiros em vez de só conferir")
    opcoes = parser.parse_args(argv)

    pasta = RAIZ / "docs" / "process"
    if not pasta.is_dir():
        print("`docs/process/` não está nesta árvore — nada a apontar. "
              "(É o estado de todo clone limpo, e não é defeito.)")
        return 0

    faltando: list[pathlib.Path] = []
    for velho, texto in alvos():
        if velho.is_file() and MARCA in velho.read_text(encoding="utf-8"):
            continue
        if not opcoes.escrever:
            faltando.append(velho)
            continue
        velho.parent.mkdir(parents=True, exist_ok=True)
        velho.write_text(texto, encoding="utf-8")
        print(f"escrito: {velho.relative_to(RAIZ)}")

    if faltando:
        print("sem ponteiro (rode com `--escrever`):")
        for velho in faltando:
            print(f"  {velho.relative_to(RAIZ)}")
        return 1
    if not opcoes.escrever:
        print(f"os {len(OS_QUE_SAIRAM)} ponteiros estão no lugar.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
