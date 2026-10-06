#!/usr/bin/env python3
"""A ABA 07 USA O CONTROLE DA MESA, e a mesa lê do APARELHO.

A LEI, e é do usuário (03/09/2026):

    "se no topo tá mostrando controle white player 1, então cada aba vai usar
    os controles lá de cima. Não mistura com a info dos mockups. Cada feature
    faz referencia ao controle conectado.   <!-- noqa-acento: citação -->
    Por isso temos o mapa pra servir como variável de identificação"

O QUE ESTAVA NA TELA, medido em 03/09/2026 com os DOIS controles do usuário na mesa
(um no cabo, um no rádio), na foto da `07-lancadores`:

    cabeçalho   2 controles: 1 USB · 1 BT      <- certo, lido do aparelho
    fita        P1 · Cosmic Red · USB          <- o MOCKUP, e ela não tem esse
                P2 · Starlight Blue · BT       <- o MOCKUP

A `07-lancadores` tinha SEIS valores de identidade congelados
(`scripts/check_identidade_vem_de_cima.py --bancada --aba 07`), e os seis eram a
fita: dois `--plastico`, dois nomes de colorway no texto e dois no `title`.

POR QUE ELES ESTAVAM LÁ: `monta()` injeta a fita chamando `fita(inerte=True)`
SEM `mesa`, e nesse caminho ela cai nos `CONECTADOS` do desenho. A página
estática nasce, portanto, nomeando dois controles que esta máquina não tem — e
`hefesto_vivo._fita` desistia de repintá-la (devolve `""` quando QUALQUER
controle está sem cor, e o JS só troca o bloco `if(p.fita)`), de modo que o
desenho sobrevivia inteiro na tela.

A CURA DESTA ABA tem duas metades, e uma sem a outra não anda:

1. o GERADOR tira da página os chips que nomeiam controle. A página estática não
   sabe nada dos controles do usuário, e a regra é a dela — *campo sem informação não
   mostra nada*. Fica o `Selecionar:` e o chip `Todos`, que são ESTRUTURA;
2. o PACOTE escreve os chips com a mesa VIVA, por `blocos[".fita"]`. **Sem esta
   metade, a primeira seria maquiagem**: zeraria a régua e deixaria a fita vazia.

A MORDIDA, medida em 03/09/2026: comentar o `onde.gravar(...)` do `aba07.py` e
regerar devolve os SEIS congelados à régua e faz a régua do próprio gerador
reprovar nomeando `['Cosmic Red', 'Starlight Blue']`. Devolvida a linha, zero.

O QUE ESTES CASOS NÃO COBREM, de propósito: o número do jogador. `P1`…`P4` são a
POSIÇÃO na mesa, não a identidade do aparelho — *"O p1 ou p2 reflete o player do
jogador."*

A SEGUNDA METADE FOI EMBORA EM 06/09/2026 (ONDA5-07-01), e a razão é que a
PRIMEIRA premissa caiu antes dela: a desistência do `hefesto_vivo._fita`
descrita acima — *"devolve `""` quando QUALQUER controle está sem cor"* — foi
curada em 03/09, e desde então o piloto repinta a fita viva em toda mesa que
tenha alguém. Com as duas metades vivas ficaram **dois donos** no mesmo
endereço: 120 mutações em 40 tiques, e a fita que ganhava era a desta aba —
sem `data-campo`, sem cor de plástico e com um `Todos` que a fita viva não tem
com um controle só. Hoje a aba só escreve a fita quando o piloto se cala, que é
a mesa VAZIA.
"""
from __future__ import annotations

import csv
import pathlib
import re
import sys

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
INTERFACE = RAIZ / "src" / "hefesto_dualsense4unix" / "interface"
sys.path.insert(0, str(INTERFACE))

PAGINA = "07-lancadores.html"

#: As chaves são as de `mesa_viva.mesa_do_estado`, que é quem monta a mesa viva.
def _palavra(transporte: str) -> str:
    """A palavra do transporte PERGUNTADA À DONA — nunca digitada aqui."""
    from hefesto_dualsense4unix.app.actions.home_actions import palavra_do_transporte

    return palavra_do_transporte(transporte)


