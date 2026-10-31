"""OS-LEITORES-DO-PAR-PERGUNTAM-AO-DONO-01 — quem lê o par da seção `gamepad` pergunta ao dono.

Medido em 31/10/2026, na conferência da O-GAMEPAD-SEM-MASCARA-TEM-UMA-REGRA-SO-01: a seção
`gamepad` tem um dono só para o par (``virtual_pad.par_da_secao_do_gamepad``), e três leitores
seguiam com regra própria. O prognóstico do lançamento (``launch_env._mascara_prevista``) dava à
seção sem máscara a máscara vigente; a escada (``ponte_escada.ponte_do_perfil``) dava à mesma
seção a ponte sem caminho; e o perfil sem seção `mode`, ativado depois de um perfil de caminho
`xbox`, seguia no caminho `xbox` (o diário dizia ``caminho=xbox flavor=dualsense``), por cabo e
por rádio.

O ENSAIO: o daemon é o de verdade, com a fábrica do pad dublada por um boneco que guarda a
máscara, o caminho e o canal que o produto pediu, e o disco num ``config`` de mentira.
"""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest

from hefesto_dualsense4unix.daemon import launch_env as le
from hefesto_dualsense4unix.daemon import lifecycle as lc
from hefesto_dualsense4unix.daemon.lifecycle import Daemon, DaemonConfig
from hefesto_dualsense4unix.daemon.subsystems import gamepad as gp
from hefesto_dualsense4unix.daemon.subsystems.coop import CoopManager
from hefesto_dualsense4unix.daemon.subsystems.external_mask import mascara_efetiva
from hefesto_dualsense4unix.integrations import ponte_escada as pe
from hefesto_dualsense4unix.integrations import virtual_pad as vp
from hefesto_dualsense4unix.profiles.schema import Profile, ProfileModeConfig
from hefesto_dualsense4unix.testing.fake_controller import FakeController
from hefesto_dualsense4unix.utils import session as session_mod
from hefesto_dualsense4unix.utils.session import save_gamepad_emulation

MAC_P1 = "aa:bb:cc:00:00:01"
SECUNDARIOS = ("aa:bb:cc:00:00:02", "aa:bb:cc:00:00:03", "aa:bb:cc:00:00:04")
TRANSPORTES = ("usb", "bt")
OS_CAMINHOS_XBOX = (("xbox", "xbox"), ("xbox", "dualsense"))

OS_PARES_DA_SECAO: list[tuple[str | None, str | None]] = [
    (None, None),
    ("dualsense", None),
    ("xbox", None),
    (None, "dualsense"),
    (None, "xbox"),
    (None, "nintendo"),
    ("dualsense", "dualsense"),
    ("xbox", "xbox"),
    ("xbox", "dualsense"),
]


def _perfil(mode: dict[str, Any] | None) -> Profile:
    dados: dict[str, Any] = {
        "name": "Jogo Sem Nome",
        "version": 1,
        "match": {"type": "criteria", "window_class": ["steam_app_9931993"]},
        "priority": 80,
    }
    if mode is not None:
        dados["mode"] = mode
    return Profile.model_validate(dados)


def _secao(caminho: str | None, mascara: str | None) -> dict[str, Any]:
    return {"kind": "gamepad", "caminho": caminho, "gamepad_flavor": mascara}


