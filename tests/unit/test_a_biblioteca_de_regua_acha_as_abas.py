"""A biblioteca com que se escreve régua de tela tem de ACHAR as abas.

O DEFEITO, medido em 03/09/2026 e o pior estado que um instrumento alcança:
``regua_de_tela.abas_conhecidas()`` devolvia **ZERO**. Uma régua nova escrita
sobre ela passaria por VACUIDADE — medindo nada e dizendo verde.

**A causa foi a mesma de três instrumentos no mesmo dia:** as pastas mudaram de
nome e as réguas não foram junto. ``layout/`` e ``novo-layout/`` não existem
nesta árvore; as páginas publicadas moraram para
``src/hefesto_dualsense4unix/interface/paginas/`` e a bancada para ``mockup/``.
O ``check_regua_de_tela.py`` e o ``test_arranjo_invariantes.py`` tinham o mesmo
endereço velho.

**E A CURA ABRIU UM PERIGO MAIOR, que este arquivo também mede.** No minuto em
que a biblioteca voltou a achar arquivo, a cópia "mais nova" da aba 04 era
``/tmp/…/audit-cor/wt/…`` — a worktree de OUTRO agente, escrita segundos antes.
Ordenar só pelo relógio faria a régua ler a árvore dele e relatar sobre a nossa:
é a armadilha nº 1 do ``COMO-OLHAR-A-TELA.md``, *medir contra a biblioteca
errada produz alarme convincente e falso*.

A MORDIDA: troque ``PASTAS_DAS_ABAS`` por ``("layout",)`` e
:func:`test_acha_as_dez_abas` reprova com zero; tire a raiz da chave de ordenação
de ``candidatas_da_aba`` e :func:`test_a_arvore_local_vence_o_relogio` reprova
quando houver worktree mais nova na mesa.
"""

from __future__ import annotations

import pathlib
import sys

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "scripts"))

import regua_de_tela as regua


def test_acha_as_dez_abas() -> None:
    """As dez páginas de aba, e não uma a menos.

    O número é literal de propósito: ``> 0`` deixaria a régua passar com UMA
    aba achada, que é quase o mesmo vazio com outra cara.
    """
    abas = regua.abas_conhecidas()
    assert len(abas) == 10, f"achou {len(abas)}: {[a.name for a in abas]}"


@pytest.mark.parametrize("numero", [f"{n:02d}" for n in range(1, 11)])
def test_cada_aba_tem_candidata(numero: str) -> None:
    """Pedir uma aba pelo número devolve arquivo que existe."""
    candidatas = regua.candidatas_da_aba(numero)
    assert candidatas, f"nenhuma cópia da aba {numero}"
    assert candidatas[0].is_file()
    assert candidatas[0].stem.startswith(numero)


def test_a_arvore_local_vence_o_relogio() -> None:
    """A primeira candidata mora NESTA árvore, mesmo com worktree mais nova.

    As worktrees de agente vivem dentro e fora desta raiz e são reescritas o
    tempo todo; uma delas ser mais nova é o caso COMUM enquanto uma leva corre,
    não a exceção. Se a régua seguisse o relógio, mediria o trabalho de outro
    agente e o relataria como se fosse deste.
    """
    escolhida = regua.candidatas_da_aba("04")[0]
    assert escolhida.is_relative_to(RAIZ), (
        f"a régua escolheu uma cópia de fora desta árvore: {escolhida}")
    assert ".claude/worktrees" not in str(escolhida), (
        f"a régua escolheu uma worktree de agente: {escolhida}")


def test_as_duas_casas_de_hoje_existem() -> None:
    """As pastas que a biblioteca declara têm de estar no disco.

    Uma lista de pastas que não existem é exatamente o defeito que este arquivo
    nasceu para não deixar repetir — e ela não dá erro, ela dá VAZIO.
    """
    for pasta in regua.PASTAS_DAS_ABAS:
        assert (RAIZ / pasta).is_dir(), (
            f"`{pasta}` está declarada em PASTAS_DAS_ABAS e não existe")


def test_a_bancada_vem_antes_do_publicado() -> None:
    """A ordem é decisão desta casa, e está escrita em ``onde.pagina``.

    *"Todo instrumento desta casa existe para medir o desenho de HOJE, e
    apontá-lo para o publicado o faria dar verde sobre a página congelada."*
    """
    assert regua.PASTAS_DAS_ABAS[0] == "mockup"
