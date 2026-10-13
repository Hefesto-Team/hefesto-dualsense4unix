"""O servidor DSU (cemuhook): leva o toque e o movimento do controle ao emulador.

Uma thread com um socket UDP em 127.0.0.1. O formato dos pacotes é do
`core/protocolo_dsu.py` (e, com a fonte de cada byte, de
`docs/protocol/o-protocolo-dsu.md`); aqui moram as regras de QUANDO e PARA QUEM
mandar.

**A thread só LÊ.** Quem monta a tabela de slots e resolve o hub de sensores é
uma tarefa do laço do daemon (`daemon/subsystems/dsu.py`), que chama
:meth:`ServidorDsu.publicar` a no máximo 10 Hz; a thread guarda o par
(tabela, hub) por atribuição e nunca chama `_garantir_*` nem toca o IPC. A
tabela é imutável depois de publicada.

Regras (§3.3 da sprint, a fonte é o documento do protocolo):

- Cliente é (IP, porta de origem), nunca o `client_id`.
- A inscrição vem do pedido de dados, vence em 5 s e é limpa a cada 1 s.
- Um pacote por amostra nova, no máximo 250 por segundo por slot e no mínimo um
  a cada 100 ms; amostra `None` rende «conectado» com pacote neutro.
- O timestamp nunca recua por slot; o contador nunca recua por cliente.
- O interruptor dela vale: sensor desligado e peça que mira perdem o giro ou a
  aceleração; o toque segue.
- Antes de parar um slot sai um pacote neutro (o Azahar guarda o último estado,
  e um dedo ficaria «apertado» para sempre).
"""

from __future__ import annotations

import contextlib
import socket
import threading
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any, Final

from hefesto_dualsense4unix.core import protocolo_dsu as dsu
from hefesto_dualsense4unix.core.virtual_motion import REGISTRO
from hefesto_dualsense4unix.daemon.udp_server import RateLimiter
from hefesto_dualsense4unix.utils.logging_config import get_logger

logger = get_logger(__name__)

PORTA_PADRAO: Final = 26760
ENDERECO: Final = "127.0.0.1"

PRAZO_DA_INSCRICAO_S: Final = 5.0
LIMPEZA_S: Final = 1.0
INTERVALO_MINIMO_S: Final = 0.004  # 250 pacotes por segundo por slot
INTERVALO_MAXIMO_S: Final = 0.100  # nunca mais de 100 ms sem pacote
MAXIMO_DE_CLIENTES: Final = 32
SALTO_MAXIMO_DO_RELOGIO_US: Final = 1_000_000
_MASCARA_DO_CONTADOR: Final = 0xFFFFFFFF
PRAZO_DA_THREAD_S: Final = 2.0
_ESPERA_OCIOSA_S: Final = 0.1
_ESPERA_COM_CLIENTE_S: Final = 0.002


@dataclass(frozen=True)
class SlotDsu:
    """UM slot publicado: o controle (`uniq`) e o MAC virtual que ele veste."""

    uniq: str
    mac: str


Inscricao = tuple[int | None, bytes | None]  # (slot, mac); (None, None) = todos


@dataclass
class _Cliente:
    endereco: tuple[str, int]
    inscricoes: dict[Inscricao, float] = field(default_factory=dict)
    contador: int = 0
    enviando: set[int] = field(default_factory=set)


@dataclass
class _EstadoDoSlot:
    uniq: str = ""
    mac: str = ""
    ultimo_envio: float = -1e9
    chave: Any = None
    carimbo_us: int = 0
    epoca: int | None = None
    carimbo_do_hub: int | None = None
    mono_us: int | None = None
    ordem: dict[int, int] = field(default_factory=dict)
    proxima_ordem: int = 0


def _mac_em_bytes(mac: str) -> bytes:
    return dsu.mac_em_bytes(mac)


