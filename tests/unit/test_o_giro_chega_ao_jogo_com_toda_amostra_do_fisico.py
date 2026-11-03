"""O-GIRO-CHEGA-AO-JOGO-COM-TODA-AMOSTRA-DO-FISICO-01 — toda amostra do físico chega ao jogo.

Na partida de 02/11, os quatro físicos pelo rádio, o jogo viu 247 e 178 Hz em dois deles: o
reader emitia numa grade de 4 ms, e a rajada de k reports dentro de 4 ms chegava como um só.
Agora sai toda amostra distinta pelo carimbo do sensor, e o pad do gadget guarda na fila o que o
endpoint de 1 ms ainda não levou.

As peças são leitores e pads de verdade (`PhysicalReportReader`, `UhidDualSense` nos caminhos
uhid e gadget, `UinputGamepad` no Xbox), alimentados por reports crus do cabo (0x01, a cada 4 ms
exatos) e do rádio (0x31 com CRC, nas cinco janelas de rajada da referência canônica §5). O
endpoint do gadget é de mentira: um report em voo por vez, que o host leva a cada 1 ms, e o fio
do gadget escoa a fila no `POLLOUT`, como no produto. O relógio é de mentira; nada aqui dorme.
"""

from __future__ import annotations

import contextlib
import errno
import heapq
import os
import random
import struct
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any

import pytest
import structlog

from hefesto_dualsense4unix.core.ds_output_report import BT_INPUT_CRC_SEED, bt_crc32
from hefesto_dualsense4unix.core.physical_report_reader import (
    CONTADOR_DE_REPORT_OFFSET,
    INPUT_REPORT_BT_SIZE,
    MOTION_WINDOW_LEN,
    PhysicalReportReader,
)
from hefesto_dualsense4unix.integrations import uhid_gamepad as uhid
from hefesto_dualsense4unix.integrations.uinput_gamepad import UinputGamepad

_DUALSENSE = 0x0CE6
_EDGE = 0x0DF2
_APARELHOS = {"dualsense": _DUALSENSE, "edge": _EDGE}
_JANELAS_DO_RADIO = {
    "janela_1": 363.3,
    "janela_2": 239.9,
    "janela_3": 392.4,
    "janela_4": 38.3,
    "janela_5": 69.7,
}
_TRANSPORTES = ["cabo", *_JANELAS_DO_RADIO]
_RAJADA_S = 0.001255
_SEGUNDOS = 1.0
_CARIMBO_NO_REPORT = slice(1 + 15 + 12, 1 + 15 + 16)


class _Relogio:
    def __init__(self) -> None:
        self.agora = 1000.0

    def __call__(self) -> float:
        return self.agora


@dataclass
class _Fluxo:
    """O que a peça mandou: os reports na hora certa e a conta que o leitor tem de fechar."""

    chegadas: list[tuple[float, bytes]] = field(default_factory=list)
    carimbos: list[bytes] = field(default_factory=list)
    repetidos: int = 0
    pulados_no_ar: int = 0


def _report(transporte: str, contador: int, amostra: int, carimbo: int) -> bytes:
    """Report cru com o contador do aparelho, o giro em `amostra` e o carimbo do sensor."""
    janela = bytearray(MOTION_WINDOW_LEN)
    janela[0:2] = (amostra & 0xFFFF).to_bytes(2, "little")
    janela[12:16] = carimbo.to_bytes(4, "little")
    if transporte == "cabo":
        cru = bytearray(64)
        cru[0], base = 0x01, 1
        cru[53] = 0x29
    else:
        cru = bytearray(INPUT_REPORT_BT_SIZE)
        cru[0], cru[1], base = 0x31, 0x01, 2
    cru[base : base + 6] = bytes([0x80, 0x80, 0x80, 0x80, 0, 0])
    inicio = base + CONTADOR_DE_REPORT_OFFSET
    cru[inicio : inicio + 4] = (contador & 0xFFFFFFFF).to_bytes(4, "little")
    cru[base + 15 : base + 15 + MOTION_WINDOW_LEN] = janela
    if transporte != "cabo":
        cru[-4:] = bt_crc32(cru[:-4], seed=BT_INPUT_CRC_SEED).to_bytes(4, "little")
    return bytes(cru)


