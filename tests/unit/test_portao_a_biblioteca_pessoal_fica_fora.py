"""O portão da biblioteca pessoal morde: num repositório de mentira, com uma lista de mentira."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
PORTAO = RAIZ / "scripts" / "check_a_biblioteca_pessoal_fica_fora.py"
VEDADOS = ("Pássaro Azul Distante", "Montanha Quebrada")


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    raiz = tmp_path / "repo"
    raiz.mkdir()
    _git(raiz, "init", "-q")
    (raiz / "LEIAME.md").write_text("nada de biblioteca aqui\n", encoding="utf-8")
    _git(raiz, "add", "LEIAME.md")
    return raiz


@pytest.fixture
def lista(tmp_path: Path) -> Path:
    arquivo = tmp_path / "biblioteca-vedada"
    arquivo.write_text("# títulos de mentira\n" + "\n".join(VEDADOS) + "\n", encoding="utf-8")
    return arquivo


def _ambiente(tmp_path: Path, **extra: str) -> dict[str, str]:
    lar = tmp_path / "lar"
    lar.mkdir(exist_ok=True)
    env = {k: v for k, v in os.environ.items() if not k.startswith("HEFESTO_")}
    return {**env, "HOME": str(lar), "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1",
            **extra}


def _git(raiz: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-c", "user.name=x", "-c", "user.email=x@exemplo.invalid", *args],
        cwd=raiz, check=True, capture_output=True, text=True,
        env={**os.environ, "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"},
    ).stdout.strip()


def _roda(raiz: Path, *args: str, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, str(PORTAO), *args], cwd=raiz, env=env,
                          capture_output=True, text=True, check=False)


def _escreve(raiz: Path, relativo: str, texto: str) -> None:
    alvo = raiz / relativo
    alvo.parent.mkdir(parents=True, exist_ok=True)
    alvo.write_text(texto, encoding="utf-8")
    _git(raiz, "add", "--", relativo)


def _nao_vaza(saida: str) -> None:
    baixa = saida.casefold()
    for titulo in VEDADOS:
        for palavra in titulo.casefold().split():
            if len(palavra) > 4:
                assert palavra not in baixa, "a saída imprimiu o título vedado"


def test_o_repositorio_limpo_passa(repo: Path, lista: Path, tmp_path: Path) -> None:
    r = _roda(repo, "--lista", str(lista), env=_ambiente(tmp_path))
    assert r.returncode == 0, r.stdout
    assert "2 título(s) vedado(s)" in r.stdout


@pytest.mark.parametrize(
    "forma", ["PASSARO_AZUL_DISTANTE", "passaroAzulDistante", "pássaro-azul distante"]
)
def test_o_titulo_no_conteudo_reprova_em_qualquer_grafia(
    repo: Path, lista: Path, tmp_path: Path, forma: str
) -> None:
    _escreve(repo, "docs/nota.md", f"linha um\no jogo {forma} abriu\n")
    r = _roda(repo, "--lista", str(lista), env=_ambiente(tmp_path))
    assert r.returncode == 1
    assert "docs/nota.md:2: título vedado nº 1" in r.stdout
    _nao_vaza(r.stdout)


def test_o_titulo_dentro_de_outra_palavra_nao_casa(repo: Path, lista: Path, tmp_path: Path) -> None:
    _escreve(repo, "docs/nota.md", "xpassaroazuldistantex e MontanhaQuebradas\n")
    r = _roda(repo, "--lista", str(lista), env=_ambiente(tmp_path))
    assert r.returncode == 0, r.stdout


def test_o_titulo_no_nome_do_arquivo_reprova_sem_imprimir_o_caminho(
    repo: Path, lista: Path, tmp_path: Path
) -> None:
    _escreve(repo, "docs/montanha_quebrada.txt", "sem nada dentro\n")
    r = _roda(repo, "--lista", str(lista), env=_ambiente(tmp_path))
    assert r.returncode == 1
    assert "o nome casa o título vedado nº 2" in r.stdout
    assert "quebrada" not in r.stdout.casefold()


def test_o_titulo_no_nome_do_ramo_reprova(repo: Path, lista: Path, tmp_path: Path) -> None:
    arvore = _git(repo, "write-tree")
    commit = _git(repo, "commit-tree", arvore, "-m", "base")
    _git(repo, "update-ref", "refs/heads/voo/montanha-quebrada", commit)
    r = _roda(repo, "--lista", str(lista), env=_ambiente(tmp_path))
    assert r.returncode == 1
    assert "o ramo nº 1" in r.stdout and "título vedado nº 2" in r.stdout
    _nao_vaza(r.stdout)


def test_o_segredo_do_ci_vale_como_lista(repo: Path, tmp_path: Path) -> None:
    _escreve(repo, "docs/nota.md", "Pássaro Azul Distante\n")
    r = _roda(repo, env=_ambiente(tmp_path, HEFESTO_BIBLIOTECA_VEDADA="\n".join(VEDADOS)))
    assert r.returncode == 1
    assert "docs/nota.md:1: título vedado nº 1" in r.stdout


def test_sem_a_lista_so_a_estrutural_roda_e_o_ci_exige(repo: Path, tmp_path: Path) -> None:
    _escreve(repo, "docs/nota.md", "Pássaro Azul Distante\n")
    r = _roda(repo, env=_ambiente(tmp_path))
    assert r.returncode == 0
    assert "só a régua estrutural rodou" in r.stdout
    exige = _roda(repo, env=_ambiente(tmp_path, HEFESTO_EXIGE_BIBLIOTECA_VEDADA="1"))
    assert exige.returncode == 1


def test_perfil_de_jogo_real_reprova_e_o_ficticio_passa(
    repo: Path, lista: Path, tmp_path: Path
) -> None:
    real = {"name": "Jogo De Verdade", "match": {"type": "criteria",
                                                  "window_class": ["steam_app_1234567"],
                                                  "process_name": ["jogodeverdade"]}}
    _escreve(repo, "tests/fixtures/perfis_x/jogo_ficticio_a.json", json.dumps(real, indent=1))
    r = _roda(repo, "--lista", str(lista), env=_ambiente(tmp_path))
    assert r.returncode == 1
    assert "perfil 1, name não é fictício" in r.stdout
    assert "window_class[0]" in r.stdout and "process_name[0]" in r.stdout
    assert "appid fora da faixa fictícia" in r.stdout
    assert "1234567" not in r.stdout


def test_perfil_fora_dos_lugares_de_perfil_reprova(repo: Path, lista: Path, tmp_path: Path) -> None:
    ficticio = {"name": "Jogo Fictício A", "match": {"type": "any"}}
    _escreve(repo, "docs/perfil.json", json.dumps(ficticio))
    r = _roda(repo, "--lista", str(lista), env=_ambiente(tmp_path))
    assert r.returncode == 1
    assert "docs/perfil.json: perfil versionado fora dos lugares de perfil" in r.stdout


def test_os_sinteticos_do_ciclo_passam(repo: Path, lista: Path, tmp_path: Path) -> None:
    origem = RAIZ / "tests" / "fixtures" / "perfis_do_ciclo" / "sinteticos"
    destino = repo / "tests" / "fixtures" / "perfis_do_ciclo" / "sinteticos"
    shutil.copytree(origem, destino)
    _git(repo, "add", "tests")
    assert len(list(destino.glob("*.json"))) >= 20
    r = _roda(repo, "--lista", str(lista), env=_ambiente(tmp_path))
    assert r.returncode == 0, r.stdout


def test_a_revisao_e_medida_pelo_que_o_git_guarda(repo: Path, lista: Path, tmp_path: Path) -> None:
    _escreve(repo, "docs/nota.md", "Montanha Quebrada\n")
    arvore = _git(repo, "write-tree")
    commit = _git(repo, "commit-tree", arvore, "-m", "com o título")
    _git(repo, "rm", "-q", "--cached", "docs/nota.md")
    (repo / "docs" / "nota.md").unlink()
    assert _roda(repo, "--lista", str(lista), env=_ambiente(tmp_path)).returncode == 0
    r = _roda(repo, "--lista", str(lista), "--rev", commit, env=_ambiente(tmp_path))
    assert r.returncode == 1
    assert "docs/nota.md:1: título vedado nº 2" in r.stdout


def test_a_divida_declarada_avisa_e_a_divida_morta_reprova(
    repo: Path, lista: Path, tmp_path: Path
) -> None:
    _escreve(repo, "mockup/09-sistema.html", "<p>Pássaro Azul Distante</p>\n")
    r = _roda(repo, "--lista", str(lista), env=_ambiente(tmp_path))
    assert r.returncode == 0, r.stdout
    assert "dívida declarada" in r.stdout
    _escreve(repo, "mockup/09-sistema.html", "<p>Jogo Fictício A</p>\n")
    morta = _roda(repo, "--lista", str(lista), env=_ambiente(tmp_path))
    assert morta.returncode == 1
    assert "mockup/09-sistema.html: dívida morta" in morta.stdout


def test_o_ramo_que_o_push_leva_e_medido_pelo_nome(repo: Path, lista: Path, tmp_path: Path) -> None:
    arvore = _git(repo, "write-tree")
    commit = _git(repo, "commit-tree", arvore, "-m", "base")
    ramo = "refs/heads/montanha_quebrada"
    r = _roda(repo, "--lista", str(lista), "--rev", commit, "--ramo", ramo, env=_ambiente(tmp_path))
    assert r.returncode == 1
    assert "o ramo nº 1 do `--ramo`: o nome casa o título vedado nº 2" in r.stdout
    limpo = _roda(repo, "--lista", str(lista), "--rev", commit, "--ramo", "refs/heads/dev",
                  env=_ambiente(tmp_path))
    assert limpo.returncode == 0, limpo.stdout