class TestOsLeitoresDaSecaoPerguntamAoDono:
    """MORDIDAS: o ``or flavor_atual`` de volta no ``_mascara_prevista``; o ``mode.caminho or
    mode.gamepad_flavor`` de volta no ``ponte_do_perfil``."""

    @pytest.mark.parametrize("vigente", ["xbox", "nintendo", "dualsense"])
    @pytest.mark.parametrize(("caminho", "mascara"), OS_PARES_DA_SECAO)
    def test_o_prognostico_do_lancamento_veste_o_que_o_daemon_veste(
        self, caminho: str | None, mascara: str | None, vigente: str
    ) -> None:
        perfil = _perfil(_secao(caminho, mascara))

        prevista = le._mascara_prevista(
            perfil, perfil.mode, flavor_atual=vigente, identidade=None)

        assert prevista == lc._o_par_do_pad(perfil.mode)[1], (
            f"o prognóstico ({prevista}) diverge do daemon para a seção {caminho}/{mascara} "
            f"com a vigente {vigente}")

    @pytest.mark.parametrize("vigente", ["xbox", "nintendo"])
    def test_a_secao_sem_par_abre_com_a_env_do_dualsense(self, vigente: str) -> None:
        perfil = _perfil(_secao(None, None))

        modo = le._modo_antecipado(perfil, flavor_atual=vigente, backends=["uinput"])

        assert modo is not None and modo.mascara == "dualsense", (
            f"a seção sem par previu {getattr(modo, 'mascara', None)}, a vigente da máquina")

    @pytest.mark.parametrize(("caminho", "mascara"), OS_PARES_DA_SECAO)
    @pytest.mark.parametrize("na_allowlist", [False, True])
    def test_a_ponte_do_perfil_e_o_caminho_do_par_do_dono(
        self, caminho: str | None, mascara: str | None, na_allowlist: bool
    ) -> None:
        perfil = _perfil(_secao(caminho, mascara))

        ponte = pe.ponte_do_perfil(perfil, na_allowlist=na_allowlist)

        par = vp.par_da_secao_do_gamepad(caminho, mascara)
        assert ponte == pe.Ponte("gamepad", par[0], steam_input=na_allowlist)

    def test_a_secao_sem_par_e_o_primeiro_degrau(self) -> None:
        perfil = _perfil(_secao(None, None))

        assert pe.ponte_do_perfil(perfil, na_allowlist=False) == pe.ESCADA[0].ponte

    def test_o_perfil_sem_secao_segue_sem_opiniao(self) -> None:
        perfil = _perfil(None)

        assert pe.ponte_do_perfil(perfil, na_allowlist=False) is None
        assert le._modo_antecipado(perfil, flavor_atual="xbox", backends=[]) is None


class _Pad:
    """O boneco do vpad: a máscara, o caminho e o canal que o produto pediu."""

    def __init__(self, flavor: str, caminho: str | None) -> None:
        self.flavor = flavor
        self.caminho = vp.caminho_resolvido(caminho, flavor)
        self.backend = "uhid" if vp.quer_uhid(caminho, flavor) else "uinput"
        self.parado = False

    def stop(self) -> None:
        self.parado = True