def _horas_de_chegada(transporte: str, semente: int, segundos: float) -> list[float]:
    """O cabo a cada 4 ms exatos; o rádio em rajadas de 1,255 ms, na média da janela."""
    if transporte == "cabo":
        return [i * 0.004 for i in range(round(segundos / 0.004))]
    hz = _JANELAS_DO_RADIO[transporte]
    sorteio = random.Random(semente)
    horas: list[float] = []
    t = 0.0
    while t < segundos:
        k = sorteio.randint(2, 6)
        for _ in range(k):
            horas.append(t)
            t += _RAJADA_S
        t += max(0.0, k / hz - k * _RAJADA_S) * sorteio.uniform(0.5, 1.5)
    return [h for h in horas if h < segundos]


def _fluxo(transporte: str, player: int, semente: int, inicio: float) -> _Fluxo:
    """Os reports de uma peça: amostras novas, umas perdidas no ar e umas lidas de novo."""
    sorteio = random.Random(semente * 7 + player)
    fluxo = _Fluxo()
    contador = 1000 * player
    carimbo = 1_000_000 * player
    ultimo: bytes | None = None
    for i, hora in enumerate(_horas_de_chegada(transporte, semente + player, _SEGUNDOS)):
        if ultimo is not None and transporte != "cabo" and sorteio.random() < 0.03:
            fluxo.chegadas.append((inicio + hora, ultimo))
            fluxo.repetidos += 1
            continue
        if i and transporte != "cabo" and sorteio.random() < 0.05:
            contador += 1
            carimbo += 1250
            fluxo.pulados_no_ar += 1
        contador += 1
        carimbo += 1250
        ultimo = _report(transporte, contador, i, carimbo)
        fluxo.chegadas.append((inicio + hora, ultimo))
        fluxo.carimbos.append(carimbo.to_bytes(4, "little"))
    return fluxo


class _Endpoint:
    """O `/dev/hidgN` de mentira: um report em voo por vez, que o host leva a cada 1 ms."""

    def __init__(self) -> None:
        self.em_voo: bytes | None = None
        self.no_jogo: list[bytes] = []
        self.recusas = 0

    def host_le(self) -> None:
        if self.em_voo is not None:
            self.no_jogo.append(self.em_voo)
            self.em_voo = None


class _OsDoGadget:
    """O `os` do módulo do pad: a escrita no fd do gadget cai no endpoint de mentira."""

    def __init__(self) -> None:
        self.endpoints: dict[int, _Endpoint] = {}

    def write(self, fd: int, dados: bytes) -> int:
        endpoint = self.endpoints.get(fd)
        if endpoint is None:
            return os.write(fd, dados)
        if endpoint.em_voo is not None:
            endpoint.recusas += 1
            raise BlockingIOError(errno.EAGAIN, "write_pending")
        endpoint.em_voo = bytes(dados)
        return len(dados)

    def __getattr__(self, nome: str) -> Any:
        return getattr(os, nome)


