"""Testes do ProfileManager."""
from __future__ import annotations

from pathlib import Path

import pytest

from hefesto_dualsense4unix.core.trigger_effects import rigid
from hefesto_dualsense4unix.daemon.state_store import StateStore
from hefesto_dualsense4unix.profiles import loader as loader_module
from hefesto_dualsense4unix.profiles.loader import save_profile
from hefesto_dualsense4unix.profiles.manager import (
    MOTIVO_JOGO_SEM_PERFIL_PROPRIO,
    ProfileManager,
)
from hefesto_dualsense4unix.profiles.schema import (
    LedsConfig,
    MatchAny,
    MatchCriteria,
    Profile,
    TriggerConfig,
    TriggersConfig,
)
from hefesto_dualsense4unix.testing import FakeController


@pytest.fixture
def isolated_profiles_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    target = tmp_path / "profiles"
    target.mkdir()

    def fake_profiles_dir(ensure: bool = False) -> Path:
        if ensure:
            target.mkdir(parents=True, exist_ok=True)
        return target

    monkeypatch.setattr(loader_module, "profiles_dir", fake_profiles_dir)
    return target


def _mk_profile(name: str, priority: int = 10, **kw) -> Profile:
    defaults = {
        "match": MatchCriteria(window_class=[f"{name}_class"]),
        "priority": priority,
        "triggers": TriggersConfig(
            left=TriggerConfig(mode="Off"),
            right=TriggerConfig(mode="Rigid", params=[5, 200]),
        ),
        "leds": LedsConfig(lightbar=(10, 20, 30), player_leds=[True] * 5),
    }
    defaults.update(kw)
    return Profile(name=name, **defaults)


def test_activate_aplica_trigger_e_led(isolated_profiles_dir: Path):
    save_profile(_mk_profile("shooter"))
    fc = FakeController()
    fc.connect()
    store = StateStore()
    manager = ProfileManager(controller=fc, store=store)

    applied = manager.activate("shooter")
    assert applied.name == "shooter"
    assert store.active_profile == "shooter"

    triggers = [c for c in fc.commands if c.kind == "set_trigger"]
    assert len(triggers) == 2
    # Right = Rigid.
    #
    # TRIGGER-CANON-01: o comentário que estava aqui dizia "RIGID_B = 5 bits,
    # forces[1] = 200 (force cru)" — e `RIGID_B` é `0x05`, o OFF do bloco de
    # gatilho. O preset mandava o controle DESLIGAR o gatilho, e ela mediu
    # isso pelo tato: *"rígido e desligado sem diferença"*. Os bytes vêm da
    # factory em vez de literais porque quem os trava é o
    # `test_trigger_effects.py`, num lugar só.
    right_call = next(c for c in triggers if c.payload[0] == "right")
    assert right_call.payload[1].forces == rigid(5, 200).forces

    leds = [c for c in fc.commands if c.kind == "set_led"]
    assert len(leds) == 1
    assert leds[0].payload == (10, 20, 30)


def test_list_profiles_ordenado(isolated_profiles_dir: Path):
    save_profile(_mk_profile("driving"))
    save_profile(_mk_profile("shooter"))
    save_profile(_mk_profile("bow"))
    fc = FakeController()
    fc.connect()
    manager = ProfileManager(controller=fc)
    names = [p.name for p in manager.list_profiles()]
    assert names == ["bow", "driving", "shooter"]


def test_select_for_window_retorna_maior_prioridade(isolated_profiles_dir: Path):
    save_profile(
        _mk_profile("driving", priority=10, match=MatchCriteria(window_class=["Forza"]))
    )
    save_profile(
        _mk_profile(
            "shooter",
            priority=20,
            match=MatchCriteria(window_class=["Forza"]),
        )
    )
    save_profile(Profile(name="fallback", match=MatchAny(), priority=0))

    fc = FakeController()
    fc.connect()
    manager = ProfileManager(controller=fc)
    picked = manager.select_for_window({"wm_class": "Forza"})
    assert picked is not None
    assert picked.name == "shooter"  # maior priority


def test_criteria_vence_catch_all_de_prioridade_maior(isolated_profiles_dir: Path):
    """R-01 (auditoria 23/07): especificidade vem ANTES de prioridade.

    Estado medido no disco da usuária: `vitoria` é MatchAny com prioridade 5, e
    um perfil de jogo criado pela GUI nasce com prioridade 0. Ordenando só por
    prioridade, o catch-all genérico de desktop vencia a regra própria do jogo
    — ou seja, **criar o perfil do jogo não resolvia** o problema que ela
    tentava resolver criando o perfil.
    """
    save_profile(
        _mk_profile(
            "mad_jack",
            priority=0,
            match=MatchCriteria(window_class=["steam_app_2111190"]),
        )
    )
    save_profile(Profile(name="vitoria", match=MatchAny(), priority=5))

    fc = FakeController()
    fc.connect()
    manager = ProfileManager(controller=fc)
    picked = manager.select_for_window({"wm_class": "steam_app_2111190"})
    assert picked is not None
    assert picked.name == "mad_jack"


