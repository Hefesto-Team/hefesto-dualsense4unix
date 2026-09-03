"""PARIDADE-TRANSPORTE — giroscópio, acelerômetro e touchpad, cabo E rádio.

O QUE ESTE ARQUIVO TRAVA, e por que ele nasceu em 03/09/2026
------------------------------------------------------------
Ela pediu para achar *"o que no código tá setado pra funcionar só via cabo e
não BT"*. Na área de movimento e toque a resposta foi medida na mesa dela, com
os dois controles ao mesmo tempo (um no cabo, um no rádio), e são DUAS metades
que este arquivo separa de propósito:

1. **A LEITURA NÃO TEM RAMO DE TRANSPORTE, e isso é para ficar assim.** O nó
   ``… Motion Sensors`` e o nó ``… Touchpad`` nascem nos dois barramentos, com
   nomes diferentes (o BlueZ não põe o prefixo do fabricante) e com os mesmos
   eixos. Quem descobre é ``_discover_dualsense_por_nome``, que casa por
   vendor + PID + SUBSTRING do nome e **nunca** consulta ``bustype``. Medido em
   03/09: o ``MotionSensorReader`` abriu o nó de bluetooth do segundo controle e
   devolveu 0,9966 g de módulo de gravidade e o bias de repouso do giroscópio.
   Os três primeiros testes reprovam no dia em que alguém puser um porteiro de
   barramento nessa descoberta;

2. **O QUE RECUSA É OUTRO PORTÃO, E ELE NÃO É DE TRANSPORTE — É DE CONTROLE.**
   ``daemon/ipc_handlers.py`` publica ``entry["inputs"] = None`` para todo
   controle que não seja o primário nem tenha instantâneo de co-op, e
   ``_merge_sensores`` desiste na hora quando ``inputs`` não é dicionário. O
   segundo controle da mesa fica sem giro, sem acelerômetro e sem toque **nos
   dois transportes** — mas como o segundo controle da mesa dela é o do rádio,
   isso se apresenta como "cabo sim, rádio não". A cura mora em arquivo de
   outra frente; o que este arquivo faz é impedir que o achado se perca: o mapa
   tem de continuar contando a história, e o código tem de continuar batendo com
   o que o mapa conta.

MORDIDA PROVADA (03/09/2026) — ver a docstring de cada caso.
"""
from __future__ import annotations

import csv
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from hefesto_dualsense4unix.core.evdev_reader import (
    DUALSENSE_PIDS,
    DUALSENSE_VENDOR,
    MotionSensorReader,
    discover_dualsense_motion_evdevs,
    discover_dualsense_touchpad_evdevs,
)

RAIZ = Path(__file__).resolve().parents[2]
MAPA = RAIZ / "docs" / "data" / "mapa-controles.csv"
IPC = RAIZ / "src" / "hefesto_dualsense4unix" / "daemon" / "ipc_handlers.py"

#: Barramentos como o kernel os numera (`linux/input.h`). Os dois nós de
#: sensor do DualSense nascem nos DOIS — é o que a bancada de 03/09 mediu.
BUS_USB = 0x03
BUS_BLUETOOTH = 0x05

#: MACs de mentira na convenção da casa (`aa:bb:cc:00:00:NN`). O que importa
#: aqui é serem DOIS, um por barramento.
MAC_CABO = "aa:bb:cc:00:00:01"
MAC_RADIO = "aa:bb:cc:00:00:02"

#: Os nomes REAIS dos nós, como esta bancada os leu em 03/09/2026: por USB o
#: kernel põe o prefixo do fabricante, por Bluetooth o BlueZ não põe. É por
#: isso que a descoberta casa por SUBSTRING — um match exato pelo nome de USB
#: nunca acharia o nó do rádio (foi o defeito TOUCHPAD-76-BT-VPAD-01).
NOME_MOTION_USB = (
    "Sony Interactive Entertainment DualSense Wireless Controller Motion Sensors"
)
NOME_MOTION_BT = "DualSense Wireless Controller Motion Sensors"
NOME_TOUCH_USB = (
    "Sony Interactive Entertainment DualSense Wireless Controller Touchpad"
)
NOME_TOUCH_BT = "DualSense Wireless Controller Touchpad"


