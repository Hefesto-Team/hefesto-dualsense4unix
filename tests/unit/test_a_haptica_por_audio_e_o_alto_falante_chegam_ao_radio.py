"""A-HAPTICA-POR-AUDIO-E-O-ALTO-FALANTE-CHEGAM-AO-RADIO-01 — o som e a háptica chegam juntos.

**A causa, medida em 29/09/2026** (a Forja com os quatro DualSense): a Forja
abre o alto-falante e a háptica de cada jogador em toda sala e toca só num
deles. O modo da ponte do rádio era escolhido pelo FLUXO ABERTO, e com o
fluxo da háptica aberto e mudo a ponte ia à háptica: o canto de O Canto saía
mudo pelo rádio, e no cabo (sem ponte) tocava.

**A cura:** um dono só responde «este nó tem sinal agora?» (o ``OUVIDO``), com
o que a ponte leu dos DOIS monitores do controle, e a troca de sinal acorda a
volta. **Desde 03/10/2026 (O-SOM-E-A-HAPTICA-NUM-RELATORIO-SO-01) não há mais
modo a escolher**: a ponte escreve o ``0x36`` com o som e a háptica que
tiverem sinal no mesmo quadro, e estas réguas contam o que foi ao fio.

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
FORJA = "5150"

VOZ = struct.pack("<2h", 12000, -12000)
MOTOR = struct.pack("<4h", 0, 0, 20000, -20000)
FRENTE = struct.pack("<4h", 20000, -20000, 0, 0)


def no_do(uniq: str) -> str:
    """O endpoint do APARELHO deste controle (o ``_EndpointDeMentira`` da irmã)."""
    return f"endpoint::{uniq}"


class FonteDeMentira:
    """O ``stdout`` do gravador de um monitor: blocos no ritmo, até fechar."""

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

    def ponte(self, uniq: str) -> Any:
        ponte = self.sub._pontes.get(uniq)
        assert ponte is not None, f"o controle {uniq} ficou sem ponte"
        return ponte

    def leva(self, uniq: str) -> bool:
        """O bloco da háptica de ``uniq`` vai ao fio (o que a ponte lê a cada quadro)."""
        return self.sub._a_ponte_leva_a_haptica(uniq)

    def no_fio(self, uniq: str) -> tuple[int, int]:
        """``(quadros de som, blocos de háptica)`` que a ponte de ``uniq`` pôs no fio."""
        contagem = self.ponte(uniq).contagem
        return (contagem.quadros_opus, contagem.hapticos_no_fio)

    def esperar_o_fio(self, uniq: str, *, som: bool, haptica: bool, prazo_s: float = 5.0) -> None:
        """Espera o que deve crescer crescer; o que não deve fica parado no mesmo tempo."""
        antes = self.no_fio(uniq)
        fim = time.monotonic() + prazo_s
        while time.monotonic() < fim:
            agora = self.no_fio(uniq)
            mudou = ((agora[0] > antes[0]) is som, (agora[1] > antes[1]) is haptica)
            if all(mudou) and (som or haptica):
                return
            time.sleep(0.02)
        if not som and not haptica:
            agora = self.no_fio(uniq)
            assert agora == antes, f"foi ao fio sem sinal: {antes} -> {agora}"
            return
        raise AssertionError(
            f"no fio de {uniq}: esperado som={som} háptica={haptica}, "
            f"foi {antes} -> {self.no_fio(uniq)}"
        )

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


def test_o_canto_pelo_radio_vai_ao_fio_com_a_haptica_aberta_e_muda(sala: Mesa) -> None:
    """O Canto: a Forja abre os dois papéis, canta no alto-falante e cala a háptica."""
    som, endpoint = af.nome_do_sink(P1), no_do(P1)
    sala.fonte(som).quadro = VOZ
    sala.abrir_a_sala(P1)
    sala.volta()
    primeira = sala.ponte(P1)
    sala.esperar(som, True)
    sala.mexer(P1)
    sala.volta()
    assert sala.ponte(P1) is primeira, "a partida derrubou a ponte do canto"
    assert sala.leva(P1) is True, "quem joga recebe a háptica junto com o som"
    sala.esperar_o_fio(P1, som=True, haptica=False)
    sala.fonte(som).quadro = None
    sala.esperar(som, False)
    sala.esperar(endpoint, False)
    sala.volta()
    assert sala.ponte(P1) is primeira


def test_o_canto_que_comeca_com_a_haptica_tocando_vai_junto_com_ela(sala: Mesa) -> None:
    """O chão tocava na háptica e o canto começa: os dois no MESMO relatório, sem troca."""
    som, endpoint = af.nome_do_sink(P2), no_do(P2)
    sala.fonte(endpoint).quadro = MOTOR
    sala.abrir_a_sala(P2)
    sala.volta()
    sala.esperar(endpoint, True)
    sala.mexer(P2)
    sala.volta()
    primeira = sala.ponte(P2)
    sala.esperar_o_fio(P2, som=False, haptica=True)
    sala.fonte(som).quadro = VOZ
    sala.esperar(som, True)
    sala.volta()
    assert sala.ponte(P2) is primeira, "o canto derrubou a ponte da háptica"
    sala.esperar_o_fio(P2, som=True, haptica=True)


def test_a_voz_nos_canais_da_frente_do_endpoint_nao_e_haptica(sala: Mesa) -> None:
    """Som na frente do endpoint de quatro canais não vibra nada: o ouvido lê os traseiros."""
    endpoint = no_do(P3)
    sala.fonte(endpoint).quadro = FRENTE
    sala.abrir_a_sala(P3)
    sala.volta()
    sala.esperar(endpoint, False)
    sala.mexer(P3)
    sala.volta()
    assert sala.leva(P3) is True
    sala.esperar_o_fio(P3, som=False, haptica=False, prazo_s=0.3)


def test_a_haptica_com_sinal_e_o_alto_falante_mudo_vai_so_a_haptica(sala: Mesa) -> None:
    """Os Caminhos: sinal nos motores, o alto-falante aberto e mudo."""
    som, endpoint = af.nome_do_sink(P4), no_do(P4)
    sala.fonte(endpoint).quadro = MOTOR
    sala.abrir_a_sala(P4)
    sala.volta()
    assert sala.leva(P4) is False, "ninguém mexeu: o portão segura a háptica"
    sala.esperar(som, False)
    sala.esperar(endpoint, True)
    sala.esperar_o_fio(P4, som=False, haptica=False, prazo_s=0.3)
    sala.mexer(P4)
    sala.volta()
    assert sala.leva(P4) is True
    sala.esperar_o_fio(P4, som=False, haptica=True)


def test_o_alto_falante_calado_e_a_haptica_que_chega_sem_derrubar_a_ponte(sala: Mesa) -> None:
    """A ponte do canto já lê o endpoint: quando o chão toca, a háptica entra no mesmo fio."""
    som, endpoint = af.nome_do_sink(P1), no_do(P1)
    sala.fonte(som).quadro = VOZ
    sala.abrir_a_sala(P1)
    sala.volta()
    sala.esperar(som, True)
    sala.mexer(P1)
    sala.volta()
    primeira = sala.ponte(P1)
    sala.esperar(endpoint, False)
    sala.sub._volta_pedida = False
    sala.fonte(som).quadro = None
    sala.fonte(endpoint).quadro = MOTOR
    sala.esperar(endpoint, True)
    sala.esperar(som, False)
    assert sala.sub._volta_pedida, "a troca de sinal não acordou a volta"
    sala.volta()
    assert sala.ponte(P1) is primeira
    sala.esperar_o_fio(P1, som=False, haptica=True)


class _PonteQueConta:
    """A ponte que só se deixa contar: o que se conta aqui é quantas vezes ela troca."""

    criadas: ClassVar[list[Any]] = []

    def __init__(self, **kw: Any) -> None:
        self.kw = kw
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


def test_tiro_e_fala_alternados_nao_trocam_a_ponte(
    sala: Mesa, monkeypatch: pytest.MonkeyPatch
) -> None:
    """O motor toca sempre e a fala vem a cada outro bloco: a ponte não troca nunca."""
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
    agora[0] += 0.010667
    ouvir_o_motor(4096)
    ouvir_o_som(1920)
    sala.volta()
    assert P2 in sala.sub._pontes
    antes = len(_PonteQueConta.criadas)
    for bloco in range(40):
        agora[0] += 0.010667
        ouvir_o_motor(4096)
        (calar_o_som if bloco % 2 == 0 else ouvir_o_som)(1920)
        sala.volta()
    trocas = len(_PonteQueConta.criadas) - antes
    assert trocas == 0, f"a ponte trocou {trocas} vezes; o relatório combinado leva os dois"
    assert sala.leva(P2) is True


def test_o_fluxo_mudo_do_alto_falante_nao_segura_o_rumble(
    mundo: Any, monkeypatch: pytest.MonkeyPatch  # noqa: F811
) -> None:
    """Modo Xbox, pelo rádio: o rumble toma a ponte do alto-falante aberto e mudo."""
    monkeypatch.setattr(af, "OUVIDO", af.OuvidoDosNos())
    controles = _no_radio_os_quatro(mundo)
    som = af.nome_do_sink(_X1)
    mundo.mesa.servidor.placa(som, "/devices/virtual/som")
    mundo.mesa.servidor.jogo_em.add(som)
    mundo.mesa.volta(*controles)
    af.fonte_que_ouve(lambda n: bytes(n), som)(1920)
    mundo.mesa.volta(*controles)
    af.fonte_que_ouve(lambda n: bytes(n), som)(1920)
    mundo.rumble(_X1, 0, 180)
    af.fonte_que_ouve(lambda n: bytes(n), som)(1920)
    mundo.mesa.volta(*controles)
    from hefesto_dualsense4unix.integrations import endpoint_de_haptica as eh

    af.fonte_que_ouve(lambda n: bytes(n), som)(1920)
    af.fonte_que_ouve(
        lambda n: MOTOR * (n // 8), eh.nome_do_endpoint(_X1), canais=af.CANAIS_DA_HAPTICA
    )(4096)
    mundo.mesa.volta(*controles)
    assert mundo.sub._pontes[_X1].leva is True, (
        "o fluxo mudo do alto-falante segurou a ponte, e o rumble ficou sem ela"
    )
    af.fonte_que_ouve(lambda n: VOZ * (n // 4), som)(1920)
    mundo.mesa.volta(*controles)
    assert mundo.sub._pontes[_X1].leva is True, "o canto tirou a háptica do rumble"


def test_o_fluxo_do_alto_falante_que_ninguem_escutou_nao_segura_o_rumble(
    mundo: Any, monkeypatch: pytest.MonkeyPatch  # noqa: F811
) -> None:
    """O fluxo do alto-falante aberto, escutado ou não, não tira a háptica do rumble."""
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
    assert mundo.sub._pontes[_X1].leva is True, "o fluxo do alto-falante tirou a háptica"
    assert mundo.backend.do(_X1)[-1] == (0, 0), "o HID voltou a levar com a háptica no ar"


def test_a_troca_de_sinal_acorda_a_volta_sem_o_fluxo_mudar(sala: Mesa) -> None:
    """O fluxo fica o mesmo e o sinal chega: a espera da volta termina antes do relógio."""
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


def test_a_ponte_do_som_que_subiu_antes_do_endpoint_ganha_a_haptica(sala: Mesa) -> None:
    """O alto-falante abre antes do endpoint: a ponte sobe sem ler a háptica e, quando o
    endpoint abre, sobe de novo UMA vez para lê-lo; a partida não a derruba de novo."""
    som, endpoint = af.nome_do_sink(P4), no_do(P4)
    sala.fonte(som).quadro = VOZ
    sala.servidor.tocar(som, FORJA)
    sala.volta()
    primeira = sala.ponte(P4)
    assert primeira.le_a_haptica is False
    sala.esperar(som, True)
    assert sala.ouvido.tem_sinal(endpoint) is None
    sala.servidor.tocar(endpoint, FORJA)
    sala.volta()
    segunda = sala.ponte(P4)
    assert segunda is not primeira and segunda.le_a_haptica is True
    sala.esperar(endpoint, False)
    sala.mexer(P4)
    sala.volta()
    assert sala.ponte(P4) is segunda, "a partida derrubou a ponte de novo"
    sala.esperar_o_fio(P4, som=True, haptica=False)
