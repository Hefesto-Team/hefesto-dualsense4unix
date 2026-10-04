"""A-VIBRACAO-E-A-HAPTICA-DE-CADA-CONTROLE-SAO-INDEPENDENTES-01 — o serviço e a aba.

Ela, 03/10/2026, validando a leva 1: *«vibração e háptico é por cada controle e
precisam funcionar em independente. hoje se eu clico em um o outro controle para
de ter o efeito.»* O serviço guardava UM par fixado para a mesa inteira
(`rumble_active`), e a aba mirava o serviço inteiro no controle clicado
(`controller.target.set`): o «Testar» do P2 abandonava o P1.

Duas metades, e cada uma tem a sua régua:

1. o DAEMON guarda um par por controle (`pares_fixados`), e o «Parar» de um
   (`rumble.stop {uniq}`) não toca no outro;
2. a ABA não mira mais o seletor global, e o teste da vibração e o da háptica
   são marcas por controle.

AS MORDIDAS (executadas na implementação):

* volte o par a um só (`fixar_par` apagando os outros donos mesmo com
  `so_este=True`) → `test_os_dois_pares_ficam_no_servico` e
  `test_o_parar_de_um_deixa_o_outro_tremendo` reprovam;
* tire o `uniq` do `rumble_stop_checked` do gesto `parar` →
  `test_o_parar_da_aba_leva_o_controle` reprova;
* volte a marca da aba a um `uniq` só (o `testar` limpando as outras) →
  `test_na_aba_os_dois_testes_ficam_ligados` reprova.
"""
from __future__ import annotations

import pathlib
import sys
from typing import Any

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(RAIZ / "src/hefesto_dualsense4unix/interface"))

from hefesto_dualsense4unix.daemon.subsystems.rumble import (
    pares_fixados,
    reassert_rumble,
)
from tests.unit.test_mesa_cheia_05_o_rumble_mira import _Mesa


@pytest.fixture
def mesa(tmp_path: Any) -> _Mesa:
    return _Mesa(tmp_path)


async def _testar(mesa: _Mesa, uniq: str, weak: int, strong: int) -> dict[str, Any]:
    return await mesa.server._handle_rumble_set(
        {"weak": weak, "strong": strong, "uniq": uniq}
    )


@pytest.mark.asyncio
async def test_os_dois_pares_ficam_no_servico(mesa: _Mesa) -> None:
    p1, p2 = mesa.uniqs[0], mesa.uniqs[1]
    assert (await _testar(mesa, p1, 160, 220))["status"] == "ok"
    assert (await _testar(mesa, p2, 100, 50))["status"] == "ok"

    fixados = pares_fixados(mesa.config)
    assert {u: (w, s) for u, (w, s, _em) in fixados.items()} == {
        p1: (160, 220), p2: (100, 50),
    }, "o par do P1 saiu do serviço quando o P2 fixou o dele"
    # o seletor global não foi tocado: nenhum dos dois gestos mirou o serviço
    assert mesa.backend.get_output_target_uniq() is None


@pytest.mark.asyncio
async def test_o_parar_de_um_deixa_o_outro_tremendo(mesa: _Mesa) -> None:
    p1, p2 = mesa.uniqs[0], mesa.uniqs[1]
    await _testar(mesa, p1, 160, 220)
    await _testar(mesa, p2, 100, 50)

    resposta = await mesa.server._handle_rumble_stop({"uniq": p1})
    assert resposta["status"] == "ok"
    mesa.limpar_motores()
    mesa.ticks(4)

    assert not any(v for _lado, v in mesa.motores_de(p1)), (
        "o P1 seguiu tremendo depois do Parar dele"
    )
    assert mesa.motores_de(p2) == [("left", 50), ("right", 100)] * 4, (
        "o «Parar» do P1 calou o P2, que o teste dele ainda segurava"
    )


@pytest.mark.asyncio
async def test_devolver_um_ao_jogo_nao_solta_o_outro(mesa: _Mesa) -> None:
    p1, p2 = mesa.uniqs[0], mesa.uniqs[1]
    await _testar(mesa, p1, 160, 220)
    await _testar(mesa, p2, 100, 50)
    await mesa.server._handle_rumble_stop({"uniq": p1})
    await mesa.server._handle_rumble_passthrough({"enabled": True, "uniq": p1})

    assert set(pares_fixados(mesa.config)) == {p2}
    assert mesa.config.rumble_active == (100, 50), "o resumo não seguiu o par que sobrou"
    await mesa.server._handle_rumble_passthrough({"enabled": True, "uniq": p2})
    assert pares_fixados(mesa.config) == {}
    assert mesa.config.rumble_active is None, "sem par nenhum, o jogo volta a mandar"


