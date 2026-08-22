"""Seção 0 da aba Configurações — o exame da mesa, com resposta em uma linha.

O `scripts/doctor.sh` tem milhares de linhas de diagnóstico e é invisível para
quem não abre terminal, que é a maior parte de quem usa o produto. Esta seção
dá cara de gente ao que já existe: um selo com o veredito, o botão que refaz o
exame, e as linhas do que foi conferido.

Fonte única: a seção NÃO reimplementa checagem nenhuma. Toda medição vem de
`integrations/exame_da_mesa.py`, e o SELO vem de `exame_da_mesa.veredito()` —
nunca de uma conta feita aqui. Isso é regra, não estilo: a casa pagou duas
vezes em agosto (`6c86e295`, `c3d3518f`) por uma tela que mostrava verde em
cima de vermelho, e a cicatriz está escrita em `scripts/doctor.sh:1586-1590`.
Um segundo lugar decidindo a cor do topo é como aquilo volta.

O QUE MORA AQUI E NÃO LÁ: a cor, o glifo, e o texto que a pessoa lê. O módulo
devolve chave, estado e um porquê; a tradução para tela é desta camada, e é
por isso que nenhuma mensagem do doctor chega à janela — as de lá carregam
`sudo` e carregam endereço de rádio, e esta tela é fotografada e versionada
pelo `scripts/gui-captura/retratar_abas.py`.

QUANDO O EXAME RODA: ao ENTRAR na aba e no botão. Nunca na montagem, que
acontece no arranque da janela — é o caminho por onde o retrato das abas passa,
e um exame ali poria leitura viva de `/sys` e do rádio dentro de um PNG que
entra em `docs/usage/assets/` sem revisão humana.

TERRITÓRIO DE CONFIG-09. Quem trabalha nesta seção escreve AQUI — o título, a
dica e todo widget dela. O montador da aba (`mixin.py`) só cria a moldura e
chama `montar`; ele não sabe o que há dentro, e é assim que cinco seções
crescem sem se pisarem.
"""
from __future__ import annotations

import contextlib
import time
from typing import Any

from hefesto_dualsense4unix.app.actions.config.moldura import rotulo_de_apoio
from hefesto_dualsense4unix.integrations.exame_da_mesa import (
    ESTADO_ATENCAO,
    ESTADO_CERTO,
    ESTADO_NAO_SEI,
    ESTADO_PROBLEMA,
    Item,
)
from hefesto_dualsense4unix.utils.i18n import _
from hefesto_dualsense4unix.utils.logging_config import get_logger

logger = get_logger(__name__)

#: O título como ela o lê na tela.
TITULO = "Está tudo certo?"

#: A dica do título, palavra por palavra como saiu do desenho aprovado
#: (`TOOLTIPS.md`). Ela não se reescreve na hora.
DICA: str | None = (
    "O mesmo exame que o Hefesto já sabe fazer pelo terminal, agora com "
    "resposta em uma linha. Só lê — não muda nada na máquina."
)

#: O nome do método que a seção pendura no hospedeiro, e que a costura da aba
#: liga em `_REFRESH_POR_ABA` (`app/app.py:925`) para o exame rodar ao ENTRAR na
#: aba. Constante, e não literal solto nos dois lados: uma string repetida em
#: dois arquivos é a forma clássica de um refresher nascer morto em silêncio
#: (BUG-GUI-EMULATION-HANDLERS-UNWIRED-01).
NOME_DO_REFRESH = "_refresh_saude_da_mesa"

#: E5 da leva: a janela passa a ter DUAS telas de saúde, e cada uma declara o
#: seu escopo. Sem esta linha, a pessoa tem de adivinhar por que há dois
#: diagnósticos e qual deles responde à pergunta dela.
ESCOPO = (
    "Este exame olha a mesa: portas, energia e rádio. O estado do Hefesto e "
    "do som fica na aba Sistema."
)

