"""AUTO-01 (sprint 25/07) — um clique em vez de dez.

O pedido dela: *"ao clicar em tal coisa, ele não precisar alterar 10 coisas em
abas, fechar a Steam, abrir, aplicar x, y e z, tudo de forma manual mas de forma
automática, o máximo que der."*

Este arquivo trava os três itens que impediam **os quatro jogadores**:

  - **AUTO-01.1** — a emulação de gamepad nascia DESLIGADA e o co-op depende
    dela: numa instalação nova, quatro DualSense plugados alimentavam UM cursor
    só. Agora dois controles na mesa ligam a emulação sozinhos — sem atropelar
    gesto manual dela nem a decisão persistida em disco;
  - **AUTO-01.2** — o co-op não existia na janela (``grep -ci coop main.glade``
    devolvia ZERO): a funcionalidade central do projeto só tinha caminho pela
    linha de comando. Agora é um botão que encadeia modo de jogo + co-op +
    renumeração;
  - **AUTO-01.3** — a máscara tinha DOIS donos: `gamepad on` pela linha de
    comando preservava a do daemon e "Jogar pelo Hefesto" impunha `xbox`. O
    mesmo gesto entregava máscaras diferentes, e a máscara decide se o jogo
    reconhece o controle.

Invariante que NÃO pode cair junto: gesto manual dela cria trava de 30 s e nada
— nem esta automação — mexe no modo nesse período.

Os testes do daemon entram pelo caminho PÚBLICO de verdade (o `Daemon.run()`,
com o poll loop girando): um teste que chamasse só o método da cura passaria
mesmo com a chamada arrancada do poll loop, e aí a automação não existiria na
máquina dela.
"""
from __future__ import annotations

import asyncio
import re
import sys
import types
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

import pytest

from hefesto_dualsense4unix.core.controller import ControllerState
from hefesto_dualsense4unix.daemon import lifecycle as lifecycle_mod
from hefesto_dualsense4unix.daemon.lifecycle import Daemon, DaemonConfig
from hefesto_dualsense4unix.daemon.state_store import MANUAL_PROFILE_LOCK_SEC
from hefesto_dualsense4unix.testing import FakeController
from hefesto_dualsense4unix.utils import session as session_mod

_GLADE = (
    Path(__file__).resolve().parents[2]
    / "src"
    / "hefesto_dualsense4unix"
    / "gui"
    / "main.glade"
)


# ---------------------------------------------------------------------------
# Infra do daemon
# ---------------------------------------------------------------------------


class _ControleComInventario(FakeController):
    """FakeController que responde `describe_controllers` (backend real responde).

    É por esta API — a mesma que o `_sync_identity_registry` já consome no tick
    lento — que o daemon conta os controles na mesa sem varrer /dev/input.
    """

    def __init__(self, conectados: int, *, transport: str = "usb") -> None:
        super().__init__(
            transport=transport,  # type: ignore[arg-type]
            states=[
                ControllerState(
                    battery_pct=80,
                    l2_raw=0,
                    r2_raw=0,
                    connected=True,
                    transport=transport,  # type: ignore[arg-type]
                )
                for _ in range(400)
            ],
        )
        self._conectados = conectados

    def describe_controllers(self) -> list[dict[str, object]]:
        if self._conectados <= 0:
            return [{"connected": False, "transport": None, "is_primary": False}]
        return [
            {
                "index": i,
                "connected": True,
                "transport": "usb",
                "is_primary": i == 0,
                "uniq": f"aa:bb:cc:dd:ee:0{i}",
            }
            for i in range(self._conectados)
        ]


