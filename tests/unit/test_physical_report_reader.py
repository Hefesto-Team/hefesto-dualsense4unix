"""Espelho de motion do físico → vpad (GYRO-01) — sem hardware.

O que estes testes travam:

1. **Parser dos reports crus**: 0x01 (USB, payload em data[1]) e 0x31 (BT,
   payload em data[2], CRC-32 nos 4 últimos bytes com o seed de INPUT 0xA1 —
   `PS_INPUT_CRC32_SEED` do hid-playstation.c). A janela extraída é SEMPRE a
   fatia `raw[base+15 : base+40]` (25 B: gyro+accel+timestamp+touch), verbatim.
2. **CRC validado de verdade** (vetor conhecido + report corrompido descartado):
   os DOIS DualSense da máquina alvo estão em BT — rádio corrompido não pode
   virar motion no vpad.
3. **Throttle**: cap de taxa com dedup por valor e coalescência do último valor
   (a 765 Hz de BT x 4 vpads, sem cap seriam ~3000 writes/s no /dev/uhid).
4. **Bordas do streaming**: abrir o device liga `set_motion_streaming(True)` no
   vpad; perder/parar desliga (fail-safe: o vpad volta ao ritmo do poll com IMU
   neutra). O device é um pipe — nenhum hidraw/uhid real é tocado.
5. **Consistência com o vpad**: os offsets/tamanho da janela daqui são os
   mesmos do `_MOTION_WINDOW` de `uhid_gamepad` (travados um no outro).
"""
from __future__ import annotations

import contextlib
import os
import threading
import time

from hefesto_dualsense4unix.core import physical_report_reader as prr
from hefesto_dualsense4unix.core.ds_output_report import (
    BT_INPUT_CRC_SEED,
    bt_crc32,
)
from hefesto_dualsense4unix.core.physical_report_reader import (
    INPUT_REPORT_BT_SIZE,
    MOTION_WINDOW_LEN,
    PhysicalReportReader,
    extract_motion_window,
)

#: Janela padrão reconhecível (25 bytes 0x01..0x19).
_WINDOW = bytes(range(1, MOTION_WINDOW_LEN + 1))


def _usb_report(window: bytes = _WINDOW) -> bytes:
    """Report 0x01 (64 B) com a janela nos offsets 16..40 do buffer cru."""
    raw = bytearray(64)
    raw[0] = 0x01
    raw[1:7] = bytes([0x80, 0x80, 0x80, 0x80, 0, 0])  # sticks neutros
    raw[16 : 16 + MOTION_WINDOW_LEN] = window
    raw[53] = 0x29  # status como o físico manda
    return bytes(raw)


def _bt_report(window: bytes = _WINDOW, *, corrupt: bool = False) -> bytes:
    """Report 0x31 (78 B) com CRC de INPUT (seed 0xA1) válido — ou corrompido."""
    raw = bytearray(INPUT_REPORT_BT_SIZE)
    raw[0] = 0x31
    raw[1] = 0x01  # header/contador BT (opaco para o parser)
    raw[17 : 17 + MOTION_WINDOW_LEN] = window
    crc = bt_crc32(raw[:-4], seed=BT_INPUT_CRC_SEED)
    raw[-4:] = crc.to_bytes(4, "little")
    if corrupt:
        raw[20] ^= 0xFF  # muda a janela DEPOIS do CRC — assinatura não bate
    return bytes(raw)


