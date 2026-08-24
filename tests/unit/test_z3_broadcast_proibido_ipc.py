"""BROADCAST-PROIBIDO-01 (24/08/2026) — a invariante do P4 na porta do IPC.

O F4 (23/08) curou a ESCRITA física: `_resolver_escopo` separa "Todos" de
"o alvo sumiu" nos três helpers do backend (`_for_each`, `_for_each_com_key`,
`_for_each_led`). Esta suíte mede o que sobrava DEPOIS da escrita, na camada
do daemon — o achado mais caro da frente Z3 (§2.1(b) da sprint):

* `daemon/ipc_handlers.py::_registrar_em_todos` (chamado por `led.set` e
  `player_leds.set` SEM `uniq`) registrava o override em CADA controle
  CONECTADO sem nunca consultar o seletor — mesmo com um alvo escolhido e
  presente (escrita DUPLA no alvo + vazamento para os outros três) ou
  escolhido e ausente (vazamento puro: os três presentes pintavam a cor do
  jogador que saiu da mesa).
* `_destinos_do_broadcast` (usado por `trigger.set`/`trigger.reset` SEM
  `uniq`) fundia "Todos" com "o alvo sumiu" no MESMO `get_output_target_index()
  is None` — a resposta nomeava os três presentes como destinatários de um
  gatilho que nunca chegou a lugar nenhum.
* `_handle_rumble_set` armava `rumble_active` e chamava `set_rumble`
  incondicionalmente — o `_for_each_com_key` (já curado) escrevia zero, mas o
  handler respondia "ok" e o reassert de 5 Hz insistia num par fantasma.

**O backend é REAL aqui** (mesmo molde do P4): o defeito mora na camada do
IPC handler, que só se revela com o `PyDualSenseController` de verdade por
baixo — um dublê de backend não reproduz a ordem "escrita clássica primeiro,
registro depois" que é o corpo do achado.

**Armadilha do instrumento, medida em §2.1(c) da sprint**: `_Mesa.daemon` é
um `MagicMock()`; `is_native_mode()` nele devolve um mock VERDADEIRO por
padrão, o que faz `_destinos_do_broadcast`/`_handle_rumble_set` saírem cedo
demais para exercitar o código que este arquivo diz medir. Toda classe que
testa a rota clássica de `trigger.set` fixa `mesa.daemon.is_native_mode.
return_value = False` explicitamente.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from tests.unit.test_p4_alvo_ausente_nao_vira_broadcast import _Mesa

pytestmark = pytest.mark.asyncio


@pytest.fixture
def mesa(tmp_path: Path) -> _Mesa:
    m = _Mesa(tmp_path)
    # A armadilha do §2.1(c): sem isto, `is_native_mode()` do MagicMock
    # devolve um mock verdadeiro e as rotas SEM `uniq` saem antes de chegar
    # ao código que este arquivo mede.
    m.daemon.is_native_mode.return_value = False
    return m


# --------------------------------------------------------------------------
# Z3-3 — `_registrar_em_todos` (led.set / player_leds.set SEM uniq)
# --------------------------------------------------------------------------


class TestLedSetRespeitaOSeletor:
    """Reproduz o §2.1(b): a barra dos outros três NÃO muda mais de cor."""

    async def test_alvo_ausente_zero_cor_nos_outros(self, mesa: _Mesa) -> None:
        dois = mesa.uniqs[1]
        await mesa.server._handle_controller_target_set({"index": mesa.indice_de(dois)})
        mesa.desligar(dois)
        mesa.limpar()

        resposta = await mesa.server._handle_led_set({"rgb": [0, 255, 0]})

        assert resposta["aplicado_em"] == [], resposta
        pintados = {u: c for u in mesa.uniqs if (c := mesa.cores_de(u))}
        assert pintados == {}, f"a barra dos outros mudou de cor: {pintados}"

    async def test_alvo_presente_uma_escrita_so_e_so_nele(self, mesa: _Mesa) -> None:
        """A variante PIOR do §2.1(b): não precisa de ninguém sair da mesa —
        o alvo presente recebia DUAS escritas (`set_led` + `_registrar_em_
        todos`) e os outros três recebiam uma que não era deles."""
        dois = mesa.uniqs[1]
        await mesa.server._handle_controller_target_set({"index": mesa.indice_de(dois)})
        mesa.limpar()

        resposta = await mesa.server._handle_led_set({"rgb": [0, 255, 0]})

        assert resposta["aplicado_em"] == [dois], resposta
        assert mesa.cores_de(dois) == [(0, 255, 0)], "escrita dupla no alvo"
        for outro in mesa.uniqs:
            if outro == dois:
                continue
            assert mesa.cores_de(outro) == [], f"{outro} foi pintado sem ser o alvo"

    async def test_todos_continua_byte_identico(self, mesa: _Mesa) -> None:
        """Contra-classe: sem alvo no seletor, os quatro continuam recebendo
        — é o caso para que `_registrar_em_todos` nasceu (BROADCAST-QUE-NAO-
        MENTE-01), e esta frente não o desfaz. Duas escritas por controle são
        o comportamento PRÉ-EXISTENTE e documentado (a clássica pinta AGORA
        via `_desired_default`, a registração garante a cor sobrevivendo ao
        reassert via `_desired_by_uniq`) — não é o defeito desta frente, que é
        o vazamento para quem NÃO é o alvo."""
        await mesa.server._handle_controller_target_set({"index": None})
        mesa.limpar()

        resposta = await mesa.server._handle_led_set({"rgb": [7, 7, 7]})

        assert set(resposta["aplicado_em"]) == set(mesa.uniqs), resposta
        for u in mesa.uniqs:
            cores = mesa.cores_de(u)
            assert cores and all(c == (7, 7, 7) for c in cores), (
                f'"Todos" deixou {u} de fora ou pintou errado: {cores}'
            )


class TestPlayerLedsSetRespeitaOSeletor:
    """NÃO VERIFICADO do §2.4: 'se player_leds.set tem o mesmo furo de
    led.set'. O sítio é o MESMO (`_registrar_em_todos`) — medido agora."""

    async def test_alvo_ausente_zero_player_led_nos_outros(self, mesa: _Mesa) -> None:
        dois = mesa.uniqs[1]
        await mesa.server._handle_controller_target_set({"index": mesa.indice_de(dois)})
        mesa.desligar(dois)
        mesa.limpar()

        bits = [True, False, False, False, False]
        resposta = await mesa.server._handle_led_player_set({"bits": bits})

        assert resposta["aplicado_em"] == [], resposta

    async def test_alvo_presente_player_leds_so_nele(self, mesa: _Mesa) -> None:
        tres = mesa.uniqs[2]
        await mesa.server._handle_controller_target_set({"index": mesa.indice_de(tres)})
        mesa.limpar()

        bits = [False, True, False, False, False]
        resposta = await mesa.server._handle_led_player_set({"bits": bits})

        assert resposta["aplicado_em"] == [tres], resposta


