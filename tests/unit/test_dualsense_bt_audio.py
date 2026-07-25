"""Testes do microfone do DualSense por Bluetooth (BT-MIC-01).

Nenhum teste toca hardware, libopus, PipeWire ou sysfs real: os reports são
montados com o MESMO utilitário de CRC do produto (`bt_crc32`), o hidraw é um
`socketpair` e o PipeWire é um runner dublado. Os valores travados aqui são os
que foram MEDIDOS ao vivo em 2026-07-25 contra um DualSense por BT — se alguém
mexer num offset, é aqui que estoura.
"""
from __future__ import annotations

import os
import socket
import threading
import time

import pytest

from hefesto_dualsense4unix.core.ds_output_report import (
    BT_CRC_SEED,
    BT_INPUT_CRC_SEED,
    bt_crc32,
)
from hefesto_dualsense4unix.integrations import dualsense_bt_audio as bt

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _report_de_audio(quadro: bytes, *, seq: int = 0, crc_ok: bool = True) -> bytes:
    """Monta um input 0x31 de 78 bytes carregando `quadro` de Opus."""
    raw = bytearray(bt.INPUT_REPORT_BT_SIZE)
    raw[0] = bt.INPUT_REPORT_BT
    raw[1] = ((seq & 0x0F) << 4) | bt.INPUT_FLAG_AUDIO
    raw[bt.MIC_OPUS_OFFSET : bt.MIC_OPUS_OFFSET + len(quadro)] = quadro
    crc = bt_crc32(raw[:74], seed=BT_INPUT_CRC_SEED)
    if not crc_ok:
        crc ^= 0xFFFF
    raw[74:78] = (crc & 0xFFFFFFFF).to_bytes(4, "little")
    return bytes(raw)


def _report_de_input(status: int = 0, *, seq: int = 0) -> bytes:
    """Monta um input 0x31 normal (sem áudio) com um byte de status de áudio."""
    raw = bytearray(bt.INPUT_REPORT_BT_SIZE)
    raw[0] = bt.INPUT_REPORT_BT
    raw[1] = ((seq & 0x0F) << 4) | bt.INPUT_FLAG_HID
    raw[bt.INPUT_OFFSET_AUDIO_STATUS] = status
    raw[74:78] = bt_crc32(raw[:74], seed=BT_INPUT_CRC_SEED).to_bytes(4, "little")
    return bytes(raw)


class _DecodadorFalso:
    """Devolve PCM de tamanho fixo por quadro; conta o que recebeu."""

    def __init__(self, *, falha: bool = False) -> None:
        self.quadros: list[bytes] = []
        self.falha = falha
        self.fechado = False

    def decodificar(self, quadro: bytes) -> bytes | None:
        self.quadros.append(quadro)
        if self.falha:
            return None
        return b"\x00\x01" * bt.MIC_AMOSTRAS_POR_QUADRO

    def close(self) -> None:
        self.fechado = True


class _SourceFalsa:
    """Coleta o PCM que a ponte publicaria, sem tocar em PipeWire."""

    def __init__(self, *, aceita: bool = True) -> None:
        self.pcm: list[bytes] = []
        self.aceita = aceita
        self.descartes = 0
        self.iniciada = False
        self.parada = False

    def iniciar(self) -> bool:
        self.iniciada = True
        return True

    def parar(self) -> None:
        self.parada = True

    def escrever(self, pcm: bytes) -> bool:
        if not self.aceita:
            self.descartes += 1
            return False
        self.pcm.append(pcm)
        return True


# ---------------------------------------------------------------------------
# 1. O report 0x32 que LIGA o microfone
# ---------------------------------------------------------------------------


def test_pedido_de_mic_tem_o_tamanho_do_report_descriptor() -> None:
    """141 bytes de payload + 1 de report ID — o que o descriptor declara."""
    assert len(bt.montar_pedido_de_mic(True)) == 142
    assert bt.AUDIO_OUTPUT_REPORT_LEN == 142


def test_pedido_de_mic_carrega_o_bloco_tlv_de_audiocontrol() -> None:
    """[0]=0x32, [2]=tag 0x11|presente, [3]=len 1, [4]=valor. Layout travado."""
    pkt = bt.montar_pedido_de_mic(True, seq=5)
    assert pkt[0] == bt.AUDIO_OUTPUT_REPORT_ID == 0x32
    assert pkt[1] == 5 << 4
    assert pkt[2] == bt.BLOCO_AUDIO_CONTROL | bt.BLOCO_PRESENTE == 0x91
    assert pkt[3] == 1
    assert pkt[4] == bt.AUDIO_CONTROL_MIC_ON == 0b011


