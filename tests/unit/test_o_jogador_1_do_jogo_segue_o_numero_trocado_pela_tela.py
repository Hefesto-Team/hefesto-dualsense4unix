"""O jogador 1 do jogo segue o número trocado pela tela (23/11/2026).

D-2311-O-NUMERO-DO-JOGADOR-TROCA-PELA-TELA-COM-O-JOGO-ABERTO: o número vale no controle e no jogo
ao mesmo tempo. Medido antes da cura, neste ensaio: o controle que entrou na mesa com o jogo
aberto (chegou depois, ou saiu e voltou) recebia o 1 pela tela, o LED dizia 1 e o primário
seguia o antigo até o jogo fechar (`_voltou_com_o_jogo` do backend segurava o posto); o que já
estava na mesa só virava o jogador 1 no tique seguinte da identidade.

O ensaio é o da O-ASSENTO-GUARDADO-NAO-ANDA-02: o ``PyDualSenseController`` real, o
``CoopManager`` real, o ``ControllerIdentityRegistry`` real e o jogo visto de fora
(``JogoPorFora``). O pedido passa pelo handler real ``identity.number.set``.

MORDIDAS: sem a reeleição do `o_numero_pedido_pela_tela`, o primário fica no antigo (o LED diz
1, o jogo diz 2); sem a parada do motor no `_recompute_primary`, o deposto segue vibrando; sem o
quadro neutro do cedido em `_recolher_os_cedidos`, o pad dele sai com o botão apertado.
"""
from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.daemon.ipc_server import IpcServer
from hefesto_dualsense4unix.daemon.state_store import StateStore
from hefesto_dualsense4unix.profiles.manager import ProfileManager
from hefesto_dualsense4unix.testing import FakeController
from tests.unit import test_o_jogo_espera_a_carta_do_lugar_guardado as ensaio_mod
from tests.unit.test_coop_ensaio_de_queda_do_primario import _FakeHandle, _VpadFalso
from tests.unit.test_o_jogo_espera_a_carta_do_lugar_guardado import (  # noqa: F401
    P1,
    P2,
    P3,
    P4,
    TRANSPORTES,
    UNIQS,
    MesaDoJogo,
    Relogio,
    _VpadDaMesa,
    config_isolado,
)
from tests.unit.test_o_numero_do_jogador_troca_com_o_jogo_aberto import _a_repintura_termina

MASCARAS = ("dualsense", "xbox", "nintendo")
NEUTRO = {"lx": 128, "ly": 128, "rx": 128, "ry": 128, "l2": 0, "r2": 0}


class _HandleComMotor(_FakeHandle):
    """O handle do ensaio que guarda o que os motores receberam."""

    def __init__(self, transporte: str = "bt") -> None:
        super().__init__(transporte)
        self.motores: list[tuple[str, int]] = []

    def setLeftMotor(self, valor: int) -> None:  # noqa: N802
        self.motores.append(("esquerdo", valor))

    def setRightMotor(self, valor: int) -> None:  # noqa: N802
        self.motores.append(("direito", valor))


class _VpadQueGuarda(_VpadDaMesa):
    """O vpad da mesa que guarda cada quadro e a parada, na ordem."""

    def __init__(self, player: int, jogo: Any) -> None:
        super().__init__(player, jogo)
        self.quadros: list[tuple[Any, ...]] = []

    def forward_buttons(self, pressed: frozenset[str]) -> None:
        self.quadros.append(("botoes", frozenset(pressed)))

    def forward_analog(self, **kw: int) -> None:
        self.quadros.append(("eixos", dict(kw)))

    def stop(self) -> None:
        self.quadros.append(("parou",))
        super().stop()


class _Mesa(MesaDoJogo):
    """A mesa do jogo com a máscara pedida em cada vpad que nasce."""

    def __init__(self, monkeypatch: pytest.MonkeyPatch, mascara: str, jogo: bool) -> None:
        relogio = Relogio()
        super().__init__(monkeypatch, relogio=relogio, tempo=relogio, jogo=jogo)
        self.daemon.config.gamepad_flavor = mascara
        self.mascara = mascara
        self.nascimentos: list[str] = []

    def _nascer_vpad(
        self, _flavor: Any, *, player: int = 1, identity: str | None = None, **_kw: Any
    ) -> _VpadFalso:
        from hefesto_dualsense4unix.integrations.uhid_gamepad import vpad_mac

        vpad = _VpadQueGuarda(player, self.jogo)
        vpad.mac = vpad_mac(identity, player)
        vpad.identidade = identity  # type: ignore[attr-defined]
        vpad.flavor = str(getattr(_flavor, "value", _flavor))
        self.vpads.append(vpad)
        self.nascimentos.append(str(identity))
        return vpad


