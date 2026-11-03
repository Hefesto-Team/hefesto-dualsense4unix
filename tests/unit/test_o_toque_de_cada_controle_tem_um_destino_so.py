"""O toque de cada controle tem um destino só (O-TOQUE-DE-CADA-CONTROLE-TEM-UM-DESTINO-SO-01).

O dedo e o clique do touchpad perguntam ao mesmo `REGISTRO.destino_do_toque`: no jogo, os dois
chegam ao pad virtual; na rota (cursor ou zonas) ou com o touchpad Desligado no jogo, nenhum dos
dois chega. Trocar o destino com o clique apertado solta o botão no pad.

O caminho roda inteiro: o report cru do físico (0x01 do cabo ou 0x31 do rádio) entra pelo laço do
`PhysicalReportReader`, um report por leitura, e o que o pad escreve (o evento do uhid ou o report
do gadget) sai num pipe, onde a régua lê o corpo que o jogo veria.
"""
from __future__ import annotations

import os
import socket
import struct
from collections.abc import Iterator

import pytest

from hefesto_dualsense4unix.core.ds_output_report import BT_INPUT_CRC_SEED, bt_crc32
from hefesto_dualsense4unix.core.physical_report_reader import (
    BUTTONS2_OFFSET,
    INPUT_REPORT_BT_SIZE,
    TOUCHPAD_CLICK_BIT,
    PhysicalReportReader,
)
from hefesto_dualsense4unix.core.virtual_motion import (
    DESTINO_JOGO,
    DESTINO_MUDO,
    DESTINO_ROTA,
    REGISTRO,
)
from hefesto_dualsense4unix.integrations.uhid_gamepad import (
    UHID_INPUT2,
    UhidDualSense,
    _GadgetDoPad,
)
from hefesto_dualsense4unix.integrations.uinput_gamepad import UinputGamepad

MACS = {n: f"AA:BB:CC:00:00:0{n}" for n in (1, 2, 3, 4)}
PRODUTO = {"dualsense": 0x0CE6, "edge": 0x0DF2}
DESTINO_DA_MESA = {1: "jogo", 2: "cursor", 3: "zonas", 4: "desligado"}
ESPERADO = {"jogo": DESTINO_JOGO, "cursor": DESTINO_ROTA, "zonas": DESTINO_ROTA,
            "desligado": DESTINO_MUDO}

JOGADORES = (1, 2, 3, 4)
MODOS_DO_PAD = ("dualsense", "edge")
VIAS = ("cabo", "radio")
CAMINHOS = ("uhid", "gadget")

_CONTATO = 32
_SEM_DEDO = 0x80


@pytest.fixture(autouse=True)
def _registro_limpo() -> Iterator[None]:
    REGISTRO.limpar()
    yield
    REGISTRO.limpar()


def _a_mesa(*, com_rota: bool = True) -> None:
    """Os quatro com jogo aberto; com rota, cada um com o destino de `DESTINO_DA_MESA`."""
    REGISTRO.definir_jogo(True)
    if not com_rota:
        REGISTRO.definir_roteados(sem_chip=False, por_peca={})
        return
    REGISTRO.definir_roteados(
        sem_chip=False,
        por_peca={},
        toque_por_peca={MACS[n]: DESTINO_DA_MESA[n] in ("cursor", "zonas") for n in JOGADORES},
    )
    for n in JOGADORES:
        REGISTRO.definir_touchpad(MACS[n], ligado=DESTINO_DA_MESA[n] != "desligado")


def _corpo(*, dedo: bool, clique: bool, marca: int) -> bytes:
    corpo = bytearray(63)
    corpo[0:4] = bytes([0x80, 0x80, 0x80, 0x80])
    corpo[15] = marca & 0xFF
    corpo[_CONTATO] = 0x00 if dedo else _SEM_DEDO
    corpo[36] = _SEM_DEDO
    if dedo:
        corpo[_CONTATO + 1] = 0x40 + (marca & 0x0F)
    if clique:
        corpo[BUTTONS2_OFFSET] |= TOUCHPAD_CLICK_BIT
    return bytes(corpo)


