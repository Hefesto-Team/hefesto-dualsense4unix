"""vigia_do_laco.py — o laço do serviço que para se denuncia (O-CONECTAR-ABRE-INTEIRO-TODA-VEZ-01).

A pilha e os números moram em ``$XDG_RUNTIME_DIR``: a parada procurada pode ser o disco que os
guardaria, e o arquivo dos números se lê sem passar pelo IPC que a medida compara.
"""
from __future__ import annotations

import asyncio
import contextlib
import faulthandler
import functools
import json
import os
import re
import sys
import threading
import time
from collections import deque
from collections.abc import Awaitable, Callable
from concurrent.futures import Future, ThreadPoolExecutor
from pathlib import Path
from types import FrameType
from typing import Any, TextIO, TypeVar

from hefesto_dualsense4unix.utils.logging_config import get_logger
from hefesto_dualsense4unix.utils.xdg_paths import runtime_dir

logger = get_logger(__name__)

LIMITE_S = 0.5
PASSO_S = 0.05
VOLTA_LENTA_S = 0.1
ESPERA_LENTA_S = 0.1
RETRATO_S = 1.0
TETO_DAS_PILHAS_BYTES = 256 * 1024
TETO_DE_NOMES = 32
ARQUIVO_DAS_PILHAS = "vigia-do-laco.pilhas"
ARQUIVO_DOS_NUMEROS = "vigia-do-laco.json"
SEM_AMOSTRA = "sem_amostra"
DEMAIS_NOMES = "outras"

T = TypeVar("T")

_RAIZ_DO_PACOTE = str(Path(__file__).resolve().parents[2]) + os.sep
_TAREFA_SEM_NOME = re.compile(r"Task-\d+")

_ativo: VigiaDoLaco | None = None
_linhas_do_pool: deque[dict[str, Any]] = deque(maxlen=64)


def _no_diario(evento: str, **campos: Any) -> None:
    logger.warning(evento, **campos)


def nome_do_chamavel(chamavel: Any) -> str:
    """O nome curto de quem roda: a função de um ``partial``, o método sem o endereço."""
    while isinstance(chamavel, functools.partial):
        chamavel = chamavel.func
    return getattr(chamavel, "__qualname__", None) or type(chamavel).__name__


def _nome_da_tarefa(tarefa: asyncio.Task[Any]) -> str:
    nome = tarefa.get_name()
    if _TAREFA_SEM_NOME.fullmatch(nome) is None:
        return nome
    return getattr(tarefa.get_coro(), "__qualname__", nome)


def _callback_em_curso(quadro: FrameType | None) -> str | None:
    """O callback que o ``Handle._run`` da pilha está rodando: quem preso fora de tarefa."""
    atual = quadro
    while atual is not None:
        codigo = atual.f_code
        if codigo.co_name == "_run" and codigo.co_filename.endswith(f"asyncio{os.sep}events.py"):
            handle = atual.f_locals.get("self")
            return nome_do_chamavel(getattr(handle, "_callback", None))
        atual = atual.f_back
    return None


def _onde(quadro: FrameType | None) -> str:
    """A linha do produto mais funda da pilha; sem nenhuma, o quadro de cima."""
    atual = quadro
    while atual is not None:
        arquivo = atual.f_code.co_filename
        if arquivo.startswith(_RAIZ_DO_PACOTE) and arquivo != __file__:
            relativo = arquivo[len(_RAIZ_DO_PACOTE):]
            return f"{relativo}:{atual.f_lineno} {atual.f_code.co_name}"
        atual = atual.f_back
    if quadro is None:
        return ""
    arquivo = os.path.basename(quadro.f_code.co_filename)
    return f"{arquivo}:{quadro.f_lineno} {quadro.f_code.co_name}"


def quem_prende(laco: asyncio.AbstractEventLoop, fio: int) -> tuple[str, str]:
    """A tarefa (ou o callback) que está no fio do laço agora, e a linha onde está."""
    quadro = sys._current_frames().get(fio)
    tarefa = None
    with contextlib.suppress(Exception):
        tarefa = asyncio.current_task(laco)
    nome = _nome_da_tarefa(tarefa) if tarefa is not None else _callback_em_curso(quadro)
    return nome or SEM_AMOSTRA, _onde(quadro)


