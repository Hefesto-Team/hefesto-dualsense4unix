"""O servidor DSU nasce e morre com o daemon (E5 do servidor DSU).

O ``Daemon`` é o de verdade, com o ``_config(...)`` do molde do
``test_bt_mic_subsystem_registrado``: ``dsu_enabled=True, dsu_port=0`` e o resto
desligado. Com os padrões o ``run()`` tentaria o bind em 127.0.0.1:6969, a porta
do daemon vivo dela, e a 26760 é a porta do servidor dela: nenhum teste aqui
toca nas duas. O hub de verdade vem do ``IpcServer`` (molde de
``test_a_mira_por_movimento_na_tela``), com a fábrica de ``SensorHub`` trocada
por uma de dublês, para nenhum nó dela abrir.
"""

from __future__ import annotations

import asyncio
import inspect
import json
import socket
import struct
import zlib
from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from hefesto_dualsense4unix.core.controller import ControllerState
from hefesto_dualsense4unix.core.events import EventBus
from hefesto_dualsense4unix.daemon import main as daemon_main
from hefesto_dualsense4unix.daemon import sensor_hub as sensor_hub_module
from hefesto_dualsense4unix.daemon.ipc_server import IpcServer
from hefesto_dualsense4unix.daemon.lifecycle import Daemon, DaemonConfig
from hefesto_dualsense4unix.daemon.sensor_hub import SensorHub
from hefesto_dualsense4unix.daemon.state_store import StateStore
from hefesto_dualsense4unix.daemon.subsystems import SUBSYSTEM_REGISTRY
from hefesto_dualsense4unix.daemon.subsystems import coop as coop_module
from hefesto_dualsense4unix.daemon.subsystems.dsu import montar_a_tabela
from hefesto_dualsense4unix.integrations.uhid_gamepad import vpad_mac
from hefesto_dualsense4unix.profiles.manager import ProfileManager
from hefesto_dualsense4unix.testing import FakeController
from hefesto_dualsense4unix.utils import maquina

UNIQ = "aabbcc000001"


# -- o daemon de verdade ---------------------------------------------------------------------


def _state() -> ControllerState:
    return ControllerState(
        battery_pct=80,
        l2_raw=0,
        r2_raw=0,
        connected=True,
        transport="usb",
        buttons_pressed=frozenset(),
    )


def _config(**over: object) -> DaemonConfig:
    base: dict[str, object] = dict(
        poll_hz=200,
        auto_reconnect=False,
        ipc_enabled=False,
        udp_enabled=False,
        autoswitch_enabled=False,
        mouse_emulation_enabled=False,
        keyboard_emulation_enabled=False,
        ps_button_action="none",
        mic_button_toggles_system=False,
        dsu_enabled=True,
        dsu_port=0,
    )
    base.update(over)
    return DaemonConfig(**base)  # type: ignore[arg-type]


def _daemon(**over: object) -> Daemon:
    controle = FakeController(transport="usb", states=[_state()])
    controle.describe_controllers = lambda: [  # type: ignore[attr-defined]
        {"index": 0, "connected": True, "transport": "usb", "is_primary": True, "uniq": UNIQ}
    ]
    return Daemon(controller=controle, bus=EventBus(), store=StateStore(), config=_config(**over))


@pytest.fixture(autouse=True)
def _o_numero_do_jogo(monkeypatch: pytest.MonkeyPatch) -> None:
    """Todo controle conectado é o jogador 1 (o co-op desligado)."""
    monkeypatch.setattr(coop_module, "resolve_player_numbers", lambda d, e: [1 for _ in e])


async def _espera(condicao: Callable[[], bool], limite: float = 5.0) -> bool:
    fim = asyncio.get_running_loop().time() + limite
    while asyncio.get_running_loop().time() < fim:
        if condicao():
            return True
        await asyncio.sleep(0.01)
    return condicao()


def _pedido(tipo: int, corpo: bytes) -> bytes:
    pacote = bytearray(b"DSUC")
    pacote += struct.pack("<HHII", 1001, 4 + len(corpo), 0, 24872)
    pacote += struct.pack("<I", tipo) + corpo
    struct.pack_into("<I", pacote, 8, zlib.crc32(bytes(pacote)) & 0xFFFFFFFF)
    return bytes(pacote)


def _pergunta_sincrona(porta: int, pedido: bytes, quantas: int) -> list[bytes]:
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.settimeout(2.0)
        sock.sendto(pedido, ("127.0.0.1", porta))
        achados: list[bytes] = []
        try:
            while len(achados) < quantas:
                achados.append(sock.recvfrom(2048)[0])
        except TimeoutError:
            pass
        return achados


async def _pergunta(porta: int, pedido: bytes, quantas: int = 1) -> list[bytes]:
    return await asyncio.to_thread(_pergunta_sincrona, porta, pedido, quantas)