def test_prioridade_ainda_decide_entre_perfis_igualmente_especificos(
    isolated_profiles_dir: Path,
):
    """A especificidade não pode atropelar o tuning 50-80 dos presets."""
    save_profile(
        _mk_profile(
            "navegacao", priority=50, match=MatchCriteria(window_class=["steam"])
        )
    )
    save_profile(
        _mk_profile(
            "sackboy", priority=80, match=MatchCriteria(window_class=["steam"])
        )
    )
    save_profile(Profile(name="fallback", match=MatchAny(), priority=0))

    fc = FakeController()
    fc.connect()
    manager = ProfileManager(controller=fc)
    picked = manager.select_for_window({"wm_class": "steam"})
    assert picked is not None
    assert picked.name == "sackboy"


def test_select_for_window_fallback(isolated_profiles_dir: Path):
    save_profile(
        _mk_profile("shooter", match=MatchCriteria(window_class=["DoomEternal"]))
    )
    save_profile(Profile(name="fallback", match=MatchAny(), priority=0))

    fc = FakeController()
    fc.connect()
    manager = ProfileManager(controller=fc)
    picked = manager.select_for_window({"wm_class": "Inkscape"})
    assert picked is not None
    assert picked.name == "fallback"


def test_select_for_window_sem_match_sem_fallback(isolated_profiles_dir: Path):
    save_profile(_mk_profile("shooter", match=MatchCriteria(window_class=["X"])))

    fc = FakeController()
    fc.connect()
    manager = ProfileManager(controller=fc)
    picked = manager.select_for_window({"wm_class": "Nada"})
    assert picked is None


# ---------------------------------------------------------------------------
# R-21 (auditoria 24/07) — catch-all NÃO tem autoridade sobre janela de jogo.
#
# O R-01 acertou a ORDEM (específico vence genérico) mas não a AUTORIDADE: sem
# NENHUMA regra para o jogo, a ordenação ainda elegia o melhor dos catch-all. É
# o caso medido: Mullet Mad Jack (steam_app_2111190) sem perfil próprio ⇒ vence
# `vitoria` (MatchAny, prio 5); alt-tab para a janela `steam` ⇒ vence
# `Navegação` (prio 50). Ping-pong a cada 18-28 s no journal de 22-23/07, com
# lightbar/gatilhos/rumble diferentes dos dois lados.
#
# Mesma doutrina do `catch_all_sem_opiniao` de `lifecycle.apply_profile_
# suppression`, um nível acima: lá o catch-all não pode REVERTER; aqui não pode
# ENTRAR.
# ---------------------------------------------------------------------------


def test_janela_de_jogo_sem_regra_propria_nao_cai_no_catch_all(
    isolated_profiles_dir: Path,
):
    """O caso medido: nenhum perfil opina sobre este jogo ⇒ None (e o
    autoswitch retém o perfil corrente em vez de trocar)."""
    save_profile(Profile(name="vitoria", match=MatchAny(), priority=5))
    save_profile(Profile(name="meu_perfil", match=MatchAny(), priority=1))

    fc = FakeController()
    fc.connect()
    manager = ProfileManager(controller=fc)
    assert manager.select_for_window({"wm_class": "steam_app_2111190"}) is None


@pytest.mark.parametrize(
    "wm_class",
    ["STEAM_APP_2111190", "Steam_App_2111190", "  steam_app_2111190  "],
)
def test_veto_r21_vale_com_wm_class_em_caixa_alta(
    isolated_profiles_dir: Path, wm_class: str
):
    """UNIFICA-PREDICADO-01: o veto R-21 não pode depender da CAIXA da janela.

    O buraco que ninguém cobria. A suíte inteira exercitava o veto só com
    ``steam_app_...`` em minúscula, então a IGNORECASE de `manager.py` era uma
    linha sem testemunha — e a "limpeza" que unifica o predicado numa fonte
    CASE-SENSITIVE revogaria o veto sem uma reprovação sequer. Com a janela se
    anunciando ``Steam_App_2111190`` (o X/XWayland escolhe a grafia, e ela
    muda entre backends de detecção), o catch-all voltaria a entrar por cima
    do jogo: exatamente o ping-pong de 22-23/07 que o R-21 fechou.

    Arranque a `re.IGNORECASE` da fonte (`profiles/steam_app.py`) e este teste
    reprova nos três casos.
    """
    save_profile(Profile(name="vitoria", match=MatchAny(), priority=5))
    save_profile(Profile(name="meu_perfil", match=MatchAny(), priority=1))

    fc = FakeController()
    fc.connect()
    manager = ProfileManager(controller=fc)
    assert manager.select_for_window({"wm_class": wm_class}) is None
    # E o MOTIVO tem de ser "jogo sem perfil próprio", não "nada casou": é ele
    # que faz o daemon ligar o modo jogo padrão em vez de reter em silêncio.
    assert manager.select_for_window_ex({"wm_class": wm_class}) == (
        None,
        MOTIVO_JOGO_SEM_PERFIL_PROPRIO,
    )


