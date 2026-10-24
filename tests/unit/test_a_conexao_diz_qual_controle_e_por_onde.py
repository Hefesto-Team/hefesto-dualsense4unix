"""A-CONEXAO-DIZ-QUAL-CONTROLE-E-POR-ONDE-01: um evento por controle, com o `uniq` e a via dele.

A borda do primário publicava um `controller.connected` só com o transporte global (o do P1) e
um `controller.disconnected` sem `uniq`: a extensão que lê as conexões não sabia de qual controle
era. O `reconnect_loop` de verdade roda sobre um backend de mentira que diz a mesa, o transporte
de cada chave e o primário; o barramento é o de verdade.
"""
from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import pytest

import hefesto_dualsense4unix.daemon.connection as conn_mod
from hefesto_dualsense4unix.core.events import EventBus, EventTopic
from hefesto_dualsense4unix.plugin_api.context import ControllerProxy

P1, P2, P3, P4 = (f"aabbcc0000{n:02x}" for n in (0x11, 0x22, 0x33, 0x44))


class _Mesa:
    """O backend visto pelo laço: a mesa por chave, o transporte de cada uma e o primário."""

    def __init__(self, mesa: dict[str, str], do_posto: str) -> None:
        self.mesa = {f"/dev/hidraw{n}": (uniq, t) for n, (uniq, t) in enumerate(mesa.items())}
        self.primary_uniq = do_posto
        self.na_tomada = False

    def connect(self) -> None:
        return None

    def is_connected(self) -> bool:
        return self.na_tomada and bool(self.mesa)

    def alvos_conectados(self) -> dict[str, str | None]:
        return {k: u for k, (u, _) in self.mesa.items()} if self.na_tomada else {}

    def transportes_dos_alvos(self) -> dict[str, str]:
        return {k: t for k, (_, t) in self.mesa.items()} if self.na_tomada else {}

    def get_transport(self) -> str:
        return next(t for u, t in self.mesa.values() if u == self.primary_uniq)

    def em_troca_de_transporte(self, uniq: str) -> bool:
        return False


class _Daemon:
    def __init__(self, controller: Any) -> None:
        self.controller = controller
        self.bus = EventBus()
        self.voltas = 0
        self._hidraw_broker_executor = ThreadPoolExecutor(max_workers=1)

    def _is_stopping(self) -> bool:
        return self.voltas >= 3

    def _arm_input_grace(self) -> None:
        return None

    def is_native_mode(self) -> bool:
        return True

    async def _run_blocking(self, fn: Any, *args: Any) -> Any:
        return fn(*args)


def _drenar(fila: asyncio.Queue[Any]) -> list[dict[str, Any]]:
    saida = []
    while not fila.empty():
        saida.append(fila.get_nowait())
    return saida


