"""O portão de anonimato do servidor não aprova mais quando NÃO CONSEGUE medir.

PUBLICAÇÃO-FIEL-01/E5, medido em 31/07 e curado em 01/08. O passo "Auditar
mensagens de commit" do `.github/workflows/anonymity-check.yml` montava a lista
de commits assim:

    MAPFILE=$(git log --pretty=format:'%H' "$RANGE" 2>/dev/null || true)
    if [ -z "$MAPFILE" ]; then
      echo "Nada a auditar (intervalo vazio)."
      exit 0
    fi

O `2>/dev/null || true` engolia o código de saída. Um `git log` que FALHA — ref
inválida, objeto ausente num clone raso, `before` órfão depois de force-push —
produzia exatamente o mesmo estado que "não havia commit no intervalo": lista
vazia. O portão então saía 0 sem olhar commit NENHUM, e o pior caso é o evento
mais arriscado: no force-push, o `github.event.before` pode apontar para um
commit que o checkout não tem. Esta main já levou dois force-push (a purga de
MAC de 20/07 e a sobrescrita de 29/07).

Era o único portão de segurança da casa que não bloqueava nada no pior caso, e
o anonimato é requisito duro daqui. A cura copia a polaridade do guarda de CI
do `release.yml`, que usa o mesmo idioma `|| true` e é fail-CLOSED: o que não dá
para medir reprova.

Os testes vêm em dois andares:

  - ESTRUTURAL, no molde do tests/unit/test_release_workflow_nomes_e_portoes.py:
    o YAML é lido e afirmado, para que o `exit 0` incondicional não volte.
  - COMPORTAMENTAL: o shell do passo é EXTRAÍDO do YAML e executado num repo
    git de mentira, com `RANGE` apontando para uma SHA que não existe. Não é
    preciso GitHub Actions para provar que o portão reprova — e é este andar
    que impede a cura de virar comentário bonito com o comportamento antigo.

O que esta cura NÃO faz, e continua valendo da E5: o workflow segue disparando
só em push e pull_request de `main` (`:11-15`), então branch de trabalho e tag
não passam por ele; e nenhum ruleset da `main` exige o check `scan-commits`, de
modo que o job reprova DEPOIS do push, sem impedi-lo. As duas coisas são de
outra natureza (uma muda o gatilho de todas as branches, a outra é configuração
do servidor, medida com `gh api`, não código) e ficaram fora desta entrega.

Nota sobre os textos venenosos usados aqui: eles são montados por CONCATENAÇÃO
(`"dev@open" "ai.com"`) de propósito. O `scripts/check_anonymity.sh` varre este
arquivo e reprova o nome do provedor escrito por inteiro — este arquivo não
está na lista de exclusões dele, e não deve estar.
"""
from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml")

REPO = Path(__file__).resolve().parents[2]
WORKFLOW = REPO / ".github" / "workflows" / "anonymity-check.yml"
JOB = "scan-commits"
PASSO_AUDITORIA = "Auditar mensagens de commit"

#: E-mail de provedor de IA, montado por partes (ver nota no topo do módulo).
EMAIL_VENENOSO = "dev@open" "ai.com"

#: SHA que não existe em repositório nenhum — é o `before` órfão do force-push.
SHA_FANTASMA = "dead" "beef" * 8
SHA_FANTASMA = SHA_FANTASMA[:40]


def _workflow() -> dict:
    if not WORKFLOW.exists():  # pragma: no cover — árvore sem o workflow
        pytest.skip(f"{WORKFLOW} não encontrado")
    dados = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    assert isinstance(dados, dict), "anonymity-check.yml não é um mapeamento YAML"
    return dados


def _passo(nome: str) -> dict:
    passos = _workflow()["jobs"][JOB]["steps"]
    achados = [p for p in passos if str(p.get("name", "")) == nome]
    assert achados, f"o passo {nome!r} sumiu do job {JOB}"
    return achados[0]


def _shell_da_auditoria() -> str:
    return str(_passo(PASSO_AUDITORIA)["run"])


def _linhas_da_auditoria() -> list[str]:
    return _shell_da_auditoria().splitlines()


def _sem_comentarios(linhas: list[str]) -> list[str]:
    return [ln for ln in linhas if not ln.strip().startswith("#")]


# --------------------------------------------------------------------------
# 1) Estrutural: o código de saída do git log não pode ser engolido.
# --------------------------------------------------------------------------


def test_o_git_log_do_intervalo_nao_engole_o_codigo_de_saida() -> None:
    """A cura em uma linha: sem `|| true` e sem `2>/dev/null` no git log que
    monta a lista de commits. Devolver qualquer um dos dois refaz o furo."""
    for linha in _sem_comentarios(_linhas_da_auditoria()):
        if "git log" not in linha or "%H" not in linha:
            continue
        assert "|| true" not in linha, (
            f"o `|| true` voltou ao git log que monta a lista: {linha.strip()!r}. "
            "Ele torna 'não consegui auditar' indistinguível de 'nada a auditar'."
        )
        assert "2>/dev/null" not in linha, (
            f"o erro do git log voltou a ir para /dev/null: {linha.strip()!r}"
        )


