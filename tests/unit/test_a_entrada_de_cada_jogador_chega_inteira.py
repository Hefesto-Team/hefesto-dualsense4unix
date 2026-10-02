"""A-ENTRADA-DE-CADA-JOGADOR-CHEGA-INTEIRA-01 — o que os programas mandam aos virtuais."""
from __future__ import annotations

import array
import contextlib
import fcntl
import errno
import itertools
import os
import statistics
import socket
import struct
import termios
import threading
import time
from collections.abc import Iterator
from typing import Any

import pytest
import structlog

from hefesto_dualsense4unix.daemon.subsystems.identity import prazo_do_lugar_guardado
from hefesto_dualsense4unix.integrations import uhid_gamepad
from hefesto_dualsense4unix.integrations.uhid_blueprint import canonical_blueprint
from hefesto_dualsense4unix.integrations.uhid_gamepad import (
    HID_MAX_DESCRIPTOR_SIZE,
    UHID_CLOSE,
    UHID_CREATE2,
    UHID_DESTROY,
    UHID_EVENT_SIZE,
    UHID_GET_REPORT,
    UHID_GET_REPORT_REPLY,
    UHID_OPEN,
    UHID_OUTPUT,
    UHID_START,
    UhidDualSense,
)
from hefesto_dualsense4unix.integrations.uinput_gamepad import UinputGamepad
from tests.unit.test_o_jogo_espera_a_carta_do_lugar_guardado import (
    TIQUE,
    config_isolado,  # noqa: F401 — o lar de mentira da bancada do item 3
)
from tests.unit.test_o_modo_tem_um_dono import FILA_DELA, TRANSPORTES, _a_mesa_do_boot
from tests.unit.test_o_pad_virtual_atende_a_vibracao_desde_que_nasce import (
    _UInputComoOPythonEvdev,
    evdev_de_mentira,  # noqa: F401 — o evdev de mentira da régua do pad Xbox
)
from tests.unit.test_vpad_ff_passthrough import _rumble_effect

UHID_BUFSIZE = 32

EVENTOS = 200
JANELA_S = 0.100

PRAZO_S = 0.25


class KernelDoUhid:
    """O lado do kernel do `/dev/uhid`: a fila de 32 lugares, e só."""

    def __init__(self) -> None:
        self.lado_do_kernel, self.lado_do_produto = socket.socketpair(
            socket.AF_UNIX, socket.SOCK_SEQPACKET
        )
        with contextlib.suppress(OSError):
            self.lado_do_kernel.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 1 << 22)
        self.lado_do_kernel.setblocking(False)
        self._trava = threading.Lock()
        self.cheia = 0
        self.enfileirados = 0
        self.destruido = False
        self.respostas_de_feature: dict[int, float] = {}
        self._pare = threading.Event()
        self._fio = threading.Thread(target=self._ler_o_produto, daemon=True)
        self._fio.start()


    def _ler_o_produto(self) -> None:
        while not self._pare.is_set():
            try:
                dado = self.lado_do_kernel.recv(UHID_EVENT_SIZE + 64)
            except BlockingIOError:
                time.sleep(0.0005)
                continue
            except OSError:
                return
            if len(dado) < 4:
                continue
            tipo = struct.unpack("<I", dado[:4])[0]
            if tipo == UHID_CREATE2:
                self.enfileirar(struct.pack("<I", UHID_START))
                self.enfileirar(struct.pack("<I", UHID_OPEN))
            elif tipo == UHID_DESTROY:
                self.destruido = True
            elif tipo == UHID_GET_REPORT_REPLY:
                pedido = struct.unpack("<I", dado[4:8])[0]
                self.respostas_de_feature.setdefault(pedido, time.monotonic())


    def pendentes(self) -> int:
        """Quantos eventos o produto ainda não leu (o `FIONREAD` soma o SEQPACKET)."""
        conta = array.array("i", [0])
        fcntl.ioctl(self.lado_do_produto.fileno(), termios.FIONREAD, conta)
        return conta[0] // UHID_EVENT_SIZE

    def enfileirar(self, evento: bytes) -> bool:
        """O `uhid_queue`: entra se couber, e o que não cabe é descartado."""
        with self._trava:
            if self.pendentes() >= UHID_BUFSIZE - 1:
                self.cheia += 1
                return False
            try:
                self.lado_do_kernel.send(evento.ljust(UHID_EVENT_SIZE, b"\0"))
            except BlockingIOError:
                self.cheia += 1
                return False
            self.enfileirados += 1
            return True

    def fd_do_produto(self) -> int:
        return os.dup(self.lado_do_produto.fileno())

    def fechar(self) -> None:
        self._pare.set()
        self._fio.join(timeout=1.0)
        for lado in (self.lado_do_kernel, self.lado_do_produto):
            with contextlib.suppress(OSError):
                lado.close()