def _no(nome: str, uniq: str, bus: int, path: str) -> SimpleNamespace:
    """Um objeto que quackeia como `evdev.InputDevice`, COM barramento.

    O `bustype` vai junto de propósito: sem ele, um porteiro de barramento
    introduzido no produto explodiria com `AttributeError` em vez de reprovar,
    e a régua estaria medindo o dublê, não a cura.
    """
    dev = SimpleNamespace()
    dev.name = nome
    dev.uniq = uniq
    dev.info = SimpleNamespace(
        vendor=DUALSENSE_VENDOR, product=next(iter(DUALSENSE_PIDS)), bustype=bus
    )
    dev.path = path
    dev.close = MagicMock()
    return dev


def _mesa_de_dois(marcador: str) -> dict[str, SimpleNamespace]:
    """A mesa dela: um controle no cabo e um no rádio, com o nó `marcador`."""
    if marcador == "Motion Sensors":
        usb, bt = NOME_MOTION_USB, NOME_MOTION_BT
    else:
        usb, bt = NOME_TOUCH_USB, NOME_TOUCH_BT
    return {
        "/dev/input/event28": _no(usb, MAC_CABO, BUS_USB, "/dev/input/event28"),
        "/dev/input/event256": _no(bt, MAC_RADIO, BUS_BLUETOOTH, "/dev/input/event256"),
    }


