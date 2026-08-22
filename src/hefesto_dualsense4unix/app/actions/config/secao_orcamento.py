"""Seção 3 da aba Configurações — o teto de recursos da mesa inteira.

Economia, Balanceado, Máximo e Auto: o mesmo vocabulário que a aba Rumble já
mostra, porque `RumbleConfig.policy` já grava esses valores e renomear
quebraria os perfis gravados no disco.

Teto, não troca: escolher Economia não desliga nada e não apaga ajuste nenhum.

TERRITÓRIO DE CONFIG-05. Quem trabalha nesta seção escreve AQUI — o título, a
dica e todo widget dela. O montador da aba (`mixin.py`) só cria a moldura e
chama `montar`; ele não sabe o que há dentro, e é assim que cinco seções
crescem sem se pisarem.

AS TRÊS DECISÕES QUE ESTE ARQUIVO CARREGA
-----------------------------------------

**1. A tabela tem UMA linha, e não as cinco do desenho.** O desenho promete
teto para vibração, gatilhos, barra de luz, microfone por rádio e giroscópio.
Só a vibração tem ponto de aplicação de verdade — o funil único
`core.rumble._effective_mult`, por onde passam os três caminhos de vibração do
produto. Uma linha dizendo "limitado a 25% pelo orçamento" sem ninguém limitar
nada é a tela mentindo, e é o defeito que esta leva inteira existe para não
cometer. Cada linha nova entra na leva que lhe der ponto de aplicação, e a
linha de apoio abaixo da tabela diz isso em voz alta em vez de deixar a
ausência falar.

**2. Esta seção NÃO tem método IPC próprio.** O dono da escolha é o
`machine.declare`, e o gesto de gravar é o "Aplicar" do rodapé
(`footer_actions._gravar_declaracao_de_maquina`). O clique aqui só acumula em
`host._maquina_pendente`. Dois donos do mesmo valor é a classe de defeito que a
`ABAS-01` curou; e a aba é DIFERIDA por decisão de produto (D-A4), então um
método que agisse no clique contrariaria as duas coisas de uma vez.

**3. O número de percentual não é escrito aqui.** Ele vem de
`core.rumble.teto_do_orcamento`, que por sua vez o deriva de
`RUMBLE_POLICY_MULT` — o dono único do degrau. Escrever "30%" à mão nesta tela
é o HARM-19 de novo: a faixa valeu 2.0 no schema, 1.0 no handler e 200% no
deslizador ao mesmo tempo, e quem pagou foi ela.
"""
from __future__ import annotations

import contextlib
from typing import Any

from hefesto_dualsense4unix.app.actions.config.moldura import rotulo_de_apoio
from hefesto_dualsense4unix.app.actions.rumble_actions import ROTULOS_DO_ORCAMENTO
from hefesto_dualsense4unix.app.widgets.segmented_selector import SegmentedSelector
from hefesto_dualsense4unix.core.rumble import teto_do_orcamento
from hefesto_dualsense4unix.utils.i18n import _
from hefesto_dualsense4unix.utils.logging_config import get_logger

logger = get_logger(__name__)

#: O título como ela o lê na tela.
TITULO = "Orçamento"

#: A dica do título, palavra por palavra como saiu do desenho aprovado
#: (`TOOLTIPS.md`). Ela não se reescreve na hora.
DICA: str | None = (
    "Um teto para a mesa inteira. As abas continuam mandando no que fazem — "
    "só não passam daqui. Nenhum ajuste seu é apagado."
)

#: As quatro chaves do orçamento, na ordem do desenho. São as MESMAS de
#: `OrcamentoDeclarado.teto` (`utils/maquina.py`) e as mesmas que
#: `RumbleConfig.policy` grava — menos `custom`, que é o deslizador livre da aba
#: Rumble e não é escolha de mesa.
#:
#: Gravar o RÓTULO no lugar da chave falha na próxima carga, e falha feio: o
#: `extra="forbid"` do pydantic recusa o DOCUMENTO INTEIRO, então o sintoma
#: seria "não consegui gravar" e não "valor inválido". O teste
#: `test_orcamento_dono_unico_do_valor_efetivo` prende esta tupla ao Literal do
#: schema justamente para que as duas listas não possam divergir.
CHAVES: tuple[str, ...] = ("economia", "balanceado", "max", "auto")