def _montar(
    monkeypatch: pytest.MonkeyPatch, quantos: int, transporte: str, mascara: str, *,
    chegam_com_o_jogo: bool, jogo: bool = True,
) -> _Mesa:
    """A mesa na ordem P1..Pn; com ``chegam_com_o_jogo``, do P2 em diante sentam com o jogo."""
    monkeypatch.setattr(ensaio_mod, "_FakeHandle", _HandleComMotor)
    mesa = _Mesa(monkeypatch, mascara, jogo)
    vias = TRANSPORTES[transporte]
    primeiros = 1 if chegam_com_o_jogo else quantos
    for uniq, via in zip(UNIQS[:primeiros], vias, strict=False):
        mesa.mesa.sentar(uniq, transporte=via)
    for _ in range(3):
        mesa.tique()
    for uniq, via in zip(UNIQS[primeiros:quantos], vias[primeiros:quantos], strict=True):
        mesa.mesa.sentar(uniq, transporte=via)
        mesa.tique()
    for _ in range(3):
        mesa.tique()
    assert mesa.inst.primary_uniq == P1
    assert mesa.a_tela() == {UNIQS[n]: n + 1 for n in range(quantos)}
    if jogo:
        assert mesa.o_jogo_ve() == {n + 1: UNIQS[n] for n in range(quantos)}
    if chegam_com_o_jogo:
        assert len(mesa.inst._voltou_com_o_jogo) == quantos - 1, "o ensaio não montou a chegada"
    return mesa


def _a_tela_pede(mesa: _Mesa, tmp: Path, alvo: str, numero: int) -> dict[str, Any]:
    """O gesto da aba Iluminação: o handler real, e a repintura que ele despacha."""
    fc = FakeController(transport="usb")
    fc.connect()
    store = StateStore()
    server = IpcServer(controller=fc, store=store,
                       profile_manager=ProfileManager(controller=fc, store=store),
                       socket_path=tmp / "j.sock", daemon=mesa.daemon)

    async def _pedir() -> dict[str, Any]:
        resposta = await server._handle_identity_number_set({"uniq": alvo, "number": numero})
        await _a_repintura_termina(server)
        return resposta

    return asyncio.run(_pedir())


def _pedidos_com_o_p1(quantos: int) -> list[tuple[int, int, int]]:
    """(quantos, quem pede, o número): cada um pedindo o 1, e o P1 pedindo cada número."""
    return [(quantos, k, 1) for k in range(1, quantos)] + [
        (quantos, 0, n) for n in range(2, quantos + 1)
    ]


PEDIDOS_COM_O_P1 = [p for q in (2, 3, 4) for p in _pedidos_com_o_p1(q)]


@pytest.mark.usefixtures("config_isolado")
@pytest.mark.parametrize("mascara", MASCARAS)
@pytest.mark.parametrize("transporte", list(TRANSPORTES))
@pytest.mark.parametrize("chegam_com_o_jogo", [False, True], ids=["antes", "com-o-jogo"])
@pytest.mark.parametrize(("quantos", "quem", "numero"), PEDIDOS_COM_O_P1)
def test_a_troca_com_o_p1_leva_o_jogador_1_do_jogo_na_hora(
    monkeypatch: pytest.MonkeyPatch, config_isolado: Path, quantos: int, quem: int,  # noqa: F811
    numero: int, transporte: str, mascara: str, chegam_com_o_jogo: bool,
) -> None:
    """D-2311-O-NUMERO-DO-JOGADOR-TROCA-PELA-TELA-COM-O-JOGO-ABERTO: o lugar 0 do jogo é de quem
    tem o 1, desde a resposta do pedido."""
    mesa = _montar(monkeypatch, quantos, transporte, mascara,
                   chegam_com_o_jogo=chegam_com_o_jogo)
    alvo = UNIQS[quem]
    novo_1 = alvo if numero == 1 else UNIQS[numero - 1]
    vpad_do_p1 = mesa.daemon._gamepad_device
    de_fora = [u for u in UNIQS[1:quantos] if u not in (alvo, novo_1)]
    vpads_de_fora = {u: mesa.vpad_de(u) for u in de_fora}
    nascidos = len(mesa.nascimentos)

    resposta = _a_tela_pede(mesa, config_isolado, alvo, numero)

    assert resposta["ok"] is True, resposta
    assert mesa.inst.primary_uniq == novo_1, "o primário espera o tique: o LED diz 1 e o jogo não"
    for _ in range(3):
        mesa.tique()
    assert mesa.inst.primary_uniq == novo_1
    assert mesa.a_tela()[novo_1] == 1
    assert mesa.o_jogo_ve()[1] == novo_1
    mesa.o_jogo_segue_a_tela()
    assert mesa.daemon._gamepad_device is vpad_do_p1, "o pad do jogador 1 fica de pé"
    assert mesa.nascimentos[nascidos:] == [P1], "só o pad do primário antigo nasce, uma vez"
    for uniq, vpad in vpads_de_fora.items():
        assert mesa.vpad_de(uniq) is vpad, f"{uniq} renasceu sem estar na troca"


