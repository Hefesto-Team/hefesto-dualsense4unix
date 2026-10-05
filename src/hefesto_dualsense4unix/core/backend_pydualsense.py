"""Backend real usando `pydualsense` para falar HID com o DualSense.

Thin adapter: traduz chamadas da `IController` para a API do pydualsense e
converte estado interno em `ControllerState` imutável. Mantém intencionalmente
sem lógica de negócio — facilita troca do backend no futuro (ADR-001).

FEAT-DSX-MULTI-CONTROLLER-01: suporta N DualSense conectados ao mesmo tempo.
A `pydualsense` NÃO é multi-device nativamente — `pydualsense.__find_device`
(`# TODO: implement multiple controllers working`) abre o controle por VID/PID
e fica com "o último enumerado". Para abrir cada controle de forma
determinística, usamos uma subclasse (`_PinnedPyDualSense`) que sobrescreve o
`__find_device` manglado e abre por `path` (hidraw) via `hidapi.Device`. Assim:

  - OUTPUT (gatilhos, lightbar, rumble, LEDs de player, LED do mic) é aplicado
    a TODOS os controles (fan-out) e o "perfil ativo" é cacheado como estado
    desejado POR CONTROLE (PERFIL-01/4P-01: `_desired_default` broadcast +
    `_desired_by_uniq` keyed por MAC) para ser re-aplicado — com MERGE POR
    CAMPO — a um controle plugado em runtime (hotplug-in).
  - INPUT/EMULAÇÃO permanece SÓ no controle PRIMÁRIO (o evdev e o `read_state`
    seguem single-instance; o `_ds` aponta para o primário). 100% compatível
    com o caso de 1 controle.
"""
from __future__ import annotations

import contextlib
import fcntl
import os
import sys
import threading
import time
from contextlib import AbstractContextManager
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, Any

from pydualsense import pydualsense
from pydualsense.enums import ConnectionType
from pydualsense.pydualsense import DSAudio, DSBattery, DSLight, DSState, DSTrigger

from hefesto_dualsense4unix.core import ds_output_report as rep
from hefesto_dualsense4unix.core.controller import (
    ControllerState,
    IController,
    OutputSpec,
    ResultadoDeSaida,
    Side,
    Transport,
    TriggerEffect,
)
from hefesto_dualsense4unix.core.evdev_reader import (
    DUALSENSE_PIDS,
    DUALSENSE_VENDOR,
    EvdevReader,
)
from hefesto_dualsense4unix.core.led_control import (
    DA_MAO,
    DA_PALETA,
    DO_BROADCAST,
    DO_GLOBAL,
    LEGADO,
    LedSettings,
    PecaDaMesa,
    cores_sem_colisao,
    degrau_do_brilho_das_luzes,
    reescalar,
)
from hefesto_dualsense4unix.core.speaker_scale import volume_do_percentual

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable, Iterator, Mapping, Sequence

from hefesto_dualsense4unix.utils.logging_config import get_logger

logger = get_logger(__name__)

#: PID do DualSense Edge (os demais PIDs em `DUALSENSE_PIDS` são o DualSense
DUALSENSE_EDGE_PID = 0x0DF2

KERNEL_DEFAULT_BLUE: tuple[int, int, int] = (0, 0, 128)

#: olho durante uma partida. O que ela comprou com isso: dá para CONTAR as três
#: e para LER a cor, que é a única coisa que o aviso tem a dizer. Um aviso que
#: pisca rápido demais vira um susto sem mensagem.
#:
AVISO_PISCADAS = 3
AVISO_ACESO_S = 0.15
AVISO_APAGADO_S = 0.12
AVISO_APAGADO: tuple[int, int, int] = (0, 0, 0)

GAME_TRIGGER_BLOCK_LEN = 11

#: não passa por este teto: já é rate-limitada pela histerese de 30s do sinal.
DEFEND_DISPLAY_MIN_INTERVAL_S = 30.0

_CALIBRATION_FEATURE_ID = 0x05
_CALIBRATION_FEATURE_SIZE = 41


def _read_feature_via_hidraw(
    path: str,
    report_id: int,
    size: int,
    opener: Callable[[str], int] | None = None,
) -> bytes:
    """GET_REPORT de feature via HIDIOCGFEATURE num fd efêmero (GYRO-01)."""
    fd = opener(path) if opener is not None else os.open(path, os.O_RDWR)
    try:
        buf = bytearray(size)
        buf[0] = report_id
        request = (3 << 30) | (size << 16) | (ord("H") << 8) | 0x07
        ret = fcntl.ioctl(fd, request, buf, True)
        return bytes(buf[:ret]) if ret > 0 else b""
    finally:
        os.close(fd)


_VPAD_PHYS = "hefesto-vpad"
_VPAD_UNIQ_PREFIX = "02fe"


def _hidraw_uevent(node: str) -> dict[str, str]:
    """Pares chave=valor do uevent do device HID pai do hidraw ({} se ilegível)."""
    try:
        with open(
            os.path.join(RAIZ_CLASS_HIDRAW, node, "device", "uevent"),
            encoding="utf-8",
            errors="replace",
        ) as fh:
            raw = fh.read()
    except OSError:
        return {}
    pares: dict[str, str] = {}
    for linha in raw.splitlines():
        chave, sep, valor = linha.partition("=")
        if sep:
            pares[chave] = valor
    return pares


def _is_virtual_hidraw(path: bytes) -> bool:
    """True se o hidraw é do NOSSO vpad uhid, não de controle físico.

    Espelha o `_is_virtual_evdev` do `evdev_reader` — e pela mesma razão CRÍTICA:
    o vpad do SPRINT-UHID-VPAD-01 nasce com VID/PID/bus idênticos ao controle
    real (é o que faz o `hid_playstation` fazer bind nele) e, ao contrário do
    vpad de uinput, tem **hidraw de verdade**. Sem este filtro o daemon adota o
    PRÓPRIO vpad como se fosse mais um controle físico — feedback loop (o daemon
    lendo a própria saída) e "3 controles" com dois na mesa.

    Medido ao vivo antes do filtro: com o vpad no ar, o enumerate devolvia
    ``('02:fe:00:00:00:02', b'/dev/hidraw7', False)`` — o MAC que nós forjamos.

    BLUEZ-UHID-01 (2026-07-19): morar sob `/sys/devices/virtual/misc/uhid/`
    DEIXOU de implicar "nosso vpad" — com BlueZ ≥5.73 (UserspaceHID default) o
    bluetoothd cria os HIDs dos controles BT FÍSICOS via /dev/uhid, no mesmo
    subtree. Medido ao vivo com o backport 5.85: os 4 controles BT da mesa
    ficaram invisíveis ao daemon (`connected: False` com 4 hidraws saudáveis).
    O critério agora é a IDENTIDADE do vpad no uevent do pai HID — HID_PHYS
    `hefesto-vpad` (blueprint) ou HID_UNIQ com prefixo 02:fe — alinhado à regra
    do projeto de validar pelo uevent do pai HID imediato, nunca por topologia.
    uevent ilegível sob o subtree virtual → True: na dúvida, o risco maior é o
    feedback loop de auto-adoção (o retry do reconcile cobre o falso-positivo).
    """
    node = os.path.basename(path.decode("utf-8", "replace"))
    if not node.startswith("hidraw"):
        return False
    try:
        destino = os.path.realpath(os.path.join(RAIZ_CLASS_HIDRAW, node, "device"))
    except OSError:  # pragma: no cover - sysfs some sob replug
        return False
    if "/devices/virtual/" not in destino:
        return False
    uevent = _hidraw_uevent(node)
    if not uevent:
        return True
    phys = uevent.get("HID_PHYS", "")
    uniq = uevent.get("HID_UNIQ", "").lower().replace(":", "")
    return phys == _VPAD_PHYS or uniq.startswith(_VPAD_UNIQ_PREFIX)

#: e, em certos estados degenerados do USB (driver kernel hid_playstation
#: contendendo o device, hidraw com handle órfão de daemon anterior, hub em
#: low-power-state), pode entrar em `D (disk sleep)` no kernel — nem SIGKILL
#: mata. Envolvemos em thread + futures com timeout: se passar do prazo, o
#: backend é marcado como offline-OK e a próxima tentativa do reconnect_loop
#: cobre. A thread em D-state é abandonada (vaza recurso, mas o daemon segue
#: vivo e funcional). 5s é compromisso entre cobrir o caso patológico e não
#: pesar no boot normal (`init()` saudável retorna em <300ms).
INIT_TIMEOUT_SEC: float = float(os.environ.get("HEFESTO_DUALSENSE4UNIX_INIT_TIMEOUT_SEC", "5"))

#: saturando o controlador USB compartilhado — e o adaptador Bluetooth vive no
#: (`DualSense input CRC's check failed`) e matando o output do controle BT.
REPORT_THREAD_THROTTLE_SEC: float = float(
    os.environ.get("HEFESTO_DUALSENSE4UNIX_REPORT_THROTTLE_SEC", "0.008")
)

REPORT_THREAD_THROTTLE_MAX_SEC: float = 0.032

#: 64 leituras esvaziam uma fila cheia e mais um report que chegue no meio. Com
LEITURAS_POR_VOLTA: int = 64

ESPERA_DA_VOLTA_VAZIA_SEM_THROTTLE_SEC: float = 0.001

OUT_REPORT_KEEPALIVE_SEC: float = 0.5

OUT_REPORT_KEEPALIVE_CONFIRMACAO_SEC: float = 2.0

#: segundo inteiro sem report já é MUITO acima disso e rende, no máximo, uma
LEITURA_VAZIA_AVISO_SEC: float = 1.0

CLOSE_JOIN_TIMEOUT_SEC = 0.5

PRIMARIO_RESERVA_SEC: float = 30.0


#: áudio, na ORDEM de `_PinnedPyDualSense._volumes_audio`
#: (fone, alto-falante, microfone, roteamento).
_AUDIO_FLAG0_BITS = (0x10, 0x20, 0x40, 0x80)
_AUDIO_COMMON_OFFSETS = (4, 5, 6, 7)


_AUDIO_TETOS = (
    rep.TETO_HEADPHONE_VOLUME,
    rep.TETO_SPEAKER_VOLUME,
    rep.TETO_MIC_VOLUME,
    0xFF,
)


#: 1 kHz, o microfone do próprio DualSense como instrumento):
VOLUME_PADRAO_DO_SOM: int = volume_do_percentual(100)

#: daemon vivo, nos dois DualSense no cabo: ``rota=None`` nos dois, volume 102,
#: `profiles/manager.apply_speaker`.
ROTA_PADRAO_DO_SOM: int = rep.SAIDA_L_FONE_R_ALTO_FALANTE


def byte_do_volume_do_microfone(percentual: Any) -> int:
    """Porcentagem da tela (0-100) -> `common[6]`, o ganho de captura do aparelho.

    MIC-VOLUME-02 (09/09/2026). **A régua mora aqui e só aqui**, pela mesma
    razão que fez a do alto-falante virar módulo próprio: a grandeza é falada
    por três superfícies (o `mic.volume.set` do IPC, o applier de perfil e o
    ensaio da bancada), e duas contas para a mesma grandeza é a classe de
    defeito que esta casa mais paga.

    **O teto é LIDO, não digitado**: `rep.TETO_MIC_VOLUME` (`0x40`), que é o
    mesmo número que o `hid-playstation` desta máquina anota ao NOMEAR o campo
    (`mic_volume`, comentário `0x0 - 0x40`). Um segundo `0x40` escrito aqui
    envelheceria no dia em que o primeiro mudasse.

    A CONTA É LINEAR, e a diferença em relação à do alto-falante é medição, não
    gosto: a curva do alto-falante foi levantada byte a byte em 01/08 (mudo até
    38, satura em 102), e a do microfone **ninguém levantou**. O que a bancada
    dela mediu em 09/09/2026 foi que o byte AGE — *"Deu certo. funciona"*,
    `docs/data/ensaios.csv`, `folha-mic-volume-o-byte-age-cabo-0909` —, e não
    onde ele fica mudo nem onde satura. Inventar uma curva aqui seria publicar
    como medida uma forma que ninguém viu; a linear é a única que não afirma
    nada além do teto.

    **0 % é ZERO e qualquer coisa acima de 0 % sai pelo menos em 1**, que é
    literalmente a regra que `core/speaker_scale.volume_do_percentual` já
    cobra do irmão: *"pedir 1 % e receber silêncio seria o defeito de novo, uma
    ponta do curso que não faz nada"*. A conta crua do enunciado da sprint
    (`v * 0x40 // 100`) devolve **0 para 1 %**, o que faria o número da tela
    dizer "um pouquinho" sobre um microfone mudo no aparelho.

    LIMITE DECLARADO, e é o mesmo do alto-falante: 64 passos de registrador
    para 101 valores de tela, logo há porcentagens vizinhas que caem no mesmo
    byte. Quem ler de volta o que mandou pode ver um ponto de diferença.
    """
    try:
        p = int(percentual)
    except (TypeError, ValueError):
        p = 0
    p = max(0, min(100, p))
    if p == 0:
        return 0
    return max(1, round(p * rep.TETO_MIC_VOLUME / 100))


def _escrever_led_do_mic(handle: pydualsense, aceso: bool) -> None:
    """Acende/apaga o LED do mudo TOMANDO A POSSE do byte (AUDIO-OWNER-01).

    Existe uma função em vez de uma chamada direta porque há dois caminhos de
    escrita (`set_mic_led` e o `_write_partial_output` do perfil/hotplug) e
    porque nem todo handle é um `_PinnedPyDualSense`: os dublês da suíte têm
    `audio.setMicrophoneLED` e não têm a posse. Sem a posse, o byte seria
    escrito e o bit de autorização nunca ligaria — o LED não acenderia.
    """
    tomar = getattr(handle, "set_microphone_led", None)
    if callable(tomar):
        tomar(bool(aceso))
        return
    handle.audio.setMicrophoneLED(bool(aceso))


def _byte_da_rota(handle: Any, rota: int | None) -> int | None:
    """O `common[7]` com a rota nova, preservando o caminho do microfone.

    SOM-ROTA-01. `None` devolve `None`, e o chamador entende isso como "não
    tome a posse deste byte" — que é o certo por omissão: o byte carrega a
    rota de saída (`OUTPUT_PATH_SEL`, bits 4-5) E o caminho do microfone
    (bits 0-3 e 6-7), e escrevê-lo inteiro com o número da rota apagaria o
    resto em silêncio.

    Com uma rota pedida, o valor VIGENTE do byte é a base — se já houver dono.
    Sem dono, a base é zero, que é o estado neutro dos bits do microfone.
    """
    if rota is None:
        return None
    # SOM-CANAL-01, REGRESSÃO MEDIDA em 02/08: a base era ZERO quando ninguém
    # tinha posse do byte — e zero apaga o `FORCE_INTERNAL_MIC`. O microfone do
    # controle parou de captar (o `parec` foi de 131072 bytes para ZERO) e
    # voltou assim que a posse foi devolvida.
    #
    # Não há como LER o `common[7]` que o firmware está usando: não existe
    # report de entrada nem feature que o devolva. Então a base é a mais
    # conservadora que se pode afirmar — o microfone INTERNO ligado, que é o
    # que este controle tem quando não há headset.
    vigente = rep.AUDIO_CONTROL_BASE_SEGURA
    volumes = getattr(handle, "_volumes_audio", None)
    if isinstance(volumes, list) and len(volumes) > 3 and volumes[3] is not None:
        vigente = int(volumes[3])
    limpo = vigente & ~rep.OUTPUT_PATH_SEL_MASK
    return limpo | ((int(rota) << rep.OUTPUT_PATH_SEL_SHIFT) & rep.OUTPUT_PATH_SEL_MASK)


def _clamp_u8(valor: Any, default: int) -> int:
    """Coerção defensiva para byte de report: 0..255, ou `default` se None/lixo."""
    if valor is None:
        return int(default) & 0xFF
    try:
        return max(0, min(255, int(valor)))
    except (TypeError, ValueError):
        return int(default) & 0xFF


def _bytes_que_sairam(escrito: Any) -> int | None:
    """Quantos bytes o fio disse ter escrito — ``None`` = **ele não disse**.

    ESCRITA-QUE-NAO-MEDE-01 (19/09/2026). O `hidapi` devolve um `int` de
    verdade: o número de bytes escritos, ou `-1` no erro. Só esse `int` é
    prova; qualquer outra coisa é ausência de resposta, e esta casa já decidiu
    o que fazer com ausência de dado — **não se acusa sem prova**. É a mesma
    disciplina do ``sondado_em is None`` do `core/escritor_cru.py`.

    Por que o teste é `isinstance` e não `int(...)`: em boa parte da suíte o
    `device` é um dublê, e `int(MagicMock())` devolve `1` — que compararia
    diferente do tamanho do quadro e faria TODA escrita de teste virar "curta".
    Uma acusação de escrita curta nascida de um dublê seria a mesma classe de
    defeito que esta função existe para curar, só com o sinal trocado.

    `bool` fica de fora de propósito: ele É `int` em Python, e um dublê que
    devolve `True` estaria dizendo "escrevi 1 byte" sem querer dizer isso.
    """
    if isinstance(escrito, bool) or not isinstance(escrito, int):
        return None
    return int(escrito)


def _escrita_completa(escrito: Any, pedidos: int) -> bool:
    """A escrita entregou os `pedidos` bytes inteiros?"""
    saidos = _bytes_que_sairam(escrito)
    return saidos is None or saidos == int(pedidos)


@dataclass
class _DesiredOutput:
    """Último output aplicado = "perfil ativo" materializado em HID."""

    trigger_left: TriggerEffect | None = None
    trigger_right: TriggerEffect | None = None
    led: tuple[int, int, int] | None = None
    player_leds: tuple[bool, bool, bool, bool, bool] | None = None
    mic_led: bool | None = None
    player_led_brightness: int | None = None


@dataclass(frozen=True)
class _ResolvidoDoDaemon:
    """O que `_resolvido_do_daemon` devolve: a saída e as três respostas que"""

    saida: _DesiredOutput
    cor_do_numero: tuple[int, int, int] | None
    procedencia: object
    numero: int | None
    cor_do_plastico: tuple[int, int, int] | None = None


_SEM_NUMERO = 1 << 30

_OUTPUT_FIELDS = (
    "trigger_left", "trigger_right", "led", "player_leds", "mic_led",
    "player_led_brightness",
)

_LAYER_PROFILE = "perfil"
_LAYER_USER = "usuaria"

_COOP_LAYER_FIELDS = ("player_leds",)

_CAMPOS_QUE_O_HEFESTO_NUMERA: frozenset[str] = frozenset({"player_leds"})

_CAMPOS_QUE_O_NATIVO_ESCREVE: frozenset[str] = frozenset(
    {"led", "player_leds", "player_led_brightness"}
)

PALETA_DE_JOGADOR_DO_SDL: frozenset[tuple[int, int, int]] = frozenset(
    {
        (0x00, 0x00, 0x40),
        (0x40, 0x00, 0x00),
        (0x00, 0x40, 0x00),
        (0x20, 0x00, 0x20),
        (0x20, 0x10, 0x00),
        (0x00, 0x10, 0x10),
        (0x10, 0x10, 0x10),
    }
)


def numeracao_do_jogo(campos: Mapping[str, Any]) -> frozenset[str]:
    """Os campos de uma réplica de exibição que são NÚMERO de jogador."""
    numero = {
        nome
        for nome, valor in campos.items()
        if nome in _CAMPOS_QUE_O_HEFESTO_NUMERA and valor is not None
    }
    cor = campos.get("led")
    if cor is not None:
        with contextlib.suppress(TypeError, ValueError):
            if tuple(int(c) for c in cor) in PALETA_DE_JOGADOR_DO_SDL:
                numero.add("led")
    return frozenset(numero)


#: Os dois modos do bloco de gatilho que o firmware lê como «sem efeito»: o `0x00`
#: e o `MODE_OFF` oficial da Sony (`0x05`).
_MODOS_DE_GATILHO_SEM_EFEITO = frozenset({0x00, 0x05})


def gatilho_do_jogo_sem_efeito(bloco: bytes) -> bool:
    """O bloco cru de gatilho que o jogo escreveu não faz nada no gatilho.

    É o modo «sem efeito» (`0x00` ou `0x05`) ou qualquer modo com os dez
    parâmetros em zero (força, zona e amplitude nulas): no gatilho os dois são
    a mesma coisa, nenhuma resistência.
    """
    if not bloco:
        return False
    return bloco[0] in _MODOS_DE_GATILHO_SEM_EFEITO or not any(bloco[1:])


def _spec_fields(spec: OutputSpec) -> dict[str, Any]:
    """Campos NÃO-None de um `OutputSpec` (o vocabulário parcial do PERFIL-01)."""
    return {
        name: getattr(spec, name)
        for name in _OUTPUT_FIELDS
        if getattr(spec, name) is not None
    }


def _rgb_do_perfil(cru: Sequence[int] | None) -> tuple[int, int, int] | None:
    """A cor global do perfil como tom (três bytes), ou `None` quando não é cor."""
    if cru is None:
        return None
    try:
        r, g, b = (int(c) for c in cru)
    except (TypeError, ValueError):
        return None
    if not all(0 <= c <= 255 for c in (r, g, b)) or (r, g, b) == (0, 0, 0):
        return None
    return (r, g, b)


def _merge_desired(default: _DesiredOutput, override: _DesiredOutput | None) -> _DesiredOutput:
    """MERGE POR CAMPO (PERFIL-01): campo do override quando não-None, senão o default."""
    if override is None:
        return default
    return _DesiredOutput(
        **{
            name: (
                getattr(override, name)
                if getattr(override, name) is not None
                else getattr(default, name)
            )
            for name in _OUTPUT_FIELDS
        }
    )


def _sem_os_campos(
    desired: _DesiredOutput, campos: frozenset[str]
) -> _DesiredOutput | None:
    """Cópia de `desired` sem os campos defendidos. None = não sobrou nada.

    A camada GAME passa por aqui antes de entrar no merge, sem a numeração do
    jogador (que é do Hefesto). Devolver `None` quando não sobrou campo é o que
    faz `_merged_desired_for_key` pular o `_merge_desired` — um merge com tudo
    em `None` seria no-op caro chamado a cada resolve, e esta função roda
    dentro do `_io_lock`.
    """
    if not campos:
        return desired
    restantes = {
        nome: getattr(desired, nome)
        for nome in _OUTPUT_FIELDS
        if nome not in campos and getattr(desired, nome) is not None
    }
    if not restantes:
        return None
    return _DesiredOutput(**restantes)


def _centered_stick_to_raw(value: Any) -> int:
    """Converte um eixo de stick da pydualsense (centrado em 0) para cru 0-255."""
    return max(0, min(255, int(value) + 128))


def _resolver_escopo(
    handles: dict[str, Any], alvo: str | None, *, broadcast: bool
) -> tuple[str | None, list[tuple[str, Any]], str | None]:
    """Resolve o escopo de UMA escrita de output. Chamar sob o `_io_lock`.

    Devolve `(escopo_do_registro, handles_a_escrever, alvo_ausente)`, e a razão
    de existir é a terceira posição: **ausência de destinatário não é "todo
    mundo"** (P4, 23/08/2026).

    Os três casos, e só há três:

    * `broadcast=True` **ou** sem alvo no seletor ("Todos") → escopo `None` (o
      default do perfil) e TODOS os handles. É o broadcast legítimo, e continua
      byte-idêntico ao que sempre foi.
    * alvo escolhido e PRESENTE → escopo = a key dele, um handle só.
    * alvo escolhido e AUSENTE (saiu da mesa entre o clique e a escrita, ou
      nunca voltou) → escopo = a key dele (o registro ainda vale: vira override
      por-uniq, "guardado para quando ele voltar") e **nenhum handle**. Quem
      chama não escreve em ninguém.

    **O que caducou, e por quê.** Até 23/08/2026 esta regra vivia copiada em
    três helpers (`_for_each`, `_for_each_com_key`, `_for_each_led`) e o
    terceiro caso caía no broadcast histórico, por escolha declarada da
    FEAT-DSX-CONTROLLER-SELECTOR-01 (*"1 handle morto não derruba os
    outros"*). A justificativa era de ROBUSTEZ, não de endereçamento — e o
    preço, medido em co-op (que nesta casa é sempre ligado): ela fixa 160/220
    no Controle 2, o Controle 2 desliga, e os motores que sacodem são os das
    OUTRAS pessoas na partida — com o daemon respondendo "aplicado" e o
    reassert insistindo a 5 Hz até alguém clicar "Parar". A casa já tinha
    decidido o contrário em dois lugares (`subsystems/rumble.py`: *"Dono
    ausente da mesa é NO-OP, não broadcast"*; `apply_output_for`, que devolve
    `"registrado"`) — aqui o broadcast era a exceção sobrevivente, não a regra.

    **É função de módulo, não método, de propósito:** os dublês de backend dos
    testes de LED tomam emprestados os métodos REAIS do produto (`_for_each_led`
    e companhia) num objeto mínimo — o instrumento tem de ser o do produto. Uma
    dependência nova em `self` quebraria todos eles de uma vez.
    """
    if broadcast or alvo is None:
        return None, list(handles.items()), None
    handle = handles.get(alvo)
    if handle is None:
        return alvo, [], alvo
    return alvo, [(alvo, handle)], None


def _casar_key(handles: dict[str, Any], uniq: str) -> str | None:
    """Key do handle endereçada por `uniq` — MAC 12-hex OU a própria key.

    P4 (23/08/2026): `enviar_release_leds` indexava `handles` com o `uniq` CRU,
    e o `uniq` que chega do IPC (`lightbar.reset`) é o MAC 12-hex, enquanto a
    key do handle é "AA:BB:CC:...". A busca nunca casava: um controle
    CONECTADO devolvia `{}`, que o docstring de lá manda ler como "nenhum
    handle aberto". Falha segura, mas é instrumento mentindo — e o instrumento
    mente mais que o produto é regra desta casa.

    Aceita as duas formas porque os dois chamadores existem: o IPC manda o
    12-hex, os testes de bancada mandam a key.
    """
    if uniq in handles:
        return uniq
    from hefesto_dualsense4unix.core.sysfs_leds import norm_mac

    procurado = norm_mac(uniq)
    if procurado is None or len(procurado) != 12:
        return None
    for key in handles:
        normalizada = norm_mac(key)
        if normalizada is not None and normalizada == procurado:
            return key
    return None


def _relogio_da_borda() -> float:
    """O relógio que carimba o aperto do botão do microfone. UM ponto, por régua."""
    return time.monotonic()


def _hid_set_nonblocking(dispositivo: Any) -> None:
    """`hid_set_nonblocking(dev, 1)`: o `read` sem prazo do handle para de esperar.

    O-BOTAO-DO-MIC-CHEGA-NA-HORA-01 (29/09/2026). O `hidapi.Device(path=...)`
    nasce com `blocking=True` (`hidapi.py:221`), e o `read(n)` cai no `hid_read`,
    que obedece a esse modo (`:300-306`): com a fila vazia, ele espera o próximo
    report. O wrapper só chama `hid_set_nonblocking` no construtor
    (`blocking=False`, `:257`), e o `init()` do upstream PRECISA da espera, na
    única leitura que descobre o transporte (`determineConnectionType`). Por
    isso o modo muda aqui, uma vez, na thread do handle, depois do `init()`.

    No hidraw o modo é só um campo da estrutura (`dev->blocking`,
    `hid.c:1277-1283`, lido na cópia do hidapi do SDL 3.4.14): o `hid_read`
    passa prazo 0 ao `hid_read_timeout` (`:1274`), o `poll` volta na hora, e o
    wrapper devolve `None` com a fila vazia.

    Um dono só para o toque no C que o wrapper não expõe, e é também a costura
    que o dublê da régua troca: o dublê do `hidapi.Device` tem o mesmo modo.
    """
    cdata = getattr(dispositivo, "_device", None)
    if cdata is None:
        # O mesmo que o `_check_device_status` do wrapper diz a quem usa um
        # dispositivo fechado — e o laço trata `OSError` como fim de vida.
        raise OSError("Trying to perform action on closed device.")
    import hidapi

    hidapi.hidapi.hid_set_nonblocking(cdata, 1)


def _onde_a_thread_esta(thread: threading.Thread, quadros: int = 4) -> str | None:
    """Os quadros de cima da pilha de `thread`: `função (arquivo:linha) < …`."""
    quadro = sys._current_frames().get(thread.ident) if thread.ident else None
    pedacos: list[str] = []
    while quadro is not None and len(pedacos) < quadros:
        codigo = quadro.f_code
        pedacos.append(
            f"{codigo.co_name} ({os.path.basename(codigo.co_filename)}:{quadro.f_lineno})"
        )
        quadro = quadro.f_back
    return " < ".join(pedacos) or None


def _fechar_os_handles_juntos(handles: Iterable[Any]) -> None:
    """Fecha muitos handles pagando UM teto, e não um por handle.

    A-REPORT-THREAD-SAI-ANTES-DO-HANDLE-FECHAR-01 (29/09/2026), item 3. O
    `disconnect()` e o `_close_handles` fechavam um por um sob o `_io_lock`, e
    cada `close()` pagava o seu teto: na parada de 29/09, ~1,65 s de
    `_io_lock` segurado, e 4 x 2 x 0,5 s no pior caso de antes. Aqui o sinal
    baixa em TODOS antes do primeiro `join`, e os `join` dividem um prazo só.
    Handle que não é `_PinnedPyDualSense` (um dublê que só sabe `close()`)
    fecha pelo `close()` dele.
    """
    lista = list(handles)
    prazo = time.monotonic() + CLOSE_JOIN_TIMEOUT_SEC
    for handle in lista:
        if isinstance(handle, _PinnedPyDualSense):
            with contextlib.suppress(Exception):
                handle._baixar_o_sinal()
    for handle in lista:
        with contextlib.suppress(Exception):
            if isinstance(handle, _PinnedPyDualSense):
                handle._terminar_de_fechar(prazo)
            else:
                handle.close()


