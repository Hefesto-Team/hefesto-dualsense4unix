"""A máscara que cada boneco veste é a do estado de AGORA, nunca a sobra.

A-MASCARA-SEGUE-O-ESTADO-01 (25/09/2026). Medido na máquina dela depois do
boot, com o diário na mão:

    00:00:44  profile_activated 'Future Knight' origin=manual   (global `xbox`)
    00:00:43  gamepad_emulation_started flavor=xbox mascara_do_p1=xbox
    00:05:31  launch_allowlist_so_a_mascara mascara_do_perfil=None mascara_viva=xbox
    00:05:31  profile_mascara_por_peca mascara=dualsense profile=PRAGMATA  (x4)
    ...       o boneco do P1 seguiu Xbox até ela desistir

O PRAGMATA venceu pela prioridade e gravou `dualsense` nos quatro cartões, e o
jogo viu um Xbox 360: sem giroscópio e sem acelerômetro. Três buracos, todos
curados na origem, e esta bateria mede os três em toda mesa (os três jeitos de
um perfil não opinar, cabo e BT, de um a quatro jogadores, os modos Xbox e
Nativo):

1. o perfil sem máscara global herdava a do jogo anterior, que ficava na
   sessão (`config.gamepad_flavor`); agora vale a da MÁQUINA (o flag dela);
2. o boneco do P1 só era refeito pelo evento que PEDIA máscara global, e os
   cartões chegam depois do modo; agora há um juiz para os quatro
   (`gamepad.reconciliar_as_mascaras`), no compasso do co-op;
3. com o P1 já certo pelo cartão, a sessão ficava com a sobra, e o P2 sem
   cartão seguia em Xbox.

Cada classe diz a mordida que a derruba.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any, get_args

import pytest

from hefesto_dualsense4unix.daemon import lifecycle as lc
from hefesto_dualsense4unix.daemon.lifecycle import Daemon, DaemonConfig
from hefesto_dualsense4unix.daemon.subsystems import gamepad as gp
from hefesto_dualsense4unix.daemon.subsystems.coop import CoopManager
from hefesto_dualsense4unix.daemon.subsystems.external_mask import (
    _zerar_registro_de_mascaras,
    mascara_efetiva,
    registro_de_mascaras,
)
from hefesto_dualsense4unix.integrations import virtual_pad as vp
from hefesto_dualsense4unix.profiles.schema import (
    MascaraDeGamepad,
    Profile,
    ProfileModeConfig,
)
from hefesto_dualsense4unix.testing.fake_controller import FakeController
from hefesto_dualsense4unix.utils import session as session_mod
from hefesto_dualsense4unix.utils.session import save_gamepad_emulation

#: A mesa forjada da casa (octetos 4 e 5 zerados).
MAC_P1 = "aa:bb:cc:00:00:01"
SECUNDARIOS = ("aa:bb:cc:00:00:02", "aa:bb:cc:00:00:03", "aa:bb:cc:00:00:04")
#: Toda máscara que um jogo pode declarar e que não é a de fábrica.
MASCARAS_DE_OUTRO_JOGO = sorted(set(get_args(MascaraDeGamepad)) - {"dualsense"})
TRANSPORTES = ("usb", "bt")


class _Pad:
    """Um boneco com o que o produto lê dele: máscara, canal e caminho.

    O canal sai de `virtual_pad.quer_uhid`, a mesma função do produto: cravar
    `uhid` aqui passaria verde com o gate do canal quebrado.
    """

    def __init__(self, flavor: str, caminho: str | None) -> None:
        self.flavor = flavor
        self.caminho = vp.caminho_resolvido(caminho, flavor)
        self.backend = "uhid" if vp.quer_uhid(caminho, flavor) else "uinput"
        self.parado = False

    def stop(self) -> None:
        self.parado = True


@pytest.fixture(autouse=True)
def _hermetico(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Any:
    """Disco em tmp (o flag e os cartões) e o registro zerado antes e depois."""
    from hefesto_dualsense4unix.utils import xdg_paths

    alvo = tmp_path / "config"

    def _config_dir(ensure: bool = False) -> Path:
        if ensure:
            alvo.mkdir(parents=True, exist_ok=True)
        return alvo

    monkeypatch.setattr(xdg_paths, "config_dir", _config_dir)
    monkeypatch.setattr(session_mod, "config_dir", _config_dir)
    _zerar_registro_de_mascaras()
    yield
    _zerar_registro_de_mascaras()


@pytest.fixture(autouse=True)
def _sem_no_de_kernel(monkeypatch: pytest.MonkeyPatch) -> None:
    # A fábrica real resolve `mascara_efetiva(identity, flavor)` por dentro;
    # um dublê que usasse só o `flavor` seria mais pobre que o produto e
    # reprovaria o cartão que o produto honra.
    monkeypatch.setattr(
        "hefesto_dualsense4unix.integrations.virtual_pad.make_virtual_pad",
        lambda flavor, **kw: _Pad(mascara_efetiva(kw.get("identity"), flavor), kw.get("caminho")),
    )
    monkeypatch.setattr(
        "hefesto_dualsense4unix.daemon.launch_env.materialize_launch_env",
        lambda _daemon: None,
    )
    monkeypatch.setattr(gp, "_set_controller_grab", lambda *_a: None)


def _daemon(transporte: str = "usb") -> Any:
    d = Daemon(
        controller=FakeController(transport=transporte),
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


def _jogo_que_opina(d: Any, mascara: str) -> None:
    """O Future Knight: o único perfil dela com máscara global."""
    gp.start_gamepad_emulation(d, "dualsense", origin="profile")
    d.apply_profile_mode(ProfileModeConfig(kind="gamepad", gamepad_flavor=mascara), origin="manual")
    assert d._gamepad_device.flavor == mascara, "premissa: o jogo que opina veste a dele"
    assert d.config.gamepad_flavor == mascara, (
        "premissa: o jogo que opina manda na sessão, que é o que os sem cartão herdam"
    )


def _perfil_sem_modo() -> Profile:
    """Um dos 23 perfis dela sem seção `mode`, com opinião (criteria)."""
    return Profile.model_validate(
        {
            "name": "Sackboy",
            "version": 1,
            "match": {"type": "criteria", "window_class": ["steam_app_1599660"]},
            "priority": 80,
        }
    )


def _o_proximo_nao_opina(d: Any, jeito: str) -> None:
    """Os três jeitos de um perfil não opinar sobre a máscara global."""
    if jeito == "sem_modo":
        d._mode_from_profile = None  # o boneco é dela, e fica de pé
        perfil = _perfil_sem_modo()
        d.apply_profile_mode(perfil.mode, profile=perfil, origin="autoswitch")
        return
    if jeito == "com_cartao":  # o PRAGMATA: os cartões em `dualsense`
        registro_de_mascaras().set_mask(MAC_P1, "dualsense")
    d.apply_profile_mode(
        ProfileModeConfig(kind="gamepad", gamepad_flavor=None, caminho="dualsense"),
        origin="launch",
    )


class TestOJogoSemOpiniaoNaoHerdaAMascaraDoAnterior:
    """MORDIDAS: `flavor_do_jogo = flavor` no `apply_profile_mode` (buraco 1),
    ou tirar a linha da sessão no ramo sem `mode`, ou o
    `_mascara_da_maquina` caindo no `normalize_flavor(None)`."""

    @pytest.mark.parametrize("transporte", TRANSPORTES)
    @pytest.mark.parametrize("anterior", MASCARAS_DE_OUTRO_JOGO)
    @pytest.mark.parametrize("jeito", ["com_cartao", "sem_cartao", "sem_modo"])
    def test_o_p1_volta_ao_dualsense(self, transporte: str, anterior: str, jeito: str) -> None:
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

    def test_a_escolha_dela_para_a_maquina_vale(self) -> None:
        """Ela escolheu Xbox para tudo (o flag, pela CLI): o jogo sem opinião
        obedece a ela, e não ao `dualsense` de fábrica."""
        save_gamepad_emulation(True, "xbox")
        d = _daemon()
        gp.start_gamepad_emulation(d, "dualsense", origin="profile")

        _o_proximo_nao_opina(d, "sem_cartao")
        gp.reconciliar_as_mascaras(d)

        assert d._gamepad_device.flavor == "xbox"


class TestOsCartoesChegamDepoisDoModo:
    """MORDIDA: `reconciliar_as_mascaras` devolvendo `None` na primeira linha
    (buraco 2). O gerente aplica o modo ANTES dos cartões, e o P1 decidia com
    os cartões do perfil anterior."""

    @pytest.mark.parametrize("transporte", TRANSPORTES)
    def test_o_cartao_novo_refaz_o_boneco_do_p1(self, transporte: str) -> None:
        d = _daemon(transporte)
        _jogo_que_opina(d, "xbox")

        registro_de_mascaras().set_mask(MAC_P1, "dualsense")
        gp.reconciliar_as_mascaras(d)

        assert d._gamepad_device.flavor == "dualsense"

    def test_com_o_jogo_na_autoridade_espera_e_depois_converge(self) -> None:
        """A R-04 inteira: ninguém recria o boneco na mão dela."""
        d = _daemon()
        _jogo_que_opina(d, "xbox")
        registro_de_mascaras().set_mask(MAC_P1, "dualsense")
        d._game_signal = SimpleNamespace(authority="game")
        antes = d._gamepad_device

        for _ in range(5):
            assert gp.reconciliar_as_mascaras(d) is None
        assert d._gamepad_device is antes and not antes.parado

        d._game_signal = SimpleNamespace(authority="daemon")
        gp.reconciliar_as_mascaras(d)
        assert d._gamepad_device.flavor == "dualsense"

    def test_o_modo_xbox_que_ela_escolheu_nao_e_desfeito(self) -> None:
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
    """MORDIDA: tirar `daemon.config.gamepad_flavor = key` do ramo
    `EMU_JA_ESTAVA` do `start_gamepad_emulation_desfecho` (buraco 3)."""

    def test_o_p1_certo_pelo_cartao_nao_segura_a_sobra_na_sessao(self) -> None:
        d = _daemon()
        registro_de_mascaras().set_mask(MAC_P1, "xbox")  # o cartão é escolha dela
        _jogo_que_opina(d, "xbox")
        boneco = d._gamepad_device

        _o_proximo_nao_opina(d, "sem_cartao")

        assert d._gamepad_device is boneco, "o cartão dela (xbox) é respeitado"
        assert d.config.gamepad_flavor == "dualsense", (
            "a sessão seguiu `xbox`, e todo secundário sem cartão herdaria o Xbox"
        )

    @pytest.mark.parametrize("secundarios", [1, 2, 3])
    def test_o_juiz_ve_o_secundario_que_ficou_para_tras(self, secundarios: int) -> None:
        d = _daemon()
        d.config.gamepad_flavor = "dualsense"
        mesa = CoopManager(d)
        macs = SECUNDARIOS[:secundarios]
        mesa._players = {mac: SimpleNamespace(vpad=_Pad("dualsense", None)) for mac in macs}
        assert not mesa.algum_boneco_ficou_para_tras(), "premissa: todos certos"

        mesa._players[macs[-1]].vpad = _Pad("xbox", None)
        assert mesa.algum_boneco_ficou_para_tras()

        registro_de_mascaras().set_mask(macs[-1], "xbox")  # agora é escolha dela
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
    """MORDIDA: devolver ao `_modo_seria_destrutivo` a comparação velha
    (`flavor is not None and flavor != flavor_atual`). Com o jogo na
    autoridade ele dizia «não destrói» e a pendência não segurava nada."""

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
