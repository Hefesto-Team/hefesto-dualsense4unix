"""A-HAPTICA-POR-AUDIO-E-O-ALTO-FALANTE-CHEGAM-AO-RADIO-01 — quem tem SINAL fica com o rádio.

**A causa, medida em 29/09/2026** (a Forja com os quatro DualSense): a Forja
abre o alto-falante e a háptica de cada jogador em toda sala e toca só num
deles. O modo da ponte do rádio era escolhido pelo FLUXO ABERTO, e com o
fluxo da háptica aberto e mudo a ponte ia à háptica: o canto de O Canto saía
mudo pelo rádio, e no cabo (sem ponte) tocava.

**A cura:** um dono só responde «este nó tem sinal agora?» (o ``OUVIDO``), com
o que a ponte leu dos DOIS monitores do controle; o modo, o rumble convertido
contra o alto-falante e o portão do cabo perguntam a ele; e a troca de sinal
acorda a volta.

O mundo destas réguas publica o que o real publica: o servidor de som de
mentira da irmã de 28/09 (as leituras curtas do ``pactl``, com o cliente dono
de cada fluxo), PCM s16le no formato que o gravador entrega (dois canais no nó
do som, quatro no endpoint, os motores nos traseiros) e um cano no lugar do
hidraw. O sinal vem dos BYTES que a fonte de mentira entrega, e não de um flag.
Endereços da faixa forjada ``aa:bb:cc``.
"""

from __future__ import annotations

import contextlib
import os
import struct
import threading
import time
from types import SimpleNamespace
from typing import Any, ClassVar

import pytest

from hefesto_dualsense4unix.integrations import alto_falante_bt as af
from tests.unit.test_a_haptica_do_radio_obedece_ao_sinal import ServidorDeSom
from tests.unit.test_no_modo_xbox_a_haptica_fina import (  # noqa: F401
    _no_radio_os_quatro,
    mesa,
    mundo,
)
from tests.unit.test_no_modo_xbox_a_haptica_fina import _P1 as _X1

P1, P2, P3, P4 = (f"aa:bb:cc:00:00:2{i}" for i in range(1, 5))
MESA = (P1, P2, P3, P4)
#: O cliente do servidor de som que é o jogo (a Forja, que abre os dois papéis).
FORJA = "5150"

#: Um quadro de voz no nó do som (dois canais) e de motor no endpoint (quatro,
#: os traseiros): o que o gravador entrega quando o jogo toca.
VOZ = struct.pack("<2h", 12000, -12000)
MOTOR = struct.pack("<4h", 0, 0, 20000, -20000)
#: Voz nos canais da FRENTE do endpoint: não é háptica (a ponte leva os traseiros).
FRENTE = struct.pack("<4h", 20000, -20000, 0, 0)


def no_do(uniq: str) -> str:
    """O endpoint do APARELHO deste controle (o ``_EndpointDeMentira`` da irmã)."""
    return f"endpoint::{uniq}"


