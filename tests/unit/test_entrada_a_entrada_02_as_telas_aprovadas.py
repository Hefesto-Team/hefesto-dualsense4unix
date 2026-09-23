"""O motor serve as três telas que ela já aprovou — ENTRADA-A-ENTRADA-02 (23/09/2026).

A conferência da ENTRADA-A-ENTRADA-01 achou o maior problema dela: as três telas
da âncora ``#mapear-entrada-a-entrada`` (a página publicada, ``08-conexoes.html``)
descrevem o fluxo da ``LogicaDaCalibracao`` — uma fase SENTADA sobre os
aparelhos já plugados e uma fase EM PÉ sobre as entradas vazias —, e o motor
perguntava a face a cada plug. Decisão de quem coordena: o motor serve as
telas APROVADAS; as telas não mudam.

UMA RÉGUA POR ITEM DA SPRINT, e cada uma morde (a mordida está no docstring):

1. as duas fases e o contador — cada campo e cada botão das três telas, LIDOS
   da página publicada, chegam ao motor;
2. só o DualSense marca uma porta;
3. a amarra pelo ``ID_PATH`` inteiro, não pelo ``devpath``;
4. as quatro faces são as do produto;
5. ``bluez_dbus.lugar_de`` só com a biblioteca padrão também na CHAMADA;
6. um escritor do ``Alias``: o motor não escreve no BlueZ.

O ``/sys`` de mentira é uma árvore de verdade no ``tmp_path``, com os NÓS de
entrada (``usbN-portM``, ``state``, ``peer``, ``device``), lida pelos leitores
de verdade (``censo_do_barramento.ler_o_barramento`` e
``entradas_do_gabinete.listar_entradas``): um dublê que devolvesse o censo
pronto seria mais frouxo que o leitor real.

Faixa sintética da casa: controladores ``0000:0a:00.0`` e ``0000:0b:00.0``.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
SRC = RAIZ / "src" / "hefesto_dualsense4unix"

PCI_A = "0000:0a:00.0"
PCI_B = "0000:0b:00.0"


# ---------------------------------------------------------------------------
# 5. a grafia do lugar vive sem pydantic — também na CHAMADA
# ---------------------------------------------------------------------------


def test_a_grafia_do_lugar_responde_sem_pydantic_na_chamada() -> None:
    """Pelo ``python3`` do sistema (o recurso do doctor, pydantic 1.10) a
    CHAMADA de ``bluez_dbus.lugar_de`` levantava ``ImportError``
    (``field_validator``): o import tardio só adiava o erro, e todo adaptador
    ficava sem lugar, calado. Aqui o pydantic some do processo inteiro, e as
    duas chamadas do caminho do doctor têm de responder o lugar.

    MORDIDA: devolva ao ``bluez_dbus.lugar_de`` (ou ao
    ``mesa_de_radio._lugar``) o ``from …utils.maquina import lugar_de`` — o
    ``ImportError`` volta, e a régua reprova nomeando a chamada.
    """
    codigo = (
        "import sys\n"
        "sys.modules['pydantic'] = None\n"
        "from hefesto_dualsense4unix.integrations import bluez_dbus, mesa_de_radio\n"
        f"print(bluez_dbus.lugar_de({PCI_B!r}, '4.1.4'))\n"
        f"a = mesa_de_radio.Adaptador('hci9', no='x', busnum=3, devpath='1',"
        f" controlador_pci={PCI_A!r})\n"
        "print(a.lugar)\n"
        "print('pydantic' in sys.modules and sys.modules['pydantic'] is not None)\n"
    )
    ambiente = dict(os.environ)
    ambiente["PYTHONPATH"] = str(RAIZ / "src")
    feito = subprocess.run(
        [sys.executable, "-c", codigo],
        capture_output=True,
        text=True,
        env=ambiente,
        timeout=60,
        check=False,
    )
    assert feito.returncode == 0, feito.stderr[-1200:]
    assert feito.stdout.split() == [
        f"pci-{PCI_B}-usb-0:4.1.4",
        f"pci-{PCI_A}-usb-0:1",
        "False",
    ], feito.stdout
