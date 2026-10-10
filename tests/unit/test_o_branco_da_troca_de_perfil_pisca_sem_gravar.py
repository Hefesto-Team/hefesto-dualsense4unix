"""O branco da troca de perfil pisca sem gravar (O-BRANCO-DA-TROCA-DE-PERFIL-PISCA-SEM-GRAVAR-01).

O gesto de trocar de perfil (PS + cima/baixo) pisca o branco na barra para dar
retorno com o controle na mão. O pisca é AVISO, não escolha: sai pelo
`pintar_lightbar_sem_lembrar` (os quatro controles, sem tocar no estado
desejado) e a cor resolvida volta SEMPRE pelo `restaurar_lightbar_do_perfil`,
inclusive quando a ativação levanta. Pintar pelo `set_led` gravava o branco no
desejado: no controle do seletor, ou no padrão de todos quando o seletor está
em «Todos», onde o perfil de destino com a cor global preta não o desfazia.

Backend real, quatro controles: P1 e P2 no cabo (nó da classe LED), P3 e P4 no
rádio (o `0x31` pelo hidraw). Só a fábrica de perfis é dublê: o `activate`
dela faz, na luz, o mesmo que o de verdade (solta a camada da usuária e leva a
cor global ao padrão, ou nada quando a global é preta).
"""
from __future__ import annotations

import copy
from types import SimpleNamespace
from typing import Any, ClassVar

import pytest
from pydualsense.pydualsense import DSAudio, DSLight, DSTrigger

from hefesto_dualsense4unix.core import backend_pydualsense as bp
from hefesto_dualsense4unix.core.controller import OutputSpec
from hefesto_dualsense4unix.core.lightbar_gatilho import COMMON_LIGHTBAR_B, COMMON_LIGHTBAR_R
from hefesto_dualsense4unix.daemon.subsystems.hotkey import build_profile_cycle_callback

BRANCO = (255, 255, 255)
COR_ANTES = (40, 80, 180)
COR_DO_P3 = (200, 30, 90)

MACS = (
    "AA:BB:CC:00:00:01",  # P1, cabo
    "AA:BB:CC:00:00:02",  # P2, cabo
    "AA:BB:CC:00:00:03",  # P3, rádio
    "AA:BB:CC:00:00:04",  # P4, rádio
)
UNIQS = tuple(m.replace(":", "").lower() for m in MACS)


class _NoDeLed:
    """A classe LED do kernel de um controle no cabo."""

    def __init__(self) -> None:
        self.cores: list[tuple[int, int, int]] = []
        self.indicator_dir = "/sys/class/leds/x"

    def writable(self) -> bool:
        return True

    def set_rgb(self, r: int, g: int, b: int, *, verify: bool = False) -> bool:
        self.cores.append((r, g, b))
        return True

    def set_players(self, _bits: tuple[bool, ...]) -> bool:
        return True

    def set_players_verified(self, bits: tuple[bool, ...]) -> bool:
        return self.set_players(bits)

    def invalidate_cache(self) -> None:
        pass

    def get_rgb(self) -> tuple[int, int, int] | None:
        return self.cores[-1] if self.cores else None


def _handle(transporte: str) -> SimpleNamespace:
    escritos: list[list[int]] = []
    handle = SimpleNamespace(
        triggerL=DSTrigger(),
        triggerR=DSTrigger(),
        light=DSLight(),
        audio=DSAudio(),
        _raw_trigger_left=None,
        _raw_trigger_right=None,
        _output_muted=False,
        transporte=transporte,
        escritos=escritos,
    )

    def _escreve(r: list[int]) -> int:
        escritos.append(list(r))
        return len(r)

    handle.writeReport = _escreve
    return handle


def _cor_do_report(report: list[int]) -> tuple[int, ...]:
    common = report[3:50]
    return tuple(common[COMMON_LIGHTBAR_R : COMMON_LIGHTBAR_B + 1])


class _Mesa:
    def __init__(self) -> None:
        self.ctl = bp.PyDualSenseController()
        self.handles = [_handle("usb"), _handle("usb"), _handle("bt"), _handle("bt")]
        self.nos = [_NoDeLed(), _NoDeLed()]
        self.ctl._handles = dict(zip(MACS, self.handles, strict=True))
        self.ctl._sysfs = {MACS[0]: self.nos[0], MACS[1]: self.nos[1]}
        self.ctl._detect_transport = lambda h: h.transporte

    def pinturas(self, i: int) -> list[tuple[int, ...]]:
        """Toda cor que o controle `i` (0 a 3) recebeu, na ordem."""
        if i < 2:
            return list(self.nos[i].cores)
        return [_cor_do_report(r) for r in self.handles[i].escritos]

    def resolvida(self, i: int) -> tuple[int, int, int]:
        cor: tuple[int, int, int] | None = self.ctl._merged_desired_for_key(MACS[i]).led
        return cor if cor is not None else bp.KERNEL_DEFAULT_BLUE

    def desejado(self) -> tuple[Any, Any]:
        return (copy.deepcopy(self.ctl._desired_default),
                copy.deepcopy(self.ctl._desired_by_uniq))


