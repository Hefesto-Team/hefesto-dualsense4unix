"""A luz que o jogo pinta chega a todo controle (A-LUZ-QUE-O-JOGO-PINTA-CHEGA-A-TODO-CONTROLE-01).

D-0211-A-LUZ-DE-JOGADOR-E-DO-JOGO (03/11/2026, por delegação, a validar; caducou a
D-2309-O-HEFESTO-MANDA-NO-NUMERO): o número e a cor que o jogo escreve no pad virtual são saída do
jogo como qualquer outra. Com a autoridade no jogo, chegam ao físico do jogador; fora da
autoridade, ficam retidos; no fim da sessão, o número e a cor do Hefesto voltam. No controle de fora
(Pro Controller, 8BitDo), as luzes mostram o número do jogo e voltam ao retrato de antes.

O caminho inteiro roda: o report 0x02 entra no pad (uhid ou gadget), a réplica sai pelos ralos do
P1 ou do co-op e o backend escreve num nó de mentira; o controle de fora escreve num ``sysfs`` de
mentira. O pad Xbox não tem canal de luz do jogo.
"""
from __future__ import annotations

import dataclasses
import os
import select
import struct
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from pydualsense.pydualsense import DSAudio, DSLight, DSTrigger

from hefesto_dualsense4unix.core import backend_pydualsense as bp
from hefesto_dualsense4unix.core import external_leds
from hefesto_dualsense4unix.core.led_control import player_led_pattern, player_slot_color
from hefesto_dualsense4unix.daemon.subsystems import gamepad as gp_mod
from hefesto_dualsense4unix.daemon.subsystems.coop import CoopManager
from hefesto_dualsense4unix.integrations import uhid_gamepad
from hefesto_dualsense4unix.integrations.uhid_gamepad import (
    _GAME_REPLICA_GRACE_S,
    _GadgetDoPad,
    UHID_CLOSE,
    UHID_OPEN,
    UHID_OUTPUT,
    UHID_START,
    HID_MAX_DESCRIPTOR_SIZE,
    UhidDualSense,
)
from hefesto_dualsense4unix.integrations.uinput_gamepad import UinputGamepad

MACS = {n: f"AA:BB:CC:00:00:0{n}" for n in (1, 2, 3, 4)}
PRODUTO = {"dualsense": 0x0CE6, "edge": 0x0DF2}
COR_DO_SDL = {1: (0, 0, 64), 2: (64, 0, 0), 3: (0, 64, 0), 4: (32, 0, 32)}

JOGADORES = (1, 2, 3, 4)
VIAS = ("cabo", "radio")
CAMINHOS = ("uhid", "gadget")
MODOS_DO_PAD = ("dualsense", "edge")


def _numero_do_jogo(player: int) -> int:
    """O jogo numera diferente do Hefesto, para que a régua veja quem venceu."""
    return player % 4 + 1


class _NoDeLed:
    """Nó sysfs falso do DualSense: grava as chamadas."""

    def __init__(self) -> None:
        self.rgb_calls: list[tuple[int, int, int]] = []
        self.player_calls: list[tuple[bool, ...]] = []

    def set_rgb(self, r: int, g: int, b: int) -> bool:
        self.rgb_calls.append((r, g, b))
        return True

    def set_players(self, bits: tuple[bool, ...]) -> bool:
        self.player_calls.append(tuple(bits))
        return True

    def invalidate_cache(self) -> None:
        return None


class _Relogio:
    def __init__(self) -> None:
        self.t = 0.0

    def __call__(self) -> float:
        return self.t


def _handle(produto: int, via: str) -> SimpleNamespace:
    handle = SimpleNamespace(
        triggerL=DSTrigger(),
        triggerR=DSTrigger(),
        light=DSLight(),
        audio=DSAudio(),
        _raw_trigger_left=None,
        _raw_trigger_right=None,
        is_edge=produto == PRODUTO["edge"],
        connected=True,
        escritos=[],
    )
    if via == "radio":
        handle.conType = SimpleNamespace(name="BT")
        handle.writeReport = handle.escritos.append
    return handle


