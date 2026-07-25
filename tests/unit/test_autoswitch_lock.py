"""FEAT-AUTOSWITCH-LOCK-01 + LOCK-CEDE-01 — o cadeado da troca de perfil.

Pedido original da mantenedora (23/07): *"no sackboy a ideia era ficar a seleção
que eu marquei na interface... deixar na interface a opção de escolha"*, e *"o
madjack também é o mesmo lance"*. Um cadeado explícito da troca AUTOMÁTICA de
perfil: enquanto ligado, o AutoSwitcher não troca de perfil por foco de janela —
a escolha dela fica —, mas gamepad/co-op/rumble seguem vivos (é o oposto do
pause do daemon).

LOCK-CEDE-01 (decisão da mantenedora, 24/07): o cadeado **cede para regra de
jogo**. O `if self.travado(): return` era a PRIMEIRA linha do `_tick` e matava
tudo — inclusive a regra própria do jogo. Na máquina dela a flag estava ligada
(mtime 24/07 20:42) e o resultado medido foi zero `profile_autoswitch` em 90 min
com o "modo jogo" nunca ligando. A política nova mantém o que ela pediu (nenhuma
janela comum de desktop troca o perfil) e devolve o que ela também quer (o jogo
com perfil PRÓPRIO entra). O predicado que decide é o mesmo do override manual
(`perfil_e_regra_de_jogo`, R-01) — um genérico de desktop NUNCA fura.

Cobre também as rotas que IGNORAM o cadeado de propósito (decisão desta sprint,
documentada em `TestRotasQueIgnoramOCadeado`): restore de boot, ciclo por
PS+D-pad e dreno da pendência de modo. Nenhuma delas é "trocar sozinho por
janela" — que é a única coisa que o cadeado promete congelar.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from hefesto_dualsense4unix.daemon.state_store import StateStore
from hefesto_dualsense4unix.profiles import loader as loader_module
from hefesto_dualsense4unix.profiles.autoswitch import AutoSwitcher
from hefesto_dualsense4unix.profiles.loader import save_profile
from hefesto_dualsense4unix.profiles.manager import ProfileManager
from hefesto_dualsense4unix.profiles.schema import (
    MatchAny,
    MatchCriteria,
    Profile,
)
from hefesto_dualsense4unix.testing import FakeController

APPID_MMJ = 2111190  # Mullet Mad Jack — o jogo do relato
WM_MMJ = f"steam_app_{APPID_MMJ}"


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


def _switcher(store: StateStore) -> tuple[AutoSwitcher, MagicMock]:
    manager = MagicMock(spec=ProfileManager)
    sw = AutoSwitcher(manager=manager, window_reader=lambda: {}, store=store)
    return sw, manager


def _switcher_real(store: StateStore) -> AutoSwitcher:
    """AutoSwitcher com ProfileManager REAL — o cadeado só é testável de
    verdade contra o `select_for_window` de verdade (é ele que diz se o
    candidato é a regra do jogo ou um genérico de desktop)."""
    fc = FakeController()
    fc.connect()
    return AutoSwitcher(
        manager=ProfileManager(controller=fc, store=store),
        window_reader=lambda: {},
        store=store,
    )


def _perfil_do_jogo() -> Profile:
    return Profile(
        name="madjack",
        match=MatchCriteria(window_class=[WM_MMJ]),
        priority=0,  # perfil de jogo nasce com prioridade 0 (R-01)
    )


class TestStore:
    def test_default_destravado(self) -> None:
        assert StateStore().autoswitch_locked is False

    def test_liga_e_desliga(self) -> None:
        s = StateStore()
        s.set_autoswitch_locked(True)
        assert s.autoswitch_locked is True
        s.set_autoswitch_locked(False)
        assert s.autoswitch_locked is False


class TestAutoswitchRespeitaOCadeado:
    def test_travado_nao_troca_por_janela_comum(
        self, isolated_profiles_dir: Path
    ) -> None:
        """O que ela pediu: nenhuma janela de desktop troca o perfil.

        `Navegação` casa a janela `steam` e é justamente metade do ping-pong do
        journal de 22-23/07 — com o cadeado ligado, ela não entra por mais
        estável que o foco fique.
        """
        save_profile(
            Profile(
                name="Navegação",
                match=MatchCriteria(window_class=["steam"]),
                priority=50,
            )
        )
        store = StateStore()
        store.set_autoswitch_locked(True)
        sw = _switcher_real(store)

        for t in (0.0, 0.6, 30.0, 300.0):
            sw._tick({"wm_class": "steam", "wm_name": "Steam"}, t)

        assert sw._current_profile is None
        assert store.active_profile is None

    def test_travado_cede_a_regra_propria_do_jogo(
        self, isolated_profiles_dir: Path
    ) -> None:
        """LOCK-CEDE-01: o jogo com perfil PRÓPRIO entra mesmo travado — é o
        que faz o modo jogo voltar a ligar sem ela abrir mão do cadeado."""
        save_profile(_perfil_do_jogo())
        save_profile(Profile(name="vitoria", match=MatchAny(), priority=5))
        store = StateStore()
        store.set_autoswitch_locked(True)
        sw = _switcher_real(store)

        sw._tick({"wm_class": WM_MMJ, "wm_name": "Mullet Mad Jack"}, 0.0)
        sw._tick({"wm_class": WM_MMJ, "wm_name": "Mullet Mad Jack"}, 0.6)

        assert sw._current_profile == "madjack"
        assert store.active_profile == "madjack"

    def test_travado_nao_cede_a_catch_all_em_janela_de_jogo(
        self, isolated_profiles_dir: Path
    ) -> None:
        """A exceção é para a REGRA do jogo, não para "há um jogo em foco".

        Sem perfil para o Mullet Mad Jack, quem casaria é o `vitoria` (MatchAny,
        genérico de desktop) — exatamente o buraco que o R-01 fechou no override
        manual. Aqui ele fica fechado também no cadeado.
        """
        save_profile(Profile(name="vitoria", match=MatchAny(), priority=5))
        store = StateStore()
        store.set_autoswitch_locked(True)
        sw = _switcher_real(store)

        for t in (0.0, 0.6, 60.0):
            sw._tick({"wm_class": WM_MMJ, "wm_name": "Mullet Mad Jack"}, t)

        assert sw._current_profile is None

    def test_destravado_volta_a_decidir(self) -> None:
        store = StateStore()
        store.set_autoswitch_locked(False)
        sw, manager = _switcher(store)
        manager.select_for_window.return_value = None
        sw._tick({"wm_class": "firefox", "wm_name": "Mozilla"}, 999.0)
        manager.select_for_window.assert_called()

    def test_destravar_nao_ativa_no_mesmo_tick(
        self, isolated_profiles_dir: Path
    ) -> None:
        """Enquanto o cadeado segura, o relógio do debounce NÃO acumula.

        Sem zerar o candidato no caminho travado, destravar depois de horas na
        mesma janela ativaria o perfil no MESMO tick — a armadilha 1 da UX-01
        (buraco-do-debounce) por outra porta.
        """
        save_profile(
            Profile(
                name="Navegação",
                match=MatchCriteria(window_class=["steam"]),
                priority=50,
            )
        )
        store = StateStore()
        store.set_autoswitch_locked(True)
        sw = _switcher_real(store)

        for t in (0.0, 100.0, 1000.0):
            sw._tick({"wm_class": "steam"}, t)

        store.set_autoswitch_locked(False)
        sw._tick({"wm_class": "steam"}, 1000.5)
        assert sw._current_profile is None  # o tempo travado não conta

        sw._tick({"wm_class": "steam"}, 1001.2)  # estabilidade REAL
        assert sw._current_profile == "Navegação"

    def test_travado_e_metodo_publico_concordam(self) -> None:
        store = StateStore()
        sw, _ = _switcher(store)
        assert sw.travado() is False
        store.set_autoswitch_locked(True)
        assert sw.travado() is True

    def test_sem_store_nunca_travado(self) -> None:
        sw = AutoSwitcher(manager=MagicMock(), window_reader=lambda: {})
        assert sw.travado() is False

    def test_log_do_cadeado_uma_vez_por_episodio(
        self, isolated_profiles_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """O cadeado é avaliado a 2 Hz e ficou ligado 90 min na máquina dela —
        sem dedup seriam ~650 mil linhas no journal."""
        from hefesto_dualsense4unix.profiles import autoswitch as autoswitch_mod

        spy = MagicMock()
        monkeypatch.setattr(autoswitch_mod, "logger", spy)

        save_profile(
            Profile(
                name="Navegação",
                match=MatchCriteria(window_class=["steam"]),
                priority=50,
            )
        )
        store = StateStore()
        store.set_autoswitch_locked(True)
        sw = _switcher_real(store)

        for t in (0.0, 0.5, 1.0, 1.5, 2.0):
            sw._tick({"wm_class": "steam"}, t)

        eventos = [
            c
            for c in spy.info.call_args_list
            if c[0][0] == "autoswitch_congelado_pelo_cadeado"
        ]
        assert len(eventos) == 1


class TestCadeadoNoRunLoop:
    """O `run()` REAL — a auditoria apontou que a cobertura parava no `_tick`
    dirigido na mão, e é o run-loop que roda na máquina dela."""

    @pytest.mark.asyncio
    async def test_run_travado_nao_troca_por_janela_comum(
        self, isolated_profiles_dir: Path
    ) -> None:
        save_profile(
            Profile(
                name="Navegação",
                match=MatchCriteria(window_class=["steam"]),
                priority=50,
            )
        )
        store = StateStore()
        store.set_autoswitch_locked(True)
        fc = FakeController()
        fc.connect()
        manager = ProfileManager(controller=fc, store=store)
        sw = AutoSwitcher(
            manager=manager,
            window_reader=lambda: {"wm_class": "steam"},
            poll_interval_sec=0.02,
            debounce_sec=0.02,
            store=store,
        )
        sw.start()
        await asyncio.sleep(0.2)
        sw.stop()
        await sw._task  # type: ignore[union-attr]

        assert sw._current_profile is None
        assert manager.store.counter("profile.activated") == 0

    @pytest.mark.asyncio
    async def test_run_travado_cede_ao_perfil_do_jogo(
        self, isolated_profiles_dir: Path
    ) -> None:
        save_profile(_perfil_do_jogo())
        store = StateStore()
        store.set_autoswitch_locked(True)
        fc = FakeController()
        fc.connect()
        manager = ProfileManager(controller=fc, store=store)
        sw = AutoSwitcher(
            manager=manager,
            window_reader=lambda: {"wm_class": WM_MMJ},
            poll_interval_sec=0.02,
            debounce_sec=0.02,
            store=store,
        )
        sw.start()
        await asyncio.sleep(0.2)
        sw.stop()
        await sw._task  # type: ignore[union-attr]

        assert sw._current_profile == "madjack"
        # E UMA vez só: ceder não pode virar reaplicação a 2 Hz.
        assert manager.store.counter("profile.activated") == 1

    @pytest.mark.asyncio
    async def test_travar_em_runtime_congela_no_tick_seguinte(
        self, isolated_profiles_dir: Path
    ) -> None:
        """Ligar o cadeado vale na hora (o `_tick` relê o store) — sem reiniciar
        o daemon nem reabrir a GUI."""
        save_profile(
            Profile(
                name="Navegação",
                match=MatchCriteria(window_class=["steam"]),
                priority=50,
            )
        )
        save_profile(
            Profile(
                name="leitura",
                match=MatchCriteria(window_class=["firefox"]),
                priority=50,
            )
        )
        store = StateStore()
        fc = FakeController()
        fc.connect()
        manager = ProfileManager(controller=fc, store=store)
        janela = {"wm_class": "steam"}
        sw = AutoSwitcher(
            manager=manager,
            window_reader=lambda: dict(janela),
            poll_interval_sec=0.02,
            debounce_sec=0.02,
            store=store,
        )
        sw.start()
        await asyncio.sleep(0.15)
        assert sw._current_profile == "Navegação"

        store.set_autoswitch_locked(True)
        janela["wm_class"] = "firefox"
        await asyncio.sleep(0.2)
        sw.stop()
        await sw._task  # type: ignore[union-attr]

        assert sw._current_profile == "Navegação"


class TestPersistencia:
    def test_flag_roundtrip(self, tmp_path: Any, monkeypatch: Any) -> None:
        from hefesto_dualsense4unix.utils import session as sess

        monkeypatch.setattr(sess, "config_dir", lambda ensure=False: tmp_path)
        assert sess.load_autoswitch_locked() is False
        sess.save_autoswitch_locked(True)
        assert sess.load_autoswitch_locked() is True
        sess.save_autoswitch_locked(False)
        assert sess.load_autoswitch_locked() is False

    @pytest.mark.asyncio
    async def test_boot_retoma_o_cadeado_da_sessao_anterior(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """`lifecycle.run` carrega a flag no boot — a escolha dela atravessa
        reboot. Era o elo NÃO coberto: a flag existia no disco desde 24/07 e
        nenhum teste provava que o daemon a lê ao subir."""
        from hefesto_dualsense4unix.core.controller import ControllerState
        from hefesto_dualsense4unix.daemon.lifecycle import Daemon, DaemonConfig

        monkeypatch.setattr(
            "hefesto_dualsense4unix.daemon.lifecycle.INPUT_GRACE_SEC", 0.02
        )
        monkeypatch.setattr(
            "hefesto_dualsense4unix.utils.session.load_paused_state", lambda: False
        )
        monkeypatch.setattr(
            "hefesto_dualsense4unix.utils.session.save_paused_state", lambda _p: None
        )
        monkeypatch.setattr(
            "hefesto_dualsense4unix.utils.session.load_autoswitch_locked",
            lambda: True,
        )

        estado = ControllerState(
            battery_pct=80,
            l2_raw=0,
            r2_raw=0,
            connected=True,
            transport="usb",
            buttons_pressed=frozenset(),
        )
        config = DaemonConfig(
            poll_hz=200,
            auto_reconnect=False,
            ipc_enabled=False,
            udp_enabled=False,
            autoswitch_enabled=False,
            mouse_emulation_enabled=False,
            keyboard_emulation_enabled=False,
            ps_button_action="none",
            mic_button_toggles_system=False,
        )
        daemon = Daemon(
            controller=FakeController(transport="usb", states=[estado]),
            config=config,
        )
        task = asyncio.create_task(daemon.run())
        await asyncio.sleep(0.06)
        try:
            assert daemon.store.autoswitch_locked is True
        finally:
            daemon.stop()
            await task


class TestHandlerIPC:
    def test_toggle_e_persiste(self, tmp_path: Any, monkeypatch: Any) -> None:
        from hefesto_dualsense4unix.utils import session as sess

        monkeypatch.setattr(sess, "config_dir", lambda ensure=False: tmp_path)

        class _H:
            from hefesto_dualsense4unix.daemon.ipc_handlers import IpcHandlersMixin

            _handle_autoswitch_lock = IpcHandlersMixin._handle_autoswitch_lock

            def __init__(self) -> None:
                self.store = StateStore()

        h = _H()
        r1 = asyncio.run(h._handle_autoswitch_lock({}))
        assert r1["autoswitch_locked"] is True
        assert sess.load_autoswitch_locked() is True
        r2 = asyncio.run(h._handle_autoswitch_lock({}))
        assert r2["autoswitch_locked"] is False

    def test_explicito_vence_o_toggle(self, tmp_path: Any, monkeypatch: Any) -> None:
        from hefesto_dualsense4unix.daemon.ipc_handlers import IpcHandlersMixin
        from hefesto_dualsense4unix.utils import session as sess

        monkeypatch.setattr(sess, "config_dir", lambda ensure=False: tmp_path)

        class _H:
            _handle_autoswitch_lock = IpcHandlersMixin._handle_autoswitch_lock

            def __init__(self) -> None:
                self.store = StateStore()

        h = _H()
        assert asyncio.run(h._handle_autoswitch_lock({"locked": True}))["autoswitch_locked"] is True
        assert asyncio.run(h._handle_autoswitch_lock({"locked": True}))["autoswitch_locked"] is True


class TestRotasQueIgnoramOCadeado:
    """DECISÃO desta sprint: estas três rotas NÃO consultam o cadeado.

    O cadeado promete uma coisa só — *"não troca de perfil sozinho"*. Nenhuma
    das três troca sozinho:

    - `restore_last_profile` (boot/reconexão) REPÕE o perfil que ela deixou, e
      o RESTORE-ESCOPO-01 já o limita a perfis MatchAny ("sempre"). Fazê-lo
      respeitar o cadeado deixaria o boot sem perfil nenhum, que é o oposto de
      "o que eu escolhi fica";
    - o ciclo por PS+D-pad é o GESTO dela, no controle, agora — a mesma
      autoridade do `profile.switch` da GUI (que também não consulta o cadeado);
    - `_drenar_modo_pendente` não escolhe perfil: reaplica UMA seção do perfil
      JÁ ativo que o lock de gesto manual (R-03, outro lock) adiou.

    Os testes abaixo travam a decisão para que ninguém a "conserte" depois.
    """

    @pytest.mark.asyncio
    async def test_restore_de_boot_ignora_o_cadeado(
        self, isolated_profiles_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from hefesto_dualsense4unix.daemon import connection as conn_mod

        save_profile(Profile(name="vitoria", match=MatchAny(), priority=5))
        monkeypatch.setattr(
            "hefesto_dualsense4unix.utils.session.resolve_boot_profile",
            lambda: "vitoria",
        )
        store = StateStore()
        store.set_autoswitch_locked(True)
        fc = FakeController()
        fc.connect()

        async def _run_blocking(fn: Any, *a: Any) -> Any:
            return fn(*a)

        daemon = MagicMock()
        daemon.controller = fc
        daemon.store = store
        daemon._native_mode = False
        daemon._run_blocking = _run_blocking

        await conn_mod.restore_last_profile(daemon)

        assert store.active_profile == "vitoria"

    def test_ciclo_por_hotkey_nao_consulta_o_cadeado(self) -> None:
        """Contrato de código: o gesto no controle não passa pelo cadeado.

        Asserção estrutural de propósito — montar o daemon inteiro para provar
        uma AUSÊNCIA custaria mais do que vale; o que precisa ficar travado é
        que ninguém enfie o gate aqui sem reabrir esta decisão.
        """
        import inspect

        from hefesto_dualsense4unix.daemon.subsystems import hotkey as hotkey_mod

        fonte = inspect.getsource(hotkey_mod)
        assert "autoswitch_locked" not in fonte

    def test_dreno_de_modo_pendente_nao_consulta_o_cadeado(self) -> None:
        import inspect

        from hefesto_dualsense4unix.daemon.lifecycle import Daemon

        fonte = inspect.getsource(Daemon._drenar_modo_pendente)
        assert "autoswitch_locked" not in fonte