def test_veto_r21_em_caixa_alta_sem_candidato_nenhum(isolated_profiles_dir: Path):
    """O ramo vizinho do veto (ZERO candidatos no disco) pelo mesmo predicado.

    `select_for_window_ex` decide o motivo ANTES de olhar candidatos; se o
    predicado for sensível a caixa, esta janela vira `MOTIVO_SEM_CANDIDATO` e
    o modo jogo padrão nunca liga.
    """
    fc = FakeController()
    fc.connect()
    manager = ProfileManager(controller=fc)
    assert manager.select_for_window_ex({"wm_class": "STEAM_APP_2111190"}) == (
        None,
        MOTIVO_JOGO_SEM_PERFIL_PROPRIO,
    )


def test_regra_propria_do_jogo_continua_vencendo(isolated_profiles_dir: Path):
    """O veto é só quando os ÚNICOS candidatos são catch-all — havendo regra
    específica, ela entra normalmente (o R-01 segue de pé)."""
    save_profile(
        _mk_profile(
            "mad_jack",
            priority=0,
            match=MatchCriteria(window_class=["steam_app_2111190"]),
        )
    )
    save_profile(Profile(name="vitoria", match=MatchAny(), priority=5))

    fc = FakeController()
    fc.connect()
    manager = ProfileManager(controller=fc)
    picked = manager.select_for_window({"wm_class": "steam_app_2111190"})
    assert picked is not None and picked.name == "mad_jack"


def test_perfil_que_casa_por_titulo_no_jogo_nao_e_vetado(
    isolated_profiles_dir: Path,
):
    """Só CATCH-ALL é vetado. Um perfil que casou por título/processo opinou
    de verdade sobre esta janela e continua valendo."""
    save_profile(
        _mk_profile(
            "fps",
            priority=60,
            match=MatchCriteria(window_title_regex=r"(Doom|Control)"),
        )
    )
    save_profile(Profile(name="vitoria", match=MatchAny(), priority=5))

    fc = FakeController()
    fc.connect()
    manager = ProfileManager(controller=fc)
    picked = manager.select_for_window(
        {"wm_class": "steam_app_379720", "wm_name": "Doom Eternal"}
    )
    assert picked is not None and picked.name == "fps"


def test_catch_all_segue_valendo_em_janela_comum(isolated_profiles_dir: Path):
    """O veto é EXCLUSIVO de janela de jogo — no desktop o catch-all continua
    sendo o fallback de sempre (senão a aba Mouse/Teclado ficaria sem perfil)."""
    save_profile(Profile(name="vitoria", match=MatchAny(), priority=5))

    fc = FakeController()
    fc.connect()
    manager = ProfileManager(controller=fc)
    picked = manager.select_for_window({"wm_class": "firefox"})
    assert picked is not None and picked.name == "vitoria"


def test_wm_class_parecida_com_steam_app_nao_e_vetada(isolated_profiles_dir: Path):
    """`steam_app_` sem número, ou com sufixo, NÃO é janela de jogo da Steam —
    o predicado é o mesmo (ancorado) dos outros dois lugares que o usam."""
    save_profile(Profile(name="vitoria", match=MatchAny(), priority=5))

    fc = FakeController()
    fc.connect()
    manager = ProfileManager(controller=fc)
    for wm in ("steam_app_", "steam_app_abc", "xsteam_app_1", "steam_app_1_x"):
        picked = manager.select_for_window({"wm_class": wm})
        assert picked is not None and picked.name == "vitoria", wm


def test_veto_loga_uma_vez_por_jogo(
    isolated_profiles_dir: Path, monkeypatch: pytest.MonkeyPatch
):
    """`select_for_window` roda a 2 Hz — o veto não pode virar 7 mil linhas/h."""
    from unittest.mock import MagicMock

    from hefesto_dualsense4unix.profiles import manager as manager_mod

    spy = MagicMock()
    monkeypatch.setattr(manager_mod, "logger", spy)
    save_profile(Profile(name="vitoria", match=MatchAny(), priority=5))

    fc = FakeController()
    fc.connect()
    manager = ProfileManager(controller=fc)
    for _ in range(10):
        manager.select_for_window({"wm_class": "steam_app_2111190"})
    # Volta ao desktop e ao jogo: episódio novo, log novo.
    manager.select_for_window({"wm_class": "firefox"})
    manager.select_for_window({"wm_class": "steam_app_2111190"})

    eventos = [
        c
        for c in spy.info.call_args_list
        if c[0][0] == "profile_select_catch_all_sem_autoridade_em_jogo"
    ]
    assert len(eventos) == 2


def test_delete_do_ativo_reseta_active_profile(isolated_profiles_dir: Path):
    save_profile(_mk_profile("tmp"))
    fc = FakeController()
    fc.connect()
    store = StateStore()
    manager = ProfileManager(controller=fc, store=store)
    manager.activate("tmp")
    assert store.active_profile == "tmp"
    manager.delete("tmp")
    assert store.active_profile is None


