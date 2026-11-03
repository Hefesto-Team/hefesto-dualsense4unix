"""O rumble que o jogo segura não expira em três segundos — O-RUMBLE-QUE-O-JOGO-SEGURA.

Medido em 02/11/2026 no diário: sete `uhid_rumble_preso_expirado` em uma hora de jogo, todos
aos 3,0 s de silêncio, em P1, P2 e P3, seis deles com o motor fraco sustentado `(40, 0)`. O
vpad cortava a vibração que o jogo vivo segurava sem repetir o pedido.

A régua: com um leitor vivo, o motor dura 60 s de silêncio em P1 a P4 juntos, no DualSense e
no Edge, pelo uhid e pelo gadget; sem leitor (nenhum, só um zumbi ou só um parado) por duas
consultas, o físico recebe `(0, 0)` uma vez, com o motivo no diário; o `UHID_CLOSE` segue
soltando na hora; e a consulta que dorme não segura a bomba. No Xbox, o pad uinput mantém o
pedido pelo tempo que o jogo declarou. Os pads leem e escrevem num `pipe`, e o `/proc` da
consulta é uma árvore de mentira.
"""

from __future__ import annotations

import contextlib
import os
import struct
import threading
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.integrations import uhid_gamepad as uhid
from hefesto_dualsense4unix.integrations.uhid_blueprint import canonical_blueprint

DUALSENSE, EDGE = 0x0CE6, 0x0DF2
PEDIDOS = {1: (40, 0), 2: (204, 127), 3: (40, 0), 4: (0, 90)}
MODOS = pytest.mark.parametrize("modo", [DUALSENSE, EDGE], ids=["dualsense", "edge"])
CAMINHOS = pytest.mark.parametrize("caminho", ["uhid", "gadget"])


class _Relogio:
    def __init__(self) -> None:
        self.agora = 5000.0

    def __call__(self) -> float:
        return self.agora


class _Diario:
    """O `logger` do módulo: guarda o evento e os campos de cada linha."""

    def __init__(self) -> None:
        self.linhas: list[tuple[str, dict[str, Any]]] = []

    def __getattr__(self, _nivel: str) -> Any:
        def anotar(evento: str, **campos: Any) -> None:
            self.linhas.append((evento, campos))
        return anotar

    def de(self, evento: str) -> list[dict[str, Any]]:
        return [campos for nome, campos in self.linhas if nome == evento]


def _relatorio_de_vibracao(weak: int, strong: int) -> bytes:
    corpo = bytearray(48)
    corpo[uhid._VALID_FLAG0_OFFSET] = uhid._VIBRATION_FLAGS
    corpo[uhid._RUMBLE_WEAK_OFFSET] = weak
    corpo[uhid._RUMBLE_STRONG_OFFSET] = strong
    return bytes([uhid._OUTPUT_REPORT_USB]) + bytes(corpo)


def _evento_uhid(report: bytes) -> bytes:
    return (
        struct.pack("<I", uhid.UHID_OUTPUT)
        + report.ljust(uhid.HID_MAX_DESCRIPTOR_SIZE, b"\0")
        + struct.pack("<HB", len(report), 1)
    )


