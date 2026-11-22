"""O IPC recusa o que não serve e responde sempre: reload, resposta grande, cliente calado, JSON.

O-IPC-RECUSA-O-QUE-NAO-SERVE-E-RESPONDE-SEMPRE-01: o `daemon.reload` aceitava `rumble_active: 5`
e matava o laço; a resposta acima de 64 KiB estourava o cliente; um cliente calado segurava o
descritor para sempre; um JSON fundo ou um resultado que não serializa fechava a conexão sem
resposta. O servidor, nos casos abaixo, está num socket de pasta temporária.
"""
from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.cli.ipc_client import IpcClient, IpcError
from hefesto_dualsense4unix.daemon import ipc_handlers as ih
from hefesto_dualsense4unix.daemon import ipc_server as srv
from hefesto_dualsense4unix.daemon.ipc_server import (
    CODE_INTERNAL,
    CODE_INVALID_PARAMS,
    CODE_PARSE_ERROR,
    IpcServer,
)
from hefesto_dualsense4unix.daemon.lifecycle import Daemon, DaemonConfig
from hefesto_dualsense4unix.profiles.manager import ProfileManager
from hefesto_dualsense4unix.testing import FakeController

_OS_QUATRO = tuple(f"aabbcc00000{n}" for n in range(1, 5))


def _o_servico(tmp_path: Path, controle: FakeController | None = None) -> IpcServer:
    controle = controle or FakeController(transport="usb")
    daemon = Daemon(
        controller=controle,
        config=DaemonConfig(
            poll_hz=120, ipc_enabled=False, udp_enabled=False, autoswitch_enabled=False,
        ),
    )
    gerente = ProfileManager(controller=controle, store=daemon.store)
    servidor = IpcServer(
        controller=controle, store=daemon.store, profile_manager=gerente,
        socket_path=tmp_path / "r.sock", daemon=daemon,
    )
    daemon._ipc_server = servidor
    return servidor


async def _chamar(
    servidor: IpcServer, metodo: str, params: dict[str, Any] | None = None
) -> Any:
    async with IpcClient.connect(servidor.socket_path) as cliente:
        return await cliente.call(metodo, params or {}, timeout=10.0)


async def _erro_de(servidor: IpcServer, metodo: str, params: dict[str, Any]) -> IpcError:
    with pytest.raises(IpcError) as erro:
        await _chamar(servidor, metodo, params)
    return erro.value


@pytest.fixture
async def servico(tmp_path: Path):
    servidor = _o_servico(tmp_path)
    await servidor.start()
    try:
        yield servidor
    finally:
        await servidor.stop()


async def test_o_reload_recusa_o_valor_que_mataria_o_laco_e_a_config_fica_igual(
    tmp_path: Path,
) -> None:
    servidor = _o_servico(tmp_path)
    daemon = servidor.daemon
    await servidor.start()
    subida = asyncio.create_task(daemon.run())
    try:
        while daemon._reconnect_task is None:
            await asyncio.sleep(0.005)
        antes = daemon.config
        tiques = daemon.store.counter("poll.tick")

        erro = await _erro_de(servidor, "daemon.reload", {"config_overrides": {"rumble_active": 5}})
        await asyncio.sleep(0.4)

        assert erro.code == CODE_INVALID_PARAMS
        assert daemon.config == antes
        assert daemon.store.counter("poll.tick") > tiques + 5
    finally:
        daemon.stop()
        await asyncio.wait_for(subida, 10)
        await servidor.stop()


@pytest.mark.parametrize(
    ("campo", "valor", "frase"),
    [
        ("poll_hz", 30, "reiniciar"),
        ("udp_port", 7000, "reiniciar"),
        ("dsu_enabled", True, "reiniciar"),
        ("metrics_enabled", True, "reiniciar"),
        ("rumble_active", [5, 5], "não se muda"),
        ("gamepad_emulation_enabled", True, "não se muda"),
        ("mouse_speed", True, "inteiro"),
        ("mouse_speed", 99, "entre"),
        ("mouse_speed", "8", "inteiro"),
        ("mouse_emulation_enabled", 1, "booleano"),
        ("ps_button_action", "apagar", "um de"),
        ("ps_button_command", "steam", "lista"),
        ("rumble_policy", "tudo", "um de"),
        ("rumble_policy_custom_mult", "alto", "número"),
        ("rumble_policy_custom_mult", 99.0, "entre"),
    ],
)
async def test_o_reload_recusa_antes_do_replace_o_que_nao_serve(
    servico: IpcServer, campo: str, valor: Any, frase: str
) -> None:
    antes = servico.daemon.config

    erro = await _erro_de(servico, "daemon.reload", {"config_overrides": {campo: valor}})

    assert erro.code == CODE_INVALID_PARAMS
    assert frase in erro.message
    assert campo in erro.message
    assert servico.daemon.config == antes


async def test_o_reload_aplica_o_campo_que_vale_ao_vivo_e_o_de_antes_segue_valendo(
    servico: IpcServer,
) -> None:
    resposta = await _chamar(
        servico,
        "daemon.reload",
        {"config_overrides": {"ps_button_action": "none", "rumble_policy_custom_mult": 1}},
    )

    assert resposta["status"] == "ok"
    assert servico.daemon.config.ps_button_action == "none"
    assert servico.daemon.config.rumble_policy_custom_mult == 1.0
    assert isinstance(servico.daemon.config.rumble_policy_custom_mult, float)
    sem_nada = await _chamar(servico, "daemon.reload")
    assert sem_nada["config"]["ps_button_action"] == "none"


