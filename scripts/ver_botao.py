#!/usr/bin/env python3
"""Mostra, na hora, qual evento cada botão do controle emite."""
from __future__ import annotations

import selectors
import sys

try:
    import evdev

    from hefesto_dualsense4unix.core.linhagem_nintendo import e_clone_conhecido
except ImportError as _falta:
    print(f"erro: `{_falta.name}` não está no interpretador atual.")
    print("      Rode pelo venv do projeto: .venv/bin/python scripts/ver_botao.py")
    raise SystemExit(2) from None


def rotulo(dev: evdev.InputDevice) -> str:
    """Nome curto e humano, para não confundir dois controles iguais."""
    uniq = dev.uniq or ""
    nome = dev.name
    if "dualsense" in nome.lower():
        return "DualSense"
    if "pro controller" in nome.lower():
        if e_clone_conhecido(uniq):
            return "8BitDo (clone)"
        return "Pro (Nintendo)" if uniq else "Pro (indistinguível)"
    return nome[:24]


def main() -> int:
    dispositivos = []
    for caminho in evdev.list_devices():
        try:
            dev = evdev.InputDevice(caminho)
        except OSError:
            continue
        if evdev.ecodes.EV_KEY not in dev.capabilities():
            continue
        nome = dev.name.lower()
        if any(t in nome for t in ("pro controller", "dualsense", "gamepad", "8bitdo")):
            dispositivos.append(dev)

    if not dispositivos:
        print("nenhum controle com botões encontrado.")
        print("Ligue o controle e rode de novo.")
        return 1

    print("Escutando:")
    for dev in dispositivos:
        print(f"  {rotulo(dev):18} {dev.path}")
    print()
    print("APERTE UM BOTÃO — o nome dele aparece aqui embaixo na hora.")
    print("Ctrl+C para sair.")
    print()

    seletor = selectors.DefaultSelector()
    for dev in dispositivos:
        seletor.register(dev, selectors.EVENT_READ)

    vistos: dict[tuple[str, str], int] = {}
    try:
        while True:
            for chave, _ in seletor.select():
                dev = chave.fileobj
                try:
                    eventos = list(dev.read())
                except OSError:
                    continue
                for ev in eventos:
                    if ev.type != evdev.ecodes.EV_KEY or ev.value != 1:
                        continue
                    nome = (
                        evdev.ecodes.BTN.get(ev.code)
                        or evdev.ecodes.KEY.get(ev.code)
                        or f"code {ev.code}"
                    )
                    if isinstance(nome, list):
                        nome = nome[0]
                    par = (rotulo(dev), nome)
                    vistos[par] = vistos.get(par, 0) + 1
                    print(f"  {par[0]:18} -> {nome}  (code {ev.code})", flush=True)
    except KeyboardInterrupt:
        print()
        print("=== o que apareceu ===")
        for (rot, nome), quantas in sorted(vistos.items(), key=lambda x: -x[1]):
            print(f"  {rot:18} {nome:16} x{quantas}")
        if not vistos:
            print("  nada — nenhum botão chegou ao evdev")
        return 0


if __name__ == "__main__":
    sys.exit(main())
