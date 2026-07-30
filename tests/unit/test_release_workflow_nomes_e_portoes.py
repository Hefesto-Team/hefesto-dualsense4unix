"""Portões do .github/workflows/release.yml: nome do pacote e acoplamento ao CI.

Sprint PACOTE-COM-NOME-01. Dois defeitos medidos em 29/07, os dois no
release.yml, os dois invisíveis para qualquer teste desta casa até aqui:

(A) o bundle Flatpak era o ÚNICO artefato publicado SEM versão no nome
    (`Hefesto-Dualsense4Unix.flatpak` fixo no `flatpak build-bundle` e repetido
    no `path` do upload), enquanto o AppImage e os dois .deb já a carregavam.
    Duas releases publicavam o mesmo nome de arquivo e quem baixasse não sabia
    qual tinha na mão. Junto disso, o `build-bundle` sem `--default-branch`
    gravava a branch `master`.

(B) o `ci.yml` dispara na tag `v*`, mas o job `github-release` dependia só de
    jobs internos ao release.yml — então os nove portões que existem apenas no
    ci.yml (packaging-parity, shellcheck, glifos, referencias-docs,
    version-sync, pre-commit, gtk-real, runtime-smoke, smoke-multi-distro)
    informavam e NÃO impediam a publicação: ci.yml vermelho e release verde
    conviviam.

Não há como rodar GitHub Actions da máquina de desenvolvimento, então a prova
é estrutural: o YAML é LIDO e afirmado. É o mesmo espírito do
tests/unit/test_check_packaging_parity.py — travar o que só se descobre em
produção.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

yaml = pytest.importorskip("yaml")

REPO_ROOT = Path(__file__).resolve().parents[2]
RELEASE_YML = REPO_ROOT / ".github" / "workflows" / "release.yml"

# O job do release.yml que efetivamente PUBLICA no GitHub.
JOB_PUBLICACAO = "github-release"


@pytest.fixture(scope="module")
def release_workflow() -> dict[str, Any]:
    if not RELEASE_YML.exists():
        pytest.skip(f"{RELEASE_YML} não encontrado")
    dados = yaml.safe_load(RELEASE_YML.read_text(encoding="utf-8"))
    assert isinstance(dados, dict), "release.yml não é um mapeamento YAML"
    return dados


def _passos_do_job(workflow: dict[str, Any], job: str) -> list[dict[str, Any]]:
    jobs = workflow.get("jobs", {})
    assert job in jobs, f"job '{job}' desapareceu do release.yml"
    return list(jobs[job].get("steps", []))


def _run_concatenado(workflow: dict[str, Any], job: str) -> str:
    """Todo o shell de um job num único texto, para varredura de comando."""
    return "\n".join(
        str(passo.get("run", "")) for passo in _passos_do_job(workflow, job)
    )


def _needs(workflow: dict[str, Any], job: str) -> list[str]:
    jobs = workflow.get("jobs", {})
    assert job in jobs, f"job '{job}' desapareceu do release.yml"
    bruto = jobs[job].get("needs", [])
    return [bruto] if isinstance(bruto, str) else list(bruto)


# ── Defeito (A): versão no nome do bundle Flatpak ────────────────────────────


def test_bundle_flatpak_carrega_a_versao_no_nome(
    release_workflow: dict[str, Any],
) -> None:
    """O arquivo .flatpak produzido tem de trazer a versão (ou variável dela).

    Aceita as duas formas legítimas: a expressão do Actions
    (`${{ needs.build.outputs.version }}`) ou a variável de shell exportada no
    `env:` do passo (`${VERSION}`). O que NÃO passa é o nome fixo.
    """
    shell = _run_concatenado(release_workflow, "flatpak")
    assert "build-bundle" in shell, "o job flatpak não exporta bundle nenhum"

    portadores_de_versao = ("${VERSION}", "needs.build.outputs.version")
    # `endswith` e não `in`: a URL do remote Flathub termina em `.flatpakrepo`
    # e não é nome de bundle nenhum.
    nomes_de_bundle = [
        pedaco.strip("\"'")
        for pedaco in shell.replace("\\\n", " ").split()
        if pedaco.strip("\"'").endswith(".flatpak")
    ]
    assert nomes_de_bundle, "nenhum nome de arquivo .flatpak no job flatpak"
    for nome in nomes_de_bundle:
        assert any(marca in nome for marca in portadores_de_versao), (
            f"bundle Flatpak sem versão no nome: {nome!r}. Duas releases "
            "publicariam o mesmo arquivo (sprint PACOTE-COM-NOME-01)."
        )


def test_upload_do_bundle_aponta_para_o_nome_versionado(
    release_workflow: dict[str, Any],
) -> None:
    """O `path` do upload-artifact tem de bater com o nome gerado.

    Este é o par que quebra junto: renomear o bundle e esquecer o upload deixa
    o job vermelho com `if-no-files-found: error`, e renomear o upload sem o
    bundle deixa o release SEM o .flatpak.
    """
    passos = _passos_do_job(release_workflow, "flatpak")
    uploads = [
        passo
        for passo in passos
        if str(passo.get("uses", "")).startswith("actions/upload-artifact")
    ]
    assert uploads, "o job flatpak não faz upload de artifact"
    for upload in uploads:
        caminho = str(upload.get("with", {}).get("path", ""))
        assert ".flatpak" in caminho
        assert "needs.build.outputs.version" in caminho, (
            f"upload do bundle aponta para caminho sem versão: {caminho!r}"
        )


def test_bundle_flatpak_declara_default_branch(
    release_workflow: dict[str, Any],
) -> None:
    """A branch `stable` tem de chegar aos DOIS comandos — por vias diferentes.

    Sem ela o ref é gravado como `master`, herdado do git, que não diz nada
    sobre canal de distribuição.

    A assimetria é do Flatpak, não nossa, e foi medida em 29/07: a flag
    `--default-branch` existe SÓ no `flatpak-builder`. O `flatpak build-bundle`
    não a conhece (`man flatpak-build-bundle`) e aborta com "Unknown option" —
    o que derrubaria o job inteiro e, com ele, o `github-release`. No bundle a
    branch é o ÚLTIMO ARGUMENTO POSICIONAL.

    Este teste existe para impedir as DUAS regressões: perder a branch, e
    devolver a flag inexistente ao bundle.
    """
    shell = _run_concatenado(release_workflow, "flatpak")

    builder = shell.split("flatpak build-bundle")[0]
    assert "--default-branch=stable" in builder, (
        "o `flatpak-builder` tem de declarar `--default-branch=stable`; sem "
        "isso o ref nasce como `master`."
    )

    bundle = shell.split("flatpak build-bundle", 1)[1]
    assert "--default-branch" not in bundle, (
        "`flatpak build-bundle` NÃO conhece `--default-branch` e aborta com "
        "\"Unknown option\" (medido em 29/07 contra o man page). A branch no "
        "bundle é o último argumento posicional."
    )
    assert bundle.rstrip().endswith("stable"), (
        "a branch `stable` tem de ser o último argumento posicional do "
        "`build-bundle`, senão ele não acha o ref publicado pelo builder."
    )


# ── Defeito (B): a publicação depende do guarda de CI ────────────────────────


def test_existe_um_guarda_que_consulta_o_ci_da_mesma_sha(
    release_workflow: dict[str, Any],
) -> None:
    """Algum job do release.yml tem de PERGUNTAR a conclusão do ci.yml."""
    jobs = release_workflow.get("jobs", {})
    guardas = [
        nome
        for nome in jobs
        if "ci.yml/runs" in _run_concatenado(release_workflow, nome)
    ]
    assert guardas, (
        "nenhum job consulta os runs do ci.yml. Sem isso os nove portões que "
        "só existem no ci.yml informam e não impedem a publicação."
    )
    for nome in guardas:
        shell = _run_concatenado(release_workflow, nome)
        assert "head_sha" in shell, (
            f"o guarda '{nome}' não filtra por head_sha: consultaria um run "
            "de outro commit."
        )
        assert "success" in shell, (
            f"o guarda '{nome}' não exige conclusão 'success' do ci.yml."
        )
        permissoes = jobs[nome].get("permissions", {})
        assert permissoes.get("actions") == "read", (
            f"o guarda '{nome}' precisa de `permissions: actions: read` para "
            "ler os runs do ci.yml."
        )


def test_github_release_depende_do_guarda_de_ci(
    release_workflow: dict[str, Any],
) -> None:
    """O job que publica tem de esperar o guarda — senão ele é decorativo."""
    guardas = {
        nome
        for nome in release_workflow.get("jobs", {})
        if "ci.yml/runs" in _run_concatenado(release_workflow, nome)
    }
    deps_do_job = set(_needs(release_workflow, JOB_PUBLICACAO))
    assert guardas & deps_do_job, (
        f"'{JOB_PUBLICACAO}' depende de {sorted(deps_do_job)} e de nenhum "
        f"guarda de CI (candidatos: {sorted(guardas)}). Um ci.yml vermelho "
        "publicaria a release."
    )
