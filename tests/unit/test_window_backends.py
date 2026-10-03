"""Testes dos backends de detecção de janela."""
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
    """Injeta um pacote `jeepney` falso em sys.modules."""
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


def test_sem_jeepney_retorna_none(monkeypatch: pytest.MonkeyPatch) -> None:
    """Sem jeepney instalado, get_active_window_info degrada para None."""
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
    """Invariante central da sprint: nenhuma thread extra por chamada."""
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
        return _FakeProperty([0x1200007])


class _FakeScreen:
    root = _FakeRoot()


class _FakeFocusReply:
    def __init__(self, focus: object) -> None:
        self.focus = focus


class _FakeWindowHandle:
    """python-xlib devolve `focus` como objeto Window com `.id` no caminho"""

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
    """foco == 0 (int, X.NONE) + _NET_ACTIVE_WINDOW apontando janela VIVA de"""
    monkeypatch.setattr(xlib, "_exe_basename_from_pid", lambda pid: "sackboy-bin")
    backend = _xlib_backend_with(_FakeXDisplay(focus=0))
    assert backend.get_active_window_info() is None


def test_focus_gate_focus_zero_como_objeto_window_retorna_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Mesmo gate com `focus` vindo como objeto Window de id 0 — a"""
    monkeypatch.setattr(xlib, "_exe_basename_from_pid", lambda pid: "sackboy-bin")
    backend = _xlib_backend_with(_FakeXDisplay(focus=_FakeWindowHandle(0)))
    assert backend.get_active_window_info() is None


def test_focus_gate_pointer_root_retorna_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """PointerRoot (1) também é tratado como sem-foco. Tradeoff DECLARADO da"""
    monkeypatch.setattr(xlib, "_exe_basename_from_pid", lambda pid: "sackboy-bin")
    backend = _xlib_backend_with(_FakeXDisplay(focus=1))
    assert backend.get_active_window_info() is None


def test_focus_valido_mantem_comportamento_atual(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Foco numa janela X válida → caminho feliz intocado: a leitura via"""
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
    """O gate roda no poll de 2 Hz do autoswitch — loga 1x por episódio"""
    monkeypatch.setattr(xlib, "_exe_basename_from_pid", lambda pid: "sackboy-bin")
    eventos: list[str] = []
    monkeypatch.setattr(
        xlib.logger,
        "info",
        lambda evt, **kw: eventos.append(evt),
    )

    backend = _xlib_backend_with(_FakeXDisplay(focus=0))
    for _ in range(4):
        backend.get_active_window_info()
    backend._display = _FakeXDisplay(focus=_FakeWindowHandle(0x1200007))
    backend.get_active_window_info()
    backend._display = _FakeXDisplay(focus=0)
    backend.get_active_window_info()

    assert eventos.count("x11_focus_gate_no_x_focus") == 2


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
    assert backend._connected is False
    assert backend._init_attempted is False
    assert backend._display is None
    assert morto.fechado is True


def test_erro_pontual_nao_custa_a_conexao_viva() -> None:
    """Um erro não-reconhecido isolado (BadWindow e afins) NÃO derruba o"""
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
    """O ciclo completo do achado: conexão morre → drop → o tick seguinte"""
    monkeypatch.setattr(xlib, "_exe_basename_from_pid", lambda pid: "sackboy-bin")
    monkeypatch.setenv("DISPLAY", ":1")
    backend = _xlib_backend_with(_FakeXDisplay(focus=0))
    backend._display = _DisplayMorto()
    assert backend.get_active_window_info() is None

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
    """Com o X ainda fora do ar, a reconexão tenta 1x e respeita o backoff —"""
    monkeypatch.setenv("DISPLAY", ":1")
    backend = _xlib_backend_with(_FakeXDisplay(focus=0))
    backend._display = _DisplayMorto()
    assert backend.get_active_window_info() is None

    tentativas: list[bool] = []

    def _connect_falha(*a: Any, **kw: Any) -> Any:
        tentativas.append(True)
        raise OSError("X ainda fora do ar")

    import Xlib.display as _xdisplay

    monkeypatch.setattr(_xdisplay, "Display", _connect_falha)
    for _ in range(5):
        assert backend.get_active_window_info() is None

    assert len(tentativas) == 1


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
    backend.get_active_window_info()
    backend.get_active_window_info()

    assert eventos.count("x11_reconnect_attempt") == 1


