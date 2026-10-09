#!/usr/bin/env python3
"""a_faixa_do_receptor.py — os mapas AFH sem e com o receptor 2,4 GHz, e a resposta da procura.

A-FAIXA-DO-TECLADO-SE-ACHA-01 (09/10/2026).

A PERGUNTA
----------
O «Descobrir a faixa» da Conexões (``receptor_sem_fio.Descoberta``) compara os canais que os
adaptadores Bluetooth evitam sem e com o receptor na porta. O teclado dela deu «não achei», e o
«não achei» juntava três medidas: sem enlace clássico não há mapa (1); o receptor salta de canal e
deixa canais espalhados (2); o AFH leva mais que 25 s para marcar a faixa (3). A procura agora diz
qual delas viu; este ensaio grava os mapas na bancada e reproduz a procura sobre eles, trocando os
números um por um.

O QUE ELE GRAVA
---------------
Somente leitura: a cada ``--cada`` segundos, por ``--segundos``, o mapa AFH de cada enlace clássico
de cada adaptador (``Read AFH Channel Map``, o mesmo que o daemon lê a cada 10 s), reduzido aos
canais que o adaptador evita em todos os enlaces. Grava o nome do adaptador (``hci0``) e os canais;
nunca o endereço de ninguém. Não escreve no aparelho nem no ``~/.config``.

USO
---
    a_faixa_do_receptor.py gravar --momento sem --saida mapas.jsonl --medir   # o receptor fora
    a_faixa_do_receptor.py gravar --momento com --saida mapas.jsonl --medir   # o receptor dentro
    a_faixa_do_receptor.py classificar mapas.jsonl [--espera 25 --ate 120 --minimos 3 --salto 6]

OS INTERRUPTORES (trocar X por Y na bancada sem editar código)
--------------------------------------------------------------
``--espera`` / ``HEFESTO_FAIXA_ESPERA_S`` (25: a leitura que fecha cada medida),
``--ate`` / ``HEFESTO_FAIXA_ATE_S`` (25: até quando a medida «com ele» relê se nada mudou),
``--minimos`` / ``HEFESTO_FAIXA_MINIMOS`` (3: canais seguidos que fazem uma faixa),
``--salto`` / ``HEFESTO_FAIXA_SALTO`` (6: canais espalhados que provam o salto),
``--segundos`` / ``HEFESTO_FAIXA_SEGUNDOS`` (120) e ``--cada`` / ``HEFESTO_FAIXA_CADA_S`` (5) na gravação.

As réguas: ``tests/unit/test_a_faixa_do_teclado_se_acha.py``.
"""
from __future__ import annotations

import argparse
import contextlib
import functools
import json
import os
import sys
import time
from collections.abc import Callable, Iterator, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

_AQUI = Path(__file__).resolve().parent
_RAIZ = _AQUI.parents[1]
if str(_RAIZ / "src") not in sys.path:
    sys.path.insert(0, str(_RAIZ / "src"))

from hefesto_dualsense4unix.integrations import receptor_sem_fio as rx

INSTRUMENTO = "a_faixa_do_receptor"
VERSAO = 1
MOMENTOS = ("sem", "com")
SEGUNDOS = 120.0
CADA_S = 5.0
CHAVE_DO_ENSAIO = "receptor"
RECUSA_SEM_MEDIR = "sem --medir: só descrevo o plano, nada toca"

Mapas = Mapping[str, Sequence[int] | None]


def _do_ambiente(nome: str, padrao: str) -> str:
    return os.environ.get(nome, "").strip() or padrao


# --------------------------------------------------------------- a gravação


