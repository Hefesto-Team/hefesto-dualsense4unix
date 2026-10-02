"""O convite a traduzir só pode existir com o encanamento ligado nas telas."""
from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]

DIR_ACOES = RAIZ / "src" / "hefesto_dualsense4unix" / "app" / "actions"


def _modulos_de_acoes() -> list[Path]:
    """Todo `.py` de `app/actions/`, inclusive os de dentro de um pacote."""
    return sorted(
        caminho
        for caminho in DIR_ACOES.rglob("*.py")
        if "__pycache__" not in caminho.parts
    )

DIR_CATALOGOS = RAIZ / "po"

ALVOS_QUE_ENSINAM = (
    "README.md",
    ".github/CONTRIBUTING.md",
    "docs/usage",
    "docs/adr",
    "docs/protocol",
)

_ACENTUADA = re.compile(r"[áàâãéêíóôõúüçÁÀÂÃÉÊÍÓÔÕÚÜÇ]")

_COMANDO_QUE_CRIA_IDIOMA = re.compile(r"i18n_extract\.sh\s+--add")

_CATALOGO_CITADO = re.compile(r"\bpo/([A-Za-z0-9_.-]+)\.po\b")

_CABECALHO_DE_RECEITA = re.compile(
    r"^#{1,6}\s.*\b(adicionar|acrescentar|criar|incluir|contribuir)\b"
    r"[^\n]{0,40}\b(idioma|l[ií]ngua|tradu[çc])",
    re.IGNORECASE,
)

_PONTEIRO_PARA_A_RECEITA = (
    re.compile(
        r"\b(para|como)\s+(adicionar|acrescentar|criar|incluir)\s+"
        r"(um\s+|uma\s+)?(novo\s+|nova\s+)?(idioma|l[ií]ngua|tradu[çc][ãa]o)",
        re.IGNORECASE,
    ),
    re.compile(r"contribuir\s+tradu[çc]", re.IGNORECASE),
)


def _importa_a_funcao_de_traducao(arvore: ast.Module) -> bool:
    """O módulo puxa o `_` de `utils.i18n` (ou o `gettext` cru)?"""
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
    """Os módulos com prosa acentuada e SEM a função de tradução."""
    fora: dict[str, int] = {}
    for fonte in sorted(diretorio.rglob("*.py")):
        if "__pycache__" in fonte.parts:
            continue
        arvore = ast.parse(fonte.read_text(encoding="utf-8"))
        if _importa_a_funcao_de_traducao(arvore):
            continue
        prosa = _literais_de_prosa(arvore)
        if prosa:
            fora[fonte.relative_to(diretorio).as_posix()] = prosa
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


def test_o_encanamento_de_i18n_nao_alcanca_o_texto_vivo_das_abas() -> None:
    """Ancora a medição que sustenta a decisão dela, e a mantém honesta."""
    fora = _modulos_que_escrevem_portugues_cru(DIR_ACOES)
    total = len(_modulos_de_acoes())

    assert total == 34, (
        f"`app/actions/` tem {total} módulos, não 34. A contagem citada em "
        "`.github/CONTRIBUTING.md`, `docs/usage/flatpak.md` e "
        "`docs/usage/troubleshooting.md` precisa mudar junto."
    )
    assert len(fora) == 25, (
        f"agora são {len(fora)} módulos escrevendo português fora da função de "
        f"tradução, não 25: {', '.join(sorted(fora))}. Se o número CAIU, é "
        "trabalho bom — atualize as três páginas que o citam. Se chegou a "
        "zero, o convite a traduzir deixou de ser falso e pode voltar."
    )
    assert sum(fora.values()) >= 400, (
        f"os {len(fora)} módulos somam agora {sum(fora.values())} literais "
        "acentuados; "
        "eram 561 em 07/08/2026. Uma queda desta ordem significa que o texto "
        "vivo das abas mudou de lugar, e a decisão da língua precisa ser "
        "remedida antes de continuar valendo como está escrita."
    )


