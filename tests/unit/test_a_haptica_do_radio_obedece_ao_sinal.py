"""A-HAPTICA-DO-RADIO-OBEDECE-AO-SINAL-DO-JOGO-01 — o rádio só leva o que tem sinal.

**A causa, medida em 27/09/2026** (PRAGMATA no menu, os quatro no rádio): o
jogo abre um fluxo de quatro canais em cada um dos quatro endpoints e manda
SILÊNCIO EXATO por eles (RMS e pico 0). Para o daemon, «tocando» era «o fluxo
existe», e não «há sinal»: a ponte de pé em silêncio a 93,75 reports por
segundo foi o que afogou o rádio em 22/09, e o portão por evdev (20/09) e o
``quem_mexe`` (26/09) nasceram para não subir quatro pontes mudas.

**A cura:** a ponte escuta o monitor o tempo todo (ler é local) e só escreve o
bloco que tem sinal nos canais que o arranjo leva — 3-4 na háptica, 1-2 no
som —, com UM silêncio depois do último sinal. A partida é o dono do fluxo no
endpoint (o cliente do servidor de som), e não quem tem
``STEAM_COMPAT_DATA_PATH`` no ambiente; e a volta acorda pelo fluxo que nasce,
avisado pelo retrato do som, sem vigia de 0,4 s.

O mundo destas réguas é de mentira e publica o que o real publica: PCM s16le
entrelaçado de quatro canais a 48 kHz (o que o ``pw-record`` entrega do monitor
do endpoint), um fd de escrita por controle no lugar do hidraw, e a linha curta
do ``pactl`` com o índice do cliente dono de cada fluxo. Nenhum aparelho,
nenhum servidor de som. Endereços da faixa forjada ``aa:bb:cc``.
"""

from __future__ import annotations

import os
import struct
from typing import Any

import pytest

from hefesto_dualsense4unix.integrations import alto_falante_bt as af
from hefesto_dualsense4unix.integrations import haptica_bt

#: O tamanho do report da háptica pelo rádio (o ``0x32``) e onde o bloco mora.
TAMANHO_032 = af.TAMANHO_DO_DEGRAU[0x32]
BLOCO_032 = slice(13, 13 + af.BYTES_DO_BLOCO_HAPTICO)


def _bloco_de_pcm(*, canais_com_sinal: tuple[int, ...] = (), amplitude: int = 20000) -> bytes:
    """512 quadros de quatro canais s16le: o que um bloco háptico consome.

    ``canais_com_sinal`` usa a numeração da sprint, de 1 a 4 (1-2 a voz, 3-4
    os motores). Sem canal nenhum, é o silêncio exato que o PRAGMATA manda no
    menu.
    """
    quadro = [0, 0, 0, 0]
    for canal in canais_com_sinal:
        quadro[canal - 1] = amplitude
    return struct.pack("<4h", *quadro) * af.QUADROS_POR_BLOCO_HAPTICO


SILENCIO = _bloco_de_pcm()
MOTOR = _bloco_de_pcm(canais_com_sinal=(3, 4))


def _fonte(blocos: list[bytes]) -> Any:
    """A fonte do monitor: um bloco por leitura, e ``b""`` quando o jogo fecha."""
    fila = list(blocos)

    def _ler(_quantos: int) -> bytes:
        return fila.pop(0) if fila else b""

    return _ler


def _bomba_da_haptica(blocos: list[bytes], *, so_com_sinal: bool = True) -> tuple[Any, list[bytes]]:
    escritas: list[bytes] = []

    def _escritor(report: bytes) -> int:
        escritas.append(report)
        return len(report)

    bomba = af.BombaDeSomPeloRadio(
        arranjo=af.ARRANJO_HAPTICA_032,
        fonte=lambda _n: b"",
        fonte_haptica=_fonte(blocos),
        escritor=_escritor,
        seco=False,
        so_com_sinal=so_com_sinal,
    )
    return bomba, escritas


# ---------------------------------------------------------------------------
# 1. A bomba: silêncio não vai, sinal vai, e um silêncio fecha
# ---------------------------------------------------------------------------


