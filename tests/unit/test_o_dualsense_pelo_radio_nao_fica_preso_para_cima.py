"""O lançamento não troca o DualSense nativo pelo XInput para curar o menu preso do rádio.

Sprint O-DUALSENSE-PELO-RADIO-FICA-PRESO-PARA-CIMA-NO-DIRECTINPUT-01, decisão
`D-2310-O-MENU-PRESO-DO-RADIO-E-DO-WINE`. No Modo Nativo pelo rádio, o Wine
ordena os objetos do DirectInput pela posição no descritor do rádio, e o
InControl do Mullet MadJack lê o gatilho como o direcional (sessão E, 23/10).
O `PROTON_SONY_HIDRAW_XINPUT=1` destrava o menu, mas o PRAGMATA deixa de
escrever no controle e fica no report curto (sessão F: fixup desligado 0 vezes
contra 2, nenhum report de 78 bytes): a háptica e os gatilhos se perdem. O
`PROTON_PREFER_SDL` tira o controle do jogo. Nenhum estado do daemon compõe os
dois, e o lançamento não os deixa passar pela allowlist.
"""
from __future__ import annotations

import pytest

from hefesto_dualsense4unix.daemon import launch_env as le

_TROCAM_O_NATIVO = ("PROTON_SONY_HIDRAW_XINPUT", "PROTON_PREFER_SDL", "PROTON_USE_SDL")

_ESTADOS = [
    (True, "dualsense", "uhid"),
    (False, "dualsense", "uhid"),
    (False, "dualsense", "uinput"),
    (False, "xbox", "uinput"),
    (False, "nintendo", "uinput"),
]


@pytest.mark.parametrize(("nativo", "mascara", "backend"), _ESTADOS)
@pytest.mark.parametrize("fisicos", [0, 1, 4])
def test_nenhum_estado_troca_o_dualsense_nativo_pelo_xinput(
    nativo: bool, mascara: str, backend: str, fisicos: int
) -> None:
    """MORDIDA: compor o `PROTON_SONY_HIDRAW_XINPUT` no Modo Nativo, e esta reprova."""
    env = le.compose_env(native_mode=nativo, emulation_enabled=True, flavor=mascara,
                         backends=[backend], fisicos=fisicos)
    for nome in _TROCAM_O_NATIVO:
        assert nome not in env


def test_a_allowlist_nao_deixa_passar_a_troca() -> None:
    for nome in _TROCAM_O_NATIVO:
        assert nome not in le.ENV_ALLOWLIST