class TestExtractMotionWindow:
    def test_usb_extrai_a_janela_verbatim(self) -> None:
        assert extract_motion_window(_usb_report()) == _WINDOW

    def test_usb_e_fatia_exata_do_buffer(self) -> None:
        raw = bytes(range(64))  # cada byte = seu offset
        window = extract_motion_window(bytes([0x01]) + raw[1:])
        assert window is not None
        assert window[0] == 16 and window[-1] == 40  # raw[16:41]

    def test_usb_curto_demais_e_descartado(self) -> None:
        assert extract_motion_window(_usb_report()[:40]) is None

    def test_bt_extrai_a_janela_com_crc_valido(self) -> None:
        assert extract_motion_window(_bt_report()) == _WINDOW

    def test_bt_com_crc_corrompido_e_descartado(self) -> None:
        assert extract_motion_window(_bt_report(corrupt=True)) is None

    def test_bt_com_tamanho_errado_e_descartado(self) -> None:
        assert extract_motion_window(_bt_report()[:64]) is None

    def test_report_de_outro_id_e_descartado(self) -> None:
        assert extract_motion_window(bytes([0x05]) + bytes(63)) is None

    def test_report_vazio_e_descartado(self) -> None:
        assert extract_motion_window(b"") is None

    def test_crc_de_input_bate_com_o_vetor_conhecido(self) -> None:
        # ps_check_crc32(0xA1, "0x31 + 73 zeros") — precomputado e fossilizado:
        # se alguém trocar o seed (0xA2 é o de OUTPUT!) ou a janela do CRC,
        # este vetor denuncia na hora.
        assert bt_crc32(bytes([0x31]) + bytes(73), seed=BT_INPUT_CRC_SEED) == 0x1C9C519D

    def test_janela_bt_e_usb_sao_a_mesma_fatia_do_struct(self) -> None:
        # base 1 (USB) vs base 2 (BT): o MESMO conteúdo de struct tem de sair
        # igual dos dois transportes.
        assert extract_motion_window(_usb_report()) == extract_motion_window(
            _bt_report()
        )


class TestConsistenciaComOVpad:
    def test_janela_do_reader_casa_com_a_do_encoder_do_vpad(self) -> None:
        from hefesto_dualsense4unix.integrations import uhid_gamepad as ug

        assert prr.MOTION_WINDOW_LEN == ug._MOTION_WINDOW_LEN
        assert prr.MOTION_WINDOW_OFFSET == ug._MOTION_WINDOW_START
        assert len(ug._MOTION_NEUTRAL) == prr.MOTION_WINDOW_LEN


class _FakeVpad:
    """Grava o contrato que o reader exerce: forward_motion + streaming."""

    player = 7

    def __init__(self) -> None:
        self.windows: list[bytes] = []
        self.streaming: list[bool] = []

    def forward_motion(self, window: bytes) -> None:
        self.windows.append(bytes(window))

    def set_motion_streaming(self, on: bool) -> None:
        self.streaming.append(bool(on))


class _FakeClock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


def _reader(
    vpad: _FakeVpad, clock: _FakeClock, *, max_hz: float = 250.0
) -> PhysicalReportReader:
    return PhysicalReportReader(
        path_provider=lambda: None, vpad=vpad, max_hz=max_hz, time_fn=clock
    )


