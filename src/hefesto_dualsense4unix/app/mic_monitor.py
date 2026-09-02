"""mic_monitor.py — nível e mute do microfone do DualSense na aba Status (S2).

O selo ATIVO/MUDO e o medidor de nível saem da MESMA fonte: a source de
captura que o PipeWire/PulseAudio publica para o controle. Um fato, um dono
— a alternativa (selo vindo do daemon, nível vindo daqui) já é a receita da
qual este projeto se arrependeu quando três lugares escreviam o perfil.

Três invariantes, cada uma paga com um incidente conhecido:

* **Nada de subprocess na thread GTK.** `pactl` e `parec` só rodam na thread
  supervisora e nas threads de captura. A interface lê um dicionário.
* **Nada de busy-loop.** A captura fica BLOQUEADA num `read()` do pipe do
  `parec` (o áudio é o relógio) e a supervisora dorme num `Event.wait`. Um
  laço apertado aqui repetiria os 104% de CPU da v3.8.1.
* **Ausência é resposta.** Sem `pactl`, sem `parec` ou sem source atribuível
  ao controle — o caso do RÁDIO, que não publica placa de som nenhuma —, a
  leitura é `None` e o painel some. Nunca um medidor parado em zero fingindo
  silêncio.

Por que `LC_ALL=C` em tudo: a saída do `pactl` é TRADUZIDA (nesta máquina o
mute sai como "Mudo: não"). Parsear texto localizado é bug esperando idioma.

Uma carona declarada (SENSOR-VIVO-01/E5 e SOM-02/E5, item 4): além das sources
de captura, este módulo lê o MUDO DO SINK de saída do controle — a "camada 1"
do alto-falante, a única que decide se sai som. Não é assunto de microfone, e
mora aqui por dois motivos medidos: este já é o leitor de PipeWire da janela,
com cadência própria e fora da thread do GTK, e o card já sabe consumir o valor
desta posição (``LeituraMic.saida_muda``) sem precisar de alteração nenhuma. A
alternativa — o daemon publicar ``speaker.saida_muda`` — custaria pôr o daemon
a falar com o PipeWire para dizer o que a janela já tem à mão.

E uma disciplina copiada do `scripts/doctor.sh`, que já detecta a mesma
condição: o alto-falante do controle mudo é um FATO sobre a saída, e a usuária
pode tê-lo escolhido. **O selo informa e nunca conserta** — nada aqui escreve
no PipeWire nem no estado do WirePlumber.
"""
from __future__ import annotations

import array
import contextlib
import math
import os
import shutil
import subprocess
import sys
import threading
from dataclasses import dataclass, replace
from typing import Any, ClassVar

from hefesto_dualsense4unix.app.usb_pai import (
    nos_e_sysfs,
    usb_pai_por_no,
    usb_pai_por_uniq,
)
from hefesto_dualsense4unix.integrations.fontes_de_captura import (  # noqa: F401
    MARCADORES_DUALSENSE as _MARCADORES_DUALSENSE,
)
from hefesto_dualsense4unix.integrations.fontes_de_captura import (  # noqa: F401
    MIN_HEX_SUFIXO_BT as _MIN_HEX_SUFIXO_BT,
)
from hefesto_dualsense4unix.integrations.fontes_de_captura import (  # noqa: F401
    PREFIXO_SOURCE_PONTE_BT as _PREFIXO_SOURCE_PONTE_BT,
)
from hefesto_dualsense4unix.integrations.fontes_de_captura import (
    CasamentoUSB,
    escolher_fonte,
    escolher_sink,
    fontes_dualsense,
    sinks_dualsense,
    sufixo_da_ponte_bt,
)
from hefesto_dualsense4unix.integrations.fontes_de_captura import (  # noqa: F401
    so_hex as _so_hex,
)
from hefesto_dualsense4unix.utils.logging_config import get_logger

logger = get_logger(__name__)

