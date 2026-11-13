"""O cursor anda pelo analógico direito: cada analógico faz o que a linha dele diz.

Sprint O-CURSOR-ANDA-PELO-ANALOGICO-DIREITO-01.

Medido antes de curar (13/11/2026), com o `resolver` e o `set_button_actions` reais: o
«Mover com: Analógico direito» (`r3_direcao=__CURSOR__`, `l3_direcao=__ROLAGEM__`) dava
`sem_dono ['l3_direcao', 'r3_direcao']` e nenhum dos dois analógicos fazia nada; o perfil de
teclado e mouse (`l3_direcao=__WASD__`, `r3_direcao=__CURSOR__`) deixava a câmera sem analógico.

MORDIDAS (arrancadas e devolvidas): devolver o `dispatch` ao par fixo (cursor só em `lx/ly`,
rolagem só em `rx/ry`) reprova as de movimento; devolver o `__CURSOR__` só ao esquerdo em
`LINHAS_DA_ACAO_DE_EIXO` reprova as do `resolver`; fazer o `_eixos_que_fazem` ignorar a soma
(só o primeiro eixo) reprova a dos dois no cursor.
"""
from __future__ import annotations

from typing import Any

import pytest

from hefesto_dualsense4unix.core import acoes_de_botao as acoes
from tests.unit.test_uinput_mouse import _started_device

ESQ, DIR = acoes.EIXO_ESQUERDO, acoes.EIXO_DIREITO
CENTRO = 128
EMPURRADO = 228
PUXADO = 28
SEM_BOTOES: frozenset[str] = frozenset()

MOVER_COM_O_DIREITO = {DIR: acoes.TOKEN_CURSOR, ESQ: acoes.TOKEN_ROLAGEM}
TECLADO_E_MOUSE = {ESQ: acoes.TOKEN_WASD, DIR: acoes.TOKEN_CURSOR}


def _aplicado(monkeypatch: pytest.MonkeyPatch, escolhas: dict[str, str] | None) -> tuple[
    Any, Any, Any,
]:
    dev, mod, device = _started_device(monkeypatch)
    if escolhas is not None:
        do_mouse, _teclado, _sem_dono = acoes.resolver(escolhas)
        dev.set_button_actions(do_mouse, acoes.botoes_calados(escolhas))
    return dev, mod, device


def _gira(dev: Any, *, lx: int = CENTRO, ly: int = CENTRO, rx: int = CENTRO, ry: int = CENTRO,
          ticks: int = 1) -> None:
    for i in range(ticks):
        dev.dispatch(lx=lx, ly=ly, rx=rx, ry=ry, l2=0, r2=0, buttons=SEM_BOTOES, now=float(i))


def _soma(device: Any, codigo: Any) -> int:
    return sum(c[1][1] for c in device.method_calls if c[0] == "emit" and c[1][0] == codigo)


def _moveu(mod: Any, device: Any) -> bool:
    return bool(_soma(device, mod.REL_X) or _soma(device, mod.REL_Y))


def _rolou(mod: Any, device: Any) -> bool:
    return bool(_soma(device, mod.REL_WHEEL) or _soma(device, mod.REL_HWHEEL))


@pytest.mark.parametrize("escolhas", [MOVER_COM_O_DIREITO, TECLADO_E_MOUSE])
def test_a_escolha_do_cursor_no_direito_tem_dono(escolhas: dict[str, str]) -> None:
    _mouse, _teclado, sem_dono = acoes.resolver(escolhas)
    assert sem_dono == [], f"sem dono: {sem_dono}"


@pytest.mark.parametrize("token", [acoes.TOKEN_CURSOR, acoes.TOKEN_ROLAGEM])
@pytest.mark.parametrize("linha", [ESQ, DIR])
def test_cursor_e_rolagem_tem_dono_nas_duas_linhas(linha: str, token: str) -> None:
    assert linha not in acoes.resolver({linha: token})[2]


