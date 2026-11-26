"""A-FILA-DO-GADGET-TEM-TETO-DE-IDADE-E-MOSTRA-A-FUNDURA-01 — a fila tem teto de idade.

D-2511-A-FILA-DO-GADGET-GUARDA-SO-O-ULTIMO-DECIMO-DE-SEGUNDO. Com o host parado, a fila do pad
no gadget guardava até 1000 reports e recusava o novo: na volta, o jogo lia segundos de estado
velho antes do de agora (0,66 s para voltar a menos de 20 ms depois de 2 s parado, 1,33 s depois
de 6 s; medido com `_enviar_pelo_gadget` real). Agora sai da frente o report mais velho que
`_GADGET_FILA_IDADE_S`, o novo nunca se recusa, e o `state_full` mostra a fundura e a idade.

As peças são pads de verdade (`UhidDualSense` no caminho gadget) com o endpoint de mentira do
`f_hid` (um report em voo por vez, que o host leva quando lê) e o relógio de mentira.

MORDIDA: devolver o teto de contagem (`if len(gadget.fila) >= 1000: recusa`) no lugar da poda
por idade reprova a idade, a fundura e o report novo que tem de estar na fila.
"""

from __future__ import annotations

import contextlib
import errno
import os
from collections.abc import Iterator
from typing import Any

import pytest
import structlog

from hefesto_dualsense4unix.daemon.ipc_handlers import IpcHandlersMixin
from hefesto_dualsense4unix.daemon.lifecycle import Daemon
from hefesto_dualsense4unix.integrations import uhid_gamepad as uhid
from hefesto_dualsense4unix.testing import FakeController

_DUALSENSE = 0x0CE6
_EDGE = 0x0DF2
_PERIODO_S = 0.004


class _Relogio:
    def __init__(self) -> None:
        self.agora = 1000.0

    def __call__(self) -> float:
        return self.agora


class _Endpoint:
    """O `f_hid`: um report em voo por vez, e o host que o leva quando lê."""

    def __init__(self) -> None:
        self.em_voo: bytes | None = None
        self.no_jogo: list[bytes] = []

    def host_le(self) -> None:
        if self.em_voo is not None:
            self.no_jogo.append(self.em_voo)
            self.em_voo = None


class _OsDoGadget:
    def __init__(self) -> None:
        self.endpoints: dict[int, _Endpoint] = {}

    def write(self, fd: int, dados: bytes) -> int:
        endpoint = self.endpoints.get(fd)
        if endpoint is None:
            return os.write(fd, dados)
        if endpoint.em_voo is not None:
            raise BlockingIOError(errno.EAGAIN, "write_pending")
        endpoint.em_voo = bytes(dados)
        return len(dados)

    def __getattr__(self, nome: str) -> Any:
        return getattr(os, nome)


class _Peca:
    """O pad de um jogador no gadget, vestido como no produto, com o endpoint dele."""

    def __init__(self, player: int, modo: int, relogio: _Relogio, os_falso: _OsDoGadget) -> None:
        self.player = player
        self.relogio = relogio
        self._leitura, self._escrita = os.pipe()
        pad = uhid.UhidDualSense(
            player=player, product=modo, time_fn=relogio, sleep_fn=lambda _s: None
        )
        pad._fd = self._escrita
        pad._gadget = uhid._GadgetDoPad(
            cliente=None, fd=-1, gadget=f"g{player}", serial=f"hefesto-pad-{player}"
        )
        self.endpoint = _Endpoint()
        os_falso.endpoints[self._escrita] = self.endpoint
        uhid._MACS_DOS_VPADS_VIVOS.vestir(pad)
        self.pad = pad
        self.n = 0
        self.nascido: dict[bytes, float] = {}

    @property
    def gadget(self) -> uhid._GadgetDoPad:
        assert self.pad._gadget is not None
        return self.pad._gadget

    def manda(self) -> bytes:
        report = self.player.to_bytes(1, "little") + self.n.to_bytes(8, "little") + bytes(55)
        self.n += 1
        self.nascido[report] = self.relogio.agora
        assert uhid._enviar_pelo_gadget(self.pad, report), "o report novo foi recusado"
        return report

    def host_le(self) -> None:
        self.endpoint.host_le()
        fd = self.pad._fd
        assert fd is not None
        if self.gadget.fila:
            with self.pad._lock:
                uhid._escoar_a_fila(self.pad, self.gadget, fd)

    def idade_da_cabeca(self) -> float:
        fila = self.gadget.fila
        return self.relogio.agora - fila[0][0] if fila else 0.0

    def fechar(self) -> None:
        uhid._MACS_DOS_VPADS_VIVOS.despir(self.pad)
        self.pad._gadget = None
        self.pad._fd = None
        for fd in (self._leitura, self._escrita):
            with contextlib.suppress(OSError):
                os.close(fd)


@pytest.fixture
def os_falso(monkeypatch: pytest.MonkeyPatch) -> _OsDoGadget:
    falso = _OsDoGadget()
    monkeypatch.setattr(uhid, "os", falso)
    return falso


@pytest.fixture
def mesa() -> Iterator[list[_Peca]]:
    pecas: list[_Peca] = []
    yield pecas
    for peca in pecas:
        peca.fechar()


def _quatro(mesa: list[_Peca], relogio: _Relogio, os_falso: _OsDoGadget) -> None:
    """P1 a P4 no gadget, com máscaras misturadas na mesma mesa (DualSense e Edge)."""
    for player, modo in ((1, _DUALSENSE), (2, _EDGE), (3, _DUALSENSE), (4, _EDGE)):
        mesa.append(_Peca(player, modo, relogio, os_falso))


