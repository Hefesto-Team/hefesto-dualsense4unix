#!/usr/bin/env python3
"""gravar_a_intensidade_da_cena.py — a intensidade separa a cena calma do combate?

A-INTENSIDADE-DA-CENA-REGE-O-QUE-O-HEFESTO-SOMA-01 (22/10/2026). A prova vem antes da força: a
graduação do que o Hefesto soma só liga se a intensidade calculada separar os trechos que a
pessoa marca à mão, em três gêneros. Duas metades:

1. O GRAVADOR (``--gravar SEGUNDOS --jogo NOME --genero GENERO --saida ARQUIVO``): pergunta
   ``daemon.state_full`` ao serviço no ar a cada 100 ms e guarda o bloco ``intensidade_da_cena``
   (a energia do som do jogo, as bordas do rumble e as do dedo por segundo, a intensidade e a
   faixa). Só LÊ o estado; é da bancada, com o jogo aberto num estilo que liga o motor do tato
   (Ação, por exemplo). A marca do trecho vem do teclado deste terminal, uma letra e Enter:
   ``c`` calmo, ``t`` tenso, ``x`` combate, ``-`` fora de trecho. Nenhum endereço é gravado.
2. A ANÁLISE (``--analisar ARQUIVO...``): pura, lê as gravações e imprime, por jogo, a mediana
   da intensidade e de cada sinal em cada trecho. Separa quando, em todos os jogos, a mediana do
   combate fica acima da do calmo; o veredito só vale com três gêneros. ``--marcas ARQUIVO`` (uma
   linha ``inicio fim rótulo`` por trecho, em segundos) troca as marcas do teclado de uma
   gravação, para quem marcou depois, pelo vídeo.

A gravação: a primeira linha JSON é ``{"jogo", "genero"}``; as seguintes,
``{"t": s, "marca": rótulo ou null, "cena": {...}}``, uma por pergunta.

rc: 0 separa nos três gêneros; 1 não separa (a sprint para com o número); 3 falta gênero ou
trecho; 4 sem dado.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import threading
import time
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

_AQUI = Path(__file__).resolve().parent
_SRC = _AQUI.parent.parent / "src"
if _SRC.is_dir() and str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

RC_SEPARA = 0
RC_NAO_SEPARA = 1
RC_FALTA = 3
RC_SEM_DADO = 4
INTERVALO_DA_PERGUNTA_S = 0.1
GENEROS_NECESSARIOS = 3

CALMO = "calmo"
TENSO = "tenso"
COMBATE = "combate"
TRECHOS = (CALMO, TENSO, COMBATE)
TECLAS = {"c": CALMO, "t": TENSO, "x": COMBATE, "-": None}
SINAIS = ("intensidade", "energia", "rumble_por_s", "dedo_por_s")


@dataclass
class Gravacao:
    """Uma sessão de um jogo: o cabeçalho e as perguntas, em ordem de tempo."""

    jogo: str
    genero: str
    perguntas: list[dict[str, Any]] = field(default_factory=list)


def ler_gravacao(texto: str) -> Gravacao:
    """A gravação de um jogo; levanta ``ValueError`` sem cabeçalho ou sem pergunta nenhuma."""
    linhas = [json.loads(linha) for linha in texto.splitlines() if linha.strip()]
    cabecalho = next((x for x in linhas if isinstance(x, dict) and "jogo" in x), None)
    if cabecalho is None:
        raise ValueError("gravação sem o cabeçalho do jogo")
    perguntas = [x for x in linhas if isinstance(x, dict) and isinstance(x.get("cena"), dict)]
    if not perguntas:
        raise ValueError("gravação sem nenhuma pergunta ao estado")
    perguntas.sort(key=lambda x: float(x.get("t", 0.0)))
    return Gravacao(str(cabecalho["jogo"]), str(cabecalho.get("genero", "")), perguntas)


def ler_marcas(texto: str) -> list[tuple[float, float, str]]:
    """As marcas escritas depois: ``inicio fim rótulo`` por linha; ``#`` comenta."""
    marcas = []
    for linha in texto.splitlines():
        partes = linha.split("#", 1)[0].split()
        if not partes:
            continue
        if len(partes) != 3 or partes[2] not in TRECHOS:
            raise ValueError(f"marca ilegível: {linha!r}")
        marcas.append((float(partes[0]), float(partes[1]), partes[2]))
    return marcas


