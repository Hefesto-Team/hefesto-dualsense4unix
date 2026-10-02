"""Seção 0 da aba Configurações — o exame da mesa, com resposta em uma linha.

O `scripts/doctor.sh` tem milhares de linhas de diagnóstico e é invisível para
quem não abre terminal, que é a maior parte de quem usa o produto. Esta seção
dá cara de gente ao que já existe: um selo com o veredito, o botão que refaz o
exame, os CARDS do que fazer, e as linhas do que foi conferido.

DUAS ZONAS, E O QUE MANDA VEM EM CIMA (25/08/2026)
----------------------------------------------------

Até esta data a seção publicava cinco palavras e mais nada: a cura de quatro
das cinco conferências existia, e chegava à tela SÓ dentro de um
`set_tooltip_text` (`_dica_do_item`, e não havia um segundo caminho). Quem não
passasse o mouse por cima da palavra certa nunca descobria o que fazer — a
`A-CASA-SABE-E-O-PRODUTO-NAO-FAZ` na forma mais barata de consertar.

Agora há duas zonas: em cima os cards do que fazer, embaixo a tira do que foi
conferido. Um card de ORDEM (`integrations/ordens_da_mesa.Ordem`) traz o
imperativo e as TRÊS linhas de porquê, cada uma com o selo de procedência; um
card de CURA traz o que fazer e o que se mediu, sem selo, porque uma cura de
conferência não tem medição por trás dizendo de onde vem o conselho.

**A terceira linha é sempre visível**, inclusive quando confessa que o ganho não
foi medido. É ela que impede raciocínio de se vestir de medição: uma ordem que
manda mover sem dizer quanto se ganha é honesta; a mesma com o ganho escondido é
palpite com cara de laudo.

Fonte única: a seção NÃO reimplementa checagem nenhuma. Toda medição vem de
`integrations/exame_da_mesa.py`, e o SELO vem de `exame_da_mesa.veredito()` —
nunca de uma conta feita aqui. Isso é regra, não estilo: a casa pagou duas
vezes em agosto (`6c86e295`, `c3d3518f`) por uma tela que mostrava verde em
cima de vermelho, e a cicatriz está escrita em `scripts/doctor.sh:1647-1651`.
Um segundo lugar decidindo a cor do topo é como aquilo volta.

O QUE MORA AQUI E NÃO LÁ: a cor, o glifo, e o texto que a pessoa lê. O módulo
devolve chave, estado e um porquê; a tradução para tela é desta camada, e é
por isso que nenhuma mensagem do doctor chega à tela — as de lá carregam
`sudo` e carregam endereço de rádio, e esta tela é fotografada e versionada
(`interface/olhar.py --todas --publicado --doc`; era
`scripts/gui-captura/retratar_abas.py` até 06/09/2026, apagado com a janela
GTK — `D-0609-GTK-LEVA-INTEIRA`).

QUANDO O EXAME RODA: ao ENTRAR na aba e no botão. Nunca na montagem — era o
caminho por onde o retrato das abas passava, e um exame ali poria leitura viva
de `/sys` e do rádio dentro de um PNG que entra em `docs/usage/assets/` sem
revisão humana. **A regra sobrevive ao retratista que a motivou**: o de hoje
não monta esta seção (fotografa HTML já gravado), mas o produto monta a cada
entrada na aba, e é dele que a leitura viva tem de continuar fora.

O CARD RESPONDE (26/08/2026)
-----------------------------

Até esta data o card de ordem era só leitura: ela lia "mova o aparelho", ia lá,
movia — e não tinha como dizer isso ao produto. A seção tinha UM botão
("Examinar de novo") e o conselho dispensado nunca sumia. A lógica inteira já
estava escrita e medida em `integrations/ordens_da_mesa.py`
(`resposta_ao_ja_movi`, `ordens_novas`, `ordens_caladas`, `cabecalho`,
`identidades`) e não tinha um único chamador: era a
`A-CASA-SABE-E-O-PRODUTO-NAO-FAZ` na forma cara — cinco funções medidas e
nenhuma tela.

Agora cada card de ordem traz `[Já movi — reexaminar]` e `[Ignorar]`:

* **Já movi** refaz o exame e COMPARA o arranjo, respondendo uma das quatro
  frases de `FRASE_DA_RESPOSTA`. A resposta FICA na tela até o próximo exame —
  um card que simplesmente some é indistinguível de um card que nunca foi
  desenhado, e ela apertou um botão e precisa ver o que ele fez;
* **Ignorar** grava a dispensa no rascunho da máquina, chaveada pelo ARRANJO
  (`D-ORDEM-IGNORADA-VOLTA`). Ela mexeu nos cabos e a mesma regra disparou com
  arranjo novo? é fato novo, e a ordem VOLTA.

O TOPO, E QUEM DECIDE A COR (26/08/2026)
------------------------------------------

O selo passa a dizer o texto de `ordens_da_mesa.cabecalho()` — os quatro
cabeçalhos da §8.3 da ORDEM-DE-SERVIÇO-01, que curam a queixa dela de que
*"o 'está tudo certo' não fala nada"*: o estado bom passa a contar QUANTA coisa
foi conferida, e o "não soube" deixa de se disfarçar dele.

**A cor continua sendo de `exame_da_mesa.veredito()`, e por uma razão medida:**
`cabecalho()` não vê `ESTADO_PROBLEMA` — a assinatura dele conhece ordens e duas
contagens, e nada mais. Um selo pintado só por ele mostraria "Nada a mudar" em
VERDE com a linha de pareamentos em VERMELHO logo abaixo, que é a cicatriz de
`6c86e295` voltando pela porta dos fundos. Por isso o topo é o estado MAIS
GRAVE entre os dois, e quem for mais grave também é quem dá a frase. Escalar
nunca inventa um verde; só o apaga.

TERRITÓRIO DE CONFIG-09. Quem trabalha nesta seção escreve AQUI — o título, a
dica e todo widget dela. O montador da aba (`mixin.py`) só cria a moldura e
chama `montar`; ele não sabe o que há dentro, e é assim que cinco seções
crescem sem se pisarem.
"""
from __future__ import annotations

