"""Backend real sobre `pydualsense`: adapta o HID do DualSense à `IController` (ADR-001).

Thin adapter, sem lógica de negócio. FEAT-DSX-MULTI-CONTROLLER-01: N controles abertos por `path`
hidraw (`_PinnedPyDualSense`); a saída vai a todos (fan-out) com o perfil guardado POR CONTROLE
(PERFIL-01/4P-01), e a entrada/emulação fica só no primário.
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
from hefesto_dualsense4unix.core.formas_do_endereco import mascarar
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
from hefesto_dualsense4unix.core.trigger_effects import (
    TAMANHO_DO_BLOCO_DO_GATILHO,
    bloco_do_gatilho,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable, Iterator, Mapping, Sequence

from hefesto_dualsense4unix.utils.logging_config import get_logger

logger = get_logger(__name__)

#: PID do DualSense Edge.
DUALSENSE_EDGE_PID = 0x0DF2

KERNEL_DEFAULT_BLUE: tuple[int, int, int] = (0, 0, 128)

#: Piscadas do aviso: poucas e lentas o bastante para contar e ler a cor.
AVISO_PISCADAS = 3
AVISO_ACESO_S = 0.15
AVISO_APAGADO_S = 0.12
AVISO_APAGADO: tuple[int, int, int] = (0, 0, 0)

GAME_TRIGGER_BLOCK_LEN = TAMANHO_DO_BLOCO_DO_GATILHO

#: não passa por este teto: já é rate-limitada pela histerese de 30s do sinal.
DEFEND_DISPLAY_MIN_INTERVAL_S = 30.0

_CALIBRATION_FEATURE_ID = 0x05
_CALIBRATION_FEATURE_SIZE = 41

#: A feature 0x20 (informações de firmware): 64 bytes, e o `update_version` é o
#: u16 little-endian do byte 44 (`hid-playstation.c`, `dualsense_get_firmware_info`).
_FIRMWARE_FEATURE_ID = 0x20
_FIRMWARE_FEATURE_SIZE = 64
_FIRMWARE_UPDATE_VERSION_OFFSET = 44

#: Firmware a partir daqui entende a vibração v2 (limiar do SDL e do SpecialK,
#: `docs/protocol/dualsense-energia-e-vibracao.md` §4.1); o Edge é sempre v2. Não é o `0x0215`
#: do driver, que tem cara de conversão decimal/hexadecimal perdida.
LIMITE_DA_VIBRACAO_V2 = 0x0224


def _acordar_a_volta_de(handle: Any) -> None:
    """Acorda a volta do handle depois de mudar um objeto por dentro (gatilho, luz); dublê sem a API
    fica como estava.

    A-VIBRACAO-DO-JOGO-NAO-ESPERA-O-SONO-DA-VOLTA-01.
    """
    acordar = getattr(handle, "acordar_a_volta", None)
    if callable(acordar):
        acordar()


def versao_do_firmware(feature: bytes | None) -> int | None:
    """O `update_version` (u16 LE no byte 44) da feature 0x20, ou None se não cabe."""
    if feature is None or len(feature) < _FIRMWARE_UPDATE_VERSION_OFFSET + 2:
        return None
    return int.from_bytes(
        feature[_FIRMWARE_UPDATE_VERSION_OFFSET : _FIRMWARE_UPDATE_VERSION_OFFSET + 2],
        "little",
    )


def fala_a_vibracao_v2(versao: int | None, *, edge: bool) -> bool:
    """O controle vibra no modo v2? O Edge sempre; o DualSense comum, pelo firmware lido (sem
    leitura, v1)."""
    if edge:
        return True
    return versao is not None and versao >= LIMITE_DA_VIBRACAO_V2


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

    Critério: a identidade do vpad no uevent do pai HID (HID_PHYS `hefesto-vpad` ou HID_UNIQ 02:fe),
    nunca a topologia (SPRINT-UHID-VPAD-01, BLUEZ-UHID-01). Uevent ilegível sob o subtree virtual →
    True: o risco maior é adotar o próprio vpad.
    """
    node = os.path.basename(path.decode("utf-8", "replace"))
    if not node.startswith("hidraw"):
        return False
    try:
        destino = os.path.realpath(os.path.join(RAIZ_CLASS_HIDRAW, node, "device"))
    except OSError:  # pragma: no cover - sysfs some sob replug
        return False
    from hefesto_dualsense4unix.integrations import pad_usb

    sob_o_vhci = pad_usb.sob_o_vhci(destino)
    if "/devices/virtual/" not in destino and not sob_o_vhci:
        return False
    uevent = _hidraw_uevent(node)
    if not uevent:
        # Sob o uhid, a dúvida é virtual (o risco é a auto-adoção); sob o
        # `vhci_hcd`, um uevent ilegível não prova que é o nosso pad em USB.
        return not sob_o_vhci
    return pad_usb.e_pad_nosso(
        destino,
        phys=uevent.get("HID_PHYS", ""),
        uniq=uevent.get("HID_UNIQ", ""),
        bus=pad_usb.bus_do_hid_id(uevent.get("HID_ID", "")),
    )

#: Teto do `init()` do pydualsense, que pode travar em `D (disk sleep)` num USB degenerado;
#: passado o prazo o backend fica offline e o reconnect_loop tenta de novo (a thread é
#: abandonada). 5 s cobre o caso patológico sem pesar no boot: o `init()` sadio volta em <300 ms.
INIT_TIMEOUT_SEC: float = float(os.environ.get("HEFESTO_DUALSENSE4UNIX_INIT_TIMEOUT_SEC", "5"))

#: saturando o controlador USB compartilhado — e o adaptador Bluetooth vive no
#: (`DualSense input CRC's check failed`) e matando o output do controle BT.
REPORT_THREAD_THROTTLE_SEC: float = float(
    os.environ.get("HEFESTO_DUALSENSE4UNIX_REPORT_THROTTLE_SEC", "0.008")
)

REPORT_THREAD_THROTTLE_MAX_SEC: float = 0.032

#: Espaçamento mínimo entre duas escritas do MESMO controle no cabo: o serviço do endpoint OUT
#: (`bInterval 6` em High Speed = 4 ms, `docs/protocol/driver-hid-playstation.md`, «Cabo: 250
#: Hz»); mais rápido só enfileira URB no controlador USB. É por controle e não soma por jogador.
#: A-VIBRACAO-DO-JOGO-NAO-ESPERA-O-SONO-DA-VOLTA-01.
PISO_DE_ESCRITA_DO_CABO_SEC: float = 0.004

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
    """Porcentagem da tela (0-100) -> `common[6]`, o ganho de captura do aparelho (MIC-VOLUME-02).

    Conta LINEAR sobre `rep.TETO_MIC_VOLUME` (a curva do microfone ninguém levantou); 0 % é zero e
    acima de 0 % sai ao menos 1. A régua mora só aqui.
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
    """Acende/apaga o LED do mudo tomando a posse do byte (AUDIO-OWNER-01); sem a posse o bit de
    autorização não liga."""
    tomar = getattr(handle, "set_microphone_led", None)
    if callable(tomar):
        tomar(bool(aceso))
        return
    handle.audio.setMicrophoneLED(bool(aceso))


def _byte_da_rota(handle: Any, rota: int | None) -> int | None:
    """O `common[7]` com a rota nova, preservando o caminho do microfone (SOM-ROTA-01).

    `None` devolve `None` (não tomar a posse do byte); com rota, a base é o valor vigente se há
    dono, senão zero.
    """
    if rota is None:
        return None
    # SOM-CANAL-01: base ZERO apagava o `FORCE_INTERNAL_MIC` e o microfone parava de captar; o
    # byte não se lê de volta, então a base é a mais conservadora: microfone interno ligado.
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
    """Quantos bytes o fio disse ter escrito; `None` = ele não disse (ESCRITA-QUE-NAO-MEDE-01).

    Só `int` é prova (não `bool`, não dublê): ausência de dado não acusa escrita curta.
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
    """O bloco cru de gatilho do jogo não faz nada: modo «sem efeito» (`0x00`/`0x05`) ou os dez
    parâmetros em zero."""
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
    """Cópia de `desired` sem os campos defendidos; `None` se não sobrou campo (o merge é pulado,
    pois roda sob o `_io_lock`)."""
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
    """Resolve o escopo de UMA escrita de output, sob o `_io_lock`: `(escopo_do_registro,
    handles_a_escrever, alvo_ausente)`.

    Sem alvo ou `broadcast=True`: escopo `None` e todos os handles. Alvo presente: a key dele e um
    handle. Alvo AUSENTE: a key dele (override guardado) e nenhum handle; ausência de destinatário
    não é «todo mundo» (P4; FEAT-DSX-CONTROLLER-SELECTOR-01). Função de módulo, não método: os
    dublês de LED tomam emprestados os métodos reais.
    """
    if broadcast or alvo is None:
        return None, list(handles.items()), None
    handle = handles.get(alvo)
    if handle is None:
        return alvo, [], alvo
    return alvo, [(alvo, handle)], None


def _casar_key(handles: dict[str, Any], uniq: str) -> str | None:
    """Key do handle por `uniq`: o MAC 12-hex (do IPC) OU a própria key (da bancada). P4."""
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
    """`hid_set_nonblocking(dev, 1)`: o `read` do handle deixa de esperar o próximo report.

    Chamado uma vez na thread do handle, depois do `init()`, que precisa da espera para descobrir o
    transporte. O-BOTAO-DO-MIC-CHEGA-NA-HORA-01.
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
    """Fecha muitos handles pagando UM teto: baixa o sinal em todos antes do primeiro `join`, e os
    `join` dividem um prazo só.

    Dublê que só sabe `close()` fecha por ele. A-REPORT-THREAD-SAI-ANTES-DO-HANDLE-FECHAR-01.
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


#: Os campos do handle que entram no report: mudar um acorda a volta
#: (:meth:`_PinnedPyDualSense.__setattr__`).
_CAMPOS_QUE_MEXEM_NA_SAIDA: frozenset[str] = frozenset(
    {
        "leftMotor",
        "rightMotor",
        "_rumble_active",
        "_rumble_stop_pending",
        "_raw_trigger_right",
        "_raw_trigger_left",
        "_haptica_de_audio",
        "_vibracao_v2", "_escala_da_vibracao", "_escala_do_gatilho",
        "_mic_mute_desejado",
        "_mic_led_desejado",
        "_volumes_audio",
        "_preamp_audio",
        "_suppress_leds",
        "_brilho_das_luzes",
        "_output_muted",
        "ds_thread",
    }
)


