"""R-13 item 1 (auditoria 23/07) — CO-OP publica seu padrão como CAMADA
por-uniq, em vez de escrever sysfs cru e brigar com o reassert do backend.

O achado `reassert-sobrescreve-player-led-coop`: o co-op escrevia o número do
jogador direto no sysfs; o `reassert_resolved_outputs` roda em TODO `connect()`
(a cada ≤30 s) e repintava o padrão do PERFIL por cima — um pisca-pisca sem
fim, metade da queixa dos números duplicados.

Este é o PAR do R-20: publicada como camada com dono, a camada do co-op
sobrevive à ativação de perfil seguinte (que antes substituía o mapa inteiro)
e o reassert passa a reafirmar o valor DO CO-OP.

Reutiliza o cenário hermético de `test_coop_player_leds` (backend real com
handles stub + nós sysfs falsos). Cada teste prova a regressão na descrição.
"""
from __future__ import annotations

from typing import Any

import pytest

from hefesto_dualsense4unix.core.controller import OutputSpec
from hefesto_dualsense4unix.daemon.subsystems.coop import CoopManager, player_led_pattern
from tests.unit.test_coop_player_leds import (  # scaffolding hermético
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
    backend.set_player_leds(DEFAULT_BITS)  # padrão global do perfil
    _set_evdevs(
        monkeypatch, {MAC1: "/dev/input/event5", MAC2: "/dev/input/event7"}
    )
    daemon = _daemon_com_backend(backend)
    return nodes, backend, daemon


# ---------------------------------------------------------------------------
# O co-op publica a camada no backend (não escreve sysfs cru)
# ---------------------------------------------------------------------------


def test_coop_publica_camada_no_backend(
    patched: None, monkeypatch: pytest.MonkeyPatch  # noqa: F811
) -> None:
    """Com a API de camadas, o co-op popula `_desired_coop_by_uniq` — o mapa
    que o merge e o reassert leem. Reverter (co-op voltar a escrever sysfs cru)
    deixa esse mapa vazio."""
    _nodes, backend, daemon = _cenario(monkeypatch)
    CoopManager(daemon).sync()

    assert backend._desired_coop_by_uniq[MAC1].player_leds == player_led_pattern(1)
    assert backend._desired_coop_by_uniq[MAC2].player_leds == player_led_pattern(2)


def test_reassert_reafirma_o_padrao_do_coop_nao_o_do_perfil(
    patched: None, monkeypatch: pytest.MonkeyPatch  # noqa: F811
) -> None:
    """O coração do R-13: o `reassert_resolved_outputs` (que roda a cada
    connect ≤30 s) reafirma o número do JOGADOR, não o padrão do perfil.

    Antes, o co-op escrevia sysfs cru e o reassert repintava o padrão do
    perfil por cima — o pisca-pisca. Agora eles concordam."""
    nodes, backend, daemon = _cenario(monkeypatch)
    CoopManager(daemon).sync()

    # Simula o reassert de um connect() qualquer (hotplug, tick de 30 s).
    backend.reassert_resolved_outputs()

    # A ÚLTIMA escrita em cada nó é o padrão do JOGADOR, não DEFAULT_BITS.
    assert nodes[MAC1].patterns[-1] == player_led_pattern(1)
    assert nodes[MAC2].patterns[-1] == player_led_pattern(2)
    assert nodes[MAC1].patterns[-1] != DEFAULT_BITS


def test_camada_do_coop_sobrevive_a_ativacao_de_perfil(
    patched: None, monkeypatch: pytest.MonkeyPatch  # noqa: F811
) -> None:
    """O PAR R-13 com R-20: ativar um perfil (que republica a camada DELE)
    não apaga a camada do co-op.

    Antes, `manager.apply` chamava `reset_output_overrides`, que substituía o
    mapa inteiro — a camada do co-op seria varrida na primeira troca de
    janela. Como `reset_profile_overrides` mexe só na camada do perfil, o
    número do jogador continua."""
    from hefesto_dualsense4unix.profiles.manager import ProfileManager
    from hefesto_dualsense4unix.profiles.schema import LedsConfig, MatchAny, Profile

    nodes, backend, daemon = _cenario(monkeypatch)
    CoopManager(daemon).sync()
    assert backend._desired_coop_by_uniq  # camada publicada

    # O autoswitch ativa um perfil (troca de janela) — origin automática.
    profile = Profile(
        name="jogo", match=MatchAny(), leds=LedsConfig(lightbar=(9, 9, 9))
    )
    ProfileManager(controller=backend).apply(profile, origin="autoswitch")

    # A camada do co-op continua intacta e o merge (o que o hardware recebe)
    # ainda mostra o número do jogador — não foi varrida pela ativação.
    assert backend._desired_coop_by_uniq[MAC1].player_leds == player_led_pattern(1)
    assert backend._merged_desired_for_key(MAC1).player_leds == player_led_pattern(1)
    # A garantia anti-flicker: o `reassert_resolved_outputs` que o manager
    # chama ao fim da ativação escreveu o número do JOGADOR no nó — não o
    # padrão do perfil "jogo". Antes, esse reassert brigava com o co-op.
    assert nodes[MAC1].patterns[-1] == player_led_pattern(1)
    assert nodes[MAC2].patterns[-1] == player_led_pattern(2)
    # E `resolved_player_leds_for` (a base SEM co-op, usada pelo revert) NÃO
    # inclui a camada do co-op — senão o revert restauraria o número para
    # sempre (R-13: a camada do co-op fica fora desse resolvedor).
    assert (
        backend.resolved_player_leds_for(MAC1)
        != backend._merged_desired_for_key(MAC1).player_leds
    )


def test_desligar_coop_revoga_a_camada(
    patched: None, monkeypatch: pytest.MonkeyPatch  # noqa: F811
) -> None:
    """Desligar o co-op REVOGA a camada e cada controle volta ao resolvido sem
    ela — o revert deixou de depender de escrever sysfs cru de volta."""
    _nodes, backend, daemon = _cenario(monkeypatch)
    mgr = CoopManager(daemon)
    mgr.sync()
    assert backend._desired_coop_by_uniq

    daemon.config.coop_enabled = False
    mgr.sync()  # should_be_active=False → disable() → revoga

    assert backend._desired_coop_by_uniq == {}
    # Sem a camada, o merge volta ao padrão do perfil.
    assert backend._merged_desired_for_key(MAC1).player_leds == DEFAULT_BITS


def test_coop_com_override_de_perfil_vence_na_camada(
    patched: None, monkeypatch: pytest.MonkeyPatch  # noqa: F811
) -> None:
    """A camada do co-op está ACIMA da camada da usuária/perfil: com o co-op
    ligado o número do jogador vence o override por-uniq; ao desligar, o
    override reaparece (não foi destruído)."""
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

    # Co-op ligado: MAC2 mostra o JOGADOR 2, não o override.
    assert backend._merged_desired_for_key(MAC2).player_leds == player_led_pattern(2)

    daemon.config.coop_enabled = False
    mgr.sync()

    # Co-op desligado: o override por-uniq de MAC2 sobreviveu e reaparece.
    assert backend._merged_desired_for_key(MAC2).player_leds == OVERRIDE_BITS
    assert backend._desired_by_uniq[MAC2].player_leds == OVERRIDE_BITS


def test_um_secundario_a_menos_revoga_so_o_dele_via_camada(
    patched: None, monkeypatch: pytest.MonkeyPatch  # noqa: F811
) -> None:
    """Com 2 secundários e um saindo, a camada é republicada SEM o que saiu; o
    que ficou continua no seu número. Não é revogação total (isso é só quando
    o último secundário some — coberto em test_coop_player_leds)."""
    mac3 = "aabbcc000003"
    nodes = _set_led_nodes(monkeypatch, MAC1, MAC2, mac3)
    backend, _h1, _h2 = _backend_real(nodes)
    # Terceiro handle para o mac3 (o backend precisa dele para escrever).
    from tests.unit.test_coop_player_leds import KEY1, _stub_handle

    backend._handles[mac3.upper()] = _stub_handle()  # key != uniq, mas casa por norm
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

    # O mac3 (jogador 3) desconecta; MAC1/MAC2 ficam.
    _set_evdevs(
        monkeypatch, {MAC1: "/dev/input/event5", MAC2: "/dev/input/event7"}
    )
    mgr.sync()

    assert mac3 not in backend._desired_coop_by_uniq
    assert MAC1 in backend._desired_coop_by_uniq
    assert backend._merged_desired_for_key(MAC2).player_leds == player_led_pattern(2)
    _ = KEY1  # import usado só para manter o cenário explícito
