"""Gravador determinístico de HID captures (V3-8).

Executa uma sequência YAML canônica contra o DualSense físico e grava
o tráfego HID em arquivo binário pra ser replayed por FakeController.

Uso:
    python scripts/record_hid_capture.py \\
        --transport usb \\
        --duration 30 \\
        --script captures/script_default.yaml \\
        --output tests/fixtures/hid_capture_usb.bin
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path


def parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Gravador determinístico de HID captures.")
    p.add_argument("--transport", choices=["usb", "bt"], required=True,
                   help="Transporte esperado; falha se device reportar diferente.")
    p.add_argument("--duration", type=float, default=30.0,
                   help="Duração máxima da gravação em segundos.")
    p.add_argument("--script", type=Path, required=True,
                   help="YAML descritor da sequência canônica.")
    p.add_argument("--output", type=Path, required=True,
                   help="Arquivo binário de saída.")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])

    if not args.script.exists():
        print(f"erro: script {args.script} nao encontrado", file=sys.stderr)
        return 2
    if args.output.suffix != ".bin":
        print("erro: --output deve ter extensao .bin", file=sys.stderr)
        return 2

    # Stub: implementação real conecta ao pydualsense, executa steps do YAML,
    # grava buffer HID. Ver W1.1 para integração com FakeController.
    print(f"[STUB] record_hid_capture: transport={args.transport} "
          f"duration={args.duration}s script={args.script} output={args.output}")
    print("Implementacao pendente: W1.1 entrega o IController e o replay format.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

# "Tudo que e grande comeca pequeno, com disciplina." — Epicteto
