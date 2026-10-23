"""O-SERVIDOR-DSU-DIZ-A-CONEXAO-QUE-O-CONTROLE-TEM-01: o byte 23 é a conexão do controle.

O servidor anunciava todo controle como USB. Aqui um cabo e um rádio, lado a lado, chegam ao
cliente de mentira com o byte 1 e o byte 2, na porta e nos dados, e o transporte que o backend
não conhece sai 0. Socket UDP na porta 0 (nunca a 26760, que é do daemon do usuário); o hub é
dublê; os pedidos são montados aqui com `struct` e `zlib`, sem o codec do produto.
"""

from __future__ import annotations

import contextlib
import socket
import struct
import time
import zlib
from collections.abc import Iterator
from types import SimpleNamespace
from typing import Any

import pytest

from hefesto_dualsense4unix.core import protocolo_dsu as dsu
from hefesto_dualsense4unix.daemon.sensor_hub import AmostraDoDsu
from hefesto_dualsense4unix.daemon.servidor_dsu import ServidorDsu, SlotDsu
from hefesto_dualsense4unix.daemon.state_store import StateStore
from hefesto_dualsense4unix.daemon.subsystems.dsu import montar_a_tabela

UNIQ_CABO = "aa:bb:cc:00:00:01"
UNIQ_RADIO = "aa:bb:cc:00:00:02"
UNIQ_ESTRANHO = "aa:bb:cc:00:00:03"
MAC_VIRTUAL = "02:fe:00:00:00:0"


def _pedido(tipo: int, corpo: bytes) -> bytes:
    pacote = bytearray(b"DSUC")
    pacote += struct.pack("<HHII", 1001, 4 + len(corpo), 0, 24872)
    pacote += struct.pack("<I", tipo) + corpo
    struct.pack_into("<I", pacote, 8, zlib.crc32(bytes(pacote)) & 0xFFFFFFFF)
    return bytes(pacote)


def _pede_portas(*slots: int) -> bytes:
    return _pedido(0x100001, struct.pack("<i", len(slots)) + bytes(slots))


def _pede_dados(slot: int) -> bytes:
    return _pedido(0x100002, bytes([1, slot]) + bytes(6))


class _Hub:
    def amostra_do_dsu(self, uniq: str) -> AmostraDoDsu | None:
        return None

    def segurar_o_dedo(self, uniq: str) -> None:
        return None


def _slot(uniq: str, numero: int, transporte: str | None) -> SlotDsu:
    return SlotDsu(uniq=uniq, mac=f"{MAC_VIRTUAL}{numero}", transport=transporte)


@pytest.fixture
def mundo() -> Iterator[SimpleNamespace]:
    servidor = ServidorDsu(porta=0, store=StateStore())
    tabela = {
        0: _slot(UNIQ_CABO, 1, "usb"),
        1: _slot(UNIQ_RADIO, 2, "bt"),
        2: _slot(UNIQ_ESTRANHO, 3, "serial"),
    }
    servidor.publicar(tabela, _Hub())
    servidor.iniciar()
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("127.0.0.1", 0))
    sock.settimeout(0.05)

    def envia(pacote: bytes) -> None:
        sock.sendto(pacote, ("127.0.0.1", servidor.porta))

    def recebe(segundos: float) -> list[bytes]:
        fim = time.monotonic() + segundos
        achados: list[bytes] = []
        while time.monotonic() < fim:
            with contextlib.suppress(TimeoutError):
                achados.append(sock.recvfrom(2048)[0])
        return achados

    yield SimpleNamespace(servidor=servidor, envia=envia, recebe=recebe, tabela=tabela)
    sock.close()
    servidor.parar()


# D-2310-O-DSU-DIZ-A-CONEXAO-DO-CONTROLE
def test_a_porta_diz_cabo_radio_e_desconhecido(mundo: SimpleNamespace) -> None:
    mundo.envia(_pede_portas(0, 1, 2, 3))
    respostas = mundo.recebe(0.5)
    assert [r[20] for r in respostas] == [0, 1, 2, 3]
    assert [r[23] for r in respostas] == [1, 2, 0, 0]
    assert [r[21] for r in respostas] == [2, 2, 2, 0]  # o estado segue conectado nos três


def test_os_dados_dizem_cabo_radio_e_desconhecido(mundo: SimpleNamespace) -> None:
    visto: dict[int, int] = {}
    for slot in (0, 1, 2):
        mundo.envia(_pede_dados(slot))
        pacotes = [p for p in mundo.recebe(0.3) if len(p) == 100 and p[20] == slot]
        assert pacotes, f"o slot {slot} não mandou dados"
        assert {p[23] for p in pacotes} == {pacotes[0][23]}
        visto[slot] = pacotes[0][23]
    assert visto == {0: 1, 1: 2, 2: 0}


def test_o_pacote_de_despedida_nao_inventa_usb(mundo: SimpleNamespace) -> None:
    """O slot que sai da tabela para de anunciar conexão: o último pacote sai desconectado, 0."""
    mundo.envia(_pede_dados(1))
    assert [p for p in mundo.recebe(0.3) if len(p) == 100 and p[20] == 1]
    mundo.servidor.publicar({0: mundo.tabela[0]}, _Hub())
    ultimo = [p for p in mundo.recebe(0.5) if len(p) == 100 and p[20] == 1][-1]
    assert (ultimo[21], ultimo[23]) == (0, 0)


def test_a_conversao_do_transporte_e_um_dono_so() -> None:
    assert dsu.conexao_do_transporte("usb") == dsu.CONEXAO_USB == 1
    assert dsu.conexao_do_transporte("bt") == dsu.CONEXAO_BLUETOOTH == 2
    for desconhecido in (None, "", "wifi", "USB"):
        assert dsu.conexao_do_transporte(desconhecido) == dsu.CONEXAO_NENHUMA == 0


def test_a_tabela_do_laco_leva_o_transporte_do_backend() -> None:
    """`montar_a_tabela` leva o `transport` do `describe_controllers`, de P1 a P4."""
    cabo, radio = UNIQ_CABO, UNIQ_RADIO
    radio_p3, cabo_p4 = "aa:bb:cc:00:00:04", "aa:bb:cc:00:00:05"

    class Coop:
        def player_indexes(self) -> dict[str, int]:
            return {cabo: 1, radio: 2, radio_p3: 3, cabo_p4: 4}

    daemon: Any = SimpleNamespace(
        _gamepad_device=object(),
        config=SimpleNamespace(coop_enabled=True),
        _coop_manager=Coop(),
    )
    entradas = [
        {"uniq": cabo, "connected": True, "transport": "usb", "is_primary": True},
        {"uniq": radio, "connected": True, "transport": "bt", "is_primary": False},
        {"uniq": radio_p3, "connected": True, "transport": "bt", "is_primary": False},
        {"uniq": cabo_p4, "connected": True, "transport": "usb", "is_primary": False},
    ]
    tabela = montar_a_tabela(daemon, entradas)
    assert {slot: s.transport for slot, s in tabela.items()} == {
        0: "usb",
        1: "bt",
        2: "bt",
        3: "usb",
    }
