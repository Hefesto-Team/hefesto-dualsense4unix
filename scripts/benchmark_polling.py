"""Benchmark de polling HID (INFRA.1).

Mede o custo efetivo de `PyDualSenseController.read_state()` contra o
controle físico em várias frequências alvo. Produz CSV com:
  - target_hz: taxa desejada
  - effective_hz: taxa efetiva medida
  - mean_read_ms: tempo médio por read
  - p95_read_ms, p99_read_ms: latências de cauda
  - jitter_ms: desvio padrão dos intervalos entre reads
  - cpu_user_pct: uso de CPU do próprio processo durante o teste

Uso:
    python scripts/benchmark_polling.py --duration 3 \\
        --output benchmarks/2026-04-20-polling.csv
    python scripts/benchmark_polling.py --frequencies 60,120,250,1000
"""
from __future__ import annotations

import argparse
import csv
import statistics
import sys
import time
from pathlib import Path

DEFAULT_FREQS = [30, 60, 120, 250, 500, 1000]


def parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Benchmark de polling HID")
    p.add_argument("--duration", type=float, default=3.0,
                   help="segundos por frequência (default 3)")
    p.add_argument(
        "--frequencies",
        type=str,
        default=",".join(str(f) for f in DEFAULT_FREQS),
        help="CSV de taxas alvo (default 30,60,120,250,500,1000)",
    )
    p.add_argument("--output", type=Path, default=None,
                   help="CSV de saída (default stdout)")
    return p.parse_args(argv)


def _bench_one(controller, target_hz: int, duration: float) -> dict[str, float]:
    period = 1.0 / target_hz
    end_time = time.monotonic() + duration

    read_latencies: list[float] = []
    intervals: list[float] = []
    last_tick = time.monotonic()

    # CPU rusage antes e depois
    import resource

    ru_before = resource.getrusage(resource.RUSAGE_SELF)
    wall_start = time.monotonic()

    n = 0
    while time.monotonic() < end_time:
        tick = time.monotonic()
        intervals.append(tick - last_tick)
        last_tick = tick

        t0 = time.monotonic()
        _ = controller.read_state()
        t1 = time.monotonic()
        read_latencies.append((t1 - t0) * 1000)

        elapsed_tick = time.monotonic() - tick
        sleep_for = period - elapsed_tick
        if sleep_for > 0:
            time.sleep(sleep_for)
        n += 1

    wall_total = time.monotonic() - wall_start
    ru_after = resource.getrusage(resource.RUSAGE_SELF)
    cpu_user = ru_after.ru_utime - ru_before.ru_utime
    cpu_sys = ru_after.ru_stime - ru_before.ru_stime

    # Remove o primeiro interval (zero por construção)
    intervals = intervals[1:] if len(intervals) > 1 else intervals

    effective_hz = n / wall_total if wall_total > 0 else 0.0
    mean_read = statistics.mean(read_latencies) if read_latencies else 0.0
    jitter = statistics.stdev(intervals) * 1000 if len(intervals) > 1 else 0.0

    sorted_reads = sorted(read_latencies)
    p95 = sorted_reads[int(len(sorted_reads) * 0.95)] if sorted_reads else 0.0
    p99 = sorted_reads[int(len(sorted_reads) * 0.99)] if sorted_reads else 0.0

    return {
        "target_hz": target_hz,
        "effective_hz": round(effective_hz, 2),
        "samples": n,
        "mean_read_ms": round(mean_read, 3),
        "p95_read_ms": round(p95, 3),
        "p99_read_ms": round(p99, 3),
        "jitter_ms": round(jitter, 3),
        "cpu_user_sec": round(cpu_user, 3),
        "cpu_sys_sec": round(cpu_sys, 3),
        "cpu_pct": round((cpu_user + cpu_sys) / wall_total * 100, 1),
    }


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    frequencies = [int(x) for x in args.frequencies.split(",") if x.strip()]

    try:
        from hefesto.core.backend_pydualsense import PyDualSenseController
    except ImportError as exc:
        print(f"erro: import falhou — rode via venv do projeto. {exc}", file=sys.stderr)
        return 2

    controller = PyDualSenseController()
    try:
        controller.connect()
    except Exception as exc:
        print(f"erro: connect falhou. {exc}", file=sys.stderr)
        return 3

    print(f"Benchmark runtime em {controller.get_transport()}, "
          f"{len(frequencies)} freqs x {args.duration}s cada", file=sys.stderr)

    results: list[dict[str, float]] = []
    try:
        for hz in frequencies:
            print(f"  target {hz:>4} Hz...", file=sys.stderr, end=" ", flush=True)
            row = _bench_one(controller, hz, args.duration)
            results.append(row)
            print(
                f"eff {row['effective_hz']:>6.1f} Hz  "
                f"mean {row['mean_read_ms']:>5.2f} ms  "
                f"p99 {row['p99_read_ms']:>5.2f} ms  "
                f"cpu {row['cpu_pct']:>4.1f}%",
                file=sys.stderr,
            )
    finally:
        controller.disconnect()

    fieldnames = list(results[0].keys()) if results else []
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(results)
        print(f"CSV gravado: {args.output}", file=sys.stderr)
    else:
        writer = csv.DictWriter(sys.stdout, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)

    return 0


if __name__ == "__main__":
    sys.exit(main())

# "Medir é começar a dominar." — Lord Kelvin (parafraseado)
