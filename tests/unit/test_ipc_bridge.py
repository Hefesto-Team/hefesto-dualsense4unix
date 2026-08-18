"""Testes do helper `_safe_call` e wrappers síncronos em ipc_bridge.

Cobre AUDIT-FINDING-IPC-BRIDGE-BARE-EXCEPT-01:

  (a) daemon offline (FileNotFoundError, ConnectionError, IpcError, OSError)
      → wrapper retorna False + log em nível debug;
  (b) daemon online (_run_call retorna valor) → wrapper retorna True;
  (c) exceção inesperada (ValueError, TypeError, RuntimeError) **propaga** —
      bug real não pode ser silenciado;
  (d) wrappers específicos (profile_switch, led_set, rumble_set, apply_draft
      etc.) seguem o mesmo contrato.
"""
from __future__ import annotations

import logging
from unittest.mock import patch

import pytest

from hefesto_dualsense4unix.app import ipc_bridge
from hefesto_dualsense4unix.cli.ipc_client import IpcError

# ---------------------------------------------------------------------------
# _safe_call — contrato central
# ---------------------------------------------------------------------------


class TestSafeCallDaemonOffline:
    """Erros esperados de transporte retornam (False, None) e logam debug."""

    @pytest.mark.parametrize(
        "exc",
        [
            FileNotFoundError("socket ausente"),
            ConnectionRefusedError("daemon recusou conexão"),
            ConnectionResetError("conexão caiu"),
            OSError("erro genérico de socket"),
            IpcError(-32000, "servidor sinalizou erro"),
        ],
    )
    def test_retorna_false_em_erro_de_transporte(self, exc, caplog):
        caplog.set_level(logging.DEBUG, logger="hefesto_dualsense4unix.app.ipc_bridge")

        with patch.object(ipc_bridge, "_run_call", side_effect=exc):
            ok, result = ipc_bridge._safe_call("foo.bar")

        assert ok is False
        assert result is None

    def test_loga_debug_nao_warning(self, caplog):
        caplog.set_level(logging.DEBUG, logger="hefesto_dualsense4unix.app.ipc_bridge")

        with patch.object(
            ipc_bridge,
            "_run_call",
            side_effect=FileNotFoundError("sem socket"),
        ):
            ipc_bridge._safe_call("daemon.status")

        # Falha esperada não deve subir para warning; deve sair em debug.
        warnings = [r for r in caplog.records if r.levelno >= logging.WARNING]
        assert not warnings, f"warnings indevidos: {warnings!r}"


class TestSafeCallDaemonOnline:
    """Resposta do daemon retorna (True, resultado)."""

    def test_retorna_tupla_true_resultado(self):
        with patch.object(
            ipc_bridge,
            "_run_call",
            return_value={"status": "ok", "data": 42},
        ):
            ok, result = ipc_bridge._safe_call("daemon.status")

        assert ok is True
        assert result == {"status": "ok", "data": 42}

    def test_resultado_none_ainda_retorna_true(self):
        """None pode ser resultado legítimo (ex.: rumble.set sem retorno)."""
        with patch.object(ipc_bridge, "_run_call", return_value=None):
            ok, result = ipc_bridge._safe_call("rumble.set")

        assert ok is True
        assert result is None


class TestSafeCallExcecaoInesperadaPropaga:
    """Bugs reais (não transporte) NÃO podem ser silenciados."""

    @pytest.mark.parametrize(
        "exc",
        [
            ValueError("parâmetro fora de faixa"),
            TypeError("tipo errado"),
            RuntimeError("bug interno do bridge"),
            KeyError("chave ausente"),
            AttributeError("atributo inexistente"),
        ],
    )
    def test_propaga_excecoes_fora_do_filtro(self, exc):
        with (
            patch.object(ipc_bridge, "_run_call", side_effect=exc),
            pytest.raises(type(exc)),
        ):
            ipc_bridge._safe_call("foo.bar")


# ---------------------------------------------------------------------------
# Wrappers públicos — bool na superfície, propagação de bug preservada
# ---------------------------------------------------------------------------


