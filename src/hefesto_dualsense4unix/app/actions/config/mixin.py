"""O montador da aba Configurações — cria as cinco molduras e nada mais."""
from __future__ import annotations

import contextlib

from hefesto_dualsense4unix.app.actions.base import WidgetAccessMixin
from hefesto_dualsense4unix.app.actions.config.moldura import moldura_de_secao
from hefesto_dualsense4unix.app.actions.config.secoes import SECOES_DA_ABA
from hefesto_dualsense4unix.utils.logging_config import get_logger

logger = get_logger(__name__)

ABA_CONFIG = "tab_config_box"

MOTIVO_ALVO_NAO_SE_APLICA = (
    "Aqui os ajustes valem para todos os controles — não há um a escolher."
)


class ConfigActionsMixin(WidgetAccessMixin):
    """Mixin da aba Configurações (a última página do notebook)."""

    def install_config_tab(self) -> None:
        """Monta as cinco seções da aba Configurações. Idempotente.

        Saída cedo tolerante, como as outras abas: sem o container no XML (dublê
        de teste, glade antigo) o método devolve sem levantar. Uma aba que não
        existe não pode derrubar a janela.
        """
        box = self._get(ABA_CONFIG)
        if box is None or getattr(self, "_config_installed", False):
            return
        self._config_installed = True

        for secao in SECOES_DA_ABA:
            frame, caixa = moldura_de_secao(secao.TITULO, secao.DICA)
            box.pack_start(frame, False, False, 0)
            with contextlib.suppress(Exception):
                secao.montar(self, caixa)
            frame.show_all()

        logger.info("config_tab_instalada", secoes=len(SECOES_DA_ABA))

    def set_alvo_inativo(self, inativo: bool, motivo: str = "") -> None:
        """Esmaece (ou devolve) o seletor de controle do cabeçalho."""
        if inativo and not motivo:
            raise ValueError(
                "set_alvo_inativo(True) exige motivo — a aba que se "
                "desqualifica do alvo declara por quê (contrato Z2 §5)"
            )
        self._alvo_inativo_motivo: str | None = motivo if inativo else None
        faixa = getattr(self, "_target_strip", None)
        if faixa is None:
            return
        with contextlib.suppress(Exception):
            faixa.set_sensitive(not inativo)
        moldura = getattr(self, "_target_strip_hover", None)
        if moldura is None:
            return
        with contextlib.suppress(Exception):
            moldura.set_tooltip_text(motivo if inativo else None)
