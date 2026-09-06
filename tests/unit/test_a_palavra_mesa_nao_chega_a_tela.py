"""A PALAVRA "mesa" não chega à tela — e a régua tem de impedir a volta.

Ela, 06/09/2026: *"Falei do termo mesa que é horrível. Mas os claudes anteriores
entraram na pira de usar isso em tudo no layout. O termo sai e coloca-se termos
simples pro user comum. feature fica."*

**PALAVRA, NÃO FEATURE.** Nenhuma tabela, contagem ou aviso saiu por causa
desta régua; o que mudou é como a tela os chama. O vocabulário que entra no
lugar está em `docs/A-LINGUA-DESTA-CASA…`, §1: *os controles*, *todos*,
*P1 e P2*, *quem está ligado*.

O NÚMERO MEDIDO EM 06/09, e ele explica por que uma régua por substring não
serve: `grep -oiE "\\bmesa\\b" mockup/??-*.html` devolvia **194**, e delas

* **121** estavam em comentário de CSS e **14** em comentário de HTML — prosa
  da casa, que ninguém lê na tela;
* **16** eram nome de classe ou de campo (`mesa-notas`, `radio-mesa`,
  `name="mesa"`, `nav-mesa`, `perfil-da-mesa`) — endereço vivo, que o glossário
  manda ficar;
* **43** eram texto que a pessoa LÊ, e delas 9 estavam dentro de `<code>`,
  escritas de propósito como identificador (`monta.MESA`).

Sobram **34**, e essas são o trabalho. Uma régua que reprovasse as 194 mandaria
a próxima pessoa renomear `mesa_viva.py` — que é estrago, não cura.

AS DUAS RÉGUAS, e elas têm pontos cegos diferentes de propósito:

1. **as dez páginas da bancada** — o que está escrito no desenho de hoje;
2. **os dez pacotes** — o que o piloto ESCREVE por tique. A página estática não
   mostra nenhuma delas, e são justamente as que chegam ao cartão dela como
   recado: *"este controle saiu da mesa"* estava em cinco lugares de
   `a02_controles.py` com a primeira régua verde.

O QUE ESTA RÉGUA NÃO ALCANÇA, e está dito porque instrumento que não declara o
próprio ponto cego mente: `interface/paginas/` (o que o produto renderiza) e
`app/`, o motor. O primeiro só muda quando ELA publica — `--publicar` é ato
dela.

O SEGUNDO DEIXOU DE SER PONTO CEGO em 06/09/2026, na costura da ONDA E: as
dezesseis frases de `app/` que a sprint listou (`A-PALAVRA-MESA-SAI-01.md`) foram
curadas no dono, e `hefesto_vivo._json` — o funil por onde todo valor passa a
caminho do WebView — passou a chamar `primeiro_trecho_banido`. De agora em
diante quem alcança `app/` é o PRODUTO RODANDO, que é a régua mais dura que
existe: a frase banida derruba o tique em vez de chegar à tela.
"""

from __future__ import annotations

import ast
from pathlib import Path

from hefesto_dualsense4unix.interface.frases_que_ela_baniu import (
    PALAVRAS_BANIDAS,
    palavra_banida_em,
    primeiro_trecho_banido,
    texto_visivel,
)

RAIZ = Path(__file__).resolve().parents[2]
INTERFACE = RAIZ / "src" / "hefesto_dualsense4unix" / "interface"
BANCADA = RAIZ / "mockup"
PACOTES = INTERFACE / "pacotes"


def _paginas() -> list[Path]:
    """As dez abas da bancada — e RECUSA achar menos que dez.

    Régua que acha zero página termina verde sobre nada, que é a armadilha
    que o `olhar.py` já carrega escrita no `--todas`.
    """
    achadas = sorted(p for p in BANCADA.glob("??-*.html"))
    assert len(achadas) == 10, (
        f"achei {len(achadas)} abas em {BANCADA} e o produto tem dez — "
        "o caminho mudou, e uma régua que não acha a tela não mede a tela."
    )
    return achadas


