"""MODO-01 (sprint 25/07) — o modo jogo liga sozinho.

O relato dela: *"modo jogo por exemplo não liga automaticamente."*

A cadeia medida com o Mullet Mad Jack (`steam_app_2111190`) aberto: nenhum dos
13 perfis do disco casa aquele jogo, os três candidatos são catch-all, a regra
R-21 recusa dar autoridade a catch-all sobre janela de jogo e devolve `None` —
e aí para. A R-21 tinha razão própria (um genérico de DESKTOP entrando num jogo
era o ping-pong `vitoria``Navegação` a cada 18-28 s), mas trocou *"o catch-all
entra num jogo"* por *"NINGUÉM entra num jogo"* e não pôs nada no lugar. O
daemon SABIA que havia jogo (`game_signal_transition de=daemon para=game`) e não
fazia nada com isso.

O que este arquivo trava, por entrega da sprint:

  - **B3** — motivo do veto (`select_for_window_ex`) + o MODO JOGO PADRÃO que o
    daemon liga quando é um jogo e nenhum perfil específico opina, **sem trocar
    de perfil** e **sem o cadeado bloquear** (o cadeado congela perfil, não modo);
  - **B2** — o cadeado cede também ao perfil que DECLARA ser de jogo (não
    catch-all, `mode.kind` em {gamepad, native}): era o `coop_local`, que casa
    por título, e todo jogo fora da Steam;
  - **B1** — perfil novo de jogo nasce com o modo jogo pré-selecionado;
  - **B5** — o `ProfileManager` de leitura do daemon é cacheado (a dedup do veto
    é campo de instância e a instância nova a cada tique a zerava);
  - os presets de jogo nascem com seção `mode`.

Invariante que NÃO pode cair junto: gesto manual dela cria trava de 30 s e
nada — nem o modo jogo padrão — mexe no modo nesse período.
"""
from __future__ import annotations

import json
import sys
import types
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

import pytest

from hefesto_dualsense4unix.daemon import lifecycle as lifecycle_mod
from hefesto_dualsense4unix.daemon.lifecycle import Daemon, DaemonConfig
from hefesto_dualsense4unix.daemon.state_store import (
    MANUAL_PROFILE_LOCK_SEC,
    StateStore,
)
from hefesto_dualsense4unix.profiles import loader as loader_module
from hefesto_dualsense4unix.profiles.autoswitch import AutoSwitcher
from hefesto_dualsense4unix.profiles.loader import save_profile
from hefesto_dualsense4unix.profiles.manager import (
    MOTIVO_JOGO_SEM_PERFIL_PROPRIO,
    MOTIVO_SELECIONADO,
    MOTIVO_SEM_CANDIDATO,
    ProfileManager,
)
from hefesto_dualsense4unix.profiles.schema import (
    MatchAny,
    MatchCriteria,
    Profile,
    perfil_declara_modo_de_jogo,
    perfil_e_regra_de_jogo,
)
from hefesto_dualsense4unix.testing import FakeController

APPID_MMJ = 2111190  # Mullet Mad Jack — o jogo do relato
WM_MMJ = f"steam_app_{APPID_MMJ}"
ASSETS_DIR = Path(__file__).resolve().parents[2] / "assets" / "profiles_default"


# ---------------------------------------------------------------------------
# Infra
# ---------------------------------------------------------------------------


@pytest.fixture
def isolated_profiles_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    target = tmp_path / "profiles"
    target.mkdir()

    def fake_profiles_dir(ensure: bool = False) -> Path:
        if ensure:
            target.mkdir(parents=True, exist_ok=True)
        return target

    monkeypatch.setattr(loader_module, "profiles_dir", fake_profiles_dir)
    return target


class _Relogio:
    """Relógio monotônico do teste — o lock de gesto manual é de 30 s de parede."""

    def __init__(self, t0: float = 10_000.0) -> None:
        self.agora = t0

    def __call__(self) -> float:
        return self.agora

    def avancar(self, segundos: float) -> None:
        self.agora += segundos


@pytest.fixture
def relogio(monkeypatch: pytest.MonkeyPatch) -> _Relogio:
    r = _Relogio()
    monkeypatch.setattr(lifecycle_mod.time, "monotonic", r)
    return r


class _Setters:
    """Captura os setters do daemon (política, não efeito de hardware)."""

    def __init__(self, daemon: Daemon) -> None:
        self.gamepad: list[tuple[bool, str | None, str]] = []
        self.native: list[tuple[bool, str]] = []
        self.coop: list[tuple[bool, str]] = []
        self._daemon = daemon

    def bind(self, monkeypatch: pytest.MonkeyPatch) -> None:
        d = self._daemon

        def fake_gamepad(
            enabled: bool, flavor: str | None = None, *, origin: str = "manual"
        ) -> bool:
            self.gamepad.append((enabled, flavor, origin))
            d.config.gamepad_emulation_enabled = enabled
            d._gamepad_device = (
                SimpleNamespace(flavor=flavor or d.config.gamepad_flavor)
                if enabled
                else None
            )
            return True

        def fake_native(
            enabled: bool,
            *,
            reapply: bool = True,
            restore_stash: bool = False,
            origin: str = "manual",
        ) -> bool:
            self.native.append((enabled, origin))
            d._native_mode = enabled
            return enabled

        def fake_coop(enabled: bool, *, origin: str = "manual") -> bool:
            self.coop.append((enabled, origin))
            d.config.coop_enabled = enabled
            return enabled

        monkeypatch.setattr(d, "set_gamepad_emulation", fake_gamepad)
        monkeypatch.setattr(d, "set_native_mode", fake_native)
        monkeypatch.setattr(d, "set_coop_enabled", fake_coop)


