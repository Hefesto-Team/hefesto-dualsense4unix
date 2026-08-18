"""8BIT-02: escreve o LED de player dos controles externos (Nintendo/8BitDo).

O co-op precisa de um número DISTINTO por controle. O Hefesto já dá 1..N aos
DualSense (via o LED próprio deles); aqui ele continua a contagem nos externos
(o 1º externo = slot N+1) escrevendo o LED de player que o kernel expõe:
``/sys/class/leds/<inst-hid>:green:player-{1..4}`` MAIS o 5º
``<inst-hid>:blue:player-5`` (atributo ``brightness``; o Nintendo usa VERDE +
o azul do 5º — o DualSense usa branco). Assim o LED físico bate com o número
da GUI.

R-25 (auditoria 25/07): o azul entrou na conta como bit "+5" (ver
:data:`_BLUE_PLAYER_LED`). Com só os 4 verdes, o slot 7 acendia o MESMO padrão
do 4 — dois controles idênticos na barra, que é a queixa "nunca sei o que é o
quê" chegando ao hardware.

SÓ LED, nunca input: o Hefesto não adota esses controles (o input segue pelo
kernel/Steam). A regra udev ``79-external-controller-leds`` torna esses nós
graváveis pelo daemon (sudo-zero). Sem a regra, a escrita falha em SILÊNCIO
(best-effort) e o LED fica no default do kernel — sem regressão.

GYRO-02 (2026-07-19): `enable_imu` é a ÚNICA exceção que sai do sysfs e
escreve um output report CRU no hidraw — o subcomando Enable-IMU (0x40/0x01)
do protocolo Switch, para ligar a IMU do Nintendo Pro REAL (que o hid-nintendo
declara mas não ativa, ver estudo 2026-07-19-estudo-gyro-universal-vpad.md
§Parte 2). Ainda é I/O pura e best-effort; a decisão de QUANDO enviar (OUI,
bus, uma vez por adoção, backoff) mora em `ExternalImuEnabler`.
"""
from __future__ import annotations

import glob
import os

from hefesto_dualsense4unix.utils.logging_config import get_logger

logger = get_logger(__name__)

#: Raiz da classe LED (monkeypatchável nos testes via env, como em sysfs_leds).
LEDS_ROOT: str = os.environ.get(
    "HEFESTO_DUALSENSE4UNIX_LEDS_ROOT", "/sys/class/leds"
)

#: LEDs VERDES de player expostos pelo hid-nintendo (``:green:player-1..4``).
_MAX_PLAYER_LEDS = 4

#: R-25 (auditoria 25/07): o 5º LED (AZUL, ``:blue:player-5``) deixou de ser
#: "sempre apagado" e virou o bit "+5" da numeração.
#:
#: Antes, `write_player_number` capava o slot em 4: com 5+ controles na mesa
#: (2 DualSense + Pro Nintendo + 8BitDo + …) o slot 7 acendia EXATAMENTE o
#: mesmo padrão do slot 4 e a numeração única (R-24) morria na última
#: polegada — no LED. O hardware medido nesta máquina (`/sys/class/leds/
#: 0003:057E:2009.*`) tem os 4 verdes MAIS o azul player-5, então o azul dá
#: 5 slots a mais de graça: azul aceso = "some 5 aos verdes acesos".
#:
#: 1..4 = N verdes à esquerda (padrão Nintendo, INTOCADO — é o que a usuária
#: já reconhece); 5 = só o azul; 6..9 = azul + 1..4 verdes.
_BLUE_PLAYER_LED = 5
_MAX_SLOT_WITH_BLUE = _MAX_PLAYER_LEDS + _BLUE_PLAYER_LED  # 9


def hid_instance_for_hidraw(hidraw_dev: str | None) -> str | None:
    """``/dev/hidraw2`` -> a instância HID (``0003:057E:2009.000E``) via sysfs.

    É o prefixo dos nós LED do controle. ``None`` quando não resolve (device
    sumiu, sem sysfs) — o chamador trata como "sem LED gravável".
    """
    if not hidraw_dev:
        return None
    name = os.path.basename(str(hidraw_dev))
    if not name.startswith("hidraw"):
        return None
    try:
        target = os.path.realpath(f"/sys/class/hidraw/{name}/device")
    except OSError:
        return None
    inst = os.path.basename(target)
    return inst or None


