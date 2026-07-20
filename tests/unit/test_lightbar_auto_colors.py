"""COR-04 — GUI da aba Lightbar: toggle "Cores automáticas por controle".

Cobre o item COR-04 do sprint 2026-07-16-sprint-cores-e-led-automaticos:

  - o checkbox reflete o draft (GLOBAL, nunca o efetivo do alvo) e o campo
    sobrevive ao round-trip from_profile → GUI → to_profile, com o mapa
    ``controllers`` intacto;
  - semântica D4: aplicar COR com alvo "Todos" e auto ligado desliga o
    toggle no draft com aviso visível (toast espião), inclusive nos botões
    "Aplicar no controle" e "Apagar" (que levam o toggle no IPC parcial);
  - religar o automático NÃO mexe nos overrides por-controle;
  - "Voltar ao automático" remove SÓ a cor explícita do alvo (player-LEDs e
    gatilhos próprios ficam); entrada que esvazia some do mapa;
  - "Voltar todos ao automático" limpa as cores explícitas de todo mundo e
    religa o auto;
  - perfil antigo sem o campo → checkbox ligado (default do schema);
  - DraftApplier propaga ``leds.auto_player_colors`` ao registro de
    identidade (espelho da ativação de perfil), com brilho junto (D11).

Sem display: instâncias parciais via construtor próprio + widgets fakes —
mesmo padrão de tests/unit/test_controller_target_ui.py.
"""
# ruff: noqa: E402  (imports após o pin de versão do gi — padrão da casa)
from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import gi
import pytest

# BUG-TEST-GDK-VERSION-PIN-01: pina Gdk/Gtk 3.0 ANTES de importar módulos da
# GUI — sem isso o gi pode carregar Gdk 4.0 e envenenar o processo inteiro.
gi.require_version("Gdk", "3.0")
gi.require_version("Gtk", "3.0")

from hefesto_dualsense4unix.app.actions import lightbar_actions
from hefesto_dualsense4unix.app.actions.lightbar_actions import (
    _AVISO_D4,
    LightbarActionsMixin,
)
from hefesto_dualsense4unix.app.draft_config import DraftConfig
from hefesto_dualsense4unix.daemon.ipc_draft_applier import DraftApplier
from hefesto_dualsense4unix.daemon.subsystems import identity
from hefesto_dualsense4unix.profiles.schema import (
    ControllerOverrides,
    LedsConfig,
    MatchAny,
    Profile,
)

#: MACs forjados da faixa permitida (tests/unit/test_anonimato_de_fixtures.py).
UNIQ_1 = "aabbcc000001"
UNIQ_2 = "aabbcc000002"


# ---------------------------------------------------------------------------
# Fakes de widget + host parcial do mixin
# ---------------------------------------------------------------------------


class _FakeCheck:
    """Stub de GtkCheckButton: emite "toggled" só quando o estado MUDA."""

    def __init__(self) -> None:
        self.active = False
        self._handlers: list[Any] = []

    def connect(self, _signal: str, handler: Any) -> None:
        self._handlers.append(handler)

    def set_active(self, value: bool) -> None:
        value = bool(value)
        if self.active == value:
            return
        self.active = value
        for handler in list(self._handlers):
            handler(self)

    def get_active(self) -> bool:
        return self.active


class _FakeRGBA:
    def __init__(self, r: float, g: float, b: float) -> None:
        self.red = r
        self.green = g
        self.blue = b
        self.alpha = 1.0


class _FakeColorButton:
    def __init__(self, rgb: tuple[int, int, int]) -> None:
        self._rgba = _FakeRGBA(rgb[0] / 255, rgb[1] / 255, rgb[2] / 255)

    def get_rgba(self) -> _FakeRGBA:
        return self._rgba


class _Host(LightbarActionsMixin):
    """Hospedeiro mínimo: draft + alvo + widgets fakes + toast espião."""

    def __init__(
        self,
        draft: DraftConfig,
        uniq: str | None = None,
        widgets: dict[str, Any] | None = None,
    ) -> None:
        self.draft = draft
        self._edit_target_uniq = uniq
        self._widgets = widgets or {}
        self._toasts: list[str] = []
        self._refresh_guard = False

    def _get(self, widget_id: str) -> Any:
        return self._widgets.get(widget_id)

    def _toast_light(self, msg: str) -> None:
        self._toasts.append(msg)


