"""O CI de casa roda o YAML do GitHub, e a tabela de jobs não deixa nenhum de fora.

`scripts/ci-local.sh` roda os workflows pelo `act`, sem uma função por job. O que esta casa decide
mora em `scripts/ci-local/jobs.txt`, e estas réguas garantem as duas pontas:

  1. TODO job dos workflows tem uma decisão (`ROLA` ou `FORA-DE-CASA|job|motivo`), nenhuma sobra e
     nenhuma se repete; e o motivo de «fora de casa» existe e não é marcador de pendência;
  2. o `--rapido` tira da cópia do YAML só o que a tabela manda, e o passo que a tabela manda tirar
     existe: passo renomeado no `ci.yml` faria o `--rapido` rodar a suíte inteira sem ninguém ver.

O script em si é medido numa árvore de mentira (um repositório git de verdade, com o `act` e o
`docker` de mentira no PATH): o que ele roda, o que ele exporta e como ele classifica o resultado.
"""

from __future__ import annotations

import os
import re
import shutil
import signal
import subprocess
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import pytest
import yaml

RAIZ = Path(__file__).resolve().parents[2]
WORKFLOWS = RAIZ / ".github" / "workflows"
TABELA = RAIZ / "scripts" / "ci-local" / "jobs.txt"
SCRIPT = RAIZ / "scripts" / "ci-local.sh"
SERVIDOR_DE_ARTEFATOS = RAIZ / "scripts" / "ci-local" / "servidor-de-artefatos.py"
RUNNER_DO_GITHUB = RAIZ / "scripts" / "ci-local" / "runner-do-github.sh"
IMAGENS = (
    RAIZ / "scripts" / "ci-local" / "Dockerfile",
    RAIZ / "scripts" / "ci-local" / "Dockerfile.ubuntu-22.04",
)
FERRAMENTAS_DA_IMAGEM = "/opt/ferramentas-do-runner"

FERRAMENTAS = (
    "awk",
    "basename",
    "bash",
    "cat",
    "cp",
    "cut",
    "date",
    "df",
    "dirname",
    "git",
    "grep",
    "head",
    "ls",
    "mkdir",
    "mktemp",
    "mv",
    "pwd",
    "python3",
    "rm",
    "sed",
    "sha256sum",
    "sleep",
    "sort",
    "tail",
    "tr",
    "uniq",
    "wc",
)
RUNNERS_QUE_O_ACT_MAPEIA = {"ubuntu-latest", "ubuntu-26.04", "ubuntu-24.04"}


def _jobs_dos_workflows() -> dict[str, dict[str, Any]]:
    jobs: dict[str, dict[str, Any]] = {}
    for caminho in sorted(WORKFLOWS.glob("*.yml")):
        dados = yaml.safe_load(caminho.read_text(encoding="utf-8")) or {}
        for nome, job in (dados.get("jobs") or {}).items():
            assert nome not in jobs, f"o job '{nome}' existe em mais de um workflow"
            jobs[nome] = job or {}
    return jobs


def _linhas() -> list[list[str]]:
    return [
        ln.split("|")
        for ln in TABELA.read_text(encoding="utf-8").splitlines()
        if ln.strip() and not ln.lstrip().startswith("#")
    ]


def _decisoes() -> dict[str, list[list[str]]]:
    por_job: dict[str, list[list[str]]] = {}
    for campos in _linhas():
        if campos[0] in {"ROLA", "FORA-DE-CASA"}:
            por_job.setdefault(campos[1], []).append(campos)
    return por_job


def test_todo_job_dos_workflows_tem_uma_decisao_e_so_uma() -> None:
    jobs = set(_jobs_dos_workflows())
    decisoes = _decisoes()
    sem_decisao = sorted(jobs - set(decisoes))
    sem_job = sorted(set(decisoes) - jobs)
    repetidos = sorted(j for j, d in decisoes.items() if len(d) != 1)
    assert not sem_decisao, (
        f"job do workflow sem linha ROLA ou FORA-DE-CASA em jobs.txt: {sem_decisao}"
    )
    assert not sem_job, f"jobs.txt cita job que nenhum workflow tem: {sem_job}"
    assert not repetidos, f"job com mais de uma decisão em jobs.txt: {repetidos}"


def test_fora_de_casa_diz_o_motivo_e_o_motivo_nao_e_pendencia() -> None:
    fracos = []
    for campos in _linhas():
        if campos[0] != "FORA-DE-CASA":
            continue
        motivo = "|".join(campos[2:]).strip()
        if len(campos) < 3 or len(motivo) < 40 or motivo.upper().startswith("A CONFERIR"):
            fracos.append(campos[1])
    assert not fracos, f"FORA-DE-CASA sem motivo medido (ou com marcador de pendência): {fracos}"


def test_a_linha_rola_diz_o_modo_e_a_imagem_do_runner_que_o_act_nao_tem() -> None:
    jobs = _jobs_dos_workflows()
    ruins = []
    for campos in _linhas():
        if campos[0] != "ROLA":
            continue
        job = campos[1]
        if len(campos) < 3 or campos[2] not in {"rapido", "completo"}:
            ruins.append(f"{job}: o modo é rapido ou completo")
            continue
        runs_on = str(jobs[job].get("runs-on", ""))
        alvos = set(jobs[job]["strategy"]["matrix"]["os"]) if "matrix.os" in runs_on else {runs_on}
        if "container" in jobs[job]:
            continue
        for alvo in alvos - RUNNERS_QUE_O_ACT_MAPEIA:
            if not (alvo == "ubuntu-22.04" and len(campos) >= 4 and campos[3] == "ubuntu-22.04"):
                ruins.append(
                    f"{job}: o runner {alvo} não tem imagem no act "
                    "(diga `ubuntu-22.04` na 4ª coluna, ou deixe fora)"
                )
    assert not ruins, ruins


def test_todo_passo_que_o_rapido_tira_existe_no_job() -> None:
    jobs = _jobs_dos_workflows()
    sumidos = []
    for campos in _linhas():
        if campos[0] != "PULA-NO-RAPIDO":
            continue
        job, passo = campos[1], campos[2]
        nomes = [
            p.get("name") for p in (jobs.get(job, {}).get("steps") or []) if isinstance(p, dict)
        ]
        if passo not in nomes:
            sumidos.append(f"{job}: «{passo}»")
    assert not sumidos, (
        "PULA-NO-RAPIDO de passo que o YAML não tem "
        f"(o --rapido rodaria o passo inteiro): {sumidos}"
    )


def test_a_suite_inteira_so_roda_no_completo() -> None:
    """Os dois passos que rodam a suíte têm de estar na lista do que o `--rapido` tira."""
    tirados = {(c[1], c[2]) for c in _linhas() if c[0] == "PULA-NO-RAPIDO"}
    for job, passo in (
        ("lint-test", "Pytest unit"),
        ("lint-test", "Pytest core"),
        ("gtk-real", "A suíte inteira sob Xvfb, com o GTK real"),
    ):
        assert (job, passo) in tirados, f"o --rapido rodaria «{passo}» do job {job}"