def _set_brightness(path: str, value: int) -> bool:
    """Escreve ``value`` no ``brightness`` do nó LED. Best-effort (False sem
    nó/permissão, nunca levanta)."""
    if not os.path.exists(path):
        return False
    try:
        with open(path, "w", encoding="ascii") as fh:
            fh.write(str(value))
        return True
    except OSError:
        return False


def _blue_node(root: str, hid_instance: str) -> str:
    """Caminho do ``brightness`` do 5º LED (azul) — o bit "+5" do R-25."""
    return f"{root}/{hid_instance}:blue:player-{_BLUE_PLAYER_LED}/brightness"


def write_player_number(
    hid_instance: str, number: int, leds_root: str | None = None
) -> bool:
    """Acende o padrão DISTINGUÍVEL do slot ``number`` na barra de player.

    R-25: 1..4 = N verdes à esquerda (padrão Nintendo, intocado); 5 = só o
    azul ``player-5``; 6..9 = azul + (número menos 5) verdes. Dois slots
    diferentes NUNCA acendem o mesmo padrão — era o buraco do capping em 4
    (slot 7 idêntico ao 4), a última polegada em que a numeração única (R-24)
    se perdia.

    Hardware SEM o nó azul (firmware clone, modo sem a 5ª lâmpada) não tem
    como exibir 5+: cai no capping histórico em 4 e loga — é limite FÍSICO,
    não decisão nossa, e degradar é melhor que apagar a barra inteira (que é
    o que "5 = só o azul" faria num controle sem azul).

    Devolve True se escreveu em ao menos um nó — False quando nenhum nó
    existe/é gravável (sem a regra udev, sem regressão). Nunca levanta.
    """
    root = leds_root if leds_root is not None else LEDS_ROOT
    azul_path = _blue_node(root, hid_instance)
    tem_azul = os.path.exists(azul_path)
    n = max(1, min(_MAX_SLOT_WITH_BLUE, int(number)))
    if n > _MAX_PLAYER_LEDS and not tem_azul:
        logger.debug(
            "external_led_sem_azul_capa_em_4", inst=hid_instance, slot=n
        )
        n = _MAX_PLAYER_LEDS
    azul = n > _MAX_PLAYER_LEDS
    verdes = n - _BLUE_PLAYER_LED if azul else n
    escreveu = False
    for i in range(1, _MAX_PLAYER_LEDS + 1):
        alvo = f"{root}/{hid_instance}:green:player-{i}/brightness"
        escreveu = _set_brightness(alvo, 1 if i <= verdes else 0) or escreveu
    # Slot ≤4 apaga o azul (é o "sem bit +5"); slot ≥5 o acende.
    escreveu = _set_brightness(azul_path, 1 if azul else 0) or escreveu
    return escreveu


#: GYRO-02: cabeçalho do output report "rumble + subcomando" do protocolo
#: Switch (hid-nintendo.c: ``JC_OUTPUT_RUMBLE_AND_SUBCMD``) — o MESMO envelope
#: que o kernel usa tanto para o subcomando de LED de player (0x30, que aqui
#: ``write_player_number`` evita e resolve via sysfs) quanto para o Enable-IMU
#: (0x40): ``output_id(1B) + packet_num(1B) + rumble_data(8B) + subcmd_id(1B)
#: + dados do subcomando``. ``packet_num`` é um contador 0..0xF que o firmware
#: só usa p/ deduplicar; 0x00 é aceito num envio isolado (não há sequência
#: anterior a continuar). ``rumble_data`` NEUTRO é o valor "sem vibração" que
#: o próprio driver manda quando não há rumble em curso.
_JC_OUTPUT_RUMBLE_AND_SUBCMD = 0x01
_JC_RUMBLE_NEUTRAL = bytes((0x00, 0x01, 0x40, 0x40, 0x00, 0x01, 0x40, 0x40))

#: Subcomando Enable-IMU + argumento "ligar" (GYRO-02 — Nintendo Pro REAL tem
#: a IMU em STANDBY; ver docs/process/estudos/2026-07-19-estudo-gyro-universal-vpad.md).
_JC_SUBCMD_ENABLE_IMU = 0x40
_JC_ENABLE_IMU_ARG_ON = 0x01


