"""STEAM-NO-FISICO-01 — o jogo vê a ordem da mesa: os vpads nascem P1→P4.

A terceira obrigação da decisão dela de 23/09/2026: *"O P1 do Hefesto é o
jogador 1 do jogo: os controles virtuais chegam ao jogo na ordem P1→P4. Meça
como o SDL e o Proton numeram (pela ordem de criação do nó? pelo índice do
hidraw?) e faça a criação obedecer ao número da aba Controles."*

A MEDIÇÃO, no fonte (`libsdl-org/SDL@0c8feecc`): o SDL dá a cada joystick novo
o menor índice livre (`SDL_joystick.c`, `SDL_PrivateJoystickAdded` →
`SDL_FindFreePlayerIndex`); a enumeração inicial do HIDAPI é o
`udev_enumerate_scan_devices` do subsistema `hidraw` (`linux/hid.c`), que o
udev ordena pelo syspath — e o syspath de um vpad uhid leva o número de
sequência do HID, isto é, a ORDEM DE CRIAÇÃO. O índice do `/dev/hidrawN` não
entra na conta. O winebus do Proton enumera pelo mesmo udev.

Logo: o jogo numera os vpads na ordem em que eles nascem. O co-op os criava na
ordem do `eventN` (a ordem em que o kernel viu os controles), e o grab ou a
calibração que atrasavam um jogador deixavam o seguinte passar na frente.

AS MORDIDAS, exercidas e devolvidas: (1) o `sync` na ordem de `want` cria o P4
antes do P2; (2) o `_promote_pending` sem a espera deixa o P3 nascer antes do
P2 de grab pendente; (3) sem o prazo, o P3 espera o P2 para sempre.

AS DUAS RESPOSTAS DELA DE 23/09/2026, 22h (a segunda metade deste arquivo):
o vpad do PRIMÁRIO espera a carta 1, e o controle fora de ordem com o jogo
aberto se recria na hora. As mordidas delas estão no relatório da sprint.
"""
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

#: A carta de cada um na aba Controles.
CARTAS = {P1: 1, P2: 2, P3: 3, P4: 4}