class TestORadioSoLevaOQueTemSinal:
    def test_o_silencio_exato_do_jogo_nao_manda_nada(self) -> None:
        """O menu do PRAGMATA: o fluxo existe, e o rádio fica livre.

        MORDIDA: troque o critério por «o fluxo existe» (faça ``_vale_mandar``
        devolver ``True``) — o silêncio passa a mandar 93,75 reports por
        segundo, o afogamento de 22/09.
        """
        bomba, escritas = _bomba_da_haptica([SILENCIO] * 8)
        bomba.rodar(segundos=10)
        assert escritas == [], f"o silêncio foi ao rádio: {len(escritas)} reports"
        assert bomba.contagem.reports_calados == 8
        assert bomba.contagem.reports_montados == 0

    def test_o_sinal_vai_no_bloco_dele_e_um_silencio_fecha(self) -> None:
        """Dois blocos com motor no meio de silêncio: vão os dois e UM silêncio.

        O silêncio depois do último sinal é o que faz o motor parar no zero em
        vez de ficar no último valor. MORDIDA: tire o ramo ``_mandou_sinal`` de
        ``_vale_mandar`` — saem dois reports, e o motor fica no último valor.
        """
        bomba, escritas = _bomba_da_haptica(
            [SILENCIO, SILENCIO, MOTOR, MOTOR, SILENCIO, SILENCIO, SILENCIO]
        )
        bomba.rodar(segundos=10)
        assert len(escritas) == 3, f"eram 2 com sinal e 1 silêncio: {len(escritas)}"
        assert all(len(r) == TAMANHO_032 for r in escritas)
        assert escritas[0][BLOCO_032] != bytes(64), "o primeiro bloco com sinal saiu mudo"
        assert escritas[1][BLOCO_032] != bytes(64)
        assert escritas[2][BLOCO_032] == haptica_bt.bloco_de_silencio(), (
            "depois do último sinal tem de ir o bloco de silêncio"
        )
        assert bomba.contagem.reports_calados == 4

    def test_a_sequencia_so_anda_com_o_que_foi(self) -> None:
        """Para o firmware, o fluxo PAUSOU: o nibble e o contador seguem de onde pararam."""
        bomba, escritas = _bomba_da_haptica(
            [MOTOR, SILENCIO, SILENCIO, SILENCIO, SILENCIO, MOTOR, SILENCIO]
        )
        bomba.rodar(segundos=10)
        assert [r[1] >> 4 for r in escritas] == [0, 1, 2, 3]
        assert [r[10] for r in escritas] == [0, 1, 2, 3], "o contador de quadros pulou"

    def test_o_ensaio_de_bancada_segue_mandando_o_que_pediu(self) -> None:
        """A bomba nasce sem o critério: o ensaio manda silêncio de propósito."""
        bomba, escritas = _bomba_da_haptica([SILENCIO] * 3, so_com_sinal=False)
        bomba.rodar(segundos=10)
        assert len(escritas) == 3


class TestOCriterioEDoArranjo:
    """Canais 3-4 na háptica, 1-2 no som — nunca um canal fixo."""

    def _bomba_do_som(self, pcm: list[bytes]) -> tuple[Any, list[bytes]]:
        escritas: list[bytes] = []

        class _Codificador:
            def codificar(self, _pcm: bytes) -> bytes:
                return b"\x01" * af.BYTES_POR_QUADRO_OPUS

        def _escritor(report: bytes) -> int:
            escritas.append(report)
            return len(report)

        bomba = af.BombaDeSomPeloRadio(
            arranjo=af.ARRANJO_035,
            fonte=_fonte(pcm),
            escritor=_escritor,
            seco=False,
            codificador=_Codificador(),
            so_com_sinal=True,
        )
        return bomba, escritas

    def test_o_alto_falante_com_som_nos_canais_1_e_2_manda(self) -> None:
        """O nó de som tem dois canais — os 1-2 da sprint —, e é o que o 0x35 leva.

        MORDIDA: fixe o critério nos motores (``_vale_mandar`` olhando só o
        ``haptico``) — o controle em modo som fica mudo.
        """
        voz = struct.pack("<2h", 12000, -12000) * af.AMOSTRAS_POR_QUADRO
        mudo = bytes(af.BYTES_DE_PCM_POR_QUADRO)
        bomba, escritas = self._bomba_do_som([mudo, voz, voz, mudo, mudo])
        bomba.rodar(segundos=10)
        assert len(escritas) == 3, f"eram 2 com som e 1 silêncio: {len(escritas)}"
        assert all(r[0] == 0x35 for r in escritas)

    def test_o_alto_falante_mudo_nao_manda(self) -> None:
        mudo = bytes(af.BYTES_DE_PCM_POR_QUADRO)
        bomba, escritas = self._bomba_do_som([mudo] * 5)
        bomba.rodar(segundos=10)
        assert escritas == []

    def test_a_voz_do_jogo_nao_liga_os_motores(self) -> None:
        """Na háptica, sinal só nos canais 1-2 do endpoint é a voz: o motor não vai.

        É a conta de :mod:`haptica_bt` (só os canais 3-4 viram bloco), e o
        critério lê o bloco — por isso ele é o do arranjo.
        """
        voz = _bloco_de_pcm(canais_com_sinal=(1, 2))
        bomba, escritas = _bomba_da_haptica([voz] * 4)
        bomba.rodar(segundos=10)
        assert escritas == []


