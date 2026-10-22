#!/usr/bin/env python3
"""contar_o_rumble_do_jogo_xbox.py — o que um jogo Xbox manda ao pad e por onde o rumble vai.

O-RUMBLE-DO-JOGO-XBOX-GANHA-O-TIMBRE-DO-ESTILO-01 (22/10/2026). Duas metades:

1. O CONTADOR (``contar``, ``ler_gravacao``): puro, lê uma GRAVAÇÃO e imprime, por controle,
   efeitos por segundo, as classes (golpe, médio, contínuo grave e fino, periódico), a onda do
   ``FF_PERIODIC``, quanto cada subida dura, por onde o rumble foi (háptica fina ou motores do
   HID) e o porquê. ``--ler ARQUIVO`` usa só ele; é o que os testes prendem.
2. O GRAVADOR (``--gravar SEGUNDOS --saida ARQUIVO``): pergunta ``daemon.state_full`` ao
   serviço no ar a cada 100 ms e guarda os campos ``ff_*`` de cada pad. Só LÊ o estado; é da
   bancada, com o jogo aberto. O endereço sai mascarado (octetos 4 e 5 zerados).

A gravação: linhas JSON ``{"t": s, "per_vpad": [{"uniq", "player", "ff_play_count",
"ff_nao_nulo_count", "ff_por_classe", "ff_forma_do_periodico", "ff_ultimos_trechos",
"ff_rota"}]}``, uma por pergunta.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

_AQUI = Path(__file__).resolve().parent
_SRC = _AQUI.parent.parent / "src"
if _SRC.is_dir() and str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from hefesto_dualsense4unix.integrations import classe_do_rumble as classes

RC_SEM_DADO = 4
INTERVALO_DA_PERGUNTA_S = 0.1
CAMPOS = (
    "uniq", "player", "ff_play_count", "ff_nao_nulo_count", "ff_por_classe",
    "ff_forma_do_periodico", "ff_ultimos_trechos", "ff_rota",
)


@dataclass
class Contagem:
    """O que se contou de UM controle ao longo da gravação."""

    uniq: str
    duracao_s: float = 0.0
    plays: int = 0
    nao_nulos: int = 0
    por_classe: dict[str, int] = field(default_factory=lambda: dict.fromkeys(classes.CLASSES, 0))
    ondas: Counter[str] = field(default_factory=Counter)
    duracoes_ms: dict[str, list[int]] = field(default_factory=dict)
    rotas: Counter[str] = field(default_factory=Counter)
    timbres: Counter[str] = field(default_factory=Counter)


def ler_gravacao(texto: str) -> list[dict[str, Any]]:
    """As perguntas da gravação, em ordem de tempo; levanta ``ValueError`` se não há nenhuma."""
    linhas = [json.loads(linha) for linha in texto.splitlines() if linha.strip()]
    linhas = [x for x in linhas if isinstance(x, dict) and isinstance(x.get("per_vpad"), list)]
    if not linhas:
        raise ValueError("gravação sem nenhuma pergunta ao estado")
    return sorted(linhas, key=lambda x: float(x.get("t", 0.0)))


def _numero(valor: Any) -> int:
    return int(valor) if isinstance(valor, int | float) else 0


def _novos_no_anel(
    antes: Sequence[tuple[Any, ...]], agora: Sequence[tuple[Any, ...]]
) -> Sequence[tuple[Any, ...]]:
    """O que entrou no anel dos trechos desde a pergunta anterior (o fim de ``antes`` encosta)."""
    for k in range(min(len(antes), len(agora)), 0, -1):
        if list(antes[-k:]) == list(agora[:k]):
            return agora[k:]
    return agora


def contar(perguntas: Sequence[dict[str, Any]]) -> dict[str, Contagem]:
    """A contagem por controle: a diferença entre a primeira e a última pergunta de cada um."""
    primeiro: dict[str, tuple[float, dict[str, Any]]] = {}
    contagens: dict[str, Contagem] = {}
    anel_de_antes: dict[str, list[tuple[Any, ...]]] = {}
    for pergunta in perguntas:
        t = float(pergunta.get("t", 0.0))
        for pad in pergunta["per_vpad"]:
            if not isinstance(pad, dict):
                continue
            uniq = str(pad.get("uniq") or f"P{pad.get('player', '?')}")
            primeiro.setdefault(uniq, (t, pad))
            t0, pad0 = primeiro[uniq]
            c = contagens.setdefault(uniq, Contagem(uniq))
            c.duracao_s = t - t0
            c.plays = _numero(pad.get("ff_play_count")) - _numero(pad0.get("ff_play_count"))
            c.nao_nulos = (
                _numero(pad.get("ff_nao_nulo_count")) - _numero(pad0.get("ff_nao_nulo_count"))
            )
            agora, antes = pad.get("ff_por_classe") or {}, pad0.get("ff_por_classe") or {}
            c.por_classe = {
                k: _numero(agora.get(k)) - _numero(antes.get(k)) for k in classes.CLASSES
            }
            forma = pad.get("ff_forma_do_periodico")
            if isinstance(forma, dict) and forma.get("onda"):
                c.ondas[str(forma["onda"])] += 1
            anel = [tuple(x) for x in pad.get("ff_ultimos_trechos") or [] if isinstance(x, list)]
            for trecho in _novos_no_anel(anel_de_antes.get(uniq, []), anel):
                if len(trecho) >= 2:
                    c.duracoes_ms.setdefault(str(trecho[0]), []).append(_numero(trecho[1]))
            anel_de_antes[uniq] = anel
            rota = pad.get("ff_rota")
            if isinstance(rota, dict):
                c.rotas[f"{rota.get('rota')} ({rota.get('porque')})"] += 1
                if rota.get("timbre"):
                    c.timbres[str(rota["timbre"])] += 1
    return contagens


def _por_segundo(n: int, duracao_s: float) -> str:
    return f"{n / duracao_s:.1f}/s" if duracao_s > 0 else "—"


def linhas_do_controle(c: Contagem) -> list[str]:
    """O relato de um controle, em linhas curtas."""
    saida = [
        f"{c.uniq}: {c.duracao_s:.1f} s, {c.plays} plays ({_por_segundo(c.plays, c.duracao_s)}),"
        f" {c.nao_nulos} pares com força ({_por_segundo(c.nao_nulos, c.duracao_s)})",
        "  classes: " + ", ".join(f"{k} {v}" for k, v in c.por_classe.items()),
    ]
    if c.ondas:
        saida.append("  FF_PERIODIC: " + ", ".join(f"{k} ({v})" for k, v in c.ondas.items()))
    else:
        saida.append("  FF_PERIODIC: nenhum (só FF_RUMBLE)")
    for classe, duracoes in sorted(c.duracoes_ms.items()):
        saida.append(
            f"  {classe}: {len(duracoes)} subidas, {min(duracoes)} a {max(duracoes)} ms"
            f" (mediana {statistics.median(duracoes):.0f})"
        )
    total = sum(c.rotas.values())
    if total:
        saida.append("  rota: " + ", ".join(
            f"{k} {100 * v // total}%" for k, v in c.rotas.most_common()))
    else:
        saida.append("  rota: o estado não disse (serviço sem ff_rota)")
    if c.timbres:
        saida.append("  timbre: " + ", ".join(f"{k} ({v})" for k, v in c.timbres.most_common()))
    return saida


def _mascarar(uniq: Any) -> Any:
    if not isinstance(uniq, str) or uniq.count(":") != 5:
        return uniq
    partes = uniq.split(":")
    partes[3] = partes[4] = "00"
    return ":".join(partes)


def gravar(segundos: float) -> list[dict[str, Any]]:
    """Bancada: pergunta o estado ao serviço no ar por ``segundos`` (só leitura)."""
    from hefesto_dualsense4unix.app.ipc_bridge import _run_call

    perguntas: list[dict[str, Any]] = []
    inicio = time.monotonic()
    while time.monotonic() - inicio < segundos:
        estado = _run_call("daemon.state_full") or {}
        pads = (estado.get("rumble_ff") or {}).get("per_vpad")
        per_vpad = [
            {k: (_mascarar(p.get(k)) if k == "uniq" else p.get(k)) for k in CAMPOS}
            for p in (pads or []) if isinstance(p, dict)
        ]
        perguntas.append({"t": round(time.monotonic() - inicio, 3), "per_vpad": per_vpad})
        time.sleep(INTERVALO_DA_PERGUNTA_S)
    return perguntas


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Conta o rumble de um jogo Xbox e por onde ele vai.")
    grupo = p.add_mutually_exclusive_group(required=True)
    grupo.add_argument("--ler", type=Path, help="conta uma gravação (só leitura)")
    grupo.add_argument("--gravar", type=float, metavar="SEGUNDOS",
                       help="bancada: pergunta o estado ao serviço no ar")
    p.add_argument("--saida", type=Path, help="com --gravar: onde guardar a gravação")
    p.add_argument("--jogo", default="Tenebris Somnia")
    p.add_argument("--transporte", choices=("cabo", "radio"), default="cabo")
    return p


def _imprimir(args: argparse.Namespace, perguntas: Sequence[dict[str, Any]]) -> int:
    print(f"o rumble do jogo Xbox — {args.jogo}, {args.transporte}")
    contagens = contar(perguntas)
    if not contagens:
        print("SEM DADO: nenhum pad Xbox na gravação")
        return RC_SEM_DADO
    for c in contagens.values():
        print("\n".join(linhas_do_controle(c)))
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.ler is not None:
            return _imprimir(args, ler_gravacao(args.ler.read_text(encoding="utf-8")))
        if args.saida is None:
            print("RECUSADO: --gravar pede --saida (a gravação é o recibo)")
            return 2
        perguntas = gravar(args.gravar)
        args.saida.write_text(
            "".join(json.dumps(x, ensure_ascii=False) + "\n" for x in perguntas), encoding="utf-8"
        )
        return _imprimir(args, perguntas)
    except (OSError, ValueError) as erro:
        print(f"SEM DADO: {erro}")
        return RC_SEM_DADO


if __name__ == "__main__":
    raise SystemExit(main())
