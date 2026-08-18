"""O desinstalador não apaga os snapshots de pareamento sem ela pedir.

CICLO-QUE-PROVA-01 (08/08/2026). MEDIDO no ciclo real, na máquina dela:

    antes do ciclo:  12 snapshots em /var/lib/hefesto-dualsense4unix/bt-bonds/
    depois:           1

O `uninstall.sh` fazia `rm -rf` **por default, sem flag e sem confirmação**, e o
`install.sh` recria só o diretório vazio. Os snapshots são a única rede entre um
crash do `bluetoothd` e ela repareando quatro controles à mão — e o crash das
00:27:35 da mesma noite mostrou exatamente para que servem: o salva-vidas gravou
os quatro bonds dois segundos depois, sozinho.

A doutrina da casa para dado dela já estava escrita e era outra: **preserva por
default, apaga só com `--purge-config`**. É o que vale para a config e para os
perfis. Os bonds passam a seguir a mesma regra.
"""

from __future__ import annotations

import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
UNINSTALL = RAIZ / "uninstall.sh"


def _bloco_dos_bonds() -> str:
    """O trecho que decide o destino dos snapshots."""
    texto = UNINSTALL.read_text(encoding="utf-8")
    inicio = texto.index('if [[ -d /var/lib/hefesto-dualsense4unix/bt-bonds ]]; then')
    return texto[inicio : inicio + 2600]


def test_o_default_preserva_os_snapshots() -> None:
    """Sem `--purge-config`, os snapshots são MOVIDOS, não apagados.

    ARRANQUE A CURA (volte o `rm -rf` incondicional) e este teste REPROVA. Ela
    perde o histórico de pareamentos num comando de manutenção, em silêncio.
    """
    bloco = _bloco_dos_bonds()
    assert "KEEP_CONFIG" in bloco, (
        "o destino dos snapshots de bond não consulta mais o `KEEP_CONFIG` — "
        "voltou a apagar por default. Ver "
        "docs/process/sprints/2026-08-08-CICLO-QUE-PROVA-01-*.md"
    )
    assert re.search(r"sudo mv\s+\"/var/lib/hefesto-dualsense4unix/bt-bonds\"", bloco), (
        "sumiu o `mv` que preserva os snapshots. Sem ele, o caminho de default "
        "volta a ser destrutivo."
    )
    assert "bt-bonds.pre-uninstall-" in bloco, (
        "sumiu o carimbo do destino preservado — sem ele a sobra não se anuncia "
        "como sobra de desinstalação."
    )


def test_a_purga_explicita_continua_possivel() -> None:
    """Com `--purge-config`, o wipe acontece — o contrapeso desta cura.

    Preservar sempre seria trocar um defeito por outro: um desinstalador que
    deixa LinkKey na máquina para sempre, sem caminho de limpeza. A flag existe
    e tem de continuar funcionando.
    """
    bloco = _bloco_dos_bonds()
    assert "sudo rm -rf /var/lib/hefesto-dualsense4unix/bt-bonds" in bloco, (
        "sumiu o caminho de wipe. Com `--purge-config` a pessoa PEDIU o apagar, e "
        "o desinstalador tem de obedecer — senão as credenciais ficam sem saída."
    )
    assert "--purge-config" in bloco, (
        "o bloco não menciona mais a flag que dá o wipe — quem quiser apagar não "
        "descobre como."
    )


def test_a_pessoa_e_avisada_de_onde_foi_parar() -> None:
    """O log diz o destino e o caminho de volta.

    Preservar em silêncio é quase tão ruim quanto apagar em silêncio: ela não
    saberia que existe o que restaurar, nem como.
    """
    bloco = _bloco_dos_bonds()
    assert "para restaurar:" in bloco, (
        "o log não diz como restaurar os snapshots preservados."
    )
    assert "cp -a" in bloco, (
        "o comando de restauração não está no log — sem ele o aviso não serve."
    )


def test_o_porque_esta_escrito_no_desinstalador() -> None:
    """Quem for 'limpar' este bloco encontra o custo medido de apagar."""
    bloco = _bloco_dos_bonds()
    assert "CICLO-QUE-PROVA-01" in bloco, (
        "o registro do CICLO-QUE-PROVA-01 saiu do `uninstall.sh`. Sem ele, o `mv` "
        "parece complicação e volta a virar `rm -rf`."
    )
    assert "Doze snapshots viraram um" in bloco, (
        "sumiu o número medido — é ele que faz o comentário valer mais que uma "
        "opinião sobre higiene."
    )
