"""ENV-VELHA-NO-BOOT-01 — o daemon subia novo e servia o arquivo do daemon velho."""

from __future__ import annotations

import ast
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
LIFECYCLE = RAIZ / "src" / "hefesto_dualsense4unix" / "daemon" / "lifecycle.py"


def _corpo_do_start() -> ast.AsyncFunctionDef:
    """A corotina que sobe o daemon — a que termina esperando o stop_event."""
    arvore = ast.parse(LIFECYCLE.read_text(encoding="utf-8"), filename=str(LIFECYCLE))
    for no in ast.walk(arvore):
        if not isinstance(no, ast.AsyncFunctionDef):
            continue
        fonte = ast.dump(no)
        if "_stop_event" in fonte and "daemon_starting" in fonte:
            return no
    raise AssertionError("não achei a corotina de start do daemon")


def _chama(no: ast.AST, nome: str) -> bool:
    return any(
        isinstance(c, ast.Call)
        and (
            (isinstance(c.func, ast.Name) and c.func.id == nome)
            or (isinstance(c.func, ast.Attribute) and c.func.attr == nome)
        )
        for c in ast.walk(no)
    )


def test_o_boot_do_daemon_materializa_o_launch_env() -> None:
    """A cura. Morde ao arrancar a chamada do `start`."""
    assert _chama(_corpo_do_start(), "materialize_launch_env"), (
        "o start do daemon não materializa o launch_env — o arquivo do ciclo "
        "anterior continua valendo até a primeira transição do gamepad"
    )


def test_a_materializacao_vem_depois_do_perfil_restaurado() -> None:
    """A ordem é a cura; inverter troca um defeito por outro."""
    start = _corpo_do_start()
    linha_restore = max(
        (n.lineno for n in ast.walk(start) if _chama(n, "restore_last_profile")),
        default=None,
    )
    linha_materialize = max(
        (n.lineno for n in ast.walk(start) if _chama(n, "materialize_launch_env")),
        default=None,
    )
    assert linha_restore is not None, "o boot não restaura mais o perfil?"
    assert linha_materialize is not None
    assert linha_materialize > linha_restore, (
        "materializar antes de restaurar o perfil grava um estado provisório"
    )


def test_a_materializacao_do_boot_nao_derruba_o_start() -> None:
    """Materialização quebrada não pode custar o daemon inteiro."""
    start = _corpo_do_start()
    protegidas = [
        n
        for n in ast.walk(start)
        if isinstance(n, ast.With) and _chama(n, "materialize_launch_env")
    ]
    assert protegidas, "a chamada do boot não está dentro de um `with`"
    assert any(_chama(w.items[0].context_expr, "suppress") for w in protegidas), (
        "a materialização do boot tem de estar sob `contextlib.suppress`"
    )
