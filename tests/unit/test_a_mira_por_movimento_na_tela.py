"""A-MIRA-POR-MOVIMENTO-NA-TELA-01 — a mira que nunca andou, e o chip dela."""

from __future__ import annotations

import re
import sys
from collections.abc import Iterator
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from hefesto_dualsense4unix.core.controller import ControllerState
from hefesto_dualsense4unix.core.virtual_motion import REGISTRO
from hefesto_dualsense4unix.daemon.ipc_server import IpcServer
from hefesto_dualsense4unix.daemon.lifecycle import Daemon
from hefesto_dualsense4unix.daemon.sensor_hub import SensorHub
from hefesto_dualsense4unix.daemon.subsystems import coop as co
from hefesto_dualsense4unix.daemon.subsystems import gamepad as gp
from hefesto_dualsense4unix.profiles.manager import ProfileManager
from hefesto_dualsense4unix.profiles.schema import (
    MatchAny,
    Profile,
    ProfileMovimentoConfig,
)
from hefesto_dualsense4unix.testing import FakeController

_P1, _P2, _P3, _P4 = (
    "aa:bb:cc:00:00:01",
    "aa:bb:cc:00:00:02",
    "aa:bb:cc:00:00:03",
    "aa:bb:cc:00:00:04",
)

_GIRO = (0.0, 150.0, 0.0)


@pytest.fixture(autouse=True)
def _registro_limpo() -> Iterator[None]:
    """O `REGISTRO` dos sensores é do processo: nada desta régua vaza dele."""
    REGISTRO.limpar()
    yield
    REGISTRO.limpar()


class _LeitorDoNo:
    """O leitor do nó «Motion Sensors» — a única peça de mentira da torneira."""

    def __init__(self, giro: tuple[float, float, float]) -> None:
        self._giro = giro

    def start(self) -> bool:
        return True

    def stop(self) -> None:
        pass

    def snapshot(self) -> Any:
        return SimpleNamespace(x=self._giro[0], y=self._giro[1], z=self._giro[2])

    def consume_angulo(self) -> tuple[float, float, float]:
        return (0.0, 0.0, 0.0)


def _hub(giro_por_uniq: dict[str, tuple[float, float, float]]) -> SensorHub:
    """O `SensorHub` REAL, com o nó e o leitor dublados — nenhum aparelho aberto."""
    hub = SensorHub(
        motion_factory=lambda uniq, node: _LeitorDoNo(giro_por_uniq[uniq]),
        touch_factory=lambda uniq, node: _LeitorDoNo((0.0, 0.0, 0.0)),
        gamepad_factory=lambda uniq, node: _LeitorDoNo((0.0, 0.0, 0.0)),
        descobrir_motion=lambda: {u: Path(f"/dev/input/event-{u}") for u in giro_por_uniq},
        descobrir_touch=dict,
        descobrir_gamepad=dict,
        auto_manutencao=False,
    )
    hub._watch = SimpleNamespace(poll=lambda: False)
    return hub


def _mesa_de_verdade(
    tmp_path: Path, transporte: str, hub: SensorHub
) -> tuple[Daemon, IpcServer]:
    """O `Daemon` e o `IpcServer` do produto, ligados como o `start_ipc` liga."""
    controle = FakeController(transport=transporte)  # type: ignore[arg-type]
    controle.primary_uniq = _P1  # type: ignore[attr-defined]
    daemon = Daemon(controller=controle)
    gerente = ProfileManager(controller=controle, store=daemon.store)
    servidor = IpcServer(
        controller=controle,
        store=daemon.store,
        profile_manager=gerente,
        socket_path=tmp_path / "mira.sock",
        daemon=daemon,
    )
    servidor._sensor_hub = hub
    daemon._ipc_server = servidor
    gerente.apply_movimento(
        Profile(
            name="Com mira",
            match=MatchAny(type="any"),
            movimento=ProfileMovimentoConfig(destino="analogico_direito"),
        )
    )
    return daemon, servidor


class _Vpad:
    """O gamepad virtual: guarda o que o JOGO receberia."""

    def __init__(self) -> None:
        self.analog: list[dict[str, int]] = []

    def forward_analog(self, **kw: int) -> None:
        self.analog.append(kw)

    def forward_buttons(self, pressed: frozenset[str]) -> None:
        pass


def _estado(transporte: str) -> ControllerState:
    return ControllerState(
        battery_pct=100, l2_raw=0, r2_raw=0, connected=True, transport=transporte  # type: ignore[arg-type]
    )


def _tique_do_p1(
    monkeypatch: pytest.MonkeyPatch, daemon: Daemon, hub: SensorHub, transporte: str
) -> _Vpad:
    """Dois tiques do `dispatch_gamepad`, com a reconciliação do hub no meio."""
    monkeypatch.setattr(gp, "_reconciliar_launch", lambda d: None)
    monkeypatch.setattr(gp, "_avisar_troca_de_modo", lambda d: None)
    vpad = _Vpad()
    daemon._gamepad_device = vpad
    gp.dispatch_gamepad(daemon, _estado(transporte), frozenset())
    hub.reconciliar()
    gp.dispatch_gamepad(daemon, _estado(transporte), frozenset())
    return vpad


@pytest.mark.parametrize("transporte", ["usb", "bt"])
def test_a_mira_anda_no_daemon_de_verdade(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, transporte: str
) -> None:
    """O P1, no cabo e no rádio, com o `Daemon` que o produto sobe."""
    hub = _hub({_P1: _GIRO})
    daemon, _servidor = _mesa_de_verdade(tmp_path, transporte, hub)
    vpad = _tique_do_p1(monkeypatch, daemon, hub, transporte)
    assert vpad.analog, "o tique nem chegou ao vpad"
    assert vpad.analog[-1]["rx"] != 128, (
        f"o controle girou {_GIRO} graus/s e o analógico direito saiu parado "
        f"({vpad.analog[-1]}) — o `Daemon` real não entrega o hub ao motor")


