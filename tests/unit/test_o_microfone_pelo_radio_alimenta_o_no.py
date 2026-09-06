"""O RÁDIO alimenta o nó com nome de CONTROLE — ONDA5-MIC-VIRTUAL-02.

O que a ONDA5-MIC-VIRTUAL-01 fez pelo cabo, aqui pelo rádio: o microfone
daquele controle passa a ter UM nome só — ``hefesto_mic_<hex6>`` — nos dois
transportes, alimentado pela MESMA
:meth:`~hefesto_dualsense4unix.integrations.dualsense_bt_audio.SourceVirtualPipeWire.escrever`.

**NENHUM TESTE DESTE ARQUIVO FALA COM O PIPEWIRE DELA.** O `pactl` é dublado
por :class:`_PactlDeMentira`, que faz o que o `module-pipe-source` faria — cria
o fifo e segura a ponta de LEITURA — para que a classe de produção seja
exercitada inteira, do `load-module` ao byte que sai do outro lado. Um dublê
mais frouxo que o mecanismo real já deu verde sobre nada três vezes nesta casa;
este é mais fiel de propósito.

OS ENDEREÇOS SÃO SINTÉTICOS E MASCARADOS. Octetos 4 e 5 zerados, que é a
máscara da casa — e há DOIS portões com réguas diferentes de propósito
(``test_docs_mac_anonimato.py`` por OUI, ``check_endereco_de_radio.py`` por
FORMA).
"""

from __future__ import annotations

import ast
import contextlib
import os
import shlex
import socket
import threading
import time
from pathlib import Path

import pytest

from hefesto_dualsense4unix.integrations import canal_do_microfone as canal
from hefesto_dualsense4unix.integrations import dualsense_bt_audio as bt
from hefesto_dualsense4unix.integrations import fontes_de_captura as fc

RAIZ = Path(__file__).resolve().parents[2]
SRC = RAIZ / "src" / "hefesto_dualsense4unix"

#: Quatro controles, quatro endereços — sintéticos, com a máscara da casa.
P1 = "aa:bb:cc:00:00:01"
P2 = "aa:bb:cc:00:00:02"
P3 = "aa:bb:cc:00:00:03"
P4 = "aa:bb:cc:00:00:04"
OS_QUATRO = (P1, P2, P3, P4)


# ---------------------------------------------------------------------------
# Os dublês — e eles são fiéis de propósito
# ---------------------------------------------------------------------------


class _PactlDeMentira:
    """O `pactl` que o `SourceVirtualPipeWire` chama — sem servidor de som.

    Ele faz o que o `module-pipe-source` faz e que a classe de produção DEPENDE
    que alguém faça: **cria o fifo e mantém a ponta de leitura aberta.** Sem
    isso o ``os.open(..., O_WRONLY | O_NONBLOCK)`` do produto daria ENXIO, o
    `iniciar()` recuaria, e a régua mediria o caminho de falha achando que mede
    o de sucesso.

    Ele também responde ao ``list sources short`` com o ESTADO que o teste
    escolher, na forma exata do servidor: cinco campos separados por TAB, com o
    formato (``s16le 1ch 48000Hz``) carregando espaços dentro do quarto campo —
    que é o detalhe que quebrou a primeira leitura deste módulo.
    """

    def __init__(self, estado: str = "SUSPENDED") -> None:
        self.estado = estado
        self.chamadas: list[list[str]] = []
        self.nos: dict[str, int] = {}
        self._proximo_id = 40

    def __call__(self, argv: list[str]) -> str | None:
        self.chamadas.append(list(argv))
        if len(argv) > 1 and argv[1] == "load-module":
            return self._carregar(argv)
        if argv[:4] == ["pactl", "list", "sources", "short"]:
            return self._listar()
        if len(argv) > 1 and argv[1] == "unload-module":
            return ""
        return ""

    def _carregar(self, argv: list[str]) -> str:
        nome = _valor(argv, "source_name=")
        caminho = _valor(argv, "file=")
        os.mkfifo(caminho)
        self.nos[nome] = os.open(caminho, os.O_RDONLY | os.O_NONBLOCK)
        self._proximo_id += 1
        return f"{self._proximo_id}\n"

    def _listar(self) -> str:
        return "\n".join(
            f"{600 + i}\t{nome}\tPipeWire\ts16le 1ch 48000Hz\t{self.estado}"
            for i, nome in enumerate(sorted(self.nos))
        )

    def colher(self, nome: str, quantos: int = 65536) -> bytes:
        """O que saiu do outro lado do fifo — o áudio, como um app o receberia."""
        try:
            return os.read(self.nos[nome], quantos)
        except BlockingIOError:
            return b""

    def fechar(self) -> None:
        for fd in self.nos.values():
            with contextlib.suppress(OSError):
                os.close(fd)
        self.nos.clear()


def _valor(argv: list[str], chave: str) -> str:
    for arg in argv:
        if arg.startswith(chave):
            return arg[len(chave) :]
    raise AssertionError(f"o `load-module` foi montado sem {chave!r}: {argv}")


