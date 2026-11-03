"""O-PAD-VIRTUAL-SOLTA-O-QUE-O-FISICO-MUDO-SEGURAVA-01 — a peça que cala leva o repouso ao jogo.

Na partida de 02/11 a entrada do rádio do P2 emudeceu sete vezes em 198 s (de 1,09 s a
3,14 s), e o pad virtual segurou no jogo o último report: o botão apertado, o analógico
fora do centro e a última velocidade angular. O `PhysicalReportReader` de cada peça é o
relógio do mudo: passado `REPOUSO_DO_MUDO_S` sem report válido, ele avisa o pad uma vez
(`soltar_por_mudo`), e o primeiro report válido avisa a volta.

As peças são pads de verdade (`UhidDualSense` nos caminhos uhid e gadget, um pad uinput de
ensaio no Xbox) e leitores de verdade, alimentados por reports crus do cabo (0x01) e do
rádio (0x31 com CRC). O laço do produto é o mesmo par de chamadas de `dispatch_gamepad` e
`forward_all`: `o_pad_da_peca_muda_repousa` e, se a peça fala, o `forward_analog` e o
`forward_buttons` do que a mão segura. O relógio é de mentira; nada aqui dorme.
"""

from __future__ import annotations

import contextlib
import os
import random
import struct
from collections.abc import Iterator
from types import SimpleNamespace
from typing import Any

import pytest

from hefesto_dualsense4unix.core import physical_report_reader as prr
from hefesto_dualsense4unix.core.ds_output_report import BT_INPUT_CRC_SEED, bt_crc32
from hefesto_dualsense4unix.core.physical_report_reader import (
    INPUT_REPORT_BT_SIZE,
    MOTION_WINDOW_LEN,
    REPOUSO_DO_MUDO_S,
    PhysicalReportReader,
    a_peca_calou,
)
from hefesto_dualsense4unix.daemon.subsystems import coop as coop_mod
from hefesto_dualsense4unix.daemon.subsystems import gamepad as gamepad_mod
from hefesto_dualsense4unix.daemon.subsystems.gamepad import o_pad_da_peca_muda_repousa
from hefesto_dualsense4unix.integrations import uhid_gamepad as uhid

_DUALSENSE = 0x0CE6
_EDGE = 0x0DF2
_GIRO = bytes([0x11, 0x01, 0x22, 0x02, 0x33, 0x03])
_ACELERACAO = bytes([0x44, 0x04, 0x55, 0x05, 0x66, 0x06])
_DEDOS_NO_TOUCHPAD = 0x05
_SEGURADO = (200, 60, 128, 128, 0, 255)
_APERTADO = frozenset({"cross", "r2"})
_CENTRO = (128, 128, 128, 128, 0, 0)


def _janela(carimbo: int = 0) -> bytes:
    """A janela de movimento com o carimbo do sensor, que anda a cada amostra como no aparelho."""
    janela = bytearray(MOTION_WINDOW_LEN)
    janela[12:16] = (carimbo & 0xFFFFFFFF).to_bytes(4, "little")
    janela[0:6] = _GIRO
    janela[6:12] = _ACELERACAO
    janela[17] = _DEDOS_NO_TOUCHPAD
    janela[21] = _DEDOS_NO_TOUCHPAD
    return bytes(janela)


def _report_do_cabo(janela: bytes) -> bytes:
    cru = bytearray(64)
    cru[0] = 0x01
    cru[1:7] = bytes(_CENTRO)
    cru[16 : 16 + MOTION_WINDOW_LEN] = janela
    cru[53] = 0x29
    return bytes(cru)


def _report_do_radio(janela: bytes) -> bytes:
    cru = bytearray(INPUT_REPORT_BT_SIZE)
    cru[0] = 0x31
    cru[1] = 0x01
    cru[17 : 17 + MOTION_WINDOW_LEN] = janela
    cru[-4:] = bt_crc32(cru[:-4], seed=BT_INPUT_CRC_SEED).to_bytes(4, "little")
    return bytes(cru)


class _Relogio:
    def __init__(self) -> None:
        self.agora = 1000.0

    def __call__(self) -> float:
        return self.agora