class _PinnedPyDualSense(pydualsense):  # type: ignore[misc]
    """`pydualsense` "pinada" a um hidraw `path` específico (multi-controle).

    Sobrescreve o `__find_device` manglado do upstream (que abre por VID/PID e
    fica com "o último enumerado") para abrir DETERMINISTICAMENTE o device do
    `path` informado via `hidapi.Device(path=...)`. É o que permite manter N
    instâncias, cada uma falando com um controle distinto.
    """

    # --- defaults de CLASSE, e a razão de existirem ---------------------
    #
    # Os três campos abaixo têm valor de classe porque nem todo
    # `_PinnedPyDualSense` passa pelo `__init__`: a suíte constrói dublês com

    _write_lock: threading.Lock = threading.Lock()

    _leitura_vazia_desde: float | None = None

    #: Um aviso por episódio, não um por ciclo.
    _leitura_vazia_avisada: bool = False

    #: A saída do rádio ficou DEVIDA enquanto a entrada estava muda. Quando a
    #: entrada volta, uma escrita só entrega o estado de agora — não a fila
    #: do que se acumulou no vão. Default de classe pelo mesmo motivo dos
    #: vizinhos: o dublê nasce por `__new__`.
    _saida_adiada_pelo_silencio: bool = False

    #: BATERIA-QUE-PULA-01 (16/09/2026) — quantos reports este handle ACEITOU e
    #: dublês desta suíte constroem `_PinnedPyDualSense` por `__new__`, e um
    _reports_aceitos: int = 0
    _reports_recusados: int = 0
    _recusa_avisada: bool = False

    _brilho_das_luzes: int = degrau_do_brilho_das_luzes(None)

    #: A háptica por áudio está tocando neste controle (a ponte `0x32` no
    #: rádio, o laço do cabo com o endpoint tocando): o rumble sai sem
    #: `HAPTICS_SELECT`. A-VIBRACAO-NAO-DESLIGA-A-HAPTICA-01; ver
    #: :meth:`set_haptica_de_audio` e `_build_common`.
    _haptica_de_audio: bool = False

    #: O `hid_device`. Toda chamada ao C deste handle (o `read` da volta, o
    #: modo do `read`, o `write` de qualquer thread) entra e sai contada sob
    _entrega: threading.Lock = threading.Lock()
    _dentro_do_c: int = 0
    _fechando: bool = False
    _entregue: bool = False
    _fechado: bool = False
    _sinal_em: float | None = None
    _descartados_depois_do_sinal: int = 0

    def __init__(self, path: bytes, *, is_edge: bool) -> None:
        super().__init__()
        self._pinned_path = path
        self._pinned_is_edge = is_edge
        self._write_lock = threading.Lock()
        self._entrega = threading.Lock()
        #
        # LIGHTBAR-BT-ADOPT-01 (provado ao vivo 2026-07-18; medido em 5 corridas):
        # nasce TRUE, nunca False. O report_thread começa a escrever assim que o
        # handle abre — ANTES de `_refresh_sysfs_leds` rodar. Nascendo False, o
        # 1º report saía com os flags de lightbar/player LIGADOS — e o report BT
        # da pydualsense 0.7.5 é MALFORMADO (layout off-by-one: [1]=0x02 fixo,
        self._suppress_leds = True
        self._throttle_sec = REPORT_THREAD_THROTTLE_SEC
        self._last_out_report: list[int] | None = None
        self._last_write_at = 0.0
        self._last_change_at = float("-inf")
        self._output_muted = False
        # GUERRA-01 item 2 (keepalive neutro): com o upstream, TODO report sai
        self._rumble_active = False
        self._rumble_stop_pending = False
        self._bt_seq = 0
        self._raw_trigger_right: bytes | None = None
        self._raw_trigger_left: bytes | None = None
        # AUDIO-OWNER-01 — os DOIS campos de áudio que o upstream autorizava em
        # TODO report sem nunca escrever valor nenhum. Enquanto estes ficarem
        # None, os bits de validação correspondentes saem ZERADOS e o firmware
        # mantém o que já tinha (mesma disciplina do keepalive neutro de
        # vibração/LED que já mora em `_build_common`).
        #
        # `_mic_mute_desejado` (common[9], flag1 0x02): o DONO no Linux é o
        # KERNEL. O `hid-playstation` alterna `ds->mic_muted` na borda do botão
        # de mute e só então liga `POWER_SAVE_CONTROL_ENABLE` com o bit
        # `integrations/dualsense_bt_audio.py` (BT-MIC-GATING-01).
        self._mic_mute_desejado: bool | None = None
        self._mic_led_desejado: int | bool | None = None
        self._volumes_audio: list[int | None] = [None, None, None, None]
        #: escrever é mandar zero a 60 Hz com cara de keepalive.
        self._preamp_audio: int | None = None
        self._audio_status: int | None = None
        self.zerar_estado_da_borda_do_mic()

    def _garantir_estado_da_borda_do_mic(self) -> None:
        """Zera o estado UMA vez, se ninguém o zerou — e não é remendo cego.

        DEZESSEIS dublês desta suíte constroem `_PinnedPyDualSense` por
        ``__new__`` e listam à mão os campos de que precisam. É o desenho certo
        para eles (abrir aparelho num teste é proibido nesta casa), e é o
        desenho que quebra toda vez que o produto ganha um campo: em
        10/09/2026 a cura da sustentação acrescentou dois, e nove testes
        caíram com `AttributeError` em quatro arquivos diferentes.

        **A cura não pode ser redigitar o campo em dezesseis lugares** — isso é
        a mesma família de defeito com outra roupa. Aqui o dono único se
        garante sozinho, e o `__init__` continua chamando-o para que o custo
        seja zero no caminho vivo. O campo-sentinela é o último que o estado
        ganhou (`_mic_botao`, 28/09/2026): um handle zerado por uma versão
        velha do dono também é refeito.
        """
        if "_mic_botao" not in self.__dict__:
            self.zerar_estado_da_borda_do_mic()

    def zerar_estado_da_borda_do_mic(self) -> None:
        """TODO o estado do botão do mic, num lugar só — e o motivo é medido."""
        self._mic_mudo: bool | None = None
        self._mic_botao: bool | None = None
        self._mic_mudo_seq: int = 0
        self._mic_mudo_pedido: bool | None = None
        self._mic_mudo_em: float | None = None
        self._mic_posse_solta_pela_mao: bool = False

    def init(self) -> None:
        """O `init()` do upstream, mas a `report_thread` é daemon e diz de quem é."""
        self.device, self.is_edge = self._pydualsense__find_device()
        self.light = DSLight()
        self.audio = DSAudio()
        self.triggerL = DSTrigger()
        self.triggerR = DSTrigger()
        self.state = DSState()
        if self.is_edge:
            self.state.L4, self.state.L5, self.state.R4, self.state.R5 = (
                False,
                False,
                False,
                False,
            )
            (
                self.l4_changed.available,
                self.l5_changed.available,
                self.r4_changed.available,
                self.r5_changed.available,
            ) = True, True, True, True
        self.battery = DSBattery()
        self.conType = self.determineConnectionType()
        if self.conType is ConnectionType.ERROR:
            raise Exception("Couldn't determine connection type")
        self.ds_thread = True
        self.connected = True
        self.report_thread = threading.Thread(
            target=self.sendReport, daemon=True, name=self._nome_da_thread()
        )
        self.report_thread.start()
        self.states = None

    def _nome_da_thread(self) -> str:
        """`hefesto-report-hidrawN`: o nó, nunca o endereço do controle."""
        caminho = getattr(self, "_pinned_path", b"") or b""
        if isinstance(caminho, bytes):
            caminho = caminho.decode("utf-8", "replace")
        return f"hefesto-report-{os.path.basename(str(caminho)) or 'sem-no'}"

    def _pydualsense__find_device(self) -> tuple[Any, bool]:
        import hidapi

        return hidapi.Device(path=self._pinned_path), self._pinned_is_edge

    def sendReport(self) -> None:  # noqa: N802 - override do nome do upstream
        """O laço do upstream, com throttle por volta e a fila esvaziada em cada uma.

        O upstream faz `read`+`write` num laço apertado sem pausa, na taxa do
        controle. Com múltiplos controles isso satura o controlador USB e
        degrada o link Bluetooth (CRC fails → output do BT morre), então a
        volta dorme `_throttle_sec`. BUG-MULTI-CONTROLLER-BT-CRC-CONTENTION-01.

        O-BOTAO-DO-MIC-CHEGA-NA-HORA-01 (29/09/2026) — A VOLTA ESVAZIA A FILA.

        O botão do microfone e o bit de mudo (`status[1]`) só chegam por este
        `read`; o kernel consome o botão e não emite tecla. A volta lia UM
        report de uma fila de 63 que o aparelho enche a centenas por segundo, e
        o kernel descarta o report NOVO com a fila cheia: cada report lido tinha
        63 voltas de idade. Na bancada de 29/09, com os quatro no rádio, isso
        deu 2,1 s do dedo à borda (63 x 33 ms); com um no cabo, os 547 ms de
        04/09 (63 x 8,7 ms). Agora a volta lê até a fila ficar vazia
        (`_esvaziar_a_fila`), conta o botão e o `status[1]` em cada report, na
        ordem em que chegaram, e entrega à pydualsense só o mais novo
        (`_consumir_lote`). A metade da saída não mudou: o mesmo throttle, um
        write quando muda e o keepalive.

        **A leitura tem prazo zero, e é por isso que a saída não espera.** O
        fd nasce bloqueante (`hidapi.Device(path=...)`, `blocking=True`); com a
        fila cheia a leitura nunca esperava, e com a fila vazia a cada volta
        ela seguraria a saída até o próximo report — ~190 ms no rádio parado.
        O `init()` precisa de UMA leitura com espera para descobrir o
        transporte, então o modo muda na primeira volta (`_hid_set_nonblocking`).

        LACO-DE-ESCRITA-02 (15/08/2026) — A LEITURA VAZIA NÃO PODE MATAR A SAÍDA.

        Com o prazo zero, o `read` devolve `None` com a fila vazia, e `None` é
        resposta legítima, não erro. O `readInput` do upstream começa com
        `list(inReport)`, que com `None` levanta `TypeError`. **A cura não é
        capturar o `TypeError`**: é não passar `None` adiante. Sem dado, não há
        o que interpretar, e a volta segue direto para a metade de SAÍDA.
        (Nota de 29/09: a docstring de 15/08 dizia que o fd já nascia
        não-bloqueante. Não nascia — o `hid_read` bloqueante nunca devolve 0 —,
        e a cura de 15/08 passou a valer de verdade com o prazo zero.)

        E o silêncio deixa RASTRO: a volta sem report nenhum é a leitura vazia
        (`_registrar_leitura_vazia`), e só ela — o «não há mais» que fecha cada
        drenagem não é silêncio. Uma linha de aviso por episódio quando ele
        passa de `LEITURA_VAZIA_AVISO_SEC`, e uma de volta quando a entrada
        fala de novo.

        A-REPORT-THREAD-SAI-ANTES-DO-HANDLE-FECHAR-01 (29/09/2026) — DEPOIS DO
        SINAL, NADA VAI AO APARELHO, E QUEM SAI POR ÚLTIMO FECHA.

        O laço confere o `ds_thread` depois de cada leitura: um report lido
        depois do sinal é jogado fora (não vai à borda do microfone, nem ao
        `readInput`, nem à metade da saída) e contado. Um handle que o
        `close()` deixou com a thread (ela estava dentro do C) pode ter o
        controle de volta no mesmo nó, ou já ter um handle novo por outro nó; o
        report velho não escreve nada num controle que já tem dono. E a thread
        que sai do C por último, com o handle marcado, fecha o `hid_device` no
        `finally` (`_sair_e_fechar_se_for_o_ultimo`).
        """
        try:
            self._girar_a_volta()
        finally:
            self._sair_e_fechar_se_for_o_ultimo()

    def _girar_a_volta(self) -> None:
        """O laço do `sendReport`; a docstring de lá diz o porquê de cada parte."""
        sem_espera = False
        while self.ds_thread:
            try:
                if not sem_espera:
                    with self._no_c():
                        _hid_set_nonblocking(self.device)
                    sem_espera = True
                lidos = self._esvaziar_a_fila()
                if not self.ds_thread:
                    self._descartados_depois_do_sinal += len(lidos)
                    break
                if lidos:
                    self._consumir_lote(lidos)
                else:
                    self._registrar_leitura_vazia()
                if not self._output_muted:
                    dono_do_rumble = self._rumble_active or self._rumble_stop_pending
                    out = self.prepareReport()
                    now = time.monotonic()
                    mudou = out != self._last_out_report
                    if mudou:
                        self._last_change_at = now
                    # DualSense na mesa dela (dois no cabo, dois no rádio) e o
                    confirmando = (
                        now - self._last_change_at
                    ) < OUT_REPORT_KEEPALIVE_CONFIRMACAO_SEC
                    vencido = (now - self._last_write_at) >= OUT_REPORT_KEEPALIVE_SEC
                    deve_escrever = mudou or (
                        vencido and (dono_do_rumble or confirmando)
                    )
                    if deve_escrever and self._a_saida_espera_a_entrada(now):
                        self._saida_adiada_pelo_silencio = True
                        deve_escrever = False
                    elif (
                        self._saida_adiada_pelo_silencio
                        and not self._a_saida_espera_a_entrada(now)
                    ):
                        deve_escrever = True
                        self._saida_adiada_pelo_silencio = False
                    if deve_escrever:
                        self.writeReport(out)
                        self._last_out_report = out
                        self._last_write_at = now
                throttle = self._throttle_sec
                if throttle > 0:
                    time.sleep(throttle)
                elif not lidos:
                    time.sleep(ESPERA_DA_VOLTA_VAZIA_SEM_THROTTLE_SEC)
            except OSError:
                self.connected = False
                break
            except AttributeError:
                self.connected = False
                break
            except Exception as exc:
                self.connected = False
                logger.error(
                    "report_thread_morreu_por_excecao",
                    path=getattr(self, "_pinned_path", None),
                    tipo=type(exc).__name__,
                    err=str(exc),
                )
                break

    def _a_saida_espera_a_entrada(self, agora: float) -> bool:
        """No rádio, não escrever enquanto a entrada está muda há tempo demais."""
        if getattr(self, "conType", None) != ConnectionType.BT:
            return False
        desde = self._leitura_vazia_desde
        if desde is None:
            return False
        return (agora - desde) >= LEITURA_VAZIA_AVISO_SEC

    def _registrar_leitura_vazia(self) -> None:
        """Contabiliza um `read` sem dado (LACO-DE-ESCRITA-02).

        Um aviso por EPISÓDIO de silêncio, nunca um por ciclo: com o throttle
        da mesa cheia são ~31 ciclos por segundo, e um aviso por ciclo afogaria
        o journal exatamente no momento em que ele mais precisa ser lido.
        """
        agora = time.monotonic()
        if self._leitura_vazia_desde is None:
            self._leitura_vazia_desde = agora
            return
        if self._leitura_vazia_avisada:
            return
        mudo_ha = agora - self._leitura_vazia_desde
        if mudo_ha >= LEITURA_VAZIA_AVISO_SEC:
            self._leitura_vazia_avisada = True
            logger.warning(
                "report_thread_entrada_muda",
                path=getattr(self, "_pinned_path", None),
                segundos=round(mudo_ha, 3),
                detalhe="o aparelho parou de entregar report; a SAÍDA segue viva",
            )

    def _registrar_leitura_viva(self) -> None:
        """Fecha o episódio de silêncio, se houver um aberto (LACO-DE-ESCRITA-02)."""
        if self._leitura_vazia_desde is None:
            return
        mudo_por = time.monotonic() - self._leitura_vazia_desde
        avisado = self._leitura_vazia_avisada
        self._leitura_vazia_desde = None
        self._leitura_vazia_avisada = False
        if avisado:
            logger.info(
                "report_thread_entrada_voltou",
                path=getattr(self, "_pinned_path", None),
                segundos=round(mudo_por, 3),
            )

    def _esvaziar_a_fila(self) -> list[Any]:
        """Lê TODO report pendente no fd deste handle, do mais velho ao mais novo.

        O-BOTAO-DO-MIC-CHEGA-NA-HORA-01 (29/09/2026). A fila do hidraw é por
        fd (`struct hidraw_list`, `buffer[64]`), e o kernel descarta o report
        que chega com ela cheia: ler um por volta deixava cada report com 63
        voltas de idade. Aqui a volta lê até o `read` devolver `None` (a
        leitura tem prazo zero, ver `sendReport`), com teto de
        `LEITURAS_POR_VOLTA`, e o dado mais velho que sobra tem uma volta.

        A leitura viva conta ANTES da guarda, report a report: um quadro de
        áudio é o aparelho falando, e deixá-lo para depois da guarda faria um
        controle com a ponte do microfone de pé passar por «entrada muda».
        """
        lidos: list[Any] = []
        for _ in range(LEITURAS_POR_VOLTA):
            with self._no_c():
                in_report = self.device.read(self.input_report_length)
            if in_report is None:
                break
            self._registrar_leitura_viva()
            lidos.append(in_report)
            if not self.ds_thread:
                break
        return lidos

    def _consumir_report(self, in_report: Any) -> None:
        """A porta de UM report: o `_consumir_lote` de um só."""
        self._consumir_lote((in_report,))

    def _consumir_lote(self, reports: Sequence[Any]) -> None:
        """Entrega os reports crus de UMA volta aos dois consumidores — e SÓ os de ESTADO.

        O-BOTAO-DO-MIC-CHEGA-NA-HORA-01 (29/09/2026). A volta esvazia a fila, e
        cada report de estado conta o botão do microfone e o `status[1]`, na
        ordem em que chegaram (`_captura_status_audio`): um toque que começa e
        acaba dentro de uma volta ainda é um aperto. A pydualsense recebe só o
        report de estado mais NOVO, uma vez por volta: o `readInput` é o parse
        caro, e o estado que ele guarda é o de agora, não o de cada report.

        **Cada report paga UMA validação.** A guarda é o próprio
        `_captura_status_audio`: o `extract_estado_do_mic` já devolve `None`
        para o que não é estado (id, tamanho, o bit de áudio e o CRC do BT).

        BATERIA-QUE-PULA-01, 16/09/2026, e a queixa dela foi: *"esse numero da
        bateria fica oscilando sem parar de 75 a 0 a 90 a 100"*.

        **O `readInput` da pydualsense não confere NADA.** Ele começa em
        `list(inReport)` e escreve direto em `self.states`, `self.state` e
        `self.battery`: id, tamanho, CRC e o bit de áudio nunca são olhados. Com
        a ponte de microfone por BT de pé, o DualSense manda Opus no MESMO
        report `0x31`, com os MESMOS 78 bytes — e `states[53]`, o byte de
        bateria, cai dentro da janela do Opus.

        MEDIDO no aparelho: 600 amostras de `daemon.state_full` em 61 s deram
        **14,8% dos valores diferentes de 75**, com o sysfs do kernel estável em
        75 nas 300 leituras. O `battery_state` trouxe 58 leituras fora dos seis
        valores que existem — só byte aleatório faz isso.

        **E A BATERIA É O MENOR DOS CAMPOS.** Tudo que o `readInput` escreve
        aceitava Opus como estado, e o pior é o `state.micBtn` (bit `0x04` do
        `misc2`): ele fecha um LAÇO, porque o botão do microfone liga e desliga
        a ponte que produz o áudio que o envenena.

        A vizinha desta linha já era guardada desde 01/09 — o
        `_captura_status_audio` confere antes de ler. O `readInput` ficou de
        fora. *Quando a cura conhece a causa, ela cobre TODOS os chamadores*, e
        este é o único que existe: `readInput` tem UM chamador em todo o `src/`.
        """
        mais_novo: Any = None
        for in_report in reports:
            try:
                cru = bytes(in_report)
            except (TypeError, ValueError):
                continue
            if not self._captura_status_audio(cru):
                self._recusar_report(cru)
                continue
            self._reports_aceitos += 1
            mais_novo = in_report
        if mais_novo is not None:
            self.readInput(mais_novo)

    def _recusar_report(self, cru: bytes) -> None:
        """DESCARTA o report que não é estado — e CONTA.

        Descartar, nunca "consertar": num report de áudio não há metade
        aproveitável, o payload inteiro é Opus.

        **Conta** porque o número é a régua — `_reports_aceitos` subindo é a
        prova de que a guarda não congelou o controle. **Avisa uma vez por
        HANDLE**, não por report: com a ponte de pé o rádio entrega mais de cem
        reports de áudio por segundo, e um aviso por report afogaria o journal
        exatamente quando ele precisa ser lido.
        """
        self._reports_recusados += 1
        if self._recusa_avisada:
            return
        self._recusa_avisada = True
        logger.info(
            "report_recusado_nao_e_estado",
            path=getattr(self, "_pinned_path", None),
            report_id=cru[0] if cru else None,
            tamanho=len(cru),
            detalhe=(
                "áudio ou pacote corrompido; não vai ao `readInput` "
                "(BATERIA-QUE-PULA-01)"
            ),
        )

    # QUEDA-QUE-PENDURA-01, 04/08/2026 — MEDIDO no journal dela.
    #
    # O `close()` do upstream é, literalmente:
    #
    #     self.ds_thread = False
    #     self.report_thread.join()     <- SEM TETO
    #     self.device.close()
    #
    # e o topo do laço acima era `self.device.read(...)`, que BLOQUEAVA. Enquanto
    # o controle responde, o `ds_thread = False` é visto no ciclo seguinte e o
    # join volta em milissegundos. **Quando o controle some do rádio sem
    # despedida** — 8BitDo que se desliga sozinho, link Bluetooth que cai —
    def close(self) -> None:
        """O `close()` do upstream com teto, e sem fechar por cima de ninguém."""
        self._baixar_o_sinal()
        self._terminar_de_fechar(time.monotonic() + CLOSE_JOIN_TIMEOUT_SEC)

    @contextlib.contextmanager
    def _no_c(self) -> Iterator[None]:
        """Uma chamada ao C deste handle, contada — e recusada se ele está fechando."""
        with self._entrega:
            if self._fechando:
                raise OSError("handle fechando: nada mais vai ao aparelho")
            self._dentro_do_c += 1
        fecho_eu = False
        try:
            yield
        finally:
            with self._entrega:
                self._dentro_do_c -= 1
                if (
                    self._entregue
                    and self._dentro_do_c == 0
                    and not self._fechado
                    and threading.current_thread() is not getattr(self, "report_thread", None)
                ):
                    self._fechado = True
                    fecho_eu = True
            if fecho_eu:
                self._fechar_o_device()
                logger.info(
                    "escrita_avulsa_saiu_e_fechou",
                    path=getattr(self, "_pinned_path", None),
                    segundos=self._segundos_desde_o_sinal(),
                )

    def _baixar_o_sinal(self) -> None:
        """Marca o handle: a thread para, e nada novo entra no C."""
        with self._entrega:
            self._fechando = True
            self.ds_thread = False
            if self._sinal_em is None:
                self._sinal_em = time.monotonic()

    def _terminar_de_fechar(self, prazo: float) -> None:
        """Espera a thread até `prazo` e fecha — ou deixa o handle com quem está no C."""
        thread = getattr(self, "report_thread", None)
        propria = thread is threading.current_thread()
        if thread is not None and not propria and thread.is_alive():
            thread.join(timeout=max(0.0, prazo - time.monotonic()))
        with self._entrega:
            dentro = self._dentro_do_c
            fecho_eu = dentro == 0 and not self._fechado
            if fecho_eu:
                self._fechado = True
            elif not self._fechado:
                # Alguém está no C: o handle fica com ele, que fecha ao sair.
                self._entregue = True
        if fecho_eu:
            self._fechar_o_device()
            return
        if thread is not None and not propria and thread.is_alive():
            logger.warning(
                "report_thread_nao_encerrou",
                path=getattr(self, "_pinned_path", None),
                segundos=self._segundos_desde_o_sinal(),
                onde=_onde_a_thread_esta(thread),
                detalhe=(
                    "a thread segue dentro do C e o handle ficou com ela: "
                    "quem sair por último fecha o hid_device"
                ),
            )
        elif dentro:
            logger.info(
                "handle_ficou_com_a_escrita_avulsa",
                path=getattr(self, "_pinned_path", None),
                dentro=dentro,
            )

    def _sair_e_fechar_se_for_o_ultimo(self) -> None:
        """O `finally` da `report_thread`: fecha se o `close()` lhe entregou o handle."""
        with self._entrega:
            fecho_eu = self._entregue and self._dentro_do_c == 0 and not self._fechado
            if fecho_eu:
                self._fechado = True
        if not fecho_eu:
            return
        self._fechar_o_device()
        logger.info(
            "report_thread_saiu_e_fechou",
            path=getattr(self, "_pinned_path", None),
            segundos=self._segundos_desde_o_sinal(),
            descartados=self._descartados_depois_do_sinal,
        )

    def _fechar_o_device(self) -> None:
        with contextlib.suppress(Exception):
            self.device.close()

    def _segundos_desde_o_sinal(self) -> float | None:
        sinal = self._sinal_em
        return None if sinal is None else round(time.monotonic() - sinal, 3)


    def _captura_status_audio(self, in_report: Any) -> bool:
        """Guarda o byte de estado de áudio do report CRU — e diz se ele era ESTADO.

        **Devolve `True` quando o report era estado de input** (e foi lido), e
        `False` quando o extrator o recusou. É essa resposta que o
        `_consumir_lote` usa como a guarda (O-BOTAO-DO-MIC-CHEGA-NA-HORA-01,
        29/09/2026): cada report paga uma conferência de CRC, e não duas.

        MIC-DA-MESA-ELEICAO-01 (01/09/2026) — POR QUE O CAMINHO MUDOU.

        Esta função lia `self.states[54]`, que é o report já digerido pelo
        `readInput` da pydualsense 0.7.5. Aquele caminho **não confere nada**:
        nem o report id, nem o tamanho, nem o CRC-32 do BT, nem o
        `INPUT_FLAG_AUDIO`. Com a ponte de microfone por Bluetooth de pé, o
        DualSense manda Opus no MESMO report `0x31`, com os MESMOS 78 bytes, e
        o byte 55 cai dentro da janela de Opus (`raw[3:74]`,
        `integrations/dualsense_bt_audio.py`). É o defeito PS-PRESO-01 inteiro,
        escrito em `core/physical_report_reader.py`: foi assim que os botões
        MIC e PS ficaram presos e ela desligou o controle.

        Enquanto este byte só pintava um selo na tela, o estrago era cosmético.
        A partir da ELEIÇÃO DE MICROFONE ele é o gesto dela — e um pacote
        corrompido de rádio elegendo microfone sozinho é o pior desfecho
        possível deste trabalho.

        A cura é **um fato, um dono**: quem lê o report cru já é o
        `core/physical_report_reader.py`, com CRC de BT e com a recusa do report
        de áudio. Aqui só se chama — e desde 28/09/2026 a chamada devolve, do
        MESMO report, o `status[1]` e o botão do microfone
        (`extract_estado_do_mic`), porque o gesto é o botão e o bit de mudo é
        só o que o firmware segurava no instante dele.

        `None` do extrator — id desconhecido, tamanho curto, CRC ruim, report de
        ÁUDIO — **NÃO mexe no cache**, e isso é diferente de `0x00`: `0x00` é
        "o report chegou íntegro e não há fone nem microfone mudo".
        """
        from hefesto_dualsense4unix.core.physical_report_reader import (
            extract_estado_do_mic,
        )

        try:
            cru = bytes(in_report)
        except (TypeError, ValueError):
            return False
        lido = extract_estado_do_mic(cru)
        if lido is None:
            return False
        status, botao = lido
        self._audio_status = status & 0xFF
        self._registrar_borda_do_mic(status & 0xFF, botao)
        return True

    def _registrar_borda_do_mic(self, status: int, botao: bool) -> None:
        """Conta os APERTOS do botão do microfone deste controle.

        MIC-DA-MESA-ELEICAO-01 deu endereço ao gesto: ele chega por um fd que é
        só deste controle, e **a identidade vem do fd, não do report**. É
        CONTADOR, não leitura de estado: um toque duplo entre duas amostragens
        do consumidor devolveria o mesmo estado e a segunda eleição sumiria.

        **O GESTO É O BOTÃO, E NÃO O BIT DE MUDO — O-BOTAO-DO-MIC-SO-OBEDECE-A-
        MAO-01 (28/09/2026).** Até aqui se contava a virada do bit `MIC_MUTE`
        de `status[1]`, a CONSEQUÊNCIA de um aperto: o `hid-playstation` alterna
        `ds->mic_muted` na borda do botão e escreve o mudo no firmware. Mas esse
        bit muda com QUALQUER um que escreva o mudo — o kernel, o próprio
        Hefesto, o que vier por outra ponte —, e na sessão dela de 28/09 o
        branco teve três bordas que ninguém deu (00:18:40, 00:22:15, 00:22:17):
        *«eu não apertei o botão do Mic»*. Cada uma elegeu o microfone da
        máquina e gravou o perfil dela. O bit do botão (`buttons[2]` bit 2,
        `DS_BUTTONS2_MIC_MUTE`) vem no mesmo report e só muda quando alguém
        aperta.

        As duas curas de 10/09/2026 sobre o bit de estado — a fila das marcas do
        que NÓS pedimos (o eco da própria escrita virava gesto) e a
        sustentação de 300 ms (o gating do rádio virava gesto) — deixam de ter
        objeto: nem o eco nem o gating apertam o botão, e o quadro de áudio do
        rádio nem chega aqui (`_consumir_lote`). As duas tinham furo medido:
        uma escrita que não ecoava deixava a marca viva e engolia o aperto
        seguinte dela, e um aperto com o bit parado (a posse do mudo nossa)
        sumia calado.

        **O `mudo` do aperto é o que ele PEDE:** o contrário do que o firmware
        segurava no report do aperto. O kernel escreve o mudo DEPOIS de ler
        este mesmo report, então o `status` daqui ainda é o de antes. É o valor
        que `hotkey._o_que_a_borda_pede` sempre recebeu (o bit depois da virada
        do kernel), agora sem depender de o kernel e o firmware estarem em fase.

        **E A MÃO DEVOLVE A POSSE DO MUDO.** Com a posse nossa (o «calado» do
        perfil, `set_microphone_mute(True)`), o próximo report do Hefesto —
        basta a luz mudar — reafirma o mudo velho por cima do que o kernel fez
        com o aperto dela. Medido na mesma sessão: o branco ficou em zero
        absoluto por 40 s com `mic_mudo_desejado=True` no `state_full` inteiro,
        porque o ato leu o bit momentaneamente livre e não escreveu. Soltar
        aqui, na thread do report, vale antes do report seguinte; o mapa
        por-uniq do controlador acompanha em `bordas_do_mic`.
        """
        from hefesto_dualsense4unix.integrations.dualsense_bt_audio import (
            STATUS_MIC_MUDO,
        )

        self._garantir_estado_da_borda_do_mic()
        mudo = bool(status & STATUS_MIC_MUDO)
        self._mic_mudo = mudo
        anterior = self._mic_botao
        self._mic_botao = bool(botao)
        if anterior is None or anterior or not botao:
            return
        self._mic_mudo_seq += 1
        self._mic_mudo_pedido = not mudo
        self._mic_mudo_em = _relogio_da_borda()
        if getattr(self, "_mic_mute_desejado", None) is not None:
            self._mic_mute_desejado = None
            self._mic_posse_solta_pela_mao = True

    def set_microphone_mute(self, muted: bool | None) -> None:
        """Assume (ou devolve) a POSSE do mudo de microfone do firmware.

        `True`/`False` = o hefesto passa a mandar `common[9]` com o bit
        `MIC_MUTE` ligado/desligado E o `POWER_SAVE_CONTROL_ENABLE` do flag1
        asserido — a partir daí somos o dono do campo em todo report.
        `None` (default de fábrica) = DEVOLVE a posse: o bit de validação some
        do report e quem manda volta a ser o kernel (`hid-playstation` alterna
        `ds->mic_muted` na borda do botão de mute do controle).

        Não existe caminho de leitura: o firmware não devolve este registrador.
        Por isso "não somos donos" é representado por None, e não por False —
        False é uma ORDEM ("desmuta"), que é exatamente o que o keepalive
        fazia sem querer.
        """
        self._mic_mute_desejado = None if muted is None else bool(muted)

    def set_microphone_led(self, aceso: bool | int | None) -> None:
        """Assume (ou devolve) a POSSE do LED do botão de mudo (`common[8]`).

        Irmão exato do `set_microphone_mute` acima, e pelo MESMO motivo: o
        registrador não tem caminho de leitura, então "não somos donos" só
        pode ser representado por `None` — `False` é uma ORDEM ("apaga"), e
        mandar essa ordem a cada report é justamente o defeito.

        `True`/`False` = o hefesto autoriza `MIC_MUTE_LED_CONTROL_ENABLE`
        (flag1 0x01) e escreve o byte. `None` (default de fábrica) = devolve o
        campo ao kernel, que o escreve na borda do botão de mudo
        (`hid-playstation.c:1538-1540`) e é quem sabe se o mic está mudo.

        O espelho em `self.audio.microphone_led` é mantido de propósito: ele é
        o estado que a pydualsense (e a suíte) leem, e quem lê o handle tem de
        ver o que foi pedido.
        """
        # `bool` é subclasse de `int`, então `isinstance(True, int)` é
        # verdadeiro e o ramo de cima guarda `True`/`False` inalterados: para
        # todo chamador que existe hoje isto é BYTE-IDÊNTICO ao `bool(aceso)`
        # que estava aqui. O que ele acrescenta é o NÍVEL, que o `bool` não
        # sabe carregar (ver o `common[8] = int(...)` em `_build_common`).
        self._mic_led_desejado = (
            None if aceso is None else aceso if isinstance(aceso, int) else bool(aceso)
        )
        if aceso is not None:
            with contextlib.suppress(Exception):
                self.audio.setMicrophoneLED(bool(aceso))

    def set_haptica_de_audio(self, ativa: bool) -> None:
        """A háptica por áudio passou a tocar (ou parou) NESTE controle.

        A-VIBRACAO-NAO-DESLIGA-A-HAPTICA-01 (03/10/2026). Medido com ela: a
        vibração pelo nó do jogo e a háptica de teste ao mesmo tempo
        ALTERNAVAM, nos quatro controles, com dois ou quatro por adaptador. O
        rumble deste report saía com `HAPTICS_SELECT` (`flag0` bit 1), que o
        firmware lê como «troque para a vibração emulada» e que cala a háptica
        por áudio até o bit cair; com o report do rumble e o da háptica
        chegando alternados, o controle trocava de modo sem parar. Com a
        háptica tocando, o rumble vai com `COMPATIBLE_VIBRATION` (bit 0) e sem
        o bit 1; sem háptica, como sempre. Quem diz é o dono das pontes (o
        `AltoFalanteSubsystem`), pelo `set_haptica_de_audio_for` do
        controlador.
        """
        self._haptica_de_audio = bool(ativa)

    def set_audio_volumes(
        self,
        *,
        headphone: int | None = None,
        speaker: int | None = None,
        microphone: int | None = None,
        audio_path: int | None = None,
        preamp: int | None = None,
    ) -> None:
        """Assume a posse dos bytes de volume que forem passados (common[4..7])."""
        for pos, valor in enumerate((headphone, speaker, microphone, audio_path)):
            if valor is not None:
                self._volumes_audio[pos] = min(
                    _clamp_u8(valor, 0), _AUDIO_TETOS[pos]
                )
        if preamp is not None:
            self._preamp_audio = int(preamp) & rep.SP_PREAMP_GAIN_MASK

    def release_audio_volumes(self, *, microfone: bool = True) -> None:
        """Devolve a posse dos bytes de áudio (volta ao neutro). Idempotente.

        `microfone=False` POUPA o `common[6]` — MIC-VOLUME-02 (09/09/2026), e o
        parâmetro existe por um defeito medido no papel antes de existir no
        disco: a partir do momento em que o ganho do microfone tem dono
        (`set_microphone_volume`), um "Devolver" do ALTO-FALANTE levava o byte
        do microfone junto e em silêncio — o número continuava na tela e o
        aparelho voltava a obedecer ao firmware. São dois campos, com dois
        donos e duas telas; a devolução de um não pode gastar a do outro.

        O default segue `True` porque o sentido desta porta não mudou: quem
        pede a devolução INTEIRA (o dono do handle desistindo do bloco) continua
        recebendo os quatro bytes de volta.

        SOM-ROTA-01: o pré-amplificador (`common[37]`) entra na devolução
        junto com os quatro de `common[4..7]`. Deixá-lo de fora faria
        "Devolver" devolver metade — e o pré-amp é justamente o campo que
        muda o alcance do controle deslizante.

        O que a devolução NÃO faz, e nunca fez: restaurar o valor anterior. O
        DualSense não devolve o volume — não há report de entrada nem feature
        que o leia. "Devolver" devolve o CONTROLE, nunca o número.
        """
        guardado = self._volumes_audio[2] if not microfone else None
        self._volumes_audio = [None, None, guardado, None]
        self._preamp_audio = None

    def soltar_volume_do_microfone(self) -> None:
        """Devolve ao firmware SÓ o `common[6]`. MIC-VOLUME-02."""
        self._volumes_audio[2] = None

    def setLeftMotor(self, intensity: int) -> None:  # noqa: N802 - nome do upstream
        super().setLeftMotor(intensity)
        self._track_rumble_transition()

    def setRightMotor(self, intensity: int) -> None:  # noqa: N802 - nome do upstream
        super().setRightMotor(intensity)
        self._track_rumble_transition()

    def _track_rumble_transition(self) -> None:
        """GUERRA-01 item 2: rastreia rumble NOSSO ativo e a transição ativa→0."""
        active = bool(self.leftMotor or self.rightMotor)
        if active:
            self._rumble_active = True
        elif self._rumble_active:
            self._rumble_active = False
            self._rumble_stop_pending = True

    def _build_common(self, *, rumble_asserted: bool) -> bytearray:
        """Payload "common" (47 bytes) a partir do estado da pydualsense.

        Mesmo mapeamento de campos do upstream (motores, mic, gatilhos, LED),
        mas com DUAS políticas nossas aplicadas na origem:

        - keepalive neutro (GUERRA-01 item 2): sem rumble nosso ativo, os bits
          de vibração (flag0 0x01|0x02, atenuação 0x40 do flag1 e a vibração
          v2 0x04 do flag2) saem DESLIGADOS — o report não PEDE vibração.
          **A premissa de que isso bastava caiu em 11/08/2026** (ensaio
          `keepalive-premissa-troca-de-lado`): o firmware obedece aos BYTES
          `common[2]`/`common[3]`, que são escritos SEMPRE logo abaixo, fora
          deste ramo. Quem faz o rumble de terceiros sobreviver é o keepalive
          limitado de `sendReport` (RUMBLE-SEM-DONO-01) — este bloco continua
          por não pedir vibração que ninguém pediu, e porque o report de STOP
          depende de ele saber ligar os bits de volta;
        - supressão de LED (FEAT-DSX-LIGHTBAR-SYSFS-01): `_suppress_leds`
          limpa lightbar 0x04 + player 0x10 do flag1 (o kernel é o dono).
        - LIGHTBAR-BT-KEEPALIVE-01 (22/07, forense da captura): sob supressão,
          o flag2 também tem de sair ZERADO nos bits de SETUP/BRILHO da
          lightbar (0x02|0x01). O `ledOption` da pydualsense nasce `Both`
          (0x03) e vazava crus no keepalive a 2 Hz; o bit 0x02
          (LIGHTBAR_SETUP_CONTROL) é o mesmo que o kernel usa UMA vez por
          conexão para tomar a barra — reengatá-lo em regime trava a exibição
          no firmware (o registrador aceita a cor, o sysfs mostra, mas a barra
          fica apagada). Foi a regressão do BTREPORT-02: antes o keepalive era
          malformado e o firmware o descartava.
        - AUDIO-OWNER-01 (25/07): o mesmo princípio aplicado ao ÁUDIO, que era
          o último escritor sem dono do report. O upstream manda `flag0=0xFF`,
          o que autoriza common[4..7] (volumes de fone/alto-falante/mic e o
          byte de roteamento) — mas NINGUÉM nunca escreveu esses bytes, então
          saía "volume 0" a cada report; e mandava `POWER_SAVE_CONTROL_ENABLE`
          com `common[9]=0x00`, ou seja "desmuta o microfone", por cima do
          kernel, que é quem alterna o mudo na borda do botão físico. Agora os
          dois blocos só ganham autorização quando ALGUÉM deste projeto
          escreveu um valor (`set_audio_volumes` / `set_microphone_mute`);
          sem dono, os bits saem zerados e o firmware conserva o que tinha.
        - AUDIO-OWNER-01, o TERCEIRO campo (12/08/2026): o `mute_button_led`
          (`common[8]`, flag1 0x01) faltava na conta de 25/07 — e é o que
          MENTE PARA O OLHO DELA. O `0x01` estava fixo no `flag1` e o byte
          saía de `audio.microphone_led`, que nasce 0: ela apertava o mudo, o
          kernel acendia o LED e mutava o mic no firmware
          (`hid-playstation.c:1538-1540`, uma escrita na BORDA do botão), e o
          nosso report seguinte APAGAVA o LED sem desmutar. Agora o campo
          segue a mesma posse por byte (`set_microphone_led`).
        """
        from hefesto_dualsense4unix.core import ds_output_report as rep

        common = bytearray(rep.COMMON_LEN)
        suppress_leds = bool(getattr(self, "_suppress_leds", False))
        volumes = getattr(self, "_volumes_audio", None) or [None, None, None, None]
        mic_mute = getattr(self, "_mic_mute_desejado", None)
        mic_led = getattr(self, "_mic_led_desejado", None)
        flag0 = 0xFF
        flag1 = 0x01 | 0x02 | 0x04 | 0x10 | 0x40
        flag2 = int(self.light.ledOption.value)
        flag2 &= ~rep.VALID_FLAG2_LED_BRIGHTNESS_CONTROL_ENABLE
        brilho_das_luzes = int(self._brilho_das_luzes)
        if not suppress_leds:
            flag2 |= rep.VALID_FLAG2_LED_BRIGHTNESS_CONTROL_ENABLE
        # AUDIO-OWNER-01: os bits de áudio do flag0 caem TODOS e só voltam,
        # um a um, para os bytes de que alguém assumiu a posse.
        flag0 &= ~rep.VALID_FLAG0_AUDIO_MASK
        for bit, valor in zip(_AUDIO_FLAG0_BITS, volumes, strict=False):
            if valor is not None:
                flag0 |= bit
        if mic_mute is None:
            flag1 &= ~rep.VALID_FLAG1_POWER_SAVE_CONTROL_ENABLE
        if mic_led is None:
            flag1 &= ~rep.VALID_FLAG1_MIC_MUTE_LED_CONTROL_ENABLE
        if not rumble_asserted:
            flag0 &= ~(
                rep.VALID_FLAG0_COMPATIBLE_VIBRATION | rep.VALID_FLAG0_HAPTICS_SELECT
            )
            flag1 &= ~rep.VALID_FLAG1_MOTOR_POWER
            flag2 &= ~rep.VALID_FLAG2_COMPATIBLE_VIBRATION2
        elif self._haptica_de_audio:
            # A-VIBRACAO-NAO-DESLIGA-A-HAPTICA-01 (03/10/2026): o HAPTICS_SELECT
            # troca os atuadores para a vibração emulada e CALA a háptica por
            # áudio até o bit cair (hid-playstation, SDL, pydualsense). Com a
            # háptica tocando, o rumble vai só com COMPATIBLE_VIBRATION.
            flag0 &= ~rep.VALID_FLAG0_HAPTICS_SELECT
        if suppress_leds:
            flag1 &= ~(
                rep.VALID_FLAG1_LIGHTBAR_CONTROL_ENABLE
                | rep.VALID_FLAG1_PLAYER_INDICATOR_CONTROL_ENABLE
            )
            flag2 &= ~(
                rep.VALID_FLAG2_LIGHTBAR_SETUP_CONTROL_ENABLE
                | rep.VALID_FLAG2_LED_BRIGHTNESS_CONTROL_ENABLE
            )
        common[2] = int(self.rightMotor) & 0xFF
        common[3] = int(self.leftMotor) & 0xFF
        for offset, valor in zip(_AUDIO_COMMON_OFFSETS, volumes, strict=False):
            if valor is not None:
                common[offset] = int(valor) & 0xFF
        preamp = getattr(self, "_preamp_audio", None)
        if preamp is None:
            flag1 &= ~rep.VALID_FLAG1_AUDIO_CONTROL2_ENABLE
        else:
            flag1 |= rep.VALID_FLAG1_AUDIO_CONTROL2_ENABLE
            common[rep.COMMON_AUDIO_CONTROL2] = int(preamp) & rep.SP_PREAMP_GAIN_MASK
        common[0] = flag0
        common[1] = flag1
        if mic_led is not None:
            common[8] = int(mic_led) & 0xFF
        if mic_mute is not None:
            self.audio.microphone_mute = mic_mute
            common[9] = rep.POWER_SAVE_MIC_MUTE if mic_mute else 0x00
        raw_r = getattr(self, "_raw_trigger_right", None)
        if raw_r is not None and len(raw_r) == GAME_TRIGGER_BLOCK_LEN:
            common[10 : 10 + GAME_TRIGGER_BLOCK_LEN] = raw_r
        else:
            common[10] = int(self.triggerR.mode.value) & 0xFF
            for i in range(6):
                common[11 + i] = int(self.triggerR.forces[i]) & 0xFF
            common[19] = int(self.triggerR.forces[6]) & 0xFF
        raw_l = getattr(self, "_raw_trigger_left", None)
        if raw_l is not None and len(raw_l) == GAME_TRIGGER_BLOCK_LEN:
            common[21 : 21 + GAME_TRIGGER_BLOCK_LEN] = raw_l
        else:
            common[21] = int(self.triggerL.mode.value) & 0xFF
            for i in range(6):
                common[22 + i] = int(self.triggerL.forces[i]) & 0xFF
            common[30] = int(self.triggerL.forces[6]) & 0xFF
        common[rep.COMMON_VALID_FLAG2] = flag2
        if not suppress_leds:
            common[41] = int(self.light.pulseOptions.value) & 0xFF
            # ESTE BYTE É O BRILHO DOS LEDS DE JOGADOR, não o da barra — medido por
            common[42] = brilho_das_luzes & 0xFF
            common[43] = int(self.light.playerNumber.value) & 0xFF
            common[44] = int(self.light.TouchpadColor[0]) & 0xFF
            common[45] = int(self.light.TouchpadColor[1]) & 0xFF
            common[46] = int(self.light.TouchpadColor[2]) & 0xFF
        return common

    def prepareReport(self) -> list[int]:  # noqa: N802 - override do nome do upstream
        """Monta o report pelo builder comum (BTREPORT-02) — não usa o upstream."""
        try:
            from pydualsense.enums import ConnectionType

            from hefesto_dualsense4unix.core import ds_output_report as rep

            stop_pending = self._rumble_stop_pending
            common = self._build_common(
                rumble_asserted=self._rumble_active or stop_pending
            )
            if self.conType == ConnectionType.BT:
                report = list(rep.build_bt_report(common, seq=0))
            else:
                report = list(rep.build_usb_report(common))
            if stop_pending:
                self._rumble_stop_pending = False
            return report
        except Exception:
            fallback: list[int] = super().prepareReport()
            return fallback

    def writeReport(self, outReport: list[int]) -> int | None:  # noqa: N802,N803 - upstream
        """Write com carimbo de sequência BT (BTREPORT-02), SERIALIZADO.

        **Devolve quantos bytes saíram** (``None`` = o fio não disse), e é isso
        que permite a quem chama dizer a verdade — ver `_escrever_conferindo`
        logo abaixo. O upstream devolvia `None`; quem ignora o retorno segue
        funcionando igual.

        Reports 0x31 ganham o contador por handle (wrap 0-15) + CRC recalculado
        NUMA CÓPIA — o buffer original (que `sendReport` guarda em
        `_last_out_report`) permanece com seq 0, mantendo o dedup funcional.

        LACO-DE-ESCRITA-02 (15/08/2026) — POR QUE HÁ UM LOCK AQUI.

        Este método é chamado de MAIS DE UMA THREAD no mesmo handle:

        - a `report_thread` daquele handle, em regime (`sendReport`);
        - a thread do chamador (IPC / executor do poll loop) em
          `reescrever_lightbar_por_hidraw`, `_pintar_por_hidraw_bt` e
          `core/lightbar_reset.py` no rádio, e `_levar_o_brilho_das_luzes` — AVULSAS.

        E o corpo era um *read-modify-write* sem exclusão: ler `_bt_seq`,
        carimbar, incrementar, escrever. Duas threads podiam ler o MESMO valor e
        carimbar o MESMO `seq` em dois quadros. **O firmware descarta o segundo,
        e o nosso log diz "escrito".** Esse preço já foi pago uma vez por esta
        casa e está escrito por extenso em `reescrever_lightbar_por_hidraw`:
        *"o firmware descarta o report fora de sequência e o log diz 'escrito'
        com a barra apagada"*. É defeito só do RÁDIO — o `0x02` do cabo não tem
        `seq` nem CRC no envelope.

        **O `write` fica DENTRO do lock, e não só o contador.** Serializar
        apenas o incremento produziria `seq` distintos entregues FORA DE ORDEM
        (a thread que carimbou 5 podendo chegar ao fio depois da que carimbou 6),
        e report fora de sequência é exatamente o que o firmware joga fora. O
        que precisa ser atômico é o par carimbo+entrega, não o contador.

        **Por que isto não trava o daemon.** O lock é POR HANDLE e o corpo dele
        não chama mais nada do backend: não toma `_io_lock`, não chama de volta
        para `PyDualSenseController`, não é reentrante. Não existe caminho que
        pegue `_write_lock` e depois `_io_lock`, então não há ciclo — a única
        ordem possível é `_io_lock` → `_write_lock`, e mesmo essa não acontece
        hoje (os três chamadores avulsos soltam o `_io_lock` ANTES do I/O, de
        propósito). O tempo de posse é o de um `hid_write`, que já era
        serializado pelo kernel no mesmo descritor — o lock só antecipa a espera
        para o espaço do usuário. E um `hid_write` pendurado num controle não
        alcança os outros: cada handle tem o seu lock.

        **A entrega ao C é contada** (`_no_c`, A-REPORT-THREAD-SAI-ANTES-DO-
        HANDLE-FECHAR-01, 29/09/2026): com o handle fechando, a escrita recusa
        com `OSError` antes de tocar o C, e a que estava dentro fecha o
        `hid_device` ao sair, se for a última. O `close()` nunca toma o
        `_write_lock`: um `hid_write` preso seguraria o `close()`, e com ele o
        `_io_lock` do `disconnect()` — a cadeia dos 90 s da QUEDA-QUE-PENDURA-01
        com o `write` no lugar do `read`.
        """
        with self._write_lock, self._no_c():
            if len(outReport) == 78 and outReport[0] == 0x31:
                from hefesto_dualsense4unix.core import ds_output_report as rep

                stamped = list(outReport)
                rep.stamp_bt_seq(stamped, self._bt_seq)
                self._bt_seq = (self._bt_seq + 1) & 0x0F
                return self._escrever_conferindo(bytes(stamped))
            return self._escrever_conferindo(bytes(outReport))

    def _escrever_conferindo(self, quadro: bytes) -> int | None:
        """Escreve `quadro` no fio e DEVOLVE o que o fio respondeu."""
        escrito = self.device.write(quadro)
        saidos = _bytes_que_sairam(escrito)
        if saidos is not None and saidos != len(quadro):
            logger.warning(
                "escrita_curta_no_hidraw",
                pedidos=len(quadro),
                saidos=saidos,
            )
        return saidos


