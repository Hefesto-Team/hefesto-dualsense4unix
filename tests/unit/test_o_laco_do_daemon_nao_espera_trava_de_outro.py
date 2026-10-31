"""O laço do daemon nunca espera trava de outro — O-LACO-DO-DAEMON-NUNCA-ESPERA-TRAVA-DE-OUTRO-01.

Medido em 31/10/2026 (``vigia_do_laco``, ``laco_parado segundos=10``): o arme do lançamento
esperava a ``_TRAVA_DA_ESCRITA`` que o fio escrevente segurava 21 s (``fora_ms=21065``), e o
tique da luz esperava o ``FileLock`` do perfil que outro processo segurava. Cada régua segura
a trava noutro fio por ``SEGURA_S`` e mede que o laço volta antes de ``TETO_S``.
"""
from __future__ import annotations

import asyncio
import threading
import time
from collections.abc import Callable, Iterator
from pathlib import Path
from types import SimpleNamespace
from typing import Any, TypeVar

import pytest
from filelock import FileLock

from hefesto_dualsense4unix.daemon import launch_env as le
from hefesto_dualsense4unix.daemon.subsystems import luz_animada
from hefesto_dualsense4unix.profiles import loader
from hefesto_dualsense4unix.profiles.schema import MatchCriteria, Profile, ProfileModeConfig

SEGURA_S = 3.0
TETO_S = 0.1
APPID = 9931031
T = TypeVar("T")


class _Dono:
    """Segura uma trava noutro fio até ``soltar`` (ou ``SEGURA_S``)."""

    def __init__(self, trava: Any) -> None:
        self._trava = trava
        self._pegou = threading.Event()
        self._solta = threading.Event()
        self._fio = threading.Thread(target=self._segurar, daemon=True)

    def _segurar(self) -> None:
        with self._trava:
            self._pegou.set()
            self._solta.wait(SEGURA_S)

    def __enter__(self) -> _Dono:
        self._fio.start()
        assert self._pegou.wait(2.0), "o dono não pegou a trava"
        return self

    def __exit__(self, *_exc: object) -> None:
        self._solta.set()
        self._fio.join(SEGURA_S + 1.0)


def _no_laco(fazer: Callable[[], T]) -> tuple[T, float]:
    """``fazer`` no fio de um laço asyncio vivo, e o tempo que o laço gastou ali."""

    async def corpo() -> tuple[T, float]:
        t0 = time.perf_counter()
        valor = fazer()
        return valor, time.perf_counter() - t0

    return asyncio.run(corpo())


def _perfil(nome: str = "Jogo da Régua") -> Profile:
    return Profile(
        name=nome,
        match=MatchCriteria(window_class=[f"steam_app_{APPID}"]),
        priority=90,
        mode=ProfileModeConfig(kind="gamepad", gamepad_flavor="dualsense"),
    )


class _DaemonFalso:
    def __init__(self) -> None:
        self.config = SimpleNamespace(gamepad_emulation_enabled=True, gamepad_flavor="xbox")
        self._gamepad_device = SimpleNamespace(backend="uinput")
        self._coop_manager = None
        self.controller = SimpleNamespace()

    def is_native_mode(self) -> bool:
        return False

    def apply_profile_mode(self, mode: Any, *, profile: Any = None, origin: str = "") -> str:
        return "aplicado"

    def apply_profile_suppression(
        self, desired: bool, *, profile: Any = None, origin: str = ""
    ) -> str:
        return "aplicado"


def _foto() -> Any:
    return le._FotoDoLancamento(
        ordem=next(le._ORDEM_DAS_FOTOS), native=False, enabled=True,
        flavor="dualsense", backends=(), fisicos=1, modo_vivo=None,  # type: ignore[arg-type]
        em_cena=frozenset(), identidade=None, permite_uhid=False, vpads_previstos=0,
        leitor=None, publicar=lambda _d: None, carimbar=lambda: None, foto_ms=0.0)


