"""R-17 e R-18 (auditoria 23/07) — alvo certo e sucesso honesto.

R-17: o "Apagar" da aba Lightbar era o ÚNICO output da GUI que não mandava o
`uniq` do controle selecionado — o "Aplicar" logo ao lado manda. Sem ele o
pedido caía na rota GLOBAL (broadcast) que o PERFIL-05 abandonou: apagava a
lightbar dos QUATRO quando ela pediu para apagar a de UM, e ainda derrubava o
override por-MAC dos outros.

R-18: `profile.apply_draft` responde `status:"ok"` SEMPRE — inclusive quando o
applier não aplicou seção nenhuma. A GUI lia só o status e toastava "aplicado"
para um no-op. A resposta já carregava `applied`, e ninguém lia.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

REPO = Path(__file__).resolve().parents[2]


class TestR17ApagarMandaOUniq:
    def test_o_handler_passa_o_alvo(self) -> None:
        fonte = (
            REPO / "src/hefesto_dualsense4unix/app/actions/lightbar_actions.py"
        ).read_text(encoding="utf-8")
        assert "led_set((0, 0, 0), uniq=self._edit_uniq())" in fonte, (
            "apagar sem `uniq` vira broadcast: apaga a lightbar dos quatro "
            "quando ela pediu para apagar a de um"
        )

    def test_led_set_aceita_uniq(self) -> None:
        """A rota por-MAC precisa existir do outro lado (PERFIL-05)."""
        import inspect

        from hefesto_dualsense4unix.app import ipc_bridge

        assert "uniq" in inspect.signature(ipc_bridge.led_set).parameters


class TestR18SucessoHonesto:
    @staticmethod
    def _apply(monkeypatch: pytest.MonkeyPatch, resposta: Any) -> bool:
        from hefesto_dualsense4unix.app import ipc_bridge

        monkeypatch.setattr(
            ipc_bridge, "_safe_call", lambda *a, **k: (True, resposta)
        )
        return ipc_bridge.apply_draft({"leds": {"lightbar_rgb": [1, 2, 3]}})

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
        """Trocar para "partial"/"failed" faria a GUI dizer "daemon offline?".

        Essa mensagem mandaria a usuária caçar o problema no lugar errado — a
        honestidade entra pelo campo `applied`, não pelo status.
        """
        fonte = (
            REPO / "src/hefesto_dualsense4unix/daemon/ipc_handlers.py"
        ).read_text(encoding="utf-8")
        assert '"status": "ok", "applied": applied' in fonte
