"""Blueprint canônico USB do DualSense, embutido no pacote (VPAD-03 / BT-01).

Por que embutido
----------------
O vpad uhid precisava LER o controle físico na hora de nascer (descriptor via
sysfs + features 0x05/0x09/0x20 via HIDIOCGFEATURE). Isso criava quatro modos de
falha, e um deles foi PROVADO ao vivo (Estudo 1, 2026-07-16): por Bluetooth, com
o controle ocioso na mesa, o firmware emudece — BlueZ segue dizendo
"Connected: yes", mas cada GET_REPORT estoura o timeout de 5 s do `hidp` do
kernel com EIO, por janelas de MINUTOS. O blueprint falhava e o vpad caía para
uinput `054c:0ce6`, indistinguível do físico — a receita do "jogo com zero
controles" quando a launch option `IGNORE_DEVICES=0x054c/0x0ce6` está persistida
na Steam. Agravante: o descriptor do físico em BT tem 321 B COM o item `85 31`
(input 0x01 de ~10 B) — copiá-lo produzia um vpad `BUS_USB` torto mesmo quando a
leitura funcionava.

Com o blueprint canônico embutido, o vpad **nunca mais lê o físico**: sobe uhid
Edge (`054c:0df2`) sempre — em BT, em USB, até sem controle conectado — e o
Bluetooth deixa de importar para o vpad.

Procedência (fossilizada, com validação viva)
---------------------------------------------
Capturado em 2026-07-16 de um DualSense físico (054c:0ce6) por CABO USB, via
HIDIOCGFEATURE read-only — o MESMO controle/firmware (update `0x0630`,
"Jul  4 2025") da validação viva do vpad uhid (commit bfd51db). O descriptor é
byte-idêntico a `captures/dualsense_usb_descriptor_054c0ce6.bin` (conferido com
`cmp` ao vivo); os features 0x05/0x20 estão em
`captures/dualsense_usb_feature_0x05_calibracao.bin` e
`captures/dualsense_usb_feature_0x20_firmware.bin`, e o teste hermético compara
as constantes com os `.bin` byte a byte. Recaptura/diagnóstico:
`scripts/capture_blueprint.py`.

O feature 0x09 (pairing) NUNCA é fossilizado de um controle real — ele carrega o
MAC do device e o MAC do host pareado (identidade). O template abaixo tem as
duas áreas de MAC zeradas e só preserva a assinatura `08 25 00` (bytes 7-9) que
o report real exibe; o `start()` do vpad carimba os bytes 1..6 com o MAC forjado
do jogador (`player_mac()` → `02:fe:00:00:00:0N`, em little-endian) — é o que o
probe do `hid_playstation` lê (`dualsense_get_mac_address`), e MAC duplicado
derruba o probe com -EEXIST.

Limitações aceitas (decisão dos sprints VPAD-03/BT-01)
------------------------------------------------------
- **Congela a calibração (0x05) de UMA unidade e o firmware (0x20)**. Inócuo
  hoje: o vpad emite motion neutro e não repassa gyro/accel do físico. **Se um
  dia houver passthrough de gyro/touchpad, a calibração por unidade volta a
  importar** — este blueprint terá de ser por-controle de novo.
- **O firmware do 0x20 decide o modo de vibração do kernel**: update version
  `0x0630` (bytes 44-45, LE) ≥ `0x0215` liga `use_vibration_v2` no
  `hid_playstation` — é o caminho validado ao vivo nesta base (o parser do
  `uhid_gamepad` cobre os dois pela máscara `_VIBRATION_FLAGS = 0x03`).
- **O par (kernel `hid_playstation`, blueprint congelado) vira a matriz de
  compatibilidade**: um kernel futuro que exija um feature novo no probe derruba
  o bind e o vpad cai no fallback uinput — visível pelo log da factory (e pelo
  badge de degradação da GUI, item VPAD-05).
- O vpad é sempre `BUS_USB` emitindo report 0x01 de 64 B, independente do
  transporte do físico — por design (o descriptor BT com `85 31` é impróprio por
  construção).
"""
from __future__ import annotations

