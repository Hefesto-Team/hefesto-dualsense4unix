"""O-CURSOR-DA-MIRA-ANDA-DEVAGAR-LOGO-ACIMA-DA-ZONA-MORTA-01 — a zona do cursor é a da tela.

O cursor da Mira (a Navegação e o destino «Mouse» no jogo, do primário e do co-op) passa
pelo portão da zona morta medido na VELOCIDADE, sem o arredondamento do eixo do analógico:
o «Ignorar tremor até 3 graus/s» da Calibrar vale 3 graus/s no cursor, em qualquer
sensibilidade. O caminho é o do produto: o `SensorHub` REAL com o leitor do nó «Motion
Sensors» de mentira, o `Daemon` e o `IpcServer` do produto, o `aplicar_o_movimento` do tique
e o `UinputMouseDevice` com o nó `uinput` de mentira.
"""

from __future__ import annotations

import asyncio
from collections.abc import Iterator
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from hefesto_dualsense4unix.core import roteador_de_movimento as rot
from hefesto_dualsense4unix.core.virtual_motion import REGISTRO
from hefesto_dualsense4unix.daemon.ipc_server import IpcServer
from hefesto_dualsense4unix.daemon.lifecycle import Daemon
from hefesto_dualsense4unix.daemon.sensor_hub import SensorHub
from hefesto_dualsense4unix.daemon.subsystems import gamepad as gp
from hefesto_dualsense4unix.integrations.uinput_mouse import (
    BUTTON_TO_UINPUT,
    DPAD_TO_KEY,
    EDGE_KEY_MAP,
    UinputMouseDevice,
)
from hefesto_dualsense4unix.profiles.manager import ProfileManager
from hefesto_dualsense4unix.profiles.schema import MatchAny, Profile
from hefesto_dualsense4unix.testing import FakeController

_P = {n: f"aabbcc00000{n}" for n in (1, 2, 3, 4)}
_TIQUE_S = 1.0 / 64.0


@pytest.fixture(autouse=True)
def _registro_limpo() -> Iterator[None]:
    REGISTRO.limpar()
    yield
    REGISTRO.limpar()


