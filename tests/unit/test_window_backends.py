"""Testes dos backends de detecção de janela.

- WaylandPortalBackend: degradação sem jeepney, caminho feliz com jeepney
  mockado, zero ThreadPoolExecutor/asyncio.run por chamada, propagação de
  timeout nativo (sprint AUDIT-FINDING-WAYLAND-PORTAL-PERF-01).
- XlibBackend: gate de foco X contra `_NET_ACTIVE_WINDOW` rançoso do
  cosmic-comp (UX-02, SPRINT-UX-AUTOSWITCH-01).
"""
from __future__ import annotations

import sys
import threading
import types
from typing import Any, ClassVar

import pytest

from hefesto_dualsense4unix.integrations.window_backends import (
    wayland_portal,
    xlib,
)

# ---------------------------------------------------------------------------
# Helpers — stub do pacote `jeepney` injetado via sys.modules
# ---------------------------------------------------------------------------


class _FakeReply:
    def __init__(self, body: tuple[Any, ...]) -> None:
        self.body = body


class _FakeConn:
    instances: ClassVar[list[_FakeConn]] = []

    def __init__(self, reply_body: tuple[Any, ...] | None = None,
                 raise_on_send: Exception | None = None) -> None:
        self.reply_body = reply_body or ("handle_xyz", {})
        self.raise_on_send = raise_on_send
        self.closed = False
        self.timeouts_received: list[float | None] = []
        _FakeConn.instances.append(self)

    def send_and_get_reply(self, msg: Any, *, timeout: float | None = None) -> _FakeReply:
        self.timeouts_received.append(timeout)
        if self.raise_on_send is not None:
            raise self.raise_on_send
        return _FakeReply(self.reply_body)

    def close(self) -> None:
        self.closed = True


def _install_fake_jeepney(
    monkeypatch: pytest.MonkeyPatch,
    *,
    reply_body: tuple[Any, ...] | None = None,
    raise_on_open: Exception | None = None,
    raise_on_send: Exception | None = None,
) -> list[_FakeConn]:
    """Injeta um pacote `jeepney` falso em sys.modules.

    Retorna a lista compartilhada de conexões criadas (para asserts).
    """
    _FakeConn.instances = []

    def _open_dbus_connection(bus: str = "SESSION") -> _FakeConn:
        if raise_on_open is not None:
            raise raise_on_open
        return _FakeConn(reply_body=reply_body, raise_on_send=raise_on_send)

    class _DBusAddress:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            self.args = args
            self.kwargs = kwargs

    def _new_method_call(*args: Any, **kwargs: Any) -> dict[str, Any]:
        return {"call": True, "args": args}

    jeepney_mod = types.ModuleType("jeepney")
    jeepney_mod.DBusAddress = _DBusAddress  # type: ignore[attr-defined]
    jeepney_mod.new_method_call = _new_method_call  # type: ignore[attr-defined]

    jeepney_io = types.ModuleType("jeepney.io")
    jeepney_io_blocking = types.ModuleType("jeepney.io.blocking")
    jeepney_io_blocking.open_dbus_connection = _open_dbus_connection  # type: ignore[attr-defined]

    monkeypatch.setitem(sys.modules, "jeepney", jeepney_mod)
    monkeypatch.setitem(sys.modules, "jeepney.io", jeepney_io)
    monkeypatch.setitem(sys.modules, "jeepney.io.blocking", jeepney_io_blocking)

    return _FakeConn.instances


# ---------------------------------------------------------------------------
# Testes
# ---------------------------------------------------------------------------


def test_sem_jeepney_retorna_none(monkeypatch: pytest.MonkeyPatch) -> None:
    """Sem jeepney instalado, get_active_window_info degrada para None."""
    # Garante que qualquer jeepney em cache seja invisível via ImportError.
    for name in ("jeepney", "jeepney.io", "jeepney.io.blocking"):
        monkeypatch.setitem(sys.modules, name, None)  # type: ignore[arg-type]

    backend = wayland_portal.WaylandPortalBackend()
    assert backend.get_active_window_info() is None


