"""O ÚNICO ponto por onde a janela grava perfil em disco (GRAVA-POR-UM-FUNIL-01)."""
from __future__ import annotations

from hefesto_dualsense4unix.profiles.schema import PonteConfirmada, Profile
from hefesto_dualsense4unix.utils.logging_config import get_logger

logger = get_logger(__name__)


def carimbo_que_o_save_leva(
    existente: Profile | None, do_rascunho: PonteConfirmada | None
) -> PonteConfirmada | None:
    """Carimbo de ponte que um perfil leva ao disco. UM dono, os dois botões."""
    if existente is not None and existente.ponte is not None:
        return existente.ponte
    return do_rascunho


