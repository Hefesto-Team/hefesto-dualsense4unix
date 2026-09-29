"""O botão do microfone chega na hora — O-BOTAO-DO-MIC-CHEGA-NA-HORA-01.

O DEFEITO, medido na bancada de 29/09/2026 (~01h38), com os quatro DualSense
no rádio: do dedo à borda (`mic_da_mesa_borda`), 2,108 s, 2,110 s e 2,086 s; e
a luz do plástico repintando o estado de antes do aperto por ~2,3 s.

A CAUSA: a volta de cada handle lia UM report e dormia o throttle. A fila do
hidraw é por fd, com 63 posições úteis, e o kernel descarta o report NOVO
quando ela está cheia. O aparelho entrega centenas por segundo e a volta lia
~30: cada report lido tinha 63 voltas de idade (63 x 33 ms ≈ 2,1 s com os
quatro; 63 x 8,7 ms ≈ 0,55 s com um no cabo, os 547 ms de 04/09).

A CURA: a volta esvazia a fila, com a leitura sem espera depois do `init()`;
conta o botão e o `status[1]` em cada report, na ordem; entrega à pydualsense
só o report de estado mais novo; e a luz segura a borda até o ato.

O INSTRUMENTO. O `hidapi.Device` é o wrapper INSTALADO, o mesmo que o
`_pydualsense__find_device` abre; só o lado C (`hidapi.hidapi`) é de mentira.
Assim o dublê não pode ser mais frouxo que o produto: o `read` segue as regras
do wrapper (`timeout_ms=0` cai no `hid_read`, que obedece ao modo do handle), e
o modo nasce BLOQUEANTE, como o de `hidapi.Device(path=...)`. O lado C tem a
fila do kernel (63 vagas, descarta o NOVO) alimentada por um relógio virtual,
que anda junto com o `time.sleep` e o `time.monotonic` do laço e com o
`_relogio_da_borda`. Uma leitura sem prazo com a fila vazia bloquearia para
sempre, e aqui ela LEVANTA (`_LeriaParaSempre`, que o laço não engole).
"""

from __future__ import annotations

import asyncio
import contextlib
import math
import sys
import types
from collections import deque
from collections.abc import Callable, Iterator
from typing import Any

import hidapi as hidapi_do_wrapper
import pytest
from pydualsense.enums import ConnectionType
from pydualsense.pydualsense import DSAudio, DSBattery, DSLight, DSState, DSTrigger

from hefesto_dualsense4unix.core import backend_pydualsense as bp
from hefesto_dualsense4unix.core import physical_report_reader as prr
from hefesto_dualsense4unix.core.events import EventBus, EventTopic
from hefesto_dualsense4unix.daemon.subsystems import luz_do_mic as luz
from hefesto_dualsense4unix.integrations.dualsense_bt_audio import STATUS_MIC_MUDO

#: `uapi/linux/hidraw.h:56`: 64 posições por fd, uma sempre livre.
_VAGAS_DA_FILA = 63

#: As taxas medidas: o …0000ab entregava ~560-720 reports/s pelo rádio na
#: bancada de 29/09, e o cabo entrega 250/s.
_TAXA = {"radio": 688.0, "cabo": 250.0}

#: O controle das réguas da luz, na faixa forjada da suíte.
UM = "aabbcc0000c1"


def _throttle(n: int) -> float:
    """O throttle de uma mesa de `n`, pela conta do `connect` do backend."""
    return float(min(bp.REPORT_THREAD_THROTTLE_SEC * n, bp.REPORT_THREAD_THROTTLE_MAX_SEC))


# ---------------------------------------------------------------------------
# O lado C do hidapi, com a fila do kernel
# ---------------------------------------------------------------------------


class _LeriaParaSempre(BaseException):
    """Um `hid_read` sem prazo com a fila vazia: no aparelho, ele não voltaria.

    `BaseException` e não `Exception` de propósito: a rede do laço
    (`except Exception`) engoliria o aviso e o teste leria só um controle
    desconectado.
    """


class _Relogio:
    def __init__(self) -> None:
        self.t = 1000.0

    def agora(self) -> float:
        return self.t