@pytest.mark.parametrize("transporte", ["usb", "bt"])
def test_a_mira_anda_nos_jogadores_2_3_e_4_no_daemon_de_verdade(
    tmp_path: Path, transporte: str
) -> None:
    """Os P2 a P4, pelo `CoopManager` real sobre o mesmo `Daemon` real."""
    giros = {_P2: _GIRO, _P3: _GIRO, _P4: _GIRO}
    hub = _hub(giros)
    daemon, _servidor = _mesa_de_verdade(tmp_path, transporte, hub)
    gerente = co.CoopManager(daemon)
    vpads: dict[str, _Vpad] = {}
    for n, uniq in enumerate(sorted(giros), start=2):
        vpads[uniq] = _Vpad()
        gerente._players[uniq] = co._SecondaryPlayer(
            identity=uniq,
            evdev_path=f"/dev/input/event{n}",
            reader=SimpleNamespace(
                snapshot=lambda: SimpleNamespace(
                    lx=128, ly=128, rx=128, ry=128, l2_raw=0, r2_raw=0,
                    buttons_pressed=frozenset()),
                grab_state="held",
            ),
            player_index=n,
            vpad=vpads[uniq],
        )
    gerente.forward_all()
    hub.reconciliar()
    gerente.forward_all()
    for uniq, vpad in sorted(vpads.items()):
        assert vpad.analog[-1]["rx"] != 128, (
            f"o jogador {uniq} girou o controle e não mirou — o `Daemon` real "
            f"não entrega o hub ao laço dos secundários")


def test_o_hub_da_mira_e_o_mesmo_do_ipc(tmp_path: Path) -> None:
    """UM HUB SÓ POR SESSÃO. Dois hubs abririam dois leitores no mesmo nó e"""
    hub = _hub({_P1: _GIRO})
    daemon, servidor = _mesa_de_verdade(tmp_path, "usb", hub)
    assert daemon._garantir_sensor_hub() is servidor._garantir_sensor_hub() is hub