def _report(via: str, *, dedo: bool, clique: bool, marca: int) -> bytes:
    """O report cru do físico: 0x01 de 64 B pelo cabo, 0x31 de 78 B com CRC pelo rádio."""
    corpo = _corpo(dedo=dedo, clique=clique, marca=marca)
    if via == "cabo":
        return bytes([0x01]) + corpo
    raw = bytearray(INPUT_REPORT_BT_SIZE)
    raw[0], raw[1] = 0x31, 0x01
    raw[2 : 2 + len(corpo)] = corpo
    raw[-4:] = bt_crc32(raw[:-4], seed=BT_INPUT_CRC_SEED).to_bytes(4, "little")
    return bytes(raw)


class _Ponta:
    """Um jogador: o pad virtual escrevendo num pipe e o leitor do físico dele."""

    def __init__(self, player: int, modo: str, caminho: str) -> None:
        self.caminho = caminho
        self.pad = UhidDualSense(player=player, product=PRODUTO[modo])
        self._saida_r, saida_w = os.pipe()
        os.set_blocking(self._saida_r, False)
        if caminho == "gadget":
            self.pad._gadget = _GadgetDoPad(
                cliente=None, fd=saida_w, gadget="g", serial=f"hefesto-pad-{player}"
            )
        self.pad._fd = saida_w
        self.leitor = PhysicalReportReader(lambda: None, self.pad)
        self.leitor._uniq_aberto = MACS[player]
        self._marca = 0

    def fisico(self, via: str, *reports: tuple[bool, bool]) -> None:
        """O físico manda `(dedo, clique)` em sequência, um report por leitura do hidraw."""
        de_la, de_ca = socket.socketpair(socket.AF_UNIX, socket.SOCK_SEQPACKET)
        try:
            for dedo, clique in reports:
                self._marca += 1
                de_la.send(_report(via, dedo=dedo, clique=clique, marca=self._marca))
            de_la.close()
            self.leitor._read_until_lost(de_ca.fileno(), 5.0)
        finally:
            de_ca.close()

    def corpos(self) -> list[bytes]:
        """Os corpos do 0x01 que o pad entregou ao jogo, sem o id."""
        bruto = b""
        while True:
            try:
                pedaco = os.read(self._saida_r, 65536)
            except BlockingIOError:
                break
            if not pedaco:
                break
            bruto += pedaco
        saida: list[bytes] = []
        if self.caminho == "gadget":
            for i in range(0, len(bruto), 64):
                if bruto[i] == 0x01:
                    saida.append(bruto[i + 1 : i + 64])
            return saida
        i = 0
        while i + 6 <= len(bruto):
            tipo, tamanho = struct.unpack_from("<IH", bruto, i)
            report = bruto[i + 6 : i + 6 + tamanho]
            i += 6 + tamanho
            if tipo == UHID_INPUT2 and report[:1] == b"\x01":
                saida.append(report[1:])
        return saida

    def fechar(self) -> None:
        os.close(self._saida_r)
        os.close(self.pad._fd)


@pytest.fixture()
def pontas() -> Iterator[list[_Ponta]]:
    abertas: list[_Ponta] = []
    yield abertas
    for ponta in abertas:
        ponta.fechar()


def _dedo(corpo: bytes) -> bool:
    return not corpo[_CONTATO] & _SEM_DEDO


def _clique(corpo: bytes) -> bool:
    return bool(corpo[BUTTONS2_OFFSET] & TOUCHPAD_CLICK_BIT)


_APERTA_E_SOLTA = ((False, False), (True, False), (True, True), (True, True), (True, False))


