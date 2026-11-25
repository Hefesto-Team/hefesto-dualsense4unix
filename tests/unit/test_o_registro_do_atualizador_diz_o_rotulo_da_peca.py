"""O registro e o ``--conferir`` do atualizador dizem o rótulo da peça que tem um.

A peça dos pacotes do sistema guarda a versão da distribuição como instalada e a contagem de
pacotes como publicada: «24.04 -> 20» lia a contagem como versão (medido em 24/11/2026, no
registro de uma fila de verdade). Vale a D-1611-O-ATUALIZAR-TROCA-E-LIMPA: o que o atualizador
escreve da troca é o que trocou.

MORDE: devolver a ``_de_para`` a condição ``and not versoes.instalada`` reprova o primeiro teste;
trocar a ``_linha_da_conferencia`` pelo par de versões reprova o terceiro.
"""
from __future__ import annotations

from hefesto_dualsense4unix.app.actions import atualizador as at


def test_a_peca_com_rotulo_e_versao_instalada_diz_o_rotulo() -> None:
    versoes = at.Versoes("24.04", "20", rotulo="20 pacotes", nova=True)
    assert at._de_para(versoes) == "20 pacotes"


def test_a_peca_sem_rotulo_segue_dizendo_de_e_para() -> None:
    assert at._de_para(at.Versoes("5.87", "5.88")) == "5.87 -> 5.88"
    assert at._de_para(at.Versoes("", "1.4.4")) == "— -> 1.4.4"
    assert at._de_para(at.Versoes("", "filelock 4.3.1", rotulo="1 pacote")) == "1 pacote"


def test_o_conferir_diz_o_rotulo_da_peca_do_sistema() -> None:
    item = {"nome": "Pacotes do sistema", "de": "24.04", "para": "20", "rotulo": "20 pacotes",
            "estado": "nova"}
    assert at._linha_da_conferencia(item) == "Pacotes do sistema: 20 pacotes (nova)"


def test_o_conferir_segue_como_era_nas_outras_pecas() -> None:
    python = {"nome": "Python", "de": "", "para": "filelock 4.3.1", "rotulo": "1 pacote",
              "estado": "nova"}
    em_dia = {"nome": "Bluetooth", "de": "5.88", "para": "5.88", "rotulo": "", "estado": "em_dia"}
    fora = {"nome": "Portal do COSMIC", "de": "", "para": "", "rotulo": "", "estado": "fora"}
    assert at._linha_da_conferencia(python) == "Python: 1 pacote -> filelock 4.3.1 (nova)"
    assert at._linha_da_conferencia(em_dia) == "Bluetooth: 5.88 -> 5.88 (em_dia)"
    assert at._linha_da_conferencia(fora) == "Portal do COSMIC: — -> — (fora)"
