"""receptor_sem_fio.py — o receptor 2.4G de teclado e mouse: reconhecer, ver sofrer, achar a faixa.

O-RECEPTOR-2-4G-SE-RECONHECE-E-DIZ-QUANDO-SOFRE-01 (04/10/2026). Ela: *«o meu teclado e mouse
quando tá super conectado desse jeito é o primeiro a pedir ajuda; ele se digita sozinho e escreve
errado agora»* e *«pensando no user universal. uma forma na origem do problema»*.

NINGUÉM LÊ O CANAL DESTES RECEPTORES. Nenhum driver, comando HID documentado ou projeto lê a
frequência de um dongle de mouse genérico (pesquisa 01 e 04 do conjunto); há canais vendor sem
documentação, e escrever neles às cegas é risco. Por isso há três coisas, todas só de leitura:

* **Reconhecer** (:func:`e_receptor`): as duas interfaces HID de arranque (teclado ``030101`` e
  mouse ``030102``) no MESMO aparelho USB, full-speed, com «2.4G», «Wireless» ou «Receiver» no
  nome. Qualquer marca; um mouse com fio tem uma interface só.
* **Ver sofrer** (:class:`ContadorDaSaude`, :class:`MonitorDosReceptores`): o evdev, só leitura e
  sem ``grab``. Conta DURAÇÕES: quantas vezes uma tecla repetiu (autorepeat) por mais de
  :data:`PRESA_APOS_S` (o «digita sozinho»; o «solta» que encerra a repetição não a desconta), e quantos buracos de movimento do mouse
  passaram do que o próprio mouse entrega. Nunca o código da tecla nem o texto: é um app de
  acessibilidade, não um registrador de teclas.
* **Achar a faixa por eliminação** (:class:`Descoberta`): o rádio dele não se lê, mas os adaptadores
  Bluetooth evitam os canais em que ele fala. Com ele fora e depois dentro, a diferença dos canais
  evitados é a banda dele. Medida, nunca causa confirmada.

Nada aqui conhece a bancada de ninguém: o ``vid:pid`` entra por argumento.
"""

from __future__ import annotations

import contextlib
import os
import re
import statistics
import struct
import threading
import time
from collections import deque
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from hefesto_dualsense4unix.utils.logging_config import get_logger

logger = get_logger(__name__)

ESPECIE = "Receptor 2.4G"

#: ``classe + subclasse + protocolo`` de uma interface HID de arranque.
TECLADO_DE_ARRANQUE = "030101"
MOUSE_DE_ARRANQUE = "030102"
#: full-speed (USB 1.1), o que estes receptores falam; um aparelho mais rápido não é um.
VELOCIDADE_MAXIMA_MBPS = 12.0
_NOME_DE_RECEPTOR = re.compile(r"2[.,]4\s*g|wireless|receiver", re.IGNORECASE)

#: Uma tecla que repete (autorepeat) por mais disto é «presa», solte ela depois ou não.
PRESA_APOS_S = 1.0
#: A janela de contagem: a última hora.
JANELA_S = 3600
#: Um buraco entre duas posições do mouse: no mínimo isto (o mouse de 1000 Hz entrega a cada 1 ms)…
BURACO_MINIMO_S = 0.008
#: …e, para o mouse que entrega mais devagar, quatro vezes o intervalo normal dele.
BURACO_EM_INTERVALOS = 4.0
#: acima disto não é buraco, é a mão parada: HID só manda report quando algo muda.
BURACO_MAXIMO_S = 0.1
#: quantas posições seguidas fazem um «movimento contínuo».
CORRIDA_MINIMA = 16
#: um mouse que entrega mais devagar que isto (50 Hz) não tem movimento contínuo para medir.
INTERVALO_MAXIMO_DA_CORRIDA_S = 0.02
#: mesma posição do mesmo report: o evdev os carimba com o mesmo instante.
MESMO_REPORT_S = 0.0005
#: quanto o ``parar`` espera a thread do monitor voltar.
ESPERA_DO_FIO_S = 2.0
#: teto de memória do que se conta (um enlace morrendo faz milhares por hora).
TETO_DA_CONTAGEM = 5000

