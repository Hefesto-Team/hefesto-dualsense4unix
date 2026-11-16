"""A janela do Modo imersão sem a coluna «Agora» (16/11/2026).

A-JANELA-DO-MODO-IMERSAO-SEM-A-COLUNA-AGORA-01, decisão D-1611-O-MODO-IMERSAO-TOCA-EM-TODO-JOGO.

O teto do ``mods.acao`` cobre o prazo em que a porta espera a resposta da extensão
(``PRAZO_DA_RESPOSTA_S``, lido da porta): a extensão que responde o «Testar» em 0,6 s chega à
janela, em vez de «O serviço não respondeu. Nada foi enviado.».

MORDIDA: devolver o ``mods.acao`` ao ``TETO_PADRAO_S`` (0,25 s) e a régua da extensão lenta
reprova.
"""
from __future__ import annotations

import contextlib
import json
import pathlib
import shutil
import socket
import tempfile
import threading
import time
from collections.abc import Iterator
from typing import Any

import pytest

from hefesto_dualsense4unix.app import ipc_bridge
from hefesto_dualsense4unix.cli import ipc_client
from hefesto_dualsense4unix.interface.pacotes import ponte
from hefesto_dualsense4unix.mods import porta as modulo_da_porta

VEREDITO = {"controles": [{"uniq": "aa:bb:cc:00:00:91", "nome": "Cosmic Red", "tocou": True,
                           "motivo": None}]}


@pytest.fixture
def curto() -> Iterator[pathlib.Path]:
    pasta = pathlib.Path(tempfile.mkdtemp(prefix="jm"))
    try:
        yield pasta
    finally:
        shutil.rmtree(pasta, ignore_errors=True)


class _ServicoLento:
    """O serviço de mentira: responde o ``mods.acao`` depois de ``atraso`` segundos, como a porta
    que espera a extensão responder o teste."""

    def __init__(self, caminho: pathlib.Path, atraso: float) -> None:
        self.sock = socket.socket(socket.AF_UNIX)
        self.sock.bind(str(caminho))
        self.sock.listen(4)
        self.atraso = atraso
        self.vivo = True
        self.fio = threading.Thread(target=self._atender, daemon=True)
        self.fio.start()

    def _atender(self) -> None:
        self.sock.settimeout(0.2)
        while self.vivo:
            try:
                con, _ = self.sock.accept()
            except (TimeoutError, OSError):
                continue
            with con:
                arquivo = con.makefile("rb")
                linha = arquivo.readline()
                if not linha:
                    continue
                pedido = json.loads(linha)
                time.sleep(self.atraso)
                corpo = {"enviada": True, "respondeu": True, "resposta": VEREDITO}
                resposta = {"jsonrpc": "2.0", "id": pedido["id"], "result": corpo}
                with contextlib.suppress(OSError):
                    con.sendall(json.dumps(resposta).encode() + b"\n")

    def fechar(self) -> None:
        self.vivo = False
        self.fio.join(2)
        self.sock.close()


def _com_o_servico(curto: pathlib.Path, monkeypatch: pytest.MonkeyPatch,
                   atraso: float) -> tuple[bool, str | None, Any]:
    caminho = curto / "s"
    monkeypatch.setattr(ipc_client, "ipc_socket_path", lambda: caminho)
    servico = _ServicoLento(caminho, atraso)
    try:
        return ponte.chamar_com_o_corpo("mods.acao", mod="imersao", acao="testar_golpe")
    finally:
        servico.fechar()


def test_o_teto_do_mods_acao_cobre_o_prazo_da_resposta_lido_da_porta(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """D-1611-O-MODO-IMERSAO-TOCA-EM-TODO-JOGO: o teto é o prazo da porta mais a folga, e segue
    o prazo da porta quando ele muda (o mesmo número, nunca repetido)."""
    assert ipc_bridge.teto("mods.acao") > modulo_da_porta.PRAZO_DA_RESPOSTA_S
    monkeypatch.setattr(modulo_da_porta, "PRAZO_DA_RESPOSTA_S", 3.0)
    assert ipc_bridge.teto("mods.acao") == 3.0 + ipc_bridge.FOLGA_DA_RESPOSTA_DA_EXTENSAO_S
    assert ipc_bridge.teto("mods.agora") == ipc_bridge.TETO_PADRAO_S


def test_a_extensao_que_responde_em_0_6_s_chega_a_janela(
        curto: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """D-1611-O-MODO-IMERSAO-TOCA-EM-TODO-JOGO: o «Testar» que a extensão responde em 0,6 s
    devolve o veredito, e não «O serviço não respondeu»."""
    ok, motivo, corpo = _com_o_servico(curto, monkeypatch, 0.6)
    assert ok and motivo is None
    assert corpo == {"enviada": True, "respondeu": True, "resposta": VEREDITO}
