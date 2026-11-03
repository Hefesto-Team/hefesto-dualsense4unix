"""O motor do jogo que caiu se solta com a Steam aberta — O-MOTOR-DO-JOGO-QUE-CAIU-SE-SOLTA.

Medido em 03/11/2026 no `/proc` da máquina, sem jogo aberto: a Steam segura o `hidraw` do pad
virtual Edge e o `cosmic-osk` segura o `event` dele. A consulta «alguém lê o nó?» respondia
«vivo» sempre, e o motor de um jogo que caiu ficava ligado até o pad ser recriado. No Xbox, o
efeito de duração 0 era cortado aos 30 s com o jogo vivo.

A régua: com a Steam e o teclado da tela segurando os nós, o jogo que morre solta o motor em
duas consultas, de P1 a P4, no DualSense e no Edge, pelo uhid e pelo gadget, e no Xbox pelo
uinput; o jogo vivo com a Steam ao lado segura o motor por 60 s; o motor que só a Steam
segurou (o Steam Input) fica com a Steam, que manda a própria parada. O `/proc` é uma árvore de
mentira com `comm` e `cmdline`, e a consulta é a do produto.
"""

from __future__ import annotations

import contextlib
import os
import struct
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
STEAM, OSK = 900, 901
JOGOS = {1: "winedevice.exe", 2: "Sackboy.exe", 3: "game.x86_64", 4: "wine64-preloader"}


class _Relogio:
    def __init__(self) -> None:
        self.agora = 5000.0

    def __call__(self) -> float:
        return self.agora


class _Diario:
    def __init__(self) -> None:
        self.linhas: list[tuple[str, dict[str, Any]]] = []

    def __getattr__(self, _nivel: str) -> Any:
        def anotar(evento: str, **campos: Any) -> None:
            self.linhas.append((evento, campos))
        return anotar

    def de(self, evento: str) -> list[dict[str, Any]]:
        return [campos for nome, campos in self.linhas if nome == evento]


class _ProcDeMentira:
    """Um `/proc` com `fd`, `stat`, `comm` e `cmdline`, e um `/dev` com os nós de cada pad."""

    def __init__(self, raiz: Path) -> None:
        self.raiz = raiz / "proc"
        self.raiz.mkdir()
        self.dev = raiz / "dev"
        self.dev.mkdir()

    def nos(self, player: int) -> list[str]:
        caminhos = [self.dev / f"hidraw{40 + player}", self.dev / f"event{20 + player}"]
        for caminho in caminhos:
            caminho.touch()
        return [str(caminho) for caminho in caminhos]

    def processo(self, pid: int, nome: str, cmdline: str, nos: list[str]) -> None:
        pasta = self.raiz / str(pid)
        fd = pasta / "fd"
        fd.mkdir(parents=True, exist_ok=True)
        inicio = 3 + len(list(fd.iterdir()))
        for indice, no in enumerate(nos, start=inicio):
            (fd / str(indice)).symlink_to(no)
        (pasta / "stat").write_text(f"{pid} ({nome}) S 1 {pid} 0\n")
        (pasta / "comm").write_text(nome + "\n")
        (pasta / "cmdline").write_bytes(cmdline.replace(" ", "\0").encode() + b"\0")

    def morre(self, pid: int) -> None:
        for link in (self.raiz / str(pid) / "fd").iterdir():
            link.unlink()
        (self.raiz / str(pid) / "stat").unlink()

    def steam_e_teclado(self, nos: list[str]) -> None:
        hidraws = [no for no in nos if "hidraw" in no]
        events = [no for no in nos if "event" in no]
        self.processo(STEAM, "steam", "/home/u/.steam/steam/ubuntu12_32/steam -silent", hidraws)
        self.processo(OSK, "cosmic-osk", "/usr/bin/cosmic-osk", events)


@pytest.fixture
def relogio() -> _Relogio:
    return _Relogio()


