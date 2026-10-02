"""NO-NATIVO-PELO-RADIO-O-JOGO-E-DONO-DOS-MOTORES-01 — a regra do cabo chega ao rádio."""

from __future__ import annotations

from typing import Any

import pytest

from hefesto_dualsense4unix.integrations import alto_falante_bt as af
from tests.unit.test_a_haptica_por_audio_e_o_alto_falante_chegam_ao_radio import (
    FORJA,
    MESA,
    MOTOR,
    Mesa,
    no_do,
)


def _daemon(*, nativo: bool) -> Any:
    """O ``Daemon`` de verdade, com o Modo Nativo no atributo que o gesto escreve."""
    from hefesto_dualsense4unix.daemon.lifecycle import Daemon, DaemonConfig
    from hefesto_dualsense4unix.testing import FakeController

    daemon = Daemon(controller=FakeController(), config=DaemonConfig())
    daemon._native_mode = nativo
    assert daemon.is_native_mode() is nativo
    return daemon


@pytest.fixture
def sala(monkeypatch: pytest.MonkeyPatch) -> Any:
    m = Mesa(monkeypatch)
    yield m
    m.fechar()


def _o_jogo_toca_nos_motores(sala: Mesa, quem: tuple[str, ...]) -> None:
    """O jogo no Nativo abre o endpoint de cada um e toca nos motores dele."""
    for uniq in quem:
        sala.fonte(no_do(uniq)).quadro = MOTOR
        sala.servidor.tocar(no_do(uniq), FORJA)


@pytest.mark.parametrize("n", [2, 3, 4], ids=["dois", "três", "quatro"])
def test_no_nativo_a_ponte_de_todo_controle_no_radio_vai_a_haptica(sala: Mesa, n: int) -> None:
    """No Modo Nativo, o jogo tocando no endpoint de cada um leva as ``n`` pontes à háptica."""
    quem = MESA[:n]
    sala.sub._daemon = _daemon(nativo=True)
    _o_jogo_toca_nos_motores(sala, quem)
    sala.volta()
    for uniq in quem:
        assert sala.arranjo(uniq) == af.ARRANJO_HAPTICA_032.nome, (
            f"no Nativo a ponte do lugar {MESA.index(uniq) + 1} não foi à háptica: "
            f"{sala.arranjo(uniq)!r}"
        )
    for uniq in quem:
        sala.esperar(no_do(uniq), True)
    sala.volta()
    for uniq in quem:
        assert sala.arranjo(uniq) == af.ARRANJO_HAPTICA_032.nome


def test_fora_do_nativo_a_escolha_dela_segue_valendo_no_radio(sala: Mesa) -> None:
    """Sem o Modo Nativo, quem não mexeu não vibra pelo rádio (a escolha (b) dela)."""
    sala.sub._daemon = _daemon(nativo=False)
    _o_jogo_toca_nos_motores(sala, MESA[:2])
    sala.volta()
    for uniq in MESA[:2]:
        assert sala.arranjo(uniq) != af.ARRANJO_HAPTICA_032.nome, (
            "fora do Nativo a ponte de quem não mexeu foi à háptica"
        )


def test_o_cabo_e_o_radio_perguntam_ao_mesmo_dono(
    sala: Mesa, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A pergunta é uma só: o dono das portas do rumble responde aos dois transportes."""
    from hefesto_dualsense4unix.daemon.subsystems import rumble

    sala.sub._daemon = _daemon(nativo=True)
    monkeypatch.setattr(rumble, "modo_nativo_manda_nos_motores", lambda _d: False)
    _o_jogo_toca_nos_motores(sala, MESA[:2])
    sala.volta()
    for uniq in MESA[:2]:
        assert sala.arranjo(uniq) != af.ARRANJO_HAPTICA_032.nome
