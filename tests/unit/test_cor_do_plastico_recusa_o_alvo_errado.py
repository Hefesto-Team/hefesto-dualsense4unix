"""COR-DO-PLASTICO-01 — as travas do único instrumento que ESCREVE no aparelho."""
from __future__ import annotations

import array
import errno
import importlib.util
import os
import socket
import sys
import zlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.core.ds_output_report import BT_FEATURE_CRC_SEED, bt_crc32

_RAIZ = Path(__file__).resolve().parents[2]
_INSTRUMENTO = _RAIZ / "scripts" / "ensaios" / "cor_do_plastico.py"


def _carregar_o_instrumento() -> tuple[Any, Any]:
    """Carrega o instrumento pelo caminho, como o precedente desta pasta manda."""
    pasta = str(_INSTRUMENTO.parent)
    if pasta not in sys.path:
        sys.path.insert(0, pasta)
    especificacao = importlib.util.spec_from_file_location(
        "cor_do_plastico_sob_ensaio", _INSTRUMENTO
    )
    if especificacao is None or especificacao.loader is None:
        raise AssertionError(f"não consegui carregar {_INSTRUMENTO}")
    modulo = importlib.util.module_from_spec(especificacao)
    sys.modules[especificacao.name] = modulo
    especificacao.loader.exec_module(modulo)
    return modulo, sys.modules["comum"]


COR, COMUM = _carregar_o_instrumento()

MAC_DO_ALVO = "aa:bb:cc:dd:ee:03"
MAC_DO_OUTRO_NO = "aa:bb:cc:dd:ee:09"

SERIAL_FORJADO = "ZZ9Y02Q0000000000"  # serial-de-mentira: prefixo forjado
COR_DO_SERIAL_FORJADO = "Cosmic Red"

FIRMWARE_FORJADO = b"FIRMWARE FORJADO"

CRC_DO_ENVELOPE = 0x73460D93
CRC_CORROMPIDO = 0x8C460D93

_NR_GETFEATURE = 0x07
_NR_SETFEATURE = 0x06


class FcntlDeMentira:
    """Um `fcntl` que ANOTA os ioctl em vez de executá-los. Nada vai ao fio."""

    def __init__(self) -> None:
        self.escritas: list[bytes] = []
        self.leituras: list[int] = []

    @property
    def resposta_do_serial(self) -> bytes:
        corpo = bytes([COR.FEATURE_RESPOSTA, COR.BASE_DO_SERIAL, COR.NUM_DO_SERIAL, 2])
        corpo += SERIAL_FORJADO.encode("ascii")
        return corpo.ljust(64, b"\x00")

    @property
    def resposta_do_firmware(self) -> bytes:
        return (bytes([COR.FEATURE_FIRMWARE]) + FIRMWARE_FORJADO).ljust(64, b"\x00")

    def ioctl(self, _fd: int, requisicao: int, buffer: Any, _mutar: bool = False) -> int:
        numero = requisicao & 0xFF
        tamanho = (requisicao >> 16) & 0x3FFF
        if numero == _NR_SETFEATURE:
            self.escritas.append(bytes(buffer))
            return len(buffer)
        if numero != _NR_GETFEATURE:
            raise AssertionError(f"ioctl que este ensaio não conhece: 0x{requisicao:08x}")
        pedido = int(buffer[0])
        self.leituras.append(pedido)
        if pedido == COR.FEATURE_FIRMWARE:
            resposta = self.resposta_do_firmware
        elif pedido == COR.FEATURE_RESPOSTA:
            if not self.escritas:
                raise OSError(errno.EPIPE, "ninguém pediu nada a este aparelho")
            resposta = self.resposta_do_serial
        else:
            raise AssertionError(f"feature que este ensaio não conhece: 0x{pedido:02x}")
        resposta = resposta[:tamanho]
        buffer[: len(resposta)] = array.array("B", resposta)
        return len(resposta)


@dataclass
class NoDeMentira:
    """O que `abrir_no_hidraw` devolveria — sem abrir coisa nenhuma."""

    fd: int
    porta: str = "bancada de mentira"
    motivo: str = "socketpair local; nenhum /dev/hidraw foi aberto"
    fechado: bool = False

    def fechar(self) -> None:
        self.fechado = True


@dataclass
class Bancada:
    """A mesa de mentira de uma execução: o alvo, o outro nó, e os espiões."""

    alvo: Any
    outro: Any
    fcntl: FcntlDeMentira
    aberturas: list[str] = field(default_factory=list)
    nos: list[NoDeMentira] = field(default_factory=list)

    @property
    def alvos(self) -> list[Any]:
        return [self.alvo, self.outro]


