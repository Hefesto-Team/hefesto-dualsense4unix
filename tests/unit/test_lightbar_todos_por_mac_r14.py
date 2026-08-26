"""R-14 (auditoria 23/07) — "Todos" na aba Lightbar deixa de matar o automático.

Defeito medido: um clique em cor (ou num preset de player-LED) com o alvo em
"Todos" desligava ``auto_player_colors`` no draft E persistia isso no perfil.
Como aquele flag único governava também a NUMERAÇÃO dos DualSense e a dos
EXTERNOS (o tick de ``external_identity`` era gateado por ele), o efeito
colateral era a queixa "dois player 1, dois player 2" — e o congelamento
seguia salvo no ``fps.json``.

Cura: com os controles CONECTADOS conhecidos (o mapa que a aba Status mantém
do ``state_full``), "Todos" vira "cada um, por MAC" — override por-uniq no
draft e um pedido IPC por controle. O override vence a camada automática no
merge por campo do backend (D5), então a cor única aparece sem desligar nada.
Sem saber quem está conectado, o caminho degradado de sempre (D4) continua,
avisado no toast.

GUI: precisa de ``gi`` (padrão de ``test_mouse_actions_gui_sync.py``).
"""

from __future__ import annotations

from tests.conftest import exigir_gi_real

# GUARDA-GI-REAL-01: vem antes de qualquer import de `gi` de propósito.
# `pytest.importorskip("gi")` ACEITA o stub que outro arquivo planta em
# sys.modules; e sem guarda nenhuma este módulo derruba a COLETA inteira
# no CI headless, em vez de pular.
exigir_gi_real("lightbar todos por mac r14")

from typing import Any

import pytest

gi = pytest.importorskip("gi")

# BUG-TEST-GDK-VERSION-PIN-01: pina Gdk/Gtk 3.0 ANTES de importar módulos da
# GUI — sem isso o gi pode carregar Gdk 4.0 e envenenar o processo inteiro.
gi.require_version("Gdk", "3.0")
gi.require_version("Gtk", "3.0")

from hefesto_dualsense4unix.app import draft_config as draft_mod
from hefesto_dualsense4unix.app.actions import lightbar_actions
from hefesto_dualsense4unix.app.actions.lightbar_actions import (
    _AVISO_D4,
    LightbarActionsMixin,
)
from hefesto_dualsense4unix.profiles.schema import (

    LedsConfig,
    MatchAny,
    Profile,
)

#: MACs forjados (faixa aa:bb:cc — teste-guarda de anonimato).
UNIQ_1 = "aabbcc000001"
UNIQ_2 = "aabbcc000002"

ROXO = (129, 61, 156)


class _FakeCheck:
    def __init__(self) -> None:
        self.active = True

    def connect(self, *_a: Any, **_kw: Any) -> None:
        return None

    def get_active(self) -> bool:
        return self.active

    def set_active(self, value: bool) -> None:
        self.active = bool(value)


class _FakeColorButton:
    def __init__(self, rgb: tuple[int, int, int]) -> None:
        self._rgb = rgb

    def get_rgba(self) -> Any:
        class _RGBA:
            red = self._rgb[0] / 255
            green = self._rgb[1] / 255
            blue = self._rgb[2] / 255

        return _RGBA()

    def set_rgba(self, _rgba: Any) -> None:
        return None


class _Host(LightbarActionsMixin):
    """Host mínimo com o mapa de conectados da aba Status (R-16/R-14)."""

    def __init__(
        self,
        draft: draft_mod.DraftConfig,
        conectados: dict[int, str | None] | None,
        uniq: str | None = None,
    ) -> None:
        self.draft = draft
        self._edit_target_uniq = uniq
        if conectados is not None:
            self._target_uniq_by_index = conectados
        self._widgets: dict[str, Any] = {"auto_player_colors_check": _FakeCheck()}
        self._toasts: list[str] = []
        self._refresh_guard = False

    def _get(self, widget_id: str) -> Any:
        return self._widgets.get(widget_id)

    def _toast_light(self, msg: str) -> None:
        self._toasts.append(msg)


def _draft(auto: bool = True) -> draft_mod.DraftConfig:
    perfil = Profile(
        name="vitoria",
        match=MatchAny(),
        priority=5,
        leds=LedsConfig(
            lightbar=ROXO,
            player_leds=[True, False, False, False, False],
            lightbar_brightness=1.0,
            auto_player_colors=auto,
        ),
    )
    return draft_mod.DraftConfig.from_profile(perfil)


