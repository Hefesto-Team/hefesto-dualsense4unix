"""O daemon nasce com a vez do GIL curta (O-CONTROLE-NAO-ESPERA-A-VEZ-DO-GIL-01)."""
from __future__ import annotations

import sys

import pytest

from hefesto_dualsense4unix.daemon import main


class _AjustouError(Exception):
    pass


class _SeguiuSemAjustarError(Exception):
    pass


@pytest.fixture
def vez_de_antes():
    antes = sys.getswitchinterval()
    yield
    sys.setswitchinterval(antes)


def test_a_vez_do_gil_fica_em_no_maximo_um_milissegundo(vez_de_antes) -> None:
    sys.setswitchinterval(0.005)
    main.ajustar_a_vez_do_gil()
    assert sys.getswitchinterval() <= 0.001


def test_o_run_daemon_ajusta_a_vez_antes_de_tudo(monkeypatch: pytest.MonkeyPatch) -> None:
    from hefesto_dualsense4unix.utils import sd_notify

    def ajustou() -> None:
        raise _AjustouError

    def seguiu() -> None:
        raise _SeguiuSemAjustarError

    monkeypatch.setattr(main, "ajustar_a_vez_do_gil", ajustou)
    monkeypatch.setattr(sd_notify, "guardar_o_soquete", seguiu)
    with pytest.raises(_AjustouError):
        main.run_daemon()