class _Mesa:
    """Quatro pads de um caminho, cada um com o seu `pipe` e o seu motor."""

    def __init__(self, caminho: str, modo: int, relogio: _Relogio) -> None:
        self.caminho = caminho
        self.pads: list[uhid.UhidDualSense] = []
        self.motores: dict[int, list[tuple[int, int]]] = {}
        self._escritas: dict[int, int] = {}
        self._fds: list[int] = []
        for player in (1, 2, 3, 4):
            pad = uhid.UhidDualSense(
                player=player, identity=f"aa:bb:cc:00:00:0{player}", product=modo,
                blueprint=canonical_blueprint(), time_fn=relogio, sleep_fn=lambda _s: None,
            )
            motor: list[tuple[int, int]] = []
            pad.rumble_sink = lambda w, s, motor=motor: motor.append((w, s))
            leitura, escrita = os.pipe()
            os.set_blocking(leitura, False)
            self._fds += [leitura, escrita]
            pad._fd = leitura
            pad._started = True
            if caminho == "gadget":
                pad._gadget = uhid._GadgetDoPad(
                    cliente=None, fd=leitura, gadget=f"hefesto-pad-{player}",
                    serial=f"serial-{player}", hidraw=f"hidraw{40 + player}",
                    interface="1-1:1.0",
                )
            self.pads.append(pad)
            self.motores[player] = motor
            self._escritas[player] = escrita

    def o_jogo_vibra(self, pad: uhid.UhidDualSense, weak: int, strong: int) -> None:
        report = _relatorio_de_vibracao(weak, strong)
        os.write(self._escritas[pad.player],
                 report if self.caminho == "gadget" else _evento_uhid(report))
        self.bombear(pad)

    def bombear(self, pad: uhid.UhidDualSense) -> None:
        pad.pump_ff()
        consulta = pad._leitor_consulta
        if consulta is not None:
            consulta.join(5.0)

    def fechar(self) -> None:
        for pad in self.pads:
            pad._fd = None
            pad._gadget = None
        for fd in self._fds:
            with contextlib.suppress(OSError):
                os.close(fd)


@pytest.fixture
def relogio() -> _Relogio:
    return _Relogio()


@pytest.fixture
def diario(monkeypatch: pytest.MonkeyPatch) -> _Diario:
    registro = _Diario()
    monkeypatch.setattr(uhid, "logger", registro)
    return registro


@pytest.fixture
def mesa_de(monkeypatch: pytest.MonkeyPatch, relogio: _Relogio) -> Iterator[Any]:
    monkeypatch.setattr(uhid, "_vigiar_a_enumeracao", lambda _pad: None)
    mesas: list[_Mesa] = []

    def montar(caminho: str, modo: int) -> _Mesa:
        mesa = _Mesa(caminho, modo, relogio)
        mesas.append(mesa)
        return mesa

    yield montar
    for mesa in mesas:
        mesa.fechar()


class _ProcDeMentira:
    """Um `/proc` com um jogo por pad: o descritor no nó dele e o estado no `stat`."""

    def __init__(self, raiz: Path) -> None:
        self.raiz = raiz / "proc"
        self.raiz.mkdir()
        self.dev = raiz / "dev"
        self.dev.mkdir()

    def no(self, player: int) -> str:
        caminho = self.dev / f"hidraw{40 + player}"
        caminho.touch()
        return str(caminho)

    def jogo(self, pid: int, nos: list[str], estado: str = "S") -> None:
        fd = self.raiz / str(pid) / "fd"
        fd.mkdir(parents=True, exist_ok=True)
        for indice, no in enumerate(nos, start=3):
            (fd / str(indice)).symlink_to(no)
        self.estado(pid, estado)

    def estado(self, pid: int, letra: str) -> None:
        (self.raiz / str(pid) / "stat").write_text(f"{pid} (jogo (x)) {letra} 1 {pid} 0\n")

    def larga(self, pid: int) -> None:
        for link in (self.raiz / str(pid) / "fd").iterdir():
            link.unlink()