def _host_com_checkbox(
    draft: DraftConfig, uniq: str | None = None
) -> tuple[_Host, _FakeCheck]:
    check = _FakeCheck()
    host = _Host(draft, uniq, widgets={"auto_player_colors_check": check})
    host.install_lightbar_tab()  # fia o "toggled" em código (COR-04)
    return host, check


# ---------------------------------------------------------------------------
# Perfis de apoio
# ---------------------------------------------------------------------------


def _perfil(
    auto: bool | None = None,
    controllers: dict[str, Any] | None = None,
) -> Profile:
    """Perfil roxo da casa; ``auto=None`` = perfil ANTIGO (campo ausente)."""
    leds_kwargs: dict[str, Any] = {
        "lightbar": (129, 61, 156),
        "player_leds": [True, False, False, False, False],
        "lightbar_brightness": 1.0,
    }
    if auto is not None:
        leds_kwargs["auto_player_colors"] = auto
    return Profile(
        name="vitoria",
        match=MatchAny(),
        priority=5,
        leds=LedsConfig(**leds_kwargs),
        controllers=controllers,
    )


def _override_verde_completo() -> ControllerOverrides:
    """Override com cor + player-LEDs + gatilho próprios (parcial-explícito)."""
    return ControllerOverrides.model_validate(
        {
            "leds": {
                "lightbar": [0, 255, 0],
                "lightbar_brightness": 0.5,
                "player_leds": [False, True, False, True, False],
            },
            "triggers": {"right": {"mode": "Rigid", "params": [5, 200]}},
        }
    )


# ---------------------------------------------------------------------------
# Round-trip: from_profile → GUI → to_profile
# ---------------------------------------------------------------------------


def test_from_profile_le_auto_false_e_checkbox_mostra_desligado() -> None:
    draft = DraftConfig.from_profile(_perfil(auto=False))
    assert draft.leds.auto_player_colors is False

    host, check = _host_com_checkbox(draft)
    check.active = True  # estado visual divergente de propósito
    host._refresh_lightbar_from_draft()
    assert check.get_active() is False  # GUI mostra desligado
    # O refresh programático não pode ter mexido no draft (guard).
    assert host.draft.leds.auto_player_colors is False


def test_perfil_antigo_sem_o_campo_checkbox_ligado() -> None:
    """Perfil salvo antes do COR-03/04 valida com o default True do schema."""
    perfil = _perfil(auto=None)
    assert "auto_player_colors" not in perfil.leds.model_fields_set
    draft = DraftConfig.from_profile(perfil)
    assert draft.leds.auto_player_colors is True

    host, check = _host_com_checkbox(draft)
    host._refresh_lightbar_from_draft()
    assert check.get_active() is True


def test_round_trip_preserva_auto_false_e_mapa_controllers() -> None:
    """from_profile(auto=False + override) → to_profile: nada se perde."""
    perfil = _perfil(auto=False, controllers={UNIQ_2: _override_verde_completo()})
    draft = DraftConfig.from_profile(perfil)

    salvo = draft.to_profile("vitoria")
    assert salvo.leds.auto_player_colors is False
    assert salvo.controllers is not None
    override = salvo.controllers[UNIQ_2]
    assert tuple(override.leds.lightbar) == (0, 255, 0)
    assert override.triggers.right.mode == "Rigid"
    # O toggle é do PERFIL: o override não pode ter ganho o campo no save.
    assert "auto_player_colors" not in override.leds.model_fields_set


def test_to_ipc_dict_leva_o_toggle_na_secao_leds() -> None:
    draft = DraftConfig.from_profile(_perfil(auto=False))
    assert draft.to_ipc_dict()["leds"]["auto_player_colors"] is False
    draft_on = DraftConfig.from_profile(_perfil(auto=True))
    assert draft_on.to_ipc_dict()["leds"]["auto_player_colors"] is True


