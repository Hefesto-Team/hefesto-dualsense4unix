"""MODO-DE-CONEXAO-01 — o PS + R3 anda por CAMINHOS e grava no perfil ativo.

A regra dela, 13/09/2026, está citada na sprint: *"o modo é base (ele o ps +
r3)"* e *"inclusive o ps +r3 e isso fica setado no perfil"*. O gesto e o chip
são o MESMO modo: Sony DualSense → Xbox → Navegação → Sony DualSense (§D.5), a
máscara do vpad não muda em aperto nenhum, e cada aperto que o aparelho confirma
fica gravado no perfil ATIVO na hora — sem esperar os 180 s de silêncio e sem
precisar de jogo (§D.4). O carimbo por jogo da escada continua separado.

O que o estudo mediu antes da cura: com a máscara do P1 no cartão, o ciclo era
de MÁSCARAS (`ponte_atual` lia `device.flavor`), todo aperto pedia uma máscara
que o cartão vencia, e a luz dava cinco pulsos vermelhos com o ciclo parado.

A bancada é a da `test_o_modo_nao_escreve_a_mascara.py`: o callback REAL do
gesto (`hotkey.build_next_bridge_callback`) e os métodos REAIS do
`lifecycle.Daemon`; dublados só o vpad, o grab, o launch env, as flags de sessão,
o co-op e a lightbar. O perfil ativo é achado pela perna do disco
(`session.json` + o marcador), que é o estado da máquina dela com o daemon
calado.

MORDE, e são duas curas independentes:

* `ponte_atual` lendo `device.flavor` — o primeiro aperto não sobe (`efetiva`
  continua `dualsense`), a luz dá os pulsos vermelhos e o ciclo trava;
* tirar a chamada `_gravar_o_modo_do_gesto` do callback — o aparelho troca, e
  o perfil ativo fica como estava.
"""
from __future__ import annotations

import functools
import threading
from collections.abc import Iterator
from types import SimpleNamespace
from typing import Any

import pytest

from hefesto_dualsense4unix.daemon import lifecycle
from hefesto_dualsense4unix.daemon.subsystems import coop as coop_mod
from hefesto_dualsense4unix.daemon.subsystems import external_mask as em
from hefesto_dualsense4unix.daemon.subsystems import gamepad as gp
from hefesto_dualsense4unix.daemon.subsystems import hotkey
from hefesto_dualsense4unix.integrations import virtual_pad as vp
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
        self.mouse = False
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
        self.mouse = bool(enabled)
        return bool(enabled)

    def set_emulation_suppressed(self, value: Any = None) -> bool:
        return bool(value)

    def set_keyboard_emulation(self, enabled: bool, **_kw: Any) -> bool:
        return bool(enabled)

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
    # O gesto sem jogo e sem relógio: esta régua mede DECISÃO.
    monkeypatch.setattr(hotkey, "PULSO_SEG", 0.0)
    monkeypatch.setattr(hotkey, "_appid_do_jogo_do_wrapper", lambda: None)
    em._zerar_registro_de_mascaras()
    (xdg_paths.config_dir(ensure=True) / "controller_masks.json").unlink(missing_ok=True)
    yield
    em._zerar_registro_de_mascaras()


@pytest.fixture
def luzes(monkeypatch: pytest.MonkeyPatch) -> list[list[Any]]:
    """Cada sequência que o gesto mandou à lightbar, na ordem."""
    sequencias: list[list[Any]] = []

    async def _anotar(daemon: Any, cores: Any) -> None:
        sequencias.append(list(cores))

    monkeypatch.setattr(hotkey, "_sinalizar_lightbar", _anotar)
    return sequencias


def _preparar_cartao_dualsense() -> _Daemon:
    loader.save_profile(
        Profile(
            name=PERFIL,
            match=MatchAny(),
            mode=ProfileModeConfig(kind="gamepad", gamepad_flavor="dualsense"),
            controllers={P1: ControllerOverrides(mascara="dualsense")},
        ),
        origem="teste",
    )
    # O perfil que está valendo, pela perna do disco — o daemon não sabe o nome.
    session.save_last_profile(PERFIL)
    session.save_active_marker(PERFIL)
    em.registro_de_mascaras().set_mask(P1, "dualsense")
    d = _Daemon("dualsense")
    assert gp.start_gamepad_emulation_desfecho(d, None, origin="profile") == gp.EMU_APLICADO
    return d


@pytest.mark.asyncio
async def test_tres_apertos_andam_pelos_caminhos_e_cada_um_fica_no_perfil(
    luzes: list[list[Any]],
) -> None:
    d = _preparar_cartao_dualsense()
    assert hotkey.ponte_atual(d) == hotkey.PONTE_DUALSENSE, "premissa da bancada"
    assert d._gamepad_device.backend == "uhid", "premissa da bancada"

    gesto = hotkey.build_next_bridge_callback(d)  # type: ignore[arg-type]
    #: (a ponte de pé, o canal do vpad, o `mode` gravado) depois de cada aperto.
    esperado = [
        (hotkey.PONTE_XBOX, "uinput", ("gamepad", "xbox")),
        (hotkey.PONTE_MOUSE_TECLADO, None, ("desktop", None)),
        (hotkey.PONTE_DUALSENSE, "uhid", ("gamepad", "dualsense")),
    ]
    andou: list[str] = []
    for aperto, (ponte, canal, modo) in enumerate(esperado, start=1):
        await gesto()
        andou.append(hotkey.ponte_atual(d))
        assert andou[-1] == ponte, f"aperto {aperto}: o ciclo andou {andou}"
        vivo = d._gamepad_device
        assert (vivo.backend if vivo is not None else None) == canal, f"aperto {aperto}"
        if vivo is not None:
            assert vivo.flavor == "dualsense", f"aperto {aperto}: o gesto trocou a máscara"
        gravado = loader.load_profile(PERFIL).mode
        assert gravado is not None
        assert (gravado.kind, gravado.caminho) == modo, (
            f"aperto {aperto}: o perfil ativo ficou em {gravado!r}, e o gesto "
            "grava na hora — sem esperar silêncio nem jogo"
        )

    vermelhas = [seq for seq in luzes if seq and seq[0][0] == hotkey.COR_AVISO_RISCO]
    assert not vermelhas, (
        f"{len(vermelhas)} sequência(s) de pulsos vermelhos — `ponte_nao_subiu`: o "
        "aparelho não concordou com o aperto"
    )
    assert em.mascara_efetiva(P1, d.config.gamepad_flavor) == "dualsense", "o cartão mudou"
