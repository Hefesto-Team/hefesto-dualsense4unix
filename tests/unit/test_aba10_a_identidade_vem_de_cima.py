"""ABA 10 — a identidade do controle vem da FITA DO TOPO, nunca do mockup.

A LEI, e ela é dela (03/09/2026):

    *"se no topo tá mostrando controle white player 1, então cada aba vai usar
    os controles lá de cima. Não mistura com a info dos mockups. Cada feature
    faz referencia ao controle conectado. Por isso temos o mapa pra servir como  (noqa-acento)
    variável de identificação"*

(A marca acima é a isenção da casa para **citação literal dela**: as palavras
dela não se corrigem, e o portão de acentuação pula a linha que a carrega.)

O QUE ELA VIU, e é o que originou a lei: a fita do topo dizendo
``P1 · White · USB`` com a tabela por controle logo abaixo pintando a barra de
3px na cor do controle do DESENHO. Nesta aba o defeito tinha endereço exato: o
``--plastico`` morava no ``<tr>``, **sem nenhum ``data-hef``**, então o
``guarda.nome`` ao lado já vinha do aparelho e a barra não vinha de lugar nenhum.

O QUE ESTA RÉGUA COBRA, e cada item é uma metade do conserto:

1. a bancada dá ENDEREÇO à barra, e não sobrou ``--plastico`` cravado no miolo;
2. o pacote ESCREVE aquele endereço com o que leu da mesa — endereço sem
   escritor troca um valor congelado por um vazio, e a tela mente igual;
3. sem cor lida, o valor é VAZIO — nunca a do mockup, nunca um cinza inventado
   (*campo sem informação não mostra nada*);
4. ``ESPERANDO_A_PUBLICACAO`` não vira ponto cego: o nome tem de estar na
   bancada e **não** na publicada.
"""
from __future__ import annotations

import re
from typing import Any

import pytest

from hefesto_dualsense4unix.interface import onde
from hefesto_dualsense4unix.interface.pacotes import Contexto, a10_perfis
from hefesto_dualsense4unix.profiles import loader

PAGINA = "10-perfis.html"  # (noqa-acento) nome de arquivo

#: O ENDEREÇO DA BARRA. Um só nome, nos dois lados — o gerador o escreve no
#: HTML e o pacote o emite; digitá-lo em dois lugares é o que faz uma cura
#: passar pela metade.
BARRA = "guarda.plastico"

#: A MESA DE PROVA — endereços MASCARADOS, faixa sintética da casa (há dois
#: portões de anonimato nesta árvore). As cores são as DELA: um no cabo e um no
#: rádio, que é a mesa que originou a lei.
MESA = [
    {"pref": "p1", "uniq": "aabbcc000001", "jogador": 1, "cor": "white",
     "nome": "White", "via": "USB", "transporte": "usb", "alvo": True,
     "mascara": "DualSense"},
    {"pref": "p2", "uniq": "aabbcc000002", "jogador": 2, "cor": "galactic-purple",
     "nome": "Galactic Purple", "via": "BT", "transporte": "bluetooth",
     "alvo": False, "mascara": "DualSense"},
]

#: O CONTROLE CUJA COR NÃO FOI LIDA. Não é hipótese: pelo rádio a cor não vem —
#: o mapa de canais diz `identidade.cor_do_aparelho = não` — e `mesa_do_estado`
#: entrega `cor: ""` com o nome "Não sei".
SEM_COR = {"pref": "p3", "uniq": "aabbcc000003", "jogador": 3, "cor": "",
           "nome": "Não sei", "via": "BT", "transporte": "bluetooth",
           "alvo": False, "mascara": "DualSense"}


def _bancada() -> str:
    return onde.pagina(PAGINA).read_text(encoding="utf-8")


def _publicada() -> str:
    return onde.pagina(PAGINA, publicado=True).read_text(encoding="utf-8")


def _enderecos(texto: str) -> set[str]:
    return set(re.findall(r'data-(?:campo|papel|hef)="([^"]+)"', texto))


