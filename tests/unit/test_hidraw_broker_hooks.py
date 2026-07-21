"""Hooks do broker hide-hidraw no daemon (BROKER-01, Onda S) — gating hermético.

A política mora no daemon; o broker é burro. Prova, sem broker real (dublê
injetado em `daemon._hidraw_broker_client`, que `broker_client_for` respeita):
- hide colado no grab: `start_gamepad_emulation` esconde o hidraw do primário;
- Modo Nativo NUNCA esconde (o jogo é dono do hidraw);
- restore no release do grab: `stop_gamepad_emulation` com `release_grab=True`
  restaura TUDO; com `release_grab=False` (troca de flavor) NÃO restaura;
- backend sem `hidraw_path` (FakeController do smoke) não fala com o broker;
- broker quebrado jamais derruba a emulação (best-effort sagrado);
- re-hide do hotplug (`rehide_physical_hidraw`): primário + jogadores de co-op
  com vpad VIVO (lição 6: uhid com `_started=False` NÃO conta), com todos os
  gates (emulação/vpad/nativo) — e o `reconnect_loop` o chama pós-connect;
- co-op: promote esconde o físico do jogador; teardown restaura; `path:*` e
  externo sem handle nunca escondem.
"""
from __future__ import annotations

import asyncio
import contextlib
import threading
from types import SimpleNamespace
from typing import Any

import pytest

from hefesto_dualsense4unix.core import physical_report_reader as prr
from hefesto_dualsense4unix.daemon.lifecycle import DaemonConfig
from hefesto_dualsense4unix.daemon.subsystems import gamepad as gp
from hefesto_dualsense4unix.integrations import virtual_pad as vp
from hefesto_dualsense4unix.utils import session


class FakeBroker:
    """Dublê do HidrawBrokerClient: grava chamadas; pode explodir."""

    def __init__(self, *, explode: bool = False) -> None:
        self.calls: list[tuple[Any, ...]] = []
        self.explode = explode

    def hide(self, node: str) -> bool:
        if self.explode:
            raise OSError("broker fora do ar")
        self.calls.append(("hide", node))
        return True

    def restore(self, node: str) -> bool:
        if self.explode:
            raise OSError("broker fora do ar")
        self.calls.append(("restore", node))
        return True

    def restore_all(self) -> bool:
        if self.explode:
            raise OSError("broker fora do ar")
        self.calls.append(("restore_all",))
        return True

    def open_fd(self, node: str) -> int | None:
        self.calls.append(("open_fd", node))
        return None

    def close(self) -> None:
        self.calls.append(("close",))


class _FakeReader:
    def __init__(self, path_provider: Any, vpad: Any, **_kw: Any) -> None:
        self.path_provider = path_provider

    def start(self) -> bool:
        return True

    def stop(self) -> None: ...


class _FakeVpad:
    def __init__(self, backend: str = "uhid", *, started: bool | None = None) -> None:
        self.flavor = "dualsense"
        self.backend = backend
        # Lição 6 (#17): `_started` só existe no uhid; False = UHID_STOP do
        # probe derrubou o device (objeto vivo, vpad MORTO).
        if started is not None:
            self._started = started

    def stop(self) -> None: ...

    def forward_analog(self, **_kw: int) -> None: ...

    def forward_buttons(self, _p: frozenset[str]) -> None: ...

    def pump_ff(self) -> None: ...


class _FakeController:
    def __init__(self, nodes: dict[str | None, str | None] | None = None) -> None:
        self._evdev = SimpleNamespace(set_grab=lambda _g: True, grab_state="held")
        #: uniq (None = primário) → nó hidraw
        self.nodes = nodes if nodes is not None else {None: "/dev/hidraw3"}

    def hidraw_path(self, uniq: str | None = None) -> str | None:
        return self.nodes.get(uniq)

    def read_calibration(self, uniq: str | None = None) -> bytes | None:
        return None

    def attach_motion_reader(self, reader: Any | None) -> None: ...

    def set_rumble(self, weak: int = 0, strong: int = 0) -> None: ...