#: Formato da captura. 16 kHz mono s16le é mais que suficiente para um
#: medidor de nível (não é gravação) e mantém o bloco pequeno: 100 ms = 3200
#: bytes, um `read()` a cada 100 ms por controle.
_TAXA_HZ = 16000
_BYTES_POR_AMOSTRA = 2
_BLOCO_MS = 100
_BLOCO_BYTES = int(_TAXA_HZ * _BYTES_POR_AMOSTRA * _BLOCO_MS / 1000)

#: Piso da escala em dBFS. Abaixo disso o medidor mostra vazio — 60 dB de
#: faixa é o que um medidor de voz precisa mostrar sem virar ruído visual.
_PISO_DBFS = -60.0

_TIMEOUT_SUBPROCESS_S = 2.0


@dataclass(frozen=True)
class LeituraMic:
    """O que o card mostra: o mic (nível e mute) e o mudo da SAÍDA do controle.

    ``nivel`` é 0.0-1.0 já em escala de dB (ver `nivel_para_fracao`), pronto
    para virar altura de barra. ``None`` ali NÃO é o mesmo que ``0.0``: quer
    dizer que não há captura nenhuma, e o card apaga o medidor em vez de
    desenhar uma barra parada no zero fingindo silêncio. ``muted`` None = a
    source existe mas o estado de mute ainda não foi lido — o selo espera em
    vez de chutar "ATIVO".

    ``saida_muda`` é a CAMADA 1 do alto-falante (o sink do PipeWire) e não diz
    nada sobre o microfone; viaja junto porque este é o leitor de PipeWire da
    janela e porque o card já lê o valor desta posição
    (``controller_card.saida_muda_do_entry``). ``None`` = não deu para saber, o
    que é diferente de "não está muda" — só ``True`` acende o selo.

    ``sink`` é o NOME desse mesmo sink de saída, e viaja pela mesma carona e
    pelo mesmo motivo (SOM-04): o som de confirmação e o botão de rota
    (``app/audio_saida.py``) precisam mandar o áudio para o sink DO CONTROLE,
    explicitamente, e quem resolve "qual sink é de qual controle" já é este
    módulo. Publicar o nome aqui é o que evita um SEGUNDO leitor de PipeWire na
    janela. ``""`` = não deu para casar com certeza — o caso do controle no
    RÁDIO, que não publica placa de som —, e quem recebe "" não toca e não
    roteia, em vez de chutar.
    """

    nivel: float | None = 0.0
    muted: bool | None = None
    fonte: str = ""
    saida_muda: bool | None = None
    sink: str = ""


# ---------------------------------------------------------------------------
# A resolução `uniq -> nó de áudio` MUDOU DE CAMADA (MIC-DA-MESA-ELEICAO-01)
# ---------------------------------------------------------------------------
#
# `CasamentoUSB`, `fontes_dualsense`, `sinks_dualsense`, `escolher_fonte`,
# `escolher_sink` e `sufixo_da_ponte_bt` desceram para
# `integrations/fontes_de_captura.py`. O motivo é o mesmo do `app/usb_pai.py`
# (MIC-DA-MESA-CHEIA-01, 20/08): o DAEMON passou a precisar da mesma resposta —
# a ELEIÇÃO DE MICROFONE resolve `uniq -> fonte` — e o daemon **não importa
# nada de `app/`**. Duplicar criaria duas verdades sobre a mesma pergunta.
#
# Este arquivo continua a reexportar tudo (ver os imports do topo): quem já
# importava daqui não muda uma linha.

def muted_de_saida(saida: str) -> bool | None:
    """Lê ``Mute: yes|no`` do `pactl get-source-mute`/`get-sink-mute`; None se ilegível.

    Os dois comandos respondem com a MESMA linha, então o parser é um só.

    Só funciona com `LC_ALL=C` (ver o cabeçalho do módulo). Saída inesperada
    vira None — o selo prefere esperar a mentir.
    """
    texto = saida.strip().lower()
    if texto.endswith("yes"):
        return True
    if texto.endswith("no"):
        return False
    return None