def _report(
    transporte: str,
    *,
    botao: bool,
    mudo: bool,
    bateria: int = 5,
    audio: bool = False,
) -> bytes:
    """Um report do aparelho: `0x01` do cabo, ou `0x31` do rádio com CRC.

    `audio=True` é o quadro de áudio do rádio (o bit `INPUT_FLAG_AUDIO` ligado,
    CRC válido): o payload é Opus, e aqui ele é lixo que cairia EM CIMA do
    botão, do `status[1]` e da bateria se passasse pela porta.
    """
    if transporte == "cabo":
        corpo = bytearray(64)
        corpo[0] = prr.INPUT_REPORT_USB
        base = 1
    else:
        corpo = bytearray(prr.INPUT_REPORT_BT_SIZE)
        corpo[0] = prr.INPUT_REPORT_BT
        base = 2
    if audio:
        corpo[1] |= prr.INPUT_FLAG_AUDIO
        for i in range(3, len(corpo) - 4):
            corpo[i] = 0xFF
    else:
        corpo[base + prr.JACK_STATUS_OFFSET] = STATUS_MIC_MUDO if mudo else 0x00
        corpo[base + prr.BATTERY_STATUS_OFFSET] = bateria & 0x0F
        if botao:
            corpo[base + prr.BUTTONS2_OFFSET] |= prr.MIC_BUTTON_BIT
    if transporte == "radio":
        crc = prr.bt_crc32(bytes(corpo[:-4]), seed=prr.BT_INPUT_CRC_SEED)
        corpo[-4:] = crc.to_bytes(4, "little")
    return bytes(corpo)


class _Aparelho:
    """O `hid_device` de UM handle: a fila do fd e o modo do `hid_read`.

    O aparelho entrega um report a cada `1/taxa` s do relógio virtual; o que
    chega com a fila cheia se perde (a política do `hidraw_report_event`). O
    que cada report diz vem das funções do ensaio, pelo instante dele.
    """

    def __init__(
        self,
        relogio: _Relogio,
        *,
        transporte: str,
        taxa: float,
        botao: Callable[[float], bool] = lambda _t: False,
        mudo: Callable[[float], bool] = lambda _t: False,
        bateria: Callable[[int], int] = lambda _i: 5,
        audio: Callable[[int], bool] = lambda _i: False,
    ) -> None:
        self.relogio = relogio
        self.transporte = transporte
        self.taxa = taxa
        self.inicio = relogio.t
        self.gerados = 0
        self.fila: deque[tuple[int, float, bytes]] = deque()
        self.bloqueante = True  # `hidapi.Device(path=...)` nasce com `blocking=True`
        self.fechado = False
        self.descartados = 0
        self.lidos = 0
        self.escritos: list[bytes] = []
        #: o tamanho da fila a cada leitura, antes de tirar o report
        self.filas_vistas: list[int] = []
        #: o último report de ESTADO que saiu da fila: (índice, bateria)
        self.ultimo_estado_lido: tuple[int, int] | None = None
        self._botao = botao
        self._mudo = mudo
        self._bateria = bateria
        self._audio = audio

    def instante(self, i: int) -> float:
        return self.inicio + (i + 1) / self.taxa

    def alimentar(self) -> None:
        if self.taxa <= 0:
            return
        while self.instante(self.gerados) <= self.relogio.t + 1e-12:
            i = self.gerados
            t = self.instante(i)
            quadro = _report(
                self.transporte,
                botao=self._botao(t),
                mudo=self._mudo(t),
                bateria=self._bateria(i),
                audio=self._audio(i),
            )
            if len(self.fila) < _VAGAS_DA_FILA:
                self.fila.append((i, t, quadro))
            else:
                self.descartados += 1
            self.gerados += 1


def _exigir(dev: Any) -> _Aparelho:
    if dev is None:
        # A mensagem do cffi quando o `_device` do wrapper já virou `None`.
        raise TypeError(
            "initializer for ctype 'hid_device *' must be a cdata pointer, not NoneType"
        )
    assert isinstance(dev, _Aparelho)
    return dev


