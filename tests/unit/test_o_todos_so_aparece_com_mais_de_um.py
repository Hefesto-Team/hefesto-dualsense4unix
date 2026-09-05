"""O chip `Todos` da fita só existe quando há MAIS DE UM controle na mesa.

DECISÃO DELA, 04/09/2026:

    "só faz sentido aparecer o todos, no selecionar se tiver mais de um
     controle conectado. faz isso também"

Com UM controle ligado, `Todos` e o chip dele escolhem EXATAMENTE o mesmo
conjunto: o botão não oferece escolha nenhuma e ainda divide a atenção com o
único chip que oferece.

**O CHIP É ESCRITO EM TRÊS LUGARES VIVOS, e lido por posição em mais dois** —
por isso a régua mora num arquivo só e visita os cinco:

    monta.fita()                       as dez páginas e o piloto (hefesto_vivo)
    a06_navegacao.chips_da_fita()      a fita da 06, quando o dono desiste
    a09_sistema._html_da_fita()        a fita da 09, idem
    aba02.fita_clicavel()              casa chip com rádio NA ORDEM
    jogar_vivo._indice_na_fita()       para quem o `Todos` era o zero

**AS DUAS METADES QUE CUSTAM**, e as duas são estado, não desenho:

1. **A IDA** — some o segundo controle e a fita não pode ficar com um chip e
   NENHUM aceso. Com um controle na mesa ele é a escolha, e acende.
2. **A VOLTA** — o segundo controle chega, o `Todos` reaparece, e o que estava
   escolhido continua escolhido. Isso só é verdade porque `escolha_da_fita` não
   GRAVA nada: quem chama fica com o `ativo` que tinha. Gravar a queda seria a
   marca de mão única que já custou caro nesta casa
   (QUEBRA-CARTAO-QUE-NAO-REABRE-01) — o `Todos` cairia para `p1` na
   desconexão e nunca mais voltaria.

FIXTURES: faixa sintética `02fe00` da casa. Nenhum endereço real em arquivo
versionado, e há dois portões que reprovam.
"""

from __future__ import annotations

import re
from typing import Any

import pytest

# A ORDEM IMPORTA: `pacotes/__init__` põe `interface/` no `sys.path`, e é dele
# que `monta` precisa para achar o `onde`. Importar `monta` primeiro dá
# `ModuleNotFoundError: No module named 'onde'`.
from hefesto_dualsense4unix.interface import pacotes  # noqa: F401  isort:skip
from hefesto_dualsense4unix.interface import monta
from hefesto_dualsense4unix.interface.pacotes import a06_navegacao, a09_sistema

#: Os dois da bancada, na faixa sintética da casa.
NO_CABO = "02fe00000001"
NO_RADIO = "02fe00000002"


def _item(pref: str, jogador: int, via: str, uniq: str,
          cor: str = "", nome: str = "Não sei") -> dict[str, Any]:
    """Um item de mesa VIVA, com as chaves que `mesa_viva.mesa_do_estado` põe."""
    return {
        "pref": pref, "uniq": uniq, "jogador": jogador, "cor": cor, "nome": nome,
        "via": via, "transporte": "usb" if via == "USB" else "bt",
        "alvo": pref == "p1", "mascara": "DualSense",
    }


#: A mesa dela quando os DOIS estão ligados.
DOIS = [_item("p1", 1, "USB", NO_CABO, cor="white", nome="White"),
        _item("p2", 2, "BT", NO_RADIO)]
#: E quando ela desliga o segundo.
UM = DOIS[:1]


def _tem_todos(html: str) -> bool:
    """O chip `Todos` está na fita?

    PELA TAG INTEIRA, e não por `"Todos" in html`: a palavra também aparece em
    `title` de dica e em texto de legenda, e uma régua que a procurasse solta
    daria verde sobre uma frase — que é a forma de instrumento falso que esta
    casa mais paga.
    """
    return re.search(r'<label class="chip[^"]*"[^>]*>Todos</label>', html) is not None


