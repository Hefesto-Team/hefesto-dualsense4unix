"""TRAVA-QUE-SOLTA-TARDE-01 — o gesto explícito é vítima da própria trava.

MEDIDO AO VIVO em 05/08/2026, na máquina dela, com o daemon de produção.

Ela ajusta um gatilho na mão (o daemon carimba a categoria `"trigger"` em
`manual_override_categories`) e depois troca de perfil — o gesto que esta casa
documenta, em três lugares, como a saída explícita da trava:

  - `state_store.clear_manual_trigger_active`: *"Tudo: `profile.switch`
    explícito, hotkey de ciclo e a ativação de perfil de JOGO pelo autoswitch —
    os três são 'troquei de perfil', onde soltar as três categorias é o que a
    usuária pediu."*;
  - `manager.apply` (:312-313): *"Trocar de perfil pela GUI limpa as TRÊS
    categorias — então isso NÃO é um estado do qual ela não consiga sair."*;
  - `ipc_handlers.py:410-411`: *"Usuário escolheu perfil explícito: libera
    autoswitch de novo."*

**A ordem trai as três.** O handler aplica o perfil em `:404` e só limpa a
trava em `:412` — oito linhas depois. A ativação inteira roda com a trava ainda
armada, `manager.apply` pula as categorias travadas (`:326-348`, emitindo
`None` no `OutputSpec`), e o daemon responde `"ativado"`. A trava é limpa tarde
demais para a ativação que a limpou: ela só vale para a PRÓXIMA.

A prova, no journal dela, com duas ativações idênticas do MESMO perfil:

    00:02:06  profile_apply_respeita_override_manual  categorias=['audio','trigger']
    00:02:06  profile_activated  name=vitoria            <- pulou as duas
    00:03:22  profile_activated  name=vitoria            <- aplicou tudo

Mesma ação, duas vezes, resultados diferentes.

**O mesmo defeito está na hotkey** (`subsystems/hotkey.py:155-163`), e o
comentário de lá diz, textualmente, *"paridade com _handle_profile_switch"* —
a paridade copiou a ordem errada. É o gesto PS + D-pad, que o README documenta
e que ela usa DENTRO do jogo.

**O caminho automático está CERTO** e serve de referência:
`autoswitch.py:505-518` limpa a trava ANTES de seguir para a aplicação.

Por que a suíte não pegou — e é o padrão que a ENTREGA-QUE-NÃO-LIGOU-01 nomeia
(*"mede o artefato, nunca o encontro dele com o resto do sistema"*):

  - `test_onda_u_trava_por_categoria.py:144-155` chama
    `store.clear_manual_trigger_active()` À MÃO, com o comentário *"# o que
    `profile.switch` chama"*, e nunca chama `_handle_profile_switch`. Ficaria
    verde com o handler quebrado — e está;
  - `test_perfil_respeita_trava_manual.py:122-132` faz `clear()` e DEPOIS
    `apply()`. Ele documenta a ordem certa que o produto não executa.

MORDIDA: inverta de volta as duas linhas de `_handle_profile_switch` (aplicar
antes de limpar) e `test_troca_explicita_aplica_a_categoria_travada` fica
vermelho. Idem em `_cycle` para o teste da hotkey.
"""
from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from hefesto_dualsense4unix.daemon.ipc_handlers import IpcHandlersMixin
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
    """Captura o `OutputSpec` que cada ativação emite em broadcast."""

    def __init__(self) -> None:
        super().__init__()
        self.defaults: list[Any] = []

    def apply_output_defaults(self, spec: Any) -> None:  # type: ignore[override]
        self.defaults.append(spec)
        super().apply_output_defaults(spec)


def _perfil() -> Profile:
    """Perfil com gatilho E cor — as duas categorias que a trava cobre."""
    return Profile(
        name="vitoria",
        match=MatchCriteria(window_class=["qualquer"]),
        priority=10,
        leds=LedsConfig(lightbar=[10, 200, 30]),
        triggers=TriggersConfig(
            left=TriggerConfig(mode="Rigid", params=[5, 200]),
            right=TriggerConfig(mode="Rigid", params=[5, 200]),
        ),
    )