class PyDualSenseController(IController):
    """Implementação de `IController` baseada em `pydualsense` (multi-controle)."""

    #: entra. Default de CLASSE pela mesma razão dos de `_PinnedPyDualSense`:
    _exposicao_do_no: Callable[[str], AbstractContextManager[bool]] | None = None

    _brilho_do_perfil: float | None = None
    _cor_do_perfil: tuple[int, int, int] | None = None

    def __init__(self, evdev_reader: EvdevReader | None = None) -> None:
        self._handles: dict[str, pydualsense] = {}
        self._primary_key: str | None = None
        self._transport: Transport = "usb"
        # há nenhum DualSense — daemon segue vivo, IPC/UDP/CLI funcionais, e
        self._offline: bool = False
        self._desired_default = _DesiredOutput()
        self._desired_by_uniq: dict[str, _DesiredOutput] = {}
        # muda em nada. O que passa a existir é a procedência, para a ativação
        # de perfil soltar só a camada dela.
        self._desired_owner_by_uniq: dict[str, dict[str, str]] = {}
        # A PROCEDÊNCIA DA COR de cada override (`{uniq: número | constante}`),
        # decidida em 08/09/2026: **para qual número aquela cor foi escolhida**.
        # É o par do `_desired_owner_by_uniq` acima — aquele guarda QUE CAMADA
        # escreveu, este guarda POR QUE. Quando o número do aparelho muda, a
        # cor gravada vira fóssil e sai sozinha (`led_control.cores_sem_colisao`).
        #
        # NASCEU DE UM DEFEITO MEDIDO: sem ele o resolvedor adivinhava fóssil
        self._procedencia_da_cor: dict[str, object] = {}
        self._brilho_da_cor: dict[str, tuple[tuple[int, int, int], float]] = {}
        self._desired_coop_by_uniq: dict[str, _DesiredOutput] = {}
        # atributo de instância do `_PinnedPyDualSense`, e o handle é RECRIADO a
        # co-op logo acima: mapa próprio, por-uniq, ao lado do merge.
        #
        # Chaveado pelo MAC 12-hex normalizado do `_key_to_uniq` — a MESMA
        # guarda de 12 dígitos que impede um pseudo-MAC de key por path
        # (`/dev/hidrawN` → "deda4") levar a posse ao controle errado.
        self._mic_mute_by_uniq: dict[str, bool] = {}
        # A-VIBRACAO-NAO-DESLIGA-A-HAPTICA-01: quem tem a háptica por áudio
        # tocando, por MAC. Mora aqui, e não só no handle, pelo motivo do mudo
        # acima: a troca de nó (rádio para cabo) e a reconexão RECRIAM o
        # handle, e o dono das pontes só diz a borda.
        self._haptica_de_audio_por_uniq: set[str] = set()
        # R-20 item 2: escala de brilho POR CONTROLE, aplicada à BASE do merge.
        # Um override que só mexia no brilho materializava a cor GLOBAL no
        # slot por-uniq (`_controllers_to_specs` resolvia `lightbar` do global
        # para poder escalar) — e, como o override vence a camada automática,
        # isso MATAVA a cor do slot daquele controle. Guardado como fator, o
        # brilho escala o global e a automática sem opinar sobre qual cor é —
        # e nunca o override, que já traz o brilho dele (`_scaled_led`).
        self._led_scale_by_uniq: dict[str, float] = {}
        # POR-UNIDADE-01 (10/08/2026): a escala de VIBRAÇÃO por-uniq — irmã
        # exata do `_led_scale_by_uniq` acima, e pelo mesmo motivo de desenho.
        # O que chega do perfil é uma POLÍTICA de intensidade por controle
        # ("o branco vibra em economia, o preto no máximo"), e o daemon só
        # sabe escalar a política GLOBAL (`DaemonConfig.rumble_policy`, um
        # número para a casa inteira). Guardar aqui um FATOR por peça deixa o
        self._rumble_scale_by_uniq: dict[str, float] = {}
        self._auto_output_provider: Callable[[str], _DesiredOutput | None] | None = None
        self._mesa_apresentada: frozenset[str] = frozenset()
        self._feature_opener: Callable[[str], int] | None = None
        self._exposicao_do_no = None
        self._game_output_by_uniq: dict[str, _DesiredOutput] = {}
        self._game_triggers_by_uniq: dict[str, dict[str, bytes]] = {}
        # PERFIL ATÉ O JOGO PROVAR (decisão dela de 04/10/2026): o «sem efeito»
        # do gatilho e o preto da lightbar são ausência até o jogo mandar um
        # efeito (ou uma cor) de verdade pela primeira vez, naquele controle e
        # naquela partida. Dali em diante o jogo manda em tudo, e a saída dele
        # (`end_game_session_for`) zera o «já provou».
        self._jogo_provou_o_gatilho: set[str] = set()
        self._jogo_provou_a_luz: set[str] = set()
        self._game_authority_provider: Callable[[], str] | None = None
        self._retained_game_outputs: dict[str, dict[str, Any]] = {}
        self._retained_log_armed = True
        self._defend_last_at: float | None = None
        # ficaria ilegível. Some no `end_game_session_for`, com a sessão.
        self._recusa_ao_jogo_logada: dict[str, set[str]] = {}
        self._sysfs: dict[str, Any] = {}
        self._suprimir_player_leds = False
        self._sysfs_written: dict[str, tuple[int, int, int]] = {}
        self._output_target_key: str | None = None
        self._output_mute = False
        # GATILHO-DA-COR-01: quantas conexões NOVAS de DualSense no RÁDIO o
        self._conexoes_bt_novas = 0
        self._pinturas_de_lightbar = 0
        self._io_lock = threading.RLock()
        self._opening: set[str] = set()
        self._evdev = evdev_reader if evdev_reader is not None else EvdevReader()
        self._motion_reader: Any | None = None
        self._primary_change_observer: Callable[[str | None, str | None], None] | None = None
        self._primario_deposto: tuple[str, float] | None = None
        self._relogio: Callable[[], float] = relogio_do_prazo


    def hidraw_path(self, uniq: str | None = None) -> str | None:
        """Nó hidraw do controle `uniq` (None = primário), ou None."""
        with self._io_lock:
            key = self._primary_key if uniq is None else self._key_for_uniq(uniq)
            handle = self._handles.get(key) if key is not None else None
        path = getattr(handle, "_pinned_path", None)
        if not isinstance(path, bytes):
            return None
        texto = path.decode("utf-8", "replace")
        return texto if texto.startswith("/dev/hidraw") else None

    def _key_for_uniq(self, uniq: str) -> str | None:
        """Key do handle cujo MAC normalizado é `uniq` (None se não achar)."""
        for key in self._handles:
            if self._key_to_uniq(key) == uniq:
                return key
        return None

    def attach_motion_reader(self, reader: Any | None) -> None:
        """Registra (ou remove, com None) o reader de motion do P1 (GYRO-01)."""
        with self._io_lock:
            self._motion_reader = reader

    def read_calibration(self, uniq: str | None = None) -> bytes | None:
        """Feature 0x05 (calibração da IMU) do controle `uniq` (None = primário).

        GYRO-01: é o report que o vpad carimba no blueprint para o
        `hid_playstation`/SDL calibrarem o motion espelhado com o bias e a
        sensibilidade DA UNIDADE que produz os bytes crus — o canônico
        embutido veio de UMA unidade e faz as outras drivarem.

        A leitura vai por HIDIOCGFEATURE direto no hidraw do handle (o mesmo
        caminho provado do `capture_dualsense_blueprint`), NÃO pelo
        `get_feature_report` da hidapi: o wrapper pure-python instalado faz
        ``return buf[1:]`` — descarta o byte do report id e devolve
        payload+pad, o que desmolduraria o report (e a validação por id
        passaria só quando o primeiro byte de payload por acaso fosse 0x05).
        O ioctl devolve o report EXATO do kernel, id incluído — byte-compatível
        com o `CANONICAL_FEATURE_0X05` do blueprint. Fd próprio e efêmero: zero
        contenção com o read do report_thread no handle da hidapi.

        Fail-safe por contrato: qualquer falha devolve None e o chamador fica
        no 0x05 canônico (vpad sempre nasce; drift leve tolerável). Modos de
        falha reais: BT ocioso responde EIO no GET_REPORT (timeout de 5 s do
        hidp — raro aqui, o report_thread mantém o link quente) e rádio
        corrompendo o report — por BT os 4 últimos bytes são CRC-32 (seed
        0xA3, `PS_FEATURE_CRC32_SEED` do kernel) e são VALIDADOS antes de
        aceitar: uma calibração corrompida carimbada no vpad quebraria o
        motion inteiro, não só o drift.
        """
        from hefesto_dualsense4unix.core.ds_output_report import (
            BT_FEATURE_CRC_SEED,
            bt_crc32,
        )

        with self._io_lock:
            key = self._primary_key if uniq is None else self._key_for_uniq(uniq)
            handle = self._handles.get(key) if key is not None else None
            if handle is None:
                return None
            transporte = self._detect_transport(handle)
            path = self.hidraw_path(uniq)
            if path is None:
                return None
            try:
                data = _read_feature_via_hidraw(
                    path,
                    _CALIBRATION_FEATURE_ID,
                    _CALIBRATION_FEATURE_SIZE,
                    opener=self._feature_opener,
                )
            except OSError as exc:
                logger.info("calibration_read_failed", key=key, err=str(exc))
                return None
        if len(data) != _CALIBRATION_FEATURE_SIZE or data[0] != _CALIBRATION_FEATURE_ID:
            logger.warning(
                "calibration_report_invalido", key=key, tamanho=len(data)
            )
            return None
        if transporte == "bt":
            crc = int.from_bytes(data[-4:], "little")
            if bt_crc32(data[:-4], seed=BT_FEATURE_CRC_SEED) != crc:
                logger.warning("calibration_crc_invalido", key=key)
                return None
        return data

    @property
    def primary_uniq(self) -> str | None:
        """MAC do dono do posto de P1: o primário, ou quem a vaga espera (None sem serial).

        FEAT-DSX-CONTROLLER-IDENTITY-01: identidade universal do controle —
        a mesma usada pelo `discover_dualsense_evdevs` (uniq do evdev) e pelo
        `sysfs_leds` (HID_UNIQ). Key de fallback por path retorna None.

        M3 (auditoria): delega a `_key_to_uniq`, que tem a guarda de 12 dígitos
        hex — `norm_mac('/dev/hidraw3')` devolvia um pseudo-MAC ('deda3'), e um
        pseudo-MAC != None furava o guard anti-input-dobrado do co-op
        (coop.py: `primary is None or primary.startswith('path:')`), spawnando um
        jogador secundário NO PRÓPRIO controle do primário. Com None, o guard
        adia o spawn até o MAC real resolver — como a docstring sempre prometeu.
        """
        return self._uniq_do_dono_do_posto()


    @property
    def _ds(self) -> pydualsense | None:
        """Handle do controle PRIMÁRIO (ou None se nenhum conectado)."""
        key = self._primary_key
        return self._handles.get(key) if key is not None else None

    @_ds.setter
    def _ds(self, value: pydualsense | None) -> None:
        with self._io_lock:
            if value is None:
                self._handles.clear()
                self._primary_key = None
            else:
                self._handles = {"_primary": value}
                self._primary_key = "_primary"


    @property
    def _desired(self) -> _DesiredOutput:
        """Alias de compatibilidade → `_desired_default` (padrão broadcast)."""
        return self._desired_default

    def set_auto_output_provider(
        self, fn: Callable[[str], _DesiredOutput | None] | None
    ) -> None:
        """Injeta (ou remove, com None) o provider da camada AUTOMÁTICA (COR-03)."""
        with self._io_lock:
            self._auto_output_provider = fn
        avisar = getattr(fn, "avisar_quando_a_automatica_mudar", None)
        if callable(avisar):
            avisar(self.reassert_resolved_outputs)

    def set_feature_opener(self, fn: Callable[[str], int] | None) -> None:
        """Injeta (ou remove, com None) o opener broker-aware da feature 0x05."""
        with self._io_lock:
            self._feature_opener = fn

    def set_exposicao_do_no(
        self, fn: Callable[[str], AbstractContextManager[bool]] | None
    ) -> None:
        """Injeta (ou remove, com None) a fábrica de exposição do nó hidraw.

        O-NO-NASCE-FECHADO-01 (20/09/2026) — irmã de `set_feature_opener`, e
        pela razão OPOSTA. Aquela existe porque o broker sabe servir um fd;
        esta existe porque o `hidapi` **não aceita fd**: o handle de controle
        nasce de `hidapi.Device(path=...)`, e com o nó do físico nascendo
        `0600 root` (`TAG-="uaccess"`) o `open(2)` de dentro do hidapi volta
        `EACCES` — para TODOS os controles. Este é o único bloqueador real da
        cura, e a única saída é o nó estar exposto DURANTE o open.

        O daemon injeta `make_exposicao_factory(daemon)` (broker primeiro,
        contexto inócuo quando não há broker). Consultado por `_open_one`.
        """
        with self._io_lock:
            self._exposicao_do_no = fn

    def set_primary_change_observer(
        self, fn: Callable[[str | None, str | None], None] | None
    ) -> None:
        """Injeta (ou remove, com None) quem é AVISADO da troca de primário."""
        with self._io_lock:
            self._primary_change_observer = fn

    def _avisar_troca_de_primario(self, anterior: str | None, novo: str | None) -> None:
        """Chama o observador de troca de primário. Nunca propaga exceção."""
        fn = self._primary_change_observer
        if fn is None:
            return
        try:
            fn(anterior, novo)
        except Exception as exc:
            logger.warning(
                "primary_change_observer_falhou",
                anterior=anterior,
                novo=novo,
                err=str(exc),
            )

    def set_game_authority_provider(
        self, fn: Callable[[], str] | None
    ) -> None:
        """Injeta (ou remove, com None) o provider da autoridade de exibição."""
        with self._io_lock:
            self._game_authority_provider = fn

    def _game_wins(self) -> bool:
        """True quando a camada GAME participa do merge (autoridade ≠ 'daemon')."""
        provider = self._game_authority_provider
        if provider is None:
            return True
        try:
            return provider() != "daemon"
        except Exception as exc:
            logger.debug("game_authority_provider_falhou", err=str(exc))
            return True

    def _resolvido_do_daemon(
        self, key: str, *, incluir_coop: bool = True
    ) -> _ResolvidoDoDaemon:
        """As camadas do DAEMON de `key`, sem a GAME e sem a regra de cor única."""
        return self._resolvido_do_uniq(
            self._key_to_uniq(key), incluir_coop=incluir_coop
        )

    def _resolvido_do_uniq(
        self, uniq: str | None, *, incluir_coop: bool = True
    ) -> _ResolvidoDoDaemon:
        """As camadas do DAEMON de `uniq`, sem a GAME e sem a regra de cor única."""
        override = self._desired_by_uniq.get(uniq) if uniq is not None else None
        base = self._desired_default
        self._assentar_mesa_locked()
        auto: _DesiredOutput | None = None
        provider = self._auto_output_provider
        if provider is not None and uniq is not None:
            try:
                auto = provider(uniq)
            except Exception as exc:
                logger.debug(
                    "auto_output_provider_falhou", uniq=uniq, err=str(exc)
                )
                auto = None
            if auto is not None:
                base = _merge_desired(base, auto)
        if uniq is not None:
            base = self._scaled_led(uniq, base)
        resolved = _merge_desired(base, override)
        coop: _DesiredOutput | None = None
        cor_do_numero: tuple[int, int, int] | None = None
        cor_do_plastico: tuple[int, int, int] | None = None
        if uniq is not None:
            if incluir_coop:
                coop = self._desired_coop_by_uniq.get(uniq)
                resolved = _merge_desired(resolved, coop)
            if auto is not None and auto.led is not None:
                automatica = self._scaled_led(uniq, _DesiredOutput(led=auto.led)).led
                do_numero = self._cor_do_numero_do_provider(uniq)
                if self._tom_do_plastico(uniq) is not None and do_numero is not None:
                    cor_do_plastico = automatica
                    cor_do_numero = self._scaled_led(
                        uniq, _DesiredOutput(led=do_numero)
                    ).led
                else:
                    cor_do_numero = automatica
        procedencia: object = DO_GLOBAL
        if auto is not None and auto.led is not None:
            procedencia = DA_PALETA
        if override is not None and override.led is not None:
            procedencia = getattr(self, "_procedencia_da_cor", {}).get(uniq, LEGADO)
        if coop is not None and coop.led is not None:
            procedencia = DA_MAO
        return _ResolvidoDoDaemon(
            resolved, cor_do_numero, procedencia, self._numero_do_slot(uniq),
            cor_do_plastico,
        )

    def _tom_do_plastico(self, uniq: str | None) -> tuple[int, int, int] | None:
        """O tom do plástico de `uniq`, pela companheira do provider — ou None."""
        consulta = getattr(self._auto_output_provider, "tom_do_plastico", None)
        if uniq is None or not callable(consulta):
            return None
        with contextlib.suppress(Exception):
            tom = consulta(uniq)
            if isinstance(tom, tuple) and len(tom) == 3:
                return (int(tom[0]), int(tom[1]), int(tom[2]))
        return None

    def _cor_do_numero_do_provider(self, uniq: str) -> tuple[int, int, int] | None:
        """A cor do número de `uniq` no brilho do perfil, pela companheira."""
        consulta = getattr(self._auto_output_provider, "cor_do_numero", None)
        if not callable(consulta):
            return None
        with contextlib.suppress(Exception):
            cor = consulta(uniq)
            if isinstance(cor, tuple) and len(cor) == 3:
                return (int(cor[0]), int(cor[1]), int(cor[2]))
        return None

    def _numero_do_slot(self, uniq: str | None) -> int | None:
        """O número que `uniq` acende AGORA — ou `None` quando não há resposta."""
        if uniq is None:
            return None
        consulta = getattr(self._auto_output_provider, "numero_do_slot", None)
        if not callable(consulta):
            return None
        with contextlib.suppress(Exception):
            n = consulta(uniq)
            if isinstance(n, int) and not isinstance(n, bool):
                return n
        return None

    def _uniqs_da_mesa_locked(self) -> list[str]:
        """Quem está na mesa da regra de cor única, sem repetir."""
        vistos: list[str] = []

        def _juntar(candidato: object) -> None:
            if isinstance(candidato, str) and candidato and candidato not in vistos:
                vistos.append(candidato)

        fonte = getattr(self._auto_output_provider, "uniqs_da_mesa", None)
        if callable(fonte):
            with contextlib.suppress(Exception):
                for uniq in fonte():
                    _juntar(uniq)
        for uniq in list(self._desired_by_uniq):
            _juntar(uniq)
        for uniq in list(self._desired_coop_by_uniq):
            _juntar(uniq)
        for chave in list(getattr(self, "_handles", {})):
            _juntar(self._key_to_uniq(chave))
        return vistos

    def _mesa_de_cores_locked(self, *, incluir_coop: bool) -> list[PecaDaMesa]:
        """A mesa que a regra de cor única resolve, JÁ NA ORDEM QUE DECIDE.

        A ordem é o número do controle (o `rank` que a identidade persiste e
        que ela já vê na tela). Sem número — provider de teste, ou controle
        fora da mesa — a peça vai para o FIM, e lá a ordem cai no `uniq`, que
        é arbitrário mas ESTÁVEL: a garantia de que duas peças não ficam
        iguais não depende da ordem, só o *quem desloca* depende.

        Por que o número e não a ordem de `_handles`: `_handles` é ordem de
        HOTPLUG. Com ela, quem replugasse primeiro reivindicaria a cor do
        vizinho e a mesa inteira mudaria de cor a cada religada — o mesmo
        defeito que o `_assentar_mesa_locked` fechou no NÚMERO, de volta na
        COR. Ordenar pelo número torna a resposta função só do estado, que é
        o que impede a barra de piscar.

        **A COR GLOBAL ENTRA NA MESA**, e não entrava na primeira volta: o
        `if not r.cor_por_controle: continue` deixava de fora justamente o
        controle sem opinião própria, e um numerado em azul automático ao
        lado de um caído no azul global ficava dois `#0000FF`. Quem está no
        global entra marcado como `DO_GLOBAL` e cede a quem tem identidade,
        sem ceder à irmã que também está no global — que é o gesto "Todos"
        do perfil (D4) e continua de pé.
        """
        pecas: list[tuple[int, str, PecaDaMesa]] = []
        for uniq in self._uniqs_da_mesa_locked():
            r = self._resolvido_do_uniq(uniq, incluir_coop=incluir_coop)
            pecas.append((
                _SEM_NUMERO if r.numero is None else r.numero,
                uniq,
                PecaDaMesa(
                    uniq=uniq,
                    pedida=r.saida.led,
                    do_numero=r.cor_do_numero,
                    procedencia=r.procedencia,
                    numero=r.numero,
                    brilho=self._brilho_da_peca_locked(uniq),
                    do_plastico=r.cor_do_plastico,
                ),
            ))
        pecas.sort(key=lambda peca: (peca[0], peca[1]))
        return [peca for _, _, peca in pecas]

    def _com_cor_unica_locked(
        self, key: str, r: _ResolvidoDoDaemon, *, incluir_coop: bool
    ) -> _DesiredOutput:
        """Aplica a regra de cor única (`led_control.cores_sem_colisao`) à saída de `key`.

        A `D-DUAS-PECAS-NUNCA-TEM-A-MESMA-COR` que ela cumpria foi REVOGADA em
        09/09/2026 pela D-0909-X (a recusa mora no gesto); o que o resolvedor
        segue cumprindo é o fóssil de 08/09 e o salto ao tom livre, ver lá.

        A regra mora AQUI, no resolvedor, e não em cada gesto que grava cor:
        a leva de 08/09/2026 contou **dezenove** escritores de cor por
        controle (doze em `Profile.controllers[...]`, quatro no mapa vivo
        `_desired_by_uniq`, mais as camadas co-op, jogo e automática). Curar
        um deixaria dezoito; o resolvedor é por onde os dezenove passam, e é
        o mesmo funil que alimenta a TELA (`resolved_led_for` →
        `lightbar_source == "desired"` do `state_full`). Uma linha cura o
        aparelho e a tela.

        FICA ABAIXO DA CAMADA GAME de propósito (R-20 item 2, mesma razão da
        escala de brilho): deslocar a cor que o jogo pediu seria mentir sobre
        o que ele pediu. O jogo pinta por cima da regra, como já pinta por
        cima do brilho.
        """
        if r.saida.led is None:
            return r.saida
        uniq = self._key_to_uniq(key)
        if uniq is None:
            return r.saida
        mesa = self._mesa_de_cores_locked(incluir_coop=incluir_coop)
        cor = cores_sem_colisao(mesa).get(uniq)
        if cor is None or cor == r.saida.led:
            return r.saida
        return replace(r.saida, led=cor)

    def _merged_desired_for_key(
        self, key: str, *, incluir_coop: bool = True
    ) -> _DesiredOutput:
        """Desired efetivo do controle `key`: MERGE POR CAMPO em 5 camadas."""
        uniq = self._key_to_uniq(key)
        resolved = self._com_cor_unica_locked(
            key,
            self._resolvido_do_daemon(key, incluir_coop=incluir_coop),
            incluir_coop=incluir_coop,
        )
        game = self._game_output_by_uniq.get(uniq) if uniq is not None else None
        if game is not None and self._game_wins():
            # O jogo manda; na ausência dele, o perfil ganha (decisão dela de
            # 03/10/2026, que revoga a PERFIL-MANDA-01 de 16/09). Só a numeração
            # do jogador é do Hefesto, e não se pinta pelo jogo.
            nao_pinta = numeracao_do_jogo(
                {nome: getattr(game, nome) for nome in _OUTPUT_FIELDS}
            )
            game = _sem_os_campos(game, nao_pinta)
            if game is not None:
                resolved = _merge_desired(resolved, game)
        return resolved

    def _assentar_mesa_locked(self) -> None:
        """Apresenta a mesa INTEIRA ao provider antes de numerar alguém.

        MESA-NO-MEIO-DO-LOTE-01 — a causa raiz medida em 27/08/2026, com os
        quatro DualSense dela no rádio. Toda escrita de LED por aqui é um
        LOTE: `enviar_gatilho_da_cor`, `reassert_resolved_outputs`, o
        priming de hotplug e o unmute resolvem `_merged_desired_for_key` de
        VÁRIAS chaves de uma vez, sob o mesmo `_io_lock`. E o provider de
        identidade não é uma leitura pura: ele ADMITE na mesa o controle que
        pergunta (`slot_for`, atribuição lazy do R-14 §1).

        Daí o defeito: o link de um controle caiu e voltou entre dois
        batimentos do `sync_connected` (~2 s). Quando o lote correu, os TRÊS
        primeiros foram numerados com a mesa de três — e o quarto, ao ser
        resolvido, entrou na mesa e foi numerado com a mesa de quatro.
        Resultado gravado no journal: dois controles com o padrão do jogador
        1, ninguém com o do 4. Ficou assim por 28 minutos, porque a lâmpada
        só é reescrita quando algo acontece.

        A cura é anterior ao número, não posterior: antes de o primeiro
        controle do lote perguntar o seu, TODOS são apresentados. A mesa
        deixa de se mexer no meio, e a tabela que o registro devolve é a
        mesma para todos do lote — que é a única forma de dois números não
        colidirem.

        Barato por contrato (`set_auto_output_provider`: sem I/O, só
        memória) e feito UMA vez por composição de `_handles`: enquanto os
        handles não mudam, isto é uma comparação de `frozenset`. A marca é
        gravada ANTES do laço de propósito — o provider não reentra aqui,
        mas a ordem torna a reentrância impossível em vez de improvável.

        **A APRESENTAÇÃO É NA ORDEM DE `_handles` (primário primeiro), nunca
        na do `frozenset`.** O conjunto é só para saber SE mudou; quem entra
        no laço é a ordem do dict. É a mesma regra do R-24 no
        `_sync_identity_registry` (*"nunca passar um `set`, que numeraria por
        hash"*) e ela morde igual aqui: com o `frozenset` no laço, dois
        controles virgens recebiam lugar na fila em ordem de hash, e o
        segundo da mesa nascia Controle 1.
        """
        atual = frozenset(self._handles)
        if atual == self._mesa_apresentada:
            return
        self._mesa_apresentada = atual
        provider = self._auto_output_provider
        if provider is None:
            return
        for chave in list(self._handles):
            uniq = self._key_to_uniq(chave)
            if uniq is None:
                continue
            with contextlib.suppress(Exception):
                provider(uniq)

    def _scaled_led(self, uniq: str, desired: _DesiredOutput) -> _DesiredOutput:
        """Aplica a escala de brilho por-uniq (R-20 item 2). Sob `_io_lock`.

        Devolve SEMPRE um objeto novo quando escala — `_merge_desired` pode
        ter devolvido o próprio `_desired_default` (quando não há override
        nem camada automática), e mutá-lo corromperia o padrão broadcast de
        todo mundo.

        **SÓ SOBRE A BASE** (o global e a automática), nunca sobre a cor
        resolvida — A-BARRA-NAO-ESCURECE-AO-REAPLICAR-01, 25/09/2026. O fator é
        RELATIVO ao brilho do perfil (`brilho_do_controle / brilho_global`,
        `manager._controllers_to_led_scales`) e só tem sentido sobre uma cor
        que chegou no brilho do perfil. O override por controle chega no
        brilho dele, e escalá-lo de novo era o defeito: o trilho acendia o P1
        a 60% em (0,0,153), o perfil reaplicado o levava a (0,0,111), e o
        trilho seguinte a 40% publicava (0,0,74) em vez de (0,0,102). Quem
        tinha cor gravada não escurecia porque o manager não lhe publicava
        fator — a guarda estava na ponta errada.
        """
        fator = self._led_scale_by_uniq.get(uniq)
        if fator is None or desired.led is None:
            return desired
        base = self._brilho_do_perfil
        para = self._brilho_da_peca_locked(uniq)
        if base is not None and para is not None:
            r, g, b = desired.led
            extras = tuple(
                tom for tom in (self._cor_do_perfil, self._tom_do_plastico(uniq))
                if tom is not None
            )
            return replace(
                desired,
                led=reescalar((int(r), int(g), int(b)), base, para, extras),
            )
        r, g, b = desired.led
        return replace(
            desired,
            led=LedSettings(lightbar=(int(r), int(g), int(b))).apply_brightness(
                fator
            ).lightbar,
        )

    def _clear_layer_locked(self, layer: str) -> None:
        """Solta os campos cuja procedência é `layer`. Sob `_io_lock` (R-20).

        Cada camada é limpa pelo SEU dono — é o que impede a ativação de
        perfil (que roda a cada troca de janela) de apagar o ajuste manual, e
        o "Aplicar" da GUI de apagar o que veio do perfil sem gesto dela.
        """
        for uniq, donos in list(self._desired_owner_by_uniq.items()):
            override = self._desired_by_uniq.get(uniq)
            for campo, dono in list(donos.items()):
                if dono != layer:
                    continue
                del donos[campo]
                if override is not None:
                    setattr(override, campo, None)
        self._prune_overrides_locked()

    def _stamp_owner_locked(self, uniq: str, campos: Any, layer: str) -> None:
        """Carimba a procedência dos campos escritos. Sob `_io_lock` (R-20).

        O jogo manda; na ausência dele, o perfil ganha (decisão dela de
        03/10/2026, que revoga a PERFIL-MANDA-01 de 16/09): o perfil carimbado
        não tira o que o jogo pintou. O GESTO dela na interface (`usuaria`) é
        a ordem mais nova, e vale o último que mandou (por delegação, a validar
        por ela): ele solta o que o jogo pintou NAQUELES campos, até o jogo
        pintar de novo.
        """
        donos = self._desired_owner_by_uniq.setdefault(uniq, {})
        for campo in campos:
            donos[campo] = layer
        if layer == _LAYER_USER:
            self._o_gesto_solta_o_que_o_jogo_pintou_locked(uniq, tuple(campos))

    def _o_gesto_solta_o_que_o_jogo_pintou_locked(
        self, uniq: str, campos: tuple[str, ...]
    ) -> None:
        """Tira da camada do jogo os campos que o gesto dela acabou de escrever."""
        game = self._game_output_by_uniq.get(uniq)
        if game is not None:
            restante = _sem_os_campos(game, frozenset(campos))
            if restante is None:
                self._game_output_by_uniq.pop(uniq, None)
            else:
                self._game_output_by_uniq[uniq] = restante
        lados = [
            ("left" if campo == "trigger_left" else "right")
            for campo in campos
            if campo in ("trigger_left", "trigger_right")
        ]
        if not lados:
            return
        do_jogo = self._game_triggers_by_uniq.get(uniq)
        key = self._key_for_uniq(uniq)
        handle = self._handles.get(key) if key is not None else None
        for lado in lados:
            if do_jogo is not None:
                do_jogo.pop(lado, None)
            if handle is not None:
                atributo = "_raw_trigger_left" if lado == "left" else "_raw_trigger_right"
                with contextlib.suppress(Exception):
                    setattr(handle, atributo, None)
        if do_jogo is not None and not do_jogo:
            self._game_triggers_by_uniq.pop(uniq, None)

    def _pode_defender_locked(self) -> bool:
        """A defesa de exibição (NUMA-03) já pode repintar? Sob `_io_lock`.

        O rate-limit é o de `DEFEND_DISPLAY_MIN_INTERVAL_S`, e quem o consulta é
        a réplica retida sob 'daemon'. É função para não haver duas contas do
        mesmo relógio: duas cópias da mesma aritmética foi como o `rumble`
        ganhou duas memórias, e a casa pagou.
        """
        agora = time.monotonic()
        return (
            self._defend_last_at is None
            or (agora - self._defend_last_at) >= DEFEND_DISPLAY_MIN_INTERVAL_S
        )

    def _carimbar_procedencia_locked(
        self,
        uniq: str,
        cor: Any,
        declarada: object,
        *,
        deduzir_todos: bool = False,
    ) -> None:
        """Grava PARA QUAL NÚMERO esta cor foi escolhida. Sob `_io_lock`."""
        carimbos = getattr(self, "_procedencia_da_cor", None)
        if carimbos is None:
            carimbos = self._procedencia_da_cor = {}
        if declarada is not None:
            carimbos[uniq] = declarada
            return
        if deduzir_todos and cor is not None and cor == self._desired_default.led:
            carimbos[uniq] = DO_BROADCAST
            return
        numero = self._numero_do_slot(uniq)
        carimbos[uniq] = DA_MAO if numero is None else numero

    def _prune_overrides_locked(self) -> None:
        """Poda overrides/carimbos que ficaram vazios. Sob `_io_lock`."""
        self._desired_by_uniq = {
            uniq: override
            for uniq, override in self._desired_by_uniq.items()
            if any(getattr(override, name) is not None for name in _OUTPUT_FIELDS)
        }
        self._desired_owner_by_uniq = {
            uniq: donos for uniq, donos in self._desired_owner_by_uniq.items() if donos
        }
        self._procedencia_da_cor = {
            uniq: proc
            for uniq, proc in getattr(self, "_procedencia_da_cor", {}).items()
            if getattr(self._desired_by_uniq.get(uniq), "led", None) is not None
        }
        self._brilho_da_cor = {
            uniq: (cor, brilho)
            for uniq, (cor, brilho) in getattr(self, "_brilho_da_cor", {}).items()
            if getattr(self._desired_by_uniq.get(uniq), "led", None) == cor
        }

    def _carimbar_o_brilho_locked(
        self, uniq: str, cor: Any, brilho: float | None
    ) -> None:
        """Guarda o brilho em que a cor da mão dela foi mandada. Sob `_io_lock`."""
        carimbos = getattr(self, "_brilho_da_cor", None)
        if carimbos is None:
            carimbos = self._brilho_da_cor = {}
        if brilho is None or cor is None:
            carimbos.pop(uniq, None)
            return
        r, g, b = (int(c) for c in tuple(cor)[:3])
        carimbos[uniq] = ((r, g, b), max(0.0, min(1.0, float(brilho))))

    def _record_desired_locked(self, target_key: str | None, fields: dict[str, Any]) -> None:
        """Grava campos do estado desejado no escopo CERTO. Chamar sob `_io_lock`."""
        if target_key is not None:
            uniq = self._key_to_uniq(target_key)
            if uniq is None:
                logger.debug(
                    "desired_por_controle_sem_mac",
                    key=target_key,
                    campos=sorted(fields),
                )
                return
            override = self._desired_by_uniq.setdefault(uniq, _DesiredOutput())
            for name, value in fields.items():
                setattr(override, name, value)
            self._stamp_owner_locked(uniq, fields, _LAYER_USER)
            if "led" in fields:
                self._carimbar_procedencia_locked(uniq, fields["led"], None)
            return
        for name, value in fields.items():
            setattr(self._desired_default, name, value)
            for override in self._desired_by_uniq.values():
                setattr(override, name, None)
            for donos in self._desired_owner_by_uniq.values():
                donos.pop(name, None)
        self._prune_overrides_locked()


    @staticmethod
    def _enumerate_device_keys() -> list[tuple[str, bytes, bool]]:
        """Retorna `[(key, path, is_edge)]` de TODOS os DualSense plugados.

        `key` é a identidade PERSISTENTE do controle: o `serial_number`
        (== MAC, estável entre replug/troca de porta) quando disponível, com
        fallback para o `path` (estável por porta) quando o firmware não expõe
        serial em USB. Faz dedupe por device (uma mesma controladora pode
        enumerar múltiplas interfaces HID).

        O-CABO-ASSUME-DO-RADIO-01 (25/09/2026): o MESMO controle nos dois
        transportes é a mesma key em dois nós, e o dedupe ficava com o que o
        hidapi listasse primeiro — sorteio de enumeração. Agora vence o cabo
        (decisão dela: no cabo há a vibração por áudio, o som e menos atraso).
        O kernel de hoje recusa o segundo nó (`ps_devices_list_add`, -EEXIST),
        então os dois só aparecem juntos num kernel que não recuse; a regra
        existe para a escolha nunca ser do sorteio.

        SEAM de teste: stubável para `[]` (offline) ou uma lista fixa.
        """
        import hidapi

        out: list[tuple[str, bytes, bool]] = []
        posicao: dict[str, int] = {}
        for info in hidapi.enumerate(vendor_id=DUALSENSE_VENDOR):
            if info.product_id not in DUALSENSE_PIDS:
                continue
            if _is_virtual_hidraw(info.path):
                continue
            # hidapi: serial_number vem de wchar_t* → str (ou None); path vem de
            serial = info.serial_number
            key = serial if serial else info.path.decode("utf-8", "replace")
            entrada = (key, info.path, info.product_id == DUALSENSE_EDGE_PID)
            if key in posicao:
                if _o_cabo_vence(info.path, out[posicao[key]][1]):
                    out[posicao[key]] = entrada
                continue
            posicao[key] = len(out)
            out.append(entrada)
        return out

    def _open_one(self, path: bytes, *, is_edge: bool) -> pydualsense | None:
        """Abre UM controle por `path`, DENTRO de uma exposição do nó.

        O-NO-NASCE-FECHADO-01 (20/09/2026). Com a regra udev da cura, o nó do
        DualSense físico nasce `0600 root` e o `hidapi.Device(path=...)` que
        abre este handle volta `EACCES` — o hidapi não aceita fd, e reabrir
        por `/proc/self/fd/N` refaz a checagem de permissão no inode, então
        não há como reapontar isto para o broker. O que há é pedir ao broker
        que exponha o nó, abrir, e soltar o pedido: é o que este `with` faz.

        A janela cobre o `join` do runner, não o runner inteiro — um `init()`
        que estoure o timeout e abra DEPOIS encontra o nó já fechado e falha,
        e essa falha é tratada pelo handoff atômico que já existia (o handle
        órfão é fechado pela própria thread). Alargar a janela até a thread
        acabar seria manter o físico aberto por tempo indeterminado, que é
        exatamente a janela que a cura fecha.

        Sem fábrica injetada (CLI, dublê, máquina sem a cura instalada) o
        contexto é inócuo e o comportamento é o histórico: abre por caminho.
        """
        exposicao = self._exposicao_do_no
        no = path.decode("utf-8", "replace")
        if exposicao is None or not no.startswith("/dev/hidraw"):
            return self._abrir_handle_pinado(path, is_edge=is_edge)
        try:
            contexto = exposicao(no)
        except Exception as exc:
            logger.warning("exposicao_do_no_falhou", path=no, err=str(exc))
            return self._abrir_handle_pinado(path, is_edge=is_edge)
        with contexto:
            return self._abrir_handle_pinado(path, is_edge=is_edge)

    def _abrir_handle_pinado(self, path: bytes, *, is_edge: bool) -> pydualsense | None:
        """Abre UM controle por `path`, com a guarda de timeout do init."""
        ds = _PinnedPyDualSense(path, is_edge=is_edge)
        result: list[Exception | None] = []
        entrega = threading.Lock()
        estado = {"terminou": False, "desistido": False}

        def _runner() -> None:
            erro: Exception | None = None
            try:
                ds.init()
            except Exception as exc:
                erro = exc
            with entrega:
                orfao = estado["desistido"]
                if not orfao:
                    estado["terminou"] = True
                    result.append(erro)
            if orfao:
                with contextlib.suppress(Exception):
                    ds.close()
                logger.warning(
                    "pydualsense_init_orfao_fechado — o handle do init que "
                    "estourou o timeout foi fechado pela própria thread",
                    path=path,
                )

        t = threading.Thread(target=_runner, daemon=True, name="hefesto-ds-init")
        t.start()
        t.join(timeout=INIT_TIMEOUT_SEC)
        with entrega:
            desistiu = not estado["terminou"]
            if desistiu:
                estado["desistido"] = True
        if desistiu:
            logger.warning(
                "pydualsense_init_timeout — kernel pode estar bloqueado em "
                "hidraw (hid_playstation conflict)",
                path=path,
                timeout_sec=INIT_TIMEOUT_SEC,
            )
            return None
        exc = result[0] if result else None
        if exc is not None:
            # `pydualsense.__find_device()` levanta `Exception("No device
            # detected")` (string match — não é subclasse dedicada). Aqui isso
            # significa corrida com unplug entre enumerate e open: trata como
            # ausência (None). Demais exceções propagam.
            if "No device detected" in str(exc):
                return None
            raise exc
        return ds

    # --- ciclo de vida / reconciliação (hotplug) ------------------------

    def connect(self) -> None:
        """Reconcilia os handles abertos com os controles fisicamente plugados.

        Idempotente e usado como TICK DE HOTPLUG pelo `reconnect_loop`:
          - controle novo → abre o handle e re-aplica o PERFIL ATIVO nele;
          - controle removido → fecha o handle (sem vazar) e promove o próximo
            mais antigo a primário se for o caso;
          - já presente → mantém intacto (não reabre);
          - já presente por OUTRO nó → troca o handle no MESMO lugar
            (O-CABO-ASSUME-DO-RADIO-01, ver `_o_no_mudou_locked`).
        """
        want = self._enumerate_device_keys()
        if not want:
            with self._io_lock:
                self._close_handles(keep=set())
                self._recompute_primary()
                self._offline = True
            return

        want_keys = {key for key, _, _ in want}
        caminho_pedido = {key: path for key, path, _ in want}
        with self._io_lock:
            # hotplug-OUT: fecha tudo que sumiu (sem vazar handle/thread).
            self._close_handles(keep=want_keys)
            existing = set(self._handles)
            trocar = {
                key for key in existing if self._o_no_mudou_locked(key, caminho_pedido[key])
            }

        new_handles: list[tuple[str, pydualsense]] = []
        trocados: dict[str, str] = {}
        for key, path, is_edge in want:
            if key in existing and key not in trocar:
                continue
            with self._io_lock:
                if key in self._opening or (key in self._handles and key not in trocar):
                    continue
                self._opening.add(key)
            try:
                handle = self._open_one(path, is_edge=is_edge)
                if handle is None:
                    continue
                dup: pydualsense | None = None
                antigo: pydualsense | None = None
                with self._io_lock:
                    if key in trocar and self._o_no_mudou_locked(key, path):
                        antigo = self._handles[key]
                        self._handles[key] = handle
                    elif key in self._handles:
                        dup = handle
                    else:
                        self._handles[key] = handle
                if dup is not None:
                    with contextlib.suppress(Exception):
                        dup.close()
                    continue
                if antigo is not None:
                    trocados[key] = self._detect_transport(antigo)
                    with contextlib.suppress(Exception):
                        antigo.close()
                    self._levar_ao_mapa_a_posse_que_a_mao_soltou(key, antigo)
                    logger.info(
                        "handle_trocado_de_no",
                        uniq=_endereco_mascarado(self._key_to_uniq(key)),
                        antes=trocados[key],
                        agora=self._detect_transport(handle),
                    )
                new_handles.append((key, handle))
            except Exception as exc:
                logger.debug("backend_open_one_failed", key=key, err=str(exc))
                continue
            finally:
                with self._io_lock:
                    self._opening.discard(key)

        with self._io_lock:
            self._recompute_primary()
            if self._primary_key in trocados:
                self._religar_o_primario_trocado_locked()
            self._anotar_os_transportes_locked(new_handles, trocados)
            self._offline = not self._handles
            n = max(1, len(self._handles))
            throttle = min(
                REPORT_THREAD_THROTTLE_SEC * n, REPORT_THREAD_THROTTLE_MAX_SEC
            )
            for handle in self._handles.values():
                with contextlib.suppress(Exception):
                    handle._throttle_sec = throttle
                    handle._output_muted = self._output_mute
        novas_bt = 0
        for _key, handle in new_handles:
            with contextlib.suppress(Exception):
                if self._detect_transport(handle) == "bt":
                    novas_bt += 1
        if novas_bt:
            with self._io_lock:
                self._conexoes_bt_novas += novas_bt
        # derruba o claim da lightbar no FIRMWARE do DualSense por BT — a
        # `core/lightbar_reset.py` — não se apaga decisão medida, e o layout do
        # report BT que eles documentam continua correto e validado. O que
        # caducou é MANDÁ-LO. Ver a sprint LIGHTBAR-BT-CULPADO-01 e o estudo
        # `2026-08-03-a-noite-em-que-medimos-a-lightbar-do-bluetooth.md`.

        # LIGHTBAR-BT-RESET-02 (Onda L): o 0x08 acima só cobre handles NOVOS. Um
        # wake/resume BT que NÃO reabre o handle também derruba o claim do
        # firmware (o kernel reseta a classe LED para KERNEL_DEFAULT_BLUE, mesmo
        # indicator_dir, logo NÃO é new_key — caso medido 2026-07-20 17:28).
        # Reenvia o 0x08 SÓ na assinatura do wake (nó sysfs voltou ao default do
        # kernel com o desired resolvido diferente); o reassert logo abaixo
        # re-cola cor E player LEDs. Nunca por timer — evita flicker de quem tem
        # o claim intacto. Snapshot sob lock, I/O de nó/handle fora dele (padrão
        # do reassert). Best-effort: falha = sintoma antigo, sem regressão.
        new_keys = {k for k, _ in new_handles}
        with self._io_lock:
            reclaim_candidates = (
                []
                if self._output_mute
                else [
                    (
                        key,
                        handle,
                        self._sysfs.get(key),
                        self._merged_desired_for_key(key),
                        self._detect_transport(handle),
                    )
                    for key, handle in self._handles.items()
                    if key not in new_keys
                ]
            )
        for key, _handle, node, desired, transport in reclaim_candidates:
            with contextlib.suppress(Exception):
                from hefesto_dualsense4unix.core.lightbar_reset import (
                    should_reclaim_on_wake,
                )

                current = node.get_rgb() if node is not None else None
                reclamar = should_reclaim_on_wake(
                    transport, desired.led, current, KERNEL_DEFAULT_BLUE
                )
                logger.debug(
                    "lightbar_reclaim_avaliado",
                    key=key,
                    transport=transport,
                    current=current,
                    desired=desired.led,
                    kernel_default=KERNEL_DEFAULT_BLUE,
                    reclamar=reclamar,
                )
                if reclamar:
                    logger.debug("lightbar_reclaim_gatilho_disparou_sem_acao", key=key)

        self._refresh_sysfs_leds()
        for key, handle in new_handles:
            with contextlib.suppress(Exception):
                self.assumir_volume_padrao_na_adocao(key, handle)
            self._reapply_desired(key, handle)
        # acabaram de surgir. Sintoma provado ao vivo: boot com os DualSense
        self.reassert_resolved_outputs()

    def _close_handles(self, keep: set[str]) -> None:
        """Fecha (e remove) os handles cujas chaves não estão em `keep`."""
        saindo: list[tuple[str, Any]] = []
        for key in [k for k in self._handles if k not in keep]:
            handle = self._handles.pop(key)
            self._segurar_a_volta_pelo_radio_locked(key, handle)
            saindo.append((key, handle))
        _fechar_os_handles_juntos(handle for _key, handle in saindo)
        for key, handle in saindo:
            self._levar_ao_mapa_a_posse_que_a_mao_soltou(key, handle)
        if self._primary_key is not None and self._primary_key not in self._handles:
            self._reservar_o_posto_de_primario(self._primary_key)
            self._primary_key = None


    def _reservar_o_posto_de_primario(self, key: str) -> None:
        """Guarda o posto de primário para `key`, que acabou de cair."""
        self._primario_deposto = (key, self._relogio())
        logger.info("primario_deposto_reservado", key=key, transporte=self._transport)

    def _posto_reservado_de_volta(self) -> str | None:
        """A key do primário deposto, se ele VOLTOU dentro da janela. Senão None.

        Também é aqui que a reserva CADUCA: passou de `PRIMARIO_RESERVA_SEC`,
        ela é esquecida — o posto não fica pendurado num controle que ficou na
        gaveta, e o próximo `next(iter(...))` volta a valer sem concorrência.

        A caducidade é `info` pela mesma razão da reserva (ver
        `_reservar_o_posto_de_primario`): ela é o desfecho ALTERNATIVO da
        retomada, e um journal que só registra o desfecho bom não mede coisa
        nenhuma. **A constante `PRIMARIO_RESERVA_SEC` não se mexe aqui** — o
        valor só se decide depois da bancada, e a bancada é dela.
        """
        reserva = self._primario_deposto
        if reserva is None:
            return None
        key, quando = reserva
        if self._relogio() - quando >= PRIMARIO_RESERVA_SEC:
            self._primario_deposto = None
            logger.info("primario_reserva_caducou", key=key)
            return None
        if key not in self._handles or key == self._primary_key:
            return None
        return key

    def _recompute_primary(self) -> None:
        """(Re)elege o primário e re-atrela evdev/transport SÓ quando ele muda.

        Primário = o controle da CARTA MENOR na mesa (`_quem_senta_no_posto`): a
        lâmpada que acende o «1» manda, e o primeiro que conectou não manda mais
        (O-MODO-XBOX-NAO-E-QUEDA-02). Sem carta, a 1ª chave de inserção. Chamado
        sob `_io_lock`. A vaga com o jogo aberto também é de `_quem_senta_no_posto`.

        COOP-QUE-NAO-DESMONTA-01 / E2(a) — **com UMA exceção à regra da 1ª
        chave**: o controle que ERA o primário e voltou dentro de
        `PRIMARIO_RESERVA_SEC` RETOMA o posto, mesmo já havendo outro sentado
        nele. Sem isso, quem cai entra no fim do dict e nunca mais é o Jogador
        1 — e no rádio, onde cair é rotina, quem é o Jogador 1 depois de
        algumas piscadas é essencialmente sorteio. Controle NOVO (sem carta, ou
        com a carta do fim da fila) segue sem roubar o posto de ninguém.

        A armadilha que a sprint nomeou fica coberta por construção: a retomada
        entra pelo MESMO caminho da promoção, então `_detect_transport` e o
        `retarget` do evdev são refeitos igual. Um atalho que devolvesse o posto
        sem passar por aqui deixaria o daemon achando que o controle está no
        cabo quando ele voltou por rádio.

        COOP-QUE-NAO-DESMONTA-01 / E1 — e o AVISO sai daqui, antes do
        `retarget`: ver `set_primary_change_observer`.
        """
        prev = self._primary_key
        retomada = self._posto_reservado_de_volta()
        if retomada is not None:
            self._primary_key, self._posto_vago_de = retomada, None
            self._primario_deposto = None
            logger.info("primario_retomou_o_posto", key=retomada)
        else:  # o posto vazio, ou a carta menor na mesa (O-MODO-XBOX-NAO-E-QUEDA-02)
            self._primary_key = self._quem_senta_no_posto(sentado=self._primary_key)
        if self._primary_key is None or self._primary_key == prev:
            return
        # E1: o co-op precisa SOLTAR o node do controle que virou primário
        # ANTES de o leitor do primário mirar nele. Depois do retarget é tarde:
        # o `EBUSY` já aconteceu, e quem morre é o Jogador 2 que já existia.
        self._avisar_troca_de_primario(
            self._key_to_uniq(prev) if prev else None, self.primary_uniq
        )
        # Trocou o primário: re-detecta transport e re-atrela o evdev a ele.
        self._transport = self._detect_transport(self._handles[self._primary_key])
        self._evdev.retarget(self.primary_uniq)
        self._evdev.refresh_device()
        if self._motion_reader is not None:
            with contextlib.suppress(Exception):
                self._motion_reader.request_reopen("primary_changed")
        if self._evdev.is_available():
            self._evdev.start()
            logger.info("controller_primary_bound", transport=self._transport, with_evdev=True)
        else:
            logger.info(
                "controller_primary_bound",
                transport=self._transport,
                with_evdev=False,
                hint="input pode ficar zerado se kernel hid_playstation capturar evdev",
            )

    def disconnect(self) -> None:
        with contextlib.suppress(Exception):
            self._evdev.stop()
        with self._io_lock:
            saindo = [(key, self._handles.pop(key)) for key in list(self._handles)]
            _fechar_os_handles_juntos(handle for _key, handle in saindo)
            for key, handle in saindo:
                self._levar_ao_mapa_a_posse_que_a_mao_soltou(key, handle)
            # E2(a): o `reconnect()` do poll loop é disconnect + connect — do
            if self._primary_key is not None:
                self._reservar_o_posto_de_primario(self._primary_key)
            self._primary_key = None
            self._sysfs = {}

    def _refresh_sysfs_leds(self) -> None:
        """(Re)mapeia cada handle ao seu nó LED do kernel (FEAT-DSX-LIGHTBAR-SYSFS-01)."""
        from hefesto_dualsense4unix.core import sysfs_leds

        try:
            by_mac = sysfs_leds.discover()
        except Exception as exc:
            logger.debug("sysfs_leds_discover_falhou", err=str(exc))
            by_mac = {}

        with self._io_lock:
            keys = list(self._handles)
            handles = dict(self._handles)
            prev = self._sysfs

        mapping: dict[str, Any] = {}
        for key in keys:
            nk = sysfs_leds.norm_mac(key)
            node = by_mac.get(nk) if nk else None
            if node is not None and node.writable():
                mapping[key] = node

        uncovered = sorted(k for k in keys if k not in mapping)
        if set(mapping) != set(prev) or uncovered != getattr(
            self, "_led_uncovered_prev", None
        ):
            logger.info(
                "sysfs_led_cobertura",
                cobertos=sorted(mapping),
                sem_no_sysfs=uncovered,
            )
        self._led_uncovered_prev = uncovered

        for key, handle in handles.items():
            with contextlib.suppress(Exception):
                # `_suppress_leds` existe no _PinnedPyDualSense (handles de teste
                handle._suppress_leds = (
                    key in mapping or self._detect_transport(handle) == "bt"
                )

        def _node_dir(node: Any) -> Any:
            return getattr(node, "indicator_dir", None)

        new_keys = [
            k
            for k in mapping
            if k not in prev or _node_dir(prev[k]) != _node_dir(mapping[k])
        ]
        if new_keys:
            with self._io_lock:
                reasserts = [
                    (key, mapping[key], self._merged_desired_for_key(key))
                    for key in new_keys
                ]
            for key, node, desired in reasserts:
                with contextlib.suppress(Exception):
                    cor = desired.led if desired.led is not None else KERNEL_DEFAULT_BLUE
                    if node.set_rgb(*cor):
                        self.record_sysfs_write(key, cor)
                    if desired.player_leds is not None and (
                        self._pode_escrever_player_leds()
                    ):
                        node.set_players(desired.player_leds)

        with self._io_lock:
            self._sysfs = mapping
            self._sysfs_written = {
                key: rgb for key, rgb in self._sysfs_written.items() if key in mapping
            }

    def record_sysfs_write(self, key: str, rgb: tuple[int, int, int]) -> None:
        """Registra que NÓS escrevemos `rgb` na classe LED do controle `key`."""
        with self._io_lock:
            self._sysfs_written[key] = (int(rgb[0]), int(rgb[1]), int(rgb[2]))

    def is_connected(self) -> bool:
        with self._io_lock:
            handles = list(self._handles.values())
        return any(bool(getattr(h, "connected", False)) for h in handles)

    def alvos_conectados(self) -> dict[str, str | None]:
        """Os controles conectados AGORA, um por handle: `{key: uniq|None}`."""
        with self._io_lock:
            items = list(self._handles.items())
        return {
            key: self._key_to_uniq(key)
            for key, handle in items
            if bool(getattr(handle, "connected", False))
        }

    def heal_evdev_if_stale(self) -> bool:
        """Watchdog HID x evdev: se o evdev reader ficou preso num node OBSOLETO"""
        if not self._evdev.is_available():
            return False
        if self._evdev.is_stale():
            self._evdev.request_reopen("hid_connected_but_evdev_node_changed")
            return True
        return False

    def read_state(self) -> ControllerState:
        ds = self._ds if self._posto_vago_de is None else self._ds_depois_da_vaga()
        if ds is None:
            return ControllerState(
                **self._carga_do_posto_vago(),
                l2_raw=0,
                r2_raw=0,
                connected=self._posto_vago_de is not None,
                transport=self._transport,
                raw_lx=128,
                raw_ly=128,
                raw_rx=128,
                raw_ry=128,
                buttons_pressed=frozenset(),
            )
        self._transport = self._detect_transport(ds)
        battery, carga = self._ler_a_carga_do_posto(ds)
        if self._evdev.is_available():
            snap = self._evdev.snapshot()
            buttons = set(snap.buttons_pressed)
            try:
                if bool(getattr(ds.state, "micBtn", False)):
                    buttons.add("mic_btn")
            except AttributeError:
                logger.debug("ds_state_mic_btn_indisponivel_evdev_path", exc_info=True)
            buttons_pressed = frozenset(buttons)
            return ControllerState(
                battery_pct=battery, battery_state=carga,
                l2_raw=snap.l2_raw,
                r2_raw=snap.r2_raw,
                connected=self.is_connected(),
                transport=self._transport,
                raw_lx=snap.lx,
                raw_ly=snap.ly,
                raw_rx=snap.rx,
                raw_ry=snap.ry,
                buttons_pressed=buttons_pressed,
            )
        state = ds.state
        l2_raw = int(getattr(state, "L2_value", 0)) & 0xFF
        r2_raw = int(getattr(state, "R2_value", 0)) & 0xFF
        buttons_fallback: frozenset[str] = frozenset()
        try:
            if bool(getattr(state, "micBtn", False)):
                buttons_fallback = frozenset({"mic_btn"})
        except AttributeError:
            logger.debug("ds_state_mic_btn_indisponivel_fallback_path", exc_info=True)
        return ControllerState(
            battery_pct=battery, battery_state=carga,
            l2_raw=l2_raw,
            r2_raw=r2_raw,
            connected=self.is_connected(),
            transport=self._transport,
            raw_lx=_centered_stick_to_raw(state.LX),
            raw_ly=_centered_stick_to_raw(state.LY),
            raw_rx=_centered_stick_to_raw(state.RX),
            raw_ry=_centered_stick_to_raw(state.RY),
            buttons_pressed=buttons_fallback,
        )


    def alvo_de_output_ausente(self) -> str | None:
        """MAC (ou key) do alvo de output que está APONTADO mas fora da mesa.

        `None` quando o alvo é "Todos" ou quando o alvo escolhido está
        presente — ou seja: enquanto isto devolver `None`, uma escrita de
        output chega a alguém.

        Existe porque `get_output_target_index`/`get_output_target_uniq`
        MASCARAM esse estado (devolvem `None`, indistinguível de "Todos") — e
        quem precisa responder à usuária *"o Controle 2 não está na mesa,
        nada foi enviado"* precisa distinguir os dois. Não altero aqueles dois
        getters: eles alimentam o seletor da GUI e a rota do rumble por dono,
        que são de outra frente.

        **A metade "e DIZ" chegou em 24/08/2026 (BROADCAST-PROIBIDO-01,
        Z3-5).** `daemon/ipc_handlers.py::_handle_rumble_set` chama este
        método ANTES de `set_rumble` e recusa no molde da NATIVO-RUMBLE-01
        que já existia ali logo acima:

            {"status": "recusado", "desfecho": RUMBLE_RECUSADO_ALVO_AUSENTE,
             "motivo": MOTIVO_ALVO_FORA_DA_MESA, "weak": 0, "strong": 0}

        A redação de `MOTIVO_ALVO_FORA_DA_MESA`
        (`daemon/subsystems/rumble.py`) é a mesma que nasceu PROVISÓRIA aqui —
        *"O controle escolhido não está na mesa — nada foi enviado."* — e
        segue **PROVISÓRIA — decisão dela**: vai ao olho dela no lote da
        Onda 9, junto de RUM-1/RUM-2. Para led/gatilho/player não há redação
        nova: o valor fica guardado no override por-uniq, e o par
        `"registrado"` + *"Guardado — vai valer quando o Controle 2 voltar"*
        já é o léxico da casa (MESA-CHEIA-09).
        """
        with self._io_lock:
            alvo = self._output_target_key
            if alvo is None or alvo in self._handles:
                return None
        return self._key_to_uniq(alvo) or alvo

    def _for_each(
        self,
        op: Callable[[pydualsense], None],
        *,
        what: str,
        broadcast: bool = False,
        record: dict[str, Any] | None = None,
    ) -> None:
        """Aplica `op` ao ALVO de output (ou a cada handle aberto, em broadcast)."""
        with self._io_lock:
            target, handles, ausente = _resolver_escopo(
                self._handles, self._output_target_key, broadcast=broadcast
            )
            if record:
                self._record_desired_locked(target, record)
        if ausente is not None:
            logger.info(
                "output_alvo_ausente_noop", op=what, alvo=ausente, guardado=bool(record)
            )
            return
        if not handles:
            logger.debug("output_offline_noop", op=what)
            return
        for key, handle in handles:
            try:
                op(handle)
            except Exception as exc:
                logger.warning("output_handle_failed", op=what, key=key, err=str(exc))

    def _for_each_com_key(
        self,
        op: Callable[[pydualsense, str], None],
        *,
        what: str,
        broadcast: bool = False,
    ) -> None:
        """`_for_each` cuja `op` recebe a KEY do handle junto (POR-UNIDADE-01)."""
        with self._io_lock:
            _target, handles, ausente = _resolver_escopo(
                self._handles, self._output_target_key, broadcast=broadcast
            )
        if ausente is not None:
            logger.info("output_alvo_ausente_noop", op=what, alvo=ausente, guardado=False)
            return
        if not handles:
            logger.debug("output_offline_noop", op=what)
            return
        for key, handle in handles:
            try:
                op(handle, key)
            except Exception as exc:
                logger.warning("output_handle_failed", op=what, key=key, err=str(exc))

    def suprimir_player_leds(self, ativo: bool) -> bool:
        """Liga/desliga a escrita dos LEDs de JOGADOR. Instrumento de eliminação."""
        self._suprimir_player_leds = bool(ativo)
        logger.info("player_leds_suprimidos", ativo=self._suprimir_player_leds)
        return self._suprimir_player_leds

    def _pode_escrever_player_leds(self) -> bool:
        """False enquanto o instrumento de eliminação estiver ligado."""
        return not getattr(self, "_suprimir_player_leds", False)

    def enviar_release_leds(self, *, uniq: str | None = None) -> dict[str, bool]:
        """Manda o Reset LED state (0x08) SOB DEMANDA. É um INSTRUMENTO.

        LIGHTBAR-MEDIR-O-0X08-01 (08/08/2026). Ele existe porque duas medições
        desta casa se contradizem em aparência, e não havia como separá-las sem
        disputar o hidraw com o daemon — que é a armadilha nº 3 do
        `COMO-OLHAR-A-TELA.md` ("o instrumento pode estar brigando com o
        produto"). Aqui não há disputa: quem escreve é o handle que o daemon
        **já tem aberto**.

        As medições a conciliar:

        1. a adoção do controle derruba o claim da lightbar no firmware
           (17-18/07, `core/lightbar_reset.py:1-11`);
        2. o 0x08 mandado DENTRO da janela de ~3,4 s pós-conexão trava a barra
           — 7 de 7 (`LIGHTBAR-BT-CULPADO-01`, 03/08), e foi por isso que ele
           foi removido em `108b711` (04/08);
        3. o 0x08 mandado FORA dessa janela **não trava** (controle negativo da
           MESMA sprint).

        CORREÇÃO DATADA (11/08/2026), porque o item 3 tinha uma cauda FALSA
        -------------------------------------------------------------------
        Colada ao item 3 vinha a frase "e sem 0x08 nenhum a barra ficou morta
        por 5 dias e 20 adoções (medido 08/08)". Ela **nunca foi medição**: era
        uma frase que só existia em docstring e que eu registrei como se fosse
        uma — a armadilha `A-12` de `docs/method/METODO-DE-ISOLAMENTO.md`, "o
        caderno envelhecer sem que ninguém note".

        A escavação do journal do daemon e dos transcritos, em 11/08, achou a
        barra **ACESA** no rádio DENTRO daqueles cinco dias, quatro vezes, três
        delas com fala literal dela: 08/08 16:39, 08/08 21:35, 08/08 23:48 e
        11/08 11:40 (ensaios `lightbar-bt-aceso-*` em `docs/data/ensaios.csv`;
        a correção está registrada no ensaio `lightbar-bt-sem-0x08-cinco-dias`,
        e a nota datada em `docs/method/METODO-DE-ISOLAMENTO.md`, seção "O que
        ficou aberto nesta sessão — e o que 12/08 fechou").

        O que é VERDADE hoje sobre o 0x08:

        - ele está fora do caminho automático desde 04/08, e continua fora;
        - nesses cinco dias sem ele a barra **obedeceu**. Isso mantém o 0x08
          fora do banco dos réus, mas pela razão OPOSTA à que estava escrita;
        - a correlação de 03/08 segue de pé (7/7 dentro da janela), mas como
          causa SUFICIENTE da barra travada ela caiu em 11/08: no ensaio
          `lightbar-bt-sem-0x08-hoje-2300` (olho dela, daemon parado, escrita
          direta, sem 0x08 havia sete dias) os dois do cabo acenderam e **os
          dois do rádio não**;
        - em 12/08 nomeou-se a variável que faltava, e nenhuma das medições
          acima a tinha: **quem estava com o hidraw aberto no instante da
          probe** — e era o Steam. Ver o terceiro gabarito em
          `docs/method/METODO-DE-ISOLAMENTO.md`.

        A hipótese que este método torna falsificável na mesa dela — uma
        variável, um gesto, um olho —, e que segue sem ensaio que a feche:
        **o 0x08 devolve o claim, desde que não seja mandado em cima da
        conexão.**

        ``uniq`` restringe a um controle (o MAC/uniq do handle); ausente, manda
        a todos. Devolve ``{key: enviou?}`` — vazio significa nenhum handle
        aberto, que é resposta e não erro.

        NÃO é chamado por caminho automático nenhum: se um dia o reset voltar à
        adoção, ele volta lá, com a sua própria decisão e o seu próprio teste.
        """
        from hefesto_dualsense4unix.core.lightbar_reset import send_release_leds

        with self._io_lock:
            if uniq is not None:
                key = _casar_key(self._handles, uniq)
                alvos = [(key, self._handles[key])] if key is not None else []
            else:
                alvos = list(self._handles.items())
        resultado: dict[str, bool] = {}
        for key, handle in alvos:
            ok = send_release_leds(handle)
            resultado[key] = ok
            logger.info("lightbar_reset_sob_demanda", key=key, enviado=ok)
            if not ok:
                continue
            no = self._sysfs.get(key) if isinstance(self._sysfs, dict) else None
            invalidar = getattr(no, "invalidate_cache", None)
            if callable(invalidar):
                invalidar()
        return resultado

    def repintar_o_cabo_por_sysfs(self) -> dict[str, bool]:
        """Repinta a barra dos DualSense do CABO, ignorando o cache.

        LIGHTBAR-O-CABO-FICOU-DE-FORA-01, achado por ela na bancada de
        07/09/2026 com os quatro na mesa: *"o lightbar azul tá nos dois
        controles. p1 e p2. cada controle deve ter um lightbar da sua cor
        apenas"*.

        O IRMÃO DESTE MÉTODO SÓ CONHECE O RÁDIO. `reescrever_lightbar_por_hidraw`
        filtra por `_detect_transport(handle) == "bt"` — e está certo em
        filtrar: o report cru do 0x31 é a única via que pinta por Bluetooth. O
        do cabo é pintado pela CLASSE LED do kernel, e ninguém o repintava
        depois que a mesa se renumerava. Medido: o Cosmic Red foi adotado
        sozinho, ganhou o azul do lugar 1, e ficou azul depois de virar o
        lugar 2 — ao lado do Galactic Purple, que é o lugar 1 de verdade.

        E O CACHE É INVALIDADO ANTES, sempre. O `SysfsLeds` pula a escrita
        idêntica à última desta instância (GUERRA-01 item 3), e é uma boa
        regra — o reassert periódico deixa de martelar o firmware. Mas ela
        mede a COR, não o NÚMERO: quando a mesa se renumera, a cor que este
        controle deve ter mudou sem que a cor que ele TEM mudasse, e o cache
        acerta a pergunta errada. O journal dela mostrou exatamente isso:
        `lightbar_reassert_skip_cache rgb=(0, 0, 255)`.

        Devolve ``{key: repintado?}``. Vazio = nenhum DualSense no cabo —
        resposta, não erro. Vale no Modo Nativo também
        (`D-2309-NO-NATIVO-A-LUZ-E-O-NUMERO-SAO-DO-HEFESTO`).
        """
        with self._io_lock:
            do_cabo = [
                key for key, handle in self._handles.items()
                if self._detect_transport(handle) != "bt"
            ]
            for key in do_cabo:
                no = self._sysfs.get(key) if isinstance(self._sysfs, dict) else None
                invalidar = getattr(no, "invalidate_cache", None)
                if callable(invalidar):
                    invalidar()
        if not do_cabo:
            return {}
        self.reassert_resolved_outputs()
        logger.info("repintar_o_cabo_feito", quantos=len(do_cabo), keys=do_cabo)
        return dict.fromkeys(do_cabo, True)

    def consumir_conexoes_bt_novas(self) -> int:
        """Quantas conexões novas pelo RÁDIO desde a última leitura, e zera."""
        with self._io_lock:
            n = self._conexoes_bt_novas
            self._conexoes_bt_novas = 0
            return n

    def consumir_pinturas_de_lightbar(self) -> int:
        """Quantas vezes o produto pintou a barra pelo rádio, e zera."""
        with self._io_lock:
            n = self._pinturas_de_lightbar
            self._pinturas_de_lightbar = 0
            return n

    def nos_hidraw_por_uniq(self) -> dict[str, str]:
        """`{uniq: /dev/hidrawN}` dos DualSense abertos AGORA (só leitura).

        ESCRITOR-CRU-01: é o endereço com que a sonda de `/proc` pergunta
        "quem mais segura este controle?", e é o mesmo `_pinned_path` que o
        `hidraw_path` já devolve por controle — aqui em forma de mapa, para
        que o vigia do daemon e a aba Status não façam N chamadas nem
        re-enumerem nada. Handle sem MAC ou com path de libusb fica de fora
        (não há como cruzar com o `/proc`, e inventar um nó seria pior que
        não responder).
        """
        with self._io_lock:
            keys = list(self._handles)
        saida: dict[str, str] = {}
        for key in keys:
            uniq = self._key_to_uniq(key)
            if uniq is None:
                continue
            no = self.hidraw_path(uniq)
            if no:
                saida[uniq] = no
        return saida

    def reescrever_lightbar_por_hidraw(self) -> dict[str, bool]:
        """Repinta cor E número de jogador em TODOS os DualSense do rádio.

        GATILHO-DA-COR-01, medido na bancada de 11-12/08/2026 com o olho dela.
        O porquê inteiro está em `core/lightbar_gatilho.py`; aqui ficam as três
        decisões que são DESTE arquivo.

        **1. Por que hidraw, e por que isto NÃO afrouxa o
        `LIGHTBAR-BT-NEVER-01`.** Aquela política (`_refresh_sysfs_leds`, o
        `handle._suppress_leds`) governa o FLUXO do `report_thread`: o report
        que sai a ~2-60 Hz não pode carregar bits de LED por Bluetooth, porque
        reengatar a máquina de estados da lightbar em regime trava a exibição
        no firmware (LIGHTBAR-BT-KEEPALIVE-01, 22/07) e porque o 0x31 da
        pydualsense 0.7.5 era malformado. Nada disso descreve **uma escrita
        avulsa, fora do fluxo, com report montado por nós**. Este método é
        irmão do `enviar_release_leds` logo acima, que já escreve um 0x31 cru
        por Bluetooth desde 08/08 sem tocar naquele flag — e o report daqui é
        mais estreito ainda: sem `RELEASE_LEDS`, sem os bits de SETUP/BRILHO do
        flag2, sem vibração, sem áudio. **`_suppress_leds` continua True para
        todo handle BT, e o keepalive continua LED-neutro.**

        **2. Por que em TODOS, e não só no que chegou.** Porque a rajada da
        Steam não é por controle: cada conexão nova faz ela repintar todo mundo
        que enxerga. A versão que escrevia só no controle recém-chegado deixou
        dois dos três no padrão da Steam (ensaio `gatilho-1500ms-por-controle`).

        **3. O Modo Nativo ESCREVE, desde 23/09/2026.** Até ali era no-op, pela
        regra dela *"no modo nativo devolvemos o controle pra steam e no modo
        conexão também, todo o resto é o hefesto"*. A decisão
        `D-2309-NO-NATIVO-A-LUZ-E-O-NUMERO-SAO-DO-HEFESTO` (STEAM-NO-FISICO-01)
        revoga o «zero write» SÓ para a luz e o número: *"no Modo Nativo, o
        Hefesto escreve a barra e o número SEMPRE"* — e este report é
        exatamente isso, sem vibração, sem gatilho e sem áudio, que continuam
        do jogo.

        **4. Por que a escrita é INCONDICIONAL — sem cache, sem dedup.**
        MEDIDO em 12/08/2026: com as três barras apagadas pela Steam, um
        restart do daemon registrou três vezes
        ``lightbar_reassert_skip_cache`` (`core/sysfs_leds.py:134`) e não
        reescreveu nada; as três barras continuaram apagadas, e ela confirmou
        *"todas apagadas mas em nenhum momento os controles desligaram"*. A
        razão está admitida no próprio código: o ``multi_intensity`` mostra o
        valor PEDIDO, nunca o ACESO (`core/sysfs_leds.py:56-68`), e escrita
        por hidraw — que é justamente o que a Steam faz — não o atualiza.
        Qualquer decisão de "já está nessa cor" tomada a partir dele erra, e
        erra silenciando a cura. Por isso este caminho **não** consulta o nó,
        **não** compara com estado lido e **não** passa pelo dedup
        `_last_out_report` do `sendReport`: ele monta o report e escreve.
        Ressalva honesta, para o caderno não mentir: o `skip_cache` NÃO é a
        causa do defeito (ele foi eliminado com o daemon parado, ensaio
        `lightbar-daemon-fora-radio`) — é agravante, e o que ele impede é a
        cura agir.

        A cor e o número não são inventados aqui: saem do
        `_merged_desired_for_key`, que é o MESMO merge de cinco camadas que o
        priming e o reassert usam (e é por ele que a posição na mesa calculada
        em `daemon/subsystems/identity.py` chega até aqui). Sem cor resolvida,
        o azul-default do kernel — a mesma escolha do priming, para o controle
        virgem nascer aceso em vez de nascer apagado.

        Devolve ``{key: escreveu?}``. Vazio significa "nenhum DualSense no
        rádio" — resposta, não erro; best-effort por handle, e a falha de um
        nunca aborta os outros.
        """
        with self._io_lock:
            pode_player = self._pode_escrever_player_leds()
            alvos = [
                (key, handle, self._merged_desired_for_key(key))
                for key, handle in self._handles.items()
                if self._detect_transport(handle) == "bt"
            ]
        resultado: dict[str, bool] = {}
        for key, handle, desired in alvos:
            ok, cor, players = self._escrever_barra_e_numero_bt(
                key, handle, desired, pode_player=pode_player, nome="gatilho_da_cor"
            )
            resultado[key] = ok
            logger.info(
                "gatilho_da_cor_escrito",
                key=key,
                cor=cor,
                players=players,
                numero=numero_do_desenho(players) if players is not None else None,
                enviado=ok,
            )
        return resultado

    def _escrever_barra_e_numero_bt(
        self,
        key: str,
        handle: Any,
        desired: _DesiredOutput,
        *,
        pode_player: bool,
        nome: str,
    ) -> tuple[bool, tuple[int, int, int], tuple[bool, ...] | None]:
        """Escreve o `0x31` MÍNIMO (cor, número e brilho dele) num handle do rádio.

        É o corpo que o `reescrever_lightbar_por_hidraw` sempre teve, posto
        num lugar só porque desde a STEAM-NO-FISICO-01 ele tem DOIS chamadores
        — o gatilho do fim da sequência e a vigia do sequestro
        (`reafirmar_barra_e_numero`). Duas cópias do mesmo report seriam duas
        verdades sobre o que sai no fio. ``nome`` é o prefixo dos avisos no
        journal, para cada chamador continuar dizendo quem falhou.

        Não loga a escrita bem-sucedida: quem chama decide a cadência (o
        gatilho diz cada uma; a vigia, que pode escrever a cada segundo, não).
        """
        from hefesto_dualsense4unix.core.lightbar_gatilho import (
            build_bt_lightbar_report,
        )

        cor = desired.led if desired.led is not None else KERNEL_DEFAULT_BLUE
        players = desired.player_leds if pode_player else None
        brilho = desired.player_led_brightness if pode_player else None
        if brilho is not None:
            with contextlib.suppress(Exception):
                handle._brilho_das_luzes = int(brilho)
        ok = False
        try:
            report = build_bt_lightbar_report(cor, players, brilho_das_luzes=brilho)
            escritor = getattr(handle, "writeReport", None)
            if callable(escritor):
                escrito = escritor(list(report))
            else:
                device = getattr(handle, "device", handle)
                escrito = device.write(report)
            ok = _escrita_completa(escrito, len(report))
            if not ok:
                logger.warning(
                    f"{nome}_escrita_curta",
                    key=key,
                    pedidos=len(report),
                    saidos=_bytes_que_sairam(escrito),
                )
        except Exception as exc:
            logger.warning(f"{nome}_falhou", key=key, err=str(exc))
        return ok, cor, players

    def reafirmar_barra_e_numero(self, uniqs: Iterable[str]) -> dict[str, bool]:
        """Reescreve a BARRA e o NÚMERO destes controles, e só isso."""
        alvos_uniq = {u for u in (self._key_to_uniq(x) for x in uniqs) if u}
        with self._io_lock:
            pode_player = self._pode_escrever_player_leds()
            alvos = []
            for key, handle in self._handles.items():
                if self._key_to_uniq(key) not in alvos_uniq:
                    continue
                no = self._sysfs.get(key) if isinstance(self._sysfs, dict) else None
                alvos.append(
                    (
                        key,
                        handle,
                        no,
                        self._detect_transport(handle) == "bt",
                        self._merged_desired_for_key(key),
                    )
                )
        resultado: dict[str, bool] = {}
        for key, handle, no, radio, desired in alvos:
            cor: tuple[int, int, int] | None
            if radio:
                ok, cor, players = self._escrever_barra_e_numero_bt(
                    key, handle, desired, pode_player=pode_player,
                    nome="vigia_do_sequestro",
                )
            else:
                ok, cor, players = self._repintar_um_no_do_cabo(
                    key, no, desired, pode_player=pode_player
                )
                self._levar_o_brilho_das_luzes(
                    key, handle, desired.player_led_brightness,
                    what="vigia_do_sequestro",
                )
            resultado[key] = ok
            logger.debug(
                "vigia_do_sequestro_reafirmou",
                key=key,
                transporte="bt" if radio else "cabo",
                cor=cor,
                players=players,
                enviado=ok,
            )
        return resultado

    def _repintar_um_no_do_cabo(
        self,
        key: str,
        no: Any,
        desired: _DesiredOutput,
        *,
        pode_player: bool,
    ) -> tuple[bool, tuple[int, int, int] | None, tuple[bool, ...] | None]:
        """Cor e número de UM controle do cabo pela classe LED, sem cache."""
        if no is None:
            return False, desired.led, desired.player_leds
        cor = desired.led
        players = desired.player_leds if pode_player else None
        ok = True
        with contextlib.suppress(Exception):
            no.invalidate_cache()
        try:
            if cor is not None:
                ok = bool(no.set_rgb(*cor)) and ok
                if ok:
                    self.record_sysfs_write(key, cor)
            if players is not None:
                ok = bool(no.set_players(players)) and ok
        except Exception as exc:
            logger.warning("vigia_do_sequestro_falhou", key=key, err=str(exc))
            ok = False
        return ok, cor, players


    def pintar_lightbar_sem_lembrar(self, rgb: tuple[int, int, int]) -> int:
        """Pinta `rgb` em TODOS os controles SEM tocar no estado desejado."""
        with self._io_lock:
            quantos = len(self._handles)
        if not quantos:
            return 0
        r, g, b = rgb
        self._for_each_led(
            sysfs_op=lambda node: node.set_rgb(r, g, b),
            pydual_op=lambda h: h.light.setColorI(r, g, b),
            what="aviso_de_modo",
            broadcast=True,
            rgb=(r, g, b),
        )
        return quantos

    def restaurar_lightbar_do_perfil(self) -> int:
        """Devolve a TODOS os controles a cor que o perfil resolve. AVISO-DE-MODO-01."""
        with self._io_lock:
            itens = [
                (key, handle, self._sysfs.get(key), self._merged_desired_for_key(key).led)
                for key, handle in self._handles.items()
            ]
        devolvidos = 0
        for key, handle, node, cor in itens:
            alvo = cor if cor is not None else KERNEL_DEFAULT_BLUE
            try:
                ok = self._write_partial_output(
                    handle,
                    node,
                    _DesiredOutput(led=alvo),
                    what="aviso_de_modo_devolve",
                )
            except Exception as exc:
                logger.warning("aviso_de_modo_devolve_falhou", key=key, err=str(exc))
                continue
            if ok:
                devolvidos += 1
        logger.debug("aviso_de_modo_devolvido", controles=devolvidos, de=len(itens))
        return devolvidos

    def piscar_aviso_de_modo(
        self,
        rgb: tuple[int, int, int],
        *,
        vezes: int = AVISO_PISCADAS,
        aceso_s: float = AVISO_ACESO_S,
        apagado_s: float = AVISO_APAGADO_S,
    ) -> int:
        """Pisca `vezes` rápido na cor do modo novo e DEVOLVE a cor dela."""
        alcancados = 0
        try:
            for volta in range(max(1, vezes)):
                escritas = self.pintar_lightbar_sem_lembrar(rgb)
                if volta == 0:
                    alcancados = escritas
                if not escritas:
                    break
                time.sleep(aceso_s)
                self.pintar_lightbar_sem_lembrar(AVISO_APAGADO)
                time.sleep(apagado_s)
        finally:
            self.restaurar_lightbar_do_perfil()
        return alcancados

    def _for_each_led(
        self,
        *,
        sysfs_op: Callable[[Any], bool],
        pydual_op: Callable[[pydualsense], None],
        what: str,
        broadcast: bool = False,
        record: dict[str, Any] | None = None,
        rgb: tuple[int, int, int] | None = None,
        players: tuple[bool, bool, bool, bool, bool] | None = None,
    ) -> None:
        """Aplica um output de LED ao ALVO, preferindo a rota sysfs do kernel."""
        with self._io_lock:
            target, items, ausente = _resolver_escopo(
                self._handles, self._output_target_key, broadcast=broadcast
            )
            if record:
                self._record_desired_locked(target, record)
            sysfs_map = dict(self._sysfs)
        if ausente is not None:
            logger.info(
                "output_alvo_ausente_noop", op=what, alvo=ausente, guardado=bool(record)
            )
            return
        if not items:
            logger.debug("output_offline_noop", op=what)
            return
        for key, handle in items:
            node = sysfs_map.get(key)
            escreveu_sysfs = False
            if node is not None:
                try:
                    escreveu_sysfs = bool(sysfs_op(node))
                except Exception as exc:
                    logger.debug(
                        "sysfs_led_falhou_fallback_pydual", op=what, key=key, err=str(exc)
                    )
            self._pintar_por_hidraw_bt(
                key, handle, rgb=rgb, players=players, what=what
            )
            if escreveu_sysfs:
                continue
            try:
                pydual_op(handle)
            except Exception as exc:
                logger.warning("output_handle_failed", op=what, key=key, err=str(exc))

    @staticmethod
    def _apply_trigger(handle: pydualsense, side: Side, effect: TriggerEffect) -> None:
        trigger = handle.triggerL if side == "left" else handle.triggerR
        trigger.mode = PyDualSenseController._coerce_mode(effect.mode)
        for idx, value in enumerate(effect.forces):
            trigger.setForce(idx, value)

    def _reapply_desired(self, key: str, handle: pydualsense) -> None:
        """Re-aplica o estado desejado DESTE controle num handle recém-aberto.

        PERFIL-01 (4P-01): o que se aplica é o MERGE POR CAMPO do default
        broadcast com o override por-uniq do controle `key` — o do controle
        CERTO, nunca o de outro (era o bug provado: mirar o Controle 2 no
        seletor e replugar o Controle 1 o pintava com a cor do 2).

        REPLICA-03: reconexão NO MEIO de uma sessão de jogo (wake BT) — o
        merge já traz a camada game (LED/player) e os blocos crus de trigger
        do jogo são re-pendurados no handle novo, para a posse sobreviver.

        MIC-BT-DONO-01: e o MUDO DO MICROFONE re-pendura no mesmo lugar, pelo
        mesmo motivo — ele é atributo do handle, e handle novo nasce sem dono.
        Vai FORA do `_write_partial_output` de propósito: aquele é o aplicador
        do `_DesiredOutput`, onde `None` quer dizer "herda de baixo"; aqui
        `None` quer dizer "devolvo ao kernel", que é ordem oposta.
        """
        with self._io_lock:
            node = self._sysfs.get(key)
            desired = self._merged_desired_for_key(key)
            uniq = self._key_to_uniq(key)
            game_triggers = (
                dict(self._game_triggers_by_uniq.get(uniq, {}))
                if uniq is not None
                else {}
            )
            mic_mudo = self._mic_mute_by_uniq.get(uniq) if uniq is not None else None
            haptica_de_audio = uniq is not None and uniq in self._haptica_de_audio_por_uniq
        definir_a_haptica = getattr(handle, "set_haptica_de_audio", None)
        if callable(definir_a_haptica):
            with contextlib.suppress(Exception):
                definir_a_haptica(haptica_de_audio)
        for side, block in game_triggers.items():
            attr = "_raw_trigger_left" if side == "left" else "_raw_trigger_right"
            with contextlib.suppress(Exception):
                setattr(handle, attr, block)
        if mic_mudo is not None:
            tomar = getattr(handle, "set_microphone_mute", None)
            if callable(tomar):
                try:
                    tomar(mic_mudo)
                except Exception as exc:
                    logger.warning(
                        "mic_posse_no_hotplug_falhou", key=key, err=str(exc)
                    )
                else:
                    logger.info("mic_posse_rependurada", key=key, mudo=mic_mudo)
            else:
                logger.debug("mic_posse_handle_sem_api", key=key)
        self._write_partial_output(
            handle, node, desired, what="reapply_perfil_no_hotplug"
        )

    def _pintar_por_hidraw_bt(
        self,
        key: str | None,
        handle: pydualsense,
        *,
        rgb: tuple[int, int, int] | None,
        players: tuple[bool, bool, bool, bool, bool] | None,
        what: str,
        brilho_das_luzes: int | None = None,
    ) -> bool:
        """A SEGUNDA rota da lightbar por rádio, em regime. ROTA-BT-EM-REGIME-01.

        **O defeito, medido na bancada dela em 12/08/2026.** Por Bluetooth, o
        produto tinha UMA rota de LED em regime — o `sysfs` — e é justamente a
        que perde: com a Steam viva, escrever `multi_intensity` NÃO muda a
        barra (ensaio ``cor-rota-sysfs-com-steam``), enquanto o report `0x31`
        escrito no `hidraw` PINTOU os três controles no mesmo instante
        (``cor-rota-hidraw-com-steam``; literal dela: *"todos tão magenta"*).
        O caderno de eliminação já julga a ROTA como **e-a-causa** nesta linha
        (`scripts/eliminacao.py`, ``luz.lightbar.cor@dualsense [radio]``).

        **Por que a segunda rota não existia.** O fallback pydualsense que o
        `_for_each_led` e o `_write_partial_output` carregam é CÓDIGO MORTO por
        rádio: `_suppress_leds` é True para todo handle BT
        (`LIGHTBAR-BT-NEVER-01`), então `handle.light.setColorI(...)` atualiza
        o estado interno e o `report_thread` remove os bits de LED do report.
        Por rádio era sysfs ou nada.

        **Por que ESTE report e não religar o fluxo.** O que a bancada mediu foi
        uma escrita AVULSA, estreita e fora do fluxo — o mesmo
        `build_bt_lightbar_report` que o `reescrever_lightbar_por_hidraw`
        (GATILHO-DA-COR-01) já manda por rádio desde 12/08: sem `RELEASE_LEDS`
        (0x08), sem os bits de SETUP/BRILHO do flag2, sem vibração e sem
        áudio. Religar a escrita de LED no `report_thread` seria outra coisa e
        continua PROIBIDO: o `LIGHTBAR-BT-KEEPALIVE-01` (22/07) mediu que
        reengatar a máquina de estados da lightbar em REGIME trava a exibição
        no firmware. Por isso `_suppress_leds` não muda aqui — o que muda é
        que a rota fora do fluxo passa a ser alcançável a partir dos caminhos
        que a GUI e o perfil usam, e não só do gatilho de conexão.

        **E explica o que JÁ funcionava**, que é a regra da casa: por CABO
        nada muda (o report `0x02` não tem janela nem máquina de estados, e o
        fallback pydualsense do cabo nunca foi suprimido); e por rádio o
        `sysfs` continua sendo escrito antes — ele funciona quando ninguém
        mais tem o `hidraw` aberto (ensaio ``lightbar-probe-limpa``: mesa
        vazia, os três obedeceram ao verde por sysfs). A segunda rota é o que
        faltava para o caso em que existe outro escritor.

        **O BRILHO DAS LUZES DE NÚMERO VAI NO MESMO QUADRO** (24/09/2026,
        `D-2409-AS-LUZES-DE-NUMERO-TEM-TRES-BRILHOS`): `brilho_das_luzes` liga o
        `flag2` bit0 e escreve o `common[42]` — ver
        `lightbar_gatilho.common_das_luzes`, onde está por que o bit0 não é o
        0x02 que trava a exibição. Um quadro só por ação, e não dois: cada
        report por rádio custa duas fatias.

        Devolve True quando escreveu. No-op (False) fora do rádio, sem valor
        para escrever, ou quando o handle não sabe carimbar o `seq`.
        """
        if rgb is None and players is None and brilho_das_luzes is None:
            return False
        if self._detect_transport(handle) != "bt":
            return False
        escritor = getattr(handle, "writeReport", None)
        if not callable(escritor):
            return False
        from hefesto_dualsense4unix.core.lightbar_gatilho import (
            build_bt_lightbar_report,
        )

        try:
            escritor(list(build_bt_lightbar_report(
                rgb, players, brilho_das_luzes=brilho_das_luzes)))
        except Exception as exc:
            logger.debug("lightbar_hidraw_bt_falhou", op=what, key=key, err=str(exc))
            return False
        with self._io_lock:
            self._pinturas_de_lightbar += 1
        logger.debug(
            "lightbar_hidraw_bt_escrito",
            op=what,
            key=key,
            cor=rgb,
            player=players,
            brilho_das_luzes=brilho_das_luzes,
        )
        return True

    def _levar_o_brilho_das_luzes(
        self,
        key: str | None,
        handle: Any,
        degrau: int | None,
        *,
        what: str,
        o_radio_ja_leva: bool = False,
    ) -> bool:
        """Leva o brilho das luzes de número a UM controle, no cabo e no rádio."""
        if degrau is None or not self._pode_escrever_player_leds():
            return False
        with contextlib.suppress(Exception):
            handle._brilho_das_luzes = int(degrau)
        radio = self._detect_transport(handle) == "bt"
        if radio and o_radio_ja_leva:
            return False
        if radio:
            return self._pintar_por_hidraw_bt(
                key, handle, rgb=None, players=None, what=what,
                brilho_das_luzes=degrau,
            )
        escritor = getattr(handle, "writeReport", None)
        if not callable(escritor):
            return False
        from hefesto_dualsense4unix.core.lightbar_gatilho import (
            build_usb_lightbar_report,
        )

        report = build_usb_lightbar_report(None, None, brilho_das_luzes=degrau)
        try:
            escrito = escritor(list(report))
        except Exception as exc:
            logger.debug("brilho_das_luzes_cabo_falhou", op=what, key=key, err=str(exc))
            return False
        ok = _escrita_completa(escrito, len(report))
        logger.debug(
            "brilho_das_luzes_cabo_escrito", op=what, key=key, degrau=degrau, ok=ok
        )
        return ok

    def _write_partial_output(
        self,
        handle: pydualsense,
        node: Any,
        out: _DesiredOutput,
        *,
        what: str,
    ) -> bool:
        """Escreve os campos NÃO-None de `out` em UM handle. Devolve se DEU CERTO."""
        from pydualsense.enums import PlayerID

        try:
            if out.trigger_left is not None:
                self._apply_trigger(handle, "left", out.trigger_left)
            if out.trigger_right is not None:
                self._apply_trigger(handle, "right", out.trigger_right)
            if out.led is not None and not (
                node is not None and node.set_rgb(*out.led)
            ):
                handle.light.setColorI(*out.led)
            if (
                out.player_leds is not None
                and self._pode_escrever_player_leds()
                and not (node is not None and node.set_players(out.player_leds))
            ):
                mask = sum(1 << i for i, b in enumerate(out.player_leds) if b)
                handle.light.playerNumber = PlayerID(mask)
            if out.mic_led is not None:
                _escrever_led_do_mic(handle, out.mic_led)
            pode_player = self._pode_escrever_player_leds()
            brilho = out.player_led_brightness if pode_player else None
            self._levar_o_brilho_das_luzes(
                None, handle, brilho, what=what, o_radio_ja_leva=True
            )
            self._pintar_por_hidraw_bt(
                None,
                handle,
                rgb=out.led,
                players=out.player_leds if pode_player else None,
                what=what,
                brilho_das_luzes=brilho,
            )
        except Exception as exc:
            logger.warning("reapply_perfil_no_hotplug_falhou", op=what, err=str(exc))
            return False
        return True

    def set_trigger(self, side: Side, effect: TriggerEffect) -> None:
        campo = "trigger_left" if side == "left" else "trigger_right"
        self._for_each(
            lambda h: self._apply_trigger(h, side, effect),
            what="set_trigger",
            record={campo: effect},
        )

    def set_led(self, color: tuple[int, int, int]) -> None:
        r, g, b = color
        self._for_each_led(
            sysfs_op=lambda node: node.set_rgb(r, g, b),
            pydual_op=lambda h: h.light.setColorI(r, g, b),
            what="set_led",
            record={"led": color},
            rgb=(r, g, b),
        )

    def set_rumble(self, weak: int, strong: int) -> None:
        # perfil. `_escalar_rumble` devolve o par intacto quando a unidade não
        def _do(handle: pydualsense, key: str) -> None:
            eff_weak, eff_strong = self._escalar_rumble(key, weak, strong)
            handle.setLeftMotor(eff_strong)
            handle.setRightMotor(eff_weak)

        self._for_each_com_key(_do, what="set_rumble")

    def _escalar_rumble(self, key: str, weak: int, strong: int) -> tuple[int, int]:
        """Aplica a escala de vibração por-uniq da `key` (POR-UNIDADE-01)."""
        uniq = self._key_to_uniq(key)
        fator = self._rumble_scale_by_uniq.get(uniq) if uniq is not None else None
        if fator is None:
            return weak, strong
        return (
            max(0, min(255, int(weak * fator))),
            max(0, min(255, int(strong * fator))),
        )

    def set_rumble_scales(self, scales: Mapping[str, float] | None = None) -> None:
        """SUBSTITUI o mapa de escala de VIBRAÇÃO por-uniq (POR-UNIDADE-01)."""
        novo: dict[str, float] = {}
        for uniq, fator in (scales or {}).items():
            alvo = self._key_to_uniq(uniq)
            if alvo is None:
                logger.warning("escala_de_vibracao_sem_mac_ignorada", uniq=uniq)
                continue
            novo[alvo] = float(fator)
        with self._io_lock:
            self._rumble_scale_by_uniq = novo

    def force_rumble_stop(self, uniq: str | None = None) -> None:
        """Para os motores com um report de stop (HARM-16) — todos, ou UM.

        `set_rumble(0, 0)` com os nossos motores JÁ em 0 (0→0) não muda o
        report — e report que não muda não é escrito (dedup do `sendReport`), de
        propósito: sem dono do rumble o keepalive fica calado depois da janela
        de confirmação, que é o que deixa o motor de terceiros em paz
        (RUMBLE-SEM-DONO-01). Mas a saída de um modo (Nativo/gamepad) precisa
        parar um motor que o JOGO deixou vibrando por fora (hidraw direto/FF)
        — aqui forçamos o
        `_rumble_stop_pending` em cada handle: UM report com flags ligados e
        motores 0, e o ciclo seguinte volta ao neutro. Broadcast deliberado
        (ignora o seletor de alvo): sair de modo para TODO mundo.

        BORDA-DE-QUEDA-01 (26/08/2026): `uniq` restringe a UM controle, e
        existe porque a borda de um jogador de co-op não é saída de modo — o
        jogador 3 cai e os outros três continuam jogando. Parar a mesa inteira
        ali seria trocar um motor preso por três motores mudos no meio da
        partida. Endereçamento pelo mesmo `_casar_key` do `enviar_release_leds`
        (aceita o MAC 12-hex do IPC e a key crua do handle); alvo que não casa
        handle nenhum é NO-OP silencioso — o controle já saiu da mesa, e é
        exatamente o caso em que não há nada a parar.
        """
        with self._io_lock:
            if uniq is not None:
                key = _casar_key(self._handles, uniq)
                handles = [(key, self._handles[key])] if key is not None else []
            else:
                handles = list(self._handles.items())
        for key, handle in handles:
            try:
                handle.setLeftMotor(0)
                handle.setRightMotor(0)
                handle._rumble_stop_pending = True
            except Exception as exc:
                logger.warning(
                    "output_handle_failed", op="force_rumble_stop", key=key,
                    err=str(exc),
                )

    def set_mic_led(self, aceso: bool, *, uniq: str | None = None) -> None:
        """Acende/apaga o LED do microfone — no ALVO, ou no controle `uniq`.

        Delega para `ds.audio.setMicrophoneLED(bool)`, que só marca o estado; o
        byte é o `common[8]`, e quem o embrulha é o `prepareReport` DESTA casa
        (`_PinnedPyDualSense.prepareReport`, via `ds_output_report`), não o da
        pydualsense. Onde o byte cai: `common[8]` = **report[9] no cabo**
        (common em `[1..47]`) e **report[11] no rádio** (common em `[3..49]`).

        CORRIGIDO em 15/08/2026: aqui se lia "outReport[9] USB / outReport[10]
        BT". O `[10]` é o que a pydualsense 0.7.5 escreve no ramo BT dela
        (`pydualsense.py:610`) — está errado por um, e não é o nosso caminho
        desde a BTREPORT-02, que substituiu o `prepareReport` do upstream
        justamente porque o 0x31 dele é malformado.

        AUDIO-OWNER-01 (12/08/2026): a chamada passou a TOMAR A POSSE de
        `common[8]` (`_escrever_led_do_mic`). Antes a posse era implícita — o
        bit `0x01` do flag1 estava sempre ligado —, e o preço era o produto
        apagar, no report seguinte, o LED que o kernel acendeu quando ela
        aperta o botão de mudo. Quem NÃO chama isto não é mais dono do byte.

        MIC-DA-MESA-ELEICAO-01 (01/09/2026) — O ENDEREÇO, e o estrago que a
        falta dele fazia. Este método não aceitava alvo e caía no `_for_each`
        sem `broadcast`: com o seletor da GUI em "Todos" ele escrevia em TODOS
        os handles E, pior, o `record` com `target_key=None` faz o
        `_record_desired_locked` **zerar o campo `mic_led` de todos os
        overrides por-uniq**. Numa mesa de quatro, a borda do Jogador 2
        acenderia os quatro LEDs e apagaria o estado por-controle dos outros
        três — o pedido dela (*"cada uma vê no PRÓPRIO controle se o mic dela
        está no ar"*) era inalcançável por esta porta.

        `uniq` fecha isso: escreve SÓ naquele handle e grava SÓ no override
        dele, como `set_microphone_mute(muted, uniq=)` já fazia.

        `aceso` é o que a LUZ faz, e nesta casa a luz mudou de significado:
        **aceso = este microfone está VIVO**, a inversão que ela pediu em
        01/09/2026. O byte não inverteu — quem decide o argumento é o chamador
        (`daemon/subsystems/mic_da_mesa.py`, que passa `not mudo`).
        """
        flag = bool(aceso)
        if uniq is not None:
            self._set_mic_led_em(uniq, flag)
            return
        self._for_each(
            lambda h: _escrever_led_do_mic(h, flag),
            what="set_mic_led",
            record={"mic_led": flag},
        )

    def _set_mic_led_em(self, uniq: str, aceso: bool) -> bool:
        """Escreve o LED do mic SÓ no handle de `uniq`, e grava SÓ no override dele."""
        from hefesto_dualsense4unix.core.sysfs_leds import norm_mac

        alvo = norm_mac(uniq)
        with self._io_lock:
            escolhido: tuple[str, Any] | None = None
            for key, handle in self._handles.items():
                if self._key_to_uniq(key) == alvo:
                    escolhido = (key, handle)
                    break
            if escolhido is not None:
                self._record_desired_locked(escolhido[0], {"mic_led": aceso})
        if escolhido is None:
            logger.info("output_alvo_ausente_noop", op="set_mic_led", alvo=uniq)
            return False
        key, handle = escolhido
        try:
            _escrever_led_do_mic(handle, aceso)
        except Exception as exc:
            logger.warning(
                "output_handle_failed", op="set_mic_led", key=key, err=str(exc)
            )
            return False
        return True


    def audio_status_for(self, uniq: str | None = None) -> dict[str, bool] | None:
        """Estado de áudio LIDO do controle, ou None se ainda não foi visto."""
        status = self._audio_status_byte(uniq)
        if status is None:
            return None
        from hefesto_dualsense4unix.integrations.dualsense_bt_audio import (
            STATUS_FONE_PLUGADO,
            STATUS_MIC_EXTERNO,
            STATUS_MIC_MUDO,
        )

        return {
            "fone_plugado": bool(status & STATUS_FONE_PLUGADO),
            "mic_externo": bool(status & STATUS_MIC_EXTERNO),
            "mic_mudo": bool(status & STATUS_MIC_MUDO),
        }

    def speaker_state_for(self, uniq: str | None = None) -> dict[str, Any] | None:
        """`{"volume": 0-255, "muted": bool}` do alto-falante, ou None.

        HONESTIDADE DO CAMPO (AUDIO-OWNER-01): o DualSense **não devolve** o
        volume — não existe report de input nem feature report que o leia. A
        única forma de SABER o volume é ter sido nós a mandá-lo. Por isso:

          - ninguém chamou `set_speaker_volume` ⇒ devolve **None** e a chave
            `speaker` nem entra no payload (a GUI esconde o módulo);
          - depois de um `set_speaker_volume`, devolve o valor EM VIGOR, que
            é o que o firmware recebe em todo report enquanto formos donos.

        `muted` é derivado: mudo = volume efetivo 0. O bloco de volume do
        report não tem bit de mute próprio.

        A CHAVE `rota` (SOM-ROTA-01/leitura, 09/08/2026) segue a MESMA regra de
        honestidade, e por isso ela é **opcional**: o `common[7]` também não é
        legível — não há report de entrada nem feature que o devolva. Ela só
        aparece quando somos donos daquele byte, e o valor é o que estamos
        mandando; enquanto ninguém escreveu o canal, a chave NÃO existe, e
        quem lê tem de dizer "não dá para saber" em vez de desenhar um padrão.

        Sem ela, o seletor de canal da janela era cego: ele desenhava "Sons do
        jogo" por ser o primeiro da lista, inclusive depois de um perfil ter
        posto o controle em "Todo o som do PC" — a tela afirmando um canal que
        não era o vigente.
        """
        handle = self._handle_for(uniq)
        if handle is None:
            return None
        volumes = getattr(handle, "_volumes_audio", None)
        if not volumes or volumes[1] is None:
            return None
        preferido = getattr(handle, "_speaker_volume_pref", None)
        efetivo = int(volumes[1])
        base = int(preferido) if isinstance(preferido, int) else efetivo
        estado: dict[str, Any] = {
            "volume": max(0, min(255, base)),
            "muted": efetivo == 0,
        }
        if len(volumes) > 3 and volumes[3] is not None:
            estado["rota"] = (
                int(volumes[3]) & rep.OUTPUT_PATH_SEL_MASK
            ) >> rep.OUTPUT_PATH_SEL_SHIFT
        return estado

    def set_speaker_volume(
        self,
        volume: int | None = None,
        *,
        muted: bool | None = None,
        uniq: str | None = None,
        rota: int | None = None,
    ) -> bool:
        """Assume a posse do volume de alto-falante/fone e o aplica."""
        alvo = self._handle_for(uniq)
        if alvo is None:
            logger.debug("output_offline_noop", op="set_speaker_volume")
            return False
        ok = self._escrever_volume_no_handle(
            alvo, volume=volume, muted=muted, rota=rota, op="set_speaker_volume"
        )
        logger.info("speaker_volume_set", volume=volume, muted=bool(muted), ok=ok)
        return ok

    def _escrever_volume_no_handle(
        self,
        handle: Any,
        *,
        volume: int | None,
        muted: bool | None,
        rota: int | None,
        op: str,
    ) -> bool:
        """A escrita de volume num handle JÁ escolhido. A conta mora aqui, só aqui."""
        try:
            pref = getattr(handle, "_speaker_volume_pref", None)
            if volume is not None:
                pref = max(0, min(255, int(volume)))
            if pref is None and muted is not None:
                logger.info("speaker_mute_sem_volume_recusado", op=op, muted=muted)
                return False
            if pref is None:
                vigente = getattr(handle, "_speaker_volume_pref", None)
                pref = int(vigente) if isinstance(vigente, int) else 0
            handle._speaker_volume_pref = pref
            efetivo = 0 if muted else pref
            handle.set_audio_volumes(
                headphone=efetivo,
                speaker=efetivo,
                preamp=rep.SP_PREAMP_GAIN_PADRAO,
                audio_path=_byte_da_rota(handle, rota),
            )
        except Exception as exc:
            logger.warning("output_handle_failed", op=op, err=str(exc))
            return False
        return True

    def release_speaker_volume(self, *, uniq: str | None = None) -> bool:
        """DEVOLVE a posse dos bytes de volume — o irmão do `mic release`.

        SOM-02 (E3). O `release_audio_volumes` existia no handle desde o
        AUDIO-OWNER-01 e não tinha porta nenhuma acima dele: nem serviço, nem
        IPC, nem janela, nem linha de comando. Sem esta porta, o PRIMEIRO uso do
        volume sequestrava o alto-falante até a próxima desconexão.

        O que a devolução faz, dito por inteiro e sem promessa a mais:

          - os quatro bytes de `common[4..7]` voltam a "sem dono" e os bits de
            validação do flag0 saem ZERADOS em todo report seguinte — o firmware
            volta a mandar no bloco;
          - **não há restauração de valor.** O DualSense não devolve o volume
            (não existe leitura), então ninguém pode saber qual era o número de
            antes. O firmware conserva o ÚLTIMO valor que mandamos; o que a
            devolução entrega de volta é o CONTROLE, não o valor;
          - a PREFERÊNCIA (`_speaker_volume_pref`) morre junto, e isso é a
            entrega, não a faxina: deixá-la viva faria um `muted=False` posterior
            ressuscitar um volume antigo e RETOMAR a posse sem ninguém pedir —
            exatamente o sequestro silencioso que esta entrega veio fechar.

        Devolve True quando o handle escolhido por `uniq` recebeu o pedido;
        False quando não há controle para o `uniq` (ou nenhum conectado).
        Idempotente: devolver duas vezes é inofensivo.
        """
        alvo = self._handle_for(uniq)
        if alvo is None:
            logger.debug("output_offline_noop", op="release_speaker_volume")
            return False
        ok = False
        try:
            alvo.release_audio_volumes(microfone=False)
            alvo._speaker_volume_pref = None
            ok = True
        except Exception as exc:
            logger.warning(
                "output_handle_failed", op="release_speaker_volume", err=str(exc)
            )
        logger.info("speaker_volume_released", uniq=uniq, ok=ok)
        return ok

    def assumir_volume_padrao_na_adocao(self, key: str, handle: Any) -> bool:
        """Toma a posse do volume e o põe em 100% assim que o controle é ADOTADO.

        SOM-SEMPRE-01 (16/08/2026). Decisão dela, textual: *"precisamos setar o
        som sempre em todos os controles no 100%"*.

        **O DEFEITO QUE ISTO FECHA, medido na bancada dela em 15-16/08 com o
        controle na mão, no CABO, em teste CEGO** (`docs/data/ensaios.csv`,
        `sfx-cabo-sem-posse` / `sfx-cabo-com-posse` / `sfx-cabo-volume-zero`)::

            volume nunca escrito por nós ... ela: "nenhum"      MUDO
            `speaker volume 85` ........... ela: "bep bep bep"  SOA
            `speaker volume 0` ............ ela: "mudo"         MUDO

        Nada mais mudou entre as três passadas. Enquanto ninguém tomava a posse
        de `common[4..7]`, o alto-falante ficava mudo — e o comentário do
        `_PinnedPyDualSense.__init__` já dizia *"idem, mandando volume ZERO em
        todo report"* desde 25/07 sem que ninguém o tivesse ligado ao silêncio.
        Mesma família do keepalive que cancelava o rumble pelos BYTES: a casa
        sabia e o produto não fazia.

        **Por que na ADOÇÃO e não num clique.** A posse morre com o handle
        (`_volumes_audio` nasce vazio a cada `_open_one`), então "o som sempre
        sai" só pode ser propriedade do momento em que o controle é adotado. É
        também o único ponto UNIVERSAL: vale para o 1º e para o 7º controle,
        no cabo e no rádio, no boot e no hotplug do meio da sessão.

        **FATO ERRADO, SUBSTITUÍDO — 16/09/2026.** Aqui se lia que o gancho de
        perfil *"só corre na TRANSIÇÃO offline→online do daemon"* e que *"o
        segundo controle a chegar numa mesa já online nunca era coberto por
        ele"*. A primeira metade caiu com a BORDA-DE-QUEDA-01: há um ramo POR
        ALVO (`daemon/connection.py:182` → `anunciar_bordas_por_alvo` →
        `reapply_speaker_after_connect(uniq=…)`) que cobre a chave nova sem
        transição agregada. O que continuava verdadeiro era a segunda guarda —
        o gancho exigia a seção `speaker` GLOBAL —, e ela foi o defeito da
        SOM-ROTA-03: os perfis dela guardam o som só por peça, então o gancho
        devolvia `None` para todo uniq e a escolha dela nunca voltava do
        replug. Curado em `profiles/manager.reapply_speaker_on_connect`.

        Esta adoção continua sendo o piso — quem não tem perfil nenhum fica
        com o som ligado e roteado —, mas ela não é mais a última rede: o
        gancho agora devolve a opinião da peça por cima dela.

        **O PREÇO, e ele é real.** Tomar a posse é irreversível até
        `speaker release` ou até o controle desconectar: enquanto formos donos,
        o firmware recebe o NOSSO valor em todo report e não há mais como ele
        guardar outro. Ela aceitou este preço ao pedir 100% sempre, e a saída
        continua existindo e continua sendo dela — `hefesto-dualsense4unix
        speaker release` devolve o registrador. O que a devolução NÃO faz é
        emudecer: com os bits de validação apagados o firmware CONSERVA o
        último valor que mandamos, isto é, os 100% — quem devolve a posse fica
        com o som ligado, não com o silêncio de antes desta cura.

        **O que fica de fora, de propósito**: o volume do MICROFONE
        (`common[6]`).

        **A ROTA SAIU DESTA LISTA EM 16/09/2026 — SOM-ROTA-02.** Ela ficava de
        fora porque `common[7]` carrega também o caminho do microfone, e mexer
        no byte sem opinião seria decidir por ela. A bancada derrubou a
        premissa: o default do FIRMWARE não é neutro, é
        `SAIDA_ESTEREO_NO_FONE` — **não escrever a rota É escolher o fone**, e
        o conector está vazio. Os 100% desta cura iam inteiros para lugar
        nenhum, e o alto-falante nascia mudo em todo controle, toda vez.
        Medido com ela do lado do controle: mesmo tom, sem rota "não saiu som";
        com `rota=3` escrita, *"Saiu som"*. Agora nasce em `ROTA_PADRAO_DO_SOM`
        («Sons do jogo», decisão dela no mesmo dia), e o
        `OUTPUT_PATH_SEL_MASK` preserva os bits do microfone — que era a razão
        real de a omissão ter sido prudente, e continua honrada.

        **SOBRE O MICROFONE, A RAZÃO TROCOU EM 09/09/2026 e a omissão FICOU.**
        Até 06/09 ele ficava fora porque *"o dono do microfone no Linux é o
        kernel"*; a bancada dela derrubou a premissa (o byte AGE — *"Deu certo.
        funciona"*, `folha-mic-volume-o-byte-age-cabo-0909`) e ela mandou ligá-lo
        (`D-0909-O-VOLUME-DO-MIC-LIGA-O-BYTE-DO-APARELHO`). Quem o liga é o
        CAMPO do microfone (`set_microphone_volume`), e não a adoção: nascer a
        100 % é decisão dela sobre o som que SAI (*"precisamos setar o som
        sempre em todos os controles no 100%"*), e tomar a posse do ganho de
        CAPTURA de todo controle adotado seria decidir por ela uma coisa que ela
        não pediu — com o preço de nunca mais o firmware mandar naquele byte.

        Fone e alto-falante vão os DOIS
        ao mesmo valor porque é UM volume só para quem segura o controle, e
        porque o fone manda por cima da rota (ensaio `sfx-o-fone-manda-por-
        cima`): deixar o fone em zero faria a cura silenciar justamente quem
        plugasse um headset.

        **Modo Nativo continua com contrato de zero escrita.** Isto aqui mexe
        só no estado em memória do handle; quem põe bytes no fio é o
        `report_thread`, e ele não manda NADA enquanto `_output_muted` estiver
        ligado (FEAT-NATIVE-OUTPUT-MUTE-01, `sendReport`). Um controle adotado
        com jogo em foco guarda os 100% e os aplica quando o mute sair — que é
        o que se quer, e não uma escrita por baixo do jogo.

        Best-effort, como todo o caminho de adoção: falhar aqui devolve False e
        deixa o controle exatamente como ele ficava antes desta cura.
        """
        escreveu = self._escrever_volume_no_handle(
            handle,
            volume=VOLUME_PADRAO_DO_SOM,
            muted=None,
            rota=ROTA_PADRAO_DO_SOM,
            op="volume_padrao_na_adocao",
        )
        logger.info(
            "volume_padrao_na_adocao",
            key=key,
            volume=VOLUME_PADRAO_DO_SOM,
            rota=ROTA_PADRAO_DO_SOM,
            ok=escreveu,
        )
        return escreveu

    def set_microphone_mute(
        self, muted: bool | None, *, uniq: str | None = None
    ) -> bool:
        """Assume (ou devolve) a posse do mudo de microfone do FIRMWARE."""
        alvo = self._handle_for(uniq)
        handles = [alvo] if alvo is not None else []
        if not handles:
            logger.debug("output_offline_noop", op="set_microphone_mute")
            return False
        ok = False
        for handle in handles:
            try:
                handle.set_microphone_mute(muted)
                ok = True
            except Exception as exc:
                logger.warning(
                    "output_handle_failed", op="set_microphone_mute", err=str(exc)
                )
        if ok:
            self._registrar_posse_do_mudo(uniq, muted)
        logger.info("microphone_mute_set", muted=muted, uniq=uniq, ok=ok)
        return ok

    def _registrar_posse_do_mudo(
        self, uniq: str | None, muted: bool | None
    ) -> str | None:
        """Grava (ou solta) a posse do mudo no mapa por-uniq. MIC-BT-DONO-01."""
        from hefesto_dualsense4unix.core.sysfs_leds import norm_mac

        alvo = (norm_mac(uniq) if uniq else self.primary_uniq) or None
        if alvo is None or len(alvo) != 12:
            logger.debug("mic_posse_sem_endereco", uniq=uniq, muted=muted)
            return None
        with self._io_lock:
            if muted is None:
                self._mic_mute_by_uniq.pop(alvo, None)
            else:
                self._mic_mute_by_uniq[alvo] = bool(muted)
        return alvo

    def set_microphone_volume(
        self, percentual: int, *, uniq: str | None = None
    ) -> bool:
        """Assume a posse do `common[6]` — o GANHO DE CAPTURA do aparelho.

        MIC-VOLUME-02 (09/09/2026). **Decisão dela, `D-0909-O-VOLUME-DO-MIC-
        LIGA-O-BYTE-DO-APARELHO`, textual: *"3-c"*** — ligar o byte do
        aparelho, revogando neste ponto a decisão de 06/09 que o mantinha fora
        da chamada. A revogação está datada nos dois lugares em que aquela
        decisão foi escrita (`_escrever_volume_no_handle` e
        `assumir_volume_padrao_na_adocao`), e a decisão de 06/09 não se apaga.

        **O QUE DECIDIU FOI A BANCADA, e é o único jeito que valia.** Duas
        afirmações desta casa se contradiziam: a docstring do `mic.volume.set`
        dizia que *"o DualSense não expõe registrador de ganho de microfone em
        transporte nenhum"*, e o mapa mais o kernel diziam que o registrador
        existe e tem nome. O olho dela desempatou no CABO, em 09/09/2026, com o
        P2 plugado e a fonte do sistema travada a 100 % para isolar o ganho do
        aparelho: *"Deu certo. funciona"* (`docs/data/ensaios.csv`,
        `folha-mic-volume-o-byte-age-cabo-0909`). Byte que obedece ganha campo.

        **UM CAMPO, DOIS DEGRAUS**, e este é o SEGUNDO. O primeiro é o ganho da
        FONTE no PipeWire, que `mic.volume.set` já mexia e continua mexendo — é
        ele que faz a feature valer nos dois transportes. Este aqui é o do
        aparelho, e os dois juntos são o que faz o número da tela ser o que a
        pessoa ouve do outro lado.

        **O QUE NÃO ESTÁ MEDIDO, dito na cara:** onde este byte fica mudo e
        onde ele satura (a curva que o alto-falante tem e o microfone não —
        ver :func:`byte_do_volume_do_microfone`), e o RÁDIO. Pelo rádio o byte
        vai no `0x31` (`common[6] = report[9]`) e o caminho de escrita é o
        mesmo, mas ninguém gravou voz pelo rádio para conferir — e não há o que
        gravar enquanto o controle no rádio não publicar microfone nenhum, que
        é a MIC-OS-QUATRO-01. O mapa de canais guarda essa metade em
        `inferido-do-codigo`, e não em `medido`.

        **O PREÇO, o mesmo do alto-falante:** tomar a posse é irreversível até
        `release_microphone_volume` ou até o controle desconectar. Enquanto
        formos donos, o firmware recebe o NOSSO byte em todo report. Quem
        desconecta e volta perde a posse (o handle é outro) — e quem a
        restaura é o applier de perfil, não este método.

        `percentual` é 0-100, a MESMA faixa de `mic.volume.set` e de
        `ControllerMicOverride.volume`; a conversão para o byte é a régua única
        de :func:`byte_do_volume_do_microfone`. Devolve True quando o handle
        daquele `uniq` recebeu a escrita, e False quando não havia handle —
        "não havia controle" nunca pode ser lido como "aplicado".
        """
        alvo = self._handle_for(uniq)
        if alvo is None:
            logger.debug("output_offline_noop", op="set_microphone_volume")
            return False
        bruto = byte_do_volume_do_microfone(percentual)
        escritor = getattr(alvo, "set_audio_volumes", None)
        if not callable(escritor):
            logger.debug("output_handle_sem_porta", op="set_microphone_volume")
            return False
        try:
            escritor(microphone=bruto)
        except Exception as exc:
            logger.warning(
                "output_handle_failed", op="set_microphone_volume", err=str(exc)
            )
            return False
        logger.info(
            "microphone_volume_set",
            percentual=percentual,
            bruto=bruto,
            uniq=uniq,
            ok=True,
        )
        return True

    def release_microphone_volume(self, *, uniq: str | None = None) -> bool:
        """Devolve ao firmware a posse do `common[6]`, e SÓ dele.

        MIC-VOLUME-02. O irmão de `release_speaker_volume`, e a razão de ser um
        método separado é a mesma pela qual `release_audio_volumes` ganhou o
        `microfone=`: são dois campos com dois donos. Devolver o microfone não
        pode apagar o volume do alto-falante que ela acabou de ajustar.

        Como toda devolução desta casa, ela devolve o CONTROLE e nunca o
        número: o DualSense não tem leitura de volume, então o firmware
        conserva o último byte que mandamos até a próxima desconexão.
        """
        alvo = self._handle_for(uniq)
        if alvo is None:
            logger.debug("output_offline_noop", op="release_microphone_volume")
            return False
        soltar = getattr(alvo, "soltar_volume_do_microfone", None)
        if not callable(soltar):
            logger.debug("output_handle_sem_porta", op="release_microphone_volume")
            return False
        try:
            soltar()
        except Exception as exc:
            logger.warning(
                "output_handle_failed", op="release_microphone_volume", err=str(exc)
            )
            return False
        logger.info("microphone_volume_released", uniq=uniq, ok=True)
        return True

    def set_microphone_led(
        self, aceso: bool | int | None, *, uniq: str | None = None
    ) -> bool:
        """Assume (`True`/`False`) ou DEVOLVE (`None`) a posse do `common[8]`.

        MIC-DA-MESA-ELEICAO-01 — A PORTA DE EMERGÊNCIA, e ela precisava existir
        ANTES da primeira escrita de LED nova.

        A devolução de posse por-byte já estava construída e testada
        (`_PinnedPyDualSense.set_microphone_led(None)`,
        `tests/unit/test_led_do_mudo_nao_apaga_o_que_o_kernel_acendeu.py`) e
        **não tinha um único chamador de produção**: os dois caminhos de
        escrita passam por `_escrever_led_do_mic`, que só sabe passar `bool`.
        Consequência medida no código: tomada a posse do LED numa sessão, ela
        só caía quando o handle morresse — ou seja, ela teria de desligar o
        controle para o kernel voltar a mandar na luz.

        Isto NÃO é o `RELEASE_LEDS` (0x31, `core/lightbar_reset.py`): aquele só
        existe no rádio, apaga os player-LEDs sempre e trava a lightbar na
        janela pós-conexão. Aqui só o bit `0x01` do flag1 cai, nos dois
        transportes, e nada mais é tocado.

        LUZ-DO-MIC-01 §2 (03/09/2026) — A DEVOLUÇÃO REPINTA ANTES DE SOLTAR.

        `None` não é mais só "derruba o bit": antes de soltar, o valor que
        corresponde ao mudo DE FATO é escrito e ENTREGUE ao aparelho (ver
        `_repintar_antes_de_soltar`). Sem isso a luz ficava presa no último
        valor que escrevemos até ela apertar o botão — foi o que ela mediu com
        dois controles na mesa: *"ambos tão ligados. e ficaram."*

        A repintura vale para os três caminhos porque todos passam por aqui: o
        `mic.led.set {aceso: null}` do IPC, o `mic led-release` da CLI (que é
        casca sobre o IPC) e quem devolver a posse no desligamento do daemon.
        """
        alvo = self._handle_for(uniq)
        if alvo is None:
            logger.debug("output_offline_noop", op="set_microphone_led")
            return False
        tomar = getattr(alvo, "set_microphone_led", None)
        if not callable(tomar):
            logger.warning("output_handle_failed", op="set_microphone_led", err="sem_api")
            return False
        repintado = self._repintar_antes_de_soltar(alvo, uniq) if aceso is None else None
        try:
            tomar(aceso)
        except Exception as exc:
            logger.warning(
                "output_handle_failed", op="set_microphone_led", err=str(exc)
            )
            return False
        logger.info(
            "microphone_led_set", aceso=aceso, uniq=uniq, repintado=repintado
        )
        return True

    def _repintar_antes_de_soltar(self, handle: Any, uniq: str | None) -> int | None:
        """Escreve o mudo REAL no `common[8]` e ENTREGA o report, antes de soltar."""
        if getattr(handle, "_mic_led_desejado", None) is None:
            logger.debug("microphone_led_repintura_no_op_sem_posse", uniq=uniq)
            return None
        if getattr(handle, "_output_muted", False):
            logger.info("microphone_led_repintura_no_op_modo_nativo", uniq=uniq)
            return None
        montar = getattr(handle, "prepareReport", None)
        escrever = getattr(handle, "writeReport", None)
        tomar = getattr(handle, "set_microphone_led", None)
        if not (callable(montar) and callable(escrever) and callable(tomar)):
            logger.warning(
                "microphone_led_repintura_sem_api",
                uniq=uniq,
                detalhe="handle sem prepareReport/writeReport",
            )
            return None
        estado: Any = None
        with contextlib.suppress(Exception):
            estado = self.audio_status_for(uniq)
        mudo = estado.get("mic_mudo") if isinstance(estado, dict) else None
        valor = 1 if mudo else 0
        try:
            tomar(valor)
            escrever(montar())
        except Exception as exc:
            logger.warning("microphone_led_repintura_falhou", uniq=uniq, err=str(exc))
            return None
        logger.info(
            "microphone_led_repintado",
            uniq=uniq,
            valor=valor,
            mudo=mudo,
            no_escuro=mudo is None,
        )
        return valor

    def microphone_mute_for(self, uniq: str | None = None) -> bool | None:
        """Valor de mudo que o HEFESTO afirma no firmware, ou None (MIC-USB-01).

        Contraparte de leitura do `set_microphone_mute`, no mesmo espírito
        honesto do `speaker_state_for`: o DualSense **não devolve** este
        registrador, então a única coisa que dá para saber é o que NÓS estamos
        mandando. Três respostas, e as três significam coisas diferentes:

          - ``True``  — estamos mandando "mudo" em todo report;
          - ``False`` — estamos mandando "não mudo" em todo report;
          - ``None``  — NÃO somos donos do campo: o bit de validação sai
            apagado e quem manda é o `hid-playstation`, que alterna o mute na
            borda do botão físico.

        A distinção entre `False` e `None` é a lição cara do AUDIO-OWNER-01
        (commit `3d9bb7e`): `False` é uma ORDEM ("desmuta"), não um "não
        mexer". Foi confundir os dois que fez o keepalive atropelar o kernel a
        60 Hz. O estado LIDO de verdade (o que o firmware declara) continua
        sendo o `mic_mudo` do `audio_status_for` — este método diz quem MANDA,
        não o que está valendo.

        Sem handle para o `uniq` pedido, devolve None (ausência é resposta).

        MIC-BT-DONO-01: a fonte de verdade passou a ser o MAPA por-uniq, e o
        atributo do handle é só o eco. O motivo é a janela: entre o handle novo
        nascer e o `_reapply_desired` correr, o atributo é `None` e esta função
        respondia *"o kernel é o dono"* sobre um controle de que somos donos —
        e é ela que alimenta o `state_full` e o rótulo da tela.
        """
        from hefesto_dualsense4unix.core.sysfs_leds import norm_mac

        with self._io_lock:
            items = list(self._handles.items())
        for key, handle_da_mesa in items:
            self._levar_ao_mapa_a_posse_que_a_mao_soltou(key, handle_da_mesa)
        alvo = (norm_mac(uniq) if uniq else self.primary_uniq) or None
        if alvo is not None and len(alvo) == 12:
            with self._io_lock:
                if alvo in self._mic_mute_by_uniq:
                    return self._mic_mute_by_uniq[alvo]
        handle = self._handle_for(uniq)
        if handle is None:
            return None
        valor = getattr(handle, "_mic_mute_desejado", None)
        return bool(valor) if isinstance(valor, bool) else None

    def _audio_status_byte(self, uniq: str | None) -> int | None:
        """Byte cru de estado de áudio do handle escolhido (ou None)."""
        handle = self._handle_for(uniq)
        if handle is None:
            return None
        valor = getattr(handle, "_audio_status", None)
        return valor if isinstance(valor, int) else None

    def _handle_for(self, uniq: str | None) -> Any:
        """Handle do controle `uniq`; sem endereço, o ALVO DE SAÍDA — e só
        então o primário.

        **O ALVO ENTROU EM 18/09/2026, e ele fecha a classe inteira.** Os nove
        chamadores deste roteador são os atos de ÁUDIO por controle
        (`set_speaker_volume`, `set_microphone_mute`, `set_microphone_led`,
        `set_microphone_volume`, os três `release_*` e as duas leituras), e
        todos caíam no primário quando a interface não mandava endereço —
        enquanto `led.set`, `rumble.set` e `trigger.*` obedeciam ao seletor.
        Duas línguas de alvo dentro do mesmo backend, e a queixa dela nomeava o
        efeito: *"a mudança dos leds e afins não foram aplicadas pros demais
        controles do app (deveriam ser 4)"*.

        A ordem vai do mais explícito ao menos, e é a MESMA de
        `ipc_handlers._uniq_do_primario`, de propósito — duas contas para "em
        quem isto cai" seria o defeito que esta casa já pagou três vezes.

        **AS LEITURAS NÃO SE MEXEM, e isso foi medido antes:** quem monta o
        `state_full` chama `audio_status_for`/`speaker_state_for` com o `uniq`
        de cada controle, explícito, entrada por entrada. Nenhum caminho quente
        passa `None` esperando o primário.

        **O `_output_target_key` é lido DENTRO do lock que já está aberto**, e
        não por `get_output_target_uniq()`: aquele método toma o mesmo
        `_io_lock`, e chamá-lo daqui seria um deadlock com o backend inteiro
        parado — o `_io_lock` não é reentrante.
        """
        from hefesto_dualsense4unix.core.sysfs_leds import norm_mac

        alvo = norm_mac(uniq) if uniq else None
        with self._io_lock:
            if alvo is None:
                escolhido = self._output_target_key
                if escolhido is not None and escolhido in self._handles:
                    return self._handles[escolhido]
                key = self._primary_key
                return self._handles.get(key) if key is not None else None
            for key, handle in self._handles.items():
                if self._key_to_uniq(key) == alvo:
                    return handle
        return None

    def set_player_leds(self, bits: tuple[bool, bool, bool, bool, bool]) -> None:
        """Aplica bitmask de 5 LEDs de player em TODOS os controles.

        `pydualsense.DSLight.playerNumber` é do tipo `PlayerID` (`IntFlag`), que
        aceita qualquer valor inteiro — não apenas os 4 canônicos (4, 10, 21, 27).
        Isso permite combinações arbitrárias de LEDs sem acesso HID bruto.

        O bitmask é montado como:
          bit0 = bits[0] (LED 1, extremo esquerdo)
          bit1 = bits[1] (LED 2)
          bit2 = bits[2] (LED 3, central — o LED do Player 1 canônico)
          bit3 = bits[3] (LED 4)
          bit4 = bits[4] (LED 5, extremo direito)

        Referência: outReport[44] (USB) / outReport[45] (BT) em
        pydualsense/pydualsense.py:572/636 — recebe `self.light.playerNumber.value`.
        """
        from pydualsense.enums import PlayerID

        if not self._pode_escrever_player_leds():
            logger.info("player_leds_suprimidos_noop", op="set_player_leds")
            return
        bitmask = sum(1 << i for i, b in enumerate(bits) if b)
        self._for_each_led(
            sysfs_op=lambda node: node.set_players(bits),
            pydual_op=lambda h: setattr(h.light, "playerNumber", PlayerID(bitmask)),
            what="set_player_leds",
            record={"player_leds": bits},
            players=bits,
        )
        logger.debug("player_leds_aplicados bits=%s bitmask=%s", list(bits), bitmask)


    def apply_output_defaults(self, spec: OutputSpec) -> ResultadoDeSaida:
        """Aplica `spec` como PADRÃO do perfil em TODOS os controles."""
        fields = _spec_fields(spec)
        if not fields:
            return "nada_a_fazer"
        with self._io_lock:
            havia_alguem_na_mesa = bool(self._handles)
            for name, value in fields.items():
                setattr(self._desired_default, name, value)
        if spec.trigger_left is not None:
            efeito_l = spec.trigger_left
            self._for_each(
                lambda h: self._apply_trigger(h, "left", efeito_l),
                what="apply_output_defaults",
                broadcast=True,
            )
        if spec.trigger_right is not None:
            efeito_r = spec.trigger_right
            self._for_each(
                lambda h: self._apply_trigger(h, "right", efeito_r),
                what="apply_output_defaults",
                broadcast=True,
            )
        if spec.led is not None:
            r, g, b = spec.led
            self._for_each_led(
                sysfs_op=lambda node: node.set_rgb(r, g, b),
                pydual_op=lambda h: h.light.setColorI(r, g, b),
                what="apply_output_defaults",
                broadcast=True,
            )
        if spec.player_leds is not None and self._pode_escrever_player_leds():
            from pydualsense.enums import PlayerID

            bits = spec.player_leds
            bitmask = sum(1 << i for i, b in enumerate(bits) if b)
            self._for_each_led(
                sysfs_op=lambda node: node.set_players(bits),
                pydual_op=lambda h: setattr(h.light, "playerNumber", PlayerID(bitmask)),
                what="apply_output_defaults",
                broadcast=True,
            )
        if spec.player_led_brightness is not None and self._pode_escrever_player_leds():
            degrau_global = spec.player_led_brightness
            with self._io_lock:
                todos = list(self._handles.items())
            for key, handle in todos:
                self._levar_o_brilho_das_luzes(
                    key, handle, degrau_global, what="apply_output_defaults"
                )
        if spec.mic_led is not None:
            flag = spec.mic_led
            self._for_each(
                lambda h: _escrever_led_do_mic(h, flag),
                what="apply_output_defaults",
                broadcast=True,
            )
        return "escreveu" if havia_alguem_na_mesa else "registrado"

    def apply_output_for(
        self,
        uniq: str,
        spec: OutputSpec,
        *,
        procedencia_da_cor: object = None,
        brilho_da_cor: float | None = None,
    ) -> ResultadoDeSaida:
        """Aplica `spec` SÓ no controle de MAC `uniq` e registra o override dele."""
        fields = _spec_fields(spec)
        if not fields:
            return "nada_a_fazer"
        alvo = self._key_to_uniq(uniq)
        if alvo is None:
            logger.warning("apply_output_for_sem_mac_ignorado", uniq=uniq)
            return "sem_alvo"
        with self._io_lock:
            override = self._desired_by_uniq.setdefault(alvo, _DesiredOutput())
            for name, value in fields.items():
                setattr(override, name, value)
            self._stamp_owner_locked(alvo, fields, _LAYER_USER)
            if "led" in fields:
                self._carimbar_procedencia_locked(
                    alvo, fields["led"], procedencia_da_cor, deduzir_todos=True
                )
                self._carimbar_o_brilho_locked(alvo, fields["led"], brilho_da_cor)
            key = self._key_for_uniq(alvo)
            handle = self._handles.get(key) if key is not None else None
            node = self._sysfs.get(key) if key is not None else None
            muted = self._output_mute
            por_fora = handle is not None and (
                node is not None or self._detect_transport(handle) == "bt"
            )
        if handle is None:
            logger.debug(
                "apply_output_for_desconectado_registrado",
                uniq=alvo,
                campos=sorted(fields),
            )
            return "registrado"
        escreveu = self._write_partial_output(
            handle, node, _DesiredOutput(**fields), what="apply_output_for"
        )
        if not escreveu:
            return "falhou"
        sairam = _CAMPOS_QUE_O_NATIVO_ESCREVE if por_fora else frozenset(
            {"player_led_brightness"}
        )
        guardados = sorted(set(fields) - sairam)
        if muted and guardados:
            logger.debug(
                "apply_output_for_modo_nativo_registrado",
                uniq=alvo,
                campos=guardados,
            )
            return "registrado"
        return "escreveu"

    def reset_output_overrides(
        self,
        overrides: Mapping[str, OutputSpec] | None = None,
        *,
        procedencias: Mapping[str, object] | None = None,
    ) -> None:
        """SUBSTITUI o mapa de overrides por-uniq inteiro (gesto da usuária)."""
        novo: dict[str, _DesiredOutput] = {}
        donos: dict[str, dict[str, str]] = {}
        carimbos: dict[str, object] = {}
        for uniq, spec in (overrides or {}).items():
            alvo = self._key_to_uniq(uniq)
            if alvo is None:
                logger.warning("override_por_controle_sem_mac_ignorado", uniq=uniq)
                continue
            campos = _spec_fields(spec)
            novo[alvo] = _DesiredOutput(**campos)
            if campos:
                donos[alvo] = dict.fromkeys(campos, _LAYER_USER)
            if campos.get("led") is not None:
                carimbos[alvo] = (procedencias or {}).get(uniq, LEGADO)
        with self._io_lock:
            self._desired_by_uniq = novo
            self._desired_owner_by_uniq = donos
            self._procedencia_da_cor = carimbos
            self._brilho_da_cor = {}

    def reset_profile_overrides(
        self,
        overrides: Mapping[str, OutputSpec] | None = None,
        *,
        procedencias: Mapping[str, object] | None = None,
    ) -> None:
        """Republica a camada do PERFIL e escreve nos conectados (R-20)."""
        novo: dict[str, dict[str, Any]] = {}
        for uniq, spec in (overrides or {}).items():
            alvo = self._key_to_uniq(uniq)
            if alvo is None:
                logger.warning("override_por_controle_sem_mac_ignorado", uniq=uniq)
                continue
            campos = _spec_fields(spec)
            if campos:
                novo[alvo] = campos
        escritas: list[tuple[Any, Any, _DesiredOutput]] = []
        adiados: dict[str, list[str]] = {}
        with self._io_lock:
            self._clear_layer_locked(_LAYER_PROFILE)
            for alvo, campos in novo.items():
                override = self._desired_by_uniq.setdefault(alvo, _DesiredOutput())
                for nome, valor in campos.items():
                    if getattr(override, nome) is not None:
                        adiados.setdefault(alvo, []).append(nome)
                        continue
                    setattr(override, nome, valor)
                    self._stamp_owner_locked(alvo, (nome,), _LAYER_PROFILE)
                    if nome == "led":
                        self._carimbar_procedencia_locked(
                            alvo, valor, (procedencias or {}).get(alvo, LEGADO)
                        )
            self._prune_overrides_locked()
            for alvo in list(self._desired_by_uniq):
                key = self._key_for_uniq(alvo)
                if key is None:
                    continue
                handle = self._handles.get(key)
                if handle is None:
                    continue
                escritas.append(
                    (handle, self._sysfs.get(key), self._merged_desired_for_key(key))
                )
        for handle, node, out in escritas:
            self._write_partial_output(
                handle, node, out, what="reset_profile_overrides"
            )
        if adiados:
            logger.info(
                "override_do_perfil_cedeu_ao_ajuste_manual",
                controles={uniq: sorted(campos) for uniq, campos in adiados.items()},
            )

    def clear_user_output_overrides(self) -> None:
        """Solta a camada da USUÁRIA no mapa por-uniq (R-20)."""
        with self._io_lock:
            self._clear_layer_locked(_LAYER_USER)

    def set_led_scales(
        self,
        scales: Mapping[str, float] | None = None,
        *,
        brilho_do_perfil: float | None = None,
        cor_do_perfil: Sequence[int] | None = None,
    ) -> None:
        """SUBSTITUI o mapa de escala de brilho por-uniq (R-20 item 2).

        Camada do PERFIL (é do JSON dele que vem), aplicada sobre a BASE do
        merge — o global e a automática do slot, que chegam no brilho do
        perfil — e nunca sobre o override por controle, que já traz o brilho
        dele (`_scaled_led`). Antes, um override que só escrevia
        `lightbar_brightness` era convertido em cor materializada (o RGB global
        escalado) e, como override vence a camada automática, o controle perdia
        a cor do slot para sempre.

        Fator ≤ 0 é aceito (apaga a lightbar daquele controle, que é o que
        brilho 0 significa); ausência de entrada = sem opinião. Sem escrita de
        hardware: o `reassert_resolved_outputs` da ativação converge.

        `brilho_do_perfil` é o brilho a que os fatores são RELATIVOS (o
        `leds.lightbar_brightness` global). Com ele, `brilho_do_perfil * fator`
        é o brilho em que cada peça acende, e é nele que a regra de cor única
        desloca o tom (`led_control.cores_sem_colisao`,
        A-BARRA-NAO-ESCURECE-AO-REAPLICAR-01). `None` guarda o anterior.

        `cor_do_perfil` é a cor GLOBAL do perfil antes do brilho (`None` quando
        não há, como o preto que não é cor). Vai sempre com o brilho, e é o
        par dele: publicar o brilho sem a cor diz *"não se sabe o global"*, e
        o controle no global volta à razão. Com ela, o fator entra numa conta
        só também no global (`led_control.reescalar`, conferência).
        """
        novo: dict[str, float] = {}
        for uniq, fator in (scales or {}).items():
            alvo = self._key_to_uniq(uniq)
            if alvo is None:
                logger.warning("escala_de_brilho_sem_mac_ignorada", uniq=uniq)
                continue
            novo[alvo] = float(fator)
        with self._io_lock:
            self._led_scale_by_uniq = novo
            if brilho_do_perfil is not None:
                self._brilho_do_perfil = max(0.0, min(1.0, float(brilho_do_perfil)))
                self._cor_do_perfil = _rgb_do_perfil(cor_do_perfil)

    def _brilho_da_peca_locked(self, uniq: str) -> float | None:
        """O brilho em que `uniq` acende: o do perfil vezes o fator dele. Sob `_io_lock`."""
        base = self._brilho_do_perfil
        if base is None:
            return None
        fator = self._led_scale_by_uniq.get(uniq, 1.0)
        # o fator é `brilho_do_controle / brilho_do_perfil`, e a volta
        return round(max(0.0, min(1.0, base * fator)), 9)

    def brilho_da_barra_para(self, uniq: str) -> float | None:
        """O brilho em que a barra de `uniq` acende AGORA (leitura pura)."""
        alvo = self._key_to_uniq(uniq)
        if alvo is None:
            return None
        with self._io_lock:
            override = self._desired_by_uniq.get(alvo)
            cor = getattr(override, "led", None)
            if cor is not None:
                carimbo = getattr(self, "_brilho_da_cor", {}).get(alvo)
                if carimbo is not None and carimbo[0] == tuple(cor):
                    return float(carimbo[1])
                dono = self._desired_owner_by_uniq.get(alvo, {}).get("led")
                if dono != _LAYER_PROFILE or not self._brilho_do_perfil:
                    return None
            return self._brilho_da_peca_locked(alvo)

    def luz_do_jogo_para(self, uniq: str) -> bool:
        """O JOGO está pintando a barra de `uniq` agora? (leitura pura)

        A camada do jogo só recebe a cor que o merge ACEITOU (`set_game_output_for`: preto sem
        prova é ausência, e a cor que o perfil escolheu e o jogo ainda não pintou vale), e ela
        cai no fim da sessão (`end_game_session_for`). É o sinal que a aba Iluminação diz como
        «Agora: a cor do jogo».
        """
        alvo = self._key_to_uniq(uniq)
        if alvo is None:
            return False
        with self._io_lock:
            camada = self._game_output_by_uniq.get(alvo)
            return bool(camada is not None and getattr(camada, "led", None) is not None)

    def brilho_das_luzes_para(self, uniq: str) -> int | None:
        """O degrau das luzes de número de `uniq`, RESOLVIDO (leitura pura)."""
        if self._key_to_uniq(uniq) is None:
            return None
        with self._io_lock:
            return self._merged_desired_for_key(uniq).player_led_brightness

    def set_coop_outputs(
        self, outputs: Mapping[str, OutputSpec] | None = None, *, escrever: bool = True
    ) -> None:
        """SUBSTITUI a camada do CO-OP e converge os controles afetados (R-13)."""
        novo: dict[str, _DesiredOutput] = {}
        for uniq, spec in (outputs or {}).items():
            alvo = self._key_to_uniq(uniq)
            if alvo is None:
                logger.debug("coop_output_sem_mac_ignorado", uniq=uniq)
                continue
            campos = {
                nome: valor
                for nome, valor in _spec_fields(spec).items()
                if nome in _COOP_LAYER_FIELDS
            }
            if not campos:
                logger.debug("coop_output_sem_campo_valido", uniq=alvo)
                continue
            novo[alvo] = _DesiredOutput(**campos)
        escritas: list[tuple[Any, Any, _DesiredOutput]] = []
        with self._io_lock:
            antigo = self._desired_coop_by_uniq
            if antigo == novo:
                return
            self._desired_coop_by_uniq = novo
            for alvo in set(antigo) | set(novo):
                key = self._key_for_uniq(alvo)
                handle = self._handles.get(key) if key is not None else None
                if key is None or handle is None:
                    continue
                if not escrever and (key in self._sysfs or self._detect_transport(handle) == "bt"):
                    continue
                bits = self._merged_desired_for_key(key).player_leds
                if bits is None:
                    continue
                escritas.append(
                    (handle, self._sysfs.get(key), _DesiredOutput(player_leds=bits))
                )
        for handle, node, out in escritas:
            self._write_partial_output(
                handle, node, out, what="set_coop_outputs"
            )
        if escritas:
            logger.info(
                "camada_do_coop_escrita",
                numeros={
                    _endereco_mascarado(u) or "?": numero_do_desenho(d.player_leds)
                    for u, d in novo.items()
                },
            )

    def set_rumble_for(self, uniq: str, weak: int, strong: int) -> bool:
        """Rumble mirado no controle de MAC `uniq`, SEM tocar no seletor global.

        PERFIL-01: substitui o flip transitório do `_output_target_key` que o
        `apply_game_rumble` fazia — com o estado desejado keyed pelo alvo lido
        de um global mutável, a corrida com o executor multi-thread
        (max_workers=2) persistiria config no controle errado. O rumble segue
        transitório (nunca entra no desejado). Devolve False quando o MAC não
        casa com nenhum handle (o chamador decide o fallback broadcast).
        """
        alvo = self._key_to_uniq(uniq)
        if alvo is None:
            return False
        with self._io_lock:
            key = self._key_for_uniq(alvo)
            handle = self._handles.get(key) if key is not None else None
        if handle is None:
            return False
        # POR-UNIDADE-01: o co-op mira UMA peça, e a peça pode ter escala
        # própria do perfil. Escalar aqui também é o que impede a incoerência
        # de o mesmo controle vibrar diferente conforme a rota (co-op x jogo).
        eff_weak, eff_strong = self._escalar_rumble(str(key), weak, strong)
        try:
            handle.setLeftMotor(eff_strong)
            handle.setRightMotor(eff_weak)
        except Exception as exc:
            logger.warning("output_handle_failed", op="set_rumble_for", key=key, err=str(exc))
        return True


    def set_haptica_de_audio_for(self, uniq: str, ativa: bool) -> bool:
        """A háptica por áudio tocando (ou não) no controle de MAC `uniq`.

        A-VIBRACAO-NAO-DESLIGA-A-HAPTICA-01: o handle dele manda o rumble sem
        `HAPTICS_SELECT` enquanto ela toca (:meth:`_PinnedPyDualSense.
        set_haptica_de_audio`). Vale nos dois transportes, porque o bit é o
        mesmo no `0x02` do cabo e no `0x31` do rádio. Devolve False quando o
        MAC não casa com handle nenhum. O que foi dito fica no mapa por MAC, e
        o handle que nasce depois (a reconexão, a troca de nó) o recebe em
        :meth:`_reapply_desired`.
        """
        alvo = self._key_to_uniq(uniq)
        if alvo is None:
            return False
        with self._io_lock:
            if ativa:
                self._haptica_de_audio_por_uniq.add(alvo)
            else:
                self._haptica_de_audio_por_uniq.discard(alvo)
            key = self._key_for_uniq(alvo)
            handle = self._handles.get(key) if key is not None else None
        definir = getattr(handle, "set_haptica_de_audio", None)
        if not callable(definir):
            return False
        definir(bool(ativa))
        return True

    def set_game_trigger_for(self, uniq: str, side: Side, block: bytes) -> bool:
        """Aplica no físico `uniq` o trigger effect CRU que o jogo mandou ao vpad."""
        alvo = self._key_to_uniq(uniq)
        if alvo is None:
            return False
        block_b = bytes(block)
        if len(block_b) != GAME_TRIGGER_BLOCK_LEN:
            logger.warning(
                "game_trigger_bloco_invalido", uniq=alvo, tamanho=len(block_b)
            )
            return False
        lado = "left" if side == "left" else "right"
        with self._io_lock:
            # O jogo manda no gatilho, de qualquer perfil e do Freestyle (decisão
            # dela de 03/10/2026, que revoga a PERFIL-MANDA-01 de 16/09) — mas o
            # «sem efeito» de quem nunca mandou um efeito é ausência, e o perfil
            # vale até o jogo provar (04/10/2026).
            if alvo not in self._jogo_provou_o_gatilho:
                if gatilho_do_jogo_sem_efeito(block_b):
                    ja_dito = self._recusa_ao_jogo_logada.setdefault(alvo, set())
                    if "ausência:gatilho" not in ja_dito:
                        ja_dito.add("ausência:gatilho")
                        logger.info(
                            "game_trigger_sem_efeito_e_ausencia_o_perfil_vale",
                            uniq=alvo,
                            lado=lado,
                        )
                    return True
                self._jogo_provou_o_gatilho.add(alvo)
                logger.info("game_trigger_provou", uniq=alvo, lado=lado)
            self._game_triggers_by_uniq.setdefault(alvo, {})[lado] = block_b
            key = self._key_for_uniq(alvo)
            handle = self._handles.get(key) if key is not None else None
        if handle is None:
            return True
        attr = "_raw_trigger_left" if lado == "left" else "_raw_trigger_right"
        try:
            setattr(handle, attr, block_b)
        except Exception as exc:
            logger.warning(
                "output_handle_failed", op="set_game_trigger_for", key=key,
                err=str(exc),
            )
        return True

    def set_game_output_for(
        self,
        uniq: str,
        *,
        led: tuple[int, int, int] | None = None,
        player_leds: tuple[bool, bool, bool, bool, bool] | None = None,
    ) -> bool:
        """Aplica no físico `uniq` a lightbar que o jogo pintou no vpad."""
        alvo = self._key_to_uniq(uniq)
        if alvo is None:
            return False
        fields: dict[str, Any] = {}
        if led is not None:
            r, g, b = led
            fields["led"] = (int(r) & 0xFF, int(g) & 0xFF, int(b) & 0xFF)
        if player_leds is not None:
            fields["player_leds"] = tuple(bool(x) for x in player_leds)
        if not fields:
            return True
        defender = False
        with self._io_lock:
            numero = numeracao_do_jogo(fields)
            if numero:
                recusa = {campo: fields.pop(campo) for campo in sorted(numero)}
                ja_dito = self._recusa_ao_jogo_logada.setdefault(alvo, set())
                marcas = {f"numero:{campo}" for campo in recusa}
                if not marcas <= ja_dito:
                    ja_dito.update(marcas)
                    logger.info(
                        "game_output_recusado_o_hefesto_numera",
                        uniq=alvo,
                        campos=sorted(recusa),
                        **self._luz_para_o_journal(recusa),
                    )
                if not fields:
                    return True
            if (
                fields.get("led") == (0, 0, 0)
                and alvo not in self._jogo_provou_a_luz
            ):
                fields.pop("led")
                ja_dito = self._recusa_ao_jogo_logada.setdefault(alvo, set())
                if "ausência:luz" not in ja_dito:
                    ja_dito.add("ausência:luz")
                    logger.info(
                        "game_output_preto_e_ausencia_o_perfil_vale", uniq=alvo
                    )
                if not fields:
                    return True
            wins = bool(fields) and self._game_wins()
            if wins and fields.get("led") is not None:
                self._jogo_provou_a_luz.add(alvo)
            if fields and not wins:
                retido = self._retained_game_outputs.setdefault(alvo, {})
                retido.update(fields)
                if self._retained_log_armed:
                    logger.info(
                        "game_output_retido_sem_jogo",
                        uniq=alvo,
                        campos=sorted(fields),
                        **self._luz_para_o_journal(fields),
                    )
                    self._retained_log_armed = False
                defender = self._pode_defender_locked()
        if not wins:
            if defender:
                self.defend_display()
            return True
        with self._io_lock:
            layer = self._game_output_by_uniq.setdefault(alvo, _DesiredOutput())
            novas = sorted(name for name in fields if getattr(layer, name) is None)
            for name, value in fields.items():
                setattr(layer, name, value)
            if novas:
                logger.info(
                    "game_output_replicado",
                    uniq=alvo,
                    campos=novas,
                    **self._luz_para_o_journal(fields),
                )
            key = self._key_for_uniq(alvo)
            handle = self._handles.get(key) if key is not None else None
            node = self._sysfs.get(key) if key is not None else None
        if handle is None:
            return True
        self._write_partial_output(
            handle, node, _DesiredOutput(**fields), what="game_output_replica"
        )
        return True

    def replay_retained_game_outputs(self) -> None:
        """Abertura do gate (NUMA-02): a luz RETIDA sob 'daemon' é DESCARTADA."""
        with self._io_lock:
            retidos = self._retained_game_outputs
            self._retained_game_outputs = {}
            self._retained_log_armed = True
            descartes = [
                (alvo, sorted(campos), self._luz_para_o_journal(campos))
                for alvo, campos in retidos.items()
            ]
        for alvo, campos, luz in descartes:
            logger.info(
                "game_output_retido_descartado_na_abertura",
                uniq=alvo,
                campos=campos,
                **luz,
            )

    def _autoridade_de_exibicao(self) -> str:
        """A autoridade de exibição como o journal a escreve — não decide nada."""
        provider = self._game_authority_provider
        if provider is None:
            return "sem_provider"
        try:
            return str(provider())
        except Exception:
            return "provider_falhou"

    def _luz_para_o_journal(self, campos: dict[str, Any]) -> dict[str, Any]:
        """`cor`, `players` e `autoridade` de uma réplica de exibição, para o log."""
        return {
            "cor": campos.get("led"),
            "players": campos.get("player_leds"),
            "autoridade": self._autoridade_de_exibicao(),
        }

    def end_game_session_for(self, uniq: str) -> bool:
        """Fim da sessão de jogo do controle `uniq`: devolve perfil/paleta/co-op."""
        alvo = self._key_to_uniq(uniq)
        if alvo is None:
            return False
        with self._io_lock:
            game = self._game_output_by_uniq.pop(alvo, None)
            triggers = self._game_triggers_by_uniq.pop(alvo, None)
            retido = self._retained_game_outputs.pop(alvo, None)
            self._recusa_ao_jogo_logada.pop(alvo, None)
            self._jogo_provou_o_gatilho.discard(alvo)
            self._jogo_provou_a_luz.discard(alvo)
            key = self._key_for_uniq(alvo)
            handle = self._handles.get(key) if key is not None else None
            node = self._sysfs.get(key) if key is not None else None
            desired = (
                self._merged_desired_for_key(key) if key is not None else None
            )
        if game is None and triggers is None:
            if retido:
                logger.info(
                    "game_output_retido_descartado_no_close",
                    uniq=alvo,
                    campos=sorted(retido),
                    **self._luz_para_o_journal(retido),
                )
            return True
        logger.info(
            "game_session_devolvida",
            uniq=alvo,
            lightbar=bool(game is not None and game.led is not None),
            player_leds=bool(game is not None and game.player_leds is not None),
            triggers=sorted(triggers) if triggers else [],
        )
        if handle is None or desired is None:
            return True
        if triggers:
            with contextlib.suppress(Exception):
                handle._raw_trigger_left = None
                handle._raw_trigger_right = None
            lados: tuple[tuple[Side, str], ...] = (
                ("left", "trigger_left"),
                ("right", "trigger_right"),
            )
            for lado, campo in lados:
                if lado not in triggers:
                    continue
                effect = getattr(desired, campo)
                try:
                    if effect is not None:
                        self._apply_trigger(handle, lado, effect)
                    else:
                        self._reset_trigger(handle, lado)
                except Exception as exc:
                    logger.warning(
                        "output_handle_failed", op="end_game_session_trigger",
                        key=key, err=str(exc),
                    )
        restore = _DesiredOutput()
        if game is not None and game.led is not None:
            if node is not None:
                with contextlib.suppress(Exception):
                    node.invalidate_cache()
            restore.led = desired.led
        if game is not None and game.player_leds is not None:
            restore.player_leds = desired.player_leds
        self._write_partial_output(
            handle, node, restore, what="game_session_close"
        )
        return True

    @staticmethod
    def _reset_trigger(handle: pydualsense, side: Side) -> None:
        """Volta um gatilho a Off (sem efeito) — o estado de fábrica do firmware."""
        from pydualsense.enums import TriggerModes

        trigger = handle.triggerL if side == "left" else handle.triggerR
        trigger.mode = TriggerModes.Off
        for idx in range(7):
            trigger.setForce(idx, 0)

    def resolved_player_leds_for(
        self, uniq: str
    ) -> tuple[bool, bool, bool, bool, bool] | None:
        """Padrão de player-LED RESOLVIDO do controle `uniq` (leitura pura)."""
        with self._io_lock:
            return self._merged_desired_for_key(uniq, incluir_coop=False).player_leds

    def resolved_led_for(self, uniq: str) -> tuple[int, int, int] | None:
        """Cor de lightbar RESOLVIDA do controle `uniq` (leitura pura).

        STATUS-01/COR-05: espelho de `resolved_player_leds_for` para o campo
        `led` — o MERGE POR CAMPO (default broadcast + override por-uniq) pelo
        MESMO resolvedor dos reasserts (`_merged_desired_for_key`). É a fonte
        do `lightbar_source == "desired"` do handler IPC: quando o nó sysfs
        não é gravável (escrita foi por hidraw → classe LED stale por
        construção), esta é a última cor que o daemon mandou aplicar.

        Nota (D8 — divergência fundamentada, registrada na
        onda): o valor devolvido é PÓS-escala de brilho — `_DesiredOutput.led`
        guarda o RGB como chegou ao `set_led`, e o manager pré-escala
        `lightbar_brightness` na borda (`led_control.py`). O D8 original pedia
        expor também a cor-identidade PRÉ-brilho, mas separá-la exigiria
        refactor do estado desejado (fora do escopo desta frente); o objetivo
        do D8 (traços legíveis com cor escura) foi resolvido por outra via —
        o contraste do traço é ajustado na borda da GUI, clareando
        a cor e preservando o matiz. None = nenhum perfil/GUI setou cor ainda. Não toca
        hardware nem muta estado.
        """
        with self._io_lock:
            return self._merged_desired_for_key(uniq).led


    def bordas_do_mic(self) -> dict[str, tuple[int, bool, float | None]]:
        """Contador de APERTOS do botão do microfone, por `uniq`.

        `{uniq: (seq, mudo, quando)}` — `seq` é monotônico por controle e só
        sobe quando o DEDO desce no botão (O-BOTAO-DO-MIC-SO-OBEDECE-A-MAO-01,
        28/09/2026: não mais quando o bit de mudo vira); `mudo` é o que o
        último aperto PEDE (o contrário do que o firmware segurava) e, antes do
        primeiro aperto, o bit lido — que ninguém publica, porque o `seq` não
        andou; `quando` é o `time.monotonic()` do último aperto.

        POR QUE ESTE É O ÚNICO LUGAR POSSÍVEL. É aqui que o produto vê todo
        report de TODO controle **com identidade** — cada `_PinnedPyDualSense`
        tem fd, thread e byte de áudio próprios. As duas alternativas não
        servem, e não é preferência:

        - `EventTopic.BUTTON_DOWN` **não carrega `uniq`** (contrato de perfil e
          de plugin, `profiles/schema.py`); dar-lhe um endereço quebraria os
          dois. Além disso o botão do mic nem chega ali: o `hid-playstation`
          consome a borda e ela não vira evdev.
        - `read_state()` só enxerga o PRIMÁRIO — numa mesa de quatro, três
          apertos ficariam sem dono.

        Handles sem `uniq` resolvível (key por path, sem serial) ficam de fora:
        eleição sem endereço é eleição do controle errado.

        **O MAPA DA POSSE ACOMPANHA A MÃO.** O aperto solta a posse do mudo no
        handle, na thread do report (`_registrar_borda_do_mic`); o mapa
        por-uniq (`_mic_mute_by_uniq`, MIC-BT-DONO-01) é quem a rependura na
        reconexão e quem responde `microphone_mute_for`. Aqui, na leitura que o
        laço das bordas faz a 20 Hz ANTES de publicar o aperto, o mapa solta
        junto — pelo dono único, `_levar_ao_mapa_a_posse_que_a_mao_soltou`.
        """
        with self._io_lock:
            items = list(self._handles.items())
        out: dict[str, tuple[int, bool, float | None]] = {}
        for key, handle in items:
            self._levar_ao_mapa_a_posse_que_a_mao_soltou(key, handle)
            uniq = self._key_to_uniq(key)
            if uniq is None:
                continue
            seq = getattr(handle, "_mic_mudo_seq", None)
            lido = getattr(handle, "_mic_mudo", None)
            if not isinstance(seq, int) or not isinstance(lido, bool):
                continue
            pedido = getattr(handle, "_mic_mudo_pedido", None)
            mudo = pedido if isinstance(pedido, bool) else lido
            quando = getattr(handle, "_mic_mudo_em", None)
            out[uniq] = (seq, mudo, quando if isinstance(quando, float) else None)
        return out

    def _levar_ao_mapa_a_posse_que_a_mao_soltou(self, key: str, handle: Any) -> None:
        """Leva ao mapa por-uniq a posse do mudo que o aperto soltou no handle.

        O-BOTAO-DO-MIC-SO-OBEDECE-A-MAO-01 (28/09/2026). O aperto solta a posse
        no handle, na thread do report, e deixa a marca
        `_mic_posse_solta_pela_mao`; o mapa `_mic_mute_by_uniq` é quem responde
        `microphone_mute_for` (o `mic_mudo_desejado` do `state_full`, que a
        tela pinta) e quem rependura a posse na reconexão. **Esta função é a
        única que consome a marca**, e ela é chamada de todo lugar que lê o
        mapa ou perde o handle: as bordas, a pergunta de quem manda, e a saída
        do handle (`disconnect`, o hotplug e a troca de nó).

        O laço das bordas sozinho não bastava: o handle que sai (desconecta, ou
        o nó troca) leva a marca sem borda nenhuma, e o mapa seguiria dizendo
        «o Hefesto manda mudo» à tela e rependurando o mudo velho na reconexão.
        (O laço das bordas sobe sempre desde 03/10/2026, sem o
        `mic_button_toggles_system`: `hotkey.start_mic_do_jogo`.) Dois lugares
        que precisam concordar, acertados por caminhos diferentes, é a família
        de defeito que esta casa já nomeia.

        Só solta se ninguém tomou a posse de novo depois do aperto: o ato (ou o
        perfil) que escreveu por cima vale.
        """
        if not getattr(handle, "_mic_posse_solta_pela_mao", False):
            return
        handle._mic_posse_solta_pela_mao = False
        if getattr(handle, "_mic_mute_desejado", None) is not None:
            return
        uniq = self._key_to_uniq(key)
        if uniq is None:
            return
        self._registrar_posse_do_mudo(uniq, None)
        logger.info("mic_posse_solta_pela_mao", uniq=uniq)


    def describe_controllers(self) -> list[dict[str, object]]:
        """Descreve cada controle conectado (observabilidade — IPC `controller.list`).

        Uma entrada por handle aberto:
        `{index, connected, transport, is_primary, uniq, battery_pct, battery_state}`.
        O `index` (FEAT-DSX-CONTROLLER-SELECTOR-01) é a POSIÇÃO em
        `list(self._handles)` (0 = primário) — o mesmo número que o seletor de
        controle usa em `set_output_target`.

        FEAT-STATE-PER-CONTROLLER-01: `uniq` é o MAC normalizado do controle
        (mesma normalização do `primary_uniq`; None quando a key é um path sem
        serial) e `battery_pct` é a bateria 0-100 POR CONTROLE lida do handle
        (None quando desconectado ou o firmware ainda não reportou) — a GUI
        identifica cada card e mostra a carga sem chamada IPC extra. Quando
        nenhum controle está conectado, devolve uma única entrada offline
        (preserva o contrato "ao menos um item" do handler legado).
        """
        with self._io_lock:
            items = list(self._handles.items())
            primary = self._primary_key
        if not items:
            return [{"connected": False, "transport": None, "is_primary": False}]
        out: list[dict[str, object]] = []
        for idx, (key, handle) in enumerate(items):
            connected = bool(getattr(handle, "connected", False))
            out.append(
                {
                    "index": idx,
                    "connected": connected,
                    "transport": self._detect_transport(handle) if connected else None,
                    "is_primary": key == primary,
                    "uniq": self._key_to_uniq(key),
                    **self._carga(handle, connected),  # battery_pct + battery_state
                }
            )
        return out

    @staticmethod
    def _key_to_uniq(key: str) -> str | None:
        """MAC normalizado da key de um handle, ou None quando a key é um path.

        FEAT-STATE-PER-CONTROLLER-01: mesma normalização do `primary_uniq`
        (`norm_mac`), com guarda de comprimento — um MAC real tem exatamente
        12 dígitos hex. A key de fallback por path ("/dev/hidrawN") também
        contém dígitos hex soltos e, sem a guarda, viraria um pseudo-MAC
        ("deda4") — identificador ERRADO no card da GUI.
        """
        from hefesto_dualsense4unix.core.sysfs_leds import norm_mac

        normalized = norm_mac(key)
        if normalized is None or len(normalized) != 12:
            return None
        return normalized

    def _carga(self, handle: pydualsense, connected: bool) -> dict[str, object]:
        """As DUAS metades da bateria de um handle, num par que não se separa.

        BATERIA-PARADA-01 (B1). `battery_pct` é o número e `battery_state` é o
        estado de carga — e eles vêm do MESMO byte (`states[53]`: nibble baixo
        = nível, nibble alto = carga). Nasceram numa função só justamente
        porque a queixa dela era a metade que faltava: *"o percentual nunca é
        atualizado"* descrevia um 100% mudo, que é indistinguível de uma barra
        travada quando ninguém diz "no cabo".

        Desconectado devolve os dois `None`: leitura fantasma de handle fechado
        é pior que ausência.
        """
        if not connected:
            return {"battery_pct": None, "battery_state": None}
        return {
            "battery_pct": self._read_battery_opt(handle),
            "battery_state": self._read_battery_state_opt(handle),
        }

    def reassert_resolved_outputs(self, *, verify: bool = False) -> None:
        """Re-aplica o desired RESOLVIDO por-controle (3 camadas) via sysfs."""
        with self._io_lock:
            check = verify and not self._game_wins()
            posse = set(self._sysfs_written) if check else set()
            reasserts = [
                (key, node, self._merged_desired_for_key(key))
                for key, node in self._sysfs.items()
            ]
            do_cabo = [
                (key, self._handles.get(key), desired.player_led_brightness)
                for key, _no, desired in reasserts
                if self._handles.get(key) is not None
                and self._detect_transport(self._handles.get(key)) != "bt"
            ]
        for key, handle, degrau in do_cabo:
            self._levar_o_brilho_das_luzes(
                key, handle, degrau, what="reassert_resolved_outputs"
            )
        for key, node, desired in reasserts:
            with contextlib.suppress(Exception):
                verificar = check and key in posse
                if desired.led is not None:
                    ok = (
                        node.set_rgb(*desired.led, verify=True)
                        if verificar
                        else node.set_rgb(*desired.led)
                    )
                    if ok:
                        self.record_sysfs_write(key, desired.led)
                if desired.player_leds is not None:
                    escrever_verificado = (
                        getattr(node, "set_players_verified", None)
                        if verificar
                        else None
                    )
                    if callable(escrever_verificado):
                        escrever_verificado(desired.player_leds)
                    else:
                        node.set_players(desired.player_leds)

    def defend_display(self) -> None:
        """Defesa de exibição: invalida os caches sysfs + reassert verificado."""
        with self._io_lock:
            self._defend_last_at = time.monotonic()
            nodes = list(self._sysfs.values())
        for node in nodes:
            with contextlib.suppress(Exception):
                node.invalidate_cache()
        self.reassert_resolved_outputs(verify=True)

    def set_output_mute(self, muted: bool) -> None:
        """Muta/desmuta TODA escrita de output HID (FEAT-NATIVE-OUTPUT-MUTE-01)."""
        with self._io_lock:
            self._output_mute = bool(muted)
            for handle in self._handles.values():
                with contextlib.suppress(Exception):
                    handle._output_muted = self._output_mute
                    if not self._output_mute:
                        handle._last_out_report = None
            reasserts = (
                [
                    (key, node, self._merged_desired_for_key(key))
                    for key, node in self._sysfs.items()
                ]
                if not muted
                else []
            )
        for key, node, desired in reasserts:
            with contextlib.suppress(Exception):
                if desired.led is not None and node.set_rgb(*desired.led):
                    self.record_sysfs_write(key, desired.led)
                if desired.player_leds is not None:
                    node.set_players(desired.player_leds)
        logger.info("backend_output_mute", muted=bool(muted))

    def set_output_target(self, index: int | None) -> int | None:
        """Define o ALVO das ações de output (FEAT-DSX-CONTROLLER-SELECTOR-01)."""
        with self._io_lock:
            if index is None:
                self._output_target_key = None
                return None
            keys = list(self._handles)
            if not (0 <= index < len(keys)):
                self._output_target_key = None
                return None
            self._output_target_key = keys[index]
            return index

    def get_output_target_index(self) -> int | None:
        """Posição atual do alvo de output, ou None (FEAT-DSX-CONTROLLER-SELECTOR-01)."""
        with self._io_lock:
            key = self._output_target_key
            if key is None or key not in self._handles:
                return None
            return list(self._handles).index(key)

    def get_output_target_uniq(self) -> str | None:
        """MAC do alvo de output de AGORA, ou None quando o alvo é "todos"."""
        with self._io_lock:
            key = self._output_target_key
            if key is None or key not in self._handles:
                return None
        return self._key_to_uniq(key)

    def get_battery(self) -> int:
        ds = self._ds
        if ds is None:
            return 0
        return self._read_battery_raw(ds)

    def get_transport(self) -> Transport:
        return self._transport

    def _require(self) -> pydualsense:
        ds = self._ds
        if ds is None:
            raise RuntimeError("pydualsense não inicializado — chamar connect() antes")
        return ds

    @staticmethod
    def _detect_transport(ds: pydualsense) -> Transport:
        con = getattr(ds, "conType", None)
        if con is None:
            return "usb"
        name = str(getattr(con, "name", con)).lower()
        return "usb" if "usb" in name else "bt"

    @staticmethod
    def _read_battery_opt(ds: pydualsense) -> int | None:
        """Bateria 0-100 de UM handle, ou None quando indisponível.

        FEAT-STATE-PER-CONTROLLER-01: leitura barata — só getattrs no objeto
        `DSBattery` que o report_thread da pydualsense atualiza (sem HID I/O
        extra; seguro fora do `_io_lock`, mesmo cuidado do `read_state`).
        Preserva a distinção "sem dado ainda" (None) de "0%": a GUI não deve
        mostrar 0% falso num controle recém-plugado.

        **ESTA DOCSTRING PROMETIA O QUE A FUNÇÃO NÃO FAZIA — curado em
        16/09/2026 (BATERIA-QUE-PULA-01).** Ela devolvia `None` só quando
        `level is None`, nunca quando `level == 0`. E `DSBattery.__init__` nasce
        com `Level = 0`: todo handle recém-aberto — ou seja, **toda reconexão de
        rádio** — publicava `battery_pct = 0` até o primeiro report chegar, e o
        cartão pintava isso como «0%». É a origem do zero que ela viu no meio do
        75/0/90/100, e o único caminho que o explica.

        A função IRMÃ logo abaixo (`_read_battery_state_opt`) já tinha a guarda
        e a explicava por extenso: *"Level 0 é 'ninguém reportou ainda'"*. Duas
        funções gêmeas, uma com a disciplina e a outra sem — e a que faltava era
        a que a tela lê.

        **O contrato legado NÃO muda:** `_read_battery_raw` continua convertendo
        `None` em `0` de propósito, porque `core/controller.py` valida `0` como
        legal e há consumidores que contam com um `int` sempre. Quem quer saber
        se HÁ dado pergunta a esta função; quem quer um número sempre pergunta
        àquela. A distinção é o ponto.

        Um DualSense de verdade nunca reporta 0: o nibble mínimo dá
        `0*10+5 = 5`, e em 600 amostras medidas o menor valor foi 5.
        """
        battery = getattr(ds, "battery", None)
        level = getattr(battery, "Level", None) if battery is not None else None
        if level is None:
            return None
        try:
            value = int(level)
        except (TypeError, ValueError):
            return None
        if value <= 0:
            return None
        return max(0, min(100, value))

    @staticmethod
    def _read_battery_state_opt(ds: pydualsense) -> str | None:
        """Estado de carga de UM handle (:data:`ESTADO_DE_CARGA`), ou None."""
        battery = getattr(ds, "battery", None)
        if battery is None:
            return None
        level = getattr(battery, "Level", None)
        estado = getattr(battery, "State", None)
        if level is None or estado is None:
            return None
        try:
            if int(level) <= 0:
                return None
            nibble = int(estado)
        except (TypeError, ValueError):
            return None
        return ESTADO_DE_CARGA.get(nibble & 0x0F)

    @staticmethod
    def _read_battery_raw(ds: pydualsense) -> int:
        value = PyDualSenseController._read_battery_opt(ds)
        return 0 if value is None else value

    @staticmethod
    def _coerce_mode(mode: int) -> object:
        from pydualsense.enums import TriggerModes
        try:
            return TriggerModes(mode)
        except ValueError:
            logger.warning("trigger_mode_fora_do_enum_mantendo_raw", mode=mode)
            return mode


    _posto_vago_de: str | None = None
    _espera_do_posto: Callable[[str], bool] | None = None

    def set_espera_do_posto(self, pergunta: Callable[[str], bool] | None) -> None:
        """Pendura quem decide se o posto do primário que caiu ESPERA por ele."""
        with self._io_lock:
            self._espera_do_posto = pergunta

    def _uniq_do_dono_do_posto(self) -> str | None:
        """O MAC do dono do posto de P1: o primário, ou quem a vaga espera.

        É o que o `primary_uniq` responde. Durante a vaga, o vpad do P1 continua
        sendo DO P1: o rumble e a cor que o jogo manda para ele miram o endereço
        do P1 ausente e são descartados com log (BROADCAST-PROIBIDO-01), em vez
        de cair em broadcast nos três que ficaram; a máscara dele segue com
        ele; e o co-op não senta o P1 como secundário quando ele volta.
        """
        chave = self._primary_key or self._posto_vago_de
        return self._key_to_uniq(chave) if chave else None

    def _quem_senta_no_posto(self, sentado: str | None = None) -> str | None:
        """Quem ocupa o posto de P1 que ficou vazio — ou None, se ele ESPERA.

        Chamado pelo `_recompute_primary`, sob o `_io_lock`. Com o primário
        `sentado` na mesa, a pergunta é outra: a carta menor chegou? — ver
        `_a_carta_menor_locked` (O-MODO-XBOX-NAO-E-QUEDA-02, item 4). Com o
        posto vazio, senta quem tem a carta menor, e não o 1º que conectou.

        **A DECISÃO (24/09/2026, por delegação dela,
        `D-2409-O-JOGO-ESPERA-O-LUGAR-GUARDADO`):** o jogo também espera a carta
        1. Com o P1 fora dentro do prazo, o P2 virava primário na hora e passava
        a dirigir o vpad do jogador 1 do jogo enquanto a lâmpada e a tela
        diziam 2 — um número que a lâmpada mostra e o jogo não segue, o defeito
        que a STEAM-NO-FISICO-01 curou. Agora o posto fica VAGO: o vpad do P1
        segue de pé e parado (o `read_state` devolve o neutro), o P2 continua no
        vpad 2, e quem chega de volta dentro do prazo retoma o posto pelo
        caminho de sempre (`_posto_reservado_de_volta`).

        Vaga só quando as duas partes dizem que sim:

        - **a reserva do posto** (`_primario_deposto`, `PRIMARIO_RESERVA_SEC`, no
          relógio único `relogio_do_prazo`) — passado o prazo, vale a NUM-01 e
          o próximo mais antigo assume;
        - **a pergunta pendurada** (`set_espera_do_posto`): o co-op de pé, o jogo
          com a autoridade e o lugar dele guardado na mesa. Sem pergunta, ou
          com ela dizendo não, é a regra de sempre — e é o gesto dela de
          desligar um controle e seguir com o outro, fora do co-op.

        Nunca deixa a mesa sem ninguém à toa: sem handle nenhum não há vaga a
        guardar (o posto fica vazio porque ninguém está na mesa).
        """
        if sentado is not None and sentado in self._handles:
            return self._a_carta_menor_locked(sentado)
        reserva = self._primario_deposto
        pergunta = self._espera_do_posto
        if reserva is not None and self._handles and self._a_troca_espera_locked(reserva[0]):
            if self._posto_vago_de != reserva[0]:
                self._posto_vago_de = reserva[0]
                logger.info(
                    "posto_do_p1_espera",
                    key=reserva[0],
                    transporte=self._transport,
                    motivo="troca_de_transporte",
                )
            return None
        if reserva is not None and pergunta is not None and self._handles:
            chave = reserva[0]
            uniq = self._key_to_uniq(chave)
            if uniq is not None and chave not in self._handles:
                try:
                    espera = bool(pergunta(uniq))
                except Exception as exc:
                    logger.warning("posto_do_p1_pergunta_falhou", err=str(exc))
                    espera = False
                if espera:
                    if self._posto_vago_de != chave:
                        self._posto_vago_de = chave
                        logger.info(
                            "posto_do_p1_espera", key=chave, transporte=self._transport
                        )
                    return None
        if self._posto_vago_de is not None:
            logger.info("posto_do_p1_liberado", key=self._posto_vago_de)
            self._posto_vago_de = None
        return next(iter(self._na_ordem_da_carta_locked(list(self._handles))), None)

    def _ds_depois_da_vaga(self) -> pydualsense | None:
        """O handle do P1 para o `read_state` enquanto o posto está vago."""
        with self._io_lock:
            if self._primary_key is None and self._posto_vago_de is not None:
                self._recompute_primary()
            elif self._primary_key is not None:
                self._posto_vago_de = None
            return self._ds

    #: A última carga lida do dono do posto de P1, `(battery_pct, battery_state)`
    _carga_do_posto: tuple[int, str | None] = (0, None)

    def _ler_a_carga_do_posto(self, ds: pydualsense) -> tuple[int, str | None]:
        """A carga do primário, lida no tique do `read_state` e guardada para a vaga.

        As duas metades num par só (BATERIA-PARADA-01), no contrato legado do
        topo: `battery_pct` sempre `int`, 0 enquanto o controle não reportou.
        Guardar custa uma atribuição por tique.
        """
        carga = (self._read_battery_raw(ds), self._read_battery_state_opt(ds))
        self._carga_do_posto = carga
        return carga

    def _carga_do_posto_vago(self) -> dict[str, Any]:
        """A carga do topo quando o `read_state` não tem primário."""
        if self._posto_vago_de is None:
            return {"battery_pct": 0, "battery_state": None}
        battery, carga = self._carga_do_posto
        return {"battery_pct": battery, "battery_state": carga}


    _trocas_de_transporte: dict[str, float] | None = None
    _transportes_da_sessao: dict[str, set[str]] | None = None

    def iniciar_troca_de_transporte(self, uniq: str, *, motivo: str) -> bool:
        """Segura o lugar do controle `uniq` enquanto ele troca de transporte."""
        from hefesto_dualsense4unix.core.sysfs_leds import norm_mac

        alvo = norm_mac(uniq)
        if not alvo or len(alvo) != 12:
            return False
        with self._io_lock:
            trocas = self._trocas_de_transporte
            if trocas is None:
                trocas = self._trocas_de_transporte = {}
            trocas[alvo] = self._relogio() + PRAZO_DA_TROCA_DE_TRANSPORTE_S
        logger.info(
            "troca_de_transporte_iniciada",
            uniq=_endereco_mascarado(alvo),
            motivo=motivo,
            prazo_s=PRAZO_DA_TROCA_DE_TRANSPORTE_S,
        )
        return True

    def cancelar_troca_de_transporte(self, uniq: str, *, motivo: str) -> None:
        """Solta a marca — a troca não vai acontecer (o rádio não caiu)."""
        from hefesto_dualsense4unix.core.sysfs_leds import norm_mac

        alvo = norm_mac(uniq)
        with self._io_lock:
            trocas = self._trocas_de_transporte
            if not trocas or not alvo or trocas.pop(alvo, None) is None:
                return
        logger.info(
            "troca_de_transporte_cancelada", uniq=_endereco_mascarado(alvo), motivo=motivo
        )

    def em_troca_de_transporte(self, uniq: str | None) -> bool:
        """O controle `uniq` está trocando de transporte (ou acabou de trocar)?"""
        from hefesto_dualsense4unix.core.sysfs_leds import norm_mac

        alvo = norm_mac(uniq) if uniq else None
        with self._io_lock:
            return self._troca_valida_locked(alvo) or self._a_volta_ja_comecou_locked(alvo)

    def trocas_de_transporte_pendentes(self) -> frozenset[str]:
        """Os MACs que estão FORA da mesa por estarem trocando de transporte."""
        with self._io_lock:
            presentes = {
                self._key_to_uniq(key)
                for key, handle in self._handles.items()
                if bool(getattr(handle, "connected", False))
            }
            trocas = dict(self._trocas_de_transporte or {})
            return frozenset(
                uniq
                for uniq in trocas
                if uniq not in presentes and self._troca_valida_locked(uniq)
            )

    def transportes_dos_alvos(self) -> dict[str, str]:
        """`{key: 'usb' | 'bt'}` dos controles conectados AGORA."""
        with self._io_lock:
            items = list(self._handles.items())
        return {
            key: self._detect_transport(handle)
            for key, handle in items
            if bool(getattr(handle, "connected", False))
        }

    def _troca_valida_locked(self, uniq: str | None) -> bool:
        """A marca de `uniq` ainda vale? Vencida, sai (com uma linha). Sob `_io_lock`."""
        trocas = self._trocas_de_transporte
        if not uniq or not trocas or uniq not in trocas:
            return False
        if self._relogio() < trocas[uniq]:
            return True
        del trocas[uniq]
        logger.info("troca_de_transporte_venceu", uniq=_endereco_mascarado(uniq))
        return False

    def _a_troca_espera_locked(self, key: str) -> bool:
        """O posto de `key` espera por ela porque ela está trocando de transporte?"""
        return key not in self._handles and self._troca_valida_locked(self._key_to_uniq(key))

    def _o_no_mudou_locked(self, key: str, pedido: bytes) -> bool:
        """A key segue na mesa, mas por OUTRO nó — o handle aberto é de um nó morto."""
        atual = getattr(self._handles.get(key), "_pinned_path", None)
        return isinstance(atual, bytes) and isinstance(pedido, bytes) and atual != pedido

    def _religar_o_primario_trocado_locked(self) -> None:
        """O primário trocou de nó sem trocar de key: o transporte e os leitores seguem."""
        chave = self._primary_key
        if chave is None or chave not in self._handles:
            return
        self._transport = self._detect_transport(self._handles[chave])
        with contextlib.suppress(Exception):
            self._evdev.request_reopen(reason="troca_de_transporte")
        if self._motion_reader is not None:
            with contextlib.suppress(Exception):
                self._motion_reader.request_reopen("troca_de_transporte")
        logger.info("controller_primary_bound", transport=self._transport, motivo="troca_de_no")

    def _anotar_os_transportes_locked(
        self, novos: list[tuple[str, pydualsense]], trocados: Mapping[str, str]
    ) -> None:
        """Guarda por onde cada controle esteve, e fecha a troca de quem voltou."""
        if not novos:
            return
        sessao = self._transportes_da_sessao
        if sessao is None:
            sessao = self._transportes_da_sessao = {}
        agora = self._relogio()
        for key, handle in novos:
            try:
                transporte = self._detect_transport(handle)
            except Exception:
                continue
            sessao.setdefault(key, set()).add(transporte)
            uniq = self._key_to_uniq(key)
            if uniq is None:
                continue
            trocas = self._trocas_de_transporte
            if trocas is None:
                trocas = self._trocas_de_transporte = {}
            if self._troca_valida_locked(uniq):
                trocas[uniq] = min(trocas[uniq], agora + FOLGA_DEPOIS_DA_TROCA_S)
                logger.info(
                    "troca_de_transporte_concluida",
                    uniq=_endereco_mascarado(uniq),
                    transporte=transporte,
                )
            elif key in trocados and trocados[key] != transporte:
                trocas[uniq] = agora + FOLGA_DEPOIS_DA_TROCA_S
                logger.info(
                    "troca_de_transporte_concluida",
                    uniq=_endereco_mascarado(uniq),
                    transporte=transporte,
                    motivo="no_trocado_no_mesmo_tique",
                )

    def _quem_volta_pelo_radio_locked(self, key: str, handle: Any) -> str | None:
        """O MAC de `key` se o handle que sai é o CABO de quem já esteve no rádio."""
        uniq = self._key_to_uniq(key)
        if uniq is None:
            return None
        try:
            transporte = self._detect_transport(handle)
        except Exception:
            return None
        if transporte != "usb" or "bt" not in (self._transportes_da_sessao or {}).get(key, ()):
            return None
        return uniq

    def _a_volta_ja_comecou_locked(self, uniq: str | None) -> bool:
        """O cabo de `uniq` saiu e o `connect()` ainda não podou o handle dele."""
        if not uniq:
            return False
        for key, handle in self._handles.items():
            if self._key_to_uniq(key) != uniq:
                continue
            if bool(getattr(handle, "connected", False)):
                return False
            return self._quem_volta_pelo_radio_locked(key, handle) is not None
        return False

    def _segurar_a_volta_pelo_radio_locked(self, key: str, handle: Any) -> None:
        """O cabo saiu de um controle que veio do rádio: o lugar espera ele voltar."""
        uniq = self._quem_volta_pelo_radio_locked(key, handle)
        if uniq is None:
            return
        trocas = self._trocas_de_transporte
        if trocas is None:
            trocas = self._trocas_de_transporte = {}
        trocas[uniq] = self._relogio() + PRAZO_DA_TROCA_DE_TRANSPORTE_S
        logger.info(
            "troca_de_transporte_iniciada",
            uniq=_endereco_mascarado(uniq),
            motivo="o_cabo_saiu",
            prazo_s=PRAZO_DA_TROCA_DE_TRANSPORTE_S,
        )

    def clear_user_output_fields(
        self,
        uniqs: Iterable[str] | None,
        campos: Iterable[str],
    ) -> None:
        """Solta da camada da USUÁRIA só os `campos` dos controles `uniqs`."""
        with self._io_lock:
            alvos = (None if uniqs is None
                     else {a for u in uniqs if (a := self._key_to_uniq(u)) is not None})
            quais = set(campos)
            for uniq, donos in list(self._desired_owner_by_uniq.items()):
                if alvos is not None and uniq not in alvos:
                    continue
                override = self._desired_by_uniq.get(uniq)
                for campo, dono in list(donos.items()):
                    if dono != _LAYER_USER or campo not in quais:
                        continue
                    del donos[campo]
                    if override is not None:
                        setattr(override, campo, None)
            self._prune_overrides_locked()


    def _cartas_locked(self, chaves: list[str]) -> dict[str, int]:
        """A carta de cada key de `chaves` — vazio quando a mesa não tem carta."""
        uniqs = {k: self._key_to_uniq(k) for k in chaves}
        lampadas = {k: self._numero_do_slot(u) for k, u in uniqs.items()}
        if chaves and all(n is not None for n in lampadas.values()):
            return {k: n for k, n in lampadas.items() if n is not None}
        consulta = getattr(self._auto_output_provider, "posto_na_fila", None)
        if not callable(consulta):
            return {}
        postos: dict[str, int | None] = {}
        for chave, uniq in uniqs.items():
            posto: int | None = None
            if uniq is not None:
                with contextlib.suppress(Exception):
                    bruto = consulta(uniq)
                    if isinstance(bruto, int) and not isinstance(bruto, bool):
                        posto = bruto
            postos[chave] = posto
        conhecidos = [p for p in postos.values() if p is not None]
        if not conhecidos:
            return {}
        fim = max(conhecidos) + 1
        return {k: (p if p is not None else fim) for k, p in postos.items()}

    def _na_ordem_da_carta_locked(self, chaves: list[str]) -> list[str]:
        """`chaves` na ordem da carta; o empate e a falta de carta ficam na de entrada."""
        cartas = self._cartas_locked(chaves)
        if not cartas:
            return list(chaves)
        return sorted(chaves, key=cartas.__getitem__)

    def _a_carta_menor_locked(self, sentado: str) -> str:
        """O primário `sentado` fica — a não ser que a carta MENOR esteja na mesa."""
        chaves = list(self._handles)
        cartas = self._cartas_locked(chaves)
        if sentado not in cartas:
            return sentado
        melhor = min(chaves, key=cartas.__getitem__)
        if cartas[melhor] >= cartas[sentado]:
            return sentado
        logger.info(
            "primario_segue_a_carta",
            uniq=_endereco_mascarado(self._key_to_uniq(melhor)),
            antes=_endereco_mascarado(self._key_to_uniq(sentado)),
            carta=cartas[melhor],
            carta_de_antes=cartas[sentado],
        )
        return melhor

    def seguir_a_carta(self) -> bool:
        """O posto de P1 segue a carta 1 sem esperar hotplug. Devolve se ele andou."""
        with self._io_lock:
            antes = self._primary_key
            self._recompute_primary()
            return self._primary_key != antes


