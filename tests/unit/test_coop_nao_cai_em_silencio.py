"""CONTAGEM-E-COOP-01 (b) — o co-op não cai mais EM SILÊNCIO.

O defeito medido em 29/07: quando um jogo da allowlist de Steam Input entra em
sessão, `suspend_vpads_for_steam_input` chama `CoopManager.disable()` e dois ou
três jogadores desaparecem. O único vestígio era o campo ``jogadores_coop`` de
um log cujo NOME fala de vpad (`steam_input_vpad_suspenso`) — nada dizia a ela
que o co-op tinha caído, e o ``coop.players`` do `state_full` voltava a 1 no
tique seguinte, indistinguível de "ela desligou o co-op".

Esta frente é SÓ observabilidade. A LÓGICA de quando o co-op cai não mudou uma
linha de propósito: mexer no gatilho encosta na exceção de Steam Input, que é o
caminho do defeito do R1 curado na onda 2. Os testes abaixo travam isso também —
o teardown continua sendo exatamente um `disable()`, na mesma ordem.

Sem GTK neste arquivo por decisão: a aba que vai MOSTRAR o aviso é de outra
frente, e um `exigir_gi_real` aqui afundaria estas checagens no CI headless.
"""
from __future__ import annotations

import asyncio
import contextlib
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
import structlog

from hefesto_dualsense4unix.daemon.ipc_handlers import IpcHandlersMixin
from hefesto_dualsense4unix.daemon.lifecycle import Daemon
from hefesto_dualsense4unix.daemon.subsystems import gamepad as gp
from hefesto_dualsense4unix.testing import FakeController
from hefesto_dualsense4unix.utils import session

#: appid qualquer da allowlist — o número não importa para esta frente.
APPID = 2111190


class _VpadDublado:
    def __init__(self, flavor: str = "dualsense") -> None:
        self.flavor = flavor
        self.parado = False
        self.ff_play_count = 0
        self.ff_last_sent = (0, 0)
        self.backend = "uhid"

    def stop(self) -> None:
        self.parado = True

    close = stop


class _CoopDublado:
    """Só o que a suspensão toca: o dict de secundários e o `disable()`."""

    def __init__(self, secundarios: int = 0, estoura: bool = False) -> None:
        self._players: dict[str, Any] = {
            f"aa:bb:cc:00:00:0{i}": SimpleNamespace(
                vpad=_VpadDublado(), player_index=i + 2
            )
            for i in range(secundarios)
        }
        self.desligados = 0
        self.syncs: list[bool] = []
        self._estoura = estoura

    def disable(self) -> None:
        self.desligados += 1
        if self._estoura:
            # Teardown parcial: derruba UM e estoura. O chamador roda sob
            # `suppress(Exception)`, então o daemon segue de pé com o resto.
            if self._players:
                self._players.pop(next(iter(self._players)))
            raise RuntimeError("uinput sumiu no meio do teardown")
        self._players.clear()

    def sync(self, *, force: bool = False) -> None:
        self.syncs.append(force)

    def player_count(self) -> int:
        return 1 + len(self._players)


class _StoreDublado:
    def __init__(self) -> None:
        self.contadores: list[str] = []
        self.window_detect_current_class: str | None = None

    def bump(self, chave: str) -> None:
        self.contadores.append(chave)


class _DaemonDublado:
    def __init__(self, *, secundarios: int = 0, estoura: bool = False) -> None:
        self.config = SimpleNamespace(
            gamepad_emulation_enabled=True,
            gamepad_flavor="dualsense",
            rumble_active=None,
            coop_enabled=True,
        )
        self._gamepad_device: Any = _VpadDublado()
        self._coop_manager = _CoopDublado(secundarios, estoura)
        self._motion_reader: Any = None
        self._mouse_device: Any = None
        self._tasks: list[Any] = []
        self.parando = False
        self.grabs: list[bool] = []
        self.store = _StoreDublado()
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
            primary_uniq="aa:bb:cc:00:00:ff",
        )

    def is_native_mode(self) -> bool:
        return False

    def _is_stopping(self) -> bool:
        return self.parando