class _PadDoXbox:
    """O pad uinput do Xbox pelo contrato que o laço usa: eixos, botões e a vibração."""

    backend = "uinput"

    def __init__(self, player: int) -> None:
        self.player = player
        self.eixos = _CENTRO
        self.botoes: frozenset[str] = frozenset()

    def forward_analog(self, *, lx: int, ly: int, rx: int, ry: int, l2: int, r2: int) -> None:
        self.eixos = (lx, ly, rx, ry, l2, r2)

    def forward_buttons(self, pressed: frozenset[str]) -> None:
        self.botoes = frozenset(pressed)

    def pump_ff(self) -> None:
        return None


class _Peca:
    """Um controle na mão de alguém: o pad dele, o leitor do hidraw dele e o que a mão segura."""

    def __init__(
        self, player: int, aparelho: int, transporte: str, caminho: str, relogio: _Relogio
    ) -> None:
        self.player = player
        self.transporte = transporte
        self.caminho = caminho
        self.relogio = relogio
        self.eixos = _SEGURADO
        self.botoes = _APERTADO
        self._leitura = -1
        if caminho == "xbox":
            self.pad: Any = _PadDoXbox(player)
        else:
            self._leitura, escrita = os.pipe()
            os.set_blocking(self._leitura, False)
            os.set_blocking(escrita, False)
            pad = uhid.UhidDualSense(
                player=player, product=aparelho, time_fn=relogio, sleep_fn=lambda _s: None
            )
            pad._fd = escrita
            if caminho == "gadget":
                pad._gadget = uhid._GadgetDoPad(
                    cliente=None, fd=-1, gadget="g", serial=f"hefesto-pad-{player}"
                )
            pad.set_motion_streaming(True)
            self.pad = pad
        self.leitor = PhysicalReportReader(lambda: None, self.pad, time_fn=relogio)
        self.leitor._valido_em = relogio()
        self.saidos: list[bytes] = []
        self.carimbo = 0

    def report(self) -> bytes:
        """O próximo report cru que a peça manda pelo cabo ou pelo rádio."""
        self.carimbo += 1
        janela = _janela(self.carimbo)
        return _report_do_cabo(janela) if self.transporte == "usb" else _report_do_radio(janela)

    def fala(self) -> None:
        self.leitor._processar(self.report(), self.relogio())

    def silencio_do_poll(self) -> None:
        self.leitor._conferir_o_mudo(self.relogio())

    def laco(self) -> None:
        self._drenar()
        if o_pad_da_peca_muda_repousa(self.pad, self.leitor):
            return
        lx, ly, rx, ry, l2, r2 = self.eixos
        self.pad.forward_analog(lx=lx, ly=ly, rx=rx, ry=ry, l2=l2, r2=r2)
        self.pad.forward_buttons(self.botoes)

    def _drenar(self) -> None:
        if self._leitura < 0:
            return
        with contextlib.suppress(BlockingIOError):
            while True:
                pedaco = os.read(self._leitura, 65536)
                if not pedaco:
                    break
                self.saidos[:] = (self.saidos + _reports_no_fio(pedaco, self.caminho))[-4:]

    def _ultimo_report(self) -> bytes:
        self._drenar()
        assert self.saidos, f"o pad do P{self.player} nunca emitiu"
        return self.saidos[-1]

    def o_jogo_ve(self) -> dict[str, Any]:
        """O que o jogo lê agora: eixos, os três bytes de botão, o giro, a aceleração e os dedos."""
        if self.caminho == "xbox":
            return {"eixos": self.pad.eixos, "botoes": self.pad.botoes}
        cru = self._ultimo_report()
        referencia = uhid.UhidDualSense(player=9, product=self.pad.product)
        if self.pad._buttons:
            referencia._buttons = self.pad._buttons
        return {
            "eixos": tuple(cru[1:7]),
            "botoes": cru[8:11],
            "botoes_soltos": bytes(referencia._encode_body()[7:10])
            if not self.pad._buttons
            else None,
            "giro": cru[16:22],
            "aceleracao": cru[22:28],
            "dedos": (cru[33], cru[37]),
        }

    def fechar(self) -> None:
        pad = self.pad
        fd = getattr(pad, "_fd", None)
        for alvo in (self._leitura, fd):
            if isinstance(alvo, int) and alvo >= 0:
                with contextlib.suppress(OSError):
                    os.close(alvo)
        if fd is not None:
            pad._fd = None
            pad._gadget = None


