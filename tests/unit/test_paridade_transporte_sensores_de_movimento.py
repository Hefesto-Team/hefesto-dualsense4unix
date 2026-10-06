"""PARIDADE-TRANSPORTE — giroscópio, acelerômetro e touchpad, cabo E rádio."""
from __future__ import annotations

import csv
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from hefesto_dualsense4unix.core import evdev_reader
from hefesto_dualsense4unix.core.evdev_reader import (
    MotionSensorReader,
    discover_dualsense_motion_evdevs,
    discover_dualsense_touchpad_evdevs,
)
from tests.unit.sysfs_de_entrada_de_mentira import publicar_no

RAIZ = Path(__file__).resolve().parents[2]
MAPA = RAIZ / "docs" / "data" / "mapa-controles.csv"
IPC = RAIZ / "src" / "hefesto_dualsense4unix" / "daemon" / "ipc_handlers.py"

#: sensor do DualSense nascem nos DOIS — é o que a bancada de 03/09 mediu.
BUS_USB = 0x03
BUS_BLUETOOTH = 0x05

MAC_CABO = "aa:bb:cc:00:00:01"
MAC_RADIO = "aa:bb:cc:00:00:02"

NOME_MOTION_USB = (
    "Sony Interactive Entertainment DualSense Wireless Controller Motion Sensors"
)
NOME_MOTION_BT = "DualSense Wireless Controller Motion Sensors"
NOME_TOUCH_USB = (
    "Sony Interactive Entertainment DualSense Wireless Controller Touchpad"
)
NOME_TOUCH_BT = "DualSense Wireless Controller Touchpad"


def _no(nome: str, uniq: str, bus: int, path: str) -> str:
    """Publica o nó no sysfs de mentira, COM barramento, e devolve o caminho."""
    publicar_no(evdev_reader.SYS_CLASS_INPUT, path, nome=nome, uniq=uniq, bus=bus)
    return path


def _mesa_de_dois(marcador: str) -> list[str]:
    """A bancada: um controle no cabo e um no rádio, com o nó `marcador`."""
    if marcador == "Motion Sensors":
        usb, bt = NOME_MOTION_USB, NOME_MOTION_BT
    else:
        usb, bt = NOME_TOUCH_USB, NOME_TOUCH_BT
    return [
        _no(usb, MAC_CABO, BUS_USB, "/dev/input/event28"),
        _no(bt, MAC_RADIO, BUS_BLUETOOTH, "/dev/input/event256"),
    ]


def _sem_open(caminho: Any) -> Any:
    raise AssertionError(f"a descoberta abriu {caminho}: ela lê o sysfs e não abre o nó")


def _com_a_mesa(marcador: str) -> Any:
    """Os dois nós sintéticos, e o TERCEIRO dublê sem o qual esta régua mentia."""
    nos = _mesa_de_dois(marcador)
    return (
        patch("evdev.list_devices", return_value=nos),
        patch("evdev.InputDevice", side_effect=_sem_open),
        patch(
            "hefesto_dualsense4unix.core.evdev_reader._is_virtual_evdev",
            return_value=False,
        ),
    )


@pytest.mark.parametrize(
    ("marcador", "descobre"),
    [
        ("Motion Sensors", discover_dualsense_motion_evdevs),
        ("Touchpad", discover_dualsense_touchpad_evdevs),
    ],
)
def test_a_descoberta_do_no_acha_o_do_radio_igual_ao_do_cabo(
    marcador: str, descobre: Any
) -> None:
    """Os DOIS nós saem da descoberta — o do cabo e o do rádio."""
    lista, dispositivo, nao_virtual = _com_a_mesa(marcador)
    with lista, dispositivo, nao_virtual:
        achados = descobre()

    esperado = {"aabbcc000001": Path("/dev/input/event28"),
                "aabbcc000002": Path("/dev/input/event256")}
    assert achados == esperado, (
        f"a descoberta do nó «{marcador}» não devolveu os dois transportes: "
        f"{achados} — o nó do rádio existe e tem os mesmos eixos (medido em "
        "03/09/2026 na mesa dela, bus 0x05)"
    )


def test_o_nome_do_no_do_radio_vem_sem_o_prefixo_do_fabricante() -> None:
    """A descoberta casa por SUBSTRING, e é isso que salva o nó do rádio."""
    assert NOME_MOTION_BT != NOME_MOTION_USB
    assert NOME_MOTION_BT in NOME_MOTION_USB

    nos = [_no(NOME_MOTION_BT, MAC_RADIO, BUS_BLUETOOTH, "/dev/input/event256")]
    with patch("evdev.list_devices", return_value=nos), patch(
        "evdev.InputDevice", side_effect=_sem_open
    ), patch(
        "hefesto_dualsense4unix.core.evdev_reader._is_virtual_evdev",
        return_value=False,
    ):
        achados = discover_dualsense_motion_evdevs()

    assert achados == {"aabbcc000002": Path("/dev/input/event256")}, (
        "o nó de movimento do rádio, com o nome que o BlueZ dá, não foi achado"
    )


