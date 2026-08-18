"""R-13 (auditoria 23/07) — a numeração de jogador para de colidir.

A queixa dela: *"dois 'player 2' e dois 'player 1' em vez de 1, 2, 3, 4"*.

Estado medido em 23/07: os EXTERNOS ocupam os slots 1 (Pro Nintendo) e 3
(8BitDo); o DualSense branco é slot 2. O co-op numera por conta própria — 1 no
primário, 2..N nos secundários — e escreve isso direto nos nós sysfs de
player-LED. Duas autoridades, dois espaços de numeração, mesma lâmpada.

Duas correções contidas, ambas independentes do R-20:

1. **sem secundário não há co-op** — `should_be_active()` liga pela preferência
   persistida (`coop_enabled.flag`, que é 1 aqui), NÃO pela contagem de
   controles; a docstring do módulo promete um gate de "2+ controles" que nunca
   existiu. Com um DualSense só, o co-op cravava 1 no primário — e o Pro
   Nintendo já era 1. A correção é no EFEITO: mexer no gate exigiria enumerar
   `/dev/input` por tick (o que o PERF-MULTI-CONTROLLER-01 removeu) e faria o
   co-op piscar a cada blip de link.

2. **o piso dos externos considera o alcance do co-op** — `_ds_reserve()` só
   olhava os slots do registry dos DualSense, então um externo podia receber um
   número que o co-op estava acendendo em outro controle.
"""

from __future__ import annotations

from typing import Any


class _CoopFalso:
    def __init__(self, *, ativo: bool, secundarios: int) -> None:
        self._ativo = ativo
        self._secundarios = secundarios

    def should_be_active(self) -> bool:
        return self._ativo

    def player_count(self) -> int:
        return 1 + self._secundarios


class _RegistryFalso:
    def __init__(self, slots: dict[str, int]) -> None:
        self._slots = slots

    def snapshot(self) -> dict[str, int]:
        return dict(self._slots)


def _piso(slots: dict[str, int], coop: Any) -> int:
    """Roda o `_ds_reserve` REAL sobre dublês."""
    import hefesto_dualsense4unix.daemon.subsystems.coop as coop_mod
    from hefesto_dualsense4unix.daemon.subsystems.external_identity import (
        ExternalLedSync,
    )

    daemon = type("D", (), {"identity_registry": _RegistryFalso(slots)})()
    original = coop_mod.get_coop_manager
    coop_mod.get_coop_manager = lambda _d: coop  # type: ignore[assignment]
    try:
        sync = ExternalLedSync.__new__(ExternalLedSync)
        sync._daemon = daemon  # type: ignore[attr-defined]
        return sync._ds_reserve()
    finally:
        coop_mod.get_coop_manager = original  # type: ignore[assignment]


class TestPisoDosExternos:
    def test_sem_coop_o_piso_e_so_o_maior_slot_dualsense(self) -> None:
        piso = _piso({"branco": 2}, _CoopFalso(ativo=False, secundarios=0))
        assert piso == 2

    def test_coop_com_secundarios_empurra_os_externos(self) -> None:
        """O caso dela: co-op com 2 DualSense usa 1 e 2 — externo começa em 3."""
        piso = _piso({"branco": 2, "roxo": 1}, _CoopFalso(ativo=True, secundarios=1))
        assert piso >= 2

    def test_coop_com_quatro_jogadores_reserva_ate_quatro(self) -> None:
        piso = _piso({"branco": 1}, _CoopFalso(ativo=True, secundarios=3))
        assert piso == 4, (
            "com 4 jogadores de co-op, um externo não pode receber 1..4 — "
            "seriam dois controles com o mesmo número aceso"
        )

    def test_coop_ativo_sem_secundario_nao_levanta_o_piso(self) -> None:
        """Sem secundário o co-op não acende nada (item 4) — nada a reservar."""
        piso = _piso({"branco": 1}, _CoopFalso(ativo=True, secundarios=0))
        assert piso == 1


class TestCoopSemSecundarioNaoEscreveLed:
    def test_o_guard_existe_antes_de_montar_os_alvos(self) -> None:
        from pathlib import Path

        fonte = (
            Path(__file__).resolve().parents[2]
            / "src/hefesto_dualsense4unix/daemon/subsystems/coop.py"
        ).read_text(encoding="utf-8")
        corpo = fonte.split("def _apply_coop_player_leds", 1)[1].split("\n    def ", 1)[0]
        antes_dos_alvos = corpo.split("targets: list", 1)[0]
        assert "if not self._players:" in antes_dos_alvos, (
            "sem secundário o co-op não pode cravar player-LED 1 no primário — "
            "é o que produzia 'dois player 1' com o Pro Nintendo no slot 1"
        )
