"""ONDA0-Z5/T5 — `app/mesa.py` é dono único de "quem está na mesa", sem GTK."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_SRC = Path(__file__).resolve().parents[2] / "src"


def test_importar_app_mesa_sozinho_em_processo_novo_nao_precisa_de_gtk() -> None:
    """Processo NOVO, sem `sys.modules` contaminado por outro teste da sessão."""
    script = (
        "import sys\n"
        f"sys.path.insert(0, {str(REPO_SRC)!r})\n"
        "assert 'gi' not in sys.modules\n"
        "from hefesto_dualsense4unix.app import mesa\n"
        "assert 'gi' not in sys.modules, "
        "'app.mesa importou gi/GTK — não é dono, é atalho'\n"
        "assert 'hefesto_dualsense4unix.app.actions.status_actions' not in sys.modules, "
        "'app.mesa arrastou status_actions — não é dono, é atalho'\n"
        "mesa.texto_de_contagem(mesa.ContagemDeControles(adotados=2, externos=1))\n"
        "print('ok')\n"
    )
    resultado = subprocess.run(
        [sys.executable, "-c", script], capture_output=True, text=True, timeout=30
    )
    assert resultado.returncode == 0, (
        f"stdout={resultado.stdout!r} stderr={resultado.stderr!r}"
    )
    assert resultado.stdout.strip() == "ok"


