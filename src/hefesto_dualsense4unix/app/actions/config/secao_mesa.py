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
adaptador para BT real (`broker/hidraw_broker.py:318`), e
`/sys/class/hidraw/*/device/uevent` abre como uid 1000. É por aí que o medidor
sabe qual controle está em qual adaptador, sem tocar em `sudo`.

A conta, a procedência de cada número e a fronteira que a tela NÃO atravessa
(ocupação nunca é culpa) moram no cabeçalho de
`integrations/radio_da_mesa.py`. Aqui em cima ficam só as três coisas que são
de tela: o rótulo, a cor da palavra e o selo de procedência.

A COLUNA "O QUE É" É LIDA, E ELA SÓ CORRIGE (22/08/2026)
---------------------------------------------------------

Decisão dela: *"classifica sozinho, você só corrige"*. Até aqui a coluna
oferecia SETE botões por linha e perguntava à mão o que o kernel já responde:
`bInterfaceClass/SubClass/Protocol` da interface 0 distingue mouse de teclado
(`03/01/02` contra `03/01/01`) e Bluetooth de "sem fio" (`e0/01/01`). Quem lê
é `integrations/censo_do_barramento`, que nasceu em 22/08/2026 e ficou sem UM
consumidor em `app/` — a `A-CASA-SABE-E-O-PRODUTO-NAO-FAZ` nascendo na mesma
sessão que a documentou.

A ordem de precedência tem três degraus, e ela é o desenho:

1. **a correção dela vence tudo** — `RadioDeclarado.tipo`, no `maquina.json`;
2. **o que o kernel leu vence o botão vazio** — a linha nasce preenchida, com
   o selo `(lido)`, e o seletor só aparece se ela clicar em "Corrigir";
3. **quando ninguém sabe** — classe `ff`, em que o fabricante declinou de
   classificar — a linha nasce com o seletor aberto e o `▲`. Na bancada dela,
   das quatro linhas de rádio vizinho, só UMA cai aqui.

A junção entre as duas leituras é o `no` — o caminho real no sysfs, a mesma
convenção nos dois módulos. Nunca o `vid:pid`, que é a chave do que ELA
declarou e que se repete quando há duas unidades do mesmo aparelho.

O NOME DE CADA ADAPTADOR (22/08/2026)
--------------------------------------

Decisão dela: *"você escreve, o produto protege o prefixo"*. Três adaptadores
`2357:0604` idênticos no barramento, e a única coisa que os separa é o BD
Address — que não é nome. Quem lê e escreve o `org.bluez.Adapter1.Alias` é
`integrations/apelido_do_dongle`, o segundo módulo que estava sem consumidor.

Duas coisas desta tela dependem dele, e as duas juntas são a razão de ele ser
lido aqui e não em outro lugar:

* a coluna **"Nome"** da tabela de adaptadores, que é um campo livre. O que a
  tela mostra é o nome DELA, limpo: o prefixo `Nintendo` que segura o Pro
  Controller fora do sniff frágil é costurado por baixo, e ela nunca precisa
  saber que existe;
* o **rótulo do medidor**, que passa a dizer `Rádio em uso · Sala` em vez de um
  endereço hexa. Essa junção é por ENDEREÇO dos dois lados (o `HID_PHYS` do
  controle contra o `Address` do BlueZ) e não tem chute nenhum dentro.

A junção da TABELA é outra, e ela é a única coisa aqui que usa `hciN`: o
`Adaptador.interface` do sysfs contra o `/org/bluez/hciN` do BlueZ. O índice
inverte entre boots e por isso ele nunca é guardado — a correspondência é
refeita a cada leitura, e as duas leituras acontecem no mesmo gesto. O que vai
para a escrita é sempre o BD Address.

AS TRÊS COSTURAS DE 26/08/2026 (L2-E)
--------------------------------------

As três fecham a mesma classe de defeito — a casa sabe e o produto não faz — e
cada uma tem o "porquê" inteiro junto da constante que a carrega:

1. **o gabinete que o install já contou.** O ``install.sh`` grava o
   ``gabinete.json`` em toda instalação desde 25/08/2026 e nenhuma linha de
   ``app/`` o abria. Agora a seção o publica — **as duas contagens lado a lado
   quando elas divergem, e nunca uma escolha** (:func:`_linhas_do_gabinete`);
2. **o hub em comum.** A coluna "Onde está" escrevia ``Em hub`` linha a linha e
   nunca comparava as linhas entre si; ``censo_do_barramento.hub_em_comum``
   respondia desde 22/08 e não tinha chamador (:func:`_frase_do_hub_em_comum`);
3. **a porta da calibração.** ``app/widgets/calibrar_entradas.py`` nasceu
   inteira na leva 1 e nada a abria (:meth:`_PainelDaMesa._abrir_a_calibracao`).

Todo texto novo delas está marcado ``PROVISÓRIO — decisão dela``, e a prova de
tela não fechou: a palavra final é dela.

