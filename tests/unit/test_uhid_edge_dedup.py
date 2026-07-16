"""UHID-04: o vpad UHID se apresenta como DualSense **Edge** (054c:0df2), distinto
do controle físico (054c:0ce6).

Essa é a raiz da desduplicação no layout PS: com físico e vpad no MESMO 054c:0ce6,
`SDL_GAMECONTROLLER_IGNORE_DEVICES=0x054c/0x0ce6` escondia os dois. Com o vpad em
0x0df2, a mesma opção esconde só o físico e o vpad sobrevive. O bind do Edge foi
validado ao vivo (`playstation ...054C:0DF2...: Registered DualSense controller`).
"""
import struct

from hefesto_dualsense4unix.integrations import uhid_gamepad as uhid
from hefesto_dualsense4unix.integrations.uinput_gamepad import UinputGamepad


def test_vpad_product_e_edge_distinto_do_fisico():
    assert uhid.VPAD_PRODUCT == 0x0DF2
    assert uhid.DUALSENSE_PRODUCT == 0x0CE6
    # o coração da cura: o PID do vpad NÃO pode colidir com o do físico
    assert uhid.VPAD_PRODUCT != uhid.DUALSENSE_PRODUCT


def test_uhid_default_product_e_edge():
    assert uhid.UhidDualSense(player=1).product == 0x0DF2


def test_create2_event_encoda_vid_pid_edge():
    """O CREATE2 vai ao kernel com 054c:0df2 — é o que o hid_playstation registra
    como DualSense e o SDL vê como PS5 com PID próprio (sobrevive ao IGNORE)."""
    pad = uhid.UhidDualSense(player=1)
    event = pad._create2_event(b"\x00" * 8)
    vendor = struct.unpack("<I", event[264:268])[0]
    product = struct.unpack("<I", event[268:272])[0]
    assert (vendor, product) == (0x054C, 0x0DF2)


def test_product_e_campo_overridavel():
    """`product` é campo do dataclass — permite forjar outro PID em teste/futuro
    (ex.: se um dia o físico for um Edge, o vpad pode virar 0x0ce6)."""
    pad = uhid.UhidDualSense(player=2, product=0x0CE6)
    event = pad._create2_event(b"\x00" * 8)
    assert struct.unpack("<I", event[268:272])[0] == 0x0CE6


def test_backend_property_distingue_os_dois_vpads():
    """O botão de Launch Options decide a variante pelo backend — uhid tem PID
    próprio (desduplica), uinput no flavor dualsense é fallback (não desduplica)."""
    assert uhid.UhidDualSense(player=1).backend == "uhid"
    assert UinputGamepad.for_flavor("xbox").backend == "uinput"
    assert UinputGamepad.for_flavor("dualsense").backend == "uinput"
