"""O workflow `autoria` do servidor não aprova mais quando NÃO CONSEGUE medir.

Os passos de verdade são extraídos do YAML e rodados num repositório de brinquedo, com a
régua real e uma lista sintética: o que o CI executa é o que o teste executa.
"""
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from typing import Any, cast

import pytest

yaml = pytest.importorskip("yaml")

REPO = Path(__file__).resolve().parents[2]
WORKFLOWS = REPO / ".github" / "workflows"
WORKFLOW = WORKFLOWS / "autoria.yml"
JOB = "autoria"

CANARIO = "zqcanario" + "autoria"
LISTA = f"1 {CANARIO}\n2 subagente\n2 Subagente\n"
MAILMAP = "Pessoa Um <um@casa.test>\n"
UM = ("Pessoa Um", "um@casa.test")
DE_FORA = ("Fulana de Fora", "fulana@fora.test")
ZERO = "0" * 40
SHA_FANTASMA = ("dead" "beef" * 8)[:40]


def _workflow() -> dict[Any, Any]:
    assert WORKFLOW.exists(), f"{WORKFLOW} não encontrado: o CI perdeu a régua de autoria"
    dados = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    assert isinstance(dados, dict), "autoria.yml não é um mapeamento YAML"
    return dados


def _passos() -> list[dict[str, Any]]:
    return cast("list[dict[str, Any]]", _workflow()["jobs"][JOB]["steps"])


def _passo(nome: str) -> dict[str, Any]:
    achados = [p for p in _passos() if str(p.get("name", "")) == nome]
    assert achados, f"o passo {nome!r} sumiu do job {JOB}"
    return achados[0]


def test_o_workflow_antigo_saiu_e_o_novo_ficou() -> None:
    assert WORKFLOW.is_file()
    assert not (WORKFLOWS / "anonymity-check.yml").exists()


def test_a_lista_vem_do_secret_e_o_clone_traz_a_historia_inteira() -> None:
    dados = _workflow()
    assert dados["jobs"][JOB]["env"]["AUTORIA_VEDADOS"] == "${{ secrets.AUTORIA_VEDADOS }}"
    checkout = _passos()[0]
    assert str(checkout["uses"]).startswith("actions/checkout@")
    assert checkout["with"]["fetch-depth"] == 0, "a régua recusa clone raso"


def test_os_gatilhos_cobrem_todo_ramo_as_tags_o_pr_e_o_agendamento() -> None:
    gatilhos = _workflow()[True]  # `on:` vira True no YAML 1.1
    assert gatilhos["push"]["branches"] == ["**"], "o ramo de fecho precisa do check antes do dev"
    assert gatilhos["push"]["tags"] == ["v*"]
    assert "pull_request" in gatilhos and "schedule" in gatilhos and "workflow_dispatch" in gatilhos
    assert _workflow()["permissions"] == {"contents": "read"}


def test_todo_passo_de_conteudo_chama_a_regua_unica_e_nenhum_engole_o_codigo_de_saida() -> None:
    for passo in _passos()[1:]:
        corpo = str(passo["run"])
        assert "scripts/check_autoria.py" in corpo, f"{passo['name']}: não chama a régua única"
        assert "grep" not in corpo, f"{passo['name']}: vocabulário no YAML em vez de na lista"
        assert "|| true" not in corpo and "2>/dev/null" not in corpo, passo["name"]
        assert not passo.get("continue-on-error"), passo["name"]


def test_o_passo_do_pr_so_pula_o_texto_de_robo() -> None:
    passo = _passo("Título e corpo do PR")
    assert "Bot" in str(passo["if"])


# ---------------------------------------------------------------------------
# Os passos de verdade, num repositório de brinquedo
# ---------------------------------------------------------------------------


def _ambiente(extra: dict[str, str] | None = None) -> dict[str, str]:
    env = dict(os.environ)
    for chave in list(env):
        if chave.startswith(("GIT_AUTHOR", "GIT_COMMITTER", "AUTORIA_")):
            del env[chave]
    env.update({"GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"})
    env.update(extra or {})
    return env


def _git(repo: Path, *args: str, extra: dict[str, str] | None = None) -> str:
    r = subprocess.run(
        ["git", "-c", "core.hooksPath=/dev/null", "-c", "commit.gpgsign=false", *args],
        cwd=repo, env=_ambiente(extra), capture_output=True, text=True,
    )
    assert r.returncode == 0, r.stderr
    return r.stdout.strip()


def _commit(repo: Path, mensagem: str, autor: tuple[str, str] = UM) -> str:
    (repo / "a.txt").write_text(mensagem, encoding="utf-8")
    _git(repo, "add", "a.txt")
    _git(repo, "commit", "-q", "-m", mensagem, extra={
        "GIT_AUTHOR_NAME": autor[0], "GIT_AUTHOR_EMAIL": autor[1],
        "GIT_COMMITTER_NAME": autor[0], "GIT_COMMITTER_EMAIL": autor[1],
    })
    return _git(repo, "rev-parse", "HEAD")


@pytest.fixture()
def repo(tmp_path: Path) -> Path:
    r = tmp_path / "r"
    r.mkdir()
    _git(r, "init", "-q", "-b", "dev")
    (r / "scripts").mkdir()
    shutil.copy2(REPO / "scripts" / "check_autoria.py", r / "scripts" / "check_autoria.py")
    (r / ".mailmap").write_text(MAILMAP, encoding="utf-8")
    _git(r, "add", ".mailmap", "scripts")
    _commit(r, "chore: nasce")
    return r


