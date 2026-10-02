#!/usr/bin/env python3
"""O "Atualizar" da aba Sistema não diz "Pronto." sem ter feito.

**A PALAVRA DELA, 05/09/2026, na `09-Q3`:** *"o botão diz Atualizando… e no fim
o campo pisca em verde — **mas o botão tem de realmente fazer o que promete**"*.

O DEFEITO QUE ESTA RÉGUA FECHA, medido em 05/09/2026: o gesto era
`p.chamar("daemon.reload")` e `chamar` devolve um `bool` que ninguém lia.
`_safe_call` devolve `False` para **serviço desligado, socket ausente, timeout
de conexão e erro JSON-RPC** (`app/ipc_bridge.py:74-81`) — e como o gesto não
levantava, o piloto executava o ramo do sucesso
(`interface/hefesto_vivo.py:1862-1864`) e depositava **"Pronto."** em verde. Com
o serviço parado, o botão trocava de palavra, esperava o teto, voltava ao rótulo
e afirmava ter feito. **Nenhum byte havia saído.**

O QUE ELA MEDE, E COMO — e a forma é o ponto: **ela chama o gesto e olha o que
ele fez.** Onze réguas desta casa caíram em 26/08 por *digitarem o que deviam
LER*; nenhuma asserção aqui lê o texto do `a09_sistema.py`.

1. com a ponte recusando **calada** (o caso da mesa dela, e `_call_checked`
   devolve `(False, None)` para toda falha de transporte), o gesto levanta
   `RuntimeError` com a frase de reserva do produto;
2. com a ponte recusando **dizendo** — o daemon respondeu e recusou —, a frase
   que chega à tela é a DELE, não a de reserva;
3. com a ponte aceitando, o gesto volta sem levantar;
4. `_LENTO` fica vazio nos **dois** desfechos;
5. a frase de reserva diz **as duas metades** e não afirma que nada aconteceu;
6. `chamar_detalhado` continua esperando os 15 s de `daemon.reload`, e não os
   250 ms do padrão do bridge.

NENHUM BYTE VAI AO DAEMON DE QUEM RODA A SUÍTE: a ponte é um dublê, e
`atualizar` não precisa entrar em `hefesto_vivo.PERIGOSOS` por causa disto.

A MORDIDA: arranque o `if not ok: raise` do gesto e 1, 2 e 4-recusa reprovam;
a 3 continua verde — é assim que se sabe que ela mede outra coisa.
"""
from __future__ import annotations

import pathlib
import sys

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src/hefesto_dualsense4unix/interface"))

UNIQ = "aa:bb:cc:00:00:01"


class PonteQueResponde:
    """Um dublê da `pacotes/ponte.py` que sabe RECUSAR — as três respostas."""

    def __init__(self, resposta: object) -> None:
        self.resposta = resposta
        self.chamadas: list[tuple[str, tuple, dict]] = []

    def __getattr__(self, nome: str):
        def registrar(*args, **kwargs):
            self.chamadas.append((nome, args, kwargs))
            return self.resposta
        return registrar


@pytest.fixture
def a09():
    import pacotes  # noqa: F401  (registra os gestos das dez abas)
    from pacotes import a09_sistema

    return a09_sistema


@pytest.fixture
def clicar():
    """Chama o gesto `atualizar` com a ponte dada, e devolve a ponte."""
    import pacotes

    def _clicar(ponte):
        fn = pacotes.gesto_da_pagina("09-sistema.html", "atualizar")
        assert fn is not None, "o `atualizar` da aba 09 perdeu o dono"
        ctx = pacotes.Contexto(state={}, mesa=[], conectados=[], estados={})
        fn(ctx, {"controle": "p1", "uniq": UNIQ, "texto": "Régua"}, ponte)
        return ponte

    return _clicar


def test_com_o_servico_mudo_o_botao_recusa_em_vez_de_dizer_pronto(a09, clicar):
    """O caso da mesa dela: serviço parado, motivo `None`, e nada de "Pronto.".

    `RuntimeError` é o contrato desta interface para *"o produto recusou, e a
    frase VAI PARA A TELA"* — `hefesto_vivo._recusou_dizendo:2523`. Sem ele o
    piloto cai no ramo do sucesso e deposita `FRASE_DE_SUCESSO`.
    """
    with pytest.raises(RuntimeError) as caiu:
        clicar(PonteQueResponde((False, None)))

    assert str(caiu.value) == a09.SEM_RESPOSTA_DO_SERVICO, (
        "a frase da recusa não é a do produto. Ela tem UM dono "
        "(`a09_sistema.SEM_RESPOSTA_DO_SERVICO`) porque texto de tela com dois "
        "donos diverge no primeiro dia em que alguém mexe num deles.")


