"""JOGO-01 — um controle físico produz exatamente UM dispositivo de jogo.

Medido ao vivo em 25/07 com o Mullet Mad Jack (`steam_app_2111190`, o único
appid da allowlist do Steam Input desta máquina) e UM DualSense no cabo:

    /dev/input/js0  ->  Hefesto Virtual DualSense P1   (o nosso gamepad virtual)
    /dev/input/js2  ->  DualSense Wireless Controller  (o controle físico dela)
    /dev/input/js4  ->  Microsoft X-Box 360 pad 0      (Steam Input)
    /dev/input/js5  ->  Microsoft X-Box 360 pad 1      (Steam Input)

O jogo dava jogador 1 ao primeiro que enumerou e jogador 2 ao seguinte, e o
relato dela descreve isso por fora: "ele muda a cor e vai pro player 2 e não
funciona". A causa não era a allowlist estar errada — era ela estar pela
metade: o ramo do `launch_env` omitia `SDL_GAMECONTROLLER_IGNORE_DEVICES` e
`PROTON_DISABLE_HIDRAW` (rótulo literal no código: "allowlist Steam Input (sem
dedup)") e o gamepad virtual CONTINUAVA DE PÉ. Cada metade estava certa
isoladamente; juntas produziam o duplicado.

Estas travas cobrem o invariante que passou a valer: a allowlist muda QUAL
dispositivo o jogo vê, nunca QUANTOS. E cobrem também o beco sem saída que a
cura poderia criar — o tick que traz o vpad de volta é o mesmo que a suspensão
apaga (`lifecycle._poll_loop` só despacha o gamepad com `_gamepad_device is not
None`), então sem a task-vigia o vpad não voltaria nem depois de fechar o jogo.
"""

from __future__ import annotations

import asyncio
import contextlib
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

import hefesto_dualsense4unix.daemon.subsystems.gamepad as gp
from hefesto_dualsense4unix.daemon import launch_env as le

MMJ = 2111190
_IGNORE = "SDL_GAMECONTROLLER_IGNORE_DEVICES"


class _VpadFalso:
    """O mínimo que `start/stop_gamepad_emulation` toca num vpad."""

    def __init__(self, flavor: str = "dualsense", backend: str = "uhid") -> None:
        self.flavor = flavor
        self.backend = backend
        self._started = True
        self.parado = False

    def stop(self) -> None:
        self.parado = True
        self._started = False


class _CoopFalso:
    def __init__(self, jogadores: int = 0) -> None:
        self._players: dict[str, Any] = {
            f"AA:BB:CC:00:00:0{i}": SimpleNamespace(
                vpad=_VpadFalso(), player_index=i + 2
            )
            for i in range(jogadores)
        }
        self.desligado = 0
        self.syncs: list[bool] = []

    def disable(self) -> None:
        self.desligado += 1
        self._players.clear()

    def sync(self, *, force: bool = False) -> None:
        self.syncs.append(force)


class _StoreFalso:
    def __init__(self) -> None:
        self.contadores: list[str] = []
        self.window_detect_current_class: str | None = None

    def bump(self, chave: str) -> None:
        self.contadores.append(chave)


class _DaemonFalso:
    """Daemon dublado que observa grab, broker, co-op e vpad."""

    def __init__(self, *, jogadores: int = 0, nativo: bool = False) -> None:
        self.config = SimpleNamespace(
            gamepad_emulation_enabled=True,
            gamepad_flavor="dualsense",
            rumble_active=None,
        )
        self._gamepad_device: Any = _VpadFalso()
        self._coop_manager = _CoopFalso(jogadores)
        self._motion_reader: Any = None
        self._mouse_device: Any = None
        self._tasks: list[Any] = []
        self._nativo = nativo
        self.parando = False
        self.grabs: list[bool] = []
        self.restores = 0
        self.hides: list[str] = []
        self.store = _StoreFalso()
        pai = self

        class _Evdev:
            grab_state = None

            def set_grab(self, grab: bool) -> bool:
                pai.grabs.append(grab)
                return True

        self.controller = SimpleNamespace(
            _evdev=_Evdev(),
            hidraw_path=lambda *a: "/dev/hidraw0",
            set_rumble=lambda **k: None,
            primary_uniq="AA:BB:CC:00:00:FF",
        )

    def is_native_mode(self) -> bool:
        return self._nativo

    def _is_stopping(self) -> bool:
        return self.parando


