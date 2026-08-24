"""O card de UM controle na seção "Os controles" da aba Configurações.

Um card por aparelho da mesa — os DualSense que o Hefesto adotou e os que ele só
VÊ (8BitDo, Pro Controller, Xbox). A borda é a cor do plástico daquele controle,
e é ela que responde, sem texto, à pergunta "qual destes é o meu?".

TRÊS COISAS DESTE ARQUIVO NÃO SÃO ESTÉTICA, E CADA UMA TEM MEDIÇÃO ATRÁS
------------------------------------------------------------------------

**1. Todos os cards têm a MESMA altura.** Um 8BitDo pede duas linhas que um
DualSense não pede (o modo e o rótulo dos botões). Sem igualar, a fileira lê como
erro de montagem. A receita tem duas metades, e as duas são necessárias:

* quem alinha cards LADO A LADO é cada card ter ``valign=FILL`` e
  ``vexpand=True`` — é o que faz o card ocupar a célula inteira em vez de
  encolher para o próprio conteúdo (o único grid de cards de hoje,
  ``status_actions.py:1308``, faz o OPOSTO, com ``Align.START``: lá eles ficam
  EMPILHADOS, e a EMPILHA-01 continua valendo naquela aba);
* quem alinha cards de LINHAS DIFERENTES é o ``row_homogeneous`` do
  ``Gtk.Grid``, que é da seção, não daqui.

E o seletor de jogador ancora no RODAPÉ de todos: entre a última declaração e ele
vai um ``Gtk.Box`` vazio com ``vexpand=True``, que é o ``margin-top:auto`` do
desenho (``mockup/aba-configuracoes.html:94``).

**2. Nada de ``Gtk.ComboBox``, e nada de ``Gtk.FlowBox``.** O combo está proibido
nesta casa desde o cosmic-epoch#2497 — o cosmic-comp rouba o foco no clique e
fecha o popup, e a pessoa não consegue escolher. O FlowBox é a armadilha irmã, já
paga e medida em ``segmented_selector.py:214-231``: ele decide as colunas pela
largura que RECEBE, o rolador lhe oferece a MÍNIMA, e ele reportou 606px de
altura empilhado — que o ``GtkNotebook`` adota como piso de TODAS as abas.

**3. Todo campo nasce em "Não sei".** ``limpar_ativo()`` deixa o seletor sem
botão marcado e NÃO emite "changed"; o valor inicial, quando existe, é posto
ANTES do ``connect``, porque ``set_active_id`` EMITE (espelha o ``GtkComboBox``) e
com o handler já ligado a abertura da janela gravaria sozinha o que ninguém
escolheu.
"""
from __future__ import annotations

import contextlib
from collections.abc import Callable
from dataclasses import dataclass, replace
from typing import Any

from hefesto_dualsense4unix.app.actions.external_controllers import (
    ID_DE_NAO_SEI,
    ID_DE_OUTRA_COR,
    MODE_SELECTOR_TOOLTIP,
    MODOS_DO_APARELHO,
    cores_do_plastico_items,
    dicas_das_cores,
    nome_oficial_da_cor,
)
from hefesto_dualsense4unix.utils.i18n import _

#: Quantos números de jogador o card oferece. Cinco, e não quatro: a mesa desta
#: casa é de cinco aparelhos (quatro DualSense mais o 8BitDo), e o desenho
#: aprovado mostra os cinco botões.
JOGADORES = 5

#: A dica de "Jogador:", literal do desenho aprovado (`TOOLTIPS.md`).
DICA_DO_JOGADOR = (
    "Fixa este controle num número de jogador. Sem nenhum marcado, vale a ordem "
    "de chegada — que é como o Hefesto trabalha por padrão."
)

#: A dica de "Modo:", literal do mesmo desenho. Ela fica no RÓTULO; o seletor
#: carrega a de `MODE_SELECTOR_TOOLTIP`, que é a mesma da ficha do controle —
#: importada, não copiada, para as duas telas nunca divergirem sobre o mesmo
#: fato (decisão T2).
DICA_DO_MODO = (
    "O modo é escolhido na chave física antes de ligar, e o controle não "
    "anuncia qual escolheram."
)