@pytest.mark.usefixtures("config_isolado")
@pytest.mark.parametrize("transporte", list(TRANSPORTES))
@pytest.mark.parametrize(("quantos", "quem", "numero"),
                         [(2, 0, 2), (3, 2, 1), (4, 3, 1), (4, 0, 3)])
def test_com_o_jogo_fechado_o_primario_segue_o_pedido(
    monkeypatch: pytest.MonkeyPatch, config_isolado: Path, quantos: int, quem: int,  # noqa: F811
    numero: int, transporte: str,
) -> None:
    """D-2311-O-NUMERO-DO-JOGADOR-TROCA-PELA-TELA-COM-O-JOGO-ABERTO: sem jogo, o mesmo."""
    mesa = _montar(monkeypatch, quantos, transporte, "dualsense",
                   chegam_com_o_jogo=False, jogo=False)
    alvo = UNIQS[quem]
    novo_1 = alvo if numero == 1 else UNIQS[numero - 1]

    resposta = _a_tela_pede(mesa, config_isolado, alvo, numero)

    assert resposta["ok"] is True, resposta
    assert mesa.inst.primary_uniq == novo_1
    for _ in range(3):
        mesa.tique()
    assert mesa.inst.primary_uniq == novo_1
    assert mesa.dono_do_vpad_do_p1() == novo_1


@pytest.mark.usefixtures("config_isolado")
@pytest.mark.parametrize("chegam_com_o_jogo", [False, True], ids=["antes", "com-o-jogo"])
@pytest.mark.parametrize("transporte", list(TRANSPORTES))
@pytest.mark.parametrize(("quantos", "quem", "numero"),
                         [(3, 1, 3), (3, 2, 2), (4, 1, 4), (4, 2, 4), (4, 3, 2)])
def test_a_troca_sem_o_p1_nao_reelege(
    monkeypatch: pytest.MonkeyPatch, config_isolado: Path, quantos: int, quem: int,  # noqa: F811
    numero: int, transporte: str, chegam_com_o_jogo: bool,
) -> None:
    mesa = _montar(monkeypatch, quantos, transporte, "dualsense",
                   chegam_com_o_jogo=chegam_com_o_jogo)
    avisos: list[tuple[str | None, str | None]] = []
    avisar = mesa.inst._avisar_troca_de_primario

    def _conta(anterior: str | None, novo: str | None) -> None:
        avisos.append((anterior, novo))
        avisar(anterior, novo)

    monkeypatch.setattr(mesa.inst, "_avisar_troca_de_primario", _conta)
    vpad_do_p1 = mesa.daemon._gamepad_device

    resposta = _a_tela_pede(mesa, config_isolado, UNIQS[quem], numero)
    for _ in range(3):
        mesa.tique()

    assert resposta["ok"] is True, resposta
    assert avisos == [], "um primário reeleito à toa"
    assert mesa.inst.primary_uniq == P1
    assert mesa.daemon._gamepad_device is vpad_do_p1
    mesa.o_jogo_segue_a_tela()


