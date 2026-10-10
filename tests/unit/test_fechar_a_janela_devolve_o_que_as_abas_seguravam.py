"""Fechar a janela devolve o que as abas seguravam.

A sprint: FECHAR-A-JANELA-DEVOLVE-O-QUE-AS-ABAS-SEGURAVAM-01.

MEDIDO EM 10/10/2026, antes da cura: `pacotes.largar_o_que_as_abas_seguram`
tinha três chamadores no piloto (a troca de página no `_carregou`, o `_ir` e o
`_relatar`), e nenhum é o fim da janela do produto. O X da janela liga
`destroy` direto em `Gtk.main_quit` (`interface/janela.py`), e depois do
`Gtk.main()` o `_o_processo_da_janela` só desligava a leitura do perfil. O
teste de vibração e o da háptica de qualquer controle seguiam no ar até o teto
do serviço, e o `rumble_passthrough` nunca voltava pelo caminho do «Parar».

A régua entra e sai do `_o_processo_da_janela` sem o GTK, com dois controles no
teste da vibração e um no da háptica, e exige a devolução de cada um. O
`finally` é o ponto por onde todo fim da janela passa: o X, o `agendar_saida`
e o `_morrer`.
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

exigir_gi_real("importa `interface.hefesto_vivo`, que carrega o GTK")

from hefesto_dualsense4unix.interface import hefesto_vivo as hv
from hefesto_dualsense4unix.interface import pacotes
from hefesto_dualsense4unix.interface.pacotes import a05_vibracao as a05

P1 = "aa:bb:cc:00:00:01"
P2 = "02:fe:00:00:00:02"
P3 = "aa:bb:cc:00:00:03"


class PonteQueAnota:
    """A ponte de mentira, com a assinatura de `app/ipc_bridge` (nada mais frouxo)."""

    def __init__(self) -> None:
        self.chamadas: list[tuple[str, tuple[Any, ...]]] = []

    def rumble_stop(self, uniq: str | None = None) -> bool:
        self.chamadas.append(("rumble_stop", (uniq,)))
        return True

    def rumble_passthrough(self, enabled: bool = True, uniq: str | None = None) -> bool:
        self.chamadas.append(("rumble_passthrough", (enabled, uniq)))
        return True

    def haptica_testar(self, uniq: str, ligado: bool) -> tuple[bool, dict[str, Any] | None]:
        self.chamadas.append(("haptica_testar", (uniq, ligado)))
        return True, {"status": "ok"}


@pytest.fixture(autouse=True)
def _mesa_limpa():
    """Nenhum caso herda as marcas do anterior: a suíte roda no MESMO processo."""
    a05.parar_o_teste()
    a05.parar_o_teste_da_haptica()
    yield
    a05.parar_o_teste()
    a05.parar_o_teste_da_haptica()


def test_sair_da_janela_devolve_cada_controle_em_teste(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Dois na vibração e um na háptica: cada um volta ao jogo, pelo endereço dele."""
    ponte = PonteQueAnota()
    monkeypatch.setattr(hv, "ponte", ponte)
    a05._EM_TESTE.update({P1, P2})
    a05._EM_TESTE_DA_HAPTICA.add(P3)

    with hv._o_processo_da_janela():
        assert ponte.chamadas == [], "a janela largou antes de sair"

    for uniq in (P1, P2):
        assert ("rumble_stop", (uniq,)) in ponte.chamadas, (
            f"fechar a janela não parou os motores de {uniq}: {ponte.chamadas}")
        assert ("rumble_passthrough", (True, uniq)) in ponte.chamadas, (
            f"fechar a janela não devolveu a vibração de {uniq} ao jogo: "
            f"{ponte.chamadas}")
        parou = ponte.chamadas.index(("rumble_stop", (uniq,)))
        devolveu = ponte.chamadas.index(("rumble_passthrough", (True, uniq)))
        assert parou < devolveu, "o passthrough veio antes do stop: o par fixo cala o jogo"
    assert ("haptica_testar", (P3, False)) in ponte.chamadas, (
        f"fechar a janela não calou o teste da háptica de {P3}: {ponte.chamadas}")
    assert a05.em_teste() == frozenset()
    assert a05.em_teste_da_haptica() == frozenset()


def test_sair_da_janela_por_erro_tambem_devolve(monkeypatch: pytest.MonkeyPatch) -> None:
    """A janela que cai com exceção passa pelo mesmo `finally`."""
    ponte = PonteQueAnota()
    monkeypatch.setattr(hv, "ponte", ponte)
    a05._EM_TESTE.add(P1)

    with pytest.raises(RuntimeError), hv._o_processo_da_janela():
        raise RuntimeError("a janela caiu")

    assert ("rumble_passthrough", (True, P1)) in ponte.chamadas