class TestWrappersRetornamBool:
    """13 wrappers públicos retornam bool e respeitam o contrato."""

    OFFLINE_EXC = FileNotFoundError("daemon offline")

    def test_profile_switch_daemon_offline_false(self):
        with patch.object(ipc_bridge, "_run_call", side_effect=self.OFFLINE_EXC):
            assert ipc_bridge.profile_switch("foo") is False

    def test_profile_switch_online_true(self):
        with patch.object(ipc_bridge, "_run_call", return_value={"ok": True}):
            assert ipc_bridge.profile_switch("foo") is True

    def test_trigger_set_offline_false(self):
        with patch.object(ipc_bridge, "_run_call", side_effect=self.OFFLINE_EXC):
            assert ipc_bridge.trigger_set("left", "rigid", [100]) is False

    def test_trigger_set_online_true(self):
        with patch.object(ipc_bridge, "_run_call", return_value=None):
            assert ipc_bridge.trigger_set("left", "rigid", [100]) is True

    def test_led_set_offline_false(self):
        with patch.object(ipc_bridge, "_run_call", side_effect=self.OFFLINE_EXC):
            assert ipc_bridge.led_set((255, 0, 0)) is False

    def test_led_set_online_true(self):
        with patch.object(ipc_bridge, "_run_call", return_value=None):
            assert ipc_bridge.led_set((255, 0, 0), brightness=0.5) is True

    def test_rumble_set_offline_false(self):
        with patch.object(ipc_bridge, "_run_call", side_effect=self.OFFLINE_EXC):
            assert ipc_bridge.rumble_set(128, 128) is False

    def test_rumble_set_online_true(self):
        with patch.object(ipc_bridge, "_run_call", return_value=None):
            assert ipc_bridge.rumble_set(128, 128) is True

    def test_rumble_stop_offline_false(self):
        with patch.object(ipc_bridge, "_run_call", side_effect=self.OFFLINE_EXC):
            assert ipc_bridge.rumble_stop() is False

    def test_rumble_passthrough_offline_false(self):
        with patch.object(ipc_bridge, "_run_call", side_effect=self.OFFLINE_EXC):
            assert ipc_bridge.rumble_passthrough(True) is False

    def test_rumble_policy_set_offline_false(self):
        with patch.object(ipc_bridge, "_run_call", side_effect=self.OFFLINE_EXC):
            assert ipc_bridge.rumble_policy_set("balanceado") is False

    def test_rumble_policy_custom_offline_false(self):
        with patch.object(ipc_bridge, "_run_call", side_effect=self.OFFLINE_EXC):
            assert ipc_bridge.rumble_policy_custom(0.5) is False

    def test_player_leds_set_offline_false(self):
        with patch.object(ipc_bridge, "_run_call", side_effect=self.OFFLINE_EXC):
            assert ipc_bridge.player_leds_set((True, False, True, False, True)) is False

    def test_mouse_emulation_set_offline_false(self):
        with patch.object(ipc_bridge, "_run_call", side_effect=self.OFFLINE_EXC):
            assert ipc_bridge.mouse_emulation_set(True, speed=5) is False

    def test_apply_draft_offline_false(self):
        with patch.object(ipc_bridge, "_run_call", side_effect=self.OFFLINE_EXC):
            assert ipc_bridge.apply_draft({"triggers": {}}) is False

    def test_apply_draft_status_ok_true(self):
        with patch.object(ipc_bridge, "_run_call", return_value={"status": "ok"}):
            assert ipc_bridge.apply_draft({"triggers": {}}) is True

    def test_apply_draft_status_nao_ok_false(self):
        """Daemon responde, mas status != ok → False (contrato FEAT-PROFILE-STATE-01)."""
        with patch.object(ipc_bridge, "_run_call", return_value={"status": "erro"}):
            assert ipc_bridge.apply_draft({"triggers": {}}) is False


