"""O-TEXTO-ENXUTO-SE-CORRIGE-NO-ATO-01: a pergunta do texto enxuto tem um dono só, e ela morde.

O ``scripts/o-texto-enxuto.py`` reúne o que as réguas do texto reprovariam (o «dela» de pessoa, a
fala citada, a docstring longa, o comentário cortado e a citação de linha nova), corrige o
mecânico e aponta o resto. Estas provas devolvem cada defeito num repositório de mentira em
``tmp_path`` e conferem que o mesmo gancho do ``.pre-commit-config.yaml`` roda em casa e no CI,
que o gancho da escrita fala só quando há o que dizer e falha ABERTO, e que a catraca do volume
só desce.
"""

from __future__ import annotations

import importlib.util
import json
import os
import pwd
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import pytest

RAIZ = Path(__file__).resolve().parents[2]
SCRIPTS = RAIZ / "scripts"
PRE_COMMIT_YAML = RAIZ / ".pre-commit-config.yaml"
CI_YML = RAIZ / ".github" / "workflows" / "ci.yml"
PORTOES_SH = SCRIPTS / "portoes.sh"

#: O que o repositório de mentira leva da árvore real: a pergunta e as réguas que ela importa.
COPIAR = (
    "o-texto-enxuto.py",
    "neutralizar-o-texto.py",
    "check_docstring_longa.py",
    "check_comentario_cortado.py",
    "validar-citacoes-de-linha.py",
    "check_a_origem.py",
    "catraca.py",
)
PACOTE = "src/hefesto_dualsense4unix"

#: Os defeitos, montados por partes: o texto deste arquivo é versionado e as réguas o leem.
DELA = "# a ordem " + "dela" + " de 19/09 manda\n"
DELA_TROCADO = "# a ordem de 19/09 manda\n"
FALA = "# a regra *" + "«" + "isso não faz sentido mais" + "»" + "*\n"
CORTADO = "# o rádio reinicia porque o\n"
LIMPO = '"""Um módulo limpo."""\n\n\ndef f() -> int:\n    return 1\n'


def _docstring_de(linhas: int, recuo: str = "") -> str:
    miolo = [f"linha {i}" for i in range(linhas - 2)]
    return "\n".join(recuo + ln for ln in ['"""Resumo.', *miolo, '"""']) + "\n"


AMBIENTE = {
    **os.environ,
    "GIT_CONFIG_GLOBAL": "/dev/null",
    "GIT_CONFIG_NOSYSTEM": "1",
    "GIT_AUTHOR_NAME": "t",
    "GIT_AUTHOR_EMAIL": "t@example.org",
    "GIT_COMMITTER_NAME": "t",
    "GIT_COMMITTER_EMAIL": "t@example.org",
}


def git(repo: Path, *args: str) -> str:
    feito = subprocess.run(
        ["git", "-C", str(repo), *args], capture_output=True, text=True, env=AMBIENTE, check=True
    )
    return feito.stdout


def o_gancho_do_yaml() -> dict:
    """O gancho ``texto-enxuto`` como está no ``.pre-commit-config.yaml`` da árvore real."""
    yaml = pytest.importorskip("yaml")
    config = yaml.safe_load(PRE_COMMIT_YAML.read_text(encoding="utf-8"))
    ganchos = [h for repo in config["repos"] for h in repo["hooks"] if h["id"] == "texto-enxuto"]
    assert len(ganchos) == 1, "o gancho entra UMA vez no .pre-commit-config.yaml"
    return ganchos[0]


def repo_de_mentira(tmp_path: Path, com_gancho: bool = True) -> Path:
    """Um repositório limpo, com o ``dev`` no commit-base e os scripts reais copiados."""
    repo = tmp_path / "hefesto-mentira"
    (repo / "scripts").mkdir(parents=True)
    (repo / PACOTE).mkdir(parents=True)
    (repo / "docs" / "protocol").mkdir(parents=True)
    (repo / "docs" / "data").mkdir(parents=True)
    for nome in COPIAR:
        shutil.copy2(SCRIPTS / nome, repo / "scripts" / nome)
    (repo / PACOTE / "__init__.py").write_text("", encoding="utf-8")
    (repo / PACOTE / "mod.py").write_text(LIMPO, encoding="utf-8")
    (repo / "docs/protocol/p.md").write_text("# p\n\nsem citação\n", encoding="utf-8")
    (repo / "docs/data/decisoes-de-produto.csv").write_text(
        "D-TESTE-1,uma decisão\n", encoding="utf-8"
    )
    if com_gancho:
        yaml = pytest.importorskip("yaml")
        config = {"repos": [{"repo": "local", "hooks": [o_gancho_do_yaml()]}]}
        (repo / ".pre-commit-config.yaml").write_text(
            yaml.safe_dump(config, allow_unicode=True), encoding="utf-8"
        )
    git(repo, "init", "-q", "-b", "dev")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "base")
    return repo


