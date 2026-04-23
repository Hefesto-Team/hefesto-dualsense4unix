"""Testes do validador estrito de acentuação PT-BR.

Cobre gate (detecção de violações), whitelist de paths, skip de
UPPERCASE_SNAKE e fenced-code em markdown, e o modo --fix.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
SCRIPT = RAIZ / "scripts" / "validar-acentuacao.py"


def _roda(args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=str(cwd),
        text=True,
        capture_output=True,
    )


@pytest.fixture()
def sandbox(tmp_path: Path) -> Path:
    """Cria sandbox com git init para que descobrir_raiz aponte para tmp_path."""
    subprocess.run(["git", "init", "-q"], cwd=str(tmp_path), check=True)
    # copia o script para a sandbox para que rode na raiz correta
    destino = tmp_path / "scripts"
    destino.mkdir()
    (destino / "validar-acentuacao.py").write_bytes(SCRIPT.read_bytes())
    (destino / "validar-acentuacao.py").chmod(0o755)
    return tmp_path


def test_arquivo_com_palavra_sem_acento_falha(sandbox: Path) -> None:
    alvo = sandbox / "src" / "exemplo.py"
    alvo.parent.mkdir(parents=True)
    alvo.write_text('msg = "perfil nao encontrado"\n', encoding="utf-8")

    res = _roda(["--check-file", str(alvo)], sandbox)
    assert res.returncode == 1
    assert "nao" in res.stdout
    assert "não" in res.stdout  # sugestão contém "não"


def test_arquivo_com_acento_correto_passa(sandbox: Path) -> None:
    alvo = sandbox / "src" / "exemplo.py"
    alvo.parent.mkdir(parents=True)
    alvo.write_text('msg = "perfil não encontrado"\n', encoding="utf-8")

    res = _roda(["--check-file", str(alvo)], sandbox)
    assert res.returncode == 0, res.stdout + res.stderr


def test_whitelist_respeitada_validator_brief(sandbox: Path) -> None:
    alvo = sandbox / "VALIDATOR_BRIEF.md"
    alvo.write_text("# Brief\n\nfuncao sem acento aqui\n", encoding="utf-8")

    res = _roda(["--check-file", str(alvo)], sandbox)
    assert res.returncode == 0, res.stdout


def test_json_ignorado(sandbox: Path) -> None:
    alvo = sandbox / "assets" / "config.json"
    alvo.parent.mkdir(parents=True)
    alvo.write_text('{"descricao": "texto sem acento"}\n', encoding="utf-8")

    res = _roda(["--check-file", str(alvo)], sandbox)
    assert res.returncode == 0


def test_uppercase_snake_id_ignorado(sandbox: Path) -> None:
    alvo = sandbox / "docs" / "spec.md"
    alvo.parent.mkdir(parents=True)
    alvo.write_text("Sprint CHORE-ACAO-01 concluída.\n", encoding="utf-8")

    res = _roda(["--check-file", str(alvo)], sandbox)
    assert res.returncode == 0, res.stdout


def test_fenced_code_block_ignorado(sandbox: Path) -> None:
    alvo = sandbox / "docs" / "exemplo.md"
    alvo.parent.mkdir(parents=True)
    alvo.write_text(
        "# Titulo\n\nTexto normal aqui.\n\n```\ndef funcao():\n    pass\n```\n",
        encoding="utf-8",
    )

    # "funcao" dentro do fence não deve ser sinalizado.
    # "Titulo" sem acento seria sinalizado se estivesse no dicionário;
    # o teste só valida fenced.
    res = _roda(["--check-file", str(alvo)], sandbox)
    assert "funcao" not in res.stdout, res.stdout


def test_noqa_inline_ignora_linha(sandbox: Path) -> None:
    alvo = sandbox / "src" / "exemplo.py"
    alvo.parent.mkdir(parents=True)
    alvo.write_text('msg = "nao"  # noqa: acentuacao\n', encoding="utf-8")

    res = _roda(["--check-file", str(alvo)], sandbox)
    assert res.returncode == 0


def test_fix_substitui_corretamente(sandbox: Path) -> None:
    alvo = sandbox / "src" / "exemplo.py"
    alvo.parent.mkdir(parents=True)
    alvo.write_text(
        'msg = "perfil nao encontrado: descricao invalida"\n',
        encoding="utf-8",
    )

    res = _roda(["--fix", str(alvo)], sandbox)
    assert res.returncode == 0, res.stdout + res.stderr

    conteudo = alvo.read_text(encoding="utf-8")
    assert "não" in conteudo
    assert "descrição" in conteudo
    assert "nao" not in conteudo
    assert "descricao" not in conteudo


def test_fix_preserva_fenced_code_block(sandbox: Path) -> None:
    alvo = sandbox / "docs" / "exemplo.md"
    alvo.parent.mkdir(parents=True)
    conteudo_original = (
        "# Guia\n\nTexto fora do bloco: nao corrigir aqui? corrigir sim.\n\n"
        "```python\ndef funcao():\n    return \"acao bruta\"\n```\n"
    )
    alvo.write_text(conteudo_original, encoding="utf-8")

    res = _roda(["--fix", str(alvo)], sandbox)
    assert res.returncode == 0

    novo = alvo.read_text(encoding="utf-8")
    # Fora do fence foi corrigido.
    assert "não corrigir" in novo
    # Dentro do fence foi preservado.
    assert "def funcao():" in novo
    assert "\"acao bruta\"" in novo


def test_fix_preserva_uppercase_snake(sandbox: Path) -> None:
    alvo = sandbox / "docs" / "spec.md"
    alvo.parent.mkdir(parents=True)
    alvo.write_text(
        "Sprint CHORE-ACAO-01 trata de acao legado.\n",
        encoding="utf-8",
    )

    res = _roda(["--fix", str(alvo)], sandbox)
    assert res.returncode == 0

    novo = alvo.read_text(encoding="utf-8")
    assert "CHORE-ACAO-01" in novo  # ID preservado
    assert "ação legado" in novo  # palavra corrigida


def test_show_whitelist_lista_padroes(sandbox: Path) -> None:
    res = _roda(["--show-whitelist"], sandbox)
    assert res.returncode == 0
    assert "VALIDATOR_BRIEF" in res.stdout
    assert "AGENTS" in res.stdout