def mapas_de_agora(
    adaptadores: Callable[[], list[int] | None],
    conexoes: Callable[[int], Sequence[object] | None],
    ler_mapa: Callable[[int, int], object | None],
) -> dict[str, list[int] | None]:
    """``{"hciN": canais que o adaptador evita em todos os enlaces clássicos}``; ``None`` sem mapa."""
    from hefesto_dualsense4unix.integrations import ar_do_adaptador as ar

    saida: dict[str, list[int] | None] = {}
    for hci in adaptadores() or ():
        lidos: dict[str, ar.EnlaceLido] = {}
        for n, conexao in enumerate(conexoes(hci) or ()):
            if getattr(conexao, "tipo", None) != ar.TIPO_ACL:
                continue
            mapa = ler_mapa(hci, int(getattr(conexao, "handle", 0)))
            evitados = getattr(mapa, "evitados", None)
            # a chave é só a ordem: o endereço do aparelho não sai daqui
            lidos[str(n)] = ar.EnlaceLido(le=False, canais_evitados=evitados)
        canais = ar.canais_evitados_pelo_adaptador(lidos)
        saida[f"hci{hci}"] = list(canais) if canais is not None else None
    return saida


def gravar(
    ler: Callable[[], Mapas], *, momento: str, segundos: float, cada: float, saida: Path,
    dormir: Callable[[float], None] = time.sleep,
) -> int:
    """Uma leitura a cada ``cada`` segundos, de 0 a ``segundos``; devolve quantas gravou."""
    saida.parent.mkdir(parents=True, exist_ok=True)
    gravadas = 0
    with saida.open("a", encoding="utf-8") as arquivo:
        t = 0.0
        while t <= segundos:
            registro = {"momento": momento, "t": t, "adaptadores": dict(ler()),
                        "instrumento": INSTRUMENTO, "versão": VERSAO}
            arquivo.write(json.dumps(registro, ensure_ascii=False) + "\n")
            gravadas += 1
            dormir(cada)
            t += cada
    return gravadas


def ler_sessao(caminho: Path) -> list[dict[str, object]]:
    """As leituras de uma sessão (JSONL) ou de uma tabela guardada (``{"leituras": [...]}``)."""
    texto = caminho.read_text(encoding="utf-8").strip()
    if texto.startswith("{") and "\n{" not in texto:
        dados = json.loads(texto)
        return list(dados["leituras"])
    return [json.loads(li) for li in texto.splitlines() if li.strip()]


# --------------------------------------------------------------- a procura, reproduzida


@dataclass(frozen=True)
class Fim:
    passo: str
    banda: tuple[int, int] | None
    causa: str
    canais: tuple[int, ...]
    frase: str


@contextlib.contextmanager
def constantes(**trocas: float | None) -> Iterator[None]:
    """Troca as constantes da procura só durante o ``with`` (o interruptor do ensaio)."""
    antes = {nome: getattr(rx, nome) for nome, valor in trocas.items() if valor is not None}
    try:
        for nome, valor in trocas.items():
            if valor is not None:
                setattr(rx, nome, type(antes[nome])(valor))
        yield
    finally:
        for nome, valor in antes.items():
            setattr(rx, nome, valor)


def reproduzir(
    leituras: Sequence[Mapping[str, object]], *, espera: float | None = None,
    ate: float | None = None, minimos: int | None = None, salto: int | None = None,
) -> Fim:
    """O gesto inteiro sobre as leituras guardadas: tira, mede sem, põe, mede com.

    Cada medida lê o mapa guardado do instante ``t`` mais próximo por baixo; o relógio anda de
    ``CADA_S`` em ``CADA_S``, como o tique da Conexões.
    """
    with constantes(ESPERA_DA_MEDIDA_S=espera, ESPERA_ATE_O_MAPA_MUDAR_S=ate,
                    CANAIS_MINIMOS_DA_BANDA=minimos, CANAIS_QUE_PROVAM_O_SALTO=salto):
        d = rx.Descoberta()
        d.iniciar(CHAVE_DO_ENSAIO, 0.0)
        relogio = 0.0
        for momento, presente in (("sem", False), ("com", True)):
            dele = sorted((x for x in leituras if x.get("momento") == momento),
                          key=lambda x: float(str(x["t"])))
            if not dele:
                break
            inicio = relogio + CADA_S
            d.andar(inicio, lambda: {}, presente=presente)
            fim = float(str(dele[-1]["t"]))
            t = 0.0
            while d.passo in (rx.PASSO_MEDINDO_SEM, rx.PASSO_MEDINDO_COM) and t <= fim + CADA_S:
                t += CADA_S
                ate_aqui = [x for x in dele if float(str(x["t"])) <= t] or dele[:1]
                d.andar(inicio + t, functools.partial(_como_mapas, ate_aqui[-1]["adaptadores"]),
                        presente=presente)
            relogio = inicio + t
        return Fim(d.passo, d.banda, d.causa, d.canais,
                   rx.frase_do_fim(d) or (f"faixa {d.banda[0]}–{d.banda[1] - 1}" if d.banda else ""))