class _FakeDaemon:
    def __init__(self, *, native: bool = False) -> None:
        self._gamepad_device = None
        self._motion_reader = None
        self._mouse_device = None
        self._coop_manager = None
        self._hidraw_broker_client = FakeBroker()
        self.config = DaemonConfig()
        self.controller = _FakeController()
        self._native = native

    def is_native_mode(self) -> bool:
        return self._native

    @property
    def broker(self) -> FakeBroker:
        client = self._hidraw_broker_client
        assert isinstance(client, FakeBroker)
        return client


@pytest.fixture()
def wired(monkeypatch: pytest.MonkeyPatch) -> _FakeDaemon:
    monkeypatch.setattr(session, "save_gamepad_emulation", lambda *a, **k: None)
    monkeypatch.setattr(session, "save_mouse_emulation_enabled", lambda *a, **k: None)
    monkeypatch.setattr(prr, "PhysicalReportReader", _FakeReader)
    monkeypatch.setattr(vp, "make_virtual_pad", lambda *_a, **_k: _FakeVpad())
    return _FakeDaemon()


class TestGrabP1:
    def test_start_esconde_o_primario(self, wired: _FakeDaemon) -> None:
        assert gp.start_gamepad_emulation(wired, flavor="dualsense") is True
        assert ("hide", "/dev/hidraw3") in wired.broker.calls

    def test_nativo_nunca_esconde(self, wired: _FakeDaemon) -> None:
        wired._native = True
        gp.start_gamepad_emulation(wired, flavor="dualsense")
        assert not any(c[0] == "hide" for c in wired.broker.calls)

    def test_stop_com_release_restaura_tudo(self, wired: _FakeDaemon) -> None:
        gp.start_gamepad_emulation(wired, flavor="dualsense")
        gp.stop_gamepad_emulation(wired)  # release_grab default True
        assert ("restore_all",) in wired.broker.calls

    def test_troca_de_flavor_nao_restaura(self, wired: _FakeDaemon) -> None:
        # release_grab=False (recriação imediata): expor o físico no meio da
        # troca abriria a janela do duplicado — o gate do grab cobre de graça
        # (o ramo nem chama `_set_controller_grab(False)`).
        gp.start_gamepad_emulation(wired, flavor="dualsense")
        wired.broker.calls.clear()
        gp.stop_gamepad_emulation(wired, persist=False, release_grab=False)
        assert ("restore_all",) not in wired.broker.calls

    def test_restore_nao_tem_gate_de_modo(self, wired: _FakeDaemon) -> None:
        # Expor nunca é errado: mesmo em Modo Nativo o release restaura.
        gp.start_gamepad_emulation(wired, flavor="dualsense")
        wired._native = True
        gp.stop_gamepad_emulation(wired)
        assert ("restore_all",) in wired.broker.calls

    def test_backend_sem_hidraw_nao_fala_com_broker(self, wired: _FakeDaemon) -> None:
        # FakeController do smoke: sem `hidraw_path` (o mesmo gate do VPAD-08).
        wired.controller = SimpleNamespace(
            _evdev=SimpleNamespace(set_grab=lambda _g: True, grab_state="held")
        )
        gp.start_gamepad_emulation(wired, flavor="dualsense")
        gp.stop_gamepad_emulation(wired)
        assert wired.broker.calls == []

    def test_primario_sem_no_nao_pede_hide(self, wired: _FakeDaemon) -> None:
        # Offline no boot: hidraw_path() → None; o re-hide do hotplug cobre.
        wired.controller.nodes[None] = None
        gp.start_gamepad_emulation(wired, flavor="dualsense")
        assert not any(c[0] == "hide" for c in wired.broker.calls)

    def test_broker_explodindo_nao_derruba_emulacao(self, wired: _FakeDaemon) -> None:
        # A regra sagrada: duplicado > zero controles.
        wired._hidraw_broker_client = FakeBroker(explode=True)
        assert gp.start_gamepad_emulation(wired, flavor="dualsense") is True
        gp.stop_gamepad_emulation(wired)  # também não levanta
        assert wired.config.gamepad_emulation_enabled is False


