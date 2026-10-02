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
  ``status_actions.py:815``, faz o OPOSTO, com ``Align.START``: lá eles ficam
  EMPILHADOS, e a EMPILHA-01 continua valendo naquela aba);
* quem alinha cards de LINHAS DIFERENTES é o ``row_homogeneous`` do
  ``Gtk.Grid``, que é da seção, não daqui.

E o seletor de jogador ancora no RODAPÉ de todos: entre a última declaração e ele
vai um ``Gtk.Box`` vazio com ``vexpand=True``, que é o ``margin-top:auto`` do
desenho (``mockup/aba-configuracoes.html:94``).

**2. Nada de ``Gtk.ComboBox``, e nada de ``Gtk.FlowBox``.** O combo está proibido
nesta casa desde o cosmic-epoch#2497 — o cosmic-comp rouba o foco no clique e
fecha o popup, e a pessoa não consegue escolher. O FlowBox é a armadilha irmã, já
paga e medida em ``segmented_selector.py:131-148``: ele decide as colunas pela
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
    cores_para_busca,
    dicas_da_busca,
    nome_oficial_da_cor,
    sinonimos_da_busca,
)
from hefesto_dualsense4unix.app.fala_do_mapa import AFIRMA_NADA, Fala, frase_de_exibicao
from hefesto_dualsense4unix.utils.i18n import _

#: casa é de cinco aparelhos (quatro DualSense mais o 8BitDo), e o desenho
JOGADORES = 5

DICA_DO_JOGADOR = (
    "Fixa este controle num número de jogador. Sem nenhum marcado, vale a ordem "
    "de chegada — que é como o Hefesto trabalha por padrão."
)

DICA_DO_MODO = (
    "O modo é escolhido na chave física antes de ligar, e o controle não "
    "anuncia qual escolheram."
)

DICA_DOS_BOTOES = "Muda só o desenho que aparece na tela. Nada é remapeado no controle."

DICA_DA_COR_NO_CABO = (
    "Lida do próprio controle: o código da cor está no firmware, nos "
    "caracteres 5 e 6 do serial de fábrica."
)
#: cuja `radio_por_que_nao_aciona` passou de `o-aparelho-recusa` para `divida`.
#: CLASSE DE TELA: esta dica é TOOLTIP (`_bloco` -> `set_tooltip_text`), não
DICA_DA_COR_NO_RADIO = Fala(
    chave="identidade.cor_do_aparelho@dualsense",
    lado="radio",
    aba="Configurações",
    texto="Pelo rádio a cor do plástico vem da lista. Escolha a sua.",
    afirma=AFIRMA_NADA,
    porque=(
        "o aparelho responde por rádio — medido em 27/08/2026 com a semente "
        "0x53 —, e quem ainda não pede somos nós: três portões do próprio "
        "Hefesto recusam antes de o byte sair (ONDA-CONEXOES-11)"
    ),
)
DICA_DA_COR_NAO_LIDA = (
    "O Hefesto não conseguiu ler a cor deste controle. Escolha na lista e a "
    "borda passa a usá-la."
)
DICA_DO_VALOR_NO_CABO = "Lida do aparelho pelo cabo. Nada a preencher."
DICA_DO_VALOR_NO_RADIO = (
    "Se o Hefesto não conseguir ler, este campo vira uma lista para você escolher."
)

AVISO_SEM_ENDERECO = (
    "Este controle não tem endereço fixo, então a escolha vale só até fechar a "
    "janela."
)

PLACEHOLDER_DA_COR = "Diga a cor"
NOME_ACESSIVEL_DA_COR = "Nome da cor deste controle"

PLACEHOLDER_DA_BUSCA = "Escreva a cor"

CORRIGIR_A_COR = "Corrigir"

SELO_LIDO = "(lido)"

_ROTULOS_NOSSOS = frozenset({ID_DE_OUTRA_COR, ID_DE_NAO_SEI})

DICA_DO_CAMPO_LIVRE = (
    "Vale qualquer nome. Se for um nome de fábrica que o Hefesto conhece, a "
    "borda já usa o tom dele."
)

#: O terceiro NÃO é um id do schema: `ID_DE_NAO_SEI` é a palavra da tela para o
BOTOES_DO_APARELHO: list[tuple[str, str]] = [
    ("xbox", "Xbox"),
    ("nintendo", "Nintendo"),
    (ID_DE_NAO_SEI, "Não sei"),
]

LARGURA_MINIMA = 208


@dataclass(frozen=True)
class DadosDoControle:
    """Tudo que um card mostra, já resolvido — o widget não deduz nada."""

    chave: str
    titulo: str
    subtitulo: str
    uniq: str = ""
    slot: int | None = None
    #: O Hefesto adotou este controle? DualSense adotado não pede modo nem
    adotado: bool = False
    modo: str = ""
    cor_id: str = ""
    cor_lida: str = ""
    cor_livre: str = ""
    tom: str = ""
    botoes: str | None = None
    no_cabo: bool = False
    endereco: str = ""
    selecionado: bool = False


