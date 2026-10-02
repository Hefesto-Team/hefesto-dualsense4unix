"""A-MIRA-NA-NAVEGACAO-01 — na Navegação, o giro move o cursor."""

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

_RAIZ = Path(__file__).resolve().parents[2]
_INTERFACE = str(_RAIZ / "src" / "hefesto_dualsense4unix" / "interface")
if _INTERFACE not in sys.path:
    sys.path.insert(0, _INTERFACE)

_P = {n: f"aabbcc00000{n}" for n in (1, 2, 3, 4)}

_GIRO_S = 128.0
_TIQUE_S = 1.0 / 64.0
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
    """O leitor do nó «Motion Sensors» — a única peça de mentira da torneira."""

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
    """O leitor de gamepad SEM grab que o hub abre para o «Só enquanto eu"""

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
    """O nó `uinput` de mentira: do tamanho do `uinput.Device` para o que o"""

    def __init__(self) -> None:
        self.eventos: list[tuple[Any, int]] = []

    def emit(self, codigo: Any, valor: int, syn: bool = True) -> None:
        self.eventos.append((codigo, valor))

    def syn(self) -> None:
        pass


def _modulo_uinput() -> Any:
    """As constantes do `python-uinput` que o device lê: os eixos relativos e as"""
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
    """O registro de identidade, do tamanho do real para o que o tique pergunta:"""

    def __init__(self, conectados: set[str]) -> None:
        self._conectados = set(conectados)

    def snapshot_connected(self) -> set[str]:
        return set(self._conectados)


def _navegacao(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, transporte: str,
    *, perfil: Profile | None = None, giro: tuple[float, float, float] = (0.0, _GIRO_S, 0.0),
) -> SimpleNamespace:
    """O `Daemon` e o `IpcServer` do produto, na Navegação: sem controle"""
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
    """Os três primeiros tiques, no ritmo do produto, e quanto o cursor andou no"""
    _tique(nav, botoes)
    nav.mesa.hub.reconciliar()
    _tique(nav, botoes)
    antes = _andou(nav.mouse, nav.no)
    _tique(nav, botoes)
    depois = _andou(nav.mouse, nav.no)
    return depois[0] - antes[0], depois[1] - antes[1]


@pytest.mark.parametrize("transporte", ["usb", "bt"])
@pytest.mark.parametrize("jogador", [1, 2, 3, 4])
def test_na_navegacao_o_chip_de_cada_um_move_o_cursor(
    perfis: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    jogador: int, transporte: str,
) -> None:
    """Os quatro controles girando igual; só o chip do jogador N aceso. O cursor"""
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
    """O mouse é um só: o P2 e o P3 com a Mira movem o MESMO cursor, e os dois"""
    nav = _navegacao(tmp_path, monkeypatch, "bt")
    for n in (2, 3):
        _mira_set(nav.servidor, uniq=_P[n], ligada=True)
    assert _ate_andar(nav) == (2 * _PX_POR_TIQUE, 0)