#: Dica por botão — o texto EXATO do desenho aprovado (`TOOLTIPS.md`), com as
#: duas correções datadas de 22/08/2026 já dentro:
#:
#: * o Economia dizia 40% e a barra de luz dizia 25%. O produto entrega 30%
#:   (`RUMBLE_POLICY_MULT["economia"]`) e não existe teto de brilho nenhum
#:   implementado — prometê-lo aqui seria a aba nova aumentando a dívida que
#:   ela existe para não aumentar;
#: * o Auto dizia "controle no cabo joga em Máximo". O Auto **nunca amplifica**
#:   desde 11/08/2026: ele lê bateria e só desce.
#:
#: E uma TERCEIRA, do mesmo dia e pelo MESMO argumento da primeira: o Máximo
#: dizia "e o giroscópio na taxa mais alta". Nada nesta leva mexe na taxa do
#: giroscópio — o teto de emissão é uma constante sem setter ao vivo e com
#: margem zero medida —, então a oração prometia o que o produto não faz, e
#: prometia isso a três centímetros da linha de apoio que diz, na mesma seção,
#: que o giroscópio ainda não tem por onde ser limitado. Duas frases da mesma
#: tela afirmando o contrário uma da outra é pior que divergir de um inventário
#: de texto: o inventário se corrige numa linha, a desconfiança não.
DICAS: dict[str, str] = {
    "economia": "Menos bateria gasta. A vibração chega com 30% da força.",
    "balanceado": "Tudo como o jogo pedir, sem teto.",
    "max": (
        "Tudo como o jogo pedir, sem teto. Hoje faz o mesmo que o Balanceado — "
        "a diferença nasce quando o giroscópio ganhar teto."
    ),
    "auto": (
        "A vibração acompanha a bateria: cheia joga inteira, pela metade cai "
        "para 70%, abaixo de 20% cai para 30%. Nunca aumenta."
    ),
}

#: Cabeçalho da tabela de consequências, na ordem do desenho.
COLUNAS: tuple[str, ...] = ("O que", "Vem de", "Economia", "Balanceado", "Máximo")

#: O que a tela diz quando o orçamento não impõe teto nenhum. Não é "100%": um
#: percentual afirmaria um limite onde não há, e o "Máximo" da aba Rumble
#: entrega 150% justamente por não ter limite.
SEM_TETO = "Sem teto"

#: A linha de apoio que declara o alcance de hoje. Ela existe porque a ausência
#: das outras quatro linhas não fala — e silêncio, nesta tela, seria lido como
#: "o teto vale para tudo".
ALCANCE_DE_HOJE = (
    "Por enquanto o teto alcança a vibração e nada mais. Gatilhos, barra de "
    "luz, microfone por rádio e giroscópio ainda não têm por onde ser "
    "limitados — cada um entra quando ganhar esse ponto."
)

#: A frase que diz quando a escolha passa a valer. A aba inteira é diferida, e
#: sem esta linha o clique parece não ter feito nada.
QUANDO_VALE = 'A escolha passa a valer quando você clicar em "Aplicar", no rodapé.'


def orcamento_em_vigor(host: Any = None) -> str | None:
    """A chave do orçamento que está GRAVADA — nunca a que espera o "Aplicar".

    É de propósito que ela ignore `host._maquina_pendente`: quem lê esta função
    é a aba de origem (a linha "limitado a 30% pelo orçamento" da aba Rumble), e
    aquela linha descreve o que o Hefesto está aplicando AGORA. Mostrar ali a
    escolha ainda pendente faria a aba Rumble afirmar um limite que o daemon não
    está impondo, que é a mentira oposta e igualmente cara.

    `host._orcamento_lido` é o ponto de injeção, no molde do `_mesa_leitor` da
    seção da mesa: é por ele que o retrato das abas alimenta a tela sem tocar o
    disco dela, e é por ele que o teste roda sem depender do `config_dir()` da
    máquina em que está.

    Devolve `None` quando ninguém declarou nada — e `None` aqui significa "não
    sei", nunca "sem teto".
    """
    leitor = getattr(host, "_orcamento_lido", None) if host is not None else None
    if leitor is not None:
        with contextlib.suppress(Exception):
            valor = leitor()
            return valor if isinstance(valor, str) else None
        return None
    from hefesto_dualsense4unix.utils.maquina import carregar_maquina

    return carregar_maquina().orcamento.teto


def celula_do_teto(orcamento: str) -> str:
    """O que a coluna de um orçamento diz sobre a vibração.

    O número sai de `teto_do_orcamento`, que o deriva de `RUMBLE_POLICY_MULT`.
    Nenhum percentual desta tela é digitado: um número digitado sobrevive à
    mudança do degrau que ele descrevia, e aí a tela passa a prometer o que o
    daemon não faz.
    """
    teto = teto_do_orcamento(orcamento)
    if teto is None:
        return SEM_TETO
    return f"No máximo {round(teto * 100)}% da força"


def montar(host: Any, caixa: Any) -> None:
    """Monta a seção dentro de `caixa` — a caixa interna da moldura.

    `host` é o `HefestoApp`: dele vêm `_get` (widgets do Glade) e o que os
    outros mixins já penduraram. `caixa` é um `Gtk.Box` vertical, com as
    margens da casa já aplicadas.

    Contrato, e ele vale para as cinco: **nunca levantar**. Uma seção que
    falha ao montar não pode derrubar a aba, e uma aba que falha não pode
    derrubar a janela. Quem chama já embrulha em `contextlib.suppress`, mas a
    tolerância começa aqui.
    """
    caixa.pack_start(_fileira_dos_quatro(host), False, False, 0)
    caixa.pack_start(rotulo_de_apoio(QUANDO_VALE), False, False, 0)
    caixa.pack_start(_tabela_das_consequencias(), False, False, 0)
    caixa.pack_start(rotulo_de_apoio(ALCANCE_DE_HOJE), False, False, 0)