class Relogio:
    """O relógio do virtual (`time_fn`): a graça da réplica anda sem `sleep`."""

    def __init__(self) -> None:
        self.t = 1000.0

    def __call__(self) -> float:
        return self.t

    def avancar(self, segundos: float) -> None:
        self.t += segundos


def _evento_de_saida(report: bytes) -> bytes:
    """`struct uhid_output_req { __u8 data[4096]; __u16 size; __u8 rtype; }`."""
    evento = struct.pack("<I", UHID_OUTPUT)
    evento += report.ljust(HID_MAX_DESCRIPTOR_SIZE, b"\0")[:HID_MAX_DESCRIPTOR_SIZE]
    evento += struct.pack("<HB", len(report), 1)
    return evento


def _vibracao(fraco: int, forte: int) -> bytes:
    """O report 0x02 de vibração que o `hid_playstation` monta (firmware v2)."""
    corpo = bytearray(47)
    corpo[0] = 0x02
    corpo[2] = fraco
    corpo[3] = forte
    return bytes([0x02]) + bytes(corpo)


def _luz(r: int, g: int, b: int) -> bytes:
    """O report 0x02 de luz (valid_flag1 = LIGHTBAR_CONTROL_ENABLE)."""
    corpo = bytearray(47)
    corpo[1] = 0x04
    corpo[44], corpo[45], corpo[46] = r, g, b
    return bytes([0x02]) + bytes(corpo)


def _pedido_de_feature(pedido: int, numero: int) -> bytes:
    """`struct uhid_get_report_req { __u32 id; __u8 rnum; __u8 rtype; }`."""
    return struct.pack("<IIBB", UHID_GET_REPORT, pedido, numero, 0)


@pytest.fixture
def kernel(monkeypatch: pytest.MonkeyPatch) -> Iterator[KernelDoUhid]:
    """O `/dev/uhid` de mentira: o `os.open` do nó devolve o lado do produto."""
    k = KernelDoUhid()
    abrir = os.open

    def _abrir(caminho: Any, flags: int, *args: Any, **kwargs: Any) -> int:
        if os.fsdecode(caminho) == uhid_gamepad.UHID_NODE:
            return k.fd_do_produto()
        return abrir(caminho, flags, *args, **kwargs)

    monkeypatch.setattr(os, "open", _abrir)
    try:
        yield k
    finally:
        k.fechar()


class Fisico:
    """Os sinks do controle físico, com a thread de cada entrega anotada."""

    def __init__(self) -> None:
        self.vibracao: list[tuple[int, int]] = []
        self.luz: list[tuple[int, int, int]] = []
        self.fins_de_sessao = 0
        self.fios: set[int] = set()

    def sinks(self) -> dict[str, Any]:
        def _vib(fraco: int, forte: int) -> None:
            self.fios.add(threading.get_ident())
            self.vibracao.append((fraco, forte))

        def _luz(r: int, g: int, b: int) -> None:
            self.fios.add(threading.get_ident())
            self.luz.append((r, g, b))

        def _fim() -> None:
            self.fios.add(threading.get_ident())
            self.fins_de_sessao += 1

        return {"rumble_sink": _vib, "lightbar_sink": _luz, "session_end_sink": _fim}


def _virtual(relogio: Relogio, fisico: Fisico | None = None) -> UhidDualSense:
    """O virtual do P2, nascido pelo caminho do produto, e esperado até o bind."""
    pad = UhidDualSense(
        player=2,
        blueprint=canonical_blueprint(),
        time_fn=relogio,
        **(fisico.sinks() if fisico is not None else {}),
    )
    assert pad.start() is True
    inicio = time.monotonic()
    while not pad.is_bound and time.monotonic() - inicio < 1.0:
        pad.pump_ff()
        time.sleep(0.002)
    assert pad.is_bound, "o virtual não fez bind no kernel de mentira"
    relogio.avancar(1.0)
    return pad