def test_delete_por_slug_limpa_active_gravado_como_display_name(
    isolated_profiles_dir: Path,
):
    """BUG-PROFILE-DELETE-ACTIVE-SLUG-01: delete por slug deve limpar o active.

    `activate()` grava o DISPLAY NAME ("Ação") em `active_profile`, mas o
    arquivo vive como `acao.json` e o usuário (ou a GUI) pode deletar pelo slug
    ("acao"). Comparar as strings cruas deixava o active preso; com normalização  # (noqa-acento)
    por slugify a limpeza acontece.
    """
    save_profile(_mk_profile("Ação"))
    fc = FakeController()
    fc.connect()
    store = StateStore()
    manager = ProfileManager(controller=fc, store=store)
    manager.activate("Ação")
    # active é gravado como display name (acentuado), não como slug.
    assert store.active_profile == "Ação"
    # delete pelo SLUG ainda deve limpar o active.
    manager.delete("acao")  # (noqa-acento)
    assert store.active_profile is None


def test_delete_de_outro_perfil_nao_limpa_active(isolated_profiles_dir: Path):
    """Deletar um perfil diferente do ativo NÃO deve zerar o active."""
    save_profile(_mk_profile("ativo"))
    save_profile(_mk_profile("outro"))
    fc = FakeController()
    fc.connect()
    store = StateStore()
    manager = ProfileManager(controller=fc, store=store)
    manager.activate("ativo")
    assert store.active_profile == "ativo"
    manager.delete("outro")
    assert store.active_profile == "ativo"


def test_create_persiste_no_disco(isolated_profiles_dir: Path):
    fc = FakeController()
    fc.connect()
    manager = ProfileManager(controller=fc)
    profile = _mk_profile("new_one")
    manager.create(profile)
    assert (isolated_profiles_dir / "new_one.json").exists()


def test_apply_propaga_brightness(isolated_profiles_dir: Path):
    """FEAT-LED-BRIGHTNESS-02: brightness do perfil chega ao hardware via FakeController.

    Cria perfil com lightbar_brightness=0.25 (25%) e lightbar=(200, 100, 50).
    Apos apply(), verifica que o set_led recebeu valores escalados a 25%.
    """
    profile = _mk_profile(
        "dim_test",
        leds=LedsConfig(lightbar=(200, 100, 50), lightbar_brightness=0.25),
    )
    fc = FakeController()
    fc.connect()
    manager = ProfileManager(controller=fc)
    manager.apply(profile)

    assert fc.last_led is not None, "set_led não foi chamado"
    # RGB escalado: 200*0.25=50, 100*0.25=25, 50*0.25=12
    r, g, b = fc.last_led.color
    assert r == 50, f"canal R esperado 50, recebeu {r}"
    assert g == 25, f"canal G esperado 25, recebeu {g}"
    assert b == 12, f"canal B esperado 12, recebeu {b}"


def test_apply_propaga_multi_position(isolated_profiles_dir: Path):
    """SCHEMA-MULTI-POSITION-PARAMS-01 / A-06: params aninhado chega ao controller.

    Cria perfil com `left` = MultiPositionFeedback (params aninhado de 10)
    e `right` = MultiPositionVibration (params aninhado de 10). Após apply(),
    verifica que `set_trigger` foi chamado para ambos os lados com o
    `TriggerEffect` idêntico ao que a factory canônica produz.
    """
    from hefesto_dualsense4unix.core.trigger_effects import (
        TriggerMode,
        multi_position_feedback,
        multi_position_vibration,
    )

    left_nested = [[0], [1], [2], [3], [4], [5], [6], [7], [8], [8]]
    right_nested = [[0], [0], [2], [2], [4], [5], [6], [7], [8], [8]]
    profile = _mk_profile(
        "multi_pos",
        triggers=TriggersConfig(
            left=TriggerConfig(mode="MultiPositionFeedback", params=left_nested),
            right=TriggerConfig(mode="MultiPositionVibration", params=right_nested),
        ),
    )

    fc = FakeController()
    fc.connect()
    manager = ProfileManager(controller=fc)
    manager.apply(profile)

    triggers = [c for c in fc.commands if c.kind == "set_trigger"]
    assert len(triggers) == 2

    # Left: feedback — compara byte a byte com a factory direta.
    left_call = next(c for c in triggers if c.payload[0] == "left")
    expected_left = multi_position_feedback([0, 1, 2, 3, 4, 5, 6, 7, 8, 8])
    assert left_call.payload[1].mode == TriggerMode.FEEDBACK
    assert left_call.payload[1].forces == expected_left.forces

    # Right: vibration com frequency=0 (default do formato aninhado).
    right_call = next(c for c in triggers if c.payload[0] == "right")
    expected_right = multi_position_vibration(0, [0, 0, 2, 2, 4, 5, 6, 7, 8, 8])
    assert right_call.payload[1].mode == TriggerMode.VIBRATION
    assert right_call.payload[1].forces == expected_right.forces


def test_apply_brightness_maximo_nao_escala(isolated_profiles_dir: Path):
    """Brightness 1.0 (padrão) não altera os valores RGB."""
    profile = _mk_profile(
        "full_test",
        leds=LedsConfig(lightbar=(200, 100, 50), lightbar_brightness=1.0),
    )
    fc = FakeController()
    fc.connect()
    manager = ProfileManager(controller=fc)
    manager.apply(profile)

    assert fc.last_led is not None
    assert fc.last_led.color == (200, 100, 50)