@pytest.fixture
def proc(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> _ProcDeMentira:
    arvore = _ProcDeMentira(tmp_path)
    monkeypatch.setattr(uhid, "RAIZ_DO_PROC", str(arvore.raiz))
    monkeypatch.setattr(
        uhid, "CONSULTAR_O_LEITOR",
        lambda pad: uhid.o_jogo_le_os_nos([arvore.no(pad.player)], meu_pid=1),
    )
    return arvore


@MODOS
@CAMINHOS
def test_o_motor_que_o_jogo_segura_dura_enquanto_o_jogo_le(
    mesa_de: Any, proc: _ProcDeMentira, relogio: _Relogio, diario: _Diario,
    caminho: str, modo: int,
) -> None:
    """`D-0311-O-TEMPO-NAO-SOLTA-O-MOTOR-QUE-O-JOGO-PEDIU`: o tempo não solta o motor."""
    mesa = mesa_de(caminho, modo)
    for pad in mesa.pads:
        proc.jogo(100 + pad.player, [proc.no(pad.player)])
        mesa.o_jogo_vibra(pad, *PEDIDOS[pad.player])
    for _tique in range(120):
        relogio.agora += 0.5
        for pad in mesa.pads:
            mesa.bombear(pad)
    for pad in mesa.pads:
        assert mesa.motores[pad.player] == [PEDIDOS[pad.player]], (
            f"P{pad.player}: o jogo vivo segurava {PEDIDOS[pad.player]} e o motor recebeu "
            f"{mesa.motores[pad.player]}"
        )
        assert pad._leitor_conferido_em is not None
    assert not diario.de("uhid_rumble_preso_expirado")
    assert not diario.de("uhid_rumble_do_jogo_morto")


@pytest.mark.parametrize("fim", ["fecha_o_no", "zumbi", "parado"])
@MODOS
@CAMINHOS
def test_o_jogo_morto_solta_o_motor_uma_vez_com_o_motivo(
    mesa_de: Any, proc: _ProcDeMentira, relogio: _Relogio, diario: _Diario,
    caminho: str, modo: int, fim: str,
) -> None:
    mesa = mesa_de(caminho, modo)
    for pad in mesa.pads:
        proc.jogo(100 + pad.player, [proc.no(pad.player)])
        mesa.o_jogo_vibra(pad, *PEDIDOS[pad.player])
    morto = mesa.pads[1]
    if fim == "fecha_o_no":
        proc.larga(100 + morto.player)
    else:
        proc.estado(100 + morto.player, "Z" if fim == "zumbi" else "T")
    for _tique in range(40):
        relogio.agora += 0.5
        for pad in mesa.pads:
            mesa.bombear(pad)
    assert mesa.motores[morto.player] == [PEDIDOS[morto.player], (0, 0)]
    for pad in mesa.pads:
        if pad is not morto:
            assert mesa.motores[pad.player] == [PEDIDOS[pad.player]]
    soltos = diario.de("uhid_rumble_do_jogo_morto")
    assert [linha["player"] for linha in soltos] == [morto.player]
    esperado = "nenhum leitor" if fim == "fecha_o_no" else "parados ou zumbis"
    assert esperado in soltos[0]["motivo"]


@MODOS
@CAMINHOS
def test_uma_consulta_sem_leitor_entre_duas_com_leitor_nao_solta(
    mesa_de: Any, proc: _ProcDeMentira, relogio: _Relogio, caminho: str, modo: int,
) -> None:
    """O jogo que troca de descritor some numa consulta e volta na seguinte."""
    mesa = mesa_de(caminho, modo)
    pad = mesa.pads[0]
    proc.jogo(101, [proc.no(1)])
    mesa.o_jogo_vibra(pad, 40, 0)
    for rodada in range(10):
        if rodada % 2:
            proc.jogo(101, [proc.no(1)])
        else:
            proc.larga(101)
        relogio.agora += uhid._CONFERE_O_LEITOR_S + 0.1
        mesa.bombear(pad)
    assert mesa.motores[1] == [(40, 0)]


@CAMINHOS
def test_o_uhid_close_segue_soltando_na_hora(
    mesa_de: Any, proc: _ProcDeMentira, caminho: str,
) -> None:
    mesa = mesa_de(caminho, DUALSENSE)
    for pad in mesa.pads:
        proc.jogo(100 + pad.player, [proc.no(pad.player)])
        mesa.o_jogo_vibra(pad, *PEDIDOS[pad.player])
        pad._handle_event(struct.pack("<I", uhid.UHID_CLOSE))
        assert mesa.motores[pad.player] == [PEDIDOS[pad.player], (0, 0)]


@CAMINHOS
def test_a_bomba_nao_espera_a_consulta(
    mesa_de: Any, relogio: _Relogio, monkeypatch: pytest.MonkeyPatch, caminho: str,
) -> None:
    solta = threading.Event()

    def dorme(_pad: uhid.UhidDualSense) -> tuple[bool | None, str]:
        solta.wait(2.0)
        return True, "dublê que dorme"

    monkeypatch.setattr(uhid, "CONSULTAR_O_LEITOR", dorme)
    mesa = mesa_de(caminho, EDGE)
    passes: list[float] = []
    try:
        for pad in mesa.pads:
            os.write(mesa._escritas[pad.player], _relatorio_de_vibracao(40, 0)
                     if caminho == "gadget" else _evento_uhid(_relatorio_de_vibracao(40, 0)))
        for _tique in range(20):
            relogio.agora += uhid._CONFERE_O_LEITOR_S + 0.1
            for pad in mesa.pads:
                inicio = time.perf_counter()
                pad.pump_ff()
                passes.append(time.perf_counter() - inicio)
        assert all(pad._leitor_consulta is not None and pad._leitor_consulta.is_alive()
                   for pad in mesa.pads)
    finally:
        solta.set()
        for pad in mesa.pads:
            if pad._leitor_consulta is not None:
                pad._leitor_consulta.join(5.0)
    assert max(passes) < 0.010, f"o passe mais lento da bomba levou {max(passes) * 1e3:.1f} ms"
    for pad in mesa.pads:
        assert mesa.motores[pad.player] == [(40, 0)]


def test_a_consulta_le_o_proc_sem_abrir_nada(tmp_path: Path) -> None:
    arvore = _ProcDeMentira(tmp_path)
    no = arvore.no(1)
    assert uhid.o_jogo_le_os_nos([], raiz_proc=str(arvore.raiz))[0] is None
    assert uhid.o_jogo_le_os_nos([no], raiz_proc=str(arvore.raiz), meu_pid=1) == (
        False, "nenhum leitor"
    )
    arvore.jogo(7, [no])
    assert uhid.o_jogo_le_os_nos([no], raiz_proc=str(arvore.raiz), meu_pid=7)[0] is False, (
        "o próprio daemon não conta como leitor"
    )
    assert uhid.o_jogo_le_os_nos([no], raiz_proc=str(arvore.raiz), meu_pid=1)[0] is True
    arvore.estado(7, "X")
    assert uhid.o_jogo_le_os_nos([no], raiz_proc=str(arvore.raiz), meu_pid=1)[0] is False
    arvore.estado(7, "D")
    assert uhid.o_jogo_le_os_nos([no], raiz_proc=str(arvore.raiz), meu_pid=1)[0] is True
    assert uhid.o_jogo_le_os_nos(
        [no], raiz_proc=str(arvore.raiz), meu_pid=1, orcamento_s=-1.0
    ) == (None, "a varredura estourou o orçamento")
    (arvore.raiz / "9").mkdir()
    arvore.larga(7)
    assert uhid.o_jogo_le_os_nos([no], raiz_proc=str(arvore.raiz), meu_pid=1) == (
        False, "nenhum leitor (1 processos sem leitura)"
    ), "o processo que não se lê vai ao motivo, e não some calado"


def test_no_modo_xbox_o_pad_uinput_mantem_o_pedido_pelo_tempo_do_jogo() -> None:
    from evdev import ecodes

    from hefesto_dualsense4unix.integrations.uinput_gamepad import UinputGamepad

    class _Efeito:
        def __init__(self) -> None:
            self.id = 0
            self.type = ecodes.FF_RUMBLE
            self.ff_replay = type("R", (), {"length": 60_000, "delay": 0})()
            self.u = type("U", (), {"ff_rumble_effect": type(
                "F", (), {"weak_magnitude": 40 << 8, "strong_magnitude": 0})()})()

    relogio = _Relogio()
    for player in (1, 2, 3, 4):
        pad = UinputGamepad.for_flavor("xbox")
        motor: list[tuple[int, int]] = []
        pad.rumble_sink = lambda w, s, motor=motor: motor.append((w, s))
        pad.time_fn = relogio
        pad._ff_supported = True
        pad._ecodes = ecodes
        pad._ff_effects[0] = pad._parse_ff_effect(_Efeito())
        pad._start_ff_effect(0, repeats=1)
        pad._refresh_ff()
        inicio = relogio.agora
        while relogio.agora < inicio + 59.5:
            relogio.agora += 0.5
            pad._refresh_ff()
        assert motor == [(40, 0)], f"P{player}: {motor}"
        relogio.agora = inicio + 60.5
        pad._refresh_ff()
        assert motor == [(40, 0), (0, 0)]
        relogio.agora = inicio


@pytest.mark.parametrize("duvida", ["nao_sei", "a_consulta_cai"])
@MODOS
@CAMINHOS
def test_o_nao_sei_mantem_o_motor(
    mesa_de: Any, relogio: _Relogio, diario: _Diario, monkeypatch: pytest.MonkeyPatch,
    caminho: str, modo: int, duvida: str,
) -> None:
    """O pad sem nó, o `/proc` ilegível, o orçamento estourado e a consulta que cai não soltam."""

    def consulta(_pad: uhid.UhidDualSense) -> tuple[bool | None, str]:
        if duvida == "a_consulta_cai":
            raise OSError("o /proc sumiu")
        return None, "a varredura estourou o orçamento"

    monkeypatch.setattr(uhid, "CONSULTAR_O_LEITOR", consulta)
    mesa = mesa_de(caminho, modo)
    for pad in mesa.pads:
        mesa.o_jogo_vibra(pad, *PEDIDOS[pad.player])
    for _tique in range(120):
        relogio.agora += 0.5
        for pad in mesa.pads:
            mesa.bombear(pad)
    for pad in mesa.pads:
        assert mesa.motores[pad.player] == [PEDIDOS[pad.player]], (
            f"P{pad.player}: o «não sei» cortou o motor: {mesa.motores[pad.player]}"
        )
    assert not diario.de("uhid_rumble_do_jogo_morto")


@CAMINHOS
def test_o_event_do_pad_conta_como_leitor(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, relogio: _Relogio, caminho: str,
) -> None:
    """O jogo que lê o pad só pelo evdev (o FF do `event`) segura o motor como o do `hidraw`."""
    from hefesto_dualsense4unix.integrations import no_do_vpad

    dev, dev_input = tmp_path / "dev", tmp_path / "dev-input"
    classe = tmp_path / "sys" / "class"
    for pasta in (dev, dev_input, classe / "input"):
        pasta.mkdir(parents=True)
    (dev / "hidraw41").touch()
    (dev_input / "event19").touch()
    monkeypatch.setattr(no_do_vpad, "RAIZ_CLASS_INPUT", str(classe / "input"))
    monkeypatch.setattr(no_do_vpad, "RAIZ_DEV_INPUT", str(dev_input))
    monkeypatch.setattr(no_do_vpad, "RAIZ_DEV", str(dev))
    pad = uhid.UhidDualSense(
        player=1, identity="aa:bb:cc:00:00:01", product=EDGE,
        blueprint=canonical_blueprint(), time_fn=relogio, sleep_fn=lambda _s: None,
    )
    if caminho == "gadget":
        (classe / "hidraw" / "hidraw41" / "device" / "input" / "input9" / "event19").mkdir(
            parents=True
        )
        pad._gadget = uhid._GadgetDoPad(
            cliente=None, fd=-1, gadget="hefesto-pad-1", serial="serial-1",
            hidraw="hidraw41", interface="1-1:1.0",
        )
    else:
        monkeypatch.setattr(
            no_do_vpad, "resolver_no_do_vpad",
            lambda **_k: {"hidraw": str(dev / "hidraw41"), "evdev": str(dev_input / "event19")},
        )
    nos = uhid._nos_do_pad(pad)
    pad._gadget = None
    assert str(dev_input / "event19") in nos, nos
    (tmp_path / "p").mkdir()
    arvore = _ProcDeMentira(tmp_path / "p")
    arvore.jogo(101, [str(dev_input / "event19")])
    assert uhid.o_jogo_le_os_nos(nos, raiz_proc=str(arvore.raiz), meu_pid=1)[0] is True
