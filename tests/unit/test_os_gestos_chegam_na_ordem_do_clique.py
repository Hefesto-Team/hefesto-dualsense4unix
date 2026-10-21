"""Os gestos chegam na ordem do clique — O-PARAR-CALA-O-TESTE-QUE-AINDA-ESTAVA-NO-AR-01.

MEDIDO EM 10/10/2026, antes da cura, pela mesma porta que o `Piloto._gesto`
usa (`pacotes.despachar`), com uma thread solta por clique: o «Testar» lento
(o `rumble_set_checked` leva 0,3 s) e o «Parar» clicado 50 ms depois no mesmo
controle terminavam fora de ordem. O «Parar» calava primeiro, o «Testar» voltava
depois e marcava o controle em teste de novo, e o coração rebatia o par até a
janela fechar. A mesma falta de ordem deixava dois gestos que gravam o mesmo
perfil escreverem um por cima do outro.

A cura mora no despachante: os gestos do mesmo `uniq` andam em fila, os que
declaram `grava=` andam em fila, e os de controles diferentes seguem juntos.
Vale para P1 a P4, por cabo e por rádio, porque a chave é o endereço.

Os endereços são da faixa forjada (`aa:bb:cc`).
"""
from __future__ import annotations

import json
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

PAGINA = "05-vibracao.html"
P1 = "aa:bb:cc:00:00:01"
P2 = "aa:bb:cc:00:00:02"
CHAVE_P1 = "aabbcc000001"
CHAVE_P2 = "aabbcc000002"

#: O tempo do `rumble.set` na ponte de mentira: o teto de tela da ponte de
#: verdade é 0,25 s, e o serviço com o laço ocupado gasta o teto inteiro.
DEMORA_DO_SET_S = 0.3


class PonteLenta:
    """A ponte de mentira, com a assinatura de `app/ipc_bridge` e um `rumble.set` lento."""

    def __init__(self) -> None:
        self.trava = threading.Lock()
        self.chamadas: list[tuple[str, str, float]] = []
        self.dentro_do_set: dict[str, float] = {}

    def _anotar(self, metodo: str, uniq: str | None) -> None:
        with self.trava:
            self.chamadas.append((metodo, str(uniq or ""), time.monotonic()))

    def rumble_set_checked(self, weak: int, strong: int, uniq: str | None = None
                           ) -> tuple[bool, str | None]:
        self.dentro_do_set[str(uniq)] = time.monotonic()
        time.sleep(DEMORA_DO_SET_S)
        self._anotar("rumble_set", uniq)
        return True, None

    def rumble_stop_checked(self, uniq: str | None = None) -> tuple[bool, str | None]:
        self._anotar("rumble_stop", uniq)
        return True, None

    def rumble_stop(self, uniq: str | None = None) -> bool:
        self._anotar("rumble_stop", uniq)
        return True

    def rumble_passthrough(self, enabled: bool = True, uniq: str | None = None) -> bool:
        self._anotar("rumble_passthrough", uniq)
        return True

    def haptica_testar(self, uniq: str, ligado: bool) -> tuple[bool, dict[str, Any] | None]:
        self._anotar("haptica_testar", uniq)
        return True, {"status": "ok"}

    def profile_reaplicar(self, nome: str, *, prender: bool = False) -> dict[str, Any]:
        self._anotar("profile_reaplicar", nome)
        return {"active_profile": nome}

    def chamar(self, metodo: str, **_: Any) -> bool:
        self._anotar(metodo, "")
        return True

    def de(self, uniq: str) -> list[str]:
        return [m for m, u, _ in self.chamadas if u == uniq]


def _ctx(ativo: str = "") -> pacotes.Contexto:
    mesa = [{"uniq": u, "pref": f"p{i}", "jogador": i, "nome": "Prova", "cor": "",
             "transporte": t, "via": t, "alvo": True, "mascara": "dualsense"}
            for i, (u, t) in enumerate(((P1, "usb"), (P2, "bt")), start=1)]
    conectados = [{"uniq": u, "connected": True, "player": i, "transport": t, "index": i - 1}
                  for i, (u, t) in enumerate(((P1, "usb"), (P2, "bt")), start=1)]
    state: dict[str, Any] = {"controllers": conectados, "rumble_motor_pct_padrao": 100,
                             "rumble_policy": "balanceado"}
    if ativo:
        state["active_profile"] = ativo
    return pacotes.Contexto(state=state, mesa=mesa, conectados=conectados,
                            estados={}, externos=[])