@pytest.fixture()
def _broker_falso(monkeypatch: pytest.MonkeyPatch) -> None:
    """Cliente do broker dublado — nenhum socket real no teste."""
    import hefesto_dualsense4unix.integrations.hidraw_broker_client as bc

    def _client_for(daemon: Any) -> Any:
        class _C:
            def hide(self, node: str) -> None:
                daemon.hides.append(node)

            def restore_all(self) -> None:
                daemon.restores += 1

        return _C()

    monkeypatch.setattr(bc, "broker_client_for", _client_for)
    monkeypatch.setattr(bc, "broker_call_nonblocking", lambda daemon, fn: fn())


@pytest.fixture()
def _sem_disco(monkeypatch: pytest.MonkeyPatch) -> list[Any]:
    """Isola o ciclo do vpad de disco, kernel e threads.

    Devolve a lista de chamadas a `save_gamepad_emulation` — a PREFERÊNCIA dela
    em disco é a coisa que a suspensão não pode encostar, e a única forma de
    provar isso é observar quem escreve.
    """
    import hefesto_dualsense4unix.integrations.virtual_pad as vp
    import hefesto_dualsense4unix.utils.session as session

    salvos: list[Any] = []
    monkeypatch.setattr(gp, "_materialize_launch_env", lambda daemon: None)
    monkeypatch.setattr(gp, "start_motion_reader", lambda daemon, device: None)
    monkeypatch.setattr(
        vp, "make_virtual_pad", lambda key, **kwargs: _VpadFalso(flavor=key)
    )
    monkeypatch.setattr(
        session,
        "save_gamepad_emulation",
        lambda *a, **k: salvos.append((a, k)),
    )
    return salvos


async def _encerrar_vigia(daemon: Any) -> Any:
    """Cancela a task-vigia (se houver) e devolve a task para inspeção."""
    vigia = getattr(daemon, "_steam_input_vigia", None)
    if vigia is not None:
        vigia.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await vigia
    return vigia


class TestSuspensaoDoVpad:
    async def test_entrar_na_excecao_derruba_o_vpad_do_p1_e_o_coop(
        self,
        monkeypatch: pytest.MonkeyPatch,
        _broker_falso: None,
        _sem_disco: list[Any],
    ) -> None:
        """O defeito: com a exceção ativa o jogo via físico E virtual."""
        daemon = _DaemonFalso(jogadores=3)
        vpad = daemon._gamepad_device
        monkeypatch.setattr(le, "steam_input_exception_appid", lambda d, **k: MMJ)

        assert gp.sync_steam_input_exception(daemon) is True
        vigia = await _encerrar_vigia(daemon)

        assert daemon._gamepad_device is None, "o vpad é o duplicado neste jogo"
        assert vpad.parado is True
        assert daemon._coop_manager.desligado == 1, "P2+ também dobravam o input"
        assert gp.steam_input_vpad_suspenso(daemon) is True
        assert daemon.grabs == [False], "o jogo tem de ver o evdev do físico"
        assert vigia is not None, "sem vigia o vpad nunca voltaria"
        assert vigia in daemon._tasks

    async def test_a_preferencia_em_disco_nao_e_tocada(
        self,
        monkeypatch: pytest.MonkeyPatch,
        _broker_falso: None,
        _sem_disco: list[Any],
    ) -> None:
        """R-07/HARM-06: só gesto manual escreve a preferência. A suspensão é
        decisão NOSSA e some com o jogo — em disco a emulação segue ligada, e é
        isso que devolve o vpad se o daemon morrer sujo no meio da partida."""
        daemon = _DaemonFalso()
        monkeypatch.setattr(le, "steam_input_exception_appid", lambda d, **k: MMJ)

        gp.sync_steam_input_exception(daemon)
        await _encerrar_vigia(daemon)

        assert _sem_disco == []
        assert daemon.config.gamepad_emulation_enabled is False, (
            "o False em MEMÓRIA é o que cala os revivedores automáticos"
        )

    def test_sem_event_loop_o_vpad_fica_de_pe_e_a_decisao_e_dita(
        self,
        monkeypatch: pytest.MonkeyPatch,
        _broker_falso: None,
        _sem_disco: list[Any],
    ) -> None:
        """Fail-safe declarado: sem quem devolva o vpad, não se retira o vpad.

        Teste SÍNCRONO de propósito — é justamente o caso "não há event loop
        rodando". Degradar para o duplicado é ruim; deixá-la sem gamepad virtual
        até reiniciar o daemon é pior, e ela não teria como desfazer.
        """
        daemon = _DaemonFalso()
        monkeypatch.setattr(le, "steam_input_exception_appid", lambda d, **k: MMJ)

        assert gp.sync_steam_input_exception(daemon) is True

        assert daemon._gamepad_device is not None
        assert gp.steam_input_vpad_suspenso(daemon) is False
        assert getattr(daemon, "_steam_input_vigia", None) is None

    async def test_sem_vpad_nem_jogadores_nao_arma_nada(
        self,
        monkeypatch: pytest.MonkeyPatch,
        _broker_falso: None,
        _sem_disco: list[Any],
    ) -> None:
        """Emulação já desligada: não há duplicado a remover (nem vigia a criar)."""
        daemon = _DaemonFalso()
        daemon._gamepad_device = None
        daemon.config.gamepad_emulation_enabled = False
        monkeypatch.setattr(le, "steam_input_exception_appid", lambda d, **k: MMJ)

        assert gp.sync_steam_input_exception(daemon) is True

        assert gp.steam_input_vpad_suspenso(daemon) is False
        assert getattr(daemon, "_steam_input_vigia", None) is None