@pytest.mark.usefixtures("config_isolado")
@pytest.mark.parametrize("chegam_com_o_jogo", [False, True], ids=["antes", "com-o-jogo"])
@pytest.mark.parametrize("transporte", list(TRANSPORTES))
def test_nada_fica_preso_no_primario_antigo_nem_no_pad_que_sai(
    monkeypatch: pytest.MonkeyPatch, config_isolado: Path, transporte: str,  # noqa: F811
    chegam_com_o_jogo: bool,
) -> None:
    """O motor do deposto para; o pad do cedido sai sem botão, gatilho nem analógico."""
    mesa = _montar(monkeypatch, 3, transporte, "dualsense", chegam_com_o_jogo=chegam_com_o_jogo)
    handle_do_p1 = next(h for k, h in mesa.inst._handles.items() if k.endswith("01"))
    handle_do_p1.motores.clear()
    pad_do_p3 = mesa.vpad_de(P3)
    leitor: Any = mesa.coop._players[P3].reader
    leitor.snap = type(leitor.snap)(lx=0, ly=255, rx=0, ry=255, l2_raw=255, r2_raw=255,
                                    buttons_pressed=frozenset({"cross"}))
    mesa.coop.forward_all()
    assert ("botoes", frozenset({"cross"})) in pad_do_p3.quadros, "o ensaio não apertou"

    _a_tela_pede(mesa, config_isolado, P3, 1)
    for _ in range(2):
        mesa.tique()

    assert mesa.inst.primary_uniq == P3
    assert ("esquerdo", 0) in handle_do_p1.motores and ("direito", 0) in handle_do_p1.motores
    assert getattr(handle_do_p1, "_rumble_stop_pending", False) is True
    parou = pad_do_p3.quadros.index(("parou",))
    antes = pad_do_p3.quadros[:parou]
    ultimos_botoes = [q for q in antes if q[0] == "botoes"][-1]
    ultimos_eixos = [q for q in antes if q[0] == "eixos"][-1]
    assert ultimos_botoes == ("botoes", frozenset()), pad_do_p3.quadros
    assert ultimos_eixos == ("eixos", NEUTRO), pad_do_p3.quadros
    assert mesa.dono_do_vpad_do_p1() == P3


@pytest.mark.usefixtures("config_isolado")
@pytest.mark.parametrize("chegam_com_o_jogo", [False, True], ids=["antes", "com-o-jogo"])
@pytest.mark.parametrize("transporte", list(TRANSPORTES))
def test_o_jogo_fecha_e_reabre_e_o_primario_pedido_fica(
    monkeypatch: pytest.MonkeyPatch, config_isolado: Path, transporte: str,  # noqa: F811
    chegam_com_o_jogo: bool,
) -> None:
    mesa = _montar(monkeypatch, 3, transporte, "dualsense", chegam_com_o_jogo=chegam_com_o_jogo)
    _a_tela_pede(mesa, config_isolado, P2, 1)
    mesa.tique()

    mesa.daemon.display_authority = "daemon"
    for _ in range(3):
        mesa.tique()
    assert mesa.inst.primary_uniq == P2
    mesa.daemon.display_authority = "game"
    for _ in range(3):
        mesa.tique()

    assert mesa.inst.primary_uniq == P2
    assert mesa.a_tela() == {P2: 1, P1: 2, P3: 3}
    assert mesa.dono_do_vpad_do_p1() == P2


@pytest.mark.usefixtures("config_isolado")
@pytest.mark.parametrize("chegam_com_o_jogo", [False, True], ids=["antes", "com-o-jogo"])
@pytest.mark.parametrize("transporte", list(TRANSPORTES))
def test_o_primario_antigo_sai_e_volta_e_a_mesa_nao_desfaz_o_pedido(
    monkeypatch: pytest.MonkeyPatch, config_isolado: Path, transporte: str,  # noqa: F811
    chegam_com_o_jogo: bool,
) -> None:
    mesa = _montar(monkeypatch, 3, transporte, "dualsense", chegam_com_o_jogo=chegam_com_o_jogo)
    _a_tela_pede(mesa, config_isolado, P2, 1)
    for _ in range(2):
        mesa.tique()

    via = mesa.mesa.transporte_de(P1)
    mesa.mesa.levantar(P1)
    for _ in range(3):
        mesa.tique()
        assert mesa.inst.primary_uniq == P2
    mesa.mesa.sentar(P1, transporte=via)
    for _ in range(3):
        mesa.tique()

    assert mesa.inst.primary_uniq == P2
    assert mesa.a_tela() == {P2: 1, P1: 2, P3: 3}
    assert mesa.o_jogo_ve()[1] == P2
    mesa.o_jogo_segue_a_tela()