@pytest.fixture
def daemon() -> Daemon:
    d = Daemon(controller=FakeController(), config=DaemonConfig())
    # NUMA-01: a autoridade de exibição vem do `GameSignal`; aqui só o valor
    # importa (o sinal real é fiado em `run()`).
    d._game_signal = SimpleNamespace(authority="game")
    return d


def _autoridade(daemon: Daemon, valor: str) -> None:
    daemon._game_signal = SimpleNamespace(authority=valor)


def _perfil_do_jogo(nome: str = "madjack") -> Profile:
    return Profile(
        name=nome,
        match=MatchCriteria(window_class=[WM_MMJ]),
        priority=0,  # perfil de jogo nasce com prioridade 0 (R-01)
    )


# ---------------------------------------------------------------------------
# B3 — o veto deixou de ser mudo
# ---------------------------------------------------------------------------


class TestMotivoDoVeto:
    """`None` era ambíguo entre "nada casou" e "vetei um catch-all num jogo"."""

    @staticmethod
    def _manager() -> ProfileManager:
        fc = FakeController()
        fc.connect()
        return ProfileManager(controller=fc)

    def test_jogo_so_com_catch_all_diz_o_motivo(
        self, isolated_profiles_dir: Path
    ) -> None:
        save_profile(Profile(name="vitoria", match=MatchAny(), priority=5))
        save_profile(Profile(name="fallback", match=MatchAny(), priority=0))

        perfil, motivo = self._manager().select_for_window_ex({"wm_class": WM_MMJ})

        assert perfil is None
        assert motivo == MOTIVO_JOGO_SEM_PERFIL_PROPRIO

    def test_jogo_sem_candidato_nenhum_e_o_mesmo_silencio(
        self, isolated_profiles_dir: Path
    ) -> None:
        """Disco sem nem catch-all: o veto nunca disparava e o buraco era igual."""
        perfil, motivo = self._manager().select_for_window_ex({"wm_class": WM_MMJ})

        assert perfil is None
        assert motivo == MOTIVO_JOGO_SEM_PERFIL_PROPRIO

    def test_desktop_sem_candidato_nao_e_jogo(
        self, isolated_profiles_dir: Path
    ) -> None:
        perfil, motivo = self._manager().select_for_window_ex({"wm_class": "inkscape"})

        assert perfil is None
        assert motivo == MOTIVO_SEM_CANDIDATO

    def test_perfil_proprio_do_jogo_continua_vencendo(
        self, isolated_profiles_dir: Path
    ) -> None:
        save_profile(_perfil_do_jogo())
        save_profile(Profile(name="vitoria", match=MatchAny(), priority=5))

        perfil, motivo = self._manager().select_for_window_ex({"wm_class": WM_MMJ})

        assert perfil is not None and perfil.name == "madjack"
        assert motivo == MOTIVO_SELECIONADO

    def test_assinatura_antiga_preservada(self, isolated_profiles_dir: Path) -> None:
        """Quem só quer o perfil (CLI, lifecycle, dublês) não muda de chamada."""
        save_profile(Profile(name="vitoria", match=MatchAny(), priority=5))
        manager = self._manager()

        assert manager.select_for_window({"wm_class": "firefox"}).name == "vitoria"
        assert manager.select_for_window({"wm_class": WM_MMJ}) is None


# ---------------------------------------------------------------------------
# B3 — o modo jogo padrão no daemon
# ---------------------------------------------------------------------------