# ---------------------------------------------------------------------------
# 2. A ponte do produto liga o critério
# ---------------------------------------------------------------------------


def _ler_tudo(fd: int) -> bytes:
    pedacos = []
    os.set_blocking(fd, False)
    while True:
        try:
            pedaco = os.read(fd, 65536)
        except BlockingIOError:
            break
        if not pedaco:
            break
        pedacos.append(pedaco)
    return b"".join(pedacos)


def _esperar_a_corrida(ponte: Any, prazo_s: float = 10.0) -> None:
    import time

    fim = time.monotonic() + prazo_s
    while ponte._corrida_viva() and time.monotonic() < fim:
        time.sleep(0.01)
    assert not ponte._corrida_viva(), "a fonte secou e a ponte não terminou"


def test_a_ponte_do_produto_so_escreve_o_que_tem_sinal(monkeypatch: pytest.MonkeyPatch) -> None:
    """A ponte de verdade, com o laço de verdade, num fd de mentira no lugar do hidraw.

    MORDIDA: mude o padrão de ``so_com_sinal`` da ``PonteDeSomPorRadio`` para
    ``False`` — o silêncio do menu vai ao fd, report a report.
    """
    monkeypatch.setattr(af, "a_ponte_do_radio_pode_subir", lambda: (True, ""))
    leitura, escrita = os.pipe()
    try:
        ponte = af.PonteDeSomPorRadio(
            uniq="aa:bb:cc:00:00:03",
            abrir_hidraw=lambda: escrita,
            fonte_de_pcm=lambda _n: b"",
            arranjo=af.ARRANJO_HAPTICA_032,
            fonte_de_haptica=_fonte([SILENCIO] * 5 + [MOTOR] + [SILENCIO] * 5),
        )
        assert ponte.subir() is True, ponte.motivo
        _esperar_a_corrida(ponte)
        escrito = _ler_tudo(leitura)
    finally:
        os.close(leitura)
    assert len(escrito) == 2 * TAMANHO_032, (
        f"eram o sinal e um silêncio; foram {len(escrito) / TAMANHO_032:.1f} reports"
    )
    assert ponte.contagem is not None and ponte.contagem.reports_calados == 9


# ---------------------------------------------------------------------------
# O servidor de som de mentira — as leituras curtas do `pactl`, com o dono
# ---------------------------------------------------------------------------