# --------------------------------------------------------------------------
# Z3-4 — `_destinos_do_broadcast` (trigger.set / trigger.reset SEM uniq)
# --------------------------------------------------------------------------


class TestTriggerSetParaDeNomearQuemNaoRecebeu:
    """Reproduz o §2.1(c): a resposta honesta estava no log e era
    descartada na volta."""

    async def test_alvo_ausente_aplicado_vazio_guardado_no_alvo(self, mesa: _Mesa) -> None:
        dois = mesa.uniqs[1]
        await mesa.server._handle_controller_target_set({"index": mesa.indice_de(dois)})
        mesa.desligar(dois)

        resposta = await mesa.server._handle_trigger_set(
            {"side": "left", "mode": "Rigid", "params": [0, 128]}
        )

        assert resposta["aplicado_em"] == [], resposta
        assert resposta["guardado_em"] == [dois], resposta

    async def test_alvo_presente_aplicado_em_um_so(self, mesa: _Mesa) -> None:
        tres = mesa.uniqs[2]
        await mesa.server._handle_controller_target_set({"index": mesa.indice_de(tres)})

        resposta = await mesa.server._handle_trigger_set(
            {"side": "right", "mode": "Rigid", "params": [0, 64]}
        )

        assert resposta["aplicado_em"] == [tres], resposta
        assert resposta["guardado_em"] == [], resposta

    async def test_todos_continua_a_mesa_inteira(self, mesa: _Mesa) -> None:
        await mesa.server._handle_controller_target_set({"index": None})

        resposta = await mesa.server._handle_trigger_set(
            {"side": "left", "mode": "Rigid", "params": [0, 200]}
        )

        assert set(resposta["aplicado_em"]) == set(mesa.uniqs), resposta
        assert resposta["guardado_em"] == [], resposta

    async def test_modo_nativo_nao_afirma_nada(self, mesa: _Mesa) -> None:
        """Contra-classe: a ressalva de Modo Nativo do método (§ docstring)
        não pode ser derrubada pela consulta nova ao alvo ausente."""
        dois = mesa.uniqs[1]
        await mesa.server._handle_controller_target_set({"index": mesa.indice_de(dois)})
        mesa.desligar(dois)
        mesa.daemon.is_native_mode.return_value = True

        resposta = await mesa.server._handle_trigger_set(
            {"side": "left", "mode": "Rigid", "params": [0, 128]}
        )

        assert resposta["aplicado_em"] == [], resposta
        assert resposta["guardado_em"] == [], resposta