@pytest.fixture
def perfis(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    from hefesto_dualsense4unix.profiles import loader as loader_module

    alvo = tmp_path / "profiles"
    alvo.mkdir()

    def _dir(ensure: bool = False) -> Path:
        if ensure:
            alvo.mkdir(parents=True, exist_ok=True)
        return alvo

    monkeypatch.setattr(loader_module, "profiles_dir", _dir)
    return alvo


class _Relogio:
    def __init__(self) -> None:
        self.agora = 1000.0

    def __call__(self) -> float:
        return self.agora

    def andar(self, segundos: float) -> None:
        self.agora += segundos


class _LeitorQueGira:
    """O leitor do nó «Motion Sensors»: a velocidade e a integral dela no relógio da mesa."""

    def __init__(self, relogio: _Relogio, giro: tuple[float, float, float]) -> None:
        self._relogio = relogio
        self._giro = giro
        self._desde = relogio()

    def start(self) -> bool:
        self._desde = self._relogio()
        return True

    def stop(self) -> None:
        pass

    def snapshot(self) -> Any:
        return SimpleNamespace(x=self._giro[0], y=self._giro[1], z=self._giro[2])

    def consume_angulo(self) -> tuple[float, float, float]:
        dt = self._relogio() - self._desde
        self._desde = self._relogio()
        return (self._giro[0] * dt, self._giro[1] * dt, self._giro[2] * dt)


class _LeitorDeEntradas:
    def start(self) -> bool:
        return True

    def stop(self) -> None:
        pass

    def snapshot(self) -> Any:
        return SimpleNamespace(lx=128, ly=128, rx=128, ry=128, l2_raw=0, r2_raw=0,
                               buttons_pressed=frozenset())


class _NoUinput:
    def __init__(self) -> None:
        self.eventos: list[tuple[Any, int]] = []

    def emit(self, codigo: Any, valor: int, syn: bool = True) -> None:
        self.eventos.append((codigo, valor))

    def syn(self) -> None:
        pass


def _modulo_uinput() -> Any:
    nomes = ["REL_X", "REL_Y", "REL_WHEEL", "REL_HWHEEL",
             *BUTTON_TO_UINPUT.values(), *DPAD_TO_KEY.values(), *EDGE_KEY_MAP.values()]
    return SimpleNamespace(**{n: (2, i) for i, n in enumerate(dict.fromkeys(nomes))})


def _a_mesa(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, giro_graus_s: float, transporte: str,
) -> SimpleNamespace:
    """O `Daemon` e o `IpcServer` do produto, com os quatro controles girando igual."""
    from hefesto_dualsense4unix.profiles.loader import save_profile

    relogio = _Relogio()
    monkeypatch.setattr(gp, "time", SimpleNamespace(monotonic=relogio))
    giro = (0.0, giro_graus_s, 0.0)
    hub = SensorHub(
        motion_factory=lambda uniq, node: _LeitorQueGira(relogio, giro),
        touch_factory=lambda uniq, node: _LeitorDeEntradas(),
        gamepad_factory=lambda uniq, node: _LeitorDeEntradas(),
        descobrir_motion=lambda: {u: Path(f"/dev/input/event-m{u}") for u in _P.values()},
        descobrir_touch=dict,
        descobrir_gamepad=lambda: {u: Path(f"/dev/input/event-g{u}") for u in _P.values()},
        relogio=relogio,
        auto_manutencao=False,
    )
    hub._watch = SimpleNamespace(poll=lambda: False)
    controle = FakeController(transport=transporte)  # type: ignore[arg-type]
    controle.primary_uniq = _P[1]  # type: ignore[attr-defined]
    daemon = Daemon(controller=controle)
    gerente = ProfileManager(controller=controle, store=daemon.store)
    servidor = IpcServer(controller=controle, store=daemon.store, profile_manager=gerente,
                         socket_path=tmp_path / "cursor.sock", daemon=daemon)
    servidor._sensor_hub = hub
    daemon._ipc_server = servidor
    perfil = Profile(name="Bancada", match=MatchAny(type="any"))
    save_profile(perfil)
    gerente.apply_movimento(perfil)
    daemon.store.set_active_profile(perfil.name)
    mouse = UinputMouseDevice()
    no = _NoUinput()
    mouse._device = no
    mouse._uinput_mod = _modulo_uinput()
    daemon._mouse_device = mouse
    return SimpleNamespace(daemon=daemon, servidor=servidor, hub=hub, relogio=relogio,
                           mouse=mouse, no=no)


def _andou_em_um_segundo(
    mesa: SimpleNamespace, uniq: str, *, na_navegacao: bool
) -> tuple[int, int]:
    """Um segundo de tiques do `aplicar_o_movimento`, e quanto o cursor andou."""
    arranjo = rot.ativo(mesa.daemon.store) or rot.ArranjoDeMovimento()
    centro = rot.CENTRO_DO_EIXO

    def _tique() -> None:
        gp.aplicar_o_movimento(mesa.daemon, arranjo, uniq=uniq, lx=centro, ly=centro,
                               rx=centro, ry=centro, botoes=frozenset(),
                               na_navegacao=na_navegacao)
        mesa.relogio.andar(_TIQUE_S)

    _tique()
    mesa.hub.reconciliar()
    _tique()  # a primeira drenagem é um acumulado e se descarta
    mesa.no.eventos.clear()
    for _ in range(64):
        _tique()
    u = mesa.mouse._uinput_mod
    return (sum(v for c, v in mesa.no.eventos if c == u.REL_X),
            sum(v for c, v in mesa.no.eventos if c == u.REL_Y))


def _na_navegacao(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *, giro: float, uniq: str = _P[1],
    sensibilidade: int = rot.SENSIBILIDADE_PADRAO,
    zona: float = rot.ZONA_MORTA_PADRAO_GRAUS_S, transporte: str = "usb",
) -> tuple[int, int]:
    """O chip da Mira aceso pela tela (`mira.set`), e o cursor da Navegação."""
    mesa = _a_mesa(tmp_path, monkeypatch, giro, transporte)
    corpo = asyncio.run(mesa.servidor._handlers["mira.set"](  # type: ignore[arg-type]
        {"uniq": uniq, "ligada": True, "sensibilidade": sensibilidade,
         "zona_morta_graus_s": zona}))
    assert corpo["status"] == "ok", corpo
    return _andou_em_um_segundo(mesa, uniq, na_navegacao=True)


def _no_jogo(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *, giro: float, uniq: str,
    transporte: str,
) -> tuple[int, int]:
    """O destino «Mouse» dentro do jogo, na peça `uniq` (o primário ou um do co-op)."""
    mesa = _a_mesa(tmp_path, monkeypatch, giro, transporte)
    rot.definir_da_peca(mesa.daemon.store, uniq, rot.ArranjoDeMovimento(
        destino=rot.DESTINO_MOUSE))
    rot.sincronizar_o_filtro(mesa.daemon.store)
    return _andou_em_um_segundo(mesa, uniq, na_navegacao=False)


def _esperado(giro: float, sensibilidade: int = rot.SENSIBILIDADE_PADRAO) -> float:
    return giro * rot.PIXELS_POR_GRAU_PADRAO * sensibilidade / rot.SENSIBILIDADE_PADRAO


@pytest.mark.parametrize("transporte", ["usb", "bt"])
def test_cinco_graus_por_segundo_andam_sessenta_pixels(
    perfis: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, transporte: str,
) -> None:
    """Sensibilidade 6, zona 3: 5 graus/s por um segundo são 12 px por grau vezes 5 graus."""
    dx, dy = _na_navegacao(tmp_path, monkeypatch, giro=5.0, transporte=transporte)
    assert abs(dx - _esperado(5.0)) <= 1 and dy == 0, (
        f"o cursor andou {dx} px a 5 graus/s; esperado ~{_esperado(5.0):.0f}")


@pytest.mark.parametrize("giro", [2.0, 1.0, 0.0])
def test_abaixo_da_zona_o_cursor_fica_parado(
    perfis: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, giro: float,
) -> None:
    """2 graus/s abaixo da zona de 3, a deriva de 1 grau/s e o controle parado: nada anda."""
    assert _na_navegacao(tmp_path, monkeypatch, giro=giro) == (0, 0)


def test_a_sensibilidade_baixa_nao_aumenta_a_zona(
    perfis: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Sensibilidade 1 a 8 graus/s: antes a zona dela era 35 graus/s, agora é a da tela."""
    dx, _ = _na_navegacao(tmp_path, monkeypatch, giro=8.0, sensibilidade=1)
    assert abs(dx - _esperado(8.0, 1)) <= 1, dx


def test_zona_zero_deixa_passar_meio_grau(
    perfis: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Zona 0 a 0,5 grau/s: o cursor anda os 6 px que a conta dá."""
    dx, _ = _na_navegacao(tmp_path, monkeypatch, giro=0.5, zona=0.0)
    assert abs(dx - _esperado(0.5)) <= 1 and dx > 0, dx


@pytest.mark.parametrize("transporte", ["usb", "bt"])
@pytest.mark.parametrize("jogador", [1, 2, 3, 4])
def test_cada_jogador_na_navegacao(
    perfis: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    jogador: int, transporte: str,
) -> None:
    """Os quatro controles, cabo e rádio: a mesma zona para todo jogador."""
    dx, _ = _na_navegacao(tmp_path, monkeypatch, giro=5.0, uniq=_P[jogador],
                          transporte=transporte)
    assert abs(dx - _esperado(5.0)) <= 1, (jogador, transporte, dx)


@pytest.mark.parametrize("transporte", ["usb", "bt"])
@pytest.mark.parametrize("jogador", [1, 2, 3, 4])
def test_o_destino_mouse_no_jogo_da_o_mesmo(
    perfis: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    jogador: int, transporte: str,
) -> None:
    """O destino «Mouse» fora da Navegação, no primário e no co-op: o mesmo cursor."""
    dx, dy = _no_jogo(tmp_path, monkeypatch, giro=5.0, uniq=_P[jogador],
                      transporte=transporte)
    assert abs(dx - _esperado(5.0)) <= 1 and dy == 0, (jogador, transporte, dx)
    assert _no_jogo(tmp_path, monkeypatch, giro=2.0, uniq=_P[jogador],
                    transporte=transporte) == (0, 0)


def test_o_predicado_e_a_deflexao_dizem_a_mesma_zona() -> None:
    """A regra mora num lugar só: o analógico também começa acima da zona, nunca antes."""
    arranjo = rot.ArranjoDeMovimento(destino=rot.DESTINO_ANALOGICO_DIREITO)
    assert not rot.passa_da_zona_morta((0.0, 3.0, 0.0), arranjo)
    assert rot.passa_da_zona_morta((0.0, 3.01, 0.0), arranjo)
    assert rot.deflexao((0.0, 3.0, 0.0), arranjo) == (0, 0)
    assert not rot.passa_da_zona_morta((0.0, 50.0, 0.0), rot.ArranjoDeMovimento())