def _a_regua(nome: str) -> Any:
    """O módulo da régua real, do ``scripts/`` da árvore: a resposta que o script tem de repetir."""
    modulo = "regua_" + re.sub(r"\W", "_", nome)
    if modulo not in sys.modules:
        spec = importlib.util.spec_from_file_location(modulo, SCRIPTS / nome)
        assert spec is not None and spec.loader is not None
        sys.modules[modulo] = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(sys.modules[modulo])
    return sys.modules[modulo]


def o_script(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(repo / "scripts" / "o-texto-enxuto.py"), "--raiz", str(repo), *args],
        cwd=repo,
        capture_output=True,
        text=True,
        env=AMBIENTE,
        check=False,
    )


# --------------------------------------------------------------------------- as cinco mordidas


class TestAsReguasMordem:
    def test_o_script_aponta_as_cinco_e_so_o_dela_se_corrige(self, tmp_path: Path) -> None:
        repo = repo_de_mentira(tmp_path)
        (repo / PACOTE / "x.py").write_text(
            DELA
            + FALA
            + CORTADO
            + "VALOR = 1\n\n\ndef g() -> int:\n"
            + _docstring_de(11, "    ")
            + "    return 2\n",
            encoding="utf-8",
        )
        (repo / "docs/protocol/p.md").write_text("# p\n\nveja `mod.py:3`\n", encoding="utf-8")
        apontou = o_script(repo, PACOTE + "/x.py", "docs/protocol/p.md")
        assert apontou.returncode == 1, apontou.stdout + apontou.stderr
        for regua in ("[dela]", "[fala]", "[docstring]", "[cortado]", "[citação]"):
            assert regua in apontou.stdout, regua + "\n" + apontou.stdout
        assert (repo / PACOTE / "x.py").read_text(encoding="utf-8").startswith(DELA), (
            "apontar não escreve"
        )

        corrigiu = o_script(repo, "--aplicar", PACOTE + "/x.py", "docs/protocol/p.md")
        depois = (repo / PACOTE / "x.py").read_text(encoding="utf-8")
        assert depois.startswith(DELA_TROCADO + FALA), "só o «dela» é mecânico"
        assert corrigiu.returncode == 1, "o resto continua reprovando"
        assert "[dela]" in corrigiu.stdout and "corrigido" in corrigiu.stdout
        for regua in ("[fala]", "[docstring]", "[cortado]", "[citação]"):
            assert regua in corrigiu.stdout
        assert "[dela]" not in o_script(repo, PACOTE + "/x.py").stdout

    def test_arquivo_limpo_fica_calado(self, tmp_path: Path) -> None:
        repo = repo_de_mentira(tmp_path)
        for modo in ((), ("--aplicar",)):
            limpo = o_script(repo, *modo, PACOTE + "/mod.py")
            assert (limpo.returncode, limpo.stdout, limpo.stderr) == (0, "", "")

    def test_docstring_antiga_nao_reprova_so_a_nova(self, tmp_path: Path) -> None:
        repo = repo_de_mentira(tmp_path)
        velha = PACOTE + "/velha.py"
        (repo / velha).write_text(_docstring_de(11) + "X = 1\n", encoding="utf-8")
        git(repo, "add", "-A")
        git(repo, "commit", "-q", "-m", "a docstring velha")
        assert o_script(repo, velha).stdout == "", (
            "a que já estava em HEAD é da catraca, não do arquivo"
        )
        (repo / velha).write_text(_docstring_de(12) + "X = 1\n", encoding="utf-8")
        assert "[docstring]" in o_script(repo, velha).stdout, "crescer reprova"

    def test_o_dela_de_pessoa_em_documento_de_prosa_tambem_se_troca(self, tmp_path: Path) -> None:
        repo = repo_de_mentira(tmp_path)
        (repo / "docs/protocol/q.md").write_text(
            "A ordem " + "dela" + " de 19/09 manda.\n", encoding="utf-8"
        )
        corrigiu = o_script(repo, "--aplicar", "docs/protocol/q.md")
        assert corrigiu.returncode == 0
        assert (repo / "docs/protocol/q.md").read_text(
            encoding="utf-8"
        ) == "A ordem de 19/09 manda.\n"

    def test_a_regua_e_importada_e_nao_copiada(self, tmp_path: Path) -> None:
        """Uma régua de mentira no lugar da real manda no resultado: o script usa a do dono."""
        repo = repo_de_mentira(tmp_path)
        (repo / "scripts" / "neutralizar-o-texto.py").write_text(
            "def tipo_do_alvo(rel):\n    return 'py'\n\n\n"
            "def reescrever_arquivo(texto, tipo):\n    return texto.replace('AAA', 'BBB')\n",
            encoding="utf-8",
        )
        (repo / PACOTE / "y.py").write_text("X = 1  # AAA\n", encoding="utf-8")
        o_script(repo, "--aplicar", PACOTE + "/y.py")
        assert (repo / PACOTE / "y.py").read_text(encoding="utf-8") == "X = 1  # BBB\n"
        (repo / "scripts" / "check_docstring_longa.py").write_text(
            "LIMITE = 2\n\n\ndef docstrings_longas(fonte, limite=2):\n"
            "    return [('f', 99)] if 'GRANDE' in fonte else []\n",
            encoding="utf-8",
        )
        (repo / PACOTE / "z.py").write_text("X = 'GRANDE'\n", encoding="utf-8")
        assert "`f` tem 99 linhas (limite 2)" in o_script(repo, PACOTE + "/z.py").stdout

    def test_o_dela_num_texto_que_o_codigo_usa_so_se_aponta(self, tmp_path: Path) -> None:
        """A troca que muda a AST (o CSS dentro de uma string de página) não é mecânica."""
        repo = repo_de_mentira(tmp_path)
        fonte = 'CSS = "  /* o nome que ' + "ela" + ' deu */"\n'
        (repo / PACOTE / "pagina.py").write_text(fonte, encoding="utf-8")
        corrida = o_script(repo, "--aplicar", PACOTE + "/pagina.py")
        assert corrida.returncode == 1 and "[dela]" in corrida.stdout, corrida.stdout
        assert "a AST mudaria" in corrida.stdout
        assert (repo / PACOTE / "pagina.py").read_text(encoding="utf-8") == fonte, "não escreve"

    @pytest.mark.parametrize(
        ("regua", "fonte"),
        [
            ("dela", DELA + "X = 1\n"),
            ("dela", "# a cor " + "dela" + " vem do aparelho\nX = 1\n"),
            ("fala", FALA + "X = 1\n"),
            ("fala", "# a regra é curta\nX = 1\n"),
            ("cortado", CORTADO + "X = 1\n"),
            ("cortado", "# o rádio reinicia porque o laço para.\nX = 1\n"),
            ("docstring", "def g() -> int:\n" + _docstring_de(11, "    ") + "    return 2\n"),
            ("docstring", "def g() -> int:\n" + _docstring_de(10, "    ") + "    return 2\n"),
        ],
    )
    def test_a_mesma_entrada_da_a_resposta_da_regua(
        self, tmp_path: Path, regua: str, fonte: str
    ) -> None:
        """Dos dois lados: a régua do dono reprova, o script aponta; ela passa, ele cala."""
        repo = repo_de_mentira(tmp_path)
        (repo / PACOTE / "n.py").write_text(fonte, encoding="utf-8")
        nz = _a_regua("neutralizar-o-texto.py")
        dl = _a_regua("check_docstring_longa.py")
        cc = _a_regua("check_comentario_cortado.py")
        falas = _a_regua("o-texto-enxuto.py").falas_em_comentario
        reprova = {
            "dela": nz.reescrever_arquivo(fonte, "py") != fonte,
            "fala": bool(falas({PACOTE + "/n.py": fonte})),
            "cortado": any(pergunta(fonte) for pergunta in cc.PERGUNTAS.values()),
            "docstring": bool(dl.docstrings_longas(fonte)),
        }[regua]
        assert (f"[{regua}]" in o_script(repo, PACOTE + "/n.py").stdout) == reprova

    @pytest.mark.parametrize(
        "ausente",
        [
            "neutralizar-o-texto.py",
            "check_docstring_longa.py",
            "check_comentario_cortado.py",
            "validar-citacoes-de-linha.py",
        ],
    )
    def test_arrancada_a_regua_o_script_reprova_com_rc_2(
        self, tmp_path: Path, ausente: str
    ) -> None:
        repo = repo_de_mentira(tmp_path)
        (repo / "scripts" / ausente).unlink()
        (repo / PACOTE / "x.py").write_text("X = 1\n", encoding="utf-8")
        (repo / "docs/protocol/p.md").write_text(
            "# p\n\nsem citação, mas mudado\n", encoding="utf-8"
        )
        corrida = o_script(repo, PACOTE + "/x.py", "docs/protocol/p.md")
        assert corrida.returncode == 2, corrida.stdout + corrida.stderr
        assert ausente in corrida.stderr