class ServidorDeSom:
    """O ``pipewire-pulse`` de mentira, pelas leituras curtas que o produto faz.

    Publica o que o real publica, no formato do ``printf`` do ``pactl`` 16.1:
    ``list short sinks`` (índice, nome, driver, formato, estado), ``list short
    sink-inputs`` (índice, nó, CLIENTE, driver, formato) e ``list short
    clients`` (índice, driver, binário). O fluxo sem programa (um módulo) sai
    com o cliente ``-``, como no real. ``mudo`` é o servidor que não responde:
    toda leitura devolve ``None``, a mesma falha de um ``pactl`` que saiu com
    erro. As funções do produto rodam de verdade sobre ele.
    """

    def __init__(self) -> None:
        self._indices: dict[str, int] = {}
        self.fluxos: list[tuple[str, str]] = []
        self.clientes: set[str] = set()
        self.mudo = False
        self.perguntas: list[tuple[str, ...]] = []

    def _indice(self, sink: str) -> int:
        return self._indices.setdefault(sink, 700 + len(self._indices))

    def tocar(self, sink: str, cliente: str) -> None:
        """Um fluxo do ``cliente`` no ``sink`` (o cliente ``-`` é um módulo)."""
        self._indice(sink)
        self.fluxos.append((sink, cliente))
        if cliente != "-":
            self.clientes.add(cliente)

    def calar(self, cliente: str) -> None:
        """O cliente fecha os fluxos dele e segue conectado."""
        self.fluxos = [(s, c) for s, c in self.fluxos if c != cliente]

    def desconectar(self, cliente: str) -> None:
        """O programa fechou: os fluxos e a conexão dele saem."""
        self.calar(cliente)
        self.clientes.discard(cliente)

    def __call__(self, argv: list[str]) -> str | None:
        self.perguntas.append(tuple(argv))
        if self.mudo:
            return None
        if argv == ["pactl", "list", "short", "sinks"]:
            return "".join(
                f"{i}\t{nome}\tPipeWire\tfloat32le 4ch 48000Hz\tRUNNING\n"
                for nome, i in self._indices.items()
            )
        if argv == ["pactl", "list", "short", "sink-inputs"]:
            return "".join(
                f"{900 + k}\t{self._indices[sink]}\t{cliente}\tPipeWire\tfloat32le 4ch 48000Hz\n"
                for k, (sink, cliente) in enumerate(self.fluxos)
            )
        if argv == ["pactl", "list", "short", "clients"]:
            return "".join(f"{c}\tPipeWire\twine64-preloader\n" for c in sorted(self.clientes))
        return None


def test_o_servidor_de_mentira_fala_o_formato_que_o_retrato_sintetiza() -> None:
    """O dublê não é mais frouxo que o real: a linha curta dos fluxos é a do retrato.

    O retrato do som (``retrato_do_som.curto_dos_fluxos``) é quem responde no
    daemon; se o dublê divergisse dele, as réguas mediriam outro formato.
    """
    from hefesto_dualsense4unix.integrations import retrato_do_som as rs

    servidor = ServidorDeSom()
    servidor.tocar("endpoint::p3", "4243")
    curto = servidor(["pactl", "list", "short", "sink-inputs"])
    assert curto is not None
    sintetizado = rs.curto_dos_fluxos(
        [rs.Fluxo(indice=900, alvo="700", cliente="4243", driver="PipeWire",
                  formato="float32le 4ch 48000Hz")]
    )
    assert curto == sintetizado
    sem_cliente = rs.curto_dos_fluxos([rs.Fluxo(indice=1, alvo="700", cliente="n/a")])
    assert sem_cliente.split("\t")[2] == af.SEM_CLIENTE


class TestODonoDoFluxo:
    def test_os_donos_sao_os_clientes_que_tocam_nos_pedidos(self) -> None:
        servidor = ServidorDeSom()
        servidor.tocar("endpoint::p1", "4243")
        servidor.tocar("endpoint::p2", "4243")
        servidor.tocar("hefesto_som_000001", "77")
        servidor.tocar("endpoint::p4", "-")
        assert af.donos_dos_fluxos(["endpoint::p1", "endpoint::p2", "endpoint::p4"], servidor) == {
            "4243"
        }, "o módulo sem cliente virou dono, ou o fluxo de outro nó entrou"
        assert af.clientes_conectados(servidor) == {"4243", "77"}

    def test_o_servidor_mudo_e_nao_sei(self) -> None:
        servidor = ServidorDeSom()
        servidor.mudo = True
        assert af.donos_dos_fluxos(["endpoint::p1"], servidor) is None
        assert af.clientes_conectados(servidor) is None
        assert af.sinks_que_tocam(["endpoint::p1"], servidor) is None

    def test_sem_nada_a_perguntar_nao_pergunta(self) -> None:
        servidor = ServidorDeSom()
        assert af.donos_dos_fluxos([], servidor) == frozenset()
        assert servidor.perguntas == []


# ---------------------------------------------------------------------------
# 3. A mesa de quatro no rádio: o subsystem de verdade, com as pontes de verdade
# ---------------------------------------------------------------------------