def test_caminho_feliz_com_jeepney_mockado(monkeypatch: pytest.MonkeyPatch) -> None:
    """Reply válido do portal deve produzir WindowInfo com app_id/title/pid."""
    _install_fake_jeepney(
        monkeypatch,
        reply_body=(
            "handle_xyz",
            {"app-id": "org.mozilla.Firefox", "title": "Mozilla Firefox", "pid": 1234},
        ),
    )
    backend = wayland_portal.WaylandPortalBackend()
    info = backend.get_active_window_info()
    assert info is not None
    assert info.app_id == "org.mozilla.Firefox"
    assert info.wm_class == "org.mozilla.Firefox"
    assert info.title == "Mozilla Firefox"
    assert info.pid == 1234


def test_reply_vazio_retorna_none(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_fake_jeepney(monkeypatch, reply_body=("handle_xyz", {}))
    backend = wayland_portal.WaylandPortalBackend()
    assert backend.get_active_window_info() is None


def test_reply_sem_segundo_elemento_retorna_none(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_fake_jeepney(monkeypatch, reply_body=("handle_xyz",))
    backend = wayland_portal.WaylandPortalBackend()
    assert backend.get_active_window_info() is None


def test_excecao_no_send_retorna_none(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_fake_jeepney(monkeypatch, raise_on_send=TimeoutError("portal timeout"))
    backend = wayland_portal.WaylandPortalBackend()
    assert backend.get_active_window_info() is None


def test_excecao_no_open_retorna_none(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_fake_jeepney(monkeypatch, raise_on_open=OSError("dbus down"))
    backend = wayland_portal.WaylandPortalBackend()
    assert backend.get_active_window_info() is None


def test_timeout_explicito_propagado_ao_jeepney(monkeypatch: pytest.MonkeyPatch) -> None:
    """Confirma que send_and_get_reply recebe timeout=_PORTAL_TIMEOUT_SECONDS."""
    conns = _install_fake_jeepney(
        monkeypatch,
        reply_body=("handle", {"app-id": "a", "title": "b", "pid": 1}),
    )
    backend = wayland_portal.WaylandPortalBackend()
    backend.get_active_window_info()
    assert len(conns) == 1
    assert conns[0].timeouts_received == [wayland_portal._PORTAL_TIMEOUT_SECONDS]


def test_conexao_sempre_fechada_mesmo_com_excecao(monkeypatch: pytest.MonkeyPatch) -> None:
    """finally em _try_jeepney garante conn.close() mesmo se send falhar."""
    conns = _install_fake_jeepney(monkeypatch, raise_on_send=RuntimeError("x"))
    backend = wayland_portal.WaylandPortalBackend()
    backend.get_active_window_info()
    assert len(conns) == 1
    assert conns[0].closed is True


def test_multiplas_chamadas_nao_criam_threadpoolexecutor(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Invariante central da sprint: nenhuma thread extra por chamada.

    Substitui `concurrent.futures.ThreadPoolExecutor` por um sentinela que
    marca a flag se for instanciado. Roda 20 chamadas de
    get_active_window_info e confirma que a flag permaneceu False.
    """
    import concurrent.futures as _cf

    pool_created = {"flag": False}

    original_pool = _cf.ThreadPoolExecutor

    class _SentinelPool(original_pool):  # type: ignore[misc,valid-type]
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            pool_created["flag"] = True
            super().__init__(*args, **kwargs)

    monkeypatch.setattr(_cf, "ThreadPoolExecutor", _SentinelPool)

    _install_fake_jeepney(
        monkeypatch,
        reply_body=("h", {"app-id": "x", "title": "y", "pid": 7}),
    )
    backend = wayland_portal.WaylandPortalBackend()
    for _ in range(20):
        backend.get_active_window_info()
    assert pool_created["flag"] is False


def test_multiplas_chamadas_nao_criam_threads(monkeypatch: pytest.MonkeyPatch) -> None:
    """Invariante: threading.active_count() estável entre chamadas."""
    _install_fake_jeepney(
        monkeypatch,
        reply_body=("h", {"app-id": "z", "title": "t", "pid": 9}),
    )
    backend = wayland_portal.WaylandPortalBackend()
    baseline = threading.active_count()
    for _ in range(30):
        backend.get_active_window_info()
    # Permite flutuação mínima (garbage collector, daemon threads do pytest).
    assert threading.active_count() <= baseline + 1


def test_nao_chama_asyncio_run(monkeypatch: pytest.MonkeyPatch) -> None:
    """Invariante: asyncio.run não é invocado pelo backend."""
    import asyncio

    called = {"count": 0}
    original_run = asyncio.run

    def _spy_run(*args: Any, **kwargs: Any) -> Any:
        called["count"] += 1
        return original_run(*args, **kwargs)

    monkeypatch.setattr(asyncio, "run", _spy_run)

    _install_fake_jeepney(
        monkeypatch,
        reply_body=("h", {"app-id": "q", "title": "r", "pid": 2}),
    )
    backend = wayland_portal.WaylandPortalBackend()
    for _ in range(5):
        backend.get_active_window_info()
    assert called["count"] == 0


def test_dbus_fast_foi_removido() -> None:
    """Regressão: _try_dbus_fast não deve existir mais no módulo."""
    assert not hasattr(wayland_portal, "_try_dbus_fast")


def test_handle_counter_incrementa_por_chamada(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_fake_jeepney(
        monkeypatch,
        reply_body=("h", {"app-id": "a", "title": "b", "pid": 1}),
    )
    backend = wayland_portal.WaylandPortalBackend()
    h1 = backend._next_handle()
    h2 = backend._next_handle()
    assert h1 != h2
    assert h1.startswith("hefesto_")
    assert h2.endswith("_2")


def test_parse_portal_result_sem_app_id() -> None:
    """Reply com title/pid mas sem app-id → wm_class='unknown'."""
    info = wayland_portal._parse_portal_result({"title": "Terminal", "pid": 42})
    assert info is not None
    assert info.wm_class == "unknown"
    assert info.app_id == ""
    assert info.title == "Terminal"
    assert info.pid == 42


def test_parse_portal_result_app_id_alternativo() -> None:
    """Aceita variante `app_id` (underscore) além de `app-id`."""
    info = wayland_portal._parse_portal_result({"app_id": "foo", "title": "bar"})
    assert info is not None
    assert info.app_id == "foo"
    assert info.wm_class == "foo"


def test_parse_portal_result_vazio() -> None:
    assert wayland_portal._parse_portal_result({}) is None


# ---------------------------------------------------------------------------
# BUG-COSMIC-PORTAL-UNSUPPORTED-01 (v2.4.0, re-portado v3.1.0)
# Threshold de 3 falhas → portal entra em modo "unsupported" silencioso.
# ---------------------------------------------------------------------------


def test_threshold_para_de_chamar_dbus_apos_3_falhas(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Após 3 falhas consecutivas, backend para de consultar D-Bus."""
    conns = _install_fake_jeepney(monkeypatch, raise_on_send=RuntimeError("no method"))
    backend = wayland_portal.WaylandPortalBackend()

    for _ in range(3):
        assert backend.get_active_window_info() is None
    assert len(conns) == 3
    assert backend._consecutive_failures == 3

    for _ in range(5):
        assert backend.get_active_window_info() is None
    assert len(conns) == 3


def test_threshold_warning_emitido_uma_vez(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Warning de unsupported deve ser logado apenas 1x na transição."""
    _install_fake_jeepney(monkeypatch, raise_on_send=RuntimeError("no method"))
    backend = wayland_portal.WaylandPortalBackend()

    warnings: list[dict[str, Any]] = []
    monkeypatch.setattr(
        wayland_portal.logger,
        "warning",
        lambda evt, **kw: warnings.append({"evt": evt, **kw}),
    )

    for _ in range(10):
        backend.get_active_window_info()

    unsupported = [w for w in warnings if w["evt"] == "wayland_portal_unsupported"]
    assert len(unsupported) == 1
    assert backend._unsupported_warned is True


def test_threshold_reset_apos_resposta_ok(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Resposta válida reseta o contador e o flag de warning."""
    backend = wayland_portal.WaylandPortalBackend()
    backend._consecutive_failures = 2
    backend._unsupported_warned = True

    _install_fake_jeepney(
        monkeypatch,
        reply_body=("handle", {"app-id": "alpha", "title": "Alpha", "pid": 5}),
    )

    info = backend.get_active_window_info()
    assert info is not None
    assert backend._consecutive_failures == 0
    assert backend._unsupported_warned is False


def test_compositor_hint_usa_xdg_current_desktop(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("XDG_CURRENT_DESKTOP", "COSMIC")
    backend = wayland_portal.WaylandPortalBackend()
    assert backend._compositor_hint() == "COSMIC"


def test_compositor_hint_fallback_session_desktop(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("XDG_CURRENT_DESKTOP", raising=False)
    monkeypatch.setenv("XDG_SESSION_DESKTOP", "sway")
    backend = wayland_portal.WaylandPortalBackend()
    assert backend._compositor_hint() == "sway"


def test_compositor_hint_unknown_sem_envs(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("XDG_CURRENT_DESKTOP", raising=False)
    monkeypatch.delenv("XDG_SESSION_DESKTOP", raising=False)
    backend = wayland_portal.WaylandPortalBackend()
    assert backend._compositor_hint() == "unknown"


# ---------------------------------------------------------------------------
# UX-02 (SPRINT-UX-AUTOSWITCH-01) — gate de foco X no XlibBackend.
#
# Provado ao vivo (2x, independente) na sessão COSMIC: `_NET_ACTIVE_WINDOW`
# aponta janela X MORTA (BadWindow ao consultar WM_CLASS) enquanto
# `get_input_focus().focus == 0` — o cosmic-comp não limpa a propriedade
# quando o foco vai para janela Wayland nativa nem quando a janela X morre.
# O gate consulta o foco ANTES de confiar na propriedade; sem foco X
# (None=0 / PointerRoot=1) retorna None e a histerese UX-01 segura o perfil.
# ---------------------------------------------------------------------------


class _FakeProperty:
    def __init__(self, value: list[int]) -> None:
        self.value = value


class _FakeGameWin:
    """Janela de jogo VIVA apontada pelo `_NET_ACTIVE_WINDOW` rançoso."""

    def get_wm_class(self) -> tuple[str, str]:
        return ("sackboy", "steam_app_1599660")

    def get_wm_name(self) -> str:
        return "Sackboy: A Big Adventure"

    def get_full_property(self, atom: int, _type: int) -> _FakeProperty:
        return _FakeProperty([4242])


class _FakeRoot:
    def get_full_property(self, atom: int, _type: int) -> _FakeProperty:
        # _NET_ACTIVE_WINDOW → id da janela de jogo (0x1200007, o id rançoso
        # medido ao vivo).
        return _FakeProperty([0x1200007])


class _FakeScreen:
    root = _FakeRoot()


class _FakeFocusReply:
    def __init__(self, focus: object) -> None:
        self.focus = focus


class _FakeWindowHandle:
    """python-xlib devolve `focus` como objeto Window com `.id` no caminho
    feliz — o gate precisa normalizar antes de comparar com {0, 1}."""

    def __init__(self, wid: int) -> None:
        self.id = wid


class _FakeXDisplay:
    def __init__(self, focus: object) -> None:
        self._focus = focus

    def screen(self) -> _FakeScreen:
        return _FakeScreen()

    def intern_atom(self, name: str) -> int:
        return 1

    def create_resource_object(self, kind: str, wid: int) -> _FakeGameWin:
        assert wid == 0x1200007
        return _FakeGameWin()

    def get_input_focus(self) -> _FakeFocusReply:
        return _FakeFocusReply(self._focus)


def _xlib_backend_with(display: _FakeXDisplay) -> xlib.XlibBackend:
    """XlibBackend já 'conectado' ao display fake (pula _ensure_connected)."""
    backend = xlib.XlibBackend()
    backend._display = display
    backend._connected = True
    backend._init_attempted = True
    return backend


def test_focus_gate_focus_zero_int_retorna_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """foco == 0 (int, X.NONE) + _NET_ACTIVE_WINDOW apontando janela VIVA de
    jogo → None (a propriedade é rançosa; quem decide é o foco)."""
    monkeypatch.setattr(xlib, "_exe_basename_from_pid", lambda pid: "sackboy-bin")
    backend = _xlib_backend_with(_FakeXDisplay(focus=0))
    assert backend.get_active_window_info() is None


def test_focus_gate_focus_zero_como_objeto_window_retorna_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Mesmo gate com `focus` vindo como objeto Window de id 0 — a
    normalização via getattr(focus, 'id', focus) cobre os DOIS tipos."""
    monkeypatch.setattr(xlib, "_exe_basename_from_pid", lambda pid: "sackboy-bin")
    backend = _xlib_backend_with(_FakeXDisplay(focus=_FakeWindowHandle(0)))
    assert backend.get_active_window_info() is None


def test_focus_gate_pointer_root_retorna_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """PointerRoot (1) também é tratado como sem-foco. Tradeoff DECLARADO da
    UX-02: cega sessões X11 legadas focus-follows-mouse — intencional, o alvo
    é COSMIC; este teste fixa o comportamento de propósito."""
    monkeypatch.setattr(xlib, "_exe_basename_from_pid", lambda pid: "sackboy-bin")
    backend = _xlib_backend_with(_FakeXDisplay(focus=1))
    assert backend.get_active_window_info() is None


def test_focus_valido_mantem_comportamento_atual(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Foco numa janela X válida → caminho feliz intocado: a leitura via
    _NET_ACTIVE_WINDOW continua exatamente como antes do gate."""
    monkeypatch.setattr(xlib, "_exe_basename_from_pid", lambda pid: "sackboy-bin")
    backend = _xlib_backend_with(
        _FakeXDisplay(focus=_FakeWindowHandle(0x1200007))
    )
    info = backend.get_active_window_info()
    assert info is not None
    assert info.wm_class == "steam_app_1599660"
    assert info.title == "Sackboy: A Big Adventure"
    assert info.pid == 4242
    assert info.exe_basename == "sackboy-bin"


def test_focus_gate_loga_uma_vez_por_episodio(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """O gate roda no poll de 2 Hz do autoswitch — loga 1x por episódio
    (sem flood no journal) e reabre quando o foco volta a ser válido."""
    monkeypatch.setattr(xlib, "_exe_basename_from_pid", lambda pid: "sackboy-bin")
    eventos: list[str] = []
    monkeypatch.setattr(
        xlib.logger,
        "info",
        lambda evt, **kw: eventos.append(evt),
    )

    backend = _xlib_backend_with(_FakeXDisplay(focus=0))
    for _ in range(4):  # episódio 1: 4 ticks sem foco → 1 log
        backend.get_active_window_info()
    backend._display = _FakeXDisplay(focus=_FakeWindowHandle(0x1200007))
    backend.get_active_window_info()  # foco válido fecha o episódio
    backend._display = _FakeXDisplay(focus=0)
    backend.get_active_window_info()  # episódio 2 → mais 1 log

    assert eventos.count("x11_focus_gate_no_x_focus") == 2


# ---------------------------------------------------------------------------
# Reconexão do XlibBackend (achado MED da revisão adversarial da Fase 2).
#
# O XWayland morre/reinicia (crash de jogo + NVIDIA; o cosmic-comp respawna) e
# o Display do python-xlib fica MORTO: antes, `_init_attempted` congelava a
# primeira conexão para sempre → todo tick virava 'unknown' e a histerese
# UX-01 retinha o perfil de jogo INDEFINIDAMENTE (as rampas de saída — Steam e
# GUI, ambas XWayland — dependem desta mesma conexão). Agora o erro de conexão
# derruba o Display e `_ensure_connected` tenta um novo.
# ---------------------------------------------------------------------------


class _DisplayMorto:
    """Display cuja conexão morreu: toda consulta levanta ConnectionClosedError."""

    def __init__(self, exc: Exception | None = None) -> None:
        from Xlib.error import ConnectionClosedError

        self._exc = exc or ConnectionClosedError("server")
        self.fechado = False

    def get_input_focus(self) -> Any:
        raise self._exc

    def close(self) -> None:
        self.fechado = True


def test_conexao_morta_derruba_o_display_na_primeira_falha(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    backend = _xlib_backend_with(_FakeXDisplay(focus=0))
    morto = _DisplayMorto()
    backend._display = morto

    assert backend.get_active_window_info() is None
    # Erro de CONEXÃO reconhecido → estado zerado já na 1ª falha.
    assert backend._connected is False
    assert backend._init_attempted is False
    assert backend._display is None
    assert morto.fechado is True


def test_erro_pontual_nao_custa_a_conexao_viva() -> None:
    """Um erro não-reconhecido isolado (BadWindow e afins) NÃO derruba o
    Display — só N falhas consecutivas."""
    backend = _xlib_backend_with(_FakeXDisplay(focus=0))
    backend._display = _DisplayMorto(exc=RuntimeError("BadWindow pontual"))

    assert backend.get_active_window_info() is None
    assert backend._connected is True
    assert backend._init_attempted is True


def test_falhas_consecutivas_derrubam_o_display() -> None:
    backend = _xlib_backend_with(_FakeXDisplay(focus=0))
    backend._display = _DisplayMorto(exc=RuntimeError("erro estranho"))

    for _ in range(xlib._MAX_QUERY_FAILURES):
        assert backend.get_active_window_info() is None

    assert backend._connected is False
    assert backend._init_attempted is False


def test_leitura_util_zera_o_contador_de_falhas() -> None:
    """Falha pontual intercalada com leitura boa nunca acumula até o drop."""
    backend = _xlib_backend_with(_FakeXDisplay(focus=_FakeWindowHandle(0x1200007)))
    vivo = backend._display

    for _ in range(xlib._MAX_QUERY_FAILURES - 1):
        backend._display = _DisplayMorto(exc=RuntimeError("pontual"))
        assert backend.get_active_window_info() is None
        backend._display = vivo
        assert backend.get_active_window_info() is not None

    assert backend._connected is True
    assert backend._query_failures == 0


def test_apos_o_drop_uma_conexao_nova_volta_a_ler(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """O ciclo completo do achado: conexão morre → drop → o tick seguinte
    reconecta (sem esperar backoff — o carimbo é zerado no drop) e a leitura
    útil volta, destravando a histerese UX-01."""
    monkeypatch.setattr(xlib, "_exe_basename_from_pid", lambda pid: "sackboy-bin")
    monkeypatch.setenv("DISPLAY", ":1")
    backend = _xlib_backend_with(_FakeXDisplay(focus=0))
    backend._display = _DisplayMorto()
    assert backend.get_active_window_info() is None  # morre + drop

    import Xlib.display as _xdisplay

    monkeypatch.setattr(
        _xdisplay,
        "Display",
        lambda *a, **kw: _FakeXDisplay(focus=_FakeWindowHandle(0x1200007)),
    )
    info = backend.get_active_window_info()
    assert info is not None
    assert info.wm_class == "steam_app_1599660"


def test_reconexao_falhada_respeita_o_backoff(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Com o X ainda fora do ar, a reconexão tenta 1x e respeita o backoff —
    nada de connect bloqueante a 2 Hz no tick do autoswitch."""
    monkeypatch.setenv("DISPLAY", ":1")
    backend = _xlib_backend_with(_FakeXDisplay(focus=0))
    backend._display = _DisplayMorto()
    assert backend.get_active_window_info() is None  # morre + drop

    tentativas: list[bool] = []

    def _connect_falha(*a: Any, **kw: Any) -> Any:
        tentativas.append(True)
        raise OSError("X ainda fora do ar")

    import Xlib.display as _xdisplay

    monkeypatch.setattr(_xdisplay, "Display", _connect_falha)
    for _ in range(5):
        assert backend.get_active_window_info() is None

    assert len(tentativas) == 1  # 1 connect; o resto caiu no backoff


def test_log_de_reconexao_e_um_por_episodio(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DISPLAY", ":1")
    eventos: list[str] = []
    monkeypatch.setattr(
        xlib.logger, "info", lambda evt, **kw: eventos.append(evt)
    )
    backend = _xlib_backend_with(_FakeXDisplay(focus=0))

    import Xlib.display as _xdisplay

    def _connect_falha(*a: Any, **kw: Any) -> Any:
        raise OSError("X fora do ar")

    monkeypatch.setattr(_xdisplay, "Display", _connect_falha)
    backend._display = _DisplayMorto()
    backend.get_active_window_info()  # drop (loga 1x)
    backend.get_active_window_info()  # reconexão falha; ainda o mesmo episódio

    assert eventos.count("x11_reconnect_attempt") == 1
