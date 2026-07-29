"""JANELA-CEGA-01 (28/07) — o detector de janela para de se declarar são cego.

Três defeitos encadeados, medidos ao vivo em 28/07 nesta máquina (COSMIC +
Wayland, backend `xlib` porque `DISPLAY` existe e o `systemd --user` o exporta):
o daemon publicava `window_detect_last_class="Hefesto-Dualsense4Unix"` (a
PRÓPRIA janela da GUI) e `window_detect_healthy=True` enquanto o backend
devolvia `None` a 2 Hz, com `get_input_focus()` em `X.NONE` nas 10 amostras.

O que este módulo mede:

1. `window_detect_seeing()` CAI depois de `WINDOW_DETECT_BLIND_AFTER_SEC` sem
   nenhuma leitura útil e VOLTA na primeira leitura útil seguinte — a resposta
   que o trinco de mão única `window_detect_healthy` não dá.
2. `window_detect_useful_age()` é a idade que denuncia a cegueira ao lado do
   sticky que nunca decai.
3. `window_detect_healthy` continua NÃO decaindo — de propósito, com teste que
   fixa a decisão: o consumidor dela é `game_signal.classify`, onde
   `healthy=False` sem evidência de jogo vira autoridade `unknown` e a
   transição `daemon -> unknown` dispara `replay_retained_game_outputs()`,
   que repinta a lightbar dela. Mudar isso é leva própria.
4. As SEIS causas de `None` do `XlibBackend` viram seis motivos DISTINTOS em
   `last_failure_reason` — "sem foco X" (normal: app Wayland nativo em foco)
   deixa de ser indistinguível de "backend morto" (grave).
5. `WindowReaderDiag.last_reason` colhe o motivo do backend e o zera na leitura
   útil; janela sem `wm_class` tem motivo próprio.
6. `daemon.state_full` E `daemon.status` publicam a leitura CRUA, a IDADE da
   última leitura útil, o `seeing` e o motivo.
"""
from __future__ import annotations

import time
import types
from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.daemon.ipc_server import IpcServer
from hefesto_dualsense4unix.daemon.state_store import (
    WINDOW_DETECT_BLIND_AFTER_SEC,
    StateStore,
)
from hefesto_dualsense4unix.integrations import window_detect
from hefesto_dualsense4unix.integrations.window_backends import null, xlib
from hefesto_dualsense4unix.profiles import loader as loader_module
from hefesto_dualsense4unix.profiles.manager import ProfileManager
from hefesto_dualsense4unix.testing import FakeController

# ---------------------------------------------------------------------------
# 1-3. A saúde que cai (e a que, de propósito, não cai)
# ---------------------------------------------------------------------------


def _semeado() -> StateStore:
    """Store com o detector semeado como o subsystem faz no boot do xlib."""
    store = StateStore()
    store.set_window_detect_backend("xlib", healthy=True)
    return store


def test_seeing_nasce_falso_porque_presuncao_nao_e_medicao() -> None:
    """O xlib nasce `healthy=True` por PRESUNÇÃO (`state_store` documenta).
    `seeing` só sobe com leitura medida."""
    store = _semeado()

    assert store.window_detect_healthy is True
    assert store.window_detect_seeing(now=0.0) is False
    assert store.window_detect_useful_age(now=0.0) is None


def test_seeing_cai_depois_do_teto_de_cegueira_e_volta_na_leitura_util() -> None:
    """O coração da leva: um detector cego para de se declarar são.

    FALHA-SEM: sem o carimbo da última leitura útil, `seeing` não existe e o
    único sinal disponível (`healthy`) fica True para sempre.
    """
    store = _semeado()
    store.record_window_detect_read("xlib", "steam_app_3357650", now=100.0)

    assert store.window_detect_seeing(now=100.0) is True
    # Um tique antes do teto ainda é "enxergando" (alt-tab longo é normal).
    quase = 100.0 + WINDOW_DETECT_BLIND_AFTER_SEC - 0.5
    store.record_window_detect_read("xlib", "unknown", now=quase)
    assert store.window_detect_seeing(now=quase) is True

    cego = 100.0 + WINDOW_DETECT_BLIND_AFTER_SEC + 0.5
    store.record_window_detect_read("xlib", "unknown", now=cego)
    assert store.window_detect_seeing(now=cego) is False

    # E VOLTA na primeira leitura útil seguinte, sem precisar de restart.
    store.record_window_detect_read("xlib", "steam", now=cego + 1.0)
    assert store.window_detect_seeing(now=cego + 1.0) is True


