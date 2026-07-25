"""sensor_hub.py — giroscópio e touchpad POR CONTROLE, sob demanda (S2).

Quem consome: o enriquecimento do `state_full` (`ipc_handlers`), que roda no
event loop do daemon a 10 Hz enquanto a GUI está aberta. Quem produz: um
`MotionSensorReader` e um `TouchpadReader` por controle, cada um na sua
thread de evdev.

As três regras que moldaram este desenho:

1. **A descoberta é cara e o event loop é único.** Enumerar `/dev/input`
   abre TODOS os nodes (~10-40 ms — a lição PERF-MULTI-CONTROLLER-01). Fazer
   isso no `state_full` congelaria o daemon inteiro dez vezes por segundo.
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
"""
from __future__ import annotations

import contextlib
import threading
import time
from collections.abc import Callable
from typing import Any, ClassVar

from hefesto_dualsense4unix.utils.logging_config import get_logger

logger = get_logger(__name__)


class SensorHub:
    """Registro de leitores de sensores por controle, movido a demanda."""

    #: Sem pedido por este tempo, os readers do controle são desligados. Cinco
    #: segundos cobrem com folga o tick de 10 Hz da GUI e ainda derrubam tudo
    #: em poucos segundos quando ela fecha.
    _DEMANDA_TTL_S: ClassVar[float] = 5.0
    #: Período da thread de manutenção. Um segundo é imperceptível para quem
    #: acabou de abrir a aba e barato o bastante para rodar o dia inteiro
    #: (a volta é um comparativo de conjuntos quando nada mudou).
    _MANUTENCAO_INTERVALO_S: ClassVar[float] = 1.0

    def __init__(
        self,
        *,
        motion_factory: Callable[[str, Any], Any] | None = None,
        touch_factory: Callable[[str, Any], Any] | None = None,
        descobrir_motion: Callable[[], dict[str, Any]] | None = None,
        descobrir_touch: Callable[[], dict[str, Any]] | None = None,
        relogio: Callable[[], float] | None = None,
        auto_manutencao: bool = True,
    ) -> None:
        """As fábricas e os descobridores são injetáveis para teste.

        Sem hardware não há como abrir um node de verdade; com dublês, toda
        a máquina de demanda/expiração/reconciliação fica exercitável.

        `auto_manutencao=False` deixa a thread de fora e o teste chama
        `reconciliar()` na mão — sem isso, a thread rodaria a mesma
        reconciliação em paralelo e o teste viraria uma corrida.
        """
        self._relogio = relogio or time.monotonic
        self._auto_manutencao = auto_manutencao
        self._motion_factory = motion_factory or self._motion_reader_real
        self._touch_factory = touch_factory or self._touch_reader_real
        self._descobrir_motion = descobrir_motion or self._descobrir_motion_real
        self._descobrir_touch = descobrir_touch or self._descobrir_touch_real

        self._lock = threading.RLock()
        self._demanda: dict[str, float] = {}
        self._motion: dict[str, Any] = {}
        self._touch: dict[str, Any] = {}
        #: Pares `(identidade, tipo)` já procurados sem sucesso. Por TIPO
        #: porque os dois nodes são independentes: um controle pode ter
        #: touchpad e não ter motion, e marcar só a identidade faria o hub
        #: varrer `/dev/input` inteiro a cada segundo por causa do que falta.
        #: Só saem daqui quando `/dev/input` muda de verdade.
        self._sem_node: set[tuple[str, str]] = set()
        self._watch: Any = None
        self._parar = threading.Event()
        self._thread: threading.Thread | None = None

    # -- API consumida pelo event loop (barata por contrato) --------------

    def leitura(self, uniq: str) -> dict[str, Any]:
        """Sensores conhecidos de `uniq` agora; `{}` enquanto não houver.

        Registra a demanda (é o que mantém os readers vivos) e devolve só o
        que EXISTE: sem reader de motion não há chave `gyro`, sem reader de
        touchpad não há chave `touchpad`. Nunca levanta — o `state_full` não
        pode cair por causa de um sensor.
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
        if touch is not None:
            with contextlib.suppress(Exception):
                estado = touch.touch_state()
                out["touchpad"] = {
                    "touching": bool(estado.touching),
                    "x": int(estado.x),
                    "y": int(estado.y),
                    "width": int(estado.largura),
                    "height": int(estado.altura),
                }
        return out

    def stop_all(self) -> None:
        """Para a manutenção e todos os readers. Idempotente."""
        self._parar.set()
        thread = self._thread
        self._thread = None
        if thread is not None:
            thread.join(timeout=2.0)
        with self._lock:
            readers = list(self._motion.values()) + list(self._touch.values())
            self._motion.clear()
            self._touch.clear()
            self._demanda.clear()
        for reader in readers:
            with contextlib.suppress(Exception):
                reader.stop()

    # -- Thread de manutenção --------------------------------------------

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
            except Exception as exc:  # nunca derruba a thread
                logger.debug("sensor_hub_reconciliacao_falhou", err=str(exc))
            self._parar.wait(self._MANUTENCAO_INTERVALO_S)

    def reconciliar(self) -> None:
        """Casa os readers vivos com a demanda atual. Roda FORA do event loop.

        Público de propósito: é o passo que o teste chama direto para
        exercitar nascimento e morte de reader sem depender de timing de
        thread.
        """
        agora = self._relogio()
        with self._lock:
            desejados = {
                uniq
                for uniq, visto in self._demanda.items()
                if (agora - visto) <= self._DEMANDA_TTL_S
            }
            self._demanda = {u: t for u, t in self._demanda.items() if u in desejados}
            sobrando = [
                (uniq, tipo)
                for tipo in ("motion", "touchpad")
                for uniq in list(self._mapa(tipo))
                if uniq not in desejados
            ]
            faltando = {
                (uniq, tipo)
                for tipo in ("motion", "touchpad")
                for uniq in desejados
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

        # O que já foi dado como inexistente só volta à fila quando
        # `/dev/input` muda — replug, hotplug, re-enumeração pós-storm.
        if self._input_dir_mudou():
            sem_node = set()
            with self._lock:
                self._sem_node = set()
        novos = faltando - sem_node
        if novos:
            self._abrir_readers(novos)

    def _mapa(self, tipo: str) -> dict[str, Any]:
        """Registro de readers do `tipo` ("motion" | "touchpad")."""
        return self._motion if tipo == "motion" else self._touch

    def _input_dir_mudou(self) -> bool:
        """True se `/dev/input` mudou desde a última volta (barato, ~µs)."""
        watch = self._watch
        if watch is None:
            from hefesto_dualsense4unix.core.evdev_reader import InputDirWatch

            watch = InputDirWatch()
            self._watch = watch
            watch.poll()  # baseline; a 1ª volta já tenta abrir de qualquer jeito
            return True
        resultado = watch.poll()
        return bool(resultado)

    def _abrir_readers(self, pendentes: set[tuple[str, str]]) -> None:
        """Cria e inicia os readers que faltam (descoberta cara mora aqui)."""
        nodes = {
            "motion": self._chamar_descobridor(self._descobrir_motion),
            "touchpad": self._chamar_descobridor(self._descobrir_touch),
        }
        fabricas = {
            "motion": self._motion_factory,
            "touchpad": self._touch_factory,
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
        """Abre UM reader; False quando este controle não tem esse node.

        O `node` já descoberto viaja para a fábrica DE PROPÓSITO: o
        construtor dos readers re-localiza o device quando não recebe path,
        e isso é uma varredura completa de `/dev/input` por reader (medido:
        ~150-200 ms cada, com 4 readers virava ~1,8 s para o painel acender).
        A partir daqui o reader se vira sozinho — ao reconectar ele usa o
        próprio finder, que é onde a re-localização faz sentido.
        """
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
        if anterior is not None:  # corrida improvável: nunca deixa órfão
            with contextlib.suppress(Exception):
                anterior.stop()
        logger.info("sensor_hub_reader_iniciado", identity=uniq, tipo=tipo)
        return True

    # -- Fábricas/descobridores reais (isolados para o teste substituir) ---

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


__all__ = ["SensorHub"]
