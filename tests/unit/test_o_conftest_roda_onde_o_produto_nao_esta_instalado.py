"""O `conftest` da suíte roda onde o produto NÃO está instalado.

MEDIDO em 21/08/2026, e o defeito estava vermelho havia um dia inteiro nos dois
repositórios sem ninguém ver.

O `ci.yml` tem jobs que rodam pytest com `pip install pytest` e MAIS NADA — o
"A casa sabe e o produto não faz" é o exemplar: doze segundos, lê a árvore com
AST e nunca importa `hefesto_dualsense4unix`. Não instalar o produto ali é
desenho, não esquecimento: é o que mantém o portão barato o bastante para rodar
em todo push.

O que quebrou: a fixture `_nenhum_sysfs_vivo_na_varredura_de_vpad` nasceu em
20/08 (`e0a5837`) `autouse=True` com escopo de SESSÃO, e importa o produto para
apontar a varredura de `/sys/class/input` ao vazio. Fixture autouse de sessão
roda em TODA sessão de pytest — inclusive naquele job. Resultado: 28 testes que
não tocam em vpad estouraram com `ModuleNotFoundError`, e o CI de `main` ficou
vermelho no repositório dela e no do dono original.

A família do defeito é a de sempre nesta casa: uma peça correta no lugar certo,
que assume um ambiente que nem todo executor tem. O irmão mais próximo é a
`_nenhum_uinput_de_verdade`, logo acima dela no mesmo arquivo — que não importa
o produto e por isso nunca teve este problema.

A REGRA que este portão cobra é estreita de propósito: fixture autouse de
sessão do `tests/conftest.py` que importe o produto tem de tolerar a ausência
dele. Não proíbe o import — proíbe o import que derruba quem não pediu nada.

Morde: tire o `try` de volta da
`_nenhum_sysfs_vivo_na_varredura_de_vpad` e este arquivo reprova, nomeando a
fixture.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest
import yaml

RAIZ = Path(__file__).resolve().parents[2]
CI = RAIZ / ".github" / "workflows" / "ci.yml"
CONFTEST = RAIZ / "tests" / "conftest.py"

#: O pacote do produto. Import dele é o que exige o pacote instalado.
PACOTE = "hefesto_dualsense4unix"

#: O que um `except` precisa capturar para que o import seja tolerante.
TRATA_AUSENCIA = frozenset({"ModuleNotFoundError", "ImportError"})

#: Como o `ci.yml` instala o produto quando quer o produto. Um job que roda
#: pytest sem NENHUMA destas formas é um job leve.
#:
#: AS ASPAS SÃO O DETALHE QUE ME PEGOU, em 21/08/2026: a primeira versão destes
#: padrões exigia `-e .` e o `ci.yml` escreve `pip install -e ".[dev]"`. O
#: detector devolveu `lint-test` e `gtk-real` como jobs LEVES — os dois maiores
#: da casa, que instalam o produto inteiro. O assert principal não usava a
#: lista, então nada reprovou: a mentira ia sair só na MENSAGEM de erro, para
#: quem estivesse consertando às pressas. Daí o teste de aferição no fim deste
#: arquivo, que trava quem é leve e quem não é.
FORMAS_DE_INSTALAR = (
    re.compile(r"""pip\s+install\s+(?:[^\n]*?\s)?-e\s+["']?\."""),
    re.compile(r"""pip\s+install\s+(?:[^\n]*?\s)?["']?\.(?:\[|["']|\s|$)"""),
    re.compile(r"""pip\s+install\s+(?:[^\n]*?\s)?["']?dist/"""),
    re.compile(r"""pip\s+install\s+(?:[^\n]*?\s)?[^\s"']+\.whl"""),
)

#: Os jobs que rodam pytest e instalam o produto. Digitados de propósito: são a
#: contraprova do detector, e um detector conferido contra a sua própria saída
#: não é conferência nenhuma.
INSTALAM_O_PRODUTO = frozenset({"lint-test", "gtk-real"})