def com_as_marcas(gravacao: Gravacao, marcas: Iterable[tuple[float, float, str]]) -> Gravacao:
    """A gravação com a marca de cada pergunta trocada pela do arquivo (fora delas, nenhuma)."""
    lista = list(marcas)
    perguntas = []
    for pergunta in gravacao.perguntas:
        t = float(pergunta.get("t", 0.0))
        rotulo = next((r for inicio, fim, r in lista if inicio <= t < fim), None)
        perguntas.append({**pergunta, "marca": rotulo})
    return Gravacao(gravacao.jogo, gravacao.genero, perguntas)


def _numero(valor: Any) -> float | None:
    if isinstance(valor, bool) or not isinstance(valor, int | float):
        return None
    return float(valor)


def medianas_por_trecho(gravacao: Gravacao) -> dict[str, dict[str, float]]:
    """``{trecho: {sinal: mediana}}`` das perguntas com jogo marcadas em cada trecho."""
    valores: dict[str, dict[str, list[float]]] = {}
    for pergunta in gravacao.perguntas:
        rotulo = pergunta.get("marca")
        cena = pergunta["cena"]
        if rotulo not in TRECHOS or not cena.get("jogo"):
            continue
        dele = valores.setdefault(rotulo, {})
        for sinal in SINAIS:
            numero = _numero(cena.get(sinal))
            if numero is not None:
                dele.setdefault(sinal, []).append(numero)
    return {
        rotulo: {sinal: statistics.median(lista) for sinal, lista in sinais.items() if lista}
        for rotulo, sinais in valores.items()
    }


@dataclass(frozen=True)
class Veredito:
    rc: int
    motivo: str


def veredito(gravacoes: Sequence[Gravacao]) -> Veredito:
    """Separa quando o combate fica acima do calmo em todo jogo, e há três gêneros."""
    if not gravacoes:
        return Veredito(RC_SEM_DADO, "nenhuma gravação")
    for gravacao in gravacoes:
        medianas = medianas_por_trecho(gravacao)
        calmo = medianas.get(CALMO, {}).get("intensidade")
        combate = medianas.get(COMBATE, {}).get("intensidade")
        if calmo is None or combate is None:
            return Veredito(RC_FALTA, f"{gravacao.jogo}: falta trecho calmo ou de combate marcado")
        if combate <= calmo:
            return Veredito(
                RC_NAO_SEPARA,
                f"{gravacao.jogo}: a mediana do combate ({combate:.3f}) não passa a do calmo "
                f"({calmo:.3f})")
    generos = {g.genero for g in gravacoes if g.genero}
    if len(generos) < GENEROS_NECESSARIOS:
        return Veredito(
            RC_FALTA, f"separa, mas em {len(generos)} gênero(s); a prova pede {GENEROS_NECESSARIOS}")
    return Veredito(RC_SEPARA, f"separa nos {len(generos)} gêneros")


def relatorio(gravacoes: Sequence[Gravacao]) -> str:
    """A tabela de cada jogo: trecho por linha, a mediana de cada sinal por coluna."""
    linhas = []
    for gravacao in gravacoes:
        linhas.append(f"{gravacao.jogo} ({gravacao.genero or 'gênero não dito'}), "
                      f"{len(gravacao.perguntas)} perguntas")
        medianas = medianas_por_trecho(gravacao)
        linhas.append("  trecho   " + "  ".join(f"{s:>12}" for s in SINAIS))
        for rotulo in TRECHOS:
            dele = medianas.get(rotulo)
            if dele is None:
                linhas.append(f"  {rotulo:<8} (sem pergunta marcada)")
                continue
            linhas.append(f"  {rotulo:<8} " + "  ".join(
                f"{dele[s]:>12.3f}" if s in dele else f"{'-':>12}" for s in SINAIS))
    return "\n".join(linhas)


