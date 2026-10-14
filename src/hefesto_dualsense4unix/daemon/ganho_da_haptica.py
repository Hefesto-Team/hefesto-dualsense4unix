"""O dono do ganho da háptica por áudio — um por controle, em fator linear.

Quem o aplica é o caminho de cada controle, nunca a placa: no cabo, o volume do
fluxo do laço (``haptica_do_cabo``); no rádio, a ponte (``ganho_da_haptica``).
OS-QUATRO-EM-HARMONIA-01 (14/10/2026): os traseiros da placa USB não valem, o nó
ALSA aplica a frente aos quatro canais.
"""

from __future__ import annotations

import contextlib
from typing import Any

from hefesto_dualsense4unix.utils.logging_config import get_logger

logger = get_logger(__name__)

#: Em Padrão a háptica chega como o jogo mandou: 100 %, sem o ganho guardado.
PCT_DO_JOGO = 100


def _chave(uniq: str | None) -> str | None:
    """A chave do perfil para este controle (o dono é ``norm_mac``)."""
    if not uniq:
        return None
    from hefesto_dualsense4unix.core.sysfs_leds import norm_mac

    with contextlib.suppress(Exception):
        return norm_mac(uniq) or None
    return None


class GanhoDaHaptica:
    """O ganho por controle, lido do perfil que vale; um só no processo (:data:`GANHO`)."""

    def __init__(self) -> None:
        self._escritos: dict[str, int] = {}
        self._pelo_carregador: str | None = None
        self._teto: float | None = None
        self._em_economia: frozenset[str] = frozenset()
        self._politicas: dict[str, str] = {}
        self._politica_global: str | None = None

    def ler_do_perfil(self, controllers: Any) -> None:
        """Troca o mapa pelo ``controllers`` de um perfil (``None`` = ninguém opinou)."""
        from hefesto_dualsense4unix.profiles.schema import (
            pcts_da_haptica_dos_controles,
            politicas_dos_controles,
        )

        mapa: dict[str, int] = {}
        politicas: dict[str, str] = {}
        with contextlib.suppress(Exception):
            for uniq, pct in pcts_da_haptica_dos_controles(controllers).items():
                chave = _chave(uniq)
                if chave is not None:
                    mapa[chave] = pct
            for uniq, politica in politicas_dos_controles(controllers).items():
                chave = _chave(uniq)
                if chave is not None:
                    politicas[chave] = politica
        self._escritos = mapa
        self._politicas = politicas

    def ler_do_daemon(self, daemon: Any, *, forcar: bool = False) -> None:
        """Relê o perfil que vale agora, pelo mesmo resolvedor dos gravadores."""
        self.ler_o_teto(daemon)
        controllers: Any = None
        with contextlib.suppress(Exception):
            from hefesto_dualsense4unix.profiles.loader import load_profile, perfil_em_disco
            from hefesto_dualsense4unix.profiles.manager import nome_do_perfil_que_grava

            store = getattr(daemon, "store", None)
            nome = nome_do_perfil_que_grava(getattr(store, "active_profile", None))
            perfil = perfil_em_disco(nome) if nome else None
            if perfil is None and nome:
                if not forcar and self._pelo_carregador == nome:
                    return
                self._pelo_carregador = nome
                perfil = load_profile(nome)
            else:
                self._pelo_carregador = None
            from hefesto_dualsense4unix.profiles.o_padrao_do_computador import (
                o_computador,
                o_que_vale,
            )

            controllers = (
                getattr(o_que_vale(perfil), "controllers", None)
                if perfil is not None else o_computador().controles or None
            )
        self.ler_do_perfil(controllers)

    def ler_o_teto(self, daemon: Any) -> None:
        """O teto da Economia de agora: o da mesa e o de cada controle que ligou a sua."""
        teto: float | None = None
        with contextlib.suppress(Exception):
            from hefesto_dualsense4unix.core.rumble import (
                _orcamento_declarado,
                teto_do_orcamento,
            )

            teto = teto_do_orcamento(_orcamento_declarado(getattr(daemon, "config", None)))
        self._teto = teto
        politica = getattr(getattr(daemon, "config", None), "rumble_policy", None)
        self._politica_global = politica if isinstance(politica, str) else None
        ligados: frozenset[str] = frozenset()
        with contextlib.suppress(Exception):
            from hefesto_dualsense4unix.profiles.schema import controles_em_economia

            ligados = frozenset(c for c in (_chave(u) for u in controles_em_economia()) if c)
        self._em_economia = ligados

    def _teto_de(self, uniq: str | None) -> float | None:
        """O teto deste controle: o da mesa, ou o da economia que ELE ligou."""
        if self._teto is not None:
            return self._teto
        chave = _chave(uniq)
        if chave is None or chave not in self._em_economia:
            return None
        from hefesto_dualsense4unix.core.rumble import _ORCAMENTO_COM_TETO, teto_do_orcamento

        return teto_do_orcamento(_ORCAMENTO_COM_TETO)

    def _vale_o_padrao(self, uniq: str | None) -> bool:
        """O degrau deste controle é o Padrão (o dele, ou o global)?"""
        from hefesto_dualsense4unix.core.rumble import vale_o_padrao

        chave = _chave(uniq)
        propria = self._politicas.get(chave) if chave is not None else None
        return vale_o_padrao(propria or self._politica_global)

    def pct_guardado(self, uniq: str | None) -> int:
        """O ganho que o usuário escolheu para este controle, em % (0 a ``HAPTICA_PCT_MAX``)."""
        from hefesto_dualsense4unix.profiles.schema import HAPTICA_PCT_PADRAO

        chave = _chave(uniq)
        if chave is None:
            return HAPTICA_PCT_PADRAO
        return self._escritos.get(chave, HAPTICA_PCT_PADRAO)

    def pct(self, uniq: str | None) -> int:
        """O ganho que VALE antes do teto, em %: o guardado, ou 100 em Padrão.

        Em Padrão o ganho guardado não se aplica (04/10/2026): o sinal chega
        como o jogo mandou, e o guardado volta com a Economia ou o Máximo.
        """
        if self._vale_o_padrao(uniq):
            return PCT_DO_JOGO
        return self.pct_guardado(uniq)

    def fator(self, uniq: str | None) -> float:
        """O ganho que VALE em fator linear de amplitude (150 % → 1,5; na Economia, 0,3)."""
        from hefesto_dualsense4unix.core.rumble import _sob_o_teto

        return _sob_o_teto(self.pct(uniq) / 100.0, self._teto_de(uniq))

    def pct_que_vale(self, uniq: str | None) -> int:
        """O ganho que vale agora, em %: o escolhido sob o teto do orçamento."""
        return round(self.fator(uniq) * 100.0)


GANHO = GanhoDaHaptica()