def _esperar(condicao: Any, prazo_s: float) -> float:
    inicio = time.monotonic()
    while not condicao() and time.monotonic() - inicio < prazo_s:
        time.sleep(0.001)
    return time.monotonic() - inicio


def test_duzentos_eventos_sem_tique_nenhum_cai(kernel: KernelDoUhid) -> None:
    """A régua da sprint: 200 eventos de saída em ~100 ms sem tique de entrada."""
    pad = _virtual(Relogio())
    try:
        inicio = time.monotonic()
        for n in range(EVENTOS):
            kernel.enfileirar(_evento_de_saida(_vibracao(n % 256, 0)))
            time.sleep(JANELA_S / EVENTOS)
        durou = time.monotonic() - inicio
        _esperar(lambda: pad.output_count >= EVENTOS, 1.0)
        assert kernel.cheia == 0, (
            f"o kernel descartou {kernel.cheia} de {EVENTOS} eventos em "
            f"{durou * 1000:.0f} ms («Output queue is full»): a saída que o jogo "
            "manda esperava o tique do repasse da entrada"
        )
        assert pad.output_count == EVENTOS, (
            f"o virtual atendeu {pad.output_count} de {EVENTOS} sem tique"
        )
    finally:
        pad.stop()


def test_o_pedido_de_feature_e_respondido_sem_tique(kernel: KernelDoUhid) -> None:
    """O jogo pede um feature report (0x09) e fica parado até a resposta."""
    pad = _virtual(Relogio())
    try:
        pedido = 77
        pediu_em = time.monotonic()
        assert kernel.enfileirar(_pedido_de_feature(pedido, 0x09))
        _esperar(lambda: pedido in kernel.respostas_de_feature, PRAZO_S)
        assert pedido in kernel.respostas_de_feature, (
            "o pedido de feature do jogo ficou sem resposta sem o tique"
        )
        assert kernel.respostas_de_feature[pedido] - pediu_em < PRAZO_S
    finally:
        pad.stop()


def test_a_entrega_ao_fisico_segue_no_tique(kernel: KernelDoUhid) -> None:
    """O fio atende; quem fala com o controle físico é o tique, com o dedup de sempre."""
    fisico = Fisico()
    relogio = Relogio()
    pad = _virtual(relogio, fisico)
    try:
        for fraco in (10, 20, 30):
            kernel.enfileirar(_evento_de_saida(_vibracao(fraco, 5)))
        kernel.enfileirar(_evento_de_saida(_luz(1, 2, 3)))
        _esperar(lambda: pad.output_count >= 4, 1.0)
        assert pad.output_count == 4
        assert fisico.vibracao == [], "o fio do virtual falou com o controle físico"
        assert fisico.luz == []

        pad.pump_ff()

        assert fisico.vibracao == [(30, 5)], (
            f"o tique não entregou o último pedido: {fisico.vibracao}"
        )
        assert fisico.luz == [(1, 2, 3)]
        assert fisico.fios == {threading.get_ident()}, (
            "o controle físico ouviu de outra thread que não a do tique"
        )
        pad.pump_ff()
        assert fisico.vibracao == [(30, 5)]
    finally:
        pad.stop()


def test_o_stop_encerra_o_fio_antes_de_fechar(kernel: KernelDoUhid) -> None:
    """O fio do virtual sai antes do fd fechar, e o kernel recebe o `UHID_DESTROY`."""
    pad = _virtual(Relogio())
    fio = pad._fio_do_uhid
    assert fio is not None and fio.is_alive(), "o virtual nasceu sem o fio que o atende"
    pad.stop()
    assert not fio.is_alive()
    assert pad._fio_do_uhid is None
    _esperar(lambda: kernel.destruido, 1.0)
    assert kernel.destruido


def test_o_dublê_sem_fd_de_verdade_segue_no_tique(monkeypatch: pytest.MonkeyPatch) -> None:
    """Sem descritor de verdade (os dublês da suíte), o tique atende, como antes."""
    lidos: list[bytes] = [struct.pack("<I", UHID_START)]
    monkeypatch.setattr(os, "open", lambda *_a, **_k: 4242)
    monkeypatch.setattr(os, "close", lambda _fd: None)
    monkeypatch.setattr(os, "set_blocking", lambda _fd, _b: None)
    monkeypatch.setattr(os, "write", lambda _fd, dado: len(dado))

    def _ler(_fd: int, _tamanho: int) -> bytes:
        if not lidos:
            raise BlockingIOError
        return lidos.pop(0)

    monkeypatch.setattr(os, "read", _ler)
    pad = UhidDualSense(player=3, blueprint=canonical_blueprint())
    assert pad.start() is True
    try:
        assert pad._fio_do_uhid is None
        pad.pump_ff()
        assert pad.is_bound
    finally:
        pad.stop()


