"""O-CIRCULO-DO-ANALOGICO-MOSTRA-O-QUE-O-JOGO-VE-01 — o anel é o que o jogo recebe.

Com a Inclinação ou a Mira num analógico, o jogo segura outra coisa que a mão, e o
círculo do cartão pintava só a mão. O pad guarda o último envio (`eixos_no_jogo`), o
`state_full` o publica por controle (`no_jogo`) e o cartão acende um anel onde a rota
aponta. A testemunha do jogo é o que o NÓ recebeu (o `ABS_X` escrito no uinput, o byte
do report do uhid), e a da tela é o número escrito nesta régua.

As mordidas de cada régua estão na docstring dela.
"""

from __future__ import annotations

import asyncio
import json
import os
import pathlib
import sys
import types
from collections.abc import Iterator
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from hefesto_dualsense4unix.core import roteador_de_movimento as rot
from hefesto_dualsense4unix.core.controller import ControllerState
from hefesto_dualsense4unix.core.virtual_motion import REGISTRO
from hefesto_dualsense4unix.daemon.ipc_server import IpcServer
from hefesto_dualsense4unix.daemon.lifecycle import Daemon
from hefesto_dualsense4unix.daemon.sensor_hub import SensorHub
from hefesto_dualsense4unix.daemon.subsystems import gamepad as gp
from hefesto_dualsense4unix.integrations import uhid_gamepad
from hefesto_dualsense4unix.integrations.virtual_pad import CAMINHO_XBOX, make_virtual_pad
from hefesto_dualsense4unix.profiles.manager import ProfileManager
from hefesto_dualsense4unix.profiles.schema import MatchAny, Profile, ProfileMovimentoConfig
from hefesto_dualsense4unix.testing import FakeController

# As receitas do pad que grava (o `evdev` sem kernel) são as da régua do modo Xbox.
from tests.unit.test_no_modo_xbox_o_toque_e_o_acelerometro import (
    _DEITADO,
    _EC,
    _AbsInfo,
    _hub,
    _inclinado,
    _NoGravado,
)

RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src/hefesto_dualsense4unix/interface"))

_P1, _P2, _P3, _P4 = (
    "aa:bb:cc:00:00:01",
    "aa:bb:cc:00:00:02",
    "aa:bb:cc:00:00:03",
    "aa:bb:cc:00:00:04",
)


@pytest.fixture
def _evdev_que_grava(monkeypatch: pytest.MonkeyPatch) -> None:
    """O `evdev` sem kernel da régua do modo Xbox: o pad escreve num `_NoGravado`."""
    from hefesto_dualsense4unix.daemon.subsystems.external_mask import (
        _zerar_registro_de_mascaras,
    )

    _zerar_registro_de_mascaras()
    _NoGravado.criados = []
    mod = types.ModuleType("evdev")
    mod.UInput = _NoGravado  # type: ignore[attr-defined]
    mod.AbsInfo = _AbsInfo  # type: ignore[attr-defined]
    mod.ecodes = _EC  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "evdev", mod)
    monkeypatch.setattr(uhid_gamepad, "uhid_available", lambda: False)


@pytest.fixture(autouse=True)
def _registro_limpo() -> Iterator[None]:
    REGISTRO.limpar()
    yield
    REGISTRO.limpar()


class _NaMao:
    """O leitor de movimento de um controle SEGURO: o giro treme como a mão.

    Com a regra do controle parado (D-2909-O-CONTROLE-PARADO-NAO-INCLINA) na
    árvore, um giro em zero seria a mesa, e a régua mediria o neutro, não o anel.
    """

    def __init__(self, acel: tuple[float, float, float] = _DEITADO,
                 giro: tuple[float, float, float] | None = None) -> None:
        self.acel = acel
        self.giro = giro
        self._lado = 1.0

    def start(self) -> bool:
        return True

    def stop(self) -> None:
        pass

    def snapshot(self) -> Any:
        if self.giro is not None:
            return SimpleNamespace(x=self.giro[0], y=self.giro[1], z=self.giro[2])
        self._lado = -self._lado
        return SimpleNamespace(x=self._lado, y=0.5 * self._lado, z=0.0)

    def consume_angulo(self) -> tuple[float, float, float]:
        return (0.0, 0.0, 0.0)

    def accel_snapshot(self) -> Any:
        return SimpleNamespace(x=self.acel[0], y=self.acel[1], z=self.acel[2])


