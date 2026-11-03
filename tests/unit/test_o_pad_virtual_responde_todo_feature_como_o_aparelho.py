"""O pad virtual responde todo feature como o aparelho — O-PAD-VIRTUAL-RESPONDE-TODO-FEATURE.

Medido em 02/11/2026 no hidraw do pad-0 pelo gadget: o `0x22`, que o pad não guarda, voltou
como 64 bytes zerados com sucesso, e um firmware `0x0000` é o que um jogo lê numa resposta
zerada. O uhid respondia `get(id, b"")` com `err=0`, e o `f_hid` respondia zeros ao id gravado
com tamanho zero, ao que ninguém respondeu e ao que o `hidg_disable` largou.

A régua, nos quatro eixos (P1 a P4 juntos, o modo DualSense e Edge, o caminho uhid e gadget,
o físico pelo cabo e pelo rádio), confere que todo id guardado sai igual ao do físico, que o
id desconhecido sai como erro e que um pedido no meio da recriação nunca sai zerado com
sucesso. O gadget é o `f_hid` da casa por um modelo: o que ele faz em C está cobrado pelo
fonte, no último teste.
"""

from __future__ import annotations

import errno
import os
import select
import struct
from collections.abc import Iterator
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from hefesto_dualsense4unix.integrations import pad_usb
from hefesto_dualsense4unix.integrations import uhid_gamepad as uhid
from hefesto_dualsense4unix.integrations.uhid_blueprint import (
    CANONICAL_FEATURE_0X20,
    TEMPLATE_FEATURE_0X09,
    canonical_blueprint,
)

RAIZ = Path(__file__).resolve().parents[2]
F_HID = RAIZ / "assets" / "dkms" / "usb-f-hid" / "f_hid.c"
DUALSENSE, EDGE = 0x0CE6, 0x0DF2
GUARDADOS = (0x05, 0x09, 0x20)
DESCONHECIDOS = (0x08, 0x22, 0x60, 0x6F, 0xF6)
ERRO = "erro"


def _calibracao(transporte: str, player: int) -> bytes:
    """O `0x05` de uma unidade: 41 bytes, por peça e por transporte."""
    base = 0x40 if transporte == "cabo" else 0x90
    return bytes([0x05]) + bytes((base + player * 3 + i) & 0xFF for i in range(40))


class _OsQueGrava:
    """O `os` do pad uhid: grava cada escrita no fd e não toca nó nenhum."""

    def __init__(self, real: Any) -> None:
        self._real = real
        self.escritas: list[tuple[int, bytes]] = []

    def __getattr__(self, nome: str) -> Any:
        return getattr(self._real, nome)

    def write(self, fd: int, dados: bytes) -> int:
        self.escritas.append((fd, bytes(dados)))
        return len(dados)


class _FHidDaCasa:
    """O `f_hid` com o 0001 e o 0002: a lista do kernel, o pedido ao espaço de usuário e o stall."""

    def __init__(self) -> None:
        self.lista: dict[int, bytes] = {}
        self.pendente = 0

    def ioctl(self, _fd: int, codigo: int, pacote: bytes) -> object:
        if codigo == pad_usb.GADGET_HID_READ_GET_REPORT_ID:
            return bytes([self.pendente])
        report_id, _userspace, tamanho, dados = struct.unpack("<BBH64s4x", pacote)
        self.lista[report_id] = dados[:tamanho]
        return 0

    def host_pede(self, pad: uhid.UhidDualSense | None, report_id: int) -> bytes | str:
        """O GET_REPORT do host: a lista na hora; senão o `POLLPRI` e, sem resposta, o stall."""
        if report_id not in self.lista and pad is not None and pad._fd is not None:
            self.pendente = report_id
            uhid._drenar_o_gadget(pad, pad._fd, select.POLLPRI)
        guardado = self.lista.get(report_id)
        return guardado if guardado else ERRO


