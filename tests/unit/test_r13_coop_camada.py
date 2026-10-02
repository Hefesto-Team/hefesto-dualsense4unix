"""R-13 item 1 (auditoria 23/07) — CO-OP publica seu padrão como CAMADA"""
from __future__ import annotations

from typing import Any

import pytest

from hefesto_dualsense4unix.core.controller import OutputSpec
from hefesto_dualsense4unix.daemon.subsystems.coop import CoopManager, player_led_pattern
from tests.unit.test_coop_player_leds import (
    DEFAULT_BITS,
    MAC1,
    MAC2,
    OVERRIDE_BITS,
    _backend_real,
    _daemon_com_backend,
    _set_evdevs,
    _set_led_nodes,
    patched,  # noqa: F401 — fixture usada pelos testes
)


def _cenario(monkeypatch: pytest.MonkeyPatch) -> tuple[Any, Any, Any]:
    """Perfil aplicado (default broadcast) + 2 controles + co-op ligado."""
    nodes = _set_led_nodes(monkeypatch, MAC1, MAC2)
    backend, _h1, _h2 = _backend_real(nodes)
    backend.set_player_leds(DEFAULT_BITS)
    _set_evdevs(
        monkeypatch, {MAC1: "/dev/input/event5", MAC2: "/dev/input/event7"}
    )
    daemon = _daemon_com_backend(backend)
    return nodes, backend, daemon


def test_coop_publica_camada_no_backend(
    patched: None, monkeypatch: pytest.MonkeyPatch  # noqa: F811
) -> None:
    """Com a API de camadas, o co-op popula `_desired_coop_by_uniq` — o mapa"""
    _nodes, backend, daemon = _cenario(monkeypatch)
    CoopManager(daemon).sync()

    assert backend._desired_coop_by_uniq[MAC1].player_leds == player_led_pattern(1)
    assert backend._desired_coop_by_uniq[MAC2].player_leds == player_led_pattern(2)


def test_reassert_reafirma_o_padrao_do_coop_nao_o_do_perfil(
    patched: None, monkeypatch: pytest.MonkeyPatch  # noqa: F811
) -> None:
    """O coração do R-13: o `reassert_resolved_outputs` (que roda a cada"""
    nodes, backend, daemon = _cenario(monkeypatch)
    CoopManager(daemon).sync()

    backend.reassert_resolved_outputs()

    assert nodes[MAC1].patterns[-1] == player_led_pattern(1)
    assert nodes[MAC2].patterns[-1] == player_led_pattern(2)
    assert nodes[MAC1].patterns[-1] != DEFAULT_BITS


def test_camada_do_coop_sobrevive_a_ativacao_de_perfil(
    patched: None, monkeypatch: pytest.MonkeyPatch  # noqa: F811
) -> None:
    """O PAR R-13 com R-20: ativar um perfil (que republica a camada DELE)"""
    from hefesto_dualsense4unix.profiles.manager import ProfileManager
    from hefesto_dualsense4unix.profiles.schema import LedsConfig, MatchAny, Profile

    nodes, backend, daemon = _cenario(monkeypatch)
    CoopManager(daemon).sync()
    assert backend._desired_coop_by_uniq

    profile = Profile(
        name="jogo", match=MatchAny(), leds=LedsConfig(lightbar=(9, 9, 9))
    )
    ProfileManager(controller=backend).apply(profile, origin="autoswitch")

    assert backend._desired_coop_by_uniq[MAC1].player_leds == player_led_pattern(1)
    assert backend._merged_desired_for_key(MAC1).player_leds == player_led_pattern(1)
    assert nodes[MAC1].patterns[-1] == player_led_pattern(1)
    assert nodes[MAC2].patterns[-1] == player_led_pattern(2)
    assert (
        backend.resolved_player_leds_for(MAC1)
        != backend._merged_desired_for_key(MAC1).player_leds
    )


def test_desligar_coop_revoga_a_camada(
    patched: None, monkeypatch: pytest.MonkeyPatch  # noqa: F811
) -> None:
    """Desligar o co-op REVOGA a camada e cada controle volta ao resolvido sem"""
    _nodes, backend, daemon = _cenario(monkeypatch)
    mgr = CoopManager(daemon)
    mgr.sync()
    assert backend._desired_coop_by_uniq

    daemon.config.coop_enabled = False
    mgr.sync()

    assert backend._desired_coop_by_uniq == {}
    assert backend._merged_desired_for_key(MAC1).player_leds == DEFAULT_BITS


def test_coop_com_override_de_perfil_vence_na_camada(
    patched: None, monkeypatch: pytest.MonkeyPatch  # noqa: F811
) -> None:
    """A camada do co-op está ACIMA da camada da usuária/perfil: com o co-op"""
    nodes = _set_led_nodes(monkeypatch, MAC1, MAC2)
    backend, _h1, _h2 = _backend_real(nodes)
    backend.set_player_leds(DEFAULT_BITS)
    backend.apply_output_for(MAC2, OutputSpec(player_leds=OVERRIDE_BITS))
    _set_evdevs(
        monkeypatch, {MAC1: "/dev/input/event5", MAC2: "/dev/input/event7"}
    )
    daemon = _daemon_com_backend(backend)
    mgr = CoopManager(daemon)
    mgr.sync()

    assert backend._merged_desired_for_key(MAC2).player_leds == player_led_pattern(2)

    daemon.config.coop_enabled = False
    mgr.sync()

    assert backend._merged_desired_for_key(MAC2).player_leds == OVERRIDE_BITS
    assert backend._desired_by_uniq[MAC2].player_leds == OVERRIDE_BITS


def test_um_secundario_a_menos_revoga_so_o_dele_via_camada(
    patched: None, monkeypatch: pytest.MonkeyPatch  # noqa: F811
) -> None:
    """Com 2 secundários e um saindo, a camada é republicada SEM o que saiu; o"""
    mac3 = "aabbcc000003"
    nodes = _set_led_nodes(monkeypatch, MAC1, MAC2, mac3)
    backend, _h1, _h2 = _backend_real(nodes)
    from tests.unit.test_coop_player_leds import KEY1, _stub_handle

    backend._handles[mac3.upper()] = _stub_handle()
    backend._sysfs[mac3.upper()] = nodes[mac3]
    backend.set_player_leds(DEFAULT_BITS)
    _set_evdevs(
        monkeypatch,
        {
            MAC1: "/dev/input/event5",
            MAC2: "/dev/input/event7",
            mac3: "/dev/input/event9",
        },
    )
    daemon = _daemon_com_backend(backend)
    mgr = CoopManager(daemon)
    mgr.sync()
    assert set(backend._desired_coop_by_uniq) == {MAC1, MAC2, mac3}

    _set_evdevs(
        monkeypatch, {MAC1: "/dev/input/event5", MAC2: "/dev/input/event7"}
    )
    mgr.sync()

    assert mac3 not in backend._desired_coop_by_uniq
    assert MAC1 in backend._desired_coop_by_uniq
    assert backend._merged_desired_for_key(MAC2).player_leds == player_led_pattern(2)
    _ = KEY1
