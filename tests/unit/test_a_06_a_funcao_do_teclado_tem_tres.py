#!/usr/bin/env python3
"""A RÉGUA DA DECISÃO 5: as três palavras da "Função do teclado".

DECISÃO DELA, 02/09/2026: *"`Só dentro do jogo` · `Só fora do jogo` ·
`Desativado`. O padrão de um perfil novo é `Só fora do jogo` — no jogo o L3 é o
clique do analógico e o teclado atrapalha; no desktop é onde ele serve."*

O FATO QUE ESTA RÉGUA DERRUBA, e ele estava escrito no pacote E no enunciado do
trabalho: *"'Só fora do jogo' não existe do outro lado"* e *"'Só dentro do jogo'
já existe, e é o `suppress_desktop_emulation`"*. **Os dois estão invertidos.**

    `Profile.suppress_desktop_emulation` (`profiles/schema.py:1036`)
        "True = ativar o perfil suprime a emulação de mouse/teclado no desktop
         (jogos de GAMEPAD que leem o controle cru)"

O perfil é ativado quando o JOGO casa; logo a supressão vale DURANTE o jogo, e o
teclado sobra FORA dele. E, sem perfil nenhum a dizer o contrário, o daemon já
cala a emulação de desktop quando um jogo assume — `_jogo_no_controle_do_desktop`
(`daemon/lifecycle.py:2263`, a cura da queixa dela de 29/07: *"aperto r1 e ele
muda de app ao invés de funcionar no jogo"*) e o `gamepad_dispatched` do laço
(`:4780`).

Logo o teclado emulado LIGADO **é** "só fora do jogo": a etiqueta velha
("Ligada — atalhos e teclado na tela") é que prometia um alcance maior do que o
produto tem. Quem não tem dono é o INVERSO — "só dentro do jogo" —, e ele pede
um campo novo no perfil, o portão com o sinal trocado.

O QUE ESTA RÉGUA COBRA:

1. as três palavras dela estão no desenho, e a lista nasce no padrão que ela
   escolheu;
2. as duas com dono chamam `keyboard.emulation.set` com o bool certo;
3. a terceira RECUSA DIZENDO, sem chamar nada — em vez de aceitar o clique e
   não fazer nada, que é o defeito mais caro desta casa;
4. o gesto casa pela palavra que DISTINGUE, e não pela primeira: com as três
   palavras dela, duas começam por "só".

A MORDIDA: devolva `_ESCOLHA` a casar pela primeira palavra
(`escolhido.split()[0]`) — o item 4 reprova, porque "Só dentro do jogo" passaria
a ligar o teclado como se fosse "Só fora do jogo".
"""
from __future__ import annotations

import pathlib
import sys

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src/hefesto_dualsense4unix/interface"))

PAGINA = "06-navegacao.html"  # (noqa-acento) nome de arquivo


class _PonteQueAnota:
    """Aceita tudo e ANOTA. É o que separa "recusou" de "chamou e não disse"."""

    def __init__(self) -> None:
        self.chamadas: list[tuple[str, dict]] = []

    def chamar(self, metodo: str, **params: object) -> bool:
        self.chamadas.append((metodo, dict(params)))
        return True


@pytest.fixture
def ctx():
    import pacotes

    return pacotes.Contexto(state={"active_profile": "regua"})


def test_as_tres_palavras_dela_estao_no_desenho():
    """O gerador e o pacote falam a MESMA lista, e ela é a dela.

    A repetição entre `aba06.OPCOES_TECLADO` e as três constantes do pacote é
    declarada nos dois lados; o que não pode é as duas envelhecerem separadas —
    uma opção que o pacote emita e o desenho não ofereça vira um campo parado
    para sempre, porque `escrever()` se cala em silêncio quando não casa.
    """
    import aba06
    from pacotes import a06_navegacao as mod

    assert aba06.OPCOES_TECLADO == [mod.TECLADO_SO_DENTRO, mod.TECLADO_SO_FORA,
                                    mod.TECLADO_DESATIVADO], (
        f"o desenho oferece {aba06.OPCOES_TECLADO} e o pacote fala outra "
        "língua — a lista pararia de ser pintada sem uma linha de erro.")
    assert aba06.TECLADO_PADRAO == mod.TECLADO_SO_FORA, (
        "a lista não nasce no padrão que ela escolheu")