class _Mesa:
    """Os quatro pads de um caminho, montados e recriados pelo código do produto."""

    def __init__(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, caminho: str,
                 modo: int) -> None:
        self.caminho = caminho
        self.modo = modo
        self.os = _OsQueGrava(os)
        self.kernels: dict[int, _FHidDaCasa] = {}
        self._pedido = 0
        no = tmp_path / "uhid-de-mentira"
        no.write_bytes(b"")
        monkeypatch.setattr(uhid, "UHID_NODE", str(no))
        monkeypatch.setattr(uhid, "os", self.os)
        monkeypatch.setattr(uhid.UhidDualSense, "_iniciar_o_fio_do_uhid", lambda *_a: None)
        monkeypatch.setattr(uhid.UhidDualSense, "_parar_o_fio_do_uhid", lambda *_a: None)
        monkeypatch.setattr(uhid, "_vigiar_a_enumeracao", lambda _pad: None)
        monkeypatch.setattr(uhid, "_GADGETS_ESTACIONADOS",
                            SimpleNamespace(retomar=lambda *_a: None))
        monkeypatch.setattr(pad_usb, "medir_a_marca_do_f_hid", lambda: True)
        gadgets: dict[int, uhid._GadgetDoPad] = {}

        def pedir(pad: uhid.UhidDualSense) -> uhid._GadgetDoPad:
            if pad.player not in gadgets:
                gadgets[pad.player] = uhid._GadgetDoPad(
                    cliente=None, fd=1000 + pad.player, gadget=f"hefesto-pad-{pad.player}",
                    serial=f"serial-{pad.player}", interface="1-1:1.0",
                )
                self.kernels[1000 + pad.player] = _FHidDaCasa()
            return gadgets[pad.player]

        def soltar(pad: uhid.UhidDualSense) -> bool:
            if pad._gadget is None:
                return False
            pad._gadget = None
            return True

        def pelo_kernel(funcao: Any) -> Any:
            def chamada(fd: int, *args: Any, **_k: Any) -> Any:
                return funcao(fd, *args, ioctl=self.kernels[fd].ioctl)
            return chamada

        monkeypatch.setattr(uhid, "_pedir_o_gadget", pedir)
        monkeypatch.setattr(uhid, "_soltar_o_gadget", soltar)
        for nome in ("escrever_get_report", "recusar_get_report", "ler_o_id_do_get_report"):
            monkeypatch.setattr(pad_usb, nome, pelo_kernel(getattr(pad_usb, nome)))

    def criar(self, player: int, transporte: str) -> uhid.UhidDualSense:
        pad = uhid.UhidDualSense(
            player=player, identity=f"aa:bb:cc:00:00:0{player}", product=self.modo,
            blueprint=canonical_blueprint(), calibration_0x05=_calibracao(transporte, player),
            sleep_fn=lambda _s: None,
        )
        pad._sem_gadget = self.caminho == "uhid"
        return pad

    def subir(self, pad: uhid.UhidDualSense) -> None:
        assert pad._criar_o_device()
        assert pad._fd is not None
        assert (pad._gadget is not None) == (self.caminho == "gadget")

    def host_pede(self, pad: uhid.UhidDualSense, report_id: int, fd: int | None = None) -> (
        bytes | str | None
    ):
        """O GET_REPORT do jogo. None = ninguém respondeu (o pad não existe mais)."""
        if self.caminho == "gadget":
            kernel = self.kernels[1000 + pad.player]
            return kernel.host_pede(pad if pad._gadget is not None else None, report_id)
        self._pedido += 1
        evento = struct.pack("<IIBB", uhid.UHID_GET_REPORT, self._pedido, report_id, 0x03)
        antes = len(self.os.escritas)
        pad._handle_event(evento.ljust(64, b"\0"))
        respostas = [
            dados for _fd, dados in self.os.escritas[antes:]
            if struct.unpack("<I", dados[:4])[0] == uhid.UHID_GET_REPORT_REPLY
        ]
        if not respostas:
            return None
        assert len(respostas) == 1
        _tipo, ident, erro, tamanho = struct.unpack("<IIHH", respostas[0][:12])
        assert ident == self._pedido
        return ERRO if erro else respostas[0][12:12 + tamanho]


def _o_do_fisico(pad: uhid.UhidDualSense, transporte: str) -> dict[int, bytes]:
    """O que o aparelho daquela peça responde a cada id que o pad guarda."""
    mac = bytearray(TEMPLATE_FEATURE_0X09)
    mac[1:7] = uhid._mac_to_report_bytes(pad.mac)
    return {
        0x05: _calibracao(transporte, pad.player),
        0x09: bytes(mac),
        0x20: CANONICAL_FEATURE_0X20,
    }


def _zerado_com_sucesso(resposta: bytes | str | None) -> bool:
    return isinstance(resposta, bytes) and not any(resposta[1:])


