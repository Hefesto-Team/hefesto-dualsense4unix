"""R-04 (auditoria 23/07) — o vpad não é destruído com o jogo na autoridade.

Medido ao vivo: trocar a máscara com o jogo já rodando DESTRÓI e RECRIA os
vpads, e o jogo perde os handles que abriu (a Steam nunca reabre o hidraw do
vpad do P1). Como o modo do perfil só era aplicado quando a JANELA aparecia —
ou seja, sempre com o jogo já rodando — a sequência era determinística: abrir o
Sackboy (perfil ``dualsense``) com a máscara global em ``xbox`` derrubava o
controle de todo mundo no meio da partida.

Contradição 3 da §5 do plano: a operação DESTRUTIVA lê o sinal STICKY
(``display_authority``), porque aqui o fail-safe é NÃO destruir; a reversão de
modo para desktop continua lendo a janela CRUA (R-02, ``lifecycle.py``). Os
dois sinais NÃO são unificados.

O gesto MANUAL nunca é bloqueado: trocar de máscara com o jogo aberto é escolha
legítima dela (é o "botão de força" do VPAD-02).
"""

from __future__ import annotations

from typing import Any

import pytest

import hefesto_dualsense4unix.daemon.subsystems.gamepad as gp
from hefesto_dualsense4unix.daemon.subsystems.gamepad import (
    start_gamepad_emulation,
    upgrade_primary_vpad_to_uhid,
)


class _Vpad:
    def __init__(self, flavor: str, backend: str = "uhid", vivo: bool = True) -> None:
        self.flavor = flavor
        self.backend = backend
        self._started = vivo
        self.parado = False

    def stop(self) -> None:
        self.parado = True


class _DaemonFalso:
    """Superfície mínima de `start_gamepad_emulation` + o sinal de autoridade."""

    def __init__(self, *, autoridade: str, vpad: _Vpad | None) -> None:
        from hefesto_dualsense4unix.daemon.lifecycle import DaemonConfig

        self.config = DaemonConfig()
        self.config.gamepad_emulation_enabled = vpad is not None
        self.config.gamepad_flavor = vpad.flavor if vpad is not None else "dualsense"
        self._gamepad_device: Any = vpad
        self._mouse_device = None
        self.controller = None
        self.display_authority = autoridade
        self._last_rebackend_ts = float("-inf")


@pytest.fixture(autouse=True)
def _sem_efeito_real(monkeypatch: pytest.MonkeyPatch) -> None:
    """Nenhum device real: só a DECISÃO de recriar (ou não) está sob teste."""
    import hefesto_dualsense4unix.integrations.virtual_pad as vp

    monkeypatch.setattr(
        vp,
        "make_virtual_pad",
        lambda key, **k: _Vpad(key, backend="uinput"),
    )
    monkeypatch.setattr(gp, "make_primary_rumble_sink", lambda *a, **k: None)
    monkeypatch.setattr(gp, "make_primary_replica_sinks", lambda *a, **k: {})
    monkeypatch.setattr(gp, "read_primary_calibration", lambda *a, **k: None)
    monkeypatch.setattr(gp, "controller_allows_uhid", lambda *a, **k: False)
    monkeypatch.setattr(gp, "start_motion_reader", lambda *a, **k: None)
    monkeypatch.setattr(gp, "stop_motion_reader", lambda *a, **k: None)
    monkeypatch.setattr(gp, "_set_controller_grab", lambda *a, **k: None)
    monkeypatch.setattr(gp, "_materialize_launch_env", lambda *a, **k: None)
    monkeypatch.setattr(gp, "notify_vpad_degradado", lambda *a, **k: None)
    monkeypatch.setattr(
        "hefesto_dualsense4unix.utils.session.save_gamepad_emulation",
        lambda *a, **k: None,
    )
    monkeypatch.setattr(
        "hefesto_dualsense4unix.daemon.subsystems.rumble.zero_motors_on_mode_exit",
        lambda *a, **k: None,
    )


