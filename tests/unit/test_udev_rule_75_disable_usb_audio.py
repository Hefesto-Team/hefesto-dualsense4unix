"""Forma da regra udev 75 (OPT-IN: desligar áudio USB do DualSense).

FEAT-DSX-DEFINITIVE-FIX-01 §7.5. A regra `75-ps5-controller-disable-usb-audio.rules`
desliga as interfaces de ÁUDIO USB (classe 01) do DualSense para matar o gatilho do
storm -71, deixando a interface HID (classe 03 = gamepad) INTACTA. Estes testes
travam o contrato:

- casa só bInterfaceClass==01 (Audio), nunca a HID (classe 03);
- cobre os dois PIDs (0ce6 DualSense, 0df2 DualSense Edge) do VID 054c (Sony);
- mecanismo PRIMÁRIO authorized=0 (race-reduzido) + REFORÇO unbind do snd-usb-audio.
"""
from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
RULE_PATH = REPO_ROOT / "assets" / "75-ps5-controller-disable-usb-audio.rules"


@pytest.fixture(scope="module")
def rule_lines() -> list[str]:
    """Linhas de regra (não-comentário, não-vazias) do arquivo 75."""
    text = RULE_PATH.read_text(encoding="utf-8")
    return [
        ln.strip()
        for ln in text.splitlines()
        if ln.strip() and not ln.lstrip().startswith("#")
    ]


def test_arquivo_existe() -> None:
    assert RULE_PATH.is_file(), f"regra 75 ausente em {RULE_PATH}"


def test_casa_apenas_classe_audio_nunca_a_hid(rule_lines: list[str]) -> None:
    # Toda linha de regra precisa casar a interface de áudio (classe 01)...
    assert rule_lines, "nenhuma linha de regra encontrada"
    for ln in rule_lines:
        assert 'ATTR{bInterfaceClass}=="01"' in ln, (
            f"linha não restringe à classe 01 (áudio): {ln}"
        )
    # ...e NUNCA a HID (classe 03), para o gamepad (If3) ficar intacto.
    blob = "\n".join(rule_lines)
    assert "03" not in blob.replace('"01"', ""), (
        "a regra 75 não pode referenciar a classe 03 (HID) — quebraria o gamepad"
    )


def test_cobre_ambos_os_pids_do_vendor_sony(rule_lines: list[str]) -> None:
    blob = "\n".join(rule_lines)
    assert 'ATTRS{idVendor}=="054c"' in blob, "VID Sony (054c) ausente"
    for pid in ("0ce6", "0df2"):
        assert f'ATTRS{{idProduct}}=="{pid}"' in blob, f"PID {pid} não coberto"


def test_mecanismo_primario_authorized_zero(rule_lines: list[str]) -> None:
    # Uma linha ACTION=="add" ... ATTR{authorized}="0" por PID (race-reduzido).
    add_lines = [
        ln for ln in rule_lines
        if 'ACTION=="add"' in ln and 'ATTR{authorized}="0"' in ln
    ]
    assert len(add_lines) >= 2, (
        "esperado authorized=0 no evento add para 0ce6 e 0df2 (mecanismo primário)"
    )
    for pid in ("0ce6", "0df2"):
        assert any(pid in ln for ln in add_lines), (
            f"authorized=0 ausente para o PID {pid}"
        )


def test_reforco_unbind_snd_usb_audio(rule_lines: list[str]) -> None:
    # Belt-and-suspenders: se mesmo assim bindar, desfaz no evento bind.
    bind_lines = [
        ln for ln in rule_lines
        if 'ACTION=="bind"' in ln and "snd-usb-audio/unbind" in ln
    ]
    assert len(bind_lines) >= 2, (
        "esperado unbind do snd-usb-audio no evento bind para 0ce6 e 0df2 (reforço)"
    )
    for pid in ("0ce6", "0df2"):
        assert any(pid in ln for ln in bind_lines), (
            f"unbind de reforço ausente para o PID {pid}"
        )
