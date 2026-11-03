#!/usr/bin/env python3
"""a_corrida_do_get_report_no_pad.py — o pad virtual responde algum feature zerado com sucesso?

O começo de partida de um jogo de SDL3: abre os pads de uma vez e lê o 0x05, o 0x09, o 0x20 e o
0x22 em paralelo, com o buffer de 128 bytes do SDL e do Wine. Na metade da rodada ele pede a
recriação de um pad (trocar o modo ou religar o controle), e segue lendo pela recriação. Cada
resposta cai numa de três classes: os bytes, o erro (com o errno) ou o zerado com sucesso, que
é o firmware 0x0000 que o jogo lê. Rode pelos dois caminhos (uhid e gadget) e com o físico
pelo cabo e pelo rádio. `--fisicos` lê também os físicos: a classe que o aparelho responde.

Saída 1 quando algum pad respondeu zerado com sucesso.
"""

from __future__ import annotations

import argparse
import array
import errno
import fcntl
import os
import sys
import threading
import time
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from comum import (
    Aparelho,
    PortaFechadaError,
    abrir_no_hidraw,
    cabecalho_do_instrumento,
    descobrir_aparelhos,
    fisicos,
    resumo,
    tabela,
    vpads,
)

IDS = (0x05, 0x09, 0x20, 0x22)
BUFFER = 128
ZERADO = "zerado com sucesso"


def _hidiocgfeature(tamanho: int) -> int:
    return (3 << 30) | (tamanho << 16) | (ord("H") << 8) | 0x07


def classificar(report_id: int, dados: bytes | None, erro: int | None) -> str:
    """`ok N B`, `erro <nome>` ou o zerado com sucesso."""
    if erro is not None:
        return f"erro {errno.errorcode.get(erro, erro)}"
    assert dados is not None
    if not any(dados[1:]):
        return ZERADO
    if dados[0] != report_id:
        return f"id trocado 0x{dados[0]:02x}"
    return f"ok {len(dados)} B"


def ler_uma_vez(caminho: str, report_id: int) -> tuple[str, float]:
    """Um GET_FEATURE de 128 bytes num nó aberto agora: a classe e os milissegundos."""
    inicio = time.monotonic()
    try:
        no = abrir_no_hidraw(caminho, escrita=False)
    except (PortaFechadaError, OSError) as exc:
        return (f"sem nó ({exc.__class__.__name__})", 0.0)
    try:
        buffer = array.array("B", [0] * BUFFER)
        buffer[0] = report_id
        try:
            lidos = fcntl.ioctl(no.fd, _hidiocgfeature(BUFFER), buffer, True)
        except OSError as exc:
            return (classificar(report_id, None, exc.errno), (time.monotonic() - inicio) * 1e3)
        return (
            classificar(report_id, bytes(buffer[:lidos]), None),
            (time.monotonic() - inicio) * 1e3,
        )
    finally:
        no.fechar()


def correr(aparelhos: list[Aparelho], segundos: float) -> tuple[
    dict[tuple[str, int], Counter[str]], dict[tuple[str, int], list[float]]
]:
    """Um fio por aparelho e por id, lendo sem pausa até o prazo."""
    classes: dict[tuple[str, int], Counter[str]] = defaultdict(Counter)
    tempos: dict[tuple[str, int], list[float]] = defaultdict(list)
    trava = threading.Lock()
    fim = time.monotonic() + segundos

    def ler(aparelho: Aparelho, report_id: int) -> None:
        while time.monotonic() < fim:
            atual = {a.apelido: a for a in descobrir_aparelhos()}.get(aparelho.apelido)
            if atual is None:
                with trava:
                    classes[(aparelho.apelido, report_id)]["sem nó (recriação)"] += 1
                time.sleep(0.05)
                continue
            classe, ms = ler_uma_vez(atual.caminho_hidraw, report_id)
            with trava:
                classes[(aparelho.apelido, report_id)][classe] += 1
                tempos[(aparelho.apelido, report_id)].append(ms)

    fios = [
        threading.Thread(target=ler, args=(aparelho, report_id), daemon=True)
        for aparelho in aparelhos
        for report_id in IDS
    ]
    for fio in fios:
        fio.start()
    time.sleep(segundos / 2)
    print(">> AGORA: troque o modo de um controle ou religue um deles; a leitura segue.")
    for fio in fios:
        fio.join()
    return classes, tempos


def _p99(valores: list[float]) -> float:
    if not valores:
        return 0.0
    ordenados = sorted(valores)
    return ordenados[min(len(ordenados) - 1, int(len(ordenados) * 0.99))]


def main() -> int:
    analisador = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    analisador.add_argument("--segundos", type=float, default=20.0)
    analisador.add_argument("--fisicos", action="store_true",
                            help="lê também os físicos (a classe que o aparelho responde)")
    args = analisador.parse_args()
    print(cabecalho_do_instrumento(
        "a_corrida_do_get_report_no_pad",
        "o pad virtual responde algum feature zerado com sucesso?",
        bibliotecas=[],
    ))
    mesa = descobrir_aparelhos()
    alvos = vpads(mesa) + (fisicos(mesa) if args.fisicos else [])
    if not vpads(mesa):
        print(resumo("nenhum pad virtual na mesa: abra o jogo ou ligue o co-op antes"))
        return 2
    print(f"lendo {', '.join(a.apelido for a in alvos)} por {args.segundos:.0f} s, "
          f"ids {', '.join(f'0x{i:02x}' for i in IDS)}, buffer de {BUFFER} B")
    classes, tempos = correr(alvos, args.segundos)
    linhas = []
    zerados = 0
    for (apelido, report_id), contagem in sorted(classes.items()):
        if apelido.startswith("vpad"):
            zerados += contagem[ZERADO]
        ms = tempos[(apelido, report_id)]
        linhas.append([
            apelido, f"0x{report_id:02x}",
            "; ".join(f"{classe} ×{n}" for classe, n in contagem.most_common()),
            f"{_p99(ms):.1f}", f"{max(ms, default=0.0):.1f}",
        ])
    print(tabela(["aparelho", "id", "respostas", "p99 ms", "máx ms"], linhas))
    if zerados:
        print(resumo(f"{zerados} resposta(s) zerada(s) com sucesso num pad virtual: o defeito"))
        return 1
    print(resumo("nenhum pad virtual respondeu zerado com sucesso"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
