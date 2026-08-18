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
* **Ausência é resposta.** Sem `pactl`, sem `parec`, sem source do controle
  ou com dois controles no cabo que não dá para distinguir, a leitura é
  `None` e o painel some. Nunca um medidor parado em zero fingindo silêncio.

Por que `LC_ALL=C` em tudo: a saída do `pactl` é TRADUZIDA (nesta máquina o
mute sai como "Mudo: não"). Parsear texto localizado é bug esperando idioma.
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
from dataclasses import dataclass
from typing import Any, ClassVar

from hefesto_dualsense4unix.utils.logging_config import get_logger

logger = get_logger(__name__)

#: Marcadores no NOME da source que identificam um DualSense. O PipeWire monta
#: o nome a partir das strings USB do device ("Sony Interactive Entertainment
#: Wireless Controller"), então o casamento é por substring normalizada.
_MARCADORES_DUALSENSE: tuple[str, ...] = (
    "wireless_controller",
    "wireless controller",
    "dualsense",
)

#: Prefixo do nome que a ponte de mic por Bluetooth publica no PipeWire
#: (``integrations/dualsense_bt_audio.py``): ``hefesto_dualsense_bt_<hex>``,
#: onde ``<hex>`` são os SEIS últimos dígitos hex do MAC do controle.
#:
#: Ele já era descoberto por :func:`fontes_dualsense` (o nome contém
#: "dualsense"), mas :func:`escolher_fonte` só sabia procurar MAC em nomes
#: ``bluez_*`` — e por Bluetooth o DualSense NÃO publica placa ALSA nem source
#: ``bluez`` (não fala A2DP/HFP; o áudio vem como Opus tunelado em HID). Com
#: dois controles ou mais, nenhuma das duas regras casava e o medidor sumia
#: justamente no cenário-alvo do projeto: quatro controles por Bluetooth.
_PREFIXO_SOURCE_PONTE_BT = "hefesto_dualsense_bt_"

#: Tamanho mínimo do sufixo hex aceito como identidade. Seis dígitos são os
#: três últimos octetos do MAC — o que a ponte publica. Menos que isso não
#: distingue controles, e a ponte tem um caminho de fallback (nó sem
#: ``HID_UNIQ``) em que o sufixo é o nome do nó e não um MAC: por isso o
#: sufixo também precisa ser hex INTEIRO para valer.
_MIN_HEX_SUFIXO_BT = 6

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
    """O que o card mostra: quanto entra no mic e se ele está mudo.

    ``nivel`` é 0.0-1.0 já em escala de dB (ver `nivel_para_fracao`), pronto
    para virar altura de barra. ``muted`` None = a source existe mas o estado
    de mute ainda não foi lido — o selo espera em vez de chutar "ATIVO".
    """

    nivel: float = 0.0
    muted: bool | None = None
    fonte: str = ""


# ---------------------------------------------------------------------------
# Funções puras (testáveis sem áudio nenhum)
# ---------------------------------------------------------------------------


def fontes_dualsense(saida_pactl: str) -> list[str]:
    """Nomes das sources de CAPTURA de DualSense em `pactl list sources short`.

    O formato é ``índice\\tnome\\tdriver\\tformato\\testado`` (não traduzido).
    Monitores de saída (``.monitor``) são descartados: são o áudio que SAI
    pelo alto-falante do controle, não o microfone dele — medir aquilo faria
    o "nível do mic" subir com a trilha do jogo.
    """
    out: list[str] = []
    for linha in saida_pactl.splitlines():
        partes = linha.split("\t")
        if len(partes) < 2:
            continue
        nome = partes[1].strip()
        alvo = nome.lower()
        if alvo.endswith(".monitor"):
            continue
        if any(marca in alvo for marca in _MARCADORES_DUALSENSE):
            out.append(nome)
    return out


