"""O-ADAPTADOR-NAO-TRAVA-AO-CANCELAR-A-BUSCA-01 — a busca da ponte root fecha pelo stdin."""

from __future__ import annotations

import dataclasses
import os
import subprocess
import time
from pathlib import Path

import pytest

from hefesto_dualsense4unix.integrations import gesto_de_pareamento as gp
from hefesto_dualsense4unix.integrations.conexao_zumbi import PedidoAPonte
from tests.unit.barramento_de_mentira import ADAPTADOR, PONTE, ainda_varrendo, ambiente, montar


@pytest.fixture()
def barramento(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    raiz = montar(tmp_path)
    for chave in ("SUDO_UID", "SUDO_USER"):
        monkeypatch.delenv(chave, raising=False)
    for chave, valor in ambiente(raiz).items():
        if os.environ.get(chave) != valor:
            monkeypatch.setenv(chave, valor)
    temporarios = tmp_path / "tmp-da-ponte"
    temporarios.mkdir()
    monkeypatch.setenv("TMPDIR", str(temporarios))
    return raiz


def _como_do_root(pedido: PedidoAPonte, sinais: list[int]) -> subprocess.Popen[str]:
    """A ponte de verdade sem o ``sudo``, com o sinal recusado como o do processo do root."""
    processo = gp._abrir_de_verdade(dataclasses.replace(pedido, argv=("bash", *pedido.argv[3:])))

    def recusar(sinal: int) -> None:
        sinais.append(sinal)
        raise PermissionError(1, "Operation not permitted")

    processo.send_signal = recusar  # type: ignore[method-assign]
    return processo


def test_fechar_encerra_a_ponte_do_root_pelo_stdin_e_pelo_trap(
    barramento: Path, tmp_path: Path
) -> None:
    """O-ADAPTADOR-NAO-TRAVA-AO-CANCELAR-A-BUSCA-01: sem sinal, o EOF fecha a busca em 2 s."""
    sinais: list[int] = []
    janela = gp.JanelaDeBusca(
        ADAPTADOR, 60, caminho=str(PONTE), abrir=lambda pedido: _como_do_root(pedido, sinais)
    )
    assert janela.abrir_a_janela() == ""
    limite = time.monotonic() + 5.0
    while not ainda_varrendo(barramento) and time.monotonic() < limite:
        time.sleep(0.05)
    assert ainda_varrendo(barramento), "a janela de mentira nem abriu"
    processo = janela._processo
    assert processo is not None

    comeco = time.monotonic()
    janela.fechar()
    while processo.poll() is None and time.monotonic() - comeco < 5.0:
        time.sleep(0.05)
    decorrido = time.monotonic() - comeco

    assert processo.poll() is not None and decorrido < 2.0, f"a ponte durou {decorrido:.1f} s"
    assert not ainda_varrendo(barramento), "a ponte saiu e o bluetoothctl seguiu varrendo"
    assert list((tmp_path / "tmp-da-ponte").iterdir()) == [], "o trap não apagou os temporários"
    assert sinais == [], "o fechar mandou sinal a um processo do root"