#: (`battery_pct=..., battery_state=...`) e o `**self._carga(...)` no
ESTADO_DE_CARGA: dict[int, str] = {
    0x0: "descarregando",
    0x1: "carregando",
    0x2: "cheio",
    0xA: "fora_de_faixa",
    0xB: "fora_de_faixa",
    0xF: "erro",
}


_RELOGIO_DOS_PRAZOS: int = getattr(time, "CLOCK_BOOTTIME", time.CLOCK_MONOTONIC)


def relogio_do_prazo() -> float:
    """Segundos no relógio dos dois prazos — o dono ÚNICO (O-ASSENTO-GUARDADO-NAO-ANDA-02).

    Quem mede o posto de primário (`PyDualSenseController._relogio`) e quem mede
    o lugar guardado (`identity.relogio_do_lugar_guardado`, que serve ao registro
    dos DualSense e ao dos externos) perguntam AQUI. Um relógio de cada lado
    deixaria os dois prazos vencerem em instantes diferentes depois de uma
    suspensão, que é a contradição que a sprint veio fechar.
    """
    return time.clock_gettime(_RELOGIO_DOS_PRAZOS)


PRAZO_DA_TROCA_DE_TRANSPORTE_S: float = PRIMARIO_RESERVA_SEC

FOLGA_DEPOIS_DA_TROCA_S: float = 10.0


