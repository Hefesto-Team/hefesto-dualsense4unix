"""O import RELATIVO de um módulo do WebKit também manda o teste para processo próprio.

O fecho do `scripts/rodar-a-suite.sh` casava `from x import`, `import x`, `from . import x` e
`from tests.unit.x import`, mas não `from .x import y` nem `from ..pasta.x import y`. Nenhum
módulo do WebKit era importado assim, então o furo era latente; o primeiro a sê-lo mandaria o
teste de WebKit para o processo da parte, onde ele morre com `rc=139`
(A-JANELA-ABERTA-CABE-NA-PARTE-01). Desde 23/10/2026 o fecho é lido pelo `ast` e casa pelo
caminho pontuado inteiro (A-LISTA-DO-WEBKIT-DA-SUITE-VOLTA-AO-TAMANHO-REAL-01), e o relativo é
resolvido contra o pacote de quem importa (`absoluto`). A régua pergunta ao próprio script
(`LISTAR_O_WEBKIT=1`) numa árvore de mentira.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
SUITE = RAIZ / "scripts" / "rodar-a-suite.sh"


def _quem_roda_sozinho(tmp_path: Path, suite: Path) -> list[str]:
    raiz = tmp_path / "arvore"
    (raiz / "scripts").mkdir(parents=True)
    shutil.copy2(suite, raiz / "scripts" / "rodar-a-suite.sh")
    unit = raiz / "tests" / "unit"
    unit.mkdir(parents=True)
    (unit / "__init__.py").write_text("")
    (unit / "ajudante_base.py").write_text(
        'def gtk():\n    import gi\n    gi.require_version("WebKit2", "4.1")\n'
    )
    (unit / "ajudante_filho.py").write_text("from .ajudante_base import gtk\n")
    (unit / "ajudante_comum.py").write_text("def nada():\n    return 1\n")
    (unit / "test_ponto.py").write_text("from .ajudante_base import gtk\n")
    (unit / "test_dois_pontos.py").write_text("from ..unit.ajudante_base import gtk\n")
    (unit / "test_pelo_filho.py").write_text("from .ajudante_filho import gtk\n")
    (unit / "test_ponto_e_pacote.py").write_text("from . import ajudante_base\n")
    (unit / "test_do_comum.py").write_text("from .ajudante_comum import nada\n")
    fora = {"PYTEST_ADDOPTS", "SUITE_PYTEST_ARGS", "LD_PRELOAD", "PARTES", "SAIDA", "PARTIDO"}
    env = {k: v for k, v in os.environ.items() if k not in fora and not k.startswith("COV_")}
    env.update(
        {"PY_COLORS": "0", "PY": sys.executable, "LISTAR_O_WEBKIT": "1",
         "SAIDA": str(tmp_path / "saida")}
    )
    feito = subprocess.run(
        ["bash", str(raiz / "scripts" / "rodar-a-suite.sh")], cwd=raiz, capture_output=True,
        text=True, timeout=120, check=False, env=env,
    )
    assert feito.returncode == 0, feito.stdout + feito.stderr
    return sorted(feito.stdout.split())


def test_o_import_relativo_de_um_modulo_do_webkit_roda_em_processo_proprio(tmp_path: Path) -> None:
    assert _quem_roda_sozinho(tmp_path, SUITE) == [
        "tests/unit/test_dois_pontos.py",
        "tests/unit/test_pelo_filho.py",
        "tests/unit/test_ponto.py",
        "tests/unit/test_ponto_e_pacote.py",
    ]


def test_a_regua_morde_sem_o_relativo(tmp_path: Path) -> None:
    """Com o relativo ignorado (a leitura de antes), ele fica de fora."""
    texto = SUITE.read_text(encoding="utf-8")
    cura = "def absoluto(base, nivel, pacote):\n"
    assert cura in texto, "a resolução do import relativo deixou de estar no script"
    velha = tmp_path / "velha.sh"
    velha.write_text(texto.replace(cura, cura + '    if nivel:\n        return ""\n'),
                     encoding="utf-8")
    sozinhos = _quem_roda_sozinho(tmp_path / "mentira", velha)
    assert "tests/unit/test_ponto.py" not in sozinhos
    assert "tests/unit/test_dois_pontos.py" not in sozinhos
    assert "tests/unit/test_pelo_filho.py" not in sozinhos
