"""FEAT-PROFILE-MODE-01 — seção `mode` do perfil + política do applier.

O perfil do jogo em foco decide o MODO do sistema (nativo/gamepad/desktop +
co-op), fazendo as features coexistirem sem toggles globais brigando. Cobre:
schema, lock manual de 30s, reversão por perfil-sem-opinião, transições entre
kinds e o respeito a gesto manual.
"""
from __future__ import annotations

from typing import Any

import pytest

from hefesto_dualsense4unix.daemon.lifecycle import Daemon, DaemonConfig
from hefesto_dualsense4unix.daemon.subsystems.gamepad import (
    EMU_APLICADO,
    EMU_DESLIGADO,
)
from hefesto_dualsense4unix.profiles.schema import Profile, ProfileModeConfig
from hefesto_dualsense4unix.testing.fake_controller import FakeController


def _profile(mode: dict[str, Any] | None, *, catch_all: bool = False) -> Profile:
    """Perfil de teste.

    R-02 (auditoria 23/07): o default virou um perfil ESPECÍFICO (`criteria`
    com `window_class`). A distinção passou a valer semanticamente — só um
    perfil com opinião pode reverter modo; um catch-all é "nenhuma regra
    casou", não "volte ao desktop". Testes que querem o catch-all pedem
    ``catch_all=True`` explicitamente.
    """
    data: dict[str, Any] = {
        "name": "teste_modo",
        "version": 1,
        "match": (
            {"type": "any"}
            if catch_all
            else {"type": "criteria", "window_class": ["app_de_desktop"]}
        ),
        "priority": 10,
    }
    if mode is not None:
        data["mode"] = mode
    return Profile.model_validate(data)


class _Calls:
    """Captura as chamadas dos setters reais do daemon (política, não efeito)."""

    def __init__(self, daemon: Daemon) -> None:
        self.native: list[tuple[bool, str]] = []
        self.native_restore_stash: list[bool] = []
        self.gamepad: list[tuple[bool, str | None, str]] = []
        self.coop: list[tuple[bool, str]] = []
        self._daemon = daemon

    def bind(self, monkeypatch: pytest.MonkeyPatch) -> None:
        d = self._daemon

        def fake_native(
            enabled: bool,
            *,
            reapply: bool = True,
            restore_stash: bool = False,
            origin: str = "manual",
        ) -> bool:
            self.native.append((enabled, origin))
            # BUG-NATIVE-REVERT-DROPS-STASH-01: registra se a reversão pediu a
            # restauração do stash (gamepad/co-op de antes do jogo).
            self.native_restore_stash.append(restore_stash)
            d._native_mode = enabled
            return enabled

        def fake_gamepad(
            enabled: bool, flavor: str | None = None, *, origin: str = "manual"
        ) -> bool:
            self.gamepad.append((enabled, flavor, origin))
            d.config.gamepad_emulation_enabled = enabled
            if enabled:
                dev = type("Vpad", (), {"flavor": flavor or "dualsense"})()
                d._gamepad_device = dev
            else:
                d._gamepad_device = None
            return True

        def fake_gamepad_desfecho(
            enabled: bool, flavor: str | None = None, *, origin: str = "manual"
        ) -> str:
            """VERDADE-01: o seam que `apply_profile_mode` usa é o do DESFECHO.

            O dublê delega ao de cima (mesma gravação de chamada) e devolve o
            vocabulário `EMU_*` — quem quer testar a recusa do gate R-04 troca
            o retorno por `EMU_BLOQUEADO_POR_JOGO`.
            """
            fake_gamepad(enabled, flavor, origin=origin)
            return EMU_APLICADO if enabled else EMU_DESLIGADO

        def fake_coop(enabled: bool, *, origin: str = "manual") -> bool:
            self.coop.append((enabled, origin))
            d.config.coop_enabled = enabled
            return enabled

        monkeypatch.setattr(d, "set_native_mode", fake_native)
        monkeypatch.setattr(d, "set_gamepad_emulation", fake_gamepad)
        monkeypatch.setattr(d, "set_gamepad_emulation_desfecho", fake_gamepad_desfecho)
        monkeypatch.setattr(d, "set_coop_enabled", fake_coop)