class _PinnedPyDualSense(pydualsense):  # type: ignore[misc]
    """`pydualsense` pinada a um hidraw `path` (via `hidapi.Device`), para manter N instâncias, uma
    por controle."""

    # Defaults de CLASSE: a suíte constrói dublês sem passar pelo `__init__`.

    _write_lock: threading.Lock = threading.Lock()

    _leitura_vazia_desde: float | None = None

    #: Um aviso por episódio, não um por ciclo.
    _leitura_vazia_avisada: bool = False

    #: A saída do rádio ficou DEVIDA com a entrada muda: ao voltar, uma escrita entrega só o
    #: estado de agora.
    _saida_adiada_pelo_silencio: bool = False

    #: Sobe a cada quadro escrito de fora da volta que a volta não pode desfazer (o Off do
    #: `soltar_os_gatilhos`). O report que a volta montou antes dele leva a geração velha, e o
    #: `writeReport` o descarta: sem isso, o Rígido montado um instante antes saía DEPOIS do Off, e
    #: com o mudo do Nativo ou o `disconnect` logo em seguida ficava no firmware.
    _geracao_da_saida: int = 0

    #: BATERIA-QUE-PULA-01: quantos reports este handle ACEITOU.
    _reports_aceitos: int = 0
    _reports_recusados: int = 0
    _recusa_avisada: bool = False

    _brilho_das_luzes: int = degrau_do_brilho_das_luzes(None)

    #: A háptica por áudio toca neste controle (ponte `0x32` no rádio, laço do cabo): o rumble
    #: sai sem `HAPTICS_SELECT`. A-VIBRACAO-NAO-DESLIGA-A-HAPTICA-01; ver
    #: :meth:`set_haptica_de_audio`.
    _haptica_de_audio: bool = False

    #: O firmware entende a vibração v2 (motor em escala cheia, `COMPATIBLE_VIBRATION2`); vem da
    #: feature 0x20 lida na conexão, sem leitura fica v1.
    #: O-CONTROLE-VIBRA-NO-MODO-DO-FIRMWARE-DELE-01.
    _vibracao_v2: bool = False

    #: A-VIBRACAO-DO-JOGO-NAO-ESPERA-O-SONO-DA-VOLTA-01: `_acordar` acorda a volta na hora em vez
    #: de dormir o `_throttle_sec`; `_piso_de_escrita_sec` é o espaçamento mínimo entre duas
    #: escritas, por transporte.
    _acordar: threading.Event | None = None
    _piso_de_escrita_sec: float = 0.0

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
        # LIGHTBAR-BT-ADOPT-01: nasce TRUE, nunca False: o report_thread escreve assim que o
        # handle abre, antes do `_refresh_sysfs_leds`, e o 1º report BT da pydualsense 0.7.5
        # sairia malformado.
        self._suppress_leds = True
        self._throttle_sec = REPORT_THREAD_THROTTLE_SEC
        self._piso_de_escrita_sec = REPORT_THREAD_THROTTLE_SEC
        self._acordar = threading.Event()
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
        # AUDIO-OWNER-01: os dois campos de áudio que o upstream autorizava em todo report sem
        # valor; enquanto None, os bits de validação saem zerados e o firmware mantém o que tinha.
        # `_mic_mute_desejado` (common[9], flag1 0x02): o dono no Linux é o kernel
        # (`hid-playstation`); ver BT-MIC-GATING-01 em `integrations/dualsense_bt_audio.py`.
        self._mic_mute_desejado: bool | None = None
        self._mic_led_desejado: int | bool | None = None
        self._volumes_audio: list[int | None] = [None, None, None, None]
        #: escrever é mandar zero a 60 Hz com cara de keepalive.
        self._preamp_audio: int | None = None
        self._audio_status: int | None = None
        self.zerar_estado_da_borda_do_mic()

    def _garantir_estado_da_borda_do_mic(self) -> None:
        """Zera o estado do botão do mic UMA vez, se ninguém o zerou.

        Os dublês da suíte constroem o handle por `__new__`: o dono único se garante sozinho (o
        `__init__` o chama, custo zero no caminho vivo) em vez de cada dublê redigitar o campo.
        Sentinela: `_mic_botao`.
        """
        if "_mic_botao" not in self.__dict__:
            self.zerar_estado_da_borda_do_mic()

    def zerar_estado_da_borda_do_mic(self) -> None:
        """TODO o estado do botão do mic, num lugar só — e o motivo é medido."""
        self._mic_mudo: bool | None = None
        self._mic_botao: bool | None = None
        self._mic_mudo_seq: int = 0
        self._mic_mudo_pedido: bool | None = None
        self._mic_mudo_em_voo: bool = False
        self._mic_mudo_em: float | None = None
        self._mic_posse_solta_pela_mao: bool = False

    def __setattr__(self, nome: str, valor: Any) -> None:
        """Mudar um campo que entra no report acorda a volta: a saída não espera o sono.

        Dono único do «a réplica mudou» (motor, blocos crus do gatilho, bits de posse do áudio e do
        mic, modo da vibração, brilho, sinal de fechar). O que muda por dentro de um objeto acorda
        por :meth:`acordar_a_volta`.
        """
        super().__setattr__(nome, valor)
        if nome in _CAMPOS_QUE_MEXEM_NA_SAIDA:
            self.acordar_a_volta()

    def acordar_a_volta(self) -> None:
        """Arma o evento da volta: a próxima passada começa agora, não no fim do sono."""
        acordar = self._acordar
        if acordar is not None:
            acordar.set()

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

        Dorme `_throttle_sec` por volta (BUG-MULTI-CONTROLLER-BT-CRC-CONTENTION-01). A volta lê com
        prazo zero até a fila esvaziar e entrega à pydualsense só o report mais novo
        (O-BOTAO-DO-MIC-CHEGA-NA-HORA-01); leitura `None` segue direto para a saída, não é erro
        (LACO-DE-ESCRITA-02); depois do sinal nada vai ao aparelho e quem sai do C por último fecha
        o handle (A-REPORT-THREAD-SAI-ANTES-DO-HANDLE-FECHAR-01).
        """
        try:
            self._girar_a_volta()
        finally:
            self._sair_e_fechar_se_for_o_ultimo()

    def _girar_a_volta(self) -> None:
        """O laço do `sendReport`."""
        sem_espera = False
        while self.ds_thread:
            try:
                acordar = self._acordar
                if acordar is not None:
                    # Limpa ANTES de montar o report: quem arma durante a
                    # passada deixa o evento de pé e a próxima volta não dorme.
                    acordar.clear()
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
                    geracao = self._geracao_da_saida
                    out = self.prepareReport()
                    now = time.monotonic()
                    mudou = out != self._last_out_report
                    if mudou:
                        self._last_change_at = now
                    # DualSense na bancada (dois no cabo, dois no rádio) e o
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
                    # O piso de escrita do transporte vale pelo sono do fim da
                    # volta (`_dormir_a_volta`): quem acorda a espera dorme só o
                    # que falta do piso, e nunca começa a próxima passada antes.
                    if deve_escrever:
                        self.writeReport(out, geracao=geracao)
                        self._last_out_report = out
                        self._last_write_at = now
                self._dormir_a_volta(acordar, lidos=bool(lidos))
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

    def _dormir_a_volta(self, acordar: threading.Event | None, *, lidos: bool) -> None:
        """O fim da passada: espera o prazo da volta OU a mudança da saída.

        O prazo segue como teto (leitura e keepalive no ritmo de sempre); mudança de saída o
        interrompe e só o que sobra do piso de escrita é dormido. Sem o evento (dublê), dorme o sono
        inteiro. A-VIBRACAO-DO-JOGO-NAO-ESPERA-O-SONO-DA-VOLTA-01.
        """
        throttle = self._throttle_sec
        if acordar is None:
            if throttle > 0:
                time.sleep(throttle)
            elif not lidos:
                time.sleep(ESPERA_DA_VOLTA_VAZIA_SEM_THROTTLE_SEC)
            return
        if throttle <= 0:
            if not lidos and not acordar.is_set():
                acordar.wait(ESPERA_DA_VOLTA_VAZIA_SEM_THROTTLE_SEC)
            return
        if not acordar.is_set() and not acordar.wait(throttle):
            return
        falta = self._piso_de_escrita_sec - (time.monotonic() - self._last_write_at)
        if falta > 0:
            time.sleep(min(falta, throttle))

    def _a_saida_espera_a_entrada(self, agora: float) -> bool:
        """No rádio, não escrever enquanto a entrada está muda há tempo demais."""
        if getattr(self, "conType", None) != ConnectionType.BT:
            return False
        desde = self._leitura_vazia_desde
        if desde is None:
            return False
        return (agora - desde) >= LEITURA_VAZIA_AVISO_SEC

    def _registrar_leitura_vazia(self) -> None:
        """Contabiliza um `read` sem dado (LACO-DE-ESCRITA-02): um aviso por EPISÓDIO de silêncio,
        nunca um por ciclo."""
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
        """Lê TODO report pendente no fd deste handle, do mais velho ao mais novo, até
        `LEITURAS_POR_VOLTA`.

        A fila do hidraw é por fd e o kernel descarta o report novo com ela cheia: um por volta
        deixava cada um com 63 voltas de idade (O-BOTAO-DO-MIC-CHEGA-NA-HORA-01). A leitura viva
        conta antes da guarda de «entrada muda».
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
        """Entrega os reports crus de UMA volta aos dois consumidores, e SÓ os de ESTADO.

        Cada report de estado conta o botão do mic e o `status[1]` em ordem
        (`_captura_status_audio`, a própria guarda); a pydualsense recebe só o mais novo, uma vez
        por volta. O `readInput` dela não confere id, tamanho, CRC nem o bit de áudio: Opus no
        `0x31` virava bateria e `micBtn` falsos (BATERIA-QUE-PULA-01); `readInput` tem UM chamador
        no `src/`.
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
        """DESCARTA o report que não é estado, e CONTA.

        Nunca "consertar": o payload de áudio é inteiro Opus. `_reports_aceitos` subindo prova que a
        guarda não congelou o controle; avisa uma vez por HANDLE, não por report.
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

    # QUEDA-QUE-PENDURA-01: o `close()` do upstream faz `join()` SEM TETO sobre uma thread cujo
    # `read` bloqueava; com o controle sumindo do rádio sem despedida, o join pendurava para
    # sempre. Daqui o `close()` tem teto e o laço lê sem espera.
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
        """Guarda o byte de estado de áudio do report CRU e diz se ele era ESTADO.

        `True` = era estado de input e foi lido; `False` = o extrator recusou (a guarda do
        `_consumir_lote`, um CRC por report). `None` do extrator NÃO mexe no cache (`0x00` é
        "íntegro, sem fone nem mic mudo"). Lê o cru por `core/physical_report_reader.py` e não
        `states[54]`: o `readInput` da pydualsense não confere nada, e Opus elegeria microfone
        sozinho (MIC-DA-MESA-ELEICAO-01, PS-PRESO-01).
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
        """Conta os APERTOS do botão do microfone deste controle (MIC-DA-MESA-ELEICAO-01).

        CONTADOR, não estado, e a identidade vem do fd. O gesto é o BOTÃO (`buttons[2]` bit 2), não
        o bit de mudo, que muda com qualquer escritor (O-BOTAO-DO-MIC-SO-OBEDECE-A-MAO-01). O `mudo`
        do aperto é o que ele PEDE: com a posse nossa e a escrita viva a referência é a posse
        (O-ECO-DO-ATO-SEM-OBJETO-01), senão o bit do report. A mão devolve a posse do mudo, solta
        aqui na thread do report; o mapa por-uniq acompanha em `bordas_do_mic`.
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
        posse = getattr(self, "_mic_mute_desejado", None)
        # O aperto se lê contra o que o firmware VAI segurar: com a posse nossa e a escrita viva o
        # bit do report ainda é o velho. Onde o jogo é dono do hidraw a posse não vai ao fio: vale
        # o bit.
        escreve = isinstance(posse, bool) and not getattr(self, "_output_muted", False)
        referencia = posse if escreve else mudo
        self._mic_mudo_pedido = not referencia
        self._mic_mudo_em_voo = bool(escreve and posse != mudo)
        self._mic_mudo_em = _relogio_da_borda()
        if posse is not None:
            self._mic_mute_desejado = None
            self._mic_posse_solta_pela_mao = True

    def set_microphone_mute(self, muted: bool | None) -> None:
        """Assume (ou devolve) a POSSE do mudo de microfone do firmware.

        `True`/`False`: mandamos `common[9]` com `MIC_MUTE` e `POWER_SAVE_CONTROL_ENABLE`. `None`
        (fábrica) devolve a posse ao kernel. O firmware não devolve o registrador: "não somos donos"
        é `None`, nunca `False` (que é a ordem "desmuta").
        """
        self._mic_mute_desejado = None if muted is None else bool(muted)

    def set_microphone_led(self, aceso: bool | int | None) -> None:
        """Assume (ou devolve) a POSSE do LED do botão de mudo (`common[8]`); irmão do
        `set_microphone_mute`.

        `True`/`False` autorizam `MIC_MUTE_LED_CONTROL_ENABLE` e escrevem o byte; `None` devolve o
        campo ao kernel. Espelha em `self.audio.microphone_led` o que foi pedido.
        """
        # `bool` é subclasse de `int`: o ramo guarda `True`/`False` inalterados e acrescenta o
        # NÍVEL (ver `common[8]` em `_build_common`).
        self._mic_led_desejado = (
            None if aceso is None else aceso if isinstance(aceso, int) else bool(aceso)
        )
        if aceso is not None:
            with contextlib.suppress(Exception):
                self.audio.setMicrophoneLED(bool(aceso))

    def set_haptica_de_audio(self, ativa: bool) -> None:
        """A háptica por áudio passou a tocar (ou parou) NESTE controle
        (A-VIBRACAO-NAO-DESLIGA-A-HAPTICA-01).

        Com háptica tocando, o rumble sai com `COMPATIBLE_VIBRATION` e sem `HAPTICS_SELECT`, que
        cala a háptica e fazia os dois alternarem. Quem diz é o `AltoFalanteSubsystem`, por
        `set_haptica_de_audio_for`.
        """
        self._haptica_de_audio = bool(ativa)

    def set_vibracao_v2(self, ativa: bool) -> None:
        """O firmware deste controle fala a vibração v2 (ou só a v1); `_build_common` pede o modo
        que ele entende.

        O-CONTROLE-VIBRA-NO-MODO-DO-FIRMWARE-DELE-01.
        """
        self._vibracao_v2 = bool(ativa)

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
        """Devolve a posse dos bytes de áudio (volta ao neutro). Idempotente; devolve o CONTROLE,
        nunca o número.

        `microfone=False` poupa o `common[6]` (MIC-VOLUME-02): o "Devolver" do alto-falante não leva
        o ganho do mic. O padrão `True` devolve tudo; o pré-amplificador `common[37]` entra junto
        (SOM-ROTA-01).
        """
        guardado = self._volumes_audio[2] if not microfone else None
        self._volumes_audio = [None, None, guardado, None]
        self._preamp_audio = None

    def soltar_volume_do_microfone(self) -> None:
        """Devolve ao firmware SÓ o `common[6]`. MIC-VOLUME-02."""
        self._volumes_audio[2] = None

    def escrever_so_o_som(self, *, radio: bool) -> bool:
        """Escreve o report MÍNIMO do som: os bytes de áudio com dono, o pré-amp e mais nada.

        É o caminho do Modo Nativo, em que o laço não escreve (FEAT-NATIVE-OUTPUT-MUTE-01) e o
        deslizante ficava só na memória. Vibração, gatilhos e luzes saem sem autorização, e o
        firmware conserva o que o jogo escreveu neles; envelope `0x02` no cabo, `0x31` no rádio
        (`radio`, do `_detect_transport` do backend).
        """
        common = bytearray(rep.COMMON_LEN)
        flag0 = 0
        for bit, offset, valor in zip(
            _AUDIO_FLAG0_BITS, _AUDIO_COMMON_OFFSETS, self._volumes_audio, strict=False
        ):
            if valor is not None:
                flag0 |= bit
                common[offset] = int(valor) & 0xFF
        if self._preamp_audio is not None:
            common[1] = rep.VALID_FLAG1_AUDIO_CONTROL2_ENABLE
            common[rep.COMMON_AUDIO_CONTROL2] = int(self._preamp_audio) & rep.SP_PREAMP_GAIN_MASK
        common[0] = flag0
        if not flag0 and not common[1]:
            return False
        report = rep.build_bt_report(common, seq=0) if radio else rep.build_usb_report(common)
        return _escrita_completa(self.writeReport(list(report)), len(report))

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
        """Payload "common" (47 bytes) a partir do estado da pydualsense, com as políticas nossas
        aplicadas na origem.

        - Keepalive neutro (GUERRA-01 item 2): sem rumble nosso ativo, os bits de vibração saem
          desligados; o rumble de terceiros sobrevive pelo keepalive limitado do `sendReport`
          (RUMBLE-SEM-DONO-01).
        - Supressão de LED (FEAT-DSX-LIGHTBAR-SYSFS-01): `_suppress_leds` limpa lightbar e player do
          flag1; no flag2 saem zerados SETUP/BRILHO (0x02|0x01), senão a exibição trava no firmware
          (LIGHTBAR-BT-KEEPALIVE-01).
        - AUDIO-OWNER-01: volumes, mudo e LED do mudo só ganham autorização quando alguém do projeto
          escreveu o valor; sem dono, os bits saem zerados e o firmware conserva o que tinha.
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
        # AUDIO-OWNER-01: os bits de áudio do flag0 caem TODOS e só voltam para os bytes de que
        # alguém assumiu a posse.
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
            flag1 &= ~(0 if _a_reducao_pede_o_bit(self) else rep.VALID_FLAG1_MOTOR_POWER)
            flag2 &= ~rep.VALID_FLAG2_COMPATIBLE_VIBRATION2
        else:
            # O-CONTROLE-VIBRA-NO-MODO-DO-FIRMWARE-DELE-01: na v2 o bit é o
            # `COMPATIBLE_VIBRATION2` do flag2 e o do flag0 cai (como o `hid-playstation`); na v1
            # é o de sempre. O byte do motor sai cheio nas duas.
            if self._vibracao_v2:
                flag0 &= ~rep.VALID_FLAG0_COMPATIBLE_VIBRATION
                flag2 |= rep.VALID_FLAG2_COMPATIBLE_VIBRATION2
            if self._haptica_de_audio:
                # A-VIBRACAO-NAO-DESLIGA-A-HAPTICA-01: `HAPTICS_SELECT` cala a háptica por áudio;
                # com ela tocando, o rumble vai sem ele.
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
        common[2] = _motor_com_a_reducao(self, self.rightMotor)
        common[3] = _motor_com_a_reducao(self, self.leftMotor)
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
        common[1] = _carimbar_a_reducao(self, common, flag1)
        if mic_led is not None:
            common[8] = int(mic_led) & 0xFF
        if mic_mute is not None:
            self.audio.microphone_mute = mic_mute
            common[9] = rep.POWER_SAVE_MIC_MUTE if mic_mute else 0x00
        raw_r = getattr(self, "_raw_trigger_right", None)
        if raw_r is not None and len(raw_r) == GAME_TRIGGER_BLOCK_LEN:
            common[10 : 10 + GAME_TRIGGER_BLOCK_LEN] = _forca_do_gatilho(self, raw_r)
        else:
            common[10 : 10 + GAME_TRIGGER_BLOCK_LEN] = _forca_do_gatilho(self, bloco_do_gatilho(
                int(self.triggerR.mode.value), self.triggerR.forces
            ))
        raw_l = getattr(self, "_raw_trigger_left", None)
        if raw_l is not None and len(raw_l) == GAME_TRIGGER_BLOCK_LEN:
            common[21 : 21 + GAME_TRIGGER_BLOCK_LEN] = _forca_do_gatilho(self, raw_l)
        else:
            common[21 : 21 + GAME_TRIGGER_BLOCK_LEN] = _forca_do_gatilho(self, bloco_do_gatilho(
                int(self.triggerL.mode.value), self.triggerL.forces
            ))
        common[rep.COMMON_VALID_FLAG2] = flag2
        if not suppress_leds:
            common[41] = int(self.light.pulseOptions.value) & 0xFF
            # ESTE BYTE É O BRILHO DOS LEDS DE JOGADOR, não o da barra.
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

    def writeReport(  # noqa: N802 - upstream
        self, outReport: list[int], geracao: int | None = None  # noqa: N803 - upstream
    ) -> int | None:
        """Write com carimbo de sequência BT (BTREPORT-02), SERIALIZADO; devolve quantos bytes
        saíram (`None` = o fio não disse).

        Reports 0x31 ganham o contador por handle (wrap 0-15) e CRC NUMA CÓPIA; o buffer de
        `sendReport` fica com seq 0 (o dedup depende disso). O `_write_lock` (por handle, sem chamar
        o backend, sem ciclo com o `_io_lock`) entrega um quadro inteiro por vez, na ordem do
        carimbo (LACO-DE-ESCRITA-02); se o firmware aceita o número repetido, quem mede é o ensaio
        `a_sequencia_do_radio.py`. A entrega ao C é contada (`_no_c`); o `close()` nunca toma o
        `_write_lock` (QUEDA-QUE-PENDURA-01, A-REPORT-THREAD-SAI-ANTES-DO-HANDLE-FECHAR-01).
        """
        with self._write_lock, self._no_c():
            # A volta passa a `_geracao_da_saida` lida antes de montar o report: velha, o quadro
            # não sai, e a volta seguinte monta o estado de agora.
            if geracao is not None and geracao != self._geracao_da_saida:
                return 0
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
        # Procedência (camada) de cada campo escrito, para a ativação de perfil soltar só a camada
        # dela.
        self._desired_owner_by_uniq: dict[str, dict[str, str]] = {}
        # A PROCEDÊNCIA DA COR de cada override (`{uniq: número | constante}`): para qual número a
        # cor foi escolhida. Par do `_desired_owner_by_uniq` (QUE camada escreveu); quando o
        # número do aparelho muda, a cor gravada vira fóssil e sai sozinha
        # (`led_control.cores_sem_colisao`).
        self._procedencia_da_cor: dict[str, object] = {}
        self._brilho_da_cor: dict[str, tuple[tuple[int, int, int], float]] = {}
        self._desired_coop_by_uniq: dict[str, _DesiredOutput] = {}
        # Mapa próprio, por-uniq, ao lado do merge: o handle é RECRIADO a co-op. Chaveado pelo MAC
        # 12-hex de `_key_to_uniq` (a guarda de 12 dígitos impede o pseudo-MAC de path levar a
        # posse ao controle errado).
        self._mic_mute_by_uniq: dict[str, bool] = {}
        # A-VIBRACAO-NAO-DESLIGA-A-HAPTICA-01: quem tem a háptica por áudio tocando, por MAC; mora
        # aqui porque a troca de nó e a reconexão RECRIAM o handle e o dono das pontes só diz a
        # borda.
        self._haptica_de_audio_por_uniq: set[str] = set()
        # O-CONTROLE-VIBRA-NO-MODO-DO-FIRMWARE-DELE-01: o `update_version` que cada controle disse
        # na conexão (feature 0x20), por MAC. `None` = nunca lido (fica na v1). O firmware é do
        # controle, não do nó: a leitura que falha num handle novo herda a versão já lida
        # (`_conhecer_o_firmware`).
        self._firmware_por_uniq: dict[str, int | None] = {}
        # R-20 item 2: escala de brilho POR CONTROLE, aplicada à BASE do merge (global e
        # automática), nunca ao override, que já traz o brilho dele (`_scaled_led`).
        self._led_scale_by_uniq: dict[str, float] = {}
        # POR-UNIDADE-01: escala de VIBRAÇÃO por-uniq, irmã do `_led_scale_by_uniq`; guarda o
        # FATOR por peça, pois o daemon só escala a política GLOBAL
        # (`DaemonConfig.rumble_policy`).
        self._rumble_scale_by_uniq: dict[str, float] = {}
        self._auto_output_provider: Callable[[str], _DesiredOutput | None] | None = None
        self._mesa_apresentada: frozenset[str] = frozenset()
        self._feature_opener: Callable[[str], int] | None = None
        self._exposicao_do_no = None
        self._game_output_by_uniq: dict[str, _DesiredOutput] = {}
        self._game_triggers_by_uniq: dict[str, dict[str, bytes]] = {}
        # PERFIL ATÉ O JOGO PROVAR: o «sem efeito» do gatilho e o preto da lightbar são ausência
        # até o jogo mandar um efeito (ou cor) de verdade naquele controle e partida; depois o
        # jogo manda, e `end_game_session_for` zera o «já provou».
        self._jogo_provou_o_gatilho: set[str] = set()
        self._jogo_provou_a_luz: set[str] = set()
        self._game_authority_provider: Callable[[], str] | None = None
        self._retained_game_outputs: dict[str, dict[str, Any]] = {}
        self._retained_log_armed = True
        self._defend_last_at: float | None = None
        # ficaria ilegível. Some no `end_game_session_for`, com a sessão.
        self._recusa_ao_jogo_logada: dict[str, set[str]] = {}
        self._sysfs: dict[str, Any] = {}
        # O handle de cada nó do mapa: o mesmo no tique seguinte, o nó (e a memória) também.
        self._sysfs_donos: dict[str, Any] = {}
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
        """Feature 0x05 (calibração da IMU) do controle `uniq` (None = primário), ou None
        (fail-safe) (GYRO-01).

        É o report que o vpad carimba no blueprint para o motion espelhado calibrar com a unidade
        real. Lê por HIDIOCGFEATURE no hidraw do handle (fd efêmero), NÃO pelo `get_feature_report`
        da hidapi, que descarta o byte do report id; no BT valida o CRC-32 (seed 0xA3). Qualquer
        falha devolve None e o chamador fica no 0x05 canônico.
        """
        with self._io_lock:
            key = self._primary_key if uniq is None else self._key_for_uniq(uniq)
        if key is None:
            return None
        return self._ler_a_feature(
            key, _CALIBRATION_FEATURE_ID, _CALIBRATION_FEATURE_SIZE, "calibration"
        )

    def _ler_a_feature(
        self, key: str, feature_id: int, size: int, rotulo: str
    ) -> bytes | None:
        """Uma feature do controle `key` pelo hidraw dele, ou None (fail-safe).

        Dono único da leitura (calibração 0x05 e firmware 0x20): mesmo fd efêmero, mesmo opener do
        broker, mesma conferência (tamanho, id e, no rádio, CRC-32).
        """
        from hefesto_dualsense4unix.core.ds_output_report import (
            BT_FEATURE_CRC_SEED,
            bt_crc32,
        )

        with self._io_lock:
            handle = self._handles.get(key)
            if handle is None:
                return None
            transporte = self._detect_transport(handle)
            caminho = getattr(handle, "_pinned_path", None)
            if not isinstance(caminho, bytes):
                return None
            path = caminho.decode("utf-8", "replace")
            if not path.startswith("/dev/hidraw"):
                return None
            try:
                data = _read_feature_via_hidraw(
                    path,
                    feature_id,
                    size,
                    opener=self._feature_opener,
                )
            except OSError as exc:
                logger.info(f"{rotulo}_read_failed", key=key, err=str(exc))
                return None
        if len(data) != size or data[0] != feature_id:
            logger.warning(f"{rotulo}_report_invalido", key=key, tamanho=len(data))
            return None
        if transporte == "bt":
            crc = int.from_bytes(data[-4:], "little")
            if bt_crc32(data[:-4], seed=BT_FEATURE_CRC_SEED) != crc:
                logger.warning(f"{rotulo}_crc_invalido", key=key)
                return None
        return data

    def read_update_version(self, uniq: str | None = None) -> int | None:
        """O `update_version` do firmware do controle `uniq` (None = primário): u16 LE do byte 44 da
        feature 0x20, ou None."""
        with self._io_lock:
            key = self._primary_key if uniq is None else self._key_for_uniq(uniq)
        if key is None:
            return None
        return versao_do_firmware(
            self._ler_a_feature(
                key, _FIRMWARE_FEATURE_ID, _FIRMWARE_FEATURE_SIZE, "firmware"
            )
        )

    def _conhecer_o_firmware(self, key: str, handle: pydualsense) -> None:
        """Na conexão: lê o firmware do controle e põe o handle no modo dele, fora do `_io_lock`.

        O-CONTROLE-VIBRA-NO-MODO-DO-FIRMWARE-DELE-01. Vale para todo handle novo (conexão,
        reconexão, troca de nó).
        """
        uniq = self._key_to_uniq(key)
        versao = versao_do_firmware(
            self._ler_a_feature(
                key, _FIRMWARE_FEATURE_ID, _FIRMWARE_FEATURE_SIZE, "firmware"
            )
        )
        if uniq is not None:
            with self._io_lock:
                if versao is None:
                    # A leitura falhou neste handle: vale o que o controle disse numa conexão
                    # anterior (o firmware é do controle).
                    versao = self._firmware_por_uniq.get(uniq)
                self._firmware_por_uniq[uniq] = versao
        edge = bool(getattr(handle, "is_edge", False))
        v2 = fala_a_vibracao_v2(versao, edge=edge)
        definir = getattr(handle, "set_vibracao_v2", None)
        if callable(definir):
            definir(v2)
        logger.info(
            "firmware_do_controle_lido",
            uniq=_endereco_mascarado(uniq),
            update_version=None if versao is None else f"0x{versao:04x}",
            edge=edge,
            vibracao="v2" if v2 else "v1",
        )

    @property
    def primary_uniq(self) -> str | None:
        """MAC do dono do posto de P1: o primário, ou quem a vaga espera (None sem serial)
        (FEAT-DSX-CONTROLLER-IDENTITY-01).

        Delega a `_key_to_uniq`, cuja guarda de 12 dígitos hex evita o pseudo-MAC de path furar o
        guard anti-input-dobrado do co-op (M3).
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
        """Injeta (ou remove, com None) a fábrica de exposição do nó hidraw (O-NO-NASCE-FECHADO-01).

        O `hidapi` não aceita fd e o nó físico nasce `0600 root`, então o nó precisa estar exposto
        DURANTE o open; irmã de `set_feature_opener`. Consultada por `_open_one`.
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
        """A mesa que a regra de cor única resolve, JÁ NA ORDEM QUE DECIDE: o número do controle
        (`rank` da identidade).

        Sem número, a peça vai ao FIM e a ordem cai no `uniq` (estável). Ordem de `_handles` seria a
        do hotplug e a cor mudaria a cada religada. A cor GLOBAL entra na mesa (`DO_GLOBAL`): cede a
        quem tem identidade, não à irmã também global (D4).
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

        Mora no resolvedor, por onde passam todos os escritores de cor e a TELA
        (`resolved_led_for`); a regra `D-DUAS-PECAS-NUNCA-TEM-A-MESMA-COR` foi revogada pela
        D-0909-X (a recusa mora no gesto), sobra o fóssil e o salto ao tom livre. Fica ABAIXO da
        camada GAME (R-20 item 2): deslocar a cor pedida pelo jogo seria mentir.
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
            # O jogo manda; sem ele, o perfil ganha (decisão de 03/10/2026, revoga
            # PERFIL-MANDA-01). Só a numeração é do Hefesto.
            nao_pinta = numeracao_do_jogo(
                {nome: getattr(game, nome) for nome in _OUTPUT_FIELDS}
            )
            game = _sem_os_campos(game, nao_pinta)
            if game is not None:
                resolved = _merge_desired(resolved, game)
        return resolved

    def _assentar_mesa_locked(self) -> None:
        """Apresenta a mesa INTEIRA ao provider antes de numerar alguém (MESA-NO-MEIO-DO-LOTE-01).

        Todo lote resolve várias chaves sob o mesmo `_io_lock` e o provider ADMITE na mesa quem
        pergunta: sem apresentar todos antes, um controle que volta entre dois batimentos era
        numerado com a mesa de três e dois ficavam com o padrão do 1. Barato (sem I/O), uma vez por
        composição de `_handles`; a marca grava ANTES do laço. A ordem é a de `_handles` (primário
        primeiro), nunca a do `frozenset` (R-24).
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
        """Aplica a escala de brilho por-uniq (R-20 item 2), sob `_io_lock`; devolve SEMPRE um
        objeto novo ao escalar.

        Só sobre a BASE, nunca sobre a cor resolvida (A-BARRA-NAO-ESCURECE-AO-REAPLICAR-01): o fator
        é relativo ao brilho do perfil e o override já chega no brilho dele. Mutar o
        `_desired_default` corromperia o padrão de todo mundo.
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
        """Solta os campos cuja procedência é `layer`, sob `_io_lock` (R-20): cada camada é limpa
        pelo SEU dono."""
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
        """Carimba a procedência dos campos escritos, sob `_io_lock` (R-20).

        O perfil carimbado não tira o que o jogo pintou; o GESTO do usuário (`usuaria`) é a ordem
        mais nova e solta o que o jogo pintou NAQUELES campos até ele pintar de novo (decisão de
        03/10/2026, revoga PERFIL-MANDA-01).
        """
        donos = self._desired_owner_by_uniq.setdefault(uniq, {})
        for campo in campos:
            donos[campo] = layer
        if layer == _LAYER_USER:
            self._o_gesto_solta_o_que_o_jogo_pintou_locked(uniq, tuple(campos))

    def _o_gesto_solta_o_que_o_jogo_pintou_locked(
        self, uniq: str, campos: tuple[str, ...]
    ) -> None:
        """Tira da camada do jogo os campos que o gesto do usuário acabou de escrever."""
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

        Rate-limit de `DEFEND_DISPLAY_MIN_INTERVAL_S`, em função própria para haver uma conta só do
        relógio.
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
        """Guarda o brilho em que a cor da mão do usuário foi mandada. Sob `_io_lock`."""
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
        """Retorna `[(key, path, is_edge)]` de TODOS os DualSense plugados, sem duplicar o device
        (seam de teste).

        `key` é o `serial_number` (== MAC) ou, sem serial em USB, o `path`. O mesmo controle em dois
        nós é uma key: vence o cabo (vibração por áudio, som, menos atraso), para a escolha nunca
        ser do sorteio (O-CABO-ASSUME-DO-RADIO-01).
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
        """Abre UM controle por `path`, DENTRO de uma exposição do nó (O-NO-NASCE-FECHADO-01).

        O nó físico nasce `0600 root` e o hidapi não aceita fd; o broker expõe o nó, abre-se,
        solta-se o pedido. A janela cobre o `join` do runner, não o runner inteiro (um `init()`
        tardio acha o nó fechado e falha pelo handoff atômico). Sem fábrica (CLI, dublê), abre por
        caminho.
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
            # `pydualsense.__find_device()` levanta `Exception("No device detected")`: corrida com
            # unplug entre enumerate e open, tratada como ausência (None); as demais propagam.
            if "No device detected" in str(exc):
                return None
            raise exc
        return ds

    # --- ciclo de vida / reconciliação (hotplug) ---

    def connect(self) -> None:
        """Reconcilia os handles abertos com os controles fisicamente plugados; idempotente, é o
        TICK DE HOTPLUG do `reconnect_loop`.

        Controle novo: abre e re-aplica o PERFIL ATIVO; removido: fecha sem vazar e promove o
        próximo a primário; presente por OUTRO nó: troca o handle no mesmo lugar
        (O-CABO-ASSUME-DO-RADIO-01, `_o_no_mudou_locked`).
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
            self._aplicar_os_pisos_de_escrita_locked()
        novas_bt = 0
        for _key, handle in new_handles:
            with contextlib.suppress(Exception):
                if self._detect_transport(handle) == "bt":
                    novas_bt += 1
        if novas_bt:
            with self._io_lock:
                self._conexoes_bt_novas += novas_bt
        # `core/lightbar_reset.py` derruba o claim da lightbar no firmware por BT: o que caducou é
        # MANDÁ-LO, não o layout do report. LIGHTBAR-BT-CULPADO-01.

        # O tique só repinta a luz que o kernel perdeu (O-TIQUE-DE-30-S-SO-REPINTA-A-LUZ-QUE-O-
        # KERNEL-PERDEU-01): o nó de quem segue no mesmo handle guarda a memória entre os tiques
        # (`_refresh_sysfs_leds`), e a cor LIDA diferente da resolvida (o wake, que devolve o nó ao
        # azul do kernel sem reabrir o handle, ou quem escreveu na classe por fora) faz o nó e o
        # quadro do `0x31` esquecerem; o reassert abaixo repinta pela rota normal, sem `0x08`
        # (LIGHTBAR-BT-CULPADO-01), e sob o mudo do Modo Nativo só pelo nó. Só leitura de sysfs.
        new_keys = {k for k, _ in new_handles}
        with self._io_lock:
            reclaim_candidates = [
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
        for key, handle, node, desired, transport in reclaim_candidates:
            with contextlib.suppress(Exception):
                self._esquecer_a_luz_que_o_kernel_perdeu(key, handle, node, desired.led, transport)

        self._refresh_sysfs_leds()
        for key, handle in new_handles:
            with contextlib.suppress(Exception):
                self.assumir_volume_padrao_na_adocao(key, handle)
            # O PS segurado sozinho por 10 s desliga este controle (`_vigiar_o_ps_segurado`).
            _vigiar_o_ps_segurado(self, key, handle)
            self._conhecer_o_firmware(key, handle)
            self._reaplicar_com_as_intensidades(key, handle)
        # acabaram de surgir. Sintoma provado ao vivo: boot com os DualSense
        self.reassert_resolved_outputs()

    def _esquecer_a_luz_que_o_kernel_perdeu(
        self,
        key: str,
        handle: Any,
        node: Any,
        cor: tuple[int, int, int] | None,
        transport: str,
    ) -> bool:
        """A cor lida no nó diverge da resolvida: o nó, o quadro do rádio e o brilho do cabo
        esquecem, e o reassert do mesmo tique repinta. Devolve se esqueceu.

        Nó ilegível ou sem cor resolvida não afirma nada. `should_reclaim_on_wake` só classifica o
        episódio no diário: o wake (o azul do kernel no rádio) ou um escritor de fora.
        """
        from hefesto_dualsense4unix.core.lightbar_reset import should_reclaim_on_wake

        if node is None or cor is None:
            return False
        lida = node.cor_perdida(cor)  # o quadro do efeito, nosso, não é perda
        if lida is None:
            return False
        node.invalidate_cache()
        with contextlib.suppress(AttributeError):
            handle._quadro_da_luz = None
            handle._brilho_do_cabo = None
        logger.info(
            "lightbar_perdida_repintada",
            key=key,
            transport=transport,
            lida=lida,
            resolvida=cor,
            wake=should_reclaim_on_wake(transport, cor, lida, KERNEL_DEFAULT_BLUE),
        )
        return True

    def _aplicar_os_pisos_de_escrita_locked(self) -> None:
        """O espaçamento mínimo entre duas escritas de cada controle, por transporte, sob `_io_lock`
        a cada `connect`.

        Cabo: `PISO_DE_ESCRITA_DO_CABO_SEC`, igual para um ou quatro. Rádio:
        `REPORT_THREAD_THROTTLE_SEC x n`, com `n` só os controles do MESMO adaptador, no teto de
        `REPORT_THREAD_THROTTLE_MAX_SEC`. A-VIBRACAO-DO-JOGO-NAO-ESPERA-O-SONO-DA-VOLTA-01.
        """
        radio: dict[str, str] = {}
        for key, handle in self._handles.items():
            if self._detect_transport(handle) == "bt":
                radio[key] = self._key_to_uniq(key) or key
        adaptadores: dict[str, str] = {}
        if radio:
            try:
                from hefesto_dualsense4unix.integrations import radio_da_mesa

                adaptadores = radio_da_mesa.adaptador_por_uniq(sorted(set(radio.values())))
            except Exception as exc:
                logger.debug("adaptador_do_radio_ilegivel", err=str(exc))
        no_adaptador: dict[str, int] = {}
        for uniq in radio.values():
            grupo = adaptadores.get(uniq, "")
            no_adaptador[grupo] = no_adaptador.get(grupo, 0) + 1
        for key, handle in self._handles.items():
            if key in radio:
                grupo = adaptadores.get(radio[key], "")
                piso = min(
                    REPORT_THREAD_THROTTLE_SEC * max(1, no_adaptador[grupo]),
                    REPORT_THREAD_THROTTLE_MAX_SEC,
                )
            else:
                piso = PISO_DE_ESCRITA_DO_CABO_SEC
            handle._piso_de_escrita_sec = piso

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

        Aqui a reserva CADUCA (passou de `PRIMARIO_RESERVA_SEC`, é esquecida); a caducidade é `info`
        para o journal medir o desfecho alternativo. A constante só se decide depois da bancada.
        """
        reserva = self._primario_deposto
        if reserva is None:
            return None
        key, quando = reserva
        if (
            self._relogio() - quando >= PRIMARIO_RESERVA_SEC
            and not self._o_lugar_do_deposto_espera_locked(key)
        ):
            self._primario_deposto = None
            logger.info("primario_reserva_caducou", key=key)
            return None
        if key not in self._handles or key == self._primary_key:
            return None
        return key

    def _o_lugar_do_deposto_espera_locked(self, key: str) -> bool:
        """A reserva do posto passa dos 30 s enquanto a pergunta da vaga diz que espera.

        `D-3009-COM-O-JOGO-O-LUGAR-GUARDADO-ESPERA`: com o jogo na autoridade o posto do P1 espera
        como o lugar guardado; caducar no relógio próprio punha o P2 no vpad do jogador 1. Quem
        decide é `set_espera_do_posto`; ele de volta na mesa também conta.
        """
        pergunta = self._espera_do_posto
        uniq = self._key_to_uniq(key)
        if pergunta is None or uniq is None:
            return False
        try:
            return bool(pergunta(uniq))
        except Exception as exc:
            logger.warning("posto_do_p1_pergunta_falhou", err=str(exc))
            return False

    def _recompute_primary(self) -> None:
        """(Re)elege o primário e re-atrela evdev/transport SÓ quando ele muda. Chamado sob
        `_io_lock`.

        Primário = o controle da CARTA MENOR na mesa (`_quem_senta_no_posto`), sem carta a 1ª chave
        de inserção (O-MODO-XBOX-NAO-E-QUEDA-02). Exceção (COOP-QUE-NAO-DESMONTA-01 / E2a): quem era
        o primário e voltou dentro de `PRIMARIO_RESERVA_SEC` RETOMA o posto, pelo MESMO caminho da
        promoção (refaz `_detect_transport` e o `retarget`). O AVISO sai daqui, antes do `retarget`
        (E1).
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
        # E1: o co-op precisa SOLTAR o node do controle que virou primário ANTES de o leitor mirar
        # nele (depois, o `EBUSY` já aconteceu e morre o Jogador 2).
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
            donos = getattr(self, "_sysfs_donos", {})

        mapping: dict[str, Any] = {}
        for key in keys:
            nk = sysfs_leds.norm_mac(key)
            node = by_mac.get(nk) if nk else None
            if node is not None and node.writable():
                mapping[key] = self._o_mesmo_no(prev.get(key), node, donos.get(key), handles[key])

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
                pode_player = self._pode_escrever_player_leds()
                reasserts = [
                    (key, mapping[key], self._merged_desired_for_key(key))
                    for key in new_keys
                ]
            for key, node, desired in reasserts:
                if desired.led is None:
                    desired = replace(desired, led=KERNEL_DEFAULT_BLUE)
                with contextlib.suppress(Exception):
                    self._repintar_a_luz_de_um(
                        key,
                        handles[key],
                        node,
                        desired,
                        pode_player=pode_player,
                        what="sysfs_no_novo",
                        forcar=True,
                    )

        with self._io_lock:
            self._sysfs = mapping
            self._sysfs_donos = {key: handles[key] for key in mapping}
            self._sysfs_written = {
                key: rgb for key, rgb in self._sysfs_written.items() if key in mapping
            }

    @staticmethod
    def _o_mesmo_no(anterior: Any, novo: Any, dono_anterior: Any, handle: Any) -> Any:
        """O nó do tique anterior quando o handle e os diretórios são os mesmos: a memória dele
        (cor e número) atravessa o tique. Handle novo (a reconexão) ganha o nó novo, sem memória.
        """
        if anterior is None or dono_anterior is not handle:
            return novo
        mesmo = getattr(anterior, "indicator_dir", None) == getattr(
            novo, "indicator_dir", None
        ) and list(getattr(anterior, "player_dirs", ())) == list(getattr(novo, "player_dirs", ()))
        return anterior if mesmo else novo

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
        """MAC (ou key) do alvo de output APONTADO mas fora da mesa; `None` se o alvo é "Todos" ou
        está presente.

        Existe porque `get_output_target_index/uniq` mascaram esse estado e o `_handle_rumble_set`
        precisa recusar com `MOTIVO_ALVO_FORA_DA_MESA` antes de `set_rumble`, no molde da
        NATIVO-RUMBLE-01 (BROADCAST-PROIBIDO-01, Z3-5; redação provisória, a validar pelo usuário).
        Led/gatilho/player guardam o valor no override por-uniq e respondem `"registrado"`
        (MESA-CHEIA-09).
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
            _acordar_a_volta_de(handle)

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
            _acordar_a_volta_de(handle)

    def suprimir_player_leds(self, ativo: bool) -> bool:
        """Liga/desliga a escrita dos LEDs de JOGADOR. Instrumento de eliminação."""
        self._suprimir_player_leds = bool(ativo)
        logger.info("player_leds_suprimidos", ativo=self._suprimir_player_leds)
        return self._suprimir_player_leds

    def _pode_escrever_player_leds(self) -> bool:
        """False enquanto o instrumento de eliminação estiver ligado."""
        return not getattr(self, "_suprimir_player_leds", False)

    def enviar_release_leds(self, *, uniq: str | None = None) -> dict[str, bool]:
        """Manda o Reset LED state (0x08) SOB DEMANDA. É um INSTRUMENTO (LIGHTBAR-MEDIR-O-0X08-01).

        Escreve pelo handle que o daemon já tem aberto, sem disputar o hidraw. `uniq` restringe a um
        controle; devolve `{key: enviou?}` (vazio = nenhum handle). Fora do caminho automático
        desde 04/08 (LIGHTBAR-BT-CULPADO-01: 7/7 travas dentro da janela de ~3,4 s pós-conexão;
        fora dela não trava); a hipótese aberta é que o 0x08 devolve o claim se não vier em cima
        da conexão. Nenhum caminho automático o chama.
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
        """Repinta a barra dos DualSense do CABO, ignorando o cache
        (LIGHTBAR-O-CABO-FICOU-DE-FORA-01).

        O irmão `reescrever_lightbar_por_hidraw` só conhece o rádio; o cabo é pintado pela classe
        LED e ninguém o repintava ao renumerar a mesa. O cache do `SysfsLeds` mede a COR e não o
        NÚMERO, por isso é invalidado antes. Devolve `{key: repintado?}` (vazio = nenhum no cabo);
        vale no Modo Nativo (`D-2309-NO-NATIVO-A-LUZ-E-O-NUMERO-SAO-DO-HEFESTO`).
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
        """`{uniq: /dev/hidrawN}` dos DualSense abertos AGORA (só leitura), o endereço da sonda de
        `/proc` (ESCRITOR-CRU-01).

        Handle sem MAC ou com path de libusb fica de fora.
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
        """Repinta cor E número de jogador em TODOS os DualSense do rádio (GATILHO-DA-COR-01);
        `{key: escreveu?}`, best-effort por handle.

        Escrita AVULSA com report montado por nós (sem `RELEASE_LEDS`, sem SETUP/BRILHO, vibração
        nem áudio), então `_suppress_leds` segue True e o keepalive LED-neutro
        (LIGHTBAR-BT-NEVER-01). Em TODOS, porque a rajada da Steam repinta todo mundo. O Modo Nativo
        ESCREVE (`D-2309-NO-NATIVO-A-LUZ-E-O-NUMERO-SAO-DO-HEFESTO`, STEAM-NO-FISICO-01).
        INCONDICIONAL: o `multi_intensity` mostra o valor pedido, não o aceso, então sem cache nem
        dedup. Cor e número vêm do `_merged_desired_for_key`; sem cor, o azul-default do kernel.
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

        Corpo comum ao gatilho do fim da sequência e à vigia do sequestro
        (`reafirmar_barra_e_numero`); `nome` prefixa os avisos. Não loga o sucesso (quem chama
        decide a cadência). O quadro inteiro fica em `_quadro_da_luz`, memória do
        `_repintar_a_luz_de_um`.
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
            with contextlib.suppress(Exception):
                handle._quadro_da_luz = (cor, players, brilho) if ok else None
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
        """Reescreve a BARRA e o NÚMERO destes controles, e só isso: o vigia do sequestro, que
        escreve SEMPRE (`forcar`).

        No rádio não passa o nó: com a Steam no hidraw a classe LED não muda a barra.
        """
        alvos_uniq = {u for u in (self._key_to_uniq(x) for x in uniqs) if u}
        with self._io_lock:
            pode_player = self._pode_escrever_player_leds()
            alvos = []
            for key, handle in self._handles.items():
                if self._key_to_uniq(key) not in alvos_uniq:
                    continue
                radio = self._detect_transport(handle) == "bt"
                no = (
                    self._sysfs.get(key)
                    if isinstance(self._sysfs, dict) and not radio
                    else None
                )
                alvos.append(
                    (key, handle, no, radio, self._merged_desired_for_key(key))
                )
        resultado: dict[str, bool] = {}
        for key, handle, no, radio, desired in alvos:
            ok, cor, players = self._repintar_a_luz_de_um(
                key,
                handle,
                no,
                desired,
                pode_player=pode_player,
                what="vigia_do_sequestro",
                forcar=True,
                apesar_do_mudo=True,
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

    def _repintar_a_luz_de_um(
        self,
        key: str,
        handle: Any,
        no: Any,
        desired: _DesiredOutput,
        *,
        pode_player: bool,
        what: str,
        verify: bool = False,
        forcar: bool = False,
        apesar_do_mudo: bool = False,
    ) -> tuple[bool, tuple[int, int, int] | None, tuple[bool, ...] | None]:
        """A cor e o número RESOLVIDOS de UM controle, pela rota que o alcança
        (A-COR-E-O-NUMERO-DO-PERFIL-CHEGAM-POR-TODA-ROTA-01).

        Dono único para o vigia, `reassert_resolved_outputs`, `set_output_mute(False)` e a repintura
        de nó novo. Cabo: o nó (`verify` quando pedido) ou o fluxo do pydualsense, mais o brilho das
        luzes. Rádio: o nó, se houver, e o `0x31` estreito (brilho no mesmo quadro); quadro igual ao
        último inteiro não sai de novo, e `forcar` ignora a memória. Modo Nativo: sem `0x31`, salvo
        `apesar_do_mudo`.
        """
        # Dono único das repinturas: o efeito da barra (`luz_animada`) lê este contador.
        self._repinturas_da_luz += 1
        if forcar and no is not None:
            with contextlib.suppress(Exception):
                no.invalidate_cache()
        if forcar:
            with contextlib.suppress(AttributeError):
                handle._brilho_do_cabo = None
        players = desired.player_leds if pode_player else None
        if self._detect_transport(handle) == "bt":
            cor_do_radio = desired.led if desired.led is not None else KERNEL_DEFAULT_BLUE
            brilho = desired.player_led_brightness if pode_player else None
            if not forcar and getattr(handle, "_quadro_da_luz", None) == (
                cor_do_radio,
                players,
                brilho,
            ):
                return True, cor_do_radio, players
            if no is not None:
                ok_no = self._escrever_a_luz_no_no(
                    key, no, desired.led, players, verify=verify, what=what
                )
            else:
                ok_no = False
            mudo = self._output_mute or getattr(handle, "_output_muted", False)
            if mudo and not apesar_do_mudo:
                # Modo nativo: o hidraw é do jogo e nenhum report cru sai por baixo dele
                # (FEAT-NATIVE-OUTPUT-MUTE-01); o nó basta.
                return ok_no, cor_do_radio, players
            return self._escrever_barra_e_numero_bt(
                key, handle, desired, pode_player=pode_player, nome=what
            )
        if no is not None:
            ok = self._escrever_a_luz_no_no(
                key, no, desired.led, players, verify=verify, what=what
            )
        else:
            ok = self._escrever_a_luz_no_fluxo(key, handle, desired.led, players, what=what)
        self._levar_o_brilho_das_luzes(key, handle, desired.player_led_brightness, what=what)
        return ok, desired.led, players

    def _escrever_a_luz_no_no(
        self,
        key: str,
        no: Any,
        cor: tuple[int, int, int] | None,
        players: tuple[bool, ...] | None,
        *,
        verify: bool,
        what: str,
    ) -> bool:
        """Cor e número pela classe LED do kernel; `verify` relê antes de pular."""
        ok = True
        try:
            if cor is not None:
                escreveu = no.set_rgb(*cor, verify=True) if verify else no.set_rgb(*cor)
                if escreveu:
                    self.record_sysfs_write(key, cor)
                ok = bool(escreveu) and ok
            if players is not None:
                verificado = getattr(no, "set_players_verified", None) if verify else None
                escreveu = (
                    verificado(players) if callable(verificado) else no.set_players(players)
                )
                ok = bool(escreveu) and ok
        except Exception as exc:
            logger.warning(f"{what}_no_falhou", key=key, err=str(exc))
            ok = False
        return ok

    @staticmethod
    def _escrever_a_luz_no_fluxo(
        key: str,
        handle: Any,
        cor: tuple[int, int, int] | None,
        players: tuple[bool, ...] | None,
        *,
        what: str,
    ) -> bool:
        """Cor e número no estado do pydualsense: a rota do cabo sem nó gravável; o que o handle já
        tem não se reescreve."""
        from pydualsense.enums import PlayerID

        try:
            luz = handle.light
            if cor is not None and getattr(luz, "TouchpadColor", None) != tuple(cor):
                luz.setColorI(*cor)
            if players is not None:
                numero = PlayerID(sum(1 << i for i, b in enumerate(players) if b))
                if getattr(luz, "playerNumber", None) != numero:
                    luz.playerNumber = numero
        except Exception as exc:
            logger.warning(f"{what}_fluxo_falhou", key=key, err=str(exc))
            return False
        return True


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
            _acordar_a_volta_de(handle)

    @staticmethod
    def _apply_trigger(handle: pydualsense, side: Side, effect: TriggerEffect) -> None:
        trigger = handle.triggerL if side == "left" else handle.triggerR
        trigger.mode = PyDualSenseController._coerce_mode(effect.mode)
        for idx, value in enumerate(effect.forces):
            trigger.setForce(idx, value)
        _acordar_a_volta_de(handle)

    def _reapply_desired(self, key: str, handle: pydualsense) -> None:
        """Re-aplica o estado desejado DESTE controle num handle recém-aberto (PERFIL-01 / 4P-01).

        Aplica o MERGE POR CAMPO do default com o override por-uniq da `key` certa. Reconexão no
        meio do jogo (REPLICA-03): a camada game e os blocos crus de gatilho são re-pendurados. O
        mudo do mic também (MIC-BT-DONO-01), FORA do `_write_partial_output`, onde `None` é "herda"
        e aqui é "devolvo ao kernel".
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
        """A SEGUNDA rota da lightbar por rádio, em regime (ROTA-BT-EM-REGIME-01); True se escreveu,
        False fora do rádio/sem valor/sem `seq`.

        Com a Steam viva o `sysfs` não muda a barra e o `0x31` no hidraw sim; é o
        `build_bt_lightbar_report` avulso e estreito do GATILHO-DA-COR-01, nunca religar o LED no
        `report_thread` (LIGHTBAR-BT-KEEPALIVE-01). `_suppress_leds` não muda; cabo não muda. O
        brilho das luzes de número vai no MESMO quadro
        (`D-2409-AS-LUZES-DE-NUMERO-TEM-TRES-BRILHOS`), pois cada report no rádio custa duas fatias.
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
        # A memória do `_repintar_a_luz_de_um` é o último quadro INTEIRO: sem cor ou sem número o
        # quadro é parcial e a memória não vale.
        quadro = None
        if rgb is not None and players is not None:
            quadro = (tuple(rgb), tuple(players), brilho_das_luzes)
        with contextlib.suppress(Exception):
            handle._quadro_da_luz = quadro
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
        # O degrau que este handle já levou não sai de novo; esquecem-no a cor perdida, o `forcar`
        # e a defesa de exibição (O-TIQUE-DE-30-S-SO-REPINTA-A-LUZ-QUE-O-KERNEL-PERDEU-01).
        if getattr(handle, "_brilho_do_cabo", None) == int(degrau):
            return True
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
        with contextlib.suppress(AttributeError):
            handle._brilho_do_cabo = int(degrau) if ok else None
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
        finally:
            _acordar_a_volta_de(handle)
        return True

    def set_trigger(self, side: Side, effect: TriggerEffect) -> None:
        campo = "trigger_left" if side == "left" else "trigger_right"
        self._for_each(
            lambda h: self._apply_trigger(h, side, effect),
            what="set_trigger",
            record={campo: effect},
        )

    def set_trigger_em_todos(
        self, side: Side, effect: TriggerEffect
    ) -> dict[str, ResultadoDeSaida]:
        """O «Em todos» da aba Gatilhos: o efeito em CADA controle aberto
        (O-EM-TODOS-DO-GATILHO-CHEGA-A-CADA-CONTROLE-DA-MESA-01).

        Escreve em todos os handles (ignora o destino da aba Conexões), grava o padrão e nivela os
        overrides, e solta o que o jogo pintou naquele lado. Devolve `{mac:
        "escreveu"|"registrado"|"falhou"}`; handle sem MAC escreve e não entra.
        """
        campo = "trigger_left" if side == "left" else "trigger_right"
        with self._io_lock:
            _alvo, handles, _ausente = _resolver_escopo(
                self._handles, self._output_target_key, broadcast=True
            )
            self._record_desired_locked(None, {campo: effect})
            alvos: list[tuple[str, Any, str | None]] = []
            for key, handle in handles:
                uniq = self._key_to_uniq(key)
                if uniq is not None:
                    self._o_gesto_solta_o_que_o_jogo_pintou_locked(uniq, (campo,))
                alvos.append((key, handle, uniq))
            muted = self._output_mute
        palavras: dict[str, ResultadoDeSaida] = {}
        for key, handle, uniq in alvos:
            palavra: ResultadoDeSaida = "registrado" if muted else "escreveu"
            try:
                self._apply_trigger(handle, side, effect)
            except Exception as exc:
                logger.warning(
                    "output_handle_failed", op="set_trigger_em_todos", key=key, err=str(exc)
                )
                palavra = "falhou"
            if uniq is not None:
                palavras[uniq] = palavra
        return palavras

    @staticmethod
    def _quadro_que_solta_os_gatilhos(desligado: TriggerEffect, *, radio: bool) -> bytearray:
        """O report que só solta os dois gatilhos: `flag0` `0x04|0x08` e os dois blocos em Off; o
        resto sai sem autorização, e o firmware conserva a luz, o som e a vibração que tinha."""
        common = bytearray(rep.COMMON_LEN)
        common[0] = rep.VALID_FLAG0_RIGHT_TRIGGER_FFB | rep.VALID_FLAG0_LEFT_TRIGGER_FFB
        bloco = bloco_do_gatilho(int(desligado.mode), desligado.forces)
        common[10 : 10 + GAME_TRIGGER_BLOCK_LEN] = bloco
        common[21 : 21 + GAME_TRIGGER_BLOCK_LEN] = bloco
        return rep.build_bt_report(common, seq=0) if radio else rep.build_usb_report(common)

    def soltar_os_gatilhos(self) -> dict[str, bool]:
        """Quem solta o controle solta o gatilho de TODOS
        (QUEM-SOLTA-O-CONTROLE-SOLTA-O-GATILHO-DE-TODOS-01).

        Em cada handle aberto, sem olhar o destino da aba Conexões: tira o bloco cru do jogo, arma
        Off nos dois lados e escreve na hora o report só dos gatilhos pelo escritor do próprio
        handle (o `writeReport` carimba o `seq` e o CRC do rádio). Não grava desejo nem override:
        soltar não é escolha de ninguém. Sob o mudo do Modo Nativo não escreve: o jogo é o dono.
        Devolve `{key: o quadro saiu inteiro}`.
        """
        from hefesto_dualsense4unix.core.trigger_effects import build_from_name

        desligado = build_from_name("Off", [])
        with self._io_lock:
            if self._output_mute:
                logger.info("gatilhos_nao_soltos_sob_o_mudo", controles=len(self._handles))
                return {}
            alvos = list(self._handles.items())
        resultado: dict[str, bool] = {}
        for key, handle in alvos:
            ok = False
            try:
                handle._raw_trigger_left = None
                handle._raw_trigger_right = None
                self._apply_trigger(handle, "left", desligado)
                self._apply_trigger(handle, "right", desligado)
                # Depois do Off armado: o report que a volta montou antes não sai mais.
                handle._geracao_da_saida = getattr(handle, "_geracao_da_saida", 0) + 1
                quadro = self._quadro_que_solta_os_gatilhos(
                    desligado, radio=self._detect_transport(handle) == "bt"
                )
                escritor = getattr(handle, "writeReport", None)
                if callable(escritor):
                    escrito = escritor(list(quadro))
                else:
                    escrito = getattr(handle, "device", handle).write(bytes(quadro))
                ok = _escrita_completa(escrito, len(quadro))
            except Exception as exc:
                logger.warning("gatilho_solto_falhou", key=key, err=str(exc))
            resultado[key] = ok
        logger.info(
            "gatilhos_soltos", controles=len(resultado), escritos=sum(resultado.values())
        )
        return resultado

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
        """O par, como veio, no alvo de output (ou em todos); o fator da peça já veio pelo funil
        `core.rumble.forca_do_controle`."""
        def _do(handle: pydualsense, _key: str) -> None:
            handle.setLeftMotor(strong)
            handle.setRightMotor(weak)

        self._for_each_com_key(_do, what="set_rumble")

    def escala_de(self, uniq: str) -> float | None:
        """O fator de vibração da peça ``uniq`` (POR-UNIDADE-01), ou ``None``; leitura do mapa de
        :meth:`set_rumble_scales`."""
        alvo = self._key_to_uniq(uniq)
        return self._rumble_scale_by_uniq.get(alvo) if alvo is not None else None

    def bateria_de(self, uniq: str) -> int | None:
        """A bateria 0-100 do controle ``uniq``, da memória do handle, sem I/O; ``None`` sem handle
        ou sem report (:meth:`_read_battery_opt`)."""
        alvo = self._key_to_uniq(uniq)
        if alvo is None:
            return None
        with self._io_lock:
            key = self._key_for_uniq(alvo)
            handle = self._handles.get(key) if key is not None else None
        return self._read_battery_opt(handle) if handle is not None else None

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
            self._trocar_o_mapa_das_intensidades("_rumble_scale_by_uniq", novo)

    def force_rumble_stop(self, uniq: str | None = None) -> None:
        """Para os motores com um report de stop (HARM-16) — todos, ou UM (`uniq`,
        BORDA-DE-QUEDA-01).

        Força `_rumble_stop_pending` em cada handle: o `set_rumble(0, 0)` 0→0 não muda o report e
        não é escrito (dedup, RUMBLE-SEM-DONO-01), mas a saída de modo precisa parar o motor que o
        JOGO deixou vibrando. `uniq` restringe a um controle (queda de um jogador do co-op não para
        a mesa), via `_casar_key`; alvo que não casa é NO-OP.
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
        """Acende/apaga o LED do microfone no ALVO, ou no controle `uniq` (MIC-DA-MESA-ELEICAO-01).

        Chama `ds.audio.setMicrophoneLED`; toma a posse de `common[8]` (`_escrever_led_do_mic`,
        AUDIO-OWNER-01): report[9] no cabo, report[11] no rádio. CORRIGIDO em 15/08/2026: a
        pydualsense 0.7.5 diz outReport[10] no BT, errado por um. Com `uniq` escreve só naquele
        handle e no override dele (sem ele, o `record` zeraria o `mic_led` de todos). `aceso` = mic
        VIVO (inversão de 01/09/2026); quem decide é o chamador (`mic_da_mesa.py`).
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
        """`{"volume": 0-255, "muted": bool}` do alto-falante, ou None (AUDIO-OWNER-01).

        O DualSense não devolve o volume: só se sabe o que NÓS mandamos. Sem `set_speaker_volume`,
        None e a chave `speaker` nem entra. `muted` = volume efetivo 0. A chave `rota` (SOM-ROTA-01)
        é opcional pelo mesmo motivo: só existe quando somos donos do `common[7]`; sem ela quem lê
        diz «não dá para saber».
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
        dono = next((self._key_to_uniq(k) for k, h in list(self._handles.items()) if h is alvo), "")
        logger.info("speaker_volume_set", uniq=dono or uniq or "", volume=volume,
                    muted=bool(muted), ok=ok)  # o dono: o alvo de saída quando não há endereço
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
            # A tela é a lei: o byte do firmware é o do deslizante, o MESMO no cabo e no rádio, e
            # o alto-falante e o fone vão juntos. A placa a 40 % era o defeito, e não a régua.
            cabo = self._detect_transport(handle) != "bt"
            efetivo = 0 if muted else pref
            handle.set_audio_volumes(
                headphone=efetivo,
                speaker=efetivo,
                preamp=rep.SP_PREAMP_GAIN_PADRAO,
                audio_path=_byte_da_rota(handle, rota),
            )
            if getattr(self, "_output_mute", False) or getattr(handle, "_output_muted", False):
                # Modo Nativo: o laço não escreve, e o som sai sozinho no report mínimo dele.
                escrever = getattr(handle, "escrever_so_o_som", None)
                if callable(escrever) and not escrever(radio=not cabo):
                    logger.warning("som_no_nativo_nao_saiu", op=op)
                    return False
        except Exception as exc:
            logger.warning("output_handle_failed", op=op, err=str(exc))
            return False
        return True

    def release_speaker_volume(self, *, uniq: str | None = None) -> bool:
        """DEVOLVE a posse dos bytes de volume — o irmão do `mic release` (SOM-02, E3). True se o
        handle de `uniq` recebeu; idempotente.

        Os quatro bytes `common[4..7]` voltam a «sem dono» e os bits do flag0 saem zerados; NÃO há
        restauração de valor (o firmware conserva o último). A PREFERÊNCIA (`_speaker_volume_pref`)
        morre junto, ou um `muted=False` retomaria a posse sem pedido.
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
        """Toma a posse do volume e o põe em 100% assim que o controle é ADOTADO (SOM-SEMPRE-01);
        best-effort, False deixa tudo como estava.

        Na adoção porque a posse morre com o handle e é o ponto universal (1º ou 7º, cabo ou rádio,
        boot ou hotplug). Sem a posse o alto-falante nascia mudo. A rota nasce em
        `ROTA_PADRAO_DO_SOM` (SOM-ROTA-02: não escrever a rota É escolher o fone), preservando os
        bits do mic por `OUTPUT_PATH_SEL_MASK`. Fone e alto-falante vão ao mesmo valor. Fica de fora
        o ganho do MICROFONE (`D-0909-O-VOLUME-DO-MIC-LIGA-O-BYTE-DO-APARELHO`: quem o liga é
        `set_microphone_volume`). O preço, irreversível até `speaker release` ou desconectar, está
        aceito. Modo Nativo: só memória; o `report_thread` não escreve com `_output_muted`
        (FEAT-NATIVE-OUTPUT-MUTE-01). O gancho de perfil cobre o replug por peça (SOM-ROTA-03,
        `reapply_speaker_on_connect`).
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
        """Assume a posse do `common[6]` — o GANHO DE CAPTURA do aparelho (MIC-VOLUME-02); True se o
        handle de `uniq` recebeu.

        `D-0909-O-VOLUME-DO-MIC-LIGA-O-BYTE-DO-APARELHO`: a bancada provou que o byte age (cabo,
        09/09/2026), e ele é o SEGUNDO degrau (o primeiro é o ganho da FONTE no PipeWire). Não
        medido: onde fica mudo/satura (ver :func:`byte_do_volume_do_microfone`) e o rádio (sem
        microfone publicado, MIC-OS-QUATRO-01). Irreversível até `release_microphone_volume` ou
        desconectar; o applier de perfil restaura. `percentual` é 0-100.
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
        """Devolve ao firmware a posse do `common[6]`, e SÓ dele (MIC-VOLUME-02); devolve o
        CONTROLE, nunca o número."""
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
        """Assume (`True`/`False`) ou DEVOLVE (`None`) a posse do `common[8]`
        (MIC-DA-MESA-ELEICAO-01).

        A porta de emergência da devolução por-byte. Não é o `RELEASE_LEDS` (só rádio): cai só o bit
        `0x01` do flag1, nos dois transportes. A devolução REPINTA ANTES DE SOLTAR (LUZ-DO-MIC-01
        §2, `_repintar_antes_de_soltar`), senão a luz fica presa no último valor. Vale para
        `mic.led.set {aceso: null}`, `mic led-release` e o desligamento do daemon.
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
            if aceso is not None and _no_modo_nativo(self, alvo):
                _entregar_a_luz_do_mic_no_nativo(self, alvo)  # o laço calado não a escreve
        except Exception as exc:
            logger.warning(
                "output_handle_failed", op="set_microphone_led", err=str(exc)
            )
            return False
        logger.info("microphone_led_set", aceso=aceso, uniq=uniq, repintado=repintado)
        return True

    def _repintar_antes_de_soltar(self, handle: Any, uniq: str | None) -> int | None:
        """Escreve o mudo REAL no `common[8]` e ENTREGA o report, antes de soltar."""
        if getattr(handle, "_mic_led_desejado", None) is None:
            logger.debug("microphone_led_repintura_no_op_sem_posse", uniq=uniq)
            return None
        # Modo Nativo: o report inteiro passaria o resto do estado por cima do jogo, e a
        # devolução repinta só a luz, no report mínimo dela (`escrever_so_a_luz_do_mic`).
        nativo = _no_modo_nativo(self, handle)
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
            _entregar_a_luz_do_mic_no_nativo(self, handle) if nativo else escrever(montar())
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

        `True`/`False` = mandamos mudo/não-mudo em todo report; `None` = não somos donos (o
        `hid-playstation` manda). `False` é ORDEM, não «não mexer» (AUDIO-OWNER-01). O estado lido é
        o `mic_mudo` do `audio_status_for`; este diz quem MANDA. A fonte é o MAPA por-uniq
        (MIC-BT-DONO-01), pois o atributo do handle novo é `None` até o `_reapply_desired`. Sem
        handle, None.
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
        """Handle do controle `uniq`; sem endereço, o ALVO DE SAÍDA — e só então o primário.

        Os nove atos de áudio por controle caíam no primário enquanto
        `led.set`/`rumble.set`/`trigger.*` obedeciam ao seletor; a ordem é a de
        `ipc_handlers._uniq_do_primario`. As leituras do `state_full` passam `uniq` explícito. O
        `_output_target_key` é lido DENTRO do `_io_lock` já aberto (não reentrante).
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

        `DSLight.playerNumber` é `PlayerID` (`IntFlag`) e aceita qualquer inteiro; bit0 = LED 1
        (esquerdo) … bit4 = LED 5 (direito), bit2 o central do Player 1 canônico. Referência:
        outReport[44] USB / [45] BT em `pydualsense/pydualsense.py:572/636`.
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
                rgb=(r, g, b),
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
                players=bits,
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
        """SUBSTITUI o mapa de escala de brilho por-uniq (R-20 item 2), camada do PERFIL.

        Aplicada sobre a BASE do merge (global e automática), nunca sobre o override, que já traz o
        brilho dele (`_scaled_led`). Fator ≤ 0 apaga a barra; ausência = sem opinião; sem escrita de
        hardware (o `reassert_resolved_outputs` converge). `brilho_do_perfil` é o brilho a que os
        fatores são RELATIVOS (`None` guarda o anterior; A-BARRA-NAO-ESCURECE-AO-REAPLICAR-01).
        `cor_do_perfil` é a cor GLOBAL antes do brilho (`None` se não há) e vai sempre com ele; o
        fator entra numa conta só também no global (`led_control.reescalar`).
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
        # o fator é `brilho_do_controle / brilho_do_perfil`
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
        """Rumble mirado no controle de MAC `uniq`, SEM tocar no seletor global (PERFIL-01).

        Substitui o flip do `_output_target_key`, que corria com o executor multi-thread.
        Transitório (nunca entra no desejado); False se o MAC não casa (o chamador decide o fallback
        broadcast).
        """
        alvo = self._key_to_uniq(uniq)
        if alvo is None:
            return False
        with self._io_lock:
            key = self._key_for_uniq(alvo)
            handle = self._handles.get(key) if key is not None else None
        if handle is None:
            return False
        try:
            handle.setLeftMotor(strong)
            handle.setRightMotor(weak)
        except Exception as exc:
            logger.warning("output_handle_failed", op="set_rumble_for", key=key, err=str(exc))
        return True


    def set_haptica_de_audio_for(self, uniq: str, ativa: bool) -> bool:
        """A háptica por áudio tocando (ou não) no controle de MAC `uniq`
        (A-VIBRACAO-NAO-DESLIGA-A-HAPTICA-01).

        Vale nos dois transportes; guarda no mapa por MAC, e o handle novo recebe em
        :meth:`_reapply_desired`. False se o MAC não casa.
        """
        alvo = self._key_to_uniq(uniq)
        if alvo is None:
            return False
        with self._io_lock:
            mudou = (alvo in self._haptica_de_audio_por_uniq) is not bool(ativa)
            if ativa:
                self._haptica_de_audio_por_uniq.add(alvo)
            else:
                self._haptica_de_audio_por_uniq.discard(alvo)
            key = self._key_for_uniq(alvo)
            handle = self._handles.get(key) if key is not None else None
        if mudou:
            # OS-QUATRO-EM-HARMONIA-01, item 6: a borda do `HAPTICS_SELECT`, por controle.
            # Com a háptica por áudio tocando, o rumble deste controle sai SEM ele.
            logger.info(
                "haptics_select_borda",
                uniq=alvo,
                haptica_de_audio=bool(ativa),
                haptics_select="fora" if ativa else "com_o_rumble",
            )
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
            # O jogo manda no gatilho (decisão de 03/10/2026, revoga PERFIL-MANDA-01), mas o «sem
            # efeito» de quem nunca mandou efeito é ausência: o perfil vale até o jogo provar
            # (04/10/2026).
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
            self._devolver_os_gatilhos(
                handle, key, desired, triggers, what="end_game_session_trigger"
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

    def _devolver_os_gatilhos(
        self,
        handle: pydualsense,
        key: str | None,
        desired: _DesiredOutput,
        lados: Iterable[str],
        *,
        what: str,
    ) -> None:
        """Tira o bloco do jogo dos `lados` do handle e devolve o efeito do perfil (ou Off)."""
        campos: dict[str, tuple[Side, str, str]] = {
            "left": ("left", "trigger_left", "_raw_trigger_left"),
            "right": ("right", "trigger_right", "_raw_trigger_right"),
        }
        for lado in lados:
            side, campo, atributo = campos[lado]
            with contextlib.suppress(Exception):
                setattr(handle, atributo, None)
            effect = getattr(desired, campo)
            try:
                if effect is not None:
                    self._apply_trigger(handle, side, effect)
                else:
                    self._reset_trigger(handle, side)
            except Exception as exc:
                logger.warning("output_handle_failed", op=what, key=key, err=str(exc))

    def soltar_o_gatilho_do_jogo_for(self, uniq: str, side: Side, bloco: bytes) -> bool:
        """Solta o lado `side` da camada do jogo de `uniq` se ele ainda é o `bloco` dado; devolve se
        soltou.

        Volta de quem pintou só o gatilho (servidor DSX): a luz e o outro lado ficam. Se outro dono
        repintou o lado, nada sai.
        """
        alvo = self._key_to_uniq(uniq)
        if alvo is None:
            return False
        lado = "left" if side == "left" else "right"
        with self._io_lock:
            do_jogo = self._game_triggers_by_uniq.get(alvo)
            if do_jogo is None or do_jogo.get(lado) != bytes(bloco):
                return False
            del do_jogo[lado]
            if not do_jogo:
                self._game_triggers_by_uniq.pop(alvo, None)
                self._jogo_provou_o_gatilho.discard(alvo)
            key = self._key_for_uniq(alvo)
            handle = self._handles.get(key) if key is not None else None
            desired = self._merged_desired_for_key(key) if key is not None else None
        logger.info("game_trigger_solto", uniq=alvo, lado=lado)
        if handle is not None and desired is not None:
            self._devolver_os_gatilhos(
                handle, key, desired, (lado,), what="soltar_o_gatilho_do_jogo"
            )
        return True

    def uniqs_do_destino(self) -> list[str]:
        """Os MACs que uma escrita sem endereço alcança agora: o do destino da aba Conexões
        (presente ou guardado) ou, em «Todos», o de cada controle aberto; handle sem MAC estável não
        entra.
        """
        with self._io_lock:
            _alvo, handles, ausente = _resolver_escopo(
                self._handles, self._output_target_key, broadcast=False
            )
        if ausente is not None:
            uniq = self._key_to_uniq(ausente)
            return [uniq] if uniq is not None else []
        destinos: list[str] = []
        for key, _handle in handles:
            uniq = self._key_to_uniq(key)
            if uniq is not None and uniq not in destinos:
                destinos.append(uniq)
        return destinos

    @staticmethod
    def _reset_trigger(handle: pydualsense, side: Side) -> None:
        """Volta um gatilho a Off (sem efeito) — o estado de fábrica do firmware."""
        from pydualsense.enums import TriggerModes

        trigger = handle.triggerL if side == "left" else handle.triggerR
        trigger.mode = TriggerModes.Off
        for idx in range(7):
            trigger.setForce(idx, 0)
        _acordar_a_volta_de(handle)

    def resolved_player_leds_for(
        self, uniq: str, *, incluir_coop: bool = False
    ) -> tuple[bool, bool, bool, bool, bool] | None:
        """Padrão de player-LED RESOLVIDO do controle `uniq` (leitura pura).

        `incluir_coop` soma a camada do co-op: é o que o controle MOSTRA, e o que o medidor do
        gesto devolve quando fecha.
        """
        with self._io_lock:
            return self._merged_desired_for_key(uniq, incluir_coop=incluir_coop).player_leds

    def resolved_led_for(self, uniq: str) -> tuple[int, int, int] | None:
        """Cor de lightbar RESOLVIDA do controle `uniq` (leitura pura; None = ninguém setou cor
        ainda).

        STATUS-01/COR-05: o MERGE POR CAMPO pelo mesmo resolvedor dos reasserts; fonte do
        `lightbar_source == "desired"` quando o nó sysfs não é gravável. O valor é PÓS-escala de
        brilho (D8: a cor pré-brilho exigiria refatorar o desejado; o contraste do traço se ajusta
        na borda da GUI).
        """
        with self._io_lock:
            return self._merged_desired_for_key(uniq).led


    def bordas_do_mic(self) -> dict[str, tuple[int, bool, float | None, bool]]:
        """Contador de APERTOS do botão do microfone, por `uniq`: `{uniq: (seq, mudo, quando,
        em_voo)}`.

        `seq` sobe quando o DEDO desce (O-BOTAO-DO-MIC-SO-OBEDECE-A-MAO-01); `mudo` é o que o último
        aperto PEDE; `quando` é o `time.monotonic()`; `em_voo` avisa que uma escrita nossa ainda não
        confirmou no bit (O-ECO-DO-ATO-SEM-OBJETO-01). Único lugar que vê todo report de todo
        controle COM identidade (`BUTTON_DOWN` não carrega `uniq` e `read_state()` só vê o
        primário); sem `uniq` resolvível fica de fora. O mapa da posse solta junto, por
        `_levar_ao_mapa_a_posse_que_a_mao_soltou`.
        """
        with self._io_lock:
            items = list(self._handles.items())
        out: dict[str, tuple[int, bool, float | None, bool]] = {}
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
            em_voo = bool(getattr(handle, "_mic_mudo_em_voo", False))
            out[uniq] = (seq, mudo, quando if isinstance(quando, float) else None, em_voo)
        return out

    def _levar_ao_mapa_a_posse_que_a_mao_soltou(self, key: str, handle: Any) -> None:
        """Leva ao mapa por-uniq a posse do mudo que o aperto soltou no handle
        (O-BOTAO-DO-MIC-SO-OBEDECE-A-MAO-01).

        Consome a marca `_mic_posse_solta_pela_mao` e é chamada de todo lugar que lê o mapa ou perde
        o handle (bordas, quem manda, saída do handle): o laço das bordas sozinho não bastava, o
        handle que sai leva a marca. Só solta se ninguém retomou a posse depois do aperto.
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
        """Descreve cada controle conectado (IPC `controller.list`): `{index, connected, transport,
        is_primary, uniq, battery_pct, battery_state, firmware, edge}`.

        `index` é a POSIÇÃO em `list(self._handles)` (0 = primário), o número do seletor
        (FEAT-DSX-CONTROLLER-SELECTOR-01); `uniq` é o MAC normalizado e `battery_pct` a bateria por
        controle (None sem dado; FEAT-STATE-PER-CONTROLLER-01). Sem nenhum conectado, devolve uma
        entrada offline (contrato "ao menos um item").
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
                    **self._carga(handle, connected), **self._o_firmware_de(key, handle),
                }
            )
        return out

    @staticmethod
    def _key_to_uniq(key: str) -> str | None:
        """MAC normalizado da key de um handle, ou None quando a key é um path
        (FEAT-STATE-PER-CONTROLLER-01).

        Guarda de 12 dígitos hex: o path "/dev/hidrawN" viraria um pseudo-MAC ("deda4") no card da
        GUI.
        """
        from hefesto_dualsense4unix.core.sysfs_leds import norm_mac

        normalized = norm_mac(key)
        if normalized is None or len(normalized) != 12:
            return None
        return normalized

    def _carga(self, handle: pydualsense, connected: bool) -> dict[str, object]:
        """As DUAS metades da bateria de um handle, num par que não se separa (BATERIA-PARADA-01
        B1).

        `battery_pct` e `battery_state` vêm do MESMO byte (`states[53]`: nibble baixo = nível, alto
        = carga). Desconectado devolve os dois `None`.
        """
        if not connected:
            return {"battery_pct": None, "battery_state": None}
        return {
            "battery_pct": self._read_battery_opt(handle),
            "battery_state": self._read_battery_state_opt(handle),
        }

    def reassert_resolved_outputs(self, *, verify: bool = False) -> None:
        """Re-aplica o desired RESOLVIDO de cada controle, pela rota que o alcança; percorre os
        HANDLES, não os nós (sem a regra do udev nenhum nó é gravável). O que cada um recebe é do
        `_repintar_a_luz_de_um`.
        """
        with self._io_lock:
            check = verify and not self._game_wins()
            posse = set(self._sysfs_written) if check else set()
            pode_player = self._pode_escrever_player_leds()
            nos = self._sysfs if isinstance(self._sysfs, dict) else {}
            alvos = [
                (key, handle, nos.get(key), self._merged_desired_for_key(key))
                for key, handle in self._handles.items()
            ]
        for key, handle, no, desired in alvos:
            with contextlib.suppress(Exception):
                self._repintar_a_luz_de_um(
                    key,
                    handle,
                    no,
                    desired,
                    pode_player=pode_player,
                    what="reassert_resolved_outputs",
                    verify=check and key in posse,
                )

    def defend_display(self) -> None:
        """Defesa de exibição: invalida os caches sysfs + reassert verificado."""
        with self._io_lock:
            self._defend_last_at = time.monotonic()
            nodes = list(self._sysfs.values())
            handles = list(self._handles.values())
        for node in nodes:
            with contextlib.suppress(Exception):
                node.invalidate_cache()
        for handle in handles:
            with contextlib.suppress(Exception):
                handle._quadro_da_luz = None
                handle._brilho_do_cabo = None
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
                        handle._quadro_da_luz = None
            pode_player = self._pode_escrever_player_leds()
            nos = self._sysfs if isinstance(self._sysfs, dict) else {}
            reasserts = (
                [
                    (key, handle, nos.get(key), self._merged_desired_for_key(key))
                    for key, handle in self._handles.items()
                ]
                if not muted
                else []
            )
        for key, handle, no, desired in reasserts:
            with contextlib.suppress(Exception):
                self._repintar_a_luz_de_um(
                    key,
                    handle,
                    no,
                    desired,
                    pode_player=pode_player,
                    what="set_output_mute",
                )
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
        """Bateria 0-100 de UM handle, ou None se indisponível (BATERIA-QUE-PULA-01, 16/09/2026).

        Só getattrs no `DSBattery` (sem HID I/O; seguro fora do `_io_lock`). `Level` nasce 0, então
        0 é «ninguém reportou»: devolve None, nunca «0%» na reconexão (um DualSense real reporta ao
        menos 5). `_read_battery_raw` segue convertendo None em 0 (contrato legado de
        `core/controller.py`); quem quer saber se HÁ dado pergunta aqui.
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
        """O MAC do dono do posto de P1: o primário, ou quem a vaga espera (o que o `primary_uniq`
        responde).

        Durante a vaga o vpad do P1 segue sendo DO P1: rumble e cor do jogo miram o P1 ausente e são
        descartados com log (BROADCAST-PROIBIDO-01); a máscara segue com ele e o co-op não o senta
        como secundário.
        """
        chave = self._primary_key or self._posto_vago_de
        return self._key_to_uniq(chave) if chave else None

    def _quem_senta_no_posto(self, sentado: str | None = None) -> str | None:
        """Quem ocupa o posto de P1 que ficou vazio — ou None, se ele ESPERA. Chamado pelo
        `_recompute_primary`, sob o `_io_lock`.

        Com o primário `sentado`, a pergunta é se a carta menor chegou (`_a_carta_menor_locked`,
        O-MODO-XBOX-NAO-E-QUEDA-02 item 4); com o posto vazio, senta quem tem a carta menor.
        `D-2409-O-JOGO-ESPERA-O-LUGAR-GUARDADO`: o posto fica VAGO (vpad do P1 de pé e parado)
        quando a reserva do posto (`_primario_deposto`, `PRIMARIO_RESERVA_SEC`, `relogio_do_prazo`)
        e a pergunta pendurada (`set_espera_do_posto`: co-op, jogo com a autoridade e lugar
        guardado) dizem sim. Sem handle nenhum não há vaga.
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

    #: A última carga lida do dono do posto de P1, `(battery_pct, battery_state)`.
    _carga_do_posto: tuple[int, str | None] = (0, None)

    def _ler_a_carga_do_posto(self, ds: pydualsense) -> tuple[int, str | None]:
        """A carga do primário, lida no tique do `read_state` e guardada para a vaga
        (BATERIA-PARADA-01); `battery_pct` sempre `int`, 0 enquanto não reportou.
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
        """A carta de cada key de `chaves` — vazio quando a mesa não tem carta.

        Com lâmpada acesa para todos, a lâmpada é a carta. Sem ela para todos,
        a carta de TODOS é a mesa que vai sentar (``numeros_ao_sentar`` do
        registro, o dono do número que a lâmpada acende no tique seguinte);
        sem a resposta dele, quem não tem lâmpada fica DEPOIS de quem tem, na
        ordem da fila. O porquê (OS-QUATRO-EM-HARMONIA-01 e a MAC-DA-VOLTA):
        docs/research/o-porque-dos-modulos.md, «A carta de quem não tem lâmpada».
        """
        uniqs = {k: self._key_to_uniq(k) for k in chaves}
        lampadas = {k: self._numero_do_slot(u) for k, u in uniqs.items()}
        acesas = {k: n for k, n in lampadas.items() if n is not None}
        if chaves and len(acesas) == len(chaves):
            return acesas
        vai_sentar = self._mesa_que_vai_sentar(uniqs)
        if chaves and len(vai_sentar) == len(chaves):
            return vai_sentar
        consulta = getattr(self._auto_output_provider, "posto_na_fila", None)
        if not callable(consulta):
            return self._depois_das_acesas(chaves, acesas, {})
        postos: dict[str, int | None] = {}
        for chave, uniq in uniqs.items():
            posto: int | None = None
            if uniq is not None:
                with contextlib.suppress(Exception):
                    bruto = consulta(uniq)
                    if isinstance(bruto, int) and not isinstance(bruto, bool):
                        posto = bruto
            postos[chave] = posto
        if acesas:
            return self._depois_das_acesas(chaves, acesas, postos)
        conhecidos = [p for p in postos.values() if p is not None]
        if not conhecidos:
            return {}
        fim = max(conhecidos) + 1
        return {k: (p if p is not None else fim) for k, p in postos.items()}

    def _mesa_que_vai_sentar(self, uniqs: dict[str, str | None]) -> dict[str, int]:
        """Key -> o número de quando todos estiverem na mesa; vazio sem a resposta do registro."""
        consulta = getattr(self._auto_output_provider, "numeros_ao_sentar", None)
        if not callable(consulta):
            return {}
        bruto = consulta([u for u in uniqs.values() if u is not None])
        if not isinstance(bruto, dict):
            return {}
        return {
            k: n
            for k, u in uniqs.items()
            if u is not None and isinstance(n := bruto.get(u), int) and not isinstance(n, bool)
        }

    @staticmethod
    def _depois_das_acesas(
        chaves: list[str], acesas: dict[str, int], postos: dict[str, int | None]
    ) -> dict[str, int]:
        """As lâmpadas acesas ficam; quem não tem lâmpada vem depois, na ordem da fila."""
        if not acesas:
            return {}
        faltam = [k for k in chaves if k not in acesas]
        na_fila = sorted(
            faltam,
            key=lambda k: (postos.get(k) is None, postos.get(k) or 0, faltam.index(k)),
        )
        fim = max(acesas.values()) + 1
        return {**acesas, **{k: fim + i for i, k in enumerate(na_fila)}}

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

    def _o_firmware_de(self, key: str, handle: object) -> dict[str, object]:
        """`{firmware, edge}` de um controle, para o `controller.list` (e o doctor).

        `firmware` é o `update_version` que a conexão leu (None antes disso). Lê um dict que só a
        conexão escreve, sem o `_io_lock` que a leitura da feature segura: o tique de estado não
        espera por ela.
        """
        uniq = self._key_to_uniq(key)
        return {
            "firmware": self._firmware_por_uniq.get(uniq) if uniq is not None else None,
            "edge": bool(getattr(handle, "is_edge", False)),
        }

    def pintar_a_barra_sem_lembrar(self, uniq: str, rgb: tuple[int, int, int]) -> bool:
        """Pinta `rgb` na barra SÓ do controle `uniq`, SEM tocar no estado desejado.

        É o quadro do efeito da luz (`luz_animada`): o desejado continua o do perfil, o do gesto
        e o do jogo, e o `reassert_resolved_outputs` devolve a barra a ele quando o efeito para.
        Devolve se o quadro saiu.
        """
        alvo = self._key_to_uniq(uniq)
        if alvo is None:
            return False
        with self._io_lock:
            key = self._key_for_uniq(alvo)
            handle = self._handles.get(key) if key is not None else None
            node = self._sysfs.get(key) if key is not None else None
        if handle is None:
            return False
        return self._write_partial_output(
            handle, node, _DesiredOutput(led=rgb), what="efeito_da_luz"
        )

    def pintar_as_luzinhas_sem_lembrar(
        self, uniq: str, bits: tuple[bool, bool, bool, bool, bool], degrau: int
    ) -> bool:
        """Acende `bits` nas luzinhas de número SÓ do controle `uniq`, SEM tocar no desejado.

        É o quadro do medidor do gesto (`volta_dos_acessorios`), irmão de
        `pintar_a_barra_sem_lembrar`: o número do jogador (o do perfil, o da troca automática e o
        do co-op) continua no desejado, e o próximo aplicar o devolve. Devolve se o quadro saiu.
        """
        alvo = self._key_to_uniq(uniq)
        if alvo is None:
            return False
        with self._io_lock:
            key = self._key_for_uniq(alvo)
            handle = self._handles.get(key) if key is not None else None
            node = self._sysfs.get(key) if key is not None else None
        if handle is None:
            return False
        return self._write_partial_output(
            handle, node,
            _DesiredOutput(player_leds=tuple(bits), player_led_brightness=degrau),  # type: ignore[arg-type]
            what="medidor_das_luzinhas",
        )

    #: Quantas vezes a luz RESOLVIDA foi repintada (``_repintar_a_luz_de_um``). Default de CLASSE,
    #: como os de cima: o dublê feito por ``__new__`` também conta.
    _repinturas_da_luz: int = 0

    @property
    def repinturas_da_luz(self) -> int:
        """O contador das repinturas da luz resolvida; só sobe, e o ``luz_animada`` o lê."""
        return self._repinturas_da_luz

    def desligar_o_controle(self, uniq: str) -> bool:
        """Desliga UM controle, pelo endereço dele, sem tocar nos outros do mesmo adaptador.

        O-CONTROLE-SE-DESLIGA-PELO-BOTAO-PELO-GESTO-E-PELA-OCIOSIDADE-01: o SET_FEATURE `0x08`
        («Set Bluetooth Control», 47 B, `buf[1] = 2`) sai no hidraw DESTE controle, assinado com a
        semente de escrita `0x53`. Só pelo rádio: no cabo a energia vem do fio e o efeito do `0x08`
        não foi medido, então o verbo recusa sem escrever. Devolve se o pedido saiu inteiro.
        """
        mascarado = _endereco_mascarado(uniq)
        with self._io_lock:
            key = self._key_for_uniq(uniq)
            handle = self._handles.get(key) if key is not None else None
            caminho = getattr(handle, "_pinned_path", None)
            if handle is None or not isinstance(caminho, bytes):
                logger.info("controle_desligar_recusado", uniq=mascarado, motivo="sem_controle")
                return False
            if self._detect_transport(handle) != "bt":
                logger.info("controle_desligar_recusado", uniq=mascarado, motivo="cabo")
                return False
            pedido = pedido_de_desligar()
            try:
                escritos = _write_feature_via_hidraw(
                    caminho.decode("utf-8", "replace"), pedido, opener=self._feature_opener
                )
            except OSError as exc:
                logger.warning("controle_desligar_falhou", uniq=mascarado, err=str(exc))
                return False
        logger.info("controle_desligado", uniq=mascarado, escritos=escritos)
        return escritos == len(pedido)

    # --- A intensidade (A-INTENSIDADE-DA-VIBRACAO-E-DO-GATILHO-SAI-DO-FIRMWARE-COMO-NO-PS5-01) ---
    # Os métodos moram no fim da classe de propósito: as citações `arquivo:linha` do meio do
    # arquivo continuam abrindo no que prometem.

    def set_trigger_scales(self, scales: Mapping[str, float] | None = None) -> None:
        """SUBSTITUI o mapa da «Intensidade do gatilho» por-uniq (1,0 = 100% do trilho).

        Abaixo de 100% vira o nibble alto do `common[36]`; acima, o reforço das forças do bloco
        (`_forca_do_gatilho`). Irmão de :meth:`set_rumble_scales`; ausente = 100%.
        """
        novo: dict[str, float] = {}
        for uniq, fator in (scales or {}).items():
            alvo = self._key_to_uniq(uniq)
            if alvo is None:
                logger.warning("escala_do_gatilho_sem_mac_ignorada", uniq=uniq)
                continue
            novo[alvo] = max(0.0, float(fator))
        with self._io_lock:
            self._trigger_scale_by_uniq: dict[str, float] = novo
            self._empurrar_as_intensidades()

    def escala_do_gatilho_de(self, uniq: str) -> float | None:
        """A «Intensidade do gatilho» da peça ``uniq``, ou ``None`` (100%)."""
        alvo = self._key_to_uniq(uniq)
        mapa = getattr(self, "_trigger_scale_by_uniq", None) or {}
        return mapa.get(alvo) if alvo is not None else None

    def _trocar_o_mapa_das_intensidades(self, nome: str, novo: dict[str, float]) -> None:
        """Troca o mapa ``nome`` (vibração ou gatilho) e põe a escala nova em cada handle."""
        with self._io_lock:
            setattr(self, nome, novo)
            self._empurrar_as_intensidades()

    def _reaplicar_com_as_intensidades(self, key: str, handle: Any) -> None:
        """O handle novo nasce com a intensidade do controle dele, antes do `_reapply_desired`."""
        self._empurrar_as_intensidades(so=key)
        self._reapply_desired(key, handle)

    def _empurrar_as_intensidades(self, so: str | None = None) -> None:
        """Põe em cada handle (ou só no ``so``) a escala da vibração e a do gatilho dele.

        A da vibração é o fator do mapa de :meth:`set_rumble_scales`, o MESMO que o funil já pôs no
        byte do motor: o firmware só tira o que o software já tirou, e o resto nunca satura. A
        volta lê as duas no `_build_common`, nos dois transportes e nos quatro controles.
        """
        with self._io_lock:
            handles = getattr(self, "_handles", None) or {}
            alvos = [(k, h) for k, h in handles.items() if so is None or k == so]
            vibracao = dict(getattr(self, "_rumble_scale_by_uniq", None) or {})
            gatilho = dict(getattr(self, "_trigger_scale_by_uniq", None) or {})
        for key, handle in alvos:
            uniq = self._key_to_uniq(key)
            escala_vib = vibracao.get(uniq, 1.0) if uniq is not None else 1.0
            escala_gat = gatilho.get(uniq, 1.0) if uniq is not None else 1.0
            with contextlib.suppress(Exception):
                if getattr(handle, "_escala_da_vibracao", 1.0) != escala_vib:
                    handle._escala_da_vibracao = escala_vib
                if getattr(handle, "_escala_do_gatilho", 1.0) != escala_gat:
                    handle._escala_do_gatilho = escala_gat


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

    Posto de primário (`PyDualSenseController._relogio`) e lugar guardado
    (`identity.relogio_do_lugar_guardado`) perguntam AQUI, para os dois prazos vencerem juntos
    depois de uma suspensão.
    """
    return time.clock_gettime(_RELOGIO_DOS_PRAZOS)


PRAZO_DA_TROCA_DE_TRANSPORTE_S: float = PRIMARIO_RESERVA_SEC

FOLGA_DEPOIS_DA_TROCA_S: float = 10.0


def _endereco_mascarado(uniq: object) -> str | None:
    """A chave do controle na máscara da casa, para o diário (dono: `core/formas_do_endereco`);
    `None` só para o que não é texto.

    Aceita qualquer grafia (colada, sysfs), o virtual sai sem o hash; o que não é endereço passa
    pelo mesmo dono, nunca cru.
    """
    if not isinstance(uniq, str):
        return None
    return mascarar(uniq)


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


def escrever_so_a_luz_do_mic(handle: Any, *, radio: bool) -> bool:
    """Escreve o report MÍNIMO da luz do botão de mudo: o bit `0x01` do flag1 e o `common[8]`.

    É o caminho do Modo Nativo, em que o laço não escreve e a luz do microfone ficava presa no
    último valor (O-MICROFONE-GANHA-O-MODO-E-A-LUZ-QUE-PULSA-01): como o `escrever_so_o_som`, o
    resto do report sai sem autorização e o firmware conserva o que o jogo escreveu. Sem posse do
    byte (`None`) não há o que escrever. Envelope `0x02` no cabo, `0x31` no rádio, com o seq e o
    CRC do `writeReport` do handle.
    """
    nivel = getattr(handle, "_mic_led_desejado", None)
    if nivel is None:
        return False
    common = bytearray(rep.COMMON_LEN)
    common[1] = rep.VALID_FLAG1_MIC_MUTE_LED_CONTROL_ENABLE
    common[8] = int(nivel) & 0xFF
    report = rep.build_bt_report(common, seq=0) if radio else rep.build_usb_report(common)
    return _escrita_completa(handle.writeReport(list(report)), len(report))


def _no_modo_nativo(controle: Any, handle: Any) -> bool:
    """O laço de escrita está calado neste handle (Modo Nativo, FEAT-NATIVE-OUTPUT-MUTE-01)."""
    return bool(getattr(controle, "_output_mute", False) or getattr(handle, "_output_muted", False))


def _entregar_a_luz_do_mic_no_nativo(controle: Any, handle: Any) -> None:
    """Entrega a luz do microfone pelo report mínimo; levanta se o fio não a levou inteira."""
    radio = PyDualSenseController._detect_transport(handle) == "bt"
    if not escrever_so_a_luz_do_mic(handle, radio=radio):
        raise RuntimeError("a luz do microfone não saiu no report mínimo do Modo Nativo")


#: O SET_FEATURE «Set Bluetooth Control» do DualSense: 47 B, `buf[1] = 2` desliga
#: (`docs/protocol/dualsense-plataforma-e-identidade.md`, a tabela das features).
_FEATURE_DO_RADIO_ID = 0x08
_FEATURE_DO_RADIO_TAMANHO = 47
_DESLIGAR_O_RADIO = 0x02

#: Quanto tempo o PS segurado desliga o controle (ordem de 13/10/2026), e o relógio do prazo.
SEGUNDOS_DO_PS_QUE_DESLIGA: float = 10.0
_TEMPORIZADOR_DO_PS: Callable[..., Any] = threading.Timer

#: As bordas dos botões da pydualsense: apertar qualquer um com o PS seguro faz do gesto um combo
#: (os Gestos do PS da aba Navegação, e o PS com R2, L2, R1 e L1 dos acessórios, que se segura
#: além dos 10 s), e o prazo cai. Os gatilhos contam desde o primeiro degrau; as pás do Edge só
#: existem nele.
_OS_OUTROS_BOTOES = (
    "triangle_pressed", "circle_pressed", "cross_pressed", "square_pressed",
    "dpad_up", "dpad_down", "dpad_left", "dpad_right", "r1_changed", "r2_changed", "r3_changed",
    "l1_changed", "l2_changed", "l3_changed", "touch_pressed", "microphone_pressed",
    "share_pressed", "option_pressed", "l4_changed", "l5_changed", "r4_changed", "r5_changed",
)


def pedido_de_desligar() -> bytes:
    """O `0x08` com `buf[1] = 2`, assinado para o rádio pelo dono da assinatura de escrita."""
    from hefesto_dualsense4unix.integrations.cor_do_plastico import envelope_de_radio

    pedido = bytearray(_FEATURE_DO_RADIO_TAMANHO)
    pedido[0] = _FEATURE_DO_RADIO_ID
    pedido[1] = _DESLIGAR_O_RADIO
    return envelope_de_radio(bytes(pedido))


def _write_feature_via_hidraw(
    path: str, data: bytes, opener: Callable[[str], int] | None = None
) -> int:
    """SET_REPORT de feature (HIDIOCSFEATURE) num fd efêmero; irmã de `_read_feature_via_hidraw`."""
    fd = opener(path) if opener is not None else os.open(path, os.O_RDWR)
    try:
        buf = bytearray(data)
        request = (3 << 30) | (len(buf) << 16) | (ord("H") << 8) | 0x06
        return int(fcntl.ioctl(fd, request, buf, True))
    finally:
        os.close(fd)


class _VigiaDoPs:
    """Segurar o PS SOZINHO por 10 s desliga ESTE controle; soltar antes, ou apertar outro botão
    junto, cancela.

    Assina a borda `ps_pressed` da pydualsense, que dispara no `readInput` de todo handle, em todo
    modo e nos dois transportes. O prazo corre num `threading.Timer` próprio, fora da thread de
    report; ao vencer, só desliga se o handle ainda é o do controle (o controle que caiu e voltou
    no meio não herda o gesto).
    """

    def __init__(self, controle: PyDualSenseController, key: str, handle: Any) -> None:
        self._controle = controle
        self._key = key
        self._handle = handle
        self._lock = threading.Lock()
        self._prazo: Any = None

    def borda(self, apertado: object) -> None:
        with self._lock:
            if self._prazo is not None:
                self._prazo.cancel()
                self._prazo = None
            if apertado:
                prazo = _TEMPORIZADOR_DO_PS(SEGUNDOS_DO_PS_QUE_DESLIGA, self._disparar)
                prazo.daemon = True
                prazo.start()
                self._prazo = prazo

    def outro_botao(self, apertado: object) -> None:
        if apertado:
            with self._lock:
                if self._prazo is not None:
                    self._prazo.cancel()
                    self._prazo = None

    def _disparar(self) -> None:
        with self._lock:
            self._prazo = None
        uniq = PyDualSenseController._key_to_uniq(self._key)
        with self._controle._io_lock:
            vivo = self._controle._handles.get(self._key) is self._handle
        if not vivo or uniq is None:
            logger.info("controle_desligar_pelo_ps_sem_alvo", vivo=vivo)
            return
        logger.info("controle_desligar_pelo_ps", uniq=_endereco_mascarado(uniq))
        self._controle.desligar_o_controle(uniq)


def _vigiar_o_ps_segurado(controle: PyDualSenseController, key: str, handle: Any) -> None:
    """Na adoção do handle: assina a borda do PS, e a dos outros botões, uma vez por handle."""
    evento: Any = getattr(handle, "ps_pressed", None)
    if not getattr(evento, "available", False) or getattr(handle, "_vigia_do_ps", None):
        return
    vigia = _VigiaDoPs(controle, key, handle)
    handle._vigia_do_ps = vigia
    evento += vigia.borda
    for nome in _OS_OUTROS_BOTOES:
        outro: Any = getattr(handle, nome, None)
        if getattr(outro, "available", False):
            outro += vigia.outro_botao


def microfone_chega_sem_ponte(transporte: object) -> bool:
    """O microfone deste transporte captura sem ponte: no cabo o canal já existe; no rádio ele só
    captura com a ponte de pé, e abrir a ponte põe o áudio do controle no adaptador.

    O ramo por transporte mora aqui, no dono do eixo (`docs/data/donos-de-comportamento.csv`,
    `eixo.transporte/backend`); a luz do microfone pergunta. Transporte desconhecido conta como
    rádio: na dúvida, não se abre nada.
    """
    return transporte == "usb"


# --- A intensidade no report (A-INTENSIDADE-DA-VIBRACAO-E-DO-GATILHO-SAI-DO-FIRMWARE-...-01)
# Funções do handle chamadas pelo `_build_common`, no fim do arquivo pelo mesmo motivo dos métodos
# do controlador. A «Força da vibração» e a «Intensidade do gatilho» do controle chegam ao handle
# como `_escala_da_vibracao` e `_escala_do_gatilho` (1,0 = 100%, ausente = 100%). Abaixo de 100% o
# `common[36]` leva os passos de 12,5% do firmware, com o flag1 `0x40` em todo report enquanto
# houver redução e no primeiro depois que ela some (`_reducao_escrita`); o motor e o gatilho levam
# só o resto (`rep.resto_do_software`). Com a força cheia o report é o de antes, byte a byte.


def _reducao_do_handle(handle: Any) -> int:
    """O `common[36]` que a escala de agora do ``handle`` pede."""
    return rep.byte_de_reducao(
        getattr(handle, "_escala_da_vibracao", 1.0), getattr(handle, "_escala_do_gatilho", 1.0)
    )


def _a_reducao_pede_o_bit(handle: Any) -> bool:
    """Sem vibração nossa, o `0x40` só sai se há redução ou se a última escrita ainda a carrega."""
    return bool(_reducao_do_handle(handle) or getattr(handle, "_reducao_escrita", 0))


def _carimbar_a_reducao(handle: Any, common: bytearray, flag1: int) -> int:
    """Escreve o `common[36]` quando o flag1 leva o `0x40`, e lembra o que saiu; devolve o flag1."""
    if flag1 & rep.VALID_FLAG1_MOTOR_POWER:
        reducao = _reducao_do_handle(handle)
        common[rep.COMMON_REDUCE_MOTOR_POWER] = reducao
        if getattr(handle, "_reducao_escrita", 0) != reducao:
            handle._reducao_escrita = reducao
    return flag1


def _motor_com_a_reducao(handle: Any, motor: Any) -> int:
    """O byte do motor já chega com a força do controle (o funil `forca_do_controle`); o firmware
    tira os passos dele, e o byte leva o que falta, com o teto de 255."""
    passos = _reducao_do_handle(handle) & rep.REDUCAO_DA_VIBRACAO_MASK
    valor: int = int(motor) & 0xFF
    if not passos:
        return valor
    return min(255, round(valor / rep.fracao_do_firmware(passos)))


def _forca_do_gatilho(handle: Any, bloco: bytes | bytearray | list[int]) -> bytes:
    """O bloco do gatilho (do jogo ou do Hefesto) com o resto da intensidade que o firmware não
    cobre: a sobra abaixo de 100% e o reforço acima, até a força 8 do efeito."""
    escala = getattr(handle, "_escala_do_gatilho", 1.0)
    return rep.escalar_o_bloco_do_gatilho(bytes(bloco), rep.resto_do_software(escala))
