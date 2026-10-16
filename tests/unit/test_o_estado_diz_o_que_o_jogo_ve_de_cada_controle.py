"""O estado diz o que o jogo vê de cada controle: a forma, o canal e o que chega.

Sprint O-ESTADO-DIZ-O-QUE-O-JOGO-VE-DE-CADA-CONTROLE-01. Os pads do `uinput` nascem
pela fábrica de verdade, com o `evdev` que grava (a infraestrutura da régua do modo
Xbox); o do `uhid` é um pad de mentira com o backend. O `state_full` sai do servidor
IPC real, com o daemon de mentira da régua do estado por controle.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from hefesto_dualsense4unix.core.roteador_de_movimento import ArranjoDeMovimento
from hefesto_dualsense4unix.core.virtual_motion import REGISTRO
from hefesto_dualsense4unix.integrations import o_que_o_jogo_ve as oqv
from hefesto_dualsense4unix.integrations import virtual_pad as vp
from tests.unit.test_ipc_state_per_controller import (  # noqa: F401
    MAC1,
    MAC2,
    _describe_dois,
    _make_state,
    _state_full,
    isolated_profiles_dir,
    running_server,
)
from tests.unit.test_no_modo_xbox_o_jogo_ve_o_pad import (  # noqa: F401
    _evdev_que_grava,
    _hermetico,
)

MIRA_LIGADA = ArranjoDeMovimento(destino="analogico_direito")
MIRA_DESLIGADA = ArranjoDeMovimento()
EDGE_NO_UHID = SimpleNamespace(flavor="dualsense", backend="uhid", caminho=vp.CAMINHO_DUALSENSE)


def _fabrica(mascara: str, caminho: str | None, **kw: Any) -> Any:
    pad = vp.make_virtual_pad(mascara, caminho=caminho, **kw)
    assert pad is not None
    return pad


def _ve(pad: Any, movimento: object = MIRA_DESLIGADA, **kw: Any) -> dict[str, Any]:
    visto = oqv.o_que_o_jogo_ve(pad, movimento, **kw)
    assert visto is not None
    return visto


def _eixos(visto: dict[str, Any]) -> tuple[str, str, str]:
    return (visto["forma"], visto["canal"], visto["conexao"])  # (noqa-acento): chave ASCII


def _chega(visto: dict[str, Any]) -> dict[str, str]:
    return dict(visto["funcoes"])  # (noqa-acento): chave ASCII


def test_o_dualsense_no_uhid_e_nativo_em_tudo() -> None:
    visto = _ve(EDGE_NO_UHID, transporte="usb")
    assert _eixos(visto) == ("dualsense", "uhid", "cabo")
    assert set(_chega(visto)) == set(oqv.FUNCOES)
    assert set(_chega(visto).values()) == {oqv.NATIVO}
    assert visto["troca_motivo"] is None and visto["degradado_motivo"] is None


def test_o_modo_xbox_e_o_xbox_360_com_a_mira_pelo_hefesto() -> None:
    """MORDIDA: leia a `forma` da máscara escolhida (`flavor`), e este reprova."""
    pad = _fabrica("dualsense", vp.CAMINHO_XBOX)
    try:
        visto = _ve(pad)
        assert visto["forma"] == "xbox360"
        assert visto["troca_motivo"] == vp.MOTIVO_MODO_XBOX_ESCOLHIDO
        assert visto["degradado_motivo"] is None
        assert _chega(visto)["gatilho_adaptativo"] == oqv.PELO_HEFESTO
        assert _chega(visto)["giroscopio"] == oqv.NAO_CHEGA
        assert _chega(_ve(pad, MIRA_LIGADA))["giroscopio"] == oqv.PELO_HEFESTO
        inclinacao = ArranjoDeMovimento(acelerometro="analogico_esquerdo")
        assert _chega(_ve(pad, inclinacao))["giroscopio"] == oqv.PELO_HEFESTO
    finally:
        pad.stop()


def test_o_pro_no_uinput_nao_leva_o_gatilho_analogico_nem_a_luz_de_jogador() -> None:
    pad = _fabrica("nintendo", vp.CAMINHO_DUALSENSE)
    try:
        visto = _ve(pad)
        assert (visto["forma"], visto["canal"]) == ("pro", "uinput")
        assert _chega(visto)["gatilho_analogico"] == oqv.NAO_CHEGA
        assert _chega(visto)["luz_de_jogador"] == oqv.NAO_CHEGA
        assert _chega(visto)["botoes"] == oqv.NATIVO
    finally:
        pad.stop()


@pytest.mark.parametrize("jogador", [1, 2, 3, 4])
def test_a_queda_diz_o_motivo_e_o_toque_chega_pelo_hefesto(jogador: int) -> None:
    """Sem o canal próprio, o jogo vê o Xbox 360 (a pergunta 6 da NO-MODO-XBOX)."""
    pad = _fabrica("dualsense", vp.CAMINHO_DUALSENSE, player=jogador, allow_uhid=False)
    try:
        visto = _ve(pad, transporte="bt")
        assert visto["degradado_motivo"] == "uhid_vetado_pelo_chamador"
        assert visto["troca_motivo"] == vp.MOTIVO_SEM_CANAL_PROPRIO
        assert _eixos(visto) == ("xbox360", "uinput", "radio")
        assert _chega(visto)["touchpad"] == oqv.PELO_HEFESTO
    finally:
        pad.stop()


@pytest.mark.parametrize(
    ("mascara", "caminho"),
    [("xbox", None), ("nintendo", vp.CAMINHO_DUALSENSE), ("dualsense", vp.CAMINHO_XBOX)],
)
def test_o_som_chega_pelo_hefesto_fora_do_dualsense(mascara: str, caminho: str | None) -> None:
    pad = _fabrica(mascara, caminho)
    try:
        funcoes = _chega(_ve(pad))
        assert (funcoes["microfone"], funcoes["alto_falante"]) == (oqv.PELO_HEFESTO,) * 2
    finally:
        pad.stop()
    funcoes = _chega(_ve(EDGE_NO_UHID))
    assert (funcoes["microfone"], funcoes["alto_falante"]) == (oqv.NATIVO,) * 2


def test_as_chaves_do_controle_calam_o_giro_e_o_toque() -> None:
    calado = _chega(_ve(EDGE_NO_UHID, giro_ligado=False, toque_ligado=False))
    assert (calado["giroscopio"], calado["touchpad"]) == (oqv.NAO_CHEGA,) * 2
    pad = _fabrica("xbox", None)
    try:
        assert _chega(_ve(pad, toque_ligado=False))["touchpad"] == oqv.NAO_CHEGA
    finally:
        pad.stop()


@pytest.mark.parametrize("pad", [None, object(), SimpleNamespace(flavor="dualsense"),
                                 SimpleNamespace(flavor="outra", backend="uinput")])
def test_o_pad_que_nao_sabe_dizer_e_none(pad: object) -> None:
    assert oqv.o_que_o_jogo_ve(pad, None) is None


class TestOEstado:
    @pytest.mark.asyncio
    async def test_os_dois_controles_levam_o_campo(
        self, running_server: Any, monkeypatch: pytest.MonkeyPatch  # noqa: F811
    ) -> None:
        _server, socket_path, fc, _store, daemon = running_server
        _describe_dois(fc)
        fc.primary_uniq = MAC1
        daemon._last_state = _make_state(transport="usb")
        p2 = _fabrica("nintendo", vp.CAMINHO_DUALSENSE, player=2)
        daemon._gamepad_device = SimpleNamespace(**vars(EDGE_NO_UHID), ff_supported=True)
        daemon._coop_manager = SimpleNamespace(
            live_snapshots=lambda: {}, _players={MAC2: SimpleNamespace(vpad=p2)},
            player_count=lambda: 2,
        )
        monkeypatch.setattr(REGISTRO, "touchpad_ligado", lambda uniq: uniq != MAC2)
        try:
            result = await _state_full(socket_path)
        finally:
            p2.stop()
        c1, c2 = result["controllers"]
        assert _eixos(c1["o_que_o_jogo_ve"]) == ("dualsense", "uhid", "cabo")
        assert _eixos(c2["o_que_o_jogo_ve"]) == ("pro", "uinput", "radio")
        assert _chega(c2["o_que_o_jogo_ve"])["touchpad"] == oqv.NAO_CHEGA
        assert result["gamepad_emulation"]["o_que_o_jogo_ve"] == c1["o_que_o_jogo_ve"]

    @pytest.mark.asyncio
    async def test_o_pad_sem_atributos_da_none_sem_derrubar_o_estado(
        self, running_server: Any  # noqa: F811
    ) -> None:
        _server, socket_path, fc, _store, daemon = running_server
        _describe_dois(fc)
        daemon._gamepad_device = SimpleNamespace()
        daemon._coop_manager = SimpleNamespace(
            live_snapshots=lambda: {}, _players={MAC2: SimpleNamespace()},
            player_count=lambda: 2,
        )
        result = await _state_full(socket_path)
        assert [c["o_que_o_jogo_ve"] for c in result["controllers"]] == [None, None]
        assert result["gamepad_emulation"]["o_que_o_jogo_ve"] is None

