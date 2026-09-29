"""NO-MODO-XBOX-TUDO-FUNCIONA-01, parte 4: no modo Xbox, a háptica fina.

A ordem dela de 27/09: *«tá errado se tiver no modo xbox é pra literalmente
tudo isso funcionar»*, e «tudo isso» inclui a háptica. O item 2 da sprint dá
duas saídas: o áudio do jogo, ou o rumble do Xbox convertido na háptica fina.
<!-- noqa-acento: citação literal dela -->

A MEDIDA ANTES DA CURA (diários e ``pactl`` da noite de 27/09, as sessões com
``caminho=xbox``): os jogos que só falam XInput (Future Knight no L4 e no G3,
DON'T SCREAM no L5, o G6) abriram ZERO fluxos nos quatro endpoints, no cabo e
no rádio. Só o PRAGMATA (G1) abriu, porque ele acha a háptica pelo registro
KS e não pelo pad. No modo Xbox o áudio do jogo não chega: o rumble do pad
vira háptica no endpoint do lugar de quem o recebe, e o laço do cabo e a ponte
do rádio o levam como levam o do jogo.

O mundo do alto-falante é o da régua da A-HAPTICA-CHEGA (o servidor de som
com memória, o ``/sys`` no ``tmp_path``), com o que aquele servidor não lista:
o cliente de cada fluxo na listagem longa e o fluxo dos nossos tocadores. Os
``uniq`` são da faixa sintética.

LIMITE DECLARADO: é fiação e conta. Se a vibração convertida se sente na mão,
no cabo e no rádio, é a prova no aparelho, e é dela.
"""

from __future__ import annotations

import array
import asyncio
import contextlib
import math
import os
import threading
import time
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any, ClassVar

import pytest

from hefesto_dualsense4unix.daemon.subsystems import gamepad as gp
from hefesto_dualsense4unix.daemon.subsystems.coop import CoopManager
from hefesto_dualsense4unix.integrations import alto_falante_bt as af
from hefesto_dualsense4unix.integrations import endpoint_de_haptica as eh
from hefesto_dualsense4unix.integrations.uhid_gamepad import UhidDualSense
from hefesto_dualsense4unix.integrations.uinput_gamepad import UinputGamepad
from tests.unit.test_a_haptica_chega_a_quem_entra_depois import (  # noqa: F401
    _P1,
    _P2,
    _P3,
    _P4,
    _Controle,
    _Mesa,
    _no_cabo,
    _PonteDeMentira,
    _Servidor,
    mesa,
)

_QUATRO = (_P1, _P2, _P3, _P4)
_APARELHOS = (("3-8", 28), ("3-7", 29), ("3-6", 30), ("3-5", 31))
_ABERTO = ["100%", "100%", "100%", "100%"]
_FECHADO = ["100%", "100%", "0%", "0%"]


# ---------------------------------------------------------------------------
# O mundo: os fluxos com dono, e o tocador de mentira
# ---------------------------------------------------------------------------


class _Fluxos:
    """O servidor da A-HAPTICA-CHEGA, com o cliente de cada fluxo e os nossos tocadores.

    Tudo o que não é listagem de fluxo vai ao servidor de lá. Os fluxos saem
    como o ``pipewire-pulse`` os imprime: na curta, o cliente na coluna 3; na
    longa, a linha ``Client:`` e o ``node.name`` nas propriedades.
    """

    def __init__(self, servidor: _Servidor) -> None:
        self.servidor = servidor
        #: lugar -> o cliente do nosso tocador que toca no endpoint dele
        self.tocando: dict[int, str] = {}

    def _todos(self) -> list[tuple[str, int, str, dict[str, str]]]:
        s = self.servidor
        todos = [
            (f"9{i}", i, "42", {"application.name": "jogo"})
            for i, sk in s.sinks.items() if sk["nome"] in s.jogo_em
        ]
        todos += [(str(i), f["sink"], "77", {"node.name": f["nome"]}) for i, f in s.fluxos.items()]
        for lugar, cliente in sorted(self.tocando.items()):
            rotulo = eh.rotulo_do_tocador(lugar)
            todos.append((
                f"8{lugar}", s.indice(eh.nome_do_endpoint(lugar)), cliente,
                {"node.name": rotulo, "media.name": rotulo},
            ))
        return todos

    def __call__(self, argv: list[str]) -> str | None:
        a = list(argv)
        if a[:4] in (
            ["pactl", "list", "short", "sink-inputs"], ["pactl", "list", "sink-inputs", "short"]
        ):
            return "\n".join(
                f"{ix}\t{sink}\t{cli}\tPipeWire\tfloat32le 4ch 48000Hz"
                for ix, sink, cli, _p in self._todos()
            )
        if a == ["pactl", "list", "sink-inputs"]:
            return "\n\n".join(
                f"Sink Input #{ix}\n\tDriver: PipeWire\n\tOwner Module: n/a\n\tClient: {cli}\n"
                f"\tSink: {sink}\n\tProperties:\n"
                + "\n".join(f'\t\t{k} = "{v}"' for k, v in props.items())
                for ix, sink, cli, props in self._todos()
            )
        return self.servidor(argv)


