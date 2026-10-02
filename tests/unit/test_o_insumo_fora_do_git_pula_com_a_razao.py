"""INSUMO-FORA-DO-GIT-01 — o marcador que pula COM A RAZÃO, e só com razão."""

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

OS_INSUMOS_QUE_NAO_VIAJAM = (
    "docs/process/sprints",
    "scripts/check_colisao_de_sprints.py",
)


def _arvore_de_mentira(raiz: Path, gitignore: str) -> Path:
    """Uma árvore com `.gitignore` próprio e nada dentro — o clone limpo em miniatura."""
    (raiz / ".gitignore").write_text(gitignore, encoding="utf-8")
    return raiz


def test_a_razao_nomeia_o_caminho_que_faltou_e_a_linha_que_o_exclui(
    tmp_path: Path,
) -> None:
    """MORDIDA 1: tirar `.gitignore:{numero}` de `InsumoDeclarado.razao`."""
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
    """A razão não é só diagnóstico: ela diz o que fazer, nos dois cenários."""
    raiz = _arvore_de_mentira(tmp_path, "docs/process/\n")
    motivo = motivo_do_pulo("docs/process/sprints", raiz=raiz)
    assert motivo is not None
    assert "clone limpo" in motivo and "copie" in motivo, motivo


def test_marcador_sem_caminho_nenhum_e_recusado_na_origem() -> None:
    """MORDIDA 6: trocar o `raise ValueError` de `motivo_do_pulo` por `return None`."""
    with pytest.raises(ValueError, match="pulo calado"):
        motivo_do_pulo()


def test_onde_o_insumo_veio_nao_ha_pulo(tmp_path: Path) -> None:
    """MORDIDA 2: fazer `motivo_do_pulo` devolver a razão antes de olhar o disco."""
    raiz = _arvore_de_mentira(tmp_path, "docs/process/\n")
    (raiz / "docs" / "process" / "sprints").mkdir(parents=True)

    assert motivo_do_pulo("docs/process/sprints", raiz=raiz) is None


def test_a_ausencia_que_o_gitignore_nao_explica_nao_pula_nunca(tmp_path: Path) -> None:
    """MORDIDA 3, e é a do ARRANJO DIFÍCIL: pular toda ausência."""
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
    """Declarar dois caminhos não compra dispensa para o que não tem regra."""
    raiz = _arvore_de_mentira(tmp_path, "docs/process/\n")

    assert (
        motivo_do_pulo(
            "docs/process/sprints",
            "docs/usage/interface.md",
            raiz=raiz,
        )
        is None
    )


def test_o_negado_do_gitignore_desfaz_a_dispensa(tmp_path: Path) -> None:
    """`!` posterior tira a dispensa, e então a ausência volta a ser defeito."""
    raiz = _arvore_de_mentira(tmp_path, "docs/process/\n!docs/process/sprints\n")

    assert _regra_que_exclui(raiz, "docs/process/sprints") is None
    assert motivo_do_pulo("docs/process/sprints", raiz=raiz) is None
    assert _regra_que_exclui(raiz, "docs/process/agentes") == ".gitignore:1"


def test_a_linha_do_gitignore_sai_do_arquivo_e_nao_deste_teste() -> None:
    """MORDIDA 4: cravar o número da linha em vez de lê-lo do `.gitignore`."""
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
        arquivo, linha, _resto = processo.stdout.split("\t", 1)[0].split(":", 2)
        do_git = f"{arquivo}:{linha}"

        nosso = _regra_que_exclui(RAIZ, relativo)
        assert nosso == do_git, (
            f"a leitura do `.gitignore` do conftest diz {nosso} para "
            f"`{relativo}` e o git diz {do_git}"
        )


def test_os_insumos_que_nao_viajam_continuam_sem_viajar() -> None:
    """A lista deste arquivo não pode envelhecer calada."""
    for relativo in OS_INSUMOS_QUE_NAO_VIAJAM:
        assert _regra_que_exclui(RAIZ, relativo) is not None, (
            f"`{relativo}` deixou de ser ignorado: reveja quem o dispensa"
        )