# ``struct input_event`` (``linux/input.h``): ``tv_sec``, ``tv_usec``, ``type``, ``code``,
# ``value``.
_EVENTO = struct.Struct("@llHHi")
EV_KEY = 0x01
EV_REL = 0x02
REL_X = 0x00
REL_Y = 0x01
#: abaixo disto o código é tecla de teclado; dali em diante são botões (de mouse, de controle).
FIM_DAS_TECLAS = 0x100

#: a identidade de um aparelho na casa: ``usb:vid:pid`` (a mesma das quedas do Wi-Fi).
CHAVE = "usb:{vid}:{pid}"


def chave_do_aparelho(vid: str, pid: str) -> str:
    """``usb:25a7:fa07`` — o que sobrevive a trocar de porta e de nó."""
    return CHAVE.format(vid=vid.lower(), pid=pid.lower())


def e_receptor(
    interfaces: Iterable[str], velocidade_mbps: float, textos: Iterable[str]
) -> bool:
    """O aparelho é um receptor 2.4G de teclado e mouse? Só pelo que o kernel publica.

    ``interfaces`` são as triplas ``"030101"`` de TODAS as interfaces do aparelho; ``textos`` são o
    ``product`` e o ``manufacturer``. Sem as duas interfaces de arranque, ou mais rápido que
    full-speed, ou sem a palavra, não é: a resposta curta é a honesta.
    """
    triplas = set(interfaces)
    if not {TECLADO_DE_ARRANQUE, MOUSE_DE_ARRANQUE} <= triplas:
        return False
    if not 0 < velocidade_mbps <= VELOCIDADE_MAXIMA_MBPS:
        return False
    return any(_NOME_DE_RECEPTOR.search(t or "") for t in textos)


# ------------------------------------------------------------------------------------- a saúde


@dataclass(frozen=True)
class Saude:
    """O que se contou na última hora. ``lendo`` é falso quando ninguém abriu o evdev dele."""

    teclas_presas: int = 0
    buracos: int = 0
    janela_s: int = JANELA_S
    lendo: bool = False

    def publicar(self) -> dict[str, Any]:
        return {"teclas_presas": self.teclas_presas, "buracos": self.buracos,
                "janela_s": self.janela_s, "lendo": self.lendo}


@dataclass
class _Aperto:
    """Uma tecla apertada agora. Só o instante: o código vira um token sem volta."""

    inicio: float
    contada: bool = False


