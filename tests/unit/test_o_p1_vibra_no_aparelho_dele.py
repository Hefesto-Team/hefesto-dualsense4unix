"""O P1 vibra no aparelho dele, como os outros (O-P1-VIBRA-NO-APARELHO-DELE-COMO-OS-OUTROS-01).

A régua das sequências do dono do posto de P1: dois controles, o pad 1 (o do
posto, cujo sink lê o dono a cada pedido) e o pad 2 (o do jogador do co-op,
preso à identidade dele). Em cada passo, cada pedido de vibração de cada pad
tem de chegar a UM aparelho, o que dirige aquele pad, ou a nenhum quando
ninguém o dirige (a vaga descarta com log, sem broadcast).

O lado do P1 é coerente: entrada e vibração do pad 1 seguem o mesmo dono.
O que diverge mora no co-op (fora desta posse): o jogador que cedeu o
aparelho ao posto de P1 ainda fala com ele até ser recolhido. Os dois casos
ficam em ``xfail(strict=True)`` até a cura, que é de
`O-PAD-CEDIDO-AO-P1-NAO-FALA-COM-O-APARELHO-QUE-CEDEU-01`.

O `FakeController` da casa não tem a API por endereço; o dublê aqui é a mesa
de mentira com ``set_rumble_for`` por MAC, como a de `test_vpad_ff_passthrough.py`.
"""
from __future__ import annotations

from collections.abc import Callable
from types import SimpleNamespace
from typing import Any

import pytest

from hefesto_dualsense4unix.daemon.subsystems import gamepad as gp_mod
from hefesto_dualsense4unix.daemon.subsystems.coop import CoopManager

P1 = "aabbcc000041"
P2 = "aabbcc000042"
RAZAO = (
    "o jogador que cedeu o aparelho ao posto de P1 ainda fala com ele até ser "
    "recolhido; a cura é do co-op: O-PAD-CEDIDO-AO-P1-NAO-FALA-COM-O-APARELHO-QUE-CEDEU-01"
)


class Mesa:
    """O backend de mentira: quem está plugado, o dono do posto e cada escrita."""

    def __init__(self) -> None:
        self.plugados = {P1, P2}
        self.primary_uniq: str | None = P1
        self.escritas: list[tuple[str | None, int, int]] = []
        self.paradas: list[str | None] = []
        self._observador: Callable[[str | None, str | None], None] | None = None

    def set_rumble_for(self, uniq: str, weak: int, strong: int) -> bool:
        if uniq not in self.plugados:
            return False
        self.escritas.append((uniq, weak, strong))
        return True

    def set_rumble(self, weak: int, strong: int) -> None:
        self.escritas.append((None, weak, strong))

    def force_rumble_stop(self, uniq: str | None = None) -> None:
        self.paradas.append(uniq)

    def set_primary_change_observer(self, fn: Any) -> None:
        self._observador = fn

    def sai(self, uniq: str) -> None:
        """O controle cai. Dentro do prazo o posto fica vago e ESPERA por ele."""
        self.plugados.discard(uniq)

    def volta(self, uniq: str) -> None:
        self.plugados.add(uniq)

    def passa_o_posto(self, novo: str) -> None:
        """O prazo passou: o posto vai a ``novo``, avisando antes do retarget."""
        anterior = self.primary_uniq
        if self._observador is not None:
            self._observador(anterior, novo)
        self.primary_uniq = novo