def test_override_criado_pela_gui_nao_ganha_o_campo() -> None:
    """with_controller_leds continua emitindo override SEM o toggle."""
    draft = DraftConfig.from_profile(_perfil(auto=True))
    base = draft.effective_leds_for(UNIQ_2)
    novo = draft.with_controller_leds(
        UNIQ_2, base.model_copy(update={"lightbar_rgb": (0, 0, 255)})
    )
    override = novo.controller_override(UNIQ_2)
    assert override is not None and override.leds is not None
    assert "auto_player_colors" not in override.leds.model_fields_set


# ---------------------------------------------------------------------------
# Handler do checkbox
# ---------------------------------------------------------------------------


def test_toggle_grava_no_global_mesmo_com_alvo_selecionado() -> None:
    """O toggle é do PERFIL: com um controle no seletor, ainda cai no global."""
    perfil = _perfil(auto=True, controllers={UNIQ_2: _override_verde_completo()})
    host, check = _host_com_checkbox(DraftConfig.from_profile(perfil), uniq=UNIQ_2)
    check.set_active(True)  # sem mudança de estado — nada dispara
    check.active = True
    check.set_active(False)  # a usuária desmarca

    assert host.draft.leds.auto_player_colors is False
    # Nenhum override foi tocado (nem criado, nem alterado).
    override = host.draft.controller_override(UNIQ_2)
    assert override is not None and tuple(override.leds.lightbar) == (0, 255, 0)
    assert host.draft.controller_override(UNIQ_1) is None


def test_religar_o_auto_nao_apaga_cores_explicitas() -> None:
    perfil = _perfil(auto=False, controllers={UNIQ_2: _override_verde_completo()})
    host, check = _host_com_checkbox(DraftConfig.from_profile(perfil))
    antes = host.draft.source_controllers
    check.set_active(True)  # religa

    assert host.draft.leds.auto_player_colors is True
    assert host.draft.source_controllers is antes  # mapa intacto (mesmo objeto)


def test_refresh_programatico_nao_dispara_o_handler() -> None:
    """set_active vindo do refresh (guard ligado) não pode editar o draft."""
    host, check = _host_com_checkbox(DraftConfig.from_profile(_perfil(auto=True)))
    host._refresh_guard = True
    check.set_active(False)
    assert host.draft.leds.auto_player_colors is True  # intacto
    host._refresh_guard = False


# ---------------------------------------------------------------------------
# Semântica D4: cor única em "Todos" com o automático ligado
# ---------------------------------------------------------------------------


def test_cor_em_todos_com_auto_on_desliga_toggle_com_aviso() -> None:
    host, check = _host_com_checkbox(DraftConfig.from_profile(_perfil(auto=True)))
    check.active = True  # espelho visual do draft
    host.on_lightbar_color_set(_FakeColorButton((0, 0, 255)))

    assert host.draft.leds.auto_player_colors is False
    assert host.draft.leds.lightbar_rgb == (0, 0, 255)
    assert check.get_active() is False  # checkbox sincronizado, sob guard
    assert any(_AVISO_D4 in toast for toast in host._toasts)


def test_cor_em_todos_com_auto_off_nao_avisa_de_novo() -> None:
    host, _check = _host_com_checkbox(DraftConfig.from_profile(_perfil(auto=False)))
    host.on_lightbar_color_set(_FakeColorButton((0, 0, 255)))
    assert host.draft.leds.auto_player_colors is False
    assert not any(_AVISO_D4 in toast for toast in host._toasts)


def test_cor_com_alvo_selecionado_nao_dispara_d4() -> None:
    """Fluxo por-controle permanece como está: override, auto intacto."""
    host, _check = _host_com_checkbox(
        DraftConfig.from_profile(_perfil(auto=True)), uniq=UNIQ_2
    )
    host.on_lightbar_color_set(_FakeColorButton((0, 0, 255)))
    assert host.draft.leds.auto_player_colors is True
    assert host.draft.effective_leds_for(UNIQ_2).lightbar_rgb == (0, 0, 255)
    assert not any(_AVISO_D4 in toast for toast in host._toasts)


def test_brilho_em_todos_nao_dispara_d4() -> None:
    """Brilho escala a própria paleta (D11) — nunca desliga o automático."""
    host, _check = _host_com_checkbox(DraftConfig.from_profile(_perfil(auto=True)))

    class _FakeScale:
        @staticmethod
        def get_value() -> float:
            return 40.0

    host.on_lightbar_brightness_changed(_FakeScale())
    assert host.draft.leds.auto_player_colors is True


