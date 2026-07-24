"""R-22 (auditoria 23/07): a calibração 0x05 sai da thread do event loop.

O bug: `coop._promote_player` lia o feature 0x05 do controle DENTRO do poll
loop. Essa leitura abre o socket do broker (2s de timeout por tentativa) e faz
`HIDIOCGFEATURE` no hidraw (BT ocioso segura até o timeout de 5s do hidp antes
do EIO). Enquanto durava, o loop não despachava `forward_all` nem o IPC — o
input dos QUATRO jogadores e a GUI congelavam por segundos, sem log nenhum
("bug não notado" da queixa 5 da mantenedora).

O que estes testes provam, sem hardware:

- promover um jogador NA THREAD DO EVENT LOOP não chama `read_calibration` ali
  (roda no executor dedicado do broker) e retorna em milissegundos mesmo com a
  leitura demorando ~1s;
- a promoção ADIA (jogador segue sem vpad, como no grab pendente) e o tick
  seguinte cria o vpad com a calibração CERTA — o GYRO-01 não é sacrificado
  pelo desbloqueio do loop;
- o cache é por MAC e imutável: a segunda promoção do mesmo controle não
  repaga a leitura;
- prazo estourado (rádio mudo) faz o jogador NASCER com o 0x05 canônico —
  ninguém fica sem controle esperando I/O;
- fora do event loop (testes/`_run_blocking`/shutdown) o comportamento
  síncrono de antes é preservado.
"""
from __future__ import annotations

import asyncio
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
from typing import Any

import pytest

from hefesto_dualsense4unix.core import physical_report_reader as prr
from hefesto_dualsense4unix.daemon.lifecycle import DaemonConfig
from hefesto_dualsense4unix.daemon.subsystems import coop as coop_mod
from hefesto_dualsense4unix.integrations import virtual_pad as vp

_CALIB = bytes([0x05]) + bytes([0xAB]) * 40
_MAC = "aabbccddee02"


class _FakeVpad:
    def __init__(self) -> None:
        self.flavor = "dualsense"
        self.backend = "uhid"
        self._started = True

    def stop(self) -> None:
        self._started = False


class _FakeReaderEvdev:
    grab_state = "held"

    def set_grab(self, _g: bool) -> bool:
        return True

    def stop(self) -> None: ...


class _FakeController:
    """Backend cuja leitura de calibração é LENTA e anota a thread que a paga."""

    def __init__(self, atraso: float = 0.0, resultado: bytes | None = _CALIB) -> None:
        self._atraso = atraso
        self._resultado = resultado
        self.pedidos = 0
        self.threads: list[str] = []
        self.primary_uniq = "aabbccddee01"
        self._evdev = SimpleNamespace(_device_path="/dev/input/event1")

    def hidraw_path(self, uniq: str | None = None) -> str | None:
        return "/dev/hidraw9"

    def read_calibration(self, uniq: str | None = None) -> bytes | None:
        self.pedidos += 1
        self.threads.append(threading.current_thread().name)
        if self._atraso:
            time.sleep(self._atraso)
        return self._resultado


class _FakeDaemon:
    def __init__(self, controller: _FakeController) -> None:
        self.controller = controller
        self.config = DaemonConfig()
        self._gamepad_device = object()

    def is_native_mode(self) -> bool:
        return False


@pytest.fixture()
def cenario(monkeypatch: pytest.MonkeyPatch) -> Any:
    """CoopManager isolado + captura dos kwargs entregues à factory do vpad."""
    monkeypatch.setattr(prr, "PhysicalReportReader", lambda **_k: None)
    monkeypatch.setattr(
        coop_mod.CoopManager, "_materialize_launch_env", lambda self: None
    )
    monkeypatch.setattr(
        coop_mod.CoopManager, "_broker_hide_player", lambda self, player: None
    )
    monkeypatch.setattr(
        coop_mod.CoopManager, "_start_player_motion_reader", lambda self, player: None
    )
    capturas: list[dict[str, Any]] = []

    def _fake_make(flavor: Any, **kwargs: Any) -> _FakeVpad:
        capturas.append(kwargs)
        return _FakeVpad()

    monkeypatch.setattr(vp, "make_virtual_pad", _fake_make)

    def _montar(controller: _FakeController) -> Any:
        daemon = _FakeDaemon(controller)
        # Executor do broker explícito: o mesmo que `broker_executor_for`
        # encontraria, mas com desligamento determinístico no fim do teste.
        daemon._hidraw_broker_executor = ThreadPoolExecutor(  # type: ignore[attr-defined]
            max_workers=1, thread_name_prefix="teste-broker"
        )
        manager = coop_mod.CoopManager(daemon)
        player = coop_mod._SecondaryPlayer(
            identity=_MAC,
            evdev_path="/dev/input/event99",
            reader=_FakeReaderEvdev(),
            player_index=2,
        )
        manager._players[_MAC] = player
        return SimpleNamespace(
            daemon=daemon, manager=manager, player=player, capturas=capturas
        )

    criados: list[Any] = []

    def _factory(controller: _FakeController) -> Any:
        ctx = _montar(controller)
        criados.append(ctx)
        return ctx

    yield _factory
    for ctx in criados:
        ctx.daemon._hidraw_broker_executor.shutdown(wait=True)


