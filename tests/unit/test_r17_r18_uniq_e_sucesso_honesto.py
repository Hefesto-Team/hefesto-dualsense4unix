"""R-17 e R-18 (auditoria 23/07) — alvo certo e sucesso honesto."""

from __future__ import annotations

from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]


class TestR17ApagarMandaOUniq:
    def test_o_handler_passa_o_alvo(self) -> None:
        fonte = (
            REPO / "src/hefesto_dualsense4unix/app/actions/lightbar_actions.py"
        ).read_text(encoding="utf-8")
        # Z2-1 (24/08/2026): `_edit_uniq()` devolve `AlvoDeEdicao`, não mais
        # BG-01 (26/08/2026): a chamada virou `led_set_detalhado` — a aba lê o
        assert "led_set_detalhado((0, 0, 0), uniq=estado_alvo.uniq)" in fonte, (
            "apagar sem `uniq` vira broadcast: apaga a lightbar dos quatro "
            "quando ela pediu para apagar a de um"
        )

    def test_led_set_aceita_uniq(self) -> None:
        """A rota por-MAC precisa existir do outro lado (PERFIL-05)."""
        import inspect

        from hefesto_dualsense4unix.app import ipc_bridge

        assert (
            "uniq" in inspect.signature(ipc_bridge.led_set_detalhado).parameters
        )


class TestR18SucessoHonesto:

    def test_nada_aplicado_nao_e_sucesso(self, monkeypatch: pytest.MonkeyPatch) -> None:
        assert self._apply(monkeypatch, {"status": "ok", "applied": []}) is False, (
            "zero seções aplicadas é no-op — toastar 'aplicado' aqui é mentir "
            "para a usuária, que fica caçando por que a config não pegou"
        )

    def test_secao_aplicada_e_sucesso(self, monkeypatch: pytest.MonkeyPatch) -> None:
        assert self._apply(monkeypatch, {"status": "ok", "applied": ["leds"]}) is True

    def test_daemon_antigo_sem_o_campo_preserva_o_contrato(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        assert self._apply(monkeypatch, {"status": "ok"}) is True

    def test_status_diferente_de_ok_segue_falha(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        assert self._apply(monkeypatch, {"status": "erro", "applied": ["leds"]}) is False

    def test_status_ok_foi_mantido_de_proposito(self) -> None:
        """Trocar para "partial"/"failed" faria a GUI dizer "daemon offline?"."""
        fonte = (
            REPO / "src/hefesto_dualsense4unix/daemon/ipc_handlers.py"
        ).read_text(encoding="utf-8")
        assert '"status": "ok", "applied": applied' in fonte
