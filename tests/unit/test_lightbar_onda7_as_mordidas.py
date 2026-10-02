"""LIGHTBAR — COR DE CADA UM-01 (Onda 7): os seis casos que a aba não tinha."""

from __future__ import annotations

from tests.conftest import exigir_gi_real

exigir_gi_real("lightbar onda7 as mordidas")

from typing import Any

import pytest

gi = pytest.importorskip("gi")

gi.require_version("Gdk", "3.0")
gi.require_version("Gtk", "3.0")

from hefesto_dualsense4unix.app import draft_config as draft_mod
from hefesto_dualsense4unix.app.actions import lightbar_actions
from hefesto_dualsense4unix.app.actions.lightbar_actions import LightbarActionsMixin
from hefesto_dualsense4unix.profiles.schema import LedsConfig, MatchAny, Profile

UNIQ_1 = "aa:bb:cc:00:00:01"
UNIQ_2 = "aa:bb:cc:00:00:02"

ROXO = (129, 61, 156)

P2 = (False, True, False, True, False)


class _Rotulo:
    """Rótulo GTK reduzido ao que a aba usa: texto, mostrar e esconder."""

    def __init__(self, texto: str = "") -> None:
        self.texto = texto
        self.visivel = True

    def set_text(self, valor: str) -> None:
        self.texto = valor

    def get_text(self) -> str:
        return self.texto

    def show(self) -> None:
        self.visivel = True

    def hide(self) -> None:
        self.visivel = False


class _Caixa:
    def __init__(self) -> None:
        self.active = False

    def connect(self, *_a: Any, **_kw: Any) -> None:
        return None

    def get_active(self) -> bool:
        return self.active

    def set_active(self, valor: bool) -> None:
        self.active = bool(valor)


class _BotaoDeCor:
    def __init__(self, rgb: tuple[int, int, int] = ROXO) -> None:
        self._rgb = rgb

    def get_rgba(self) -> Any:
        class _RGBA:
            red = self._rgb[0] / 255
            green = self._rgb[1] / 255
            blue = self._rgb[2] / 255

        return _RGBA()

    def set_rgba(self, _rgba: Any) -> None:
        return None


def _aceitou(uniq: str | None) -> dict[str, Any]:
    """Corpo de um ``led.set``/``led.player_set`` que ESCREVEU em ``uniq``."""
    return {
        "status": "ok",
        "aplicado_em": [uniq] if uniq else [],
        "guardado_em": [],
    }


class _HostLightbar(LightbarActionsMixin):
    """Host mínimo da aba Lightbar — o molde de ``test_lightbar_todos_por_mac_r14``."""

    def __init__(
        self,
        draft: draft_mod.DraftConfig,
        *,
        conectados: dict[int, str | None] | None = None,
        alvo: str | None = None,
        com_alvo: bool = True,
        slot: int | None = None,
        rotulo_do_alvo: str | None = None,
    ) -> None:
        self.draft = draft
        if com_alvo:
            self._edit_target_uniq = alvo
        if rotulo_do_alvo is not None:
            self._edit_target_label = rotulo_do_alvo
        if slot is not None:
            self._edit_target_slot = slot
        if conectados is not None:
            self._target_uniq_by_index = conectados
        self._widgets: dict[str, Any] = {
            "auto_player_colors_check": _Caixa(),
            "player_leds_estado": _Rotulo("Desenho que mandamos: lendo o perfil…"),
            "lightbar_estado_no_controle": _Rotulo(),
            "lightbar_color_button": _BotaoDeCor(),
        }
        self._toasts: list[str] = []
        self._refresh_guard = False

    def _get(self, widget_id: str) -> Any:
        return self._widgets.get(widget_id)

    def _toast_light(self, msg: str) -> None:
        self._toasts.append(msg)

    @property
    def rotulo_do_desenho(self) -> _Rotulo:
        return self._widgets["player_leds_estado"]

    @property
    def rotulo_da_barra(self) -> _Rotulo:
        return self._widgets["lightbar_estado_no_controle"]


def _perfil(auto: bool = True) -> Profile:
    return Profile(
        name="vitoria",
        match=MatchAny(),
        priority=5,
        leds=LedsConfig(
            lightbar=ROXO,
            player_leds=[False, False, False, False, False],
            lightbar_brightness=1.0,
            auto_player_colors=auto,
        ),
    )


def _draft(auto: bool = True) -> draft_mod.DraftConfig:
    return draft_mod.DraftConfig.from_profile(_perfil(auto))


def _state(**campos: Any) -> dict[str, Any]:
    entrada = {
        "index": 0,
        "connected": True,
        "transport": "bt",
        "uniq": UNIQ_1,
        "lightbar_rgb": [0, 0, 255],
        "lightbar_on": True,
        "lightbar_source": "sysfs",
        "lightbar_disputada": False,
    }
    entrada.update(campos)
    return {"native_mode": False, "controllers": [entrada]}


@pytest.mark.parametrize("numero", [1, 2, 3, 4])
def test_cada_botao_de_desenho_sai_da_tabela_canonica(
    numero: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    """L9 — o botão e a tabela deixam de ser duas cópias que nada amarra.

    Os quatro botões "Desenho do PN" traziam o padrão escrito à mão, enquanto
    ``core/led_control.player_led_pattern`` já é a tabela que o DAEMON usa para
    acender — e que o MESMO arquivo já lia em ``nome_do_desenho`` para BATIZAR
    o desenho. A aba nomeava por uma fonte e pintava por outra.

    **O ARRANQUE, e ele tem duas metades porque o defeito tinha duas.** Devolva
    o literal escrito à mão a um dos botões E troque o bit correspondente em
    ``_PLAYER_LED_PATTERNS`` — que é exatamente o estado de 24/08: duas cópias
    independentes. O botão reprova nomeando o número. Trocar o bit da tabela
    SOZINHO já não reprova nada, e isso é a cura funcionando: depois do L9 há
    uma fonte só, e uma fonte só não tem como divergir de si mesma.
    """
    from hefesto_dualsense4unix.core.led_control import player_led_pattern

    enviados: list[tuple[bool, ...]] = []
    monkeypatch.setattr(
        lightbar_actions,
        "player_leds_set_detalhado",
        lambda bits, uniq=None: enviados.append(tuple(bits)) or _aceitou(uniq),
    )
    host = _HostLightbar(_draft(auto=False), alvo=UNIQ_1, conectados={0: UNIQ_1})

    getattr(host, f"on_player_leds_preset_p{numero}")(None)

    assert enviados == [tuple(player_led_pattern(numero))], (
        f"o botão P{numero} pintou um desenho que a tabela canônica não "
        "produz — o daemon acenderia outra coisa"
    )


