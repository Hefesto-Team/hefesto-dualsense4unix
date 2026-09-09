"""Subsystem: o canal de captura de CADA DualSense por Bluetooth (BT-MIC-01).

Embrulha `integrations/dualsense_bt_audio.py` no contrato `Subsystem` do
daemon (`start`/`stop`/`is_enabled`). É fino de propósito — toda a lógica de
protocolo, Opus e PipeWire mora no módulo de integração, que roda igual pelo
CLI (`mic bt`), pela GUI ou por aqui.

AS DUAS TRAVAS, LIDAS ANTES DE MEXER (CANAL-POR-CONTROLE-01, 03/09/2026)
------------------------------------------------------------------------
Decisão dela, com as palavras dela e sem corrigi-las:
*"4 controles os 4 tem que ter canais de entrada unico pra cada qual."*  (noqa-acento)

Medido com os dois controles na mesa: existia **UM** canal, o do cabo.
O do rádio não publicava fonte nenhuma, e quem recusava eram duas travas
NOSSAS. A §2 da sprint manda achar o que cada uma protegia antes de tocá-las,
e a leitura é esta:

=====================  =========================  =============================
trava                  de onde veio               o que protegia
=====================  =========================  =============================
`habilitado_por_env`   `d6f9d331`, 25/07/2026     privacidade + banda do rádio
`uniqs_declarados`     `c59dd346`, 23/08/2026,    a mesma razão, mais o *"por
                       QUATRO-MICROFONES-01/E1    controle"* que ela pediu. Não
                       (decisão dela: *"por       é precaução nossa: é o
                       controle"*)                INTERRUPTOR dela
=====================  =========================  =============================

**As duas são a MESMA razão em duas roupas**, e ela está escrita abaixo: a
ponte é um gesto explícito.

**A PERGUNTA QUE A §2 OBRIGA** — *"por que o cabo não precisa da mesma
proteção?"* — foi medida em 03/09/2026, com o controle do cabo na mesa::

    600  alsa_input...DualSense_Wireless_Controller-00.iec958-stereo  SUSPENDED

O canal do cabo **existe e está SUSPENDED**: publicado, e sem capturar nada
enquanto ninguém o abre. Ele não paga privacidade nem banda por existir.

**A ponte do rádio NÃO SABIA FAZER ISSO — e passou a saber em 06/09/2026**
(ONDA5-MIC-VIRTUAL-02). Aqui estava escrito, no presente, que
`PonteMicBluetooth.iniciar()` manda o `0x32` de LIGAR incondicionalmente e o
controle transmite áudio o tempo todo, ouvido ou não. Era verdade e deixou de
ser: o pedido agora SEGUE o estado da source — `RUNNING` (tem app gravando)
liga, qualquer outro desliga —, que é a mesma coisa que o cabo faz de graça.
Medido na máquina dela no mesmo dia: sem ouvinte `SUSPENDED`, com um `parec`
gravando `RUNNING`, e `IDLE` depois que ele sai (`integrations/
dualsense_bt_audio.ESTADO_COM_OUVINTE`).

**Logo a trava protegia a coisa certa pela alavanca errada** — ela negava o
CANAL para evitar a CAPTURA, e o cabo prova que os dois são separáveis. É
exatamente a distinção que a sprint faz: *"perder o padrão não é perder o
canal"*. **Hoje a distinção é do PRODUTO, e não só do argumento:** o canal do
rádio pode existir sem capturar, como o do cabo.

**Então a trava NÃO SAI: ela vira automática, e o critério explícito é o do
cabo — PROCURA.** A ponte sobe para o controle cujo canal alguém está tentando
usar, e o gesto que diz isso já existe e já é dela: o botão do microfone, que
desde 01/09 quer dizer *"eu falo por este controle"*
(`integrations/eleicao_de_microfone.py`). A exigência que MORRE é a de declarar
cada `uniq` à mão no `maquina.json` antes que ele possa ter canal.

**O que isso muda em quem chama:** `is_enabled` passa a ser sempre `True` — o
supervisor tem de estar de pé para atender o primeiro toque, e de pé ele não
captura nada: sem pedido e sem declaração, `alvos()` devolve `[]`, nenhuma
ponte sobe, nenhum `0x32` é escrito e a libopus nem é importada. O custo em
repouso é uma varredura de sysfs a cada `RECONCILIA_S`.

**Por que ele não sobe SOZINHO, e a razão continua de pé.** Ligar o mic
significa mandar o controle capturar áudio o tempo todo, e isso tem dois preços
que só a usuária pode aceitar:

1. **Privacidade.** Um microfone que liga sozinho quando o daemon sobe é
   inaceitável, por melhor que seja a intenção. A ponte é um gesto explícito.
2. **Banda do rádio.** Medido ao vivo (2026-07-25, DualSense por BT nesta
   máquina): com o mic desligado o controle entrega ~260 reports de input/s;
   com o mic ligado a MESMA banda passa a carregar ~106 quadros de áudio/s e
   os reports de input caem para ~170/s. O total de pacotes fica igual — o
   áudio não é de graça, ele divide o link. É por isso que a conta é POR
   ADAPTADOR, e é ela que diz quantos microfones cabem numa mesa.

   NOTA DATADA — 22/08/2026, decisão dela. Aqui estava escrito que *"quem usa
   gyro aiming perde resolução de integração (o espelho de motion mira
   250 Hz)"*. **Aquilo comparava réguas de transportes diferentes** e a
   remedição de 11/08/2026 o derrubou: 250 Hz é a taxa NATIVA DO CABO, e no
   rádio o físico nunca teve taxa — entrega em RAJADA, medida "entre ~55 e
   ~392 Hz" com o mic DESLIGADO, p95 de intervalo em 187 ms
   (`core/physical_report_reader.py`, "A taxa do rádio é RAJADA"). Um número
   que oscila 55 a 392 não perde resolução por passar a valer 170 de média: a
   premissa da frase não existia. Ela é a armadilha nº 1 desta casa — medir
   contra a régua errada produz alarme convincente e falso.

   O que fica: o microfone **não é trade-off contra giroscópio**. O alvo dela,
   textual em 22/08, é *"a mesma experiência do controle da Sony como se
   tivesse jogando no PS5"* — lá tudo funciona junto, e a conta de três
   adaptadores diz que aqui também cabe. O que continua verdadeiro é a conta
   do link, e ela é o que o orçamento da mesa mede.

POR CONTROLE, E POR QUE UM `bool` NÃO SERVE (QUATRO-MICROFONES-01, 22/08/2026)
------------------------------------------------------------------------------

Até 22/08 o gate era `DaemonConfig.bt_mic_enabled: bool` — **um** campo, lido
por três lugares e escrito por nenhum. A decisão dela é literal: *"por
controle"*, um interruptor por card, quatro independentes ao mesmo tempo.

**Um `bool` não sustenta quatro independentes** — ele só sabe dizer "todos" ou
"nenhum", e a mesa dela tem quatro DualSense em três adaptadores. Somar um `bool`
por controle no `DaemonConfig` também não serve: o `DaemonConfig` é config de
PROCESSO, e o número de controles muda por hotplug, no meio da sessão.

O que substituiu: **um CONJUNTO de `uniq` ligados**, e a ausência é o desligado.
Três razões, e a terceira é a que fecha a escolha:

* a chave é o `uniq` — endereço de hardware, doze hex — porque ele é o que
  sobrevive a hotplug, a renumeração de jogador e à troca do nó `hidrawN`. O
  número de jogador não sobrevive a nenhum dos três;
* **conjunto, e não `dict[uniq, bool]`**: um `false` gravado é um valor de
  catálogo para o silêncio, e é por essa porta que o default entra disfarçado de
  escolha dela (a regra é do `utils/maquina.py`). Ausente = desligado dá o
  "nasce desligado" de graça, em máquina nova e em controle novo;
* a fonte é **chamável**, nunca uma cópia: o `machine.declare` relê o
  `maquina.json` e REBINDA `daemon._maquina` no "Aplicar" (`ipc_handlers.py`),
  então uma cópia tirada no boot ficaria velha no instante exato em que ela
  acabou de escolher. É o mesmo desenho do `DaemonConfig.orcamento_da_mesa`.

QUEM GANHA PONTE, em três caminhos e nesta ordem (03/09/2026)
--------------------------------------------------------------
1. **PROCURA** — `PEDIDOS`, o registro deste módulo. É o caminho automático que
   substituiu a exigência de declarar à mão, e quem escreve nele é a eleição do
   microfone quando o canal daquele controle não está no ar. Um pedido vale
   enquanto o controle estiver na mesa: ao cair do rádio ele é esquecido, e uma
   reconexão não ressuscita microfone nenhum;
2. **declaração** — `DaemonConfig.bt_mic_uniqs` (fiada por `run()` a partir do
   `maquina.json`). Continua valendo inteira: quem já marcou um controle
   continua com a ponte de pé sem precisar tocar em botão nenhum;
3. **a env** `HEFESTO_DUALSENSE4UNIX_BT_MIC=1` — o caminho à mão, que vale para
   TODOS os controles. É o que ela sempre significou, e quem a exporta está
   pedindo a mesa inteira de propósito.

**E DESLIGAR CONTINUA DESLIGANDO.** Tirar a marca do card no "Aplicar" derruba
a ponte mesmo que houvesse um pedido aberto: o laço vê o `uniq` SAIR da
declaração e solta o pedido junto (`_soltar_os_que_ela_desmarcou`). Sem isso o
gesto mais explícito que ela tem — o interruptor — perderia para um toque de
botão feito minutos antes, que é o oposto de quem manda.

O laço de reconciliação vive num `threading.Thread` e DORME num `Event` entre
as varreduras — nunca um laço apertado, nunca um `sleep` de polling de dados.
O áudio em si não passa por aqui: cada ponte tem a própria thread bloqueada no
`read()` do hidraw (o áudio é o relógio).
"""
from __future__ import annotations