def _estado() -> ControllerState:
    return ControllerState(
        battery_pct=100, l2_raw=0, r2_raw=0, connected=True, transport="bt"  # type: ignore[arg-type]
    )


def _mesa(tmp_path: Path, hub: SensorHub, movimento: ProfileMovimentoConfig,
          monkeypatch: pytest.MonkeyPatch) -> tuple[Daemon, IpcServer]:
    """O `Daemon` e o `IpcServer` do produto, com o P1 primário na lista do `state_full`."""
    controle = FakeController(transport="bt")
    controle.primary_uniq = _P1  # type: ignore[attr-defined]
    controle.describe_controllers = lambda: [  # type: ignore[attr-defined]
        {"index": 0, "connected": True, "transport": "bt", "is_primary": True,
         "uniq": _P1},
    ]
    daemon = Daemon(controller=controle)
    gerente = ProfileManager(controller=controle, store=daemon.store)
    servidor = IpcServer(
        controller=controle, store=daemon.store, profile_manager=gerente,
        socket_path=tmp_path / "circulo.sock", daemon=daemon,
    )
    servidor._sensor_hub = hub
    daemon._ipc_server = servidor
    gerente.apply_movimento(Profile(name="Anel", match=MatchAny(type="any"),
                                    movimento=movimento))
    daemon._last_state = _estado()  # type: ignore[attr-defined]
    monkeypatch.setattr(gp, "_reconciliar_launch", lambda d: None)
    monkeypatch.setattr(gp, "_avisar_troca_de_modo", lambda d: None)
    return daemon, servidor


def _tiques(daemon: Daemon, hub: SensorHub, n: int = 2) -> None:
    gp.dispatch_gamepad(daemon, _estado(), frozenset())
    hub.reconciliar()
    for _ in range(n):
        gp.dispatch_gamepad(daemon, _estado(), frozenset())


def _o_p1(servidor: IpcServer) -> dict[str, Any]:
    corpo = asyncio.run(servidor._handle_daemon_state_full({}))
    (p1,) = [c for c in corpo["controllers"] if c.get("uniq") == _P1]
    return p1


# 1, 4. O P1 no modo Xbox: o `state_full` diz o que o nó recebeu


def test_1_o_p1_inclina_e_o_state_full_diz_o_que_o_no_recebeu(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, _evdev_que_grava: None
) -> None:
    """MORDIDAS: o `_merge_no_jogo` copiar o `inputs` → `lx == 128` e reprova no `==`;
    a propriedade devolver `None` sempre → reprova também."""
    movimento = _NaMao(_DEITADO)
    hub = _hub({_P1: movimento}, {})  # type: ignore[dict-item]
    daemon, servidor = _mesa(
        tmp_path, hub, ProfileMovimentoConfig(acelerometro="analogico_esquerdo"), monkeypatch)
    pad = make_virtual_pad("dualsense", identity=_P1, caminho=CAMINHO_XBOX)
    assert pad is not None
    no = pad._device  # type: ignore[attr-defined]
    assert isinstance(no, _NoGravado)
    daemon._gamepad_device = pad
    try:
        _tiques(daemon, hub)
        movimento.acel = _inclinado(0.0, 25.0)
        gp.dispatch_gamepad(daemon, _estado(), frozenset())
        p1 = _o_p1(servidor)
        no_x = no.ultimo(_EC.EV_ABS, _EC.ABS_X)
        assert no_x is not None and no_x > 128, f"premissa: a inclinação não chegou ao nó ({no_x})"
        assert p1["inputs"]["lx"] == 128, p1["inputs"]
        assert p1["no_jogo"] is not None, "o state_full não disse o que o jogo recebe"
        assert p1["no_jogo"]["lx"] == no_x, (p1["no_jogo"], no_x)
        assert p1["no_jogo"]["lx"] > 128
    finally:
        pad.stop()


