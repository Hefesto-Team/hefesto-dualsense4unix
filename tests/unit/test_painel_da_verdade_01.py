"""PAINEL-DA-VERDADE-01 — a aba Status diz o que CHEGA ao jogo."""

from __future__ import annotations

from typing import Any, ClassVar



_PRIMARIO: dict[str, Any] = {"is_primary": True, "player": None}


def _estado(visto: dict[str, float] | None = None, **extra: Any) -> dict[str, Any]:
    """Um `state_full` com o vpad do jogador 1 vivo."""
    vpad: dict[str, Any] = {"player": 1, "visto_ha_s": dict(visto or {})}
    vpad.update(extra)
    return {"rumble_ff": {"per_vpad": [vpad]}}


def _pedido_de_vibracao(ha_s: float = 0.2) -> list[dict[str, Any]]:
    """Um anel de vibração com um PEDIDO de verdade: motor não-nulo e fresco."""
    return [
        {
            "ha_s": ha_s,
            "flag0": 4,
            "flag1": 0,
            "flag2": 0,
            "weak": 40,
            "strong": 90,
            "ramo": "v1",
        }
    ]


class _Relogio:
    def __init__(self) -> None:
        self.t = 1000.0

    def __call__(self) -> float:
        return self.t

    def avancar(self, s: float) -> None:
        self.t += s


def _vpad_de_bancada() -> Any:
    """Um vpad com os campos de estado que o carimbo usa, e nada mais."""
    from hefesto_dualsense4unix.integrations import uhid_gamepad as uhid

    class _Bancada(uhid.UhidDualSense):  # type: ignore[misc]
        def __init__(self, relogio: _Relogio) -> None:
            self.time_fn = relogio
            self.player = 1
            self._visto_em = {}
            self._trigger_replicas = 0
            self._lightbar_replicas = 0
            self._player_led_replicas = 0
            self._game_dirty = False
            self.trigger_sink = None
            self.lightbar_sink = None
            self.player_led_sink = None

    return _Bancada


def test_o_vpad_carimba_a_categoria_e_a_idade_envelhece() -> None:
    """O carimbo diz HÁ QUANTO TEMPO, e a categoria ausente diz "nunca"."""
    from hefesto_dualsense4unix.integrations.uhid_gamepad import (
        ATIVIDADE_LIGHTBAR,
        ATIVIDADE_TRIGGER,
    )

    relogio = _Relogio()
    vpad = _vpad_de_bancada()(relogio)

    assert vpad.visto_ha_s == {}, "vpad recém-nascido não viu nada"

    vpad._carimbar(ATIVIDADE_TRIGGER)
    assert vpad.visto_ha_s == {ATIVIDADE_TRIGGER: 0.0}
    assert ATIVIDADE_LIGHTBAR not in vpad.visto_ha_s, (
        "categoria que nunca aconteceu tem de ficar AUSENTE, não zerada"
    )

    relogio.avancar(7.5)
    assert vpad.visto_ha_s[ATIVIDADE_TRIGGER] == 7.5, "a idade tem de envelhecer"

    vpad._carimbar(ATIVIDADE_TRIGGER)
    assert vpad.visto_ha_s[ATIVIDADE_TRIGGER] == 0.0, "e rejuvenescer no evento"


def test_categoria_sem_sink_nao_e_carimbada() -> None:
    """Réplica sem sink não chegou a lugar nenhum — e não pode dizer que sim."""
    from hefesto_dualsense4unix.integrations.uhid_gamepad import ATIVIDADE_TRIGGER

    relogio = _Relogio()
    vpad = _vpad_de_bancada()(relogio)
    vpad.trigger_sink = None

    vpad._forward_replica("trigger_right", b"\x00" * 11, primeira=True)

    assert ATIVIDADE_TRIGGER not in vpad.visto_ha_s
    assert vpad.trigger_replicas == 0

    recebido: list[Any] = []
    vpad.trigger_sink = lambda lado, valor: recebido.append((lado, valor))
    vpad._forward_replica("trigger_right", b"\x00" * 11, primeira=False)

    assert recebido, "com sink, a réplica sai"
    assert vpad.visto_ha_s[ATIVIDADE_TRIGGER] == 0.0


def test_o_daemon_publica_o_carimbo_e_sobrevive_a_vpad_sem_ele() -> None:
    """O `state_full` nunca pode morrer por causa de uma linha de telemetria.

    O vpad pode ser um `uinput` (que não tem hidraw e não tem o que carimbar)
    ou um dublê. O saneador devolve `{}` nesses casos, e descarta valores
    não-numéricos — o payload vira JSON, e um valor exótico aqui derrubaria a
    serialização inteira por causa do campo menos importante dela.

    Mordida: trocar o `_visto_ha_s` por `vp.visto_ha_s` direto no
    `ipc_handlers`. As duas últimas asserções levantam AttributeError.
    """
    from hefesto_dualsense4unix.daemon.ipc_handlers import _visto_ha_s

    class _ComCarimbo:
        visto_ha_s: ClassVar[dict[str, Any]] = {
            "rumble": 0.5,
            "lightbar": 3.0,
            "lixo": "agora",
        }

    class _SemCarimbo:
        pass

    assert _visto_ha_s(_ComCarimbo()) == {"rumble": 0.5, "lightbar": 3.0}
    assert _visto_ha_s(_SemCarimbo()) == {}
    assert _visto_ha_s(None) == {}


