"""A MÁSCARA DO GESTO VOLTA PARA O PERFIL (29/08/2026), e o degrau caro guarda."""
from __future__ import annotations

import json
import time
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from hefesto_dualsense4unix.daemon import launch_env as le
from hefesto_dualsense4unix.daemon.subsystems import hotkey as hotkey_sub
from hefesto_dualsense4unix.integrations import ponte_escada as pe
from hefesto_dualsense4unix.integrations import ponte_tentativa as pt
from hefesto_dualsense4unix.profiles.loader import load_all_profiles, save_profile
from hefesto_dualsense4unix.profiles.schema import (
    CONFIRMADA_POR_GESTO,
    MatchCriteria,
    PonteConfirmada,
    Profile,
    ProfileModeConfig,
)

RAIZ = Path(__file__).resolve().parents[2]
FIXTURE = (
    RAIZ / "tests" / "fixtures" / "perfis" / "mullet_mad_jack-carimbo-que-ela-desmente.json"
)
APPID = 2111190
EPOCH = 1000


def _perfil_dela() -> Profile:
    """O perfil do usuário, da CÓPIA. Nunca do diretório em que ela joga."""
    return Profile.model_validate(json.loads(FIXTURE.read_text(encoding="utf-8")))


def _no_disco() -> Profile:
    """O perfil como ficou em disco — releitura, não o objeto em memória."""
    perfis = [p for p in load_all_profiles() if p.name == "Mullet Mad Jack"]
    assert len(perfis) == 1, f"esperava um perfil no disco, achei {len(perfis)}"
    return perfis[0]


class _Daemon:
    """Um daemon só, porque as duas frentes atravessam o gesto E o lançamento."""

    def __init__(self, *, flavor: str = "dualsense") -> None:
        self.controller = SimpleNamespace()
        self.store = SimpleNamespace(
            native_mode_active=False,
            bump=lambda chave: None,
            window_detect_current_class=None,
            window_detect_last_class=None,
        )
        self.display_authority = "game"
        self.config = SimpleNamespace(
            gamepad_emulation_enabled=True, gamepad_flavor=flavor, gamepad_caminho=None
        )
        self._gamepad_device: Any = SimpleNamespace(backend="uhid", flavor=flavor)
        self._coop_manager = None
        self.pedidos: list[tuple[bool, str | None, str, str | None]] = []
        self.aplicados: list[Any] = []

    async def _run_blocking(self, fn: Any, *args: Any) -> Any:
        return fn(*args)

    def set_gamepad_emulation(
        self,
        enabled: bool,
        flavor: str | None = None,
        *,
        origin: str = "manual",
        caminho: str | None = None,
        grava_o_modo: Any = False,
    ) -> bool:
        self.pedidos.append((enabled, flavor, origin, caminho))
        if enabled:
            if flavor is not None:
                self.config.gamepad_flavor = flavor
            self.config.gamepad_caminho = caminho or self.config.gamepad_caminho
            self._gamepad_device = SimpleNamespace(
                backend="uinput" if caminho == "xbox" else "uhid",
                flavor=self.config.gamepad_flavor,
            )
        else:
            self._gamepad_device = None
        return True

    def set_mouse_emulation(self, enabled: bool, *, origin: str = "profile") -> bool:
        return enabled

    def set_keyboard_emulation(self, enabled: bool) -> bool:
        return enabled

    def set_emulation_suppressed(self, value: bool | None = None) -> bool:
        return bool(value)

    def is_native_mode(self) -> bool:
        return False

    def apply_profile_mode(
        self, mode: Any, *, profile: Any = None, origin: str = "autoswitch"
    ) -> str:
        self.aplicados.append(mode)
        if getattr(mode, "kind", None) == "gamepad":
            self.config.gamepad_flavor = mode.gamepad_flavor
            self.config.gamepad_caminho = getattr(mode, "caminho", None)
            self._gamepad_device = SimpleNamespace(
                backend="uhid", flavor=mode.gamepad_flavor
            )
        else:
            self._gamepad_device = None
            self.config.gamepad_emulation_enabled = False
        return "aplicado"


@pytest.fixture(autouse=True)
def _sem_espera(monkeypatch: pytest.MonkeyPatch) -> None:
    """Zera a lightbar: estas réguas medem DECISÃO, não relógio."""
    monkeypatch.setattr(hotkey_sub, "PULSO_SEG", 0.0)


@pytest.fixture
def jogo_dela(monkeypatch: pytest.MonkeyPatch) -> int:
    """O appid que o wrapper diria estar rodando — o MESMO sinal do produto."""
    monkeypatch.setattr(le, "launch_session_appid", lambda **kw: APPID)
    return APPID