class TestApplyDraftDetalhado:
    """APLICAR-VERDADE-01/E2 — a ponte para de estreitar a verdade.

    A ``apply_draft`` devolve ``bool`` e o mapa ``failed`` (quais seções NÃO
    entraram) morria aqui: quem chamava recebia ``False`` e não tinha como
    distinguir "o daemon está desligado" de "a seção de luzes falhou". A cura
    foi ADITIVA — a ``apply_draft`` continua devolvendo ``bool`` (o valor-
    verdade dela É o contrato R-18, e um ``dict`` no lugar seria sempre
    verdadeiro num ``if``), e quem precisa dizer a verdade na tela chama a
    detalhada.

    Esta classe é a metade da E2 que NÃO precisa de GTK, então morde também no
    CI headless; a metade da tela mora em
    ``tests/unit/test_aplicar_verdade_ponte_lightbar.py``.
    """

    OFFLINE_EXC = FileNotFoundError("socket ausente")

    def test_o_failed_atravessa_a_ponte(self):
        """Falha-sem: o mapa de seções que caíram tem de CHEGAR ao chamador."""
        resposta = {
            "status": "ok",
            "applied": [],
            "failed": {"leds": "hidraw: Permission denied"},
        }
        with patch.object(ipc_bridge, "_run_call", return_value=resposta):
            assert ipc_bridge.apply_draft_detalhado({"leds": {}}) == resposta

    def test_offline_devolve_none_e_nao_dicionario_vazio(self):
        """``None`` quer dizer "não houve resposta" — é o que separa "o Hefesto
        está desligado" de "a seção não entrou". Um ``{}`` no lugar apagaria a
        distinção que a aba Lightbar usa para escolher a frase."""
        with patch.object(ipc_bridge, "_run_call", side_effect=self.OFFLINE_EXC):
            assert ipc_bridge.apply_draft_detalhado({"leds": {}}) is None

    def test_resposta_que_nao_e_dicionario_e_tratada_como_ausencia(self):
        with patch.object(ipc_bridge, "_run_call", return_value="ok"):
            assert ipc_bridge.apply_draft_detalhado({"leds": {}}) is None

    def test_apply_draft_continua_bool(self):
        """Compatibilidade: a assinatura exportada no ``__all__`` não mudou."""
        resposta = {"status": "ok", "applied": [], "failed": {"leds": "x"}}
        with patch.object(ipc_bridge, "_run_call", return_value=resposta):
            assert ipc_bridge.apply_draft({"leds": {}}) is False
        with patch.object(
            ipc_bridge, "_run_call", return_value={"status": "ok", "applied": ["leds"]}
        ):
            assert ipc_bridge.apply_draft({"leds": {}}) is True

    def test_aplicacao_confirmada_e_o_dono_unico_da_regra_r18(self):
        """A mesma leitura do payload para os dois caminhos — sem ``failed``
        vazio virando sucesso e sem daemon antigo virando falha."""
        confirmada = ipc_bridge.aplicacao_confirmada
        assert confirmada({"status": "ok", "applied": ["leds"]}) is True
        assert confirmada({"status": "ok", "applied": []}) is False
        assert confirmada({"status": "ok"}) is True  # daemon antigo
        assert confirmada({"status": "erro", "applied": ["leds"]}) is False
        assert confirmada(None) is False
        assert confirmada(True) is False

    def test_daemon_state_full_offline_none(self):
        with patch.object(ipc_bridge, "_run_call", side_effect=self.OFFLINE_EXC):
            assert ipc_bridge.daemon_state_full() is None

    def test_daemon_state_full_online_dict(self):
        with patch.object(ipc_bridge, "_run_call", return_value={"a": 1}):
            assert ipc_bridge.daemon_state_full() == {"a": 1}

    def test_daemon_status_basic_offline_none(self):
        with patch.object(ipc_bridge, "_run_call", side_effect=self.OFFLINE_EXC):
            assert ipc_bridge.daemon_status_basic() is None

    def test_daemon_status_basic_online_dict(self):
        with patch.object(ipc_bridge, "_run_call", return_value={"running": True}):
            assert ipc_bridge.daemon_status_basic() == {"running": True}


