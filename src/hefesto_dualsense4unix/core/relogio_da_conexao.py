"""O relógio de uma conexão: o tempo de cada etapa, por controle, numa linha só do diário.

A linha ``conexao_etapas`` sai quando todas as peças do controle ficam de pé, ou no teto, com as
que faltaram. Os tempos são em milissegundos desde a primeira marca, e valem para o cabo direto,
para o rádio e para a troca do rádio pelo cabo. Quem marca só diz o que acabou de acontecer.
"""
from __future__ import annotations

import re
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field

from hefesto_dualsense4unix.core.formas_do_endereco import mascarar, mascarar_endereco
from hefesto_dualsense4unix.utils.logging_config import get_logger

logger = get_logger(__name__)

USB_ENTROU = "usb_entrou"
O_CABO_CHEGOU = "o_cabo_chegou"
O_CABO_ASSUME = "o_cabo_assume"
TENTATIVA_FALHOU = "tentativa_falhou"
ABERTO = "aberto"
CONECTADO = "conectado"
MOVIMENTO = "movimento"
HAPTICA = "haptica"
SOM = "som"
MICROFONE = "microfone"
CHEGADA = "chegada"

_ABREM_O_RELOGIO = frozenset({ABERTO, CONECTADO, O_CABO_CHEGOU})
_PECAS_DO_CABO = (MOVIMENTO, HAPTICA, SOM, MICROFONE, CHEGADA)
_PECAS_DO_RADIO = (MOVIMENTO, MICROFONE, CHEGADA)
_PECAS_POR_TRANSPORTE = {"bt": _PECAS_DO_RADIO}

TETO_DAS_PECAS_S = 20.0
VALIDADE_DO_USB_S = 60.0

_RE_HEXA = re.compile(r"[^0-9a-fA-F]")


def _chave(uniq: object) -> str:
    texto = str(uniq or "")
    hexa = _RE_HEXA.sub("", texto).lower()
    return hexa if len(hexa) == 12 else texto


@dataclass
class _Conexao:
    transporte: str = ""
    inicio: float = 0.0
    marcas: dict[str, float] = field(default_factory=dict)
    dispensadas: set[str] = field(default_factory=set)
    uniq: str = ""
    falhas: int = 0
    conectado_em: float | None = None