@pytest.fixture
def mesa_de(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Iterator[Any]:
    criadas: list[uhid.UhidDualSense] = []

    def montar(caminho: str, modo: int) -> _Mesa:
        mesa = _Mesa(monkeypatch, tmp_path, caminho, modo)
        criar = mesa.criar

        def criar_e_lembrar(player: int, transporte: str) -> uhid.UhidDualSense:
            pad = criar(player, transporte)
            criadas.append(pad)
            return pad

        mesa.criar = criar_e_lembrar  # type: ignore[method-assign]
        return mesa

    yield montar
    for pad in criadas:
        pad._destruir_o_device()


EIXOS = pytest.mark.parametrize("transporte", ["cabo", "radio"])
MODOS = pytest.mark.parametrize("modo", [DUALSENSE, EDGE], ids=["dualsense", "edge"])
CAMINHOS = pytest.mark.parametrize("caminho", ["uhid", "gadget"])


@EIXOS
@MODOS
@CAMINHOS
def test_todo_id_guardado_sai_igual_ao_do_fisico_e_o_desconhecido_sai_como_erro(
    mesa_de: Any, caminho: str, modo: int, transporte: str
) -> None:
    """`D-0311-O-FEATURE-QUE-O-PAD-VIRTUAL-NAO-GUARDA-VOLTA-COMO-ERRO`."""
    mesa = mesa_de(caminho, modo)
    pads = [mesa.criar(player, transporte) for player in (1, 2, 3, 4)]
    for pad in pads:
        mesa.subir(pad)
    for _rodada in range(3):
        for report_id in (*GUARDADOS, *DESCONHECIDOS):
            for pad in pads:
                resposta = mesa.host_pede(pad, report_id)
                if report_id in GUARDADOS:
                    assert resposta == _o_do_fisico(pad, transporte)[report_id], (
                        f"P{pad.player}: o 0x{report_id:02x} saiu diferente do físico"
                    )
                else:
                    assert resposta == ERRO, (
                        f"P{pad.player}: o 0x{report_id:02x}, que o pad não guarda, saiu como "
                        f"{resposta!r}, e não como erro"
                    )


@EIXOS
@MODOS
@CAMINHOS
def test_o_pedido_no_meio_da_recriacao_nunca_sai_zerado_com_sucesso(
    mesa_de: Any, caminho: str, modo: int, transporte: str
) -> None:
    """Troca de conexão no meio da leitura: o pad cai e nasce com o `0x05` da outra."""
    outra = "radio" if transporte == "cabo" else "cabo"
    mesa = mesa_de(caminho, modo)
    pads = [mesa.criar(player, transporte) for player in (1, 2, 3, 4)]
    for pad in pads:
        mesa.subir(pad)
    vistas: list[bytes | str | None] = []
    for pad in pads:
        pad._destruir_o_device()
        for report_id in (*GUARDADOS, *DESCONHECIDOS):
            resposta = mesa.host_pede(pad, report_id)
            vistas.append(resposta)
            if isinstance(resposta, bytes):
                assert resposta == _o_do_fisico(pad, transporte)[report_id]
    for pad in pads:
        pad.calibration_0x05 = _calibracao(outra, pad.player)
        mesa.subir(pad)
        for report_id in (*GUARDADOS, *DESCONHECIDOS):
            resposta = mesa.host_pede(pad, report_id)
            vistas.append(resposta)
            esperado = _o_do_fisico(pad, outra).get(report_id, ERRO)
            assert resposta == esperado, f"P{pad.player} 0x{report_id:02x}: {resposta!r}"
    assert not [r for r in vistas if _zerado_com_sucesso(r)]


@MODOS
def test_no_uhid_o_pedido_antes_dos_features_prontos_recebe_erro(
    mesa_de: Any, modo: int
) -> None:
    mesa = mesa_de("uhid", modo)
    pads = [mesa.criar(player, "cabo") for player in (1, 2, 3, 4)]
    for pad in pads:
        mesa.subir(pad)
        guardados, pad._features = pad._features, {}
        for report_id in GUARDADOS:
            assert mesa.host_pede(pad, report_id) == ERRO
        pad._features = guardados


def test_a_recusa_do_uhid_e_o_epipe_do_aparelho_e_a_do_gadget_e_o_tamanho_zero(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    gravadas: list[bytes] = []
    pad_usb.recusar_get_report(7, 0x22, ioctl=lambda _fd, _c, pacote: gravadas.append(pacote))
    assert struct.unpack("<BBH", gravadas[0][:4]) == (0x22, 0, 0)
    os_do_pad = _OsQueGrava(os)
    monkeypatch.setattr(uhid, "os", os_do_pad)
    pad = uhid.UhidDualSense(player=1, blueprint=canonical_blueprint())
    pad._fd = 99
    pad._reply_get_report(struct.pack("<IIBB", uhid.UHID_GET_REPORT, 5, 0x22, 3))
    pad._fd = None
    resposta = os_do_pad.escritas[0][1]
    assert struct.unpack("<IIH", resposta[:10]) == (uhid.UHID_GET_REPORT_REPLY, 5, errno.EPIPE)


def test_no_modo_xbox_nao_ha_feature_report_e_nada_muda() -> None:
    from hefesto_dualsense4unix.integrations.uinput_gamepad import UinputGamepad

    xbox = UinputGamepad.for_flavor("xbox")
    assert not hasattr(xbox, "_reply_get_report")
    assert not hasattr(xbox, "_features")


def test_o_f_hid_da_casa_responde_stall_e_nunca_zeros() -> None:
    """O lado C do gadget: o id recusado, o sem resposta e o largado pelo disable."""
    fonte = F_HID.read_text(encoding="utf-8")
    assert "memset(req->buf, 0x0, req->length)" not in fonte, (
        "o f_hid voltou a responder o buffer zerado ao id sem resposta"
    )
    assert fonte.count("status = usb_ep_set_halt(cdev->gadget->ep0);") == 2
    assert "return !ptr || !ptr->report_data.length;" in fonte
    disable = fonte[fonte.index("static void hidg_disable("):]
    disable = disable[:disable.index("\n}\n")]
    assert "hidg->get_req = NULL;" not in disable, (
        "o hidg_disable larga o get_req, e todo GET_REPORT seguinte fica sem resposta"
    )
    assert "hidg->get_report_dropped = true;" in disable
    assert "wake_up(&hidg->get_queue);" in disable
