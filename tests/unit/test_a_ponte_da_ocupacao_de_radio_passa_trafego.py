"""A aba Conexões pergunta a ocupação de rádio ao dono — e recebe resposta.

Até 05/09/2026 ela perguntava errado e nunca soube. A chamada era::

    ocupacao_por_adaptador([c.get("uniq") for c in conectados])

— uma lista de **strings**. O dono (`integrations/radio_da_mesa.py:323`)
declara `Iterable[Mapping]` e faz `controle.get("transport")`, então a chamada
levantava `AttributeError: 'str' object has no attribute 'get'` **sempre**, e o
`except Exception: return {}` logo abaixo engolia.

A chave `adaptadores` do pacote da aba 08 era `{}` em toda máquina, desde que a
linha foi escrita. O sintoma era a AUSÊNCIA de dado — nada quebrava na tela — e
é por isso que a régua do rádio daquela aba recalcula a ocupação por conta
própria em 353 linhas em vez de ler o dono.

A palavra dela, no dia em que isto foi medido:

    "estamos recriando um produto que estava praticamente pronto pro gtk"

Esta régua LÊ o comportamento, não o texto: ela chama a função e confere que
veio conta. E cobra a segunda metade — o `com_ponte_de_mic`, que a GTK passa
(`app/actions/config/secao_mesa.py:1335`) e a aba 08 nunca passou.
"""
from __future__ import annotations

import importlib

import pytest

MODULO = "hefesto_dualsense4unix.interface.pacotes.a08_conexoes"

#: Um DualSense no rádio. `transport` e `connected` são o que o dono LÊ.
NO_RADIO = [{"uniq": "aabbcc000011", "transport": "bt", "connected": True}]


@pytest.fixture
def a08():
    return importlib.import_module(MODULO)


def test_a_ponte_devolve_conta_em_vez_de_vazio(a08):
    """O `{}` de antes era o AttributeError engolido, não 'não há rádio'."""
    saida = a08._adaptadores(NO_RADIO)
    assert saida, (
        "`_adaptadores` devolveu vazio para um controle no rádio. Se a chamada "
        "voltou a passar uma lista de strings, o `except Exception` está "
        "engolindo um AttributeError — ver o cabeçalho desta régua."
    )
    (ocupacao,) = saida.values()
    assert ocupacao.controles == 1
    assert ocupacao.slots_input > 0, "a conta veio zerada com um controle no rádio"


def test_a_ponte_de_microfone_entra_na_conta(a08):
    """Sem ela, a aba conta menos rádio do que a máquina gasta."""
    sem = next(iter(a08._adaptadores(NO_RADIO).values()))
    com = next(
        iter(
            a08._adaptadores(NO_RADIO, {"bt_mic": {"uniqs": ["aabbcc000011"]}}).values()
        )
    )
    assert com.com_microfone == 1, (
        "o `com_ponte_de_mic` não chegou ao dono: a aba 08 voltou a contar o "
        "rádio como se o microfone não custasse nada"
    )
    assert com.slots_audio > 0
    assert com.slots_input + com.slots_audio > sem.slots_input, (
        "a ponte de microfone tem de AUMENTAR o gasto de rádio — a GTK conta "
        "276,7 onde a conta sem ela dá 260,4"
    )


def test_o_estado_sem_a_chave_nao_derruba(a08):
    """Daemon mais velho que a janela não manda `bt_mic`; ausência é vazio."""
    for estado in (None, {}, {"bt_mic": None}, {"bt_mic": {}}, {"bt_mic": {"uniqs": None}}):
        saida = a08._adaptadores(NO_RADIO, estado)
        assert saida, f"o estado {estado!r} zerou a conta em vez de contar sem o mic"
        assert next(iter(saida.values())).com_microfone == 0


def test_a_mordida_a_chamada_antiga_reprovaria(a08):
    """Prova que o defeito era REAL: o jeito antigo levanta, e é o que se engolia."""
    from hefesto_dualsense4unix.integrations import radio_da_mesa

    with pytest.raises(AttributeError):
        radio_da_mesa.ocupacao_por_adaptador([c["uniq"] for c in NO_RADIO])


def test_o_pacote_entrega_o_estado_para_a_ponte(a08):
    """Sem `ctx.state`, a ponte de microfone não teria de onde sair."""
    import inspect

    fonte = inspect.getsource(a08.pacote)
    assert "_adaptadores(ctx.conectados, ctx.state)" in fonte, (
        "o chamador voltou a omitir o estado: a ponte de microfone fica cega e "
        "a aba conta menos rádio do que a máquina gasta"
    )
