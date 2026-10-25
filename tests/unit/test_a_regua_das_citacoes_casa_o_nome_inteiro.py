"""A citação nomeada casa o nome INTEIRO e fora de comentário (o `casa_o_nome` do validador).

`A-REGUA-DAS-CITACOES-CASA-O-NOME-INTEIRO-FORA-DO-COMENTARIO-01`: com o ``nome in trecho``, ``cor``
casava em ``cores``, ``acao_mic`` casava num comentário que só cita o nome, e uma linha inserida
acima deixava a citação verde no lugar errado.
"""

from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest

RAIZ = Path(__file__).resolve().parents[2]
VALIDADOR = RAIZ / "scripts" / "validar-citacoes-de-linha.py"
REAPONTAR = RAIZ / "scripts" / "reapontar-citacoes.py"


def _carregar(caminho: Path, nome: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(nome, caminho)
    assert spec is not None and spec.loader is not None
    modulo = importlib.util.module_from_spec(spec)
    sys.modules[nome] = modulo
    spec.loader.exec_module(modulo)
    return modulo


@pytest.fixture(scope="module")
def val() -> ModuleType:
    return _carregar(VALIDADOR, "validar_citacoes_de_linha")


def _casa(val: ModuleType, nome: str, texto: str, sufixo: str, linha: int = 0) -> bool:
    corpo = texto.split("\n")
    primeira, ultima = (linha, linha) if linha else (1, len(corpo))
    return bool(val.casa_o_nome(nome, corpo, primeira, ultima, sufixo))


def test_cor_nao_casa_em_cores(val: ModuleType) -> None:
    assert not _casa(val, "cor", "cores = ler_cores()\n", ".py")
    assert _casa(val, "cor", "self.cor = cores[0]\n", ".py"), "acesso por atributo é uso"


def test_o_nome_num_comentario_nao_casa(val: ModuleType) -> None:
    assert not _casa(val, "acao_mic", "x = 1  # quem liga é o acao_mic\n", ".py")
    assert not _casa(val, "acao_mic", "<!-- o acao_mic mora aqui -->\n<p>oi</p>\n", ".html")
    assert not _casa(val, "acao_mic", "// acao_mic\nconst y = 1;\n", ".js")
    assert not _casa(val, "acao_mic", "/* o\nacao_mic */ const y = 1;\n", ".js")
    assert not _casa(
        val, "acao_mic", "<script>\n// acao_mic\nlet z = 0;\n</script>\n", ".html")


def test_o_nome_na_docstring_e_na_cadeia_casa(val: ModuleType) -> None:
    fonte = 'def f():\n    """Chama o acao_mic."""\n    return "acao_mic"\n'
    assert _casa(val, "acao_mic", fonte, ".py", 2), "a docstring é prosa da tela: conta"
    assert _casa(val, "acao_mic", fonte, ".py", 3), "a cadeia é valor: conta"
    assert _casa(val, "acao_mic", "const s = '// acao_mic';\n", ".js"), "// na cadeia é valor"
    assert _casa(val, "cor", 'COR = "#A51C48"  # cor\nx = cor\n', ".py", 2)


def test_o_id_do_html_casa_inteiro(val: ModuleType) -> None:
    linha = '<span data-campo="est-mic" class="vol">80</span>\n'
    assert _casa(val, "est-mic", linha, ".html")
    assert not _casa(val, "est", linha, ".html"), "o - é parte do id no HTML"
    assert _casa(val, "vol", linha, ".html")
    assert val.NOME_DEPOIS.match(" (`est-mic`)"), "a gramática do nome prometido aceita o id"
    assert not val.NOME_DEPOIS.match(" (`est-`)"), "o id não termina em -"


def test_a_quebra_de_linha_do_comentario_fica_no_lugar(val: ModuleType) -> None:
    html = "<p>a</p>\n<!-- um\ndois -->\n<b data-campo=\"alvo\">x</b>\n"
    assert _casa(val, "alvo", html, ".html", 4), "o comentário de duas linhas não desloca nada"


# --- o validador e o reapontar, num repositório de mentira -----------------------------------

ANTES = (
    '"""O alvo."""\n# o acao_mic mora logo abaixo\ndef acao_mic():\n    return 1\n'
    "todas_as_cores = (1, 2)\ncor = 1\n"
)
DEPOIS = ANTES.replace('"""O alvo."""\n', '"""O alvo."""\nEXTRA = 0\n')
CSV = (
    "id,prosa\n"
    'um,"o gesto em src/hefesto_dualsense4unix/alvo.py:3 (`acao_mic`)"\n'
    'dois,"a cor em src/hefesto_dualsense4unix/alvo.py:6 (`cor`)"\n'
)


def _git(raiz: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-C", str(raiz), "-c", "core.hooksPath=/dev/null", "-c", "commit.gpgsign=false",
         "-c", "user.name=régua", "-c", "user.email=regua@exemplo.invalid", *args],
        capture_output=True, text=True, check=True,
        env={**os.environ, "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_NOSYSTEM": "1"},
    )