#: A frase do selo, por estado. Ela responde à pergunta do título, e responde
#: em português de gente — as chaves de estado do módulo são vocabulário de
#: máquina, e nenhuma delas chega à tela.
FRASE_DO_SELO = {
    ESTADO_CERTO: "Pronto para jogar",
    ESTADO_ATENCAO: "Dá para jogar, mas vale um ajuste",
    ESTADO_PROBLEMA: "Há algo atrapalhando o jogo",
    ESTADO_NAO_SEI: "Não deu para conferir tudo",
}

#: O que o selo diz antes do primeiro exame. A montagem NÃO examina (ver o
#: cabeçalho), então este é o estado que o retrato das abas fotografa.
FRASE_ANTES_DO_EXAME = "Ainda não examinei"

#: E o que ele diz enquanto o worker trabalha.
FRASE_EXAMINANDO = "Examinando…"

#: O glifo de cada estado. E2 da leva: o sinal de conferido (U+2713) colorido,
#: FORMAS GEOMÉTRICAS, e não o sinal de conferido, e a razão é dupla.
#:
#: A primeira é de portão: o sanitizador global do ambiente dela recusa o bloco
#: U+2700 inteiro, e o CHECK MARK U+2713 mora lá. O `validar-glifos.py` deste
#: projeto o aceitaria — ele deriva a proibição de `Emoji_Presentation`, e o
#: U+2713 não está nela —, mas os dois portões precisam concordar, e o mais
#: estrito manda. O `docs/adr/011-glyphs-vs-emojis.md` já tinha respondido a
#: pergunta por escrito: Geometric Shapes (U+25A0 a U+25FF) são o vocabulário
#: permitido, e o BLACK CIRCLE é o exemplo canônico que a casa já usa nos
#: cabeçalhos Pango e no medidor de bateria da TUI.
#:
#: A segunda é de leitura: a FORMA muda junto com a cor. Quem não distingue
#: verde de laranja ainda vê círculo, triângulo e quadrado — o triângulo é o
#: sinal de alerta em qualquer lugar do mundo, e o quadrado para o olho. Um
#: check verde e um check laranja seriam o mesmo desenho duas vezes.
#:
#: O pedido dela era "ficando verde com um check". O verde ficou onde importa:
#: no selo do topo, que é o que responde em uma linha.
GLIFO = {
    ESTADO_CERTO: "●",
    ESTADO_ATENCAO: "▲",
    ESTADO_PROBLEMA: "■",
    ESTADO_NAO_SEI: "○",
}

#: O glifo de "ainda não olhei". Distinto do "?" de propósito: "não medi" e
#: "medi e não soube" são estados diferentes, e cinco interrogações na tela de
#: uma aba recém-aberta leriam como cinco falhas.
GLIFO_PENDENTE = "·"

#: A cor de cada estado, nos tokens da casa (`gui/theme.css:21-54`). LARANJA e
#: não amarelo para atenção: o `theme.css:13` fixa "VERDE confirma, LARANJA
#: alerta, VERMELHO destrói, CIANO informa", e o `daemon_actions.py:754` já
#: pinta `[WARN]` de `#ffb86c` NESTA MESMA JANELA. Duas cores para o mesmo
#: estado na mesma janela é dívida de tela.
COR = {
    ESTADO_CERTO: "#50fa7b",
    ESTADO_ATENCAO: "#ffb86c",
    ESTADO_PROBLEMA: "#ff5555",
    ESTADO_NAO_SEI: "#8b8fa8",
}

#: Cor do glifo pendente e do carimbo — o cinza de "item não selecionado".
COR_APAGADA = "#8b8fa8"

#: A dica de cada linha, por chave do exame. Palavra por palavra do desenho
#: aprovado (`TOOLTIPS.md:77-81`); não se reescreve na hora.
#:
#: Elas descrevem o que a linha PROMETE, não o que se mediu agora — e é por
#: isso que `_dica_do_item` cola a medição embaixo. Uma dica que afirma "todos
#: os controles têm pareamento salvo e válido" enquanto o exame achou o
#: contrário é a mesma mentira do selo verde sobre linha vermelha, em letra
#: menor.
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