def _literais_dos_pacotes() -> list[tuple[Path, int, str]]:
    """Todo literal de string dos dez pacotes que NÃO é docstring.

    O `ast` e não um `grep`, pela mesma razão da régua irmã: a frase viva mora
    partida em quatro linhas do fonte com o recuo no meio, e o parser junta a
    concatenação implícita antes de a régua olhar.

    A DOCSTRING FICA DE FORA porque é prosa da casa — o glossário deixa `mesa`
    viver como nome interno, e é em docstring que esta casa explica o `mesa`
    de `mesa_viva`. Comentário nem entra: o `ast` não o vê.
    """
    fora: list[tuple[Path, int, str]] = []
    for arquivo in sorted(PACOTES.glob("a??_*.py")):
        arvore = ast.parse(arquivo.read_text(encoding="utf-8"))
        docstrings = set()
        for no in ast.walk(arvore):
            corpo = getattr(no, "body", None)
            if not isinstance(
                no, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)
            ) or not corpo:
                continue
            primeiro = corpo[0]
            if (
                isinstance(primeiro, ast.Expr)
                and isinstance(primeiro.value, ast.Constant)
                and isinstance(primeiro.value.value, str)
            ):
                docstrings.add(id(primeiro.value))
        for no in ast.walk(arvore):
            if not isinstance(no, ast.Constant) or not isinstance(no.value, str):
                continue
            if id(no) in docstrings:
                continue
            fora.append((arquivo, no.lineno, no.value))
    assert len(fora) > 500, (
        f"li {len(fora)} literais nos dez pacotes — são milhares. "
        "Uma régua que não acha literal nenhum passa sobre qualquer frase."
    )
    return fora


# ---------------------------------------------------------------------------
# 1. O DESENHO — as dez páginas da bancada
# ---------------------------------------------------------------------------
def test_a_palavra_nao_e_lida_em_nenhuma_das_dez_abas() -> None:
    """Zero, e o erro diz PÁGINA, LINHA e a frase inteira.

    A entrega de uma régua é o endereço do defeito, não o número dele: quem
    ler esta reprovação tem de saber o que reescrever sem abrir o HTML.
    """
    sujas: list[str] = []
    for pagina in _paginas():
        visivel = texto_visivel(pagina.read_text(encoding="utf-8"))
        for numero, linha in enumerate(visivel.splitlines(), start=1):
            if palavra_banida_em(linha) is None:
                continue
            sujas.append(f"{pagina.name}:{numero}: {' '.join(linha.split())[:220]}")
    assert not sujas, (
        f"palavra banida LIDA na tela ({', '.join(PALAVRAS_BANIDAS)}):\n  "
        + "\n  ".join(sujas)
        + "\n\nEla, 06/09/2026: *o termo sai e coloca-se termos simples pro "
        "user comum. feature fica*. O que entra no lugar está no glossário, "
        "§1 — `docs/A-LINGUA-DESTA-CASA-o-glossario-que-a-tela-e-o-codigo-"
        "falam.md`. O nome interno (`mesa_viva`, `monta.MESA`, `mesa-frase`) "
        "NÃO muda: a régua já o deixa passar, e trocá-lo é estrago."
    )


# ---------------------------------------------------------------------------
# 2. O TIQUE — o que os dez pacotes escrevem em execução
# ---------------------------------------------------------------------------
def test_a_palavra_nao_nasce_em_nenhum_dos_dez_pacotes() -> None:
    """A página estática não mostra recado nenhum — e é lá que ela morava.

    Cinco frases de `a02_controles.py` diziam *"este controle saiu da mesa"* com
    a régua da página VERDE, porque um recado só existe quando o gesto falha.
    Esta metade lê o fonte, que é onde a frase existe antes de acontecer.
    """
    sujos: list[str] = []
    for arquivo, linha, texto in _literais_dos_pacotes():
        if palavra_banida_em(texto) is None:
            continue
        sujos.append(f"{arquivo.name}:{linha}: {' '.join(texto.split())[:220]}")
    assert not sujos, (
        "palavra banida num literal de pacote — ela chega à tela pelo tique:\n  "
        + "\n  ".join(sujos)
        + "\n\nA chave do pacote (`{\"mesa\": {campo: valor}}`) NÃO cai aqui: a "
        "régua deixa passar o texto que É a palavra e nada mais. Se a sua "
        "linha caiu, ela é frase."
    )


# ---------------------------------------------------------------------------
# 3. O CONTRATO da lista — e ele é o que deixa a próxima palavra entrar barato
# ---------------------------------------------------------------------------
def test_a_borda_de_palavra_deixa_o_nome_interno_em_paz() -> None:
    """O glossário em forma de teste: a palavra sai, o nome fica."""
    for nome in (
        "mesa",
        "mesa_viva.py",
        "app/mesa.py",
        "monta.MESA",
        "MESA_VAZIA",
        'data-campo="mesa-frase"',
        "perfil-da-mesa",
        "radio-mesa",
        '{"mesa": {"conta": 2}}',
        "uma remessa nova",
    ):
        assert palavra_banida_em(nome) is None, (
            f"{nome!r} é NOME INTERNO e a régua o reprovou — ela mandaria "
            "renomear `mesa_viva.py`, que a sprint proíbe com todas as letras."
        )
    for frase in (
        "quatro controles na mesa",
        "a mesa inteira",
        "Mesa: 4 faces",
        "este controle saiu da mesa",
        '{"mesa": {"aviso": "sem controle na mesa"}}',
    ):
        assert palavra_banida_em(frase) == "mesa", (
            f"{frase!r} é FRASE de tela e a régua a deixou passar."
        )