class TestQuemTentaLevantarOVpadDeVolta:
    def test_apply_automatico_e_recusado_durante_a_excecao(
        self, _broker_falso: None, _sem_disco: list[Any]
    ) -> None:
        """O autoswitch reaplica a emulação a cada troca de janela — e a janela
        que ele vê é a do próprio jogo da allowlist ganhando foco."""
        daemon = _DaemonFalso()
        daemon._gamepad_device = None
        daemon._steam_input_excecao = True
        daemon._steam_input_vpad_suspenso = True

        assert gp.start_gamepad_emulation(daemon, "dualsense", origin="profile") is False

        assert daemon._gamepad_device is None
        assert gp.steam_input_vpad_suspenso(daemon) is True

    def test_gesto_manual_vence_e_encerra_a_suspensao(
        self, _broker_falso: None, _sem_disco: list[Any]
    ) -> None:
        """A última palavra é dela. Religar na mão devolve o vpad (com o preço
        do duplicado neste jogo) e a suspensão morre ali — a saída da exceção
        não pode tentar devolver um vpad que já está de pé."""
        daemon = _DaemonFalso()
        daemon._gamepad_device = None
        daemon._steam_input_excecao = True
        daemon._steam_input_vpad_suspenso = True

        assert gp.start_gamepad_emulation(daemon, "dualsense", origin="manual") is True

        assert daemon._gamepad_device is not None
        assert gp.steam_input_vpad_suspenso(daemon) is False

    def test_revive_pos_falha_total_nao_ressuscita_durante_a_excecao(
        self, _broker_falso: None, _sem_disco: list[Any]
    ) -> None:
        """VPAD-09 dispara em borda de CONEXÃO — a mais frequente desta máquina
        (BT reconectando no meio da partida)."""
        daemon = _DaemonFalso()
        daemon._gamepad_device = None
        daemon._steam_input_excecao = True

        assert gp.upgrade_primary_vpad_to_uhid(daemon) is False
        assert daemon._gamepad_device is None


