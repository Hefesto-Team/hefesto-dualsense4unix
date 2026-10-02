"""STEAM-NO-FISICO-01 — o jogo vê a ordem da mesa: os vpads nascem P1→P4."""
from __future__ import annotations

from types import SimpleNamespace
from typing import Any, ClassVar

import pytest

from hefesto_dualsense4unix.daemon.subsystems import coop as coop_mod
from hefesto_dualsense4unix.daemon.subsystems import gamepad as gamepad_mod
from hefesto_dualsense4unix.daemon.subsystems.coop import (
    CoopManager,
    planejar_a_ordem,
)

P1 = "aabbcc000001"
P2 = "aabbcc000002"
P3 = "aabbcc000003"
P4 = "aabbcc000004"

CARTAS = {P1: 1, P2: 2, P3: 3, P4: 4}

EVDEVS = {
    P1: "/dev/input/event20",
    P4: "/dev/input/event21",
    P2: "/dev/input/event22",
    P3: "/dev/input/event23",
}


class _Leitor:
    """Leitor evdev falso; `pendentes` são os que o grab deixa em "pending"."""

    pendentes: ClassVar[set[str]] = set()

    def __init__(self, device_path: Any = None, target_uniq: str | None = None) -> None:
        self.device_path = device_path
        self.target_uniq = target_uniq
        self.grab_state = "off"
        self.snap = SimpleNamespace(
            lx=128, ly=128, rx=128, ry=128, l2_raw=0, r2_raw=0,
            buttons_pressed=frozenset(),
        )

    def start(self) -> bool:
        return True

    def set_grab(self, grab: bool) -> bool:
        if grab and self.target_uniq in type(self).pendentes:
            self.grab_state = "pending"
            return True
        self.grab_state = "held" if grab else "off"
        return True

    def stop(self) -> None:
        return None

    def snapshot(self) -> Any:
        return self.snap


class _Vpad:
    def __init__(self, identidade: str) -> None:
        self.identidade = identidade
        self.flavor = "dualsense"

    def stop(self) -> None:
        return None

    def forward_analog(self, **_kw: int) -> None:
        return None

    def forward_buttons(self, _pressed: frozenset[str]) -> None:
        return None

    def pump_ff(self) -> None:
        return None


