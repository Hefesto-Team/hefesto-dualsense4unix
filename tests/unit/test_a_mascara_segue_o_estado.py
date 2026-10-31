"""A máscara que cada boneco veste é a do estado de AGORA, nunca a sobra."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any, get_args

import pytest

from hefesto_dualsense4unix.core.controller import Transport
from hefesto_dualsense4unix.core.evdev_reader import EvdevReader
from hefesto_dualsense4unix.core.numeros_da_sony import roupa_normalizada
from hefesto_dualsense4unix.daemon import lifecycle as lc
from hefesto_dualsense4unix.daemon.lifecycle import Daemon, DaemonConfig
from hefesto_dualsense4unix.daemon.subsystems import gamepad as gp
from hefesto_dualsense4unix.daemon.subsystems.coop import CoopManager, _SecondaryPlayer
from hefesto_dualsense4unix.daemon.subsystems.external_mask import mascara_efetiva
from hefesto_dualsense4unix.integrations import virtual_pad as vp
from hefesto_dualsense4unix.profiles.schema import (
    MascaraDeGamepad,
    Profile,
    ProfileModeConfig,
)
from hefesto_dualsense4unix.testing.fake_controller import FakeController
from hefesto_dualsense4unix.utils import session as session_mod
from hefesto_dualsense4unix.utils.session import save_gamepad_emulation

MAC_P1 = "aa:bb:cc:00:00:01"
SECUNDARIOS = ("aa:bb:cc:00:00:02", "aa:bb:cc:00:00:03", "aa:bb:cc:00:00:04")
MASCARAS_DE_OUTRO_JOGO = sorted(set(get_args(MascaraDeGamepad)) - {"dualsense"})
TRANSPORTES: tuple[Transport, ...] = ("usb", "bt")


class _Pad:
    """Um boneco com o que o produto lê dele: máscara, canal, caminho e roupa."""

    ff_supported = False
    ff_play_count = 0
    ff_nao_nulo_count = 0
    ff_maior_pedido = (0, 0)
    ff_descartado_count = 0
    ff_last_sent = (0, 0)
    eixos_no_jogo: tuple[int, int, int, int] | None = None

    def __init__(self, flavor: str, caminho: str | None, roupa: int | None = None) -> None:
        self.flavor = flavor
        self.caminho = vp.caminho_resolvido(caminho, flavor)
        self.backend = "uhid" if vp.quer_uhid(caminho, flavor) else "uinput"
        self.product = roupa_normalizada(roupa)
        self.parado = False

    def start(self) -> bool:
        return True

    def stop(self) -> None:
        self.parado = True

    def is_active(self) -> bool:
        return not self.parado

    def forward_analog(self, *, lx: int, ly: int, rx: int, ry: int, l2: int, r2: int) -> None:
        return None

    def forward_buttons(self, pressed: frozenset[str]) -> None:
        return None

    def pump_ff(self) -> None:
        return None


class _Leitor(EvdevReader):
    def __init__(self) -> None:
        self._grab_state = "held"


class _ControleDoP1(FakeController):
    primary_uniq: str | None = MAC_P1


def _jogador(mac: str, indice: int, vpad: _Pad) -> _SecondaryPlayer:
    return _SecondaryPlayer(
        identity=mac,
        evdev_path=f"/dev/input/event9{indice}",
        reader=_Leitor(),
        player_index=indice,
        vpad=vpad,
    )


@pytest.fixture(autouse=True)
def _hermetico(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Any:
    """Disco em tmp: o flag da máquina."""
    from hefesto_dualsense4unix.utils import xdg_paths

    alvo = tmp_path / "config"

    def _config_dir(ensure: bool = False) -> Path:
        if ensure:
            alvo.mkdir(parents=True, exist_ok=True)
        return alvo

    monkeypatch.setattr(xdg_paths, "config_dir", _config_dir)
    monkeypatch.setattr(session_mod, "config_dir", _config_dir)
    yield


@pytest.fixture(autouse=True)
def _sem_no_de_kernel(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "hefesto_dualsense4unix.integrations.virtual_pad.make_virtual_pad",
        lambda flavor, **kw: _Pad(
            mascara_efetiva(kw.get("identity"), flavor), kw.get("caminho"), kw.get("roupa")
        ),
    )
    monkeypatch.setattr(
        "hefesto_dualsense4unix.daemon.launch_env.materialize_launch_env",
        lambda _daemon: None,
    )
    monkeypatch.setattr(gp, "_set_controller_grab", lambda *_a: None)


def _daemon(transporte: Transport = "usb") -> Any:
    d = Daemon(
        controller=_ControleDoP1(transport=transporte),
        config=DaemonConfig(ipc_enabled=False, udp_enabled=False),
    )
    d._coop_manager = SimpleNamespace(
        sync=lambda **_k: None,
        disable=lambda: None,
        player_count=lambda: 1,
        algum_boneco_ficou_para_tras=lambda: False,
    )
    d._game_signal = SimpleNamespace(authority="daemon")
    return d


def _jogo_que_opina(d: Any, mascara: MascaraDeGamepad) -> None:
    """O Future Knight: o único perfil do usuário com máscara global."""
    gp.start_gamepad_emulation(d, "dualsense", origin="profile")
    d.apply_profile_mode(ProfileModeConfig(kind="gamepad", gamepad_flavor=mascara), origin="manual")
    assert d._gamepad_device.flavor == mascara, "premissa: o jogo que opina veste a dele"
    assert d.config.gamepad_flavor == mascara, (
        "premissa: o jogo que opina manda na sessão, que é o que os sem cartão herdam"
    )


def _perfil_sem_modo() -> Profile:
    """Um dos 23 perfis do usuário sem seção `mode`, com opinião (criteria)."""
    return Profile.model_validate(
        {
            "name": "Sackboy",
            "version": 1,
            "match": {"type": "criteria", "window_class": ["steam_app_9931993"]},
            "priority": 80,
        }
    )


def _o_proximo_nao_opina(d: Any, jeito: str) -> None:
    """Os três jeitos de um perfil não opinar sobre a máscara global."""
    if jeito == "sem_modo":
        d._mode_from_profile = None
        perfil = _perfil_sem_modo()
        d.apply_profile_mode(perfil.mode, profile=perfil, origin="autoswitch")
        return
    d.apply_profile_mode(
        ProfileModeConfig(kind="gamepad", gamepad_flavor=None, caminho="dualsense"),
        origin="launch",
    )


class TestOJogoSemOpiniaoNaoHerdaAMascaraDoAnterior:
    """MORDIDAS: `flavor_do_jogo = flavor` no `apply_profile_mode` (buraco 1),"""

    @pytest.mark.parametrize("transporte", TRANSPORTES)
    @pytest.mark.parametrize("anterior", MASCARAS_DE_OUTRO_JOGO)
    @pytest.mark.parametrize("jeito", ["sem_cartao", "sem_modo"])
    def test_o_p1_volta_ao_dualsense(
        self, transporte: Transport, anterior: MascaraDeGamepad, jeito: str
    ) -> None:
        d = _daemon(transporte)
        _jogo_que_opina(d, anterior)

        _o_proximo_nao_opina(d, jeito)
        gp.reconciliar_as_mascaras(d)

        assert d.config.gamepad_flavor == "dualsense", (
            f"a sessão ficou com o `{anterior}` do jogo anterior ({jeito}, {transporte})"
        )
        assert d._gamepad_device.flavor == "dualsense", (
            f"o boneco do P1 seguiu `{d._gamepad_device.flavor}` depois de um jogo "
            f"em `{anterior}`: sem giroscópio ({jeito}, {transporte})"
        )
        assert d._gamepad_device.backend == "uhid", "o movimento só chega pelo uhid"

    def test_sem_flag_a_maquina_e_a_de_fabrica_da_sessao(self) -> None:
        assert lc._mascara_da_maquina() == DaemonConfig.gamepad_flavor == "dualsense"

    def test_a_escolha_do_usuario_para_a_maquina_vale(self) -> None:
        """O usuário escolheu Xbox para tudo (o flag, pela CLI): o perfil sem seção `mode` a veste.

        A seção `gamepad` sem máscara é o par do DualSense em todo computador
        (``test_o_gamepad_sem_mascara_tem_uma_regra_so.py``); a da máquina é só do perfil sem
        seção."""
        save_gamepad_emulation(True, "xbox")
        d = _daemon()
        gp.start_gamepad_emulation(d, "dualsense", origin="profile")

        _o_proximo_nao_opina(d, "sem_modo")
        gp.reconciliar_as_mascaras(d)

        assert d._gamepad_device.flavor == "xbox"


class TestOsCartoesChegamDepoisDoModo:
    """MORDIDA: `reconciliar_as_mascaras` devolvendo `None` na primeira linha"""

    @pytest.mark.parametrize("transporte", TRANSPORTES)
    def test_o_modo_novo_refaz_o_boneco_do_p1(self, transporte: Transport) -> None:
        d = _daemon(transporte)
        _jogo_que_opina(d, "xbox")

        d.config.gamepad_flavor = "dualsense"
        gp.reconciliar_as_mascaras(d)

        assert d._gamepad_device.flavor == "dualsense"

    def test_com_o_jogo_na_autoridade_espera_e_depois_converge(self) -> None:
        """A R-04 inteira: ninguém recria o boneco na mão do usuário."""
        d = _daemon()
        _jogo_que_opina(d, "xbox")
        d.config.gamepad_flavor = "dualsense"
        d._game_signal = SimpleNamespace(authority="game")
        antes = d._gamepad_device

        for _ in range(5):
            assert gp.reconciliar_as_mascaras(d) is None
        assert d._gamepad_device is antes and not antes.parado

        d._game_signal = SimpleNamespace(authority="daemon")
        gp.reconciliar_as_mascaras(d)
        assert d._gamepad_device.flavor == "dualsense"

    def test_o_modo_xbox_que_o_usuario_escolheu_nao_e_desfeito(self) -> None:
        """O caminho Xbox com máscara DualSense é uinput de propósito: o juiz
        não pode brigar com ele, nem entrar em laço."""
        d = _daemon()
        gp.start_gamepad_emulation_desfecho(d, "dualsense", origin="profile", caminho="xbox")
        boneco = d._gamepad_device
        assert boneco.backend == "uinput", "premissa"

        for _ in range(10):
            assert gp.reconciliar_as_mascaras(d) is None
        assert d._gamepad_device is boneco

    @pytest.mark.parametrize("estado", ["nativo", "desligado"])
    def test_sem_boneco_nao_ha_o_que_reconciliar(self, estado: str) -> None:
        d = _daemon()
        _jogo_que_opina(d, "xbox")
        if estado == "nativo":
            d._native_mode = True
        else:
            d.config.gamepad_emulation_enabled = False
        antes = d._gamepad_device

        assert gp.reconciliar_as_mascaras(d) is None
        assert d._gamepad_device is antes


class TestAMesaInteiraSegueAMesmaRegra:
    """MORDIDA: tirar `daemon.config.gamepad_flavor = key` do ramo"""

    def test_o_jogo_sem_opiniao_nao_segura_a_sobra_na_sessao(self) -> None:
        d = _daemon()
        _jogo_que_opina(d, "xbox")

        _o_proximo_nao_opina(d, "sem_cartao")

        assert d.config.gamepad_flavor == "dualsense", (
            "a sessão seguiu `xbox`, e todo secundário sem cartão herdaria o Xbox"
        )

    @pytest.mark.parametrize("secundarios", [1, 2, 3])
    def test_o_juiz_ve_o_secundario_que_ficou_para_tras(self, secundarios: int) -> None:
        d = _daemon()
        d.config.gamepad_flavor = "dualsense"
        mesa = CoopManager(d)
        macs = SECUNDARIOS[:secundarios]
        mesa._players = {
            mac: _jogador(mac, i, _Pad("dualsense", None)) for i, mac in enumerate(macs, start=2)
        }
        assert not mesa.algum_boneco_ficou_para_tras(), "premissa: todos certos"

        mesa._players[macs[-1]].vpad = _Pad("xbox", None)
        assert mesa.algum_boneco_ficou_para_tras()

        d.config.gamepad_flavor = "xbox"
        assert mesa.algum_boneco_ficou_para_tras() is (secundarios > 1), (
            "o modo único vale para todos: quem ficou no DualSense ficou para trás"
        )
        for mac in macs:
            mesa._players[mac].vpad = _Pad("xbox", None)
        assert not mesa.algum_boneco_ficou_para_tras()

    def test_o_juiz_manda_o_co_op_refazer_so_sem_o_jogo_na_autoridade(self) -> None:
        d = _daemon()
        gp.start_gamepad_emulation(d, "dualsense", origin="profile")
        forcados: list[bool] = []
        d._coop_manager = SimpleNamespace(
            sync=lambda **k: forcados.append(bool(k.get("force"))),
            algum_boneco_ficou_para_tras=lambda: True,
        )

        d._game_signal = SimpleNamespace(authority="game")
        gp.reconciliar_as_mascaras(d)
        assert forcados == []

        d._game_signal = SimpleNamespace(authority="daemon")
        gp.reconciliar_as_mascaras(d)
        assert forcados == [True]


class TestOPortaoDoJogoAbertoPreveARecriacao:
    """MORDIDA: devolver ao `_modo_seria_destrutivo` a comparação velha"""

    def test_o_perfil_sem_opiniao_sobre_um_boneco_xbox_recriaria(self) -> None:
        d = _daemon()
        _jogo_que_opina(d, "xbox")
        sem_opiniao = ProfileModeConfig(kind="gamepad", gamepad_flavor=None)

        assert d._modo_seria_destrutivo(sem_opiniao)

    def test_o_mesmo_perfil_sobre_um_boneco_certo_nao_recriaria(self) -> None:
        d = _daemon()
        gp.start_gamepad_emulation(d, "dualsense", origin="profile")
        sem_opiniao = ProfileModeConfig(kind="gamepad", gamepad_flavor=None)

        assert not d._modo_seria_destrutivo(sem_opiniao)