def test_player_leds_em_todos_com_auto_on_dispara_d4(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """ONDA-U (U9): clique manual de player-LED em "Todos" com o automático
    ligado AGORA desliga o toggle — antes só ``lightbar_rgb`` disparava o D4,
    e a paleta automática (COR-03) reescrevia o player-LED por cima no
    próximo merge do backend, fazendo o clique manual parecer que "não
    funciona" (falha-sem: no HEAD nem o toggle nem o toast do D4 apareciam
    aqui). Exercita o caminho REAL do botão "Aplicar LEDs"
    (``on_player_leds_apply``), não só ``_persist_leds_update`` isolado — é o
    chamador quem compõe o toast."""
    monkeypatch.setattr(lightbar_actions, "player_leds_set", lambda _bits: True)
    host, check = _host_com_checkbox(DraftConfig.from_profile(_perfil(auto=True)))
    check.active = True  # espelho visual do draft

    host.on_player_leds_apply(None)

    assert host.draft.leds.auto_player_colors is False
    assert check.get_active() is False  # checkbox sincronizado, sob guard
    assert any(_AVISO_D4 in toast for toast in host._toasts)


def test_player_leds_em_todos_com_auto_off_nao_dispara_de_novo(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(lightbar_actions, "player_leds_set", lambda _bits: True)
    host, _check = _host_com_checkbox(DraftConfig.from_profile(_perfil(auto=False)))

    host.on_player_leds_apply(None)

    assert host.draft.leds.auto_player_colors is False
    assert not any(_AVISO_D4 in toast for toast in host._toasts)


def test_player_leds_com_alvo_selecionado_nao_dispara_d4(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Fluxo por-controle permanece como está: override, auto intacto."""
    monkeypatch.setattr(lightbar_actions, "player_leds_set", lambda _bits: True)
    host, _check = _host_com_checkbox(
        DraftConfig.from_profile(_perfil(auto=True)), uniq=UNIQ_2
    )

    host.on_player_leds_apply(None)

    assert host.draft.leds.auto_player_colors is True
    assert not any(_AVISO_D4 in toast for toast in host._toasts)


def test_aplicar_no_controle_em_todos_leva_toggle_no_ipc(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Botão "Aplicar no controle" em "Todos": D4 + cor e toggle num único
    profile.apply_draft parcial (led.set clássico seria vencido pela paleta)."""
    host, check = _host_com_checkbox(DraftConfig.from_profile(_perfil(auto=True)))
    check.active = True
    payloads: list[dict[str, Any]] = []

    def _spy(payload: dict[str, Any]) -> bool:
        payloads.append(payload)
        return True

    monkeypatch.setattr(lightbar_actions.ipc_bridge, "apply_draft", _spy)
    monkeypatch.setattr(
        lightbar_actions,
        "led_set",
        lambda *_a, **_kw: pytest.fail("em 'Todos' o caminho é apply_draft"),
    )
    host._current_rgb = (10, 20, 30)
    host._current_brightness = 0.5
    host.on_lightbar_apply(None)

    assert host.draft.leds.auto_player_colors is False  # D4
    assert check.get_active() is False
    assert payloads == [
        {
            "leds": {
                "lightbar_rgb": [10, 20, 30],
                "lightbar_brightness": 0.5,
                "auto_player_colors": False,
            }
        }
    ]
    assert any(_AVISO_D4 in toast for toast in host._toasts)
    assert any("aplicada" in toast for toast in host._toasts)


def test_aplicar_no_controle_com_alvo_usa_led_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    host, _check = _host_com_checkbox(
        DraftConfig.from_profile(_perfil(auto=True)), uniq=UNIQ_2
    )
    chamadas: list[Any] = []
    monkeypatch.setattr(
        lightbar_actions,
        "led_set",
        lambda rgb, brightness=None: chamadas.append((rgb, brightness)) or True,
    )
    monkeypatch.setattr(
        lightbar_actions.ipc_bridge,
        "apply_draft",
        lambda *_a: pytest.fail("com alvo o caminho é led.set (respeita o alvo)"),
    )
    host._current_rgb = (10, 20, 30)
    host._current_brightness = 1.0
    host.on_lightbar_apply(None)

    assert chamadas == [((10, 20, 30), 1.0)]
    assert host.draft.leds.auto_player_colors is True  # alvo não dispara D4


def _gdk_rgba_ok() -> bool:
    """Gdk.RGBA existe? A CI headless de release tem um Gdk parcial sem RGBA;
    este caso exercita o botão "Apagar" que constrói um Gdk.RGBA. Pula lá."""
    try:
        import gi

        gi.require_version("Gdk", "3.0")
        from gi.repository import Gdk

        return hasattr(Gdk, "RGBA")
    except Exception:
        return False


@pytest.mark.skipif(not _gdk_rgba_ok(), reason="Gdk.RGBA ausente (CI headless)")
def test_apagar_em_todos_leva_toggle_no_ipc(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    host, _check = _host_com_checkbox(DraftConfig.from_profile(_perfil(auto=True)))
    payloads: list[dict[str, Any]] = []
    monkeypatch.setattr(
        lightbar_actions.ipc_bridge,
        "apply_draft",
        lambda payload: payloads.append(payload) or True,
    )
    host.on_lightbar_off(None)

    assert host.draft.leds.auto_player_colors is False  # D4 (preto é cor única)
    assert host.draft.leds.lightbar_rgb == (0, 0, 0)
    assert payloads == [
        {"leds": {"lightbar_rgb": [0, 0, 0], "auto_player_colors": False}}
    ]
    assert any(_AVISO_D4 in toast for toast in host._toasts)


# ---------------------------------------------------------------------------
# "Voltar ao automático" (alvo) e "Voltar todos ao automático"
# ---------------------------------------------------------------------------


def test_voltar_ao_automatico_remove_so_a_cor_do_alvo() -> None:
    perfil = _perfil(auto=True, controllers={UNIQ_2: _override_verde_completo()})
    host, _check = _host_com_checkbox(DraftConfig.from_profile(perfil), uniq=UNIQ_2)
    host.on_lightbar_auto_reset_target(None)

    override = host.draft.controller_override(UNIQ_2)
    assert override is not None and override.leds is not None
    assert "lightbar" not in override.leds.model_fields_set
    assert "lightbar_brightness" not in override.leds.model_fields_set
    # Player-LEDs e gatilhos próprios FICAM.
    assert "player_leds" in override.leds.model_fields_set
    assert override.triggers is not None and override.triggers.right.mode == "Rigid"
    # A aba volta a exibir o global no alvo (cor herdada).
    assert host.draft.effective_leds_for(UNIQ_2).lightbar_rgb == (129, 61, 156)
    assert host._toasts  # feedback visível


def test_voltar_ao_automatico_poda_entrada_que_esvaziou() -> None:
    so_cor = ControllerOverrides.model_validate(
        {"leds": {"lightbar": [0, 255, 0], "lightbar_brightness": 0.5}}
    )
    perfil = _perfil(auto=True, controllers={UNIQ_2: so_cor})
    host, _check = _host_com_checkbox(DraftConfig.from_profile(perfil), uniq=UNIQ_2)
    host.on_lightbar_auto_reset_target(None)

    assert host.draft.controller_override(UNIQ_2) is None
    assert host.draft.source_controllers is None  # mapa vazio → None


def test_voltar_ao_automatico_sem_alvo_orienta_sem_mexer() -> None:
    perfil = _perfil(auto=True, controllers={UNIQ_2: _override_verde_completo()})
    draft = DraftConfig.from_profile(perfil)
    host, _check = _host_com_checkbox(draft, uniq=None)
    host.on_lightbar_auto_reset_target(None)

    assert host.draft is draft  # nada mudou
    assert any("Voltar todos ao automático" in toast for toast in host._toasts)


def test_voltar_todos_limpa_cores_e_religa_o_auto() -> None:
    so_player_leds = ControllerOverrides.model_validate(
        {"leds": {"player_leds": [True, True, False, False, False]}}
    )
    perfil = _perfil(
        auto=False,
        controllers={UNIQ_1: _override_verde_completo(), UNIQ_2: so_player_leds},
    )
    host, check = _host_com_checkbox(DraftConfig.from_profile(perfil))
    host.on_lightbar_auto_reset_all(None)

    assert host.draft.leds.auto_player_colors is True  # religou
    assert check.get_active() is True  # refresh sincronizou o checkbox
    o1 = host.draft.controller_override(UNIQ_1)
    assert o1 is not None and o1.leds is not None
    assert "lightbar" not in o1.leds.model_fields_set  # cor saiu
    assert "player_leds" in o1.leds.model_fields_set  # player-LEDs ficaram
    assert o1.triggers is not None  # gatilhos ficaram
    o2 = host.draft.controller_override(UNIQ_2)
    assert o2 is not None and "player_leds" in o2.leds.model_fields_set
    assert host._toasts


# ---------------------------------------------------------------------------
# DraftApplier: o toggle chega ao registro de identidade (daemon)
# ---------------------------------------------------------------------------


class TestApplierAutoColors:
    @pytest.fixture(autouse=True)
    def _singleton_limpo(self) -> Any:
        identity.reset_identity_registry()
        yield
        identity.reset_identity_registry()

    @staticmethod
    def _applier() -> tuple[DraftApplier, MagicMock]:
        controller = MagicMock()
        return (
            DraftApplier(controller=controller, store=MagicMock(), daemon=None),
            controller,
        )

    def test_secao_leds_configura_o_registro(self) -> None:
        applier, controller = self._applier()
        applied = applier.apply(
            {
                "leds": {
                    "lightbar_rgb": [10, 20, 30],
                    "lightbar_brightness": 0.4,
                    "player_leds": [True, False, False, False, False],
                    "auto_player_colors": False,
                }
            }
        )
        assert applied == ["leds"]
        registry = identity.get_identity_registry()
        assert registry.auto_enabled is False
        assert registry.auto_brightness == pytest.approx(0.4)  # D11
        controller.apply_output_defaults.assert_called_once()

    def test_toggle_sozinho_configura_sem_broadcast(self) -> None:
        """Payload parcial (só o toggle) — o caminho do botão da aba."""
        applier, controller = self._applier()
        registry = identity.get_identity_registry()
        registry.configure(enabled=False)
        applied = applier.apply({"leds": {"auto_player_colors": True}})
        assert applied == ["leds"]
        assert registry.auto_enabled is True
        controller.apply_output_defaults.assert_not_called()

    def test_payload_sem_a_chave_nao_mexe_no_registro(self) -> None:
        """GUI antiga (sem o campo) = sem opinião: o vigente fica."""
        applier, _controller = self._applier()
        registry = identity.get_identity_registry()
        registry.configure(enabled=False, brightness=0.2)
        applier.apply({"leds": {"lightbar_rgb": [1, 2, 3]}})
        assert registry.auto_enabled is False
        assert registry.auto_brightness == pytest.approx(0.2)

    def test_toggle_invalido_recusa_a_secao(self) -> None:
        applier, controller = self._applier()
        applied = applier.apply({"leds": {"auto_player_colors": "sim"}})
        assert applied == []  # seção falhou (best-effort, logada)
        assert identity.get_identity_registry().auto_enabled is True  # intacto
        controller.apply_output_defaults.assert_not_called()


class TestPreviaHonestaAuto:
    """Achado ao vivo 2026-07-17: com auto ON + um controle específico em
    edição, a prévia mostra a cor REAL da paleta (não a manual global)."""

    def test_le_o_slot_do_alvo(self) -> None:
        draft = DraftConfig.default()  # auto_player_colors=True (default COR-04)
        host = _Host(draft, uniq="aabbcc000002")
        host._edit_target_label = "Controle 2 — BT"
        assert host._auto_preview_slot() == 2

    def test_none_quando_auto_desligado(self) -> None:
        draft = DraftConfig.default()
        leds = draft.leds.model_copy(update={"auto_player_colors": False})
        draft = draft.model_copy(update={"leds": leds})
        host = _Host(draft, uniq="aabbcc000002")
        host._edit_target_label = "Controle 2 — BT"
        assert host._auto_preview_slot() is None

    def test_none_no_alvo_todos(self) -> None:
        draft = DraftConfig.default()
        host = _Host(draft, uniq=None)  # "Todos" — sem controle específico
        host._edit_target_label = "Todos os controles"
        assert host._auto_preview_slot() is None
