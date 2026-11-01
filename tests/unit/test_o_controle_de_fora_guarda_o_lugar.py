"""O controle de fora guarda o lugar como o DualSense.

O assento é do jogador, não do tipo de controle (D-3009-COM-O-JOGO-O-LUGAR-GUARDADO-ESPERA):

1. com o jogo aberto, o Pro (ou o 8BitDo) que dirige o pad do P1 segue no boneco 1 quando um
   DualSense chega, e o DualSense senta no primeiro lugar livre; sem jogo, a carta manda;
2. o de fora sentado no P2 assume o P1 que ficou vago só quando o lugar guardado do número 1
   vence (com o jogo, o prazo para e só o «Renumerar agora» solta); o guardado de outro número
   não o atrasa;
3. o quadro neutro do pad que o de fora larga sai antes do primeiro despacho do DualSense.

O backend é o real no ensaio de queda (``MesaDoJogo``), no cabo e no rádio; o co-op é o real
com o Pro da mesa do acionador, e o lugar guardado é o do ``ControllerIdentityRegistry`` de
verdade. Nenhum endereço real: faixa forjada ``aa:bb:cc``.
"""
from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from hefesto_dualsense4unix.daemon.subsystems import coop as coop_mod
from hefesto_dualsense4unix.daemon.subsystems import gamepad as gamepad_mod
from hefesto_dualsense4unix.daemon.subsystems.coop import CoopManager
from hefesto_dualsense4unix.daemon.subsystems.identity import (
    ControllerIdentityRegistry,
    prazo_do_lugar_guardado,
)
from tests.unit.test_o_acionador_entrega_a_um_controle_de_fora import (
    P1,
    PRO,
    _Broker,
    _daemon,
    _PadDoP1,
    mesa,
)
from tests.unit.test_o_jogo_espera_a_carta_do_lugar_guardado import (
    UNIQS,
    MesaDoJogo,
    Relogio,
    config_isolado,
)

__all__ = ["config_isolado", "mesa"]

MASCARAS = pytest.mark.parametrize("mascara", ["dualsense", "xbox"])
VIAS = pytest.mark.parametrize("via", ["usb", "bt"])
NEUTRO = {"lx": 128, "ly": 128, "rx": 128, "ry": 128, "l2": 0, "r2": 0}
QUADRO_DO_DUALSENSE = {"lx": 7, "ly": 128, "rx": 128, "ry": 128, "l2": 0, "r2": 0}


class _Backend(SimpleNamespace):
    """O que o co-op lê do backend: o primário e as perguntas penduradas."""

    def set_o_p1_com_o_de_fora(self, pergunta: Any) -> None:
        self.p1_com_o_de_fora = pergunta

    def set_primary_change_observer(self, fn: Any) -> None:
        self.observador = fn


def _mesa_com_o_pro(
    monkeypatch: pytest.MonkeyPatch, mascara: str, *, jogo: bool
) -> tuple[CoopManager, Any, dict[str, str]]:
    dualsenses: dict[str, str] = {}
    monkeypatch.setattr(
        "hefesto_dualsense4unix.core.evdev_reader.discover_dualsense_evdevs",
        lambda: dict(dualsenses),
    )
    pad: Any = _PadDoP1()
    pad.flavor = mascara
    daemon: Any = _daemon(_Broker())
    daemon.config.gamepad_flavor = mascara
    daemon._gamepad_device = pad
    daemon.display_authority = "game" if jogo else "daemon"
    daemon.controller = _Backend(
        primary_uniq=None,
        _evdev=SimpleNamespace(_device_path=None),
        is_connected=lambda: bool(dualsenses),
    )
    mgr = CoopManager(daemon)
    daemon._coop_manager = mgr
    mgr.sync()
    mgr.sync(force=True)
    assert mgr.o_de_fora_no_p1() is mgr._players[PRO]
    return mgr, pad, dualsenses


def _chega_o_dualsense(mgr: CoopManager, dualsenses: dict[str, str]) -> None:
    """O hotplug: o backend senta o DualSense no posto só se a pergunta pendurada deixa."""
    ctrl: Any = mgr._daemon.controller
    dualsenses[P1] = "/dev/input/event20"
    if not ctrl.p1_com_o_de_fora():
        ctrl.primary_uniq = P1
        ctrl.observador(None, P1)