class TestThrottle:
    def test_primeira_janela_sai_na_hora(self) -> None:
        vpad, clock = _FakeVpad(), _FakeClock()
        reader = _reader(vpad, clock)
        reader._maybe_emit(_WINDOW)
        assert vpad.windows == [_WINDOW]

    def test_janela_dentro_do_intervalo_e_retida_e_coalescida(self) -> None:
        vpad, clock = _FakeVpad(), _FakeClock()
        reader = _reader(vpad, clock)
        w2 = bytes([2]) * MOTION_WINDOW_LEN
        w3 = bytes([3]) * MOTION_WINDOW_LEN
        reader._maybe_emit(_WINDOW)
        clock.now += 0.001  # < 1/250 s
        reader._maybe_emit(w2)
        clock.now += 0.001
        reader._maybe_emit(w3)  # sobrescreve a retida (coalescência)
        assert vpad.windows == [_WINDOW]
        assert reader._pending == w3

    def test_janela_apos_o_intervalo_sai_e_derruba_a_retida(self) -> None:
        vpad, clock = _FakeVpad(), _FakeClock()
        reader = _reader(vpad, clock)
        w2 = bytes([2]) * MOTION_WINDOW_LEN
        w3 = bytes([3]) * MOTION_WINDOW_LEN
        reader._maybe_emit(_WINDOW)
        clock.now += 0.001
        reader._maybe_emit(w2)  # retida
        clock.now += 0.010  # venceu o intervalo de 4 ms
        reader._maybe_emit(w3)
        assert vpad.windows == [_WINDOW, w3]
        assert reader._pending is None  # w2 foi superada — nunca sai atrasada

    def test_valor_repetido_nao_reemite(self) -> None:
        vpad, clock = _FakeVpad(), _FakeClock()
        reader = _reader(vpad, clock)
        reader._maybe_emit(_WINDOW)
        clock.now += 1.0
        reader._maybe_emit(_WINDOW)
        assert vpad.windows == [_WINDOW]

    def test_flush_entrega_a_retida_quando_o_fluxo_para(self) -> None:
        vpad, clock = _FakeVpad(), _FakeClock()
        reader = _reader(vpad, clock)
        w2 = bytes([2]) * MOTION_WINDOW_LEN
        reader._maybe_emit(_WINDOW)
        clock.now += 0.001
        reader._maybe_emit(w2)  # retida pelo cap
        reader._flush_pending()  # cedo demais: segue retida
        assert vpad.windows == [_WINDOW]
        clock.now += 0.010
        reader._flush_pending()  # agora sai — a última janela nunca se perde
        assert vpad.windows == [_WINDOW, w2]

    def test_cap_de_taxa_segura_uma_rajada_de_bt(self) -> None:
        # ~765 Hz de BT simulados por 0,1 s: o cap de 250 Hz deixa passar no
        # máximo ~26 janelas (0,1 s ÷ 4 ms + a primeira).
        vpad, clock = _FakeVpad(), _FakeClock()
        reader = _reader(vpad, clock)
        for i in range(77):
            reader._maybe_emit(bytes([i % 256]) * MOTION_WINDOW_LEN)
            clock.now += 1.0 / 765.0
        assert len(vpad.windows) <= 27

    def test_vpad_que_explode_nao_derruba_o_reader(self) -> None:
        class _Bomba(_FakeVpad):
            def forward_motion(self, window: bytes) -> None:
                raise RuntimeError("boom")

        vpad, clock = _Bomba(), _FakeClock()
        reader = _reader(vpad, clock)
        reader._maybe_emit(_WINDOW)  # não propaga

    def test_max_hz_zero_desliga_o_cap(self) -> None:
        vpad, clock = _FakeVpad(), _FakeClock()
        reader = _reader(vpad, clock, max_hz=0)
        for i in range(5):
            reader._maybe_emit(bytes([i + 1]) * MOTION_WINDOW_LEN)
        assert len(vpad.windows) == 5


