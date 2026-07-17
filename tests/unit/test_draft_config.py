"""Testes unitarios de DraftConfig (FEAT-PROFILE-STATE-01).

Cobre:
  (a) DraftConfig.default() — valores seguros
  (b) from_profile(profile) — preserva campos do perfil
  (c) to_profile(name) — gera Profile valido; round-trip via model_validate
  (d) model_copy em uma secao preserva outras secoes
"""
from __future__ import annotations

from pathlib import Path

import pytest

from hefesto_dualsense4unix.app.draft_config import (
    DraftConfig,
    EmulationDraft,
    LedsDraft,
    MouseDraft,
    RumbleDraft,
    TriggerDraft,
    TriggersDraft,
)
from hefesto_dualsense4unix.profiles.schema import (
    LedsConfig,
    MatchAny,
    Profile,
    RumbleConfig,
    TriggerConfig,
    TriggersConfig,
)

# ---------------------------------------------------------------------------
# (a) default()
# ---------------------------------------------------------------------------


def test_default_instancia_sem_erro() -> None:
    draft = DraftConfig.default()
    assert isinstance(draft, DraftConfig)


def test_default_triggers_off() -> None:
    draft = DraftConfig.default()
    assert draft.triggers.left.mode == "Off"
    assert draft.triggers.right.mode == "Off"
    assert draft.triggers.left.params == ()
    assert draft.triggers.right.params == ()


def test_default_leds_valores_seguros() -> None:
    draft = DraftConfig.default()
    assert isinstance(draft.leds.lightbar_rgb, tuple)
    assert len(draft.leds.lightbar_rgb) == 3
    assert 0 <= draft.leds.lightbar_brightness <= 100
    assert len(draft.leds.player_leds) == 5
    assert draft.leds.mic_led is False


def test_default_rumble_zerado() -> None:
    draft = DraftConfig.default()
    assert draft.rumble.weak == 0
    assert draft.rumble.strong == 0
    # FEAT-RUMBLE-POLICY-PROFILE-01: default é SEM opinião (None) — salvar um
    # perfil novo sem tocar na aba Rumble não inventa política.
    assert draft.rumble.policy is None
    assert draft.rumble.custom_mult is None


def test_default_mouse_desabilitado() -> None:
    draft = DraftConfig.default()
    assert draft.mouse.enabled is False
    assert 1 <= draft.mouse.speed <= 12
    assert 1 <= draft.mouse.scroll_speed <= 5


def test_default_imutavel() -> None:
    """DraftConfig é frozen — atribuição direta deve levantar ValidationError."""
    from pydantic import ValidationError
    draft = DraftConfig.default()
    with pytest.raises(ValidationError):
        draft.rumble = RumbleDraft(weak=50, strong=50)  # type: ignore[misc]


# ---------------------------------------------------------------------------
# (b) from_profile(profile)
# ---------------------------------------------------------------------------


def _make_profile(
    name: str = "teste",
    left_mode: str = "Rigid",
    left_params: list[int] | None = None,
    right_mode: str = "Off",
    right_params: list[int] | None = None,
    rgb: tuple[int, int, int] = (128, 0, 255),
    brightness: float = 0.8,
    player_leds: list[bool] | None = None,
) -> Profile:
    # Rigid(position=0..9, force=0..255) — apenas 2 params posicionais
    # Off — sem params
    return Profile(
        name=name,
        match=MatchAny(),
        triggers=TriggersConfig(
            left=TriggerConfig(mode=left_mode, params=left_params or [0, 100]),
            right=TriggerConfig(mode=right_mode, params=right_params or []),
        ),
        leds=LedsConfig(
            lightbar=rgb,
            lightbar_brightness=brightness,
            player_leds=player_leds or [True, True, True, True, True],
        ),
        rumble=RumbleConfig(),
    )


def test_from_profile_modo_trigger() -> None:
    profile = _make_profile(left_mode="Rigid", right_mode="Galloping")
    draft = DraftConfig.from_profile(profile)
    assert draft.triggers.left.mode == "Rigid"
    assert draft.triggers.right.mode == "Galloping"


def test_from_profile_params_trigger() -> None:
    # Rigid(position, force) — 2 params; Off — 0 params
    profile = _make_profile(
        left_params=[0, 100],
        right_params=[],
    )
    draft = DraftConfig.from_profile(profile)
    assert draft.triggers.left.params == (0, 100)
    assert draft.triggers.right.params == ()


def test_from_profile_leds_rgb() -> None:
    profile = _make_profile(rgb=(128, 0, 255))
    draft = DraftConfig.from_profile(profile)
    assert draft.leds.lightbar_rgb == (128, 0, 255)