def _aceitou(uniq: str | None) -> dict[str, Any]:
    """O corpo de um ``led.set``/``led.player_set`` que ESCREVEU em ``uniq``.

    BG-01 (26/08/2026): a aba passou a ler o CORPO do daemon em vez do ``bool``
    da ponte estreita. A forma é a do handler (``daemon/ipc_handlers.py``):
    ``status`` fixo em "ok" por contrato, ``aplicado_em`` com quem recebeu o
    byte, ``guardado_em`` vazio — que é o que ``_destinos_por_uniq`` devolve
    para o ``"escreveu"`` do backend, com o controle na mesa. Aqui o que está
    em julgamento continua sendo o ENDEREÇO de cada pedido, não a frase.
    """
    return {
        "status": "ok",
        "aplicado_em": [uniq] if uniq else [],
        "guardado_em": [],
    }


def _host(auto: bool = True, com_conectados: bool = True) -> _Host:
    conectados = {1: UNIQ_1, 2: UNIQ_2} if com_conectados else None
    return _Host(_draft(auto), conectados)


# ---------------------------------------------------------------------------
# Draft: "Todos" vira override por-MAC, sem derrubar o automático
# ---------------------------------------------------------------------------


def test_cor_em_todos_nao_desliga_o_auto_e_grava_por_mac() -> None:
    """Falha-sem: o D4 desligava ``auto_player_colors`` no draft (e o "Salvar
    Perfil" levava isso ao JSON), congelando numeração e externos junto."""
    host = _host()
    host.on_lightbar_color_set(_FakeColorButton((0, 0, 255)))

    assert host.draft.leds.auto_player_colors is True, "a paleta continua viva"
    for uniq in (UNIQ_1, UNIQ_2):
        assert host.draft.effective_leds_for(uniq).lightbar_rgb == (0, 0, 255)
    assert not any(_AVISO_D4 in t for t in host._toasts)
    # O global também registra a cor única (é o que a aba exibe em "Todos").
    assert host.draft.leds.lightbar_rgb == (0, 0, 255)


def test_override_por_mac_sobrevive_ao_round_trip_do_perfil() -> None:
    """O que a GUI grava tem de chegar ao JSON: sem o override por-MAC a
    ativação seguinte devolveria a paleta automática por cima da cor única."""
    host = _host()
    host.on_lightbar_color_set(_FakeColorButton((0, 0, 255)))
    perfil = host.draft.to_profile("vitoria")
    assert perfil.leds.auto_player_colors is True
    assert perfil.controllers is not None
    for uniq in (UNIQ_1, UNIQ_2):
        assert tuple(perfil.controllers[uniq].leds.lightbar) == (0, 0, 255)


