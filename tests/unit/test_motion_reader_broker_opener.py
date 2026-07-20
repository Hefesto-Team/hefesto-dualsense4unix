"""Opener injetável do `PhysicalReportReader` (BROKER-01 §6.2) — sem hardware.

O que estes testes travam:

1. **Todos os gatilhos de reopen passam pelo opener**: start inicial,
   silêncio ≥ limiar, `request_reopen` (retarget de primário) e ENODEV/EOF
   (wake BT / hotplug-out) — o único `open` do loop é o `self._opener(path)`.
2. **OSError do opener cai no backoff existente** (o loop não morre e a
   próxima tentativa recupera o fluxo).
3. **Default = comportamento de hoje**: sem opener injetado, o reader abre
   por caminho com `os.open(path, O_RDONLY)`.
4. **`make_broker_opener`**: broker responde ⇒ o fd do broker é usado e
   NENHUM open por caminho acontece (grep-prova em runtime); broker
   ausente/recusa/dublê sem `open_fd` ⇒ fallback `os.open` — nunca exceção.
"""
from __future__ import annotations

import contextlib
import os
import time
from typing import Any

import pytest

from hefesto_dualsense4unix.core import physical_report_reader as prr
from hefesto_dualsense4unix.core.physical_report_reader import (
    MOTION_WINDOW_LEN,
    PhysicalReportReader,
)
from hefesto_dualsense4unix.integrations import hidraw_broker_client as hbc

_WINDOW = bytes(range(1, MOTION_WINDOW_LEN + 1))


def _usb_report(window: bytes = _WINDOW) -> bytes:
    raw = bytearray(64)
    raw[0] = 0x01
    raw[1:7] = bytes([0x80, 0x80, 0x80, 0x80, 0, 0])
    raw[16 : 16 + MOTION_WINDOW_LEN] = window
    raw[53] = 0x29
    return bytes(raw)


class _FakeVpad:
    player = 3

    def __init__(self) -> None:
        self.windows: list[bytes] = []
        self.streaming: list[bool] = []

    def forward_motion(self, window: bytes) -> None:
        self.windows.append(bytes(window))

    def set_motion_streaming(self, on: bool) -> None:
        self.streaming.append(bool(on))


def _esperar(cond: Any, timeout_s: float = 2.0) -> bool:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if cond():
            return True
        time.sleep(0.005)
    return False


class _PipeOpener:
    """Opener de teste: cada chamada entrega um pipe NOVO (e guarda a escrita)."""

    def __init__(self, *, falhas_iniciais: int = 0) -> None:
        self.calls: list[str] = []
        self.escritas: list[int] = []
        self._falhas = falhas_iniciais

    def __call__(self, path: str) -> int:
        self.calls.append(path)
        if self._falhas > 0:
            self._falhas -= 1
            raise OSError("broker e caminho indisponíveis (teste)")
        lido, escrita = os.pipe()
        self.escritas.append(escrita)
        return lido

    def fechar(self) -> None:
        for fd in self.escritas:
            with contextlib.suppress(OSError):
                os.close(fd)


