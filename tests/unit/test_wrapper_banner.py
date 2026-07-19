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
"""
from __future__ import annotations

import inspect
from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.app.actions.home_actions import (
    WRAPPER_MISSING_TEXT,
    wrapper_banner_text,
)


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


class TestFiacao:
    """A fiação nas duas abas, por fonte (roda headless)."""

    def test_render_slow_state_da_status_chama_o_refresh(self) -> None:
        from hefesto_dualsense4unix.app.actions.status_actions import (
            StatusActionsMixin,
        )

        src = inspect.getsource(StatusActionsMixin._render_slow_state)
        assert "_refresh_wrapper_banner(state)" in src
        # e o caminho offline apaga (nunca banner de um estado morto):
        src_off = inspect.getsource(StatusActionsMixin)
        assert "_refresh_wrapper_banner(None)" in src_off

    def test_render_home_consome_a_mesma_funcao_pura(self) -> None:
        from hefesto_dualsense4unix.app.actions.home_actions import (
            HomeActionsMixin,
        )

        src = inspect.getsource(HomeActionsMixin._render_home)
        assert "wrapper_banner_text(state)" in src
        assert "_home_wrapper_banner" in src

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