def test_o_perfil_de_teclado_e_mouse_o_direito_move_o_cursor(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dev, mod, device = _aplicado(monkeypatch, TECLADO_E_MOUSE)
    _gira(dev, rx=EMPURRADO, ry=EMPURRADO)
    assert _soma(device, mod.REL_X) > 0 and _soma(device, mod.REL_Y) > 0
    assert not _rolou(mod, device), "o direito em cursor rolou"


def test_o_perfil_de_teclado_e_mouse_o_esquerdo_nao_toca_o_mouse(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dev, mod, device = _aplicado(monkeypatch, TECLADO_E_MOUSE)
    _gira(dev, lx=EMPURRADO, ly=EMPURRADO, ticks=5)
    assert not _moveu(mod, device), "o esquerdo em WASD moveu o cursor"
    assert not _rolou(mod, device), "o esquerdo em WASD rolou"


def test_mover_com_o_direito_o_direito_move_e_o_esquerdo_rola(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dev, mod, device = _aplicado(monkeypatch, MOVER_COM_O_DIREITO)
    _gira(dev, rx=EMPURRADO, ry=PUXADO)
    assert _soma(device, mod.REL_X) > 0 and _soma(device, mod.REL_Y) < 0
    assert not _rolou(mod, device), "o direito em cursor rolou"

    dev2, mod2, device2 = _aplicado(monkeypatch, MOVER_COM_O_DIREITO)
    _gira(dev2, lx=EMPURRADO, ly=PUXADO)
    assert _soma(device2, mod2.REL_WHEEL) > 0, "o esquerdo em rolagem não rolou para cima"
    assert _soma(device2, mod2.REL_HWHEEL) > 0
    assert not _moveu(mod2, device2), "o esquerdo em rolagem moveu o cursor"


@pytest.mark.parametrize("escolhas", [None, {}])
def test_o_de_fabrica_segue_esquerdo_cursor_direito_rolagem(
    monkeypatch: pytest.MonkeyPatch, escolhas: dict[str, str] | None,
) -> None:
    dev, mod, device = _aplicado(monkeypatch, escolhas)
    _gira(dev, lx=EMPURRADO, ly=EMPURRADO)
    assert _moveu(mod, device) and not _rolou(mod, device)

    dev2, mod2, device2 = _aplicado(monkeypatch, escolhas)
    _gira(dev2, rx=EMPURRADO, ry=EMPURRADO)
    assert _rolou(mod2, device2) and not _moveu(mod2, device2)


def test_os_dois_analogicos_no_cursor_somam(monkeypatch: pytest.MonkeyPatch) -> None:
    escolhas = {ESQ: acoes.TOKEN_CURSOR, DIR: acoes.TOKEN_CURSOR}
    dev, mod, device = _aplicado(monkeypatch, escolhas)
    _gira(dev, lx=255, rx=255, ticks=10)
    dev1, mod1, device1 = _aplicado(monkeypatch, escolhas)
    _gira(dev1, lx=255, ticks=10)
    sozinho = _soma(device1, mod1.REL_X)
    assert sozinho > 0
    assert abs(_soma(device, mod.REL_X) - 2 * sozinho) <= 1


def test_os_dois_analogicos_em_sentidos_opostos_se_anulam(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dev, mod, device = _aplicado(
        monkeypatch, {ESQ: acoes.TOKEN_CURSOR, DIR: acoes.TOKEN_CURSOR})
    _gira(dev, lx=EMPURRADO, rx=PUXADO, ticks=5)
    assert _soma(device, mod.REL_X) == 0


@pytest.mark.parametrize("escolhas", [
    {ESQ: acoes.TOKEN_ROLAGEM, DIR: acoes.TOKEN_ROLAGEM},
    {ESQ: acoes.TOKEN_WASD, DIR: acoes.TOKEN_SETAS},
    {ESQ: acoes.TOKEN_NADA, DIR: acoes.TOKEN_NADA},
])
def test_nenhum_analogico_no_cursor_o_cursor_fica_calado(
    monkeypatch: pytest.MonkeyPatch, escolhas: dict[str, str],
) -> None:
    dev, mod, device = _aplicado(monkeypatch, escolhas)
    _gira(dev, lx=255, ly=255, rx=255, ry=255, ticks=5)
    assert not _moveu(mod, device)


def test_calar_o_direito_com_o_cursor_no_esquerdo_nao_cala_o_esquerdo(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dev, mod, device = _aplicado(monkeypatch, {DIR: acoes.TOKEN_NADA})
    _gira(dev, lx=EMPURRADO, ly=EMPURRADO)
    assert _moveu(mod, device)


def test_trocar_a_escolha_nao_deixa_o_eixo_antigo_vivo(monkeypatch: pytest.MonkeyPatch) -> None:
    dev, mod, device = _aplicado(monkeypatch, MOVER_COM_O_DIREITO)
    do_mouse, _t, _s = acoes.resolver(None)
    dev.set_button_actions(do_mouse, acoes.botoes_calados(None))
    _gira(dev, rx=EMPURRADO, ry=EMPURRADO)
    assert not _moveu(mod, device) and _rolou(mod, device)