@pytest.mark.parametrize("caminho", CAMINHOS)
@pytest.mark.parametrize("via", VIAS)
@pytest.mark.parametrize("modo", MODOS_DO_PAD)
@pytest.mark.parametrize("player", JOGADORES)
def test_o_dedo_e_o_clique_chegam_juntos_ou_nenhum(
    pontas: list[_Ponta], player: int, modo: str, via: str, caminho: str
) -> None:
    _a_mesa()
    destino = DESTINO_DA_MESA[player]
    assert REGISTRO.destino_do_toque(MACS[player]) == ESPERADO[destino]
    ponta = _Ponta(player, modo, caminho)
    pontas.append(ponta)

    ponta.fisico(via, *_APERTA_E_SOLTA)

    corpos = ponta.corpos()
    assert corpos, "o movimento parou de chegar ao pad"
    com_dedo = any(_dedo(c) for c in corpos)
    com_clique = any(_clique(c) for c in corpos)
    if destino == "jogo":
        assert com_dedo and com_clique, (player, destino, com_dedo, com_clique)
    else:
        assert not com_dedo and not com_clique, (player, destino, com_dedo, com_clique)


@pytest.mark.parametrize("caminho", CAMINHOS)
@pytest.mark.parametrize("via", VIAS)
@pytest.mark.parametrize("modo", MODOS_DO_PAD)
@pytest.mark.parametrize("player", (2, 3, 4))
def test_trocar_o_destino_com_o_clique_apertado_solta_o_botao(
    pontas: list[_Ponta], player: int, modo: str, via: str, caminho: str
) -> None:
    REGISTRO.definir_jogo(True)
    ponta = _Ponta(player, modo, caminho)
    pontas.append(ponta)
    ponta.fisico(via, (True, True))
    antes = ponta.corpos()
    assert antes and _clique(antes[-1]) and _dedo(antes[-1]), "no jogo, o apertado chega"

    _a_mesa()
    ponta.fisico(via, (True, True))
    fora = ponta.corpos()
    assert fora, "o pad tem de ouvir a troca"
    assert not _clique(fora[-1]) and not _dedo(fora[-1]), DESTINO_DA_MESA[player]
    assert not any(_clique(c) for c in fora)

    ponta.fisico(via, (True, True), (True, True))
    seguindo = ponta.corpos()
    assert not any(_clique(c) or _dedo(c) for c in seguindo), "fora do jogo, o apertado não volta"

    REGISTRO.limpar()
    REGISTRO.definir_jogo(True)
    ponta.fisico(via, (True, True))
    de_volta = ponta.corpos()
    assert de_volta and _clique(de_volta[-1]) and _dedo(de_volta[-1]), (
        "de volta ao jogo, o próximo report entrega o estado real"
    )


@pytest.mark.parametrize("caminho", CAMINHOS)
@pytest.mark.parametrize("via", VIAS)
@pytest.mark.parametrize("modo", MODOS_DO_PAD)
def test_o_perfil_sem_rota_leva_os_quatro_ao_jogo(
    pontas: list[_Ponta], modo: str, via: str, caminho: str
) -> None:
    _a_mesa(com_rota=False)
    for player in JOGADORES:
        assert REGISTRO.destino_do_toque(MACS[player]) == DESTINO_JOGO
        ponta = _Ponta(player, modo, caminho)
        pontas.append(ponta)
        ponta.fisico(via, *_APERTA_E_SOLTA)
        corpos = ponta.corpos()
        assert any(_dedo(c) for c in corpos), player
        assert any(_clique(c) for c in corpos), player


def test_o_desligado_fora_do_jogo_segue_o_mesmo_destino_do_dedo() -> None:
    REGISTRO.definir_touchpad(MACS[4], ligado=False)
    REGISTRO.definir_jogo(False)
    REGISTRO.desligado_fora_do_jogo = "cursor"
    assert REGISTRO.destino_do_toque(MACS[4]) == DESTINO_JOGO
    REGISTRO.desligado_fora_do_jogo = "mudo"
    assert REGISTRO.destino_do_toque(MACS[4]) == DESTINO_MUDO
    REGISTRO.definir_jogo(True)
    REGISTRO.desligado_fora_do_jogo = "cursor"
    assert REGISTRO.destino_do_toque(MACS[4]) == DESTINO_MUDO


def test_o_pad_xbox_nao_tem_touchpad() -> None:
    """No Xbox, nada do toque chega ao pad: o leitor só entrega a quem tem o método."""
    assert not hasattr(UinputGamepad, "forward_touchpad_click")
    assert not hasattr(UinputGamepad, "forward_motion")