class ContadorDaSaude:
    """Conta teclas presas e buracos de movimento de UM receptor; nunca guarda tecla.

    A identidade de uma tecla é um token de ``hash((sal, código))`` com sal sorteado por processo:
    serve para casar o «solta» com o «aperta» enquanto ela está apertada, e não devolve o código
    nem a ordem em que se digitou. O que sai (:meth:`saude`) são duas contagens.
    """

    def __init__(self, sal: int | None = None) -> None:
        self._sal = int.from_bytes(os.urandom(8), "big") if sal is None else sal
        self._apertadas: dict[int, _Aperto] = {}
        self._presas: deque[float] = deque(maxlen=TETO_DA_CONTAGEM)
        self._buracos: deque[float] = deque(maxlen=TETO_DA_CONTAGEM)
        self._intervalos: deque[float] = deque(maxlen=CORRIDA_MINIMA * 2)
        self._ultimo_movimento: float | None = None

    def tecla(self, valor: int, codigo: int, t: float) -> None:
        """Um evento de tecla: ``valor`` 1 aperta, 2 repete, 0 solta."""
        token = hash((self._sal, codigo))
        if valor == 1:
            self._apertadas[token] = _Aperto(inicio=t)
        elif valor == 2:
            aperto = self._apertadas.get(token)
            if aperto is not None and not aperto.contada \
                    and t - aperto.inicio >= PRESA_APOS_S:
                aperto.contada = True
                self._presas.append(t)
        elif valor == 0:
            # O «solta» NÃO desfaz a conta: o «digita sozinho» num teclado HID termina sempre
            # num solta (o rádio volta e entrega o key up que perdeu), então descontá-lo faria a
            # métrica tender a zero justamente no sintoma. A tecla presa mede-se pela REPETIÇÃO
            # que passou de PRESA_APOS_S; o solta só encerra o acompanhamento dela.
            self._apertadas.pop(token, None)

    def movimento(self, t: float) -> None:
        """Uma posição do mouse (``REL_X``/``REL_Y``) no instante ``t``."""
        antes = self._ultimo_movimento
        self._ultimo_movimento = t
        if antes is None:
            return
        dt = t - antes
        if dt < MESMO_REPORT_S:
            return
        if dt > BURACO_MAXIMO_S:
            self._intervalos.clear()
            return
        normal = statistics.median(self._intervalos) if len(self._intervalos) >= CORRIDA_MINIMA \
            else None
        if normal is not None and normal <= INTERVALO_MAXIMO_DA_CORRIDA_S \
                and dt >= max(BURACO_MINIMO_S, BURACO_EM_INTERVALOS * normal):
            self._buracos.append(t)
            return
        self._intervalos.append(dt)

    def saude(self, agora: float, *, lendo: bool = True) -> Saude:
        corte = agora - JANELA_S
        for fila in (self._presas, self._buracos):
            while fila and fila[0] < corte:
                fila.popleft()
        for token in [k for k, a in self._apertadas.items() if a.inicio < corte]:
            del self._apertadas[token]
        return Saude(teclas_presas=len(self._presas), buracos=len(self._buracos), lendo=lendo)


def _abrir_so_para_ler(caminho: str) -> int:
    """``open(O_RDONLY)``: ler o evdev não o toma de ninguém (``grab`` é outro ``ioctl``)."""
    return os.open(caminho, os.O_RDONLY | os.O_NONBLOCK | os.O_CLOEXEC)


def eventos_do_fluxo(dados: bytes) -> list[tuple[int, int, int, float]]:
    """``(tipo, código, valor, instante)`` de cada ``input_event`` inteiro de ``dados``."""
    saida = []
    for desde in range(0, len(dados) - _EVENTO.size + 1, _EVENTO.size):
        seg, useg, tipo, codigo, valor = _EVENTO.unpack_from(dados, desde)
        saida.append((tipo, codigo, valor, seg + useg / 1_000_000))
    return saida


def empacotar_evento(tipo: int, codigo: int, valor: int, instante: float) -> bytes:
    """O inverso de :func:`eventos_do_fluxo` — a forma que a régua alimenta o monitor."""
    seg = int(instante)
    return _EVENTO.pack(seg, round((instante - seg) * 1_000_000), tipo, codigo, valor)


