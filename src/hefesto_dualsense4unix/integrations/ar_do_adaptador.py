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
  bit 14). Conferido no fonte em 23/09/2026 e MEDIDO na máquina dela no mesmo
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
import select
import socket
import struct
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass

#: ``_IOR('H', 210..212, int)`` de ``include/net/bluetooth/hci_sock.h``.
HCIGETDEVLIST = 0x800448D2
HCIGETDEVINFO = 0x800448D3
HCIGETCONNLIST = 0x800448D4

#: ``struct hci_dev_info``: dev_id, name[8], bdaddr[6], flags, type,
#: features[8], (3 de alinhamento), pkt_type, link_policy, link_mode, acl_mtu,
#: acl_pkts, sco_mtu, sco_pkts e os dez ``__u32`` de ``struct hci_dev_stats``.
#: 92 bytes — medido na máquina dela com o ``calcsize`` e com os valores lidos
#: batendo com o ``1021:6`` do estudo.
FORMATO_DEV_INFO = "<H8s6sIB8s3xIIIHHHH10I"
#: ``struct hci_conn_info``: handle, bdaddr[6], type, out, state, link_mode.
FORMATO_CONN_INFO = "<H6sBBHI"
TAMANHO_CONN_INFO = 16

#: Quantos adaptadores e quantas conexões por adaptador se pedem ao kernel.
MAX_ADAPTADORES = 16
MAX_CONEXOES = 20

#: ``HCI_UP`` é o bit 0 de ``hci_dev_info.flags``.
FLAG_HCI_UP = 0x01
#: ``HCI_LM_MASTER`` em ``link_mode``: o adaptador é o mestre do enlace.
LINK_MODE_MESTRE = 0x0001
#: ``ACL_LINK`` em ``hci_conn_info.type``.
TIPO_ACL = 0x01

#: O contador do kernel é ``__u32``.
VOLTA_DO_CONTADOR = 1 << 32
#: Acima disto um salto negativo NÃO é volta, é contador zerado. O teto físico
#: do BR/EDR é 1.600 fatias por segundo; 20.000 pacotes/s deixa folga de sobra
#: para qualquer rádio e ainda separa volta de reinício.
TETO_DE_PACOTES_POR_S = 20_000.0
#: O mesmo teto para os contadores de BYTES, que não contam pacote: o
#: ``btusb`` soma ali cada URB (evento e ACL) de um barramento USB full-speed,
#: 12 Mbit/s = 1,5 MB/s. É o contador que MAIS dá a volta — a ~70 kB/s de um
#: controle no rádio, uma vez a cada ~17 h —, e medi-lo com o teto de pacotes
#: fazia toda volta dele virar «o adaptador reiniciou» e apagar a janela
#: inteira (conferência da AR-MEDIDO-01, 23/09/2026).
TETO_DE_BYTES_POR_S = 2_000_000.0
#: Os contadores de bytes, que leem o teto acima em vez do de pacotes.
_CONTADORES_DE_BYTES = frozenset({"byte_rx", "byte_tx"})

#: Janela padrão de uma taxa: um segundo. O governador pede 0,25 s.
JANELA_S = 1.0
#: Referência mais velha que isto não vira taxa: é média de um silêncio de
#: quem perguntou (a janela fechada, o daemon ocupado), e seria número velho
#: publicado como «agora».
JANELA_MAXIMA_S = 5.0

#: ``Read AFH Channel Map`` = OGF 0x05 (STATUS_PARAM), OCF 0x0006.
OPCODE_LER_MAPA_AFH = (0x05 << 10) | 0x0006
#: Os 79 canais do BR/EDR, de 2.402 a 2.480 MHz.
CANAIS_DO_BT = 79
#: Quanto se espera o ``Command Complete``. O controlador responde em
#: milissegundos; meio segundo cobre o adaptador ocupado sem prender ninguém.
PRAZO_DO_AFH_S = 0.5

_HCI_COMMAND_PKT = 0x01
_HCI_EVENT_PKT = 0x04
_EVT_CMD_COMPLETE = 0x0E
_EVT_CMD_STATUS = 0x0F
_SOL_HCI = getattr(socket, "SOL_HCI", 0)
_HCI_FILTER = getattr(socket, "HCI_FILTER", 2)

#: As frases do «não sei». Curtas: elas podem chegar a uma dica da tela.
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
    """``bdaddr_t`` (6 bytes, ordem invertida) → ``aa:bb:cc:dd:ee:ff``.

    Minúsculo e com dois-pontos: é a forma do ``HID_PHYS`` que
    ``radio_da_mesa.adaptador_por_uniq`` devolve, e as duas chaves têm de casar.
    """
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
    """Os três ioctls de leitura. Todo erro vira ``None`` — «não sei».

    ``ioctl`` é injetável: a suíte entrega um dublê que empacota o que o
    kernel empacotaria, e nada aqui toca o rádio dela.
    """

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
    """O ar de uma janela entre duas fotos — o CONFERIR do medidor.

    É aqui que mora o contrato inteiro de «não sei»; :class:`MedidorDeAr` só
    guarda as fotos e chama isto.
    """
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
    # Sem a lista de conexões, contador parado não separa «ninguém no rádio»
    # de «instrumento parado com enlace de pé» — e só o primeiro é zero.
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
        """``{endereço do adaptador: ArDoAdaptador}`` de agora.

        Chave ``""`` com :data:`SEM_BLUETOOTH` quando o kernel nem lista os
        adaptadores. O adaptador que existia e sumiu sai UMA vez com
        :data:`ADAPTADOR_SUMIU` — ausência dita, não apagada.
        """
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
    """O ``Command Complete`` do ``Read AFH Channel Map`` → :class:`MapaAFH`.

    ``None`` para qualquer outra coisa: outro evento, outro opcode, outro
    handle, status de erro (``0x02``, conexão desconhecida) ou pacote curto.
    Os parâmetros de retorno são status, handle, modo e dez bytes de mapa; o
    canal ``n`` é o bit ``n % 8`` do byte ``n // 8``.
    """
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