P1, P2, P3, P4 = (f"aa:bb:cc:00:00:0{i}" for i in range(1, 5))
MESA = (P1, P2, P3, P4)
#: O cliente do servidor de som que é o jogo (o ``winepulse`` do PRAGMATA).
JOGO = "4243"


class MesaDeQuatro:
    """``_casar_as_pontes`` do produto, com a ``PonteDeSomPorRadio`` e a bomba de verdade.

    Só o que toca aparelho ou servidor é de mentira: o endpoint (o nome), o
    servidor de som (:class:`ServidorDeSom`), o monitor de cada endpoint (um
    bloco por leitura, e o jogo fechando quando a lista acaba) e o hidraw de
    cada controle (um cano, lido no fim).
    """

    def __init__(self, monkeypatch: pytest.MonkeyPatch, sinal: dict[str, list[bytes]]) -> None:
        from types import SimpleNamespace

        from hefesto_dualsense4unix.daemon.subsystems.alto_falante import (
            AltoFalanteSubsystem,
            ControleNaLista,
        )
        from hefesto_dualsense4unix.integrations import endpoint_de_haptica as eh
        from tests.unit.test_haptica_por_radio_01_a_ponte_troca_de_modo import (
            _EndpointDeMentira,
        )

        self.servidor = ServidorDeSom()
        self.sinal = sinal
        self.canos: dict[str, int] = {}
        monkeypatch.setattr(af, "rodar_pactl", self.servidor)
        monkeypatch.setattr(af, "a_ponte_do_radio_pode_subir", lambda: (True, ""))
        monkeypatch.setattr(af, "fonte_do_monitor_do_no", self._fonte)
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
        self.sub._abrir_hidraw = self._abrir  # type: ignore[method-assign]
        self._controle = ControleNaLista

    def controles(self, ordem: tuple[str, ...] = MESA) -> list[Any]:
        return [
            self._controle(uniq=u, caminho=f"/dev/hidraw{10 + MESA.index(u)}", transporte="rádio")
            for u in ordem
        ]

    def _fonte(self, id_do_no: str, **kw: Any) -> tuple[Any, Any, str]:
        if kw.get("papel") == "haptica":
            uniq = id_do_no.removeprefix("endpoint::")
            return _fonte(self.sinal.get(uniq, [])), None, ""
        return (lambda _n: b""), None, ""

    def _abrir(self, caminho: str) -> int:
        leitura, escrita = os.pipe()
        self.canos[caminho] = leitura
        return escrita

    def o_jogo_abre(self) -> None:
        """O jogo abre um fluxo em cada um dos quatro endpoints — medido em 27/09."""
        for uniq in MESA:
            self.servidor.tocar(f"endpoint::{uniq}", JOGO)

    def mexer(self, *quem: str) -> None:
        from hefesto_dualsense4unix.daemon.subsystems.quem_mexe import quem_mexe_de

        marcas = quem_mexe_de(self.daemon)
        assert marcas is not None and marcas.jogo_aberto, "a partida não abriu"
        for uniq in quem:
            marcas.marcar(uniq)

    def reports_por_controle(self) -> dict[str, int]:
        """Espera as pontes terminarem (o jogo fechou o monitor) e conta o que foi ao fio."""
        for ponte in list(self.sub._pontes.values()):
            _esperar_a_corrida(ponte)
        contagem = {}
        for uniq in MESA:
            leitura = self.canos.pop(f"/dev/hidraw{10 + MESA.index(uniq)}", None)
            if leitura is None:
                contagem[uniq] = 0
                continue
            try:
                escrito = _ler_tudo(leitura)
            finally:
                os.close(leitura)
            assert len(escrito) % TAMANHO_032 == 0, "um report saiu cortado"
            contagem[uniq] = len(escrito) // TAMANHO_032
        return contagem

    def fechar(self) -> None:
        for ponte in list(self.sub._pontes.values()):
            ponte.descer(esperar_s=2.0)
        for leitura in self.canos.values():
            os.close(leitura)
        self.canos.clear()


@pytest.fixture
def mesa_de_quatro(monkeypatch: pytest.MonkeyPatch) -> Any:
    criadas: list[MesaDeQuatro] = []

    def _nova(sinal: dict[str, list[bytes]]) -> MesaDeQuatro:
        mesa = MesaDeQuatro(monkeypatch, sinal)
        criadas.append(mesa)
        return mesa

    yield _nova
    for mesa in criadas:
        mesa.fechar()