def rms_de_pcm_s16le(bloco: bytes) -> float:
    """RMS normalizado (0.0-1.0) de um bloco PCM 16 bits little-endian.

    Bloco vazio/ímpar → 0.0: um `read()` truncado no encerramento do `parec`
    não pode virar pico no medidor.
    """
    if len(bloco) < 2:
        return 0.0
    amostras = array.array("h")
    amostras.frombytes(bloco[: len(bloco) - (len(bloco) % 2)])
    if not amostras:
        return 0.0
    if sys.byteorder == "big":
        # `parec` entrega s16LE; em máquina big-endian o `array` leria os
        # bytes trocados e o medidor viraria ruído.
        amostras.byteswap()
    soma = sum(float(a) * float(a) for a in amostras)
    return math.sqrt(soma / len(amostras)) / 32768.0


def nivel_para_fracao(rms: float) -> float:
    """RMS linear → 0.0-1.0 em escala de dB (o que o olho lê como "volume").

    Escala linear é inútil num medidor de voz: fala normal fica com 3% de
    barra e só um grito enche. Mapeia `_PISO_DBFS`..0 dBFS em 0..1.
    """
    if rms <= 0.0:
        return 0.0
    dbfs = 20.0 * math.log10(min(1.0, rms))
    if dbfs <= _PISO_DBFS:
        return 0.0
    return min(1.0, (dbfs - _PISO_DBFS) / (-_PISO_DBFS))


# ---------------------------------------------------------------------------
# Monitor (threads)
# ---------------------------------------------------------------------------


