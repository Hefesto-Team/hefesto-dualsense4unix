"""campo_de_busca.py — escolher numa lista LONGA digitando, e sem popup.

POR QUE ELE EXISTE, e o número é a razão inteira: a tabela de cores de fábrica
do DualSense tem **vinte e uma** entradas (``integrations/cor_do_plastico.py``,
``NOMES_DE_FABRICA``) e a aba Configurações mostrava **seis**, num
``SegmentedSelector(wrap=True)`` — grade de três colunas fixas, logo três
fileiras de botões por card. Ela: *"o user começa a escrever o nome do controle
dele, se é Cosmic Red ou Galactic Purple, aí a lista sugere"*.

O recorte de seis não era arbitrário (``00``-``05`` são as cores de catálogo),
mas era um recorte — e quem tem uma edição especial ficava fora da lista, no
campo livre, digitando um nome que a casa já conhece. Uma busca resolve as duas
pontas de uma vez: cabem as vinte e uma, e a altura do card deixa de crescer com
o tamanho da tabela.

**NADA DE POPUP, E A PROIBIÇÃO É MEDIDA.** ``Gtk.ComboBox`` está proibido nesta
casa desde o cosmic-epoch#2497 — o cosmic-comp rouba o foco no clique e fecha o
popup, e a pessoa não consegue escolher. O contorno seria forçar XWayland, e
``app/main.py:58-64`` registra que em 24/08/2026 a bancada mediu a janela **não
abrir** sob ``GDK_BACKEND=x11`` sem XWayland vivo. ``Gtk.EntryCompletion``
**é um popup** e cairia no mesmo buraco por outro caminho: seria apostar a cura
contra um bug já pago. Por isso a lista deste widget é um ``Gtk.ListBox``
empacotado DENTRO do próprio widget, que cresce a caixa em vez de flutuar sobre
ela.

A ALTURA É LIMITADA, e o limite não é estética: sem teto, digitar uma letra que
casa com vinte nomes empurraria o card inteiro para baixo e a fileira de cards
junto com ele (``Gtk.Grid`` com ``row_homogeneous``, ``secao_controles.py:1056``,
iguala as fileiras — um card alto encarece a fileira toda). Seis linhas é o teto,
e o rolador aparece só quando ele é atingido.

A API É A DO ``SegmentedSelector``, de propósito: ``set_items``,
``get_active_id``, ``set_active_id``, ``set_tooltips``, ``limpar_ativo`` e o
sinal ``changed``. É o que permite trocar um pelo outro num call site sem mexer
na lógica dele — e é a mesma API por-ID do ``GtkComboBoxText`` que esta casa
já espelha em dois widgets.

A LÓGICA POR-ID É IMPORTADA, NÃO COPIADA. ``_SegmentedLogic`` guarda a semântica
que importa e que é fácil de errar — ``set_items`` idempotente que preserva o
ativo, ``set_active_id`` que só emite quando o id MUDA, ``limpar_ativo`` que não
emite porque é populate e não gesto. Duas cópias dessa semântica divergiriam na
primeira correção, e a divergência apareceria como "a janela gravou sozinha o
que ninguém escolheu", que é o defeito que aquele arquivo documenta em três
lugares.
"""
from __future__ import annotations

import contextlib
import unicodedata
from collections.abc import Callable
from typing import Any, ClassVar

from hefesto_dualsense4unix.app.widgets.segmented_selector import _SegmentedLogic
from hefesto_dualsense4unix.utils.i18n import _

#: Quantas linhas de sugestão cabem antes de a lista virar rolador. Ver a
#: explicação da altura no topo — é teto de card, não gosto.
LINHAS_VISIVEIS = 6

#: Altura de referência de uma linha da lista, em pixels. Só é usada para
#: calcular o teto do rolador; o GTK mede a linha de verdade e o teto vira o
#: menor dos dois.
_ALTURA_DA_LINHA = 28

#: A frase do beco sem saída: digitou algo que não casa com nome nenhum. Sem
#: ela a lista simplesmente some, e sumir é indistinguível de "o campo quebrou".
#:
#: PROVISÓRIO — decisão dela (PROVA-DE-TELA-01). Texto novo de tela.
SEM_RESULTADO = "Nenhum nome com essas letras."


