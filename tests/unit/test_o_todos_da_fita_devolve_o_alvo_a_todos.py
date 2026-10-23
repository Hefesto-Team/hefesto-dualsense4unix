#!/usr/bin/env python3
"""O «Todos» da fita devolve as ações a todos os controles — depois de um «só este» na 08.

MEDIDO NO PILOTO em 20/10/2026 (lar de mentira, mesa `p1-usb,p2-bt`): o clique no cartão do P2
mandava `controller.target.set {"index": 1}`, e o clique no «Todos» do alto não mandava nada; a 08
seguia em `gc-p2`. Escolha de 23/10/2026: o «Todos» manda `index: null`, uma vez, pela mesma
ponte dos gestos.

O dublê da ponte GUARDA o alvo como o serviço guarda (`output_target_index` no estado), então a
volta na 08 (`_pref_do_alvo`) é a leitura de verdade e não um valor digitado na régua.

MORDIDAS (cada uma reprova ao menos um teste daqui):
  (i)   tire o `_devolver_o_alvo_a_todos(ctx, ipc)` do ramo `todos` → caem 1, 2, 5 e 6;
  (ii)  troque o `is None` por `False` (chama sempre) → caem 3 e 7;
  (iii) tire o `raise` da recusa → cai o 5;
  (iv)  faça o chip de um controle chamar o serviço → cai o 4.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pytest

RAIZ = Path(__file__).resolve().parents[2]
for _p in (RAIZ / "src", RAIZ / "src/hefesto_dualsense4unix/interface"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

P1 = "aa:bb:cc:00:00:01"
P2 = "aa:bb:cc:00:00:02"
MESA = [
    {"pref": "p1", "jogador": 1, "uniq": P1, "nome": "Cosmic Red", "via": "USB",
     "cor": "cosmic-red", "transporte": "usb"},
    {"pref": "p2", "jogador": 2, "uniq": P2, "nome": "Starlight Blue", "via": "BT",
     "cor": "starlight-blue", "transporte": "bt"},
]
CONTROLES = [{"uniq": P1, "index": 0}, {"uniq": P2, "index": 1}]


class ServicoDeMentira:
    """A ponte e o estado que o serviço guarda: `controller.target.set` muda o alvo."""

    def __init__(self, alvo: int | None, *, aceita: bool = True) -> None:
        self.alvo = alvo
        self.aceita = aceita
        self.pedidos: list[tuple[str, dict[str, Any]]] = []

    def chamar(self, metodo: str, timeout: float | None = None, **params: Any) -> bool:
        self.pedidos.append((metodo, params))
        if not self.aceita:
            return False
        if metodo == "controller.target.set":
            self.alvo = params["index"]
        return True

    def contexto(self) -> Any:
        from hefesto_dualsense4unix.interface import pacotes

        return pacotes.Contexto(
            state={"output_target_index": self.alvo, "controllers": CONTROLES},
            mesa=MESA, conectados=[dict(c) for c in CONTROLES])


@pytest.fixture(scope="module")
def hv() -> Any:
    pytest.importorskip("gi", reason="o piloto precisa do PyGObject do sistema")
    from hefesto_dualsense4unix.interface import hefesto_vivo

    return hefesto_vivo


@pytest.fixture(autouse=True)
def escolha_limpa(hv: Any) -> Any:
    antes = hv.ESCOLHA_DA_FITA.uniq
    hv.ESCOLHA_DA_FITA.uniq = ""
    yield
    hv.ESCOLHA_DA_FITA.uniq = antes


def test_1_o_todos_devolve_o_alvo_depois_de_um_so_este(hv: Any) -> None:
    """«Só este» no P2 (index 1) e depois «Todos»: o serviço recebe `index: null`, uma vez."""
    from hefesto_dualsense4unix.interface.pacotes import a08_conexoes as a08

    servico = ServicoDeMentira(alvo=None)
    a08.alvo(servico.contexto(), {"uniq": P2}, servico)
    assert servico.alvo == 1
    assert a08._pref_do_alvo(servico.contexto()) == "p2"

    hv._escolher_na_fita(servico.contexto(), {"pref": "todos"}, servico)

    assert servico.pedidos == [("controller.target.set", {"index": 1}),
                               ("controller.target.set", {"index": None})]
    assert hv._pref_escolhido(MESA) == "todos"


def test_2_a_08_volta_a_marcar_todos_pela_leitura_do_servico(hv: Any) -> None:
    """O que a 08 lê no tique seguinte: `todos` marcado, e nenhum lugar de controle."""
    from hefesto_dualsense4unix.interface.pacotes import a08_conexoes as a08

    servico = ServicoDeMentira(alvo=1)
    assert a08._alvo_de_saida(servico.contexto()) == ["", "", "sim", "", ""]
    hv._escolher_na_fita(servico.contexto(), {"pref": "todos"}, servico)
    assert a08._pref_do_alvo(servico.contexto()) == a08.TODOS_NA_TELA
    assert a08._alvo_de_saida(servico.contexto()) == ["sim", "", "", "", ""]


def test_3_com_o_alvo_ja_em_todos_nao_ha_o_que_desfazer(hv: Any) -> None:
    """`None` já é «todos»: a chamada em todo clique seria ruído, e o clique não pode fazê-la."""
    servico = ServicoDeMentira(alvo=None)
    hv._escolher_na_fita(servico.contexto(), {"pref": "todos"}, servico)
    assert servico.pedidos == []
    assert hv._pref_escolhido(MESA) == "todos"


def test_4_o_chip_de_um_controle_nao_fala_com_o_servico(hv: Any) -> None:
    """A fita aponta a aba; o alvo do serviço é o «só este» da 08."""
    servico = ServicoDeMentira(alvo=1)
    hv._escolher_na_fita(servico.contexto(), {"pref": "p1"}, servico)
    assert servico.pedidos == []
    assert servico.alvo == 1


def test_5_o_servico_que_recusa_nao_deixa_a_fita_dizer_todos(hv: Any) -> None:
    """Fita em «Todos» com o serviço ainda num controle só seria a tela dizendo duas coisas."""
    servico = ServicoDeMentira(alvo=1, aceita=False)
    with pytest.raises(RuntimeError, match="não devolveu"):
        hv._escolher_na_fita(servico.contexto(), {"pref": "todos"}, servico)
    assert hv.ESCOLHA_DA_FITA.uniq == "", "a recusa não pode ter mexido na escolha"


def test_6_o_gesto_registrado_no_despachante_e_o_que_devolve(hv: Any) -> None:
    """O clique do chip chega por `pacotes.gesto_da_pagina`, em qualquer das dez abas."""
    from hefesto_dualsense4unix.interface import monta, pacotes

    for pagina in ("01-jogar.html", "02-controles.html", "08-conexoes.html"):
        servico = ServicoDeMentira(alvo=0)
        acao = pacotes.gesto_da_pagina(pagina, monta.GESTO_DA_FITA)
        assert acao is not None, pagina
        acao(servico.contexto(), {"pref": "todos"}, servico)
        assert servico.pedidos == [("controller.target.set", {"index": None})], pagina


def test_7_sem_a_chave_o_servico_esta_mudo_e_o_clique_nao_o_chama(hv: Any) -> None:
    """Sem `output_target_index` no estado não se sabe o alvo, e não há com quem falar."""
    from hefesto_dualsense4unix.interface import pacotes

    servico = ServicoDeMentira(alvo=1)
    ctx = pacotes.Contexto(state={}, mesa=MESA, conectados=MESA)
    hv._escolher_na_fita(ctx, {"pref": "todos"}, servico)
    assert servico.pedidos == []