@pytest.fixture()
def config_isolado(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Flags de sessão em tmp — o disco DELA não pode decidir o teste.

    Sem isto, o `gamepad_emulation.flag` que existe na máquina da mantenedora
    faria "nunca decidiu" virar "já decidiu" e o teste passaria/falharia
    conforme quem roda.
    """
    monkeypatch.setattr(session_mod, "config_dir", lambda ensure=False: tmp_path)
    return tmp_path


class _EspiaoDeEmulacao:
    """Captura `set_gamepad_emulation` sem criar uinput de verdade."""

    def __init__(self, daemon: Daemon) -> None:
        self.chamadas: list[tuple[bool, str | None, str]] = []
        self._daemon = daemon

    def bind(self, monkeypatch: pytest.MonkeyPatch) -> None:
        d = self._daemon

        def _fake(
            enabled: bool, flavor: str | None = None, *, origin: str = "manual"
        ) -> bool:
            self.chamadas.append((enabled, flavor, origin))
            d.config.gamepad_emulation_enabled = enabled
            d._gamepad_device = (
                SimpleNamespace(flavor=flavor or d.config.gamepad_flavor)
                if enabled
                else None
            )
            return True

        monkeypatch.setattr(d, "set_gamepad_emulation", _fake)


def _daemon(controles: int) -> Daemon:
    return Daemon(
        controller=_ControleComInventario(controles),
        config=DaemonConfig(
            poll_hz=200,
            auto_reconnect=False,
            ipc_enabled=False,
            udp_enabled=False,
            autoswitch_enabled=False,
            mouse_emulation_enabled=False,
            keyboard_emulation_enabled=False,
        ),
    )


async def _gira_o_poll_loop(daemon: Daemon, segundos: float = 0.12) -> None:
    """Roda o daemon DE VERDADE por um instante (caminho público)."""
    task = asyncio.create_task(daemon.run())
    await asyncio.sleep(segundos)
    daemon.stop()
    await task


class _Relogio:
    """Relógio monotônico do teste — o lock de gesto manual é de 30 s de parede."""

    def __init__(self, t0: float = 10_000.0) -> None:
        self.agora = t0

    def __call__(self) -> float:
        return self.agora

    def avancar(self, segundos: float) -> None:
        self.agora += segundos


# ---------------------------------------------------------------------------
# AUTO-01.1 — a emulação liga sozinha com dois controles na mesa
# ---------------------------------------------------------------------------


class TestDoisControlesLigamAEmulacao:
    @pytest.mark.asyncio
    async def test_o_poll_loop_liga_a_emulacao_com_dois_controles(
        self, config_isolado: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A cura, pelo caminho que roda na máquina dela: o daemon de pé.

        Instalação nova (nenhuma flag em disco), dois DualSense plugados: a
        emulação sobe sem ninguém abrir terminal nem aba. Sem ela o co-op nunca
        passa do gate (`CoopManager.should_be_active`) e os dois controles
        alimentam o mesmo cursor.
        """
        d = _daemon(controles=2)
        espiao = _EspiaoDeEmulacao(d)
        espiao.bind(monkeypatch)

        await _gira_o_poll_loop(d)

        assert espiao.chamadas, "a emulação não ligou com dois controles na mesa"
        ligou, _flavor, origem = espiao.chamadas[0]
        assert ligou is True
        # R-07: origem "profile" NÃO persiste preferência em disco e NÃO carimba
        # o lock de 30 s — a automação não pode fingir ser gesto dela.
        assert origem == "profile"

    @pytest.mark.asyncio
    async def test_um_controle_so_nao_liga_nada(
        self, config_isolado: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Quem joga sozinha não tem o modo trocado sob os pés."""
        d = _daemon(controles=1)
        espiao = _EspiaoDeEmulacao(d)
        espiao.bind(monkeypatch)

        await _gira_o_poll_loop(d)

        assert espiao.chamadas == []

    @pytest.mark.asyncio
    async def test_desligado_de_proposito_nunca_e_religado(
        self, config_isolado: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """O pior desfecho possível seria o produto brigando com ela.

        "Controlar o PC" grava o opt-out (`gamepad_disabled.flag`); com dois
        controles na mesa, a automação tem de ficar quieta para sempre.
        """
        session_mod.save_gamepad_emulation(False)
        d = _daemon(controles=4)
        espiao = _EspiaoDeEmulacao(d)
        espiao.bind(monkeypatch)

        await _gira_o_poll_loop(d)

        assert espiao.chamadas == []

    @pytest.mark.asyncio
    async def test_mouse_em_uso_nao_e_derrubado(
        self, config_isolado: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Emulação de mouse VIVA = ela está usando o controle como cursor agora.

        Ligar o vpad aqui derrubaria o mouse pela exclusão mútua e o perfil o
        religaria no tique seguinte: flap sem fim entre cursor e gamepad.
        """
        d = _daemon(controles=2)
        espiao = _EspiaoDeEmulacao(d)
        espiao.bind(monkeypatch)
        d._mouse_device = MagicMock()

        await _gira_o_poll_loop(d)

        assert espiao.chamadas == []

    def test_gesto_manual_recente_apenas_espera(
        self, config_isolado: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Invariante forte: trava de 30 s do gesto dela vale também aqui."""
        relogio = _Relogio()
        monkeypatch.setattr(lifecycle_mod.time, "monotonic", relogio)
        d = _daemon(controles=2)
        espiao = _EspiaoDeEmulacao(d)
        espiao.bind(monkeypatch)
        d._emu_manual_ts = relogio.agora

        assert d.aplicar_gamepad_para_multiplos_controles() == "adiado_lock_manual"
        assert espiao.chamadas == []

        relogio.avancar(MANUAL_PROFILE_LOCK_SEC + 0.1)

        assert d.aplicar_gamepad_para_multiplos_controles() == "aplicado"
        assert espiao.chamadas == [(True, None, "profile")]

    def test_modo_nativo_manual_vence_a_automacao(
        self, config_isolado: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """"Jogar direto (Sony)" é o controle SOLTO para o jogo, de propósito."""
        d = _daemon(controles=2)
        espiao = _EspiaoDeEmulacao(d)
        espiao.bind(monkeypatch)
        d.store.set_native_mode_active(True, origin="manual")

        assert d.aplicar_gamepad_para_multiplos_controles() == "ignorado_gesto_dela"
        assert espiao.chamadas == []

    def test_idempotente_um_pedido_por_episodio(
        self, config_isolado: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """O tick lento pede a cada 2 s: não pode virar respawn de vpad."""
        d = _daemon(controles=2)
        espiao = _EspiaoDeEmulacao(d)
        espiao.bind(monkeypatch)

        for _ in range(20):
            d.aplicar_gamepad_para_multiplos_controles()

        assert len(espiao.chamadas) == 1

    def test_log_do_adiamento_uma_vez_por_episodio(
        self, config_isolado: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Pedido a cada 2 s por tempo indefinido = journal inundado sem a dedup."""
        d = _daemon(controles=1)
        espiao = _EspiaoDeEmulacao(d)
        espiao.bind(monkeypatch)
        spy = MagicMock()
        monkeypatch.setattr(lifecycle_mod, "logger", spy)

        for _ in range(20):
            d.aplicar_gamepad_para_multiplos_controles()

        eventos = [
            c
            for c in spy.info.call_args_list
            if c[0][0] == "gamepad_multiplos_controles_adiado"
        ]
        assert len(eventos) == 1

    def test_contagem_ignora_desconectados(self, config_isolado: Path) -> None:
        """A entrada "offline" do backend (nenhum controle) não conta como um."""
        assert _daemon(controles=0).contar_controles_fisicos() == 0
        assert _daemon(controles=1).contar_controles_fisicos() == 1
        assert _daemon(controles=4).contar_controles_fisicos() == 4

    def test_backend_sem_a_api_nao_conta_ninguem(self, config_isolado: Path) -> None:
        """FakeController puro/legado: na dúvida, nada liga sozinho."""
        d = Daemon(controller=FakeController(), config=DaemonConfig())

        assert d.contar_controles_fisicos() == 0


# ---------------------------------------------------------------------------
# AUTO-01.1 — "nunca decidiu" ≠ "decidiu desligar" (utils.session)
# ---------------------------------------------------------------------------


class TestPreferenciaDeGamepadTemTresEstados:
    def test_instalacao_nova_e_nunca_decidiu(self, config_isolado: Path) -> None:
        assert session_mod.load_gamepad_preference() == (None, None)

    def test_desligar_grava_o_opt_out(self, config_isolado: Path) -> None:
        """Antes o desligar APAGAVA o flag e virava indistinguível de "nova"."""
        session_mod.save_gamepad_emulation(False)

        assert session_mod.load_gamepad_preference() == (False, None)
        assert (config_isolado / "gamepad_disabled.flag").exists()

    def test_ligar_apaga_o_opt_out(self, config_isolado: Path) -> None:
        session_mod.save_gamepad_emulation(False)
        session_mod.save_gamepad_emulation(True, "xbox")

        assert session_mod.load_gamepad_preference() == (True, "xbox")
        assert not (config_isolado / "gamepad_disabled.flag").exists()

    def test_contrato_antigo_de_leitura_intacto(self, config_isolado: Path) -> None:
        """`load_gamepad_emulation` é o que o boot usa — não pode mudar."""
        assert session_mod.load_gamepad_emulation() == (False, None)
        session_mod.save_gamepad_emulation(True, "dualsense")
        assert session_mod.load_gamepad_emulation() == (True, "dualsense")
        session_mod.save_gamepad_emulation(False)
        assert session_mod.load_gamepad_emulation() == (False, None)


# ---------------------------------------------------------------------------
# AUTO-01.2 / AUTO-01.3 — a janela
# ---------------------------------------------------------------------------


def _install_gi_stubs() -> None:
    """Stubs mínimos de ``gi.repository`` quando o PyGObject real falta (A-12)."""
    existente = sys.modules.get("gi")
    if existente is None or getattr(existente, "__spec__", None) is not None:
        try:
            import gi

            gi.require_version("Gtk", "3.0")
            from gi.repository import Gtk  # noqa: F401

            return
        except Exception:  # pragma: no cover — ambientes sem GTK
            pass

    gi_mod = sys.modules.get("gi") or types.ModuleType("gi")
    gi_mod.require_version = lambda _n, _v: None  # type: ignore[attr-defined]
    repo_mod = sys.modules.get("gi.repository") or types.ModuleType("gi.repository")
    gtk_mod = sys.modules.get("gi.repository.Gtk") or types.ModuleType(
        "gi.repository.Gtk"
    )
    glib_mod = sys.modules.get("gi.repository.GLib") or types.ModuleType(
        "gi.repository.GLib"
    )
    gobject_mod = sys.modules.get("gi.repository.GObject") or types.ModuleType(
        "gi.repository.GObject"
    )
    for cls_name in ("Builder", "Window", "Button", "Label", "Box", "Frame"):
        if not hasattr(gtk_mod, cls_name):
            setattr(gtk_mod, cls_name, type(cls_name, (), {}))
    if not hasattr(glib_mod, "idle_add"):
        glib_mod.idle_add = lambda fn, *a, **kw: fn(*a, **kw)  # type: ignore[attr-defined]
    repo_mod.Gtk = gtk_mod  # type: ignore[attr-defined]
    repo_mod.GLib = glib_mod  # type: ignore[attr-defined]
    repo_mod.GObject = gobject_mod  # type: ignore[attr-defined]
    sys.modules["gi"] = gi_mod
    sys.modules["gi.repository"] = repo_mod
    sys.modules["gi.repository.Gtk"] = gtk_mod
    sys.modules["gi.repository.GLib"] = glib_mod
    sys.modules["gi.repository.GObject"] = gobject_mod


_install_gi_stubs()

from hefesto_dualsense4unix.app.actions import (  # noqa: E402
    home_actions,
    mode_transition,
)

Chamada = tuple[str, dict[str, Any], float]


@pytest.fixture()
def ipc(monkeypatch: pytest.MonkeyPatch) -> list[Chamada]:
    """Grava (método, params, timeout) do IPC despachado pela GUI."""
    chamadas: list[Chamada] = []

    def _fake(
        method: str,
        params: dict[str, Any] | None,
        _ok: Any = None,
        _err: Any = None,
        timeout_s: float = 0.25,
    ) -> None:
        chamadas.append((method, dict(params or {}), timeout_s))

    monkeypatch.setattr(mode_transition, "call_async", _fake)
    monkeypatch.setattr(home_actions, "call_async", _fake)
    return chamadas


class _FakeWidget:
    def __init__(self, active_id: str | None = None) -> None:
        self.label = ""
        self.text = ""
        self.sensitive = True
        self._active_id = active_id

    def set_label(self, value: str) -> None:
        self.label = value

    def get_label(self) -> str:
        return self.label

    def set_text(self, value: str) -> None:
        self.text = value

    def get_text(self) -> str:
        return self.text

    def set_sensitive(self, value: bool) -> None:
        self.sensitive = bool(value)

    def get_active_id(self) -> str | None:
        return self._active_id

    def set_active_id(self, value: str) -> None:
        self._active_id = value


class _HomeStub:
    """Instância mínima com o que os caminhos de co-op/máscara tocam."""

    _on_home_coop_prep_clicked = home_actions.HomeActionsMixin._on_home_coop_prep_clicked
    _render_coop_prep = home_actions.HomeActionsMixin._render_coop_prep

    def __init__(self, flavor: str | None = None) -> None:
        self._home_flavor_selector = _FakeWidget(flavor)
        self._home_coop_prep_btn = _FakeWidget()
        self._home_coop_prep_hint = _FakeWidget()
        self.toasts: list[str] = []
        self.refreshed = 0

    def _status_toast(self, _origem: str, mensagem: str) -> None:
        self.toasts.append(mensagem)

    def _refresh_home_tab(self) -> None:
        self.refreshed += 1


class TestCoopExisteNaJanela:
    def test_o_glade_declara_o_botao_de_coop(self) -> None:
        """A medida da queixa: ``grep -ci coop main.glade`` devolvia ZERO."""
        fonte = _GLADE.read_text(encoding="utf-8")

        assert 'id="home_coop_prep_btn"' in fonte
        assert re.search(r"coop", fonte, re.IGNORECASE)

    def test_plano_encadeia_modo_coop_e_renumeracao(self) -> None:
        """Um clique no lugar de: aba Início, terminal, e voltar pra renumerar."""
        assert mode_transition.plan_coop_prep("xbox") == [
            ("native.mode.set", {"enabled": False}),
            ("gamepad.emulation.set", {"enabled": True, "flavor": "xbox"}),
            ("coop.set", {"enabled": True}),
            ("identity.renumber", {}),
        ]

    def test_o_botao_dispara_a_sequencia_inteira(self, ipc: list[Chamada]) -> None:
        _HomeStub("xbox")._on_home_coop_prep_clicked(None)

        assert [m for m, _p, _t in ipc] == [
            "native.mode.set",
            "gamepad.emulation.set",
            "coop.set",
            "identity.renumber",
        ]
        # Cada passo cria/desmonta uinput e grab: nenhum cabe nos 0,25 s default.
        assert all(t == mode_transition.MODE_IPC_TIMEOUT_S for _m, _p, t in ipc)

    def test_a_renumeracao_recusada_nao_vira_falha_do_coop(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """O daemon recusa renumerar com jogo aberto. Com os jogadores JÁ de pé,
        um toast de falha seria a interface mentindo."""
        callbacks: dict[str, Any] = {}

        def _fake(
            method: str,
            _params: dict[str, Any] | None,
            ok: Any = None,
            err: Any = None,
            timeout_s: float = 0.25,
        ) -> None:
            callbacks[method] = (ok, err)

        monkeypatch.setattr(mode_transition, "call_async", _fake)
        stub = _HomeStub("xbox")
        stub._on_home_coop_prep_clicked(None)

        _ok_renumber, err_renumber = callbacks["identity.renumber"]
        err_renumber(RuntimeError("sessao_de_jogo_aberta"))
        assert stub.toasts == []

        ok_coop, _err_coop = callbacks["coop.set"]
        ok_coop({"status": "ok", "enabled": True, "players": 4})
        assert stub.toasts == ["Co-op pronto — 4 jogador(es)."]

    def test_rotulo_conta_os_jogadores_que_vao_existir(self) -> None:
        assert home_actions.coop_prep_label([]) == "Preparar co-op"
        assert home_actions.coop_prep_label([{"a": 1}]) == "Preparar co-op"
        assert (
            home_actions.coop_prep_label([{"a": 1}, {"b": 2}, {"c": 3}])
            == "Preparar co-op (3 jogadores)"
        )

    def test_frase_convida_quando_ha_dois_controles_e_o_coop_esta_frio(self) -> None:
        estado = {
            "gamepad_emulation": {"enabled": False, "flavor": "xbox"},
            "coop": {"enabled": True, "players": 1},
        }

        assert home_actions.coop_prep_hint(estado, [{"a": 1}, {"b": 2}]) == (
            home_actions.COOP_PREP_HINT_CONVITE
        )

    def test_frase_avisa_que_falta_o_segundo_controle(self) -> None:
        estado = {"gamepad_emulation": {"enabled": True, "flavor": "xbox"}}

        assert home_actions.coop_prep_hint(estado, [{"a": 1}]) == (
            home_actions.COOP_PREP_HINT_UM_CONTROLE
        )

    def test_frase_reconhece_o_coop_ja_de_pe(self) -> None:
        estado = {
            "gamepad_emulation": {"enabled": True, "flavor": "xbox"},
            "coop": {"enabled": True, "players": 2},
        }

        assert home_actions.coop_prep_hint(estado, [{"a": 1}, {"b": 2}]) == (
            home_actions.COOP_PREP_HINT_PRONTO
        )

    def test_offline_desabilita_o_botao_e_cala_a_frase(self) -> None:
        """Sem daemon os três passos são IPC que não chega a lugar nenhum."""
        stub = _HomeStub()

        stub._render_coop_prep(None, [])

        assert stub._home_coop_prep_btn.sensitive is False
        assert stub._home_coop_prep_hint.text == ""

    def test_render_com_daemon_vivo_habilita_e_conta(self) -> None:
        stub = _HomeStub()
        estado = {
            "gamepad_emulation": {"enabled": True, "flavor": "xbox"},
            "coop": {"enabled": True, "players": 1},
        }

        stub._render_coop_prep(estado, [{"a": 1}, {"b": 2}])

        assert stub._home_coop_prep_btn.sensitive is True
        assert stub._home_coop_prep_btn.label == "Preparar co-op (2 jogadores)"


class TestUmDonoSoParaAMascara:
    def test_a_janela_nao_escolhe_mascara_por_ela(self) -> None:
        """Sem escolha explícita, o campo NÃO vai — quem decide é o daemon."""
        plano = mode_transition.plan_mode_transition("gamepad", None)

        assert plano[-1] == ("gamepad.emulation.set", {"enabled": True})

    def test_as_duas_portas_de_entrada_pedem_a_mesma_coisa(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """O achado do AUTO-01.3, medido nas duas portas.

        `gamepad on` (linha de comando) e "Jogar pelo Hefesto" (janela) agora
        emitem params IDÊNTICOS quando ninguém escolheu máscara — antes um
        preservava a do daemon e o outro impunha `xbox`, e a máscara decide se
        o jogo reconhece o controle.
        """
        from typer.testing import CliRunner

        import hefesto_dualsense4unix.app.ipc_bridge as bridge
        from hefesto_dualsense4unix.cli.app import app

        chamadas: list[tuple[str, dict[str, Any]]] = []

        def _fake_run_call(
            method: str,
            params: dict[str, Any] | None = None,
            timeout: float | None = None,
        ) -> Any:
            chamadas.append((method, dict(params or {})))
            return {"status": "ok", "enabled": True, "flavor": "dualsense"}

        monkeypatch.setattr(bridge, "_run_call", _fake_run_call)
        CliRunner().invoke(app, ["gamepad", "on"])
        (_metodo_cli, params_cli), = chamadas

        pela_janela = mode_transition.plan_mode_transition("gamepad", None)[-1][1]

        assert params_cli == pela_janela

    def test_o_clique_manda_a_mascara_que_ela_escolheu(
        self, ipc: list[Chamada]
    ) -> None:
        """O outro lado da regra: escolha explícita dela chega intacta ao daemon.

        (O guard do `_render_home` — payload sem máscara não reescreve o
        seletor — é travado em `test_home_render_state.py`, onde vive o dublê
        completo da aba.)
        """
        _HomeStub("dualsense")._on_home_coop_prep_clicked(None)

        passo = [(m, p) for m, p, _t in ipc if m == "gamepad.emulation.set"]
        assert passo == [("gamepad.emulation.set", {"enabled": True, "flavor": "dualsense"})]


# ---------------------------------------------------------------------------
# AUTO-01.7 — as curas de conexão valem sem reboot nos DOIS caminhos de install
# ---------------------------------------------------------------------------


class TestParamsDeModuloAQuenteNoInstallSh:
    """O caminho por PACOTE escrevia os params a quente; o `install.sh` não.

    Todos os parâmetros envolvidos são graváveis em tempo de execução e são
    lidos A CADA PROBE — escrevê-los faz a cura valer no próximo plug/conexão
    do controle, sem reiniciar a máquina. Inclusive a do "segundo DualSense que
    some" (`hid_playstation.feature_retries`), que é o que impede os quatro
    jogadores por Bluetooth.
    """

    _RAIZ = Path(__file__).resolve().parents[2]
    _INSTALL = (_RAIZ / "install.sh").read_text(encoding="utf-8")
    _HOST_UDEV = (_RAIZ / "scripts" / "install-host-udev.sh").read_text(
        encoding="utf-8"
    )

    def _alvos_do_caminho_por_pacote(self) -> set[str]:
        return {
            alvo
            for alvo in re.findall(
                r"/sys/module/(?:hid_nintendo|hid_playstation)/parameters/\w+",
                self._HOST_UDEV,
            )
        }

    def test_o_caminho_por_pacote_segue_escrevendo_os_params(self) -> None:
        """Guarda da premissa: se ELE parar, este teste vira falso-positivo."""
        assert self._alvos_do_caminho_por_pacote(), (
            "install-host-udev.sh deixou de escrever params de módulo a quente"
        )

    def test_install_sh_escreve_os_mesmos_params_a_quente(self) -> None:
        faltando = [
            alvo
            for alvo in sorted(self._alvos_do_caminho_por_pacote())
            if f"tee {alvo}" not in self._INSTALL
        ]

        assert faltando == [], (
            "install.sh não escreve a quente (exige reboot à toa): "
            f"{faltando}"
        )

    def test_a_escrita_nunca_recarrega_modulo(self) -> None:
        """Inviolável do projeto: recarregar hid_playstation derruba TODOS os
        DualSense, e os por Bluetooth perdem o link."""
        for nome in (
            "install_dkms_hid_nintendo_host",
            "install_dkms_hid_playstation_host",
        ):
            inicio = self._INSTALL.index(f"{nome}() {{")
            fim = self._INSTALL.index("\n}\n", inicio)
            corpo = "\n".join(
                re.sub(r"(^|\s)#.*$", r"\1", linha)
                for linha in self._INSTALL[inicio:fim].splitlines()
            )
            assert not re.search(r"\b(modprobe(?!\.d)|rmmod|insmod)\b", corpo), nome