class _Tocador:
    """O tocador de mentira, que publica o que o real publica.

    Fica de pé com o primeiro nível não nulo, e aí o fluxo NOSSO aparece no
    endpoint do lugar (com cliente próprio); com zero cala e segue de pé, até
    a folga vencer (:meth:`sair`). Avisa ``ao_mudar`` nas duas pontas, como o
    real.
    """

    criados: ClassVar[dict[int, _Tocador]] = {}
    fluxos: ClassVar[_Fluxos | None] = None
    eventos: ClassVar[list[str]] = []

    def __init__(self, lugar: int, *, ao_mudar: Any = None, **_k: Any) -> None:
        self.lugar = lugar
        self.ao_mudar = ao_mudar
        self._nivel = (0, 0)
        self._sink = ""
        self._dono = ""
        self._vivo = False
        self.parou = False
        self.pedidos: list[tuple[int, int, str, str]] = []
        _Tocador.criados[lugar] = self

    @property
    def nivel(self) -> tuple[int, int]:
        return self._nivel

    @property
    def dono(self) -> str:
        return self._dono

    @property
    def sink(self) -> str:
        return self._sink

    @property
    def vivo(self) -> bool:
        return self._vivo

    def levar(self, fraco: int, forte: int, *, sink: str, dono: str) -> None:
        self.pedidos.append((fraco, forte, sink, dono))
        self._nivel, self._sink, self._dono = (fraco, forte), sink, dono
        if any(self._nivel) and not self._vivo and not self.parou:
            self._vivo = True
            if self.fluxos is not None:
                self.fluxos.tocando[self.lugar] = str(60 + self.lugar)
            if self.ao_mudar is not None:
                self.ao_mudar()

    def calar(self) -> None:
        self._nivel = (0, 0)

    def sair(self) -> None:
        if not self._vivo:
            return
        self._vivo = False
        if self.fluxos is not None:
            self.fluxos.tocando.pop(self.lugar, None)
        if self.ao_mudar is not None:
            self.ao_mudar()

    def parar(self) -> None:
        _Tocador.eventos.append(f"tocador-{self.lugar}-parou")
        self.parou = True
        self.sair()


class _Backend:
    """O backend de mentira: os motores do HID de cada controle, por endereço."""

    def __init__(self, uniqs: tuple[str, ...]) -> None:
        self.uniqs = set(uniqs)
        self.primary_uniq: str | None = uniqs[0] if uniqs else None
        self.escritas: list[tuple[str | None, int, int]] = []

    def set_rumble_for(self, uniq: str, weak: int, strong: int) -> bool:
        if uniq not in self.uniqs:
            return False
        self.escritas.append((uniq, weak, strong))
        return True

    def set_rumble(self, weak: int, strong: int) -> None:
        self.escritas.append((None, weak, strong))

    def do(self, uniq: str) -> list[tuple[int, int]]:
        return [(w, s) for u, w, s in self.escritas if u == uniq]


@dataclass
class _Mundo:
    mesa: _Mesa
    fluxos: _Fluxos
    daemon: Any
    backend: _Backend

    @property
    def sub(self) -> Any:
        return self.mesa.sub

    def tocador(self, lugar: int) -> _Tocador:
        return _Tocador.criados[lugar]

    def rumble(self, uniq: str, fraco: int, forte: int, *, vpad: Any = None) -> Any:
        """O que o ``rumble_sink`` do pad de ``uniq`` faz com o pedido do jogo."""
        pad = vpad if vpad is not None else UinputGamepad.for_flavor("xbox")
        return gp.apply_game_rumble(self.daemon, fraco, forte, target_uniq=uniq, vpad=pad)


def _daemon(sub: Any, backend: _Backend, *, politica: str = "balanceado") -> Any:
    """O daemon de mentira do rumble do jogo (o molde de ``test_vpad_ff_passthrough``)."""
    estado = SimpleNamespace(battery_pct=80)
    return SimpleNamespace(
        config=SimpleNamespace(
            rumble_active=None, rumble_policy=politica, rumble_policy_custom_mult=0.5
        ),
        controller=backend,
        store=SimpleNamespace(
            snapshot=lambda: SimpleNamespace(controller=estado), active_profile=None
        ),
        _last_auto_mult=0.7,
        _last_auto_change_at=0.0,
        _alto_falante_subsystem=sub,
    )


@pytest.fixture
def mundo(mesa: _Mesa, monkeypatch: pytest.MonkeyPatch) -> _Mundo:  # noqa: F811
    fluxos = _Fluxos(mesa.servidor)
    monkeypatch.setattr(af, "_rodar", fluxos)
    _Tocador.criados = {}
    _Tocador.fluxos = fluxos
    _Tocador.eventos = []
    monkeypatch.setattr(eh, "TocadorDoRumble", _Tocador)
    backend = _Backend(_QUATRO)
    return _Mundo(mesa=mesa, fluxos=fluxos, daemon=_daemon(mesa.sub, backend), backend=backend)


def _no_cabo_os_quatro(m: _Mundo) -> list[_Controle]:
    return [
        _no_cabo(m.mesa, uniq, lugar, *_APARELHOS[lugar - 1])
        for lugar, uniq in enumerate(_QUATRO, 1)
    ]