class _Marcador:
    """Lê as letras do teclado numa thread; a marca vigente vale para as perguntas seguintes."""

    def __init__(self) -> None:
        self.marca: str | None = None
        self.fim = threading.Event()

    def ouvir(self, entrada: Iterable[str]) -> None:
        for linha in entrada:
            letra = linha.strip().lower()
            if letra == "q":
                break
            if letra in TECLAS:
                self.marca = TECLAS[letra]
                print(f"  trecho: {self.marca or 'fora'}", flush=True)
        self.fim.set()


def gravar(segundos: float, marcador: _Marcador) -> list[dict[str, Any]]:
    """Bancada: pergunta o estado ao serviço no ar por ``segundos`` (só leitura)."""
    from hefesto_dualsense4unix.app.ipc_bridge import _run_call

    perguntas: list[dict[str, Any]] = []
    inicio = time.monotonic()
    while time.monotonic() - inicio < segundos and not marcador.fim.is_set():
        estado = _run_call("daemon.state_full") or {}
        cena = estado.get("intensidade_da_cena")
        if isinstance(cena, dict):
            perguntas.append({
                "t": round(time.monotonic() - inicio, 3), "marca": marcador.marca, "cena": cena})
        time.sleep(INTERVALO_DA_PERGUNTA_S)
    return perguntas


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="A intensidade da cena separa o calmo do combate?")
    p.add_argument("--gravar", type=float, metavar="SEGUNDOS")
    p.add_argument("--jogo", default="")
    p.add_argument("--genero", default="")
    p.add_argument("--saida", type=Path)
    p.add_argument("--analisar", type=Path, nargs="+", metavar="ARQUIVO")
    p.add_argument("--marcas", type=Path, metavar="ARQUIVO",
                   help="com uma gravação só: as marcas escritas depois, no lugar das do teclado")
    return p


def _analisar(args: argparse.Namespace) -> int:
    try:
        gravacoes = [ler_gravacao(c.read_text(encoding="utf-8")) for c in args.analisar]
    except (OSError, ValueError) as erro:
        print(f"SEM DADO: {erro}")
        return RC_SEM_DADO
    if args.marcas is not None:
        if len(gravacoes) != 1:
            print("RECUSADO: --marcas vale para uma gravação só")
            return 2
        gravacoes = [com_as_marcas(gravacoes[0], ler_marcas(args.marcas.read_text("utf-8")))]
    print(relatorio(gravacoes))
    resultado = veredito(gravacoes)
    print(resultado.motivo)
    return resultado.rc


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.analisar:
        return _analisar(args)
    if args.gravar is None or args.saida is None or not args.jogo:
        print("RECUSADO: --gravar pede --jogo e --saida (a gravação é o recibo)")
        return 2
    marcador = _Marcador()
    threading.Thread(target=marcador.ouvir, args=(sys.stdin,), daemon=True).start()
    print("c calmo, t tenso, x combate, - fora de trecho, q encerra (letra e Enter)", flush=True)
    perguntas = gravar(args.gravar, marcador)
    cabecalho = {"jogo": args.jogo, "genero": args.genero}
    args.saida.write_text(
        "".join(json.dumps(x, ensure_ascii=False) + "\n" for x in [cabecalho, *perguntas]),
        encoding="utf-8")
    if not perguntas:
        print("SEM DADO: o estado não trouxe o bloco intensidade_da_cena")
        return RC_SEM_DADO
    gravacao = Gravacao(args.jogo, args.genero, perguntas)
    print(relatorio([gravacao]))
    return RC_SEPARA


if __name__ == "__main__":
    sys.exit(main())
