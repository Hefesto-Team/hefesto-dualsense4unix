"""Seção 2 da aba Configurações — os adaptadores, a vizinhança e o rádio.

O que a máquina responde sozinha (adaptadores, rádios vizinhos, hub, topologia
USB) é LIDO; o que nenhum barramento sabe (altura da antena, linha de visada) é
declarado. A ordem importa: onde a leitura acerta, ela pré-preenche.

TERRITÓRIO DE CONFIG-02, e do medidor de rádio de CONFIG-04. Quem trabalha
nesta seção escreve AQUI — o título, a
dica e todo widget dela. O montador da aba (`mixin.py`) só cria a moldura e
chama `montar`; ele não sabe o que há dentro, e é assim que cinco seções
crescem sem se pisarem.

DE ONDE VEM CADA COISA NA TELA
-------------------------------

A leitura inteira sai de `integrations/mesa_de_radio.ler_a_mesa` — sysfs, sem
root, sem subprocesso, sem IPC. Este módulo não lê arquivo nenhum: ele TRADUZ
o que o kernel respondeu para palavra de gente, e é só aqui que `right` vira
"Direita" e que a ausência de resposta vira "Não sei".

Duas colunas do desenho não estão aqui, e o motivo é o mesmo dos dois lados —
não há fonte (F3 de `DECISOES-DA-EXECUCAO.md`):

* **"Firmware"** — não existe check por adaptador em `scripts/doctor.sh`; a
  leitura viria do registro do kernel, que é escopo de CONFIG-09;
* **"Em uso"** — o que amarra controle a adaptador é o *bond*, em
  `/var/lib/bluetooth` (árvore `700`), e a janela é sudo-zero por doutrina. A
  metade derivável vira o medidor de CONFIG-04, que é onde ela tem procedência.

Coluna que só sabe dizer "Não sei" em toda linha ocupa largura — o recurso
escasso desta janela — e ensina a ignorar a tabela.
"""
from __future__ import annotations

import contextlib
from typing import Any

from hefesto_dualsense4unix.app.actions.config.moldura import rotulo_de_apoio
from hefesto_dualsense4unix.integrations.mesa_de_radio import (
    Adaptador,
    Mesa,
    RadioUsb,
    ler_a_mesa,
)
from hefesto_dualsense4unix.utils.i18n import _
from hefesto_dualsense4unix.utils.logging_config import get_logger

logger = get_logger(__name__)

#: O título como ela o lê na tela.
TITULO = "A mesa"

#: A dica do título, palavra por palavra como saiu do desenho aprovado
#: (`TOOLTIPS.md`). Ela não se reescreve na hora.
DICA: str | None = (
    "O Hefesto enxerga os adaptadores, mas não enxerga onde eles estão. Cabo, "
    "hub e altura mudam o alcance e não aparecem em lugar nenhum do sistema."
)

#: As SETE palavras do painel do gabinete, uma por valor de
#: `physical_location/panel` do kernel. O desenho só previa duas ("Frente" e
#: "Trás") e o kernel entrega sete — esta bancada mede `right`, que sem as
#: outras cinco cairia em "Não sei" justamente no único aparelho da casa que
#: SABE onde está. Decisão M2 de `DECISOES-DA-EXECUCAO.md`.
_PAINEL_EM_PORTUGUES: dict[str, str] = {
    "front": "Frente",
    "back": "Trás",
    "left": "Esquerda",
    "right": "Direita",
    "top": "Cima",
    "bottom": "Baixo",
}

#: A resposta quando o kernel não sabe — e ela é comum: o arquivo
#: `physical_location/panel` não existe em boa parte dos aparelhos, e some
#: sempre atrás de um hub. Chutar "Frente" aqui seria a tela afirmando o que
#: ninguém mediu.
_PAINEL_DESCONHECIDO = "Não sei"

#: A dica do par colado, literal do desenho aprovado (`TOOLTIPS.md`).
_DICA_COLADOS = (
    "Dois rádios encostados um no outro se atrapalham. Vale afastar em portas "
    "diferentes."
)