def _no_radio_os_quatro(m: _Mundo) -> list[_Controle]:
    for lugar, uniq in enumerate(_QUATRO, 1):
        m.mesa.assentos[uniq] = lugar
    return [_Controle(u, "bt", f"/dev/hidraw{n}") for n, u in enumerate(_QUATRO, 1)]


def _motores(m: _Mundo, lugar: int) -> list[str]:
    return m.mesa.servidor.volumes[m.mesa.servidor.fluxo_do_laco(lugar)]


# ---------------------------------------------------------------------------
# O bloco: a frente muda, cada motor no seu atuador
# ---------------------------------------------------------------------------


def _canais(bloco: bytes) -> list[array.array[float]]:
    quadros = array.array("f")
    quadros.frombytes(bloco)
    return [quadros[c::4] for c in range(4)]


def _potencia(amostras: Any, frequencia: float) -> float:
    n = len(amostras)
    re = sum(x * math.cos(2 * math.pi * frequencia * i / 48000) for i, x in enumerate(amostras))
    im = sum(x * math.sin(2 * math.pi * frequencia * i / 48000) for i, x in enumerate(amostras))
    return math.hypot(re, im) / n


def test_a_frente_fica_muda_e_cada_motor_no_seu_atuador() -> None:
    """O forte no traseiro esquerdo a 60 Hz, o fraco no direito a 160 Hz, e a frente em zero.

    A frente é o alto-falante do controle: o rumble tocado ali sairia como
    zumbido. O ``strong`` é o ``motor_left`` do report (o atuador da esquerda).

    MORDIDA: em ``bloco_da_haptica``, troque os dois traseiros
    (``quadros[2::4]`` com o seno do fraco) — o forte vai à direita.
    """
    ciclo = b"".join(eh.bloco_da_haptica(100, 200, fase=f) for f in range(0, 2400, 480))
    frente_e, frente_d, esquerdo, direito = _canais(ciclo)
    assert max(map(abs, frente_e)) == 0.0 and max(map(abs, frente_d)) == 0.0
    assert max(esquerdo) == pytest.approx(200 / 255, abs=1e-3)
    assert max(direito) == pytest.approx(100 / 255, abs=1e-3)
    assert _potencia(esquerdo, 60) > 10 * _potencia(esquerdo, 160)
    assert _potencia(direito, 160) > 10 * _potencia(direito, 60)


def test_o_zero_e_silencio_e_o_nivel_novo_nao_estala() -> None:
    """Zero é silêncio; o nível que muda anda em rampa, e o ciclo emenda sem salto.

    MORDIDA: em ``bloco_da_haptica``, ignore o ``antes`` (``a0, b0 = a1, b1``)
    — o primeiro quadro de um rumble que liga salta de zero ao pico.
    """
    assert eh.bloco_da_haptica(0, 0) == bytes(eh.QUADROS_POR_BLOCO * 16)
    liga = _canais(eh.bloco_da_haptica(255, 255, fase=120, antes=(0, 0)))
    assert abs(liga[2][0]) < 0.01 and abs(liga[3][0]) < 0.01, "o rumble que liga estala"
    seguidos = b"".join(eh.bloco_da_haptica(255, 255, fase=f) for f in range(0, 4800, 480))
    esquerdo = _canais(seguidos)[2]
    passo = 2 * math.pi * 60 / 48000
    assert max(abs(esquerdo[i + 1] - esquerdo[i]) for i in range(len(esquerdo) - 1)) <= passo * 1.01


# ---------------------------------------------------------------------------
# O comando: pelo serial, e nunca para a saída padrão
# ---------------------------------------------------------------------------

_ENDPOINT_1 = eh.nome_do_endpoint(1)


def _servidor_de(nome_do_servidor: str) -> Any:
    def _rodar(argv: list[str]) -> str | None:
        if argv[:2] == ["pactl", "info"]:
            return f"Server Name: {nome_do_servidor}\n"
        if argv[:4] == ["pactl", "list", "sinks", "short"]:
            return f"207\t{_ENDPOINT_1}\tPipeWire\tfloat32le 4ch 48000Hz\tIDLE\n"
        return ""

    return _rodar