def test_os_checks_que_o_ruleset_exige_pelo_nome_rodam_no_rapido() -> None:
    """Os checks que o ruleset exige pelo nome (`lint-test (3.10)`…) rodam no `--rapido`."""
    rapidos = {c[1] for c in _linhas() if c[0] == "ROLA" and c[2] == "rapido"}
    assert "lint-test" in rapidos
    assert "acentuacao" in rapidos


def _git(arvore: Path, *args: str) -> None:
    env = {**os.environ, "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_SYSTEM": os.devnull}
    subprocess.run(
        [
            "git",
            "-c",
            "core.hooksPath=/dev/null",
            "-c",
            "user.name=t",
            "-c",
            "user.email=t@t.t",
            *args,
        ],
        cwd=arvore,
        env=env,
        check=True,
        capture_output=True,
    )


ACT_DE_MENTIRA = r"""#!/usr/bin/env bash
# `act` de mentira: escreve no log o que recebeu e o que viu, e sai com o código que o teste mandou.
job=""; yml=""; args=("$@")
for ((i = 0; i < ${#args[@]}; i++)); do
  [ "${args[i]}" = "-j" ] && job="${args[i+1]}"
  [ "${args[i]}" = "-W" ] && yml="${args[i+1]}"
done
echo "ARGS: $*"
echo "CWD: $(pwd)"
echo "ARQUIVOS: $(ls -A | tr '\n' ' ')"
echo "ENV: ${RUNNER_TOOL_CACHE:-}"
echo "SEGREDO: ${HEFESTO_BIBLIOTECA_VEDADA:+veio}"
for ((i = 0; i < ${#args[@]}; i++)); do
  [ "${args[i]}" = "--action-cache-path" ] && cache="${args[i+1]}"
done
echo "CACHE_ACOES: $(ls -A "$cache" | tr '\n' ' ')"
mkdir -p "$cache/actions-novo@v1" && echo x > "$cache/actions-novo@v1/x"
echo "---YAML---"
cat "$yml"
echo "---FIM---"
RUN=$'\xe2\xad\x90 Run'; FALHA=$'\xe2\x9d\x8c  Failure -'; OK=$'\xe2\x9c\x85  Success -'
PASSOU=$'\xf0\x9f\x8f\x81  Job succeeded'
TEXTO="Temporary failure resolving 'archive.ubuntu.com'"
# a rede caída como o apt a escreve, na saída do passo que reprovou (`[job]   | texto`)
case ",${FAKE_REDE:-}," in *",$job,"*)
  echo "[CI/$job] $RUN Main Instalar deps do sistema"
  echo "[CI/$job]   | W: Failed to fetch http://archive.ubuntu.com/InRelease  $TEXTO"
  echo "[CI/$job]   $FALHA Main Instalar deps do sistema [1s]"
  exit 1 ;; esac
# o pip que tentou de novo e conseguiu deixa a linha da rede num passo VERDE;
# o vermelho é de outro passo
PIP="WARNING: Retrying (Retry(total=4)) after connection broken by"
PIP="$PIP 'NewConnectionError(': Failed to establish a new connection: [Errno -3]"
PIP="$PIP Temporary failure in name resolution')': /simple/pytest/"
case ",${FAKE_PIP_E_FALHA:-}," in *",$job,"*)
  echo "[CI/$job-1] $RUN Main Instalar"
  echo "[CI/$job-1]   | $PIP"
  echo "[CI/$job-1]   $OK Main Instalar [9s]"
  echo "[CI/$job-1] $RUN Main Ruff"
  echo "[CI/$job-1]   $FALHA Main Ruff [1s]"
  exit 1 ;; esac
# uma perna da matriz cai pela rede e a outra reprova de verdade
case ",${FAKE_PERNAS:-}," in *",$job,"*)
  echo "[CI/$job-1] $RUN Main Instalar"
  echo "[CI/$job-2] $RUN Main Ruff"
  echo "[CI/$job-1]   | $PIP"
  echo "[CI/$job-2]   $FALHA Main Ruff [1s]"
  echo "[CI/$job-1]   $FALHA Main Instalar [9s]"
  exit 1 ;; esac
# o docker que não respondeu ao limpar o container de um job que passou
case ",${FAKE_DOCKER:-}," in *",$job,"*)
  echo "[CI/$job] failed to remove container: Delete http://x: context deadline exceeded"
  echo "Error: Error occurred running finally: context deadline exceeded"; exit 1 ;; esac
# o job inteiro passou e só a remoção do contêiner estourou o minuto do act
case ",${FAKE_LIMPEZA:-}," in *",$job,"*)
  echo "[CI/$job] $RUN Set up job"
  echo "[CI/$job] failed to remove container: Delete http://x: context deadline exceeded"
  echo "[CI/$job] Error while stop job container: context deadline exceeded"
  echo "[CI/$job] $PASSOU"
  echo "Error: Error occurred running finally: context deadline exceeded"; exit 1 ;; esac
# duas pernas: uma passou, a outra ficou sem resposta do docker no meio
case ",${FAKE_LIMPEZA_NO_MEIO:-}," in *",$job,"*)
  echo "[CI/$job-1] $RUN Set up job"
  echo "[CI/$job-2] $RUN Set up job"
  echo "[CI/$job-1] $PASSOU"
  echo "[CI/$job-2] failed to remove container: Delete http://x: context deadline exceeded"
  echo "Error: Error occurred running finally: context deadline exceeded"; exit 1 ;; esac
# o mesmo docker lento, num job que JÁ tinha reprovado num passo
case ",${FAKE_DOCKER_E_FALHA:-}," in *",$job,"*)
  echo "[CI/$job] $RUN Main Ruff"
  echo "[CI/$job]   $FALHA Main Ruff [1s]"
  echo "[CI/$job] failed to remove container: Delete http://x: context deadline exceeded"
  echo "Error: Error occurred running finally: context deadline exceeded"; exit 1 ;; esac
# o mesmo texto CITADO (uma linha de teste, com número de linha): reprova, mas não é a rede
case ",${FAKE_CITA:-}," in *",$job,"*)
  echo "[CI/$job]   | 163 | echo \"E: $TEXTO\"; exit 1"
  echo "Error: Job '$job' failed"; exit 1 ;; esac
case ",${FAKE_FALHA:-}," in *",$job,"*) echo "Error: Job '$job' failed"; exit 1 ;; esac
exit 0
"""

DOCKER_DE_MENTIRA = """#!/usr/bin/env bash
exit 0
"""


def _escrever_exec(caminho: Path, texto: str) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text(texto, encoding="utf-8")
    caminho.chmod(0o755)


