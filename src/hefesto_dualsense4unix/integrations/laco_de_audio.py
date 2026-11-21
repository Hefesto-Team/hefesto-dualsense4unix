"""O `pw-loopback` com dono — um nó ligado a outro, por chave, e quem fecha."""

from __future__ import annotations

import atexit
import concurrent.futures
import os
import queue
import re
import shutil
import signal
import subprocess
import threading
from collections.abc import Callable, Sequence
from pathlib import Path

from hefesto_dualsense4unix.integrations.filho_de_som import lancar_filho
from hefesto_dualsense4unix.utils.logging_config import get_logger

logger = get_logger(__name__)

__all__ = ["LATENCIA_MS", "Lacos", "fechar_tudo", "varrer_orfaos"]

LATENCIA_MS = 50

_CARA_DE_ENDERECO = re.compile(r"[0-9a-fA-F]{6,}")

_FAMILIAS: list[Lacos] = []

_PROC = Path("/proc")

_MATAR: Callable[[int, int], None] = os.kill


class _Lancador:
    """O fio de vida longa de onde sai todo `pw-loopback`.

    O ``PR_SET_PDEATHSIG`` do ``lancar_filho`` dispara quando morre o FIO que fez o
    ``fork``, não o processo. Os gestos da janela correm cada um num fio que acaba com o
    gesto, e o laço lançado ali morreria junto: todo laço nasce neste fio, que só acaba
    com o processo, e o kernel recolhe os laços quando ele cai por qualquer meio.
    """

    def __init__(self) -> None:
        self._pedidos: queue.Queue[
            tuple[Sequence[str], concurrent.futures.Future[subprocess.Popen[bytes]]]
        ] = queue.Queue()
        self._trava = threading.Lock()
        self._fio: threading.Thread | None = None

    def lancar(self, argv: Sequence[str]) -> subprocess.Popen[bytes]:
        """Lança `argv` preso ao processo. Levanta o que o ``Popen`` levantar."""
        self._garantir_o_fio()
        futuro: concurrent.futures.Future[subprocess.Popen[bytes]] = concurrent.futures.Future()
        self._pedidos.put((argv, futuro))
        return futuro.result()

    def _garantir_o_fio(self) -> None:
        with self._trava:
            if self._fio is None or not self._fio.is_alive():
                self._fio = threading.Thread(
                    target=self._servir, name="laco-de-audio-lancador", daemon=True)
                self._fio.start()

    def _servir(self) -> None:
        while True:
            argv, futuro = self._pedidos.get()
            try:
                futuro.set_result(lancar_filho(
                    argv, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))
            except Exception as erro:
                futuro.set_exception(erro)


_LANCADOR = _Lancador()


def _ler_o_processo(proc: Path) -> tuple[list[str], int, str, int] | None:
    """`(argv, pai, início, dono)` do processo em `proc`, ou `None` se ele sumiu ou não se lê."""
    try:
        argv = (proc / "cmdline").read_bytes().decode("utf-8", "replace").split("\0")
        stat = (proc / "stat").read_text(encoding="utf-8", errors="replace")
        dono = proc.stat().st_uid
    except OSError as erro:
        logger.debug("laco_processo_nao_se_le", pid=proc.name, err=str(erro))
        return None
    campos = stat.rpartition(")")[2].split()
    if len(campos) < 20:
        return None
    return argv, int(campos[1]), campos[19], dono


def _e_do_hefesto(pai: int, raiz: Path) -> bool:
    """O pai é este processo ou outro vivo do Hefesto (janela ou serviço)?"""
    if pai == os.getpid():
        return True
    lido = _ler_o_processo(raiz / str(pai)) if pai > 1 else None
    return lido is not None and "hefesto" in " ".join(lido[0]).lower()