MESA_COM_UM_SEM_COR = [
    {"pref": "p1", "jogador": 1, "cor": "white", "nome": "White",
     "via": "USB", "transporte": "usb", "alvo": True},
    {"pref": "p2", "jogador": 2, "cor": "", "nome": "Não sei",
     "via": "BT", "transporte": "bt", "alvo": False},
]


#: O texto que `mesa_viva.mesa_do_estado` põe em `nome` quando o leitor de cor
SEM_LEITURA_DE_COR = "Não sei"

SELETOR_DA_FITA = ".fita"


def _fita_da_07(mesa: list[dict]) -> str:
    """A fita que o produto pinta nesta aba, pelo dono das dez."""
    from hefesto_dualsense4unix.interface import hefesto_vivo

    return hefesto_vivo._fita(mesa, PAGINA)


@pytest.fixture(scope="module")
def a07():
    from hefesto_dualsense4unix.interface.pacotes import a07_lancadores

    return a07_lancadores


@pytest.fixture
def ctx():
    import pacotes

    return pacotes.Contexto(state={"active_profile": "regua"},
                            mesa=list(MESA_COM_UM_SEM_COR),
                            conectados=[], estados={})


def _bancada() -> str:
    """A página da BANCADA — o desenho de HOJE, não o congelado."""
    from hefesto_dualsense4unix.interface import onde

    caminho = onde.pagina(PAGINA)
    if not caminho.exists():
        pytest.fail(f"{caminho} não existe — a régua mediria o vazio.")
    return caminho.read_text(encoding="utf-8")


def _colorways() -> list[str]:
    """Os 28 nomes, lidos do CSV que é dono deles."""
    bruto = (RAIZ / "docs/data/cores-do-dualsense.csv").read_text(encoding="utf-8")
    linhas = [ln for ln in bruto.splitlines()
              if ln.strip() and not ln.lstrip().startswith("#")]
    nomes = {(ln.get("nome") or "").strip() for ln in csv.DictReader(linhas)}
    return sorted(n for n in nomes if len(n) >= 4)


def _chips(html: str) -> list[str]:
    """Os `<label class="chip …">` da fita, um por elemento, na ordem."""
    partes = html.split('<label class="chip')[1:]
    return ['<label class="chip' + p for p in partes]


def test_o_chip_sem_cor_lida_nao_inventa_cor(a07) -> None:
    """Regra de produto: campo sem informação NÃO MOSTRA NADA."""
    chips = _chips(_fita_da_07(MESA_COM_UM_SEM_COR))
    assert len(chips) == 3, (
        f"esperava `Todos` + dois controles, saíram {len(chips)}. Uma fita que "
        f"perde chip esconde controle da mesa dela.")

    do_radio = chips[2]
    assert "--plastico" not in do_radio, (
        f"o chip do controle SEM cor lida trouxe `--plastico`. Inventar a cor "
        f"do plástico é a lei de 03/09 ao contrário:\n{do_radio}")
    assert SEM_LEITURA_DE_COR not in do_radio, (
        f"o chip escreveu {SEM_LEITURA_DE_COR!r} na tela. `mesa_do_estado` "
        f"usa esse texto quando o leitor não conhece a peça — ele é a AUSÊNCIA "
        f"de leitura, e a regra dela é não mostrar nada:\n{do_radio}")
    assert "P2" in do_radio and _palavra("bt") in do_radio, (
        f"o chip perdeu o jogador ou o transporte, que a leitura TROUXE. Calar "
        f"sobre o que se sabe é o defeito oposto, e igualmente caro:\n{do_radio}")


def test_o_chip_com_cor_lida_diz_o_modelo(a07) -> None:
    """A outra metade: o que FOI lido aparece."""
    do_cabo = _chips(_fita_da_07(MESA_COM_UM_SEM_COR))[1]
    assert "White" in do_cabo, (
        f"o modelo LIDO do aparelho não chegou ao chip:\n{do_cabo}")
    assert "P1" in do_cabo and _palavra("usb") in do_cabo, (
        f"o chip do cabo perdeu o jogador ou o transporte:\n{do_cabo}")


