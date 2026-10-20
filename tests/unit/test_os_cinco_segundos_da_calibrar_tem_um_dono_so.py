"""OS-CINCO-SEGUNDOS-DA-CALIBRAR-TEM-UM-DONO-SO-01 (20/10/2026).

O «Medindo N s» da Calibrar diz o tempo que o daemon mede
(`roteador_de_movimento.SEGUNDOS_DO_ZERO`, o do `motion.calibrate`), e não uma cópia.

A MORDIDA: devolva `SEGUNDOS = 5` ao `interface/calibrar.py` e o primeiro caso reprova.
"""
from __future__ import annotations

import importlib.util
import pathlib
import sys

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
INTERFACE = RAIZ / "src" / "hefesto_dualsense4unix" / "interface"
for _caminho in (str(RAIZ / "src"), str(INTERFACE)):
    if _caminho not in sys.path:
        sys.path.insert(0, _caminho)

from tests.conftest import exigir_gi_real

exigir_gi_real("carrega o `calibrar`, que carrega o GTK")

from hefesto_dualsense4unix.core import roteador_de_movimento as rot


def _calibrar_novo() -> object:
    """Um `calibrar` recém-carregado, que lê o tempo do daemon na hora do import."""
    spec = importlib.util.spec_from_file_location(
        "calibrar_do_teste_dos_segundos", INTERFACE / "calibrar.py"
    )
    assert spec is not None and spec.loader is not None
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def _passo_medindo(modulo: object) -> str:
    return next(texto for chave, texto, _ in modulo.PASSOS if chave == "e-medindo")  # type: ignore[attr-defined]


def test_o_tempo_da_tela_vem_do_daemon(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(rot, "SEGUNDOS_DO_ZERO", 7.0)
    assert _passo_medindo(_calibrar_novo()) == "Medindo 7 s", (
        "a Calibrar diz um tempo que não é o que o daemon mede (`SEGUNDOS_DO_ZERO`)")


@pytest.mark.parametrize("publicado", [False, True], ids=["mockup", "publicado"])
def test_o_desenho_e_o_publicado_dizem_o_tempo_de_hoje(publicado: bool) -> None:
    import onde

    arquivo = (onde.PUBLICADO if publicado else onde.BANCADA) / "calibrar-sensores.html"
    esperado = f"<b>Medindo {rot.SEGUNDOS_DO_ZERO:g} s</b>"
    assert esperado in arquivo.read_text(encoding="utf-8"), f"{arquivo} não diz {esperado}"