class MonitorDosReceptores:
    """Lê o evdev dos receptores (só leitura) e mantém um :class:`ContadorDaSaude` por ``vid:pid``.

    Roda em UMA thread do daemon, longe do fio da janela. ``varrer`` devolve
    ``{usb:vid:pid: (caminho do evento, …)}`` do que o censo reconheceu; os nós que somem ou
    param de responder são fechados. Sem permissão para abrir o nó, o receptor fica com
    ``lendo`` falso — a tela diz o que sabe, e o que não sabe não vira número.
    """

    def __init__(
        self,
        varrer: Callable[[], Mapping[str, Sequence[str]]],
        *,
        abrir: Callable[[str], int] = _abrir_so_para_ler,
        ler: Callable[[int], bytes] = lambda fd: os.read(fd, _EVENTO.size * 64),
        fechar: Callable[[int], None] = os.close,
        relogio: Callable[[], float] = time.time,
        varredura_s: float = 10.0,
    ) -> None:
        self._varrer = varrer
        self._abrir, self._ler, self._fechar = abrir, ler, fechar
        self._relogio = relogio
        self._varredura_s = varredura_s
        self._contadores: dict[str, ContadorDaSaude] = {}
        self._abertos: dict[int, tuple[str, str]] = {}
        self._lidos_em = float("-inf")
        self._trava = threading.Lock()
        self._parar = threading.Event()
        self._fio: threading.Thread | None = None

    def passo(self, prazo_s: float = 0.25) -> None:
        """Uma volta: refaz a varredura se venceu, espera os nós e conta o que chegou."""
        from hefesto_dualsense4unix.utils.espera import prontos_para_ler

        agora = time.monotonic()
        if agora - self._lidos_em >= self._varredura_s:
            self._lidos_em = agora
            self._reabrir()
        if not self._abertos:
            self._parar.wait(prazo_s)
            return
        try:
            prontos = prontos_para_ler(list(self._abertos), prazo_s)
        except (OSError, ValueError):
            self._lidos_em = float("-inf")
            return
        for fd in prontos:
            self._drenar(fd)

    def _reabrir(self) -> None:
        try:
            alvo = {c: tuple(caminhos) for c, caminhos in self._varrer().items()}
        except Exception:  # pragma: no cover - a varredura nunca derruba o monitor
            logger.debug("receptor_varredura_falhou", exc_info=True)
            return
        queremos = {(c, p) for c, ps in alvo.items() for p in ps}
        for fd, quem in list(self._abertos.items()):
            if quem not in queremos:
                self._soltar(fd)
        ja = set(self._abertos.values())
        for chave, caminho in sorted(queremos - ja):
            with self._trava:
                self._contadores.setdefault(chave, ContadorDaSaude())
            try:
                fd = self._abrir(caminho)
            except OSError as erro:
                # sem o grupo `input` o receptor fica publicado com `lendo` falso
                logger.debug("receptor_nao_abriu", erro=type(erro).__name__)
                continue
            self._abertos[fd] = (chave, caminho)
        with self._trava:
            for chave in [c for c in self._contadores if c not in alvo]:
                del self._contadores[chave]

    def _soltar(self, fd: int) -> None:
        self._abertos.pop(fd, None)
        with contextlib.suppress(OSError):
            self._fechar(fd)

    def _drenar(self, fd: int) -> None:
        chave = self._abertos.get(fd, ("", ""))[0]
        try:
            dados = self._ler(fd)
        except OSError as erro:
            if not isinstance(erro, BlockingIOError):
                self._soltar(fd)  # o nó sumiu (o receptor saiu da porta)
            return
        if not dados:
            self._soltar(fd)
            return
        with self._trava:
            contador = self._contadores.get(chave)
            if contador is None:
                return
            for tipo, codigo, valor, t in eventos_do_fluxo(dados):
                if tipo == EV_KEY and codigo < FIM_DAS_TECLAS:
                    contador.tecla(valor, codigo, t)
                elif tipo == EV_REL and codigo in (REL_X, REL_Y):
                    contador.movimento(t)

    def publicar(self) -> dict[str, dict[str, Any]]:
        """``{usb:vid:pid: {...}}`` agora; o que não tem nó aberto sai com ``lendo`` falso."""
        agora = self._relogio()
        abertos = {chave for chave, _p in self._abertos.values()}
        with self._trava:
            return {c: k.saude(agora, lendo=c in abertos).publicar()
                    for c, k in self._contadores.items()}

    def iniciar(self) -> None:
        if self._fio is not None and self._fio.is_alive():
            return
        self._parar.clear()
        self._fio = threading.Thread(target=self._laco, name="receptores-2-4g", daemon=True)
        self._fio.start()

    def _laco(self) -> None:
        while not self._parar.is_set():
            try:
                self.passo()
            except Exception:  # pragma: no cover - defensivo: o monitor nunca derruba o daemon
                logger.debug("receptor_passo_falhou", exc_info=True)
                self._parar.wait(1.0)

    def parar(self) -> None:
        self._parar.set()
        if self._fio is not None:
            self._fio.join(timeout=ESPERA_DO_FIO_S)
        for fd in list(self._abertos):
            self._soltar(fd)


