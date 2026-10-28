"""O modo DualSense sem o canal próprio cai no Xbox 360 até o canal voltar.

A pergunta 6 da NO-MODO-XBOX-TUDO-FUNCIONA-01, respondida em 13/10: o `uhid` que
não sobe deixava o Edge no `uinput`, sem hidraw, e o Proton não o usa. A fábrica
veste o pad de Xbox 360 com o motivo `sem_canal_proprio`; o cartão (`flavor`)
fica, a queda segue anunciada, nenhum juiz recria em laço, e a promoção devolve
o `uhid` quando ele volta. A infraestrutura (o `evdev` que grava, o disco em
tmp) é a da régua do modo Xbox.
"""

from __future__ import annotations

from typing import Any

import pytest

from hefesto_dualsense4unix.daemon.subsystems import gamepad as gp
from hefesto_dualsense4unix.daemon.subsystems.external_mask import (
    vpad_ficou_para_tras,
)
from hefesto_dualsense4unix.integrations import uhid_gamepad
from hefesto_dualsense4unix.integrations import virtual_pad as vp
from hefesto_dualsense4unix.integrations.uinput_gamepad import (
    XBOX360_NAME,
    XBOX360_PRODUCT,
    XBOX360_VENDOR,
)
from tests.unit.test_no_modo_xbox_o_jogo_ve_o_pad import (  # noqa: F401
    EIXOS_DO_XBOX,
    MACS,
    TECLAS_DO_XBOX,
    _daemon_do_p1,
    _evdev_que_grava,
    _hermetico,
    _no_de,
    _NoGravado,
)

XBOX = (XBOX360_VENDOR, XBOX360_PRODUCT)
DS = vp.CAMINHO_DUALSENSE
SEM_CANAL = vp.MOTIVO_SEM_CANAL_PROPRIO


def _uhid(monkeypatch: pytest.MonkeyPatch, *, sobe: bool = True, binda: bool = True) -> None:
    """O `/dev/uhid` disponível, sem kernel: `start` e `wait_for_bind` dizem o pedido."""
    monkeypatch.setattr(uhid_gamepad, "uhid_available", lambda: True)
    monkeypatch.setattr(uhid_gamepad.UhidDualSense, "start", lambda self: sobe)
    monkeypatch.setattr(
        uhid_gamepad.UhidDualSense, "wait_for_bind", lambda self, timeout_s=2.0: binda
    )
    monkeypatch.setattr(uhid_gamepad.UhidDualSense, "stop", lambda self: None)


_QUEDAS = ("uhid_indisponivel", "uhid_start_falhou", "uhid_bind_falhou",
           "uhid_vetado_pelo_chamador")


def _pad_que_caiu(queda: str, monkeypatch: pytest.MonkeyPatch, jogador: int = 1) -> Any:
    if queda != "uhid_indisponivel":
        _uhid(monkeypatch, sobe=queda != "uhid_start_falhou",
              binda=queda != "uhid_bind_falhou")
    pad = vp.make_virtual_pad(
        "dualsense", caminho=DS, player=jogador, identity=MACS[jogador - 1],
        allow_uhid=queda != "uhid_vetado_pelo_chamador",
    )
    assert pad is not None
    return pad


def test_a_regra_tem_um_dono() -> None:
    """Prova da D-1610-SEM-CANAL-PROPRIO-O-DUALSENSE-VESTE-O-XBOX-360."""
    for caminho in (None, DS):
        assert vp.mascara_no_jogo(caminho, "dualsense", sem_canal=True) == "xbox"
        assert vp.mascara_no_jogo(caminho, "dualsense") == "dualsense"
        assert vp.motivo_da_troca(caminho, "dualsense", sem_canal=True) == SEM_CANAL
        for outra in ("xbox", "nintendo"):
            assert vp.mascara_no_jogo(caminho, outra, sem_canal=True) == outra, outra
            assert vp.motivo_da_troca(caminho, outra, sem_canal=True) is None, outra
    assert vp.motivo_da_troca(vp.CAMINHO_XBOX, "dualsense", sem_canal=True) == (
        vp.MOTIVO_MODO_XBOX_ESCOLHIDO
    ), "o modo Xbox escolhido é escolha, e o motivo dele vence"


@pytest.mark.parametrize("jogador", [1, 2, 3, 4])
@pytest.mark.parametrize("queda", _QUEDAS)
def test_sem_o_canal_o_jogo_ve_o_xbox_360(
    queda: str, jogador: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    """MORDIDA: tire o `sem_canal` da fábrica, e o Edge `054c:0df2` volta ao `uinput`."""
    pad = _pad_que_caiu(queda, monkeypatch, jogador)
    try:
        no = _no_de(pad)
        assert no.vidpid == XBOX, f"P{jogador}, {queda}: {no.vidpid[0]:04x}:{no.vidpid[1]:04x}"
        assert no.kwargs["name"] == XBOX360_NAME
        assert (no.teclas, no.eixos) == (TECLAS_DO_XBOX, EIXOS_DO_XBOX)
        assert pad.backend == "uinput"
        assert pad.flavor == "dualsense", "o cartão não se perde"
        assert pad.mascara_no_jogo == "xbox"
        assert pad.troca_motivo == SEM_CANAL
        assert vp.motivo_da_degradacao(pad) == queda, "a queda segue anunciada"
        assert vp.caminho_do_vpad(pad) == DS
    finally:
        pad.stop()


@pytest.mark.parametrize("queda", _QUEDAS)
def test_nenhum_juiz_recria_o_pad_que_caiu(
    queda: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """MORDIDA: tire o `sem_canal` de `o_aparelho_mudou`, e o juiz pede outro pad."""
    pad = _pad_que_caiu(queda, monkeypatch)
    try:
        assert not vp.o_aparelho_mudou(pad, DS, "dualsense")
        assert not vpad_ficou_para_tras(pad.flavor, MACS[0], "dualsense", vpad=pad, caminho=DS)
    finally:
        pad.stop()


def test_o_p1_que_caiu_fica_de_pe_e_volta_ao_uhid_quando_o_canal_volta(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """O P1 pelo daemon: sem `uhid`, Xbox 360 sem laço; com ele de volta, o Edge.

    A volta é a promoção que já existia (a re-seleção da máscara, VPAD-02): ela
    olha o `flavor` e o `backend`, que o pad vestido guarda.
    """
    monkeypatch.setattr(gp, "controller_allows_uhid", lambda _d: True)
    d = _daemon_do_p1(monkeypatch)
    try:
        gp.start_gamepad_emulation_desfecho(d, "dualsense", origin="profile", caminho=DS)
        pad = d._gamepad_device
        assert _no_de(pad).vidpid == XBOX, "premissa: o canal fora do ar"
        assert pad.troca_motivo == SEM_CANAL
        for _ in range(10):
            assert gp.reconciliar_as_mascaras(d) is None
        assert d._gamepad_device is pad, "um juiz recriou o pad que caiu"
        assert len(_NoGravado.criados) == 1
        _uhid(monkeypatch)
        gp.start_gamepad_emulation_desfecho(d, "dualsense", origin="manual", caminho=DS)
        assert d._gamepad_device.backend == "uhid", "o canal voltou e o pad não subiu nele"
        assert vp.motivo_da_degradacao(d._gamepad_device) is None
    finally:
        gp.stop_gamepad_emulation(d, persist=False)