@pytest.fixture
def daemon() -> Daemon:
    return Daemon(controller=FakeController(), config=DaemonConfig())


def test_schema_aceita_secao_mode() -> None:
    p = _profile({"kind": "gamepad", "gamepad_flavor": "xbox"})
    assert isinstance(p.mode, ProfileModeConfig)
    assert p.mode.kind == "gamepad"
    assert p.mode.gamepad_flavor == "xbox"
    # Perfil sem a seção continua válido (aditivo ao v1).
    assert _profile(None).mode is None


def test_schema_rejeita_kind_invalido() -> None:
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        _profile({"kind": "turbo"})


def test_kind_native_liga_o_modo_nativo(
    daemon: Daemon, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = _Calls(daemon)
    calls.bind(monkeypatch)

    daemon.apply_profile_mode(_profile({"kind": "native"}).mode)

    assert calls.native == [(True, "profile")]
    assert daemon._mode_from_profile == "native"


def test_perfil_sem_opiniao_reverte_so_modo_de_perfil(
    daemon: Daemon, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = _Calls(daemon)
    calls.bind(monkeypatch)

    daemon.apply_profile_mode(_profile({"kind": "native"}).mode)
    # R-02: quem reverte é um perfil COM opinião (ex.: "Navegação" no Firefox).
    daemon.apply_profile_mode(None, profile=_profile(None))  # focou um app comum

    assert calls.native == [(True, "profile"), (False, "profile")]
    # BUG-NATIVE-REVERT-DROPS-STASH-01: a reversão por perfil-sem-opinião
    # PRECISA restaurar o stash de emulação (gamepad/co-op de antes do jogo) —
    # sem isso a usuária saía do Sackboy sem gamepad (flagrado ao vivo).
    assert calls.native_restore_stash == [False, True]
    assert daemon._mode_from_profile is None

    # Nativo de origem MANUAL não é revertido por perfil sem opinião.
    daemon._native_mode = True
    daemon._mode_from_profile = None
    calls.native.clear()
    daemon.apply_profile_mode(None, profile=_profile(None))
    assert calls.native == []


def test_kind_gamepad_liga_o_flavor_e_nao_mexe_no_coop(
    daemon: Daemon, monkeypatch: pytest.MonkeyPatch
) -> None:
    """NOTA DATADA (06/08/2026) — COOP-SEM-INTERRUPTOR-01: era
    ``test_kind_gamepad_liga_flavor_e_coop``.

    O perfil deixou de GOVERNAR o co-op. Ele nunca mais o liga (não precisa: o
    piso do daemon já nasce ligado) nem o desliga — a chamada
    ``set_coop_enabled(..., origin="profile")`` saiu do
    ``apply_profile_mode``. A máscara continua sendo do perfil, e é isso que
    este teste guarda.
    """
    calls = _Calls(daemon)
    calls.bind(monkeypatch)

    daemon.apply_profile_mode(
        _profile({"kind": "gamepad", "gamepad_flavor": "dualsense"}).mode
    )

    assert calls.gamepad == [(True, "dualsense", "profile")]
    assert calls.coop == []
    assert daemon.config.coop_enabled is True
    assert daemon._mode_from_profile == "gamepad"

    # Re-ativação do MESMO perfil (tick do autoswitch) é idempotente.
    calls.gamepad.clear()
    daemon.apply_profile_mode(
        _profile({"kind": "gamepad", "gamepad_flavor": "dualsense"}).mode
    )
    assert calls.gamepad == []
    assert calls.coop == []


class TestOCoopNaoVemDoPerfil:
    """Nenhum perfil liga nem desliga o co-op — cada controle é um jogador.

    O dono do fato é `DaemonConfig.coop_enabled`, e ele nasce ligado. Se um
    perfil conseguisse zerá-lo, os dois controles viravam o mesmo jogador sem
    caminho de volta. Cada caso aqui é uma porta que precisa continuar fechada.

    A porta do ESQUEMA (não existe campo de co-op em perfil) é guardada por
    `tests/unit/test_cada_controle_e_um_jogador.py`. Estas medem o RUNTIME.
    """

    def test_ativar_um_perfil_nao_mexe_no_coop(
        self, daemon: Daemon, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Medido de ponta a ponta: aplicar o modo não chama `set_coop_enabled`."""
        calls = _Calls(daemon)
        calls.bind(monkeypatch)

        mode = _profile({"kind": "gamepad", "gamepad_flavor": "xbox"}).mode
        assert mode is not None

        daemon.apply_profile_mode(mode)

        assert calls.coop == [], (
            f"aplicar um perfil mexeu no co-op: {calls.coop}. O perfil não tem "
            f"opinião sobre isso, e o dono é `DaemonConfig.coop_enabled`."
        )
        assert daemon.config.coop_enabled is True

    def test_perfil_sem_secao_mode_tambem_nao_mexe(
        self, daemon: Daemon, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        calls = _Calls(daemon)
        calls.bind(monkeypatch)

        daemon.apply_profile_mode(None)

        assert calls.coop == []
        assert daemon.config.coop_enabled is True

class TestR02CatchAllNaoReverte:
    """R-02 (auditoria 23/07) — "sem opinião" não é ordem de reverter.

    Jogo sem perfil próprio (Mullet Mad Jack) cai no catch-all `vitoria`, que
    tem `mode=null`. O ramo de reversão executava
    `set_gamepad_emulation(False, origin="profile")` COM O JOGO EM FOCO: zero
    controles no meio da partida.
    """

    def test_catch_all_nao_reverte_o_modo(
        self, daemon: Daemon, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        calls = _Calls(daemon)
        calls.bind(monkeypatch)
        daemon.apply_profile_mode(
            _profile({"kind": "gamepad", "gamepad_flavor": "dualsense"}).mode
        )
        daemon.config.gamepad_emulation_enabled = True
        daemon._gamepad_device = object()
        calls.gamepad.clear()

        daemon.apply_profile_mode(None, profile=_profile(None, catch_all=True))

        assert calls.gamepad == [], "catch-all não pode desligar o vpad"
        assert daemon._mode_from_profile == "gamepad", (
            "a posse do modo continua com o perfil que a tomou — o catch-all "
            "não decide nada, nem para reverter nem para soltar"
        )

    def test_sem_perfil_informado_tambem_nao_reverte(
        self, daemon: Daemon, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Fail-safe: caller que não diz quem é não derruba o modo dela."""
        calls = _Calls(daemon)
        calls.bind(monkeypatch)
        daemon.apply_profile_mode(
            _profile({"kind": "gamepad", "gamepad_flavor": "dualsense"}).mode
        )
        daemon.config.gamepad_emulation_enabled = True
        daemon._gamepad_device = object()
        calls.gamepad.clear()

        daemon.apply_profile_mode(None)

        assert calls.gamepad == []

    def test_janela_de_jogo_em_foco_bloqueia_reversao_de_perfil_especifico(
        self, daemon: Daemon, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """2ª guarda: nem uma regra específica reverte com jogo em foco.

        Cobre o caso de um perfil de desktop casar por engano (ex.: regex
        solto) enquanto ela joga.
        """
        calls = _Calls(daemon)
        calls.bind(monkeypatch)
        daemon.apply_profile_mode(
            _profile({"kind": "gamepad", "gamepad_flavor": "dualsense"}).mode
        )
        daemon.config.gamepad_emulation_enabled = True
        daemon._gamepad_device = object()
        calls.gamepad.clear()
        daemon.store.record_window_detect_read("teste", "steam_app_2111190")

        daemon.apply_profile_mode(None, profile=_profile(None))

        assert calls.gamepad == []

    def test_perfil_especifico_fora_de_jogo_reverte_normalmente(
        self, daemon: Daemon, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A reversão legítima continua acontecendo (guarda contra 'perfil grudado')."""
        calls = _Calls(daemon)
        calls.bind(monkeypatch)
        daemon.apply_profile_mode(
            _profile({"kind": "gamepad", "gamepad_flavor": "dualsense"}).mode
        )
        daemon.config.gamepad_emulation_enabled = True
        daemon._gamepad_device = object()
        calls.gamepad.clear()
        daemon.store.record_window_detect_read("teste", "firefox")

        daemon.apply_profile_mode(None, profile=_profile(None))

        assert calls.gamepad == [(False, None, "profile")]
        assert daemon._mode_from_profile is None
