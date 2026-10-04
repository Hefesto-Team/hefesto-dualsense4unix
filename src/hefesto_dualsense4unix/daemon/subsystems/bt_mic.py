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

**ELE SOBE SOZINHO DESDE 17/09/2026, E A RAZÃO DE NÃO SUBIR CADUCOU.** Aqui
estava escrito, no presente, *"por que ele não sobe SOZINHO, e a razão continua
de pé"* — privacidade e banda, as duas abaixo. **Ela revogou as duas em
25/08/2026, por escrito**, em `docs/data/decisoes-dela.csv`: a id 37
(D-AUDIO-E-GIRO-NASCEM-LIGADOS) e a id 38 (D-O-MIC-LIGADO-VALE-NO-RADIO), esta
com as palavras dela — *"LIGADO SEMPRE, NOS DOIS TRANSPORTES, COM A TELA DIZENDO
O PREÇO… o que caduca é o padrão desligado"*. A decisão nunca foi implementada,
e em 17/09/2026 ela pediu a mesma coisa pela TERCEIRA vez:

    *"segue por default mudo. eu preciso lembrar de clicar no icon do mic pra
    ativar e ele ser reconhecido. isso deveria ta  # (noqa-acento) dela
    ativado por padrao"*  # (noqa-acento) dela, 17/09/2026

**O QUE MUDOU, E O QUE NÃO MUDOU.** Quem diz a palavra na CHEGADA do controle é
`daemon/subsystems/hotkey.nascer_no_ar`, chamado pelo gancho de conexão
(`daemon/connection.nascer_o_microfone_ao_conectar`) — NASCE-LIGADO-MIC-01.
Nada aqui virou persistência: as portas de saída do latch continuam todas de
pé, quem sai da mesa perde o pedido e a palavra, e nada volta do disco. O que
mudou é que a chegada volta a dizer a palavra — e é por isso que ela não
clicava uma vez, clicava *toda vez*.

**E O SILÊNCIO DELA CONTINUA VENCENDO.** O nascimento recua diante das duas
formas de ela ter pedido para calar: o mudo daquele controle no `maquina.json`
(a `ProfileManager.o_controle_pede_silencio`, O-MUDO-E-DO-CONTROLE-01) e o bit
do mudo já aceso no aparelho.
Sem isso a SOM-MIC-REPLUG-01 — *"o silêncio que o produto promete e não
entrega"* — voltaria pela porta da frente.

**AS DUAS RAZÕES QUE ELA REVOGOU FICAM ESCRITAS**, porque a segunda continua
sendo a CONTA que diz quantos microfones cabem numa mesa, e porque apagá-las
deixaria a próxima pessoa sem saber que o padrão desligado já foi política:

1. **Privacidade.** Era: *"um microfone que liga sozinho quando o daemon sobe é
   inaceitável, por melhor que seja a intenção"*. Revogada por ela — e o que
   sobrou da preocupação é o recuo diante do silêncio pedido, acima.
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
* **eram DOIS conjuntos desde 18/09/2026**, e o segundo é o que a inversão
  pediu: `bt_mic_uniqs` (quem ela ligou) e `bt_mic_recusados` (quem ela
  desligou). Até aqui havia um só, e o comentário nesta linha dizia que um
  `false` gravado *"é um valor de catálogo para o silêncio, e é por essa porta
  que o default entra disfarçado de escolha dela"*. Isso valia com o default
  sendo o silêncio; com a ordem dela — *"todos os controles tem que nascer com
  tudo mic, giroscopio e afins"* — o `false` virou a ÚNICA forma de ela dizer
  não, e não gravá-lo é que deixaria o produto decidir por cima dela;
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
import shutil
import subprocess
import threading
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from hefesto_dualsense4unix.core.sysfs_leds import norm_mac
from hefesto_dualsense4unix.daemon.subsystems.base import numero_do_assento_na_mesa
from hefesto_dualsense4unix.utils.logging_config import get_logger

if TYPE_CHECKING:
    from hefesto_dualsense4unix.daemon.context import DaemonContext
    from hefesto_dualsense4unix.daemon.lifecycle import DaemonConfig
    from hefesto_dualsense4unix.utils.maquina import MaquinaConfig

logger = get_logger(__name__)

ENV_HABILITA = "HEFESTO_DUALSENSE4UNIX_BT_MIC"

RECONCILIA_S = 5.0

_VALORES_LIGADOS = ("1", "true", "yes", "on")

_UNIQ_HEX = 12


def habilitado_por_env(ambiente: dict[str, str] | None = None) -> bool:
    """True se a env de opt-in está ligada (função pura, testável)."""
    env = ambiente if ambiente is not None else os.environ
    return env.get(ENV_HABILITA, "").strip().lower() in _VALORES_LIGADOS


# carregado na máquina dela até o próximo boot. Ele se reconhece pelo

#: O nome do driver HID do DualSense no sysfs (`.../drivers/playstation`).
DRIVER_QUE_LE_O_DUALSENSE = "playstation"

RAIZ_DO_MODULO_DO_DRIVER = "/sys/module/hid_playstation"

PARAMETRO_DA_MARCA = "mic_frames_ignored"

SRCVERSION_DO_0003_SEM_A_MARCA: frozenset[str] = frozenset({"CFB81A3D4C7FAA41489CCBD"})

#: O que o `state_full` e o log dizem quando a guarda falta.
MOTIVO_SEM_A_GUARDA = "driver_sem_a_guarda_do_audio"


def o_driver_le_este_no(caminho: str, raiz_hidraw: str | None = None) -> bool:
    """O nó `/dev/hidrawN` está ligado ao driver `playstation`?"""
    if raiz_hidraw is None:
        from hefesto_dualsense4unix.integrations import dualsense_bt_audio

        raiz_hidraw = str(getattr(dualsense_bt_audio, "_SYSFS_HIDRAW", "/sys/class/hidraw"))
    nome = os.path.basename(str(caminho or ""))
    if not nome:
        return False
    try:
        driver = os.readlink(os.path.join(raiz_hidraw, nome, "device", "driver"))
    except OSError:
        return False
    return os.path.basename(driver) == DRIVER_QUE_LE_O_DUALSENSE


