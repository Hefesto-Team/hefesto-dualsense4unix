"""O-MODO-XBOX-NAO-E-QUEDA-02, item 5 — o PS e as combinações valem em qualquer um dos quatro."""
from __future__ import annotations

import asyncio
from collections.abc import Iterator
from types import SimpleNamespace
from typing import Any

import pytest
import structlog

from hefesto_dualsense4unix.daemon.sensor_hub import SensorHub
from hefesto_dualsense4unix.daemon.subsystems import external_mask as em
from hefesto_dualsense4unix.daemon.subsystems.hotkey import build_next_mask_callback
from hefesto_dualsense4unix.integrations.virtual_pad import CAMINHO_XBOX
from tests.unit.test_dois_vpads_nunca_tem_o_mesmo_mac import (
    KernelDoHidPlaystation,
    kernel_de_mentira,
)
from tests.unit.test_o_jogo_espera_a_carta_do_lugar_guardado import (  # noqa: F401
    P1,
    P2,
    P3,
    P4,
    TIQUE,
    TRANSPORTES,
    UNIQS,
    Relogio,
    config_isolado,
)
from tests.unit.test_os_atalhos_na_espera import (
    CAMINHO_NATIVO,
    CAMINHO_VIRTUAL,
    GESTOS,
    MATRIZ,
    MesaDosAtalhos,
    armar_o_ato_do_daemon,
    montar_atalhos,
)


@pytest.fixture
def kernel(monkeypatch: pytest.MonkeyPatch) -> Iterator[KernelDoHidPlaystation]:
    """O kernel de mentira da O-VPAD: nenhum ``/dev/uhid`` ou ``/dev/uinput`` de verdade."""
    with kernel_de_mentira(monkeypatch) as k:
        yield k


def _disparos_no_diario(registros: list[dict[str, Any]]) -> list[tuple[str, Any]]:
    """`(gesto, de)` de cada disparo que o diário registrou, na ordem."""
    return [
        (r.get("combo") or "ps_solo", r.get("de"))
        for r in registros
        if r["event"] in ("hotkey_fired", "ps_solo_released")
    ]


def _apertar_juntos(bancada: MesaDosAtalhos, apertos: dict[str, tuple[str, ...]]) -> list[str]:
    """Cada controle de ``apertos`` aperta os dele, todos no mesmo instante, e soltam juntos."""
    antes = len(bancada.disparos)
    for uniq, botoes in apertos.items():
        bancada.mesa.apertados[uniq] = frozenset(botoes)  # type: ignore[attr-defined]
    bancada.tique(0.0)
    bancada.tique(0.3)
    for uniq in apertos:
        del bancada.mesa.apertados[uniq]  # type: ignore[attr-defined]
    bancada.tique(0.05)
    return bancada.disparos[antes:]


@pytest.mark.usefixtures("config_isolado")
class TestNoControleDaCarta2:
    """Com o P1 na mesa, o PS + R3 do controle que acende o «2» troca o modo."""

    @MATRIZ
    @pytest.mark.parametrize("caminho", [CAMINHO_VIRTUAL, CAMINHO_XBOX])
    def test_o_ps_r3_da_carta_2_dispara_e_o_diario_diz_de_quem(
        self, monkeypatch: pytest.MonkeyPatch, kernel: KernelDoHidPlaystation,
        quantos: int, transporte: str, caminho: str,
    ) -> None:
        bancada = montar_atalhos(monkeypatch, kernel, quantos, transporte, caminho=caminho)
        assert not bancada.vaga() and bancada.inst.primary_uniq == P1
        with structlog.testing.capture_logs() as registros:
            assert bancada.apertar(P2, "ps", "r3") == ["ponte"], (
                "o PS + R3 do controle da carta 2 caiu no vazio com o P1 na mesa"
            )
        assert _disparos_no_diario(registros) == [("ponte", P2)]
        assert bancada.a_tela() == {u: n + 1 for n, u in enumerate(UNIQS[:quantos])}
        assert bancada.dono_do_vpad_do_p1() == P1

    @pytest.mark.parametrize(("botoes", "gesto"), GESTOS)
    @pytest.mark.parametrize("transporte", list(TRANSPORTES))
    def test_os_seis_atalhos_em_cada_um_dos_quatro(
        self, monkeypatch: pytest.MonkeyPatch, kernel: KernelDoHidPlaystation,
        transporte: str, botoes: tuple[str, ...], gesto: str,
    ) -> None:
        bancada = montar_atalhos(monkeypatch, kernel, 4, transporte)
        for uniq in UNIQS[:4]:
            assert bancada.apertar(uniq, *botoes) == [gesto], f"{uniq} não alcançou {gesto}"


