"""Os corações da vibração não seguram o tique — OS-CORACOES-DA-VIBRACAO-NAO-SEGURAM-A-JANELA-01.

MEDIDO EM 10/10/2026, antes da cura: o `_tique` chama `pacotes.bater_os_coracoes`
no fio do GTK a cada 100 ms, e os dois corações da aba Vibração faziam o IPC ali
mesmo, um por controle em teste a cada segundo. Com o serviço demorando o teto
da ponte (0,25 s), quatro controles em teste prendiam o fio do GTK por um
segundo inteiro a cada segundo. E a recusa do serviço sumia num
`contextlib.suppress`.

A cura: o coração só diz QUEM bate e o quê; o despachante entrega cada
batimento à fila do controle dele (a mesma dos gestos, então o batimento nunca
passa à frente de um «Parar» do mesmo controle), um batimento pendente não se
empilha, e a recusa vai ao diário da janela uma vez por episódio.

Os endereços são da faixa forjada (`aa:bb:cc`).
"""
from __future__ import annotations

import pathlib
import sys
import threading
import time
from typing import Any

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src"))

from tests.conftest import exigir_gi_real

exigir_gi_real("importa `interface.pacotes`, que carrega o GTK")

from hefesto_dualsense4unix.interface import pacotes
from hefesto_dualsense4unix.interface.pacotes import a05_vibracao as a05

P1 = "aa:bb:cc:00:00:01"
P2 = "aa:bb:cc:00:00:02"
P3 = "aa:bb:cc:00:00:03"
P4 = "aa:bb:cc:00:00:04"
NA_VIBRACAO = (P1, P2)
NA_HAPTICA = (P3, P4)

#: O teto de tela da ponte de verdade: o serviço com o laço ocupado gasta todo.
DEMORA_S = 0.25

#: O que o tique pode gastar entregando os quatro batimentos.
TETO_DO_TIQUE_MS = 20.0


class PonteDormente:
    """A ponte de mentira, com a assinatura de `app/ipc_bridge` e o prazo inteiro gasto."""

    def __init__(self) -> None:
        self.trava = threading.Lock()
        self.batidas: list[tuple[str, str]] = []
        self.recusa = ""

    def rumble_set_checked(self, weak: int, strong: int, uniq: str | None = None
                           ) -> tuple[bool, str | None]:
        time.sleep(DEMORA_S)
        with self.trava:
            self.batidas.append(("rumble_set", str(uniq)))
        if self.recusa:
            return False, self.recusa
        return True, None

    def haptica_testar(self, uniq: str, ligado: bool) -> tuple[bool, dict[str, Any] | None]:
        time.sleep(DEMORA_S)
        with self.trava:
            self.batidas.append(("haptica_testar", uniq))
        if self.recusa:
            return True, {"status": "recusado", "motivo": self.recusa}
        return True, {"status": "ok"}

    def quantas(self, uniq: str) -> int:
        with self.trava:
            return sum(1 for _, u in self.batidas if u == uniq)


def _ctx() -> pacotes.Contexto:
    todos = NA_VIBRACAO + NA_HAPTICA
    mesa = [{"uniq": u, "pref": f"p{i}", "jogador": i, "nome": "Prova", "cor": "",
             "transporte": "usb" if i % 2 else "bt", "via": "cabo" if i % 2 else "radio",
             "alvo": True, "mascara": "dualsense"}
            for i, u in enumerate(todos, start=1)]
    conectados = [{"uniq": u, "connected": True, "player": i,
                   "transport": "usb" if i % 2 else "bt"}
                  for i, u in enumerate(todos, start=1)]
    return pacotes.Contexto(
        state={"controllers": conectados, "rumble_motor_pct_padrao": 100},
        mesa=mesa, conectados=conectados, estados={}, externos=[])


def _esperar_as_filas(teto_s: float = 5.0) -> None:
    """Até a última fila esvaziar: o batimento roda fora do tique."""
    fim = time.monotonic() + teto_s
    while time.monotonic() < fim:
        vivos = [t for t in threading.enumerate() if t.name.startswith("coração")]
        if not vivos:
            return
        for t in vivos:
            t.join(max(0.0, fim - time.monotonic()))
    raise AssertionError("os batimentos não saíram das filas em 5 s")


@pytest.fixture(autouse=True)
def _quatro_em_teste():
    a05.parar_o_teste()
    a05.parar_o_teste_da_haptica()
    a05._EM_TESTE.update(NA_VIBRACAO)
    a05._EM_TESTE_DA_HAPTICA.update(NA_HAPTICA)
    yield
    _esperar_as_filas()
    a05.parar_o_teste()
    a05.parar_o_teste_da_haptica()


