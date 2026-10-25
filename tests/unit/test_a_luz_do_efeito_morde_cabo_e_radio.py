"""O quadro do efeito da luz chega à barra pelos DOIS transportes, nos quatro controles.

`luz.lightbar.efeito` só vira linha forte do mapa com um teste que morda cabo e rádio na MESMA
chamada. O laço da luz animada pinta cada quadro por `pintar_a_barra_sem_lembrar`, que cai em
`_write_partial_output`: no cabo a barra sai pelo nó do sysfs, no rádio sai também o `0x31` avulso
(com a Steam no hidraw o sysfs não muda a barra, só o `0x31` muda). A mesa tem quatro: P1 e P2 no
cabo, P3 e P4 no rádio, cada um com o seu quadro do efeito (o arco-íris defasa um quarto de volta
por controle).

O backend é o do produto; só o handle e o nó são dublês, e os dois anotam o que receberam.
MORDIDA: tirar o `0x31` do rádio (`_pintar_por_hidraw_bt`) reprova; tirar o nó do cabo reprova.
"""
from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest
from pydualsense.pydualsense import DSAudio, DSLight, DSTrigger

from hefesto_dualsense4unix.core import backend_pydualsense as bp
from hefesto_dualsense4unix.core.lightbar_gatilho import COMMON_LIGHTBAR_B, COMMON_LIGHTBAR_R
from hefesto_dualsense4unix.daemon.subsystems.luz_animada import escritor_de_producao
from hefesto_dualsense4unix.profiles.efeitos_de_luz import cor_no_instante
from hefesto_dualsense4unix.profiles.schema import ler_o_efeito_da_luz

#: Faixa forjada (`aa:bb:cc`), nunca endereço de aparelho de verdade.
MACS = tuple(f"AA:BB:CC:00:00:0{n}" for n in range(1, 5))
TRANSPORTES = ("usb", "usb", "bt", "bt")
POS_FLAG1 = 3 + 1
FLAG1_LIGHTBAR = 0x04
EFEITOS = (  # (noqa-acento) o texto que o perfil guarda
    "arco-iris;;7", "respirar;FF0000;2", "piscar;00FF00;3", "mare;0000FF;10")


class _NoDeLed:
    """A classe LED do kernel de um controle: guarda cada cor que o backend escreveu."""

    def __init__(self) -> None:
        self.cores: list[tuple[int, int, int]] = []
        self.indicator_dir = "/sys/class/leds/x"

    def writable(self) -> bool:
        return True

    def set_rgb(self, r: int, g: int, b: int, *, verify: bool = False) -> bool:
        self.cores.append((r, g, b))
        return True

    def set_players(self, bits: tuple[bool, ...]) -> bool:
        return True

    def set_players_verified(self, bits: tuple[bool, ...]) -> bool:
        return True

    def invalidate_cache(self) -> None:
        return None

    def get_rgb(self) -> tuple[int, int, int] | None:
        return self.cores[-1] if self.cores else None


def _handle(transporte: str) -> SimpleNamespace:
    escritos: list[list[int]] = []
    handle = SimpleNamespace(
        conType=SimpleNamespace(name="BT_31" if transporte == "bt" else "USB_01"),
        triggerL=DSTrigger(), triggerR=DSTrigger(), light=DSLight(), audio=DSAudio(),
        _raw_trigger_left=None, _raw_trigger_right=None, _output_muted=False, escritos=escritos)

    def _escreve(report: Any) -> int:
        escritos.append(list(report))
        return len(report)

    handle.writeReport = _escreve
    return handle


def _mesa() -> tuple[bp.PyDualSenseController, list[SimpleNamespace], dict[str, _NoDeLed]]:
    ctl = bp.PyDualSenseController()
    handles = [_handle(t) for t in TRANSPORTES]
    ctl._handles = dict(zip(MACS, handles, strict=True))
    nos = {mac: _NoDeLed() for mac in MACS}
    ctl._sysfs = dict(nos)
    return ctl, handles, nos


def _cor_do_0x31(report: list[int]) -> tuple[int, ...]:
    common = report[3:50]
    return tuple(common[COMMON_LIGHTBAR_R: COMMON_LIGHTBAR_B + 1])


def _quadros_0x31(handle: SimpleNamespace) -> list[tuple[int, ...]]:
    return [_cor_do_0x31(r) for r in handle.escritos
            if r[0] == 0x31 and r[POS_FLAG1] & FLAG1_LIGHTBAR]