@pytest.fixture()
def bancada(monkeypatch: pytest.MonkeyPatch) -> tuple[StateStore, _Espiao, ProfileManager]:
    """`ProfileManager` real + `StateStore` real, sem tocar o disco dela."""
    monkeypatch.setattr(
        "hefesto_dualsense4unix.profiles.manager.load_profile",
        lambda _name: _perfil(),
    )
    for alvo in ("save_active_marker", "save_last_profile"):
        monkeypatch.setattr(
            f"hefesto_dualsense4unix.utils.session.{alvo}",
            lambda _n: None,
        )
    fc = _Espiao()
    fc.connect()
    store = StateStore()
    return store, fc, ProfileManager(controller=fc, store=store)


def _host(store: StateStore, manager: ProfileManager) -> Any:
    class _Host(IpcHandlersMixin):
        pass

    host = _Host()
    host.profile_manager = manager  # type: ignore[attr-defined]
    host.store = store  # type: ignore[attr-defined]
    host.daemon = None  # type: ignore[attr-defined]
    return host


@pytest.mark.asyncio
async def test_troca_explicita_aplica_a_categoria_travada(
    bancada: tuple[StateStore, _Espiao, ProfileManager],
) -> None:
    """O caso dela: mexeu no gatilho, trocou de perfil, o gatilho do perfil ENTRA.

    Reprova hoje: o `OutputSpec` sai com `trigger_left=None` porque a trava
    ainda estava armada quando `manager.apply` rodou.
    """
    store, fc, manager = bancada
    store.mark_manual_trigger_active("trigger")

    await _host(store, manager)._handle_profile_switch({"name": "vitoria"})

    spec = fc.defaults[-1]
    assert spec.trigger_left is not None and spec.trigger_right is not None, (
        "trocar de perfil é a saída EXPLÍCITA da trava manual — a ativação que "
        "solta a trava não pode ser a única que não a aproveita"
    )


@pytest.mark.asyncio
async def test_troca_explicita_aplica_todas_as_categorias_travadas(
    bancada: tuple[StateStore, _Espiao, ProfileManager],
) -> None:
    """Não é só o gatilho: `led` e `audio` sofrem o mesmo (o journal dela traz as duas)."""
    store, fc, manager = bancada
    for categoria in ("trigger", "led", "audio"):
        store.mark_manual_trigger_active(categoria)

    await _host(store, manager)._handle_profile_switch({"name": "vitoria"})

    spec = fc.defaults[-1]
    assert spec.led == (10, 200, 30), (
        "a cor do perfil escolhido a dedo não entrou porque um gesto anterior "
        "de LED ainda estava carimbado"
    )
    assert spec.trigger_left is not None


@pytest.mark.asyncio
async def test_a_trava_fica_limpa_no_fim(
    bancada: tuple[StateStore, _Espiao, ProfileManager],
) -> None:
    """A garantia que JÁ existia não pode regredir com a correção da ordem."""
    store, _fc, manager = bancada
    store.mark_manual_trigger_active("trigger")

    await _host(store, manager)._handle_profile_switch({"name": "vitoria"})

    assert store.manual_override_categories == frozenset()


