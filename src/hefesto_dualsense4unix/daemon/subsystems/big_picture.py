"""O Modo Big Picture na Steam: um valor, um dono, e o foco da Steam decide.

A-ABA-NAVEGACAO-FAZ-O-QUE-DIZ-E-O-MODO-STEAM-NAVEGA-O-BIG-PICTURE-01 (03/10/2026).
Com o modo ligado e a janela do cliente da Steam na frente, o controle navega o
Big Picture: o direcional anda, a Cruz confirma (Enter) e o Círculo volta (Esc).

QUEM LÊ O CONTROLE decide se o Hefesto entra (``hotkey.QUEM_LE_O_CONTROLE``).
No Nativo e no Steam Input a Steam lê o físico, e o Big Picture navega sozinho:
o Hefesto não faz nada. No Sony DualSense, no Xbox e na Navegação o controle é
do Hefesto, e a Steam só enxerga o pad virtual (ou nada, na Navegação): ali o
Hefesto entrega a tecla ao Big Picture. UM CAMINHO SÓ por modo: os botões que
viram tecla SAEM do pad virtual (e do mouse virtual) enquanto isso vale, para o
Big Picture não andar dois passos por aperto. O analógico, os gatilhos e os
demais botões seguem como sempre.

Vale para P1 a P4: cada fonte (o primário e cada jogador do co-op) diz os botões
que está apertando, e a tecla é a união deles. Sem tecla virtual para entregar
(``/dev/uinput`` fechado), o Hefesto não rouba botão nenhum.
"""
from __future__ import annotations

import threading
import time
from collections.abc import Callable
from typing import Any

from hefesto_dualsense4unix.utils.logging_config import get_logger

logger = get_logger(__name__)

TECLAS: dict[str, tuple[str, ...]] = {
    "dpad_up": ("KEY_UP",),
    "dpad_down": ("KEY_DOWN",),
    "dpad_left": ("KEY_LEFT",),
    "dpad_right": ("KEY_RIGHT",),
    "cross": ("KEY_ENTER",),
    "circle": ("KEY_ESC",),
}
BOTOES_QUE_NAVEGAM = frozenset(TECLAS)

NOME_DO_TECLADO = "Hefesto - DualSense4Unix Big Picture Keyboard"

VALIDADE_DA_FONTE_S = 0.5

FONTE_PRIMARIA = "P1"


def _teclado_de_verdade() -> Any:
    from hefesto_dualsense4unix.integrations.uinput_keyboard import UinputKeyboardDevice

    return UinputKeyboardDevice(name=NOME_DO_TECLADO, bindings=dict(TECLAS))


