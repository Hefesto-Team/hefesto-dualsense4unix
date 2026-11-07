"""O que o Som no corpo tocou, por controle, numa linha por minuto.

Os contadores moram aqui e sobem ao ``store`` só na linha do minuto. O rótulo é a cor do
plástico, nunca o endereço. Quem chama conta; a escrita sai fora do tique.
"""
from __future__ import annotations

import threading
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass, field

from hefesto_dualsense4unix.utils.logging_config import get_logger

logger = get_logger(__name__)

JANELA_DO_MINUTO_S = 60.0
PASSO_DO_DIARIO_S = 5.0
PRAZO_DO_SURDO_S = 30.0
SEM_COR = "controle"

RECUSA_SEM_APARELHO = "sem_aparelho"
RECUSA_FORCA_ZERO = "forca_zero"
RECUSA_SEM_ENDPOINT = "sem_endpoint"
RECUSA_JOGO_NO_ENDPOINT = "jogo_no_endpoint"
RECUSA_RADIO_CEDE = "radio_cede"
RECUSA_ECONOMIA = "economia"
FALA_DA_RECUSA = {
    RECUSA_SEM_APARELHO: "sem aparelho",
    RECUSA_FORCA_ZERO: "Força em 0",
    RECUSA_SEM_ENDPOINT: "sem endpoint",
    RECUSA_JOGO_NO_ENDPOINT: "o jogo no endpoint",
    RECUSA_RADIO_CEDE: "o rádio sem fatia",
    RECUSA_ECONOMIA: "economia",
}

PREFIXO_DO_CONTROLE = "corpo.controle."
CHAVE_DO_PCM = "corpo.pcm_lido"
CHAVE_DO_SURDO = "corpo.ouvido_surdo"


@dataclass(frozen=True)
class DesfechoDoCorpo:
    """O que ``tocar_o_corpo`` fez: verdadeiro quando tocou, e o motivo quando recusou."""

    motivo: str | None = None

    def __bool__(self) -> bool:
        return self.motivo is None


TOCOU = DesfechoDoCorpo()


@dataclass
class _Conta:
    blocos: int = 0
    recusas: Counter[str] = field(default_factory=Counter)


def _nada_sobe(_chave: str, _delta: int) -> object:
    return None


class DiarioDoCorpo:
    """As contas do minuto. As duas threads que contam (a do ouvido e a do tique) nunca esperam."""

    def __init__(
        self,
        cor_de: Callable[[str], str | None] = lambda _uniq: None,
        subir: Callable[[str, int], object] = _nada_sobe,
    ) -> None:
        self._cor_de = cor_de
        self._subir = subir
        self._trava = threading.Lock()
        self._pcm = 0
        self._contas: dict[str, _Conta] = {}
        self._rotulos: dict[str, str] = {}
        self._aberto_em: float | None = None
        self._jogo = False
        self._pedido = False
        self._surdo = False

    def somar_o_pcm(self, bytes_lidos: int) -> None:
        with self._trava:
            self._pcm += bytes_lidos

    def entregue(self, uniq: str) -> None:
        with self._trava:
            self._contas.setdefault(uniq, _Conta()).blocos += 1

    def recusado(self, uniq: str, motivo: str) -> None:
        with self._trava:
            self._contas.setdefault(uniq, _Conta()).recusas[motivo] += 1

    def rotulo(self, uniq: str) -> str:
        """A cor do plástico. Dois da mesma cor ganham número, e a cor lida fica para a sessão."""
        rotulo = self._rotulos.get(uniq)
        if rotulo is not None and not rotulo.startswith(SEM_COR):
            return rotulo
        nome = self._cor_de(uniq) or SEM_COR
        if rotulo is not None and nome == SEM_COR:
            return rotulo
        ocupados = {r for u, r in self._rotulos.items() if u != uniq}
        novo = nome
        numero = 1
        while novo in ocupados:
            numero += 1
            novo = f"{nome} #{numero}"
        self._rotulos[uniq] = novo
        return novo

    def andar(self, agora: float, *, jogo: bool, pedido: bool, surdo_ha_s: float) -> None:
        """Um passo fora do tique: a borda do ouvido surdo e, a cada minuto, a linha."""
        self._ver_o_surdo(
            jogo and pedido and surdo_ha_s >= PRAZO_DO_SURDO_S, surdo_ha_s, ouve=jogo and pedido)
        self._jogo = self._jogo or jogo
        self._pedido = self._pedido or pedido
        if self._aberto_em is None:
            self._aberto_em = agora
        elif agora - self._aberto_em >= JANELA_DO_MINUTO_S:
            self._aberto_em = agora
            self._fechar_o_minuto()

    def _ver_o_surdo(self, surdo: bool, ha_s: float, *, ouve: bool) -> None:
        """A borda do surdo. O jogo que fechou encerra a surdez, sem dizer que voltou a ouvir."""
        if surdo == self._surdo:
            return
        self._surdo = surdo
        if surdo:
            self._subir(CHAVE_DO_SURDO, 1)
            logger.warning("tato_ouvido_surdo", ha_s=round(ha_s))
        elif ouve:
            logger.info("tato_ouvido_voltou_a_ouvir")

    def _fechar_o_minuto(self) -> None:
        with self._trava:
            pcm, contas = self._pcm, self._contas
            self._pcm, self._contas = 0, {}
        jogo, pedido = self._jogo, self._pedido
        self._jogo = self._pedido = False
        if not jogo or not (pedido or pcm or contas):
            return
        por_rotulo = {self.rotulo(uniq): conta for uniq, conta in contas.items()}
        logger.info(
            "tato_corpo_minuto", pcm_lido=pcm, surdo=self._surdo,
            controles={
                rotulo: {"blocos": conta.blocos, "recusas": dict(conta.recusas)}
                for rotulo, conta in por_rotulo.items()
            },
        )
        self._subir(CHAVE_DO_PCM, pcm)
        for rotulo, conta in por_rotulo.items():
            self._subir(f"{PREFIXO_DO_CONTROLE}{rotulo}.blocos", conta.blocos)
            for motivo, quantas in conta.recusas.items():
                self._subir(f"{PREFIXO_DO_CONTROLE}{rotulo}.recusa.{motivo}", quantas)


__all__ = [
    "CHAVE_DO_PCM",
    "CHAVE_DO_SURDO",
    "FALA_DA_RECUSA",
    "JANELA_DO_MINUTO_S",
    "PASSO_DO_DIARIO_S",
    "PRAZO_DO_SURDO_S",
    "PREFIXO_DO_CONTROLE",
    "RECUSA_ECONOMIA",
    "RECUSA_FORCA_ZERO",
    "RECUSA_JOGO_NO_ENDPOINT",
    "RECUSA_RADIO_CEDE",
    "RECUSA_SEM_APARELHO",
    "RECUSA_SEM_ENDPOINT",
    "SEM_COR",
    "TOCOU",
    "DesfechoDoCorpo",
    "DiarioDoCorpo",
]