class MicMonitor:
    """Captura o nível do mic dos controles enquanto a aba Status está visível.

    Uso (a mixin de status é a dona)::

        monitor.set_ativo(True)              # entrou na aba Status
        monitor.set_controles(("aabb...",))  # tick de 10 Hz, barato
        leitura = monitor.leitura("aabb...") # None = sem mic atribuível
        monitor.set_ativo(False)             # saiu da aba: mata tudo

    ``set_ativo(False)`` não é otimização: sem ele, um `parec` por controle
    ficaria capturando o microfone da usuária a sessão inteira com a janela
    minimizada.
    """

    #: Intervalo da supervisora. Descobrir sources é subprocess; 3 s é rápido
    #: o bastante para plugar um controle e ver o medidor aparecer.
    _SUPERVISAO_S: ClassVar[float] = 3.0
    #: Frequência de releitura do mute. O nível é contínuo; o mute muda por
    #: gesto humano — 1 Hz é imperceptível e evita um subprocess por bloco.
    _MUTE_S: ClassVar[float] = 1.0

    def __init__(
        self,
        *,
        runner: Any = None,
        capturador: Any = None,
        auto_supervisao: bool = True,
    ) -> None:
        """`runner` e `capturador` são injetáveis para teste (sem áudio real).

        `auto_supervisao=False` deixa a thread supervisora de fora e o teste
        chama `reconciliar()` na mão — do contrário a thread rodaria a mesma
        reconciliação em paralelo e o teste viraria uma corrida.
        """
        self._runner = runner or _rodar
        self._capturador = capturador or _abrir_captura
        self._auto_supervisao = auto_supervisao
        self._lock = threading.RLock()
        self._ativo = False
        self._controles: tuple[str, ...] = ()
        self._leituras: dict[str, LeituraMic] = {}
        #: Camada 1 do alto-falante por controle. Só entra aqui o que foi LIDO
        #: e casado com certeza; ausência = "não sei", nunca "não está mudo".
        self._saidas_mudas: dict[str, bool] = {}
        #: NOME do sink de saída por controle (SOM-04). Mesma regra: só entra o
        #: que casou com certeza. Este mapa é o que evita um segundo leitor de
        #: PipeWire na janela — ele existe mesmo quando o mudo do sink não deu
        #: para ler, porque roteirizar e tocar dependem do NOME, não do mudo.
        self._sinks: dict[str, str] = {}
        self._capturas: dict[str, _Captura] = {}
        self._acordar = threading.Event()
        self._parar = threading.Event()
        self._supervisora: threading.Thread | None = None

    # -- API da thread GTK (tudo barato: só dict/tuple sob lock) ----------

    def set_ativo(self, ativo: bool) -> None:
        """Liga/desliga a captura. Chamado pelo gancho de troca de aba."""
        with self._lock:
            if ativo == self._ativo:
                return
            self._ativo = ativo
        if ativo:
            self._garantir_supervisora()
        self._acordar.set()

    def set_controles(self, uniqs: tuple[str, ...]) -> None:
        """Identidades dos controles que PODEM ter mic (chamado a 10 Hz)."""
        with self._lock:
            if uniqs == self._controles:
                return
            self._controles = uniqs
        self._acordar.set()

    def leitura(self, uniq: str) -> LeituraMic | None:
        """Leitura deste controle; None = nada a dizer sobre mic NEM sobre saída.

        Duas fontes independentes se encontram aqui: a captura do microfone
        (thread de `parec`) e o mudo do sink de saída (thread supervisora).
        Uma pode existir sem a outra, e é por isso que a saída muda NÃO viaja
        dentro da leitura publicada pela captura: por Bluetooth sem a ponte de
        mic, ou sem `parec` na máquina, não há captura nenhuma — e o
        alto-falante continua mudo do mesmo jeito.

        Sem captura, o carona vira uma leitura própria com ``nivel=None``, que
        o card desenha EXATAMENTE como desenha a ausência de microfone (o
        bloco fica, o medidor some). E ela só nasce com ``saida_muda is True``:
        materializar um objeto para dizer "a saída não está muda" seria
        inventar presença de sensor para não dizer nada.
        """
        with self._lock:
            base = self._leituras.get(uniq)
            saida_muda = self._saidas_mudas.get(uniq)
            sink = self._sinks.get(uniq, "")
        if base is not None:
            if base.saida_muda is saida_muda and base.sink == sink:
                return base
            return replace(base, saida_muda=saida_muda, sink=sink)
        if saida_muda is True:
            return LeituraMic(
                nivel=None, muted=None, fonte="", saida_muda=True, sink=sink
            )
        # SOM-04, decisão registrada: o NOME do sink **não** materializa a
        # leitura. Ele é um fato sobre a SAÍDA e não sobre o microfone, e a
        # regra desta função — não materializar um objeto para dizer nada sobre
        # o mic — é de outra sprint e está travada em teste. Quem precisa do
        # nome sem depender do microfone usa :meth:`sink_de`, que devolve o
        # mesmo mapa sem fingir sensor nenhum.
        return None

    def sink_de(self, uniq: str) -> str:
        """Nome do sink de SAÍDA deste controle; ``""`` = não dá para saber.

        A porta que o som de confirmação e o botão de rota (SOM-04) usam, e a
        razão de ela existir separada de :meth:`leitura`: o sink é um fato da
        SAÍDA e sobrevive à ausência de microfone (sem `parec` na máquina, ou
        por Bluetooth sem a ponte de mic, não há captura nenhuma e o
        alto-falante continua lá).

        ``""`` sai em dois casos que valem a mesma recusa: o sistema não
        publicou sink nenhum para este controle — o caso do RÁDIO, em que o
        DualSense não expõe placa de som (medido 15/08/2026: a placa segue o
        transporte) —, ou o casamento por dispositivo USB não fechou. Quem
        recebe "" não toca e não roteia.

        Desde 15/08/2026 "mais de um DualSense no cabo" NÃO é mais um desses
        casos: o ``escolher_sink`` casa cada placa com o seu controle pelo nó
        USB em que os dois penduram, e devolve o sink certo para cada um.
        """
        with self._lock:
            return self._sinks.get(uniq, "")

    def stop(self) -> None:
        """Encerra tudo. Idempotente (fechamento da janela)."""
        self._parar.set()
        self._acordar.set()
        thread = self._supervisora
        self._supervisora = None
        if thread is not None:
            thread.join(timeout=2.0)
        self._derrubar_capturas(set())

    # -- Supervisora ------------------------------------------------------

    def _garantir_supervisora(self) -> None:
        if self._parar.is_set() or not self._auto_supervisao:
            return
        with self._lock:
            atual = self._supervisora
            if atual is not None and atual.is_alive():
                return
            self._supervisora = threading.Thread(
                target=self._loop_supervisao, name="hefesto-mic-monitor", daemon=True
            )
            self._supervisora.start()

    def _loop_supervisao(self) -> None:
        while not self._parar.is_set():
            try:
                self.reconciliar()
            except Exception as exc:  # nunca derruba a thread
                logger.debug("mic_monitor_reconciliacao_falhou", err=str(exc))
            self._acordar.wait(self._SUPERVISAO_S)
            self._acordar.clear()

    def reconciliar(self) -> None:
        """Casa as capturas vivas com aba visível, controles, sources e sinks.

        Público para o teste exercitar o ciclo sem depender de temporização.
        """
        with self._lock:
            ativo = self._ativo
            controles = self._controles
        if not ativo or not controles:
            self._derrubar_capturas(set())
            with self._lock:
                self._leituras = {}
                self._saidas_mudas = {}
                self._sinks = {}
            return

        fontes = self._descobrir_fontes()
        # Uma varredura de sysfs por ciclo, sem subprocesso: o dispositivo USB
        # pai de cada controle serve aos DOIS lados (mic e saída) e não muda
        # dentro do ciclo.
        usb_por_uniq = usb_pai_por_uniq(controles)
        casamento = self._casar_por_usb("sources", fontes, usb_por_uniq)
        alvos: dict[str, str] = {}
        for uniq in controles:
            fonte = escolher_fonte(fontes, uniq, list(controles), casamento)
            if fonte is not None:
                alvos[uniq] = fonte
        self._derrubar_capturas(set(alvos))
        with self._lock:
            self._leituras = {
                u: leitura for u, leitura in self._leituras.items() if u in alvos
            }
        for uniq, fonte in alvos.items():
            self._garantir_captura(uniq, fonte)
        # Depois das capturas de propósito: o medidor não espera dois
        # subprocessos a mais para aparecer, e o mudo da saída muda por gesto
        # humano — 3 s de atraso ali é invisível.
        saidas, nomes = self._descobrir_saidas(controles, usb_por_uniq)
        with self._lock:
            self._saidas_mudas = saidas
            self._sinks = nomes

    def _descobrir_fontes(self) -> list[str]:
        saida = self._runner(["pactl", "list", "sources", "short"])
        return fontes_dualsense(saida or "")

    def _casar_por_usb(
        self, tipo: str, nomes: list[str], usb_por_uniq: dict[str, str]
    ) -> CasamentoUSB | None:
        """Monta o casamento por dispositivo USB deste lado (sources ou sinks).

        Um `pactl list <tipo>` LONGO por lado e por ciclo — o curto não traz o
        ``sysfs.path``, que é o fio inteiro desta cura. É subprocesso, então
        ele só sai quando há nó de DualSense na lista: sem candidato não há
        casamento a fazer, e o ciclo fica exatamente tão caro quanto era.

        ``None`` quando não deu para montar (sem `pactl`, sem candidato, saída
        ilegível). Quem recebe ``None`` volta ao comportamento anterior à cura,
        que é conservador e não inventa dado — degradar não pode virar chute.
        """
        if not nomes:
            return None
        longa = self._runner(["pactl", "list", tipo]) or ""
        if not longa.strip():
            return None
        return CasamentoUSB(
            por_uniq=dict(usb_por_uniq),
            por_no=usb_pai_por_no(nos_e_sysfs(longa)),
        )

    def _descobrir_saidas(
        self, controles: tuple[str, ...], usb_por_uniq: dict[str, str] | None = None
    ) -> tuple[dict[str, bool], dict[str, str]]:
        """Sink de saída de cada controle que dá para casar COM CERTEZA.

        Devolve DOIS mapas do mesmo casamento: o mudo (a camada 1, para o selo)
        e o NOME (SOM-04, para tocar e rotear). Eles são separados porque não
        empatam: o nome pode ser conhecido e o mudo, ilegível — e quem toca o
        som de confirmação precisa do nome mesmo quando o `get-sink-mute` não
        respondeu. Empacotar os dois num só faria a confirmação sonora depender
        de uma leitura que ela não usa.

        Os mapas são SUBSTITUÍDOS inteiros a cada ciclo e nunca ganham entrada
        por chute: controle sem sink atribuível (o do RÁDIO, que não publica
        placa) ou sem `pactl` na máquina fica DE FORA — e ficar de fora é
        exatamente o que mantém o selo apagado e o botão de rota parado.

        Nenhuma escrita: `list sinks short` e `get-sink-mute` são leituras. O
        mudo persistido é escolha da usuária (ver o cabeçalho do módulo).
        """
        saida = self._runner(["pactl", "list", "sinks", "short"])
        sinks = sinks_dualsense(saida or "")
        if not sinks:
            return {}, {}
        if usb_por_uniq is None:
            usb_por_uniq = usb_pai_por_uniq(controles)
        casamento = self._casar_por_usb("sinks", sinks, usb_por_uniq)
        mudos: dict[str, bool] = {}
        nomes: dict[str, str] = {}
        for uniq in controles:
            sink = escolher_sink(sinks, uniq, list(controles), casamento)
            if sink is None:
                continue
            nomes[uniq] = sink
            muda = muted_de_saida(self._runner(["pactl", "get-sink-mute", sink]) or "")
            if muda is not None:
                mudos[uniq] = muda
        return mudos, nomes

    def _derrubar_capturas(self, manter: set[str]) -> None:
        with self._lock:
            mortas = [u for u in self._capturas if u not in manter]
            capturas = [self._capturas.pop(u) for u in mortas]
        for captura in capturas:
            captura.parar()

    def _garantir_captura(self, uniq: str, fonte: str) -> None:
        with self._lock:
            atual = self._capturas.get(uniq)
            if atual is not None and atual.fonte == fonte and atual.viva():
                return
            if atual is not None:
                self._capturas.pop(uniq, None)
        if atual is not None:
            atual.parar()
        captura = _Captura(
            uniq=uniq,
            fonte=fonte,
            publicar=self._publicar,
            runner=self._runner,
            capturador=self._capturador,
            parar_global=self._parar,
            mute_intervalo_s=self._MUTE_S,
        )
        with self._lock:
            self._capturas[uniq] = captura
        captura.iniciar()

    def _publicar(self, uniq: str, leitura: LeituraMic) -> None:
        with self._lock:
            self._leituras[uniq] = leitura