def achatar(texto: str) -> str:
    """O texto sem acento e em minúscula, para a busca casar como ela digita.

    Quem procura "cosmic" tem de achar "Cosmic Red", e quem procura "purpura"
    não pode ser punido por não ter digitado o acento. A comparação é por
    SUBSTRING e não por prefixo: os nomes de fábrica trazem a cor no fim tantas
    vezes quanto no começo ("Nova Pink", "Icon Blue Limited Edition"), e uma
    busca por prefixo esconderia metade da tabela de quem digita a cor.
    """
    sem_marca = "".join(
        caractere
        for caractere in unicodedata.normalize("NFD", texto)
        if unicodedata.category(caractere) != "Mn"
    )
    return sem_marca.casefold().strip()


class _BuscaLogic(_SegmentedLogic):
    """A lógica por-ID do ``SegmentedSelector`` mais o filtro por texto."""

    _sinonimos: dict[str, str]

    def set_sinonimos(self, sinonimos: dict[str, str]) -> None:
        """Palavras que também ACHAM um item, sem nunca aparecer na tela.

        ELAS EXISTEM POR UMA REGRESSÃO QUE A BUSCA CRIARIA SEM ELAS. A lista de
        botões que a busca substituiu mostrava seis rótulos em português —
        "Branco", "Preto", "Vermelho", "Rosa", "Roxo", "Azul" —, e os nomes de
        fábrica são todos em inglês. Quem sabe o nome do próprio controle digita
        "Cosmic Red" e acha; quem só sabe que *é vermelho* digitaria "vermelho"
        e não acharia nada — e essa pessoa era justamente a que a lista de seis
        botões atendia.

        O sinônimo casa, mas não se mostra: a linha continua dizendo "Cosmic
        Red", que é o que está escrito na caixa e no serial. Trocar o rótulo
        pelo sinônimo inventaria um nome que a Sony não usa, que é a decisão de
        21/08/2026 sobre esta tabela.
        """
        self._sinonimos = dict(sinonimos)

    def filtrados(self, digitado: str) -> list[tuple[str, str]]:
        """Os itens que casam com o que foi digitado, no teto de linhas.

        Campo vazio devolve lista vazia, e não a lista inteira: a lista só
        existe enquanto há texto. Mostrar as vinte e uma ao focar o campo seria
        devolver ao card a altura que este widget nasceu para tirar dele.
        """
        agulha = achatar(digitado)
        if not agulha:
            return []
        sinonimos = getattr(self, "_sinonimos", {})
        return [
            (ident, rotulo)
            for ident, rotulo in self._items
            if agulha in achatar(rotulo)
            or agulha in achatar(sinonimos.get(ident, ""))
        ][:LINHAS_VISIVEIS]

    def rotulo_de(self, the_id: str | None) -> str:
        """O rótulo de tela do id ativo, ou string vazia."""
        idx = self._index_of(self._items, the_id)
        return "" if idx is None else self._items[idx][1]


try:
    import gi

    gi.require_version("Gtk", "3.0")
    from gi.repository import GObject, Gtk

    _GTK_DISPONIVEL = True
except (ImportError, ValueError):  # pragma: no cover - CI sem PyGObject
    _GTK_DISPONIVEL = False