@pytest.mark.asyncio
async def test_falha_na_ativacao_devolve_a_trava(
    bancada: tuple[StateStore, _Espiao, ProfileManager],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Atomicidade: `profile.switch` com nome inexistente não custa a trava dela.

    Mover o clear para ANTES do `activate` abriu esta borda — sem o restore,
    um nome errado na CLI apagaria a configuração que ela fez na mão.
    """
    store, _fc, manager = bancada
    monkeypatch.setattr(
        "hefesto_dualsense4unix.profiles.manager.load_profile",
        lambda _name: (_ for _ in ()).throw(FileNotFoundError("perfil inexistente")),
    )
    store.mark_manual_trigger_active("trigger")
    store.mark_manual_trigger_active("led")

    with pytest.raises(FileNotFoundError):
        await _host(store, manager)._handle_profile_switch({"name": "fantasma"})

    assert store.manual_override_categories == frozenset({"trigger", "led"})


@pytest.mark.asyncio
async def test_falha_na_ativacao_nao_congela_o_autoswitch(
    bancada: tuple[StateStore, _Espiao, ProfileManager],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A segunda borda que a subida do lock abriu, apontada na revisão.

    O lock manual suprime o autoswitch por `MANUAL_PROFILE_LOCK_SEC` (30 s).
    Ele passou a ser armado ANTES do `activate` — então uma ativação que falha
    deixava a troca automática congelada por 30 s **sem gesto nenhum
    cumprido**. Um nome errado na CLI não pode ter esse preço.
    """
    import time

    store, _fc, manager = bancada
    monkeypatch.setattr(
        "hefesto_dualsense4unix.profiles.manager.load_profile",
        lambda _name: (_ for _ in ()).throw(FileNotFoundError("perfil inexistente")),
    )
    assert not store.manual_profile_lock_active(time.monotonic())

    with pytest.raises(FileNotFoundError):
        await _host(store, manager)._handle_profile_switch({"name": "fantasma"})

    assert not store.manual_profile_lock_active(time.monotonic()), (
        "uma ativação que falhou congelou a troca automática de perfil"
    )


@pytest.mark.asyncio
async def test_hotkey_ps_dpad_tambem_aplica_a_categoria_travada(
    bancada: tuple[StateStore, _Espiao, ProfileManager],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """O MESMO defeito no gesto que ela usa dentro do jogo (PS + D-pad).

    O comentário do `speaker_applier` (`hotkey.py:132-135`) promete, desde a
    SOM-02/E4, que este ciclo *"limpa as categorias travadas (inclusive
    `audio`) e portanto aplica o volume do perfil que entra"*. Com a ordem
    invertida, não aplicava.
    """
    from hefesto_dualsense4unix.daemon.subsystems.hotkey import (
        build_profile_cycle_callback,
    )

    store, fc, _manager = bancada
    monkeypatch.setattr(
        ProfileManager,
        "list_profiles",
        lambda _self: [SimpleNamespace(name="navegacao"), SimpleNamespace(name="vitoria")],
    )
    store.set_active_profile("navegacao")
    store.mark_manual_trigger_active("trigger")

    class _Daemon:
        def __init__(self) -> None:
            self.store = store
            self.controller = fc
            self._keyboard_device = None

        async def _run_blocking(self, fn: Any, *args: Any) -> Any:
            return fn(*args)

    await build_profile_cycle_callback(_Daemon(), +1)()

    spec = fc.defaults[-1]
    assert spec.trigger_left is not None, (
        "PS + D-pad é troca EXPLÍCITA de perfil — o gatilho do perfil que "
        "entra tem de entrar, mesmo com um ajuste manual anterior carimbado"
    )
    assert store.manual_override_categories == frozenset()


@pytest.mark.asyncio
async def test_duas_ativacoes_seguidas_sao_indistinguiveis(
    bancada: tuple[StateStore, _Espiao, ProfileManager],
) -> None:
    """A assinatura do defeito, virada em teste.

    Na máquina dela, a 1a ativação pulava e a 2a aplicava. Duas ativações
    idênticas do mesmo perfil têm de produzir o MESMO `OutputSpec`.
    """
    store, fc, manager = bancada
    store.mark_manual_trigger_active("trigger")
    host = _host(store, manager)

    await host._handle_profile_switch({"name": "vitoria"})
    primeira = fc.defaults[-1]
    await host._handle_profile_switch({"name": "vitoria"})
    segunda = fc.defaults[-1]

    assert primeira == segunda, (
        "a mesma ação, repetida, produziu resultados diferentes — a trava "
        "estava sendo limpa tarde demais para a ativação que a limpou"
    )
