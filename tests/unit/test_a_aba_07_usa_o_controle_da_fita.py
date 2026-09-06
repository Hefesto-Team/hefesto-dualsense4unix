#!/usr/bin/env python3
"""A ABA 07 USA O CONTROLE DA MESA, e a mesa lê do APARELHO.

A LEI, e ela é dela (03/09/2026):

    "se no topo tá mostrando controle white player 1, então cada aba vai usar
    os controles lá de cima. Não mistura com a info dos mockups. Cada feature
    faz referencia ao controle conectado.   <!-- noqa-acento: citação dela -->
    Por isso temos o mapa pra servir como variável de identificação"

O QUE ESTAVA NA TELA, medido em 03/09/2026 com os DOIS controles dela na mesa
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
   sabe nada dos controles dela, e a regra é a dela — *campo sem informação não
   mostra nada*. Fica o `Selecionar:` e o chip `Todos`, que são ESTRUTURA;
2. o PACOTE escreve os chips com a mesa VIVA, por `blocos[".fita"]`. **Sem esta
   metade, a primeira seria maquiagem**: zeraria a régua e deixaria a fita vazia.

A MORDIDA, medida em 03/09/2026: comentar o `onde.gravar(...)` do `aba07.py` e
regerar devolve os SEIS congelados à régua e faz a régua do próprio gerador
reprovar nomeando `['Cosmic Red', 'Starlight Blue']`. Devolvida a linha, zero.

O QUE ESTES CASOS NÃO COBREM, de propósito: o número do jogador. `P1`…`P4` são a
POSIÇÃO na mesa, não a identidade do aparelho — *"O p1 ou p2 reflete o player do
jogador."*

O QUE FICA DE FORA DESTA ABA, e está relatado: `hefesto_vivo._fita` e
`monta.fita` são das DEZ páginas, e a desistência descrita acima continua lá.
Esta aba não pode consertá-la sem tocar arquivo de todo mundo.
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

#: Uma mesa de MENTIRA com o defeito que ela viu: um controle lido inteiro (o do
#: cabo) e um cujo plástico o leitor não conhece (o do rádio). É o estado REAL
#: desta máquina — `LeitorDeCor.conhecidos()` devolveu zero para o controle de
#: rádio em 03/09/2026 — e é o único estado em que o defeito aparece.
#:
#: As chaves são as de `mesa_viva.mesa_do_estado`, que é quem monta a mesa viva.
def _palavra(transporte: str) -> str:
    """A palavra do transporte PERGUNTADA À DONA — nunca digitada aqui.

    ONDA4-S10, 06/09/2026. Estas asserções diziam `"USB"` e `"BT"`, e por isso
    reprovaram a decisão dela (D-05: *"cabo / rádio, pela função que já
    existe"*) em vez do defeito. É a forma que esta casa já pegou onze vezes: a
    régua DIGITAVA o que devia LER. Com a pergunta à dona, ela continua
    mordendo o chip que perde o transporte — e passa a morder também o chip que
    inventa uma palavra que a dona não disse.
    """
    from hefesto_dualsense4unix.app.actions.home_actions import palavra_do_transporte

    return palavra_do_transporte(transporte)


MESA_COM_UM_SEM_COR = [
    {"pref": "p1", "jogador": 1, "cor": "white", "nome": "White",
     "via": "USB", "transporte": "usb", "alvo": True},
    {"pref": "p2", "jogador": 2, "cor": "", "nome": "Não sei",
     "via": "BT", "transporte": "bt", "alvo": False},
]


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
    """A página da BANCADA — o desenho de HOJE, não o congelado.

    Apontar para o publicado daria **verde sobre a página congelada**, que é a
    armadilha mais cara do `COMO-OLHAR-A-TELA.md`. Publicar é ato dela; enquanto
    ela não publicar, o publicado é a página com os dois chips do mockup.
    """
    from hefesto_dualsense4unix.interface import onde

    caminho = onde.pagina(PAGINA)
    if not caminho.exists():
        pytest.fail(f"{caminho} não existe — a régua mediria o vazio.")
    return caminho.read_text(encoding="utf-8")


def _colorways() -> list[str]:
    """Os 28 nomes, lidos do CSV que é dono deles.

    Digitá-los aqui criaria a segunda lista que o `cores-do-dualsense.csv`
    existe para não ter — e ela envelheceria calada no dia em que o desenho
    trocasse de controle de exemplo. É a mesma leitura que
    `scripts/check_identidade_vem_de_cima.nomes_de_colorway` faz.
    """
    bruto = (RAIZ / "docs/data/cores-do-dualsense.csv").read_text(encoding="utf-8")
    linhas = [ln for ln in bruto.splitlines()
              if ln.strip() and not ln.lstrip().startswith("#")]
    nomes = {(ln.get("nome") or "").strip() for ln in csv.DictReader(linhas)}
    return sorted(n for n in nomes if len(n) >= 4)


def _chips(html: str) -> list[str]:
    """Os `<label class="chip …">` da fita, um por elemento, na ordem.

    POR FATIA E NÃO POR REGEX: o chip tem `<span class="pt">•</span>` DENTRO, e
    um `.*?</span>` fecha no filho — a primeira versão deste ajudante perdia o
    último chip e o caso passava medindo dois onde há três. Fatiar pelo começo
    do próximo chip não tem esse buraco, e `class="pt"` não colide com
    `class="chip`.
    """
    partes = html.split('<label class="chip')[1:]
    return ['<label class="chip' + p for p in partes]


# ---------------------------------------------------------------------------
# 1. O PACOTE — quem escreve a fita desta aba
# ---------------------------------------------------------------------------
def test_o_chip_sem_cor_lida_nao_inventa_cor(a07) -> None:
    """Regra dela: campo sem informação NÃO MOSTRA NADA.

    O chip do rádio, cuja cor não foi lida, mostra o que a leitura TROUXE — o
    jogador e o transporte — e cala sobre o que ela não trouxe. Sem isto o
    caminho fácil é o travessão, o `Não sei` cru ou, pior, o nome do mockup.
    """
    chips = _chips(a07.fita_html(MESA_COM_UM_SEM_COR))
    assert len(chips) == 3, (
        f"esperava `Todos` + dois controles, saíram {len(chips)}. Uma fita que "
        f"perde chip esconde controle da mesa dela.")

    do_radio = chips[2]
    assert "--plastico" not in do_radio, (
        f"o chip do controle SEM cor lida trouxe `--plastico`. Inventar a cor "
        f"do plástico é a lei de 03/09 ao contrário:\n{do_radio}")
    assert a07.SEM_LEITURA_DE_COR not in do_radio, (
        f"o chip escreveu {a07.SEM_LEITURA_DE_COR!r} na tela. `mesa_do_estado` "
        f"usa esse texto quando o leitor não conhece a peça — ele é a AUSÊNCIA "
        f"de leitura, e a regra dela é não mostrar nada:\n{do_radio}")
    assert "P2" in do_radio and _palavra("bt") in do_radio, (
        f"o chip perdeu o jogador ou o transporte, que a leitura TROUXE. Calar "
        f"sobre o que se sabe é o defeito oposto, e igualmente caro:\n{do_radio}")


def test_o_chip_com_cor_lida_diz_o_modelo(a07) -> None:
    """A outra metade: o que FOI lido aparece.

    Sem este caso, apagar tudo passaria — e um chip que nunca nomeia controle
    nenhum zera a régua do mesmo jeito que a página vazia zeraria.
    """
    do_cabo = _chips(a07.fita_html(MESA_COM_UM_SEM_COR))[1]
    assert "White" in do_cabo, (
        f"o modelo LIDO do aparelho não chegou ao chip:\n{do_cabo}")
    assert "P1" in do_cabo and _palavra("usb") in do_cabo, (
        f"o chip do cabo perdeu o jogador ou o transporte:\n{do_cabo}")


def test_a_fita_nao_cai_de_volta_no_desenho(a07) -> None:
    """Nenhum dos nomes do mapa entra na fita sem ter vindo da LEITURA.

    É a régua que pega o contorno mais provável — cair de volta em
    `monta.CONECTADOS` quando a leitura falha. `Cosmic Red` e `Starlight Blue`
    são o desenho, e é exatamente isso que ela viu na tela.
    """
    saiu = a07.fita_html(MESA_COM_UM_SEM_COR)
    lidos = {str(c["nome"]) for c in MESA_COM_UM_SEM_COR if c["cor"]}
    for nome in _colorways():
        if nome in lidos:
            continue
        assert nome not in saiu, (
            f"a fita trouxe {nome!r}, e ele NÃO saiu da leitura "
            f"(lidos: {sorted(lidos)}). O caminho de volta ao mockup está "
            f"aberto:\n{saiu}")


def test_a_fita_nunca_volta_vazia(a07) -> None:
    """Mesa vazia ainda tem rótulo e `Todos`.

    O piloto troca o bloco por `innerHTML` — devolver `""` aqui APAGARIA o
    `Selecionar:` da tela dela, que é estrutura e não identidade.
    """
    saiu = a07.fita_html([])
    assert "Selecionar:" in saiu, f"a fita vazia perdeu o rótulo:\n{saiu}"
    assert len(_chips(saiu)) == 1, (
        f"a mesa vazia produziu chip de controle. Sem controle na mesa não há "
        f"quem nomear:\n{saiu}")


def test_o_pacote_escreve_a_fita(a07, ctx, monkeypatch) -> None:
    """A metade que separa o conserto da maquiagem: alguém ESCREVE.

    Um endereço (ou, aqui, um bloco) que ninguém escreve zera a régua e deixa a
    tela igualmente mentindo — seria trocar um congelado por um vazio.

    A VIGIA VAI DUBLADA: sem isso `pacote()` dispara a thread que lê o disco
    dela, e uma régua que acorda o disco de outra é ruído (medido em 02/09/2026
    no arquivo irmão).
    """
    monkeypatch.setattr(a07.VIGIA, "agora", lambda: None)

    # 1. o seletor tem de EXISTIR na página, senão o bloco é escrito no nada
    assert 'class="fita' in _bancada(), (
        f"a página não tem `{a07.SELETOR_DA_FITA}` — o `blocos` cairia no chão, "
        f"e `querySelector` devolve `null` sem uma linha de erro")

    fita = (a07.pacote(ctx).get("blocos") or {}).get(a07.SELETOR_DA_FITA)
    assert fita, (
        "o pacote não manda a fita. Sem ela a tira do topo desta aba fica com o "
        "que o gerador deixou, e o gerador não sabe quais controles estão aqui.")
    assert "White" in fita, (
        f"a fita que o pacote manda não traz o controle da mesa:\n{fita}")


# ---------------------------------------------------------------------------
# 2. A BANCADA — a `07-lancadores` no disco
# ---------------------------------------------------------------------------
def test_a_bancada_da_07_nao_tem_identidade_congelada() -> None:
    """A régua da aba, na bancada: ZERO.

    Ela repete aqui a regra de `scripts/check_identidade_vem_de_cima.py` porque
    aquele script mede as DEZ e este arquivo responde por UMA — e porque um
    portão que ainda não está na lista dos trinta não guarda nada sozinho.

    COMENTÁRIO NÃO CONTA, e é a mesma isenção do script: `<!-- -->` e `/* */`
    são prosa, e contá-los inflaria o número. Número inflado é a coisa que esta
    casa mais derruba.
    """
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
    """O que sobra na fita do disco é `Selecionar:` e `Todos`.

    O caso irmão acima passaria com a fita cheia de chips genéricos (`P1 • USB`)
    escritos à mão pelo gerador — e eles voltariam a afirmar uma mesa que a
    página estática não conhece. Aqui o que se cobra é a AUSÊNCIA de chip de
    controle: quem os põe é o produto, no tique.
    """
    bloco = re.search(r'<div class="fita.*?</div>', _bancada(), re.S)
    assert bloco, "não achei a fita na página — a régua ficaria verde sobre nada"
    chips = _chips(bloco.group(0))
    assert len(chips) == 1 and "Todos" in chips[0], (
        f"a fita da bancada tem {len(chips)} chip(s), e só o `Todos` é "
        f"estrutura. Os outros nomeiam controle que esta página não conhece:\n"
        f"{bloco.group(0)}")
    assert "Selecionar:" in bloco.group(0), (
        "a fita perdeu o rótulo `Selecionar:` — ele é do desenho dela e não "
        "tem nada com identidade de aparelho")
