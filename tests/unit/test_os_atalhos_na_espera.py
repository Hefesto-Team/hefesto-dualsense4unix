"""OS-ATALHOS-NA-ESPERA-01 — na espera do lugar guardado, o próximo da fila segura os atalhos do PS.

**A decisão é dela** (24/09/2026, 19h, ``D-2409-OS-ATALHOS-NA-ESPERA-FICAM-COM-
O-P2``, escolhida em opções, com a foto do dia): *«O P2 segura os atalhos
durante a espera, sem trocar de número»*; quando o P1 volta, os atalhos voltam
para ele. Revoga o «custo aceito» da ``D-2409-O-JOGO-ESPERA-O-LUGAR-GUARDADO``.

**O QUE FOI MEDIDO, antes da cura** (24/09/2026, nesta bancada, a classe real):
com o jogo aberto e o P1 fora dentro do prazo, o posto de P1 fica VAGO
(``_posto_vago_de``), o leitor do primário fica sem nó, e o laço entregava
``frozenset()`` aos atalhos em todo tique. O PS + R3, o PS + L3 e o PS sozinho
do P2 não disparavam nada — aos 2 s e aos 20 s, com 2, 3 e 4 controles, USB, BT
e a mesa mista. Com o P1 na mesa, só o PS + R3 dele disparava; de volta, também.

**A cura mora no dono** (``poll.botoes_dos_atalhos``): na vaga, os atalhos
leem o próximo da fila que está na mesa — o menor número da lâmpada entre os
jogadores do co-op com o vpad de pé —, e o vpad do P1 continua recebendo só os
botões do posto. O laço de produção entrega os botões por
``poll.observar_os_atalhos``, e o PS + L3 anda o cartão de quem segura os
atalhos (``poll.quem_segura_os_atalhos``), nunca o do P1 ausente.

**A bancada é a honesta** (:class:`MesaHonesta`, da O-VPAD-DO-P1-NAO-REPETE-O-
MAC-01): os vpads da fábrica REAL contra o kernel de mentira que recusa MAC
repetido, com o backend, o co-op e o registro de identidade reais. Ela ganha a
MÃO de quem joga — o que se aperta num controle chega a quem lê o nó dele: o
leitor do primário ou o do co-op — e o ``HotkeyManager`` real, montado pelo
``start_hotkey_manager`` real (os combos de fábrica), com os atos trocados por
quem anota o que disparou. O laço de produção é medido à parte, com o
``Daemon.run`` de verdade (:class:`TestOLacoDeProducao`).

AS MORDIDAS (24/09/2026, cada uma devolvida com o md5 conferido):

- ``botoes_dos_atalhos`` devolvendo sempre os botões do posto (o produto de
  antes) reprova a matriz do P2, o próximo da fila, os três caminhos e o
  diário: o silêncio dos 30 s volta;
- o próximo da fila pelo MAIOR número reprova os que medem quem segura com
  três ou quatro na mesa, e as testemunhas;
- a vaga perguntada ao ``primary_uniq`` fora da mesa (em vez do
  ``_posto_vago_de`` do backend) não passa pela régua do próprio dono:
  reprova ``test_a_vaga_e_a_do_backend``;
- o PS + L3 andando o cartão do ``primary_identity`` reprova
  :class:`TestOPsL3AndaOCartaoDeQuemSegura`: o do P1 ausente seria gravado;
- o laço voltando a chamar ``observe`` com os botões do posto reprova
  :class:`TestOLacoDeProducao`, e só ela — as outras chamam o dono direto.

Nenhum endereço real: faixa forjada ``aa:bb:cc`` com os octetos 4 e 5 zerados.
"""
from __future__ import annotations

import asyncio
import functools
import threading
from collections.abc import Iterator, Sequence
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

import pytest
import structlog

from hefesto_dualsense4unix.core.controller import ControllerState
from hefesto_dualsense4unix.daemon.lifecycle import Daemon, DaemonConfig
from hefesto_dualsense4unix.daemon.subsystems import external_mask as em
from hefesto_dualsense4unix.daemon.subsystems import gamepad as gp
from hefesto_dualsense4unix.daemon.subsystems import hotkey, rumble
from hefesto_dualsense4unix.daemon.subsystems.hotkey import (
    build_next_bridge_callback,
    build_next_mask_callback,
    start_hotkey_manager,
)
from hefesto_dualsense4unix.daemon.subsystems.poll import (
    botoes_dos_atalhos,
    evdev_buttons_once,
    observar_os_atalhos,
    quem_segura_os_atalhos,
)
from hefesto_dualsense4unix.integrations.hotkey_daemon import HotkeyManager
from hefesto_dualsense4unix.integrations.virtual_pad import CAMINHO_XBOX
from hefesto_dualsense4unix.testing import FakeController
from hefesto_dualsense4unix.utils import session
from tests.unit.test_coop_bancada_de_queda_do_primario import _LeitorDeSecundario
from tests.unit.test_dois_vpads_nunca_tem_o_mesmo_mac import (
    KernelDoHidPlaystation,
    kernel_de_mentira,
)
from tests.unit.test_o_buraco_de_quem_saiu_se_fecha_no_jogo import MesaHonesta
from tests.unit.test_o_jogo_espera_a_carta_do_lugar_guardado import (  # noqa: F401
    P1,
    P2,
    P3,
    P4,
    TIQUE,
    TRANSPORTES,
    UNIQS,
    Relogio,
    _LeitorDoP1,
    config_isolado,
)

#: O gesto da linha 17 e da O-ASSENTO-02: fora vinte segundos, dentro do prazo.
VINTE_SEGUNDOS = 20.0

#: Os atos do ``HotkeyManager``, pelo nome do gesto que cada um responde.
ATOS = {
    "on_next_bridge": "ponte",
    "on_next_mask": "mascara",
    "on_ps_solo": "ps_solo",
    "on_next": "perfil_seguinte",
    "on_prev": "perfil_anterior",
    "on_ps_long_press": "modo_jogo",
}

#: Os seis atalhos do PS, e o que cada um dispara.
GESTOS = [
    pytest.param(("ps", "r3"), "ponte", id="ps-r3-proximo-modo"),
    pytest.param(("ps", "l3"), "mascara", id="ps-l3-proxima-mascara"),
    pytest.param(("ps",), "ps_solo", id="ps-sozinho"),
    pytest.param(("ps", "dpad_up"), "perfil_seguinte", id="ps-cima"),
    pytest.param(("ps", "dpad_down"), "perfil_anterior", id="ps-baixo"),
    pytest.param(("ps", "options"), "modo_jogo", id="ps-options"),
]

#: A matriz de sempre: dois, três e quatro controles; USB, BT e a mesa mista.
MATRIZ = pytest.mark.parametrize(
    ("quantos", "transporte"),
    [(n, t) for n in (2, 3, 4) for t in TRANSPORTES],
    ids=[f"{n}-controles-{t}" for n in (2, 3, 4) for t in TRANSPORTES],
)