def test_pedido_de_desligar_muda_so_o_bit_zero() -> None:
    """0b011 -> 0b010: o liga/desliga é UM bit, o resto do bloco é idêntico."""
    liga = bt.montar_pedido_de_mic(True, seq=0)
    desliga = bt.montar_pedido_de_mic(False, seq=0)
    assert liga[4] ^ desliga[4] == 0b001
    assert liga[:4] == desliga[:4]
    assert liga[5:138] == desliga[5:138]


def test_pedido_de_mic_tem_crc_de_output_valido() -> None:
    """Seed 0xA2 sobre os 138 primeiros bytes — CRC errado o firmware ignora."""
    pkt = bt.montar_pedido_de_mic(True, seq=3)
    esperado = bt_crc32(pkt[:138], seed=BT_CRC_SEED)
    assert int.from_bytes(pkt[138:142], "little") == esperado


def test_seq_do_pedido_e_mascarado_em_quatro_bits() -> None:
    """O nibble de sequência é 0..15; 16 volta a 0 sem estourar o byte."""
    assert bt.montar_pedido_de_mic(True, seq=16)[1] == 0
    assert bt.montar_pedido_de_mic(True, seq=15)[1] == 0xF0


def test_pedido_de_mic_nunca_usa_o_report_id_do_kernel() -> None:
    """O 0x31 é do `hid-playstation`; nós só falamos 0x32 (ver o cabeçalho)."""
    for ligar in (True, False):
        assert bt.montar_pedido_de_mic(ligar)[0] != bt.INPUT_REPORT_BT


# ---------------------------------------------------------------------------
# 2. Extração do quadro Opus do input 0x31
# ---------------------------------------------------------------------------


def test_extrai_71_bytes_de_opus_do_report_de_audio() -> None:
    quadro = bytes(range(bt.MIC_OPUS_LEN))
    assert bt.frame_opus_do_report(_report_de_audio(quadro)) == quadro


def test_janela_do_opus_encaixa_exatamente_antes_do_crc() -> None:
    """3 + 71 = 74, e 74..77 é o CRC: o quadro ocupa TODO o espaço que sobra."""
    assert bt.MIC_OPUS_OFFSET + bt.MIC_OPUS_LEN == bt.INPUT_REPORT_BT_SIZE - 4


def test_report_sem_o_bit_de_audio_nao_e_quadro() -> None:
    assert bt.frame_opus_do_report(_report_de_input()) is None
    assert not bt.eh_report_de_audio(_report_de_input())


def test_report_com_crc_quebrado_e_descartado() -> None:
    """Rádio corrompeu: melhor perder 10 ms que estourar o decodificador."""
    ruim = _report_de_audio(bytes(bt.MIC_OPUS_LEN), crc_ok=False)
    assert bt.frame_opus_do_report(ruim) is None


def test_report_de_tamanho_errado_e_descartado() -> None:
    bom = _report_de_audio(bytes(bt.MIC_OPUS_LEN))
    assert bt.frame_opus_do_report(bom[:-1]) is None
    assert bt.frame_opus_do_report(bom + b"\x00") is None


def test_report_de_outro_id_e_descartado() -> None:
    outro = bytearray(_report_de_audio(bytes(bt.MIC_OPUS_LEN)))
    outro[0] = 0x01
    assert bt.frame_opus_do_report(bytes(outro)) is None


# ---------------------------------------------------------------------------
# 3. Byte de status do áudio (mute pelo botão físico)
# ---------------------------------------------------------------------------


def test_status_de_audio_le_mudo_e_fone() -> None:
    assert bt.status_de_audio(_report_de_input(bt.STATUS_MIC_MUDO)) == bt.STATUS_MIC_MUDO
    lido = bt.status_de_audio(_report_de_input(bt.STATUS_FONE_PLUGADO))
    assert lido is not None and lido & bt.STATUS_FONE_PLUGADO


def test_status_de_audio_recusa_o_pacote_de_audio() -> None:
    """Naquele offset, num pacote de áudio, mora Opus — não estado de fone."""
    assert bt.status_de_audio(_report_de_audio(bytes(bt.MIC_OPUS_LEN))) is None