def test_4_a_mira_no_direito_move_o_rx_do_jogo(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, _evdev_que_grava: None
) -> None:
    """O giro com a Mira no analógico direito move `no_jogo.rx`, e `inputs.rx` fica.

    MORDIDA: a mesma da régua 1 (o `inputs` copiado no `no_jogo`).
    """
    movimento = _NaMao(_DEITADO, giro=(0.0, 150.0, 0.0))
    hub = _hub({_P1: movimento}, {})  # type: ignore[dict-item]
    daemon, servidor = _mesa(
        tmp_path, hub, ProfileMovimentoConfig(destino="analogico_direito", sensibilidade=12),
        monkeypatch)
    pad = make_virtual_pad("dualsense", identity=_P1, caminho=CAMINHO_XBOX)
    assert pad is not None
    no = pad._device  # type: ignore[attr-defined]
    daemon._gamepad_device = pad
    try:
        _tiques(daemon, hub)
        p1 = _o_p1(servidor)
        no_rx = no.ultimo(_EC.EV_ABS, _EC.ABS_RX)
        assert no_rx is not None and no_rx != 128, f"premissa: a Mira não chegou ao nó ({no_rx})"
        assert p1["inputs"]["rx"] == 128
        assert p1["no_jogo"]["rx"] == no_rx, (p1["no_jogo"], no_rx)
    finally:
        pad.stop()


# 2. O mesmo no uhid (modo DualSense)

_BYTE_DO_LX = 1  # o report 0x01: o id, e o corpo começa no lx


@pytest.fixture
def _uhid() -> Iterator[tuple[Any, list[bytes]]]:
    """O `UhidDualSense` de verdade com o fd no `/dev/null` e os reports gravados."""
    pad = uhid_gamepad.UhidDualSense(player=1, blueprint=None)
    pad._fd = os.open(os.devnull, os.O_WRONLY)
    reports: list[bytes] = []
    enviar = pad.send_report

    def _gravar(report: bytes) -> bool:
        reports.append(bytes(report))
        return enviar(report)

    pad.send_report = _gravar  # type: ignore[method-assign]
    try:
        yield pad, reports
    finally:
        fd, pad._fd = pad._fd, None
        if fd is not None:
            os.close(fd)


def test_2_o_uhid_diz_o_byte_do_report(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, _uhid: tuple[Any, list[bytes]]
) -> None:
    """MORDIDA: a propriedade do uhid ler o `_AXES_NEUTRAL` → reprova no `==`."""
    pad, reports = _uhid
    movimento = _NaMao(_DEITADO)
    hub = _hub({_P1: movimento}, {})  # type: ignore[dict-item]
    daemon, servidor = _mesa(
        tmp_path, hub, ProfileMovimentoConfig(acelerometro="analogico_esquerdo"), monkeypatch)
    daemon._gamepad_device = pad
    _tiques(daemon, hub)
    movimento.acel = _inclinado(0.0, 25.0)
    gp.dispatch_gamepad(daemon, _estado(), frozenset())
    assert reports, "premissa: o uhid não emitiu report"
    lx_do_report = reports[-1][_BYTE_DO_LX]
    assert lx_do_report > 128, f"premissa: a inclinação não chegou ao report ({lx_do_report})"
    p1 = _o_p1(servidor)
    assert p1["no_jogo"]["lx"] == lx_do_report, (p1["no_jogo"], lx_do_report)
    assert p1["inputs"]["lx"] == 128


# 3, 5. Os jogadores 2 a 4, cada um o seu; e quem não tem pad diz `None`


