"""UX-03 (SPRINT-UX-AUTOSWITCH-01) — banner de degradação do vpad na GUI.

O `state_full.gamepad_emulation` expõe `backend` desde a Fase 1 e ninguém
além do botão de copiar consumia: quando o vpad caía em uinput (EIO de BT no
blueprint, uhid indisponível) a usuária concluía que "o hefesto não funciona".
Aqui fixamos:

1. A função pura `vpad_degradation_text` — a tabela-verdade EXATA do critério
   de aceite do doc: só (dualsense, uinput, gamepad) acende; backend
   ausente/"" é transitório real e NÃO acende (sem alarme falso).
2. O texto honesto — a revisão adversarial REFUTOU "reconecte o controle"
   (a promoção uinput→uhid só roda no boot; reconectar não cura): o conselho
   é reiniciar o Hefesto na aba Sistema.
3. As duas abas consumidoras: Início (`_render_home`) e Status
   (`_render_slow_state`/`_render_offline`) mostram o banner no estado
   degradado e o escondem no saudável/offline.

Herméticos: Gtk fake em `sys.modules` (padrão de `test_home_render_state`) e
stubs gi para o import do `status_actions` (padrão GATE-SKIP-MASK-01 de
`test_status_actions_reconnect`).
"""
from __future__ import annotations

import sys
import types
from types import SimpleNamespace
from typing import Any

import pytest


def _install_gi_stubs() -> None:
    """Instala stubs mínimos de gi.repository para rodar sem GTK real."""
    # GATE-SKIP-MASK-01: com o PyGObject real disponível, NÃO instala stubs —
    # poluir sys.modules["gi"] na coleta fazia testes de GUI pularem como
    # "ambiente sem GTK" mesmo com o GTK real presente.
    existente = sys.modules.get("gi")
    if existente is None or getattr(existente, "__spec__", None) is not None:
        try:
            import gi

            gi.require_version("Gtk", "3.0")
            from gi.repository import Gtk  # noqa: F401

            return
        except Exception:  # pragma: no cover — ambientes sem GTK
            pass

    gi_mod = types.ModuleType("gi")

    def _require_version(_name: str, _ver: str) -> None:
        return None

    gi_mod.require_version = _require_version  # type: ignore[attr-defined]
    repo_mod = types.ModuleType("gi.repository")
    gtk_mod = types.ModuleType("gi.repository.Gtk")
    glib_mod = types.ModuleType("gi.repository.GLib")

    gtk_mod.Builder = object  # type: ignore[attr-defined]
    gtk_mod.DrawingArea = object  # type: ignore[attr-defined]
    gtk_mod.Box = object  # type: ignore[attr-defined]
    gtk_mod.Grid = object  # type: ignore[attr-defined]
    gtk_mod.Label = object  # type: ignore[attr-defined]
    gtk_mod.Align = type("Align", (), {"CENTER": 0})  # type: ignore[attr-defined]
    glib_mod.timeout_add = lambda *_a, **_kw: 0  # type: ignore[attr-defined]
    glib_mod.timeout_add_seconds = lambda *_a, **_kw: 0  # type: ignore[attr-defined]
    glib_mod.idle_add = lambda *_a, **_kw: 0  # type: ignore[attr-defined]
    repo_mod.Gtk = gtk_mod  # type: ignore[attr-defined]
    repo_mod.GLib = glib_mod  # type: ignore[attr-defined]

    sys.modules["gi"] = gi_mod
    sys.modules["gi.repository"] = repo_mod
    sys.modules["gi.repository.Gtk"] = gtk_mod
    sys.modules["gi.repository.GLib"] = glib_mod


_install_gi_stubs()

from hefesto_dualsense4unix.app.actions.home_actions import (  # noqa: E402
    NATIVE_BT_FRAGIL_TEXT,
    VPAD_COOP_DEGRADED_TEXT,
    VPAD_DEGRADED_TEXT,
    HomeActionsMixin,
    vpad_degradation_text,
)
from hefesto_dualsense4unix.app.actions.status_actions import (  # noqa: E402
    StatusActionsMixin,
)


