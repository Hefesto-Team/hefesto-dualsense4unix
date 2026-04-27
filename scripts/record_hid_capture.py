"""Gravador determinístico de HID captures (V3-8 + INFRA.2).

Grava estado do DualSense em tempo real (~30Hz) em formato JSONL
comprimido com gzip, extensão `.bin`. FakeController lê pra replay em
testes sem hardware.

Formato:
  bytes = gzip(JSONL UTF-8)
  linha 1 = header: {"type": "header", "version", "transport", "recorded_at", ...}
  linhas 2+ = samples: {"ts", "l2", "r2", "lx", "ly", "rx", "ry",
                         "battery", "connected", "buttons"}

Modos:
  - Livre (default): grava por --duration segundos, user fica a vontade.
  - Guiado (--guided): narra sequência completa de botões, mostra feedback
    em tempo real, avança quando detecta a ação esperada.

Uso:
    # modo livre:
    python scripts/record_hid_capture.py --transport usb --duration 15 \\
        --output tests/fixtures/hid_capture_usb.bin

    # modo guiado (mapeia todos os botões em ordem):
    python scripts/record_hid_capture.py --transport usb --guided \\
        --output tests/fixtures/hid_capture_usb.bin
"""
from __future__ import annotations

import argparse
import contextlib
import gzip
import json
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_SAMPLE_HZ = 30
STEP_TIMEOUT_SEC = 12.0      # tempo máximo pra cada passo do modo guiado
STEP_CONFIRM_DELAY = 0.5     # mantém o estado por esse tempo antes de avançar


@dataclass
class GuidedStep:
    """Um passo do roteiro guiado."""

    name: str
    instruction: str
    # check(state, snap) -> bool: retorna True quando a ação esperada aconteceu
    check: callable
    hold_sec: float = 0.6
    cooldown_sec: float = 0.4