def _o_coop(monkeypatch: pytest.MonkeyPatch, acel: dict[str, tuple[float, float, float]],
            cedidos: frozenset[str] = frozenset()) -> tuple[IpcServer, dict[str, Any]]:
    """O `forward_all` de verdade com PADS de verdade (uinput sobre o evdev que grava)."""
    from hefesto_dualsense4unix.daemon.subsystems import coop as co
    from hefesto_dualsense4unix.daemon.subsystems.coop import CoopManager, _SecondaryPlayer

    class _Leitor:
        grab_state = "held"

        def snapshot(self) -> Any:
            return SimpleNamespace(buttons_pressed=frozenset(), l2_raw=0, r2_raw=0,
                                   lx=128, ly=128, rx=128, ry=128)

    class _HubDaInclinacao:
        def aceleracao_do_movimento(self, uniq: str) -> Any:
            return acel[uniq]

    monkeypatch.setattr(
        REGISTRO, "estado",
        lambda uniq: SimpleNamespace(giroscopio=True, acelerometro=uniq != _P3),
    )
    neutros: dict[str, Any] = {}
    monkeypatch.setattr(
        rot, "neutro_da_inclinacao",
        lambda dono, uniq, a, agora, **_: neutros.setdefault(uniq, _DEITADO),
    )
    store = SimpleNamespace(udp_trigger_thresholds=(0, 0))
    rot.definir_ativo(store, rot.montar(ProfileMovimentoConfig(acelerometro="analogico_esquerdo")))
    hub = _HubDaInclinacao()
    daemon = SimpleNamespace(
        _ipc_server=SimpleNamespace(_garantir_sensor_hub=lambda: hub), store=store,
        _mouse_device=None, _gamepad_device=None,
    )
    from types import MethodType

    daemon._garantir_sensor_hub = MethodType(Daemon._garantir_sensor_hub, daemon)
    gerente = CoopManager.__new__(CoopManager)
    gerente._daemon = daemon  # type: ignore[attr-defined]
    gerente._players = {}  # type: ignore[attr-defined]
    monkeypatch.setattr(co.CoopManager, "_recolher_os_cedidos", lambda self: None)
    monkeypatch.setattr(co.CoopManager, "_promote_pending", lambda self: None)
    pads: dict[str, Any] = {}
    for n, uniq in enumerate((_P2, _P3, _P4), start=2):
        pad = make_virtual_pad("dualsense", identity=uniq, caminho=CAMINHO_XBOX, player=n)
        assert pad is not None
        pads[uniq] = pad
        gerente._players[uniq] = _SecondaryPlayer(  # type: ignore[attr-defined]
            identity=uniq, evdev_path=f"/dev/input/event{n}", reader=_Leitor(),  # type: ignore[arg-type]
            player_index=n, vpad=pad,
        )
    gerente.forward_all()
    # o cedido mandou antes de ceder: o pad dele guarda um valor que já não vale
    for uniq in cedidos:
        gerente._players[uniq].cedido_ao_primario = True  # type: ignore[attr-defined]
    daemon._coop_manager = gerente
    servidor = IpcServer.__new__(IpcServer)
    servidor.daemon = daemon  # type: ignore[assignment]
    return servidor, pads


def _entradas() -> list[dict[str, Any]]:
    return [{"uniq": u, "is_primary": False} for u in (_P2, _P3, _P4)]


def test_3_os_jogadores_2_a_4_cada_um_o_seu(
    monkeypatch: pytest.MonkeyPatch, _evdev_que_grava: None
) -> None:
    """MORDIDA: publicar o pad do primário (ou um só) em toda entrada → reprova no P3 e no P4."""
    servidor, pads = _o_coop(
        monkeypatch, {_P2: _inclinado(0.0, 25.0), _P3: _inclinado(0.0, 25.0), _P4: _DEITADO})
    try:
        entradas = _entradas()
        servidor._merge_no_jogo(entradas)
        lido = {e["uniq"]: e["no_jogo"] for e in entradas}
        for uniq, pad in pads.items():
            no_x = pad._device.ultimo(_EC.EV_ABS, _EC.ABS_X)
            assert lido[uniq] is not None and lido[uniq]["lx"] == no_x, (uniq, lido[uniq], no_x)
        assert lido[_P2]["lx"] > 128, "o P2 inclinou e o jogo não recebeu"
        assert lido[_P3]["lx"] == 128, "o P3 tem o acelerômetro desligado e andou"
        assert lido[_P4]["lx"] == 128, "o P4 estava deitado e andou"
    finally:
        for pad in pads.values():
            pad.stop()