def _o_jogo_fecha(kernel: KernelDoUhid, pad: UhidDualSense) -> None:
    """O jogo fecha o hidraw do virtual: o `UHID_CLOSE`, atendido pelo fio."""
    assert kernel.enfileirar(struct.pack("<I", UHID_CLOSE))
    _esperar(lambda: not pad.game_open, 1.0)
    assert not pad.game_open, "o fio não atendeu o CLOSE"


def test_o_fim_da_sessao_e_a_parada_vao_ao_fisico_no_tique(kernel: KernelDoUhid) -> None:
    """O jogo fecha com o motor girando: a parada e o perfil voltam ao físico no tique."""
    fisico = Fisico()
    pad = _virtual(Relogio(), fisico)
    try:
        kernel.enfileirar(_evento_de_saida(_vibracao(200, 100)))
        kernel.enfileirar(_evento_de_saida(_luz(1, 2, 3)))
        _esperar(lambda: pad.output_count >= 2, 1.0)
        pad.pump_ff()
        assert fisico.vibracao == [(200, 100)]
        assert fisico.luz == [(1, 2, 3)]

        _o_jogo_fecha(kernel, pad)
        assert fisico.vibracao == [(200, 100)], "o fio parou o motor sem o tique"
        assert fisico.fins_de_sessao == 0, "o fio devolveu o perfil sem o tique"

        pad.pump_ff()
        assert fisico.vibracao[-1] == (0, 0), (
            f"o jogo fechou com o motor girando e o tique não o parou: {fisico.vibracao}"
        )
        assert fisico.fins_de_sessao == 1, "o perfil não voltou ao físico"
        assert fisico.fios == {threading.get_ident()}
        pad.pump_ff()
        assert fisico.fins_de_sessao == 1
    finally:
        pad.stop()


def test_o_stop_entrega_o_que_o_fio_atendeu(kernel: KernelDoUhid) -> None:
    """O jogo fecha e o virtual morre antes do tique: o perfil volta e o motor para."""
    fisico = Fisico()
    pad = _virtual(Relogio(), fisico)
    try:
        kernel.enfileirar(_evento_de_saida(_luz(4, 5, 6)))
        _esperar(lambda: pad.output_count >= 1, 1.0)
        pad.pump_ff()
        assert fisico.luz == [(4, 5, 6)]
        kernel.enfileirar(_evento_de_saida(_vibracao(50, 60)))
        _esperar(lambda: pad.output_count >= 2, 1.0)
        _o_jogo_fecha(kernel, pad)
    finally:
        pad.stop()
    assert fisico.fins_de_sessao == 1, "o fim da sessão morreu com o virtual"
    assert fisico.vibracao[-1:] == [(0, 0)], f"o motor ficou girando: {fisico.vibracao}"
    assert fisico.fios == {threading.get_ident()}


def test_o_stop_nao_espera_o_prazo_do_fio(kernel: KernelDoUhid) -> None:
    """O `stop` acorda o fio na hora: o laço não para esperando o prazo do `poll`."""
    pad = _virtual(Relogio())
    kernel.enfileirar(_evento_de_saida(_luz(7, 8, 9)))
    _esperar(lambda: pad.output_count >= 1, 1.0)
    inicio = time.monotonic()
    pad.stop()
    durou = time.monotonic() - inicio
    assert durou < PRAZO_S, f"o stop esperou {durou * 1000:.0f} ms pelo fio do virtual"