class _Store:
    def __init__(self) -> None:
        self.active_profile = "a"
        self._manual_profile_lock_until = 0.0
        self.native_mode_active = False

    def mark_manual_profile_lock(self, t: float) -> None:
        self._manual_profile_lock_until = t


class _Fabrica:
    """A fábrica de perfis: `b` tem a cor global preta (o `activate` não toca na cor)."""

    cor_global: ClassVar[dict[str, tuple[int, int, int] | None]] = {"a": COR_ANTES, "b": None}
    levanta: ClassVar[bool] = False
    ao_ativar: ClassVar[list[tuple[Any, Any]]] = []

    def __init__(self, controller: Any = None, store: Any = None, **_k: Any) -> None:
        self.controller = controller
        self.store = store

    def list_profiles(self) -> list[SimpleNamespace]:
        return [SimpleNamespace(name=n) for n in self.cor_global]

    def activate(self, name: str, *, origin: str = "manual") -> SimpleNamespace:
        _Fabrica.ao_ativar.append(
            (copy.deepcopy(self.controller._desired_default),
             copy.deepcopy(self.controller._desired_by_uniq)))
        if _Fabrica.levanta:
            raise RuntimeError("o perfil não abriu")
        if origin == "manual":
            self.controller.clear_user_output_overrides()
        self.controller.apply_output_defaults(OutputSpec(led=self.cor_global[name]))
        self.store.active_profile = name
        return SimpleNamespace(name=name)


class _Daemon:
    def __init__(self, mesa: _Mesa) -> None:
        self.controller = mesa.ctl
        self.store = _Store()
        self._keyboard_device = None

    async def _run_blocking(self, fn: Any, *args: Any) -> Any:
        return fn(*args)


@pytest.fixture
def mesa(monkeypatch: pytest.MonkeyPatch) -> _Mesa:
    _Fabrica.levanta = False
    _Fabrica.ao_ativar = []
    monkeypatch.setattr("hefesto_dualsense4unix.profiles.manager.ProfileManager", _Fabrica)
    monkeypatch.setattr(
        "hefesto_dualsense4unix.utils.session.save_active_marker", lambda _n: None)
    monkeypatch.setattr("asyncio.sleep", _sem_espera)
    m = _Mesa()
    m.ctl._desired_default.led = COR_ANTES
    m.ctl._desired_by_uniq[UNIQS[2]] = bp._DesiredOutput(led=COR_DO_P3)
    return m


async def _sem_espera(_s: float) -> None:
    return None


@pytest.mark.asyncio
async def test_com_o_seletor_no_p2_pisca_nos_quatro_e_nao_grava(mesa: _Mesa) -> None:
    mesa.ctl.set_output_target(1)
    antes = mesa.desejado()

    await build_profile_cycle_callback(_Daemon(mesa), +1)()

    for i in range(4):
        assert BRANCO in mesa.pinturas(i), f"P{i + 1} não piscou"
    default, por_uniq = _Fabrica.ao_ativar[0]
    assert default == antes[0], "o pisca gravou no padrão"
    assert por_uniq == antes[1], "o pisca gravou na camada de um controle"


@pytest.mark.asyncio
async def test_com_todos_e_destino_preto_cada_um_volta_a_cor_do_perfil(mesa: _Mesa) -> None:
    mesa.ctl.set_output_target(None)

    await build_profile_cycle_callback(_Daemon(mesa), +1)()

    for i in range(4):
        assert mesa.resolvida(i) != BRANCO, f"P{i + 1}: o pisca gravou no padrão"
        assert mesa.pinturas(i)[-1] == mesa.resolvida(i), f"P{i + 1} ficou no branco"
    assert mesa.pinturas(2)[-1] == COR_DO_P3


@pytest.mark.asyncio
async def test_a_ativacao_que_levanta_devolve_a_cor_de_antes(mesa: _Mesa) -> None:
    _Fabrica.levanta = True
    cores_antes = [mesa.resolvida(i) for i in range(4)]

    with pytest.raises(RuntimeError):
        await build_profile_cycle_callback(_Daemon(mesa), +1)()

    for i in range(4):
        assert BRANCO in mesa.pinturas(i), f"P{i + 1} não piscou"
        assert mesa.pinturas(i)[-1] == cores_antes[i], f"P{i + 1} ficou no branco"