class _DecodadorFixo:
    """Devolve sempre o mesmo PCM — o teste mede o CAMINHO, não a libopus."""

    PCM = bytes(range(256)) * 4

    def __init__(self) -> None:
        self.quadros: list[bytes] = []

    def decodificar(self, quadro: bytes) -> bytes:
        self.quadros.append(quadro)
        return self.PCM

    def close(self) -> None:
        return None


class _ParDeSockets:
    """Um hidraw de mentira: o teste emite reports, a ponte lê e escreve."""

    def __init__(self) -> None:
        self.nosso, self.controle = socket.socketpair(
            socket.AF_UNIX, socket.SOCK_SEQPACKET
        )
        self.escritos: list[bytes] = []
        self._parar = threading.Event()
        self._thread = threading.Thread(target=self._coletar, daemon=True)
        self._thread.start()

    def opener(self, _caminho: str) -> int:
        return os.dup(self.nosso.fileno())

    def emitir(self, report: bytes) -> None:
        self.controle.sendall(report)

    def _coletar(self) -> None:
        self.controle.settimeout(0.05)
        while not self._parar.is_set():
            try:
                dado = self.controle.recv(4096)
            except (TimeoutError, OSError):
                continue
            if not dado:
                return
            self.escritos.append(dado)

    def pedidos_de_mic(self) -> list[int]:
        """Só o byte que liga/desliga, de cada 0x32 escrito no controle."""
        return [
            w[4]
            for w in self.escritos
            if len(w) == bt.AUDIO_OUTPUT_REPORT_LEN and w[0] == bt.AUDIO_OUTPUT_REPORT_ID
        ]

    def fechar(self) -> None:
        self._parar.set()
        self._thread.join(timeout=1.0)
        self.nosso.close()
        self.controle.close()


def _report_de_audio(quadro: bytes) -> bytes:
    """Um 0x31 com carga de ÁUDIO, com o CRC certo — como o rádio o entrega."""
    raw = bytearray(bt.INPUT_REPORT_BT_SIZE)
    raw[0] = bt.INPUT_REPORT_BT
    raw[1] = bt.INPUT_FLAG_AUDIO
    raw[bt.MIC_OPUS_OFFSET : bt.MIC_OPUS_OFFSET + bt.MIC_OPUS_LEN] = quadro
    crc = bt.bt_crc32(bytes(raw[:74]), seed=bt.BT_INPUT_CRC_SEED)
    raw[74:78] = crc.to_bytes(4, "little")
    return bytes(raw)


def _esperar(cond, prazo: float = 3.0) -> bool:  # type: ignore[no-untyped-def]
    fim = time.monotonic() + prazo
    while time.monotonic() < fim:
        if cond():
            return True
        time.sleep(0.01)
    return False


@pytest.fixture()
def pactl(monkeypatch: pytest.MonkeyPatch):  # type: ignore[no-untyped-def]
    """O `pactl` dublado, com o `which` que o produto consulta antes de chamar."""
    import shutil

    falso = _PactlDeMentira()
    monkeypatch.setattr(shutil, "which", lambda cmd: f"/usr/bin/{cmd}")
    monkeypatch.setattr(bt, "_rodar", falso)
    # `desmutar` do dono do canal roda um `pactl` PRÓPRIO. Sem este dublê ele
    # lançaria subprocesso de verdade contra o servidor de som dela.
    monkeypatch.setattr(canal, "_rodar_pactl", lambda argv: True)
    monkeypatch.setattr(
        canal,
        "SourceVirtualPipeWire",
        lambda **kw: bt.SourceVirtualPipeWire(runner=falso, **kw),
    )
    yield falso
    for uniq in list(canal.de_pe()):
        canal.fechar(uniq)
    falso.fechar()


@pytest.fixture()
def par():  # type: ignore[no-untyped-def]
    p = _ParDeSockets()
    yield p
    p.fechar()


def _ponte(uniq: str, par: _ParDeSockets, **kw):  # type: ignore[no-untyped-def]
    no = bt.NoDualSenseBT(caminho=f"/dev/hidraw-{uniq[-2:]}", uniq=uniq, produto=0x0CE6)
    return bt.PonteMicBluetooth(
        no, opener=par.opener, decodificador=_DecodadorFixo(), **kw
    )


# ---------------------------------------------------------------------------
# MORDIDA 1 — o nó nasce pelo RÁDIO, com o nome do CONTROLE, e recebe áudio
# ---------------------------------------------------------------------------


def test_o_radio_publica_o_no_com_nome_de_controle(pactl, par) -> None:  # type: ignore[no-untyped-def]
    """O microfone do rádio deixa de se chamar pelo TRANSPORTE.

    O defeito era o NOME: ``hefesto_dualsense_bt_<hex6>`` diz o transporte, e
    trocar o cabo pelo rádio trocava o nome do microfone daquele controle —
    todo app que tivesse fixado o device o perdia.

    ARRANQUE A CURA (faça `_abrir_o_canal_por_controle` devolver `None` sempre)
    e esta régua REPROVA, dizendo qual nome nasceu.
    """
    ponte = _ponte(P1, par)
    assert ponte.iniciar(), "a ponte não subiu com o `pactl` dublado"
    try:
        assert ponte.nome_source == canal.nome_do_canal(P1) == "hefesto_mic_000001", (
            f"o rádio publicou {ponte.nome_source!r}. O nome com IDENTIDADE é o "
            "que faz o microfone daquele controle ser o mesmo nos dois "
            "transportes — que é o 'Mic virtual' que ela pediu."
        )
        assert not ponte.nome_source.startswith(fc.PREFIXO_SOURCE_PONTE_BT), (
            "o nome do TRANSPORTE voltou ao nó do rádio"
        )
        assert canal.de_pe() == {P1: "hefesto_mic_000001"}, (
            "o dono do ciclo de vida do canal não sabe que ele está de pé — "
            "e é essa tabela que impede o cabo e o rádio de publicarem dois "
            "`module-pipe-source` com o mesmo `source_name`"
        )
    finally:
        ponte.parar()