# --------------------------------------------------------------- a palavra do selo, para a tela

#: a partir de quantas teclas presas na hora o selo fica «sofrendo» (abaixo, «apertada»).
PRESAS_QUE_SOFREM = 3
#: a partir de quantos buracos na hora o mouse «engasga».
BURACOS_QUE_SOFREM = 20


def selo_da_saude(saude: Mapping[str, Any] | None, tipo: str) -> tuple[str, str, str] | None:
    """``(nível, texto, quando)`` do que se contou, ou ``None`` quando ninguém leu.

    ``tipo`` é ``teclado`` ou ``mouse``: o teclado fala em teclas presas, o mouse em buracos.
    Sem leitura não há selo — «sem falhas» sobre o que ninguém mediu seria dizer o que não se sabe.
    """
    if not isinstance(saude, Mapping) or not saude.get("lendo"):
        return None
    janela = int(saude.get("janela_s") or JANELA_S)
    quando = "em 1 h" if janela == JANELA_S else f"em {round(janela / 60)} min"
    if tipo == "mouse":
        n = int(saude.get("buracos") or 0)
        if n == 0:
            return ("boa", "sem falhas", "")
        nivel = "sofrendo" if n >= BURACOS_QUE_SOFREM else "apertada"
        return (nivel, f"engasgou {n}×" if n > 1 else "engasgou 1×", quando)  # noqa: RUF001
    n = int(saude.get("teclas_presas") or 0)
    if n == 0:
        return ("boa", "sem falhas", "")
    nivel = "sofrendo" if n >= PRESAS_QUE_SOFREM else "apertada"
    return (nivel, f"{n} {'tecla presa' if n == 1 else 'teclas presas'}", quando)


# ------------------------------------------------------------------- achar a faixa dele


#: os passos do gesto guiado, na ordem.
PASSO_TIRE = "tire"
PASSO_MEDINDO_SEM = "medindo-sem"
PASSO_PONHA = "ponha"
PASSO_MEDINDO_COM = "medindo-com"
PASSO_ACHOU = "achou"
PASSO_NADA = "nada"
#: quanto o adaptador leva para reaprender os canais depois de o receptor sair ou voltar: o
#: daemon relê o AFH a cada 10 s, e o rádio reclassifica em alguns segundos.
ESPERA_DA_MEDIDA_S = 25.0
#: a banda mais estreita que vale: uma sobra de um canal só é o AFH mexendo sozinho.
CANAIS_MINIMOS_DA_BANDA = 3
CANAIS_DA_REGUA = 79


def banda_por_eliminacao(
    sem: Mapping[str, Iterable[int] | None], com: Mapping[str, Iterable[int] | None]
) -> tuple[int, int] | None:
    """``(ini, fim)`` dos canais que os adaptadores passaram a EVITAR com o receptor no lugar.

    ``sem`` e ``com`` são ``{adaptador: canais evitados}`` (``None`` = esse adaptador não mede).
    A banda é a maior sequência contínua de canais evitados só no «com», somando todos os
    adaptadores que mediram nos dois momentos. Menos de :data:`CANAIS_MINIMOS_DA_BANDA` seguidos é
    ruído do próprio AFH: devolve ``None`` — «não achei» é resposta.
    """
    novos: set[int] = set()
    for adaptador, evitados_com in com.items():
        antes = sem.get(adaptador)
        if antes is None or evitados_com is None:
            continue
        novos |= set(evitados_com) - set(antes)
    melhor: tuple[int, int] | None = None
    atual: list[int] = []
    for canal in [*sorted(c for c in novos if 0 <= c < CANAIS_DA_REGUA), CANAIS_DA_REGUA + 1]:
        if atual and canal != atual[-1] + 1:
            if len(atual) >= CANAIS_MINIMOS_DA_BANDA and (
                    melhor is None or len(atual) > melhor[1] - melhor[0]):
                melhor = (atual[0], atual[-1] + 1)
            atual = []
        atual.append(canal)
    return melhor