def escolher_fonte(
    fontes: list[str], uniq: str, uniqs_com_audio: list[str]
) -> str | None:
    """Source atribuível ao controle `uniq` — ou None quando não dá para saber.

    Três regras, nesta ordem:

    1. **O nome carrega o MAC inteiro.** Sources de Bluetooth nascem como
       ``bluez_input.XX_XX_XX_XX_XX_XX``; ali o MAC está no nome e a
       atribuição é certa mesmo com vários controles. A busca por MAC é
       restrita a esses nomes DE PROPÓSITO: em nomes ALSA o "hex" que sobra
       ao filtrar letras é lixo de palavra ("Interactive" vira "eac"), e um
       casamento por acaso ali apontaria o mic do controle errado.
    2. **O nome carrega o RABO do MAC** (MIC-BT-01). A ponte de mic por
       Bluetooth deste projeto publica ``hefesto_dualsense_bt_<hex6>``, e
       esses seis dígitos são os três últimos octetos do MAC. O casamento é
       por sufixo, e só quando o que vem depois do prefixo é hex INTEIRO com
       ao menos :data:`_MIN_HEX_SUFIXO_BT` dígitos — a ponte tem um caminho
       de fallback, para nó sem ``HID_UNIQ``, em que ali vai o nome do nó
       (``hidraw3``) e não um MAC. Sem esta regra o medidor NUNCA aparecia
       por Bluetooth com dois controles ou mais.
    3. **Um para um.** Uma única source de DualSense e um único controle
       candidato: só pode ser ele.

    Fora disso devolve None. Dois DualSense no cabo publicam sources cujo
    nome não distingue um do outro (a string USB é a mesma), e exibir o mic
    do controle errado é pior que não exibir nenhum — é a regra do "não
    invente dado na interface".
    """
    alvo = _so_hex(uniq)
    if alvo:
        for fonte in fontes:
            if fonte.lower().startswith("bluez") and alvo in _so_hex(fonte):
                return fonte
        for fonte in fontes:
            sufixo = sufixo_da_ponte_bt(fonte)
            if sufixo and alvo.endswith(sufixo):
                return fonte
    if len(fontes) == 1 and len(uniqs_com_audio) == 1 and uniqs_com_audio[0] == uniq:
        return fontes[0]
    return None


def sufixo_da_ponte_bt(fonte: str) -> str:
    """Rabo hex do MAC no nome da source da ponte BT — "" se não for uma.

    Recorta o prefixo ANTES de filtrar hex, e a ordem não é detalhe: o
    próprio prefixo ``hefesto_dualsense_bt_`` é cheio de letras hex
    (``e``, ``f``, ``d``, ``a``, ``b``), e passar o nome inteiro por
    :func:`_so_hex` produziria um "MAC" com lixo do prefixo grudado na
    frente — casamento por acaso, que é exatamente o que a regra 1 evita.
    """
    baixa = fonte.lower()
    if not baixa.startswith(_PREFIXO_SOURCE_PONTE_BT):
        return ""
    resto = baixa[len(_PREFIXO_SOURCE_PONTE_BT) :]
    if len(resto) < _MIN_HEX_SUFIXO_BT or _so_hex(resto) != resto:
        return ""
    return resto


def _so_hex(valor: str) -> str:
    """Só os dígitos hex minúsculos — mesma normalização de MAC do projeto."""
    return "".join(ch for ch in valor.lower() if ch in "0123456789abcdef")


def muted_de_saida(saida: str) -> bool | None:
    """Lê ``Mute: yes|no`` do `pactl get-source-mute`; None se ilegível.

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
        """Última leitura do mic deste controle; None = sem mic atribuível."""
        with self._lock:
            return self._leituras.get(uniq)

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
        """Casa as capturas vivas com aba visível, controles e sources.

        Público para o teste exercitar o ciclo sem depender de temporização.
        """
        with self._lock:
            ativo = self._ativo
            controles = self._controles
        if not ativo or not controles:
            self._derrubar_capturas(set())
            with self._lock:
                self._leituras = {}
            return

        fontes = self._descobrir_fontes()
        alvos: dict[str, str] = {}
        for uniq in controles:
            fonte = escolher_fonte(fontes, uniq, list(controles))
            if fonte is not None:
                alvos[uniq] = fonte
        self._derrubar_capturas(set(alvos))
        with self._lock:
            self._leituras = {
                u: leitura for u, leitura in self._leituras.items() if u in alvos
            }
        for uniq, fonte in alvos.items():
            self._garantir_captura(uniq, fonte)

    def _descobrir_fontes(self) -> list[str]:
        saida = self._runner(["pactl", "list", "sources", "short"])
        return fontes_dualsense(saida or "")

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
    "fontes_dualsense",
    "muted_de_saida",
    "nivel_para_fracao",
    "rms_de_pcm_s16le",
    "sufixo_da_ponte_bt",
]
