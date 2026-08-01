"""SOM-02/E4 — a FIAÇÃO do `speaker_applier` no daemon.

A seção `speaker` do perfil já carregava, salvava e fazia round-trip antes
desta entrega — e não escrevia NADA, porque ninguém injetava o applier. Aqui
ficam as mordidas do lado do daemon:

  1. **o applier** (`Daemon.apply_profile_speaker`) escreve o par completo no
     backend e NUNCA um `set_speaker_volume` sem volume (armadilha 1, medida:
     chamada sem volume toma a posse e manda ZERO, publicando
     `{'volume': 0, 'muted': True}`);
  2. **a armadilha desta entrega** — o applier NÃO pode armar a categoria
     manual `audio`. O `speaker.set` do IPC a arma (decisão da E3), e é ela
     que `ProfileManager.apply_speaker` consulta para desistir de escrever: um
     applier que passasse por aquele caminho armaria a trava na primeira
     ativação e todas as seguintes seriam descartadas EM SILÊNCIO. O teste da
     SEGUNDA ativação é o mais importante do arquivo;
  3. **os pontos de injeção** — IPC (duas rotas), autoswitch (duas rotas),
     ciclo por hotkey e restore de boot. Cada um prova o wiring ATIVANDO um
     perfil com o manager que o próprio callsite construiu e contando as
     escritas no backend: arrancar a linha `speaker_applier=` derruba o teste;
  4. **a reaplicação no connect** — a posse dos bytes de áudio morre com o
     cabo (`_volumes_audio` nasce vazio em cada handle, e cada conexão cria um
     handle novo). Sem o gancho, trocar o cabo devolve o volume ao do firmware
     em silêncio.

Perfil SEM a seção continua sem produzir escrita nenhuma em todos os caminhos
— sem opinião é silêncio, não ordem.
"""
from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, ClassVar

import pytest

from hefesto_dualsense4unix.daemon import connection as connection_mod
from hefesto_dualsense4unix.daemon.connection import (
    connect_with_retry,
    reapply_speaker_after_connect,
    restore_last_profile,
)
from hefesto_dualsense4unix.daemon.context import DaemonContext
from hefesto_dualsense4unix.daemon.lifecycle import Daemon, DaemonConfig
from hefesto_dualsense4unix.daemon.state_store import StateStore
from hefesto_dualsense4unix.daemon.subsystems import autoswitch as autoswitch_mod
from hefesto_dualsense4unix.daemon.subsystems import ipc as ipc_mod
from hefesto_dualsense4unix.daemon.subsystems.hotkey import (
    build_profile_cycle_callback,
)
from hefesto_dualsense4unix.profiles import loader as loader_module
from hefesto_dualsense4unix.profiles import manager as manager_module
from hefesto_dualsense4unix.profiles.loader import save_profile
from hefesto_dualsense4unix.profiles.manager import ProfileManager
from hefesto_dualsense4unix.profiles.schema import (
    LedsConfig,
    MatchAny,
    Profile,
    TriggerConfig,
    TriggersConfig,
)
from hefesto_dualsense4unix.testing import FakeController

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


class _BackendComAudio(FakeController):
    """Backend que CONTA as escritas de áudio, no molde do real.

    Espelha `core/backend_pydualsense.py`: `speaker_state_for` devolve **None**
    enquanto ninguém escreveu (é o que faz a chave `speaker` nem entrar no
    estado e a janela dizer "não ajustado") e, depois da escrita, devolve o par
    preferido/efetivo. `sem_handle=True` encena o controle ausente — o backend
    real devolve False quando não há handle para o `uniq`.
    """

    def __init__(self, *, sem_handle: bool = False, explode: bool = False) -> None:
        super().__init__()
        self.escritas_de_audio: list[dict[str, Any]] = []
        self._pref: int | None = None
        self._efetivo: int | None = None
        self._sem_handle = sem_handle
        self._explode = explode

    def set_speaker_volume(
        self,
        volume: int | None = None,
        *,
        muted: bool | None = None,
        uniq: str | None = None,
    ) -> bool:
        self.escritas_de_audio.append(
            {"volume": volume, "muted": muted, "uniq": uniq}
        )
        if self._explode:
            raise RuntimeError("controle sumiu no meio da escrita")
        if self._sem_handle:
            return False
        pref = self._pref
        if volume is not None:
            pref = max(0, min(255, int(volume)))
        if pref is None:
            # A armadilha 1, reproduzida: sem volume e sem preferência o real
            # cai em ZERO e toma a posse assim mesmo.
            pref = 0
        self._pref = pref
        self._efetivo = 0 if muted else pref
        return True

    def speaker_state_for(self, uniq: str | None = None) -> dict[str, Any] | None:
        if self._efetivo is None:
            return None
        return {"volume": int(self._pref or 0), "muted": self._efetivo == 0}


