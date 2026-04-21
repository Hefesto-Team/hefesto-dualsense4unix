"""Testes de replay de capture no FakeController (INFRA.2)."""
from __future__ import annotations

import gzip
import json
from pathlib import Path

import pytest

from tests.fixtures.fake_controller import FakeController


def _write_capture(path: Path, transport: str, samples: list[dict]) -> None:
    header = {
        "type": "header",
        "version": 1,
        "transport": transport,
        "sample_hz": 30,
        "duration_target_sec": len(samples) / 30,
        "recorded_at": "2026-04-20T22:00:00+00:00",
    }
    lines = [json.dumps(header)] + [json.dumps(s) for s in samples]
    payload = ("\n".join(lines) + "\n").encode("utf-8")
    with gzip.open(path, "wb") as f:
        f.write(payload)


def test_from_capture_carrega_sequencia(tmp_path: Path):
    path = tmp_path / "c.bin"
    _write_capture(
        path,
        "usb",
        [
            {"ts": 0.0, "l2": 10, "r2": 20, "lx": 100, "ly": 100,
             "rx": 128, "ry": 128, "battery": 80, "connected": True, "buttons": []},
            {"ts": 0.1, "l2": 50, "r2": 100, "lx": 120, "ly": 120,
             "rx": 128, "ry": 128, "battery": 80, "connected": True, "buttons": ["cross"]},
            {"ts": 0.2, "l2": 200, "r2": 255, "lx": 128, "ly": 128,
             "rx": 128, "ry": 128, "battery": 80, "connected": True,
             "buttons": ["cross", "circle"]},
        ],
    )

    fc = FakeController.from_capture(path)
    fc.connect()
    assert fc.get_transport() == "usb"

    s1 = fc.read_state()
    assert s1.l2_raw == 10
    assert s1.r2_raw == 20
    assert s1.raw_lx == 100

    s2 = fc.read_state()
    assert s2.l2_raw == 50
    assert s2.r2_raw == 100

    s3 = fc.read_state()
    assert s3.l2_raw == 200
    assert s3.r2_raw == 255

    # Após esgotar, repete último
    s4 = fc.read_state()
    assert s4 == s3


def test_from_capture_bt(tmp_path: Path):
    path = tmp_path / "bt.bin"
    _write_capture(path, "bt", [
        {"ts": 0.0, "l2": 0, "r2": 0, "lx": 128, "ly": 128,
         "rx": 128, "ry": 128, "battery": 45, "connected": True, "buttons": []},
    ])
    fc = FakeController.from_capture(path)
    fc.connect()
    assert fc.get_transport() == "bt"
    s = fc.read_state()
    assert s.transport == "bt"
    assert s.battery_pct == 45


def test_from_capture_arquivo_vazio_rejeita(tmp_path: Path):
    path = tmp_path / "empty.bin"
    with gzip.open(path, "wb") as f:
        f.write(b"")
    with pytest.raises(ValueError, match="capture vazio"):
        FakeController.from_capture(path)


def test_from_capture_sem_header_rejeita(tmp_path: Path):
    path = tmp_path / "noheader.bin"
    with gzip.open(path, "wb") as f:
        f.write(b'{"ts": 0.0, "l2": 0}\n')
    with pytest.raises(ValueError, match="nao e header"):
        FakeController.from_capture(path)


def test_from_capture_versao_desconhecida(tmp_path: Path):
    path = tmp_path / "v2.bin"
    header = {"type": "header", "version": 99, "transport": "usb"}
    with gzip.open(path, "wb") as f:
        f.write(json.dumps(header).encode() + b"\n")
    with pytest.raises(ValueError, match="version"):
        FakeController.from_capture(path)


def test_from_capture_transport_invalido(tmp_path: Path):
    path = tmp_path / "weird.bin"
    header = {"type": "header", "version": 1, "transport": "ir"}
    with gzip.open(path, "wb") as f:
        f.write(json.dumps(header).encode() + b"\n")
    with pytest.raises(ValueError, match="transport"):
        FakeController.from_capture(path)


def test_from_capture_real_do_repo_se_existir():
    """Se o capture real existe no repo, valida que carrega sem erro."""
    real_path = Path("tests/fixtures/hid_capture_usb.bin")
    if not real_path.exists():
        pytest.skip(f"{real_path} nao existe (ok — capture real e opt-in)")
    fc = FakeController.from_capture(real_path)
    fc.connect()
    # Lê pelo menos os 5 primeiros states sem explodir
    for _ in range(5):
        state = fc.read_state()
        assert state.connected in (True, False)
        assert 0 <= state.battery_pct <= 100