def test_idade_da_ultima_leitura_util_cresce_enquanto_o_sticky_mente() -> None:
    """A medição ao vivo, reproduzida: o sticky continua exibindo a classe de
    minutos atrás; a idade é quem conta que ninguém mais viu nada."""
    store = _semeado()
    store.record_window_detect_read("xlib", "Hefesto-Dualsense4Unix", now=10.0)
    for passo in range(1, 21):
        store.record_window_detect_read("xlib", "unknown", now=10.0 + passo * 30.0)

    assert store.window_detect_last_class == "Hefesto-Dualsense4Unix"
    assert store.window_detect_current_class == "unknown"
    assert store.window_detect_useful_age(now=610.0) == pytest.approx(600.0)
    assert store.window_detect_seeing(now=610.0) is False


def test_healthy_continua_sendo_trinco_de_mao_unica_de_proposito() -> None:
    """Trava de decisão: `healthy` NÃO pode decair enquanto o consumidor for o
    `game_signal` — `daemon -> unknown` dispara `replay_retained_game_outputs`
    e repinta a lightbar dela. Quem decai é `seeing`, que não decide nada."""
    store = _semeado()
    store.record_window_detect_read("xlib", "steam", now=0.0)
    store.record_window_detect_read(
        "xlib", "unknown", now=WINDOW_DETECT_BLIND_AFTER_SEC * 10
    )

    assert store.window_detect_healthy is True
    assert store.window_detect_seeing(now=WINDOW_DETECT_BLIND_AFTER_SEC * 10) is False


def test_boot_novo_do_detector_zera_a_contabilidade() -> None:
    """`set_window_detect_backend` = episódio novo: idade, motivo e `seeing`
    voltam ao zero (não se herda leitura útil de sessão anterior)."""
    store = _semeado()
    store.record_window_detect_read("xlib", "steam", now=5.0)
    store.record_window_detect_read("xlib", None, now=6.0, reason="sem_foco_x")

    store.set_window_detect_backend("xlib", healthy=True)

    assert store.window_detect_useful_age(now=7.0) is None
    assert store.window_detect_seeing(now=7.0) is False
    assert store.window_detect_reason is None


def test_motivo_guardado_ao_lado_da_leitura_crua_e_zerado_na_leitura_util() -> None:
    store = _semeado()
    store.record_window_detect_read(
        "xlib", "unknown", now=1.0, reason=xlib.MOTIVO_SEM_FOCO
    )
    assert store.window_detect_reason == xlib.MOTIVO_SEM_FOCO

    store.record_window_detect_read(
        "xlib", None, now=2.0, reason=xlib.MOTIVO_SEM_CONEXAO
    )
    assert store.window_detect_reason == xlib.MOTIVO_SEM_CONEXAO

    store.record_window_detect_read("xlib", "steam", now=3.0)
    assert store.window_detect_reason is None


# ---------------------------------------------------------------------------
# 4. As seis causas de `None` do backend X11 param de colapsar num só
# ---------------------------------------------------------------------------

ROOT_ID = 0x1


class _Prop:
    def __init__(self, value: list[int]) -> None:
        self.value = value


class _Win:
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

    def get_full_property(self, atom: int, _type: int) -> _Prop | None:
        return _Prop([self._pid]) if self._pid else None

    def query_tree(self) -> Any:
        return types.SimpleNamespace(parent=self._parent)


class _Root(_Win):
    def __init__(self, net_active: int) -> None:
        super().__init__(ROOT_ID)
        self._net_active = net_active

    def get_full_property(self, atom: int, _type: int) -> _Prop | None:
        return _Prop([self._net_active]) if self._net_active else None


class _Display:
    """Display X falso com árvore de verdade e `_NET_ACTIVE_WINDOW`."""

    def __init__(
        self, *, foco: Any, janelas: dict[int, _Win], net_active: int
    ) -> None:
        self._foco = foco
        self._janelas = janelas
        self._root = _Root(net_active)
        self._janelas.setdefault(ROOT_ID, self._root)

    def screen(self) -> Any:
        return types.SimpleNamespace(root=self._root)

    def intern_atom(self, name: str) -> int:
        return 1

    def create_resource_object(self, kind: str, wid: int) -> _Win:
        return self._janelas[wid]

    def get_input_focus(self) -> Any:
        return types.SimpleNamespace(focus=self._foco)