@pytest.mark.usefixtures("config_isolado")
class TestOBackendDeixaOPostoComODeFora:
    """O backend real: a pergunta pendurada segura o posto, no cabo e no rádio."""

    @VIAS
    def test_o_dualsense_que_chega_nao_senta_no_posto_enquanto_o_de_fora_segue(
        self, monkeypatch: pytest.MonkeyPatch, via: str
    ) -> None:
        relogio = Relogio()
        ensaio = MesaDoJogo(monkeypatch, relogio=relogio, tempo=relogio, jogo=True)
        segue = [True]
        ensaio.inst.set_o_p1_com_o_de_fora(lambda: segue[0])
        ensaio.mesa.sentar(UNIQS[0], transporte=via)
        ensaio.connect()
        ensaio.inst.seguir_a_carta()

        assert ensaio.inst.primary_uniq is None
        assert ensaio.inst.read_state().connected, "o posto ocupado pelo de fora não é queda"

        segue[0] = False
        ensaio.inst.seguir_a_carta()
        assert ensaio.inst.primary_uniq == UNIQS[0]

    @VIAS
    def test_o_dualsense_deposto_que_volta_nao_retoma_o_posto_do_de_fora(
        self, monkeypatch: pytest.MonkeyPatch, via: str
    ) -> None:
        relogio = Relogio()
        ensaio = MesaDoJogo(monkeypatch, relogio=relogio, tempo=relogio, jogo=True)
        segue = [False]
        ensaio.inst.set_o_p1_com_o_de_fora(lambda: segue[0])
        ensaio.mesa.sentar(UNIQS[0], transporte=via)
        ensaio.connect()
        ensaio.inst.seguir_a_carta()
        assert ensaio.inst.primary_uniq == UNIQS[0]

        ensaio.mesa.levantar(UNIQS[0])
        ensaio.connect()
        segue[0] = True
        relogio.avancar(5.0)
        ensaio.mesa.sentar(UNIQS[0], transporte=via)
        ensaio.connect()
        ensaio.inst.seguir_a_carta()
        assert ensaio.inst.primary_uniq is None, (
            "o DualSense que voltou na janela da reserva retomou o posto que o de fora segura"
        )
        assert ensaio.inst.read_state().connected

        segue[0] = False
        ensaio.inst.seguir_a_carta()
        assert ensaio.inst.primary_uniq == UNIQS[0]


@pytest.mark.usefixtures("mesa")
class TestComOJogoQuemJogaFicaNoLugar:
    """Item 1: o Pro no P1 com o jogo aberto, e chega um DualSense."""

    @MASCARAS
    def test_o_pro_segue_no_p1_e_o_dualsense_senta_no_p2(
        self, monkeypatch: pytest.MonkeyPatch, mascara: str
    ) -> None:
        mgr, pad, dualsenses = _mesa_com_o_pro(monkeypatch, mascara, jogo=True)
        pro = mgr._players[PRO]

        _chega_o_dualsense(mgr, dualsenses)
        mgr.sync(force=True)
        mgr.forward_all()

        daemon: Any = mgr._daemon
        assert daemon.controller.primary_uniq is None
        assert pro.no_p1 and pro.vpad is pad and pro.player_index == 1
        assert mgr._players[P1].player_index == 2 and mgr._players[P1].vpad is not pad
        assert coop_mod.o_p1_e_do_de_fora(mgr._daemon)

    @MASCARAS
    def test_o_despacho_do_posto_vazio_nao_pisa_no_pro(
        self, monkeypatch: pytest.MonkeyPatch, mascara: str
    ) -> None:
        mgr, _pad, dualsenses = _mesa_com_o_pro(monkeypatch, mascara, jogo=True)
        _chega_o_dualsense(mgr, dualsenses)
        mgr.sync(force=True)
        pisou: list[str] = []

        def _apertos(*_a: Any) -> tuple[frozenset[str], frozenset[str]]:
            pisou.append("despacho")
            return frozenset(), frozenset()

        monkeypatch.setattr(gamepad_mod, "_apertos_do_primario", _apertos)
        for nome in ("_avisar_troca_de_modo", "bater_a_vibracao", "_bater_os_eventos_do_jogo"):
            monkeypatch.setattr(gamepad_mod, nome, lambda _d: None)

        gamepad_mod.dispatch_gamepad(mgr._daemon, SimpleNamespace(), frozenset())

        assert pisou == [], "o estado vazio do posto foi ao pad que o Pro dirige"

    @MASCARAS
    def test_sem_jogo_a_carta_manda(
        self, monkeypatch: pytest.MonkeyPatch, mascara: str
    ) -> None:
        mgr, pad, dualsenses = _mesa_com_o_pro(monkeypatch, mascara, jogo=False)
        pro = mgr._players[PRO]

        _chega_o_dualsense(mgr, dualsenses)
        mgr.sync(force=True)

        daemon: Any = mgr._daemon
        assert daemon.controller.primary_uniq == P1
        assert not pro.no_p1 and pro.vpad is not pad and pro.player_index >= 2

    @MASCARAS
    def test_o_jogo_que_fecha_devolve_a_carta(
        self, monkeypatch: pytest.MonkeyPatch, mascara: str
    ) -> None:
        mgr, pad, dualsenses = _mesa_com_o_pro(monkeypatch, mascara, jogo=True)
        pro = mgr._players[PRO]
        _chega_o_dualsense(mgr, dualsenses)
        mgr.sync(force=True)

        daemon: Any = mgr._daemon
        daemon.display_authority = "daemon"
        ctrl = daemon.controller
        assert not ctrl.p1_com_o_de_fora()
        ctrl.primary_uniq = P1
        ctrl.observador(None, P1)
        mgr.sync(force=True)

        assert not pro.no_p1 and pro.vpad is not pad and pro.player_index >= 2