# ------------------------------------------------------------ o mesmo gancho, em casa e no CI


def _rodar_o_gancho(repo: Path, arquivos: list[str]) -> subprocess.CompletedProcess[str]:
    """O contrato do ``pre-commit``, sem ele: o ``entry`` do YAML com os arquivos de ``files``.

    O gancho reprova se sair com rc != 0 ou se mudar a árvore (o que ele faz no CI)."""
    gancho = o_gancho_do_yaml()
    casam = [a for a in arquivos if re.search(gancho.get("files", ""), a)]
    antes = git(repo, "diff", "--binary")
    feito = subprocess.run(
        [*gancho["entry"].split(), *casam],
        cwd=repo,
        capture_output=True,
        text=True,
        env=AMBIENTE,
        check=False,
    )
    mudou = git(repo, "diff", "--binary") != antes
    return subprocess.CompletedProcess(
        feito.args, 1 if (feito.returncode or mudou) else 0, feito.stdout, feito.stderr
    )


def _o_pre_commit_real() -> list[str] | None:
    caminho = os.environ.get("HEFESTO_PRE_COMMIT") or shutil.which("pre-commit")
    return [caminho] if caminho else None


def _rodar_o_pre_commit_real(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    comando = _o_pre_commit_real()
    assert comando
    return subprocess.run(
        [*comando, "run", *args],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
        env={**AMBIENTE, "PRE_COMMIT_HOME": str(repo.parent / "pc-home")},
    )


class TestOMesmoGanchoEmCasaENoCI:
    def test_o_gancho_entra_uma_vez_e_o_ci_roda_a_mesma_definicao(self) -> None:
        gancho = o_gancho_do_yaml()
        assert "o-texto-enxuto.py" in gancho["entry"] and "--aplicar" in gancho["entry"]
        assert gancho["language"] == "system"
        assert gancho.get("require_serial") is True, "em paralelo, os `git add` disputam o índice"
        ci = CI_YML.read_text(encoding="utf-8")
        assert "pre-commit run --all-files" in ci, "o job pre-commit roda o YAML inteiro"

    def test_em_casa_o_dela_passa_ja_corrigido_e_re_staged(self, tmp_path: Path) -> None:
        repo = repo_de_mentira(tmp_path)
        (repo / PACOTE / "x.py").write_text(DELA + "X = 1\n", encoding="utf-8")
        git(repo, "add", PACOTE + "/x.py")
        feito = _rodar_o_gancho(repo, [PACOTE + "/x.py"])
        assert feito.returncode == 0, feito.stdout + feito.stderr
        assert "corrigi 1 arquivo" in feito.stdout
        assert (repo / PACOTE / "x.py").read_text(encoding="utf-8") == DELA_TROCADO + "X = 1\n"
        assert git(repo, "diff") == "", "o que ele corrigiu voltou ao índice"
        assert "ordem de 19/09" in git(repo, "diff", "--cached")

    def test_em_casa_a_fala_citada_reprova_o_commit(self, tmp_path: Path) -> None:
        repo = repo_de_mentira(tmp_path)
        (repo / PACOTE / "x.py").write_text(FALA + "X = 1\n", encoding="utf-8")
        git(repo, "add", PACOTE + "/x.py")
        feito = _rodar_o_gancho(repo, [PACOTE + "/x.py"])
        assert feito.returncode == 1 and "[fala]" in feito.stdout

    def test_no_ci_o_que_em_casa_se_corrige_reprova(self, tmp_path: Path) -> None:
        """``pre-commit run --all-files`` commitada: o gancho modificaria, então reprova."""
        repo = repo_de_mentira(tmp_path)
        (repo / PACOTE / "x.py").write_text(DELA + "X = 1\n", encoding="utf-8")
        git(repo, "add", PACOTE + "/x.py")
        git(repo, "commit", "-q", "-m", "com o dela de pessoa")
        feito = _rodar_o_gancho(repo, git(repo, "ls-files").split())
        assert feito.returncode == 1, feito.stdout + feito.stderr

    @pytest.mark.skipif(
        _o_pre_commit_real() is None,
        reason="sem o `pre-commit` instalado (defina HEFESTO_PRE_COMMIT)",
    )
    def test_o_pre_commit_de_verdade_faz_o_mesmo(self, tmp_path: Path) -> None:
        repo = repo_de_mentira(tmp_path)
        (repo / PACOTE / "x.py").write_text(DELA + "X = 1\n", encoding="utf-8")
        git(repo, "add", PACOTE + "/x.py")
        em_casa = _rodar_o_pre_commit_real(repo)
        assert em_casa.returncode == 0, em_casa.stdout + em_casa.stderr
        assert (repo / PACOTE / "x.py").read_text(encoding="utf-8") == DELA_TROCADO + "X = 1\n"
        git(repo, "commit", "-q", "-m", "corrigido")
        (repo / PACOTE / "w.py").write_text(DELA + "X = 1\n", encoding="utf-8")
        git(repo, "add", PACOTE + "/w.py")
        git(repo, "commit", "-q", "-m", "com o dela de pessoa")
        no_ci = _rodar_o_pre_commit_real(repo, "--all-files")
        assert no_ci.returncode == 1, no_ci.stdout + no_ci.stderr
        (repo / PACOTE / "w.py").write_text(FALA + "X = 1\n", encoding="utf-8")
        git(repo, "add", PACOTE + "/w.py")
        fala = _rodar_o_pre_commit_real(repo)
        assert fala.returncode == 1 and "[fala]" in fala.stdout
        git(repo, "reset", "-q", "--hard")
        for i in range(40):
            (repo / PACOTE / f"m{i}.py").write_text(DELA + f"X = {i}\n", encoding="utf-8")
        git(repo, "add", PACOTE)
        muitos = _rodar_o_pre_commit_real(repo)
        assert muitos.returncode == 0, muitos.stdout + muitos.stderr
        assert git(repo, "diff") == "", "todo arquivo corrigido voltou ao índice"


class TestOGanchoDoGitRodaOYaml:
    """O ``scripts/hooks/pre-commit`` da árvore roda o mesmo ``.pre-commit-config.yaml`` do CI."""

    def _com_o_gancho_do_git(self, tmp_path: Path) -> Path:
        repo = repo_de_mentira(tmp_path)
        gancho = repo / ".git" / "hooks" / "pre-commit"
        shutil.copy2(SCRIPTS / "hooks" / "pre-commit", gancho)
        gancho.chmod(0o755)
        return repo

    def _commit(self, repo: Path, **ambiente: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["git", "-C", str(repo), "commit", "-q", "-m", "um commit"],
            capture_output=True,
            text=True,
            env={**AMBIENTE, "PRE_COMMIT_HOME": str(repo.parent / "pc-home"), **ambiente},
            check=False,
        )

    def test_o_gancho_chama_o_framework_na_fase_do_commit(self, tmp_path: Path) -> None:
        repo = self._com_o_gancho_do_git(tmp_path)
        chamadas = tmp_path / "chamadas.txt"
        falso = tmp_path / "pre-commit-falso"
        falso.write_text(
            f'#!/bin/sh\necho "$@" >> {chamadas}\nexit "${{RC_FALSO:-0}}"\n', encoding="utf-8"
        )
        falso.chmod(0o755)
        (repo / PACOTE / "x.py").write_text("X = 1\n", encoding="utf-8")
        git(repo, "add", PACOTE + "/x.py")
        reprovou = self._commit(repo, HEFESTO_PRE_COMMIT=str(falso), RC_FALSO="1")
        assert reprovou.returncode != 0, "o framework reprovou, o commit não sai"
        assert chamadas.read_text(encoding="utf-8").split() == ["run", "--hook-stage", "pre-commit"]
        assert self._commit(repo, HEFESTO_PRE_COMMIT=str(falso)).returncode == 0

    @pytest.mark.skipif(shutil.which("pre-commit") is not None, reason="o framework está no PATH")
    def test_sem_o_framework_avisa_e_deixa_passar(self, tmp_path: Path) -> None:
        repo = self._com_o_gancho_do_git(tmp_path)
        (repo / PACOTE / "x.py").write_text("X = 1\n", encoding="utf-8")
        git(repo, "add", PACOTE + "/x.py")
        feito = self._commit(repo, HEFESTO_PRE_COMMIT="")
        assert feito.returncode == 0 and "só roda no CI" in feito.stderr

    @pytest.mark.skipif(
        _o_pre_commit_real() is None,
        reason="sem o `pre-commit` instalado (defina HEFESTO_PRE_COMMIT)",
    )
    def test_o_commit_de_verdade_corrige_o_dela_e_barra_a_fala(self, tmp_path: Path) -> None:
        repo = self._com_o_gancho_do_git(tmp_path)
        [comando] = _o_pre_commit_real() or [""]
        (repo / PACOTE / "x.py").write_text(DELA + "X = 1\n", encoding="utf-8")
        git(repo, "add", PACOTE + "/x.py")
        passou = self._commit(repo, HEFESTO_PRE_COMMIT=comando)
        assert passou.returncode == 0, passou.stdout + passou.stderr
        assert git(repo, "show", f"HEAD:{PACOTE}/x.py") == DELA_TROCADO + "X = 1\n"
        (repo / PACOTE / "x.py").write_text(FALA + "X = 1\n", encoding="utf-8")
        git(repo, "add", PACOTE + "/x.py")
        barrou = self._commit(repo, HEFESTO_PRE_COMMIT=comando)
        assert barrou.returncode != 0 and "[fala]" in barrou.stdout + barrou.stderr


# --------------------------------------------------------------------------- o portão e o CI


class TestOPortao:
    def test_a_pergunta_entra_na_tabela_e_no_so_do_ci(self) -> None:
        tabela = PORTOES_SH.read_text(encoding="utf-8")
        ci = CI_YML.read_text(encoding="utf-8")
        for id_ in ("texto-enxuto", "texto-enxuto-catraca", "texto-enxuto-morde"):
            assert re.search(rf"^rapido\|{id_}\|", tabela, re.M), id_
            assert re.search(rf"--so [^\n]*(?<![\w-]){id_}(?![\w-])", ci), id_
        assert re.search(
            r"^rapido\|texto-enxuto\|py\|scripts/o-texto-enxuto\.py --conferir --mudados",
            tabela,
            re.M,
        )

    def test_o_portao_acusa_o_arquivo_mudado_do_ramo(self, tmp_path: Path) -> None:
        repo = repo_de_mentira(tmp_path)
        git(repo, "checkout", "-q", "-b", "leva")
        (repo / PACOTE / "x.py").write_text(FALA + "X = 1\n", encoding="utf-8")
        git(repo, "add", PACOTE + "/x.py")
        git(repo, "commit", "-q", "-m", "a fala volta")
        corrida = o_script(repo, "--conferir", "--mudados")
        assert corrida.returncode == 1 and "[fala]" in corrida.stdout
        (repo / PACOTE / "x.py").write_text("X = 1\n", encoding="utf-8")
        assert o_script(repo, "--conferir", "--mudados").returncode == 0


# --------------------------------------------------------------------------- a catraca do volume


def _comentarios(quantos: int) -> str:
    return "".join(f"# linha {i}\n" for i in range(quantos))


def _volume(repo: Path) -> int:
    return json.loads(o_script(repo, "--catraca", "--json").stdout)["texto-em-src"]["hoje"]


class TestACatracaDoVolume:
    def _com_piso(self, tmp_path: Path) -> Path:
        repo = repo_de_mentira(tmp_path, com_gancho=False)
        (repo / PACOTE / "c.py").write_text(_comentarios(45) + "X = 1\n", encoding="utf-8")
        git(repo, "add", "-A")
        git(repo, "commit", "-q", "-m", "o texto de hoje")
        assert o_script(repo, "--catraca", "--aceitar", "texto-em-src").returncode == 0
        git(repo, "add", "-A")
        git(repo, "commit", "-q", "-m", "o piso")
        git(repo, "checkout", "-q", "-b", "leva")
        return repo

    def test_o_volume_conta_comentario_e_docstring(self, tmp_path: Path) -> None:
        repo = repo_de_mentira(tmp_path, com_gancho=False)
        (repo / PACOTE / "c.py").write_text("# um\n# dois\nX = 1\n", encoding="utf-8")
        assert _volume(repo) == 1 + 2, (
            "a docstring de uma linha do mod.py e os dois comentários do c.py"
        )

    def test_subir_reprova_e_nomeia_o_arquivo(self, tmp_path: Path) -> None:
        repo = self._com_piso(tmp_path)
        assert o_script(repo, "--catraca").returncode == 0
        (repo / PACOTE / "c.py").write_text(_comentarios(46) + "X = 1\n", encoding="utf-8")
        git(repo, "add", "-A")
        git(repo, "commit", "-q", "-m", "mais um comentário")
        corrida = o_script(repo, "--catraca")
        assert corrida.returncode == 1, corrida.stdout
        assert "c.py" in corrida.stdout and "Origem" in corrida.stdout

    def test_com_origem_passa_e_o_fecho_registra_a_subida(self, tmp_path: Path) -> None:
        repo = self._com_piso(tmp_path)
        (repo / PACOTE / "c.py").write_text(_comentarios(46) + "X = 1\n", encoding="utf-8")
        git(repo, "add", "-A")
        git(repo, "commit", "-q", "-m", "mais um comentário\n\nOrigem: D-TESTE-1")
        paga = o_script(repo, "--catraca")
        assert paga.returncode == 0 and "D-TESTE-1" in paga.stdout
        registrou = o_script(repo, "--registrar-subida")
        assert registrou.returncode == 0 and "registrada" in registrou.stdout
        caderno = json.loads((repo / "docs/data/o-texto-enxuto.json").read_text(encoding="utf-8"))
        assert "D-TESTE-1" in json.dumps(caderno)

    def test_origem_que_nao_existe_nao_paga(self, tmp_path: Path) -> None:
        repo = self._com_piso(tmp_path)
        (repo / PACOTE / "c.py").write_text(_comentarios(46) + "X = 1\n", encoding="utf-8")
        git(repo, "add", "-A")
        git(repo, "commit", "-q", "-m", "mais um comentário\n\nOrigem: D-NAO-EXISTE")
        assert o_script(repo, "--catraca").returncode == 1

    def test_descer_passa_e_pede_o_piso_novo(self, tmp_path: Path) -> None:
        repo = self._com_piso(tmp_path)
        (repo / PACOTE / "c.py").write_text("X = 1\n", encoding="utf-8")
        corrida = o_script(repo, "--catraca")
        assert corrida.returncode == 0 and "--aceitar" in corrida.stdout

    def test_o_piso_da_arvore_real_esta_gravado(self) -> None:
        caderno = (RAIZ / "docs/data/o-texto-enxuto.json").read_text(encoding="utf-8")
        assert "texto-em-src" in caderno


# --------------------------------------------------------------------------- o gancho da escrita


def _casa_real() -> Path:
    return Path(pwd.getpwuid(os.getuid()).pw_dir)


#: A pasta dos ganchos da sessão, fora do git; o nome dela é montado por partes.
PASTA_DOS_GANCHOS = Path(
    os.environ.get("HEFESTO_GANCHOS_DIR") or _casa_real() / ("." + "cla" + "ude") / "hooks"
)
GANCHO_DA_ESCRITA = PASTA_DOS_GANCHOS / "texto-enxuto.py"
FRAGMENTO = PASTA_DOS_GANCHOS / "travas/manifesto.d/o-texto-enxuto.json"
sem_o_gancho = pytest.mark.skipif(
    not GANCHO_DA_ESCRITA.is_file(), reason="o gancho vive fora do git"
)


def _gesto(repo: Path, arquivo: str, ferramenta: str = "Write") -> str:
    return json.dumps(
        {
            "hook_event_name": "PostToolUse",
            "tool_name": ferramenta,
            "session_id": "sessao-de-mentira",
            "cwd": str(repo),
            "tool_input": {"file_path": str(repo / arquivo)},
        }
    )


def _gancho(
    repo: Path, entrada: str, tmp_path: Path, **ambiente: str
) -> tuple[subprocess.CompletedProcess[str], float]:
    lar = tmp_path / "lar"
    lar.mkdir(exist_ok=True)
    # o repositório de mentira é `<tmp_path>/hefesto-mentira`: a raiz de mentira o põe no corte
    env = {
        **os.environ,
        "HOME": str(lar),
        "HEFESTO_TRAVAS_RAIZES": str(tmp_path / "hefesto-"),
        **ambiente,
    }
    inicio = time.monotonic()
    feito = subprocess.run(
        [sys.executable, str(GANCHO_DA_ESCRITA)],
        input=entrada,
        capture_output=True,
        text=True,
        env=env,
        cwd=repo,
        check=False,
    )
    return feito, time.monotonic() - inicio


def _diario(tmp_path: Path) -> str:
    achados = sorted((tmp_path / "lar").rglob("*.jsonl"))
    return "".join(a.read_text(encoding="utf-8") for a in achados)


@sem_o_gancho
class TestOGanchoDaEscrita:
    def test_arquivo_limpo_fica_calado_e_rapido(self, tmp_path: Path) -> None:
        repo = repo_de_mentira(tmp_path, com_gancho=False)
        medio = repo / PACOTE / "medio.py"
        medio.write_text(
            "\n".join(f"def f{i}(x: int) -> int:\n    return x + {i}\n" for i in range(300)),
            encoding="utf-8",
        )
        saida, segundos = _gancho(repo, _gesto(repo, PACOTE + "/medio.py"), tmp_path)
        assert (saida.returncode, saida.stdout) == (0, "")
        assert segundos < 2, f"o gancho levou {segundos:.2f} s num arquivo de 600 linhas"

    def test_arquivo_com_defeito_devolve_o_que_corrigiu_e_o_que_falta(self, tmp_path: Path) -> None:
        repo = repo_de_mentira(tmp_path, com_gancho=False)
        (repo / PACOTE / "x.py").write_text(DELA + FALA + "X = 1\n", encoding="utf-8")
        saida, _ = _gancho(repo, _gesto(repo, PACOTE + "/x.py", "Edit"), tmp_path)
        assert saida.returncode == 0
        contexto = json.loads(saida.stdout)["hookSpecificOutput"]["additionalContext"]
        assert "[fala]" in contexto and "corrigiu" in contexto and "Releia" in contexto
        assert (repo / PACOTE / "x.py").read_text(encoding="utf-8").startswith(DELA_TROCADO)

    def test_so_o_mecanico_tambem_avisa_para_reler(self, tmp_path: Path) -> None:
        """O script sai 0 depois de corrigir: calado, o próximo Edit cairia num arquivo velho."""
        repo = repo_de_mentira(tmp_path, com_gancho=False)
        (repo / PACOTE / "x.py").write_text(DELA + "X = 1\n", encoding="utf-8")
        saida, _ = _gancho(repo, _gesto(repo, PACOTE + "/x.py", "Edit"), tmp_path)
        assert saida.returncode == 0
        contexto = json.loads(saida.stdout)["hookSpecificOutput"]["additionalContext"]
        assert "Releia" in contexto and "Falta" not in contexto
        assert len(contexto) < 300, "a mensagem é lida por modelo: curta"

    def test_sem_o_script_o_gesto_segue_e_o_diario_ganha_uma_linha(self, tmp_path: Path) -> None:
        repo = repo_de_mentira(tmp_path, com_gancho=False)
        (repo / "scripts" / "o-texto-enxuto.py").unlink()
        (repo / PACOTE / "x.py").write_text(FALA + "X = 1\n", encoding="utf-8")
        saida, _ = _gancho(repo, _gesto(repo, PACOTE + "/x.py"), tmp_path)
        assert (saida.returncode, saida.stdout) == (0, "")
        assert "texto-enxuto" in _diario(tmp_path)

    def test_quebrado_ou_lento_o_gesto_segue(self, tmp_path: Path) -> None:
        repo = repo_de_mentira(tmp_path, com_gancho=False)
        (repo / PACOTE / "x.py").write_text("X = 1\n", encoding="utf-8")
        (repo / "scripts" / "o-texto-enxuto.py").write_text(
            "raise SystemExit(7)\n", encoding="utf-8"
        )
        saida, _ = _gancho(repo, _gesto(repo, PACOTE + "/x.py"), tmp_path)
        assert (saida.returncode, saida.stdout) == (0, "")
        (repo / "scripts" / "o-texto-enxuto.py").write_text(
            "import time\ntime.sleep(30)\n", encoding="utf-8"
        )
        saida, segundos = _gancho(
            repo, _gesto(repo, PACOTE + "/x.py"), tmp_path, HEFESTO_TEXTO_ENXUTO_PRAZO="0.5"
        )
        assert (saida.returncode, saida.stdout) == (0, "")
        assert segundos < 5

    @pytest.mark.parametrize(
        "entrada", ["", "não é json", "[]", '{"tool_name": "Write", "tool_input": null}']
    )
    def test_entrada_torta_nao_derruba(self, tmp_path: Path, entrada: str) -> None:
        repo = repo_de_mentira(tmp_path, com_gancho=False)
        saida, _ = _gancho(repo, entrada, tmp_path)
        assert (saida.returncode, saida.stdout) == (0, "")

    def test_fora_do_python_ou_do_hefesto_nao_age(self, tmp_path: Path) -> None:
        repo = repo_de_mentira(tmp_path, com_gancho=False)
        (repo / "docs" / "n.md").write_text(FALA, encoding="utf-8")
        assert _gancho(repo, _gesto(repo, "docs/n.md"), tmp_path)[0].stdout == ""
        (repo / PACOTE / "x.py").write_text(FALA + "X = 1\n", encoding="utf-8")
        fora = _gancho(
            repo,
            _gesto(repo, PACOTE + "/x.py"),
            tmp_path,
            HEFESTO_TRAVAS_RAIZES="/nao/existe/hefesto-",
        )[0]
        assert fora.stdout == "", "outro projeto: a régua é do Hefesto"

    @pytest.mark.skipif(not FRAGMENTO.is_file(), reason="o fragmento vive fora do git")
    def test_o_fragmento_do_manifesto_e_valido_e_registra_o_post_tool_use(self) -> None:
        fragmento = json.loads(FRAGMENTO.read_text(encoding="utf-8"))
        assert fragmento["sprint"] == "O-TEXTO-ENXUTO-SE-CORRIGE-NO-ATO-01"
        [gancho] = fragmento["ganchos"]
        assert gancho["evento"] == "PostToolUse" and gancho["arquivo"] == "texto-enxuto.py"
        assert gancho["matcher"] == "Write|Edit|MultiEdit" and gancho["nivel"] == "hefesto"
        assert gancho["prazo"] >= 5
