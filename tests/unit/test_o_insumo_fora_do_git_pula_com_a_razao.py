"""INSUMO-FORA-DO-GIT-01 — o marcador que pula COM A RAZÃO, e só com razão.

RELEASE-NO-CLONE-LIMPO-01, 20/09/2026. `docs/process/` é `.gitignore:178` e o
despacho de leva saiu junto (`.gitignore:189-195`). O `release.yml` roda
`pytest tests/unit` num CLONE LIMPO, onde nada disso existe: as réguas
versionadas cujo insumo saiu reprovavam por AMBIENTE e a esteira dos pacotes
caía ali. A cura é UM marcador (`tests/conftest.py`), não cento e vinte e nove
`if`s espalhados.

ESTE ARQUIVO É A RÉGUA DO MARCADOR, e ele tem de cobrir o arranjo DIFÍCIL. O
arranjo fácil é "faltou, então pula" — e um marcador que faça só isso é pior
do que o defeito que veio curar: ele esconde toda ausência, inclusive a que é
regressão de verdade. Por isso metade dos testes abaixo mede a RECUSA de pular.

AS SEIS MORDIDAS, arrancadas de verdade no `tests/conftest.py` em 20/09/2026,
vistas reprovar e devolvidas (as 13 daqui passam com a cura no lugar):

===  o que a mordida arranca  ==========================  reprovaram  ====
1. a razão perde o `.gitignore:<linha>`                            2
2. `motivo_do_pulo` devolve razão antes de olhar o disco           8
3. `motivo_do_pulo` pula TODA ausência, explicada ou não           4  ← a que importa
4. `_regra_que_exclui` digita o número em vez de ler o arquivo     3
5. `pytest_collection_modifyitems` sai do `conftest.py`            2
6. marcador sem caminho nenhum passa a ser aceito calado           2
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import textwrap
import uuid
from pathlib import Path

import pytest

from tests.conftest import (
    _regra_que_exclui,
    motivo_do_pulo,
    olhar_insumo,
)

RAIZ = Path(__file__).resolve().parents[2]

#: Os dois insumos que esta casa de fato perdeu para o `.gitignore`, e que o
#: `release.yml` não tem. Ficam aqui por NOME, e o número da linha vem sempre do
#: arquivo — ver `test_a_linha_do_gitignore_sai_do_arquivo_e_nao_deste_teste`.
OS_INSUMOS_QUE_NAO_VIAJAM = (
    "docs/process/sprints",
    "scripts/check_colisao_de_sprints.py",
)


def _arvore_de_mentira(raiz: Path, gitignore: str) -> Path:
    """Uma árvore com `.gitignore` próprio e nada dentro — o clone limpo em miniatura."""
    (raiz / ".gitignore").write_text(gitignore, encoding="utf-8")
    return raiz


# ═══════════════════════════════════════════════════════════════════════════
# 1. A RAZÃO — pulo calado é verde sobre nada
# ═══════════════════════════════════════════════════════════════════════════


def test_a_razao_nomeia_o_caminho_que_faltou_e_a_linha_que_o_exclui(
    tmp_path: Path,
) -> None:
    """MORDIDA 1: tirar `.gitignore:{numero}` de `InsumoDeclarado.razao`.

    Com a cura arrancada a razão vira "não veio" sobre um caminho sem
    procedência, e quem ler o `-rs` no clone limpo não tem como saber se aquilo
    é decisão desta casa ou arquivo perdido. Arrancada, vista reprovar nas duas
    asserções de baixo, devolvida.
    """
    raiz = _arvore_de_mentira(
        tmp_path,
        "# um comentário, que não conta linha de padrão\n*.pyc\ndocs/process/\n",
    )

    motivo = motivo_do_pulo("docs/process/sprints", raiz=raiz)

    assert motivo is not None
    assert "docs/process/sprints" in motivo, motivo
    assert ".gitignore:3" in motivo, (
        "a razão tem de dizer QUAL linha exclui o caminho — sem isso o pulo não "
        f"se distingue de arquivo perdido; saiu: {motivo}"
    )


def test_a_razao_diz_o_que_fazer_a_respeito(tmp_path: Path) -> None:
    """A razão não é só diagnóstico: ela diz o que fazer, nos dois cenários.

    Num clone limpo a ausência é esperada e não há nada a fazer; numa árvore de
    agente ela é a armadilha que o `CLAUDE.md` descreve, e o conserto é copiar
    os ignorados ANTES de medir. As duas leituras saem na mesma frase.
    """
    raiz = _arvore_de_mentira(tmp_path, "docs/process/\n")
    motivo = motivo_do_pulo("docs/process/sprints", raiz=raiz)
    assert motivo is not None
    assert "clone limpo" in motivo and "copie" in motivo, motivo


def test_marcador_sem_caminho_nenhum_e_recusado_na_origem() -> None:
    """MORDIDA 6: trocar o `raise ValueError` de `motivo_do_pulo` por `return None`.

    Um marcador sem caminho declarado é o pulo calado em pessoa: ele não tem o
    que olhar, logo nunca pularia — e passaria a vida dando verde sobre uma
    régua que ninguém mediu. Arrancada, `pytest.raises` reprovou; devolvida.
    """
    with pytest.raises(ValueError, match="pulo calado"):
        motivo_do_pulo()


# ═══════════════════════════════════════════════════════════════════════════
# 2. O ARRANJO DIFÍCIL — quando NÃO se pula
# ═══════════════════════════════════════════════════════════════════════════


def test_onde_o_insumo_veio_nao_ha_pulo(tmp_path: Path) -> None:
    """MORDIDA 2: fazer `motivo_do_pulo` devolver a razão antes de olhar o disco.

    Esta é a régua que impede o marcador de virar um `skip` universal: na
    árvore DELA e na de quem despacha os insumos estão no lugar, e ali nada
    pode mudar. Arrancada (razão devolvida sempre), reprovou aqui; devolvida.
    """
    raiz = _arvore_de_mentira(tmp_path, "docs/process/\n")
    (raiz / "docs" / "process" / "sprints").mkdir(parents=True)

    assert motivo_do_pulo("docs/process/sprints", raiz=raiz) is None


def test_a_ausencia_que_o_gitignore_nao_explica_nao_pula_nunca(tmp_path: Path) -> None:
    """MORDIDA 3, e é a do ARRANJO DIFÍCIL: pular toda ausência.

    O arranjo fácil — "o caminho não existe, então pula" — é o que quase todo
    marcador deste tipo faz, e é exatamente o verde sobre nada: um arquivo
    VERSIONADO que alguém apagou passaria a dispensar a régua que o mede, em
    silêncio, para sempre.

    A cura é perguntar ao dono: só pula o que o `.gitignore` explica. Arrancada
    (as duas linhas `if any(... regra is None ...): return None` fora), quatro
    testes reprovaram — este, o do lote contaminado, o do `!` e o do gancho —
    e as outras nove réguas deste arquivo continuaram VERDES. É isso que torna
    esta mordida a que importa: sem ela, nove verdes sobre um marcador que
    apagaria toda régua cujo arquivo alguém deletasse. Devolvida.
    """
    raiz = _arvore_de_mentira(tmp_path, "docs/process/\n")

    insumo = olhar_insumo("docs/usage/interface.md", raiz=raiz)
    assert not insumo.existe
    assert insumo.regra is None, "nada no `.gitignore` de mentira exclui docs/usage/"
    assert not insumo.nao_viaja

    assert motivo_do_pulo("docs/usage/interface.md", raiz=raiz) is None, (
        "sumiço de arquivo versionado é DEFEITO; esconder defeito atrás de "
        "`skip` é o que este bloco existe para impedir"
    )


def test_um_ausente_sem_regra_contamina_o_lote_inteiro(tmp_path: Path) -> None:
    """Declarar dois caminhos não compra dispensa para o que não tem regra.

    O caminho mais fácil de burlar a régua acima é declarar, ao lado do arquivo
    versionado que sumiu, um caminho ignorado qualquer — e deixar o marcador
    pular pelo segundo. Aqui isso não passa: basta UM ausente sem regra para o
    pulo inteiro ser recusado.
    """
    raiz = _arvore_de_mentira(tmp_path, "docs/process/\n")

    assert (
        motivo_do_pulo(
            "docs/process/sprints",  # ausente E ignorado
            "docs/usage/interface.md",  # ausente e SEM regra
            raiz=raiz,
        )
        is None
    )


def test_o_negado_do_gitignore_desfaz_a_dispensa(tmp_path: Path) -> None:
    """`!` posterior des-ignora, e então a ausência volta a ser defeito.

    O git resolve pela ÚLTIMA linha que casa. Uma leitura que parasse na
    primeira dispensaria um caminho que o repositório decidiu voltar a
    carregar — e a régua dele morreria calada.
    """
    raiz = _arvore_de_mentira(tmp_path, "docs/process/\n!docs/process/sprints\n")

    assert _regra_que_exclui(raiz, "docs/process/sprints") is None
    assert motivo_do_pulo("docs/process/sprints", raiz=raiz) is None
    assert _regra_que_exclui(raiz, "docs/process/agentes") == ".gitignore:1"


# ═══════════════════════════════════════════════════════════════════════════
# 3. O DONO DO NÚMERO — o `.gitignore`, não este arquivo
# ═══════════════════════════════════════════════════════════════════════════


def test_a_linha_do_gitignore_sai_do_arquivo_e_nao_deste_teste() -> None:
    """MORDIDA 4: cravar o número da linha em vez de lê-lo do `.gitignore`.

    O valor tem dono, e o dono é o `git`. Este teste não digita `178` em lugar
    nenhum: ele pergunta ao `git check-ignore -v`, que devolve arquivo e linha,
    e exige que a leitura do `conftest.py` diga a MESMA coisa. Arrancada (o
    número digitado à mão), reprovou no dia em que uma linha entrou acima.

    Pula com a razão onde não há git — e dizer por que se pulou é a regra desta
    casa, inclusive aqui.
    """
    if shutil.which("git") is None:
        pytest.skip("sem `git` nesta máquina: não há a quem perguntar a linha")
    if not (RAIZ / ".git").exists():
        pytest.skip("esta árvore não tem `.git`: `check-ignore` não responde")

    for relativo in OS_INSUMOS_QUE_NAO_VIAJAM:
        processo = subprocess.run(
            ["git", "check-ignore", "-v", "--no-index", "--", relativo],
            cwd=str(RAIZ),
            capture_output=True,
            text=True,
            check=False,
        )
        assert processo.returncode == 0, (
            f"o git diz que `{relativo}` NÃO é ignorado — se o `.gitignore` "
            "mudou, esta lista mudou junto: "
            f"{processo.stdout}{processo.stderr}"
        )
        # `<arquivo>:<linha>:<padrão>\t<caminho>`
        arquivo, linha, _resto = processo.stdout.split("\t", 1)[0].split(":", 2)
        do_git = f"{arquivo}:{linha}"

        nosso = _regra_que_exclui(RAIZ, relativo)
        assert nosso == do_git, (
            f"a leitura do `.gitignore` do conftest diz {nosso} para "
            f"`{relativo}` e o git diz {do_git}"
        )


def test_os_insumos_que_nao_viajam_continuam_sem_viajar() -> None:
    """A lista deste arquivo não pode envelhecer calada.

    Se um destes dois voltar para o repositório, a dispensa que ele justifica
    tem de sair junto — e o lugar de descobrir isso é aqui, não num clone
    limpo seis semanas depois.
    """
    for relativo in OS_INSUMOS_QUE_NAO_VIAJAM:
        assert _regra_que_exclui(RAIZ, relativo) is not None, (
            f"`{relativo}` deixou de ser ignorado: reveja quem o dispensa"
        )


def test_o_marcador_esta_registrado(pytestconfig: pytest.Config) -> None:
    """Quem responde se o marcador existe é o pytest, não uma cópia da string.

    Marcador não registrado vira `PytestUnknownMarkWarning` e morre sob
    `--strict-markers` — e o `release.yml` é exatamente onde alguém acrescenta
    `--strict-markers` sem avisar.
    """
    registrados = "\n".join(pytestconfig.getini("markers"))
    assert "insumo_fora_do_git" in registrados, registrados


# ═══════════════════════════════════════════════════════════════════════════
# 4. A FIAÇÃO — o gancho pulando de verdade, medido por pytest de verdade
# ═══════════════════════════════════════════════════════════════════════════
#
# As sete acima medem a FUNÇÃO. Estas duas medem o GANCHO, que é outra coisa:
# uma função perfeita num `conftest.py` que ninguém chama não pula nada, e foi
# assim que a régua do rótulo do gravador deu verde por 540 execuções. O
# subprocesso roda o pytest desta árvore sobre um módulo de mentira nascido
# DENTRO de `tests/unit/` — é a única forma de o `tests/conftest.py` de verdade
# entrar na conta.

_TEMPLATE_DO_MODULO = '''\
"""Módulo de mentira do INSUMO-FORA-DO-GIT-01 — apagado no `finally`."""

import pytest


@pytest.mark.insumo_fora_do_git({alvos})
def test_de_mentira():
    assert False, "este teste nunca deveria RODAR quando o insumo é dispensado"
'''


def _rodar_pytest_sobre(modulo: Path) -> subprocess.CompletedProcess[str]:
    ambiente = dict(os.environ)
    ambiente["PYTHONDONTWRITEBYTECODE"] = "1"
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            str(modulo.relative_to(RAIZ)),
            "-rs",
            "-q",
            "--no-header",
            "-p",
            "no:cacheprovider",
        ],
        cwd=str(RAIZ),
        capture_output=True,
        text=True,
        env=ambiente,
        check=False,
    )


def _modulo_de_mentira(*alvos: str) -> Path:
    nome = f"test_zz_insumo_de_mentira_{uuid.uuid4().hex[:8]}.py"
    caminho = RAIZ / "tests" / "unit" / nome
    caminho.write_text(
        _TEMPLATE_DO_MODULO.format(alvos=", ".join(repr(a) for a in alvos)),
        encoding="utf-8",
    )
    return caminho


def test_o_gancho_do_conftest_pula_de_verdade_e_diz_por_que() -> None:
    """MORDIDA 5: tirar `pytest_collection_modifyitems` do `tests/conftest.py`.

    Sem o gancho o marcador vira decoração: o teste de mentira RODA e reprova
    (`assert False`), que é justamente o que o `release.yml` via. Arrancado o
    gancho, este teste reprovou com `1 failed` no lugar de `1 skipped`;
    devolvido.

    O alvo é um arquivo que NUNCA existe debaixo de `docs/process/`, que é
    ignorado: assim o resultado é o mesmo na árvore dela (onde a pasta existe) e
    no clone limpo (onde não existe) — a régua não pode medir a máquina.
    """
    modulo = _modulo_de_mentira(f"docs/process/NAO-EXISTE-{uuid.uuid4().hex}.md")
    try:
        processo = _rodar_pytest_sobre(modulo)
    finally:
        modulo.unlink(missing_ok=True)

    saida = processo.stdout + processo.stderr
    assert "1 skipped" in saida, saida[-3000:]
    assert "INSUMO-FORA-DO-GIT-01" in saida, (
        "pulou, mas não disse por quê — pulo calado é verde sobre nada:\n"
        + saida[-3000:]
    )
    assert ".gitignore:" in saida, saida[-3000:]


def test_o_gancho_nao_pula_o_que_o_gitignore_nao_explica() -> None:
    """O arranjo DIFÍCIL atravessando o gancho inteiro, não só a função.

    Mesmo módulo de mentira, mesma marca — só muda o alvo: um caminho ausente
    que nenhuma linha do `.gitignore` cobre. O teste tem de RODAR e reprovar.
    Um gancho que pulasse por ausência daria `1 skipped` aqui e apagaria toda
    régua cujo arquivo alguém tivesse deletado.
    """
    modulo = _modulo_de_mentira(f"docs/usage/NAO-EXISTE-{uuid.uuid4().hex}.md")
    try:
        processo = _rodar_pytest_sobre(modulo)
    finally:
        modulo.unlink(missing_ok=True)

    saida = processo.stdout + processo.stderr
    assert "1 failed" in saida, (
        "o gancho dispensou uma ausência que o git não explica:\n" + saida[-3000:]
    )


def test_o_gancho_recusa_o_marcador_sem_caminho() -> None:
    """MORDIDA 6, do lado do gancho: aceitar `@pytest.mark.insumo_fora_do_git`.

    Sem argumento nenhum não há o que olhar, e o item passaria incólume — uma
    marca que não faz nada é pior que nenhuma, porque quem lê o código acredita
    nela. A recusa é `UsageError` na coleta, alto. Arrancada (o `raise` trocado
    por `continue`), o teste de mentira passou a RODAR e este teste reprovou;
    devolvida.
    """
    nome = f"test_zz_insumo_sem_caminho_{uuid.uuid4().hex[:8]}.py"
    modulo = RAIZ / "tests" / "unit" / nome
    modulo.write_text(
        textwrap.dedent(
            '''\
            """Módulo de mentira do INSUMO-FORA-DO-GIT-01 — apagado no `finally`."""

            import pytest


            @pytest.mark.insumo_fora_do_git
            def test_de_mentira():
                assert True
            '''
        ),
        encoding="utf-8",
    )
    try:
        processo = _rodar_pytest_sobre(modulo)
    finally:
        modulo.unlink(missing_ok=True)

    saida = processo.stdout + processo.stderr
    assert processo.returncode != 0, saida[-3000:]
    assert "pulo calado" in saida, saida[-3000:]