def _rodar(repo: Path, nome_do_passo: str, extra: dict[str, str], lista: str | None = LISTA,
           entrada: str | None = None) -> subprocess.CompletedProcess[str]:
    """Executa o shell REAL do passo, extraído do YAML, sob `bash -e` como o runner."""
    script = repo.parent / "passo.sh"
    script.write_text(str(_passo(nome_do_passo)["run"]), encoding="utf-8")
    env = _ambiente({**extra, **({"AUTORIA_VEDADOS": lista} if lista is not None else {})})
    return subprocess.run(["bash", "-e", str(script)], cwd=repo, env=env, input=entrada,
                          capture_output=True, text=True)


def _saida(p: subprocess.CompletedProcess[str]) -> str:
    return p.stdout + p.stderr


PUSH = "O que o push traz"


def test_push_com_before_orfao_mede_a_historia_inteira(repo: Path) -> None:
    """O push forçado não vira «nada a auditar»: a identidade de fora na história reprova."""
    _commit(repo, "feat: de fora", autor=DE_FORA)
    topo = _commit(repo, "feat: limpo")
    p = _rodar(repo, PUSH, {"ANTES": ZERO, "DEPOIS": topo})
    assert p.returncode != 0, _saida(p)
    assert "VERMELHO" in p.stdout


def test_push_com_before_que_nao_resolve_reprova_em_vez_de_passar(repo: Path) -> None:
    _commit(repo, "feat: de fora", autor=DE_FORA)
    topo = _commit(repo, "feat: limpo")
    p = _rodar(repo, PUSH, {"ANTES": SHA_FANTASMA, "DEPOIS": topo})
    assert p.returncode != 0, _saida(p)


def test_push_com_before_orfao_e_historia_limpa_aprova(repo: Path) -> None:
    topo = _commit(repo, "feat: limpo")
    p = _rodar(repo, PUSH, {"ANTES": ZERO, "DEPOIS": topo})
    assert p.returncode == 0, _saida(p)
    assert "OK" in p.stdout


def test_push_com_before_valido_mede_o_que_foi_acrescentado(repo: Path) -> None:
    antes = _commit(repo, "feat: limpo")
    topo = _commit(repo, "fix: o subagente refez")
    p = _rodar(repo, PUSH, {"ANTES": antes, "DEPOIS": topo})
    assert p.returncode != 0, _saida(p)
    assert "(nível 2)" in p.stdout


def test_push_com_before_valido_e_commit_de_fora_reprova_pela_identidade(repo: Path) -> None:
    antes = _commit(repo, "feat: limpo")
    topo = _commit(repo, "feat: de fora", autor=DE_FORA)
    p = _rodar(repo, PUSH, {"ANTES": antes, "DEPOIS": topo})
    assert p.returncode != 0, _saida(p)


def test_push_limpo_com_before_valido_aprova(repo: Path) -> None:
    antes = _commit(repo, "feat: um")
    topo = _commit(repo, "feat: dois")
    p = _rodar(repo, PUSH, {"ANTES": antes, "DEPOIS": topo})
    assert p.returncode == 0, _saida(p)


def test_sem_o_secret_o_passo_diz_nao_medido_e_reprova(repo: Path) -> None:
    """O PR de fork não recebe o secret: o verde sobre o vazio é o que se evita."""
    topo = _commit(repo, "feat: limpo")
    p = _rodar(repo, PUSH, {"ANTES": ZERO, "DEPOIS": topo}, lista="")
    assert p.returncode != 0
    assert "NÃO MEDIDO" in p.stdout


def test_o_passo_do_pr_mede_a_historia_do_topo_e_o_que_ele_acrescenta(repo: Path) -> None:
    base = _commit(repo, "feat: base")
    topo = _commit(repo, "fix: o subagente refez")
    p = _rodar(repo, "O que o PR traz", {"BASE": base, "TOPO": topo})
    assert p.returncode != 0, _saida(p)


def test_o_passo_do_pr_com_base_que_nao_resolve_reprova(repo: Path) -> None:
    topo = _commit(repo, "feat: limpo")
    p = _rodar(repo, "O que o PR traz", {"BASE": SHA_FANTASMA, "TOPO": topo})
    assert p.returncode != 0, _saida(p)


def test_o_texto_do_pr_com_termo_reprova_e_o_limpo_passa(repo: Path) -> None:
    sujo = _rodar(repo, "Título e corpo do PR", {"TITULO": "fix: x", "CORPO": f"veja {CANARIO}"})
    assert sujo.returncode != 0 and CANARIO not in _saida(sujo)
    limpo = _rodar(repo, "Título e corpo do PR", {"TITULO": "fix: x", "CORPO": "corpo limpo"})
    assert limpo.returncode == 0, _saida(limpo)


def test_o_passo_da_arvore_mede_o_conteudo(repo: Path) -> None:
    topo = _commit(repo, f"feat: {CANARIO}")
    p = _rodar(repo, "A árvore", {"REV": topo})
    assert p.returncode != 0 and CANARIO not in _saida(p)