#: A dica do rádio USB 3.0 ao lado do adaptador, literal do mesmo desenho. Ela
#: afirma "USB 3.0", então só aparece onde `speed >= 5000` foi medido.
_DICA_USB3_AO_LADO = (
    "USB 3.0 emite ruído de banda larga bem em cima dos 2,4 GHz. Ao lado do "
    "adaptador Bluetooth, atrapalha."
)

#: Laranja de ATENÇÃO, `@orange` do `theme.css:27`. É a cor que a casa já usa
#: para `[WARN]` nesta mesma janela (`daemon_actions.py:754`) — o desenho da
#: leva dizia "amarelo", e o tema vence (F2).
_LARANJA = "#ffb86c"

#: Quanto texto cabe numa linha de apoio desta seção antes de quebrar. Menor
#: que o padrão de 92 da moldura porque a seção já gasta largura com duas
#: tabelas, e a rolagem horizontal não existe nesta janela.
_LARGURA_DA_FRASE = 84


def montar(host: Any, caixa: Any) -> None:
    """Monta a seção dentro de `caixa` — a caixa interna da moldura.

    `host` é o `HefestoApp`: dele vêm `_get` (widgets do Glade) e o que os
    outros mixins já penduraram. `caixa` é um `Gtk.Box` vertical, com as
    margens da casa já aplicadas.

    Contrato, e ele vale para as cinco: **nunca levantar**. Uma seção que
    falha ao montar não pode derrubar a aba, e uma aba que falha não pode
    derrubar a janela. Quem chama já embrulha em `contextlib.suppress`, mas a
    tolerância começa aqui.

    Os dois últimos gestos penduram coisas no hospedeiro, e nenhum é acidente:

    * `_reexaminar_a_mesa` é o nome que o `_REFRESH_POR_ABA` (`app/app.py`)
      procura para reler o barramento ao ENTRAR na aba. Ele nasce aqui, e não
      no `mixin.py`, porque o montador da aba não conhece uma linha do que há
      dentro de nenhuma seção — e é isso que deixa oito frentes crescerem no
      mesmo lugar sem se pisarem;
    * `_mesa_declarada` é o dicionário vivo das duas escolhas que barramento
      nenhum responde. Hoje ele só existe em memória; é por ele que CONFIG-03
      leva as duas ao disco, sem precisar alcançar widget nenhum.
    """
    painel = _PainelDaMesa(host)
    painel.montar(caixa)
    host._reexaminar_a_mesa = painel.reexaminar
    host._mesa_declarada = painel.declarado


