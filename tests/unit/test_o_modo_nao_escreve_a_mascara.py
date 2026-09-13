"""MODO-DE-CONEXAO-01 — o chip de modo escolhe o CAMINHO, e nunca a máscara.

A queixa dela, 13/09/2026, está citada na sprint: o chip «Xbox» da aba Jogar
dizia «aplicado» e não mudava nada. A causa, medida pelo estudo: o plano do chip
mandava a MÁSCARA (`gamepad.emulation.set {flavor: "xbox"}`), o cartão do P1 a
vencia em `mascara_efetiva`, e `start_gamepad_emulation_desfecho` respondia
`ja_estava` antes de gravar qualquer coisa. O perfil ativo recebia
`gamepad_flavor = "xbox"` e o jogo continuava recebendo o DualSense.

A regra dela (a sprint cita as três mensagens): o MODO é a base, a MÁSCARA vem
por cima e independe dele. Esta régua a cobra de ponta a ponta, pelo gesto REAL
(`a01_jogar.modo_xbox`), pelo handler REAL (`_handle_gamepad_emulation_set`) e
pelos métodos REAIS do `lifecycle.Daemon`, até o vpad. Só a borda é dublada: o
vpad (nenhum `/dev/uinput`, nenhum `/dev/uhid`), o grab, o launch env, a flag de
sessão e o co-op.

MORDE, e são duas curas independentes:

* devolver a máscara ao `_plano_do_chip` (o plano volta a mandar `flavor`) — o
  daemon responde `ja_estava`, o vpad não é recriado e o caminho não muda;
* a idempotência só por máscara em `start_gamepad_emulation_desfecho` (tirar o
  `mesmo_canal`) — a mesma resposta `ja_estava`, pelo outro lado.
"""
from __future__ import annotations

import asyncio
import functools
import threading
from collections.abc import Iterator
from types import SimpleNamespace
from typing import Any

import pytest

from hefesto_dualsense4unix.daemon import ipc_handlers as ih
from hefesto_dualsense4unix.daemon import lifecycle
from hefesto_dualsense4unix.daemon.subsystems import coop as coop_mod
from hefesto_dualsense4unix.daemon.subsystems import external_mask as em
from hefesto_dualsense4unix.daemon.subsystems import gamepad as gp
from hefesto_dualsense4unix.integrations import virtual_pad as vp
from hefesto_dualsense4unix.interface.pacotes import Contexto
from hefesto_dualsense4unix.interface.pacotes import a01_jogar as aba
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
        self.parado = False

    def stop(self) -> None:
        self.parado = True


def _fabrica(flavor: Any, *, identity: Any = None, caminho: Any = None, **_kw: Any) -> _Vpad:
    """A fábrica dublada veste a máscara EFETIVA, como a real."""
    return _Vpad(em.mascara_efetiva(identity, flavor), identity, caminho)


def _parar(daemon: Any, *, persist: bool = True, release_grab: bool = True) -> None:
    if daemon._gamepad_device is not None:
        daemon._gamepad_device.stop()
    daemon._gamepad_device = None
    daemon.config.gamepad_emulation_enabled = False