@pytest.fixture
def sem_escrevente(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setattr(le, "_ESCREVENTE", None)
    yield
    escrevente = le._ESCREVENTE
    if escrevente is not None:
        le.desarmar_o_escrevente(escrevente)


def test_o_arme_do_lancamento_nao_espera_a_escrita_do_fio_escrevente(
    sem_escrevente: None, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """O arme pede a escrita ao fio escrevente e volta, com a trava da escrita ocupada."""
    from hefesto_dualsense4unix.profiles import manager

    (tmp_path / "last_run").write_text(f"appid={APPID}\nepoch=1000\npid=1\n", encoding="utf-8")
    perfil = _perfil()
    monkeypatch.setattr(le, "launch_env_dir", lambda ensure=False: tmp_path)
    monkeypatch.setattr(le, "_steam_profiles", lambda _daemon: [(APPID, perfil)])
    monkeypatch.setattr(le, "steam_input_appids", lambda path=None: set())
    monkeypatch.setattr(le, "_foto_do_lancamento", lambda _daemon, *, no_fio: _foto())
    monkeypatch.setattr(le, "_a_parte_de_fora", lambda _foto, _devolver: None)
    monkeypatch.setattr(
        manager, "gerente_do_daemon",
        lambda daemon, **kw: SimpleNamespace(activate=lambda *a, **k: None))
    daemon = _DaemonFalso()

    def armar() -> tuple[Any, Any]:
        laco = asyncio.get_running_loop()
        escrevente = le.armar_o_escrevente(laco.call_soon_threadsafe, laco)
        assert escrevente is not None
        with _Dono(le._TRAVA_DA_ESCRITA):
            t0 = time.perf_counter()
            resultado = le.arm_launch_profile(daemon, base_dir=tmp_path, now=1001.0)
            gasto = time.perf_counter() - t0
        return (resultado, escrevente), gasto

    async def corpo() -> tuple[Any, float]:
        return armar()

    (resultado, escrevente), gasto = asyncio.run(corpo())
    assert resultado is not None and resultado["armado"] is True
    assert gasto < TETO_S, (
        f"o arme ficou {gasto:.2f} s no laço esperando a trava da escrita de outro fio")
    assert escrevente.em_voo() or escrevente.escritas >= 1, (
        "o arme não pediu a escrita do lançamento ao fio escrevente")


@pytest.mark.parametrize("pela_assinatura", [False, True], ids=["direto", "pela-assinatura"])
def test_o_tique_da_luz_nao_espera_o_filelock_do_perfil(
    monkeypatch: pytest.MonkeyPatch, pela_assinatura: bool
) -> None:
    """A luz lê o perfil ativo no laço com o ``FileLock`` dele nas mãos de outro dono."""
    monkeypatch.setenv(loader.SEED_SKIP_ENV_VAR, "1")
    monkeypatch.setattr(loader, "_LEITURA_LIGADA_PELO_PROCESSO", pela_assinatura)
    loader._PERFIS_PELA_ASSINATURA.esquecer()
    caminho = loader.save_profile(_perfil())
    daemon = SimpleNamespace(store=SimpleNamespace(active_profile="Jogo da Régua"))
    with _Dono(FileLock(str(loader._lock_path(caminho)))):
        perfil, gasto = _no_laco(lambda: luz_animada.perfil_ativo(daemon))
    loader._PERFIS_PELA_ASSINATURA.esquecer()
    assert gasto < TETO_S, (
        f"o tique da luz ficou {gasto:.2f} s no laço esperando o FileLock do perfil")
    assert perfil is not None and perfil.name == "Jogo da Régua"


def test_a_carga_dos_perfis_no_laco_nao_espera_o_filelock(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``perfis_para_consulta`` (o autoswitch, o arme) no laço, com o perfil travado por outro."""
    monkeypatch.setenv(loader.SEED_SKIP_ENV_VAR, "1")
    monkeypatch.setattr(loader, "_talvez_semear_jogos", lambda: None)
    caminho = loader.save_profile(_perfil())
    with _Dono(FileLock(str(loader._lock_path(caminho)))):
        perfis, gasto = _no_laco(loader.perfis_para_consulta)
    assert gasto < TETO_S, (
        f"a carga dos perfis ficou {gasto:.2f} s no laço esperando o FileLock")
    assert "Jogo da Régua" in {p.name for p in perfis}


def test_fora_do_laco_a_leitura_segue_esperando_quem_grava(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Fora do laço asyncio (a CLI, a janela, os fios), a leitura continua sob o ``FileLock``."""
    monkeypatch.setenv(loader.SEED_SKIP_ENV_VAR, "1")
    caminho = loader.save_profile(_perfil())
    assert isinstance(loader._trava_da_leitura(caminho), FileLock)
    _trava, _ = _no_laco(lambda: loader._trava_da_leitura(caminho))
    assert not isinstance(_trava, FileLock)