def test_apply_propaga_player_leds_ao_controller(isolated_profiles_dir: Path):
    """BUG-PLAYER-LEDS-APPLY-01 / A-06: player_leds do perfil chega ao hardware
    via ProfileManager.apply → apply_led_settings → controller.set_player_leds.

    Cenário alvo: usuário marca padrão `0b10101` no editor, salva perfil, troca
    de janela e o autoswitch reaplica o perfil — os 5 LEDs do controle devem
    refletir exatamente o bitmask salvo. Sem a propagação em `apply_led_settings`,
    o perfil aparece correto na GUI mas o hardware mantém a configuração antiga.
    """
    profile = _mk_profile(
        "player_leds_test",
        leds=LedsConfig(
            lightbar=(10, 20, 30),
            player_leds=[True, False, True, False, True],  # 0b10101
        ),
    )
    fc = FakeController()
    fc.connect()
    manager = ProfileManager(controller=fc)
    manager.apply(profile)

    assert fc.last_player_leds == (True, False, True, False, True)
    pl_cmds = [c for c in fc.commands if c.kind == "set_player_leds"]
    assert len(pl_cmds) == 1, "apply() deve chamar set_player_leds exatamente 1x"


def test_apply_propaga_player_leds_todos_apagados(isolated_profiles_dir: Path):
    """Perfil com player_leds=[False]*5 propaga ao controller (apaga os 5 LEDs)."""
    profile = _mk_profile(
        "player_leds_off",
        leds=LedsConfig(
            lightbar=(0, 0, 0),
            player_leds=[False, False, False, False, False],
        ),
    )
    fc = FakeController()
    fc.connect()
    manager = ProfileManager(controller=fc)
    manager.apply(profile)

    assert fc.last_player_leds == (False, False, False, False, False)


def test_activate_propaga_player_leds(isolated_profiles_dir: Path):
    """`activate()` (caminho de profile.switch) também chega ao controller.

    `activate` delega a `apply`; o teste garante que o caminho comum do
    trocar-de-perfil-pela-GUI reenvia os 5 LEDs ao hardware em vez de deixar
    o controle com o padrão antigo.
    """
    save_profile(
        _mk_profile(
            "p2_canonico",
            leds=LedsConfig(
                lightbar=(100, 100, 100),
                player_leds=[False, True, False, True, False],  # 0b01010 = Player 2
            ),
        )
    )
    fc = FakeController()
    fc.connect()
    store = StateStore()
    manager = ProfileManager(controller=fc, store=store)
    manager.activate("p2_canonico")
    assert fc.last_player_leds == (False, True, False, True, False)


# -- PERFIL-01 (4P-01): perfil atinge TODOS os controles, mesmo com alvo -----
#
# Bug provado no código (agravante da revisão): `ProfileManager.apply()` usava
# os setters broadcast que RESPEITAM `_output_target_key` — com um alvo
# selecionado na GUI, ativar um perfil (manual OU via autoswitch, que passa
# pela MESMA cadeia `activate()`) aplicava só no alvo.


def _backend_com_dois_controles():
    """PyDualSenseController real com dois handles stubados (keys MAC aa:bb:cc)."""
    from hefesto_dualsense4unix.core.backend_pydualsense import PyDualSenseController
    from tests.unit.test_backend_multi_controller import (
        KEY_1,
        KEY_2,
        _FakeHandle,
        _null_evdev,
    )

    inst = PyDualSenseController(evdev_reader=_null_evdev())
    h1, h2 = _FakeHandle(), _FakeHandle()
    inst._handles = {KEY_1: h1, KEY_2: h2}
    inst._primary_key = KEY_1
    return inst, h1, h2


def test_activate_manual_com_alvo_selecionado_atinge_todos(
    isolated_profiles_dir: Path,
):
    """Ativação MANUAL com alvo=Controle 2 no seletor → as DUAS lightbars."""
    save_profile(_mk_profile("shooter"))
    backend, h1, h2 = _backend_com_dois_controles()
    backend.set_output_target(1)  # usuária estava mexendo só no Controle 2

    manager = ProfileManager(controller=backend, store=StateStore())
    manager.activate("shooter")

    for h in (h1, h2):
        assert h.light.colors[-1] == (10, 20, 30)
        assert h.triggerR.forces == list(rigid(5, 200).forces)
    # O seletor da usuária segue como estava (estado de UI preservado).
    assert backend.get_output_target_index() == 1


def test_activate_via_autoswitch_com_alvo_selecionado_atinge_todos(
    isolated_profiles_dir: Path,
):
    """Mesma cadeia pelo AUTOSWITCH (`AutoSwitcher._activate` → `activate`):
    toda troca automática com alvo ativo também aplicava só no alvo."""
    from hefesto_dualsense4unix.profiles.autoswitch import AutoSwitcher

    save_profile(_mk_profile("shooter"))
    backend, h1, h2 = _backend_com_dois_controles()
    backend.set_output_target(1)

    manager = ProfileManager(controller=backend, store=StateStore())
    switcher = AutoSwitcher(manager=manager, window_reader=lambda: {})
    switcher._activate("shooter", {"wm_class": "shooter_class"})

    for h in (h1, h2):
        assert h.light.colors[-1] == (10, 20, 30)
        assert h.triggerR.forces == list(rigid(5, 200).forces)