def build_enable_imu_packet(packet_num: int = 0) -> bytes:
    """Monta o pacote cru do subcomando Enable-IMU (0x40, arg 0x01).

    Byte a byte: ``[0x01, packet_num&0xF, *rumble_neutro(8B), 0x40, 0x01]`` —
    12 bytes, o mesmo envelope rumble+subcmd do protocolo Switch (ver
    docstring do módulo). Função PURA — não sabe de hidraw, OUI ou bus; só
    monta bytes (testável sem device nenhum).
    """
    return (
        bytes((_JC_OUTPUT_RUMBLE_AND_SUBCMD, packet_num & 0x0F))
        + _JC_RUMBLE_NEUTRAL
        + bytes((_JC_SUBCMD_ENABLE_IMU, _JC_ENABLE_IMU_ARG_ON))
    )


def enable_imu(hidraw_dev: str | None, *, packet_num: int = 0) -> bool:
    """Escreve o pacote Enable-IMU cru no ``hidraw_dev`` (GYRO-02).

    Best-effort, como o resto do módulo: ``False`` sem device/sem permissão
    de escrita — NUNCA levanta. Quem decide POR QUE/QUANDO enviar (OUI ==
    Nintendo real, bus == usb, uma vez por adoção, backoff ≤2 tentativas
    ≥2s) é o chamador (`ExternalImuEnabler`, em `external_identity.py`) —
    esta função é só o I/O cru, análoga a `_set_brightness`.
    """
    if not hidraw_dev or not os.path.exists(hidraw_dev):
        return False
    packet = build_enable_imu_packet(packet_num)
    try:
        fd = os.open(hidraw_dev, os.O_WRONLY)
    except OSError:
        return False
    try:
        os.write(fd, packet)
        return True
    except OSError:
        return False
    finally:
        os.close(fd)