def test_o_leitor_de_movimento_resolve_o_alvo_do_radio() -> None:
    """`MotionSensorReader(target_uniq=<mac do rádio>)` acha o nó do rádio."""
    nos = _mesa_de_dois("Motion Sensors")
    leitor = MotionSensorReader(target_uniq="aabbcc000002")
    with patch("evdev.list_devices", return_value=nos), patch(
        "evdev.InputDevice", side_effect=_sem_open
    ), patch(
        "hefesto_dualsense4unix.core.evdev_reader._is_virtual_evdev",
        return_value=False,
    ):
        alvo = leitor._locate()

    assert alvo == Path("/dev/input/event256"), (
        f"o leitor de movimento não achou o nó do controle de rádio: {alvo}"
    )


def _linhas_do_mapa() -> dict[tuple[str, str], dict[str, str]]:
    csv.field_size_limit(10_000_000)
    with open(MAPA, encoding="utf-8", newline="") as fh:
        return {(r["chave"], r["controle"]): r for r in csv.DictReader(fh)}


LINHAS_COM_CAMINHO_DE_RADIO = [
    ("movimento.giroscopio", "dualsense"),
    ("movimento.acelerometro", "dualsense"),
    ("toque.touchpad", "dualsense"),
    ("toque.touchpad.cursor", "dualsense"),
    ("movimento.giroscopio", "sn30"),
    ("movimento.acelerometro", "sn30"),
]


@pytest.mark.parametrize(("chave", "controle"), LINHAS_COM_CAMINHO_DE_RADIO)
def test_o_mapa_guarda_o_caminho_do_radio_desta_area(chave: str, controle: str) -> None:
    """Canal, offset, comando e endereço de código do RÁDIO, preenchidos."""
    linha = _linhas_do_mapa().get((chave, controle))
    assert linha is not None, f"linha {chave}@{controle} sumiu do mapa"
    for coluna in ("radio_canal", "radio_offset", "radio_comando", "radio_codigo_ref"):
        assert linha[coluna].strip(), (
            f"{chave}@{controle}: `{coluna}` está muda — o caminho do rádio desta "
            "linha foi escrito em 03/09/2026 e não pode voltar a sumir"
        )


def test_o_mapa_conta_o_portao_do_segundo_controle_e_o_codigo_ainda_bate() -> None:
    """O PORTÃO FOI CURADO em 04/09/2026, e esta régua virou junto.

    Ela nasceu em 03/09 guardando o achado — *"o `daemon.state_full` publica
    `inputs: null` para todo controle que não é o primário"* — e cobrando que
    o mapa e o código dissessem a mesma coisa. A terceira asserção dela era
    `'entry["inputs"] = None' in fonte`, e a mensagem já dizia o que fazer no
    dia em que ela reprovasse: *"Se o portão foi curado, ótimo — e então o mapa
    mente: reescreva a `radio_ressalva`"*. Foi o que aconteceu (STATUS-04), e
    é o que este commit faz.

    **A régua não foi apagada, foi virada** — continua mordendo por dois
    lados, agora sobre a CURA em vez do defeito:

    - se alguém apagar a evidência do mapa, a primeira metade reprova;
    - se alguém REGREDIR o `_inputs_passivos` (ou a exigência de dicionário do
      `_merge_sensores`, que continua sendo o portão a vigiar), a segunda
      metade reprova — e o segundo card volta a ficar mudo em silêncio, que é
      exatamente como o defeito atravessou de 17/07 a 03/09.
    """
    linha = _linhas_do_mapa()[("movimento.giroscopio", "dualsense")]
    ressalva = linha["radio_ressalva"]
    assert "_merge_sensores" in ressalva and "ipc_handlers.py" in ressalva, (
        "a `radio_ressalva` de `movimento.giroscopio@dualsense` perdeu o endereço "
        "do portão que deixava o SEGUNDO controle sem sensores — medido em "
        "03/09/2026, curado em 04/09/2026"
    )
    assert "_inputs_passivos" in ressalva, (
        "a `radio_ressalva` de `movimento.giroscopio@dualsense` não conta mais "
        "COMO o portão foi curado. Se a cura foi revertida, o mapa tem de voltar "
        "a descrever o defeito — e as três que apontam para ela também "
        "(`movimento.acelerometro@dualsense`, `toque.touchpad@dualsense`, "
        "`toque.touchpad.cursor@dualsense`)"
    )

    fonte = IPC.read_text(encoding="utf-8")
    assert "def _merge_sensores" in fonte, (
        "`_merge_sensores` sumiu de daemon/ipc_handlers.py — a `radio_ressalva` "
        "de `movimento.giroscopio@dualsense` tem de ser reescrita NO MESMO COMMIT"
    )
    assert "def _inputs_passivos" in fonte, (
        "`_inputs_passivos` sumiu de daemon/ipc_handlers.py: a TERCEIRA fonte de "
        "`inputs` era o que dava sensores ao segundo controle fora do co-op. Sem "
        "ela o card volta a mostrar '—' em silêncio — reescreva a "
        "`radio_ressalva` de `movimento.giroscopio@dualsense` e as três que "
        "apontam para ela"
    )
    assert "not isinstance(inputs, dict)" in fonte, (
        "a desistência de `_merge_sensores` mudou de forma; confira se o segundo "
        "controle continua recebendo sensores e atualize o mapa junto"
    )