class Jogo:
    def __init__(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self.mesa = Mesa()
        self.daemon = SimpleNamespace(
            config=SimpleNamespace(
                rumble_active=None, rumble_policy="balanceado", rumble_policy_custom_mult=0.7
            ),
            controller=self.mesa,
            store=SimpleNamespace(
                snapshot=lambda: SimpleNamespace(controller=SimpleNamespace(battery_pct=80))
            ),
            _last_auto_mult=0.7,
            _last_auto_change_at=0.0,
            _gamepad_device=None,
        )
        self.coop = CoopManager(self.daemon)
        for nome in (
            "_broker_restore_player",
            "_levantar",
            "_revert_single_player_led",
            "_materialize_launch_env",
        ):
            monkeypatch.setattr(self.coop, nome, lambda *_a, **_k: None)
        monkeypatch.setattr(self.coop, "numero_do_diario", lambda _i, indice: indice)
        self.mesa.set_primary_change_observer(self.coop.ceder_ao_primario)
        self.pad1 = gp_mod.make_primary_rumble_sink(self.daemon)
        self.pads = {1: self.pad1}
        self.dono_do_pad: dict[int, str] = {}
        self.senta(P2, 2)

    def senta(self, uniq: str, pad: int) -> None:
        """O co-op senta ``uniq`` num pad dele (o `_spawn_player`, sem nó de verdade)."""
        sink = self.coop._make_player_rumble_sink(uniq)
        self.pads[pad] = sink
        self.coop._players[uniq] = SimpleNamespace(
            identity=uniq,
            player_index=pad - 1,
            vpad=SimpleNamespace(backend="uhid", stop=lambda: sink(0, 0)),
            reader=SimpleNamespace(set_grab=lambda _v: None, stop=lambda: None),
            motion_reader=None,
            cedido_ao_primario=False,
        )
        self.dono_do_pad[pad] = uniq

    def quem_dirige(self, pad: int) -> str | None:
        """O aparelho cuja entrada vai a este pad agora (o que o jogo lê dele)."""
        if pad == 1:
            dono = self.mesa.primary_uniq
            return dono if dono in self.mesa.plugados else None
        uniq = self.dono_do_pad.get(pad)
        jogador = self.coop._players.get(uniq) if uniq else None
        if jogador is None or jogador.cedido_ao_primario or uniq not in self.mesa.plugados:
            return None
        return uniq

    def pede(self, pad: int, weak: int = 120, strong: int = 200) -> list[str | None]:
        antes = len(self.mesa.escritas)
        self.pads[pad](weak, strong)
        return [uniq for uniq, _w, _s in self.mesa.escritas[antes:]]

    def confere(self, *pads: int) -> None:
        for pad in pads:
            dono = self.quem_dirige(pad)
            destinos = self.pede(pad)
            esperado = [dono] if dono is not None else []
            assert destinos == esperado, (
                f"o pedido do pad {pad} foi a {destinos}; quem o dirige é {dono}"
            )


@pytest.fixture
def jogo(monkeypatch: pytest.MonkeyPatch) -> Jogo:
    return Jogo(monkeypatch)


def test_a_mesa_de_dois_cada_pad_vibra_quem_o_dirige(jogo: Jogo) -> None:
    jogo.confere(1, 2)
    assert [uniq for uniq, _w, _s in jogo.mesa.escritas] == [P1, P2]


def test_o_p1_que_sai_dentro_do_prazo_deixa_o_pad_1_mudo_sem_broadcast(jogo: Jogo) -> None:
    jogo.mesa.sai(P1)
    assert jogo.pede(1) == [], "a vibração do pad 1 vazou para outro controle na vaga"
    jogo.confere(2)


def test_o_p1_que_volta_dentro_do_prazo_retoma_a_vibracao_do_pad_1(jogo: Jogo) -> None:
    jogo.mesa.sai(P1)
    jogo.pede(1)
    jogo.mesa.volta(P1)
    jogo.confere(1, 2)


def test_passado_o_prazo_o_pad_1_vibra_o_novo_dono_do_posto(jogo: Jogo) -> None:
    jogo.mesa.sai(P1)
    jogo.mesa.passa_o_posto(P2)
    assert jogo.quem_dirige(1) == P2
    jogo.confere(1)


def test_o_p1_que_volta_depois_do_prazo_vibra_pelo_pad_dele(jogo: Jogo) -> None:
    jogo.mesa.sai(P1)
    jogo.mesa.passa_o_posto(P2)
    jogo.coop._recolher_os_cedidos()
    jogo.mesa.volta(P1)
    jogo.senta(P1, 3)
    jogo.confere(1, 3)
    assert jogo.pede(1) == [P2] and jogo.pede(3) == [P1]


@pytest.mark.xfail(strict=True, reason=RAZAO)
def test_o_pad_2_cedido_nao_vibra_o_aparelho_que_agora_e_o_p1(jogo: Jogo) -> None:
    jogo.mesa.sai(P1)
    jogo.mesa.passa_o_posto(P2)
    # Entre o aviso da troca e o recolhimento no tique seguinte, o pad 2 segue
    # aberto no jogo; ninguém o dirige mais, e o pedido dele não tem dono.
    jogo.confere(2)


@pytest.mark.xfail(strict=True, reason=RAZAO)
def test_recolher_o_pad_2_cedido_nao_cala_o_motor_do_p1(jogo: Jogo) -> None:
    jogo.mesa.sai(P1)
    jogo.mesa.passa_o_posto(P2)
    assert jogo.pede(1) == [P2]
    antes = len(jogo.mesa.escritas)
    jogo.coop._recolher_os_cedidos()
    assert jogo.mesa.paradas == [], "a parada do jogador que saiu caiu no aparelho do P1"
    assert jogo.mesa.escritas[antes:] == [], "o zero do pad 2 caiu no aparelho do P1"