class TestLoopComPipe:
    """O loop de leitura de ponta a ponta, com um pipe no lugar do hidraw."""

    def _esperar(self, cond, timeout_s: float = 2.0) -> bool:
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            if cond():
                return True
            time.sleep(0.005)
        return False

    def test_streaming_liga_no_open_e_janela_chega_ao_vpad(
        self, monkeypatch
    ) -> None:
        lido, escrita = os.pipe()
        aberto = {"count": 0}

        def _fake_open(path: str, flags: int) -> int:
            aberto["count"] += 1
            return os.dup(lido)

        monkeypatch.setattr(prr.os, "open", _fake_open)
        vpad = _FakeVpad()
        reader = PhysicalReportReader(
            path_provider=lambda: "/dev/hidraw-fake", vpad=vpad
        )
        try:
            assert reader.start() is True
            os.write(escrita, _usb_report())
            assert self._esperar(lambda: vpad.windows)
            assert vpad.windows[0] == _WINDOW
            assert vpad.streaming[:1] == [True]
            assert reader.reports_seen >= 1
            assert reader.windows_emitted >= 1
        finally:
            reader.stop()
            os.close(escrita)
            os.close(lido)
        # stop() desliga o streaming (fail-safe) e a thread morre.
        assert vpad.streaming[-1] is False
        assert reader.is_running is False

    def test_report_bt_corrompido_conta_drop_e_nao_chega_ao_vpad(
        self, monkeypatch
    ) -> None:
        lido, escrita = os.pipe()
        monkeypatch.setattr(prr.os, "open", lambda *_a: os.dup(lido))
        vpad = _FakeVpad()
        reader = PhysicalReportReader(
            path_provider=lambda: "/dev/hidraw-fake", vpad=vpad
        )
        try:
            reader.start()
            os.write(escrita, _bt_report(corrupt=True))
            assert self._esperar(lambda: reader.bt_drops >= 1)
            assert vpad.windows == []
            # O são passa depois do corrompido — o reader não desistiu.
            os.write(escrita, _bt_report())
            assert self._esperar(lambda: vpad.windows)
            assert vpad.windows[0] == _WINDOW
        finally:
            reader.stop()
            os.close(escrita)
            os.close(lido)

    def test_sem_path_nao_abre_nada_e_para_limpo(self) -> None:
        vpad = _FakeVpad()
        reader = PhysicalReportReader(path_provider=lambda: None, vpad=vpad)
        reader.start()
        time.sleep(0.05)
        reader.stop()
        assert vpad.windows == []
        assert reader.is_running is False
        # Nunca abriu device: o único set_motion_streaming é o False do stop.
        assert True not in vpad.streaming

    def test_stop_acorda_o_select_na_hora_sem_esperar_o_timeout(
        self, monkeypatch
    ) -> None:
        """GYRO-FD-01: com select de 5 s, o stop() tem de voltar em bem menos
        de 2 s (o wake do self-pipe acorda a thread; sem ele, o join de 2 s
        estouraria esperando o select)."""
        monkeypatch.setattr(prr, "_SELECT_TIMEOUT_S", 5.0)
        lido, escrita = os.pipe()
        monkeypatch.setattr(prr.os, "open", lambda *_a: os.dup(lido))
        vpad = _FakeVpad()
        reader = PhysicalReportReader(
            path_provider=lambda: "/dev/hidraw-fake", vpad=vpad
        )
        try:
            reader.start()
            assert self._esperar(lambda: True in vpad.streaming)
            inicio = time.monotonic()
            reader.stop()
            assert (time.monotonic() - inicio) < 1.5
            assert reader.is_running is False
        finally:
            reader.stop()
            os.close(escrita)
            os.close(lido)

    def test_request_reopen_acorda_o_select_na_hora(self, monkeypatch) -> None:
        """GYRO-FD-01: reopen não espera o timeout do select — o wake pipe
        derruba a espera e o 2º open acontece em instantes."""
        monkeypatch.setattr(prr, "_SELECT_TIMEOUT_S", 5.0)
        lido, escrita = os.pipe()
        abertos: list[int] = []

        def _fake_open(path: str, flags: int) -> int:
            fd = os.dup(lido)
            abertos.append(fd)
            return fd

        monkeypatch.setattr(prr.os, "open", _fake_open)
        vpad = _FakeVpad()
        reader = PhysicalReportReader(
            path_provider=lambda: "/dev/hidraw-fake", vpad=vpad
        )
        try:
            reader.start()
            assert self._esperar(lambda: len(abertos) >= 1)
            inicio = time.monotonic()
            reader.request_reopen("primary_changed")
            assert self._esperar(lambda: len(abertos) >= 2)
            assert (time.monotonic() - inicio) < 2.0
        finally:
            reader.stop()
            os.close(escrita)
            os.close(lido)

    def test_request_reopen_derruba_o_fd_e_reabre_no_provider(
        self, monkeypatch
    ) -> None:
        lido1, escrita1 = os.pipe()
        lido2, escrita2 = os.pipe()
        fontes = [lido1, lido2]
        abertos: list[int] = []

        def _fake_open(path: str, flags: int) -> int:
            fd = os.dup(fontes[min(len(abertos), 1)])
            abertos.append(fd)
            return fd

        monkeypatch.setattr(prr.os, "open", _fake_open)
        vpad = _FakeVpad()
        reader = PhysicalReportReader(
            path_provider=lambda: "/dev/hidraw-fake", vpad=vpad
        )
        try:
            reader.start()
            os.write(escrita1, _usb_report())
            assert self._esperar(lambda: vpad.windows)
            reader.request_reopen("primary_changed")  # retarget do backend
            assert self._esperar(lambda: len(abertos) >= 2)
            w2 = bytes([9]) * MOTION_WINDOW_LEN
            os.write(escrita2, _usb_report(w2))
            assert self._esperar(lambda: w2 in vpad.windows)
            # A borda perder→reabrir desligou e religou o streaming.
            assert vpad.streaming.count(False) >= 1
            assert vpad.streaming.count(True) >= 2
        finally:
            reader.stop()
            for fd in (escrita1, escrita2, lido1, lido2):
                os.close(fd)


