"""Portões do .github/workflows/release.yml: nome do pacote e acoplamento ao CI."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

yaml = pytest.importorskip("yaml")

REPO_ROOT = Path(__file__).resolve().parents[2]
RELEASE_YML = REPO_ROOT / ".github" / "workflows" / "release.yml"

JOB_PUBLICACAO = "github-release"

PUBLICACAO_EM_SHELL = (
    "gh release create",
    "gh release upload",
    "gh release edit",
    "twine upload",
)
PUBLICACAO_EM_USES = (
    "pypi-publish",
    "action-gh-release",
    "release-action",
)

PUBLICADORES_DE_HOJE = ("github-release", "pypi")


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


def _needs_transitivos(workflow: dict[str, Any], job: str) -> set[str]:
    """Fecho dos `needs`: no Actions o job só roda se TODO o fecho passar."""
    alcancados: set[str] = set()
    fila = list(_needs(workflow, job))
    while fila:
        atual = fila.pop()
        if atual in alcancados:
            continue
        alcancados.add(atual)
        fila.extend(_needs(workflow, atual))
    return alcancados


def _guardas_de_ci(workflow: dict[str, Any]) -> set[str]:
    return {
        nome
        for nome in workflow.get("jobs", {})
        if "ci.yml/runs" in _run_concatenado(workflow, nome)
    }


def _publica_para_fora(workflow: dict[str, Any], job: str) -> bool:
    dados = workflow.get("jobs", {}).get(job, {})
    if dados.get("environment"):
        return True
    if any(marca in _run_concatenado(workflow, job) for marca in PUBLICACAO_EM_SHELL):
        return True
    usadas = " ".join(
        str(passo.get("uses", "")) for passo in _passos_do_job(workflow, job)
    )
    return any(marca in usadas for marca in PUBLICACAO_EM_USES)


def _jobs_que_publicam(workflow: dict[str, Any]) -> set[str]:
    return {
        nome for nome in workflow.get("jobs", {}) if _publica_para_fora(workflow, nome)
    }


def test_bundle_flatpak_carrega_a_versao_no_nome(
    release_workflow: dict[str, Any],
) -> None:
    """O arquivo .flatpak produzido tem de trazer a versão (ou variável dela)."""
    shell = _run_concatenado(release_workflow, "flatpak")
    assert "build-bundle" in shell, "o job flatpak não exporta bundle nenhum"

    portadores_de_versao = ("${VERSION}", "needs.build.outputs.version")
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
    """O `path` do upload-artifact tem de bater com o nome gerado."""
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
    """A branch `stable` tem de chegar aos DOIS comandos — por vias diferentes."""
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


def test_existe_um_guarda_que_consulta_o_ci_da_mesma_sha(
    release_workflow: dict[str, Any],
) -> None:
    """Algum job do release.yml tem de PERGUNTAR a conclusão do ci.yml."""
    jobs = release_workflow.get("jobs", {})
    guardas = sorted(_guardas_de_ci(release_workflow))
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
    guardas = _guardas_de_ci(release_workflow)
    deps_do_job = set(_needs(release_workflow, JOB_PUBLICACAO))
    assert guardas & deps_do_job, (
        f"'{JOB_PUBLICACAO}' depende de {sorted(deps_do_job)} e de nenhum "
        f"guarda de CI (candidatos: {sorted(guardas)}). Um ci.yml vermelho "
        "publicaria a release."
    )


def test_todo_job_que_entrega_para_fora_depende_do_guarda_de_ci(
    release_workflow: dict[str, Any],
) -> None:
    """Mordida: tirar o guarda do `needs` de QUALQUER publicador reprova."""
    guardas = _guardas_de_ci(release_workflow)
    assert guardas, "nenhum guarda de CI no release.yml"

    desguardados = {
        nome: sorted(_needs_transitivos(release_workflow, nome))
        for nome in sorted(_jobs_que_publicam(release_workflow))
        if not guardas & _needs_transitivos(release_workflow, nome)
    }
    assert desguardados == {}, (
        "job que entrega artefato para fora sem depender do guarda de CI "
        f"(guardas: {sorted(guardas)}): {desguardados}. Um ci.yml vermelho "
        "publicaria por esse caminho."
    )


def test_o_detector_de_publicacao_enxerga_quem_publica_hoje(
    release_workflow: dict[str, Any],
) -> None:
    """Detector cego aprova tudo: o teste acima não pode varrer conjunto vazio."""
    jobs = release_workflow.get("jobs", {})
    publicadores = _jobs_que_publicam(release_workflow)
    assert publicadores, "o detector não achou publicador nenhum no release.yml"

    invisiveis = [
        nome for nome in PUBLICADORES_DE_HOJE if nome in jobs and nome not in publicadores
    ]
    assert invisiveis == [], (
        f"o detector deixou de reconhecer {invisiveis} como publicação: as "
        "marcas em PUBLICACAO_EM_SHELL/PUBLICACAO_EM_USES precisam acompanhar "
        "o que o job passou a usar."
    )
