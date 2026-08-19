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
import threading
import time
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, Any

from pydualsense import pydualsense

# SOM-ROTA-01: import no TOPO, e não tardio como as três ocorrências dentro de
# funções deste arquivo. O `ds_output_report` só importa `zlib` — não há ciclo
# a evitar, e os tetos de volume precisam ser resolvidos em tempo de módulo.
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

# SOM-SEMPRE-01: a régua ÚNICA de volume, no topo pela mesma razão do
# `ds_output_report` logo acima — o default de adoção precisa ser resolvido em
# tempo de módulo, e `core/speaker_scale.py` é Python puro (nenhum `gi`,
# nenhum daemon, nenhum ciclo possível).
from hefesto_dualsense4unix.core.speaker_scale import volume_do_percentual

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping

from hefesto_dualsense4unix.utils.logging_config import get_logger

logger = get_logger(__name__)

#: PID do DualSense Edge (os demais PIDs em `DUALSENSE_PIDS` são o DualSense
#: comum). Usado para sinalizar `is_edge` ao abrir o handle.
DUALSENSE_EDGE_PID = 0x0DF2

#: STATUS-01 (priming): azul-default que o `hid_playstation` acende no probe
#: por um caminho interno que NUNCA atualiza a classe LED (`dualsense_create`
#: → `dualsense_set_lightbar`, provado no kernel upstream). Escrever ESTE RGB
#: via sysfs num nó recém-surgido é idempotente com o hardware (a lightbar já
#: está azul) e serve só para a classe LED convergir com a realidade — sem
#: isso, todo reconnect BT/hotplug leria `0 0 0` com o LED visivelmente aceso.
KERNEL_DEFAULT_BLUE: tuple[int, int, int] = (0, 0, 128)

#: AVISO-DE-MODO-01: a piscada do aviso de modo. Ela pediu "pisca 3 vezes
#: rápido", e "rápido" é palavra DELA — quem escreveu o primeiro número chutou.
#:
#: ESCOLHA DELA, 19/08/2026: 0,15 s aceso e 0,12 s apagado, três vezes — 0,81 s
#: no total. Ela viu as três opções (0,33 s / 0,48 s / 0,81 s) e escolheu a mais
#: LENTA, com o preço na mesa: é quase um segundo de luz piscando no canto do
#: olho durante uma partida. O que ela comprou com isso: dá para CONTAR as três
#: e para LER a cor, que é a única coisa que o aviso tem a dizer. Um aviso que
#: pisca rápido demais vira um susto sem mensagem.
#:
#: O apagado é PRETO, não brilho zero: `luz.lightbar.brilho` tem `aciona=não`
#: nos dois transportes no mapa de canais, então mexer no `brightness` não
#: apaga nada — quem apaga é a COR.
AVISO_PISCADAS = 3
AVISO_ACESO_S = 0.15
AVISO_APAGADO_S = 0.12
AVISO_APAGADO: tuple[int, int, int] = (0, 0, 0)

#: REPLICA-03: tamanho do bloco de trigger effect que o jogo escreve no report
#: 0x02 do vpad (modo + 10 parâmetros — `rgucRightTriggerEffect[11]` do
#: DS5EffectsState_t do SDL; no kernel a área é o `reserved2` do
#: `dualsense_output_report_common`, common[10..20]/[21..31]).
GAME_TRIGGER_BLOCK_LEN = 11

#: NUMA-03: intervalo mínimo entre duas defesas de exibição disparadas por
#: réplica RETIDA (`defend_display` via `set_game_output_for` sob autoridade
#: 'daemon'). Réplica retida = prova de escritor ativo, mas a defesa reescreve
#: sysfs em todos os nós — sem o teto ela viraria o reassert incondicional que
#: causou o flash azul de 30s (GUERRA-01). A defesa por TRANSIÇÃO (*→daemon)
#: não passa por este teto: já é rate-limitada pela histerese de 30s do sinal.
DEFEND_DISPLAY_MIN_INTERVAL_S = 30.0

#: GYRO-01: feature report da calibração da IMU (`DS_FEATURE_REPORT_CALIBRATION`
#: / `_SIZE` do hid-playstation.c). Lido POR UNIDADE em `read_calibration` para
#: o vpad carimbar no blueprint — por BT os 4 últimos bytes são CRC-32 (seed
#: 0xA3) e são validados antes de aceitar.
_CALIBRATION_FEATURE_ID = 0x05
_CALIBRATION_FEATURE_SIZE = 41


def _read_feature_via_hidraw(
    path: str,
    report_id: int,
    size: int,
    opener: Callable[[str], int] | None = None,
) -> bytes:
    """GET_REPORT de feature via HIDIOCGFEATURE num fd efêmero (GYRO-01).

    Espelho do `_hidiocgfeature` de `uhid_gamepad.py` (caminho VALIDADO ao
    vivo pelo capture do blueprint) — duplicado aqui porque core/ não importa
    integrations/. Devolve o report como o kernel o entrega: ``data[0]`` é o
    report id e o payload começa em ``data[1]`` (`hidraw_get_report` +
    `hid_hw_raw_request`). Propaga OSError (EIO do BT ocioso, permissão) para
    o chamador decidir o fallback.

    S-5 (auditoria 21/07): `opener` injetável (broker-aware). Sem ele, o
    `os.open(path)` dá EACCES quando o broker ESCONDE o hidraw (0600 root) —
    e a calibração cai no canônico (DRIFT do gyro). O opener do broker serve
    um fd root via SCM_RIGHTS, que funciona com o nó escondido. None = os.open.
    """
    fd = opener(path) if opener is not None else os.open(path, os.O_RDWR)
    try:
        buf = bytearray(size)
        buf[0] = report_id
        # HIDIOCGFEATURE(len) = _IOC(READ|WRITE, 'H', 0x07, len)
        request = (3 << 30) | (size << 16) | (ord("H") << 8) | 0x07
        ret = fcntl.ioctl(fd, request, buf, True)
        return bytes(buf[:ret]) if ret > 0 else b""
    finally:
        os.close(fd)


#: Identidade do vpad no HID: phys gravado pelo blueprint (uhid_gamepad) e
#: prefixo do MAC forjado (`player_mac()` → 02:fe:00:00:00:0N).
_VPAD_PHYS = "hefesto-vpad"
_VPAD_UNIQ_PREFIX = "02fe"