class TestDevolucaoDoVpad:
    @staticmethod
    def _suspenso(flavor: str = "dualsense") -> _DaemonFalso:
        daemon = _DaemonFalso()
        daemon._gamepad_device = None
        daemon.config.gamepad_emulation_enabled = False
        daemon._steam_input_excecao = True
        daemon._steam_input_vpad_suspenso = True
        daemon._steam_input_flavor_suspenso = flavor
        return daemon

    def test_sair_da_excecao_devolve_o_vpad_com_a_mascara_de_antes(
        self,
        monkeypatch: pytest.MonkeyPatch,
        _broker_falso: None,
        _sem_disco: list[Any],
    ) -> None:
        daemon = self._suspenso(flavor="xbox")
        monkeypatch.setattr(le, "steam_input_exception_appid", lambda d, **k: None)

        assert gp.sync_steam_input_exception(daemon) is False

        assert daemon._gamepad_device is not None
        assert daemon._gamepad_device.flavor == "xbox"
        assert daemon.config.gamepad_emulation_enabled is True
        assert gp.steam_input_vpad_suspenso(daemon) is False
        assert daemon._coop_manager.syncs == [True], "P2+ voltam junto com o P1"
        assert _sem_disco == [], "a volta também não escreve preferência nenhuma"
        assert daemon.grabs == [True] and daemon.hides == ["/dev/hidraw0"]

    def test_sem_mascara_gravada_a_devolucao_nao_inventa_um_vpad(
        self, _broker_falso: None, _sem_disco: list[Any]
    ) -> None:
        """Máscara `None` na suspensão = não havia vpad do P1 para derrubar.
        Criar um agora seria dar a ela um device que ela não tinha."""
        daemon = self._suspenso()
        daemon._steam_input_flavor_suspenso = None

        assert gp.resume_vpads_after_steam_input(daemon) is True

        assert daemon._gamepad_device is None
        assert gp.steam_input_vpad_suspenso(daemon) is False

    def test_modo_nativo_no_meio_da_sessao_vence_a_devolucao(
        self,
        monkeypatch: pytest.MonkeyPatch,
        _broker_falso: None,
        _sem_disco: list[Any],
    ) -> None:
        """No Modo Nativo o físico é o dispositivo por escolha dela: ressuscitar
        o vpad recriaria o duplicado pelo outro lado."""
        daemon = self._suspenso()
        daemon._nativo = True
        monkeypatch.setattr(le, "steam_input_exception_appid", lambda d, **k: None)

        assert gp.sync_steam_input_exception(daemon) is False

        assert daemon._gamepad_device is None
        assert gp.steam_input_vpad_suspenso(daemon) is False, (
            "estado pendurado voltaria a mentir na próxima borda"
        )


class TestVigiaDaExcecao:
    async def test_vigia_reconcilia_ate_a_excecao_cair_e_morre(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """É ela que substitui o tick do `dispatch_gamepad` enquanto não há vpad."""
        daemon = _DaemonFalso()
        daemon._steam_input_excecao = True
        chamadas: list[int] = []

        def _reconciliar(d: Any) -> None:
            chamadas.append(1)
            if len(chamadas) == 2:
                d._steam_input_excecao = False

        monkeypatch.setattr(gp, "STEAM_INPUT_VIGIA_INTERVAL_SEC", 0.001)
        monkeypatch.setattr(gp, "_reconciliar_launch", _reconciliar)

        await gp._vigia_da_excecao_steam_input(daemon)

        assert chamadas == [1, 1]
        assert daemon._steam_input_vigia is None, "a vigia não pode vazar"

    async def test_vigia_nao_reconcilia_com_o_daemon_parando(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        daemon = _DaemonFalso()
        daemon._steam_input_excecao = True
        daemon.parando = True
        chamadas: list[int] = []
        monkeypatch.setattr(gp, "STEAM_INPUT_VIGIA_INTERVAL_SEC", 0.001)
        monkeypatch.setattr(gp, "_reconciliar_launch", lambda d: chamadas.append(1))

        await gp._vigia_da_excecao_steam_input(daemon)

        assert chamadas == []


class TestEnvDaAllowlist:
    def test_estado_declara_o_fisico_como_unico_dispositivo(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """O rótulo "sem dedup" descrevia o defeito com precisão; o arquivo é a
        primeira coisa que se lê ao diagnosticar "o jogo vê quatro controles"."""
        monkeypatch.setattr(le, "launch_env_dir", lambda ensure=False: tmp_path)
        monkeypatch.setattr(le, "_steam_profiles", lambda daemon: [])
        monkeypatch.setattr(le, "steam_input_appids", lambda path=None: {MMJ})
        daemon = _DaemonFalso()

        le.materialize_launch_env(daemon)

        texto = (tmp_path / f"steam_app_{MMJ}.env").read_text(encoding="utf-8")
        assert le.ESTADO_ALLOWLIST_STEAM_INPUT in texto
        assert "sem dedup" not in texto
        assert _IGNORE not in texto, "esconder o físico agora seria ZERO controles"