def test_o_passo_consulta_o_codigo_de_saida_do_git_log() -> None:
    shell = _shell_da_auditoria()
    assert re.search(r"RC_\w+=\$\?", shell), (
        "o passo não guarda mais o código de saída do git log — sem ele não há "
        "como separar erro de intervalo vazio"
    )


def test_a_captura_do_codigo_sobrevive_ao_bash_e() -> None:
    """O runner roda todo `run:` com `bash -e`.

    Sem o `|| RC_...=$?`, um git log que falha derruba o passo na própria linha:
    reprova — o que já é melhor que o fail-open —, mas sem a segunda tentativa
    e sem dizer QUAL intervalo não pôde ser auditado. A guarda existe para que
    a cura não perca a voz numa limpeza futura.
    """
    for linha in _sem_comentarios(_linhas_da_auditoria()):
        if "git log" in linha and "%H" in linha:
            assert re.search(r"\|\|\s*RC_\w+=\$\?", linha), (
                f"git log sem captura do código sob `bash -e`: {linha.strip()!r}"
            )


def test_entre_o_git_log_e_o_primeiro_exit_0_existe_um_exit_1() -> None:
    """Reprova se o `exit 0` incondicional voltar.

    A ordem no texto do passo é o contrato: primeiro se monta a lista, depois
    se trata a FALHA (com `exit 1`), e só então o vazio legítimo pode sair 0.
    Um `exit 0` que apareça antes de qualquer `exit 1` é o furo de volta.
    """
    linhas = _sem_comentarios(_linhas_da_auditoria())
    i_git = next(
        (i for i, ln in enumerate(linhas) if "git log" in ln and "%H" in ln), None
    )
    assert i_git is not None, "o passo não monta mais a lista de commits"

    i_exit0 = next(
        (i for i, ln in enumerate(linhas) if i > i_git and "exit 0" in ln), None
    )
    if i_exit0 is None:
        return  # sem saída-cedo não há fail-open a provar
    houve_exit_1 = any("exit 1" in ln for ln in linhas[i_git:i_exit0])
    assert houve_exit_1, (
        "o passo sai 0 depois do git log sem nenhum caminho de `exit 1` no meio: "
        "é o fail-open de PUBLICAÇÃO-FIEL-01/E5 de volta"
    )


def test_a_reprovacao_por_intervalo_irresoluvel_nomeia_o_intervalo() -> None:
    """Aceite da E5: sair 1 com o intervalo escrito na mensagem."""
    linhas = _sem_comentarios(_linhas_da_auditoria())
    erros_com_range = [
        ln
        for ln in linhas
        if "::error::" in ln and "$RANGE" in ln and "git log" in ln
    ]
    assert erros_com_range, (
        "nenhuma mensagem de erro cita o intervalo e o git log — quem lê o log "
        "do run não saberia o que não pôde ser auditado"
    )


def test_o_vazio_legitimo_continua_aprovando() -> None:
    """A outra metade da separação: intervalo que RESOLVE e não tem commit não
    pode reprovar, senão o portão vira ruído em todo push sem commit novo."""
    shell = _shell_da_auditoria()
    assert "Nada a auditar" in shell


# --------------------------------------------------------------------------
# 2) Comportamental: o shell do passo, rodado de verdade.
# --------------------------------------------------------------------------


def _git(repo: Path, *args: str, env: dict[str, str] | None = None) -> None:
    """git com os ganchos globais desligados — a máquina de desenvolvimento tem
    hook de coautoria instalado e ele não pode tocar num repo de teste."""
    ambiente = dict(os.environ)
    ambiente.update(env or {})
    subprocess.run(
        ["git", "-c", "core.hooksPath=/dev/null", "-c", "commit.gpgsign=false", *args],
        cwd=repo,
        env=ambiente,
        check=True,
        capture_output=True,
        text=True,
    )


def _commit(repo: Path, texto: str, mensagem: str, email: str) -> None:
    (repo / "arquivo.txt").write_text(texto, encoding="utf-8")
    _git(repo, "add", "arquivo.txt")
    _git(
        repo,
        "commit",
        "--no-verify",
        "-m",
        mensagem,
        env={
            "GIT_AUTHOR_NAME": "Fulana",
            "GIT_AUTHOR_EMAIL": email,
            "GIT_COMMITTER_NAME": "Fulana",
            "GIT_COMMITTER_EMAIL": email,
        },
    )