def _reports_no_fio(pedaco: bytes, caminho: str) -> list[bytes]:
    if caminho == "gadget":
        return [pedaco[i : i + 64] for i in range(0, len(pedaco), 64)]
    saida: list[bytes] = []
    i = 0
    while i + 6 <= len(pedaco):
        tipo, tamanho = struct.unpack_from("<IH", pedaco, i)
        assert tipo == uhid.UHID_INPUT2
        saida.append(pedaco[i + 6 : i + 6 + tamanho])
        i += 6 + tamanho
    return saida


def _solto(visto: dict[str, Any], peca: _Peca) -> bool:
    if peca.caminho == "xbox":
        return visto["eixos"] == _CENTRO and not visto["botoes"]
    return (
        visto["eixos"] == _CENTRO
        and visto["botoes"] == visto["botoes_soltos"]
        and visto["giro"] == bytes(6)
        and visto["aceleracao"] == _ACELERACAO
        and all(d & 0x80 for d in visto["dedos"])
    )


def _segurando(visto: dict[str, Any], peca: _Peca) -> bool:
    if peca.caminho == "xbox":
        return bool(visto["eixos"] == _SEGURADO and visto["botoes"] == _APERTADO)
    return bool(visto["eixos"] == _SEGURADO and visto["giro"] == _GIRO)


def _andar(pecas: list[_Peca], relogio: _Relogio, segundos: float, calada: _Peca | None) -> None:
    """O tempo corre em tiques de 4 ms: quem fala manda um report, o poll de quem cala acorda."""
    passos = round(segundos / 0.004)
    for _ in range(passos):
        relogio.agora += 0.004
        for peca in pecas:
            if peca is calada:
                peca.silencio_do_poll()
            else:
                peca.fala()
            peca.laco()


@pytest.fixture
def mesa() -> Iterator[list[_Peca]]:
    pecas: list[_Peca] = []
    yield pecas
    for peca in pecas:
        peca.fechar()


_APARELHOS = {"dualsense": _DUALSENSE, "edge": _EDGE}


@pytest.mark.parametrize("calada_n", [1, 2, 3, 4])
@pytest.mark.parametrize("aparelho", ["dualsense", "edge"])
@pytest.mark.parametrize("transporte", ["usb", "bt"])
@pytest.mark.parametrize("caminho", ["uhid", "gadget", "xbox"])
def test_a_peca_que_cala_solta_tudo_no_jogo_e_as_outras_seguem(
    mesa: list[_Peca], calada_n: int, aparelho: str, transporte: str, caminho: str
) -> None:
    """Analógico fora do centro e botão apertado: o silêncio longo leva o repouso só à peça muda."""
    relogio = _Relogio()
    for n in (1, 2, 3, 4):
        mesa.append(_Peca(n, _APARELHOS[aparelho], transporte, caminho, relogio))
    calada = mesa[calada_n - 1]
    _andar(mesa, relogio, 0.2, None)
    for peca in mesa:
        assert _segurando(peca.o_jogo_ve(), peca), f"P{peca.player} não chegou a segurar"

    _andar(mesa, relogio, REPOUSO_DO_MUDO_S + 0.02, calada)

    assert a_peca_calou(calada.leitor)
    assert _solto(calada.o_jogo_ve(), calada), (
        f"P{calada_n} calou e o jogo segue com o que a mão segurava"
    )
    for peca in mesa:
        if peca is not calada:
            assert not a_peca_calou(peca.leitor)
            assert _segurando(peca.o_jogo_ve(), peca), f"P{peca.player} parou junto"

    _andar(mesa, relogio, 1.0, calada)
    assert _solto(calada.o_jogo_ve(), calada), "o repouso se desfez no meio do mudo"
    if caminho != "xbox":
        assert calada.pad.repousos_pelo_mudo == 1
    assert calada.leitor.mudos == 1

    _andar(mesa, relogio, 0.1, None)
    assert not a_peca_calou(calada.leitor)
    assert _segurando(calada.o_jogo_ve(), calada), "a volta não entregou o estado real"