def _hidraw_uevent(node: str) -> dict[str, str]:
    """Pares chave=valor do uevent do device HID pai do hidraw ({} se ilegível)."""
    try:
        with open(
            f"/sys/class/hidraw/{node}/device/uevent",
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
    if not node.startswith("hidraw"):  # path de libusb ("0001:0002:00")
        return False
    try:
        destino = os.path.realpath(f"/sys/class/hidraw/{node}/device")
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

#: Timeout para `pydualsense.init()` em segundos
#: (BUG-BACKEND-PYDUALSENSE-DSTATE-01). A chamada faz HID I/O sync via libhidapi
#: e, em certos estados degenerados do USB (driver kernel hid_playstation
#: contendendo o device, hidraw com handle órfão de daemon anterior, hub em
#: low-power-state), pode entrar em `D (disk sleep)` no kernel — nem SIGKILL
#: mata. Envolvemos em thread + futures com timeout: se passar do prazo, o
#: backend é marcado como offline-OK e a próxima tentativa do reconnect_loop
#: cobre. A thread em D-state é abandonada (vaza recurso, mas o daemon segue
#: vivo e funcional). 5s é compromisso entre cobrir o caso patológico e não
#: pesar no boot normal (`init()` saudável retorna em <300ms).
INIT_TIMEOUT_SEC: float = float(os.environ.get("HEFESTO_DUALSENSE4UNIX_INIT_TIMEOUT_SEC", "5"))

#: Throttle do report_thread da pydualsense (segundos de sleep por ciclo
#: read+write). O loop `sendReport` do upstream roda SEM pausa, na taxa do
#: controle (~250Hz-1kHz), martelando o hidraw. Com 2+ controles são 2+ threads
#: saturando o controlador USB compartilhado — e o adaptador Bluetooth vive no
#: MESMO controlador (família do storm), degradando o link BT
#: (`DualSense input CRC's check failed`) e matando o output do controle BT.
#: Como o INPUT vem do evdev (não do `read` da pydualsense), dá pra throttlar o
#: ciclo sem perder responsividade: ~125Hz de output é de sobra para
#: gatilhos/LED/rumble, e a leitura de bateria/transporte é esparsa.
#: BUG-MULTI-CONTROLLER-BT-CRC-CONTENTION-01.
REPORT_THREAD_THROTTLE_SEC: float = float(
    os.environ.get("HEFESTO_DUALSENSE4UNIX_REPORT_THROTTLE_SEC", "0.008")
)

#: Teto do throttle adaptativo por-controle (PERF-MULTI-CONTROLLER-01): com N
#: controles o throttle vira `base * N` capado aqui — 2 controles ≈ 60Hz de
#: output, 4 ≈ 30Hz. Output é LED/trigger/rumble (latência de até ~32ms é
#: imperceptível); o INPUT vem do evdev e não passa por este ciclo.
REPORT_THREAD_THROTTLE_MAX_SEC: float = 0.032

#: Keepalive do write OUT quando o report não mudou (PERF-MULTI-CONTROLLER-01):
#: o firmware retém o último estado, então reescrever um report IDÊNTICO a
#: ~100Hz só satura o barramento (2+ controles = pressão no host controller da
#: família do storm). Reescrevemos no máximo a cada 0.5s quando nada mudou —
#: cobre perda de report e glitch de link sem martelar o USB.
OUT_REPORT_KEEPALIVE_SEC: float = 0.5

#: RUMBLE-SEM-DONO-01 (11/08/2026): por quanto tempo, DEPOIS de uma mudança
#: real, o keepalive continua reconfirmando o MESMO report quando o rumble não é
#: nosso. Ver o bloco de comentário em `sendReport`: o keepalive perpétuo apaga o
#: motor de outro dono a cada `OUT_REPORT_KEEPALIVE_SEC`, e o que ele realmente
#: cura — *"perda de report e glitch de link"*, a linha acima, escrita em
#: PERF-MULTI-CONTROLLER-01 — é a MUDANÇA que não chegou, coisa que quatro
#: repetições resolvem e repetição eterna não melhora. Dois segundos são ~4
#: reconfirmações a 0,5 s: folga de sobra para um glitch de link, e teto do
#: estrago quando alguém está vibrando por fora.
OUT_REPORT_KEEPALIVE_CONFIRMACAO_SEC: float = 2.0

#: LACO-DE-ESCRITA-02 (15/08/2026): por quanto tempo a ENTRADA de um controle
#: pode ficar muda antes de virar UMA linha de aviso no journal. O handle é
#: aberto sem `blocking=True`, então `hidapi.Device.read` devolve `None` na hora
#: quando não há dado — e isso NÃO é erro, é o contrato da leitura
#: não-bloqueante. Mas a fila do `hidraw` vive cheia (o laço consome ~31
#: reports/s de um fluxo de 200-360/s com a mesa cheia), então para o `read`
#: devolver `None` o aparelho precisa ter parado por tempo suficiente para
#: drenar a fila inteira — ordem de segundos. Um segundo já é MUITO acima do
#: normal e ainda assim rende, no máximo, uma linha por episódio.
LEITURA_VAZIA_AVISO_SEC: float = 1.0

# QUEDA-QUE-PENDURA-01: teto do join da report_thread no `close()`. Meio
# segundo é uma eternidade para um laço que gira a ~100 Hz e ainda assim
# é imperceptível no desligamento — contra os 90 s do SIGKILL do systemd.
CLOSE_JOIN_TIMEOUT_SEC = 0.5

#: AUDIO-STATUS-01: índice do byte de estado de áudio dentro do `states`
#: NORMALIZADO da pydualsense (o mesmo em USB e BT — ver
#: `_PinnedPyDualSense._captura_status_audio`). Um a mais que o índice de
#: bateria que a própria pydualsense usa (`states[53]`).
_INPUT_AUDIO_STATUS_IDX = 54

#: AUDIO-OWNER-01: bit de validação (flag0) e offset no common de cada byte de
#: áudio, na ORDEM de `_PinnedPyDualSense._volumes_audio`
#: (fone, alto-falante, microfone, roteamento).
_AUDIO_FLAG0_BITS = (0x10, 0x20, 0x40, 0x80)
_AUDIO_COMMON_OFFSETS = (4, 5, 6, 7)


#: SOM-ROTA-01: os TETOS de cada um, na mesma ordem. Eles não são 255 — o fone
#: vai até 0x7F e o microfone até 0x40, e mandar mais é mandar lixo num campo
#: que o firmware interpreta. O roteamento (`common[7]`) é um byte de bits e
#: aceita a faixa inteira.
_AUDIO_TETOS = (
    rep.TETO_HEADPHONE_VOLUME,
    rep.TETO_SPEAKER_VOLUME,
    rep.TETO_MIC_VOLUME,
    0xFF,
)


#: SOM-SEMPRE-01 (16/08/2026) — o volume com que TODO controle nasce, em
#: unidades CRUAS do registrador. Decisão dela, textual: *"precisamos setar o
#: som sempre em todos os controles no 100%"*.
#:
#: **Por que ele NÃO é 255, e nem 0x64.** O número sai da régua única
#: (`core/speaker_scale.volume_do_percentual`), que é a MESMA conta da barra da
#: aba Status e do `speaker volume` da linha de comando — se este default fosse
#: um literal, a tela nasceria dizendo um número que ninguém conseguiria
#: reproduzir pelo controle deslizante, e teríamos duas contas para a mesma
#: grandeza (a classe de defeito que a SOM-03 já pagou).
#:
#: Os três candidatos e o dado que decide, medido nesta casa em 01/08 (tom de
#: 1 kHz, o microfone do próprio DualSense como instrumento):
#:
#:   * **255** — `TETO_SPEAKER_VOLUME`, e é onde "100%" cairia numa régua
#:     linear ingênua. A curva medida diz `102 -> 8759`, `128 -> 8488`,
#:     `255 -> 8793`: de 102 para cima **nada muda**. Escrever 255 é escrever
#:     um número fora da faixa que o firmware usa na prática (a documentação do
#:     report 0x02 anota `0x3D..0x64`) para obter exatamente o mesmo som;
#:   * **100 (0x64)** — o que o `hid-playstation` escreve, com o comentário
#:     *"the accepted range seems to be [0x3d..0x64]"*. É defensável, mas fica
#:     DOIS passos abaixo da saturação medida aqui e não é o topo de régua
#:     nenhuma nossa: a tela leria 97%, não 100%;
#:   * **102** — `volume_do_percentual(100)`, e é o mesmo 102 em que a curva
#:     satura. O topo da régua e o topo do som são o MESMO ponto.
#:
#: Escolhido o terceiro. Ele é o único em que a decisão dela ("100%"), o que a
#: aba Status mostra (100%) e o que o alto-falante entrega (o máximo audível)
#: são a mesma coisa — e é o único que NÃO é um número mágico, porque muda
#: sozinho se alguém repetir a medição e corrigir a borda em `speaker_scale`.
VOLUME_PADRAO_DO_SOM: int = volume_do_percentual(100)


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


@dataclass
class _DesiredOutput:
    """Último output aplicado = "perfil ativo" materializado em HID.

    PERFIL-01 (4P-01): existe um `_desired_default` (padrão broadcast) e um
    override PARCIAL por controle em `_desired_by_uniq` (keyed pelo MAC
    12-hex, estável entre USB e BT — provado ao vivo). O hotplug-in re-aplica
    o MERGE POR CAMPO dos dois no controle CERTO — nunca o de outro (era o
    bug provado: mirar o Controle 2 no seletor e replugar o Controle 1 o
    pintava com a cor do 2). O rumble é transitório (efeito de jogo, não faz
    parte de um perfil) e por isso NÃO entra aqui — não seria correto
    "ressuscitar" um rumble antigo num controle novo.
    """

    trigger_left: TriggerEffect | None = None
    trigger_right: TriggerEffect | None = None
    led: tuple[int, int, int] | None = None
    player_leds: tuple[bool, bool, bool, bool, bool] | None = None
    mic_led: bool | None = None


#: Campos de `_DesiredOutput`/`OutputSpec` — a ordem é a de aplicação no HID.
_OUTPUT_FIELDS = ("trigger_left", "trigger_right", "led", "player_leds", "mic_led")

#: R-20 (auditoria 23/07): CAMADAS do override por-uniq, com DONO declarado.
#:
#: A saída era resolvida por SUBSTITUIÇÃO: `reset_output_overrides` trocava o
#: mapa `_desired_by_uniq` INTEIRO. Como o autoswitch ativa um perfil a CADA
#: troca de janela, todo ajuste por-controle que a usuária tinha acabado de
#: fazer era apagado segundos depois (achado C5, queixa "as configs que eu faço
#: não impactam controle a controle"). Agora cada CAMPO de cada uniq tem dono:
#: a ativação de perfil substitui só o que é DELA e nunca pisa (nem apaga) o
#: campo que a usuária ajustou na mão.
#:
#: Ordem (baixa → alta): `perfil` < `usuaria`. Regra de escrita derivada dela:
#: o perfil só ocupa campo VAGO (depois de soltar o que era dele) — o que
#: sobrou com valor pertence a uma camada mais alta.
_LAYER_PROFILE = "perfil"
_LAYER_USER = "usuaria"

#: R-13 item 1 + R-20: o CO-OP fica FORA de `_desired_by_uniq`, em mapa próprio
#: (`_desired_coop_by_uniq`), acima da camada da usuária. Motivo medido: o
#: co-op é TRANSITÓRIO (publica ao ligar, revoga ao desligar) e o revert dele
#: precisa reencontrar o padrão configurado INTACTO embaixo — se ele gravasse
#: no mesmo slot, `resolved_player_leds_for` devolveria o padrão do próprio
#: co-op e o revert restauraria o número do jogador para sempre.
_COOP_LAYER_FIELDS = ("player_leds",)


def _spec_fields(spec: OutputSpec) -> dict[str, Any]:
    """Campos NÃO-None de um `OutputSpec` (o vocabulário parcial do PERFIL-01)."""
    return {
        name: getattr(spec, name)
        for name in _OUTPUT_FIELDS
        if getattr(spec, name) is not None
    }


def _merge_desired(default: _DesiredOutput, override: _DesiredOutput | None) -> _DesiredOutput:
    """MERGE POR CAMPO (PERFIL-01): campo do override quando não-None, senão o default.

    NUNCA resolução por objeto (refutada na revisão adversarial do sprint):
    um override PARCIAL (só gatilhos) precisa herdar a cor global do perfil —
    resolver por objeto aplicaria `led=None` como no-op e o controle replugado
    ficaria sem a cor broadcast.
    """
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


def _centered_stick_to_raw(value: Any) -> int:
    """Converte um eixo de stick da pydualsense (centrado em 0) para cru 0-255.

    FEAT-MOUSE-CURSOR-FEEL-01 (A6): a pydualsense 0.7.5 instalada armazena
    ``state.LX = states[1] - 128`` (range -128..127, repouso = 0). O fallback
    HID-raw fazia ``int(state.LX) & 0xFF``, que transformava repouso (cru 128 →
    LX=0) em raw 0 e drift leve (cru 125 → LX=-3) em raw 253 — o cursor "voava"
    na diagonal com o stick parado (é a memória "sticks ~253 em repouso").
    Somar 128 de volta e clampar restaura o valor cru que o resto do pipeline
    (deadzone em 128, gamepad virtual, check de neutralidade) espera.
    """
    return max(0, min(255, int(value) + 128))


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
    # `__new__` (nove arquivos em `tests/unit/`) e só preenche o que o trecho
    # sob teste usa. Um `getattr` defensivo em cada leitura resolveria, mas
    # esconderia o campo; o default de classe deixa o nome VISÍVEL aqui e faz o
    # dublê funcionar sem que ninguém precise lembrar de inicializá-lo.

    #: LACO-DE-ESCRITA-02 (15/08/2026) — serializa o fluxo de escrita DESTE
    #: handle. O default de classe é um lock COMPARTILHADO, e ele é seguro
    #: justamente porque nenhum handle de produção o usa: `__init__` dá a cada
    #: instância o seu. Se algum dia um handle de produção nascer sem `__init__`,
    #: o pior desfecho é escrita serializada demais — nunca escrita corrompida.
    _write_lock: threading.Lock = threading.Lock()

    #: LACO-DE-ESCRITA-02 — `time.monotonic()` do início do silêncio atual da
    #: entrada (`read` devolvendo `None`), ou `None` quando a entrada está
    #: falando. Ver `sendReport`.
    _leitura_vazia_desde: float | None = None

    #: LACO-DE-ESCRITA-02 — se o silêncio ATUAL já rendeu a sua linha de aviso.
    #: Um aviso por episódio, não um por ciclo.
    _leitura_vazia_avisada: bool = False

    def __init__(self, path: bytes, *, is_edge: bool) -> None:
        super().__init__()
        self._pinned_path = path
        self._pinned_is_edge = is_edge
        # LACO-DE-ESCRITA-02: o lock DESTE handle (ver `writeReport`). Por
        # instância, nunca compartilhado entre controles — um `hid_write` que
        # pendure num controle não pode calar os outros três da mesa.
        self._write_lock = threading.Lock()
        # FEAT-DSX-LIGHTBAR-SYSFS-01: quando a lightbar/player-LED deste controle
        # estão sendo controlados pela rota sysfs do kernel (cor funciona em
        # USB E BT), suprimimos a escrita desses LEDs no report_thread para NÃO
        # disputar com o kernel (a disputa é o que faz a cor "não colar" no BT).
        # `_refresh_sysfs_leds` mantém True SÓ quando o sysfs é gravável; senão
        # vira False e o caminho pydualsense segue normal.
        #
        # LIGHTBAR-BT-ADOPT-01 (provado ao vivo 2026-07-18; estudo 5 agentes):
        # nasce TRUE, nunca False. O report_thread começa a escrever assim que o
        # handle abre — ANTES de `_refresh_sysfs_leds` rodar. Nascendo False, o
        # 1º report saía com os flags de lightbar/player LIGADOS — e o report BT
        # da pydualsense 0.7.5 é MALFORMADO (layout off-by-one: [1]=0x02 fixo,
        # 0xFF onde o firmware espera o tag obrigatório 0x10, campos deslocados
        # 1 byte). Chegando dentro da JANELA da máquina de estados da lightbar
        # do firmware (~3.4s pós-connect BT — o SDL espera essa janela e fecha
        # com flag1 0x08 "Reset LED state"; o kernel nunca envia 0x08), a
        # lightbar LATCHEIA APAGADA e passa a ignorar as escritas de cor do
        # kernel (330k writes em multi_intensity sem acender, provado ao vivo) —
        # enquanto player-LEDs/gatilhos, sem máquina de estados própria, seguem
        # funcionando. O latch persiste até o POWER-OFF do controle (sobrevive a
        # re-parear e a rebind do driver; cabo USB escapa — report 0x02 sem
        # seq/janela). Sintoma: a lightbar acende no connect e APAGA na adoção.
        # Nascer suprimido fecha a janela inteira (inclusive o zumbi do
        # init-timeout, que nenhum refresh alcança); quem decide o estado final
        # continua sendo `_refresh_sysfs_leds` (~ms depois, no próprio connect).
        self._suppress_leds = True
        # PERF-MULTI-CONTROLLER-01: throttle POR-INSTÂNCIA (o backend escala
        # com o nº de controles conectados) + dirty-flag do write OUT.
        self._throttle_sec = REPORT_THREAD_THROTTLE_SEC
        self._last_out_report: list[int] | None = None
        self._last_write_at = 0.0
        # RUMBLE-SEM-DONO-01: quando o report MUDOU pela última vez. Nasce em
        # `-inf` (e não em 0.0) para que a janela de confirmação esteja FECHADA
        # antes do primeiro report — com 0.0 o relógio monotônico de uma máquina
        # recém-ligada cairia dentro da janela por acidente.
        self._last_change_at = float("-inf")
        # FEAT-NATIVE-OUTPUT-MUTE-01: em Modo Nativo o JOGO escreve no hidraw
        # (rumble/gatilhos/LED nativos); QUALQUER write nosso — até o keepalive
        # de 0.5s — pisoteia o que o jogo mandou (rumble zerado a cada meio
        # segundo, sentido ao vivo no Sackboy 2026-07-13). Mutado = zero write;
        # a leitura de input/bateria continua.
        self._output_muted = False
        # GUERRA-01 item 2 (keepalive neutro): com o upstream, TODO report sai
        # com os bits de vibração do flag0 ligados (0xFF) e motores=0 — o
        # keepalive zerava rumble de TERCEIROS (o jogo escrevendo direto no
        # hidraw do físico) a cada ≤0.5s. Agora os bits de vibração só ligam
        # quando há rumble NOSSO ativo (`_rumble_active`) ou na transição
        # ativa→0 (`_rumble_stop_pending`: UM report com flags ligados e
        # motores 0 para parar o motor de verdade; depois volta ao neutro).
        #
        # ATENÇÃO — desligar os bits NÃO BASTA, medido em 11/08/2026
        # (`keepalive-premissa-troca-de-lado`): o firmware obedece aos BYTES de
        # motor mesmo com os bits de autorização desligados. Estes dois campos
        # continuam valendo — são eles que dizem quem é o dono do rumble —, mas
        # quem protege o motor alheio é a janela de confirmação do keepalive em
        # `sendReport` (RUMBLE-SEM-DONO-01), não a neutralidade dos bits.
        self._rumble_active = False
        self._rumble_stop_pending = False
        # BTREPORT-02: contador de sequência do report 0x31 (wrap 0-15, como o
        # hid_playstation faz), carimbado por `writeReport` no momento do
        # write — nunca no prepare, senão todo report "mudaria" e o dedup
        # `_last_out_report` morreria (write a ~125Hz de volta).
        self._bt_seq = 0
        # REPLICA-03: blocos CRUS de trigger effect do JOGO (11 bytes: modo +
        # 10 parâmetros, layout do DS5EffectsState_t do SDL). Quando setados,
        # `_build_common` os embute VERBATIM em common[10..20]/[21..31] no
        # lugar do estado da pydualsense — a DSTrigger só representa 7 forças
        # e espalharia zeros nos parâmetros 8/9/10 do efeito do jogo. None =
        # posse do perfil (caminho DSTrigger histórico).
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
        # `MIC_MUTE`. Nós mandávamos `common[9]=0x00` COM o enable ligado a até
        # 60 Hz — ou seja, "desmuta" reescrito por cima da decisão do kernel a
        # cada 16 ms. É o suspeito nº 1 registrado em
        # `integrations/dualsense_bt_audio.py` (BT-MIC-GATING-01).
        # `_volumes_audio` (common[4..7], flag0 0x10..0x80): idem, mandando
        # volume ZERO em todo report. Ver `set_audio_volumes`.
        self._mic_mute_desejado: bool | None = None
        #: AUDIO-OWNER-01, o TERCEIRO campo — e o que MENTE PARA O OLHO DELA
        #: (12/08/2026). `common[8]` é o `mute_button_led` do
        #: `dualsense_output_report_common`, e o dono dele no Linux é o MESMO
        #: dono do mudo: o kernel. `assets/dkms/hid-playstation/
        #: hid-playstation.c:1538-1540` liga
        #: `VALID_FLAG1_MIC_MUTE_LED_CONTROL_ENABLE` e escreve
        #: `common->mute_button_led = ds->mic_muted` — uma vez, na BORDA do
        #: botão (`:1631-1637`).
        #:
        #: Nós autorizávamos o mesmo byte em TODO report (o `0x01` estava fixo
        #: no `flag1` do `_build_common`) escrevendo `microphone_led`, que a
        #: pydualsense inicializa em 0. Consequência lida no código e visível
        #: na mão dela: ela aperta o mudo, o kernel acende o LED e MUTA o mic
        #: no firmware, e o PRÓXIMO report nosso (≤ 0,5 s) apaga o LED sem
        #: desmutar — o mic segue mudo com a luz apagada. O produto mente
        #: sobre o estado do microfone dela.
        #:
        #: Mesma disciplina dos outros dois: `None` = não somos donos, o bit
        #: `0x01` sai APAGADO e o byte fica inerte; só quem chamou
        #: `set_microphone_led` assume o campo. Não escrever é o único write
        #: não-destrutivo, porque este registrador não tem leitura.
        self._mic_led_desejado: bool | None = None
        #: 4 posições (fone, alto-falante, mic, roteamento). Cada uma é
        #: independente: `None` = não somos donos DAQUELE byte e o bit de
        #: validação dele sai apagado. Isso importa no byte 7 (roteamento de
        #: áudio / seleção de microfone), que não sabemos ler e cujo valor
        #: neutro NÃO é 0 — autorizá-lo junto do volume seria adivinhar.
        self._volumes_audio: list[int | None] = [None, None, None, None]
        #: SOM-ROTA-01: o ganho do pré-amp (common[37] bits 0-2). `None` = sem
        #: dono, e o byte sai zerado com o bit de autorização apagado — a
        #: MESMA disciplina dos quatro de cima (AUDIO-OWNER-01): autorizar sem
        #: escrever é mandar zero a 60 Hz com cara de keepalive.
        self._preamp_audio: int | None = None
        # AUDIO-STATUS-01 — último byte de estado de áudio visto no report de
        # INPUT (fone plugado / mic externo / mic MUDO pelo firmware). Custo
        # zero: a pydualsense já guarda o report cru em `self.states` a cada
        # leitura; aqui só copiamos UM byte no mesmo laço que já roda.
        self._audio_status: int | None = None

    # O nome manglado de `pydualsense.__find_device` é
    # `_pydualsense__find_device`; o `init()` do upstream chama
    # `self.__find_device()` que resolve para este override.
    def _pydualsense__find_device(self) -> tuple[Any, bool]:  # nome manglado do upstream
        import hidapi

        return hidapi.Device(path=self._pinned_path), self._pinned_is_edge

    def sendReport(self) -> None:  # noqa: N802 - override do nome do upstream
        """Igual ao loop do upstream, mas com throttle por ciclo.

        O upstream faz `read`+`write` num laço apertado sem pausa, na taxa do
        controle. Com múltiplos controles isso satura o controlador USB e
        degrada o link Bluetooth (CRC fails → output do BT morre). Como o INPUT
        real vem do evdev, aqui só precisamos do flush de OUTPUT e da leitura
        esparsa de bateria/transporte — então pausamos `REPORT_THREAD_THROTTLE_SEC`
        por ciclo. BUG-MULTI-CONTROLLER-BT-CRC-CONTENTION-01.

        LACO-DE-ESCRITA-02 (15/08/2026) — A LEITURA VAZIA NÃO PODE MATAR A SAÍDA.

        O handle é aberto por `_pydualsense__find_device` com `hidapi.Device(
        path=...)` — SEM `blocking=True` —, e o construtor do hidapi chama
        `hid_set_nonblocking(...)` sempre que `blocking` é falso. Logo o `read`
        pode devolver `None` (rv == 0, "não havia dado"), e `None` é resposta
        legítima, não erro.

        O `readInput` do upstream começa com `list(inReport)`. Com `None` isso
        levanta `TypeError` — que este laço NÃO capturava (só `OSError` e
        `AttributeError`). A thread morria, e com ela toda a saída daquele
        controle: sem rumble, sem lightbar, sem gatilho, para sempre, porque o
        `connect()` do `reconnect_loop` não reabre handle de controle que
        continua enumerado. Pior: morria sem `connected = False`, então nem a
        tela dela sabia.

        **A cura não é capturar o `TypeError`** — capturar trocaria uma morte
        calada por um laço calado, e continuaria tratando como acidente uma
        resposta que a API promete. A cura é PARAR DE PASSAR `None` adiante: sem
        dado, não há o que interpretar, e o ciclo segue direto para a metade de
        SAÍDA, que é a metade que importa aqui (o INPUT vem do evdev). O
        controle continua tendo saída durante o silêncio, que é o desfecho certo.

        E o silêncio deixa RASTRO: uma linha de aviso por episódio quando ele
        passa de `LEITURA_VAZIA_AVISO_SEC`, e uma de volta quando a entrada
        fala de novo — porque um controle mudo por segundos é notícia, e a
        ausência de dado é justamente o sintoma que esta casa mais demora a ver.
        """
        while self.ds_thread:
            try:
                in_report = self.device.read(self.input_report_length)
                if in_report is None:
                    self._registrar_leitura_vazia()
                else:
                    self._registrar_leitura_viva()
                    self.readInput(in_report)
                    self._captura_status_audio()
                # FEAT-NATIVE-OUTPUT-MUTE-01: mutado (Modo Nativo) = NENHUM
                # write; o jogo é o dono do output deste controle.
                if not self._output_muted:
                    # RUMBLE-SEM-DONO-01: lido ANTES do `prepareReport`, que
                    # CONSOME o `_rumble_stop_pending` ao montar o report.
                    dono_do_rumble = self._rumble_active or self._rumble_stop_pending
                    out = self.prepareReport()
                    now = time.monotonic()
                    # PERF-MULTI-CONTROLLER-01: write OUT só quando o report
                    # MUDOU, com keepalive esparso. O seq-tag BT da pydualsense
                    # é fixo, e o report USB não tem contador — o buffer é
                    # função pura do estado desejado, então a comparação detecta
                    # mudança real (rumble do jogo, trigger novo, LED). Report
                    # idêntico reescrito a ~100Hz era pura pressão de barramento
                    # com 2+ controles.
                    mudou = out != self._last_out_report
                    if mudou:
                        self._last_change_at = now
                    # RUMBLE-SEM-DONO-01 — MEDIDO em 11/08/2026, com quatro
                    # DualSense na mesa dela (dois no cabo, dois no rádio) e o
                    # olho dela como aceite. Ensaios `keepalive-dose-cabo`,
                    # `keepalive-dose-radio` e `keepalive-premissa-troca-de-lado`
                    # em `docs/data/ensaios.csv`.
                    #
                    # O QUE CAIU. A cura `keepalive neutro` (GUERRA-01 item 2,
                    # em `_build_common`) apostava que DESLIGAR os bits de
                    # autorização de vibração bastava para o firmware conservar
                    # o motor de outro dono. Não basta: com o daemon parado, o
                    # EV_FF ligou o motor ESQUERDO, e UM único report com os
                    # bits de vibração DESLIGADOS pedindo `common[2]=200`
                    # (direito) e `common[3]=0` (esquerdo) fez o tremor TROCAR
                    # DE LADO na mão dela. O firmware obedece aos BYTES de motor
                    # e ignora os bits para esse fim — e os bytes saem SEMPRE,
                    # em `_build_common`, fora do `if not rumble_asserted`.
                    #
                    # A DOSE-RESPOSTA que fechou a conta: subindo
                    # `OUT_REPORT_KEEPALIVE_SEC` de 0,5 s para 8,0 s, a vibração
                    # de terceiros passou a durar OITO SEGUNDOS EXATOS nos dois
                    # transportes. O keepalive não é vizinho do defeito: ele é o
                    # cronômetro do defeito.
                    #
                    # POR QUE A CURA É ESTA E NÃO OUTRA. O report é atômico:
                    # `common[2]`/`common[3]` viajam em TODO write, e não existe
                    # valor neutro para eles (não há report de entrada nem
                    # feature que devolva o que o outro dono pediu, então
                    # "carregar o último valor conhecido" seria carregar o NOSSO
                    # zero com outro nome). Logo, o único write não-destrutivo é
                    # o write que NÃO acontece. Mas calar o keepalive para
                    # sempre perderia o que ele já curava, e a regra da casa é
                    # que hipótese tem de explicar o que JÁ funcionava — então
                    # ele não some: fica LIMITADO à janela de confirmação depois
                    # de cada mudança, que é onde mora a função dele (garantir
                    # que a mudança chegou). Passada a janela, o report idêntico
                    # não carrega informação nenhuma e só apaga motor alheio.
                    #
                    # Com rumble NOSSO (`dono_do_rumble`) nada muda: ali o
                    # keepalive é o que faz a vibração dela persistir.
                    confirmando = (
                        now - self._last_change_at
                    ) < OUT_REPORT_KEEPALIVE_CONFIRMACAO_SEC
                    vencido = (now - self._last_write_at) >= OUT_REPORT_KEEPALIVE_SEC
                    if mudou or (vencido and (dono_do_rumble or confirmando)):
                        self.writeReport(out)
                        self._last_out_report = out
                        self._last_write_at = now
                throttle = self._throttle_sec
                if throttle > 0:
                    time.sleep(throttle)
            except OSError:
                self.connected = False
                break
            except AttributeError:
                self.connected = False
                break
            except Exception as exc:
                # LACO-DE-ESCRITA-02 — a REDE, e ela não engole nada.
                #
                # O `TypeError` do `read` vazio foi curado na raiz acima; esta
                # cláusula existe para a categoria dele, não para ele. Sem ela,
                # qualquer exceção nova neste laço mata a `report_thread` com
                # nada além de um traceback solto no stderr: sem linha
                # estruturada, sem `connected = False`, e com a tela dela ainda
                # jurando que o controle está conectado.
                #
                # O desfecho é o MESMO do `OSError` (fim de vida do handle) — e
                # de propósito: seguir o laço depois de uma exceção que não se
                # sabe nomear é girar sem saber em quê, e este laço escreve no
                # aparelho dela. O que muda é que agora fica escrito.
                self.connected = False
                logger.error(
                    "report_thread_morreu_por_excecao",
                    path=getattr(self, "_pinned_path", None),
                    tipo=type(exc).__name__,
                    err=str(exc),
                )
                break

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

    # QUEDA-QUE-PENDURA-01, 04/08/2026 — MEDIDO no journal dela.
    #
    # O `close()` do upstream é, literalmente:
    #
    #     self.ds_thread = False
    #     self.report_thread.join()     <- SEM TETO
    #     self.device.close()
    #
    # e o topo do laço acima é `self.device.read(...)`, que BLOQUEIA. Enquanto
    # o controle responde, o `ds_thread = False` é visto no ciclo seguinte e o
    # join volta em milissegundos. **Quando o controle some do rádio sem
    # despedida** — 8BitDo que se desliga sozinho, link Bluetooth que cai —
    # o `read` fica pendurado num fd que nunca mais entrega nada, o join espera
    # para sempre, e a espera sobe inteira pela pilha:
    #
    #     read (nunca volta)
    #       -> report_thread.join()          (upstream, sem teto)
    #         -> handle.close()
    #           -> disconnect()              SEGURANDO o `_io_lock`
    #             -> shutdown() do daemon
    #               -> systemd: 90 s e SIGKILL
    #
    # O journal de 04/08 tem a coisa inteira: `gamepad_emulation_stopped` às
    # 00:20:19.601, o `daemon_stopped` NUNCA, e às 00:21:49
    # *"State 'stop-sigterm' timed out. Killing."*. Custo real: 90 segundos em
    # que o serviço não volta, os vpads não renascem e a mesa fica sem
    # controle nenhum.
    #
    # A cura é fechar o fd MESMO ASSIM. O laço acima já trata `OSError` como
    # fim de vida (`connected = False; break`) — fechar o dispositivo faz o
    # `read` pendurado retornar erro e a thread sair sozinha, que é a ordem
    # inversa da do upstream e a única que funciona com o fd morto.
    #
    # Uma thread que ainda assim não morra NÃO segura o processo: é o mesmo
    # trade-off que o `HANG-01` já escreveu por extenso nos dois executores do
    # `shutdown` (`wait=False`) — *"uma thread wedged não impede o processo de
    # encerrar"*. Aqui ela vale para o handle, que era o furo que faltava.
    def close(self) -> None:
        """Igual ao upstream, mas o join tem TETO e o fd fecha de todo jeito."""
        self.ds_thread = False
        thread = getattr(self, "report_thread", None)
        if thread is not None and thread.is_alive():
            thread.join(timeout=CLOSE_JOIN_TIMEOUT_SEC)
        with contextlib.suppress(Exception):
            self.device.close()
        if thread is not None and thread.is_alive():
            # O fd acabou de fechar; dá-se à thread a última chance de ver o
            # OSError e sair. Se nem assim, seguimos — ela não escreve mais em
            # dispositivo nenhum, e o processo precisa poder morrer.
            thread.join(timeout=CLOSE_JOIN_TIMEOUT_SEC)
            if thread.is_alive():
                logger.warning(
                    "report_thread_nao_encerrou",
                    detalhe="fd fechado e thread ainda viva — controle sumiu do rádio",
                )

    # --- AUDIO-STATUS-01 / AUDIO-OWNER-01 --------------------------------

    def _captura_status_audio(self) -> None:
        """Copia o byte de estado de áudio do último report de INPUT lido.

        A pydualsense guarda o report cru NORMALIZADO em `self.states` dentro
        do `readInput` (por USB são os bytes do report; por BT ela descarta o
        byte de seq/flags do envelope). Nos dois casos o índice do byte de
        áudio é o MESMO 54 — é o offset 53 do `USBGetStateData`, um a mais que
        o byte de bateria que a própria pydualsense lê em `states[53]`.

        Custo: uma indexação de lista por report já lido. NÃO abrimos fd novo,
        NÃO fazemos leitura extra — o report de input já estava na mão.
        """
        estados = getattr(self, "states", None)
        if isinstance(estados, list) and len(estados) > _INPUT_AUDIO_STATUS_IDX:
            valor = estados[_INPUT_AUDIO_STATUS_IDX]
            if isinstance(valor, int):
                self._audio_status = valor & 0xFF

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

    def set_microphone_led(self, aceso: bool | None) -> None:
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
        self._mic_led_desejado = None if aceso is None else bool(aceso)
        if aceso is not None:
            with contextlib.suppress(Exception):
                self.audio.setMicrophoneLED(bool(aceso))

    def set_audio_volumes(
        self,
        *,
        headphone: int | None = None,
        speaker: int | None = None,
        microphone: int | None = None,
        audio_path: int | None = None,
        preamp: int | None = None,
    ) -> None:
        """Assume a posse dos bytes de volume que forem passados (common[4..7]).

        Cada byte tem o SEU bit de validação no flag0 (fone 0x10, alto-falante
        0x20, microfone 0x40, roteamento 0x80), então a posse é por byte:
        quem passa só `speaker` autoriza só o alto-falante e o resto do bloco
        continua com o firmware. Argumento omitido mantém o que já estava
        (inclusive "sem dono").

        `set_audio_volumes(...)` é a ÚNICA porta: sem ela `_build_common`
        mantém os bits de áudio do flag0 zerados e os quatro bytes em 0
        (inertes — o firmware ignora byte cujo bit de validação está apagado).
        """
        for pos, valor in enumerate((headphone, speaker, microphone, audio_path)):
            if valor is not None:
                # SOM-ROTA-01: o clamp é por CAMPO, e não 0-255 para todos.
                self._volumes_audio[pos] = min(
                    _clamp_u8(valor, 0), _AUDIO_TETOS[pos]
                )
        if preamp is not None:
            self._preamp_audio = int(preamp) & rep.SP_PREAMP_GAIN_MASK

    def release_audio_volumes(self) -> None:
        """Devolve a posse dos bytes de áudio (volta ao neutro). Idempotente.

        SOM-ROTA-01: o pré-amplificador (`common[37]`) entra na devolução
        junto com os quatro de `common[4..7]`. Deixá-lo de fora faria
        "Devolver" devolver metade — e o pré-amp é justamente o campo que
        muda o alcance do controle deslizante.

        O que a devolução NÃO faz, e nunca fez: restaurar o valor anterior. O
        DualSense não devolve o volume — não há report de entrada nem feature
        que o leia. "Devolver" devolve o CONTROLE, nunca o número.
        """
        self._volumes_audio = [None, None, None, None]
        self._preamp_audio = None

    def setLeftMotor(self, intensity: int) -> None:  # noqa: N802 - nome do upstream
        super().setLeftMotor(intensity)
        self._track_rumble_transition()

    def setRightMotor(self, intensity: int) -> None:  # noqa: N802 - nome do upstream
        super().setRightMotor(intensity)
        self._track_rumble_transition()

    def _track_rumble_transition(self) -> None:
        """GUERRA-01 item 2: rastreia rumble NOSSO ativo e a transição ativa→0.

        `_rumble_active` liga com qualquer motor > 0; ao ambos zerarem, vira
        `_rumble_stop_pending` — o próximo report sai com os flags de vibração
        LIGADOS (e motores 0) para o firmware parar o motor de verdade, e só
        então o report volta ao neutro. 0→0 não gera stop (nunca vibrou).
        """
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
        flag0 = 0xFF  # upstream: vibração+gatilhos+áudio sempre autorizados
        flag1 = 0x01 | 0x02 | 0x04 | 0x10 | 0x40  # upstream: mic+LED+atenuação
        flag2 = int(self.light.ledOption.value)
        # AUDIO-OWNER-01: os bits de áudio do flag0 caem TODOS e só voltam,
        # um a um, para os bytes de que alguém assumiu a posse.
        flag0 &= ~rep.VALID_FLAG0_AUDIO_MASK
        for bit, valor in zip(_AUDIO_FLAG0_BITS, volumes, strict=False):
            if valor is not None:
                flag0 |= bit
        if mic_mute is None:
            flag1 &= ~rep.VALID_FLAG1_POWER_SAVE_CONTROL_ENABLE
        # AUDIO-OWNER-01 (12/08/2026), o LED do botão de mudo: sem dono, o
        # `0x01` cai e `common[8]` fica inerte — o kernel, que acende o LED na
        # borda do botão, deixa de ser desfeito pelo nosso próximo report.
        if mic_led is None:
            flag1 &= ~rep.VALID_FLAG1_MIC_MUTE_LED_CONTROL_ENABLE
        if not rumble_asserted:
            flag0 &= ~(
                rep.VALID_FLAG0_COMPATIBLE_VIBRATION | rep.VALID_FLAG0_HAPTICS_SELECT
            )
            flag1 &= ~rep.VALID_FLAG1_MOTOR_POWER
            flag2 &= ~rep.VALID_FLAG2_COMPATIBLE_VIBRATION2
        if suppress_leds:
            flag1 &= ~(
                rep.VALID_FLAG1_LIGHTBAR_CONTROL_ENABLE
                | rep.VALID_FLAG1_PLAYER_INDICATOR_CONTROL_ENABLE
            )
            # LIGHTBAR-BT-KEEPALIVE-01: não tocar a máquina de setup/brilho da
            # lightbar (o kernel é o dono) — o keepalive vira LED-neutro de fato.
            flag2 &= ~(
                rep.VALID_FLAG2_LIGHTBAR_SETUP_CONTROL_ENABLE
                | rep.VALID_FLAG2_LED_BRIGHTNESS_CONTROL_ENABLE
            )
        common[2] = int(self.rightMotor) & 0xFF
        common[3] = int(self.leftMotor) & 0xFF
        for offset, valor in zip(_AUDIO_COMMON_OFFSETS, volumes, strict=False):
            if valor is not None:
                common[offset] = int(valor) & 0xFF
        # SOM-ROTA-01: o pré-amplificador, com o MESMO contrato dos quatro de
        # cima — o bit de autorização só liga quando alguém escreveu um valor.
        preamp = getattr(self, "_preamp_audio", None)
        if preamp is None:
            flag1 &= ~rep.VALID_FLAG1_AUDIO_CONTROL2_ENABLE
        else:
            flag1 |= rep.VALID_FLAG1_AUDIO_CONTROL2_ENABLE
            common[rep.COMMON_AUDIO_CONTROL2] = int(preamp) & rep.SP_PREAMP_GAIN_MASK
        common[0] = flag0
        common[1] = flag1
        if mic_led is not None:
            common[8] = 1 if mic_led else 0
        # `audio.microphone_mute` da pydualsense continua sendo o valor de
        # fato mandado — mas só quando temos a posse (ver AUDIO-OWNER-01).
        if mic_mute is not None:
            self.audio.microphone_mute = mic_mute
            common[9] = rep.POWER_SAVE_MIC_MUTE if mic_mute else 0x00
        # REPLICA-03: bloco cru do jogo (se em posse) vence o estado DSTrigger.
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
            common[42] = int(self.light.brightness.value) & 0xFF
            common[43] = int(self.light.playerNumber.value) & 0xFF
            common[44] = int(self.light.TouchpadColor[0]) & 0xFF
            common[45] = int(self.light.TouchpadColor[1]) & 0xFF
            common[46] = int(self.light.TouchpadColor[2]) & 0xFF
        # LIGHTBAR-BT-KEEPALIVE-01: sob supressão os bytes de lightbar/player/
        # setup ficam ZERO (inertes — os flags que os validariam estão
        # limpos) e estáveis para o dedup `_last_out_report`.
        return common

    def prepareReport(self) -> list[int]:  # noqa: N802 - override do nome do upstream
        """Monta o report pelo builder comum (BTREPORT-02) — não usa o upstream.

        USB: envelope 0x02 (idêntico ao histórico). BT: envelope 0x31 CORRETO
        (`[1]=seq<<4`, `[2]=0x10`, common em `[3..49]`, CRC nos 4 últimos) —
        o 0x31 da pydualsense 0.7.5 é malformado e o firmware o descarta, o
        que fazia todo o nosso output BT (rumble/gatilhos/keepalive) ser
        no-op. O nibble de seq sai 0 aqui (report comparável para o dedup
        `_last_out_report`); quem carimba o contador real é `writeReport`.

        Fallback: qualquer falha na montagem cai no report do upstream (USB
        correto; BT malformado = comportamento pré-fix, nunca pior) — o
        report_thread não pode morrer por causa disto.
        """
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
                # O report de STOP (flags ligados, motores 0) foi montado —
                # o próximo ciclo volta ao neutro. Limpa SÓ o snapshot lido
                # (um pending novo, setado durante a montagem, sobrevive).
                self._rumble_stop_pending = False
            return report
        except Exception:  # nunca derrubar o report_thread por causa disto
            fallback: list[int] = super().prepareReport()
            return fallback

    def writeReport(self, outReport: list[int]) -> None:  # noqa: N802,N803 - upstream
        """Write com carimbo de sequência BT (BTREPORT-02), SERIALIZADO.

        Reports 0x31 ganham o contador por handle (wrap 0-15) + CRC recalculado
        NUMA CÓPIA — o buffer original (que `sendReport` guarda em
        `_last_out_report`) permanece com seq 0, mantendo o dedup funcional.

        LACO-DE-ESCRITA-02 (15/08/2026) — POR QUE HÁ UM LOCK AQUI.

        Este método é chamado de MAIS DE UMA THREAD no mesmo handle:

        - a `report_thread` daquele handle, em regime (`sendReport`);
        - a thread do chamador (IPC / executor do poll loop) em
          `reescrever_lightbar_por_hidraw`, `_pintar_por_hidraw_bt` e
          `core/lightbar_reset.py` — todas escritas AVULSAS, todas só no rádio.

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
        """
        with self._write_lock:
            if len(outReport) == 78 and outReport[0] == 0x31:
                from hefesto_dualsense4unix.core import ds_output_report as rep

                stamped = list(outReport)
                rep.stamp_bt_seq(stamped, self._bt_seq)
                self._bt_seq = (self._bt_seq + 1) & 0x0F
                self.device.write(bytes(stamped))
                return
            self.device.write(bytes(outReport))


class PyDualSenseController(IController):
    """Implementação de `IController` baseada em `pydualsense` (multi-controle).

    OUTPUT é aplicado a todos os controles (fan-out); INPUT/EMULAÇÃO vem só do
    controle primário. Ver o cabeçalho do módulo (FEAT-DSX-MULTI-CONTROLLER-01).
    """

    def __init__(self, evdev_reader: EvdevReader | None = None) -> None:
        # chave (serial/MAC ou path) -> handle aberto. O `dict` preserva ordem
        # de inserção (py3.7+): o 1º inserido que ainda estiver presente é o
        # PRIMÁRIO. Controles novos entram no FIM, então nunca roubam o primário
        # de um já conectado.
        self._handles: dict[str, pydualsense] = {}
        self._primary_key: str | None = None
        self._transport: Transport = "usb"
        # BUG-DAEMON-NO-DEVICE-FATAL-01: estado "offline-OK". Marcado quando não
        # há nenhum DualSense — daemon segue vivo, IPC/UDP/CLI funcionais, e
        # `connect()` é retentado periodicamente pelo `reconnect_loop`.
        self._offline: bool = False
        # PERFIL-01 (4P-01): estado desejado POR CONTROLE. `_desired_default`
        # é o padrão broadcast (o "perfil ativo" histórico); `_desired_by_uniq`
        # guarda o override PARCIAL de cada controle, keyed pelo MAC 12-hex
        # normalizado (o mesmo `_key_to_uniq` — estável entre USB e BT). O
        # hotplug-in re-aplica o MERGE POR CAMPO dos dois no controle certo.
        self._desired_default = _DesiredOutput()
        self._desired_by_uniq: dict[str, _DesiredOutput] = {}
        # R-20: DONO de cada campo de cada override (`{uniq: {campo: camada}}`).
        # O mapa de valores continua sendo UM só (`_desired_by_uniq`) — o
        # merge por campo do PERFIL-01/04/05, provado ao vivo no hotplug, não
        # muda em nada. O que passa a existir é a procedência, para a ativação
        # de perfil soltar só a camada dela.
        self._desired_owner_by_uniq: dict[str, dict[str, str]] = {}
        # R-13 item 1: camada do CO-OP (padrão de player-LED por jogador).
        # Antes o co-op escrevia sysfs CRU, fora do estado desejado — e o
        # `reassert_resolved_outputs`, que roda em TODO `connect()` (≤30 s),
        # repintava o padrão do perfil por cima: pisca-pisca sem fim, com os
        # números duplicados que ela vê. Publicada aqui, a mesma reafirmação
        # passa a reafirmar o valor DO CO-OP.
        self._desired_coop_by_uniq: dict[str, _DesiredOutput] = {}
        # R-20 item 2: escala de brilho POR CONTROLE, aplicada DEPOIS do merge.
        # Um override que só mexia no brilho materializava a cor GLOBAL no
        # slot por-uniq (`_controllers_to_specs` resolvia `lightbar` do global
        # para poder escalar) — e, como o override vence a camada automática,
        # isso MATAVA a cor do slot daquele controle. Guardado como fator, o
        # brilho escala a cor RESOLVIDA (automática inclusive) sem opinar
        # sobre qual cor é.
        self._led_scale_by_uniq: dict[str, float] = {}
        # POR-UNIDADE-01 (10/08/2026): a escala de VIBRAÇÃO por-uniq — irmã
        # exata do `_led_scale_by_uniq` acima, e pelo mesmo motivo de desenho.
        # O que chega do perfil é uma POLÍTICA de intensidade por controle
        # ("o branco vibra em economia, o preto no máximo"), e o daemon só
        # sabe escalar a política GLOBAL (`DaemonConfig.rumble_policy`, um
        # número para a casa inteira). Guardar aqui um FATOR por peça deixa o
        # `set_rumble` broadcast continuar sendo UM valor pedido — cada handle
        # recebe o seu, escalado na saída. Ausência de entrada = sem opinião
        # (fator 1.0, byte-idêntico ao de hoje).
        self._rumble_scale_by_uniq: dict[str, float] = {}
        # COR-03: provider da camada AUTOMÁTICA do desejado (cor do slot +
        # player-LED do número do controle), injetado pelo daemon via
        # `set_auto_output_provider` (injeção de dependência — core/ nunca
        # importa daemon/). None = sem camada automática (o merge cai no
        # comportamento histórico default+override). Consultado POR UNIQ em
        # `_merged_desired_for_key`, SOB `_io_lock` — o provider DEVE ser
        # barato e sem I/O.
        self._auto_output_provider: Callable[[str], _DesiredOutput | None] | None = None
        # S-5 (auditoria 21/07): opener broker-aware da leitura da feature 0x05
        # (calibração). Sem ele, `read_calibration` abre por `os.open(path)` e,
        # quando o broker ESCONDE o hidraw (0600 root — promoção VPAD-02 com
        # release_grab=False, respawn de coop), dá EACCES → calibração canônica
        # → DRIFT do gyro (o que o GYRO-01 quis evitar). O daemon injeta
        # `make_broker_opener` (fd root via SCM_RIGHTS, funciona com o nó
        # escondido); None = `os.open` por caminho (comportamento histórico).
        self._feature_opener: Callable[[str], int] | None = None
        # REPLICA-03: camada GAME do desejado — o que o JOGO escreveu no vpad
        # deste controle (lightbar/player-LED), replicado pelo daemon. É o TOPO
        # do merge de `_merged_desired_for_key` (jogo vence override, auto e
        # default enquanto a sessão uhid estiver aberta) e some no
        # `end_game_session_for` (UHID_CLOSE), quando o perfil/paleta voltam.
        # Os trigger effects do jogo ficam à parte (`_game_triggers_by_uniq`):
        # são blocos CRUS de 11 bytes (não cabem no TriggerEffect de 7 forças)
        # aplicados direto no handle (`_raw_trigger_*`).
        self._game_output_by_uniq: dict[str, _DesiredOutput] = {}
        self._game_triggers_by_uniq: dict[str, dict[str, bytes]] = {}
        # NUMA-02: provider da AUTORIDADE de exibição ('game'|'daemon'|
        # 'unknown'), injetado pelo daemon (GameSignal do lifecycle) — leitura
        # de estado cacheado, zero I/O (mesmo contrato do
        # `_auto_output_provider`). None = sem fiação = `_game_wins()` True
        # (compat byte-idêntica: FakeController e a suíte REPLICA-03 inteira
        # não mudam de comportamento — fail-safe "nunca pior que hoje").
        self._game_authority_provider: Callable[[], str] | None = None
        # NUMA-02 (retain-latest): réplicas de EXIBIÇÃO recebidas sob
        # autoridade 'daemon' — 1 valor por (uniq, categoria), sempre o MAIS
        # recente (bounded por construção: só 'led'/'player_leds' por MAC).
        # `replay_retained_game_outputs()` entrega tudo 1x na abertura do
        # gate — a escrita ÚNICA de player-LED que jogos fazem (FATO 0) não
        # pode se perder na latência ~2s do sinal. Drop sem retenção é
        # vetado pela síntese da Onda N. Correção pós-auditoria: também
        # purgado por `end_game_session_for` no fim da MESMA sessão que o
        # gerou — sem isso, o valor sobrevive ao UHID_CLOSE (é um dict por
        # uniq, não por sessão) e vaza para a PRÓXIMA sessão de jogo real
        # deste controle via `replay_retained_game_outputs`, mesmo sem
        # nenhuma relação com quem escreveu o valor original.
        self._retained_game_outputs: dict[str, dict[str, Any]] = {}
        # Log `game_output_retido_sem_jogo` 1x por episódio (re-armado no
        # replay — episódio = um período contínuo de autoridade 'daemon').
        self._retained_log_armed = True
        # NUMA-03: monotonic da última defesa de exibição (rate-limit da
        # defesa disparada por réplica retida).
        self._defend_last_at: float | None = None
        # FEAT-DSX-LIGHTBAR-SYSFS-01: mapeia key (serial/MAC/path) -> nó LED do
        # kernel (sysfs) para os controles cuja lightbar/player-LED são graváveis
        # por sysfs. Quando presente, a cor/player vão por essa rota (USB E BT) e
        # a escrita pydualsense desses LEDs é suprimida (anti-contenção). Vazio =
        # ninguém coberto (sem regra udev / driver antigo) → caminho pydualsense.
        self._sysfs: dict[str, Any] = {}
        # LIGHTBAR-ISOLAR-OS-PLAYERS-01: instrumento de eliminação, sempre
        # desligado ao nascer (ver `suprimir_player_leds`).
        self._suprimir_player_leds = False
        # STATUS-01: rastreio "escrito por nós" — key (a mesma de `_sysfs`) ->
        # última cor RGB escrita POR ESTE backend via classe LED (sysfs). É a
        # prova de POSSE do nó que autoriza ler `multi_intensity` como verdade
        # (refutação 1 do sprint: a classe nasce zerada no probe e `0 0 0` sem
        # escrita nossa NUNCA significa "apagada"). Mantido por
        # `record_sysfs_write`/`_refresh_sysfs_leds`; podado junto com o mapa.
        self._sysfs_written: dict[str, tuple[int, int, int]] = {}
        # FEAT-DSX-CONTROLLER-SELECTOR-01: ALVO das ações de output. None =
        # TODOS (broadcast, padrão e idêntico ao histórico). Guardamos a KEY
        # estável (serial/MAC) do controle escolhido — NÃO o índice — para
        # sobreviver a hotplug/troca de porta. Se a key alvo sumir (controle
        # desconectou), o `_for_each` cai de volta em broadcast.
        self._output_target_key: str | None = None
        # FEAT-NATIVE-OUTPUT-MUTE-01: espelho no backend do mute de output
        # (Modo Nativo) — aplicado a todo handle atual E aos que abrirem
        # durante o mute (hotplug com o jogo aberto).
        self._output_mute = False
        # GATILHO-DA-COR-01: quantas conexões NOVAS de DualSense no RÁDIO o
        # `connect()` abriu desde a última leitura. É o SINAL do gatilho da cor
        # (`core/lightbar_gatilho.py`), e ele mora aqui — e não num vigia
        # próprio — porque o `connect()` já é o tick de hotplug do produto: o
        # `reconnect_loop` o chama a cada `backend_hotplug_reconcile`, e o
        # `reconnect()` do poll loop também. Contador, não flag: duas conexões
        # entre duas leituras não podem virar uma.
        self._conexoes_bt_novas = 0
        # ESCRITOR-CRU-01: quantas vezes o produto PINTOU a barra pelo rádio
        # desde a última leitura (o `_pintar_por_hidraw_bt`, que é por onde
        # passam a GUI, a CLI, o perfil e o hotplug). É o segundo SINAL do
        # gatilho da cor, e existe porque a medição de 16/08 é literal: *"a
        # barra fica APAGADA depois de cada comando nosso"* — com a Steam
        # aberta, quem escreve por ÚLTIMO ganha, e hoje quem escreve por
        # último é ela. Contador, não flag, pela mesma razão do irmão acima.
        self._pinturas_de_lightbar = 0
        # Protege a mutação de `_handles`/`_primary_key` contra o fan-out de
        # escrita: o daemon roda `connect`/`read_state`/setters em executor
        # multi-thread (max_workers=2). RLock pois um caminho pode reentrar.
        self._io_lock = threading.RLock()
        # L2: chaves cuja abertura (`_open_one`) está EM ANDAMENTO. O
        # `reconnect_loop` (via `connect`) e o reconnect do poll loop podem
        # disparar a abertura da MESMA key em paralelo — trabalho duplicado caro
        # (até INIT_TIMEOUT_SEC por probe) cujo handle dup já era descartado.
        # Marcamos a key aqui sob `_io_lock` antes de abrir e a removemos depois,
        # para que o probe concorrente pule essa key em vez de reabrir.
        self._opening: set[str] = set()
        # HOTFIX-2: evdev como fonte primária de input (contorna conflito
        # com kernel hid_playstation). pydualsense segue como caminho de
        # output (triggers, LED, rumble). Single-instance, atrelado ao primário.
        self._evdev = evdev_reader if evdev_reader is not None else EvdevReader()
        # GYRO-01: `PhysicalReportReader` do vpad do P1 (espelho de motion),
        # registrado pelo daemon via `attach_motion_reader`. O backend só o
        # cutuca no retarget de primário (`_recompute_primary`), junto do
        # `_evdev.retarget` — quem cria/para o reader é o subsystem gamepad.
        self._motion_reader: Any | None = None

    # --- identidade ------------------------------------------------------

    def hidraw_path(self, uniq: str | None = None) -> str | None:
        """Nó hidraw do controle `uniq` (None = primário), ou None.

        SPRINT-UHID-VPAD-01: é de onde o vpad uhid copia o report descriptor e os
        feature reports do probe (o "blueprint"). Vem do `_pinned_path` do handle
        já aberto — não re-enumera.

        Devolve None para path de libusb ("0001:0002:00"), que não é nó do sysfs
        e não serve de blueprint; o chamador cai no uinput.
        """
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
        """Registra (ou remove, com None) o reader de motion do P1 (GYRO-01).

        Injeção do daemon (`subsystems/gamepad.py`) — core/ nunca importa
        daemon/. O único uso aqui é o retarget: quando o primário troca,
        `_recompute_primary` manda o reader largar o hidraw antigo e reabrir
        no do primário novo (o `path_provider` dele re-resolve sozinho).
        """
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
        contenção com o read bloqueante do report_thread no handle da hidapi.

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
                return None  # path de libusb: sem nó hidraw para o ioctl
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
        """MAC normalizado do controle PRIMÁRIO (None se sem serial/offline).

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
        return self._key_to_uniq(self._primary_key) if self._primary_key else None

    # --- compat: `_ds` == handle primário -------------------------------

    @property
    def _ds(self) -> pydualsense | None:
        """Handle do controle PRIMÁRIO (ou None se nenhum conectado).

        Seam de compatibilidade: todo o caminho de INPUT (`read_state`,
        `get_battery`, `is_connected` legado, `_detect_transport`) e os testes
        legados continuam falando com um único handle via este atributo.
        """
        key = self._primary_key
        return self._handles.get(key) if key is not None else None

    @_ds.setter
    def _ds(self, value: pydualsense | None) -> None:
        # Seam de compat p/ testes/legado que atribuem o handle primário direto
        # (`inst._ds = fake` / `inst._ds = None`).
        with self._io_lock:
            if value is None:
                self._handles.clear()
                self._primary_key = None
            else:
                self._handles = {"_primary": value}
                self._primary_key = "_primary"

    # --- estado desejado por controle (PERFIL-01 / 4P-01) ----------------

    @property
    def _desired(self) -> _DesiredOutput:
        """Alias de compatibilidade → `_desired_default` (padrão broadcast).

        O co-op lê `getattr(ctrl, "_desired", None).player_leds` como "o
        padrão do perfil" (coop.py `_profile_player_leds`) — um rename seco
        falharia EM SILÊNCIO (getattr devolvendo None para sempre; o co-op
        desligado pararia de restaurar o player-LED do perfil sem nenhum
        teste quebrando). Leitura apenas; a escrita interna usa
        `_desired_default`/`_desired_by_uniq`.
        """
        return self._desired_default

    def set_auto_output_provider(
        self, fn: Callable[[str], _DesiredOutput | None] | None
    ) -> None:
        """Injeta (ou remove, com None) o provider da camada AUTOMÁTICA (COR-03).

        O provider recebe o UNIQ (MAC 12-hex normalizado) de um controle e
        devolve um `_DesiredOutput` com APENAS os campos automáticos
        preenchidos (`led` = cor do slot já escalada pelo brilho, D11;
        `player_leds` = padrão do número do controle, D7) — ou None quando
        não tem opinião (auto desligado, uniq sem slot, vpad). É consultado
        por `_merged_desired_for_key` SOB `_io_lock`: DEVE ser barato e sem
        I/O (nada de disco/HID — só memória). Exceções do provider são
        engolidas com log (a resolução cai no merge histórico) — um provider
        quebrado jamais derruba um reassert de LED.
        """
        with self._io_lock:
            self._auto_output_provider = fn

    def set_feature_opener(self, fn: Callable[[str], int] | None) -> None:
        """Injeta (ou remove, com None) o opener broker-aware da feature 0x05.

        S-5 — espelho de `set_auto_output_provider`: o daemon injeta
        `make_broker_opener(daemon)` (broker primeiro, `os.open` de fallback)
        para que `read_calibration` obtenha um fd mesmo com o hidraw ESCONDIDO
        pelo broker (0600 root), evitando o EACCES → calibração canônica →
        drift do gyro. Consultado dentro de `read_calibration` sob `_io_lock`.
        """
        with self._io_lock:
            self._feature_opener = fn

    def set_game_authority_provider(
        self, fn: Callable[[], str] | None
    ) -> None:
        """Injeta (ou remove, com None) o provider da autoridade de exibição.

        NUMA-02 — espelho exato de `set_auto_output_provider`: o daemon
        (GameSignal do lifecycle, tick lento ~2s) injeta uma função que
        devolve a autoridade corrente ('game'|'daemon'|'unknown'). É
        consultada por `_game_wins()` SOB `_io_lock`: DEVE ser leitura de
        estado cacheado, sem I/O. Sem provider o backend é HEAD
        byte-idêntico — remover esta fiação desliga a Onda N inteira
        (rollback de 1 linha, decisão da síntese).
        """
        with self._io_lock:
            self._game_authority_provider = fn

    def _game_wins(self) -> bool:
        """True quando a camada GAME participa do merge (autoridade ≠ 'daemon').

        NUMA-02 — fail-safe assimétrico da síntese: sem provider injetado OU
        exceção no provider ⇒ True (jogo vence = comportamento atual;
        bloquear réplica exige evidência POSITIVA de não-jogo). Só a
        autoridade 'daemon' explícita fecha o gate; 'game', 'unknown' e
        qualquer lixo devolvido mantêm o caminho de hoje.
        """
        provider = self._game_authority_provider
        if provider is None:
            return True
        try:
            return provider() != "daemon"
        except Exception as exc:
            logger.debug("game_authority_provider_falhou", err=str(exc))
            return True

    def _merged_desired_for_key(
        self, key: str, *, incluir_coop: bool = True
    ) -> _DesiredOutput:
        """Desired efetivo do controle `key`: MERGE POR CAMPO em 5 camadas.

        Precedência (D5, POR CAMPO): camada GAME (REPLICA-03 — o que o jogo
        escreveu no vpad, viva só durante a sessão uhid) > camada CO-OP
        (R-13: o número do jogador enquanto o co-op está ligado) > override
        explícito por-uniq (perfil/usuária, arbitrados por dono — R-20) >
        camada AUTOMÁTICA do provider (COR-03) > default global do perfil.
        Chamar sob `_io_lock` (lê o mapa por-uniq; o provider é chamado aqui
        dentro — barato e sem I/O por contrato de `set_auto_output_provider`).

        R-20 item 2: a escala de brilho por-uniq entra DEPOIS do merge das
        camadas do daemon e ANTES da camada GAME — o brilho é da usuária, a
        cor do jogo é do jogo (escalar o que o jogo pinta seria mentir sobre
        o que ele pediu).

        Key sem MAC (fallback por path) não tem override NEM camada
        automática possível — devolve o default puro (o controle segue só o
        global, comportamento documentado do sprint; a cor automática exige
        identidade estável, D9/D10).

        Nota honesta (D4): com o auto LIGADO, um "Todos" da GUI grava só o
        default — e a automática continuaria vencendo (está acima no merge).
        É exatamente por isso que a semântica D4 manda a GUI DESLIGAR o
        toggle ao aplicar "Todos"; o merge daqui fica honesto e não resolve
        isso por conta própria.
        """
        uniq = self._key_to_uniq(key)
        override = self._desired_by_uniq.get(uniq) if uniq is not None else None
        base = self._desired_default
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
        resolved = _merge_desired(base, override)
        if uniq is not None:
            if incluir_coop:
                resolved = _merge_desired(
                    resolved, self._desired_coop_by_uniq.get(uniq)
                )
            resolved = self._scaled_led(uniq, resolved)
        game = self._game_output_by_uniq.get(uniq) if uniq is not None else None
        # NUMA-02 (gate de exibição em ponto ÚNICO): sob autoridade 'daemon' a
        # camada GAME não entra no merge — este if governa de uma vez o
        # priming, o reassert de hotplug, `reassert_resolved_outputs` e o
        # unmute. Consequência provada nos replays: camada STALE (cliente
        # Steam segurando a sessão uhid sem UHID_CLOSE) é neutralizada no
        # resolve, não defendida — fechar o jogo devolve a paleta em ≤ ~32s.
        if game is not None and self._game_wins():
            resolved = _merge_desired(resolved, game)
        return resolved

    def _scaled_led(self, uniq: str, desired: _DesiredOutput) -> _DesiredOutput:
        """Aplica a escala de brilho por-uniq (R-20 item 2). Sob `_io_lock`.

        Devolve SEMPRE um objeto novo quando escala — `_merge_desired` pode
        ter devolvido o próprio `_desired_default` (quando não há override
        nem camada automática), e mutá-lo corromperia o padrão broadcast de
        todo mundo.
        """
        fator = self._led_scale_by_uniq.get(uniq)
        if fator is None or desired.led is None:
            return desired
        return replace(
            desired,
            led=tuple(  # type: ignore[arg-type]
                max(0, min(255, int(canal * fator))) for canal in desired.led
            ),
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
        """Carimba a procedência dos campos escritos. Sob `_io_lock` (R-20)."""
        donos = self._desired_owner_by_uniq.setdefault(uniq, {})
        for campo in campos:
            donos[campo] = layer

    def _prune_overrides_locked(self) -> None:
        """Poda overrides/carimbos que ficaram vazios. Sob `_io_lock`.

        Mantém a invariante que os testes do PERFIL-01 travam ("entrada vazia
        é podada do mapa") agora que a limpeza acontece campo a campo.
        """
        self._desired_by_uniq = {
            uniq: override
            for uniq, override in self._desired_by_uniq.items()
            if any(getattr(override, name) is not None for name in _OUTPUT_FIELDS)
        }
        self._desired_owner_by_uniq = {
            uniq: donos for uniq, donos in self._desired_owner_by_uniq.items() if donos
        }

    def _record_desired_locked(self, target_key: str | None, fields: dict[str, Any]) -> None:
        """Grava campos do estado desejado no escopo CERTO. Chamar sob `_io_lock`.

        `target_key=None` (broadcast — sem alvo, ou alvo que desconectou, o
        mesmo fallback do `_for_each`): grava no default E LIMPA o campo
        escrito de todos os overrides por-uniq — um "Todos" ao vivo da GUI
        vale para todo mundo; sem a limpeza, "mudei todos para azul,
        repluguei e um voltou verde". Alvo presente: grava SÓ no override do
        MAC do alvo (era o bug provado do 4P-01 — o setter gravava no global
        incondicionalmente e o replug de OUTRO controle herdava o ajuste).
        Alvo sem MAC (key por path): a escrita de hardware acontece, mas não
        há identidade estável para lembrar — log em vez de silêncio.
        """
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
            # R-20: escrita mirada da GUI = camada da USUÁRIA. É este carimbo
            # que faz o ajuste dela sobreviver à próxima ativação de perfil.
            self._stamp_owner_locked(uniq, fields, _LAYER_USER)
            return
        for name, value in fields.items():
            setattr(self._desired_default, name, value)
            for override in self._desired_by_uniq.values():
                setattr(override, name, None)
            # R-20: "Todos" é gesto explícito de nivelar — solta o campo em
            # TODAS as camadas do mapa por-uniq (a do perfil inclusive), senão
            # o override do perfil continuaria vencendo o azul que ela acabou
            # de mandar para todo mundo. A camada do co-op fica de fora: ela
            # tem dono próprio e some no `disable()`.
            for donos in self._desired_owner_by_uniq.values():
                donos.pop(name, None)
        # Poda overrides que ficaram sem nenhum campo (mapa limpo p/ debug).
        self._prune_overrides_locked()

    # --- enumeração + abertura ------------------------------------------

    @staticmethod
    def _enumerate_device_keys() -> list[tuple[str, bytes, bool]]:
        """Retorna `[(key, path, is_edge)]` de TODOS os DualSense plugados.

        `key` é a identidade PERSISTENTE do controle: o `serial_number`
        (== MAC, estável entre replug/troca de porta) quando disponível, com
        fallback para o `path` (estável por porta) quando o firmware não expõe
        serial em USB. Faz dedupe por device (uma mesma controladora pode
        enumerar múltiplas interfaces HID).

        SEAM de teste: stubável para `[]` (offline) ou uma lista fixa.
        """
        import hidapi

        out: list[tuple[str, bytes, bool]] = []
        seen: set[str] = set()
        for info in hidapi.enumerate(vendor_id=DUALSENSE_VENDOR):
            if info.product_id not in DUALSENSE_PIDS:
                continue
            if _is_virtual_hidraw(info.path):
                continue
            # hidapi: serial_number vem de wchar_t* → str (ou None); path vem de
            # char* → bytes. NÃO chamar .decode() no serial (já é str).
            serial = info.serial_number
            key = serial if serial else info.path.decode("utf-8", "replace")
            if key in seen:  # dedupe de múltiplas interfaces do mesmo device
                continue
            seen.add(key)
            out.append((key, info.path, info.product_id == DUALSENSE_EDGE_PID))
        return out

    def _open_one(self, path: bytes, *, is_edge: bool) -> pydualsense | None:
        """Abre UM controle por `path`, com a guarda de timeout do init.

        Retorna o handle aberto, ou None se o device sumiu entre o enumerate e
        o open ("No device detected") ou se o `init()` estourou o timeout
        (BUG-BACKEND-PYDUALSENSE-DSTATE-01). Demais exceções (permissão hidraw,
        USB transitório) propagam para o chamador fazer backoff.

        FD-ZUMBI-DO-INIT-TIMEOUT-01 (15/08/2026, visto ao vivo em
        `/proc/<pid>/fd` da máquina dela). Quem abre o fd do nó hidraw é o
        `hidapi.Device(path=...)` do `_pydualsense__find_device` — ou seja,
        DENTRO do `init()`, dentro da thread que pode pendurar. Quando o join
        estourava, esta função devolvia None e mais ninguém tinha o `ds` na mão:
        o handle ficava órfão, e com ele o fd. Dois desfechos, ambos ruins:

        - `init()` termina com ERRO depois do timeout: o fd só volta quando o
          coletor do Python destrói o `ds` (`hidapi.Device.__del__`), o que
          demora o que o kernel demorar para destravar. Foi o que se mediu: um
          descritor para `/dev/hidraw8 (deleted)` aberto às 06:29:45 e ainda
          aberto mais de uma hora depois, num daemon com teto de 1024 fds.
        - `init()` termina BEM depois do timeout: pior. O upstream sobe o
          `report_thread` na última linha do `init()`, e essa thread segura o
          `ds` vivo para sempre (`while self.ds_thread`). Nasce um ZUMBI que
          escreve report de output num controle que o backend nem sabe que
          abriu — o mesmo zumbi que o `_suppress_leds` já citava por nome, e
          que nenhum `_refresh_sysfs_leds` nem o mute de Modo Nativo alcança,
          porque ambos só varrem `self._handles`.

        A cura é um HANDOFF ATÔMICO: caller e runner decidem sob o MESMO lock
        de quem é o handle. Quem perde, fecha. Não dá para decidir por
        `t.is_alive()` — entre o `is_alive()` e o `return None` cabe o runner
        terminar, e o zumbi escapava pela fresta.

        Por que fechar aqui não pode tirar o hidraw do produto: este `ds` é
        local e só chega ao `self._handles` pelo `connect()` DEPOIS que esta
        função retorna o handle. No ramo do timeout ela retorna None — o handle
        que a thread fecha nunca foi visto por ninguém. E cada `hidapi.Device`
        faz o SEU `open()` do nó, então o fd fechado é o desta tentativa, não o
        de um handle vivo que por acaso aponte para o mesmo `/dev/hidrawN`.

        Por que o `close()` roda na thread do runner e não aqui: fechar o
        `hid_device` por cima de um `hid_read` em curso é puxar a estrutura
        debaixo de quem está lendo. Na thread do runner, o `close()` só acontece
        depois que o `init()` voltou.
        """
        ds = _PinnedPyDualSense(path, is_edge=is_edge)
        # Roda `ds.init()` numa thread daemon com timeout. Se a chamada entrar
        # em D-state (kernel HID bloqueado, hidraw órfão, hub em low-power), o
        # daemon principal não trava: a thread segue sozinha (daemon=True → morre
        # com o processo) e devolvemos None. O probe periódico retenta. Não
        # usamos ThreadPoolExecutor porque seu __exit__ join-aria a thread morta.
        result: list[Exception | None] = []
        # O handoff. Tudo aqui dentro só se lê e se escreve sob `entrega`:
        # `terminou` = o runner acabou a tempo e o handle é do caller;
        # `desistido` = o caller já foi embora e o handle é do runner (fechar).
        entrega = threading.Lock()
        estado = {"terminou": False, "desistido": False}

        def _runner() -> None:
            erro: Exception | None = None
            try:
                ds.init()
            except Exception as exc:  # propagamos para o caller via result
                erro = exc
            with entrega:
                orfao = estado["desistido"]
                if not orfao:
                    estado["terminou"] = True
                    result.append(erro)
            if orfao:
                # O caller já desistiu deste handle: ele é lixo, e é aqui que o
                # fd do hidraw volta. O `close()` da subclasse também derruba o
                # `report_thread` que o `init()` possa ter subido tarde demais.
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
          - já presente → mantém intacto (não reabre).
        """
        want = self._enumerate_device_keys()
        if not want:
            with self._io_lock:
                self._close_handles(keep=set())
                self._recompute_primary()
                self._offline = True
            return

        want_keys = {key for key, _, _ in want}
        with self._io_lock:
            # hotplug-OUT: fecha tudo que sumiu (sem vazar handle/thread).
            self._close_handles(keep=want_keys)
            existing = set(self._handles)

        # hotplug-IN: abre os que faltam (fora do lock — `_open_one` pode levar
        # até INIT_TIMEOUT_SEC e não deve bloquear read_state/fan-out).
        new_handles: list[tuple[str, pydualsense]] = []
        for key, path, is_edge in want:
            if key in existing:
                continue
            # L2: pula se já há handle OU se outro probe concorrente já está
            # abrindo esta key (guard sob `_io_lock`). Marca a key como "em
            # abertura" antes do `_open_one` (caro) e a libera no `finally`.
            with self._io_lock:
                if key in self._handles or key in self._opening:
                    continue
                self._opening.add(key)
            try:
                handle = self._open_one(path, is_edge=is_edge)
                if handle is None:
                    continue  # timeout / sumiu na corrida — retenta no próximo probe
                dup: pydualsense | None = None
                with self._io_lock:
                    if key in self._handles:
                        # outro probe concorrente abriu primeiro — descarta o dup.
                        dup = handle
                    else:
                        self._handles[key] = handle
                if dup is not None:
                    with contextlib.suppress(Exception):
                        dup.close()
                    continue
                new_handles.append((key, handle))
            except Exception as exc:
                # LIGHTBAR-BT-ADOPT-01 (complemento): falha de UM device não pode
                # abortar o connect() — sem isto, uma exceção do `_open_one` (ex.:
                # permissão hidraw de um 2º controle) pulava `_refresh_sysfs_leds`
                # em TODO tick e, com `_suppress_leds` nascendo True, deixava os
                # handles JÁ abertos suprimidos para sempre (lightbar/player
                # inaplicáveis). Loga e segue para o próximo device.
                logger.debug("backend_open_one_failed", key=key, err=str(exc))
                continue
            finally:
                with self._io_lock:
                    self._opening.discard(key)

        with self._io_lock:
            self._recompute_primary()
            self._offline = not self._handles
            # PERF-MULTI-CONTROLLER-01: throttle do report_thread escala com o
            # nº de controles (base x N, capado) — divide a pressão de USB e de
            # CPU/GIL por controle. Output (LED/trigger/rumble) tolera bem.
            n = max(1, len(self._handles))
            throttle = min(
                REPORT_THREAD_THROTTLE_SEC * n, REPORT_THREAD_THROTTLE_MAX_SEC
            )
            for handle in self._handles.values():
                with contextlib.suppress(Exception):
                    handle._throttle_sec = throttle
                    # FEAT-NATIVE-OUTPUT-MUTE-01: handle novo aberto durante o
                    # Modo Nativo herda o mute (hotplug com jogo em foco).
                    handle._output_muted = self._output_mute
        # GATILHO-DA-COR-01: conta as conexões NOVAS pelo RÁDIO. Só o rádio
        # porque só ele tem o defeito: pelo cabo a barra obedece (ensaio
        # `lightbar-usb-1`, 03/08, e os dois do cabo brancos em 11/08 com o
        # daemon parado). Contado aqui, no fim do tick de hotplug, e NUNCA
        # consumido aqui — quem consome é o `reconnect_loop`, que é quem sabe
        # esperar. Falha de leitura de transporte não pode derrubar o
        # `connect()`: sem o número o gatilho apenas não arma, que é o
        # comportamento de antes desta feature.
        novas_bt = 0
        for _key, handle in new_handles:
            with contextlib.suppress(Exception):
                if self._detect_transport(handle) == "bt":
                    novas_bt += 1
        if novas_bt:
            with self._io_lock:
                self._conexoes_bt_novas += novas_bt
        # LIGHTBAR-BT-RESET-01: a adoção (feature reads do init da pydualsense)
        # derruba o claim da lightbar no FIRMWARE do DualSense por BT — a
        # lightbar apaga e passa a ignorar as escritas de cor do kernel até um
        # power-off (provado ao vivo 2026-07-17/18). A cura é o report "Reset
        # LED state" (flag1=0x08) que o SDL envia em toda conexão BT e o kernel
        # nunca envia. Enviado AQUI, logo após abrir o handle (pós feature
        # reads) e ANTES do reassert de cor — a próxima escrita sysfs volta a
        # colar. Só BT (USB não tem o claim) e best-effort (falha = sintoma
        # antigo, sem regressão).
        # FEAT-NATIVE-OUTPUT-MUTE-01: em Modo Nativo (output mutado) o JOGO é
        # dono do hidraw — não enviar o 0x08 na adoção (mesmo gate do irmão
        # RESET-02 abaixo). Sem isso, um drop+reconnect BT com jogo em foco
        # (handle reaberto → cai em new_handles, a key/MAC é estável) escrevia
        # um report cru por baixo do jogo, violando o contrato de zero write.
        # LIGHTBAR-BT-CULPADO-01 (03/08/2026) — O 0x08 SAIU DAQUI, E ELE ERA A
        # CAUSA DO DEFEITO QUE VEIO CURAR.
        #
        # Este bloco enviava `send_release_leds` (o `0x08`,
        # VALID_FLAG1_RELEASE_LEDS) a todo handle BT recém-adotado. Ele entrou
        # em 18/07 (`bbfe74d`) como a CURA da lightbar por Bluetooth. **Medido
        # no hardware dela em 03/08, com 7 eventos de correlação PERFEITA: o
        # `0x08` enviado DENTRO da janela de ~3,4 s pós-conexão TRAVA a
        # lightbar até o power-off físico do controle.**
        #
        #   | evento                | 0x08 após conectar | barra    |
        #   | branco  17:48:24.266  | mesmo milissegundo | travou   |
        #   | roxo    17:48:36.709  | 53 ms              | travou   |
        #   | roxo    19:56:08.022  | 695 ms             | travou   |
        #   | roxo    20:03:56      | NÃO (handle reusado)| OBEDECE |
        #   | branco  20:04:20.989  | 515 ms             | travou   |
        #
        # Os dois controles no MESMO rádio, no mesmo minuto — e o único que não
        # recebeu o report é o único que obedeceu. Controle negativo: o `0x08`
        # isolado, num controle conectado havia dez minutos (FORA da janela),
        # NÃO travou a barra. É essa assimetria que enganou duas sprints.
        #
        # E a intermitência que ela descrevia como *"sempre arrumamos mas
        # sempre volta"* é este bloco: `adopt_candidates` sai de `new_handles`,
        # então às vezes o report sai e às vezes não — o produto acertava ou
        # errava um sorteio a cada conexão.
        #
        # POR QUE REMOVER E NÃO ADIAR:
        #   1. ele NÃO cura — sem o `0x08` a barra obedece (evento 20:03:56);
        #   2. ele CAUSA o latch dentro da janela (7/7);
        #   3. ele APAGA os player-LEDs SEMPRE (medido isolado: `--x--` antes,
        #      tudo escuro depois) — todo reconnect BT apagava o número do
        #      jogador;
        #   4. o kernel DEFINE `DS_OUTPUT_VALID_FLAG1_RELEASE_LEDS` e NUNCA o
        #      envia (grep no hid-playstation.c: só a definição).
        #
        # O `build_bt_release_leds_report`/`send_release_leds` FICAM em
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
            # Modo Nativo (output mutado): o JOGO é dono do LED — não reenviar o
            # 0x08 (mesmo gate do reassert, que é no-op sob mute). Sem isso, um
            # wake em nativo escreveria no firmware por baixo do jogo.
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
        # `_handle` deixou de ser usado com a saída do `send_release_leds`
        # (LIGHTBAR-BT-CULPADO-01). Fica na tupla porque o snapshot sob lock é
        # compartilhado com o resto do bloco e reduzi-lo aqui não paga.
        for key, _handle, node, desired, transport in reclaim_candidates:
            with contextlib.suppress(Exception):
                from hefesto_dualsense4unix.core.lightbar_reset import (
                    should_reclaim_on_wake,
                )

                current = node.get_rgb() if node is not None else None
                reclamar = should_reclaim_on_wake(
                    transport, desired.led, current, KERNEL_DEFAULT_BLUE
                )
                # L-01 (auditoria 21/07): instrumentação do gate humano de
                # suspend/wake. A eficácia do RESET-02 depende de o kernel ter
                # reescrito a CLASSE sysfs para o azul-default no resume — o
                # estudo W12 sugere que ele NÃO reescreve em parte dos casos,
                # então a assinatura pode nunca casar. Este DEBUG (silencioso
                # em produção) mostra, por candidato, transport/current/desired
                # e a decisão — sem ele, um wake que não acende a lightbar é
                # indistinguível de "gatilho disparou mas falhou". Migrar o
                # gatilho (detector de suspend / nó recriado em handle BT
                # existente) fica para DEPOIS do gate humano, com este dado.
                logger.debug(
                    "lightbar_reclaim_avaliado",
                    key=key,
                    transport=transport,
                    current=current,
                    desired=desired.led,
                    kernel_default=KERNEL_DEFAULT_BLUE,
                    reclamar=reclamar,
                )
                # LIGHTBAR-BT-CULPADO-01 (03/08/2026): o `send_release_leds`
                # SAIU daqui também, pelo mesmo motivo do irmão acima — o
                # `0x08` trava a barra dentro da janela e apaga os player-LEDs
                # fora dela.
                #
                # Este gate (RESET-02) já era CÓDIGO MORTO EM REGIME, e agora
                # sabemos por quê de verdade: ele exige
                # `current_sysfs_rgb == KERNEL_DEFAULT_BLUE`, e o
                # `multi_intensity` mostra o valor PEDIDO, nunca o ACESO —
                # provado em 03/08, quando o nó nasceu `0 0 0` com a barra
                # acesa em azul. A condição está certa e é medida no lugar
                # errado. O `L-01` da auditoria de 21/07 já suspeitava
                # ("a assinatura pode nunca casar"); casou nunca.
                #
                # O DEBUG abaixo FICA: ele é a instrumentação que prova que o
                # gatilho não dispara, e é barato. Quando alguém aposentar o
                # RESET-02 de vez, `tests/unit/test_lightbar_reset.py:122-129`
                # é um teste-MURALHA (lê o texto-fonte deste arquivo e exige as
                # strings `should_reclaim_on_wake` e
                # `lightbar_reset_reenviado_wake`) e tem de ser encarado antes.
                if reclamar:
                    logger.debug("lightbar_reclaim_gatilho_disparou_sem_acao", key=key)

        # FEAT-DSX-LIGHTBAR-SYSFS-01: (re)mapeia os nós LED do kernel a cada tick
        # de hotplug — cobre controle novo E o nó LED que o kernel às vezes
        # registra com atraso após o hidraw; re-afirma a cor/player ativos nos
        # nós que acabaram de surgir.
        self._refresh_sysfs_leds()
        # re-aplica o perfil ativo nos controles recém-chegados.
        for key, handle in new_handles:
            # SOM-SEMPRE-01: o volume nasce em 100% em TODO controle adotado,
            # e nasce ANTES do perfil de propósito — quem tiver seção
            # `speaker` sobrescreve isto logo em seguida
            # (`reapply_speaker_after_connect`), e quem não tiver fica com o
            # som ligado em vez de ficar com o mudo que a bancada mediu.
            # Best-effort: nunca derruba a reaplicação do perfil.
            with contextlib.suppress(Exception):
                self.assumir_volume_padrao_na_adocao(key, handle)
            self._reapply_desired(key, handle)
        # COR-WAKE-01 (fix ao vivo 2026-07-17): re-resolve a cor/LED por-controle
        # em TODA reconciliação de hotplug/wake — não só nos handles/nós que
        # acabaram de surgir. Sintoma provado ao vivo: boot com os DualSense
        # dormindo em BT (ou um resume que faz o kernel resetar a classe LED sem
        # recriar o `inputN` — mesmo `indicator_dir`, logo NÃO é `new_key`)
        # deixava os dois controles na cor default do kernel
        # (`KERNEL_DEFAULT_BLUE` = 0,0,128) até uma ativação MANUAL de perfil.
        # `connect()` roda a cada `backend_hotplug_reconcile`, então este
        # reassert converge o físico ao resolvido (explícita > automática >
        # global) sozinho. É idempotente (reescreve a MESMA cor), pega o
        # `_io_lock` por conta própria e já é no-op em Modo Nativo (output
        # mutado — o jogo é dono do LED).
        self.reassert_resolved_outputs()

    def _close_handles(self, keep: set[str]) -> None:
        """Fecha (e remove) os handles cujas chaves não estão em `keep`.

        `handle.close()` para o report_thread e fecha o `hidapi.Device` — sem
        vazar thread/handle. Chamado sob `_io_lock`.
        """
        for key in [k for k in self._handles if k not in keep]:
            handle = self._handles.pop(key)
            with contextlib.suppress(Exception):
                handle.close()
        if self._primary_key is not None and self._primary_key not in self._handles:
            self._primary_key = None

    def _recompute_primary(self) -> None:
        """(Re)elege o primário e re-atrela evdev/transport SÓ quando ele muda.

        Primário = 1ª chave de inserção ainda presente (`next(iter(...))`).
        Controles novos entram no fim, então nunca roubam o primário de um já
        conectado; se o primário cai, promove o próximo mais antigo. Chamado sob
        `_io_lock`.
        """
        prev = self._primary_key
        if self._primary_key is None or self._primary_key not in self._handles:
            self._primary_key = next(iter(self._handles), None)
        if self._primary_key is None or self._primary_key == prev:
            return
        # Trocou o primário: re-detecta transport e re-atrela o evdev a ele.
        self._transport = self._detect_transport(self._handles[self._primary_key])
        # FEAT-DSX-CONTROLLER-IDENTITY-01: o reader passa a mirar o MAC do
        # primário (uniq do evdev == serial hidapi). Antes o finder pegava o
        # MENOR node — com 2+ controles, "menor node" e "primário do backend"
        # divergiam após re-enumeração e o P1 passava a ler OUTRO controle
        # (raiz da duplicação de input no co-op). `retarget` força reabrir no
        # node certo quando necessário.
        self._evdev.retarget(self.primary_uniq)
        # BUG-DAEMON-EVDEV-HOTPLUG-CACHE-01: o EvdevReader cacheia o path no
        # __init__. Se o daemon bootou offline (sem controle), o path ficava
        # None e o hotplug nunca o reavaliava — input caía no HID-raw cru
        # (sticks ~253 em repouso). Re-procura aqui, a cada troca de primário.
        self._evdev.refresh_device()
        # GYRO-01: o espelho de motion do P1 também segue o primário — larga o
        # hidraw antigo; o `path_provider` do reader re-resolve o novo sozinho.
        # Best-effort e não-bloqueante (só fecha um fd), seguro sob o _io_lock.
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
            for key in list(self._handles):
                handle = self._handles.pop(key)
                with contextlib.suppress(Exception):
                    handle.close()
            self._primary_key = None
            self._sysfs = {}

    def _refresh_sysfs_leds(self) -> None:
        """(Re)mapeia cada handle ao seu nó LED do kernel (FEAT-DSX-LIGHTBAR-SYSFS-01).

        Casa a `key` estável do handle (serial/MAC) com o MAC (`uniq`) do nó
        sysfs. Só usa um nó quando ele é GRAVÁVEL pelo usuário do daemon (regra
        udev aplicada) — gate anti-regressão: sem permissão, o controle fica fora
        do mapa e segue pelo caminho pydualsense histórico.

        Marca `_suppress_leds` nos handles cobertos (para o report_thread não
        disputar a lightbar com o kernel) e re-afirma a cor/player ativos nos nós
        que acabaram de surgir (cobre o nó LED que o kernel registra com atraso).

        STATUS-01 (priming + rastreio "escrito por nós"):
          - "nó novo" inclui o nó RECRIADO do mesmo controle (reconnect BT gera
            outro ``inputN`` — o ``indicator_dir`` muda): a classe LED renasce
            ZERADA no probe do kernel e precisa convergir de novo;
          - nó novo cuja cor resolvida é None recebe o azul-default do kernel
            (``KERNEL_DEFAULT_BLUE``) — escrita idempotente com o hardware, só
            para a classe LED espelhar a lightbar que o probe já acendeu;
          - toda escrita de COR bem-sucedida daqui é registrada em
            ``_sysfs_written`` (prova de posse do nó — é o que autoriza o
            handler IPC a ler ``multi_intensity`` como verdade e o único estado
            em que ``0 0 0`` significa "apagada");
          - exceção documentada: em Modo Nativo (muted) NADA disso roda — o
            jogo é dono do LED (o gate histórico cobre reassert E priming); o
            nó novo fica SEM rastreio e o estado por controle sai como
            "desired"/"desconhecida" até o unmute re-afirmar.
        """
        from hefesto_dualsense4unix.core import sysfs_leds

        try:
            by_mac = sysfs_leds.discover()
        except Exception as exc:  # ambiente sem /sys, etc. — degrada p/ pydualsense
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
        # Sem fallback single-controle: o casamento é SÓ por MAC. Controle real
        # sempre expõe o MAC (serial == HID_UNIQ) em USB e BT, então o match é
        # confiável; um handle sem MAC (ou um nó de outra máquina) NUNCA é casado
        # por coincidência — evita acoplar a um nó errado e mantém os testes
        # herméticos. Quem não casa segue pelo caminho pydualsense (USB funciona).

        # LIGHTBAR-BT-ADOPT-01 (telemetria): a cobertura sysfs muda raramente
        # (adoção, replug, regra udev) — logar em INFO torna DATÁVEL uma futura
        # regressão de lightbar (a de 2026-07-17 não tinha registro; o logging
        # de LED era debug-only e a janela da quebra ficou sem timestamp).
        # Dispara também quando o conjunto DESCOBERTO muda (handle presente sem
        # nó sysfs): foi exatamente o ponto cego que escondeu a reconexão
        # envenenada de 2026-07-18 00:53 (o 14:3a entrou em `keys` sem nó e o
        # log de cobertura não disparou).
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

        # Marca supressão de LED no report_thread. Coberto pelo sysfs => o
        # kernel é o dono (design original).
        # LIGHTBAR-BT-NEVER-01 (política, estudo 2026-07-18): por BLUETOOTH o
        # FLUXO do `report_thread` fica SEMPRE LED-neutro, coberto ou não. Em
        # USB o fallback histórico segue.
        #
        # DUAS DAS TRÊS RAZÕES ORIGINAIS CADUCARAM, e ficam registradas aqui
        # em vez de sobreviverem como fato (regra dela, 11/08: fato errado se
        # SUBSTITUI; o que se preserva é o custo já pago, não o número):
        #
        #  1. *"o report BT da pydualsense 0.7.5 é MALFORMADO"* — verdade em
        #     18/07, IRRELEVANTE desde 19/07: o `prepareReport` daqui não usa
        #     mais o report dela. O BTREPORT-02 monta o 0x31 do kernel (tag
        #     0x10, seq por handle, CRC-32) em `core/ds_output_report.py`;
        #  2. *"a cor via pydualsense NUNCA funcionou por BT"* — consequência
        #     de (1), e derrubada por MEDIÇÃO em 12/08: o 0x31 bem-formado
        #     escrito no `hidraw` pintou os três controles do rádio com a
        #     Steam viva (ensaio `cor-rota-hidraw-com-steam`), no mesmo
        #     instante em que o sysfs não pintava nenhum;
        #  3. *"um write com flags de LED dentro da janela LATCHEIA a barra"* —
        #     esta ERROU O CULPADO, e quem provou foi esta casa: o
        #     LIGHTBAR-BT-CULPADO-01 (03/08) correlacionou 7 de 7 o latch com o
        #     `0x08` (RELEASE_LEDS) que NÓS mandávamos na janela, e ele saiu do
        #     código em `108b711` (04/08). Julho acertou a janela e errou o
        #     report.
        #
        # O QUE SUSTENTA A POLÍTICA HOJE, e é medido: o LIGHTBAR-BT-KEEPALIVE-01
        # (22/07) — reengatar a máquina de estados da lightbar EM REGIME trava a
        # exibição no firmware (o registrador aceita a cor, o sysfs mostra, a
        # barra fica apagada). É uma afirmação sobre o FLUXO a 2-60 Hz, não
        # sobre o transporte: por isso a supressão continua, e a rota que
        # voltou a existir por rádio é a escrita AVULSA e estreita, fora do
        # fluxo (`_pintar_por_hidraw_bt` / `reescrever_lightbar_por_hidraw`).
        for key, handle in handles.items():
            with contextlib.suppress(Exception):
                # `_suppress_leds` existe no _PinnedPyDualSense (handles de teste
                # podem não ter — daí o suppress(Exception)).
                handle._suppress_leds = (
                    key in mapping or self._detect_transport(handle) == "bt"
                )

        # Re-afirma o perfil de LED ativo nos nós que SURGIRAM agora (cor que o
        # kernel ainda não tinha ou perdeu no connect/resume).
        # FEAT-PARITY-REVIEW-01: em Modo Nativo (muted) NÃO re-afirma — o jogo é
        # dono do LED; o desejado segue guardado e o unmute o re-aplica.
        # PERFIL-01: o valor re-afirmado é o MERGE por controle (default +
        # override do uniq DESTE nó) — nunca o desejado de outro controle.
        # STATUS-01: nó RECRIADO (mesmo MAC, `indicator_dir` diferente) também é
        # "novo" — a classe LED dele renasceu zerada. `getattr` defensivo: nós
        # dublados em teste podem não ter `indicator_dir` (aí compara None==None
        # e nada re-prima à toa).
        def _node_dir(node: Any) -> Any:
            return getattr(node, "indicator_dir", None)

        new_keys = [
            k
            for k in mapping
            if k not in prev or _node_dir(prev[k]) != _node_dir(mapping[k])
        ]
        if not self._output_mute and new_keys:
            with self._io_lock:
                reasserts = [
                    (key, mapping[key], self._merged_desired_for_key(key))
                    for key in new_keys
                ]
            for key, node, desired in reasserts:
                with contextlib.suppress(Exception):
                    # Priming (STATUS-01, refutação 1): sem cor resolvida, a
                    # classe zerada do probe converge para o azul que o kernel
                    # de fato acendeu — e a escrita entra no rastreio (só assim
                    # o handler pode confiar na leitura do nó).
                    cor = desired.led if desired.led is not None else KERNEL_DEFAULT_BLUE
                    if node.set_rgb(*cor):
                        self.record_sysfs_write(key, cor)
                    if desired.player_leds is not None and (
                        self._pode_escrever_player_leds()
                    ):
                        node.set_players(desired.player_leds)

        with self._io_lock:
            self._sysfs = mapping
            # Poda do rastreio: nó que saiu do mapa (controle desconectou /
            # perdeu gravabilidade) não tem mais escrita nossa válida — quando
            # voltar, entra como new_key e o priming/reassert re-registra.
            self._sysfs_written = {
                key: rgb for key, rgb in self._sysfs_written.items() if key in mapping
            }

    def record_sysfs_write(self, key: str, rgb: tuple[int, int, int]) -> None:
        """Registra que NÓS escrevemos `rgb` na classe LED do controle `key`.

        STATUS-01 — metade pública do rastreio "escrito por nós": os caminhos
        de escrita sysfs de cor fora desta função (`_for_each_led` do
        `set_led`, `_write_partial_output` do hotplug/`apply_output_for`, o
        reassert do unmute em `set_output_mute`) podem chamá-lo na borda da
        escrita bem-sucedida. Janela ACEITA e documentada (decisão do sprint):
        enquanto esses call sites não chamam (estão fora da fronteira desta
        entrega), o rastreio guarda a cor da última passada de
        priming/reassert — o que ainda basta para o handler IPC, porque o
        rastreio é prova de POSSE do nó (todas as escritas subsequentes do
        backend nesse nó também vão via sysfs) e a COR exibida vem da leitura
        viva (`SysfsLedNode.get_rgb`), não daqui. Em particular, o unmute do
        Modo Nativo re-escreve a MESMA cor resolvida que a última passada já
        registrou.
        """
        with self._io_lock:
            self._sysfs_written[key] = (int(rgb[0]), int(rgb[1]), int(rgb[2]))

    def is_connected(self) -> bool:
        # "Qualquer controle conectado". `ds.connected` é o canônico do
        # pydualsense (bool). AUDIT-FINDING-LOG-EXC-INFO-01: default conservador
        # `False` quando o atributo está ausente (estado desconhecido).
        with self._io_lock:
            handles = list(self._handles.values())
        return any(bool(getattr(h, "connected", False)) for h in handles)

    def heal_evdev_if_stale(self) -> bool:
        """Watchdog HID x evdev: se o evdev reader ficou preso num node OBSOLETO
        (re-enumeração pós storm -71 / replug, sem ENODEV), força reabrir.

        Retorna True se disparou o reopen. No-op (False) sem reader disponível.
        FEAT-DSX-EVDEV-WATCHDOG-01 — chamado pelo poll loop só com o HID
        conectado (o cross-check) e em intervalo throttled (escaneia /dev/input).
        """
        if not self._evdev.is_available():
            return False
        if self._evdev.is_stale():
            self._evdev.request_reopen("hid_connected_but_evdev_node_changed")
            return True
        return False

    def read_state(self) -> ControllerState:
        # INPUT vem SEMPRE do controle PRIMÁRIO (`self._ds`). Emulação de
        # mouse/teclado/gamepad é, portanto, single-controller por construção.
        ds = self._ds
        # BUG-DAEMON-NO-DEVICE-FATAL-01: quando offline, devolve snapshot
        # neutro em vez de levantar. Daemon segue rodando o poll_loop e
        # publica estado vazio para CLI/GUI/IPC.
        if ds is None:
            return ControllerState(
                battery_pct=0,
                l2_raw=0,
                r2_raw=0,
                connected=False,
                transport=self._transport,
                raw_lx=128,
                raw_ly=128,
                raw_rx=128,
                raw_ry=128,
                buttons_pressed=frozenset(),
            )
        # BUG-TRANSPORT-CACHE-STALE-01 (v3.2.1): re-detecta transport a cada
        # tick em vez de só no connect(). Quando o controle troca USB <-> BT
        # sem desconectar (cabo plugado/desplugado com BT pareado), o
        # pydualsense atualiza `conType` mas o cached `_transport` ficava
        # stale, fazendo a CLI/GUI mostrarem o transporte errado por horas.
        # Custo: 1 getattr + 1 string check por tick (~60Hz) — desprezível.
        self._transport = self._detect_transport(ds)
        battery = self._read_battery_raw(ds)
        # HOTFIX-2: evdev é fonte primária de input quando disponível.
        if self._evdev.is_available():
            snap = self._evdev.snapshot()
            # Consolida botões: evdev (ramo primário) + HID-raw do Mic (INFRA-MIC-HID-01).
            # O botão Mic não tem keycode evdev estável — vem por `ds.state.micBtn`
            # (byte misc2, bit 0x04). Tratamento defensivo: primeiro tick pode
            # ter state cru antes do firmware enviar o primeiro report completo.
            buttons = set(snap.buttons_pressed)
            try:
                if bool(getattr(ds.state, "micBtn", False)):
                    buttons.add("mic_btn")
            except AttributeError:  # state cru no primeiro tick — ds.state pode faltar atributos
                logger.debug("ds_state_mic_btn_indisponivel_evdev_path", exc_info=True)
            buttons_pressed = frozenset(buttons)
            return ControllerState(
                battery_pct=battery,
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
        # Fallback pydualsense: HOTFIX-1 corrigiu os atributos, mas em
        # runtime com hid_playstation ativo os valores não atualizam.
        # Sem evdev, botões evdev ficam vazios; apenas `micBtn` (HID-raw) é
        # garantido pelo pydualsense mesmo neste ramo.
        state = ds.state
        l2_raw = int(getattr(state, "L2_value", 0)) & 0xFF
        r2_raw = int(getattr(state, "R2_value", 0)) & 0xFF
        buttons_fallback: frozenset[str] = frozenset()
        try:
            if bool(getattr(state, "micBtn", False)):
                buttons_fallback = frozenset({"mic_btn"})
        except AttributeError:
            logger.debug("ds_state_mic_btn_indisponivel_fallback_path", exc_info=True)
        # FEAT-MOUSE-CURSOR-FEEL-01 (A6): sticks da pydualsense são centrados
        # em 0 — reconverter para cru 0-255. L2/R2 NÃO passam por aqui: já são
        # crus 0-255 na lib (não somar 128 neles).
        return ControllerState(
            battery_pct=battery,
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

    # --- output (fan-out p/ TODOS os controles) -------------------------

    def _for_each(
        self,
        op: Callable[[pydualsense], None],
        *,
        what: str,
        broadcast: bool = False,
        record: dict[str, Any] | None = None,
    ) -> None:
        """Aplica `op` ao ALVO de output (ou a cada handle aberto, em broadcast).

        FEAT-DSX-CONTROLLER-SELECTOR-01: se `_output_target_key` está setada E o
        controle ainda está presente em `_handles`, aplica SÓ a esse handle;
        senão (sem alvo, ou alvo desconectou), volta ao broadcast histórico —
        TODOS os controles. 1 handle morto não derruba os outros.

        PERFIL-01: `broadcast=True` IGNORA o seletor (broadcast real — o
        caminho do perfil, que não pode ser sequestrado pelo alvo da GUI);
        `record` grava os campos no estado desejado do MESMO escopo resolvido
        aqui, sob o MESMO lock — alvo e registro nunca divergem (a corrida do
        seletor global mutável que a revisão apontou). O registro acontece
        mesmo offline (perfil ativado sem controle vale para o hotplug).

        Tira um snapshot da lista sob `_io_lock` e faz o HID I/O fora da seção
        crítica (não segura o lock durante a escrita no device).
        """
        with self._io_lock:
            target = self._output_target_key
            if not broadcast and target is not None and target in self._handles:
                handles = [(target, self._handles[target])]
            else:
                target = None
                handles = list(self._handles.items())
            if record:
                self._record_desired_locked(target, record)
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
        """`_for_each` cuja `op` recebe a KEY do handle junto (POR-UNIDADE-01).

        Mesma resolução de alvo, mesmo tratamento de falha por handle, mesmo
        I/O fora do `_io_lock`. A diferença é a única que a escala por peça
        exige: a `op` precisa saber EM QUEM está escrevendo para resolver o
        fator daquela unidade. Sem `record` de propósito — quem usa isto (o
        rumble) é TRANSITÓRIO e nunca entra no estado desejado.
        """
        with self._io_lock:
            target = self._output_target_key
            if not broadcast and target is not None and target in self._handles:
                handles = [(target, self._handles[target])]
            else:
                handles = list(self._handles.items())
        if not handles:
            logger.debug("output_offline_noop", op=what)
            return
        for key, handle in handles:
            try:
                op(handle, key)
            except Exception as exc:
                logger.warning("output_handle_failed", op=what, key=key, err=str(exc))

    def suprimir_player_leds(self, ativo: bool) -> bool:
        """Liga/desliga a escrita dos LEDs de JOGADOR. Instrumento de eliminação.

        LIGHTBAR-ISOLAR-OS-PLAYERS-01 (08/08/2026) — hipótese DELA, e o método é
        o mesmo que ela usou para mapear a lightbar: *"vamos isolar os leds dos
        players então. igual fizemos naquele dia com o lightbar"*.

        A pergunta: **é a escrita do LED de jogador que derruba o claim da
        lightbar quando o controle acaba de conectar?** O que aponta para lá:

        - o 0x08, que DEVOLVE a barra, **apaga os players** (medido ao vivo hoje,
          23:35) — as duas coisas vivem na mesma máquina de estados do firmware;
        - a barra apaga quando o controle **acaba de conectar** (observação dela,
          08/08), e é exatamente aí que o priming escreve os players;
        - um restart do daemon com o controle JÁ conectado pinta a barra sem
          problema (journal, 23:33:10) — mesma adoção, sem conexão nova.

        **É comutável ao vivo, e isso é a metade que importa.** O experimento de
        23:35 se perdeu porque o instrumento exigia reiniciar o daemon, e o
        restart curou a barra antes do gesto que eu queria medir. Aqui ela liga a
        supressão com o controle na mão, desliga e religa o controle, e olha —
        sem nada mais mudar no meio.

        Devolve o estado que ficou. Não persiste: um restart volta ao normal, de
        propósito — instrumento esquecido ligado é defeito com data marcada.
        """
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
        uma — a armadilha `A-12` de `docs/process/METODO-DE-ISOLAMENTO.md`, "o
        caderno envelhecer sem que ninguém note".

        A escavação do journal do daemon e dos transcritos, em 11/08, achou a
        barra **ACESA** no rádio DENTRO daqueles cinco dias, quatro vezes, três
        delas com fala literal dela: 08/08 16:39, 08/08 21:35, 08/08 23:48 e
        11/08 11:40 (ensaios `lightbar-bt-aceso-*` em `docs/data/ensaios.csv`;
        a correção está registrada no ensaio `lightbar-bt-sem-0x08-cinco-dias`,
        e a nota datada em `docs/process/METODO-DE-ISOLAMENTO.md`, seção "O que
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
          `docs/process/METODO-DE-ISOLAMENTO.md`.

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
                handle = self._handles.get(uniq)
                alvos = [(uniq, handle)] if handle is not None else []
            else:
                alvos = list(self._handles.items())
        resultado: dict[str, bool] = {}
        for key, handle in alvos:
            ok = send_release_leds(handle)
            resultado[key] = ok
            logger.info("lightbar_reset_sob_demanda", key=key, enviado=ok)
            if not ok:
                continue
            # O 0x08 zera o estado de LED do firmware, então o cache do nó
            # sysfs passa a mentir sobre o que está aceso: sem invalidar, a
            # próxima escrita da MESMA cor seria pulada e a barra ficaria
            # apagada com o produto achando que já pintou. Vinha junto do
            # reset original e foi removido junto com ele em `108b711`.
            no = self._sysfs.get(key) if isinstance(self._sysfs, dict) else None
            invalidar = getattr(no, "invalidate_cache", None)
            if callable(invalidar):
                invalidar()
        return resultado

    def consumir_conexoes_bt_novas(self) -> int:
        """Quantas conexões novas pelo RÁDIO desde a última leitura, e zera.

        GATILHO-DA-COR-01 — o sinal do gatilho da cor. Consome de propósito: o
        chamador (`daemon/connection.py`) ARMA o debounce com o número, e uma
        conexão contada duas vezes viraria uma sequência que nunca fecha.
        """
        with self._io_lock:
            n = self._conexoes_bt_novas
            self._conexoes_bt_novas = 0
            return n

    def consumir_pinturas_de_lightbar(self) -> int:
        """Quantas vezes o produto pintou a barra pelo rádio, e zera.

        ESCRITOR-CRU-01 — o segundo sinal do gatilho da cor, irmão do
        `consumir_conexoes_bt_novas`. Consome pela MESMA razão: o chamador arma
        o debounce com o número, e uma pintura contada duas vezes viraria uma
        sequência que nunca fecha.

        **Não conta a reafirmação do próprio gatilho**, e isso é requisito, não
        detalhe: quem repinta no silêncio é o `reescrever_lightbar_por_hidraw`,
        que não passa por aqui. Se passasse, cada disparo armaria o gatilho de
        novo e a cura viraria o martelo que o GUERRA-01 tirou do produto.
        """
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

        **3. Por que o Modo Nativo é no-op.** Regra dela, literal: *"no modo
        nativo devolvemos o controle pra steam e no modo conexão também, todo o
        resto é o hefesto"*. O portão é o `_output_mute` que já existe — o
        mesmo que o `reassert_resolved_outputs` e o `defend_display` usam; em
        Modo Nativo / Conexão Nativa (Sony) o dono do hidraw é o jogo, e um
        report nosso por baixo dele violaria o contrato de zero write.

        **4. Por que a escrita é INCONDICIONAL — sem cache, sem dedup.**
        MEDIDO em 12/08/2026: com as três barras apagadas pela Steam, um
        restart do daemon registrou três vezes
        ``lightbar_reassert_skip_cache`` (`core/sysfs_leds.py:198`) e não
        reescreveu nada; as três barras continuaram apagadas, e ela confirmou
        *"todas apagadas mas em nenhum momento os controles desligaram"*. A
        razão está admitida no próprio código: o ``multi_intensity`` mostra o
        valor PEDIDO, nunca o ACESO (`core/sysfs_leds.py:92-104`), e escrita
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
        rádio" ou "Modo Nativo" — resposta, não erro; best-effort por handle,
        e a falha de um nunca aborta os outros.
        """
        from hefesto_dualsense4unix.core.lightbar_gatilho import (
            build_bt_lightbar_report,
        )

        with self._io_lock:
            if self._output_mute:
                logger.info("gatilho_da_cor_no_op_modo_nativo")
                return {}
            pode_player = self._pode_escrever_player_leds()
            alvos = [
                (key, handle, self._merged_desired_for_key(key))
                for key, handle in self._handles.items()
                if self._detect_transport(handle) == "bt"
            ]
        resultado: dict[str, bool] = {}
        for key, handle, desired in alvos:
            cor = desired.led if desired.led is not None else KERNEL_DEFAULT_BLUE
            # LIGHTBAR-ISOLAR-OS-PLAYERS-01: o instrumento de eliminação dela
            # vale AQUI também — se ele está ligado, o número não sai, e o
            # report vai só com a cor (o bit do jogador nem é autorizado).
            players = desired.player_leds if pode_player else None
            ok = False
            try:
                report = build_bt_lightbar_report(cor, players)
                # LIGHTBAR-BT-RESET-03: pelo `writeReport` do handle, que
                # carimba o `seq` do FLUXO daquele handle e recalcula o CRC.
                # Escrever cru no `device` com seq 0 já matou uma cura desta
                # casa uma vez — o firmware descarta o report fora de sequência
                # e o log diz "escrito" com a barra apagada.
                escritor = getattr(handle, "writeReport", None)
                if callable(escritor):
                    escritor(list(report))
                    ok = True
                else:
                    device = getattr(handle, "device", handle)
                    escrito = device.write(report)
                    ok = escrito is None or int(escrito) == len(report)
            except Exception as exc:
                logger.warning("gatilho_da_cor_falhou", key=key, err=str(exc))
            resultado[key] = ok
            logger.info(
                "gatilho_da_cor_escrito",
                key=key,
                cor=cor,
                players=players,
                enviado=ok,
            )
        return resultado

    # --- aviso de modo na lightbar (AVISO-DE-MODO-01) --------------------

    def pintar_lightbar_sem_lembrar(self, rgb: tuple[int, int, int]) -> int:
        """Pinta `rgb` em TODOS os controles SEM tocar no estado desejado.

        AVISO-DE-MODO-01 (19/08/2026). É o irmão do `set_led` para o caso do
        AVISO: a cor tem de aparecer agora e **sumir depois**, devolvendo a cor
        que ela escolheu. Três diferenças, todas deliberadas:

        1. **Não grava `record=`.** O `set_led` grava a cor no estado desejado
           — e no caminho broadcast o `_record_desired_locked` ainda LIMPA o
           campo `led` de todos os overrides por-uniq. Um aviso que passasse
           por ali apagaria o perfil dela de verdade: o `reassert` seguinte
           devolveria a cor do AVISO, não a dela. Aqui nada é lembrado, então
           `restaurar_lightbar_do_perfil` tem o que devolver.
        2. **`broadcast=True` sempre.** Ela pediu "o lightbar de TODOS pisca" —
           o seletor de controle da janela não pode calar o aviso nos outros.
        3. **Passa `rgb=` para a rota avulsa por hidraw.** Por rádio, com outro
           processo (a Steam) segurando o nó, o `multi_intensity` não pinta e o
           `0x31` avulso pinta (ROTA-BT-EM-REGIME-01, 12/08/2026). O
           `_for_each_led` já manda os dois quando recebe o valor em forma de
           dado.

        Em Modo Nativo (`_output_mute`) é no-op: ali o dono do LED é o jogo, e
        essa é a mesma regra do `reassert_resolved_outputs` e do
        `reescrever_lightbar_por_hidraw`. O aviso de ENTRADA no Modo Nativo
        ainda sai, porque quem o dispara roda antes do mute (ver
        `daemon/subsystems/gamepad.stop_gamepad_emulation`).

        Devolve **quantos controles receberam a escrita** — nunca "quantos
        acenderam". Não há como saber o segundo: o `multi_intensity` é a
        memória do último valor PEDIDO pela classe LED, não a verdade do
        hardware, e escrita por hidraw nem o atualiza.
        """
        with self._io_lock:
            if self._output_mute:
                logger.debug("aviso_de_modo_no_op_modo_nativo")
                return 0
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
        """Devolve a TODOS os controles a cor que o perfil resolve. AVISO-DE-MODO-01.

        O par do `pintar_lightbar_sem_lembrar`. A cor não é inventada aqui: sai
        do `_merged_desired_for_key`, o MESMO merge de camadas que o hotplug, o
        reassert e o gatilho da cor usam — sem cor resolvida, o azul-default do
        kernel, que é a mesma escolha do priming (controle virgem nasce aceso,
        não apagado).

        Escreve pelo `_write_partial_output`, e é por isso que ele: cobre as
        TRÊS rotas de uma vez (sysfs, `0x31` avulso por rádio e o fallback
        pydualsense do cabo) e falha por controle sem abortar os outros — o
        caso medido do rádio travado registra no journal e o resto segue.

        Só o campo `led` é devolvido. Reaplicar o `_DesiredOutput` inteiro
        traria gatilhos e número de jogador junto, que o aviso nunca tocou —
        devolver o que não se tirou é mudança que ela não pediu.
        """
        with self._io_lock:
            if self._output_mute:
                return 0
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
                    False,
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
        """Pisca `vezes` rápido na cor do modo novo e DEVOLVE a cor dela.

        AVISO-DE-MODO-01, pedido dela em 19/08/2026: *"o lightbar de todos
        pisca 3 vezes rápido"* na cor do modo em que se acabou de entrar.

        **A piscada é por COR, nunca por brilho.** O mapa de canais mede
        `luz.lightbar.brilho` com `aciona=não` nos DOIS transportes — mexer no
        `brightness` não apaga nada. Apagado aqui é escrever preto.

        **BLOQUEANTE de propósito** (`time.sleep`): a sequência tem de ficar
        junta, e um `await` no meio a deixaria intercalada com o resto do laço.
        Quem chama do laço de eventos joga isto numa thread — é o que o
        `daemon/subsystems/hotkey._disparar_piscada` faz.

        O `finally` é o contrato: **qualquer** saída — inclusive uma exceção no
        meio — devolve a cor do perfil. Um aviso que rouba a cor dela e não
        devolve é defeito, não cura.

        Devolve quantos controles receberam a PRIMEIRA escrita (mesma ressalva
        do `pintar_lightbar_sem_lembrar`: escrita recebida, não barra acesa).
        """
        alcancados = 0
        try:
            for volta in range(max(1, vezes)):
                escritas = self.pintar_lightbar_sem_lembrar(rgb)
                if volta == 0:
                    alcancados = escritas
                if not escritas:
                    # Ninguém para avisar (mesa vazia ou Modo Nativo já mudo):
                    # dormir a sequência inteira seria segurar a thread à toa.
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
        """Aplica um output de LED ao ALVO, preferindo a rota sysfs do kernel.

        Mesma resolução de alvo do `_for_each` (seletor de controle ou broadcast),
        mas, por handle: tenta o nó LED do kernel (cor funciona em USB E BT) e, se
        não houver nó coberto ou a escrita falhar, cai no caminho pydualsense
        (hidraw) — garantindo nenhum regresso quando a regra udev não está
        aplicada. FEAT-DSX-LIGHTBAR-SYSFS-01.

        PERFIL-01: `broadcast`/`record` idênticos ao `_for_each` — alvo e
        registro do estado desejado resolvidos juntos, sob o mesmo lock.

        ROTA-BT-EM-REGIME-01: `rgb`/`players` são o MESMO valor que o
        `sysfs_op` escreveria, em forma de dado — é o que permite acrescentar
        a rota hidraw por Bluetooth (`_pintar_por_hidraw_bt`) sem desmontar as
        closures. Omitidos = comportamento histórico byte-idêntico.
        """
        with self._io_lock:
            target = self._output_target_key
            if not broadcast and target is not None and target in self._handles:
                items = [(target, self._handles[target])]
            else:
                target = None
                items = list(self._handles.items())
            if record:
                self._record_desired_locked(target, record)
            sysfs_map = dict(self._sysfs)
            muted = self._output_mute
        if not items:
            logger.debug("output_offline_noop", op=what)
            return
        for key, handle in items:
            node = sysfs_map.get(key)
            # FEAT-PARITY-REVIEW-01: em Modo Nativo (muted) o JOGO é dono do LED
            # do controle. A rota sysfs escreve DIRETO no /sys (fora do
            # report_thread, que o mute cobre), então sem este gate um perfil/
            # reassert de player-LED/lightbar pisaria no número que o jogo setou.
            # `_desired` já guarda o valor (setado pelo caller) e o unmute o
            # re-aplica ao sysfs — aqui só evitamos tocar o hardware. O pydual_op
            # abaixo apenas atualiza o estado interno (o report_thread mutado não
            # escreve), mantendo o handle coerente para o próximo unmute.
            escreveu_sysfs = False
            if node is not None and not muted:
                try:
                    escreveu_sysfs = bool(sysfs_op(node))
                except Exception as exc:
                    logger.debug(
                        "sysfs_led_falhou_fallback_pydual", op=what, key=key, err=str(exc)
                    )
            # ROTA-BT-EM-REGIME-01: por rádio a rota sysfs NÃO basta, e isso é
            # medido — ver `_pintar_por_hidraw_bt`. O report vai junto, tenha
            # o sysfs escrito ou não; em Modo Nativo (`muted`) é no-op.
            if not muted:
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
        """
        with self._io_lock:
            node = self._sysfs.get(key)
            muted = self._output_mute
            desired = self._merged_desired_for_key(key)
            uniq = self._key_to_uniq(key)
            game_triggers = (
                dict(self._game_triggers_by_uniq.get(uniq, {}))
                if uniq is not None
                else {}
            )
        for side, block in game_triggers.items():
            attr = "_raw_trigger_left" if side == "left" else "_raw_trigger_right"
            with contextlib.suppress(Exception):
                setattr(handle, attr, block)
        self._write_partial_output(
            handle, node, muted, desired, what="reapply_perfil_no_hotplug"
        )

    def _pintar_por_hidraw_bt(
        self,
        key: str | None,
        handle: pydualsense,
        *,
        rgb: tuple[int, int, int] | None,
        players: tuple[bool, bool, bool, bool, bool] | None,
        what: str,
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

        Devolve True quando escreveu. No-op (False) fora do rádio, sem valor
        para escrever, ou quando o handle não sabe carimbar o `seq`.
        """
        if rgb is None and players is None:
            return False
        if self._detect_transport(handle) != "bt":
            return False
        # LIGHTBAR-BT-RESET-03: pelo `writeReport` do handle, que carimba o
        # `seq` do FLUXO daquele handle e recalcula o CRC. Um 0x31 escrito cru
        # com seq 0 é descartado pelo firmware, e o sintoma é o pior de todos:
        # o log diz "escrito" e a barra não muda.
        escritor = getattr(handle, "writeReport", None)
        if not callable(escritor):
            return False
        from hefesto_dualsense4unix.core.lightbar_gatilho import (
            build_bt_lightbar_report,
        )

        try:
            escritor(list(build_bt_lightbar_report(rgb, players)))
        except Exception as exc:
            logger.debug("lightbar_hidraw_bt_falhou", op=what, key=key, err=str(exc))
            return False
        # ESCRITOR-CRU-01: este é o "comando nosso" da medição de 16/08. Só
        # conta a escrita que SAIU (o `except` acima não chega aqui): armar o
        # gatilho por uma escrita que falhou seria reafirmar em cima de nada.
        with self._io_lock:
            self._pinturas_de_lightbar += 1
        logger.debug(
            "lightbar_hidraw_bt_escrito",
            op=what,
            key=key,
            cor=rgb,
            player=players,
        )
        return True

    def _write_partial_output(
        self,
        handle: pydualsense,
        node: Any,
        muted: bool,
        out: _DesiredOutput,
        *,
        what: str,
    ) -> bool:
        """Escreve os campos NÃO-None de `out` em UM handle. Devolve se DEU CERTO.

        Gatilhos e LED do mic vão sempre por pydualsense (o kernel não os expõe).
        Lightbar e player-LED vão pelo nó sysfs do kernel quando o controle está
        coberto (cor em USB E BT); senão, por pydualsense (fallback histórico).

        FEAT-PARITY-REVIEW-01: em Modo Nativo (muted) a rota sysfs de LED é
        desabilitada (o jogo é dono do LED). `node and not muted` mantém o
        fallback: sem sysfs disponível, o LED cai em handle.light — mas o
        report_thread também está mutado, então nada chega ao hardware; o
        estado interno fica coerente para o unmute re-aplicar.

        ROTA-BT-EM-REGIME-01: por rádio, cor e número saem TAMBÉM pelo report
        `0x31` avulso (`_pintar_por_hidraw_bt`) — é este o caminho do perfil e
        do hotplug, e por rádio o `sysfs` sozinho perde para quem tem o
        `hidraw` aberto. Uma escrita por ação, nunca no fluxo do
        `report_thread`.

        **Conserto 1.3 — o retorno.** A captura de exceção continua a mesma (a
        falha de um controle não pode abortar o laço de quem chama em cima de
        vários), mas ela deixa de ser INVISÍVEL: quem chama recebe ``False`` e
        pode dizer a verdade. O `apply_output_for` respondia "escreveu" a uma
        escrita que levantou `OSError` porque só o log sabia da falha.
        """
        from pydualsense.enums import PlayerID

        try:
            if out.trigger_left is not None:
                self._apply_trigger(handle, "left", out.trigger_left)
            if out.trigger_right is not None:
                self._apply_trigger(handle, "right", out.trigger_right)
            if out.led is not None and not (
                node is not None and not muted and node.set_rgb(*out.led)
            ):
                handle.light.setColorI(*out.led)
            if (
                out.player_leds is not None
                and self._pode_escrever_player_leds()
                and not (
                    node is not None
                    and not muted
                    and node.set_players(out.player_leds)
                )
            ):
                mask = sum(1 << i for i, b in enumerate(out.player_leds) if b)
                handle.light.playerNumber = PlayerID(mask)
            if out.mic_led is not None:
                _escrever_led_do_mic(handle, out.mic_led)
            if not muted:
                self._pintar_por_hidraw_bt(
                    None,
                    handle,
                    rgb=out.led,
                    players=(
                        out.player_leds
                        if self._pode_escrever_player_leds()
                        else None
                    ),
                    what=what,
                )
        except Exception as exc:
            logger.warning("reapply_perfil_no_hotplug_falhou", op=what, err=str(exc))
            return False
        return True

    def set_trigger(self, side: Side, effect: TriggerEffect) -> None:
        # PERFIL-01: o registro no estado desejado vai para o ESCOPO do alvo
        # (broadcast → default; alvo selecionado → override por-uniq), junto
        # com a resolução do alvo, sob o mesmo lock (`record=`).
        campo = "trigger_left" if side == "left" else "trigger_right"
        self._for_each(
            lambda h: self._apply_trigger(h, side, effect),
            what="set_trigger",
            record={campo: effect},
        )

    def set_led(self, color: tuple[int, int, int]) -> None:
        r, g, b = color
        # Prefere a rota sysfs do kernel (cor funciona em USB E BT); cai no
        # pydualsense (hidraw) quando o controle não está coberto.
        self._for_each_led(
            sysfs_op=lambda node: node.set_rgb(r, g, b),
            pydual_op=lambda h: h.light.setColorI(r, g, b),
            what="set_led",
            record={"led": color},
            # ROTA-BT-EM-REGIME-01: por rádio, a cor sai TAMBÉM pelo 0x31
            # avulso — a rota que venceu a Steam na mesa dela em 12/08.
            rgb=(r, g, b),
        )

    def set_rumble(self, weak: int, strong: int) -> None:
        # Rumble é TRANSITÓRIO (efeito de jogo) — NÃO entra em `_desired`, logo
        # não é "ressuscitado" num controle plugado depois.
        #
        # POR-UNIDADE-01: o valor pedido continua sendo UM (o do jogo, o do
        # teste de motores, o do keepalive); o que muda por peça é o FATOR do
        # perfil. `_escalar_rumble` devolve o par intacto quando a unidade não
        # tem opinião — sem escalas registradas isto é byte-idêntico ao que
        # era. O escopo (alvo do seletor ou broadcast) segue do `_for_each`.
        def _do(handle: pydualsense, key: str) -> None:
            eff_weak, eff_strong = self._escalar_rumble(key, weak, strong)
            handle.setLeftMotor(eff_strong)
            handle.setRightMotor(eff_weak)

        self._for_each_com_key(_do, what="set_rumble")

    def _escalar_rumble(self, key: str, weak: int, strong: int) -> tuple[int, int]:
        """Aplica a escala de vibração por-uniq da `key` (POR-UNIDADE-01).

        Espelho de `_scaled_led`, um andar acima: lê o fator registrado por
        `set_rumble_scales` e satura em 0-255. Sem fator (o caso de todo
        perfil de antes desta linha) devolve o par recebido SEM tocar nele —
        nenhum arredondamento novo entra no caminho de quem não pediu nada.

        Não segura `_io_lock`: é chamado de dentro do laço de I/O do
        `_for_each_com_key`, que já soltou o lock de propósito (o HID write
        não pode acontecer sob lock). O dict é substituído inteiro em
        `set_rumble_scales` — leitura de referência é atômica no CPython e o
        pior caso é um tick com o fator anterior, que o próximo report corrige.
        """
        uniq = self._key_to_uniq(key)
        fator = self._rumble_scale_by_uniq.get(uniq) if uniq is not None else None
        if fator is None:
            return weak, strong
        return (
            max(0, min(255, int(weak * fator))),
            max(0, min(255, int(strong * fator))),
        )

    def set_rumble_scales(self, scales: Mapping[str, float] | None = None) -> None:
        """SUBSTITUI o mapa de escala de VIBRAÇÃO por-uniq (POR-UNIDADE-01).

        Camada do PERFIL — é do bloco ``controllers`` do JSON dele que vem —,
        aplicada na SAÍDA de cada handle, depois de o chamador já ter decidido
        o valor. Contrato copiado de `set_led_scales`, campo por campo: chave
        sem MAC estável é ignorada com aviso (não há como mirar uma peça sem
        endereço), fator ≤ 0 é aceito (é o que "vibração desligada nesta
        unidade" significa) e ausência de entrada = sem opinião.

        Sem escrita de hardware: o rumble é transitório e não tem reassert. O
        fator vale a partir do PRÓXIMO `set_rumble` — o que é a verdade do que
        se está pedindo (não existe "re-vibrar o que já passou").
        """
        novo: dict[str, float] = {}
        for uniq, fator in (scales or {}).items():
            alvo = self._key_to_uniq(uniq)
            if alvo is None:
                logger.warning("escala_de_vibracao_sem_mac_ignorada", uniq=uniq)
                continue
            novo[alvo] = float(fator)
        with self._io_lock:
            self._rumble_scale_by_uniq = novo

    def force_rumble_stop(self) -> None:
        """Para os motores de TODOS os controles com um report de stop (HARM-16).

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
        """
        with self._io_lock:
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

    def set_mic_led(self, muted: bool) -> None:
        """Acende/apaga o LED do microfone em TODOS os controles (INFRA-SET-MIC-LED-01).

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
        """
        flag = bool(muted)
        self._for_each(
            lambda h: _escrever_led_do_mic(h, flag),
            what="set_mic_led",
            record={"mic_led": flag},
        )

    # --- Áudio do controle (AUDIO-STATUS-01 / AUDIO-OWNER-01) -------------

    def audio_status_for(self, uniq: str | None = None) -> dict[str, bool] | None:
        """Estado de áudio LIDO do controle, ou None se ainda não foi visto.

        Decodifica o byte de estado que vem no report de INPUT (o mesmo que a
        ponte de mic por BT já lia e consumia internamente — aqui ele SOBE):

          - ``fone_plugado`` — há headset no P2 do controle;
          - ``mic_externo`` — o microfone do headset está presente;
          - ``mic_mudo``    — o firmware declara o microfone MUDO.

        `uniq` seleciona o controle (MAC normalizado); None = o primário.
        Devolve None quando não há handle, quando ele nunca leu um report ou
        quando o MAC não corresponde a controle nenhum — ausência é resposta,
        e a GUI esconde o bloco em vez de desenhar "não plugado" adivinhado.
        """
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
        # `len(volumes) > 3` porque o dublê de teste (e um handle de outra
        # versão) pode ter a lista mais curta — a ausência do byte é a mesma
        # resposta de nunca o termos escrito.
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
        """Assume a posse do volume de alto-falante/fone e o aplica.

        A partir da 1ª chamada o hefesto passa a mandar os bytes de volume em
        todo report (com os bits de validação ligados) — antes disso o
        firmware é o dono e nós não tocamos no bloco.

        `volume` 0-255 (None mantém o vigente); `muted=True` manda 0 sem
        perder o volume preferido (guardado em `_speaker_volume_pref`), e
        `muted=False` o restaura. Sem volume conhecido, `muted` é RECUSADO
        (devolve False sem tomar a posse) — ver a guarda no laço abaixo.
        Aplica o MESMO valor ao alto-falante interno e ao fone: para quem usa o
        controle é UM volume só, e qual dos dois toca depende do headset estar
        plugado (que é o `fone_plugado` do `audio_status_for`). O volume de
        MICROFONE (common[6]) não é tocado.

        SOM-ROTA-01: o `rota` é opcional e, quando omitido, o `common[7]`
        continua intocado — pela razão de sempre, que agora está escrita: o
        byte carrega a rota de SAÍDA nos bits 4-5 e o caminho do MICROFONE no
        resto, e escrever o byte inteiro com um número de rota apagaria o
        caminho do mic sem ninguém notar. Quando `rota` vem, só os dois bits
        dela mudam.

        E o PRÉ-AMPLIFICADOR (`common[37]`) passa a ir junto do volume — ver o
        bloco de comentário no laço, é ele que destrava os 60% de curso que ela
        mediu como inertes.

        Retorna True se algum handle recebeu o pedido.
        """
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
        """A escrita de volume num handle JÁ escolhido. A conta mora aqui, só aqui.

        SOM-SEMPRE-01 (16/08/2026): extraída do corpo do `set_speaker_volume`
        porque ela passou a ter DOIS chamadores — o pedido explícito (janela,
        perfil, linha de comando) e a ADOÇÃO do controle, que agora assume o
        volume padrão sem ninguém pedir. Duas cópias desta sequência (a
        preferência, a guarda do mudo, o pré-amplificador, a rota) divergiriam
        no primeiro conserto feito só de um lado — é o mesmo motivo pelo qual a
        régua de porcentagem mora num módulo só.

        Devolve True quando o handle recebeu a escrita. Nunca levanta: a falha
        de um handle não pode derrubar quem varre vários.
        """
        try:
            pref = getattr(handle, "_speaker_volume_pref", None)
            if volume is not None:
                pref = max(0, min(255, int(volume)))
            # SOM-02 (E3): `muted` é MODULAÇÃO de um volume conhecido, não
            # uma primeira escrita. Sem volume nenhum na mão (nem no pedido
            # nem na preferência), mandá-lo assumiria a posse e emudeceria o
            # controle em ZERO — e o próprio "desmudo" não teria o que
            # restaurar (armadilha 2, medida na sprint: o par mudo/desmudo
            # tranca em `{'volume': 0, 'muted': True}` e não sai mais de
            # lá). Recusar aqui é o que faz a DEVOLUÇÃO da posse valer: sem
            # esta guarda, um `muted=False` depois do `release_speaker_volume`
            # reabriria a posse sozinho.
            if pref is None and muted is not None:
                logger.info("speaker_mute_sem_volume_recusado", op=op, muted=muted)
                return False
            if pref is None:
                # SOM-CANAL-01, GUARDA DE RAIZ (04/08/2026). "Não me
                # disseram" e "me disseram zero" eram o mesmo valor aqui, e
                # a diferença é a de um alto-falante mudo.
                #
                # Medido com ela: o seletor de canal do card chamava
                # `speaker_set(rota=...)` sem volume, caía nesta linha e
                # TRANCAVA o alto-falante em zero — enquanto tomava a posse
                # do registrador, de modo que nem o firmware o recuperava.
                # A regra já estava escrita na SOM-02 ("Armadilha 1") e num
                # validador de perfil (`profiles/schema.py` RECUSA seção de
                # alto-falante sem volume); faltava valer no caminho vivo.
                #
                # Sem volume pedido, herda-se o que JÁ está em vigor neste
                # handle. Só quando não há nada em vigor é que o zero
                # aparece — e aí ele é o estado real, não uma suposição.
                vigente = getattr(handle, "_speaker_volume_pref", None)
                pref = int(vigente) if isinstance(vigente, int) else 0
            handle._speaker_volume_pref = pref
            efetivo = 0 if muted else pref
            # SOM-ROTA-01/E1 — o PRÉ-AMPLIFICADOR vai junto, e é ele que
            # destrava o curso do controle deslizante.
            #
            # Ela mediu a curva em 01/08: mudo até 38, satura em 102 — 60%
            # do curso inerte. A causa não é o usuário quebrando nada: é o
            # registrador de volume lutando contra um ganho de entrada no
            # valor padrão. O kernel 6.18, para fazer o alto-falante soar
            # quando o fone sai, escreve TRÊS campos (rota, volume e
            # pré-amp); esta árvore escrevia só o volume, e 64 passos úteis
            # é a assinatura de mexer em um de três botões.
            #
            # O `SP_PREAMP_GAIN_PADRAO` é o mesmo `0x2` que o kernel
            # escolhe. Ele entra na MESMA posse do volume: quem assume um
            # assume o outro, e o `release` devolve os dois — meio
            # devolvido seria pior que nada.
            #
            # `rota` fica em `None` por omissão e o `common[7]` NÃO é
            # tocado: aquele byte carrega a rota (bits 4-5) E o caminho do
            # microfone (o resto), e escrevê-lo pela metade muda a outra
            # metade em silêncio.
            #
            # SOM-SEMPRE-01: o volume do MICROFONE (`common[6]`) continua
            # FORA da chamada, e isso é decisão, não esquecimento — o dono
            # do microfone no Linux é o kernel (AUDIO-OWNER-01), e "o som"
            # que ela pediu a 100% é o que SAI do controle.
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
            alvo.release_audio_volumes()
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
        no cabo e no rádio, no boot e no hotplug do meio da sessão — o gancho
        de perfil `reapply_speaker_after_connect` só corre na TRANSIÇÃO
        offline→online do daemon e só quando o perfil ativo tem seção
        `speaker`, de modo que o segundo controle a chegar numa mesa já online
        nunca era coberto por ele.

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
        (`common[6]`, do kernel) e a ROTA de saída (`common[7]`, que carrega o
        caminho do microfone nos outros bits). Fone e alto-falante vão os DOIS
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
            rota=None,
            op="volume_padrao_na_adocao",
        )
        logger.info(
            "volume_padrao_na_adocao",
            key=key,
            volume=VOLUME_PADRAO_DO_SOM,
            ok=escreveu,
        )
        return escreveu

    def set_microphone_mute(
        self, muted: bool | None, *, uniq: str | None = None
    ) -> bool:
        """Assume (ou devolve) a posse do mudo de microfone do FIRMWARE.

        `None` = devolve a posse ao kernel (`hid-playstation`), que é quem
        alterna o mudo na borda do botão físico do controle — é o default e
        foi o que o keepalive do upstream vinha atropelando a 60 Hz
        (AUDIO-OWNER-01). Não confundir com o mute do microfone do SISTEMA,
        que é do `integrations/audio_control.py` e continua sendo o caminho do
        botão de mic.

        MIC-USB-01 (25/07): passou a devolver `bool` — True quando ALGUM
        handle recebeu o pedido. O `mic.set` do IPC precisa distinguir "mandei"
        de "não havia controle para mandar", exatamente como o `speaker.set`
        já fazia com `set_speaker_volume`; antes o retorno era `None` e o
        chamador não tinha como saber que a ordem caiu no vazio.

        Esta é a CAMADA 3 do achado das três camadas de mudo empilhadas: o
        firmware do controle guarda o próprio mute, e nem desmutar a rota do
        WirePlumber nem trocar o perfil da placa o alcançam. Até 25/07 o único
        caminho para mexer nele era o botão físico do controle.
        """
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
        logger.info("microphone_mute_set", muted=muted, uniq=uniq, ok=ok)
        return ok

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
        """
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
        """Handle do controle `uniq` (MAC normalizado) ou o primário se None."""
        from hefesto_dualsense4unix.core.sysfs_leds import norm_mac

        alvo = norm_mac(uniq) if uniq else None
        with self._io_lock:
            if alvo is None:
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

        # LIGHTBAR-ISOLAR-OS-PLAYERS-01: com o instrumento ligado, NENHUMA
        # escrita de player-LED sai — nem o gesto direto. Cobrir só o priming
        # deixaria a numeração do co-op escrevendo por trás e a medição não
        # teria variável única.
        if not self._pode_escrever_player_leds():
            logger.info("player_leds_suprimidos_noop", op="set_player_leds")
            return
        bitmask = sum(1 << i for i, b in enumerate(bits) if b)
        # Prefere a rota sysfs do kernel (player-LED em USB E BT, sem disputa);
        # cai no pydualsense quando o controle não está coberto.
        self._for_each_led(
            sysfs_op=lambda node: node.set_players(bits),
            pydual_op=lambda h: setattr(h.light, "playerNumber", PlayerID(bitmask)),
            what="set_player_leds",
            record={"player_leds": bits},
            # ROTA-BT-EM-REGIME-01: são DUAS luzes, e a Steam repinta as duas
            # (o mesmo motivo do GATILHO-DA-COR-01) — o número acompanha a cor.
            players=bits,
        )
        logger.debug("player_leds_aplicados bits=%s bitmask=%s", list(bits), bitmask)

    # --- API por-uniq (PERFIL-01 / 4P-01) --------------------------------

    def apply_output_defaults(self, spec: OutputSpec) -> None:
        """Aplica `spec` como PADRÃO do perfil em TODOS os controles.

        Broadcast REAL: IGNORA o seletor de alvo (`_output_target_key`) de
        propósito — os setters clássicos o respeitam, então ativar um perfil
        (manual OU via autoswitch, mesma cadeia) com um alvo selecionado na
        GUI aplicava SÓ no alvo (bug provado do sprint). Grava no
        `_desired_default` SEM limpar os overrides por-uniq: quem substitui o
        mapa na ativação é `reset_output_overrides` (ciclo de vida explícito)
        — um default novo não pode apagar o override que o próprio perfil
        acabou de registrar.
        """
        fields = _spec_fields(spec)
        if not fields:
            return
        with self._io_lock:
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
        if spec.mic_led is not None:
            flag = spec.mic_led
            self._for_each(
                lambda h: h.audio.setMicrophoneLED(flag),
                what="apply_output_defaults",
                broadcast=True,
            )

    def apply_output_for(self, uniq: str, spec: OutputSpec) -> ResultadoDeSaida:
        """Aplica `spec` SÓ no controle de MAC `uniq` e registra o override dele.

        PERFIL-01: NÃO passa pelo `_output_target_key` — o alvo é o parâmetro,
        resolvido na borda pelo chamador (por construção imune à corrida do
        seletor global mutável com o executor multi-thread). Controle
        DESCONECTADO: o override fica REGISTRADO no mapa em memória (o hotplug
        lê o mapa, não o JSON do perfil, e aplica quando ele chegar) — só a
        escrita de hardware é pulada.

        R-20: esta é a porta da camada da USUÁRIA — os chamadores são o
        `led.set`/`trigger.set`/`player.set` com `uniq` (gesto na GUI) e o
        "Aplicar" do rodapé. A ativação de perfil tem porta própria
        (`reset_profile_overrides`), justamente para que ela não pise aqui.

        MESA-CHEIA-09 (E1): **devolve o que fez**, e é a raiz das quatro
        mentiras de "aplicado" da janela. Os quatro caminhos abaixo eram
        indistinguíveis de fora — todos `return` seco —, então nem o IPC nem a
        tela tinham como saber se algum byte saiu. Ver `ResultadoDeSaida`.

        **Conserto 1.3 — os dois estados que ainda diziam "escreveu" sem byte
        nenhum**, e o primeiro é a TERCEIRA linha da tabela de mentiras da
        sprint (*"Modo Nativo com output mutado"*), que a entrega original
        deixou passar com afirmação POSITIVA:

        * **Modo Nativo** (``_output_mute``): a rota sysfs de LED está
          desabilitada por `not muted`, o `_pintar_por_hidraw_bt` é pulado, e o
          `report_thread` não escreve NADA (`set_output_mute`). O que a escrita
          faz aqui é só deixar o estado interno pronto — e, ao desmutar, o
          `set_output_mute` limpa o dirty-flag e re-aplica o desejado pelo
          sysfs. Isso é, palavra por palavra, o que ``"registrado"`` já
          significa: **fica guardado e vale quando o evento que o segura
          passar** — hotplug num caso, desmute no outro. Por isso é a mesma
          palavra, e não uma sexta.
        * **escrita que LEVANTOU**: `_write_partial_output` engole a exceção
          (log `reapply_perfil_no_hotplug_falhou`), e o caminho seguia para
          "escreveu". Agora ela devolve ``False`` e isto vira ``"falhou"`` —
          que não é "guardado", porque não há promessa a fazer: o override
          está no mapa, mas nada garante que a próxima tentativa exista.
        """
        fields = _spec_fields(spec)
        if not fields:
            return "nada_a_fazer"
        alvo = self._key_to_uniq(uniq)
        if alvo is None:
            # Sem MAC 12-hex não há identidade estável (receiver 2.4G, key por
            # path) — fora do mapa, com log em vez de silêncio (regra do sprint).
            logger.warning("apply_output_for_sem_mac_ignorado", uniq=uniq)
            return "sem_alvo"
        with self._io_lock:
            override = self._desired_by_uniq.setdefault(alvo, _DesiredOutput())
            for name, value in fields.items():
                setattr(override, name, value)
            self._stamp_owner_locked(alvo, fields, _LAYER_USER)
            key = self._key_for_uniq(alvo)
            handle = self._handles.get(key) if key is not None else None
            node = self._sysfs.get(key) if key is not None else None
            muted = self._output_mute
        if handle is None:
            logger.debug(
                "apply_output_for_desconectado_registrado",
                uniq=alvo,
                campos=sorted(fields),
            )
            return "registrado"
        escreveu = self._write_partial_output(
            handle, node, muted, _DesiredOutput(**fields), what="apply_output_for"
        )
        if not escreveu:
            return "falhou"
        if muted:
            logger.debug(
                "apply_output_for_modo_nativo_registrado",
                uniq=alvo,
                campos=sorted(fields),
            )
            return "registrado"
        return "escreveu"

    def reset_output_overrides(
        self, overrides: Mapping[str, OutputSpec] | None = None
    ) -> None:
        """SUBSTITUI o mapa de overrides por-uniq inteiro (gesto da usuária).

        Ciclo de vida explícito do PERFIL-01. Hoje o único chamador é o
        "Aplicar" da GUI (`ipc_draft_applier`), que manda o conjunto COMPLETO
        de overrides do draft: substituir o mapa é o que faz um ajuste que ela
        TIROU de um controle sumir de fato. Por isso o mapa novo entra
        carimbado como camada da USUÁRIA — foi ela quem mandou.

        R-20: a ativação de perfil NÃO usa mais este caminho (usava, e era o
        C5: toda troca de janela apagava o ajuste por-controle dela). Ela usa
        `reset_profile_overrides`, que substitui só a camada do perfil. A
        camada do co-op (`_desired_coop_by_uniq`) não é tocada aqui: quem a
        publica e revoga é o `CoopManager`.

        Overrides de controles DESCONECTADOS também entram no mapa (o hotplug
        lê o mapa em memória). Nenhuma escrita de hardware aqui — o chamador
        aplica na sequência (`apply_output_defaults` + `apply_output_for`).
        """
        novo: dict[str, _DesiredOutput] = {}
        donos: dict[str, dict[str, str]] = {}
        for uniq, spec in (overrides or {}).items():
            alvo = self._key_to_uniq(uniq)
            if alvo is None:
                logger.warning("override_por_controle_sem_mac_ignorado", uniq=uniq)
                continue
            campos = _spec_fields(spec)
            novo[alvo] = _DesiredOutput(**campos)
            if campos:
                donos[alvo] = dict.fromkeys(campos, _LAYER_USER)
        with self._io_lock:
            self._desired_by_uniq = novo
            self._desired_owner_by_uniq = donos

    def reset_profile_overrides(
        self, overrides: Mapping[str, OutputSpec] | None = None
    ) -> None:
        """Republica a camada do PERFIL e escreve nos conectados (R-20).

        Substitui APENAS o que pertence ao perfil, em três passos:

        1. solta todo campo carimbado como `perfil` (a camada está sendo
           republicada — sem isso o override do perfil anterior ressuscitaria
           no hotplug sob o perfil novo, que é a razão de existir do
           `reset_output_overrides`);
        2. escreve os campos do perfil novo **só onde o slot ficou VAGO**. O
           que sobrou com valor depois do passo 1 é, por construção, de uma
           camada mais alta — o ajuste que a usuária fez na mão. É esta linha
           que conserta o C5: o autoswitch reativa perfil a cada troca de
           janela e não apaga mais o que ela acabou de ajustar;
        3. converge no hardware dos conectados que têm QUALQUER override o
           estado RESOLVIDO por-controle. Não são só os campos que este
           perfil aplicou: o `apply_output_defaults` (broadcast do global)
           roda ANTES desta chamada no manager e pinta o global por cima do
           por-uniq de todo mundo — sem repintar o resolvido aqui, o ajuste
           manual dela ficaria só na MEMÓRIA e o hardware mostraria o global.
           Espelha o laço `apply_output_for` que o manager fazia (que
           repintava cada override), agora com o valor resolvido para também
           reparar o campo que a usuária tinha travado. Desconectado fica só
           registrado, como sempre.

        Escape hatch documentado: um gesto explícito dela — trocar de perfil
        na GUI (`origin="manual"`, ver `ProfileManager.apply`) ou aplicar uma
        cor em "Todos" — solta a camada da usuária, e aí o perfil volta a
        mandar. Sem esse par, a camada alta viraria "estado armado que nunca
        é liberado" (a queixa 5).
        """
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
            muted = self._output_mute
            for alvo, campos in novo.items():
                override = self._desired_by_uniq.setdefault(alvo, _DesiredOutput())
                for nome, valor in campos.items():
                    if getattr(override, nome) is not None:
                        adiados.setdefault(alvo, []).append(nome)
                        continue
                    setattr(override, nome, valor)
                    self._stamp_owner_locked(alvo, (nome,), _LAYER_PROFILE)
            self._prune_overrides_locked()
            # Converge o hardware dos conectados COM override ao resolvido
            # (passo 3 da docstring). Um controle sem override nenhum já ficou
            # certo com o broadcast global anterior; o auto/sysfs dele é do
            # `reassert_resolved_outputs` que o manager chama em seguida.
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
                handle, node, muted, out, what="reset_profile_overrides"
            )
        if adiados:
            # Observabilidade da precedência (o doctor/journal precisam poder
            # explicar "por que o perfil não pintou aquele controle").
            logger.info(
                "override_do_perfil_cedeu_ao_ajuste_manual",
                controles={uniq: sorted(campos) for uniq, campos in adiados.items()},
            )

    def clear_user_output_overrides(self) -> None:
        """Solta a camada da USUÁRIA no mapa por-uniq (R-20).

        Chamado pelo gesto EXPLÍCITO de trocar de perfil (`origin="manual"`):
        escolher um perfil na GUI é mais novo que o slider que ela arrastou
        antes, e é o botão de soltar que impede a camada alta de virar estado
        preso. Ativação AUTOMÁTICA (autoswitch, restore de boot) nunca chama —
        é justamente dela que a camada precisa se defender.

        Só muda estado: quem escreve o hardware é a ativação que vem logo em
        seguida (`reset_profile_overrides` + `reassert_resolved_outputs`).
        """
        with self._io_lock:
            self._clear_layer_locked(_LAYER_USER)

    def set_led_scales(self, scales: Mapping[str, float] | None = None) -> None:
        """SUBSTITUI o mapa de escala de brilho por-uniq (R-20 item 2).

        Camada do PERFIL (é do JSON dele que vem), aplicada DEPOIS do merge
        sobre a cor RESOLVIDA — inclusive a automática do slot. Antes, um
        override que só escrevia `lightbar_brightness` era convertido em cor
        materializada (o RGB global escalado) e, como override vence a camada
        automática, o controle perdia a cor do slot para sempre.

        Fator ≤ 0 é aceito (apaga a lightbar daquele controle, que é o que
        brilho 0 significa); ausência de entrada = sem opinião. Sem escrita de
        hardware: o `reassert_resolved_outputs` da ativação converge.
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

    def set_coop_outputs(
        self, outputs: Mapping[str, OutputSpec] | None = None
    ) -> None:
        """SUBSTITUI a camada do CO-OP e converge os controles afetados (R-13).

        O co-op deixou de escrever sysfs cru: ele publica aqui `{uniq: spec}`
        com o padrão de player-LED de cada jogador. Ganho medido no desenho:
        o `reassert_resolved_outputs`, que roda em TODO `connect()` (≤30 s) e
        antes repintava o padrão do PERFIL por cima do co-op, agora reafirma o
        MESMO valor — acaba o pisca-pisca entre as duas autoridades.

        Vocabulário restrito a `player_leds` (`_COOP_LAYER_FIELDS`): co-op é
        sobre QUEM é cada jogador, não sobre a paleta. Campo fora disso é
        ignorado com log — evitaria que um chamador futuro sequestrasse a cor
        por uma camada que ninguém revoga.

        Escreve no hardware dos conectados cujo resolvido MUDOU (entrou, saiu
        ou trocou de padrão), pela mesma rota do resto do backend (sysfs com
        fallback pydualsense). `None`/vazio revoga a camada inteira.
        """
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
            muted = self._output_mute
            for alvo in set(antigo) | set(novo):
                key = self._key_for_uniq(alvo)
                handle = self._handles.get(key) if key is not None else None
                if key is None or handle is None:
                    continue
                bits = self._merged_desired_for_key(key).player_leds
                if bits is None:
                    continue
                escritas.append(
                    (handle, self._sysfs.get(key), _DesiredOutput(player_leds=bits))
                )
        for handle, node, out in escritas:
            self._write_partial_output(
                handle, node, muted, out, what="set_coop_outputs"
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

    # --- REPLICA-03: posse do output pelo JOGO (sessão uhid) --------------

    def set_game_trigger_for(self, uniq: str, side: Side, block: bytes) -> bool:
        """Aplica no físico `uniq` o trigger effect CRU que o jogo mandou ao vpad.

        REPLICA-03: `block` são os 11 bytes (modo + 10 parâmetros) do report
        0x02 do jogo, embutidos VERBATIM no report do físico pelo
        `_build_common` (a rota DSTrigger só representa 7 forças e mutilaria
        o efeito). A posse fica registrada em `_game_triggers_by_uniq` — o
        hotplug re-pendura no handle novo e `end_game_session_for` devolve o
        perfil. False = sem identidade estável (MAC) ou bloco inválido.
        """
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
            self._game_triggers_by_uniq.setdefault(alvo, {})[lado] = block_b
            key = self._key_for_uniq(alvo)
            handle = self._handles.get(key) if key is not None else None
        if handle is None:
            return True  # registrado; o hotplug aplica quando o controle voltar
        attr = "_raw_trigger_left" if lado == "left" else "_raw_trigger_right"
        try:
            # O report_thread detecta a mudança no próximo prepareReport
            # (o dedup `_last_out_report` compara o buffer montado).
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
        """Aplica no físico `uniq` a lightbar/player-LED que o jogo pintou no vpad.

        REPLICA-03: grava a camada GAME do desejado (topo do merge — o
        reassert periódico passa a reafirmar a COR DO JOGO, nunca a paleta
        por baixo dela, matando a race verde-limãoazul por construção) e
        escreve no hardware pela rota normal (sysfs preferido, fallback
        pydualsense). Controle desconectado: fica registrado (hotplug aplica).
        False = sem identidade estável (MAC).

        NUMA-02 (retain-latest): sob autoridade 'daemon' (evidência positiva
        de NÃO-jogo — no incidente 14:42, o escritor era o CLIENTE Steam) a
        réplica de exibição é RETIDA: não popula a camada GAME, não escreve
        hardware; `replay_retained_game_outputs()` entrega o valor mais
        recente 1x na abertura do gate. A telemetria `uhid_replica_ativa`
        do vpad segue intacta (é emitida antes de chegar aqui). Réplica
        retida = prova de escritor ativo ⇒ dispara a defesa de exibição,
        rate-limitada (NUMA-03).
        """
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
            # Decisão de gate UMA vez, sob o lock — o sinal pode flipar no
            # tick de outro thread e uma réplica não pode ser retida E
            # aplicada ao mesmo tempo.
            wins = self._game_wins()
            if not wins:
                retido = self._retained_game_outputs.setdefault(alvo, {})
                retido.update(fields)  # retain-latest: 1 valor por categoria
                if self._retained_log_armed:
                    logger.info(
                        "game_output_retido_sem_jogo",
                        uniq=alvo,
                        campos=sorted(fields),
                    )
                    self._retained_log_armed = False
                agora = time.monotonic()
                defender = (
                    self._defend_last_at is None
                    or (agora - self._defend_last_at)
                    >= DEFEND_DISPLAY_MIN_INTERVAL_S
                )
        if not wins:
            if defender:
                self.defend_display()
            return True
        with self._io_lock:
            layer = self._game_output_by_uniq.setdefault(alvo, _DesiredOutput())
            for name, value in fields.items():
                setattr(layer, name, value)
            key = self._key_for_uniq(alvo)
            handle = self._handles.get(key) if key is not None else None
            node = self._sysfs.get(key) if key is not None else None
            muted = self._output_mute
        if handle is None:
            return True
        self._write_partial_output(
            handle, node, muted, _DesiredOutput(**fields), what="game_output_replica"
        )
        return True

    def replay_retained_game_outputs(self) -> None:
        """Entrega as réplicas RETIDAS na abertura do gate (NUMA-02).

        Chamado pelo lifecycle na transição `daemon→game|unknown`: cada valor
        retido (o MAIS recente por (uniq, categoria)) é entregue exatamente
        1x pelo caminho normal (`set_game_output_for`) — a escrita única de
        player-LED que jogos fazem (FATO 0) atravessa a latência ~2s do
        sinal sem se perder. Risco aceito na síntese: o último valor pode
        ser do CLIENTE Steam, mas cliente e jogo compartilham a numeração do
        Steam Input e o jogo sobrescreve em seguida. Re-arma o log
        `game_output_retido_sem_jogo` (episódio novo). Falha em um controle
        não aborta os demais.
        """
        with self._io_lock:
            retidos = self._retained_game_outputs
            self._retained_game_outputs = {}
            self._retained_log_armed = True
        for alvo, campos in retidos.items():
            with contextlib.suppress(Exception):
                self.set_game_output_for(alvo, **campos)

    def end_game_session_for(self, uniq: str) -> bool:
        """Fim da sessão de jogo do controle `uniq`: devolve perfil/paleta/co-op.

        REPLICA-03 (UHID_CLOSE): a camada GAME e os triggers crus somem; o
        estado físico converge de volta ao desejado resolvido (explícito >
        automático > global). O nó sysfs tem o cache invalidado (GUERRA-01
        item 3): o jogo pode ter escrito a cor por hidraw sem recriar o nó —
        o cache estaria "certo" com o hardware errado. Trigger do jogo sem
        perfil por baixo volta a Off (efeito de jogo não sobrevive à sessão).

        Correção pós-auditoria da Onda N: a réplica RETIDA (NUMA-02,
        `_retained_game_outputs` — escrita sob autoridade 'daemon', ex.: o
        cliente Steam abrindo sessão uhid sem jogo nenhum) também é
        descartada AQUI, no fim da MESMA sessão que a gerou. Sem isso, o
        valor fantasma sobrevive ao UHID_CLOSE (e a qualquer disconnect/
        reconnect físico) e só seria purgado quando a autoridade saísse de
        'daemon' — vazando via `replay_retained_game_outputs()` para a
        PRÓXIMA sessão de jogo real deste controle, totalmente não
        relacionada à que escreveu o valor (o "player 3 verde" acendendo
        antes de o jogo escrever qualquer coisa).
        """
        alvo = self._key_to_uniq(uniq)
        if alvo is None:
            return False
        with self._io_lock:
            game = self._game_output_by_uniq.pop(alvo, None)
            triggers = self._game_triggers_by_uniq.pop(alvo, None)
            retido = self._retained_game_outputs.pop(alvo, None)
            key = self._key_for_uniq(alvo)
            handle = self._handles.get(key) if key is not None else None
            node = self._sysfs.get(key) if key is not None else None
            muted = self._output_mute
            desired = (
                self._merged_desired_for_key(key) if key is not None else None
            )
        if game is None and triggers is None:
            if retido:
                logger.info(
                    "game_output_retido_descartado_no_close",
                    uniq=alvo,
                    campos=sorted(retido),
                )
            return True  # o jogo nunca tocou este controle
        logger.info(
            "game_session_devolvida",
            uniq=alvo,
            lightbar=bool(game is not None and game.led is not None),
            player_leds=bool(game is not None and game.player_leds is not None),
            triggers=sorted(triggers) if triggers else [],
        )
        if handle is None or desired is None:
            return True  # desconectado: o hotplug reaplica o perfil sozinho
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
            restore.led = desired.led  # None = paleta sem opinião: fica como está
        if game is not None and game.player_leds is not None:
            restore.player_leds = desired.player_leds
        self._write_partial_output(
            handle, node, muted, restore, what="game_session_close"
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
        """Padrão de player-LED RESOLVIDO do controle `uniq` (leitura pura).

        PERFIL-06: API pública de LEITURA para o revert do co-op — devolve o
        MERGE POR CAMPO (default broadcast + override por-uniq) do campo
        `player_leds`, pelo MESMO resolvedor dos reasserts de hotplug/unmute
        (`_merged_desired_for_key`). `uniq` sem MAC 12-hex (fallback por
        path) não tem override possível → devolve o default puro (o controle
        segue só o global, regra do sprint). None = nenhum perfil/GUI setou
        player-LED ainda — o chamador não escreve nada. Não toca hardware
        nem muta estado.

        R-13: a camada do CO-OP fica FORA deste resolvedor de propósito —
        quem lê isto é o revert do co-op, perguntando "para qual padrão eu
        devolvo este controle". Incluir a própria camada dele faria o revert
        restaurar o número do jogador e o co-op nunca mais sair de cena.
        """
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

        Nota (D8 — divergência fundamentada, decidida pelo orquestrador da
        onda): o valor devolvido é PÓS-escala de brilho — `_DesiredOutput.led`
        guarda o RGB como chegou ao `set_led`, e o manager pré-escala
        `lightbar_brightness` na borda (`led_control.py`). O D8 original pedia
        expor também a cor-identidade PRÉ-brilho, mas separá-la exigiria
        refactor do estado desejado (fora do escopo desta frente); o objetivo
        do D8 (traços legíveis com cor escura) foi resolvido por outra via —
        `utils/color_contrast.ensure_min_contrast` clareia preservando o matiz
        na borda da GUI. None = nenhum perfil/GUI setou cor ainda. Não toca
        hardware nem muta estado.
        """
        with self._io_lock:
            return self._merged_desired_for_key(uniq).led

    # --- introspecção / leitura do primário -----------------------------

    def describe_controllers(self) -> list[dict[str, object]]:
        """Descreve cada controle conectado (observabilidade — IPC `controller.list`).

        Uma entrada por handle aberto:
        `{index, connected, transport, is_primary, uniq, battery_pct}`.
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
                    "battery_pct": self._read_battery_opt(handle) if connected else None,
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

    def reassert_resolved_outputs(self, *, verify: bool = False) -> None:
        """Re-aplica o desired RESOLVIDO por-controle (3 camadas) via sysfs.

        COR-03 — fix de integração pego AO VIVO na validação pós-install
        (2026-07-17): a ativação de perfil termina num broadcast do GLOBAL
        (`apply_output_defaults`), que pisa a paleta automática nos controles
        conectados; os reasserts por-key (`_merged_desired_for_key`) só
        rodavam em hotplug/new_keys/unmute — então um boot com os controles
        JÁ conectados ficava com a cor global até o próximo replug. Este
        método é o "unmute sem mute": o manager (ativação de perfil) e o
        ipc_draft_applier ("Aplicar" da GUI) o chamam AO FINAL, para o estado
        físico convergir ao resolvido (explícita > automática > global).

        Escreve pela rota sysfs (os nós do mapa `_sysfs`, com registro no
        rastreio "escrito por nós"). Controle sem nó gravável (sem a regra
        77) segue no caminho pydualsense com o global até o próximo
        `_reapply_desired` — limitação documentada do caminho degradado. Em
        Modo Nativo é no-op (o jogo é dono do LED; o unmute já re-aplica).

        NUMA-03 (``verify=True``): repassa a verificação de escritor
        estrangeiro a `SysfsLedNode.set_rgb`/`set_players_verified` — mas SÓ
        para o nó com autoridade 'daemon' vigente E posse registrada em
        `_sysfs_written` (STATUS-01: leitura de classe sem prova de escrita
        nossa nunca vira verdade — o probe do kernel zera a classe com a
        lightbar acesa). Sem posse ou fora de 'daemon', o nó segue o caminho
        histórico (`verify=False` é byte-idêntico ao HEAD).
        """
        with self._io_lock:
            if self._output_mute:
                return
            # `verify` só vale sob autoridade 'daemon' explícita — em
            # game/unknown/sem-provider a defesa não roda (fail-safe).
            check = verify and not self._game_wins()
            posse = set(self._sysfs_written) if check else set()
            reasserts = [
                (key, node, self._merged_desired_for_key(key))
                for key, node in self._sysfs.items()
            ]
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
        """Defesa de exibição: invalida os caches sysfs + reassert verificado.

        NUMA-03 — disparada (a) pelo lifecycle na transição `*→daemon` e
        (b) por réplica de exibição RETIDA (rate-limitada por
        `DEFEND_DISPLAY_MIN_INTERVAL_S` em `set_game_output_for` — réplica
        retida é prova de escritor ativo, e o invalidate alcança até o vetor
        hidraw-direto que a re-leitura de classe não vê; no incidente 14:42,
        repinte ≤2s da escrita estrangeira). NÃO é o reassert incondicional
        do flash azul (GUERRA-01): só em transição ou sob evidência de
        escritor, sempre com teto de frequência. No-op TOTAL sob
        `_output_mute` (Modo Nativo: o jogo é o dono — nada escrito, nem
        repaint). Falha de um nó não aborta os demais (suppress por item do
        reassert).
        """
        with self._io_lock:
            if self._output_mute:
                return
            self._defend_last_at = time.monotonic()
            nodes = list(self._sysfs.values())
        for node in nodes:
            with contextlib.suppress(Exception):
                node.invalidate_cache()
        self.reassert_resolved_outputs(verify=True)

    def set_output_mute(self, muted: bool) -> None:
        """Muta/desmuta TODA escrita de output HID (FEAT-NATIVE-OUTPUT-MUTE-01).

        Modo Nativo = o JOGO é o dono do hidraw: rumble, gatilhos adaptativos e
        LEDs vêm dele. Mutado, o report_thread NÃO escreve nada (nem o
        keepalive — que zerava o rumble do jogo a cada 0.5s, sentido ao vivo no
        Sackboy). Ao desmutar, o dirty-flag é limpo para o estado desejado do
        hefesto ser re-escrito no próximo ciclo (~ms).
        """
        with self._io_lock:
            self._output_mute = bool(muted)
            for handle in self._handles.values():
                with contextlib.suppress(Exception):
                    handle._output_muted = self._output_mute
                    if not self._output_mute:
                        handle._last_out_report = None
            # FEAT-PARITY-REVIEW-01: snapshot p/ re-aplicar o LED do perfil na
            # rota sysfs ao DESMUTAR (fora do lock). Controles cobertos por sysfs
            # não recebem LED pelo report_thread (_suppress_leds), então só o
            # sysfs restaura a cor/player do perfil ao sair do Modo Nativo.
            # PERFIL-01: valor por controle (merge default + override do uniq).
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
                # STATUS-03: espelha o reassert_resolved_outputs — registrar a
                # POSSE do nó (escrita nossa) mesmo quando o nó surgiu PELA
                # PRIMEIRA VEZ durante o Modo Nativo (reconnect BT no meio do
                # jogo); sem isto, ao desmutar a cor era escrita mas o campo
                # diagnostico da cor ficava como "desconhecida".
                if desired.led is not None and node.set_rgb(*desired.led):
                    self.record_sysfs_write(key, desired.led)
                if desired.player_leds is not None:
                    node.set_players(desired.player_leds)
        logger.info("backend_output_mute", muted=bool(muted))

    def set_output_target(self, index: int | None) -> int | None:
        """Define o ALVO das ações de output (FEAT-DSX-CONTROLLER-SELECTOR-01).

        `index` é a POSIÇÃO em `list(self._handles)` (0 = primário); guardamos a
        KEY estável (serial/MAC) correspondente — NÃO o índice — para o alvo
        sobreviver a hotplug/troca de porta. `None` ou fora de faixa → broadcast
        (TODOS, padrão). Devolve o índice efetivo (ou None para "todos"). Sob
        `_io_lock` (consistente com o snapshot que o `_for_each` tira).
        """
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
        """Posição atual do alvo de output, ou None (FEAT-DSX-CONTROLLER-SELECTOR-01).

        Mapeia a KEY guardada para a posição em `list(self._handles)`; devolve
        None quando o alvo é "todos" (broadcast) ou quando o controle alvo sumiu
        (desconectou) — caso em que o `_for_each` já voltou ao broadcast.
        """
        with self._io_lock:
            key = self._output_target_key
            if key is None or key not in self._handles:
                return None
            return list(self._handles).index(key)

    def get_output_target_uniq(self) -> str | None:
        """MAC do alvo de output de AGORA, ou None quando o alvo é "todos".

        MESA-CHEIA-05 (E0): o índice não serve para GUARDAR um alvo — ele é
        posição em `list(self._handles)` e muda quando alguém pluga, despluga
        ou o alvo some. Quem precisa lembrar *em quem* um valor transitório foi
        fixado (o rumble do poll loop) precisa do endereço estável, que é o
        mesmo que `set_rumble_for` aceita.

        Devolve None também quando o alvo não tem MAC 12-hex (key por path —
        receiver 2.4G): sem endereço estável não há o que guardar, e o chamador
        cai no comportamento histórico.
        """
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
        """
        # HOTFIX-1: battery vive em `ds.battery` (top-level), não em ds.state.
        # DSBattery expõe `Level` (0-100) e `State` (enum BatteryState).
        battery = getattr(ds, "battery", None)
        level = getattr(battery, "Level", None) if battery is not None else None
        if level is None:
            return None
        try:
            value = int(level)
        except (TypeError, ValueError):
            return None
        return max(0, min(100, value))

    @staticmethod
    def _read_battery_raw(ds: pydualsense) -> int:
        # Contrato legado do read_state/get_battery: bateria SEMPRE int
        # (0 quando indisponível). Delega a leitura ao `_read_battery_opt`.
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


__all__ = ["PyDualSenseController"]