@pytest.fixture
def disco(monkeypatch: pytest.MonkeyPatch) -> list[Any]:
    """Um perfil, sem escrever no disco.

    A ``conftest.py`` põe ``HEFESTO_DUALSENSE4UNIX_SKIP_PRESET_SEED=1`` em todo
    teste, e ``load_all_profiles()`` devolve ``[]`` na suíte inteira — sem esta
    dublagem o pacote cai no ramo vazio e a guarda sai sem uma linha.
    """
    from hefesto_dualsense4unix.profiles.schema import MatchAny, Profile

    todos = [Profile(name="Pragmata", match=MatchAny(), priority=100)]
    monkeypatch.setattr(loader, "load_all_profiles", lambda *a, **k: todos)
    return todos


def _pacote(mesa: list[dict[str, Any]]) -> dict[str, Any]:
    ctx = Contexto(state={"active_profile": "Pragmata"}, mesa=list(mesa),
                   conectados=list(mesa), estados={})
    return a10_perfis.pacote(ctx)


# --------------------------------------------------------------------------
# 1. A BANCADA DÁ ENDEREÇO — e não sobrou cor congelada no miolo
# --------------------------------------------------------------------------
def test_a_barra_do_plastico_tem_endereco_na_bancada() -> None:
    """MORDIDA: tire o ``data-hef`` do ``<span class="pl">`` em
    ``aba10.linha_do_controle``, regere, e a conta cai a zero."""
    html = _bancada()
    quantas = html.count(f'data-hef="{BARRA}"')
    assert quantas == 4, (
        f"são {quantas} barras endereçadas na tabela por controle, e o desenho "
        f"tem quatro linhas. Uma barra sem endereço fica com a cor do MOCKUP "
        f"enquanto o nome ao lado já vem do aparelho.")


def test_o_alvo_da_barra_e_cor_e_nao_fundo() -> None:
    """O alvo `fundo` guarda ``#ae335a`` e lê ``rgb(174, 51, 90)`` de volta: a
    comparação nunca casa e o contador de pinturas soma +1 por tique, para
    sempre. O ramo `cor` escreve e depois compara, e por isso é idempotente.

    MORDIDA: troque o alvo por ``fundo`` no gerador e regere."""
    html = _bancada()
    assert html.count('data-hef-alvo="cor"') == 4, (
        "a barra do plástico perdeu o alvo `cor` — com `fundo` o contador de "
        "pinturas mente uma vez por tique, e ele é O instrumento com que esta "
        "casa prova que um endereço existe")


def test_nenhum_plastico_congelado_sobrou_no_miolo_da_bancada() -> None:
    """A régua da leva — ``check_identidade_vem_de_cima.py`` — acusa
    ``--plastico:#hex`` num elemento sem endereço. No miolo desta aba não pode
    haver nenhum: a cor de um aparelho não se digita na página.

    MORDIDA: devolva ``style="--plastico:{plastico}"`` ao ``<tr>`` e regere.

    O MIOLO, E NÃO A PÁGINA INTEIRA: a fita de chips vem do ``monta.fita()``,
    que é das DEZ abas e não é território desta. Ela é trocada inteira pelo
    piloto (``hefesto_vivo.pintar``, ``p.fita``) com a mesa VIVA; o conserto do
    endereço dela é um só, compartilhado, e está no relato desta frente.
    """
    miolo = _bancada().split('class="miolo"')[-1]
    assert "--plastico:" not in miolo, (
        "voltou um `--plastico` cravado no miolo da 10 — identidade de aparelho "
        "escrita à mão numa página é o desenho mandando na tela do produto")


# --------------------------------------------------------------------------
# 2. O PACOTE ESCREVE — endereço sem escritor é um vazio no lugar de um erro
# --------------------------------------------------------------------------
def test_o_pacote_manda_a_cor_do_plastico_de_cada_controle(disco: list[Any]) -> None:
    """As cores são as do MAPA, lidas por ``monta.cor_da_zona``.

    MORDIDA: apague a linha ``fora["guarda.plastico"] = …`` de ``pacote()`` —
    ou o ``"plastico": _plastico(c)`` de ``_mesa_com_rotulo`` — e este teste
    nomeia o que sumiu.
    """
    from hefesto_dualsense4unix.interface import monta

    fora = _pacote(MESA)
    assert BARRA in fora, (
        "o pacote da 10 não manda a cor do plástico: a barra fica com a do "
        "mockup para sempre, e dar endereço sem escritor é maquiagem")
    assert fora[BARRA] == [monta.cor_da_zona("white"),
                           monta.cor_da_zona("galactic-purple")], (
        "a cor da barra não é a do mapa. Ela tem de sair de "
        "`cor_da_zona()` — o mesmo `<style>` de onde a fita tira a do chip")