def o_driver_guarda_o_audio(raiz_do_modulo: str | None = None) -> bool:
    """O `hid-playstation` carregado descarta os quadros de áudio do microfone?"""
    raiz = raiz_do_modulo if raiz_do_modulo is not None else RAIZ_DO_MODULO_DO_DRIVER
    try:
        with open(os.path.join(raiz, "parameters", PARAMETRO_DA_MARCA), encoding="ascii") as fh:
            if fh.read().strip() in ("Y", "1"):
                return True
    except (OSError, UnicodeDecodeError):
        pass
    try:
        with open(os.path.join(raiz, "srcversion"), encoding="ascii") as fh:
            return fh.read().strip() in SRCVERSION_DO_0003_SEM_A_MARCA
    except (OSError, UnicodeDecodeError):
        return False


class RegistroDePedidosDeCanal:
    """Quem PEDIU o canal de captura do próprio controle — o critério automático."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._abertos: set[str] = set()
        self._no_ar: dict[str, bool] = {}
        self.novidade = threading.Event()

    def pedir(self, uniq: str) -> bool:
        """Registra o pedido. False = `uniq` ilegível, e sem chave não há dono."""
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
        """A PALAVRA DELA sobre este microfone. False = `uniq` ilegível."""
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
        """Ela deixa de ter dito qualquer coisa — a decisão volta ao ouvinte."""
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


PEDIDOS = RegistroDePedidosDeCanal()


def uniqs_declarados(maquina: MaquinaConfig | None) -> frozenset[str]:
    """Os `uniq` que a declaração da mesa marcou com microfone LIGADO."""
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


def uniqs_recusados(maquina: MaquinaConfig | None) -> frozenset[str]:
    """Os `uniq` que ela DESLIGOU — a única coisa que tira um microfone do ar.

    **A INVERSÃO — 18/09/2026, ordem dela:** *"todos os controles tem que
    nascer com tudo mic, giroscopio e afins"*. Até aqui o microfone era
    opt-in: um DualSense novo na mesa nascia sem canal, e a aba respondia *"o
    sistema não vê um microfone neste controle"* — uma recusa que a pessoa não
    tinha como resolver, porque o botão que a resolveria estava atrás de uma
    declaração que ninguém sabia existir. MEDIDO na mesa dela no mesmo dia:
    dos quatro DualSense ligados, DOIS tinham microfone; os outros dois nunca
    haviam sido declarados.

    **O QUE ISSO CUSTOU, e fica escrito porque era uma decisão fundamentada:**
    o cabeçalho deste módulo dizia *"um microfone que sobe sozinho com o
    daemon é inaceitável"*, e o `_start_alto_falante` do `lifecycle` explica o
    contraste — *"um alto-falante não escuta, e a privacidade não entra nesta
    conta"*. A ordem dela substitui esse default, e a contrapartida é o que
    NÃO existia antes: um jeito de dizer NÃO. Até hoje só havia "não pedi",
    que não é a mesma coisa que "não quero" — e era por isso que o `False` não
    chegava ao disco.

    `None` (ausente) = **nasce ligado**. `False` = ela desligou, e a ponte fica
    no chão. `True` = ligado, como sempre foi — quem já declarou não perde nada.
    """
    if maquina is None:
        return frozenset()
    controles = getattr(maquina, "controles", None)
    if not isinstance(controles, dict):
        return frozenset()
    desligados: set[str] = set()
    for chave, declarado in controles.items():
        if getattr(declarado, "microfone", None) is not False:
            continue
        normalizado = norm_mac(str(chave)) or ""
        if normalizado:
            desligados.add(normalizado)
    return frozenset(desligados)


def uniqs_negados(config: DaemonConfig | Any) -> frozenset[str]:
    """O conjunto RECUSADO agora, lido da fonte chamável do `DaemonConfig`."""
    fonte = getattr(config, "bt_mic_recusados", None)
    if not callable(fonte):
        return frozenset()
    try:
        negados = fonte()
    except Exception:
        logger.debug("bt_mic_fonte_de_recusa_falhou", exc_info=True)
        return frozenset()
    if not isinstance(negados, (set, frozenset, list, tuple)):
        return frozenset()
    return frozenset(norm_mac(str(u)) or "" for u in negados) - {""}


def uniqs_pedidos(config: DaemonConfig | Any) -> frozenset[str]:
    """O conjunto pedido AGORA, lido da fonte chamável do `DaemonConfig`."""
    fonte = getattr(config, "bt_mic_uniqs", None)
    if not callable(fonte):
        return frozenset()
    try:
        pedidos = fonte()
    except Exception:
        logger.debug("bt_mic_fonte_falhou", exc_info=True)
        return frozenset()
    if not isinstance(pedidos, (set, frozenset, list, tuple)):
        return frozenset()
    return frozenset(norm_mac(str(u)) or "" for u in pedidos) - {""}


# A queixa dela, de 16/09, com o DualSense no rádio: *"o canal de som não
# acessibilidade — quem usa o microfone do DualSense como único microfone (o


_NADA_DO_PIPEWIRE = ("auto_null", "@")

_SUFIXO_DE_MONITOR = ".monitor"

_TIMEOUT_DO_PACTL_S = 3.0

BURACO_NENHUM = "nenhum"
BURACO_MONITOR = "monitor"
BURACO_FANTASMA = "fantasma"
BURACO_VAZIO = "vazio"
BURACO_NAO_SEI = "nao_sei"
BURACO_CANAL_DE_CONTROLE = "canal_de_controle"


@dataclass(frozen=True)
class HerancaDoNoMorto:
    """O veredicto sobre a fonte padrão DEPOIS de um nó nosso morrer."""

    buraco: str
    eleito: str | None
    motivo: str

    @property
    def aberto(self) -> bool:
        """A porta abre? `nao_sei` NUNCA conta como buraco."""
        return self.buraco in (
            BURACO_MONITOR,
            BURACO_FANTASMA,
            BURACO_VAZIO,
            BURACO_CANAL_DE_CONTROLE,
        )


def a_heranca_do_no_morto(
    bruto: str | None, *, morreram: frozenset[str]
) -> HerancaDoNoMorto:
    """Classifica a fonte padrão de agora. Função PURA — não lê nada."""
    if bruto is None:
        return HerancaDoNoMorto(
            BURACO_NAO_SEI, None, "não deu para ler a fonte padrão — não mexo às cegas"
        )
    nome = bruto.strip()
    if not nome:
        return HerancaDoNoMorto(
            BURACO_VAZIO, None, "a máquina ficou sem fonte padrão depois de o nó morrer"
        )
    baixa = nome.lower()
    if baixa.startswith(_NADA_DO_PIPEWIRE):
        return HerancaDoNoMorto(
            BURACO_VAZIO, nome, f"{nome} não é microfone nenhum — é o nó de escassez"
        )
    if baixa.endswith(_SUFIXO_DE_MONITOR):
        return HerancaDoNoMorto(
            BURACO_MONITOR,
            nome,
            f"{nome} é um MONITOR: quem gravar pela fonte padrão capta o som "
            "que SAI, e o medidor mostra sinal",
        )
    if nome in morreram:
        return HerancaDoNoMorto(
            BURACO_FANTASMA, nome, f"{nome} morreu e a escolha gravada ainda o pede"
        )
    if _e_canal_de_controle(nome):
        return HerancaDoNoMorto(
            BURACO_CANAL_DE_CONTROLE,
            nome,
            f"{nome} é o canal de um controle — o padrão só fica nele se o "
            "dono estiver no ar",
        )
    return HerancaDoNoMorto(BURACO_NENHUM, nome, "")


def _e_canal_de_controle(nome: str) -> bool:
    """O nó é a fonte de captura de um DualSense — o nosso canal ou a do kernel?

    Pelos donos de `integrations/fontes_de_captura`: a identidade no nome (o
    `hefesto_mic_<marca>`) ou os marcadores do DualSense (a fonte do kernel no
    cabo). É a mesma leitura de `hotkey._a_escolha_gravada_e_de_outro_controle`.
    """
    from hefesto_dualsense4unix.integrations.fontes_de_captura import (
        MARCADORES_DUALSENSE,
        identidade_no_nome,
    )

    baixa = nome.lower()
    return bool(identidade_no_nome(nome)) or any(m in baixa for m in MARCADORES_DUALSENSE)


def fonte_padrao_crua(rodar: Any = None) -> str | None:
    """`pactl get-default-source` CRU — o nome, `""` ou `None`."""
    if rodar is not None:
        try:
            resposta = rodar()
        except Exception:
            logger.debug("bt_mic_fonte_padrao_dublada_falhou", exc_info=True)
            return None
        return resposta if resposta is None or isinstance(resposta, str) else None
    from hefesto_dualsense4unix.integrations import retrato_do_som

    do_retrato = retrato_do_som.responder(["pactl", "get-default-source"])
    if do_retrato is not None:
        return do_retrato.strip() if isinstance(do_retrato, str) else None
    exe = shutil.which("pactl")
    if exe is None:
        return None
    try:
        proc = subprocess.run(
            [exe, "get-default-source"],
            capture_output=True,
            text=True,
            timeout=_TIMEOUT_DO_PACTL_S,
            env={**os.environ, "LC_ALL": "C"},
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if proc.returncode != 0:
        return None
    return (proc.stdout or "").strip()


class BtMicSubsystem:
    """Mantém o canal de captura de cada DualSense cujo canal alguém procura."""

    name = "bt_mic"

    def __init__(
        self,
        *,
        gerenciador: Any = None,
        registro: RegistroDePedidosDeCanal | None = None,
        daemon: Any = None,
        varredor: Any = None,
    ) -> None:
        self._varredor_injetado = varredor
        self._varredor: Any = varredor
        self._daemon: Any = daemon
        self._gerenciador_injetado = gerenciador
        self._gerenciador: Any = None
        self._amostras_de_voz: dict[str, tuple[float, int, float | None]] = {}
        self._relogio_da_voz: Any = None
        self._thread: threading.Thread | None = None
        self._parar = threading.Event()
        self._config: Any = None
        self._registro = registro if registro is not None else PEDIDOS
        self._declarados_antes: frozenset[str] = frozenset()
        self._negados_antes: frozenset[str] = frozenset()
        self._pedidor_anterior: Any = None
        self._dizedor_anterior: tuple[Any, Any, Any] | None = None
        self._numerador_anterior: Any = None
        self._ouvinte_anterior: Any = None
        self._backend: Any = None
        self._canais_do_cabo: dict[str, str] = {}
        self._de_pe_antes: frozenset[str] = frozenset()
        self._motivo = ""
        self._laco: asyncio.AbstractEventLoop | None = None
        self._herancas_em_voo: set[asyncio.Task[None]] = set()

    @property
    def motivo(self) -> str:
        """O que do SISTEMA segura a ponte do rádio agora, ou `""`.

        É a resposta que o `state_full` publica como `bt_mic.motivo`: a recusa
        dela (o «Desligado» do card) não entra aqui, porque ela sabe o que
        pediu; entra o que ela não tem como ver da tela.
        """
        return self._motivo


    def is_enabled(self, config: DaemonConfig) -> bool:
        """Sempre. O supervisor tem de estar de pé para atender o primeiro toque."""
        del config
        return True

    def alvos(self, nos: list[Any]) -> list[Any]:
        """Os nós de BT que ganham ponte: TODOS, menos os que ela desligou.

        **A INVERSÃO DE 18/09/2026** (ver :func:`uniqs_recusados` para a ordem
        dela e o que ela substitui). Antes a lista era a UNIÃO de quem pediu
        com quem foi declarado, e um controle fora das duas ficava sem
        microfone para sempre. Agora a régua é a recusa: um DualSense TEM
        microfone, e isso é fato do aparelho, não escolha de configuração.

        **O PEDIDO E A DECLARAÇÃO SAÍRAM DA CONTA, e a razão é aritmética.** A
        primeira escrita desta função de 18/09 mantinha a união
        (`uniqs_pedidos | _registro.abertos()`) num segundo laço "para alcançar
        quem não está entre os `nos`" — e o laço iterava sobre os PRÓPRIOS
        `nos`, então todo nó legível e não-recusado já havia entrado no
        primeiro. Era código morto com um comentário que prometia o contrário,
        e isso é pior que o código morto sozinho: a próxima pessoa confiaria na
        promessa. `alvos()` só pode entregar o que está na lista que recebe.

        Quem trata do pedido continua sendo o `_soltar_os_que_ela_desmarcou`
        (a borda de subida da recusa solta o pedido) e o
        `_esquecer_quem_saiu_da_mesa`.

        Um nó sem `HID_UNIQ` legível continua NUNCA entrando: sem endereço não
        há como saber de quem é o microfone, nem como ela o desligaria depois.

        **E O DRIVER TEM A PRIMEIRA PALAVRA (28/09/2026).** Um nó que o
        `playstation` lê sem a guarda do áudio não entra, com ou sem a env e a
        recusa: ver `o_driver_guarda_o_audio` e `motivo`.
        """
        nos = self._os_que_o_driver_deixa(nos)
        if habilitado_por_env():
            return list(nos)
        negados = uniqs_negados(self._config)
        return [
            no
            for no in nos
            if (chave := norm_mac(str(getattr(no, "uniq", ""))) or "")
            and chave not in negados
        ]

    def _os_que_o_driver_deixa(self, nos: list[Any]) -> list[Any]:
        """Tira os nós cujo driver leria o áudio do microfone como gamepad."""
        lidos = [no for no in nos if o_driver_le_este_no(str(getattr(no, "caminho", "")))]
        if not lidos or o_driver_guarda_o_audio():
            if self._motivo:
                logger.info("bt_mic_driver_com_a_guarda")
            self._motivo = ""
            return list(nos)
        if self._motivo != MOTIVO_SEM_A_GUARDA:
            logger.warning(
                "bt_mic_driver_sem_a_guarda_do_audio",
                nos=[str(getattr(no, "caminho", "")) for no in lidos],
            )
        self._motivo = MOTIVO_SEM_A_GUARDA
        return [no for no in nos if no not in lidos]

    def pedir_canal(self, uniq: str) -> bool:
        """Alguém quer o canal de captura DESTE controle. Porta pública."""
        return self._registro.pedir(uniq)

    def no_ar(self, uniq: str, ligado: bool) -> bool:
        """A palavra DELA sobre este microfone. Porta pública, irmã de `pedir_canal`."""
        if ligado:
            self._registro.pedir(uniq)
        ok = self._registro.dizer_no_ar(uniq, ligado)
        if ok:
            self._aplicar_a_palavra_dela()
        return ok

    def esquecer_a_palavra(self, uniq: str) -> bool:
        """Ela deixa de ter dito qualquer coisa sobre este microfone.

        Quem chama é o microfone que saiu do ar DE FATO, pelo mesmo gancho: o
        canal dele sumiu ou o controle saiu da mesa
        (`hotkey._conferir_quem_saiu_do_ar`), e a luz dele apaga no mesmo gesto.
        Sem isto o LED diria *"saí do ar"* com o `0x32` ainda ligado — a mentira
        de segunda geração pelo lado de dentro.

        **PERDER O PADRÃO NÃO CHAMA MAIS — 13/09/2026 (OS-QUATRO-NO-AR-01).**
        Até aqui quem chamava era a perda da eleição, e ligar o microfone de um
        segundo controle tirava o primeiro do ar: medido em 10/09/2026 com dois
        DualSense no rádio, `bt_mic_palavra_dela_esquecida` e depois
        `bt_mic_pedido ligar=False` no hidraw do primeiro. Os quatro ficam no ar
        juntos; só a fonte padrão do sistema é de um.

        **E a SEXTA PORTA também entra por aqui** (08/09/2026): o ato que a
        eleição RECUSA devolve o registro ao que ele era, e quando ele não era
        nada isso é esquecer. Ver `hotkey._metade_do_canal`.
        """
        saiu = self._registro.esquecer_a_palavra(uniq)
        if saiu:
            self._aplicar_a_palavra_dela()
        return saiu

    def palavra_no_ar(self, uniq: str) -> bool | None:
        """O que ela disse sobre ESTE microfone. `None` = ela não disse nada."""
        chave = norm_mac(str(uniq)) or ""
        return self._registro.no_ar().get(chave)

    def _aplicar_a_palavra_dela(self) -> None:
        """Entrega a cada ponte viva o que ela disse — ou `None`, se não disse."""
        gerenciador = self._gerenciador
        if gerenciador is None:
            return
        try:
            pontes = gerenciador.pontes
        except Exception:
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

    def microfone_no_ar(self, uniq: str) -> bool:
        """O microfone deste controle está PEDIDO agora — 10/09/2026."""
        alvo = norm_mac(str(uniq or "")) or ""
        if not alvo:
            return False
        gerenciador = self._gerenciador
        if gerenciador is None:
            return False
        try:
            pontes = gerenciador.pontes
        except Exception:
            logger.debug("bt_mic_pontes_ilegiveis", exc_info=True)
            return False
        if not isinstance(pontes, dict):
            return False
        for ponte in pontes.values():
            no = getattr(ponte, "no", None)
            if (norm_mac(str(getattr(no, "uniq", ""))) or "") != alvo:
                continue
            return bool(getattr(ponte, "mic_no_ar", False))
        return False

    JANELA_DA_VOZ_S = 1.0
    JANELA_MAXIMA_DA_VOZ_S = 5.0

    def hz_de_voz(self, uniq: str) -> float | None:
        """Quadros de VOZ por segundo que o rádio traz deste controle AGORA."""
        chave = norm_mac(str(uniq)) or ""
        ponte = None
        gerenciador = self._gerenciador
        if chave and gerenciador is not None:
            with contextlib.suppress(Exception):
                for candidata in gerenciador.pontes.values():
                    dono = getattr(getattr(candidata, "no", None), "uniq", "")
                    if norm_mac(str(dono)) == chave:
                        ponte = candidata
                        break
        if ponte is None:
            self._amostras_de_voz.pop(chave, None)
            return None
        try:
            stats = ponte.estatistica()
            quadros = int(stats.quadros_audio) + int(stats.quadros_invalidos)
        except Exception:
            return None
        relogio = self._relogio_da_voz
        if relogio is None:
            import time

            relogio = time.monotonic
        agora = float(relogio())
        antes = self._amostras_de_voz.get(chave)
        if (
            antes is None
            or quadros < antes[1]
            or agora - antes[0] > self.JANELA_MAXIMA_DA_VOZ_S
        ):
            self._amostras_de_voz[chave] = (agora, quadros, None)
            return None
        if agora - antes[0] < self.JANELA_DA_VOZ_S:
            return antes[2]
        hz = round((quadros - antes[1]) / (agora - antes[0]), 1)
        self._amostras_de_voz[chave] = (agora, quadros, hz)
        return hz

    def uniqs_com_ponte(self) -> frozenset[str]:
        """Os `uniq` cuja ponte está DE PÉ agora — o que o rádio carrega."""
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


    def _controles_da_mesa(self) -> list[dict[str, Any]]:
        """`describe_controllers()` do backend, ou `[]` quando ele não sabe."""
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

    def _conectados_da_mesa(self) -> list[dict[str, Any]]:
        """Os itens CONECTADOS de `describe_controllers()`, na ordem da tela."""
        return [item for item in self._controles_da_mesa() if item.get("connected")]

    def uniqs_na_mesa(self) -> frozenset[str]:
        """Todo controle CONECTADO agora — o do rádio e o do CABO."""
        vivos: set[str] = set()
        for item in self._conectados_da_mesa():
            chave = norm_mac(str(item.get("uniq") or "")) or ""
            if len(chave) == _UNIQ_HEX:
                vivos.add(chave)
        return frozenset(vivos)

    def numero_do_assento(self, uniq: str) -> int | None:
        """O «Controle N» deste controle — o MESMO que a tela imprime no cartão.

        **NÃO CONTA NADA AQUI, e é isso que mudou em 12/09/2026**
        (TRES-CONTAS-PARA-UM-NUMERO-01). Quem responde é
        `subsystems/base.numero_do_assento_na_mesa`, que pergunta o
        `player_slot` ao dono dele — o `identity_registry` — e só então aplica a
        regra da casa. A conta própria que vivia aqui era a TERCEIRA de três
        para o mesmo rótulo, e era a que mentia na lista de som dela: «Microfone
        do Controle 2» no aparelho que o cartão chamava de P1, medido às 22h de
        09/09 com os quatro na mesa.

        A mesa continua sendo a dos CONECTADOS (`_conectados_da_mesa`), e a
        INVARIANTE continua: `numero_do_assento(u) is not None` se e somente se
        `u in uniqs_na_mesa()`. Um controle desligado não ganha nome nem quando
        o registro guarda um lugar na fila para ele.

        **CONTINUA NÃO SENDO `resolve_player_numbers`:** aquele é o número que o
        JOGO vê, e com o co-op desligado ele responde `1` para todos — quatro
        «Microfone do Controle 1» na lista dela.

        Sem daemon, sem registro fiado, ou controle que ainda não estreou na
        fila, a regra da casa cai no `index + 1` — o mesmo número que o cartão
        mostra nessa mesma situação. `None` é *"não sei"*, e o rótulo nasce sem
        número.
        """
        return numero_do_assento_na_mesa(
            self._conectados_da_mesa(), uniq, daemon=self._daemon
        )

    async def start(self, ctx: DaemonContext) -> None:
        """Sobe a thread de reconciliação. Idempotente."""
        self._config = getattr(ctx, "config", None)
        self._backend = getattr(ctx, "controller", None)
        self._laco = asyncio.get_running_loop()
        if self._thread is not None and self._thread.is_alive():
            return
        from hefesto_dualsense4unix.integrations.dualsense_bt_audio import (
            GerenciadorMicBluetooth,
        )

        self._gerenciador = self._gerenciador_injetado or GerenciadorMicBluetooth()
        if self._varredor_injetado is None and self._gerenciador_injetado is None:
            self._varredor = VarredorDeCanaisOrfaos()
        self._declarados_antes = uniqs_pedidos(self._config)
        self._negados_antes = uniqs_negados(self._config)
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
        """Faz a eleição do microfone alcançar o registro de procura."""
        from hefesto_dualsense4unix.integrations.eleicao_de_microfone import (
            registrar_dizedor_do_no_ar,
            registrar_pedidor_de_canal,
        )

        self._pedidor_anterior = registrar_pedidor_de_canal(self.pedir_canal)
        self._dizedor_anterior = registrar_dizedor_do_no_ar(
            self.no_ar, self.esquecer_a_palavra, self.palavra_no_ar
        )
        from hefesto_dualsense4unix.integrations.dualsense_bt_audio import (
            registrar_numerador_de_assento,
        )

        self._numerador_anterior = registrar_numerador_de_assento(
            self.numero_do_assento
        )
        from hefesto_dualsense4unix.integrations.dualsense_bt_audio import (
            registrar_ouvinte_do_microfone,
        )

        self._ouvinte_anterior = registrar_ouvinte_do_microfone(self.microfone_no_ar)

    async def stop(self) -> None:
        """Derruba as pontes (o que DESLIGA o mic em cada controle). Idempotente."""
        self._parar.set()
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
        self._laco = None
        self._varredor = self._varredor_injetado
        for uniq in list(self._canais_do_cabo):
            self._fechar_o_canal_do_cabo(uniq)
        with contextlib.suppress(Exception):
            self._desinstalar_o_gancho_da_procura()
        self._registro.limpar()
        self._declarados_antes = frozenset()
        self._negados_antes = frozenset()
        logger.info("bt_mic_subsystem_parado")

    def _desinstalar_o_gancho_da_procura(self) -> None:
        """Devolve o pedidor anterior — o subsystem parado não atende ninguém."""
        from hefesto_dualsense4unix.integrations.dualsense_bt_audio import (
            registrar_numerador_de_assento,
            registrar_ouvinte_do_microfone,
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
        registrar_ouvinte_do_microfone(self._ouvinte_anterior)
        self._ouvinte_anterior = None


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
                self._reconciliar_o_cabo(nos)
                gerenciador.reconciliar(self.alvos(nos))
                # reconexão. Ver `_aplicar_a_palavra_dela`.
                self._aplicar_a_palavra_dela()
                self._varrer_os_orfaos(nos)
                self._renomear_os_canais_velhos()
                self._devolver_a_fonte_padrao()
            except Exception as exc:
                logger.debug("bt_mic_reconciliacao_falhou", err=str(exc))
            if self._dormir(gerenciador):
                return

    def _dormir(self, gerenciador: Any) -> bool:
        """Dorme até a próxima varredura — ou até alguém PEDIR um canal."""
        if self._registro.novidade.wait(RECONCILIA_S):
            self._registro.novidade.clear()
        return self._parar.is_set() or gerenciador.dormir(0.0)

    def _esquecer_quem_saiu_da_mesa(self, nos: list[Any]) -> None:
        """Um pedido vale enquanto o controle está NA MESA, e não mais."""
        do_radio = frozenset(
            (norm_mac(str(getattr(no, "uniq", ""))) or "") for no in nos
        ) - {""}
        self._registro.esquecer_ausentes(do_radio | self.uniqs_na_mesa())


    def _reconciliar_o_cabo(self, nos: list[Any]) -> None:
        """O canal com nome de controle para TODO controle que está no FIO.

        A decisão dela de 02/10/2026 (OS-NOS-DE-SOM-SEM-O-ENDERECO-NO-NOME-01):
        um microfone por controle, sempre, nos dois transportes. O rádio já
        erguia a ponte de todo controle (``alvos``); o cabo só erguia o canal
        de quem o pedia pelo botão. Agora todo DualSense conectado pelo fio
        ganha o «Microfone do Controle N»; o pedido continua valendo para quem
        ainda não está na mesa, e a recusa dela continua tirando o canal.
        """
        do_radio = frozenset(
            (norm_mac(str(getattr(no, "uniq", ""))) or "") for no in nos
        ) - {""}
        querem = (
            (self._registro.abertos() | self.uniqs_na_mesa()) - do_radio
        ) - uniqs_negados(self._config)
        for uniq in list(self._canais_do_cabo):
            if uniq not in querem:
                self._fechar_o_canal_do_cabo(uniq)
        faltam = sorted(u for u in querem if u not in self._canais_do_cabo)
        if faltam:
            self._abrir_os_canais_do_cabo(faltam)

    def _abrir_os_canais_do_cabo(self, uniqs: list[str]) -> None:
        """Ergue o canal de cada `uniq` da lista, alimentado pelo nó ALSA dele."""
        from hefesto_dualsense4unix.integrations import canal_do_microfone
        from hefesto_dualsense4unix.integrations.dualsense_bt_audio import (
            descricao_do_microfone,
            pactl_mudo,
        )
        from hefesto_dualsense4unix.integrations.eleicao_de_microfone import (
            casamento_usb_agora,
            fontes_de_captura_agora,
        )

        if pactl_mudo():
            logger.debug("bt_mic_canal_do_cabo_espera_o_pactl", uniqs=uniqs)
            return
        from hefesto_dualsense4unix.integrations.fontes_de_captura import (
            PREFIXO_SOURCE_CANAL_DO_MIC,
            escolher_fonte,
        )

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
        """Derruba o canal deste `uniq` PELO DONO dele, e esquece a posse."""
        self._canais_do_cabo.pop(uniq, None)
        try:
            from hefesto_dualsense4unix.integrations import canal_do_microfone

            canal_do_microfone.fechar(uniq)
        except Exception:  # pragma: no cover - defensivo
            logger.warning("bt_mic_canal_do_cabo_nao_fechou", uniq=uniq, exc_info=True)
            return
        logger.info("bt_mic_canal_do_cabo_fora", uniq=uniq)

    def _soltar_os_que_ela_desmarcou(self) -> None:
        """O interruptor do card vence o botão do controle, e por isso a BORDA."""
        agora = uniqs_pedidos(self._config)
        negados = uniqs_negados(self._config)
        for uniq in negados - self._negados_antes:
            self._registro.soltar(uniq)
        self._declarados_antes = agora
        self._negados_antes = negados


    def _varrer_os_orfaos(self, nos: list[Any]) -> list[str]:
        """Entrega ao varredor quem QUER canal agora e o que está de pé aqui."""
        varredor = self._varredor
        if varredor is None:
            return []
        do_radio = frozenset((norm_mac(str(getattr(no, "uniq", ""))) or "") for no in nos)
        querem = (
            uniqs_pedidos(self._config)
            | self._registro.abertos()
            | (do_radio - {""})
        ) - uniqs_negados(self._config)
        return list(varredor.varrer(querem=querem, de_pe=self._nomes_de_pe()))


    def _renomear_os_canais_velhos(self) -> list[str]:
        """Os «Microfone do Controle N» passam a dizer o assento de AGORA."""
        from hefesto_dualsense4unix.integrations import canal_do_microfone
        from hefesto_dualsense4unix.integrations.dualsense_bt_audio import (
            descricao_do_microfone,
        )

        renomeados: list[str] = []
        das_pontes: set[str] = set()
        gerenciador = self._gerenciador
        try:
            pontes = gerenciador.pontes if gerenciador is not None else None
        except Exception:  # pragma: no cover - defensivo
            logger.debug("bt_mic_pontes_ilegiveis", exc_info=True)
            pontes = None
        if isinstance(pontes, dict):
            for ponte in pontes.values():
                renomear = getattr(ponte, "renomear_a_source", None)
                if not callable(renomear):
                    continue
                try:
                    mexeu = bool(renomear())
                except Exception:  # pragma: no cover - defensivo
                    logger.debug("bt_mic_ponte_nao_renomeou", exc_info=True)
                    continue
                proprio = (
                    norm_mac(str(getattr(ponte, "uniq_do_canal_proprio", "") or "")) or ""
                )
                if proprio:
                    das_pontes.add(proprio)
                if mexeu and proprio:
                    renomeados.append(proprio)
        for uniq in sorted(set(canal_do_microfone.de_pe()) - das_pontes):
            try:
                antes = canal_do_microfone.canal_de_pe(uniq)
                no_ar = getattr(antes, "descricao", "")  # (noqa-acento) atributo
                no_ar = str(no_ar or "")
                depois = canal_do_microfone.renomear(uniq, descricao_do_microfone(uniq))
            except Exception:  # pragma: no cover - defensivo
                logger.debug("bt_mic_canal_do_cabo_nao_renomeou", uniq=uniq, exc_info=True)
                continue
            if depois is None:
                logger.warning("bt_mic_canal_sumiu_ao_renomear", uniq=uniq)
                self._canais_do_cabo.pop(uniq, None)
                continue
            agora = getattr(depois, "descricao", "")  # (noqa-acento) atributo
            if str(agora or "") != no_ar:
                renomeados.append(uniq)
        return [u for u in renomeados if u]

    def _nomes_de_pe(self) -> frozenset[str]:
        """Os nós que ESTE processo segura agora — nunca são órfãos."""
        from hefesto_dualsense4unix.integrations import canal_do_microfone

        nomes = set(canal_do_microfone.de_pe().values()) | set(self._canais_do_cabo.values())
        gerenciador = self._gerenciador
        try:
            pontes = gerenciador.pontes if gerenciador is not None else None
        except Exception:
            logger.debug("bt_mic_pontes_ilegiveis", exc_info=True)
            pontes = None
        if isinstance(pontes, dict):
            for ponte in pontes.values():
                nome = getattr(ponte, "nome_source", None)
                if isinstance(nome, str) and nome:
                    nomes.add(nome)
        return frozenset(nomes)


    def _eleitor_da_sessao(self) -> Any:
        """O `EleitorDeMicrofone` DESTA sessão do daemon — ou `None`."""
        daemon = self._daemon
        if daemon is None:
            return None
        try:
            from hefesto_dualsense4unix.daemon.subsystems.hotkey import _eleitor

            return _eleitor(daemon)
        except Exception:
            logger.debug("bt_mic_eleitor_da_sessao_ilegivel", exc_info=True)
            return None

    def _devolver_a_fonte_padrao(
        self, *, ler: Any = None, eleitor: Any = None
    ) -> HerancaDoNoMorto | None:
        """Fecha o buraco que o nó MORTO deixa na fonte padrão do sistema.

        O gatilho é a MORTE, e não o relógio: compara os nomes que este
        processo segurava no fim da volta anterior com os de agora. Sem óbito
        não há pergunta, e o `pactl` não é chamado — um laço que interrogasse o
        servidor a cada cinco segundos pagaria o preço de um defeito que só
        existe no instante em que o nó cai.

        **A ESCOLHA NÃO É DAQUI.** Quem escolhe é o eleitor da sessão
        (`EleitorDeMicrofone.passar_o_padrao`), a mesma pergunta do botão do
        microfone: quem está no ar, depois a captura da máquina que não é
        controle nenhum (`outra_captura_elegivel`, que nunca devolve um
        `.monitor`), e sem as duas o padrão fica. Este método não digita nome de
        alvo nenhum — é o que impede um caminho nosso de terminar num monitor.

        **A PERGUNTA VAI AO LAÇO** (A-VOLTA-DO-MICROFONE-NAO-ELEGE-CONTROLE-01,
        29/09/2026). Este método roda no fio do `bt_mic`, e a ordem de quem está
        no ar é do `MicrofonesNoAr`, que só o laço do daemon toca e não tem
        lock. O fio classifica a herança (pura) e entrega o resto pela ponte
        fio→laço da casa (`call_soon_threadsafe`); até 29/09 ele chamava a
        volta à máquina direto e pulava quem estava no ar. E a porta abre
        também com o `canal_de_controle` (o herdeiro calado que o WirePlumber
        escolhe): antes ela só abria com monitor, fantasma ou vazio, e o canal
        de um calado herdava o padrão sem a pergunta ser feita.

        **E QUANDO NÃO HÁ PARA ONDE VOLTAR, a recusa vai para o diário.** Foi o
        caso medido nesta bancada: o único microfone dela é o do DualSense, e
        com o controle fora da mesa e ninguém mais no ar não sobra captura com
        porta usável que não seja controle. Aí nada é escrito, e o que fica no
        journal é o NOME do nó que herdou a eleição — porque uma denúncia sem o
        nome obriga a próxima pessoa a remedir o que já foi medido.

        Devolve o veredicto (`None` quando não houve óbito), para a régua.
        """
        de_pe = self._nomes_de_pe()
        antes = self._de_pe_antes
        self._de_pe_antes = de_pe
        morreram = antes - de_pe
        if not morreram:
            return None
        heranca = a_heranca_do_no_morto(fonte_padrao_crua(ler), morreram=morreram)
        if not heranca.aberto:
            logger.debug(
                "bt_mic_heranca_sem_buraco",
                buraco=heranca.buraco,
                eleito=heranca.eleito,
                morreram=sorted(morreram),
            )
            return heranca
        laco = self._laco
        if laco is None or laco.is_closed():
            logger.warning(
                "bt_mic_heranca_sem_laco",
                buraco=heranca.buraco,
                eleito=heranca.eleito,
                morreram=sorted(morreram),
                motivo=heranca.motivo,
            )
            return heranca
        try:
            laco.call_soon_threadsafe(self._agendar_a_heranca, heranca, morreram, eleitor)
        except RuntimeError as exc:
            logger.warning("bt_mic_heranca_nao_agendada", err=str(exc))
        return heranca

    def _agendar_a_heranca(
        self, heranca: HerancaDoNoMorto, morreram: frozenset[str], eleitor: Any
    ) -> None:
        """No LAÇO: põe a herança numa tarefa própria, guardada até terminar."""
        tarefa = asyncio.get_running_loop().create_task(
            self._herdar_no_laco(heranca, morreram, eleitor),
            name="bt_mic_heranca_do_no_morto",
        )
        self._herancas_em_voo.add(tarefa)
        tarefa.add_done_callback(self._herancas_em_voo.discard)

    async def _herdar_no_laco(
        self, heranca: HerancaDoNoMorto, morreram: frozenset[str], eleitor: Any
    ) -> None:
        """No LAÇO: pergunta ao dono para onde vai o padrão, e anota o desfecho."""
        daemon = self._daemon
        dono = eleitor if eleitor is not None else self._eleitor_da_sessao()
        if daemon is None or dono is None:
            logger.warning(
                "bt_mic_heranca_sem_eleitor",
                buraco=heranca.buraco,
                eleito=heranca.eleito,
                morreram=sorted(morreram),
                motivo=heranca.motivo,
            )
            return
        from hefesto_dualsense4unix.daemon.subsystems.hotkey import (
            passar_o_padrao_do_no_morto,
        )

        resultado: Any = None
        try:
            resultado = await passar_o_padrao_do_no_morto(
                daemon,
                dono,
                heranca.eleito,
                herdeiro_e_de_controle=heranca.buraco == BURACO_CANAL_DE_CONTROLE,
            )
        except Exception:
            logger.warning("bt_mic_heranca_devolucao_falhou", exc_info=True)
            resultado = False
        if resultado is None:
            logger.debug(
                "bt_mic_heranca_sem_buraco",
                buraco=heranca.buraco,
                eleito=heranca.eleito,
                morreram=sorted(morreram),
            )
            return
        logger.warning(
            "bt_mic_heranca_do_no_morto",
            buraco=heranca.buraco,
            eleito=heranca.eleito,
            morreram=sorted(morreram),
            motivo=heranca.motivo,
            curado=bool(getattr(resultado, "ok", False)),
            alvo=getattr(resultado, "alvo", None),
            recusa=getattr(resultado, "motivo", ""),
        )


class VarredorDeCanaisOrfaos:
    """Derruba o `module-pipe-source` desta casa que ficou no servidor sem dono."""

    def __init__(
        self,
        *,
        listar: Any = None,
        alguem_escreve: Any = None,
        descarregar: Any = None,
        mudo: Any = None,
    ) -> None:
        self._listar = listar
        self._alguem_escreve = alguem_escreve
        self._descarregar = descarregar
        self._mudo = mudo
        self._suspeitos: dict[str, str] = {}

    def varrer(self, *, querem: frozenset[str], de_pe: frozenset[str]) -> list[str]:
        """Uma varredura. Devolve os NOMES dos módulos derrubados agora."""
        from hefesto_dualsense4unix.integrations import dualsense_bt_audio as bt
        from hefesto_dualsense4unix.integrations.fontes_de_captura import (
            identidade_e_do_controle,
            identidade_no_nome,
        )

        mudo = self._mudo or bt.pactl_mudo
        if mudo():
            return []
        listar = self._listar or bt.modulos_de_captura_da_casa
        modulos = listar()
        if modulos is None:
            return []
        alguem_escreve = self._alguem_escreve or bt.alguem_escreve_no_fifo
        sem_dono: dict[str, str] = {}
        for modulo in modulos:
            nome = str(getattr(modulo, "nome", ""))
            module_id = str(getattr(modulo, "module_id", ""))
            if not nome or not module_id or nome in de_pe:
                continue
            identidade = identidade_no_nome(nome)
            if any(
                identidade_e_do_controle(identidade, uniq, forma_velha=False)
                for uniq in querem
            ):
                continue
            if alguem_escreve(str(getattr(modulo, "fifo", ""))) is not False:
                continue
            sem_dono[module_id] = nome
        descarregar = self._descarregar or bt.descarregar_modulo
        derrubados: list[str] = []
        for module_id, nome in sorted(sem_dono.items()):
            if self._suspeitos.get(module_id) != nome:
                logger.info("bt_mic_canal_orfao_suspeito", source=nome, module_id=module_id)
                continue
            if descarregar(module_id):
                logger.warning("bt_mic_canal_orfao_removido", source=nome, module_id=module_id)
                derrubados.append(module_id)
        self._suspeitos = {k: v for k, v in sem_dono.items() if k not in derrubados}
        return [sem_dono[k] for k in derrubados]


__all__ = [
    "BURACO_FANTASMA",
    "BURACO_MONITOR",
    "BURACO_NAO_SEI",
    "BURACO_NENHUM",
    "BURACO_VAZIO",
    "ENV_HABILITA",
    "PEDIDOS",
    "RECONCILIA_S",
    "BtMicSubsystem",
    "HerancaDoNoMorto",
    "RegistroDePedidosDeCanal",
    "VarredorDeCanaisOrfaos",
    "a_heranca_do_no_morto",
    "fonte_padrao_crua",
    "habilitado_por_env",
    "uniqs_declarados",
    "uniqs_negados",
    "uniqs_pedidos",
    "uniqs_recusados",
]