def test_o_marcador_esta_registrado(pytestconfig: pytest.Config) -> None:
    """Quem responde se o marcador existe é o pytest, não uma cópia da string."""
    registrados = "\n".join(pytestconfig.getini("markers"))
    assert "insumo_fora_do_git" in registrados, registrados


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
    """MORDIDA 5: tirar `pytest_collection_modifyitems` do `tests/conftest.py`."""
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
    """O arranjo DIFÍCIL atravessando o gancho inteiro, não só a função."""
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
    """MORDIDA 6, do lado do gancho: aceitar `@pytest.mark.insumo_fora_do_git`."""
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


_TEMPLATE_DA_PORTA_DO_MODULO = '''\
"""Módulo de mentira do INSUMO-FORA-DO-GIT-01 — apagado no `finally`."""

from pathlib import Path

from tests.conftest import exigir_insumo_fora_do_git

exigir_insumo_fora_do_git({alvos})

# Só se chega aqui quando a porta do módulo NÃO pulou.
Path(__file__).resolve().parents[2].joinpath({primeiro}).read_text(encoding="utf-8")


def test_de_mentira():
    assert False, "este teste nunca deveria RODAR quando o insumo é dispensado"
'''

_TEMPLATE_DA_PORTA_SEM_LEITURA = '''\
"""Módulo de mentira do INSUMO-FORA-DO-GIT-01 — apagado no `finally`."""

from tests.conftest import exigir_insumo_fora_do_git

exigir_insumo_fora_do_git({alvos})


def test_de_mentira():
    assert False, "este teste tem de RODAR e reprovar quando não há dispensa"
'''


def _modulo_da_porta(template: str, *alvos: str) -> Path:
    nome = f"test_zz_porta_do_modulo_{uuid.uuid4().hex[:8]}.py"
    caminho = RAIZ / "tests" / "unit" / nome
    caminho.write_text(
        template.format(
            alvos=", ".join(repr(a) for a in alvos),
            primeiro=repr(alvos[0]) if alvos else "''",
        ),
        encoding="utf-8",
    )
    return caminho


def test_a_porta_do_modulo_pula_o_lote_com_a_razao() -> None:
    """MORDIDA: `pytest.skip(motivo)` sem `allow_module_level=True`."""
    modulo = _modulo_da_porta(
        _TEMPLATE_DA_PORTA_DO_MODULO,
        f"docs/process/NAO-EXISTE-{uuid.uuid4().hex}.md",
    )
    try:
        processo = _rodar_pytest_sobre(modulo)
    finally:
        modulo.unlink(missing_ok=True)

    saida = processo.stdout + processo.stderr
    assert "error during collection" not in saida, (
        "a porta do módulo deixou a exceção subir na COLETA — é o lote inteiro "
        "morrendo, e `no tests ran` lê-se como limpo:\n" + saida[-3000:]
    )
    assert "1 skipped" in saida, saida[-3000:]
    assert "INSUMO-FORA-DO-GIT-01" in saida, (
        "pulou, mas não disse por quê — pulo calado é verde sobre nada:\n"
        + saida[-3000:]
    )
    assert ".gitignore:" in saida, saida[-3000:]


def test_a_porta_do_modulo_nao_pula_o_que_o_gitignore_nao_explica() -> None:
    """MORDIDA: `exigir_insumo_fora_do_git` virando `return None`, e a mordida 3."""
    modulo = _modulo_da_porta(
        _TEMPLATE_DA_PORTA_SEM_LEITURA,
        f"docs/usage/NAO-EXISTE-{uuid.uuid4().hex}.md",
    )
    try:
        processo = _rodar_pytest_sobre(modulo)
    finally:
        modulo.unlink(missing_ok=True)

    saida = processo.stdout + processo.stderr
    assert "1 failed" in saida, (
        "a porta do módulo dispensou uma ausência que o git não explica:\n"
        + saida[-3000:]
    )


def test_a_porta_do_modulo_recusa_a_chamada_sem_caminho() -> None:
    """MORDIDA 6, do lado da porta do módulo: aceitar a chamada sem argumento."""
    modulo = _modulo_da_porta(_TEMPLATE_DA_PORTA_SEM_LEITURA)
    try:
        processo = _rodar_pytest_sobre(modulo)
    finally:
        modulo.unlink(missing_ok=True)

    saida = processo.stdout + processo.stderr
    assert processo.returncode != 0, saida[-3000:]
    assert "pulo calado" in saida, saida[-3000:]
