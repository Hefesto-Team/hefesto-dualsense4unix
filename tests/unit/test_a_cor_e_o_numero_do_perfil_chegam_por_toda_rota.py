"""A-COR-E-O-NUMERO-DO-PERFIL-CHEGAM-POR-TODA-ROTA-01 — a ativação pinta cada um.

A ativação de um perfil (`profiles/manager.py`) chama, nesta ordem,
`apply_output_defaults`, `set_led_scales`, `reset_profile_overrides` e
`reassert_resolved_outputs`. A cor AUTOMÁTICA de cada controle e o número de
cada um vêm do provider, e só o reassert os escreve. Até 09/10/2026 o reassert
percorria `self._sysfs` e escrevia só na classe LED: no rádio o `0x31` não saía
(com a Steam no hidraw, o sysfs não muda a barra), e sem a regra do udev (nó
nenhum gravável) ele não tocava controle nenhum.

O backend é o do produto; só o handle e o nó são dublês, e os dois anotam o que
receberam. A mesa tem quatro: P1 e P2 no cabo, P3 e P4 no rádio.
"""
from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from pydualsense.enums import PlayerID
from pydualsense.pydualsense import DSAudio, DSLight, DSTrigger

from hefesto_dualsense4unix.core import backend_pydualsense as bp
from hefesto_dualsense4unix.core.controller import OutputSpec
from hefesto_dualsense4unix.core.lightbar_gatilho import (
    COMMON_LIGHTBAR_B,
    COMMON_LIGHTBAR_R,
    COMMON_PLAYER_LEDS,
    mascara_de_player_leds,
)

MACS = (
    "AA:BB:CC:00:00:01",
    "AA:BB:CC:00:00:02",
    "AA:BB:CC:00:00:03",
    "AA:BB:CC:00:00:04",
)
TRANSPORTES = ("usb", "usb", "bt", "bt")
CORES = ((0, 90, 255), (255, 40, 40), (40, 220, 60), (230, 0, 230))
NUMEROS = (
    (False, False, True, False, False),
    (False, True, False, True, False),
    (True, False, True, False, True),
    (True, True, False, True, True),
)
COR_GLOBAL = (9, 9, 9)
NUMERO_GLOBAL = (False, False, False, False, True)
POS_FLAG1 = 3 + 1
FLAG1_LIGHTBAR = 0x04
FLAG1_PLAYER = 0x10


class _NoDeLed:
    """A classe LED do kernel de um controle (a regra 77 instalada)."""

    def __init__(self) -> None:
        self.cores: list[tuple[int, int, int]] = []
        self.numeros: list[tuple[bool, ...]] = []
        self.indicator_dir = "/sys/class/leds/x"

    def writable(self) -> bool:
        return True

    def set_rgb(self, r: int, g: int, b: int, *, verify: bool = False) -> bool:
        self.cores.append((r, g, b))
        return True

    def set_players(self, bits: tuple[bool, ...]) -> bool:
        self.numeros.append(tuple(bits))
        return True

    def set_players_verified(self, bits: tuple[bool, ...]) -> bool:
        return self.set_players(bits)

    def invalidate_cache(self) -> None:
        return None

    def get_rgb(self) -> tuple[int, int, int] | None:
        return self.cores[-1] if self.cores else None


def _handle(transporte: str) -> SimpleNamespace:
    escritos: list[list[int]] = []
    nome = "BT_31" if transporte == "bt" else "USB_01"
    handle = SimpleNamespace(
        conType=SimpleNamespace(name=nome),
        triggerL=DSTrigger(),
        triggerR=DSTrigger(),
        light=DSLight(),
        audio=DSAudio(),
        _raw_trigger_left=None,
        _raw_trigger_right=None,
        _output_muted=False,
        escritos=escritos,
    )

    def _escreve(report: Any) -> int:
        escritos.append(list(report))
        return len(report)

    handle.writeReport = _escreve
    return handle


def _automatica(uniq: str) -> bp._DesiredOutput | None:
    for indice, mac in enumerate(MACS):
        if mac.replace(":", "").lower() == uniq:
            return bp._DesiredOutput(led=CORES[indice], player_leds=NUMEROS[indice])
    return None


def _mesa(
    *, com_nos: bool
) -> tuple[bp.PyDualSenseController, list[SimpleNamespace], dict[str, _NoDeLed]]:
    ctl = bp.PyDualSenseController()
    handles = [_handle(t) for t in TRANSPORTES]
    ctl._handles = dict(zip(MACS, handles, strict=True))
    nos = {mac: _NoDeLed() for mac in MACS} if com_nos else {}
    ctl._sysfs = dict(nos)
    ctl.set_auto_output_provider(_automatica)
    return ctl, handles, nos


def _ativar(ctl: bp.PyDualSenseController) -> None:
    """A sequência de `ProfileManager.activate`, na ordem de produto."""
    ctl.apply_output_defaults(OutputSpec(led=COR_GLOBAL, player_leds=NUMERO_GLOBAL))
    ctl.set_led_scales(None)
    ctl.reset_profile_overrides({})
    ctl.reassert_resolved_outputs()


def _cor(report: list[int]) -> tuple[int, ...]:
    common = report[3:50]
    return tuple(common[COMMON_LIGHTBAR_R : COMMON_LIGHTBAR_B + 1])


