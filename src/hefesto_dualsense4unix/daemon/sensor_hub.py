"""sensor_hub.py — giroscópio, acelerômetro, touchpad e ENTRADAS por controle.

Quem consome: o enriquecimento do `state_full` (`ipc_handlers`), que roda no
event loop do daemon a 10 Hz enquanto a GUI está aberta. Quem produz: um
`MotionSensorReader`, um `TouchpadReader` e — desde STATUS-04 — um
`EvdevReader` PASSIVO por controle, cada um na sua thread de evdev.

**O terceiro tipo nasceu em 04/09/2026 e é a entrega STATUS-04**, escrita em
17/07/2026 e adiada com razão medida: *"co-op é DEFAULT ON (…) no estado
normal da máquina do usuário, TODO secundário já tem reader e o card dele já terá
inputs só com STATUS-01/02. O buraco real é o **modo Nativo** (…) e
emulação-off"*. A aposta continua verdadeira — medido em 04/09/2026 com os
dois DualSense do usuário em USB e co-op ligado, os DOIS controles publicam
`inputs` com giro, acelerômetro e touchpad, e este hub não abre reader de
gamepad NENHUM. O que ela fecha é o buraco: nos modos em que o co-op está
desmontado (Nativo, emulação off, suspensão por Steam Input) o secundário
ficava com `inputs: None` e METADE DA MESA emudecia por desenho.

As três regras que moldaram este desenho:

1. **A descoberta é cara e o event loop é único.** Enumerar `/dev/input`
   custa: a do gamepad abre cada nó de gamepad (a lição
   PERF-MULTI-CONTROLLER-01), e a do touchpad e a do movimento leem dezenas
   de arquivos do sysfs. Fazer isso no `state_full` congelaria o daemon inteiro
   dez vezes por segundo.
   Aqui `leitura()` só toca dicionários sob lock (µs) e TODA descoberta mora
   na thread de manutenção.

2. **Sensor sem consumidor não deve existir.** Os readers nascem quando
   alguém pede o controle e morrem `_DEMANDA_TTL_S` depois do último pedido
   — fechar a GUI (ou só sair da aba Status) apaga as threads sozinho. Sem
   isso, um daemon de dias acumularia um reader por controle que já passou
   pela máquina.

3. **Ausência é resposta válida.** Controle sem node de motion (externo,
   kernel antigo, BT em modo estranho) não é erro: entra na lista de "já
   procurei e não achei" e só é reprocurado quando `/dev/input` muda de
   verdade. O payload sai sem o campo e a interface não mostra sensor
   nenhum — nunca um zero fingindo repouso.

O touchpad é aberto com `acumular_movimento=False`: o mesmo node já é lido
pelo `TouchpadReader` do cursor, e um segundo acumulador que ninguém drena
viraria salto de cursor. Aqui só se OBSERVA (`touch_state()`), nunca se
drena (`consume_motion()` continua sendo exclusividade do poll loop).

**O reader do GAMEPAD nunca faz `set_grab`, e é onde isso deixa de ser
detalhe.** Um `EVIOCGRAB` no node do CONTROLE tornaria o daemon leitor
exclusivo e o JOGO pararia de ver o controle — seria trocar um card mudo por
um controle morto. Observar um node que ninguém grabou não disputa nada: o
evdev entrega o mesmo evento a todos os fds abertos, e isto não é hidraw
(a armadilha nº 3 desta casa, o instrumento que briga com o produto, mora na
outra camada).

**O reader de MOTION é a exceção, e ela nasceu deliberada em 04/09/2026**
(SENSOR-DE-VERDADE-01, decisão de produto: *"ele tem que funcionar de verdade.
ambos independente do modo e da mascara"*). <!-- noqa-acento: citação literal -->
O node "Motion Sensors" é SEPARADO do node do controle: grabá-lo esconde o
giro e o acelerômetro de quem lê evdev **sem tocar um único botão** — os
gatilhos, os analógicos e o d-pad continuam chegando ao jogo pelo outro node.
É o oposto do caso acima, e é por isso que a mesma máquina de grab serve aos
dois com sinais trocados. Só grabamos quando ELA desligou um sensor; sem
pedido, este hub continua sendo um observador que não disputa nada
(:meth:`SensorHub._reconciliar_grabs`).

**Quem grabou o node é que fica com os eventos, e por isso o `ipc_handlers`
NÃO pede `entradas()` de um controle que o co-op já segura.** MEDIDO no
hardware dela em 04/09/2026, e o resultado é PIOR do que "o card fica em
zero": abrindo um reader passivo sobre os dois nodes que o daemon já grabava,
os dois abriram sem erro e publicaram

    lx=129 ly=130 rx=127 ry=130   ·   lx=128 ly=129 rx=130 ry=126

**parados, por 4 s.** Não são os `128` de fábrica, que se reconheceriam de
longe: o `_on_device_opened` lê o `absinfo` no open, então a leitura nasce com
a posição REAL de repouso de cada analógico daquele aparelho — um número
plausível, específico do controle, e eternamente congelado. Um card alimentado
por isso não parece quebrado; parece um controle que ninguém está tocando. É a
mentira mais cara que este módulo poderia contar, e é por isso que a recusa
mora em quem PERGUNTA (`_inputs_passivos`), não aqui.
"""
from __future__ import annotations