def _como_mapas(bruto: object) -> dict[str, tuple[int, ...] | None]:
    saida: dict[str, tuple[int, ...] | None] = {}
    if isinstance(bruto, Mapping):
        for nome, canais in bruto.items():
            saida[str(nome)] = tuple(int(c) for c in canais) if isinstance(canais, list) else None
    return saida


def linha_curta(fim: Fim) -> str:
    canais = ", ".join(str(c) for c in fim.canais) or "nenhum"
    return f"{fim.passo or 'em curso'}: {fim.frase} (canais novos: {canais})"


# --------------------------------------------------------------- a linha de comando


def main(argv: Sequence[str] | None = None, ler: Callable[[], Mapas] | None = None) -> int:
    p = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    sub = p.add_subparsers(dest="comando", required=True)
    g = sub.add_parser("gravar")
    g.add_argument("--momento", choices=MOMENTOS, required=True)
    g.add_argument("--saida", type=Path, required=True)
    g.add_argument("--medir", action="store_true")
    g.add_argument("--segundos", type=float,
                   default=float(_do_ambiente("HEFESTO_FAIXA_SEGUNDOS", str(SEGUNDOS))))
    g.add_argument("--cada", type=float, default=float(_do_ambiente("HEFESTO_FAIXA_CADA_S", str(CADA_S))))
    c = sub.add_parser("classificar")
    c.add_argument("arquivo", type=Path)
    c.add_argument("--espera", type=float, default=float(_do_ambiente(
        "HEFESTO_FAIXA_ESPERA_S", str(rx.ESPERA_DA_MEDIDA_S))))
    c.add_argument("--ate", type=float, default=float(_do_ambiente(
        "HEFESTO_FAIXA_ATE_S", str(rx.ESPERA_ATE_O_MAPA_MUDAR_S))))
    c.add_argument("--minimos", type=int, default=int(_do_ambiente(
        "HEFESTO_FAIXA_MINIMOS", str(rx.CANAIS_MINIMOS_DA_BANDA))))
    c.add_argument("--salto", type=int, default=int(_do_ambiente(
        "HEFESTO_FAIXA_SALTO", str(rx.CANAIS_QUE_PROVAM_O_SALTO))))
    args = p.parse_args(argv)

    if args.comando == "classificar":
        fim = reproduzir(ler_sessao(args.arquivo), espera=args.espera, ate=args.ate,
                         minimos=args.minimos, salto=args.salto)
        print(linha_curta(fim))
        return 0
    if not args.medir:
        print("RECUSO: " + RECUSA_SEM_MEDIR)
        print(f"o plano: momento {args.momento}, {args.segundos:g} s, uma leitura a cada {args.cada:g} s")
        return 2
    if ler is None:  # pragma: no cover - a bancada
        from hefesto_dualsense4unix.integrations import ar_do_adaptador as ar

        kernel = ar.LeitorDoKernel()

        def ler() -> Mapas:
            return mapas_de_agora(kernel.adaptadores, kernel.conexoes, ar.ler_mapa_afh)

    n = gravar(ler, momento=args.momento, segundos=args.segundos, cada=args.cada, saida=args.saida)
    print(f"momento {args.momento}: {n} leituras gravadas")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