def _acesos(html: str) -> int:
    """Quantos chips estão acesos. Nunca pode ser zero com a mesa cheia."""
    return len(re.findall(r'<label class="chip[^"]*\bon"', html))


# ---------------------------------------------------------------------------
# 1. O DONO DA REGRA — `monta.escolha_da_fita`, e os três emissores o consultam
# ---------------------------------------------------------------------------
def test_a_regra_e_uma_so_e_responde_pelo_numero_de_controles() -> None:
    """Dois é escolha; um e zero não são.

    MORDIDA: troque o `> 1` de `cabe_o_todos` por `>= 1` e o caso de UM reprova.
    """
    assert monta.cabe_o_todos(DOIS) is True
    assert monta.cabe_o_todos(UM) is False
    assert monta.cabe_o_todos([]) is False


def test_a_escolha_nao_grava_nada_e_por_isso_a_volta_funciona() -> None:
    """A IDA e a VOLTA, no dono da regra, com o MESMO `ativo` guardado.

    Este é o teste da marca de mão única: quem chama entra com `"todos"` nos dois
    tempos, porque `escolha_da_fita` não tem como mudar o que ele guarda.

    MORDIDA: faça `escolha_da_fita` devolver o `ativo` já rebaixado e guarde-o do
    lado de quem chama (o que um `self.ativo = ativo` faria) — a volta passa a
    devolver `p1` com dois na mesa, e este teste reprova.
    """
    assert monta.escolha_da_fita("todos", DOIS) == (True, "todos")
    assert monta.escolha_da_fita("todos", UM) == (False, "p1")
    # A VOLTA, com o mesmo "todos" que quem chama nunca deixou de ter.
    assert monta.escolha_da_fita("todos", DOIS) == (True, "todos")


def test_com_um_controle_a_escolha_cai_para_o_que_restou() -> None:
    """Nunca uma fita sem ninguém escolhido — nem quando quem sai é o P1.

    MORDIDA: devolva `ativo` intocado no ramo de um controle só e este teste
    reprova, com a fita mostrando um chip e nenhum aceso.
    """
    so_o_radio = [DOIS[1]]
    assert monta.escolha_da_fita("todos", so_o_radio) == (False, "p2")
    assert monta.escolha_da_fita("p1", so_o_radio) == (False, "p2")


# ---------------------------------------------------------------------------
# 2. O PRIMEIRO EMISSOR — `monta.fita()`, que é das dez abas e do piloto
# ---------------------------------------------------------------------------
def test_a_fita_esconde_o_todos_com_um_controle_e_o_devolve_com_dois() -> None:
    """A mordida DOS DOIS SENTIDOS, na função que as dez páginas usam.

    MORDIDA: volte o `chips = [f'<label class="chip…">Todos</label>']` incondicional
    e o caso de UM reprova; tire o `if mostra_todos` inteiro e o de DOIS reprova.
    """
    com_dois = monta.fita(ativo="todos", mesa=DOIS)
    assert _tem_todos(com_dois), com_dois
    assert _acesos(com_dois) == 1, com_dois

    com_um = monta.fita(ativo="todos", mesa=UM)
    assert not _tem_todos(com_um), com_um
    # O ÚNICO QUE SOBROU CONTINUA NA TELA, e aceso: some o botão, não o controle.
    assert "P1" in com_um and _acesos(com_um) == 1, com_um

    # A VOLTA: o mesmo `ativo` de sempre, e o `Todos` reacende.
    de_volta = monta.fita(ativo="todos", mesa=DOIS)
    assert _tem_todos(de_volta) and de_volta == com_dois, de_volta


def test_o_rotulo_da_fita_fica_mesmo_sem_o_todos() -> None:
    """O `Selecionar:` é o rótulo, não o chip — ele não some junto."""
    assert monta.ROTULO_DA_FITA in monta.fita(ativo="todos", mesa=UM)


def test_o_desenho_dela_nao_se_mexe() -> None:
    """A bancada tem DOIS na mesa, então o `Todos` continua lá, byte a byte.

    É o que faz as dez páginas publicadas saírem iguais depois desta cura — a
    régua do desenho aprovado compara o que se VÊ, e não se vê mudança nenhuma.
    """
    assert len(monta.CONECTADOS) > 1, "a mesa do desenho encolheu — releia esta cura"
    assert _tem_todos(monta.fita(ativo="todos"))