class _Peca:
    """Um controle na mão de alguém: o pad dele no caminho dado e o leitor do hidraw dele."""

    def __init__(
        self, player: int, modo: int, caminho: str, relogio: _Relogio, os_do_gadget: _OsDoGadget
    ) -> None:
        self.player = player
        self.caminho = caminho
        self._leitura, self._escrita = os.pipe()
        os.set_blocking(self._leitura, False)
        os.set_blocking(self._escrita, False)
        pad = uhid.UhidDualSense(
            player=player, product=modo, time_fn=relogio, sleep_fn=lambda _s: None
        )
        pad._fd = self._escrita
        self.endpoint: _Endpoint | None = None
        if caminho == "gadget":
            pad._gadget = uhid._GadgetDoPad(
                cliente=None, fd=-1, gadget="g", serial=f"hefesto-pad-{player}"
            )
            self.endpoint = _Endpoint()
            os_do_gadget.endpoints[self._escrita] = self.endpoint
        pad.set_motion_streaming(True)
        pad._game_open = True
        self.pad = pad
        self.leitor = PhysicalReportReader(lambda: None, pad, time_fn=relogio)
        self.do_uhid: list[bytes] = []

    def chega(self, report: bytes, agora: float) -> None:
        self.leitor._processar(report, agora)

    def host_le(self) -> None:
        """O host leva o report em voo, e o fio do gadget escoa a fila no `POLLOUT`."""
        if self.endpoint is None:
            self._drenar_o_uhid()
            return
        self.endpoint.host_le()
        gadget, fd = self.pad._gadget, self.pad._fd
        if gadget is not None and fd is not None and gadget.fila:
            with self.pad._lock:
                uhid._escoar_a_fila(self.pad, gadget, fd)

    def _drenar_o_uhid(self) -> None:
        with contextlib.suppress(BlockingIOError):
            while True:
                pedaco = os.read(self._leitura, 65536)
                if not pedaco:
                    return
                i = 0
                while i + 6 <= len(pedaco):
                    tipo, tamanho = struct.unpack_from("<IH", pedaco, i)
                    assert tipo == uhid.UHID_INPUT2
                    self.do_uhid.append(pedaco[i + 6 : i + 6 + tamanho])
                    i += 6 + tamanho

    def no_jogo(self) -> list[bytes]:
        """Os carimbos das amostras que o jogo leu, na ordem em que leu.

        O report de carimbo zero é o do pad que ainda não recebeu amostra (o fone e a bateria
        do primeiro report do físico saem antes do movimento) e não é amostra.
        """
        reports = self.endpoint.no_jogo if self.endpoint is not None else self.do_uhid
        return [r[_CARIMBO_NO_REPORT] for r in reports if any(r[_CARIMBO_NO_REPORT])]

    def assentar(self, transporte: str, agora: float) -> None:
        """O primeiro report e o host que o leva: a medida começa com o endpoint livre."""
        self.chega(_report(transporte, 1, 0, 4000), agora)
        for _ in range(4):
            self.host_le()
        assert self.endpoint is not None and self.fila() == 0
        self.endpoint.no_jogo.clear()
        self.endpoint.recusas = 0

    def fila(self) -> int:
        gadget = self.pad._gadget
        return len(gadget.fila) if gadget is not None else 0

    def fechar(self) -> None:
        self.pad._gadget = None
        self.pad._fd = None
        for fd in (self._leitura, self._escrita):
            with contextlib.suppress(OSError):
                os.close(fd)


@pytest.fixture
def os_do_gadget(monkeypatch: pytest.MonkeyPatch) -> _OsDoGadget:
    falso = _OsDoGadget()
    monkeypatch.setattr(uhid, "os", falso)
    return falso


@pytest.fixture
def mesa() -> Iterator[list[_Peca]]:
    pecas: list[_Peca] = []
    yield pecas
    for peca in pecas:
        peca.fechar()


def _jogar(pecas: list[_Peca], fluxos: list[_Fluxo], relogio: _Relogio) -> None:
    """Os reports das quatro peças e o host a cada 1 ms, numa linha do tempo só."""
    eventos: list[tuple[float, int, int, bytes]] = []
    for n, fluxo in enumerate(fluxos):
        for hora, report in fluxo.chegadas:
            eventos.append((hora, 1, n, report))
    fim = max(hora for hora, *_ in eventos) + 0.5
    t = relogio.agora
    while t < fim:
        eventos.append((t, 0, -1, b""))
        t += 0.001
    heapq.heapify(eventos)
    while eventos:
        hora, tipo, n, report = heapq.heappop(eventos)
        relogio.agora = hora
        if tipo == 1:
            pecas[n].chega(report, hora)
        else:
            for peca in pecas:
                peca.host_le()