def _build_default_guided_script() -> list[GuidedStep]:
    """Sequência canônica: cada botão, direção, gatilho analog."""
    def need_button(name: str):
        def _c(state, snap) -> bool:
            return snap is not None and name in snap.buttons_pressed
        return _c

    def need_release(name: str):
        def _c(state, snap) -> bool:
            return snap is None or name not in snap.buttons_pressed
        return _c

    def need_trigger(side: str, floor: int):
        attr = "l2_raw" if side == "left" else "r2_raw"
        def _c(state, snap) -> bool:
            return getattr(state, attr) >= floor
        return _c

    def need_trigger_zero(side: str):
        attr = "l2_raw" if side == "left" else "r2_raw"
        def _c(state, snap) -> bool:
            return getattr(state, attr) <= 5
        return _c

    def need_stick(side: str, axis: str, target: int, tol: int = 30):
        lx_like = "raw_lx" if side == "left" else "raw_rx"
        ly_like = "raw_ly" if side == "left" else "raw_ry"
        attr = lx_like if axis == "x" else ly_like
        def _c(state, snap) -> bool:
            return abs(getattr(state, attr) - target) <= tol
        return _c

    steps = [
        GuidedStep("idle", "Controle em REPOUSO (solte tudo).",
                   lambda s, snap: True, hold_sec=1.5, cooldown_sec=0.1),

        # Gatilhos analógicos
        GuidedStep("r2_full", "Segure R2 ATE O FIM (pressao maxima).",
                   need_trigger("right", 220)),
        GuidedStep("r2_release", "Solte R2 completamente.",
                   need_trigger_zero("right")),
        GuidedStep("l2_full", "Segure L2 ATE O FIM (pressao maxima).",
                   need_trigger("left", 220)),
        GuidedStep("l2_release", "Solte L2 completamente.",
                   need_trigger_zero("left")),
        GuidedStep("r2_half", "Aperte R2 METADE (pressao leve).",
                   lambda s, snap: 60 <= s.r2_raw <= 180),
        GuidedStep("r2_release_2", "Solte R2.",
                   need_trigger_zero("right")),

        # Face buttons
        GuidedStep("cross_press", "Aperte X (cross).", need_button("cross")),
        GuidedStep("cross_release", "Solte X.", need_release("cross")),
        GuidedStep("circle_press", "Aperte O (circle).", need_button("circle")),
        GuidedStep("circle_release", "Solte O.", need_release("circle")),
        GuidedStep("square_press", "Aperte Quadrado.", need_button("square")),
        GuidedStep("square_release", "Solte Quadrado.", need_release("square")),
        GuidedStep("triangle_press", "Aperte Triangulo.", need_button("triangle")),
        GuidedStep("triangle_release", "Solte Triangulo.", need_release("triangle")),

        # Shoulders
        GuidedStep("l1_press", "Aperte L1.", need_button("l1")),
        GuidedStep("l1_release", "Solte L1.", need_release("l1")),
        GuidedStep("r1_press", "Aperte R1.", need_button("r1")),
        GuidedStep("r1_release", "Solte R1.", need_release("r1")),

        # D-pad
        GuidedStep("dpad_up", "D-pad PARA CIMA.", need_button("dpad_up")),
        GuidedStep("dpad_release_u", "Solte o D-pad.", need_release("dpad_up")),
        GuidedStep("dpad_down", "D-pad PARA BAIXO.", need_button("dpad_down")),
        GuidedStep("dpad_release_d", "Solte o D-pad.", need_release("dpad_down")),
        GuidedStep("dpad_left", "D-pad PARA ESQUERDA.", need_button("dpad_left")),
        GuidedStep("dpad_release_l", "Solte o D-pad.", need_release("dpad_left")),
        GuidedStep("dpad_right", "D-pad PARA DIREITA.", need_button("dpad_right")),
        GuidedStep("dpad_release_r", "Solte o D-pad.", need_release("dpad_right")),

        # System buttons
        GuidedStep("options_press", "Aperte Options (ou Start).", need_button("options")),
        GuidedStep("options_release", "Solte Options.", need_release("options")),
        GuidedStep("create_press", "Aperte Create (ou Select).", need_button("create")),
        GuidedStep("create_release", "Solte Create.", need_release("create")),
        GuidedStep("ps_press", "Aperte o botao PS.", need_button("ps")),
        GuidedStep("ps_release", "Solte PS.", need_release("ps")),

        # Stick clicks
        GuidedStep("l3_press", "Clique L3 (pressione o stick esquerdo).",
                   need_button("l3")),
        GuidedStep("l3_release", "Solte L3.", need_release("l3")),
        GuidedStep("r3_press", "Clique R3 (pressione o stick direito).",
                   need_button("r3")),
        GuidedStep("r3_release", "Solte R3.", need_release("r3")),

        # Sticks analógicos
        GuidedStep("lstick_left", "Stick ESQUERDO pra ESQUERDA (ate o limite).",
                   need_stick("left", "x", 20)),
        GuidedStep("lstick_right", "Stick ESQUERDO pra DIREITA (ate o limite).",
                   need_stick("left", "x", 235)),
        GuidedStep("lstick_up", "Stick ESQUERDO pra CIMA.",
                   need_stick("left", "y", 20)),
        GuidedStep("lstick_down", "Stick ESQUERDO pra BAIXO.",
                   need_stick("left", "y", 235)),
        GuidedStep("lstick_center", "Centralize o stick esquerdo.",
                   lambda s, snap: abs(s.raw_lx - 128) < 20 and abs(s.raw_ly - 128) < 20),

        GuidedStep("rstick_left", "Stick DIREITO pra ESQUERDA.",
                   need_stick("right", "x", 20)),
        GuidedStep("rstick_right", "Stick DIREITO pra DIREITA.",
                   need_stick("right", "x", 235)),
        GuidedStep("rstick_up", "Stick DIREITO pra CIMA.",
                   need_stick("right", "y", 20)),
        GuidedStep("rstick_down", "Stick DIREITO pra BAIXO.",
                   need_stick("right", "y", 235)),
        GuidedStep("rstick_center", "Centralize o stick direito.",
                   lambda s, snap: abs(s.raw_rx - 128) < 20 and abs(s.raw_ry - 128) < 20),

        GuidedStep("done", "OK! Solte tudo. Gravacao finalizando.",
                   lambda s, snap: True, hold_sec=1.0, cooldown_sec=0.1),
    ]
    return steps


