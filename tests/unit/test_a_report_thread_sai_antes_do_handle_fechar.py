"""A report_thread sai antes de o handle fechar — A-REPORT-THREAD-SAI-ANTES-DO-HANDLE-FECHAR-01."""

from __future__ import annotations

import threading
import time
from collections import deque
from collections.abc import Iterator
from typing import Any

import hidapi as hidapi_do_wrapper
import pytest
from pydualsense.enums import ConnectionType
from pydualsense.pydualsense import DSAudio, DSBattery, DSLight, DSState, DSTrigger

from hefesto_dualsense4unix.core import backend_pydualsense as bp
from hefesto_dualsense4unix.core import physical_report_reader as prr

TETO = bp.CLOSE_JOIN_TIMEOUT_SEC
FOLGA = 0.35


def _report_do_radio(*, botao_do_mic: bool = False) -> bytes:
    """Um `0x31` de estado, com CRC (78 bytes: o `determineConnectionType` lê BT)."""
    corpo = bytearray(prr.INPUT_REPORT_BT_SIZE)
    corpo[0] = prr.INPUT_REPORT_BT
    if botao_do_mic:
        corpo[2 + prr.BUTTONS2_OFFSET] |= prr.MIC_BUTTON_BIT
    crc = prr.bt_crc32(bytes(corpo[:-4]), seed=prr.BT_INPUT_CRC_SEED)
    corpo[-4:] = crc.to_bytes(4, "little")
    return bytes(corpo)


class _No:
    """O `hid_device` de UM nó: o que o kernel entrega e quem está no C agora."""

    def __init__(self) -> None:
        self.cond = threading.Condition()
        self.fila: deque[bytes] = deque()
        self.segurar_read = False
        self.segurar_write = False
        self.saiu = False
        self.bloqueante = True
        self.leitores = 0
        self.escritores = 0
        self.fechado = False
        self.liberado_com_uso = False
        self.writes_chamados = 0
        self.preso_no_read = threading.Event()
        self.preso_no_write = threading.Event()

    def soltar(self, report: bytes | None = None) -> None:
        """O kernel solta o `read`: com um report, ou tirando o nó."""
        with self.cond:
            if report is None:
                self.saiu = True
            else:
                self.fila.append(report)
                self.segurar_read = False
            self.cond.notify_all()

    def soltar_o_write(self) -> None:
        with self.cond:
            self.segurar_write = False
            self.cond.notify_all()


def _exigir(dev: Any) -> _No:
    if dev is None:
        raise TypeError(
            "initializer for ctype 'hid_device *' must be a cdata pointer, not NoneType"
        )
    assert isinstance(dev, _No)
    return dev


class _CDoHidapi:
    """`hid.c` do Linux no que o handle usa; o `hid_close` NÃO acorda ninguém."""

    def __init__(self) -> None:
        self.ffi = hidapi_do_wrapper.ffi

    def hid_read(self, dev: Any, bufp: Any, length: int) -> int:
        no = _exigir(dev)
        return self.hid_read_timeout(dev, bufp, length, -1 if no.bloqueante else 0)

    def hid_read_timeout(self, dev: Any, bufp: Any, length: int, ms: int) -> int:
        no = _exigir(dev)
        with no.cond:
            no.leitores += 1
            try:
                while not no.fila and not no.saiu:
                    if not no.segurar_read and ms == 0:
                        return 0
                    no.preso_no_read.set()
                    no.cond.wait()
                if no.fila:
                    quadro = no.fila.popleft()
                    n = min(length, len(quadro))
                    self.ffi.memmove(bufp, quadro, n)
                    return n
                return -1
            finally:
                no.leitores -= 1

    def hid_write(self, dev: Any, bufp: Any, length: int) -> int:
        no = _exigir(dev)
        with no.cond:
            no.writes_chamados += 1
            no.escritores += 1
            try:
                while no.segurar_write and not no.saiu:
                    no.preso_no_write.set()
                    no.cond.wait()
                return -1 if no.saiu else length
            finally:
                no.escritores -= 1

    def hid_set_nonblocking(self, dev: Any, nonblock: int) -> int:
        _exigir(dev).bloqueante = not nonblock
        return 0

    def hid_close(self, dev: Any) -> None:
        no = _exigir(dev)
        with no.cond:
            if no.leitores or no.escritores:
                no.liberado_com_uso = True
            no.fechado = True

    def hid_error(self, dev: Any) -> Any:
        _exigir(dev)
        return self.ffi.NULL


