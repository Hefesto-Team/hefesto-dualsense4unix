"""sensor_hub.py — giroscópio, acelerômetro, touchpad e ENTRADAS por controle.

Quem consome: o enriquecimento do `state_full` (`ipc_handlers`), que roda no
event loop do daemon a 10 Hz enquanto a GUI está aberta. Quem produz: um
`MotionSensorReader`, um `TouchpadReader` e — desde STATUS-04 — um
`EvdevReader` PASSIVO por controle, cada um na sua thread de evdev.

**O terceiro tipo nasceu em 04/09/2026 e é a entrega STATUS-04**, escrita em
17/07/2026 e adiada com razão medida: *"co-op é DEFAULT ON (…) no estado
normal da máquina dela, TODO secundário já tem reader e o card dele já terá
inputs só com STATUS-01/02. O buraco real é o **modo Nativo** (…) e
emulação-off"*. A aposta continua verdadeira — medido em 04/09/2026 com os
dois DualSense dela em USB e co-op ligado, os DOIS controles publicam
`inputs` com giro, acelerômetro e touchpad, e este hub não abre reader de
gamepad NENHUM. O que ela fecha é o buraco: nos modos em que o co-op está
desmontado (Nativo, emulação off, suspensão por Steam Input) o secundário
ficava com `inputs: None` e METADE DA MESA emudecia por desenho.

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

**O reader do GAMEPAD nunca faz `set_grab`, e é onde isso deixa de ser
detalhe.** Um `EVIOCGRAB` no node do CONTROLE tornaria o daemon leitor
exclusivo e o JOGO pararia de ver o controle — seria trocar um card mudo por
um controle morto. Observar um node que ninguém grabou não disputa nada: o
evdev entrega o mesmo evento a todos os fds abertos, e isto não é hidraw
(a armadilha nº 3 desta casa, o instrumento que briga com o produto, mora na
outra camada).

**O reader de MOTION é a exceção, e ela nasceu deliberada em 04/09/2026**
(SENSOR-DE-VERDADE-01, decisão dela: *"ele tem que funcionar de verdade.
ambos independente do modo e da mascara"*). <!-- noqa-acento: citação literal dela -->
O node "Motion Sensors" é SEPARADO do node do controle: grabá-lo esconde o
giro e o acelerômetro de quem lê evdev **sem tocar um único botão** — os
gatilhos, os analógicos e o d-pad continuam chegando ao jogo pelo outro node.
É o oposto do caso acima, e é por isso que a mesma máquina de grab serve aos
dois com sinais trocados. Só grabamos quando ELA desligou um sensor; sem
pedido dela, este hub continua sendo um observador que não disputa nada
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
    #: Os três tipos de leitor administrados. "gamepad" (STATUS-04) tem
    #: registro de demanda PRÓPRIO — ver :meth:`entradas`.
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
        self._gamepad_factory = gamepad_factory or self._gamepad_reader_real
        self._descobrir_motion = descobrir_motion or self._descobrir_motion_real
        self._descobrir_touch = descobrir_touch or self._descobrir_touch_real
        self._descobrir_gamepad = descobrir_gamepad or self._descobrir_gamepad_real

        self._lock = threading.RLock()
        #: Demanda dos SENSORES (`leitura`) — vale para motion e touchpad.
        self._demanda: dict[str, float] = {}
        #: Demanda das ENTRADAS (`entradas`), separada de propósito: o
        #: `state_full` pede sensor de TODO controle que já tem `inputs`, e
        #: pediria um reader de gamepad inútil para cada um deles. Aqui só
        #: entra quem ficaria mudo sem ele.
        self._demanda_entradas: dict[str, float] = {}
        self._motion: dict[str, Any] = {}
        self._touch: dict[str, Any] = {}
        self._gamepad: dict[str, Any] = {}
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
                estado = touch.touch_state()
                out["touchpad"] = {
                    "touching": bool(estado.touching),
                    "x": int(estado.x),
                    "y": int(estado.y),
                    "width": int(estado.largura),
                    "height": int(estado.altura),
                }
        return out

    def entradas(self, uniq: str) -> dict[str, Any] | None:
        """Analógicos, gatilhos e botões de `uniq` agora; `None` sem reader.

        STATUS-04. Mesmo contrato de `leitura`: registra a demanda (é o que
        mantém o reader vivo), só toca dicionário sob lock e NUNCA levanta.
        A primeira chamada devolve `None` — o reader nasce na volta seguinte
        da thread de manutenção, porque a descoberta é cara e o event loop é
        único (regra 1 do módulo).

        **`None` não é falha, é a verdade daquele instante**, e a interface já
        sabe lê-la: é o mesmo `None` que o card desenha como "—". O erro que
        esta função não pode cometer é o contrário — devolver os `128` de
        fábrica de um reader que nunca vai receber evento. Ver o cabeçalho do
        módulo: quem decide QUANDO perguntar é o `ipc_handlers`, e ele só
        pergunta por controle que não tem outra fonte.
        """
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
        desligados = self._sensores_desligados()
        with self._lock:
            vivos_sensores = self._podar(self._demanda, agora)
            self._demanda = {
                u: t for u, t in self._demanda.items() if u in vivos_sensores
            }
            vivos_entradas = self._podar(self._demanda_entradas, agora)
            self._demanda_entradas = {
                u: t for u, t in self._demanda_entradas.items() if u in vivos_entradas
            }
            desejados: dict[str, set[str]] = {
                # SENSOR-DE-VERDADE-01 — A LINHA QUE FAZ O INTERRUPTOR DURAR.
                # Quem tem sensor desligado entra na lista dos motion MESMO sem
                # ninguém pedir leitura: é o reader do nó "Motion Sensors" que
                # segura o EVIOCGRAB, e sem esta união o TTL de 5 s derrubaria
                # o reader — e com ele o grab — CINCO SEGUNDOS depois de ela
                # fechar a janela. O interruptor se desligaria sozinho, calado,
                # e a próxima tela ainda diria "desligado".
                #
                # Só o `motion`: o touchpad não tem interruptor e manter um
                # reader dele de graça seria uma thread por controle, o dia
                # inteiro, pelo nada.
                "motion": vivos_sensores | desligados,
                "touchpad": vivos_sensores,
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

        # O que já foi dado como inexistente só volta à fila quando
        # `/dev/input` muda — replug, hotplug, re-enumeração pós-storm.
        if self._input_dir_mudou():
            sem_node = set()
            with self._lock:
                self._sem_node = set()
        novos = faltando - sem_node
        if novos:
            self._abrir_readers(novos)
        self._reconciliar_grabs(desligados)

    # -- O BRAÇO EVDEV do interruptor de sensor (SENSOR-DE-VERDADE-01) -----

    def _sensores_desligados(self) -> set[str]:
        """Os `uniq` (na grafia da DESCOBERTA) com algum sensor desligado.

        Duas grafias da mesma peça convivem nesta casa: o `uniq` do evdev vem
        com dois-pontos (`aa:bb:cc:00:00:01`) e a chave do perfil vem sem
        (`aabbcc000001`). O registro indexa pela forma normalizada; este hub
        precisa da forma que os DESCOBRIDORES usam, senão pediria reader para
        um endereço que `/dev/input` não conhece — e o interruptor daquela peça
        nunca abriria nó nenhum.

        A DESCOBERTA SÓ É PAGA quando há sensor desligado de peça sem reader —
        o caso raro. No caso normal (dicionário vazio) o custo é um `if`, e
        essa é a regra 1 deste módulo: a enumeração de `/dev/input` custa
        10-40 ms e não pode entrar no ritmo de 1 s por precaução.

        Import tardio pela mesma razão de todos os outros daqui.
        """
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
        if faltando:
            for uniq in self._chamar_descobridor(self._descobrir_motion):
                if chave_de_sensor(uniq) in faltando:
                    achados.add(uniq)
        return achados

    def _reconciliar_grabs(self, desligados: set[str]) -> None:
        """O nó "Motion Sensors" fica GRABADO enquanto houver sensor desligado.

        **É a metade que a medição de 04/09/2026 obrigou a existir**, e ela
        alcança o que o filtro do report não alcança: o consumidor que lê o nó
        evdev direto (`evtest`, emulador com backend evdev). O SDL não lê esse
        nó — mede-se em `core/virtual_motion`, no cabeçalho —, então nenhum dos
        dois braços sozinho é o interruptor: são os dois.

        POR QUE O NÓ INTEIRO, e não um sensor por vez: giroscópio e
        acelerômetro viajam no MESMO nó (`ABS_RX/RY/RZ` e `ABS_X/Y/Z`,
        `hid-playstation.c`), e o EVIOCGRAB é do descritor de arquivo, não do
        eixo. Desligar UM esconde os dois de quem lê evdev — e é por isso que a
        resposta do `sensor.set` DIZ isso, em vez de deixar a tela prometer
        precisão que o kernel não oferece. O braço do report, esse sim, separa
        os dois byte a byte.

        O grab não some quando a GUI fecha: quem mantém o reader vivo é a
        união lá em cima. E não some no replug nem na troca de máscara: o
        `_reapply_grab` do loop o reaplica ao reabrir o nó.
        """
        with self._lock:
            readers = dict(self._motion)
        for uniq, reader in readers.items():
            querido = uniq in desligados
            aplicar = getattr(reader, "set_grab", None)
            if not callable(aplicar):
                continue  # dublê de teste sem grab: nada a fazer, e sem erro
            estado = getattr(reader, "grab_state", "off")
            if querido and estado == "held":
                continue
            if not querido and estado in ("off", "failed"):
                continue
            with contextlib.suppress(Exception):
                aplicar(querido)

    def grab_do_movimento(self, uniq: str) -> str:
        """Estado do EVIOCGRAB no nó de movimento de `uniq`.

        `off | pending | held | failed`, e `sem_reader` quando não há nó aberto
        para aquela peça. Quem chama é o `sensor.set`, para dizer na resposta
        **qual metade do interruptor pegou** — a lição de 04/09/2026: quando o
        instrumento e o aparelho discordam, o aparelho ganha, e a única forma
        de saber é PERGUNTAR ao aparelho em vez de afirmar pelo desenho.

        Aceita as DUAS grafias do endereço (com e sem dois-pontos): quem
        pergunta é o handler do IPC, que já converteu para a chave do perfil,
        e o card, que tem a do evdev. Casar só uma delas devolveria
        `sem_reader` sobre um nó grabado — o instrumento mentindo de novo.
        """
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
            watch.poll()  # baseline; a 1ª volta já tenta abrir de qualquer jeito
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
        # SÓ o tipo que falta paga a descoberta. Cada descobridor abre todos os
        # nodes de `/dev/input` (~10-40 ms — PERF-MULTI-CONTROLLER-01) e o caso
        # normal é faltar um tipo só; pagar os três aqui era desperdício desde
        # antes do "gamepad", e com ele passaria a custar 50% a mais.
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
    def _gamepad_reader_real(uniq: str, node: Any) -> Any:
        """O reader PASSIVO de STATUS-04 — e `set_grab` nunca é chamado.

        `EvdevReader` nasce com `_grab=False` e só graba por pedido explícito
        (`set_grab`); a ausência da chamada aqui é a entrega, não um esquecimento.
        Com grab, o daemon viraria leitor exclusivo do controle e o JOGO
        deixaria de vê-lo — o card acenderia à custa da partida dela.
        """
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
        """MAC -> node de gamepad, reusando a descoberta ÚNICA da casa.

        `discover_dualsense_evdevs()` e não uma enumeração por VID/PID: o
        filtro `_is_virtual_evdev` dela é o que impede o hub de abrir o
        PRÓPRIO vpad do daemon — o fallback uinput cria um `054c:0ce6`
        idêntico ao físico, e o card viraria eco do daemon.
        """
        from hefesto_dualsense4unix.core.evdev_reader import discover_dualsense_evdevs

        return dict(discover_dualsense_evdevs())


__all__ = ["SensorHub"]