def _state(
    *,
    enabled: bool = True,
    flavor: str = "dualsense",
    backend: str | None = "uinput",
    native_mode: bool = False,
) -> dict[str, Any]:
    gamepad: dict[str, Any] = {"enabled": enabled, "flavor": flavor}
    if backend is not None:
        gamepad["backend"] = backend
    return {
        "gamepad_emulation": gamepad,
        "native_mode": native_mode,
        "controllers": [],
    }


# ---------------------------------------------------------------------------
# Função pura — a tabela-verdade do critério de aceite do doc
# ---------------------------------------------------------------------------


class TestVpadDegradationText:
    def test_dualsense_uinput_gamepad_acende(self) -> None:
        """(dualsense, uinput, gamepad) → o texto de degradação, verbatim."""
        assert vpad_degradation_text(_state()) == VPAD_DEGRADED_TEXT

    def test_dualsense_uhid_gamepad_nao_acende(self) -> None:
        """(dualsense, uhid, gamepad) → vpad saudável, nada a avisar."""
        assert vpad_degradation_text(_state(backend="uhid")) is None

    def test_xbox_uinput_gamepad_nao_acende(self) -> None:
        """(xbox, uinput, gamepad) → uinput é o desenho normal da máscara Xbox."""
        assert vpad_degradation_text(_state(flavor="xbox")) is None

    def test_modo_desktop_nao_acende(self) -> None:
        """(dualsense, uinput, desktop) → sem emulação não há vpad a avaliar."""
        assert vpad_degradation_text(_state(enabled=False)) is None

    def test_modo_nativo_nao_acende(self) -> None:
        """Nativo vence o gamepad no mode_of_state — e não tem vpad."""
        assert vpad_degradation_text(_state(native_mode=True)) is None

    def test_backend_vazio_e_transitorio_sem_alarme_falso(self) -> None:
        """backend "" = vpad ainda subindo (device None) — NUNCA alarme falso."""
        assert vpad_degradation_text(_state(backend="")) is None

    def test_backend_ausente_e_transitorio_sem_alarme_falso(self) -> None:
        """O ipc_handlers só emite a chave com device vivo — ausência é normal."""
        assert vpad_degradation_text(_state(backend=None)) is None

    def test_payload_degenerado_nao_explode(self) -> None:
        assert vpad_degradation_text(None) is None
        assert vpad_degradation_text({}) is None
        assert vpad_degradation_text(
            {"gamepad_emulation": "lixo", "native_mode": False}
        ) is None

    def test_texto_honesto_sem_o_conselho_refutado(self) -> None:
        """"Reconecte o controle" foi REFUTADO: reconectar não promove a uhid.

        O conselho que funciona no código atual é reiniciar o Hefesto (a
        promoção só roda no boot do daemon) — e o texto diz onde: aba Sistema.
        """
        texto = VPAD_DEGRADED_TEXT
        assert "aba Sistema" in texto
        assert "modo simples" in texto
        assert "vibração" in texto
        assert "econecte" not in texto  # cobre "Reconecte" e "reconecte"


