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
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest
import yaml

RAIZ = Path(__file__).resolve().parents[2]
WORKFLOWS = RAIZ / ".github" / "workflows"
TABELA = RAIZ / "scripts" / "ci-local" / "jobs.txt"
SCRIPT = RAIZ / "scripts" / "ci-local.sh"

# O que o script usa. O PATH da árvore de mentira só tem isto (mais o `act` e o `docker` de
# mentira), e é por isso que «sem act» e «sem docker» são medidas de verdade.
FERRAMENTAS = (
    "awk",
    "basename",
    "bash",
    "cat",
    "cp",
    "cut",
    "date",
    "dirname",
    "git",
    "grep",
    "head",
    "ls",
    "mkdir",
    "mktemp",
    "mv",
    "pwd",
    "rm",
    "sed",
    "sha256sum",
    "sort",
    "tr",
    "uniq",
    "wc",
)
RUNNERS_QUE_O_ACT_MAPEIA = {"ubuntu-latest", "ubuntu-24.04"}


# --- a tabela contra os workflows ------------------------------------------------------------


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
            continue  # o container do job manda; o runner é só o hospedeiro
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


# --- o script, numa árvore de mentira ----------------------------------------------------------


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
echo "---YAML---"
cat "$yml"
echo "---FIM---"
TEXTO="Temporary failure resolving 'archive.ubuntu.com'"
# a rede caída como o apt a escreve, na saída de um passo (`[job]   | texto`)
case ",${FAKE_REDE:-}," in *",$job,"*)
  echo "[CI/$job]   | W: Failed to fetch http://archive.ubuntu.com/InRelease  $TEXTO"
  exit 1 ;; esac
# o docker que não respondeu ao limpar o container de um job que passou
case ",${FAKE_DOCKER:-}," in *",$job,"*)
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
    # job do workflow sem decisão: reprova e nomeia
    sem = Mundo(
        tmp_path / "b", tabela=_sem_linha(TABELA.read_text(encoding="utf-8"), "ROLA|glifos|")
    )
    r = sem.rodar("--rapido", "--conferir")
    assert r.returncode == 2 and "glifos" in r.stderr, r.stderr
    # linha que cita job que não existe
    sobra = Mundo(
        tmp_path / "c",
        tabela=TABELA.read_text(encoding="utf-8") + "ROLA|job-que-nao-existe|rapido\n",
    )
    r = sobra.rodar("--listar")
    assert r.returncode == 2 and "job-que-nao-existe" in r.stderr, r.stderr
    # fora de casa sem motivo
    tabela = TABELA.read_text(encoding="utf-8").replace("FORA-DE-CASA|pypi|", "FORA-DE-CASA|pypi")
    r = Mundo(tmp_path / "d", tabela=tabela).rodar("--listar")
    assert r.returncode == 2 and "pypi" in r.stderr, r.stderr
    # PULA-NO-RAPIDO de passo que o YAML não tem
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


def test_o_texto_da_rede_citado_dentro_do_log_nao_e_rede(mundo: Mundo) -> None:
    """Um teste que cita a frase da rede caída não faz o job vermelho virar «não rodou»."""
    r = mundo.rodar("--rapido", FAKE_CITA="glifos")
    assert r.returncode == 1, r.stdout + r.stderr
    assert "1 vermelho(s) [glifos]" in r.stdout and "0 não rodado(s)" in r.stdout


def test_vermelho_vale_mais_que_nao_rodado_no_codigo_de_saida(mundo: Mundo) -> None:
    r = mundo.rodar("--rapido", FAKE_FALHA="glifos", FAKE_REDE="pre-commit")
    assert r.returncode == 1
    assert "[glifos]" in r.stdout and "[pre-commit]" in r.stdout


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
    assert "RUNNER_TOOL_CACHE=/tmp/hostedtoolcache" in log, (
        "o Python do setup-python voltou a ficar num volume que sobrevive ao job"
    )
    assert "--artifact-server-addr 127.0.0.1" in log
    assert "--cache-server-addr 127.0.0.1" in log
    assert "--pull=false" in log and "--rm" in log


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
    assert "Ruff" in passos, "o --rapido tirou mais do que a tabela mandou"
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
    # e o que a tabela não manda tirar continua como o YAML escreveu
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


def test_a_matriz_de_runners_roda_uma_perna_por_chamada_com_a_imagem_dela(mundo: Mundo) -> None:
    """Com as duas imagens no mesmo `-P` o act dava a MESMA imagem às duas pernas, e ao acaso."""
    mundo.rodar("--job", "deb")
    log = mundo.log("deb")
    assert "=== a perna ubuntu-24.04 (rc=0)" in log and "=== a perna ubuntu-22.04 (rc=0)" in log
    chamadas = [ln for ln in log.splitlines() if ln.startswith("ARGS:")]
    assert len(chamadas) == 2, chamadas
    assert "--matrix os:ubuntu-24.04" in chamadas[0] and "ubuntu-22.04=" not in chamadas[0]
    assert "--matrix os:ubuntu-22.04" in chamadas[1]
    assert "ubuntu-22.04=catthehacker/ubuntu:act-22.04" in chamadas[1]


def test_a_perna_pedida_e_a_unica_que_roda(mundo: Mundo) -> None:
    mundo.rodar("--job", "deb", "--perna", "ubuntu-22.04")
    log = mundo.log("deb")
    assert len([ln for ln in log.splitlines() if ln.startswith("ARGS:")]) == 1
    assert "--matrix os:ubuntu-22.04" in log and "=== a perna ubuntu-24.04" not in log


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
    chamadas = [ln for ln in mundo.log("deb-install-smoke").splitlines() if ln.startswith("ARGS:")]
    assert len(chamadas) == 2, "o deb-install-smoke roda as duas pernas, e o deb vai dentro delas"
    # falhando o que cobre, o coberto leva o mesmo código: não fica verde por ter sido «só um plano»
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
