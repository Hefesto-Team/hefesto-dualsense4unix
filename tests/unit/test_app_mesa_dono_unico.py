"""ONDA0-Z5/T5 — `app/mesa.py` é dono único de "quem está na mesa", sem GTK.

CONTAGEM-E-COOP-01 (29/07) já tinha nascido a função canônica
(`ContagemDeControles`/`texto_de_contagem`), mas ela morava DENTRO do mixin
da aba Status (`app/actions/status_actions.py`) — nove abas precisam da
resposta, só uma era dona do arquivo (a mesma doença que a F3 já causou
noutro fato, com custo medido de perda de dado dela em 23/08).

A MORDIDA: importar `app.mesa` sem montar GTK e sem importar
`app.actions.status_actions`. Se isso levantar `ImportError`/
`ValueError: Namespace Gtk not available` (o erro que `gi.require_version`
produz sob Xvfb sem display, ou mesmo com display se o import arrastar o
mixin), o módulo não é dono de nada — é atalho que só funciona porque
`status_actions` já foi importado antes em algum outro teste da sessão.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_SRC = Path(__file__).resolve().parents[2] / "src"


def test_importar_app_mesa_sozinho_em_processo_novo_nao_precisa_de_gtk() -> None:
    """Processo NOVO, sem `sys.modules` contaminado por outro teste da sessão.

    Roda fora do processo do pytest de propósito: se `app/mesa.py` importasse
    `gi`/GTK (direto ou via `status_actions`), o subprocesso reprovaria com
    `ModuleNotFoundError`/`ValueError` mesmo sem display — é a única forma de
    provar "não precisa de GTK" sem depender de quem já rodou antes na mesma
    sessão de teste.
    """
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


def test_contagem_de_controles_deriva_do_state_e_dos_externos() -> None:
    from hefesto_dualsense4unix.app import mesa

    state = {
        "controllers": [
            {"connected": True, "is_primary": True, "transport": "usb"},
            {"connected": True, "is_primary": False, "transport": "bt"},
            {"connected": False, "is_primary": False, "transport": None},
        ]
    }
    contagem = mesa.contagem_de_controles(state, externos=1)
    assert contagem.adotados == 2
    assert contagem.externos == 1
    assert contagem.na_mesa == 3


def test_texto_de_contagem_mesa_vazia_e_string_vazia() -> None:
    from hefesto_dualsense4unix.app import mesa

    vazio = mesa.contagem_de_controles({"controllers": []}, externos=0)
    assert vazio.na_mesa == 0
    assert mesa.texto_de_contagem(vazio) == ""


def test_status_actions_reexporta_os_mesmos_objetos_de_mesa() -> None:
    """O espelho (§ do docstring de `app/mesa.py`): mesma classe/função,
    não uma cópia — `status_actions.ContagemDeControles is mesa.ContagemDeControles`.
    """
    from tests.conftest import exigir_gi_real

    exigir_gi_real()
    from hefesto_dualsense4unix.app import mesa
    from hefesto_dualsense4unix.app.actions import status_actions

    assert status_actions.ContagemDeControles is mesa.ContagemDeControles
    assert status_actions.texto_de_contagem is mesa.texto_de_contagem