class _PainelDaMesa:
    """Os widgets da seção e a leitura que os preenche.

    Uma instância por montagem. As duas tabelas moram dentro de caixas que
    ficam: reexaminar esvazia a caixa e a preenche de novo, em vez de mexer na
    página — assim a ordem dos filhos da seção nunca muda, e a tela não pula.
    """

    def __init__(self, host: Any) -> None:
        self._host = host
        self._caixa_adaptadores: Any = None
        self._caixa_radios: Any = None
        #: A declaração dela, enquanto CONFIG-03 não a leva ao disco.
        #: TODO(CONFIG-03): mandar cada mudança para `machine.declare` e ler o
        #: valor gravado ao montar — os dois valores precisam sobreviver a
        #: fechar a janela, e hoje não sobrevivem. O dicionário fica exposto no
        #: hospedeiro como `_mesa_declarada`, que é por onde a costura entra.
        self.declarado: dict[str, str | None] = {
            "altura_da_antena": None,
            "linha_de_visada": None,
        }

    # -- montagem ----------------------------------------------------------

    def montar(self, caixa: Any) -> None:
        """Desenha a seção inteira e faz a primeira leitura."""
        from gi.repository import Gtk

        self._caixa_adaptadores = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        caixa.pack_start(self._caixa_adaptadores, False, False, 0)

        caixa.pack_start(self._declaracoes(), False, False, 0)
        caixa.pack_start(
            self._subcabecalho(
                "Outros rádios que dividem a faixa",
                "Tudo aqui divide a faixa de 2,4 GHz com os controles. O "
                "Hefesto encontra os aparelhos, mas não sabe para que servem.",
            ),
            False,
            False,
            0,
        )

        self._caixa_radios = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        caixa.pack_start(self._caixa_radios, False, False, 0)

        caixa.pack_start(self._botao_de_reexame(), False, False, 0)
        self.reexaminar()

    def _declaracoes(self) -> Any:
        """As duas perguntas que barramento nenhum responde.

        Elas ficam ENTRE as duas tabelas, como no desenho, e é o lugar certo:
        vêm logo depois do que a máquina soube dizer sozinha, e antes do que
        ela sabe menos ainda.
        """
        from gi.repository import Gtk

        caixa = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        caixa.set_margin_top(6)
        caixa.pack_start(
            self._linha_declarada(
                "altura_da_antena",
                "Altura da antena:",
                "Corpo humano absorve 2,4 GHz. Antena acima da linha das "
                "cabeças rende mais que antena perto. Nenhum barramento sabe "
                "disto — só você.",
                [("acima", "Acima"), ("abaixo", "Abaixo"), ("nao_sei", "Não sei")],
            ),
            False,
            False,
            0,
        )
        caixa.pack_start(
            self._linha_declarada(
                "linha_de_visada",
                "Linha de visada:",
                "Sem obstáculo entre a antena e quem joga. Também não há como "
                "medir.",
                [
                    ("livre", "Livre"),
                    ("com_gente", "Com gente"),
                    ("nao_sei", "Não sei"),
                ],
            ),
            False,
            False,
            0,
        )
        return caixa

    def _linha_declarada(
        self, chave: str, rotulo: str, dica: str, itens: list[tuple[str, str]]
    ) -> Any:
        """Rótulo com dica mais botões segmentados, numa fileira.

        `Gtk.ComboBox` está proibido nesta casa: o cosmic-comp rouba o foco no
        clique e FECHA o popup na hora (cosmic-epoch#2497), então a pessoa não
        consegue escolher. O `SegmentedSelector` não tem popup nenhum.

        A fileira NÃO é homogênea, e isso é regra medida: uma fileira homogênea
        com rótulo longo já custou 1004 dos 1066px da largura mínima da janela.
        """
        from gi.repository import Gtk

        from hefesto_dualsense4unix.app.widgets.segmented_selector import (
            SegmentedSelector,
        )

        fileira = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        texto = Gtk.Label(label=_(rotulo))
        texto.set_xalign(0.0)
        texto.set_tooltip_text(_(dica))
        with contextlib.suppress(Exception):
            texto.get_style_context().add_class("hefesto-rotulo")
        fileira.pack_start(texto, False, False, 0)

        seletor = SegmentedSelector()
        # O `SegmentedSelector` nasce VERTICAL (`segmented_selector.py:204`) e o
        # modo sem `wrap` empacota os botões no próprio widget — medido em
        # 22/08/2026 na foto desta seção: "Acima", "Abaixo" e "Não sei" saíram
        # empilhados, três linhas onde o desenho tem uma. A fileira do desenho é
        # horizontal, e o pedido é DESTA tela: mudar o padrão do widget mexeria
        # em cinco outras.
        seletor.set_orientation(Gtk.Orientation.HORIZONTAL)
        seletor.set_items([(ident, _(nome)) for ident, nome in itens])
        seletor.connect("changed", self._ao_declarar, chave)
        fileira.pack_start(seletor, False, False, 0)
        return fileira

    def _subcabecalho(self, texto: str, dica: str) -> Any:
        """O rótulo da sub-seção mais o `?` que carrega a explicação."""
        from gi.repository import Gtk

        fileira = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        fileira.set_margin_top(6)
        rotulo = Gtk.Label(label=_(texto))
        rotulo.set_xalign(0.0)
        rotulo.set_tooltip_text(_(dica))
        with contextlib.suppress(Exception):
            rotulo.get_style_context().add_class("hefesto-rotulo-secao")
        fileira.pack_start(rotulo, False, False, 0)

        ajuda = Gtk.Label(label="?")
        ajuda.set_tooltip_text(_(dica))
        with contextlib.suppress(Exception):
            ajuda.get_style_context().add_class("dim-label")
        fileira.pack_start(ajuda, False, False, 0)
        return fileira

    def _botao_de_reexame(self) -> Any:
        """O botão que relê o barramento.

        Ele mora DENTRO da seção, e não no rodapé da aba como o desenho mostra,
        por dois motivos que apontam para o mesmo lado: o rodapé da janela é do
        "Aplicar" e é território de outra frente, e um botão que só relê a mesa
        se explica melhor colado na mesa que releu.
        """
        from gi.repository import Gtk

        fileira = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        fileira.set_margin_top(6)
        botao = Gtk.Button(label=_("Reexaminar a mesa"))
        botao.set_tooltip_text(_("Relê os adaptadores e os rádios. Não muda nada."))
        botao.connect("clicked", self._ao_clicar_reexaminar)
        fileira.pack_start(botao, False, False, 0)
        return fileira

    # -- leitura -----------------------------------------------------------

    def reexaminar(self) -> None:
        """Relê o barramento e redesenha as duas tabelas.

        É o refresher da aba: `_REFRESH_POR_ABA` o chama ao ENTRAR na
        Configurações, e o botão o chama de novo. Nunca em tique — os tiques da
        casa são de 100 ms, 500 ms e 2 s, e uma varredura de barramento em
        qualquer um deles é gastar CPU relendo o que não muda entre dois
        quadros.

        Engole a própria exceção porque o chamador não a embrulha: `app.py`
        chama o refresher direto, e uma leitura de `/sys` que falhe não pode
        derrubar a troca de aba.
        """
        try:
            mesa = self._ler()
            self._desenhar_adaptadores(mesa)
            self._desenhar_radios(mesa)
        except Exception:
            logger.warning("mesa_reexame_falhou", exc_info=True)

    def _ler(self) -> Mesa:
        """A leitura, ou a bancada de mentira que o retrato injetou.

        `_mesa_leitor` é O ponto de injeção da seção, e ele existe por um
        motivo só: a foto da aba entra em `docs/usage/assets` sem revisão
        humana, e nenhum portão desta casa varre imagem. Uma seção que lesse
        `/sys` de verdade durante a captura publicaria o barramento dela num
        PNG versionado — que é o incidente que a `test_retrato_das_abas_nao_
        vaza_dado_real` existe para não repetir, e que ela não pega.
        """
        leitor = getattr(self._host, "_mesa_leitor", None)
        if leitor is None:
            return ler_a_mesa()
        resultado = leitor()
        return resultado if isinstance(resultado, Mesa) else Mesa()

    # -- desenho das tabelas -----------------------------------------------

    def _desenhar_adaptadores(self, mesa: Mesa) -> None:
        """A tabela de adaptadores — ou a frase de que não há nenhum."""
        if self._caixa_adaptadores is None:
            return
        self._esvaziar(self._caixa_adaptadores)
        if not mesa.adaptadores:
            # Decisão M5: tabela em branco parece defeito. Uma linha de texto
            # diz o mesmo sem culpa e sem jargão — e é o estado REAL desta
            # bancada, onde `/sys/class/bluetooth` está vazio.
            self._caixa_adaptadores.pack_start(
                rotulo_de_apoio(
                    "Nenhum adaptador Bluetooth encontrado. Os controles no "
                    "cabo continuam funcionando.",
                    largura_max=_LARGURA_DA_FRASE,
                ),
                False,
                False,
                0,
            )
            self._caixa_adaptadores.show_all()
            return

        grade = self._grade(["Adaptador", "Onde está"])
        for linha, adaptador in enumerate(mesa.adaptadores, start=1):
            grade.attach(self._celula_mono(_nome_do_adaptador(adaptador)), 0, linha, 1, 1)
            texto, dica = _onde_esta_o_adaptador(adaptador)
            grade.attach(self._celula(texto, dica=dica), 1, linha, 1, 1)
        self._caixa_adaptadores.pack_start(grade, False, False, 0)
        self._caixa_adaptadores.show_all()

    def _desenhar_radios(self, mesa: Mesa) -> None:
        """A tabela dos outros rádios — ou a frase de que não há nenhum."""
        if self._caixa_radios is None:
            return
        self._esvaziar(self._caixa_radios)
        if not mesa.radios:
            self._caixa_radios.pack_start(
                rotulo_de_apoio(
                    "Nenhum outro rádio encontrado no barramento USB.",
                    largura_max=_LARGURA_DA_FRASE,
                ),
                False,
                False,
                0,
            )
            self._caixa_radios.show_all()
            return

        avisos = _avisos_de_vizinhanca(mesa)
        grade = self._grade(["Aparelho", "Onde"])
        for linha, radio in enumerate(mesa.radios, start=1):
            grade.attach(self._celula_mono(f"{radio.vid}:{radio.pid}"), 0, linha, 1, 1)
            aviso = avisos.get(radio.no)
            grade.attach(
                self._celula(
                    _onde_esta_o_radio(radio, aviso),
                    dica=None if aviso is None else aviso[1],
                    alerta=aviso is not None,
                ),
                1,
                linha,
                1,
                1,
            )
        self._caixa_radios.pack_start(grade, False, False, 0)
        self._caixa_radios.show_all()

    def _grade(self, cabecalhos: list[str]) -> Any:
        """Uma grade com a fileira de cabeçalhos já posta.

        Grade de rótulos e não `Gtk.TreeView`, e a razão é de portão: o
        `test_config_a_palavra_de_tela_da_aba_montada` anda a árvore de widgets
        e cobra maiúscula, jargão e acentuação de cada texto que encontra —
        e o cabeçalho de coluna de um `TreeView` não é widget da árvore, então
        nasceria fora do alcance dele. Tabela pequena e em somente leitura não
        precisa de modelo; precisa de estar sob o portão de redação.
        """
        from gi.repository import Gtk

        grade = Gtk.Grid()
        grade.set_column_spacing(18)
        grade.set_row_spacing(4)
        for coluna, texto in enumerate(cabecalhos):
            rotulo = Gtk.Label(label=_(texto))
            rotulo.set_xalign(0.0)
            with contextlib.suppress(Exception):
                rotulo.get_style_context().add_class("hefesto-rotulo-secao")
            grade.attach(rotulo, coluna, 0, 1, 1)
        return grade

    def _celula(self, texto: str, *, dica: str | None = None, alerta: bool = False) -> Any:
        """Uma célula de texto comum; em `@orange` quando é atenção."""
        from gi.repository import Gtk
        from gi.repository.GLib import markup_escape_text

        rotulo = Gtk.Label(label=texto)
        rotulo.set_xalign(0.0)
        with contextlib.suppress(Exception):
            rotulo.get_style_context().add_class("hefesto-rotulo")
        if alerta:
            rotulo.set_markup(
                f'<span foreground="{_LARANJA}">{markup_escape_text(texto)}</span>'
            )
        if dica is not None:
            rotulo.set_tooltip_text(_(dica))
        return rotulo

    def _celula_mono(self, texto: str) -> Any:
        """Uma célula de valor lido do barramento, em fonte monoespaçada."""
        from gi.repository import Gtk

        rotulo = Gtk.Label(label=texto)
        rotulo.set_xalign(0.0)
        with contextlib.suppress(Exception):
            rotulo.get_style_context().add_class("hefesto-valor-mono-peq")
        return rotulo

    @staticmethod
    def _esvaziar(caixa: Any) -> None:
        """Tira e destrói os filhos — reexaminar redesenha do zero."""
        for filho in caixa.get_children():
            caixa.remove(filho)
            filho.destroy()

    # -- gestos ------------------------------------------------------------

    def _ao_declarar(self, seletor: Any, chave: str) -> None:
        """Guarda a escolha dela em memória.

        TODO(CONFIG-03): mandar para `machine.declare`. Enquanto a camada de
        persistência de mesa não existe, o valor morre com a janela — e a tela
        não promete o contrário em lugar nenhum.
        """
        self.declarado[chave] = seletor.get_active_id()

    def _ao_clicar_reexaminar(self, _botao: Any) -> None:
        self.reexaminar()