async def _plugar_e_tirar(
    monkeypatch: pytest.MonkeyPatch, controle: _Mesa
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Volta 1: a mesa entra. Volta 2: a mesa sai inteira. Devolve (conexões, quedas)."""
    daemon = _Daemon(controle)
    entrou = daemon.bus.subscribe(EventTopic.CONTROLLER_CONNECTED)
    saiu = daemon.bus.subscribe(EventTopic.CONTROLLER_DISCONNECTED)

    async def _nada(*args: Any, **kwargs: Any) -> int:
        return 0

    for nome in ("vigiar_escritor_cru", "carimbar_o_nascimento", "vigiar_o_cabo_em_espera",
                 "reaplicar_som_em_todos_os_alvos", "reapply_speaker_after_connect",
                 "reapply_mic_after_connect"):
        if hasattr(conn_mod, nome):
            monkeypatch.setattr(conn_mod, nome, _nada)
    monkeypatch.setattr(conn_mod, "restore_last_profile", _nada)
    monkeypatch.setattr(conn_mod, "registrar_gatilho_da_lightbar", lambda d: None)
    monkeypatch.setattr(conn_mod, "armar_gatilho_da_cor", lambda d: 0)
    monkeypatch.setattr(conn_mod, "armar_gatilho_da_cor_por_numeracao", lambda d: 0)
    monkeypatch.setattr(conn_mod, "anunciar_a_chegada", lambda *a, **k: 0)

    async def _tique(daemon_: _Daemon, *resto: Any) -> bool:
        daemon_.voltas += 1
        controle.na_tomada = daemon_.voltas == 1
        return False

    monkeypatch.setattr(conn_mod, "_wait_online_or_hotplug", _tique)
    monkeypatch.setattr(conn_mod, "_wait_or_stop", _tique)

    class _WatchMudo:
        def poll(self) -> bool:
            return False

    try:
        await asyncio.wait_for(
            conn_mod.reconnect_loop(daemon, input_watch=_WatchMudo()), timeout=5.0  # type: ignore[arg-type]
        )
    finally:
        daemon._hidraw_broker_executor.shutdown(wait=False)
    return _drenar(entrou), _drenar(saiu)


#: (rótulo, a mesa {uniq: transporte}, o primário). O primário muda de lugar de propósito:
#: o transporte de cada evento é o do controle dele, nunca o do P1.
MATRIZ = [
    ("p1-usb,p2-bt,p3-usb,p4-bt", {P1: "usb", P2: "bt", P3: "usb", P4: "bt"}, P1),
    ("3-adaptadores-e-1-no-cabo,posto-no-radio", {P1: "bt", P2: "bt", P3: "bt", P4: "usb"}, P1),
    ("3-adaptadores-e-1-no-cabo,posto-no-cabo", {P1: "bt", P2: "bt", P3: "bt", P4: "usb"}, P4),
    ("todos-no-cabo", {P1: "usb", P2: "usb", P3: "usb", P4: "usb"}, P1),
    ("todos-no-radio", {P1: "bt", P2: "bt", P3: "bt", P4: "bt"}, P1),
    ("um-so", {P1: "usb"}, P1),
]


@pytest.mark.asyncio
@pytest.mark.parametrize(("rotulo", "mesa", "do_posto"), MATRIZ, ids=[m[0] for m in MATRIZ])
async def test_um_controller_connected_por_controle_com_o_transporte_dele(
    monkeypatch: pytest.MonkeyPatch, rotulo: str, mesa: dict[str, str], do_posto: str
) -> None:
    conexoes, _ = await _plugar_e_tirar(monkeypatch, _Mesa(mesa, do_posto))
    assert all(c.get("uniq") for c in conexoes), f"{rotulo}: evento sem `uniq`: {conexoes}"
    assert len(conexoes) == len(mesa), f"{rotulo}: um evento por controle, veio {conexoes}"
    assert {c["uniq"]: c["transport"] for c in conexoes} == mesa, rotulo


@pytest.mark.asyncio
@pytest.mark.parametrize(("rotulo", "mesa", "do_posto"), MATRIZ, ids=[m[0] for m in MATRIZ])
async def test_cada_queda_diz_o_uniq_de_quem_saiu(
    monkeypatch: pytest.MonkeyPatch, rotulo: str, mesa: dict[str, str], do_posto: str
) -> None:
    _, quedas = await _plugar_e_tirar(monkeypatch, _Mesa(mesa, do_posto))
    assert sorted(q.get("uniq") or "" for q in quedas) == sorted(mesa), f"{rotulo}: {quedas}"
    assert {q["reason"] for q in quedas} == {"probe_offline"}


def test_backend_sem_mesa_por_alvo_publica_um_so_com_o_primario() -> None:
    """O backend que não enumera alvos (o de um controle só) segue com UM evento, o do primário."""
    controle = type("_Um", (), {"primary_uniq": P1, "get_transport": lambda self: "bt"})()
    daemon = _Daemon(controle)
    entrou = daemon.bus.subscribe(EventTopic.CONTROLLER_CONNECTED)
    saiu = daemon.bus.subscribe(EventTopic.CONTROLLER_DISCONNECTED)
    conn_mod.publicar_a_borda_do_primario(daemon, {}, None)  # type: ignore[arg-type]
    conn_mod.publicar_a_queda_de_cada_alvo(daemon, {}, None, "probe_offline")  # type: ignore[arg-type]
    assert _drenar(entrou) == [{"transport": "bt", "uniq": P1}]
    assert _drenar(saiu) == [{"reason": "probe_offline", "uniq": P1}]
    daemon._hidraw_broker_executor.shutdown(wait=False)


def test_a_borda_do_boot_publica_um_por_controle() -> None:
    """O boot (`lifecycle`) usa a mesma borda: a mesa já de pé ganha um evento por controle."""
    controle = _Mesa({P1: "usb", P2: "bt"}, P1)
    controle.na_tomada = True
    daemon = _Daemon(controle)
    entrou = daemon.bus.subscribe(EventTopic.CONTROLLER_CONNECTED)
    conn_mod.publicar_a_borda_do_primario(daemon, {}, None)  # type: ignore[arg-type]
    assert _drenar(entrou) == [{"transport": "usb", "uniq": P1}, {"transport": "bt", "uniq": P2}]
    daemon._hidraw_broker_executor.shutdown(wait=False)


@pytest.mark.parametrize("do_posto", [P1, P4])
def test_a_api_de_plugin_diz_o_transporte_de_cada_controle(do_posto: str) -> None:
    controle = _Mesa({P1: "bt", P2: "bt", P3: "bt", P4: "usb"}, do_posto)
    controle.na_tomada = True
    proxy = ControllerProxy(controle)  # type: ignore[arg-type]
    assert proxy.transport == ("usb" if do_posto == P4 else "bt"), "o nome velho é o do primário"
    assert {u: proxy.transporte_de(u) for u in (P1, P2, P3, P4)} == {
        P1: "bt", P2: "bt", P3: "bt", P4: "usb"}
    assert proxy.transporte_de("aabbcc0000ff") is None
