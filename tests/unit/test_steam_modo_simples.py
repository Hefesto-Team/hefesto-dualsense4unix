"""FEAT-STEAM-SIMPLES-01 — dois botões que escondem os dois mecanismos.

Pedido literal da usuária final (25/07): "tem jogos que precisamos ativar
entrada steam, outros que temos que colocar comandos de inicialização — é uma
confusão real". Os dois mecanismos continuam existindo; o que sai da tela é a
ESCOLHA entre eles.

  "Deixar tudo pronto"     → encadeia o desligar do Steam Input + a aplicação
                             do wrapper em todos os jogos, com UM consentimento
                             só (o de fechar a Steam) e UMA janela de Steam
                             fechada para as duas edições.
  "Este jogo não funciona" → resolve o appid do jogo ativo, grava na allowlist
                             `steam_input_apps.txt` e manda o daemon
                             rematerializar as envs de launch.

Este arquivo também trava a honestidade do "Aplicar correções" (sem senha):
ele NÃO fecha a Steam, então quando o `--apply-quiet` adia, o toast tem de
DIZER que adiou — era ele que anunciava "Correções aplicadas" sobre um no-op.
"""
from __future__ import annotations

import re
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from hefesto_dualsense4unix.app.actions import daemon_actions
from hefesto_dualsense4unix.app.actions.daemon_actions import (
    DaemonActionsMixin,
    format_fix_safe_result,
    format_game_broken_result,
    format_steam_janela_recusa,
    format_steam_ready_result,
)
from tests.conftest import skip_sem_gtk_response

_GLADE = (
    Path(__file__).resolve().parents[2]
    / "src"
    / "hefesto_dualsense4unix"
    / "gui"
    / "main.glade"
)


# ---------------------------------------------------------------------------
# Formatters puros
# ---------------------------------------------------------------------------


class TestFormatSteamJanelaRecusa:
    def test_ok_nao_e_recusa(self) -> None:
        assert format_steam_janela_recusa("ok") is None

    def test_jogo_aberto_explica_o_risco(self) -> None:
        msg = format_steam_janela_recusa("jogo_aberto")
        assert msg and "progresso" in msg and "Nada foi mudado" in msg

    def test_nao_fechou_explica_o_porque(self) -> None:
        msg = format_steam_janela_recusa("nao_fechou")
        assert msg and "regrava o arquivo ao sair" in msg

    @pytest.mark.parametrize("torto", [None, "", "qualquer", 7])
    def test_status_desconhecido_e_recusa_honesta(self, torto: object) -> None:
        msg = format_steam_janela_recusa(torto)
        assert msg and "Pronto" not in msg


class TestFormatFixSafe:
    def test_adiado_diz_que_adiou_e_aponta_o_botao_certo(self) -> None:
        """O bug: dizia "Correções aplicadas" mesmo quando NADA foi aplicado."""
        msg = format_fix_safe_result(
            {
                "ran": 2,
                "missing": 0,
                "steam_input": (0, "[steam-input] resultado=adiado-steam-aberta\n"),
            }
        )
        assert "NÃO foi desligado" in msg
        assert "Deixar tudo pronto" in msg

    def test_aplicado_relata_o_que_mudou(self) -> None:
        msg = format_fix_safe_result(
            {
                "ran": 2,
                "missing": 0,
                "steam_input": (0, "[steam-input] resultado=aplicado\n"),
            }
        )
        assert "não sequestra mais" in msg
        assert "Deixar tudo pronto" not in msg

    def test_erro_do_script_nao_vira_sucesso(self) -> None:
        msg = format_fix_safe_result(
            {"ran": 2, "missing": 0, "steam_input": (1, "[steam-input] resultado=erro\n")}
        )
        assert "NÃO mudou" in msg
        assert "erro 1" in msg

    def test_scripts_ausentes(self) -> None:
        msg = format_fix_safe_result({"ran": 0, "missing": 2, "steam_input": None})
        assert "Não encontrei os scripts" in msg

    @pytest.mark.parametrize("torto", [None, "ok", 7, []])
    def test_fora_do_contrato_e_recusa(self, torto: object) -> None:
        msg = format_fix_safe_result(torto)
        assert "Não consegui aplicar" in msg


