"""A régua da aba 03: a identidade do controle vem da FITA, nunca do mockup.

A LEI, e ela é dela (03/09/2026)::

    "se no topo tá mostrando controle white player 1, então cada aba vai usar
    os controles lá de cima. Não mistura com a info dos mockups. Cada feature
    faz referencia ao controle conectado.   <!-- noqa-acento: citação dela -->
    Por isso temos o mapa pra servir como variável de identificação"

O DEFEITO, na tela dela, com os dois controles na mesa e três centímetros entre
uma coisa e outra::

    fita do topo (lida do APARELHO)   P1 · White · USB   P2 · Galactic Purple · BT
    cabeçalho da coluna (do MOCKUP)   P1 · Cosmic Red · USB   P2 · Starlight Blue · BT

Nenhuma das duas cores do cabeçalho é de um controle dela.

O QUE ESTA RÉGUA MORDE, e os seis já aconteceram nesta casa:

* arrancar o endereço do chip            → `test_todo_chip_da_bancada_tem_endereco`
* o pacote parar de emitir o chip vivo   → `test_o_chip_vivo_e_o_controle_da_mesa`
* inventar cor quando o rádio não a diz  → `test_sem_cor_lida_o_chip_nao_veste_plastico`
* deixar o nome de quem saiu na coluna   → `test_o_lugar_sem_aparelho_perde_o_nome`
* desenho e produto com marcação difer.  → `test_o_desenho_e_o_produto_tem_um_dono_so`
* o chip repintar a cada tique, calado   → `test_o_chip_nao_repinta_a_cada_tique`

**DUAS ESCRITAS SÃO O DEFEITO DE ORIGEM.** É por isso que a última é uma régua e
não um detalhe: enquanto o gerador montava o chip à mão e o pacote montava
outro, os dois podiam divergir sem ninguém ver — e é exatamente a forma do
`novo-layout/` que divergiu 25 KB calada.
"""
from __future__ import annotations

import pathlib
import re
import sys

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
INTERFACE = RAIZ / "src" / "hefesto_dualsense4unix" / "interface"
sys.path.insert(0, str(INTERFACE))

PAGINA = "03-gatilhos.html"

#: As duas cores do DESENHO. Nenhuma delas é de um controle desta bancada, e é
#: por isso que elas servem de agulha: se uma aparecer no que o produto escreve,
#: o mockup voltou a mandar na tela.
DO_MOCKUP = ("Cosmic Red", "Starlight Blue")

#: UM CONTROLE DE MENTIRA, com a forma que o daemon devolve. O MAC é da faixa
#: sintética da casa (`aa:bb:cc`): há dois portões de anonimato nesta árvore.
NO_CABO = {
    "uniq": "aa:bb:cc:00:00:01", "player": 1, "transport": "usb",
    "is_primary": True, "inputs": {"l2_raw": 0, "r2_raw": 0},
}
NO_RADIO = {
    "uniq": "aa:bb:cc:00:00:02", "player": 2, "transport": "bt",
    "is_primary": False, "inputs": {"l2_raw": 0, "r2_raw": 0},
}

#: A MESA DELA DE HOJE: um **White no cabo** e um **por rádio sem cor lida**.
#: O segundo não é hipótese — a leitura de cor pelo rádio ainda não chega, e a
#: mesa nasce com `cor` vazia e `nome` igual a `mesa_viva.COR_DESCONHECIDA`.
MESA_DELA = [
    {"pref": "p1", "jogador": 1, "uniq": NO_CABO["uniq"], "nome": "White",
     "via": "USB", "cor": "white", "mascara": "DualSense", "alvo": True},
    {"pref": "p2", "jogador": 2, "uniq": NO_RADIO["uniq"], "nome": "Não sei",
     "via": "BT", "cor": "", "mascara": "DualSense", "alvo": False},
]

#: A MESA DE UM SÓ. Ela é o caso em que a coluna do P2 fica sem dono — e o
#: cabeçalho dela é o que continuava dizendo `Starlight Blue`.
MESA_DE_UM = [MESA_DELA[0]]


@pytest.fixture(scope="module")
def a03():
    import pacotes  # noqa: F401  (registra os dez)
    from pacotes import a03_gatilhos

    return a03_gatilhos