#: A dica do `?` ao lado de "Botões:". O rótulo dela fica SEM dica, e isso é
#: deliberado no desenho: quem quer entender o preço passa o mouse no `?`.
DICA_DOS_BOTOES = "Muda só o desenho que aparece na tela. Nada é remapeado no controle."

#: As dicas de "Cor:", uma por situação. Literais do desenho aprovado.
DICA_DA_COR_NO_CABO = (
    "Lida do próprio controle: o código da cor está no firmware, nos "
    "caracteres 5 e 6 do serial de fábrica."
)
DICA_DA_COR_NO_RADIO = "Lida do próprio controle, por cabo ou por rádio."
DICA_DA_COR_NAO_LIDA = (
    "O Hefesto não conseguiu ler a cor deste controle. Escolha na lista e a "
    "borda passa a usá-la."
)
DICA_DO_VALOR_NO_CABO = "Lida do aparelho pelo cabo. Nada a preencher."
DICA_DO_VALOR_NO_RADIO = (
    "Se o Hefesto não conseguir ler, este campo vira uma lista para você escolher."
)

#: A frase que aparece quando a escolha não sobrevive a fechar a janela. Ela
#: existe porque o `maquina.json` é indexado por endereço de doze hexa, e um
#: controle sem endereço estável (o MAC forjado que começa em `02`) não tem
#: chave — gravar seria fundir dois clones do mesmo modelo num só.
AVISO_SEM_ENDERECO = (
    "Este controle não tem endereço fixo, então a escolha vale só até fechar a "
    "janela."
)

#: O placeholder e o nome acessível do campo livre, literais do desenho.
PLACEHOLDER_DA_COR = "Diga a cor"
NOME_ACESSIVEL_DA_COR = "Nome da cor deste controle"

#: A dica do campo livre. Ela responde à armadilha do próprio desenho, que
#: sugeria digitar "Volcanic Red" — um nome que a casa JÁ conhece (é o código
#: `07` da tabela do firmware). O campo aceita qualquer coisa, e reconhece os
#: vinte e um nomes de fábrica quando é um deles.
DICA_DO_CAMPO_LIVRE = (
    "Vale qualquer nome. Se for um nome de fábrica que o Hefesto conhece, a "
    "borda já usa o tom dele."
)

#: Rótulos dos botões de "Botões:", com os ids do `ControleDeclarado.botoes`.
#: O terceiro NÃO é um id do schema: `ID_DE_NAO_SEI` é a palavra da tela para o
#: `None`, e o handler o traduz antes de declarar. Sem ele não havia gesto para
#: desfazer — grupo de rádio ignora o clique no botão já afundado.
BOTOES_DO_APARELHO: list[tuple[str, str]] = [
    ("xbox", "Xbox"),
    ("nintendo", "Nintendo"),
    (ID_DE_NAO_SEI, "Não sei"),
]

#: Largura mínima de um card, em pixels. Menos que isto e a lista de cor (três
#: colunas fixas) começa a quebrar rótulo de oito letras no meio.
LARGURA_MINIMA = 208


@dataclass(frozen=True)
class DadosDoControle:
    """Tudo que um card mostra, já resolvido — o widget não deduz nada.

    Separar assim não é cerimônia: é o que deixa a decisão de "o que este card
    diz" viver em função pura, testável sem GTK, e o widget cuidar só de
    desenhar. Todo campo tem um valor que significa "não sei", e nenhum deles é
    um valor de catálogo: string vazia ou ``None``.
    """

    #: Id estável do card — o que volta nos callbacks. Vem de `external_key`.
    chave: str
    #: "Jogador 3", ou a frase de quem ainda não tem número.
    titulo: str
    #: "8BitDo · Bluetooth".
    subtitulo: str
    #: O endereço que o `identity.number.set` recebe. "" = não dá para numerar.
    uniq: str = ""
    #: O número de jogador de hoje. `None` = o daemon ainda não opinou.
    slot: int | None = None
    #: O Hefesto adotou este controle? DualSense adotado não pede modo nem
    #: rótulo de botões: ele tem um desenho só.
    adotado: bool = False
    #: Id de `MODOS_DO_APARELHO`, ou "" para "não sei".
    modo: str = ""
    #: Id da lista de cor a marcar (código de fábrica, ou "outra"). "" = nenhum.
    cor_id: str = ""
    #: O nome que aparece na tela quando a cor foi LIDA do aparelho.
    cor_lida: str = ""
    #: O texto do campo livre, quando a escolha foi "Outra".
    cor_livre: str = ""
    #: O hexa da borda, já clareado para não sumir no fundo. "" = borda neutra.
    tom: str = ""
    #: "xbox" | "nintendo" | `None` (não declarado).
    botoes: str | None = None
    #: O controle chegou pelo cabo? Muda a dica de "Cor:", e só ela.
    no_cabo: bool = False
    #: A chave de doze hexa deste controle no `maquina.json`. "" = não há uma,
    #: e então a declaração não sobrevive a fechar a janela.
    endereco: str = ""
    #: Este é o controle marcado no cabeçalho da janela?
    selecionado: bool = False