def test_sair_sem_teste_ligado_nao_fala_com_o_servico(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Fechar a janela sem teste no ar não mexe na vibração do jogo."""
    ponte = PonteQueAnota()
    monkeypatch.setattr(hv, "ponte", ponte)
    with hv._o_processo_da_janela():
        pass
    assert ponte.chamadas == []


# A LARGADA ANDA NA FILA DE CADA CONTROLE (10/10/2026, conferência do conjunto):
# ela é o «Parar» de todos, e o que ainda está no ar naquele controle termina
# antes dela. Medido antes desta cura, com o `rumble.set` da ponte levando 0,3 s:
# o «Testar» deixado na troca de página marcava o controle em teste DEPOIS da
# largada (o coração o rebatia na aba seguinte, até ela voltar e clicar), e o
# batimento já conferido mandava o par depois do `rumble.stop` da largada.

DEMORA_DO_SET_S = 0.3


class PonteLenta(PonteQueAnota):
    """A mesma ponte, com o `rumble.set` gastando o prazo como o serviço ocupado."""

    def rumble_set_checked(self, weak: int, strong: int, uniq: str | None = None
                           ) -> tuple[bool, str | None]:
        time.sleep(DEMORA_DO_SET_S)
        self.chamadas.append(("rumble_set", (uniq,)))
        return True, None

    def rumble_stop_checked(self, uniq: str | None = None) -> tuple[bool, str | None]:
        self.chamadas.append(("rumble_stop", (uniq,)))
        return True, None


def _ctx() -> pacotes.Contexto:
    mesa = [{"uniq": P1, "pref": "p1", "jogador": 1, "nome": "Prova", "cor": "",
             "transporte": "bt", "via": "bt", "alvo": True, "mascara": "dualsense"}]
    conectados = [{"uniq": P1, "connected": True, "player": 1, "transport": "bt",
                   "index": 0}]
    return pacotes.Contexto(
        state={"controllers": conectados, "rumble_motor_pct_padrao": 100},
        mesa=mesa, conectados=conectados, estados={}, externos=[])


def _testar_pela_porta_do_clique(p: Any) -> threading.Thread:
    """O «Testar» do P1 pela porta do `Piloto._gesto`: o despachante."""
    acao = pacotes.gesto_da_pagina("05-vibracao.html", "testar")
    assert acao is not None
    ctx = _ctx()
    return pacotes.despachar("05-vibracao.html", "testar", {"uniq": P1},
                             lambda: acao(ctx, {"uniq": P1}, p))


def _esperar(*fios: threading.Thread | None) -> None:
    for fio in fios:
        if fio is not None:
            fio.join(5)
            assert not fio.is_alive(), "a fila não andou em 5 s"


def test_a_troca_de_pagina_larga_o_testar_que_ainda_estava_no_ar() -> None:
    """«Testar» lento e a troca de página logo atrás: o controle termina fora do teste."""
    ponte = PonteLenta()
    testar = _testar_pela_porta_do_clique(ponte)
    time.sleep(0.05)
    largada = pacotes.largar_o_que_as_abas_seguram(ponte)
    _esperar(testar, largada)
    assert a05.em_teste() == frozenset(), (
        "a largada da troca de página passou à frente do «Testar» no ar, e o "
        f"controle ficou em teste: {sorted(a05.em_teste())} — o coração o rebate "
        "na aba seguinte")
    assert ("rumble_passthrough", (True, P1)) in ponte.chamadas, ponte.chamadas


def test_a_saida_da_janela_espera_o_testar_que_ainda_estava_no_ar(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Fechar a janela com um «Testar» no ar: ele termina, e a largada o devolve."""
    ponte = PonteLenta()
    monkeypatch.setattr(hv, "ponte", ponte)
    with hv._o_processo_da_janela():
        testar = _testar_pela_porta_do_clique(ponte)
        time.sleep(0.05)
    # Lido na SAÍDA, antes de esperar qualquer fio: depois do `finally` o
    # processo acaba, e um fio de largada que ainda não rodou morre com ele.
    nomes = [n for n, _ in ponte.chamadas]
    assert nomes[-2:] == ["rumble_stop", "rumble_passthrough"], (
        f"a saída da janela não esperou a largada atrás do «Testar»: {nomes}")
    _esperar(testar)
    assert a05.em_teste() == frozenset(), sorted(a05.em_teste())


def test_a_largada_nao_passa_a_frente_do_batimento_no_ar() -> None:
    """O batimento conferido sai antes da largada, e o `rumble.stop` é o último."""
    ponte = PonteLenta()
    a05._EM_TESTE.add(P1)
    pacotes.bater_os_coracoes(_ctx(), ponte)
    largada = pacotes.largar_o_que_as_abas_seguram(ponte)
    _esperar(largada)
    nomes = [n for n, _ in ponte.chamadas]
    assert nomes == ["rumble_set", "rumble_stop", "rumble_passthrough"], (
        f"a largada cruzou o batimento no ar: {nomes} — o par chega ao serviço "
        "depois do `rumble.stop` e o motor fica ligado até o teto")
