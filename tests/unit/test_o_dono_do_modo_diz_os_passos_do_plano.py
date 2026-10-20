"""O-DONO-DO-MODO-DIZ-OS-PASSOS-DO-PLANO-01 — a linha de dono de cada modo diz o plano de hoje.

Medido em 20/10/2026: `painel.ESCRITOR_DOS_MODOS[desktop]`, a linha que o piloto mostra como dono
do gesto `modo:desktop` (`controles_vivos.DONOS_DOS_GESTOS`), dizia que o terceiro IPC era
`mouse.emulation.restore`. Desde 17/09/2026 (POINT-AND-CLICK-01) é `desktop.arranjo.apply`. A régua
compara os métodos de IPC que a linha cita com os do `plan_mode_transition` do mesmo modo.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from hefesto_dualsense4unix.app.actions import mode_transition
from hefesto_dualsense4unix.app.actions.jogar import painel

SERVIDOR = (Path(__file__).resolve().parents[2] / "src" / "hefesto_dualsense4unix" / "daemon"
            / "ipc_server.py")


def _metodos_do_servidor() -> set[str]:
    """Os nomes do mapa de handlers do servidor, lidos do fonte."""
    texto = SERVIDOR.read_text(encoding="utf-8")
    metodos = set(re.findall(r'"([a-z_]+(?:\.[a-z_]+)+)":\s*self\._handle_', texto))
    assert {"desktop.arranjo.apply", "native.mode.set"} <= metodos, (
        "o mapa do servidor mudou de forma")
    return metodos


@pytest.mark.parametrize("modo", sorted(painel.ESCRITOR_DOS_MODOS))
def test_a_linha_de_dono_cita_os_passos_do_plano(modo: str) -> None:
    """Todo IPC que a linha cita está no plano, e quem cita um cita todos."""
    servidor = _metodos_do_servidor()
    citados = {m for m in re.findall(r"`([a-z_.]+)`", painel.ESCRITOR_DOS_MODOS[modo])
               if m in servidor}
    plano = {metodo for metodo, _params in mode_transition.plan_mode_transition(modo)}
    assert citados <= plano, (
        f"a linha de dono de {modo!r} cita {sorted(citados - plano)}, que o plano não manda")
    if citados:
        assert citados == plano, (
            f"a linha de dono de {modo!r} esquece {sorted(plano - citados)} do plano")