@pytest.mark.asyncio
async def test_a_ociosidade_solta_so_o_controle_que_ninguem_rebate(mesa: _Mesa) -> None:
    p1, p2 = mesa.uniqs[0], mesa.uniqs[1]
    await _testar(mesa, p1, 160, 220)
    await _testar(mesa, p2, 100, 50)
    fixados = pares_fixados(mesa.config)
    w, s, _em = fixados[p1]
    fixados[p1] = (w, s, 0.0)         # o P1 deixou de ser rebatido há muito tempo
    w, s, _em = fixados[p2]
    fixados[p2] = (w, s, 1000.0)      # o P2 acaba de ser rebatido
    reassert_rumble(mesa.daemon, 1001.0)
    assert set(pares_fixados(mesa.config)) == {p2}


@pytest.mark.asyncio
async def test_controle_fora_da_mesa_recusa_e_nao_arma_nada(mesa: _Mesa) -> None:
    resposta = await _testar(mesa, "aa:bb:cc:00:00:99", 160, 220)
    assert resposta["status"] == "recusado"
    assert pares_fixados(mesa.config) == {}
    assert mesa.config.rumble_active is None


@pytest.mark.asyncio
async def test_o_gesto_sem_controle_continua_sendo_o_par_da_mesa(mesa: _Mesa) -> None:
    """A CLI e o «Aplicar» não mudam: um par só, e o dono antigo é abandonado."""
    p1, p2 = mesa.uniqs[0], mesa.uniqs[1]
    await _testar(mesa, p1, 160, 220)
    await mesa.server._handle_controller_target_set({"index": mesa.indice_de(p2)})
    await mesa.server._handle_rumble_set({"weak": 30, "strong": 40})
    assert set(pares_fixados(mesa.config)) == {p2}, (
        "o par sem controle devia substituir os outros, como era"
    )
    mesa.limpar_motores()
    mesa.ticks(2)
    assert not any(v for _lado, v in mesa.motores_de(p1)), "o P1 seguiu tremendo"


# --- a aba -------------------------------------------------------------------
P1 = "aa:bb:cc:00:00:01"
P2 = "aa:bb:cc:00:00:02"


class _Ponte:
    """A ponte de mentira: guarda cada pedido, com o endereço que ele levou."""

    def __init__(self) -> None:
        self.chamadas: list[tuple[str, tuple[Any, ...], dict[str, Any]]] = []

    def chamar(self, metodo: str, **k: Any) -> bool:
        self.chamadas.append(("chamar", (metodo,), k))
        return True

    def __getattr__(self, nome: str) -> Any:
        def registrar(*a: Any, **k: Any) -> Any:
            self.chamadas.append((nome, a, k))
            if nome == "haptica_testar":
                return True, {"status": "ok"}
            return (True, None) if nome.endswith("_checked") else True

        return registrar


@pytest.fixture
def aba() -> Any:
    import pacotes
    from pacotes import a05_vibracao

    a05_vibracao.parar_o_teste()
    a05_vibracao.parar_o_teste_da_haptica()
    yield pacotes, a05_vibracao
    a05_vibracao.parar_o_teste()
    a05_vibracao.parar_o_teste_da_haptica()


def _ctx(pacotes: Any) -> Any:
    return pacotes.Contexto(
        state={"active_profile": "Bancada", "rumble_policy": "balanceado",
               "rumble_ff": {}},
        mesa=[{"pref": "p1", "jogador": 1, "uniq": P1, "nome": "P1", "via": "USB",
               "cor": "starlight-blue"},
              {"pref": "p2", "jogador": 2, "uniq": P2, "nome": "P2", "via": "BT",
               "cor": "midnight-black"}],
        conectados=[{"uniq": P1, "connected": True, "transport": "usb", "index": 0,
                     "player": 1},
                    {"uniq": P2, "connected": True, "transport": "bt", "index": 1,
                     "player": 2}],
        estados={})


def _clicar(aba: Any, gesto: str, uniq: str, ponte: _Ponte) -> None:
    pacotes, _a05 = aba
    pacotes.gesto_da_pagina("05-vibracao.html", gesto)(
        _ctx(pacotes), {"uniq": uniq, "controle": "p1"}, ponte)