@pytest.fixture(scope="module")
def bancada() -> str:
    from hefesto_dualsense4unix.interface import onde

    caminho = onde.pagina(PAGINA)
    assert caminho.exists(), f"{PAGINA} sumiu da bancada — não há o que medir"
    return caminho.read_text(encoding="utf-8")


# A ÂNCORA É `class="fita"`, COM AS ASPAS, e não o prefixo `class="fita` —
# 12/09/2026. A ALTURA-DA-VISTA-01 embrulhou a fita numa linha nova
# (`<div class="fita-linha">`, que carrega marca, fita, contagem e perfil
# ativo), e o prefixo passou a casar com o EMBRULHO: o recorte começava no
# `.fita-linha` e terminava no primeiro `</div>` de dentro dele, muito antes
# da fita acabar. O resultado é o pior tipo — a régua parou de pular a fita
# que ela mandava pular, e acusou os chips do esqueleto como se fossem cor
# cravada desta aba. *A régua digitava um prefixo e devia ler o elemento.*
# `monta.fita()` escreve `<div class="fita"` ou `<div class="fita inerte"`,
# e é isso que este padrão casa — nunca um nome de classe que só começa igual.
_A_FITA = re.compile(r'<div class="fita(?: inerte)?"')


def _pacote(a03, mesa, conectados):
    """O pacote inteiro para aquela mesa, com o perfil injetado pela porta.

    O PERFIL VEM PELA PORTA DE CIMA (`perfil.ativo`) e não por um `.json` de
    mentira no disco: o que esta régua mede é a IDENTIDADE do controle na
    coluna, e escrever um arquivo faria a régua medir o leitor de perfis junto.
    """
    from pacotes import Contexto, perfil

    guardado = perfil.ativo
    perfil.ativo = lambda _n: {  # type: ignore[assignment]
        "triggers": {"left": {"mode": "Rigid", "params": []},
                     "right": {"mode": "Rigid", "params": []}},
        "controllers": {}}
    try:
        return a03.pacote(Contexto(state={"active_profile": "régua"}, mesa=mesa,
                                   conectados=conectados, estados={}))
    finally:
        perfil.ativo = guardado  # type: ignore[assignment]


def _depois_da_fita(doc: str) -> int:
    """O ponto do documento em que a FITA DO TOPO acaba.

    A fita é do `monta.fita()`, que é o esqueleto das DEZ páginas — território
    de ninguém nesta leva, e por isso fora do alcance desta régua. O corte é
    aqui, com nome e razão, e não um `if` escondido no laço: **isenção sem razão
    é ponto cego com nome bonito.**
    """
    achou = _A_FITA.search(doc)
    assert achou, "a fita do esqueleto sumiu da página"
    return doc.index("</div>", achou.start()) + len("</div>")


def _chips(a03, r, mesa) -> dict[str, str]:
    """Os cabeçalhos que o pacote escreve, por `pref` — pelos DOIS caminhos.

    A coluna COM aparelho sai em `colunas`, para ganhar o selo do piloto; a
    coluna SEM sai em `blocos`, porque a `colunas` de um lugar vazio tem régua
    de conteúdo exato. Uma régua que olhasse só um dos dois daria verde sobre
    metade da tela — e é a metade que muda quando um controle sai da mesa.
    """
    fora = {}
    for seletor, html in r["blocos"].items():
        achou = re.fullmatch(
            rf'\[data-controle="(p\d+)"\] \[data-campo="{a03.CAMPO_DO_CHIP}"\]',
            seletor)
        if achou:
            fora[achou.group(1)] = str(html)
    pref_de = {str(m.get("uniq") or ""): str(m.get("pref") or "") for m in mesa}
    for chave, col in r["colunas"].items():
        if a03.CAMPO_DO_CHIP in col:
            fora[pref_de.get(chave, chave)] = str(col[a03.CAMPO_DO_CHIP])
    return fora