# ---------------------------------------------------------------------------
# 4. Descoberta dos controles em Bluetooth
# ---------------------------------------------------------------------------


def _sysfs_falso(tmp_path, nome: str, uevent: str):  # type: ignore[no-untyped-def]
    no = tmp_path / nome / "device"
    no.mkdir(parents=True)
    (no / "uevent").write_text(uevent, encoding="utf-8")


def test_descobre_so_dualsense_em_bluetooth(tmp_path) -> None:  # type: ignore[no-untyped-def]
    _sysfs_falso(
        tmp_path,
        "hidraw6",
        "DRIVER=playstation\nHID_ID=0005:0000054C:00000CE6\n"
        "HID_PHYS=aa:bb:cc:04:13:c4\nHID_UNIQ=aa:bb:cc:c3:11:f0\n",
    )
    # DualSense no CABO: bus 0x03 — o mic já funciona sozinho, fora daqui.
    _sysfs_falso(
        tmp_path, "hidraw1", "HID_ID=0003:0000054C:00000CE6\nHID_UNIQ=aa:bb:cc:dd:ee:ff\n"
    )
    # Pro Controller da Nintendo em BT: fabricante errado.
    _sysfs_falso(tmp_path, "hidraw2", "HID_ID=0005:0000057E:00002009\nHID_UNIQ=1\n")

    achados = bt.nos_dualsense_bluetooth(str(tmp_path))
    assert [n.caminho for n in achados] == ["/dev/hidraw6"]
    assert achados[0].uniq == "aa:bb:cc:c3:11:f0"