class Mundo:
    """Uma árvore git de verdade com o script, a tabela, os workflows e um PATH mínimo."""

    def __init__(
        self, base: Path, tabela: str | None = None, com_act: bool = True, com_docker: bool = True
    ) -> None:
        base.mkdir(parents=True, exist_ok=True)
        self.base = base
        self.arvore = base / "arvore"
        self.casa = base / "casa"
        self.saida = base / "saida"
        self.arvore.mkdir()
        (self.arvore / "scripts" / "ci-local").mkdir(parents=True)
        shutil.copy(SCRIPT, self.arvore / "scripts" / "ci-local.sh")
        shutil.copy(SERVIDOR_DE_ARTEFATOS, self.arvore / "scripts" / "ci-local")
        (self.arvore / "scripts" / "ci-local" / "jobs.txt").write_text(
            tabela if tabela is not None else TABELA.read_text(encoding="utf-8"), encoding="utf-8"
        )
        shutil.copytree(WORKFLOWS, self.arvore / ".github" / "workflows")
        (self.arvore / "versionado.txt").write_text("está no índice\n", encoding="utf-8")
        (self.arvore / ".gitignore").write_text("ignorado.txt\n", encoding="utf-8")
        _git(self.arvore, "init", "-q")
        _git(self.arvore, "add", ".")
        _git(self.arvore, "commit", "-qm", "base")
        (self.arvore / "ignorado.txt").write_text("só no disco\n", encoding="utf-8")
        ferramentas = base / "ferramentas"
        ferramentas.mkdir()
        for nome in FERRAMENTAS:
            achado = shutil.which(nome)
            assert achado, f"a ferramenta {nome} não está no PATH desta máquina"
            (ferramentas / nome).symlink_to(achado)
        if com_docker:
            _escrever_exec(ferramentas / "docker", DOCKER_DE_MENTIRA)
        if com_act:
            _escrever_exec(self.casa / "bin" / "act", ACT_DE_MENTIRA)
        self.casa.mkdir(exist_ok=True)
        self.ferramentas = ferramentas

    def rodar(self, *args: str, **ambiente: str) -> subprocess.CompletedProcess[str]:
        env = {
            "PATH": str(self.ferramentas),
            "HOME": str(self.base),
            "HEFESTO_CASA": str(self.casa),
            "CI_LOCAL_SAIDA": str(self.saida),
            "CI_LOCAL_IMAGEM": "imagem-de-mentira",
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_CONFIG_SYSTEM": os.devnull,
            **ambiente,
        }
        return subprocess.run(
            ["bash", str(self.arvore / "scripts" / "ci-local.sh"), *args],
            cwd=self.arvore,
            env=env,
            capture_output=True,
            text=True,
            timeout=120,
        )

    def log(self, job: str) -> str:
        return (self.saida / f"{job}.log").read_text(encoding="utf-8")


@pytest.fixture()
def mundo(tmp_path: Path) -> Mundo:
    return Mundo(tmp_path)


def _sem_linha(tabela: str, prefixo: str) -> str:
    saida = [ln for ln in tabela.splitlines() if not ln.startswith(prefixo)]
    assert len(saida) == len(tabela.splitlines()) - 1, (
        f"a tabela não tem uma linha única que comece por {prefixo!r}"
    )
    return "\n".join(saida) + "\n"


def test_o_script_confere_a_tabela_com_os_workflows_na_propria_corrida(tmp_path: Path) -> None:
    ok = Mundo(tmp_path / "a").rodar("--listar")
    assert ok.returncode == 0, ok.stderr
    sem = Mundo(
        tmp_path / "b", tabela=_sem_linha(TABELA.read_text(encoding="utf-8"), "ROLA|glifos|")
    )
    r = sem.rodar("--rapido", "--conferir")
    assert r.returncode == 2 and "glifos" in r.stderr, r.stderr
    sobra = Mundo(
        tmp_path / "c",
        tabela=TABELA.read_text(encoding="utf-8") + "ROLA|job-que-nao-existe|rapido\n",
    )
    r = sobra.rodar("--listar")
    assert r.returncode == 2 and "job-que-nao-existe" in r.stderr, r.stderr
    tabela = TABELA.read_text(encoding="utf-8").replace("FORA-DE-CASA|pypi|", "FORA-DE-CASA|pypi")
    r = Mundo(tmp_path / "d", tabela=tabela).rodar("--listar")
    assert r.returncode == 2 and "pypi" in r.stderr, r.stderr
    r = Mundo(
        tmp_path / "e",
        tabela=TABELA.read_text(encoding="utf-8")
        + "PULA-NO-RAPIDO|lint-test|Passo que não existe\n",
    ).rodar("--listar")
    assert r.returncode == 2 and "Passo que não existe" in r.stderr, r.stderr


def test_sem_act_e_sem_docker_nada_roda_e_nada_e_verde(tmp_path: Path) -> None:
    sem_act = Mundo(tmp_path / "a", com_act=False).rodar("--rapido")
    assert sem_act.returncode == 2 and "não há act" in sem_act.stderr, sem_act.stderr
    sem_docker = Mundo(tmp_path / "b", com_docker=False).rodar("--rapido")
    assert sem_docker.returncode == 2 and "docker" in sem_docker.stderr, sem_docker.stderr


def test_o_conferir_diz_o_que_rodaria_e_sai_1(mundo: Mundo) -> None:
    r = mundo.rodar("--rapido", "--conferir")
    assert r.returncode == 1
    assert "lint-test" in r.stdout and "runtime-smoke" not in r.stdout
    assert "runtime-smoke" in mundo.rodar("--completo", "--conferir").stdout


def test_tudo_verde_sai_0_e_o_resumo_e_a_ultima_linha(mundo: Mundo) -> None:
    r = mundo.rodar("--rapido")
    assert r.returncode == 0, r.stderr + r.stdout
    ultima = r.stdout.strip().splitlines()[-1]
    assert (
        ultima.startswith("ci-local --rapido:")
        and "0 vermelho(s)" in ultima
        and "0 não rodado(s)" in ultima
    )
    assert (
        (mundo.casa / "ci-local" / "ultimo-rapido.txt")
        .read_text(encoding="utf-8")
        .strip()
        .endswith(ultima)
    )


def test_vermelho_sai_1_e_diz_qual(mundo: Mundo) -> None:
    r = mundo.rodar("--rapido", FAKE_FALHA="glifos")
    assert r.returncode == 1
    assert "1 vermelho(s) [glifos]" in r.stdout


def test_a_rede_caida_nao_e_verde_nem_vermelho_e_sai_2(mundo: Mundo) -> None:
    r = mundo.rodar("--rapido", FAKE_REDE="pre-commit")
    assert r.returncode == 2, r.stdout + r.stderr
    assert "0 vermelho(s)" in r.stdout and "1 não rodado(s) [pre-commit]" in r.stdout
    assert "a rede caiu" in mundo.log("pre-commit")


def test_o_docker_que_nao_respondeu_nao_e_verde_nem_vermelho(mundo: Mundo) -> None:
    r = mundo.rodar("--rapido", FAKE_DOCKER="glifos")
    assert r.returncode == 2, r.stdout + r.stderr
    assert "0 vermelho(s)" in r.stdout and "1 não rodado(s) [glifos]" in r.stdout
    assert "o docker não respondeu" in mundo.log("glifos") and "NÃO RODOU (docker)" in r.stderr


def test_a_remocao_atrasada_do_conteiner_nao_desfaz_o_job_que_passou(mundo: Mundo) -> None:
    """O `act` dá um minuto à remoção e sai 1 depois do `Job succeeded`. Medido em 07/11/2026:
    2 de 17 jobs do `--rapido` com a máquina cheia. MORDIDA: tirar o `todo_job_passou`."""
    r = mundo.rodar("--rapido", FAKE_LIMPEZA="glifos")
    assert r.returncode == 0, r.stdout + r.stderr
    assert "0 vermelho(s), 0 não rodado(s)" in r.stdout
    assert "todo passo deste job passou" in mundo.log("glifos")


