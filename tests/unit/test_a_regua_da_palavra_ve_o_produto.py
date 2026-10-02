"""A régua da palavra passou a ver O PRODUTO — e a bancada continua vendo tudo."""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

from hefesto_dualsense4unix.interface.folha_da_casa import (
    FOLHA_DA_CASA,
    seletores_escondidos,
)
from hefesto_dualsense4unix.interface.frases_que_ela_baniu import (
    palavra_banida_em,
    texto_visivel,
    texto_visivel_no_produto,
)

RAIZ = Path(__file__).resolve().parents[2]
INTERFACE = RAIZ / "src" / "hefesto_dualsense4unix" / "interface"
BANCADA = RAIZ / "mockup"
PRODUTO = INTERFACE / "paginas"  # (noqa-acento) nome de pasta

PAGINA = (
    '<style>/* <div class="nota">isto é comentário</div> a mesa */</style>\n'
    '<div class="rodape">\n'
    '  <div class="nota curta"><p>quatro na mesa</p>\n'
    '    <div><span>e a mesa inteira</span></div>\n'
    '  </div>\n'
    '</div>\n'
    '<p title="a dica fica">o texto do produto</p>\n'
)


def _paginas(pasta: Path) -> list[Path]:
    achadas = sorted(pasta.glob("??-*.html"))
    assert len(achadas) == 10, (
        f"achei {len(achadas)} abas em {pasta} e o produto tem dez — régua que "
        "não acha a tela não mede a tela."
    )
    return achadas


def _regras_da_folha(folha: str) -> list[tuple[str, str]]:
    """A folha partida em `(seletor, declarações)`, por uma leitura PRÓPRIA."""
    fora: list[tuple[str, str]] = []
    for pedaco in folha.split("}"):
        if "{" not in pedaco:
            continue
        seletor, _, declaracoes = pedaco.partition("{")
        fora.append((seletor.strip(), declaracoes))
    return fora


_ESCONDE = re.compile(
    r"(?:^|;)\s*display\s*:\s*none\s*(?:!important)?\s*(?:;|$)", re.IGNORECASE
)


def test_a_folha_diz_o_que_esconde_e_a_regua_le_dela() -> None:
    """`.nota` não se digita na régua: ele sai da folha do produto."""
    escondidos = seletores_escondidos()
    assert escondidos == seletores_escondidos(FOLHA_DA_CASA), (
        "a folha padrão e a mesma folha passada à mão deram listas diferentes "
        "— o valor que a régua lê não é o que o piloto põe na tela."
    )

    assert ".nota" in escondidos, (
        "`.nota` saiu da lista de esconder — a leitura do PRODUTO volta a "
        f"contar o bilhete de projeto. A folha diz: {escondidos}"
    )
    assert "select" not in escondidos, (
        "a régua caiu no `appearance:none` e vai apagar os 117 `<select>` das "
        "dez abas da leitura do produto."
    )

    esconde_de_verdade = tuple(
        seletor
        for seletor, declaracoes in _regras_da_folha(FOLHA_DA_CASA)
        if _ESCONDE.search(declaracoes)
    )
    assert escondidos == esconde_de_verdade, (
        "a lista de esconder não bate com o que a folha declara:\n"
        f"  a função devolve: {escondidos}\n"
        f"  a folha esconde:  {esconde_de_verdade}"
    )

    assert "appearance" in FOLHA_DA_CASA, (
        "a folha perdeu a cura do `<select>` — esta régua mede a lista de "
        "esconder e a armadilha dela é justamente o `appearance:none`."
    )


def test_a_folha_tem_um_dono_so_em_src_inteiro() -> None:
    """Uma folha só. Duas divergiriam, e a régua leria a que não está na tela."""
    src = RAIZ / "src" / "hefesto_dualsense4unix"
    donos = []
    for modulo in sorted(src.rglob("*.py")):
        if "__pycache__" in modulo.parts:
            continue
        for no in ast.walk(ast.parse(modulo.read_text(encoding="utf-8"))):
            if not isinstance(no, (ast.Assign, ast.AnnAssign)):
                continue
            alvos = no.targets if isinstance(no, ast.Assign) else [no.target]
            if any(
                isinstance(a, ast.Name) and a.id == "FOLHA_DA_CASA" for a in alvos
            ):
                donos.append(f"{modulo.relative_to(RAIZ)}:{no.lineno}")
    assert len(donos) == 1, (
        "a FOLHA_DA_CASA tem de ter UM dono e tem "
        f"{len(donos)} — a janela põe uma na tela e a régua lê a outra: {donos}"
    )
    assert donos[0].startswith(
        "src/hefesto_dualsense4unix/interface/folha_da_casa.py:"
    ), (
        "a folha mudou de casa e ninguém avisou esta régua nem o docstring do "
        f"módulo: {donos[0]}"
    )
    assert FOLHA_DA_CASA.startswith(".nota{display:none"), (
        "o valor importado não é a folha — o dono achado não é o dono lido."
    )