# --------------------------------------------------------------------------
# Z3-5 — rumble.set recusa antes de escrever, com alvo ausente
# --------------------------------------------------------------------------


class TestRumbleSetRecusaComAlvoAusente:
    async def test_recusa_e_zero_escrita(self, mesa: _Mesa) -> None:
        dois = mesa.uniqs[1]
        await mesa.server._handle_controller_target_set({"index": mesa.indice_de(dois)})
        mesa.desligar(dois)
        mesa.limpar()

        resposta = await mesa.server._handle_rumble_set({"weak": 160, "strong": 220})

        assert resposta["status"] == "recusado", resposta
        assert resposta["desfecho"] == "recusado_alvo_ausente", resposta
        assert isinstance(resposta.get("motivo"), str) and resposta["motivo"], resposta
        recebeu = mesa.quem_recebeu_motor()
        assert recebeu == {}, f"recusou e mesmo assim escreveu: {recebeu}"
        # A recusa não pode armar o par no daemon.config — senão o poll loop
        # de 5 Hz reafirma um pedido que foi recusado (mesma disciplina do
        # NATIVO-RUMBLE-01).
        assert mesa.config.rumble_active is None, (
            "rumble_active foi armado apesar da recusa"
        )

    async def test_alvo_presente_continua_aplicando(self, mesa: _Mesa) -> None:
        """Contra-classe: com o alvo presente, `rumble.set` continua "ok"."""
        tres = mesa.uniqs[2]
        await mesa.server._handle_controller_target_set({"index": mesa.indice_de(tres)})
        mesa.limpar()

        resposta = await mesa.server._handle_rumble_set({"weak": 90, "strong": 90})

        assert resposta["status"] == "ok", resposta
        assert mesa.motores_de(tres) == [("left", 90), ("right", 90)]

    async def test_todos_continua_aplicando(self, mesa: _Mesa) -> None:
        """Contra-classe: sem alvo no seletor, `rumble.set` continua "ok"."""
        await mesa.server._handle_controller_target_set({"index": None})
        mesa.limpar()

        resposta = await mesa.server._handle_rumble_set({"weak": 50, "strong": 50})

        assert resposta["status"] == "ok", resposta
        for u in mesa.uniqs:
            assert mesa.motores_de(u) == [("left", 50), ("right", 50)]
