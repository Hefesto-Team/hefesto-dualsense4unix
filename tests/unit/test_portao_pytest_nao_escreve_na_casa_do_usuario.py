"""O runner `pytest` do `portoes.sh` roda num LAR DE MENTIRA — `PORTAO-LAR-01`."""

from __future__ import annotations

import re
import shlex
import subprocess
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
PORTOES = RAIZ / "scripts" / "portoes.sh"

VARIAVEIS = (
    "HOME",
    "XDG_CONFIG_HOME",
    "XDG_DATA_HOME",
    "XDG_CACHE_HOME",
    "XDG_STATE_HOME",
    "XDG_RUNTIME_DIR",
)


def _bloco_do_array() -> str:
    """O trecho do `portoes.sh` que cria o lar e monta o ambiente."""
    fonte = PORTOES.read_text(encoding="utf-8")
    inicio = fonte.find('LAR_DE_MENTIRA="$(mktemp')
    if inicio < 0:
        pytest.fail(
            "o `portoes.sh` não cria mais o LAR_DE_MENTIRA — a cura do "
            "PORTAO-LAR-01 foi arrancada, e o runner `pytest` voltou a rodar "
            "com o HOME real de quem chamou"
        )
    fim = fonte.find(")", fonte.find("_AMBIENTE_DE_MENTIRA=(", inicio))
    assert fim > inicio, "o array _AMBIENTE_DE_MENTIRA está sem fecho"
    return fonte[inicio : fim + 1]


def test_o_mecanismo_alcanca_o_import(tmp_path: Path) -> None:
    """`HOME` no ambiente muda `Path.home()` num processo novo — a premissa."""
    lar = tmp_path / "lar"
    lar.mkdir()
    saida = subprocess.run(
        [sys.executable, "-c", "from pathlib import Path; print(Path.home())"],
        env={"HOME": str(lar), "PATH": "/usr/bin:/bin"},
        capture_output=True,
        text=True,
        check=True,
    )
    assert saida.stdout.strip() == str(lar)


def test_o_lar_de_mentira_cobre_as_seis_variaveis(tmp_path: Path) -> None:
    """Executa o bloco do script e confere onde o processo filho cai."""
    bloco = _bloco_do_array()
    script = "\n".join(
        (
            "set -euo pipefail",
            bloco,
            'env ${_AMBIENTE_DE_MENTIRA[*]} ' + shlex.quote(sys.executable) + " -c "
            + shlex.quote(
                "import os;"
                "print('\\n'.join(f'{k}={os.environ.get(k, \"\")}' "
                "for k in " + repr(list(VARIAVEIS)) + "))"
            ),
            'printf "LAR=%s\\n" "$LAR_DE_MENTIRA"',
        )
    )
    saida = subprocess.run(
        ["bash", "-c", script],
        env={"PATH": "/usr/bin:/bin", "TMPDIR": str(tmp_path)},
        capture_output=True,
        text=True,
    )
    assert saida.returncode == 0, saida.stderr
    lidos = dict(
        linha.split("=", 1)
        for linha in saida.stdout.splitlines()
        if "=" in linha
    )
    lar = lidos.pop("LAR", "")
    assert lar.startswith(str(tmp_path)), (
        f"o lar nasceu fora do TMPDIR do teste: {lar!r}"
    )
    for nome in VARIAVEIS:
        valor = lidos.get(nome, "")
        assert valor.startswith(lar), (
            f"{nome} não caiu no lar de mentira: {valor!r} — o runner `pytest` "
            f"do portão escreveria em {valor!r} na máquina de quem chamar"
        )


def test_o_runner_pytest_usa_o_lar() -> None:
    """A linha do runner `pytest` carrega o ambiente de mentira."""
    fonte = PORTOES.read_text(encoding="utf-8")
    linha = next(
        (ln for ln in fonte.splitlines() if re.match(r"\s*pytest\)\s*cmd=", ln)),
        None,
    )
    assert linha is not None, "o runner `pytest` sumiu da tabela do portoes.sh"
    assert "_AMBIENTE_DE_MENTIRA" in linha, (
        "o runner `pytest` voltou a rodar com o HOME de quem chamou — em "
        "21/09/2026 isso zerou o `controller_masks.json` dela e trocou o "
        "perfil ativo no meio de uma corrida. Ver PORTAO-LAR-01."
    )