def varrer_orfaos(
    familia: str,
    *,
    raiz: Path | None = None,
    uid: int | None = None,
    matar: Callable[[int, int], None] | None = None,
) -> list[int]:
    """Recolhe os `pw-loopback` desta família que ficaram sem o pai do Hefesto.

    Só cai o processo do mesmo usuário, de nome ``pw-loopback`` e ``--name hefesto-<família>-…``,
    cujo pai não é mais processo do Hefesto, e o PID é lido duas vezes antes do sinal. O PID 1,
    este processo e o pai dele nunca levam sinal. ``raiz`` e ``matar`` vazios valem o ``/proc`` e o
    ``os.kill`` de produção, lidos na hora da varredura. Devolve os PIDs recolhidos.
    """
    raiz = _PROC if raiz is None else raiz
    matar = _MATAR if matar is None else matar
    dono = os.getuid() if uid is None else uid
    prefixo = f"hefesto-{familia}-"
    intocaveis = {1, os.getpid(), os.getppid()}
    recolhidos: list[int] = []
    try:
        candidatos = [p for p in raiz.iterdir() if p.name.isdigit()]
    except OSError as erro:
        logger.debug("laco_proc_nao_se_lista", err=str(erro))
        return recolhidos
    for proc in candidatos:
        if int(proc.name) in intocaveis:
            continue
        lido = _ler_o_processo(proc)
        if lido is None or lido[3] != dono or not _e_um_laco_da_familia(lido[0], prefixo):
            continue
        if _e_do_hefesto(lido[1], raiz) or _ler_o_processo(proc) != lido:
            continue
        pid = int(proc.name)
        try:
            matar(pid, signal.SIGTERM)
        except OSError as erro:
            logger.debug("laco_orfao_nao_caiu", familia=familia, pid=pid, err=str(erro))
            continue
        recolhidos.append(pid)
        logger.info("laco_orfao_recolhido", familia=familia, pid=pid)
    return recolhidos


def _e_um_laco_da_familia(argv: list[str], prefixo: str) -> bool:
    if not argv or Path(argv[0]).name != "pw-loopback" or "--name" not in argv:
        return False
    indice = argv.index("--name") + 1
    return indice < len(argv) and argv[indice].startswith(prefixo)