def test_vpad_do_hefesto_nunca_entra(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """O vpad se apresenta como Edge (0x0DF2); só o bus e o phys o separam."""
    _sysfs_falso(
        tmp_path,
        "hidraw3",
        "HID_ID=0005:0000054C:00000DF2\nHID_PHYS=hefesto-vpad\nHID_UNIQ=02:fe:00:00:00:01\n",
    )
    assert bt.nos_dualsense_bluetooth(str(tmp_path)) == []


def test_sysfs_ausente_devolve_lista_vazia() -> None:
    assert bt.nos_dualsense_bluetooth("/nao/existe/mesmo") == []


def test_nome_curto_usa_o_fim_do_mac() -> None:
    no = bt.NoDualSenseBT(caminho="/dev/hidraw6", uniq="aa:bb:cc:c3:11:f0", produto=0x0CE6)
    assert no.nome_curto == "c311f0"


def test_nome_curto_sem_uniq_cai_no_no() -> None:
    """Dois controles sem MAC não podem gerar o MESMO nome de source."""
    no = bt.NoDualSenseBT(caminho="/dev/hidraw9", uniq="", produto=0x0CE6)
    assert no.nome_curto == "hidraw9"


# ---------------------------------------------------------------------------
# 5. A ponte (com hidraw dublado por socketpair)
# ---------------------------------------------------------------------------


class _ParDeSockets:
    """Um socketpair fazendo as vezes de /dev/hidrawN (select + read + write).

    SOCK_SEQPACKET, não o SOCK_STREAM default: o hidraw entrega UM report por
    `read()`, e num stream dois reports emitidos juntos chegariam colados num
    buffer de 156 bytes. O teste ficaria flaky e — pior — passaria a testar um
    comportamento que o dispositivo real não tem.
    """

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
        # A ponte ESCREVE o 0x32 no mesmo fd; sem alguém drenando, o buffer do
        # socketpair encheria e o teste travaria.
        self.controle.settimeout(0.1)
        while not self._parar.is_set():
            try:
                dado = self.controle.recv(4096)
            except (TimeoutError, OSError):
                continue
            if not dado:
                return
            self.escritos.append(dado)

    def fechar(self) -> None:
        self._parar.set()
        self._thread.join(timeout=1.0)
        self.nosso.close()
        self.controle.close()


@pytest.fixture()
def par():  # type: ignore[no-untyped-def]
    p = _ParDeSockets()
    yield p
    p.fechar()


def _esperar(cond, prazo: float = 2.0) -> bool:  # type: ignore[no-untyped-def]
    fim = time.monotonic() + prazo
    while time.monotonic() < fim:
        if cond():
            return True
        time.sleep(0.01)
    return False


def test_ponte_decodifica_e_publica_o_audio(par) -> None:  # type: ignore[no-untyped-def]
    dec, src = _DecodadorFalso(), _SourceFalsa()
    no = bt.NoDualSenseBT(caminho="/dev/hidrawX", uniq="aa:bb:cc:c3:11:f0", produto=0x0CE6)
    ponte = bt.PonteMicBluetooth(
        no, opener=par.opener, decodificador=dec, source=src
    )
    assert ponte.iniciar()
    try:
        quadro = bytes(range(bt.MIC_OPUS_LEN))
        for i in range(3):
            par.emitir(_report_de_audio(quadro, seq=i))
        assert _esperar(lambda: len(src.pcm) >= 3), "o PCM não chegou na source"
        assert dec.quadros == [quadro] * 3
        assert len(src.pcm[0]) == bt.MIC_BYTES_POR_QUADRO
        assert ponte.estatistica().quadros_audio == 3
    finally:
        ponte.parar()


def test_ponte_liga_o_mic_no_start_e_desliga_no_stop(par) -> None:  # type: ignore[no-untyped-def]
    no = bt.NoDualSenseBT(caminho="/dev/hidrawX", uniq="aa:bb:cc:dd:ee:ff", produto=0x0CE6)
    ponte = bt.PonteMicBluetooth(
        no, opener=par.opener, decodificador=_DecodadorFalso(), source=_SourceFalsa()
    )
    assert ponte.iniciar()
    assert _esperar(lambda: bool(par.escritos))
    primeiro = par.escritos[0]
    assert primeiro[0] == bt.AUDIO_OUTPUT_REPORT_ID
    assert primeiro[4] == bt.AUDIO_CONTROL_MIC_ON

    ponte.parar()
    assert _esperar(lambda: len(par.escritos) >= 2)
    assert par.escritos[-1][4] == bt.AUDIO_CONTROL_MIC_OFF


def test_mudo_pct_mede_o_ciclo_de_trabalho_do_gating() -> None:
    """A anomalia BT-MIC-GATING-01 tem que ser MEDÍVEL, não só relatada."""
    assert bt.EstatisticaMic().mudo_pct == 0.0  # sem dado, não inventa número
    st = bt.EstatisticaMic(quadros_input=4, input_mudos=3)
    assert st.mudo_pct == 75.0


def test_ponte_conta_os_reports_mudos(par) -> None:  # type: ignore[no-untyped-def]
    no = bt.NoDualSenseBT(caminho="/dev/hidrawX", uniq="aa:bb:cc:dd:ee:ff", produto=0x0CE6)
    ponte = bt.PonteMicBluetooth(
        no, opener=par.opener, decodificador=_DecodadorFalso(), source=_SourceFalsa()
    )
    assert ponte.iniciar()
    try:
        for _ in range(3):
            par.emitir(_report_de_input(bt.STATUS_MIC_MUDO))
        par.emitir(_report_de_input(0))
        assert _esperar(lambda: ponte.estatistica().quadros_input == 4)
        assert ponte.estatistica().input_mudos == 3
        assert ponte.estatistica().mudo_pct == 75.0
    finally:
        ponte.parar()


def test_ponte_le_o_mute_do_botao_fisico(par) -> None:  # type: ignore[no-untyped-def]
    no = bt.NoDualSenseBT(caminho="/dev/hidrawX", uniq="aa:bb:cc:dd:ee:ff", produto=0x0CE6)
    ponte = bt.PonteMicBluetooth(
        no, opener=par.opener, decodificador=_DecodadorFalso(), source=_SourceFalsa()
    )
    assert ponte.iniciar()
    try:
        par.emitir(_report_de_input(bt.STATUS_MIC_MUDO))
        assert _esperar(lambda: ponte.estatistica().mudo is True)
        par.emitir(_report_de_input(0))
        assert _esperar(lambda: ponte.estatistica().mudo is False)
    finally:
        ponte.parar()


def test_quadro_com_crc_ruim_conta_como_invalido_e_nao_publica(par) -> None:  # type: ignore[no-untyped-def]
    dec, src = _DecodadorFalso(), _SourceFalsa()
    no = bt.NoDualSenseBT(caminho="/dev/hidrawX", uniq="aa:bb:cc:dd:ee:ff", produto=0x0CE6)
    ponte = bt.PonteMicBluetooth(no, opener=par.opener, decodificador=dec, source=src)
    assert ponte.iniciar()
    try:
        par.emitir(_report_de_audio(bytes(bt.MIC_OPUS_LEN), crc_ok=False))
        assert _esperar(lambda: ponte.estatistica().quadros_invalidos == 1)
        assert src.pcm == []
        assert dec.quadros == []
    finally:
        ponte.parar()


def test_decodificador_que_recusa_o_quadro_nao_publica_lixo(par) -> None:  # type: ignore[no-untyped-def]
    dec, src = _DecodadorFalso(falha=True), _SourceFalsa()
    no = bt.NoDualSenseBT(caminho="/dev/hidrawX", uniq="aa:bb:cc:dd:ee:ff", produto=0x0CE6)
    ponte = bt.PonteMicBluetooth(no, opener=par.opener, decodificador=dec, source=src)
    assert ponte.iniciar()
    try:
        par.emitir(_report_de_audio(bytes(bt.MIC_OPUS_LEN)))
        assert _esperar(lambda: ponte.estatistica().quadros_invalidos == 1)
        assert src.pcm == []
    finally:
        ponte.parar()


def test_ponte_nao_sobe_sem_libopus(par, monkeypatch: pytest.MonkeyPatch) -> None:  # type: ignore[no-untyped-def]
    """Ausência é resposta: nada de source publicada só para exibir silêncio."""

    def _sem_opus(*_a: object, **_k: object) -> None:
        raise bt.OpusIndisponivelError("teste")

    monkeypatch.setattr(bt, "DecodadorOpus", _sem_opus)
    src = _SourceFalsa()
    no = bt.NoDualSenseBT(caminho="/dev/hidrawX", uniq="aa:bb:cc:dd:ee:ff", produto=0x0CE6)
    ponte = bt.PonteMicBluetooth(no, opener=par.opener, source=src)
    assert ponte.iniciar() is False
    assert src.iniciada is False


def test_ponte_nao_sobe_sem_hidraw() -> None:
    def _sem_fd(_caminho: str) -> int:
        raise OSError(13, "EACCES")

    src = _SourceFalsa()
    no = bt.NoDualSenseBT(caminho="/dev/hidrawX", uniq="aa:bb:cc:dd:ee:ff", produto=0x0CE6)
    ponte = bt.PonteMicBluetooth(
        no, opener=_sem_fd, decodificador=_DecodadorFalso(), source=src
    )
    assert ponte.iniciar() is False
    assert src.iniciada is False


def test_parar_e_idempotente(par) -> None:  # type: ignore[no-untyped-def]
    no = bt.NoDualSenseBT(caminho="/dev/hidrawX", uniq="aa:bb:cc:dd:ee:ff", produto=0x0CE6)
    ponte = bt.PonteMicBluetooth(
        no, opener=par.opener, decodificador=_DecodadorFalso(), source=_SourceFalsa()
    )
    assert ponte.iniciar()
    ponte.parar()
    ponte.parar()  # não pode levantar


def test_descartes_vem_da_source_e_nao_sao_somados(par) -> None:  # type: ignore[no-untyped-def]
    """Um número, um dono: o contador de descarte é da source, copiado daqui."""
    src = _SourceFalsa(aceita=False)
    no = bt.NoDualSenseBT(caminho="/dev/hidrawX", uniq="aa:bb:cc:dd:ee:ff", produto=0x0CE6)
    ponte = bt.PonteMicBluetooth(
        no, opener=par.opener, decodificador=_DecodadorFalso(), source=src
    )
    assert ponte.iniciar()
    try:
        for i in range(2):
            par.emitir(_report_de_audio(bytes(bt.MIC_OPUS_LEN), seq=i))
        assert _esperar(lambda: ponte.estatistica().quadros_descartados == 2)
        assert ponte.estatistica().quadros_descartados == 2  # não acumula ao reler
    finally:
        ponte.parar()


# ---------------------------------------------------------------------------
# 6. Source virtual do PipeWire (runner dublado)
# ---------------------------------------------------------------------------


class _RunnerFalso:
    def __init__(self, saida: str | None = "42\n") -> None:
        self.chamadas: list[list[str]] = []
        self.saida = saida

    def __call__(self, argv: list[str]) -> str | None:
        self.chamadas.append(argv)
        if argv[:2] == ["pactl", "load-module"]:
            return self.saida
        return ""


def test_source_carrega_module_pipe_source_com_o_formato_do_mic(monkeypatch, tmp_path) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path))
    monkeypatch.setattr(bt.shutil, "which", lambda _n: "/usr/bin/pactl")
    runner = _RunnerFalso()
    src = bt.SourceVirtualPipeWire(nome="hef_teste", descricao="Teste", runner=runner)
    # `_abrir_fifo` falha (não há PipeWire de verdade): o start recua inteiro.
    assert src.iniciar() is False
    argv = runner.chamadas[0]
    assert argv[:3] == ["pactl", "load-module", "module-pipe-source"]
    assert "source_name=hef_teste" in argv
    assert "format=s16le" in argv
    assert f"rate={bt.MIC_TAXA_HZ}" in argv
    assert f"channels={bt.MIC_CANAIS}" in argv
    # Recuou de verdade: o módulo carregado foi descarregado.
    assert ["pactl", "unload-module", "42"] in runner.chamadas