class TestGuardDedup06NoBanner:
    """DEDUP-06: o banner também fala pelos jogadores do co-op e pelo estado
    BT+Nativo — a dedup quebrada nunca mais é silenciosa (P0 do sprint doc)."""

    def _com_dedup(
        self, *, dedup_ok: bool, motivo: str | None, backend: str = "uhid"
    ) -> dict[str, Any]:
        state = _state(backend=backend)
        state["gamepad_emulation"]["dedup_ok"] = dedup_ok
        if motivo is not None:
            state["gamepad_emulation"]["dedup_motivo"] = motivo
        return state

    def test_jogador_do_coop_degradado_acende_mesmo_com_p1_saudavel(self) -> None:
        state = self._com_dedup(dedup_ok=False, motivo="jogador_2_uinput")
        assert vpad_degradation_text(state) == VPAD_COOP_DEGRADED_TEXT

    def test_dedup_ok_true_nao_acende(self) -> None:
        state = self._com_dedup(dedup_ok=True, motivo=None)
        assert vpad_degradation_text(state) is None

    def test_vpad_ausente_e_transitorio_sem_alarme_falso(self) -> None:
        """`vpad_ausente` acontece por instantes no boot (device None com a
        emulação ligada) — o banner não pode piscar alarme falso; quem fala
        desse estado é o doctor (rodado à mão, sem flicker)."""
        state = self._com_dedup(dedup_ok=False, motivo="vpad_ausente")
        assert vpad_degradation_text(state) is None

    def test_primario_degradado_vence_o_aviso_de_coop(self) -> None:
        """P1 uinput + P2 uinput: o texto do primário é o mais acionável."""
        state = self._com_dedup(
            dedup_ok=False, motivo="sem_uhid, jogador_2_uinput", backend="uinput"
        )
        assert vpad_degradation_text(state) == VPAD_DEGRADED_TEXT

    def test_bt_mais_nativo_tem_aviso_proprio(self) -> None:
        """Achado novo da revisão: físico BT + Modo Nativo = o SDL pode não
        enxergar o controle nem sem launch option — aviso específico."""
        state = _state(native_mode=True)
        state["native_bt_fragil"] = True
        assert vpad_degradation_text(state) == NATIVE_BT_FRAGIL_TEXT

    def test_nativo_por_usb_nao_alarma(self) -> None:
        state = _state(native_mode=True)
        state["native_bt_fragil"] = False
        assert vpad_degradation_text(state) is None

    def test_texto_do_bt_nativo_da_a_saida(self) -> None:
        assert "USB" in NATIVE_BT_FRAGIL_TEXT
        assert "Bluetooth" in NATIVE_BT_FRAGIL_TEXT

    def test_texto_do_coop_diz_o_risco_e_a_saida(self) -> None:
        assert "aba Sistema" in VPAD_COOP_DEGRADED_TEXT
        assert "jogador" in VPAD_COOP_DEGRADED_TEXT


# ---------------------------------------------------------------------------
# Aba Início — _render_home liga/desliga o banner
# ---------------------------------------------------------------------------


class _StyleCtx:
    def add_class(self, _name: str) -> None:
        pass


class _FakeWidget:
    def __init__(self, label: str | None = None, **_kwargs: object) -> None:
        self.label = label
        self.children: list[_FakeWidget] = []
        self.visible = True

    def get_style_context(self) -> _StyleCtx:
        return _StyleCtx()

    def set_xalign(self, _value: float) -> None:
        pass

    def set_margin_end(self, _value: int) -> None:
        pass

    def set_markup(self, markup: str) -> None:
        self.label = markup

    def set_text(self, text: str) -> None:
        self.label = text

    def set_sensitive(self, _value: bool) -> None:
        pass

    def set_visible(self, value: bool) -> None:
        self.visible = value

    def set_no_show_all(self, _value: bool) -> None:
        pass

    def set_active_id(self, _value: str) -> None:
        pass

    def pack_start(self, child: _FakeWidget, *_args: object) -> None:
        self.children.append(child)

    def get_children(self) -> list[_FakeWidget]:
        return list(self.children)

    def remove(self, child: _FakeWidget) -> None:
        self.children.remove(child)

    def show_all(self) -> None:
        pass


class _HomeStub:
    _render_home = HomeActionsMixin._render_home
    _render_home_controllers = HomeActionsMixin._render_home_controllers

    def __init__(self) -> None:
        self._home_installed = True
        self._home_inflight = False
        self._home_guard = False
        self._home_controllers_box = _FakeWidget()
        self._home_mode_selector = _FakeWidget()
        self._home_players_hint = _FakeWidget()
        self._home_flavor_selector = _FakeWidget()
        self._home_mode_desc = _FakeWidget()
        self._home_origin_label = _FakeWidget()
        self._home_session_label = _FakeWidget()
        self._home_gamepad_opts = _FakeWidget()
        self._home_vpad_banner = _FakeWidget()
        # Estado inicial do widget real: invisível até o render decidir.
        self._home_vpad_banner.visible = False


