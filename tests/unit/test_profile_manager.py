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
    assert picked.name == "shooter"


def test_criteria_vence_catch_all_de_prioridade_maior(isolated_profiles_dir: Path):
    """R-01 (auditoria 23/07): especificidade vem ANTES de prioridade."""
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


def test_select_for_window_nao_elege_o_match_any(isolated_profiles_dir: Path):
    """NOTA DATADA — 01/10/2026 (`D-2909-O-HEFESTO-ABRE-NA-ESCOLHA-DELA`, item"""
    save_profile(
        _mk_profile("shooter", match=MatchCriteria(window_class=["DoomEternal"]))
    )
    save_profile(Profile(name="fallback", match=MatchAny(), priority=0))

    fc = FakeController()
    fc.connect()
    manager = ProfileManager(controller=fc)
    assert manager.select_for_window({"wm_class": "Inkscape"}) is None
    assert manager.select_for_window({"wm_class": "DoomEternal"}).name == "shooter"


def test_select_for_window_sem_match_sem_fallback(isolated_profiles_dir: Path):
    save_profile(_mk_profile("shooter", match=MatchCriteria(window_class=["X"])))

    fc = FakeController()
    fc.connect()
    manager = ProfileManager(controller=fc)
    picked = manager.select_for_window({"wm_class": "Nada"})
    assert picked is None


def test_janela_de_jogo_sem_regra_propria_nao_cai_no_catch_all(
    isolated_profiles_dir: Path,
):
    """O caso medido: nenhum perfil opina sobre este jogo ⇒ None (e o"""
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
    """UNIFICA-PREDICADO-01: o veto R-21 não pode depender da CAIXA da janela."""
    save_profile(Profile(name="vitoria", match=MatchAny(), priority=5))
    save_profile(Profile(name="meu_perfil", match=MatchAny(), priority=1))

    fc = FakeController()
    fc.connect()
    manager = ProfileManager(controller=fc)
    assert manager.select_for_window({"wm_class": wm_class}) is None
    assert manager.select_for_window_ex({"wm_class": wm_class}) == (
        None,
        MOTIVO_JOGO_SEM_PERFIL_PROPRIO,
    )


def test_veto_r21_em_caixa_alta_sem_candidato_nenhum(isolated_profiles_dir: Path):
    """O ramo vizinho do veto (ZERO candidatos no disco) pelo mesmo predicado."""
    fc = FakeController()
    fc.connect()
    manager = ProfileManager(controller=fc)
    assert manager.select_for_window_ex({"wm_class": "STEAM_APP_2111190"}) == (
        None,
        MOTIVO_JOGO_SEM_PERFIL_PROPRIO,
    )


def test_regra_propria_do_jogo_continua_vencendo(isolated_profiles_dir: Path):
    """O veto é só quando os ÚNICOS candidatos são catch-all — havendo regra"""
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
    """Só CATCH-ALL é vetado. Um perfil que casou por título/processo opinou"""
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


def test_catch_all_nao_entra_nem_em_janela_comum(isolated_profiles_dir: Path):
    """NOTA DATADA — 01/10/2026 (`D-2909-O-HEFESTO-ABRE-NA-ESCOLHA-DELA`): o"""
    save_profile(Profile(name="vitoria", match=MatchAny(), priority=5))

    fc = FakeController()
    fc.connect()
    manager = ProfileManager(controller=fc)
    assert manager.select_for_window_ex({"wm_class": "firefox"}) == (
        None, "sem_candidato")


