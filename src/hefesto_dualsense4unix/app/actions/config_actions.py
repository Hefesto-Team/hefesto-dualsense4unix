"""Aba Configurações — onde entra o que o Hefesto não tem como medir.

CONFIG-01, a décima primeira aba. As dez abas de hoje operam sobre o que o
produto **mede**; esta é o lugar do que ele **não consegue medir** e precisa que
a pessoa declare — onde o dongle está fisicamente, se há um hub no caminho, o
que é aquele rádio vizinho, qual a cor do plástico quando a leitura falha.

O teste de admissão de qualquer controle novo aqui é uma pergunta só: *o Hefesto
conseguiria descobrir isso sozinho?* Se sim, o lugar não é esta aba.

Nesta primeira entrega a aba nasce **vazia de propósito**: só os cinco títulos
de seção, na ordem do desenho aprovado, cada um com a dica que explica por que a
seção existe. Nenhum widget de conteúdo, nenhuma chamada ao daemon, nenhuma
leitura de disco — e, principalmente, **nenhum número na tela**, porque nenhum
número foi medido ainda. Rótulo estático é honesto; valor inventado não é.

O que esta sprint existe para descobrir já foi medido, e é um não-evento: a
décima primeira aba vazia custa ZERO de largura e ZERO do orçamento de altura.
A largura mínima da janela e o teto por aba não se mexeram; a tira de abas
continua sem seta de rolagem em 1180px. O aceite desta entrega é negativo e
verificável — *os números não se mexeram*.

Como a aba Início, o Glade só reserva o container (`tab_config_box`): todo
widget é montado aqui, em código. É o padrão dos widgets dinâmicos desta casa,
imune ao bug de popup do cosmic-comp (cosmic-epoch#2497).
"""
from __future__ import annotations

import contextlib
from typing import Any, Final

from hefesto_dualsense4unix.app.actions.base import WidgetAccessMixin
from hefesto_dualsense4unix.utils.i18n import _
from hefesto_dualsense4unix.utils.logging_config import get_logger

logger = get_logger(__name__)

#: Id do Glade da aba Configurações. Mesma disciplina de `ABA_INICIO` e
#: `ABA_STATUS`: a aba é identificada pelo id do Glade, NUNCA pelo número da
#: página (EST-10). Acrescentar uma aba renumera todas, e um gate por índice
#: passaria a agir sobre a aba errada em silêncio.
ABA_CONFIG = "tab_config_box"

#: As cinco seções, na ordem do desenho aprovado, como (título, dica).
#:
#: A dica de cada uma é o texto do desenho, palavra por palavra — o contrato de
#: escrita das dicas é explícito quanto a isso: elas não se reescrevem na hora.
#: A quinta, "A janela", não tem dica porque no desenho ela também não tem: os
#: rótulos dela se explicam sozinhos, e inventar uma explicação aqui seria pôr
#: na tela uma frase que ninguém aprovou.
#:
#: A maiúscula inicial não é estilo: o portão da palavra de tela cobra.
SECOES: Final[tuple[tuple[str, str | None], ...]] = (
    (
        "Está tudo certo?",
        "O mesmo exame que o Hefesto já sabe fazer pelo terminal, agora com "
        "resposta em uma linha. Só lê — não muda nada na máquina.",
    ),
    (
        "Os controles",
        "A borda de cada card é a cor do plástico daquele controle. O anel roxo "
        "por dentro marca qual está selecionado no cabeçalho da janela.",
    ),
    (
        "A mesa",
        "O Hefesto enxerga os adaptadores, mas não enxerga onde eles estão. "
        "Cabo, hub e altura mudam o alcance e não aparecem em lugar nenhum do "
        "sistema.",
    ),
    (
        "Orçamento",
        "Um teto para a mesa inteira. As abas continuam mandando no que fazem — "
        "só não passam daqui. Nenhum ajuste seu é apagado.",
    ),
    ("A janela", None),
)