import contextlib
import time
from collections.abc import Mapping, Sequence
from dataclasses import replace
from datetime import date
from typing import Any

from hefesto_dualsense4unix.app.actions.config.moldura import QUANDO_VALE
from hefesto_dualsense4unix.integrations.exame_da_mesa import (
    ESTADO_ATENCAO,
    ESTADO_CERTO,
    ESTADO_NAO_SEI,
    ESTADO_PROBLEMA,
    ROTULOS_DA_ORDEM,
    Item,
    veredito,
)
from hefesto_dualsense4unix.integrations.ordens_da_mesa import (
    CONFIRMEI,
    FRASE_DA_RESPOSTA,
    MOVEU_E_CONTINUA,
    NAO_CONSEGUI_CONFIRMAR,
    SEM_MUDANCA,
    TEXTO_DO_SELO,
    Identidade,
    Ordem,
    cabecalho,
    identidades,
    ordens_caladas,
    ordens_novas,
    resposta_ao_ja_movi,
)
from hefesto_dualsense4unix.utils.i18n import _
from hefesto_dualsense4unix.utils.logging_config import get_logger

logger = get_logger(__name__)

TITULO = "Está tudo certo?"

ESCOPO = (
    "Este exame olha o que está ligado: portas, energia e rádio. O estado do "
    "Hefesto e do som fica na aba Sistema."
)

DICA: str | None = (
    "O mesmo exame que o Hefesto já sabe fazer pelo terminal, agora com "
    f"resposta em uma linha. Só lê — não muda nada na máquina. {ESCOPO}"
)

NOME_DO_REFRESH = "_refresh_saude_da_mesa"

FRASE_DO_SELO = {
    ESTADO_CERTO: "Pronto para jogar",
    ESTADO_ATENCAO: "Dá para jogar, mas vale um ajuste",
    ESTADO_PROBLEMA: "Há algo atrapalhando o jogo",
    ESTADO_NAO_SEI: "Não deu para conferir tudo",
}

FRASE_ANTES_DO_EXAME = "Ainda não examinei"

FRASE_EXAMINANDO = "Examinando…"

GLIFO = {
    ESTADO_CERTO: "●",
    ESTADO_ATENCAO: "▲",
    ESTADO_PROBLEMA: "■",
    ESTADO_NAO_SEI: "○",
}

GLIFO_PENDENTE = "·"

COR = {
    ESTADO_CERTO: "#50fa7b",
    ESTADO_ATENCAO: "#ffb86c",
    ESTADO_PROBLEMA: "#ff5555",
    ESTADO_NAO_SEI: "#8b8fa8",
}

COR_APAGADA = "#8b8fa8"