import contextlib
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, ClassVar

from hefesto_dualsense4unix.utils.logging_config import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True)
class AmostraDoDsu:
    """O que o servidor DSU lê de UM controle num instante, sem arredondar.

    ``carimbo_us`` e ``epoca`` são os do ``MotionSensorReader``
    (``carimbo_us`` é ``None`` sem leitor de movimento ou antes do primeiro
    carimbo). ``toques`` são os dedos do último quadro fechado do touchpad,
    em ordem de slot; vazio sem dedo ou sem leitor de touchpad.
    """

    giro: tuple[float, float, float] = (0.0, 0.0, 0.0)
    aceleracao: tuple[float, float, float] = (0.0, 0.0, 0.0)
    carimbo_us: int | None = None
    epoca: int = 0
    toques: tuple[Any, ...] = ()
    #: Quais leitores responderam. Giro e aceleração zerados sem
    #: ``com_movimento`` são ausência, não repouso.
    com_movimento: bool = False
    com_toque: bool = False


class SensorHub:
    """Registro de leitores de sensores por controle, movido a demanda."""

    _DEMANDA_TTL_S: ClassVar[float] = 5.0
    _MANUTENCAO_INTERVALO_S: ClassVar[float] = 1.0
    _TIPOS: ClassVar[tuple[str, ...]] = ("motion", "touchpad", "gamepad")

    def __init__(
        self,
        *,
        motion_factory: Callable[[str, Any], Any] | None = None,
        touch_factory: Callable[[str, Any], Any] | None = None,
        gamepad_factory: Callable[[str, Any], Any] | None = None,
        descobrir_motion: Callable[[], dict[str, Any]] | None = None,
        descobrir_touch: Callable[[], dict[str, Any]] | None = None,
        descobrir_gamepad: Callable[[], dict[str, Any]] | None = None,
        relogio: Callable[[], float] | None = None,
        auto_manutencao: bool = True,
        ha_jogo: Callable[[], bool] | None = None,
        toque_proprio_do_jogo: Callable[[str], bool] | None = None,
    ) -> None:
        """As fábricas e os descobridores são injetáveis para teste.

        ``ha_jogo`` diz se há jogo aberto; ``toque_proprio_do_jogo(uniq)`` diz se o jogo em foco
        tem configuração própria de toque para esta peça. Sem eles, não há jogo.
        """
        self._relogio = relogio or time.monotonic
        self._ha_jogo = ha_jogo
        self._toque_proprio_do_jogo = toque_proprio_do_jogo
        self._universo_do_toque: set[str] | None = None
        self._auto_manutencao = auto_manutencao
        self._motion_factory = motion_factory or self._motion_reader_real
        self._touch_factory = touch_factory or self._touch_reader_real
        self._gamepad_factory = gamepad_factory or self._gamepad_reader_real
        self._descobrir_motion = descobrir_motion or self._descobrir_motion_real
        self._descobrir_touch = descobrir_touch or self._descobrir_touch_real
        self._descobrir_gamepad = descobrir_gamepad or self._descobrir_gamepad_real

        self._lock = threading.RLock()
        self._demanda: dict[str, float] = {}
        self._demanda_entradas: dict[str, float] = {}  # o `state_full`: TODO controle com `inputs`
        self._demanda_do_toque: dict[str, float] = {}
        self._demanda_dos_dedos: dict[str, float] = {}  # `pedir_os_dedos`: só o toque, sem grab
        #: Os controles cujo dedo o servidor DSU segura (``segurar_o_dedo``).
        self._dedo_segurado: dict[str, float] = {}
        self._motion: dict[str, Any] = {}
        self._touch: dict[str, Any] = {}
        self._gamepad: dict[str, Any] = {}
        #: varrer `/dev/input` inteiro a cada segundo por causa do que falta.
        #: Só saem daqui quando `/dev/input` muda de verdade.
        self._sem_node: set[tuple[str, str]] = set()
        #: O mesmo, para as peças com sensor desligado (`_sensores_desligados`):
        #: as chaves já procuradas desde a última mudança de `/dev/input`.
        self._desligados_procurados: set[str] = set()
        self._watch: Any = None
        self._parar = threading.Event()
        self._thread: threading.Thread | None = None

    # -- API consumida pelo event loop (barata por contrato) --------------

    def velocidade_do_movimento(self, uniq: str) -> tuple[float, float, float] | None:
        """Velocidade angular de `uniq` AGORA, em graus/s; `None` sem reader.

        IRMÃ MAGRA DA `leitura()`, e a magreza é o ponto: esta é chamada pelo
        TIQUE do jogo (60 Hz por controle), não pelo painel. Sem arredondar e
        sem montar dicionário — uma tupla de três floats sob lock.

        REGISTRA A DEMANDA, como a `leitura()`: é isto que mantém o reader de
        motion vivo enquanto a mira estiver ligada. Sem o registro, o TTL
        apagaria a thread no meio da partida e a mira morreria sozinha, que é a
        forma de defeito mais difícil de diagnosticar que existe.

        `None` é resposta honesta — *"não há reader para este controle"* — e
        não `(0,0,0)`: zero é um controle parado, e um painel (ou uma mira)
        alimentado por essa confusão descreve um aparelho que não está lá.
        """
        agora = self._relogio()
        with self._lock:
            self._demanda[uniq] = agora
            motion = self._motion.get(uniq)
        self._garantir_manutencao()
        if motion is None:
            return None
        try:
            giro = motion.snapshot()
            return (float(giro.x), float(giro.y), float(giro.z))
        except Exception:
            return None

    def angulo_do_movimento(self, uniq: str) -> tuple[float, float, float] | None:
        """Ângulo percorrido por `uniq` desde a última chamada — **DRENA**.

        TEM UM DONO SÓ, e ele está escrito para ninguém acrescentar o segundo:
        o roteador de movimento, no tique do jogo. Um segundo chamador
        dividiria o movimento entre os dois e a mira dela andaria pela metade —
        é a mesma regra do `TouchpadReader.consume_motion`, cujo dono é o poll
        loop.

        Quem quiser VER o giro sem consumir chama `velocidade_do_movimento` ou
        `leitura`, que não drenam nada.
        """
        agora = self._relogio()
        with self._lock:
            self._demanda[uniq] = agora
            motion = self._motion.get(uniq)
        self._garantir_manutencao()
        if motion is None:
            return None
        try:
            x, y, z = motion.consume_angulo()
            return (float(x), float(y), float(z))
        except Exception:
            return None

    def leitura(self, uniq: str) -> dict[str, Any]:
        """Sensores conhecidos de `uniq` agora; `{}` enquanto não houver.

        Registra a demanda (é o que mantém os readers vivos) e devolve só o
        que EXISTE: sem reader de motion não há chave `gyro` nem `accel`, sem
        reader de touchpad não há chave `touchpad`. Nunca levanta — o
        `state_full` não pode cair por causa de um sensor.

        `gyro` e `accel` saem do MESMO reader e do MESMO node evdev (os seis
        eixos do "Motion Sensors"), mas são chaves independentes: um reader que
        não saiba entregar o acelerômetro continua publicando o giro.
        """
        agora = self._relogio()
        with self._lock:
            self._demanda[uniq] = agora
            motion = self._motion.get(uniq)
            touch = self._touch.get(uniq)
        self._garantir_manutencao()

        out: dict[str, Any] = {}
        if motion is not None:
            with contextlib.suppress(Exception):
                gyro = motion.snapshot()
                out["gyro"] = {
                    "x": round(float(gyro.x), 2),
                    "y": round(float(gyro.y), 2),
                    "z": round(float(gyro.z), 2),
                }
            # DOIS `suppress` e não um, e o motivo é o que a MORDIDA mediu, não
            # o que parecia (29/08/2026). A primeira redação desta linha dizia
            # que um bloco só faria o `AttributeError` do acelerômetro "apagar o
            # `out["gyro"]`" — e é FALSO: a atribuição do giro já aconteceu
            # quando a exceção sobe, e o dicionário fica com ela. Arrancada a
            # separação, o teste passou igual, que é como o erro apareceu.
            #
            # O que a separação protege de verdade é o SENTIDO CONTRÁRIO: com um
            # bloco só, um `snapshot()` que levanta (node sumindo no meio da
            # leitura) aborta o bloco ANTES de chegar ao acelerômetro, e o
            # acelerômetro some da tela por causa de um defeito do giroscópio.
            # Separados, cada sensor cai sozinho.
            #
            # Três casas e não duas (o giro usa duas): a escala é g, e 1 g é o
            # repouso. Com duas casas a inclinação de um controle na mão anda em
            # degraus de 0,01 g — visível como serrilha nas barras. Três casas
            # custam ~6 bytes por controle por tique.
            with contextlib.suppress(Exception):
                accel = motion.accel_snapshot()
                out["accel"] = {
                    "x": round(float(accel.x), 3),
                    "y": round(float(accel.y), 3),
                    "z": round(float(accel.z), 3),
                }
        if touch is not None:
            with contextlib.suppress(Exception):
                out["touchpad"] = self._o_toque(touch)
        return out

    def toque_visto(self, uniq: str) -> dict[str, Any] | None:
        """O ``touchpad`` da :meth:`leitura` de `uniq`, só se o leitor já vive; ``None`` sem ele.

        Só VÊ: não registra demanda nem sobe a manutenção. Quem lê a cada tique sem pedir o
        touchpad (o tópico ``entradas`` das extensões) usa esta, e o leitor fica vivo só pela
        tela, pelo toque roteado, pelo DSU ou por :meth:`pedir_os_dedos`.
        """
        with self._lock:
            touch = self._touch.get(uniq)
        if touch is None:
            return None
        try:
            return self._o_toque(touch)
        except Exception as exc:
            logger.debug("sensor_hub_toque_visto_falhou", identity=uniq, err=str(exc))
            return None

    def pedir_os_dedos(self, uniq: str) -> None:
        """Mantém vivo o leitor de toque de `uniq` pelo prazo da demanda, sem o de movimento.

        Não graba o nó: o cursor do computador segue com o dedo (o grab é do
        :meth:`toque_da_peca` e do DSU).
        """
        with self._lock:
            self._demanda_dos_dedos[uniq] = self._relogio()
        self._garantir_manutencao()

    @staticmethod
    def _o_toque(touch: Any) -> dict[str, Any]:
        """O ``touchpad`` de um leitor, na forma da :meth:`leitura`; levanta se o leitor falha."""
        estado = touch.touch_state()
        return {
            "touching": bool(estado.touching),
            "x": int(estado.x),
            "y": int(estado.y),
            "width": int(estado.largura),
            "height": int(estado.altura),
            # MULTITOQUE-01 (18/09/2026): os dedos, um por slot do
            # kernel. `x`/`y` acima continuam sendo o dedo principal
            # — quem conhecia só eles não muda de comportamento.
            # Lista VAZIA quer dizer "nenhum dedo agora", e é
            # diferente da chave AUSENTE, que quer dizer "este
            # reader não sabe ler dedo por slot": a tela desenha o
            # resumo no segundo caso e a verdade no primeiro.
            "pontos": [
                {
                    "slot": int(ponto.slot),
                    "x": int(ponto.x),
                    "y": int(ponto.y),
                    "id": int(ponto.identidade),
                }
                for ponto in getattr(estado, "pontos", ())
            ],
        }

    def entradas(self, uniq: str) -> dict[str, Any] | None:
        """Analógicos, gatilhos e botões de `uniq` agora; `None` sem reader."""
        agora = self._relogio()
        with self._lock:
            self._demanda_entradas[uniq] = agora
            reader = self._gamepad.get(uniq)
        self._garantir_manutencao()

        if reader is None:
            return None
        try:
            snap = reader.snapshot()
            return {
                "lx": int(snap.lx),
                "ly": int(snap.ly),
                "rx": int(snap.rx),
                "ry": int(snap.ry),
                "l2_raw": int(snap.l2_raw),
                "r2_raw": int(snap.r2_raw),
                "buttons": sorted(snap.buttons_pressed),
            }
        except Exception as exc:  # o `state_full` não cai por causa de um node
            logger.debug("sensor_hub_entradas_falhou", identity=uniq, err=str(exc))
            return None

    def apertos(self, uniq: str) -> dict[str, int] | None:
        """Os contadores de aperto do reader de gamepad de `uniq`; `None` sem reader.

        A Navegação Interna conta os toques de cada controle pela borda, e o
        passivo é a fonte do secundário sem co-op (o Nativo). Leitura pura:
        não registra demanda, quem mantém o reader vivo é a `entradas`.
        """
        with self._lock:
            reader = self._gamepad.get(uniq)
        if reader is None:
            return None
        try:
            apertos = getattr(reader.snapshot(), "apertos", None)
        except Exception as exc:  # o IPC não cai por causa de um node
            logger.debug("sensor_hub_apertos_falhou", identity=uniq, err=str(exc))
            return None
        return dict(apertos) if isinstance(apertos, dict) else None

    def hz_do_movimento(self, uniq: str) -> float | None:
        """Pacotes por segundo que o nó de movimento de `uniq` recebe AGORA."""
        agora = self._relogio()
        with self._lock:
            self._demanda[uniq] = agora
            motion = self._motion.get(uniq)
        self._garantir_manutencao()
        perguntar = getattr(motion, "hz_do_movimento", None)
        if not callable(perguntar):
            return None
        try:
            hz = perguntar()
        except Exception:
            return None
        if isinstance(hz, bool) or not isinstance(hz, (int, float)):
            return None
        return float(hz)

    def stop_all(self) -> None:
        """Para a manutenção e todos os readers. Idempotente."""
        self._parar.set()
        thread = self._thread
        self._thread = None
        if thread is not None:
            thread.join(timeout=2.0)
        with self._lock:
            readers = [
                reader for tipo in self._TIPOS for reader in self._mapa(tipo).values()
            ]
            self._motion.clear()
            self._touch.clear()
            self._gamepad.clear()
            self._demanda.clear()
            self._demanda_entradas.clear()
            self._demanda_do_toque.clear()
            self._demanda_dos_dedos.clear()
            self._dedo_segurado.clear()
        for reader in readers:
            with contextlib.suppress(Exception):
                reader.stop()


    def _garantir_manutencao(self) -> None:
        """Sobe a thread de manutenção na primeira demanda (idempotente)."""
        if self._parar.is_set() or not self._auto_manutencao:
            return
        thread = self._thread
        if thread is not None and thread.is_alive():
            return
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                return
            self._thread = threading.Thread(
                target=self._loop_manutencao,
                name="hefesto-sensor-hub",
                daemon=True,
            )
            self._thread.start()

    def _loop_manutencao(self) -> None:
        while not self._parar.is_set():
            try:
                self.reconciliar()
            except Exception as exc:
                logger.debug("sensor_hub_reconciliacao_falhou", err=str(exc))
            self._parar.wait(self._MANUTENCAO_INTERVALO_S)

    def perguntar_ao_daemon(
        self,
        *,
        ha_jogo: Callable[[], bool] | None,
        toque_proprio_do_jogo: Callable[[str], bool] | None,
    ) -> None:
        """Liga o hub às duas perguntas que só o daemon sabe responder (ver ``__init__``)."""
        self._ha_jogo = ha_jogo
        self._toque_proprio_do_jogo = toque_proprio_do_jogo

    def vigiar(self) -> None:
        """Sobe a manutenção sem esperar pedido: o touchpad Desligado vale com a tela fechada."""
        self._garantir_manutencao()

    def reconciliar(self) -> None:
        """Casa os readers vivos com a demanda atual. Roda FORA do event loop."""
        agora = self._relogio()
        self._empurrar_o_jogo()
        mudou = self._input_dir_mudou()
        desligados = self._sensores_desligados(mudou)
        do_toque = self._toque_sem_demanda(mudou)
        with self._lock:
            vivos_sensores = self._podar(self._demanda, agora)
            self._demanda = {
                u: t for u, t in self._demanda.items() if u in vivos_sensores
            }
            vivos_entradas = self._podar(self._demanda_entradas, agora)
            self._demanda_entradas = {
                u: t for u, t in self._demanda_entradas.items() if u in vivos_entradas
            }
            vivos_dedos = self._podar(self._demanda_dos_dedos, agora)
            self._demanda_dos_dedos = {
                u: t for u, t in self._demanda_dos_dedos.items() if u in vivos_dedos
            }
            segurados = {
                u
                for u, t in self._dedo_segurado.items()
                if (agora - t) <= self._DEDO_SEGURADO_TTL_S
            }
            desejados: dict[str, set[str]] = {
                "motion": vivos_sensores | desligados,
                "touchpad": vivos_sensores | segurados | do_toque | vivos_dedos,
                "gamepad": vivos_entradas,
            }
            sobrando = [
                (uniq, tipo)
                for tipo in self._TIPOS
                for uniq in list(self._mapa(tipo))
                if uniq not in desejados[tipo]
            ]
            faltando = {
                (uniq, tipo)
                for tipo in self._TIPOS
                for uniq in desejados[tipo]
                if uniq not in self._mapa(tipo)
            }
            sem_node = set(self._sem_node)

        for uniq, tipo in sobrando:
            with self._lock:
                reader = self._mapa(tipo).pop(uniq, None)
            if reader is not None:
                with contextlib.suppress(Exception):
                    reader.stop()
                logger.debug("sensor_hub_reader_parado", identity=uniq, tipo=tipo)

        if mudou:
            sem_node = set()
            with self._lock:
                self._sem_node = set()
        novos = faltando - sem_node
        if novos:
            self._abrir_readers(novos)
        self._reconciliar_grabs(desligados)
        self._reconciliar_grabs_do_toque(agora)


    def _sensores_desligados(self, mudou: bool = False) -> set[str]:
        """Os `uniq` (na grafia da DESCOBERTA) com algum sensor desligado."""
        from hefesto_dualsense4unix.core.virtual_motion import (
            REGISTRO,
            chave_de_sensor,
        )

        alvos = set(REGISTRO.desligados())
        if not alvos:
            return set()
        with self._lock:
            conhecidos = set(self._motion) | set(self._demanda)
        achados = {u for u in conhecidos if chave_de_sensor(u) in alvos}
        faltando = alvos - {chave_de_sensor(u) for u in achados}
        if mudou:
            self._desligados_procurados = set()
        if faltando and not faltando <= self._desligados_procurados:
            for uniq in self._chamar_descobridor(self._descobrir_motion):
                if chave_de_sensor(uniq) in faltando:
                    achados.add(uniq)
            if not mudou:
                self._desligados_procurados |= faltando
        return achados

    def _toque_sem_demanda(self, mudou: bool) -> set[str]:
        """Os `uniq` cujo reader do touchpad tem de ficar vivo SEM ninguém o pedindo.

        O Desligado que cala o toque no jogo e o toque que o jogo recebe pelo vpad seguram o nó
        enquanto durarem, e o reader some sozinho 5 s depois do último pedido da tela. A
        descoberta dos nós roda só quando alguma dessas duas demandas existe.
        """
        from hefesto_dualsense4unix.core.virtual_motion import REGISTRO

        jogo = REGISTRO.jogo_aberto()
        interesse = bool(REGISTRO.touchpad_desligados()) or (
            jogo and callable(self._toque_proprio_do_jogo)
        )
        if not interesse:
            self._universo_do_toque = None
            return set()
        if mudou or self._universo_do_toque is None:
            self._universo_do_toque = set(self._chamar_descobridor(self._descobrir_touch))
        return {
            uniq
            for uniq in self._universo_do_toque
            if self._toque_querido(uniq, 0.0, {}, {}, jogo)
        }

    def _reconciliar_grabs(self, desligados: set[str]) -> None:
        """O nó "Motion Sensors" fica GRABADO enquanto houver sensor desligado."""
        with self._lock:
            readers = dict(self._motion)
        for uniq, reader in readers.items():
            querido = uniq in desligados
            aplicar = getattr(reader, "set_grab", None)
            if not callable(aplicar):
                continue
            estado = getattr(reader, "grab_state", "off")
            if querido and estado == "held":
                continue
            if not querido and estado in ("off", "failed"):
                continue
            with contextlib.suppress(Exception):
                aplicar(querido)

    def grab_do_movimento(self, uniq: str) -> str:
        """Estado do EVIOCGRAB no nó de movimento de `uniq`."""
        from hefesto_dualsense4unix.core.virtual_motion import chave_de_sensor

        alvo = chave_de_sensor(uniq)
        with self._lock:
            reader = next(
                (r for u, r in self._motion.items() if chave_de_sensor(u) == alvo),
                None,
            )
        if reader is None:
            return "sem_reader"
        estado = getattr(reader, "grab_state", None)
        return str(estado) if isinstance(estado, str) else "off"

    def _podar(self, registro: dict[str, float], agora: float) -> set[str]:
        """Quem, neste registro de demanda, ainda está dentro do TTL."""
        return {
            uniq
            for uniq, visto in registro.items()
            if (agora - visto) <= self._DEMANDA_TTL_S
        }

    def _mapa(self, tipo: str) -> dict[str, Any]:
        """Registro de readers do `tipo` ("motion" | "touchpad" | "gamepad")."""
        if tipo == "motion":
            return self._motion
        if tipo == "touchpad":
            return self._touch
        return self._gamepad

    def _input_dir_mudou(self) -> bool:
        """True se `/dev/input` mudou desde a última volta (barato, ~µs)."""
        watch = self._watch
        if watch is None:
            from hefesto_dualsense4unix.core.evdev_reader import InputDirWatch

            watch = InputDirWatch()
            self._watch = watch
            watch.poll()
            return True
        resultado = watch.poll()
        return bool(resultado)

    def _abrir_readers(self, pendentes: set[tuple[str, str]]) -> None:
        """Cria e inicia os readers que faltam (descoberta cara mora aqui)."""
        descobridores = {
            "motion": self._descobrir_motion,
            "touchpad": self._descobrir_touch,
            "gamepad": self._descobrir_gamepad,
        }
        nodes = {
            tipo: self._chamar_descobridor(descobridores[tipo])
            for tipo in {t for _, t in pendentes}
        }
        fabricas = {
            "motion": self._motion_factory,
            "touchpad": self._touch_factory,
            "gamepad": self._gamepad_factory,
        }
        for uniq, tipo in sorted(pendentes):
            if not self._abrir_um(uniq, tipo, nodes[tipo], fabricas[tipo]):
                with self._lock:
                    self._sem_node.add((uniq, tipo))

    @staticmethod
    def _chamar_descobridor(fn: Callable[[], dict[str, Any]]) -> dict[str, Any]:
        try:
            mapa = fn()
        except Exception as exc:
            logger.debug("sensor_hub_descoberta_falhou", err=str(exc))
            return {}
        return mapa if isinstance(mapa, dict) else {}

    def _abrir_um(
        self,
        uniq: str,
        tipo: str,
        nodes: dict[str, Any],
        factory: Callable[[str, Any], Any],
    ) -> bool:
        """Abre UM reader; False quando este controle não tem esse node."""
        with self._lock:
            if uniq in self._mapa(tipo):
                return True
        node = nodes.get(uniq)
        if node is None:
            return False
        try:
            reader = factory(uniq, node)
            if not reader.start():
                with contextlib.suppress(Exception):
                    reader.stop()
                return False
        except Exception as exc:
            logger.debug(
                "sensor_hub_reader_falhou", identity=uniq, tipo=tipo, err=str(exc)
            )
            return False
        with self._lock:
            anterior = self._mapa(tipo).get(uniq)
            self._mapa(tipo)[uniq] = reader
        if anterior is not None:
            with contextlib.suppress(Exception):
                anterior.stop()
        logger.info("sensor_hub_reader_iniciado", identity=uniq, tipo=tipo)
        return True


    @staticmethod
    def _motion_reader_real(uniq: str, node: Any) -> Any:
        from hefesto_dualsense4unix.core.evdev_reader import MotionSensorReader

        return MotionSensorReader(device_path=node, target_uniq=uniq)

    @staticmethod
    def _touch_reader_real(uniq: str, node: Any) -> Any:
        from hefesto_dualsense4unix.core.evdev_reader import TouchpadReader

        return TouchpadReader(
            device_path=node, target_uniq=uniq, acumular_movimento=False
        )

    @staticmethod
    def _gamepad_reader_real(uniq: str, node: Any) -> Any:
        """O reader PASSIVO de STATUS-04 — e `set_grab` nunca é chamado."""
        from hefesto_dualsense4unix.core.evdev_reader import EvdevReader

        return EvdevReader(device_path=node, target_uniq=uniq)

    @staticmethod
    def _descobrir_motion_real() -> dict[str, Any]:
        from hefesto_dualsense4unix.core.evdev_reader import (
            discover_dualsense_motion_evdevs,
        )

        return dict(discover_dualsense_motion_evdevs())

    @staticmethod
    def _descobrir_touch_real() -> dict[str, Any]:
        from hefesto_dualsense4unix.core.evdev_reader import (
            discover_dualsense_touchpad_evdevs,
        )

        return dict(discover_dualsense_touchpad_evdevs())

    @staticmethod
    def _descobrir_gamepad_real() -> dict[str, Any]:
        """MAC -> node de gamepad, reusando a descoberta ÚNICA da casa."""
        from hefesto_dualsense4unix.core.evdev_reader import discover_dualsense_evdevs

        return dict(discover_dualsense_evdevs())


    _TOQUE_ROTEADO_TTL_S: ClassVar[float] = 1.5
    #: Quanto o dedo fica guardado para o emulador depois do último pedido do
    #: servidor DSU. É o mesmo prazo da inscrição do cliente (5 s).
    _DEDO_SEGURADO_TTL_S: ClassVar[float] = 5.0

    def aceleracao_do_movimento(self, uniq: str) -> tuple[float, float, float] | None:
        """O acelerômetro de `uniq` AGORA, em g; `None` sem leitor."""
        agora = self._relogio()
        with self._lock:
            self._demanda[uniq] = agora
            motion = self._motion.get(uniq)
        self._garantir_manutencao()
        if motion is None:
            return None
        try:
            acel = motion.accel_snapshot()
            return (float(acel.x), float(acel.y), float(acel.z))
        except Exception:
            return None

    def amostra_do_dsu(self, uniq: str) -> AmostraDoDsu | None:
        """Giro, aceleração, carimbo, época e toques de `uniq` AGORA; `None` sem leitor.

        IRMÃ MAGRA do servidor DSU, no molde da `velocidade_do_movimento`: sem
        arredondar, sem montar dicionário, nunca levanta e NÃO DRENA nada
        (nem o ângulo, nem o delta do cursor). Registra a demanda dos sensores,
        e é isso que mantém os leitores vivos enquanto um emulador pede; sem
        pedido, o TTL os apaga em 5 s.

        Um leitor que levanta não derruba o outro: o toque some da amostra sem
        levar o movimento, e vice-versa. Sem nenhum dos dois, `None`.
        """
        agora = self._relogio()
        with self._lock:
            self._demanda[uniq] = agora
            motion = self._motion.get(uniq)
            touch = self._touch.get(uniq)
        self._garantir_manutencao()
        if motion is None and touch is None:
            return None
        giro: tuple[float, float, float] = (0.0, 0.0, 0.0)
        aceleracao: tuple[float, float, float] = (0.0, 0.0, 0.0)
        carimbo_us: int | None = None
        epoca = 0
        toques: tuple[Any, ...] = ()
        com_movimento = com_toque = False
        if motion is not None:
            try:
                amostra = motion.amostra_do_movimento()
                g, a = amostra.giro, amostra.aceleracao
                giro = (float(g[0]), float(g[1]), float(g[2]))
                aceleracao = (float(a[0]), float(a[1]), float(a[2]))
                carimbo_us = amostra.carimbo_us
                epoca = int(amostra.epoca)
                com_movimento = True
            except Exception:
                com_movimento = False
        if touch is not None:
            try:
                toques = tuple(touch.touch_state().pontos)
                com_toque = True
            except Exception:
                toques = ()
        if not (com_movimento or com_toque):
            return None
        return AmostraDoDsu(
            giro=giro,
            aceleracao=aceleracao,
            carimbo_us=carimbo_us,
            epoca=epoca,
            toques=toques,
            com_movimento=com_movimento,
            com_toque=com_toque,
        )

    def segurar_o_dedo(self, uniq: str) -> None:
        """Guarda o dedo de `uniq` para o emulador pelos próximos 5 s.

        Enquanto o servidor DSU renova, o nó «Touchpad» do controle fica com
        `EVIOCGRAB`: o libinput para de ver o dedo (o cursor do PC não anda) e
        este hub segue lendo. O prazo vence sozinho; sem renovação o grab solta
        na volta seguinte da manutenção. O grab do movimento e o do toque são
        independentes.
        """
        with self._lock:
            self._dedo_segurado[uniq] = self._relogio()
        self._garantir_manutencao()

    def toque_da_peca(self, uniq: str) -> tuple[Any, bool] | None:
        """O dedo de `uniq` AGORA e o clique: `(TouchState, clicado)`; `None` sem leitor."""
        agora = self._relogio()
        with self._lock:
            self._demanda[uniq] = agora
            self._demanda_do_toque[uniq] = agora
            touch = self._touch.get(uniq)
        self._garantir_manutencao()
        if touch is None:
            return None
        try:
            estado = touch.touch_state()
        except Exception:
            return None
        clicado = False
        with contextlib.suppress(Exception):
            clicado = bool(touch.regions_pressed())
        return estado, clicado

    def _empurrar_o_jogo(self) -> bool:
        """Pergunta se há jogo e deposita a resposta no REGISTRO, que o report lê a ~250 Hz."""
        from hefesto_dualsense4unix.core.virtual_motion import REGISTRO

        jogo = False
        if callable(self._ha_jogo):
            try:
                jogo = bool(self._ha_jogo())
            except Exception as exc:
                logger.debug("sensor_hub_jogo_nao_respondeu", err=str(exc))
        REGISTRO.definir_jogo(jogo)
        return jogo

    def _toque_querido(
        self,
        uniq: str,
        agora: float,
        vistos: dict[str, float],
        segurados: dict[str, float],
        jogo: bool,
    ) -> bool:
        """A UNIÃO das demandas pelo nó «Touchpad» de `uniq`; quem pede não solta o que outro pediu.

        1. o toque roteado (cursor ou zonas), renovado a cada tique;
        2. o dedo que o servidor DSU segura para o emulador;
        3. o Desligado desta peça, com jogo aberto;
        4. o Ligado com jogo aberto cuja configuração própria de toque recebe o dedo pelo vpad.
        """
        from hefesto_dualsense4unix.core.virtual_motion import REGISTRO

        roteado = uniq in vistos and agora - vistos[uniq] <= self._TOQUE_ROTEADO_TTL_S
        dsu = uniq in segurados and agora - segurados[uniq] <= self._DEDO_SEGURADO_TTL_S
        calado = REGISTRO.toque_calado(uniq)
        ao_jogo = False
        if jogo and REGISTRO.touchpad_ligado(uniq) and callable(self._toque_proprio_do_jogo):
            try:
                ao_jogo = bool(self._toque_proprio_do_jogo(uniq))
            except Exception as exc:
                logger.debug("sensor_hub_toque_proprio_falhou", identity=uniq, err=str(exc))
        return roteado or dsu or calado or ao_jogo

    def _reconciliar_grabs_do_toque(self, agora: float) -> None:
        """O nó do touchpad fica GRABADO enquanto alguma demanda (`_toque_querido`) o quiser."""
        from hefesto_dualsense4unix.core.virtual_motion import REGISTRO

        jogo = REGISTRO.jogo_aberto()
        with self._lock:
            leitores = dict(self._touch)
            vistos = dict(self._demanda_do_toque)
            segurados = dict(self._dedo_segurado)
            self._demanda_do_toque = {
                u: t for u, t in vistos.items() if agora - t <= self._TOQUE_ROTEADO_TTL_S
            }
            self._dedo_segurado = {
                u: t for u, t in segurados.items() if agora - t <= self._DEDO_SEGURADO_TTL_S
            }
        for uniq, leitor in leitores.items():
            querido = self._toque_querido(uniq, agora, vistos, segurados, jogo)
            aplicar = getattr(leitor, "set_grab", None)
            if not callable(aplicar):
                continue
            estado = getattr(leitor, "grab_state", "off")
            if querido and estado == "held":
                continue
            if not querido and estado in ("off", "failed"):
                continue
            with contextlib.suppress(Exception):
                aplicar(querido)

    def grab_do_toque(self, uniq: str) -> str:
        """Estado do EVIOCGRAB no nó «Touchpad» de `uniq`: `off|pending|held|failed|sem_reader`."""
        from hefesto_dualsense4unix.core.virtual_motion import chave_de_sensor

        alvo = chave_de_sensor(uniq)
        with self._lock:
            leitor = next((r for u, r in self._touch.items() if chave_de_sensor(u) == alvo), None)
        if leitor is None:
            return "sem_reader"
        estado = getattr(leitor, "grab_state", None)
        return str(estado) if isinstance(estado, str) else "off"


__all__ = ["AmostraDoDsu", "SensorHub"]
