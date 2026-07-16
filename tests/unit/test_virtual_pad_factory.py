"""Escolha do backend do vpad e o fallback honesto (SPRINT-UHID-VPAD-01 + VPAD-03).

O ponto do sprint original é a máscara DualSense VIBRAR no jogo, e isso só
acontece pelo backend uhid (device HID de verdade → hidraw → o SDL usa o driver
PS5 e o FF chega até nós). Com VPAD-03/BT-01 o blueprint virou o CANÔNICO
EMBUTIDO — nenhuma leitura do controle físico no caminho de criação. O que
estes testes travam:

1. **máscara DualSense + /dev/uhid usável → uhid, SEM precisar de físico.** Era
   o buraco do estudo de 117 agentes: sem hidraw legível (BT dormindo, boot
   antes do connect) o vpad caía para uinput `054c:0ce6`, indistinguível do
   físico — e a launch option `IGNORE_DEVICES` persistida escondia os dois.
2. **máscara Xbox → uinput, sempre.** O `hid_playstation` só faz bind em VID da
   Sony: um uhid com VID/PID de Xbox seria um device HID sem driver.
3. **fallback**: nó ausente, `start()` recusado e bind que não chega caem TODOS
   no uinput — e um bind que falha não pode deixar o device uhid de pé
   disputando o jogo com o uinput que vem em seguida.
4. **`allow_uhid=False` (VPAD-08)**: o chamador fake veta o uhid — o smoke não
   pode registrar um DualSense Edge REAL no kernel.

Herméticos: os dois backends são substituídos por fakes; nada toca /dev/uhid nem
/dev/uinput, e o teste roda em CI sem hardware.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.integrations import virtual_pad
from hefesto_dualsense4unix.integrations.uhid_blueprint import (
    CANONICAL_DESCRIPTOR_USB,
    TEMPLATE_FEATURE_0X09,
)
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
    O blueprint NÃO é dublado: o canônico embutido é puro (bytes no pacote, sem
    I/O) — o que chega ao backend é exatamente o que o vpad real usaria.
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

    monkeypatch.setattr(uhid_gamepad.UhidDualSense, "for_flavor",
                        staticmethod(_uhid_for_flavor))
    monkeypatch.setattr(uinput_gamepad.UinputGamepad, "for_flavor",
                        staticmethod(_uinput_for_flavor))
    monkeypatch.setattr(uhid_gamepad, "uhid_available", lambda: True)
    return registro


def test_dualsense_usa_uhid_sem_precisar_do_fisico(backends: dict[str, Any]) -> None:
    """O critério central do VPAD-03: nada de hidraw, nada de controle conectado
    — e o vpad ainda assim nasce uhid (hoje era uinput)."""
    pad = make_virtual_pad("dualsense", player=3)

    assert pad is backends["uhid"]
    assert backends["uinput_kwargs"] is None  # nem tentou o uinput


def test_uhid_recebe_o_player_do_slot(backends: dict[str, Any]) -> None:
    """MAC próprio por jogador: sem o `player` certo, o probe do P2 morre -EEXIST."""
    make_virtual_pad("dualsense", player=4)

    assert backends["uhid_kwargs"]["player"] == 4


def test_uhid_recebe_o_blueprint_canonico(backends: dict[str, Any]) -> None:
    """O blueprint injetado é o sintético embutido — descriptor USB de 289 B e o
    template 0x09 SEM identidade (o start() carimba o MAC do jogador depois)."""
    make_virtual_pad("dualsense", player=1)

    blueprint = backends["uhid_kwargs"]["blueprint"]
    assert blueprint["descriptor"] is CANONICAL_DESCRIPTOR_USB
    assert blueprint["features"][0x09] is TEMPLATE_FEATURE_0X09
    assert set(blueprint["features"]) == {0x05, 0x09, 0x20}


def test_rumble_sink_chega_ao_backend_escolhido(backends: dict[str, Any]) -> None:
    def _sink(_weak: int, _strong: int) -> None: ...

    pad = make_virtual_pad("dualsense", rumble_sink=_sink)

    assert pad is not None
    assert backends["uhid"].rumble_sink is _sink


def test_mascara_xbox_nunca_vai_para_o_uhid(backends: dict[str, Any]) -> None:
    pad = make_virtual_pad("xbox")

    assert pad is backends["uinput"]
    assert backends["uhid_kwargs"] is None


def test_sem_dev_uhid_cai_no_uinput(
    backends: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    from hefesto_dualsense4unix.integrations import uhid_gamepad

    monkeypatch.setattr(uhid_gamepad, "uhid_available", lambda: False)

    pad = make_virtual_pad("dualsense")

    assert pad is backends["uinput"]
    assert backends["uinput_kwargs"]["flavor"] == "dualsense"  # a máscara é preservada
    assert backends["uhid_kwargs"] is None


def test_allow_uhid_false_veta_o_uhid_mesmo_disponivel(
    backends: dict[str, Any],
) -> None:
    """VPAD-08: o daemon FAKE declara "sem uhid" — registrar um DualSense Edge
    REAL no kernel a partir de um smoke exporia um controle fantasma à Steam."""
    pad = make_virtual_pad("dualsense", allow_uhid=False)

    assert pad is backends["uinput"]
    assert backends["uhid_kwargs"] is None  # nem chegou a tentar


def test_allow_uhid_false_loga_o_veto(
    backends: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    logados: list[str] = []
    monkeypatch.setattr(virtual_pad.logger, "info",
                        lambda evento, **_kw: logados.append(evento))

    make_virtual_pad("dualsense", allow_uhid=False)

    assert "vpad_uhid_vetado_pelo_chamador_usando_uinput" in logados


def test_uhid_start_falho_cai_no_uinput(backends: dict[str, Any]) -> None:
    backends["uhid_start_ok"] = False

    pad = make_virtual_pad("dualsense")

    assert pad is backends["uinput"]


def test_bind_que_nao_chega_cai_no_uinput_e_destroi_o_uhid(
    backends: dict[str, Any],
) -> None:
    """`start()` só diz que o CREATE2 foi aceito — o bind vem depois, ou não vem.

    Sem o `stop()`, o device uhid ficaria de pé (mudo, sem driver) disputando o
    jogo com o vpad uinput criado logo a seguir = controle duplicado.
    """
    backends["uhid_bind_ok"] = False

    pad = make_virtual_pad("dualsense")

    assert pad is backends["uinput"]
    assert backends["uhid"].stopped is True


def test_nenhum_backend_sobe_devolve_none(backends: dict[str, Any]) -> None:
    backends["uhid_start_ok"] = False
    backends["uinput_start_ok"] = False

    assert make_virtual_pad("dualsense") is None


def test_flavor_desconhecido_normaliza_antes_de_escolher(
    backends: dict[str, Any],
) -> None:
    """A factory decide pelo flavor NORMALIZADO ("ps" é sinônimo de dualsense)."""
    pad = make_virtual_pad("ps")

    assert pad is backends["uhid"]


def test_fallback_loga_o_motivo(
    backends: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    """"Caiu no uinput" sem motivo é um bug que a usuária sente e ninguém acha."""
    logados: list[str] = []
    monkeypatch.setattr(virtual_pad.logger, "warning",
                        lambda evento, **_kw: logados.append(evento))
    backends["uhid_start_ok"] = False

    make_virtual_pad("dualsense")

    assert logados == ["vpad_uhid_start_falhou_usando_uinput"]


def test_criacao_nao_le_o_controle_fisico() -> None:
    """BT-01, critério 4: nenhum caminho de criação de vpad lê o físico.

    Se `capture_dualsense_blueprint` voltar para a factory, o EIO do BT dormindo
    volta a decidir o backend — exatamente o bug do estudo de 117 agentes.
    """
    fonte = Path(virtual_pad.__file__).read_text(encoding="utf-8")

    assert "capture_dualsense_blueprint" not in fonte
    assert "canonical_blueprint" in fonte


class TestMotivoDoFallback:
    """VPAD-05 — fallback nunca silencioso: o vpad degradado carrega o PORQUÊ.

    A factory pendura `fallback_motivo` no uinput quando o flavor dualsense
    degradou; o `state_full` expõe isso (`gamepad_emulation.degraded_motivo`)
    para a GUI/doctor sem ninguém garimpar o journal. Xbox e uhid saudável NÃO
    carregam motivo — uinput por design não é degradação.
    """

    def test_uhid_indisponivel(
        self, backends: dict[str, Any], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from hefesto_dualsense4unix.integrations import uhid_gamepad

        monkeypatch.setattr(uhid_gamepad, "uhid_available", lambda: False)

        pad = make_virtual_pad("dualsense")

        assert getattr(pad, "fallback_motivo", None) == "uhid_indisponivel"

    def test_start_falhou(self, backends: dict[str, Any]) -> None:
        backends["uhid_start_ok"] = False

        pad = make_virtual_pad("dualsense")

        assert getattr(pad, "fallback_motivo", None) == "uhid_start_falhou"

    def test_bind_falhou(self, backends: dict[str, Any]) -> None:
        backends["uhid_bind_ok"] = False

        pad = make_virtual_pad("dualsense")

        assert getattr(pad, "fallback_motivo", None) == "uhid_bind_falhou"

    def test_veto_do_chamador(self, backends: dict[str, Any]) -> None:
        """VPAD-08: o backend fake veta o uhid — e o estado diz isso às claras."""
        pad = make_virtual_pad("dualsense", allow_uhid=False)

        assert getattr(pad, "fallback_motivo", None) == "uhid_vetado_pelo_chamador"

    def test_xbox_nao_e_degradacao(self, backends: dict[str, Any]) -> None:
        pad = make_virtual_pad("xbox")

        assert getattr(pad, "fallback_motivo", None) is None

    def test_uhid_saudavel_nao_carrega_motivo(self, backends: dict[str, Any]) -> None:
        pad = make_virtual_pad("dualsense")

        assert getattr(pad, "fallback_motivo", None) is None


class TestInvarianteVpad06:
    """VPAD-06 — o teste-invariante do sprint: NENHUM caminho de criação de vpad
    com flavor dualsense expõe o VID/PID do FÍSICO (054c:0ce6).

    É o teste que teria pegado o "zero controles" antes do estudo de 117
    agentes: o fallback uinput nascia 0ce6 e a launch option persistida na Steam
    (`IGNORE_DEVICES=0x054c/0x0ce6`) escondia físico E vpad juntos. Usa os
    backends REAIS (o VID/PID testado é o de produção) — só o I/O de /dev/uhid
    e /dev/uinput é stubado, então roda em CI sem hardware e sem skip (regra
    dos 22 skips falsos).
    """

    @pytest.fixture()
    def io_stub(self, monkeypatch: pytest.MonkeyPatch) -> dict[str, bool]:
        from hefesto_dualsense4unix.integrations import uhid_gamepad, uinput_gamepad

        estado = {"available": True, "start": True, "bind": True}
        monkeypatch.setattr(uhid_gamepad, "uhid_available",
                            lambda: estado["available"])
        monkeypatch.setattr(uhid_gamepad.UhidDualSense, "start",
                            lambda self: estado["start"])
        monkeypatch.setattr(uhid_gamepad.UhidDualSense, "wait_for_bind",
                            lambda self, timeout_s=2.0: estado["bind"])
        monkeypatch.setattr(uhid_gamepad.UhidDualSense, "stop", lambda self: None)
        monkeypatch.setattr(uinput_gamepad.UinputGamepad, "start",
                            lambda self: True)
        return estado

    @pytest.mark.parametrize(
        ("cenario", "backend_esperado"),
        [
            ("uhid_ok", "uhid"),
            ("uhid_indisponivel", "uinput"),
            ("uhid_start_falhou", "uinput"),
            ("uhid_bind_falhou", "uinput"),
            ("uhid_vetado_allow_false", "uinput"),
        ],
    )
    def test_nenhum_caminho_expoe_o_vidpid_do_fisico(
        self, cenario: str, backend_esperado: str, io_stub: dict[str, bool]
    ) -> None:
        allow_uhid = True
        if cenario == "uhid_indisponivel":
            io_stub["available"] = False
        elif cenario == "uhid_start_falhou":
            io_stub["start"] = False
        elif cenario == "uhid_bind_falhou":
            io_stub["bind"] = False
        elif cenario == "uhid_vetado_allow_false":
            allow_uhid = False

        pad = make_virtual_pad("dualsense", allow_uhid=allow_uhid)

        assert pad is not None
        assert pad.backend == backend_esperado
        product = getattr(pad, "product", None)
        assert product != 0x0CE6, (
            "vpad dividindo VID/PID com o físico — a launch option persistida "
            "esconderia os dois (jogo com ZERO controles)"
        )
        assert product == 0x0DF2  # Edge nos DOIS backends (VPAD-04)
        # UhidDualSense não tem campo vendor (constante do módulo, testada em
        # test_uhid_edge_dedup); no uinput o vendor é campo e TEM de ser Sony.
        assert getattr(pad, "vendor", 0x054C) == 0x054C


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
