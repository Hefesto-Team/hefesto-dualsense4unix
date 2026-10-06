"""ar_do_adaptador.py — o ar de cada adaptador Bluetooth, lido do kernel, sem root.

AR-MEDIDO-01 (23/09/2026), decisões R10 e R11 dela: *«Hz reais + pontes»* e a
régua de 79 canais com o que cada adaptador DE FATO evita. Nada estimado.

O QUE ESTE MÓDULO LÊ, e por que nada disto pede root
=====================================================
Três leituras, as três como uid 1000, sem subprocesso:

* ``HCIGETDEVINFO`` — os contadores do adaptador (``acl_rx``, ``acl_tx``,
  ``byte_rx``, ``byte_tx``, ``err_*``) e os créditos ``acl_mtu:acl_pkts``.
  ``acl_rx`` sobe em ``hci_acldata_packet``; ``acl_tx`` em ``btusb_send_frame``,
  isto é, DEPOIS de haver crédito do controlador. Leitura pura do kernel: não
  sai comando nenhum para o rádio.
* ``HCIGETCONNLIST`` — as conexões: handle, endereço, papel e ``out``.
* ``Read AFH Channel Map`` (OGF 0x05, OCF 0x0006), por handle, pelo socket HCI
  cru. ESTE é um comando ao controlador, e é de LEITURA. O kernel o deixa
  passar sem ``CAP_NET_RAW`` pelo ``hci_sec_filter`` de ``net/bluetooth/
  hci_sock.c``: a linha ``OGF_STATUS_PARAM`` é ``0x000000ea``, e o bit 6 (OCF
  0x0006) está ligado. O mesmo filtro deixa o evento ``Command Complete``
  (0x0E) chegar ao socket sem privilégio (``event_mask[0]`` = ``0x1000d9fe``,
  bit 14). Conferido no fonte em 23/09/2026 e MEDIDO na máquina do usuário no mesmo
  dia — ver ``docs/data/orcamento-de-ar.csv``.

AUSÊNCIA É RESPOSTA — o contrato do ``varredura_do_radio.py``
==============================================================
«Não sei» é diferente de «zero», e a diferença viaja em :attr:`ArDoAdaptador.sei`:

* o ioctl falhou, o adaptador sumiu, está desligado, o contador recomeçou, ou
  é a primeira leitura → ``sei`` falso, taxas ``None``, :attr:`motivo` dito;
* **contador congelado com conexão de pé** → «não sei». Um DualSense no rádio
  manda centenas de relatórios por segundo mesmo parado na mesa; ``acl_rx`` que
  não anda com enlace vivo é o instrumento (ou o adaptador) parado, e dizer
  «0 Hz» ali seria o medidor respondendo sobre outra coisa que não o ar;
* adaptador SEM conexão e contador parado → ``0.0``. Isso é «ninguém no
  rádio», que é verdade, e não «rádio ruim». Mas só quando a lista de
  conexões VEIO: sem ela, contador parado é «não sei» (``CONEXOES_ILEGIVEIS``).

O contador é de 32 bits e dá a volta. Um salto negativo é VOLTA quando a taxa
que ele implica é possível (:data:`TETO_DE_PACOTES_POR_S` para pacotes,
:data:`TETO_DE_BYTES_POR_S` para bytes); fora disso é o adaptador que
reiniciou e zerou, e a janela vira «não sei».

O QUE ELE NÃO É
================
Não é o orçamento: quem junta pontes, ``n_max`` e Hz por adaptador é
``integrations/radio_da_mesa.py``, o dono. Este módulo só entrega o que o
kernel e o rádio dizem. E o contador é do ADAPTADOR inteiro — mistura todos
os aparelhos dele; a taxa por controle vem do nó de movimento de cada um
(``core/evdev_reader.MotionSensorReader.hz_do_movimento``).
"""

from __future__ import annotations

import contextlib
import fcntl
import socket
import struct
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

from hefesto_dualsense4unix.core import formas_do_endereco as _formas
from hefesto_dualsense4unix.utils.espera import prontos_para_ler

