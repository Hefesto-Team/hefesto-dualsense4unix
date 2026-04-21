"""Gravador determinístico de HID captures (V3-8 + INFRA.2).

Grava estado do DualSense em tempo real (~30Hz) em formato JSONL
comprimido com gzip, extensão `.bin`. FakeController lê pra replay em
testes sem hardware.

Formato:
  bytes = gzip(JSONL UTF-8)
  linha 1 = header: {"type": "header", "version", "transport", "recorded_at", ...}
  linhas 2+ = samples: {"ts": float, "l2", "r2", "lx", "ly", "rx", "ry",
                         "battery", "connected", "buttons": [str]}

Uso:
    python scripts/record_hid_capture.py \\
        --transport usb --duration 10 \\
        --output tests/fixtures/hid_capture_usb.bin

Se `--script` for fornecido, ele imprime dicas passo-a-passo pro usuário
executar a sequência canônica (captures/script_default.yaml).
"""
from __future__ import annotations

import argparse
import contextlib
import gzip
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_SAMPLE_HZ = 30


def parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Gravador determinístico de HID captures.")
    p.add_argument("--transport", choices=["usb", "bt"], required=True,
                   help="Transporte esperado; avisa se device reportar diferente.")
    p.add_argument("--duration", type=float, default=10.0,
                   help="Duração da gravação em segundos (default 10).")
    p.add_argument("--sample-hz", type=int, default=DEFAULT_SAMPLE_HZ,
                   help=f"Taxa de amostragem (default {DEFAULT_SAMPLE_HZ}Hz).")
    p.add_argument("--script", type=Path, default=None,
                   help="YAML descritor da sequência canônica (opcional).")
    p.add_argument("--output", type=Path, required=True,
                   help="Arquivo binário de saída (.bin).")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])

    if args.output.suffix != ".bin":
        print("erro: --output deve ter extensao .bin", file=sys.stderr)
        return 2
    if args.script is not None and not args.script.exists():
        print(f"erro: script {args.script} nao encontrado", file=sys.stderr)
        return 2

    try:
        from hefesto.core.backend_pydualsense import PyDualSenseController
        from hefesto.core.evdev_reader import EvdevReader
    except ImportError as exc:
        print(f"erro: import falhou — rode via venv do projeto. {exc}", file=sys.stderr)
        return 3

    controller = PyDualSenseController()
    evdev = controller._evdev  # Reutiliza o reader pra extrair buttons
    try:
        controller.connect()
    except Exception as exc:
        print(f"erro: connect falhou — verifique udev rules e device. {exc}", file=sys.stderr)
        return 4

    reported_transport = controller.get_transport()
    if reported_transport != args.transport:
        print(f"aviso: transport esperado={args.transport} reportado={reported_transport}",
              file=sys.stderr)

    header = {
        "type": "header",
        "version": 1,
        "transport": reported_transport,
        "sample_hz": args.sample_hz,
        "duration_target_sec": args.duration,
        "recorded_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }

    period = 1.0 / max(1, args.sample_hz)
    n_expected = int(args.duration * args.sample_hz)

    args.output.parent.mkdir(parents=True, exist_ok=True)

    print(f"Gravando {args.duration:.1f}s a {args.sample_hz}Hz -> {args.output}")
    if args.script:
        print(f"Siga a sequencia em: {args.script}")
    print("Pressione Ctrl+C para abortar.")
    print()

    samples: list[dict] = [header]
    start = time.monotonic()
    try:
        for i in range(n_expected):
            tick_t = start + i * period
            now = time.monotonic()
            if now < tick_t:
                time.sleep(tick_t - now)
            ts = time.monotonic() - start
            state = controller.read_state()
            snap = evdev.snapshot() if evdev.is_available() else None
            buttons = sorted(snap.buttons_pressed) if snap else []
            samples.append({
                "ts": round(ts, 4),
                "l2": state.l2_raw,
                "r2": state.r2_raw,
                "lx": state.raw_lx,
                "ly": state.raw_ly,
                "rx": state.raw_rx,
                "ry": state.raw_ry,
                "battery": state.battery_pct,
                "connected": state.connected,
                "buttons": buttons,
            })
            if i % args.sample_hz == 0:
                remaining = args.duration - ts
                print(f"  +{ts:5.1f}s | remaining {remaining:4.1f}s | "
                      f"L2={state.l2_raw:3d} R2={state.r2_raw:3d} btn={buttons}")
    except KeyboardInterrupt:
        print("\nabortado pelo usuario — gravando o que foi coletado...")
    finally:
        with contextlib.suppress(Exception):
            controller.disconnect()

    # Serializa
    payload_lines = [json.dumps(s, ensure_ascii=False) for s in samples]
    payload = ("\n".join(payload_lines) + "\n").encode("utf-8")
    with gzip.open(args.output, "wb") as f:
        f.write(payload)

    size_kb = args.output.stat().st_size / 1024
    print()
    print(f"OK: {len(samples) - 1} samples gravados em {args.output} ({size_kb:.1f} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

# "Tudo que e grande comeca pequeno, com disciplina." — Epicteto