from typing import Any

#: Report descriptor USB do DualSense — 289 bytes, SEM o item `85 31` (o input
#: 0x01 aqui é o de 64 B do transporte USB, que é o que o vpad emite).
CANONICAL_DESCRIPTOR_USB: bytes = bytes.fromhex(
    "05010905a1018501093009310932093509330934150026ff007508950681020600ff0920"
    "9501810205010939150025073500463b016514750495018142650005091901290f150025"
    "017501950f81020600ff0921950d81020600ff0922150026ff0075089534810285020923"
    "952f9102850509339528b10285080934952fb102850909249513b102850a0925951ab102"
    "850b09419529b102850c09429529b10285200926953fb102852109279504b10285220940"
    "953fb10285800928953fb10285810929953fb1028582092a9509b1028583092b953fb102"
    "8584092c953fb1028585092d9502b10285a0092e9501b10285e0092f953fb10285f00930"
    "953fb10285f10931953fb10285f20932950fb10285f40935953fb10285f509369503b102"
    "c0"
)

#: Feature 0x05 — calibração de gyro/accel, 41 bytes. TEM que ser bytes de um
#: DualSense real (o `hid_playstation` usa os campos como divisores/escala em
#: `dualsense_get_calibration_data`; uma "calibração neutra" inventada, com
#: zeros, pode rejeitar o probe ou quebrar o motion).
CANONICAL_FEATURE_0X05: bytes = bytes.fromhex(
    "051700fdfffcffa32285dd87226fdd882275dd1c021c020420f9df711f76dfe71fdedf0d"
    "0000000000"
)

#: Feature 0x20 — info de firmware, 64 bytes ("Jul  4 2025", update `0x0630`
#: nos bytes 44-45 LE). Decide `use_vibration_v2` no driver (limiar `0x0215`).
CANONICAL_FEATURE_0X20: bytes = bytes.fromhex(
    "204a756c202034203230323531303a31303a333203000400100700002a00100100d80000"
    "0000000000000000300600003c0001000a0002000600000000000000"
)

#: Feature 0x09 — pairing info, 20 bytes (`DS_FEATURE_REPORT_PAIRING_INFO_SIZE`
#: do hid-playstation.c). SANITIZADO por construção: bytes 1..6 (MAC do device)
#: e 10..15 (MAC do host pareado) zerados; bytes 7-9 preservam a assinatura
#: `08 25 00` do report real. O MAC de verdade entra em runtime — o `start()`
#: do vpad sobrescreve os bytes 1..6 com o MAC forjado do jogador
#: (`02:fe:00:00:00:0N`, LE), que é o único campo que o probe USB lê.
TEMPLATE_FEATURE_0X09: bytes = bytes.fromhex(
    "0900000000000008250000000000000000000000"
)


def canonical_blueprint() -> dict[str, Any]:
    """Blueprint sintético pronto para `UhidDualSense` — nunca lê o físico.

    Mesmo shape do (hoje diagnóstico) `capture_dualsense_blueprint`:
    ``{"descriptor": bytes, "features": {id: bytes}}``. Devolve um dict NOVO a
    cada chamada: o `start()` do vpad deriva os features por cópia, mas um
    caller que mutasse o dict compartilhado envenenaria todos os vpads seguintes
    (co-op cria até 4).
    """
    return {
        "descriptor": CANONICAL_DESCRIPTOR_USB,
        "features": {
            0x05: CANONICAL_FEATURE_0X05,
            0x09: TEMPLATE_FEATURE_0X09,
            0x20: CANONICAL_FEATURE_0X20,
        },
    }


__all__ = [
    "CANONICAL_DESCRIPTOR_USB",
    "CANONICAL_FEATURE_0X05",
    "CANONICAL_FEATURE_0X20",
    "TEMPLATE_FEATURE_0X09",
    "canonical_blueprint",
]