HCIGETDEVLIST = 0x800448D2
HCIGETDEVINFO = 0x800448D3
HCIGETCONNLIST = 0x800448D4

FORMATO_DEV_INFO = "<H8s6sIB8s3xIIIHHHH10I"
FORMATO_CONN_INFO = "<H6sBBHI"
TAMANHO_CONN_INFO = 16

MAX_ADAPTADORES = 16
MAX_CONEXOES = 20

FLAG_HCI_UP = 0x01
LINK_MODE_MESTRE = 0x0001
TIPO_ACL = 0x01
#: ``LE_LINK`` do kernel: o enlace de baixa energia (pulseira, relógio, fone novo). O
#: ``Read AFH Channel Map`` é do enlace clássico; o equivalente LE (``LE Read Channel Map``,
#: OGF 0x08 OCF 0x0015) NÃO passa pelo ``hci_sec_filter`` sem ``CAP_NET_RAW`` (a tabela do
#: filtro acaba no OGF 5), então um enlace LE não tem faixa própria lida sem root.
TIPO_LE = 0x80

VOLTA_DO_CONTADOR = 1 << 32
TETO_DE_PACOTES_POR_S = 20_000.0
TETO_DE_BYTES_POR_S = 2_000_000.0
_CONTADORES_DE_BYTES = frozenset({"byte_rx", "byte_tx"})

JANELA_S = 1.0
JANELA_MAXIMA_S = 5.0

OPCODE_LER_MAPA_AFH = (0x05 << 10) | 0x0006
OPCODE_LER_RSSI = (0x05 << 10) | 0x0005
OPCODE_LER_QUALIDADE = (0x05 << 10) | 0x0003
CANAIS_DO_BT = 79
CANAIS_MINIMOS_DO_AFH = 20
CANAIS_CALMOS = 60
NIVEL_LISO = "liso"
NIVEL_MEDIO = "medio"  # (noqa-acento): nome de máquina, o valor do `data-nivel`
NIVEL_ENGASGA = "engasga"
PRAZO_DO_AFH_S = 0.5

_HCI_COMMAND_PKT = 0x01
_HCI_EVENT_PKT = 0x04
_EVT_CMD_COMPLETE = 0x0E
_EVT_CMD_STATUS = 0x0F
_SOL_HCI = getattr(socket, "SOL_HCI", 0)
_HCI_FILTER = getattr(socket, "HCI_FILTER", 2)

SEM_BLUETOOTH = "o kernel não abriu o socket de Bluetooth"
IOCTL_FALHOU = "o kernel não respondeu a leitura do adaptador"
ADAPTADOR_SUMIU = "o adaptador sumiu do kernel"
ADAPTADOR_DESLIGADO = "o adaptador está desligado"
PRIMEIRA_LEITURA = "primeira leitura: falta a segunda para haver taxa"
CONTADOR_RECOMECOU = "o contador recomeçou: o adaptador reiniciou"
CONTADOR_PARADO = "o contador não andou com conexão de pé"
CONEXOES_ILEGIVEIS = "o contador não andou e o kernel não listou as conexões"

Ioctl = Callable[[int, bytearray], None]


@dataclass(frozen=True)
class Contadores:
    """Os dez ``__u32`` de ``struct hci_dev_stats``, na ordem do kernel."""

    err_rx: int = 0
    err_tx: int = 0
    cmd_tx: int = 0
    evt_rx: int = 0
    acl_tx: int = 0
    acl_rx: int = 0
    sco_tx: int = 0
    sco_rx: int = 0
    byte_rx: int = 0
    byte_tx: int = 0


@dataclass(frozen=True)
class LeituraDoAdaptador:
    """Uma foto do ``HCIGETDEVINFO``. ``instante`` é ``time.monotonic``."""

    hci: int
    endereco: str
    ligado: bool
    acl_mtu: int
    acl_pkts: int
    contadores: Contadores
    instante: float