class TestVpadVivo:
    def test_sem_objeto_nao_e_vivo(self, wired: _FakeDaemon) -> None:
        assert gp._vpad_vivo(wired) is False

    def test_uinput_sem_atributo_e_vivo(self, wired: _FakeDaemon) -> None:
        wired._gamepad_device = _FakeVpad(backend="uinput")
        assert gp._vpad_vivo(wired) is True

    def test_uhid_started_true_e_vivo(self, wired: _FakeDaemon) -> None:
        wired._gamepad_device = _FakeVpad(started=True)
        assert gp._vpad_vivo(wired) is True

    def test_uhid_derrubado_pelo_probe_nao_e_vivo(self, wired: _FakeDaemon) -> None:
        # Lição 6 (#17): UHID_STOP derruba o device sem destruir o objeto —
        # VIDA, não existência, é o gate do hide.
        wired._gamepad_device = _FakeVpad(started=False)
        assert gp._vpad_vivo(wired) is False


class TestRehideHotplug:
    def _daemon_ativo(self, wired: _FakeDaemon) -> _FakeDaemon:
        wired.config.gamepad_emulation_enabled = True
        wired._gamepad_device = _FakeVpad()
        return wired

    def test_rehide_primario(self, wired: _FakeDaemon) -> None:
        daemon = self._daemon_ativo(wired)
        gp.rehide_physical_hidraw(daemon)
        assert daemon.broker.calls == [("hide", "/dev/hidraw3")]

    def test_rehide_cobre_jogadores_do_coop(self, wired: _FakeDaemon) -> None:
        daemon = self._daemon_ativo(wired)
        daemon.controller.nodes["aabbccddee02"] = "/dev/hidraw7"
        daemon.controller.nodes["aabbccddee03"] = None  # externo sem handle
        daemon._coop_manager = SimpleNamespace(
            _players={
                "aabbccddee02": SimpleNamespace(vpad=_FakeVpad()),
                "aabbccddee03": SimpleNamespace(vpad=_FakeVpad()),
                "path:/dev/input/event9": SimpleNamespace(vpad=_FakeVpad()),
                "aabbccddee04": SimpleNamespace(vpad=None),  # sem vpad vivo
            }
        )
        gp.rehide_physical_hidraw(daemon)
        assert ("hide", "/dev/hidraw3") in daemon.broker.calls
        assert ("hide", "/dev/hidraw7") in daemon.broker.calls
        assert len([c for c in daemon.broker.calls if c[0] == "hide"]) == 2

    def test_gates_emulacao_vpad_nativo(self, wired: _FakeDaemon) -> None:
        # Emulação desligada → nada.
        gp.rehide_physical_hidraw(wired)
        assert wired.broker.calls == []
        # Emulação ligada mas SEM vpad → nada (regra de ouro).
        wired.config.gamepad_emulation_enabled = True
        gp.rehide_physical_hidraw(wired)
        assert wired.broker.calls == []
        # Nativo → nada.
        wired._gamepad_device = _FakeVpad()
        wired._native = True
        gp.rehide_physical_hidraw(wired)
        assert wired.broker.calls == []

    def test_vpad_uhid_derrubado_nao_autoriza_rehide(self, wired: _FakeDaemon) -> None:
        # Lição 6: o gate é VIDA do vpad — uhid com `_started=False` (probe
        # recusou via UHID_STOP) não pode esconder físico nenhum.
        daemon = self._daemon_ativo(wired)
        daemon._gamepad_device = _FakeVpad(started=False)
        gp.rehide_physical_hidraw(daemon)
        assert daemon.broker.calls == []

    def test_jogador_de_coop_com_vpad_morto_nao_autoriza_rehide(
        self, wired: _FakeDaemon
    ) -> None:
        # Achado Onda S #1: a lição 6 (#17) vale para P2+ — jogador de co-op
        # cujo uhid levou UHID_STOP pós-promoção (`_started=False`, objeto
        # vivo) NUNCA autoriza o rehide do próprio físico. Sem o gate, o
        # próximo tick do reconnect_loop esconderia o nó dele com o vpad
        # MORTO = zero input para aquela pessoa (invariante sagrado violado).
        daemon = self._daemon_ativo(wired)
        daemon.controller.nodes["aabbccddee02"] = "/dev/hidraw7"
        daemon.controller.nodes["aabbccddee05"] = "/dev/hidraw9"
        daemon._coop_manager = SimpleNamespace(
            _players={
                "aabbccddee02": SimpleNamespace(vpad=_FakeVpad(started=False)),
                "aabbccddee05": SimpleNamespace(vpad=_FakeVpad(started=True)),
            }
        )
        gp.rehide_physical_hidraw(daemon)
        assert ("hide", "/dev/hidraw7") not in daemon.broker.calls
        assert ("hide", "/dev/hidraw9") in daemon.broker.calls

    def test_backend_sem_hidraw_nao_fala_com_broker(self, wired: _FakeDaemon) -> None:
        daemon = self._daemon_ativo(wired)
        daemon.controller = SimpleNamespace()
        gp.rehide_physical_hidraw(daemon)
        assert daemon.broker.calls == []

    def test_no_duplicado_nao_repete_hide(self, wired: _FakeDaemon) -> None:
        # Primário e jogador no MESMO nó (não deve acontecer, mas dedup barato).
        daemon = self._daemon_ativo(wired)
        daemon.controller.nodes["aabbccddee02"] = "/dev/hidraw3"
        daemon._coop_manager = SimpleNamespace(
            _players={"aabbccddee02": SimpleNamespace(vpad=_FakeVpad())}
        )
        gp.rehide_physical_hidraw(daemon)
        assert daemon.broker.calls == [("hide", "/dev/hidraw3")]


