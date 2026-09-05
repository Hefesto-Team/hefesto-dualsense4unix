#!/usr/bin/env python3
"""A IDENTIDADE DA ABA 08 VEM DA MESA, nunca do mockup.

**03/09/2026, `IDENTIDADE-VEM-DE-CIMA-01`.** A lei é dela:

    "se no topo tá mostrando controle white player 1, então cada aba vai usar
    os controles lá de cima. Não mistura com a info dos mockups."

A `mockup/08-conexoes.html` tinha **15 valores de identidade congelados**, e o
que os punha na tela dela era simples: ninguém os reescrevia. Com o White no
cabo e o Galactic Purple no rádio, a Gestão de Controles dizia
`Sony · Player 1 · Cosmic Red · USB`.

O QUE ESTA RÉGUA TRAVA, e são as duas metades — porque o conserto tem duas e
**dar endereço não é entregar**:

    (a) a BANCADA tem endereço      `check_identidade_vem_de_cima --bancada`
                                    devolve zero para a 08
    (b) o PACOTE ESCREVE            `pacote()` emite `nome` e `plastico` por
                                    controle, com o que leu da mesa

A metade (b) é a que impede a maquiagem. Um `data-campo` sem ninguém escrevendo
nele zera a régua (a) e deixa a tela mentindo igual — seria trocar um congelado
por um vazio. Foi MEDIDO em 03/09: com a linha `"nome"` comentada no pacote, a
régua de identidade continua em ZERO e a foto mostra `Cosmic Red` de volta.

E A TERCEIRA COISA QUE ELA TRAVA É A REGRA DELA: **campo sem informação não
mostra nada.** Pelo rádio o Hefesto ainda não pergunta a cor
(`ONDA-CONEXOES-11`), e a mesa responde `COR_DESCONHECIDA`. Nem "Não sei" na
tela, nem a cor do desenho: o pedaço do rótulo SOME e a barra fica vazia.

A MORDIDA: tire o `data-campo="nome"` do `aba08.py` e regenere — `sem_congelado`
reprova. Comente a linha `"nome"` do `pacote()` — `o_pacote_escreve_o_rotulo`
reprova, e a de identidade continua VERDE, que é a prova de que as duas se
precisam.
"""
from __future__ import annotations

import pathlib
import re
import subprocess
import sys
from typing import Any

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(RAIZ / "src/hefesto_dualsense4unix/interface"))

BANCADA = RAIZ / "mockup/08-conexoes.html"
REGUA = RAIZ / "scripts/check_identidade_vem_de_cima.py"


def _pacote() -> Any:
    from hefesto_dualsense4unix.interface.pacotes import a08_conexoes

    return a08_conexoes


# ---------------------------------------------------------------------------
# (a) A BANCADA — nenhum valor de identidade congelado sem endereço
# ---------------------------------------------------------------------------
@pytest.mark.skipif(not REGUA.exists(), reason="a régua de identidade não está nesta árvore")
def test_sem_congelado_na_bancada_da_08() -> None:
    """A régua da sprint, chamada como a sprint manda, tem de devolver zero."""
    saida = subprocess.run(
        [sys.executable, str(REGUA), "--bancada", "--aba", "08"],
        capture_output=True, text=True, cwd=str(RAIZ), check=False)
    assert saida.returncode == 0, (
        "a `08-conexoes` voltou a ter identidade congelada na bancada:\n"
        + saida.stdout + saida.stderr)


def test_os_enderecos_da_identidade_existem_na_bancada() -> None:
    """Os quatro endereços desta cura, no arquivo que o produto vai renderizar.

    SÃO QUATRO E NÃO UM: `nome` e `plastico` são POR CONTROLE; `regua-do-radio`
    e `aparelhos` são blocos que se trocam inteiros porque o número de filhos
    deles muda com a mesa dela. O `fita-chip` é o quinto e mora na fita, que é
    das dez abas — ver `test_os_chips_da_fita_tem_endereco`.
    """
    html = BANCADA.read_text(encoding="utf-8")
    for endereco in ('data-campo="nome" data-hef-alvo="html"',
                     'data-campo="plastico" data-hef-alvo="cor"',
                     'data-campo="regua-do-radio" data-hef-alvo="html"',
                     'data-campo="aparelhos" data-hef-alvo="html"'):
        assert endereco in html, (
            f"o endereço `{endereco}` sumiu da bancada da 08 — sem ele o produto "
            f"não tem onde escrever, e a tela volta ao desenho")