def test_wm_class_parecida_com_steam_app_nao_e_vetada(isolated_profiles_dir: Path):
    """`steam_app_` sem número, ou com sufixo, NÃO é janela de jogo da Steam —"""
    save_profile(Profile(name="vitoria", match=MatchAny(), priority=5))

    fc = FakeController()
    fc.connect()
    manager = ProfileManager(controller=fc)
    for wm in ("steam_app_", "steam_app_abc", "xsteam_app_1", "steam_app_1_x"):
        assert manager.select_for_window_ex({"wm_class": wm}) == (
            None, "sem_candidato"), wm


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
    """BUG-PROFILE-DELETE-ACTIVE-SLUG-01: delete por slug deve limpar o active."""
    save_profile(_mk_profile("Ação"))
    fc = FakeController()
    fc.connect()
    store = StateStore()
    manager = ProfileManager(controller=fc, store=store)
    manager.activate("Ação")
    assert store.active_profile == "Ação"
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
    r, g, b = fc.last_led.color
    assert r == 80, f"canal R esperado 80, recebeu {r}"
    assert g == 40, f"canal G esperado 40, recebeu {g}"
    assert b == 20, f"canal B esperado 20, recebeu {b}"


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

    left_call = next(c for c in triggers if c.payload[0] == "left")
    expected_left = multi_position_feedback([0, 1, 2, 3, 4, 5, 6, 7, 8, 8])
    assert left_call.payload[1].mode == TriggerMode.FEEDBACK
    assert left_call.payload[1].forces == expected_left.forces

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
    via ProfileManager.apply → controller.set_player_leds.

    Cenário alvo: usuário marca padrão `0b10101` no editor, salva perfil, troca
    de janela e o autoswitch reaplica o perfil — os 5 LEDs do controle devem
    refletir exatamente o bitmask salvo. Sem a propagação no apply, o perfil
    aparece correto na tela mas o hardware mantém a configuração antiga.
    """
    profile = _mk_profile(
        "player_leds_test",
        leds=LedsConfig(
            lightbar=(10, 20, 30),
            player_leds=[True, False, True, False, True],
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
                player_leds=[False, True, False, True, False],
            ),
        )
    )
    fc = FakeController()
    fc.connect()
    store = StateStore()
    manager = ProfileManager(controller=fc, store=store)
    manager.activate("p2_canonico")
    assert fc.last_player_leds == (False, True, False, True, False)


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
    backend.set_output_target(1)

    manager = ProfileManager(controller=backend, store=StateStore())
    manager.activate("shooter")

    for h in (h1, h2):
        assert h.light.colors[-1] == (10, 20, 30)
        assert h.triggerR.forces == list(rigid(5, 200).forces)
    assert backend.get_output_target_index() == 1


def test_activate_via_autoswitch_com_alvo_selecionado_atinge_todos(
    isolated_profiles_dir: Path,
):
    """Mesma cadeia pelo AUTOSWITCH (`AutoSwitcher._activate` → `activate`):"""
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
    """Reset na ativação: o override em memória do perfil anterior não pode"""
    from hefesto_dualsense4unix.core.controller import OutputSpec

    save_profile(_mk_profile("shooter"))
    backend, _h1, _h2 = _backend_com_dois_controles()
    backend.apply_output_for("aabbcc000002", OutputSpec(led=(0, 255, 0)))
    assert backend._desired_by_uniq

    manager = ProfileManager(controller=backend, store=StateStore())
    manager.activate("shooter")

    assert backend._desired_by_uniq == {}
    assert backend._desired_default.led == (10, 20, 30)


def test_activate_sem_secao_mic_nao_toca_o_mic_led(isolated_profiles_dir: Path):
    """AUDIT-FINDING-PROFILE-MIC-LED-RESET-01: o LED do mic nunca é COLATERAL."""
    save_profile(_mk_profile("shooter"))
    fc = FakeController()
    fc.connect()
    manager = ProfileManager(controller=fc, store=StateStore())
    manager.activate("shooter")
    assert fc.mic_led_history == []


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
    """O pedido inteiro: *"temos que salvar isso no perfil sempre"*."""
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
    """Sem opinião é silêncio, não ordem — o outro sentido da mesma queixa."""
    save_profile(_mk_profile("sem_mic"))
    espiao = _MicEspiao()
    manager = ProfileManager(
        controller=FakeController(), store=StateStore(), mic_applier=espiao
    )
    manager.activate("sem_mic", origin="manual")
    assert espiao.chamadas == []


def test_o_jogo_nao_rouba_o_mudo_durante_a_gravacao(isolated_profiles_dir: Path):
    """MIC-GRAVACAO-01 — a exceção nomeada, e a razão de ela existir."""
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
    assert espiao.chamadas[-1] == (70, None, "manual"), (
        "a troca explícita de perfil levou o mudo — ele é do controle, não do "
        f"perfil: {espiao.chamadas[-1]!r}"
    )


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
    """O pedido aplicado: ativar o perfil pinta SÓ o controle do"""
    from tests.unit.test_backend_multi_controller import UNIQ_2

    save_profile(_mk_profile_com_override("vitoria"))
    backend, h1, h2 = _backend_com_dois_controles()

    manager = ProfileManager(controller=backend, store=StateStore())
    manager.activate("vitoria")

    assert h1.light.colors[-1] == (10, 20, 30)
    assert h2.light.colors[-1] == (0, 0, 255)
    assert backend._desired_by_uniq[UNIQ_2].led == (0, 0, 255)
    assert backend._desired_by_uniq[UNIQ_2].player_leds == (
        False, True, False, True, False,
    )
    assert backend._desired_by_uniq[UNIQ_2].trigger_left is None


def test_activate_registra_override_de_desconectado(isolated_profiles_dir: Path):
    """Override de controle DESCONECTADO fica registrado no mapa (a escrita"""
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
    backend._handles = {KEY_1: h1}
    backend._primary_key = KEY_1

    manager = ProfileManager(controller=backend, store=StateStore())
    manager.activate("vitoria")

    assert h1.light.colors[-1] == (10, 20, 30)
    assert backend._desired_by_uniq[UNIQ_2].led == (0, 0, 255)


def test_activate_override_escala_brilho_no_mesmo_caminho(
    isolated_profiles_dir: Path,
):
    """Brilho do override passa pelo MESMO caminho de escala do global"""
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

    assert h2.light.colors[-1] == (60, 120, 30)
    assert backend._desired_by_uniq[UNIQ_2].led == (60, 120, 30)


def test_activate_override_parcial_herda_player_e_brilho_do_global(
    isolated_profiles_dir: Path,
):
    """O EXATO JSON do aceite 1 do PERFIL-02, escrito à mão: override só com"""
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

    assert h2.light.colors[-1] == (0, 153, 0)
    assert backend._desired_by_uniq[UNIQ_2].led == (0, 153, 0)
    assert backend._desired_by_uniq[UNIQ_2].player_leds is None
    assert backend._desired_by_uniq[UNIQ_2].trigger_left is None


def test_activate_override_parcial_de_gatilho_nao_desliga_o_outro_lado(
    isolated_profiles_dir: Path,
):
    """Override só de `left`: o `right` daquele controle segue o GLOBAL —"""
    from tests.unit.test_backend_multi_controller import UNIQ_2

    raw = _mk_profile("vitoria").model_dump(mode="json")
    raw["controllers"] = {
        UNIQ_2: {"triggers": {"left": {"mode": "Rigid", "params": [1, 100]}}}
    }
    save_profile(Profile.model_validate(raw))

    backend, _h1, h2 = _backend_com_dois_controles()
    manager = ProfileManager(controller=backend, store=StateStore())
    manager.activate("vitoria")

    assert h2.triggerL.forces == list(rigid(1, 100).forces)
    assert h2.triggerR.forces == list(rigid(5, 200).forces)
    assert backend._desired_by_uniq[UNIQ_2].trigger_right is None