def _corridas_do_job(job: dict) -> str:
    """Todo o texto de `run:` de um job, num bloco só."""
    partes = []
    for passo in job.get("steps") or []:
        run = passo.get("run")
        if isinstance(run, str):
            partes.append(run)
    return "\n".join(partes)


def jobs_leves() -> dict[str, str]:
    """Jobs que RODAM pytest e NÃO instalam o produto, pelo nome do job."""
    dados = yaml.safe_load(CI.read_text(encoding="utf-8"))
    leves: dict[str, str] = {}
    for nome, job in (dados.get("jobs") or {}).items():
        texto = _corridas_do_job(job)
        if "pytest" not in texto:
            continue
        if any(forma.search(texto) for forma in FORMAS_DE_INSTALAR):
            continue
        leves[nome] = texto
    return leves


def _e_autouse_de_sessao(no: ast.FunctionDef) -> bool:
    """A função é uma fixture `autouse=True` com escopo de sessão?"""
    for enfeite in no.decorator_list:
        if not isinstance(enfeite, ast.Call):
            continue
        alvo = enfeite.func
        nome = alvo.attr if isinstance(alvo, ast.Attribute) else getattr(alvo, "id", "")
        if nome != "fixture":
            continue
        autouse = escopo = None
        for chave in enfeite.keywords:
            if chave.arg == "autouse" and isinstance(chave.value, ast.Constant):
                autouse = chave.value.value
            if chave.arg == "scope" and isinstance(chave.value, ast.Constant):
                escopo = chave.value.value
        if autouse is True and escopo == "session":
            return True
    return False


def _importa_o_produto(no: ast.AST) -> list[ast.stmt]:
    """Os nós de import do produto dentro desta função."""
    achados: list[ast.stmt] = []
    for filho in ast.walk(no):
        if isinstance(filho, ast.ImportFrom):
            raizes = [(filho.module or "").split(".")[0]]
        elif isinstance(filho, ast.Import):
            raizes = [a.name.split(".")[0] for a in filho.names]
        else:
            continue
        if PACOTE in raizes:
            achados.append(filho)
    return achados


def _protegido_por_try(funcao: ast.FunctionDef, alvo: ast.stmt) -> bool:
    """O import está dentro de um `try` que trata `ModuleNotFoundError`?"""
    for filho in ast.walk(funcao):
        if not isinstance(filho, ast.Try):
            continue
        no_corpo = any(alvo is dentro for corpo in filho.body for dentro in ast.walk(corpo))
        if not no_corpo:
            # Estar no `except` ou no `finally` não protege — protege estar no
            # bloco que o `try` vigia.
            continue
        for tratador in filho.handlers:
            if any(n in TRATA_AUSENCIA for n in _nomes_do_tratador(tratador)):
                return True
    return False


def _nomes_do_tratador(tratador: ast.ExceptHandler) -> list[str]:
    """Os nomes de exceção que este `except` captura."""
    tipo = tratador.type
    if isinstance(tipo, ast.Name):
        return [tipo.id]
    if isinstance(tipo, ast.Tuple):
        return [e.id for e in tipo.elts if isinstance(e, ast.Name)]
    return []


def fixtures_de_sessao_que_importam_o_produto() -> list[tuple[str, bool]]:
    """`(nome_da_fixture, esta_protegida)` para cada autouse de sessão."""
    arvore = ast.parse(CONFTEST.read_text(encoding="utf-8"))
    saida: list[tuple[str, bool]] = []
    for no in ast.walk(arvore):
        if not isinstance(no, ast.FunctionDef):
            continue
        if not _e_autouse_de_sessao(no):
            continue
        imports = _importa_o_produto(no)
        if not imports:
            continue
        saida.append((no.name, all(_protegido_por_try(no, i) for i in imports)))
    return saida