#: Os três caminhos da casa: o Virtual (uhid), o Xbox (uinput) e o Nativo (o
#: jogo recebe o físico, sem vpad do Hefesto).
CAMINHO_VIRTUAL = "virtual"
CAMINHO_NATIVO = "nativo"
CAMINHOS = [CAMINHO_VIRTUAL, CAMINHO_XBOX, CAMINHO_NATIVO]


@pytest.fixture
def kernel(monkeypatch: pytest.MonkeyPatch) -> Iterator[KernelDoHidPlaystation]:
    """O kernel de mentira da O-VPAD: nenhum ``/dev/uhid`` ou ``/dev/uinput`` de verdade."""
    with kernel_de_mentira(monkeypatch) as k:
        yield k


# ---------------------------------------------------------------------------
# A mão de quem joga
# ---------------------------------------------------------------------------


class _LeitorDoP1QueAperta(_LeitorDoP1):
    """O leitor do P1 da bancada, que também devolve o que se aperta no nó que ele lê.

    O carimbo de dono (``de:<uniq>``) continua: é por ele que a bancada sabe
    quem dirige o vpad do P1. Sem nó (a vaga), ninguém aperta nada aqui — e o
    ``evdev_buttons_once`` nem chega a pedir, porque o leitor não está de pé.
    """

    def snapshot(self) -> Any:
        base = super().snapshot()
        dono = next((u for u, n in self._mesa.nodes.items() if n == self.node), None)
        apertados = self._mesa.apertados.get(dono, frozenset()) if dono else frozenset()
        return SimpleNamespace(
            **{**vars(base), "buttons_pressed": base.buttons_pressed | apertados}
        )


class _LeitorDoCoopQueAperta(_LeitorDeSecundario):
    """O leitor de um jogador do co-op, que devolve o que se aperta no controle DELE.

    Só enquanto o nó que ele segura ainda é o do controle: quem saiu da mesa
    não aperta nada, e um nó renumerado não herda os botões de ninguém.

    **E O GRAB CONFIRMA NO TIQUE SEGUINTE, como no ``EvdevReader`` de verdade**
    (conferência de 24/09/2026). O ``set_grab(True)`` que o co-op chama logo
    depois do ``start()`` acha o device ainda fechado — quem o abre é a thread
    do leitor — e fica «pending»; o vpad do jogador nasce no ``forward_all`` de
    um tique seguinte (``CoopManager._promote_pending``). O leitor da bancada de
    queda confirmava na hora, e era mais frouxo que o real justamente onde o
    PS + L3 do P2 mede: o vpad dele renasce, e a prova do aparelho olhava antes
    de ele voltar — os pulsos de falha sobre uma troca que pegou passavam
    verdes. ``mesa.grab_recusado`` recusa o grab de quem estiver nele: o
    controle que outro leitor exclusivo segura.
    """

    def set_grab(self, grab: bool) -> bool:
        mesa = type(self).mesa
        if grab and self.target_uniq in getattr(mesa, "grab_recusado", ()):
            self.grab_state = "failed"
            return False
        aplicado = super().set_grab(grab)
        if grab and aplicado:
            self.grab_state = "pending"
        return aplicado

    def abrir(self) -> None:
        """A thread do leitor abriu o device: o grab pedido passa a valer."""
        if self.grab_state == "pending":
            self.grab_state = "held"

    def snapshot(self) -> Any:
        mesa = type(self).mesa
        assert mesa is not None
        uniq = self.target_uniq
        apertados: frozenset[str] = frozenset()
        if uniq is not None and mesa.nodes.get(uniq) == self.node:
            apertados = mesa.apertados.get(uniq, frozenset())  # type: ignore[attr-defined]
        return SimpleNamespace(
            lx=128, ly=128, rx=128, ry=128, l2_raw=0, r2_raw=0, buttons_pressed=apertados
        )


class MesaDosAtalhos(MesaHonesta):
    """A bancada honesta, com a mão de quem joga e o gerente de atalhos real.

    ``caminho`` escolhe um dos três caminhos: o Virtual é o da bancada; no
    Xbox o posto e os jogadores nascem pelo ``uinput`` (o de mentira do
    kernel); no Nativo o vpad do P1 não existe — o jogo recebe o físico.
    """

    def __init__(
        self,
        monkeypatch: pytest.MonkeyPatch,
        *,
        kernel: KernelDoHidPlaystation,
        relogio: Relogio,
        caminho: str = CAMINHO_VIRTUAL,
        jogo: bool = True,
        coop: bool = True,
    ) -> None:
        super().__init__(
            monkeypatch, kernel=kernel, relogio=relogio, tempo=relogio, jogo=jogo, coop=coop
        )
        self.mesa.apertados = {}  # type: ignore[attr-defined]
        self.mesa.grab_recusado = set()  # type: ignore[attr-defined]
        leitor = _LeitorDoP1QueAperta(self.mesa)
        self.leitor_p1 = leitor
        self.inst._evdev = leitor
        monkeypatch.setattr(
            "hefesto_dualsense4unix.core.evdev_reader.EvdevReader", _LeitorDoCoopQueAperta
        )
        self.caminho = caminho
        if caminho == CAMINHO_XBOX:
            self.daemon.config.gamepad_caminho = CAMINHO_XBOX
            self.vpad_do_p1.stop()
            self.vpads = []
            posto = self._nascer_vpad(
                "dualsense", player=1, identity=None, allow_uhid=True, caminho=CAMINHO_XBOX
            )
            self.vpad_do_p1 = self.daemon._gamepad_device = posto
        elif caminho == CAMINHO_NATIVO:
            # O Modo Nativo solta o vpad do P1: o jogo recebe o físico.
            self.vpad_do_p1.stop()
            self.vpads = []
            self.daemon._gamepad_device = None
        start_hotkey_manager(self.daemon)  # type: ignore[arg-type]
        self.disparos: list[str] = []
        gerente = self.daemon._hotkey_manager
        for atributo, nome in ATOS.items():
            setattr(gerente, atributo, self._anotador(nome))
        #: O que o laço mandou ao vpad do P1 em cada tique (`evdev_buttons_once`).
        self.ao_vpad_do_p1: list[frozenset[str]] = []

    def _anotador(self, nome: str) -> Any:
        return lambda: self.disparos.append(nome)

    def tique(self, segundos: float = TIQUE) -> None:
        """Os laços da bancada, e a metade do laço que alimenta o vpad do P1 e os atalhos.

        Entre um tique e outro, a thread de cada leitor do co-op que pediu o grab
        abriu o device (:meth:`_LeitorDoCoopQueAperta.abrir`).
        """
        for jogador in list(self.coop._players.values()):
            abrir = getattr(jogador.reader, "abrir", None)
            if callable(abrir):
                abrir()
        super().tique(segundos)
        botoes = evdev_buttons_once(self.daemon)
        self.ao_vpad_do_p1.append(botoes)
        if isinstance(self.inst._posto_vago_de, str):
            assert botoes == frozenset(), (
                f"o vpad do P1 recebe {sorted(botoes)} com o posto vago — ele espera parado"
            )
        observar_os_atalhos(self.daemon, botoes, now=self.tempo.t)

    def apertar(self, uniq: str, *botoes: str) -> list[str]:
        """``uniq`` aperta ``botoes`` juntos, segura além dos 150 ms do combo e solta."""
        antes = len(self.disparos)
        self.mesa.apertados[uniq] = frozenset(botoes)  # type: ignore[attr-defined]
        self.tique(0.0)
        self.tique(0.3)
        del self.mesa.apertados[uniq]  # type: ignore[attr-defined]
        self.tique(0.05)
        return self.disparos[antes:]

    def vaga(self) -> bool:
        return isinstance(self.inst._posto_vago_de, str)