class TestWrappersPropagandoBugs:
    """Exceções fora do filtro transporte propagam — executor detecta bug."""

    @pytest.mark.parametrize(
        "wrapper,args",
        [
            (ipc_bridge.profile_switch, ("foo",)),
            (ipc_bridge.trigger_set, ("left", "rigid", [1])),
            (ipc_bridge.led_set, ((10, 20, 30),)),
            (ipc_bridge.rumble_set, (1, 2)),
            (ipc_bridge.rumble_stop, ()),
            (ipc_bridge.rumble_passthrough, (True,)),
            (ipc_bridge.rumble_policy_set, ("max",)),
            (ipc_bridge.rumble_policy_custom, (0.3,)),
            (ipc_bridge.player_leds_set, ((True, True, False, False, False),)),
            (ipc_bridge.mouse_emulation_set, (True,)),
            (ipc_bridge.apply_draft, ({"x": 1},)),
            (ipc_bridge.apply_draft_detalhado, ({"x": 1},)),
            (ipc_bridge.daemon_state_full, ()),
            (ipc_bridge.daemon_status_basic, ()),
        ],
    )
    def test_value_error_propaga(self, wrapper, args):
        with (
            patch.object(
                ipc_bridge,
                "_run_call",
                side_effect=ValueError("bug real"),
            ),
            pytest.raises(ValueError, match="bug real"),
        ):
            wrapper(*args)


# ---------------------------------------------------------------------------
# profile_list — fallback de disco preservado
# ---------------------------------------------------------------------------


class TestProfileListFallback:
    """profile_list tem duas camadas: IPC primário + disco fallback."""

    def test_daemon_online_retorna_perfis_do_daemon(self):
        with patch.object(
            ipc_bridge,
            "_run_call",
            return_value={"profiles": [{"name": "default", "active": True}]},
        ):
            resultado = ipc_bridge.profile_list()

        assert resultado == [{"name": "default", "active": True}]

    def test_daemon_offline_usa_fallback_disco(self):
        """IPC falha → loader de disco é consultado."""
        with patch.object(
            ipc_bridge,
            "_run_call",
            side_effect=FileNotFoundError("sem socket"),
        ):
            # Chamada real ao loader — garante formato mínimo.
            resultado = ipc_bridge.profile_list()

        # assets/profiles_default/ tem pelo menos 1 perfil default.
        assert isinstance(resultado, list)
        assert all("name" in p and "active" in p for p in resultado)
        assert all(p["active"] is False for p in resultado)  # fallback marca offline


# ---------------------------------------------------------------------------
# HARM-19 — recusa do daemon != daemon offline
# ---------------------------------------------------------------------------


class TestTriggerSetChecked:
    """`trigger_set_checked` separa "o daemon recusou" de "não achei o daemon".

    `_safe_call` colapsa os dois em (False, None) — e era por isso que a aba
    Triggers pintava "Fim <= Início" como "daemon offline?" com o daemon vivo.
    """

    def test_recusa_de_validacao_devolve_a_mensagem(self):
        from hefesto_dualsense4unix.daemon.ipc_server import CODE_INVALID_PARAMS

        exc = IpcError(CODE_INVALID_PARAMS, "end (3) deve ser > start (5)")
        with patch.object(ipc_bridge, "_run_call", side_effect=exc):
            ok, motivo = ipc_bridge.trigger_set_checked("left", "Bow", [5, 3, 4, 4])

        assert ok is False
        assert motivo == "end (3) deve ser > start (5)"

    def test_daemon_offline_nao_inventa_motivo(self):
        with patch.object(
            ipc_bridge, "_run_call", side_effect=FileNotFoundError("sem socket")
        ):
            ok, motivo = ipc_bridge.trigger_set_checked("left", "Rigid", [5, 200])

        assert (ok, motivo) == (False, None)

    def test_timeout_de_transporte_nao_vira_motivo(self):
        """O timeout do IpcClient também é IpcError — mas com code=-1, não é
        uma recusa do daemon."""
        with patch.object(
            ipc_bridge, "_run_call", side_effect=IpcError(-1, "conexão timeout")
        ):
            ok, motivo = ipc_bridge.trigger_set_checked("left", "Rigid", [5, 200])

        assert (ok, motivo) == (False, None)

    def test_sucesso_sem_motivo(self):
        with patch.object(ipc_bridge, "_run_call", return_value={"status": "ok"}):
            assert ipc_bridge.trigger_set_checked("left", "Rigid", [5, 200]) == (
                True,
                None,
            )

    def test_excecao_inesperada_propaga(self):
        with (
            patch.object(ipc_bridge, "_run_call", side_effect=TypeError("bug")),
            pytest.raises(TypeError),
        ):
            ipc_bridge.trigger_set_checked("left", "Rigid", [5, 200])
