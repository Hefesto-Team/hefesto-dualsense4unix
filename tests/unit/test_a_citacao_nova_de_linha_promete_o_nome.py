"""A citação de linha NOVA promete o nome (A-CITACAO-NOVA-DE-LINHA-PROMETE-O-NOME-01, 10/10/2026).

A crua (`x.py:3` sem nome) o `reapontar-citacoes.py` só leva pelo histórico, e cada uma vira
trabalho à mão do fecho. O `validar-citacoes-de-linha.py --novas` fecha a porta da crua nova: a
linha acrescentada desde o pé comum com o `dev`, em `docs/protocol` ou nas planilhas de
`docs/data`, reprova sem `` `nome` em `` antes nem `` (`nome`) `` depois. Tudo num repositório de
mentira em ``tmp_path``.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
SCRIPT = RAIZ / "scripts" / "validar-citacoes-de-linha.py"

X_PY = (
    "import os\n\ndef fala():\n    return os.sep\n\n\nclass Casa:\n    def guarda(self):\n"
    "        return 1\n")
CABECALHO_PARIDADE = (
    "aba,feature,veredito,sinal,sinal_espera,sinal_escopo,gtk_onde,html_onde,gtk_faz,html_faz,"
    "porque\n")


def _ambiente(casa: Path) -> dict[str, str]:
    return {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "HOME": str(casa),
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CEILING_DIRECTORIES": str(casa.parent),
        "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@exemplo.invalid",
        "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@exemplo.invalid",
    }


def _git(raiz: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(raiz), "-c", "core.hooksPath=/dev/null", *args],
                   check=True, capture_output=True, env=_ambiente(raiz.parent / "casa"))


def _escreve(raiz: Path, relativo: str, texto: str) -> None:
    alvo = raiz / relativo
    alvo.parent.mkdir(parents=True, exist_ok=True)
    alvo.write_text(texto, encoding="utf-8")


def _repo(tmp_path: Path, pagina: str, base: str = "dev") -> Path:
    """O `dev` com o `x.py` e a página; o HEAD num ramo nascido dele."""
    (tmp_path / "casa").mkdir()
    raiz = tmp_path / "repo"
    raiz.mkdir()
    _git(raiz, "init", "-q", "-b", base)
    _escreve(raiz, "x.py", X_PY)
    _escreve(raiz, "docs/protocol/p.md", pagina)
    _git(raiz, "add", "-A")
    _git(raiz, "commit", "-q", "-m", "base")
    _git(raiz, "checkout", "-q", "-b", "ramo")
    return raiz


def _commita(raiz: Path) -> None:
    _git(raiz, "add", "-A")
    _git(raiz, "commit", "-q", "-m", "ramo")


def _roda(raiz: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--novas", "--root", str(raiz)],
        capture_output=True, text=True, check=False, env=_ambiente(raiz.parent / "casa"))


def test_a_crua_nova_reprova_e_diz_a_forma_com_o_nome(tmp_path: Path) -> None:
    raiz = _repo(tmp_path, "# P\n\nNada aqui.\n")
    _escreve(raiz, "docs/protocol/p.md", "# P\n\nNada aqui.\nO laço mora em `x.py:3`.\n")
    _commita(raiz)
    feito = _roda(raiz)
    assert feito.returncode == 1, feito.stdout + feito.stderr
    assert "docs/protocol/p.md:4" in feito.stdout
    assert "`fala` em `x.py:3`" in feito.stdout


def test_a_citacao_nova_com_o_nome_passa(tmp_path: Path) -> None:
    raiz = _repo(tmp_path, "# P\n")
    _escreve(raiz, "docs/protocol/p.md",
             "# P\nO laço mora em `fala` em `x.py:3`, e `x.py:8` (`guarda`).\n")
    _commita(raiz)
    feito = _roda(raiz)
    assert feito.returncode == 0, feito.stdout + feito.stderr


def test_a_crua_antiga_que_so_muda_de_numero_passa(tmp_path: Path) -> None:
    raiz = _repo(tmp_path, "# P\nO laço mora em `x.py:3`.\n")
    _escreve(raiz, "docs/protocol/p.md", "# P\nO laço mora em `x.py:4`.\n")
    _commita(raiz)
    feito = _roda(raiz)
    assert feito.returncode == 0, feito.stdout + feito.stderr
    assert "1 crua(s) antiga(s)" in feito.stdout


def test_a_crua_antiga_nao_paga_duas_novas(tmp_path: Path) -> None:
    raiz = _repo(tmp_path, "# P\nO laço mora em `x.py:3`.\n")
    _escreve(raiz, "docs/protocol/p.md", "# P\nO laço mora em `x.py:4`, e o resto em `x.py:8`.\n")
    _commita(raiz)
    feito = _roda(raiz)
    assert feito.returncode == 1, feito.stdout + feito.stderr
    assert "`guarda` em `x.py:8`" in feito.stdout


def test_sem_dev_o_modo_falha_dizendo_sem_base(tmp_path: Path) -> None:
    raiz = _repo(tmp_path, "# P\n", base="principal")
    feito = _roda(raiz)
    assert feito.returncode == 2, feito.stdout + feito.stderr
    assert "sem base" in feito.stderr


def test_o_que_ainda_nao_foi_commitado_conta(tmp_path: Path) -> None:
    raiz = _repo(tmp_path, "# P\n")
    _escreve(raiz, "docs/protocol/nova.md", "# Nova\nVer `x.py:3`.\n")
    feito = _roda(raiz)
    assert feito.returncode == 1, feito.stdout + feito.stderr
    assert "docs/protocol/nova.md:2" in feito.stdout


def test_a_fonte_de_fora_da_arvore_nao_conta(tmp_path: Path) -> None:
    raiz = _repo(tmp_path, "# P\n")
    _escreve(raiz, "docs/protocol/p.md", "# P\nO kernel faz isso em `hid-playstation.c:1593`.\n")
    _commita(raiz)
    assert _roda(raiz).returncode == 0


def test_a_planilha_le_celula_a_celula_e_respeita_a_coluna_de_endereco_puro(tmp_path: Path) -> None:
    raiz = _repo(tmp_path, "# P\n")
    linha = "06-x,feature,SO_NO_HTML,s,PRESENTE,,,x.py:3,Não existe.,faz,porque\n"
    _escreve(raiz, "docs/data/paridade-gtk-html.csv", CABECALHO_PARIDADE + linha)
    _commita(raiz)
    assert _roda(raiz).returncode == 0, "a coluna `html_onde` é lista de endereço por formato"
    _escreve(raiz, "docs/data/paridade-gtk-html.csv",
             CABECALHO_PARIDADE + linha.replace(",porque\n", ",mora em x.py:8\n"))
    _commita(raiz)
    feito = _roda(raiz)
    assert feito.returncode == 1, feito.stdout + feito.stderr
    assert "`guarda` em `x.py:8`" in feito.stdout