class FonteDeMentira:
    """O ``stdout`` do gravador de um monitor: blocos no ritmo, até fechar.

    ``quadro`` é o que o jogo toca AGORA (um quadro, repetido até encher o
    pedido); ``None`` é silêncio exato. ``fechar()`` é o gravador colhido.
    """

    def __init__(self, largura: int) -> None:
        self.largura = largura
        self.quadro: bytes | None = None
        self.fechada = False
        self.lidos = 0

    def __call__(self, quantos: int) -> bytes:
        if self.fechada:
            return b""
        time.sleep(0.003)
        self.lidos += 1
        quadro = self.quadro or bytes(self.largura)
        return quadro * (quantos // len(quadro))


class _Codificador:
    """O Opus de mentira: a suíte não depende da libopus da máquina."""

    def __init__(self, *_: Any, **__: Any) -> None:
        pass

    def codificar(self, _pcm: bytes) -> bytes:
        return b"\x01" * af.BYTES_POR_QUADRO_OPUS


class Mesa:
    """``_casar_as_pontes`` do produto, com a ``PonteDeSomPorRadio`` e a bomba de verdade."""

    def __init__(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from hefesto_dualsense4unix.daemon.subsystems.alto_falante import (
            AltoFalanteSubsystem,
            ControleNaLista,
        )
        from hefesto_dualsense4unix.integrations import endpoint_de_haptica as eh
        from tests.unit.test_haptica_por_radio_01_a_ponte_troca_de_modo import (
            _EndpointDeMentira,
        )

        self.servidor = ServidorDeSom()
        self.ouvido = af.OuvidoDosNos()
        self.fontes: dict[str, FonteDeMentira] = {}
        self.canos: list[tuple[int, int]] = []
        self.parar = threading.Event()
        monkeypatch.setattr(af, "OUVIDO", self.ouvido)
        monkeypatch.setattr(af, "JANELA_DO_SINAL_S", 0.3)
        monkeypatch.setattr(af, "rodar_pactl", self.servidor)
        monkeypatch.setattr(af, "a_ponte_do_radio_pode_subir", lambda: (True, ""))
        monkeypatch.setattr(af, "fonte_do_monitor_do_no", self._fonte)
        monkeypatch.setattr(af, "CodificadorOpus", _Codificador)
        monkeypatch.setattr(eh, "EndpointDeHaptica", _EndpointDeMentira)
        monkeypatch.setattr(
            eh,
            "ancoras",
            lambda *a, **k: [eh.Ancora(syspath=f"/d/{i}", declarado=f"/d/{i}/i:1.0")
                             for i in range(4)],
        )
        monkeypatch.setattr(eh, "endpoints_de_pe", lambda *a, **k: {})
        monkeypatch.setattr(eh, "varrer_endpoints_orfaos", lambda *a, **k: None)
        self.daemon = SimpleNamespace()
        self.sub = AltoFalanteSubsystem(daemon=self.daemon)
        monkeypatch.setattr(
            AltoFalanteSubsystem, "numero_do_assento", lambda _self, u: MESA.index(u) + 1
        )
        self.sub._abrir_hidraw = self._abrir  # type: ignore[method-assign]
        self._controle = ControleNaLista

    def fonte(self, no: str) -> FonteDeMentira:
        largura = 8 if no.startswith("endpoint::") else 4
        return self.fontes.setdefault(no, FonteDeMentira(largura))

    def _fonte(self, id_do_no: str, **_: Any) -> tuple[Any, Any, str]:
        fonte = self.fonte(id_do_no)
        fonte.fechada = False
        return fonte, None, ""

    def _abrir(self, _caminho: str) -> int:
        leitura, escrita = os.pipe()
        self.canos.append((leitura, escrita))

        def _esvaziar() -> None:
            while not self.parar.is_set():
                try:
                    if not os.read(leitura, 65536):
                        return
                except OSError:
                    return

        threading.Thread(target=_esvaziar, daemon=True).start()
        return escrita

    def controles(self) -> list[Any]:
        return [
            self._controle(uniq=u, caminho=f"/dev/hidraw{30 + MESA.index(u)}", transporte="rádio")
            for u in MESA
        ]

    def abrir_a_sala(self, *quem: str) -> None:
        """A Forja abre os DOIS papéis de cada jogador, como em toda sala."""
        for uniq in quem:
            self.servidor.tocar(af.nome_do_sink(uniq), FORJA)
            self.servidor.tocar(no_do(uniq), FORJA)

    def mexer(self, *quem: str) -> None:
        from hefesto_dualsense4unix.daemon.subsystems.quem_mexe import quem_mexe_de

        marcas = quem_mexe_de(self.daemon)
        assert marcas is not None and marcas.jogo_aberto, "a partida não abriu"
        for uniq in quem:
            marcas.marcar(uniq)

    def volta(self) -> None:
        self.sub._casar_as_pontes(self.controles())

    def arranjo(self, uniq: str) -> str:
        ponte = self.sub._pontes.get(uniq)
        return "" if ponte is None else ponte.arranjo.nome

    def esperar(self, no: str, valor: bool | None, prazo_s: float = 5.0) -> None:
        fim = time.monotonic() + prazo_s
        while time.monotonic() < fim:
            if self.ouvido.tem_sinal(no) is valor:
                return
            time.sleep(0.01)
        agora = self.ouvido.tem_sinal(no)
        raise AssertionError(f"o ouvido não chegou a {valor!r} em {no}: {agora!r}")

    def fechar(self) -> None:
        for fonte in self.fontes.values():
            fonte.fechada = True
        for ponte in list(self.sub._pontes.values()):
            ponte.descer(esperar_s=2.0)
        self.parar.set()
        for leitura, escrita in self.canos:
            for fd in (escrita, leitura):
                with contextlib.suppress(OSError):
                    os.close(fd)


@pytest.fixture
def sala(monkeypatch: pytest.MonkeyPatch) -> Any:
    m = Mesa(monkeypatch)
    yield m
    m.fechar()


# ---------------------------------------------------------------------------
# 1. O modo segue o sinal
# ---------------------------------------------------------------------------


def test_o_canto_pelo_radio_fica_no_alto_falante_com_a_haptica_aberta_e_muda(sala: Mesa) -> None:
    """O Canto: a Forja abre os dois papéis, canta no alto-falante e cala a háptica.

    A ponte sobe no ``0x35`` antes de o jogador mexer (é o que o diário de
    29/09 mostra, nas 13 salas) e FICA nele quando ele mexe, com o canto
    tocando e na pausa entre dois cantos.

    MORDIDA: volte o modo a ``endpoint_toca and (este_joga or pelo_rumble)``
    em ``_casar_as_pontes`` — depois de mexer, a ponte vai à háptica.
    """
    som, endpoint = af.nome_do_sink(P1), no_do(P1)
    sala.fonte(som).quadro = VOZ
    sala.abrir_a_sala(P1)
    sala.volta()
    assert sala.arranjo(P1) == af.ARRANJO_035.nome
    sala.esperar(som, True)
    sala.mexer(P1)
    sala.volta()
    assert sala.arranjo(P1) == af.ARRANJO_035.nome, "o fluxo mudo da háptica tirou o canto"
    # A pausa entre dois cantos: os dois mudos, e a háptica ESCUTADA.
    sala.fonte(som).quadro = None
    sala.esperar(som, False)
    sala.esperar(endpoint, False)
    sala.volta()
    assert sala.arranjo(P1) == af.ARRANJO_035.nome, "a pausa do canto deu o rádio à háptica muda"


def test_o_canto_que_comeca_com_a_ponte_na_haptica_a_devolve_ao_alto_falante(sala: Mesa) -> None:
    """A ponte está na háptica (o chão tocava) e o canto começa: ela volta ao ``0x35``.

    No modo da háptica o nó do som é lido pelo fio do ouvido da ponte, só
    para ouvir; é por ele que o canto chega ao dono do sinal.
    """
    som, endpoint = af.nome_do_sink(P2), no_do(P2)
    sala.fonte(endpoint).quadro = MOTOR
    sala.abrir_a_sala(P2)
    sala.volta()
    sala.esperar(endpoint, True)
    sala.mexer(P2)
    sala.volta()
    assert sala.arranjo(P2) == af.ARRANJO_HAPTICA_032.nome
    sala.esperar(som, False)
    sala.fonte(endpoint).quadro = None
    sala.fonte(som).quadro = VOZ
    sala.esperar(som, True)
    sala.volta()
    assert sala.arranjo(P2) == af.ARRANJO_035.nome
    sala.esperar(endpoint, False)


def test_a_voz_nos_canais_da_frente_do_endpoint_nao_e_haptica(sala: Mesa) -> None:
    """Som na frente do endpoint de quatro canais não vibra nada: o ouvido lê os traseiros."""
    endpoint = no_do(P3)
    sala.fonte(endpoint).quadro = FRENTE
    sala.abrir_a_sala(P3)
    sala.volta()
    sala.esperar(endpoint, False)
    sala.mexer(P3)
    sala.volta()
    assert sala.arranjo(P3) == af.ARRANJO_035.nome


# ---------------------------------------------------------------------------
# 2. A háptica ainda ganha quando é ela que tem sinal
# ---------------------------------------------------------------------------


def test_a_haptica_com_sinal_e_o_alto_falante_mudo_vao_a_haptica(sala: Mesa) -> None:
    """Os Caminhos: sinal nos motores, o alto-falante aberto e mudo.

    MORDIDA: faça ``_modo_pelo_sinal`` devolver sempre ``"som"`` — a ponte
    fica no ``0x35`` com o chão tocando nos motores.
    """
    som, endpoint = af.nome_do_sink(P4), no_do(P4)
    sala.fonte(endpoint).quadro = MOTOR
    sala.abrir_a_sala(P4)
    sala.volta()
    assert sala.arranjo(P4) == af.ARRANJO_035.nome
    sala.esperar(som, False)
    sala.esperar(endpoint, True)
    sala.mexer(P4)
    sala.volta()
    assert sala.arranjo(P4) == af.ARRANJO_HAPTICA_032.nome
    sala.esperar(endpoint, True)
    sala.volta()
    assert sala.arranjo(P4) == af.ARRANJO_HAPTICA_032.nome


def test_o_alto_falante_calado_devolve_o_radio_a_haptica_que_tem_sinal(sala: Mesa) -> None:
    """A ponte no som escuta o endpoint de quem pode passar à háptica, e passa quando o chão toca.

    É a volta que acorda na troca de sinal (a régua 5, no fio de verdade): o
    fluxo não muda, o sinal passa do alto-falante ao endpoint.
    """
    som, endpoint = af.nome_do_sink(P1), no_do(P1)
    sala.fonte(som).quadro = VOZ
    sala.abrir_a_sala(P1)
    sala.volta()
    sala.esperar(som, True)
    sala.mexer(P1)
    sala.volta()
    assert sala.arranjo(P1) == af.ARRANJO_035.nome
    sala.esperar(endpoint, False)  # o ouvido da háptica no modo som
    sala.sub._volta_pedida = False
    sala.fonte(som).quadro = None
    sala.fonte(endpoint).quadro = MOTOR
    sala.esperar(endpoint, True)
    sala.esperar(som, False)
    assert sala.sub._volta_pedida, "a troca de sinal não acordou a volta"
    sala.volta()
    assert sala.arranjo(P1) == af.ARRANJO_HAPTICA_032.nome


# ---------------------------------------------------------------------------
# 3. A histerese — o relógio é de mentira, os bytes passam pelo ouvido do produto
# ---------------------------------------------------------------------------


class _PonteQueConta:
    """A ponte que só diz o arranjo: o que se conta aqui é quantas vezes ela troca."""

    criadas: ClassVar[list[Any]] = []

    def __init__(self, **kw: Any) -> None:
        self.arranjo = kw.get("arranjo") or af.ARRANJO_035
        self.motivo = ""
        _PonteQueConta.criadas.append(self)

    def subir(self) -> bool:
        return True

    def descer(self, **_: Any) -> bool:
        return True

    def esta_de_pe(self) -> bool:
        return True

    def terminou_sozinha(self) -> bool:
        return False


def test_tiro_e_fala_alternados_nao_trocam_a_ponte_mais_de_uma_vez(
    sala: Mesa, monkeypatch: pytest.MonkeyPatch
) -> None:
    """O motor toca sempre e a fala vem a cada outro bloco: a ponte troca uma vez só.

    Quarenta blocos de 10,667 ms (menos que a janela de um segundo), uma volta
    por bloco, com o relógio de mentira. Os dois têm sinal, e o alto-falante
    ganha — sem voltar à háptica a cada respiro da fala.

    MORDIDA: encurte ``JANELA_DO_SINAL_S`` para menos que um bloco (0,005 s)
    — a ponte troca a cada bloco, e a conta passa de uma.
    """
    agora = [100.0]
    sala.ouvido = af.OuvidoDosNos(relogio=lambda: agora[0])
    monkeypatch.setattr(af, "OUVIDO", sala.ouvido)
    monkeypatch.setattr(af, "JANELA_DO_SINAL_S", 1.0)
    monkeypatch.setattr(af, "PonteDeSomPorRadio", _PonteQueConta)
    _PonteQueConta.criadas = []
    som, endpoint = af.nome_do_sink(P2), no_do(P2)
    sala.abrir_a_sala(P2)
    sala.volta()
    sala.mexer(P2)
    ouvir_o_som = af.fonte_que_ouve(lambda n: VOZ * (n // 4), som)
    calar_o_som = af.fonte_que_ouve(lambda n: bytes(n), som)
    ouvir_o_motor = af.fonte_que_ouve(
        lambda n: MOTOR * (n // 8), endpoint, canais=af.CANAIS_DA_HAPTICA
    )
    # A cena começa: o motor e a fala, e a ponte vai ao alto-falante.
    agora[0] += 0.010667
    ouvir_o_motor(4096)
    ouvir_o_som(1920)
    sala.volta()
    assert sala.arranjo(P2) == af.ARRANJO_035.nome
    antes = len(_PonteQueConta.criadas)
    for bloco in range(40):
        agora[0] += 0.010667
        ouvir_o_motor(4096)
        (calar_o_som if bloco % 2 == 0 else ouvir_o_som)(1920)
        sala.volta()
    trocas = len(_PonteQueConta.criadas) - antes
    assert trocas <= 1, f"a ponte trocou {trocas} vezes em menos de uma janela"
    assert sala.arranjo(P2) == af.ARRANJO_035.nome


# ---------------------------------------------------------------------------
# 4. O espelho no rumble: o fluxo MUDO do alto-falante não segura a ponte
# ---------------------------------------------------------------------------


def test_o_fluxo_mudo_do_alto_falante_nao_segura_o_rumble(
    mundo: Any, monkeypatch: pytest.MonkeyPatch  # noqa: F811
) -> None:
    """Modo Xbox, pelo rádio: o rumble toma a ponte do alto-falante aberto e mudo.

    E com o alto-falante TOCANDO o som fica com ela (a D-2909-NO-RADIO-O-
    ALTO-FALANTE-GANHA de sempre: a decisão não muda, muda a pergunta).

    MORDIDA: devolva ``sink_esta_tocando(nome_do_sink(uniq), na_duvida=True)``
    ao ramo do rumble em ``_casar_as_pontes`` — o primeiro caso fica no som.
    """
    monkeypatch.setattr(af, "OUVIDO", af.OuvidoDosNos())
    controles = _no_radio_os_quatro(mundo)
    som = af.nome_do_sink(_X1)
    mundo.mesa.servidor.placa(som, "/devices/virtual/som")
    mundo.mesa.servidor.jogo_em.add(som)
    mundo.mesa.volta(*controles)
    # A ponte do som escuta o fluxo aberto e MUDO: bytes zero no monitor. Na
    # volta em que ela subiu ninguém o tinha ouvido ainda («não sei»), e o
    # fluxo segurou; a volta seguinte já sabe que ele é mudo.
    af.fonte_que_ouve(lambda n: bytes(n), som)(1920)
    mundo.mesa.volta(*controles)
    af.fonte_que_ouve(lambda n: bytes(n), som)(1920)
    mundo.rumble(_X1, 0, 180)
    af.fonte_que_ouve(lambda n: bytes(n), som)(1920)
    mundo.mesa.volta(*controles)
    # O tocador do rumble toca no endpoint do aparelho, e a ponte do som o escuta.
    from hefesto_dualsense4unix.integrations import endpoint_de_haptica as eh

    af.fonte_que_ouve(lambda n: bytes(n), som)(1920)
    af.fonte_que_ouve(
        lambda n: MOTOR * (n // 8), eh.nome_do_endpoint(_X1), canais=af.CANAIS_DA_HAPTICA
    )(4096)
    mundo.mesa.volta(*controles)
    assert mundo.sub._pontes[_X1].arranjo is af.ARRANJO_HAPTICA_032, (
        "o fluxo mudo do alto-falante segurou a ponte, e o rumble ficou sem ela"
    )
    # Ela põe som no alto-falante: o som fica com o rádio, e o HID leva o rumble.
    af.fonte_que_ouve(lambda n: VOZ * (n // 4), som)(1920)
    mundo.mesa.volta(*controles)
    assert mundo.sub._pontes[_X1].arranjo is None


def test_o_fluxo_do_alto_falante_que_ninguem_escutou_ainda_segura_o_rumble(
    mundo: Any, monkeypatch: pytest.MonkeyPatch  # noqa: F811
) -> None:
    """«Não sei» não é «mudo»: sem ninguém escutando o nó do som, vale o fluxo aberto.

    A ponte ainda não subiu (ou espera vaga) e ninguém leu o monitor do
    alto-falante: o rumble segue pelo HID e o som fica com o rádio, como antes
    (a D-2909-NO-RADIO-O-ALTO-FALANTE-GANHA com o ``na_duvida=True`` dela). Só o
    fluxo ESCUTADO e mudo solta a ponte para o rumble.

    MORDIDA: no ramo do rumble de ``_casar_as_pontes``, pergunte só
    ``som_toca`` (o «não sei» vira «mudo») — a háptica do rumble toma o rádio de
    um alto-falante que ninguém ouviu.
    """
    monkeypatch.setattr(af, "OUVIDO", af.OuvidoDosNos())
    controles = _no_radio_os_quatro(mundo)
    mundo.mesa.volta(*controles)
    mundo.rumble(_X1, 0, 180)
    mundo.mesa.volta(*controles)
    som = af.nome_do_sink(_X1)
    mundo.mesa.servidor.placa(som, "/devices/virtual/som")
    mundo.mesa.servidor.jogo_em.add(som)
    assert af.OUVIDO.tem_sinal(som) is None
    mundo.mesa.volta(*controles)
    assert mundo.sub._pontes[_X1].arranjo is None, "o «não sei» do ouvido virou «mudo»"
    assert mundo.backend.do(_X1)[-1] == (0, 180), "o HID não voltou a levar"


# ---------------------------------------------------------------------------
# 5. A volta acorda na troca de sinal
# ---------------------------------------------------------------------------


def test_a_troca_de_sinal_acorda_a_volta_sem_o_fluxo_mudar(sala: Mesa) -> None:
    """O fluxo fica o mesmo e o sinal chega: a espera da volta termina antes do relógio.

    MORDIDA: tire ``OUVIDO.escutar(self._acordar_a_volta)`` do ``__init__`` do
    subsystem — a espera vai até o relógio, e ninguém troca o modo.
    """
    som = af.nome_do_sink(P3)
    sala.abrir_a_sala(P3)
    sala.sub._volta_pedida = False
    sala.sub._acordar.clear()
    af.fonte_que_ouve(lambda n: bytes(n), som)(1920)
    assert not sala.sub._acordar.is_set(), "o silêncio acordou a volta"
    af.fonte_que_ouve(lambda n: VOZ * (n // 4), som)(1920)
    assert sala.sub._acordar.is_set() and sala.sub._volta_pedida

    gerenciador = SimpleNamespace(dormir=lambda _s: False)
    comeco = time.monotonic()
    assert sala.sub._esperar_a_mesa_do_som(gerenciador) is False
    assert time.monotonic() - comeco < 1.0, "a volta esperou o relógio"


def test_o_ouvido_diz_nao_sei_quando_ninguem_escuta() -> None:
    """Sem leitura há mais que ``SURDO_S``, a resposta é ``None``, e não «mudo»."""
    agora = [0.0]
    ouvido = af.OuvidoDosNos(relogio=lambda: agora[0])
    assert ouvido.tem_sinal("hefesto_som_000021") is None
    ouvido.ouvir("hefesto_som_000021", False)
    assert ouvido.tem_sinal("hefesto_som_000021") is False
    ouvido.ouvir("hefesto_som_000021", True)
    assert ouvido.tem_sinal("hefesto_som_000021") is True
    agora[0] += af.JANELA_DO_SINAL_S + af.SURDO_S + 0.1
    assert ouvido.tem_sinal("hefesto_som_000021") is None


# ---------------------------------------------------------------------------
# 6. Os três nós de um controle: desde 02/10 dizem o APARELHO, e a régua mora
# em ``tests/unit/test_a_haptica_e_por_aparelho.py`` (A-HAPTICA-E-POR-APARELHO-01)
# ---------------------------------------------------------------------------


def test_a_ponte_do_som_que_subiu_antes_do_endpoint_ganha_o_ouvido(sala: Mesa) -> None:
    """O fluxo do alto-falante abre antes do endpoint (a ponte sobe sem ouvido da
    háptica); o endpoint abre depois, com o canto calado: a ponte sobe de novo COM o
    ouvido, e a pausa entre dois cantos não dá o rádio à háptica muda.

    MORDIDA: faça ``sem_ouvido`` ser sempre falso em ``_casar_as_pontes`` — o
    endpoint fica sem ninguém que o escute («não sei»), e o jogador que mexe na
    pausa leva a ponte à háptica muda.
    """
    som, endpoint = af.nome_do_sink(P4), no_do(P4)
    sala.servidor.tocar(som, FORJA)
    sala.volta()
    assert sala.arranjo(P4) == af.ARRANJO_035.nome
    sala.esperar(som, False)
    assert sala.ouvido.tem_sinal(endpoint) is None
    sala.servidor.tocar(endpoint, FORJA)
    sala.volta()
    assert sala.arranjo(P4) == af.ARRANJO_035.nome
    sala.esperar(endpoint, False)
    sala.mexer(P4)
    sala.volta()
    assert sala.arranjo(P4) == af.ARRANJO_035.nome, "a pausa do canto deu o rádio à háptica muda"
