"""O pacote DSU (cemuhook) que o emulador aceita, montado e lido sem I/O.

Só bytes: nada aqui abre socket, lê relógio ou fala com o hub. O servidor
(`daemon/servidor_dsu.py`) escolhe QUANDO mandar; este módulo sabe COMO é cada
pacote. O formato, com a fonte de cada fato, está em
`docs/protocol/o-protocolo-dsu.md`.

Dois lados:

- ``interpretar_pedido`` lê o que o emulador manda (``DSUC``). Pedido malformado
  devolve ``None``, nunca levanta: a porta está aberta a qualquer processo local.
- ``montar_*`` monta o que o servidor responde (``DSUS``). Valor fora do campo
  levanta ``ValueError`` com o nome do campo (e nunca ``struct.error``), porque
  quem chama é código nosso e o erro tem de dizer qual contador estourou.

``validar_saida`` é o inverso de cada ``montar_*``: os testes o usam para recusar
um pacote que o Azahar recusaria. O ensaio do emulador tem o leitor dele, sem
import do produto.
"""

from __future__ import annotations

import struct
import zlib
from dataclasses import dataclass
from typing import Final

VERSAO_DO_PROTOCOLO: Final = 1001
MAGIC_DO_CLIENTE: Final = b"DSUC"
MAGIC_DO_SERVIDOR: Final = b"DSUS"

TIPO_VERSAO: Final = 0x100000
TIPO_PORTAS: Final = 0x100001
TIPO_DADOS: Final = 0x100002

TAMANHO_DO_CABECALHO: Final = 16
TAMANHO_DA_VERSAO: Final = 22
TAMANHO_DA_PORTA: Final = 32
TAMANHO_DOS_DADOS: Final = 100

SLOTS: Final = 4

ESTADO_DESCONECTADO: Final = 0
ESTADO_CONECTADO: Final = 2
MODELO_GIRO_COMPLETO: Final = 2
CONEXAO_USB: Final = 1

_ANALOGICO_NEUTRO: Final = 128

_TAMANHO_POR_TIPO: Final = {
    TIPO_VERSAO: TAMANHO_DA_VERSAO,
    TIPO_PORTAS: TAMANHO_DA_PORTA,
    TIPO_DADOS: TAMANHO_DOS_DADOS,
}


@dataclass(frozen=True)
class PedidoDeVersao:
    client_id: int


@dataclass(frozen=True)
class PedidoDePortas:
    client_id: int
    slots: tuple[int, ...]


@dataclass(frozen=True)
class PedidoDeDados:
    client_id: int
    flags: int
    slot: int
    mac: bytes

    @property
    def por_slot(self) -> bool:
        return bool(self.flags & 0x01)

    @property
    def por_mac(self) -> bool:
        return bool(self.flags & 0x02)


Pedido = PedidoDeVersao | PedidoDePortas | PedidoDeDados


@dataclass(frozen=True)
class Toque:
    """Um contato do touchpad; x e y crus (0..1919 e 0..1079 no DualSense)."""

    ativo: bool = False
    identidade: int = 0
    x: int = 0
    y: int = 0


TOQUE_INATIVO: Final = Toque()


def crc_do_pacote(pacote: bytes | bytearray) -> int:
    """CRC-32 do zlib sobre o pacote inteiro, com os bytes 8..11 zerados."""
    copia = bytearray(pacote)
    copia[8:12] = b"\x00\x00\x00\x00"
    return zlib.crc32(bytes(copia)) & 0xFFFFFFFF


def _u(nome: str, valor: int, bits: int) -> int:
    if not 0 <= valor < (1 << bits):
        raise ValueError(f"{nome} fora de u{bits}: {valor}")
    return valor


def mac_em_bytes(mac: str | bytes) -> bytes:
    """``02:fe:00:00:00:01`` ou 6 bytes crus; vazio ou ``None`` viram zeros."""
    if isinstance(mac, bytes):
        if len(mac) != 6:
            raise ValueError(f"mac com {len(mac)} bytes, esperava 6")
        return mac
    partes = mac.split(":")
    if len(partes) != 6:
        raise ValueError(f"mac ilegível: {mac!r}")
    try:
        return bytes(int(p, 16) for p in partes)
    except ValueError as exc:
        raise ValueError(f"mac ilegível: {mac!r}") from exc