def _cores(a03, r, mesa) -> dict[str, str]:
    """A COR que o pacote escreve em cada coluna, por `pref`.

    Ela saiu do HTML do chip em 03/09/2026 e passou a ter endereço próprio no
    EMBRULHO — o único elemento que o produto pode pintar com o alvo `plastico`
    sem carimbar o selo dentro do HTML que ele mesmo compara. Uma régua que
    continuasse procurando `--plastico` no chip daria verde sobre a mesa dela e
    vermelho sobre a cura, que é o pior defeito que uma régua pode ter.

    O LUGAR SEM COLUNA NÃO APARECE AQUI, e é fato e não omissão: o `blocos`
    escreve HTML, não estilo. Quem checa aquele caso é
    `test_o_lugar_sem_aparelho_perde_o_nome`.
    """
    pref_de = {str(m.get("uniq") or ""): str(m.get("pref") or "") for m in mesa}
    return {pref_de.get(chave, chave): str(col[a03.CAMPO_DO_PLASTICO])
            for chave, col in r["colunas"].items()
            if a03.CAMPO_DO_PLASTICO in col}


# ---------------------------------------------------------------------------
# 1. O ENDEREÇO — sem ele a régua da identidade acusa, e com razão.
# ---------------------------------------------------------------------------

def test_todo_chip_da_bancada_tem_endereco(a03, bancada):
    """Os dois endereços do chip, e cada um tem um trabalho — e um alcance.

    O DO EMBRULHO É O DA COR — 03/09/2026, e é a cura desta frente. O
    `--plastico` morava no `style` do `<span>` de dentro, e ali o produto não
    tinha como reescrevê-lo: `check_a_cor_vem_do_aparelho.py` contava os dois
    chips com cor como CRAVADOS, com razão — *"o `escrever()` escreve no
    elemento que ACHOU"*, e o alvo daquele `<span>` era `texto`.

    ELE ESTÁ NAS QUATRO COLUNAS, com cor ou sem: a página é estática e o piloto
    não cria endereço. Sem ele no P3, o dia em que um controle entra ali a cor
    não teria por onde chegar — e a coluna mostraria o nome do plástico com a
    borda neutra.

    O DO MIOLO É O QUE REFAZ O CHIP: classe, dica e nome de uma vez, pelo alvo
    `html`. Ele desceu para um `<span>` de embrulho justamente para a cor poder
    subir: o selo da visita não pode cair dentro do HTML comparado, ou a coluna
    repinta a cada tique (medido: 17 tiques, 17 pinturas).

    ARRANQUE qualquer um dos dois, rode o gerador, e esta régua reprova aqui.
    """
    embrulhos = bancada.count(
        f'<div class="{a03.CLASSE_DO_CHIP}" data-campo="{a03.CAMPO_DO_PLASTICO}"'
        f' data-hef-alvo="{a03.ALVO_DO_PLASTICO}"')
    assert embrulhos == 4, (
        f"o endereço da COR está em {embrulhos} colunas, e não em 4. É por ele "
        f"que o produto veste o plástico do controle que a fita já leu.")

    miolos = bancada.count(
        f'<span data-campo="{a03.CAMPO_DO_CHIP}" data-hef-alvo="html">')
    assert miolos == 4, (
        f"o endereço do MIOLO está em {miolos} colunas, e não em 4. É por ele "
        f"que o nome e a dica do chip trocam quando a mesa muda.")

    # E A COR CRAVADA SÓ MORA NO EMBRULHO ENDEREÇADO. Um `--plastico` solto em
    # qualquer outro lugar da página é identidade que o produto não alcança.
    #
    # A FITA DO TOPO ESTÁ FORA DESTE ALCANCE, e a razão é de território, não de
    # conveniência: os chips dela saem de `monta.fita()`, o esqueleto das DEZ
    # páginas, e os mesmos seis achados aparecem nas dez. Consertá-los aqui
    # seria dez pessoas editando a mesma linha. **Ela continua acusada** pela
    # `check_identidade_vem_de_cima --bancada`, que é onde o número tem de
    # aparecer.
    for casa in re.finditer(r"--plastico\s*:", bancada[_depois_da_fita(bancada):]):
        posicao = casa.start() + _depois_da_fita(bancada)
        inicio = bancada.rfind("<", 0, posicao)
        tag = bancada[inicio:bancada.find(">", posicao) + 1]
        assert f'data-hef-alvo="{a03.ALVO_DO_PLASTICO}"' in tag, (
            f"há `--plastico` num elemento que o produto não repinta: "
            f"{tag[:120]!r}. A borda fica com a cor de um controle que não "
            f"está na mesa.")


