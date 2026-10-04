"""O perfil com `rumble.passthrough` solta o par que VIBRA de cada controle.

Com a vibração por controle (A-VIBRACAO-E-A-HAPTICA-DE-CADA-CONTROLE-SAO-
INDEPENDENTES-01), o resumo `rumble_active` é só o par mais recente. O P1 vibrando
e o P2 acabado de parar deixavam o resumo em `(0, 0)`, e a soltura do passthrough
(`apply_profile_rumble_passthrough`) saía cedo, com o P1 ainda fixado e o jogo sem
a vibração dele. O silêncio deliberado (o par em zero) continua valendo.
"""
from __future__ import annotations

from typing import Any

import pytest

from hefesto_dualsense4unix.daemon.lifecycle import Daemon, DaemonConfig
from hefesto_dualsense4unix.daemon.subsystems import rumble
from hefesto_dualsense4unix.testing.fake_controller import FakeController

P1 = "aabbcc000001"
P2 = "aabbcc000002"
P3 = "aabbcc000003"


class _Controle(FakeController):
    """Anota cada escrita de motor por dono, sem tocar aparelho nenhum."""

    def __init__(self) -> None:
        super().__init__()
        self.escritas: list[tuple[str | None, int, int]] = []

    def set_rumble_for(self, uniq: str, weak: int, strong: int) -> bool:
        self.escritas.append((uniq, weak, strong))
        return True

    def set_rumble(self, weak: int, strong: int, **_kw: Any) -> None:
        self.escritas.append((None, weak, strong))


@pytest.fixture
def daemon() -> Daemon:
    return Daemon(controller=_Controle(), config=DaemonConfig())


def _fixar(daemon: Daemon, dono: str | None, weak: int, strong: int, em: float) -> None:
    rumble.fixar_par(daemon.config, dono, weak, strong, em, so_este=True)


def test_o_par_que_vibra_e_solto_mesmo_com_o_resumo_em_zero(daemon: Daemon) -> None:
    """MORDIDA: o `if active == (0, 0): return` de volta deixa o P1 fixado."""
    _fixar(daemon, P1, 160, 220, 1.0)
    _fixar(daemon, P2, 0, 0, 2.0)
    assert daemon.config.rumble_active == (0, 0)

    daemon.apply_profile_rumble_passthrough(True)

    assert P1 not in rumble.pares_fixados(daemon.config)
    assert (P1, 0, 0) in daemon.controller.escritas  # type: ignore[attr-defined]


def test_o_silencio_deliberado_de_outro_controle_fica(daemon: Daemon) -> None:
    _fixar(daemon, P1, 160, 220, 1.0)
    _fixar(daemon, P2, 0, 0, 2.0)

    daemon.apply_profile_rumble_passthrough(True)

    assert rumble.pares_fixados(daemon.config) == {P2: (0, 0, 2.0)}
    assert daemon.config.rumble_active == (0, 0)
    assert daemon.config.rumble_active_uniq == P2
    assert not any(e[0] == P2 for e in daemon.controller.escritas)  # type: ignore[attr-defined]


def test_cada_controle_que_vibra_volta_ao_jogo(daemon: Daemon) -> None:
    _fixar(daemon, P1, 160, 220, 1.0)
    _fixar(daemon, P2, 10, 0, 2.0)
    _fixar(daemon, P3, 0, 0, 3.0)

    daemon.apply_profile_rumble_passthrough(True)

    zerados = {e[0] for e in daemon.controller.escritas if e[1:] == (0, 0)}  # type: ignore[attr-defined]
    assert zerados == {P1, P2}
    assert set(rumble.pares_fixados(daemon.config)) == {P3}


def test_sem_nenhum_par_vibrando_nada_e_solto(daemon: Daemon) -> None:
    _fixar(daemon, P1, 0, 0, 1.0)

    daemon.apply_profile_rumble_passthrough(True)

    assert rumble.pares_fixados(daemon.config) == {P1: (0, 0, 1.0)}
    assert daemon.controller.escritas == []  # type: ignore[attr-defined]


def test_o_par_da_mesa_inteira_solta_pelo_broadcast(daemon: Daemon) -> None:
    _fixar(daemon, None, 100, 120, 1.0)

    daemon.apply_profile_rumble_passthrough(True)

    assert daemon.config.rumble_active is None
    assert (None, 0, 0) in daemon.controller.escritas  # type: ignore[attr-defined]


def test_sem_passthrough_nada_e_solto(daemon: Daemon) -> None:
    _fixar(daemon, P1, 160, 220, 1.0)

    daemon.apply_profile_rumble_passthrough(False)

    assert rumble.pares_fixados(daemon.config) == {P1: (160, 220, 1.0)}


def test_o_registro_dos_pares_nasce_declarado_e_e_um_por_config() -> None:
    """MORDIDA: tirar o campo do `DaemonConfig` e o registro nasce por `getattr` solto."""
    import dataclasses

    nomes = {campo.name for campo in dataclasses.fields(DaemonConfig)}
    assert "rumble_fixados" in nomes
    um, outro = DaemonConfig(), DaemonConfig()
    assert um.rumble_fixados == {}
    assert um.rumble_fixados is not outro.rumble_fixados