# ---------------------------------------------------------------------------
# 3. OS OUTROS DOIS EMISSORES — a 06 e a 09 escrevem a fita delas
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("quem", ["06", "09"])
def test_as_abas_que_escrevem_a_propria_fita_seguem_a_mesma_regra(quem: str) -> None:
    """A 06 e a 09 não podem oferecer o botão que a 01 já não oferece.

    MORDIDA: devolva o `'<label class="chip on">Todos</label>'` incondicional em
    qualquer uma das duas e o caso de UM reprova só nela — que é exatamente a
    divergência que fazer a régua morar em `monta` existe para impedir.
    """
    emitir = (a06_navegacao.chips_da_fita if quem == "06"
              else a09_sistema._html_da_fita)

    com_dois = emitir(DOIS)
    assert _tem_todos(com_dois), com_dois
    assert _acesos(com_dois) == 1, com_dois

    com_um = emitir(UM)
    assert not _tem_todos(com_um), com_um
    # E ALGUÉM CONTINUA ACESO: sem o `Todos`, quem acende é o que restou.
    assert _acesos(com_um) == 1, com_um

    assert emitir(DOIS) == com_dois, "a volta não devolveu a fita de dois"


# ---------------------------------------------------------------------------
# 4. OS DOIS LEITORES POSICIONAIS — quem casa chip com rádio pela ORDEM
# ---------------------------------------------------------------------------
def test_o_casamento_com_os_radios_nao_para_com_um_controle() -> None:
    """`aba02.fita_clicavel` casa chip e rádio NA ORDEM, e parava com `SystemExit`.

    Com um controle na mesa a fita passa a ter um chip; a lista de rádios ainda
    trazia o `c-todos`, e o gerador morria com `1 chips para 2 rádios` — o piloto
    da Controles caindo no dia em que ela desliga o segundo controle.

    MORDIDA: volte o `ids = ["c-todos"] + …` incondicional e este teste reprova
    com o `SystemExit` no texto.
    """
    import aba02

    bruta = monta.fita(ativo="todos", mesa=UM)
    saida = aba02.fita_clicavel(bruta, mesa=UM)
    assert 'for="c-p1"' in saida, saida
    assert 'for="c-todos"' not in saida, saida

    com_dois = aba02.fita_clicavel(monta.fita(ativo="todos", mesa=DOIS), mesa=DOIS)
    assert 'for="c-todos"' in com_dois and 'for="c-p2"' in com_dois, com_dois


def test_o_indice_do_alvo_na_fita_conta_o_todos_so_quando_ele_existe() -> None:
    """`jogar_vivo._indice_na_fita` acendia `chips[1]` numa fita de um chip.

    A função é lida pelo JS da bancada (`chips[i].classList.toggle('on', …)`), e
    um índice fora da fita é ninguém aceso com a régua dizendo "clicou".

    MORDIDA: force o `start=1` e o caso de UM reprova.
    """
    jogar_vivo = pytest.importorskip(
        "hefesto_dualsense4unix.interface.jogar_vivo",
        reason="a bancada da 01 pede gi/Gtk, que nem toda árvore tem")

    class _Falso:
        alvo: str | None = None
        chaves: tuple = ()

    def chave(m: list[dict[str, Any]]) -> tuple:
        """A chave de remontagem, na forma exata que `jogar_vivo` monta."""
        return (tuple((c["uniq"], c["cor"], c["nome"], c["via"], c["jogador"])
                      for c in m), ())

    falso = _Falso()
    falso.chaves = chave(DOIS)
    falso.alvo = NO_RADIO
    assert jogar_vivo.Janela._indice_na_fita(falso) == 2

    falso.chaves = chave(UM)
    falso.alvo = NO_CABO
    assert jogar_vivo.Janela._indice_na_fita(falso) == 0, (
        "com um controle o único chip é o zero — o `Todos` não está lá")