@pytest.mark.usefixtures("mesa")
class TestOQuadroNeutroVemAntes:
    """Item 3: o pad do P1 não recebe quadro neutro depois do primeiro do DualSense."""

    @MASCARAS
    def test_nenhum_neutro_depois_do_primeiro_quadro_do_dualsense(
        self, monkeypatch: pytest.MonkeyPatch, mascara: str
    ) -> None:
        mgr, pad, dualsenses = _mesa_com_o_pro(monkeypatch, mascara, jogo=False)
        pad.analogicos.clear()

        _chega_o_dualsense(mgr, dualsenses)
        pad.forward_analog(**QUADRO_DO_DUALSENSE)
        mgr.forward_all()
        mgr.sync(force=True)
        mgr.forward_all()

        assert QUADRO_DO_DUALSENSE in pad.analogicos
        depois = pad.analogicos[pad.analogicos.index(QUADRO_DO_DUALSENSE) + 1 :]
        assert NEUTRO not in depois, f"o neutro caiu depois do DualSense: {pad.analogicos}"
        assert NEUTRO in pad.analogicos[: pad.analogicos.index(QUADRO_DO_DUALSENSE)]


RANK_DO_PRO = 2
P3 = "aabbcc000005"


def _registro(relogio: Relogio, outros: tuple[str, ...]) -> ControllerIdentityRegistry:
    """O registro de verdade: o P1 no lugar 1 da fila, o Pro no 2 e os ``outros`` depois."""
    registro = ControllerIdentityRegistry(clock=relogio)
    registro.slot_for(P1)
    registro.set_external_reserve_provider(lambda: {RANK_DO_PRO})
    registro.set_external_presence_provider(lambda: {RANK_DO_PRO})
    for uniq in outros:
        registro.slot_for(uniq)
    registro.sync_connected([P1, *outros])
    assert registro.posto_na_fila(P1) == 1
    return registro


def _o_prazo_passa(relogio: Relogio) -> None:
    relogio.avancar(prazo_do_lugar_guardado() + 1.0)