def _backend(display: Any) -> xlib.XlibBackend:
    backend = xlib.XlibBackend()
    backend._display = display
    backend._connected = True
    backend._init_attempted = True
    return backend


def test_motivo_sem_conexao_x(monkeypatch: pytest.MonkeyPatch) -> None:
    """Backend morto (sem DISPLAY / X caiu) — o caso GRAVE."""
    monkeypatch.delenv("DISPLAY", raising=False)
    backend = xlib.XlibBackend()

    assert backend.get_active_window_info() is None
    assert backend.last_failure_reason == xlib.MOTIVO_SEM_CONEXAO


def test_motivo_foco_sem_id() -> None:
    """`focus` sem `.id` e não-int (resposta malformada do servidor)."""
    backend = _backend(_Display(foco=object(), janelas={}, net_active=0))

    assert backend.get_active_window_info() is None
    assert backend.last_failure_reason == xlib.MOTIVO_FOCO_SEM_ID


def test_motivo_sem_foco_x() -> None:
    """`X.NONE` — o caso NORMAL nesta máquina: app Wayland nativo em foco.

    Foi o que as 10 amostras ao vivo mostraram; não pode ficar com a mesma
    cara de "o XWayland caiu".
    """
    backend = _backend(_Display(foco=0, janelas={}, net_active=0))

    assert backend.get_active_window_info() is None
    assert backend.last_failure_reason == xlib.MOTIVO_SEM_FOCO
    assert backend.last_failure_reason != xlib.MOTIVO_SEM_CONEXAO


def test_motivo_foco_sem_top_level() -> None:
    orfa = _Win(0x500001, parent=None)
    backend = _backend(
        _Display(foco=orfa, janelas={orfa.id: orfa}, net_active=0x400001)
    )

    assert backend.get_active_window_info() is None
    assert backend.last_failure_reason == xlib.MOTIVO_FOCO_SEM_TOP_LEVEL


def test_motivo_foco_discorda_do_net_active() -> None:
    gui = _Win(35651599, wm_class=("main.py", "Main.py"))
    steam = _Win(44040223, wm_class=("steam", "steam"))
    backend = _backend(
        _Display(
            foco=gui, janelas={gui.id: gui, steam.id: steam}, net_active=steam.id
        )
    )

    assert backend.get_active_window_info() is None
    assert backend.last_failure_reason == xlib.MOTIVO_FOCO_DISCORDA


