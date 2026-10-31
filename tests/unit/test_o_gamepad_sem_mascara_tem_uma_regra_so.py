"""O-GAMEPAD-SEM-MASCARA-TEM-UMA-REGRA-SO-01 — a seção `gamepad` sem par é o DualSense.

Medido em 31/10/2026, depois da migração em disco: dois perfis de uma máquina real ficaram com
``mode = {"kind": "gamepad", "gamepad_flavor": null}``, um sem ponte e outro com a ponte
``native`` carimbada por silêncio. O escritor único deixava o par vazio, o daemon vestia a
máscara da máquina (``_mascara_da_maquina``) e o ``virtual_pad.modo_do_par`` dizia
``dualsense``: num computador com a máquina em Xbox, o perfil que a aba Jogar mostra como
DualSense abria em Xbox.

O ENSAIO: os perfis moram no ``XDG_CONFIG_HOME`` do teste (o ``conftest`` isola), escritos crus
como a migração os deixou; o daemon é o de verdade, só com a fábrica do pad dublada por um
boneco que guarda a máscara, o caminho e o canal que o produto pediu.
"""
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest

from hefesto_dualsense4unix.daemon import lifecycle as lc
from hefesto_dualsense4unix.daemon.lifecycle import Daemon, DaemonConfig
from hefesto_dualsense4unix.daemon.subsystems import gamepad as gp
from hefesto_dualsense4unix.daemon.subsystems.external_mask import mascara_efetiva
from hefesto_dualsense4unix.integrations import virtual_pad as vp
from hefesto_dualsense4unix.interface.pacotes import a10_perfis
from hefesto_dualsense4unix.profiles import loader
from hefesto_dualsense4unix.profiles.manager import (
    secao_do_modo_com_o_caminho,
    secao_do_modo_do_estilo,
)
from hefesto_dualsense4unix.profiles.schema import (
    MatchCriteria,
    Profile,
    ProfileModeConfig,
)
from hefesto_dualsense4unix.testing.fake_controller import FakeController
from hefesto_dualsense4unix.utils.session import save_gamepad_emulation
from hefesto_dualsense4unix.utils.xdg_paths import profiles_dir

MAC_P1 = "aa:bb:cc:00:00:01"
TRANSPORTES = ("usb", "bt")
PAR_DUALSENSE = {"kind": "gamepad", "gamepad_flavor": "dualsense", "caminho": "dualsense"}
MODIFICADO_EM = "2026-10-01T12:00:00-03:00"


def _cru(nome: str, appid: int, **resto: Any) -> dict[str, Any]:
    return {
        "name": nome,
        "match": {"type": "criteria", "window_class": [f"steam_app_{appid}"]},
        "priority": 80,
        "modificado_em": MODIFICADO_EM,
        **resto,
    }


OS_DOIS_QUE_SOBRARAM: dict[str, dict[str, Any]] = {
    "sem_ponte": _cru("Sem Ponte", 9931201, mode={"kind": "gamepad", "gamepad_flavor": None}),
    "ponte_nativa_por_silencio": _cru(
        "Ponte Nativa Por Silencio", 9931202, mode={"kind": "gamepad", "gamepad_flavor": None},
        ponte={"kind": "native", "gamepad_flavor": None, "steam_input": False,
               "confirmada_por": "silencio", "confirmada_em": "2026-10-17T04:08:17-03:00"}),
}