def montar_atalhos(
    monkeypatch: pytest.MonkeyPatch,
    kernel: KernelDoHidPlaystation,
    quantos: int,
    transporte: str = "mista",
    *,
    caminho: str = CAMINHO_VIRTUAL,
    ordem: Sequence[str] | None = None,
    jogo: bool = True,
    coop: bool = True,
) -> MesaDosAtalhos:
    """A mesa de ``quantos`` controles, na ``ordem`` de chegada, com o jogo aberto."""
    relogio = Relogio()
    bancada = MesaDosAtalhos(
        monkeypatch, kernel=kernel, relogio=relogio, caminho=caminho, jogo=jogo, coop=coop
    )
    chegada = tuple(ordem) if ordem is not None else UNIQS[:quantos]
    for uniq, via in zip(chegada, TRANSPORTES[transporte][:quantos], strict=True):
        bancada.mesa.sentar(uniq, transporte=via)
    for _ in range(3):
        bancada.tique()
    assert bancada.dono_do_vpad_do_p1() == chegada[0]
    assert bancada.a_tela() == {u: n + 1 for n, u in enumerate(chegada)}
    return bancada


def _fora_dentro_do_prazo(bancada: MesaDosAtalhos, *quem: str) -> None:
    """``quem`` sai da mesa, um de cada vez, e dois tiques assentam a saída."""
    for uniq in quem:
        bancada.mesa.levantar(uniq)
        bancada.tique()
    bancada.tique()


def _gesto_com_o_laco(bancada: MesaDosAtalhos, gesto: Any) -> None:
    """O ato do gesto como o daemon o roda: uma tarefa no laço, com o poll seguindo.

    O ``HotkeyManager._fire`` agenda o callback com ``create_task`` e o laço do
    daemon continua a cada tique enquanto ele espera — é esse laço que promove o
    vpad de um jogador do co-op que renasce (``forward_all``). Rodar o callback
    sozinho (``asyncio.run``) congelaria a mesa no instante do ato. Os tiques
    daqui não andam o relógio: o prazo do lugar guardado não vence no meio.
    """

    async def _junto() -> None:
        tarefa = asyncio.ensure_future(gesto())
        while not tarefa.done():
            await asyncio.sleep(0)
            if not tarefa.done():
                bancada.tique(0.0)
        await tarefa

    asyncio.run(_junto())


def armar_o_ato_do_daemon(
    bancada: MesaDosAtalhos, monkeypatch: pytest.MonkeyPatch
) -> SimpleNamespace:
    """Os atos de verdade do ``Daemon`` no daemon de mentira da bancada.

    O PS + R3 (e o PS + L3 do cartão do posto) chamam o
    ``set_gamepad_emulation`` do ``Daemon``, que recria o vpad do posto pela
    fábrica real (contra o kernel de mentira) e força o ``sync`` do co-op.
    Dublado só o que tocaria o aparelho ou o disco dela — o grab do físico, o
    launch env, o espelho de movimento, a leitura da calibração, os motores, as
    preferências da sessão e a gravação do modo no perfil ativo — e a luz, que
    é anotada em vez de piscar. Devolve ``luz`` (cada sequência e cada piscada,
    na ordem) e ``gravado`` (o modo que o gesto gravaria no perfil).
    """
    d: Any = bancada.daemon
    d._emu_lock = threading.Lock()
    d._native_mode = False
    d._emu_manual_ts = 0.0
    d._mode_from_profile = None
    d._esquecer_mascara_adiada = lambda _motivo: None
    d.set_native_mode = lambda _ligado, **_kw: True
    d._mouse_device = None
    d.store = None
    d.set_gamepad_emulation = functools.partial(Daemon.set_gamepad_emulation, d)
    d.set_gamepad_emulation_desfecho = functools.partial(
        Daemon.set_gamepad_emulation_desfecho, d
    )
    d.vestir_a_mascara_do_aparelho = Daemon.vestir_a_mascara_do_aparelho.__get__(d)
    d.config.gamepad_emulation_enabled = True
    dubles: dict[str, Any] = {
        "_set_controller_grab": lambda _d, _grab: None,
        "_materialize_launch_env": lambda _d: None,
        "start_motion_reader": lambda _d, _dev: None,
        "stop_motion_reader": lambda _d: None,
        "read_primary_calibration": lambda _d: None,
        "make_primary_rumble_sink": lambda _d: None,
        "make_primary_replica_sinks": lambda _d: {},
    }
    for nome, valor in dubles.items():
        monkeypatch.setattr(gp, nome, valor)
    monkeypatch.setattr(rumble, "zero_motors_on_mode_exit", lambda _d: None)
    monkeypatch.setattr(session, "save_gamepad_emulation", lambda *_a, **_kw: None)
    monkeypatch.setattr(session, "save_gamepad_caminho", lambda *_a, **_kw: None)

    anotado = SimpleNamespace(luz=[], gravado=[])

    async def _sinalizar(_daemon: Any, cores: Any) -> None:
        anotado.luz.append(("pulsos", len(cores)))

    monkeypatch.setattr(hotkey, "_sinalizar_lightbar", _sinalizar)
    monkeypatch.setattr(
        hotkey, "_disparar_piscada",
        lambda _d, _cor, *, modo: anotado.luz.append(("piscada", modo)) or True,
    )
    monkeypatch.setattr(hotkey, "_appid_do_jogo_do_wrapper", lambda: None)
    monkeypatch.setattr(
        hotkey, "_gravar_o_modo_do_gesto", lambda _d, ponte: anotado.gravado.append(ponte)
    )
    # A espera da prova do PS + L3 cede o laço a cada volta, e quem anda é a
    # bancada (`_gesto_com_o_laco`): um tique por volta, sem relógio de parede.
    monkeypatch.setattr(hotkey, "_PASSO_DA_ESPERA_DO_VPAD_S", 0.0)
    return anotado


# ---------------------------------------------------------------------------
# A prova da sprint
# ---------------------------------------------------------------------------