def test_from_profile_brightness_convertida_para_pct() -> None:
    """brightness 0.8 no perfil deve virar 80 (%) no draft."""
    profile = _make_profile(brightness=0.8)
    draft = DraftConfig.from_profile(profile)
    assert draft.leds.lightbar_brightness == 80


def test_from_profile_player_leds() -> None:
    profile = _make_profile(player_leds=[True, False, True, False, True])
    draft = DraftConfig.from_profile(profile)
    assert draft.leds.player_leds == (True, False, True, False, True)


def test_from_profile_rumble_default() -> None:
    """Profile v1 não tem weak/strong; draft deve usar defaults."""
    profile = _make_profile()
    draft = DraftConfig.from_profile(profile)
    assert draft.rumble.weak == 0
    assert draft.rumble.strong == 0


def test_from_profile_mouse_default() -> None:
    """Profile v1 não tem mouse; draft deve usar defaults."""
    profile = _make_profile()
    draft = DraftConfig.from_profile(profile)
    assert draft.mouse.enabled is False


# ---------------------------------------------------------------------------
# (c) to_profile — round-trip via Profile.model_validate
# ---------------------------------------------------------------------------


def test_to_profile_nome_preservado() -> None:
    draft = DraftConfig.default()
    profile = draft.to_profile("meu_perfil")
    assert profile.name == "meu_perfil"


def test_to_profile_priority_default() -> None:
    draft = DraftConfig.default()
    profile = draft.to_profile("p", priority=5)
    assert profile.priority == 5


def test_to_profile_triggers_preservados() -> None:
    # Rigid(position, force) — 2 params
    draft = DraftConfig(
        triggers=TriggersDraft(
            left=TriggerDraft(mode="Rigid", params=(0, 100)),
            right=TriggerDraft(mode="Off", params=()),
        )
    )
    profile = draft.to_profile("p")
    assert profile.triggers.left.mode == "Rigid"
    assert profile.triggers.left.params == [0, 100]
    assert profile.triggers.right.mode == "Off"


def test_to_profile_leds_preservados() -> None:
    draft = DraftConfig(
        leds=LedsDraft(
            lightbar_rgb=(128, 0, 255),
            lightbar_brightness=80,
            player_leds=(True, True, True, True, True),
        )
    )
    profile = draft.to_profile("p")
    assert profile.leds.lightbar == (128, 0, 255)
    assert abs(profile.leds.lightbar_brightness - 0.8) < 0.01
    assert profile.leds.player_leds == [True, True, True, True, True]


def test_to_profile_valida_via_model_validate() -> None:
    """to_profile deve passar por model_validate sem excecao."""
    draft = DraftConfig.default()
    profile = draft.to_profile("validado")
    revalidated = Profile.model_validate(profile.model_dump(mode="python"))
    assert revalidated.name == "validado"


def test_round_trip_from_profile_to_profile() -> None:
    """from_profile(p).to_profile(p.name) deve reproduzir campos equivalentes."""
    original = _make_profile(
        name="roundtrip",
        left_mode="Rigid",
        left_params=[0, 100],
        rgb=(64, 128, 192),
        brightness=0.5,
    )
    draft = DraftConfig.from_profile(original)
    restored = draft.to_profile("roundtrip")

    assert restored.triggers.left.mode == "Rigid"
    assert restored.triggers.left.params == [0, 100]
    assert restored.leds.lightbar == (64, 128, 192)
    assert abs(restored.leds.lightbar_brightness - 0.5) < 0.01


# ---------------------------------------------------------------------------
# (d) model_copy preserva outras secoes
# ---------------------------------------------------------------------------


def test_model_copy_leds_preserva_triggers() -> None:
    """Alterar leds via model_copy não deve modificar triggers."""
    draft = DraftConfig(
        triggers=TriggersDraft(
            left=TriggerDraft(mode="Rigid", params=(0, 100, 255)),
        ),
        leds=LedsDraft(lightbar_rgb=(255, 0, 0)),
    )
    novo_leds = draft.leds.model_copy(update={"lightbar_brightness": 50})
    novo_draft = draft.model_copy(update={"leds": novo_leds})

    # leds atualizado
    assert novo_draft.leds.lightbar_brightness == 50
    # triggers preservados
    assert novo_draft.triggers.left.mode == "Rigid"
    assert novo_draft.triggers.left.params == (0, 100, 255)


def test_model_copy_triggers_preserva_mouse() -> None:
    """Alterar triggers via model_copy não deve modificar mouse."""
    draft = DraftConfig(
        mouse=MouseDraft(enabled=True, speed=8, scroll_speed=3),
    )
    novo_left = TriggerDraft(mode="SlopeFeedback", params=(0, 10, 100))
    novo_triggers = draft.triggers.model_copy(update={"left": novo_left})
    novo_draft = draft.model_copy(update={"triggers": novo_triggers})

    # triggers atualizados
    assert novo_draft.triggers.left.mode == "SlopeFeedback"
    # mouse preservado
    assert novo_draft.mouse.enabled is True
    assert novo_draft.mouse.speed == 8
    assert novo_draft.mouse.scroll_speed == 3