# -- tradução do que o barramento respondeu ---------------------------------


def _nome_do_adaptador(adaptador: Adaptador) -> str:
    """O nome de tela — identidade física, NUNCA `hciN`.

    `hci0` e `hci1` invertem entre boots, e um nome que troca de dono é pior
    que nenhum: a pessoa mexe na porta errada. O sysfs também não entrega o
    endereço (medido: `/sys/class/bluetooth/hci0/` não tem `address`), então o
    que resta é o que basta — VID:PID mais a porta, na coluna ao lado. É a
    decisão M1.
    """
    if not adaptador.vid or not adaptador.pid:
        return "Adaptador embutido"
    return f"{adaptador.vid}:{adaptador.pid}"


def _onde_esta_o_adaptador(adaptador: Adaptador) -> tuple[str, str | None]:
    """`(texto, dica)` da coluna "Onde está"."""
    if not adaptador.no:
        # Sem nó USB o adaptador não pendura em porta nenhuma: é PCIe, UART ou
        # SDIO, ou seja, faz parte da máquina. Não há porta para trocar.
        return "Dentro da máquina", None
    partes = [
        f"Barramento {adaptador.busnum}, porta {adaptador.devpath}",
        _painel_em_portugues(adaptador.painel),
    ]
    if not adaptador.atras_de_hub:
        return " · ".join(partes), None
    partes.append("Em hub")
    # A dica do desenho dizia "...e se ele tem fonte própria". A segunda metade
    # saiu: `bMaxPower` NÃO distingue hub alimentado — medido, o hub USB 3.1
    # com fonte reporta 0mA e o USB 2.1 sem fonte reporta 100mA, o oposto do
    # palpite. Afirmar "com fonte" seria a tela inventando uma medição.
    return " · ".join(partes), "Lido do barramento USB: o Hefesto reconhece o hub."