@pytest.mark.usefixtures("config_isolado")
class TestOP2SeguraOsAtalhosNaEspera:
    """O P1 sai com o jogo aberto: o PS + R3 do P2 troca o modo dentro do prazo."""

    @MATRIZ
    def test_o_ps_r3_do_p2_troca_o_modo_e_ninguem_troca_de_numero(
        self, monkeypatch: pytest.MonkeyPatch, kernel: KernelDoHidPlaystation,
        quantos: int, transporte: str,
    ) -> None:
        """A MORDIDA desta sprint: sem a cura, o PS + R3 do P2 cai no vazio por 30 s."""
        bancada = montar_atalhos(monkeypatch, kernel, quantos, transporte)
        ficaram = UNIQS[1:quantos]
        vpads_de_antes = {u: bancada.vpad_de(u) for u in ficaram}

        saiu = bancada.tempo.t
        _fora_dentro_do_prazo(bancada, P1)
        assert bancada.vaga(), "a bancada não abriu a vaga do posto"
        assert bancada.apertar(P2, "ps", "r3") == ["ponte"], (
            "o P2 apertou PS + R3 com o P1 fora e o modo não trocou"
        )
        while bancada.tempo.t - saiu < VINTE_SEGUNDOS:
            bancada.tique()
        assert bancada.vaga(), "o prazo venceu antes dos vinte segundos"
        assert bancada.apertar(P2, "ps", "r3") == ["ponte"], "aos 20 s o atalho do P2 sumiu"

        # Sem trocar de número, de lâmpada nem de boneco.
        assert bancada.a_tela() == {u: n + 2 for n, u in enumerate(ficaram)}
        assert bancada.dono_do_vpad_do_p1() is None, "o P2 passou a dirigir o boneco 1"
        assert bancada.o_jogo_ve() == {1: None, **{n + 2: u for n, u in enumerate(ficaram)}}
        for uniq in ficaram:
            assert bancada.vpad_de(uniq) is vpads_de_antes[uniq], f"{uniq} perdeu o vpad dele"
        bancada.o_jogo_segue_a_tela()
        assert bancada.inst.primary_uniq == P1, "o posto de P1 deixou de ser do P1"

    @pytest.mark.parametrize(("botoes", "gesto"), GESTOS)
    def test_os_seis_atalhos_do_ps_ficam_com_o_p2(
        self, monkeypatch: pytest.MonkeyPatch, kernel: KernelDoHidPlaystation,
        botoes: tuple[str, ...], gesto: str,
    ) -> None:
        bancada = montar_atalhos(monkeypatch, kernel, 3)
        assert bancada.apertar(P2, *botoes) == [], "com o P1 na mesa, o P2 já segurava"
        _fora_dentro_do_prazo(bancada, P1)
        assert bancada.apertar(P2, *botoes) == [gesto]

    @MATRIZ
    def test_as_testemunhas_nao_seguram_nada(
        self, monkeypatch: pytest.MonkeyPatch, kernel: KernelDoHidPlaystation,
        quantos: int, transporte: str,
    ) -> None:
        """Os atalhos são de UM controle só: o próximo da fila, e não quem vier atrás."""
        bancada = montar_atalhos(monkeypatch, kernel, quantos, transporte)
        _fora_dentro_do_prazo(bancada, P1)
        for uniq in UNIQS[2:quantos]:
            assert bancada.apertar(uniq, "ps", "r3") == [], f"{uniq} disparou o atalho"
            assert bancada.apertar(uniq, "ps") == [], f"{uniq} disparou o PS"

    @MATRIZ
    def test_quando_o_p1_volta_os_atalhos_voltam_para_ele(
        self, monkeypatch: pytest.MonkeyPatch, kernel: KernelDoHidPlaystation,
        quantos: int, transporte: str,
    ) -> None:
        bancada = montar_atalhos(monkeypatch, kernel, quantos, transporte)
        via = bancada.mesa.transporte_de(P1)
        _fora_dentro_do_prazo(bancada, P1)
        assert bancada.apertar(P2, "ps", "r3") == ["ponte"]

        bancada.mesa.sentar(P1, transporte=via)
        bancada.tique()
        assert not bancada.vaga() and bancada.dono_do_vpad_do_p1() == P1
        assert bancada.apertar(P2, "ps", "r3") == [], "o P1 voltou e o P2 seguiu com os atalhos"
        assert bancada.apertar(P1, "ps", "r3") == ["ponte"], "o P1 voltou sem os atalhos"

    @pytest.mark.parametrize(
        ("de", "para"), [("usb", "bt"), ("bt", "usb")], ids=["cabo-para-radio", "radio-para-cabo"]
    )
    def test_a_volta_pelo_outro_transporte_devolve_os_atalhos(
        self, monkeypatch: pytest.MonkeyPatch, kernel: KernelDoHidPlaystation, de: str, para: str,
    ) -> None:
        """A linha 3 da bancada dela: o P1 sai do cabo e volta pelo rádio (e o inverso)."""
        bancada = montar_atalhos(monkeypatch, kernel, 4, "usb" if de == "usb" else "bt")
        _fora_dentro_do_prazo(bancada, P1)
        assert bancada.apertar(P2, "ps", "r3") == ["ponte"]
        bancada.mesa.sentar(P1, transporte=para)
        bancada.tique()
        assert bancada.inst.get_transport() == para
        assert bancada.apertar(P1, "ps", "r3") == ["ponte"]
        assert bancada.apertar(P2, "ps", "r3") == []

    def test_o_diario_diz_a_troca_de_mao_uma_vez_por_episodio(
        self, monkeypatch: pytest.MonkeyPatch, kernel: KernelDoHidPlaystation,
    ) -> None:
        bancada = montar_atalhos(monkeypatch, kernel, 3)
        with structlog.testing.capture_logs() as registros:
            _fora_dentro_do_prazo(bancada, P1)
            for _ in range(4):
                bancada.tique()
            bancada.mesa.sentar(P1)
            bancada.tique()
            bancada.tique()
        com_o_proximo = [r for r in registros if r["event"] == "atalhos_com_o_proximo_da_fila"]
        de_volta = [r for r in registros if r["event"] == "atalhos_voltam_ao_posto"]
        assert [r["uniq"] for r in com_o_proximo] == [P2]
        assert [r["de"] for r in de_volta] == [P2]