@pytest.fixture()
def sem_disco_nem_broker(monkeypatch: pytest.MonkeyPatch) -> None:
    """Isola o ciclo do vpad de disco, kernel, broker e threads."""
    import hefesto_dualsense4unix.integrations.hidraw_broker_client as bc
    import hefesto_dualsense4unix.integrations.virtual_pad as vp
    import hefesto_dualsense4unix.utils.session as session

    monkeypatch.setattr(bc, "broker_client_for", lambda daemon: SimpleNamespace(
        hide=lambda node: None, restore_all=lambda: None
    ))
    monkeypatch.setattr(bc, "broker_call_nonblocking", lambda daemon, fn: fn())
    monkeypatch.setattr(gp, "_materialize_launch_env", lambda daemon: None)
    monkeypatch.setattr(gp, "start_motion_reader", lambda daemon, device: None)
    monkeypatch.setattr(
        vp, "make_virtual_pad", lambda key, **kwargs: _VpadDublado(flavor=key)
    )
    monkeypatch.setattr(session, "save_gamepad_emulation", lambda *a, **k: None)


async def _encerrar_vigia(daemon: Any) -> None:
    vigia = getattr(daemon, "_steam_input_vigia", None)
    if vigia is not None:
        vigia.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await vigia


class _Handlers(IpcHandlersMixin):
    """Só as três dependências que o `state_full` consome (molde do JOGO-01)."""

    def __init__(self, daemon: Any, store: Any, controller: Any) -> None:
        self.daemon = daemon  # type: ignore[assignment]
        self.store = store
        self.controller = controller


