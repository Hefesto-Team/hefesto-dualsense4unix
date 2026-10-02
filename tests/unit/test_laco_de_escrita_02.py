"""LACO-DE-ESCRITA-02 — os dois defeitos do laço de saída, achados por leitura"""
from __future__ import annotations

import threading
import time
import types
from typing import Any

import hidapi
import pytest

from hefesto_dualsense4unix.core import backend_pydualsense as bp
from hefesto_dualsense4unix.core import ds_output_report as rep


class _LoggerDeMentira:
    """Registra as linhas do `logger` do backend, com nível e campos."""

    def __init__(self) -> None:
        self.linhas: list[tuple[str, str, dict[str, Any]]] = []

    def _guardar(self, nivel: str, evento: str, **campos: Any) -> None:
        self.linhas.append((nivel, evento, campos))

    def debug(self, evento: str, **campos: Any) -> None:
        self._guardar("debug", evento, **campos)

    def info(self, evento: str, **campos: Any) -> None:
        self._guardar("info", evento, **campos)

    def warning(self, evento: str, **campos: Any) -> None:
        self._guardar("warning", evento, **campos)

    def error(self, evento: str, **campos: Any) -> None:
        self._guardar("error", evento, **campos)

    def eventos(self, nome: str) -> list[dict[str, Any]]:
        return [campos for _n, evento, campos in self.linhas if evento == nome]


def _handle_do_radio() -> bp._PinnedPyDualSense:
    """Um handle com só o que `writeReport` usa (o resto é dublê)."""
    inst = bp._PinnedPyDualSense.__new__(bp._PinnedPyDualSense)
    inst._bt_seq = 0
    inst._write_lock = threading.Lock()
    return inst