@pytest.mark.usefixtures("mesa", "config_isolado")
class TestOP1VagoSoDepoisDoPrazo:
    """Item 2: o DualSense do P1 sai de vez, e o Pro sentado no P2 espera o prazo."""

    @MASCARAS
    def test_o_pro_do_p2_assume_o_p1_quando_o_lugar_vence(
        self, monkeypatch: pytest.MonkeyPatch, mascara: str
    ) -> None:
        mgr, pad, dualsenses, registro, relogio = _mesa_com_o_dualsense_no_p1(
            monkeypatch, mascara, jogo=False
        )
        pro = mgr._players[PRO]
        proprio: Any = pro.vpad
        proprio.flavor = mascara

        _o_dualsense_sai(mgr, dualsenses, registro)
        relogio.avancar(prazo_do_lugar_guardado() - 1.0)
        for _ in range(3):
            mgr.sync(force=True)
        assert pro.vpad is proprio and not pro.no_p1, "o Pro andou antes de o lugar vencer"
        assert mgr.o_de_fora_no_p1() is None

        relogio.avancar(2.0)
        mgr.sync(force=True)
        assert pro.no_p1 and pro.vpad is pad and pro.player_index == 1
        assert mgr.numeros_de_jogador()[PRO] == 1

    @MASCARAS
    def test_com_o_jogo_o_prazo_para_e_so_o_renumerar_solta_o_p1(
        self, monkeypatch: pytest.MonkeyPatch, mascara: str
    ) -> None:
        mgr, pad, dualsenses, registro, relogio = _mesa_com_o_dualsense_no_p1(
            monkeypatch, mascara, jogo=True
        )
        pro = mgr._players[PRO]
        proprio: Any = pro.vpad
        proprio.flavor = mascara

        _o_dualsense_sai(mgr, dualsenses, registro)
        for _ in range(3):
            _o_prazo_passa(relogio)
            mgr.sync(force=True)
        assert pro.vpad is proprio and not pro.no_p1, "com o jogo o prazo andou e o Pro trocou"

        registro.soltar_os_lugares_guardados()
        mgr.sync(force=True)
        assert pro.no_p1 and pro.vpad is pad and pro.player_index == 1

    @MASCARAS
    def test_o_guardado_de_outro_numero_nao_segura_o_p1(
        self, monkeypatch: pytest.MonkeyPatch, mascara: str
    ) -> None:
        mgr, pad, dualsenses, registro, relogio = _mesa_com_o_dualsense_no_p1(
            monkeypatch, mascara, jogo=False, outros=(P3,)
        )
        pro = mgr._players[PRO]
        proprio: Any = pro.vpad
        proprio.flavor = mascara

        _o_dualsense_sai(mgr, dualsenses, registro, ficam=(P3,))
        relogio.avancar(prazo_do_lugar_guardado() - 5.0)
        registro.sync_connected([])
        relogio.avancar(6.0)
        mgr.sync(force=True)

        assert registro.guardados().keys() == {P3}, "o P3 ainda tem o lugar guardado"
        assert pro.no_p1 and pro.vpad is pad and pro.player_index == 1, (
            "o lugar guardado do P3 segurou o P1 que já venceu"
        )

    @MASCARAS
    def test_o_registro_que_nao_responde_segura_o_p1(
        self, monkeypatch: pytest.MonkeyPatch, mascara: str
    ) -> None:
        mgr, pad, dualsenses, registro, relogio = _mesa_com_o_dualsense_no_p1(
            monkeypatch, mascara, jogo=False
        )
        pro = mgr._players[PRO]
        proprio: Any = pro.vpad
        proprio.flavor = mascara
        _o_dualsense_sai(mgr, dualsenses, registro)
        _o_prazo_passa(relogio)

        calado = [True]
        de_verdade = registro.o_lugar_1_espera

        def _ilegivel() -> bool:
            if calado[0]:
                raise RuntimeError("registro ocupado")
            return de_verdade()

        monkeypatch.setattr(registro, "o_lugar_1_espera", _ilegivel)
        mgr.sync(force=True)
        assert pro.vpad is proprio and not pro.no_p1, "o registro calado soltou o P1"

        calado[0] = False
        mgr.sync(force=True)
        assert pro.no_p1 and pro.vpad is pad and pro.player_index == 1

    @MASCARAS
    def test_quem_espera_fora_da_mesa_nao_senta_no_p1_vago(
        self, monkeypatch: pytest.MonkeyPatch, mascara: str
    ) -> None:
        mgr, pad, dualsenses, registro, relogio = _mesa_com_o_dualsense_no_p1(
            monkeypatch, mascara, jogo=False
        )
        pro = mgr._players[PRO]
        proprio: Any = pro.vpad
        paradas: list[str] = []
        proprio.stop = lambda: paradas.append("parou")
        _o_dualsense_sai(mgr, dualsenses, registro)
        _o_prazo_passa(relogio)
        assert not registro.o_lugar_1_espera()

        pro.a_espera = True
        mgr._sentar_o_de_fora_no_p1(True)
        assert not pro.no_p1 and pro.vpad is proprio and paradas == [], (
            "quem está fora da mesa, com o pad próprio à espera, tomou o pad do P1"
        )
        assert mgr.o_de_fora_no_p1() is None and pad is not proprio

        pro.a_espera = False
        mgr._sentar_o_de_fora_no_p1(True)
        assert pro.no_p1 and pro.vpad is pad and paradas == ["parou"]