@pytest.fixture()
def config_em_tmp(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """`config_dir` em tmp: o daemon real deste teste NUNCA toca a config dela."""
    monkeypatch.setattr(session, "config_dir", lambda ensure=False: tmp_path)
    return tmp_path


def _daemon_real_com_coop(secundarios: int) -> Any:
    """Daemon de verdade (o `state_full` pede muito mais que um dublê), com o
    `CoopManager` substituído pelo dublê — é o co-op que está sob teste."""
    daemon = Daemon(controller=FakeController(transport="usb"))
    daemon._coop_manager = _CoopDublado(secundarios)  # type: ignore[assignment]
    daemon.config.coop_enabled = True
    return daemon


# ---------------------------------------------------------------------------
# O fato ganha nome no journal
# ---------------------------------------------------------------------------


class TestOJournalDizQueOCoopCaiu:
    async def test_derrubar_tres_jogadores_emite_o_fato_nomeado(
        self, sem_disco_nem_broker: None
    ) -> None:
        """A MORDIDA: sem a cura, nenhum evento com nome de co-op é emitido.

        Com a observabilidade arrancada, o journal só tem
        ``steam_input_vpad_suspenso`` — cujo nome fala de vpad — e o aviso da
        janela nunca nasce.
        """
        daemon = _DaemonDublado(secundarios=3)

        with structlog.testing.capture_logs() as registros:
            assert gp.suspend_vpads_for_steam_input(daemon, appid=APPID) is True
        await _encerrar_vigia(daemon)

        quedas = [
            r
            for r in registros
            if r["event"] == "coop_derrubado_pela_excecao_steam_input"
        ]
        assert len(quedas) == 1, "o co-op caiu e o journal tem de dizer isso"
        assert quedas[0]["secundarios_derrubados"] == 3
        assert quedas[0]["secundarios_restantes"] == 0
        assert quedas[0]["appid"] == APPID
        assert quedas[0]["log_level"] == "warning", (
            "perda de função que ela não pediu não é info"
        )
        # E a LÓGICA da queda segue intacta: um `disable()`, nada mais.
        assert daemon._coop_manager.desligados == 1
        assert daemon._gamepad_device is None
        assert gp.steam_input_vpad_suspenso(daemon) is True
        assert "gamepad.steam_input.coop_derrubado" in daemon.store.contadores

    async def test_sem_coop_de_pe_nao_inventa_aviso(
        self, sem_disco_nem_broker: None
    ) -> None:
        """Cura exagerada reprova: com o co-op desligado, quem cai é só o vpad
        do P1 e não há jogador nenhum a lamentar."""
        daemon = _DaemonDublado(secundarios=0)

        with structlog.testing.capture_logs() as registros:
            assert gp.suspend_vpads_for_steam_input(daemon, appid=APPID) is True
        await _encerrar_vigia(daemon)

        assert not [
            r
            for r in registros
            if r["event"] == "coop_derrubado_pela_excecao_steam_input"
        ]
        assert gp.steam_input_coop_derrubados(daemon) == 0
        assert "gamepad.steam_input.coop_derrubado" not in daemon.store.contadores

    async def test_teardown_parcial_conta_o_que_caiu_de_verdade(
        self, sem_disco_nem_broker: None
    ) -> None:
        """`coop.disable()` roda sob `suppress(Exception)`: se estourar no meio,
        sobra jogador de pé. Declarar "derrubei 3" ali seria a mesma classe de
        mentira do log de ``jogadores_coop=0`` que esta sprint está desfazendo —
        por isso a conta é o RESIDUAL, não o total de antes."""
        daemon = _DaemonDublado(secundarios=3, estoura=True)

        with structlog.testing.capture_logs() as registros:
            assert gp.suspend_vpads_for_steam_input(daemon, appid=APPID) is True
        await _encerrar_vigia(daemon)

        queda = next(
            r
            for r in registros
            if r["event"] == "coop_derrubado_pela_excecao_steam_input"
        )
        assert queda["secundarios_derrubados"] == 1
        assert queda["secundarios_restantes"] == 2
        # NOTA DATADA — 09/08/2026 (AVISO-FALSO-DO-COOP-01): aqui havia
        # `steam_input_coop_derrubados(daemon) == 1`, quando o número da JANELA
        # ainda era o de vpads recolhidos. Era esse número que acendia o aviso
        # vermelho "1 jogador saiu" com os controles dela conectados na tela. O
        # RESIDUAL desta sprint continua exato — no journal, que é onde ele
        # sempre foi o fato de engenharia; a janela passou a falar de CONTROLE
        # e só acende quando um deles sai da mesa de verdade. A mesa fica
        # registrada com a identidade de quem caiu, e é dela que o tique do
        # co-op pergunta (ver `test_aviso_falso_do_coop_01.py`).
        assert gp.steam_input_coop_derrubados(daemon) == 0
        assert gp.coop_sentados_na_suspensao(daemon) == ("aa:bb:cc:00:00:00",)


# ---------------------------------------------------------------------------
# O aviso vive exatamente enquanto a suspensão vive
# ---------------------------------------------------------------------------


class TestOAvisoMorreQuandoOCoopVolta:
    async def test_sair_da_excecao_zera_o_aviso(
        self, sem_disco_nem_broker: None
    ) -> None:
        daemon = _DaemonDublado(secundarios=2)
        assert gp.suspend_vpads_for_steam_input(daemon, appid=APPID) is True
        await _encerrar_vigia(daemon)
        # NOTA DATADA — 09/08/2026 (AVISO-FALSO-DO-COOP-01): a suspensão sozinha
        # já não acende o aviso (recolher vpad não é controle saindo da mesa),
        # então o "aviso aceso" que esta saída tem de apagar é construído aqui,
        # medindo a mesa VAZIA — os dois controles caíram de verdade.
        assert gp.reavaliar_coop_fora_da_mesa(daemon, set()) == 2

        with structlog.testing.capture_logs() as registros:
            assert gp.resume_vpads_after_steam_input(daemon) is True

        assert gp.steam_input_coop_derrubados(daemon) == 0, (
            "aviso pendurado mandaria a janela lamentar um estrago encerrado"
        )
        assert [
            r for r in registros if r["event"] == "steam_input_coop_aviso_encerrado"
        ], "o encerramento também é um fato"
        # A devolução do co-op continua sendo a de sempre (P2+ junto com o P1).
        assert daemon._coop_manager.syncs == [True]

    async def test_religar_a_emulacao_na_mao_tambem_zera_o_aviso(
        self, sem_disco_nem_broker: None
    ) -> None:
        """A SEGUNDA saída da suspensão: ela mesma religa a emulação com o jogo
        aberto (`origin="manual"`). Sem zerar aqui, a janela seguiria avisando."""
        daemon = _DaemonDublado(secundarios=2)
        daemon._steam_input_excecao = True
        assert gp.suspend_vpads_for_steam_input(daemon, appid=APPID) is True
        await _encerrar_vigia(daemon)
        # NOTA DATADA — 09/08/2026: ver a saída irmã acima (AVISO-FALSO-DO-COOP-01).
        assert gp.reavaliar_coop_fora_da_mesa(daemon, set()) == 2

        gp.start_gamepad_emulation(daemon, flavor="dualsense", origin="manual")

        assert gp.steam_input_vpad_suspenso(daemon) is False
        assert gp.steam_input_coop_derrubados(daemon) == 0

    async def test_leitura_blindada_contra_lixo_em_memoria(self) -> None:
        """`state_full` roda a 10 Hz e serializa em JSON: só int de verdade
        passa (a mesma blindagem do `players`)."""
        daemon = _DaemonDublado()
        assert gp.steam_input_coop_derrubados(daemon) == 0  # atributo ausente
        daemon._steam_input_coop_derrubados = True  # bool não é contagem
        assert gp.steam_input_coop_derrubados(daemon) == 0
        daemon._steam_input_coop_derrubados = "dois"
        assert gp.steam_input_coop_derrubados(daemon) == 0


# ---------------------------------------------------------------------------
# A janela consegue avisar: o fato sai no state_full
# ---------------------------------------------------------------------------


class TestOStateFullPublicaAQueda:
    async def test_bloco_coop_declara_a_queda_e_quantos_cairam(
        self, config_em_tmp: Path
    ) -> None:
        """A MORDIDA do contrato: sem estas duas chaves a janela não tem como
        distinguir "ela desligou o co-op" de "o jogo derrubou o co-op"."""
        daemon = _daemon_real_com_coop(2)
        h = _Handlers(daemon, daemon.store, daemon.controller)

        cheio = await h._handle_daemon_state_full({})
        assert cheio["coop"]["derrubado_por_steam_input"] is False
        assert cheio["coop"]["secundarios_derrubados"] == 0

        daemon._steam_input_excecao = True
        daemon._steam_input_coop_derrubados = 2
        cheio = await h._handle_daemon_state_full({})
        assert cheio["coop"]["derrubado_por_steam_input"] is True
        assert cheio["coop"]["secundarios_derrubados"] == 2
        # O par de Steam Input segue publicado ao lado, intacto (JOGO-01).
        assert "excecao_ativa" in cheio["steam_input"]

    async def test_o_bloco_e_serializavel_com_daemon_dublado(
        self, config_em_tmp: Path
    ) -> None:
        """Blindagem de serialização: um mock pendurado no atributo não pode
        derrubar o servidor IPC no `json.dumps`."""
        import json

        daemon = _daemon_real_com_coop(0)
        daemon._steam_input_coop_derrubados = object()
        h = _Handlers(daemon, daemon.store, daemon.controller)

        cheio = await h._handle_daemon_state_full({})
        assert cheio["coop"]["secundarios_derrubados"] == 0
        json.dumps(cheio["coop"])


# ---------------------------------------------------------------------------
# O gatilho NÃO mudou (guarda da onda 2)
# ---------------------------------------------------------------------------


async def test_a_suspensao_segue_derrubando_o_coop_antes_do_p1(
    sem_disco_nem_broker: None,
) -> None:
    """Guarda: esta sprint é observabilidade, não mudança de gatilho.

    A ordem importa e está explicada em `suspend_vpads_for_steam_input` —
    derrubar o P1 primeiro deixaria o jogo enumerar vpads órfãos até o tick
    seguinte do co-op. Se alguém "melhorar" o gatilho, este teste reprova.

    NOTA DATADA — 09/08/2026 (ESCONDER-EM-VEZ-DE-SAIR-01, decisão dela): este
    teste entrava por `sync_steam_input_exception`, porque era a BORDA DA MARCA
    que suspendia. Não é mais — a marca passou a esconder o controle físico e a
    deixar os virtuais de pé, justamente porque o preço medido desta suspensão é
    o jogador 2. A ordem interna da suspensão, que é o que este teste guarda,
    não mudou uma linha; mudou quem a percorre. Entrar por uma porta que hoje
    não leva a lugar nenhum deixaria o teste verde e mudo.
    """
    daemon = _DaemonDublado(secundarios=3)

    assert gp.suspend_vpads_for_steam_input(daemon, appid=APPID) is True
    await _encerrar_vigia(daemon)

    assert daemon._coop_manager.desligados == 1
    assert daemon._coop_manager._players == {}
    assert daemon._gamepad_device is None
    # NOTA DATADA — 09/08/2026 (AVISO-FALSO-DO-COOP-01): aqui havia `== 3`, do
    # tempo em que o número da janela era o de vpads recolhidos. O gatilho —
    # que é o que este teste guarda — não mudou: os três secundários caem, na
    # mesma ordem, antes do P1. O que mudou é quem a JANELA ouve.
    assert gp.steam_input_coop_derrubados(daemon) == 0
    assert len(gp.coop_sentados_na_suspensao(daemon)) == 3