def test_o_desenho_nasce_no_padrao_dela():
    """`Só fora do jogo` marcada, e é a única das três com dono hoje.

    Nascer marcada na primeira (`Só dentro do jogo`) faria a tela prometer, nos
    500 ms anteriores ao primeiro tique, o que o Hefesto ainda não sabe fazer.

    A MORDIDA: tire o `escolhido=TECLADO_PADRAO` da chamada de `simples()` no
    gerador — esta linha reprova, e o `_conferir` do gerador reprova antes.
    """
    import onde
    from pacotes import a06_navegacao as mod

    doc = onde.pagina(PAGINA).read_text(encoding="utf-8")
    assert f"<option selected>{mod.TECLADO_SO_FORA}</option>" in doc
    for opcao in (mod.TECLADO_SO_DENTRO, mod.TECLADO_DESATIVADO):
        assert f"<option>{opcao}</option>" in doc, f"{opcao!r} sumiu do desenho"


@pytest.mark.parametrize("rotulo_e_bool", [("TECLADO_SO_FORA", True),
                                           ("TECLADO_DESATIVADO", False)])
def test_as_duas_com_dono_chamam_o_daemon(ctx, rotulo_e_bool):
    """Uma chamada, `keyboard.emulation.set`, e o bool que a opção quer dizer."""
    from pacotes import a06_navegacao as mod

    nome, esperado = rotulo_e_bool
    ponte = _PonteQueAnota()
    mod.teclado(ctx, {"valor": getattr(mod, nome)}, ponte)
    assert ponte.chamadas == [("keyboard.emulation.set", {"enabled": esperado})], (
        f"{nome}: o gesto chamou {ponte.chamadas}")


def test_a_terceira_recusa_dizendo_e_nao_chama_nada(ctx):
    """"Só dentro do jogo" não tem dono, e o botão DIZ isso.

    Um gesto que aceitasse o clique e não fizesse nada seria a
    `A-CASA-SABE-E-O-PRODUTO-NAO-FAZ` em miniatura: quem clicou concluiria que
    funcionou. `RuntimeError` é o produto recusando com o motivo.

    A MORDIDA: faça `_ESCOLHA["dentro"]` valer `True` — esta linha reprova
    dizendo que a opção sem dono passou a ligar o teclado calada.
    """
    from pacotes import a06_navegacao as mod

    ponte = _PonteQueAnota()
    with pytest.raises(RuntimeError) as caiu:
        mod.teclado(ctx, {"valor": mod.TECLADO_SO_DENTRO}, ponte)
    frase = str(caiu.value)
    assert mod.TECLADO_SO_DENTRO in frase, f"a recusa não diz qual opção: {frase!r}"
    assert mod.TECLADO_SO_FORA in frase, (
        "a recusa não diz o que o produto FAZ hoje, que é o outro lado — sem "
        f"isso ela é um 'não dá' sem saída: {frase!r}")
    assert not ponte.chamadas, f"recusou e ainda assim chamou {ponte.chamadas}"


def test_o_gesto_casa_pela_palavra_que_distingue(ctx):
    """Duas das três começam por "só" — casar pela primeira as confundiria.

    E o casamento é TOLERANTE ao resto da frase: reescrever o texto da tela não
    pode desligar o botão calado, que é o que aconteceria com a frase inteira
    como chave.
    """
    from pacotes import a06_navegacao as mod

    ponte = _PonteQueAnota()
    mod.teclado(ctx, {"valor": "Só fora do jogo — o teclado vale no desktop"}, ponte)
    assert ponte.chamadas == [("keyboard.emulation.set", {"enabled": True})]

    with pytest.raises(RuntimeError):
        mod.teclado(ctx, {"valor": "Só dentro do jogo, e mais nada"},
                    _PonteQueAnota())

    with pytest.raises(ValueError, match="não reconheci"):
        mod.teclado(ctx, {"valor": "Ligada — atalhos e teclado na tela"},
                    _PonteQueAnota())


def test_a_pintura_diz_a_palavra_que_a_lista_oferece():
    """O que o pacote pinta tem de ser uma das três — senão o campo não anda.

    `escrever()` com `data-hef-alvo="valor"` só aceita o texto exato de uma
    `<option>` e devolve `0` **em silêncio** fora disso (`hefesto_vivo.py`, ramo
    `alvo === 'valor'`).
    """
    import pacotes
    from pacotes import a06_navegacao as mod

    for ligado, esperado in ((True, mod.TECLADO_SO_FORA),
                             (False, mod.TECLADO_DESATIVADO)):
        estado = {"active_profile": None,
                  "keyboard_emulation": {"enabled": ligado}}
        mesa = mod.pacote(pacotes.Contexto(state=estado))["mesa"]
        assert mesa["teclado-estado"] == esperado

    # SEM O BLOCO, A CHAVE NÃO SAI — e é o que impede a tela de afirmar um
    # estado que ninguém mediu (daemon mudo, ou config inacessível).
    mudo = mod.pacote(pacotes.Contexto(state={"active_profile": None}))["mesa"]
    assert "teclado-estado" not in mudo, (
        "sem `keyboard_emulation` no estado, a tela afirmaria um estado que o "
        "daemon não disse")
