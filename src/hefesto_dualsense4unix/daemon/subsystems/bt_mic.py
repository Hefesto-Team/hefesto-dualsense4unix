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
enquanto ninguém o abre. Ele não paga privacidade nem banda por existir. A
ponte do rádio **não sabe fazer isso**: `PonteMicBluetooth.iniciar()` manda o
`0x32` de LIGAR incondicionalmente, e daí o controle transmite áudio o tempo
todo, ouvido ou não.

**Logo a trava protegia a coisa certa pela alavanca errada** — ela negava o
CANAL para evitar a CAPTURA, e o cabo prova que os dois são separáveis. É
exatamente a distinção que a sprint faz: *"perder o padrão não é perder o
canal"*.

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

    def soltar(self, uniq: str) -> bool:
        """Tira o pedido (o controle saiu da mesa, ou alguém desistiu)."""
        chave = norm_mac(str(uniq)) or ""
        with self._lock:
            saiu = chave in self._abertos
            self._abertos.discard(chave)
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
        if sumidos:
            logger.info("bt_mic_pedidos_esquecidos", uniqs=sorted(sumidos))
        return sumidos

    def limpar(self) -> None:
        with self._lock:
            self._abertos.clear()
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

    async def start(self, ctx: DaemonContext) -> None:
        """Sobe a thread de reconciliação. Idempotente.

        Nada de bloquear o event loop: a criação do gerenciador é barata e a
        varredura do sysfs (mais o `pactl` do load-module) roda na thread.
        """
        self._config = getattr(ctx, "config", None)
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
            registrar_pedidor_de_canal,
        )

        self._pedidor_anterior = registrar_pedidor_de_canal(self.pedir_canal)

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
        from hefesto_dualsense4unix.integrations.eleicao_de_microfone import (
            registrar_pedidor_de_canal,
        )

        registrar_pedidor_de_canal(self._pedidor_anterior)
        self._pedidor_anterior = None

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
                # A LISTA vai explícita, e é aqui que o "por controle" acontece:
                # o gerenciador casa as pontes vivas com os nós que recebe, então
                # tirar um controle da lista DERRUBA a ponte dele e deixa as
                # outras de pé. Sem isto, ligar um microfone ligaria os quatro.
                gerenciador.reconciliar(self.alvos(nos))
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
        """Um pedido vale enquanto o controle está no rádio, e não mais.

        Sem isto o pedido sobreviveria à queda do controle e a reconexão dele
        subiria a ponte sozinha — o *"liga sozinho"* pela porta dos fundos.
        """
        presentes = frozenset(
            (norm_mac(str(getattr(no, "uniq", ""))) or "") for no in nos
        ) - {""}
        self._registro.esquecer_ausentes(presentes)

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
