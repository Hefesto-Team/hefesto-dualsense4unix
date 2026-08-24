"""O montador da aba Configurações — cria as cinco molduras e nada mais.

Este arquivo é deliberadamente burro, e é isso que o torna útil: ele conhece a
ORDEM das seções e o formato da moldura, e não conhece uma linha do que há
dentro de nenhuma delas. Cada seção mora no seu módulo (`secao_*.py`), declara
o próprio título e a própria dica, e monta o próprio conteúdo.

O desenho nasceu de uma medição: as oito frentes que constroem esta aba
tocariam, todas, o mesmo arquivo. Um arquivo por seção troca oito colisões por
zero, e o preço é este montador de trinta linhas.
"""
from __future__ import annotations

import contextlib

from hefesto_dualsense4unix.app.actions.base import WidgetAccessMixin
from hefesto_dualsense4unix.app.actions.config.moldura import moldura_de_secao
from hefesto_dualsense4unix.app.actions.config.secoes import SECOES_DA_ABA
from hefesto_dualsense4unix.utils.logging_config import get_logger

logger = get_logger(__name__)

#: Id do Glade da aba Configurações. Mesma disciplina de `ABA_INICIO` e
#: `ABA_STATUS`: a aba é identificada pelo id do Glade, NUNCA pelo número da
#: página (EST-10). Acrescentar uma aba renumera todas, e um gate por índice
#: passaria a agir sobre a aba errada em silêncio.
ABA_CONFIG = "tab_config_box"


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
            # Uma seção que falha ao montar deixa a MOLDURA na tela e some com
            # o conteúdo — que é o comportamento certo: a pessoa vê que a
            # seção existe e está vazia, em vez de ver a aba inteira sumir.
            with contextlib.suppress(Exception):
                secao.montar(self, caixa)
            frame.show_all()

        logger.info("config_tab_instalada", secoes=len(SECOES_DA_ABA))

    def set_alvo_inativo(self, inativo: bool) -> None:
        """Esmaece (ou devolve) o seletor de controle do cabeçalho.

        O cabeçalho carrega a fita "Ajustes vão para: [1][2][3][4]", que escolhe
        a QUEM as outras abas aplicam o que fazem. Nesta aba a pergunta não tem
        sentido — o que se declara aqui vale para a mesa inteira —, então a fita
        fica inerte.

        Esmaecer em vez de esconder é deliberado: sumir com a fita faria o
        cabeçalho pular de altura a cada troca de aba, e deixaria a pessoa sem
        saber que a escolha dela continua valendo nas outras abas.

        **O cabeçalho não ganha nada, e é decisão dela (23/08/2026).** A versão
        anterior pendurava ao lado da fita um rótulo com o motivo. Ele empurrava
        a altura e a largura do cabeçalho, cobria o subtítulo do produto e
        deixava esta aba visivelmente mais larga que as outras dez. Explicação
        que deforma a página cobra caro demais pelo que entrega.

        Tolerante por dentro e por fora: hospedeiro sem cabeçalho, sem fita ou
        sem GTK não levanta. É a fiação de uma aba, não pode derrubar a janela.
        """
        faixa = getattr(self, "_target_strip", None)
        if faixa is None:
            return
        with contextlib.suppress(Exception):
            faixa.set_sensitive(not inativo)