class Lacos:
    """As laçadas de UMA família, guardadas por chave (normalmente o `uniq`)."""

    def __init__(
        self,
        familia: str,
        *,
        raiz: Path | None = None,
        matar: Callable[[int, int], None] | None = None,
    ) -> None:
        """Nasce sem varrer: guarda a `raiz` do `/proc` e o `matar` da varredura de quem a cria.

        Criar a família no nível do módulo é o caso comum; a varredura de órfãos corre uma vez, no
        primeiro uso da família pelo processo (:meth:`recolher_orfaos`), nunca no import.
        """
        self.familia = familia
        self._vivos: dict[str, subprocess.Popen[bytes]] = {}
        self._pedidos: dict[str, dict[str, object]] = {}
        self._trava = threading.Lock()
        self._raiz = raiz
        self._matar = matar
        self._varrida = False
        self._trava_da_varredura = threading.Lock()
        _FAMILIAS.append(self)

    def recolher_orfaos(self) -> list[int]:
        """Recolhe os laços órfãos desta família agora, com a `raiz` e o `matar` de quem a criou."""
        with self._trava_da_varredura:
            try:
                return varrer_orfaos(self.familia, raiz=self._raiz, matar=self._matar)
            finally:
                self._varrida = True

    def _recolher_no_primeiro_contato(self) -> None:
        """Varre uma vez; o fio que chega durante a varredura aguarda o fim da varredura."""
        if self._varrida:
            return
        with self._trava_da_varredura:
            if self._varrida:
                return
            try:
                varrer_orfaos(self.familia, raiz=self._raiz, matar=self._matar)
            finally:
                self._varrida = True

    def esta_ligado(self, chave: str) -> bool:
        """Esta laçada está de pé AGORA? Pergunta ao processo, não à lembrança."""
        if not chave:
            return False
        self._recolher_no_primeiro_contato()
        with self._trava:
            proc = self._vivos.get(chave)
            if proc is None:
                return False
            if proc.poll() is None:
                return True
            self._vivos.pop(chave, None)
            return False

    def ligados(self) -> tuple[str, ...]:
        """As chaves com laçada de pé, em ordem ESTÁVEL."""
        self._recolher_no_primeiro_contato()
        with self._trava:
            vivos = [c for c, p in self._vivos.items() if p.poll() is None]
            for morto in [c for c in self._vivos if c not in vivos]:
                self._vivos.pop(morto, None)
        return tuple(sorted(vivos))

    def ligar(
        self,
        chave: str,
        *,
        captura: str,
        destino: str = "",
        canais: int = 1,
        mapa: str = "[ MONO ]",
    ) -> bool:
        """Abre a laçada. `True` = de pé."""
        if not chave or not captura:
            return False
        if _CARA_DE_ENDERECO.search(chave):
            logger.warning("laco_recusa_chave_com_endereco", familia=self.familia)
            return False
        if self.esta_ligado(chave):
            return True
        if shutil.which("pw-loopback") is None:
            logger.info("laco_sem_pw_loopback", familia=self.familia, chave=chave)
            return False
        argv = [
            "pw-loopback",
            "--capture", captura,
            "--latency", str(LATENCIA_MS),
            "--channels", str(canais),
            "--channel-map", mapa,
            "--name", f"hefesto-{self.familia}-{chave}",
        ]
        if destino:
            argv += ["--playback", destino]
        try:
            proc = _LANCADOR.lancar(argv)
        except (OSError, subprocess.SubprocessError) as exc:
            logger.info(
                "laco_nao_subiu", familia=self.familia, chave=chave, err=str(exc))
            return False
        with self._trava:
            self._vivos[chave] = proc
            self._pedidos[chave] = {
                "captura": captura, "destino": destino, "canais": canais, "mapa": mapa}
        logger.info(
            "laco_ligado", familia=self.familia, chave=chave,
            captura=captura, destino=destino or "(padrão)")
        return True

    def desligar(self, chave: str) -> bool:
        """Fecha a laçada. `True` = havia uma e a laçada morreu."""
        with self._trava:
            proc = self._vivos.pop(chave, None)
            self._pedidos.pop(chave, None)
        if proc is None:
            return False
        try:
            proc.kill()
            proc.wait(timeout=2)
        except (OSError, subprocess.SubprocessError):
            pass
        logger.info("laco_desligado", familia=self.familia, chave=chave)
        return True

    def destino_de(self, chave: str) -> str | None:
        """O destino pedido para a laçada de pé; ``None`` quando não há laçada."""
        if not self.esta_ligado(chave):
            return None
        with self._trava:
            pedido = self._pedidos.get(chave)
        return str(pedido.get("destino") or "") if pedido is not None else None

    def seguir(self, chave: str, destino: str) -> bool:
        """A laçada de pé passa a tocar em ``destino``. ``True`` = trocou agora."""
        atual = self.destino_de(chave)
        if atual is None or atual == destino:
            return False
        with self._trava:
            pedido = dict(self._pedidos.get(chave) or {})
        if not pedido or not self.desligar(chave):
            return False
        pedido["destino"] = destino
        return self.ligar(chave, **pedido)  # type: ignore[arg-type]

    def alternar(self, chave: str, *, captura: str, **kw: object) -> bool:
        """Liga se estava desligada, desliga se estava ligada. Devolve o estado NOVO."""
        if self.esta_ligado(chave):
            self.desligar(chave)
            return False
        return self.ligar(chave, captura=captura, **kw)  # type: ignore[arg-type]

    def desligar_todos(self) -> int:
        """Fecha tudo desta família e devolve quantas eram."""
        return sum(1 for chave in list(self._vivos) if self.desligar(chave))


def fechar_tudo() -> int:
    """Fecha as laçadas de TODAS as famílias. Registrado no `atexit` abaixo."""
    return sum(familia.desligar_todos() for familia in _FAMILIAS)


atexit.register(fechar_tudo)
