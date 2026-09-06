"""A régua da palavra passou a ver O PRODUTO — e a bancada continua vendo tudo.

O DEFEITO, medido em 06/09/2026 e curado no mesmo dia:

    interface/olhar.py --palavra mesa --publicado
    →  'mesa': 34 ocorrência(s) visível(eis) em o produto

E o produto não mostrava NENHUMA das 34. Elas moram dentro de `.nota` — o
bilhete de projeto que o mockup carrega —, e o piloto injeta
`.nota{display:none !important}` na página antes de ela aparecer
(`interface/folha_da_casa.FOLHA_DA_CASA`). Medido num Chrome de verdade, `file://`
sobre `interface/paginas/`, viewport 1180x777, com a folha posta: **zero** nas
dez páginas. O instrumento respondia sobre o ARQUIVO e dizia "o produto".

É a assinatura que esta casa persegue desde 04/09 — *o instrumento respondia
sobre outra coisa que não o produto* —, e a cura tem a forma que a casa já
escreveu: **o que tem dono, a régua PERGUNTA ao dono**. `.nota` não se digita
uma segunda vez; ele vem de `seletores_escondidos()`, que lê o `display:none`
da folha do piloto.

AS DUAS LEITURAS SÃO DIFERENTES DE PROPÓSITO, e é o ponto inteiro:

* `texto_visivel` — a BANCADA (`mockup/`), que ela abre no navegador CRUA. Ali
  o bilhete é texto de verdade e tem de contar.
* `texto_visivel_no_produto` — a JANELA, com a folha do piloto aplicada.

Uma cura que apagasse a `.nota` nas duas deixaria o desenho sem régua nenhuma,
e a palavra voltaria pela bancada sem nada reprovar.
"""

from __future__ import annotations

import ast
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

#: Uma página de mentira com as três armadilhas juntas: o comentário de CSS que
#: CITA a marcação escondida, o `<div>` dentro do `<div>` escondido, e o texto
#: que fica ao lado e não pode sumir junto.
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


# ---------------------------------------------------------------------------
# 1. O DONO DA FOLHA — e a régua perguntando a ele
# ---------------------------------------------------------------------------
def test_a_folha_diz_o_que_esconde_e_a_regua_le_dela() -> None:
    """`.nota` não se digita na régua: ele sai da folha do produto.

    E A ARMADILHA ESTÁ NA PRÓPRIA FOLHA DE HOJE: `select{appearance:none}` tem
    a palavra `none` e não esconde nada. Um `"none" in regra` — ou um
    `"display:none" in folha`, que erra no outro sentido com um espaço no meio
    — daria a lista errada, e a régua apagaria os 117 `<select>` das dez abas.
    """
    assert seletores_escondidos() == (".nota",)
    assert seletores_escondidos(FOLHA_DA_CASA) == (".nota",)
    assert "appearance" in FOLHA_DA_CASA, (
        "a folha perdeu a cura do `<select>` — esta régua mede a lista de "
        "esconder e a armadilha dela é justamente o `appearance:none`."
    )


def test_a_folha_tem_um_dono_so_em_src_inteiro() -> None:
    """Uma folha só. Duas divergiriam, e a régua leria a que não está na tela.

    A régua ANDA PELA ÁRVORE de todo módulo de `src/` e conta as ATRIBUIÇÕES do
    nome: quem reexporta (`from … import FOLHA_DA_CASA`) não atribui, e quem
    escreve uma segunda folha atribui. Um `grep` daria o mesmo número por
    motivos errados — as menções em prosa passam de uma dúzia.

    ELA NÃO IMPORTA A JANELA de propósito. `gui.ponte_da_tela` puxa `gi`, `Gtk`
    e `WebKit2` na primeira linha, e está de saída de `gui/`
    (`D-0609-GTK-LEVA-INTEIRA`): uma régua que a importasse quebraria na
    máquina sem PyGObject e de novo no dia da mudança.
    """
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
    """O que a cura promete ao futuro: a régua acompanha a folha sem tocar nela.

    As três escritas que o CSS aceita para a mesma coisa estão aqui de
    propósito — com `!important`, com espaço em volta do `:` e em maiúscula.
    """
    folha = (
        ".nota{display:none !important}"
        "#rodape{display : NONE}"
        "aviso{color:red;display:none}"
        "select{appearance:none}"
    )
    assert seletores_escondidos(folha) == (".nota", "#rodape", "aviso")


def test_o_seletor_que_a_regua_nao_sabe_honrar_e_recusado_em_voz_alta() -> None:
    """Ignorar em silêncio é voltar ao defeito de origem, e é pior.

    Uma régua que desse de ombros para um `.nota > p` novo continuaria verde
    contando o que o produto esconde — que foi exatamente o estado do mundo até
    hoje. A recusa NOMEIA o seletor.
    """
    for seletor in (".nota > p", ".rodape .nota", "div.nota", "*", "[hidden]"):
        with pytest.raises(ValueError, match="ENSINE A RÉGUA"):
            seletores_escondidos(seletor + "{display:none}")
    # A VÍRGULA SOBRANDO NÃO É SELETOR NOVO — `.nota,{…}` é a mesma regra com
    # um vazio ao lado, e recusá-la seria a régua reprovando digitação.
    assert seletores_escondidos(".nota,{display:none}") == (".nota",)


# ---------------------------------------------------------------------------
# 2. AS DUAS LEITURAS — e a diferença entre elas
# ---------------------------------------------------------------------------
def test_o_produto_esconde_o_bilhete_e_a_bancada_o_conta() -> None:
    """A mesma página, duas respostas — e as duas certas.

    O `<div>` dentro do `<div class="nota">` está aqui porque parar no primeiro
    `</div>` deixaria de fora justamente o miolo, que é onde o texto mora.
    """
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
    """`<div class="nota">` sem `</div>` apagaria o resto do arquivo.

    Um apagão silencioso numa régua é o mesmo defeito que ela veio curar, só
    que ao contrário: ela passaria a dar verde sobre a página inteira.
    """
    with pytest.raises(ValueError, match="nunca fechado"):
        texto_visivel_no_produto('<div class="nota"><p>a mesa</p>\n')


# ---------------------------------------------------------------------------
# 3. SOBRE AS PÁGINAS DE VERDADE — as dez de cada lado
# ---------------------------------------------------------------------------
def test_a_leitura_do_produto_nao_apaga_a_tela() -> None:
    """A régua que zera por apagar tudo passa em qualquer proibição.

    Esta é a guarda contra a cura preguiçosa: se `texto_visivel_no_produto`
    devolvesse espaço, o portão da palavra ficaria verde para sempre e sobre
    nada. Medido em 06/09/2026 nas dez publicadas: a leitura do produto tem
    entre 2.500 e 9.400 letras.
    """
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
    """O bilhete é a maior parte do texto do desenho, e ele tem de contar.

    Medido em 06/09/2026: nas dez páginas da bancada a `.nota` responde por
    milhares de letras cada. Se as duas leituras devolvessem o mesmo, a
    separação teria sido escrita e não feita.
    """
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