def test_a_fita_nao_cai_de_volta_no_desenho(a07) -> None:
    """Nenhum dos nomes do mapa entra na fita sem ter vindo da LEITURA."""
    saiu = _fita_da_07(MESA_COM_UM_SEM_COR)
    lidos = {str(c["nome"]) for c in MESA_COM_UM_SEM_COR if c["cor"]}
    for nome in _colorways():
        if nome in lidos:
            continue
        assert nome not in saiu, (
            f"a fita trouxe {nome!r}, e ele NÃO saiu da leitura "
            f"(lidos: {sorted(lidos)}). O caminho de volta ao mockup está "
            f"aberto:\n{saiu}")


def test_a_fita_tem_um_dono_so_com_alguem_na_mesa(a07, ctx, monkeypatch) -> None:
    """ERA `test_o_pacote_escreve_a_fita`, e ele exigia o SEGUNDO dono."""
    monkeypatch.setattr(a07.VIGIA, "agora", lambda: None)

    assert 'class="fita' in _bancada(), (
        f"a página não tem `{SELETOR_DA_FITA}` — o `blocos` cairia no chão, "
        f"e `querySelector` devolve `null` sem uma linha de erro")

    blocos = a07.pacote(ctx).get("blocos") or {}
    assert SELETOR_DA_FITA not in blocos, (
        f"a aba 07 voltou a publicar um bloco em {SELETOR_DA_FITA!r} com "
        f"alguém na mesa. `.fita` é endereço do PILOTO (`hefesto_vivo._fita` "
        f"→ `monta.fita`): dois donos no mesmo tique é a tela sambando, e quem "
        f"ganha é o bloco — a fita MENOS informada das duas.")


def test_a_fita_da_mesa_vazia_tambem_e_do_piloto(a07, monkeypatch) -> None:
    """ERA `test_a_fita_da_mesa_vazia_ainda_sai_daqui`, e a premissa dele morreu."""
    import pacotes

    from hefesto_dualsense4unix.interface import hefesto_vivo

    monkeypatch.setattr(a07.VIGIA, "agora", lambda: None)
    vazia = pacotes.Contexto(state={"active_profile": "regua"},
                             mesa=[], conectados=[], estados={})

    blocos = a07.pacote(vazia).get("blocos") or {}
    assert SELETOR_DA_FITA not in blocos, (
        f"com a mesa VAZIA esta aba voltou a escrever a fita — segundo dono, e "
        f"o que ela escreve é `Selecionar:` sobre nada:\n{blocos[SELETOR_DA_FITA]}")

    fita = hefesto_vivo._fita([], "07-lancadores.html")
    assert 'class="fita' in fita, "o piloto se calou com a mesa vazia"
    assert "Selecionar" not in fita and "Todos" not in fita, fita
    for nome in _colorways():
        assert nome not in fita, (
            f"a fita da mesa VAZIA nomeia {nome!r} — o desenho voltou a mandar "
            f"na tela do produto:\n{fita}")


def test_a_bancada_da_07_nao_tem_identidade_congelada() -> None:
    """A régua da aba, na bancada: ZERO."""
    sem_prosa = re.sub(r"<!--.*?-->|/\*.*?\*/", " ", _bancada(), flags=re.S)
    achados = [c for c in _colorways() if c in sem_prosa]
    assert not achados, (
        f"{len(achados)} nome(s) de colorway na `{PAGINA}` — {achados}. A "
        f"identidade do controle vem do APARELHO; um nome de modelo escrito na "
        f"página é o desenho mandando na tela do produto.")
    assert "--plastico:" not in sem_prosa, (
        "voltou um `--plastico:` cravado à página. A cor do plástico é leitura "
        "de aparelho — quem a escreve é o pacote, nunca o gerador.")


def test_a_fita_da_bancada_so_tem_estrutura() -> None:
    """O que sobra na fita do disco é `Selecionar:` e `Todos`."""
    bloco = re.search(r'<div class="fita(?: inerte)?".*?</div>', _bancada(), re.S)
    assert bloco, "não achei a fita na página — a régua ficaria verde sobre nada"
    chips = _chips(bloco.group(0))
    assert len(chips) == 1 and "Todos" in chips[0], (
        f"a fita da bancada tem {len(chips)} chip(s), e só o `Todos` é "
        f"estrutura. Os outros nomeiam controle que esta página não conhece:\n"
        f"{bloco.group(0)}")
    assert "Selecionar:" in bloco.group(0), (
        "a fita perdeu o rótulo `Selecionar:` — ele é do desenho dela e não "
        "tem nada com identidade de aparelho")