@pytest.fixture
def quatro_kernels(monkeypatch: pytest.MonkeyPatch) -> Iterator[list[KernelDoUhid]]:
    """Um `/dev/uhid` de mentira por virtual: cada `open` do nó é um kernel novo."""
    kernels: list[KernelDoUhid] = []
    abrir = os.open

    def _abrir(caminho: Any, flags: int, *args: Any, **kwargs: Any) -> int:
        if os.fsdecode(caminho) == uhid_gamepad.UHID_NODE:
            k = KernelDoUhid()
            kernels.append(k)
            return k.fd_do_produto()
        return abrir(caminho, flags, *args, **kwargs)

    monkeypatch.setattr(os, "open", _abrir)
    try:
        yield kernels
    finally:
        for k in kernels:
            k.fechar()


def test_os_quatro_virtuais_atendem_ao_mesmo_tempo(quatro_kernels: list[KernelDoUhid]) -> None:
    """Os quatro jogadores, cada um com o seu virtual: 200 eventos a cada um, sem tique."""
    pads: list[UhidDualSense] = []
    try:
        for jogador in (1, 2, 3, 4):
            pad = UhidDualSense(
                player=jogador, blueprint=canonical_blueprint(), time_fn=Relogio()
            )
            assert pad.start() is True
            pads.append(pad)
        for pad in pads:
            _esperar(lambda pad=pad: pad.is_bound, 1.0)
            assert pad.is_bound, f"o virtual do P{pad.player} não fez bind"
        assert len({pad.mac for pad in pads}) == 4
        for n in range(EVENTOS):
            for k in quatro_kernels:
                k.enfileirar(_evento_de_saida(_vibracao(n % 256, 1)))
            time.sleep(JANELA_S / EVENTOS)
        for pad in pads:
            _esperar(lambda pad=pad: pad.output_count >= EVENTOS, 1.0)
        perdas = {pad.player: k.cheia for pad, k in zip(pads, quatro_kernels, strict=True)}
        assert perdas == {1: 0, 2: 0, 3: 0, 4: 0}, (
            f"o kernel descartou a saída de algum jogador (P -> descartados): {perdas}"
        )
        assert [pad.output_count for pad in pads] == [EVENTOS] * 4
    finally:
        for pad in pads:
            pad.stop()


def test_sem_descritor_para_o_despertador_o_tique_drena(
    kernel: KernelDoUhid, monkeypatch: pytest.MonkeyPatch
) -> None:
    """O processo sem descritor livre: o virtual nasce mesmo assim, e o tique atende."""

    def _sem_descritor() -> tuple[int, int]:
        raise OSError(errno.EMFILE, "Too many open files")

    monkeypatch.setattr(os, "pipe", _sem_descritor)
    pad = _virtual(Relogio())
    try:
        assert pad._fio_do_uhid is None
        pedido = 91
        assert kernel.enfileirar(_pedido_de_feature(pedido, 0x09))
        time.sleep(0.02)
        pad.pump_ff()
        _esperar(lambda: pedido in kernel.respostas_de_feature, PRAZO_S)
        assert pedido in kernel.respostas_de_feature, "o tique não atendeu o pedido"
    finally:
        pad.stop()


def test_sem_fio_novo_o_virtual_nasce_e_nao_vaza_o_despertador(
    kernel: KernelDoUhid, monkeypatch: pytest.MonkeyPatch
) -> None:
    """O processo no teto de fios: o virtual nasce, o tique atende e o pipe fecha."""
    iniciar = threading.Thread.start
    pipes: list[tuple[int, int]] = []
    criar_pipe = os.pipe

    def _pipe() -> tuple[int, int]:
        par = criar_pipe()
        pipes.append(par)
        return par

    def _start(fio: threading.Thread) -> None:
        if fio.name.startswith("hefesto-uhid-"):
            raise RuntimeError("can't start new thread")
        iniciar(fio)

    monkeypatch.setattr(os, "pipe", _pipe)
    monkeypatch.setattr(threading.Thread, "start", _start)
    pad = _virtual(Relogio())
    try:
        assert pad._fio_do_uhid is None
        assert pipes, "premissa: o despertador chegou a nascer"
        for ponta in pipes[-1]:
            with pytest.raises(OSError):
                os.fstat(ponta)
    finally:
        pad.stop()


