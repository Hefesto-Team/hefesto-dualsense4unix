"""O `pw-loopback` com dono — um nó ligado a outro, por chave, e quem fecha."""

from __future__ import annotations

import atexit
import shutil
import subprocess
import threading

import structlog

logger = structlog.get_logger(__name__)

__all__ = ["LATENCIA_MS", "Lacos", "fechar_tudo"]

LATENCIA_MS = 50

_FAMILIAS: list[Lacos] = []


class Lacos:
    """As laçadas de UMA família, guardadas por chave (normalmente o `uniq`)."""

    def __init__(self, familia: str) -> None:
        self.familia = familia
        self._vivos: dict[str, subprocess.Popen[bytes]] = {}
        self._trava = threading.Lock()
        _FAMILIAS.append(self)

    def esta_ligado(self, chave: str) -> bool:
        """Esta laçada está de pé AGORA? Pergunta ao processo, não à lembrança."""
        if not chave:
            return False
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
            proc = subprocess.Popen(
                argv, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except (OSError, subprocess.SubprocessError) as exc:
            logger.info(
                "laco_nao_subiu", familia=self.familia, chave=chave, err=str(exc))
            return False
        with self._trava:
            self._vivos[chave] = proc
        logger.info(
            "laco_ligado", familia=self.familia, chave=chave,
            captura=captura, destino=destino or "(padrão)")
        return True

    def desligar(self, chave: str) -> bool:
        """Fecha a laçada. `True` = havia uma e ela morreu."""
        with self._trava:
            proc = self._vivos.pop(chave, None)
        if proc is None:
            return False
        try:
            proc.kill()
            proc.wait(timeout=2)
        except (OSError, subprocess.SubprocessError):
            pass
        logger.info("laco_desligado", familia=self.familia, chave=chave)
        return True

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