def resposta_de_erro_do_afh(evento: bytes) -> int | None:
    """O status de erro do nosso comando (``Command Complete`` ou ``Status``)."""
    if len(evento) < 7 or evento[0] != _HCI_EVENT_PKT:
        return None
    if evento[1] == _EVT_CMD_COMPLETE:
        opcode, status = struct.unpack_from("<H", evento, 4)[0], evento[6]
    elif evento[1] == _EVT_CMD_STATUS:
        opcode, status = struct.unpack_from("<H", evento, 5)[0], evento[3]
    else:
        return None
    return int(status) if opcode == OPCODE_LER_MAPA_AFH and status else None


def _abrir_hci_cru(hci: int) -> socket.socket:
    sock = socket.socket(socket.AF_BLUETOOTH, socket.SOCK_RAW, socket.BTPROTO_HCI)
    try:
        sock.bind((hci,))
    except OSError:
        sock.close()
        raise
    return sock


def ler_mapa_afh(
    hci: int,
    handle: int,
    *,
    prazo_s: float = PRAZO_DO_AFH_S,
    abrir: Callable[[int], socket.socket] | None = None,
    relogio: Callable[[], float] = time.monotonic,
) -> MapaAFH | None:
    """Pergunta ao rádio o mapa AFH de um enlace. ``None`` = não sei.

    BLOQUEIA até ``prazo_s``: quem chama do laço do daemon chama numa thread.
    O filtro do socket deixa passar só ``Command Complete``/``Status`` do
    nosso opcode, então o que chega é a resposta — ou nada.
    """
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
                OPCODE_LER_MAPA_AFH,
            )
            sock.setsockopt(_SOL_HCI, _HCI_FILTER, filtro)
            sock.send(struct.pack("<BHBH", _HCI_COMMAND_PKT, OPCODE_LER_MAPA_AFH, 2, handle))
        except OSError:
            return None
        fim = relogio() + prazo_s
        while True:
            restante = fim - relogio()
            if restante <= 0:
                return None
            try:
                prontos, _, _ = select.select([sock], [], [], restante)
                if not prontos:
                    return None
                evento = sock.recv(260)
            except OSError:
                return None
            mapa = mapa_afh_da_resposta(evento, handle)
            if mapa is not None:
                return mapa
            if resposta_de_erro_do_afh(evento) is not None:
                return None


def mapas_afh_do_adaptador(
    ar: ArDoAdaptador,
    *,
    ler: Callable[[int, int], MapaAFH | None] = ler_mapa_afh,
) -> dict[str, MapaAFH | None]:
    """``{endereço do aparelho: MapaAFH | None}`` de cada enlace ACL do adaptador."""
    saida: dict[str, MapaAFH | None] = {}
    for conexao in ar.conexoes or ():
        if conexao.tipo == TIPO_ACL:
            saida[conexao.endereco] = ler(ar.hci, conexao.handle)
    return saida


def canais_evitados_pelo_adaptador(
    mapas: Mapping[str, MapaAFH | None],
) -> tuple[int, ...] | None:
    """Os canais que o adaptador evita em TODOS os enlaces dele.

    ``None`` = não sei: adaptador sem enlace (AFH só existe com conexão) ou
    nenhum mapa lido. Com enlaces que discordam, conta só o canal evitado em
    todos — «evita» é afirmação, e afirmação pede os dois lados.
    """
    lidos = [m for m in mapas.values() if m is not None]
    if not lidos:
        return None
    evitados = set(lidos[0].evitados)
    for mapa in lidos[1:]:
        evitados &= set(mapa.evitados)
    return tuple(sorted(evitados))


def _mascarar(endereco: str) -> str:
    """A máscara da casa: octetos 4 e 5 zerados."""
    partes = endereco.split(":")
    if len(partes) != 6:
        return endereco
    return ":".join([*partes[:3], "00", "00", *partes[5:]])


def main(argv: list[str] | None = None) -> int:
    """Bancada, só leitura: ``python -m …ar_do_adaptador [segundos]``.

    Imprime ``acl_rx/s`` por adaptador na janela pedida e o mapa AFH de cada
    enlace. Endereços saem mascarados — a saída pode acabar num relatório.
    """
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


__all__ = [
    "ADAPTADOR_DESLIGADO",
    "ADAPTADOR_SUMIU",
    "CANAIS_DO_BT",
    "CONEXOES_ILEGIVEIS",
    "CONTADOR_PARADO",
    "CONTADOR_RECOMECOU",
    "IOCTL_FALHOU",
    "JANELA_S",
    "OPCODE_LER_MAPA_AFH",
    "PRIMEIRA_LEITURA",
    "SEM_BLUETOOTH",
    "ArDoAdaptador",
    "Contadores",
    "Enlace",
    "LeitorDoKernel",
    "LeituraDoAdaptador",
    "MapaAFH",
    "MedidorDeAr",
    "canais_evitados_pelo_adaptador",
    "conferir",
    "endereco_do_kernel",
    "ler_mapa_afh",
    "main",
    "mapa_afh_da_resposta",
    "mapas_afh_do_adaptador",
    "resposta_de_erro_do_afh",
]