def _bind_livre(porta: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        try:
            sock.bind(("127.0.0.1", porta))
        except OSError:
            return False
    return True


async def _roda(daemon: Daemon) -> asyncio.Task[None]:
    tarefa = asyncio.create_task(daemon.run())
    assert await _espera(
        lambda: daemon._servidor_dsu is not None or "dsu" in daemon._failed_subsystems
    ), "o run() não chegou a subir o servidor nem a registrar a falha"
    return tarefa


# -- 1 · o run sobe, o shutdown fecha --------


@pytest.mark.asyncio
async def test_o_run_sobe_o_servidor_e_o_shutdown_fecha_a_porta() -> None:
    daemon = _daemon()
    tarefa = await _roda(daemon)
    servidor = daemon._servidor_dsu
    assert servidor is not None and "dsu" not in daemon._failed_subsystems
    porta = servidor.porta
    assert porta != 0

    versao = await _pergunta(porta, _pedido(0x100000, b""))
    assert len(versao) == 1 and struct.unpack_from("<H", versao[0], 20)[0] == 1001

    # A tabela nasce no laço do daemon: o controle 1 aparece no slot 0, com MAC de vpad.
    assert await _espera(lambda: 0 in servidor._estado[0])
    portas = await _pergunta(porta, _pedido(0x100001, struct.pack("<i", 1) + bytes([0])))
    assert tuple(portas[0][20:24]) == (0, 2, 2, 1)
    assert portas[0][24:26] == bytes([0x02, 0xFE])

    assert not _bind_livre(porta), "a porta devia estar presa pelo servidor"
    daemon.stop()
    await tarefa
    assert daemon._servidor_dsu is None and daemon._tarefa_dsu is None
    assert _bind_livre(porta), "o shutdown deixou a porta presa"


# -- 2 · desligado, nem socket --------


@pytest.mark.asyncio
async def test_dsu_desligado_nao_abre_socket(monkeypatch: pytest.MonkeyPatch) -> None:
    chamadas: list[int] = []
    monkeypatch.setattr(Daemon, "_start_dsu", lambda self: chamadas.append(1))
    daemon = _daemon(dsu_enabled=False)
    tarefa = asyncio.create_task(daemon.run())
    await _espera(lambda: daemon.store.counter("poll.tick") >= 2)
    daemon.stop()
    await tarefa
    assert chamadas == [] and daemon._servidor_dsu is None
    assert "dsu" not in daemon._failed_subsystems


# -- 3 · porta ocupada --------


@pytest.mark.asyncio
async def test_porta_ocupada_registra_a_falha_e_o_daemon_segue_de_pe() -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as dono:
        dono.bind(("127.0.0.1", 0))
        porta = dono.getsockname()[1]
        daemon = _daemon(dsu_port=porta)
        tarefa = await _roda(daemon)
        assert set(daemon._failed_subsystems) == {"dsu"}
        assert str(porta) in daemon._failed_subsystems["dsu"]
        assert daemon._servidor_dsu is None
        assert await _espera(lambda: daemon.store.counter("poll.tick") >= 2), "o daemon caiu"
        daemon.stop()
        await tarefa


# -- 4 · o hub é um só --------


@pytest.mark.asyncio
async def test_o_hub_criado_pelo_servidor_e_o_do_ipc(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    criados: list[SensorHub] = []

    def fabrica() -> SensorHub:
        hub = SensorHub(
            motion_factory=lambda uniq, node: SimpleNamespace(
                start=lambda: True, stop=lambda: None
            ),
            touch_factory=lambda uniq, node: SimpleNamespace(start=lambda: True, stop=lambda: None),
            gamepad_factory=lambda uniq, node: SimpleNamespace(
                start=lambda: True, stop=lambda: None
            ),
            descobrir_motion=dict,
            descobrir_touch=dict,
            descobrir_gamepad=dict,
            auto_manutencao=False,
        )
        hub._watch = SimpleNamespace(poll=lambda: False)
        criados.append(hub)
        return hub

    monkeypatch.setattr(sensor_hub_module, "SensorHub", fabrica)
    daemon = _daemon()
    ipc = IpcServer(
        controller=daemon.controller,
        store=daemon.store,
        profile_manager=ProfileManager(controller=daemon.controller, store=daemon.store),
        socket_path=tmp_path / "dsu.sock",
        daemon=daemon,
    )
    assert ipc._sensor_hub is None
    daemon._ipc_server = ipc

    tarefa = await _roda(daemon)
    servidor = daemon._servidor_dsu
    assert servidor is not None
    dados = _pedido(0x100002, bytes([1, 0]) + bytes(6))
    await _pergunta(servidor.porta, dados)
    assert await _espera(lambda: servidor._estado[1] is not None and ipc._sensor_hub is not None)
    assert len(criados) == 1, f"dois hubs na mesma sessão: {len(criados)}"
    assert servidor._estado[1] is ipc._sensor_hub is criados[0]
    daemon.stop()
    await tarefa


# -- 5 · a lista sobe e para o dsu --------


def test_a_lista_sobe_e_para_o_dsu() -> None:
    nomes = [p.nome for p in SUBSYSTEM_REGISTRY]
    assert nomes.index("ipc") < nomes.index("dsu"), "o dsu sobe DEPOIS do ipc"
    [passo] = [p for p in SUBSYSTEM_REGISTRY if p.nome == "dsu"]
    assert passo.partida is not None and passo.parada is not None
    assert "_start_dsu" in inspect.getsource(Daemon)
    assert "_stop_dsu" in inspect.getsource(Daemon)
    assert passo.quando is not None
    assert passo.quando(_config()) is True
    assert passo.quando(DaemonConfig()) is False


def test_o_daemon_config_nasce_com_o_dsu_desligado() -> None:
    """A suíte fica fora da porta: quem liga é o main, pelo maquina.json."""
    assert DaemonConfig().dsu_enabled is False
    assert DaemonConfig().dsu_port == 26760


# -- 6 · a tabela de slots --------


def _entrada(uniq: str, *, primario: bool = False, conectado: bool = True) -> dict[str, object]:
    return {"connected": conectado, "is_primary": primario, "uniq": uniq, "transport": "usb"}


def test_a_tabela_do_coop_desligado_poe_o_primario_no_slot_zero(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.undo()  # a função de verdade, não a do autouse
    daemon = SimpleNamespace(
        _gamepad_device=object(), config=SimpleNamespace(coop_enabled=False), _coop_manager=None
    )
    entradas = [_entrada("aabbcc000002"), _entrada("aabbcc000001", primario=True)]
    tabela = montar_a_tabela(daemon, entradas)
    assert set(tabela) == {0}
    assert tabela[0].uniq == "aabbcc000001"
    assert tabela[0].mac == vpad_mac("aabbcc000001", 1)


def test_a_tabela_do_coop_segue_os_numeros_do_jogo(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.undo()
    gerente = SimpleNamespace(player_indexes=lambda: {"aabbcc000001": 1, "aabbcc000003": 3})
    daemon = SimpleNamespace(
        _gamepad_device=object(),
        config=SimpleNamespace(coop_enabled=True),
        _coop_manager=gerente,
    )
    entradas = [
        _entrada("aabbcc000001", primario=True),
        _entrada("aabbcc000003"),
        _entrada("aabbcc000009"),  # sem número: «Controlar o PC», fica sem slot
    ]
    tabela = montar_a_tabela(daemon, entradas)
    assert {n: s.uniq for n, s in tabela.items()} == {0: "aabbcc000001", 2: "aabbcc000003"}
    assert all(s.mac.startswith("02:fe:") for s in tabela.values())


def test_a_tabela_sem_vpad_numera_na_nativa_e_esvazia_no_controlar_o_pc(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Sem vpad, o número vem do registro de identidade só na Conexão Nativa."""
    monkeypatch.undo()
    numeros = {"aabbcc000001": 1, "aabbcc000002": 2}
    pedidos: list[bool] = []

    def slot_for(uniq: str, *, assign: bool) -> int | None:
        pedidos.append(assign)
        return numeros.get(uniq)

    def daemon(nativa: bool) -> SimpleNamespace:
        return SimpleNamespace(
            _gamepad_device=None,
            is_native_mode=lambda: nativa,
            identity_registry=SimpleNamespace(slot_for=slot_for),
        )

    entradas = [_entrada("aabbcc000002"), _entrada("aabbcc000001", primario=True)]
    tabela = montar_a_tabela(daemon(True), entradas)
    assert {n: s.uniq for n, s in tabela.items()} == {0: "aabbcc000001", 1: "aabbcc000002"}
    assert tabela[1].mac == vpad_mac("aabbcc000002", 2)
    assert pedidos and not any(pedidos), "perguntar o número não pode dar lugar na fila"
    assert montar_a_tabela(daemon(False), entradas) == {}


def test_a_tabela_ignora_desconectado_sem_mac_e_numero_fora_de_faixa(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(coop_module, "resolve_player_numbers", lambda d, e: [1, 1, 5, 2])
    entradas: list[dict[str, object]] = [
        _entrada("aabbcc000001", conectado=False),
        {"connected": True, "uniq": None, "is_primary": True},
        _entrada("aabbcc000003"),
        _entrada("aabbcc000004"),
    ]
    assert set(montar_a_tabela(SimpleNamespace(), entradas)) == {1}


# -- 7 · o maquina.json --------


def _com_o_arquivo(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, documento: Any | None) -> None:
    arquivo = tmp_path / "maquina.json"
    if documento is not None:
        arquivo.write_text(
            documento if isinstance(documento, str) else json.dumps(documento), encoding="utf-8"
        )
    monkeypatch.setattr(maquina, "caminho_da_maquina", lambda: arquivo)


@pytest.mark.parametrize(
    ("documento", "ligado", "porta"),
    [
        (None, True, 26760),  # arquivo que não existe
        ("{não é json", True, 26760),
        ({}, True, 26760),
        ({"version": 1}, True, 26760),
        ({"version": 1, "orcamento": {"teto": "max"}}, True, 26760),  # o arquivo de ontem
        ({"version": 1, "servidor_dsu": None}, True, 26760),
        ({"version": 1, "servidor_dsu": "desligado"}, True, 26760),
        ({"version": 1, "servidor_dsu": {}}, True, 26760),
        ({"version": 1, "servidor_dsu": {"ligado": True}}, True, 26760),
        ({"version": 1, "servidor_dsu": {"ligado": None}}, True, 26760),
        ({"version": 1, "servidor_dsu": {"ligado": False}}, False, 26760),
        ({"version": 1, "servidor_dsu": {"ligado": False, "porta": 27001}}, False, 27001),
        ({"version": 1, "servidor_dsu": {"porta": 27002}}, True, 27002),
        ({"version": 1, "servidor_dsu": {"porta": 0}}, True, 26760),
        ({"version": 1, "servidor_dsu": {"porta": 70000}}, True, 26760),
        ({"version": 1, "servidor_dsu": {"porta": True}}, True, 26760),
        ({"version": 1, "servidor_dsu": {"porta": "27003"}}, True, 26760),
        ({"version": 2, "servidor_dsu": {"ligado": False}}, True, 26760),
    ],
)
def test_o_maquina_json_le_nao_sei_como_ligado_e_so_o_false_desliga(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    documento: Any,
    ligado: bool,
    porta: int,
) -> None:
    _com_o_arquivo(monkeypatch, tmp_path, documento)
    assert maquina.servidor_dsu_declarado() == (ligado, porta)


def test_a_chave_nova_nao_derruba_o_documento_nem_se_perde_ao_gravar(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Sem subir a ``version``: o schema ignora a chave e a gravação a devolve ao disco."""
    _com_o_arquivo(
        monkeypatch,
        tmp_path,
        {"version": 1, "servidor_dsu": {"ligado": False, "porta": 27004}},
    )
    assert maquina.carregar_maquina().orcamento.teto is None
    assert maquina.gravar_maquina({"orcamento": {"teto": "max"}})
    depois = json.loads((tmp_path / "maquina.json").read_text(encoding="utf-8"))
    assert depois["servidor_dsu"] == {"ligado": False, "porta": 27004}
    assert depois["orcamento"]["teto"] == "max" and depois["version"] == 1
    assert maquina.servidor_dsu_declarado() == (False, 27004)


# -- 8 · o main liga o config pelo maquina.json --------


@pytest.mark.parametrize(
    ("documento", "ligado", "porta"),
    [
        (None, True, 26760),
        ({"version": 1, "servidor_dsu": {"ligado": False}}, False, 26760),
        ({"version": 1, "servidor_dsu": {"porta": 27005}}, True, 27005),
    ],
)
def test_o_main_entrega_ao_daemon_o_que_o_maquina_json_diz(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    documento: Any,
    ligado: bool,
    porta: int,
) -> None:
    from hefesto_dualsense4unix.daemon.subsystems import vigia_do_laco
    from hefesto_dualsense4unix.utils import chave, migrate_legacy_paths, single_instance

    _com_o_arquivo(monkeypatch, tmp_path, documento)
    monkeypatch.setenv("HEFESTO_DUALSENSE4UNIX_NICE", "0")
    monkeypatch.setattr(chave, "motivo_do_desligamento", lambda: None)
    monkeypatch.setattr(migrate_legacy_paths, "migrate_legacy_paths", lambda: None)
    monkeypatch.setattr(single_instance, "acquire_or_takeover", lambda nome: None)
    monkeypatch.setattr(daemon_main, "build_controller", lambda: FakeController())
    vistos: list[DaemonConfig] = []

    class _DaemonDeMentira:
        def __init__(self, controller: Any, config: DaemonConfig) -> None:
            vistos.append(config)

        async def run(self) -> None:
            return None

    monkeypatch.setattr(daemon_main, "Daemon", _DaemonDeMentira)
    monkeypatch.setattr(vigia_do_laco, "vigiado", lambda coro: coro)
    assert daemon_main.run_daemon() == 0
    assert (vistos[0].dsu_enabled, vistos[0].dsu_port) == (ligado, porta)