def test_activate_substitui_o_mapa_de_overrides(isolated_profiles_dir: Path):
    """Reset na ativação: o override em memória do perfil anterior não pode
    ressuscitar no hotplug sob o perfil novo (ciclo de vida explícito)."""
    from hefesto_dualsense4unix.core.controller import OutputSpec

    save_profile(_mk_profile("shooter"))
    backend, _h1, _h2 = _backend_com_dois_controles()
    backend.apply_output_for("aabbcc000002", OutputSpec(led=(0, 255, 0)))
    assert backend._desired_by_uniq  # override registrado

    manager = ProfileManager(controller=backend, store=StateStore())
    manager.activate("shooter")

    assert backend._desired_by_uniq == {}  # mapa substituído (vazio: sem campo)
    assert backend._desired_default.led == (10, 20, 30)


def test_activate_sem_secao_mic_nao_toca_o_mic_led(isolated_profiles_dir: Path):
    """AUDIT-FINDING-PROFILE-MIC-LED-RESET-01: o LED do mic nunca é COLATERAL.

    **NOTA DATADA — 18/08/2026 (PERFIL-GUARDA-O-MIC-01).** Este caso se chamava
    `test_activate_nao_toca_o_mic_led` e afirmava "profile switch JAMAIS mexe
    no LED do mic". A decisão medida CONTINUA valendo, e o ESCOPO dela é que ficou
    explícito: o proibido é o LED como **colateral** — perfil que não pediu nada
    apagando a luz vermelha do microfone dela ao trocar de janela. O que passou
    a ser permitido, porque é o oposto disso, é o LED como **consequência de um
    pedido explícito dela**: um perfil que GUARDA `mic.muted` porque ela o
    salvou, aplicado numa troca EXPLÍCITA de perfil (a exceção MIC-GRAVACAO-01,
    escrita em `ProfileManager.apply_mic`).

    O que este caso trava, e é o que importa: **sem seção `mic`, jamais.**
    """
    save_profile(_mk_profile("shooter"))
    fc = FakeController()
    fc.connect()
    manager = ProfileManager(controller=fc, store=StateStore())
    manager.activate("shooter")
    assert fc.mic_led_history == []


# ---------------------------------------------------------------------------
# PERFIL-GUARDA-O-MIC-01 (18/08/2026) — ativar um perfil aplica o microfone
# ---------------------------------------------------------------------------


class _MicEspiao:
    """Dublê do `mic_applier`: guarda as chamadas, devolve "aplicado"."""

    def __init__(self) -> None:
        self.chamadas: list[tuple[int | None, bool | None, str]] = []

    def __call__(
        self,
        volume: int | None,
        muted: bool | None,
        *,
        uniq: str | None = None,
        origin: str = "manual",
    ) -> str:
        self.chamadas.append((volume, muted, origin))
        return "aplicado"


def _mk_profile_com_mic(
    name: str = "gravando",
    *,
    volume: int | None = 70,
    muted: bool | None = None,
) -> Profile:
    from hefesto_dualsense4unix.profiles.schema import ProfileMicConfig

    return _mk_profile(
        name,
        mic=ProfileMicConfig(
            button_toggles_system=True, volume=volume, muted=muted
        ),
    )


def test_ativar_perfil_com_mic_aplica_volume(isolated_profiles_dir: Path):
    """O pedido dela inteiro: *"temos que salvar isso no perfil sempre"*.

    Medido em 18/08/2026: nenhum dos 18 perfis dela tinha a seção `mic`, e
    ativar um perfil NUNCA tocava no microfone — a seção existia no esquema
    desde 16/08 e nada a lia.

    MORDIDA: apague a linha `self.apply_mic(...)` de
    `ProfileManager.apply_emulation` (ou o `mic_applier=` da injeção) e este
    caso fica vermelho.
    """
    save_profile(_mk_profile_com_mic("gravando", volume=70))
    espiao = _MicEspiao()
    manager = ProfileManager(
        controller=FakeController(), store=StateStore(), mic_applier=espiao
    )
    relatorio: dict[str, str] = {}
    manager.activate("gravando", origin="manual", relatorio=relatorio)

    assert espiao.chamadas, (
        "o applier do microfone não foi chamado — ativar o perfil continua "
        "não tocando no mic (a queixa de 18/08)"
    )
    volume, _muted, _origin = espiao.chamadas[0]
    assert volume == 70, f"o volume que chegou ao applier foi {volume!r}"
    assert relatorio.get("mic") == "aplicado"


def test_perfil_sem_secao_mic_nao_chama_o_applier(isolated_profiles_dir: Path):
    """Sem opinião é silêncio, não ordem — o outro sentido da mesma queixa.

    Mesmo contrato do alto-falante: perfil que não pediu nada não impõe nada.

    MORDIDA (medida em 18/08/2026): `apply_mic` tem DUAS guardas de ausência —
    o `or secao is None` e o `volume is None and muted is None` logo abaixo —, e
    a segunda absorve a primeira num perfil legado. Arrancar só uma delas deixa
    este caso verde; arrancar as DUAS o deixa vermelho, que é o que prova que a
    ausência de opinião é o que segura a chamada. Sem elas, todo perfil legado
    passaria a mexer no microfone dela.
    """
    save_profile(_mk_profile("sem_mic"))
    espiao = _MicEspiao()
    manager = ProfileManager(
        controller=FakeController(), store=StateStore(), mic_applier=espiao
    )
    manager.activate("sem_mic", origin="manual")
    assert espiao.chamadas == []