@dataclass
class CaptureSession:
    controller: object
    evdev: object
    sample_hz: int
    samples: list[dict] = field(default_factory=list)
    start_mono: float = 0.0

    def begin(self, header: dict) -> None:
        self.samples = [header]
        self.start_mono = time.monotonic()

    def tick_record(self) -> tuple[object, object]:
        """Lê estado atual, grava sample, retorna (state, snap)."""
        state = self.controller.read_state()  # type: ignore[attr-defined]
        snap = self.evdev.snapshot() if self.evdev.is_available() else None  # type: ignore[attr-defined]
        buttons = sorted(snap.buttons_pressed) if snap else []
        self.samples.append({
            "ts": round(time.monotonic() - self.start_mono, 4),
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
        return state, snap


def parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Gravador determinístico de HID captures.")
    p.add_argument("--transport", choices=["usb", "bt"], required=True,
                   help="Transporte esperado; avisa se device reportar diferente.")
    p.add_argument("--duration", type=float, default=10.0,
                   help="[modo livre] duração da gravação em segundos.")
    p.add_argument("--sample-hz", type=int, default=DEFAULT_SAMPLE_HZ,
                   help=f"Taxa de amostragem (default {DEFAULT_SAMPLE_HZ}Hz).")
    p.add_argument("--guided", action="store_true",
                   help="Modo guiado: narra passo a passo o que apertar.")
    p.add_argument("--output", type=Path, required=True,
                   help="Arquivo binário de saída (.bin).")
    return p.parse_args(argv)


def _free_form_loop(session: CaptureSession, duration: float, sample_hz: int) -> None:
    period = 1.0 / max(1, sample_hz)
    n_expected = int(duration * sample_hz)
    for i in range(n_expected):
        tick_t = session.start_mono + i * period
        now = time.monotonic()
        if now < tick_t:
            time.sleep(tick_t - now)
        state, _ = session.tick_record()
        if i % sample_hz == 0:
            ts = time.monotonic() - session.start_mono
            remaining = duration - ts
            print(f"  +{ts:5.1f}s | remaining {remaining:4.1f}s | "
                  f"L2={state.l2_raw:3d} R2={state.r2_raw:3d}")


def _guided_loop(session: CaptureSession, sample_hz: int) -> None:
    period = 1.0 / max(1, sample_hz)
    steps = _build_default_guided_script()

    total = len(steps)
    for idx, step in enumerate(steps, start=1):
        print()
        print(f"[{idx}/{total}] {step.name}: {step.instruction}")
        print("      (aguardando ...)", end="", flush=True)

        step_start = time.monotonic()
        held_since: float | None = None
        detected = False

        while True:
            tick_start = time.monotonic()
            state, snap = session.tick_record()

            try:
                ok = bool(step.check(state, snap))
            except Exception:
                ok = False

            if ok:
                if held_since is None:
                    held_since = tick_start
                elif tick_start - held_since >= step.hold_sec:
                    detected = True
                    print(" OK")
                    break
            else:
                held_since = None

            if time.monotonic() - step_start >= STEP_TIMEOUT_SEC:
                print(" TIMEOUT (seguindo mesmo assim)")
                break

            elapsed = time.monotonic() - tick_start
            sleep_for = period - elapsed
            if sleep_for > 0:
                time.sleep(sleep_for)

        # cooldown entre passos pra o user relaxar o gesto
        cooldown_end = time.monotonic() + step.cooldown_sec
        while time.monotonic() < cooldown_end:
            session.tick_record()
            time.sleep(period)

        _ = detected  # telemetria silenciosa por enquanto


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])

    if args.output.suffix != ".bin":
        print("erro: --output deve ter extensão .bin", file=sys.stderr)
        return 2

    try:
        from hefesto_dualsense4unix.core.backend_pydualsense import PyDualSenseController
    except ImportError as exc:
        print(f"erro: import falhou — rode via venv do projeto. {exc}", file=sys.stderr)
        return 3

    controller = PyDualSenseController()
    try:
        controller.connect()
    except Exception as exc:
        print(f"erro: connect falhou — verifique udev rules e device. {exc}", file=sys.stderr)
        return 4

    evdev = controller._evdev  # Reutiliza o reader pra extrair buttons

    reported_transport = controller.get_transport()
    if reported_transport != args.transport:
        print(f"aviso: transport esperado={args.transport} reportado={reported_transport}",
              file=sys.stderr)

    header = {
        "type": "header",
        "version": 1,
        "transport": reported_transport,
        "sample_hz": args.sample_hz,
        "mode": "guided" if args.guided else "free",
        "duration_target_sec": args.duration if not args.guided else None,
        "recorded_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)

    session = CaptureSession(
        controller=controller, evdev=evdev, sample_hz=args.sample_hz
    )
    session.begin(header)

    if args.guided:
        print("=== MODO GUIADO ===")
        print("Siga cada instrucao. Cada passo precisa ser segurado por ~0.6s")
        print("pra confirmar; se não confirmar em 12s, pulamos automaticamente.")
        print()
        print("Preparando... 3...")
        time.sleep(1)
        print("2...")
        time.sleep(1)
        print("1...")
        time.sleep(1)
        print("GRAVANDO!")
    else:
        print(f"Gravando {args.duration:.1f}s a {args.sample_hz}Hz -> {args.output}")
        print("Pressione Ctrl+C para abortar.")
        print()

    try:
        if args.guided:
            _guided_loop(session, args.sample_hz)
        else:
            _free_form_loop(session, args.duration, args.sample_hz)
    except KeyboardInterrupt:
        print("\nabortado pelo usuário — gravando o que foi coletado...")
    finally:
        with contextlib.suppress(Exception):
            controller.disconnect()

    payload_lines = [json.dumps(s, ensure_ascii=False) for s in session.samples]
    payload = ("\n".join(payload_lines) + "\n").encode("utf-8")
    with gzip.open(args.output, "wb") as f:
        f.write(payload)

    size_kb = args.output.stat().st_size / 1024
    n_samples = len(session.samples) - 1
    print()
    print(f"OK: {n_samples} samples gravados em {args.output} ({size_kb:.1f} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

# "Tudo que e grande comeca pequeno, com disciplina." — Epicteto