class _Captura:
    """Uma captura `parec` + a releitura periódica do mute, numa thread só."""

    def __init__(
        self,
        *,
        uniq: str,
        fonte: str,
        publicar: Any,
        runner: Any,
        capturador: Any,
        parar_global: threading.Event,
        mute_intervalo_s: float,
    ) -> None:
        self.uniq = uniq
        self.fonte = fonte
        self._publicar = publicar
        self._runner = runner
        self._capturador = capturador
        self._parar_global = parar_global
        self._mute_intervalo_s = mute_intervalo_s
        self._parar = threading.Event()
        self._thread: threading.Thread | None = None
        self._proc: Any = None

    def viva(self) -> bool:
        thread = self._thread
        return thread is not None and thread.is_alive()

    def iniciar(self) -> None:
        if self.viva():
            return
        self._thread = threading.Thread(
            target=self._loop, name=f"hefesto-mic-{self.uniq[:8]}", daemon=True
        )
        self._thread.start()

    def parar(self) -> None:
        self._parar.set()
        proc = self._proc
        if proc is not None:
            with contextlib.suppress(Exception):
                proc.terminate()
        thread = self._thread
        self._thread = None
        if thread is not None:
            thread.join(timeout=2.0)

    def _loop(self) -> None:
        proc = None
        try:
            proc = self._capturador(self.fonte)
        except Exception as exc:
            logger.debug("mic_captura_nao_abriu", fonte=self.fonte, err=str(exc))
        if proc is None or proc.stdout is None:
            # Degradação silenciosa: sem `parec` (ou sem permissão) o card
            # simplesmente não mostra o módulo de microfone.
            return
        self._proc = proc
        muted: bool | None = None
        blocos_por_leitura_de_mute = max(
            1, int(self._mute_intervalo_s * 1000 / _BLOCO_MS)
        )
        contador = 0
        try:
            while not self._parar.is_set() and not self._parar_global.is_set():
                bloco = proc.stdout.read(_BLOCO_BYTES)
                if not bloco:
                    break  # `parec` morreu: a supervisora respawna no próximo ciclo
                if contador % blocos_por_leitura_de_mute == 0:
                    muted = self._ler_mute()
                contador += 1
                self._publicar(
                    self.uniq,
                    LeituraMic(
                        nivel=nivel_para_fracao(rms_de_pcm_s16le(bloco)),
                        muted=muted,
                        fonte=self.fonte,
                    ),
                )
        except Exception as exc:
            logger.debug("mic_captura_interrompida", fonte=self.fonte, err=str(exc))
        finally:
            self._proc = None
            with contextlib.suppress(Exception):
                proc.terminate()
            with contextlib.suppress(Exception):
                proc.wait(timeout=1.0)

    def _ler_mute(self) -> bool | None:
        saida = self._runner(["pactl", "get-source-mute", self.fonte])
        return muted_de_saida(saida or "")


