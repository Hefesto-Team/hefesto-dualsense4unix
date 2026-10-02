"""O leitor de movimento que um caso liga não sobrevive a ele."""

from __future__ import annotations

import threading
from typing import Any

from hefesto_dualsense4unix.core.physical_report_reader import PhysicalReportReader


class _VpadDeMentira:
    player = 9

    def set_motion_streaming(self, ligado: bool) -> None:
        pass

    def forward_motion(self, janela: Any) -> None:
        pass


def _leitores_vivos() -> list[PhysicalReportReader]:
    vivos = []
    for fio in threading.enumerate():
        dono = getattr(getattr(fio, "_target", None), "__self__", None)
        if isinstance(dono, PhysicalReportReader):
            vivos.append(dono)
    return vivos


def test_1_o_caso_liga_um_leitor_e_nao_o_para() -> None:
    """Sem nó para abrir, o leitor fica de pé no recuo — como o do co-op na mesa de mentira."""
    leitor = PhysicalReportReader(lambda: None, _VpadDeMentira())
    assert leitor.start()
    assert leitor in _leitores_vivos()


def test_2_nenhum_leitor_atravessou() -> None:
    assert _leitores_vivos() == [], "um leitor ligado no caso anterior continua vivo"