async def test_resposta_de_200_kb_chega_ao_cliente(servico: IpcServer) -> None:
    async def _grande(_params: dict[str, Any]) -> dict[str, Any]:
        return {"blob": "a" * 200_000}

    servico._handlers["teste.grande"] = _grande

    resposta = await _chamar(servico, "teste.grande")

    assert len(resposta["blob"]) == 200_000


async def test_resposta_acima_do_teto_do_cliente_vira_erro_com_frase(servico: IpcServer) -> None:
    async def _enorme(_params: dict[str, Any]) -> dict[str, Any]:
        return {"blob": "a" * (2 * 1024 * 1024)}

    servico._handlers["teste.enorme"] = _enorme

    with pytest.raises(IpcError) as erro:
        await _chamar(servico, "teste.enorme")

    assert "MiB" in erro.value.message


async def test_o_state_full_de_quatro_controles_e_500_pontes_cabe_no_cliente(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    class _OsQuatro(FakeController):
        def describe_controllers(self) -> list[dict[str, Any]]:
            return [
                {"index": i, "uniq": u, "transport": "usb", "connected": True}
                for i, u in enumerate(_OS_QUATRO)
            ]

    pontes = {
        f"{n:032x}": {"jogo": f"Jogo {n}", "ponte": "x" * 100} for n in range(500)
    }
    monkeypatch.setattr(ih, "_pontes_confirmadas_seguro", lambda: dict(pontes))
    servidor = _o_servico(tmp_path, _OsQuatro(transport="usb"))
    await servidor.start()
    try:
        servidor.aquecer_as_leituras()
        await asyncio.sleep(0.2)
        estado = await _chamar(servidor, "daemon.state_full")
    finally:
        await servidor.stop()

    assert len(json.dumps(estado)) > 65_536
    assert len(estado["controllers"]) == 4
    assert len(estado["pontes_confirmadas"]) == 500


async def test_duzentos_clientes_calados_sao_soltos_no_prazo_e_um_novo_e_atendido(
    servico: IpcServer, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(srv, "_TETO_DE_OCIOSIDADE_S", 0.5)
    calados = [await asyncio.open_unix_connection(str(servico.socket_path)) for _ in range(200)]
    try:
        await asyncio.sleep(0.2)
        assert len(servico._clientes) <= srv.TETO_DE_CONEXOES
        assert servico.store.counter("ipc.conexoes_recusadas") == 200 - srv.TETO_DE_CONEXOES

        inicio = time.monotonic()
        while servico._clientes and time.monotonic() - inicio < 3.0:
            await asyncio.sleep(0.05)

        assert not servico._clientes
        assert servico.store.counter("ipc.conexoes_ociosas") == srv.TETO_DE_CONEXOES
        resposta = await _chamar(servico, "controller.list")
        assert "controllers" in resposta
    finally:
        for _, escritor in calados:
            escritor.close()


async def _linha(servico: IpcServer, bruto: bytes) -> dict[str, Any]:
    leitor, escritor = await asyncio.open_unix_connection(str(servico.socket_path))
    try:
        escritor.write(bruto + b"\n")
        await escritor.drain()
        linha = await asyncio.wait_for(leitor.readline(), timeout=5.0)
        assert linha, "a conexão fechou sem resposta"
        resposta: dict[str, Any] = json.loads(linha)
        pedido = {"jsonrpc": "2.0", "id": 9, "method": "controller.list", "params": {}}
        escritor.write(json.dumps(pedido).encode() + b"\n")
        await escritor.drain()
        depois = json.loads(await asyncio.wait_for(leitor.readline(), timeout=5.0))
        assert "result" in depois
        return resposta
    finally:
        escritor.close()


async def test_o_json_de_30_mil_niveis_devolve_erro_de_parse_e_a_conexao_segue(
    servico: IpcServer,
) -> None:
    resposta = await _linha(servico, b"[" * 30_000 + b"]" * 30_000)

    assert resposta["error"]["code"] == CODE_PARSE_ERROR


async def test_o_numero_gigante_devolve_erro_de_parse_e_a_conexao_segue(
    servico: IpcServer,
) -> None:
    bruto = b'{"id": 1, "method": "x", "params": {"n": ' + b"9" * 6000 + b"}}"
    resposta = await _linha(servico, bruto)

    assert resposta["error"]["code"] == CODE_PARSE_ERROR


async def test_o_resultado_que_nao_serializa_devolve_erro_com_o_id(servico: IpcServer) -> None:
    async def _nao_serializa(_params: dict[str, Any]) -> dict[str, Any]:
        return {"objeto": object()}

    servico._handlers["teste.nao_serializa"] = _nao_serializa
    leitor, escritor = await asyncio.open_unix_connection(str(servico.socket_path))
    try:
        pedido = {"jsonrpc": "2.0", "id": 77, "method": "teste.nao_serializa", "params": {}}
        escritor.write(json.dumps(pedido).encode() + b"\n")
        await escritor.drain()
        linha = await asyncio.wait_for(leitor.readline(), timeout=5.0)
    finally:
        escritor.close()

    assert linha, "a conexão fechou sem resposta"
    resposta = json.loads(linha)
    assert resposta["id"] == 77
    assert resposta["error"]["code"] == CODE_INTERNAL