@pytest.mark.usefixtures("config_isolado")
class TestOProximoDaFila:
    """Quem segura: o P2; se o P2 também saiu, o P3; se o P3 também, o P4."""

    @pytest.mark.parametrize("transporte", list(TRANSPORTES))
    @pytest.mark.parametrize(
        ("fora", "segura"),
        [((P1,), P2), ((P1, P2), P3), ((P2, P1), P3), ((P1, P2, P3), P4), ((P3, P2, P1), P4)],
        ids=["sai-p1", "sai-p1-e-p2", "sai-p2-e-p1", "sai-p1-p2-p3", "sai-p3-p2-p1"],
    )
    def test_o_menor_numero_na_mesa_segura(
        self, monkeypatch: pytest.MonkeyPatch, kernel: KernelDoHidPlaystation,
        transporte: str, fora: tuple[str, ...], segura: str,
    ) -> None:
        bancada = montar_atalhos(monkeypatch, kernel, 4, transporte)
        _fora_dentro_do_prazo(bancada, *fora)
        assert bancada.vaga()
        assert quem_segura_os_atalhos(bancada.daemon) == segura
        assert bancada.apertar(segura, "ps", "r3") == ["ponte"]
        for uniq in UNIQS[:4]:
            if uniq not in fora and uniq != segura:
                assert bancada.apertar(uniq, "ps", "r3") == [], f"{uniq} não segura e disparou"
        # E ninguém trocou de número por isso.
        assert bancada.a_tela() == {u: UNIQS.index(u) + 1 for u in UNIQS[:4] if u not in fora}

    @pytest.mark.parametrize("transporte", list(TRANSPORTES))
    def test_o_p2_que_volta_na_espera_retoma_os_atalhos(
        self, monkeypatch: pytest.MonkeyPatch, kernel: KernelDoHidPlaystation, transporte: str,
    ) -> None:
        bancada = montar_atalhos(monkeypatch, kernel, 4, transporte)
        via = bancada.mesa.transporte_de(P2)
        _fora_dentro_do_prazo(bancada, P1, P2)
        assert bancada.apertar(P3, "ps", "r3") == ["ponte"]
        bancada.mesa.sentar(P2, transporte=via)
        bancada.tique()
        bancada.tique()
        assert bancada.vaga() and quem_segura_os_atalhos(bancada.daemon) == P2
        assert bancada.apertar(P2, "ps", "r3") == ["ponte"]
        assert bancada.apertar(P3, "ps", "r3") == []

    @pytest.mark.parametrize(
        "posto", [0, 1, 2, 3], ids=["posto-p1", "posto-p2", "posto-p3", "posto-p4"]
    )
    @pytest.mark.parametrize("transporte", list(TRANSPORTES))
    def test_o_vago_pode_ser_qualquer_um_que_segura_o_posto(
        self, monkeypatch: pytest.MonkeyPatch, kernel: KernelDoHidPlaystation,
        posto: int, transporte: str,
    ) -> None:
        """O posto é de quem chegou primeiro — qualquer um dos quatro controles."""
        chegada = UNIQS[posto:4] + UNIQS[:posto]
        bancada = montar_atalhos(monkeypatch, kernel, 4, transporte, ordem=chegada)
        dono, proximo, *atras = chegada
        _fora_dentro_do_prazo(bancada, dono)
        assert bancada.vaga() and bancada.inst.primary_uniq == dono
        assert bancada.apertar(proximo, "ps", "r3") == ["ponte"]
        for uniq in atras:
            assert bancada.apertar(uniq, "ps", "r3") == []
        bancada.mesa.sentar(dono)
        bancada.tique()
        assert bancada.apertar(dono, "ps", "r3") == ["ponte"]
        assert bancada.apertar(proximo, "ps", "r3") == []


@pytest.mark.usefixtures("config_isolado")
class TestOsTresCaminhos:
    """O Virtual e o Xbox têm a espera; o Nativo não tem vpad a esperar, e nada muda."""

    @pytest.mark.parametrize("transporte", list(TRANSPORTES))
    @pytest.mark.parametrize("caminho", [CAMINHO_VIRTUAL, CAMINHO_XBOX])
    def test_nos_caminhos_com_vpad_o_p2_segura(
        self, monkeypatch: pytest.MonkeyPatch, kernel: KernelDoHidPlaystation,
        caminho: str, transporte: str,
    ) -> None:
        bancada = montar_atalhos(monkeypatch, kernel, 3, transporte, caminho=caminho)
        esperado = "uhid" if caminho == CAMINHO_VIRTUAL else "uinput"
        assert getattr(bancada.vpad_de(P2), "backend", None) == esperado
        _fora_dentro_do_prazo(bancada, P1)
        assert bancada.vaga()
        assert bancada.apertar(P2, "ps", "r3") == ["ponte"]
        assert bancada.apertar(P2, "ps", "l3") == ["mascara"]
        assert bancada.apertar(P3, "ps", "r3") == []

    @pytest.mark.parametrize("transporte", list(TRANSPORTES))
    def test_no_nativo_nao_ha_espera_e_nada_muda(
        self, monkeypatch: pytest.MonkeyPatch, kernel: KernelDoHidPlaystation, transporte: str,
    ) -> None:
        """Sem vpad do P1 não há posto a guardar: o P2 assume na hora, como sempre."""
        bancada = montar_atalhos(monkeypatch, kernel, 3, transporte, caminho=CAMINHO_NATIVO)
        _fora_dentro_do_prazo(bancada, P1)
        assert not bancada.vaga()
        assert bancada.inst.primary_uniq == P2
        assert quem_segura_os_atalhos(bancada.daemon) == P2
        do_posto = frozenset({"ps", "r3"})
        assert botoes_dos_atalhos(bancada.daemon, do_posto) is do_posto


@pytest.mark.usefixtures("config_isolado")
class TestForaDaEsperaNadaMuda:
    """Sem a espera, os atalhos são do primário — do jeito que sempre foram."""

    @MATRIZ
    def test_com_todos_na_mesa_so_o_p1_segura(
        self, monkeypatch: pytest.MonkeyPatch, kernel: KernelDoHidPlaystation,
        quantos: int, transporte: str,
    ) -> None:
        bancada = montar_atalhos(monkeypatch, kernel, quantos, transporte)
        assert bancada.apertar(P1, "ps", "r3") == ["ponte"]
        for uniq in UNIQS[1:quantos]:
            assert bancada.apertar(uniq, "ps", "r3") == []
        assert quem_segura_os_atalhos(bancada.daemon) == P1

    @pytest.mark.parametrize(
        ("jogo", "coop"), [(False, True), (True, False)], ids=["sem-jogo", "sem-co-op"]
    )
    def test_sem_a_espera_o_p2_assume_na_hora_pelo_posto(
        self, monkeypatch: pytest.MonkeyPatch, kernel: KernelDoHidPlaystation,
        jogo: bool, coop: bool,
    ) -> None:
        relogio = Relogio()
        bancada = MesaDosAtalhos(
            monkeypatch, kernel=kernel, relogio=relogio, jogo=jogo, coop=coop
        )
        for uniq in UNIQS[:3]:
            bancada.mesa.sentar(uniq)
        for _ in range(3):
            bancada.tique()
        _fora_dentro_do_prazo(bancada, P1)
        assert not bancada.vaga()
        assert bancada.dono_do_vpad_do_p1() == P2, "sem a espera o P2 assume o posto na hora"
        assert quem_segura_os_atalhos(bancada.daemon) == P2
        assert bancada.apertar(P2, "ps", "r3") == ["ponte"]
        do_posto = frozenset({"cross"})
        assert botoes_dos_atalhos(bancada.daemon, do_posto) is do_posto

    def test_depois_do_prazo_os_atalhos_sao_do_novo_primario(
        self, monkeypatch: pytest.MonkeyPatch, kernel: KernelDoHidPlaystation,
    ) -> None:
        """Passado o prazo vale a NUM-01: o P2 vira o 1 e segura pelo leitor do posto."""
        bancada = montar_atalhos(monkeypatch, kernel, 3)
        _fora_dentro_do_prazo(bancada, P1)
        while bancada.vaga():
            bancada.tique()
        assert bancada.inst.primary_uniq == P2 and bancada.dono_do_vpad_do_p1() == P2
        assert bancada.apertar(P2, "ps", "r3") == ["ponte"]
        assert bancada.apertar(P3, "ps", "r3") == []