def _mesa(
    aparelho: str, via: str, autoridade: str
) -> tuple[bp.PyDualSenseController, dict[int, _NoDeLed], dict[int, SimpleNamespace], Any]:
    """Quatro DualSense (ou Edge) na mesa, com o número e a cor do Hefesto já pintados."""
    ctl = bp.PyDualSenseController()
    nos = {n: _NoDeLed() for n in JOGADORES}
    handles = {n: _handle(PRODUTO.get(aparelho, PRODUTO["dualsense"]), via) for n in JOGADORES}
    if aparelho in PRODUTO:
        ctl._handles = {MACS[n]: handles[n] for n in JOGADORES}
        ctl._sysfs = {MACS[n]: nos[n] for n in JOGADORES}
        ctl._primary_key = MACS[1]
        for n in JOGADORES:
            uniq = MACS[n].replace(":", "").lower()
            ctl._desired_by_uniq[uniq] = bp._DesiredOutput(
                led=player_slot_color(n), player_leds=player_led_pattern(n)
            )
            ctl._desired_owner_by_uniq[uniq] = {
                "led": bp._LAYER_PROFILE,
                "player_leds": bp._LAYER_PROFILE,
            }
    sinal = SimpleNamespace(valor=autoridade)
    ctl.set_game_authority_provider(lambda: sinal.valor)
    daemon = SimpleNamespace(controller=ctl, display_authority=autoridade, sinal=sinal)
    return ctl, nos, handles, daemon


def _ralos(daemon: Any, player: int, identidade: str) -> dict[str, Any]:
    """Os ralos do produto: o do P1 mira o primário; o do co-op, a identidade do jogador."""
    if player == 1 and identidade == MACS[1]:
        return gp_mod.make_primary_replica_sinks(daemon)
    return CoopManager(daemon)._make_player_replica_sinks(identidade)


def _report_do_jogo(numero: int, cor: tuple[int, int, int]) -> bytes:
    """O report 0x02 do jogo: as luzes de jogador e a barra, com as duas bandeiras."""
    corpo = bytearray(47)
    corpo[1] = uhid_gamepad._PLAYER_INDICATOR_CONTROL_ENABLE | uhid_gamepad._LIGHTBAR_CONTROL_ENABLE
    corpo[43] = sum(1 << i for i, b in enumerate(player_led_pattern(numero)) if b)
    corpo[44:47] = bytes(cor)
    return bytes([0x02]) + bytes(corpo)


def _evento(tipo: int) -> bytes:
    return struct.pack("<I", tipo)


def _pad_em_sessao(
    daemon: Any, player: int, identidade: str, modo: str, caminho: str
) -> UhidDualSense:
    """O pad do jogador com o jogo aberto e a graça vencida, como o uhid e o gadget o deixam."""
    relogio = _Relogio()
    pad = UhidDualSense(
        player=player,
        identity=identidade,
        product=PRODUTO[modo],
        time_fn=relogio,
        sleep_fn=lambda _s: None,
        **_ralos(daemon, player, identidade),
    )
    if caminho == "gadget":
        pad._gadget = _GadgetDoPad(
            cliente=None, fd=-1, gadget="g", serial=f"hefesto-pad-{player}"
        )
    pad._handle_event(_evento(UHID_START))
    pad._handle_event(_evento(UHID_OPEN))
    relogio.t = _GAME_REPLICA_GRACE_S + 0.5
    return pad


def _o_jogo_escreve(pad: UhidDualSense, caminho: str, report: bytes) -> None:
    """O report chega como chega no produto: o evento do uhid, ou o `/dev/hidgN` do gadget."""
    if caminho == "uhid":
        evento = (
            struct.pack("<I", UHID_OUTPUT)
            + report.ljust(HID_MAX_DESCRIPTOR_SIZE, b"\0")[:HID_MAX_DESCRIPTOR_SIZE]
            + struct.pack("<HB", len(report), 1)
        )
        pad._handle_event(evento)
        return
    leitura, escrita = os.pipe()
    try:
        os.set_blocking(leitura, False)
        os.write(escrita, report)
        uhid_gamepad._drenar_o_gadget(pad, leitura, select.POLLIN)
    finally:
        os.close(leitura)
        os.close(escrita)


