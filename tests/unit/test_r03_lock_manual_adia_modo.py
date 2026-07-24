"""R-03 (auditoria 23/07) — o lock de gesto manual ADIA a seção `mode`.

Sintoma medido (queixa 1 da mantenedora): ela mexia na máscara e, em menos de
30 s, abria o Sackboy. O `mode` do perfil era descartado em silêncio pelo lock
de gesto manual (`_emu_manual_ts`), a ativação era COMMITADA assim mesmo, o IPC
respondia sucesso e NADA reaplicava depois — a máscara ficava errada a sessão
inteira com a GUI mostrando o perfil ativo.

O que este arquivo trava:

  - ativação automática (autoswitch) **adia**: devolve ``adiado_lock_manual`` e
    guarda UMA pendência, sempre sobrescrita, nunca enfileirada;
  - ativação manual (`profile.switch`/PS+D-pad) **fura** o lock e consome o
    carimbo — o gesto mais novo dela é "ative este perfil";
  - o dreno do poll loop aplica UMA vez, e só se o perfil ainda for o mesmo,
    sem gesto manual novo e sem trocar máscara com o jogo na autoridade;
  - o `profile.switch` responde a verdade (`mode_aplicado`/`secoes`).

Contradições 1 e 2 da consolidação: a variante "não commitar `_current_profile`
para o autoswitch tentar de novo" está REJEITADA (rodaria `_activate` ~60x em
30 s, reescrevendo gatilhos/LEDs a 2 Hz — o flap que o MISC-08 removeu), e o
retry é gated pelo jogo (recriar vpad mid-game invalida os handles do jogo).
"""
from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from hefesto_dualsense4unix.daemon import lifecycle as lifecycle_mod
from hefesto_dualsense4unix.daemon.lifecycle import Daemon, DaemonConfig
from hefesto_dualsense4unix.daemon.state_store import (
    MANUAL_PROFILE_LOCK_SEC,
    StateStore,
)
from hefesto_dualsense4unix.profiles import loader as loader_module
from hefesto_dualsense4unix.profiles.loader import save_profile
from hefesto_dualsense4unix.profiles.manager import ProfileManager
from hefesto_dualsense4unix.profiles.schema import Profile
from hefesto_dualsense4unix.testing.fake_controller import FakeController

# ---------------------------------------------------------------------------
# Infra
# ---------------------------------------------------------------------------


class _Relogio:
    """Relógio monotônico controlado pelo teste.

    O lock é de 30 s de parede: sem controlar o tempo não dá para provar "adiou
    agora" e "drenou depois" no mesmo teste. Mesmo padrão já usado em
    `test_autoswitch_manual_lock.py` (patch de `time.monotonic` no módulo).
    """

    def __init__(self, t0: float = 10_000.0) -> None:
        self.agora = t0

    def __call__(self) -> float:
        return self.agora

    def avancar(self, segundos: float) -> None:
        self.agora += segundos


@pytest.fixture
def relogio(monkeypatch: pytest.MonkeyPatch) -> _Relogio:
    r = _Relogio()
    monkeypatch.setattr(lifecycle_mod.time, "monotonic", r)
    return r


class _Setters:
    """Captura os setters do daemon (política, não efeito de hardware)."""

    def __init__(self, daemon: Daemon) -> None:
        self.gamepad: list[tuple[bool, str | None, str]] = []
        self.native: list[tuple[bool, str]] = []
        self.coop: list[tuple[bool, str]] = []
        self._daemon = daemon

    def bind(self, monkeypatch: pytest.MonkeyPatch) -> None:
        d = self._daemon

        def fake_gamepad(
            enabled: bool, flavor: str | None = None, *, origin: str = "manual"
        ) -> bool:
            self.gamepad.append((enabled, flavor, origin))
            d.config.gamepad_emulation_enabled = enabled
            d._gamepad_device = (
                SimpleNamespace(flavor=flavor or "dualsense") if enabled else None
            )
            return True

        def fake_native(
            enabled: bool,
            *,
            reapply: bool = True,
            restore_stash: bool = False,
            origin: str = "manual",
        ) -> bool:
            self.native.append((enabled, origin))
            d._native_mode = enabled
            return enabled

        def fake_coop(enabled: bool, *, origin: str = "manual") -> bool:
            self.coop.append((enabled, origin))
            d.config.coop_enabled = enabled
            return enabled

        monkeypatch.setattr(d, "set_gamepad_emulation", fake_gamepad)
        monkeypatch.setattr(d, "set_native_mode", fake_native)
        monkeypatch.setattr(d, "set_coop_enabled", fake_coop)


