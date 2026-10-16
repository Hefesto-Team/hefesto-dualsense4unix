"""LIGHTBAR-BT-RESET-01: destrava a lightbar do DualSense por Bluetooth.

O QUE ACONTECE (provado ao vivo 2026-07-17/18 + 5 corridas de estudo): a ADOÇÃO
do controle pelo daemon (abertura do hidraw pela pydualsense + feature reads do
``init``) derruba o "claim" da lightbar na máquina de estados do FIRMWARE — a
lightbar apaga no ato e passa a IGNORAR as escritas de cor do kernel (rota
sysfs ``multi_intensity``; 330 mil escritas ignoradas ao vivo), enquanto
player-LEDs e gatilhos adaptativos seguem funcionando (não têm máquina de
estados própria). O estado ruim persiste até o POWER-OFF físico do controle
(sobrevive a re-parear e a rebind do driver; cabo USB escapa — o caminho USB
não tem esse claim).

O GESTO MANUAL DE ÚLTIMO RECURSO (``hefesto lightbar-reset`` / IPC
``lightbar.reset``): enviar UM report de output 0x31 BEM-FORMADO com
``valid_flag1 = 0x08`` ("Reset LED state") — é o que o SDL faz em toda conexão
BT e o driver do kernel nunca faz (``DS_OUTPUT_VALID_FLAG1_RELEASE_LEDS`` é
definido e jamais usado). Devolve a lightbar ao host, e a próxima escrita de
cor volta a colar.

**Isto NÃO é cura automática, e chamá-la assim foi o erro deste cabeçalho até
22/08/2026.** O envio AUTOMÁTICO na adoção foi medido como NOCIVO — o
LIGHTBAR-BT-CULPADO-01 (03/08) correlacionou 7 de 7 o travamento da barra com o
``0x08`` que NÓS mandávamos na janela de conexão, e ele saiu do código em
``108b711`` (04/08). O código está coerente com essa decisão: 776 reports
capturados no fio em 22/08 trazem **zero** ``RELEASE_LEDS``. Quem estava
incoerente era este texto — que prometia como remédio de rotina o que a
medição derrubou (ver ``core/backend_pydualsense.py``, o bloco do
LIGHTBAR-BT-CULPADO-01, e o F9 do
a sprint `LUZ-CEGA-01`).

LAYOUT (validado contra o binário do hid-playstation DESTA máquina, por
desmontagem — estudo 2026-07-18): ``[0]=0x31``, ``[1]=seq<<4`` (nibble alto;
o SDL usa 0 fixo e o firmware aceita), ``[2]=0x10`` (tag mágico OBRIGATÓRIO),
common de 47 bytes em ``[3..49]`` (``[3]``=valid_flag0, ``[4]``=valid_flag1),
CRC-32 little-endian em ``[74..77]`` sobre o byte de seed ``0xA2`` (header
HIDP DATA|OUTPUT) + os bytes ``[0..73]``.
"""
from __future__ import annotations

from typing import Any

from hefesto_dualsense4unix.core.ds_output_report import (
    BT_REPORT_LEN,
    COMMON_LEN,
    VALID_FLAG1_RELEASE_LEDS,
    build_bt_report,
)
from hefesto_dualsense4unix.utils.logging_config import get_logger

logger = get_logger(__name__)


def build_bt_release_leds_report(seq: int = 0) -> bytes:
    """Report 0x31 mínimo com flag1=0x08 (Reset LED state) e CRC válido.

    Todos os demais flags/campos ZERADOS — não toca rumble, gatilhos, player
    LEDs nem cor; só devolve o claim da lightbar ao host. ``seq`` é o nibble
    de sequência (0..15); o firmware aceita 0 fixo (comportamento do SDL).
    Envelope/CRC vêm do builder comum (BTREPORT-02: `core/ds_output_report`).
    """
    common = bytearray(COMMON_LEN)
    common[1] = VALID_FLAG1_RELEASE_LEDS  # common.valid_flag1 ([0] é o flag0)
    return bytes(build_bt_report(common, seq=seq))