class BigPicture:
    """O dono do Modo Big Picture no daemon: ligado, o foco da Steam e as teclas."""

    def __init__(
        self,
        *,
        ligado: bool = False,
        teclado: Callable[[], Any] = _teclado_de_verdade,
        relogio: Callable[[], float] = time.monotonic,
    ) -> None:
        self.ligado = bool(ligado)
        self._fabrica = teclado
        self._relogio = relogio
        self._teclado: Any = None
        self._falhou = False
        self._lock = threading.Lock()
        self._por_fonte: dict[str, frozenset[str]] = {}
        self._visto: dict[str, float] = {}

    @classmethod
    def da_sessao(cls) -> BigPicture:
        """A escolha guardada (``big_picture.flag``); sem ela, desligado."""
        from hefesto_dualsense4unix.utils.session import load_big_picture

        return cls(ligado=load_big_picture())

    def definir(self, ligado: bool) -> None:
        """Liga ou desliga e guarda. Desligar solta toda tecla e fecha o teclado."""
        self.ligado = bool(ligado)
        from hefesto_dualsense4unix.utils.session import save_big_picture

        save_big_picture(self.ligado)
        if not self.ligado:
            self.parar()
        logger.info("big_picture_definido", ligado=self.ligado)

    def parar(self) -> None:
        """Solta as teclas e fecha o teclado virtual."""
        with self._lock:
            self._por_fonte.clear()
            self._visto.clear()
            teclado, self._teclado = self._teclado, None
            self._falhou = False
        if teclado is not None:
            try:
                teclado.stop()
            except Exception as exc:
                logger.debug("big_picture_teclado_nao_parou", err=str(exc))

    def agindo(self, daemon: Any) -> bool:
        """Ligado, a Steam na frente e o controle é do Hefesto neste modo."""
        if not self.ligado:
            return False
        classe = getattr(getattr(daemon, "store", None), "window_detect_current_class", None)
        from hefesto_dualsense4unix.profiles.steam_app import e_janela_do_cliente_steam

        if not e_janela_do_cliente_steam(classe):
            return False
        from hefesto_dualsense4unix.daemon.subsystems.hotkey import (
            LE_O_HEFESTO,
            quem_le_o_controle,
        )

        return quem_le_o_controle(daemon) == LE_O_HEFESTO

    def _com_teclado(self) -> bool:
        """Há tecla virtual para entregar? Abre na primeira vez; falha uma vez só."""
        if self._teclado is not None:
            return True
        if self._falhou:
            return False
        try:
            teclado = self._fabrica()
            aberto = bool(teclado.start())
        except Exception as exc:
            logger.warning("big_picture_teclado_falhou", err=str(exc))
            aberto = False
        if not aberto:
            self._falhou = True
            logger.warning("big_picture_sem_teclado_virtual")
            return False
        self._teclado = teclado
        return True

    def _emitir(self, extra: frozenset[str] = frozenset()) -> None:
        """Leva ao teclado a união dos botões de todas as fontes (e o toque curto)."""
        teclado = self._teclado
        if teclado is None:
            return
        uniao: frozenset[str] = frozenset().union(*self._por_fonte.values())
        try:
            if extra - uniao:
                teclado.dispatch(uniao | extra)
            teclado.dispatch(uniao)
        except Exception as exc:
            logger.warning("big_picture_tecla_falhou", err=str(exc))

    def rotear(
        self,
        daemon: Any,
        fonte: str | None,
        botoes: frozenset[str],
        soltos: frozenset[str] = frozenset(),
    ) -> tuple[frozenset[str], frozenset[str]]:
        """Os botões que ficam para o pad (ou o mouse) depois de virarem tecla.

        Agindo, o direcional, a Cruz e o Círculo de ``fonte`` viram setas, Enter
        e Esc, e saem de ``botoes`` e de ``soltos`` (o toque que coube num tique
        só vira uma tecla apertada e solta). Fora disso devolve tudo como veio e
        solta o que a ``fonte`` segurava.
        """
        nome = fonte or FONTE_PRIMARIA
        agora = self._relogio()
        agindo = self.agindo(daemon)
        with self._lock:
            if agindo:
                agindo = self._com_teclado()
            if not agindo:
                if self._por_fonte.pop(nome, None) is not None:
                    self._visto.pop(nome, None)
                    self._emitir()
                return botoes, soltos
            self._por_fonte[nome] = botoes & BOTOES_QUE_NAVEGAM
            self._visto[nome] = agora
            for velha in [f for f, t in self._visto.items() if agora - t > VALIDADE_DA_FONTE_S]:
                self._por_fonte.pop(velha, None)
                self._visto.pop(velha, None)
            self._emitir(soltos & BOTOES_QUE_NAVEGAM)
        return botoes - BOTOES_QUE_NAVEGAM, soltos - BOTOES_QUE_NAVEGAM

    def bloco(self, daemon: Any) -> dict[str, Any]:
        """O bloco ``big_picture`` do ``state_full``: ``{ligado, agindo, quem_le}``."""
        quem = None
        if self.ligado:
            from hefesto_dualsense4unix.daemon.subsystems.hotkey import quem_le_o_controle

            quem = quem_le_o_controle(daemon)
        return {"ligado": self.ligado, "agindo": self.agindo(daemon), "quem_le": quem}


def da_big_picture(daemon: Any) -> BigPicture | None:
    """O Modo Big Picture do daemon, ou ``None`` num dublê que não o tem."""
    bp = getattr(daemon, "_big_picture", None)
    return bp if isinstance(bp, BigPicture) else None


def levar_o_big_picture(
    daemon: Any,
    fonte: str | None,
    botoes: frozenset[str],
    soltos: frozenset[str] = frozenset(),
) -> tuple[frozenset[str], frozenset[str]]:
    """O gancho dos três lugares onde o botão sai do controle: o pad e o mouse."""
    bp = da_big_picture(daemon)
    if bp is None:
        return botoes, soltos
    return bp.rotear(daemon, fonte, botoes, soltos)