def test_dois_stops_ao_mesmo_tempo_fecham_o_despertador_uma_vez(
    kernel: KernelDoUhid, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A interface e o laço derrubam o mesmo virtual juntos: cada ponta fecha uma vez."""
    fechar = os.close
    fechados: list[int] = []

    def _close(fd: int) -> None:
        fechados.append(fd)
        fechar(fd)

    monkeypatch.setattr(os, "close", _close)
    for _volta in range(8):
        pad = _virtual(Relogio())
        despertador = pad._despertador
        assert despertador is not None
        largada = threading.Barrier(2)

        def _parar(pad: UhidDualSense = pad, largada: threading.Barrier = largada) -> None:
            largada.wait()
            pad.stop()

        dupla = [threading.Thread(target=_parar) for _ in range(2)]
        fechados.clear()
        for fio in dupla:
            fio.start()
        for fio in dupla:
            fio.join(timeout=5.0)
        vezes = {ponta: fechados.count(ponta) for ponta in despertador}
        assert vezes == dict.fromkeys(despertador, 1), (
            f"o despertador fechou {vezes} vezes (ponta -> closes) com dois stops juntos"
        )


@pytest.mark.usefixtures("evdev_de_mentira")
def test_o_pad_xbox_responde_o_efeito_antes_de_5_ms() -> None:
    """A régua da sprint para o pad Xbox: o envio de efeito, sem tique, antes de 5 ms."""
    pad = UinputGamepad.for_flavor("xbox", rumble_sink=lambda _w, _s: None)
    assert pad.start() is True
    aparelho = _UInputComoOPythonEvdev.instancias[0]
    esperas: list[float] = []
    try:
        for n in range(21):
            inicio = time.monotonic()
            aparelho.o_jogo_manda_um_efeito(
                _rumble_effect(0, strong=0x8000, weak=0x4000), request_id=100 + n
            )
            while len(aparelho.uploads_feitos) <= n and time.monotonic() - inicio < PRAZO_S:
                time.sleep(0.0001)
            assert len(aparelho.uploads_feitos) > n, (
                "o envio de efeito ficou sem resposta sem o tique"
            )
            esperas.append(time.monotonic() - inicio)
    finally:
        pad.stop()
    mediana = statistics.median(esperas)
    assert mediana < 0.005, f"o pad Xbox respondeu em {mediana * 1000:.1f} ms (mediana)"


# `vpad_indice`). O alarme que a régua lê é o do PRODUTO: o `nome_divergente`
# da `CoopManager.mesa()`, o mesmo que o `state_full` publica.

_PASSA_O_PRAZO = 3 + int(prazo_do_lugar_guardado() // TIQUE)

_ORDENS = [
    ordem for quantos in (2, 3, 4) for ordem in itertools.permutations(FILA_DELA[:quantos])
]


def _nomes_errados(bancada: Any) -> list[dict[str, Any]]:
    """Os itens da mesa em que o número no nome do vpad não é o número de agora."""
    return [item for item in bancada.coop.mesa() if item["nome_divergente"]]


def _vivos(bancada: Any) -> set[int]:
    return {id(v) for v in bancada.vpads if v.vivo}


@pytest.mark.usefixtures("config_isolado")
@pytest.mark.parametrize("transporte", sorted(TRANSPORTES))
@pytest.mark.parametrize(
    "chegada", _ORDENS, ids=["-".join(u[-1] for u in o) for o in _ORDENS]
)
def test_com_o_jogo_solto_o_nome_e_o_numero(
    monkeypatch: pytest.MonkeyPatch, chegada: tuple[str, ...], transporte: str
) -> None:
    """Sem jogo, em toda ordem de chegada: o nome de cada vpad é o número dele."""
    bancada = _a_mesa_do_boot(monkeypatch, chegada, jogo=False, transporte=transporte)
    for _ in range(6):
        bancada.tique()
    assert _nomes_errados(bancada) == [], "premissa: a mesa nasce com os nomes certos"

    bancada.mesa.levantar(FILA_DELA[0])
    for _ in range(_PASSA_O_PRAZO):
        bancada.tique()
    assert _nomes_errados(bancada) == [], (
        "a fila andou e o vpad seguiu com o número de quando nasceu"
    )

    bancada.mesa.sentar(FILA_DELA[0], transporte=transporte)
    for _ in range(6):
        bancada.tique()
    assert _nomes_errados(bancada) == []


@pytest.mark.usefixtures("config_isolado")
def test_o_nome_espera_a_mesa_assentar(monkeypatch: pytest.MonkeyPatch) -> None:
    """Quem ficou renasce UMA vez pelo nome, e só com a mesa assentada."""
    bancada = _a_mesa_do_boot(monkeypatch, FILA_DELA, jogo=False)
    for _ in range(6):
        bancada.tique()
    nascidos = len(bancada.vpads)

    bancada.mesa.levantar(FILA_DELA[0])
    for _ in range(_PASSA_O_PRAZO):
        bancada.tique()
    assert len(bancada.vpads) - nascidos == 2, "a saída da carta 1: o roxo e o azul"

    nascidos = len(bancada.vpads)
    bancada.mesa.sentar(FILA_DELA[0])
    for _ in range(6):
        bancada.tique()
    assert len(bancada.vpads) - nascidos == 3, (
        "a volta: o vermelho, e o roxo e o azul uma vez só"
    )
    assert _nomes_errados(bancada) == []


@pytest.mark.usefixtures("config_isolado")
@pytest.mark.parametrize("quem", ["posto", "secundário"])
def test_com_o_jogo_segurando_nenhum_virtual_renasce_pelo_nome(
    monkeypatch: pytest.MonkeyPatch, quem: str
) -> None:
    """Com o jogo na autoridade, o nome velho espera; o jogo solta, e ele renasce."""
    bancada = _a_mesa_do_boot(monkeypatch, FILA_DELA, jogo=True)
    for _ in range(6):
        bancada.tique()
    assert _nomes_errados(bancada) == []
    alvo = bancada.daemon._gamepad_device if quem == "posto" else bancada.vpad_de(FILA_DELA[2])
    alvo.player = 4 if quem == "posto" else 2
    assert _nomes_errados(bancada), "premissa: o nome velho aparece no alarme"
    vivos = _vivos(bancada)

    for _ in range(4):
        bancada.tique()
    assert _vivos(bancada) == vivos, "um vpad renasceu com o jogo segurando"
    assert alvo.vivo

    bancada.daemon.display_authority = "daemon"
    for _ in range(3):
        bancada.tique()
    assert not alvo.vivo, "o jogo soltou e o vpad seguiu com o nome velho"
    assert _nomes_errados(bancada) == []


@pytest.mark.usefixtures("config_isolado")
@pytest.mark.parametrize("transporte", sorted(TRANSPORTES))
@pytest.mark.parametrize("quem_sai", range(4), ids=["carta-1", "carta-2", "carta-3", "carta-4"])
def test_qualquer_carta_que_sai_deixa_os_nomes_certos(
    monkeypatch: pytest.MonkeyPatch, quem_sai: int, transporte: str
) -> None:
    """Sem jogo, a mesa dela inteira, e sai qualquer um dos quatro (não só a carta 1)."""
    bancada = _a_mesa_do_boot(monkeypatch, FILA_DELA, jogo=False, transporte=transporte)
    for _ in range(6):
        bancada.tique()
    assert _nomes_errados(bancada) == [], "premissa: a mesa nasce com os nomes certos"

    saiu = FILA_DELA[quem_sai]
    bancada.mesa.levantar(saiu)
    for _ in range(_PASSA_O_PRAZO):
        bancada.tique()
    assert _nomes_errados(bancada) == [], (
        f"a carta {quem_sai + 1} saiu e quem ficou seguiu com o número de quando nasceu"
    )

    bancada.mesa.sentar(saiu, transporte=TRANSPORTES[transporte][quem_sai])
    for _ in range(6):
        bancada.tique()
    assert _nomes_errados(bancada) == []


@pytest.mark.usefixtures("config_isolado")
def test_cada_episodio_do_nome_velho_vai_ao_diario(monkeypatch: pytest.MonkeyPatch) -> None:
    """A carta 1 sai duas vezes na mesma vida do daemon: o diário diz as duas."""
    bancada = _a_mesa_do_boot(monkeypatch, FILA_DELA, jogo=False)
    for _ in range(6):
        bancada.tique()
    por_saida: list[int] = []
    for _volta in range(2):
        with structlog.testing.capture_logs() as diario:
            bancada.mesa.levantar(FILA_DELA[0])
            for _ in range(_PASSA_O_PRAZO):
                bancada.tique()
        por_saida.append(
            sum(1 for r in diario if r["event"] == "coop_nome_do_virtual_renasce")
        )
        assert _nomes_errados(bancada) == []
        bancada.mesa.sentar(FILA_DELA[0])
        for _ in range(6):
            bancada.tique()
    assert por_saida == [1, 1], f"linhas do diário por saída da carta 1: {por_saida}"
