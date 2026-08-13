"""GUI-05 item 3 — banner "jogo sem wrapper" (honestidade do dedup).

FATO 0 do estudo 2026-07-18: o jogo rodou a sessão inteira SEM o
`hefesto-launch` e `dedup_ok: true` era falso-tranquilizante. O daemon (lane
própria) passa a expor `state_full.gamepad_emulation.wrapper_used`; a GUI
codifica CONTRA O CONTRATO, com state fake e sem importar nada do daemon:

- ``False``  → jogo aberto sem o wrapper → banner discreto pro leigo;
- ``True``   → jogo aberto PELO wrapper → sem banner;
- ``None``/ausente → sem jogo (ou daemon antigo sem o campo) → sem banner.

Só o ``False`` LITERAL acende — payload torto nunca vira alarme falso. A
função pura mora em `home_actions` (mesmo desenho do `vpad_degradation_text`)
e é consumida pelas abas Início (test_home_render_state) e Status (aqui).

TESTE-HONESTO-01/E3 (13/08/2026): a fiação das duas abas era medida por três
asserts de substring sobre o TEXTO-FONTE do método. Eles não proibiam bug
nenhum — proibiam RENOMEAR: trocar o nome da função pura, ou do refresh,
pintava três testes de vermelho sem mudar comportamento algum. Agora os dois
renders são EXECUTADOS e o despacho é observado por dublê (`MagicMock` com
`side_effect`, o padrão de `test_emulacao_no_jogo_teclado.py:458-459`).
"""
from __future__ import annotations

import sys
import types
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, call

import pytest

from hefesto_dualsense4unix.app.actions import home_actions
from hefesto_dualsense4unix.app.actions.home_actions import (
    WRAPPER_MISSING_TEXT,
    wrapper_banner_text,
)

# O dublê de widgets da aba Início já existe e é mantido pelos testes de
# render dela — copiá-lo aqui daria duas muralhas de GTK falso para manter em
# dia, e a segunda envelheceria calada.
from tests.unit.test_home_render_state import _FakeWidget, _HomeStub


def _state(wrapper_used: object = "__ausente__") -> dict[str, Any]:
    gamepad: dict[str, Any] = {
        "enabled": True,
        "flavor": "dualsense",
        "backend": "uhid",
    }
    if wrapper_used != "__ausente__":
        gamepad["wrapper_used"] = wrapper_used
    return {"connected": True, "gamepad_emulation": gamepad}


class TestDecisaoPura:
    def test_false_literal_acende(self) -> None:
        assert wrapper_banner_text(_state(False)) == WRAPPER_MISSING_TEXT

    def test_true_nao_acende(self) -> None:
        assert wrapper_banner_text(_state(True)) is None

    def test_none_sem_jogo_nao_acende(self) -> None:
        assert wrapper_banner_text(_state(None)) is None

    def test_campo_ausente_daemon_antigo_nao_acende(self) -> None:
        assert wrapper_banner_text(_state()) is None

    @pytest.mark.parametrize("torto", [0, "", "false", [], {}])
    def test_payload_torto_nao_vira_alarme_falso(self, torto: object) -> None:
        # 0/""/[] são falsy mas NÃO são o False literal do contrato.
        assert wrapper_banner_text(_state(torto)) is None

    def test_estado_offline_nao_acende(self) -> None:
        assert wrapper_banner_text(None) is None

    def test_estado_sem_gamepad_emulation_nao_acende(self) -> None:
        assert wrapper_banner_text({"connected": True}) is None
        assert wrapper_banner_text({"gamepad_emulation": "torto"}) is None

    def test_texto_e_pro_leigo_e_aponta_o_caminho(self) -> None:
        assert "hefesto-launch" in WRAPPER_MISSING_TEXT
        assert "duplicar" in WRAPPER_MISSING_TEXT
        assert "aba Sistema" in WRAPPER_MISSING_TEXT
        # Sem jargão que o estudo mandou esconder do leigo.
        for jargao in ("env", "vdf", "wrapper_used", "dedup"):
            assert jargao not in WRAPPER_MISSING_TEXT


# ---------------------------------------------------------------------------
# Aba Status — _refresh_wrapper_banner (widget fixo do Glade)
# ---------------------------------------------------------------------------


class _FakeBanner:
    def __init__(self) -> None:
        self.text = ""
        self.visible = True  # sobra visível: o refresh precisa apagar

    def set_text(self, text: str) -> None:
        self.text = text

    def set_visible(self, value: bool) -> None:
        self.visible = value