if _GTK_DISPONIVEL:
    _RUN_FIRST = getattr(getattr(GObject, "SignalFlags", None), "RUN_FIRST", 1)

    class CampoDeBusca(_BuscaLogic, Gtk.Box):  # type: ignore[misc]
        """Campo de texto + lista filtrada DENTRO do widget. Sem popup."""

        __gsignals__: ClassVar[dict[str, tuple[Any, ...]]] = {
            "changed": (_RUN_FIRST, None, ()),
        }

        def __init__(
            self,
            *,
            placeholder: str = "",
            nome_acessivel: str | None = None,
            largura: int = 16,
        ) -> None:
            Gtk.Box.__init__(self, orientation=Gtk.Orientation.VERTICAL, spacing=2)
            self._init_logic(wrap=False)
            self._sinonimos = {}
            #: A lista filtrada que está DESENHADA agora. Ela é a ponte entre a
            #: linha clicada e o id dela — ver `_ao_ativar_linha`.
            self._visiveis: list[tuple[str, str]] = []

            self._entrada = Gtk.Entry()
            self._entrada.set_width_chars(largura)
            if placeholder:
                self._entrada.set_placeholder_text(_(placeholder))
            if nome_acessivel:
                with contextlib.suppress(Exception):
                    self._entrada.get_accessible().set_name(_(nome_acessivel))
            self._entrada.connect("changed", self._ao_digitar)
            # ESC devolve o campo ao que já estava escolhido e fecha a lista. Sem
            # isso, quem abre a busca por engano fica com uma lista aberta
            # empurrando o card e sem gesto para desfazer.
            self._entrada.connect("key-press-event", self._ao_teclar)
            self.pack_start(self._entrada, False, False, 0)

            self._lista = Gtk.ListBox()
            self._lista.set_selection_mode(Gtk.SelectionMode.NONE)
            self._lista.connect("row-activated", self._ao_ativar_linha)
            self._rolador = Gtk.ScrolledWindow()
            self._rolador.set_policy(
                Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC
            )
            self._rolador.set_max_content_height(
                LINHAS_VISIVEIS * _ALTURA_DA_LINHA
            )
            self._rolador.set_propagate_natural_height(True)
            self._rolador.add(self._lista)
            # `no_show_all` para o `show_all()` da aba não revelar a lista de
            # todo card — é a mesma costura do campo livre da cor
            # (`external_card.py:448`), e pela mesma razão: um `show_all` numa
            # aba com quatro cards abriria quatro listas vazias de uma vez.
            self._rolador.set_no_show_all(True)
            self._rolador.set_visible(False)
            self.pack_start(self._rolador, False, False, 0)

        # ---- o que o call site chama, além da API por-ID ----

        def get_entrada(self) -> Any:
            """O ``Gtk.Entry`` de dentro — para foco e para o portão medir."""
            return self._entrada

        def get_lista(self) -> Any:
            """O ``Gtk.ListBox`` de dentro — para o portão contar linhas."""
            return self._lista

        def lista_visivel(self) -> bool:
            return bool(self._rolador.get_visible())

        # ---- hooks de toolkit ----

        def _create_buttons(self, items: list[tuple[str, str]]) -> None:
            """A lista de sugestões é redesenhada a cada tecla, não aqui.

            Trocar os itens só invalida o que está desenhado; quem redesenha é
            o `_redesenhar`, chamado pelo texto digitado. Redesenhar aqui
            mostraria a lista inteira no instante do `set_items`, que é
            populate — e populate não abre lista.
            """
            self._redesenhar()

        def _activate_button(self, idx: int) -> None:
            """Escreve o rótulo do item no campo, sem disparar o filtro."""
            self._escrever(self._items[idx][1])
            self._fechar()

        def _desmarcar_todos(self) -> None:
            self._escrever("")
            self._fechar()

        def _aplicar_dicas(self) -> None:
            self._redesenhar()

        def _emit_changed(self) -> None:
            self.emit("changed")

        # ---- o miolo ----

        def _escrever(self, texto: str) -> None:
            """Põe texto no campo sob guard, para o filtro não reabrir a lista."""
            self._updating = True
            try:
                self._entrada.set_text(texto)
            finally:
                self._updating = False

        def _fechar(self) -> None:
            self._rolador.set_visible(False)

        def _ao_digitar(self, _entrada: Any) -> None:
            if self._updating:
                return
            self._redesenhar()

        def _ao_teclar(self, _entrada: Any, evento: Any) -> bool:
            from gi.repository import Gdk

            if getattr(evento, "keyval", None) != Gdk.KEY_Escape:
                return False
            self._escrever(self.rotulo_de(self._active_id))
            self._fechar()
            return True

        def _redesenhar(self) -> None:
            """Reconstrói as linhas para o que está digitado agora."""
            for linha in list(self._lista.get_children()):
                self._lista.remove(linha)
                linha.destroy()

            digitado = self._entrada.get_text() or ""
            achados = self.filtrados(digitado)
            self._visiveis = achados
            if not achados and achatar(digitado):
                self._lista.add(self._linha_morta())
            for ident, rotulo in achados:
                self._lista.add(self._linha(ident, rotulo))

            visivel = bool(achatar(digitado))
            self._rolador.set_visible(visivel)
            if visivel:
                self._lista.show_all()
                self._rolador.show()

        def _linha(self, ident: str, rotulo: str) -> Any:
            linha = Gtk.ListBoxRow()
            etiqueta = Gtk.Label(label=rotulo)
            etiqueta.set_xalign(0.0)
            dica = self._dicas.get(ident)
            if dica:
                linha.set_tooltip_text(dica)
            linha.add(etiqueta)
            return linha

        def _linha_morta(self) -> Any:
            """A linha de "não achei" — insensível, para não parecer escolha."""
            linha = Gtk.ListBoxRow()
            etiqueta = Gtk.Label(label=_(SEM_RESULTADO))
            etiqueta.set_xalign(0.0)
            with contextlib.suppress(Exception):
                etiqueta.get_style_context().add_class("dim-label")
            linha.add(etiqueta)
            linha.set_activatable(False)
            linha.set_selectable(False)
            return linha

        def _ao_ativar_linha(self, _lista: Any, linha: Any) -> None:
            """Qual item a linha clicada é — pelo ÍNDICE, não por um atributo.

            Pendurar `linha.hefesto_id = ident` num `Gtk.ListBoxRow` funciona no
            PyGObject e o mypy o aceita sem reclamar, mas é um atributo que não
            existe no tipo: no dia em que o `Gtk.ListBoxRow` ganhar um `__slots__`
            ou o stub apertar, ele cai calado. O índice da linha na `Gtk.ListBox`
            É a posição na lista filtrada, porque as duas são redesenhadas juntas
            e na mesma ordem — não há uma segunda fonte para divergir.

            A linha de "não achei" nunca chega aqui: ela nasce
            `set_activatable(False)`, e `row-activated` não dispara para ela.
            """
            indice = linha.get_index()
            if not (0 <= indice < len(self._visiveis)):
                return
            ident = self._visiveis[indice][0]
            # Pela API por-ID: `set_active_id` é quem marca E emite, e só emite
            # quando o id MUDA. Clicar duas vezes na mesma linha não é um
            # segundo gesto.
            anterior = self._active_id
            self.set_active_id(ident)
            if anterior == ident:
                # Mesmo id: `set_active_id` não fez nada, mas a pessoa clicou —
                # o campo tem de voltar a mostrar a escolha e a lista, fechar.
                self._escrever(self.rotulo_de(ident))
                self._fechar()