def _clicar(ctx: pacotes.Contexto, nome: str, o: dict[str, Any], p: Any,
            erros: list[BaseException]) -> threading.Thread:
    """O clique pela porta do `Piloto._gesto`: o despachante, com o gesto registrado."""
    acao = pacotes.gesto_da_pagina(PAGINA, nome)
    assert acao is not None, f"{PAGINA}:{nome} perdeu o dono"

    def trabalhar() -> None:
        try:
            acao(ctx, o, p)
        except BaseException as erro:
            erros.append(erro)

    return pacotes.despachar(PAGINA, nome, o, trabalhar)


@pytest.fixture(autouse=True)
def _mesa_limpa():
    a05.parar_o_teste()
    a05.parar_o_teste_da_haptica()
    yield
    a05.parar_o_teste()
    a05.parar_o_teste_da_haptica()


def test_o_parar_depois_do_testar_lento_cala_o_teste() -> None:
    """«Testar» e, 50 ms depois, «Parar» no mesmo controle: o teste termina calado."""
    p = PonteLenta()
    ctx = _ctx()
    erros: list[BaseException] = []
    testar = _clicar(ctx, "testar", {"uniq": P1}, p, erros)
    time.sleep(0.05)
    parar = _clicar(ctx, "parar", {"uniq": P1}, p, erros)
    for fio in (testar, parar):
        fio.join(5)
        assert not fio.is_alive(), "o gesto não terminou em 5 s"
    assert erros == [], f"os gestos levantaram: {erros!r}"
    assert a05.em_teste() == frozenset(), (
        f"o «Parar» foi clicado depois do «Testar» e o controle ficou em teste: "
        f"{sorted(a05.em_teste())} — o coração rebateria o par até a janela fechar")
    ordem = p.de(P1)
    assert "rumble_stop" in ordem and "rumble_set" in ordem, ordem
    assert ordem.index("rumble_set") < ordem.index("rumble_stop"), (
        f"um `rumble.set` chegou ao serviço depois do `rumble.stop`: {ordem}")


def test_o_testar_de_um_controle_nao_espera_o_do_outro() -> None:
    """P1 e P2 em paralelo: a fila é por endereço, não uma só para a janela."""
    p = PonteLenta()
    ctx = _ctx()
    erros: list[BaseException] = []
    um = _clicar(ctx, "testar", {"uniq": P1}, p, erros)
    outro = _clicar(ctx, "testar", {"uniq": P2}, p, erros)
    for fio in (um, outro):
        fio.join(5)
    assert erros == [], f"os gestos levantaram: {erros!r}"
    assert P1 in p.dentro_do_set and P2 in p.dentro_do_set
    distancia = abs(p.dentro_do_set[P1] - p.dentro_do_set[P2])
    assert distancia < DEMORA_DO_SET_S / 2, (
        f"o «Testar» do P2 esperou o do P1 ({distancia:.2f} s): a fila prendeu "
        "controles diferentes")
    assert a05.em_teste() == frozenset({P1, P2})


def test_dois_gestos_que_gravam_o_mesmo_perfil_guardam_as_duas_mudancas(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Força do P1 e força do P2 no mesmo perfil, clicadas juntas: o disco guarda as duas.

    O disco é o de mentira do `conftest` (o `XDG_CONFIG_HOME` isolado), com o
    `loader` de verdade. A leitura do perfil ganha 0,2 s, o tempo de um disco
    ocupado, e é o que abre a janela entre ler e gravar.
    """
    from hefesto_dualsense4unix.profiles import loader
    from hefesto_dualsense4unix.profiles.schema import Profile

    monkeypatch.setenv(loader.SEED_SKIP_ENV_VAR, "1")
    loader.save_profile(Profile.model_validate(
        {"name": "Bancada", "match": {"type": "criteria"},
         "rumble": {"policy": "balanceado"}}))
    ler_de_verdade = loader.load_profile

    def ler_devagar(nome: str) -> Any:
        prof = ler_de_verdade(nome)
        time.sleep(0.2)
        return prof

    monkeypatch.setattr(loader, "load_profile", ler_devagar)
    p = PonteLenta()
    ctx = _ctx("Bancada")
    erros: list[BaseException] = []
    um = _clicar(ctx, "intensidade", {"uniq": P1, "valor": "30"}, p, erros)
    outro = _clicar(ctx, "intensidade", {"uniq": P2, "valor": "150"}, p, erros)
    for fio in (um, outro):
        fio.join(10)
        assert not fio.is_alive(), "o gesto não terminou em 10 s"
    assert erros == [], f"os gestos levantaram: {erros!r}"
    caminho = next(loader.profiles_dir().glob("*.json"))
    no_disco = json.loads(caminho.read_text())
    controles = no_disco.get("controllers") or {}
    assert CHAVE_P1 in controles and CHAVE_P2 in controles, (
        f"um gesto gravou por cima do outro: o perfil guarda {sorted(controles)}")