def test_o_embrulho_diz_como_quer_ser_pintado(a03, bancada):
    """Cada endereço declara o alvo que o alcança — e são dois alvos diferentes.

    O MIOLO PEDE `html`: `escrever()` no alvo padrão faz `el.textContent = t`,
    que **apaga os filhos** — e o que se escreve ali é um `<span>` inteiro com
    dois `<span class="pt">•</span>` dentro. Sem o alvo declarado, o primeiro
    tique poria a marcação como TEXTO LITERAL na tela: `<span class="chip …`. É
    a mesma família do `Aceso` escrito dentro do desenho da Iluminação.

    O EMBRULHO PEDE `plastico`: é o único alvo do piloto que escreve uma
    propriedade CSS de autor. Com qualquer outro, o hexadecimal do aparelho vira
    o TEXTO do cabeçalho — `#e4e0d8` no lugar de `P1 • White • USB`.
    """
    for casa in re.finditer(rf'<div class="{a03.CLASSE_DO_CHIP}"([^>]*)>', bancada):
        atributos = casa.group(1)
        assert f'data-campo="{a03.CAMPO_DO_PLASTICO}"' in atributos, (
            f"um embrulho de chip sem o endereço da cor: {casa.group(0)!r}")
        assert f'data-hef-alvo="{a03.ALVO_DO_PLASTICO}"' in atributos, (
            f"o embrulho {casa.group(0)!r} não diz como quer ser pintado — sem "
            f"o alvo `plastico` o hexadecimal do aparelho vira texto de tela")

    for casa in re.finditer(
            rf'<span data-campo="{a03.CAMPO_DO_CHIP}"([^>]*)>', bancada):
        assert 'data-hef-alvo="html"' in casa.group(1), (
            f"o miolo {casa.group(0)!r} não diz como quer ser pintado — no "
            f"alvo padrão o `textContent` põe a marcação do chip como texto")


# ---------------------------------------------------------------------------
# 2. O CHIP VIVO — dar endereço não é entregar.
# ---------------------------------------------------------------------------

def test_o_chip_vivo_e_o_controle_da_mesa(a03):
    """Com um White no cabo, a coluna diz White — e nenhuma cor do desenho.

    ESTA É A RÉGUA QUE SEPARA O CONSERTO DA MAQUIAGEM. Um `data-campo` que
    ninguém escreve zera a régua da identidade e deixa a tela igualmente
    mentindo: seria trocar um congelado por um vazio.

    ARRANQUE o `CAMPO_DO_CHIP: _chip_vivo(ctx, c)` da coluna e esta régua
    reprova nomeando a coluna. **A régua da identidade NÃO reprova** — ela
    continua em 6, porque o endereço está lá. Medido em 03/09/2026, com o
    escritor arrancado de propósito: `--bancada --aba 03` seguiu dizendo 6 e a
    tela voltou a dizer `Cosmic Red`. É por isso que este arquivo existe.
    """
    r = _pacote(a03, MESA_DELA, [NO_CABO, NO_RADIO])
    chips = _chips(a03, r, MESA_DELA)
    assert set(chips) == {"p1", "p2", "p3", "p4"}, (
        f"o pacote escreve o cabeçalho de {sorted(chips)}. A coluna que ele não "
        f"escreve continua com o controle que o gerador desenhou.")

    assert "White" in chips["p1"], (
        f"a coluna do controle no cabo não diz o nome dele: {chips['p1']!r}")
    from monta import cor_da_zona

    assert _cores(a03, r, MESA_DELA)["p1"] == cor_da_zona("white"), (
        "a borda da coluna do White não recebeu a cor do MAPA dela — ela é "
        "como se sabe de quem é a coluna (`D-A-BORDA-E-A-IDENTIDADE-DA-PECA`), "
        "e o hexadecimal tem de sair do CSV, não de uma tabela deste código")

    inteiro = "".join(chips.values()) + str(r["colunas"])
    for cor in DO_MOCKUP:
        assert cor not in inteiro, (
            f"o produto ainda escreve {cor!r} — é a cor do DESENHO, e ela não é "
            f"de nenhum controle desta mesa. A fita do topo lê do aparelho; a "
            f"aba abaixo dela tem de usar AQUELE controle.")