def test_escritores_concorrentes_no_radio_nunca_repetem_o_seq(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Quatro threads escrevendo no MESMO handle BT produzem quatro `seq`"""
    inst = _handle_do_radio()
    report = list(rep.build_bt_report(bytearray(rep.COMMON_LEN), seq=0))
    assert len(report) == 78 and report[0] == 0x31

    vistos: list[int] = []
    trava_do_registro = threading.Lock()

    class _DispositivoDeMentira:
        def write(self, dados: bytes) -> None:
            with trava_do_registro:
                vistos.append(dados[1] >> 4)

    inst.device = _DispositivoDeMentira()

    carimbo_real = rep.stamp_bt_seq

    def _carimbo_lento(buf: Any, seq: int) -> None:
        carimbo_real(buf, seq)
        time.sleep(0.02)

    monkeypatch.setattr(rep, "stamp_bt_seq", _carimbo_lento)

    largada = threading.Event()

    def _escritor() -> None:
        largada.wait(timeout=5)
        inst.writeReport(list(report))

    threads = [threading.Thread(target=_escritor) for _ in range(4)]
    for t in threads:
        t.start()
    largada.set()
    for t in threads:
        t.join(timeout=10)
        assert not t.is_alive()

    assert len(vistos) == 4
    assert len(set(vistos)) == 4, f"seq repetido entre escritores: {vistos}"
    assert vistos == [0, 1, 2, 3], f"quadros entregues fora de ordem: {vistos}"
    assert inst._bt_seq == 4


def test_o_write_acontece_com_o_lock_na_mao() -> None:
    """O `write` está DENTRO da seção crítica, não só o contador."""
    inst = _handle_do_radio()
    visto = {"com_o_lock": None}

    class _DispositivoDeMentira:
        def write(self, _dados: bytes) -> None:
            visto["com_o_lock"] = inst._write_lock.locked()

    inst.device = _DispositivoDeMentira()
    inst.writeReport(list(rep.build_bt_report(bytearray(rep.COMMON_LEN), seq=0)))
    assert visto["com_o_lock"] is True, "o write do rádio saiu fora do lock"

    visto["com_o_lock"] = None
    inst.writeReport(list(rep.build_usb_report(bytearray(rep.COMMON_LEN))))
    assert visto["com_o_lock"] is True, "o write do cabo saiu fora do lock"


def test_cada_handle_tem_o_seu_proprio_lock() -> None:
    """O lock é POR HANDLE, e é isso que impede um `hid_write` pendurado num"""
    a = bp._PinnedPyDualSense(b"/dev/hidraw-teste-a", is_edge=False)
    b = bp._PinnedPyDualSense(b"/dev/hidraw-teste-b", is_edge=False)

    assert a._write_lock is not b._write_lock
    assert a._write_lock is not bp._PinnedPyDualSense._write_lock
    assert b._write_lock is not bp._PinnedPyDualSense._write_lock


def test_o_cabo_tambem_passa_pelo_lock_e_sai_sem_carimbo() -> None:
    """O `0x02` não ganha `seq` (não tem campo para ele) mas continua saindo —"""
    inst = _handle_do_radio()
    enviados: list[bytes] = []

    class _DispositivoDeMentira:
        def write(self, dados: bytes) -> None:
            enviados.append(dados)

    inst.device = _DispositivoDeMentira()
    usb = list(rep.build_usb_report(bytearray(rep.COMMON_LEN)))
    inst.writeReport(usb)

    assert enviados == [bytes(usb)]
    assert inst._bt_seq == 0


class _HidDevice:
    """O `hid_device` do C, só no que o laço toca: o modo do `hid_read`."""

    def __init__(self) -> None:
        self.bloqueante = True


class _DispositivoDoLaco:
    """A base dos dispositivos de mentira do laço: o `_device` do wrapper."""

    def __init__(self) -> None:
        self._device = _HidDevice()

    def _vazio(self) -> None:
        assert not self._device.bloqueante, (
            "leitura vazia com o handle bloqueante: no aparelho ela não voltaria"
        )


def _trocar_o_modo(dev: _HidDevice, nonblock: int) -> int:
    dev.bloqueante = not nonblock
    return 0


@pytest.fixture(autouse=True)
def _o_c_do_hidapi(monkeypatch: pytest.MonkeyPatch) -> None:
    """O lado C do `hidapi`, no único ponto que o laço toca além do `read`."""
    monkeypatch.setattr(
        hidapi, "hidapi", types.SimpleNamespace(hid_set_nonblocking=_trocar_o_modo)
    )


def _estado_do_cabo() -> bytes:
    """Um report de ESTADO do cabo (`0x01`, 64 bytes): passa pela porta."""
    return bytes([0x01]) + bytes(63)


def _handle_do_laco() -> bp._PinnedPyDualSense:
    """Um handle com o que o `sendReport` usa (mesmo molde do throttle)."""
    inst = bp._PinnedPyDualSense.__new__(bp._PinnedPyDualSense)
    inst.input_report_length = 64
    inst.connected = True
    inst.ds_thread = True
    inst._throttle_sec = bp.REPORT_THREAD_THROTTLE_SEC
    inst._last_out_report = None
    inst._last_write_at = 0.0
    inst._last_change_at = float("-inf")
    inst._output_muted = False
    inst._rumble_active = False
    inst._rumble_stop_pending = False
    inst._write_lock = threading.Lock()
    return inst


def _read_input_do_upstream(in_report: Any) -> None:
    """A PRIMEIRA linha do `readInput` do upstream, e só ela."""
    list(in_report)[1:]


def test_leitura_vazia_nao_mata_a_thread_e_a_saida_continua(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`read` devolvendo `None` é resposta legítima da leitura não-bloqueante:"""
    inst = _handle_do_laco()
    inst.conType = None

    contas = {"read": 0, "write": 0, "sleep": 0, "parse": 0}
    respostas: list[bytes | None] = [
        None,
        None,
        _estado_do_cabo(),
        None,
        _estado_do_cabo(),
        None,
    ]

    class _DispositivoDeMentira(_DispositivoDoLaco):
        def read(self, _n: int) -> bytes | None:
            resposta = respostas[min(contas["read"], len(respostas) - 1)]
            contas["read"] += 1
            if resposta is None:
                self._vazio()
            return resposta

    inst.device = _DispositivoDeMentira()

    def _parse(in_report: Any) -> None:
        contas["parse"] += 1
        _read_input_do_upstream(in_report)

    monkeypatch.setattr(inst, "readInput", _parse)
    monkeypatch.setattr(
        inst, "prepareReport", lambda: [contas["sleep"] & 0xFF] + [0] * 63
    )

    def _conta_write(_r: object) -> None:
        contas["write"] += 1

    monkeypatch.setattr(inst, "writeReport", _conta_write)

    def _sono_de_mentira(_secs: float) -> None:
        contas["sleep"] += 1
        if contas["sleep"] >= 4:
            inst.ds_thread = False

    monkeypatch.setattr(bp.time, "sleep", _sono_de_mentira)

    inst.sendReport()

    assert contas["sleep"] == 4, "a thread não chegou ao fim dos ciclos"
    assert inst.connected is True, "leitura vazia não é desconexão"
    assert contas["write"] == 4, "os ciclos mudos ficaram sem SAÍDA"
    assert contas["parse"] == 2, "os ciclos com dado não chegaram ao `readInput`"


def test_o_silencio_da_entrada_deixa_rastro_no_journal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """UMA linha de aviso por episódio de silêncio, e uma de volta quando a"""
    inst = _handle_do_laco()
    inst.conType = None
    inst._pinned_path = b"/dev/hidraw-teste"

    registro = _LoggerDeMentira()
    monkeypatch.setattr(bp, "logger", registro)

    relogio = {"t": 1000.0}
    contas = {"read": 0, "sleep": 0}
    mudos = 6

    class _DispositivoDeMentira(_DispositivoDoLaco):
        def read(self, _n: int) -> bytes | None:
            contas["read"] += 1
            if contas["read"] == mudos + 1:
                return _estado_do_cabo()
            self._vazio()
            return None

    inst.device = _DispositivoDeMentira()
    monkeypatch.setattr(inst, "readInput", _read_input_do_upstream)
    monkeypatch.setattr(inst, "prepareReport", lambda: [0] * 64)
    monkeypatch.setattr(inst, "writeReport", lambda _r: None)
    monkeypatch.setattr(bp.time, "monotonic", lambda: relogio["t"])

    def _sono_de_mentira(_secs: float) -> None:
        contas["sleep"] += 1
        relogio["t"] += 0.5
        if contas["sleep"] >= mudos + 1:
            inst.ds_thread = False

    monkeypatch.setattr(bp.time, "sleep", _sono_de_mentira)

    inst.sendReport()

    avisos = registro.eventos("report_thread_entrada_muda")
    voltas = registro.eventos("report_thread_entrada_voltou")
    assert len(avisos) == 1, f"esperado UM aviso por episódio, veio {len(avisos)}"
    assert len(voltas) == 1, "a volta da entrada não foi registrada"
    assert avisos[0]["segundos"] >= bp.LEITURA_VAZIA_AVISO_SEC
    assert voltas[0]["segundos"] >= bp.LEITURA_VAZIA_AVISO_SEC
    assert inst.connected is True


def test_silencio_curto_nao_polui_o_journal(monkeypatch: pytest.MonkeyPatch) -> None:
    """Um ciclo mudo isolado não é notícia — e não pode virar linha."""
    inst = _handle_do_laco()
    inst.conType = None

    registro = _LoggerDeMentira()
    monkeypatch.setattr(bp, "logger", registro)

    relogio = {"t": 500.0}
    contas = {"read": 0, "sleep": 0}

    class _DispositivoDeMentira(_DispositivoDoLaco):
        def read(self, _n: int) -> bytes | None:
            contas["read"] += 1
            if contas["read"] == 1 or contas["read"] % 2 == 1:
                self._vazio()
                return None
            return _estado_do_cabo()

    inst.device = _DispositivoDeMentira()
    monkeypatch.setattr(inst, "readInput", _read_input_do_upstream)
    monkeypatch.setattr(inst, "prepareReport", lambda: [0] * 64)
    monkeypatch.setattr(inst, "writeReport", lambda _r: None)
    monkeypatch.setattr(bp.time, "monotonic", lambda: relogio["t"])

    def _sono_de_mentira(_secs: float) -> None:
        contas["sleep"] += 1
        relogio["t"] += 0.032
        if contas["sleep"] >= 3:
            inst.ds_thread = False

    monkeypatch.setattr(bp.time, "sleep", _sono_de_mentira)

    inst.sendReport()

    assert registro.eventos("report_thread_entrada_muda") == []
    assert registro.eventos("report_thread_entrada_voltou") == []


def test_no_radio_a_saida_espera_a_entrada_que_parou(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No rádio, saída nova não entra num episódio de entrada já muda."""
    from pydualsense.enums import ConnectionType

    inst = _handle_do_laco()
    inst.conType = ConnectionType.BT
    inst._pinned_path = b"/dev/hidraw-teste"
    inst._rumble_active = True

    relogio = {"t": 1000.0}
    contas = {"read": 0, "write": 0, "sleep": 0}
    mudos = 3

    class _DispositivoDeMentira(_DispositivoDoLaco):
        _entregou = False

        def read(self, _n: int) -> bytes | None:
            contas["read"] += 1
            if contas["sleep"] >= mudos and not self._entregou:
                self._entregou = True
                return _estado_do_cabo()
            self._vazio()
            return None

    inst.device = _DispositivoDeMentira()
    monkeypatch.setattr(inst, "readInput", lambda _r: None)
    monkeypatch.setattr(inst, "prepareReport", lambda: [1, 2, 3])

    def _conta_write(_r: object) -> None:
        contas["write"] += 1

    monkeypatch.setattr(inst, "writeReport", _conta_write)
    monkeypatch.setattr(bp.time, "monotonic", lambda: relogio["t"])

    def _sono_de_mentira(_secs: float) -> None:
        contas["sleep"] += 1
        relogio["t"] += 1.1 if contas["sleep"] == 1 else 0.6
        if contas["sleep"] >= 4:
            inst.ds_thread = False

    monkeypatch.setattr(bp.time, "sleep", _sono_de_mentira)

    inst.sendReport()

    assert contas["write"] == 2, (
        "a saída do rádio não esperou a entrada "
        f"(escritas={contas['write']}, esperadas a primeira e a de volta)"
    )
    assert inst._saida_adiada_pelo_silencio is False


def test_excecao_inesperada_no_laco_deixa_linha_antes_de_morrer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A rede: exceção que ninguém previu não pode matar a `report_thread` em"""
    inst = _handle_do_laco()
    registro = _LoggerDeMentira()
    monkeypatch.setattr(bp, "logger", registro)

    class _DispositivoDeMentira(_DispositivoDoLaco):
        def read(self, _n: int) -> bytes:
            raise ValueError("algo que ninguém previu")

    inst.device = _DispositivoDeMentira()

    inst.sendReport()

    assert inst.connected is False
    mortes = registro.eventos("report_thread_morreu_por_excecao")
    assert len(mortes) == 1
    assert mortes[0]["tipo"] == "ValueError"