@pytest.fixture(autouse=True)
def _hermetico(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from hefesto_dualsense4unix.utils import xdg_paths

    alvo = tmp_path / "config"

    def _config_dir(ensure: bool = False) -> Path:
        if ensure:
            alvo.mkdir(parents=True, exist_ok=True)
        return alvo

    monkeypatch.setattr(xdg_paths, "config_dir", _config_dir)
    monkeypatch.setattr(session_mod, "config_dir", _config_dir)


@pytest.fixture(autouse=True)
def _sem_no_de_kernel(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "hefesto_dualsense4unix.integrations.virtual_pad.make_virtual_pad",
        lambda flavor, **kw: _Pad(mascara_efetiva(kw.get("identity"), flavor), kw.get("caminho")),
    )
    monkeypatch.setattr(
        "hefesto_dualsense4unix.daemon.launch_env.materialize_launch_env",
        lambda _daemon: None,
    )
    monkeypatch.setattr(gp, "_set_controller_grab", lambda *_a: None)


def _daemon(transporte: str) -> Any:
    d: Any = Daemon(
        controller=FakeController(transport=cast("Any", transporte)),
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


def _o_jogo_de_caminho_xbox(d: Any, caminho: str, mascara: str) -> None:
    """O P1 de pé no caminho `xbox`, pelo perfil do jogo anterior."""
    gp.start_gamepad_emulation(d, "dualsense", origin="profile")
    d.apply_profile_mode(
        ProfileModeConfig(kind="gamepad", caminho=caminho, gamepad_flavor=mascara),  # type: ignore[arg-type]
        origin="manual",
    )
    assert d._gamepad_device.backend == "uinput", "premissa: o caminho xbox é uinput"
    assert gp.caminho_da_sessao(d) == "xbox", "premissa: a sessão está no caminho xbox"


def _o_perfil_sem_secao(d: Any, *, dono_do_pad: str | None) -> None:
    """Ativa um perfil sem seção `mode` (com opinião: casa por janela)."""
    d._mode_from_profile = dono_do_pad
    perfil = _perfil(None)
    d.apply_profile_mode(perfil.mode, profile=perfil, origin="autoswitch")


class TestOPerfilSemSecaoNaoHerdaOCaminhoDoAnterior:
    """MORDIDA: o ramo do perfil sem seção `mode` sem levar o caminho da sessão ao da máquina
    (só a máscara), como era."""

    @pytest.mark.parametrize("transporte", TRANSPORTES)
    @pytest.mark.parametrize(("caminho", "mascara"), OS_CAMINHOS_XBOX)
    @pytest.mark.parametrize("dono_do_pad", [None, "gamepad"])
    def test_o_p1_volta_ao_caminho_da_maquina(
        self, transporte: str, caminho: str, mascara: str, dono_do_pad: str | None
    ) -> None:
        save_gamepad_emulation(True, "dualsense")
        d = _daemon(transporte)
        _o_jogo_de_caminho_xbox(d, caminho, mascara)

        _o_perfil_sem_secao(d, dono_do_pad=dono_do_pad)
        gp.reconciliar_as_mascaras(d)

        assert gp.caminho_da_sessao(d) is None, (
            f"a sessão seguiu no caminho {gp.caminho_da_sessao(d)} do perfil {caminho}/{mascara}")
        assert d._gamepad_device.flavor == "dualsense"
        assert d._gamepad_device.caminho == "dualsense", (
            f"o P1 seguiu no caminho {d._gamepad_device.caminho} ({transporte})")
        assert d._gamepad_device.backend == "uhid", "o movimento só chega pelo uhid"

    @pytest.mark.parametrize("transporte", TRANSPORTES)
    def test_com_a_maquina_em_xbox_o_p1_segue_a_maquina(self, transporte: str) -> None:
        save_gamepad_emulation(True, "xbox")
        d = _daemon(transporte)
        _o_jogo_de_caminho_xbox(d, "xbox", "dualsense")

        _o_perfil_sem_secao(d, dono_do_pad=None)
        gp.reconciliar_as_mascaras(d)

        assert gp.caminho_da_sessao(d) is None
        assert (d._gamepad_device.flavor, d._gamepad_device.backend) == ("xbox", "uinput")

    @pytest.mark.parametrize("secundarios", [1, 2, 3])
    @pytest.mark.parametrize(("caminho", "mascara"), OS_CAMINHOS_XBOX)
    def test_os_secundarios_saem_do_caminho_xbox(
        self, secundarios: int, caminho: str, mascara: str
    ) -> None:
        save_gamepad_emulation(True, "dualsense")
        d = _daemon("bt")
        _o_jogo_de_caminho_xbox(d, caminho, mascara)
        mesa: Any = CoopManager(d)
        macs = SECUNDARIOS[:secundarios]
        mesa._players = {
            mac: SimpleNamespace(vpad=_Pad("dualsense", "xbox")) for mac in macs}

        _o_perfil_sem_secao(d, dono_do_pad=None)

        assert mesa.algum_boneco_ficou_para_tras(), (
            "os secundários no caminho xbox não ficaram para trás: a sessão seguiu em xbox")
        for mac in macs:
            mesa._players[mac].vpad = _Pad("dualsense", None)
        assert not mesa.algum_boneco_ficou_para_tras()

    def test_o_perfil_catch_all_sem_opiniao_nao_mexe_no_caminho(self) -> None:
        save_gamepad_emulation(True, "dualsense")
        d = _daemon("usb")
        _o_jogo_de_caminho_xbox(d, "xbox", "xbox")
        catch_all = Profile.model_validate(
            {"name": "Padrão", "version": 1, "match": {"type": "any"}, "priority": 0})

        d.apply_profile_mode(None, profile=catch_all, origin="autoswitch")

        assert gp.caminho_da_sessao(d) == "xbox"