def _fechar(corpo: bytearray, server_id: int) -> bytes:
    """Grava magic, versão, comprimento, id e CRC num pacote que já tem o tipo."""
    corpo[0:4] = MAGIC_DO_SERVIDOR
    struct.pack_into("<HH", corpo, 4, VERSAO_DO_PROTOCOLO, len(corpo) - TAMANHO_DO_CABECALHO)
    struct.pack_into("<I", corpo, 8, 0)
    struct.pack_into("<I", corpo, 12, _u("id do servidor", server_id, 32))
    struct.pack_into("<I", corpo, 8, crc_do_pacote(corpo))
    return bytes(corpo)


def montar_versao(server_id: int) -> bytes:
    """Resposta de versão: 22 bytes, comprimento 6."""
    corpo = bytearray(TAMANHO_DA_VERSAO)
    struct.pack_into("<IH", corpo, 16, TIPO_VERSAO, VERSAO_DO_PROTOCOLO)
    return _fechar(corpo, server_id)


def _escrever_o_estado(
    corpo: bytearray,
    *,
    slot: int,
    estado: int,
    modelo: int,
    conexao: int,
    mac: bytes,
    bateria: int,
) -> None:
    """Os 11 bytes que a porta e os dados têm em comum (offset 20..30)."""
    _u("slot", slot, 8)
    _u("estado", estado, 8)
    _u("modelo", modelo, 8)
    _u("conexão", conexao, 8)
    _u("bateria", bateria, 8)
    struct.pack_into("<BBBB", corpo, 20, slot, estado, modelo, conexao)
    corpo[24:30] = mac_em_bytes(mac)
    corpo[30] = bateria


def montar_porta(
    server_id: int,
    *,
    slot: int,
    estado: int = ESTADO_DESCONECTADO,
    modelo: int = 0,
    conexao: int = 0,
    mac: str | bytes = b"\x00" * 6,
    bateria: int = 0,
) -> bytes:
    """Resposta de portas para UM slot: 32 bytes, comprimento 16.

    Slot vazio leva o número e zeros: ``montar_porta(i, slot=2)``.
    """
    corpo = bytearray(TAMANHO_DA_PORTA)
    struct.pack_into("<I", corpo, 16, TIPO_PORTAS)
    _escrever_o_estado(
        corpo,
        slot=slot,
        estado=estado,
        modelo=modelo,
        conexao=conexao,
        mac=mac_em_bytes(mac),
        bateria=bateria,
    )
    return _fechar(corpo, server_id)


def montar_dados(
    server_id: int,
    *,
    slot: int,
    mac: str | bytes,
    contador: int,
    timestamp_us: int,
    toques: tuple[Toque, Toque] = (TOQUE_INATIVO, TOQUE_INATIVO),
    aceleracao: tuple[float, float, float] = (0.0, 0.0, 0.0),
    giro: tuple[float, float, float] = (0.0, 0.0, 0.0),
    conectado: bool = True,
    estado: int = ESTADO_CONECTADO,
    modelo: int = MODELO_GIRO_COMPLETO,
    conexao: int = CONEXAO_USB,
    bateria: int = 0,
) -> bytes:
    """Resposta de dados: 100 bytes, comprimento 84, botões e analógicos neutros.

    ``contador`` é u32 e ``timestamp_us`` é u64; quem chama aplica a máscara do
    contador (``& 0xFFFFFFFF``), e o excesso aqui levanta ``ValueError``.
    """
    corpo = bytearray(TAMANHO_DOS_DADOS)
    struct.pack_into("<I", corpo, 16, TIPO_DADOS)
    _escrever_o_estado(
        corpo,
        slot=slot,
        estado=estado,
        modelo=modelo,
        conexao=conexao,
        mac=mac_em_bytes(mac),
        bateria=bateria,
    )
    corpo[31] = 1 if conectado else 0
    struct.pack_into("<I", corpo, 32, _u("contador", contador, 32))
    # 36..39: botões, home e botão do touchpad, todos soltos.
    corpo[40:44] = bytes([_ANALOGICO_NEUTRO] * 4)
    # 44..55: direcional e botões analógicos, zerados.
    for indice, toque in enumerate(toques):
        base = 56 + 6 * indice
        corpo[base] = 1 if toque.ativo else 0
        corpo[base + 1] = _u("id do toque", toque.identidade, 8)
        struct.pack_into(
            "<HH", corpo, base + 2, _u("x do toque", toque.x, 16), _u("y do toque", toque.y, 16)
        )
    struct.pack_into("<Q", corpo, 68, _u("timestamp", timestamp_us, 64))
    struct.pack_into("<fff", corpo, 76, *aceleracao)
    struct.pack_into("<fff", corpo, 88, *giro)
    return _fechar(corpo, server_id)