def _bater_por(segundos: float, ctx: pacotes.Contexto, p: Any) -> list[float]:
    """O tique de 100 ms, pelo tempo pedido. Devolve o custo de cada um, em ms."""
    custos: list[float] = []
    fim = time.monotonic() + segundos
    while time.monotonic() < fim:
        t0 = time.perf_counter()
        pacotes.bater_os_coracoes(ctx, p)
        custos.append((time.perf_counter() - t0) * 1000)
        time.sleep(0.1)
    return custos


def test_o_tique_entrega_os_quatro_batimentos_sem_esperar_o_servico() -> None:
    """Quatro controles em teste, o serviço gastando 0,25 s cada: o tique não espera."""
    p = PonteDormente()
    ctx = _ctx()
    t0 = time.perf_counter()
    pacotes.bater_os_coracoes(ctx, p)
    custo = (time.perf_counter() - t0) * 1000
    _esperar_as_filas()
    assert custo < TETO_DO_TIQUE_MS, (
        f"o tique gastou {custo:.0f} ms batendo os corações de quatro controles: "
        "o IPC voltou para o fio do GTK")
    for uniq in NA_VIBRACAO + NA_HAPTICA:
        assert p.quantas(uniq) == 1, f"{uniq} recebeu {p.quantas(uniq)} batimento(s)"


def test_cada_controle_recebe_um_batimento_por_segundo() -> None:
    """Três segundos de tique: três batimentos para cada um dos quatro, nem mais nem menos."""
    p = PonteDormente()
    custos = _bater_por(3.0, _ctx(), p)
    _esperar_as_filas()
    for uniq in NA_VIBRACAO + NA_HAPTICA:
        assert 3 <= p.quantas(uniq) <= 4, (
            f"{uniq} recebeu {p.quantas(uniq)} batimento(s) em 3 s")
    assert max(custos) < 10 * TETO_DO_TIQUE_MS, (
        f"um tique gastou {max(custos):.0f} ms com os batimentos fora dele")


def test_o_batimento_pendente_nao_se_empilha() -> None:
    """Se o anterior daquele controle ainda não saiu, o novo não entra na fila."""
    p = PonteDormente()
    ctx = _ctx()
    pacotes.bater_os_coracoes(ctx, p)
    a05._BATEU_EM.clear()
    a05._BATEU_A_HAPTICA_EM.clear()
    pacotes.bater_os_coracoes(ctx, p)
    _esperar_as_filas()
    for uniq in NA_VIBRACAO + NA_HAPTICA:
        assert p.quantas(uniq) == 1, (
            f"{uniq} recebeu {p.quantas(uniq)} batimentos: o pendente se empilhou")


def test_o_batimento_que_chega_depois_do_parar_nao_religa() -> None:
    """O «Parar» entra na fila do controle; o batimento atrás dele não manda o par."""
    p = PonteDormente()
    ctx = _ctx()
    parado = threading.Event()

    def parar() -> None:
        a05.parar_o_teste(P1)
        parado.set()

    segura = threading.Event()
    pacotes.na_fila([pacotes.fila_do_controle(P1)], segura.wait, nome="gesto prova")
    pacotes.na_fila([pacotes.fila_do_controle(P1)], parar, nome="gesto prova")
    pacotes.bater_os_coracoes(ctx, p)
    segura.set()
    assert parado.wait(5)
    _esperar_as_filas()
    assert p.quantas(P1) == 0, (
        "o batimento que esperava atrás do «Parar» mandou o par mesmo assim")


def test_a_recusa_vai_ao_diario_uma_vez_por_episodio(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """O serviço recusando: uma linha por controle, e outra só depois de ele aceitar."""
    p = PonteDormente()
    ctx = _ctx()
    p.recusa = "recusado pela prova"
    _bater_por(2.2, ctx, p)
    _esperar_as_filas()
    p.recusa = ""
    _bater_por(1.1, ctx, p)
    _esperar_as_filas()
    p.recusa = "recusado pela prova"
    _bater_por(1.1, ctx, p)
    _esperar_as_filas()
    diario = capsys.readouterr().err.splitlines()
    for uniq in NA_VIBRACAO + NA_HAPTICA:
        linhas = [x for x in diario if uniq in x and "recusado pela prova" in x]
        assert len(linhas) == 2, (
            f"{uniq}: {len(linhas)} linha(s) de recusa no diário, esperava uma por "
            f"episódio (duas): {linhas}")