class _Daemon:
    """Os métodos REAIS do `lifecycle.Daemon`, amarrados a um objeto sem aparelho."""

    def __init__(self, sessao: str) -> None:
        self.config = SimpleNamespace(
            gamepad_flavor=sessao,
            gamepad_emulation_enabled=False,
            gamepad_caminho=None,
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
        self.set_gamepad_emulation = functools.partial(
            lifecycle.Daemon.set_gamepad_emulation, self
        )
        self.set_gamepad_emulation_desfecho = functools.partial(
            lifecycle.Daemon.set_gamepad_emulation_desfecho, self
        )

    def set_native_mode(self, enabled: bool, **_kw: Any) -> bool:
        self._native_mode = bool(enabled)
        return True

    def _esquecer_mascara_adiada(self, _m: Any) -> None:
        return

    def set_mouse_emulation(self, enabled: bool, *_a: Any, **_kw: Any) -> bool:
        return bool(enabled)

    def set_emulation_suppressed(self, value: Any = None) -> bool:
        return bool(value)

    def set_keyboard_emulation(self, enabled: bool, **_kw: Any) -> bool:
        return bool(enabled)


class _Ponte:
    """O `p` do gesto: despacha o plano para o HANDLER REAL do IPC."""

    def __init__(self, daemon: _Daemon) -> None:
        self.daemon = daemon
        self.pedidos: list[tuple[str, dict[str, Any]]] = []

    def chamar(self, metodo: str, **params: Any) -> bool:
        self.pedidos.append((metodo, dict(params)))
        if metodo == "gamepad.emulation.set":
            asyncio.run(
                ih.IpcHandlersMixin._handle_gamepad_emulation_set(
                    SimpleNamespace(daemon=self.daemon), params  # type: ignore[arg-type]
                )
            )
        elif metodo == "native.mode.set":
            self.daemon.set_native_mode(bool(params.get("enabled")))
        return True


@pytest.fixture(autouse=True)
def _bancada(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """A borda dublada; o registro de máscaras e o lembrete da aba zerados."""
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
    em._zerar_registro_de_mascaras()
    (xdg_paths.config_dir(ensure=True) / "controller_masks.json").unlink(missing_ok=True)
    aba._ESCOLHA.clear()
    aba._ROTULO.clear()
    yield
    em._zerar_registro_de_mascaras()
    aba._ESCOLHA.clear()
    aba._ROTULO.clear()


def _preparar(sessao: str, cartao: str) -> _Daemon:
    """Perfil ativo com a máscara no cartão do P1, e o vpad de pé pelo perfil."""
    loader.save_profile(
        Profile(
            name=PERFIL,
            match=MatchAny(),
            mode=ProfileModeConfig(kind="gamepad", gamepad_flavor=sessao),
            controllers={P1: ControllerOverrides(mascara=cartao)},
        ),
        origem="teste",
    )
    em.registro_de_mascaras().set_mask(P1, cartao)
    d = _Daemon(sessao)
    assert gp.start_gamepad_emulation_desfecho(d, None, origin="profile") == gp.EMU_APLICADO
    return d


def _estado(d: _Daemon) -> dict[str, Any]:
    """O pedaço do `state_full` que a aba lê — o caminho pelo MESMO leitor do daemon."""
    emu: dict[str, Any] = {
        "enabled": bool(d.config.gamepad_emulation_enabled),
        "flavor": d.config.gamepad_flavor,
        "caminho": ih._caminho_publicado(d),
        "por_aparelho": {P1: em.mascara_efetiva(P1, d.config.gamepad_flavor)},
    }
    if d._gamepad_device is not None:
        emu["backend"] = d._gamepad_device.backend
    return {
        "connected": True,
        "native_mode": d._native_mode,
        "paused": False,
        "active_profile": PERFIL,
        "gamepad_emulation": emu,
    }


def _ctx(d: _Daemon) -> Contexto:
    return Contexto(state=_estado(d), mesa=[], conectados=[], estados={})


def _mascara_do_cartao_no_disco() -> str | None:
    controles = loader.load_profile(PERFIL).controllers or {}
    return next((c.mascara for c in controles.values()), None)


def test_o_chip_xbox_troca_o_caminho_e_a_mascara_do_cartao_fica() -> None:
    """Cartão do P1 em DualSense: «Xbox» recria o vpad no canal comum, vestindo DualSense."""
    d = _preparar("dualsense", "dualsense")
    antes = d._gamepad_device
    assert (antes.backend, antes.flavor) == ("uhid", "dualsense"), "premissa da bancada"
    assert aba._estado_da_tela(_estado(d))["modo-aceso"] == "dualsense", "premissa"

    ponte = _Ponte(d)
    aba.modo_xbox(_ctx(d), {"texto": "Xbox"}, ponte)

    vivo = d._gamepad_device
    assert vivo is not antes and antes.parado, (
        "o vpad não foi recriado: o daemon respondeu `ja_estava` e o chip disse "
        f"«aplicado» sobre nada. Pedidos: {ponte.pedidos}"
    )
    assert vivo.backend == "uinput", "o caminho Xbox é o canal comum"
    assert vivo.flavor == "dualsense", "o chip de modo trocou a máscara"
    assert d.config.gamepad_flavor == "dualsense", "o chip de modo trocou a máscara da sessão"
    assert ih._caminho_publicado(d) == "xbox"

    estado = _estado(d)
    assert aba._estado_da_tela(estado)["modo-aceso"] == "xbox"
    assert estado["gamepad_emulation"]["por_aparelho"][P1] == "dualsense", "o cartão mudou"
    assert aba._faixa_do_pendente(estado) == ("", ""), "a pendência «Xbox» não morreu"

    gravado = loader.load_profile(PERFIL)
    assert gravado.mode is not None
    assert gravado.mode.caminho == "xbox", "o caminho não chegou ao perfil ativo"
    assert gravado.mode.gamepad_flavor == "dualsense", "o chip escreveu a máscara no perfil"
    assert _mascara_do_cartao_no_disco() == "dualsense"


def test_com_o_cartao_em_xbox_360_o_chip_acende_o_escolhido_e_nao_a_mascara() -> None:
    """Cartão do P1 em Xbox 360: «Sony DualSense» fica escolhido e aceso (§D.2).

    O `uhid` só se constrói com máscara DualSense, então os dois caminhos dão o
    MESMO aparelho: recriar o vpad aqui arrancaria o controle do jogo por nada.
    """
    d = _preparar("dualsense", "xbox")
    antes = d._gamepad_device
    assert (antes.backend, antes.flavor) == ("uinput", "xbox"), "premissa da bancada"
    assert aba._estado_da_tela(_estado(d))["modo-aceso"] == "xbox", (
        "premissa: sem caminho escolhido, ele sai da máscara, como antes da cura"
    )

    aba.modo_dualsense(_ctx(d), {"texto": "Sony DualSense"}, _Ponte(d))

    assert d._gamepad_device is antes and not antes.parado, (
        "recriou o vpad sem mudar de canal"
    )
    assert ih._caminho_publicado(d) == "dualsense", "o caminho escolhido não ficou"

    estado = _estado(d)
    assert aba._estado_da_tela(estado)["modo-aceso"] == "dualsense", (
        "o chip de modo acendeu pela máscara, e não pelo caminho escolhido"
    )
    assert estado["gamepad_emulation"]["por_aparelho"][P1] == "xbox", "o cartão mudou"
    assert aba._faixa_do_pendente(estado) == ("", "")

    gravado = loader.load_profile(PERFIL)
    assert gravado.mode is not None
    assert gravado.mode.caminho == "dualsense"
    assert gravado.mode.gamepad_flavor == "dualsense", "a máscara padrão do perfil mudou"
    assert _mascara_do_cartao_no_disco() == "xbox"