def test_o_jogo_nao_rouba_o_mudo_durante_a_gravacao(isolated_profiles_dir: Path):
    """MIC-GRAVACAO-01 — a exceção nomeada, e a razão de ela existir.

    O `muted` do perfil é o mudo do FIRMWARE, o mesmo que apaga o LED vermelho.
    A trava manual de áudio sozinha NÃO basta para protegê-lo: o perfil de JOGO
    limpa as categorias travadas ao entrar (`profiles/autoswitch.py`, exceção
    F2 — a troca por jogo não pode ficar silenciada para sempre por um
    `led.set` da manhã). Sem esta guarda, abrir um jogo durante uma gravação
    roubaria o mudo do microfone dela.

    A separação: o `volume` (ganho da fonte no PipeWire, não apaga luz nenhuma)
    atravessa toda ativação; o `muted` só a troca EXPLÍCITA de perfil.

    MORDIDA: apague o `if origin != "manual": muted = None` de `apply_mic` e
    este caso fica vermelho na primeira asserção.
    """
    save_profile(_mk_profile_com_mic("jogo", volume=70, muted=False))
    espiao = _MicEspiao()
    manager = ProfileManager(
        controller=FakeController(), store=StateStore(), mic_applier=espiao
    )

    manager.activate("jogo", origin="autoswitch")
    assert espiao.chamadas == [(70, None, "autoswitch")], (
        "o mudo do perfil atravessou uma troca AUTOMÁTICA de perfil — abrir um "
        f"jogo no meio da gravação dela desfaria o mudo: {espiao.chamadas!r}"
    )

    manager.activate("jogo", origin="system")
    assert espiao.chamadas[-1] == (70, None, "system"), (
        "o mudo do perfil atravessou o restauro de boot/reconexão"
    )

    manager.activate("jogo", origin="manual")
    assert espiao.chamadas[-1] == (70, False, "manual"), (
        "ela trocou de perfil DE PROPÓSITO e o mudo que ela salvou não foi "
        f"aplicado: {espiao.chamadas[-1]!r}"
    )


def test_a_trava_manual_de_audio_vence_o_perfil_no_mic(isolated_profiles_dir: Path):
    """Ela acabou de mexer no microfone na mão: o perfil não pisa.

    Mesma disciplina do alto-falante (categoria `"audio"` do `StateStore`), e
    agora com o `mic.set`/`mic.volume.set` armando a trava também.

    MORDIDA: tire o bloco `if "audio" in self._categorias_travadas()` de
    `apply_mic` e este caso fica vermelho.
    """
    save_profile(_mk_profile_com_mic("gravando", volume=70))
    espiao = _MicEspiao()
    store = StateStore()
    store.mark_manual_trigger_active("audio")
    manager = ProfileManager(
        controller=FakeController(), store=store, mic_applier=espiao
    )
    relatorio: dict[str, str] = {}
    manager.activate("gravando", origin="autoswitch", relatorio=relatorio)

    assert espiao.chamadas == []
    assert relatorio.get("mic") == "ignorado_trava_manual"


# ---------------------------------------------------------------------------
# PERFIL-04: ativação aplica o mapa `controllers` do perfil por-uniq
# ---------------------------------------------------------------------------


def _mk_profile_com_override(name: str = "vitoria") -> Profile:
    """Perfil com seção global + override de lightbar SÓ para o segundo MAC."""
    from hefesto_dualsense4unix.profiles.schema import ControllerOverrides
    from tests.unit.test_backend_multi_controller import UNIQ_2

    return _mk_profile(
        name,
        controllers={
            UNIQ_2: ControllerOverrides(
                leds=LedsConfig(
                    lightbar=(0, 0, 255),
                    player_leds=[False, True, False, True, False],
                )
            )
        },
    )


def test_activate_aplica_override_so_no_alvo(isolated_profiles_dir: Path):
    """O pedido dela aplicado: ativar o perfil pinta SÓ o controle do
    override de azul — o outro recebe a seção global (o merge do PERFIL-01
    cuida do hotplug depois)."""
    from tests.unit.test_backend_multi_controller import UNIQ_2

    save_profile(_mk_profile_com_override("vitoria"))
    backend, h1, h2 = _backend_com_dois_controles()

    manager = ProfileManager(controller=backend, store=StateStore())
    manager.activate("vitoria")

    assert h1.light.colors[-1] == (10, 20, 30)  # global
    assert h2.light.colors[-1] == (0, 0, 255)  # override do alvo
    # O mapa em memória ficou registrado para o hotplug reaplicar.
    assert backend._desired_by_uniq[UNIQ_2].led == (0, 0, 255)
    assert backend._desired_by_uniq[UNIQ_2].player_leds == (
        False, True, False, True, False,
    )
    # Override sem seção triggers = sem opinião (merge por campo no replug).
    assert backend._desired_by_uniq[UNIQ_2].trigger_left is None