def test_o_audio_do_radio_sai_do_outro_lado_do_no(pactl, par) -> None:  # type: ignore[no-untyped-def]
    """O quadro Opus entra pelo rádio e o PCM SAI do nó — byte por byte.

    Esta é a régua que prova *"o rádio alimenta o nó"*, e ela não acredita em
    contador nenhum: mede o que um app que gravasse do canal receberia, lendo a
    ponta de LEITURA do fifo — a mesma que o `module-pipe-source` segura.

    ARRANQUE A ALIMENTAÇÃO (tire o `self._source.escrever(pcm)` do
    `_processar`) e ela REPROVA: o contador de quadros continua subindo e do
    outro lado não sai byte nenhum — que é exatamente o sintoma que esta casa
    passou uma hora depurando em 25/07.
    """
    pactl.estado = bt.ESTADO_COM_OUVINTE  # tem app gravando: o mic é pedido
    ponte = _ponte(P1, par)
    assert ponte.iniciar()
    try:
        quadro = bytes(range(bt.MIC_OPUS_LEN))
        par.emitir(_report_de_audio(quadro))
        assert _esperar(lambda: ponte.estatistica().quadros_audio >= 1)
        colhido = bytearray()

        def _chegou() -> bool:
            colhido.extend(pactl.colher("hefesto_mic_000001"))
            return len(colhido) >= len(_DecodadorFixo.PCM)

        assert _esperar(_chegou), (
            f"o PCM não chegou ao outro lado do nó: {len(colhido)} bytes, e a "
            f"ponte diz ter decodificado {ponte.estatistica().quadros_audio} quadros"
        )
        assert bytes(colhido).startswith(_DecodadorFixo.PCM), (
            "saiu do nó um PCM diferente do que o decodificador produziu"
        )
    finally:
        ponte.parar()


def test_sem_identidade_o_radio_volta_ao_nome_de_sempre(pactl, par) -> None:  # type: ignore[no-untyped-def]
    """O caminho de volta fica INTEIRO — é o que torna a troca reversível.

    Um DualSense recém-pareado pode não ter `HID_UNIQ`. Sem endereço não há
    identidade, e batizar o canal com um nome inventado colidiria com o do
    vizinho na mesa de quatro. A resposta certa é o nome de sempre, e o rádio
    NUNCA fica sem microfone por causa desta mudança.
    """
    ponte = _ponte("", par)
    assert ponte.iniciar()
    try:
        assert ponte.nome_source.startswith(fc.PREFIXO_SOURCE_PONTE_BT), (
            f"sem identidade o nó nasceu {ponte.nome_source!r} — o caminho de "
            "volta sumiu e um controle sem HID_UNIQ ficaria sem microfone"
        )
        assert canal.de_pe() == {}, "batizou um canal sem endereço para batizar"
    finally:
        ponte.parar()


def test_a_ponte_nao_derruba_o_canal_de_quem_ela_nao_abriu(pactl, par) -> None:  # type: ignore[no-untyped-def]
    """Fechar o que não é seu tiraria o microfone de quem não pediu nada.

    O canal por controle tem UM dono de ciclo de vida, e ele é compartilhado
    entre o cabo e o rádio. Se o canal já estava de pé quando a ponte subiu, ele
    é de outro — e o `parar()` da ponte não pode derrubá-lo.
    """
    ja = canal.abrir(P1, "canal de quem chegou antes")
    assert ja is not None
    ponte = _ponte(P1, par)
    assert ponte.iniciar()
    assert ponte.nome_source == "hefesto_mic_000001"
    ponte.parar()
    assert canal.de_pe() == {P1: "hefesto_mic_000001"}, (
        "a ponte derrubou um canal que não era dela — o microfone de quem "
        "chegou antes sumiu no `parar()` de outro controle"
    )


# ---------------------------------------------------------------------------
# MORDIDA 4 — o 0x32 SEGUE o ouvinte da source
# ---------------------------------------------------------------------------