def _fileira_dos_quatro(host: Any) -> Any:
    """Os quatro botões do orçamento, deitados, com a escolha gravada marcada.

    **Por que a orientação é trocada à mão.** O `SegmentedSelector` sem `wrap`
    é um `Gtk.Box` VERTICAL (`segmented_selector.py:206`) e empilharia as
    quatro opções uma sobre a outra; com `wrap=True` ele vira grade de TRÊS
    colunas fixas (`_WRAP_COLUNAS`), e quatro opções saem em 3 + 1, com o
    "Auto" sozinho numa segunda linha. Nenhum dos dois é o desenho. Deitar a
    caixa é a terceira via, e é a barata: a classe `linked` que o widget já
    aplica sem `wrap` foi feita para exatamente esta fileira de botões colados,
    e `set_orientation` é API do próprio `Gtk.Box`. Mexe só nesta instância.

    A marcação inicial vem ANTES do `connect`, e a ordem é a cura: o
    `set_active_id` EMITE "changed" (espelha o `GtkComboBox`), e com o handler
    já ligado abrir a janela deixaria uma declaração pendente que ninguém fez —
    e o próximo "Aplicar" a gravaria como escolha dela.
    """
    from gi.repository import Gtk

    seletor = SegmentedSelector()
    with contextlib.suppress(Exception):
        seletor.set_orientation(Gtk.Orientation.HORIZONTAL)
    seletor.set_items([(chave, ROTULOS_DO_ORCAMENTO[chave]) for chave in CHAVES])
    seletor.set_tooltips(dict(DICAS))
    gravado = orcamento_em_vigor(host)
    if gravado in CHAVES:
        with contextlib.suppress(Exception):
            seletor.set_active_id(str(gravado))
    else:
        # Ninguém declarou: nenhum botão afundado. Afundar o "Balanceado" por
        # ser o default do daemon faria a tela afirmar uma escolha que ela não
        # fez — a mesma regra do "não sei" que vale em toda esta aba.
        with contextlib.suppress(Exception):
            seletor.limpar_ativo()
    seletor.set_hexpand(False)
    seletor.connect("changed", lambda sel: _ao_escolher(host, sel))
    host._config_orcamento_seletor = seletor

    linha = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
    linha.pack_start(seletor, False, False, 0)
    return linha


def _ao_escolher(host: Any, seletor: Any) -> None:
    """Acumula a escolha em `_maquina_pendente`. NÃO grava, NÃO manda IPC.

    A declaração é PARCIAL de propósito: `fundir_declaracao` desce nos
    dicionários aninhados, então mandar só `{"orcamento": {"teto": ...}}` não
    apaga o que as outras quatro seções declararam na mesma janela.
    """
    from hefesto_dualsense4unix.utils.maquina import fundir_declaracao

    escolha = seletor.get_active_id()
    if escolha not in CHAVES:
        return
    host._maquina_pendente = fundir_declaracao(
        getattr(host, "_maquina_pendente", None),
        {"orcamento": {"teto": escolha}},
    )
    logger.info("config_orcamento_escolhido", teto=escolha)


def _tabela_das_consequencias() -> Any:
    """A tabela "o que o teto faz com cada coisa" — hoje, uma linha.

    `Gtk.Grid` e não caixas encaixadas porque as colunas têm de alinhar entre
    as linhas, e vão alinhar sozinhas quando a segunda linha chegar.

    Sem `column_homogeneous`: a coluna "O que" tem uma palavra e a de Economia
    tem uma frase, e forçar largura igual daria à palavra o tamanho da frase —
    é a mesma medição que proíbe `set_homogeneous(True)` nas fileiras desta aba
    (`main.glade:1644-1650`: 459px para a palavra "Auto", e a largura mínima da
    janela em 1004px numa janela que abre com 1180 e não rola na horizontal).
    """
    from gi.repository import Gtk

    grade = Gtk.Grid()
    grade.set_row_spacing(4)
    grade.set_column_spacing(16)
    grade.set_margin_top(4)

    for coluna, titulo in enumerate(COLUNAS):
        grade.attach(_celula(titulo, cabecalho=True), coluna, 0, 1, 1)

    linha = (
        "Vibração",
        "Rumble",
        celula_do_teto("economia"),
        celula_do_teto("balanceado"),
        celula_do_teto("max"),
    )
    for coluna, texto in enumerate(linha):
        grade.attach(_celula(texto), coluna, 1, 1, 1)
    return grade


def _celula(texto: str, *, cabecalho: bool = False) -> Any:
    """Uma célula da tabela: alinhada à esquerda, sem quebra.

    O cabeçalho é esmaecido em vez de negrito: negrito numa linha inteira
    compete com o título da seção logo acima, e a coluna já se distingue pela
    posição.
    """
    from gi.repository import Gtk

    rotulo = Gtk.Label(label=_(texto))
    rotulo.set_xalign(0.0)
    if cabecalho:
        with contextlib.suppress(Exception):
            rotulo.get_style_context().add_class("dim-label")
    return rotulo