def test_a_remocao_atrasada_de_uma_perna_nao_fecha_a_outra(mundo: Mundo) -> None:
    """MORDIDA: contar um `Job succeeded` no job inteiro, e não por perna, faz isto dar verde."""
    r = mundo.rodar("--rapido", FAKE_LIMPEZA_NO_MEIO="glifos")
    assert r.returncode == 2, r.stdout + r.stderr
    assert "1 não rodado(s) [glifos]" in r.stdout


def test_o_texto_da_rede_citado_dentro_do_log_nao_e_rede(mundo: Mundo) -> None:
    """Um teste que cita a frase da rede caída não faz o job vermelho virar «não rodou»."""
    r = mundo.rodar("--rapido", FAKE_CITA="glifos")
    assert r.returncode == 1, r.stdout + r.stderr
    assert "1 vermelho(s) [glifos]" in r.stdout and "0 não rodado(s)" in r.stdout


def test_vermelho_vale_mais_que_nao_rodado_no_codigo_de_saida(mundo: Mundo) -> None:
    r = mundo.rodar("--rapido", FAKE_FALHA="glifos", FAKE_REDE="pre-commit")
    assert r.returncode == 1
    assert "[glifos]" in r.stdout and "[pre-commit]" in r.stdout


def test_a_linha_da_rede_num_passo_verde_nao_esconde_o_vermelho(mundo: Mundo) -> None:
    """O pip que tentou de novo e conseguiu não faz o vermelho de outro passo virar «rede»."""
    r = mundo.rodar("--rapido", FAKE_PIP_E_FALHA="lint-test")
    assert r.returncode == 1, r.stdout + r.stderr
    assert "1 vermelho(s) [lint-test]" in r.stdout and "0 não rodado(s)" in r.stdout


def test_a_perna_que_caiu_pela_rede_nao_esconde_a_perna_vermelha(mundo: Mundo) -> None:
    r = mundo.rodar("--rapido", FAKE_PERNAS="lint-test")
    assert r.returncode == 1, r.stdout + r.stderr
    assert "1 vermelho(s) [lint-test]" in r.stdout and "0 não rodado(s)" in r.stdout


def test_o_docker_lento_nao_esconde_o_passo_que_reprovou(mundo: Mundo) -> None:
    r = mundo.rodar("--rapido", FAKE_DOCKER_E_FALHA="glifos")
    assert r.returncode == 1, r.stdout + r.stderr
    assert "1 vermelho(s) [glifos]" in r.stdout and "0 não rodado(s)" in r.stdout


def test_cada_job_da_corrida_tem_a_sua_porta_de_artefato(mundo: Mundo) -> None:
    """Duas chamadas na mesma porta: a segunda morre (`bind: address already in use`), vermelha."""
    mundo.rodar("--completo")
    portas = []
    for log in sorted(mundo.saida.glob("*.log")):
        for ln in log.read_text(encoding="utf-8").splitlines():
            if ln.startswith("ARGS:"):
                args = ln.split()
                portas.append((log.stem, args[args.index("--artifact-server-port") + 1]))
    jobs_por_porta: dict[str, set[str]] = {}
    for job, porta in portas:
        jobs_por_porta.setdefault(porta, set()).add(job)
    repetidas = {p: j for p, j in jobs_por_porta.items() if len(j) > 1}
    assert len(portas) > 10 and not repetidas, repetidas


PRAZO_DO_FIM_DO_SERVIDOR_S = 3.0

ACT_QUE_SOBE_ARTEFATO = """#!/usr/bin/env bash
exec python3 -c '
import json, os, urllib.request
base = os.environ["ACTIONS_RUNTIME_URL"]
corpo = {
    "workflow_run_backend_id": "1", "workflow_job_run_backend_id": "1",
    "name": "dados", "version": 7, "mime_type": "application/zip",
}
pedido = urllib.request.Request(
    base + "twirp/github.actions.results.api.v1.ArtifactService/CreateArtifact",
    data=json.dumps(corpo).encode(), headers={"Content-Type": "application/json"},
)
print("PORTA:", base, urllib.request.urlopen(pedido, timeout=10).read().decode())
'
"""


def test_o_passo_de_artefato_fala_com_o_servidor_da_casa_e_ele_sai_com_a_corrida(
    mundo: Mundo,
) -> None:
    """Sem o `ACTIONS_RUNTIME_URL`, o job fala com o servidor do `act`, que recusa o `mime_type`."""
    _escrever_exec(mundo.casa / "bin" / "act", ACT_QUE_SOBE_ARTEFATO)
    r = mundo.rodar("--job", "glifos")
    assert r.returncode == 0, r.stdout + r.stderr + mundo.log("glifos")
    linha = next(ln for ln in mundo.log("glifos").splitlines() if ln.startswith("PORTA:"))
    assert '"ok": true' in linha
    assert (mundo.casa / "ci-local" / "artefatos" / "1" / "dados" / "meta.json").is_file()
    assert urlsplit(linha.split()[1]).port
    servidor = str(mundo.arvore / "scripts" / "ci-local" / "servidor-de-artefatos.py")
    prazo = time.monotonic() + PRAZO_DO_FIM_DO_SERVIDOR_S
    while _processos_com(servidor) and time.monotonic() < prazo:
        time.sleep(0.05)
    assert not _processos_com(servidor), "o servidor de artefatos ficou vivo depois da corrida"


def _processos_com(trecho: str) -> list[int]:
    vivos = []
    for pid in Path("/proc").iterdir():
        if not pid.name.isdigit():
            continue
        try:
            linha = (pid / "cmdline").read_bytes()
        except OSError:
            continue
        if trecho.encode() in linha:
            vivos.append(int(pid.name))
    return vivos


def test_sem_o_servidor_de_artefatos_nada_roda(mundo: Mundo) -> None:
    (mundo.arvore / "scripts" / "ci-local" / "servidor-de-artefatos.py").unlink()
    r = mundo.rodar("--job", "glifos")
    assert r.returncode == 2 and "servidor de artefatos" in r.stderr, r.stdout + r.stderr


def _df_de_mentira(mundo: Mundo, **livres: int) -> None:
    """Um `df` que devolve o espaço de cada pasta, com a saída de `df --output=avail -m`."""
    casos = "".join(f'  *{pasta}) echo " {mb}" ;;\n' for pasta, mb in livres.items())
    corpo = f'echo " Disp."\ncase "${{!#}}" in\n{casos}  *) echo " 999999" ;;\nesac\n'
    (mundo.ferramentas / "df").unlink()
    _escrever_exec(mundo.ferramentas / "df", "#!/usr/bin/env bash\n" + corpo)


def _docker_com_raiz(mundo: Mundo, raiz: Path) -> None:
    raiz.mkdir(exist_ok=True)
    _escrever_exec(
        mundo.ferramentas / "docker",
        f'#!/usr/bin/env bash\n[ "$1" = info ] && [ "$2" = --format ] && echo "{raiz}"\nexit 0\n',
    )