def _perfil(nome: str, **kw: object) -> Profile:
    """Perfil catch-all (MatchAny) — o restore de boot recusa perfil de janela."""
    dados: dict[str, object] = {
        "match": MatchAny(),
        "priority": 10,
        "triggers": TriggersConfig(
            left=TriggerConfig(mode="Off"),
            right=TriggerConfig(mode="Off"),
        ),
        "leds": LedsConfig(lightbar=(0, 0, 0), player_leds=[False] * 5),
    }
    dados.update(kw)
    return Profile(name=nome, **dados)  # type: ignore[arg-type]


def _daemon(backend: _BackendComAudio) -> Daemon:
    return Daemon(controller=backend, config=DaemonConfig())


def _sem_executor(daemon: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    """Troca `_run_blocking` por chamada direta (sem pool de threads no teste)."""

    async def _direto(fn: Any, *args: Any) -> Any:
        return fn(*args)

    monkeypatch.setattr(daemon, "_run_blocking", _direto)


class _ManagerEspiao(ProfileManager):
    """`ProfileManager` REAL que registra as instâncias criadas.

    Real de propósito: o teste de wiring precisa ATIVAR um perfil pelo manager
    que o callsite construiu e contar a escrita no backend. Um dublê provaria
    apenas que a palavra `speaker_applier` foi digitada.
    """

    instancias: ClassVar[list[ProfileManager]] = []

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        _ManagerEspiao.instancias.append(self)


def _espionar_manager(monkeypatch: pytest.MonkeyPatch) -> None:
    _ManagerEspiao.instancias = []
    monkeypatch.setattr(manager_module, "ProfileManager", _ManagerEspiao)


# ---------------------------------------------------------------------------
# 1) O applier do daemon
# ---------------------------------------------------------------------------


class TestApplierDoDaemon:
    def test_escreve_o_par_completo_no_backend(self) -> None:
        backend = _BackendComAudio()
        backend.connect()
        estado = _daemon(backend).apply_profile_speaker(180, False)

        assert estado == "aplicado"
        assert backend.escritas_de_audio == [
            {"volume": 180, "muted": False, "uniq": None}
        ]
        assert backend.speaker_state_for() == {"volume": 180, "muted": False}

    def test_o_mudo_do_perfil_vai_junto_do_volume(self) -> None:
        """Mudo NUNCA viaja sozinho — mudo como primeira escrita tranca em zero."""
        backend = _BackendComAudio()
        backend.connect()
        _daemon(backend).apply_profile_speaker(180, True)

        assert backend.escritas_de_audio == [
            {"volume": 180, "muted": True, "uniq": None}
        ]
        assert backend.speaker_state_for() == {"volume": 180, "muted": True}

    def test_recusa_a_chamada_sem_volume_sem_escrever_nada(self) -> None:
        """MORDIDA: sem esta guarda o backend recebe `volume=None`, toma a posse
        dos bytes de áudio e manda ZERO — `{'volume': 0, 'muted': True}`, de
        onde nem o desmudo sai (a preferência guardada passa a valer 0)."""
        backend = _BackendComAudio()
        backend.connect()
        estado = _daemon(backend).apply_profile_speaker(None)  # type: ignore[arg-type]

        assert estado == "falhou"
        assert backend.escritas_de_audio == []
        assert backend.speaker_state_for() is None

    def test_repassa_o_uniq_do_controle(self) -> None:
        backend = _BackendComAudio()
        backend.connect()
        _daemon(backend).apply_profile_speaker(90, False, uniq="aabbcc000002")

        assert backend.escritas_de_audio == [
            {"volume": 90, "muted": False, "uniq": "aabbcc000002"}
        ]

    def test_volume_fora_do_range_e_grampeado(self) -> None:
        backend = _BackendComAudio()
        backend.connect()
        _daemon(backend).apply_profile_speaker(999, False)

        assert backend.escritas_de_audio == [
            {"volume": 255, "muted": False, "uniq": None}
        ]

    def test_sem_handle_diz_sem_controle_e_nao_mente_aplicado(self) -> None:
        backend = _BackendComAudio(sem_handle=True)
        assert _daemon(backend).apply_profile_speaker(180, False) == (
            "ignorado_sem_controle"
        )

    def test_backend_que_levanta_devolve_falhou(self) -> None:
        backend = _BackendComAudio(explode=True)
        backend.connect()
        assert _daemon(backend).apply_profile_speaker(180, False) == "falhou"

    def test_backend_sem_o_metodo_nao_derruba(self) -> None:
        """FakeController puro não tem `set_speaker_volume` — ausência é resposta."""
        daemon = Daemon(controller=FakeController(), config=DaemonConfig())
        assert daemon.apply_profile_speaker(180, False) == "ignorado_sem_controle"


# ---------------------------------------------------------------------------
# 2) A ARMADILHA: o applier não pode armar a trava manual
# ---------------------------------------------------------------------------


class TestNaoArmaATravaManual:
    def test_applier_nao_arma_a_categoria_audio(self) -> None:
        """O `speaker.set` do IPC arma `audio`; o applier de perfil NÃO pode.

        MORDIDA: pôr um `store.mark_manual_trigger_active("audio")` no applier
        (ou fazê-lo passar pelo handler do IPC, que o faz) reprova aqui e,
        pior, no teste seguinte — em produção o sintoma seria mudo: o perfil
        funcionaria uma vez e nunca mais.
        """
        backend = _BackendComAudio()
        backend.connect()
        daemon = _daemon(backend)

        daemon.apply_profile_speaker(180, False)

        assert "audio" not in daemon.store.manual_override_categories

    def test_segunda_ativacao_do_perfil_ainda_escreve(
        self, isolated_profiles_dir: Path
    ) -> None:
        """O teste mais importante da entrega.

        Se a primeira ativação armasse a trava de áudio, `apply_speaker`
        consultaria a trava na segunda e desistiria — o perfil pararia de
        funcionar depois do primeiro uso, em silêncio, e o relatório diria
        `ignorado_trava_manual` para um gesto que ela nunca fez.
        """
        save_profile(_perfil("som", speaker={"volume": 180}))
        backend = _BackendComAudio()
        backend.connect()
        daemon = _daemon(backend)
        manager = ProfileManager(
            controller=backend,
            store=daemon.store,
            speaker_applier=daemon.apply_profile_speaker,
        )

        relatorios = []
        for _ in range(3):
            relatorio: dict[str, str] = {}
            manager.activate("som", origin="autoswitch", relatorio=relatorio)
            relatorios.append(relatorio.get("speaker"))

        assert relatorios == ["aplicado", "aplicado", "aplicado"]
        assert [e["volume"] for e in backend.escritas_de_audio] == [180, 180, 180]

    def test_a_trava_armada_na_mao_bloqueia_a_ativacao_seguinte(
        self, isolated_profiles_dir: Path
    ) -> None:
        """A contraprova: a trava MORDE mesmo — por isso o applier não a arma.

        Aqui quem arma é ela (o `speaker.set` do IPC faz exatamente isto), e o
        autoswitch reaplicando o perfil não pisa o ajuste manual.
        """
        save_profile(_perfil("som", speaker={"volume": 180}))
        backend = _BackendComAudio()
        backend.connect()
        daemon = _daemon(backend)
        manager = ProfileManager(
            controller=backend,
            store=daemon.store,
            speaker_applier=daemon.apply_profile_speaker,
        )

        manager.activate("som", origin="autoswitch")
        backend.escritas_de_audio.clear()
        daemon.store.mark_manual_trigger_active("audio")  # o gesto dela
        relatorio: dict[str, str] = {}
        manager.activate("som", origin="autoswitch", relatorio=relatorio)

        assert backend.escritas_de_audio == []
        assert relatorio["speaker"] == "ignorado_trava_manual"


# ---------------------------------------------------------------------------
# 3) Pontos de injeção
# ---------------------------------------------------------------------------


def _ativar_pelo_manager_do_callsite(nome: str) -> ProfileManager:
    """Ativa `nome` pelo ÚLTIMO manager que o callsite construiu."""
    manager = _ManagerEspiao.instancias[-1]
    manager.activate(nome, origin="manual")
    return manager


class _IpcServerFalso:
    """Substitui o IpcServer: o teste é do manager, não do socket."""

    def __init__(self, **kwargs: Any) -> None:
        self.kwargs = kwargs

    async def start(self) -> None:
        return None

    async def stop(self) -> None:
        return None


class _AutoSwitcherFalso:
    """Substitui o AutoSwitcher: sem thread de poll no teste."""

    def __init__(self, **kwargs: Any) -> None:
        self.kwargs = kwargs

    def disabled(self) -> bool:
        return True

    def start(self) -> None:  # pragma: no cover - nunca chamado (disabled)
        return None

    def stop(self) -> None:
        return None


class _DaemonEnxuto:
    """Daemon mínimo que EMPRESTA o applier real de um `Daemon` de verdade.

    Os callsites fazem `getattr(daemon, "apply_profile_speaker", None)` — o que
    se prova aqui é que o nome está fiado e que a ponta escreve no backend.
    """

    def __init__(self, backend: _BackendComAudio) -> None:
        self.controller = backend
        self.store = StateStore()
        self.real = Daemon(controller=backend, store=self.store, config=DaemonConfig())
        self._keyboard_device = None

    def __getattr__(self, nome: str) -> Any:
        # Os appliers (`apply_profile_*`) e o resto da superfície vêm do Daemon
        # REAL — o que este dublê encena é só a forma do objeto que os callsites
        # recebem, não o comportamento dos appliers.
        return getattr(self.real, nome)

    async def _run_blocking(self, fn: Any, *args: Any) -> Any:
        return fn(*args)


class TestPontosDeInjecao:
    @pytest.mark.asyncio
    async def test_ipc_subsystem_injeta_o_applier(
        self, isolated_profiles_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        save_profile(_perfil("som", speaker={"volume": 180}))
        _espionar_manager(monkeypatch)
        monkeypatch.setattr(
            "hefesto_dualsense4unix.daemon.ipc_server.IpcServer", _IpcServerFalso
        )
        backend = _BackendComAudio()
        backend.connect()
        daemon = _DaemonEnxuto(backend)
        ctx = DaemonContext(
            controller=backend,
            bus=daemon.real.bus,
            store=daemon.store,
            config=DaemonConfig(),
        )
        ctx.daemon = daemon  # type: ignore[attr-defined]

        await ipc_mod.IpcSubsystem().start(ctx)
        _ativar_pelo_manager_do_callsite("som")

        assert [e["volume"] for e in backend.escritas_de_audio] == [180]

    @pytest.mark.asyncio
    async def test_start_ipc_injeta_o_applier(
        self, isolated_profiles_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        save_profile(_perfil("som", speaker={"volume": 180}))
        _espionar_manager(monkeypatch)
        monkeypatch.setattr(
            "hefesto_dualsense4unix.daemon.ipc_server.IpcServer", _IpcServerFalso
        )
        backend = _BackendComAudio()
        backend.connect()
        daemon = _DaemonEnxuto(backend)

        await ipc_mod.start_ipc(daemon)  # type: ignore[arg-type]
        _ativar_pelo_manager_do_callsite("som")

        assert [e["volume"] for e in backend.escritas_de_audio] == [180]

    @pytest.mark.asyncio
    async def test_autoswitch_subsystem_injeta_o_applier(
        self, isolated_profiles_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        save_profile(_perfil("som", speaker={"volume": 180}))
        _espionar_manager(monkeypatch)
        monkeypatch.setattr(autoswitch_mod, "_ensure_display_env", lambda: None)
        monkeypatch.setattr(
            "hefesto_dualsense4unix.profiles.autoswitch.AutoSwitcher",
            _AutoSwitcherFalso,
        )
        backend = _BackendComAudio()
        backend.connect()
        daemon = _DaemonEnxuto(backend)
        ctx = DaemonContext(
            controller=backend,
            bus=daemon.real.bus,
            store=daemon.store,
            config=DaemonConfig(),
        )
        ctx.daemon = daemon  # type: ignore[attr-defined]

        await autoswitch_mod.AutoswitchSubsystem().start(ctx)
        _ativar_pelo_manager_do_callsite("som")

        assert [e["volume"] for e in backend.escritas_de_audio] == [180]

    @pytest.mark.asyncio
    async def test_start_autoswitch_injeta_o_applier(
        self, isolated_profiles_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        save_profile(_perfil("som", speaker={"volume": 180}))
        _espionar_manager(monkeypatch)
        monkeypatch.setattr(autoswitch_mod, "_ensure_display_env", lambda: None)
        monkeypatch.setattr(
            "hefesto_dualsense4unix.profiles.autoswitch.AutoSwitcher",
            _AutoSwitcherFalso,
        )
        backend = _BackendComAudio()
        backend.connect()
        daemon = _DaemonEnxuto(backend)

        await autoswitch_mod.start_autoswitch(daemon)  # type: ignore[arg-type]
        _ativar_pelo_manager_do_callsite("som")

        assert [e["volume"] for e in backend.escritas_de_audio] == [180]

    @pytest.mark.asyncio
    async def test_ciclo_por_hotkey_aplica_o_volume_do_perfil(
        self, isolated_profiles_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """PS+D-pad é gesto dela: o perfil que entra leva o volume junto.

        Aqui a ativação é REAL (o callback cicla e chama `activate`), então
        arrancar o `speaker_applier=` de `subsystems/hotkey.py` zera as
        escritas e o teste reprova.
        """
        save_profile(_perfil("baixo", speaker={"volume": 60}))
        save_profile(_perfil("alto", speaker={"volume": 220}))
        monkeypatch.setattr(
            "hefesto_dualsense4unix.utils.session.save_active_marker",
            lambda _n: None,
        )
        monkeypatch.setattr(asyncio, "sleep", lambda _s: asyncio.sleep(0))
        backend = _BackendComAudio()
        backend.connect()
        daemon = Daemon(controller=backend, config=DaemonConfig())
        _sem_executor(daemon, monkeypatch)
        daemon.store.set_active_profile("alto")

        await build_profile_cycle_callback(daemon, +1)()  # type: ignore[arg-type]

        assert daemon.store.active_profile == "baixo"
        assert [e["volume"] for e in backend.escritas_de_audio] == [60]

    @pytest.mark.asyncio
    async def test_restore_de_boot_aplica_o_volume_do_perfil(
        self, isolated_profiles_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """O volume não tem flag persistido — o perfil é a única fonte no boot."""
        save_profile(_perfil("som", speaker={"volume": 140}))
        monkeypatch.setattr(
            "hefesto_dualsense4unix.utils.session.resolve_boot_profile",
            lambda: "som",
        )
        backend = _BackendComAudio()
        backend.connect()
        daemon = Daemon(controller=backend, config=DaemonConfig())
        _sem_executor(daemon, monkeypatch)

        await restore_last_profile(daemon)  # type: ignore[arg-type]

        assert [e["volume"] for e in backend.escritas_de_audio] == [140]

    @pytest.mark.asyncio
    async def test_restore_de_perfil_sem_a_secao_nao_escreve(
        self, isolated_profiles_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Perfil legado no boot não pode tomar a posse do alto-falante."""
        save_profile(_perfil("legado"))
        monkeypatch.setattr(
            "hefesto_dualsense4unix.utils.session.resolve_boot_profile",
            lambda: "legado",
        )
        backend = _BackendComAudio()
        backend.connect()
        daemon = Daemon(controller=backend, config=DaemonConfig())
        _sem_executor(daemon, monkeypatch)

        await restore_last_profile(daemon)  # type: ignore[arg-type]

        assert backend.escritas_de_audio == []
        assert backend.speaker_state_for() is None


# ---------------------------------------------------------------------------
# 4) Reaplicação no connect (armadilha 4: a posse morre com o cabo)
# ---------------------------------------------------------------------------


class TestReaplicacaoNoConnect:
    @pytest.mark.asyncio
    async def test_connect_reaplica_o_volume_do_perfil_ativo(
        self, isolated_profiles_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """MORDIDA: arrancar a chamada de `connect_with_retry` faz o replug
        perder o volume do perfil ativo — o handle novo nasce sem posse e o
        firmware volta a mandar no bloco, sem uma linha de aviso."""
        save_profile(_perfil("som", speaker={"volume": 180}))
        backend = _BackendComAudio()
        daemon = Daemon(controller=backend, config=DaemonConfig())
        _sem_executor(daemon, monkeypatch)
        daemon.store.set_active_profile("som")

        await connect_with_retry(daemon)  # type: ignore[arg-type]

        assert [e["volume"] for e in backend.escritas_de_audio] == [180]

    @pytest.mark.asyncio
    async def test_connect_com_perfil_sem_secao_nao_escreve(
        self, isolated_profiles_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Reaplicar sem seção seria tomar a posse sem pedido a CADA replug."""
        save_profile(_perfil("legado"))
        backend = _BackendComAudio()
        daemon = Daemon(controller=backend, config=DaemonConfig())
        _sem_executor(daemon, monkeypatch)
        daemon.store.set_active_profile("legado")

        await connect_with_retry(daemon)  # type: ignore[arg-type]

        assert backend.escritas_de_audio == []
        assert backend.speaker_state_for() is None

    @pytest.mark.asyncio
    async def test_connect_sem_perfil_ativo_nao_escreve(
        self, isolated_profiles_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        backend = _BackendComAudio()
        daemon = Daemon(controller=backend, config=DaemonConfig())
        _sem_executor(daemon, monkeypatch)

        await connect_with_retry(daemon)  # type: ignore[arg-type]

        assert backend.escritas_de_audio == []

    @pytest.mark.asyncio
    async def test_connect_respeita_a_trava_manual_de_audio(
        self, isolated_profiles_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Se ela mexeu no volume na mão, a reconexão não devolve o campo ao perfil."""
        save_profile(_perfil("som", speaker={"volume": 180}))
        backend = _BackendComAudio()
        daemon = Daemon(controller=backend, config=DaemonConfig())
        _sem_executor(daemon, monkeypatch)
        daemon.store.set_active_profile("som")
        daemon.store.mark_manual_trigger_active("audio")

        await connect_with_retry(daemon)  # type: ignore[arg-type]

        assert backend.escritas_de_audio == []

    @pytest.mark.asyncio
    async def test_reaplicacao_roteia_o_uniq_do_controle_que_chegou(
        self, isolated_profiles_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        save_profile(_perfil("som", speaker={"volume": 90}))
        backend = _BackendComAudio()
        daemon = Daemon(controller=backend, config=DaemonConfig())
        _sem_executor(daemon, monkeypatch)
        daemon.store.set_active_profile("som")

        await reapply_speaker_after_connect(  # type: ignore[arg-type]
            daemon, uniq="aabbcc000002"
        )

        assert backend.escritas_de_audio == [
            {"volume": 90, "muted": False, "uniq": "aabbcc000002"}
        ]

    @pytest.mark.asyncio
    async def test_daemon_sem_store_nao_quebra_a_conexao(self) -> None:
        """Daemon enxuto (CLI/testes antigos) não reaplica e não levanta."""

        class _Cru:
            controller = _BackendComAudio()

            async def _run_blocking(self, fn: Any, *args: Any) -> Any:
                return fn(*args)

        await reapply_speaker_after_connect(_Cru())  # type: ignore[arg-type]

    @pytest.mark.asyncio
    async def test_a_reaplicacao_nao_arma_a_trava_manual(
        self, isolated_profiles_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Um replug que armasse `audio` faria a PRÓXIMA troca de perfil ser
        descartada por uma trava que nenhum gesto dela armou."""
        save_profile(_perfil("som", speaker={"volume": 180}))
        backend = _BackendComAudio()
        daemon = Daemon(controller=backend, config=DaemonConfig())
        _sem_executor(daemon, monkeypatch)
        daemon.store.set_active_profile("som")

        await reapply_speaker_after_connect(daemon)  # type: ignore[arg-type]

        assert "audio" not in daemon.store.manual_override_categories


# ---------------------------------------------------------------------------
# 5) Conexão de ponta a ponta (o ciclo que ela vive: perfil, replug, perfil)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ciclo_perfil_replug_perfil_nunca_perde_o_volume(
    isolated_profiles_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ativa, reconecta duas vezes, troca de perfil — sempre com escrita.

    É o encadeamento inteiro num teste só: se qualquer elo (applier, trava,
    gancho do connect) se soltar, o volume some de um dos passos.
    """
    save_profile(_perfil("baixo", speaker={"volume": 60}))
    save_profile(_perfil("alto", speaker={"volume": 220}))
    backend = _BackendComAudio()
    daemon = Daemon(controller=backend, config=DaemonConfig())
    _sem_executor(daemon, monkeypatch)
    manager = ProfileManager(
        controller=backend,
        store=daemon.store,
        speaker_applier=daemon.apply_profile_speaker,
    )

    manager.activate("baixo", origin="manual")
    await connect_with_retry(daemon)  # type: ignore[arg-type]
    await connect_with_retry(daemon)  # type: ignore[arg-type]
    manager.activate("alto", origin="autoswitch")
    await connect_with_retry(daemon)  # type: ignore[arg-type]

    assert [e["volume"] for e in backend.escritas_de_audio] == [60, 60, 60, 220, 220]
    assert backend.speaker_state_for() == {"volume": 220, "muted": False}
    assert connection_mod.reapply_speaker_after_connect is not None