class RelogioDaConexao:
    """As conexões em curso, por controle; cada uma fecha numa linha ``conexao_etapas``."""

    def __init__(
        self,
        *,
        relogio: Callable[[], float] = time.monotonic,
        dizer: Callable[..., object] | None = None,
    ) -> None:
        self._relogio = relogio
        self._dizer = dizer if dizer is not None else logger.info
        self._trava = threading.Lock()
        self._usb: dict[str, float] = {}
        self._abertas: dict[str, _Conexao] = {}
        self._falhas_antes: dict[str, int] = {}

    def usb_entrou(self, no: str) -> None:
        """Um DualSense apareceu no barramento USB: ainda sem endereço, só a porta."""
        with self._trava:
            agora = self._relogio()
            self._esquecer_os_velhos_locked(agora)
            self._usb.setdefault(no, agora)

    def marcar(
        self, uniq: object, etapa: str, *, transporte: str = "", no: str | None = None
    ) -> None:
        """Anota ``etapa`` de ``uniq``. A primeira marca de cada etapa vale."""
        chave = _chave(uniq)
        if not chave:
            return
        with self._trava:
            agora = self._relogio()
            conexao = self._abertas.get(chave)
            if conexao is None:
                if etapa == TENTATIVA_FALHOU:
                    self._falhas_antes[chave] = self._falhas_antes.get(chave, 0) + 1
                    return
                if etapa not in _ABREM_O_RELOGIO:
                    return
                conexao = self._abrir_locked(chave, str(uniq), agora, no)
            if transporte:
                conexao.transporte = transporte
            if etapa == TENTATIVA_FALHOU:
                conexao.falhas += 1
                return
            conexao.marcas.setdefault(etapa, agora)
            if etapa == CONECTADO and conexao.conectado_em is None:
                conexao.conectado_em = agora
            if etapa == O_CABO_CHEGOU:
                conexao.dispensadas.add(CHEGADA)
            self._fechar_se_pronta_locked(chave, conexao, agora)

    def dispensar(self, uniq: object, etapa: str) -> None:
        """Esta peça não sobe nesta conexão, e a linha não a conta como falta."""
        chave = _chave(uniq)
        with self._trava:
            conexao = self._abertas.get(chave)
            if conexao is None:
                return
            conexao.dispensadas.add(etapa)
            self._fechar_se_pronta_locked(chave, conexao, self._relogio())

    def varrer(self) -> int:
        """Fecha quem passou do teto. Devolve quantas linhas saíram."""
        with self._trava:
            agora = self._relogio()
            vencidas = [
                (chave, conexao)
                for chave, conexao in self._abertas.items()
                if self._venceu(conexao, agora)
            ]
            for chave, conexao in vencidas:
                self._fechar_locked(chave, conexao, agora)
            return len(vencidas)

    def limpar(self) -> None:
        with self._trava:
            self._usb.clear()
            self._abertas.clear()
            self._falhas_antes.clear()

    def _abrir_locked(self, chave: str, uniq: str, agora: float, no: str | None) -> _Conexao:
        self._esquecer_os_velhos_locked(agora)
        entrou = self._usb.pop(no, None) if no else None
        if entrou is None and not no and len(self._usb) == 1:
            entrou = self._usb.pop(next(iter(self._usb)))
        conexao = _Conexao(
            inicio=agora if entrou is None else entrou,
            uniq=uniq,
            falhas=self._falhas_antes.pop(chave, 0),
        )
        if entrou is not None:
            conexao.marcas[USB_ENTROU] = entrou
        self._abertas[chave] = conexao
        return conexao

    def _esquecer_os_velhos_locked(self, agora: float) -> None:
        for no in [n for n, quando in self._usb.items() if agora - quando > VALIDADE_DO_USB_S]:
            self._usb.pop(no, None)

    @staticmethod
    def _pecas(conexao: _Conexao) -> tuple[str, ...]:
        do_transporte = _PECAS_POR_TRANSPORTE.get(conexao.transporte, _PECAS_DO_CABO)
        return tuple(p for p in do_transporte if p not in conexao.dispensadas)

    def _venceu(self, conexao: _Conexao, agora: float) -> bool:
        desde = conexao.inicio if conexao.conectado_em is None else conexao.conectado_em
        return agora - desde >= TETO_DAS_PECAS_S

    def _fechar_se_pronta_locked(self, chave: str, conexao: _Conexao, agora: float) -> None:
        if CONECTADO in conexao.marcas and all(
            peca in conexao.marcas for peca in self._pecas(conexao)
        ):
            self._fechar_locked(chave, conexao, agora)

    def _fechar_locked(self, chave: str, conexao: _Conexao, agora: float) -> None:
        self._abertas.pop(chave, None)
        tempos = {
            etapa: round((quando - conexao.inicio) * 1000)
            for etapa, quando in sorted(conexao.marcas.items(), key=lambda par: par[1])
        }
        ultima = max(conexao.marcas.values(), default=agora)
        self._dizer(
            "conexao_etapas",
            uniq=mascarar_endereco(conexao.uniq) or mascarar(conexao.uniq),
            transporte=conexao.transporte or "?",
            total_ms=round((ultima - conexao.inicio) * 1000),
            faltam=[p for p in self._pecas(conexao) if p not in conexao.marcas],
            falhas=conexao.falhas,
            **tempos,
        )


RELOGIO = RelogioDaConexao()

__all__ = [
    "ABERTO",
    "CHEGADA",
    "CONECTADO",
    "HAPTICA",
    "MICROFONE",
    "MOVIMENTO",
    "O_CABO_ASSUME",
    "O_CABO_CHEGOU",
    "RELOGIO",
    "SOM",
    "TENTATIVA_FALHOU",
    "TETO_DAS_PECAS_S",
    "USB_ENTROU",
    "VALIDADE_DO_USB_S",
    "RelogioDaConexao",
]