import asyncio
import contextlib
import os
import threading
from typing import TYPE_CHECKING, Any

from hefesto_dualsense4unix.core.sysfs_leds import norm_mac
from hefesto_dualsense4unix.utils.logging_config import get_logger

if TYPE_CHECKING:
    from hefesto_dualsense4unix.daemon.context import DaemonContext
    from hefesto_dualsense4unix.daemon.lifecycle import DaemonConfig
    from hefesto_dualsense4unix.utils.maquina import MaquinaConfig

logger = get_logger(__name__)

#: Opt-in explícito. Sem isto o subsystem nem importa a libopus.
ENV_HABILITA = "HEFESTO_DUALSENSE4UNIX_BT_MIC"

#: Cadência da varredura de hotplug (sysfs). Ver o cabeçalho: não é polling de
#: áudio, é só "apareceu/sumiu controle em BT?".
RECONCILIA_S = 5.0

_VALORES_LIGADOS = ("1", "true", "yes", "on")

#: Um endereço de rádio tem doze hex. Ver `RegistroDePedidosDeCanal.pedir`.
_UNIQ_HEX = 12


def habilitado_por_env(ambiente: dict[str, str] | None = None) -> bool:
    """True se a env de opt-in está ligada (função pura, testável)."""
    env = ambiente if ambiente is not None else os.environ
    return env.get(ENV_HABILITA, "").strip().lower() in _VALORES_LIGADOS