def test_a_mira_do_perfil_inteiro_move_com_os_quatro_conectados(
    perfis: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A mira no PERFIL (a mesa inteira), com o registro de identidade dizendo"""
    perfil = Profile(name="Mesa", match=MatchAny(type="any"),
                     movimento=ProfileMovimentoConfig(destino="analogico_direito"))
    nav = _navegacao(tmp_path, monkeypatch, "usb", perfil=perfil)
    nav.daemon.identity_registry = _RegistroDeIdentidade({_P[1], _P[2], _P[3]})
    assert _ate_andar(nav) == (3 * _PX_POR_TIQUE, 0)
    assert _P[4] not in nav.mesa.movimento, "o P4 fora da mesa ganhou leitor"


def test_o_chip_aceso_de_quem_saiu_da_mesa_nao_pede_leitor(
    perfis: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """O chip é opinião GRAVADA no perfil e sobrevive à saída do controle: o P4"""
    nav = _navegacao(tmp_path, monkeypatch, "bt")
    for n in (2, 4):
        _mira_set(nav.servidor, uniq=_P[n], ligada=True)
    nav.daemon.identity_registry = _RegistroDeIdentidade({_P[1], _P[2], _P[3]})
    assert _ate_andar(nav) == (_PX_POR_TIQUE, 0)
    assert _P[4] not in nav.mesa.movimento, "o chip de quem saiu pediu leitor"


def test_na_navegacao_o_destino_e_o_cursor_nunca_o_analogico(
    perfis: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """O chip grava o analógico direito, que na Navegação é a RODA do mouse: o"""
    nav = _navegacao(tmp_path, monkeypatch, "usb")
    _mira_set(nav.servidor, uniq=_P[1], ligada=True)
    assert _ate_andar(nav)[0] == _PX_POR_TIQUE
    u = nav.mouse._uinput_mod
    assert not [e for e in nav.no.eventos if e[0] in (u.REL_WHEEL, u.REL_HWHEEL)]


def test_a_sensibilidade_e_o_inverter_valem_no_cursor(
    perfis: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Sensibilidade 12 dobra o passo; «Inverter esquerda e direita» troca o"""
    nav = _navegacao(tmp_path, monkeypatch, "bt")
    _mira_set(nav.servidor, uniq=_P[2], ligada=True, sensibilidade=12,
              inverter_horizontal=True)
    assert _ate_andar(nav) == (-2 * _PX_POR_TIQUE, 0)


def test_o_ignorar_tremor_corta_o_giro_lento(
    perfis: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Um tremor de 20 °/s abaixo de um «Ignorar tremor até» de 24: nada anda."""
    nav = _navegacao(tmp_path, monkeypatch, "usb", giro=(0.0, 20.0, 0.0))
    _mira_set(nav.servidor, uniq=_P[3], ligada=True, zona_morta_graus_s=24.0)
    assert _ate_andar(nav) == (0, 0)


@pytest.mark.parametrize("jogador", [1, 3])
def test_so_enquanto_eu_segurar_vale_no_primario_e_nos_outros(
    perfis: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, jogador: int,
) -> None:
    """«Só enquanto eu segurar» com L2: solto, o cursor fica; apertado, anda."""
    nav = _navegacao(tmp_path, monkeypatch, "bt")
    _mira_set(nav.servidor, uniq=_P[jogador], ligada=True, gatilho="l2")
    assert _ate_andar(nav) == (0, 0), "a mira andou com o botão solto"
    apertado = frozenset({"l2_btn"})
    if jogador != 1:
        nav.mesa.entradas[_P[jogador]].botoes = apertado
    antes = _andou(nav.mouse, nav.no)
    _tique(nav, apertado if jogador == 1 else frozenset())
    _tique(nav, apertado if jogador == 1 else frozenset())
    depois = _andou(nav.mouse, nav.no)
    assert depois[0] - antes[0] > 0, f"P{jogador}: L2 apertado e o cursor parado"


def test_o_giroscopio_desligado_nao_move_o_cursor(
    perfis: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """O interruptor do Giroscópio dela vale na Navegação: desligado, nada anda."""
    nav = _navegacao(tmp_path, monkeypatch, "usb")
    _mira_set(nav.servidor, uniq=_P[2], ligada=True)
    REGISTRO.definir(_P[2], giroscopio=False)
    assert _ate_andar(nav) == (0, 0)


def test_a_volta_de_um_silencio_nao_salta_o_cursor(
    perfis: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Dez minutos sem o tique da Navegação (a emulação calada por um jogo, a"""
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
    """O leitor fica aberto com o chip apagado (o cartão da tela lê o giro), e"""
    nav = _navegacao(tmp_path, monkeypatch, "usb")
    nav.mesa.hub.velocidade_do_movimento(_P[2])
    nav.mesa.hub.reconciliar()
    nav.relogio.andar(120.0)
    _mira_set(nav.servidor, uniq=_P[2], ligada=True)
    _tique(nav)
    assert _andou(nav.mouse, nav.no) == (0, 0), "o chip acendeu e o cursor saltou"
    _tique(nav)
    assert _andou(nav.mouse, nav.no) == (_PX_POR_TIQUE, 0)


@pytest.mark.parametrize(("anterior", "agora", "passa"), [
    (None, 10.0, False),
    (10.0, 10.0 + _TIQUE_S, True),
    (10.0, 10.0 + rot.SILENCIO_DA_DRENAGEM_S, True),
    (10.0, 10.0 + rot.SILENCIO_DA_DRENAGEM_S + 0.01, False),
])
def test_o_relogio_da_drenagem(anterior: float | None, agora: float, passa: bool) -> None:
    """A regra pura: passa o ângulo de quem drenou há até meio segundo."""
    dono = SimpleNamespace()
    if anterior is not None:
        assert rot.angulo_do_tique(dono, _P[1], (0.0, 1.0, 0.0), anterior) is None
    volta = rot.angulo_do_tique(dono, _P[1], (0.0, 1.0, 0.0), agora)
    assert (volta is not None) is passa, (anterior, agora, volta)


def test_sem_mira_nenhuma_nada_drena_e_o_cursor_fica(
    perfis: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Sem chip aceso e sem mira no perfil, o tique da Navegação paga o"""
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
    """As peças que não são o primário vão ao hub pela chave de doze hex — a"""
    nav = _navegacao(tmp_path, monkeypatch, "bt")
    _mira_set(nav.servidor, uniq="AA:BB:CC:00:00:02", ligada=True)
    assert _ate_andar(nav) == (_PX_POR_TIQUE, 0)
    assert set(nav.mesa.movimento) == {_P[2]}


def test_sem_o_mouse_emulado_o_tique_da_navegacao_nao_drena(
    perfis: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """O mouse emulado desligado: o `dispatch_mouse` volta cedo e ninguém"""
    nav = _navegacao(tmp_path, monkeypatch, "usb")
    _mira_set(nav.servidor, uniq=_P[1], ligada=True)
    nav.daemon._mouse_device = None
    _tique(nav)
    nav.mesa.hub.reconciliar()
    _tique(nav)
    assert all(leitor.drenagens == 0 for leitor in nav.mesa.movimento.values())


# 5. O «FLUINDO» COM O GIROSCÓPIO DESLIGADO — `controller_card.texto_motion`


def _com_espelho(jogador: int) -> dict[str, Any]:
    return {"rumble_ff": {"per_vpad": [
        {"player": jogador, "motion_streaming": True, "motion_hz": 250.0}]}}


@pytest.mark.parametrize(("entrada", "jogador"), [
    ({"is_primary": True}, 1),
    ({"player": 3}, 3),
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


def test_na_mascara_xbox_o_giroscopio_desligado_nao_diz_que_segue_ativo() -> None:
    """A frase da máscara Xbox termina em «no Hefesto ele segue ativo», e ao"""
    from hefesto_dualsense4unix.app.widgets.controller_card import (
        _FRASE_MASCARA_XBOX,
        texto_motion,
    )

    xbox = {**_com_espelho(1), "gamepad_emulation": {"enabled": True, "flavor": "xbox"}}
    frase = f"Giroscópio: {_FRASE_MASCARA_XBOX['giroscopio']}"
    base = {"is_primary": True}
    assert texto_motion({**base, "sensores": {"giroscopio_ligado": True}}, xbox) == frase
    assert texto_motion({**base, "mira": {"ligada": True}}, xbox) == frase
    assert texto_motion({**base, "sensores": {"giroscopio_ligado": False}}, xbox) is None


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
    """A aba 04 desenhava a tira tracejada do «não sei» no Nativo. Com a barra"""
    from pacotes import a04_iluminacao as a04

    from hefesto_dualsense4unix.app.widgets.controller_card import rotulo_lightbar

    recado, base = rotulo_lightbar(dict(_ACESA), {"native_mode": True})
    assert (recado, base) == (None, (0, 0, 255))
    assert a04.estado_da_tira(recado) == a04.ACESA


_DICA_DE_HOJE = "Ligado: o jogo recebe o giro deste controle."
_DICA_NO_DIREITO = ("Com a Mira Virtual acesa, o giro deste controle vai ao jogo "
                    "pelo analógico direito.")
_DICA_NO_ESQUERDO = ("Com a Mira Virtual acesa, o giro deste controle vai ao jogo "
                     "pelo analógico esquerdo.")
_DICA_NO_CURSOR = "Com a Mira Virtual acesa, o giro deste controle move o cursor."

#: Os três modos vivos, na forma do `state_full` que `mode_of_state` lê.
_NAVEGACAO = {"native_mode": False, "gamepad_emulation": {"enabled": False}}
_VIRTUAL = {"native_mode": False, "gamepad_emulation": {"enabled": True}}
_NATIVO = {"native_mode": True, "gamepad_emulation": {"enabled": False}}


def _dicas(monkeypatch: pytest.MonkeyPatch, estado: dict[str, Any],
           miras: dict[int, dict[str, Any] | None]) -> dict[int, str]:
    """A dica do Giroscópio de cada controle, pelo pacote da aba 02 — um"""
    import pacotes
    import pacotes.a02_controles as a02

    monkeypatch.setattr(a02, "_so_se_a_pagina_tiver", lambda campos: campos)
    conectados = []
    for n, mira in miras.items():
        dele: dict[str, Any] = {
            "uniq": f"aa:bb:cc:00:00:0{n}", "transport": "usb" if n % 2 else "bluetooth",
            "connected": True, "inputs": {}, "audio": {}, "speaker": {}}
        if mira is not None:
            dele["mira"] = mira
        conectados.append(dele)
    ctx = pacotes.Contexto(state=estado, mesa=[], conectados=conectados, estados={})
    cards = a02.pacote(ctx)["cards"]
    return {int(u[-1]): c["giro-dica"] for u, c in cards.items()}


def test_na_navegacao_a_dica_diz_que_o_giro_move_o_cursor(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Na Navegação o giro de quem está com a Mira acesa move o cursor, e a"""
    acesa = {"ligada": True, "destino": "analogico_direito"}
    dicas = _dicas(monkeypatch, _NAVEGACAO,
                   {1: acesa, 2: {"ligada": False, "destino": "nenhum"}, 3: acesa, 4: None})
    assert dicas == {1: _DICA_NO_CURSOR, 2: _DICA_DE_HOJE, 3: _DICA_NO_CURSOR,
                     4: _DICA_DE_HOJE}, dicas


@pytest.mark.parametrize(("estado", "esperada"), [
    (_VIRTUAL, _DICA_NO_DIREITO),
    (_NATIVO, _DICA_DE_HOJE),
    ({}, _DICA_NO_DIREITO),
])
def test_fora_da_navegacao_a_dica_nao_fala_do_cursor(
    monkeypatch: pytest.MonkeyPatch, estado: dict[str, Any], esperada: str,
) -> None:
    """O controle da régua de cima: o MESMO chip aceso, fora da Navegação.

    MORDIDA: faça `_na_navegacao` devolver `True` para o estado vazio (o
    `mode_of_state({})` cru) e o terceiro caso reprova.
    """
    dicas = _dicas(monkeypatch, estado, {2: {"ligada": True, "destino": "analogico_direito"}})
    assert dicas == {2: esperada}


@pytest.mark.parametrize(("destino", "esperada"), [
    ("analogico_direito", _DICA_NO_DIREITO),
    ("analogico_esquerdo", _DICA_NO_ESQUERDO),
    ("mouse", _DICA_NO_CURSOR),
])
def test_a_dica_segue_o_destino_que_o_daemon_publica(
    monkeypatch: pytest.MonkeyPatch, destino: str, esperada: str,
) -> None:
    """O destino fora do padrão (só no perfil escrito à mão) não pode acender"""
    dicas = _dicas(monkeypatch, _VIRTUAL, {3: {"ligada": True, "destino": destino}})
    assert dicas == {3: esperada}


def _dica_do_jogador() -> str:
    """O texto da dica do rótulo «Jogador» na bancada da 04, sem comentário."""
    import re

    pagina = (_RAIZ / "mockup" / "04-iluminacao.html").read_text(encoding="utf-8")
    bloco = pagina.split('<div class="sec-rot">Jogador', 1)[1]
    bloco = bloco.split('<span class="dica">', 1)[1].split("</span></span>", 1)[0]
    bloco = re.sub(r"<!--.*?-->", "", bloco, flags=re.S)
    return " ".join(re.sub(r"<[^>]+>", " ", bloco).split())


def test_a_dica_do_jogador_nao_diz_que_o_jogo_manda_no_numero() -> None:
    """MORDIDA: devolva «Um jogo em co-op pode mandar o próprio número por"""
    texto = _dica_do_jogador()
    assert "por cima" not in texto, texto
    assert "volta em até um segundo" in texto, texto


def test_o_segundo_da_dica_e_a_conta_da_vigia() -> None:
    """A dica promete UM segundo, e a promessa é a conta do dono."""
    import math

    from hefesto_dualsense4unix.core import escritor_cru
    from hefesto_dualsense4unix.core.backend_pydualsense import numeracao_do_jogo

    passo = escritor_cru.PASSO_DA_VIGIA_S
    reescrita = math.ceil(escritor_cru.INTERVALO_DA_REAFIRMACAO_S / passo) * passo
    assert reescrita <= 1.0, (
        f"a vigia reescreve a cada {reescrita} s e a dica promete um segundo")
    assert "player_leds" in numeracao_do_jogo(
        {"player_leds": (True, False, False, False, False)})