def test_uma_segunda_regra_de_esconder_vale_para_a_regua_sozinha() -> None:
    """O que a cura promete ao futuro: a régua acompanha a folha sem tocar nela."""
    folha = (
        ".nota{display:none !important}"
        "#rodape{display : NONE}"
        "aviso{color:red;display:none}"
        "select{appearance:none}"
    )
    assert seletores_escondidos(folha) == (".nota", "#rodape", "aviso")


def test_o_seletor_que_a_regua_nao_sabe_honrar_e_recusado_em_voz_alta() -> None:
    """Ignorar em silêncio é voltar ao defeito de origem, e é pior."""
    for seletor in (".nota > p", ".rodape .nota", "div.nota", "*", "[hidden]"):
        with pytest.raises(ValueError, match="ENSINE A RÉGUA"):
            seletores_escondidos(seletor + "{display:none}")
    assert seletores_escondidos(".nota,{display:none}") == (".nota",)


def test_o_produto_esconde_o_bilhete_e_a_bancada_o_conta() -> None:
    """A mesma página, duas respostas — e as duas certas."""
    bancada = texto_visivel(PAGINA)
    produto = texto_visivel_no_produto(PAGINA)

    assert palavra_banida_em(bancada) == "mesa", (
        "a BANCADA deixou de contar o bilhete. Ela é o desenho que ela abre "
        "CRU no navegador — ali a `.nota` é texto de verdade, e uma régua que "
        "a ignore deixa a palavra voltar pelo desenho."
    )
    assert palavra_banida_em(produto) is None, (
        "a leitura do PRODUTO ainda conta a `.nota`, que a folha do piloto "
        "apaga antes de a página aparecer. É o defeito de origem, de volta."
    )
    assert "o texto do produto" in produto, "sumiu o texto que fica AO LADO"
    assert "a dica fica" in produto, (
        "a dica do `title` some com o bilhete — e ela é onde o glossário diz "
        "que a explicação mora."
    )


def test_as_duas_leituras_devolvem_o_tamanho_da_pagina() -> None:
    """Byte a byte com a entrada, senão a linha reportada é a de outro lugar."""
    for lida in (texto_visivel(PAGINA), texto_visivel_no_produto(PAGINA)):
        assert len(lida) == len(PAGINA)
        assert lida.count("\n") == PAGINA.count("\n")


def test_o_bilhete_nao_fecha_e_a_regua_diz_em_vez_de_chutar() -> None:
    """`<div class="nota">` sem `</div>` apagaria o resto do arquivo."""
    with pytest.raises(ValueError, match="nunca fechado"):
        texto_visivel_no_produto('<div class="nota"><p>a mesa</p>\n')


def test_a_leitura_do_produto_nao_apaga_a_tela() -> None:
    """A régua que zera por apagar tudo passa em qualquer proibição."""
    magros: list[str] = []
    for pagina in _paginas(PRODUTO):
        lida = texto_visivel_no_produto(pagina.read_text(encoding="utf-8"))
        letras = len(lida.split())
        if letras < 200 or "Hefesto" not in lida:
            magros.append(f"{pagina.name}: {letras} palavras lidas")
    assert not magros, (
        "a leitura do PRODUTO ficou vazia nestas páginas — a régua deixou de "
        "medir a tela e passou a medir o próprio apagão:\n  " + "\n  ".join(magros)
    )


def test_a_bancada_continua_lendo_o_que_o_produto_esconde() -> None:
    """O bilhete é a maior parte do texto do desenho, e ele tem de contar."""
    iguais: list[str] = []
    for pagina in _paginas(BANCADA):
        cru = pagina.read_text(encoding="utf-8")
        so_no_desenho = len(texto_visivel(cru).split()) - len(
            texto_visivel_no_produto(cru).split()
        )
        if so_no_desenho < 100:
            iguais.append(f"{pagina.name}: só {so_no_desenho} palavras a mais")
    assert not iguais, (
        "a leitura da BANCADA deixou de ver o bilhete de projeto — as duas "
        "leituras viraram uma só, e o desenho ficou sem régua:\n  "
        + "\n  ".join(iguais)
    )