def test_sem_ouvinte_o_radio_nao_pede_o_microfone(pactl, par) -> None:  # type: ignore[no-untyped-def]
    """Nó publicado e SUSPENDED: o canal existe e o controle não captura nada.

    É o que o canal do CABO faz de graça, e era a assimetria que obrigava o
    subsystem a negar o CANAL para evitar a CAPTURA. Sem ouvinte, ligar o
    microfone custa ~106 quadros de áudio por segundo no link do rádio e a
    privacidade de um microfone capturando para ninguém.

    CONGELE O BYTE (volte o `self._escrever_pedido(ligar=True)` incondicional
    ao `iniciar`) e esta régua REPROVA.

    **O 0x32 de DESLIGAR na subida é esperado, e é o desfecho certo**: quem sobe
    a ponte não sabe em que estado o firmware ficou — outro escritor (o app da
    PlayStation em Proton, o re-arme de uma ponte anterior) pode ter deixado o
    microfone dela no ar. Uma escrita a mais custa um report; um microfone
    ligado que ninguém pediu custa a privacidade dela.
    """
    pactl.estado = "SUSPENDED"
    ponte = _ponte(P1, par)
    assert ponte.iniciar()
    try:
        time.sleep(0.3)
        assert bt.AUDIO_CONTROL_MIC_ON not in par.pedidos_de_mic(), (
            "a ponte ligou o microfone do controle sem ninguém gravando do nó: "
            f"{par.pedidos_de_mic()}"
        )
    finally:
        ponte.parar()


def test_com_ouvinte_o_radio_pede_o_microfone(pactl, par) -> None:  # type: ignore[no-untyped-def]
    """`RUNNING` quer dizer que tem app gravando — e aí o mic tem de estar no ar.

    O contrapeso da régua acima: seguir o estado não pode virar nunca ligar.
    """
    pactl.estado = bt.ESTADO_COM_OUVINTE
    ponte = _ponte(P1, par)
    assert ponte.iniciar()
    try:
        assert _esperar(lambda: par.pedidos_de_mic() == [bt.AUDIO_CONTROL_MIC_ON]), (
            f"com ouvinte o microfone não foi pedido: {par.pedidos_de_mic()}"
        )
    finally:
        ponte.parar()


def test_o_ouvinte_que_sai_desliga_o_microfone(pactl, par) -> None:  # type: ignore[no-untyped-def]
    """DOIS valores, e a transição entre eles — não um instante congelado.

    Uma régua que lê o estado UMA vez mede um instante, não um comportamento.
    Aqui o app começa gravando (`RUNNING`), sai (`IDLE`), e o microfone tem de
    apagar sozinho.

    **`IDLE` NÃO É OUVINTE**, e a distinção é o ponto: depois que o último app
    solta o nó ele fica `IDLE`, não volta a `SUSPENDED` (medido na máquina dela
    em 06/09/2026). Tratar `IDLE` como "alguém está ouvindo" deixaria o
    microfone dela ligado para sempre depois da primeira gravação.
    """
    pactl.estado = bt.ESTADO_COM_OUVINTE
    ponte = _ponte(P1, par)
    assert ponte.iniciar()
    try:
        assert _esperar(lambda: par.pedidos_de_mic() == [bt.AUDIO_CONTROL_MIC_ON])
        pactl.estado = "IDLE"
        assert _esperar(
            lambda: par.pedidos_de_mic()
            == [bt.AUDIO_CONTROL_MIC_ON, bt.AUDIO_CONTROL_MIC_OFF]
        ), (
            "o ouvinte saiu e o microfone continuou no ar: "
            f"{par.pedidos_de_mic()}"
        )
    finally:
        ponte.parar()


def test_o_pedido_nao_se_repete_em_regime(pactl, par) -> None:  # type: ignore[no-untyped-def]
    """A escrita é de BORDA — a parcimônia do cabeçalho continua inteira.

    Escrever 0x32 a cada volta do laço seria um write por segundo por controle
    disputando o link com o `hid-playstation`, que é a razão pela qual este
    módulo escreve só na borda desde 25/07.

    **REGIME É COM ÁUDIO CHEGANDO**, e é por isso que este teste emite quadros
    o tempo todo: sem áudio por dois segundos o `_talvez_rearmar` escreve de
    novo — autocura de borda que EXISTE de propósito e não é o que esta régua
    mede.
    """
    pactl.estado = bt.ESTADO_COM_OUVINTE
    ponte = _ponte(P1, par)
    assert ponte.iniciar()
    try:
        assert _esperar(lambda: par.pedidos_de_mic() == [bt.AUDIO_CONTROL_MIC_ON])
        quadro = bytes(range(bt.MIC_OPUS_LEN))
        fim = time.monotonic() + 2.5  # duas voltas do olhar na source
        while time.monotonic() < fim:
            par.emitir(_report_de_audio(quadro))
            time.sleep(0.05)
        assert par.pedidos_de_mic() == [bt.AUDIO_CONTROL_MIC_ON], (
            f"a ponte voltou a escrever em regime: {par.pedidos_de_mic()}"
        )
    finally:
        ponte.parar()


def test_nao_sei_nunca_vira_ninguem_esta_ouvindo(pactl, par) -> None:  # type: ignore[no-untyped-def]
    """Estado ilegível deixa o comportamento como era — nunca desliga por falta
    de instrumento.

    `estado()` devolve `None` quando o nó não está na lista ou o `pactl` não
    respondeu. Transformar isso em "ninguém está ouvindo" desligaria o
    microfone dela porque a régua não conseguiu perguntar — o *"silêncio não é
    sucesso"* com o sinal trocado.
    """
    pactl.estado = bt.ESTADO_COM_OUVINTE
    ponte = _ponte(P1, par)
    assert ponte.iniciar()
    try:
        assert _esperar(lambda: par.pedidos_de_mic() == [bt.AUDIO_CONTROL_MIC_ON])
        pactl.nos.pop("hefesto_mic_000001", None)  # o nó sumiu da lista
        quadro = bytes(range(bt.MIC_OPUS_LEN))
        fim = time.monotonic() + 1.6
        while time.monotonic() < fim:
            par.emitir(_report_de_audio(quadro))
            time.sleep(0.05)
        assert par.pedidos_de_mic() == [bt.AUDIO_CONTROL_MIC_ON], (
            "a ponte desligou o microfone porque não conseguiu PERGUNTAR quem "
            f"estava ouvindo: {par.pedidos_de_mic()}"
        )
    finally:
        ponte.parar()