class PoolQueDizQuem(ThreadPoolExecutor):
    """O pool que mede a fila de cada pedido e lembra quem ocupava os fios quando ele chegou.

    Pedido nenhum escreve no store: o tique colhe a janela ao fechá-la.
    """

    def __init__(self, max_workers: int, **ajustes: Any) -> None:
        super().__init__(max_workers=max_workers, **ajustes)
        self._vagas = max_workers
        self._ocupantes: dict[int, str] = {}
        self._trava_da_medida = threading.Lock()
        self._pior_da_janela = 0.0
        self._lentas = 0
        self._por_ocupante: dict[str, float] = {}

    def submit(self, fn: Callable[..., T], /, *args: Any, **kwargs: Any) -> Future[T]:
        ocupantes = list(self._ocupantes.values())
        if len(ocupantes) < self._vagas:
            ocupantes = []
        return super().submit(
            self._rodar, nome_do_chamavel(fn), time.monotonic(), ocupantes, fn, *args, **kwargs
        )

    def _medir_a_fila(self, nome: str, espera: float, ocupantes: list[str]) -> None:
        with self._trava_da_medida:
            self._pior_da_janela = max(self._pior_da_janela, espera)
            if espera <= ESPERA_LENTA_S:
                return
            self._lentas += 1
            for ocupante in ocupantes:
                chave = ocupante
                if chave not in self._por_ocupante and len(self._por_ocupante) >= TETO_DE_NOMES:
                    chave = DEMAIS_NOMES
                self._por_ocupante[chave] = max(self._por_ocupante.get(chave, 0.0), espera)
        _linhas_do_pool.append({"ms": round(espera * 1000), "esperou": nome,
                                "ocupado_por": sorted(set(ocupantes))})

    def _rodar(
        self, nome: str, chegou: float, ocupantes: list[str], fn: Callable[..., T],
        *args: Any, **kwargs: Any,
    ) -> T:
        self._medir_a_fila(nome, time.monotonic() - chegou, ocupantes)
        fio = threading.get_ident()
        self._ocupantes[fio] = nome
        try:
            return fn(*args, **kwargs)
        finally:
            self._ocupantes.pop(fio, None)

    def colher_a_janela(self) -> dict[str, int]:
        """A maior fila desde a última colheita e o que vale desde que o serviço subiu."""
        with self._trava_da_medida:
            pior, self._pior_da_janela = self._pior_da_janela, 0.0
            medidas = {"poll.tique.espera_pool_pior_us": round(pior * 1e6),
                       "poll.pool.lentas": self._lentas}
            for nome, espera in self._por_ocupante.items():
                medidas[f"poll.pool.ocupante.{nome}"] = round(espera * 1e6)
        return medidas