def _drenar(ctx: Any) -> None:
    """Espera o executor do broker terminar o que já foi submetido."""
    ctx.daemon._hidraw_broker_executor.submit(lambda: None).result(timeout=10)


class TestCalibracaoForaDoLoop:
    def test_promocao_no_event_loop_nao_paga_a_leitura_ali(
        self, cenario: Any
    ) -> None:
        """A leitura NÃO roda na thread do loop, e a promoção volta na hora.

        Este é o teste que pega a regressão do R-22: com a leitura inline (o
        código de antes) a chamada demoraria ~1s NA thread do event loop e o
        nome da thread anotado seria o da própria thread do loop.
        """
        ctx = cenario(_FakeController(atraso=1.0))

        async def _no_loop() -> tuple[float, str]:
            t0 = time.monotonic()
            ctx.manager._promote_player(ctx.player)
            return time.monotonic() - t0, threading.current_thread().name

        gasto, thread_do_loop = asyncio.run(_no_loop())

        # 1) O loop não ficou preso pela leitura lenta.
        assert gasto < 0.3, f"promoção bloqueou o event loop por {gasto:.2f}s"
        # 2) A promoção ADIOU: sem vpad, sem factory chamada.
        assert ctx.player.vpad is None
        assert ctx.capturas == []
        # 3) A leitura foi paga por OUTRA thread (o executor do broker).
        _drenar(ctx)
        assert ctx.daemon.controller.pedidos == 1
        assert ctx.daemon.controller.threads[0] != thread_do_loop
        assert ctx.daemon.controller.threads[0].startswith("teste-broker")

    def test_tick_seguinte_promove_com_a_calibracao_certa(
        self, cenario: Any
    ) -> None:
        """Adiar não sacrifica o GYRO-01: o vpad nasce com o 0x05 da unidade.

        Atraso pequeno de propósito: sem ele o executor pode terminar ANTES de
        `_calibration_pronta` reconsultar o cache (caminho legítimo — HIT já no
        primeiro tick), e o teste não exercitaria o adiamento.
        """
        ctx = cenario(_FakeController(atraso=0.05))

        async def _dois_ticks() -> None:
            ctx.manager._promote_player(ctx.player)  # miss: agenda e adia
            assert ctx.player.vpad is None
            _drenar(ctx)
            ctx.manager._promote_pending()  # tick seguinte: cache quente

        asyncio.run(_dois_ticks())
        assert ctx.player.vpad is not None
        assert ctx.capturas[0]["calibration_0x05"] == _CALIB

    def test_cache_por_mac_nao_repaga_a_leitura(self, cenario: Any) -> None:
        """0x05 é imutável por unidade: uma leitura por MAC, e só."""
        ctx = cenario(_FakeController())

        async def _promove_duas_vezes() -> None:
            ctx.manager._promote_player(ctx.player)
            _drenar(ctx)
            ctx.manager._promote_pending()
            # Respawn do MESMO controle (node novo / troca de máscara).
            ctx.manager._teardown_player(_MAC)
            novo = coop_mod._SecondaryPlayer(
                identity=_MAC,
                evdev_path="/dev/input/event100",
                reader=_FakeReaderEvdev(),
                player_index=2,
            )
            ctx.manager._players[_MAC] = novo
            ctx.manager._promote_player(novo)
            assert novo.vpad is not None  # HIT: nem adiou

        asyncio.run(_promove_duas_vezes())
        assert ctx.daemon.controller.pedidos == 1
        assert ctx.capturas[1]["calibration_0x05"] == _CALIB

    def test_prazo_estourado_promove_com_canonico(
        self, cenario: Any, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Rádio mudo não pode deixar um jogador sem controle para sempre."""
        monkeypatch.setattr(coop_mod, "_CALIB_PRAZO_S", 0.0)
        ctx = cenario(_FakeController(atraso=0.5))

        async def _dois_ticks() -> None:
            ctx.manager._promote_player(ctx.player)  # adia (prazo já vencido…)
            assert ctx.player.vpad is None
            ctx.manager._promote_pending()  # …e o tick seguinte desiste

        asyncio.run(_dois_ticks())
        assert ctx.player.vpad is not None
        assert ctx.capturas[0]["calibration_0x05"] is None

    def test_leitura_sem_bytes_nao_adia_de_novo(self, cenario: Any) -> None:
        """Resolvido-sem-bytes é HIT negativo: promove canônico, sem repetir I/O."""
        ctx = cenario(_FakeController(resultado=None))

        async def _dois_ticks() -> None:
            ctx.manager._promote_player(ctx.player)
            _drenar(ctx)
            ctx.manager._promote_pending()

        asyncio.run(_dois_ticks())
        assert ctx.player.vpad is not None
        assert ctx.capturas[0]["calibration_0x05"] is None
        assert ctx.daemon.controller.pedidos == 1

    def test_teardown_devolve_a_chance_a_quem_falhou(self, cenario: Any) -> None:
        """Falha típica é transitória (BT ocioso): replug tenta de novo."""
        ctx = cenario(_FakeController(resultado=None))

        async def _falha_e_respawna() -> None:
            ctx.manager._promote_player(ctx.player)
            _drenar(ctx)
            assert _MAC in ctx.manager._calib_sem_leitura
            ctx.manager._teardown_player(_MAC)
            assert _MAC not in ctx.manager._calib_sem_leitura

        asyncio.run(_falha_e_respawna())

    def test_identidade_sem_mac_nunca_toca_no_backend(self, cenario: Any) -> None:
        """"path:..." não tem handle por-uniq: canônico direto, zero I/O."""
        ctx = cenario(_FakeController(atraso=0.5))
        externo = coop_mod._SecondaryPlayer(
            identity="path:/dev/input/event9",
            evdev_path="/dev/input/event9",
            reader=_FakeReaderEvdev(),
            player_index=3,
        )
        ctx.manager._players[externo.identity] = externo

        async def _no_loop() -> None:
            ctx.manager._promote_player(externo)

        asyncio.run(_no_loop())
        assert externo.vpad is not None
        assert ctx.capturas[0]["calibration_0x05"] is None
        assert ctx.daemon.controller.pedidos == 0

    def test_fora_do_loop_segue_sincrono(self, cenario: Any) -> None:
        """`_run_blocking`/shutdown/testes: o valor volta na mesma chamada.

        O R-22 é sobre a thread do event loop; fora dela a leitura inline nunca
        foi problema e o contrato antigo (`_read_player_calibration` devolve os
        bytes na hora) continua valendo.
        """
        ctx = cenario(_FakeController())
        assert ctx.manager._read_player_calibration(_MAC) == _CALIB
        ctx.manager._promote_player(ctx.player)
        assert ctx.player.vpad is not None
        assert ctx.capturas[0]["calibration_0x05"] == _CALIB


class TestCacheCompartilhado:
    def test_cache_mora_no_daemon(self, cenario: Any) -> None:
        """O cache é do DAEMON (`_calibration_by_uniq`) — o P1 lê o mesmo."""
        ctx = cenario(_FakeController())
        ctx.manager._promote_player(ctx.player)
        assert coop_mod.calibration_cache(ctx.daemon) == {_MAC: _CALIB}
        assert ctx.daemon._calibration_by_uniq == {_MAC: _CALIB}

    def test_daemon_que_recusa_setattr_nao_bloqueia(self) -> None:
        """Sem lugar para o cache, o contrato preservado é "não bloquear"."""

        class _Imutavel:
            __slots__ = ()

        cache = coop_mod.calibration_cache(_Imutavel())
        assert cache == {}
