"""Todo passo de todo workflow tem `run` ou `uses`, e nenhuma chave se repete.

YAML-DUPLO-01 (13/08/2026). Este arquivo existe por causa de um defeito que
custou um run inteiro do CI — e que NENHUM teste desta casa era capaz de ver.

O DEFEITO, medido no próprio histórico. O commit `edc4dce` inseriu o passo
"Instalar rsvg-convert" no meio do passo "Instalar pre-commit e o ruff pinado",
e o `ci.yml` ficou assim (`git show edc4dce:.github/workflows/ci.yml`, linhas
508 a 523)::

    - name: Instalar pre-commit e o ruff pinado
      # (só comentário: o `run:` foi embora)
    - name: Instalar rsvg-convert (o hook de ícones precisa dele)
      run: |
        sudo apt-get update
        sudo apt-get install -y librsvg2-bin
      run: pip install pre-commit "ruff==0.15.20"

São DUAS formas do mesmo estrago, no mesmo lugar:

1. um passo com `name` e comentário e **nenhum** `run` nem `uses` — o GitHub
   recusa o workflow inteiro e o run morre em segundos, antes de qualquer job;
2. a chave `run` **duas vezes** no mesmo mapeamento — o `yaml.safe_load` aceita
   calado e fica com a última, então até uma leitura por programa via
   `safe_load` via um workflow plausível onde o GitHub via um arquivo inválido.

A cura veio em `93485de`, e a mensagem daquele commit diz como ela foi
conferida: **"Conferido por leitura do YAML"**. À mão. Nada na suíte reprovava
o arquivo quebrado, e nada impedia a repetição — sete arquivos de `tests/` já
carregavam workflows em 13/08/2026 e nenhum olhava a FORMA de um passo.

POR QUE A REGRA 2 PRECISA DE LEITOR PRÓPRIO. `yaml.safe_load` implementa a
especificação de forma permissiva: mapeamento com chave repetida não é erro, é
sobrescrita silenciosa. Um teste escrito com `safe_load` puro é, portanto,
estruturalmente incapaz de ver a duplicata — ele recebe o dicionário já
achatado. Daí o `_LeitorQueDelataDuplicata` abaixo: mesma gramática, mesma
segurança (deriva de `SafeLoader`, não constrói objeto arbitrário), e reprova
onde a permissividade escondia.

O ALCANCE. Todos os workflows de `.github/workflows/`, e não só o `ci.yml`: o
`release.yml` já perdeu uma leva por um gatilho mal escrito (`43ce755`), e é
justamente o arquivo que ninguém exercita antes da tag. A guarda é de FORMA, e
forma custa milissegundos — não há razão para cobrir um arquivo e deixar três.

O QUE ESTA GUARDA NÃO É. Ela não valida o esquema do GitHub Actions (isso
exigiria acompanhar um esquema de terceiro que muda sem aviso). Ela cobre as
duas formas que ESTA casa já pagou. Regra da casa: portão nasce de defeito
real.

PROVA DE QUE MORDE (13/08/2026): as duas rodadas estão no relatório da leva 4.
Arrancado do `ci.yml` o `run: pip install pre-commit "ruff==0.15.20"` do passo
"Instalar pre-commit e o ruff pinado" — que é literalmente o defeito de
`edc4dce` — `test_todo_passo_de_todo_workflow_tem_run_ou_uses` reprovou
nomeando o passo e o job. Devolvido, verde. A segunda mordida foi o arquivo
histórico inteiro (`git show edc4dce:.github/workflows/ci.yml`), que reprova
pelas duas regras de uma vez.
"""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml

RAIZ = Path(__file__).resolve().parents[2]
WORKFLOWS = RAIZ / ".github" / "workflows"

#: Quantos workflows havia quando esta guarda nasceu (13/08/2026): `ci.yml`,
#: `release.yml`, `flatpak.yml` e `anonymity-check.yml`. É trava de
#: encolhimento, não meta: se a pasta esvaziar por um erro de caminho, os
#: testes daqui passariam por vacuidade — que é o modo de falha preferido de
#: toda guarda derivada. Sobe quando alguém acrescentar workflow.
PISO_DE_WORKFLOWS = 4


class ChaveRepetidaError(Exception):
    """Uma chave apareceu duas vezes no mesmo mapeamento do YAML."""


class _LeitorQueDelataDuplicata(yaml.SafeLoader):
    """`SafeLoader` que reprova chave repetida em vez de ficar com a última.

    A permissividade do `safe_load` é a razão de existir desta classe: sem ela,
    um teste que lê o workflow por programa NUNCA vê a duplicata, porque recebe
    o dicionário depois de a última chave ter vencido a primeira.
    """

    def construct_mapping(self, no, deep=False):  # type: ignore[no-untyped-def]
        vistas: set[object] = set()
        for chave_no, _valor_no in no.value:
            chave = self.construct_object(chave_no, deep=deep)
            try:
                repetida = chave in vistas
            except TypeError:  # chave não hasheável: fora do alcance desta guarda
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
    """Todo passo de todo job, com o nome do job e a posição dentro dele.

    A posição vem junto porque um passo sem `run` costuma também estar sem
    `name` — e "o terceiro passo do job `pre-commit`" é endereço, enquanto
    "algum passo" é adivinhação.
    """
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
    """A régua não pode nascer cega — ela é conferida contra o defeito real.

    Este teste não olha a árvore: ele exercita `carregar` e `passos` contra o
    formato exato que `edc4dce` produziu. Sem ele, um refactor poderia
    silenciar as duas regras acima e todos os testes deste arquivo continuariam
    verdes, porque hoje a árvore está limpa.
    """
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