@pytest.fixture
def env_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(le, "launch_env_dir", lambda ensure=False: tmp_path)
    monkeypatch.setattr(le, "materialize_launch_env", lambda daemon: None)
    monkeypatch.setattr(le, "steam_input_appids", lambda path=None: set())
    (tmp_path / "last_run").write_text(
        f"appid={APPID}\nepoch={EPOCH}\npid=1\n", encoding="utf-8"
    )
    return tmp_path


class TestOGestoDelaChegaAoPerfil:
    @pytest.mark.asyncio
    async def test_o_perfil_dela_vira_xbox_depois_do_silencio(
        self, jogo_dela: int
    ) -> None:
        """A sequência inteira, do arquivo dela até o arquivo dela."""
        save_profile(_perfil_dela(), origem="teste")
        antes = _no_disco()
        assert antes.mode is not None and antes.mode.gamepad_flavor == "dualsense"
        assert antes.ponte is not None and antes.ponte.gamepad_flavor == "dualsense"

        d = _Daemon(flavor="dualsense")
        await hotkey_sub.build_next_bridge_callback(d)()  # type: ignore[arg-type]
        assert d.pedidos == [(True, None, "manual", "xbox")], "o gesto tem de obedecer"

        gesto = pt.gesto_em_curso(d)
        assert gesto is not None, "o gesto dela não deixou rastro"
        assert gesto.appid == APPID
        assert gesto.ponte == pe.ESCADA[1].ponte

        le.tique_da_escada(d, agora=gesto.ultimo_gesto + pe.SILENCIO_CONFIRMA_SEC - 1)
        meio = _no_disco()
        assert meio.mode is not None and meio.mode.gamepad_flavor == "dualsense"
        assert meio.mode.caminho is None

        le.tique_da_escada(d, agora=gesto.ultimo_gesto + pe.SILENCIO_CONFIRMA_SEC + 1)

        depois = _no_disco()
        assert depois.mode is not None
        assert depois.mode.caminho == "xbox", "o caminho do gesto não voltou"
        assert depois.mode.gamepad_flavor == "dualsense", "o gesto reescreveu a máscara"
        assert depois.ponte is not None
        assert depois.ponte.gamepad_flavor == "xbox", "o carimbo velho ficou"
        assert depois.ponte.confirmada_por == CONFIRMADA_POR_GESTO
        assert depois.ponte.confirmada_em != antes.ponte.confirmada_em

    @pytest.mark.asyncio
    async def test_o_resto_do_perfil_dela_nao_e_tocado(self, jogo_dela: int) -> None:
        """Alinhar a máscara não pode reescrever o perfil ao redor dela."""
        save_profile(_perfil_dela(), origem="teste")
        antes = _no_disco()

        d = _Daemon(flavor="dualsense")
        await hotkey_sub.build_next_bridge_callback(d)()  # type: ignore[arg-type]
        gesto = pt.gesto_em_curso(d)
        assert gesto is not None
        le.tique_da_escada(d, agora=gesto.ultimo_gesto + pe.SILENCIO_CONFIRMA_SEC + 1)

        depois = _no_disco()
        assert depois.priority == antes.priority
        assert depois.match == antes.match
        assert depois.triggers == antes.triggers
        assert depois.leds == antes.leds
        assert depois.rumble == antes.rumble
        assert antes.mode is not None and depois.mode is not None
        assert depois.mode.kind == antes.mode.kind

    @pytest.mark.asyncio
    async def test_o_lancamento_seguinte_arma_xbox_e_para_de_perguntar(
        self, jogo_dela: int, env_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A entrega vista do lado dela: o aperto seguinte não acontece."""
        save_profile(_perfil_dela(), origem="teste")
        d = _Daemon(flavor="dualsense")
        await hotkey_sub.build_next_bridge_callback(d)()  # type: ignore[arg-type]
        gesto = pt.gesto_em_curso(d)
        assert gesto is not None
        le.tique_da_escada(d, agora=gesto.ultimo_gesto + pe.SILENCIO_CONFIRMA_SEC + 1)

        gravado = _no_disco()
        monkeypatch.setattr(le, "_steam_profiles", lambda dd: [(APPID, gravado)])
        outro = _Daemon(flavor="dualsense")
        outro.display_authority = "unknown"

        resultado = le.arm_launch_profile(outro, base_dir=env_dir, now=EPOCH + 1.0)

        assert resultado is not None
        assert resultado["armado"] is True
        assert resultado["ponte"] == "gamepad/xbox"
        assert outro.config.gamepad_caminho == "xbox", "armou o caminho de novo errado"
        assert resultado["escada"] == pt.COMECO_PRODUTO_JA_SABE

    @pytest.mark.asyncio
    async def test_sem_jogo_do_wrapper_o_gesto_nao_escreve_em_perfil_nenhum(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Ela mexendo na mesa, fora de uma partida, não é opinião sobre jogo."""
        monkeypatch.setattr(le, "launch_session_appid", lambda **kw: None)
        save_profile(_perfil_dela(), origem="teste")

        d = _Daemon(flavor="dualsense")
        await hotkey_sub.build_next_bridge_callback(d)()  # type: ignore[arg-type]

        assert d.pedidos == [(True, None, "manual", "xbox")], "o gesto tem de obedecer"
        assert pt.gesto_em_curso(d) is None
        le.tique_da_escada(d, agora=time.monotonic() + 1e6)
        assert _no_disco().mode.gamepad_flavor == "dualsense"  # type: ignore[union-attr]
        assert _no_disco().mode.caminho is None  # type: ignore[union-attr]

    @pytest.mark.asyncio
    async def test_jogo_fechado_no_meio_nao_carimba_nada(
        self, jogo_dela: int
    ) -> None:
        """Silêncio com o jogo fechado é ela tendo ido embora, não aprovação."""
        save_profile(_perfil_dela(), origem="teste")
        d = _Daemon(flavor="dualsense")
        await hotkey_sub.build_next_bridge_callback(d)()  # type: ignore[arg-type]
        gesto = pt.gesto_em_curso(d)
        assert gesto is not None

        d.display_authority = "unknown"
        le.tique_da_escada(d, agora=gesto.ultimo_gesto + pe.SILENCIO_CONFIRMA_SEC + 1)

        assert pt.gesto_em_curso(d) is None
        depois = _no_disco()
        assert depois.mode is not None and depois.mode.gamepad_flavor == "dualsense"
        assert depois.mode.caminho is None
        assert depois.ponte is not None
        assert depois.ponte.confirmada_em == _perfil_dela().ponte.confirmada_em  # type: ignore[union-attr]

    @pytest.mark.asyncio
    async def test_mouse_teclado_nao_vira_modo_de_perfil_de_jogo(
        self, jogo_dela: int
    ) -> None:
        """A terceira ponte do ciclo não é degrau da escada, e não se grava."""
        save_profile(_perfil_dela(), origem="teste")
        d = _Daemon(flavor="xbox")

        await hotkey_sub.build_next_bridge_callback(d)()  # type: ignore[arg-type]

        assert d.pedidos == [(False, None, "manual", None)], "premissa: foi para o desktop"
        assert pt.gesto_em_curso(d) is None
        le.tique_da_escada(d, agora=time.monotonic() + 1e6)
        assert _no_disco().mode.kind == "gamepad"  # type: ignore[union-attr]


def _perfil_antes_do_gesto() -> Profile:
    """O estado dos três casos do journal, e é o dela: o ARQUIVO diz"""
    return Profile(
        name="Mullet Mad Jack",
        match=MatchCriteria(window_class=[f"steam_app_{APPID}"]),
        priority=80,
        mode=ProfileModeConfig(kind="gamepad", gamepad_flavor="dualsense"),
    )


class TestODegrauCaroNaoCustaAPartida:
    @pytest.mark.asyncio
    async def test_a_sequencia_do_journal_termina_em_xbox_gravado(
        self, jogo_dela: int
    ) -> None:
        """As quatro linhas do journal, reproduzidas, e o desfecho trocado."""
        save_profile(_perfil_antes_do_gesto(), origem="teste")
        d = _Daemon(flavor="xbox")
        d._ponte_tentativa = pt.Tentativa(
            appid=APPID,
            epoch=EPOCH,
            degrau=pe.ESCADA[1],
            ultimo_gesto=0.0,
            viu_o_jogo=True,
            gestos=2,
        )

        await hotkey_sub.build_next_bridge_callback(d)()  # type: ignore[arg-type]

        assert d.pedidos == [(False, None, "manual", None)], "o aperto dela foi comido"
        assert pt.em_curso(d) is None, "a tentativa tinha de ser encerrada"

        le.tique_da_escada(d)

        gravado = _no_disco()
        assert gravado.mode is not None
        assert gravado.mode.caminho == "xbox", "o degrau de pé evaporou"

    @pytest.mark.asyncio
    async def test_o_degrau_caro_nao_carimba_e_a_escada_continua_aberta(
        self, jogo_dela: int, env_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """O CUIDADO da frente: não matar o caminho para o Nativo."""
        save_profile(_perfil_antes_do_gesto(), origem="teste")
        d = _Daemon(flavor="xbox")
        d._ponte_tentativa = pt.Tentativa(
            appid=APPID,
            epoch=EPOCH,
            degrau=pe.ESCADA[1],
            ultimo_gesto=0.0,
            viu_o_jogo=True,
            gestos=2,
        )
        await hotkey_sub.build_next_bridge_callback(d)()  # type: ignore[arg-type]
        le.tique_da_escada(d)

        gravado = _no_disco()
        assert gravado.ponte is None, "carimbou o degrau que ela acabou de recusar"

        for adiante in (60.0, 120.0, 181.0):
            le.tique_da_escada(d, agora=EPOCH + adiante)
            depois = _no_disco()
            assert depois.ponte is None, (
                f"{adiante:.0f}s depois do degrau caro, o produto carimbou "
                f"sozinho o degrau que ela recusou: {depois.ponte}"
            )
            assert depois.mode is not None and depois.mode.caminho == "xbox", (
                "o alinhamento do mode não sobreviveu ao tique seguinte — "
                "alinhar NÃO é confirmar, e o mode é o que vale no próximo "
                "lançamento"
            )

        monkeypatch.setattr(le, "_steam_profiles", lambda dd: [(APPID, gravado)])
        outro = _Daemon(flavor="dualsense")
        outro.display_authority = "unknown"

        resultado = le.arm_launch_profile(outro, base_dir=env_dir, now=EPOCH + 1.0)

        assert resultado is not None
        assert pe.ESCADA[2].ponte.kind == pe.KIND_NATIVE, "premissa do teste"
        assert resultado["ponte"] == "gamepad/xbox", "o degrau dela não voltou"
        assert outro.config.gamepad_caminho == "xbox"
        assert resultado["escada"] == pt.COMECO_PERFIL_MANDA
        tentativa = pt.em_curso(outro)
        assert tentativa is not None, "a escada fechou num jogo sem carimbo"
        assert tentativa.degrau == pe.ESCADA[1], "a tentativa recomeçou de baixo"
        assert (
            pe.proximo_degrau(ponte_atual=tentativa.ponte) == pe.ESCADA[2]
        ), "o Nativo deixou de ser o próximo"

    @pytest.mark.asyncio
    async def test_o_alinhamento_sobrevive_ao_jogo_fechando(
        self, jogo_dela: int
    ) -> None:
        """Alinhar o `mode` NÃO é confirmar, e por isso não espera silêncio."""
        save_profile(_perfil_antes_do_gesto(), origem="teste")
        d = _Daemon(flavor="xbox")
        d._ponte_tentativa = pt.Tentativa(
            appid=APPID,
            epoch=EPOCH,
            degrau=pe.ESCADA[1],
            ultimo_gesto=0.0,
            viu_o_jogo=True,
            gestos=2,
        )
        await hotkey_sub.build_next_bridge_callback(d)()  # type: ignore[arg-type]

        d.display_authority = "unknown"
        le.tique_da_escada(d)

        gravado = _no_disco()
        assert gravado.mode is not None
        assert gravado.mode.caminho == "xbox"
        assert gravado.ponte is None


class TestOQueNenhumaDasDuasFaz:
    @pytest.mark.asyncio
    async def test_jogo_sem_perfil_nao_ganha_arquivo(
        self, jogo_dela: int
    ) -> None:
        """Criar perfil nas costas dela tem uma porta só, e é o editor."""
        d = _Daemon(flavor="dualsense")
        await hotkey_sub.build_next_bridge_callback(d)()  # type: ignore[arg-type]
        gesto = pt.gesto_em_curso(d)
        assert gesto is not None

        le.tique_da_escada(d, agora=gesto.ultimo_gesto + pe.SILENCIO_CONFIRMA_SEC + 1)

        assert load_all_profiles() == []

    @pytest.mark.asyncio
    async def test_o_silencio_sem_gesto_continua_carimbando_por_silencio(
        self, jogo_dela: int
    ) -> None:
        """A escada sem gesto nenhum não muda de origem NEM alinha o `mode`."""
        sem_modo = Profile(
            name="Mullet Mad Jack",
            match=MatchCriteria(window_class=[f"steam_app_{APPID}"]),
            priority=80,
        )
        save_profile(sem_modo, origem="teste")
        d = _Daemon(flavor="dualsense")
        d._ponte_tentativa = pt.Tentativa(
            appid=APPID,
            epoch=EPOCH,
            degrau=pe.ESCADA[0],
            ultimo_gesto=0.0,
            viu_o_jogo=True,
            gestos=0,
        )

        le.tique_da_escada(d, agora=pe.SILENCIO_CONFIRMA_SEC + 1)

        gravado = _no_disco()
        assert gravado.ponte is not None
        assert gravado.ponte.confirmada_por == "silencio"
        assert gravado.mode is None, "escreveu `mode` num perfil sem opinião"

    def test_a_fixture_e_o_estado_dela_de_29_08(self) -> None:
        """A régua da própria régua: se a cópia mudar, o teste deixa de medir"""
        perfil = _perfil_dela()
        assert perfil.mode is not None
        assert perfil.mode.gamepad_flavor == "dualsense"
        assert perfil.ponte == PonteConfirmada(
            kind="gamepad",
            gamepad_flavor="dualsense",
            steam_input=False,
            confirmada_em="2026-08-29T03:23:13-03:00",
            confirmada_por="silencio",
        )