FOCO_MEDIDO = 35651599
NET_ACTIVE_MEDIDO = 44040223
ROOT_ID = 0x1


class _FakeXWin:
    """Janela do fake: id, WM_CLASS opcional, pai opcional, título e pid."""

    def __init__(
        self,
        wid: int,
        *,
        wm_class: tuple[str, str] | None = None,
        parent: Any = None,
        title: str = "",
        pid: int = 0,
    ) -> None:
        self.id = wid
        self._wm_class = wm_class
        self._parent = parent
        self._title = title
        self._pid = pid

    def get_wm_class(self) -> tuple[str, str] | None:
        return self._wm_class

    def get_wm_name(self) -> str:
        return self._title

    def get_full_property(self, atom: int, _type: int) -> _FakeProperty | None:
        return _FakeProperty([self._pid]) if self._pid else None

    def query_tree(self) -> Any:
        return types.SimpleNamespace(parent=self._parent)


class _FakeRootWin(_FakeXWin):
    """Raiz: guarda o `_NET_ACTIVE_WINDOW` que o backend consulta."""

    def __init__(self, net_active: int) -> None:
        super().__init__(ROOT_ID)
        self._net_active = net_active

    def get_full_property(self, atom: int, _type: int) -> _FakeProperty | None:
        return _FakeProperty([self._net_active]) if self._net_active else None


class _FakeArvoreDisplay:
    """Display com árvore X de verdade (pais/filhos) e `_NET_ACTIVE_WINDOW`."""

    def __init__(self, *, foco: int, janelas: dict[int, _FakeXWin], net_active: int):
        self._foco = foco
        self._janelas = janelas
        self._root = _FakeRootWin(net_active)
        self._janelas.setdefault(ROOT_ID, self._root)

    def screen(self) -> Any:
        return types.SimpleNamespace(root=self._root)

    def intern_atom(self, name: str) -> int:
        return 1

    def create_resource_object(self, kind: str, wid: int) -> _FakeXWin:
        return self._janelas[wid]

    def get_input_focus(self) -> _FakeFocusReply:
        return _FakeFocusReply(_FakeWindowHandle(self._foco))


def _backend_arvore(display: _FakeArvoreDisplay) -> xlib.XlibBackend:
    backend = xlib.XlibBackend()
    backend._display = display
    backend._connected = True
    backend._init_attempted = True
    return backend