@pytest.fixture
def diario(monkeypatch: pytest.MonkeyPatch) -> _Diario:
    registro = _Diario()
    monkeypatch.setattr(uhid, "logger", registro)
    return registro


@pytest.fixture
def proc(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> _ProcDeMentira:
    arvore = _ProcDeMentira(tmp_path)
    monkeypatch.setattr(uhid, "RAIZ_DO_PROC", str(arvore.raiz))
    monkeypatch.setattr(uhid, "_nos_do_pad", lambda pad: arvore.nos(pad.player))
    return arvore


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
    """Quatro pads de um caminho, cada um com o seu `pipe` e o seu motor, com a hora da escrita."""

    def __init__(self, caminho: str, modo: int, relogio: _Relogio) -> None:
        self.caminho = caminho
        self.relogio = relogio
        self.pads: list[uhid.UhidDualSense] = []
        self.motores: dict[int, list[tuple[float, tuple[int, int]]]] = {}
        self._escritas: dict[int, int] = {}
        self._fds: list[int] = []
        for player in (1, 2, 3, 4):
            pad = uhid.UhidDualSense(
                player=player, identity=f"aa:bb:cc:00:00:0{player}", product=modo,
                blueprint=canonical_blueprint(), time_fn=relogio, sleep_fn=lambda _s: None,
            )
            motor: list[tuple[float, tuple[int, int]]] = []
            pad.rumble_sink = lambda w, s, motor=motor: motor.append((relogio.agora, (w, s)))
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

    def pedidos(self, player: int) -> list[tuple[int, int]]:
        return [pedido for _hora, pedido in self.motores[player]]

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

    def passar(self, segundos: float) -> None:
        fim = self.relogio.agora + segundos
        while self.relogio.agora < fim:
            self.relogio.agora += 0.5
            for pad in self.pads:
                self.bombear(pad)

    def fechar(self) -> None:
        for pad in self.pads:
            pad._fd = None
            pad._gadget = None
        for fd in self._fds:
            with contextlib.suppress(OSError):
                os.close(fd)


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


def _a_mesa_com_a_steam_e_os_jogos(mesa: _Mesa, proc: _ProcDeMentira) -> None:
    todos = [no for pad in mesa.pads for no in proc.nos(pad.player)]
    proc.steam_e_teclado(todos)
    for pad in mesa.pads:
        proc.processo(100 + pad.player, JOGOS[pad.player], f"C:\\jogo\\{JOGOS[pad.player]}",
                      proc.nos(pad.player))
        mesa.o_jogo_vibra(pad, *PEDIDOS[pad.player])


@MODOS
@CAMINHOS
def test_o_jogo_que_cai_com_a_steam_e_o_teclado_da_tela_abertos_solta_em_duas_consultas(
    mesa_de: Any, proc: _ProcDeMentira, relogio: _Relogio, diario: _Diario,
    caminho: str, modo: int,
) -> None:
    mesa = mesa_de(caminho, modo)
    _a_mesa_com_a_steam_e_os_jogos(mesa, proc)
    mesa.passar(6.0)
    for morto in mesa.pads:
        proc.morre(100 + morto.player)
        morreu_em = relogio.agora
        mesa.passar(2 * uhid._CONFERE_O_LEITOR_S + 1.0)
        assert mesa.pedidos(morto.player) == [PEDIDOS[morto.player], (0, 0)], (
            f"P{morto.player}: o jogo caiu com a Steam e o teclado da tela abertos e o motor "
            f"recebeu {mesa.pedidos(morto.player)}"
        )
        solto_em = mesa.motores[morto.player][-1][0]
        assert solto_em - morreu_em <= 2 * uhid._CONFERE_O_LEITOR_S + 0.5
    soltos = diario.de("uhid_rumble_do_jogo_morto")
    assert [linha["player"] for linha in soltos] == [1, 2, 3, 4]
    for linha in soltos:
        assert "só quem não é jogo lê" in linha["motivo"], linha
        assert "steam" in linha["motivo"] and "cosmic-osk" in linha["motivo"], linha


@MODOS
@CAMINHOS
def test_o_jogo_vivo_com_a_steam_ao_lado_segura_o_motor_por_60_s(
    mesa_de: Any, proc: _ProcDeMentira, diario: _Diario, caminho: str, modo: int,
) -> None:
    mesa = mesa_de(caminho, modo)
    _a_mesa_com_a_steam_e_os_jogos(mesa, proc)
    mesa.passar(60.0)
    for pad in mesa.pads:
        assert mesa.pedidos(pad.player) == [PEDIDOS[pad.player]], (
            f"P{pad.player}: {mesa.pedidos(pad.player)}"
        )
        assert pad._jogo_no_motor
    assert not diario.de("uhid_rumble_do_jogo_morto")


@CAMINHOS
def test_o_motor_que_so_a_steam_segurou_fica_com_a_steam(
    mesa_de: Any, proc: _ProcDeMentira, diario: _Diario, caminho: str,
) -> None:
    """Steam Input: o jogo lê o pad da Steam, e a Steam escreve o motor e manda a parada."""
    mesa = mesa_de(caminho, EDGE)
    proc.steam_e_teclado([no for pad in mesa.pads for no in proc.nos(pad.player)])
    for pad in mesa.pads:
        mesa.o_jogo_vibra(pad, *PEDIDOS[pad.player])
    mesa.passar(60.0)
    for pad in mesa.pads:
        assert mesa.pedidos(pad.player) == [PEDIDOS[pad.player]]
        assert not pad._jogo_no_motor
    proc.morre(STEAM)
    proc.morre(OSK)
    mesa.passar(2 * uhid._CONFERE_O_LEITOR_S + 1.0)
    for pad in mesa.pads:
        assert mesa.pedidos(pad.player) == [PEDIDOS[pad.player], (0, 0)]
    assert all("nenhum leitor" in linha["motivo"]
               for linha in diario.de("uhid_rumble_do_jogo_morto"))


def test_a_consulta_separa_o_jogo_de_quem_le_todo_pad(proc: _ProcDeMentira) -> None:
    nos = proc.nos(1)
    proc.steam_e_teclado(nos)
    raiz = str(proc.raiz)
    vivo, motivo = uhid.o_jogo_le_os_nos(nos, raiz_proc=raiz, meu_pid=1)
    assert vivo is False
    assert motivo.startswith("só quem não é jogo lê: "), motivo
    assert f"steam:{STEAM}" in motivo and f"cosmic-osk:{OSK}" in motivo, motivo
    assert uhid.o_jogo_le_os_nos(nos, raiz_proc=raiz, meu_pid=1, autor_fora_do_jogo=True)[0] \
        is None
    proc.processo(77, "python3", "python3 -m hefesto_dualsense4unix.daemon", nos)
    assert uhid.o_jogo_le_os_nos(nos, raiz_proc=raiz, meu_pid=1)[0] is False, (
        "o próprio Hefesto não é jogo"
    )
    proc.processo(101, "winedevice.exe", "C:\\windows\\system32\\winedevice.exe", nos)
    assert uhid.o_jogo_le_os_nos(nos, raiz_proc=raiz, meu_pid=1) == (True, "o pid 101 lê (S)")


class _Efeito:
    def __init__(self, ecodes: Any, weak: int, strong: int) -> None:
        self.id = 0
        self.type = ecodes.FF_RUMBLE
        self.ff_replay = type("R", (), {"length": 0, "delay": 0})()
        self.u = type("U", (), {"ff_rumble_effect": type(
            "F", (), {"weak_magnitude": weak << 8, "strong_magnitude": strong << 8})()})()


@pytest.fixture
def xbox(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, proc: _ProcDeMentira, relogio: _Relogio,
) -> Iterator[tuple[list[Any], dict[int, list[tuple[int, int]]], _Diario]]:
    """Quatro pads Xbox do uinput com um efeito de duração 0, e o `inputN` de cada um."""
    from evdev import ecodes

    from hefesto_dualsense4unix.integrations import no_do_vpad
    from hefesto_dualsense4unix.integrations import uinput_gamepad as uinput

    classe = tmp_path / "sys-class-input"
    monkeypatch.setattr(no_do_vpad, "RAIZ_CLASS_INPUT", str(classe))
    monkeypatch.setattr(no_do_vpad, "RAIZ_DEV_INPUT", str(proc.dev))
    registro = _Diario()
    monkeypatch.setattr(uinput, "logger", registro)
    pads: list[Any] = []
    motores: dict[int, list[tuple[int, int]]] = {}
    todos: list[str] = []
    for player in (1, 2, 3, 4):
        (classe / f"input{70 + player}" / f"event{20 + player}").mkdir(parents=True)
        (classe / f"input{70 + player}" / f"js{player}").mkdir()
        (proc.dev / f"js{player}").touch()
        (proc.dev / f"event{20 + player}").touch()
        pad = uinput.UinputGamepad.for_flavor("xbox")
        motor: list[tuple[int, int]] = []
        pad.rumble_sink = lambda w, s, motor=motor: motor.append((w, s))
        pad.time_fn = relogio
        pad._ff_supported = True
        pad._ecodes = ecodes
        pad._sysname = f"input{70 + player}"
        nos = uinput._nos_do_uinput(pad)
        assert nos == [str(proc.dev / f"event{20 + player}"), str(proc.dev / f"js{player}")]
        todos += nos
        pads.append(pad)
        motores[player] = motor
    proc.processo(STEAM, "steam", "/home/u/.steam/steam/ubuntu12_32/steam", todos)
    proc.processo(OSK, "cosmic-osk", "/usr/bin/cosmic-osk", todos)
    for player, pad in enumerate(pads, start=1):
        proc.processo(100 + player, JOGOS[player], f"C:\\jogo\\{JOGOS[player]}",
                      uinput._nos_do_uinput(pad))
        pad._ff_effects[0] = pad._parse_ff_effect(_Efeito(ecodes, *PEDIDOS[player]))
        pad._start_ff_effect(0, repeats=1)
        _refrescar(pad)
    yield pads, motores, registro


def _refrescar(pad: Any) -> None:
    pad._refresh_ff()
    consulta = pad._leitor_consulta
    if consulta is not None:
        consulta.join(5.0)


def _passar(pads: list[Any], relogio: _Relogio, segundos: float) -> None:
    fim = relogio.agora + segundos
    while relogio.agora < fim:
        relogio.agora += 0.5
        for pad in pads:
            _refrescar(pad)


def test_no_xbox_o_efeito_de_duracao_zero_dura_60_s_com_o_jogo_vivo(
    xbox: Any, relogio: _Relogio,
) -> None:
    pads, motores, registro = xbox
    _passar(pads, relogio, 60.0)
    for player, pad in enumerate(pads, start=1):
        assert motores[player] == [PEDIDOS[player]], (
            f"P{player}: o jogo vivo segurava o efeito de duração 0 e o motor recebeu "
            f"{motores[player]}"
        )
        assert pad._jogo_no_motor
    assert not registro.de("uinput_rumble_do_jogo_morto")


def test_no_xbox_o_jogo_que_cai_com_a_steam_aberta_solta_em_duas_consultas(
    xbox: Any, proc: _ProcDeMentira, relogio: _Relogio,
) -> None:
    from hefesto_dualsense4unix.integrations import uinput_gamepad as uinput

    pads, motores, registro = xbox
    _passar(pads, relogio, 6.0)
    for player in range(1, len(pads) + 1):
        proc.morre(100 + player)
        _passar(pads, relogio, 2 * uinput._CONFERE_O_LEITOR_S + 1.0)
        assert motores[player] == [PEDIDOS[player], (0, 0)], f"P{player}: {motores[player]}"
    soltos = registro.de("uinput_rumble_do_jogo_morto")
    assert len(soltos) == 4
    assert all("só quem não é jogo lê" in linha["motivo"] for linha in soltos), soltos