def read_player_pattern(
    hid_instance: str, leds_root: str | None = None
) -> int | None:
    """Lê o padrão de player que o KERNEL tem em memória (PURA, NUMA-03).

    .. warning::

       **NOTA DATADA — 07/08/2026 21h04: esta função NÃO enxerga lâmpada
       nenhuma, e a redação anterior ("o padrão ACESO na barra") é o que
       enganou a casa.** O que ela lê é o ``brightness`` da classe LED do
       kernel, que guarda o valor **PEDIDO** — o kernel o grava ANTES de tentar
       o hardware e **nunca o reverte** quando a escrita falha.

       MEDIDO em 07/08 às 15h24: os cinco nós do Pro liam ``1,1,0,0,0``, que é
       exatamente o slot 2 pedido às 15:24:01 — e **três** daquelas cinco
       escritas tinham falhado com ``-110`` (``ETIMEDOUT``). No
       ``hid-nintendo`` a escrita é assíncrona, então o ``write(2)`` volta com
       sucesso 1,18 s a 3,45 s ANTES de o erro existir.

       **Consequências, e as duas doem:**

       - **o leitor é cego à falha de escrita.** Escrita que morreu no rádio é
         invisível aqui **para sempre**, e não há outro caminho na árvore que
         saiba dela (83 falhas no kernel contra ZERO avisos do daemon na mesma
         janela);
       - **o ``-1`` NÃO distingue firmware de terceiro.** Ele só separa
         "padrão não-canônico neste ``sysfs``" de "padrão canônico" — e quem
         escreveu o não-canônico pode ter sido outro processo (a Steam) ou nós
         mesmos numa versão anterior do writer. Em 11 de 11 repinturas do lado
         A de 07/08, o "intruso" acusado era **a nossa própria escrita
         anterior**.

       A medição inteira está em
       ``docs/process/sprints/2026-08-07-A-LUZ-QUE-CUROU-01-calar-parou-o-bombardeio-e-voltar-tem-preco.md``,
       seções 2.1 a 2.3. GRAU: MEDIDO.

    Espelho de leitura de :func:`write_player_number` — e tem de acompanhá-la
    bit a bit (R-25): se o writer passa a usar o azul como "+5" e o reader
    continua só nos verdes, todo controle em slot ≥5 é lido como um número
    diferente do que está escrito, o tick o declara "escritor estrangeiro" e
    repinta o mesmo LED de 2 em 2 segundos — exatamente o bombardeio de
    subcomando que o EXT-04 existe para não repetir. (O "para sempre" desta
    frase caducou em 07/08: ver a nota datada acima. Divergência entre writer e
    reader é a ÚNICA forma de divergência que este leitor enxerga de verdade, e
    por isso a simetria bit a bit continua obrigatória.)

    Retorno:

    - ``1..9`` — padrão canônico (verdes 1..n em prefixo + azul = +5), o que
      o próprio daemon escreve;
    - ``0`` — tudo apagado (kernel default ou apagão de terceiro);
    - ``-1`` — padrão NÃO-canônico (buracos nos verdes, ex.: o "player 1+3"
      que a Steam pinta). **NÃO é assinatura de "escritor estrangeiro"** — ver
      a nota datada de 07/08 acima: ele não distingue firmware de terceiro, e
      escrita nossa que morreu no rádio nunca aparece aqui;
    - ``None`` — algum nó VERDE ausente/ilegível (device sumiu, modo DS4 sem
      barra verde) — o chamador trata como "sem leitura" (skip, comportamento
      de hoje), NUNCA como padrão apagado.

    O nó AZUL é opcional na leitura (ausente/ilegível = apagado): controle sem
    a 5ª lâmpada é o mesmo hardware em que o writer capa em 4, então ler
    "sem +5" ali é a verdade, não um chute.

    Leitura de classe LED é memória do kernel: ZERO subcomando BT (EXT-04 —
    o inventário segue 100% puro; foi subcomando em excesso que matou o
    8BitDo BT). Nunca levanta.
    """
    root = leds_root if leds_root is not None else LEDS_ROOT
    bits: list[bool] = []
    for i in range(1, _MAX_PLAYER_LEDS + 1):
        alvo = f"{root}/{hid_instance}:green:player-{i}/brightness"
        try:
            with open(alvo, encoding="ascii") as fh:
                bits.append(int(fh.read().strip() or "0") > 0)
        except (OSError, ValueError):
            return None
    acesos = bits.count(True)
    if bits != [i < acesos for i in range(_MAX_PLAYER_LEDS)]:
        return -1  # buracos: alguém escreveu um padrão que não é nosso
    azul = False
    try:
        with open(_blue_node(root, hid_instance), encoding="ascii") as fh:
            azul = int(fh.read().strip() or "0") > 0
    except (OSError, ValueError):
        azul = False
    return acesos + _BLUE_PLAYER_LED if azul else acesos


def _hid_device_dir(hidraw_dev: str | None) -> str | None:
    """Diretório real do device HID do ``hidraw`` (onde ficam os nós de LED)."""
    if not hidraw_dev:
        return None
    name = os.path.basename(str(hidraw_dev))
    if not name.startswith("hidraw"):
        return None
    try:
        return os.path.realpath(f"/sys/class/hidraw/{name}/device")
    except OSError:
        return None


def resolve_external_leds(
    hidraw_dev: str | None, leds_root: str | None = None
) -> tuple[str | None, str | None]:
    """Descobre COMO indicar a posição no LED do externo, pelo modo do controle.

    Devolve ``("nintendo", inst)`` quando há a barra verde de player
    (``<inst>:green:player-N``, modo Switch/8BitDo-cabo — ``inst`` = instância
    HID); ``("ds4", prefixo)`` quando só há a lightbar RGB do DualShock4
    (``<inputNN>:red|:green|:blue``, caso do 8BitDo por Bluetooth — o prefixo é
    o ``inputNN`` real, NÃO a instância HID); ``(None, None)`` sem nenhum.

    A lightbar do DS4 usa prefixo ``inputNN`` arbitrário (não a instância HID),
    então é resolvida por ``realpath``: o nó ``:red`` cujo device é o mesmo do
    ``hidraw``. Best-effort; nunca levanta.
    """
    root = leds_root if leds_root is not None else LEDS_ROOT
    inst = hid_instance_for_hidraw(hidraw_dev)
    if inst and glob.glob(f"{root}/{inst}:green:player-*"):
        return ("nintendo", inst)
    hid_dir = _hid_device_dir(hidraw_dev)
    if hid_dir:
        for red in glob.glob(f"{root}/*:red"):
            try:
                if os.path.realpath(red).startswith(hid_dir):
                    base = os.path.basename(red)
                    return ("ds4", base[: -len(":red")])
            except OSError:
                continue
    return (None, None)