@pytest.fixture()
def repo_limpo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    _commit(repo, "um", "feat: o primeiro", "fulana@example.com")
    _commit(repo, "dois", "feat: o segundo", "fulana@example.com")
    return repo


def _sha(repo: Path, ref: str = "HEAD") -> str:
    saida = subprocess.run(
        ["git", "rev-parse", ref], cwd=repo, capture_output=True, text=True, check=True
    )
    return saida.stdout.strip()


def _rodar_o_passo(
    repo: Path, *, intervalo: str, topo: str
) -> subprocess.CompletedProcess[str]:
    """Executa o shell REAL do passo, extraído do YAML, no repo de mentira.

    `bash -e` de propósito: é o shell com que o runner executa um `run:` sem
    `shell:` declarado. Rodar sem o `-e` aqui esconderia toda uma classe de
    defeito — a de comando que derruba o passo antes da mensagem.
    """
    script = repo / "passo_auditoria.sh"
    script.write_text(_shell_da_auditoria(), encoding="utf-8")
    ambiente = dict(os.environ)
    ambiente.update({"RANGE": intervalo, "PUSH_AFTER": topo})
    return subprocess.run(
        ["bash", "-e", str(script)],
        cwd=repo,
        env=ambiente,
        capture_output=True,
        text=True,
    )


def test_intervalo_irresoluvel_reprova(repo_limpo: Path) -> None:
    """O caso do force-push: `before` órfão, e nem o topo resolve.

    Com o `|| true` de volta, este teste passa a ver returncode 0 com
    'Nada a auditar' — é a mordida desta cura.
    """
    proc = _rodar_o_passo(
        repo_limpo, intervalo=f"{SHA_FANTASMA}..HEAD", topo=SHA_FANTASMA
    )
    saida = proc.stdout + proc.stderr
    assert proc.returncode != 0, (
        "o portão APROVOU um intervalo que não conseguiu auditar: " + saida
    )
    assert "não consegui auditar" in saida
    assert SHA_FANTASMA in saida, "a mensagem não nomeia o intervalo"


def test_intervalo_vazio_de_verdade_aprova(repo_limpo: Path) -> None:
    """Intervalo que RESOLVE e não tem commit continua saindo 0."""
    proc = _rodar_o_passo(repo_limpo, intervalo="HEAD..HEAD", topo=_sha(repo_limpo))
    saida = proc.stdout + proc.stderr
    assert proc.returncode == 0, saida
    assert "Nada a auditar" in saida


def test_intervalo_valido_com_historia_limpa_aprova(repo_limpo: Path) -> None:
    proc = _rodar_o_passo(
        repo_limpo, intervalo="HEAD~1..HEAD", topo=_sha(repo_limpo)
    )
    saida = proc.stdout + proc.stderr
    assert proc.returncode == 0, saida
    assert "OK:" in saida


def test_identidade_de_provedor_de_ia_reprova(tmp_path: Path) -> None:
    """Contraprova de que o passo AUDITA: o que ele deve pegar, ele pega."""
    repo = tmp_path / "sujo"
    repo.mkdir()
    _git(repo, "init", "-q")
    _commit(repo, "um", "feat: o primeiro", "fulana@example.com")
    _commit(repo, "dois", "feat: o segundo", EMAIL_VENENOSO)
    proc = _rodar_o_passo(repo, intervalo="HEAD~1..HEAD", topo=_sha(repo))
    saida = proc.stdout + proc.stderr
    assert proc.returncode != 0, "o portão passou por cima de identidade de IA: " + saida
    assert "provedor IA" in saida


def test_recuo_para_o_topo_audita_de_verdade(tmp_path: Path) -> None:
    """O recuo não pode ser carimbo: quando o intervalo não resolve e o topo
    resolve, o topo tem de ser AUDITADO — com commit sujo lá, reprova."""
    repo = tmp_path / "sujo-com-intervalo-quebrado"
    repo.mkdir()
    _git(repo, "init", "-q")
    _commit(repo, "um", "feat: o primeiro", "fulana@example.com")
    _commit(repo, "dois", "feat: o segundo", EMAIL_VENENOSO)
    proc = _rodar_o_passo(
        repo, intervalo=f"{SHA_FANTASMA}..HEAD", topo=_sha(repo)
    )
    saida = proc.stdout + proc.stderr
    assert proc.returncode != 0, "o recuo para o topo virou carimbo: " + saida
    assert "provedor IA" in saida


def test_recuo_para_o_topo_avisa_no_log(repo_limpo: Path) -> None:
    """Auditar coisa diferente da pedida não pode acontecer em silêncio."""
    proc = _rodar_o_passo(
        repo_limpo, intervalo=f"{SHA_FANTASMA}..HEAD", topo=_sha(repo_limpo)
    )
    saida = proc.stdout + proc.stderr
    assert proc.returncode == 0, saida
    assert "::warning::" in saida
    assert "não resolvível" in saida