def _o_jogo_fecha(pad: UhidDualSense) -> None:
    pad._handle_event(_evento(UHID_CLOSE))


def _uniq(mac: str) -> str:
    return mac.replace(":", "").lower()


COMBINACOES_DUALSENSE = [
    (player, aparelho, modo, via, caminho)
    for player in JOGADORES
    for aparelho in ("dualsense", "edge")
    for modo in MODOS_DO_PAD
    for via in VIAS
    for caminho in CAMINHOS
]


@pytest.mark.parametrize(("player", "aparelho", "modo", "via", "caminho"), COMBINACOES_DUALSENSE)
def test_com_o_jogo_na_autoridade_o_numero_e_a_cor_chegam_e_voltam(
    player: int, aparelho: str, modo: str, via: str, caminho: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """D-0211-A-LUZ-DE-JOGADOR-E-DO-JOGO.

    MORDIDA: devolver o veto do número na entrada e a luz de jogador do jogo não chega."""
    procurados: list[str | None] = []
    monkeypatch.setattr(external_leds, "hidraw_do_uniq", lambda uniq: procurados.append(uniq))
    ctl, nos, handles, daemon = _mesa(aparelho, via, "game")
    pad = _pad_em_sessao(daemon, player, MACS[player], modo, caminho)
    numero = _numero_do_jogo(player)
    cor = COR_DO_SDL[numero]

    _o_jogo_escreve(pad, caminho, _report_do_jogo(numero, cor))

    assert procurados == [], "o DualSense foi procurado entre os controles de fora"
    no = nos[player]
    assert player_led_pattern(numero) in no.player_calls
    assert cor in no.rgb_calls
    with ctl._io_lock:
        merged = ctl._merged_desired_for_key(MACS[player])
    assert (merged.player_leds, merged.led) == (player_led_pattern(numero), cor)
    if via == "radio":
        assert handles[player].escritos, "pelo rádio o 0x31 da luz não saiu"
    for outro in JOGADORES:
        if outro != player:
            assert nos[outro].player_calls == []
            assert nos[outro].rgb_calls == []

    _o_jogo_fecha(pad)

    with ctl._io_lock:
        depois = ctl._merged_desired_for_key(MACS[player])
    assert depois.player_leds == player_led_pattern(player)
    assert depois.led == player_slot_color(player)
    assert no.player_calls[-1] == player_led_pattern(player)
    assert no.rgb_calls[-1] == player_slot_color(player)


@pytest.mark.parametrize(("player", "aparelho", "modo", "via", "caminho"), COMBINACOES_DUALSENSE)
def test_sem_a_autoridade_o_que_o_jogo_pinta_fica_retido(
    player: int, aparelho: str, modo: str, via: str, caminho: str
) -> None:
    """O cliente da Steam fora de jogo segue sem pintar: o portão da autoridade o retém."""
    ctl, nos, handles, daemon = _mesa(aparelho, via, "daemon")
    pad = _pad_em_sessao(daemon, player, MACS[player], modo, caminho)
    numero = _numero_do_jogo(player)
    cor = COR_DO_SDL[numero]

    _o_jogo_escreve(pad, caminho, _report_do_jogo(numero, cor))

    assert ctl._retained_game_outputs[_uniq(MACS[player])] == {
        "led": cor,
        "player_leds": player_led_pattern(numero),
    }
    assert _uniq(MACS[player]) not in ctl._game_output_by_uniq
    for n in JOGADORES:
        assert set(nos[n].player_calls) <= {player_led_pattern(n)}
        assert set(nos[n].rgb_calls) <= {player_slot_color(n)}
        assert not any(bytes(cor) in bytes(escrito) for escrito in handles[n].escritos)
    with ctl._io_lock:
        merged = ctl._merged_desired_for_key(MACS[player])
    assert merged.player_leds == player_led_pattern(player)


def _luzes_de_fora(raiz: Path, player: int, modo_do_aparelho: str, via: str) -> dict[str, Path]:
    """O ``sysfs`` de um controle de fora: o hidraw com o ``HID_UNIQ`` e as luzes do modo."""
    barramento = "0005" if via == "radio" else "0003"
    instancia = f"{barramento}:057E:2009.00{40 + player}"
    hid = raiz / "sys/devices/externo" / instancia
    hid.mkdir(parents=True)
    (hid / "uevent").write_text(f"HID_NAME=Externo\nHID_UNIQ={MACS[player].lower()}\n")
    hidraw = raiz / "sys/class/hidraw" / f"hidraw{20 + player}"
    hidraw.mkdir(parents=True)
    (hidraw / "device").symlink_to(hid)
    leds = raiz / "sys/class/leds"
    leds.mkdir(parents=True, exist_ok=True)
    caminhos: dict[str, Path] = {}
    if modo_do_aparelho == "nintendo":
        nomes = {f"green:player-{i}": 0 for i in range(1, 5)} | {"blue:player-5": 1}
        for nome, valor in nomes.items():
            no = leds / f"{instancia}:{nome}"
            no.mkdir()
            (no / "brightness").write_text(f"{valor}\n")
            caminhos[nome] = no / "brightness"
        return caminhos
    prefixo = f"input{70 + player}"
    for nome, valor in {"red": 7, "green": 8, "blue": 9, "global": 1}.items():
        real = hid / "leds" / f"{prefixo}:{nome}"
        real.mkdir(parents=True)
        (real / "brightness").write_text(f"{valor}\n")
        (leds / f"{prefixo}:{nome}").symlink_to(real)
        caminhos[nome] = leds / f"{prefixo}:{nome}" / "brightness"
    return caminhos


def _valores(caminhos: dict[str, Path]) -> dict[str, int]:
    return {nome: int(p.read_text().strip()) for nome, p in caminhos.items()}


@pytest.fixture
def raiz_de_fora(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(external_leds, "RAIZ_HIDRAW", str(tmp_path / "sys/class/hidraw"))
    monkeypatch.setattr(external_leds, "LEDS_ROOT", str(tmp_path / "sys/class/leds"))
    (tmp_path / "sys/class/hidraw").mkdir(parents=True)
    return tmp_path


COMBINACOES_DE_FORA = [
    (player, modo_do_aparelho, modo, via, caminho)
    for player in JOGADORES
    for modo_do_aparelho in ("nintendo", "ds4")
    for modo in MODOS_DO_PAD
    for via in VIAS
    for caminho in CAMINHOS
]


@pytest.mark.parametrize(
    ("player", "modo_do_aparelho", "modo", "via", "caminho"), COMBINACOES_DE_FORA
)
def test_o_controle_de_fora_mostra_o_numero_do_jogo_e_devolve_o_de_antes(
    raiz_de_fora: Path, player: int, modo_do_aparelho: str, modo: str, via: str, caminho: str
) -> None:
    """MORDIDA: tirar o `_o_numero_do_jogo_no_controle_de_fora` e as luzes ficam como estavam."""
    luzes = _luzes_de_fora(raiz_de_fora, player, modo_do_aparelho, via)
    antes = _valores(luzes)
    _ctl, _nos, _handles, daemon = _mesa("de-fora", via, "game")
    pad = _pad_em_sessao(daemon, player, _uniq(MACS[player]), modo, caminho)
    numero = _numero_do_jogo(player)

    _o_jogo_escreve(pad, caminho, _report_do_jogo(numero, COR_DO_SDL[numero]))

    agora = _valores(luzes)
    if modo_do_aparelho == "nintendo":
        assert agora == {f"green:player-{i}": int(i <= numero) for i in range(1, 5)} | {
            "blue:player-5": 0
        }
    else:
        r, g, b = player_slot_color(numero)
        assert agora == {"red": r, "green": g, "blue": b, "global": 1}

    _o_jogo_fecha(pad)

    assert _valores(luzes) == antes


@pytest.mark.parametrize("modo_do_aparelho", ["nintendo", "ds4"])
def test_o_controle_de_fora_fora_de_jogo_nao_muda(
    raiz_de_fora: Path, modo_do_aparelho: str
) -> None:
    luzes = _luzes_de_fora(raiz_de_fora, 2, modo_do_aparelho, "radio")
    antes = _valores(luzes)
    _ctl, _nos, _handles, daemon = _mesa("de-fora", "radio", "daemon")
    pad = _pad_em_sessao(daemon, 2, _uniq(MACS[2]), "dualsense", "uhid")

    _o_jogo_escreve(pad, "uhid", _report_do_jogo(3, COR_DO_SDL[3]))

    assert _valores(luzes) == antes
    _o_jogo_fecha(pad)
    assert _valores(luzes) == antes


@pytest.mark.parametrize("via", VIAS)
@pytest.mark.parametrize("caminho", CAMINHOS)
def test_na_mesa_mista_cada_controle_mostra_o_numero_do_jogo_pelo_seu_caminho(
    raiz_de_fora: Path, via: str, caminho: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """MORDIDA: sem o `_e_um_dualsense_aberto`, o DualSense é procurado entre os de fora.

    P1 e P3 são DualSense, P2 e P4 são de fora (Nintendo e DS4), na mesma mesa.
    """
    externos = {2: "nintendo", 4: "ds4"}
    luzes = {n: _luzes_de_fora(raiz_de_fora, n, modo, via) for n, modo in externos.items()}
    antes = {n: _valores(c) for n, c in luzes.items()}
    ctl, nos, _handles, daemon = _mesa("dualsense", via, "game")
    for n in externos:
        del ctl._handles[MACS[n]]
        del ctl._sysfs[MACS[n]]
    procurados: list[str | None] = []
    original = external_leds.hidraw_do_uniq

    def procura(uniq: str | None) -> str | None:
        procurados.append(uniq)
        return original(uniq)

    monkeypatch.setattr(external_leds, "hidraw_do_uniq", procura)
    identidades = {n: _uniq(MACS[n]) if n in externos else MACS[n] for n in JOGADORES}
    pads = {
        n: _pad_em_sessao(daemon, n, identidade, "dualsense", caminho)
        for n, identidade in identidades.items()
    }
    for n, pad in pads.items():
        numero = _numero_do_jogo(n)
        _o_jogo_escreve(pad, caminho, _report_do_jogo(numero, COR_DO_SDL[numero]))

    assert sorted(procurados) == sorted(_uniq(MACS[n]) for n in externos)
    for n in (1, 3):
        assert player_led_pattern(_numero_do_jogo(n)) in nos[n].player_calls
    numero_do_p2 = _numero_do_jogo(2)
    assert _valores(luzes[2])["green:player-1"] == 1
    assert _valores(luzes[2])[f"green:player-{numero_do_p2}"] == 1
    r, g, b = player_slot_color(_numero_do_jogo(4))
    assert _valores(luzes[4]) == {"red": r, "green": g, "blue": b, "global": 1}

    for pad in pads.values():
        _o_jogo_fecha(pad)

    assert {n: _valores(c) for n, c in luzes.items()} == antes


def test_o_pad_xbox_nao_tem_canal_de_luz_do_jogo() -> None:
    """O Xbox 360 só devolve vibração ao produto: o pad nem tem ralo de luz para o jogo usar."""
    campos = {campo.name for campo in dataclasses.fields(UinputGamepad)}
    assert {"lightbar_sink", "player_led_sink", "session_end_sink"} & campos == set()
    assert "rumble_sink" in campos