def test_o_primeiro_trecho_banido_consulta_as_duas_listas() -> None:
    """A função que a sprint pediu: frase e palavra numa consulta só.

    O DIA CHEGOU em 06/09/2026: as dezesseis frases de `app/` foram curadas no
    dono e `hefesto_vivo._json` trocou `frase_banida_em` por esta, de modo que o
    funil de execução recusa as duas coisas. Enquanto as dezesseis viviam, ligá-lo
    trocaria uma palavra feia por uma JANELA MORTA — e é por isso que a ordem
    importava, não a pressa.
    """
    assert primeiro_trecho_banido("nada demais aqui") is None
    assert primeiro_trecho_banido("na mesa inteira") == "mesa"
    assert primeiro_trecho_banido("Alguns jogos derrubam o controle") == (
        "derrubam o controle"
    )
    # A FRASE VEM PRIMEIRO quando as duas casam: ela é a mais específica, e é
    # dela que a mensagem de erro do funil fala.
    assert primeiro_trecho_banido("na mesa eles derrubam o controle") == (
        "derrubam o controle"
    )


def test_o_funil_de_execucao_consulta_as_duas_listas() -> None:
    """O `_json` chama `primeiro_trecho_banido`, e não a metade dele.

    Esta régua existe porque a troca é de UMA LINHA e o recuo também seria: o
    dia em que alguém devolver `frase_banida_em` ao funil, a palavra volta a
    chegar à tela por `app/` sem nada reprovar — foi o estado do mundo até
    06/09/2026, e ele era declarado, não esquecido.

    Ela lê o FONTE do funil em vez de exercitá-lo porque o `_json` é interno ao
    piloto GTK e importá-lo aqui abriria uma janela na tela dela.

    E ela anda pela ÁRVORE, não pelo texto. O `grep` seria a sétima vez nesta
    casa em que um comentário vira o defeito que descreve: o do `_json` explica
    a troca e CITA o nome da função, então uma régua que procurasse a palavra
    daria verde com a chamada arrancada. `ast` só enxerga a chamada.
    """
    fonte = (
        Path(__file__).resolve().parents[2]
        / "src/hefesto_dualsense4unix/interface/hefesto_vivo.py"
    ).read_text(encoding="utf-8")
    funil = next(
        no
        for no in ast.parse(fonte).body
        if isinstance(no, ast.FunctionDef) and no.name == "_json"
    )
    chamadas = {
        alvo.func.id
        for alvo in ast.walk(funil)
        if isinstance(alvo, ast.Call) and isinstance(alvo.func, ast.Name)
    }
    assert "primeiro_trecho_banido" in chamadas, (
        "o funil `hefesto_vivo._json` deixou de CHAMAR `primeiro_trecho_banido`. "
        "Ele é por onde TODO valor passa a caminho do WebView, e "
        f"`frase_banida_em` sozinha não vê a palavra — só a frase. Chama: {sorted(chamadas)}"
    )


def test_o_stripper_nao_engole_a_dica_nem_inventa_tamanho() -> None:
    """As duas armadilhas do `texto_visivel`, medidas em vez de afirmadas.

    A dica do `?` mora num `title=`, DENTRO de uma tag: um stripper que só
    olhasse nó de texto daria verde sobre a palavra escondida ali. E o tamanho
    tem de bater byte a byte com a entrada, senão a linha que a régua reporta é
    a linha de outro lugar.
    """
    pagina = (
        '<style>/* a mesa toda */</style>\n'
        '<!-- na mesa -->\n'
        '<p title="a mesa aqui">x <code>monta.MESA</code> y</p>\n'
    )
    visivel = texto_visivel(pagina)
    assert len(visivel) == len(pagina), (
        "o `texto_visivel` mudou de tamanho — a linha que a régua reporta "
        "deixa de ser a linha da página."
    )
    assert visivel.count("\n") == pagina.count("\n")
    assert palavra_banida_em(visivel) == "mesa", (
        "a palavra na DICA passou — e a dica é onde o glossário diz que a "
        "explicação mora."
    )
    sem_dica = pagina.replace(' title="a mesa aqui"', "")
    assert palavra_banida_em(texto_visivel(sem_dica)) is None, (
        "sobrou palavra fora da dica: ou o CSS, ou o comentário, ou o "
        "`<code>` está chegando à leitura."
    )