else:  # pragma: no cover - CI sem PyGObject

    class CampoDeBusca(_BuscaLogic):  # type: ignore[no-redef]
        """Stub puro para ambientes sem GTK3 — a MESMA API por-ID.

        Ele sabe RECUSAR do mesmo jeito que a versão real: `set_active_id` de um
        id que não está na lista não emite nada, e `filtrados` de campo vazio
        devolve vazio. Régua que só sabe passar não é régua.
        """

        def __init__(
            self,
            *,
            placeholder: str = "",
            nome_acessivel: str | None = None,
            largura: int = 16,
        ) -> None:
            self._init_logic(wrap=False)
            self._sinonimos = {}
            self._placeholder = placeholder
            self._nome_acessivel = nome_acessivel
            self._largura = largura
            self._texto = ""
            self._handlers: list[Callable[[Any], None]] = []

        def connect(self, signal: str, callback: Callable[[Any], None]) -> None:
            if signal == "changed":
                self._handlers.append(callback)

        def show_all(self) -> None:
            pass

        def show(self) -> None:
            pass

        def set_tooltip_text(self, _text: str) -> None:
            pass

        def lista_visivel(self) -> bool:
            return bool(achatar(self._texto))

        def _create_buttons(self, items: list[tuple[str, str]]) -> None:
            pass

        def _activate_button(self, idx: int) -> None:
            self._texto = self._items[idx][1]

        def _desmarcar_todos(self) -> None:
            self._texto = ""

        def _emit_changed(self) -> None:
            for cb in list(self._handlers):
                cb(self)


__all__ = ["LINHAS_VISIVEIS", "SEM_RESULTADO", "CampoDeBusca", "achatar"]