@dataclass(frozen=True)
class Enlace:
    """Uma linha do ``HCIGETCONNLIST``."""

    handle: int
    endereco: str
    tipo: int
    saida: bool
    estado: int
    link_mode: int

    @property
    def mestre(self) -> bool:
        """O adaptador é o mestre do enlace (``HCI_LM_MASTER``)."""
        return bool(self.link_mode & LINK_MODE_MESTRE)


@dataclass(frozen=True)
class MapaAFH:
    """O mapa de canais que o rádio USA num enlace. ``True`` = canal usado."""

    handle: int
    modo: int
    canais: tuple[bool, ...]

    @property
    def usados(self) -> int:
        return sum(1 for usado in self.canais if usado)

    @property
    def evitados(self) -> tuple[int, ...]:
        return tuple(n for n, usado in enumerate(self.canais) if not usado)


@dataclass(frozen=True)
class ArDoAdaptador:
    """O ar de UM adaptador numa janela. Taxas por segundo; ``None`` = não sei."""

    hci: int
    endereco: str
    entrada_por_s: float | None = None
    saida_por_s: float | None = None
    bytes_entrada_por_s: float | None = None
    bytes_saida_por_s: float | None = None
    erros_por_s: float | None = None
    conexoes: tuple[Enlace, ...] | None = None
    acl_mtu: int = 0
    acl_pkts: int = 0
    janela_s: float = 0.0
    motivo: str = ""

    @property
    def sei(self) -> bool:
        """``False`` quando a janela não deu taxa — «não sei», nunca «zero»."""
        return self.entrada_por_s is not None


def endereco_do_kernel(bdaddr: bytes) -> str:
    """``bdaddr_t`` (6 bytes, ordem invertida) → ``aa:bb:cc:dd:ee:ff``."""
    return ":".join(f"{b:02x}" for b in bytes(bdaddr)[::-1])


def _ioctl_do_kernel() -> Ioctl:
    """O ioctl de verdade, num socket HCI aberto na primeira chamada."""
    guardado: list[socket.socket] = []

    def chamar(pedido: int, buf: bytearray) -> None:
        if not guardado:
            guardado.append(
                socket.socket(socket.AF_BLUETOOTH, socket.SOCK_RAW, socket.BTPROTO_HCI)
            )
        fcntl.ioctl(guardado[0].fileno(), pedido, buf, True)

    return chamar


class LeitorDoKernel:
    """Os três ioctls de leitura. Todo erro vira ``None`` — «não sei»."""

    def __init__(
        self, *, ioctl: Ioctl | None = None, relogio: Callable[[], float] = time.monotonic
    ) -> None:
        self._ioctl = ioctl if ioctl is not None else _ioctl_do_kernel()
        self._relogio = relogio

    def adaptadores(self) -> list[int] | None:
        """Os ``hci`` que o kernel conhece, ou ``None`` se ele não respondeu."""
        buf = bytearray(struct.pack("<H2x", MAX_ADAPTADORES) + bytes(8 * MAX_ADAPTADORES))
        try:
            self._ioctl(HCIGETDEVLIST, buf)
        except OSError:
            return None
        quantos = min(struct.unpack_from("<H", buf, 0)[0], MAX_ADAPTADORES)
        return sorted(struct.unpack_from("<H", buf, 4 + 8 * i)[0] for i in range(quantos))

    def ler(self, hci: int) -> LeituraDoAdaptador | None:
        """``HCIGETDEVINFO`` de um adaptador, ou ``None``."""
        tamanho = struct.calcsize(FORMATO_DEV_INFO)
        buf = bytearray(struct.pack("<H", hci) + bytes(tamanho - 2))
        try:
            self._ioctl(HCIGETDEVINFO, buf)
        except OSError:
            return None
        campos = struct.unpack(FORMATO_DEV_INFO, bytes(buf))
        flags = campos[3]
        acl_mtu, acl_pkts = campos[9], campos[10]
        return LeituraDoAdaptador(
            hci=int(campos[0]),
            endereco=endereco_do_kernel(campos[2]),
            ligado=bool(flags & FLAG_HCI_UP),
            acl_mtu=int(acl_mtu),
            acl_pkts=int(acl_pkts),
            contadores=Contadores(*(int(v) for v in campos[13:23])),
            instante=self._relogio(),
        )

    def conexoes(self, hci: int) -> tuple[Enlace, ...] | None:
        """``HCIGETCONNLIST`` — tupla vazia é «nenhuma conexão», não erro."""
        buf = bytearray(
            struct.pack("<HH", hci, MAX_CONEXOES) + bytes(TAMANHO_CONN_INFO * MAX_CONEXOES)
        )
        try:
            self._ioctl(HCIGETCONNLIST, buf)
        except OSError:
            return None
        quantas = min(struct.unpack_from("<H", buf, 2)[0], MAX_CONEXOES)
        saida: list[Enlace] = []
        for i in range(quantas):
            handle, bdaddr, tipo, out, estado, link_mode = struct.unpack_from(
                FORMATO_CONN_INFO, buf, 4 + TAMANHO_CONN_INFO * i
            )
            saida.append(
                Enlace(
                    handle=int(handle),
                    endereco=endereco_do_kernel(bdaddr),
                    tipo=int(tipo),
                    saida=bool(out),
                    estado=int(estado),
                    link_mode=int(link_mode),
                )
            )
        return tuple(saida)