def test_os_chips_da_fita_tem_endereco() -> None:
    """Todo chip de plástico da fita tem endereço, e nenhum sobra sem.

    A fita é reescrita INTEIRA pelo piloto (`hefesto_vivo._fita` →
    `f.outerHTML = p.fita`), com a mesa viva. O endereço é o que faz as duas
    réguas desta casa enxergarem isso: um campo que SOME da tela porque o bloco
    foi trocado é PRODUTO por definição na `regua_do_mockup`.

    ELE MEDE A TAG, E NÃO A ORDEM DOS ATRIBUTOS — corrigido em 03/09/2026, e é
    a forma de defeito que esta casa já nomeou onze vezes: *a régua digita o
    que devia LER*. A versão anterior procurava a fatia literal
    `data-campo="fita-chip" class="chip plastico`, que só casa se o endereço
    vier ANTES da classe. Nesse dia o `aba08.py` deixou de remendar o atributo
    (o `monta.fita()` já o emitia, e os dois juntos duplicavam o `data-campo`),
    a ordem passou a ser `class` → `data-campo`, e este teste reprovou a fita
    que estava CERTA. Para o HTML as duas ordens são o mesmo elemento.
    """
    html = BANCADA.read_text(encoding="utf-8")
    # As tags de abertura de cada chip de plástico, inteiras.
    tags = re.findall(r"<label[^>]*\bclass=\"chip plastico[^>]*>", html)
    endereçados = [t for t in tags if 'data-campo="fita-chip"' in t]
    assert tags and len(tags) == len(endereçados), (
        f"a fita da 08 tem {len(tags)} chips de plástico e "
        f"{len(endereçados)} com endereço")
    # E NENHUM COM O ENDEREÇO DUAS VEZES: com o remendo do gerador vivo ao lado
    # do `monta.fita()`, cada chip saía com `data-campo` duplicado. O navegador
    # fica com o primeiro e a tela não muda — mas o arquivo gerado deixa de ser
    # o arquivo publicado, calado.
    for t in tags:
        assert t.count('data-campo="fita-chip"') == 1, (
            f"um chip da fita traz o endereço mais de uma vez: {t}")


# ---------------------------------------------------------------------------
# (b) O PACOTE ESCREVE — e é esta metade que impede a maquiagem
# ---------------------------------------------------------------------------
def _ctx(cor_do_p2: str = "galactic-purple") -> Any:
    """Uma mesa de dois: um no cabo com cor lida, um no rádio (cor variável)."""
    from hefesto_dualsense4unix.interface.pacotes import Contexto

    # A FAIXA SINTÉTICA DA CASA — há dois portões de anonimato nesta árvore.
    p1, p2 = "aa:bb:cc:00:00:01", "aa:bb:cc:00:00:02"
    mesa = [
        {"pref": "p1", "uniq": p1, "jogador": 1, "cor": "white",
         "nome": "White", "via": "USB", "transporte": "usb", "mascara": "DualSense"},
        {"pref": "p2", "uniq": p2, "jogador": 2, "cor": cor_do_p2,
         "nome": "Galactic Purple" if cor_do_p2 else "Não sei",
         "via": "BT", "transporte": "bt", "mascara": "DualSense"},
    ]
    conectados = [
        {"uniq": p1, "transport": "usb", "connected": True, "battery_pct": 100},
        {"uniq": p2, "transport": "bt", "connected": True, "battery_pct": 64},
    ]
    return Contexto(state={"controllers": conectados}, mesa=mesa,
                    conectados=conectados, estados={})


def test_o_pacote_escreve_o_rotulo_da_mesa() -> None:
    """O rótulo de cada linha vem da MESA, e nomeia o controle que está lá."""
    pac = _pacote().pacote(_ctx())
    nomes = [c.get("nome", "") for c in pac["colunas"].values()]
    assert any("White" in n for n in nomes), (
        f"o pacote não escreveu o White da mesa — escreveu {nomes!r}")
    assert any("Galactic Purple" in n for n in nomes)
    for n in nomes:
        for do_desenho in ("Cosmic Red", "Starlight Blue"):
            assert do_desenho not in n, (
                f"o pacote escreveu `{do_desenho}`, que é do MOCKUP e não da mesa")


