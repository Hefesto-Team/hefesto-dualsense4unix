"""O leitor de movimento que um caso liga não sobrevive a ele.

A guarda é o ``_nenhum_leitor_fisico_atravessa`` do ``tests/conftest.py``.
Medido na costura da 6e-3, 25/09/2026: a família da ``MesaHonesta`` deixava
um ``PhysicalReportReader`` vivo por jogador montado, 189 num arquivo só, e o
caso que junta todo fio do processo parou a parte 03 da suíte por minutos.

Os dois casos rodam NA ORDEM do arquivo: o primeiro liga um leitor de verdade
e não o para, e o segundo exige que nenhum tenha atravessado.

MORDIDA: tire o laço do ``leitor.stop()`` da guarda — o segundo caso reprova.
"""

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