def _status_stub(banner: _FakeBanner | None) -> Any:
    from hefesto_dualsense4unix.app.actions.status_actions import (
        StatusActionsMixin,
    )

    class _Stub:
        _refresh_wrapper_banner = StatusActionsMixin._refresh_wrapper_banner

        def _get(self, widget_id: str) -> Any:
            return banner if widget_id == "status_wrapper_banner" else None

    return _Stub()


class TestRefreshNaAbaStatus:
    def test_false_pinta_e_mostra(self) -> None:
        banner = _FakeBanner()
        stub = _status_stub(banner)

        stub._refresh_wrapper_banner(_state(False))

        assert banner.visible is True
        assert banner.text == WRAPPER_MISSING_TEXT

    def test_true_esconde(self) -> None:
        banner = _FakeBanner()
        stub = _status_stub(banner)

        stub._refresh_wrapper_banner(_state(True))

        assert banner.visible is False

    def test_offline_esconde(self) -> None:
        banner = _FakeBanner()
        stub = _status_stub(banner)

        stub._refresh_wrapper_banner(None)

        assert banner.visible is False

    def test_widget_ausente_nao_explode(self) -> None:
        stub = _status_stub(None)
        stub._refresh_wrapper_banner(_state(False))  # não levanta


def _aba_status_falsa() -> Any:
    """A aba Status REAL com o toolkit desligado — só o despacho é gravado.

    Herda o mixin inteiro de propósito: um dublê que copiasse método por
    método não teria como reprovar a chamada que SUMIU do render, que é
    exatamente o que se mede aqui.
    """
    from hefesto_dualsense4unix.app.actions.status_actions import (
        StatusActionsMixin,
    )

    class _AbaFalsa(StatusActionsMixin):
        def __init__(self) -> None:
            self.despachos: list[Any] = []
            self._target_combo = None
            self._refresh_wrapper_banner = MagicMock(  # type: ignore[method-assign]
                side_effect=self.despachos.append
            )

        def _get(self, _widget_id: str) -> Any:
            # Sem Glade: todo widget é ausente, e a aba tolera isso por
            # desenho (`if widget is not None`) em todo lugar.
            return None

        @staticmethod
        def _popup_is_open() -> bool:
            # A guarda do popup tem medida própria e precisa de um GTK vivo
            # para responder; aqui ela só mascararia o que se quer ver.
            return False

    return _AbaFalsa()


class TestFiacao:
    """A fiação nas duas abas — por EXECUÇÃO do render (roda headless)."""

    def test_o_tick_lento_da_status_despacha_o_estado_para_o_banner(self) -> None:
        aba = _aba_status_falsa()
        estado = _state(False)

        aba._render_slow_state(estado)

        assert aba.despachos == [estado]

    def test_o_caminho_offline_da_status_apaga_o_banner(self) -> None:
        """Nunca banner de um estado morto: offline manda `None`, não o último
        estado vivo — é a diferença entre "sem jogo" e "não sei"."""
        aba = _aba_status_falsa()

        aba._render_offline()

        assert aba.despachos == [None]

    def test_render_home_consome_a_mesma_funcao_pura(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A aba Início pinta o que a FUNÇÃO PURA devolveu — sem segunda régua.

        O dublê entra pelo `__name__` da própria função: congelar o nome numa
        string é o que fazia este teste reprovar um `rename` que não muda
        comportamento nenhum (TESTE-HONESTO-01/E3).
        """
        repo = types.ModuleType("gi.repository")
        repo.Gtk = types.SimpleNamespace(  # type: ignore[attr-defined]
            Label=_FakeWidget,
            Box=_FakeWidget,
            Orientation=types.SimpleNamespace(VERTICAL=0, HORIZONTAL=1),
        )
        monkeypatch.setitem(sys.modules, "gi.repository", repo)
        espiao = MagicMock(return_value="AVISO-DO-WRAPPER")
        monkeypatch.setattr(home_actions, wrapper_banner_text.__name__, espiao)
        aba = _HomeStub()
        estado = _state(False)

        aba._render_home(estado)

        assert espiao.call_args_list == [call(estado)]
        assert aba._home_wrapper_banner.get_text() == "AVISO-DO-WRAPPER"
        assert aba._home_wrapper_banner.visible is True

    def test_glade_tem_o_widget_do_banner_da_status(self) -> None:
        glade = (
            Path(__file__).resolve().parents[2]
            / "src"
            / "hefesto_dualsense4unix"
            / "gui"
            / "main.glade"
        ).read_text(encoding="utf-8")
        assert 'id="status_wrapper_banner"' in glade
        bloco = glade.split('id="status_wrapper_banner"', 1)[1].split(
            "</object>", 1
        )[0]
        # invisível por padrão e imune ao show_all (como o banner do vpad).
        assert '<property name="visible">False</property>' in bloco
        assert '<property name="no-show-all">True</property>' in bloco
