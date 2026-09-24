"""A-MIRA-NA-NAVEGACAO-01 — na Navegação, o giro move o cursor.

A decisão (`D-2409-NA-NAVEGACAO-O-GIRO-VIRA-CURSOR`) é a leitura literal da
frase dela:
*"A exceção do nativo todo o resto deve ter mira Virtual"*.  <!-- noqa-acento: dela -->
Na Navegação não há controle virtual, e o chip da Mira acendia sem mover nada.

A PRIMEIRA SEÇÃO NÃO DUBLA O DAEMON, pela lição da A-MIRA-01 (o dublê tinha o
que o real não tinha, e a mira ficou verde sem mover um eixo): o `Daemon`, o
`IpcServer`, o `SensorHub` e o `UinputMouseDevice` são os do produto. Só o leitor
do nó de movimento e o nó `uinput` são de mentira — NENHUM nó de verdade nasce
aqui (a suíte já derrubou a sessão gráfica dela com nós `uinput`).

AS CHAVES SÃO AS DO PRODUTO: o hub conhece cada controle pelo MAC normalizado
(`discover_dualsense_motion_evdevs`, doze hex) e o `primary_uniq` do backend
também é normalizado. Endereços da faixa SINTÉTICA da casa (``aa:bb:cc``).

Cada régua diz a MORDIDA: o que arrancar para vê-la reprovar.
"""

from __future__ import annotations

import asyncio
import sys
from collections.abc import Iterator
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from hefesto_dualsense4unix.core import roteador_de_movimento as rot
from hefesto_dualsense4unix.core.controller import ControllerState
from hefesto_dualsense4unix.core.virtual_motion import REGISTRO
from hefesto_dualsense4unix.daemon.ipc_server import IpcServer
from hefesto_dualsense4unix.daemon.lifecycle import Daemon
from hefesto_dualsense4unix.daemon.sensor_hub import SensorHub
from hefesto_dualsense4unix.daemon.subsystems import gamepad as gp
from hefesto_dualsense4unix.daemon.subsystems import mouse as mouse_sub
from hefesto_dualsense4unix.integrations.uinput_mouse import (
    BUTTON_TO_UINPUT,
    DPAD_TO_KEY,
    EDGE_KEY_MAP,
    UinputMouseDevice,
)
from hefesto_dualsense4unix.profiles.manager import ProfileManager
from hefesto_dualsense4unix.profiles.schema import (
    MatchAny,
    Profile,
    ProfileMovimentoConfig,
)
from hefesto_dualsense4unix.testing import FakeController

#: A RAIZ DA ÁRVORE, e a pasta da interface no caminho de import: os pacotes das
#: abas (`pacotes.a02_controles`, `pacotes.a04_iluminacao`) se importam pelo
#: nome curto, como o piloto os importa.
_RAIZ = Path(__file__).resolve().parents[2]
_INTERFACE = str(_RAIZ / "src" / "hefesto_dualsense4unix" / "interface")
if _INTERFACE not in sys.path:
    sys.path.insert(0, _INTERFACE)

#: Os quatro controles, na grafia do backend e do hub (doze hex).
_P = {n: f"aabbcc00000{n}" for n in (1, 2, 3, 4)}

#: Um giro de pulso no `yaw` (graus/s): acima da zona morta, abaixo do teto.
_GIRO_S = 128.0
#: Um tique de ~60 Hz, em segundos — o relógio de mentira anda isto por tique.
#: 1/64 e não 1/60 porque o binário o escreve EXATO: com 1/60 o relógio soma
#: resto de ponto flutuante, e o carry sub-pixel do device dá 29 onde a conta dá
#: 30 — a régua mediria o arredondamento, não a mira.
_TIQUE_S = 1.0 / 64.0
#: O deslocamento de UM controle por tique, na conta do motor: 128 °/s vezes 1/64 s
#: = 2 graus; vezes 12 px por grau, vezes 6/6 da sensibilidade padrão = 24 px.
_PX_POR_TIQUE = round(_GIRO_S * _TIQUE_S * rot.PIXELS_POR_GRAU_PADRAO)