class _CDoHidapi:
    """O `hidapi.hidapi` de mentira: `hid.c` do Linux, só no que o laço usa.

    `hid_read` passa ao `hid_read_timeout` o prazo -1 no modo bloqueante e 0
    no outro (`hid.c:1274`); `hid_set_nonblocking` só troca o modo
    (`hid.c:1277-1283`).
    """

    def __init__(self) -> None:
        self.ffi = hidapi_do_wrapper.ffi

    def hid_read(self, dev: Any, bufp: Any, length: int) -> int:
        aparelho = _exigir(dev)
        return self.hid_read_timeout(dev, bufp, length, -1 if aparelho.bloqueante else 0)

    def hid_read_timeout(self, dev: Any, bufp: Any, length: int, ms: int) -> int:
        aparelho = _exigir(dev)
        aparelho.alimentar()
        if not aparelho.fila and ms > 0:
            aparelho.relogio.t += ms / 1000.0
            aparelho.alimentar()
        if not aparelho.fila:
            if ms < 0:
                raise _LeriaParaSempre("hid_read sem prazo com a fila vazia")
            return 0
        aparelho.filas_vistas.append(len(aparelho.fila))
        i, _t, quadro = aparelho.fila.popleft()
        aparelho.lidos += 1
        if prr.eh_report_de_estado(quadro):
            base = 1 if quadro[0] == prr.INPUT_REPORT_USB else 2
            aparelho.ultimo_estado_lido = (i, quadro[base + prr.BATTERY_STATUS_OFFSET] & 0x0F)
        n = min(length, len(quadro))
        self.ffi.memmove(bufp, quadro, n)
        return n

    def hid_set_nonblocking(self, dev: Any, nonblock: int) -> int:
        _exigir(dev).bloqueante = not nonblock
        return 0

    def hid_write(self, dev: Any, bufp: Any, length: int) -> int:
        _exigir(dev).escritos.append(bytes(self.ffi.buffer(bufp, length)))
        return length

    def hid_close(self, dev: Any) -> None:
        _exigir(dev).fechado = True

    def hid_error(self, dev: Any) -> Any:
        _exigir(dev)
        return self.ffi.NULL