def test_player_leds_em_todos_nao_desliga_o_auto(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """U9 sem o martelo: o padrão manual vence por override por-MAC, não
    desligando a identidade automática de todo mundo.

    **NOTA DATADA — 25/08/2026 (L12 da LIGHTBAR-COR-DE-CADA-UM-01).** Este
    teste mede DUAS coisas, e só a primeira é decisão medida:

    1. **que o automático NÃO é desligado** (U9/R-14, auditoria de 23/07) —
       desligar ``auto_player_colors`` é o martelo mais pesado que a aba tem:
       o flag governava também a numeração dos DualSense e a dos externos, e
       ia para o JSON do perfil. **Esta metade fica**, e é o que o nome do
       teste promete;
    2. **que o P3 vai igual para os dois controles** — isto é INCIDENTAL. O
       M7 mediu que é justamente o defeito: os quatro passam a exibir o
       desenho do jogador 3, e o perfil guarda assim. A pergunta "recusar ou
       dar a cada um o desenho do próprio número" é DELA (§8 da sprint), e a
       mordida vermelha dos dois caminhos está em
       ``tests/unit/test_lightbar_todos_o_desenho_de_cada_um.py``.

    Quando a resposta dela vier, a asserção do bloco 2 muda **aqui**; a do
    bloco 1 não se toca.
    """
    enviados: list[tuple[Any, str | None]] = []
    monkeypatch.setattr(
        lightbar_actions,
        "player_leds_set_detalhado",
        lambda bits, uniq=None: enviados.append((bits, uniq)) or _aceitou(uniq),
    )
    host = _host()
    host.on_player_leds_preset_p3(None)

    # Bloco 1 — a decisão medida do U9/R-14. Não muda com a resposta dela.
    assert host.draft.leds.auto_player_colors is True
    assert [uniq for _bits, uniq in enviados] == [UNIQ_1, UNIQ_2]

    # Bloco 2 — INCIDENTAL, e é o defeito do M7. Ver a nota datada acima.
    p3 = (True, False, True, False, True)
    for uniq in (UNIQ_1, UNIQ_2):
        assert tuple(host.draft.effective_leds_for(uniq).player_leds) == p3


def test_brilho_em_todos_continua_global() -> None:
    """Brilho ESCALA a paleta (D11) — não disputa com o automático, então
    continua sendo campo global (nada de override por-MAC)."""

    class _FakeScale:
        @staticmethod
        def get_value() -> float:
            return 40.0

    host = _host()
    host.on_lightbar_brightness_changed(_FakeScale())
    assert host.draft.leds.auto_player_colors is True
    assert host.draft.leds.lightbar_brightness == 40
    assert host.draft.source_controllers in (None, {})


def test_sem_saber_os_conectados_o_d4_antigo_permanece() -> None:
    """Caminho degradado explícito: sem alvo não há override possível, e a
    cor única só aparece desligando a paleta (com aviso)."""
    host = _host(com_conectados=False)
    host.on_lightbar_color_set(_FakeColorButton((0, 0, 255)))
    assert host.draft.leds.auto_player_colors is False
    assert any(_AVISO_D4 in t for t in host._toasts)


# ---------------------------------------------------------------------------
# IPC: "Todos" manda um pedido POR MAC (R-14 + disciplina do R-17)
# ---------------------------------------------------------------------------


def test_aplicar_em_todos_manda_led_set_por_mac(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Falha-sem: o "Aplicar" em "Todos" ia por ``apply_draft`` com o toggle
    desligado — a única forma de a cor vencer a paleta era matá-la."""
    chamadas: list[tuple[Any, Any, str | None]] = []
    monkeypatch.setattr(
        lightbar_actions,
        "led_set_detalhado",
        lambda rgb, brightness=None, uniq=None: chamadas.append(
            (rgb, brightness, uniq)
        )
        or _aceitou(uniq),
    )
    monkeypatch.setattr(
        lightbar_actions.ipc_bridge,
        "apply_draft_detalhado",
        lambda *_a, **_kw: pytest.fail("com conectados conhecidos é led.set por MAC"),
    )
    host = _host()
    host._current_rgb = (10, 20, 30)
    host._current_brightness = 0.5
    host.on_lightbar_apply(None)

    assert chamadas == [
        ((10, 20, 30), 0.5, UNIQ_1),
        ((10, 20, 30), 0.5, UNIQ_2),
    ]
    assert host.draft.leds.auto_player_colors is True
    assert not any(_AVISO_D4 in t for t in host._toasts)


def test_falha_em_um_controle_nao_vira_sucesso(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Um controle que não aceitou é falha visível (sem curto-circuito: os
    outros ainda recebem o pedido)."""
    vistos: list[str | None] = []

    def _led_set(
        rgb: Any, brightness: Any = None, uniq: str | None = None
    ) -> dict[str, Any] | None:
        vistos.append(uniq)
        # BG-01: `None` é como o daemon "não respondeu" chega pela ponte
        # `_detalhado` — o mesmo que o `False` de ontem.
        return None if uniq == UNIQ_1 else _aceitou(uniq)

    monkeypatch.setattr(lightbar_actions, "led_set_detalhado", _led_set)
    host = _host()
    host.on_lightbar_apply(None)
    assert vistos == [UNIQ_1, UNIQ_2]
    assert any("Não consegui aplicar" in t for t in host._toasts)


def _gdk_rgba_ok() -> bool:
    """A CI headless de release tem um Gdk parcial sem RGBA (o botão
    "Apagar" constrói um) — mesmo skip de ``test_lightbar_auto_colors``."""
    try:
        from gi.repository import Gdk

        return hasattr(Gdk, "RGBA")
    except Exception:
        return False


@pytest.mark.skipif(not _gdk_rgba_ok(), reason="Gdk.RGBA ausente (CI headless)")
def test_apagar_em_todos_manda_preto_por_mac(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    chamadas: list[tuple[Any, Any, str | None]] = []
    monkeypatch.setattr(
        lightbar_actions,
        "led_set_detalhado",
        lambda rgb, brightness=None, uniq=None: chamadas.append(
            (rgb, brightness, uniq)
        )
        or _aceitou(uniq),
    )
    monkeypatch.setattr(
        lightbar_actions.ipc_bridge,
        "apply_draft_detalhado",
        lambda *_a, **_kw: pytest.fail("com conectados conhecidos é led.set por MAC"),
    )
    host = _host()
    host.on_lightbar_off(None)

    assert chamadas == [((0, 0, 0), None, UNIQ_1), ((0, 0, 0), None, UNIQ_2)]
    assert host.draft.leds.auto_player_colors is True