def _o_dualsense_sai(
    mgr: CoopManager,
    dualsenses: dict[str, str],
    registro: ControllerIdentityRegistry,
    ficam: tuple[str, ...] = (),
) -> None:
    daemon: Any = mgr._daemon
    dualsenses.clear()
    daemon.controller.primary_uniq = None
    registro.sync_connected(list(ficam))
    assert registro.o_lugar_1_espera()


def _mesa_com_o_dualsense_no_p1(
    monkeypatch: pytest.MonkeyPatch,
    mascara: str,
    *,
    jogo: bool,
    outros: tuple[str, ...] = (),
) -> tuple[CoopManager, Any, dict[str, str], ControllerIdentityRegistry, Relogio]:
    dualsenses = {P1: "/dev/input/event20"}
    monkeypatch.setattr(
        "hefesto_dualsense4unix.core.evdev_reader.discover_dualsense_evdevs",
        lambda: dict(dualsenses),
    )
    pad: Any = _PadDoP1()
    pad.flavor = mascara
    daemon: Any = _daemon(_Broker())
    daemon.config.gamepad_flavor = mascara
    daemon._gamepad_device = pad
    daemon.display_authority = "game" if jogo else "daemon"
    daemon.controller.is_connected = lambda: bool(dualsenses)
    relogio = Relogio()
    registro = _registro(relogio, outros)
    daemon.identity_registry = registro
    mgr = CoopManager(daemon)
    daemon._coop_manager = mgr
    mgr.sync()
    mgr.sync(force=True)
    assert mgr._players[PRO].vpad is not pad and mgr._players[PRO].player_index == 2
    return mgr, pad, dualsenses, registro, relogio


@pytest.mark.usefixtures("mesa", "config_isolado")
class TestOP1GuardadoNaoSeTomaNaVolta:
    """Item 2 na volta do de fora: com o lugar do P1 guardado, quem volta não toma o pad do P1."""

    @MASCARAS
    @pytest.mark.parametrize("jogo", [False, True], ids=["sem-jogo", "com-jogo"])
    def test_o_pro_que_volta_com_o_p1_guardado_senta_no_pad_proprio(
        self, monkeypatch: pytest.MonkeyPatch, mascara: str, jogo: bool
    ) -> None:
        mgr, pad, dualsenses, registro, relogio = _mesa_com_o_dualsense_no_p1(
            monkeypatch, mascara, jogo=jogo
        )

        _o_dualsense_sai(mgr, dualsenses, registro)
        mgr._teardown_player(PRO)
        mgr.sync(force=True)
        pro = mgr._players[PRO]
        recriado: Any = pro.vpad
        if recriado is not None and recriado is not pad:
            recriado.flavor = mascara
        for _ in range(2):
            mgr.sync(force=True)
        assert not pro.no_p1 and pro.vpad is not None and pro.vpad is not pad, (
            "o Pro que voltou tomou o pad do P1 com o lugar do P1 guardado"
        )
        assert mgr.o_de_fora_no_p1() is None

        proprio: Any = pro.vpad
        paradas: list[str] = []
        proprio.stop = lambda: paradas.append("parou")
        if jogo:
            registro.soltar_os_lugares_guardados()
        else:
            _o_prazo_passa(relogio)
        mgr.sync(force=True)
        assert pro.no_p1 and pro.vpad is pad and pro.player_index == 1
        assert paradas == ["parou"], "o pad próprio do Pro ficou de pé junto com o do P1"


@pytest.mark.usefixtures("mesa")
class TestOAvisoDoHotplugNaoDesmontaNinguem:
    """O aviso de troca de primário pode vir do fio do hotplug: quem espera só sai no ``sync``."""

    @MASCARAS
    def test_o_de_fora_que_espera_no_p1_sai_no_sync_e_nao_no_aviso(
        self, monkeypatch: pytest.MonkeyPatch, mascara: str
    ) -> None:
        mgr, _pad, dualsenses = _mesa_com_o_pro(monkeypatch, mascara, jogo=False)
        pro = mgr._players[PRO]
        pro.a_espera = True

        dualsenses[P1] = "/dev/input/event20"
        mgr.ceder_ao_primario(None, P1)
        assert mgr._players.get(PRO) is pro, "o aviso de troca desmontou o jogador fora do laço"

        daemon: Any = mgr._daemon
        daemon.controller.primary_uniq = P1
        mgr.sync(force=True)
        assert mgr.o_de_fora_no_p1() is None