def _cabecalho_valido(pacote: bytes, magic: bytes) -> tuple[int, int] | None:
    """(comprimento, tipo) se magic, versão e comprimento do cabeçalho valem."""
    if len(pacote) < TAMANHO_DO_CABECALHO + 4 or pacote[0:4] != magic:
        return None
    versao, comprimento = struct.unpack_from("<HH", pacote, 4)
    if versao != VERSAO_DO_PROTOCOLO or comprimento < 4:
        return None
    return comprimento, struct.unpack_from("<I", pacote, 16)[0]


def interpretar_pedido(datagrama: bytes) -> Pedido | None:
    """Lê um pedido do emulador; ``None`` para qualquer coisa que não seja um.

    Nunca levanta. Datagrama menor que ``16 + comprimento`` cai; o excesso é
    truncado e o CRC cobre só ``16 + comprimento`` bytes.
    """
    cab = _cabecalho_valido(datagrama, MAGIC_DO_CLIENTE)
    if cab is None:
        return None
    comprimento, tipo = cab
    total = TAMANHO_DO_CABECALHO + comprimento
    if len(datagrama) < total:
        return None
    pacote = datagrama[:total]
    if struct.unpack_from("<I", pacote, 8)[0] != crc_do_pacote(pacote):
        return None
    client_id = struct.unpack_from("<I", pacote, 12)[0]
    if tipo == TIPO_VERSAO:
        return PedidoDeVersao(client_id)
    if tipo == TIPO_PORTAS:
        if comprimento < 8:
            return None
        quantidade = struct.unpack_from("<i", pacote, 20)[0]
        if not 1 <= quantidade <= SLOTS or comprimento < 8 + quantidade:
            return None
        slots = tuple(pacote[24 : 24 + quantidade])
        if any(s >= SLOTS for s in slots):
            return None
        return PedidoDePortas(client_id, slots)
    if tipo == TIPO_DADOS:
        if comprimento != 12:
            return None
        return PedidoDeDados(client_id, pacote[20], pacote[21], bytes(pacote[22:28]))
    return None


def validar_saida(pacote: bytes) -> int | None:
    """Tipo do pacote se o Azahar o aceitaria; ``None`` se algo não confere.

    Confere magic ``DSUS``, versão, comprimento igual ao resto do pacote, o
    tamanho exato do tipo (22, 32 ou 100) e o CRC.
    """
    cab = _cabecalho_valido(pacote, MAGIC_DO_SERVIDOR)
    if cab is None:
        return None
    comprimento, tipo = cab
    esperado = _TAMANHO_POR_TIPO.get(tipo)
    if esperado is None or len(pacote) != esperado:
        return None
    if comprimento != esperado - TAMANHO_DO_CABECALHO:
        return None
    if struct.unpack_from("<I", pacote, 8)[0] != crc_do_pacote(pacote):
        return None
    return tipo


__all__ = [
    "CONEXAO_USB",
    "ESTADO_CONECTADO",
    "ESTADO_DESCONECTADO",
    "MAGIC_DO_CLIENTE",
    "MAGIC_DO_SERVIDOR",
    "MODELO_GIRO_COMPLETO",
    "SLOTS",
    "TAMANHO_DA_PORTA",
    "TAMANHO_DA_VERSAO",
    "TAMANHO_DOS_DADOS",
    "TIPO_DADOS",
    "TIPO_PORTAS",
    "TIPO_VERSAO",
    "TOQUE_INATIVO",
    "VERSAO_DO_PROTOCOLO",
    "Pedido",
    "PedidoDeDados",
    "PedidoDePortas",
    "PedidoDeVersao",
    "Toque",
    "crc_do_pacote",
    "interpretar_pedido",
    "mac_em_bytes",
    "montar_dados",
    "montar_porta",
    "montar_versao",
    "validar_saida",
]