def test_a_lista_da_barra_acompanha_a_da_linha(disco: list[Any]) -> None:
    """A pintura DISTRIBUI listas pelos elementos de mesmo endereço, na ordem —
    então a barra e o nome têm de ter o mesmo tamanho, ou a linha 2 recebe a cor
    da linha 1."""
    fora = _pacote(MESA)
    assert len(fora[BARRA]) == len(fora["guarda.nome"]), (
        "a lista da barra e a do nome têm tamanhos diferentes: a distribuição "
        "por ordem daria a cor de um controle à linha de outro")


# --------------------------------------------------------------------------
# 3. SEM COR LIDA, NADA — nunca a do mockup, nunca um cinza inventado
# --------------------------------------------------------------------------
def test_sem_cor_lida_a_barra_fica_vazia(disco: list[Any]) -> None:
    """Regra dela: *campo sem informação não mostra nada*.

    O vazio faz o piloto escrever ``''`` no alvo `cor` — o `style` de linha cai,
    o ``color:transparent`` da classe volta, e a barra SOME. Um cinza inventado,
    ou a cor do desenho, seria a tela afirmando um modelo que ninguém pode
    conferir.

    MORDIDA: devolva um hexadecimal padrão em ``_plastico`` e este teste o pega.
    """
    assert a10_perfis._plastico(SEM_COR) == "", (
        "a aba inventou uma cor para um controle cuja cor não foi lida")
    fora = _pacote([*MESA, SEM_COR])
    assert fora[BARRA][-1] == "", (
        "o controle sem cor lida saiu com cor na tabela por controle")


def test_um_colorway_que_o_mapa_nao_tem_nao_derruba_a_aba() -> None:
    """``cor_da_zona`` ergue ``SystemExit`` — que **não** é ``Exception`` — para
    um colorway ausente. Foi assim que o piloto morreu na primeira execução da
    fita viva: um ``except Exception`` passa ao lado e a janela inteira cai.

    MORDIDA: tire o ``SystemExit`` do ``except`` de ``_plastico``.
    """
    assert a10_perfis._plastico({"cor": "cor-que-nao-existe"}) == ""


# --------------------------------------------------------------------------
# 4. O QUE ESPERA O ATO DELA NÃO VIRA PONTO CEGO
# --------------------------------------------------------------------------
def test_o_que_espera_publicacao_ja_esta_na_bancada() -> None:
    """Declarar "espera a publicação" sobre um endereço que nem a bancada tem é
    dizer que está pronto o que não foi feito.

    MORDIDA: ponha um nome inventado em ``ESPERANDO_A_PUBLICACAO``.
    """
    tem = _enderecos(_bancada())
    faltando = set(a10_perfis.ESPERANDO_A_PUBLICACAO) - tem
    assert not faltando, (
        f"{sorted(faltando)} está declarado como 'esperando a publicação' e a "
        f"BANCADA não tem o endereço. Não está esperando: está faltando.")


def test_o_que_espera_publicacao_sai_da_lista_quando_ela_publicar() -> None:
    """Uma declaração que envelheceu é a régua se desligando sem ninguém
    decidir isso — no dia em que ela publicar, o nome sai desta lista.

    MORDIDA: ponha ``perfis.conta`` (que a publicada já tem) na lista.
    """
    ja_publicados = set(a10_perfis.ESPERANDO_A_PUBLICACAO) & _enderecos(_publicada())
    assert not ja_publicados, (
        f"{sorted(ja_publicados)} já está na página PUBLICADA e continua "
        f"declarado como à espera. Tire da lista no mesmo commit.")


def test_toda_declaracao_traz_a_razao() -> None:
    """Isenção sem razão não é isenção — é ponto cego com nome bonito."""
    for nome, razao in a10_perfis.ESPERANDO_A_PUBLICACAO.items():
        assert len(razao.strip()) >= 20, f"`{nome}` está declarado sem razão"