def _endereco_mascarado(uniq: object) -> str | None:
    """O MAC 12-hex com os octetos 4 e 5 zerados — a máscara da casa, para o diário."""
    if not isinstance(uniq, str) or len(uniq) != 12:
        return None
    return uniq[:6] + "0000" + uniq[10:]


def _barramento_do_hidraw(path: bytes) -> str | None:
    """`usb` ou `bt` pelo `HID_ID` do nó (``0003:`` é o cabo, ``0005:`` o rádio)."""
    no = os.path.basename(path.decode("utf-8", "replace"))
    barramento = _hidraw_uevent(no).get("HID_ID", "")[:4]
    return {"0003": "usb", "0005": "bt"}.get(barramento)


def _o_cabo_vence(novo: bytes, guardado: bytes) -> bool:
    """O nó `novo` do mesmo controle toma o lugar do `guardado`? Só se for o cabo."""
    return _barramento_do_hidraw(novo) == "usb" and _barramento_do_hidraw(guardado) != "usb"


RAIZ_CLASS_HIDRAW = "/sys/class/hidraw"


def numero_do_desenho(bits: object) -> int | None:
    """O número que o desenho das cinco lâmpadas de jogador diz. O tradutor ÚNICO."""
    from hefesto_dualsense4unix.core.led_control import player_led_pattern

    try:
        desenho = tuple(bool(b) for b in bits)  # type: ignore[attr-defined]
    except TypeError:
        return None
    if len(desenho) != 5:
        return None
    if not any(desenho):
        return 0
    for numero in range(1, 9):
        if player_led_pattern(numero) == desenho:
            return numero
    return None


__all__ = [
    "ESTADO_DE_CARGA",
    "FOLGA_DEPOIS_DA_TROCA_S",
    "PRAZO_DA_TROCA_DE_TRANSPORTE_S",
    "PyDualSenseController",
    "numero_do_desenho",
    "relogio_do_prazo",
]