class RegistroDePedidosDeCanal:
    """Quem PEDIU o canal de captura do próprio controle — o critério automático.

    É o que ficou no lugar da declaração à mão (ver o cabeçalho). Ele guarda
    `uniq`, nunca nó nem caminho: o `uniq` é o que sobrevive a hotplug, a
    renumeração de jogador e à troca do `hidrawN`, e é a mesma chave que o
    `maquina.json` usa.

    **Um pedido não caduca no relógio, e isso é a sprint:** *"ninguém perde
    nada quando outro é eleito — perder o padrão não é perder o canal"*. Ele só
    morre quando o controle sai da mesa (`esquecer_ausentes`, chamado pelo laço
    com os `uniq` que o rádio ainda mostra) ou quando o subsystem para. Uma
    reconexão portanto **não** ressuscita microfone nenhum: quem voltar pede de
    novo, com o botão, se quiser.

    `novidade` é o `Event` que ACORDA o laço. Sem ele o pedido esperaria a
    varredura inteira, e os segundos entre o toque dela e o canal no ar
    apareceriam na tela como *"não pegou"* — que é a mentira que a eleição
    existe para não contar.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._abertos: set[str] = set()
        #: A PALAVRA DELA sobre o microfone de cada controle: `True` = no ar,
        #: `False` = calado, ausente = ela não disse nada e quem decide é o
        #: ouvinte da source. Ver `dizer_no_ar`.
        #:
        #: **ELA MORA AQUI E NÃO NA PONTE, e é medição:** a `PonteMicBluetooth`
        #: morre a cada reconexão de rádio — rotina, não exceção —, e um pedido
        #: guardado nela evaporaria no primeiro hotplug. O sintoma seria o
        #: mesmo que esta cura fecha, voltando por outra porta. O registro já é
        #: o dono do *"quem quer canal"* e sobrevive à ponte; guardar aqui não
        #: cria um segundo dono do mesmo estado.
        self._no_ar: dict[str, bool] = {}
        self.novidade = threading.Event()

    def pedir(self, uniq: str) -> bool:
        """Registra o pedido. False = `uniq` ilegível, e sem chave não há dono.

        A CHAVE TEM DE TER OS DOZE HEX, e não é preciosismo: `norm_mac` só filtra
        os dígitos hex e devolve o que sobrar, então uma palavra qualquer vira
        endereço — medido em 03/09/2026, ``"nao-e-um-mac"`` sai como ``"aeac"``.
        É a mesma armadilha que `escolher_fonte` documenta (*"Interactive" vira
        "eac"*), e aqui ela abriria um pedido fantasma que nenhum controle
        atende e que ninguém consegue soltar.
        """
        chave = norm_mac(str(uniq)) or ""
        if len(chave) != _UNIQ_HEX:
            return False
        with self._lock:
            novo = chave not in self._abertos
            self._abertos.add(chave)
        if novo:
            logger.info("bt_mic_canal_pedido", uniq=chave)
            self.novidade.set()
        return True

    def dizer_no_ar(self, uniq: str, ligado: bool) -> bool:
        """A PALAVRA DELA sobre este microfone. False = `uniq` ilegível.

        O ATO tem dois lados desde que ele existe — o canal no sistema e o bit
        do firmware —, e o do RÁDIO tinha um terceiro que ninguém dizia: o
        `0x32` que põe o microfone do controle no ar. Ele seguia só o ouvinte
        da source, e o gesto dela ELEGE o canal como fonte padrão, o que deixa
        a source ``SUSPENDED``. Medido no journal dela em 07/09/2026: quase
        três minutos de botão apertado com a ponte em `ligar=False`.

        **UMA PORTA SÓ, e é isso que faz a cura cobrir os DOIS chamadores.**
        Quem chama é `hotkey._metade_do_canal`, que é por onde passam o 🎙 da
        tela E a borda do botão do plástico — os dois entram por
        `ligar_o_microfone`. Costurar isto no `ipc_handlers` deixaria o
        plástico de fora com a suíte verde, e a regra dela é explícita: *"o
        botão fisico do mic se ligado no microfone ele fica ligado tambem.  # (noqa-acento) dela
        indepente se nativo ou virtual"*.

        A CHAVE TEM DE TER OS DOZE HEX, pela mesma razão que `pedir` documenta.

        **DIZER `False` NÃO SOLTA O CANAL**, e a distinção é dela: *"ninguém
        perde nada quando outro é eleito — perder o padrão não é perder o
        canal"*. Calar o microfone é uma coisa; derrubar a ponte é outra, e
        quem a derruba é o controle sair da mesa ou ela desmarcar o modo.
        """
        chave = norm_mac(str(uniq)) or ""
        if len(chave) != _UNIQ_HEX:
            return False
        with self._lock:
            mudou = self._no_ar.get(chave) is not ligado
            self._no_ar[chave] = ligado
        if mudou:
            logger.info("bt_mic_palavra_dela", uniq=chave, ligado=ligado)
            self.novidade.set()
        return True

    def esquecer_a_palavra(self, uniq: str) -> bool:
        """Ela deixa de ter dito qualquer coisa — a decisão volta ao ouvinte.

        Não é o mesmo que dizer `False`: `False` é *"me cale"* e vence um
        aplicativo gravando; esquecer é *"não tenho opinião"*, e aí o
        comportamento de 06/09/2026 volta inteiro. Quem chama é a perda da
        eleição — a luz do ex-dono apaga, e o microfone dele tem de sair do ar
        junto, senão o contrato *"aceso = este mic está no ar"* passa a mentir
        do outro lado.
        """
        chave = norm_mac(str(uniq)) or ""
        with self._lock:
            saiu = self._no_ar.pop(chave, None) is not None
        if saiu:
            logger.info("bt_mic_palavra_dela_esquecida", uniq=chave)
            self.novidade.set()
        return saiu

    def no_ar(self) -> dict[str, bool]:
        """O que ela disse, por `uniq`. Cópia: o chamador não escreve aqui."""
        with self._lock:
            return dict(self._no_ar)

    def soltar(self, uniq: str) -> bool:
        """Tira o pedido (o controle saiu da mesa, ou alguém desistiu)."""
        chave = norm_mac(str(uniq)) or ""
        with self._lock:
            saiu = chave in self._abertos
            self._abertos.discard(chave)
            # A PALAVRA DELA CAI JUNTO. Soltar é o controle saindo da mesa ou
            # ela desmarcando o modo — nos dois casos a ponte cai, e um pedido
            # sobrevivente ressuscitaria o microfone na volta sem ninguém ter
            # pedido nada.
            self._no_ar.pop(chave, None)
        if saiu:
            self.novidade.set()
        return saiu

    def abertos(self) -> frozenset[str]:
        with self._lock:
            return frozenset(self._abertos)

    def esquecer_ausentes(self, presentes: frozenset[str]) -> frozenset[str]:
        """Esquece o pedido de quem não está mais na mesa. Devolve os esquecidos."""
        with self._lock:
            sumidos = frozenset(self._abertos - presentes)
            self._abertos -= sumidos
            # A QUARTA PORTA do pedido dela: quem saiu do rádio perde a
            # palavra junto com o pedido de canal. Sem isto a reconexão traria
            # o microfone de volta ao ar sozinha.
            for uniq in list(self._no_ar):
                if uniq not in presentes:
                    del self._no_ar[uniq]
        if sumidos:
            logger.info("bt_mic_pedidos_esquecidos", uniqs=sorted(sumidos))
        return sumidos

    def limpar(self) -> None:
        with self._lock:
            self._abertos.clear()
            self._no_ar.clear()
        self.novidade.set()


#: O registro do processo. A eleição escreve nele pelo gancho que o subsystem
#: instala em `start()` — daemon importando `integrations`, nunca o contrário.
PEDIDOS = RegistroDePedidosDeCanal()


def uniqs_declarados(maquina: MaquinaConfig | None) -> frozenset[str]:
    """Os `uniq` que a declaração da mesa marcou com microfone LIGADO.

    Função pura sobre o `maquina.json` já carregado — é ela que `run()` fecha
    numa `lambda` para virar `DaemonConfig.bt_mic_uniqs`. Só `True` conta:
    ausência e `False` são a mesma coisa aqui (ver `ControleDeclarado`).

    A chave do `maquina.json` já é doze hex minúsculos por schema; normalizar de
    novo é barato e impede que uma escrita à mão com dois-pontos passe adiante
    numa forma que o resto do daemon não casa.
    """
    if maquina is None:
        return frozenset()
    controles = getattr(maquina, "controles", None)
    if not isinstance(controles, dict):
        return frozenset()
    ligados: set[str] = set()
    for chave, declarado in controles.items():
        if getattr(declarado, "microfone", None) is not True:
            continue
        normalizado = norm_mac(str(chave)) or ""
        if normalizado:
            ligados.add(normalizado)
    return frozenset(ligados)


def uniqs_pedidos(config: DaemonConfig | Any) -> frozenset[str]:
    """O conjunto pedido AGORA, lido da fonte chamável do `DaemonConfig`.

    Nunca levanta: uma fonte que exploda (dublê de teste, `MagicMock`) vale como
    "ninguém pediu", que é o lado seguro — o lado inseguro seria um microfone
    subindo por causa de um erro de leitura.
    """
    fonte = getattr(config, "bt_mic_uniqs", None)
    if not callable(fonte):
        return frozenset()
    try:
        pedidos = fonte()
    except Exception:  # best-effort: a fonte não derruba o boot do daemon
        logger.debug("bt_mic_fonte_falhou", exc_info=True)
        return frozenset()
    if not isinstance(pedidos, (set, frozenset, list, tuple)):
        return frozenset()
    return frozenset(norm_mac(str(u)) or "" for u in pedidos) - {""}


class BtMicSubsystem:
    """Mantém o canal de captura de cada DualSense cujo canal alguém procura."""

    name = "bt_mic"

    def __init__(
        self, *, gerenciador: Any = None, registro: RegistroDePedidosDeCanal | None = None
    ) -> None:
        self._gerenciador_injetado = gerenciador
        self._gerenciador: Any = None
        self._thread: threading.Thread | None = None
        self._parar = threading.Event()
        #: A config viva, guardada no `start` — o laço precisa reler a fonte a
        #: cada varredura para que o "Aplicar" valha sem reiniciar o daemon.
        self._config: Any = None
        #: O registro de procura. Injetável para que um teste não escreva no
        #: singleton do processo e contamine o próximo.
        self._registro = registro if registro is not None else PEDIDOS
        #: O que a declaração pedia na varredura anterior, para enxergar a
        #: BORDA de descida — ver `_soltar_os_que_ela_desmarcou`.
        self._declarados_antes: frozenset[str] = frozenset()
        self._pedidor_anterior: Any = None
        #: `(dizedor, esquecedor, leitor)` que estava instalado antes de nós.
        self._dizedor_anterior: tuple[Any, Any, Any] | None = None
        self._numerador_anterior: Any = None
        #: O backend do daemon (`DaemonContext.controller`). É por ele que este
        #: subsystem enxerga a MESA INTEIRA — o rádio e o CABO —, e não só os
        #: nós de Bluetooth que o gerenciador reconcilia. Ver `uniqs_na_mesa`.
        self._backend: Any = None
        #: `{uniq: nome do nó}` dos canais do CABO que ESTE supervisor ergueu.
        #: Só o que está aqui é fechado por ele: o canal do rádio é da ponte, e
        #: derrubar o do vizinho pelas costas do dono é o defeito que
        #: `PonteMicBluetooth._fechar_a_source` já nomeia do outro lado.
        self._canais_do_cabo: dict[str, str] = {}

    # -- contrato Subsystem ----------------------------------------------

    def is_enabled(self, config: DaemonConfig) -> bool:
        """Sempre. O supervisor tem de estar de pé para atender o primeiro toque.

        MUDOU EM 03/09/2026 (CANAL-POR-CONTROLE-01). Até aqui isto respondia
        *"alguém declarou um `uniq`?"*, e era essa resposta que trancava o
        rádio: sem declaração o subsystem nem existia, então não havia a quem
        pedir canal, e o primeiro toque no botão do microfone caía no vazio.

        **Ligado não quer dizer capturando.** Sem pedido, sem declaração e sem
        a env, `alvos()` devolve `[]`: nenhuma ponte sobe, nenhum `0x32` é
        escrito, a libopus não é importada e o custo em repouso é uma varredura
        de sysfs a cada `RECONCILIA_S`. A privacidade que as duas travas
        protegiam continua inteira — o que saiu foi a exigência de declarar
        cada controle à mão ANTES de poder pedir.

        `config` fica na assinatura porque o contrato `Subsystem` é esse, e
        porque `reconciliar_bt_mic` chama por aqui.
        """
        del config
        return True

    def alvos(self, nos: list[Any]) -> list[Any]:
        """Os nós de BT cujo canal alguém procura, declarou, ou a env pediu.

        A env é o caminho à mão e não filtra nada — quem a exporta está pedindo
        a mesa inteira (ver o cabeçalho). Sem env, um nó sem `HID_UNIQ` legível
        NUNCA entra: sem endereço não há como saber de quem é o microfone, e
        subir a ponte no escuro é o oposto do gesto explícito.
        """
        if habilitado_por_env():
            return list(nos)
        querem = uniqs_pedidos(self._config) | self._registro.abertos()
        if not querem:
            return []
        return [no for no in nos if (norm_mac(str(getattr(no, "uniq", ""))) or "") in querem]

    def pedir_canal(self, uniq: str) -> bool:
        """Alguém quer o canal de captura DESTE controle. Porta pública.

        É o gancho que a eleição do microfone chama quando o canal daquele
        controle não está no ar. Devolve `False` só quando o `uniq` é ilegível
        — sem endereço não há de quem seja o canal.
        """
        return self._registro.pedir(uniq)

    def no_ar(self, uniq: str, ligado: bool) -> bool:
        """A palavra DELA sobre este microfone. Porta pública, irmã de `pedir_canal`.

        É o gancho que `hotkey._metade_do_canal` chama — o mesmo ponto por onde
        passam o 🎙 da tela e a borda do botão do plástico. Ver
        `RegistroDePedidosDeCanal.dizer_no_ar` para o porquê.

        **PEDIR O CANAL VEM JUNTO quando ela liga**, e não é atalho: sem ponte
        de pé não há a quem entregar a palavra. Com a ponte já erguida o pedido
        é idempotente e não custa nada; sem ela, é o que a faz subir para
        receber o `0x32`. Desligar NÃO solta o canal — calar não é desconectar.
        """
        if ligado:
            self._registro.pedir(uniq)
        ok = self._registro.dizer_no_ar(uniq, ligado)
        if ok:
            self._aplicar_a_palavra_dela()
        return ok

    def esquecer_a_palavra(self, uniq: str) -> bool:
        """Ela deixa de ter dito qualquer coisa sobre este microfone.

        Quem chama é a perda da eleição, pelo mesmo gancho: o ex-dono do canal
        tem a luz apagada por `_apagar_a_luz_de_quem_perdeu_o_canal`, e o
        microfone dele tem de sair do ar no mesmo gesto. Sem isto o LED diria
        *"saí do ar"* com o `0x32` ainda ligado — a mesma mentira de segunda
        geração que aquele laço existe para matar, do lado de dentro.

        **E a SEXTA PORTA também entra por aqui** (08/09/2026): o ato que a
        eleição RECUSA devolve o registro ao que ele era, e quando ele não era
        nada isso é esquecer. Ver `hotkey._metade_do_canal`.
        """
        saiu = self._registro.esquecer_a_palavra(uniq)
        if saiu:
            self._aplicar_a_palavra_dela()
        return saiu

    def palavra_no_ar(self, uniq: str) -> bool | None:
        """O que ela disse sobre ESTE microfone. `None` = ela não disse nada.

        A terceira porta pública do trio, e ela é só leitura: quem desfaz um
        ato recusado precisa saber o que havia ANTES dele, senão o desfazer
        vira chute. Ver `RegistroDePedidosDeCanal.dizer_no_ar`.

        A chave é normalizada aqui pela mesma razão que em `dizer_no_ar`: quem
        chama entrega o `uniq` do gesto, que pode vir com dois-pontos.
        """
        chave = norm_mac(str(uniq)) or ""
        return self._registro.no_ar().get(chave)

    def _aplicar_a_palavra_dela(self) -> None:
        """Entrega a cada ponte viva o que ela disse — ou `None`, se não disse.

        **É CHAMADO A CADA VARREDURA, e é isso que sobrevive ao hotplug.** No
        rádio a reconexão é rotina: o gerenciador derruba a ponte e ergue
        outra, e a nova nasce sem saber de nada. Reaplicar aqui, depois do
        `reconciliar`, é o que impede o pedido dela de evaporar no primeiro
        hotplug — o mesmo sintoma que esta cura fecha, voltando por outra porta.

        Nunca levanta: uma ponte que não conheça a porta (dublê, versão velha)
        vale como *"não deu para dizer"*, e o caminho segue para as outras.
        """
        gerenciador = self._gerenciador
        if gerenciador is None:
            return
        try:
            pontes = gerenciador.pontes
        except Exception:  # best-effort: o relato nunca derruba o áudio
            logger.debug("bt_mic_pontes_ilegiveis", exc_info=True)
            return
        if not isinstance(pontes, dict):
            return
        palavras = self._registro.no_ar()
        for ponte in pontes.values():
            dizer = getattr(ponte, "dizer_o_pedido_dela", None)
            if not callable(dizer):
                continue
            uniq = norm_mac(str(getattr(getattr(ponte, "no", None), "uniq", ""))) or ""
            with contextlib.suppress(Exception):
                dizer(palavras.get(uniq))

    def uniqs_com_ponte(self) -> frozenset[str]:
        """Os `uniq` cuja ponte está DE PÉ agora — o que o rádio carrega.

        É esta a régua que o medidor de ocupação consome, e não o conjunto
        pedido: uma ponte que ela pediu e que não subiu (libopus ausente, hidraw
        recusado) não ocupa fatia de rádio nenhuma, e pintá-la na barra seria o
        produto respondendo pelo pedido em vez de pelo efeito.
        """
        gerenciador = self._gerenciador
        if gerenciador is None:
            return frozenset()
        try:
            pontes = gerenciador.pontes
        except Exception:  # best-effort: o relato nunca derruba o state_full
            logger.debug("bt_mic_pontes_ilegiveis", exc_info=True)
            return frozenset()
        if not isinstance(pontes, dict):
            return frozenset()
        vivos: set[str] = set()
        for ponte in pontes.values():
            uniq = norm_mac(str(getattr(getattr(ponte, "no", None), "uniq", ""))) or ""
            if uniq:
                vivos.add(uniq)
        return frozenset(vivos)

    # -- a mesa inteira: o rádio E o cabo ---------------------------------

    def _controles_da_mesa(self) -> list[dict[str, Any]]:
        """`describe_controllers()` do backend, ou `[]` quando ele não sabe.

        `getattr` porque nem todo backend é o de produção: os dublês da suíte e
        o backend de um controle só não conhecem a pergunta, e um backend que
        não conhece a pergunta não pode virar portão silencioso — é a mesma
        regra de `mic_da_mesa._bordas`.
        """
        descrever = getattr(self._backend, "describe_controllers", None)
        if not callable(descrever):
            return []
        try:
            itens = descrever()
        except Exception:  # pragma: no cover - defensivo
            logger.debug("bt_mic_mesa_ilegivel", exc_info=True)
            return []
        if not isinstance(itens, list):
            return []
        return [item for item in itens if isinstance(item, dict)]

    def uniqs_na_mesa(self) -> frozenset[str]:
        """Todo controle CONECTADO agora — o do rádio e o do CABO.

        **É ISTO QUE FALTAVA, e o defeito era de perda de dado dela.** Até
        09/09/2026 este subsystem só enxergava `nos_dualsense_bluetooth()`, e
        `_esquecer_quem_saiu_da_mesa` tratava *"não está no rádio"* como *"saiu
        da mesa"*. Medido nesta árvore, com o registro em mãos::

            sub.no_ar("aa:bb:cc:00:00:01", True)        # ela aperta o botão
              -> {'aabbcc000001': True}  pedidos: ['aabbcc000001']
            sub._esquecer_quem_saiu_da_mesa([<só o do rádio>])
              -> {}                     pedidos: []

        O controle do CABO está na mesa dela, com o microfone aceso, e a
        palavra dela sobre ele era apagada na varredura seguinte —
        imediatamente, porque `dizer_no_ar` toca a `novidade` e acorda o laço.
        """
        vivos: set[str] = set()
        for item in self._controles_da_mesa():
            if not item.get("connected"):
                continue
            chave = norm_mac(str(item.get("uniq") or "")) or ""
            if len(chave) == _UNIQ_HEX:
                vivos.add(chave)
        return frozenset(vivos)

    def numero_do_assento(self, uniq: str) -> int | None:
        """P1..P4 deste controle — a POSIÇÃO na mesa, `None` quando não dá.

        É o número que ela lê no card, e por isso a fonte é a MESMA lista que
        desenha os cards: `describe_controllers()`, cujo `index` é a posição em
        `list(self._handles)` (0 = primário) e que o `state_full` publica como
        `controllers` sem reordenar.

        **NÃO é `resolve_player_numbers`, e a diferença é medida:** aquele é o
        número que o JOGO vê, e com o co-op desligado ele responde `1` para
        todos os controles conectados (`coop.resolve_player_numbers`). Batizar
        os nós por ele poria quatro «Microfone do Controle 1» na lista dela —
        um rótulo repetido que mente sobre qual é qual.

        A decisão dela de 09/09 diz *"o número é o assento (P1..P4), como na
        tela"*, e aceita explicitamente que ele siga o ASSENTO e não o
        aparelho.
        """
        chave = norm_mac(str(uniq)) or ""
        if len(chave) != _UNIQ_HEX:
            return None
        for posicao, item in enumerate(self._controles_da_mesa(), start=1):
            if (norm_mac(str(item.get("uniq") or "")) or "") != chave:
                continue
            indice = item.get("index")
            if isinstance(indice, int) and not isinstance(indice, bool) and indice >= 0:
                return indice + 1
            return posicao
        return None

    async def start(self, ctx: DaemonContext) -> None:
        """Sobe a thread de reconciliação. Idempotente.

        Nada de bloquear o event loop: a criação do gerenciador é barata e a
        varredura do sysfs (mais o `pactl` do load-module) roda na thread.
        """
        self._config = getattr(ctx, "config", None)
        self._backend = getattr(ctx, "controller", None)
        if self._thread is not None and self._thread.is_alive():
            return
        from hefesto_dualsense4unix.integrations.dualsense_bt_audio import (
            GerenciadorMicBluetooth,
        )

        self._gerenciador = self._gerenciador_injetado or GerenciadorMicBluetooth()
        self._declarados_antes = uniqs_pedidos(self._config)
        self._instalar_o_gancho_da_procura()
        self._parar.clear()
        self._registro.novidade.clear()
        self._thread = threading.Thread(
            target=self._loop, name="hefesto-btmic-sup", daemon=True
        )
        self._thread.start()
        logger.info(
            "bt_mic_subsystem_iniciado",
            declarados=len(self._declarados_antes),
            pedidos=len(self._registro.abertos()),
        )

    def _instalar_o_gancho_da_procura(self) -> None:
        """Faz a eleição do microfone alcançar o registro de procura.

        O sentido do import é o que importa: **daemon importando
        `integrations`**, nunca o contrário. Por isso quem registra é este
        módulo, e a eleição só conhece um chamável que ela mesma guarda.

        Import tardio para que importar o subsystem não arraste o `pactl` nem o
        casamento USB, que é o mesmo motivo do import da ponte logo acima.
        """
        from hefesto_dualsense4unix.integrations.eleicao_de_microfone import (
            registrar_dizedor_do_no_ar,
            registrar_pedidor_de_canal,
        )

        self._pedidor_anterior = registrar_pedidor_de_canal(self.pedir_canal)
        # OS DOIS GANCHOS SOBEM JUNTOS, e é de propósito: o ato do microfone
        # pede o canal E diz se ele vai ao ar. Instalar só o primeiro é o
        # estado de antes de 08/09/2026 — o canal eleito, o `0x32` desligado.
        #
        # E SÃO TRÊS DESDE A SEXTA PORTA (08/09/2026, mesmo dia). O leitor sobe
        # junto porque desfazer um ato recusado sem saber o que havia antes só
        # pode ser chute; instalar dizedor sem leitor é o estado em que a
        # recusa deixava a palavra LIGADA.
        self._dizedor_anterior = registrar_dizedor_do_no_ar(
            self.no_ar, self.esquecer_a_palavra, self.palavra_no_ar
        )
        # E O QUARTO É O ASSENTO (09/09/2026). Quem SABE em que assento está o
        # controle é o daemon — o backend tem a lista que desenha os cards —, e
        # quem BATIZA o nó é a integração. O gancho é o que junta os dois sem
        # inverter a camada, exatamente como os três acima.
        from hefesto_dualsense4unix.integrations.dualsense_bt_audio import (
            registrar_numerador_de_assento,
        )

        self._numerador_anterior = registrar_numerador_de_assento(
            self.numero_do_assento
        )

    async def stop(self) -> None:
        """Derruba as pontes (o que DESLIGA o mic em cada controle). Idempotente.

        O `join` sai do event loop por `to_thread`: ele espera até 2 s por
        varredura em curso, e segurar o loop do daemon nesse tempo atrasaria o
        shutdown inteiro.
        """
        self._parar.set()
        # O mesmo `Event` que ACORDA o laço para um pedido novo acorda-o para a
        # parada: sem isto o `join` esperaria a varredura inteira, e o shutdown
        # do daemon carregaria `RECONCILIA_S` de atraso que não existia antes.
        self._registro.novidade.set()
        gerenciador = self._gerenciador
        if gerenciador is not None:
            with contextlib.suppress(Exception):
                gerenciador.parar()
        thread = self._thread
        self._thread = None
        if thread is not None:
            with contextlib.suppress(Exception):
                await asyncio.to_thread(thread.join, 2.0)
        self._gerenciador = None
        self._backend = None
        # OS CANAIS DO CABO MORREM COM A SESSÃO, e pela mesma razão que os
        # pedidos: cada um carrega um `module-pipe-source` no servidor de áudio
        # e um `parec` lendo o microfone dela. Deixá-los de pé com o daemon
        # fora seria um microfone ligado sem ninguém a quem pedir para desligar.
        for uniq in list(self._canais_do_cabo):
            self._fechar_o_canal_do_cabo(uniq)
        with contextlib.suppress(Exception):
            self._desinstalar_o_gancho_da_procura()
        # OS PEDIDOS MORREM COM A SESSÃO. Guardá-los faria o próximo boot subir
        # microfone sem ninguém ter pedido nada — que é exatamente o *"liga
        # sozinho quando o daemon sobe"* que o cabeçalho recusa.
        self._registro.limpar()
        self._declarados_antes = frozenset()
        logger.info("bt_mic_subsystem_parado")

    def _desinstalar_o_gancho_da_procura(self) -> None:
        """Devolve o pedidor anterior — o subsystem parado não atende ninguém."""
        from hefesto_dualsense4unix.integrations.dualsense_bt_audio import (
            registrar_numerador_de_assento,
        )
        from hefesto_dualsense4unix.integrations.eleicao_de_microfone import (
            registrar_dizedor_do_no_ar,
            registrar_pedidor_de_canal,
        )

        registrar_pedidor_de_canal(self._pedidor_anterior)
        self._pedidor_anterior = None
        dizedor, esquecedor, leitor = self._dizedor_anterior or (None, None, None)
        registrar_dizedor_do_no_ar(dizedor, esquecedor, leitor)
        self._dizedor_anterior = None
        registrar_numerador_de_assento(self._numerador_anterior)
        self._numerador_anterior = None

    # -- laço -------------------------------------------------------------

    def _loop(self) -> None:
        gerenciador = self._gerenciador
        if gerenciador is None:
            return
        from hefesto_dualsense4unix.integrations.dualsense_bt_audio import (
            nos_dualsense_bluetooth,
        )

        while not self._parar.is_set():
            try:
                nos = nos_dualsense_bluetooth()
                self._esquecer_quem_saiu_da_mesa(nos)
                self._soltar_os_que_ela_desmarcou()
                # ANTES do `reconciliar`, e a ordem é a cura de um estrago:
                # o canal do cabo e o do rádio são o MESMO nó do PipeWire
                # (`hefesto_mic_<hex6>`), e quem sobe um nó com nome que já
                # existe DERRUBA o de pé como órfão
                # (`SourceVirtualPipeWire.iniciar`). Soltar o do cabo antes de
                # a ponte nascer é o que faz a troca de fio para rádio passar
                # o nó de mão em mão em vez de os dois disputarem o nome.
                self._reconciliar_o_cabo(nos)
                # A LISTA vai explícita, e é aqui que o "por controle" acontece:
                # o gerenciador casa as pontes vivas com os nós que recebe, então
                # tirar um controle da lista DERRUBA a ponte dele e deixa as
                # outras de pé. Sem isto, ligar um microfone ligaria os quatro.
                gerenciador.reconciliar(self.alvos(nos))
                # DEPOIS do reconciliar, sempre: a ponte que acabou de nascer
                # (hotplug de rádio, que é rotina) não sabe o que ela pediu, e
                # sem esta linha o pedido dela evaporaria na primeira
                # reconexão. Ver `_aplicar_a_palavra_dela`.
                self._aplicar_a_palavra_dela()
            except Exception as exc:  # nunca derruba a thread
                logger.debug("bt_mic_reconciliacao_falhou", err=str(exc))
            if self._dormir(gerenciador):
                return

    def _dormir(self, gerenciador: Any) -> bool:
        """Dorme até a próxima varredura — ou até alguém PEDIR um canal.

        True quando é para parar. Duas fontes de parada, e as duas continuam
        valendo: o `stop()` daqui (`_parar`, que também toca a `novidade`) e o
        `gerenciador.parar()` chamado de fora, que o `dormir(0.0)` relê sem
        esperar nada.
        """
        if self._registro.novidade.wait(RECONCILIA_S):
            self._registro.novidade.clear()
        return self._parar.is_set() or gerenciador.dormir(0.0)

    def _esquecer_quem_saiu_da_mesa(self, nos: list[Any]) -> None:
        """Um pedido vale enquanto o controle está NA MESA, e não mais.

        Sem isto o pedido sobreviveria à queda do controle e a reconexão dele
        subiria a ponte sozinha — o *"liga sozinho"* pela porta dos fundos.

        **A MESA É O RÁDIO MAIS O CABO — e era só o rádio até 09/09/2026.**
        `nos` vem de `nos_dualsense_bluetooth()`, então um controle no fio
        nunca estava entre os presentes e a palavra dela sobre o microfone
        dele era apagada na varredura seguinte. Ver a medição em
        :meth:`uniqs_na_mesa`.

        A união é o que corrige, e não a troca: o rádio continua entrando
        inteiro porque um nó de BT pode existir sem que o backend tenha um
        handle aberto para ele (o `describe_controllers` responde por handle),
        e trocar uma leitura pela outra derrubaria a ponte de quem o backend
        ainda não enxerga.
        """
        do_radio = frozenset(
            (norm_mac(str(getattr(no, "uniq", ""))) or "") for no in nos
        ) - {""}
        self._registro.esquecer_ausentes(do_radio | self.uniqs_na_mesa())

    # -- o canal do CABO ---------------------------------------------------

    def _reconciliar_o_cabo(self, nos: list[Any]) -> None:
        """O canal com nome de controle para quem está no FIO.

        **POR QUE ELE PRECISA DE UM SUPERVISOR, e o rádio não.** No rádio a
        `PonteMicBluetooth` já chama `canal_do_microfone.abrir` ao subir
        (`_abrir_o_canal_por_controle`, 06/09/2026), então o controle do rádio
        ganha o `hefesto_mic_<hex6>` de graça. **No cabo não havia ninguém**:
        `grep -rn "canal_do_microfone" src/` devolvia UM chamador de `abrir`, e
        era a ponte. O nó ALSA do cabo continua existindo, mas ele tem o nome
        do TRANSPORTE — trocar o fio pelo rádio troca o microfone de nome, que
        é o defeito inteiro que o canal por controle existe para matar.

        **O GESTO CONTINUA SENDO DELA.** Só sobe canal para `uniq` que PEDIU, e
        o pedido vem de `no_ar(uniq, True)` — o 🎙 da tela e a borda do botão do
        plástico, pela porta única de `hotkey._metade_do_canal`. Sem toque, o
        conjunto é vazio e nada acontece: nenhum módulo carregado, nenhum
        `parec` lançado. É a mesma privacidade que o cabeçalho protege no
        rádio, pela mesma alavanca.

        **E ELE SÓ FECHA O QUE ELE ABRIU** (`_canais_do_cabo`). O canal do
        rádio é da ponte, e derrubá-lo daqui seria o mesmo erro que
        `PonteMicBluetooth._fechar_a_source` já recusa do outro lado.

        **QUEM ESTÁ NO RÁDIO NÃO É DAQUI, e a régua é o NÓ, não a ponte.** O
        alvo é o `uniq` que o sysfs mostra no rádio AGORA, mesmo que a ponte
        dele ainda não tenha subido: os dois transportes publicam o MESMO nó
        (`hefesto_mic_<hex6>`), e quem carrega um `module-pipe-source` com nome
        que já existe derruba o de pé como órfão. Ler a ponte em vez do nó
        deixaria uma janela em que os dois disputam o nome — a janela em que o
        microfone dela entrega zeros perfeitos (MIC-RADIO-ORFAO-01).
        """
        do_radio = frozenset(
            (norm_mac(str(getattr(no, "uniq", ""))) or "") for no in nos
        ) - {""}
        querem = self._registro.abertos() - do_radio
        for uniq in list(self._canais_do_cabo):
            if uniq not in querem:
                self._fechar_o_canal_do_cabo(uniq)
        faltam = sorted(u for u in querem if u not in self._canais_do_cabo)
        if faltam:
            self._abrir_os_canais_do_cabo(faltam)

    def _abrir_os_canais_do_cabo(self, uniqs: list[str]) -> None:
        """Ergue o canal de cada `uniq` da lista, alimentado pelo nó ALSA dele.

        **A FONTE É RESOLVIDA PELO DONO**, `fontes_de_captura.escolher_fonte`,
        e não por uma segunda régua escrita aqui: é a mesma função que a
        eleição, a luz, o áudio da janela e o `escolher_sink` chamam, e uma
        régua paralela sobre o mesmo estado é o defeito RECEITA-ERRADA-01.

        **E ela é perguntada ANTES de o canal subir**, por causa da regra 0
        daquela função: depois que `hefesto_mic_<hex6>` está no ar ela responde
        o próprio canal — a resposta certa para *"qual é o microfone dele"* e a
        errada para *"de onde eu leio"*. É o que a docstring de
        `canal_do_microfone.abrir` manda fazer.

        Um `uniq` sem nó ALSA atribuível não abre nada e não vira falta: no
        rádio quem ergue é a ponte, e no cabo sem casamento de USB o produto
        não sabe de quem é a placa — inventar aqui apontaria o microfone do
        controle errado.

        **E NUNCA SE SOBE UM NÓ QUE JÁ ESTÁ NO AR**, mesmo que a tabela do dono
        o guarde sob outra chave: a ponte de rádio abre o canal com o `uniq`
        do sysfs (``aa:bb:cc:…``, com dois-pontos) e este supervisor com a
        chave normalizada do registro (doze hex), então o dicionário do dono
        não é comparável entre os dois — mas o NOME DO NÓ é o mesmo nos dois,
        e é ele que o servidor de áudio usa para decidir quem é órfão. É a
        régua que impede o supervisor de derrubar o canal da ponte.
        """
        from hefesto_dualsense4unix.integrations import canal_do_microfone
        from hefesto_dualsense4unix.integrations.dualsense_bt_audio import (
            descricao_do_microfone,
        )
        from hefesto_dualsense4unix.integrations.eleicao_de_microfone import (
            casamento_usb_agora,
            fontes_de_captura_agora,
        )
        from hefesto_dualsense4unix.integrations.fontes_de_captura import (
            PREFIXO_SOURCE_CANAL_DO_MIC,
            escolher_fonte,
        )

        # A RECUSA DA REGRA 0 É NA ENTRADA, e não na saída: o canal por
        # controle sai da lista ANTES da pergunta. Perguntar com ele dentro e
        # descartar a resposta depois daria o mesmo veredicto só quando ele é a
        # única resposta — nos outros casos a regra 0 responde primeiro e as
        # regras do cabo nunca chegam a correr.
        do_cabo = [
            f for f in fontes_de_captura_agora()
            if not f.startswith(PREFIXO_SOURCE_CANAL_DO_MIC)
        ]
        if not do_cabo:
            return
        na_mesa = sorted(self.uniqs_na_mesa() | set(uniqs))
        usb = casamento_usb_agora(na_mesa)
        ja_no_ar = set(canal_do_microfone.de_pe().values())
        for uniq in uniqs:
            if canal_do_microfone.nome_do_canal(uniq) in ja_no_ar:
                logger.debug("bt_mic_canal_do_cabo_ja_tem_dono", uniq=uniq)
                continue
            fonte = escolher_fonte(do_cabo, uniq, na_mesa, usb)
            if not fonte:
                continue
            canal = canal_do_microfone.abrir(
                uniq, descricao_do_microfone(uniq), fonte=fonte
            )
            if canal is None:
                logger.warning("bt_mic_canal_do_cabo_nao_subiu", uniq=uniq)
                continue
            self._canais_do_cabo[uniq] = canal.nome
            logger.info("bt_mic_canal_do_cabo_no_ar", uniq=uniq, source=canal.nome)

    def _fechar_o_canal_do_cabo(self, uniq: str) -> None:
        """Derruba o canal deste `uniq` PELO DONO dele, e esquece a posse.

        `canal_do_microfone.fechar` mata o alimentador ANTES da source, que é a
        ordem que impede um `parec` vivo gravando o microfone dela sem nó para
        onde mandar. Chamar `source.parar()` daqui pularia essa ordem e ainda
        deixaria o dono anunciando de pé um canal que não existe mais.
        """
        self._canais_do_cabo.pop(uniq, None)
        try:
            from hefesto_dualsense4unix.integrations import canal_do_microfone

            canal_do_microfone.fechar(uniq)
        except Exception:  # pragma: no cover - defensivo
            logger.warning("bt_mic_canal_do_cabo_nao_fechou", uniq=uniq, exc_info=True)
            return
        logger.info("bt_mic_canal_do_cabo_fora", uniq=uniq)

    def _soltar_os_que_ela_desmarcou(self) -> None:
        """O interruptor do card vence o botão do controle, e por isso a BORDA.

        Ela desmarcar o microfone de um controle no "Aplicar" tem de derrubar a
        ponte dele mesmo que houvesse um pedido aberto de minutos antes. Ler só
        o estado ATUAL não bastaria: `alvos()` uniria os dois conjuntos e a
        procura manteria de pé o que ela acabou de desligar. O que decide é a
        borda de DESCIDA da declaração — quem estava declarado e não está mais.
        """
        agora = uniqs_pedidos(self._config)
        for uniq in self._declarados_antes - agora:
            self._registro.soltar(uniq)
        self._declarados_antes = agora


__all__ = [
    "ENV_HABILITA",
    "PEDIDOS",
    "RECONCILIA_S",
    "BtMicSubsystem",
    "RegistroDePedidosDeCanal",
    "habilitado_por_env",
    "uniqs_declarados",
    "uniqs_pedidos",
]