class TestDonoUnicoDoFd:
    """GYRO-FD-01: a thread do reader é a ÚNICA dona do fd do hidraw.

    O bug original: `request_reopen`/`stop` fechavam o fd de OUTRA thread
    enquanto o loop estava em select/read no NÚMERO local — um open
    concorrente do daemon (eventX do `_recompute_primary`, /dev/uhid de um
    vpad novo) reciclava o número e o reader passava a drenar um fd ALHEIO
    (input do jogo congelado + gyro-lixo no vpad).
    """

    def _esperar(self, cond, timeout_s: float = 2.0) -> bool:
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            if cond():
                return True
            time.sleep(0.005)
        return False

    def test_request_reopen_e_stop_nao_fecham_o_fd_do_hidraw_de_fora(
        self,
    ) -> None:
        """Quem está fora só SINALIZA — o fd plantado sobrevive aos dois."""
        vpad = _FakeVpad()
        reader = PhysicalReportReader(path_provider=lambda: None, vpad=vpad)
        lido, escrita = os.pipe()
        try:
            with reader._fd_lock:
                reader._fd = lido  # fd "ativo" plantado (sem thread viva)
            reader.request_reopen("primary_changed")
            os.fstat(lido)  # não levanta: o número NÃO foi liberado
            reader.stop()
            os.fstat(lido)  # stop() também não toca o fd do hidraw
        finally:
            for fd in (lido, escrita):
                with contextlib.suppress(OSError):
                    os.close(fd)

    def test_reopen_concorrente_nao_recicla_o_numero_do_fd(
        self, monkeypatch
    ) -> None:
        """O cenário do achado, determinístico: a thread está no select do fd
        antigo, outra thread pede reopen e um open concorrente acontece em
        seguida — o número do fd do reader NUNCA pode ser entregue ao open
        concorrente (quem fecha é a própria thread, DEPOIS de sair do loop),
        e os bytes do fd alheio ficam intactos (o reader não os drena)."""
        lido1, escrita1 = os.pipe()
        lido2, escrita2 = os.pipe()
        lido3, escrita3 = os.pipe()  # o "eventX" alheio do daemon
        fontes = [lido1, lido2]
        abertos: list[int] = []

        def _fake_open(path: str, flags: int) -> int:
            fd = os.dup(fontes[min(len(abertos), 1)])
            abertos.append(fd)
            return fd

        pode_fechar = threading.Event()
        fechados: list[tuple[str, int]] = []
        real_close = os.close

        def _close_gated(fd: int) -> None:
            # Segura SÓ o close do fd do hidraw (determinismo do teste): a
            # janela "reopen pedido, fd ainda não fechado" fica aberta até o
            # teste liberar — é nela que o bug original reciclava o número.
            if abertos and fd == abertos[0] and not pode_fechar.is_set():
                pode_fechar.wait(2.0)
            fechados.append((threading.current_thread().name, fd))
            real_close(fd)

        monkeypatch.setattr(prr.os, "open", _fake_open)
        monkeypatch.setattr(prr.os, "close", _close_gated)
        vpad = _FakeVpad()
        reader = PhysicalReportReader(
            path_provider=lambda: "/dev/hidraw-fake", vpad=vpad
        )
        try:
            reader.start()
            os.write(escrita1, _usb_report())
            assert self._esperar(lambda: vpad.windows)
            fd_reader = abertos[0]

            reader.request_reopen("primary_changed")
            # O open concorrente do daemon, logo após o pedido: com o close
            # externo do bug, o menor número livre seria o RECICLADO fd do
            # reader; com a posse única, o fd segue aberto e fora de alcance.
            alheio = os.dup(lido3)
            try:
                assert alheio != fd_reader
                os.fstat(fd_reader)  # o número do reader segue vivo/nosso
                os.write(escrita3, b"segredo-alheio")

                pode_fechar.set()  # libera o close do PRÓPRIO reader
                assert self._esperar(lambda: len(abertos) >= 2)
                w2 = bytes([9]) * MOTION_WINDOW_LEN
                os.write(escrita2, _usb_report(w2))
                assert self._esperar(lambda: w2 in vpad.windows)

                # Quem fechou o fd antigo foi a THREAD DO READER, nunca a de
                # fora (a chamadora do request_reopen é a MainThread).
                donos = [nome for (nome, fd) in fechados if fd == fd_reader]
                assert donos == ["hefesto-motion-p7"]
                # E os bytes do fd alheio continuam lá, intactos.
                assert os.read(alheio, 64) == b"segredo-alheio"
            finally:
                real_close(alheio)
        finally:
            pode_fechar.set()
            reader.stop()
            for fd in (escrita1, escrita2, escrita3, lido1, lido2, lido3):
                with contextlib.suppress(OSError):
                    real_close(fd)