def test_model_copy_rumble_preserva_emulation() -> None:
    """Alterar rumble via model_copy não deve modificar emulation."""
    draft = DraftConfig(
        emulation=EmulationDraft(xbox360_enabled=True),
    )
    novo_rumble = draft.rumble.model_copy(update={"weak": 100, "strong": 200})
    novo_draft = draft.model_copy(update={"rumble": novo_rumble})

    # rumble atualizado
    assert novo_draft.rumble.weak == 100
    assert novo_draft.rumble.strong == 200
    # emulation preservado
    assert novo_draft.emulation.xbox360_enabled is True


def test_model_copy_nao_modifica_original() -> None:
    """model_copy deve retornar nova instancia; original inalterado."""
    draft = DraftConfig.default()
    novo_draft = draft.model_copy(
        update={"rumble": RumbleDraft(weak=50, strong=50)}
    )
    # Original inalterado
    assert draft.rumble.weak == 0
    assert draft.rumble.strong == 0
    # Novo tem valores atualizados
    assert novo_draft.rumble.weak == 50
    assert novo_draft.rumble.strong == 50


# ---------------------------------------------------------------------------
# to_ipc_dict
# ---------------------------------------------------------------------------


def test_to_ipc_dict_estrutura() -> None:
    """to_ipc_dict deve retornar dict com secoes triggers/leds/rumble/mouse."""
    draft = DraftConfig.default()
    d = draft.to_ipc_dict()
    assert "triggers" in d
    assert "leds" in d
    assert "rumble" in d
    assert "mouse" in d


def test_to_ipc_dict_brightness_normalizada() -> None:
    """lightbar_brightness 80 (%) deve virar 0.8 no dict IPC."""
    draft = DraftConfig(leds=LedsDraft(lightbar_brightness=80))
    d = draft.to_ipc_dict()
    assert abs(d["leds"]["lightbar_brightness"] - 0.8) < 0.01


def test_to_ipc_dict_mic_led_ausente() -> None:
    """mic_led e reservado V2 — não deve aparecer no dict IPC."""
    draft = DraftConfig.default()
    d = draft.to_ipc_dict()
    assert "mic_led" not in d.get("leds", {})


# ---------------------------------------------------------------------------
# Dirty-tracking da seção mouse (BUG-MOUSE-GUI-SYNC-01 A2)
# ---------------------------------------------------------------------------


def test_to_ipc_dict_mouse_none_quando_nao_tocado() -> None:
    """Seção mouse intocada vira None — DraftApplier pula e o Aplicar não
    desliga (nem persiste off) uma emulação ligada por CLI/applet (repro A2)."""
    draft = DraftConfig.default()
    d = draft.to_ipc_dict()
    assert d["mouse"] is None


def test_to_ipc_dict_mouse_emitido_quando_dirty() -> None:
    """Seção mouse tocada (dirty=True) viaja — só as velocidades (HARM-05).

    ``enabled`` fica de fora: quem liga/desliga o mouse é o MODO. Só os sliders
    marcam dirty, então o `enabled` do draft aqui é sempre eco de estado velho —
    emiti-lo fazia o Aplicar durante o jogo religar o mouse e matar o vpad.
    """
    draft = DraftConfig.default()
    novo_mouse = draft.mouse.model_copy(
        update={"enabled": True, "speed": 9, "dirty": True}
    )
    d = draft.model_copy(update={"mouse": novo_mouse}).to_ipc_dict()
    assert d["mouse"] == {"speed": 9, "scroll_speed": 1}


def test_to_ipc_dict_mouse_dirty_nao_vaza_no_payload() -> None:
    """O campo interno `dirty` não faz parte do contrato IPC."""
    novo_mouse = MouseDraft(enabled=True, dirty=True)
    d = DraftConfig(mouse=novo_mouse).to_ipc_dict()
    assert "dirty" not in d["mouse"]


def test_to_ipc_dict_mouse_nunca_leva_enabled() -> None:
    """Nenhum "Aplicar" pode mudar o modo do sistema (HARM-05, aceite).

    Repro que este teste tranca: Início em "Controlar o PC" -> aba Mouse liga o
    switch -> "Jogar pelo Hefesto" -> um "Aplicar" qualquer (mudou um gatilho).
    Com `enabled=True` no payload o daemon aplicava a exclusão mútua e o vpad
    morria no meio do jogo. O payload não consegue mais expressar isso — não é
    uma limpeza tardia (que só alcança o SEGUNDO Aplicar), é o campo não existir.
    """
    sujo = MouseDraft(enabled=True, speed=9, scroll_speed=3, dirty=True)
    for mouse in (sujo, sujo.model_copy(update={"enabled": False})):
        d = DraftConfig(mouse=mouse).to_ipc_dict()
        assert "enabled" not in d["mouse"]