class TestFormatSteamReady:
    def _dados(self, tag: str = "aplicado", rc: int = 0) -> dict[str, Any]:
        return {
            "script": (rc, f"[steam-input] resultado={tag}\n"),
            "wrapper": {"applied": 3, "skipped": 0, "errors": 0},
        }

    def test_caminho_feliz_relata_as_duas_pernas(self) -> None:
        msg = format_steam_ready_result(janela="ok", dados=self._dados())
        assert "Controle:" in msg
        assert "Jogos:" in msg
        assert "3 jogo(s)" in msg

    def test_recusa_de_jogo_aberto_vence_tudo(self) -> None:
        msg = format_steam_ready_result(janela="jogo_aberto", dados=self._dados())
        assert "progresso" in msg
        assert "Jogos:" not in msg

    def test_steam_teimosa_nao_diz_pronto(self) -> None:
        msg = format_steam_ready_result(janela="nao_fechou", dados=None)
        assert "não fechou" in msg

    def test_script_ausente_e_dito_sem_derrubar_a_outra_perna(self) -> None:
        msg = format_steam_ready_result(
            janela="ok", dados={"script": None, "wrapper": {"applied": 1}},
            script_ok=False,
        )
        assert "install.sh" in msg
        assert "1 jogo(s)" in msg

    def test_instalacao_sem_nenhuma_das_pecas(self) -> None:
        msg = format_steam_ready_result(
            janela="ok", dados={}, script_ok=False, wrapper_ok=False
        )
        assert "install.sh" in msg

    def test_dados_fora_do_contrato(self) -> None:
        msg = format_steam_ready_result(janela="ok", dados="oi")
        assert "Não consegui deixar tudo pronto" in msg

    def test_nao_pronuncia_os_conceitos_que_confundem(self) -> None:
        """A usuária final não deve ler "Steam Input" nem "opção de
        inicialização" no caminho feliz — é o ponto do botão."""
        msg = format_steam_ready_result(janela="ok", dados=self._dados())
        assert "Steam Input" not in msg
        assert "inicialização" not in msg


class TestFormatGameBroken:
    def test_adicionado_diz_o_proximo_passo(self) -> None:
        msg = format_game_broken_result(status="adicionado", appid=2111190)
        assert "2111190" in msg
        assert "Feche e abra o jogo" in msg

    def test_ja_estava_nao_finge_novidade(self) -> None:
        msg = format_game_broken_result(status="ja_estava", appid=620)
        assert "já estava marcado" in msg

    def test_sem_jogo_pede_o_que_falta(self) -> None:
        msg = format_game_broken_result(status="sem_jogo")
        assert "Não descobri qual é o jogo" in msg

    def test_erro_nao_vira_sucesso(self) -> None:
        assert "Não consegui anotar" in format_game_broken_result(status="erro")

    def test_nunca_pronuncia_steam_input_nem_launch_option(self) -> None:
        for status in ("adicionado", "ja_estava", "sem_jogo", "erro"):
            msg = format_game_broken_result(status=status, appid=1)
            assert "Steam Input" not in msg
            assert "inicialização" not in msg


# ---------------------------------------------------------------------------
# Fluxo dos handlers
# ---------------------------------------------------------------------------


class _Stub(DaemonActionsMixin):
    def __init__(self) -> None:
        self.toasts: list[str] = []
        self.diag_refreshes = 0
        self.window = None

    def _status_toast(self, _ctx: str, msg: str) -> None:
        self.toasts.append(msg)

    def _refresh_storm_diag(self) -> None:  # type: ignore[override]
        self.diag_refreshes += 1


@pytest.fixture()
def sincrono(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        daemon_actions,
        "_get_executor",
        lambda: SimpleNamespace(submit=lambda fn: fn()),
    )
    monkeypatch.setattr(
        daemon_actions,
        "GLib",
        SimpleNamespace(idle_add=lambda fn, *args: fn(*args)),
    )


