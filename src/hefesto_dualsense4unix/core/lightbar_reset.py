"""LIGHTBAR-BT-RESET-01: destrava a lightbar do DualSense por Bluetooth.

O QUE ACONTECE (provado ao vivo 2026-07-17/18 + estudo de 5 agentes): a ADOÇÃO
do controle pelo daemon (abertura do hidraw pela pydualsense + feature reads do
``init``) derruba o "claim" da lightbar na máquina de estados do FIRMWARE — a
lightbar apaga no ato e passa a IGNORAR as escritas de cor do kernel (rota
sysfs ``multi_intensity``; 330 mil escritas ignoradas ao vivo), enquanto
player-LEDs e gatilhos adaptativos seguem funcionando (não têm máquina de
estados própria). O estado ruim persiste até o POWER-OFF físico do controle
(sobrevive a re-parear e a rebind do driver; cabo USB escapa — o caminho USB
não tem esse claim).

A CURA (o que o SDL faz em toda conexão BT e o driver do kernel nunca faz —
``DS_OUTPUT_VALID_FLAG1_RELEASE_LEDS`` é definido e jamais usado): enviar UM
report de output 0x31 BEM-FORMADO com ``valid_flag1 = 0x08`` ("Reset LED
state") — devolve a lightbar ao host, e a próxima escrita de cor volta a colar.

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


def send_release_leds(device: Any) -> bool:
    """Envia o report de Reset LED state por um device hidapi já aberto.

    ``device`` é o ``hidapi.Device`` do handle pydualsense (a adoção acabou de
    abri-lo — reusar evita abrir o hidraw duas vezes). Best-effort: ``False``
    em qualquer falha, nunca levanta (a adoção segue; sem a cura o sintoma é
    só a lightbar apagada, o comportamento pré-fix).
    """
    try:
        report = build_bt_release_leds_report()
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


__all__ = ["BT_REPORT_LEN", "build_bt_release_leds_report", "send_release_leds"]