def test_from_profile_limpa_dirty_do_mouse() -> None:
    """Recarregar do perfil (ex.: Restaurar Default) LIMPA o dirty da seção
    mouse — perfil v1 não tem mouse, então a seção volta a intocada."""
    profile = _make_profile()
    draft = DraftConfig.from_profile(profile)
    assert draft.mouse.dirty is False
    assert draft.to_ipc_dict()["mouse"] is None


def test_mouse_draft_dirty_default_false() -> None:
    """Sincronização programática (overlay do state_full) não marca dirty."""
    overlay = MouseDraft(enabled=True, speed=9, scroll_speed=2)
    assert overlay.dirty is False


# ---------------------------------------------------------------------------
# PERFIL-02 (sprint 2026-07-16-perfis-por-controle): passthrough do mapa
# `controllers` — o anti-BUG-FOOTER-SAVE-DROPS-SECTIONS-01 desta frente
# ---------------------------------------------------------------------------

#: MAC forjado da faixa permitida (test_anonimato_de_fixtures.py).
_MAC_BT = "aabbcc000002"


def _profile_com_mapa(name: str = "vitoria") -> Profile:
    from hefesto_dualsense4unix.profiles.schema import ControllerOverrides

    base = _make_profile(name=name)
    return base.model_copy(
        update={
            "controllers": {
                _MAC_BT: ControllerOverrides(leds=LedsConfig(lightbar=(0, 0, 255))),
            }
        }
    )


def test_from_profile_transporta_controllers() -> None:
    """O mapa do perfil entra no draft como passthrough (source_controllers)."""
    draft = DraftConfig.from_profile(_profile_com_mapa())
    assert draft.source_controllers is not None
    assert _MAC_BT in draft.source_controllers


def test_to_profile_preserva_controllers_apos_editar_outra_coisa() -> None:
    """O round-trip que trava a classe de bug histórica: carregar perfil COM
    mapa → editar OUTRA seção na GUI (leds globais) → salvar → mapa intacto.

    `to_profile()` reconstrói o Profile do zero — sem o passthrough, este é
    exatamente o caminho que já apagou seções DUAS vezes
    (BUG-FOOTER-SAVE-DROPS-SECTIONS-01, BUG-MOUSE-SAVE-DROPS-SECTION-01).
    """
    original = _profile_com_mapa()
    draft = DraftConfig.from_profile(original)

    # A usuária mexe em OUTRA coisa: a cor global da lightbar.
    novo_leds = draft.leds.model_copy(update={"lightbar_rgb": (255, 0, 0)})
    draft = draft.model_copy(update={"leds": novo_leds})

    salvo = draft.to_profile(original.name)
    assert salvo.leds.lightbar == (255, 0, 0)  # a edição valeu
    assert salvo.controllers == original.controllers  # o mapa NÃO se perdeu
    assert salvo.controllers is not None
    assert salvo.controllers[_MAC_BT].leds is not None
    assert salvo.controllers[_MAC_BT].leds.lightbar == (0, 0, 255)


def test_to_profile_sem_mapa_nao_inventa_a_chave() -> None:
    """Perfil de origem SEM mapa (os antigos da usuária) segue sem mapa após
    o ciclo do draft — e um draft novo (sem origem) idem."""
    draft = DraftConfig.from_profile(_make_profile(name="antigo"))
    assert draft.to_profile("antigo").controllers is None
    assert DraftConfig.default().to_profile("novo").controllers is None


def test_roundtrip_draft_e_loader_ponta_a_ponta(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """O fluxo inteiro do rodapé: load_profile → from_profile → editar outra
    coisa → to_profile → save_profile → o JSON no disco mantém o mapa."""
    import json

    from hefesto_dualsense4unix.profiles import loader as loader_module
    from hefesto_dualsense4unix.profiles.loader import load_profile, save_profile

    target = tmp_path / "profiles"
    target.mkdir()
    monkeypatch.setattr(
        loader_module, "profiles_dir", lambda ensure=False: target
    )

    save_profile(_profile_com_mapa(name="vitoria"))
    draft = DraftConfig.from_profile(load_profile("vitoria"))
    novo_leds = draft.leds.model_copy(update={"lightbar_brightness": 50})
    draft = draft.model_copy(update={"leds": novo_leds})
    path = save_profile(draft.to_profile("vitoria"))
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["controllers"][_MAC_BT]["leds"]["lightbar"] == [0, 0, 255]
    assert abs(data["leds"]["lightbar_brightness"] - 0.5) < 0.01