def test_foco_em_filha_sobe_ate_o_top_level(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """O servidor X entrega o foco à janela-filha do toolkit, dentro do frame"""
    monkeypatch.setattr(xlib, "_exe_basename_from_pid", lambda pid: "mmj-bin")
    topo = _FakeXWin(
        0x400001,
        wm_class=("mmj", "steam_app_2111190"),
        title="Mullet Mad Jack",
        pid=4242,
    )
    frame = _FakeXWin(0x400002, parent=topo)
    filha = _FakeXWin(0x400003, parent=frame)
    display = _FakeArvoreDisplay(
        foco=filha.id,
        janelas={w.id: w for w in (topo, frame, filha)},
        net_active=topo.id,
    )
    topo._parent = display._root

    info = _backend_arvore(display).get_active_window_info()

    assert info is not None
    assert info.wm_class == "steam_app_2111190"
    assert info.title == "Mullet Mad Jack"
    assert info.pid == 4242
    assert info.exe_basename == "mmj-bin"


def test_desacordo_medido_ao_vivo_retorna_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """O caso EXATO da medição: GUI do Hefesto com o foco, `_NET_ACTIVE_WINDOW`"""
    monkeypatch.setattr(xlib, "_exe_basename_from_pid", lambda pid: "python3")
    gui = _FakeXWin(
        FOCO_MEDIDO, wm_class=("main.py", "Main.py"), title="Hefesto", pid=7
    )
    steam = _FakeXWin(NET_ACTIVE_MEDIDO, wm_class=("steam", "steam"), title="Steam")
    display = _FakeArvoreDisplay(
        foco=gui.id,
        janelas={gui.id: gui, steam.id: steam},
        net_active=steam.id,
    )

    assert _backend_arvore(display).get_active_window_info() is None


def test_foco_sem_top_level_na_arvore_retorna_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Subida esgota a árvore sem achar WM_CLASS nenhum (janela override-redirect,"""
    monkeypatch.setattr(xlib, "_exe_basename_from_pid", lambda pid: "x")
    orfa = _FakeXWin(0x500001, parent=None)
    display = _FakeArvoreDisplay(
        foco=orfa.id, janelas={orfa.id: orfa}, net_active=0x400001
    )

    assert _backend_arvore(display).get_active_window_info() is None


def test_net_active_ausente_retorna_none(monkeypatch: pytest.MonkeyPatch) -> None:
    """Sem `_NET_ACTIVE_WINDOW` não há corroboração — degrada para None, como"""
    monkeypatch.setattr(xlib, "_exe_basename_from_pid", lambda pid: "x")
    topo = _FakeXWin(0x600001, wm_class=("a", "steam_app_1599660"))
    display = _FakeArvoreDisplay(
        foco=topo.id, janelas={topo.id: topo}, net_active=0
    )

    assert _backend_arvore(display).get_active_window_info() is None


def test_subida_para_na_raiz(monkeypatch: pytest.MonkeyPatch) -> None:
    """A raiz não é janela de aplicação nenhuma: chegar nela é 'não sei',"""
    monkeypatch.setattr(xlib, "_exe_basename_from_pid", lambda pid: "x")
    filha = _FakeXWin(0x700001)
    display = _FakeArvoreDisplay(
        foco=filha.id, janelas={filha.id: filha}, net_active=0x700001
    )
    filha._parent = display._root

    assert _backend_arvore(display).get_active_window_info() is None


def test_profundidade_maxima_barra_arvore_patologica(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Cadeia sem fim (ou ciclo) não pode travar o tick de 2 Hz do autoswitch."""
    monkeypatch.setattr(xlib, "_exe_basename_from_pid", lambda pid: "x")
    a = _FakeXWin(0x800001)
    b = _FakeXWin(0x800002, parent=a)
    a._parent = b
    display = _FakeArvoreDisplay(
        foco=a.id, janelas={a.id: a, b.id: b}, net_active=0x800001
    )

    assert _backend_arvore(display).get_active_window_info() is None


def test_log_do_desacordo_uma_vez_por_episodio(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """O poll é de 2 Hz e a GUI aberta em cima do jogo dura minutos — 1 log por"""
    monkeypatch.setattr(xlib, "_exe_basename_from_pid", lambda pid: "x")
    eventos: list[str] = []
    monkeypatch.setattr(xlib.logger, "info", lambda evt, **kw: eventos.append(evt))

    gui = _FakeXWin(FOCO_MEDIDO, wm_class=("main.py", "Main.py"))
    steam = _FakeXWin(NET_ACTIVE_MEDIDO, wm_class=("steam", "steam"))
    janelas = {gui.id: gui, steam.id: steam}
    discorda = _FakeArvoreDisplay(foco=gui.id, janelas=dict(janelas), net_active=steam.id)
    concorda = _FakeArvoreDisplay(
        foco=steam.id, janelas=dict(janelas), net_active=steam.id
    )

    backend = _backend_arvore(discorda)
    for _ in range(4):
        backend.get_active_window_info()
    backend._display = concorda
    assert backend.get_active_window_info() is not None
    backend._display = discorda
    backend.get_active_window_info()

    assert eventos.count("x11_foco_discorda_do_net_active") == 2