@pytest.mark.parametrize("parado", [1, 2, 3, 4])
@pytest.mark.parametrize("parada_s", [0.3, 2.0, 6.0])
def test_o_host_parado_de_um_jogador_nao_enche_a_fila_alem_da_idade(
    mesa: list[_Peca], os_falso: _OsDoGadget, parado: int, parada_s: float
) -> None:
    """Com o host de um jogador parado, a fila dele guarda só o último décimo de segundo.

    Os outros três seguem lendo a 1 kHz, sem poda; o do jogador parado nunca recusa o report
    novo, e na volta o jogo chega ao estado de agora em vez de ler segundos de estado velho.
    """
    relogio = _Relogio()
    _quatro(mesa, relogio, os_falso)
    teto = uhid._GADGET_FILA_IDADE_S
    fim = relogio.agora + parada_s
    ultimo: bytes = b""
    pico_da_idade = 0.0
    with structlog.testing.capture_logs() as registros:
        proximo = relogio.agora
        while relogio.agora < fim:
            if relogio.agora >= proximo:
                for peca in mesa:
                    report = peca.manda()
                    if peca.player == parado:
                        ultimo = report
                pico_da_idade = max(pico_da_idade, mesa[parado - 1].idade_da_cabeca())
                proximo += _PERIODO_S
            for peca in mesa:
                if peca.player != parado:
                    peca.host_le()
            relogio.agora += 0.001
        quieto = mesa[parado - 1]
        assert pico_da_idade <= teto + 1e-9, f"a fila guardou {pico_da_idade:.3f} s de estado"
        assert len(quieto.gadget.fila) <= int(teto / _PERIODO_S) + 1
        assert quieto.gadget.fila[-1][1] == ultimo, "o report de agora não está na fila"
        for peca in mesa:
            if peca.player != parado:
                assert peca.gadget.descartados == 0
                assert len(peca.gadget.fila) <= 1
        for _ in range(int(teto / 0.001) + 50):
            quieto.host_le()
            relogio.agora += 0.001
    assert quieto.endpoint.no_jogo[-1] == ultimo
    lidos_na_volta = quieto.endpoint.no_jogo[1:]
    assert all(
        quieto.nascido[r] >= fim - teto - _PERIODO_S for r in lidos_na_volta
    ), "o jogo leu estado mais velho que o teto na volta do host"
    numeros = [int.from_bytes(r[1:9], "little") for r in lidos_na_volta]
    assert numeros == sorted(numeros), "a fila saiu fora da ordem"
    eventos = [r for r in registros if r.get("player") == parado]
    assert [r["event"] for r in eventos].count("pad_usb_fila_parada") == (
        1 if parada_s > teto else 0
    )
    escoou = [r for r in eventos if r["event"] == "pad_usb_fila_escoou"]
    assert len(escoou) == 1 and escoou[0]["descartados"] == quieto.gadget.descartados > 0


@pytest.mark.parametrize("rajada", [2, 5, 12, 25])
def test_a_rajada_do_radio_que_o_host_leva_sai_inteira(
    mesa: list[_Peca], os_falso: _OsDoGadget, rajada: int
) -> None:
    """A rajada que chega junta espera na fila e sai toda: a amostra distinta não se perde."""
    relogio = _Relogio()
    peca = _Peca(2, _EDGE, relogio, os_falso)
    mesa.append(peca)
    mandados = [peca.manda() for _ in range(rajada)]
    for _ in range(rajada + 2):
        relogio.agora += 0.001
        peca.host_le()
    assert peca.endpoint.no_jogo == mandados
    assert peca.gadget.descartados == 0
    assert peca.gadget.maior_fundura == rajada - 1


def test_o_state_full_mostra_a_fundura_e_a_idade_de_cada_jogador(
    mesa: list[_Peca], os_falso: _OsDoGadget
) -> None:
    """`filas_dos_gadgets` diz, por jogador, a fundura, a idade, os maiores e os descartados."""
    relogio = _Relogio()
    _quatro(mesa, relogio, os_falso)
    for _ in range(100):
        relogio.agora += _PERIODO_S
        for peca in mesa:
            if peca.player != 3:
                peca.host_le()
        for peca in mesa:
            peca.manda()
    filas = {f["player"]: f for f in uhid.filas_dos_gadgets()}
    assert set(filas) == {1, 2, 3, 4}
    p3 = filas[3]
    assert p3["fundura"] == len(mesa[2].gadget.fila) > 1
    assert 0 < p3["idade_ms"] <= uhid._GADGET_FILA_IDADE_S * 1000.0
    assert p3["descartados"] == mesa[2].gadget.descartados > 0
    assert p3["maior_idade_ms"] >= p3["idade_ms"]
    for player in (1, 2, 4):
        assert filas[player]["descartados"] == 0
        assert filas[player]["fundura"] <= 1


class _Handlers(IpcHandlersMixin):
    def __init__(self, daemon: Any) -> None:
        self.daemon = daemon
        self.store = daemon.store
        self.controller = daemon.controller


@pytest.mark.asyncio
async def test_o_bloco_chega_ao_state_full_do_servico(
    mesa: list[_Peca], os_falso: _OsDoGadget
) -> None:
    """O `daemon.state_full` leva `gamepad_emulation.filas_do_gadget` com a fila de cada pad."""
    relogio = _Relogio()
    _quatro(mesa, relogio, os_falso)
    for peca in mesa:
        peca.manda()
        peca.manda()
    daemon = Daemon(controller=FakeController(transport="usb"))
    estado = await _Handlers(daemon)._handle_daemon_state_full({})
    filas = estado["gamepad_emulation"]["filas_do_gadget"]
    assert [f["player"] for f in filas] == [1, 2, 3, 4]
    assert all(f["fundura"] == 1 for f in filas)
