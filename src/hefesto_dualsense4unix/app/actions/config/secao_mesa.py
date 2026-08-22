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

Uma coluna do desenho não está aqui, e o motivo é que não há fonte (F3 de
`DECISOES-DA-EXECUCAO.md`): **"Firmware"** — não existe check por adaptador em
`scripts/doctor.sh`; a leitura viria do registro do kernel, que é escopo de
CONFIG-09. Coluna que só sabe dizer "Não sei" em toda linha ocupa largura — o
recurso escasso desta janela — e ensina a ignorar a tabela.

A coluna **"Em uso"** também saiu da tabela, mas por outro motivo: ela virou o
MEDIDOR, mais abaixo nesta mesma seção, que é onde ela tem procedência.

O MEDIDOR DE RÁDIO (CONFIG-04)
-------------------------------

O limite que CONFIG-02 escreveu — *"o que amarra controle a adaptador é o bond,
em `/var/lib/bluetooth`, árvore 700, e a janela é sudo-zero"* — estava FALSO, e
foi derrubado em 22/08/2026: o uevent do nó hidraw publica `HID_PHYS` = MAC do
adaptador para BT real (`broker/hidraw_broker.py:281`), e
`/sys/class/hidraw/*/device/uevent` abre como uid 1000. É por aí que o medidor
sabe qual controle está em qual adaptador, sem tocar em `sudo`.

A conta, a procedência de cada número e a fronteira que a tela NÃO atravessa
(ocupação nunca é culpa) moram no cabeçalho de
`integrations/radio_da_mesa.py`. Aqui em cima ficam só as três coisas que são
de tela: o rótulo, a cor da palavra e o selo de procedência.
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
from hefesto_dualsense4unix.integrations.radio_da_mesa import (
    PALAVRA_FOLGADA,
    SEM_ADAPTADOR,
    Ocupacao,
    ocupacao_por_adaptador,
)
from hefesto_dualsense4unix.utils.i18n import _
from hefesto_dualsense4unix.utils.logging_config import get_logger
from hefesto_dualsense4unix.utils.maquina import carregar_maquina, fundir_declaracao

logger = get_logger(__name__)

#: O título como ela o lê na tela.
TITULO = "A mesa"

#: A dica do título, palavra por palavra como saiu do desenho aprovado
#: (`TOOLTIPS.md`). Ela não se reescreve na hora.
DICA: str | None = (
    "O Hefesto enxerga os adaptadores, mas não enxerga onde eles estão. Cabo, "
    "hub e altura mudam o alcance e não aparecem em lugar nenhum do sistema."
)