@pytest.mark.parametrize("transporte", ["usb", "bt"])
@pytest.mark.parametrize("caminho", ["uhid", "gadget", "xbox"])
def test_o_silencio_curto_nao_mexe_em_nada(
    mesa: list[_Peca], transporte: str, caminho: str
) -> None:
    """Abaixo da constante, o jogo segue com o que a mão segura."""
    relogio = _Relogio()
    peca = _Peca(2, _DUALSENSE, transporte, caminho, relogio)
    mesa.append(peca)
    _andar(mesa, relogio, 0.2, None)
    _andar(mesa, relogio, REPOUSO_DO_MUDO_S - 0.02, peca)
    assert not a_peca_calou(peca.leitor)
    assert _segurando(peca.o_jogo_ve(), peca)
    assert peca.leitor.mudos == 0


def _intervalos_do_radio(semente: int, segundos: float) -> list[float]:
    """Rajadas com o p05 (1,255 ms) e o p95 (187 ms) da canônica §5, de 38 a 392 Hz.

    O maior intervalo sorteado é duas vezes o p95 (374 ms), abaixo do piso: a régua prova que
    o silêncio abaixo de `REPOUSO_DO_MUDO_S` nunca vira repouso. O maior intervalo de um rádio
    são não foi medido, e é o aparelho que diz se ele cabe abaixo do piso.
    """
    sorteio = random.Random(semente)
    saida: list[float] = []
    total = 0.0
    while total < segundos:
        faixa = sorteio.random()
        if faixa < 0.05:
            passo = 0.001255
        elif faixa < 0.90:
            passo = sorteio.uniform(1 / 392, 1 / 38)
        elif faixa < 0.99:
            passo = sorteio.uniform(0.03, 0.187)
        else:
            passo = sorteio.uniform(0.187, 2 * 0.187)
        saida.append(passo)
        total += passo
    return saida


class _PollDeMentira:
    """O `prontos_ou_acordado` do leitor no relógio de mentira: o report chega na hora marcada."""

    def __init__(self, leitor: PhysicalReportReader, relogio: _Relogio, chegadas: list[float],
                 fim: float, peca: _Peca) -> None:
        self.leitor = leitor
        self.relogio = relogio
        self.chegadas = list(chegadas)
        self.fim = fim
        self.peca = peca
        self.esperas: list[float] = []
        self._escrita = -1

    def __call__(self, fd: int, wake_r: int, espera: float) -> list[int]:
        self.esperas.append(espera)
        self.peca.laco()
        if self.relogio.agora >= self.fim:
            self.leitor._stop_flag.set()
            os.write(self.leitor._wake_w, b"w")
            return [wake_r]
        if self.chegadas and self.chegadas[0] <= self.relogio.agora + espera:
            self.relogio.agora = max(self.relogio.agora, self.chegadas.pop(0))
            os.write(self._escrita, self.peca.report())
            return [fd]
        self.relogio.agora += espera
        return []


def _rodar_o_leitor_de_verdade(
    monkeypatch: pytest.MonkeyPatch, peca: _Peca, chegadas: list[float], fim: float
) -> _PollDeMentira:
    """O `_read_until_lost` de verdade, reaberto como o `_run` o reabre, até o fim do relógio."""
    leitura, escrita = os.pipe()
    peca.leitor._wake_r, peca.leitor._wake_w = prr._novo_wake_pipe()
    poll = _PollDeMentira(peca.leitor, peca.relogio, chegadas, fim, peca)
    poll._escrita = escrita
    monkeypatch.setattr(prr, "prontos_ou_acordado", poll)
    orcamento = 1.0 if peca.transporte == "usb" else 30.0
    try:
        while not peca.leitor._stop_flag.is_set():
            peca.leitor._read_until_lost(leitura, orcamento)
            peca.laco()
    finally:
        for fd in (leitura, escrita, peca.leitor._wake_r, peca.leitor._wake_w):
            with contextlib.suppress(OSError):
                os.close(fd)
        peca.leitor._wake_r = peca.leitor._wake_w = -1
    return poll