def test_o_pacote_escreve_a_cor_do_plastico() -> None:
    """A barra da linha recebe o hex do MAPA, e nunca um hex digitado."""
    import monta

    pac = _pacote().pacote(_ctx())
    cores = [c.get("plastico", "") for c in pac["colunas"].values()]
    assert monta.cor_da_zona("white") in cores, (
        f"o pacote não escreveu a cor do White — escreveu {cores!r}")
    assert monta.cor_da_zona("galactic-purple") in cores


def test_sem_cor_lida_nao_se_inventa_nem_se_escreve_nao_sei() -> None:
    """Regra dela: campo sem informação NÃO MOSTRA NADA.

    Pelo rádio a cor ainda não é perguntada. O pedaço do rótulo some, a barra
    fica vazia — e a palavra interna `COR_DESCONHECIDA` ("Não sei") não vaza
    para a tela em lugar nenhum do pacote.
    """
    pac = _pacote().pacote(_ctx(cor_do_p2=""))
    do_radio = [c for c in pac["colunas"].values() if c.get("via") == "BT"]
    assert do_radio, "a mesa de prova perdeu o controle de rádio"
    for c in do_radio:
        assert c["plastico"] == "", (
            f"sem cor lida a barra recebeu {c['plastico']!r} — isso é inventar")
        assert "Não sei" not in c["nome"], (
            f"a palavra interna da mesa vazou para a tela: {c['nome']!r}")
        for do_desenho in ("Cosmic Red", "Starlight Blue", "Galactic Purple"):
            assert do_desenho not in c["nome"]
    inteiro = c["nome"] + str(pac.get("regua-do-radio") or "")
    assert "Não sei" not in inteiro, (
        "`Não sei` apareceu na régua do rádio — foi o vazamento medido em 03/09, "
        "no `title` da fatia: *'Não sei — 260,4 turnos de entrada'*")


def test_a_regua_do_radio_e_um_bloco_e_nomeia_quem_esta_na_mesa() -> None:
    """A régua de Desempenho nasce do produto, com os controles da mesa.

    ELA É UM BLOCO e não um campo por vez porque o `title` de cada fatia nomeia
    o plástico — e `title` não tem alvo no `escrever()` do piloto.
    """
    html = str(_pacote().pacote(_ctx()).get("regua-do-radio") or "")
    assert 'class="pista"' in html and 'class="leg"' in html, (
        "a régua do rádio saiu sem pista ou sem legenda")
    assert "Galactic Purple" in html, (
        "a régua do rádio não nomeou o controle que está NO rádio")
    for do_desenho in ("Cosmic Red", "Starlight Blue"):
        assert do_desenho not in html, (
            f"a régua do rádio trouxe `{do_desenho}`, que é do desenho")


def test_o_rotulo_tem_um_dono_so() -> None:
    """O gerador e o pacote escrevem o MESMO rótulo, porque é a mesma função.

    Enquanto eram duas escritas, o desenho e o produto podiam divergir sem que
    ninguém visse — o defeito que a `novo-layout/` já cobrou 25 KB.

    LIDO NO FONTE, e nunca por `import aba08`: o gerador **roda ao ser
    importado** (ele é um script — `monta(...)` e `onde.gravar(...)` moram no
    topo do módulo), e um teste que o importasse REESCREVERIA a bancada dela.
    """
    fonte = (RAIZ / "src/hefesto_dualsense4unix/interface/aba08.py").read_text(
        encoding="utf-8")
    for linha in ("rotulo = _pacote08.rotulo_do_controle",
                  "tinta_legivel = _pacote08.tinta_legivel"):
        assert linha in fonte, (
            f"`{linha}` sumiu do gerador — o rótulo do plástico voltou a ter "
            f"duas escritas, e duas escritas divergem caladas")
    assert "def rotulo(" not in fonte, (
        "o gerador voltou a definir o próprio `rotulo` ao lado do do pacote")
