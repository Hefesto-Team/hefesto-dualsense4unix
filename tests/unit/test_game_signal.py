"""NUMA-01 — o sinal "jogo real ativo" (`classify` puro + casca `GameSignal`).

Bloco 1 do plano de testes da sprint (2026-07-19-sprint-numeracao-una.md):
tabela-verdade de `classify()` por ramo de evidência isolado, histerese de
30s da queda `*→daemon` (não cai antes, sobe/degrada imediato) e os dois
vetos permanentes anti-regressão do incidente 14:42:

  - sessão-uhid-aberta SOZINHA não é evidência de jogo (`session_open` não
    entra em `classify` — só modula a histerese em `GameSignal.evaluate`);
  - `window_detect_last_class` STICKY com a leitura corrente vazia/unknown
    NÃO é evidência (prenderia `game` para sempre depois do jogo fechar).
"""
from __future__ import annotations

from hefesto_dualsense4unix.daemon.subsystems.game_signal import (
    HYSTERESIS_SEC,
    Authority,
    GameSignal,
    classify,
)

APPID = 1599660
STEAM_WC = f"steam_app_{APPID}"


def _classify(
    *,
    window_healthy: bool = True,
    window_class_current: str | None = None,
    window_seen_age: float | None = None,
    profile_rule_match: bool = False,
    marker: tuple[int, int] | None = None,
    marker_pid_alive: bool = False,
    exit_marker: int | None = None,
    session_open: bool = False,
    now: float = 1_000.0,
) -> Authority:
    """`classify()` com uma base "sem evidência nenhuma", só overrides."""
    return classify(
        window_healthy=window_healthy,
        window_class_current=window_class_current,
        window_seen_age=window_seen_age,
        profile_rule_match=profile_rule_match,
        marker=marker,
        marker_pid_alive=marker_pid_alive,
        exit_marker=exit_marker,
        session_open=session_open,
        now=now,
    )


# --- tabela-verdade de classify() --------------------------------------------


class TestSemEvidenciaNenhuma:
    def test_detector_saudavel_sem_evidencia_e_daemon(self) -> None:
        assert _classify(window_healthy=True) == "daemon"

    def test_detector_nao_saudavel_sem_evidencia_e_unknown(self) -> None:
        """Fail-safe: detector cego (Wayland puro/backend null) sem NENHUMA
        evidência não pode virar `daemon` — nunca pior que hoje."""
        assert _classify(window_healthy=False) == "unknown"


class TestEvidenciaJanela:
    def test_wm_class_corrente_steam_app_e_game(self) -> None:
        assert (
            _classify(window_healthy=False, window_class_current=STEAM_WC)
            == "game"
        )

    def test_wm_class_corrente_nao_steam_app_nao_e_evidencia(self) -> None:
        assert _classify(window_class_current="Celeste") == "daemon"

    def test_idade_fresca_de_game_window_seen_at_e_evidencia(self) -> None:
        """Hiccup momentâneo do detector (leitura corrente vazia) tolerado
        enquanto a idade do último carimbo `steam_app` ainda cabe na
        histerese — SEM recorrer ao sticky vetado."""
        assert (
            _classify(
                window_healthy=False,
                window_class_current=None,
                window_seen_age=HYSTERESIS_SEC,
            )
            == "game"
        )

    def test_idade_expirada_nao_e_mais_evidencia(self) -> None:
        assert (
            _classify(
                window_healthy=False,
                window_class_current=None,
                window_seen_age=HYSTERESIS_SEC + 0.01,
            )
            == "unknown"
        )

    def test_sticky_nao_entra_no_classify_nao_e_parametro(self) -> None:
        """Veto anti-regressão do incidente: `classify()` nem ACEITA o
        sticky `window_detect_last_class` como parâmetro — só a leitura
        CORRENTE (`window_class_current`) e a idade que DECAI
        (`window_seen_age`). Corrente vazia + idade None (nunca visto) ⇒
        NUNCA `game`, mesmo que uma classe sticky antiga exista em outro
        lugar do estado — prenderia a autoridade em `game` para sempre."""
        assert (
            _classify(
                window_healthy=True,
                window_class_current=None,
                window_seen_age=None,
            )
            == "daemon"
        )


class TestEvidenciaPerfil:
    def test_profile_rule_match_e_game(self) -> None:
        assert (
            _classify(window_healthy=False, profile_rule_match=True) == "game"
        )

    def test_profile_rule_match_false_nao_e_evidencia(self) -> None:
        assert _classify(profile_rule_match=False) == "daemon"


class TestEvidenciaMarker:
    def test_marker_fresco_pid_vivo_sem_exit_e_game(self) -> None:
        assert (
            _classify(
                window_healthy=False,
                marker=(APPID, 990),
                marker_pid_alive=True,
                exit_marker=None,
                now=1000.0,
            )
            == "game"
        )

    def test_marker_sem_pid_vivo_nao_e_evidencia(self) -> None:
        assert (
            _classify(
                marker=(APPID, 990), marker_pid_alive=False, now=1000.0
            )
            == "daemon"
        )

    def test_marker_com_exit_mais_novo_nao_e_evidencia(self) -> None:
        """FEIT-EXIT: o processo daquele launch já terminou — o marker não
        atesta jogo rodando."""
        assert (
            _classify(
                marker=(APPID, 990),
                marker_pid_alive=True,
                exit_marker=995,
                now=1000.0,
            )
            == "daemon"
        )

    def test_marker_velho_demais_nao_e_evidencia(self) -> None:
        from hefesto_dualsense4unix.daemon.launch_env import (
            WRAPPER_MARKER_WINDOW_SEC,
        )

        velho = 1000.0 - WRAPPER_MARKER_WINDOW_SEC - 1
        assert (
            _classify(
                marker=(APPID, velho), marker_pid_alive=True, now=1000.0
            )
            == "daemon"
        )