@pytest.fixture(autouse=True)
def _registro_limpo() -> Iterator[None]:
    """O `REGISTRO` dos sensores é do processo: nada desta régua vaza dele."""
    REGISTRO.limpar()
    yield
    REGISTRO.limpar()


@pytest.fixture
def perfis(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Diretório de perfis isolado — o molde das réguas da A-MIRA."""
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
    """O tempo da mesa: o leitor integra por ele e o motor mede o silêncio por ele."""

    def __init__(self) -> None:
        self.agora = 1000.0

    def __call__(self) -> float:
        return self.agora

    def andar(self, segundos: float) -> None:
        self.agora += segundos


class _LeitorQueGira:
    """O leitor do nó «Motion Sensors» — a única peça de mentira da torneira.

    Do tamanho do `MotionSensorReader` para o que o hub pergunta: `start()`
    afirma que abriu, `snapshot()` devolve a velocidade e `consume_angulo()`
    DRENA o ângulo percorrido desde a última drenagem — integrado pelo relógio,
    como o real integra o carimbo do kernel. Um controle girando parado a
    128 °/s acumula 2 graus por tique e 76.800 graus em dez minutos: o
    mesmo acumulador sem dono que o real tem.
    """

    def __init__(self, relogio: _Relogio, giro: tuple[float, float, float]) -> None:
        self._relogio = relogio
        self._giro = giro
        self._desde = relogio()
        self.drenagens = 0

    def start(self) -> bool:
        self._desde = self._relogio()
        return True

    def stop(self) -> None:
        pass

    def snapshot(self) -> Any:
        return SimpleNamespace(x=self._giro[0], y=self._giro[1], z=self._giro[2])

    def consume_angulo(self) -> tuple[float, float, float]:
        self.drenagens += 1
        dt = self._relogio() - self._desde
        self._desde = self._relogio()
        return (self._giro[0] * dt, self._giro[1] * dt, self._giro[2] * dt)


class _LeitorDeEntradas:
    """O leitor de gamepad SEM grab que o hub abre para o «Só enquanto eu
    segurar» de quem não é o primário — do tamanho do `EvdevReader` para o
    `hub.entradas`: `start`, `stop` e o `snapshot` com os botões."""

    def __init__(self) -> None:
        self.botoes: frozenset[str] = frozenset()

    def start(self) -> bool:
        return True

    def stop(self) -> None:
        pass

    def snapshot(self) -> Any:
        return SimpleNamespace(lx=128, ly=128, rx=128, ry=128, l2_raw=0, r2_raw=0,
                               buttons_pressed=self.botoes)


class _Mesa:
    """O hub REAL com os quatro controles girando, e os leitores à mão da régua."""

    def __init__(self, relogio: _Relogio, giro: tuple[float, float, float]) -> None:
        self.movimento: dict[str, _LeitorQueGira] = {}
        self.entradas: dict[str, _LeitorDeEntradas] = {
            u: _LeitorDeEntradas() for u in _P.values()}

        def _abrir(uniq: str, node: Any) -> _LeitorQueGira:
            self.movimento[uniq] = _LeitorQueGira(relogio, giro)
            return self.movimento[uniq]

        self.hub = SensorHub(
            motion_factory=_abrir,
            touch_factory=lambda uniq, node: _LeitorDeEntradas(),
            gamepad_factory=lambda uniq, node: self.entradas[uniq],
            descobrir_motion=lambda: {u: Path(f"/dev/input/event-m{u}") for u in _P.values()},
            descobrir_touch=dict,
            descobrir_gamepad=lambda: {u: Path(f"/dev/input/event-g{u}") for u in _P.values()},
            relogio=relogio,
            auto_manutencao=False,
        )
        self.hub._watch = SimpleNamespace(poll=lambda: False)


class _NoUinput:
    """O nó `uinput` de mentira: do tamanho do `uinput.Device` para o que o
    `UinputMouseDevice` usa — `emit(código, valor, syn=)` e `syn()` —, e nada a
    mais. Guarda cada evento, na ordem."""

    def __init__(self) -> None:
        self.eventos: list[tuple[Any, int]] = []

    def emit(self, codigo: Any, valor: int, syn: bool = True) -> None:
        self.eventos.append((codigo, valor))

    def syn(self) -> None:
        pass


def _modulo_uinput() -> Any:
    """As constantes do `python-uinput` que o device lê: os eixos relativos e as
    teclas dos três mapas, cada uma com um código só dela."""
    nomes = ["REL_X", "REL_Y", "REL_WHEEL", "REL_HWHEEL",
             *BUTTON_TO_UINPUT.values(), *DPAD_TO_KEY.values(), *EDGE_KEY_MAP.values()]
    return SimpleNamespace(**{n: (2, i) for i, n in enumerate(dict.fromkeys(nomes))})


def _o_mouse() -> tuple[UinputMouseDevice, _NoUinput]:
    """O `UinputMouseDevice` DO PRODUTO, com o nó de mentira no lugar do real."""
    mouse = UinputMouseDevice()
    no = _NoUinput()
    mouse._device = no
    mouse._uinput_mod = _modulo_uinput()
    return mouse, no


def _andou(mouse: UinputMouseDevice, no: _NoUinput) -> tuple[int, int]:
    """Quanto o cursor andou, em pixels: a soma de REL_X e de REL_Y."""
    u = mouse._uinput_mod
    return (sum(v for c, v in no.eventos if c == u.REL_X),
            sum(v for c, v in no.eventos if c == u.REL_Y))


class _RegistroDeIdentidade:
    """O registro de identidade, do tamanho do real para o que o tique pergunta:
    `snapshot_connected()` devolve as chaves CONECTADAS (doze hex)."""

    def __init__(self, conectados: set[str]) -> None:
        self._conectados = set(conectados)

    def snapshot_connected(self) -> set[str]:
        return set(self._conectados)


def _navegacao(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, transporte: str,
    *, perfil: Profile | None = None, giro: tuple[float, float, float] = (0.0, _GIRO_S, 0.0),
) -> SimpleNamespace:
    """O `Daemon` e o `IpcServer` do produto, na Navegação: sem controle
    virtual e com o mouse emulado de pé. O perfil ATIVO não tem mira — quem a
    acende é o chip (`mira.set`), salvo quando a régua passa outro."""
    from hefesto_dualsense4unix.profiles.loader import save_profile

    relogio = _Relogio()
    monkeypatch.setattr(gp, "time", SimpleNamespace(monotonic=relogio))
    mesa = _Mesa(relogio, giro)
    controle = FakeController(transport=transporte)  # type: ignore[arg-type]
    controle.primary_uniq = _P[1]  # type: ignore[attr-defined]
    daemon = Daemon(controller=controle)
    gerente = ProfileManager(controller=controle, store=daemon.store)
    servidor = IpcServer(controller=controle, store=daemon.store, profile_manager=gerente,
                         socket_path=tmp_path / "navegacao.sock", daemon=daemon)
    servidor._sensor_hub = mesa.hub
    daemon._ipc_server = servidor
    perfil = perfil or Profile(name="Bancada", match=MatchAny(type="any"))
    save_profile(perfil)
    gerente.apply_movimento(perfil)
    daemon.store.set_active_profile(perfil.name)
    assert daemon._gamepad_device is None, "a Navegação não tem controle virtual"
    mouse, no = _o_mouse()
    daemon._mouse_device = mouse
    estado = ControllerState(battery_pct=100, l2_raw=0, r2_raw=0, connected=True,
                             transport=transporte)  # type: ignore[arg-type]
    return SimpleNamespace(daemon=daemon, servidor=servidor, mesa=mesa, relogio=relogio,
                           mouse=mouse, no=no, estado=estado)


def _mira_set(servidor: IpcServer, **params: Any) -> dict[str, Any]:
    corpo: dict[str, Any] = asyncio.run(servidor._handlers["mira.set"](params))  # type: ignore[arg-type]
    return corpo


def _tique(nav: SimpleNamespace, botoes: frozenset[str] = frozenset()) -> None:
    """UM tique da Navegação — o `dispatch_mouse` do laço do daemon."""
    mouse_sub.dispatch_mouse(nav.daemon, nav.estado, botoes)
    nav.relogio.andar(_TIQUE_S)


def _ate_andar(nav: SimpleNamespace, botoes: frozenset[str] = frozenset()) -> tuple[int, int]:
    """Os três primeiros tiques, no ritmo do produto, e quanto o cursor andou no
    TERCEIRO.

    O primeiro registra a demanda (o hub abre o leitor na volta de manutenção,
    aqui a `reconciliar()`); o segundo drena pela primeira vez — e a primeira
    drenagem é o acumulado de antes, que sai como nada; o terceiro move.
    """
    _tique(nav, botoes)
    nav.mesa.hub.reconciliar()
    _tique(nav, botoes)
    antes = _andou(nav.mouse, nav.no)
    _tique(nav, botoes)
    depois = _andou(nav.mouse, nav.no)
    return depois[0] - antes[0], depois[1] - antes[1]


# ---------------------------------------------------------------------------
# 1. A MATRIZ — o cursor anda com o giro, do P1 ao P4, no USB e no BT
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("transporte", ["usb", "bt"])
@pytest.mark.parametrize("jogador", [1, 2, 3, 4])
def test_na_navegacao_o_chip_de_cada_um_move_o_cursor(
    perfis: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    jogador: int, transporte: str,
) -> None:
    """Os quatro controles girando igual; só o chip do jogador N aceso. O cursor
    anda EXATAMENTE o giro de um controle: o dele, e o de ninguém mais.

    MORDIDA: arranque a chamada de `mover_o_cursor_pelo_giro` do
    `dispatch_mouse` e os oito casos reprovam com o cursor parado.
    """
    nav = _navegacao(tmp_path, monkeypatch, transporte)
    corpo = _mira_set(nav.servidor, uniq=_P[jogador], ligada=True)
    assert corpo["status"] == "ok" and corpo["alcance"] == {"tique": "aplicado"}, corpo
    dx, dy = _ate_andar(nav)
    assert (dx, dy) == (_PX_POR_TIQUE, 0), (
        f"P{jogador}/{transporte}: o chip acendeu e o cursor andou {(dx, dy)} — "
        f"esperado o giro de UM controle, {(_PX_POR_TIQUE, 0)}")


def test_dois_controles_com_a_mira_somam_no_mesmo_cursor(
    perfis: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """O mouse é um só: o P2 e o P3 com a Mira movem o MESMO cursor, e os dois
    giros se somam — como duas mãos no mesmo mouse. Cada peça drena o próprio
    leitor, e nenhum giro conta duas vezes.

    MORDIDA: faça `_pecas_da_navegacao` devolver só a primeira peça e o cursor
    anda metade.
    """
    nav = _navegacao(tmp_path, monkeypatch, "bt")
    for n in (2, 3):
        _mira_set(nav.servidor, uniq=_P[n], ligada=True)
    assert _ate_andar(nav) == (2 * _PX_POR_TIQUE, 0)


def test_a_mira_do_perfil_inteiro_move_com_os_quatro_conectados(
    perfis: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A mira no PERFIL (a mesa inteira), com o registro de identidade dizendo
    quem está na mesa: os quatro somam. O P4 fora da mesa não pede leitor.

    MORDIDA: tire o ramo `arranjo.ligado` de `_pecas_da_navegacao` e só o
    primário move.
    """
    perfil = Profile(name="Mesa", match=MatchAny(type="any"),
                     movimento=ProfileMovimentoConfig(destino="analogico_direito"))
    nav = _navegacao(tmp_path, monkeypatch, "usb", perfil=perfil)
    nav.daemon.identity_registry = _RegistroDeIdentidade({_P[1], _P[2], _P[3]})
    assert _ate_andar(nav) == (3 * _PX_POR_TIQUE, 0)
    assert _P[4] not in nav.mesa.movimento, "o P4 fora da mesa ganhou leitor"


def test_na_navegacao_o_destino_e_o_cursor_nunca_o_analogico(
    perfis: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """O chip grava o analógico direito, que na Navegação é a RODA do mouse: o
    giro não pode virar rolagem. Nenhum `REL_WHEEL`, nenhum `REL_HWHEEL`.

    MORDIDA: tire o `para_o_cursor` do `aplicar_o_movimento` e o cursor fica
    parado (o motor devolve os eixos a um `dispatch_mouse` que já passou).
    """
    nav = _navegacao(tmp_path, monkeypatch, "usb")
    _mira_set(nav.servidor, uniq=_P[1], ligada=True)
    assert _ate_andar(nav)[0] == _PX_POR_TIQUE
    u = nav.mouse._uinput_mod
    assert not [e for e in nav.no.eventos if e[0] in (u.REL_WHEEL, u.REL_HWHEEL)]


# ---------------------------------------------------------------------------
# 2. OS AJUSTES DA CALIBRAR VALEM IGUAL
# ---------------------------------------------------------------------------


def test_a_sensibilidade_e_o_inverter_valem_no_cursor(
    perfis: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Sensibilidade 12 dobra o passo; «Inverter esquerda e direita» troca o
    lado. É o arranjo da peça, inteiro, que vai ao cursor.

    MORDIDA: faça o `para_o_cursor` devolver `ArranjoDeMovimento(destino="mouse")`
    em vez de `replace(...)` e os ajustes dela somem.
    """
    nav = _navegacao(tmp_path, monkeypatch, "bt")
    _mira_set(nav.servidor, uniq=_P[2], ligada=True, sensibilidade=12,
              inverter_horizontal=True)
    assert _ate_andar(nav) == (-2 * _PX_POR_TIQUE, 0)


def test_o_ignorar_tremor_corta_o_giro_lento(
    perfis: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Um tremor de 20 °/s abaixo de um «Ignorar tremor até» de 24: nada anda.

    MORDIDA: tire a pergunta `deflexao(velocidade) == (0, 0)` do ramo do cursor
    e o tremor move o cursor.
    """
    nav = _navegacao(tmp_path, monkeypatch, "usb", giro=(0.0, 20.0, 0.0))
    _mira_set(nav.servidor, uniq=_P[3], ligada=True, zona_morta_graus_s=24.0)
    assert _ate_andar(nav) == (0, 0)


@pytest.mark.parametrize("jogador", [1, 3])
def test_so_enquanto_eu_segurar_vale_no_primario_e_nos_outros(
    perfis: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, jogador: int,
) -> None:
    """«Só enquanto eu segurar» com L2: solto, o cursor fica; apertado, anda.
    O primário pergunta aos botões do tique; o P3 pergunta ao leitor de
    entradas do hub, sem grab.

    MORDIDA: devolva sempre o vazio em `_botoes_da_peca` e o P3 nunca anda.
    """
    nav = _navegacao(tmp_path, monkeypatch, "bt")
    _mira_set(nav.servidor, uniq=_P[jogador], ligada=True, gatilho="l2")
    assert _ate_andar(nav) == (0, 0), "a mira andou com o botão solto"
    apertado = frozenset({"l2_btn"})
    nav.mesa.entradas[_P[jogador]].botoes = apertado
    antes = _andou(nav.mouse, nav.no)
    _tique(nav, apertado if jogador == 1 else frozenset())
    _tique(nav, apertado if jogador == 1 else frozenset())
    depois = _andou(nav.mouse, nav.no)
    assert depois[0] - antes[0] > 0, f"P{jogador}: L2 apertado e o cursor parado"


def test_o_giroscopio_desligado_nao_move_o_cursor(
    perfis: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """O interruptor do Giroscópio dela vale na Navegação: desligado, nada anda.

    MORDIDA: tire o portão `REGISTRO.estado(uniq).giroscopio` do motor.
    """
    nav = _navegacao(tmp_path, monkeypatch, "usb")
    _mira_set(nav.servidor, uniq=_P[2], ligada=True)
    REGISTRO.definir(_P[2], giroscopio=False)
    assert _ate_andar(nav) == (0, 0)


# ---------------------------------------------------------------------------
# 3. O ÂNGULO DE UM SILÊNCIO NÃO É MOVIMENTO
# ---------------------------------------------------------------------------


def test_a_volta_de_um_silencio_nao_salta_o_cursor(
    perfis: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Dez minutos sem o tique da Navegação (a emulação calada por um jogo, a
    pausa, o modo com controle virtual) com o controle girando: o leitor
    acumulou 76.800 graus. A volta não pode despejá-los: o primeiro tique
    descarta, e o seguinte anda um passo normal.

    MORDIDA: faça `roteador.angulo_do_tique` devolver sempre o ângulo e o
    primeiro tique salta mais de um milhão de pixels.
    """
    nav = _navegacao(tmp_path, monkeypatch, "bt")
    _mira_set(nav.servidor, uniq=_P[4], ligada=True)
    assert _ate_andar(nav) == (_PX_POR_TIQUE, 0)
    nav.relogio.andar(600.0)
    antes = _andou(nav.mouse, nav.no)
    _tique(nav)
    salto = _andou(nav.mouse, nav.no)[0] - antes[0]
    assert salto == 0, f"a volta do silêncio saltou {salto} px"
    _tique(nav)
    assert _andou(nav.mouse, nav.no)[0] - antes[0] == _PX_POR_TIQUE


def test_o_chip_que_acende_depois_nao_despeja_o_acumulado(
    perfis: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """O leitor fica aberto com o chip apagado (o cartão da tela lê o giro), e
    ninguém drena. Quando ela acende o chip, o primeiro tique não salta.

    MORDIDA: a mesma do silêncio.
    """
    nav = _navegacao(tmp_path, monkeypatch, "usb")
    nav.mesa.hub.velocidade_do_movimento(_P[2])  # o cartão pediu o giro
    nav.mesa.hub.reconciliar()
    nav.relogio.andar(120.0)
    _mira_set(nav.servidor, uniq=_P[2], ligada=True)
    _tique(nav)
    assert _andou(nav.mouse, nav.no) == (0, 0), "o chip acendeu e o cursor saltou"
    _tique(nav)
    assert _andou(nav.mouse, nav.no) == (_PX_POR_TIQUE, 0)


@pytest.mark.parametrize(("anterior", "agora", "passa"), [
    (None, 10.0, False),              # nunca drenou: o que veio é acumulado
    (10.0, 10.0 + _TIQUE_S, True),    # o tique seguinte
    (10.0, 10.0 + rot.SILENCIO_DA_DRENAGEM_S, True),  # a borda ainda é tique
    (10.0, 10.0 + rot.SILENCIO_DA_DRENAGEM_S + 0.01, False),
])
def test_o_relogio_da_drenagem(anterior: float | None, agora: float, passa: bool) -> None:
    """A regra pura: passa o ângulo de quem drenou há até meio segundo.

    MORDIDA: troque o `>` por `>=` e a borda reprova.
    """
    dono = SimpleNamespace()
    if anterior is not None:
        assert rot.angulo_do_tique(dono, _P[1], (0.0, 1.0, 0.0), anterior) is None
    volta = rot.angulo_do_tique(dono, _P[1], (0.0, 1.0, 0.0), agora)
    assert (volta is not None) is passa, (anterior, agora, volta)


# ---------------------------------------------------------------------------
# 4. O QUE NÃO MUDA
# ---------------------------------------------------------------------------


def test_sem_mira_nenhuma_nada_drena_e_o_cursor_fica(
    perfis: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Sem chip aceso e sem mira no perfil, o tique da Navegação paga o
    `roteador.ativo` e mais nada: o motor nem é chamado, nenhum leitor é
    pedido, nenhum pixel anda.

    MORDIDA: tire o `if arranjo is None: return` de `mover_o_cursor_pelo_giro`
    e o motor passa a ser chamado a cada tique. (O comportamento sozinho não
    morde, e isso foi medido: sem o atalho o tique leva o `SO_NAS_PECAS`, que é
    desligado, e o motor volta no portão da peça sem drenar — o atalho é de
    CUSTO, e é o custo que esta régua conta.)
    """
    nav = _navegacao(tmp_path, monkeypatch, "usb")
    chamadas: list[str | None] = []
    motor = gp.aplicar_o_movimento

    def _contar(*args: Any, **kw: Any) -> Any:
        chamadas.append(kw.get("uniq"))
        return motor(*args, **kw)

    monkeypatch.setattr(gp, "aplicar_o_movimento", _contar)
    assert _ate_andar(nav) == (0, 0)
    assert nav.mesa.movimento == {}, "sem mira, o tique pediu leitor de movimento"
    assert chamadas == [], f"sem mira, o motor foi chamado {len(chamadas)} vez(es)"


def test_a_chave_do_hub_e_a_do_backend(
    perfis: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """As peças que não são o primário vão ao hub pela chave de doze hex — a
    grafia de `discover_dualsense_motion_evdevs`. Uma peça pedida com outra
    grafia abriria um leitor que ninguém tem e o cursor ficaria parado.

    MORDIDA: faça `_pecas_da_navegacao` devolver `aa:bb:cc:…` e o P2 para.
    """
    nav = _navegacao(tmp_path, monkeypatch, "bt")
    _mira_set(nav.servidor, uniq="AA:BB:CC:00:00:02", ligada=True)
    assert _ate_andar(nav) == (_PX_POR_TIQUE, 0)
    assert set(nav.mesa.movimento) == {_P[2]}


def test_sem_o_mouse_emulado_o_tique_da_navegacao_nao_drena(
    perfis: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """O mouse emulado desligado: o `dispatch_mouse` volta cedo e ninguém
    drena — a volta dele é a do silêncio, que a régua da seção 3 cobre.

    MORDIDA: chame a mira antes do `device is None` e esta régua reprova.
    """
    nav = _navegacao(tmp_path, monkeypatch, "usb")
    _mira_set(nav.servidor, uniq=_P[1], ligada=True)
    nav.daemon._mouse_device = None
    _tique(nav)
    nav.mesa.hub.reconciliar()
    _tique(nav)
    assert all(leitor.drenagens == 0 for leitor in nav.mesa.movimento.values())



# ---------------------------------------------------------------------------
# 5. O «FLUINDO» COM O GIROSCÓPIO DESLIGADO — `controller_card.texto_motion`
# ---------------------------------------------------------------------------


def _com_espelho(jogador: int) -> dict[str, Any]:
    return {"rumble_ff": {"per_vpad": [
        {"player": jogador, "motion_streaming": True, "motion_hz": 250.0}]}}


@pytest.mark.parametrize(("entrada", "jogador"), [
    ({"is_primary": True}, 1),       # o primário, fora do co-op
    ({"player": 3}, 3),              # um secundário do co-op
])
def test_o_giroscopio_desligado_nao_diz_que_flui(entrada: dict[str, Any], jogador: int) -> None:
    """Com o chip Giroscópio desligado, o filtro tira o giro da janela do
    report daquele controle, e o `motion_streaming` segue pelo acelerômetro:
    «fluindo para o jogo» seria fato errado. Só o `False` DITO pelo daemon
    apaga a linha — sem o bloco `sensores`, ninguém leu.

    MORDIDA: tire a guarda `giroscopio_ligado is False` de `texto_motion` e os
    dois casos reprovam.
    """
    from hefesto_dualsense4unix.app.widgets.controller_card import texto_motion

    estado = _com_espelho(jogador)
    ligado = {**entrada, "sensores": {"giroscopio_ligado": True}}
    desligado = {**entrada, "sensores": {"giroscopio_ligado": False}}
    assert texto_motion(ligado, estado) == "Giroscópio: fluindo para o jogo (~250 Hz)"
    assert texto_motion(entrada, estado) == "Giroscópio: fluindo para o jogo (~250 Hz)"
    assert texto_motion(desligado, estado) is None


def test_o_giroscopio_desligado_apaga_a_linha_do_cartao() -> None:
    """Pelo pacote da aba 02, que é quem leva a linha à tela: o vazio a esconde."""
    import pacotes
    import pacotes.a02_controles as a02

    dele = {"uniq": "aa:bb:cc:00:00:02", "transport": "bt", "connected": True,
            "is_primary": True, "inputs": {}, "audio": {}, "speaker": {},
            "sensores": {"giroscopio_ligado": False}}
    ctx = pacotes.Contexto(state=_com_espelho(1), mesa=[], conectados=[dele], estados={})
    cards = a02.pacote(ctx)["cards"]
    assert [c["giro-no-jogo"] for c in cards.values()] == [""], cards


# ---------------------------------------------------------------------------
# 6. NO MODO NATIVO A TELA MOSTRA A COR — `D-2409-NO-NATIVO-A-TELA-MOSTRA-A-COR`
# ---------------------------------------------------------------------------
#: A barra acesa numa cor que o Hefesto escreveu (fonte NOSSA), nos dois
#: transportes. É o estado do Nativo depois da `D-2309-NO-NATIVO-A-LUZ-E-O-
#: NUMERO-SAO-DO-HEFESTO`: a vigia do sequestro a reafirma em até 1 s.
_ACESA = {"lightbar_rgb": [0, 0, 255], "lightbar_on": True, "lightbar_source": "sysfs"}


@pytest.mark.parametrize("transporte", ["usb", "bluetooth"])
def test_no_nativo_a_aba_02_mostra_a_cor_e_nao_jogo(transporte: str) -> None:
    """A aba 02 mostrava «Jogo» no lugar da cor, e o hover dizia «Em Nativo o
    jogo é dono do LED». A cor aparece como em qualquer modo, sem palavra nova.

    MORDIDA: devolva o ramo `native_mode` ao `controller_card.rotulo_lightbar`
    e os dois casos reprovam.
    """
    import pacotes
    import pacotes.a02_controles as a02

    dele = {"uniq": "aa:bb:cc:00:00:03", "transport": transporte, "connected": True,
            "inputs": {}, "audio": {}, "speaker": {}, **_ACESA}
    ctx = pacotes.Contexto(state={"native_mode": True}, mesa=[], conectados=[dele],
                           estados={})
    campos = next(iter(a02.pacote(ctx)["cards"].values()))
    assert campos["luz-hex"] == "#0000FF", campos["luz-hex"]
    assert campos["luz-porque"] == a02.DICA_DA_LUZ
    assert "Jogo" not in a02.PALAVRA_DA_LUZ.values()


def test_no_nativo_a_aba_04_desenha_a_tira_na_cor() -> None:
    """A aba 04 desenhava a tira tracejada do «não sei» no Nativo. Com a barra
    do Hefesto, a tira é a da cor, como em todo modo.

    MORDIDA: a mesma — o ramo `native_mode` de volta ao motor.
    """
    from pacotes import a04_iluminacao as a04

    from hefesto_dualsense4unix.app.widgets.controller_card import rotulo_lightbar

    recado, base = rotulo_lightbar(dict(_ACESA), {"native_mode": True})
    assert (recado, base) == (None, (0, 0, 255))
    assert a04.estado_da_tira(recado) == a04.ACESA