def _delta(
    antes: int, depois: int, janela_s: float, teto_por_s: float = TETO_DE_PACOTES_POR_S
) -> int | None:
    """``depois - antes`` com a volta dos 32 bits; ``None`` = o contador zerou."""
    if depois >= antes:
        return depois - antes
    volta = depois + VOLTA_DO_CONTADOR - antes
    if janela_s > 0 and volta / janela_s <= teto_por_s:
        return volta
    return None


def conferir(
    antes: LeituraDoAdaptador | None,
    depois: LeituraDoAdaptador | None,
    conexoes: tuple[Enlace, ...] | None,
) -> ArDoAdaptador:
    """O ar de uma janela entre duas fotos — o CONFERIR do medidor."""
    if depois is None:
        base = antes
        return ArDoAdaptador(
            hci=base.hci if base else -1,
            endereco=base.endereco if base else "",
            conexoes=conexoes,
            motivo=IOCTL_FALHOU,
        )

    def feito(motivo: str = "", janela: float = 0.0, **taxas: float) -> ArDoAdaptador:
        return ArDoAdaptador(
            hci=depois.hci,
            endereco=depois.endereco,
            conexoes=conexoes,
            acl_mtu=depois.acl_mtu,
            acl_pkts=depois.acl_pkts,
            janela_s=janela,
            motivo=motivo,
            **taxas,
        )

    if not depois.ligado:
        return feito(ADAPTADOR_DESLIGADO)
    if antes is None or antes.endereco != depois.endereco or antes.hci != depois.hci:
        return feito(PRIMEIRA_LEITURA)
    janela = depois.instante - antes.instante
    if janela <= 0:
        return feito(PRIMEIRA_LEITURA)
    a, d = antes.contadores, depois.contadores
    deltas: dict[str, int] = {}
    for nome in ("acl_rx", "acl_tx", "byte_rx", "byte_tx", "err_rx", "err_tx"):
        teto = TETO_DE_BYTES_POR_S if nome in _CONTADORES_DE_BYTES else TETO_DE_PACOTES_POR_S
        delta = _delta(getattr(a, nome), getattr(d, nome), janela, teto)
        if delta is None:
            return feito(CONTADOR_RECOMECOU, round(janela, 3))
        deltas[nome] = delta
    ha_enlace = any(c.tipo == TIPO_ACL for c in conexoes or ())
    if ha_enlace and deltas["acl_rx"] == 0:
        return feito(CONTADOR_PARADO, round(janela, 3))
    if conexoes is None and deltas["acl_rx"] == 0:
        return feito(CONEXOES_ILEGIVEIS, round(janela, 3))
    return feito(
        "",
        round(janela, 3),
        entrada_por_s=round(deltas["acl_rx"] / janela, 1),
        saida_por_s=round(deltas["acl_tx"] / janela, 1),
        bytes_entrada_por_s=round(deltas["byte_rx"] / janela, 1),
        bytes_saida_por_s=round(deltas["byte_tx"] / janela, 1),
        erros_por_s=round((deltas["err_rx"] + deltas["err_tx"]) / janela, 1),
    )


