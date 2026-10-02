"""L12 — o "Todos" pinta o mesmo número de jogador nos quatro."""

from __future__ import annotations

from tests.conftest import exigir_gi_real

exigir_gi_real("lightbar todos o desenho de cada um")

from typing import Any

import pytest

gi = pytest.importorskip("gi")

gi.require_version("Gdk", "3.0")
gi.require_version("Gtk", "3.0")

from hefesto_dualsense4unix.app import draft_config as draft_mod
from hefesto_dualsense4unix.app.actions import lightbar_actions
from hefesto_dualsense4unix.app.actions.lightbar_actions import LightbarActionsMixin
from hefesto_dualsense4unix.core.led_control import player_led_pattern
from hefesto_dualsense4unix.profiles.schema import LedsConfig, MatchAny, Profile

UNIQ_1 = "aa:bb:cc:00:00:01"
UNIQ_2 = "aa:bb:cc:00:00:02"
ROXO = (129, 61, 156)

MESA = {0: (UNIQ_1, 1), 1: (UNIQ_2, 2)}


class _Caixa:
    def __init__(self) -> None:
        self.active = False

    def connect(self, *_a: Any, **_kw: Any) -> None:
        return None

    def get_active(self) -> bool:
        return self.active

    def set_active(self, valor: bool) -> None:
        self.active = bool(valor)


def _aceitou(uniq: str | None) -> dict[str, Any]:
    """Corpo de um ``led.player_set`` que ESCREVEU em ``uniq`` (BG-01)."""
    return {
        "status": "ok",
        "bits": [],
        "aplicado_em": [uniq] if uniq else [],
        "guardado_em": [],
    }


class _Host(LightbarActionsMixin):
    """Host da aba com DOIS controles na mesa e o alvo em "Todos"."""

    def __init__(self, draft: draft_mod.DraftConfig) -> None:
        self.draft = draft
        self._edit_target_uniq = None
        self._target_uniq_by_index = {i: u for i, (u, _s) in MESA.items()}
        self._target_slot_by_index = {i: s for i, (_u, s) in MESA.items()}
        self._widgets: dict[str, Any] = {"auto_player_colors_check": _Caixa()}
        self._toasts: list[str] = []
        self._refresh_guard = False

    def _get(self, widget_id: str) -> Any:
        return self._widgets.get(widget_id)

    def _toast_light(self, msg: str) -> None:
        self._toasts.append(msg)


def _draft() -> draft_mod.DraftConfig:
    return draft_mod.DraftConfig.from_profile(
        Profile(
            name="vitoria",
            match=MatchAny(),
            priority=5,
            leds=LedsConfig(
                lightbar=ROXO,
                player_leds=[False] * 5,
                lightbar_brightness=1.0,
                auto_player_colors=True,
            ),
        )
    )


@pytest.mark.xfail(
    strict=True,
    reason=(
        "L12 — DEFEITO CONHECIDO, aguardando a resposta dela: recusar em "
        '"Todos" (resposta a) ou dar a cada um o desenho do próprio número '
        "(resposta b). Quando qualquer uma das duas entrar, este teste passa, "
        "o pytest acusa XPASS e o `xfail` tem de sair junto com a cura."
    ),
)
def test_todos_nao_pode_pintar_o_numero_de_um_no_outro(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A mordida vermelha: a asserção que as DUAS respostas satisfazem."""
    enviados: dict[str, tuple[bool, ...]] = {}
    monkeypatch.setattr(
        lightbar_actions,
        "player_leds_set_detalhado",
        lambda bits, uniq=None: enviados.__setitem__(uniq, tuple(bits))
        or _aceitou(uniq),
    )
    host = _Host(_draft())

    host.on_player_leds_preset_p2(None)

    for _idx, (uniq, numero) in MESA.items():
        recebido = enviados.get(uniq)
        if recebido is None:
            continue
        assert recebido == tuple(player_led_pattern(numero)), (
            f"o controle de número {numero} recebeu o desenho de outro "
            f"jogador ({recebido}) — é a invariante do co-op quebrada na "
            "superfície que existe para distinguir jogadores"
        )


def test_o_perfil_nao_pode_guardar_o_numero_do_vizinho(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """O que o teste acima mede no FIO, este mede no PERFIL — e é pior."""
    pytest.xfail(
        "L12 — mesmo defeito do teste acima, medido no rascunho: "
        "`_persist_leds_update` grava o MESMO desenho no override de cada MAC. "
        "Sai com a resposta dela."
    )


def test_a_tela_para_de_esconder_que_o_clique_vai_para_todos(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """O que A4 entrega ANTES da resposta dela: o efeito deixa de ser secreto."""
    monkeypatch.setattr(
        lightbar_actions,
        "player_leds_set_detalhado",
        lambda _bits, uniq=None: _aceitou(uniq),
    )
    host = _Host(_draft())

    host.on_player_leds_preset_p2(None)

    assert host._toasts
    esperada = lightbar_actions._AVISO_MESMO_DESENHO_NOS_QUATRO.format(n=2)
    assert esperada in host._toasts[-1], (
        "o clique pegou em dois controles e o toast não contou"
    )


def test_com_um_controle_so_a_frase_do_para_todos_nao_aparece(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A recíproca: contar "1 controle" seria ruído, não informação."""
    monkeypatch.setattr(
        lightbar_actions,
        "player_leds_set_detalhado",
        lambda _bits, uniq=None: _aceitou(uniq),
    )
    host = _Host(_draft())
    host._target_uniq_by_index = {0: UNIQ_1}

    host.on_player_leds_preset_p2(None)

    assert host._toasts
    assert (lightbar_actions._AVISO_MESMO_DESENHO_NOS_QUATRO.split("{n}")[-1]
            not in host._toasts[-1])


def test_os_dois_atalhos_para_todos_ficam_fora_da_pergunta(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """"Todas acesas" e "Todas apagadas" não são desenho de jogador nenhum."""
    enviados: list[tuple[Any, str | None]] = []
    monkeypatch.setattr(
        lightbar_actions,
        "player_leds_set_detalhado",
        lambda bits, uniq=None: enviados.append((tuple(bits), uniq))
        or _aceitou(uniq),
    )
    host = _Host(_draft())

    host.on_player_leds_preset_all(None)
    host.on_player_leds_preset_none(None)

    assert [uniq for _bits, uniq in enviados] == [UNIQ_1, UNIQ_2, UNIQ_1, UNIQ_2]
    assert enviados[0][0] == (True,) * 5
    assert enviados[2][0] == (False,) * 5
