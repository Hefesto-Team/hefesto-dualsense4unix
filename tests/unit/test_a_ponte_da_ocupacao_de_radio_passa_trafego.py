"""A aba Conexões não faz mais a conta de ocupação do rádio — ela a LÊ do daemon.

**NASCEU EM 05/09/2026** cobrando a ponte `a08._adaptadores`, que perguntava a
ocupação ao dono (`radio_da_mesa.ocupacao_por_adaptador`) com uma lista de
strings onde o dono queria dicionários: a chamada levantava sempre, o `except`
engolia, e a chave `adaptadores` do pacote era `{}` em toda máquina. A palavra
dela, no dia em que isso foi medido:

    "estamos recriando um produto que estava praticamente pronto pro gtk"

**23/09/2026 — A PONTE SAIU, E A RAZÃO É A MESMA DA CURA DE 05/09**
(TRANSPLANTE-DA-SECAO-01). A seção «Rádio e Adaptadores» virou o desenho
aprovado, e a decisão de quem coordenou a leva foi que a tela não conta
ocupação nenhuma: ela LÊ o que o daemon publica no `state_full` —
`radio_ar`, `radio_governador` e `radio_central` —, e o `Ocupacao`, o
`palavra_da_ocupacao` e o `SLOTS_POR_RELATORIO` saem da aba 08. Uma conta
feita pela tela é a segunda grafia do que o governador decide, e a primeira
coisa que uma segunda grafia perde é a revisão dela.

A MORDIDA: devolva ao pacote uma importação de `Ocupacao` ou uma chamada a
`ocupacao_por_adaptador` e o primeiro caso reprova com a linha.
"""
from __future__ import annotations

import importlib
import inspect
import re

import pytest

MODULO = "hefesto_dualsense4unix.interface.pacotes.a08_conexoes"

#: O que saiu da aba 08, e não volta sem reabrir esta régua.
A_CONTA_DA_TELA = ("Ocupacao", "palavra_da_ocupacao", "SLOTS_POR_RELATORIO",
                   "ocupacao_por_adaptador")


@pytest.fixture
def a08():
    return importlib.import_module(MODULO)


def _codigo(fonte: str) -> str:
    """O fonte sem comentários: a régua mede CÓDIGO, e a prosa conta a história."""
    return "\n".join(re.sub(r"#.*$", "", linha) for linha in fonte.splitlines())


def test_a_aba_08_nao_faz_a_conta_da_ocupacao(a08):
    codigo = _codigo(inspect.getsource(a08))
    for nome in A_CONTA_DA_TELA:
        linhas = [n for n in codigo.splitlines() if re.search(rf"\b{nome}\b", n)]
        assert not linhas, (
            f"`{nome}` voltou à aba 08 — a ocupação é do daemon (`radio_ar`, "
            f"`radio_governador`), e a tela só a lê: {linhas[:3]}")


def test_a_ponte_antiga_nao_existe_mais(a08):
    assert not hasattr(a08, "_adaptadores"), (
        "`_adaptadores` voltou: a chave `adaptadores` não tem mais leitor na página")


def test_a_secao_le_o_que_o_daemon_publica(a08):
    """As três chaves do `state_full` são lidas pela cena — nenhuma é inventada."""
    fonte = inspect.getsource(a08.cena_do_radio)
    for chave in ("radio_ar", "radio_governador", "radio_central"):
        assert f'st.get("{chave}")' in fonte, (
            f"a cena deixou de ler `{chave}` do `state_full`")