def test_na_aba_os_dois_testes_ficam_ligados(aba: Any) -> None:
    """O «Testar» do P2 não encerra o do P1. MORDIDA: o `testar` limpando as
    outras marcas (um `uniq` só) reprova aqui."""
    _pacotes, a05 = aba
    ponte = _Ponte()
    _clicar(aba, "testar", P1, ponte)
    _clicar(aba, "testar", P2, ponte)
    assert a05.em_teste() == {P1, P2}
    enderecos = [k.get("uniq") for n, _a, k in ponte.chamadas if n == "rumble_set_checked"]
    assert enderecos == [P1, P2], f"os pedidos não levaram o controle: {enderecos}"


def test_a_aba_nao_mira_o_seletor_global(aba: Any) -> None:
    """O serviço inteiro não segue mais o último clique."""
    ponte = _Ponte()
    _clicar(aba, "testar", P1, ponte)
    _clicar(aba, "parar", P1, ponte)
    assert not any(n == "chamar" for n, _a, _k in ponte.chamadas), (
        "a aba voltou a mirar o seletor global (`controller.target.set`)"
    )


def test_o_parar_da_aba_leva_o_controle(aba: Any) -> None:
    """O «Parar» do P1 pede ao serviço só o P1. MORDIDA: tire o `uniq` do
    `rumble_stop_checked` do gesto `parar` → reprova."""
    _pacotes, a05 = aba
    ponte = _Ponte()
    _clicar(aba, "testar", P1, ponte)
    _clicar(aba, "testar", P2, ponte)
    ponte.chamadas.clear()
    _clicar(aba, "parar", P1, ponte)
    pedidos = {n: k.get("uniq") for n, _a, k in ponte.chamadas}
    assert pedidos == {"rumble_stop_checked": P1, "rumble_passthrough": P1}, pedidos
    assert a05.em_teste() == {P2}, "o Parar do P1 apagou a marca do P2"


def test_o_coracao_rebate_cada_teste_com_o_endereco_dele(aba: Any) -> None:
    pacotes, a05 = aba
    ponte = _Ponte()
    _clicar(aba, "testar", P1, ponte)
    _clicar(aba, "testar", P2, ponte)
    ponte.chamadas.clear()
    a05._bater_o_coracao_do_teste(_ctx(pacotes), ponte)
    enderecos = sorted(k.get("uniq") for n, _a, k in ponte.chamadas
                       if n == "rumble_set_checked")
    assert enderecos == [P1, P2], "um dos testes deixou de ser rebatido"


def test_a_haptica_dos_dois_controles_fica_ligada(aba: Any) -> None:
    """O mesmo para a háptica: o do P2 não cala o do P1, e o «Parar» é de cada um."""
    _pacotes, a05 = aba
    ponte = _Ponte()
    _clicar(aba, "testar-haptica", P1, ponte)
    _clicar(aba, "testar-haptica", P2, ponte)
    assert a05.em_teste_da_haptica() == {P1, P2}
    assert not any(n == "haptica_testar" and a[1] is False and a[0] == P1
                   for n, a, _k in ponte.chamadas), "o P2 calou a háptica do P1"
    ponte.chamadas.clear()
    _clicar(aba, "parar", P1, ponte)
    assert a05.em_teste_da_haptica() == {P2}


@pytest.mark.asyncio
async def test_o_resumo_solto_de_fora_nao_ressuscita_o_par_velho(mesa: _Mesa) -> None:
    """A troca de perfil e o Modo Nativo soltam o resumo direto (`rumble_active =
    None`, `daemon/lifecycle.py`). O par de antes não volta com o próximo pedido,
    nem no vão de 200 ms antes do tique que limparia o registro. MORDIDA: tire a
    limpeza do começo de `fixar_par` → o P2 volta a tremer aqui."""
    p1, p2 = mesa.uniqs[0], mesa.uniqs[1]
    await _testar(mesa, p1, 160, 220)
    await _testar(mesa, p2, 100, 50)
    mesa.config.rumble_active = None          # o que o lifecycle faz
    mesa.config.rumble_active_uniq = None
    await _testar(mesa, p1, 30, 40)           # o batimento do P1, antes do tique

    assert set(pares_fixados(mesa.config)) == {p1}, (
        "o par do P2, solto pela troca de perfil, voltou junto com o do P1"
    )
    mesa.limpar_motores()
    mesa.ticks(2)
    assert not any(v for _lado, v in mesa.motores_de(p2)), "o P2 voltou a tremer"
