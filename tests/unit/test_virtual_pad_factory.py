"""Escolha do backend do vpad e o fallback honesto (SPRINT-UHID-VPAD-01).

O ponto do sprint é a máscara DualSense VIBRAR no jogo, e isso só acontece pelo
backend uhid (device HID de verdade → hidraw → o SDL usa o driver PS5 e o FF chega
até nós). O que estes testes travam:

1. **máscara DualSense + /dev/uhid usável + blueprint capturável → uhid.** Se a
   factory silenciosamente preferir o uinput, tudo continua "funcionando" — menos a
   vibração, que é o motivo do sprint.
2. **máscara Xbox → uinput, sempre.** O `hid_playstation` só faz bind em 054c:0ce6:
   um uhid com VID/PID de Xbox seria um device HID sem driver = controle nenhum.
3. **fallback**: nó ausente, blueprint que não veio, `start()` recusado e bind que
   não chega caem TODOS no uinput — e um bind que falha não pode deixar o device
   uhid de pé disputando o jogo com o uinput que vem em seguida.

Herméticos: os dois backends são substituídos por fakes; nada toca /dev/uhid nem
/dev/uinput, e o teste roda em CI sem hardware.
"""
from __future__ import annotations

from typing import Any

import pytest

from hefesto_dualsense4unix.integrations import virtual_pad
from hefesto_dualsense4unix.integrations.virtual_pad import VirtualPad, make_virtual_pad


class _FakeUinput:
    """Dublê do `UinputGamepad` — só o que a factory usa."""

    def __init__(self, flavor: str, rumble_sink: Any, *, ok: bool = True) -> None:
        self.flavor = flavor
        self.rumble_sink = rumble_sink
        self._ok = ok
        self.started = False

    def start(self) -> bool:
        self.started = self._ok
        return self._ok


class _FakeUhid:
    """Dublê do `UhidDualSense`, com start/bind configuráveis."""

    def __init__(
        self,
        *,
        player: int,
        blueprint: Any,
        rumble_sink: Any,
        start_ok: bool = True,
        bind_ok: bool = True,
    ) -> None:
        self.player = player
        self.blueprint = blueprint
        self.rumble_sink = rumble_sink
        self._start_ok = start_ok
        self._bind_ok = bind_ok
        self.stopped = False
        self.name = f"Hefesto Virtual DualSense P{player}"
        self.mac = f"02:fe:00:00:00:{player:02x}"

    def start(self) -> bool:
        return self._start_ok

    def wait_for_bind(self, _timeout_s: float = 2.0) -> bool:
        return self._bind_ok

    def stop(self) -> None:
        self.stopped = True