AoDeclarar = Callable[[str, str, str | None], None]
AoNumerar = Callable[[str, int], None]


try:
    import gi

    gi.require_version("Gtk", "3.0")
    from gi.repository import Gtk

    from hefesto_dualsense4unix.app.widgets.campo_de_busca import CampoDeBusca
    from hefesto_dualsense4unix.app.widgets.segmented_selector import SegmentedSelector

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

            respiro = Gtk.Box()
            respiro.set_vexpand(True)
            corpo.pack_start(respiro, True, True, 0)

            corpo.pack_start(self._linha_do_jogador(dados), False, False, 0)


        def _linha_da_cor(self, dados: DadosDoControle) -> Any:
            """A cor: valor LIDO quando o aparelho respondeu, busca quando não.

            A ordem das três situações é a decisão de quem manda: **a escolha
            dela vence a tabela e vence a leitura** (`docs/data/cores-do-plastico.md`,
            21/08/2026). Então:

            1. há cor DECLARADA → a busca, com a escolha dela escrita no campo;
            2. não há, mas o aparelho respondeu → o valor, com a amostra, o selo
               `(lido)` e um "Corrigir" que abre a busca;
            3. nenhuma das duas → a busca, com o campo vazio. É o "não sei".

            A BUSCA SUBSTITUIU OITO BOTÕES EM TRÊS FILEIRAS (LEX-5, 25/08/2026).
            O que estava na tela era um `SegmentedSelector(wrap=True)` de seis
            cores mais "Outra" e "Não sei" — grade de três colunas fixas, três
            fileiras. Medido lado a lado na foto de 24/08: a barra "A luz não
            acende" nascia mais baixa nos cards do rádio (que mostravam a grade)
            do que nos do cabo (que mostravam a cor lida numa linha), e como o
            grid da seção iguala as fileiras (`row_homogeneous`), um card com
            grade encarecia a fileira inteira.

            **Por que os dois desenhos continuam diferentes** — e a razão
            MUDOU em 29/08/2026, embora o desenho não. Até aqui esta nota dizia
            que o cabo respondia e o rádio não, porque o `SET_FEATURE 0x80`
            devolvia `EIO`. Medido: o APARELHO responde nos dois transportes
            (cabo, 4 de 4 unidades em 15/08/2026; rádio, uma unidade em
            27/08/2026, depois de a semente do CRC ser corrigida para `0x53`).
            Quem não pergunta é o PRODUTO, e só do lado do rádio: três portões
            nossos recusam antes de o byte sair.
            `docs/data/mapa-controles.csv:111`
            (`identidade.cor_do_aparelho@dualsense`) diz hoje `cabo_aciona=sim`
            e `radio_aciona=não`, com `divida` no rádio.

            **E o cabo esteve quebrado sem esta nota saber, de 22/08 a
            29/08/2026:** a célula dizia `sim` porque o ENSAIO lia, e o produto
            abria o nó com `os.open` direto num nó que o BROKER-01 deixa
            `0600 root:root` — EACCES, e "Não sei" na tela. A cura (pedir o fd
            ao broker) entrou em 29/08.

            O desenho fica como está: no rádio a busca é o único caminho, e é
            ela que está na tela.
            """
            declarada = bool(dados.cor_id)
            if not declarada and dados.cor_lida:
                dica = (
                    DICA_DA_COR_NO_CABO
                    if dados.no_cabo
                    else frase_de_exibicao(DICA_DA_COR_NO_RADIO)
                )
                caixa = _bloco("Cor:", dica)
                valor = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
                if dados.tom:
                    valor.pack_start(_amostra(dados.tom), False, False, 0)
                nome = Gtk.Label(label=dados.cor_lida)
                nome.set_xalign(0.0)
                valor.pack_start(nome, False, False, 0)
                selo = Gtk.Label(label=_(SELO_LIDO))
                selo.set_xalign(0.0)
                with contextlib.suppress(Exception):
                    selo.get_style_context().add_class("dim-label")
                valor.pack_start(selo, False, False, 0)
                valor.pack_start(
                    _ajuda(
                        DICA_DO_VALOR_NO_CABO if dados.no_cabo else DICA_DO_VALOR_NO_RADIO
                    ),
                    False,
                    False,
                    0,
                )
                caixa.pack_start(valor, False, False, 0)

                busca = self._busca_da_cor(dados)
                busca.set_no_show_all(True)
                busca.set_visible(False)
                corrigir = Gtk.Button(label=_(CORRIGIR_A_COR))
                corrigir.set_halign(Gtk.Align.START)
                corrigir.connect(
                    "clicked", lambda botao: _revelar(botao, busca)
                )
                caixa.pack_start(corrigir, False, False, 0)
                caixa.pack_start(busca, False, False, 0)
                caixa.pack_start(self._campo_livre_da_cor(dados), False, False, 0)
                return caixa

            caixa = _bloco("Cor:", DICA_DA_COR_NAO_LIDA)
            caixa.pack_start(self._busca_da_cor(dados), False, False, 0)
            caixa.pack_start(self._campo_livre_da_cor(dados), False, False, 0)
            return caixa

        def _campo_livre_da_cor(self, dados: DadosDoControle) -> Any:
            """A caixa de escrever o nome, para quando nada na lista serve."""
            campo = Gtk.Entry()
            campo.set_placeholder_text(_(PLACEHOLDER_DA_COR))
            campo.set_tooltip_text(_(DICA_DO_CAMPO_LIVRE))
            campo.set_width_chars(12)
            with contextlib.suppress(Exception):
                campo.get_accessible().set_name(_(NOME_ACESSIVEL_DA_COR))
            if dados.cor_livre:
                campo.set_text(dados.cor_livre)
            campo.connect("changed", self._ao_digitar_a_cor)
            campo.set_no_show_all(True)
            campo.set_visible(dados.cor_id == ID_DE_OUTRA_COR)
            self._campo_livre = campo
            return campo

        def _busca_da_cor(self, dados: DadosDoControle) -> Any:
            """O campo de busca da cor, montado e já com a escolha dentro."""
            busca = CampoDeBusca(
                placeholder=PLACEHOLDER_DA_BUSCA,
                nome_acessivel=NOME_ACESSIVEL_DA_COR,
            )
            busca.set_items(
                [
                    (ident, _(rotulo) if ident in _ROTULOS_NOSSOS else rotulo)
                    for ident, rotulo in cores_para_busca()
                ]
            )
            dicas = dicas_da_busca()
            for ident in _ROTULOS_NOSSOS:
                if ident in dicas:
                    dicas[ident] = _(dicas[ident])
            busca.set_tooltips(dicas)
            busca.set_sinonimos(
                {ident: _(rotulo) for ident, rotulo in sinonimos_da_busca().items()}
            )
            if dados.cor_id:
                with contextlib.suppress(Exception):
                    busca.set_active_id(dados.cor_id)
            else:
                busca.limpar_ativo()
            busca.connect("changed", self._ao_escolher_cor)
            return busca

        def _linha_do_modo(self, dados: DadosDoControle) -> Any:
            """O modo DEDUZIDO, em seletor INSENSÍVEL — decisões T1, T2 e T3."""
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


        def _ao_escolher_cor(self, seletor: Any) -> None:
            escolha = seletor.get_active_id()
            if self._campo_livre is not None:
                self._campo_livre.set_visible(escolha == ID_DE_OUTRA_COR)
            if escolha == ID_DE_NAO_SEI:
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
            """Pede o número ao daemon — e NÃO pinta nada por conta própria."""
            escolha = seletor.get_active_id()
            if self._ao_numerar is None or not escolha or not self.dados.uniq:
                return
            with contextlib.suppress(ValueError):
                self._ao_numerar(self.dados.uniq, int(escolha))

        def _declarar(self, campo: str, valor: str | None) -> None:
            if self._ao_declarar is not None:
                self._ao_declarar(self.dados.chave, campo, valor)


        def repintar_a_borda(self, tom: str) -> None:
            """Troca a cor da borda sem redesenhar o card."""
            self.dados = replace(self.dados, tom=tom)
            _pintar_a_borda(self, tom)

        def repintar_o_nome_da_cor(self, nome: str) -> None:
            """Põe na tela o nome que o aparelho respondeu, no lugar da lista."""
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
        """Rótulo EM CIMA e controle embaixo — a fileira do card é vertical."""
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


    def _deitado() -> Any:
        """Um `SegmentedSelector` com os botões numa fileira só."""
        seletor = SegmentedSelector()
        seletor.set_orientation(Gtk.Orientation.HORIZONTAL)
        return seletor

    def _revelar(botao: Any, alvo: Any) -> None:
        """Mostra a busca escondida e apaga o botão que a chamou."""
        with contextlib.suppress(Exception):
            alvo.set_no_show_all(False)
            alvo.show_all()
            botao.set_visible(False)
            entrada = getattr(alvo, "get_entrada", None)
            if entrada is not None:
                entrada().grab_focus()

    def _ajuda(dica: str) -> Any:
        """O `?` do desenho: recebe foco pelo teclado, porque a dica é a única"""
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
        """A borda na cor do plástico, por `Gtk.CssProvider` POR WIDGET."""
        if not tom:
            return
        _aplicar_css(card, f".hefesto-card-de-controle {{ border-color: {tom}; }}")

    def _aplicar_css(widget: Any, css: str) -> None:
        """Prega um provider no contexto DESTE widget, e só nele."""
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
        """Stub para ambientes sem GTK3 (testes puros, CI sem PyGObject)."""

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