def send_release_leds(handle: Any) -> bool:
    """Envia o report de Reset LED state pelo handle pydualsense já aberto.

    LIGHTBAR-BT-RESET-03 (22/07, regressão MEDIDA ao vivo): desde o BTREPORT-02
    (18/07) todo 0x31 nosso sai com o nibble de SEQUÊNCIA POR-HANDLE — o
    ``writeReport`` do handle carimba ``seq`` + CRC e incrementa o contador. O
    reset, porém, escrevia DIRETO no ``device`` com ``seq=0`` fixo, e depois que
    o keepalive/réplica já tinha rodado o claim NUNCA era devolvido — a lightbar
    BT ficava apagada com todas as escritas de cor ignoradas (journal 22/07
    14:55: ``lightbar_reset_enviado`` + cor escrita e barra escura); a cura de
    17/07 funcionava quando TODOS os reports saíam com seq 0. Que o firmware jogue
    fora o número repetido foi a leitura daquele dia, não medida isolada; quem
    mede é ``scripts/ensaios/a_sequencia_do_radio.py``. O reset passa pelo MESMO
    ``writeReport`` (seq/CRC na ordem real do fluxo); ``device`` cru continua como fallback
    (testes/objetos sem writeReport — comportamento antigo).

    Best-effort: ``False`` em qualquer falha, nunca levanta (a adoção segue;
    sem a cura o sintoma é só a lightbar apagada, o comportamento pré-fix).
    """
    try:
        report = build_bt_release_leds_report()
        writer = getattr(handle, "writeReport", None)
        if callable(writer):
            writer(list(report))
            return True
        device = getattr(handle, "device", handle)
        written = device.write(report)
        ok = written is None or int(written) == len(report)
        if not ok:
            logger.warning(
                "lightbar_reset_write_incompleto", written=written, len=len(report)
            )
        return ok
    except Exception as exc:
        logger.warning("lightbar_reset_falhou", err=str(exc))
        return False


def should_reclaim_on_wake(
    transport: str,
    desired_rgb: tuple[int, int, int] | None,
    current_sysfs_rgb: tuple[int, int, int] | None,
    kernel_default: tuple[int, int, int],
) -> bool:
    """LIGHTBAR-BT-RESET-02 (Onda L): a assinatura do wake BT numa reconciliação
    de hotplug SEM handle novo.

    Um wake/resume BT que NÃO reabre o handle (caso medido 2026-07-20 17:28)
    devolve a classe LED à cor default do kernel (``KERNEL_DEFAULT_BLUE``) com o
    mesmo ``indicator_dir``, enquanto o desired resolvido é OUTRA cor. O 0x08
    saiu (LIGHTBAR-BT-CULPADO-01): desde 16/10/2026 o backend repinta toda cor
    lida diferente da resolvida, e esta função só CLASSIFICA o episódio no
    diário (wake ou escritor de fora).

    - ``transport`` != ``bt``: USB não tem o claim → nunca.
    - ``desired_rgb`` None ou == ``kernel_default``: sem cor resolvida ou o
      próprio desired É o default → a assinatura é indistinguível → não mexe.
    - ``current_sysfs_rgb`` None (nó ilegível) → não afirma a borda → não mexe.
    - só ``True`` quando a cor atual do nó == default do kernel (a classe foi
      resetada) e o desired é diferente.
    """
    if transport != "bt":
        return False
    if desired_rgb is None or tuple(desired_rgb) == tuple(kernel_default):
        return False
    if current_sysfs_rgb is None:
        return False
    return tuple(current_sysfs_rgb) == tuple(kernel_default)


__all__ = [
    "BT_REPORT_LEN",
    "build_bt_release_leds_report",
    "send_release_leds",
    "should_reclaim_on_wake",
]