@pytest.mark.usefixtures("config_isolado")
class TestOsApertosNaoSeMisturam:
    """O PS de um e o R3 de outro não são um PS + R3 de ninguém."""

    @pytest.mark.parametrize("transporte", list(TRANSPORTES))
    def test_o_ps_de_um_e_o_r3_de_outro_nao_trocam_o_modo(
        self, monkeypatch: pytest.MonkeyPatch, kernel: KernelDoHidPlaystation, transporte: str,
    ) -> None:
        """Ninguém fez o PS + R3: o P1 fez um PS sozinho, e é ele que dispara."""
        bancada = montar_atalhos(monkeypatch, kernel, 3, transporte)
        with structlog.testing.capture_logs() as registros:
            disparou = _apertar_juntos(bancada, {P1: ("ps",), P2: ("r3",)})
        assert disparou == ["ps_solo"], f"os dois apertos viraram {disparou}"
        assert _disparos_no_diario(registros) == [("ps_solo", P1)]

    def test_um_gesto_por_aperto_vale_para_cada_controle(
        self, monkeypatch: pytest.MonkeyPatch, kernel: KernelDoHidPlaystation,
    ) -> None:
        """O P2 segura o PS + R3 que já disparou; o PS + L3 do P3 dispara mesmo assim."""
        bancada = montar_atalhos(monkeypatch, kernel, 3)
        bancada.mesa.apertados[P2] = frozenset({"ps", "r3"})  # type: ignore[attr-defined]
        bancada.tique(0.0)
        bancada.tique(0.3)
        assert bancada.disparos[-1:] == ["ponte"]
        antes = len(bancada.disparos)
        bancada.mesa.apertados[P3] = frozenset({"ps", "l3"})  # type: ignore[attr-defined]
        bancada.tique(0.0)
        bancada.tique(0.3)
        bancada.tique(0.3)
        assert bancada.disparos[antes:] == ["mascara"], (
            "o combo que o P2 segura travou o gesto do P3"
        )


def _o_gesto_pelo_laco(bancada: MesaDosAtalhos, uniq: str, *botoes: str) -> None:
    """``uniq`` faz o gesto, e o ato roda como o daemon o roda: tarefa, com o laço seguindo."""

    async def _junto() -> None:
        bancada.apertar(uniq, *botoes)
        este = asyncio.current_task()
        for _ in range(500):
            pendentes = [t for t in asyncio.all_tasks() if t is not este and not t.done()]
            if not pendentes:
                return
            await asyncio.sleep(0)
            bancada.tique(0.0)
        raise AssertionError("o ato do gesto não terminou")

    asyncio.run(_junto())


@pytest.mark.usefixtures("config_isolado")
class TestOPsL3AndaOCartaoDeQuemFaz:
    """Com o P1 na mesa, o PS + L3 do P3 troca a máscara DO P3."""

    @pytest.mark.parametrize("transporte", list(TRANSPORTES))
    def test_o_ps_l3_do_p3_troca_a_mascara_dele(
        self, monkeypatch: pytest.MonkeyPatch, kernel: KernelDoHidPlaystation, transporte: str,
    ) -> None:
        bancada = montar_atalhos(monkeypatch, kernel, 3, transporte)
        luz = armar_o_ato_do_daemon(bancada, monkeypatch).luz
        bancada.daemon._hotkey_manager.on_next_mask = build_next_mask_callback(bancada.daemon)
        posto = bancada.daemon._gamepad_device
        vpad_do_p2 = bancada.vpad_de(P2)
        assert em.mascara_vestida(bancada.daemon, P3) == "dualsense"

        with structlog.testing.capture_logs() as registros:
            _o_gesto_pelo_laco(bancada, P3, "ps", "l3")
        bancada.tique()

        assert _disparos_no_diario(registros) == [("mascara", P3)]
        assert em.mascara_vestida(bancada.daemon, P3) == "xbox", "a máscara do P3 não trocou"
        assert em.registro_de_mascaras().mask_for(P1) is None, "o cartão do P1 andou"
        assert em.registro_de_mascaras().mask_for(P2) is None, "o cartão do P2 andou"
        assert bancada.daemon._gamepad_device is posto and posto.vivo, (
            "o gesto do P3 recriou o vpad do P1"
        )
        assert bancada.vpad_de(P2) is vpad_do_p2, "o gesto do P3 recriou o P2"
        assert ("piscada", "mascara:xbox") in luz, f"a luz disse {luz}"
        assert bancada.a_tela() == {P1: 1, P2: 2, P3: 3}
        bancada.o_jogo_segue_a_tela()


class _LeitorPassivoDaMesa:
    """O leitor PASSIVO do ``SensorHub`` (STATUS-04), sem grab, sobre a mesa da bancada."""

    def __init__(self, mesa: Any, uniq: str, node: Any) -> None:
        self._mesa = mesa
        self.uniq = uniq
        self.node = str(node)

    def start(self) -> bool:
        return True

    def stop(self) -> None:
        return None

    def snapshot(self) -> Any:
        apertados: frozenset[str] = frozenset()
        no_lugar = self._mesa.nodes.get(self.uniq) == self.node
        if no_lugar and self._mesa.dono_do_grab.get(self.node) is None:
            apertados = self._mesa.apertados.get(self.uniq, frozenset())
        return SimpleNamespace(
            lx=128, ly=128, rx=128, ry=128, l2_raw=0, r2_raw=0, buttons_pressed=apertados
        )