def _ultimo_quadro(handle: SimpleNamespace) -> tuple[tuple[int, ...], int]:
    """A cor e o número do último `0x31` que carrega os dois."""
    completos = [
        r for r in handle.escritos
        if r[0] == 0x31
        and r[POS_FLAG1] & FLAG1_LIGHTBAR
        and r[POS_FLAG1] & FLAG1_PLAYER
    ]
    assert completos, "nenhum 0x31 com a cor e o número saiu por este rádio"
    ultimo = completos[-1]
    return _cor(ultimo), ultimo[3:50][COMMON_PLAYER_LEDS]


def _quadros(handle: SimpleNamespace) -> int:
    return sum(1 for r in handle.escritos if r[0] == 0x31)


def _confere_a_mesa(handles: list[SimpleNamespace], nos: dict[str, _NoDeLed]) -> None:
    for indice, (mac, handle) in enumerate(zip(MACS, handles, strict=True)):
        cor, numero = CORES[indice], NUMEROS[indice]
        no = nos.get(mac)
        if no is not None:
            assert no.cores[-1] == cor, f"P{indice + 1}: a cor do nó"
            assert no.numeros[-1] == numero, f"P{indice + 1}: o número do nó"
        if TRANSPORTES[indice] == "bt":
            assert _ultimo_quadro(handle) == (cor, mascara_de_player_leds(numero)), (
                f"P{indice + 1}: o 0x31 do rádio"
            )
        elif no is None:
            assert handle.light.TouchpadColor == cor, f"P{indice + 1}: a cor no fluxo"
            assert handle.light.playerNumber == PlayerID(
                mascara_de_player_leds(numero)
            ), f"P{indice + 1}: o número no fluxo"


def test_o_global_da_ativacao_sai_tambem_pelo_radio() -> None:
    """`apply_output_defaults` passa a cor e o número à segunda rota, como o `set_led`."""
    ctl, handles, _nos = _mesa(com_nos=True)

    ctl.apply_output_defaults(OutputSpec(led=COR_GLOBAL, player_leds=NUMERO_GLOBAL))

    for handle in handles[2:]:
        cores = [_cor(r) for r in handle.escritos if r[POS_FLAG1] & FLAG1_LIGHTBAR]
        numeros = [
            r[3:50][COMMON_PLAYER_LEDS]
            for r in handle.escritos
            if r[POS_FLAG1] & FLAG1_PLAYER
        ]
        assert cores == [COR_GLOBAL], "a cor global não saiu pelo 0x31"
        assert numeros == [mascara_de_player_leds(NUMERO_GLOBAL)]


def test_com_os_nos_cada_um_termina_com_a_sua_cor_e_o_seu_numero() -> None:
    ctl, handles, nos = _mesa(com_nos=True)

    _ativar(ctl)

    _confere_a_mesa(handles, nos)


def test_sem_no_nenhum_o_cabo_vai_pelo_fluxo_e_o_radio_pelo_0x31() -> None:
    """Quem instala sem a regra do udev: nenhum nó gravável entra no `_sysfs`."""
    ctl, handles, nos = _mesa(com_nos=False)

    _ativar(ctl)

    _confere_a_mesa(handles, nos)


def test_o_reassert_sem_mudanca_nao_gasta_o_radio_e_o_vigia_gasta() -> None:
    """Cada report no rádio custa duas fatias, e o reassert roda a cada tique."""
    ctl, handles, _nos = _mesa(com_nos=False)
    _ativar(ctl)
    antes = [_quadros(h) for h in handles[2:]]

    ctl.reassert_resolved_outputs()

    assert [_quadros(h) for h in handles[2:]] == antes, "o reassert repetiu o 0x31"

    ctl.reafirmar_barra_e_numero(MACS[2:])

    assert [_quadros(h) for h in handles[2:]] == [n + 1 for n in antes], (
        "o vigia obedeceu à memória do reassert"
    )


def test_a_cor_que_muda_volta_a_sair_pelo_radio() -> None:
    """A memória é do quadro: cor nova é quadro novo."""
    ctl, handles, _nos = _mesa(com_nos=False)
    _ativar(ctl)
    antes = _quadros(handles[2])

    ctl.apply_output_for(MACS[2], OutputSpec(led=(1, 2, 3)))
    ctl.reassert_resolved_outputs()

    assert _quadros(handles[2]) > antes
    assert _ultimo_quadro(handles[2])[0] == (1, 2, 3)


def test_handle_novo_esquece_a_memoria() -> None:
    """O rádio que reconectou nasce no azul do kernel: o quadro tem de sair de novo."""
    ctl, _handles, _nos = _mesa(com_nos=False)
    _ativar(ctl)
    novo = _handle("bt")
    ctl._handles[MACS[3]] = novo

    ctl.reassert_resolved_outputs()

    assert _ultimo_quadro(novo) == (CORES[3], mascara_de_player_leds(NUMEROS[3]))


def test_desligar_o_mudo_repinta_o_radio_e_o_cabo_sem_no() -> None:
    """O `set_output_mute(False)` usa o mesmo dono, e não só a classe LED."""
    ctl, handles, _nos = _mesa(com_nos=False)
    ctl.set_output_mute(True)

    ctl.set_output_mute(False)

    for indice in (2, 3):
        assert _ultimo_quadro(handles[indice]) == (
            CORES[indice],
            mascara_de_player_leds(NUMEROS[indice]),
        )
    assert handles[0].light.TouchpadColor == CORES[0]
    assert handles[1].light.TouchpadColor == CORES[1]