def _perfil(mode: dict[str, Any] | None, *, nome: str = "sackboy_nativo") -> Profile:
    """Perfil ESPECÍFICO (regra do jogo) — não catch-all: o R-02 já cobre esse."""
    dados: dict[str, Any] = {
        "name": nome,
        "version": 1,
        "match": {"type": "criteria", "window_class": ["steam_app_1599660"]},
        "priority": 80,
    }
    if mode is not None:
        dados["mode"] = mode
    return Profile.model_validate(dados)


@pytest.fixture
def daemon() -> Daemon:
    return Daemon(controller=FakeController(), config=DaemonConfig())


def _com_mascara_mexida_agora(daemon: Daemon, relogio: _Relogio) -> None:
    """Estado inicial da queixa: ela acabou de trocar a máscara na GUI."""
    daemon._emu_manual_ts = relogio.agora
    daemon.config.gamepad_emulation_enabled = True
    daemon._gamepad_device = SimpleNamespace(flavor="xbox")


# ---------------------------------------------------------------------------
# 1) Adiamento (em vez de descarte silencioso)
# ---------------------------------------------------------------------------


class TestAdiamento:
    def test_lock_adia_a_secao_e_agenda_pendencia(
        self, daemon: Daemon, relogio: _Relogio, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        setters = _Setters(daemon)
        setters.bind(monkeypatch)
        _com_mascara_mexida_agora(daemon, relogio)
        perfil = _perfil({"kind": "gamepad", "gamepad_flavor": "dualsense"})

        estado = daemon.apply_profile_mode(
            perfil.mode, profile=perfil, origin="autoswitch"
        )

        assert estado == "adiado_lock_manual"
        assert setters.gamepad == []  # o lock continua protegendo o gesto dela
        pendencia = daemon._mode_pendente
        assert pendencia is not None
        assert pendencia.profile_name == "sackboy_nativo"
        # A pendência vence quando o lock vence — nem antes nem "nunca".
        assert pendencia.nao_antes_de == pytest.approx(
            relogio.agora + MANUAL_PROFILE_LOCK_SEC
        )

    def test_pendencia_e_sobrescrita_nunca_enfileirada(
        self, daemon: Daemon, relogio: _Relogio, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Alt-tab entre dois jogos dentro da mesma janela de 30 s.

        Enfileirar aplicaria um modo que já não corresponde ao perfil ativo.
        """
        setters = _Setters(daemon)
        setters.bind(monkeypatch)
        _com_mascara_mexida_agora(daemon, relogio)

        primeiro = _perfil({"kind": "gamepad", "gamepad_flavor": "dualsense"})
        segundo = _perfil({"kind": "native"}, nome="madjack")
        daemon.apply_profile_mode(primeiro.mode, profile=primeiro, origin="autoswitch")
        daemon.apply_profile_mode(segundo.mode, profile=segundo, origin="autoswitch")

        pendencia = daemon._mode_pendente
        assert pendencia is not None
        assert pendencia.profile_name == "madjack"
        assert getattr(pendencia.mode, "kind", None) == "native"

    def test_gesto_manual_fura_o_lock_e_consome_o_carimbo(
        self, daemon: Daemon, relogio: _Relogio, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """`profile.switch`/PS+D-pad é gesto MAIS NOVO que a máscara."""
        setters = _Setters(daemon)
        setters.bind(monkeypatch)
        _com_mascara_mexida_agora(daemon, relogio)
        perfil = _perfil({"kind": "gamepad", "gamepad_flavor": "dualsense"})

        estado = daemon.apply_profile_mode(
            perfil.mode, profile=perfil, origin="manual"
        )

        assert estado == "aplicado"
        assert setters.gamepad == [(True, "dualsense", "profile")]
        assert daemon._mode_pendente is None
        # Consumido: a máscara que ESTE perfil acabou de pôr não pode travar o
        # perfil seguinte (o do jogo, quando a janela aparecer).
        assert daemon._emu_manual_ts == float("-inf")

    def test_ativacao_que_passa_do_lock_descarta_pendencia_velha(
        self, daemon: Daemon, relogio: _Relogio, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        setters = _Setters(daemon)
        setters.bind(monkeypatch)
        _com_mascara_mexida_agora(daemon, relogio)
        velho = _perfil({"kind": "native"}, nome="antigo")
        daemon.apply_profile_mode(velho.mode, profile=velho, origin="autoswitch")
        assert daemon._mode_pendente is not None

        relogio.avancar(MANUAL_PROFILE_LOCK_SEC + 1)
        novo = _perfil({"kind": "gamepad", "gamepad_flavor": "dualsense"})
        daemon.apply_profile_mode(novo.mode, profile=novo, origin="autoswitch")

        assert daemon._mode_pendente is None
        assert setters.native == []  # o modo velho NÃO ressuscita


# ---------------------------------------------------------------------------
# 2) Dreno (a metade que faltava: alguém reaplica depois)
# ---------------------------------------------------------------------------


class TestDreno:
    def _adiar(
        self,
        daemon: Daemon,
        relogio: _Relogio,
        monkeypatch: pytest.MonkeyPatch,
        *,
        mode: dict[str, Any] | None = None,
    ) -> _Setters:
        setters = _Setters(daemon)
        setters.bind(monkeypatch)
        _com_mascara_mexida_agora(daemon, relogio)
        perfil = _perfil(mode or {"kind": "gamepad", "gamepad_flavor": "dualsense"})
        daemon.store.set_active_profile(perfil.name)
        daemon.apply_profile_mode(perfil.mode, profile=perfil, origin="autoswitch")
        assert daemon._mode_pendente is not None
        return setters

    def test_dreno_espera_o_lock_vencer(
        self, daemon: Daemon, relogio: _Relogio, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        setters = self._adiar(daemon, relogio, monkeypatch)
        relogio.avancar(MANUAL_PROFILE_LOCK_SEC - 1)

        daemon._drenar_modo_pendente()

        assert setters.gamepad == []
        assert daemon._mode_pendente is not None

    def test_dreno_aplica_uma_unica_vez(
        self, daemon: Daemon, relogio: _Relogio, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A cura da queixa: a máscara do perfil entra quando o lock vence.

        E entra UMA vez — o dreno roda a ~1 Hz; repetir a aplicação seria o
        flap de teardown/respawn de vpad que o MISC-08 removeu.
        """
        setters = self._adiar(daemon, relogio, monkeypatch)
        relogio.avancar(MANUAL_PROFILE_LOCK_SEC + 0.5)

        daemon._drenar_modo_pendente()
        daemon._drenar_modo_pendente()
        daemon._drenar_modo_pendente()

        assert setters.gamepad == [(True, "dualsense", "profile")]
        assert daemon._mode_pendente is None
        assert daemon._mode_from_profile == "gamepad"

    def test_dreno_descarta_apos_gesto_manual_novo(
        self, daemon: Daemon, relogio: _Relogio, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A última palavra é dela: gesto novo mata a pendência do perfil."""
        setters = self._adiar(daemon, relogio, monkeypatch)
        relogio.avancar(20.0)
        daemon._emu_manual_ts = relogio.agora  # ela mexeu na máscara de novo
        relogio.avancar(MANUAL_PROFILE_LOCK_SEC + 1)

        daemon._drenar_modo_pendente()

        assert setters.gamepad == []
        assert daemon._mode_pendente is None

    def test_dreno_descarta_quando_o_perfil_ativo_mudou(
        self, daemon: Daemon, relogio: _Relogio, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Aplicar modo de perfil obsoleto é o risco declarado do retry."""
        setters = self._adiar(daemon, relogio, monkeypatch)
        daemon.store.set_active_profile("navegacao")
        relogio.avancar(MANUAL_PROFILE_LOCK_SEC + 1)

        daemon._drenar_modo_pendente()

        assert setters.gamepad == []
        assert daemon._mode_pendente is None

    def test_dreno_nao_troca_mascara_com_o_jogo_na_autoridade(
        self, daemon: Daemon, relogio: _Relogio, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Recriar vpad mid-game invalida os handles do jogo (medido ao vivo).

        A pendência SEGURA (não morre) e entra na primeira borda em que a
        autoridade de exibição sai de "game".
        """
        setters = self._adiar(daemon, relogio, monkeypatch)
        daemon._game_signal = SimpleNamespace(authority="game")
        relogio.avancar(MANUAL_PROFILE_LOCK_SEC + 1)

        daemon._drenar_modo_pendente()
        daemon._drenar_modo_pendente()

        assert setters.gamepad == []
        assert daemon._mode_pendente is not None

        daemon._game_signal = SimpleNamespace(authority="daemon")
        daemon._drenar_modo_pendente()

        assert setters.gamepad == [(True, "dualsense", "profile")]

    def test_dreno_aplica_com_jogo_aberto_quando_nao_e_destrutivo(
        self, daemon: Daemon, relogio: _Relogio, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Gate só para o que DESTRÓI: mesmo flavor não recria vpad nenhum.

        Sem esta assimetria o gate viraria "o perfil nunca é aplicado", que é a
        própria queixa (risco (b) do R-04 no plano).
        """
        setters = _Setters(daemon)
        setters.bind(monkeypatch)
        daemon._emu_manual_ts = relogio.agora
        daemon.config.gamepad_emulation_enabled = True
        daemon._gamepad_device = SimpleNamespace(flavor="dualsense")
        perfil = _perfil({"kind": "gamepad", "gamepad_flavor": "dualsense", "coop": True})
        daemon.store.set_active_profile(perfil.name)
        daemon.apply_profile_mode(perfil.mode, profile=perfil, origin="autoswitch")
        daemon._game_signal = SimpleNamespace(authority="game")
        relogio.avancar(MANUAL_PROFILE_LOCK_SEC + 1)

        daemon._drenar_modo_pendente()

        # Vpad intocado (mesmo flavor, `set_gamepad_emulation` nem é chamado) e
        # o co-op do perfil sobe — que é o que ela precisa para jogar a 4.
        assert setters.gamepad == []
        assert setters.coop == [(True, "profile")]
        assert daemon._mode_pendente is None


# ---------------------------------------------------------------------------
# 3) Relatório do manager + cenário fim-a-fim da queixa
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


def _manager(daemon: Daemon, store: StateStore) -> ProfileManager:
    return ProfileManager(
        controller=daemon.controller,
        store=store,
        mode_applier=daemon.apply_profile_mode,
        suppression_applier=daemon.apply_profile_suppression,
        mouse_applier=daemon.apply_profile_mouse,
    )


class TestRelatorio:
    def test_relatorio_marca_a_secao_adiada(
        self,
        daemon: Daemon,
        relogio: _Relogio,
        monkeypatch: pytest.MonkeyPatch,
        isolated_profiles_dir: Path,
    ) -> None:
        setters = _Setters(daemon)
        setters.bind(monkeypatch)
        _com_mascara_mexida_agora(daemon, relogio)
        save_profile(_perfil({"kind": "gamepad", "gamepad_flavor": "dualsense"}))
        manager = _manager(daemon, daemon.store)

        relatorio: dict[str, str] = {}
        manager.activate(
            "sackboy_nativo", origin="autoswitch", relatorio=relatorio
        )

        # A ativação é COMMITADA (nada de flap a 2 Hz) e o relatório conta o que
        # ficou pendente — antes disso a seção sumia sem rastro nenhum.
        assert daemon.store.active_profile == "sackboy_nativo"
        assert relatorio["mode"] == "adiado_lock_manual"
        assert daemon._mode_pendente is not None

    def test_ativacao_manual_aplica_o_modo_mesmo_com_a_mascara_recem_mexida(
        self,
        daemon: Daemon,
        relogio: _Relogio,
        monkeypatch: pytest.MonkeyPatch,
        isolated_profiles_dir: Path,
    ) -> None:
        """O caso (a) da validação ao vivo do plano, sem hardware."""
        setters = _Setters(daemon)
        setters.bind(monkeypatch)
        _com_mascara_mexida_agora(daemon, relogio)
        save_profile(_perfil({"kind": "gamepad", "gamepad_flavor": "dualsense"}))
        manager = _manager(daemon, daemon.store)

        relatorio: dict[str, str] = {}
        manager.activate("sackboy_nativo", origin="manual", relatorio=relatorio)

        assert relatorio["mode"] == "aplicado"
        assert setters.gamepad == [(True, "dualsense", "profile")]


class TestIpcProfileSwitch:
    @pytest.mark.asyncio
    async def test_profile_switch_responde_a_verdade(
        self,
        daemon: Daemon,
        relogio: _Relogio,
        monkeypatch: pytest.MonkeyPatch,
        isolated_profiles_dir: Path,
    ) -> None:
        from hefesto_dualsense4unix.daemon.ipc_handlers import IpcHandlersMixin

        setters = _Setters(daemon)
        setters.bind(monkeypatch)
        _com_mascara_mexida_agora(daemon, relogio)
        save_profile(_perfil({"kind": "gamepad", "gamepad_flavor": "dualsense"}))
        monkeypatch.setattr(
            "hefesto_dualsense4unix.utils.session.save_active_marker",
            lambda _n: None,
        )

        class _Host(IpcHandlersMixin):
            pass

        host = _Host()
        host.store = daemon.store
        host.daemon = None  # pula o materialize_launch_env
        host.profile_manager = _manager(daemon, daemon.store)

        resposta = await host._handle_profile_switch({"name": "sackboy_nativo"})

        # Gesto manual fura o lock: modo aplicado DE VERDADE, e a resposta diz.
        assert resposta["active_profile"] == "sackboy_nativo"
        assert resposta["mode_aplicado"] is True
        assert resposta["secoes"]["mode"] == "aplicado"
        assert setters.gamepad == [(True, "dualsense", "profile")]


# ---------------------------------------------------------------------------
# 4) Fiação no poll loop (sem ela, a pendência nunca é drenada)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_poll_loop_drena_a_pendencia() -> None:
    """Integração com `Daemon.run()`: quem chama o dreno é o poll loop.

    Relógio REAL aqui de propósito (o loop do asyncio depende dele): a
    pendência nasce com o carimbo no passado, então já está vencida.
    """
    from hefesto_dualsense4unix.core.controller import ControllerState

    estados = [
        ControllerState(
            battery_pct=80, l2_raw=0, r2_raw=0, connected=True, transport="usb"
        )
        for _ in range(2000)
    ]
    daemon = Daemon(
        controller=FakeController(transport="usb", states=estados),
        config=DaemonConfig(
            poll_hz=200,
            auto_reconnect=False,
            ipc_enabled=False,
            udp_enabled=False,
            autoswitch_enabled=False,
            mouse_emulation_enabled=False,
            keyboard_emulation_enabled=False,
        ),
    )
    aplicados: list[tuple[Any, str]] = []

    def fake_apply(mode: Any, *, profile: Any = None, origin: str = "autoswitch") -> str:
        aplicados.append((mode, origin))
        return "aplicado"

    run_task = asyncio.create_task(daemon.run())
    try:
        await asyncio.sleep(0.05)  # deixa o run() subir e conectar
        perfil = _perfil({"kind": "gamepad", "gamepad_flavor": "dualsense"})
        daemon.store.set_active_profile(perfil.name)
        daemon._emu_manual_ts = lifecycle_mod.time.monotonic() - 120.0
        daemon._mode_pendente = lifecycle_mod.ModoAdiado(
            mode=perfil.mode,
            profile=perfil,
            profile_name=perfil.name,
            origin="autoswitch",
            carimbo_manual=daemon._emu_manual_ts,
            nao_antes_de=daemon._emu_manual_ts + MANUAL_PROFILE_LOCK_SEC,
        )
        daemon.apply_profile_mode = fake_apply  # type: ignore[method-assign]

        for _ in range(200):
            if aplicados:
                break
            await asyncio.sleep(0.02)

        assert aplicados, "o poll loop não drenou a pendência de modo (R-03)"
        assert aplicados[0][1] == "pendencia"
        assert daemon._mode_pendente is None
    finally:
        daemon.stop()
        await run_task