class _Bancada:
    """O relógio virtual, o lado C de mentira e os wrappers de verdade."""

    def __init__(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self.relogio = _Relogio()
        self.c = _CDoHidapi()
        self.devices: list[Any] = []
        self._depois_de_dormir: list[Callable[[], None]] = []
        monkeypatch.setattr(hidapi_do_wrapper, "hidapi", self.c)
        monkeypatch.setattr(bp.time, "monotonic", self.relogio.agora)
        monkeypatch.setattr(bp.time, "sleep", self._dormir)
        monkeypatch.setattr(bp, "_relogio_da_borda", self.relogio.agora)

    def _dormir(self, segundos: float) -> None:
        self.relogio.t += segundos
        for gancho in list(self._depois_de_dormir):
            gancho()

    def depois_de_cada_volta(self, gancho: Callable[[], None]) -> None:
        self._depois_de_dormir.append(gancho)

    def device(self, aparelho: _Aparelho) -> Any:
        """Um `hidapi.Device` DE VERDADE sobre o `hid_device` de mentira."""
        dev = hidapi_do_wrapper.Device.__new__(hidapi_do_wrapper.Device)
        dev._device = aparelho
        self.devices.append(dev)
        return dev

    def handle(self, aparelho: _Aparelho, *, n: int) -> bp._PinnedPyDualSense:
        """O handle de produção, com o que o `init()` do upstream monta."""
        h = bp._PinnedPyDualSense(b"/dev/hidraw-de-mentira", is_edge=False)
        h.device = self.device(aparelho)
        h.is_edge = False
        h.light = DSLight()
        h.audio = DSAudio()
        h.triggerL = DSTrigger()
        h.triggerR = DSTrigger()
        h.state = DSState()
        h.battery = DSBattery()
        radio = aparelho.transporte == "radio"
        h.conType = ConnectionType.BT if radio else ConnectionType.USB
        h.input_report_length = 78 if radio else 64
        h.output_report_length = 78 if radio else 64
        h.ds_thread = True
        h.connected = True
        h._throttle_sec = _throttle(n)
        return h

    def rodar(self, h: bp._PinnedPyDualSense, *, segundos: float) -> None:
        """Gira o `sendReport` de produção por `segundos` do relógio virtual."""
        fim = self.relogio.t + segundos

        def _parar() -> None:
            if self.relogio.t >= fim:
                h.ds_thread = False

        self.depois_de_cada_volta(_parar)
        try:
            h.sendReport()
        finally:
            self._depois_de_dormir.remove(_parar)

    def soltar(self) -> None:
        # O `__del__` do wrapper chama o `hid_close` do lado C DE VERDADE se o
        # `_device` ainda estiver de pé quando o monkeypatch já tiver saído.
        for dev in self.devices:
            dev._device = None


@pytest.fixture
def bancada(monkeypatch: pytest.MonkeyPatch) -> Iterator[_Bancada]:
    b = _Bancada(monkeypatch)
    try:
        yield b
    finally:
        b.soltar()


def _aperto(inicio: float, dura: float) -> Callable[[float], bool]:
    return lambda t: inicio <= t < inicio + dura


def _primeiro_com_o_dedo(aparelho: _Aparelho, inicio: float) -> float:
    """O instante do primeiro report com o dedo embaixo (o `t0` do aperto)."""
    return aparelho.instante(math.ceil((inicio - aparelho.inicio) * aparelho.taxa - 1 - 1e-9))


# ---------------------------------------------------------------------------
# 1. Do dedo à borda: uma volta, e não 63
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("n", [1, 2, 3, 4])
@pytest.mark.parametrize("transporte", ["radio", "cabo"])
def test_do_dedo_a_borda_leva_no_maximo_uma_volta(
    bancada: _Bancada, transporte: str, n: int
) -> None:
    """Um aperto em `t0` dá `_mic_mudo_em - t0` ≤ uma volta, em todo `n`.

    Três segundos de aquecimento antes do aperto: com a leitura de um report
    por volta, a fila enche nesse tempo em todos os casos.

    MORDIDA: `LEITURAS_POR_VOLTA = 1` (a volta de uma leitura) dá 63 voltas —
    0,55 s, 1,05 s, 1,55 s e 2,08 s no modelo — e reprova; é o
    `test_a_fila_de_mentira_reproduz_o_defeito` abaixo.
    """
    inicio = bancada.relogio.t + 3.0
    aparelho = _Aparelho(
        bancada.relogio,
        transporte=transporte,
        taxa=_TAXA[transporte],
        botao=_aperto(inicio, 0.1),
    )
    h = bancada.handle(aparelho, n=n)
    bancada.rodar(h, segundos=4.0)

    t0 = _primeiro_com_o_dedo(aparelho, inicio)
    assert h._mic_mudo_seq == 1, "o aperto não virou borda"
    assert h._mic_mudo_em is not None
    atraso = h._mic_mudo_em - t0
    assert 0.0 <= atraso <= _throttle(n) + 1e-9, (
        f"{transporte}, {n} controle(s): do dedo à borda levou {atraso:.3f} s "
        f"com a volta de {_throttle(n):.3f} s"
    )
    assert aparelho.bloqueante is False, "a volta leu no modo bloqueante"


@pytest.mark.parametrize(("transporte", "n"), [("cabo", 1), ("radio", 4)])
def test_a_fila_de_mentira_reproduz_o_defeito(
    bancada: _Bancada, monkeypatch: pytest.MonkeyPatch, transporte: str, n: int
) -> None:
    """O INSTRUMENTO MEDE: com UMA leitura por volta, a borda leva ~63 voltas.

    É o controle positivo da régua 1. Uma fila de mentira que não enchesse, ou
    que descartasse o report VELHO, daria verde sobre a volta de hoje. Os dois
    números são os da casa: 0,5 s com um no cabo (547 ms em 04/09) e 2,0 s com
    os quatro no rádio (2,1 s em 29/09).
    """
    monkeypatch.setattr(bp, "LEITURAS_POR_VOLTA", 1)
    inicio = bancada.relogio.t + 3.0
    aparelho = _Aparelho(
        bancada.relogio,
        transporte=transporte,
        taxa=_TAXA[transporte],
        botao=_aperto(inicio, 0.1),
    )
    h = bancada.handle(aparelho, n=n)
    bancada.rodar(h, segundos=6.0)

    t0 = _primeiro_com_o_dedo(aparelho, inicio)
    assert h._mic_mudo_em is not None
    voltas = (h._mic_mudo_em - t0) / _throttle(n)
    assert voltas >= 60, f"a fila de mentira não enche: a borda veio em {voltas:.1f} voltas"
    assert aparelho.descartados > 0, "a fila de mentira nunca descartou nada"


# ---------------------------------------------------------------------------
# 2. O toque curto
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("transporte", ["radio", "cabo"])
def test_o_toque_curto_entre_duas_voltas_da_uma_borda(
    bancada: _Bancada, transporte: str
) -> None:
    """Três reports com o dedo embaixo, dentro de uma volta: UMA borda.

    O botão e o `status[1]` se contam em cada report, na ordem em que chegaram;
    a pydualsense só vê o mais novo, e nele o dedo já subiu.

    MORDIDA: a leitura única (um report por volta, com a fila cheia) perde o
    toque inteiro para o descarte do kernel, e dá zero.
    """
    taxa = _TAXA[transporte]
    aparelho = _Aparelho(bancada.relogio, transporte=transporte, taxa=taxa)
    inicio = aparelho.instante(int(2.0 * taxa)) - 1e-6
    aparelho._botao = _aperto(inicio, 2.5 / taxa)
    h = bancada.handle(aparelho, n=4)
    bancada.rodar(h, segundos=3.0)

    assert h._mic_mudo_seq == 1
    assert h._mic_botao is False, "o report mais novo é o do dedo que subiu"


# ---------------------------------------------------------------------------
# 3. A saída não espera a entrada
# ---------------------------------------------------------------------------


def test_com_a_fila_vazia_a_saida_escreve_em_cada_volta(bancada: _Bancada) -> None:
    """Dez voltas com o aparelho calado: dez escritas, uma por mudança.

    O `hid_read` sem prazo com a fila vazia não volta; o dublê LEVANTA. A volta
    que esvazia a fila termina TODA volta numa leitura vazia, então ela só
    funciona com a leitura sem espera (`_hid_set_nonblocking` depois do
    `init()`).

    MORDIDA: tirar o `_hid_set_nonblocking` do `sendReport` (a drenagem com a
    leitura de hoje) levanta `_LeriaParaSempre` na primeira volta.
    """
    aparelho = _Aparelho(bancada.relogio, transporte="radio", taxa=0.0)
    h = bancada.handle(aparelho, n=4)
    h._suppress_leds = True
    voltas = {"n": 0}

    def _mudar_a_saida() -> None:
        voltas["n"] += 1
        h.leftMotor = voltas["n"] & 0xFF
        if voltas["n"] >= 10:
            h.ds_thread = False

    bancada.depois_de_cada_volta(_mudar_a_saida)
    h.sendReport()

    assert voltas["n"] == 10
    assert len(aparelho.escritos) == 10, "a saída esperou a entrada"
    assert h.connected is True
    assert aparelho.lidos == 0


# ---------------------------------------------------------------------------
# 4. Um parse por volta, com o report mais novo
# ---------------------------------------------------------------------------


def test_um_parse_por_volta_com_o_report_de_estado_mais_novo(
    bancada: _Bancada, monkeypatch: pytest.MonkeyPatch
) -> None:
    """O `readInput` roda uma vez por volta, e com o report de estado mais NOVO.

    Um quadro de áudio a cada três conta em `_reports_recusados` e não mexe em
    borda nem em status: o lixo dele tem o botão e o mudo ligados.

    MORDIDAS: `readInput` por report reprova pela contagem; entregar o report
    mais VELHO reprova pela bateria (cada report tem a sua).
    """
    aparelho = _Aparelho(
        bancada.relogio,
        transporte="radio",
        taxa=_TAXA["radio"],
        bateria=lambda i: i % 11,
        audio=lambda i: i % 3 == 1,
    )
    h = bancada.handle(aparelho, n=4)
    parses: list[int] = []
    real = bp._PinnedPyDualSense.readInput

    def _conta(in_report: Any) -> None:
        parses.append(len(bytes(in_report)))
        real(h, in_report)

    monkeypatch.setattr(h, "readInput", _conta)
    #: as voltas que tiraram da fila ao menos um report de ESTADO
    com_estado: list[tuple[int, int] | None] = [None]

    def _conta_volta() -> None:
        if aparelho.ultimo_estado_lido != com_estado[-1]:
            com_estado.append(aparelho.ultimo_estado_lido)

    bancada.depois_de_cada_volta(_conta_volta)
    bancada.rodar(h, segundos=2.0)

    voltas = len(com_estado) - 1
    assert voltas > 50
    assert len(parses) == voltas, (
        f"{len(parses)} parses em {voltas} voltas com estado: o parse caro é um por volta"
    )
    audio_lido = sum(1 for i in range(aparelho.gerados) if i % 3 == 1) - sum(
        1 for i, _t, _q in aparelho.fila if i % 3 == 1
    )
    assert h._reports_recusados == audio_lido
    assert h._mic_mudo_seq == 0, "o quadro de áudio virou aperto"
    assert h._audio_status == 0x00, "o quadro de áudio virou status"
    assert aparelho.ultimo_estado_lido is not None
    _indice, nibble = aparelho.ultimo_estado_lido
    assert h.battery.Level == min(nibble * 10 + 5, 100), (
        "a pydualsense recebeu um report velho da volta, e não o mais novo"
    )


# ---------------------------------------------------------------------------
# 6. No tempo: os quatro, trinta segundos, um aperto a cada 1,5 s
# ---------------------------------------------------------------------------


_MESA = (("radio", 688.0), ("radio", 560.0), ("radio", 390.0), ("cabo", 250.0))


@pytest.mark.parametrize("jogador", range(4))
def test_no_tempo_os_quatro_apertos_chegam_numa_volta(
    bancada: _Bancada, jogador: int
) -> None:
    """Trinta segundos de mesa de quatro, um aperto a cada 1,5 s alternando.

    Cada handle tem o seu fd, a sua fila e a sua volta, e nada da volta é
    comum entre eles; por isso cada jogador roda os seus 30 s no relógio
    virtual, com o throttle da mesa de quatro. Toda borda chega em ≤ uma
    volta, nenhuma borda aparece sem aperto, e a fila nunca passa de uma volta
    de reports.
    """
    transporte, taxa = _MESA[jogador]
    inicio = bancada.relogio.t
    apertos = [inicio + 1.0 + 1.5 * k for k in range(20) if k % 4 == jogador]
    aparelho = _Aparelho(
        bancada.relogio,
        transporte=transporte,
        taxa=taxa,
        botao=lambda t: any(a <= t < a + 0.08 for a in apertos),
    )
    h = bancada.handle(aparelho, n=4)
    bordas: list[float] = []
    seq = {"visto": 0}

    def _anotar() -> None:
        if h._mic_mudo_seq != seq["visto"]:
            assert h._mic_mudo_seq == seq["visto"] + 1, "duas bordas numa volta"
            seq["visto"] = h._mic_mudo_seq
            assert h._mic_mudo_em is not None
            bordas.append(h._mic_mudo_em)

    bancada.depois_de_cada_volta(_anotar)
    bancada.rodar(h, segundos=30.0)

    assert len(bordas) == len(apertos), f"{len(bordas)} bordas para {len(apertos)} apertos"
    for aperto, borda in zip(apertos, bordas, strict=True):
        atraso = borda - _primeiro_com_o_dedo(aparelho, aperto)
        assert 0.0 <= atraso <= _throttle(4) + 1e-9, f"o aperto de {aperto - inicio:.1f} s"
    teto = math.ceil(taxa * _throttle(4)) + 1
    assert max(aparelho.filas_vistas) <= teto, (
        f"a fila chegou a {max(aparelho.filas_vistas)} reports (uma volta são {teto})"
    )
    assert aparelho.descartados == 0


# ---------------------------------------------------------------------------
# 5. A luz segura a borda
# ---------------------------------------------------------------------------


class _Backend:
    """O backend visto pela luz: o bit do firmware, a posse e a escrita da luz."""

    def __init__(self, *, mudo_no_firmware: bool) -> None:
        self.firmware: bool | None = mudo_no_firmware
        self.posse: bool | None = None
        self.escritas: list[tuple[str | None, int | None]] = []
        self.voltas = 0

    def set_microphone_led(self, aceso: Any, *, uniq: str | None = None) -> bool:
        self.escritas.append((uniq, aceso))
        return True

    def audio_status_for(self, uniq: str | None = None) -> dict[str, bool] | None:
        if self.firmware is None:
            return None
        return {"fone_plugado": False, "mic_externo": False, "mic_mudo": self.firmware}

    def microphone_mute_for(self, uniq: str | None = None) -> bool | None:
        return self.posse

    def describe_controllers(self) -> list[dict[str, object]]:
        self.voltas += 1
        return [
            {
                "index": 0,
                "connected": True,
                "transport": "bt",
                "is_primary": True,
                "uniq": UM,
                "battery_pct": 90,
            }
        ]


class _Daemon:
    def __init__(self, controller: _Backend) -> None:
        self.bus = EventBus()
        self.controller = controller
        self._tasks: list[asyncio.Task[Any]] = []

    def _is_stopping(self) -> bool:
        return False

    async def _run_blocking(self, fn: Any, *args: Any) -> Any:
        await asyncio.sleep(0)
        return fn(*args)


@pytest.fixture
def luz_na_bancada(monkeypatch: pytest.MonkeyPatch) -> None:
    """As cadências encolhidas, e as peças irmãs de mentira (ninguém ouve)."""
    monkeypatch.setattr(luz, "INTERVALO_S", 0.001)
    monkeypatch.setattr(luz, "INTERVALO_DE_QUEM_OUVE_S", 0.0)
    monkeypatch.setattr(luz, "ESPERA_DO_REPORT_S", 0.001)
    monkeypatch.setattr(luz, "_fontes_para", lambda _uniqs, _mesa: {})
    peca_a = types.ModuleType(luz.MODULO_DE_QUEM_OUVE)
    peca_a.quem_ouve_agora = lambda _uniqs: {UM: []}  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, luz.MODULO_DE_QUEM_OUVE, peca_a)
    monkeypatch.setitem(sys.modules, luz.MODULO_DO_NIVEL, types.ModuleType(luz.MODULO_DO_NIVEL))


