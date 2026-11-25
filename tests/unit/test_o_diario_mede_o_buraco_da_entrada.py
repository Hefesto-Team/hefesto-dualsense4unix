"""O-DIARIO-MEDE-O-BURACO-DA-ENTRADA-POR-CONTROLE-01 — o silêncio curto da entrada deixa medida.

O leitor do controle já avisa o silêncio de um segundo (`report_thread_entrada_muda`). Abaixo
disso nada ficava escrito: o buraco de 100 a 500 ms, que é o botão que chega atrasado, não tinha
linha. Aqui a conta recebe voltas vazias e voltas com relatório num relógio de mentira, no cabo
e no rádio, e o laço de produção do leitor (`sendReport`) prova que a conta está ligada nele.
"""

from __future__ import annotations

from typing import Any

import pytest

from hefesto_dualsense4unix.core import backend_pydualsense as bp
from tests.unit.test_laco_de_escrita_02 import (
    _DispositivoDoLaco,
    _estado_do_cabo,
    _handle_do_laco,
    _LoggerDeMentira,
    _o_c_do_hidapi,
    _read_input_do_upstream,
)

__all__ = ["_o_c_do_hidapi"]

TRANSPORTES = [("usb", None), ("bt", bp.ConnectionType.BT)]
RELATORIO = [b"x"]


class _Mesa:
    def __init__(self, monkeypatch: pytest.MonkeyPatch, con: Any) -> None:
        self.t = 5000.0
        self.h = _handle_do_laco()
        self.h.conType = con
        self.h._pinned_path = b"/dev/hidraw-teste"
        self.registro = _LoggerDeMentira()
        monkeypatch.setattr(bp, "logger", self.registro)
        monkeypatch.setattr(bp.time, "monotonic", lambda: self.t)

    def calar(self, segundos: float, voltas: int, leitor: Any = None) -> None:
        """Um silêncio de ``segundos``: ``voltas`` voltas vazias e depois uma com relatório."""
        leitor = self.h if leitor is None else leitor
        passo = segundos / voltas
        bp._o_buraco_da_volta(leitor, [])
        for _ in range(voltas - 1):
            self.t += passo
            bp._o_buraco_da_volta(leitor, [])
        self.t += passo
        bp._o_buraco_da_volta(leitor, RELATORIO)

    def passar(self, segundos: float, leitor: Any = None) -> None:
        self.t += segundos
        bp._o_buraco_da_volta(self.h if leitor is None else leitor, RELATORIO)

    def linhas(self) -> list[dict[str, Any]]:
        return list(self.registro.eventos("entrada_buraco_minuto"))


@pytest.mark.parametrize(("nome", "con"), TRANSPORTES, ids=[t[0] for t in TRANSPORTES])
def test_o_buraco_acima_do_piso_sai_numa_linha_por_janela(
    monkeypatch: pytest.MonkeyPatch, nome: str, con: Any,
) -> None:
    """D-2511-O-DIARIO-MEDE-O-BURACO-DA-ENTRADA-POR-CONTROLE.

    MORDIDA: deixe de contar o silêncio que passou do piso, e a linha não sai.
    """
    mesa = _Mesa(monkeypatch, con)
    mesa.calar(0.12, 30)
    mesa.calar(0.30, 75)
    mesa.calar(0.08, 1)
    assert mesa.linhas() == [], "a linha só sai quando a janela fecha"

    mesa.passar(bp.BURACO_DA_ENTRADA_JANELA_SEC)

    linhas = mesa.linhas()
    assert len(linhas) == 1, linhas
    linha = linhas[0]
    assert linha["transporte"] == nome
    assert linha["vezes"] == 3
    assert linha["pior_ms"] == 300
    assert linha["voltas_vazias_no_pior"] == 75
    assert linha["path"] == b"/dev/hidraw-teste"