@dataclass
class Descoberta:
    """O gesto guiado «Descobrir a faixa», de UM receptor por vez, sem tocar em nada.

    ``tire`` → (o gesto) → ``medindo-sem`` → ``ponha`` → (o gesto) → ``medindo-com`` → ``achou`` ou
    ``nada``. Quem chama entrega ``evitados()`` (o que os adaptadores evitam AGORA, vindo do
    daemon) e o relógio; o tique chama :meth:`andar`, e o gesto, :meth:`avancar`.
    """

    chave: str = ""
    passo: str = ""
    desde: float = 0.0
    sem: dict[str, tuple[int, ...] | None] = field(default_factory=dict)
    com: dict[str, tuple[int, ...] | None] = field(default_factory=dict)
    banda: tuple[int, int] | None = None
    #: a banda achada já foi para o disco (o tique guarda uma vez só)
    guardada: bool = False

    @property
    def ativa(self) -> bool:
        return bool(self.chave) and self.passo not in ("", PASSO_ACHOU, PASSO_NADA)

    def iniciar(self, chave: str, agora: float) -> None:
        self.chave, self.passo, self.desde = chave, PASSO_TIRE, agora
        self.sem, self.com, self.banda, self.guardada = {}, {}, None, False

    def avancar(self, agora: float) -> None:
        """O gesto dela: «já tirei» ou «já pus». Nos passos de medida e nos finais não faz nada."""
        if self.passo == PASSO_TIRE:
            self.passo, self.desde = PASSO_MEDINDO_SEM, agora
        elif self.passo == PASSO_PONHA:
            self.passo, self.desde = PASSO_MEDINDO_COM, agora

    def andar(
        self, agora: float, evitados: Callable[[], Mapping[str, Iterable[int] | None]]
    ) -> None:
        """O tique: fecha a medida quando a espera passou."""
        if self.passo not in (PASSO_MEDINDO_SEM, PASSO_MEDINDO_COM):
            return
        if agora - self.desde < ESPERA_DA_MEDIDA_S:
            return
        lido = {a: (None if v is None else tuple(sorted(v))) for a, v in evitados().items()}
        if self.passo == PASSO_MEDINDO_SEM:
            self.sem = lido
            self.passo, self.desde = PASSO_PONHA, agora
            return
        self.com = lido
        self.banda = banda_por_eliminacao(self.sem, self.com)
        self.passo, self.desde = (PASSO_ACHOU if self.banda else PASSO_NADA), agora

    def cancelar(self) -> None:
        self.chave, self.passo, self.banda = "", "", None


#: o texto de cada passo (o que a tela diz) e o rótulo do botão que o faz andar.
FRASE_DO_PASSO = {
    PASSO_TIRE: "Tire o receptor da porta",
    PASSO_MEDINDO_SEM: "Medindo sem ele…",
    PASSO_PONHA: "Ponha o receptor de volta",
    PASSO_MEDINDO_COM: "Medindo com ele…",
    PASSO_NADA: "Não achei a faixa dele",
}
BOTAO_DO_PASSO = {PASSO_TIRE: "Já tirei", PASSO_PONHA: "Já pus"}
BOTAO_DE_COMECAR = "Descobrir"


__all__ = [
    "BOTAO_DE_COMECAR",
    "BOTAO_DO_PASSO",
    "BURACOS_QUE_SOFREM",
    "ESPECIE",
    "FRASE_DO_PASSO",
    "JANELA_S",
    "PASSO_ACHOU",
    "PASSO_MEDINDO_COM",
    "PASSO_MEDINDO_SEM",
    "PASSO_NADA",
    "PASSO_PONHA",
    "PASSO_TIRE",
    "PRESAS_QUE_SOFREM",
    "ContadorDaSaude",
    "Descoberta",
    "MonitorDosReceptores",
    "Saude",
    "banda_por_eliminacao",
    "chave_do_aparelho",
    "e_receptor",
    "empacotar_evento",
    "eventos_do_fluxo",
    "selo_da_saude",
]