class MesaSemCoop(MesaDosAtalhos):
    """A bancada dos atalhos com o ``SensorHub`` real no daemon, movido a cada tique."""

    def __init__(self, monkeypatch: pytest.MonkeyPatch, **kw: Any) -> None:
        super().__init__(monkeypatch, **kw)
        self.hub = SensorHub(
            gamepad_factory=lambda uniq, node: _LeitorPassivoDaMesa(self.mesa, uniq, node),
            descobrir_gamepad=self.mesa.como_o_coop_ve,
            descobrir_motion=dict,
            descobrir_touch=dict,
            relogio=self.tempo,
            auto_manutencao=False,
        )
        self.daemon._garantir_sensor_hub = lambda: self.hub

    def tique(self, segundos: float = TIQUE) -> None:
        self.hub.reconciliar()
        super().tique(segundos)


def montar_sem_coop(
    monkeypatch: pytest.MonkeyPatch, kernel: KernelDoHidPlaystation, modo: str, transporte: str
) -> MesaSemCoop:
    """Três controles na mesa, com o co-op desligado ou em mouse e teclado (sem vpad do P1)."""
    bancada = MesaSemCoop(
        monkeypatch,
        kernel=kernel,
        relogio=Relogio(),
        caminho=CAMINHO_NATIVO if modo == "mouse-e-teclado" else CAMINHO_VIRTUAL,
        coop=modo != "co-op-desligado",
    )
    for uniq, via in zip(UNIQS[:3], TRANSPORTES[transporte][:3], strict=True):
        bancada.mesa.sentar(uniq, transporte=via)
    for _ in range(3):
        bancada.tique()
    assert bancada.coop.live_snapshots() == {}, "premissa: o co-op não segura ninguém"
    assert bancada.inst.primary_uniq == P1
    return bancada


@pytest.mark.usefixtures("config_isolado")
class TestSemOCoop:
    """Em mouse e teclado e com o co-op desligado, os outros controles também têm os atalhos."""

    @pytest.mark.parametrize("transporte", list(TRANSPORTES))
    @pytest.mark.parametrize("modo", ["mouse-e-teclado", "co-op-desligado"])
    def test_os_outros_alcancam_o_ps_pelo_leitor_passivo(
        self, monkeypatch: pytest.MonkeyPatch, kernel: KernelDoHidPlaystation,
        modo: str, transporte: str,
    ) -> None:
        bancada = montar_sem_coop(monkeypatch, kernel, modo, transporte)
        with structlog.testing.capture_logs() as registros:
            assert bancada.apertar(P1, "ps", "r3") == ["ponte"]
            assert bancada.apertar(P2, "ps", "r3") == ["ponte"], "o P2 ficou mudo sem o co-op"
            assert bancada.apertar(P3, "ps") == ["ps_solo"], "o PS do P3 não abriu a Steam"
        assert _disparos_no_diario(registros) == [
            ("ponte", P1), ("ponte", P2), ("ps_solo", P3)
        ]

    def test_o_leitor_passivo_nao_e_aberto_no_posto(
        self, monkeypatch: pytest.MonkeyPatch, kernel: KernelDoHidPlaystation,
    ) -> None:
        """O posto já tem leitor: o hub só abre leitor para quem não tem outra fonte."""
        bancada = montar_sem_coop(monkeypatch, kernel, "mouse-e-teclado", "mista")
        bancada.tique()
        assert set(bancada.hub._gamepad) == {P2, P3}


@pytest.mark.usefixtures("config_isolado")
class TestQuemRenasceNaoGanhaLeitorPassivo:
    """O co-op segura o nó de quem renasce: o hub não abre um segundo leitor ali."""

    def test_o_grab_pendente_nao_pede_o_leitor_do_hub(
        self, monkeypatch: pytest.MonkeyPatch, kernel: KernelDoHidPlaystation,
    ) -> None:
        bancada = MesaSemCoop(monkeypatch, kernel=kernel, relogio=Relogio())
        for uniq, via in zip(UNIQS[:3], TRANSPORTES["mista"][:3], strict=True):
            bancada.mesa.sentar(uniq, transporte=via)
        for _ in range(3):
            bancada.tique()
        assert set(bancada.coop.live_snapshots()) == {P2, P3}, "premissa: o co-op de pé"
        assert bancada.hub._demanda_entradas == {}, "o co-op de pé já tem leitor"
        bancada.coop._teardown_player(P2)
        bancada.tique()
        jogador = bancada.coop._players.get(P2)
        assert jogador is not None and jogador.vpad is None, "premissa: o P2 renasce"
        assert P2 not in bancada.hub._demanda_entradas, (
            "o hub abriu um leitor passivo sobre o nó que o co-op segura"
        )