@pytest.fixture()
def backends(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """Troca os dois backends por fakes; devolve o registro do que foi criado.

    `uhid_kwargs`/`uinput_kwargs` = None enquanto aquele backend não foi tentado.
    """
    from hefesto_dualsense4unix.integrations import uhid_gamepad, uinput_gamepad

    registro: dict[str, Any] = {
        "uhid_kwargs": None,
        "uinput_kwargs": None,
        "uhid": None,
        "uinput": None,
        "uhid_start_ok": True,
        "uhid_bind_ok": True,
        "uinput_start_ok": True,
        "blueprint": {"descriptor": b"\x05\x01", "features": {0x09: b"\x09" + bytes(19)}},
        "capturados": [],
    }

    def _uhid_for_flavor(
        flavor: str | None, *, rumble_sink: Any = None, player: int = 1,
        blueprint: Any = None,
    ) -> Any:
        registro["uhid_kwargs"] = {"flavor": flavor, "player": player,
                                   "blueprint": blueprint}
        pad = _FakeUhid(
            player=player,
            blueprint=blueprint,
            rumble_sink=rumble_sink,
            start_ok=bool(registro["uhid_start_ok"]),
            bind_ok=bool(registro["uhid_bind_ok"]),
        )
        registro["uhid"] = pad
        return pad

    def _uinput_for_flavor(flavor: str | None, *, rumble_sink: Any = None) -> Any:
        registro["uinput_kwargs"] = {"flavor": flavor}
        pad = _FakeUinput(str(flavor), rumble_sink, ok=bool(registro["uinput_start_ok"]))
        registro["uinput"] = pad
        return pad

    def _capture(path: str) -> Any:
        registro["capturados"].append(path)
        return registro["blueprint"]

    monkeypatch.setattr(uhid_gamepad.UhidDualSense, "for_flavor",
                        staticmethod(_uhid_for_flavor))
    monkeypatch.setattr(uinput_gamepad.UinputGamepad, "for_flavor",
                        staticmethod(_uinput_for_flavor))
    monkeypatch.setattr(uhid_gamepad, "capture_dualsense_blueprint", _capture)
    monkeypatch.setattr(uhid_gamepad, "uhid_available", lambda: True)
    return registro


def test_dualsense_com_uhid_disponivel_usa_uhid(backends: dict[str, Any]) -> None:
    pad = make_virtual_pad("dualsense", player=3, hidraw_path="/dev/hidraw4")

    assert pad is backends["uhid"]
    assert backends["uinput_kwargs"] is None  # nem tentou o uinput
    assert backends["capturados"] == ["/dev/hidraw4"]


def test_uhid_recebe_o_player_do_slot(backends: dict[str, Any]) -> None:
    """MAC próprio por jogador: sem o `player` certo, o probe do P2 morre -EEXIST."""
    make_virtual_pad("dualsense", player=4, hidraw_path="/dev/hidraw4")

    assert backends["uhid_kwargs"]["player"] == 4


def test_uhid_recebe_o_blueprint_do_controle_fisico(backends: dict[str, Any]) -> None:
    make_virtual_pad("dualsense", player=1, hidraw_path="/dev/hidraw4")

    assert backends["uhid_kwargs"]["blueprint"] is backends["blueprint"]


def test_rumble_sink_chega_ao_backend_escolhido(backends: dict[str, Any]) -> None:
    def _sink(_weak: int, _strong: int) -> None: ...

    pad = make_virtual_pad("dualsense", rumble_sink=_sink, hidraw_path="/dev/hidraw4")

    assert pad is not None
    assert backends["uhid"].rumble_sink is _sink


def test_mascara_xbox_nunca_vai_para_o_uhid(backends: dict[str, Any]) -> None:
    pad = make_virtual_pad("xbox", hidraw_path="/dev/hidraw4")

    assert pad is backends["uinput"]
    assert backends["uhid_kwargs"] is None
    assert backends["capturados"] == []  # nem lê o controle físico à toa


def test_sem_hidraw_cai_no_uinput(backends: dict[str, Any]) -> None:
    pad = make_virtual_pad("dualsense", hidraw_path=None)

    assert pad is backends["uinput"]
    assert backends["uinput_kwargs"]["flavor"] == "dualsense"  # a máscara é preservada


def test_sem_dev_uhid_cai_no_uinput(
    backends: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    from hefesto_dualsense4unix.integrations import uhid_gamepad

    monkeypatch.setattr(uhid_gamepad, "uhid_available", lambda: False)

    pad = make_virtual_pad("dualsense", hidraw_path="/dev/hidraw4")

    assert pad is backends["uinput"]
    assert backends["uhid_kwargs"] is None


def test_blueprint_indisponivel_cai_no_uinput(backends: dict[str, Any]) -> None:
    backends["blueprint"] = None

    pad = make_virtual_pad("dualsense", hidraw_path="/dev/hidraw4")

    assert pad is backends["uinput"]
    assert backends["uhid_kwargs"] is None


def test_uhid_start_falho_cai_no_uinput(backends: dict[str, Any]) -> None:
    backends["uhid_start_ok"] = False

    pad = make_virtual_pad("dualsense", hidraw_path="/dev/hidraw4")

    assert pad is backends["uinput"]


def test_bind_que_nao_chega_cai_no_uinput_e_destroi_o_uhid(
    backends: dict[str, Any],
) -> None:
    """`start()` só diz que o CREATE2 foi aceito — o bind vem depois, ou não vem.

    Sem o `stop()`, o device uhid ficaria de pé (mudo, sem driver) disputando o
    jogo com o vpad uinput criado logo a seguir = controle duplicado.
    """
    backends["uhid_bind_ok"] = False

    pad = make_virtual_pad("dualsense", hidraw_path="/dev/hidraw4")

    assert pad is backends["uinput"]
    assert backends["uhid"].stopped is True


def test_nenhum_backend_sobe_devolve_none(backends: dict[str, Any]) -> None:
    backends["uhid_start_ok"] = False
    backends["uinput_start_ok"] = False

    assert make_virtual_pad("dualsense", hidraw_path="/dev/hidraw4") is None


def test_flavor_desconhecido_normaliza_antes_de_escolher(
    backends: dict[str, Any],
) -> None:
    """A factory decide pelo flavor NORMALIZADO ("ps" é sinônimo de dualsense)."""
    pad = make_virtual_pad("ps", hidraw_path="/dev/hidraw4")

    assert pad is backends["uhid"]


def test_fallback_loga_o_motivo(
    backends: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    """"Caiu no uinput" sem motivo é um bug que a usuária sente e ninguém acha."""
    logados: list[str] = []
    monkeypatch.setattr(virtual_pad.logger, "warning",
                        lambda evento, **_kw: logados.append(evento))
    backends["blueprint"] = None

    make_virtual_pad("dualsense", hidraw_path="/dev/hidraw4")

    assert logados == ["vpad_uhid_blueprint_falhou_usando_uinput"]


def test_os_dois_backends_reais_cumprem_o_protocolo() -> None:
    """O Protocol é o contrato que permite trocar de backend sem cirurgia.

    Instancia os dois DE VERDADE (sem start — nada de /dev aqui) e exercita a
    interface inteira num pad parado: todo método é no-op seguro sem device.
    """
    from hefesto_dualsense4unix.integrations.uhid_gamepad import UhidDualSense
    from hefesto_dualsense4unix.integrations.uinput_gamepad import UinputGamepad

    pads: list[VirtualPad] = [
        UinputGamepad.for_flavor("dualsense"),
        UhidDualSense(player=2),
    ]
    for pad in pads:
        assert isinstance(pad, VirtualPad)
        assert pad.is_active() is False
        assert pad.flavor in ("dualsense", "xbox")
        assert isinstance(pad.ff_supported, bool)
        assert pad.ff_play_count == 0
        assert pad.ff_last_sent == (0, 0)
        pad.forward_analog(lx=128, ly=128, rx=128, ry=128, l2=0, r2=0)
        pad.forward_buttons(frozenset({"cross"}))
        pad.pump_ff()
        pad.stop()


def test_uhid_declara_o_flavor_dualsense() -> None:
    """Sem isto o daemon compara `vpad.flavor` com "dualsense", vê None e recria
    o vpad a cada tick de sync do co-op."""
    from hefesto_dualsense4unix.integrations.uhid_gamepad import UhidDualSense

    assert UhidDualSense(player=1).flavor == "dualsense"