def test_5_quem_nao_tem_pad_diz_none(
    monkeypatch: pytest.MonkeyPatch, _evdev_que_grava: None
) -> None:
    """O cedido ao primário, o pendente, o primário sem pad e o pad parado: `None`.

    MORDIDAS: tirar o teste do `cedido_ao_primario` publica o último valor de antes;
    tirar o `_fd is None` do uhid devolve o `_AXES_NEUTRAL` do pad parado.
    """
    servidor, pads = _o_coop(
        monkeypatch, {_P2: _inclinado(0.0, 25.0), _P3: _DEITADO, _P4: _DEITADO},
        cedidos=frozenset({_P2}))
    try:
        servidor.daemon._coop_manager._players[_P4].vpad = None  # o pendente de grab
        entradas = [*_entradas(), {"uniq": _P1, "is_primary": True}]
        servidor._merge_no_jogo(entradas)
        lido = {e["uniq"]: e["no_jogo"] for e in entradas}
        assert pads[_P2].eixos_no_jogo[0] > 128, "premissa: o P2 mandou antes de ceder"
        assert lido[_P2] is None, "o cedido ao primário publicou o último valor de antes"
        assert lido[_P3] is not None, "premissa: o P3 tem pad e mandou"
        assert lido[_P4] is None, "o pendente sem pad disse um valor"
        assert lido[_P1] is None, "o primário sem pad (o Nativo, a Navegação) disse um valor"
    finally:
        for pad in pads.values():
            pad.stop()
    for pad in pads.values():
        assert pad.eixos_no_jogo is None, "o uinput parado ainda diz eixos"


def test_5b_o_uhid_parado_diz_none(_uhid: tuple[Any, list[bytes]]) -> None:
    """MORDIDA: tirar o `_fd is None` → o `_AXES_NEUTRAL` do pad parado sai como valor."""
    pad, _reports = _uhid
    pad.forward_analog(lx=200, ly=128, rx=128, ry=128, l2=0, r2=0)
    assert pad.eixos_no_jogo == (200, 128, 128, 128)
    pad.stop()
    assert pad.eixos_no_jogo is None


# 6. O cartão pinta o jogo, e só onde a rota aponta

UNIQ = _P1
MESA = [{"uniq": UNIQ, "pref": "p1", "nome": "White", "via": "USB", "cor": "white"}]
NO_GAMEPAD = {"gamepad_emulation": {"enabled": True}}


@pytest.fixture(scope="module")
def a02() -> Any:
    from pacotes import a02_controles

    return a02_controles


def _anel(a02: Any, monkeypatch: pytest.MonkeyPatch, mira: dict[str, Any],
          estado: dict[str, Any] | None = None, no_jogo: Any = "de_nascenca") -> dict[str, str]:
    import pacotes

    campos = {*a02.CAMPOS_DO_JOGO.values(), *a02.ACENDE_O_JOGO.values()}
    monkeypatch.setattr(a02, "_ENDERECOS", frozenset(campos), raising=False)
    entrada = {
        "uniq": UNIQ, "player": 1, "connected": True, "transport": "usb",
        "battery_pct": 95, "is_primary": True, "audio": {},
        "inputs": {"lx": 128, "ly": 128, "rx": 128, "ry": 128},
        "no_jogo": ({"lx": 200, "ly": 128, "rx": 64, "ry": 128}
                    if no_jogo == "de_nascenca" else no_jogo),
        "mira": mira,
    }
    ctx = pacotes.Contexto(state=estado if estado is not None else NO_GAMEPAD,
                           mesa=MESA, conectados=[entrada], estados={})
    card = a02.pacote(ctx)["cards"][UNIQ]
    return {campo: card[campo] for campo in campos}


def test_6_a_inclinacao_no_esquerdo_acende_o_esquerdo(a02: Any, monkeypatch: pytest.MonkeyPatch,
                                                      ) -> None:
    """MORDIDAS: `posicoes_do_jogo` ler o `inputs` → o anel cai na mão (50.2) e reprova;
    acender sempre que há `no_jogo` → o `ana-d-jogo` acende e reprova."""
    anel = _anel(a02, monkeypatch, {"ligada": False, "destino": "nenhum",
                                    "inclinacao": "analogico_esquerdo"})
    assert anel["pos-ana-e-jogo"] == f"{round(200 / 255 * 100, 1)},{round(128 / 255 * 100, 1)}"
    assert anel["ana-e-jogo"] == "sim"
    assert anel["ana-d-jogo"] == "" and anel["pos-ana-d-jogo"] == ""