def _ambiente_c() -> dict[str, str]:
    """Cópia do ambiente com locale neutro (a saída do pactl é traduzida)."""
    env = dict(os.environ)
    env["LC_ALL"] = "C"
    env["LANG"] = "C"
    return env


def _rodar(argv: list[str]) -> str:
    """Roda um comando curto e devolve o stdout ("" em qualquer falha).

    Nunca `shell=True` (invariante do projeto) e sempre com timeout: um
    `pactl` pendurado num PipeWire morto não pode segurar a supervisora.

    A checagem de disponibilidade da ferramenta mora AQUI, no runner, e não
    em quem o chama: assim um runner dublado no teste não depende do que
    está instalado na máquina que roda a suíte.
    """
    if shutil.which(argv[0]) is None:
        return ""
    try:
        proc = subprocess.run(
            argv,
            timeout=_TIMEOUT_SUBPROCESS_S,
            check=False,
            capture_output=True,
            text=True,
            env=_ambiente_c(),
        )
    except Exception as exc:
        logger.debug("mic_comando_falhou", argv=argv[0], err=str(exc))
        return ""
    return proc.stdout or ""


def _abrir_captura(fonte: str) -> Any:
    """Abre o `parec` da source e devolve o processo (None se indisponível)."""
    if shutil.which("parec") is None:
        return None
    # Sem `shell=True` (invariante do projeto): argv fixo, a source entra como
    # argumento e não como texto de comando.
    return subprocess.Popen(
        [
            "parec",
            f"--device={fonte}",
            "--format=s16le",
            f"--rate={_TAXA_HZ}",
            "--channels=1",
            f"--latency-msec={_BLOCO_MS}",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        env=_ambiente_c(),
    )


__all__ = [
    "LeituraMic",
    "MicMonitor",
    "escolher_fonte",
    "escolher_sink",
    "fontes_dualsense",
    "muted_de_saida",
    "nivel_para_fracao",
    "rms_de_pcm_s16le",
    "sinks_dualsense",
    "sufixo_da_ponte_bt",
]
