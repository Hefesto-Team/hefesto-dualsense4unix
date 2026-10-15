"""O teclado e o mouse Bluetooth se reconhecem pela aparência.

A categoria `0x0F` (HID) da `Appearance` diz o tipo pela subcategoria: `0x03C1` é teclado,
`0x03C2` é mouse, `0x03C3` e `0x03C4` são controle, o resto (`0x03C0`) fica «outro».

MORDIDAS: tirar o ramo da categoria `0x0F` reprova os testes do teclado, do mouse e da linha
desligada; tirar `0x03C2` da tabela reprova o do mouse; devolver o relógio ou o celular a «outro»
reprova os dois casos de antes.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from hefesto_dualsense4unix.interface.pacotes import a08_conexoes as a08

ENDERECO = "AA:BB:CC:DD:EE:01"
ADAPTADOR = "/org/bluez/hci0"
LUGAR = "AA:BB:CC:DD:EE:F0"


@pytest.mark.parametrize(("aparencia", "tipo"), [
    (0x03C1, "teclado"),
    (0x03C2, "mouse"),
    (0x03C3, "controle"),
    (0x03C4, "controle"),
    (0x03C0, "outro"),
    (0x03C5, "outro"),
    (0x03FF, "outro"),
])
def test_a_categoria_hid_se_le_pela_subcategoria(aparencia: int, tipo: str) -> None:
    assert a08._tipo_pela_aparencia(aparencia) == tipo
    assert a08._tipo_do_aparelho("", None, aparencia) == tipo


def test_os_dois_casos_de_antes_continuam() -> None:
    assert a08._tipo_pela_aparencia(0x00C0) == "relogio"
    assert a08._tipo_pela_aparencia(0x0040) == "celular"
    assert a08._tipo_pela_aparencia(0x0300) == "outro"


@pytest.mark.parametrize("aparencia", [None, True, "0x03C1"])
def test_sem_aparencia_valida_fica_outro(aparencia: Any) -> None:
    assert a08._tipo_pela_aparencia(aparencia) == "outro"


def test_o_icone_e_a_classe_seguem_antes_da_aparencia() -> None:
    assert a08._tipo_do_aparelho("input-mouse", None, 0x03C1) == "mouse"
    assert a08._tipo_do_aparelho("", 0x000540, 0x03C2) == "teclado"


@pytest.mark.parametrize(("aparencia", "tipo", "rotulo"), [
    (0x03C1, "teclado", "Teclado"),
    (0x03C2, "mouse", "Mouse"),
])
def test_o_aparelho_desligado_sem_icone_nem_classe_sai_com_o_tipo_da_aparencia(
        aparencia: int, tipo: str, rotulo: str) -> None:
    """A linha do aparelho pareado e fora do ar, sem nome: o tipo e o rótulo vêm da aparência."""
    aparelho = SimpleNamespace(
        adaptador=ADAPTADOR, endereco=ENDERECO, pareado=True, conectado=False, nome="",
        classe=None, icone="", aparencia=aparencia, modalias="")
    linhas = a08._os_desligados((aparelho,), {ADAPTADOR: LUGAR}, [])
    assert len(linhas) == 1
    assert linhas[0]["tipo"] == tipo
    assert linhas[0]["rotulo"] == rotulo