_ORDENS = list(__import__("itertools").permutations(MESA))


@pytest.mark.parametrize("ordem", _ORDENS, ids=["-".join(u[-1] for u in o) for o in _ORDENS])
def test_so_o_endpoint_com_sinal_manda_em_toda_ordem_de_conexao(
    mesa_de_quatro: Any, ordem: tuple[str, ...]
) -> None:
    """Quatro jogando, o jogo manda vibração só ao P3: só o P3 vai ao rádio.

    O sinal e o fio são do MESMO controle em toda ordem de conexão — o
    jogo vibra o controle que ele escolheu, e nenhum índice é privilegiado.

    MORDIDA: troque o critério por «o fluxo existe» (``_vale_mandar``
    devolvendo ``True``) — os três mudos mandam o silêncio do menu, bloco a
    bloco.
    """
    mudo = [SILENCIO] * 4
    mesa = mesa_de_quatro({P1: mudo, P2: mudo, P3: [SILENCIO, MOTOR, SILENCIO, SILENCIO], P4: mudo})
    mesa.o_jogo_abre()
    mesa.sub._casar_as_pontes(mesa.controles(ordem))
    assert mesa.sub._pontes == {}, "ninguém mexeu, e uma ponte subiu"
    mesa.mexer(*MESA)
    mesa.sub._casar_as_pontes(mesa.controles(ordem))
    assert sorted(mesa.sub._pontes) == sorted(MESA)
    assert mesa.reports_por_controle() == {P1: 0, P2: 0, P3: 2, P4: 0}


def test_o_jogo_que_espelha_vibra_so_quem_esta_com_o_controle_na_mao(mesa_de_quatro: Any) -> None:
    """A noite de 27/09: o PRAGMATA mandou a mesma vibração aos quatro. Vale a (b) dela.

    Um jogador (o P2, e não o P1: nenhum índice é privilegiado), os quatro no
    rádio, o sinal nos quatro endpoints — vibra quem mexeu desde que o jogo
    abriu. O controle parado na mão não vibra: é o limite escrito da (b).

    MORDIDA: tire ``este_joga`` da condição do modo em ``_casar_as_pontes`` —
    os quatro vibram o espelho.
    """
    tiro = [SILENCIO, MOTOR, MOTOR, SILENCIO]
    mesa = mesa_de_quatro({u: list(tiro) for u in MESA})
    mesa.o_jogo_abre()
    mesa.sub._casar_as_pontes(mesa.controles())
    mesa.mexer(P2)
    mesa.sub._casar_as_pontes(mesa.controles())
    assert sorted(mesa.sub._pontes) == [P2]
    assert mesa.reports_por_controle() == {P1: 0, P2: 3, P3: 0, P4: 0}


def test_no_menu_nenhum_report_vai_ao_radio(mesa_de_quatro: Any) -> None:
    """A prova 2 da sprint, na mesa de mentira: o jogo no menu, os quatro jogando.

    Os quatro fluxos existem, as quatro pontes escutam — e o fio fica vazio.
    """
    mesa = mesa_de_quatro({u: [SILENCIO] * 12 for u in MESA})
    mesa.o_jogo_abre()
    mesa.sub._casar_as_pontes(mesa.controles())
    mesa.mexer(*MESA)
    mesa.sub._casar_as_pontes(mesa.controles())
    assert sorted(mesa.sub._pontes) == sorted(MESA)
    assert mesa.reports_por_controle() == dict.fromkeys(MESA, 0)


# ---------------------------------------------------------------------------
# 4. A partida é o dono do fluxo
# ---------------------------------------------------------------------------


