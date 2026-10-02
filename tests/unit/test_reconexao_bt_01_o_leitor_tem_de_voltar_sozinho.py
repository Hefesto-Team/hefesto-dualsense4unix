"""RECONEXÃO-BT-01 (16/08/2026) — o leitor tem de voltar sozinho, no nó NOVO."""
from __future__ import annotations

import sys
import threading
import time
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from hefesto_dualsense4unix.core import evdev_reader as er_mod
from hefesto_dualsense4unix.core.evdev_reader import EvdevReader

_NO_ANTES = Path("/dev/input/event25")
_NO_DEPOIS = Path("/dev/input/event26")


class _DeviceFalso:
    """Um `InputDevice` de bancada que sabe morrer e renascer noutro nó."""

    def __init__(self, caminho: str) -> None:
        self.path = caminho
        self.name = "DualSense Wireless Controller"
        self.fd = 0
        self.fechado = False

    def read(self) -> Any:
        return iter([])

    def close(self) -> None:
        self.fechado = True

    def grab(self) -> None: ...

    def ungrab(self) -> None: ...

    def capabilities(self, *_a: object, **_k: object) -> dict[int, object]:
        return {}


@pytest.fixture()
def bancada(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """Um mundo onde o nó do controle pode sumir e voltar com outro número."""
    estado: dict[str, Any] = {
        "no_atual": str(_NO_ANTES),
        "abertos": [],
        "morrer": threading.Event(),
    }

    def _abrir(caminho: str, *_a: object, **_k: object) -> _DeviceFalso:
        estado["abertos"].append(caminho)
        return _DeviceFalso(caminho)

    fake = MagicMock()
    fake.InputDevice = _abrir
    fake.ecodes = MagicMock()
    monkeypatch.setitem(sys.modules, "evdev", fake)

    monkeypatch.setattr(
        er_mod, "find_dualsense_evdev",
        lambda: Path(estado["no_atual"]) if estado["no_atual"] else None,
    )
    monkeypatch.setattr(er_mod, "discover_dualsense_evdevs", lambda: {})

    class _AvisoDaBancada:
        """O `/dev/input` desta bancada: muda quando o nó vigente muda."""

        def __init__(self) -> None:
            self.visto = estado["no_atual"]
            self.nasceu = False

        def poll(self) -> bool:
            mudou = estado["no_atual"] != self.visto
            self.visto = estado["no_atual"]
            self.nasceu = bool(mudou and estado["no_atual"])
            return bool(mudou)

    monkeypatch.setattr(er_mod, "_novo_aviso_de_entrada", _AvisoDaBancada)
    return estado


def _reader_com_morte(
    bancada: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> EvdevReader:
    """Um reader cujo select morre com ENODEV assim que o flag é armado."""
    reader = EvdevReader(device_path=None)

    def _select(_dev: object) -> list[object]:
        if bancada["morrer"].is_set():
            bancada["morrer"].clear()
            raise OSError(19, "No such device")
        time.sleep(0.01)
        return []

    monkeypatch.setattr(reader, "_wait_ready", _select)
    return reader


class TestOCicloCompleto:
    def test_o_leitor_reabre_no_no_novo_depois_da_reconexao(
        self, bancada: dict[str, Any], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A MORDIDA. É o defeito de 16/08 inteiro, em três atos."""
        reader = _reader_com_morte(bancada, monkeypatch)
        assert reader.start() is True
        try:
            _esperar(lambda: str(_NO_ANTES) in bancada["abertos"], 2.0)

            bancada["no_atual"] = ""
            bancada["morrer"].set()
            time.sleep(0.3)

            bancada["no_atual"] = str(_NO_DEPOIS)

            reabriu = _esperar(
                lambda: str(_NO_DEPOIS) in bancada["abertos"], 4.0
            )
        finally:
            reader.stop()

        assert reabriu, (
            "o leitor NÃO reabriu no nó novo — é o defeito de 16/08: o daemon "
            f"segue dizendo connected=True com os eixos congelados. "
            f"nós abertos: {bancada['abertos']}"
        )

    def test_o_no_velho_nao_e_reaberto_as_cegas(
        self, bancada: dict[str, Any], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Reabrir o número antigo pegaria OUTRO aparelho."""
        reader = _reader_com_morte(bancada, monkeypatch)
        assert reader.start() is True
        try:
            _esperar(lambda: str(_NO_ANTES) in bancada["abertos"], 2.0)
            quantos_antes = bancada["abertos"].count(str(_NO_ANTES))

            bancada["no_atual"] = ""
            bancada["morrer"].set()
            time.sleep(0.6)
        finally:
            reader.stop()

        assert bancada["abertos"].count(str(_NO_ANTES)) == quantos_antes, (
            "o reader reabriu o nó VELHO enquanto o controle estava fora — "
            "o kernel já pode ter dado esse número a outro aparelho"
        )

    def test_sumico_prolongado_nao_derruba_a_thread(
        self, bancada: dict[str, Any], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Controle desligado por um tempo não pode matar o leitor."""
        reader = _reader_com_morte(bancada, monkeypatch)
        assert reader.start() is True
        try:
            _esperar(lambda: str(_NO_ANTES) in bancada["abertos"], 2.0)
            bancada["no_atual"] = ""
            bancada["morrer"].set()
            time.sleep(1.0)

            bancada["no_atual"] = str(_NO_DEPOIS)
            voltou = _esperar(
                lambda: str(_NO_DEPOIS) in bancada["abertos"], 4.0
            )
        finally:
            reader.stop()
        assert voltou, "a thread do leitor não sobreviveu ao sumiço prolongado"


def _esperar(condicao: Any, limite_s: float) -> bool:
    """Espera ativa curta — devolve se a condição virou verdadeira a tempo."""
    fim = time.time() + limite_s
    while time.time() < fim:
        if condicao():
            return True
        time.sleep(0.02)
    return False
