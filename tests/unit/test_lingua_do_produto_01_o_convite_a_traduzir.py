"""O convite a traduzir só pode existir com o encanamento ligado nas telas.

Decisão dela, 07/08/2026 (resposta 10 do painel): **o português do Brasil é a
língua do produto**. Três páginas do projeto — `.github/CONTRIBUTING.md`,
`docs/usage/flatpak.md` e `docs/usage/troubleshooting.md` — convidavam a
comunidade a acrescentar um idioma, com receita pronta. O convite era falso: o
catálogo alcança o esqueleto fixo da janela, e não alcança o texto que as abas
escrevem enquanto rodam.

Este arquivo é o portão que impede o convite de voltar **sozinho**. Ele não
proíbe traduzir para sempre: proíbe enquanto o encanamento não estiver de fato
ligado às telas. No dia em que estiver, o portão para de reprovar sem que
ninguém precise editar uma linha aqui — a condição é medida do CÓDIGO, não
escrita à mão.

O CRITÉRIO, e por que não é "procurar a palavra traduzir"
--------------------------------------------------------

Um portão que procurasse `traduzir` reprovaria `docs/usage/integrating-mods.md`,
que fala de *"modo de gatilho sem tradução"* — outro assunto, mesma palavra — e
viraria ruído no primeiro documento honesto. O que caracteriza o convite não é
o vocábulo: é a **receita**, e receita tem comando, arquivo-alvo e cabeçalho
imperativo. Por isso as marcas são quatro, e cada uma sozinha já é prova:

1. **o comando que cria idioma** (`i18n_extract.sh --add`). Ninguém o escreve
   sem estar ensinando alguém a usá-lo;
2. **um catálogo que o repositório não tem** (`po/fr_FR.po` e parentes),
   derivado de `po/` em tempo de execução — citar um `.po` inexistente é dizer
   ao leitor que ele o crie;
3. **cabeçalho de receita** — "Adicionar idioma novo", "Contribuir traduções".
   Cabeçalho é o índice de um procedimento; prosa que apenas *menciona*
   tradução não vira seção;
4. **ponteiro para a receita** — a frase-alvo *"para adicionar um novo
   idioma..."*, que era como a `flatpak.md` empurrava o leitor para a
   `CONTRIBUTING`, e o nome da seção removida.

E o portão só cobra isso nos documentos que **ENSINAM** — o mesmo escopo que
`scripts/validar-referencias-docs.py` usa e pelo mesmo motivo: `docs/process/`
é registro histórico, e uma sprint que conta o que foi removido precisa citar o
removido.

A MORDIDA (verificada em 07/08/2026)
------------------------------------

Devolvi a receita ao fim da seção 11 de `docs/usage/troubleshooting.md`, com as
mesmas linhas que saíram, e
`test_nenhuma_pagina_que_ensina_convida_a_traduzir` reprovou nas quatro marcas
de uma vez. Devolvi só o ponteiro da `flatpak.md` (uma frase, sem comando) e
reprovou de novo. Depois arranquei a condição do encanamento (fingindo os 18
módulos traduzidos) e o portão passou a ACEITAR a receita — que é a metade
condicional funcionando, e não um "não" disfarçado de condição.

O ALCANCE DESTE PORTÃO, MEDIDO (07/08/2026) — leia antes de confiar nele
------------------------------------------------------------------------

Ele é ESTREITO, e isso é de propósito. As quatro marcas são casadas com A
REDAÇÃO QUE SAIU, não com a ideia. Um convite EQUIVALENTE escrito com outras
palavras passa VERDE, e isso está medido: acrescentado à `docs/usage/flatpak.md`
um bloco com cabeçalho "Traduzir o Hefesto", o comando `msginit` do `gettext`
sobre um `.pot` e o pedido de mandar o arquivo num pull request, os 50 testes
deste arquivo passaram. Trocado só o comando pelo `i18n_extract.sh --add`, o
mesmo bloco reprovou na hora (`1 failed, 49 passed`). A página foi devolvida
byte a byte depois das duas medições. GRAU: MEDIDO.

NÃO alargue isto procurando a palavra `traduzir`: a seção "O CRITÉRIO" acima
explica por que essa versão reprovaria três documentos honestos e seria
desligada na terceira vez. O que este portão promete é impedir que a receita
REMOVIDA volte sozinha — e é só isso que ele entrega. Contra a forma reescrita,
a defesa é a revisão humana. O registro completo está na
LINGUA-DO-PRODUTO-01, seção "O que fica ABERTO".
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]

#: Os módulos que escrevem o texto vivo das abas. É aqui que o encanamento de
#: i18n precisa chegar para que traduzir signifique alguma coisa.
DIR_ACOES = RAIZ / "src" / "hefesto_dualsense4unix" / "app" / "actions"

#: Onde moram os catálogos que o projeto de fato entrega.
DIR_CATALOGOS = RAIZ / "po"

#: Os documentos que ENSINAM. `docs/process/` fica de fora por escrito: sprint
#: é registro, e registrar a remoção de uma receita exige transcrevê-la.
ALVOS_QUE_ENSINAM = (
    "README.md",
    ".github/CONTRIBUTING.md",
    "docs/usage",
    "docs/adr",
    "docs/protocol",
)

#: Letra acentuada do português. Um literal que a carrega é prosa escrita para
#: uma pessoa ler, não chave de dicionário nem nome de sinal.
_ACENTUADA = re.compile(r"[áàâãéêíóôõúüçÁÀÂÃÉÊÍÓÔÕÚÜÇ]")

#: O comando que cria um catálogo novo. Marca 1.
_COMANDO_QUE_CRIA_IDIOMA = re.compile(r"i18n_extract\.sh\s+--add")

#: Um arquivo `po/<algo>.po`. Marca 2 depois de descontar os que existem.
_CATALOGO_CITADO = re.compile(r"\bpo/([A-Za-z0-9_.-]+)\.po\b")

#: Cabeçalho markdown com forma de receita. Marca 3.
_CABECALHO_DE_RECEITA = re.compile(
    r"^#{1,6}\s.*\b(adicionar|acrescentar|criar|incluir|contribuir)\b"
    r"[^\n]{0,40}\b(idioma|l[ií]ngua|tradu[çc])",
    re.IGNORECASE,
)

#: Ponteiro para a receita: a construção final ("para adicionar um novo
#: idioma...") e o nome da seção que saiu da `CONTRIBUTING`. Marca 4.
_PONTEIRO_PARA_A_RECEITA = (
    re.compile(
        r"\b(para|como)\s+(adicionar|acrescentar|criar|incluir)\s+"
        r"(um\s+|uma\s+)?(novo\s+|nova\s+)?(idioma|l[ií]ngua|tradu[çc][ãa]o)",
        re.IGNORECASE,
    ),
    re.compile(r"contribuir\s+tradu[çc]", re.IGNORECASE),
)


def _importa_a_funcao_de_traducao(arvore: ast.Module) -> bool:
    """O módulo puxa o `_` de `utils.i18n` (ou o `gettext` cru)?

    Lido por AST, sem importar o pacote: importar `app.actions` arrasta GTK e
    transformaria este portão num erro de coleta na primeira máquina sem
    PyGObject — modo de falha que some calado, e esta casa já pagou por ele.
    """
    for no in ast.walk(arvore):
        if (
            isinstance(no, ast.ImportFrom)
            and no.module
            and "i18n" in no.module
            and any(alias.name == "_" for alias in no.names)
        ):
            return True
        if isinstance(no, ast.Import) and any(
            alias.name == "gettext" for alias in no.names
        ):
            return True
        if isinstance(no, ast.ImportFrom) and no.module == "gettext":
            return True
    return False


def _literais_de_prosa(arvore: ast.Module) -> int:
    """Quantos literais de texto do módulo carregam acentuação portuguesa."""
    total = 0
    for no in ast.walk(arvore):
        if (
            isinstance(no, ast.Constant)
            and isinstance(no.value, str)
            and _ACENTUADA.search(no.value)
        ):
            total += 1
    return total


def _modulos_que_escrevem_portugues_cru(diretorio: Path) -> dict[str, int]:
    """Os módulos com prosa acentuada e SEM a função de tradução.

    É a medida de "o encanamento não está ligado nas telas", e é o que decide se
    o convite pode existir. Devolve nome do arquivo -> quantidade de literais.
    """
    fora: dict[str, int] = {}
    for fonte in sorted(diretorio.glob("*.py")):
        arvore = ast.parse(fonte.read_text(encoding="utf-8"))
        if _importa_a_funcao_de_traducao(arvore):
            continue
        prosa = _literais_de_prosa(arvore)
        if prosa:
            fora[fonte.name] = prosa
    return fora


def _catalogos_existentes() -> set[str]:
    """Os idiomas que o repositório de fato entrega hoje (`en`, `pt_BR`)."""
    return {arquivo.stem for arquivo in DIR_CATALOGOS.glob("*.po")}


def _paginas_que_ensinam() -> list[Path]:
    paginas: list[Path] = []
    for alvo in ALVOS_QUE_ENSINAM:
        caminho = RAIZ / alvo
        if caminho.is_dir():
            paginas.extend(sorted(caminho.rglob("*.md")))
        elif caminho.is_file():
            paginas.append(caminho)
    return paginas


def _convites_em(texto: str, catalogos: set[str]) -> list[tuple[int, str]]:
    """As linhas que convidam a traduzir, com o motivo de cada uma."""
    achados: list[tuple[int, str]] = []
    for numero, linha in enumerate(texto.splitlines(), start=1):
        if _COMANDO_QUE_CRIA_IDIOMA.search(linha):
            achados.append((numero, "receita: o comando que cria catálogo novo"))
            continue
        citado = _CATALOGO_CITADO.search(linha)
        if citado and citado.group(1) not in catalogos:
            achados.append(
                (numero, f"catálogo inexistente `po/{citado.group(1)}.po`")
            )
            continue
        if _CABECALHO_DE_RECEITA.match(linha):
            achados.append((numero, "cabeçalho com forma de receita"))
            continue
        if any(marca.search(linha) for marca in _PONTEIRO_PARA_A_RECEITA):
            achados.append((numero, "ponteiro para a receita"))
    return achados


# ---------------------------------------------------------------------------
# A condição: o encanamento está ligado nas telas?
# ---------------------------------------------------------------------------


def test_o_encanamento_de_i18n_nao_alcanca_o_texto_vivo_das_abas() -> None:
    """Ancora a medição que sustenta a decisão dela, e a mantém honesta.

    Se alguém ligar o encanamento de verdade, este teste reprova PRIMEIRO, com
    nome e sobrenome, em vez de o portão de baixo afrouxar em silêncio. É o
    lembrete de que a decisão tem uma condição, e a condição tem número.
    """
    fora = _modulos_que_escrevem_portugues_cru(DIR_ACOES)
    total = len(list(DIR_ACOES.glob("*.py")))

    assert total == 18, (
        f"`app/actions/` tem {total} módulos, não 18. A contagem citada em "
        "`.github/CONTRIBUTING.md`, `docs/usage/flatpak.md` e "
        "`docs/usage/troubleshooting.md` precisa mudar junto."
    )
    assert len(fora) == 15, (
        f"agora são {len(fora)} módulos escrevendo português fora da função de "
        f"tradução, não 15: {', '.join(sorted(fora))}. Se o número CAIU, é "
        "trabalho bom — atualize as três páginas que o citam. Se chegou a "
        "zero, o convite a traduzir deixou de ser falso e pode voltar."
    )
    # O volume entra como PISO, não como igualdade: 561 é a medição datada de
    # 07/08/2026, e qualquer edição de frase em qualquer um dos 15 a move. Um
    # portão que exigisse o número exato reprovaria trabalho alheio inocente e
    # seria desligado na terceira vez — que é como portão vira decoração. O que
    # precisa doer é o volume DESABAR, porque aí a premissa mudou.
    assert sum(fora.values()) >= 400, (
        f"os 15 módulos somam agora {sum(fora.values())} literais acentuados; "
        "eram 561 em 07/08/2026. Uma queda desta ordem significa que o texto "
        "vivo das abas mudou de lugar, e a decisão da língua precisa ser "
        "remedida antes de continuar valendo como está escrita."
    )


def test_os_tres_modulos_que_ja_traduzem_continuam_traduzindo() -> None:
    """O encanamento existente não pode sumir enquanto ninguém olha.

    A decisão dela diz explicitamente que o i18n **não** é removido. Estes três
    são a prova viva de que ele funciona; perdê-los seria arrancar trabalho bom
    para provar um ponto, que é o que ela recusou.
    """
    com_encanamento = sorted(
        fonte.name
        for fonte in DIR_ACOES.glob("*.py")
        if _importa_a_funcao_de_traducao(
            ast.parse(fonte.read_text(encoding="utf-8"))
        )
    )

    assert com_encanamento == [
        "footer_actions.py",
        "lightbar_actions.py",
        "status_actions.py",
    ], (
        "mudou quem importa a função de tradução em `app/actions/`: "
        f"{', '.join(com_encanamento)}. Ganhar módulo aqui é bom e esperado; "
        "PERDER é regressão — o encanamento de i18n não se remove."
    )


def test_os_catalogos_entregues_continuam_no_repositorio() -> None:
    """`po/en.po` e `po/pt_BR.po` são o encanamento que fica."""
    assert _catalogos_existentes() >= {"en", "pt_BR"}, (
        "sumiu catálogo de `po/`. A decisão de 07/08/2026 tira o CONVITE, não o "
        "encanamento — ele está correto e continua."
    )


# ---------------------------------------------------------------------------
# O portão: enquanto a condição não for satisfeita, o convite não volta.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "documento",
    [p.relative_to(RAIZ).as_posix() for p in _paginas_que_ensinam()],
)
def test_nenhuma_pagina_que_ensina_convida_a_traduzir(documento: str) -> None:
    """Enquanto houver português cru nas telas, a receita não pode existir.

    Repare no `if not fora: return`: o portão é CONDICIONAL de verdade. Ligado o
    encanamento, ele libera o convite sozinho — porque a decisão dela foi contra
    a promessa falsa, não contra traduzir.
    """
    fora = _modulos_que_escrevem_portugues_cru(DIR_ACOES)
    if not fora:
        return

    achados = _convites_em(
        (RAIZ / documento).read_text(encoding="utf-8"), _catalogos_existentes()
    )

    assert not achados, (
        f"{documento} voltou a convidar a traduzir: "
        + "; ".join(f"linha {n} ({motivo})" for n, motivo in achados)
        + ". Hoje "
        + f"{len(fora)} dos {len(list(DIR_ACOES.glob('*.py')))} módulos de "
        "`app/actions/` escrevem português direto, então a tradução não "
        "alcançaria a janela e o convite seria falso. Decisão de 07/08/2026, "
        "em `docs/process/sprints/"
        "2026-08-07-LINGUA-DO-PRODUTO-01-o-convite-a-traduzir-era-falso.md`."
    )


def test_a_contributing_diz_o_que_o_convite_perdido_foi_substituido_por() -> None:
    """Tirar sem explicar é apagar. A página tem de carregar a decisão."""
    texto = (RAIZ / ".github" / "CONTRIBUTING.md").read_text(encoding="utf-8")

    for esperado in (
        "07/08/2026",
        "português do Brasil é a língua",
        "encanamento",
    ):
        assert esperado in texto, (
            f"`.github/CONTRIBUTING.md` não diz {esperado!r}. A seção de "
            "traduções foi removida em 07/08/2026 e o lugar dela é de quem "
            "explica a decisão — senão a próxima pessoa reabre o convite."
        )


# ---------------------------------------------------------------------------
# O critério medido contra si mesmo: sem isto, a metade condicional do portão
# seria afirmação, não medição.
# ---------------------------------------------------------------------------


def test_o_criterio_reconhece_o_encanamento_ligado(tmp_path: Path) -> None:
    """Módulo com `_` importado não conta como português cru, e vice-versa."""
    (tmp_path / "traduzido.py").write_text(
        "from hefesto_dualsense4unix.utils.i18n import _\n"
        'TEXTO = _("Não foi possível aplicar")\n',
        encoding="utf-8",
    )
    (tmp_path / "cru.py").write_text(
        'TEXTO = "Não foi possível aplicar"\n', encoding="utf-8"
    )
    (tmp_path / "sem_prosa.py").write_text('CHAVE = "trigger_mode"\n', encoding="utf-8")

    fora = _modulos_que_escrevem_portugues_cru(tmp_path)

    assert fora == {"cru.py": 1}, (
        "o critério do portão errou: só o módulo com prosa acentuada e sem a "
        f"função de tradução deveria contar, e ele devolveu {fora}."
    )


def test_o_criterio_enxerga_a_receita_e_ignora_quem_so_fala_de_traducao() -> None:
    """As quatro marcas mordem a receita; a prosa honesta passa ilesa.

    A segunda metade é a que impede o portão de virar ruído: são frases reais
    de `docs/usage/integrating-mods.md`, de `README.md` e da própria explicação
    da decisão. Nenhuma delas é convite, e nenhuma delas pode reprovar.
    """
    catalogos = {"en", "pt_BR"}

    receita = (
        "### Adicionar idioma novo (comunidade)\n"
        "```bash\n"
        "bash scripts/i18n_extract.sh --add fr_FR\n"
        "$EDITOR po/fr_FR.po\n"
        "```\n"
        "Para adicionar um novo idioma (ES, FR, DE), ver a seção "
        '"Contribuir traduções".\n'
    )
    achados = _convites_em(receita, catalogos)
    assert {motivo for _numero, motivo in achados} == {
        "receita: o comando que cria catálogo novo",
        "catálogo inexistente `po/fr_FR.po`",
        "cabeçalho com forma de receita",
        "ponteiro para a receita",
    }, f"as quatro marcas não pegaram a receita inteira: {achados}"

    honesto = (
        "## Localização (i18n)\n"
        "Instrução conhecida que falhou: modo de gatilho sem tradução.\n"
        "As curvas prontas ainda não têm tradução — são curvas de força.\n"
        "O runtime sobrescreve `/app/share/locale/` para vários idiomas.\n"
        "O bundle embarca os catálogos `po/en.po` e `po/pt_BR.po`.\n"
        "A janela traduz `resultado=aplicado` para uma frase em português.\n"
        "O português do Brasil é a língua do produto; o encanamento fica.\n"
    )
    assert _convites_em(honesto, catalogos) == [], (
        "o portão reprovou prosa que só FALA de tradução — é assim que um "
        "portão vira ruído e a casa aprende a ignorá-lo."
    )