@pytest.mark.parametrize("caminho", ["uhid", "gadget", "xbox"])
@pytest.mark.parametrize("semente", [3, 11, 29])
def test_trinta_segundos_de_radio_cheio_sem_repouso_falso(
    mesa: list[_Peca], monkeypatch: pytest.MonkeyPatch, caminho: str, semente: int
) -> None:
    """O laço de leitura de verdade, 30 s de rajadas do rádio: nenhum repouso falso."""
    relogio = _Relogio()
    peca = _Peca(3, _DUALSENSE, "bt", caminho, relogio)
    mesa.append(peca)
    inicio = relogio.agora
    chegadas: list[float] = []
    t = inicio
    intervalos = _intervalos_do_radio(semente, 30.0)
    assert max(intervalos) < REPOUSO_DO_MUDO_S
    for passo in intervalos:
        t += passo
        chegadas.append(t)
    _rodar_o_leitor_de_verdade(monkeypatch, peca, chegadas, inicio + 30.0)
    assert peca.leitor.mudos == 0, "rajada sã do rádio virou repouso"
    assert not a_peca_calou(peca.leitor)


@pytest.mark.parametrize("transporte", ["usb", "bt"])
@pytest.mark.parametrize("caminho", ["uhid", "gadget", "xbox"])
def test_o_laco_de_leitura_acorda_na_hora_do_mudo_e_o_mudo_atravessa_a_reabertura(
    mesa: list[_Peca], monkeypatch: pytest.MonkeyPatch, transporte: str, caminho: str
) -> None:
    """O mudo de 3,14 s de 02/11: repouso na constante, atravessa a reabertura, a volta desfaz."""
    relogio = _Relogio()
    peca = _Peca(2, _EDGE, transporte, caminho, relogio)
    mesa.append(peca)
    for _ in range(20):
        relogio.agora += 0.004
        peca.fala()
        peca.laco()
    inicio = relogio.agora
    repouso_em: list[float] = []
    soltar = getattr(peca.pad, "soltar_por_mudo", None)
    if callable(soltar):
        def _anotado() -> None:
            repouso_em.append(relogio.agora)
            soltar()
        peca.pad.soltar_por_mudo = _anotado
    chegadas = [inicio + 3.14 + 0.004 * i for i in range(1, 50)]
    _rodar_o_leitor_de_verdade(monkeypatch, peca, chegadas, inicio + 3.5)
    assert peca.leitor.mudos == 1
    if repouso_em:
        atraso = repouso_em[0] - inicio
        assert REPOUSO_DO_MUDO_S <= atraso <= REPOUSO_DO_MUDO_S + 0.006, atraso
    assert not a_peca_calou(peca.leitor)
    peca.laco()
    peca.fala()
    assert _segurando(peca.o_jogo_ve(), peca)


def test_o_pad_mudo_nao_aceita_o_estado_guardado_por_cima_do_repouso() -> None:
    """Quem escrever no pad durante o mudo não reacende o botão: só a volta reabre."""
    relogio = _Relogio()
    peca = _Peca(1, _DUALSENSE, "usb", "uhid", relogio)
    try:
        peca.fala()
        peca.laco()
        peca.pad.soltar_por_mudo()
        peca.pad.forward_analog(lx=200, ly=60, rx=128, ry=128, l2=0, r2=255)
        peca.pad.forward_buttons(_APERTADO)
        assert peca.pad._axes == uhid._AXES_NEUTRAL
        assert peca.pad._buttons == frozenset()
        peca.pad.voltar_do_mudo()
        peca.pad.forward_buttons(_APERTADO)
        assert peca.pad._buttons == _APERTADO
    finally:
        peca.fechar()


class _LeitorDoDeFora:
    """O contrato que o leitor do controle de fora cumpre: a propriedade `mudo`."""

    def __init__(self) -> None:
        self.mudo = False