@pytest.mark.usefixtures("config_isolado")
class TestAVagaEDoBackend:
    """A vaga que os atalhos seguem é a mesma que para o vpad do P1 — um dono só."""

    @pytest.mark.parametrize("jogo", [True, False], ids=["com-jogo", "sem-jogo"])
    def test_a_vaga_e_a_do_backend(
        self, monkeypatch: pytest.MonkeyPatch, kernel: KernelDoHidPlaystation, jogo: bool,
    ) -> None:
        """O handle do P1 que caiu e ainda não foi podado não abre a vaga.

        Entre o controle cair e o ``connect()`` podar o handle, o P1 já não está
        entre os conectados (``alvos_conectados``), mas o posto ainda é dele e
        não está vago. Os atalhos seguem a MESMA resposta que para o vpad do P1
        — senão mudariam de mão antes de o posto parar, e também sem jogo, onde
        a espera nem existe e o P2 assume o posto no ``connect()`` seguinte.
        """
        relogio = Relogio()
        bancada = MesaDosAtalhos(monkeypatch, kernel=kernel, relogio=relogio, jogo=jogo)
        for uniq in UNIQS[:3]:
            bancada.mesa.sentar(uniq)
        for _ in range(3):
            bancada.tique()
        handle_do_p1 = bancada.inst._handles["AA:BB:CC:00:00:01"]
        handle_do_p1.connected = False  # caiu; o `connect()` ainda não passou
        assert P1 not in bancada.inst.alvos_conectados().values()
        assert bancada.inst.primary_uniq == P1 and not bancada.vaga()
        assert quem_segura_os_atalhos(bancada.daemon) == P1
        do_posto = frozenset({"ps"})
        assert botoes_dos_atalhos(bancada.daemon, do_posto) is do_posto


# ---------------------------------------------------------------------------
# O PS + L3: o cartão de quem segura
# ---------------------------------------------------------------------------


@pytest.mark.usefixtures("config_isolado")
class TestOPsL3AndaOCartaoDeQuemSegura:
    """Na espera, o PS + L3 do P2 anda o cartão DELE — o do P1 ausente não se mexe.

    O ato é o de verdade: o callback do gesto, o ``escolher_a_mascara`` e o
    ``vestir_a_mascara_do_aparelho`` do ``Daemon``, o co-op recriando o vpad
    de quem trocou (:func:`armar_o_ato_do_daemon`). Só a luz é anotada em vez
    de piscar.
    """

    @staticmethod
    def _preparar(bancada: MesaDosAtalhos, monkeypatch: pytest.MonkeyPatch) -> list[Any]:
        luz: list[Any] = armar_o_ato_do_daemon(bancada, monkeypatch).luz
        return luz

    @pytest.mark.parametrize("transporte", list(TRANSPORTES))
    def test_o_ps_l3_do_p2_na_espera_troca_a_mascara_dele(
        self, monkeypatch: pytest.MonkeyPatch, kernel: KernelDoHidPlaystation, transporte: str,
    ) -> None:
        """A luz diz o que o aparelho fez: o vpad do P2 volta num tique seguinte.

        Conferência de 24/09/2026: com o grab do co-op confirmando no tique
        seguinte, como no leitor de verdade, a prova do aparelho julgava antes
        de o vpad do P2 renascer e piscava os pulsos de falha sobre uma troca
        que pegou.
        """
        bancada = montar_atalhos(monkeypatch, kernel, 3, transporte)
        luz = self._preparar(bancada, monkeypatch)
        _fora_dentro_do_prazo(bancada, P1)
        posto = bancada.daemon._gamepad_device
        vpad_do_p3 = bancada.vpad_de(P3)
        assert em.mascara_vestida(bancada.daemon, P2) == "dualsense"

        _gesto_com_o_laco(bancada, build_next_mask_callback(bancada.daemon))  # type: ignore[arg-type]
        bancada.tique()

        assert em.mascara_vestida(bancada.daemon, P2) == "xbox", "a máscara do P2 não trocou"
        assert em.registro_de_mascaras().mask_for(P1) is None, "o cartão do P1 ausente andou"
        assert bancada.daemon._gamepad_device is posto and posto.vivo, (
            "o vpad parado no lugar do P1 foi recriado com o jogo aberto"
        )
        assert bancada.vpad_de(P3) is vpad_do_p3, "o gesto do P2 recriou o P3"
        assert luz == [("pulsos", len(hotkey._PULSOS_DE_RISCO)), ("piscada", "mascara:xbox")], (
            f"a luz disse {luz}: a troca pegou, e os pulsos de falha a negam"
        )
        assert bancada.dono_do_vpad_do_p1() is None
        assert bancada.a_tela() == {P2: 2, P3: 3}
        bancada.o_jogo_segue_a_tela()

    @pytest.mark.parametrize("transporte", list(TRANSPORTES))
    def test_o_ps_l3_do_p2_anda_o_ciclo_dele_e_nao_o_do_p1(
        self, monkeypatch: pytest.MonkeyPatch, kernel: KernelDoHidPlaystation, transporte: str,
    ) -> None:
        """Três apertos do P2 na espera: o ciclo parte da máscara DELE a cada vez.

        Conferência de 24/09/2026: com o ciclo partindo da máscara do posto (a
        do P1 ausente, que não anda), o segundo aperto pedia de novo o Xbox 360
        que o P2 já vestia, a luz dizia «trocou» e o ciclo dele ficava parado.
        """
        bancada = montar_atalhos(monkeypatch, kernel, 3, transporte)
        luz = self._preparar(bancada, monkeypatch)
        _fora_dentro_do_prazo(bancada, P1)
        posto = bancada.daemon._gamepad_device
        vpad_do_p3 = bancada.vpad_de(P3)

        vestiu = []
        for _ in range(3):
            _gesto_com_o_laco(bancada, build_next_mask_callback(bancada.daemon))  # type: ignore[arg-type]
            bancada.tique(0.0)
            vestiu.append(em.mascara_vestida(bancada.daemon, P2))

        assert vestiu == ["xbox", "nintendo", "dualsense"], f"o ciclo do P2 andou {vestiu}"
        assert [modo for tipo, modo in luz if tipo == "piscada"] == [
            "mascara:xbox", "mascara:nintendo", "mascara:dualsense"
        ]
        assert ("pulsos", len(hotkey._pulsos_de_falha())) not in luz
        assert em.registro_de_mascaras().mask_for(P1) is None, "o cartão do P1 ausente andou"
        assert bancada.daemon._gamepad_device is posto and posto.vivo
        assert bancada.vpad_de(P3) is vpad_do_p3, "os gestos do P2 recriaram o P3"
        bancada.o_jogo_segue_a_tela()

    def test_o_ps_l3_do_p2_que_nao_volta_da_os_pulsos_de_falha(
        self, monkeypatch: pytest.MonkeyPatch, kernel: KernelDoHidPlaystation,
    ) -> None:
        """A prova é o vpad DELE: o do posto de pé não responde pelo do P2.

        O co-op não consegue sentar o P2 de novo (outro leitor exclusivo segura
        o controle dele), o vpad do P2 não volta, e a luz diz que falhou — o do
        posto, parado à espera do P1, continua de pé e não é prova de nada.
        """
        bancada = montar_atalhos(monkeypatch, kernel, 3)
        luz = self._preparar(bancada, monkeypatch)
        monkeypatch.setattr(hotkey, "_ESPERA_DO_VPAD_DO_COOP_S", 0.05)
        _fora_dentro_do_prazo(bancada, P1)
        bancada.mesa.grab_recusado.add(P2)  # type: ignore[attr-defined]

        _gesto_com_o_laco(bancada, build_next_mask_callback(bancada.daemon))  # type: ignore[arg-type]

        assert em.mascara_vestida(bancada.daemon, P2) is None, "premissa: o P2 não voltou"
        assert not any(tipo == "piscada" for tipo, _ in luz), f"a luz disse que trocou: {luz}"
        assert luz[-1] == ("pulsos", len(hotkey._pulsos_de_falha())), luz

    def test_a_espera_cobre_o_prazo_da_calibracao_do_co_op(self) -> None:
        """O vpad que volta mais tarde é o que espera a calibração: a prova espera mais."""
        from hefesto_dualsense4unix.daemon.subsystems import coop

        assert hotkey._ESPERA_DO_VPAD_DO_COOP_S > coop._CALIB_PRAZO_S

    def test_com_todos_na_mesa_o_ps_l3_anda_o_cartao_do_p1(
        self, monkeypatch: pytest.MonkeyPatch, kernel: KernelDoHidPlaystation,
    ) -> None:
        """O contrapeso: fora da espera, quem segura é o P1, e é o cartão dele."""
        bancada = montar_atalhos(monkeypatch, kernel, 3)
        luz = self._preparar(bancada, monkeypatch)
        escolhas: list[str] = []
        real = em.escolher_a_mascara
        monkeypatch.setattr(
            em, "escolher_a_mascara",
            lambda d, uniq, alvo, **kw: escolhas.append(uniq) or real(d, uniq, alvo, **kw),
        )
        _gesto_com_o_laco(bancada, build_next_mask_callback(bancada.daemon))  # type: ignore[arg-type]
        assert escolhas == [P1]
        assert ("piscada", "mascara:xbox") in luz