class TestGateDestrutivo:
    def test_perfil_nao_troca_mascara_com_o_jogo_na_autoridade(self) -> None:
        """O caso medido: Sackboy aberto, perfil pede outra máscara."""
        vpad = _Vpad("dualsense")
        daemon = _DaemonFalso(autoridade="game", vpad=vpad)

        assert start_gamepad_emulation(daemon, "xbox", origin="profile") is True

        assert vpad.parado is False, (
            "o vpad do jogo foi destruído no meio da partida — é exatamente o "
            "'abri o jogo e os controles morreram' da queixa"
        )
        assert daemon._gamepad_device is vpad
        assert daemon.config.gamepad_flavor == "dualsense"
        assert daemon.config.gamepad_emulation_enabled is True

    def test_gesto_manual_dela_continua_trocando_a_mascara(self) -> None:
        """A última palavra é sempre dela — o gate só segura o automático."""
        vpad = _Vpad("dualsense")
        daemon = _DaemonFalso(autoridade="game", vpad=vpad)

        assert start_gamepad_emulation(daemon, "xbox", origin="manual") is True

        assert vpad.parado is True
        assert daemon._gamepad_device is not vpad
        assert daemon.config.gamepad_flavor == "xbox"

    def test_fora_do_jogo_o_perfil_troca_normalmente(self) -> None:
        """Sem o jogo na autoridade não há handle para invalidar."""
        vpad = _Vpad("dualsense")
        daemon = _DaemonFalso(autoridade="daemon", vpad=vpad)

        assert start_gamepad_emulation(daemon, "xbox", origin="profile") is True

        assert vpad.parado is True
        assert daemon.config.gamepad_flavor == "xbox"

    def test_autoridade_desconhecida_nao_bloqueia(self) -> None:
        """Gate largo demais faria o perfil não valer NUNCA (risco (b) do R-04)."""
        vpad = _Vpad("dualsense")
        daemon = _DaemonFalso(autoridade="unknown", vpad=vpad)

        start_gamepad_emulation(daemon, "xbox", origin="profile")

        assert daemon.config.gamepad_flavor == "xbox"

    def test_vpad_morto_pode_ser_recriado_mesmo_no_jogo(self) -> None:
        """Vpad derrubado por UHID_STOP: não há o que perder, e recriar é a
        única chance de o jogo ter controle."""
        vpad = _Vpad("dualsense", vivo=False)
        daemon = _DaemonFalso(autoridade="game", vpad=vpad)

        start_gamepad_emulation(daemon, "xbox", origin="profile")

        assert vpad.parado is True
        assert daemon.config.gamepad_flavor == "xbox"

    def test_apply_identico_segue_no_op(self) -> None:
        """A idempotência do VPAD-02 não pode ser confundida com o gate."""
        vpad = _Vpad("dualsense")
        daemon = _DaemonFalso(autoridade="game", vpad=vpad)

        assert start_gamepad_emulation(daemon, "dualsense", origin="profile") is True

        assert vpad.parado is False
        assert daemon._gamepad_device is vpad


class TestPromocaoUhidNoJogo:
    def test_promocao_por_hotplug_nao_recria_vpad_com_jogo_na_autoridade(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Reconexão BT é frequente nesta máquina: recuperar vibração não pode
        custar o controle inteiro do jogo."""
        monkeypatch.setattr(gp, "controller_allows_uhid", lambda *a, **k: True)
        monkeypatch.setattr(
            "hefesto_dualsense4unix.integrations.uhid_gamepad.uhid_available",
            lambda: True,
        )
        vpad = _Vpad("dualsense", backend="uinput")
        daemon = _DaemonFalso(autoridade="game", vpad=vpad)

        assert upgrade_primary_vpad_to_uhid(daemon) is False
        assert vpad.parado is False
        assert daemon._last_rebackend_ts == float("-inf"), (
            "o gate não pode consumir o cooldown — a promoção legítima depois "
            "do jogo ficaria bloqueada por 30 s à toa"
        )

    def test_revive_pos_falha_total_nao_e_bloqueado(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """VPAD-09: sem device NENHUM o jogo já está com zero controles —
        reviver só pode melhorar, mesmo com o jogo na autoridade."""
        monkeypatch.setattr(gp, "controller_allows_uhid", lambda *a, **k: True)
        daemon = _DaemonFalso(autoridade="game", vpad=None)
        daemon.config.gamepad_emulation_enabled = True

        assert upgrade_primary_vpad_to_uhid(daemon) is True
        assert daemon._gamepad_device is not None
