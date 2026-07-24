"""FEAT-AUTOSWITCH-LOCK-01 (pedido da mantenedora, 23/07).

*"no sackboy a ideia era ficar a seleção que eu marquei na interface... deixar
na interface a opção de escolha"*, e *"o madjack também é o mesmo lance"*.

Um cadeado explícito da troca AUTOMÁTICA de perfil: enquanto ligado, o
AutoSwitcher não troca de perfil por foco de janela — a escolha dela fica —, mas
gamepad/co-op/rumble seguem vivos (é o oposto do pause do daemon).
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

from hefesto_dualsense4unix.daemon.state_store import StateStore
from hefesto_dualsense4unix.profiles.autoswitch import AutoSwitcher
from hefesto_dualsense4unix.profiles.manager import ProfileManager


def _switcher(store: StateStore) -> tuple[AutoSwitcher, MagicMock]:
    manager = MagicMock(spec=ProfileManager)
    sw = AutoSwitcher(manager=manager, window_reader=lambda: {}, store=store)
    return sw, manager


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
    def test_travado_nao_troca_de_perfil(self) -> None:
        store = StateStore()
        store.set_active_profile("FPS")
        store.set_autoswitch_locked(True)
        sw, manager = _switcher(store)
        # Uma janela de jogo que NORMALMENTE ativaria outro perfil.
        sw._tick({"wm_class": "steam_app_1599660", "wm_name": "Sackboy"}, 999.0)
        manager.select_for_window.assert_not_called()
        manager.activate.assert_not_called()

    def test_destravado_volta_a_decidir(self) -> None:
        store = StateStore()
        store.set_autoswitch_locked(False)
        sw, manager = _switcher(store)
        manager.select_for_window.return_value = None
        sw._tick({"wm_class": "firefox", "wm_name": "Mozilla"}, 999.0)
        manager.select_for_window.assert_called()

    def test_travado_e_metodo_publico_concordam(self) -> None:
        store = StateStore()
        sw, _ = _switcher(store)
        assert sw.travado() is False
        store.set_autoswitch_locked(True)
        assert sw.travado() is True

    def test_sem_store_nunca_travado(self) -> None:
        sw = AutoSwitcher(manager=MagicMock(), window_reader=lambda: {})
        assert sw.travado() is False


class TestPersistencia:
    def test_flag_roundtrip(self, tmp_path: Any, monkeypatch: Any) -> None:
        from hefesto_dualsense4unix.utils import session as sess

        monkeypatch.setattr(sess, "config_dir", lambda ensure=False: tmp_path)
        assert sess.load_autoswitch_locked() is False
        sess.save_autoswitch_locked(True)
        assert sess.load_autoswitch_locked() is True
        sess.save_autoswitch_locked(False)
        assert sess.load_autoswitch_locked() is False


class TestHandlerIPC:
    def test_toggle_e_persiste(self, tmp_path: Any, monkeypatch: Any) -> None:
        import asyncio

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
        import asyncio

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
