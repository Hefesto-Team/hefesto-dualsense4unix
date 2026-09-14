"""PS-L3-MASCARA-01 — o PS + L3 anda pelas MÁSCARAS, grava no perfil e não mexe no modo.

O pedido dela, 14/09/2026, com a grafia dela: *"preciso que o ps+ l3 funcione
igual o ps /+ r3 que muda o modo porém para as máscaras. a ideia é que eu
nao precise fechar o jogo (noqa-acento: citação literal)
pra ajustar ingame isso e continuar a jogar."*

A bancada é a da `test_o_ps_r3_anda_por_caminhos_e_grava_no_perfil.py`: o
callback REAL do gesto (`hotkey.build_next_mask_callback`), o handler REAL do
chip do cartão (`IpcHandlersMixin._handle_gamepad_mask_set`) e os métodos REAIS
do `lifecycle.Daemon`; dublados só o vpad, o grab, o launch env, as flags de
sessão, o co-op e a lightbar. O perfil ativo é achado pela perna do disco.

MORDE, e são quatro curas independentes (medidas em 14/09, uma de cada vez):

* o gesto escrever só o registro, sem o handler do cartão — o vpad não troca e o
  perfil ativo fica como estava;
* `mascara_atual` ler o registro em vez do vpad — o aparelho que não vestiu a
  máscara ganha a cor dela na barra;
* tirar o `on_next_mask` do `start_hotkey_manager` — o combo dispara no vazio;
* tirar o `"mascara"` do despacho do `HotkeyManager` — idem, pelo outro lado.
"""
from __future__ import annotations

import functools
import threading
from collections.abc import Iterator
from types import SimpleNamespace
from typing import Any

import pytest

from hefesto_dualsense4unix.daemon import lifecycle
from hefesto_dualsense4unix.daemon.ipc_handlers import IpcHandlersMixin
from hefesto_dualsense4unix.daemon.subsystems import coop as coop_mod
from hefesto_dualsense4unix.daemon.subsystems import external_mask as em
from hefesto_dualsense4unix.daemon.subsystems import gamepad as gp
from hefesto_dualsense4unix.daemon.subsystems import hotkey
from hefesto_dualsense4unix.integrations import virtual_pad as vp
from hefesto_dualsense4unix.integrations.hotkey_daemon import (
    DEFAULT_COMBO_MASCARA,
    HotkeyManager,
)
from hefesto_dualsense4unix.profiles import loader
from hefesto_dualsense4unix.profiles.schema import (
    ControllerOverrides,
    MatchAny,
    Profile,
    ProfileModeConfig,
)
from hefesto_dualsense4unix.utils import session, xdg_paths

#: A faixa sintética da casa — nada de endereço real em arquivo versionado.
P1 = "aabbcc000001"
PERFIL = "Bancada"


class _Vpad:
    """O vpad de mentira. O canal sai da regra do produto (`quer_uhid`)."""

    def __init__(self, mascara: str, identity: str | None, caminho: str | None) -> None:
        self.flavor = mascara
        self.identity = identity
        self.backend = "uhid" if vp.quer_uhid(caminho, mascara) else "uinput"
        vp._pendurar_o_caminho(self, vp.caminho_resolvido(caminho, mascara))

    def stop(self) -> None:
        return


def _fabrica(flavor: Any, *, identity: Any = None, caminho: Any = None, **_kw: Any) -> _Vpad:
    return _Vpad(em.mascara_efetiva(identity, flavor), identity, caminho)


def _parar(daemon: Any, *, persist: bool = True, release_grab: bool = True) -> None:
    daemon._gamepad_device = None
    daemon.config.gamepad_emulation_enabled = False


class _Servidor(IpcHandlersMixin):
    """O servidor IPC com os handlers REAIS — só o que o handler da máscara lê."""

    def __init__(self, daemon: Any) -> None:
        self.daemon = daemon
        self.store = None


class _Daemon:
    """Os métodos REAIS do `lifecycle.Daemon`, amarrados a um objeto sem aparelho."""

    def __init__(self) -> None:
        self.config = SimpleNamespace(
            gamepad_flavor="dualsense",
            gamepad_emulation_enabled=False,
            gamepad_caminho="dualsense",
            coop_enabled=True,
            rumble_active=(0, 0),
        )
        self.controller = SimpleNamespace(primary_uniq=P1)
        self._gamepad_device: Any = None
        self._mouse_device = None
        self._coop_manager = None
        self.store = None
        self._emu_lock = threading.Lock()
        self._native_mode = False
        self._emu_manual_ts = 0.0
        self._mode_from_profile = None
        self.display_authority = "unknown"
        for nome in (
            "set_gamepad_emulation",
            "set_gamepad_emulation_desfecho",
            "vestir_a_mascara_do_aparelho",
        ):
            setattr(self, nome, functools.partial(getattr(lifecycle.Daemon, nome), self))
        self._ipc_server = _Servidor(self)

    def set_native_mode(self, enabled: bool, **_kw: Any) -> bool:
        self._native_mode = bool(enabled)
        return True

    def _esquecer_mascara_adiada(self, _m: Any) -> None:
        return

    async def _run_blocking(self, fn: Any, *args: Any) -> Any:
        return fn(*args)