class VigiaDoLaco:
    """A batida no laço, o olho num fio, e o relógio de C do ``faulthandler``.

    O olho nunca pede nada ao laço: a amostra de quem prende sai de fora, com o laço preso, e o
    diário e o arquivo dos números saem do fio dele, nunca do fio do laço.
    """

    def __init__(
        self,
        *,
        limite_s: float = LIMITE_S,
        passo_s: float = PASSO_S,
        volta_s: float = VOLTA_LENTA_S,
        avisar: Callable[..., None] = _no_diario,
        saida: TextIO | None = None,
        relogio: Callable[[], float] = time.monotonic,
    ) -> None:
        self.limite_s = float(limite_s)
        self.passo_s = float(passo_s)
        self.volta_s = max(float(volta_s), self.passo_s * 1.5)
        self._avisar = avisar
        self._saida = saida
        self._pilhas: TextIO | None = None
        self._relogio = relogio
        self._batida = relogio()
        self._parado_desde: float | None = None
        self._parar = threading.Event()
        self._fio: threading.Thread | None = None
        self._tarefa: asyncio.Task[None] | None = None
        self._laco: asyncio.AbstractEventLoop | None = None
        self._fio_do_laco: int | None = None
        self._amostra: tuple[float, str, str] | None = None
        self._voltas: deque[tuple[float, float]] = deque(maxlen=64)
        self._lentas = 0
        self._pior_volta_s = 0.0
        self._por_tarefa: dict[str, float] = {}
        self._do_tique: dict[str, int] = {}
        self._numeros: Path | None = None
        self._retrato_em = 0.0


    def _abrir_as_pilhas(self) -> None:
        """A pilha vai a arquivo próprio em memória; sem ele, ao stderr de sempre."""
        if self._saida is not None:
            return
        with contextlib.suppress(OSError):
            pasta = runtime_dir(ensure=True)
            self._pilhas = (pasta / ARQUIVO_DAS_PILHAS).open("a", encoding="utf-8")
            self._saida = self._pilhas


    def _girar_as_pilhas(self) -> None:
        """Com o relógio de C desarmado, a pilha cheia vira ``.1`` e a nova nasce vazia."""
        velho = self._pilhas
        if velho is None:
            return
        with contextlib.suppress(OSError, ValueError):
            if os.fstat(velho.fileno()).st_size < TETO_DAS_PILHAS_BYTES:
                return
            faulthandler.cancel_dump_traceback_later()
            caminho = Path(velho.name)
            os.replace(caminho, caminho.with_name(caminho.name + ".1"))
            self._pilhas = caminho.open("a", encoding="utf-8")
            self._saida = self._pilhas
            velho.close()


    def _armar(self) -> None:
        """Rearma o relógio de C: a pilha sai se a próxima batida não vier no limite."""
        with contextlib.suppress(Exception):
            faulthandler.cancel_dump_traceback_later()
            faulthandler.dump_traceback_later(
                self.limite_s, repeat=False, file=self._saida or sys.stderr)


    async def _bater(self) -> None:
        while not self._parar.is_set():
            agora = self._relogio()
            intervalo = agora - self._batida
            if intervalo > self.volta_s:
                self._voltas.append((self._batida, agora))
            if intervalo > self.limite_s:
                self._girar_as_pilhas()
            self._batida = agora
            self._armar()
            await asyncio.sleep(self.passo_s)


    def olhar(self) -> None:
        """UMA olhada na batida: diz a parada uma vez, e a volta quando a batida vem."""
        agora = self._relogio()
        idade = agora - self._batida
        if idade > self.passo_s * 1.1 and self._laco is not None:
            assert self._fio_do_laco is not None
            self._amostra = (agora, *quem_prende(self._laco, self._fio_do_laco))
        if idade > self.limite_s:
            if self._parado_desde is None:
                self._parado_desde = self._batida
                self._avisar("laco_parado", segundos=round(idade, 1))
            return
        if self._parado_desde is not None:
            parado = self._batida - self._parado_desde
            self._parado_desde = None
            self._avisar("laco_voltou", parado_s=round(parado, 1))


    def _dizer_as_voltas(self) -> None:
        """Cada volta lenta vira uma linha, com a amostra tirada durante a parada."""
        while self._voltas:
            comeco, fim = self._voltas.popleft()
            amostra = self._amostra
            tarefa, onde = SEM_AMOSTRA, ""
            if amostra is not None and comeco <= amostra[0] <= fim:
                _, tarefa, onde = amostra
            intervalo = fim - comeco
            self._lentas += 1
            self._pior_volta_s = max(self._pior_volta_s, intervalo)
            chave = tarefa
            if chave not in self._por_tarefa and len(self._por_tarefa) >= TETO_DE_NOMES:
                chave = DEMAIS_NOMES
            self._por_tarefa[chave] = max(self._por_tarefa.get(chave, 0.0), intervalo)
            self._avisar("laco_lento", ms=round(intervalo * 1000), tarefa=tarefa, onde=onde)


    def _dizer_o_pool(self) -> None:
        while _linhas_do_pool:
            self._avisar("pool_lento", **_linhas_do_pool.popleft())


    def medidas(self) -> dict[str, int]:
        """O que vale desde que o serviço subiu: a janela do tique esquece, e isto não."""
        medidas = {"poll.laco.lentas": self._lentas,
                   "poll.laco.pior_us": round(self._pior_volta_s * 1e6)}
        for tarefa, intervalo in dict(self._por_tarefa).items():
            medidas[f"poll.laco.lenta.{tarefa}"] = round(intervalo * 1e6)
        return medidas


    def publicar(self, do_tique: dict[str, int]) -> None:
        """A janela do tique que o arquivo dos números leva; só troca a referência."""
        self._do_tique = do_tique


    def _escrever_os_numeros(self, agora: float) -> None:
        """O arquivo pequeno que se lê sem IPC, trocado inteiro: quem lê nunca o vê pela metade."""
        if self._numeros is None or agora - self._retrato_em < RETRATO_S:
            return
        self._retrato_em = agora
        retrato = {
            "pid": os.getpid(),
            "instante": round(time.time(), 1),
            "laco_parado_ha_s": round(max(agora - self._batida, 0.0), 3),
            "contadores": {**self._do_tique, **self.medidas()},
        }
        provisorio = self._numeros.with_name(f"{self._numeros.name}.{os.getpid()}")
        try:
            provisorio.write_text(json.dumps(retrato, sort_keys=True), encoding="utf-8")
            os.replace(provisorio, self._numeros)
        except OSError as erro:
            self._numeros = None
            logger.warning("vigia_do_laco_sem_arquivo", err=str(erro))


    def _olhar_sempre(self) -> None:
        while not self._parar.wait(self.passo_s / 2):
            try:
                self.olhar()
                self._dizer_as_voltas()
                self._dizer_o_pool()
                self._escrever_os_numeros(self._relogio())
            except Exception:
                logger.warning("vigia_do_laco_levantou", exc_info=True)


    def ligar(self) -> None:
        """Liga as três peças. Chamado DE DENTRO do laço que o vigia observa."""
        global _ativo
        self._laco = asyncio.get_running_loop()
        self._fio_do_laco = threading.get_ident()
        self._abrir_as_pilhas()
        with contextlib.suppress(OSError):
            self._numeros = runtime_dir(ensure=True) / ARQUIVO_DOS_NUMEROS
        self._batida = self._relogio()
        self._armar()
        self._tarefa = self._laco.create_task(self._bater(), name="vigia_do_laco")
        self._fio = threading.Thread(target=self._olhar_sempre, name="hefesto-vigia-do-laco",
                                     daemon=True)
        self._fio.start()
        _ativo = self

    def desligar(self) -> None:
        """Desliga as três. Idempotente; nunca levanta."""
        global _ativo
        if _ativo is self:
            _ativo = None
        self._parar.set()
        with contextlib.suppress(Exception):
            faulthandler.cancel_dump_traceback_later()
        if self._tarefa is not None:
            self._tarefa.cancel()
        if self._fio is not None and self._fio is not threading.current_thread():
            self._fio.join(timeout=self.passo_s * 2)
        if self._pilhas is not None:
            with contextlib.suppress(OSError):
                self._pilhas.close()
            self._pilhas = None
            self._saida = None


def vigia_ativo() -> VigiaDoLaco | None:
    """O vigia ligado neste processo; o medidor do tique lê daqui ao fechar a janela."""
    return _ativo


async def vigiado(corrotina: Awaitable[T], **ajustes: Any) -> T:
    """Roda ``corrotina`` com a vigia ligada em volta, e a desliga no fim."""
    vigia = VigiaDoLaco(**ajustes)
    vigia.ligar()
    try:
        return await corrotina
    finally:
        vigia.desligar()


__all__ = [
    "ARQUIVO_DAS_PILHAS",
    "ARQUIVO_DOS_NUMEROS",
    "ESPERA_LENTA_S",
    "LIMITE_S",
    "PASSO_S",
    "SEM_AMOSTRA",
    "VOLTA_LENTA_S",
    "PoolQueDizQuem",
    "VigiaDoLaco",
    "nome_do_chamavel",
    "quem_prende",
    "vigia_ativo",
    "vigiado",
]