#: A ordem em que o kernel os viu (o `eventN`): nada a ver com a carta.
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
        """A MORDIDA (1): na ordem do `eventN` nasceria P4, P2, P3 — e o jogo
        chamaria o P4 dela de «jogador 2»."""
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
        """A MORDIDA (2): o grab do P2 confirma um tique depois; sem a espera,
        o P3 nasceria antes e seria o «jogador 2» do jogo."""
        _Leitor.pendentes = {P2}
        mgr = CoopManager(_daemon())

        mgr.sync()
        assert nascimentos == []  # P2 pendente; P3 e P4 esperam a vez dele

        mgr._players[P2].reader.grab_state = "held"
        mgr._promote_pending()

        assert nascimentos == [P2, P3, P4]

    def test_o_prazo_e_o_piso_de_quem_esta_pronto(
        self, nascimentos: list[str], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A MORDIDA (3): o P2 que nunca confirma não deixa o P3 sem controle —
        passado `ESPERA_PELA_ORDEM_S`, o P3 nasce e o diário diz."""
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
        """A espera é só por quem AINDA não nasceu: um P2 de pé não trava o P3.

        24/09/2026, a segunda resposta dela (`D-2309-FORA-DE-ORDEM-SE-RECRIA-
        NA-HORA`): o P3 que volta DEPOIS do P4 renasce, e o P4 renasce atrás
        dele — sem jogo aberto, o jogo que abrir depois os enumera na ordem em
        que nasceram. Esta linha dizia `[P2, P3, P4, P3]`, e era a desordem.
        """
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
        """O `_promote_pending` roda a cada tique do poll loop (~10 ms). Com
        todos os vpads de pé não há fila a ordenar, e ele não pode ir ao
        registro por carta — seriam centenas de idas por segundo sob o lock
        dele. A ordem só custa enquanto alguém espera nascer."""
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


# ---------------------------------------------------------------------------
# As duas respostas dela de 23/09/2026, 22h.
# ---------------------------------------------------------------------------


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
    """O caminho de verdade do vpad do P1 (`gamepad`), com o nascimento anotado.

    Não é mais frouxo que o real nos dois pontos que a mesa lê: o `stop` deixa
    `_gamepad_device` em ``None`` e o `start` põe um objeto NOVO lá.
    """
    eventos: list[tuple[Any, ...]] = []

    def _stop(daemon: Any, *, persist: bool = True, release_grab: bool = True) -> None:
        eventos.append(("stop", persist, release_grab))
        daemon._gamepad_device = None

    def _start(daemon: Any, flavor: Any = None, *, origin: str) -> bool:
        eventos.append(("start", origin))
        nascimentos.append("p1")
        daemon._gamepad_device = object()
        return True

    monkeypatch.setattr(gamepad_mod, "stop_gamepad_emulation", _stop)
    monkeypatch.setattr(gamepad_mod, "start_gamepad_emulation", _start)
    return eventos


class TestOPrimarioEsperaACarta1:
    """`D-2309-O-PRIMARIO-ESPERA-A-CARTA-1`: o vpad do P1 nasce no boot, antes
    de o daemon saber quem é o primário; «esperar» é renascer DEPOIS do vpad
    da carta 1, que é o que o jogo enumera."""

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
        # Quem é o primário NÃO muda: «controle novo nunca rouba o posto».
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
        """A R-04 medida em 23/07: recriar o vpad do P1 com o jogo na
        autoridade mata aquele controle até o fim da sessão. O P1 fica, os
        secundários nascem em ordem entre si, e o P1 renasce quando o jogo
        devolve a autoridade."""
        daemon = _daemon(cartas={P1: 2, P2: 1, P3: 3, P4: 4})
        daemon.display_authority = "game"
        mgr = CoopManager(daemon)

        mgr.sync()
        assert nascimentos == [P2, P3, P4]
        assert vpad_do_p1 == []
        assert mgr._p1_espera_o_jogo is True

        daemon.display_authority = "desktop"
        mgr.sync()

        # Sem jogo, o jogo que abrir enumera na ordem de nascimento: a carta 1
        # (o P2) fica, e o resto renasce atrás dela, na ordem da carta.
        assert nascimentos == [P2, P3, P4, "p1", P3, P4]
        assert vpad_do_p1 == [("stop", False, False), ("start", "profile")]
        assert mgr._p1_espera_o_jogo is False

    def test_o_p1_que_renasceu_por_outro_caminho_nao_renasce_de_novo(
        self, nascimentos: list[str], vpad_do_p1: list[tuple[Any, ...]]
    ) -> None:
        """A troca de máscara recria o vpad do P1 (carta 1) DEPOIS dos
        secundários. Sem jogo, quem volta para trás dele são os secundários —
        derrubar o P1 de novo seria pagar o preço dele por nada."""
        daemon = _daemon()
        mgr = CoopManager(daemon)
        mgr.sync()
        assert nascimentos == [P2, P3, P4]

        daemon._gamepad_device = object()
        mgr.sync()

        assert nascimentos == [P2, P3, P4, P2, P3, P4]
        assert vpad_do_p1 == []


class TestForaDeOrdemSeRecriaNaHora:
    """`D-2309-FORA-DE-ORDEM-SE-RECRIA-NA-HORA`, com o jogo ABERTO: o jogo dá
    ao vpad que nasce o menor lugar livre."""

    def test_a_carta_renumerada_recria_os_que_trocaram(
        self, nascimentos: list[str], vpad_do_p1: list[tuple[Any, ...]]
    ) -> None:
        cartas = dict(CARTAS)
        daemon = _daemon(cartas=cartas)
        daemon.display_authority = "game"
        mgr = CoopManager(daemon)
        mgr.sync()
        assert nascimentos == [P2, P3, P4]

        # A aba Controles: o P4 do kernel passa a ser o jogador 2 dela.
        cartas[P2], cartas[P4] = 4, 2
        mgr.sync()

        assert nascimentos == [P2, P3, P4, P4, P3, P2]
        assert vpad_do_p1 == []  # o P1 (carta 1) não se mexe
        assert list(mgr._mesa_do_jogo.items()) == sorted(
            {0: "<p1>", 1: P4, 2: P3, 3: P2}.items()
        )

    def test_a_carta_menor_que_chega_depois_da_maior(
        self, nascimentos: list[str], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """O P2 cujo grab demorou além do prazo: o P3 e o P4 nasceram sem ele.
        Quando o P2 fica pronto, os dois renascem atrás dele."""
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
        """O P2 cai no meio da partida (as cartas andam: o P3 vira 2, o P4
        vira 3) e volta como o 4º. O jogo daria a ele o lugar vazio do meio;
        o P3 e o P4 renascem para ele entrar no fim."""
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
        """Sem jogo não há buraco: quem chega vai para o fim — e o P2 que volta
        como o 4º JÁ está no fim. Nada renasce."""
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
        """A renumeração roda o `sync(force=True)` num worker. Recriar vpad
        ali disputaria o `forward_all` do poll loop: o worker deixa o recado,
        e o tique seguinte do laço recria."""
        cartas = dict(CARTAS)
        mgr = CoopManager(_daemon(cartas=cartas))
        mgr.sync()
        mgr._fio_do_laco = -1  # o laço é OUTRA thread

        cartas[P2], cartas[P4] = 4, 2
        mgr.sync(force=True)
        assert nascimentos == [P2, P3, P4]
        assert mgr._ordem_pendente is True

        mgr.forward_all()  # esta thread passa a ser a do laço

        # Sem jogo aberto, o P4 (agora carta 2) sobe sozinho quando os de trás
        # renascem: só o P3 e o P2 pagam.
        assert nascimentos == [P2, P3, P4, P3, P2]
        assert mgr._ordem_pendente is False

    def test_a_mesma_desordem_nao_recria_em_laco(
        self, nascimentos: list[str]
    ) -> None:
        """Se o jogo discordar do modelo e a MESMA desordem voltar logo depois
        de recriar, recriar de novo arrancaria o controle dela em laço."""
        cartas = dict(CARTAS)
        daemon = _daemon(cartas=cartas)
        daemon.display_authority = "game"
        mgr = CoopManager(daemon)
        mgr.sync()
        antes = dict(mgr._mesa_do_jogo)
        cartas[P2], cartas[P4] = 4, 2
        mgr.sync()
        assert nascimentos == [P2, P3, P4, P4, P3, P2]

        mgr._mesa_do_jogo = antes  # o jogo «desfez»: a mesma desordem de novo
        mgr.sync()
        mgr.sync()

        assert nascimentos == [P2, P3, P4, P4, P3, P2]

    def test_o_tique_nao_pergunta_a_carta(self, nascimentos: list[str]) -> None:
        """O `forward_all` roda a cada ~10 ms: a ordem não pode custar uma ida
        ao registro por tique."""
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