class ServidorDsu:
    """O servidor DSU de um daemon. `iniciar()` abre a porta; `parar()` fecha."""

    def __init__(
        self,
        *,
        host: str = ENDERECO,
        porta: int = PORTA_PADRAO,
        store: Any = None,
        relogio: Callable[[], float] | None = None,
        limitador: RateLimiter | None = None,
        registro: Any = None,
        id_do_servidor: int | None = None,
    ) -> None:
        self._host = host
        self._porta_pedida = porta
        self._store = store
        self._relogio = relogio or time.monotonic
        self._limitador = limitador or RateLimiter()
        self._registro = registro if registro is not None else REGISTRO
        self._id = (
            id_do_servidor
            if id_do_servidor is not None
            else int(time.time() * 1000) & _MASCARA_DO_CONTADOR
        )
        self._estado: tuple[Mapping[int, SlotDsu], Any] = ({}, None)
        self._clientes: dict[tuple[str, int], _Cliente] = {}
        self._slots: dict[int, _EstadoDoSlot] = {}
        self._sock: socket.socket | None = None
        self._thread: threading.Thread | None = None
        self._parar = threading.Event()
        self._ultima_limpeza = 0.0

    # -- vida ---------------------------------------------------------------

    @property
    def porta(self) -> int:
        """A porta em que o socket escuta (a real, mesmo quando se pediu a 0)."""
        sock = self._sock
        return int(sock.getsockname()[1]) if sock is not None else self._porta_pedida

    def iniciar(self) -> None:
        """Abre o socket e sobe a thread. Levanta `OSError` com a porta ocupada."""
        if self._sock is not None:
            return
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            sock.bind((self._host, self._porta_pedida))
        except OSError:
            sock.close()
            self._bump("dsu.porta_ocupada")
            raise
        sock.settimeout(_ESPERA_OCIOSA_S)
        self._sock = sock
        self._parar.clear()
        self._thread = threading.Thread(target=self._laco, name="hefesto-dsu", daemon=True)
        self._thread.start()
        logger.info("dsu_servidor_iniciado", host=self._host, porta=self.porta)

    def parar(self) -> None:
        """Manda o pacote neutro de cada slot em uso, fecha a porta. Idempotente."""
        sock = self._sock
        if sock is None:
            return
        self._parar.set()
        thread = self._thread
        self._thread = None
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout=PRAZO_DA_THREAD_S)
        try:
            self._neutro_para_todos(sock, self._agora())
        except Exception as exc:
            logger.debug("dsu_neutro_final_falhou", err=str(exc))
        self._sock = None
        with contextlib.suppress(OSError):
            sock.close()
        self._clientes.clear()
        logger.info("dsu_servidor_parado")

    def publicar(self, tabela: Mapping[int, SlotDsu], hub: Any) -> None:
        """Troca (tabela, hub) por atribuição: a thread lê um par sempre inteiro."""
        self._estado = (dict(tabela), hub)

    # -- contadores ----------------------------------------------------------

    def _bump(self, nome: str, delta: int = 1) -> None:
        if self._store is not None:
            try:
                self._store.bump(nome, delta)
            except Exception as exc:
                logger.debug("dsu_contador_falhou", nome=nome, err=str(exc))

    def _agora(self) -> float:
        return float(self._relogio())

    # -- a thread --------------------------------------------------------------

    def _laco(self) -> None:
        sock = self._sock
        assert sock is not None
        while not self._parar.is_set():
            sock.settimeout(_ESPERA_COM_CLIENTE_S if self._clientes else _ESPERA_OCIOSA_S)
            try:
                dados, endereco = sock.recvfrom(2048)
            except TimeoutError:
                dados = b""
                endereco = ("", 0)
            except OSError:
                if self._parar.is_set():
                    return
                dados = b""
                endereco = ("", 0)
            agora = self._agora()
            try:
                if dados:
                    self._atender(sock, dados, endereco, agora)
                self._tique(sock, agora)
            except Exception as exc:  # a thread nunca morre por um pacote
                logger.warning("dsu_laco_falhou", err=str(exc))

    # -- os pedidos ------------------------------------------------------------

    def _atender(
        self, sock: socket.socket, dados: bytes, endereco: tuple[str, int], agora: float
    ) -> None:
        ip, porta = endereco[0], int(endereco[1])
        if not self._limitador.allow(ip, now=agora):
            self._bump("dsu.recusado")
            return
        pedido = dsu.interpretar_pedido(dados)
        if pedido is None:
            self._bump("dsu.recusado")
            return
        tabela, hub = self._estado
        if isinstance(pedido, dsu.PedidoDeVersao):
            sock.sendto(dsu.montar_versao(self._id), endereco)
        elif isinstance(pedido, dsu.PedidoDePortas):
            for slot in pedido.slots:
                sock.sendto(self._porta_do_slot(slot, tabela), endereco)
        else:
            self._inscrever(pedido, (ip, porta), tabela, hub, agora)

    def _porta_do_slot(self, slot: int, tabela: Mapping[int, SlotDsu]) -> bytes:
        publicado = tabela.get(slot)
        if publicado is None:
            return dsu.montar_porta(self._id, slot=slot)
        return dsu.montar_porta(
            self._id,
            slot=slot,
            estado=dsu.ESTADO_CONECTADO,
            modelo=dsu.MODELO_GIRO_COMPLETO,
            conexao=dsu.CONEXAO_USB,
            mac=publicado.mac,
        )

    def _inscrever(
        self,
        pedido: dsu.PedidoDeDados,
        endereco: tuple[str, int],
        tabela: Mapping[int, SlotDsu],
        hub: Any,
        agora: float,
    ) -> None:
        # Cliente é (IP, porta de origem), nunca o client_id: o Azahar usa o
        # mesmo id no cliente, no botão Test e na calibração.
        cliente_id = endereco
        slot = pedido.slot if pedido.por_slot else None
        mac = pedido.mac if pedido.por_mac else None
        if slot is not None and slot >= dsu.SLOTS:
            self._bump("dsu.recusado")
            return
        cliente = self._clientes.get(cliente_id)
        if cliente is None:
            if len(self._clientes) >= MAXIMO_DE_CLIENTES:
                self._bump("dsu.recusado")
                return
            cliente = self._clientes[cliente_id] = _Cliente(endereco)
            self._bump("dsu.clientes")
        cliente.endereco = endereco
        cliente.inscricoes[(slot, mac)] = agora + PRAZO_DA_INSCRICAO_S
        if hub is None:
            return
        for numero in _slots_da_inscricao((slot, mac), tabela):
            try:
                hub.segurar_o_dedo(tabela[numero].uniq)
            except Exception as exc:
                logger.debug("dsu_segurar_o_dedo_falhou", err=str(exc))

    # -- o envio ---------------------------------------------------------------

    def _tique(self, sock: socket.socket, agora: float) -> None:
        tabela, hub = self._estado
        if agora - self._ultima_limpeza >= LIMPEZA_S:
            self._ultima_limpeza = agora
            self._limpar(agora)

        desejados: dict[tuple[str, int], set[int]] = {}
        for cliente_id, cliente in self._clientes.items():
            slots: set[int] = set()
            for chave, vence in cliente.inscricoes.items():
                if vence > agora:
                    slots |= _slots_da_inscricao(chave, tabela)
            desejados[cliente_id] = slots

        for cliente_id, cliente in list(self._clientes.items()):
            parando = cliente.enviando - desejados[cliente_id]
            for numero in sorted(parando):
                self._pacote_final(sock, cliente, numero, tabela, agora)
            cliente.enviando &= desejados[cliente_id]

        em_uso = set().union(*desejados.values()) if desejados else set()
        for numero in sorted(em_uso):
            self._enviar_o_slot(sock, numero, tabela, hub, desejados, agora)

    def _limpar(self, agora: float) -> None:
        for cliente_id in list(self._clientes):
            cliente = self._clientes[cliente_id]
            cliente.inscricoes = {k: v for k, v in cliente.inscricoes.items() if v > agora}
            if not cliente.inscricoes and not cliente.enviando:
                del self._clientes[cliente_id]

    def _enviar_o_slot(
        self,
        sock: socket.socket,
        numero: int,
        tabela: Mapping[int, SlotDsu],
        hub: Any,
        desejados: Mapping[tuple[str, int], set[int]],
        agora: float,
    ) -> None:
        publicado = tabela[numero]
        est = self._slots.setdefault(numero, _EstadoDoSlot())
        decorrido = agora - est.ultimo_envio
        if decorrido < INTERVALO_MINIMO_S:
            return
        if est.uniq != publicado.uniq:
            est.uniq = publicado.uniq
            est.epoca = None
            est.carimbo_do_hub = None
            est.ordem.clear()
        est.mac = publicado.mac
        amostra = None
        if hub is not None:
            try:
                amostra = hub.amostra_do_dsu(publicado.uniq)
            except Exception as exc:
                logger.debug("dsu_amostra_falhou", err=str(exc))
        toques = self._toques(est, amostra)
        chave = (
            (
                amostra.epoca,
                amostra.carimbo_us,
                tuple((t.ativo, t.identidade, t.x, t.y) for t in toques),
            )
            if amostra is not None
            else None
        )
        if chave == est.chave and decorrido < INTERVALO_MAXIMO_S:
            return
        est.chave = chave
        est.ultimo_envio = agora
        carimbo = self._carimbo(est, amostra, agora)
        giro, aceleracao = self._movimento(publicado.uniq, amostra)
        for cliente_id, slots in desejados.items():
            if numero not in slots:
                continue
            cliente = self._clientes.get(cliente_id)
            if cliente is None:
                continue
            cliente.enviando.add(numero)
            self._mandar(
                sock,
                cliente,
                dsu.montar_dados(
                    self._id,
                    slot=numero,
                    mac=publicado.mac,
                    contador=self._contador(cliente, agora),
                    timestamp_us=carimbo,
                    toques=toques,
                    aceleracao=aceleracao,
                    giro=giro,
                ),
            )

    def _mandar(self, sock: socket.socket, cliente: _Cliente, pacote: bytes) -> None:
        try:
            sock.sendto(pacote, cliente.endereco)
            self._bump("dsu.pacotes")
        except OSError:
            # O cliente sumiu (ICMP): a inscrição vence sozinha, e nada mais a fazer.
            cliente.inscricoes.clear()

    @staticmethod
    def _contador(cliente: _Cliente, agora: float) -> int:
        cliente.contador = max(cliente.contador + 1, int(agora * 1000))
        return cliente.contador & _MASCARA_DO_CONTADOR

    def _toques(self, est: _EstadoDoSlot, amostra: Any) -> tuple[dsu.Toque, dsu.Toque]:
        """Os dois contatos mais antigos; o toque 1 é o ativo mais antigo."""
        pontos = [] if amostra is None else list(amostra.toques)
        vivos = {int(p.identidade) for p in pontos}
        for identidade in list(est.ordem):
            if identidade not in vivos:
                del est.ordem[identidade]
        for p in pontos:
            if int(p.identidade) not in est.ordem:
                est.ordem[int(p.identidade)] = est.proxima_ordem
                est.proxima_ordem += 1
        pontos.sort(key=lambda p: est.ordem[int(p.identidade)])
        saida = [
            dsu.Toque(True, int(p.identidade) & 0xFF, _u16(p.x), _u16(p.y)) for p in pontos[:2]
        ]
        while len(saida) < 2:
            saida.append(dsu.TOQUE_INATIVO)
        return saida[0], saida[1]

    def _movimento(
        self, uniq: str, amostra: Any
    ) -> tuple[tuple[float, float, float], tuple[float, float, float]]:
        """(giro, aceleração) já nos sinais do protocolo, com o interruptor dela."""
        zero = (0.0, 0.0, 0.0)
        if amostra is None or not amostra.com_movimento:
            return zero, zero
        giroscopio = acelerometro = True
        mirando = False
        if self._registro is not None:
            try:
                estado = self._registro.estado(uniq)
                giroscopio, acelerometro = bool(estado.giroscopio), bool(estado.acelerometro)
                mirando = bool(self._registro.roteado(uniq))
            except Exception as exc:
                logger.debug("dsu_registro_falhou", err=str(exc))
        gx, gy, gz = amostra.giro
        ax, ay, az = amostra.aceleracao
        giro = (gx, -gy, -gz) if giroscopio and not mirando else zero
        aceleracao = (-ax, -ay, -az) if acelerometro else zero
        return giro, aceleracao

    def _carimbo(self, est: _EstadoDoSlot, amostra: Any, agora: float) -> int:
        """Timestamp em µs que só sobe: o do aparelho quando é confiável, senão o do relógio."""
        mono_us = int(agora * 1_000_000)
        proprio = amostra.carimbo_us if amostra is not None else None
        passo: int | None = None
        if proprio is not None and est.carimbo_do_hub is not None and est.epoca == amostra.epoca:
            delta = proprio - est.carimbo_do_hub
            if 0 < delta <= SALTO_MAXIMO_DO_RELOGIO_US:
                passo = delta
        if passo is None:
            passo = max(1, mono_us - est.mono_us) if est.mono_us is not None else 0
        est.carimbo_us = est.carimbo_us + passo if est.carimbo_us else mono_us
        if proprio is not None:
            est.epoca = amostra.epoca
            est.carimbo_do_hub = proprio
        est.mono_us = mono_us
        return est.carimbo_us

    # -- o pacote neutro ---------------------------------------------------------

    def _pacote_final(
        self,
        sock: socket.socket,
        cliente: _Cliente,
        numero: int,
        tabela: Mapping[int, SlotDsu],
        agora: float,
    ) -> None:
        """O último pacote de um slot que para: neutro, com o contador seguinte."""
        est = self._slots.setdefault(numero, _EstadoDoSlot())
        publicado = tabela.get(numero)
        est.ordem.clear()
        mono_us = int(agora * 1_000_000)
        est.carimbo_us = max(est.carimbo_us + 1, mono_us)
        est.mono_us = mono_us
        est.chave = None
        est.epoca = None
        est.carimbo_do_hub = None
        mac = publicado.mac if publicado is not None else est.mac
        if not mac:
            return
        self._mandar(
            sock,
            cliente,
            dsu.montar_dados(
                self._id,
                slot=numero,
                mac=mac,
                contador=self._contador(cliente, agora),
                timestamp_us=est.carimbo_us,
                conectado=publicado is not None,
                estado=dsu.ESTADO_CONECTADO if publicado is not None else dsu.ESTADO_DESCONECTADO,
            ),
        )

    def _neutro_para_todos(self, sock: socket.socket, agora: float) -> None:
        tabela, _ = self._estado
        for cliente in list(self._clientes.values()):
            for numero in sorted(cliente.enviando):
                self._pacote_final(sock, cliente, numero, tabela, agora)
            cliente.enviando.clear()


def _u16(valor: Any) -> int:
    return max(0, min(0xFFFF, int(valor)))


def _slots_da_inscricao(chave: Inscricao, tabela: Mapping[int, SlotDsu]) -> set[int]:
    """Os slots publicados que esta inscrição alcança (flags: 0 todos, 1 slot, 2 MAC)."""
    slot, mac = chave
    achados: set[int] = set()
    for numero, publicado in tabela.items():
        if slot is not None and numero != slot:
            continue
        if mac is not None and _mac_em_bytes(publicado.mac) != mac:
            continue
        achados.add(numero)
    return achados


__all__ = ["ENDERECO", "PORTA_PADRAO", "ServidorDsu", "SlotDsu"]