#: Rótulo e dica do botão (`TOOLTIPS.md:75`).
ROTULO_DO_BOTAO = "Examinar de novo"
DICA_DO_BOTAO = "Refaz o exame agora. Leva alguns segundos e não altera nada."

#: Colunas da grade de linhas. Duas, como no desenho — e sem homogeneidade:
#: coluna homogênea numa fileira de rótulo longo já custou 1004 dos 1066px da
#: largura mínima da janela, que abre com 1180 e não tem rolagem horizontal.
COLUNAS = 2


def _escapar(texto: str) -> str:
    """Escapa o que o Pango leria como marcação."""
    return texto.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def frase_de_quando(idade_s: float) -> str:
    """O carimbo "Há N minutos", a partir da idade do exame em segundos.

    Função pura e separada do widget para poder ser medida sem GTK. O
    arredondamento é grosso de propósito: o valor exato não muda decisão
    nenhuma, e "Há 3 minutos" é mais fácil de ler que "Há 187 segundos".
    """
    if idade_s < 45:
        return "Agora mesmo"
    if idade_s < 90:
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
    """
    partes = [_(DICAS_DAS_LINHAS.get(item.chave, ""))]
    if item.porque:
        partes.append(_(item.porque))
    if item.cura:
        partes.append(_("O que fazer: ") + _(item.cura))
    return "\n\n".join(p for p in partes if p)


class PainelDoExame:
    """Os widgets da seção e o ciclo do exame — montar, examinar, aplicar.

    Uma classe, e não três métodos no mixin, por uma razão de território: cinco
    frentes escrevem esta aba ao mesmo tempo, e cada método a mais no mixin é
    uma colisão a mais. O que o hospedeiro ganha é UM atributo — o refresher,
    pendurado por `montar` — e é o que a costura da aba precisa.
    """

    def __init__(self) -> None:
        self.selo: Any = None
        self.quando: Any = None
        self.botao: Any = None
        self.linhas: dict[str, Any] = {}
        self._examinando = False

    # --- montagem -------------------------------------------------------

    def montar(self, caixa: Any) -> None:
        """Desenha o cabeçalho, o escopo e a grade das linhas. NÃO examina."""
        from gi.repository import Gtk

        cabecalho = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.selo = Gtk.Label()
        self.selo.set_xalign(0.0)
        self.selo.set_markup(
            self._markup_do_selo(GLIFO_PENDENTE, COR_APAGADA, _(FRASE_ANTES_DO_EXAME))
        )
        cabecalho.pack_start(self.selo, False, False, 0)

        self.quando = Gtk.Label()
        self.quando.set_xalign(1.0)
        with contextlib.suppress(Exception):
            self.quando.get_style_context().add_class("dim-label")

        self.botao = Gtk.Button(label=_(ROTULO_DO_BOTAO))
        self.botao.set_tooltip_text(_(DICA_DO_BOTAO))
        # Ligado AQUI, e não no `_signal_handlers()` do `app.py`: o botão nasce
        # nesta função e morre com ela, então dono único é quem o criou. Um
        # handler declarado noutro arquivo para um widget criado aqui é como
        # botão nasce morto em silêncio nesta casa.
        self.botao.connect("clicked", self._ao_clicar)
        # A ordem do `pack_end` é da direita para a esquerda: o carimbo encosta
        # na borda e o botão fica à esquerda dele.
        cabecalho.pack_end(self.quando, False, False, 0)
        cabecalho.pack_end(self.botao, False, False, 0)
        caixa.pack_start(cabecalho, False, False, 0)

        caixa.pack_start(rotulo_de_apoio(ESCOPO), False, False, 0)

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
        """As cinco linhas na ordem da tela, com os rótulos do módulo.

        Chamar `exame()` para descobrir os rótulos leria `/sys` na montagem, que
        é justamente o que a montagem não pode fazer. Os rótulos vêm das
        constantes do módulo, que é o mesmo lugar de onde o exame os tira.
        """
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

    # --- o exame --------------------------------------------------------

    def _ao_clicar(self, _botao: Any) -> None:
        self.reexaminar()

    def reexaminar(self) -> None:
        """Roda o exame num worker e devolve o resultado pela thread do GTK.

        Nunca na thread do GTK: BUG-GUI-SYSTEMCTL-SYNC-NA-THREAD-GTK-01
        (`daemon_actions.py:1817-1827`) — um `subprocess.run` síncrono com teto
        de 10 s congelou a janela inteira, e em D-state nem o kill chegava. O
        exame chama `busctl`, que é subprocesso.

        Reentrância barrada por um sinalizador: entrar na aba e clicar no botão
        no mesmo segundo enfileiraria dois exames no executor de UM worker, e o
        segundo só serviria para o carimbo pular duas vezes.
        """
        if self._examinando:
            return
        self._examinando = True
        self._marcar_examinando()

        def _trabalho() -> None:
            # DIAGNÓSTICO-NAO-DERRUBA-A-ABA-01 (`daemon_actions.py:787`): o que
            # se perde no pior caso é uma frase na tela; o que se protege é a
            # aba inteira, e com ela a janela.
            try:
                from gi.repository import GLib

                from hefesto_dualsense4unix.integrations import exame_da_mesa

                itens = exame_da_mesa.exame()
                selo = exame_da_mesa.veredito(itens)
            except Exception as exc:
                logger.warning("exame_da_mesa_falhou", erro=str(exc))
                self._examinando = False
                return
            GLib.idle_add(self.aplicar, itens, selo, time.time())

        try:
            from hefesto_dualsense4unix.app.ipc_bridge import _get_executor

            _get_executor().submit(_trabalho)
        except Exception as exc:  # pragma: no cover - sem executor não há janela
            logger.warning("exame_da_mesa_sem_worker", erro=str(exc))
            self._examinando = False

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

    def aplicar(self, itens: list[Item], selo: str, quando: float) -> bool:
        """Escreve o resultado nos widgets. Roda na thread do GTK.

        Devolve `False` porque é alvo de `GLib.idle_add`: um `True` faria o
        GTK repetir a chamada para sempre.

        `selo` chega pronto de `exame_da_mesa.veredito()` e NÃO é recalculado
        aqui — ver o cabeçalho deste arquivo.

        `quando` é o instante em que o worker terminou, não o instante em que o
        GTK chegou a atender o `idle_add`. A diferença é o que o carimbo mostra,
        e ela não é sempre zero: numa janela ocupada o `idle_add` espera.
        """
        self._examinando = False
        if self.selo is not None:
            with contextlib.suppress(Exception):
                self.selo.set_markup(
                    self._markup_do_selo(
                        GLIFO.get(selo, "?"),
                        COR.get(selo, COR_APAGADA),
                        _(FRASE_DO_SELO.get(selo, FRASE_DO_SELO[ESTADO_NAO_SEI])),
                    )
                )
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
    """Monta a seção dentro de `caixa` — a caixa interna da moldura.

    `host` é o `HefestoApp`: dele vêm `_get` (widgets do Glade) e o que os
    outros mixins já penduraram. `caixa` é um `Gtk.Box` vertical, com as
    margens da casa já aplicadas.

    Ao fim, pendura em `host` o refresher `_refresh_saude_da_mesa`
    (`NOME_DO_REFRESH`), que é o que a costura da aba liga em
    `_REFRESH_POR_ABA` para o exame rodar ao ENTRAR na aba. Pendurar em vez de
    declarar no mixin é o que mantém esta seção dentro de um arquivo só; e se a
    montagem falhar, o atributo não existe e o `getattr(self, nome, None)` de
    `app/app.py:993` simplesmente não chama nada.

    Contrato, e ele vale para as cinco: **nunca levantar**. Uma seção que
    falha ao montar não pode derrubar a aba, e uma aba que falha não pode
    derrubar a janela. Quem chama já embrulha em `contextlib.suppress`, mas a
    tolerância começa aqui.
    """
    painel = PainelDoExame()
    painel.montar(caixa)
    host._painel_do_exame = painel
    setattr(host, NOME_DO_REFRESH, painel.reexaminar)