def test_o_ci_ainda_tem_job_que_roda_pytest_sem_o_produto() -> None:
    """A razão desta guarda continua de pé.

    Se um dia todo job que roda pytest passar a instalar o produto, esta guarda
    perde o motivo — e é melhor que ela AVISE do que envelheça calada cobrando
    uma regra sem dono.
    """
    leves = jobs_leves()
    assert leves, (
        "nenhum job do ci.yml roda pytest sem instalar o produto. Se isso é "
        "verdade de propósito, apague este arquivo com uma nota datada; se é "
        "acidente, o portão barato de doze segundos virou caro e ninguém viu."
    )


def test_toda_fixture_autouse_de_sessao_tolera_o_produto_ausente() -> None:
    """O que estourou em 20/08 não volta a estourar.

    Reprova nomeando a fixture, porque `ModuleNotFoundError` em 28 testes que
    não tocam no assunto não aponta para a causa — foi preciso ler o traceback
    inteiro do runner para chegar nela.
    """
    desprotegidas = [nome for nome, ok in fixtures_de_sessao_que_importam_o_produto() if not ok]
    assert not desprotegidas, (
        "fixture(s) autouse de escopo de sessão em tests/conftest.py importam "
        f"{PACOTE} sem tolerar a ausência dele: {', '.join(desprotegidas)}. "
        f"Elas rodam em TODA sessão de pytest, inclusive nos jobs leves do "
        f"ci.yml ({', '.join(sorted(jobs_leves()))}), que instalam só o pytest. "
        "Envolva o import num try/except ModuleNotFoundError estreito."
    )


@pytest.mark.parametrize("fonte, esperado", [
    (
        "@pytest.fixture(autouse=True, scope='session')\n"
        "def f():\n"
        "    from hefesto_dualsense4unix.integrations import no_do_vpad\n"
        "    yield\n",
        False,
    ),
    (
        "@pytest.fixture(autouse=True, scope='session')\n"
        "def f():\n"
        "    try:\n"
        "        from hefesto_dualsense4unix.integrations import no_do_vpad\n"
        "    except ModuleNotFoundError:\n"
        "        yield\n"
        "        return\n"
        "    yield\n",
        True,
    ),
])
def test_o_detector_separa_o_protegido_do_desprotegido(fonte: str, esperado: bool) -> None:
    """A régua mede o que promete.

    Sem isto, um detector que devolvesse `True` para tudo deixaria o teste
    acima verde para sempre — o defeito que esta casa chama de "portão que não
    mede o que promete".
    """
    arvore = ast.parse(fonte)
    funcao = next(n for n in ast.walk(arvore) if isinstance(n, ast.FunctionDef))
    assert _e_autouse_de_sessao(funcao) is True
    imports = _importa_o_produto(funcao)
    assert imports, "o detector perdeu o import do produto"
    assert all(_protegido_por_try(funcao, i) for i in imports) is esperado


def test_o_detector_de_job_leve_nao_chama_de_leve_quem_instala_o_produto() -> None:
    """A régua dos JOBS mede o que promete.

    `lint-test` e `gtk-real` rodam `pip install -e ".[dev]"`. Um detector que os
    chamasse de leves mandaria a próxima pessoa procurar o defeito no lugar
    errado — e foi o que a primeira versão deste arquivo fez, por causa das
    aspas.
    """
    leves = set(jobs_leves())
    intrusos = sorted(INSTALAM_O_PRODUTO & leves)
    assert not intrusos, (
        f"o detector chamou de leve quem instala o produto: {', '.join(intrusos)}. "
        "Confira FORMAS_DE_INSTALAR contra as linhas de `pip install` do ci.yml."
    )
    for nome in sorted(INSTALAM_O_PRODUTO):
        assert nome in yaml.safe_load(CI.read_text(encoding="utf-8"))["jobs"], (
            f"o job {nome} sumiu do ci.yml — esta lista envelheceu calada."
        )
