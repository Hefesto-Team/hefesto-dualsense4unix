"""O teste de vibração para quando a janela se esconde.

A sprint: O-TESTE-DE-VIBRACAO-PARA-QUANDO-A-JANELA-SE-ESCONDE-01.

MEDIDO EM 19/11/2026, antes da cura: `_a_janela_mudou(True)` só pausava o leitor e soltava as
ondas, e o `_tique` escondido seguia batendo os corações. A largada só rodava na troca de página,
no relato e no fim do processo: o teste «Vibração» (e o padrão em repetição, que renova o teto do
serviço a cada passo) mantinha o controle tremendo com a janela minimizada ou na bandeja, no cabo e
no rádio, até alguém reabrir e clicar «Parar».

A régua usa a ponte de mentira, dois controles (um no teste das barras, outro no padrão em
repetição) e um terceiro na háptica, manda `visibilidade=escondida` pela porta do `_gesto` e exige
a largada de cada um e zero `rumble_set_checked` depois da largada, com os corações batendo.
"""
from __future__ import annotations

import pathlib
import sys
import threading
import time
from types import SimpleNamespace
from typing import Any

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src"))

from tests.conftest import exigir_gi_real

exigir_gi_real("importa `interface.hefesto_vivo`, que carrega o GTK")

from hefesto_dualsense4unix.daemon.subsystems import padroes_de_vibracao
from hefesto_dualsense4unix.interface import hefesto_vivo as hv
from hefesto_dualsense4unix.interface import pacotes
from hefesto_dualsense4unix.interface.pacotes import a05_vibracao as a05

P1 = "aa:bb:cc:00:00:01"
P2 = "02:fe:00:00:00:02"
P3 = "aa:bb:cc:00:00:03"


class PonteQueAnota:
    """A ponte de mentira, com a assinatura de `app/ipc_bridge`."""

    def __init__(self) -> None:
        self.chamadas: list[tuple[str, tuple[Any, ...]]] = []
        self._trava = threading.Lock()

    def _anotar(self, nome: str, *args: Any) -> None:
        with self._trava:
            self.chamadas.append((nome, args))

    def rumble_set_checked(self, weak: int, strong: int, uniq: str | None = None
                           ) -> tuple[bool, str | None]:
        self._anotar("rumble_set_checked", uniq)
        return True, None

    def rumble_stop(self, uniq: str | None = None) -> bool:
        self._anotar("rumble_stop", uniq)
        return True

    def rumble_passthrough(self, enabled: bool = True, uniq: str | None = None) -> bool:
        self._anotar("rumble_passthrough", enabled, uniq)
        return True

    def haptica_testar(self, uniq: str, ligado: bool) -> tuple[bool, dict[str, Any] | None]:
        self._anotar("haptica_testar", uniq, ligado)
        return True, {"status": "ok"}

    def nomes(self) -> list[str]:
        with self._trava:
            return [n for n, _ in self.chamadas]


def _ctx() -> pacotes.Contexto:
    mesa = [{"uniq": u, "pref": f"p{i}", "jogador": i, "nome": "Prova", "cor": "",
             "transporte": t, "via": t, "alvo": True, "mascara": "dualsense"}
            for i, (u, t) in enumerate(((P1, "bt"), (P2, "usb"), (P3, "bt")), start=1)]
    conectados = [{"uniq": m["uniq"], "connected": True, "player": m["jogador"],
                   "transport": m["transporte"], "index": m["jogador"] - 1} for m in mesa]
    return pacotes.Contexto(
        state={"controllers": conectados, "rumble_motor_pct_padrao": 100},
        mesa=mesa, conectados=conectados, estados={}, externos=[])


@pytest.fixture(autouse=True)
def _mesa_limpa():
    a05.parar_o_teste()
    a05.parar_o_teste_da_haptica()
    yield
    a05.parar_o_teste()
    a05.parar_o_teste_da_haptica()


def _piloto() -> Any:
    """O `Piloto` sem GTK: só o que `_a_janela_mudou` e o `_gesto` da visibilidade tocam."""
    piloto = object.__new__(hv.Piloto)
    piloto._escondida = False
    piloto._escondida_desde = 0.0
    piloto._pintada = "algo"
    piloto._mesa_de_agora = _ctx().mesa
    piloto._estado_vivo = SimpleNamespace(
        pausar=lambda: None, retomar=lambda: None, ultimo=lambda: (None, None, 0))
    return piloto