class MedidorDeAr:
    """As taxas de todos os adaptadores, janela a janela.

    Pode ser chamado mais depressa que a janela (o ``state_full`` roda a
    10 Hz): entre duas janelas ele devolve o último resultado, e a foto de
    referência só anda quando a janela fecha. Referência mais velha que
    :data:`JANELA_MAXIMA_S` recomeça a conta em vez de publicar média velha.
    """

    def __init__(
        self,
        leitor: LeitorDoKernel | None = None,
        *,
        janela_s: float = JANELA_S,
        janela_maxima_s: float = JANELA_MAXIMA_S,
    ) -> None:
        self._leitor = leitor if leitor is not None else LeitorDoKernel()
        self._janela_s = janela_s
        self._janela_maxima_s = janela_maxima_s
        self._referencia: dict[int, LeituraDoAdaptador] = {}
        self._ultimo: dict[str, ArDoAdaptador] = {}

    def amostrar(self) -> dict[str, ArDoAdaptador]:
        """``{endereço do adaptador: ArDoAdaptador}`` de agora."""
        hcis = self._leitor.adaptadores()
        if hcis is None:
            self._referencia.clear()
            self._ultimo = {"": ArDoAdaptador(hci=-1, endereco="", motivo=SEM_BLUETOOTH)}
            return dict(self._ultimo)
        resultado: dict[str, ArDoAdaptador] = {}
        vistos: set[int] = set()
        for hci in hcis:
            vistos.add(hci)
            agora = self._leitor.ler(hci)
            conexoes = self._leitor.conexoes(hci)
            ref = self._referencia.get(hci)
            if agora is None:
                ar = conferir(ref, None, conexoes)
                self._referencia.pop(hci, None)
            elif (
                ref is None
                or ref.endereco != agora.endereco
                or not agora.ligado
                or agora.instante - ref.instante > self._janela_maxima_s
            ):
                ar = conferir(None, agora, conexoes)
                self._referencia[hci] = agora
            elif agora.instante - ref.instante >= self._janela_s:
                ar = conferir(ref, agora, conexoes)
                self._referencia[hci] = agora
            else:
                anterior = self._ultimo.get(agora.endereco)
                ar = (
                    anterior
                    if anterior is not None
                    else conferir(None, agora, conexoes)
                )
            resultado[ar.endereco or f"hci{hci}"] = ar
        for hci in [h for h in self._referencia if h not in vistos]:
            ref = self._referencia.pop(hci)
            resultado.setdefault(
                ref.endereco,
                ArDoAdaptador(hci=hci, endereco=ref.endereco, motivo=ADAPTADOR_SUMIU),
            )
        self._ultimo = dict(resultado)
        return resultado