def test_activate_registra_override_de_desconectado(isolated_profiles_dir: Path):
    """Override de controle DESCONECTADO fica registrado no mapa (a escrita
    de hardware é pulada) — é o que faz o religar do BT receber a cor dele
    (teste de fogo do PERFIL-05c)."""
    from hefesto_dualsense4unix.core.backend_pydualsense import PyDualSenseController
    from tests.unit.test_backend_multi_controller import (
        KEY_1,
        UNIQ_2,
        _FakeHandle,
        _null_evdev,
    )

    save_profile(_mk_profile_com_override("vitoria"))
    backend = PyDualSenseController(evdev_reader=_null_evdev())
    h1 = _FakeHandle()
    backend._handles = {KEY_1: h1}  # só o Controle 1 conectado
    backend._primary_key = KEY_1

    manager = ProfileManager(controller=backend, store=StateStore())
    manager.activate("vitoria")

    assert h1.light.colors[-1] == (10, 20, 30)  # o conectado ficou no global
    assert backend._desired_by_uniq[UNIQ_2].led == (0, 0, 255)  # registrado


def test_activate_override_escala_brilho_no_mesmo_caminho(
    isolated_profiles_dir: Path,
):
    """Brilho do override passa pelo MESMO caminho de escala do global
    (`LedSettings.apply_brightness`): o hardware recebe a cor JÁ escalada."""
    from hefesto_dualsense4unix.profiles.schema import ControllerOverrides
    from tests.unit.test_backend_multi_controller import UNIQ_2

    save_profile(
        _mk_profile(
            "vitoria",
            controllers={
                UNIQ_2: ControllerOverrides(
                    leds=LedsConfig(
                        lightbar=(100, 200, 50), lightbar_brightness=0.5
                    )
                )
            },
        )
    )
    backend, _h1, h2 = _backend_com_dois_controles()
    manager = ProfileManager(controller=backend, store=StateStore())
    manager.activate("vitoria")

    assert h2.light.colors[-1] == (50, 100, 25)
    assert backend._desired_by_uniq[UNIQ_2].led == (50, 100, 25)


# ---------------------------------------------------------------------------
# Fix do review (2026-07-16, MED): override PARCIAL dentro da seção não
# densifica — campo não escrito herda o GLOBAL (merge por campo de verdade)
# ---------------------------------------------------------------------------


def test_activate_override_parcial_herda_player_e_brilho_do_global(
    isolated_profiles_dir: Path,
):
    """O EXATO JSON do aceite 1 do PERFIL-02, escrito à mão: override só com
    a cor. Os campos NÃO escritos herdam o GLOBAL — antes, os defaults do
    schema densificavam e o controle acordava com player-LEDs TODOS apagados
    e a cor a brilho cheio (a resolução-por-objeto refutada, um nível
    abaixo)."""
    from tests.unit.test_backend_multi_controller import UNIQ_2

    raw = _mk_profile(
        "vitoria",
        leds=LedsConfig(
            lightbar=(129, 61, 156),
            player_leds=[True, False, False, False, False],
            lightbar_brightness=0.5,
        ),
    ).model_dump(mode="json")
    raw["controllers"] = {UNIQ_2: {"leds": {"lightbar": [0, 255, 0]}}}
    save_profile(Profile.model_validate(raw))

    backend, _h1, h2 = _backend_com_dois_controles()
    manager = ProfileManager(controller=backend, store=StateStore())
    manager.activate("vitoria")

    # A cor escrita herda o brilho 0.5 do GLOBAL (verde escalado, não cheio).
    assert h2.light.colors[-1] == (0, 127, 0)
    assert backend._desired_by_uniq[UNIQ_2].led == (0, 127, 0)
    # Campos não escritos ficam SEM OPINIÃO no mapa → hotplug herda o global
    # (antes: player_leds=(False,)*5 apagava o player 1 aceso do global).
    assert backend._desired_by_uniq[UNIQ_2].player_leds is None
    assert backend._desired_by_uniq[UNIQ_2].trigger_left is None


def test_activate_override_parcial_de_gatilho_nao_desliga_o_outro_lado(
    isolated_profiles_dir: Path,
):
    """Override só de `left`: o `right` daquele controle segue o GLOBAL —
    antes o default `Off` densificado desligava o gatilho direito global do
    controle do override."""
    from tests.unit.test_backend_multi_controller import UNIQ_2

    raw = _mk_profile("vitoria").model_dump(mode="json")
    raw["controllers"] = {
        UNIQ_2: {"triggers": {"left": {"mode": "Rigid", "params": [1, 100]}}}
    }
    save_profile(Profile.model_validate(raw))

    backend, _h1, h2 = _backend_com_dois_controles()
    manager = ProfileManager(controller=backend, store=StateStore())
    manager.activate("vitoria")

    # O lado escrito aplicou; o NÃO escrito manteve o global (Rigid 5,200).
    assert h2.triggerL.forces == list(rigid(1, 100).forces)
    assert h2.triggerR.forces == list(rigid(5, 200).forces)
    assert backend._desired_by_uniq[UNIQ_2].trigger_right is None