# ---------------------------------------------------------------------------
# O PS + R3 do P2 troca o modo DE VERDADE
# ---------------------------------------------------------------------------


class _OPostoSoltouNoMeioDoAtoError(AssertionError):
    """O posto que espera o P1 soltou durante o ato — e só isso conta como o xfail."""


@pytest.mark.usefixtures("config_isolado")
class TestOPsR3DoP2TrocaOModo:
    """A prova da sprint até o fim: o ato do PS + R3 do P2 roda na espera.

    Conferência de 24/09/2026. A régua da implementação parava no disparo
    (``on_next_bridge``); o ato — ``Daemon.set_gamepad_emulation`` com
    ``origin="manual"``, o vpad do posto recriado no caminho novo com o MAC do
    P1, o ``sync`` forçado do co-op recriando cada jogador — não rodava na
    espera. Aqui ele roda, pela fábrica real contra o kernel de mentira, com o
    grab do co-op confirmando no tique seguinte.
    """

    @MATRIZ
    def test_o_modo_troca_e_a_espera_segue_de_pe(
        self, monkeypatch: pytest.MonkeyPatch, kernel: KernelDoHidPlaystation,
        quantos: int, transporte: str,
    ) -> None:
        bancada = montar_atalhos(monkeypatch, kernel, quantos, transporte)
        anotado = armar_o_ato_do_daemon(bancada, monkeypatch)
        ficaram = UNIQS[1:quantos]
        via = bancada.mesa.transporte_de(P1)
        _fora_dentro_do_prazo(bancada, P1)
        assert bancada.vaga()
        assert hotkey.ponte_atual(bancada.daemon) == hotkey.PONTE_DUALSENSE
        posto = bancada.daemon._gamepad_device

        with structlog.testing.capture_logs() as registros:
            assert bancada.apertar(P2, "ps", "r3") == ["ponte"]
            _gesto_com_o_laco(bancada, build_next_bridge_callback(bancada.daemon))  # type: ignore[arg-type]
            for _ in range(3):
                bancada.tique(0.0)

        # O modo trocou, e o aparelho concorda: o posto renasceu no caminho novo.
        assert hotkey.ponte_atual(bancada.daemon) == hotkey.PONTE_XBOX
        assert bancada.daemon._gamepad_device is not posto
        assert getattr(bancada.daemon._gamepad_device, "backend", None) == "uinput"
        assert anotado.gravado == [hotkey.PONTE_XBOX], "o modo não foi ao perfil ativo"
        assert anotado.luz == [("pulsos", 4)], (
            f"a luz disse {anotado.luz}: os dois pulsos de risco antes, e nada de falha"
        )
        # E a espera segue de pé: ninguém trocou de número, de lâmpada nem de boneco.
        assert bancada.vaga(), "o PS + R3 do P2 soltou o posto que espera o P1"
        assert bancada.inst.primary_uniq == P1
        assert bancada.a_tela() == {u: n + 2 for n, u in enumerate(ficaram)}
        assert bancada.dono_do_vpad_do_p1() is None, "o P2 passou a dirigir o boneco 1"
        bancada.o_jogo_segue_a_tela()
        assert quem_segura_os_atalhos(bancada.daemon) == P2
        assert not [r for r in registros if r["event"] == "atalhos_voltam_ao_posto"], (
            "o diário disse que os atalhos voltaram ao posto com o P1 ainda fora"
        )

        # O P1 volta e dirige o vpad do posto, que renasceu à espera dele.
        bancada.mesa.sentar(P1, transporte=via)
        bancada.tique()
        bancada.tique()
        assert not bancada.vaga() and bancada.dono_do_vpad_do_p1() == P1
        bancada.o_jogo_segue_a_tela()
        assert bancada.apertar(P1, "ps", "r3") == ["ponte"]
        assert bancada.apertar(P2, "ps", "r3") == []

    @pytest.mark.xfail(
        strict=True,
        raises=_OPostoSoltouNoMeioDoAtoError,
        reason=(
            "o `read_state` do executor que cai no meio da recriação do posto pergunta "
            "a vaga com o `_gamepad_device` vazio, e o co-op responde que não espera "
            "(`CoopManager.o_posto_do_p1_espera` → `should_be_active`): o P2 senta no "
            "posto e dirige o boneco 1 com a lâmpada dizendo 2. Anterior a esta sprint "
            "(o chip do modo na aba Jogar corre o mesmo risco); o dono é o co-op, que "
            "está na O-ASSENTO-GUARDADO-NAO-ANDA-04."
        ),
    )
    @pytest.mark.parametrize("transporte", list(TRANSPORTES))
    def test_a_leitura_do_executor_no_meio_do_ato_nao_solta_o_posto(
        self, monkeypatch: pytest.MonkeyPatch, kernel: KernelDoHidPlaystation, transporte: str,
    ) -> None:
        """O laço lê o estado num fio do executor enquanto o gesto recria o vpad do posto.

        O ato do PS + R3 é síncrono no laço de eventos, mas o ``read_state`` do
        tique anterior pode estar rodando no executor ``hefesto-hid`` ao mesmo
        tempo; na vaga, ele refaz a pergunta da espera a cada tique
        (``_ds_depois_da_vaga``). A régua põe essa leitura no instante em que o
        vpad do posto já parou e o novo ainda não nasceu.
        """
        bancada = montar_atalhos(monkeypatch, kernel, 3, transporte)
        armar_o_ato_do_daemon(bancada, monkeypatch)
        _fora_dentro_do_prazo(bancada, P1)
        nascer = bancada._nascer_vpad
        no_meio: list[Any] = []

        def _nascer_com_a_leitura_no_meio(flavor: Any, **kw: Any) -> Any:
            if kw.get("identity") == P1 and not no_meio:
                no_meio.append(bancada.daemon._gamepad_device)
                bancada.inst.read_state()  # o tique do executor, no meio do ato
            return nascer(flavor, **kw)

        monkeypatch.setattr(
            "hefesto_dualsense4unix.integrations.virtual_pad.make_virtual_pad",
            _nascer_com_a_leitura_no_meio,
        )
        _gesto_com_o_laco(bancada, build_next_bridge_callback(bancada.daemon))  # type: ignore[arg-type]
        assert no_meio == [None], "premissa: a leitura caiu no meio da recriação do posto"
        for _ in range(3):
            bancada.tique(0.0)
        if not bancada.vaga() or bancada.dono_do_vpad_do_p1() is not None:
            raise _OPostoSoltouNoMeioDoAtoError(
                f"o posto soltou: dono do boneco 1 = {bancada.dono_do_vpad_do_p1()}, "
                f"o jogo {bancada.o_jogo_ve()}, a tela {bancada.a_tela()}"
            )