def _onde_esta_o_radio(radio: RadioUsb, aviso: tuple[str, str] | None) -> str:
    """O painel do rádio, mais o aviso de vizinhança quando há um."""
    onde = _painel_em_portugues(radio.painel)
    return onde if aviso is None else f"{onde} · {aviso[0]}"


def _painel_em_portugues(painel: str) -> str:
    """A palavra do kernel virando palavra de tela — ausência é "Não sei"."""
    return _PAINEL_EM_PORTUGUES.get(painel, _PAINEL_DESCONHECIDO)


def _avisos_de_vizinhanca(mesa: Mesa) -> dict[str, tuple[str, str]]:
    """`{nó do rádio: (sufixo, dica)}` — no máximo um aviso por rádio.

    Duas leituras diferentes saem do MESMO par de nós colados:

    * rádio colado em rádio — o aviso vai numa das duas linhas, não nas duas:
      são dois aparelhos e UM problema, e marcar os dois leria como dois;
    * rádio colado no adaptador — aqui o aviso vai sempre no RÁDIO, porque é
      ele que tem coluna de aviso e é ele que a pessoa vai mudar de porta.

    A dica do USB 3.0 só aparece quando o rádio É USB 3.0 (`speed >= 5000`).
    A frase do desenho afirma "USB 3.0 emite ruído de banda larga", e mostrá-la
    sobre um receptor USB 2.0 seria explicar o problema errado.
    """
    posicao_do_adaptador = {
        adaptador.no: numero
        for numero, adaptador in enumerate(mesa.adaptadores, start=1)
        if adaptador.no
    }
    radios = {radio.no: radio for radio in mesa.radios}
    avisos: dict[str, tuple[str, str]] = {}
    for primeiro, segundo in mesa.apertadas:
        numero = posicao_do_adaptador.get(primeiro) or posicao_do_adaptador.get(segundo)
        if numero is not None:
            alvo = segundo if primeiro in posicao_do_adaptador else primeiro
            radio = radios.get(alvo)
            if radio is None or alvo in avisos:
                continue
            avisos[alvo] = (
                f"vizinho do adaptador {numero}",
                _DICA_USB3_AO_LADO if radio.usb3 else _DICA_COLADOS,
            )
            continue
        if primeiro in radios and segundo in radios and segundo not in avisos:
            avisos[segundo] = ("colado no vizinho", _DICA_COLADOS)
    return avisos