@pytest.mark.parametrize("caminho", ["uhid", "gadget"])
@pytest.mark.parametrize("transporte", _TRANSPORTES)
@pytest.mark.parametrize("modo", ["dualsense", "edge"])
@pytest.mark.parametrize("aparelho", ["dualsense", "edge"])
def test_toda_amostra_distinta_chega_ao_jogo_nos_quatro_ao_mesmo_tempo(
    mesa: list[_Peca],
    os_do_gadget: _OsDoGadget,
    aparelho: str,
    modo: str,
    transporte: str,
    caminho: str,
) -> None:
    """P1 a P4 juntos: o jogo lê cada amostra nova, na ordem, com o carimbo do sensor intacto."""
    relogio = _Relogio()
    semente = sum(map(ord, aparelho + modo + transporte + caminho))
    for n in (1, 2, 3, 4):
        mesa.append(_Peca(n, _APARELHOS[modo], caminho, relogio, os_do_gadget))
    fluxos = [_fluxo(transporte, n, semente, relogio.agora) for n in (1, 2, 3, 4)]

    with structlog.testing.capture_logs() as registros:
        _jogar(mesa, fluxos, relogio)
        contas = [peca.leitor.amostras for peca in mesa]
        for peca, fluxo in zip(mesa, fluxos, strict=True):
            peca.pad._game_open = False
            peca.chega(fluxo.chegadas[-1][1], relogio.agora)

    for peca, fluxo, conta in zip(mesa, fluxos, contas, strict=True):
        lidos = len(fluxo.chegadas)
        assert peca.no_jogo() == fluxo.carimbos, (
            f"P{peca.player}: o jogo leu {len(peca.no_jogo())} de {len(fluxo.carimbos)} amostras"
        )
        assert conta == {
            "lidos": lidos,
            "pulados_no_ar": fluxo.pulados_no_ar,
            "duplicados": fluxo.repetidos,
            "entregues": len(fluxo.carimbos),
        }
        assert conta["entregues"] == conta["lidos"] - conta["duplicados"]
        assert peca.fila() == 0
        assert peca.pad._gadget is None or peca.pad._gadget.fila_cheia == 0
    sessoes = {
        r["player"]: r for r in registros if r["event"] == "motion_reader_amostras_da_sessao"
    }
    for peca, conta in zip(mesa, contas, strict=True):
        linha = sessoes[peca.player]
        assert linha["motivo"] == "jogo_largou"
        assert {nome: linha[nome] for nome in conta} == conta


@pytest.mark.parametrize("rajada", [2, 5, 12])
def test_a_rajada_que_o_leitor_le_junta_espera_na_fila_e_sai_inteira(
    mesa: list[_Peca], os_do_gadget: _OsDoGadget, rajada: int
) -> None:
    """O leitor atrasado lê k reports no mesmo instante: o endpoint recusa, a fila guarda."""
    relogio = _Relogio()
    peca = _Peca(2, _EDGE, "gadget", relogio, os_do_gadget)
    mesa.append(peca)
    peca.assentar("janela_3", relogio.agora)
    carimbos = []
    for i in range(rajada):
        carimbo = 5000 + 1250 * i
        peca.chega(_report("janela_3", 10 + i, i, carimbo), relogio.agora)
        carimbos.append(carimbo.to_bytes(4, "little"))
    assert peca.endpoint is not None
    assert peca.endpoint.recusas == rajada - 1
    assert peca.fila() == rajada - 1
    for _ in range(rajada):
        relogio.agora += 0.001
        peca.host_le()
    assert peca.no_jogo() == carimbos
    assert peca.fila() == 0