@pytest.fixture()
def fake_gtk(monkeypatch: pytest.MonkeyPatch) -> None:
    repo = types.ModuleType("gi.repository")
    repo.Gtk = SimpleNamespace(  # type: ignore[attr-defined]
        Label=_FakeWidget,
        Box=_FakeWidget,
        Orientation=SimpleNamespace(VERTICAL=0, HORIZONTAL=1),
    )
    monkeypatch.setitem(sys.modules, "gi.repository", repo)


class TestBannerAbaInicio:
    def test_estado_degradado_mostra_banner_com_o_texto_certo(
        self, fake_gtk: None
    ) -> None:
        host = _HomeStub()

        host._render_home(_state())

        assert host._home_vpad_banner.visible is True
        assert host._home_vpad_banner.label == VPAD_DEGRADED_TEXT

    def test_estado_saudavel_uhid_esconde_banner(self, fake_gtk: None) -> None:
        host = _HomeStub()
        host._home_vpad_banner.visible = True  # estava degradado antes

        host._render_home(_state(backend="uhid"))

        assert host._home_vpad_banner.visible is False

    def test_backend_transitorio_nao_acende(self, fake_gtk: None) -> None:
        host = _HomeStub()

        host._render_home(_state(backend=None))

        assert host._home_vpad_banner.visible is False

    def test_offline_esconde_banner(self, fake_gtk: None) -> None:
        host = _HomeStub()
        host._home_vpad_banner.visible = True  # estava degradado antes

        host._render_home(None)

        assert host._home_vpad_banner.visible is False


# ---------------------------------------------------------------------------
# Aba Status — _render_slow_state/_render_offline ligam/desligam o banner
# ---------------------------------------------------------------------------


class _FakeLabel:
    def __init__(self) -> None:
        self.text: str | None = None
        self.markup: str | None = None
        self.visible: bool | None = None

    def set_text(self, text: str) -> None:
        self.text = text

    def set_markup(self, markup: str) -> None:
        self.markup = markup

    def set_visible(self, value: bool) -> None:
        self.visible = value

    def set_fraction(self, _frac: float) -> None:
        pass


class _FakeBuilder:
    def __init__(self) -> None:
        self._widgets: dict[str, Any] = {}

    def get_object(self, wid: str) -> Any:
        if wid not in self._widgets:
            self._widgets[wid] = _FakeLabel()
        return self._widgets[wid]


class _StatusHost(StatusActionsMixin):
    def __init__(self) -> None:
        self.builder = _FakeBuilder()


@pytest.fixture()
def status_host(monkeypatch: pytest.MonkeyPatch) -> _StatusHost:
    # O render lento consulta o grab global do Gtk (BUG-COMBO-POPUP-FLICKER-02);
    # aqui não há popup nenhum — força o caminho de render.
    monkeypatch.setattr(
        StatusActionsMixin, "_popup_is_open", staticmethod(lambda: False)
    )
    return _StatusHost()


class TestBannerAbaStatus:
    def test_estado_degradado_mostra_banner_com_o_texto_certo(
        self, status_host: _StatusHost
    ) -> None:
        state = _state()
        state.update({"connected": True, "transport": "usb"})

        status_host._render_slow_state(state)

        banner = status_host.builder.get_object("status_vpad_banner")
        assert banner.visible is True
        assert banner.text == VPAD_DEGRADED_TEXT

    def test_estado_saudavel_uhid_esconde_banner(
        self, status_host: _StatusHost
    ) -> None:
        banner = status_host.builder.get_object("status_vpad_banner")
        banner.visible = True  # estava degradado antes

        state = _state(backend="uhid")
        state.update({"connected": True, "transport": "usb"})
        status_host._render_slow_state(state)

        assert banner.visible is False

    def test_offline_esconde_banner(self, status_host: _StatusHost) -> None:
        banner = status_host.builder.get_object("status_vpad_banner")
        banner.visible = True  # estava degradado antes

        status_host._render_offline()

        assert banner.visible is False