@pytest.fixture()
def slo_fake(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    from hefesto_dualsense4unix.integrations import steam_launch_options as slo

    caixa: dict[str, Any] = {
        "steam": False,
        "jogo": False,
        "parou": 0,
        "reabriu": 0,
        "wrapper": {"applied": 2, "skipped": 0, "errors": 0},
        "runs": [],
        "script_rc": 0,
        "script_saida": "[steam-input] resultado=aplicado\n",
    }
    monkeypatch.setattr(slo, "steam_running", lambda: caixa["steam"])
    monkeypatch.setattr(slo, "steam_game_running", lambda: caixa["jogo"])

    def _stop() -> bool:
        caixa["parou"] += 1
        caixa["steam"] = False
        return True

    monkeypatch.setattr(slo, "stop_steam", _stop)
    monkeypatch.setattr(
        slo, "reopen_steam", lambda: caixa.__setitem__("reabriu", caixa["reabriu"] + 1)
    )
    monkeypatch.setattr(
        slo, "apply_wrapper_to_all_games", lambda: caixa["wrapper"], raising=False
    )

    def _run(args, **_kwargs):
        caixa["runs"].append(list(args))
        return SimpleNamespace(
            returncode=caixa["script_rc"], stdout=caixa["script_saida"], stderr=""
        )

    monkeypatch.setattr(
        daemon_actions,
        "subprocess",
        SimpleNamespace(run=_run, SubprocessError=Exception),
    )
    return caixa


class TestFixSafeHandler:
    def test_toast_final_sai_do_formatter_honesto(
        self, sincrono: None, slo_fake: dict[str, Any], monkeypatch
    ) -> None:
        slo_fake["script_saida"] = "[steam-input] resultado=adiado-steam-aberta\n"
        monkeypatch.setattr(
            _Stub, "_find_repo_file", lambda _self, rel: Path("/fake") / rel
        )
        stub = _Stub()

        stub.on_storm_fix_safe(None)

        assert any("NÃO foi desligado" in t for t in stub.toasts)
        assert not any(
            t.startswith("Correções aplicadas (sem senha). A cura") for t in stub.toasts
        )


class TestDeixarTudoPronto:
    def test_jogo_aberto_nao_toca_em_nada(
        self, sincrono: None, slo_fake: dict[str, Any], monkeypatch
    ) -> None:
        slo_fake["jogo"] = True
        slo_fake["steam"] = True
        monkeypatch.setattr(
            _Stub, "_find_repo_file", lambda _self, rel: Path("/fake") / rel
        )
        stub = _Stub()

        stub._steam_ready_worker()

        assert slo_fake["runs"] == []
        assert slo_fake["parou"] == 0
        assert any("progresso" in t for t in stub.toasts)

    def test_uma_janela_so_para_as_duas_edicoes(
        self, sincrono: None, slo_fake: dict[str, Any], monkeypatch
    ) -> None:
        """Fecha UMA vez, roda as duas correções, reabre UMA vez — duas
        janelas separadas seriam duas chances de a Steam pisar a edição."""
        slo_fake["steam"] = True
        monkeypatch.setattr(
            _Stub, "_find_repo_file", lambda _self, rel: Path("/fake") / rel
        )
        stub = _Stub()

        stub._steam_ready_worker()

        assert slo_fake["parou"] == 1
        assert slo_fake["reabriu"] == 1
        assert slo_fake["runs"] and "--apply-quiet" in slo_fake["runs"][0]
        toast = stub.toasts[-1]
        assert "Controle:" in toast and "Jogos:" in toast
        assert "2 jogo(s)" in toast

    def test_steam_fechada_nao_fecha_nem_reabre(
        self, sincrono: None, slo_fake: dict[str, Any], monkeypatch
    ) -> None:
        monkeypatch.setattr(
            _Stub, "_find_repo_file", lambda _self, rel: Path("/fake") / rel
        )
        stub = _Stub()

        stub._steam_ready_worker()

        assert slo_fake["parou"] == 0
        assert slo_fake["reabriu"] == 0
        assert slo_fake["runs"]

    def test_instalacao_sem_o_script_nao_derruba_a_outra_perna(
        self, sincrono: None, slo_fake: dict[str, Any], monkeypatch
    ) -> None:
        monkeypatch.setattr(_Stub, "_find_repo_file", lambda _self, _rel: None)
        stub = _Stub()

        stub._steam_ready_worker()

        assert slo_fake["runs"] == []
        assert "install.sh" in stub.toasts[-1]
        assert "2 jogo(s)" in stub.toasts[-1]  # o wrapper rodou mesmo assim

    @skip_sem_gtk_response
    def test_cancelar_a_confirmacao_nao_faz_nada(
        self, sincrono: None, slo_fake: dict[str, Any], monkeypatch
    ) -> None:
        from gi.repository import Gtk

        chamou = []
        monkeypatch.setattr(
            _Stub, "_steam_ready_worker", lambda _self: chamou.append(True)
        )
        stub = _Stub()

        stub._on_steam_ready_response(
            SimpleNamespace(destroy=lambda: None), int(Gtk.ResponseType.CANCEL)
        )

        assert chamou == []
        assert any("Nada foi mudado" in t for t in stub.toasts)

    @skip_sem_gtk_response
    def test_ok_na_confirmacao_dispara_o_worker(
        self, sincrono: None, monkeypatch
    ) -> None:
        from gi.repository import Gtk

        chamou = []
        monkeypatch.setattr(
            _Stub, "_steam_ready_worker", lambda _self: chamou.append(True)
        )
        stub = _Stub()

        stub._on_steam_ready_response(
            SimpleNamespace(destroy=lambda: None), int(Gtk.ResponseType.OK)
        )

        assert chamou == [True]

    def test_dialogo_avisa_do_fechamento_e_dos_downloads(self, monkeypatch) -> None:
        capturado: dict[str, Any] = {}
        monkeypatch.setattr(
            daemon_actions,
            "build_steam_close_consent_dialog",
            lambda _p, **kw: (capturado.update(kw), SimpleNamespace())[1],
        )

        _Stub()._build_steam_ready_confirm_dialog()

        assert "20 segundos" in capturado["corpo"]
        assert "Pause os downloads" in capturado["corpo"]
        assert "jogo estiver aberto" in capturado["corpo"]
        # Nenhum jargão na cara da usuária.
        assert "Steam Input" not in capturado["corpo"]
        assert "inicialização" not in capturado["corpo"]


class TestEsteJogoNaoFunciona:
    @pytest.fixture(autouse=True)
    def _sem_ipc(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """`launch_env.refresh` é best-effort — aqui só registramos a chamada."""
        from hefesto_dualsense4unix.app import ipc_bridge

        self.chamadas_ipc: list[str] = []
        monkeypatch.setattr(
            ipc_bridge,
            "call_async",
            lambda method, params, on_success=None, on_failure=None: (
                self.chamadas_ipc.append(method)
            ),
        )

    def test_grava_o_appid_e_manda_rematerializar(
        self, sincrono: None, monkeypatch, tmp_path: Path
    ) -> None:
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
        monkeypatch.setattr(
            DaemonActionsMixin, "_appid_do_jogo_ativo", staticmethod(lambda: 2111190)
        )
        stub = _Stub()

        stub.on_steam_game_broken(None)

        alvo = tmp_path / "hefesto-dualsense4unix" / "steam_input_apps.txt"
        assert "2111190" in alvo.read_text(encoding="utf-8")
        assert "launch_env.refresh" in self.chamadas_ipc
        assert any("2111190" in t for t in stub.toasts)

    def test_duplicata_nao_reescreve_e_e_dita(
        self, sincrono: None, monkeypatch, tmp_path: Path
    ) -> None:
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
        alvo = tmp_path / "hefesto-dualsense4unix" / "steam_input_apps.txt"
        alvo.parent.mkdir(parents=True)
        alvo.write_text("# meu cabeçalho\n2111190\n", encoding="utf-8")
        monkeypatch.setattr(
            DaemonActionsMixin, "_appid_do_jogo_ativo", staticmethod(lambda: 2111190)
        )
        stub = _Stub()

        stub.on_steam_game_broken(None)

        assert alvo.read_text(encoding="utf-8") == "# meu cabeçalho\n2111190\n"
        assert any("já estava marcado" in t for t in stub.toasts)

    def test_sem_jogo_identificado_nao_escreve_nada(
        self, sincrono: None, monkeypatch, tmp_path: Path
    ) -> None:
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
        monkeypatch.setattr(
            DaemonActionsMixin, "_appid_do_jogo_ativo", staticmethod(lambda: None)
        )
        stub = _Stub()

        stub.on_steam_game_broken(None)

        assert not (tmp_path / "hefesto-dualsense4unix").exists()
        assert any("Não descobri qual é o jogo" in t for t in stub.toasts)


class TestResolucaoDoAppid:
    """Ordem das evidências: sessão viva > última janela útil > último launch.

    A ordem NÃO é cosmética: para clicar no Hefesto a usuária SAI do jogo, e o
    caso mais comum do botão é o jogo que ela já fechou porque não funcionou —
    por isso o marker `last_run` cru é fallback legítimo, e não lixo.
    """

    def _patch_launch_env(self, monkeypatch, *, sessao, marker):
        from hefesto_dualsense4unix.daemon import launch_env

        monkeypatch.setattr(launch_env, "launch_session_appid", lambda: sessao)
        monkeypatch.setattr(launch_env, "read_last_run_marker", lambda: marker)

    def test_sessao_viva_vence(self, monkeypatch) -> None:
        self._patch_launch_env(monkeypatch, sessao=111, marker=(999, 1))
        assert DaemonActionsMixin._appid_do_jogo_ativo() == 111

    def test_janela_util_quando_nao_ha_sessao(self, monkeypatch) -> None:
        from hefesto_dualsense4unix.app import ipc_bridge

        self._patch_launch_env(monkeypatch, sessao=None, marker=(999, 1))
        monkeypatch.setattr(
            ipc_bridge,
            "daemon_state_full",
            lambda *a, **k: {"window_detect_last_class": "steam_app_222"},
        )
        assert DaemonActionsMixin._appid_do_jogo_ativo() == 222

    def test_marker_cru_e_o_ultimo_recurso(self, monkeypatch) -> None:
        from hefesto_dualsense4unix.app import ipc_bridge

        self._patch_launch_env(monkeypatch, sessao=None, marker=(999, 1))
        monkeypatch.setattr(
            ipc_bridge,
            "daemon_state_full",
            lambda *a, **k: {"window_detect_last_class": "hefesto-dualsense4unix"},
        )
        assert DaemonActionsMixin._appid_do_jogo_ativo() == 999

    def test_sem_evidencia_nenhuma_devolve_none(self, monkeypatch) -> None:
        from hefesto_dualsense4unix.app import ipc_bridge

        self._patch_launch_env(monkeypatch, sessao=None, marker=None)
        monkeypatch.setattr(ipc_bridge, "daemon_state_full", lambda *a, **k: {})
        assert DaemonActionsMixin._appid_do_jogo_ativo() is None

    def test_daemon_offline_nao_derruba_a_resolucao(self, monkeypatch) -> None:
        """A GUI abre com o daemon morto o tempo todo — o IPC que estoura não
        pode custar o fallback do marker."""
        from hefesto_dualsense4unix.app import ipc_bridge

        self._patch_launch_env(monkeypatch, sessao=None, marker=(777, 1))

        def _explode(*_a, **_k):
            raise OSError("daemon offline")

        monkeypatch.setattr(ipc_bridge, "daemon_state_full", _explode)
        assert DaemonActionsMixin._appid_do_jogo_ativo() == 777


# ---------------------------------------------------------------------------
# Glade: os botões existem e são ligados em CÓDIGO (não por <signal> morto)
# ---------------------------------------------------------------------------


class TestGladeEWiring:
    def test_os_dois_botoes_existem_no_glade(self) -> None:
        xml = _GLADE.read_text(encoding="utf-8")
        assert 'id="btn_steam_ready"' in xml
        assert 'id="btn_steam_game_broken"' in xml

    def test_nao_ha_signal_orfao_para_eles(self) -> None:
        """BUG-GUI-EMULATION-HANDLERS-UNWIRED-01: `<signal handler="...">` sem
        entrada no dict de `app._signal_handlers()` vira botão MORTO. Estes
        dois são ligados em código, então o glade NÃO pode declarar o sinal."""
        xml = _GLADE.read_text(encoding="utf-8")
        for handler in ("on_steam_ready", "on_steam_game_broken"):
            assert f'handler="{handler}"' not in xml

    def test_install_da_aba_liga_os_dois(self) -> None:
        ligados: list[tuple[str, str]] = []

        class _StubWiring(_Stub):
            def _get(self, widget_id: str):  # type: ignore[override]
                return SimpleNamespace(
                    connect=lambda sinal, handler: ligados.append(
                        (widget_id, getattr(handler, "__name__", ""))
                    )
                )

        _StubWiring()._wire_steam_simple_buttons()

        assert ("btn_steam_ready", "on_steam_ready") in ligados
        assert ("btn_steam_game_broken", "on_steam_game_broken") in ligados

    def test_widget_ausente_nao_quebra(self) -> None:
        class _StubSemWidget(_Stub):
            def _get(self, _widget_id: str):  # type: ignore[override]
                return None

        _StubSemWidget()._wire_steam_simple_buttons()  # não levanta

    def test_tooltip_do_desligar_steam_input_nao_promete_o_que_nao_faz(
        self,
    ) -> None:
        """HONESTIDADE-STEAM-01: o tooltip prometia "(fecha e reabre a Steam)"
        e o handler rodava `--apply-quiet`, que nunca fecha nada."""
        xml = _GLADE.read_text(encoding="utf-8")
        bloco = re.search(
            r'id="emulation_steam_input_disable_button".*?</object>', xml, re.S
        )
        assert bloco is not None
        texto = bloco.group(0)
        assert "(fecha e reabre a Steam)" not in texto
        assert "permissão" in texto
