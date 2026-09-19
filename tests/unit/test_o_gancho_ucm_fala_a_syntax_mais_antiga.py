"""O gancho UCM do DualSense declara a Syntax mais antiga que o lê — 18/09/2026.

O ``Syntax`` da primeira linha é o piso de versão que a alsa-lib exige para ler
o arquivo: uma alsa-lib mais velha que o número recusa o gancho INTEIRO, e o
DualSense no cabo volta a nascer sem ``Speaker__sink`` — sem o endpoint que o
jogo procura para a vibração. Medido com o controle no cabo: o ``alsaucm``
devolve o mesmo verbo ``HiFi`` e os mesmos dispositivos ``Speaker`` e ``Mic``
com ``Syntax 6`` e com ``Syntax 4``. O gancho só usa ``SectionUseCase`` e
``File``; nada nele pede mais que 4.
"""

from __future__ import annotations

from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
GANCHO = RAIZ / "assets" / "ucm" / "DualSense-gancho.conf"
PISO = 4


def test_o_gancho_nao_pede_alsa_lib_mais_nova_que_a_necessaria() -> None:
    """MORDIDA: volte a primeira linha do gancho para ``Syntax 6``."""
    primeira = GANCHO.read_text(encoding="utf-8").splitlines()[0].split()
    assert primeira[0] == "Syntax", "a primeira linha de um arquivo UCM é o Syntax"
    assert int(primeira[1]) <= PISO, (
        f"o gancho declara Syntax {primeira[1]}: alsa-lib anterior a ele recusa o "
        "arquivo inteiro. Suba só com uma construção que exija, e escreva qual.")
