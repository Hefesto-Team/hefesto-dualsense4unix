"""IPC-SEM-TRAVA-01: nenhuma chamada do IpcClient pode ficar presa.

O `close()` fazia `await writer.wait_closed()` sem prazo nenhum, dentro do
`finally` do `async with IpcClient.connect(...)`. Com uma escrita pendente que
o servidor nunca drena, o `wait_closed()` não retorna — e o worker que estava
executando a chamada fica preso para sempre. Como a GUI compartilha um pool de
um worker só, isso congela o IPC assíncrono da janela inteira.

Estes testes usam um writer falso cujo `wait_closed()` nunca resolve. Sem a
cura, cada teste estoura o prazo curto do próprio teste (fica VERMELHO); com a
cura, retorna. O mesmo vale para o `drain()` do caminho de envio.
"""
from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from hefesto_dualsense4unix.cli import ipc_client as mod
from hefesto_dualsense4unix.cli.ipc_client import IpcClient, IpcError

# Prazo do próprio teste: se a chamada ficar presa, o teste falha em vez de
# pendurar a suíte inteira.
PRAZO_DO_TESTE_S = 1.0


class _WriterQueNuncaFecha:
    """Writer falso: `wait_closed()` fica pendurado para sempre."""

    def __init__(self) -> None:
        self.fechou = False
        self.escrito: list[bytes] = []

    def write(self, payload: bytes) -> None:
        self.escrito.append(payload)

    async def drain(self) -> None:
        return None

    def close(self) -> None:
        self.fechou = True

    async def wait_closed(self) -> None:
        # Nunca resolve — imita a escrita pendente que o servidor não drena.
        await asyncio.Event().wait()


@pytest.mark.asyncio
async def test_close_com_wait_closed_preso_retorna_dentro_do_prazo():
    """close(timeout=...) devolve o controle mesmo com wait_closed pendurado."""
    writer = _WriterQueNuncaFecha()
    client = IpcClient(reader=AsyncMock(), writer=writer)  # type: ignore[arg-type]

    await asyncio.wait_for(client.close(timeout=0.05), timeout=PRAZO_DO_TESTE_S)

    assert writer.fechou, "close() deve ter pedido o fechamento do writer"


@pytest.mark.asyncio
async def test_close_nao_levanta_quando_o_prazo_estoura():
    """Fechar é higiene: o estouro do prazo não pode virar exceção que sobe."""
    client = IpcClient(
        reader=AsyncMock(),
        writer=_WriterQueNuncaFecha(),  # type: ignore[arg-type]
    )

    # Se levantasse, o pytest reportaria a exceção aqui.
    await asyncio.wait_for(client.close(timeout=0.05), timeout=PRAZO_DO_TESTE_S)


@pytest.mark.asyncio
async def test_close_usa_prazo_padrao_finito(monkeypatch):
    """Sem argumento, close() ainda tem prazo — o padrão do módulo."""
    monkeypatch.setattr(mod, "_CLOSE_TIMEOUT_S", 0.05)
    client = IpcClient(
        reader=AsyncMock(),
        writer=_WriterQueNuncaFecha(),  # type: ignore[arg-type]
    )

    await asyncio.wait_for(client.close(), timeout=PRAZO_DO_TESTE_S)


@pytest.mark.asyncio
async def test_saida_do_context_manager_nao_fica_presa(monkeypatch):
    """O `finally` do `async with` também tem que devolver o controle."""
    monkeypatch.setattr(mod, "_CLOSE_TIMEOUT_S", 0.05)
    writer = _WriterQueNuncaFecha()
    reader = AsyncMock()

    async def _abrir(_caminho):
        return reader, writer

    async def _bloco() -> str:
        async with IpcClient.connect(
            socket_path=Path("/tmp/hefesto-dualsense4unix-teste-sem-trava.sock"),
        ):
            pass
        return "saiu"

    with patch("asyncio.open_unix_connection", side_effect=_abrir):
        assert await asyncio.wait_for(_bloco(), timeout=PRAZO_DO_TESTE_S) == "saiu"


@pytest.mark.asyncio
async def test_close_engole_erro_do_writer():
    """Regressão: erro no fechamento continua engolido, como antes."""
    writer = MagicMock()
    writer.close = MagicMock()
    writer.wait_closed = AsyncMock(side_effect=RuntimeError("socket já morto"))

    client = IpcClient(reader=AsyncMock(), writer=writer)

    await asyncio.wait_for(client.close(timeout=0.05), timeout=PRAZO_DO_TESTE_S)


@pytest.mark.asyncio
async def test_call_com_drain_preso_vira_ipc_error():
    """O envio (drain) também tem prazo: preso, vira IpcError de timeout."""

    async def _drain_preso() -> None:
        await asyncio.Event().wait()

    writer = MagicMock()
    writer.write = MagicMock()
    writer.drain = _drain_preso
    writer.close = MagicMock()
    writer.wait_closed = AsyncMock()

    reader = AsyncMock()
    reader.readline = AsyncMock(return_value=b"")

    client = IpcClient(reader=reader, writer=writer)

    async def _chamar() -> None:
        await client.call("daemon.status", timeout=0.05)

    with pytest.raises(IpcError) as exc_info:
        await asyncio.wait_for(_chamar(), timeout=PRAZO_DO_TESTE_S)

    assert exc_info.value.code == -1
    assert "timeout" in exc_info.value.message.lower()

# "O que não se mede, não se cura." — adaptado de Lord Kelvin