class TestOpenerNosGatilhosDeReopen:
    def test_start_inicial_abre_pelo_opener(self) -> None:
        opener = _PipeOpener()
        vpad = _FakeVpad()
        reader = PhysicalReportReader(
            path_provider=lambda: "/dev/hidraw-fake", vpad=vpad, opener=opener
        )
        try:
            reader.start()
            assert _esperar(lambda: len(opener.escritas) >= 1)
            assert opener.calls == ["/dev/hidraw-fake"]
            os.write(opener.escritas[0], _usb_report())
            assert _esperar(lambda: vpad.windows)
            assert vpad.windows[0] == _WINDOW
        finally:
            reader.stop()
            opener.fechar()

    def test_silencio_reabre_pelo_opener(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # Sem nenhum byte no fd, o limiar de silêncio derruba e reabre — e o
        # reopen TAMBÉM passa pelo opener (o caminho que dava EACCES na v1).
        monkeypatch.setattr(prr, "_SELECT_TIMEOUT_S", 0.05)
        monkeypatch.setattr(prr, "_SILENCE_REOPEN_S", 0.1)
        opener = _PipeOpener()
        vpad = _FakeVpad()
        reader = PhysicalReportReader(
            path_provider=lambda: "/dev/hidraw-fake", vpad=vpad, opener=opener
        )
        try:
            reader.start()
            assert _esperar(lambda: len(opener.calls) >= 2)
        finally:
            reader.stop()
            opener.fechar()

    def test_request_reopen_usa_o_opener(self) -> None:
        opener = _PipeOpener()
        vpad = _FakeVpad()
        reader = PhysicalReportReader(
            path_provider=lambda: "/dev/hidraw-fake", vpad=vpad, opener=opener
        )
        try:
            reader.start()
            assert _esperar(lambda: len(opener.calls) >= 1)
            reader.request_reopen("primary_changed")
            assert _esperar(lambda: len(opener.calls) >= 2)
        finally:
            reader.stop()
            opener.fechar()

    def test_eof_do_fd_reabre_pelo_opener(self) -> None:
        # Wake BT/hotplug-out: o fd morre (EOF/ENODEV) e o loop re-resolve o
        # path e REABRE pelo opener — o fluxo volta no fd novo.
        opener = _PipeOpener()
        vpad = _FakeVpad()
        reader = PhysicalReportReader(
            path_provider=lambda: "/dev/hidraw-fake", vpad=vpad, opener=opener
        )
        try:
            reader.start()
            assert _esperar(lambda: len(opener.escritas) >= 1)
            os.close(opener.escritas[0])  # EOF: "o nó sumiu"
            assert _esperar(lambda: len(opener.escritas) >= 2)
            os.write(opener.escritas[1], _usb_report())
            assert _esperar(lambda: vpad.windows)
        finally:
            reader.stop()
            for fd in opener.escritas[1:]:
                with contextlib.suppress(OSError):
                    os.close(fd)

    def test_oserror_do_opener_cai_no_backoff_e_recupera(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(prr, "_BACKOFF_START_S", 0.01)
        opener = _PipeOpener(falhas_iniciais=1)
        vpad = _FakeVpad()
        reader = PhysicalReportReader(
            path_provider=lambda: "/dev/hidraw-fake", vpad=vpad, opener=opener
        )
        try:
            reader.start()
            assert _esperar(lambda: len(opener.escritas) >= 1)
            assert len(opener.calls) >= 2  # a 1ª foi a OSError
            os.write(opener.escritas[0], _usb_report())
            assert _esperar(lambda: vpad.windows)
        finally:
            reader.stop()
            opener.fechar()


class TestOpenerDefault:
    def test_sem_opener_abre_por_caminho_com_os_open(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        lido, escrita = os.pipe()
        chamadas: list[tuple[str, int]] = []

        def _fake_open(path: str, flags: int) -> int:
            chamadas.append((path, flags))
            return os.dup(lido)

        monkeypatch.setattr(prr.os, "open", _fake_open)
        vpad = _FakeVpad()
        reader = PhysicalReportReader(
            path_provider=lambda: "/dev/hidraw-fake", vpad=vpad
        )
        try:
            reader.start()
            assert _esperar(lambda: chamadas)
            assert chamadas[0] == ("/dev/hidraw-fake", os.O_RDONLY)
        finally:
            reader.stop()
            os.close(escrita)
            os.close(lido)


class _FakeBrokerOpen:
    """Dublê do cliente: `open_fd` roteirizado (fd real, None ou explosão)."""

    def __init__(self, resultado: Any) -> None:
        self.resultado = resultado
        self.calls: list[str] = []

    def open_fd(self, node: str) -> int | None:
        self.calls.append(node)
        if isinstance(self.resultado, Exception):
            raise self.resultado
        if callable(self.resultado):
            out = self.resultado()
            return int(out) if out is not None else None
        return self.resultado if self.resultado is None else int(self.resultado)


class _DaemonComBroker:
    def __init__(self, broker: Any) -> None:
        self._hidraw_broker_client = broker


class TestMakeBrokerOpener:
    def test_fd_do_broker_e_usado_sem_os_open(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        lido, escrita = os.pipe()
        broker = _FakeBrokerOpen(lambda: os.dup(lido))
        opener = hbc.make_broker_opener(_DaemonComBroker(broker))

        def _nunca(*_a: Any, **_k: Any) -> int:
            raise AssertionError("os.open por caminho no caminho broker-ativo")

        monkeypatch.setattr(hbc.os, "open", _nunca)
        try:
            fd = opener("/dev/hidraw3")
            assert broker.calls == ["/dev/hidraw3"]
            assert os.fstat(fd).st_ino == os.fstat(lido).st_ino
            os.close(fd)
        finally:
            monkeypatch.undo()
            os.close(lido)
            os.close(escrita)

    def test_broker_recusando_cai_no_os_open(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        broker = _FakeBrokerOpen(None)
        opener = hbc.make_broker_opener(_DaemonComBroker(broker))
        chamadas: list[tuple[str, int]] = []
        monkeypatch.setattr(
            hbc.os, "open", lambda p, f: chamadas.append((p, f)) or 42
        )
        assert opener("/dev/hidraw3") == 42
        assert broker.calls == ["/dev/hidraw3"]
        assert chamadas == [("/dev/hidraw3", os.O_RDONLY)]

    def test_duble_sem_open_fd_cai_no_os_open(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Dublê antigo (só hide/restore) não pode explodir o opener — o
        # suppress interno degrada para o open por caminho.
        class _SemOpenFd:
            pass

        opener = hbc.make_broker_opener(_DaemonComBroker(_SemOpenFd()))
        monkeypatch.setattr(hbc.os, "open", lambda p, f: 43)
        assert opener("/dev/hidraw3") == 43

    def test_broker_explodindo_cai_no_os_open(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        broker = _FakeBrokerOpen(RuntimeError("boom"))
        opener = hbc.make_broker_opener(_DaemonComBroker(broker))
        monkeypatch.setattr(hbc.os, "open", lambda p, f: 44)
        assert opener("/dev/hidraw3") == 44

    def test_fallback_com_no_escondido_propaga_oserror(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Janela broker-morto com nó 0600: o os.open dá EACCES e o contrato
        # do opener é PROPAGAR OSError (o backoff do reader cobre).
        broker = _FakeBrokerOpen(None)
        opener = hbc.make_broker_opener(_DaemonComBroker(broker))

        def _eacces(_p: str, _f: int) -> int:
            raise PermissionError("nó escondido, broker morto")

        monkeypatch.setattr(hbc.os, "open", _eacces)
        with pytest.raises(OSError):
            opener("/dev/hidraw3")


class TestGrepProvaPontaAPonta:
    def test_reader_broker_ativo_nunca_abre_por_caminho(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Grep-prova em runtime: com o broker servindo fd, NENHUM open por
        caminho do hidraw acontece — nem no reader, nem no fallback do
        opener (os.open é vigiado e o path do físico é proibido)."""
        lido, escrita = os.pipe()
        broker = _FakeBrokerOpen(lambda: os.dup(lido))
        daemon = _DaemonComBroker(broker)
        vpad = _FakeVpad()

        proibidos: list[str] = []
        real_open = os.open

        def _vigiado(path: Any, flags: int, *args: Any, **kwargs: Any) -> int:
            if path == "/dev/hidraw-fisico":
                proibidos.append(str(path))
            return real_open(path, flags, *args, **kwargs)

        monkeypatch.setattr(os, "open", _vigiado)
        reader = PhysicalReportReader(
            path_provider=lambda: "/dev/hidraw-fisico",
            vpad=vpad,
            opener=hbc.make_broker_opener(daemon),
        )
        try:
            reader.start()
            os.write(escrita, _usb_report())
            assert _esperar(lambda: vpad.windows)
            # O fd veio do broker (dublê chamado com o path do físico)...
            assert broker.calls and broker.calls[0] == "/dev/hidraw-fisico"
            # ...e NINGUÉM abriu o físico por caminho.
            assert proibidos == []
        finally:
            reader.stop()
            monkeypatch.undo()
            os.close(escrita)
            os.close(lido)