def test_quando_o_servico_diz_por_que_recusou_a_tela_mostra_a_frase_dele(a09, clicar):
    """A frase de reserva é RESERVA — ela não engole o motivo do daemon."""
    recusa = "o serviço recusou: já há um reload em curso"
    with pytest.raises(RuntimeError) as caiu:
        clicar(PonteQueResponde((False, recusa)))

    assert str(caiu.value) == recusa, (
        f"o daemon disse *{recusa}* e a tela mostrou *{caiu.value}*. O motivo "
        f"dele vence a frase de reserva sempre que existe.")


def test_com_o_servico_de_pe_o_botao_nao_levanta(a09, clicar):
    """A cura não pode transformar o clique que funciona em recusa."""
    for resposta in ((True, None), True):
        p = clicar(PonteQueResponde(resposta))
        assert p.chamadas == [("chamar_detalhado", ("daemon.reload",), {})], (
            f"o clique mandou {p.chamadas!r}. O gesto tem de sair pela porta "
            f"que traz o motivo da recusa, e com o método do daemon.")


@pytest.mark.parametrize(
    ("resposta", "levanta"),
    [((True, None), False), ((False, None), True)],
    ids=["deu-certo", "recusou"])
def test_a_aba_rele_na_hora_nos_dois_desfechos(a09, clicar, resposta, levanta):
    """`_LENTO` zerado nos dois — e a recusa é o caso que custa."""
    a09._LENTO["marcador"] = "o valor de antes do clique"

    if levanta:
        with pytest.raises(RuntimeError):
            clicar(PonteQueResponde(resposta))
    else:
        clicar(PonteQueResponde(resposta))

    assert a09._LENTO == {}, (
        f"o cache das leituras caras sobreviveu ao clique: {a09._LENTO!r}. "
        f"Ele tem de zerar nos dois desfechos, e DEPOIS de o `daemon.reload` "
        f"voltar — zerar antes publicaria o estado de antes como o de depois.")


def test_a_frase_de_reserva_diz_as_duas_metades(a09):
    """AS-DUAS-ABAS-FALAM-01, e aqui ela protege contra uma afirmação FALSA."""
    frase = a09.SEM_RESPOSTA_DO_SERVICO

    assert "pode não ter reaplicado nada" in frase, (
        f"a metade do que NÃO se sabe sumiu da frase: {frase!r}")
    assert "pode ter reaplicado sem me responder" in frase, (
        f"a metade do trabalho-feito-sem-resposta sumiu da frase: {frase!r}. "
        f"Sem ela a tela volta a afirmar um desfecho que ninguém mediu.")
    assert "de novo" in frase, (
        f"a frase parou de dizer o que fazer: {frase!r}. Clicar de novo é "
        f"seguro — sem `config_overrides` o reload é `replace` do mesmo valor "
        f"(`daemon/ipc_handlers.py:4002`) —, e uma recusa sem saída deixa quem "
        f"clicou sem próximo passo.")

    for mentira in ("nada foi reaplicado", "nada aconteceu", "não fez nada"):
        assert mentira not in frase.lower(), (
            f"a frase afirma *{mentira}*, e isso não se mede daqui: o daemon "
            f"pode ter feito o trabalho e a resposta não ter chegado.")


def test_a_porta_nova_continua_esperando_os_quinze_segundos(monkeypatch):
    """Se a espera encolher, o botão passa a recusar todo clique que FUNCIONA.

    `daemon.reload` leva 9,5 s medidos no daemon dela em 01/09/2026, e por isso
    tem teto de 15 s em `ponte.TETOS`. O padrão do bridge é 250 ms e, desde o
    `BUG-IPC-READ-NO-TIMEOUT-01`, cobre também a LEITURA da resposta: com ele, o
    `daemon.reload` que dá certo voltaria `False` — e a cura desta sprint viraria
    um defeito pior que o original, porque agora o `False` RECUSA na tela.

    Ela mede o número que SAI da ponte, não o que está escrito na tabela.
    """
    from pacotes import ponte

    visto: list[float | None] = []

    def espiao(metodo, params, timeout=None):
        visto.append(timeout)
        return True, None, None

    monkeypatch.setattr(ponte._b, "_call_checked_detalhado", espiao)
    ponte.chamar_detalhado("daemon.reload")

    assert visto == [15.0], (
        f"`chamar_detalhado('daemon.reload')` esperou {visto!r}. O gesto do "
        f"botão passa por aqui, e 0.25 s é menos que os 9,5 s que o reload "
        f"leva na máquina dela.")