#: Por que o seletor de controle do cabeçalho fica inerte nesta aba.
#:
#: A frase é a resposta a uma pergunta que a pessoa faria em silêncio: "por que
#: o chip do controle parou de responder?". Sem ela o seletor pareceria quebrado
#: — e um widget que não responde sem dizer o motivo é defeito, não desenho.
RAZAO_ALVO_INATIVO = "Esta aba vale para a mesa inteira, não para um controle"


class ConfigActionsMixin(WidgetAccessMixin):
    """Mixin da aba Configurações (a última página do notebook)."""

    def install_config_tab(self) -> None:
        """Monta o conteúdo da aba Configurações. Idempotente.

        Nesta entrega o conteúdo são os cinco títulos de seção e nada mais.

        Saída cedo tolerante, como as outras abas: sem o container no XML (dublê
        de teste, glade antigo) o método devolve sem levantar. Uma aba que não
        existe não pode derrubar a janela.
        """
        from gi.repository import Gtk

        box = self._get(ABA_CONFIG)
        if box is None or getattr(self, "_config_installed", False):
            return
        self._config_installed = True

        for titulo, dica in SECOES:
            rotulo = Gtk.Label(label=_(titulo))
            rotulo.set_xalign(0.0)
            with contextlib.suppress(Exception):
                rotulo.get_style_context().add_class("hefesto-titulo-secao")
            if dica is not None:
                rotulo.set_tooltip_text(_(dica))
            box.pack_start(rotulo, False, False, 0)
            rotulo.show()

        logger.info("config_tab_instalada", secoes=len(SECOES))

    def set_alvo_inativo(self, inativo: bool) -> None:
        """Esmaece (ou devolve) o seletor de controle do cabeçalho.

        O cabeçalho carrega a fita "Ajustes vão para: [1][2][3][4]", que escolhe
        a QUEM as outras abas aplicam o que fazem. Nesta aba a pergunta não tem
        sentido — o que se declara aqui vale para a mesa inteira —, então a fita
        fica inerte e ganha, ao lado, a frase que diz por quê.

        Esmaecer em vez de esconder é deliberado: sumir com a fita faria o
        cabeçalho pular de altura a cada troca de aba, e deixaria a pessoa sem
        saber que a escolha dela continua valendo nas outras abas.

        Tolerante por dentro e por fora: hospedeiro sem cabeçalho, sem fita ou
        sem GTK não levanta. É a fiação de uma aba, não pode derrubar a janela.
        """
        faixa = getattr(self, "_target_strip", None)
        if faixa is None:
            return
        with contextlib.suppress(Exception):
            faixa.set_sensitive(not inativo)
        if not inativo:
            # Sair da aba não é motivo para criar widget nenhum: quem nunca
            # entrou em Configurações não ganha um rótulo invisível no
            # cabeçalho a cada troca de aba.
            razao = getattr(self, "_alvo_inativo_label", None)
            if razao is not None:
                with contextlib.suppress(Exception):
                    razao.hide()
            return
        razao = self._rotulo_da_razao_do_alvo(faixa)
        if razao is None:
            return
        with contextlib.suppress(Exception):
            razao.show()

    def _rotulo_da_razao_do_alvo(self, faixa: Any) -> Any:
        """O rótulo da razão, criado na primeira vez que faz falta.

        Nasce ao lado da fita e não DENTRO dela, de propósito: dentro, ele
        herdaria a insensibilidade da fita e a explicação sairia esmaecida junto
        com aquilo que ela explica.

        Devolve ``None`` quando não há onde pendurá-lo (dublê de teste, fita
        solta), e nunca levanta.
        """
        existente = getattr(self, "_alvo_inativo_label", None)
        if existente is not None:
            return existente
        try:
            from gi.repository import Gtk

            cabecalho = faixa.get_parent()
            if cabecalho is None:
                return None
            razao = Gtk.Label(label=_(RAZAO_ALVO_INATIVO))
            razao.set_xalign(0.0)
            razao.set_line_wrap(True)
            razao.set_max_width_chars(84)
            with contextlib.suppress(Exception):
                razao.get_style_context().add_class("dim-label")
            razao.set_no_show_all(True)
            razao.hide()
            cabecalho.pack_end(razao, False, False, 0)
        except Exception:
            return None
        self._alvo_inativo_label = razao
        return razao