def _esperar(condicao: Any, motivo: str) -> None:
    limite = time.monotonic() + 5
    while time.monotonic() < limite:
        if condicao():
            return
        time.sleep(0.02)
    pytest.fail(motivo)


def _ligar_os_tres(ponte: PonteQueAnota) -> None:
    ctx = _ctx()
    a05._EM_TESTE.add(P1)
    padrao = next(iter(padroes_de_vibracao.PADROES))
    a05._repetir_o_padrao(ctx, ponte, P2, padrao, padroes_de_vibracao.AMBOS)
    a05._EM_TESTE_DA_HAPTICA.add(P3)
    _esperar(lambda: "rumble_set_checked" in ponte.nomes(),
             "o padrão em repetição não começou a mandar")


def test_esconder_a_janela_larga_o_teste_de_cada_controle(monkeypatch: pytest.MonkeyPatch) -> None:
    """D-2511-ESCONDER-A-JANELA-LARGA-O-TESTE-DE-VIBRACAO: barras, padrão em repetição e
    háptica voltam ao jogo, cada um, e nada renova depois."""
    ponte = PonteQueAnota()
    monkeypatch.setattr(hv, "ponte", ponte)
    monkeypatch.setattr(hv, "_soltar_as_ondas", lambda: None)
    _ligar_os_tres(ponte)
    piloto = _piloto()

    piloto._gesto({"visibilidade": "escondida"})

    _esperar(lambda: a05.em_teste() == frozenset() and a05.em_teste_da_haptica() == frozenset(),
             f"esconder a janela não largou o teste: {sorted(a05.em_teste())}")
    _esperar(lambda: ("haptica_testar", (P3, False)) in ponte.chamadas,
             "a háptica do terceiro controle não calou")
    for uniq in (P1, P2):
        _esperar(lambda u=uniq: ("rumble_passthrough", (True, u)) in ponte.chamadas,
                 f"a vibração de {uniq} não voltou ao jogo: {ponte.chamadas}")
        assert ("rumble_stop", (uniq,)) in ponte.chamadas
    marca = len(ponte.chamadas)
    for _ in range(4):
        pacotes.bater_os_coracoes(_ctx(), ponte)
        time.sleep(a05.SEGUNDOS_ENTRE_BATIMENTOS / 8)
    depois = [n for n, _ in ponte.chamadas[marca:]]
    assert "rumble_set_checked" not in depois, (
        f"o controle seguiu recebendo vibração com a janela escondida: {depois}")


def test_voltar_a_janela_nao_religa_o_teste(monkeypatch: pytest.MonkeyPatch) -> None:
    """A janela que volta à vista não retoma o teste que a escondida largou."""
    ponte = PonteQueAnota()
    monkeypatch.setattr(hv, "ponte", ponte)
    monkeypatch.setattr(hv, "_soltar_as_ondas", lambda: None)
    _ligar_os_tres(ponte)
    piloto = _piloto()
    piloto._gesto({"visibilidade": "escondida"})
    _esperar(lambda: a05.em_teste() == frozenset(), "o teste não foi largado")
    piloto._gesto({"visibilidade": "vista"})
    assert a05.em_teste() == frozenset()
    assert a05.em_teste_da_haptica() == frozenset()


def test_o_gesto_de_visibilidade_repetido_nao_larga_de_novo(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """Dizer «escondida» duas vezes é um só esconder: a largada não roda a cada aviso."""
    ponte = PonteQueAnota()
    monkeypatch.setattr(hv, "ponte", ponte)
    monkeypatch.setattr(hv, "_soltar_as_ondas", lambda: None)
    piloto = _piloto()
    piloto._gesto({"visibilidade": "escondida"})
    _esperar(lambda: piloto._escondida is True, "a janela não ficou escondida")
    a05._EM_TESTE.add(P1)
    piloto._gesto({"visibilidade": "escondida"})
    time.sleep(0.2)
    assert a05.em_teste() == frozenset({P1}), "o aviso repetido largou o que outro pedido ligou"