def test_o_controle_de_fora_entra_pelo_mesmo_contrato_do_mudo() -> None:
    """Pro Controller e 8BitDo: o laço pergunta `mudo` ao leitor, e o pad uinput recebe o centro."""
    leitor = _LeitorDoDeFora()
    pad = _PadDoXbox(2)
    pad.forward_analog(lx=200, ly=60, rx=128, ry=128, l2=0, r2=255)
    pad.forward_buttons(_APERTADO)
    assert not o_pad_da_peca_muda_repousa(pad, leitor)
    leitor.mudo = True
    assert o_pad_da_peca_muda_repousa(pad, leitor)
    assert pad.eixos == _CENTRO and not pad.botoes


def test_dispatch_do_p1_pergunta_ao_leitor_e_nao_reescreve(monkeypatch: pytest.MonkeyPatch) -> None:
    """O P1: com a peça muda, `dispatch_gamepad` não leva o `read_state` ao pad."""
    escrito: list[Any] = []
    pad = SimpleNamespace(
        forward_analog=lambda **k: escrito.append(tuple(k.values())),
        forward_buttons=lambda b: escrito.append(frozenset(b)),
        pump_ff=lambda: escrito.append("pump"),
    )
    daemon = SimpleNamespace(_gamepad_device=pad, _motion_reader=SimpleNamespace(mudo=True))
    for nome in ("_avisar_troca_de_modo", "bater_a_vibracao", "_bater_os_eventos_do_jogo"):
        monkeypatch.setattr(gamepad_mod, nome, lambda _d: None)
    monkeypatch.setattr(gamepad_mod, "_o_p1_e_do_de_fora", lambda _d: False)
    gamepad_mod.dispatch_gamepad(daemon, SimpleNamespace(), _APERTADO)
    assert escrito == [_CENTRO, frozenset(), "pump"], escrito


def test_forward_all_pula_a_peca_muda_sem_ler_o_snapshot(monkeypatch: pytest.MonkeyPatch) -> None:
    """Do P2 ao P4: a peça muda não tem o `snapshot()` levado ao pad."""
    lidos: list[str] = []
    jogador = SimpleNamespace(
        vpad=_PadDoXbox(2),
        motion_reader=SimpleNamespace(mudo=True),
        cedido_ao_primario=False,
        reader=SimpleNamespace(snapshot=lambda: lidos.append("snapshot")),
        identity="aa:bb:cc:00:00:02",
    )
    gerente = SimpleNamespace(
        _ordem_pendente=False,
        _recolher_os_cedidos=lambda: None,
        _andar_a_fila=lambda: None,
        _promote_pending=lambda: None,
        _daemon=SimpleNamespace(store=None),
        _players={"aa:bb:cc:00:00:02": jogador},
        _espera=lambda _p: False,
    )
    with contextlib.suppress(AttributeError):
        coop_mod.CoopManager.forward_all(gerente)  # type: ignore[arg-type]
    assert lidos == []
    assert jogador.vpad.eixos == _CENTRO and not jogador.vpad.botoes


def test_o_xbox_ganha_o_leitor_do_mudo(monkeypatch: pytest.MonkeyPatch) -> None:
    """O portão `backend != "uhid"` saiu: o pad uinput do P1 tem relógio de mudo."""
    subiu: list[Any] = []

    class _Leitor:
        def __init__(self, path_provider: Any, vpad: Any, opener: Any = None) -> None:
            self.vpad = vpad

        def start(self) -> bool:
            subiu.append(self.vpad)
            return True

        def stop(self) -> None:
            return None

    monkeypatch.setattr(prr, "PhysicalReportReader", _Leitor)
    from hefesto_dualsense4unix.integrations import hidraw_broker_client

    monkeypatch.setattr(hidraw_broker_client, "make_broker_opener", lambda _d: None)
    pad = _PadDoXbox(1)
    daemon = SimpleNamespace(
        _motion_reader=None,
        controller=SimpleNamespace(hidraw_path=lambda: "/dev/hidraw-de-mentira"),
    )
    gamepad_mod.start_motion_reader(daemon, pad)
    assert subiu == [pad]
    assert daemon._motion_reader is not None
