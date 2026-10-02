"""Todo passo de todo workflow tem `run` ou `uses`, e nenhuma chave se repete."""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml

RAIZ = Path(__file__).resolve().parents[2]
WORKFLOWS = RAIZ / ".github" / "workflows"

PISO_DE_WORKFLOWS = 4


class ChaveRepetidaError(Exception):
    """Uma chave apareceu duas vezes no mesmo mapeamento do YAML."""


class _LeitorQueDelataDuplicata(yaml.SafeLoader):
    """`SafeLoader` que reprova chave repetida em vez de ficar com a última."""

    def construct_mapping(self, no, deep=False):  # type: ignore[no-untyped-def]
        vistas: set[object] = set()
        for chave_no, _valor_no in no.value:
            chave = self.construct_object(chave_no, deep=deep)
            try:
                repetida = chave in vistas
            except TypeError:
                continue
            if repetida:
                raise ChaveRepetidaError(
                    f"chave {chave!r} repetida no mesmo mapeamento, "
                    f"linha {chave_no.start_mark.line + 1} "
                    f"(o mapeamento começa na linha {no.start_mark.line + 1})"
                )
            vistas.add(chave)
        return super().construct_mapping(no, deep=deep)


def workflows() -> list[Path]:
    """Os arquivos de workflow, em ordem estável de caminho."""
    if not WORKFLOWS.is_dir():
        return []
    return sorted(p for p in WORKFLOWS.iterdir() if p.suffix in (".yml", ".yaml"))


def carregar(caminho: Path) -> dict:
    """O workflow como dicionário — reprovando chave repetida pelo caminho."""
    dados = yaml.load(caminho.read_text(encoding="utf-8"), Loader=_LeitorQueDelataDuplicata)
    return dados if isinstance(dados, dict) else {}


def passos(dados: dict) -> list[tuple[str, int, dict]]:
    """Todo passo de todo job, com o nome do job e a posição dentro dele."""
    achados: list[tuple[str, int, dict]] = []
    for nome_do_job, job in (dados.get("jobs") or {}).items():
        if not isinstance(job, dict):
            continue
        for posicao, passo in enumerate(job.get("steps") or [], start=1):
            if isinstance(passo, dict):
                achados.append((str(nome_do_job), posicao, passo))
    return achados


def test_a_pasta_de_workflows_nao_encolhe_calada() -> None:
    """Sem esta trava, um caminho errado faria os outros testes passarem vazios."""
    achados = workflows()
    assert len(achados) >= PISO_DE_WORKFLOWS, (
        f"{WORKFLOWS} rendeu {len(achados)} workflow(s), piso "
        f"{PISO_DE_WORKFLOWS}: {[p.name for p in achados]}\n"
        "Se um workflow foi APAGADO de propósito, baixe o piso no mesmo commit, "
        "para que a queda fique escrita em vez de descoberta.\n"
        "Se a PASTA mudou de lugar, conserte `WORKFLOWS` — sem isso os outros "
        "testes deste arquivo passam sem olhar arquivo nenhum."
    )


@pytest.mark.parametrize("caminho", workflows(), ids=lambda p: p.name)
def test_nenhum_workflow_repete_chave_no_mesmo_mapeamento(caminho: Path) -> None:
    """`run:` duas vezes no mesmo passo: o safe_load aceita, o GitHub recusa."""
    try:
        carregar(caminho)
    except ChaveRepetidaError as erro:
        pytest.fail(
            f"{caminho.relative_to(RAIZ)}: {erro}\n"
            "APAGUE a chave repetida. O `yaml.safe_load` fica com a ÚLTIMA e "
            "não reclama, então a leitura por programa mostra um arquivo "
            "plausível enquanto o GitHub recusa o workflow inteiro.\n"
            "Foi assim em `edc4dce`: um passo ganhou `run:` duas vezes quando "
            "outro passo foi colado no meio dele."
        )
    except yaml.YAMLError as erro:
        pytest.fail(
            f"{caminho.relative_to(RAIZ)} não é YAML válido: {erro}\n"
            "O GitHub recusa o arquivo inteiro e o run morre antes de "
            "qualquer job — sem log de job para explicar por quê."
        )


@pytest.mark.parametrize("caminho", workflows(), ids=lambda p: p.name)
def test_todo_passo_de_todo_workflow_tem_run_ou_uses(caminho: Path) -> None:
    """Passo sem `run` e sem `uses` derruba o workflow INTEIRO, em segundos."""
    for nome_do_job, posicao, passo in passos(carregar(caminho)):
        onde = passo.get("name") or f"passo nº {posicao} (sem `name`)"
        assert ("run" in passo) or ("uses" in passo), (
            f"{caminho.relative_to(RAIZ)}: o passo '{onde}' do job "
            f"'{nome_do_job}' não tem `run` nem `uses`.\n"
            "DEVOLVA o `run:` do passo. Um passo só com `name` e comentário "
            "faz o GitHub recusar o WORKFLOW INTEIRO: o run morre em segundos, "
            "antes de qualquer job, e nenhum log de job explica por quê.\n"
            "Foi exatamente isto em `edc4dce` (curado em `93485de`, à mão, "
            "porque nada na suíte reprovava)."
        )


@pytest.mark.parametrize("caminho", workflows(), ids=lambda p: p.name)
def test_nenhum_job_nasce_sem_passo_e_sem_workflow_chamado(caminho: Path) -> None:
    """Job sem `steps` e sem `uses` é job que não faz nada e parece que faz."""
    for nome_do_job, job in (carregar(caminho).get("jobs") or {}).items():
        if not isinstance(job, dict):
            continue
        assert job.get("steps") or job.get("uses"), (
            f"{caminho.relative_to(RAIZ)}: o job '{nome_do_job}' não tem "
            "`steps` nem `uses` — ele aparece verde no relatório sem ter "
            "executado nada.\n"
            "DEVOLVA os passos, ou APAGUE o job. Um job vazio é a forma mais "
            "silenciosa de desligar um portão: o nome continua no relatório."
        )


def test_a_regua_ve_as_duas_formas_do_defeito_de_edc4dce(tmp_path: Path) -> None:
    """A régua não pode nascer cega — ela é conferida contra o defeito real."""
    duplicata = tmp_path / "duplicata.yml"
    duplicata.write_text(
        "jobs:\n"
        "  pre-commit:\n"
        "    steps:\n"
        "      - name: Instalar rsvg-convert\n"
        "        run: sudo apt-get install -y librsvg2-bin\n"
        '        run: pip install pre-commit "ruff==0.15.20"\n',
        encoding="utf-8",
    )
    with pytest.raises(ChaveRepetidaError):
        carregar(duplicata)

    sem_run = tmp_path / "sem-run.yml"
    sem_run.write_text(
        "jobs:\n"
        "  pre-commit:\n"
        "    steps:\n"
        "      - name: Instalar pre-commit e o ruff pinado\n"
        "      - name: Rodar todos os hooks\n"
        "        run: pre-commit run --all-files\n",
        encoding="utf-8",
    )
    forma = [
        (nome, ("run" in passo) or ("uses" in passo))
        for nome, _posicao, passo in passos(carregar(sem_run))
    ]
    assert forma == [("pre-commit", False), ("pre-commit", True)], forma