def test_o_host_que_parou_de_ler_enche_a_fila_ate_o_teto_e_a_fila_se_diz_parada(
    mesa: list[_Peca], os_do_gadget: _OsDoGadget
) -> None:
    """Sem host, a fila para no teto e conta a recusa; com o host de volta, escoa pela ordem."""
    relogio = _Relogio()
    peca = _Peca(1, _DUALSENSE, "gadget", relogio, os_do_gadget)
    mesa.append(peca)
    peca.assentar("cabo", relogio.agora)
    total = uhid._GADGET_FILA_TETO + 1 + 5
    with structlog.testing.capture_logs() as registros:
        for i in range(total):
            peca.chega(_report("cabo", i, i, 7000 + 1250 * i), relogio.agora)
            relogio.agora += 0.004
    assert peca.fila() == uhid._GADGET_FILA_TETO
    assert peca.pad._gadget is not None and peca.pad._gadget.fila_cheia == 5
    assert [r["event"] for r in registros].count("pad_usb_fila_parada") == 1
    for _ in range(uhid._GADGET_FILA_TETO + 1):
        peca.host_le()
    esperados = [(7000 + 1250 * i).to_bytes(4, "little") for i in range(uhid._GADGET_FILA_TETO + 1)]
    assert peca.no_jogo() == esperados
    assert peca.pad._gadget.fila_cheia == 0


class _NoDoUinput:
    """O nó evdev do pad Xbox: guarda toda escrita que o pad fizer."""

    def __init__(self) -> None:
        self.escritas: list[tuple[Any, ...]] = []

    def write(self, *args: Any) -> None:
        self.escritas.append(args)

    def syn(self) -> None:
        self.escritas.append(("syn",))


@pytest.mark.parametrize("transporte", _TRANSPORTES)
@pytest.mark.parametrize("aparelho", ["dualsense", "edge"])
def test_no_modo_xbox_nenhum_giro_chega_ao_uinput(aparelho: str, transporte: str) -> None:
    """O Xbox não tem canal de giro: o leitor lê o físico e nada sai para o nó do jogo."""
    relogio = _Relogio()
    pad = UinputGamepad.for_flavor("xbox")
    no = _NoDoUinput()
    pad._device = no
    leitor = PhysicalReportReader(lambda: None, pad, time_fn=relogio)
    fluxo = _fluxo(transporte, 3, sum(map(ord, aparelho + transporte)), relogio.agora)
    for hora, report in fluxo.chegadas:
        relogio.agora = hora
        leitor._processar(report, hora)
    assert no.escritas == []
    assert leitor.amostras["lidos"] == 0
    assert leitor.amostras["entregues"] == 0


@pytest.mark.parametrize("caminho", ["uhid", "gadget"])
@pytest.mark.parametrize("transporte", ["cabo", "janela_3"])
def test_o_mesmo_carimbo_e_a_mesma_amostra_e_o_carimbo_zero_separa_pelo_valor(
    mesa: list[_Peca], os_do_gadget: _OsDoGadget, caminho: str, transporte: str
) -> None:
    """O carimbo repetido com outro valor não se repete no jogo; sem carimbo, o valor separa."""
    relogio = _Relogio()
    peca = _Peca(3, _EDGE, caminho, relogio, os_do_gadget)
    mesa.append(peca)
    if caminho == "gadget":
        peca.assentar(transporte, relogio.agora)
    else:
        peca.chega(_report(transporte, 1, 0, 4000), relogio.agora)
        peca.host_le()
        peca.do_uhid.clear()
    antes = dict(peca.leitor.amostras)
    for contador, amostra in ((2, 11), (3, 12)):
        relogio.agora += 0.004
        peca.chega(_report(transporte, contador, amostra, 9000), relogio.agora)
        peca.host_le()
    assert peca.no_jogo() == [(9000).to_bytes(4, "little")]
    for contador, amostra in ((4, 21), (5, 22)):
        relogio.agora += 0.004
        peca.chega(_report(transporte, contador, amostra, 0), relogio.agora)
        peca.host_le()
    depois = peca.leitor.amostras
    assert depois["entregues"] - antes["entregues"] == 3
    assert depois["duplicados"] - antes["duplicados"] == 1