#: `(chave do controle, campo, valor)` — valor `None` volta para "não sei".
AoDeclarar = Callable[[str, str, str | None], None]
#: `(uniq, número)`.
AoNumerar = Callable[[str, int], None]


# ---------------------------------------------------------------------------
# Resolução condicional de GTK (padrão da casa: real + stub)
# ---------------------------------------------------------------------------

try:
    import gi

    gi.require_version("Gtk", "3.0")
    from gi.repository import Gtk

    from hefesto_dualsense4unix.app.widgets.segmented_selector import SegmentedSelector

    # Com um stub parcial de `gi` (testes antigos, sem display), o import acima
    # passa mas faltam classes — o card cai no stub em vez de explodir.
    _GTK_DISPONIVEL = all(
        hasattr(Gtk, atributo)
        for atributo in ("Frame", "Box", "Label", "Entry", "Align", "Orientation")
    )
except (ImportError, ValueError):
    _GTK_DISPONIVEL = False


if _GTK_DISPONIVEL:

    class ExternalCard(Gtk.Frame):  # type: ignore[misc]
        """O card de um controle. Monta-se inteiro no construtor."""

        def __init__(
            self,
            dados: DadosDoControle,
            *,
            ao_declarar: AoDeclarar | None = None,
            ao_numerar: AoNumerar | None = None,
        ) -> None:
            Gtk.Frame.__init__(self)
            self.dados = dados
            self._ao_declarar = ao_declarar
            self._ao_numerar = ao_numerar
            self._campo_livre: Any = None
            self._bloco_da_cor: Any = None

            contexto = self.get_style_context()
            with contextlib.suppress(Exception):
                contexto.add_class("hefesto-dualsense4unix-card")
                contexto.add_class("hefesto-card-de-controle")
                if dados.selecionado:
                    contexto.add_class("hefesto-card-selecionado")
            _pintar_a_borda(self, dados.tom)

            # FILL + vexpand é metade da altura igual (ver o cabeçalho); a outra
            # metade é o `row_homogeneous` do grid da seção.
            self.set_valign(Gtk.Align.FILL)
            self.set_vexpand(True)
            self.set_hexpand(True)
            self.set_size_request(LARGURA_MINIMA, -1)

            corpo = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
            self.add(corpo)

            corpo.pack_start(_titulo(dados.titulo), False, False, 0)
            corpo.pack_start(_subtitulo(dados.subtitulo), False, False, 0)
            self._bloco_da_cor = self._linha_da_cor(dados)
            corpo.pack_start(self._bloco_da_cor, False, False, 0)
            if not dados.adotado:
                corpo.pack_start(self._linha_do_modo(dados), False, False, 0)
                corpo.pack_start(self._linha_dos_botoes(dados), False, False, 0)
            if not dados.endereco:
                corpo.pack_start(_apoio(AVISO_SEM_ENDERECO), False, False, 0)

            # O espaçador do desenho: é ele que empurra "Jogador:" para o rodapé
            # de TODOS os cards, inclusive os de duas linhas.
            respiro = Gtk.Box()
            respiro.set_vexpand(True)
            corpo.pack_start(respiro, True, True, 0)

            corpo.pack_start(self._linha_do_jogador(dados), False, False, 0)

        # -- as linhas -----------------------------------------------------

        def _linha_da_cor(self, dados: DadosDoControle) -> Any:
            """A cor: valor estático quando foi LIDA, lista quando não.

            A ordem das três situações é a decisão de quem manda: **a escolha
            dela vence a tabela e vence a leitura** (`docs/data/cores-do-plastico.md`,
            21/08/2026). Então:

            1. há cor DECLARADA → a lista, com a escolha dela marcada;
            2. não há, mas o aparelho respondeu → o valor, com a amostra ao lado
               e nada a preencher, como no desenho;
            3. nenhuma das duas → a lista, sem nada marcado. É o "não sei".
            """
            declarada = bool(dados.cor_id)
            if not declarada and dados.cor_lida:
                dica = DICA_DA_COR_NO_CABO if dados.no_cabo else DICA_DA_COR_NO_RADIO
                caixa = _bloco("Cor:", dica)
                valor = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
                if dados.tom:
                    valor.pack_start(_amostra(dados.tom), False, False, 0)
                nome = Gtk.Label(label=dados.cor_lida)
                nome.set_xalign(0.0)
                valor.pack_start(nome, False, False, 0)
                valor.pack_start(
                    _ajuda(
                        DICA_DO_VALOR_NO_CABO if dados.no_cabo else DICA_DO_VALOR_NO_RADIO
                    ),
                    False,
                    False,
                    0,
                )
                caixa.pack_start(valor, False, False, 0)
                return caixa

            caixa = _bloco("Cor:", DICA_DA_COR_NAO_LIDA)
            seletor = SegmentedSelector(wrap=True)
            seletor.set_items(
                [(ident, _(rotulo)) for ident, rotulo in cores_do_plastico_items()]
            )
            # Os seis nomes de fábrica NÃO passam por `_()`: "Cosmic Red" é o
            # que está escrito na caixa e no serial do aparelho, e traduzi-lo
            # inventaria um nome que a Sony não usa e que não casa com nenhuma
            # outra fonte. As frases do "Outra" e do "Não sei" são redação
            # nossa, e passam.
            dicas = dicas_das_cores()
            dicas[ID_DE_OUTRA_COR] = _(dicas[ID_DE_OUTRA_COR])
            dicas[ID_DE_NAO_SEI] = _(dicas[ID_DE_NAO_SEI])
            seletor.set_tooltips(dicas)
            # ANTES do connect: `set_active_id` emite "changed", e com o handler
            # ligado a montagem gravaria sozinha o que ninguém escolheu.
            if dados.cor_id:
                with contextlib.suppress(Exception):
                    seletor.set_active_id(dados.cor_id)
            else:
                seletor.limpar_ativo()
            seletor.connect("changed", self._ao_escolher_cor)
            caixa.pack_start(seletor, False, False, 0)

            campo = Gtk.Entry()
            campo.set_placeholder_text(_(PLACEHOLDER_DA_COR))
            campo.set_tooltip_text(_(DICA_DO_CAMPO_LIVRE))
            campo.set_width_chars(12)
            with contextlib.suppress(Exception):
                campo.get_accessible().set_name(_(NOME_ACESSIVEL_DA_COR))
            if dados.cor_livre:
                campo.set_text(dados.cor_livre)
            campo.connect("changed", self._ao_digitar_a_cor)
            # `no_show_all` para o `show_all()` da aba não revelar o campo de
            # todo card: ele só existe quando ela escolhe "Outra".
            campo.set_no_show_all(True)
            campo.set_visible(dados.cor_id == ID_DE_OUTRA_COR)
            self._campo_livre = campo
            caixa.pack_start(campo, False, False, 0)
            return caixa

        def _linha_do_modo(self, dados: DadosDoControle) -> Any:
            """O modo DEDUZIDO, em seletor INSENSÍVEL — decisões T1, T2 e T3.

            Insensível porque a troca não é por software: é um combo de botões
            no próprio controle, ao ligar. A dica que diz isso é a MESMA da ficha
            do controle, importada de `external_controllers` — se um dia ela
            mudar, muda nos dois lugares de uma vez.
            """
            caixa = _bloco("Modo:", DICA_DO_MODO)
            seletor = SegmentedSelector(wrap=True)
            seletor.set_items([(ident, _(rotulo)) for ident, rotulo in MODOS_DO_APARELHO])
            if dados.modo:
                with contextlib.suppress(Exception):
                    seletor.set_active_id(dados.modo)
            else:
                seletor.limpar_ativo()
            seletor.set_sensitive(False)
            seletor.set_tooltip_text(_(MODE_SELECTOR_TOOLTIP))
            caixa.pack_start(seletor, False, False, 0)
            return caixa

        def _linha_dos_botoes(self, dados: DadosDoControle) -> Any:
            """O desenho dos botões na tela — preferência dela, não do aparelho."""
            caixa = _bloco("Botões:", None)
            fileira = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
            seletor = _deitado()
            seletor.set_items([(ident, _(rotulo)) for ident, rotulo in BOTOES_DO_APARELHO])
            if dados.botoes:
                with contextlib.suppress(Exception):
                    seletor.set_active_id(dados.botoes)
            else:
                seletor.limpar_ativo()
            seletor.connect("changed", self._ao_escolher_botoes)
            fileira.pack_start(seletor, True, True, 0)
            fileira.pack_start(_ajuda(DICA_DOS_BOTOES), False, False, 0)
            caixa.pack_start(fileira, False, False, 0)
            return caixa

        def _linha_do_jogador(self, dados: DadosDoControle) -> Any:
            """Os cinco números, ancorados no rodapé de todo card."""
            caixa = _bloco("Jogador:", DICA_DO_JOGADOR)
            seletor = _deitado()
            seletor.set_items([(str(n), str(n)) for n in range(1, JOGADORES + 1)])
            if dados.slot is not None and 1 <= dados.slot <= JOGADORES:
                with contextlib.suppress(Exception):
                    seletor.set_active_id(str(dados.slot))
            else:
                seletor.limpar_ativo()
            seletor.set_sensitive(bool(dados.uniq))
            seletor.connect("changed", self._ao_escolher_jogador)
            caixa.pack_start(seletor, False, False, 0)
            return caixa

        # -- gestos --------------------------------------------------------

        def _ao_escolher_cor(self, seletor: Any) -> None:
            escolha = seletor.get_active_id()
            if self._campo_livre is not None:
                self._campo_livre.set_visible(escolha == ID_DE_OUTRA_COR)
            if escolha == ID_DE_NAO_SEI:
                # Cedo e explícito: cair no `nome_oficial_da_cor` abaixo daria
                # `None` por acidente (o id não é código de cor nenhum), e um
                # acerto por acidente some na primeira mudança daquela função.
                self._declarar("cor", None)
                return
            if escolha == ID_DE_OUTRA_COR:
                texto = "" if self._campo_livre is None else self._campo_livre.get_text()
                self._declarar("cor", texto.strip() or None)
                return
            self._declarar("cor", nome_oficial_da_cor(escolha or ""))

        def _ao_digitar_a_cor(self, campo: Any) -> None:
            self._declarar("cor", campo.get_text().strip() or None)

        def _ao_escolher_botoes(self, seletor: Any) -> None:
            escolha = seletor.get_active_id()
            self._declarar("botoes", None if escolha == ID_DE_NAO_SEI else escolha)

        def _ao_escolher_jogador(self, seletor: Any) -> None:
            """Pede o número ao daemon — e NÃO pinta nada por conta própria.

            É a mesma disciplina do chip da aba Status
            (`status_actions.py:1854-1868`): quem repinta é a resposta do
            daemon, no refresh seguinte. A janela mostrar o número novo antes de
            o daemon confirmar é como se cria a terceira verdade.
            """
            escolha = seletor.get_active_id()
            if self._ao_numerar is None or not escolha or not self.dados.uniq:
                return
            with contextlib.suppress(ValueError):
                self._ao_numerar(self.dados.uniq, int(escolha))

        def _declarar(self, campo: str, valor: str | None) -> None:
            if self._ao_declarar is not None:
                self._ao_declarar(self.dados.chave, campo, valor)

        # -- repintura pontual ---------------------------------------------

        def repintar_a_borda(self, tom: str) -> None:
            """Troca a cor da borda sem redesenhar o card.

            Duas coisas chegam depois da montagem e mudam esta cor: a resposta
            do aparelho, que leva segundos, e o clique dela na lista. Redesenhar
            o card em qualquer um dos dois casos tiraria o foco de quem
            estivesse digitando no campo livre — que é justamente o gesto em
            curso no segundo caso.

            O `dados.tom` acompanha, e não é arrumação: `repintar_o_nome_da_cor`
            REMONTA o bloco da cor a partir de `self.dados`, e sem esta linha a
            amostra ao lado do nome nasceria sem cor — medido em 22/08/2026, o
            quadradinho sumia justamente no card em que a leitura tinha dado
            certo.
            """
            self.dados = replace(self.dados, tom=tom)
            _pintar_a_borda(self, tom)

        def repintar_o_nome_da_cor(self, nome: str) -> None:
            """Põe na tela o nome que o aparelho respondeu, no lugar da lista.

            Enquanto a resposta não chega, o card mostra a lista de escolha —
            que é o "não sei" honesto. Quando ela chega, a linha vira o valor
            lido, como no desenho.
            """
            if not nome or self.dados.cor_id:
                return
            self.dados = replace(self.dados, cor_lida=nome)
            self._remontar_a_cor()

        def _remontar_a_cor(self) -> None:
            """Refaz só o bloco da cor, no lugar em que ele estava."""
            corpo = self.get_child()
            if corpo is None or self._bloco_da_cor is None:
                return
            posicao = corpo.get_children().index(self._bloco_da_cor)
            corpo.remove(self._bloco_da_cor)
            self._bloco_da_cor.destroy()
            self._campo_livre = None
            self._bloco_da_cor = self._linha_da_cor(self.dados)
            corpo.pack_start(self._bloco_da_cor, False, False, 0)
            corpo.reorder_child(self._bloco_da_cor, posicao)
            self._bloco_da_cor.show_all()

    # -- peças de montagem, todas privadas ---------------------------------

    def _titulo(texto: str) -> Any:
        rotulo = Gtk.Label(label=_(texto))
        rotulo.set_xalign(0.0)
        rotulo.set_line_wrap(True)
        rotulo.set_max_width_chars(20)
        with contextlib.suppress(Exception):
            rotulo.get_style_context().add_class("hefesto-rotulo-secao")
        return rotulo

    def _subtitulo(texto: str) -> Any:
        rotulo = Gtk.Label(label=texto)
        rotulo.set_xalign(0.0)
        rotulo.set_line_wrap(True)
        rotulo.set_max_width_chars(20)
        with contextlib.suppress(Exception):
            rotulo.get_style_context().add_class("hefesto-valor-mono-peq")
        return rotulo

    def _apoio(texto: str) -> Any:
        rotulo = Gtk.Label(label=_(texto))
        rotulo.set_xalign(0.0)
        rotulo.set_line_wrap(True)
        rotulo.set_max_width_chars(24)
        with contextlib.suppress(Exception):
            rotulo.get_style_context().add_class("dim-label")
        return rotulo

    def _bloco(titulo: str, dica: str | None) -> Any:
        """Rótulo EM CIMA e controle embaixo — a fileira do card é vertical.

        Diferente das fileiras das outras seções, que são deitadas: um card tem
        cerca de 210px de largura, e "Jogador:" mais cinco botões lado a lado não
        cabem. O desenho já faz assim (`.ctrl .linha { display:block }`).
        """
        caixa = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        caixa.set_margin_top(6)
        rotulo = Gtk.Label(label=_(titulo))
        rotulo.set_xalign(0.0)
        if dica is not None:
            rotulo.set_tooltip_text(_(dica))
        with contextlib.suppress(Exception):
            rotulo.get_style_context().add_class("hefesto-rotulo")
        caixa.pack_start(rotulo, False, False, 0)
        return caixa

    # NOTA DATADA — 23/08/2026: os seletores deste card SAÍRAM da classe
    # `hefesto-seletor-compacto`.
    #
    # A medição que a pôs aqui continua valendo (02/08/2026, SOM-CANAL-01: o
    # `SegmentedSelector` pede 67px contra os 34px de um botão comum, e a
    # diferença é só padding) — não foi ela que caducou. O que a derrubou foi
    # uma medição NOVA: este era o único lugar da aba a usar DUAS gramáticas de
    # seletor ao mesmo tempo, e a aba saía com CINCO alturas de botão
    # (22/24/26/32/38px) contra UMA das abas Início e Perfis. Sem a classe são
    # três, e a fileira volta a ler como a mesma janela. Altura se recupera com
    # rolagem; gramática visual quebrada, não.
    #
    # A classe segue no tema e segue em uso em `controller_card.py` — o que
    # mudou é este card, não a receita.

    def _deitado() -> Any:
        """Um `SegmentedSelector` com os botões numa fileira só.

        Sem `wrap` o widget é um `Gtk.Box` VERTICAL (`segmented_selector.py:206`)
        e empilha as opções — foi assim que "Sons do jogo / Todo o som do PC"
        saiu empilhado em `docs/usage/assets/readme_status.png`. Com `wrap` ele
        vira grade de TRÊS colunas fixas, e cinco números virariam duas fileiras
        de altura para caber `[1][2][3] / [4][5]`.

        Trocar a orientação é a receita que `secao_mesa.py:257` já usa: uma
        fileira deitada de itens curtos, sem gastar altura, e sem mexer no padrão
        do widget — que cinco outras telas dependem dele como está.

        Vale só para item CURTO. "Modo:" e "Cor:" continuam com `wrap`: quatro e
        sete rótulos de palavra inteira lado a lado passariam da largura de um
        card de 208px, e a largura é o recurso escasso desta janela.
        """
        seletor = SegmentedSelector()
        seletor.set_orientation(Gtk.Orientation.HORIZONTAL)
        return seletor

    def _ajuda(dica: str) -> Any:
        """O `?` do desenho: recebe foco pelo teclado, porque a dica é a única
        fonte daquela informação."""
        rotulo = Gtk.Label(label="?")
        rotulo.set_tooltip_text(_(dica))
        with contextlib.suppress(Exception):
            rotulo.get_style_context().add_class("dim-label")
        return rotulo

    def _amostra(tom: str) -> Any:
        """O quadradinho da cor, 13x13 como no desenho."""
        caixa = Gtk.Box()
        caixa.set_size_request(13, 13)
        caixa.set_valign(Gtk.Align.CENTER)
        with contextlib.suppress(Exception):
            caixa.get_style_context().add_class("hefesto-amostra-de-cor")
        _aplicar_css(caixa, f".hefesto-amostra-de-cor {{ background-color: {tom}; }}")
        return caixa

    def _pintar_a_borda(card: Any, tom: str) -> None:
        """A borda na cor do plástico, por `Gtk.CssProvider` POR WIDGET.

        Não dá para fazer isto na folha global: a restrição 6 da leva proíbe hex
        solto no `theme.css` (só os vinte tokens `@define-color`), e a cor do
        plástico é um hex DIFERENTE por controle. O mecanismo é o de
        `utils/color_contrast.tintar_progressbar` — provider por widget, com
        cache anti-rebuild —, mas o CSS dele é fixo em `progressbar trough` e não
        serve direto numa `Gtk.Frame`.

        Tom vazio não põe provider nenhum: fica a borda neutra do tema, que é
        como o card diz "não sei de que cor este controle é".
        """
        if not tom:
            return
        _aplicar_css(card, f".hefesto-card-de-controle {{ border-color: {tom}; }}")

    def _aplicar_css(widget: Any, css: str) -> None:
        """Prega um provider no contexto DESTE widget, e só nele.

        Cache pelo próprio CSS: repintar com a mesma cor é no-op, e sem isso um
        refresh empilharia provider a cada entrada na aba.
        """
        if getattr(widget, "_hefesto_css", None) == css:
            return
        with contextlib.suppress(Exception):
            provider = Gtk.CssProvider()
            provider.load_from_data(css.encode("utf-8"))
            contexto = widget.get_style_context()
            anterior = getattr(widget, "_hefesto_css_provider", None)
            if anterior is not None:
                contexto.remove_provider(anterior)
            contexto.add_provider(provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
            widget._hefesto_css_provider = provider
            widget._hefesto_css = css

else:

    class ExternalCard:  # type: ignore[no-redef]
        """Stub para ambientes sem GTK3 (testes puros, CI sem PyGObject).

        Guarda os dados — o suficiente para asserção de contrato sem toolkit.
        """

        def __init__(
            self,
            dados: DadosDoControle,
            *,
            ao_declarar: AoDeclarar | None = None,
            ao_numerar: AoNumerar | None = None,
        ) -> None:
            self.dados = dados
            self._ao_declarar = ao_declarar
            self._ao_numerar = ao_numerar

        def repintar_a_borda(self, tom: str) -> None:
            self.tom = tom

        def repintar_o_nome_da_cor(self, nome: str) -> None:
            self.dados = replace(self.dados, cor_lida=nome)


__all__ = ["JOGADORES", "LARGURA_MINIMA", "DadosDoControle", "ExternalCard"]
