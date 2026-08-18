"""PERFIL-MANUAL-VENCE-01 (pedido da mantenedora, 23/07).

*"o sackboy deveria ser trava manual também"*.

O R-01 fez o catch-all parar de ser tratado como "perfil do jogo" — isso curou o
Mullet Mad Jack. Mas o Sackboy TEM perfil próprio, então ele É a regra do jogo e
cede legitimamente: a trava manual era limpa e o perfil reescrevia tudo.

Isso está CERTO para o MODO — ela precisa do gamepad+co-op aplicados para jogar
a 4 — e ERRADO para a aparência: a cor/gatilho que ela acabou de ajustar sumia
ao abrir o jogo. É a queixa "a config que eu deixo nunca é respeitada", na
metade que o R-01 não cobria.

Os eixos passam a ser independentes: o `mode` aplica sempre; as seções que ela
travou NA MÃO atravessam a ativação. `None` no `OutputSpec` já significa "sem
opinião" (merge POR CAMPO no backend), então a seção travada simplesmente não é
emitida.

Sair da trava continua fácil e explícito: trocar de perfil pela GUI, o
`trigger.reset` ou o botão "Desligar" limpam o carimbo.
"""

from __future__ import annotations

from typing import Any

from hefesto_dualsense4unix.daemon.state_store import StateStore
from hefesto_dualsense4unix.profiles.manager import ProfileManager
from hefesto_dualsense4unix.profiles.schema import (
    LedsConfig,
    MatchCriteria,
    Profile,
    TriggerConfig,
    TriggersConfig,
)
from hefesto_dualsense4unix.testing import FakeController


class _Espiao(FakeController):
    """Captura o OutputSpec que a ativação emite em broadcast."""

    def __init__(self) -> None:
        super().__init__()
        self.defaults: list[Any] = []

    def apply_output_defaults(self, spec: Any) -> None:  # type: ignore[override]
        self.defaults.append(spec)
        super().apply_output_defaults(spec)


def _perfil_do_sackboy() -> Profile:
    return Profile(
        name="sackboy_nativo",
        match=MatchCriteria(window_class=["steam_app_1599660"]),
        priority=80,
        leds=LedsConfig(lightbar=[10, 200, 30]),
        triggers=TriggersConfig(
            left=TriggerConfig(mode="Rigid", params=[5, 200]),
            right=TriggerConfig(mode="Rigid", params=[5, 200]),
        ),
    )


def _manager(store: StateStore) -> tuple[ProfileManager, _Espiao]:
    fc = _Espiao()
    fc.connect()
    return ProfileManager(controller=fc, store=store), fc


def test_sem_trava_o_perfil_aplica_tudo() -> None:
    """Linha de base: sem gesto manual, o perfil manda em tudo."""
    store = StateStore()
    mgr, fc = _manager(store)
    mgr.apply(_perfil_do_sackboy())

    spec = fc.defaults[-1]
    assert spec.led == (10, 200, 30)
    assert spec.trigger_left is not None


def test_led_travado_sobrevive_ao_perfil_do_jogo() -> None:
    """O caso dela: ajusta a cor, abre o Sackboy, a cor FICA."""
    store = StateStore()
    store.mark_manual_trigger_active("led")
    mgr, fc = _manager(store)
    mgr.apply(_perfil_do_sackboy())

    spec = fc.defaults[-1]
    assert spec.led is None, (
        "o perfil do jogo reescreveu a cor que ela acabou de ajustar na mão"
    )
    assert spec.player_leds is None
    # ...mas o gatilho, que ela NÃO travou, segue vindo do perfil.
    assert spec.trigger_left is not None


def test_gatilho_travado_sobrevive_e_o_led_nao() -> None:
    """A trava é POR CATEGORIA — não é tudo ou nada."""
    store = StateStore()
    store.mark_manual_trigger_active("trigger")
    mgr, fc = _manager(store)
    mgr.apply(_perfil_do_sackboy())

    spec = fc.defaults[-1]
    assert spec.trigger_left is None and spec.trigger_right is None
    assert spec.led == (10, 200, 30)


def test_as_tres_travadas_deixam_o_perfil_sem_opiniao_de_saida() -> None:
    store = StateStore()
    for categoria in ("led", "trigger", "rumble"):
        store.mark_manual_trigger_active(categoria)
    mgr, fc = _manager(store)
    mgr.apply(_perfil_do_sackboy())

    spec = fc.defaults[-1]
    assert spec.led is None
    assert spec.player_leds is None
    assert spec.trigger_left is None and spec.trigger_right is None


def test_limpar_a_trava_devolve_o_comando_ao_perfil() -> None:
    """Não é estado sem saída: `trigger.reset`/troca de perfil limpam."""
    store = StateStore()
    store.mark_manual_trigger_active("led")
    mgr, fc = _manager(store)
    mgr.apply(_perfil_do_sackboy())
    assert fc.defaults[-1].led is None

    store.clear_manual_trigger_active()
    mgr.apply(_perfil_do_sackboy())
    assert fc.defaults[-1].led == (10, 200, 30)


def test_manager_sem_store_nao_explode() -> None:
    """Dublês e CLI podem não ter store — na dúvida, comportamento clássico."""
    fc = _Espiao()
    fc.connect()
    mgr = ProfileManager(controller=fc)
    mgr.apply(_perfil_do_sackboy())
    assert fc.defaults[-1].led == (10, 200, 30)
