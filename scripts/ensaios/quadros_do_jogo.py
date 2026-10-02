#!/usr/bin/env python3
"""quadros_do_jogo.py — o tempo de cada quadro de um jogo do Proton, sem reabri-lo."""
from __future__ import annotations

import argparse
import json
import os
import re
import statistics
import subprocess
import sys
import time
from collections import defaultdict
from pathlib import Path

LIMIAR_JITTER_MS = 20.0
LIMIAR_TRANCO_MS = 50.0

PROGRAMA = """\
uprobe:{alvo}:thunk64_vkQueuePresentKHR /pid == {pid}/ {{
  if (@ult) {{ printf("q %llu %llu\\n", nsecs, (nsecs - @ult) / 1000); }}
  @ult = nsecs;
}}
interval:s:{segundos} {{ exit(); }}
END {{ clear(@ult); }}
"""

_LINHA_RE = re.compile(r"^q (\d+) (\d+)$")


def achar_winevulkan(pid: int, maps: str | None = None) -> str | None:
    """O caminho do `winevulkan.so` do lado Linux, como o jogo o vê."""
    if maps is None:
        maps = Path(f"/proc/{pid}/maps").read_text(encoding="utf-8", errors="replace")
    for linha in maps.splitlines():
        partes = linha.split(None, 5)
        if len(partes) == 6 and partes[5].endswith("/x86_64-unix/winevulkan.so"):
            return partes[5]
    return None


def ler_saida(texto: str, inicio_mono_ns: int, inicio_wall: float) -> list[tuple[float, float]]:
    """As linhas `q <nsecs> <µs>` do bpftrace → [(hora em epoch, ms do quadro)]."""
    quadros: list[tuple[float, float]] = []
    for linha in texto.splitlines():
        achado = _LINHA_RE.match(linha.strip())
        if achado is None:
            continue
        quando = inicio_wall + (int(achado.group(1)) - inicio_mono_ns) / 1e9
        quadros.append((quando, int(achado.group(2)) / 1000.0))
    return quadros


def _percentil(ordenados: list[float], p: float) -> float:
    if not ordenados:
        return 0.0
    return ordenados[min(len(ordenados) - 1, int(p * (len(ordenados) - 1)))]


def resumir_rodada(quadros: list[tuple[float, float]], segundos: float) -> dict[str, object]:
    ms = [q for _t, q in quadros]
    ordenados = sorted(ms)
    return {
        "segundos": segundos,
        "quadros": len(ms),
        "acima_20": sum(q > LIMIAR_JITTER_MS for q in ms),
        "acima_50": sum(q > LIMIAR_TRANCO_MS for q in ms),
        "mediana_ms": round(statistics.median(ms), 2) if ms else 0.0,
        "p99_ms": round(_percentil(ordenados, 0.99), 2),
        "picos": [[time.strftime("%H:%M:%S", time.localtime(t)), round(q, 1)]
                  for t, q in quadros if q > LIMIAR_TRANCO_MS],
    }


def medir(pid: int, segundos: int, rotulo: str, saida: Path) -> int:
    alvo = achar_winevulkan(pid)
    if alvo is None:
        print(f"o processo {pid} não carregou o winevulkan.so (não é um jogo do Proton "
              "com Vulkan, ou ainda não desenhou)", file=sys.stderr)
        return 2
    programa = PROGRAMA.format(alvo=f"/proc/{pid}/root{alvo}", pid=pid, segundos=segundos)
    inicio_mono = time.monotonic_ns()
    inicio_wall = time.time()
    sudo = ["sudo", "-A"] if os.environ.get("SUDO_ASKPASS") else ["sudo"]
    proc = subprocess.run([*sudo, "bpftrace", "-e", programa], capture_output=True,
                          text=True, timeout=segundos + 60, check=False)
    quadros = ler_saida(proc.stdout, inicio_mono, inicio_wall)
    if not quadros:
        print("o bpftrace não viu quadro nenhum: " + (proc.stderr.strip()[-400:] or
              f"rc={proc.returncode}"), file=sys.stderr)
        return 1
    linha = {"rotulo": rotulo, "pid": pid, "inicio": time.strftime(
        "%Y-%m-%d %H:%M:%S", time.localtime(inicio_wall)), **resumir_rodada(quadros, segundos)}
    saida.parent.mkdir(parents=True, exist_ok=True)
    with saida.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(linha, ensure_ascii=False) + "\n")
    print(json.dumps({k: v for k, v in linha.items() if k != "picos"}, ensure_ascii=False))
    return 0


def celula(rotulo: str) -> str:
    """`virtual-livre-2` → `virtual-livre`: as repetições da mesma célula."""
    return re.sub(r"-\d+$", "", rotulo)


def resumo(linhas: list[dict[str, object]]) -> str:
    grupos: dict[str, list[dict[str, object]]] = defaultdict(list)
    for linha in linhas:
        grupos[celula(str(linha["rotulo"]))].append(linha)
    saida = [f"{'célula':<20} {'n':>2} {'>20 ms/min':>11} {'>50 ms/min':>11} {'p99 (ms)':>9}"]
    for nome in sorted(grupos):
        rodadas = grupos[nome]
        minutos = sum(float(r["segundos"]) for r in rodadas) / 60 or 1
        a20 = sum(int(r["acima_20"]) for r in rodadas) / minutos
        a50 = sum(int(r["acima_50"]) for r in rodadas) / minutos
        p99 = statistics.median(float(r["p99_ms"]) for r in rodadas)
        saida.append(f"{nome:<20} {len(rodadas):>2} {a20:>11.1f} {a50:>11.1f} {p99:>9.1f}")
    return "\n".join(saida)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = p.add_subparsers(dest="cmd", required=True)
    m = sub.add_parser("medir")
    m.add_argument("--pid", type=int, required=True)
    m.add_argument("--segundos", type=int, default=180)
    m.add_argument("--rotulo", required=True)
    m.add_argument("--saida", type=Path, required=True)
    r = sub.add_parser("resumo")
    r.add_argument("arquivo", type=Path)
    args = p.parse_args(argv)
    if args.cmd == "medir":
        return medir(args.pid, args.segundos, args.rotulo, args.saida.expanduser())
    linhas = [json.loads(ln) for ln in args.arquivo.expanduser().read_text(
        encoding="utf-8").splitlines() if ln.strip()]
    print(resumo(linhas))
    return 0


if __name__ == "__main__":
    sys.exit(main())