@pytest.mark.parametrize(
    ("pasta", "livre", "piso"),
    [("tmp-pequeno", 850, 1536), ("raiz-dos-conteineres", 900, 8192)],
)
def test_sem_espaco_a_recusa_sai_antes_de_qualquer_job(
    mundo: Mundo, pasta: str, livre: int, piso: int
) -> None:
    """850 MB no `/tmp` e o disco cheio já viraram vermelho de teste, sem aviso."""
    tmp = mundo.base / "tmp-pequeno"
    tmp.mkdir()
    _docker_com_raiz(mundo, mundo.base / "raiz-dos-conteineres")
    _df_de_mentira(mundo, **{pasta: livre})
    r = mundo.rodar("--job", "glifos", CI_LOCAL_TMP=str(tmp))
    assert r.returncode == 2, r.stdout + r.stderr
    assert f"{pasta} tem {livre} MB livres e a corrida pede {piso} MB" in r.stderr, r.stderr
    assert "nada rodou" in r.stderr
    assert not (mundo.saida / "glifos.log").exists(), "o job foi lançado mesmo sem espaço"


def test_pasta_que_nao_existe_recusa_antes_de_qualquer_job(mundo: Mundo) -> None:
    pasta = mundo.base / "nao-existe"
    r = mundo.rodar("--job", "glifos", CI_LOCAL_TMP=str(pasta))
    assert r.returncode == 2 and f"não consegui medir o espaço de {pasta}" in r.stderr, r.stderr
    assert "nada rodou" in r.stderr
    assert not (mundo.saida / "glifos.log").exists()


def test_espaco_que_nao_se_mede_recusa_e_nao_passa_por_sobra(mundo: Mundo) -> None:
    """Não saber não é ter espaço: a trava existe para o vermelho falso não voltar."""
    (mundo.ferramentas / "df").unlink()
    _escrever_exec(mundo.ferramentas / "df", '#!/usr/bin/env bash\nexit 1\n')
    tmp = mundo.base / "tmp-sem-medida"
    tmp.mkdir()
    r = mundo.rodar("--job", "glifos", CI_LOCAL_TMP=str(tmp))
    assert r.returncode == 2 and "não consegui medir" in r.stderr, r.stderr
    assert not (mundo.saida / "glifos.log").exists()


def test_com_espaco_a_corrida_segue_e_usa_a_pasta_medida(mundo: Mundo) -> None:
    tmp = mundo.base / "tmp-grande"
    tmp.mkdir()
    _docker_com_raiz(mundo, mundo.base / "raiz-dos-conteineres")
    _df_de_mentira(mundo, **{"tmp-grande": 1536, "raiz-dos-conteineres": 8192})
    r = mundo.rodar("--job", "glifos", CI_LOCAL_TMP=str(tmp))
    assert r.returncode == 0, r.stdout + r.stderr
    assert f"{tmp}/cil." in next(
        ln for ln in mundo.log("glifos").splitlines() if ln.startswith("CWD:")
    )


def test_docker_de_outra_maquina_nao_impede_a_corrida(mundo: Mundo) -> None:
    """O `DockerRootDir` de um `DOCKER_HOST` remoto não existe aqui: não há o que medir."""
    _escrever_exec(
        mundo.ferramentas / "docker",
        '#!/usr/bin/env bash\n[ "$1" = info ] && [ "$2" = --format ] && echo /nao/existe\nexit 0\n',
    )
    assert mundo.rodar("--job", "glifos").returncode == 0


def _vivo(pid: int) -> bool:
    try:
        return Path(f"/proc/{pid}/stat").read_text(encoding="utf-8").split(") ")[1][0] != "Z"
    except OSError:
        return False