def test_o_chip_nao_repinta_a_cada_tique(a03):
    """O HTML do chip não carrega `data-campo` — e é uma régua de CONTADOR.

    O DEFEITO, medido em 03/09/2026 com o piloto e os dois controles dela, e ele
    é do tipo que passa despercebido porque não muda um pixel::

        endereço DENTRO do miolo comparado ... 17 tiques, 17 pintaram
        endereço no embrulho (agora) ......... 17 tiques,  2 pintaram

    `escrever()` carimba `data-hef-visto="1"` no elemento que visita. Com um
    `data-campo` DENTRO do HTML que o alvo `html` compara, o selo entra na
    comparação, o `innerHTML` nunca mais bate com o que o pacote emite, e a
    pintura se repete para sempre — somando +1 por tique.

    ISSO IMPORTA PORQUE O CONTADOR É O INSTRUMENTO. É com ele que esta casa
    prova que um endereço existe, e o próprio piloto já escreveu a frase sobre
    o `<select>` que recusa um valor: *um contador que mente é pior que um campo
    parado*.

    O ENDEREÇO DO `<span>` É `data-hef`, e o nome não casa com chave nenhuma: o
    `achar()` varre os três vocabulários pela MESMA chave, e um `<span>` com o
    nome do embrulho receberia um chip dentro de si.
    """
    html = a03.chip_do_controle(1, "White", "USB", "#e4e0d8")
    assert "data-campo" not in html, (
        f"o chip emitido traz `data-campo`: {html!r}. O piloto vai carimbar o "
        f"selo dentro do HTML que ele compara, e a coluna passa a repintar a "
        f"cada tique — pintura que não muda nada, contada como se mudasse.")
    assert "data-hef-visto" not in html, (
        "o pacote está emitindo o SELO do piloto. O selo é um fato do piloto — "
        "quem o escreve declara que esteve ali; escrevê-lo aqui seria a aba "
        "assinando a visita que não fez.")

    r = _pacote(a03, MESA_DELA, [NO_CABO, NO_RADIO])
    col = r["colunas"][NO_CABO["uniq"]]
    assert a03.CAMPO_DO_CHIP in col, (
        "a coluna COM aparelho tem de sair por `colunas`, e não por `blocos`: é "
        "o campo que ganha o selo, e sem ele um controle que por acaso SEJA o "
        "Cosmic Red do desenho ficaria classificado como mockup para sempre")
    assert "White" in str(col[a03.CAMPO_DO_CHIP])


# ---------------------------------------------------------------------------
# 3. A ARMADILHA DELA — campo sem informação não mostra nada.
# ---------------------------------------------------------------------------

def test_sem_cor_lida_o_chip_nao_veste_plastico(a03):
    """O controle por rádio, sem cor lida, sai `P2 • BT` — e nada mais.

    A LEITURA POR RÁDIO AINDA NÃO TRAZ A COR. A mesa nasce com `cor` vazia e
    `nome` igual a `"Não sei"`, e a regra dela é a de sempre: *campo sem
    informação não mostra nada*. Cair de volta no mockup vestiria aquele
    controle com o plástico de outro.

    A BORDA NÃO SOME: `topo.html` declara
    `.chip.plastico{border-color:var(--plastico, var(--border-forte))}`, com a
    queda já escrita.
    """
    r = _pacote(a03, MESA_DELA, [NO_CABO, NO_RADIO])
    chip = _chips(a03, r, MESA_DELA)["p2"]
    assert _cores(a03, r, MESA_DELA)["p2"] == "", (
        f"a coluna do controle por rádio recebeu cor de plástico: "
        f"{_cores(a03, r, MESA_DELA)['p2']!r}. Ninguém leu essa cor — ela viria "
        f"do desenho. O vazio APAGA o `--plastico`, e a queda do `topo.html` "
        f"deixa a borda neutra.")
    assert "Não sei" not in chip, (
        f"`Não sei` é a AUSÊNCIA de leitura, não um nome, e ela não vai para a "
        f"tela: {chip!r}")
    assert "P2" in chip and "BT" in chip, (
        f"sobrou menos do que a tela pode afirmar: {chip!r}. A posição e o "
        f"transporte são fatos, e eles ficam.")