class TestQualquerEvidenciaVenceUnknown:
    def test_evidencia_de_jogo_vence_mesmo_com_detector_cego(self) -> None:
        """Marker/perfil não dependem do detector de janela (Wayland puro
        COM wrapper é exatamente o caso que a evidência #3 cobre)."""
        assert (
            _classify(
                window_healthy=False,
                marker=(APPID, 990),
                marker_pid_alive=True,
                now=1000.0,
            )
            == "game"
        )


class TestSessionOpenNaoEntraNoClassify:
    def test_session_open_true_sozinho_nunca_vira_game(self) -> None:
        """Veto permanente #1 da síntese: sessão uhid aberta (o cliente
        Steam TAMBÉM abre) JAMAIS é evidência de jogo."""
        assert _classify(session_open=True) == "daemon"

    def test_session_open_false_nao_muda_o_veredito_de_game(self) -> None:
        assert (
            _classify(
                window_healthy=False,
                window_class_current=STEAM_WC,
                session_open=False,
            )
            == "game"
        )


# --- GameSignal: histerese + telemetria --------------------------------------


class _Clock:
    def __init__(self, start: float = 0.0) -> None:
        self.now = start

    def __call__(self) -> float:
        return self.now

    def advance(self, delta: float) -> None:
        self.now += delta


class TestHisterese:
    def test_subida_para_game_e_imediata(self) -> None:
        clock = _Clock()
        signal = GameSignal(time_fn=clock)
        assert signal.evaluate("game", session_open=True) == "game"

    def test_degradacao_para_unknown_e_imediata(self) -> None:
        clock = _Clock()
        signal = GameSignal(time_fn=clock)
        signal.evaluate("game", session_open=True)
        assert signal.evaluate("unknown", session_open=True) == "unknown"

    def test_queda_para_daemon_nao_acontece_antes_de_30s_com_sessao_aberta(
        self,
    ) -> None:
        """Ticks periódicos (padrão de produção, ~2s): a PRIMEIRA observação
        de `daemon` arma o relógio; antes de completar `HYSTERESIS_SEC`
        contínuos de observações `daemon`, a autoridade PERMANECE `game`."""
        clock = _Clock()
        signal = GameSignal(time_fn=clock)
        signal.evaluate("game", session_open=True)
        assert signal.evaluate("daemon", session_open=True) == "game"  # arma
        clock.advance(HYSTERESIS_SEC - 0.01)
        assert signal.evaluate("daemon", session_open=True) == "game"

    def test_queda_para_daemon_honrada_apos_30s_continuos(self) -> None:
        clock = _Clock()
        signal = GameSignal(time_fn=clock)
        signal.evaluate("game", session_open=True)
        assert signal.evaluate("daemon", session_open=True) == "game"  # arma
        clock.advance(HYSTERESIS_SEC)
        assert signal.evaluate("daemon", session_open=True) == "daemon"

    def test_sem_sessao_aberta_queda_e_imediata(self) -> None:
        """Sem sessão uhid aberta não há réplica de exibição a proteger —
        a histerese é dispensada por completo."""
        clock = _Clock()
        signal = GameSignal(time_fn=clock)
        signal.evaluate("game", session_open=True)
        assert signal.evaluate("daemon", session_open=False) == "daemon"

    def test_retorno_a_game_antes_da_janela_reseta_o_relogio_da_queda(
        self,
    ) -> None:
        """Alt-tab curto: evidência volta antes dos 30s — a queda seguinte
        precisa esperar os 30s inteiros de novo (não herda o tempo já
        decorrido)."""
        clock = _Clock()
        signal = GameSignal(time_fn=clock)
        signal.evaluate("game", session_open=True)
        clock.advance(HYSTERESIS_SEC - 1)
        assert signal.evaluate("daemon", session_open=True) == "game"
        assert signal.evaluate("game", session_open=True) == "game"
        clock.advance(HYSTERESIS_SEC - 1)
        assert signal.evaluate("daemon", session_open=True) == "game"

    def test_mark_degraded_e_imediato_e_loga(self) -> None:
        clock = _Clock()
        signal = GameSignal(time_fn=clock)
        signal.evaluate("game", session_open=True)
        assert signal.mark_degraded("erro_leitura") == "unknown"

    def test_authority_inicial_e_unknown(self) -> None:
        assert GameSignal().authority == "unknown"

    def test_transicao_para_o_mesmo_valor_nao_reloga(self) -> None:
        clock = _Clock()
        signal = GameSignal(time_fn=clock)
        signal.evaluate("daemon", session_open=False)
        signal.evaluate("daemon", session_open=False)
        # Não deve levantar nem mudar o estado — idempotente.
        assert signal.authority == "daemon"