def mapa_afh_da_resposta(evento: bytes, handle: int) -> MapaAFH | None:
    """O ``Command Complete`` do ``Read AFH Channel Map`` → :class:`MapaAFH`."""
    if len(evento) < 20 or evento[0] != _HCI_EVENT_PKT or evento[1] != _EVT_CMD_COMPLETE:
        return None
    opcode = struct.unpack_from("<H", evento, 4)[0]
    if opcode != OPCODE_LER_MAPA_AFH or evento[6] != 0x00:
        return None
    devolvido = struct.unpack_from("<H", evento, 7)[0] & 0x0FFF
    if devolvido != (handle & 0x0FFF):
        return None
    mapa = evento[10:20]
    canais = tuple(bool(mapa[n // 8] & (1 << (n % 8))) for n in range(CANAIS_DO_BT))
    return MapaAFH(handle=devolvido, modo=int(evento[9]), canais=canais)


def rssi_da_resposta(evento: bytes, handle: int) -> int | None:
    """O ``Command Complete`` do ``Read RSSI`` → o RSSI do enlace, assinado."""
    if len(evento) < 10 or evento[0] != _HCI_EVENT_PKT or evento[1] != _EVT_CMD_COMPLETE:
        return None
    opcode = struct.unpack_from("<H", evento, 4)[0]
    if opcode != OPCODE_LER_RSSI or evento[6] != 0x00:
        return None
    if (struct.unpack_from("<H", evento, 7)[0] & 0x0FFF) != (handle & 0x0FFF):
        return None
    return int(struct.unpack_from("<b", evento, 9)[0])


def qualidade_da_resposta(evento: bytes, handle: int) -> int | None:
    """O ``Command Complete`` do ``Read Link Quality`` → a qualidade do enlace (0 a 255)."""
    if len(evento) < 10 or evento[0] != _HCI_EVENT_PKT or evento[1] != _EVT_CMD_COMPLETE:
        return None
    opcode = struct.unpack_from("<H", evento, 4)[0]
    if opcode != OPCODE_LER_QUALIDADE or evento[6] != 0x00:
        return None
    if (struct.unpack_from("<H", evento, 7)[0] & 0x0FFF) != (handle & 0x0FFF):
        return None
    return int(evento[9])


def _erro_do_comando(evento: bytes, opcode_esperado: int) -> int | None:
    """O status de erro do NOSSO comando (``Command Complete`` ou ``Status``)."""
    if len(evento) < 7 or evento[0] != _HCI_EVENT_PKT:
        return None
    if evento[1] == _EVT_CMD_COMPLETE:
        opcode, status = struct.unpack_from("<H", evento, 4)[0], evento[6]
    elif evento[1] == _EVT_CMD_STATUS:
        opcode, status = struct.unpack_from("<H", evento, 5)[0], evento[3]
    else:
        return None
    return int(status) if opcode == opcode_esperado and status else None


def _abrir_hci_cru(hci: int) -> socket.socket:
    sock = socket.socket(socket.AF_BLUETOOTH, socket.SOCK_RAW, socket.BTPROTO_HCI)
    try:
        sock.bind((hci,))
    except OSError:
        sock.close()
        raise
    return sock


def _perguntar_ao_hci(
    hci: int,
    handle: int,
    opcode: int,
    entender: Callable[[bytes], Any],
    *,
    prazo_s: float,
    abrir: Callable[[int], socket.socket] | None,
    relogio: Callable[[], float],
) -> Any:
    """Um comando de leitura de UM enlace ao rádio cru; ``entender`` lê a resposta.

    ``None`` = não sei. Dono único do socket cru, do filtro e do prazo: o AFH e o
    RSSI perguntam por aqui.
    """
    if abrir is None:
        from hefesto_dualsense4unix.utils.xdg_paths import fake_mode_enabled

        if fake_mode_enabled():
            return None
    try:
        sock = (abrir or _abrir_hci_cru)(hci)
    except OSError:
        return None
    with contextlib.closing(sock):
        try:
            filtro = struct.pack(
                "<IIIH2x",
                1 << _HCI_EVENT_PKT,
                (1 << _EVT_CMD_COMPLETE) | (1 << _EVT_CMD_STATUS),
                0,
                opcode,
            )
            sock.setsockopt(_SOL_HCI, _HCI_FILTER, filtro)
            sock.send(struct.pack("<BHBH", _HCI_COMMAND_PKT, opcode, 2, handle))
        except OSError:
            return None
        fim = relogio() + prazo_s
        while True:
            restante = fim - relogio()
            if restante <= 0:
                return None
            try:
                prontos = prontos_para_ler([sock], restante)
                if not prontos:
                    return None
                evento = sock.recv(260)
            except OSError:
                return None
            achado = entender(evento)
            if achado is not None:
                return achado
            if _erro_do_comando(evento, opcode) is not None:
                return None


def ler_mapa_afh(
    hci: int,
    handle: int,
    *,
    prazo_s: float = PRAZO_DO_AFH_S,
    abrir: Callable[[int], socket.socket] | None = None,
    relogio: Callable[[], float] = time.monotonic,
) -> MapaAFH | None:
    """Pergunta ao rádio o mapa AFH de um enlace. ``None`` = não sei."""
    achado = _perguntar_ao_hci(
        hci, handle, OPCODE_LER_MAPA_AFH, lambda e: mapa_afh_da_resposta(e, handle),
        prazo_s=prazo_s, abrir=abrir, relogio=relogio)
    return achado if isinstance(achado, MapaAFH) else None


def ler_rssi(
    hci: int,
    handle: int,
    *,
    prazo_s: float = PRAZO_DO_AFH_S,
    abrir: Callable[[int], socket.socket] | None = None,
    relogio: Callable[[], float] = time.monotonic,
) -> int | None:
    """O RSSI do enlace (``HCI_Read_RSSI``, sem root). ``None`` = não sei."""
    achado = _perguntar_ao_hci(
        hci, handle, OPCODE_LER_RSSI, lambda e: rssi_da_resposta(e, handle),
        prazo_s=prazo_s, abrir=abrir, relogio=relogio)
    return achado if isinstance(achado, int) else None


def ler_qualidade(
    hci: int,
    handle: int,
    *,
    prazo_s: float = PRAZO_DO_AFH_S,
    abrir: Callable[[int], socket.socket] | None = None,
    relogio: Callable[[], float] = time.monotonic,
) -> int | None:
    """A qualidade do enlace (``HCI_Read_Link_Quality``, sem root). ``None`` = não sei.

    O comando é opcional no controlador: um chip que não o tem responde «Unknown HCI
    Command», e isso volta como ``None`` (o mesmo «não sei» do AFH), sem pergunta à parte.
    """
    achado = _perguntar_ao_hci(
        hci, handle, OPCODE_LER_QUALIDADE, lambda e: qualidade_da_resposta(e, handle),
        prazo_s=prazo_s, abrir=abrir, relogio=relogio)
    return achado if isinstance(achado, int) else None


@dataclass(frozen=True)
class EnlaceLido:
    """O que se leu de UM enlace: o mapa dele (clássico), a qualidade_do_enlace, ou ``le``.

    ``canais_evitados`` é ``None`` quando o mapa não veio (enlace LE, comando recusado ou o
    primeiro tique): «não sei», nunca «nenhum evitado».
    """

    le: bool
    canais_evitados: tuple[int, ...] | None = None
    qualidade_do_enlace: int | None = None


def enlaces_do_adaptador(
    ar: ArDoAdaptador,
    *,
    ler_mapa: Callable[[int, int], MapaAFH | None] = ler_mapa_afh,
    ler_qual: Callable[[int, int], int | None] = ler_qualidade,
) -> dict[str, EnlaceLido]:
    """``{endereço do aparelho: EnlaceLido}`` de TODO enlace do adaptador, o aparelho que for.

    O enlace clássico (ACL) leva o mapa AFH e a qualidade; o LE só diz que é LE. Um aparelho
    com os dois (um celular) fica com o clássico.
    """
    saida: dict[str, EnlaceLido] = {}
    for conexao in ar.conexoes or ():
        if conexao.tipo == TIPO_ACL:
            mapa = ler_mapa(ar.hci, conexao.handle)
            saida[conexao.endereco] = EnlaceLido(
                le=False,
                canais_evitados=mapa.evitados if mapa is not None else None,
                qualidade_do_enlace=ler_qual(ar.hci, conexao.handle))
        elif conexao.tipo == TIPO_LE:
            saida.setdefault(conexao.endereco, EnlaceLido(le=True))
    return saida


def canais_evitados_pelo_adaptador(
    enlaces: Mapping[str, EnlaceLido],
) -> tuple[int, ...] | None:
    """Os canais que o adaptador evita em TODOS os enlaces dele que tiveram o mapa lido.

    ``None`` = nenhum mapa lido (sem conexão clássica, ou o rádio não respondeu): adaptador
    vazio não «evita zero canais».
    """
    lidos = [e.canais_evitados for e in enlaces.values() if e.canais_evitados is not None]
    if not lidos:
        return None
    evitados = set(lidos[0])
    for canais in lidos[1:]:
        evitados &= set(canais)
    return tuple(sorted(evitados))


def _mascarar(endereco: str) -> str:
    """A máscara da casa: octetos 4 e 5 zerados, na grafia que chegou."""
    return _formas.mascarar(endereco)


def main(argv: list[str] | None = None) -> int:
    """Bancada, só leitura: ``python -m …ar_do_adaptador [segundos]``."""
    import sys

    args = list(sys.argv[1:] if argv is None else argv)
    segundos = float(args[0]) if args else 10.0
    medidor = MedidorDeAr(janela_s=segundos, janela_maxima_s=segundos + 5.0)
    medidor.amostrar()
    time.sleep(segundos)
    for endereco, ar in sorted(medidor.amostrar().items()):
        print(
            f"hci{ar.hci} {_mascarar(endereco)} janela={ar.janela_s}s "
            f"acl_rx/s={ar.entrada_por_s} acl_tx/s={ar.saida_por_s} "
            f"B_rx/s={ar.bytes_entrada_por_s} erros/s={ar.erros_por_s} "
            f"acl={ar.acl_mtu}:{ar.acl_pkts} conexoes="
            f"{len(ar.conexoes) if ar.conexoes is not None else 'não sei'}"
            + (f" motivo={ar.motivo!r}" if ar.motivo else "")
        )
        for conexao in ar.conexoes or ():
            mapa = ler_mapa_afh(ar.hci, conexao.handle) if conexao.tipo == TIPO_ACL else None
            print(
                f"  handle={conexao.handle} {_mascarar(conexao.endereco)} "
                f"tipo={conexao.tipo} out={int(conexao.saida)} mestre={conexao.mestre} "
                + (
                    f"afh modo={mapa.modo} usados={mapa.usados}/{CANAIS_DO_BT} "
                    f"evitados={list(mapa.evitados)}"
                    if mapa is not None
                    else "afh=não sei"
                )
            )
    return 0


if __name__ == "__main__":  # pragma: no cover - bancada
    raise SystemExit(main())


def nivel_dos_canais(usados: object) -> str:
    """O nível do «N/79» de um adaptador, pelo piso do salto"""
    if isinstance(usados, bool) or not isinstance(usados, int):
        return ""
    if usados >= CANAIS_CALMOS:
        return NIVEL_LISO
    if usados > CANAIS_MINIMOS_DO_AFH:
        return NIVEL_MEDIO
    return NIVEL_ENGASGA


__all__ = [
    "ADAPTADOR_DESLIGADO",
    "ADAPTADOR_SUMIU",
    "CANAIS_CALMOS",
    "CANAIS_DO_BT",
    "CANAIS_MINIMOS_DO_AFH",
    "CONEXOES_ILEGIVEIS",
    "CONTADOR_PARADO",
    "CONTADOR_RECOMECOU",
    "IOCTL_FALHOU",
    "JANELA_S",
    "NIVEL_ENGASGA",
    "NIVEL_LISO",
    "NIVEL_MEDIO",
    "OPCODE_LER_MAPA_AFH",
    "OPCODE_LER_QUALIDADE",
    "PRIMEIRA_LEITURA",
    "SEM_BLUETOOTH",
    "TIPO_LE",
    "ArDoAdaptador",
    "Contadores",
    "Enlace",
    "EnlaceLido",
    "LeitorDoKernel",
    "LeituraDoAdaptador",
    "MapaAFH",
    "MedidorDeAr",
    "canais_evitados_pelo_adaptador",
    "conferir",
    "endereco_do_kernel",
    "enlaces_do_adaptador",
    "ler_mapa_afh",
    "ler_qualidade",
    "main",
    "mapa_afh_da_resposta",
    "nivel_dos_canais",
    "qualidade_da_resposta",
]
