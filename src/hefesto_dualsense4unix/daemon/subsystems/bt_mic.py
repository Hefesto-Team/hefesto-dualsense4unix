"""Subsystem opcional: microfone do DualSense por Bluetooth (BT-MIC-01).

Embrulha `integrations/dualsense_bt_audio.py` no contrato `Subsystem` do
daemon (`start`/`stop`/`is_enabled`). É fino de propósito — toda a lógica de
protocolo, Opus e PipeWire mora no módulo de integração, que roda igual pelo
CLI (`mic bt`), pela GUI ou por aqui.

**Por que ele nasce DESLIGADO.** Ligar o mic significa mandar o controle
capturar áudio o tempo todo, e isso tem dois preços que só a usuária pode
aceitar:

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

Gate: `DaemonConfig.bt_mic_uniqs` (a fonte acima, fiada por `run()` a partir do
`maquina.json`) OU `HEFESTO_DUALSENSE4UNIX_BT_MIC=1`. A env continua sendo o
caminho à mão e vale para TODOS os controles — é o que ela sempre significou, e
quem a exporta está pedindo a mesa inteira de propósito.

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


def habilitado_por_env(ambiente: dict[str, str] | None = None) -> bool:
    """True se a env de opt-in está ligada (função pura, testável)."""
    env = ambiente if ambiente is not None else os.environ
    return env.get(ENV_HABILITA, "").strip().lower() in _VALORES_LIGADOS


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
    """Mantém uma ponte de microfone por DualSense que ELA ligou."""

    name = "bt_mic"

    def __init__(self, *, gerenciador: Any = None) -> None:
        self._gerenciador_injetado = gerenciador
        self._gerenciador: Any = None
        self._thread: threading.Thread | None = None
        self._parar = threading.Event()
        #: A config viva, guardada no `start` — o laço precisa reler a fonte a
        #: cada varredura para que o "Aplicar" valha sem reiniciar o daemon.
        self._config: Any = None

    # -- contrato Subsystem ----------------------------------------------

    def is_enabled(self, config: DaemonConfig) -> bool:
        """Alguém pediu microfone? Um `uniq` na fonte basta; a env vale por todos."""
        return bool(uniqs_pedidos(config)) or habilitado_por_env()

    def alvos(self, nos: list[Any]) -> list[Any]:
        """Filtra os nós de BT pelos `uniq` que ela ligou.

        A env é o caminho à mão e não filtra nada — quem a exporta está pedindo
        a mesa inteira (ver o cabeçalho). Sem env, um nó sem `HID_UNIQ` legível
        NUNCA entra: sem endereço não há como saber de quem é o microfone, e
        subir a ponte no escuro é o oposto do gesto explícito.
        """
        if habilitado_por_env():
            return list(nos)
        ligados = uniqs_pedidos(self._config)
        if not ligados:
            return []
        return [no for no in nos if (norm_mac(str(getattr(no, "uniq", ""))) or "") in ligados]

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
        self._parar.clear()
        self._thread = threading.Thread(
            target=self._loop, name="hefesto-btmic-sup", daemon=True
        )
        self._thread.start()
        logger.info("bt_mic_subsystem_iniciado", pedidos=len(uniqs_pedidos(self._config)))

    async def stop(self) -> None:
        """Derruba as pontes (o que DESLIGA o mic em cada controle). Idempotente.

        O `join` sai do event loop por `to_thread`: ele espera até 2 s por
        varredura em curso, e segurar o loop do daemon nesse tempo atrasaria o
        shutdown inteiro.
        """
        self._parar.set()
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
        logger.info("bt_mic_subsystem_parado")

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
                # A LISTA vai explícita, e é aqui que o "por controle" acontece:
                # o gerenciador casa as pontes vivas com os nós que recebe, então
                # tirar um controle da lista DERRUBA a ponte dele e deixa as
                # outras de pé. Sem isto, ligar um microfone ligaria os quatro.
                gerenciador.reconciliar(self.alvos(nos_dualsense_bluetooth()))
            except Exception as exc:  # nunca derruba a thread
                logger.debug("bt_mic_reconciliacao_falhou", err=str(exc))
            if gerenciador.dormir(RECONCILIA_S):
                return


__all__ = [
    "ENV_HABILITA",
    "RECONCILIA_S",
    "BtMicSubsystem",
    "habilitado_por_env",
    "uniqs_declarados",
    "uniqs_pedidos",
]