def test_o_parar_desliga_o_microfone_mesmo_sem_ter_ligado(pactl, par) -> None:  # type: ignore[no-untyped-def]
    """Deixar o microfone de alguém ligado depois de fechar não é opção.

    O 0x32 de desligar é incondicional no `parar()` de propósito: outro
    escritor (o app da PlayStation em Proton, o re-arme de uma ponte anterior)
    pode ter deixado o microfone no ar, e uma escrita a mais é barata.
    """
    pactl.estado = "SUSPENDED"
    ponte = _ponte(P1, par)
    assert ponte.iniciar()
    ponte.parar()
    assert _esperar(lambda: par.pedidos_de_mic()[-1:] == [bt.AUDIO_CONTROL_MIC_OFF]), (
        f"o `parar()` não desligou o microfone: {par.pedidos_de_mic()}"
    )


# ---------------------------------------------------------------------------
# A TELA CONTA QUATRO
# ---------------------------------------------------------------------------


def test_quatro_controles_no_radio_tem_quatro_canais(pactl) -> None:  # type: ignore[no-untyped-def]
    """Quatro DualSense, quatro canais com nome próprio — o foco dela.

    *"4 controles os 4 tem que ter canais de entrada unico pra cada qual."*
    Uma tela que conta um está descrevendo a bancada de ontem.
    """
    for uniq in OS_QUATRO:
        assert canal.abrir(uniq, f"Microfone de {uniq}") is not None
    de_pe = canal.de_pe()
    assert len(de_pe) == 4, f"os quatro canais não subiram: {de_pe}"
    assert len(set(de_pe.values())) == 4, (
        f"dois controles ficaram com o MESMO nome de nó: {de_pe}"
    )
    fontes = sorted(de_pe.values())
    for uniq in OS_QUATRO:
        assert fc.escolher_fonte(fontes, uniq, list(OS_QUATRO), None) == de_pe[uniq], (
            f"a resolução devolveu o canal de outro controle para {uniq}"
        )


def test_o_canal_de_um_nao_e_o_canal_do_vizinho(pactl) -> None:  # type: ignore[no-untyped-def]
    """Derrubar o canal de um não pode tocar no dos outros três."""
    for uniq in OS_QUATRO:
        canal.abrir(uniq, f"Microfone de {uniq}")
    assert canal.fechar(P2) is True
    restantes = canal.de_pe()
    assert set(restantes) == {P1, P3, P4}, (
        f"fechar o canal do P2 mexeu no dos outros: {restantes}"
    )


# ---------------------------------------------------------------------------
# MORDIDA 3 — a ELEIÇÃO decide o padrão do sistema, e SÓ isso
# ---------------------------------------------------------------------------


