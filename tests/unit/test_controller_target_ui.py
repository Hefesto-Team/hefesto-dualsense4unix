"""Lógica do seletor de controle na GUI (FEAT-DSX-CONTROLLER-SELECTOR-01)
e da edição POR-CONTROLE alimentada por ele (PERFIL-04, sprint
2026-07-16-perfis-por-controle).

Cobre:
  - Helpers estáticos do `StatusActionsMixin` que montam as linhas da combo
    e mapeiam o `output_target_index` do daemon para a posição ativa.
  - O alvo de EDIÇÃO derivado do seletor (`_edit_target_uniq` + badge
    "Editando: Controle N (BT)").
  - Seletor→`draft.controllers`: lightbar/gatilhos editados com um controle
    selecionado caem no override por-MAC do draft (e SÓ nele).
  - O round-trip do pedido dela: selecionar o Controle 2 → mudar a lightbar
    → salvar o perfil → recarregar → o Controle 2 tem a cor, o Controle 1
    não (seção global intacta).

Sem display: instâncias parciais via ``__new__`` + widgets stubados.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.app.actions.status_actions import StatusActionsMixin
from hefesto_dualsense4unix.app.draft_config import DraftConfig, TriggerDraft
from hefesto_dualsense4unix.profiles import loader as loader_module
from hefesto_dualsense4unix.profiles.loader import load_profile, save_profile
from hefesto_dualsense4unix.profiles.schema import (
    LedsConfig,
    MatchAny,
    Profile,
)

#: MACs forjados da faixa permitida (tests/unit/test_anonimato_de_fixtures.py).
UNIQ_1 = "aabbcc000001"
UNIQ_2 = "aabbcc000002"


def _conectado(index: int, transport: str, *, primary: bool = False) -> dict[str, object]:
    return {
        "index": index,
        "connected": True,
        "transport": transport,
        "is_primary": primary,
    }


def test_rows_comeca_com_todos() -> None:
    rows = StatusActionsMixin._controller_target_rows(
        [_conectado(0, "bt", primary=True), _conectado(1, "usb")]
    )
    assert rows[0] == ("Todos os controles", None)
    assert rows[1] == ("Controle 1 — BT", 0)
    assert rows[2] == ("Controle 2 — USB", 1)


def test_rows_transporte_ausente_vira_interrogacao() -> None:
    rows = StatusActionsMixin._controller_target_rows(
        [{"index": 0, "connected": True}, {"index": 1, "connected": True}]
    )
    assert rows[1] == ("Controle 1 — ?", 0)


def test_active_position_alvo_todos() -> None:
    rows = StatusActionsMixin._controller_target_rows(
        [_conectado(0, "bt"), _conectado(1, "usb")]
    )
    assert StatusActionsMixin._target_active_position(rows, None) == 0


def test_active_position_alvo_segundo_controle() -> None:
    rows = StatusActionsMixin._controller_target_rows(
        [_conectado(0, "bt"), _conectado(1, "usb")]
    )
    # output_target_index=1 → posição 2 na combo (0=Todos, 1=Controle1, 2=Controle2).
    assert StatusActionsMixin._target_active_position(rows, 1) == 2


def test_active_position_alvo_inexistente_cai_em_todos() -> None:
    rows = StatusActionsMixin._controller_target_rows([_conectado(0, "usb")])
    # alvo aponta para um índice que não está na lista → "Todos" (posição 0).
    assert StatusActionsMixin._target_active_position(rows, 5) == 0


# ---------------------------------------------------------------------------
# PERFIL-04: alvo de EDIÇÃO derivado do seletor + badge
# ---------------------------------------------------------------------------


class _FakeBadge:
    """Stub de GtkLabel do badge: registra texto e visibilidade."""

    def __init__(self) -> None:
        self.text = ""
        self.visible = False

    def set_text(self, text: str) -> None:
        self.text = text

    def show(self) -> None:
        self.visible = True

    def hide(self) -> None:
        self.visible = False


def _status_instance() -> StatusActionsMixin:
    inst = StatusActionsMixin.__new__(StatusActionsMixin)
    inst._edit_target_uniq = None
    inst._edit_target_label = None
    inst._target_uniq_by_index = {}
    inst._target_label_by_index = {}
    inst._edit_badge = _FakeBadge()
    return inst


def _conectado_com_uniq(
    index: int, transport: str, uniq: str | None
) -> dict[str, object]:
    entry = _conectado(index, transport)
    entry["uniq"] = uniq
    return entry


def test_update_target_maps_extrai_uniq_e_rotulo() -> None:
    inst = _status_instance()
    inst._update_target_maps(
        [
            _conectado_com_uniq(0, "bt", UNIQ_1),
            _conectado_com_uniq(1, "usb", UNIQ_2),
        ]
    )
    assert inst._target_uniq_by_index == {0: UNIQ_1, 1: UNIQ_2}
    assert inst._target_label_by_index[0] == "Controle 1 (BT)"
    assert inst._target_label_by_index[1] == "Controle 2 (USB)"


def test_sync_edit_target_liga_badge_no_alvo() -> None:
    """Selecionar o Controle 2 → uniq dele vira o alvo de edição + badge."""
    inst = _status_instance()
    inst._update_target_maps(
        [
            _conectado_com_uniq(0, "bt", UNIQ_1),
            _conectado_com_uniq(1, "usb", UNIQ_2),
        ]
    )
    inst._sync_edit_target(1)
    assert inst._edit_target_uniq == UNIQ_2
    badge = inst._edit_badge
    assert badge.visible
    assert badge.text == "Editando: Controle 2 (USB)"


def test_sync_edit_target_todos_esconde_badge() -> None:
    inst = _status_instance()
    inst._update_target_maps([_conectado_com_uniq(0, "bt", UNIQ_1)])
    inst._sync_edit_target(0)
    assert inst._edit_target_uniq == UNIQ_1
    inst._sync_edit_target(None)  # "Todos"
    assert inst._edit_target_uniq is None
    assert not inst._edit_badge.visible


def test_sync_edit_target_alvo_sem_mac_edita_global() -> None:
    """Controle sem MAC estável (key por path): edição segue GLOBAL, sem
    badge — regra do sprint (fora do mapa, com trilha em vez de silêncio)."""
    inst = _status_instance()
    inst._update_target_maps([_conectado_com_uniq(0, "usb", None)])
    inst._sync_edit_target(0)
    assert inst._edit_target_uniq is None
    assert not inst._edit_badge.visible


def test_sync_edit_target_repopula_abas_por_controle() -> None:
    """Trocar o alvo re-popula lightbar/gatilhos (mostram o efetivo do alvo)."""
    inst = _status_instance()
    chamadas: list[str] = []
    inst._refresh_lightbar_from_draft = lambda: chamadas.append("lightbar")  # type: ignore[attr-defined]
    inst._refresh_triggers_from_draft = lambda: chamadas.append("triggers")  # type: ignore[attr-defined]
    inst._update_target_maps([_conectado_com_uniq(0, "bt", UNIQ_1)])
    inst._sync_edit_target(0)
    assert chamadas == ["lightbar", "triggers"]
    chamadas.clear()
    inst._sync_edit_target(0)  # idempotente: alvo igual não repinta
    assert chamadas == []


def test_edit_badge_text_vazio_sem_alvo() -> None:
    assert StatusActionsMixin._edit_badge_text(None) == ""
    assert StatusActionsMixin._edit_badge_text("") == ""
    assert (
        StatusActionsMixin._edit_badge_text("Controle 1 (BT)")
        == "Editando: Controle 1 (BT)"
    )


# ---------------------------------------------------------------------------
# PERFIL-04: API por-controle do DraftConfig (seletor → draft.controllers)
# ---------------------------------------------------------------------------


def _perfil_base(name: str = "vitoria") -> Profile:
    return Profile(
        name=name,
        match=MatchAny(),
        priority=5,
        leds=LedsConfig(
            lightbar=(129, 61, 156),  # o roxo dela
            player_leds=[True, False, False, False, False],
            lightbar_brightness=1.0,
        ),
    )


def test_with_controller_leds_grava_so_no_override() -> None:
    """Editar leds do alvo NÃO toca a seção global nem outros controles."""
    draft = DraftConfig.from_profile(_perfil_base())
    base = draft.effective_leds_for(UNIQ_2)
    assert base.lightbar_rgb == (129, 61, 156)  # sem override herda o global

    novo = draft.with_controller_leds(
        UNIQ_2, base.model_copy(update={"lightbar_rgb": (0, 0, 255)})
    )
    # Override do alvo criado, semeado com o que estava NA TELA.
    assert novo.effective_leds_for(UNIQ_2).lightbar_rgb == (0, 0, 255)
    assert novo.effective_leds_for(UNIQ_2).player_leds == (
        True, False, False, False, False,
    )
    # Global e o outro controle seguem intactos.
    assert novo.leds.lightbar_rgb == (129, 61, 156)
    assert novo.effective_leds_for(UNIQ_1).lightbar_rgb == (129, 61, 156)
    assert novo.controller_override(UNIQ_1) is None
    # O draft original não foi mutado (frozen + mapa novo).
    assert draft.controller_override(UNIQ_2) is None


def test_with_controller_triggers_merge_por_secao() -> None:
    """Override só de gatilhos: leds do alvo continuam herdando o global."""
    draft = DraftConfig.from_profile(_perfil_base())
    trigs = draft.effective_triggers_for(UNIQ_2)
    novo = draft.with_controller_triggers(
        UNIQ_2,
        trigs.model_copy(
            update={"right": TriggerDraft(mode="Rigid", params=(5, 200))}
        ),
    )
    assert novo.effective_triggers_for(UNIQ_2).right.mode == "Rigid"
    assert novo.effective_triggers_for(UNIQ_2).left.mode == "Off"  # semeado
    # A seção leds do override ficou SEM opinião → exibe o global.
    assert novo.effective_leds_for(UNIQ_2).lightbar_rgb == (129, 61, 156)
    override = novo.controller_override(UNIQ_2)
    assert override is not None and override.leds is None


def test_to_ipc_dict_emite_secao_controllers() -> None:
    """'Aplicar' envia os overrides (seção controllers no apply_draft)."""
    draft = DraftConfig.from_profile(_perfil_base())
    base = draft.effective_leds_for(UNIQ_2)
    draft = draft.with_controller_leds(
        UNIQ_2,
        base.model_copy(
            update={"lightbar_rgb": (0, 0, 255), "lightbar_brightness": 50}
        ),
    )
    payload = draft.to_ipc_dict()
    secao = payload["controllers"]
    assert secao is not None
    assert secao[UNIQ_2]["leds"]["lightbar_rgb"] == [0, 0, 255]
    assert secao[UNIQ_2]["leds"]["lightbar_brightness"] == pytest.approx(0.5)
    assert "triggers" not in secao[UNIQ_2]  # seção sem opinião não viaja


def test_to_ipc_dict_sem_mapa_secao_none() -> None:
    """Draft sem overrides → seção None (o DraftApplier a pula; aditivo)."""
    assert DraftConfig.default().to_ipc_dict()["controllers"] is None
    assert (
        DraftConfig.from_profile(_perfil_base()).to_ipc_dict()["controllers"]
        is None
    )


# ---------------------------------------------------------------------------
# PERFIL-04: handlers das abas gravam no override do alvo selecionado
# ---------------------------------------------------------------------------


class _AppStub:
    """Hospedeiro mínimo para os mixins de aba: draft + alvo + widgets nulos."""

    def __init__(self, draft: DraftConfig, uniq: str | None) -> None:
        self.draft = draft
        self._edit_target_uniq = uniq

    def _get(self, _widget_id: str) -> None:
        return None  # nenhum widget real (preview/checkboxes ausentes)

    def _toast_light(self, _msg: str) -> None:
        return None


def _lightbar_host(draft: DraftConfig, uniq: str | None) -> Any:
    from hefesto_dualsense4unix.app.actions.lightbar_actions import (
        LightbarActionsMixin,
    )

    class _Host(_AppStub, LightbarActionsMixin):
        pass

    host = _Host(draft, uniq)
    host._refresh_guard = False
    return host


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


def test_lightbar_com_alvo_grava_no_override(monkeypatch: pytest.MonkeyPatch) -> None:
    """Cor mudada com o Controle 2 selecionado cai em controllers[uniq2]."""
    host = _lightbar_host(DraftConfig.from_profile(_perfil_base()), UNIQ_2)
    host.on_lightbar_color_set(_FakeColorButton((0, 0, 255)))
    assert host.draft.effective_leds_for(UNIQ_2).lightbar_rgb == (0, 0, 255)
    assert host.draft.leds.lightbar_rgb == (129, 61, 156)  # global intacto
    assert host.draft.controller_override(UNIQ_1) is None


def test_lightbar_sem_alvo_grava_no_global() -> None:
    """Em 'Todos' o comportamento clássico segue: seção global do draft."""
    host = _lightbar_host(DraftConfig.from_profile(_perfil_base()), None)
    host.on_lightbar_color_set(_FakeColorButton((0, 255, 0)))
    assert host.draft.leds.lightbar_rgb == (0, 255, 0)
    assert host.draft.source_controllers is None  # nenhum mapa inventado


def test_brilho_com_alvo_persiste_no_override() -> None:
    """Brilho do alvo vai para o override e volta na exibição (lido do perfil)."""
    host = _lightbar_host(DraftConfig.from_profile(_perfil_base()), UNIQ_2)

    class _FakeScale:
        @staticmethod
        def get_value() -> float:
            return 40.0

    host.on_lightbar_brightness_changed(_FakeScale())
    efetivo = host.draft.effective_leds_for(UNIQ_2)
    assert efetivo.lightbar_brightness == 40
    assert efetivo.lightbar_rgb == (129, 61, 156)  # cor semeada da tela
    assert host.draft.leds.lightbar_brightness == 100  # global intacto


def test_triggers_com_alvo_gravam_no_override() -> None:
    """Gatilho editado com alvo selecionado cai em controllers[uniq].triggers."""
    from hefesto_dualsense4unix.app.actions.triggers_actions import (
        TriggersActionsMixin,
    )

    class _Host(_AppStub, TriggersActionsMixin):
        pass

    class _FakeModeCombo:
        @staticmethod
        def get_active_id() -> str:
            return "Rigid"

    host = _Host(DraftConfig.from_profile(_perfil_base()), UNIQ_2)
    host._trigger_mode = {"right": _FakeModeCombo()}
    host._trigger_param_widgets = {"right": {}}  # sliders ausentes → defaults
    host._persist_params_to_draft("right")

    efetivo = host.draft.effective_triggers_for(UNIQ_2)
    assert efetivo.right.mode == "Rigid"
    assert host.draft.triggers.right.mode == "Off"  # global intacto
    assert host.draft.effective_triggers_for(UNIQ_1).right.mode == "Off"


def test_refresh_lightbar_exibe_o_efetivo_do_alvo() -> None:
    """Com o alvo selecionado, a aba exibe o override (brilho incluso, lido
    do PERFIL — não do backend)."""
    draft = DraftConfig.from_profile(_perfil_base())
    base = draft.effective_leds_for(UNIQ_2)
    draft = draft.with_controller_leds(
        UNIQ_2,
        base.model_copy(
            update={"lightbar_rgb": (0, 0, 255), "lightbar_brightness": 40}
        ),
    )
    host = _lightbar_host(draft, UNIQ_2)
    host._refresh_lightbar_from_draft()
    assert host._current_rgb == (0, 0, 255)
    assert host._current_brightness == pytest.approx(0.4)

    # O MESMO draft exibido em "Todos" mostra o global.
    host_global = _lightbar_host(draft, None)
    host_global._refresh_lightbar_from_draft()
    assert host_global._current_rgb == (129, 61, 156)
    assert host_global._current_brightness == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# PERFIL-04: o round-trip do pedido dela, de ponta a ponta
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Fix HIGH do review 2026-07-16: editar em "Todos" limpa o campo editado dos
# overrides do draft — espelho da regra do backend ao vivo. Sem isso, "mudei
# todos para azul" + "Salvar Perfil" ressuscitava a cor antiga do alvo na
# próxima ativação (o "voltou verde" que o sprint doc proíbe).
# ---------------------------------------------------------------------------


def _draft_com_override_verde() -> DraftConfig:
    """Draft do perfil dela + override DENSO (semeado pela GUI) verde no C2."""
    draft = DraftConfig.from_profile(_perfil_base())
    base = draft.effective_leds_for(UNIQ_2)
    return draft.with_controller_leds(
        UNIQ_2, base.model_copy(update={"lightbar_rgb": (0, 255, 0)})
    )


def test_editar_cor_em_todos_limpa_a_cor_do_override() -> None:
    """Cor global editada em "Todos" → o campo de cor (e o brilho, que forma
    UM campo com ela no backend) sai do override; o efetivo do C2 vira azul.
    COR-04: a GUI só grava no override o que a usuária mexeu (a cor), então
    essa era a única opinião do C2 — limpá-la poda a entrada e o C2 herda o
    azul (nada de player-LEDs congelados por trás)."""
    host = _lightbar_host(_draft_com_override_verde(), None)  # alvo: Todos
    host.on_lightbar_color_set(_FakeColorButton((0, 0, 255)))

    assert host.draft.leds.lightbar_rgb == (0, 0, 255)
    assert host.draft.effective_leds_for(UNIQ_2).lightbar_rgb == (0, 0, 255)
    assert host.draft.controller_override(UNIQ_2) is None


def test_editar_player_leds_em_todos_preserva_a_cor_do_override() -> None:
    """Granularidade POR CAMPO: mexer nos player-LEDs em "Todos" não apaga a
    cor própria do C2 — só o campo editado sai do override. ONDA-U (U9):
    `_perfil_base()` nasce com o automático LIGADO, então este clique também
    dispara o D4 (fora do escopo deste teste — coberto em
    test_lightbar_auto_colors.py)."""
    host = _lightbar_host(_draft_com_override_verde(), None)
    host._persist_leds_update({"player_leds": (True, True, False, False, False)})

    assert host.draft.leds.player_leds == (True, True, False, False, False)
    override = host.draft.controller_override(UNIQ_2)
    assert override is not None and override.leds is not None
    assert "player_leds" not in override.leds.model_fields_set
    assert override.leds.lightbar == (0, 255, 0)  # a cor dele ficou
    efetivo = host.draft.effective_leds_for(UNIQ_2)
    assert efetivo.lightbar_rgb == (0, 255, 0)
    assert efetivo.player_leds == (True, True, False, False, False)  # herdado


def test_editar_tudo_em_todos_esvazia_e_poda_o_override() -> None:
    """Override cuja última opinião foi limpa some do mapa; mapa vazio volta
    a None (nenhuma chave fantasma no JSON salvo)."""
    host = _lightbar_host(_draft_com_override_verde(), None)
    host._persist_leds_update({"lightbar_rgb": (0, 0, 255)})
    host._persist_leds_update({"player_leds": (False,) * 5})

    assert host.draft.controller_override(UNIQ_2) is None
    assert host.draft.source_controllers is None


def test_editar_com_alvo_selecionado_nao_poda_outros_overrides() -> None:
    """A limpeza é SÓ do ramo "Todos": editar com um alvo selecionado não
    mexe nos overrides dos outros controles."""
    draft = _draft_com_override_verde()
    host = _lightbar_host(draft, UNIQ_1)  # alvo: Controle 1
    host.on_lightbar_color_set(_FakeColorButton((255, 0, 0)))

    assert host.draft.effective_leds_for(UNIQ_1).lightbar_rgb == (255, 0, 0)
    assert host.draft.effective_leds_for(UNIQ_2).lightbar_rgb == (0, 255, 0)


def test_editar_gatilho_em_todos_limpa_so_o_lado_editado() -> None:
    """Gatilho global editado em "Todos" limpa SÓ aquele lado dos overrides;
    o lado não editado do override fica."""
    from hefesto_dualsense4unix.app.actions.triggers_actions import (
        TriggersActionsMixin,
    )

    class _Host(_AppStub, TriggersActionsMixin):
        pass

    class _FakeModeCombo:
        @staticmethod
        def get_active_id() -> str:
            return "Rigid"

    draft = DraftConfig.from_profile(_perfil_base())
    trigs = draft.effective_triggers_for(UNIQ_2)
    draft = draft.with_controller_triggers(
        UNIQ_2,
        trigs.model_copy(
            update={"left": TriggerDraft(mode="Resistance", params=(3, 5))}
        ),
    )

    host = _Host(draft, None)  # alvo: Todos
    host._trigger_mode = {"right": _FakeModeCombo()}
    host._trigger_param_widgets = {"right": {}}
    host._persist_params_to_draft("right")

    assert host.draft.triggers.right.mode == "Rigid"  # global editado
    override = host.draft.controller_override(UNIQ_2)
    assert override is not None and override.triggers is not None
    assert "right" not in override.triggers.model_fields_set
    assert override.triggers.left.mode == "Resistance"  # o lado dele ficou
    # O efetivo do C2 no lado editado segue o global novo.
    assert host.draft.effective_triggers_for(UNIQ_2).right.mode == "Rigid"
    assert host.draft.effective_triggers_for(UNIQ_2).left.mode == "Resistance"


def test_round_trip_editar_todos_nao_ressuscita_a_cor_antiga(
    isolated_profiles_dir: Path,
) -> None:
    """A reprodução do achado HIGH, fechada de ponta a ponta: override verde
    no C2 salvo no perfil → sessão nova em "Todos" muda a cor para azul →
    "Salvar Perfil" → ATIVAR pinta os DOIS controles de azul (nada de
    "voltou verde" na próxima ativação/autoswitch)."""
    from hefesto_dualsense4unix.core.backend_pydualsense import (
        PyDualSenseController,
    )
    from hefesto_dualsense4unix.daemon.state_store import StateStore
    from hefesto_dualsense4unix.profiles.manager import ProfileManager
    from tests.unit.test_backend_multi_controller import (
        KEY_1,
        KEY_2,
        _FakeHandle,
        _null_evdev,
    )

    save_profile(_perfil_base("vitoria"))

    # Sessão 1: ela cria o override verde no C2 e salva.
    host = _lightbar_host(DraftConfig.from_profile(load_profile("vitoria")), UNIQ_2)
    host.on_lightbar_color_set(_FakeColorButton((0, 255, 0)))
    save_profile(host.draft.to_profile("vitoria"))

    # Sessão 2: em "Todos", muda a cor global para azul e salva.
    host2 = _lightbar_host(DraftConfig.from_profile(load_profile("vitoria")), None)
    host2.on_lightbar_color_set(_FakeColorButton((0, 0, 255)))
    save_profile(host2.draft.to_profile("vitoria"))

    # Ativação (o que o autoswitch refaz a ~1s): TUDO azul, como ela viu.
    backend = PyDualSenseController(evdev_reader=_null_evdev())
    h1, h2 = _FakeHandle(), _FakeHandle()
    backend._handles = {KEY_1: h1, KEY_2: h2}
    backend._primary_key = KEY_1
    ProfileManager(controller=backend, store=StateStore()).activate("vitoria")

    assert h1.light.colors[-1] == (0, 0, 255)
    assert h2.light.colors[-1] == (0, 0, 255)  # era o "voltou verde"
    # O que restou do override (player-LEDs semeados) não guarda cor nenhuma.
    residual = backend._desired_by_uniq.get(UNIQ_2)
    assert residual is None or residual.led is None


# ---------------------------------------------------------------------------
# Fix MED do review 2026-07-16: override PARCIAL escrito à mão não densifica
# na exibição, na semeadura nem no payload do "Aplicar"
# ---------------------------------------------------------------------------


def _perfil_com_override_parcial() -> Profile:
    """O JSON do aceite 1 do PERFIL-02: override só com a cor, escrito à mão."""
    raw = _perfil_base().model_dump(mode="json")
    raw["leds"]["lightbar_brightness"] = 0.5
    raw["controllers"] = {UNIQ_2: {"leds": {"lightbar": [0, 255, 0]}}}
    return Profile.model_validate(raw)


def test_effective_leds_de_override_parcial_herda_o_global() -> None:
    """A aba exibe o merge POR CAMPO: cor do override + brilho/player-LEDs do
    GLOBAL — e a semeadura da próxima edição parte desses valores (antes,
    partia dos defaults do schema e os gravava por cima do global)."""
    draft = DraftConfig.from_profile(_perfil_com_override_parcial())
    efetivo = draft.effective_leds_for(UNIQ_2)
    assert efetivo.lightbar_rgb == (0, 255, 0)  # o campo escrito
    assert efetivo.player_leds == (True, False, False, False, False)  # global
    assert efetivo.lightbar_brightness == 50  # global (0.5)


def test_effective_triggers_de_override_parcial_herda_o_outro_lado() -> None:
    raw = _perfil_base().model_dump(mode="json")
    raw["triggers"]["right"] = {"mode": "Rigid", "params": [5, 200]}
    raw["controllers"] = {
        UNIQ_2: {"triggers": {"left": {"mode": "Resistance", "params": [3, 5]}}}
    }
    draft = DraftConfig.from_profile(Profile.model_validate(raw))
    efetivo = draft.effective_triggers_for(UNIQ_2)
    assert efetivo.left.mode == "Resistance"  # o lado escrito
    assert efetivo.right.mode == "Rigid"  # herdado do global


def test_to_ipc_dict_override_parcial_nao_densifica() -> None:
    """O "Aplicar" emite SÓ os campos escritos do override; cor sem brilho
    resolve o brilho do GLOBAL na borda (cor e brilho são UM campo no
    backend), em paridade com a ativação de perfil."""
    draft = DraftConfig.from_profile(_perfil_com_override_parcial())
    secao = draft.to_ipc_dict()["controllers"]
    assert secao is not None
    leds = secao[UNIQ_2]["leds"]
    assert leds["lightbar_rgb"] == [0, 255, 0]
    assert leds["lightbar_brightness"] == pytest.approx(0.5)  # do global
    assert "player_leds" not in leds  # campo não escrito não viaja
    assert "triggers" not in secao[UNIQ_2]


def test_round_trip_do_pedido_dela(isolated_profiles_dir: Path) -> None:
    """O fluxo inteiro: selecionar o Controle 2 → mudar a lightbar → "Salvar
    Perfil" (vitoria) → recarregar → o Controle 2 tem a cor salva PARA ELE
    dentro do perfil; o Controle 1 e a seção global seguem como estavam."""
    save_profile(_perfil_base("vitoria"))

    # Abrir a GUI: draft carregado do perfil ativo.
    draft = DraftConfig.from_profile(load_profile("vitoria"))

    # Ela clica "2 - USB" no seletor e muda a cor para azul.
    host = _lightbar_host(draft, UNIQ_2)
    host.on_lightbar_color_set(_FakeColorButton((0, 0, 255)))

    # "Salvar Perfil" do rodapé (mesmo caminho do footer: to_profile+save).
    save_profile(host.draft.to_profile("vitoria"))

    # Recarrega do disco (reabrir a GUI / ativar o perfil).
    recarregado = load_profile("vitoria")
    assert recarregado.controllers is not None
    assert UNIQ_2 in recarregado.controllers
    assert recarregado.controllers[UNIQ_2].leds is not None
    assert recarregado.controllers[UNIQ_2].leds.lightbar == (0, 0, 255)
    # Controle 1 NÃO ganhou entrada; seção global intacta (o roxo dela).
    assert UNIQ_1 not in recarregado.controllers
    assert recarregado.leds.lightbar == (129, 61, 156)

    # Reabrir a GUI mostra o override para o alvo e o global para o resto.
    draft2 = DraftConfig.from_profile(recarregado)
    assert draft2.effective_leds_for(UNIQ_2).lightbar_rgb == (0, 0, 255)
    assert draft2.effective_leds_for(UNIQ_1).lightbar_rgb == (129, 61, 156)