@pytest.fixture(autouse=True)
def _bancada(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setattr(vp, "make_virtual_pad", _fabrica)
    monkeypatch.setattr(gp, "stop_gamepad_emulation", _parar)
    dubles: dict[str, Any] = {
        "_set_controller_grab": lambda d, g: None,
        "_materialize_launch_env": lambda d: None,
        "start_motion_reader": lambda d, dev: None,
        "read_primary_calibration": lambda d: None,
        "make_primary_rumble_sink": lambda d: None,
        "make_primary_replica_sinks": lambda d: {},
        "controller_allows_uhid": lambda d: False,
        "vpad_vivo": lambda dev: True,
        "_deve_promover_backend": lambda *a, **k: False,
    }
    for nome, valor in dubles.items():
        monkeypatch.setattr(gp, nome, valor)
    monkeypatch.setattr(coop_mod, "numero_do_nome_do_primario", lambda d, fallback=1: 1)
    monkeypatch.setattr(
        coop_mod, "get_coop_manager", lambda d: SimpleNamespace(sync=lambda force=False: None)
    )
    monkeypatch.setattr(session, "save_gamepad_emulation", lambda ativo, flavor=None: None)
    monkeypatch.setattr(session, "save_gamepad_caminho", lambda caminho: None)
    monkeypatch.setattr(hotkey, "PULSO_SEG", 0.0)
    em._zerar_registro_de_mascaras()
    (xdg_paths.config_dir(ensure=True) / "controller_masks.json").unlink(missing_ok=True)
    yield
    em._zerar_registro_de_mascaras()


@pytest.fixture
def luz(monkeypatch: pytest.MonkeyPatch) -> dict[str, list[Any]]:
    """As sequências da lightbar e as piscadas de aviso, na ordem."""
    anotado: dict[str, list[Any]] = {"sequencias": [], "piscadas": []}

    async def _sequencia(daemon: Any, cores: Any) -> None:
        anotado["sequencias"].append(list(cores))

    def _piscada(daemon: Any, cor: Any, *, modo: str) -> bool:
        anotado["piscadas"].append((tuple(cor), modo))
        return True

    monkeypatch.setattr(hotkey, "_sinalizar_lightbar", _sequencia)
    monkeypatch.setattr(hotkey, "_disparar_piscada", _piscada)
    return anotado


def _perfil_com_cartao_dualsense() -> None:
    loader.save_profile(
        Profile(
            name=PERFIL,
            match=MatchAny(),
            mode=ProfileModeConfig(kind="gamepad", gamepad_flavor="xbox", caminho="dualsense"),
            controllers={P1: ControllerOverrides(mascara="dualsense")},
        ),
        origem="teste",
    )
    session.save_last_profile(PERFIL)
    session.save_active_marker(PERFIL)
    em.registro_de_mascaras().set_mask(P1, "dualsense")


def _mascara_gravada() -> str | None:
    perfil = loader.load_profile(PERFIL)
    dele = (perfil.controllers or {}).get(P1)
    return getattr(dele, "mascara", None)


def test_o_ciclo_cobre_o_catalogo_inteiro() -> None:
    assert set(hotkey.CICLO_DE_MASCARAS) == set(em.mascaras_validas())
    assert set(hotkey.CORES_DA_MASCARA) == set(hotkey.CICLO_DE_MASCARAS)
    assert hotkey.COR_AVISO_RISCO not in hotkey.CORES_DA_MASCARA.values()


@pytest.mark.asyncio
async def test_tres_apertos_andam_pelas_mascaras_com_o_jogo_aberto(
    luz: dict[str, list[Any]],
) -> None:
    _perfil_com_cartao_dualsense()
    d = _Daemon()
    assert gp.start_gamepad_emulation_desfecho(d, None, origin="profile") == gp.EMU_APLICADO
    assert d._gamepad_device.backend == "uhid", "premissa: Sony DualSense com cartão DualSense"
    d.display_authority = "game"

    gesto = hotkey.build_next_mask_callback(d)  # type: ignore[arg-type]
    #: (a máscara que o vpad veste, o canal) depois de cada aperto.
    esperado = [("xbox", "uinput"), ("nintendo", "uinput"), ("dualsense", "uhid")]
    for aperto, (mascara, canal) in enumerate(esperado, start=1):
        await gesto()
        vivo = d._gamepad_device
        assert vivo is not None, f"aperto {aperto}: o vpad sumiu"
        assert (vivo.flavor, vivo.backend) == (mascara, canal), f"aperto {aperto}"
        assert _mascara_gravada() == mascara, (
            f"aperto {aperto}: o cartão do perfil ativo ficou em {_mascara_gravada()!r}"
        )
        assert em.registro_de_mascaras().mask_for(P1) == mascara, f"aperto {aperto}"
        assert d.config.gamepad_caminho == "dualsense", f"aperto {aperto}: o gesto mexeu no modo"
        modo = loader.load_profile(PERFIL).mode
        assert modo is not None and (modo.kind, modo.caminho) == ("gamepad", "dualsense")

    assert [cor for cor, _m in luz["piscadas"]] == [
        hotkey.CORES_DA_MASCARA[m] for m, _c in esperado
    ]
    riscos = [s for s in luz["sequencias"] if s and s[0][0] == hotkey.COR_AVISO_RISCO]
    assert len(riscos) == 3, "com jogo na mão, cada troca avisa o risco — e nenhuma falha"
    assert all(len(s) == 4 for s in riscos), "pulsos de falha (o longo no fim) apareceram"


@pytest.mark.asyncio
async def test_na_navegacao_o_gesto_guarda_a_mascara_sem_ligar_o_vpad(
    luz: dict[str, list[Any]],
) -> None:
    _perfil_com_cartao_dualsense()
    d = _Daemon()
    assert d._gamepad_device is None

    await hotkey.build_next_mask_callback(d)()  # type: ignore[arg-type]

    assert d._gamepad_device is None, "escolher máscara não liga o Hefesto"
    assert _mascara_gravada() == "xbox"
    assert hotkey.mascara_atual(d) == "xbox"  # type: ignore[arg-type]
    assert luz["piscadas"] == [(hotkey.CORES_DA_MASCARA["xbox"], "mascara:xbox")]


@pytest.mark.asyncio
async def test_o_aparelho_que_nao_veste_a_mascara_nao_ganha_a_cor_dela(
    luz: dict[str, list[Any]], monkeypatch: pytest.MonkeyPatch
) -> None:
    """A prova é o aparelho: o registro já diz a máscara pedida, o vpad não."""
    _perfil_com_cartao_dualsense()
    d = _Daemon()
    assert gp.start_gamepad_emulation_desfecho(d, None, origin="profile") == gp.EMU_APLICADO

    def _teimoso(flavor: Any, *, identity: Any = None, caminho: Any = None, **_kw: Any) -> _Vpad:
        return _Vpad("dualsense", identity, caminho)

    monkeypatch.setattr(vp, "make_virtual_pad", _teimoso)

    await hotkey.build_next_mask_callback(d)()  # type: ignore[arg-type]

    assert d._gamepad_device is not None and d._gamepad_device.flavor == "dualsense"
    assert em.registro_de_mascaras().mask_for(P1) == "xbox", "premissa: o handler gravou"
    assert luz["piscadas"] == [], "a cor do Xbox numa barra que continua DualSense"
    assert luz["sequencias"][-1] == hotkey._pulsos_de_falha()


@pytest.mark.asyncio
async def test_sem_mac_do_primario_o_gesto_recusa_pela_luz(
    luz: dict[str, list[Any]],
) -> None:
    d = _Daemon()
    d.controller = SimpleNamespace(primary_uniq=None)

    await hotkey.build_next_mask_callback(d)()  # type: ignore[arg-type]

    assert luz["piscadas"] == [], "sem cartão não há máscara a anunciar"
    assert luz["sequencias"] == [hotkey._pulsos_de_falha()], "a recusa tem de aparecer na luz"
    assert em.registro_de_mascaras().snapshot() == {}, "nada foi gravado"


def test_ps_l3_dispara_a_mascara_e_nao_vaza_o_l3() -> None:
    eventos: list[str] = []
    mgr = HotkeyManager(
        on_prev=lambda: eventos.append("prev"),
        on_next_bridge=lambda: eventos.append("ponte"),
        on_next_mask=lambda: eventos.append("mascara"),
    )
    assert DEFAULT_COMBO_MASCARA == ("ps", "l3")
    assert mgr.combo_buttons_active(["ps", "l3"]) == frozenset({"ps", "l3"})
    mgr.observe(["ps", "l3"], now=0.0)
    assert mgr.observe(["ps", "l3"], now=0.2) == "mascara"
    assert eventos == ["mascara"]
    assert not mgr.should_passthrough(["ps", "l3"], emulation_active=True)


def test_o_daemon_liga_o_gesto_da_mascara() -> None:
    d = SimpleNamespace(
        config=SimpleNamespace(ps_long_press_ms=0, ps_button_action="steam"),
        _hotkey_manager=None,
    )
    hotkey.start_hotkey_manager(d)  # type: ignore[arg-type]
    mgr = d._hotkey_manager
    assert mgr.config.next_mask == ("ps", "l3")
    assert callable(mgr.on_next_mask)