#: Os sete botões da coluna "O que é", na ordem do desenho. Os seis primeiros
#: são exatamente os `Literal` de `RadioDeclarado.tipo`; o sétimo é a ausência
#: de opinião, que o esquema representa como `None` e não como palavra.
#:
#: O "Outro" NÃO abre campo de texto aqui, e o desenho abria
#: (`mockup:1148`, "Fone sem fio da TV"). O `apelido` existe no esquema e é
#: entrega de outra leva: um `Gtk.Entry` por linha numa tabela que já tem três
#: colunas custaria a largura que esta janela não tem, e o apelido não muda uma
#: linha do que o exame consegue afirmar — o `tipo` muda.
_TIPOS_DE_RADIO: tuple[tuple[str, str], ...] = (
    ("wifi", "Wi-Fi"),
    ("teclado", "Teclado"),
    ("mouse", "Mouse"),
    ("webcam", "Webcam"),
    ("caixa_de_som", "Caixa de som"),
    ("outro", "Outro"),
    ("nao_sei", "Não sei"),
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

#: Verde de "está folgado", `@green` do `theme.css:26`.
_VERDE = "#50fa7b"

#: A dica do rótulo do medidor, literal do desenho aprovado (`TOOLTIPS.md`).
#: Ela é a ÚNICA coisa na tela que declara de onde vêm as 1.600 fatias — e o
#: número não é medição desta máquina.
_DICA_DO_MEDIDOR = (
    "Aritmética da especificação do Bluetooth, não medição desta máquina: o "
    "rádio tem 1.600 fatias de tempo por segundo e todos os controles do mesmo "
    "adaptador as dividem."
)

#: O selo de procedência, montado em Python porque os dois números são
#: calculados. A frase depois do meio-ponto não muda nunca: é ela que impede a
#: barra de ser lida como medição.
_SELO_DE_PROCEDENCIA = "derivado da especificação"

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
    * `_mesa_declarada` é o espelho de leitura das duas escolhas que barramento
      nenhum responde. Desde 22/08/2026 ele **não é mais o dono**: quem guarda
      é `host._maquina_pendente`, e quem grava é o "Aplicar" do rodapé. O
      dicionário fica porque é por onde um teste ou o retrato olha o estado da
      seção sem alcançar widget nenhum.
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
        self._caixa_medidores: Any = None
        #: A última mesa lida — o medidor precisa dela quando a resposta do
        #: daemon chega DEPOIS da leitura do barramento (é sempre o caso).
        self._mesa = Mesa()
        #: `state["controllers"]` da última resposta, e os `uniq` com ponte de
        #: microfone de pé. Nascem vazios, e barra em zero é o desenho certo
        #: enquanto ninguém respondeu: zero é o que se sabe.
        self._controles: list[dict[str, Any]] = []
        self._com_mic: frozenset[str] = frozenset()
        #: Impede empilhar pedidos ao daemon quando ela troca de aba rápido.
        self._estado_pedido = False
        #: A declaração dela nesta sessão, espelho de leitura do que já foi
        #: acumulado em `host._maquina_pendente`. Exposto no hospedeiro como
        #: `_mesa_declarada`.
        #:
        #: ELE NÃO É MAIS O DONO (22/08/2026). Até esta data o dicionário era o
        #: único lugar onde a escolha existia, e o TODO daqui dizia que o valor
        #: morria com a janela — mas a camada que faltava nasceu no MESMO dia
        #: (CONFIG-03, `utils/maquina.py` mais o `machine.declare` do IPC), e o
        #: TODO sobreviveu a ela. Foi a classe de defeito mais cara desta casa
        #: acontecendo dentro da leva que a documentou: a cura escrita e nunca
        #: ligada. Quem grava agora é o "Aplicar" do rodapé, pela mesma rota das
        #: outras seções — `host._maquina_pendente`.
        self.declarado: dict[str, str | None] = {
            "altura_da_antena": None,
            "linha_de_visada": None,
        }
        #: O tipo declarado de cada rádio vizinho, por `vid:pid`. Mesma rota.
        self.radios_declarados: dict[str, str | None] = {}

    # -- montagem ----------------------------------------------------------

    def montar(self, caixa: Any) -> None:
        """Desenha a seção inteira e faz a primeira leitura."""
        from gi.repository import Gtk

        self._caixa_adaptadores = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        caixa.pack_start(self._caixa_adaptadores, False, False, 0)

        caixa.pack_start(self._declaracoes(), False, False, 0)

        # O medidor fica ENTRE as declarações e os outros rádios, como no
        # desenho (`mockup/aba-configuracoes.html:365-373`), e a ordem faz
        # sentido de cima para baixo: primeiro quais adaptadores existem,
        # depois o que você declarou sobre eles, depois quanto do rádio deles
        # já está comprometido, e só então o que mais divide a faixa.
        self._caixa_medidores = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        caixa.pack_start(self._caixa_medidores, False, False, 0)

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
        # Montar lê o BARRAMENTO e nada mais. O `daemon.state_full` que
        # alimenta o medidor fica de fora daqui de propósito, pelo mesmo motivo
        # da decisão E6 do exame: `install_config_tab` roda no ARRANQUE da
        # janela (`app/app.py:1217` e `:1487`), inclusive por quem sobe
        # minimizado na bandeja, e é por esse caminho que o retrato passa. Uma
        # aba que ninguém abriu não fala com o daemon.
        self._reler_a_mesa()

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
        # A pré-seleção vem ANTES do `connect`, e é a diferença entre mostrar o
        # que ela escolheu e re-escrever no rascunho tudo o que a tela desenhou:
        # `set_active_id` emite `changed`, e com o sinal já ligado o simples ato
        # de abrir a aba marcaria o rascunho como sujo. O rodapé passaria a ter
        # o que "Aplicar" sem ninguém ter clicado em nada.
        gravado = self._mesa_em_vigor().get(chave)
        if gravado is not None:
            self.declarado[chave] = str(gravado)
            with contextlib.suppress(Exception):
                seletor.set_active_id(str(gravado))
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
        """Relê tudo: o barramento agora, e quem está no rádio quando chegar.

        É o refresher da aba: `_REFRESH_POR_ABA` o chama ao ENTRAR na
        Configurações, e o botão o chama de novo. Nunca em tique — os tiques da
        casa são de 100 ms, 500 ms e 2 s, e uma varredura de barramento em
        qualquer um deles é gastar CPU relendo o que não muda entre dois
        quadros.

        As duas leituras são assimétricas de propósito: o barramento responde
        na hora, e o daemon responde por callback. É por isso que o medidor é
        desenhado DUAS vezes — uma com o que já se sabe, outra quando a
        resposta chega. Esperar a segunda para desenhar a primeira deixaria a
        seção em branco no gesto mais comum da aba.
        """
        self._reler_a_mesa()
        self._pedir_o_estado()

    def _reler_a_mesa(self) -> None:
        """A metade síncrona: `/sys` agora, as três caixas redesenhadas.

        Engole a própria exceção porque o chamador não a embrulha: `app.py`
        chama o refresher direto, e uma leitura de `/sys` que falhe não pode
        derrubar a troca de aba.
        """
        try:
            mesa = self._ler()
            self._mesa = mesa
            self._desenhar_adaptadores(mesa)
            self._desenhar_radios(mesa)
            self._desenhar_medidores()
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

    def _pedir_o_estado(self) -> None:
        """Pede ao daemon quem está no rádio — sem bloquear a thread da tela.

        O medidor precisa de UMA coisa que o sysfs desta seção não tem: a lista
        de controles conectados, com transporte e `uniq`. Ela mora no
        `daemon.state_full`, e vem por `call_async` porque o refresher roda na
        thread do GTK ao trocar de aba: um IPC síncrono ali congelaria a janela
        no gesto mais comum da aba.

        **A foto não fala com o daemon, e a guarda é a mesma da mesa.** Quem
        injetou `_mesa_leitor` está capturando `docs/usage/assets/` — e o
        `state_full` desta máquina traz o `uniq` dos controles DELA, que é MAC.
        Nenhum portão de anonimato varre imagem (F5). Com o desvio de pé o
        medidor fica com o que já tem, que é zero, e a foto sai com a barra
        vazia — o resultado honesto de uma bancada sem rádio.
        """
        if getattr(self._host, "_mesa_leitor", None) is not None:
            return
        if self._estado_pedido:
            return

        # O timeout é o MESMO de toda leitura de `daemon.state_full` da casa
        # (`mode_transition.py:43`, HARM-15: 1,0 s, porque sob hotplug o daemon
        # passa dos 0,25 s de padrão do `call_async` e a janela o declarava
        # morto estando vivo). Um número próprio aqui seria um segundo dono da
        # mesma folga.
        from hefesto_dualsense4unix.app.actions.mode_transition import (
            STATE_IPC_TIMEOUT_S,
        )
        from hefesto_dualsense4unix.app.ipc_bridge import call_async

        def _chegou(estado: Any) -> bool:
            self._estado_pedido = False
            self._aplicar_estado(estado if isinstance(estado, dict) else None)
            return False

        def _falhou(_exc: Exception) -> bool:
            self._estado_pedido = False
            # Daemon fora do ar não é "rádio folgado": é "não sei quem está no
            # rádio". Zerar é o que a tela já mostra, e a barra em zero com o
            # daemon parado não afirma nada que a seção não saiba.
            self._aplicar_estado(None)
            return False

        self._estado_pedido = True
        call_async(
            "daemon.state_full", None, _chegou, _falhou, timeout_s=STATE_IPC_TIMEOUT_S
        )

    def _aplicar_estado(self, estado: dict[str, Any] | None) -> None:
        """Guarda os controles e os `uniq` com microfone, e redesenha."""
        controles = (estado or {}).get("controllers")
        if isinstance(controles, list):
            self._controles = [c for c in controles if isinstance(c, dict)]
        else:
            self._controles = []
        # A TERCEIRA chave do bloco `bt_mic` — a lista de `uniq` com ponte de
        # microfone de pé — AINDA NÃO EXISTE no `daemon.state_full`: o bloco de
        # `daemon/ipc_handlers.py:2937-2940` publica só `enabled` e `running`,
        # que são do PROCESSO e não do controle. Está lido daqui de propósito,
        # com ausência virando conjunto vazio, para que ligá-la seja UMA linha
        # no daemon e nenhuma aqui. Enquanto ela não existe, um controle com a
        # ponte de pé é contado como sem microfone: a soma erra por 6% (276,7
        # contra 260,4 fatias) e a fatia ciana não aparece. Está registrado como
        # pendência da sprint CONFIG-04.
        bloco = (estado or {}).get("bt_mic")
        uniqs = bloco.get("uniqs") if isinstance(bloco, dict) else None
        if isinstance(uniqs, list):
            self._com_mic = frozenset(u for u in uniqs if isinstance(u, str))
        else:
            self._com_mic = frozenset()
        self._desenhar_medidores()

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
        em_vigor = self._mesa_em_vigor().get("radios")
        gravados: dict[str, Any] = em_vigor if isinstance(em_vigor, dict) else {}
        grade = self._grade(["Aparelho", "Onde", "O que é"])
        for linha, radio in enumerate(mesa.radios, start=1):
            chave = f"{radio.vid}:{radio.pid}"
            grade.attach(self._celula_mono(chave), 0, linha, 1, 1)
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
            declarado = gravados.get(chave)
            grade.attach(
                self._seletor_do_tipo(
                    chave,
                    declarado.get("tipo") if isinstance(declarado, dict) else None,
                ),
                2,
                linha,
                1,
                1,
            )
        self._caixa_radios.pack_start(grade, False, False, 0)
        self._caixa_radios.show_all()

    def _seletor_do_tipo(self, chave_do_radio: str, gravado: Any) -> Any:
        """Os seis tipos mais "Não sei", em grade de três colunas.

        POR QUE ESTA COLUNA EXISTE. O Hefesto acha o aparelho no barramento e
        não tem como saber para que ele serve — um dongle de teclado e um de
        caixa de som são o mesmo `vid:pid` para o kernel. A resposta é a única
        coisa desta seção que só a pessoa tem, e é ela que deixa o exame dizer
        *"o engasgo pode ser a webcam ao lado do adaptador"* em vez de listar
        um endereço hexa e calar.

        O esquema (`RadioDeclarado.tipo`) existe desde CONFIG-03, no mesmo dia,
        e ficou SEM TELA até aqui — a metade que faltava do mesmo defeito.

        HORIZONTAL, E O NÚMERO É MEDIDO. A primeira versão usava `wrap=True`,
        que é grade de três colunas FIXAS (`segmented_selector.py:32`) — sete
        botões viram TRÊS linhas, e com quatro rádios na mesa a seção cresceu
        384px de uma vez (1921 → 2305, medido na foto de 22/08). Em fileira
        única os sete ocupam ~595px; com "Aparelho" (~90) e "Onde" (~200) a
        tabela fica em ~885px, dentro dos 1066px de largura mínima da janela.
        A largura sobrava e a altura não — esta tabela tem três colunas num
        espaço de 1920px, e é a altura que custa numa aba que já rola.

        `set_hexpand(False)` porque o `SegmentedSelector` propaga a expansão
        horizontal para cima: sem isto a coluna come a largura da tabela
        inteira, que é o defeito que a seção "A janela" pagou em 22/08 (757px
        de vão). Curar dentro do widget quebraria a aba Início, que DEPENDE
        dessa expansão (`home_actions.py:1523`).
        """
        from gi.repository import Gtk

        from hefesto_dualsense4unix.app.widgets.segmented_selector import (
            SegmentedSelector,
        )

        seletor = SegmentedSelector()
        seletor.set_orientation(Gtk.Orientation.HORIZONTAL)
        seletor.set_items([(ident, _(nome)) for ident, nome in _TIPOS_DE_RADIO])
        seletor.set_hexpand(False)
        if gravado is not None:
            self.radios_declarados[chave_do_radio] = str(gravado)
            with contextlib.suppress(Exception):
                seletor.set_active_id(str(gravado))
        seletor.connect("changed", self._ao_declarar_o_radio, chave_do_radio)
        return seletor

    # -- desenho do medidor ------------------------------------------------

    def _desenhar_medidores(self) -> None:
        """Uma barra por adaptador — ou nenhuma, quando não há adaptador."""
        if self._caixa_medidores is None:
            return
        self._esvaziar(self._caixa_medidores)
        for nome, ocupacao in _medidores_da_mesa(self._mesa, self._ocupacoes()):
            self._caixa_medidores.pack_start(
                self._fileira_do_medidor(nome, ocupacao), False, False, 0
            )
        self._caixa_medidores.show_all()

    def _ocupacoes(self) -> dict[str, Ocupacao]:
        """A conta, ou nada quando o sysfs não responde.

        Engole a exceção pelo mesmo motivo do `reexaminar`: uma varredura de
        `/sys` que falhe não pode apagar as duas tabelas que já foram
        desenhadas acima.
        """
        try:
            return ocupacao_por_adaptador(
                self._controles, com_ponte_de_mic=self._com_mic
            )
        except Exception:
            logger.warning("medidor_de_radio_falhou", exc_info=True)
            return {}

    def _fileira_do_medidor(self, nome: str, ocupacao: Ocupacao) -> Any:
        """Rótulo, trilha de duas fatias, a palavra e o selo — nesta ordem.

        A ordem é a do desenho (`mockup/aba-configuracoes.html:365-372`) e ela
        conta uma frase: QUAL rádio, QUANTO dele, em UMA palavra, e DE ONDE
        veio o número. Trocar a ordem quebra a frase.
        """
        from gi.repository import Gtk
        from gi.repository.GLib import markup_escape_text

        from hefesto_dualsense4unix.app.widgets.sensor_widgets import MedidorDeRadio

        fileira = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        fileira.set_margin_top(4)

        rotulo = Gtk.Label(label=_(_rotulo_do_medidor(nome)))
        rotulo.set_xalign(0.0)
        rotulo.set_tooltip_text(_(_DICA_DO_MEDIDOR))
        with contextlib.suppress(Exception):
            rotulo.get_style_context().add_class("hefesto-rotulo")
        fileira.pack_start(rotulo, False, False, 0)

        medidor = MedidorDeRadio()
        medidor.set_ocupacao(ocupacao.fracao_input, ocupacao.fracao_audio)
        medidor.set_hexpand(True)
        medidor.set_valign(Gtk.Align.CENTER)
        # O trilho é a única coisa da fileira que pode crescer, e é ele que
        # come a largura sobrando. Sem o `hexpand` aqui e com um
        # `set_size_request` largo no widget, o mínimo da barra viraria o
        # mínimo da aba inteira — a janela abre com 1180px e não tem rolagem
        # horizontal.
        with contextlib.suppress(Exception):
            medidor.get_accessible().set_name(_texto_acessivel(ocupacao))
        fileira.pack_start(medidor, True, True, 0)

        palavra = Gtk.Label()
        cor = _VERDE if ocupacao.rotulo == PALAVRA_FOLGADA else _LARANJA
        # Duas cores, nunca três, e NUNCA vermelho (R3): rádio cheio se resolve
        # tirando um controle daquele adaptador, e o vermelho desta casa é para
        # o que destrói e não tem volta (`theme.css:13`).
        palavra.set_markup(
            f'<span foreground="{cor}">{markup_escape_text(_(ocupacao.rotulo))}</span>'
        )
        palavra.set_xalign(0.0)
        with contextlib.suppress(Exception):
            palavra.get_style_context().add_class("hefesto-valor-mono-peq")
        fileira.pack_start(palavra, False, False, 0)

        selo = Gtk.Label(label=_selo_da_ocupacao(ocupacao))
        selo.set_xalign(0.0)
        with contextlib.suppress(Exception):
            selo.get_style_context().add_class("hefesto-valor-mono-peq")
            selo.get_style_context().add_class("dim-label")
        fileira.pack_start(selo, False, False, 0)
        return fileira

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
        """Acumula a escolha no rascunho da máquina. NÃO grava, NÃO manda IPC.

        `D-A4`, o mesmo contrato de `secao_controles` e `secao_orcamento`: o
        clique marca o rascunho e o efeito sai no "Aplicar" do rodapé. Chamar
        `machine.declare` daqui criaria um segundo dono do gesto de gravar, que
        é a classe de defeito que a `ABAS-01` curou.

        `"nao_sei"` vira `None` e não a string: o esquema
        (`MesaDeclarada.altura_da_antena`) só aceita os valores reais, e
        `extra="forbid"` mais `Literal` recusariam o DOCUMENTO INTEIRO — o
        sintoma na tela seria "não consegui gravar", não "valor inválido".
        `None` é a resposta que o esquema já tem para "não sei", e ela é
        preservada na fusão como qualquer outra.
        """
        escolha = self._valor_do_seletor(seletor)
        self.declarado[chave] = escolha
        self._acumular({chave: escolha})

    def _ao_declarar_o_radio(self, seletor: Any, chave_do_radio: str) -> None:
        """O mesmo gesto, para o `tipo` de um rádio vizinho.

        A chave é `vid:pid` em hexa minúsculo, e o esquema a valida por regex
        (`MesaDeclarada._chave_de_radio_e_vid_pid`). É de propósito que ela NÃO
        seja o nó do sysfs: o nó muda de nome quando o aparelho troca de porta,
        e a resposta "isto é um teclado" não muda com a porta.
        """
        escolha = self._valor_do_seletor(seletor)
        self.radios_declarados[chave_do_radio] = escolha
        self._acumular({"radios": {chave_do_radio: {"tipo": escolha}}})

    @staticmethod
    def _valor_do_seletor(seletor: Any) -> str | None:
        """O id ativo, com `"nao_sei"` traduzido para a ausência de opinião."""
        ativo = seletor.get_active_id()
        return None if ativo in (None, "nao_sei") else str(ativo)

    def _acumular(self, mesa: dict[str, Any]) -> None:
        """Funde o pedaço em `host._maquina_pendente`, sob a chave `mesa`.

        Fusão e não substituição pelo mesmo motivo de `gravar_maquina`: as cinco
        seções da aba escrevem no MESMO rascunho pelo mesmo gesto, e a última a
        clicar apagaria as outras quatro se cada uma trocasse o documento.
        """
        with contextlib.suppress(Exception):
            self._host._maquina_pendente = fundir_declaracao(
                getattr(self._host, "_maquina_pendente", None),
                {"mesa": mesa},
            )

    def _mesa_em_vigor(self) -> dict[str, Any]:
        """O que está no DISCO, com o que ainda espera o "Aplicar" por cima.

        A ordem importa e é a mesma de `secao_controles._declarado_hoje`: o
        pendente é mais novo que o disco, e mostrar o valor antigo faria o
        clique dela parecer perdido ao trocar de aba e voltar.
        """
        gravado: dict[str, Any] = {}
        with contextlib.suppress(Exception):
            gravado = carregar_maquina().mesa.model_dump(mode="json")
        pendente = getattr(self._host, "_maquina_pendente", None)
        if isinstance(pendente, dict):
            mesa = pendente.get("mesa")
            if isinstance(mesa, dict):
                gravado = fundir_declaracao(gravado, mesa)
        return gravado

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


def _medidores_da_mesa(
    mesa: Mesa, ocupacoes: dict[str, Ocupacao]
) -> list[tuple[str, Ocupacao]]:
    """`[(nome do rádio, ocupação)]` — a lista de barras a desenhar.

    Duas fontes respondem "quais adaptadores existem", e elas não casam: a
    tabela acima vem do sysfs e conhece VID:PID e porta, mas **não conhece o
    endereço** (medido em 22/08: `/sys/class/bluetooth/hci0/` não publica
    `address`); o medidor vem do `HID_PHYS` dos controles e conhece só o
    endereço. Sem um lado que tenha os dois, casar linha com barra seria chute.

    A regra que sai daí tem uma frase: **quem manda é quem sabe.**

    * há controle no rádio -> uma barra por ENDEREÇO, que é o que o desenho
      pede (`Rádio em uso · AA:BB:CC:11:22:33`). Com dois adaptadores e
      controles só num deles, aparece uma barra — a do que está em uso, com
      nome verdadeiro;
    * não há controle nenhum no rádio -> uma barra em ZERO por adaptador da
      tabela, nomeada pela identidade física. É o caso desta bancada, e é o
      controle negativo da sprint: todos os controles no cabo, toda barra em
      zero;
    * não há nem controle nem adaptador -> nenhuma barra. A linha "Nenhum
      adaptador Bluetooth encontrado" já disse tudo, e uma barra vazia embaixo
      dela só ocuparia altura.

    O que a regra NUNCA faz é somar a ocupação de um endereço numa linha da
    tabela por posição. Emprestar o adaptador do vizinho é o erro que a chave
    de ausência existe para impedir.
    """
    if ocupacoes:
        return [(endereco, ocupacoes[endereco]) for endereco in sorted(ocupacoes)]
    return [(_nome_do_adaptador(a), Ocupacao()) for a in mesa.adaptadores]


def _rotulo_do_medidor(nome: str) -> str:
    """O rótulo da barra. Endereço ausente vira "Não sei", nunca `hciN`.

    `hci0` e `hci1` invertem entre boots — é a mesma decisão M1 que tirou o
    `hciN` da tabela acima, e vale em dobro aqui: uma barra que troca de dono
    entre boots faz a pessoa mexer na porta errada.
    """
    if nome == SEM_ADAPTADOR:
        return f"Rádio em uso · {_PAINEL_DESCONHECIDO}"
    return f"Rádio em uso · {nome}"


def _selo_da_ocupacao(ocupacao: Ocupacao) -> str:
    """`831/1600 · derivado da especificação` — o selo mono, montado aqui.

    Montado em Python, e não declarado no Glade, por dois motivos: os dois
    números são calculados, e um rótulo estático começando por "derivado"
    reprovaria no `validar-palavra-de-tela.py` por primeira letra minúscula
    (`:174-186`). Aqui a primeira coisa é um dígito, e o portão de maiúscula
    pula o que não começa por letra.

    A frase depois do meio-ponto não é enfeite: as 1.600 fatias vêm da
    especificação do Bluetooth Classic e **nunca foram medidas nesta máquina**.
    Sem ela, a barra seria lida como medição.
    """
    return (
        f"{round(ocupacao.slots_total)}/{ocupacao.slots_teto} "
        f"· {_SELO_DE_PROCEDENCIA}"
    )


def _texto_acessivel(ocupacao: Ocupacao) -> str:
    """O que o leitor de tela lê na trilha — o `aria-label` do desenho.

    A barra é desenhada em Cairo: sem isto ela é um retângulo sem nome nenhum
    para quem não a enxerga, e a informação inteira do medidor ficaria só na
    cor.
    """
    return f"{round(ocupacao.slots_total)} de {ocupacao.slots_teto}"


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
