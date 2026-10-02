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
  ``status_actions.py``, faz o OPOSTO, com ``Align.START``: lá eles ficam
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

from dataclasses import dataclass

DICA_DO_MODO = (
    "O modo é escolhido na chave física antes de ligar, e o controle não "
    "anuncia qual escolheram."
)

DICA_DOS_BOTOES = "Muda só o desenho que aparece na tela. Nada é remapeado no controle."


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


__all__ = [
    "DadosDoControle",
]