def test_motivo_erro_de_consulta(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(xlib.logger, "warning", lambda *a, **k: None)

    class _Explode:
        def get_input_focus(self) -> Any:
            raise RuntimeError("BadWindow")

    backend = _backend(_Explode())

    assert backend.get_active_window_info() is None
    assert backend.last_failure_reason == xlib.MOTIVO_ERRO_DE_CONSULTA


def test_seis_motivos_do_xlib_sao_seis_strings_distintas() -> None:
    """O achado em uma linha: seis causas, seis nomes."""
    motivos = {
        xlib.MOTIVO_SEM_CONEXAO,
        xlib.MOTIVO_FOCO_SEM_ID,
        xlib.MOTIVO_SEM_FOCO,
        xlib.MOTIVO_FOCO_SEM_TOP_LEVEL,
        xlib.MOTIVO_FOCO_DISCORDA,
        xlib.MOTIVO_ERRO_DE_CONSULTA,
    }
    assert len(motivos) == 6


def test_leitura_boa_limpa_o_motivo(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(xlib, "_exe_basename_from_pid", lambda pid: "jogo-bin")
    topo = _Win(0x400001, wm_class=("j", "steam_app_3357650"), title="Jogo", pid=42)
    display = _Display(
        foco=topo, janelas={topo.id: topo}, net_active=topo.id
    )
    topo._parent = display._root
    backend = _backend(display)
    backend.last_failure_reason = xlib.MOTIVO_SEM_FOCO

    info = backend.get_active_window_info()

    assert info is not None
    assert backend.last_failure_reason is None


def test_null_backend_diz_que_e_cego_por_construcao() -> None:
    assert null.NullBackend().last_failure_reason == null.MOTIVO_SEM_BACKEND


# ---------------------------------------------------------------------------
# 5. O leitor colhe o motivo do backend
# ---------------------------------------------------------------------------


class _BackendFalso:
    backend_name = "falso"

    def __init__(self, info: Any, motivo: str | None = None) -> None:
        self._info = info
        self.last_failure_reason = motivo

    def get_active_window_info(self) -> Any:
        return self._info


def test_reader_propaga_o_motivo_do_backend_e_zera_na_leitura_util() -> None:
    from hefesto_dualsense4unix.integrations.window_backends.base import WindowInfo

    backend = _BackendFalso(None, motivo=xlib.MOTIVO_SEM_FOCO)
    reader = window_detect.WindowReaderDiag(backend)

    reader()
    assert reader.last_reason == xlib.MOTIVO_SEM_FOCO

    backend._info = WindowInfo(wm_class="steam_app_1", pid=1)
    reader()
    assert reader.last_read_useful is True
    assert reader.last_reason is None


def test_reader_nomeia_janela_sem_classe() -> None:
    """Backend DEVOLVEU janela, mas sem `wm_class`: a leitura não é útil e o
    motivo não pode virar "não sei por quê"."""
    from hefesto_dualsense4unix.integrations.window_backends.base import WindowInfo

    reader = window_detect.WindowReaderDiag(
        _BackendFalso(WindowInfo(wm_class="unknown"))
    )

    reader()

    assert reader.last_reason == window_detect.MOTIVO_JANELA_SEM_CLASSE


def test_reader_com_backend_sem_campo_ainda_diz_alguma_coisa() -> None:
    """`Protocol` intocado: backend de terceiro (ou dublê antigo) não expõe
    `last_failure_reason` — e mesmo assim o motivo é DITO, não engolido."""

    class _Antigo:
        def get_active_window_info(self) -> Any:
            return None

    reader = window_detect.WindowReaderDiag(_Antigo())

    reader()

    assert reader.last_reason == window_detect.MOTIVO_BACKEND_SEM_MOTIVO


def test_cascata_wayland_nomeia_a_propria_cegueira() -> None:
    cascata = window_detect._WaylandCascadeBackend()
    cascata._portal.get_active_window_info = lambda: None  # type: ignore[method-assign]
    cascata._wlrctl.get_active_window_info = lambda: None  # type: ignore[method-assign]

    assert cascata.get_active_window_info() is None
    assert cascata.last_failure_reason == window_detect.MOTIVO_CASCATA_SEM_LEITURA


# ---------------------------------------------------------------------------
# 6. O estado publicado deixa a cegueira à vista
# ---------------------------------------------------------------------------


@pytest.fixture
def ipc_server(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> IpcServer:
    """IpcServer mínimo (sem socket no ar) para chamar os handlers."""
    target = tmp_path / "profiles"
    target.mkdir()

    def fake_profiles_dir(ensure: bool = False) -> Path:
        if ensure:
            target.mkdir(parents=True, exist_ok=True)
        return target

    monkeypatch.setattr(loader_module, "profiles_dir", fake_profiles_dir)
    fc = FakeController(transport="usb")
    fc.connect()
    store = StateStore()
    manager = ProfileManager(controller=fc, store=store)
    return IpcServer(
        controller=fc,
        store=store,
        profile_manager=manager,
        socket_path=tmp_path / "hefesto-dualsense4unix.sock",
    )


def _cegueira_ao_vivo(store: StateStore) -> None:
    """Reproduz a medição de 28/07: sticky com a própria GUI, leitura crua
    cega há 10 minutos, motivo "sem foco X".

    Ancorado no monotonic REAL (nada de congelar `time.monotonic` global: o
    relógio do event loop do asyncio é o mesmo, e travá-lo no meio de um
    handler `async` é armadilha para os próximos).
    """
    agora = time.monotonic()
    store.set_window_detect_backend("xlib", healthy=True)
    store.record_window_detect_read(
        "xlib", "Hefesto-Dualsense4Unix", now=agora - 600.0
    )
    store.record_window_detect_read(
        "xlib", "unknown", now=agora, reason=xlib.MOTIVO_SEM_FOCO
    )


async def test_state_full_publica_a_cegueira(ipc_server: IpcServer) -> None:
    """FALHA-SEM: no HEAD anterior o `state_full` só tinha backend/healthy/
    last_class — as quatro chaves novas dão KeyError."""
    _cegueira_ao_vivo(ipc_server.store)

    result = await ipc_server._handle_daemon_state_full({})

    assert result["window_detect_last_class"] == "Hefesto-Dualsense4Unix"
    assert result["window_detect_current_class"] == "unknown"
    assert result["window_detect_useful_age_sec"] == pytest.approx(600.0, abs=1.0)
    assert result["window_detect_seeing"] is False
    assert result["window_detect_reason"] == xlib.MOTIVO_SEM_FOCO
    # O trinco continua True — e agora dá para ver que ele está mentindo.
    assert result["window_detect_healthy"] is True


async def test_status_passa_a_ter_o_bloco_do_detector(
    ipc_server: IpcServer,
) -> None:
    """FALHA-SEM: `daemon.status` não expunha campo `window_detect_*` nenhum."""
    _cegueira_ao_vivo(ipc_server.store)

    result = await ipc_server._handle_daemon_status({})

    assert result["window_detect_backend"] == "xlib"
    assert result["window_detect_seeing"] is False
    assert result["window_detect_reason"] == xlib.MOTIVO_SEM_FOCO
    assert result["window_detect_current_class"] == "unknown"


async def test_status_e_state_full_nao_divergem(ipc_server: IpcServer) -> None:
    _cegueira_ao_vivo(ipc_server.store)

    status = await ipc_server._handle_daemon_status({})
    full = await ipc_server._handle_daemon_state_full({})

    chaves = [k for k in full if k.startswith("window_detect_")]
    assert len(chaves) == 7
    for chave in chaves:
        assert status[chave] == full[chave]


async def test_idade_none_quando_nunca_houve_leitura_util(
    ipc_server: IpcServer,
) -> None:
    ipc_server.store.set_window_detect_backend("xlib", healthy=True)

    result = await ipc_server._handle_daemon_state_full({})

    assert result["window_detect_useful_age_sec"] is None
    assert result["window_detect_seeing"] is False
    assert result["window_detect_current_class"] is None


class TestOMotivoChegaAoStore:
    """JANELA-CEGA-01: o campo do IPC não pode nascer morto.

    O backend calcula o motivo, o `StateStore` sabe guardá-lo e o `state_full`
    o publica — mas isso só vale se o ÚNICO call site de produção
    (`_build_diag_window_reader`, o leitor que roda a 2 Hz) passar o parâmetro.
    Ele não passava: o campo saía `null` para sempre no daemon real.
    """

    @staticmethod
    def _montar(monkeypatch, *, motivo, classe):
        from hefesto_dualsense4unix.daemon.state_store import StateStore
        from hefesto_dualsense4unix.daemon.subsystems import autoswitch as aw

        class _ReaderComDiag:
            backend_name = "xlib"
            last_reason = motivo

            def __call__(self):
                return {"wm_class": classe}

        monkeypatch.setattr(
            "hefesto_dualsense4unix.integrations.window_detect.build_window_reader",
            lambda: _ReaderComDiag(),
        )
        store = StateStore()
        return store, aw._build_diag_window_reader(store)

    def test_o_motivo_da_cegueira_chega_ao_store(self, monkeypatch) -> None:
        store, ler = self._montar(monkeypatch, motivo="sem_foco_x", classe="unknown")
        ler()
        assert store.window_detect_reason == "sem_foco_x"

    def test_leitura_util_nao_carrega_motivo(self, monkeypatch) -> None:
        store, ler = self._montar(
            monkeypatch, motivo=None, classe="steam_app_1599660"
        )
        ler()
        assert store.window_detect_reason is None

    def test_leitor_sem_diagnostico_nao_derruba_o_tick(self, monkeypatch) -> None:
        """Leitor legado é callable puro, sem `last_reason` — não pode explodir."""
        from hefesto_dualsense4unix.daemon.state_store import StateStore
        from hefesto_dualsense4unix.daemon.subsystems import autoswitch as aw

        monkeypatch.setattr(
            "hefesto_dualsense4unix.integrations.window_detect.build_window_reader",
            lambda: (lambda: {"wm_class": "unknown"}),
        )
        store = StateStore()
        ler = aw._build_diag_window_reader(store)
        ler()
        assert store.window_detect_reason is None