def test_o_lugar_sem_aparelho_perde_o_nome(a03):
    """Com um controle só, a coluna do P2 diz `Desconectado`.

    O DESENHO DÁ O P2 POR CONECTADO — e é por isso que este caso existe: o
    laço dos lugares vazios usa a conta LARGA (`_todos_os_lugares_da_pagina`),
    não só os que o gerador já marcou. Sem ele, o cabeçalho do P2 continuaria
    dizendo `Starlight Blue` com ninguém ali.
    """
    r = _pacote(a03, MESA_DE_UM, [NO_CABO])
    chips = _chips(a03, r, MESA_DE_UM)
    cores = _cores(a03, r, MESA_DE_UM)
    assert "Desconectado" in chips["p2"], (
        f"o P2 ficou com {chips['p2']!r} e não há controle nele")
    for pref in ("p2", "p3", "p4"):
        assert "--plastico" not in chips[pref], (
            f"{pref} está vazio e o chip dele traz cor: {chips[pref]!r}. A cor "
            f"mora no embrulho, e o chip de um lugar vazio não a carrega.")
    # O P3 E O P4 A APAGAM POR CAMPO; o P2 sai por BLOCO (a página o dá por
    # conectado) e o bloco escreve HTML, não estilo. Ali o `--plastico` do
    # desenho fica no embrulho — e é INERTE, porque a classe do chip vira
    # `vazio` e `.chip.vazio` declara a borda inteira sem `var(--plastico)`.
    for pref in ("p3", "p4"):
        assert cores.get(pref) == "", (
            f"{pref} está vazio e a coluna não apaga a cor: {cores.get(pref)!r}. "
            f"Um controle que SAI do P1 deixaria a borda dele acesa num lugar "
            f"sem aparelho.")


def test_o_numero_do_jogador_fica(a03):
    """`P1`…`P4` continuam na tela: eles são ESTRUTURA, não identidade.

    Ela, com todas as letras: *"O p1 ou p2 reflete o player do jogador."* A
    régua da identidade não os acusa de propósito, e apagá-los aqui seria
    consertar o que estava certo.
    """
    r = _pacote(a03, MESA_DELA, [NO_CABO, NO_RADIO])
    chips = _chips(a03, r, MESA_DELA)
    for n, pref in enumerate(("p1", "p2", "p3", "p4"), start=1):
        assert f"P{n}" in chips[pref], (
            f"a coluna {pref} perdeu o número do jogador: {chips[pref]!r}")


# ---------------------------------------------------------------------------
# 4. UM DONO, DOIS CHAMADORES — a régua que fecha o buraco de origem.
# ---------------------------------------------------------------------------

def test_o_desenho_e_o_produto_tem_um_dono_so(a03, bancada):
    """O chip que o pacote emite para a MESA do desenho é o que está na bancada.

    ENQUANTO ERAM DUAS ESCRITAS, o desenho e o produto podiam divergir sem
    ninguém ver — e o produto passaria a trocar o desenho por outro desenho.
    Esta régua compara byte a byte.

    ARRANQUE o `chip_do_controle` do gerador (volte a montar o `<span>` à mão) e
    ela reprova no primeiro atributo que ficar fora de ordem.
    """
    import monta

    for c in monta.MESA:
        conectado = bool(c.get("conectado", True))
        esperado = a03.chip_do_controle(
            c["jogador"],
            c["nome"] if conectado else "",
            c["via"] if conectado else "",
            monta.cor_da_zona(c["cor"]) if conectado else "",
            conectado=conectado)
        assert esperado in bancada, (
            f"o chip do {c['pref'].upper()} da bancada não é o que a função "
            f"emite. Esperado:\n  {esperado}\nO desenho e o produto voltaram a "
            f"ter duas marcações para a mesma coisa.")


def test_o_separador_do_chip_e_o_da_casa(a03):
    """O `•` do chip é o MESMO `monta.SEPARADOR` do resto do desenho.

    Uma segunda cópia dele envelheceria sozinha — é a mesma razão pela qual o
    `NOME_SEM_LEITURA` do `pacotes/__init__` tem régua que o compara com o
    `mesa_viva.COR_DESCONHECIDA`.
    """
    import monta

    assert a03.PONTO == monta.SEPARADOR, (
        f"o chip separa com {a03.PONTO!r} e o desenho com {monta.SEPARADOR!r} — "
        f"duas verdades sobre a mesma marca")