# ---------------------------------------------------------------------------
# O laço de produção
# ---------------------------------------------------------------------------


class _CoopDaEspera:
    """O co-op como o laço o vê na espera: o P2 e o P3 na mesa, cada um apertando um botão.

    Dublê SÓ do que o laço chama por tique e do que os atalhos perguntam; o
    comportamento do co-op de verdade é o da bancada honesta, lá em cima.
    """

    def __init__(self) -> None:
        self._players: dict[str, Any] = {}
        # Botões que não formam atalho nenhum: o laço de verdade despacharia o
        # ato de verdade, e o do PS + R3 recria vpad (um nó uinput real).
        self._vivos = {
            P2: SimpleNamespace(buttons_pressed=frozenset({"triangle"})),
            P3: SimpleNamespace(buttons_pressed=frozenset({"square"})),
        }

    def sync(self, *, force: bool = False) -> None:
        return None

    def forward_all(self) -> None:
        return None

    def stop_all(self) -> None:
        return None

    def should_be_active(self) -> bool:
        return True

    def player_count(self) -> int:
        return 3

    def live_snapshots(self) -> dict[str, Any]:
        return dict(self._vivos)

    def numeros_de_jogador(self) -> dict[str, int]:
        return {P1: 1, P2: 2, P3: 3}


def _estados(n: int) -> list[ControllerState]:
    return [
        ControllerState(battery_pct=80, l2_raw=0, r2_raw=0, connected=True, transport="usb")
        for _ in range(n)
    ]


class TestOLacoDeProducao:
    """O `_poll_loop` de verdade entrega aos atalhos os botões de quem segura.

    A bancada honesta chama o dono direto; esta é a régua de que o LAÇO chama
    o dono, com o ``Daemon.run`` de verdade e o ``FakeController`` — nenhum
    aparelho, nenhum nó.
    """

    @staticmethod
    async def _rodar(monkeypatch: pytest.MonkeyPatch, *, vaga: bool) -> list[frozenset[str]]:
        monkeypatch.setattr("hefesto_dualsense4unix.daemon.lifecycle.INPUT_GRACE_SEC", 0.0)
        observados: list[frozenset[str]] = []
        original = HotkeyManager.observe

        def _espiao(self: Any, pressed: Any, *, now: Any = None) -> Any:
            observados.append(frozenset(pressed))
            return original(self, pressed, now=now)

        monkeypatch.setattr(HotkeyManager, "observe", _espiao)
        fc = FakeController(transport="usb", states=_estados(400))
        leitor = MagicMock()
        leitor.is_available.return_value = not vaga  # na vaga o leitor do P1 não tem nó
        leitor.snapshot.return_value = SimpleNamespace(buttons_pressed=["cross"])
        fc._evdev = leitor
        fc._posto_vago_de = "AA:BB:CC:00:00:01" if vaga else None  # type: ignore[attr-defined]
        fc.primary_uniq = P1  # type: ignore[attr-defined]
        daemon = Daemon(
            controller=fc,
            config=DaemonConfig(
                poll_hz=200,
                auto_reconnect=False,
                ipc_enabled=False,
                udp_enabled=False,
                autoswitch_enabled=False,
                mouse_emulation_enabled=False,
                keyboard_emulation_enabled=False,
            ),
        )
        daemon._coop_manager = _CoopDaEspera()
        tarefa = asyncio.create_task(daemon.run())
        await asyncio.sleep(0.15)
        daemon.stop()
        await tarefa
        return observados

    @pytest.mark.asyncio
    async def test_na_vaga_o_laco_entrega_os_botoes_do_p2(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        observados = await self._rodar(monkeypatch, vaga=True)
        assert observados, "o laço não chamou os atalhos"
        assert set(observados) == {frozenset({"triangle"})}, (
            f"o laço entregou aos atalhos {sorted(set(observados), key=sorted)} — "
            "os do posto vago, e não os do P2"
        )

    @pytest.mark.asyncio
    async def test_fora_da_vaga_o_laco_entrega_os_do_posto(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        observados = await self._rodar(monkeypatch, vaga=False)
        assert observados and set(observados) == {frozenset({"cross"})}