DICAS_DAS_LINHAS = {
    "energia_do_radio": (
        "O sistema está proibido de desligar os adaptadores para poupar "
        "energia. Se desligar, o controle cai sozinho no meio do jogo."
    ),
    "energia_das_portas": (
        "Nenhuma porta está entregando menos corrente do que o aparelho pede."
    ),
    "pareamentos": (
        "Todos os controles têm pareamento salvo e válido. Pareamento pela "
        "metade faz o controle cair logo depois de conectar."
    ),
    "suporte_ao_controle": "O módulo que fala com o DualSense está carregado.",
    "vizinhanca_das_portas": (
        "Há um Wi-Fi USB 3.0 na porta ao lado de um adaptador Bluetooth. Ele "
        "emite ruído bem em cima da faixa dos controles. Vale mudar de porta."
    ),
}

PREFIXO_DA_CURA = "O que fazer: "

MARGEM_DO_CARD = 8

ROTULO_DO_BOTAO = "Examinar de novo"
DICA_DO_BOTAO = "Refaz o exame agora. Leva alguns segundos e não altera nada."

ROTULO_JA_MOVI = "Já movi — reexaminar"
ROTULO_IGNORAR = "Ignorar"

#: produto não tem o que afirmar. A FRASE vem de `FRASE_DA_RESPOSTA`, no módulo
ESTADO_DA_RESPOSTA = {
    CONFIRMEI: ESTADO_CERTO,
    MOVEU_E_CONTINUA: ESTADO_ATENCAO,
    SEM_MUDANCA: ESTADO_NAO_SEI,
    NAO_CONSEGUI_CONFIRMAR: ESTADO_NAO_SEI,
}

ESCADA_DE_GRAVIDADE = (
    ESTADO_PROBLEMA,
    ESTADO_ATENCAO,
    ESTADO_NAO_SEI,
    ESTADO_CERTO,
)

COLUNAS = 2


def _escapar(texto: str) -> str:
    """Escapa o que o Pango leria como marcação."""
    return texto.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def frase_de_quando(idade_s: float) -> str:
    """O carimbo "Há N minutos", a partir da idade do exame em segundos."""
    if idade_s < 45:
        return "Agora mesmo"
    if idade_s < 120:
        return "Há 1 minuto"
    if idade_s < 3600:
        return f"Há {int(idade_s // 60)} minutos"
    return "Há mais de uma hora"


def _dica_do_item(item: Item) -> str:
    """A dica aprovada, mais a medição desta rodada embaixo.

    As duas metades têm papéis distintos e nenhuma substitui a outra: a de cima
    diz o que a linha significa, a de baixo diz o que o exame achou agora. Sem
    a de baixo, a dica de "Pareamentos salvos" continuaria afirmando que está
    tudo salvo com a linha pintada de vermelho ao lado — é a
    LED-QUE-NÃO-AFIRMA-01 aplicada a uma dica.

    A CURA CONTINUA AQUI, E DEIXOU DE SER SÓ AQUI. Até 25/08/2026 este era o
    ÚNICO caminho de `Item.cura` até a tela, e quem não passasse o mouse por
    cima da palavra certa nunca descobria o que fazer. Agora ela também sai em
    card (:meth:`PainelDoExame._desenhar_o_que_fazer`); a dica a mantém porque
    quem já está com o ponteiro na linha não deve ter de procurar embaixo.
    """
    partes = [_(DICAS_DAS_LINHAS.get(item.chave, ""))]
    if item.porque:
        partes.append(_(item.porque))
    if item.cura:
        partes.append(_(PREFIXO_DA_CURA) + _(item.cura))
    return "\n\n".join(p for p in partes if p)


def _linha_da_ordem(rotulo: str, texto: str, selo: str) -> str:
    """Uma das três frases de uma ordem, com o selo de procedência à direita."""
    return (
        f"<b>{_escapar(_(rotulo))}:</b> {_escapar(_(texto))} "
        f'<span foreground="{COR_APAGADA}" size="small">'
        f"[{_escapar(_(TEXTO_DO_SELO.get(selo, selo)))}]</span>"
    )


def _markup_da_resposta(resposta: str) -> str:
    """A frase do "Já movi", com o glifo e a cor do estado dela.

    A FRASE não é escrita aqui: ela vem de `ordens_da_mesa.FRASE_DA_RESPOSTA`,
    que é o dono único das quatro. O que esta camada decide é a cor — e ela é a
    mesma escada de sempre, para que "Confirmei" leia verde e os dois casos em
    que o produto não sabe leiam cinza, nunca verde.
    """
    estado = ESTADO_DA_RESPOSTA.get(resposta, ESTADO_NAO_SEI)
    frase = FRASE_DA_RESPOSTA.get(resposta, "")
    return (
        f'<span foreground="{COR[estado]}" weight="bold">'
        f"{_escapar(GLIFO[estado])}</span> {_escapar(_(frase))}"
    )