def test_source_nao_publica_quando_o_load_module_falha(monkeypatch, tmp_path) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path))
    monkeypatch.setattr(bt.shutil, "which", lambda _n: "/usr/bin/pactl")
    runner = _RunnerFalso(saida=None)
    src = bt.SourceVirtualPipeWire(nome="hef_teste", descricao="Teste", runner=runner)
    assert src.iniciar() is False
    assert not any(c[1] == "unload-module" for c in runner.chamadas)


def test_source_sem_pactl_nao_tenta_nada(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr(bt.shutil, "which", lambda _n: None)
    runner = _RunnerFalso()
    src = bt.SourceVirtualPipeWire(nome="hef_teste", descricao="Teste", runner=runner)
    assert src.iniciar() is False
    assert runner.chamadas == []


def test_escrita_no_fifo_nunca_bloqueia(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """Fifo cheio ⇒ descarte contado, nunca uma thread pendurada."""
    fifo = tmp_path / "f"
    os.mkfifo(fifo)
    leitor = os.open(fifo, os.O_RDONLY | os.O_NONBLOCK)
    try:
        src = bt.SourceVirtualPipeWire(nome="hef_teste", descricao="Teste")
        src._fifo = str(fifo)
        assert src.escrever(b"\x00" * 64) is True
        # Enche o pipe: em algum momento o EAGAIN aparece e vira descarte.
        for _ in range(4096):
            src.escrever(b"\x00" * 4096)
        assert src.descartes > 0
        src.parar()
    finally:
        os.close(leitor)


# ---------------------------------------------------------------------------
# 7. Gerenciador (hotplug)
# ---------------------------------------------------------------------------


class _PonteFalsa:
    def __init__(self, no: bt.NoDualSenseBT, *, sobe: bool = True) -> None:
        self.no = no
        self.sobe = sobe
        self.parada = False

    def iniciar(self) -> bool:
        return self.sobe

    def parar(self) -> None:
        self.parada = True


def _no(caminho: str) -> bt.NoDualSenseBT:
    return bt.NoDualSenseBT(caminho=caminho, uniq="aa:bb:cc:dd:ee:ff", produto=0x0CE6)


def test_gerenciador_sobe_uma_ponte_por_controle() -> None:
    g = bt.GerenciadorMicBluetooth(fabrica=_PonteFalsa)
    g.reconciliar([_no("/dev/hidraw6"), _no("/dev/hidraw7")])
    assert sorted(g.pontes) == ["/dev/hidraw6", "/dev/hidraw7"]


def test_gerenciador_e_idempotente() -> None:
    g = bt.GerenciadorMicBluetooth(fabrica=_PonteFalsa)
    g.reconciliar([_no("/dev/hidraw6")])
    primeira = g.pontes["/dev/hidraw6"]
    g.reconciliar([_no("/dev/hidraw6")])
    assert g.pontes["/dev/hidraw6"] is primeira


def test_gerenciador_derruba_a_ponte_do_controle_que_sumiu() -> None:
    g = bt.GerenciadorMicBluetooth(fabrica=_PonteFalsa)
    g.reconciliar([_no("/dev/hidraw6")])
    ponte = g.pontes["/dev/hidraw6"]
    g.reconciliar([])
    assert g.pontes == {}
    assert ponte.parada is True


def test_gerenciador_nao_guarda_ponte_que_nao_subiu() -> None:
    g = bt.GerenciadorMicBluetooth(
        fabrica=lambda no: _PonteFalsa(no, sobe=False)
    )
    g.reconciliar([_no("/dev/hidraw6")])
    assert g.pontes == {}


def test_gerenciador_sobrevive_a_ponte_que_levanta() -> None:
    def _explode(_no: bt.NoDualSenseBT) -> object:
        raise RuntimeError("boom")

    g = bt.GerenciadorMicBluetooth(fabrica=_explode)
    g.reconciliar([_no("/dev/hidraw6")])  # não pode propagar
    assert g.pontes == {}


def test_dormir_acorda_no_parar() -> None:
    """O laço DORME num Event — `parar()` o acorda na hora, sem polling."""
    g = bt.GerenciadorMicBluetooth(fabrica=_PonteFalsa)
    t0 = time.monotonic()
    threading.Timer(0.05, g.parar).start()
    assert g.dormir(5.0) is True
    assert time.monotonic() - t0 < 2.0


# ---------------------------------------------------------------------------
# 8. Diagnóstico
# ---------------------------------------------------------------------------


def test_diagnostico_sem_controle_nao_esta_pronto() -> None:
    d = bt.Diagnostico(controles=[], libopus="1.4", pactl=True, pipe_source=True, broker=True)
    assert d.pronto is False
    assert any("Bluetooth" in i for i in d.impedimentos)


def test_diagnostico_sem_libopus_diz_o_que_instalar() -> None:
    d = bt.Diagnostico(
        controles=[_no("/dev/hidraw6")],
        libopus=None,
        pactl=True,
        pipe_source=True,
        broker=True,
    )
    assert d.pronto is False
    assert any("libopus0" in i for i in d.impedimentos)


def test_diagnostico_completo_esta_pronto() -> None:
    d = bt.Diagnostico(
        controles=[_no("/dev/hidraw6")],
        libopus="libopus 1.4",
        pactl=True,
        pipe_source=True,
        broker=True,
    )
    assert d.pronto is True
    assert d.impedimentos == []


# ---------------------------------------------------------------------------
# 9. Subsystem do daemon (opt-in)
# ---------------------------------------------------------------------------


class _ConfigFalsa:
    """DaemonConfig o bastante para o gate — sem importar o lifecycle inteiro."""

    def __init__(self, **campos: object) -> None:
        self.__dict__.update(campos)


class _GerenciadorFalso:
    def __init__(self) -> None:
        self.reconciliacoes = 0
        self.parado = False
        self._evt = threading.Event()

    def reconciliar(self) -> None:
        self.reconciliacoes += 1

    def dormir(self, _s: float) -> bool:
        return self._evt.wait(0.01)

    def parar(self) -> None:
        self.parado = True
        self._evt.set()


def test_subsystem_nasce_desligado() -> None:
    """Microfone que liga sozinho no boot do daemon é inaceitável."""
    from hefesto_dualsense4unix.daemon.subsystems.bt_mic import BtMicSubsystem

    assert BtMicSubsystem().is_enabled(_ConfigFalsa()) is False


def test_subsystem_liga_por_env(monkeypatch: pytest.MonkeyPatch) -> None:
    from hefesto_dualsense4unix.daemon.subsystems import bt_mic

    monkeypatch.setenv(bt_mic.ENV_HABILITA, "1")
    assert bt_mic.BtMicSubsystem().is_enabled(_ConfigFalsa()) is True


def test_subsystem_liga_por_campo_de_config() -> None:
    from hefesto_dualsense4unix.daemon.subsystems.bt_mic import BtMicSubsystem

    assert BtMicSubsystem().is_enabled(_ConfigFalsa(bt_mic_enabled=True)) is True


def test_habilitado_por_env_aceita_as_grafias_usuais() -> None:
    from hefesto_dualsense4unix.daemon.subsystems.bt_mic import (
        ENV_HABILITA,
        habilitado_por_env,
    )

    for valor in ("1", "true", "TRUE", "yes", "on"):
        assert habilitado_por_env({ENV_HABILITA: valor}) is True
    for valor in ("", "0", "false", "no", "talvez"):
        assert habilitado_por_env({ENV_HABILITA: valor}) is False


@pytest.mark.asyncio
async def test_subsystem_sobe_e_para_o_gerenciador() -> None:
    from hefesto_dualsense4unix.daemon.subsystems.bt_mic import BtMicSubsystem

    g = _GerenciadorFalso()
    sub = BtMicSubsystem(gerenciador=g)
    await sub.start(None)  # type: ignore[arg-type]
    assert _esperar(lambda: g.reconciliacoes >= 1)
    await sub.stop()
    assert g.parado is True
    await sub.stop()  # idempotente