def _quadro_do_efeito(texto: str, t: float, posicao: int) -> tuple[int, int, int]:
    efeito = ler_o_efeito_da_luz(texto)
    assert efeito is not None, texto
    return cor_no_instante(efeito, t, posicao=posicao, semente=posicao)


def _pintar_a_mesa(ctl: bp.PyDualSenseController, t: float) -> list[tuple[int, int, int]]:
    """O que o laço faz a cada tique: o quadro de cada controle, pela ponta do backend."""
    escrever, _soltar = escritor_de_producao(SimpleNamespace(controller=ctl))
    quadros = []
    for posicao, (mac, texto) in enumerate(zip(MACS, EFEITOS, strict=True)):
        quadro = _quadro_do_efeito(texto, t, posicao)
        saiu = escrever(mac.replace(":", "").lower(), quadro)
        assert saiu is True, f"P{posicao + 1}: o quadro não saiu"
        quadros.append(quadro)
    return quadros


def _confere_a_mesa(handles: list[SimpleNamespace], nos: dict[str, _NoDeLed],
                    quadros: list[tuple[int, int, int]]) -> None:
    for indice, (mac, handle) in enumerate(zip(MACS, handles, strict=True)):
        esperado = quadros[indice]
        assert nos[mac].cores and nos[mac].cores[-1] == esperado, f"P{indice + 1}: a cor do nó"
        if TRANSPORTES[indice] == "bt":
            vistos = _quadros_0x31(handle)
            assert vistos, f"P{indice + 1}: nenhum 0x31 com a cor saiu pelo rádio"
            assert vistos[-1] == esperado, f"P{indice + 1}: o 0x31 do rádio"
        else:
            assert not _quadros_0x31(handle), f"P{indice + 1}: o cabo não leva o 0x31"


@pytest.mark.parametrize("t", [0.0, 1.3, 4.2])
def test_o_quadro_do_efeito_chega_ao_no_no_cabo_e_ao_0x31_no_radio(t: float) -> None:
    ctl, handles, nos = _mesa()
    _confere_a_mesa(handles, nos, _pintar_a_mesa(ctl, t))


def test_o_arco_iris_defasa_cada_controle_e_cada_um_leva_o_seu_quadro() -> None:
    """Quatro quadros diferentes no mesmo instante: o rádio não repete o do vizinho."""
    ctl, handles, nos = _mesa()
    quadros = _pintar_a_mesa(ctl, 2.0)
    cores_do_arco = [  # (noqa-acento) chave ASCII
        _quadro_do_efeito("arco-iris;;7", 2.0, p) for p in range(4)]
    assert len(set(cores_do_arco)) == 4, "o arco-íris devia defasar os quatro controles"
    _confere_a_mesa(handles, nos, quadros)


def test_o_quadro_nao_entra_no_estado_desejado() -> None:
    """O efeito pinta sem lembrar: o desejado segue o do perfil e do gesto."""
    ctl, _handles, _nos = _mesa()
    _pintar_a_mesa(ctl, 0.0)
    assert not ctl._desired_by_uniq, "o quadro do efeito virou estado desejado"


def test_sem_o_0x31_o_radio_reprova(monkeypatch: pytest.MonkeyPatch) -> None:
    """A MORDIDA, dentro do teste: com o `0x31` avulso quebrado, a régua do rádio acusa."""
    monkeypatch.setattr(bp.PyDualSenseController, "_pintar_por_hidraw_bt",
                        lambda self, *a, **k: False)
    ctl, handles, nos = _mesa()
    quadros = _pintar_a_mesa(ctl, 1.3)
    with pytest.raises(AssertionError, match="nenhum 0x31"):
        _confere_a_mesa(handles, nos, quadros)


def test_sem_o_no_o_cabo_reprova(monkeypatch: pytest.MonkeyPatch) -> None:
    """E a do cabo: se o nó deixa de receber a cor, a régua acusa."""
    ctl, handles, nos = _mesa()
    for no in nos.values():
        no.set_rgb = lambda *a, **k: True  # type: ignore[method-assign]
    quadros = _pintar_a_mesa(ctl, 1.3)
    with pytest.raises(AssertionError, match="a cor do nó"):
        _confere_a_mesa(handles, nos, quadros)