def write_lightbar_slot(
    prefix: str, slot: int, leds_root: str | None = None
) -> bool:
    """Pinta a lightbar RGB (DualShock4) com a cor canônica do ``slot``.

    O 8BitDo por Bluetooth cai em modo DS4 — o KERNEL só expõe a lightbar RGB
    (``<prefix>:red|:green|:blue`` + ``:global`` mestre 0/1). Como indicador
    de posição, acende a lightbar na cor do slot (1=azul, 2=vermelho, 3=verde,
    4=rosa — a MESMA paleta dos DualSense). Best-effort: ``False`` se os nós não
    existem/são graváveis (sem a regra udev do DS4, sem regressão).

    .. warning::

       **NOTA DATADA — 07/08/2026: esta docstring dizia "sem barra de player", e
       a frase era falsa sobre o PLÁSTICO.** A mantenedora corrigiu, olhando o
       aparelho: *"não há lightbar mas existe led de identificação de player
       nele também, igual o pro controller"*.

       O que é verdade, e a distinção importa: o **driver** ``hid-playstation``
       registra ``player_leds[5]`` apenas no caminho do DualSense
       (``assets/dkms/hid-playstation/hid-playstation.c:250-252`` e o laço de
       registro em ``:1946``); no caminho do DualShock4 existe só
       ``lightbar_leds`` (``:2348``). Isso é correto para o DS4 da Sony, que de
       fato não tem a barra — e **errado como descrição do 8BitDo**, que é um
       clone com quatro luzes no plástico falando um protocolo que não as prevê.

       **O que ninguém mediu, e bloqueia a numeração dele:** quem acende aquelas
       luzes. Ou o firmware do 8BitDo traduz a cor da lightbar que escrevemos
       aqui para os LEDs físicos — e então esta função já numera o aparelho —,
       ou ele as acende por conta própria e ignora o que mandamos, e então esta
       função escreve num lugar que não chega a lugar nenhum.

       **GRAU: SEM PROVA.** A medição que decide custa uma escrita e o olho dela:
       pintar um slot conhecido e perguntar o que as luzes fizeram. Está na
       ``P-4`` de :doc:`docs/protocol/externos-referencia-canonica`.
    """
    from hefesto_dualsense4unix.core.led_control import player_slot_color

    root = leds_root if leds_root is not None else LEDS_ROOT
    r, g, b = player_slot_color(slot)
    escreveu = _set_brightness(f"{root}/{prefix}:red/brightness", r)
    escreveu = _set_brightness(f"{root}/{prefix}:green/brightness", g) or escreveu
    escreveu = _set_brightness(f"{root}/{prefix}:blue/brightness", b) or escreveu
    # ``global`` é o mestre 0/1 da lightbar DS4 — liga p/ a cor valer.
    _set_brightness(f"{root}/{prefix}:global/brightness", 1)
    return escreveu


def apply_player_number(
    hidraw_dev: str | None, slot: int, leds_root: str | None = None
) -> bool:
    """Acende o indicador de posição do controle externo NO MODO que ele estiver.

    Switch/8BitDo-cabo (barra verde) -> :func:`write_player_number`; 8BitDo por
    Bluetooth (modo DS4, lightbar RGB) -> :func:`write_lightbar_slot` com a cor
    do slot. Assim a numeração vale por CABO e por BLUETOOTH. Best-effort.
    """
    kind, ident = resolve_external_leds(hidraw_dev, leds_root)
    if kind == "nintendo" and ident:
        return write_player_number(ident, slot, leds_root)
    if kind == "ds4" and ident:
        return write_lightbar_slot(ident, slot, leds_root)
    return False


__all__ = [
    "LEDS_ROOT",
    "apply_player_number",
    "build_enable_imu_packet",
    "enable_imu",
    "hid_instance_for_hidraw",
    "read_player_pattern",
    "resolve_external_leds",
    "write_lightbar_slot",
    "write_player_number",
]