async def _esperar_voltas(backend: _Backend, voltas: int) -> None:
    alvo = backend.voltas + voltas
    for _ in range(20000):
        if backend.voltas >= alvo:
            return
        await asyncio.sleep(0.001)
    raise AssertionError("o laço da luz parou de girar")


async def _a_borda(
    backend: _Backend,
    *,
    mudo_da_borda: bool,
    o_ato: Callable[[], None],
    na_borda: Callable[[], None] | None = None,
    depois: Callable[[], None] | None = None,
) -> tuple[list[int | None], list[int | None]]:
    """A luz de produção antes e depois de UMA borda; devolve as duas escritas.

    `na_borda` é o que muda no aparelho junto do aperto (o kernel virando o
    bit). `o_ato` roda depois de a luz ter girado VINTE voltas com a borda na
    mão — o ato atrasado de propósito, que é onde o esquecer-e-reler pintava o
    estado velho. `depois` é a devolução da posse, com o firmware já
    concordando.
    """
    daemon = _Daemon(backend)
    tarefa = asyncio.create_task(luz.luz_do_mic_loop(daemon))
    try:
        await _esperar_voltas(backend, 20)
        antes = [valor for _u, valor in backend.escritas]
        marca = len(backend.escritas)
        if na_borda is not None:
            na_borda()
        daemon.bus.publish(
            str(EventTopic.MIC_DA_MESA), {"uniq": UM, "mudo": mudo_da_borda, "seq": 1}
        )
        await _esperar_voltas(backend, 20)
        o_ato()
        await _esperar_voltas(backend, 20)
        if depois is not None:
            depois()
            await _esperar_voltas(backend, 20)
        apos = [valor for _u, valor in backend.escritas[marca:]]
    finally:
        tarefa.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await tarefa
    return antes, apos