def test_sem_servidor_os_eixos_saem_como_entraram(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """O instante antes de o IPC subir (ou um IPC que caiu): sem hub, sem mira,"""
    from structlog.testing import capture_logs

    hub = _hub({_P1: _GIRO})
    daemon, _servidor = _mesa_de_verdade(tmp_path, "usb", hub)
    daemon._ipc_server = None
    with capture_logs() as logs:
        vpad = _tique_do_p1(monkeypatch, daemon, hub, "usb")
    assert vpad.analog and vpad.analog[-1]["rx"] == 128
    avisos = [e for e in logs if e.get("event") == "roteador_de_movimento_falhou"]
    assert not avisos, f"o tique sem servidor registrou {len(avisos)} aviso(s): {avisos}"


def _mira(**kw: Any) -> Any:
    from hefesto_dualsense4unix.core import roteador_de_movimento as rot

    base: dict[str, Any] = {"destino": rot.DESTINO_ANALOGICO_DIREITO}
    base.update(kw)
    return rot.ArranjoDeMovimento(**base)


def test_o_arranjo_desligado_nao_move_nada() -> None:
    """O arranjo `nenhum` guarda os números dos deslizantes e não move o eixo."""
    from hefesto_dualsense4unix.core import roteador_de_movimento as rot

    desligado = _mira(destino=rot.DESTINO_NENHUM, sensibilidade=12)
    assert rot.deflexao((0.0, 200.0, 0.0), desligado) == (0, 0)
    assert rot.pixels((0.0, 30.0, 0.0), desligado) == (0.0, 0.0)
    assert rot.deflexao((0.0, 200.0, 0.0), rot.SO_NAS_PECAS) == (0, 0)


def test_o_arranjo_desligado_guarda_os_numeros_dela() -> None:
    """`montar` devolve o arranjo mesmo com a mira apagada, e o `ativo()` não o"""
    from hefesto_dualsense4unix.core import roteador_de_movimento as rot

    secao = ProfileMovimentoConfig(destino="nenhum", zona_morta_graus_s=25.0)
    montado = rot.montar(secao)
    assert montado.zona_morta_graus_s == 25.0 and not montado.ligado
    store = SimpleNamespace()
    rot.definir_ativo(store, montado)
    assert rot.ativo(store) is None
    assert rot.parametros_da_peca(store, _P1).zona_morta_graus_s == 25.0


def test_so_uma_peca_mira_e_o_tique_ainda_chama_o_motor() -> None:
    """Sem mira no perfil e com o chip aceso no P3, o `ativo()` NÃO pode dizer"""
    from hefesto_dualsense4unix.core import roteador_de_movimento as rot

    store = SimpleNamespace()
    rot.definir_ativo(store, None)
    assert rot.ativo(store) is None, "sem mira nenhuma o tique pagou o motor"
    rot.definir_por_peca(store, {_P3: _mira()})
    assert rot.ativo(store) is rot.SO_NAS_PECAS
    rot.definir_por_peca(store, {_P3: _mira(destino=rot.DESTINO_NENHUM)})
    assert rot.ativo(store) is None, "a peça de mira APAGADA acordou o motor"


def test_a_peca_com_opiniao_manda_e_a_calada_segue_o_perfil() -> None:
    """A ordem de decisão, nos dois sentidos."""
    from hefesto_dualsense4unix.core import roteador_de_movimento as rot

    store = SimpleNamespace()
    mesa = _mira(sensibilidade=4)
    rot.definir_ativo(store, mesa)
    rot.definir_por_peca(store, {
        _P3: _mira(sensibilidade=11),
        _P4: _mira(destino=rot.DESTINO_NENHUM),
    })
    ativo = rot.ativo(store)
    assert rot.da_peca(store, _P2, ativo) is mesa, "o P2 calado não seguiu o perfil"
    assert rot.da_peca(store, _P3, ativo).sensibilidade == 11, (
        "o P3 tem a mira dele e recebeu a do perfil")
    assert rot.da_peca(store, _P4, ativo) is None, (
        "o P4 APAGOU o chip e mira assim mesmo, pela mira do perfil")
    assert rot.da_peca(store, "aabbcc000003", ativo).sensibilidade == 11


def test_a_peca_sobrepoe_o_perfil_campo_a_campo() -> None:
    """A peça que só escreveu o destino HERDA do perfil a sensibilidade e o"""
    from hefesto_dualsense4unix.core import roteador_de_movimento as rot

    perfil = ProfileMovimentoConfig(destino="nenhum", zona_morta_graus_s=30.0,
                                    sensibilidade=9)
    peca = ProfileMovimentoConfig(destino="analogico_direito")
    arranjo = rot.arranjo_da_peca(perfil, peca)
    assert arranjo.ligado
    assert arranjo.zona_morta_graus_s == 30.0 and arranjo.sensibilidade == 9


def test_o_perfil_sem_mira_por_peca_apaga_a_do_anterior() -> None:
    """O CAMINHO-CONTAGIO-01 por peça: o P3 do jogo de ontem não mira no de hoje."""
    from hefesto_dualsense4unix.core import roteador_de_movimento as rot

    store = SimpleNamespace()
    rot.definir_por_peca(store, {_P3: _mira()})
    rot.definir_por_peca(store, {})
    assert rot.por_peca(store) == {}
    assert rot.ativo(store) is None


def _janela_viva() -> bytes:
    """Uma janela de motion com giro, aceleração e um dedo no touchpad."""
    from hefesto_dualsense4unix.core.virtual_motion import TAMANHO_DA_JANELA

    janela = bytearray(range(1, TAMANHO_DA_JANELA + 1))
    return bytes(janela)


def test_a_camera_nao_anda_em_dobro_no_caminho_virtual() -> None:
    """A PEÇA QUE MIRA PERDE O GIROSCÓPIO da janela do vpad, e SÓ ele."""
    from hefesto_dualsense4unix.core import roteador_de_movimento as rot
    from hefesto_dualsense4unix.core.virtual_motion import (
        FAIXA_ACELEROMETRO,
        FAIXA_GIROSCOPIO,
    )

    store = SimpleNamespace()
    rot.definir_ativo(store, None)
    rot.definir_por_peca(store, {_P3: _mira()})
    rot.sincronizar_o_filtro(store)
    janela = _janela_viva()
    do_p3 = REGISTRO.filtrar(_P3, janela)
    assert do_p3[FAIXA_GIROSCOPIO] == bytes(6), "o P3 mira e o jogo ainda recebe o giro"
    assert do_p3[FAIXA_ACELEROMETRO] == janela[FAIXA_ACELEROMETRO]
    assert do_p3[12:] == janela[12:], "a mira apagou o carimbo ou o touchpad"
    assert REGISTRO.filtrar(_P2, janela) is janela, "o P2 não mira e perdeu o giro"
    assert REGISTRO.estado(_P3).giroscopio is True


def test_a_mira_do_perfil_tira_o_giro_de_quem_nao_tem_opiniao() -> None:
    """Com a mira no PERFIL, toda peça calada mira — e perde o giro nativo; a"""
    from hefesto_dualsense4unix.core import roteador_de_movimento as rot
    from hefesto_dualsense4unix.core.virtual_motion import FAIXA_GIROSCOPIO

    store = SimpleNamespace()
    rot.definir_ativo(store, _mira())
    rot.definir_por_peca(store, {_P4: _mira(destino=rot.DESTINO_NENHUM)})
    rot.sincronizar_o_filtro(store)
    janela = _janela_viva()
    assert REGISTRO.filtrar(_P2, janela)[FAIXA_GIROSCOPIO] == bytes(6)
    assert REGISTRO.filtrar(_P4, janela) is janela
    rot.definir_ativo(store, None)
    rot.definir_por_peca(store, {})
    rot.sincronizar_o_filtro(store)
    assert REGISTRO.filtrar(_P2, janela) is janela


def _perfil_com_miras(**por_uniq: Any) -> Profile:
    from hefesto_dualsense4unix.profiles.schema import ControllerOverrides

    return Profile(
        name="miras",
        match=MatchAny(type="any"),
        controllers={
            uniq: ControllerOverrides(movimento=ProfileMovimentoConfig(**campos))
            for uniq, campos in por_uniq.items()
        },
    )


def test_a_mira_nasce_desligada() -> None:
    """O perfil novo, o controle novo e o perfil sem a seção: NINGUÉM mira."""
    from hefesto_dualsense4unix.core import roteador_de_movimento as rot
    from hefesto_dualsense4unix.profiles.schema import (
        NASCIMENTO_DOS_CAMPOS,
        ControllerOverrides,
    )

    assert ControllerOverrides().movimento is None
    assert ProfileMovimentoConfig().destino == "nenhum", (
        "a seção de mira nasce LIGADA — o perfil que só escreveu o tremor "
        "moveria a câmera")
    assert "ControllerOverrides.movimento" in NASCIMENTO_DOS_CAMPOS
    store = SimpleNamespace()
    gerente = ProfileManager.__new__(ProfileManager)
    gerente.store = store  # type: ignore[attr-defined]
    gerente.apply_movimento(Profile(name="nada", match=MatchAny(type="any")))
    assert rot.ativo(store) is None
    assert not REGISTRO.roteado(_P1), "o perfil calado tirou o giro do jogo"


def test_o_perfil_leva_a_mira_de_cada_peca_ao_tique() -> None:
    """A ativação deposita o mapa por peça, e cada uma decide a sua."""
    from hefesto_dualsense4unix.core import roteador_de_movimento as rot

    store = SimpleNamespace()
    gerente = ProfileManager.__new__(ProfileManager)
    gerente.store = store  # type: ignore[attr-defined]
    gerente.apply_movimento(_perfil_com_miras(**{
        "aabbcc000003": {"destino": "analogico_direito", "sensibilidade": 10},
        "aabbcc000004": {"destino": "nenhum", "zona_morta_graus_s": 25.0},
    }))
    ativo = rot.ativo(store)
    assert ativo is rot.SO_NAS_PECAS
    assert rot.da_peca(store, _P3, ativo).sensibilidade == 10
    assert rot.da_peca(store, _P4, ativo) is None
    assert rot.da_peca(store, _P2, ativo) is None
    assert rot.parametros_da_peca(store, _P4).zona_morta_graus_s == 25.0
    assert REGISTRO.roteado(_P3) and not REGISTRO.roteado(_P4)


def test_uma_peca_torta_nao_derruba_as_outras() -> None:
    """Só um `model_copy` sem validação chega aqui torto — e ele cala UMA peça."""
    from hefesto_dualsense4unix.core import roteador_de_movimento as rot

    perfil = _perfil_com_miras(**{
        "aabbcc000002": {"destino": "analogico_direito"},
        "aabbcc000003": {"destino": "analogico_direito"},
    })
    object.__setattr__(perfil.controllers["aabbcc000002"].movimento,
                       "destino", "destino_que_nao_existe")
    store = SimpleNamespace()
    gerente = ProfileManager.__new__(ProfileManager)
    gerente.store = store  # type: ignore[attr-defined]
    relatorio: dict[str, str] = {}
    gerente.apply_movimento(perfil, relatorio=relatorio)
    assert relatorio.get("movimento:aabbcc000002") == "falhou"
    ativo = rot.ativo(store)
    assert rot.da_peca(store, _P2, ativo) is None
    assert rot.da_peca(store, _P3, ativo) is not None, "a peça certa pagou pela torta"


def _mesa_de_quatro_de_verdade(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, transporte: str,
    perfil: Profile, *, antes: Profile | None = None, hub: SensorHub | None = None,
) -> dict[str, _Vpad]:
    """O `Daemon` real, o P1 pelo `dispatch_gamepad` e os P2 a P4 pelo co-op,"""
    giros = {_P1: _GIRO, _P2: _GIRO, _P3: _GIRO, _P4: _GIRO}
    hub = hub or _hub(giros)
    daemon, servidor = _mesa_de_verdade(tmp_path, transporte, hub)
    if antes is not None:
        servidor.profile_manager.apply_movimento(antes)
    servidor.profile_manager.apply_movimento(perfil)
    gerente = co.CoopManager(daemon)
    vpads: dict[str, _Vpad] = {}
    for n, uniq in enumerate((_P2, _P3, _P4), start=2):
        vpads[uniq] = _Vpad()
        gerente._players[uniq] = co._SecondaryPlayer(
            identity=uniq,
            evdev_path=f"/dev/input/event{n}",
            reader=SimpleNamespace(
                snapshot=lambda: SimpleNamespace(
                    lx=128, ly=128, rx=128, ry=128, l2_raw=0, r2_raw=0,
                    buttons_pressed=frozenset()),
                grab_state="held",
            ),
            player_index=n,
            vpad=vpads[uniq],
        )
    monkeypatch.setattr(gp, "_reconciliar_launch", lambda d: None)
    monkeypatch.setattr(gp, "_avisar_troca_de_modo", lambda d: None)
    vpads[_P1] = _Vpad()
    daemon._gamepad_device = vpads[_P1]
    for _ in range(2):
        gp.dispatch_gamepad(daemon, _estado(transporte), frozenset())
        gerente.forward_all()
        hub.reconciliar()
    return vpads


def _quem_mirou(vpads: dict[str, _Vpad]) -> list[str]:
    return sorted(u for u, v in vpads.items() if v.analog and v.analog[-1]["rx"] != 128)


@pytest.mark.parametrize("transporte", ["usb", "bt"])
def test_so_o_p3_acendeu_o_chip_e_so_o_p3_mira(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, transporte: str
) -> None:
    """O chip de UMA peça, num perfil sem mira: só ela mira, nos dois transportes."""
    perfil = _perfil_com_miras(aabbcc000003={"destino": "analogico_direito"})
    vpads = _mesa_de_quatro_de_verdade(monkeypatch, tmp_path, transporte, perfil)
    assert _quem_mirou(vpads) == [_P3], (
        f"com o chip aceso só no P3, miraram {_quem_mirou(vpads)}")


def test_a_peca_que_apagou_o_chip_nao_mira_pela_mira_do_perfil(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Mira no PERFIL, e o P1 (o primário) e o P4 apagaram o chip: miram o P2 e"""
    from hefesto_dualsense4unix.profiles.schema import ControllerOverrides

    apagado = ControllerOverrides(movimento=ProfileMovimentoConfig(destino="nenhum"))
    perfil = Profile(
        name="mesa com mira",
        match=MatchAny(type="any"),
        movimento=ProfileMovimentoConfig(destino="analogico_direito"),
        controllers={"aabbcc000001": apagado, "aabbcc000004": apagado},
    )
    vpads = _mesa_de_quatro_de_verdade(monkeypatch, tmp_path, "bt", perfil)
    assert _quem_mirou(vpads) == [_P2, _P3], (
        f"com o chip apagado no P1 e no P4, miraram {_quem_mirou(vpads)}")


@pytest.mark.parametrize("transporte", ["usb", "bt"])
def test_o_jogo_seguinte_nao_herda_a_mira_nem_o_giro_cortado(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, transporte: str
) -> None:
    """O CAMINHO-CONTAGIO-01 POR PEÇA, pela ATIVAÇÃO — e não pelo ajudante."""
    ontem = _perfil_com_miras(aabbcc000003={"destino": "analogico_direito"})
    hoje = Profile(name="sem mira", match=MatchAny(type="any"))
    vpads = _mesa_de_quatro_de_verdade(
        monkeypatch, tmp_path, transporte, hoje, antes=ontem)
    assert _quem_mirou(vpads) == [], (
        f"o jogo de hoje não tem mira e miraram {_quem_mirou(vpads)} — a mira "
        f"do jogo de ontem contagiou")
    janela = _janela_viva()
    assert REGISTRO.filtrar(_P3, janela) is janela, (
        "o jogo de hoje não tem mira e o P3 continua sem giroscópio no jogo — "
        "o filtro ficou com a resposta do jogo de ontem")


class _LeitorQueConta(_LeitorDoNo):
    """O leitor do nó que CONTA as drenagens do acumulador de ângulo."""

    def __init__(self, giro: tuple[float, float, float]) -> None:
        super().__init__(giro)
        self.drenagens = 0

    def consume_angulo(self) -> tuple[float, float, float]:
        self.drenagens += 1
        return (0.0, 0.0, 0.0)


def test_a_peca_que_apagou_o_chip_ainda_drena_o_angulo(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A DRENAGEM VEM ANTES DE TODO PORTÃO — inclusive o da peça."""
    from hefesto_dualsense4unix.profiles.schema import ControllerOverrides

    leitores: dict[str, _LeitorQueConta] = {}

    def _abrir(uniq: str, node: Any) -> _LeitorQueConta:
        leitores[uniq] = _LeitorQueConta(_GIRO)
        return leitores[uniq]

    todos = (_P1, _P2, _P3, _P4)
    hub = SensorHub(
        motion_factory=_abrir,
        touch_factory=lambda uniq, node: _LeitorDoNo((0.0, 0.0, 0.0)),
        gamepad_factory=lambda uniq, node: _LeitorDoNo((0.0, 0.0, 0.0)),
        descobrir_motion=lambda: {u: Path(f"/dev/input/event-{u}") for u in todos},
        descobrir_touch=dict,
        descobrir_gamepad=dict,
        auto_manutencao=False,
    )
    hub._watch = SimpleNamespace(poll=lambda: False)
    perfil = Profile(
        name="mesa no cursor",
        match=MatchAny(type="any"),
        movimento=ProfileMovimentoConfig.model_construct(destino="mouse"),
        controllers={"aabbcc000004": ControllerOverrides(
            movimento=ProfileMovimentoConfig(destino="nenhum"))},
    )
    _mesa_de_quatro_de_verdade(monkeypatch, tmp_path, "bt", perfil, hub=hub)
    drenagens = {u: (leitores[u].drenagens if u in leitores else 0) for u in todos}
    assert drenagens[_P2] >= 1, f"nem a peça que mira drenou — régua cega: {drenagens}"
    assert drenagens[_P4] == drenagens[_P2], (
        f"a peça de chip apagado não descartou o ângulo: {drenagens}")


# 5. O IPC — `mira.set` e a leitura de volta no `state_full`


@pytest.fixture
def perfis(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Diretório de perfis isolado — o molde do `test_o_sensor_desliga_de_verdade`."""
    from hefesto_dualsense4unix.profiles import loader as loader_module

    alvo = tmp_path / "profiles"
    alvo.mkdir()

    def _dir(ensure: bool = False) -> Path:
        if ensure:
            alvo.mkdir(parents=True, exist_ok=True)
        return alvo

    monkeypatch.setattr(loader_module, "profiles_dir", _dir)
    return alvo


def _servidor_com_perfil(tmp_path: Path, perfil: Profile | None = None) -> IpcServer:
    """O `IpcServer` real sobre o `Daemon` real, com um perfil ATIVO no disco."""
    from hefesto_dualsense4unix.profiles.loader import save_profile

    perfil = perfil or Profile(name="Bancada", match=MatchAny(type="any"))
    save_profile(perfil)
    _daemon, servidor = _mesa_de_verdade(tmp_path, "usb", _hub({}))
    servidor.profile_manager.apply_movimento(perfil)
    servidor.store.set_active_profile(perfil.name)
    return servidor


def _mira_set(servidor: IpcServer, **params: Any) -> dict[str, Any]:
    import asyncio

    return asyncio.run(servidor._handlers["mira.set"](params))


def test_o_que_ela_escolhe_chega_ao_disco(perfis: Path, tmp_path: Path) -> None:
    """O chip grava NO PERFIL daquela peça, e só o que o usuário mexeu."""
    from hefesto_dualsense4unix.core import roteador_de_movimento as rot
    from hefesto_dualsense4unix.profiles.loader import load_profile

    servidor = _servidor_com_perfil(tmp_path)
    corpo = _mira_set(servidor, uniq=_P3, ligada=True)
    assert corpo["status"] == "ok" and corpo["gravado"] is True and corpo["ligada"]
    dele = load_profile("Bancada").controllers["aabbcc000003"].movimento
    assert dele is not None and dele.destino == "analogico_direito"
    assert dele.model_fields_set == {"destino"}, (
        "o chip gravou campos que ela não mexeu — a peça deixaria de herdar do "
        "perfil")
    corpo = _mira_set(servidor, uniq=_P3, zona_morta_graus_s=22.0)
    dele = load_profile("Bancada").controllers["aabbcc000003"].movimento
    assert dele.destino == "analogico_direito" and dele.zona_morta_graus_s == 22.0
    store = servidor.store
    assert rot.da_peca(store, _P3, rot.ativo(store)).zona_morta_graus_s == 22.0
    assert REGISTRO.roteado(_P3) and not REGISTRO.roteado(_P2)


def test_a_tela_nao_liga_a_mira_sozinha(perfis: Path, tmp_path: Path) -> None:
    """Mexer no deslizante de um controle de mira apagada NÃO a acende."""
    servidor = _servidor_com_perfil(tmp_path)
    corpo = _mira_set(servidor, uniq=_P2, sensibilidade=9)
    assert corpo["status"] == "ok" and corpo["ligada"] is False
    assert not REGISTRO.roteado(_P2)
    entradas: list[dict[str, Any]] = [{"uniq": _P1}, {"uniq": _P2}]
    servidor._merge_mira(entradas)
    assert [e["mira"]["ligada"] for e in entradas] == [False, False]
    assert entradas[1]["mira"]["sensibilidade"] == 9, (
        "o número que ela ajustou com a mira apagada sumiu da leitura de volta")


def test_o_ps_nunca_vira_gatilho_pela_tela(perfis: Path, tmp_path: Path) -> None:
    """O PS é a saída de emergência dela, e nenhum pedido da tela o torna"""
    from hefesto_dualsense4unix.profiles.loader import load_profile

    servidor = _servidor_com_perfil(tmp_path)
    with pytest.raises(ValueError, match="gatilho"):
        _mira_set(servidor, uniq=_P3, ligada=True, gatilho="ps")
    assert not load_profile("Bancada").controllers, "a recusa gravou alguma coisa"


def test_o_chip_apagado_vence_a_mira_do_perfil_e_a_tela_ve(
    perfis: Path, tmp_path: Path
) -> None:
    """Perfil com mira na mesa, e ela apaga o chip do P4: o P4 não mira, e o
    `state_full` diz isso pela mesma pergunta que o tique faz."""
    perfil = Profile(
        name="Bancada",
        match=MatchAny(type="any"),
        movimento=ProfileMovimentoConfig(destino="analogico_direito"),
    )
    servidor = _servidor_com_perfil(tmp_path, perfil)
    _mira_set(servidor, uniq=_P4, ligada=False)
    entradas: list[dict[str, Any]] = [{"uniq": _P2}, {"uniq": _P4}]
    servidor._enriquecer_e_medir_o_ar({}, entradas, None)
    assert entradas[0]["mira"]["ligada"] is True, "o P2 calado não seguiu o perfil"
    assert entradas[1]["mira"]["ligada"] is False, "o chip apagado do P4 não pegou"
    assert REGISTRO.roteado(_P2) and not REGISTRO.roteado(_P4)


def test_o_deslizante_da_peca_calada_segue_a_mira_do_perfil(
    perfis: Path, tmp_path: Path
) -> None:
    """O perfil tem a mira na mesa, com a sensibilidade 9; ela mexe só no"""
    from hefesto_dualsense4unix.core import roteador_de_movimento as rot
    from hefesto_dualsense4unix.profiles.loader import load_profile

    perfil = Profile(
        name="Bancada",
        match=MatchAny(type="any"),
        movimento=ProfileMovimentoConfig(destino="analogico_direito", sensibilidade=9),
    )
    servidor = _servidor_com_perfil(tmp_path, perfil)
    corpo = _mira_set(servidor, uniq=_P2, zona_morta_graus_s=20.0)
    assert corpo["ligada"] is True and corpo["sensibilidade"] == 9, corpo
    store = servidor.store
    vivo = rot.da_peca(store, _P2, rot.ativo(store))
    assert vivo is not None and (vivo.sensibilidade, vivo.zona_morta_graus_s) == (9, 20.0), (
        f"mexer no tremor do P2 mudou a mira dele para {vivo}")
    servidor.profile_manager.apply_movimento(load_profile("Bancada"))
    assert rot.da_peca(store, _P2, rot.ativo(store)) == vivo, (
        "a próxima ativação, lendo o disco, dá outra mira ao P2 que a do vivo")


def test_em_modo_nativo_a_resposta_diz_o_que_nao_alcanca(
    perfis: Path, tmp_path: Path
) -> None:
    """Sem gamepad virtual não há onde a mira escreva — a RESPOSTA diz. A tela"""
    servidor = _servidor_com_perfil(tmp_path)
    servidor.daemon._native_mode = True
    corpo = _mira_set(servidor, uniq=_P3, sensibilidade=8)
    assert corpo["alcance"] == {"tique": "nao_se_aplica"}
    assert "Nativo" in (corpo["ressalva"] or "")
    assert corpo["gravado"] is True


def test_o_metodo_esta_no_dispatcher() -> None:
    """A tela chama pelo NOME; sem a linha no `_handlers`, o chip responde"""
    import inspect

    from hefesto_dualsense4unix.app import ipc_bridge

    fonte = inspect.getsource(IpcServer.__post_init__)
    assert '"mira.set": self._handle_mira_set' in fonte
    assert "mira_set_detalhado" in ipc_bridge.__all__


_RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_RAIZ / "src" / "hefesto_dualsense4unix" / "interface"))

_DICA_DELA = ("Usar os movimentos do controle como mira (analógico R), para "
              "pessoas com deficiência motora.")


def _cartoes_da_bancada() -> list[tuple[str, str]]:
    """`(abertura, miolo)` de cada cartão da aba Controles, na bancada."""
    doc = (_RAIZ / "mockup/02-controles.html").read_text(encoding="utf-8")
    doc = doc.split('<div class="nota">', 1)[0]
    partes = re.split(r'(?=<div class="ctl card)', doc)[1:]
    assert partes, "a bancada não tem cartão de controle — régua cega"
    return [(parte.split(">", 1)[0], parte) for parte in partes]


def test_o_chip_da_mira_esta_em_cada_controle_com_a_dica_dela() -> None:
    """MORDIDA: troque uma vírgula da dica no gerador, ou tire o `off`, e reprova."""
    for abertura, miolo in _cartoes_da_bancada():
        chips = re.findall(r'<span class="chip-da-mira([^"]*)"([^>]*)>'
                           r'<button class="sw" data-gesto="mira"([^>]*)>'
                           r'<span class="p"></span>([^<]*)</button></span>', miolo)
        assert len(chips) == 1, f"{abertura}: {len(chips)} chip(s) da mira"
        classe, involucro, atributos, rotulo = chips[0]
        assert rotulo == "Mira Virtual", rotulo
        assert f'title="{_DICA_DELA}"' in atributos, atributos
        assert 'data-campo="mira-ligada"' in involucro
        assert 'data-hef-quando="DESLIGADO"' in involucro
        assert 'data-campo="mira-fora"' in atributos
        assert 'data-hef-atributo="aria-disabled"' in atributos
        if 'data-conectado="nao"' not in abertura:
            assert "off" in classe.split(), (
                f"{abertura}: o chip da mira nasceu aceso — ela nasce desligada")
        grupo = miolo.split('<span class="sensores-peca"', 1)[1].split("\n          </span>", 1)[0]
        assert grupo.index('data-sensor="acelerometro"') < grupo.index(
            'data-gesto="mira"'), "o chip não está ao lado dos dois de sensor"


def test_o_chip_giroscopio_nao_mudou() -> None:
    """A palavra de produto: *o chip Giroscópio NÃO muda* — liga o sensor e manda o giro."""
    for abertura, miolo in _cartoes_da_bancada():
        giro = re.findall(r'<button class="sw[^"]*" data-gesto="sensor" '
                          r'data-sensor="giroscopio" data-campo="giro-ligado"[^>]*>'
                          r'<span class="p"></span>([^<]*)</button>', miolo)
        assert giro == ["Giroscópio"], (abertura, giro)
        dica = re.findall(r'<span class="dica-do-giro"[^>]*?(?: title="([^"]*)")?>'
                          r'<button[^>]*data-sensor="giroscopio"', miolo)
        esperada = ("" if 'data-conectado="nao"' in abertura
                    else "Ligado: o jogo recebe o giro deste controle.")
        assert dica == [esperada], (abertura, dica)


def test_o_rotulo_do_tremor_nao_diz_zona_morta() -> None:
    """§5 da sprint: a palavra técnica esconde para que o campo serve."""
    import calibrar

    assert calibrar.ROTULO_TREMOR == "Ignorar tremor até"
    doc = (_RAIZ / "mockup/calibrar-sensores.html").read_text(encoding="utf-8")
    visivel = re.sub(r"<style>.*?</style>|<!--.*?-->", "", doc, flags=re.S)
    assert "zona morta" not in visivel.lower()
    assert calibrar.ROTULO_TREMOR in visivel


def _faixa_do_esquema(campo: str) -> tuple[float, float, float]:
    info = ProfileMovimentoConfig.model_fields[campo]
    ge = next(m.ge for m in info.metadata if hasattr(m, "ge"))
    le = next(m.le for m in info.metadata if hasattr(m, "le"))
    return ge, le, info.default


def test_os_numeros_dos_deslizantes_sao_os_do_esquema() -> None:
    """O gerador roda sem o pacote e escreve os números; o dono é o esquema."""
    import calibrar

    escrito = calibrar.SENSIBILIDADE
    assert escrito == _faixa_do_esquema("sensibilidade")
    ge, le, nasce = _faixa_do_esquema("zona_morta_graus_s")
    assert (ge, le, nasce) == (0.0, 60.0, 3.0), "o esquema mudou — releia a sprint"
    escrito = calibrar.TREMOR
    assert escrito == (1, le, nasce)


def test_a_calibrar_tem_os_dois_deslizantes_de_cada_controle() -> None:
    """Uma coluna por cartão, com o MESMO `data-controle` — é ele que leva o"""
    import calibrar

    doc = (_RAIZ / "mockup/calibrar-sensores.html").read_text(encoding="utf-8")
    cartoes = re.findall(r'<div class="ctr"[^>]*\s+data-controle="(p\d)"', doc)
    colunas = re.findall(r'<div class="mira" data-controle="(p\d)">', doc)
    assert cartoes and colunas == cartoes, (cartoes, colunas)
    for gesto, (minimo, maximo, nasce) in (("mira-sensibilidade", calibrar.SENSIBILIDADE),
                                           ("mira-tremor", calibrar.TREMOR)):
        trilhos = re.findall(rf'<input class="trilho" type="range" min="{minimo}" '
                             rf'max="{maximo}" step="1" value="{nasce}" '
                             rf'data-gesto="{gesto}"', doc)
        assert len(trilhos) == len(cartoes), (gesto, len(trilhos))


class _PonteDaMira:
    """O dublê ESTRITO da ponte: devolve o corpo do daemon, como a real."""

    def __init__(self, corpo: dict[str, Any] | None) -> None:
        self.corpo = corpo
        self.chamadas: list[dict[str, Any]] = []

    def mira_set_detalhado(self, **kw: Any) -> dict[str, Any] | None:
        import inspect

        from hefesto_dualsense4unix.app import ipc_bridge

        inspect.signature(ipc_bridge.mira_set_detalhado).bind(**kw)
        self.chamadas.append(kw)
        return self.corpo


_OK = {"status": "ok", "alcance": {"tique": "aplicado"}, "ressalva": None}


def _ctx_da_aba(**entrada: Any) -> Any:
    import pacotes

    dele = {"uniq": _P1, "transport": "usb", "connected": True, "inputs": {},
            "audio": {}, "speaker": {}, **entrada}
    return pacotes.Contexto(state={}, mesa=[], conectados=[dele], estados={})


def _o_gesto(pagina: str, nome: str) -> Any:
    import pacotes

    fn = pacotes.gesto_da_pagina(pagina, nome)
    assert fn is not None, f"{pagina}:{nome} não tem dono"
    return fn


def test_o_chip_alterna_pelo_que_o_daemon_diz() -> None:
    """MORDIDA: mande `ligada=True` fixo e o segundo caso reprova."""
    for agora in (False, True):
        p = _PonteDaMira(_OK)
        _o_gesto("02-controles.html", "mira")(
            _ctx_da_aba(mira={"ligada": agora, "sensibilidade": 6}),
            {"uniq": _P1}, p)
        assert p.chamadas == [{"ligada": not agora, "uniq": _P1}]


def test_sem_leitura_o_chip_recusa_dizendo() -> None:
    """Sem o bloco `mira`, alternar é chutar o oposto: recusa e não chama."""
    import pacotes.a02_controles as a02

    p = _PonteDaMira(_OK)
    with pytest.raises(RuntimeError) as erro:
        _o_gesto("02-controles.html", "mira")(_ctx_da_aba(), {"uniq": _P1}, p)
    assert str(erro.value) == a02.SEM_LEITURA_DA_MIRA
    assert p.chamadas == []


def test_o_chip_recusa_o_que_o_daemon_nao_confirma() -> None:
    """O daemon que responde sem `ok` não vira «aplicado»: a recusa sai com a"""
    import pacotes.a02_controles as a02

    p = _PonteDaMira({"status": "sem_controle", "motivo": "texto do daemon"})
    with pytest.raises(RuntimeError) as erro:
        _o_gesto("02-controles.html", "mira")(
            _ctx_da_aba(mira={"ligada": False}), {"uniq": _P1}, p)
    assert str(erro.value) == a02.MIRA_SEM_O_CONTROLE


def test_o_chip_pinta_pelo_que_o_daemon_diz(monkeypatch: pytest.MonkeyPatch) -> None:
    """Três estados: aceso, apagado e o travessão de quem não leu."""
    import mesa_viva

    import pacotes.a02_controles as a02

    monkeypatch.setattr(a02, "_so_se_a_pagina_tiver", lambda campos: campos)

    def _campo(**entrada: Any) -> Any:
        cards = a02.pacote(_ctx_da_aba(**entrada))["cards"]
        assert cards, "o pacote não montou card nenhum — régua cega"
        return next(iter(cards.values()))["mira-ligada"]

    assert _campo(mira={"ligada": True}) == a02.SENSOR_LIGADO
    assert _campo(mira={"ligada": False}) == a02.SENSOR_DESLIGADO
    assert _campo() == mesa_viva.SEM_LEITOR


def test_os_deslizantes_mandam_um_campo_so() -> None:
    """O arrasto na Calibrar não acende o chip nem mexe no outro deslizante."""
    for gesto, valor, esperado in (
        ("mira-sensibilidade", "9", {"sensibilidade": 9}),
        ("mira-tremor", "25", {"zona_morta_graus_s": 25.0}),
    ):
        p = _PonteDaMira(_OK)
        _o_gesto("calibrar-sensores.html", gesto)(
            _ctx_da_aba(), {"uniq": _P1, "valor": valor}, p)
        assert p.chamadas == [{"uniq": _P1, **esperado}], (gesto, p.chamadas)
        _o_gesto("calibrar-sensores.html", gesto)(
            _ctx_da_aba(), {"uniq": _P1, "valor": valor, "tipo": "input",
                            "evento": "click"}, p)
        assert len(p.chamadas) == 1
    with pytest.raises(ValueError):
        _o_gesto("calibrar-sensores.html", "mira-tremor")(
            _ctx_da_aba(), {"uniq": _P1, "valor": "61"}, _PonteDaMira(_OK))


def test_a_calibrar_so_pinta_a_mira_quando_a_pagina_publicada_tem(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Antes de ela publicar, o produto não remonta nem pinta o bloco novo."""
    import pacotes
    from pacotes import a11_calibrar_sensores as a11

    mesa = [{"pref": "p1", "uniq": _P1, "jogador": 1, "cor": "cosmic-red",
             "nome": "Cosmic Red", "via": "USB"}]
    dele = {"uniq": _P1, "transport": "usb", "connected": True, "inputs": {},
            "mira": {"ligada": True, "sensibilidade": 9,
                     "zona_morta_graus_s": 25.0}}
    ctx = pacotes.Contexto(state={}, mesa=mesa, conectados=[dele], estados={})

    monkeypatch.setattr(a11, "_TEM_A_MIRA", False)
    carga = a11.pacote(ctx)
    assert a11.BLOCO_DAS_MIRAS not in carga["blocos"]
    assert not any(k.startswith("mira-") for k in carga["colunas"]["p1"])

    monkeypatch.setattr(a11, "_TEM_A_MIRA", True)
    carga = a11.pacote(ctx)
    html = carga["blocos"][a11.BLOCO_DAS_MIRAS]
    campos = carga["colunas"]["p1"]
    assert campos["mira-sensibilidade"] == "9"
    assert campos["mira-tremor-num"] == "25"
    for chave in campos:
        if chave.startswith("mira-"):
            assert f'data-campo="{chave}"' in html, chave