@pytest.fixture
def pasta() -> Path:
    destino = profiles_dir(ensure=True)
    for chave, dados in OS_DOIS_QUE_SOBRARAM.items():
        (destino / f"{chave}.json").write_text(
            json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8")
    return destino


def test_a_migracao_grava_o_par_do_dualsense_e_a_segunda_rodada_nao_escreve(pasta: Path) -> None:
    """**A MORDIDA.** Com o «sem caminho nem máscara, fica» de volta no escritor único, os dois
    perfis seguem sem par no disco e esta régua reprova."""
    antes = {c: (pasta / f"{c}.json").read_bytes() for c in OS_DOIS_QUE_SOBRARAM}

    convertidos = loader.todo_perfil_no_formato_da_aba_jogar()

    assert sorted(convertidos) == sorted(f"{c}.json" for c in OS_DOIS_QUE_SOBRARAM)
    for chave, original in OS_DOIS_QUE_SOBRARAM.items():
        dados = json.loads((pasta / f"{chave}.json").read_text(encoding="utf-8"))
        assert dados["mode"] == PAR_DUALSENSE, chave
        assert {k: v for k, v in dados.items() if k != "mode"} == {
            k: v for k, v in original.items() if k != "mode"}, chave
        assert [v.read_bytes() for v in loader.listar_historico(chave)] == [antes[chave]], chave

    bytes_da_primeira = {c: (pasta / f"{c}.json").read_bytes() for c in OS_DOIS_QUE_SOBRARAM}
    assert loader.todo_perfil_no_formato_da_aba_jogar() == []
    assert {c: (pasta / f"{c}.json").read_bytes() for c in OS_DOIS_QUE_SOBRARAM} == (
        bytes_da_primeira)
    for chave in OS_DOIS_QUE_SOBRARAM:
        assert len(loader.listar_historico(chave)) == 1, chave


@pytest.mark.parametrize(
    ("caminho", "mascara", "par"),
    [
        (None, None, ("dualsense", "dualsense")),
        ("dualsense", None, ("dualsense", "dualsense")),
        ("xbox", None, ("xbox", "xbox")),
        (None, "xbox", ("xbox", "xbox")),
        (None, "nintendo", (None, "nintendo")),
        ("xbox", "dualsense", ("xbox", "xbox")),
    ],
)
def test_o_dono_da_regra_e_o_escritor_unico_dao_o_mesmo_par(
    caminho: str | None, mascara: str | None, par: tuple[str | None, str]
) -> None:
    """O par da seção `gamepad` tem um dono, e o escritor único grava o que ele diz."""
    assert vp.par_da_secao_do_gamepad(caminho, mascara) == par
    secao = secao_do_modo_com_o_caminho(None, kind="gamepad", caminho=caminho, mascara=mascara)
    assert (secao.caminho, secao.gamepad_flavor) == par
    atual = ProfileModeConfig.model_validate(
        {"kind": "gamepad", "caminho": caminho, "gamepad_flavor": mascara})
    assert vp.modo_do_par(caminho, mascara) == par[1]
    _mudou, do_estilo = secao_do_modo_do_estilo(atual, "gamepad")
    assert do_estilo is not None and (do_estilo.caminho, do_estilo.gamepad_flavor) == par


class _Pad:
    """O boneco do vpad: a máscara, o caminho e o canal que o produto pediu."""

    def __init__(self, flavor: str, caminho: str | None) -> None:
        self.flavor = flavor
        self.caminho = vp.caminho_resolvido(caminho, flavor)
        self.backend = "uhid" if vp.quer_uhid(caminho, flavor) else "uinput"
        self.parado = False

    def stop(self) -> None:
        self.parado = True


@pytest.fixture
def maquina_em_xbox(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "hefesto_dualsense4unix.integrations.virtual_pad.make_virtual_pad",
        lambda flavor, **kw: _Pad(mascara_efetiva(kw.get("identity"), flavor), kw.get("caminho")),
    )
    monkeypatch.setattr(
        "hefesto_dualsense4unix.daemon.launch_env.materialize_launch_env", lambda _daemon: None)
    monkeypatch.setattr(gp, "_set_controller_grab", lambda *_a: None)
    save_gamepad_emulation(True, "xbox")
    assert lc._mascara_da_maquina() == "xbox", "premissa: a máquina escolheu Xbox"


def _daemon(transporte: str) -> Any:
    d: Any = Daemon(
        controller=FakeController(transport=cast(Any, transporte)),
        config=DaemonConfig(ipc_enabled=False, udp_enabled=False),
    )
    d.controller.primary_uniq = MAC_P1
    d._coop_manager = SimpleNamespace(
        sync=lambda **_k: None,
        disable=lambda: None,
        player_count=lambda: 1,
        algum_boneco_ficou_para_tras=lambda: False,
    )
    d._game_signal = SimpleNamespace(authority="daemon")
    return d


def _perfil(mode: dict[str, Any] | None) -> Profile:
    return Profile.model_validate(_cru("Jogo", 9931203, **({"mode": mode} if mode else {})))


@pytest.mark.usefixtures("maquina_em_xbox")
@pytest.mark.parametrize("transporte", TRANSPORTES)
def test_a_secao_gamepad_sem_mascara_veste_o_dualsense_com_a_maquina_em_xbox(
    transporte: str,
) -> None:
    """**A MORDIDA.** Com o ``_o_ramo_do_pad`` de volta à máscara da máquina para a seção sem
    máscara, o pad nasce Xbox no uinput e esta régua reprova."""
    d = _daemon(transporte)
    gp.start_gamepad_emulation(d, "xbox", origin="profile")
    perfil = _perfil({"kind": "gamepad", "gamepad_flavor": None})

    d.apply_profile_mode(perfil.mode, profile=perfil, origin="autoswitch")
    gp.reconciliar_as_mascaras(d)

    assert d.config.gamepad_flavor == "dualsense"
    assert vp.caminho_resolvido(d.config.gamepad_caminho, d.config.gamepad_flavor) == "dualsense"
    assert (d._gamepad_device.flavor, d._gamepad_device.backend) == ("dualsense", "uhid"), (
        f"a seção sem máscara vestiu {d._gamepad_device.flavor} ({transporte})")


@pytest.mark.usefixtures("maquina_em_xbox")
@pytest.mark.parametrize("transporte", TRANSPORTES)
def test_sem_a_secao_mode_a_maquina_segue_valendo(transporte: str) -> None:
    """O perfil sem seção `mode` continua sem opinião: veste a máscara da máquina."""
    d = _daemon(transporte)
    gp.start_gamepad_emulation(d, "dualsense", origin="profile")
    perfil = _perfil(None)

    d.apply_profile_mode(perfil.mode, profile=perfil, origin="autoswitch")
    gp.reconciliar_as_mascaras(d)

    assert d.config.gamepad_flavor == "xbox"
    assert d._gamepad_device.flavor == "xbox"


@pytest.mark.usefixtures("maquina_em_xbox")
def test_o_portao_do_jogo_aberto_e_o_boot_fazem_a_mesma_pergunta(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """O pad já de pé no DualSense não se recria pela seção sem máscara, e o boot a restaura
    no mesmo par: a ativação, o portão do jogo aberto e o boot leem o mesmo dono."""
    from hefesto_dualsense4unix.daemon import connection

    d = _daemon("usb")
    gp.start_gamepad_emulation_desfecho(d, "dualsense", origin="profile", caminho="dualsense")
    sem_mascara = ProfileModeConfig(kind="gamepad", gamepad_flavor=None)

    assert not d._modo_seria_destrutivo(sem_mascara)

    perfil = _perfil({"kind": "gamepad", "gamepad_flavor": None})
    monkeypatch.setattr(connection, "perfil_que_o_boot_restaura", lambda *_a, **_k: perfil)
    assert lc._o_modo_do_perfil_do_boot(None) == (None, "dualsense", "Jogo")


@pytest.mark.parametrize("mascara", ["dualsense", "xbox", "nintendo"])
def test_o_perfil_novo_do_jogo_nasce_com_o_par(mascara: str) -> None:
    """O perfil novo do jogo com a ponte confirmada no disco nasce com a seção do escritor
    único, com o caminho do par, sem esperar a migração da partida seguinte."""
    carimbado = _cru("Carimbado", 9931204, ponte={
        "kind": "gamepad", "gamepad_flavor": mascara, "steam_input": False,
        "confirmada_por": "silencio", "confirmada_em": "2026-10-17T04:08:17-03:00"})
    (profiles_dir(ensure=True) / "carimbado.json").write_text(
        json.dumps(carimbado, ensure_ascii=False), encoding="utf-8")

    secao = a10_perfis._o_modo_que_o_jogo_pede(MatchCriteria(window_class=["steam_app_9931204"]))

    assert secao is not None
    assert (secao.caminho, secao.gamepad_flavor) == vp.par_do_modo(mascara)
