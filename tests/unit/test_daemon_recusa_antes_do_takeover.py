"""A ORDEM das duas recusas no boot do daemon (29/08/2026).

A chave (``utils/chave.py``) e a trava mútua (``utils/trava_do_aparelho.py``)
recusam ANTES do ``acquire_or_takeover``, e isso é requisito, não estilo: o
``acquire_or_takeover`` manda SIGTERM — e depois SIGKILL — no daemon
predecessor. Se a conferência viesse depois, **desligar um Hefesto derrubaria
o outro no caminho**, que é o oposto exato do que as duas existem para
garantir.

COMO ESTA RÉGUA MORDE
----------------------
Ela não se contenta com "o takeover não foi chamado": um ``run_daemon`` que
morresse na primeira linha também passaria nisso. O par
``test_sem_recusa_o_takeover_acontece`` é o controle — sem chave e sem trava,
o mesmo caminho chama o takeover. É a diferença entre os dois que prova a
ordem.
"""
from __future__ import annotations

from typing import Any

import pytest

from hefesto_dualsense4unix.daemon import main as daemon_main
from hefesto_dualsense4unix.utils import chave, single_instance, trava_do_aparelho


class _DaemonDeMentira:
    """Fica no lugar do `Daemon` real: nada de hidraw, uinput ou loop."""

    def __init__(self, **_kwargs: Any) -> None:
        pass

    async def run(self) -> None:
        return None


@pytest.fixture
def _sem_efeito_colateral(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Neutraliza tudo que `run_daemon` faria de verdade, menos a ORDEM."""
    chamadas: list[str] = []

    def _takeover(nome: str) -> int:
        chamadas.append(nome)
        return 0

    monkeypatch.setattr(single_instance, "acquire_or_takeover", _takeover)
    monkeypatch.setattr(trava_do_aparelho, "tomar", lambda: False)
    monkeypatch.setattr(daemon_main, "build_controller", lambda: object())
    monkeypatch.setattr(daemon_main, "Daemon", _DaemonDeMentira)
    # `os.nice(5)` no processo do pytest seria um efeito colateral de verdade.
    monkeypatch.setenv("HEFESTO_DUALSENSE4UNIX_NICE", "0")
    return chamadas


def test_sem_recusa_o_takeover_acontece(
    _sem_efeito_colateral: list[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """O controle. Sem ele, "não chamou" não provaria nada."""
    monkeypatch.setattr(chave, "motivo_do_desligamento", lambda: None)
    monkeypatch.setattr(trava_do_aparelho, "conferir_antes_do_takeover", lambda: None)

    assert daemon_main.run_daemon() == 0
    # A suíte roda com FAKE=1 (conftest), então o nome do lock é o isolado —
    # o que importa aqui é que houve UMA chamada.
    assert _sem_efeito_colateral == [daemon_main.single_instance_name()]


def test_a_chave_recusa_sem_matar_o_predecessor(
    _sem_efeito_colateral: list[str],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(
        chave, "motivo_do_desligamento", lambda: "desligado em 2026-08-29 por hefesto-chave"
    )
    monkeypatch.setattr(trava_do_aparelho, "conferir_antes_do_takeover", lambda: None)

    # 0, e não 1: `Restart=on-failure` na unit dela transformaria a recusa
    # num ciclo de respawn.
    assert daemon_main.run_daemon() == 0
    assert _sem_efeito_colateral == [], "o takeover NÃO pode ter rodado"
    erro = capsys.readouterr().err
    assert "está desligado pela chave" in erro
    assert "Para religar:" in erro


def test_a_trava_recusa_sem_matar_o_predecessor(
    _sem_efeito_colateral: list[str],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    dono = trava_do_aparelho.Dono(casa=trava_do_aparelho.CASA_DEV, pid=4242)
    recado = trava_do_aparelho.recado_da_recusa(dono, trava_do_aparelho.CASA_ESTAVEL)

    def _recusa() -> None:
        raise trava_do_aparelho.OutraCasaComOAparelhoError(dono, recado)

    monkeypatch.setattr(chave, "motivo_do_desligamento", lambda: None)
    monkeypatch.setattr(trava_do_aparelho, "conferir_antes_do_takeover", _recusa)

    assert daemon_main.run_daemon() == 0
    assert _sem_efeito_colateral == [], "o takeover NÃO pode ter rodado"
    erro = capsys.readouterr().err
    assert "Hefesto de DESENVOLVIMENTO está com o aparelho (pid 4242)" in erro
    assert "Para liberar:" in erro


def test_a_chave_vem_antes_da_trava(
    _sem_efeito_colateral: list[str],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Com as duas armadas, quem fala é a chave.

    A chave é a decisão DELA, gravada em disco; a trava é uma constatação
    sobre o outro processo. Dizer "o outro está com o aparelho" quando ela
    mesma desligou este Hefesto mandaria consertar a coisa errada.
    """
    def _nunca() -> None:  # pragma: no cover - o teste falha se rodar
        raise AssertionError("a trava foi consultada antes da chave")

    monkeypatch.setattr(chave, "motivo_do_desligamento", lambda: "porque sim")
    monkeypatch.setattr(trava_do_aparelho, "conferir_antes_do_takeover", _nunca)

    assert daemon_main.run_daemon() == 0
    assert "está desligado pela chave" in capsys.readouterr().err