def test_os_modulos_que_ja_traduzem_continuam_traduzindo() -> None:
    """O encanamento existente não pode sumir enquanto ninguém olha.

    A decisão dela diz explicitamente que o i18n **não** é removido. Estes
    módulos são a prova viva de que ele funciona; perdê-los seria arrancar
    trabalho bom para provar um ponto, que é o que ela recusou.

    Eram três até 21/08/2026, quando a aba Configurações entrou já traduzindo.
    O nome do teste dizia "os três" e passou a mentir — por isso mudou. Em
    22/08/2026 viraram cinco, e depois nove: as cinco seções do pacote `config/`
    também põem texto na tela e também traduzem.

    **A ASSERÇÃO É DE PISO, E NÃO DE IGUALDADE, DESDE 22/08/2026.** Ela era um
    `==` contra uma lista congelada, e o `==` contradizia a própria mensagem de
    falha deste teste: *"ganhar módulo aqui é bom e esperado; PERDER é
    regressão"*. Com o `==`, ganhar reprovava igual a perder — e reprovou, na
    leva que deu conteúdo às cinco seções. Um portão que acusa quem fez a coisa
    certa ensina a próxima pessoa a desligá-lo, que é a lição que esta casa já
    pagou em 13/08 com o `portao_a_casa_sabe_e_o_produto_nao_faz`.

    O piso é a lista dos que JÁ traduziam. Perder qualquer um reprova; ganhar,
    não.
    """
    com_encanamento = {
        fonte.relative_to(DIR_ACOES).as_posix()
        for fonte in _modulos_de_acoes()
        if _importa_a_funcao_de_traducao(
            ast.parse(fonte.read_text(encoding="utf-8"))
        )
    }

    piso = {
        "config/moldura.py",
        "footer_actions.py",
        "lightbar_actions.py",
        "status_actions.py",
    }

    assert piso <= com_encanamento, (
        "PERDEU encanamento de tradução em `app/actions/`: "
        f"{', '.join(sorted(piso - com_encanamento))}. Ganhar módulo aqui é bom "
        "e esperado; perder é regressão — o i18n não se remove."
    )


def test_os_catalogos_entregues_continuam_no_repositorio() -> None:
    """`po/en.po` e `po/pt_BR.po` são o encanamento que fica."""
    assert _catalogos_existentes() >= {"en", "pt_BR"}, (
        "sumiu catálogo de `po/`. A decisão de 07/08/2026 tira o CONVITE, não o "
        "encanamento — ele está correto e continua."
    )


@pytest.mark.parametrize(
    "documento",
    [p.relative_to(RAIZ).as_posix() for p in _paginas_que_ensinam()],
)
def test_nenhuma_pagina_que_ensina_convida_a_traduzir(documento: str) -> None:
    """Enquanto houver português cru nas telas, a receita não pode existir."""
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
        + f"{len(fora)} dos {len(_modulos_de_acoes())} módulos de "
        "`app/actions/` escrevem português direto, então a tradução não "
        "alcançaria a janela e o convite seria falso. Decisão de 07/08/2026, "
        "em `docs/process/sprints/"
        "2026-08-07-LINGUA-DO-PRODUTO-01-o-convite-a-traduzir-era-falso.md`."
    )


def test_a_contributing_diz_o_que_o_convite_perdido_foi_substituido_por() -> None:
    """Tirar sem explicar é apagar. A página tem de carregar a decisão."""
    texto = (RAIZ / ".github" / "CONTRIBUTING.md").read_text(encoding="utf-8")

    for esperado in (
        "português do Brasil é a língua",
        "encanamento",
    ):
        assert esperado in texto, (
            f"`.github/CONTRIBUTING.md` não diz {esperado!r}. A seção de "
            "traduções saiu da página, e o lugar dela é de quem explica a "
            "decisão; senão a próxima pessoa reabre o convite."
        )


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
    """As quatro marcas mordem a receita; a prosa honesta passa ilesa."""
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