def test_a_corrida_morta_por_sinal_derruba_os_jobs_e_nao_deixa_a_pasta(mundo: Mundo) -> None:
    """Sem o `trap` do TERM, cada corrida interrompida deixa quase 1 GB no `/tmp` da máquina; sem
    derrubar o grupo do job, o `act` seguia rodando a suíte sem dono. O sinal é o INT: no TERM o
    `act` sai na hora e o contêiner fica de pé (medido em 07/11)."""
    tmp = mundo.base / "tmp"
    tmp.mkdir()
    _escrever_exec(
        mundo.casa / "bin" / "act",
        f"#!/usr/bin/env bash\ntrap 'echo INT > \"{mundo.base}/sinal\"; exit 0' INT\n"
        f"trap 'echo TERM > \"{mundo.base}/sinal\"; exit 0' TERM\n"
        f'echo $$ > "{mundo.base}/act-no-ar.novo"\n'
        f'mv "{mundo.base}/act-no-ar.novo" "{mundo.base}/act-no-ar"\n'
        "while :; do sleep 0.05; done\n",
    )
    ambiente = {
        "PATH": str(mundo.ferramentas), "HOME": str(mundo.base), "HEFESTO_CASA": str(mundo.casa),
        "CI_LOCAL_SAIDA": str(mundo.saida), "CI_LOCAL_IMAGEM": "imagem-de-mentira",
        "CI_LOCAL_TMP": str(tmp), "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_SYSTEM": os.devnull,
    }
    corrida = subprocess.Popen(
        ["bash", str(mundo.arvore / "scripts" / "ci-local.sh"), "--job", "glifos"],
        cwd=mundo.arvore, env=ambiente, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    prazo = time.monotonic() + 30
    while not (mundo.base / "act-no-ar").exists():
        assert time.monotonic() < prazo and corrida.poll() is None, "o act não subiu"
        time.sleep(0.05)
    act = int((mundo.base / "act-no-ar").read_text(encoding="utf-8"))
    assert list(tmp.glob("cil.*"))
    corrida.terminate()
    try:
        assert corrida.wait(timeout=10) == 143
        assert not list(tmp.glob("cil.*"))
        prazo = time.monotonic() + 3
        while _vivo(act) and time.monotonic() < prazo:
            time.sleep(0.05)
        assert not _vivo(act), "o act ficou rodando depois da corrida morta"
        assert (mundo.base / "sinal").read_text(encoding="utf-8").strip() == "INT"
    finally:
        if _vivo(act):
            os.kill(act, signal.SIGKILL)


def test_a_tabela_e_so_a_do_jobs_txt(mundo: Mundo) -> None:
    """Uma variável de ambiente não troca a decisão da casa."""
    r = mundo.rodar("--listar", TABELA="ROLA|glifos|rapido")
    assert r.returncode == 0 and "pypi" in r.stdout, r.stdout + r.stderr


def test_o_act_roda_a_arvore_do_indice_e_nao_o_disco(mundo: Mundo) -> None:
    mundo.rodar("--job", "glifos")
    log = mundo.log("glifos")
    arquivos = next(ln for ln in log.splitlines() if ln.startswith("ARQUIVOS:"))
    assert "versionado.txt" in arquivos
    assert "ignorado.txt" not in arquivos, (
        "o arquivo ignorado entrou no que o act roda: o runner do GitHub não o tem"
    )
    assert "/tmp/cil." in next(ln for ln in log.splitlines() if ln.startswith("CWD:"))


def test_o_act_nao_compartilha_a_ferramenta_nem_abre_o_servidor_para_a_rede_local(
    mundo: Mundo,
) -> None:
    mundo.rodar("--job", "glifos")
    log = mundo.log("glifos")
    assert "RUNNER_TOOL_CACHE=/opt/hostedtoolcache" not in log, (
        "o act monta o volume `act-toolcache` nessa pasta, e ele esconde o Python da imagem"
    )
    assert f"RUNNER_TOOL_CACHE={FERRAMENTAS_DA_IMAGEM}" in log
    assert f"AGENT_TOOLSDIRECTORY={FERRAMENTAS_DA_IMAGEM}" in log
    assert "--artifact-server-addr 127.0.0.1" in log
    assert "--cache-server-addr 127.0.0.1" in log
    assert "--pull=false" in log and "--rm" in log


def _diretivas(dockerfile: Path, nome: str) -> list[str]:
    linhas = dockerfile.read_text(encoding="utf-8").splitlines()
    return [ln.split(None, 1)[1] for ln in linhas if ln.startswith(f"{nome} ")]


@pytest.mark.parametrize("dockerfile", IMAGENS, ids=lambda d: d.name)
def test_a_imagem_roda_como_o_runner_do_github_e_nao_como_root(dockerfile: Path) -> None:
    """MORDIDA: sem o `USER runner`, as pernas voltam a rodar com uid 0 e 42 arquivos reprovam."""
    assert _diretivas(dockerfile, "USER")[-1:] == ["runner"]
    env = " ".join(_diretivas(dockerfile, "ENV"))
    assert "USER=runner" in env and "RUNNER_USER=runner" in env, "a imagem da act diz root"
    assert f"AGENT_TOOLSDIRECTORY={FERRAMENTAS_DA_IMAGEM}" in env
    assert any(RUNNER_DO_GITHUB.name in ln for ln in _diretivas(dockerfile, "RUN"))


def test_o_usuario_da_imagem_e_o_do_runner_com_sudo_sem_senha() -> None:
    texto = RUNNER_DO_GITHUB.read_text(encoding="utf-8")
    assert "useradd --uid 1001" in texto, "o runner do GitHub é o uid 1001"
    assert "NOPASSWD:ALL" in texto, "os passos dos workflows chamam `sudo` sem senha"
    assert "patchelf --set-rpath" in texto, "o Python nasce apontando para /opt/hostedtoolcache"


@pytest.mark.parametrize("pacote", ["patchelf", "sound-theme-freedesktop", "xvfb"])
def test_a_imagem_traz_o_que_o_runner_traz(pacote: str) -> None:
    """MORDIDA: sem o `xvfb`, a guarda da tela sai com rc=1 no `lint-test`."""
    apt = next(ln for ln in _diretivas(IMAGENS[0], "RUN") if "apt-get update" in ln)
    continuacao = IMAGENS[0].read_text(encoding="utf-8").split(apt, 1)[1].split("\nENV ", 1)[0]
    assert pacote in continuacao.split(), f"a imagem não instala {pacote}"


@pytest.mark.parametrize(("no_act", "pula"), [(True, True), (False, False)], ids=["act", "casa"])
def test_a_caixa_que_nao_abre_so_pula_no_act(
    monkeypatch: pytest.MonkeyPatch, no_act: bool, pula: bool,
) -> None:
    """Na casa e no GitHub a caixa que não abre reprova: o `bwrap` existe e o produto conta com ele.

    MORDIDA: tirar a condição do `ACT` de `exigir_caixa_do_bwrap` esconde a caixa quebrada."""
    import tests.conftest as casa

    monkeypatch.setattr(casa, "_por_que_o_bwrap_nao_abre_a_caixa", lambda: "o /proc não monta")
    monkeypatch.setattr(casa.shutil, "which", lambda _nome: "/usr/bin/bwrap")
    monkeypatch.setenv("ACT", "true") if no_act else monkeypatch.delenv("ACT", raising=False)
    try:
        casa.exigir_caixa_do_bwrap()
        pulou = False
    except pytest.skip.Exception:
        pulou = True
    assert pulou is pula


def _pythons_da_imagem(dockerfile: Path) -> set[str]:
    achado = re.search(r'PYTHONS_DO_RUNNER="([^"]+)"', dockerfile.read_text(encoding="utf-8"))
    assert achado, f"{dockerfile.name} não diz quais Pythons traz"
    return set(achado.group(1).split())


def _pythons_pedidos() -> set[tuple[str, str]]:
    pedidos = set()
    for job in _jobs_dos_workflows().values():
        matriz = (job.get("strategy") or {}).get("matrix") or {}
        pernas = matriz.get("os") or [job.get("runs-on")]
        for passo in job.get("steps") or []:
            if not str(passo.get("uses", "")).startswith("actions/setup-python@"):
                continue
            versao = str(passo["with"]["python-version"])
            versoes = matriz["python"] if "matrix.python" in versao else [versao]
            pedidos |= {(str(perna), str(v)) for perna in pernas for v in versoes}
    return pedidos


def test_toda_versao_que_um_workflow_pede_vem_na_imagem_do_runner_dele() -> None:
    """MORDIDA: tirar o 3.10 do `Dockerfile` reprova (o `lint-test` e o `acentuacao` o pedem).

    Sem a versão no cache de ferramentas o setup-python busca o manifesto a cada job, e o manifesto
    cortado no meio sai 0 sem Python nenhum: medido em 06/11/2026, cinco chamadas em doze."""
    pedidos = _pythons_pedidos()
    assert {("ubuntu-latest", "3.10"), ("ubuntu-22.04", "3.12")} <= pedidos
    do_ultimo, do_22 = (_pythons_da_imagem(dockerfile) for dockerfile in IMAGENS)
    faltam = sorted(
        (perna, versao) for perna, versao in pedidos
        if versao not in (do_22 if perna == "ubuntu-22.04" else do_ultimo))
    assert not faltam, f"versão que nenhuma imagem traz: {faltam}"


def test_o_contener_tem_quem_recolhe_o_orfao(mundo: Mundo) -> None:
    """O PID 1 do `act` é um `tail`, que não recolhe filho: o órfão morto fica zumbi e `kill -0`
    responde que ele vive. No GitHub o PID 1 é o systemd. MORDIDA: tirar o `--init` do script."""
    mundo.rodar("--job", "glifos")
    achado = re.search(r"--container-options (\S+)", mundo.log("glifos"))
    assert achado and achado.group(1) == "--init", mundo.log("glifos")


def test_o_tmp_do_contener_e_memoria_como_o_da_casa(mundo: Mundo) -> None:
    """A captura do pytest grava em `/tmp`: no disco da máquina, a escrita do fio do uhid parou
    155 ms a 2 s dentro do `join` do tique, e o disco cheio virou 4798 erros de ENOSPC. MORDIDA:
    tirar o `--tmpfs` do script."""
    mundo.rodar("--job", "glifos")
    assert "--tmpfs /tmp:exec,mode=1777" in mundo.log("glifos"), mundo.log("glifos")


def test_o_script_do_runner_entra_no_nome_da_imagem(mundo: Mundo) -> None:
    """MORDIDA: tirar o `runner-do-github.sh` do `sha256sum` faz a imagem velha seguir valendo."""
    pasta = mundo.arvore / "scripts" / "ci-local"
    (pasta / "Dockerfile").write_text("FROM base\n", encoding="utf-8")

    def imagem_com(texto: str) -> str:
        (pasta / "runner-do-github.sh").write_text(texto, encoding="utf-8")
        mundo.rodar("--job", "glifos", CI_LOCAL_IMAGEM="")
        achado = re.search(r"ubuntu-latest=(hefesto-ci-local:\w+)", mundo.log("glifos"))
        assert achado, mundo.log("glifos")
        return achado.group(1)

    assert imagem_com("uma\n") != imagem_com("outra\n")


def _passos_do_yaml_do_log(log: str) -> list[str]:
    corpo = log.split("---YAML---\n", 1)[1].split("---FIM---", 1)[0]
    dados = yaml.safe_load(corpo)
    return [
        p.get("name", "")
        for j in dados["jobs"].values()
        for p in (j.get("steps") or [])
        if isinstance(p, dict)
    ]


def test_o_rapido_tira_a_suite_da_copia_e_o_completo_a_deixa(mundo: Mundo) -> None:
    mundo.rodar("--rapido")
    passos = _passos_do_yaml_do_log(mundo.log("lint-test"))
    assert "Pytest unit" not in passos and "Pytest core" not in passos
    assert "Os portões do job, pelo nome na tabela" in passos, (
        "o --rapido tirou mais do que a tabela mandou")
    assert "A suíte inteira sob Xvfb, com o GTK real" not in _passos_do_yaml_do_log(
        mundo.log("gtk-real")
    )
    shutil.rmtree(mundo.saida)
    mundo.rodar("--completo")
    assert "Pytest unit" in _passos_do_yaml_do_log(mundo.log("lint-test"))
    assert "A suíte inteira sob Xvfb, com o GTK real" in _passos_do_yaml_do_log(
        mundo.log("gtk-real")
    )


def test_o_job_avulso_roda_o_yaml_inteiro_e_so_tira_o_que_mandam(mundo: Mundo) -> None:
    mundo.rodar("--job", "lint-test")
    assert "Pytest unit" in _passos_do_yaml_do_log(mundo.log("lint-test"))
    shutil.rmtree(mundo.saida)
    mundo.rodar("--job", "lint-test", "--sem-passo", "lint-test|Pytest unit")
    passos = _passos_do_yaml_do_log(mundo.log("lint-test"))
    assert "Pytest unit" not in passos and "Pytest core" in passos


def _yaml_do_log(log: str) -> dict[str, Any]:
    dados: dict[str, Any] = yaml.safe_load(log.split("---YAML---\n", 1)[1].split("---FIM---", 1)[0])
    return dados


def test_sem_needs_tira_so_a_dependencia_que_a_tabela_manda(mundo: Mundo) -> None:
    mundo.rodar("--completo")
    smoke = _yaml_do_log(mundo.log("runtime-smoke"))["jobs"]["runtime-smoke"]
    assert "needs" not in smoke, (
        "o needs: lint-test mandaria o act rodar a suíte inteira antes do smoke"
    )
    release = _yaml_do_log(mundo.log("deb-install-smoke"))["jobs"]
    assert "needs" not in release["deb"], (
        "o deb ainda manda o act rodar o `build` (e a suíte) antes dele"
    )
    assert release["deb-install-smoke"]["needs"] == ["deb"], (
        "o artefato do .deb vem do `deb`: esse needs fica"
    )
    original = yaml.safe_load((WORKFLOWS / "release.yml").read_text(encoding="utf-8"))["jobs"]
    assert release["github-release"]["needs"] == original["github-release"]["needs"]


def test_o_checkout_com_ref_vira_o_da_arvore_local(mundo: Mundo) -> None:
    """Com `ref:` o act roda o checkout de verdade e busca no servidor um repositório qualquer."""
    mundo.rodar("--completo")
    for job, onde_rodou in (("build", "build"), ("deb", "deb-install-smoke")):
        passos = _yaml_do_log(mundo.log(onde_rodou))["jobs"][job]["steps"]
        checkout = next(p for p in passos if str(p.get("uses", "")).startswith("actions/checkout"))
        assert "ref" not in (checkout.get("with") or {}), f"o checkout do {job} ainda pede ref:"
    assert "ref:" in (WORKFLOWS / "release.yml").read_text(encoding="utf-8"), (
        "o teste deixou de medir o que o YAML tem"
    )


def test_a_matriz_de_runners_roda_uma_perna_por_chamada_com_a_imagem_do_usuario(
    mundo: Mundo,
) -> None:
    """Com as duas imagens no mesmo `-P` o act dava a MESMA imagem às duas pernas, e ao acaso."""
    mundo.rodar("--job", "deb")
    log = mundo.log("deb")
    assert "=== a perna ubuntu-24.04 (rc=0)" in log and "=== a perna ubuntu-22.04 (rc=0)" in log
    chamadas = [ln for ln in log.splitlines() if ln.startswith("ARGS:")]
    assert len(chamadas) == 2, chamadas
    assert "--matrix os:ubuntu-24.04" in chamadas[0] and "ubuntu-22.04=" not in chamadas[0]
    assert "ubuntu-24.04=catthehacker/ubuntu:act-24.04" in chamadas[0]
    assert "--matrix os:ubuntu-22.04" in chamadas[1]
    assert "ubuntu-22.04=catthehacker/ubuntu:act-22.04" in chamadas[1]


def test_o_ubuntu_latest_roda_na_imagem_do_26_04_como_o_runner(mundo: Mundo) -> None:
    """O `ubuntu-latest` do GitHub é o 26.04: na imagem do 24.04 o vermelho dele não aparece."""
    r = mundo.rodar("--job", "glifos", CI_LOCAL_IMAGEM="")
    chamadas = [ln for ln in mundo.log("glifos").splitlines() if ln.startswith("ARGS:")]
    assert r.returncode == 0 and len(chamadas) == 1, r.stderr
    assert "ubuntu-latest=catthehacker/ubuntu:act-26.04-dev" in chamadas[0]
    assert "ubuntu-26.04=catthehacker/ubuntu:act-26.04-dev" in chamadas[0]
    assert "ubuntu-24.04=" not in chamadas[0], "o job do 26.04 montou também a imagem do 24.04"


def test_o_job_que_nomeia_o_24_04_roda_na_imagem_do_24_04(mundo: Mundo) -> None:
    """O `peca-gdk` diz `runs-on: ubuntu-24.04`: só ele e as pernas do 24.04 pedem essa imagem."""
    r = mundo.rodar("--job", "peca-gdk", CI_LOCAL_IMAGEM="")
    chamadas = [ln for ln in mundo.log("peca-gdk").splitlines() if ln.startswith("ARGS:")]
    assert r.returncode == 0 and len(chamadas) == 1, r.stderr
    assert "ubuntu-24.04=catthehacker/ubuntu:act-24.04" in chamadas[0]
    assert "ubuntu-latest=catthehacker/ubuntu:act-26.04-dev" in chamadas[0]


def test_a_perna_pedida_e_a_unica_que_roda(mundo: Mundo) -> None:
    mundo.rodar("--job", "deb", "--perna", "ubuntu-22.04")
    log = mundo.log("deb")
    assert len([ln for ln in log.splitlines() if ln.startswith("ARGS:")]) == 1
    assert "--matrix os:ubuntu-22.04" in log and "=== a perna ubuntu-24.04" not in log


def test_cada_chamada_trabalha_numa_copia_do_cache_das_actions(mundo: Mundo) -> None:
    """Dois act no mesmo `~/.cache/act` se pisam (`Unable to reset to <sha>: EOF`)."""
    compartilhado = mundo.base / ".cache" / "act"
    (compartilhado / "actions-fake@v1").mkdir(parents=True)
    (compartilhado / "actions-fake@v1" / "marca").write_text("x", encoding="utf-8")
    mundo.rodar("--job", "glifos")
    log = mundo.log("glifos")
    args = next(ln for ln in log.splitlines() if ln.startswith("ARGS:")).split()
    privado = args[args.index("--action-cache-path") + 1]
    assert privado != str(compartilhado) and privado.startswith("/tmp/cil."), privado
    assert "actions-fake@v1" in next(ln for ln in log.splitlines() if ln.startswith("CACHE_ACOES:"))
    assert (compartilhado / "actions-novo@v1" / "x").is_file(), "o que o act baixou não voltou"
    assert not Path(privado).exists(), "a cópia ficou para trás"


def test_com_as_actions_em_cache_o_act_nao_baixa_de_novo(mundo: Mundo) -> None:
    mundo.rodar("--job", "glifos")
    assert "--action-offline-mode" not in mundo.log("glifos"), "sem a cópia local ele tem de baixar"
    texto = (WORKFLOWS / "ci.yml").read_text(encoding="utf-8")
    usos = re.findall(r"uses:\s*(actions/[A-Za-z0-9_.-]+)@(\S+)", texto)
    pastas = {f"{a.replace('/', '-')}@{ref}" for a, ref in usos if a != "actions/checkout"}
    esperadas = {"actions-setup-python", "actions-upload-artifact", "actions-download-artifact"}
    assert {p.split("@")[0] for p in pastas} >= esperadas
    for pasta in sorted(pastas):
        (mundo.base / ".cache" / "act" / pasta).mkdir(parents=True, exist_ok=True)
    mundo.rodar("--job", "glifos")
    assert "--action-offline-mode" in mundo.log("glifos")


def test_o_job_sem_matriz_de_runners_roda_numa_chamada_so(mundo: Mundo) -> None:
    mundo.rodar("--job", "glifos")
    log = mundo.log("glifos")
    assert len([ln for ln in log.splitlines() if ln.startswith("ARGS:")]) == 1
    assert "--matrix" not in log.split("---YAML---")[0]


def test_uma_perna_vermelha_faz_o_job_vermelho(mundo: Mundo) -> None:
    r = mundo.rodar("--job", "deb", FAKE_FALHA="deb")
    assert r.returncode == 1 and "1 vermelho(s) [deb]" in r.stdout


def test_o_job_que_e_plano_de_outro_nao_roda_sozinho_ao_lado_dele(mundo: Mundo) -> None:
    """Dois act com um job em comum brigam pelo mesmo container (`Conflict. The container name`)."""
    r = mundo.rodar("--job", "deb,deb-install-smoke")
    assert r.returncode == 0, r.stdout + r.stderr
    assert "2 verde(s)" in r.stdout.strip().splitlines()[-1]
    assert "rodou dentro do plano de deb-install-smoke" in mundo.log("deb")
    assert not (mundo.saida / "deb.seg").exists(), (
        "o deb rodou o próprio act ao lado do que o cobre"
    )
    chamadas = [ln for ln in mundo.log("deb-install-smoke").splitlines() if ln.startswith("ARGS:")]
    assert len(chamadas) == 2, "o deb-install-smoke roda as duas pernas, e o deb vai nas duas"
    r = mundo.rodar("--job", "deb,deb-install-smoke", FAKE_FALHA="deb-install-smoke")
    assert r.returncode == 1 and "2 vermelho(s)" in r.stdout.strip().splitlines()[-1]


def test_o_runtime_smoke_nao_cobre_o_lint_test_porque_o_needs_dele_sai(mundo: Mundo) -> None:
    r = mundo.rodar("--job", "runtime-smoke,lint-test")
    assert r.returncode == 0 and "2 verde(s)" in r.stdout.strip().splitlines()[-1]
    assert len([ln for ln in mundo.log("lint-test").splitlines() if ln.startswith("ARGS:")]) == 1
    assert "rodou dentro" not in mundo.log("lint-test")


def test_job_que_fica_fora_de_casa_nao_roda_calado(mundo: Mundo) -> None:
    r = mundo.rodar("--job", "pypi")
    assert r.returncode == 2 and "não roda em casa" in r.stderr
    r = mundo.rodar("--job", "job-que-nao-existe")
    assert r.returncode == 2


def test_o_modo_e_pedido(mundo: Mundo) -> None:
    r = mundo.rodar()
    assert r.returncode == 2 and "--rapido" in r.stderr


def test_o_ci_de_casa_nao_tem_lista_propria_de_portoes() -> None:
    """O `ci-local.sh` roda o YAML pelo `act`; o comando de cada portão mora só na tabela.

    O-CI-CHAMA-OS-PORTOES-PELO-NOME-01 (10/10/2026): uma terceira cópia dos comandos aqui
    seria a mesma divergência calada que o `--so` tirou do `ci.yml`.
    """
    from tests.unit.test_portao_a_lista_de_portoes_e_uma_so import PORTOES_SH, tabela

    texto = SCRIPT.read_text(encoding="utf-8")
    citados = sorted(
        id_ for id_, (_, runner, argv) in tabela(PORTOES_SH.read_text(encoding="utf-8")).items()
        if runner != "bin" and argv.split()[0] in texto
    )
    assert not citados, f"o ci-local.sh cita o comando de portão da tabela: {citados}"


TITULO_DE_MENTIRA = "Jogo Vedado De Mentira"


def _linha(log: str, prefixo: str) -> str:
    return next(ln for ln in log.splitlines() if ln.startswith(prefixo))


def test_a_lista_vedada_de_casa_chega_ao_act_como_segredo_e_o_valor_nao_vaza(mundo: Mundo) -> None:
    lista = mundo.base / ".config" / "hefesto" / "biblioteca-vedada"
    lista.parent.mkdir(parents=True)
    lista.write_text(TITULO_DE_MENTIRA + "\n", encoding="utf-8")
    r = mundo.rodar("--job", "glifos")
    log = mundo.log("glifos")
    assert "-s HEFESTO_BIBLIOTECA_VEDADA" in _linha(log, "ARGS:")
    assert _linha(log, "SEGREDO:") == "SEGREDO: veio"
    assert TITULO_DE_MENTIRA not in log + r.stdout + r.stderr


def test_o_segredo_do_ambiente_vence_a_lista_de_casa(mundo: Mundo) -> None:
    r = mundo.rodar("--job", "glifos", HEFESTO_BIBLIOTECA_VEDADA=TITULO_DE_MENTIRA)
    log = mundo.log("glifos")
    assert "-s HEFESTO_BIBLIOTECA_VEDADA" in _linha(log, "ARGS:")
    assert _linha(log, "SEGREDO:") == "SEGREDO: veio"
    assert TITULO_DE_MENTIRA not in log + r.stdout + r.stderr


def test_sem_a_lista_o_act_roda_sem_segredo_e_o_script_diz(mundo: Mundo) -> None:
    r = mundo.rodar("--job", "glifos")
    log = mundo.log("glifos")
    assert "HEFESTO_BIBLIOTECA_VEDADA" not in _linha(log, "ARGS:")
    assert _linha(log, "SEGREDO:").strip() == "SEGREDO:"
    assert "sem a lista da biblioteca vedada" in r.stderr