def _aparelho(dir_device: Path, *, hidraw: str, mac: str, transporte: str) -> Any:
    return COMUM.Aparelho(
        hidraw=hidraw,
        caminho_hidraw=f"/dev/{hidraw}-que-nao-existe",
        dir_device=str(dir_device),
        mac=mac,
        nome="DualSense de mentira",
        transporte=transporte,
        e_vpad=False,
        rotulo="",
    )


@pytest.fixture()
def bancada(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Bancada:
    """A mesa inteira substituída: descritor, porta, `fcntl` e reports."""
    device = tmp_path / "sysfs-do-alvo"
    device.mkdir()
    (device / "hardware_version").write_text("0x00000811\n", encoding="utf-8")

    esquerda, direita = socket.socketpair(socket.AF_UNIX, socket.SOCK_DGRAM)
    for _ in range(8):
        direita.send(bytes([0x01]) + b"\x00" * 63)

    falso = FcntlDeMentira()
    mesa = Bancada(
        alvo=_aparelho(device, hidraw="hidraw4", mac=MAC_DO_ALVO, transporte=COMUM.CABO),
        outro=_aparelho(device, hidraw="hidraw9", mac=MAC_DO_OUTRO_NO, transporte=COR.RADIO),
        fcntl=falso,
    )

    def _abrir(caminho: str, *, escrita: bool = True) -> NoDeMentira:
        mesa.aberturas.append(caminho)
        no = NoDeMentira(fd=esquerda.fileno())
        mesa.nos.append(no)
        return no

    monkeypatch.setattr(COR, "fcntl", falso)
    monkeypatch.setattr(COR, "abrir_no_hidraw", _abrir)
    monkeypatch.setattr(
        COR,
        "tamanhos_do_descritor",
        lambda _dir: {"feature": {0x20: 64, 0x80: 64, 0x81: 64}},
    )
    try:
        yield mesa
    finally:
        esquerda.close()
        direita.close()


def _como_o_main(mesa: Bancada, pedido: str, **argumentos: Any) -> Any:
    """A MESMA ordem do `_corpo()`: escolher o alvo e SÓ ENTÃO medir."""
    exigir_mac = argumentos.pop("exigir_mac", "")
    aparelho = COR.escolher_alvo(mesa.alvos, pedido, exigir_mac=exigir_mac)
    return COR.medir(
        aparelho,
        escrever=argumentos.pop("escrever", False),
        radio_a_serio=argumentos.pop("radio_a_serio", False),
        com_crc=argumentos.pop("com_crc", True),
    )


def test_exigir_mac_com_o_mac_do_no_devolve_o_alvo(bancada: Bancada) -> None:
    """O caso feliz, e ele importa: uma trava que recusa tudo não é trava."""
    escolhido = COR.escolher_alvo(bancada.alvos, "hidraw4", exigir_mac=MAC_DO_ALVO)
    assert escolhido is bancada.alvo

    assert (
        COR.escolher_alvo(bancada.alvos, "/dev/hidraw4", exigir_mac=MAC_DO_ALVO.upper())
        is bancada.alvo
    )


def test_exigir_mac_do_outro_no_recusa_antes_de_abrir_a_porta(bancada: Bancada) -> None:
    """A mordida provada à mão: pedir um nó exigindo o MAC de OUTRO controle."""
    with pytest.raises(SystemExit) as caiu:
        _como_o_main(bancada, "hidraw4", exigir_mac=MAC_DO_OUTRO_NO, escrever=True)

    recado = str(caiu.value)
    assert "NÃO é o controle que você pediu" in recado
    assert "NADA foi ao aparelho" in recado

    assert bancada.aberturas == []
    assert bancada.fcntl.escritas == []
    assert bancada.fcntl.leituras == []


def test_a_recusa_do_mac_nao_imprime_o_endereco_inteiro(bancada: Bancada) -> None:
    """A recusa é texto que vai para transcrito versionado — e ele é mascarado."""
    with pytest.raises(SystemExit) as caiu:
        COR.escolher_alvo(bancada.alvos, "hidraw4", exigir_mac=MAC_DO_OUTRO_NO)

    recado = str(caiu.value)
    assert "aa:bb:cc:00:00:03" in recado
    assert "aa:bb:cc:00:00:09" in recado
    assert "dd:ee" not in recado


def test_o_envelope_de_radio_integro_passa_e_o_rabo_e_o_medido(
    bancada: Bancada, capsys: pytest.CaptureFixture[str]
) -> None:
    """O envelope montado pelo instrumento é aceito, e o CRC é o de 14:46."""
    envelope = COR.envelope_de_radio(COR.montar_payload(64))
    capsys.readouterr()

    assert int.from_bytes(envelope[-4:], "little") == CRC_DO_ENVELOPE
    assert bytes(envelope[:3]) == bytes([0x80, 0x01, 0x13])

    falha = COR.mandar_o_comando(4242, bytearray(envelope), bytes_de_crc=4)

    assert falha == ""
    assert bancada.fcntl.escritas == [bytes(envelope)]


def test_o_rabo_de_crc_corrompido_reprova(bancada: Bancada) -> None:
    """A mordida literal do transcrito: veio `0x8c460d93`, recalculado `0x73460d93`."""
    envelope = COR.envelope_de_radio(COR.montar_payload(64))
    envelope[-1] ^= 0xFF

    with pytest.raises(COR.PayloadRecusadoError) as caiu:
        COR.mandar_o_comando(4242, envelope, bytes_de_crc=4)

    recado = str(caiu.value)
    assert f"veio 0x{CRC_CORROMPIDO:08x}" in recado
    assert f"recalculado 0x{CRC_DO_ENVELOPE:08x}" in recado
    assert bancada.fcntl.escritas == []


def test_o_miolo_continua_conferido_por_tras_do_crc(bancada: Bancada) -> None:
    """Conhecer o rabo não pode afrouxar o miolo — foi essa a promessa da cura."""
    payload = COR.montar_payload(64)
    payload[5] = 0x01
    envelope = COR.envelope_de_radio(payload)

    with pytest.raises(COR.PayloadRecusadoError) as caiu:
        COR.mandar_o_comando(4242, envelope, bytes_de_crc=4)

    assert "vieram sujos" in str(caiu.value)
    assert bancada.fcntl.escritas == []


def test_o_par_que_reseta_o_controle_e_recusado(bancada: Bancada) -> None:
    """`[1,1]` reseta o aparelho. A trava tem de conhecê-lo pelo nome."""
    payload = COR.montar_payload(64)
    payload[2] = 1

    with pytest.raises(COR.PayloadRecusadoError):
        COR.mandar_o_comando(4242, payload)

    assert bancada.fcntl.escritas == []


def test_a_semente_do_instrumento_e_a_mesma_do_pacote() -> None:
    """O instrumento copia a semente para rodar sem o pacote; a cópia é presa aqui."""
    assert COR.SEMENTE_FEATURE_BT == BT_FEATURE_CRC_SEED

    miolo = bytes(COR.montar_payload(64))[:60]
    daqui = zlib.crc32(bytes([COR.SEMENTE_FEATURE_BT]) + miolo) & 0xFFFFFFFF
    assert daqui == bt_crc32(miolo, seed=BT_FEATURE_CRC_SEED) == CRC_DO_ENVELOPE


def test_conferir_a_semente_diz_de_onde_veio_o_numero() -> None:
    """A conferência roda em tempo de execução e nomeia a outra cópia."""
    dito = COR.conferir_a_semente()
    assert dito.startswith(f"0x{BT_FEATURE_CRC_SEED:02x},")
    assert "core/ds_output_report.py::BT_FEATURE_CRC_SEED" in dito


def test_mascarar_serial_deixa_seis_publicos_e_o_resto_em_cerquilha() -> None:
    mascarado = COR.mascarar_serial(SERIAL_FORJADO)

    assert mascarado == "ZZ9Y02###########"
    assert len(mascarado) == len(SERIAL_FORJADO)
    assert mascarado[:6] == SERIAL_FORJADO[:6]
    assert set(mascarado[6:]) == {"#"}
    assert mascarado[COR.FATIA_DA_COR] == "02"
    assert SERIAL_FORJADO[6:] not in mascarado


def test_mascarar_serial_curto_nao_inventa_caractere() -> None:
    assert COR.mascarar_serial("ZZ9Y02") == "ZZ9Y02"
    assert COR.mascarar_serial("") == ""


def test_sem_o_serial_mascara_tambem_o_hexadecimal() -> None:
    """`4d 36 35` é o serial tanto quanto `M65` — o dump também tem de mascarar."""
    resposta = FcntlDeMentira().resposta_do_serial
    limpa = COR.sem_o_serial(resposta)

    inicio = 4 + COR.CARACTERES_PUBLICOS_DO_SERIAL
    fim = 4 + COR.TAMANHO_DO_SERIAL
    assert limpa[:inicio] == resposta[:inicio]
    assert limpa[inicio:fim] == b"#" * (fim - inicio)
    assert SERIAL_FORJADO.encode("ascii")[6:] not in limpa
    assert limpa[:4] == bytes([COR.FEATURE_RESPOSTA, 1, 19, 2])


def test_mascarar_mac_zera_os_octetos_quatro_e_cinco() -> None:
    assert COR.mascarar("aa:bb:cc:dd:ee:ff") == "aa:bb:cc:00:00:ff"
    assert COR.mascarar("") == ""
    assert COR.mascarar("sem forma de endereço") == "sem forma de endereço"


def test_sem_escrever_nada_vai_ao_fio(
    bancada: Bancada, capsys: pytest.CaptureFixture[str]
) -> None:
    """Seco por omissão: o instrumento chega até a beira da escrita e para."""
    medida = _como_o_main(bancada, "hidraw4", exigir_mac=MAC_DO_ALVO, escrever=False)
    tela = capsys.readouterr().out

    assert bancada.fcntl.escritas == []
    assert medida.escreveu is False
    assert medida.serial.texto == ""

    assert bancada.aberturas == [bancada.alvo.caminho_hidraw]
    assert COR.FEATURE_FIRMWARE in bancada.fcntl.leituras
    assert medida.antes.vivo is True
    assert "RODADA SECA" in tela
    assert "--escrever" in tela


def test_com_escrever_sai_exatamente_um_set_feature(
    bancada: Bancada, capsys: pytest.CaptureFixture[str]
) -> None:
    """A contraprova do teste acima: com a autorização, o comando sai — UM."""
    medida = _como_o_main(bancada, "hidraw4", exigir_mac=MAC_DO_ALVO, escrever=True)
    capsys.readouterr()

    esperado = bytes([0x80, 0x01, 0x13]) + b"\x00" * 61
    assert bancada.fcntl.escritas == [esperado]
    assert medida.escreveu is True
    assert medida.serial.texto == SERIAL_FORJADO
    assert medida.serial.codigo_da_cor == "02"
    assert medida.serial.nome_da_cor == COR_DO_SERIAL_FORJADO
    assert medida.continua_sao is True
    assert bancada.nos[0].fechado is True


def test_a_tela_nunca_mostra_o_serial_em_hexadecimal(
    bancada: Bancada, capsys: pytest.CaptureFixture[str]
) -> None:
    """O dump da resposta sai mascarado já na tela; o texto decodificado, não."""
    _como_o_main(bancada, "hidraw4", exigir_mac=MAC_DO_ALVO, escrever=True)
    tela = capsys.readouterr().out

    em_hexadecimal = SERIAL_FORJADO.encode("ascii")[6:].hex(" ")
    assert em_hexadecimal not in tela


def test_radio_sem_radio_a_serio_nao_abre_a_porta(
    bancada: Bancada, capsys: pytest.CaptureFixture[str]
) -> None:
    """Caminho novo não se estreia por omissão — nem com `--escrever` na linha."""
    medida = _como_o_main(bancada, "hidraw9", exigir_mac=MAC_DO_OUTRO_NO, escrever=True)
    tela = capsys.readouterr().out

    assert bancada.aberturas == []
    assert bancada.fcntl.escritas == []
    assert medida.escreveu is False
    assert "--radio-a-serio" in medida.erro_da_escrita
    assert "RECUSADO" in tela


def test_a_familia_do_firmware_nunca_e_escrita(bancada: Bancada) -> None:
    """A D-32 dela: ler a família `0xf0`-`0xf7`, nunca escrever."""
    for report_id in COR.FAMILIA_DO_FIRMWARE:
        payload = COR.montar_payload(64)
        payload[0] = report_id
        with pytest.raises(COR.PayloadRecusadoError) as caiu:
            COR.mandar_o_comando(4242, payload)
        assert "família do FIRMWARE" in str(caiu.value)

    assert bancada.fcntl.escritas == []


def test_o_ensaio_nao_abriu_dev_hidraw_nenhum(bancada: Bancada) -> None:
    """A guarda contra o próprio ensaio: nenhum caminho de `/dev` é real."""
    _como_o_main(bancada, "hidraw4", exigir_mac=MAC_DO_ALVO, escrever=True)

    for caminho in bancada.aberturas:
        assert caminho.startswith("/dev/hidraw")
        assert not os.path.exists(caminho)