@pytest.fixture()
def repo(tmp_path: Path) -> Path:
    raiz = tmp_path / "repo"
    pacote = raiz / "src" / "hefesto_dualsense4unix"
    pacote.mkdir(parents=True)
    (pacote / "alvo.py").write_text(ANTES, encoding="utf-8")
    (raiz / "docs" / "data").mkdir(parents=True)
    (raiz / "docs" / "data" / "mapa.csv").write_text(CSV, encoding="utf-8")
    _git(raiz, "init", "-q")
    _git(raiz, "add", ".")
    _git(raiz, "commit", "-q", "-m", "o alvo nasce")
    (pacote / "alvo.py").write_text(DEPOIS, encoding="utf-8")
    _git(raiz, "commit", "-q", "-am", "uma linha entra acima")
    return raiz


def _validar(raiz: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(VALIDADOR), "--all", "--root", str(raiz)],
        capture_output=True, text=True, check=False)


def test_a_linha_inserida_acima_reprova_no_validador(repo: Path) -> None:
    """A `:3` caiu no comentário que cita `acao_mic`; a `:6`, em `todas_as_cores`."""
    feito = _validar(repo)
    assert feito.returncode == 1, feito.stdout
    assert "não contém `acao_mic`" in feito.stdout, feito.stdout
    assert "não contém `cor`" in feito.stdout, feito.stdout


def test_o_reapontar_leva_a_citacao_e_nao_a_deixa_verde_no_lugar_errado(repo: Path) -> None:
    reapontar = _carregar(REAPONTAR, "reapontar_citacoes")
    atual = (repo / "src" / "hefesto_dualsense4unix" / "alvo.py").read_text(encoding="utf-8")
    linhas = atual.split("\n")
    relativo = "src/hefesto_dualsense4unix/alvo.py"
    assert not reapontar._contem(linhas, 3, 3, {"acao_mic"}, relativo), "o comentário não é o gesto"
    assert not reapontar._contem(linhas, 6, 6, {"cor"}, relativo), "`todas_as_cores` não é `cor`"
    assert reapontar.levar(repo, relativo, 3, 3, {"acao_mic"}) == (4, 4)
    assert reapontar.levar(repo, relativo, 6, 6, {"cor"}) == (7, 7)

    reapontar.reapontar(repo, escrever=True)
    texto = (repo / "docs" / "data" / "mapa.csv").read_text(encoding="utf-8")
    assert "alvo.py:4 (`acao_mic`)" in texto and "alvo.py:7 (`cor`)" in texto, texto
    assert _validar(repo).returncode == 0, _validar(repo).stdout


def test_o_reapontar_ancora_a_faixa_no_nome_fora_do_comentario(tmp_path: Path) -> None:
    """A âncora do `_mapear` é a linha do código, não o comentário que cita o nome.

    A linha `:2` (o comentário) mudou e caiu dentro do pedaço alterado; a `:4` (o código) só andou.
    Ancorada no comentário, a faixa se perde; ancorada no código, ela anda junto.
    """
    raiz = tmp_path / "repo"
    pacote = raiz / "src" / "hefesto_dualsense4unix"
    pacote.mkdir(parents=True)
    alvo = pacote / "alvo.py"
    alvo.write_text(
        "def f():\n    # chama acao_mic aqui\n    x = 0\n    acao_mic()\n    return x\n",
        encoding="utf-8")
    _git(raiz, "init", "-q")
    _git(raiz, "add", ".")
    _git(raiz, "commit", "-q", "-m", "o alvo nasce")
    alvo.write_text(
        "def f():\n    y = 0\n    z = 0\n    # chama o acao_mic logo abaixo\n    x = 0\n"
        "    acao_mic()\n    return x\n",
        encoding="utf-8")
    _git(raiz, "commit", "-q", "-am", "o comentário muda e duas linhas entram acima")
    reapontar = _carregar(REAPONTAR, "reapontar_citacoes")
    assert reapontar.levar(raiz, "src/hefesto_dualsense4unix/alvo.py", 2, 4, {"acao_mic"}) == (4, 6)