class TestReconnectLoopRehide:
    def test_reconciliacao_online_chama_o_rehide_no_executor_do_broker(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """§2.2 + corretor final (interação S x HANG-01, achado #6): cada tick
        online do `reconnect_loop` re-esconde no executor DEDICADO do broker
        ('hefesto-broker', 1 worker) — NUNCA no pool compartilhado
        'hefesto-hid' de `_run_blocking`, do qual read_state/_gather/heal
        dependem (um broker degradado segurava até ~8s por tick 1 dos 2
        workers do pool de input; o padrão que o HANG-01 baniu)."""
        import threading

        from hefesto_dualsense4unix.daemon import connection

        chamadas: list[Any] = []
        threads_do_rehide: list[str] = []

        def _spy_rehide(daemon: Any) -> None:
            chamadas.append(daemon)
            threads_do_rehide.append(threading.current_thread().name)

        monkeypatch.setattr(gp, "rehide_physical_hidraw", _spy_rehide)
        executadas_no_pool_compartilhado: list[Any] = []

        parada = iter([False, True, True, True])
        stop_event = asyncio.Event()
        stop_event.set()  # os waits voltam na hora; _is_stopping governa o fim

        daemon = SimpleNamespace(
            controller=SimpleNamespace(
                connect=lambda: None,
                is_connected=lambda: True,
                get_transport=lambda: "usb",
            ),
            bus=SimpleNamespace(publish=lambda *a, **k: None),
            config=DaemonConfig(),
            _stop_event=stop_event,
            _is_stopping=lambda: next(parada),
            _arm_input_grace=lambda: None,
        )

        async def _run_blocking(fn: Any, *args: Any) -> Any:
            executadas_no_pool_compartilhado.append(fn)
            return fn(*args)

        daemon._run_blocking = _run_blocking
        watch = SimpleNamespace(poll=lambda: False)

        asyncio.run(connection.reconnect_loop(daemon, input_watch=watch))
        assert chamadas == [daemon]
        # No executor dedicado do broker (thread própria 'hefesto-broker'),
        # nunca inline no event loop nem no pool compartilhado.
        assert threads_do_rehide and all(
            nome.startswith("hefesto-broker") for nome in threads_do_rehide
        ), f"rehide rodou fora do executor do broker: {threads_do_rehide}"
        assert _spy_rehide not in executadas_no_pool_compartilhado, (
            "rehide não pode ocupar o pool 'hefesto-hid' de read_state"
        )
        # O executor lazy ficou pendurado no daemon (o shutdown o desliga).
        executor = getattr(daemon, "_hidraw_broker_executor", None)
        assert executor is not None
        executor.shutdown(wait=True)


class TestCoopHooks:
    def _manager(self, daemon: _FakeDaemon) -> Any:
        from hefesto_dualsense4unix.daemon.subsystems.coop import CoopManager

        return CoopManager(daemon)

    def _player(
        self, identity: str, *, vpad: _FakeVpad | None = None
    ) -> Any:
        from hefesto_dualsense4unix.daemon.subsystems.coop import _SecondaryPlayer

        reader = SimpleNamespace(
            set_grab=lambda _g: True, stop=lambda: None, grab_state="held"
        )
        return _SecondaryPlayer(
            identity=identity,
            evdev_path="/dev/input/event99",
            reader=reader,
            player_index=2,
            vpad=vpad,
        )

    def test_hide_do_jogador(self, wired: _FakeDaemon) -> None:
        wired.controller.nodes["aabbccddee02"] = "/dev/hidraw7"
        manager = self._manager(wired)
        manager._broker_hide_player(self._player("aabbccddee02", vpad=_FakeVpad()))
        assert wired.broker.calls == [("hide", "/dev/hidraw7")]

    def test_jogador_sem_vpad_nunca_esconde(self, wired: _FakeDaemon) -> None:
        wired.controller.nodes["aabbccddee02"] = "/dev/hidraw7"
        manager = self._manager(wired)
        manager._broker_hide_player(self._player("aabbccddee02", vpad=None))
        assert wired.broker.calls == []

    def test_jogador_com_vpad_morto_nunca_esconde(self, wired: _FakeDaemon) -> None:
        # Achado Onda S #1: `_broker_hide_player` gateia por VIDA do vpad
        # (`vpad_vivo`), não por existência — uhid derrubado por UHID_STOP
        # (`_started=False`) não pode esconder o físico do jogador.
        wired.controller.nodes["aabbccddee02"] = "/dev/hidraw7"
        manager = self._manager(wired)
        manager._broker_hide_player(
            self._player("aabbccddee02", vpad=_FakeVpad(started=False))
        )
        assert wired.broker.calls == []

    def test_nativo_nao_esconde_jogador(self, wired: _FakeDaemon) -> None:
        wired.controller.nodes["aabbccddee02"] = "/dev/hidraw7"
        wired._native = True
        manager = self._manager(wired)
        manager._broker_hide_player(self._player("aabbccddee02", vpad=_FakeVpad()))
        assert wired.broker.calls == []

    def test_externo_e_sem_mac_ficam_expostos(self, wired: _FakeDaemon) -> None:
        manager = self._manager(wired)
        # sem handle no backend (hidraw_path(uniq) → None) e identidade path:*
        manager._broker_hide_player(self._player("aabbccddee99", vpad=_FakeVpad()))
        manager._broker_hide_player(
            self._player("path:/dev/input/event9", vpad=_FakeVpad())
        )
        assert wired.broker.calls == []

    def test_daemon_sem_is_native_mode_nao_explode_nem_esconde(
        self, wired: _FakeDaemon
    ) -> None:
        # Best-effort fail-closed: dúvida (dublê sem o método) ⇒ NÃO esconder.
        wired.controller.nodes["aabbccddee02"] = "/dev/hidraw7"
        manager = self._manager(wired)
        del wired.__class__.is_native_mode
        try:
            manager._broker_hide_player(
                self._player("aabbccddee02", vpad=_FakeVpad())
            )
        finally:
            _FakeDaemon.is_native_mode = lambda self: self._native  # type: ignore[method-assign]
        assert wired.broker.calls == []

    def test_teardown_restaura_o_jogador(self, wired: _FakeDaemon) -> None:
        wired.controller.nodes["aabbccddee02"] = "/dev/hidraw7"
        manager = self._manager(wired)
        player = self._player("aabbccddee02", vpad=_FakeVpad())
        manager._players[player.identity] = player
        manager._teardown_player(player.identity)
        assert ("restore", "/dev/hidraw7") in wired.broker.calls

    def test_teardown_de_externo_nao_fala_com_broker(self, wired: _FakeDaemon) -> None:
        manager = self._manager(wired)
        player = self._player("path:/dev/input/event9", vpad=_FakeVpad())
        manager._players[player.identity] = player
        manager._teardown_player(player.identity)
        assert not any(c[0] == "restore" for c in wired.broker.calls)

    def test_promote_esconde_o_fisico_do_jogador(
        self, wired: _FakeDaemon, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        wired.controller.nodes["aabbccddee02"] = "/dev/hidraw7"
        manager = self._manager(wired)
        player = self._player("aabbccddee02")
        manager._players[player.identity] = player
        manager._promote_player(player)
        assert player.vpad is not None
        assert ("hide", "/dev/hidraw7") in wired.broker.calls

    def test_promote_falho_nao_esconde(
        self, wired: _FakeDaemon, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # vpad não nasceu ⇒ jogador derrubado SEM hide (zero controles jamais).
        monkeypatch.setattr(vp, "make_virtual_pad", lambda *_a, **_k: None)
        wired.controller.nodes["aabbccddee02"] = "/dev/hidraw7"
        manager = self._manager(wired)
        player = self._player("aabbccddee02")
        manager._players[player.identity] = player
        manager._promote_player(player)
        assert not any(c[0] == "hide" for c in wired.broker.calls)


class _BrokerBloqueante:
    """Dublê de broker LENTO: cada operação trava num Event até o teste soltar.

    Achados Onda S #5/#6/#10: o cliente real bloqueia até ~4 s por operação
    (timeout 2 s vezes 2 tentativas). Este dublê torna o bloqueio observável e
    determinístico — se a operação rodar INLINE na thread do event loop, o
    chamador só retorna depois do `wait` (e o teste flagra pela lista de
    chamadas ainda vazia + pela thread registrada).
    """

    def __init__(self) -> None:
        self.calls: list[tuple[Any, ...]] = []
        self.liberar = threading.Event()
        self.threads: list[int] = []

    def _travar(self, call: tuple[Any, ...]) -> bool:
        self.threads.append(threading.get_ident())
        self.liberar.wait(timeout=5.0)
        self.calls.append(call)
        return True

    def hide(self, node: str) -> bool:
        return self._travar(("hide", node))

    def restore(self, node: str) -> bool:
        return self._travar(("restore", node))

    def restore_all(self) -> bool:
        return self._travar(("restore_all",))

    def close(self) -> None:
        self.calls.append(("close",))


def _drena_executor_do_broker(daemon: _FakeDaemon) -> None:
    executor = getattr(daemon, "_hidraw_broker_executor", None)
    assert executor is not None, "a chamada deveria ter criado o executor dedicado"
    executor.shutdown(wait=True)


class TestBrokerForaDoEventLoop:
    """Achados Onda S #5/#6/#10 — I/O do broker NUNCA na thread do event loop.

    Precedente HANG-01 ('só AGENDA a task') + §9 do desenho ('chamadas via
    executor; hide/restore best-effort jamais bloqueiam start/stop'). Cada
    teste roda o hook DENTRO de um event loop com o broker travado: com a
    correção, o hook retorna na hora (a operação fica agendada no executor
    dedicado); sem ela, o `asyncio.run` só volta após o wait de 5 s do dublê
    e a lista de chamadas chega preenchida — o assert de lista vazia flagra.
    """

    def _com_broker_travado(self, wired: _FakeDaemon) -> _BrokerBloqueante:
        broker = _BrokerBloqueante()
        wired._hidraw_broker_client = broker
        return broker

    def test_sync_grab_hide_agenda_e_nao_bloqueia(self, wired: _FakeDaemon) -> None:
        broker = self._com_broker_travado(wired)
        loop_thread: list[int] = []

        async def _main() -> None:
            loop_thread.append(threading.get_ident())
            gp._broker_sync_grab(wired, True)

        asyncio.run(_main())
        assert broker.calls == []  # inline teria completado o hide aqui
        broker.liberar.set()
        _drena_executor_do_broker(wired)
        assert broker.calls == [("hide", "/dev/hidraw3")]
        # E rodou FORA da thread do event loop.
        assert broker.threads and broker.threads[0] != loop_thread[0]

    def test_sync_grab_restore_all_agenda_e_nao_bloqueia(
        self, wired: _FakeDaemon
    ) -> None:
        broker = self._com_broker_travado(wired)

        async def _main() -> None:
            gp._broker_sync_grab(wired, False)

        asyncio.run(_main())
        assert broker.calls == []
        broker.liberar.set()
        _drena_executor_do_broker(wired)
        assert broker.calls == [("restore_all",)]

    def test_cadeia_do_setter_ipc_nao_bloqueia_o_loop(self, wired: _FakeDaemon) -> None:
        # Achado #6: `gamepad.emulation.set` → `set_gamepad_emulation` →
        # `start_gamepad_emulation` → `_set_controller_grab` → broker. O
        # handler roda como coroutine no ÚNICO event loop do daemon — a
        # cadeia inteira precisa voltar sem esperar o broker.
        broker = self._com_broker_travado(wired)
        resultado: list[bool] = []

        async def _main() -> None:
            resultado.append(gp.start_gamepad_emulation(wired, flavor="dualsense"))

        asyncio.run(_main())
        assert resultado == [True]
        assert broker.calls == []  # broker travado não segurou o start
        broker.liberar.set()
        _drena_executor_do_broker(wired)
        assert ("hide", "/dev/hidraw3") in broker.calls

    def test_hide_de_jogador_coop_agenda_e_nao_bloqueia(
        self, wired: _FakeDaemon
    ) -> None:
        # Achado #5: `coop.sync()` roda inline no `_poll_loop`; o hide da
        # promoção de um jogador não pode congelar todos os outros.
        from hefesto_dualsense4unix.daemon.subsystems.coop import (
            CoopManager,
            _SecondaryPlayer,
        )

        broker = self._com_broker_travado(wired)
        wired.controller.nodes["aabbccddee02"] = "/dev/hidraw7"
        manager = CoopManager(wired)
        reader = SimpleNamespace(
            set_grab=lambda _g: True, stop=lambda: None, grab_state="held"
        )
        player = _SecondaryPlayer(
            identity="aabbccddee02",
            evdev_path="/dev/input/event99",
            reader=reader,
            player_index=2,
            vpad=_FakeVpad(),
        )

        async def _main() -> None:
            manager._broker_hide_player(player)

        asyncio.run(_main())
        assert broker.calls == []
        broker.liberar.set()
        _drena_executor_do_broker(wired)
        assert broker.calls == [("hide", "/dev/hidraw7")]

    def test_teardown_de_jogador_agenda_o_restore(self, wired: _FakeDaemon) -> None:
        from hefesto_dualsense4unix.daemon.subsystems.coop import (
            CoopManager,
            _SecondaryPlayer,
        )

        broker = self._com_broker_travado(wired)
        wired.controller.nodes["aabbccddee02"] = "/dev/hidraw7"
        manager = CoopManager(wired)
        reader = SimpleNamespace(
            set_grab=lambda _g: True, stop=lambda: None, grab_state="held"
        )
        player = _SecondaryPlayer(
            identity="aabbccddee02",
            evdev_path="/dev/input/event99",
            reader=reader,
            player_index=2,
            vpad=_FakeVpad(),
        )
        manager._players[player.identity] = player

        async def _main() -> None:
            manager._teardown_player(player.identity)

        asyncio.run(_main())
        assert not any(c[0] == "restore" for c in broker.calls)
        broker.liberar.set()
        _drena_executor_do_broker(wired)
        assert ("restore", "/dev/hidraw7") in broker.calls

    def test_fora_do_event_loop_segue_inline(self, wired: _FakeDaemon) -> None:
        # Contrato do rehide (§6.5): via `_run_blocking` a chamada já está
        # fora do loop — roda INLINE e síncrona (a ordem hide/restore que os
        # chamadores esperam), sem executor no meio.
        broker = self._com_broker_travado(wired)
        broker.liberar.set()  # inline: sem outra thread para soltar depois
        gp._broker_sync_grab(wired, True)
        assert broker.calls == [("hide", "/dev/hidraw3")]
        assert broker.threads == [threading.get_ident()]


class TestShutdownFechaLease:
    def test_shutdown_close(self, wired: _FakeDaemon) -> None:
        from hefesto_dualsense4unix.daemon import connection

        daemon: Any = wired
        # Superfície mínima que o shutdown() toca.
        daemon._plugins_subsystem = None
        daemon._hotkey_manager = None
        daemon._audio = None
        daemon._keyboard_device = None
        daemon._ipc_server = None
        daemon._udp_server = None
        daemon._autoswitch = None
        daemon._last_state = None
        daemon._tasks = []
        daemon._reconnect_task = None
        daemon._executor = None
        daemon._external_executor = None
        daemon.controller.disconnect = lambda: None

        async def _run_blocking(fn: Any, *args: Any) -> Any:
            return fn(*args)

        daemon._run_blocking = _run_blocking
        broker = daemon.broker
        asyncio.run(connection.shutdown(daemon))
        assert ("close",) in broker.calls
        assert daemon._hidraw_broker_client is None

    def test_shutdown_sem_lease_nao_explode(self, wired: _FakeDaemon) -> None:
        from hefesto_dualsense4unix.daemon import connection

        daemon: Any = wired
        daemon._hidraw_broker_client = None
        daemon._plugins_subsystem = None
        daemon._hotkey_manager = None
        daemon._audio = None
        daemon._keyboard_device = None
        daemon._ipc_server = None
        daemon._udp_server = None
        daemon._autoswitch = None
        daemon._last_state = None
        daemon._tasks = []
        daemon._reconnect_task = None
        daemon._executor = None
        daemon._external_executor = None
        daemon.controller.disconnect = lambda: None

        async def _run_blocking(fn: Any, *args: Any) -> Any:
            return fn(*args)

        daemon._run_blocking = _run_blocking
        asyncio.run(connection.shutdown(daemon))
        assert daemon._hidraw_broker_client is None


class TestBrokerClientForRespeitaDuble:
    def test_hooks_usam_o_duble_injetado(self, wired: _FakeDaemon) -> None:
        # O contrato que TODOS os testes acima assumem: `broker_client_for`
        # devolve o dublê de `_hidraw_broker_client` sem criar cliente real.
        from hefesto_dualsense4unix.integrations.hidraw_broker_client import (
            broker_client_for,
        )

        assert broker_client_for(wired) is wired.broker

    def test_start_stop_nao_criam_cliente_real_com_duble(
        self, wired: _FakeDaemon
    ) -> None:
        gp.start_gamepad_emulation(wired, flavor="dualsense")
        gp.stop_gamepad_emulation(wired)
        assert isinstance(wired._hidraw_broker_client, FakeBroker)


# `_teardown_player` best-effort de ponta a ponta: reader/vpad que explodem
# não impedem o restore do broker (nó nunca fica 0600 órfão por causa disso).
def test_teardown_explosivo_ainda_restaura(wired: _FakeDaemon) -> None:
    from hefesto_dualsense4unix.daemon.subsystems.coop import _SecondaryPlayer

    wired.controller.nodes["aabbccddee02"] = "/dev/hidraw7"
    from hefesto_dualsense4unix.daemon.subsystems.coop import CoopManager

    manager = CoopManager(wired)

    def _boom(*_a: Any, **_k: Any) -> None:
        raise RuntimeError("boom")

    reader = SimpleNamespace(set_grab=_boom, stop=_boom, grab_state="held")
    vpad = _FakeVpad()
    vpad.stop = _boom  # type: ignore[method-assign]
    player = _SecondaryPlayer(
        identity="aabbccddee02",
        evdev_path="/dev/input/event99",
        reader=reader,
        player_index=2,
        vpad=vpad,
    )
    manager._players[player.identity] = player
    with contextlib.suppress(Exception):
        manager._teardown_player(player.identity)
    assert ("restore", "/dev/hidraw7") in wired.broker.calls