@pytest.mark.usefixtures("luz_na_bancada")
async def test_a_luz_nao_repinta_o_estado_de_antes_no_aperto_que_cala(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """(a) Borda `mudo=True`, bit ainda `False`, o ato toma a posse com `True`.

    A luz não escreve ACESA em tique nenhum depois da borda, e termina APAGADA.

    MORDIDA: o esquecer-e-reler de antes (sem `_segura_a_borda`) escreve ACESA
    no tique seguinte à borda, pelo bit de antes do aperto.
    """
    monkeypatch.setattr(luz, "SEGURA_A_BORDA_S", 30.0)
    backend = _Backend(mudo_no_firmware=False)

    def _o_ato() -> None:
        backend.posse = True

    def _a_devolucao() -> None:
        backend.firmware = True
        backend.posse = None

    antes, apos = await _a_borda(backend, mudo_da_borda=True, o_ato=_o_ato, depois=_a_devolucao)

    assert antes == [luz.ACESA]
    assert luz.ACESA not in apos, f"a luz repintou o estado de antes: {apos}"
    assert apos and apos[-1] == luz.APAGADA
    assert luz.estado_da_luz_do_mic(UM) == luz.APAGADA


@pytest.mark.usefixtures("luz_na_bancada")
async def test_a_luz_nao_repinta_o_estado_de_antes_no_aperto_que_liga(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """(b) O espelho: borda `mudo=False`, bit ainda `True`, a posse vira `False`.

    MORDIDA: sem `_segura_a_borda`, a luz escreve APAGADA pelo bit velho.
    """
    monkeypatch.setattr(luz, "SEGURA_A_BORDA_S", 30.0)
    backend = _Backend(mudo_no_firmware=True)

    def _o_ato() -> None:
        backend.posse = False

    def _a_devolucao() -> None:
        backend.firmware = False
        backend.posse = None

    antes, apos = await _a_borda(
        backend, mudo_da_borda=False, o_ato=_o_ato, depois=_a_devolucao
    )

    assert antes == [luz.APAGADA]
    assert luz.APAGADA not in apos, f"a luz repintou o estado de antes: {apos}"
    assert apos and apos[-1] == luz.ACESA


@pytest.mark.usefixtures("luz_na_bancada")
async def test_a_reancoragem_liga_e_a_luz_nunca_apaga(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """(c) Borda `mudo=True` do primeiro aperto, e o ato LIGA (a reancoragem).

    O kernel vira o bit junto da borda (o toggle cego do `hid-playstation`,
    firmware `True`), e o ato, com a mesa sem dono, liga: escreve a posse
    `False`. A luz nunca escreve APAGADA e termina ACESA.

    MORDIDAS: pintar o `mudo` cru da borda escreve APAGADA; e o
    esquecer-e-reler de antes também, pelo bit que o kernel virou.
    """
    monkeypatch.setattr(luz, "SEGURA_A_BORDA_S", 30.0)
    backend = _Backend(mudo_no_firmware=False)

    def _o_kernel_vira() -> None:
        backend.firmware = True

    def _o_ato() -> None:
        backend.posse = False  # o firmware obedece só na volta seguinte

    def _a_devolucao() -> None:
        backend.firmware = False
        backend.posse = None

    antes, apos = await _a_borda(
        backend,
        mudo_da_borda=True,
        na_borda=_o_kernel_vira,
        o_ato=_o_ato,
        depois=_a_devolucao,
    )

    assert antes == [luz.ACESA]
    assert luz.APAGADA not in apos, f"a luz apagou o microfone que o ato ligou: {apos}"
    assert apos and apos[-1] == luz.ACESA


@pytest.mark.usefixtures("luz_na_bancada")
async def test_o_ato_que_nao_escreve_solta_a_borda_no_teto(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """(c) sem escrita: o ato liga e vê «já está» (bit `False`, posse do kernel).

    Nenhuma posse aparece; a luz segura até `SEGURA_A_BORDA_S`, não escreve
    APAGADA em tique nenhum, e passado o teto reescreve ACESA pelo bit fresco.

    MORDIDA: pintar o `mudo` cru da borda (`True`) escreve APAGADA.
    """
    monkeypatch.setattr(luz, "SEGURA_A_BORDA_S", 0.01)
    backend = _Backend(mudo_no_firmware=False)

    antes, apos = await _a_borda(
        backend, mudo_da_borda=True, o_ato=lambda: None, depois=lambda: None
    )

    assert antes == [luz.ACESA]
    assert apos == [luz.ACESA], f"depois do teto, UMA reescrita pelo bit fresco: {apos}"