def test_o_tocador_mira_pelo_serial_e_nunca_recua_para_a_saida_padrao(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``pw-cat`` pelo ``object.serial``, sem recuo, sem alvo nem volume guardados.

    Um fluxo cujo alvo não resolve toca na saída PADRÃO — a TV dela. O nome do
    endpoint não pode ir no comando: é pelo nome que o recuo acontece.

    MORDIDA: em ``argv_do_tocador``, mire pelo nome (``--target={sink}``) — ou
    tire o ``node.dont-fallback=true``.
    """
    monkeypatch.setattr(eh.shutil, "which", lambda b: f"/usr/bin/{b}")
    monkeypatch.setattr(af, "_rodar", _servidor_de("PulseAudio (on PipeWire 1.6.8)"))
    argv = eh.argv_do_tocador(_ENDPOINT_1, eh.rotulo_do_tocador(1))
    assert argv[:3] == ["pw-cat", "--playback", "--raw"]
    assert "--target=207" in argv
    assert not any(_ENDPOINT_1 in a for a in argv), "o tocador mira pelo nome"
    for pedaco in ("--rate=48000", "--channels=4", "--format=f32", "--channel-map=FL,FR,RL,RR"):
        assert pedaco in argv
    assert any(a.startswith("--latency=") for a in argv), "sem latência, o rumble chega atrasado"
    propriedades = argv[argv.index("-P") + 1].split()
    for pedaco in (
        "node.dont-fallback=true", "node.dont-reconnect=true",
        "state.restore-target=false", "state.restore-props=false",
        f"node.name={eh.rotulo_do_tocador(1)}",
    ):
        assert pedaco in propriedades, pedaco


def test_sem_o_pipewire_o_pacat_acerta_pelo_nome(monkeypatch: pytest.MonkeyPatch) -> None:
    """Sem o serial do PipeWire, o ``pacat`` pelo nome, com as mesmas proibições.

    MORDIDA: em ``argv_do_tocador``, dê o ``pw-cat`` também sem serial
    (``--target={sink}``) — o nome vai ao PipeWire, que recua.
    """
    monkeypatch.setattr(eh.shutil, "which", lambda b: f"/usr/bin/{b}")
    monkeypatch.setattr(af, "_rodar", _servidor_de("PulseAudio"))
    argv = eh.argv_do_tocador(_ENDPOINT_1, eh.rotulo_do_tocador(1))
    assert argv[0] == "pacat"
    assert f"--device={_ENDPOINT_1}" in argv
    assert "--property=node.dont-fallback=true" in argv
    assert any(a.startswith("--latency-msec=") for a in argv)
    monkeypatch.setattr(eh.shutil, "which", lambda _b: None)
    assert eh.argv_do_tocador(_ENDPOINT_1, eh.rotulo_do_tocador(1)) == []


def test_o_fluxo_nosso_se_separa_do_fluxo_do_jogo() -> None:
    """Pela listagem longa: o nosso pelo nome, o do jogo pelo resto, o do módulo fora.

    MORDIDA: em ``fluxos_nos_lugares``, conte o fluxo nosso como de outro
    (tire o ``if nosso:``) — o endpoint 2 vira «o jogo toca aqui».
    """
    nomes = [eh.nome_do_endpoint(n) for n in (1, 2, 3)]
    sinks = "\n".join(f"{200 + n}\t{nome}\tPipeWire\tx\tIDLE" for n, nome in enumerate(nomes, 1))
    longa = (
        'Sink Input #1\n\tClient: 118\n\tSink: 201\n\tProperties:\n\t\tapplication.name = "J"\n\n'
        "Sink Input #2\n\tClient: 130\n\tSink: 202\n\tProperties:\n"
        f'\t\tnode.name = "{eh.rotulo_do_tocador(2)}"\n\n'
        'Sink Input #3\n\tClient: n/a\n\tSink: 203\n\tProperties:\n\t\tnode.name = "laço"\n'
    )

    def _rodar(argv: list[str]) -> str | None:
        return sinks if "short" in argv else longa

    assert eh.fluxos_nos_lugares(nomes, _rodar) == (frozenset({"130"}), frozenset({nomes[0]}))
    assert eh.fluxos_nos_lugares(nomes, lambda _a: None) is None


# ---------------------------------------------------------------------------
# O tocador de verdade, com um processo de mentira
# ---------------------------------------------------------------------------


class _Processo:
    """O ``pw-cat`` de mentira: um cano de verdade, lido no ritmo do áudio (ou não lido)."""

    criados: ClassVar[list[_Processo]] = []

    def __init__(self, argv: list[str], *, le: bool = True, **_k: Any) -> None:
        self.args = argv
        leitura, escrita = os.pipe()
        self.stdin = os.fdopen(escrita, "wb", buffering=0)
        self._leitura = leitura
        self._rc: int | None = None
        self.lido = bytearray()
        _Processo.criados.append(self)
        if le:
            threading.Thread(target=self._ler, daemon=True).start()

    def _ler(self) -> None:
        while self._rc is None:
            try:
                pedaco = os.read(self._leitura, 7680)
            except OSError:
                return
            if not pedaco:
                return
            self.lido += pedaco
            time.sleep(0.005)

    def poll(self) -> int | None:
        return self._rc

    def kill(self) -> None:
        self._rc = -9
        with contextlib.suppress(OSError):
            os.close(self._leitura)

    def wait(self, timeout: float | None = None) -> int | None:
        return self._rc


def _esperar(condicao: Any, prazo: float = 3.0) -> bool:
    fim = time.monotonic() + prazo
    while time.monotonic() < fim:
        if condicao():
            return True
        time.sleep(0.01)
    return bool(condicao())


@pytest.fixture
def processos() -> Any:
    _Processo.criados = []
    yield _Processo
    for p in _Processo.criados:
        p.kill()


def _tocador(**kw: Any) -> eh.TocadorDoRumble:
    base: dict[str, Any] = {
        "argv_de": lambda sink, rotulo: ["pw-cat", f"--target={sink}", rotulo],
        "lancar": _Processo,
        "conferir": lambda _r: _ENDPOINT_1,
        "folga_s": 0.15,
    }
    base.update(kw)
    return eh.TocadorDoRumble(1, **base)


def test_o_tocador_sobe_com_o_rumble_toca_o_nivel_e_sai_no_silencio(processos: Any) -> None:
    """Sobe no primeiro nível, toca o forte à esquerda, e sai depois da folga de silêncio.

    MORDIDA: em ``TocadorDoRumble._escrever_enquanto_toca``, nunca saia pelo
    silêncio (tire o ``return "silencio"``) — o fluxo fica de pé no endpoint,
    e a ponte do rádio nunca volta ao alto-falante.
    """
    avisos: list[str] = []
    tocador = _tocador(ao_mudar=lambda: avisos.append("mudou"))
    tocador.levar(0, 255, sink=_ENDPOINT_1, dono=_P1)
    assert _esperar(lambda: tocador.vivo), "o tocador não subiu"
    assert _esperar(lambda: len(processos.criados[0].lido) >= 7680 * 3)
    # O aviso sai DEPOIS de o tocador se dizer de pé (e, na saída, depois de
    # se dizer fora): quem o lê espera por ele, e não pelo ``vivo``.
    assert _esperar(lambda: avisos == ["mudou"]), avisos
    _fl, _fr, esquerdo, direito = _canais(bytes(processos.criados[0].lido[: 7680 * 3]))
    assert max(esquerdo) > 0.9 and max(map(abs, direito)) == 0.0
    tocador.calar()
    assert _esperar(lambda: not tocador.vivo), "o silêncio não tirou o tocador do endpoint"
    assert _esperar(lambda: processos.criados[0].poll() is not None), "o processo ficou de pé"
    assert _esperar(lambda: avisos == ["mudou", "mudou"]), avisos
    tocador.levar(10, 10, sink=_ENDPOINT_1, dono=_P1)
    assert _esperar(lambda: tocador.vivo) and len(processos.criados) == 2
    tocador.parar()
    assert not tocador.vivo


def test_o_tocador_que_nao_le_nao_prende_o_fio(
    processos: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """O fluxo sem destino não consome nada: a escrita desiste e o tocador é recusado.

    MORDIDA: em ``TocadorDoRumble._escrever``, espere sem prazo (tire o
    ``return False`` do ``PRAZO_DA_ESCRITA_S``) — o fio fica preso no cano, e
    um novo rumble não sai dele.
    """
    monkeypatch.setattr(eh, "PRAZO_DA_ESCRITA_S", 0.2)
    tocador = _tocador(lancar=lambda argv, **kw: _Processo(argv, le=False, **kw))
    tocador.levar(0, 255, sink=_ENDPOINT_1, dono=_P1)
    assert _esperar(lambda: processos.criados and processos.criados[0].poll() is not None)
    assert not tocador.vivo
    tocador.levar(0, 200, sink=_ENDPOINT_1, dono=_P1)
    time.sleep(0.3)
    assert len(processos.criados) == 1, "o tocador que não tocou foi relançado a cada rumble"
    tocador.parar()


def test_o_tocador_ligado_a_outro_no_morre(
    processos: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ligado a outro nó que não o endpoint, o tocador morre e não volta.

    MORDIDA: em ``TocadorDoRumble._conferir_o_destino``, aceite qualquer destino
    (``if destino == sink or True``) — o zumbido segue na saída dela.
    """
    monkeypatch.setattr(eh, "ESPERAS_DA_CONFERENCIA_S", (0.02,))
    tocador = _tocador(conferir=lambda _r: "alsa_output.pci-0000_0a_00.1.hdmi-stereo")
    tocador.levar(0, 255, sink=_ENDPOINT_1, dono=_P1)
    assert _esperar(lambda: processos.criados and processos.criados[0].poll() is not None)
    assert _esperar(lambda: not tocador.vivo)
    tocador.levar(0, 200, sink=_ENDPOINT_1, dono=_P1)
    time.sleep(0.2)
    assert len(processos.criados) == 1
    tocador.parar()


def test_sem_tocador_na_maquina_o_hid_segue_sozinho(processos: Any) -> None:
    """Sem ``pw-cat`` nem ``pacat`` não há processo, e o tocador nunca fica de pé.

    MORDIDA: em ``TocadorDoRumble._tocar``, lance mesmo sem ``argv`` — o
    processo vazio morre e o tocador se diz de pé por um instante.
    """
    tocador = _tocador(argv_de=lambda _s, _r: [])
    tocador.levar(0, 255, sink=_ENDPOINT_1, dono=_P1)
    time.sleep(0.2)
    assert processos.criados == [] and not tocador.vivo
    tocador.parar()


# ---------------------------------------------------------------------------
# O rumble do pad uinput leva a háptica ao lugar, P1 a P4, cabo e rádio
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("lugar", [1, 2, 3, 4])
def test_no_cabo_o_rumble_de_cada_lugar_abre_so_os_motores_dele(mundo: _Mundo, lugar: int) -> None:
    """Quatro no cabo, ninguém mexeu: o rumble do jogador N abre os motores do laço N.

    Antes do caminho, o HID leva o par; com o portão aberto, a volta reaplica
    e os motores do HID vão a zero, porque o bit do rumble cala a háptica.

    MORDIDA: em ``_casar_o_cabo``, tire o ``self._recebe_o_rumble(uniq)`` do
    ``_abre`` — o laço N fica fechado e o HID nunca solta.
    """
    controles = _no_cabo_os_quatro(mundo)
    mundo.mesa.volta(*controles)
    uniq = _QUATRO[lugar - 1]
    assert mundo.rumble(uniq, 100, 200) == (100, 200)
    assert mundo.backend.do(uniq) == [(100, 200)], "antes do caminho, o HID leva"
    tocador = mundo.tocador(lugar)
    assert (tocador.nivel, tocador.sink, tocador.dono) == (
        (100, 200), eh.nome_do_endpoint(lugar), uniq
    )
    mundo.mesa.volta(*controles)
    for n in (1, 2, 3, 4):
        esperado = _ABERTO if n == lugar else _FECHADO
        assert _motores(mundo, n) == esperado, f"lugar {n}: {_motores(mundo, n)}"
    assert mundo.backend.do(uniq) == [(100, 200), (0, 0)], "o HID não soltou o rumble"
    mundo.rumble(uniq, 150, 50)
    assert mundo.backend.do(uniq)[-1] == (0, 0)
    assert tocador.nivel == (150, 50)
    assert set(_Tocador.criados) == {lugar}


@pytest.mark.parametrize("lugar", [1, 2, 3, 4])
def test_no_radio_o_rumble_sobe_a_ponte_da_haptica_de_quem_recebe(
    mundo: _Mundo, lugar: int
) -> None:
    """Quatro no rádio: o rumble do jogador N sobe a ponte dele em háptica, lendo o lugar N.

    MORDIDA: no laço das pontes de ``_casar_as_pontes``, tire o
    ``pelo_rumble`` do modo — a ponte não sobe, e o HID nunca solta.
    """
    controles = _no_radio_os_quatro(mundo)
    mundo.mesa.volta(*controles)
    uniq = _QUATRO[lugar - 1]
    mundo.rumble(uniq, 0, 180)
    mundo.mesa.lidos.clear()
    mundo.mesa.volta(*controles)
    hapticas = [no for no, papel in mundo.mesa.lidos if papel == "haptica"]
    assert hapticas == [eh.nome_do_endpoint(lugar)], hapticas
    (ponte,) = [p for p in _PonteDeMentira.criadas if p.uniq == uniq]
    assert ponte.arranjo is af.ARRANJO_HAPTICA_032
    assert mundo.backend.do(uniq) == [(0, 180), (0, 0)]
    assert [p.uniq for p in _PonteDeMentira.criadas] == [uniq], "outro controle ganhou ponte"


def test_pelo_radio_o_alto_falante_tocando_fica_com_o_radio(mundo: _Mundo) -> None:
    """Som e vibração pelo rádio são exclusivos: o alto-falante tocando fica, e o HID leva.

    MORDIDA: no laço das pontes, tire a pergunta ao alto-falante antes do
    ``pelo_rumble`` — a ponte troca o som pela háptica do rumble.
    """
    controles = _no_radio_os_quatro(mundo)
    mundo.mesa.volta(*controles)
    mundo.rumble(_P1, 0, 180)
    mundo.mesa.volta(*controles)
    assert mundo.backend.do(_P1)[-1] == (0, 0)
    # Ela põe som no alto-falante do P1 com o rumble tocando.
    som = af.nome_do_sink(_P1)
    mundo.mesa.servidor.placa(som, "/devices/virtual/som")
    mundo.mesa.servidor.jogo_em.add(som)
    mundo.mesa.volta(*controles)
    ponte = mundo.sub._pontes[_P1]
    assert ponte.arranjo is None, "a háptica do rumble tirou o alto-falante dela"
    assert mundo.backend.do(_P1)[-1] == (0, 180), "o HID não voltou a levar"
    assert mundo.tocador(1).nivel == (0, 0)
    assert mundo.rumble(_P1, 0, 90) == (0, 90)
    assert mundo.backend.do(_P1)[-1] == (0, 90)


def test_onde_o_jogo_toca_a_haptica_e_a_dele(mundo: _Mundo) -> None:
    """O jogo que toca no endpoint do lugar é a háptica dali: o rumble segue pelo HID.

    É o «ou» da sprint: o áudio do jogo, ou o rumble convertido — nunca os
    dois somados no mesmo atuador.

    MORDIDA: em ``_quer_a_haptica_fina``, tire o ``lugar in
    self._lugares_com_jogo`` — o tocador segue somando no lugar do jogo.
    """
    controles = _no_cabo_os_quatro(mundo)
    mundo.mesa.servidor.jogo_em.add(eh.nome_do_endpoint(1))
    mundo.mesa.volta(*controles)
    mundo.rumble(_P1, 100, 200)
    mundo.mesa.volta(*controles)
    assert 1 in mundo.sub._lugares_com_jogo
    assert mundo.tocador(1).nivel == (0, 0), "o rumble convertido soma na háptica do jogo"
    assert mundo.backend.do(_P1)[-1] == (100, 200)
    assert _motores(mundo, 1) == _FECHADO


def test_o_nosso_tocador_nao_abre_a_partida(mundo: _Mundo) -> None:
    """A partida é o dono do fluxo de JOGO: o tocador do rumble não é jogo.

    MORDIDA: em ``_donos_dos_fluxos``, não tire os ``_clientes_do_rumble`` — o
    tocador abre uma partida a cada rumble e zera quem já jogava.
    """
    controles = _no_cabo_os_quatro(mundo)
    mundo.mesa.volta(*controles)
    mundo.rumble(_P1, 100, 200)
    mundo.mesa.volta(*controles)
    assert mundo.fluxos.tocando == {1: "61"}
    assert mundo.sub._donos_dos_fluxos() == frozenset()
    mundo.mesa.servidor.jogo_em.add(eh.nome_do_endpoint(3))
    mundo.mesa.volta(*controles)
    assert mundo.sub._donos_dos_fluxos() == frozenset({"42"})


def test_o_caminho_que_cai_devolve_o_rumble_ao_hid(mundo: _Mundo) -> None:
    """O tocador saiu com o rumble ainda pedido: a volta reaplica, e o HID volta a levar.

    MORDIDA: tire o ``self._conferir_o_rumble()`` do fim de
    ``_casar_as_pontes`` — o motor fica mudo até o jogo mudar o pedido.
    """
    controles = _no_cabo_os_quatro(mundo)
    mundo.mesa.volta(*controles)
    mundo.rumble(_P2, 30, 60)
    mundo.mesa.volta(*controles)
    assert mundo.backend.do(_P2) == [(30, 60), (0, 0)]
    mundo.tocador(2).sair()
    mundo.mesa.volta(*controles)
    assert mundo.backend.do(_P2)[-1] == (30, 60), "o caminho caiu e o motor ficou mudo"
    assert _motores(mundo, 2) == _FECHADO
    mundo.mesa.volta(*controles)
    assert len(mundo.backend.do(_P2)) == 4, "a volta sem mudança reaplicou à toa"


def test_o_assento_que_anda_cala_o_tocador_do_lugar_de_antes(mundo: _Mundo) -> None:
    """O P1 passa ao lugar 2: o tocador do lugar 1 cala, e não vibra quem se sentou ali.

    MORDIDA: tire o ``self._conferir_os_tocadores(lugar_de)`` de
    ``_casar_as_pontes`` — sem quem reaplicar, o lugar 1 segue tocando o P1.
    """
    controles = _no_radio_os_quatro(mundo)
    mundo.mesa.volta(*controles)
    assert mundo.sub.levar_o_rumble(_P1, 0, 200) is False
    assert mundo.tocador(1).nivel == (0, 200)
    mundo.mesa.assentos.update({_P1: 2, _P2: 1})
    mundo.mesa.volta(*controles)
    assert mundo.tocador(1).nivel == (0, 0), "o lugar 1 segue tocando o P1"


def test_o_tocador_sai_antes_do_endpoint_do_lugar(
    mundo: _Mundo, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Sem DualSense e sem jogo, os lugares caem — e o tocador sai antes do endpoint.

    MORDIDA: tire o ``self._parar_o_tocador(lugar)`` do laço que derruba os
    endpoints — o fluxo fica sem nó, e o recuo manda o zumbido à saída dela.
    """
    controles = _no_radio_os_quatro(mundo)
    mundo.mesa.volta(*controles)
    mundo.sub.levar_o_rumble(_P1, 0, 200)
    mundo.fluxos.tocando.clear()  # o servidor já não o vê
    parar = eh.EndpointDeHaptica.parar

    def _parar(self: Any) -> None:
        _Tocador.eventos.append(f"endpoint-{self.lugar}-caiu")
        parar(self)

    monkeypatch.setattr(eh.EndpointDeHaptica, "parar", _parar)
    mundo.mesa.volta()
    assert _Tocador.eventos.index("tocador-1-parou") < _Tocador.eventos.index("endpoint-1-caiu")
    assert 1 not in mundo.sub._tocadores


def test_o_stop_derruba_os_tocadores(mundo: _Mundo) -> None:
    """Os tocadores morrem com o subsystem, como as pontes e os laços.

    MORDIDA: tire o bloco dos tocadores do ``stop()`` — o processo fica
    tocando depois do daemon parado.
    """
    controles = _no_cabo_os_quatro(mundo)
    mundo.mesa.volta(*controles)
    mundo.rumble(_P3, 0, 90)
    asyncio.run(mundo.sub.stop())
    assert mundo.tocador(3).parou
    assert mundo.sub._tocadores == {}


# ---------------------------------------------------------------------------
# Quem pede: o pad uinput, pelo rumble_sink do P1 e dos P2 a P4
# ---------------------------------------------------------------------------


def test_o_pad_uhid_nunca_converte(mundo: _Mundo) -> None:
    """O pad ``uhid`` é um DualSense para o jogo, e ele escolhe a própria háptica.

    E o pad que deixou o ``uinput`` cala o tocador que tocava por ele.

    MORDIDA: em ``_levar_a_haptica_fina``, converta todo pad (``converte =
    True``) — o rumble que o jogo escolheu vira háptica por cima da dele.
    """
    controles = _no_cabo_os_quatro(mundo)
    mundo.mesa.volta(*controles)
    uhid = UhidDualSense(player=1)
    assert mundo.rumble(_P1, 100, 200, vpad=uhid) == (100, 200)
    assert _Tocador.criados == {}
    mundo.rumble(_P1, 100, 200)
    assert mundo.tocador(1).nivel == (100, 200)
    mundo.rumble(_P1, 90, 90, vpad=uhid)
    assert mundo.tocador(1).nivel == (0, 0)
    assert mundo.backend.do(_P1)[-1] == (90, 90)


@pytest.mark.parametrize("transporte", ["cabo", "radio"])
def test_o_pad_que_volta_ao_uhid_com_o_caminho_de_pe_segue_no_hid(
    mundo: _Mundo, transporte: str
) -> None:
    """O pad trocou de ``uinput`` para ``uhid`` com o caminho da háptica ainda de pé.

    O tocador do lugar cala, mas segue no endpoint durante a folga, e o laço
    do cabo (ou a ponte do rádio) segue aberto para ele. O rumble que o jogo
    manda ao pad ``uhid`` nessa janela vai ao HID inteiro: quem converte é só o
    ``uinput``, e o caminho de pé não é licença para soltar os motores.

    MORDIDA: em ``_levar_a_haptica_fina``, devolva ``leva is True`` sem o
    ``converte and`` — o HID recebe (0, 0) e o rumble do jogo se perde.
    """
    if transporte == "cabo":
        controles = _no_cabo_os_quatro(mundo)
    else:
        controles = _no_radio_os_quatro(mundo)
    mundo.mesa.volta(*controles)
    mundo.rumble(_P1, 100, 200)
    mundo.mesa.volta(*controles)
    assert mundo.backend.do(_P1)[-1] == (0, 0), "o caminho da háptica não abriu"
    assert mundo.tocador(1).vivo
    uhid = UhidDualSense(player=1)
    assert mundo.rumble(_P1, 90, 90, vpad=uhid) == (90, 90)
    assert mundo.tocador(1).nivel == (0, 0)
    assert mundo.backend.do(_P1)[-1] == (90, 90), "o rumble do pad uhid não chegou ao HID"


def test_o_rumble_fixado_pela_tela_cala_a_haptica_fina(mundo: _Mundo) -> None:
    """O «Testar» da tela vence o rumble do jogo — e a háptica fina dele.

    MORDIDA: em ``apply_game_rumble``, volte o ramo do rumble fixado a só
    ``return None`` — o tocador segue tocando o jogo por baixo do teste.
    """
    controles = _no_cabo_os_quatro(mundo)
    mundo.mesa.volta(*controles)
    mundo.rumble(_P1, 100, 200)
    mundo.daemon.config.rumble_active = (10, 20)
    assert mundo.rumble(_P1, 120, 220) is None
    assert mundo.tocador(1).nivel == (0, 0)


def test_o_degrau_e_a_barra_valem_na_haptica_fina(mundo: _Mundo) -> None:
    """O par que toca é o efetivo: o degrau da coluna vale na háptica também.

    MORDIDA: em ``apply_game_rumble``, mande o par cru do jogo à háptica
    (``weak, strong`` no lugar de ``weak_eff, strong_eff``).
    """
    controles = _no_cabo_os_quatro(mundo)
    mundo.mesa.volta(*controles)
    mundo.daemon.config.rumble_policy = "custom"
    assert mundo.rumble(_P4, 100, 200) == (50, 100)
    assert mundo.tocador(4).nivel == (50, 100)


def test_o_sink_do_p1_leva_o_pad_dele(mundo: _Mundo) -> None:
    """O ``rumble_sink`` do posto entrega o pad do P1 junto do pedido.

    MORDIDA: em ``make_primary_rumble_sink``, não passe o ``vpad`` — o rumble
    do P1 nunca vira háptica.
    """
    controles = _no_cabo_os_quatro(mundo)
    mundo.mesa.volta(*controles)
    mundo.daemon._gamepad_device = UinputGamepad.for_flavor("xbox")
    gp.make_primary_rumble_sink(mundo.daemon)(40, 80)
    assert mundo.tocador(1).nivel == (40, 80)
    assert mundo.tocador(1).dono == _P1


@pytest.mark.parametrize("uniq", [_P2, _P3, _P4], ids=["P2", "P3", "P4"])
def test_o_sink_de_cada_secundario_leva_o_pad_dele(mundo: _Mundo, uniq: str) -> None:
    """O ``rumble_sink`` de cada jogador do co-op entrega o pad DELE, ao lugar dele.

    MORDIDA: em ``CoopManager._make_player_rumble_sink``, não passe o ``vpad``
    — os P2 a P4 nunca vibram pela háptica.
    """
    controles = _no_radio_os_quatro(mundo)
    mundo.mesa.volta(*controles)
    coop = CoopManager(mundo.daemon)
    coop._players[uniq] = SimpleNamespace(vpad=UinputGamepad.for_flavor("xbox"))
    coop._make_player_rumble_sink(uniq)(70, 0)
    lugar = _QUATRO.index(uniq) + 1
    assert mundo.tocador(lugar).nivel == (70, 0)
    assert mundo.tocador(lugar).dono == uniq
    assert set(_Tocador.criados) == {lugar}