def o_mais_grave(primeiro: str, segundo: str) -> str:
    """O pior dos dois estados — e, no empate, o segundo."""
    for estado in ESCADA_DE_GRAVIDADE:
        if segundo == estado:
            return segundo
        if primeiro == estado:
            return primeiro
    return segundo


def contagens_do_cabecalho(itens: Sequence[Item]) -> tuple[int, int]:
    """Quantas checagens responderam, e quantas rodaram sem saber."""
    conferencias = [item for item in itens if item.ordem is None]
    sem_resposta = sum(
        1 for item in conferencias if item.estado == ESTADO_NAO_SEI
    )
    return len(conferencias) - sem_resposta, sem_resposta


def leitura_das_ordens(maquina: Any) -> Any:
    """O que o catálogo de ordens lê — o barramento MAIS o desenho dela."""
    from hefesto_dualsense4unix.integrations import (
        censo_do_barramento,
        entrada_a_entrada,
        entradas_do_gabinete,
        mapa_das_portas,
        ordens_da_mesa,
    )
    from hefesto_dualsense4unix.utils.maquina import entradas_do_mapa

    censo = censo_do_barramento.ler_o_barramento()
    mapa = maquina.mapa
    radios = maquina.mesa.radios
    return ordens_da_mesa.Leitura(
        censo=censo,
        entradas=entradas_do_gabinete.listar_entradas(),
        vizinhas=mapa_das_portas.vizinhas_de_verdade(mapa, censo),
        ocupante_da_entrada={
            numero: mapa_das_portas.ocupante_de(mapa, numero, censo)
            for numero in mapa.portas
        },
        entradas_livres_declaradas=mapa_das_portas.portas_livres(mapa, censo),
        nomes_declarados={
            chave: radio.apelido
            for chave, radio in radios.items()
            if radio.apelido
        },
        tipos_declarados={
            chave: radio.tipo for chave, radio in radios.items() if radio.tipo
        },
        nomes_das_entradas={
            numero: nome
            for numero in entradas_do_mapa(mapa)
            if (nome := entrada_a_entrada.nome_da_entrada(numero, maquina=maquina))
        },
    )