def test_6_a_mira_no_direito_acende_o_direito(a02: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    anel = _anel(a02, monkeypatch, {"ligada": True, "destino": "analogico_direito",
                                    "inclinacao": "nenhum"})
    assert anel["pos-ana-d-jogo"] == f"{round(64 / 255 * 100, 1)},{round(128 / 255 * 100, 1)}"
    assert anel["ana-d-jogo"] == "sim" and anel["ana-e-jogo"] == ""


def test_6_a_mira_no_cursor_nao_acende(a02: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    """MORDIDA: acender pelo `mira.ligada` sem olhar o destino → o «mouse» acende e reprova."""
    anel = _anel(a02, monkeypatch, {"ligada": True, "destino": "mouse",
                                    "inclinacao": "nenhum"})
    assert anel["ana-e-jogo"] == "" and anel["ana-d-jogo"] == "", anel


def test_6_a_mira_desligada_com_destino_nao_acende(a02: Any,
                                                    monkeypatch: pytest.MonkeyPatch) -> None:
    anel = _anel(a02, monkeypatch, {"ligada": False, "destino": "analogico_direito",
                                    "inclinacao": "nenhum"})
    assert anel["ana-d-jogo"] == "", anel


@pytest.mark.parametrize("caso", ["nativo", "navegacao", "sem_no_jogo"])
def test_6_sem_pad_nada_acende(a02: Any, monkeypatch: pytest.MonkeyPatch, caso: str) -> None:
    mira = {"ligada": True, "destino": "analogico_direito", "inclinacao": "analogico_esquerdo"}
    estado = {"nativo": {"native_mode": True},
              "navegacao": {"gamepad_emulation": {"enabled": False}, "connected": True},
              "sem_no_jogo": NO_GAMEPAD}[caso]
    anel = _anel(a02, monkeypatch, mira, estado,
                 no_jogo=None if caso == "sem_no_jogo" else "de_nascenca")
    assert anel == {"pos-ana-e-jogo": "", "pos-ana-d-jogo": "",
                    "ana-e-jogo": "", "ana-d-jogo": ""}, (caso, anel)


def test_6_sem_o_endereco_na_pagina_o_pacote_cala(a02: Any,
                                                    monkeypatch: pytest.MonkeyPatch) -> None:
    """Até o `--publicar 02`, a página não tem o anel e o pacote não emite para ele."""
    import pacotes

    monkeypatch.setattr(a02, "_ENDERECOS", frozenset(), raising=False)
    ctx = pacotes.Contexto(state=NO_GAMEPAD, mesa=MESA, conectados=[{
        "uniq": UNIQ, "is_primary": True, "connected": True, "inputs": {},
        "no_jogo": {"lx": 200, "ly": 128, "rx": 128, "ry": 128},
        "mira": {"inclinacao": "analogico_esquerdo"}}], estados={})
    card = a02.pacote(ctx)["cards"][UNIQ]
    assert not ({*a02.CAMPOS_DO_JOGO.values(), *a02.ACENDE_O_JOGO.values()} & set(card))


# 7. O gerador

@pytest.fixture(scope="module")
def pagina() -> str:
    from hefesto_dualsense4unix.interface import onde

    return onde.pagina("02-controles.html").read_text(encoding="utf-8")


def test_7_o_anel_mora_nos_quatro_lugares_e_o_exemplo_so_no_p1(a02: Any, pagina: str) -> None:
    """MORDIDA: apagar o anel de um lugar → o `exigir` do gerador e esta régua reprovam."""
    for alvo, campo in a02.CAMPOS_DO_JOGO.items():
        assert pagina.count(f'data-campo="{campo}" data-hef-alvo="posicao"') == 4, campo
        assert pagina.count(f'data-campo="{a02.ACENDE_O_JOGO[alvo]}" data-hef-alvo="classe" '
                            f'title="{a02.DICA_DO_PONTO_DO_JOGO}"') == 4, alvo
    assert pagina.count(a02.REGRA_DAS_POSICOES) == 1
    assert ".ctl .stick .pj" in a02.REGRA_DAS_POSICOES
    cravado = 'data-campo="pos-ana-e-jogo" data-hef-alvo="posicao" style="--hef-x:'
    assert pagina.count(cravado) == 1
    assert pagina.count('class="pj on"') == 1
    assert 'data-campo="pos-ana-d-jogo" data-hef-alvo="posicao" style=' not in pagina


# 8. A página no WebKit (roda no `xvfb-run`; sem display, pula)

_MEDIR = r"""
(function(){
  const p1 = document.querySelector('[data-controle="p1"]');
  const medir = (campo) => {
    const anel = p1.querySelector('[data-campo="' + campo + '"]');
    const roda = anel.closest('.stick');
    const r = anel.getBoundingClientRect(), s = roda.getBoundingClientRect();
    const dentro = s.left + roda.clientLeft, topo = s.top + roda.clientTop;
    return {x: (r.left + r.width / 2 - dentro) / roda.clientWidth * 100,
            y: (r.top + r.height / 2 - topo) / roda.clientHeight * 100,
            w: r.width, op: getComputedStyle(anel).opacity};
  };
  const antes = medir('ana-d-jogo');
  const casca = p1.querySelector('[data-campo="pos-ana-d-jogo"]');
  casca.style.setProperty('--hef-x', '78.4%');
  casca.style.setProperty('--hef-y', '23.5%');
  p1.querySelector('[data-campo="ana-d-jogo"]').classList.add('on');
  return JSON.stringify({exemplo: medir('ana-e-jogo'), antes: antes,
                         depois: medir('ana-d-jogo')});
})()
"""


def _no_webkit(roteiro: str) -> dict[str, Any]:
    gi = pytest.importorskip("gi", reason="a GUI precisa do PyGObject do sistema")
    gi.require_version("Gtk", "3.0")
    gi.require_version("WebKit2", "4.1")
    from gi.repository import GLib, Gtk, WebKit2

    if not Gtk.init_check(None)[0]:
        pytest.skip("sem sessão gráfica — o WebKit não abre")
    from hefesto_dualsense4unix.interface import onde

    saiu: list[str] = []
    janela = Gtk.OffscreenWindow()
    janela.set_default_size(1280, 900)
    view = WebKit2.WebView()
    janela.add(view)
    janela.show_all()

    def guardou(v: Any, res: Any) -> None:
        try:
            saiu.append(v.evaluate_javascript_finish(res).to_string())
        except Exception as e:  # pragma: no cover — só quando o roteiro quebra
            saiu.append(f"ERRO {e}")
        Gtk.main_quit()

    def carregou(v: Any, evento: Any) -> None:
        if evento == WebKit2.LoadEvent.FINISHED:
            GLib.timeout_add(300, lambda: v.evaluate_javascript(
                roteiro, -1, None, None, None, guardou) and False)

    view.connect("load-changed", carregou)
    view.load_uri(onde.pagina("02-controles.html").as_uri())
    guarda = GLib.timeout_add(30000, Gtk.main_quit)
    try:
        Gtk.main()
    finally:
        GLib.source_remove(guarda)
        janela.destroy()
    assert saiu and not saiu[0].startswith("ERRO"), saiu
    return dict(json.loads(saiu[0]))


def test_8_o_anel_cai_onde_o_numero_diz_no_webkit() -> None:
    """MORDIDA: tirar `.ctl .stick .pj` da regra única → o anel não lê `--hef-x` e reprova."""
    lido = _no_webkit(_MEDIR)
    exemplo, antes, depois = lido["exemplo"], lido["antes"], lido["depois"]
    assert exemplo["x"] == pytest.approx(43.1, abs=0.6), exemplo
    assert exemplo["y"] == pytest.approx(78.4, abs=0.6), exemplo
    assert exemplo["op"] == "1" and exemplo["w"] == pytest.approx(13, abs=0.5), exemplo
    assert antes["op"] == "0", f"o anel apagado aparece: {antes}"
    assert depois["x"] == pytest.approx(78.4, abs=0.6), depois
    assert depois["y"] == pytest.approx(23.5, abs=0.6), depois
    assert depois["op"] == "1", depois