class TestAPartidaEODonoDoFluxo:
    def test_o_processo_auxiliar_da_steam_nao_abre_a_partida(
        self, mesa_de_quatro: Any, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Um ``run`` do GE-Proton com ``STEAM_COMPAT_DATA_PATH`` e sem fluxo: nada abre.

        Medido em 27/09: a partida abria e fechava três vezes antes de o jogo
        rodar, por um processo assim, e cada abertura zerava as marcas.

        MORDIDA: devolva a partida ao ``pids_de_jogo`` (abrir quando há
        processo com a variável do Proton) — ela abre com o auxiliar.
        """
        from hefesto_dualsense4unix.daemon.subsystems.quem_mexe import quem_mexe_de
        from hefesto_dualsense4unix.integrations import quem_o_jogo_le as qjl

        monkeypatch.setattr(qjl, "pids_de_jogo", lambda *_a, **_k: {5555})
        mesa = mesa_de_quatro({})
        mesa.sub._casar_as_pontes(mesa.controles())
        marcas = quem_mexe_de(mesa.daemon)
        assert marcas is not None
        assert marcas.jogo_aberto is False, "o processo auxiliar abriu a partida"
        mesa.o_jogo_abre()
        mesa.sub._casar_as_pontes(mesa.controles())
        assert marcas.jogo_aberto is True, "o fluxo do jogo no endpoint não abriu a partida"

    def test_donos_alternados_nao_zeram_a_marca(self) -> None:
        """Os donos A, B, A, B — os dois vivos: a marca de quem joga não zera.

        Das 00h12 às 05h21 de 27/09 foram 35 aberturas, e às 05h07 as quatro
        marcas do Sackboy zeraram no meio do jogo por um conjunto novo de pids.

        MORDIDA: devolva o ``agora.isdisjoint(antes)`` ao ``acompanhar_o_jogo``
        (dono novo sem nada em comum = outro jogo) — a marca zera na volta B.
        """
        from hefesto_dualsense4unix.daemon.subsystems.quem_mexe import QuemMexe

        marcas = QuemMexe()
        vivos = lambda donos: frozenset(donos)  # noqa: E731 - os dois seguem conectados
        marcas.acompanhar_o_jogo({"A"}, vivos=vivos)
        marcas.marcar(P1)
        for dono in ("B", "A", "B", "A", "B"):
            marcas.acompanhar_o_jogo({dono}, vivos=vivos)
            assert marcas.joga(P1), f"a marca zerou quando o dono virou {dono}"

    def test_o_dono_que_sai_e_o_outro_que_chega_e_outro_jogo(self) -> None:
        """Se nenhum dono de antes segue conectado, o dono novo é outro jogo."""
        from hefesto_dualsense4unix.daemon.subsystems.quem_mexe import QuemMexe

        marcas = QuemMexe()
        conectados = {"A"}
        vivos = lambda donos: frozenset(d for d in donos if d in conectados)  # noqa: E731
        marcas.acompanhar_o_jogo({"A"}, vivos=vivos)
        marcas.marcar(P1)
        conectados = {"B"}
        marcas.acompanhar_o_jogo({"B"}, vivos=vivos)
        assert marcas.jogo_aberto and not marcas.joga(P1), "a marca do jogo de antes valeu no novo"

    def test_o_jogo_que_fecha_o_fluxo_e_segue_vivo_e_a_mesma_partida(self) -> None:
        """O GE remira a háptica a cada hotplug de endpoint: o fluxo some e volta."""
        from hefesto_dualsense4unix.daemon.subsystems.quem_mexe import QuemMexe

        marcas = QuemMexe()
        vivos = lambda donos: frozenset(donos)  # noqa: E731
        marcas.acompanhar_o_jogo({"A"}, vivos=vivos)
        marcas.marcar(P3)
        marcas.acompanhar_o_jogo(set(), vivos=vivos)
        assert marcas.jogo_aberto and marcas.joga(P3)
        marcas.acompanhar_o_jogo(set(), vivos=lambda _d: frozenset())
        assert not marcas.jogo_aberto and not marcas.joga(P3), "o jogo fechou e a partida seguiu"

    def test_na_duvida_a_partida_nao_muda(self) -> None:
        from hefesto_dualsense4unix.daemon.subsystems.quem_mexe import QuemMexe

        marcas = QuemMexe()
        marcas.acompanhar_o_jogo({"A"}, vivos=lambda _d: None)
        marcas.marcar(P2)
        marcas.acompanhar_o_jogo({"B"}, vivos=lambda _d: None)
        marcas.acompanhar_o_jogo(set(), vivos=lambda _d: None)
        assert marcas.jogo_aberto and marcas.joga(P2)


# ---------------------------------------------------------------------------
# 5. O fluxo que nasce é avisado, e não caçado
# ---------------------------------------------------------------------------


class TestAVoltaAcordaPeloAviso:
    def test_quem_entra_na_partida_acorda_a_volta(self, mesa_de_quatro: Any) -> None:
        """O primeiro toque de um controle pede a volta — a ponte dele sobe na hora.

        MORDIDA: tire a chamada a ``ao_marcar`` de ``QuemMexe.marcar`` — a volta
        só vem com o relógio (5 s), e o primeiro tiro não vibra.
        """
        mesa = mesa_de_quatro({})
        mesa.sub._ouvir_quem_entra_na_partida(mesa.sub._acordar_a_volta)
        mesa.o_jogo_abre()
        mesa.sub._casar_as_pontes(mesa.controles())
        assert not mesa.sub._acordar.is_set()
        mesa.mexer(P4)
        assert mesa.sub._volta_pedida is True
        assert mesa.sub._acordar.is_set()

    def test_sem_mudanca_a_espera_nao_pergunta_nada_ao_servidor(
        self, mesa_de_quatro: Any, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A prova 5 da sprint, na régua: parado, o daemon não pergunta ao servidor.

        O vigia de 0,4 s perguntava duas vezes por fatia — 5 por segundo, e sem
        o retrato vivo eram `pactl` de verdade.

        MORDIDA: devolva a fatia (``acordar.wait(min(0.4, falta))`` seguido de
        ``_a_mesa_do_som_mudou()``) — as perguntas voltam.
        """
        import time

        from hefesto_dualsense4unix.daemon.subsystems import alto_falante as mod

        monkeypatch.setattr(mod, "RECONCILIA_S", 1.2)
        mesa = mesa_de_quatro({})
        mesa.o_jogo_abre()
        mesa.sub._casar_as_pontes(mesa.controles())
        mesa.sub._o_que_a_volta_viu = mesa.sub._o_que_a_mesa_do_som_diz()
        antes = len(mesa.servidor.perguntas)

        class _Ger:
            def dormir(self, _s: float) -> bool:
                return False

        inicio = time.monotonic()
        assert mesa.sub._esperar_a_mesa_do_som(_Ger()) is False
        assert time.monotonic() - inicio >= 1.0, "a espera voltou antes do relógio sem aviso"
        assert mesa.servidor.perguntas[antes:] == [], "a espera parada perguntou ao servidor"

    def test_a_tentativa_que_falhou_nao_prende_a_volta_num_laco(
        self, mesa_de_quatro: Any, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A ponte que não sobe (sem fonte) não faz a volta acordar de novo.

        A espera compara o que a volta LEU, e não o que ela conseguiu: uma
        falha não muda entrada nenhuma. Um aviso do retrato que chega (o
        endpoint que a própria volta publicou) é olhado uma vez, e só.

        MORDIDA: tire o ``acordar.clear()`` de ``_esperar_a_mesa_do_som`` — o
        aviso fica armado, e a espera gira olhando o servidor sem parar.
        """
        from hefesto_dualsense4unix.daemon.subsystems import alto_falante as mod

        monkeypatch.setattr(mod, "RECONCILIA_S", 0.5)
        mesa = mesa_de_quatro({})
        monkeypatch.setattr(
            af, "fonte_do_monitor_do_no", lambda _no, **_k: (None, None, "sem gravador")
        )
        mesa.o_jogo_abre()
        mesa.sub._casar_as_pontes(mesa.controles())
        mesa.mexer(P1)
        mesa.sub._o_que_a_volta_viu = mesa.sub._o_que_a_mesa_do_som_diz()
        mesa.sub._casar_as_pontes(mesa.controles())
        assert mesa.sub._pontes == {}, "sem fonte, a ponte subiu"
        olhadas: list[int] = []
        verdadeira = mesa.sub._a_mesa_do_som_mudou

        def _contada() -> bool:
            olhadas.append(1)
            return verdadeira()

        mesa.sub._a_mesa_do_som_mudou = _contada  # type: ignore[method-assign]
        mesa.sub._volta_pedida = False
        mesa.sub._acordar.set()

        class _Ger:
            def dormir(self, _s: float) -> bool:
                return False

        assert mesa.sub._esperar_a_mesa_do_som(_Ger()) is False
        assert len(olhadas) == 1, f"a falha prendeu a volta: {len(olhadas)} olhadas"