class TestModoJogoPadrao:
    def test_liga_o_gamepad_quando_ninguem_opina(
        self, daemon: Daemon, relogio: _Relogio, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A cura: jogo em foco, nenhum perfil, e o modo jogo entra sozinho."""
        setters = _Setters(daemon)
        setters.bind(monkeypatch)

        estado = daemon.aplicar_modo_jogo_padrao(wm_class=WM_MMJ)

        assert estado == "aplicado"
        assert setters.gamepad == [(True, daemon.config.gamepad_flavor, "profile")]
        assert daemon._modo_jogo_padrao is not None
        assert daemon._modo_jogo_padrao.ligou_gamepad is True

    def test_sem_autoridade_de_jogo_nao_liga_nada(
        self, daemon: Daemon, relogio: _Relogio, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """`wm_class` de jogo sozinha não basta — quem manda é o sinal NUMA-01."""
        setters = _Setters(daemon)
        setters.bind(monkeypatch)
        _autoridade(daemon, "daemon")

        estado = daemon.aplicar_modo_jogo_padrao(wm_class=WM_MMJ)

        assert estado == "ignorado_sem_jogo"
        assert setters.gamepad == []
        assert daemon._modo_jogo_padrao is None

    def test_modo_nativo_manual_vence_o_default(
        self, daemon: Daemon, relogio: _Relogio, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """"Conexão Nativa (Sony)" já É a resposta dela para "como quero jogar" —
        o controle está SOLTO para o jogo, de propósito. Um default não troca uma
        escolha explícita quando o lock de 30 s vence."""
        setters = _Setters(daemon)
        setters.bind(monkeypatch)
        daemon.store.set_native_mode_active(True, origin="manual")

        estado = daemon.aplicar_modo_jogo_padrao(wm_class=WM_MMJ)

        assert estado == "ignorado_gesto_dela"
        assert setters.gamepad == []
        assert setters.native == []

    def test_nativo_ligado_por_perfil_nao_bloqueia(
        self, daemon: Daemon, relogio: _Relogio, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Nativo de PERFIL é automatismo, não gesto — não tem essa autoridade."""
        setters = _Setters(daemon)
        setters.bind(monkeypatch)
        daemon.store.set_native_mode_active(True, origin="profile")

        assert daemon.aplicar_modo_jogo_padrao(wm_class=WM_MMJ) == "aplicado"

    def test_idempotente_um_pedido_por_episodio(
        self, daemon: Daemon, relogio: _Relogio, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """O autoswitch pede a 2 Hz: não pode virar teardown/respawn de vpad."""
        setters = _Setters(daemon)
        setters.bind(monkeypatch)

        for _ in range(20):
            daemon.aplicar_modo_jogo_padrao(wm_class=WM_MMJ)

        assert len(setters.gamepad) == 1

    def test_gesto_manual_recente_adia_e_nao_mexe_no_modo(
        self, daemon: Daemon, relogio: _Relogio, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Invariante forte: trava de 30 s do gesto dela vale também aqui."""
        setters = _Setters(daemon)
        setters.bind(monkeypatch)
        daemon._emu_manual_ts = relogio.agora

        estado = daemon.aplicar_modo_jogo_padrao(wm_class=WM_MMJ)

        assert estado == "adiado_lock_manual"
        assert setters.gamepad == []
        assert daemon._modo_jogo_padrao is None

    def test_depois_do_lock_o_pedido_repetido_entra(
        self, daemon: Daemon, relogio: _Relogio, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """O pedido só ESPERA — o autoswitch repete e o modo entra ao vencer."""
        setters = _Setters(daemon)
        setters.bind(monkeypatch)
        daemon._emu_manual_ts = relogio.agora
        assert daemon.aplicar_modo_jogo_padrao(wm_class=WM_MMJ) == "adiado_lock_manual"

        relogio.avancar(MANUAL_PROFILE_LOCK_SEC + 0.1)

        assert daemon.aplicar_modo_jogo_padrao(wm_class=WM_MMJ) == "aplicado"
        assert setters.gamepad == [(True, daemon.config.gamepad_flavor, "profile")]

    def test_nao_usa_a_pendencia_de_perfil(
        self, daemon: Daemon, relogio: _Relogio, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """`ModoAdiado` é o canal do modo de um PERFIL — e morre quando o perfil
        ativo muda. O modo jogo padrão não tem perfil: usar aquele canal o faria
        ser descartado por um motivo que não se aplica a ele."""
        _Setters(daemon).bind(monkeypatch)
        daemon._emu_manual_ts = relogio.agora

        daemon.aplicar_modo_jogo_padrao(wm_class=WM_MMJ)

        assert daemon._mode_pendente is None

    def test_log_do_adiamento_uma_vez_por_episodio(
        self, daemon: Daemon, relogio: _Relogio, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Pedido a 2 Hz por até 30 s de lock = 60 linhas sem a dedup."""
        _Setters(daemon).bind(monkeypatch)
        spy = MagicMock()
        monkeypatch.setattr(lifecycle_mod, "logger", spy)
        daemon._emu_manual_ts = relogio.agora

        for _ in range(20):
            daemon.aplicar_modo_jogo_padrao(wm_class=WM_MMJ)

        eventos = [
            c for c in spy.info.call_args_list if c[0][0] == "modo_jogo_padrao_adiado"
        ]
        assert len(eventos) == 1

    def test_loga_a_aplicacao_com_origem_game_signal(
        self, daemon: Daemon, relogio: _Relogio, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """É por este evento que se distingue, meses depois, "o perfil do jogo
        ligou o modo" de "ninguém tinha perfil e o daemon ligou o padrão"."""
        _Setters(daemon).bind(monkeypatch)
        spy = MagicMock()
        monkeypatch.setattr(lifecycle_mod, "logger", spy)

        daemon.aplicar_modo_jogo_padrao(wm_class=WM_MMJ)

        eventos = [
            c for c in spy.info.call_args_list if c[0][0] == "profile_mode_aplicado"
        ]
        assert len(eventos) == 1
        assert eventos[0][1]["origin"] == "game_signal"


class TestSoltarOModoJogoPadrao:
    def test_desliga_so_o_gamepad_que_nos_ligamos(
        self, daemon: Daemon, relogio: _Relogio, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        setters = _Setters(daemon)
        setters.bind(monkeypatch)
        daemon.aplicar_modo_jogo_padrao(wm_class=WM_MMJ)
        setters.gamepad.clear()

        daemon.reverter_modo_jogo_padrao(wm_class="firefox")

        assert setters.gamepad == [(False, None, "profile")]
        assert daemon._modo_jogo_padrao is None

    def test_nao_derruba_o_vpad_que_ja_estava_ligado(
        self, daemon: Daemon, relogio: _Relogio, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Na máquina dela o vpad vive LIGADO por flag em disco. Um "reverter"
        ingênuo a deixaria sem controle nenhum no desktop ao fechar o jogo."""
        setters = _Setters(daemon)
        setters.bind(monkeypatch)
        daemon.config.gamepad_emulation_enabled = True
        daemon._gamepad_device = SimpleNamespace(flavor=daemon.config.gamepad_flavor)

        daemon.aplicar_modo_jogo_padrao(wm_class=WM_MMJ)
        setters.gamepad.clear()
        daemon.reverter_modo_jogo_padrao(wm_class="firefox")

        assert setters.gamepad == []
        assert daemon.config.gamepad_emulation_enabled is True

    def test_devolve_o_eixo_de_modo_a_quem_era_dono(
        self, daemon: Daemon, relogio: _Relogio, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Sem isto, o `"gamepad"` que o applier carimba daria a um perfil de
        desktop qualquer autoridade para reverter um modo que nenhum perfil
        ligou."""
        _Setters(daemon).bind(monkeypatch)
        daemon.aplicar_modo_jogo_padrao(wm_class=WM_MMJ)
        assert daemon._mode_from_profile == "gamepad"

        daemon.reverter_modo_jogo_padrao(wm_class="firefox")

        assert daemon._mode_from_profile is None

    def test_sem_modo_padrao_de_pe_e_no_op(
        self, daemon: Daemon, relogio: _Relogio, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        setters = _Setters(daemon)
        setters.bind(monkeypatch)
        daemon.config.gamepad_emulation_enabled = True
        daemon._gamepad_device = SimpleNamespace(flavor="xbox")

        daemon.reverter_modo_jogo_padrao(wm_class="firefox")

        assert setters.gamepad == []

    def test_gesto_manual_recente_so_solta_a_posse(
        self, daemon: Daemon, relogio: _Relogio, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        setters = _Setters(daemon)
        setters.bind(monkeypatch)
        daemon.aplicar_modo_jogo_padrao(wm_class=WM_MMJ)
        setters.gamepad.clear()
        daemon._emu_manual_ts = relogio.agora

        estado = daemon.reverter_modo_jogo_padrao(wm_class="firefox")

        assert estado == "adiado_lock_manual"
        assert setters.gamepad == []
        assert daemon._modo_jogo_padrao is None

    def test_perfil_com_opiniao_toma_a_posse(
        self, daemon: Daemon, relogio: _Relogio, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Ela cria o perfil do jogo no meio da sessão: dali em diante quem manda
        no modo é o perfil, e o padrão não tem mais o que soltar."""
        setters = _Setters(daemon)
        setters.bind(monkeypatch)
        daemon.aplicar_modo_jogo_padrao(wm_class=WM_MMJ)
        perfil = Profile.model_validate(
            {
                "name": "madjack",
                "match": {"type": "criteria", "window_class": [WM_MMJ]},
                "mode": {"kind": "gamepad", "gamepad_flavor": "xbox"},
            }
        )

        daemon.apply_profile_mode(perfil.mode, profile=perfil, origin="autoswitch")

        assert daemon._modo_jogo_padrao is None
        setters.gamepad.clear()
        daemon.reverter_modo_jogo_padrao(wm_class="firefox")
        assert setters.gamepad == []


# ---------------------------------------------------------------------------
# B3 — integração pelo AutoSwitcher (é ele que roda na máquina dela)
# ---------------------------------------------------------------------------


class _DaemonEspiao:
    """Dublê do par de callables do modo jogo padrão."""

    def __init__(self) -> None:
        self.aplicados: list[str] = []
        self.revertidos: list[str] = []

    def aplicar(self, *, wm_class: str = "") -> str:
        self.aplicados.append(wm_class)
        return "aplicado"

    def reverter(self, *, wm_class: str = "") -> str:
        self.revertidos.append(wm_class)
        return "aplicado"


def _switcher(store: StateStore, espiao: _DaemonEspiao | None = None) -> AutoSwitcher:
    fc = FakeController()
    fc.connect()
    return AutoSwitcher(
        manager=ProfileManager(controller=fc, store=store),
        window_reader=lambda: {},
        store=store,
        modo_jogo_padrao_applier=espiao.aplicar if espiao else None,
        modo_jogo_padrao_reverter=espiao.reverter if espiao else None,
    )


class TestAutoswitchPedeOModoJogoPadrao:
    def test_com_o_cadeado_ligado_o_modo_liga_e_o_perfil_nao_troca(
        self, isolated_profiles_dir: Path
    ) -> None:
        """O cenário exato da validação: cadeado ligado (mtime 24/07 20:42) e
        nenhum perfil para o jogo. O modo jogo liga; o perfil NÃO troca."""
        save_profile(Profile(name="vitoria", match=MatchAny(), priority=5))
        store = StateStore()
        store.set_autoswitch_locked(True)
        espiao = _DaemonEspiao()
        sw = _switcher(store, espiao)

        for t in (0.0, 0.6, 60.0):
            sw._tick({"wm_class": WM_MMJ, "wm_name": "Mullet Mad Jack"}, t)

        assert espiao.aplicados == [WM_MMJ] * 3
        assert sw._current_profile is None
        assert store.active_profile is None

    def test_janela_fora_do_jogo_solta_o_modo(
        self, isolated_profiles_dir: Path
    ) -> None:
        save_profile(Profile(name="vitoria", match=MatchAny(), priority=5))
        store = StateStore()
        espiao = _DaemonEspiao()
        sw = _switcher(store, espiao)

        sw._tick({"wm_class": WM_MMJ}, 0.0)
        sw._tick({"wm_class": "firefox", "wm_name": "Mozilla"}, 0.5)

        assert espiao.aplicados == [WM_MMJ]
        assert espiao.revertidos == ["firefox"]

    def test_perfil_proprio_do_jogo_nao_pede_o_padrao(
        self, isolated_profiles_dir: Path
    ) -> None:
        """Havendo regra própria, o modo é do PERFIL — o padrão sai de cena."""
        save_profile(
            Profile.model_validate(
                {
                    "name": "madjack",
                    "match": {"type": "criteria", "window_class": [WM_MMJ]},
                    "mode": {"kind": "gamepad", "gamepad_flavor": "xbox"},
                }
            )
        )
        store = StateStore()
        espiao = _DaemonEspiao()
        sw = _switcher(store, espiao)

        sw._tick({"wm_class": WM_MMJ}, 0.0)

        assert espiao.aplicados == []

    def test_tick_sem_informacao_nao_solta_o_modo(
        self, isolated_profiles_dir: Path
    ) -> None:
        """A histerese UX-01 pula o tick INTEIRO: leitura cega não é evidência de
        que ela saiu do jogo (o EIO de BT já mediu 5,1 s; loading dura minutos)."""
        save_profile(Profile(name="vitoria", match=MatchAny(), priority=5))
        store = StateStore()
        espiao = _DaemonEspiao()
        sw = _switcher(store, espiao)

        sw._tick({"wm_class": WM_MMJ}, 0.0)
        sw._tick({"wm_class": "unknown"}, 0.5)
        sw._tick({}, 1.0)

        assert espiao.revertidos == []

    def test_sem_daemon_o_tick_segue_igual(self, isolated_profiles_dir: Path) -> None:
        """Sem os callables (CLI/testes legados) nada muda no autoswitch."""
        save_profile(Profile(name="vitoria", match=MatchAny(), priority=5))
        store = StateStore()
        sw = _switcher(store, None)

        for t in (0.0, 0.6):
            sw._tick({"wm_class": WM_MMJ}, t)

        assert sw._current_profile is None

    def test_manager_sem_o_metodo_novo_nao_derruba_o_tick(self) -> None:
        """Dublê de teste/integração antiga: o motivo é informação EXTRA e sua
        ausência tem de deixar o autoswitch byte-idêntico ao de antes."""
        store = StateStore()
        manager = MagicMock(spec=ProfileManager)
        manager.select_for_window_ex.return_value = MagicMock()
        manager.select_for_window.return_value = None
        espiao = _DaemonEspiao()
        sw = AutoSwitcher(
            manager=manager,
            window_reader=lambda: {},
            store=store,
            modo_jogo_padrao_applier=espiao.aplicar,
            modo_jogo_padrao_reverter=espiao.reverter,
        )

        sw._tick({"wm_class": WM_MMJ}, 0.0)

        manager.select_for_window.assert_called_once()
        assert espiao.aplicados == []

    def test_falha_do_daemon_nao_derruba_o_tick(
        self, isolated_profiles_dir: Path
    ) -> None:
        save_profile(Profile(name="vitoria", match=MatchAny(), priority=5))
        store = StateStore()

        def _explode(*, wm_class: str = "") -> str:
            raise RuntimeError("daemon caiu")

        fc = FakeController()
        fc.connect()
        sw = AutoSwitcher(
            manager=ProfileManager(controller=fc, store=store),
            window_reader=lambda: {},
            store=store,
            modo_jogo_padrao_applier=_explode,
        )

        sw._tick({"wm_class": WM_MMJ}, 0.0)  # não levanta


# ---------------------------------------------------------------------------
# B2 — o cadeado congelava mais do que prometia
# ---------------------------------------------------------------------------


class TestCadeadoCedeAPerfilQueSeDeclaraDeJogo:
    def test_coop_local_casa_por_titulo_e_deixa_de_ser_congelado(
        self, isolated_profiles_dir: Path
    ) -> None:
        """O preset TEM `mode: gamepad` e casa por TÍTULO (Sackboy, Overcooked,
        It Takes Two, Cuphead) — o cadeado o congelava por não ser `steam_app_*`
        em `window_class`."""
        save_profile(
            Profile.model_validate(
                {
                    "name": "coop_local",
                    "match": {
                        "type": "criteria",
                        "window_title_regex": ".*(Sackboy|Overcooked).*",
                    },
                    "priority": 75,
                    "mode": {"kind": "gamepad", "gamepad_flavor": "xbox"},
                }
            )
        )
        store = StateStore()
        store.set_autoswitch_locked(True)
        sw = _switcher(store)

        janela = {"wm_class": "steam_app_1599660", "wm_name": "Sackboy"}
        sw._tick(janela, 0.0)
        sw._tick(janela, 0.6)

        assert sw._current_profile == "coop_local"

    def test_jogo_fora_da_steam_com_perfil_proprio_tambem_cede(
        self, isolated_profiles_dir: Path
    ) -> None:
        """GOG/Heroic/itch/nativo: sem `steam_app_*` não havia como ceder."""
        save_profile(
            Profile.model_validate(
                {
                    "name": "cyberpunk_gog",
                    "match": {"type": "criteria", "process_name": ["Cyberpunk2077"]},
                    "mode": {"kind": "native"},
                }
            )
        )
        store = StateStore()
        store.set_autoswitch_locked(True)
        sw = _switcher(store)

        janela = {"wm_class": "cyberpunk", "exe_basename": "Cyberpunk2077"}
        sw._tick(janela, 0.0)
        sw._tick(janela, 0.6)

        assert sw._current_profile == "cyberpunk_gog"

    def test_perfil_de_desktop_continua_congelado(
        self, isolated_profiles_dir: Path
    ) -> None:
        """O que ela pediu segue de pé: janela comum não troca o perfil."""
        save_profile(
            Profile(
                name="Navegação",
                match=MatchCriteria(window_class=["steam"]),
                priority=50,
            )
        )
        store = StateStore()
        store.set_autoswitch_locked(True)
        sw = _switcher(store)

        for t in (0.0, 0.6, 30.0):
            sw._tick({"wm_class": "steam", "wm_name": "Steam"}, t)

        assert sw._current_profile is None

    def test_catch_all_com_mode_gamepad_nao_cede(self) -> None:
        """Um catch-all chegou por acidente (nenhuma regra casou) — declarar
        `mode` não lhe dá a autoridade que a R-01/R-21 lhe negaram."""
        catch_all = Profile.model_validate(
            {
                "name": "vitoria",
                "match": {"type": "any"},
                "mode": {"kind": "gamepad", "gamepad_flavor": "xbox"},
            }
        )
        assert perfil_declara_modo_de_jogo(catch_all) is False

    def test_predicado_estrito_nao_foi_afrouxado(self) -> None:
        """`perfil_e_regra_de_jogo` também gateia o furo da trava manual
        (F2/R-01) — afrouxá-lo reabriria por outra porta o buraco em que um
        regex de título solto apagava a configuração recém-feita à mão."""
        por_titulo = Profile.model_validate(
            {
                "name": "fps",
                "match": {"type": "criteria", "window_title_regex": "(Doom|Control)"},
                "mode": {"kind": "gamepad", "gamepad_flavor": "xbox"},
            }
        )
        janela = {"wm_class": "steam_app_379720", "wm_name": "Doom Eternal"}

        assert perfil_e_regra_de_jogo(por_titulo, janela) is False
        assert perfil_declara_modo_de_jogo(por_titulo) is True

    def test_sem_secao_mode_nao_declara_nada(self) -> None:
        sem_mode = Profile(name="fps", match=MatchCriteria(process_name=["cs2"]))
        assert perfil_declara_modo_de_jogo(sem_mode) is False
        assert perfil_declara_modo_de_jogo(None) is False

    def test_mode_desktop_nao_e_declaracao_de_jogo(self) -> None:
        desktop = Profile.model_validate(
            {
                "name": "leitura",
                "match": {"type": "criteria", "window_class": ["firefox"]},
                "mode": {"kind": "desktop"},
            }
        )
        assert perfil_declara_modo_de_jogo(desktop) is False


# ---------------------------------------------------------------------------
# B5 — a enxurrada de log
# ---------------------------------------------------------------------------


class TestManagerDeSelecaoCacheado:
    def test_mesma_instancia_entre_tiques(self, daemon: Daemon) -> None:
        """A dedup do veto R-21 é campo de INSTÂNCIA: instância nova a cada tique
        a zerava e o journal levava 1 linha a cada 2,00 s (12 medidas)."""
        primeiro = daemon._manager_de_selecao()
        assert daemon._manager_de_selecao() is primeiro

    def test_veto_loga_uma_vez_ao_longo_dos_tiques(
        self,
        daemon: Daemon,
        isolated_profiles_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from hefesto_dualsense4unix.profiles import manager as manager_mod

        spy = MagicMock()
        monkeypatch.setattr(manager_mod, "logger", spy)
        save_profile(Profile(name="vitoria", match=MatchAny(), priority=5))

        for _ in range(12):  # 12 tiques = os 24 s medidos no journal
            daemon._profile_rule_matches_game(WM_MMJ)

        eventos = [
            c
            for c in spy.info.call_args_list
            if c[0][0] == "profile_select_catch_all_sem_autoridade_em_jogo"
        ]
        assert len(eventos) == 1


# ---------------------------------------------------------------------------
# B1 — perfil de jogo nasce com modo
# ---------------------------------------------------------------------------


def _install_gi_stubs() -> None:
    """Stubs mínimos de ``gi.repository`` quando o PyGObject real falta.

    Réplica do helper de ``test_profiles_editor_mode.py`` (armadilha A-12: o
    ``.venv`` de CI pode não ter PyGObject).
    """
    # GATE-SKIP-MASK-01: com o PyGObject real disponível, NÃO instala stubs.
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
    gi_mod.require_version = lambda _n, _v: None  # type: ignore[attr-defined]
    repo_mod = types.ModuleType("gi.repository")
    gtk_mod = types.ModuleType("gi.repository.Gtk")
    glib_mod = types.ModuleType("gi.repository.GLib")
    gobject_mod = types.ModuleType("gi.repository.GObject")
    for nome in (
        "Builder",
        "Window",
        "Button",
        "ComboBoxText",
        "Switch",
        "TextView",
        "TextBuffer",
        "TreeView",
        "TreeViewColumn",
        "CellRendererText",
        "ListStore",
        "TreeSelection",
        "TreePath",
        "Box",
        "Entry",
        "RadioButton",
        "Scale",
        "Stack",
    ):
        setattr(gtk_mod, nome, object)
    glib_mod.timeout_add = lambda *_a, **_kw: 0  # type: ignore[attr-defined]
    glib_mod.idle_add = lambda *_a, **_kw: 0  # type: ignore[attr-defined]
    gobject_mod.TYPE_STRING = "str"  # type: ignore[attr-defined]
    gobject_mod.TYPE_INT = "int"  # type: ignore[attr-defined]
    repo_mod.Gtk = gtk_mod  # type: ignore[attr-defined]
    repo_mod.GLib = glib_mod  # type: ignore[attr-defined]
    repo_mod.GObject = gobject_mod  # type: ignore[attr-defined]
    gi_mod.repository = repo_mod  # type: ignore[attr-defined]
    sys.modules["gi"] = gi_mod
    sys.modules["gi.repository"] = repo_mod
    sys.modules["gi.repository.Gtk"] = gtk_mod
    sys.modules["gi.repository.GLib"] = glib_mod
    sys.modules["gi.repository.GObject"] = gobject_mod


class _FakeSelector:
    """Mesma API por-ID do SegmentedSelector, sem GTK."""

    def __init__(self, active_id: str = "") -> None:
        self._id = active_id

    def get_active_id(self) -> str:
        return self._id

    def set_active_id(self, value: str) -> None:
        self._id = value

    def connect(self, _sinal: str, _cb: Any) -> int:
        return 0


class _FakeBox:
    def __init__(self) -> None:
        self.visible = True
        self.no_show_all = True
        self.filhos_visiveis = False

    def show(self) -> None:
        self.visible = True

    def show_all(self) -> None:
        # CAMPO-QUE-NAO-NASCIA-01: doutrina do GTK — com o `no_show_all` armado
        # o `show_all()` IGNORA o widget (e, por não descer nele, os filhos).
        if self.no_show_all:
            return
        self.visible = True
        self.filhos_visiveis = True

    def hide(self) -> None:
        self.visible = False

    def set_visible(self, value: bool) -> None:
        self.visible = bool(value)

    def set_no_show_all(self, value: bool) -> None:
        self.no_show_all = bool(value)

    def set_sensitive(self, _value: bool) -> None:
        return None


class _FakeEntry:
    def __init__(self, text: str = "") -> None:
        self._text = text

    def get_text(self) -> str:
        return self._text

    def set_text(self, value: str) -> None:
        self._text = value

    def set_placeholder_text(self, _v: str) -> None:
        return None

    def set_tooltip_text(self, _v: str) -> None:
        return None


def _editor_novo(escolha: str) -> Any:
    """Editor fake com a seção Modo montada, no estado "perfil NOVO"."""
    _install_gi_stubs()
    from hefesto_dualsense4unix.app.actions.profiles_actions import (
        ProfilesActionsMixin,
    )

    class _Editor(ProfilesActionsMixin):
        def __init__(self) -> None:
            self._widgets: dict[str, Any] = {
                "profile_simple_custom_name": _FakeEntry(""),
                "profile_game_entry_box": _FakeBox(),
            }
            self._aplica_a = _FakeSelector(escolha)
            self._mode_kind_selector = _FakeSelector("none")
            self._mode_flavor_selector = _FakeSelector("xbox")
            self._mode_gamepad_opts = _FakeBox()
            self._new_profile = True

        def _get(self, widget_id: str) -> Any:
            return self._widgets.get(widget_id)

    return _Editor()


@pytest.fixture
def sem_ipc(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Neutraliza o IPC da GUI: o teste é do CONTRATO, não do transporte."""
    _install_gi_stubs()
    from hefesto_dualsense4unix.app.actions import profiles_actions as pa

    chamadas: list[str] = []

    def _fake_call_async(*, method: str, **_kw: Any) -> None:
        chamadas.append(method)

    monkeypatch.setattr(pa, "call_async", _fake_call_async)
    return chamadas


class TestPerfilDeJogoNasceComModo:
    def test_jogo_da_steam_pre_seleciona_o_modo_jogo(
        self, sem_ipc: list[str]
    ) -> None:
        """O caminho que a interface oferecia como solução não solucionava: o
        perfil nascia com `"none"` — "Não mexer no modo"."""
        editor = _editor_novo("steam_game")

        editor._on_aplica_a_changed(editor._aplica_a)

        assert editor._mode_kind_selector.get_active_id() == "gamepad"

    def test_jogo_especifico_tambem(self, sem_ipc: list[str]) -> None:
        editor = _editor_novo("game")

        editor._on_aplica_a_changed(editor._aplica_a)

        assert editor._mode_kind_selector.get_active_id() == "gamepad"

    def test_preserva_a_mascara_corrente_do_seletor(
        self, sem_ipc: list[str]
    ) -> None:
        """Pré-selecionar uma máscara diferente da que está de pé faria o perfil
        RECRIAR o vpad ao entrar — e recriar vpad com o jogo aberto invalida os
        handles que ele já abriu (medido ao vivo)."""
        editor = _editor_novo("steam_game")
        editor._mode_flavor_selector.set_active_id("dualsense")

        editor._on_aplica_a_changed(editor._aplica_a)

        assert editor._mode_flavor_selector.get_active_id() == "dualsense"

    def test_contexto_de_desktop_nao_pre_seleciona_nada(
        self, sem_ipc: list[str]
    ) -> None:
        editor = _editor_novo("browser")

        editor._on_aplica_a_changed(editor._aplica_a)

        assert editor._mode_kind_selector.get_active_id() == "none"

    def test_perfil_ja_salvo_nao_tem_o_modo_reescrito(
        self, sem_ipc: list[str]
    ) -> None:
        """Trocar o "Aplica a" de um perfil existente não pode apagar a escolha
        de modo que ela fez antes."""
        editor = _editor_novo("steam_game")
        editor._new_profile = False

        editor._on_aplica_a_changed(editor._aplica_a)

        assert editor._mode_kind_selector.get_active_id() == "none"

    def test_modo_escolhido_a_mao_nao_e_sobrescrito(
        self, sem_ipc: list[str]
    ) -> None:
        """`desktop`/`native` escolhidos à mão são opinião dela, não campo vazio."""
        editor = _editor_novo("steam_game")
        editor._mode_kind_selector.set_active_id("native")

        editor._on_aplica_a_changed(editor._aplica_a)

        assert editor._mode_kind_selector.get_active_id() == "native"


# ---------------------------------------------------------------------------
# Presets de fábrica
# ---------------------------------------------------------------------------


class TestPresetsDeJogoNascemComModo:
    """Dos 12 presets, 10 não tinham seção `mode` — inclusive o `fps`, que
    estava persistido como ATIVO no disco dela. Sem a seção, ativar o perfil do
    jogo não liga modo nenhum."""

    @staticmethod
    def _preset(nome: str) -> dict[str, Any]:
        return json.loads((ASSETS_DIR / f"{nome}.json").read_text(encoding="utf-8"))

    @pytest.mark.parametrize(
        # Slugs dos arquivos em assets/profiles_default/.
        "nome",
        [
            "fps",
            "aventura",
            "acao",  # slug do arquivo acao.json (noqa-acento)
            "corrida",
            "esportes",
            "coop_local",
        ],
    )
    def test_preset_de_jogo_tem_modo_gamepad(self, nome: str) -> None:
        mode = self._preset(nome).get("mode")
        assert isinstance(mode, dict), f"{nome}: sem seção mode"
        assert mode.get("kind") == "gamepad", f"{nome}: kind={mode.get('kind')!r}"

    @pytest.mark.parametrize("nome", ["navegacao", "point_and_click", "fallback"])
    def test_preset_de_desktop_segue_sem_opiniao(self, nome: str) -> None:
        """O mínimo desta sprint é não inventar modo onde não há jogo."""
        assert self._preset(nome).get("mode") is None

    def test_coop_local_vence_a_navegacao(self) -> None:
        """Prioridade 45 o deixava atrás de `Navegação` (50) — o único preset de
        fábrica que faz o modo jogo ligar em co-op fora da Steam perdia para um
        perfil de navegador."""
        coop = self._preset("coop_local")["priority"]
        navegacao = self._preset("navegacao")["priority"]
        sackboy = self._preset("sackboy_nativo")["priority"]
        assert coop > navegacao
        assert coop < sackboy  # o perfil do PRÓPRIO jogo segue ganhando
