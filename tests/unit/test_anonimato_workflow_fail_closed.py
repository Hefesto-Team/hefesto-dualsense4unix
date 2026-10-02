"""O portão de anonimato do servidor não aprova mais quando NÃO CONSEGUE medir."""
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

EMAIL_VENENOSO = "dev@open" "ai.com"

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


def test_o_git_log_do_intervalo_nao_engole_o_codigo_de_saida() -> None:
    """A cura em uma linha: sem `|| true` e sem `2>/dev/null` no git log que"""
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
    """O runner roda todo `run:` com `bash -e`."""
    for linha in _sem_comentarios(_linhas_da_auditoria()):
        if "git log" in linha and "%H" in linha:
            assert re.search(r"\|\|\s*RC_\w+=\$\?", linha), (
                f"git log sem captura do código sob `bash -e`: {linha.strip()!r}"
            )


def test_entre_o_git_log_e_o_primeiro_exit_0_existe_um_exit_1() -> None:
    """Reprova se o `exit 0` incondicional voltar."""
    linhas = _sem_comentarios(_linhas_da_auditoria())
    i_git = next(
        (i for i, ln in enumerate(linhas) if "git log" in ln and "%H" in ln), None
    )
    assert i_git is not None, "o passo não monta mais a lista de commits"

    i_exit0 = next(
        (i for i, ln in enumerate(linhas) if i > i_git and "exit 0" in ln), None
    )
    if i_exit0 is None:
        return
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
    """A outra metade da separação: intervalo que RESOLVE e não tem commit não"""
    shell = _shell_da_auditoria()
    assert "Nada a auditar" in shell


def _git(repo: Path, *args: str, env: dict[str, str] | None = None) -> None:
    """git com os ganchos globais desligados — a máquina de desenvolvimento tem"""
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
    """Executa o shell REAL do passo, extraído do YAML, no repo de mentira."""
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
    """O caso do force-push: `before` órfão, e nem o topo resolve."""
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
    """O recuo não pode ser carimbo: quando o intervalo não resolve e o topo"""
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