**O nome grava NA HORA**, e a frase ao lado do campo diz isso. As três
declarações desta seção esperam o "Aplicar" do rodapé porque moram no
`maquina.json`; o alias mora no BlueZ, que não passa pelo rascunho da máquina
nem pelo rodapé. Duas semânticas na mesma seção é dívida declarada — ver o
relatório da leva.
"""
from __future__ import annotations

import contextlib
from collections.abc import Sequence
from typing import Any

from hefesto_dualsense4unix.app.actions.config.moldura import (
    QUANDO_VALE,
    rotulo_de_apoio,
)
from hefesto_dualsense4unix.integrations.apelido_do_dongle import (
    Dongle,
    ler_os_dongles,
)
from hefesto_dualsense4unix.integrations.censo_do_barramento import (
    GRAU_LIDO,
    Censo,
    hub_em_comum,
    ler_o_barramento,
)
from hefesto_dualsense4unix.integrations.censo_do_gabinete import (
    contagens_declaradas,
    ler_do_disco,
    pergunta_pendente,
)
from hefesto_dualsense4unix.integrations.entradas_do_gabinete import (
    Furo,
    NoDeEntrada,
    listar_entradas,
)
from hefesto_dualsense4unix.integrations.mapa_das_portas import (
    porta_de,
    resumo_do_mapa,
)
from hefesto_dualsense4unix.integrations.mesa_de_radio import (
    Adaptador,
    Mesa,
    RadioUsb,
    ler_a_mesa,
)
from hefesto_dualsense4unix.integrations.portas_do_barramento import (
    livres,
)
from hefesto_dualsense4unix.integrations.radio_da_mesa import (
    PALAVRA_FOLGADA,
    SEM_ADAPTADOR,
    Ocupacao,
    ocupacao_por_adaptador,
)
from hefesto_dualsense4unix.utils.i18n import _
from hefesto_dualsense4unix.utils.logging_config import get_logger
from hefesto_dualsense4unix.utils.maquina import (
    MapaDaMesa,
    carregar_maquina,
    fundir_declaracao,
)

logger = get_logger(__name__)

#: constante (`ipc_bridge.py:661`), nunca a copia.
TITULO = "Conexões"

DICA: str | None = (
    "O Hefesto enxerga os adaptadores, mas não enxerga onde eles estão. Cabo, "
    "hub e altura mudam o alcance e não aparecem em lugar nenhum do sistema."
)

_TIPOS_DE_RADIO: tuple[tuple[str, str], ...] = (
    ("wifi", "Wi-Fi"),
    ("teclado", "Teclado"),
    ("mouse", "Mouse"),
    ("webcam", "Webcam"),
    ("caixa_de_som", "Caixa de som"),
    ("outro", "Outro"),
    ("nao_sei", "Não sei"),
)

_PALAVRA_DO_TIPO: dict[str, str] = dict(_TIPOS_DE_RADIO)

_SELO_LIDO = "(lido)"
_SELO_DECLARADO = "(você disse)"

_DICA_LIDO = (
    "O próprio aparelho informou ao sistema o que ele é. "
    'Se estiver errado, clique em "Corrigir".'
)

_DICA_DECLARADO = (
    'Foi você quem respondeu isto. Clique em "Corrigir" para trocar a resposta.'
)

_BOTAO_CORRIGIR = "Corrigir"

_AVISO_NAO_SABE = "▲ O Hefesto não sabe"

_DICA_NAO_SABE = (
    "Este aparelho não diz ao sistema para que serve. É a única linha que "
    "precisa de você."
)

_COLUNA_NOME = "Nome"
_DICA_DO_NOME = (
    "Adaptadores iguais são idênticos no sistema. O nome é seu, e é ele que "
    "diz qual é qual."
)

_NOME_EM_BRANCO = "Sem nome"

_NOME_VALE_JA = (
    "O nome vai para o Bluetooth do sistema assim que você aperta Enter."
)

_NOTA_DO_PREFIXO = (
    "▲ Um dos adaptadores guarda a palavra Nintendo por dentro do nome: é ela "
    "que impede o Pro Controller de cair sob carga. O Hefesto cuida disso "
    "sozinho, e o nome que você lê aqui é só o seu."
)

_PAINEL_EM_PORTUGUES: dict[str, str] = {
    "front": "Frente",
    "back": "Trás",
    "left": "Esquerda",
    "right": "Direita",
    "top": "Cima",
    "bottom": "Baixo",
}

_PAINEL_DESCONHECIDO = "Não sei"


_PERGUNTA_DA_ALTURA = "O dongle fica acima da cabeça de quem joga sentado?"

_DICA_DA_ALTURA = (
    "Corpo humano absorve 2,4 GHz. Um dongle acima da linha das cabeças rende "
    "mais que um dongle perto. Isto nenhum sistema sabe — só você."
)

_PERGUNTA_DA_VISADA = "Tem gente sentada entre o dongle e o sofá?"

_DICA_DA_VISADA = (
    "Gente no caminho entre o dongle e quem joga custa alcance, e também não "
    "há como medir daqui."
)

_DICA_COLADOS = (
    "Dois rádios encostados um no outro se atrapalham. Vale afastar em portas "
    "diferentes."
)

_DICA_USB3_AO_LADO = (
    "USB 3.0 emite ruído de banda larga bem em cima dos 2,4 GHz. Ao lado do "
    "adaptador Bluetooth, atrapalha."
)

_LARANJA = "#ffb86c"

_VERDE = "#50fa7b"

_DICA_DO_MEDIDOR = (
    "Aritmética da especificação do Bluetooth, não medição desta máquina: o "
    "rádio tem 1.600 fatias de tempo por segundo e todos os controles do mesmo "
    "adaptador as dividem."
)

_SELO_DE_PROCEDENCIA = "derivado da especificação"

_SEM_RESPOSTA_DO_DAEMON = "o daemon não respondeu"

_LARGURA_DA_FRASE = 84


def montar(host: Any, caixa: Any) -> None:
    """Monta a seção dentro de `caixa` — a caixa interna da moldura."""
    painel = _PainelDaMesa(host)
    painel.montar(caixa)
    host._reexaminar_a_mesa = painel.reexaminar
    host._mesa_declarada = painel.declarado


class _PainelDaMesa:
    """Os widgets da seção e a leitura que os preenche."""

    def __init__(self, host: Any) -> None:
        self._host = host
        self._caixa_adaptadores: Any = None
        self._caixa_radios: Any = None
        self._caixa_medidores: Any = None
        self._mesa = Mesa()
        self._censo = Censo()
        self._mapa = MapaDaMesa()
        self._caixa_do_mapa: Any = None
        self._gabinete: dict[str, Any] = {}
        self._entradas: tuple[NoDeEntrada, ...] = ()
        self._caixa_do_gabinete: Any = None
        self._caixa_do_hub: Any = None
        self._dongles: tuple[Dongle, ...] = ()
        self._dongles_pedidos = False
        self._corrigindo: set[str] = set()
        self._campos_de_nome: dict[str, Any] = {}
        self._controles: list[dict[str, Any]] = []
        self._com_mic: frozenset[str] = frozenset()
        self._estado_pedido = False
        self._daemon_respondeu: bool | None = None
        self.declarado: dict[str, str | None] = {
            "altura_da_antena": None,
            "linha_de_visada": None,
        }
        self.radios_declarados: dict[str, str | None] = {}


    def montar(self, caixa: Any) -> None:
        """Desenha a seção inteira e faz a primeira leitura."""
        from gi.repository import Gtk

        self._caixa_adaptadores = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        caixa.pack_start(self._caixa_adaptadores, False, False, 0)

        self._caixa_do_hub = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        caixa.pack_start(self._caixa_do_hub, False, False, 0)

        self._caixa_do_mapa = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        caixa.pack_start(self._caixa_do_mapa, False, False, 0)

        self._caixa_do_gabinete = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        caixa.pack_start(self._caixa_do_gabinete, False, False, 0)

        caixa.pack_start(self._declaracoes(), False, False, 0)

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
        self._reler_a_mesa()

    def _declaracoes(self) -> Any:
        """As duas perguntas que barramento nenhum responde."""
        from gi.repository import Gtk

        caixa = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        caixa.set_margin_top(6)
        caixa.pack_start(
            self._linha_declarada(
                "altura_da_antena",
                _PERGUNTA_DA_ALTURA,
                _DICA_DA_ALTURA,
                [
                    ("acima", "Sim"),
                    ("abaixo", "Não"),
                    ("nao_sei", "Não sei"),
                ],
            ),
            False,
            False,
            0,
        )
        caixa.pack_start(
            self._linha_declarada(
                "linha_de_visada",
                _PERGUNTA_DA_VISADA,
                _DICA_DA_VISADA,
                [
                    ("com_gente", "Sim"),
                    ("livre", "Não"),
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
        """Rótulo com dica mais botões segmentados, numa fileira."""
        from gi.repository import Gtk

        from hefesto_dualsense4unix.app.widgets.segmented_selector import (
            SegmentedSelector,
        )

        fileira = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        texto = Gtk.Label(label=_(rotulo))
        texto.set_xalign(0.0)
        # acontecer é quem precisa da frase, e ela está sob o cursor dele.
        texto.set_tooltip_text(f"{_(dica)} {_(QUANDO_VALE)}")
        with contextlib.suppress(Exception):
            texto.get_style_context().add_class("hefesto-rotulo")
        fileira.pack_start(texto, False, False, 0)

        seletor = SegmentedSelector()
        # em cinco outras.
        seletor.set_orientation(Gtk.Orientation.HORIZONTAL)
        seletor.set_items([(ident, _(nome)) for ident, nome in itens])
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
        """O botão que relê o barramento."""
        from gi.repository import Gtk

        fileira = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        fileira.set_margin_top(6)
        # A PALAVRA "mesa" SAIU DA TELA em 05/09/2026, ordem dela. O que este
        botao = Gtk.Button(label=_("Reexaminar as conexões"))
        botao.set_tooltip_text(_("Relê os adaptadores e os rádios. Não muda nada."))
        botao.connect("clicked", self._ao_clicar_reexaminar)
        fileira.pack_start(botao, False, False, 0)
        return fileira


    def reexaminar(self) -> None:
        """Relê tudo: o barramento agora, e quem está no rádio quando chegar."""
        self._reler_a_mesa()
        self._pedir_o_estado()
        self._pedir_os_dongles()

    def _reler_a_mesa(self) -> None:
        """A metade síncrona: `/sys` agora, as três caixas redesenhadas."""
        try:
            mesa = self._ler()
            self._mesa = mesa
            self._censo = self._ler_o_censo()
            self._entradas = self._ler_as_entradas()
            self._gabinete = self._ler_o_gabinete()
            self._mapa = self._mapa_em_vigor()
            self._ler_os_dongles_de_bancada()
            self._desenhar_adaptadores(mesa)
            self._desenhar_o_hub()
            self._desenhar_o_mapa()
            self._desenhar_o_gabinete()
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

    def _ler_o_censo(self) -> Censo:
        """O barramento USB inteiro — ou a bancada de mentira do retrato."""
        leitor = getattr(self._host, "_censo_leitor", None)
        if leitor is not None:
            resultado = leitor()
            return resultado if isinstance(resultado, Censo) else Censo()
        if getattr(self._host, "_mesa_leitor", None) is not None:
            return Censo()
        return ler_o_barramento()

    def _ler_as_entradas(self) -> tuple[NoDeEntrada, ...]:
        """Os nós de entrada, inclusive os VAZIOS — ou a bancada de mentira."""
        leitor = getattr(self._host, "_entradas_leitor", None)
        if leitor is not None:
            with contextlib.suppress(Exception):
                return tuple(leitor())
            return ()
        if getattr(self._host, "_mesa_leitor", None) is not None:
            return ()
        return listar_entradas()

    def _ler_o_gabinete(self) -> dict[str, Any]:
        """O `gabinete.json` que o install gravou — `{}` quando não há."""
        leitor = getattr(self._host, "_gabinete_leitor", None)
        if leitor is not None:
            with contextlib.suppress(Exception):
                lido = leitor()
                return lido if isinstance(lido, dict) else {}
            return {}
        if getattr(self._host, "_mesa_leitor", None) is not None:
            return {}
        return ler_do_disco()

    def _ler_os_dongles_de_bancada(self) -> None:
        """A leitura do BlueZ quando ela é de mentira — e só então.

        O dublê é de MEMÓRIA e responde na hora, então entra no caminho
        síncrono. A leitura de verdade não pode: ela é `busctl`, um subprocesso
        por propriedade e por adaptador, e este método roda dentro de `montar`.

        `montar` acontece no ARRANQUE da janela (`app/app.py:1217` e `:1487`),
        inclusive em quem sobe minimizado na bandeja — é a mesma decisão E6 que
        mantém o `daemon.state_full` fora daqui. Uma aba que ninguém abriu não
        fala com o BlueZ nem gasta treze subprocessos.
        """
        leitor = getattr(self._host, "_dongles_leitor", None)
        if leitor is None:
            return
        with contextlib.suppress(Exception):
            self._dongles = tuple(leitor())

    def _pedir_os_dongles(self) -> None:
        """Pede ao BlueZ o nome de cada adaptador — fora da thread da tela."""
        if getattr(self._host, "_dongles_leitor", None) is not None:
            return
        if getattr(self._host, "_mesa_leitor", None) is not None:
            return
        if not self._mesa.adaptadores or self._dongles_pedidos:
            return

        from hefesto_dualsense4unix.app.ipc_bridge import run_in_thread

        def _chegaram(resultado: Any) -> bool:
            self._dongles_pedidos = False
            if isinstance(resultado, tuple):
                self._dongles = resultado
                self._redesenhar_os_nomes()
            return False

        def _falhou(_exc: Exception) -> bool:
            self._dongles_pedidos = False
            return False

        self._dongles_pedidos = True
        run_in_thread(ler_os_dongles, _chegaram, _falhou)

    def _redesenhar_os_nomes(self) -> None:
        """Redesenha o que depende do BlueZ — a não ser que ela esteja digitando."""
        digitando = any(
            campo.has_focus()
            for campo in self._campos_de_nome.values()
            if hasattr(campo, "has_focus")
        )
        if digitando:
            return
        self._desenhar_adaptadores(self._mesa)
        self._desenhar_medidores()

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
        from hefesto_dualsense4unix.app.actions.mode_transition import (
            STATE_IPC_TIMEOUT_S,
        )
        from hefesto_dualsense4unix.app.ipc_bridge import call_async

        def _chegou(estado: Any) -> bool:
            self._estado_pedido = False
            self._daemon_respondeu = True
            self._aplicar_estado(estado if isinstance(estado, dict) else None)
            return False

        def _falhou(_exc: Exception) -> bool:
            self._estado_pedido = False
            self._daemon_respondeu = False
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
        bloco = (estado or {}).get("bt_mic")
        uniqs = bloco.get("uniqs") if isinstance(bloco, dict) else None
        if isinstance(uniqs, list):
            self._com_mic = frozenset(u for u in uniqs if isinstance(u, str))
        else:
            self._com_mic = frozenset()
        self._desenhar_medidores()


    def _desenhar_adaptadores(self, mesa: Mesa) -> None:
        """A tabela de adaptadores — ou a frase de que não há nenhum."""
        if self._caixa_adaptadores is None:
            return
        self._esvaziar(self._caixa_adaptadores)
        if not mesa.adaptadores:
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

        por_interface = _dongle_por_interface(self._dongles)
        com_nome = any(
            adaptador.interface in por_interface for adaptador in mesa.adaptadores
        )
        self._campos_de_nome = {}

        cabecalhos = ["Adaptador", "Onde está"]
        if com_nome:
            cabecalhos.insert(0, _COLUNA_NOME)
        grade = self._grade(cabecalhos)
        if com_nome:
            with contextlib.suppress(Exception):
                grade.get_child_at(0, 0).set_tooltip_text(_(_DICA_DO_NOME))

        for linha, adaptador in enumerate(mesa.adaptadores, start=1):
            coluna = 0
            if com_nome:
                grade.attach(
                    self._campo_do_nome(por_interface.get(adaptador.interface)),
                    coluna,
                    linha,
                    1,
                    1,
                )
                coluna += 1
            grade.attach(
                self._celula_mono(_nome_do_adaptador(adaptador)), coluna, linha, 1, 1
            )
            texto, dica = _onde_esta_o_adaptador(adaptador, self._mapa)
            grade.attach(self._celula(texto, dica=dica), coluna + 1, linha, 1, 1)
        self._caixa_adaptadores.pack_start(grade, False, False, 0)

        if com_nome:
            self._caixa_adaptadores.pack_start(
                rotulo_de_apoio(_NOME_VALE_JA, largura_max=_LARGURA_DA_FRASE),
                False,
                False,
                0,
            )
            if any(d.hospeda_nintendo for d in self._dongles):
                self._caixa_adaptadores.pack_start(
                    rotulo_de_apoio(_NOTA_DO_PREFIXO, largura_max=_LARGURA_DA_FRASE),
                    False,
                    False,
                    0,
                )
        self._caixa_adaptadores.show_all()

    def _campo_do_nome(self, dongle: Dongle | None) -> Any:
        """O campo livre do nome de um adaptador — ou uma célula vazia."""
        from gi.repository import Gtk

        if dongle is None:
            return self._celula("")

        campo = Gtk.Entry()
        campo.set_text(dongle.nome)
        campo.set_placeholder_text(_(_NOME_EM_BRANCO))
        campo.set_width_chars(12)
        campo.set_max_width_chars(16)
        campo.set_hexpand(False)
        campo.set_tooltip_text(_(_DICA_DO_NOME))
        campo.connect("activate", self._ao_salvar_o_nome, dongle.endereco)
        campo.connect("focus-out-event", self._ao_sair_do_nome, dongle.endereco)
        self._campos_de_nome[dongle.endereco] = campo
        return campo

    def _desenhar_radios(self, mesa: Mesa) -> None:
        """A tabela dos outros rádios — ou a frase de que não há nenhum."""
        if self._caixa_radios is None:
            return
        self._esvaziar(self._caixa_radios)
        if not mesa.radios:
            self._caixa_radios.pack_start(
                rotulo_de_apoio(
                    "Nenhum outro rádio espetado no computador.",
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
                    _onde_esta_o_radio(radio, aviso, self._mapa),
                    dica=None if aviso is None else aviso[1],
                    alerta=aviso is not None,
                ),
                1,
                linha,
                1,
                1,
            )
            declarado = gravados.get(chave)
            tipo = declarado.get("tipo") if isinstance(declarado, dict) else None
            if tipo is not None:
                self.radios_declarados[chave] = str(tipo)
            grade.attach(
                self._celula_do_que_e(radio, chave, tipo),
                2,
                linha,
                1,
                1,
            )
        self._caixa_radios.pack_start(grade, False, False, 0)
        self._caixa_radios.show_all()

    def _celula_do_que_e(self, radio: RadioUsb, chave: str, gravado: Any) -> Any:
        """A coluna "O que é" — a resposta já pronta, ou o seletor."""
        from gi.repository import Gtk

        if chave in self._corrigindo:
            return self._seletor_do_tipo(chave, gravado)

        if gravado is not None:
            palavra = _PALAVRA_DO_TIPO.get(str(gravado), str(gravado))
            return self._celula_respondida(
                palavra, _SELO_DECLARADO, _DICA_DECLARADO, chave
            )

        aparelho = self._censo.aparelho(radio.no)
        if aparelho is not None and aparelho.grau == GRAU_LIDO:
            return self._celula_respondida(
                aparelho.especie, _SELO_LIDO, _DICA_LIDO, chave
            )

        fileira = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        fileira.pack_start(self._seletor_do_tipo(chave, gravado), False, False, 0)
        aviso = Gtk.Label(label=_AVISO_NAO_SABE)
        aviso.set_xalign(0.0)
        aviso.set_tooltip_text(_(_DICA_NAO_SABE))
        with contextlib.suppress(Exception):
            aviso.get_style_context().add_class("dim-label")
        fileira.pack_start(aviso, False, False, 0)
        return fileira

    def _celula_respondida(
        self, palavra: str, selo: str, dica: str, chave: str
    ) -> Any:
        """Palavra, selo de procedência e o botão que reabre a pergunta."""
        from gi.repository import Gtk

        fileira = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)

        rotulo = Gtk.Label(label=_(palavra))
        rotulo.set_xalign(0.0)
        rotulo.set_tooltip_text(_(dica))
        with contextlib.suppress(Exception):
            rotulo.get_style_context().add_class("hefesto-rotulo")
        fileira.pack_start(rotulo, False, False, 0)

        marca = Gtk.Label(label=selo)
        marca.set_xalign(0.0)
        marca.set_tooltip_text(_(dica))
        with contextlib.suppress(Exception):
            marca.get_style_context().add_class("hefesto-valor-mono-peq")
            marca.get_style_context().add_class("dim-label")
        fileira.pack_start(marca, False, False, 0)

        botao = Gtk.Button(label=_(_BOTAO_CORRIGIR))
        botao.set_tooltip_text(_(dica))
        botao.connect("clicked", self._ao_corrigir, chave)
        fileira.pack_start(botao, False, False, 0)
        return fileira

    def _ao_corrigir(self, _botao: Any, chave: str) -> None:
        """Abre o seletor daquela linha. Não grava nada, não relê nada."""
        self._corrigindo.add(chave)
        self._desenhar_radios(self._mesa)

    def _seletor_do_tipo(self, chave_do_radio: str, gravado: Any) -> Any:
        """Os seis tipos mais "Não sei", em fileira única."""
        from gi.repository import Gtk

        from hefesto_dualsense4unix.app.widgets.segmented_selector import (
            SegmentedSelector,
        )

        seletor = SegmentedSelector()
        seletor.set_orientation(Gtk.Orientation.HORIZONTAL)
        seletor.set_items([(ident, _(nome)) for ident, nome in _TIPOS_DE_RADIO])
        seletor.set_hexpand(False)
        if gravado is not None:
            with contextlib.suppress(Exception):
                seletor.set_active_id(str(gravado))
        seletor.connect("changed", self._ao_declarar_o_radio, chave_do_radio)
        return seletor


    def _desenhar_medidores(self) -> None:
        """Uma barra por adaptador — ou nenhuma, quando não há adaptador."""
        if self._caixa_medidores is None:
            return
        self._esvaziar(self._caixa_medidores)
        apelidos = _apelido_por_endereco(self._dongles)
        for nome, ocupacao in _medidores_da_mesa(
            self._mesa, self._ocupacoes(), _dongle_por_interface(self._dongles)
        ):
            self._caixa_medidores.pack_start(
                self._fileira_do_medidor(nome, ocupacao, apelidos),
                False,
                False,
                0,
            )
        self._caixa_medidores.show_all()

    def _ocupacoes(self) -> dict[str, Ocupacao]:
        """A conta, ou nada quando o sysfs não responde."""
        try:
            return ocupacao_por_adaptador(
                self._controles, com_ponte_de_mic=self._com_mic
            )
        except Exception:
            logger.warning("medidor_de_radio_falhou", exc_info=True)
            self._daemon_respondeu = False
            return {}

    def _fileira_do_medidor(
        self, nome: str, ocupacao: Ocupacao, apelidos: dict[str, str] | None = None
    ) -> Any:
        """Rótulo, trilha de duas fatias, a palavra e o selo — nesta ordem."""
        from gi.repository import Gtk
        from gi.repository.GLib import markup_escape_text

        from hefesto_dualsense4unix.app.widgets.sensor_widgets import MedidorDeRadio

        fileira = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        fileira.set_margin_top(4)

        rotulo = Gtk.Label(label=_(_rotulo_do_medidor(nome, apelidos)))
        rotulo.set_xalign(0.0)
        rotulo.set_tooltip_text(_(_DICA_DO_MEDIDOR))
        with contextlib.suppress(Exception):
            rotulo.get_style_context().add_class("hefesto-rotulo")
        fileira.pack_start(rotulo, False, False, 0)

        medidor = MedidorDeRadio()
        medidor.set_ocupacao(ocupacao.fracao_input, ocupacao.fracao_audio)
        medidor.set_hexpand(True)
        medidor.set_valign(Gtk.Align.CENTER)

        sabido = self._daemon_respondeu is True
        with contextlib.suppress(Exception):
            medidor.get_accessible().set_name(_texto_acessivel(ocupacao, sabido=sabido))
        fileira.pack_start(medidor, True, True, 0)

        palavra = Gtk.Label()
        if sabido:
            dizer = ocupacao.rotulo
            cor = _VERDE if ocupacao.rotulo == PALAVRA_FOLGADA else _LARANJA
        else:
            dizer = _PAINEL_DESCONHECIDO
            cor = _LARANJA
        palavra.set_markup(
            f'<span foreground="{cor}">{markup_escape_text(_(dizer))}</span>'
        )
        palavra.set_xalign(0.0)
        with contextlib.suppress(Exception):
            palavra.get_style_context().add_class("hefesto-valor-mono-peq")
        fileira.pack_start(palavra, False, False, 0)

        selo = Gtk.Label(label=_selo_da_ocupacao(ocupacao, sabido=sabido))
        selo.set_xalign(0.0)
        with contextlib.suppress(Exception):
            selo.get_style_context().add_class("hefesto-valor-mono-peq")
            selo.get_style_context().add_class("dim-label")
        fileira.pack_start(selo, False, False, 0)
        return fileira

    def _grade(self, cabecalhos: list[str]) -> Any:
        """Uma grade com a fileira de cabeçalhos já posta."""
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


    def _ao_declarar(self, seletor: Any, chave: str) -> None:
        """Acumula a escolha no rascunho da máquina. NÃO grava, NÃO manda IPC."""
        escolha = self._valor_do_seletor(seletor)
        self.declarado[chave] = escolha
        self._acumular({chave: escolha})

    def _ao_declarar_o_radio(self, seletor: Any, chave_do_radio: str) -> None:
        """O mesmo gesto, para o `tipo` de um rádio vizinho."""
        escolha = self._valor_do_seletor(seletor)
        self.radios_declarados[chave_do_radio] = escolha
        self._acumular({"radios": {chave_do_radio: {"tipo": escolha}}})

    @staticmethod
    def _valor_do_seletor(seletor: Any) -> str | None:
        """O id ativo, com `"nao_sei"` traduzido para a ausência de opinião."""
        ativo = seletor.get_active_id()
        return None if ativo in (None, "nao_sei") else str(ativo)

    def _acumular(self, mesa: dict[str, Any]) -> None:
        """Funde o pedaço em `host._maquina_pendente`, sob a chave `mesa`."""
        with contextlib.suppress(Exception):
            self._host._maquina_pendente = fundir_declaracao(
                getattr(self._host, "_maquina_pendente", None),
                {"mesa": mesa},
            )
        marcar = getattr(self._host, "_marcar_declaracao_por_aplicar", None)
        if marcar is not None:
            with contextlib.suppress(Exception):
                marcar()

    def _desenhar_o_mapa(self) -> None:
        """A linha-resumo do gabinete dela, mais o botão que abre o desenho."""
        if self._caixa_do_mapa is None:
            return
        self._esvaziar(self._caixa_do_mapa)
        self._caixa_do_mapa.pack_start(
            _linha_do_mapa(self._mapa, self._censo, self._abrir_o_desenho),
            False,
            False,
            0,
        )
        self._caixa_do_mapa.show_all()

    def _desenhar_o_hub(self) -> None:
        """A linha do hub em comum — e o conselho, quando há para onde mandar."""
        if self._caixa_do_hub is None:
            return
        from gi.repository import Gtk

        self._esvaziar(self._caixa_do_hub)
        fato, por_que, conselho = _frase_do_hub_em_comum(
            self._mesa, self._censo, self._entradas
        )
        if not fato:
            return
        caixa = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        caixa.set_margin_top(6)
        for texto in (fato, por_que, conselho):
            if texto:
                caixa.pack_start(
                    rotulo_de_apoio(texto, largura_max=_LARGURA_DA_FRASE),
                    False,
                    False,
                    0,
                )
        self._caixa_do_hub.pack_start(caixa, False, False, 0)
        self._caixa_do_hub.show_all()

    def _desenhar_o_gabinete(self) -> None:
        """As contagens do gabinete, a pergunta, e o botão da calibração."""
        if self._caixa_do_gabinete is None:
            return
        from gi.repository import Gtk

        self._esvaziar(self._caixa_do_gabinete)
        caixa = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        caixa.set_margin_top(6)
        for texto in _linhas_do_gabinete(self._gabinete):
            caixa.pack_start(
                rotulo_de_apoio(texto, largura_max=_LARGURA_DA_FRASE), False, False, 0
            )
        fileira = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        botao = Gtk.Button(label=_(_BOTAO_CALIBRAR))
        botao.set_tooltip_text(_(_DICA_CALIBRAR))
        botao.connect("clicked", self._abrir_a_calibracao)
        fileira.pack_start(botao, False, False, 0)
        caixa.pack_start(fileira, False, False, 0)
        self._caixa_do_gabinete.pack_start(caixa, False, False, 0)
        self._caixa_do_gabinete.show_all()

    def _abrir_a_calibracao(self, _botao: Any = None) -> None:
        """Abre a cerimônia de calibração — a janela que a leva 1 entregou."""
        from hefesto_dualsense4unix.app.widgets.calibrar_entradas import (
            JanelaDeCalibrarEntradas,
        )

        janela = JanelaDeCalibrarEntradas(
            self._host, self._mapa, self._censo, self._entradas
        )
        with contextlib.suppress(Exception):
            janela.connect("destroy", lambda *_a: self.reexaminar())
        janela.show_all()

    def _abrir_o_desenho(self, _botao: Any = None) -> None:
        """Abre a janela do mapa 2D — e ela grava no rascunho, não no disco."""
        from hefesto_dualsense4unix.app.widgets.mapa_da_mesa import (
            JanelaDoMapaDaMesa,
        )

        janela = JanelaDoMapaDaMesa(
            self._host, self._mapa, self._censo, ao_fechar=self.reexaminar
        )
        janela.show_all()

    def _mapa_em_vigor(self) -> MapaDaMesa:
        """O mapa do DISCO, com o rascunho que espera o "Aplicar" por cima."""
        bruto: dict[str, Any] = {}
        with contextlib.suppress(Exception):
            bruto = carregar_maquina().mapa.model_dump(mode="json")
        pendente = getattr(self._host, "_maquina_pendente", None)
        if isinstance(pendente, dict):
            mapa = pendente.get("mapa")
            if isinstance(mapa, dict):
                bruto = fundir_declaracao(bruto, mapa)
        try:
            return MapaDaMesa.model_validate(bruto)
        except Exception:
            logger.debug("mapa_em_vigor_invalido", exc_info=True)
            return MapaDaMesa()

    def _mesa_em_vigor(self) -> dict[str, Any]:
        """O que está no DISCO, com o que ainda espera o "Aplicar" por cima."""
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

    def _ao_sair_do_nome(self, campo: Any, _evento: Any, endereco: str) -> bool:
        """Sair do campo salva. Devolve `False` para não engolir o foco."""
        self._ao_salvar_o_nome(campo, endereco)
        return False

    def _ao_salvar_o_nome(self, campo: Any, endereco: str) -> None:
        """Grava o nome do adaptador, pelo endereço — e só quando ele MUDOU.

        UM ESCRITOR SÓ — TRANSPLANTE-DA-SECAO-01, item 1 (23/09/2026). Esta
        janela escrevia o `Alias` no BlueZ por endereço (`renomear_o_dongle`),
        a aba 08 também, e o `bt_active_mode.sh` trocava o apelido pelo nome do
        lugar no tique seguinte: três escritores do mesmo nome, e o último a
        escrever ganhava. Agora o nome mora no `maquina.json`
        (`entrada_a_entrada.dar_nome_ao_adaptador`, pelo endereço desde
        26/09/2026 — antes era o da entrada, e os dois se confundiam), e o
        `Alias` é a projeção que o watchdog escreve.

        A comparação é contra `Dongle.nome`, que é o alias já limpo da costura:
        sem ela, cada troca de aba regravaria o nome que já está lá.

        O ESPELHO DE MEMÓRIA fica, pela razão de sempre: o `Alias` só muda no
        próximo tique do watchdog, e o próximo `focus-out` compararia contra o
        nome velho e gravaria o mesmo nome de novo.
        """
        alvo = next(
            (d for d in self._dongles if d.endereco == endereco),
            None,
        )
        if alvo is None:
            return
        novo = campo.get_text().strip()
        if novo == alvo.nome:
            return
        try:
            from hefesto_dualsense4unix.integrations.entrada_a_entrada import (
                dar_nome_ao_adaptador,
            )

            feito = dar_nome_ao_adaptador(endereco, novo)
        except Exception:
            logger.warning("nome_do_adaptador_falhou", exc_info=True)
            return
        if not feito.gravou:
            with contextlib.suppress(Exception):
                campo.set_tooltip_text(_(_DICA_DO_NOME))
            return
        self._dongles = tuple(
            Dongle(
                endereco=d.endereco,
                alias=novo,
                nome_do_sistema=d.nome_do_sistema,
                hospeda_nintendo=d.hospeda_nintendo,
                ligado=d.ligado,
                objeto=d.objeto,
            )
            if d.endereco == endereco
            else d
            for d in self._dongles
        )
        with contextlib.suppress(Exception):
            campo.set_tooltip_text(_(_DICA_DO_NOME))
        self._desenhar_medidores()


def _nome_do_adaptador(adaptador: Adaptador) -> str:
    """O nome de tela — identidade física, NUNCA `hciN`."""
    if not adaptador.vid or not adaptador.pid:
        return "Adaptador embutido"
    return f"{adaptador.vid}:{adaptador.pid}"


_PROCEDENCIA_DA_ENTRADA = (
    "Foi você quem desenhou este mapa: este aparelho está na entrada {numero}. "
    "O sistema o enumera como {caminho}."
)

_RESUMO_DO_MAPA = "Mapa: {faces} faces, {entradas} entradas, {colocados} aparelhos colocados."

#: botão ao lado — que é o "o que fazer" desta frase e passou a chamar-se
_SEM_MAPA = (
    "Você ainda não mapeou as suas entradas. Enquanto isso o Hefesto diz o caminho "
    "do sistema (3-1.1.4) em vez do número da sua entrada, e não sabe quais "
    "entradas ficam coladas no metal — então ele não avisa quando dois "
    "receptores sem fio estão encostados. Não é que esteja tudo bem: ele não "
    "sabe."
)

_BOTAO_DESENHAR = "Mapear Entradas"


_GABINETE_FIRMWARE = "A BIOS desta placa conta {numero} entradas USB."

_GABINETE_SISTEMA = "Contando pelo que o sistema enxerga, são {numero}."

_GABINETE_DELA = "Você disse que a sua traseira tem {numero}."

_BOTAO_CALIBRAR = "Mapear Entrada a Entrada"

_DICA_CALIBRAR = (
    "Um toque por aparelho, sentado, e o Hefesto aprende em que entrada cada "
    "um está. As entradas vazias só o computador não alcança — essas você "
    "ensina de pé, se quiser, e pode parar em qualquer passo."
)


_HUB_EM_COMUM = (
    "Os {numero} adaptadores chegam ao computador por dentro do mesmo hub."
)

_HUB_POR_QUE = (
    "Tudo que passa por esse hub divide o mesmo caminho com o que mais estiver "
    "nele."
)

_HUB_CONSELHO_UMA = (
    "Há 1 entrada livre num caminho diferente do computador: levar um dos "
    "adaptadores para lá tira o hub do caminho dele."
)

_HUB_CONSELHO_VARIAS = (
    "Há {numero} entradas livres num caminho diferente do computador: levar um "
    "dos adaptadores para lá tira o hub do caminho dele."
)


def _linha_do_mapa(
    mapa: MapaDaMesa, censo: Censo, ao_clicar: Any
) -> Any:
    """A linha-resumo mais o botão, numa fileira — o widget que a seção ganha."""
    from gi.repository import Gtk

    resumo = resumo_do_mapa(mapa, censo)
    fileira = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
    fileira.set_margin_top(6)
    texto = (
        _SEM_MAPA
        if resumo.vazio
        else _RESUMO_DO_MAPA.format(
            faces=resumo.faces,
            entradas=resumo.entradas,
            colocados=resumo.colocados,
        )
    )
    fileira.pack_start(
        rotulo_de_apoio(texto, largura_max=_LARGURA_DA_FRASE), False, False, 0
    )
    botao = Gtk.Button(label=_(_BOTAO_DESENHAR))
    botao.connect("clicked", ao_clicar)
    fileira.pack_start(botao, False, False, 0)
    return fileira


def _linhas_do_gabinete(gabinete: dict[str, Any]) -> tuple[str, ...]:
    """As contagens de entrada lado a lado, mais a pergunta — nunca uma escolha.

    **A CURA, e é a primeira mordida.** Com o censo desta bancada — BIOS a
    declarar 5 conectores USB e o barramento a contar 8 buracos — saem TRÊS
    frases: os dois números e a pergunta que o censo já traz pronta. Arrancada
    a regra (deixando o firmware vencer, ou o kernel vencer), a aba desenha um
    gabinete que ninguém tem e a pessoa procura na traseira buracos que o mapa
    não mostra. Mordida:
    ``test_a_aba_mostra_a_divergencia_em_vez_de_escolher``.

    Sem ``gabinete.json`` — primeira instalação, ou install de antes de 25/08 —
    a resposta é tupla vazia, e a seção fala exatamente como falava antes desta
    leva. Firmware é FONTE, nunca premissa.

    O desempacotamento do par ``{valor, de_onde_sei}`` NÃO acontece aqui: quem
    o faz é ``censo_do_gabinete.contagens_declaradas``, que é o dono do formato.
    Repetir a forma do JSON em código de tela seria a segunda verdade de sempre.
    """
    numeros = contagens_declaradas(gabinete)
    frases = {
        "firmware": _GABINETE_FIRMWARE,
        "kernel_buracos": _GABINETE_SISTEMA,
        "declarado_por_ela": _GABINETE_DELA,
    }
    linhas = [
        frases[fonte].format(numero=numero)
        for fonte, numero in numeros.items()
        if fonte in frases
    ]
    pergunta = pergunta_pendente(gabinete)
    if pergunta:
        linhas.append(pergunta)
    return tuple(linhas)


def _frase_do_hub_em_comum(
    mesa: Mesa, censo: Censo, entradas: Sequence[NoDeEntrada]
) -> tuple[str, str, str]:
    """`(fato, por quê, conselho)` do hub que está acima de TODOS os adaptadores.

    **A CURA, e é a segunda mordida.** A coluna "Onde está" escreve "Em hub"
    linha a linha e nunca compara as linhas entre si; quem compara é
    ``hub_em_comum``, e ela sobe a cadeia em vez de olhar o pai. Trocada por uma
    comparação de pai, os três adaptadores desta casa param de aparecer juntos —
    eles têm dois pais (``3-3.1`` e ``3-3``) e um só hub em comum.

    **O conselho é a metade opcional, e a contra-regra R3 é quem o segura.**
    Três adaptadores no mesmo hub é o arranjo que o próprio
    ``docs/usage/bluetooth-varios-adaptadores.md`` §3.4 sugere: o fato sozinho
    não é queixa. O
    conselho só nasce quando há para onde mandar — buraco livre, alcançável com
    a mão, numa controladora DIFERENTE. E nenhuma das três frases acusa um
    adaptador de atrapalhar outro; o que elas contam é que o caminho até o
    computador passa por um hub. Mordida:
    ``test_o_hub_em_comum_so_vira_conselho_com_buraco_livre_em_outra_pci``.

    Menos de dois adaptadores não tem "em comum" nenhum, e a resposta é o
    silêncio das três.
    """
    nos = [adaptador.no for adaptador in mesa.adaptadores if adaptador.no]
    if len(nos) < 2:
        return "", "", ""
    hub = hub_em_comum(censo, nos)
    if not hub:
        return "", "", ""
    fato = _HUB_EM_COMUM.format(numero=len(nos))
    quantos = len(_livres_em_outra_controladora(censo, entradas, hub))
    if quantos == 0:
        return fato, _HUB_POR_QUE, ""
    if quantos == 1:
        return fato, _HUB_POR_QUE, _HUB_CONSELHO_UMA
    return fato, _HUB_POR_QUE, _HUB_CONSELHO_VARIAS.format(numero=quantos)


def _livres_em_outra_controladora(
    censo: Censo, entradas: Sequence[NoDeEntrada], hub: str
) -> tuple[Furo, ...]:
    """Os buracos livres que NÃO pendem da mesma controladora deste hub."""
    aparelho = censo.aparelho(hub)
    controlador = aparelho.controlador_pci if aparelho is not None else ""
    if not controlador:
        return ()
    controlador_por_hub = {
        atual.nome_do_kernel: atual.controlador_pci for atual in censo.aparelhos
    }
    return tuple(
        furo
        for furo in livres(entradas)
        if controlador
        not in {controlador_por_hub.get(no.hub, "") for no in furo.entradas}
    )


def _onde_esta_o_adaptador(
    adaptador: Adaptador, mapa: MapaDaMesa | None = None
) -> tuple[str, str | None]:
    """`(texto, dica)` da coluna "Onde está".

    COM o mapa dela, a coluna diz o número que ela escreveu no gabinete —
    "Entrada 9" — e o caminho do sistema desce para a dica, que é onde a
    procedência mora nesta casa. SEM o mapa, o texto é exatamente o de hoje,
    sem uma vírgula de diferença: quem nunca desenhou a mesa não pode perder o
    pouco que a tela já sabia dizer.
    """
    if not adaptador.no:
        return "Dentro da máquina", None
    nome = _nome_da_entrada(adaptador.caminho, mapa)
    if nome is not None:
        numero = None if mapa is None else porta_de(mapa, adaptador.caminho)
        dica = (
            None
            if numero is None
            else _PROCEDENCIA_DA_ENTRADA.format(numero=numero, caminho=adaptador.caminho)
        )
        return nome, dica
    partes = [
        f"Barramento {adaptador.busnum}, porta {adaptador.devpath}",
        _painel_em_portugues(adaptador.painel),
    ]
    if not adaptador.atras_de_hub:
        return " · ".join(partes), None
    partes.append("Em hub")
    return " · ".join(partes), "Lido do barramento USB: o Hefesto reconhece o hub."


def _medidores_da_mesa(
    mesa: Mesa,
    ocupacoes: dict[str, Ocupacao],
    por_interface: dict[str, Dongle] | None = None,
) -> list[tuple[str, Ocupacao]]:
    """`[(nome do rádio, ocupação)]` — a lista de barras a desenhar."""
    if ocupacoes:
        return [(endereco, ocupacoes[endereco]) for endereco in sorted(ocupacoes)]
    nomes = por_interface or {}
    return [
        (
            (dongle.nome if (dongle := nomes.get(a.interface)) and dongle.nome else "")
            or _nome_do_adaptador(a),
            Ocupacao(),
        )
        for a in mesa.adaptadores
    ]


def _rotulo_do_medidor(nome: str, apelidos: dict[str, str] | None = None) -> str:
    """O rótulo da barra. Endereço ausente vira "Não sei", nunca `hciN`."""
    if nome == SEM_ADAPTADOR:
        return f"Rádio em uso · {_PAINEL_DESCONHECIDO}"
    apelido = (apelidos or {}).get(nome.upper(), "")
    return f"Rádio em uso · {apelido or nome}"


def _dongle_por_interface(dongles: Sequence[Dongle]) -> dict[str, Dongle]:
    """`hciN -> Dongle`, refeito a cada leitura e NUNCA guardado."""
    achados: dict[str, Dongle] = {}
    for dongle in dongles:
        interface = dongle.objeto.rsplit("/", 1)[-1]
        if interface.startswith("hci"):
            achados[interface] = dongle
    return achados


def _apelido_por_endereco(dongles: Sequence[Dongle]) -> dict[str, str]:
    """`ENDEREÇO -> nome dela`, só para quem tem nome. Maiúsculas dos dois lados."""
    return {d.endereco.upper(): d.nome for d in dongles if d.nome}


def _selo_da_ocupacao(ocupacao: Ocupacao, *, sabido: bool = True) -> str:
    """`831/1600 · derivado da especificação` — o selo mono, montado aqui."""
    if not sabido:
        return f"— · {_SEM_RESPOSTA_DO_DAEMON}"
    return (
        f"{round(ocupacao.slots_total)}/{ocupacao.slots_teto} "
        f"· {_SELO_DE_PROCEDENCIA}"
    )


def _texto_acessivel(ocupacao: Ocupacao, *, sabido: bool = True) -> str:
    """O que o leitor de tela lê na trilha — o `aria-label` do desenho."""
    if not sabido:
        return f"{_PAINEL_DESCONHECIDO} — {_SEM_RESPOSTA_DO_DAEMON}"
    return f"{round(ocupacao.slots_total)} de {ocupacao.slots_teto}"


def _onde_esta_o_radio(
    radio: RadioUsb,
    aviso: tuple[str, str] | None,
    mapa: MapaDaMesa | None = None,
) -> str:
    """O painel do rádio, mais o aviso de vizinhança quando há um."""
    onde = _nome_da_entrada(radio.caminho, mapa) or _painel_em_portugues(radio.painel)
    return onde if aviso is None else f"{onde} · {aviso[0]}"


def _nome_da_entrada(caminho: str, mapa: MapaDaMesa | None) -> str | None:
    """O nome da entrada em que este caminho está — pelo DONO do nome."""
    if mapa is None or not caminho:
        return None
    try:
        from hefesto_dualsense4unix.integrations.entrada_a_entrada import nome_da_porta

        documento = carregar_maquina().model_copy(update={"mapa": mapa})
        return nome_da_porta(caminho, maquina=documento, so_o_declarado=True)
    except Exception:
        logger.debug("secao_mesa_nome_da_entrada_ilegivel", caminho=caminho, exc_info=True)
        return None


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