@pytest.fixture
def nascimentos(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """A ordem em que os vpads nascem — que é a ordem que o jogo vê."""
    ordem: list[str] = []
    _Leitor.pendentes = set()
    monkeypatch.setattr(
        "hefesto_dualsense4unix.core.evdev_reader.InputDirWatch.poll", lambda self: True
    )
    monkeypatch.setattr("hefesto_dualsense4unix.core.evdev_reader.EvdevReader", _Leitor)
    monkeypatch.setattr(
        "hefesto_dualsense4unix.core.evdev_reader.discover_dualsense_evdevs",
        lambda: dict(EVDEVS),
    )

    def _nasce(_flavor: Any, *, identity: str | None = None, **_kw: Any) -> _Vpad:
        ordem.append(str(identity))
        return _Vpad(str(identity))

    monkeypatch.setattr(
        "hefesto_dualsense4unix.integrations.virtual_pad.make_virtual_pad", _nasce
    )
    monkeypatch.setattr(
        "hefesto_dualsense4unix.daemon.launch_env.materialize_launch_env",
        lambda daemon: None,
    )
    monkeypatch.setattr("hefesto_dualsense4unix.core.sysfs_leds.discover", lambda: {})
    return ordem


def _daemon(cartas: dict[str, int] | None = CARTAS) -> Any:
    registro = (
        SimpleNamespace(numero_da_lampada=lambda mac, assign=False: cartas.get(mac))
        if cartas is not None
        else None
    )
    return SimpleNamespace(
        config=SimpleNamespace(coop_enabled=True, gamepad_flavor="dualsense"),
        _gamepad_device=object(),
        controller=SimpleNamespace(
            primary_uniq=P1,
            _evdev=SimpleNamespace(_device_path="/dev/input/event20"),
        ),
        identity_registry=registro,
        _coop_manager=None,
    )


class TestONascimentoSegueACarta:
    def test_a_mesa_cheia_nasce_na_ordem_da_carta(self, nascimentos: list[str]) -> None:
        """A MORDIDA (1): na ordem do `eventN` nasceria P4, P2, P3 — e o jogo"""
        mgr = CoopManager(_daemon())

        mgr.sync()

        assert nascimentos == [P2, P3, P4]

    def test_sem_registro_a_ordem_e_a_de_sempre(self, nascimentos: list[str]) -> None:
        """Sem quem responda o número (dublê, backend legado), nada muda."""
        mgr = CoopManager(_daemon(cartas=None))

        mgr.sync()

        assert nascimentos == [P4, P2, P3]

    def test_a_carta_trocada_pela_aba_vale(self, nascimentos: list[str]) -> None:
        """A aba Controles renumerou: o P4 do kernel é o jogador 2 dela."""
        mgr = CoopManager(_daemon(cartas={P1: 1, P4: 2, P3: 3, P2: 4}))

        mgr.sync()

        assert nascimentos == [P4, P3, P2]


class TestQuemAtrasaNaoPerdeOLugar:
    def test_o_grab_pendente_do_p2_segura_o_p3(self, nascimentos: list[str]) -> None:
        """A MORDIDA (2): o grab do P2 confirma um tique depois; sem a espera,"""
        _Leitor.pendentes = {P2}
        mgr = CoopManager(_daemon())

        mgr.sync()
        assert nascimentos == []

        mgr._players[P2].reader.grab_state = "held"
        mgr._promote_pending()

        assert nascimentos == [P2, P3, P4]

    def test_o_prazo_e_o_piso_de_quem_esta_pronto(
        self, nascimentos: list[str], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A MORDIDA (3): o P2 que nunca confirma não deixa o P3 sem controle —"""
        relogio = {"t": 1000.0}
        monkeypatch.setattr(coop_mod.time, "monotonic", lambda: relogio["t"])
        _Leitor.pendentes = {P2}
        mgr = CoopManager(_daemon())

        mgr.sync()
        relogio["t"] += coop_mod.ESPERA_PELA_ORDEM_S - 0.1
        mgr._promote_pending()
        assert nascimentos == []

        relogio["t"] += 0.2
        mgr._promote_pending()

        assert nascimentos == [P3, P4]
        assert mgr._players[P2].vpad is None

    def test_quem_ja_tem_vpad_nao_segura_ninguem(self, nascimentos: list[str]) -> None:
        """A espera é só por quem AINDA não nasceu: um P2 de pé não trava o P3."""
        mgr = CoopManager(_daemon())
        mgr.sync()
        assert nascimentos == [P2, P3, P4]

        mgr._teardown_player(P3)
        mgr.sync()

        assert nascimentos == [P2, P3, P4, P3, P4]


class TestOTiqueNaoPagaAOrdem:
    def test_com_todos_nascidos_o_tique_nao_pergunta_a_carta(
        self, nascimentos: list[str]
    ) -> None:
        """O `_promote_pending` roda a cada tique do poll loop (~10 ms). Com"""
        consultas: list[str] = []

        def _carta(mac: str, assign: bool = False) -> int | None:
            consultas.append(mac)
            return CARTAS.get(mac)

        daemon = _daemon()
        daemon.identity_registry = SimpleNamespace(numero_da_lampada=_carta)
        mgr = CoopManager(daemon)
        mgr.sync()
        assert nascimentos == [P2, P3, P4]

        consultas.clear()
        for _ in range(100):
            mgr._promote_pending()

        assert consultas == []


@pytest.fixture
def presentes(
    nascimentos: list[str], monkeypatch: pytest.MonkeyPatch
) -> dict[str, str]:
    """Os controles na mesa, mutáveis: tirar um é ele sair, pôr é ele voltar."""
    mesa = dict(EVDEVS)
    monkeypatch.setattr(
        "hefesto_dualsense4unix.core.evdev_reader.discover_dualsense_evdevs",
        lambda: dict(mesa),
    )
    return mesa


@pytest.fixture
def vpad_do_p1(
    nascimentos: list[str], monkeypatch: pytest.MonkeyPatch
) -> list[tuple[Any, ...]]:
    """O caminho de verdade do vpad do P1 (`gamepad`), com o nascimento anotado."""
    eventos: list[tuple[Any, ...]] = []

    def _stop(daemon: Any, *, persist: bool = True, release_grab: bool = True) -> None:
        eventos.append(("stop", persist, release_grab))
        daemon._gamepad_device = None

    def _start(
        daemon: Any, flavor: Any = None, *, origin: str, caminho: str | None = None
    ) -> str:
        eventos.append(("start", origin))
        nascimentos.append("p1")
        daemon._gamepad_device = object()
        return gamepad_mod.EMU_APLICADO

    monkeypatch.setattr(gamepad_mod, "stop_gamepad_emulation", _stop)
    monkeypatch.setattr(gamepad_mod, "start_gamepad_emulation_desfecho", _start)
    return eventos


class TestOPrimarioEsperaACarta1:
    """`D-2309-O-PRIMARIO-ESPERA-A-CARTA-1`: o vpad do P1 nasce no boot, antes"""

    def test_o_p1_renasce_depois_da_carta_1(
        self, nascimentos: list[str], vpad_do_p1: list[tuple[Any, ...]]
    ) -> None:
        daemon = _daemon(cartas={P1: 2, P2: 1, P3: 3, P4: 4})
        vpad_de_boot = daemon._gamepad_device
        mgr = CoopManager(daemon)

        mgr.sync()

        assert nascimentos == [P2, "p1", P3, P4]
        assert vpad_do_p1 == [("stop", False, False), ("start", "profile")]
        assert daemon._gamepad_device is not vpad_de_boot
        assert daemon.controller.primary_uniq == P1

    def test_com_o_p1_na_carta_1_nada_renasce(
        self, nascimentos: list[str], vpad_do_p1: list[tuple[Any, ...]]
    ) -> None:
        mgr = CoopManager(_daemon())

        mgr.sync()

        assert nascimentos == [P2, P3, P4]
        assert vpad_do_p1 == []

    def test_com_o_jogo_na_autoridade_o_p1_espera_o_jogo_fechar(
        self, nascimentos: list[str], vpad_do_p1: list[tuple[Any, ...]]
    ) -> None:
        """A R-04 medida em 23/07: recriar o vpad do P1 com o jogo na"""
        daemon = _daemon(cartas={P1: 2, P2: 1, P3: 3, P4: 4})
        daemon.display_authority = "game"
        mgr = CoopManager(daemon)

        mgr.sync()
        assert nascimentos == [P2, P3, P4]
        assert vpad_do_p1 == []
        assert mgr._p1_espera_o_jogo is True

        daemon.display_authority = "daemon"
        mgr.sync()

        assert nascimentos == [P2, P3, P4, "p1", P3, P4]
        assert vpad_do_p1 == [("stop", False, False), ("start", "profile")]
        assert mgr._p1_espera_o_jogo is False

    def test_o_p1_que_renasceu_por_outro_caminho_nao_renasce_de_novo(
        self, nascimentos: list[str], vpad_do_p1: list[tuple[Any, ...]]
    ) -> None:
        """A troca de máscara recria o vpad do P1 (carta 1) DEPOIS dos"""
        daemon = _daemon()
        mgr = CoopManager(daemon)
        mgr.sync()
        assert nascimentos == [P2, P3, P4]

        daemon._gamepad_device = object()
        mgr.sync()

        assert nascimentos == [P2, P3, P4, P2, P3, P4]
        assert vpad_do_p1 == []


class TestForaDeOrdemSeRecriaNaHora:
    """`D-2309-FORA-DE-ORDEM-SE-RECRIA-NA-HORA`, com o jogo ABERTO: o jogo dá"""

    def test_a_carta_renumerada_recria_os_que_trocaram(
        self, nascimentos: list[str], vpad_do_p1: list[tuple[Any, ...]]
    ) -> None:
        cartas = dict(CARTAS)
        daemon = _daemon(cartas=cartas)
        daemon.display_authority = "game"
        mgr = CoopManager(daemon)
        mgr.sync()
        assert nascimentos == [P2, P3, P4]

        cartas[P2], cartas[P4] = 4, 2
        mgr.sync()

        assert nascimentos == [P2, P3, P4, P4, P3, P2]
        assert vpad_do_p1 == []
        assert list(mgr._mesa_do_jogo.items()) == sorted(
            {0: "<p1>", 1: P4, 2: P3, 3: P2}.items()
        )

    def test_a_carta_menor_que_chega_depois_da_maior(
        self, nascimentos: list[str], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """O P2 cujo grab demorou além do prazo: o P3 e o P4 nasceram sem ele."""
        relogio = {"t": 1000.0}
        monkeypatch.setattr(coop_mod.time, "monotonic", lambda: relogio["t"])
        _Leitor.pendentes = {P2}
        daemon = _daemon()
        daemon.display_authority = "game"
        mgr = CoopManager(daemon)
        mgr.sync()
        relogio["t"] += coop_mod.ESPERA_PELA_ORDEM_S + 0.1
        mgr._promote_pending()
        assert nascimentos == [P3, P4]

        mgr._players[P2].reader.grab_state = "held"
        mgr._promote_pending()

        assert nascimentos == [P3, P4, P2, P3, P4]

    def test_o_buraco_de_quem_saiu_nao_fica_para_quem_chega(
        self, nascimentos: list[str], presentes: dict[str, str]
    ) -> None:
        """O P2 cai no meio da partida (as cartas andam: o P3 vira 2, o P4"""
        cartas = dict(CARTAS)
        daemon = _daemon(cartas=cartas)
        daemon.display_authority = "game"
        mgr = CoopManager(daemon)
        mgr.sync()

        del presentes[P2]
        cartas.update({P3: 2, P4: 3})
        del cartas[P2]
        mgr.sync()
        assert nascimentos == [P2, P3, P4]

        presentes[P2] = EVDEVS[P2]
        cartas[P2] = 4
        mgr.sync()

        assert nascimentos == [P2, P3, P4, P3, P4, P2]

    def test_sem_jogo_o_mesmo_buraco_so_recria_quem_ficou_para_tras(
        self, nascimentos: list[str], presentes: dict[str, str]
    ) -> None:
        """Sem jogo não há buraco: quem chega vai para o fim — e o P2 que volta"""
        cartas = dict(CARTAS)
        mgr = CoopManager(_daemon(cartas=cartas))
        mgr.sync()
        del presentes[P2]
        cartas.update({P3: 2, P4: 3})
        del cartas[P2]
        mgr.sync()

        presentes[P2] = EVDEVS[P2]
        cartas[P2] = 4
        mgr.sync()

        assert nascimentos == [P2, P3, P4, P2]


class TestAOrdemNaoAtropelaOLaco:
    def test_o_worker_da_renumeracao_so_deixa_o_recado(
        self, nascimentos: list[str]
    ) -> None:
        """A renumeração roda o `sync(force=True)` num worker. Recriar vpad"""
        cartas = dict(CARTAS)
        mgr = CoopManager(_daemon(cartas=cartas))
        mgr.sync()
        mgr._fio_do_laco = -1

        cartas[P2], cartas[P4] = 4, 2
        mgr.sync(force=True)
        assert nascimentos == [P2, P3, P4]
        assert mgr._ordem_pendente is True

        mgr.forward_all()

        assert nascimentos == [P2, P3, P4, P3, P2]
        assert mgr._ordem_pendente is False

    def test_a_mesma_desordem_nao_recria_em_laco(
        self, nascimentos: list[str]
    ) -> None:
        """Se o jogo discordar do modelo e a MESMA desordem voltar logo depois"""
        cartas = dict(CARTAS)
        daemon = _daemon(cartas=cartas)
        daemon.display_authority = "game"
        mgr = CoopManager(daemon)
        mgr.sync()
        antes = dict(mgr._mesa_do_jogo)
        cartas[P2], cartas[P4] = 4, 2
        mgr.sync()
        assert nascimentos == [P2, P3, P4, P4, P3, P2]

        mgr._mesa_do_jogo = antes
        mgr.sync()
        mgr.sync()

        assert nascimentos == [P2, P3, P4, P4, P3, P2]

    def test_a_ordem_que_falha_nao_derruba_o_laco(
        self, nascimentos: list[str], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A regra do módulo: o poll loop não cai. Se a recriação do P1"""

        def _quebra(daemon: Any, **_kw: Any) -> None:
            raise OSError("uhid sumiu")

        monkeypatch.setattr(gamepad_mod, "stop_gamepad_emulation", _quebra)
        mgr = CoopManager(_daemon(cartas={P1: 2, P2: 1, P3: 3, P4: 4}))

        mgr.sync()

        assert nascimentos == [P2, P3, P4]

    def test_o_tique_nao_pergunta_a_carta(self, nascimentos: list[str]) -> None:
        """O `forward_all` roda a cada ~10 ms: a ordem não pode custar uma ida"""
        consultas: list[str] = []

        def _carta(mac: str, assign: bool = False) -> int | None:
            consultas.append(mac)
            return CARTAS.get(mac)

        daemon = _daemon()
        daemon.identity_registry = SimpleNamespace(numero_da_lampada=_carta)
        mgr = CoopManager(daemon)
        mgr.sync()
        consultas.clear()

        for _ in range(100):
            mgr.forward_all()

        assert consultas == []


class TestOPlano:
    """`planejar_a_ordem`, puro: a menor perturbação que põe a mesa em ordem."""

    def test_em_ordem_nao_recria_ninguem(self) -> None:
        assert planejar_a_ordem({0: "a", 1: "b"}, {"a": 1, "b": 2}) == ([], True)

    def test_o_buraco_do_meio_com_o_jogo_aberto(self) -> None:
        mesa = {0: "a", 2: "c"}
        assert planejar_a_ordem(mesa, {"a": 1, "c": 2, "d": 3}, ["d"]) == (
            ["c"],
            True,
        )

    def test_quem_nasce_no_buraco_certo_nao_derruba_ninguem(self) -> None:
        """O 2 que volta cai no lugar vazio do meio, que é o dele."""
        mesa = {0: "a", 2: "c"}
        assert planejar_a_ordem(mesa, {"a": 1, "c": 3, "d": 2}, ["d"]) == ([], True)

    def test_carta_repetida_nao_recria(self) -> None:
        """Registro degenerado: duas cartas iguais não têm ordem a impor."""
        assert planejar_a_ordem({0: "a"}, {"a": 1, "b": 1}, ["b"]) == ([], True)

    def test_sem_jogo_quem_nasce_vai_para_o_fim(self) -> None:
        mesa = {0: "a", 2: "c"}
        assert planejar_a_ordem(
            mesa, {"a": 1, "c": 2, "d": 3}, ["d"], compacta=True
        ) == ([], True)

    def test_o_fixo_fica_e_os_outros_se_acertam_entre_si(self) -> None:
        mesa = {0: "p1", 1: "x", 2: "y"}
        cartas = {"p1": 2, "x": 3, "y": 1}
        assert planejar_a_ordem(mesa, cartas, fixos=frozenset({"p1"})) == (
            ["x", "y"],
            False,
        )


class _PadComCaminho:
    """Um vpad com o que o produto lê dele: máscara, canal e caminho de origem."""

    def __init__(self, flavor: str, caminho: str | None, identidade: str) -> None:
        from hefesto_dualsense4unix.integrations import virtual_pad as vp

        self.identidade = identidade
        self.flavor = flavor
        self.caminho = vp.caminho_resolvido(caminho, flavor)
        self.backend = "uhid" if vp.quer_uhid(caminho, flavor) else "uinput"

    def stop(self) -> None:
        return None

    def forward_analog(self, **_kw: int) -> None:
        return None

    def forward_buttons(self, _pressed: frozenset[str]) -> None:
        return None

    def pump_ff(self) -> None:
        return None


class _EspelhoFalso:
    """`PhysicalReportReader` de mentira: o P1 em uhid sobe um, e ele não lê nada."""

    def __init__(self, **_kw: Any) -> None:
        return None

    def start(self) -> bool:
        return True

    def stop(self) -> None:
        return None


class TestOP1RenasceNoMesmoCaminho:
    """O vpad do P1 que renasce pela ordem volta no caminho em que estava.

    A conferência de 24/09/2026 achou a terceira porta do vazamento de caminho
    (O-CAMINHO-NAO-VAZA-01, CAMINHO-CONTAGIO-01): o `_reerguer_o_p1` chamava o
    start SEM caminho. Um start sem opinião não herda de lugar nenhum, por
    ordem dela (`gamepad._caminho_a_herdar` devolve ``None``), e o
    `_guardar_o_caminho` LIMPA o slot da sessão. Com a mesa no Modo Xbox — o
    chip da aba Jogar, que muda o CAMINHO e não a máscara —, a carta 1 que
    chegava depois do primário devolvia o P1 em DualSense/uhid, e a escolha
    dela sumia da tela e dos secundários sem ela ter tocado em nada.

    Aqui o start e o stop são os DE VERDADE (`gamepad`), para a régua não ser
    mais frouxa que o produto: o dublê do `vpad_do_p1` não conhece caminho.
    A MORDIDA: devolva o `_reerguer_o_p1` sem o `caminho=` e o P1 volta uhid.
    """

    def test_o_modo_xbox_sobrevive_a_recriacao_do_p1(
        self, nascimentos: list[str], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        pads: list[_PadComCaminho] = []

        def _fabrica(
            flavor: str | None, *, identity: str | None = None, **kw: Any
        ) -> _PadComCaminho:
            pad = _PadComCaminho(flavor or "dualsense", kw.get("caminho"), str(identity))
            nascimentos.append(str(identity))
            pads.append(pad)
            return pad

        monkeypatch.setattr(
            "hefesto_dualsense4unix.integrations.virtual_pad.make_virtual_pad", _fabrica
        )
        monkeypatch.setattr(gamepad_mod, "_set_controller_grab", lambda *_a: None)
        monkeypatch.setattr(
            "hefesto_dualsense4unix.core.physical_report_reader.PhysicalReportReader",
            _EspelhoFalso,
        )
        daemon = _daemon(cartas={P1: 2, P2: 1, P3: 3, P4: 4})
        daemon.config.gamepad_emulation_enabled = False
        daemon.config.gamepad_caminho = None
        daemon.config.gamepad_caminho_global = None
        daemon.config.rumble_active = None
        daemon._gamepad_device = None
        daemon._mouse_device = None
        daemon._motion_reader = None
        daemon.controller.hidraw_path = lambda uniq=None: "/dev/hidraw4"
        # O caminho DA SESSÃO em Xbox, com a máscara DualSense de sempre — o
        gamepad_mod.start_gamepad_emulation_desfecho(
            daemon, origin="profile", caminho="xbox"
        )
        assert daemon._gamepad_device.backend == "uinput"
        nascimentos.clear()

        CoopManager(daemon).sync()

        assert nascimentos == [P2, P1, P3, P4], "o P1 tinha de renascer atrás da carta 1"
        assert daemon._gamepad_device.caminho == "xbox", (
            "o P1 renasceu em outro caminho — a recriação pela ordem desfez o "
            "Modo Xbox que ela escolheu"
        )
        assert daemon._gamepad_device.backend == "uinput"
        assert daemon.config.gamepad_caminho == "xbox", (
            "o slot da sessão foi limpo: a tela e os secundários passam a ver "
            "DualSense sobre uma escolha dela de Xbox"
        )