def test_o_leitor_que_parou_se_distingue_do_aparelho_que_calou(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """O pior buraco com uma volta vazia só é o leitor parado, não o enlace.

    MORDIDA: guarde sempre zero nas voltas do pior, e os dois casos ficam iguais.
    """
    mesa = _Mesa(monkeypatch, bp.ConnectionType.BT)
    mesa.calar(0.40, 1)
    mesa.passar(bp.BURACO_DA_ENTRADA_JANELA_SEC)
    assert mesa.linhas()[0]["voltas_vazias_no_pior"] == 1

    mesa.calar(0.40, 100)
    mesa.passar(bp.BURACO_DA_ENTRADA_JANELA_SEC)
    assert mesa.linhas()[1]["voltas_vazias_no_pior"] == 100


@pytest.mark.parametrize(("nome", "con"), TRANSPORTES, ids=[t[0] for t in TRANSPORTES])
def test_a_janela_sem_buraco_nao_escreve_nada(
    monkeypatch: pytest.MonkeyPatch, nome: str, con: Any,
) -> None:
    """O intervalo normal entre relatórios (abaixo do piso) não deixa linha, em janela nenhuma.

    MORDIDA: zere o piso, e cada janela escreve uma linha.
    """
    mesa = _Mesa(monkeypatch, con)
    for _ in range(4):
        for _ in range(50):
            mesa.calar(bp.BURACO_DA_ENTRADA_PISO_SEC / 5, 2)
        mesa.passar(bp.BURACO_DA_ENTRADA_JANELA_SEC)

    assert mesa.linhas() == []


def test_cada_janela_recomeca_do_zero(monkeypatch: pytest.MonkeyPatch) -> None:
    """O pior de uma janela não vaza para a seguinte.

    MORDIDA: não zere o pior ao fechar a janela, e a segunda linha repete os 300 ms.
    """
    mesa = _Mesa(monkeypatch, bp.ConnectionType.BT)
    mesa.calar(0.30, 60)
    mesa.passar(bp.BURACO_DA_ENTRADA_JANELA_SEC)
    mesa.calar(0.07, 14)
    mesa.passar(bp.BURACO_DA_ENTRADA_JANELA_SEC)

    assert [(x["vezes"], x["pior_ms"]) for x in mesa.linhas()] == [(1, 300), (1, 70)]


def test_dois_controles_medem_cada_um_o_seu(monkeypatch: pytest.MonkeyPatch) -> None:
    """A conta mora no leitor de cada controle: o buraco de um não entra na do outro."""
    mesa = _Mesa(monkeypatch, bp.ConnectionType.BT)
    cabo = _handle_do_laco()
    cabo.conType = None
    cabo._pinned_path = b"/dev/hidraw-do-cabo"

    mesa.calar(0.25, 50)
    mesa.calar(0.004, 1, leitor=cabo)
    mesa.passar(bp.BURACO_DA_ENTRADA_JANELA_SEC)
    mesa.passar(0.0, leitor=cabo)

    assert [x["path"] for x in mesa.linhas()] == [b"/dev/hidraw-teste"]


def test_o_laco_de_producao_do_leitor_chama_a_conta(monkeypatch: pytest.MonkeyPatch) -> None:
    """O `sendReport` de produção, com um aparelho que cala por 1 s e depois fala.

    MORDIDA: tire `_o_buraco_da_volta` da volta do leitor, e a linha não sai.
    """
    inst = _handle_do_laco()
    inst.conType = None
    inst._pinned_path = b"/dev/hidraw-teste"
    registro = _LoggerDeMentira()
    monkeypatch.setattr(bp, "logger", registro)
    relogio = {"t": 1000.0}
    contas = {"read": 0, "sleep": 0}
    voltas_ate_o_fim = int(bp.BURACO_DA_ENTRADA_JANELA_SEC / 0.5) + 8

    class _DispositivoDeMentira(_DispositivoDoLaco):
        def read(self, _n: int) -> bytes | None:
            contas["read"] += 1
            if contas["read"] > 20 * voltas_ate_o_fim:
                inst.ds_thread = False
            if contas["read"] in (1, 5, 6):
                return _estado_do_cabo()
            self._vazio()
            return None

    def _sono_de_mentira(_secs: float) -> None:
        contas["sleep"] += 1
        relogio["t"] += 0.5
        if contas["sleep"] >= voltas_ate_o_fim:
            inst.ds_thread = False

    inst.device = _DispositivoDeMentira()
    monkeypatch.setattr(inst, "readInput", _read_input_do_upstream)
    monkeypatch.setattr(inst, "prepareReport", lambda: [0] * 64)
    monkeypatch.setattr(inst, "writeReport", lambda _r, **_geracao: None)
    monkeypatch.setattr(bp.time, "monotonic", lambda: relogio["t"])
    monkeypatch.setattr(bp.time, "sleep", _sono_de_mentira)

    inst.sendReport()

    linhas = registro.eventos("entrada_buraco_minuto")
    assert linhas, "o laço do leitor não chamou a conta do buraco"
    assert linhas[0]["transporte"] == "usb"
    assert linhas[0]["pior_ms"] >= 500