class PainelDoExame:
    """Os widgets da seção e o ciclo do exame — montar, examinar, aplicar."""

    def __init__(self, host: Any = None) -> None:
        self.host = host
        self.selo: Any = None
        self.quando: Any = None
        self.botao: Any = None
        self.botao_do_cabecalho: Any = None
        self.linhas: dict[str, Any] = {}
        self.cards: Any = None
        self._examinando = False
        self._itens: list[Item] = []
        self._veredito: str = ESTADO_NAO_SEI
        self._dispensadas: dict[str, str] = {}
        self._identidades: dict[str, Identidade] = {}
        self._aguardando: dict[str, Ordem] = {}
        self._respostas: dict[str, tuple[str, Ordem]] = {}
        self._mostrar_caladas = False


    def montar(self, caixa: Any) -> None:
        """Desenha o cabeçalho, o escopo e a grade das linhas. NÃO examina."""
        from gi.repository import Gtk

        fileira = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.selo = Gtk.Label()
        self.selo.set_xalign(0.0)
        self.selo.set_markup(
            self._markup_do_selo(GLIFO_PENDENTE, COR_APAGADA, _(FRASE_ANTES_DO_EXAME))
        )
        fileira.pack_start(self.selo, False, False, 0)

        self.botao_do_cabecalho = Gtk.Button()
        self.botao_do_cabecalho.set_no_show_all(True)
        self.botao_do_cabecalho.connect("clicked", self._ao_ver_as_caladas)
        fileira.pack_start(self.botao_do_cabecalho, False, False, 0)

        self.quando = Gtk.Label()
        self.quando.set_xalign(1.0)
        with contextlib.suppress(Exception):
            self.quando.get_style_context().add_class("dim-label")

        self.botao = Gtk.Button(label=_(ROTULO_DO_BOTAO))
        self.botao.set_tooltip_text(_(DICA_DO_BOTAO))
        self.botao.connect("clicked", self._ao_clicar)
        fileira.pack_end(self.quando, False, False, 0)
        fileira.pack_end(self.botao, False, False, 0)
        caixa.pack_start(fileira, False, False, 0)

        with contextlib.suppress(Exception):
            self.selo.set_tooltip_text(_(QUANDO_VALE))

        self.cards = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        caixa.pack_start(self.cards, False, False, 0)

        grade = Gtk.Grid()
        grade.set_column_spacing(24)
        grade.set_row_spacing(4)
        for indice, (chave, rotulo) in enumerate(self._linhas_do_desenho()):
            etiqueta = Gtk.Label()
            etiqueta.set_xalign(0.0)
            etiqueta.set_line_wrap(True)
            etiqueta.set_max_width_chars(46)
            etiqueta.set_markup(
                f'<span foreground="{COR_APAGADA}">{GLIFO_PENDENTE}</span> '
                f"{_escapar(_(rotulo))}"
            )
            etiqueta.set_tooltip_text(_(DICAS_DAS_LINHAS.get(chave, "")))
            grade.attach(etiqueta, indice % COLUNAS, indice // COLUNAS, 1, 1)
            self.linhas[chave] = etiqueta
        caixa.pack_start(grade, False, False, 0)

    @staticmethod
    def _linhas_do_desenho() -> list[tuple[str, str]]:
        """As cinco linhas na ordem da tela, com os rótulos do módulo."""
        from hefesto_dualsense4unix.integrations import exame_da_mesa

        return [
            ("energia_do_radio", exame_da_mesa.ROTULO_ENERGIA_DO_RADIO),
            ("energia_das_portas", exame_da_mesa.ROTULO_ENERGIA_DAS_PORTAS),
            ("pareamentos", exame_da_mesa.ROTULO_PAREAMENTOS),
            ("suporte_ao_controle", exame_da_mesa.ROTULO_SUPORTE_AO_CONTROLE),
            ("vizinhanca_das_portas", exame_da_mesa.ROTULO_VIZINHANCA),
        ]

    @staticmethod
    def _markup_do_selo(glifo: str, cor: str, frase: str) -> str:
        return (
            f'<span foreground="{cor}" weight="bold">{_escapar(glifo)}</span> '
            f"<b>{_escapar(frase)}</b>"
        )


    @staticmethod
    def _etiqueta(markup: str, *, margem: int = 0) -> Any:
        """Um rótulo de card: quebra linha, alinhado à esquerda, com markup."""
        from gi.repository import Gtk

        etiqueta = Gtk.Label()
        etiqueta.set_xalign(0.0)
        etiqueta.set_line_wrap(True)
        etiqueta.set_max_width_chars(70)
        etiqueta.set_margin_start(margem)
        etiqueta.set_markup(markup)
        return etiqueta

    def _card(self, filhos: list[Any]) -> Any:
        """A moldura de um card, com os rótulos já prontos dentro."""
        from gi.repository import Gtk

        corpo = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        for filho in filhos:
            corpo.pack_start(filho, False, False, 0)
        for lado in ("start", "end", "top", "bottom"):
            with contextlib.suppress(Exception):
                getattr(corpo, f"set_margin_{lado}")(MARGEM_DO_CARD)
        moldura = Gtk.Frame()
        moldura.add(corpo)
        return moldura

    def _card_da_ordem(
        self, ordem: Ordem, *, resposta: str = "", calada: bool = False
    ) -> Any:
        """O card de uma ordem de serviço: o imperativo e as TRÊS linhas."""
        glifo = (
            f'<span foreground="{COR[ESTADO_ATENCAO]}" weight="bold">'
            f"{_escapar(GLIFO[ESTADO_ATENCAO])}</span> "
        )
        filhos: list[Any] = []
        recuo = 0
        if ordem.tem_acao:
            filhos.append(
                self._etiqueta(f"{glifo}<b>{_escapar(_(ordem.acao))}</b>")
            )
            glifo = ""
            recuo = 12
        for rotulo, linha in zip(ROTULOS_DA_ORDEM, ordem.linhas, strict=True):
            filhos.append(
                self._etiqueta(
                    glifo + _linha_da_ordem(rotulo, linha.texto, linha.selo),
                    margem=recuo,
                )
            )
            glifo = ""
            recuo = 12
        if resposta:
            filhos.append(self._etiqueta(_markup_da_resposta(resposta), margem=12))
        if not calada:
            filhos.append(self._botoes_da_ordem(ordem))
        return self._card(filhos)

    def _botoes_da_ordem(self, ordem: Ordem) -> Any:
        """A fileira `[Já movi — reexaminar] [Ignorar]` de um card."""
        from gi.repository import Gtk

        fileira = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        fileira.set_margin_top(6)
        ja_movi = Gtk.Button(label=_(ROTULO_JA_MOVI))
        ja_movi.connect("clicked", self._ao_ja_movi, ordem)
        fileira.pack_start(ja_movi, False, False, 0)
        ignorar = Gtk.Button(label=_(ROTULO_IGNORAR))
        ignorar.set_tooltip_text(_(QUANDO_VALE))
        ignorar.connect("clicked", self._ao_ignorar, ordem)
        fileira.pack_start(ignorar, False, False, 0)
        return fileira

    def _card_da_resposta(self, resposta: str) -> Any:
        """O card que sobra quando a regra PAROU de disparar."""
        return self._card([self._etiqueta(_markup_da_resposta(resposta))])

    def _card_da_cura(self, item: Item) -> Any:
        """O card de uma conferência que tem cura e não tem ordem.

        Quatro das cinco conferências escrevem uma cura, e até 25/08/2026 as
        quatro morriam dentro de um `set_tooltip_text`. Este card é o caminho
        que faltava — e ele é MENOR que o da ordem de propósito: uma cura de
        conferência não traz selo de procedência, porque não há medição por trás
        dela dizendo de onde vem o conselho. Pôr um selo aqui seria dar ao
        raciocínio a roupa da medição, que é o que o selo existe para impedir.
        """
        cor = COR.get(item.estado, COR_APAGADA)
        return self._card(
            [
                self._etiqueta(
                    f'<span foreground="{cor}" weight="bold">'
                    f"{_escapar(GLIFO.get(item.estado, '?'))}</span> "
                    f"<b>{_escapar(_(PREFIXO_DA_CURA) + _(item.cura or ''))}</b>"
                ),
                self._etiqueta(_escapar(_(item.porque)), margem=12),
            ]
        )

    def _desenhar_o_que_fazer(self, itens: list[Item]) -> None:
        """Refaz a zona de cards a partir dos itens desta rodada."""
        if self.cards is None:
            return
        with contextlib.suppress(Exception):
            for filho in self.cards.get_children():
                self.cards.remove(filho)
                filho.destroy()
        todas = [item.ordem for item in itens if item.ordem is not None]
        novas = ordens_novas(todas, self._dispensadas)
        chaves_novas = {ordem.chave for ordem in novas}
        desenhados: list[Any] = []
        for ordem in novas:
            respondida = self._respostas.get(ordem.chave)
            desenhados.append(
                self._card_da_ordem(
                    ordem, resposta="" if respondida is None else respondida[0]
                )
            )
        for chave, (resposta, _antes) in self._respostas.items():
            if chave not in chaves_novas:
                desenhados.append(self._card_da_resposta(resposta))
        for item in itens:
            if item.ordem is None and item.cura and item.estado != ESTADO_CERTO:
                desenhados.append(self._card_da_cura(item))
        if self._mostrar_caladas:
            for ordem in ordens_caladas(todas, self._dispensadas):
                desenhados.append(self._card_da_ordem(ordem, calada=True))
        with contextlib.suppress(Exception):
            for card in desenhados:
                self.cards.pack_start(card, False, False, 0)
            self.cards.show_all()

    def _escrever_o_cabecalho(self, itens: Sequence[Item]) -> None:
        """O selo do topo: a frase de `cabecalho()` e a cor do estado mais grave."""
        if self.selo is None:
            return
        todas = [item.ordem for item in itens if item.ordem is not None]
        novas = ordens_novas(todas, self._dispensadas)
        caladas = ordens_caladas(todas, self._dispensadas)
        conferidas, sem_resposta = contagens_do_cabecalho(itens)
        topo = cabecalho(
            ordens=novas,
            conferidas=conferidas,
            sem_resposta=sem_resposta,
            dispensadas=len(caladas),
        )
        chaves_caladas = {ordem.chave for ordem in caladas}
        vivos = [
            item
            for item in itens
            if item.ordem is None or item.ordem.chave not in chaves_caladas
        ]
        estado = o_mais_grave(
            self._veredito if not caladas else veredito(vivos), topo.estado
        )
        frase = topo.texto if estado == topo.estado else FRASE_DO_SELO[estado]
        with contextlib.suppress(Exception):
            self.selo.set_markup(
                self._markup_do_selo(GLIFO[estado], COR[estado], _(frase))
            )
        self._mostrar_o_botao_do_cabecalho(topo.botao, bool(caladas))

    def _mostrar_o_botao_do_cabecalho(self, rotulo: str, ha_caladas: bool) -> None:
        """O `[Ver]` da §8.2 — e só ele, porque só ele revela algo."""
        if self.botao_do_cabecalho is None:
            return
        with contextlib.suppress(Exception):
            if rotulo and ha_caladas:
                self.botao_do_cabecalho.set_label(_(rotulo))
                self.botao_do_cabecalho.show()
            else:
                self._mostrar_caladas = False
                self.botao_do_cabecalho.hide()

    def _redesenhar(self) -> None:
        """Refaz as duas zonas com os itens que já estão em mãos."""
        self._desenhar_o_que_fazer(list(self._itens))
        self._escrever_o_cabecalho(self._itens)


    def _com_ambiguidade_fina(self, ordem: Ordem) -> Ordem:
        """A ordem com a ambiguidade que só o SERIAL enxerga.

        `ordens_da_mesa._identidade_do_caminho` marca `ambigua` quando há dois
        aparelhos de mesmo `vid:pid` na mesa — e nesta casa os três adaptadores
        Bluetooth são `2357:0604`, então TODA ordem sobre eles nasceria ambígua
        e nenhuma jamais poderia dizer "Confirmei". Quem separa é o serial, e
        quem o lê (e o descarta na mesma função) é `identidades`.

        O serial não chega aqui: o que volta de `identidades` é a `Identidade`,
        que não tem campo para ele. É assim que ele não entra no PNG que o
        retrato das abas versiona.
        """
        fina = self._identidades.get(ordem.alvo.caminho)
        if fina is None:
            return ordem
        return replace(ordem, alvo=replace(ordem.alvo, ambigua=fina.ambigua))

    def _ao_ja_movi(self, _botao: Any, ordem: Ordem) -> None:
        """Guarda a ordem que ela leu e refaz o exame para comparar o arranjo.

        A ordem de ANTES tem de ser guardada antes do exame novo: é ela que
        `resposta_ao_ja_movi` compara com a de agora, e ela deixa de existir no
        instante em que o exame novo chega.
        """
        self._aguardando[ordem.chave] = ordem
        self.reexaminar()

    def _responder_ao_ja_movi(self, itens: Sequence[Item]) -> None:
        """Compara o antes e o depois de cada ordem que ela disse ter movido."""
        if not self._aguardando:
            return
        agora = {
            item.ordem.chave: item.ordem for item in itens if item.ordem is not None
        }
        for chave, antes in self._aguardando.items():
            depois = agora.get(chave)
            self._respostas[chave] = (
                resposta_ao_ja_movi(
                    self._com_ambiguidade_fina(antes),
                    None if depois is None else self._com_ambiguidade_fina(depois),
                ),
                antes,
            )
        self._aguardando = {}

    def _ao_ignorar(self, _botao: Any, ordem: Ordem) -> None:
        """Cala esta ordem NESTE arranjo, e grava a decisão no rascunho.

        A chave do dispensado é o ARRANJO, não a recomendação
        (`D-ORDEM-IGNORADA-VOLTA`): ela mexeu nos cabos, o conselho pode ter
        mudado, e um conselho dispensado sobre um arranjo que não existe mais
        não é o mesmo conselho.

        A tela obedece na hora e o disco espera o "Aplicar" do rodapé — mesmo
        contrato de `secao_mesa._ao_declarar` e de `secao_orcamento`: chamar
        `machine.declare` daqui criaria um segundo dono do gesto de gravar, que
        é a classe de defeito que a `ABAS-01` curou.
        """
        self._dispensadas[ordem.chave] = ordem.arranjo
        self._respostas.pop(ordem.chave, None)
        self._gravar_a_dispensa(ordem)
        self._redesenhar()

    def _gravar_a_dispensa(self, ordem: Ordem) -> None:
        """Acumula a dispensa em `host._maquina_pendente`, sob `mesa`."""
        from hefesto_dualsense4unix.utils.maquina import fundir_declaracao

        with contextlib.suppress(Exception):
            self.host._maquina_pendente = fundir_declaracao(
                getattr(self.host, "_maquina_pendente", None),
                {
                    "mesa": {
                        "ordens_dispensadas": {
                            ordem.chave: {
                                "quando": date.today().isoformat(),
                                "arranjo": ordem.arranjo,
                            }
                        }
                    }
                },
            )
        marcar = getattr(self.host, "_marcar_declaracao_por_aplicar", None)
        if marcar is not None:
            with contextlib.suppress(Exception):
                marcar()

    def _ao_ver_as_caladas(self, _botao: Any) -> None:
        """O `[Ver]`: mostra as ordens que a decisão dela está segurando.

        Dispensa que some sem deixar marca é a mesma classe de defeito do card
        que some: ela deixaria de saber que existe uma decisão dela ali.
        """
        self._mostrar_caladas = not self._mostrar_caladas
        self._redesenhar()


    def _ao_clicar(self, _botao: Any) -> None:
        self.reexaminar()

    def reexaminar(self) -> None:
        """Roda o exame num worker e devolve o resultado pela thread do GTK."""
        if self._examinando:
            return
        self._examinando = True
        self._respostas = {}
        self._marcar_examinando()

        def _trabalho() -> None:
            try:
                from gi.repository import GLib

                from hefesto_dualsense4unix.integrations import exame_da_mesa
                from hefesto_dualsense4unix.utils.maquina import carregar_maquina

                maquina = carregar_maquina()
                mesa = maquina.mesa
                guardado: dict[str, Any] = {}

                def _ler_as_ordens() -> Any:
                    guardado["leitura"] = leitura_das_ordens(maquina)
                    return guardado["leitura"]

                itens = exame_da_mesa.exame(
                    altura_da_antena=mesa.altura_da_antena,
                    linha_de_visada=mesa.linha_de_visada,
                    leitura_das_ordens=_ler_as_ordens,
                )
                selo = exame_da_mesa.veredito(itens)
                quem: dict[str, Identidade] = {}
                leitura = guardado.get("leitura")
                if leitura is not None:
                    with contextlib.suppress(Exception):
                        quem = identidades(leitura.censo)
                dispensadas = {
                    chave: dispensa.arranjo
                    for chave, dispensa in mesa.ordens_dispensadas.items()
                }
                dispensadas.update(self._dispensas_do_rascunho())
            except Exception as exc:
                logger.warning("exame_da_mesa_falhou", erro=str(exc))
                self._examinando = False
                return
            GLib.idle_add(
                self.aplicar, itens, selo, time.time(), quem, dispensadas
            )

        try:
            from hefesto_dualsense4unix.app.ipc_bridge import _get_executor

            _get_executor().submit(_trabalho)
        except Exception as exc:  # pragma: no cover - sem executor não há janela
            logger.warning("exame_da_mesa_sem_worker", erro=str(exc))
            self._examinando = False

    def _dispensas_do_rascunho(self) -> dict[str, str]:
        """O que ela dispensou e ainda não aplicou — `{chave: arranjo}`."""
        pendente = getattr(self.host, "_maquina_pendente", None)
        if not isinstance(pendente, Mapping):
            return {}
        mesa = pendente.get("mesa")
        if not isinstance(mesa, Mapping):
            return {}
        dispensadas = mesa.get("ordens_dispensadas")
        if not isinstance(dispensadas, Mapping):
            return {}
        return {
            str(chave): str(valor.get("arranjo", ""))
            for chave, valor in dispensadas.items()
            if isinstance(valor, Mapping)
        }

    def _marcar_examinando(self) -> None:
        if self.selo is not None:
            with contextlib.suppress(Exception):
                self.selo.set_markup(
                    self._markup_do_selo(
                        GLIFO_PENDENTE, COR_APAGADA, _(FRASE_EXAMINANDO)
                    )
                )
        if self.botao is not None:
            with contextlib.suppress(Exception):
                self.botao.set_sensitive(False)

    def aplicar(
        self,
        itens: list[Item],
        selo: str,
        quando: float,
        quem: Mapping[str, Identidade] | None = None,
        dispensadas: Mapping[str, str] | None = None,
    ) -> bool:
        """Escreve o resultado nos widgets. Roda na thread do GTK."""
        self._examinando = False
        if quem is not None:
            self._identidades = dict(quem)
        if dispensadas is not None:
            self._dispensadas = dict(dispensadas)
        self._itens = list(itens)
        self._veredito = selo
        self._responder_ao_ja_movi(itens)
        for item in itens:
            etiqueta = self.linhas.get(item.chave)
            if etiqueta is None:
                continue
            with contextlib.suppress(Exception):
                etiqueta.set_markup(
                    f'<span foreground="{COR.get(item.estado, COR_APAGADA)}">'
                    f"{_escapar(GLIFO.get(item.estado, '?'))}</span> "
                    f"{_escapar(_(item.rotulo))}"
                )
                etiqueta.set_tooltip_text(_dica_do_item(item))
        self._desenhar_o_que_fazer(list(itens))
        self._escrever_o_cabecalho(itens)
        if self.quando is not None:
            with contextlib.suppress(Exception):
                self.quando.set_markup(
                    f'<span foreground="{COR_APAGADA}">'
                    f"{_escapar(_(frase_de_quando(time.time() - quando)))}</span>"
                )
        if self.botao is not None:
            with contextlib.suppress(Exception):
                self.botao.set_sensitive(True)
        return False


def montar(host: Any, caixa: Any) -> None:
    """Monta a seção dentro de `caixa` — a caixa interna da moldura."""
    painel = PainelDoExame(host)
    painel.montar(caixa)
    host._painel_do_exame = painel
    setattr(host, NOME_DO_REFRESH, painel.reexaminar)
