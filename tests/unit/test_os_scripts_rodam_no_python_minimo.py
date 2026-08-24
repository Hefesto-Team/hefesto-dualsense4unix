"""Todo script versionado tem de compilar no Python MÍNIMO que o projeto declara.

NASCEU DE UM DEFEITO MEU, em 23/08/2026, e ele é o "vício de bancada" na sua
forma mais pura. O `gerar-painel.py` foi escrito com uma f-string que usa aspas
escapadas por dentro — **sintaxe que só existe a partir do Python 3.12**. Ele
rodava aqui, porque esta bancada tem 3.12; e quebraria com `SyntaxError` na
máquina de quem tem 3.10 ou 3.11, que o `pyproject.toml` declara suportar.

Nada acusou: a suíte roda no python da bancada, e um `SyntaxError` de versão
futura é indistinguível de código correto para quem já tem a versão.

**A RÉGUA É DUPLA, e as duas metades foram medidas:**

1. `ast.parse(fonte, feature_version=...)` — reprova sem precisar de outro
   interpretador instalado. **Mas ela é PARCIAL**, e isso foi conferido caso a
   caso em 23/08/2026 contra `feature_version=(3, 10)`:

   | sintaxe | o `ast` pega? |
   |---|---|
   | `except*` (3.11) | sim |
   | `type X = int` (3.12) | sim |
   | `def f[T](x: T)` (3.12) | sim |
   | **aspas reusadas em f-string (3.12)** | **NÃO** |

   Ou seja: ela não pega justamente o caso que originou este arquivo. Declarar
   isso é obrigatório — régua que se acredita completa é pior que régua nenhuma.

2. **O `ruff`, que pega o resto** — e ele JÁ está configurado para isso:
   `target-version = "py310"` no `pyproject.toml`. Ele acusou o defeito na hora.

**O BURACO REAL, e é ele que este arquivo fecha:** o CI roda
`ruff check src/ tests/` — **`scripts/` fica de fora**. E foi num script que o
defeito nasceu. As duas metades juntas cobrem o território inteiro.

O ALVO desta casa, e ele é o motivo desta régua existir, nas palavras dela:
*"quero que funcione pra mim obviamente, mas pra qualquer outra pessoa, com
qualquer outro adaptador, outros hubs, outros Linux, outros kernel."*
"""
from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]

#: As pastas de código versionado que o portão varre. `venv/` e `.venv/` ficam
#: de fora: são dependência de terceiro, não código desta casa.
TERRITORIOS = ("src", "scripts", "tests")


def _minimo_declarado() -> tuple[int, int]:
    """O Python mínimo, lido do `pyproject.toml` — nunca digitado aqui.

    Um número digitado neste arquivo sobreviveria a uma mudança do
    `requires-python` e o portão passaria a medir o passado.
    """
    texto = (RAIZ / "pyproject.toml").read_text(encoding="utf-8")
    achado = re.search(r'requires-python\s*=\s*"[><=~^]*(\d+)\.(\d+)', texto)
    assert achado, "não achei `requires-python` no pyproject.toml"
    return int(achado.group(1)), int(achado.group(2))


def _fontes() -> list[Path]:
    achadas: list[Path] = []
    for territorio in TERRITORIOS:
        for f in (RAIZ / territorio).rglob("*.py"):
            if any(p in {"__pycache__", ".venv", "venv"} for p in f.parts):
                continue
            achadas.append(f)
    return sorted(achadas)


def test_a_regua_sabe_reprovar() -> None:
    """Valide o instrumento antes de acreditar nele — a disciplina da casa.

    Usa `type X = int`, que o `ast` reprova em 3.10. NÃO usa o caso das aspas em
    f-string: ele passa, e é justamente por isso que a metade do `ruff` existe
    (ver o docstring do módulo).
    """
    minimo = _minimo_declarado()
    if minimo >= (3, 12):
        pytest.skip("o mínimo declarado já é 3.12+; a régua não teria o que pegar")

    with pytest.raises(SyntaxError):
        ast.parse("type X = int", feature_version=minimo)


def test_todo_script_compila_no_minimo_declarado() -> None:
    """MORDE: escrever sintaxe de 3.12 em qualquer script versionado.

    Foi assim que o `gerar-painel.py` nasceu quebrado para metade das pessoas,
    passando verde nesta bancada.
    """
    minimo = _minimo_declarado()
    quebrados: list[str] = []

    for f in _fontes():
        fonte = f.read_text(encoding="utf-8", errors="replace")
        try:
            ast.parse(fonte, feature_version=minimo)
        except SyntaxError as erro:
            quebrados.append(
                f"{f.relative_to(RAIZ)}:{erro.lineno} — {erro.msg}"
            )

    versao = ".".join(map(str, minimo))
    assert not quebrados, (
        f"estes arquivos NÃO compilam no Python {versao}, que é o mínimo que o "
        f"`pyproject.toml` declara suportar (esta bancada roda "
        f"{'.'.join(map(str, sys.version_info[:2]))}, e por isso não acusa):\n  "
        + "\n  ".join(quebrados)
    )


def test_o_ruff_cobre_scripts_tambem() -> None:
    """O buraco que deixou o defeito passar: o CI não roda `ruff` em `scripts/`.

    O `ruff` tem `target-version = "py310"` no `pyproject.toml` e acusou o
    defeito na hora — mas só quando alguém o apontou para o arquivo à mão. O CI
    roda `ruff check src/ tests/`, e o script ficou fora.

    MORDE: escrever sintaxe de 3.12 em `scripts/`. A metade do `ast` não pega,
    e sem esta chamada nada mais pega.
    """
    import subprocess

    p = subprocess.run(
        [".venv/bin/ruff", "check", "scripts/", "--output-format", "concise"],
        cwd=RAIZ,
        capture_output=True,
        text=True,
        timeout=300,
    )

    # `E999` foi REMOVIDO do ruff e não pode mais ser selecionado (medido em
    # 23/08/2026: `Rule E999 was removed and cannot be selected`). Erro de
    # sintaxe hoje sai como `invalid-syntax` na saída concisa — e essa é a única
    # classe que este teste cobra. Estilo em `scripts/` não é assunto daqui: o
    # CI escolheu não olhar essa pasta, e reabrir a decisão pela porta de um
    # teste seria decidir por quem decidiu.
    quebras = [
        linha for linha in p.stdout.splitlines() if "invalid-syntax" in linha
    ]

    assert not quebras, (
        "há sintaxe nova demais para o `target-version` do projeto em "
        "`scripts/` — o CI roda `ruff check src/ tests/` e não olha essa "
        "pasta, então este teste é o único portão:\n  "
        + "\n  ".join(quebras)
    )