class _Diario:
    """O `logger` do backend, com os campos de cada linha."""

    def __init__(self) -> None:
        self.linhas: list[tuple[str, dict[str, Any]]] = []

    def _guardar(self, evento: str, **campos: Any) -> None:
        self.linhas.append((evento, campos))

    debug = info = warning = error = _guardar

    def eventos(self, nome: str) -> list[dict[str, Any]]:
        return [campos for evento, campos in self.linhas if evento == nome]


class _Bancada:
    def __init__(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self.c = _CDoHidapi()
        self.diario = _Diario()
        self.nos: list[_No] = []
        self.devices: list[Any] = []
        self.threads: list[threading.Thread] = []
        monkeypatch.setattr(hidapi_do_wrapper, "hidapi", self.c)
        monkeypatch.setattr(bp, "logger", self.diario)

    def device(self, no: _No) -> Any:
        """Um `hidapi.Device` DE VERDADE sobre o nó de mentira."""
        self.nos.append(no)
        dev = hidapi_do_wrapper.Device.__new__(hidapi_do_wrapper.Device)
        dev._device = no
        self.devices.append(dev)
        return dev

    def handle(self, no: _No, *, path: bytes = b"/dev/hidraw9") -> bp._PinnedPyDualSense:
        """O handle de produção, montado como o `init()` o deixa."""
        h = bp._PinnedPyDualSense(path, is_edge=False)
        h.device = self.device(no)
        h.is_edge = False
        h.light = DSLight()
        h.audio = DSAudio()
        h.triggerL = DSTrigger()
        h.triggerR = DSTrigger()
        h.state = DSState()
        h.battery = DSBattery()
        h.conType = ConnectionType.BT
        h.input_report_length = 78
        h.output_report_length = 78
        h.ds_thread = True
        h.connected = True
        h._throttle_sec = 0.002
        return h

    def subir(self, h: bp._PinnedPyDualSense) -> threading.Thread:
        t = threading.Thread(target=h.sendReport, daemon=True, name="régua")
        h.report_thread = t
        self.threads.append(t)
        t.start()
        return t

    def soltar_tudo(self) -> None:
        for no in self.nos:
            no.soltar()
            no.soltar_o_write()
        for t in self.threads:
            t.join(timeout=2.0)
        for dev in self.devices:
            dev._device = None


@pytest.fixture
def bancada(monkeypatch: pytest.MonkeyPatch) -> Iterator[_Bancada]:
    b = _Bancada(monkeypatch)
    try:
        yield b
    finally:
        b.soltar_tudo()


def _preso_no_read(bancada: _Bancada, no: _No) -> tuple[bp._PinnedPyDualSense, threading.Thread]:
    """Um handle com a thread de produção DENTRO do `read`, que o kernel segura."""
    no.segurar_read = True
    h = bancada.handle(no)
    t = bancada.subir(h)
    assert no.preso_no_read.wait(2.0), "a thread não chegou ao read"
    return h, t


def _cronometrar(fn: Any) -> float:
    inicio = time.monotonic()
    fn()
    return time.monotonic() - inicio


def test_o_handle_so_fecha_depois_que_a_thread_sai(bancada: _Bancada) -> None:
    """A thread presa no `read`; `close()` volta no teto e NÃO fecha por cima dela."""
    no = _No()
    h, t = _preso_no_read(bancada, no)

    gasto = _cronometrar(h.close)

    assert gasto <= TETO + FOLGA, f"o close levou {gasto:.2f} s"
    assert no.fechado is False, "o hid_device fechou com a thread dentro do read"
    assert t.is_alive()
    no.soltar()
    t.join(timeout=2.0)
    assert not t.is_alive()
    assert no.fechado is True, "quem saiu por último não fechou"
    assert no.liberado_com_uso is False
    assert bancada.diario.eventos("report_thread_morreu_por_excecao") == []
    saidas = bancada.diario.eventos("report_thread_saiu_e_fechou")
    assert len(saidas) == 1
    assert saidas[0]["path"] == b"/dev/hidraw9"
    assert saidas[0]["segundos"] >= TETO


def test_o_aviso_diz_onde_a_thread_estava(bancada: _Bancada) -> None:
    """O `report_thread_nao_encerrou` traz o nó, os segundos e ONDE ela está."""
    no = _No()
    h, _t = _preso_no_read(bancada, no)

    h.close()

    avisos = bancada.diario.eventos("report_thread_nao_encerrou")
    assert len(avisos) == 1
    aviso = avisos[0]
    assert aviso["path"] == b"/dev/hidraw9"
    assert aviso["segundos"] >= TETO - 0.05
    assert "hid_read_timeout" in (aviso["onde"] or ""), aviso["onde"]
    assert "ficou com ela" in aviso["detalhe"]


def test_depois_do_sinal_o_report_que_chega_e_jogado_fora(bancada: _Bancada) -> None:
    """O kernel solta o `read` com um REPORT (o dedo no botão do microfone)."""
    no = _No()
    no.fila.append(_report_do_radio())
    h = bancada.handle(no)
    t = bancada.subir(h)
    for _ in range(400):
        if h._reports_aceitos >= 1 and no.writes_chamados >= 1:
            break
        time.sleep(0.005)
    assert h._reports_aceitos == 1
    no.preso_no_read.clear()
    with no.cond:
        no.segurar_read = True
    assert no.preso_no_read.wait(2.0)
    writes_antes = no.writes_chamados
    seq_antes = h._mic_mudo_seq

    h.close()
    with pytest.raises(OSError):
        h.writeReport([0x31] + [0] * 77)
    assert no.writes_chamados == writes_antes, "a escrita depois da marca chegou ao C"
    no.soltar(_report_do_radio(botao_do_mic=True))
    t.join(timeout=2.0)

    assert not t.is_alive()
    assert no.writes_chamados == writes_antes, "a thread escreveu depois do sinal"
    assert h._mic_mudo_seq == seq_antes, "o report de depois do sinal virou aperto"
    saidas = bancada.diario.eventos("report_thread_saiu_e_fechou")
    assert len(saidas) == 1 and saidas[0]["descartados"] == 1
    assert no.fechado is True and no.liberado_com_uso is False


def test_o_escritor_avulso_fecha_ao_sair_e_o_close_nao_espera_por_ele(
    bancada: _Bancada,
) -> None:
    """Um `hid_write` avulso preso (um USB lento); a `report_thread` já saiu."""
    no = _No()
    h = bancada.handle(no)
    h.report_thread = None
    no.segurar_write = True
    quadro = [0x31] + [0] * 77
    avulso = threading.Thread(target=lambda: h.writeReport(quadro), daemon=True)
    bancada.threads.append(avulso)
    avulso.start()
    assert no.preso_no_write.wait(2.0)

    quem_fecha = threading.Thread(target=h.close, daemon=True)
    bancada.threads.append(quem_fecha)
    inicio = time.monotonic()
    quem_fecha.start()
    quem_fecha.join(timeout=TETO + FOLGA)
    gasto = time.monotonic() - inicio

    assert not quem_fecha.is_alive(), f"o close() esperou o write ({gasto:.2f} s)"
    assert no.fechado is False, "o hid_device fechou com o write dentro"
    no.soltar_o_write()
    avulso.join(timeout=2.0)
    assert no.fechado is True, "o avulso saiu e não fechou"
    assert no.liberado_com_uso is False
    assert len(bancada.diario.eventos("escrita_avulsa_saiu_e_fechou")) == 1
    chamados = no.writes_chamados
    with pytest.raises(OSError):
        h.writeReport(quadro)
    assert no.writes_chamados == chamados, "a escrita depois da marca chegou ao C"


def _mesa_presa(
    bancada: _Bancada, n: int
) -> tuple[Any, list[_No], list[bp._PinnedPyDualSense]]:
    ctl = bp.PyDualSenseController()
    nos: list[_No] = []
    handles: list[bp._PinnedPyDualSense] = []
    for i in range(n):
        no = _No()
        no.segurar_read = True
        h = bancada.handle(no, path=f"/dev/hidraw{20 + i}".encode())
        bancada.subir(h)
        assert no.preso_no_read.wait(2.0)
        ctl._handles[f"aabbcc0000a{i}"] = h
        nos.append(no)
        handles.append(h)
    return ctl, nos, handles


def _os_que_sairam_param_e_fecham(
    bancada: _Bancada, nos: list[_No], handles: list[bp._PinnedPyDualSense]
) -> None:
    """Todo handle que saiu recebeu o sinal, e fecha quando o «kernel» o solta."""
    assert all(h.ds_thread is False for h in handles), "um handle saiu sem o sinal"
    for no in nos:
        no.soltar(_report_do_radio())
    for h in handles:
        assert h.report_thread is not None
        h.report_thread.join(timeout=2.0)
        assert not h.report_thread.is_alive(), "a thread que saiu não parou"
    assert all(no.fechado for no in nos), "quem saiu por último não fechou"
    assert not any(no.liberado_com_uso for no in nos)
    assert len(bancada.diario.eventos("report_thread_saiu_e_fechou")) == len(handles)


def test_os_quatro_presos_param_num_teto_so(bancada: _Bancada) -> None:
    """`disconnect()` com os quatro presos no `read` volta em < 1,5 x o teto."""
    ctl, nos, handles = _mesa_presa(bancada, 4)

    gasto = _cronometrar(ctl.disconnect)

    assert gasto < 1.5 * TETO, f"o disconnect levou {gasto:.2f} s com quatro presos"
    assert not any(no.fechado for no in nos), "fechou por cima de uma leitura"
    assert len(bancada.diario.eventos("report_thread_nao_encerrou")) == 4
    _os_que_sairam_param_e_fecham(bancada, nos, handles)


def test_os_dois_que_saem_no_hotplug_pagam_um_teto(bancada: _Bancada) -> None:
    """O `_close_handles` com duas chaves saindo, idem."""
    ctl, nos, handles = _mesa_presa(bancada, 4)
    ficam = {"aabbcc0000a0", "aabbcc0000a1"}

    def _hotplug() -> None:
        with ctl._io_lock:
            ctl._close_handles(keep=ficam)

    gasto = _cronometrar(_hotplug)

    assert gasto < 1.5 * TETO, f"o hotplug levou {gasto:.2f} s com dois saindo"
    assert set(ctl._handles) == ficam
    assert not any(no.fechado for no in nos)
    assert all(h.ds_thread is True for h in handles[:2]), "o sinal alcançou quem fica"
    _os_que_sairam_param_e_fecham(bancada, nos[2:], handles[2:])


def _find_device_de_mentira(
    bancada: _Bancada, monkeypatch: pytest.MonkeyPatch
) -> list[_No]:
    criados: list[_No] = []

    def _achar(self: bp._PinnedPyDualSense) -> tuple[Any, bool]:
        no = _No()
        no.fila.append(_report_do_radio())
        criados.append(no)
        return bancada.device(no), False

    monkeypatch.setattr(bp._PinnedPyDualSense, "_pydualsense__find_device", _achar)
    return criados


def test_pelo_open_one_a_thread_e_daemon_e_tem_o_nome_do_no(
    bancada: _Bancada, monkeypatch: pytest.MonkeyPatch
) -> None:
    """O `init()` dentro do `_runner` do `_open_one` de produção."""
    _find_device_de_mentira(bancada, monkeypatch)
    ctl = bp.PyDualSenseController()

    handle = ctl._open_one(b"/dev/hidraw5", is_edge=False)

    assert handle is not None
    thread = handle.report_thread
    bancada.threads.append(thread)
    assert thread.daemon is True
    assert thread.name == "hefesto-report-hidraw5"
    assert handle.conType is ConnectionType.BT
    handle.close()


def test_por_uma_thread_que_nao_e_daemon_a_report_thread_segue_daemon(
    bancada: _Bancada, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Um `init()` chamado de uma thread NÃO-daemon (um ensaio, um teste)."""
    _find_device_de_mentira(bancada, monkeypatch)
    h = bp._PinnedPyDualSense(b"/dev/hidraw6", is_edge=False)
    quem_inicia = threading.Thread(target=h.init, daemon=False)
    quem_inicia.start()
    quem_inicia.join(timeout=2.0)

    thread = h.report_thread
    bancada.threads.append(thread)
    assert thread.daemon is True
    assert thread.name == "hefesto-report-hidraw6"
    h.close()


def test_com_o_controle_falando_o_close_fecha_na_hora_sem_aviso(bancada: _Bancada) -> None:
    """(a) A thread vê o sinal, o `close()` fecha ele mesmo e não há aviso."""
    no = _No()
    h = bancada.handle(no)
    t = bancada.subir(h)
    for _ in range(10):
        no.soltar(_report_do_radio())
        time.sleep(0.005)

    h.close()

    assert no.fechado is True, "o close() voltou com o dispositivo aberto"
    assert not t.is_alive()
    assert no.liberado_com_uso is False
    assert bancada.diario.eventos("report_thread_nao_encerrou") == []
    assert bancada.diario.eventos("report_thread_morreu_por_excecao") == []
    assert bancada.diario.eventos("report_thread_saiu_e_fechou") == [], (
        "a linha de volta é só de quem ficou com o handle"
    )


def test_a_queda_do_radio_sai_limpa_e_o_close_nao_avisa(bancada: _Bancada) -> None:
    """(b) O kernel tira o nó ANTES: o `read` volta erro com o `_device` de pé."""
    no = _No()
    h, t = _preso_no_read(bancada, no)

    no.soltar()
    t.join(timeout=2.0)
    assert not t.is_alive()
    assert h.connected is False
    h.close()

    assert no.fechado is True
    assert no.liberado_com_uso is False
    assert bancada.diario.eventos("report_thread_nao_encerrou") == []
    assert bancada.diario.eventos("report_thread_morreu_por_excecao") == []