def test_a_eleicao_nao_muda_quem_e_ouvido_no_canal_de_cada_um(pactl, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """Trocar a fonte PADRÃO do sistema não mexe no canal de controle nenhum.

    São perguntas diferentes, e confundi-las é o defeito que a
    CANAL-POR-CONTROLE-01 nomeou: *"ter canal"* não é escasso — cada DualSense
    publica o dele —, e *"ser o padrão do sistema"* é o único recurso
    genuinamente único, porque `pactl get-default-source` devolve UM nome.
    """
    from hefesto_dualsense4unix.integrations import eleicao_de_microfone as el

    for uniq in OS_QUATRO:
        canal.abrir(uniq, f"Microfone de {uniq}")
    antes = dict(canal.de_pe())
    fontes = sorted(antes.values())

    escritas: list[list[str]] = []
    monkeypatch.setattr(el, "fonte_se_sustenta", lambda _n: True)
    monkeypatch.setattr(
        el, "_rodar", lambda argv: (escritas.append(argv), (0, ""))[1]
    )
    monkeypatch.setattr(
        el.EleitorDeMicrofone, "_assentar_e_reler", lambda _s, alvo: alvo
    )

    eleitor = el.EleitorDeMicrofone()
    resultado = eleitor.eleger_por_uniq(
        P2, fontes=fontes, uniqs_com_audio=list(OS_QUATRO)
    )

    assert resultado.ok and resultado.alvo == antes[P2], (
        f"a eleição não elegeu o canal do P2: {resultado}"
    )
    assert any("set-default-source" in a for argv in escritas for a in argv), (
        "a eleição não escreveu o padrão do sistema — ela deixou de fazer a "
        "única coisa que lhe cabe"
    )
    assert canal.de_pe() == antes, (
        "eleger o P2 mexeu nos canais dos outros controles: "
        f"{canal.de_pe()} != {antes}"
    )
    for uniq in OS_QUATRO:
        assert fc.escolher_fonte(fontes, uniq, list(OS_QUATRO), None) == antes[uniq], (
            f"depois da eleição, quem é ouvido no canal de {uniq} mudou"
        )


# ---------------------------------------------------------------------------
# MORDIDA 2 — O CENSO DOS CHAMADORES, e a dirigida em cada um
# ---------------------------------------------------------------------------

#: OS CHAMADORES DE `escolher_fonte`, MEDIDOS por AST em 06/09/2026.
#:
#: **SÃO SEIS, e não quatro.** O enunciado da MIC-VIRTUAL-02 diz "os quatro
#: chamadores", herdando o número do docstring de `escolher_fonte`, que lista
#: *"a eleição, a luz, o áudio da janela e o `escolher_sink`"*. A contagem
#: envelheceu: `integrations/audio_control.py` entrou em 03/09/2026
#: (`fonte_de_captura_do_uniq` deixou de ser uma segunda régua) e a luz virou
#: DOIS — `integrations/quem_ouve_o_microfone.py` responde QUEM ouve e
#: `daemon/subsystems/luz_do_mic.py` responde POR ONDE.
#:
#: É por isso que esta lista é MEDIDA e não digitada: um número escrito à mão
#: em prosa é a forma mais barata de a próxima pessoa curar cinco de seis.
CHAMADORES_MEDIDOS = frozenset(
    {
        "app/mic_monitor.py",
        "daemon/subsystems/luz_do_mic.py",
        "integrations/audio_control.py",
        "integrations/eleicao_de_microfone.py",
        "integrations/fontes_de_captura.py",
        "integrations/quem_ouve_o_microfone.py",
    }
)


def _quem_chama_escolher_fonte() -> set[str]:
    """Os módulos de `src/` que CHAMAM `escolher_fonte` — por AST, não por grep.

    Grep aqui daria falso positivo em toda a prosa que cita a função (são 20
    linhas de docstring contra 7 chamadas). A pergunta é sobre o CÓDIGO, então
    quem responde é o AST.
    """
    achados: set[str] = set()
    for arquivo in sorted(SRC.rglob("*.py")):
        try:
            arvore = ast.parse(arquivo.read_text(encoding="utf-8"))
        except SyntaxError:  # pragma: no cover - o portão de sintaxe pega antes
            continue
        for no in ast.walk(arvore):
            if not isinstance(no, ast.Call):
                continue
            alvo = no.func
            nome = (
                alvo.id
                if isinstance(alvo, ast.Name)
                else alvo.attr
                if isinstance(alvo, ast.Attribute)
                else ""
            )
            if nome == "escolher_fonte":
                achados.add(arquivo.relative_to(SRC).as_posix())
    return achados


def test_o_censo_dos_chamadores_de_escolher_fonte_nao_envelhece() -> None:
    """Quem resolve "qual é o microfone deste controle" passa pelo DONO.

    **ESTA É A RÉGUA QUE IMPEDE O DEFEITO DE 05/09 DE ACONTECER PELA TERCEIRA
    VEZ.** A regra que aquele dia deixou escrita: *quando a cura conhece a
    causa, ela cobre TODOS os chamadores* — e ela foi violada duas vezes num dia
    porque ninguém tinha CONTADO os chamadores.

    Ela reprova nos DOIS sentidos, e os dois são notícia:

    * um módulo NOVO chamando — alguém passou a resolver a mesma pergunta e a
      lista de quem precisa ser conferido cresceu;
    * um módulo que PAROU de chamar — o suspeito imediato é uma segunda régua
      sobre o mesmo estado, que é como esta casa fabrica divergência silenciosa
      (foi o que `audio_control.fonte_de_captura_do_uniq` era até 03/09).
    """
    agora = _quem_chama_escolher_fonte()
    entraram = sorted(agora - CHAMADORES_MEDIDOS)
    sairam = sorted(CHAMADORES_MEDIDOS - agora)
    assert not entraram, (
        f"CHAMADOR NOVO de `escolher_fonte`: {entraram}. Ele passa pela regra 0? "
        "Acrescente-o a `CHAMADORES_MEDIDOS` e à régua dirigida abaixo — a "
        "conta que não se refaz é a que deixa a próxima pessoa curar cinco de "
        "seis."
    )
    assert not sairam, (
        f"CHAMADOR QUE SUMIU: {sairam}. Se ele parou de perguntar ao dono, o "
        "suspeito é uma segunda régua sobre o mesmo estado."
    )


def test_a_regra_0_alcanca_a_eleicao(pactl, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """Chamador 1/6 — `integrations/eleicao_de_microfone.py`."""
    from hefesto_dualsense4unix.integrations import eleicao_de_microfone as el

    canal.abrir(P1, "Microfone do P1")
    alvo = canal.de_pe()[P1]
    monkeypatch.setattr(el, "fonte_se_sustenta", lambda _n: True)
    monkeypatch.setattr(el, "_rodar", lambda _argv: (0, ""))
    monkeypatch.setattr(el.EleitorDeMicrofone, "_assentar_e_reler", lambda _s, a: a)
    resultado = el.EleitorDeMicrofone().eleger_por_uniq(
        P1, fontes=[alvo], uniqs_com_audio=[]
    )
    assert resultado.alvo == alvo, f"a eleição não viu o canal com identidade: {resultado}"


def test_a_regra_0_alcanca_o_volume_por_controle(pactl, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """Chamador 2/6 — `integrations/audio_control.py`.

    É o caminho do controle deslizante do microfone. Até 03/09 ele tinha régua
    própria e só enxergava o cabo; hoje pergunta ao dono, e é por isso que a
    regra 0 o alcança de graça.
    """
    from hefesto_dualsense4unix.integrations import audio_control as ac

    canal.abrir(P1, "Microfone do P1")
    alvo = canal.de_pe()[P1]
    curta = f"600\t{alvo}\tPipeWire\ts16le 1ch 48000Hz\tSUSPENDED"
    monkeypatch.setattr(
        ac, "_texto_do_pactl", lambda argv: curta if "short" in argv else ""
    )
    assert ac.fonte_de_captura_do_uniq(P1, mesa=list(OS_QUATRO)) == alvo


def test_a_regra_0_alcanca_quem_ouve(pactl, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """Chamador 3/6 — `integrations/quem_ouve_o_microfone.py` (QUEM ouve)."""
    from hefesto_dualsense4unix.integrations import quem_ouve_o_microfone as qo

    canal.abrir(P1, "Microfone do P1")
    alvo = canal.de_pe()[P1]
    curta = f"600\t{alvo}\tPipeWire\ts16le 1ch 48000Hz\tSUSPENDED"

    def _falso(argv: list[str]) -> tuple[int, str]:
        return (0, curta if "short" in argv else "")

    monkeypatch.setattr(qo, "_rodar", _falso)
    monkeypatch.setattr(qo, "casamento_usb_agora", lambda _u: None)
    leitura = qo.ler_quem_ouve([P1])
    assert leitura.lida and P1 not in leitura.sem_canal, (
        f"quem responde 'quem te escuta' não achou o canal com identidade: {leitura}"
    )


def test_a_regra_0_alcanca_a_luz(pactl, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """Chamador 4/6 — `daemon/subsystems/luz_do_mic.py` (POR ONDE)."""
    from hefesto_dualsense4unix.daemon.subsystems import luz_do_mic as luz
    from hefesto_dualsense4unix.integrations import eleicao_de_microfone as el

    canal.abrir(P1, "Microfone do P1")
    alvo = canal.de_pe()[P1]
    monkeypatch.setattr(el, "fontes_de_captura_agora", lambda: [alvo])
    monkeypatch.setattr(el, "casamento_usb_agora", lambda _m: None)
    assert luz._fontes_para([P1], [P1]) == {P1: alvo}


def test_a_regra_0_alcanca_o_medidor_da_janela(pactl, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """Chamador 5/6 — `app/mic_monitor.py` (o medidor de nível de cada card)."""
    from hefesto_dualsense4unix.app import mic_monitor as mm

    canal.abrir(P1, "Microfone do P1")
    alvo = canal.de_pe()[P1]
    monitor = mm.MicMonitor()
    capturas: dict[str, str] = {}
    monkeypatch.setattr(monitor, "_descobrir_fontes", lambda: [alvo])
    monkeypatch.setattr(monitor, "_casar_por_usb", lambda *a, **k: None)
    monkeypatch.setattr(monitor, "_derrubar_capturas", lambda _m: None)
    monkeypatch.setattr(
        monitor, "_garantir_captura", lambda uniq, fonte: capturas.__setitem__(uniq, fonte)
    )
    monkeypatch.setattr(monitor, "_descobrir_saidas", lambda *a, **k: ({}, {}))
    monkeypatch.setattr(mm, "usb_pai_por_uniq", lambda _u: {})
    monitor.set_ativo(True)
    monitor.set_controles((P1,))
    monitor.reconciliar()
    assert capturas == {P1: alvo}, (
        f"o medidor da janela não mediu o canal com identidade: {capturas}"
    )


def test_a_regra_0_e_inerte_no_escolher_sink_por_construcao(pactl) -> None:  # type: ignore[no-untyped-def]
    """Chamador 6/6 — `integrations/fontes_de_captura.py::escolher_sink`.

    Aqui a regra 0 é INERTE **de propósito, e o corte é a montante**: um
    `hefesto_mic_<hex6>` é nó de CAPTURA e `sinks_dualsense` nunca o devolve. O
    microfone não sai por lugar nenhum; se ele aparecesse numa lista de sinks, o
    defeito estaria antes daqui.
    """
    canal.abrir(P1, "Microfone do P1")
    alvo = canal.de_pe()[P1]
    tabela = f"600\t{alvo}\tPipeWire\ts16le 1ch 48000Hz\tSUSPENDED"
    assert fc.sinks_dualsense(tabela) == [], (
        "o canal do microfone entrou numa lista de SAÍDA — o selo da saída "
        "passaria a falar do microfone"
    )


# ---------------------------------------------------------------------------
# A PRIORIDADE QUE NÃO VIAJAVA — a régua que LÊ como o servidor lê
# ---------------------------------------------------------------------------


def _como_o_servidor_le(source_properties: str) -> dict[str, str]:
    """Quebra o `source_properties` como o `pipewire-pulse` o quebra.

    A regra medida em 06/09/2026 nesta máquina: sem ASPAS DUPLAS em volta do
    valor inteiro, tudo depois do primeiro ESPAÇO é descartado em silêncio.
    Entre aspas, a lista sobrevive inteira — e as ASPAS SIMPLES de dentro
    sobrevivem junto, que é como a descrição com espaços chega completa
    (medido: ``device.description='Microfone DualSense BT (…)'`` virou
    ``Description: Microfone DualSense BT (…)``).

    O `shlex` é quem quebra respeitando as aspas simples. Quebrar por espaço
    seco seria um instrumento MAIS CRU que o servidor — e um instrumento cru
    reprova a cura em vez do defeito, que é o modo de falha mais caro desta
    casa.
    """
    bruto = source_properties.split("=", 1)[1]
    entre_aspas = bruto.startswith('"') and bruto.endswith('"')
    valor = bruto[1:-1] if entre_aspas else bruto.split(" ", 1)[0]
    props: dict[str, str] = {}
    for pedaco in shlex.split(valor):
        chave, _, val = pedaco.partition("=")
        if chave:
            props[chave] = val
    return props


def test_a_prioridade_chega_ao_no_e_nao_so_ao_argv(pactl) -> None:  # type: ignore[no-untyped-def]
    """O `priority.session` da ponte tem de SOBREVIVER ao parser do servidor.

    **A RÉGUA QUE JÁ VIGIAVA ISTO DAVA VERDE SOBRE UM NÓ QUE NASCIA EM 2000.**
    ``test_o_canal_do_radio_nao_perde_para_um_monitor.py::
    test_a_prioridade_viaja_de_verdade_no_load_module`` afirma
    ``"priority.session=1500" in props[0]`` — e a string ESTÁ no argv, dentro do
    pedaço que o servidor joga fora. Ela mede o TEXTO do comando; o nó nascia
    com o 2000 padrão do `pipewire-pulse`.

    MEDIDO na máquina dela em 06/09/2026, carregando os dois lado a lado e
    LENDO O NÓ com `pactl list sources`::

        sem aspas  ->  description = Microfone          priority.session = 2000
        com aspas  ->  description = Microfone DualSense BT (aa:bb:cc:00:00:01)
                       priority.session = 1500

    ARRANQUE AS ASPAS de `propriedades_da_source` e esta régua REPROVA.
    """
    fonte = bt.SourceVirtualPipeWire(
        nome="hefesto_mic_000001", descricao="Microfone DualSense BT (P1)", runner=pactl
    )
    assert fonte.iniciar()
    try:
        carga = next(c for c in pactl.chamadas if len(c) > 1 and c[1] == "load-module")
        props = _como_o_servidor_le(_valor_bruto(carga, "source_properties="))
        assert props.get("priority.session") == str(bt.PRIORIDADE_SESSAO_DA_PONTE), (
            "a prioridade não sobrevive ao parser do servidor: o nó nasce com o "
            f"padrão do pipewire-pulse. O servidor leu {props!r}"
        )
        assert props.get("device.description", "").count(" ") >= 1, (
            "a descrição chegou cortada no primeiro espaço — é o mesmo defeito, "
            "e é o que a bandeja de som dela mostra"
        )
    finally:
        fonte.parar()


def _valor_bruto(argv: list[str], chave: str) -> str:
    for arg in argv:
        if arg.startswith(chave):
            return arg
    raise AssertionError(f"o `load-module` foi montado sem {chave!r}")


# ---------------------------------------------------------------------------
# O `pactl` TRADUZ — e uma leitura que não força o idioma responde sobre ele
# ---------------------------------------------------------------------------


def test_o_audio_control_le_o_mudo_em_lingua_que_ele_entende(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """`Mute: sim` não contém `yes` — e era isso que a leitura de volta lia.

    MEDIDO na máquina dela em 06/09/2026, com o `LANG=pt_BR.UTF-8` dela::

        pactl get-source-mute <nó>    sem LC_ALL   ->  Mute: sim / Mute: não
                                      com LC_ALL=C ->  Mute: yes

    `_query_pactl_muted` responde ``"yes" in saida.lower()``, então nesta
    máquina ele devolvia **False sempre**. A cura é a MESMA que este arquivo já
    aplicou duas vezes por outra porta em 15/08/2026.

    ARRANQUE O `env` de `AudioControl._run` e esta régua REPROVA.
    """
    import subprocess

    from hefesto_dualsense4unix.integrations.audio_control import AudioControl

    vistos: list[dict[str, str]] = []

    class _Proc:
        stdout = "Mute: yes\n"
        stderr = ""
        returncode = 0

    def _run(argv, **kw):  # type: ignore[no-untyped-def]
        vistos.append(dict(kw.get("env") or {}))
        return _Proc()

    monkeypatch.setattr(subprocess, "run", _run)
    AudioControl()._query_pactl_muted()
    assert vistos, "a leitura não chegou a rodar `pactl`"
    assert vistos[0].get("LC_ALL") == "C", (
        "a leitura do mudo roda no idioma da sessão dela, e o `pactl` TRADUZ: "
        "a resposta passa a ser sobre o idioma do shell, não sobre o aparelho"
    )