def _com_a_mesa(marcador: str) -> Any:
    nos = _mesa_de_dois(marcador)
    return patch("evdev.list_devices", return_value=list(nos)), patch(
        "evdev.InputDevice", side_effect=lambda p: nos[p]
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
    """Os DOIS nós saem da descoberta — o do cabo e o do rádio.

    MORDIDA PROVADA em 03/09/2026, com `src/` copiado para fora da árvore e o
    `PYTHONPATH` apontado para a cópia (a árvore de trabalho nunca foi mutada):
    acrescentado `and dev.info.bustype == 0x03` ao casamento de
    `_discover_dualsense_por_nome`, reprovam os quatro casos deste arquivo que
    dependem do nó de rádio.
    """
    lista, dispositivo = _com_a_mesa(marcador)
    with lista, dispositivo:
        achados = descobre()

    esperado = {"aabbcc000001": Path("/dev/input/event28"),
                "aabbcc000002": Path("/dev/input/event256")}
    assert achados == esperado, (
        f"a descoberta do nó «{marcador}» não devolveu os dois transportes: "
        f"{achados} — o nó do rádio existe e tem os mesmos eixos (medido em "
        "03/09/2026 na mesa dela, bus 0x05)"
    )


def test_o_nome_do_no_do_radio_vem_sem_o_prefixo_do_fabricante() -> None:
    """A descoberta casa por SUBSTRING, e é isso que salva o nó do rádio.

    Não é detalhe de implementação: por Bluetooth o BlueZ nomeia o nó sem
    "Sony Interactive Entertainment", e um match EXATO pelo nome de USB é
    exatamente o defeito que a `assets/76-dualsense-touchpad-libinput-ignore.rules`
    pagou em 21/07/2026. Se alguém trocar a substring por igualdade, este caso
    reprova antes de a mesa dela reprovar.
    """
    assert NOME_MOTION_BT != NOME_MOTION_USB
    assert NOME_MOTION_BT in NOME_MOTION_USB

    nos = {"/dev/input/event256": _no(
        NOME_MOTION_BT, MAC_RADIO, BUS_BLUETOOTH, "/dev/input/event256"
    )}
    with patch("evdev.list_devices", return_value=list(nos)), patch(
        "evdev.InputDevice", side_effect=lambda p: nos[p]
    ):
        achados = discover_dualsense_motion_evdevs()

    assert achados == {"aabbcc000002": Path("/dev/input/event256")}, (
        "o nó de movimento do rádio, com o nome que o BlueZ dá, não foi achado"
    )


def test_o_leitor_de_movimento_resolve_o_alvo_do_radio() -> None:
    """`MotionSensorReader(target_uniq=<mac do rádio>)` acha o nó do rádio.

    É a rota do PRODUTO, não um instrumento à parte: foi esta classe que, em
    03/09/2026, leu 0,9966 g de gravidade e o bias de repouso do giroscópio no
    controle de Bluetooth da mesa dela.
    """
    nos = _mesa_de_dois("Motion Sensors")
    leitor = MotionSensorReader(target_uniq="aabbcc000002")
    with patch("evdev.list_devices", return_value=list(nos)), patch(
        "evdev.InputDevice", side_effect=lambda p: nos[p]
    ):
        alvo = leitor._locate()

    assert alvo == Path("/dev/input/event256"), (
        f"o leitor de movimento não achou o nó do controle de rádio: {alvo}"
    )


# ---------------------------------------------------------------------------
# A evidência no mapa, e o código que ela cita
# ---------------------------------------------------------------------------
def _linhas_do_mapa() -> dict[tuple[str, str], dict[str, str]]:
    csv.field_size_limit(10_000_000)
    with open(MAPA, encoding="utf-8", newline="") as fh:
        return {(r["chave"], r["controle"]): r for r in csv.DictReader(fh)}


#: As linhas desta área que têm de carregar o caminho do RÁDIO por escrito. É o
#: mecanismo que ela descreveu: *"quando colocarmos o caminho certo no specs o
#: script original vai fazer uso desse place holder"*.
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
    """Canal, offset, comando e endereço de código do RÁDIO, preenchidos.

    MORDIDA: apagar qualquer uma das quatro células reprova o caso — e é isso
    que impede o `specs.html` de voltar a publicar uma linha muda no lado do
    rádio depois de alguém ter escrito o caminho.
    """
    linha = _linhas_do_mapa().get((chave, controle))
    assert linha is not None, f"linha {chave}@{controle} sumiu do mapa"
    for coluna in ("radio_canal", "radio_offset", "radio_comando", "radio_codigo_ref"):
        assert linha[coluna].strip(), (
            f"{chave}@{controle}: `{coluna}` está muda — o caminho do rádio desta "
            "linha foi escrito em 03/09/2026 e não pode voltar a sumir"
        )


def test_o_mapa_conta_o_portao_do_segundo_controle_e_o_codigo_ainda_bate() -> None:
    """O achado de 03/09 tem de continuar escrito NO MAPA e VERDADEIRO NO CÓDIGO.

    Duas leituras, e as duas mordem por lados opostos:

    - se alguém apagar a evidência do mapa, a primeira metade reprova;
    - se alguém CURAR o portão em `daemon/ipc_handlers.py` sem atualizar o mapa,
      a segunda metade reprova — e a mensagem diz o que fazer. É de propósito:
      nesta casa, curar o defeito e deixar o mapa afirmando que ele existe é o
      mesmo tipo de podridão que a citação de linha que não abre.
    """
    linha = _linhas_do_mapa()[("movimento.giroscopio", "dualsense")]
    ressalva = linha["radio_ressalva"]
    assert "_merge_sensores" in ressalva and "ipc_handlers.py" in ressalva, (
        "a `radio_ressalva` de `movimento.giroscopio@dualsense` perdeu o endereço "
        "do portão que deixa o SEGUNDO controle sem sensores — medido em 03/09/2026"
    )

    fonte = IPC.read_text(encoding="utf-8")
    assert "def _merge_sensores" in fonte, (
        "`_merge_sensores` sumiu de daemon/ipc_handlers.py — se o portão foi "
        "curado, a `radio_ressalva` de `movimento.giroscopio@dualsense` tem de ser "
        "reescrita NO MESMO COMMIT"
    )
    assert 'entry["inputs"] = None' in fonte, (
        "o `entry[\"inputs\"] = None` do controle não-primário sumiu de "
        "daemon/ipc_handlers.py. Se o portão foi curado, ótimo — e então o mapa "
        "mente: reescreva a `radio_ressalva` de `movimento.giroscopio@dualsense` e "
        "as duas que apontam para ela (`movimento.acelerometro@dualsense`, "
        "`toque.touchpad@dualsense`, `toque.touchpad.cursor@dualsense`)"
    )
    assert "not isinstance(inputs, dict)" in fonte, (
        "a desistência de `_merge_sensores` mudou de forma; confira se o segundo "
        "controle passou a receber sensores e atualize o mapa junto"
    )
