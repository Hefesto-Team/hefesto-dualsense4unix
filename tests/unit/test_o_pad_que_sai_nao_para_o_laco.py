"""O-PAD-QUE-SAI-NAO-PARA-O-LACO-EM-NENHUMA-MASCARA-01 (22/11/2026).

O `parar_fora_do_tique` mandava à fila da descida só a devolução do gadget ao broker. O
pad que não é do uhid (a máscara Xbox e o pad genérico) fazia o `stop()` inteiro no fio de
quem chamava, o `join` do fio do rumble e o `close` do nó, e o uhid fazia o `UHID_DESTROY`
e o `close` do fd: o laço parava segundos quando um controle saía.

O `UHID_DESTROY` e o `close` do nó dormem de mentira; o kernel do uhid é o da régua dos
dois vpads, e o fio do rumble é uma thread que não acorda com o pedido de parar.
"""

from __future__ import annotations

import struct
import threading
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.integrations import uhid_gamepad, uinput_gamepad
from hefesto_dualsense4unix.integrations.uhid_gamepad import (
    UHID_DESTROY,
    esperar_as_descidas,
    parar_fora_do_tique,
)
from hefesto_dualsense4unix.integrations.virtual_pad import make_virtual_pad
from tests.unit.test_o_pad_virtual_so_nasce_com_o_endereco_que_o_kernel_soltou import Mundo

P1, P2 = "aabbcc000001", "aabbcc000002"

TETO_DO_CHAMADOR_S = 0.02

LENTO_S = 0.3


class _NoLento:
    """O `UInput` cujo `close` leva o que o kernel levou nas paradas de 21/11."""

    def __init__(self) -> None:
        self.fechado = False

    def write(self, *_a: Any) -> None:
        pass

    def syn(self) -> None:
        pass

    def read_one(self) -> None:
        return None

    def close(self) -> None:
        time.sleep(LENTO_S)
        self.fechado = True


class Mesa(Mundo):
    """O mundo do endereço, com o `UHID_DESTROY` e o `close` do nó lentos."""

    def __init__(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        super().__init__(monkeypatch, tmp_path)
        self.lentos: set[int] = set()
        self.nos: list[_NoLento] = []
        self._solta_o_fio = threading.Event()
        original = self.kernel.escrever

        def escrever(fd: int, dados: bytes) -> int:
            if fd in self.lentos and struct.unpack("<I", dados[:4])[0] == UHID_DESTROY:
                time.sleep(LENTO_S)
            return original(fd, dados)

        self.kernel.escrever = escrever  # type: ignore[method-assign]
        self.vivos_ao_nascer: list[int] = []
        criar_no_uhid = self.kernel._criar

        def criar_o_uhid(device: Any, dados: bytes) -> None:
            self.vivos_ao_nascer.append(self.vivos())
            criar_no_uhid(device, dados)

        self.kernel._criar = criar_o_uhid  # type: ignore[method-assign]

        def criar(_pad: Any, *, with_ff: bool) -> _NoLento:
            self.vivos_ao_nascer.append(self.vivos())
            no = _NoLento()
            self.nos.append(no)
            return no

        monkeypatch.setattr(uinput_gamepad.UinputGamepad, "_create_device", criar)
        monkeypatch.setattr(uinput_gamepad, "_FF_FIO_ACORDA_S", 0.1)

    def uinput(self, identidade: str, jogador: int, flavor: str) -> Any:
        pad = make_virtual_pad(flavor, identity=identidade, player=jogador, allow_uhid=False)
        assert pad is not None and pad.backend == "uinput" and pad.is_active()
        return pad

    def vivos(self) -> int:
        """Os nós de pad que o jogo vê agora: os do uinput não fechados e os do uhid criados."""
        no_uinput = sum(1 for no in self.nos if not no.fechado)
        return no_uinput + sum(1 for d in self.kernel.devices.values() if d.criado)

    def com_o_fio_do_rumble_demorando(self, pad: Any) -> None:
        """O fio do rumble só sai no `join` estourar: o `stop` leva o `join` inteiro."""
        fio = threading.Thread(target=self._solta_o_fio.wait, args=(10.0,), daemon=True)
        fio.start()
        pad._ff_fio = fio

    def fechar(self) -> None:
        self._solta_o_fio.set()
        super().fechar()


@pytest.fixture
def mesa(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Iterator[Mesa]:
    m = Mesa(monkeypatch, tmp_path)
    monkeypatch.setattr(
        uhid_gamepad, "_DESCIDA_AO_BROKER", uhid_gamepad._DescidaAoBroker()
    )
    try:
        yield m
    finally:
        m.fechar()
        esperar_as_descidas(5.0)


def _tique(pad: Any) -> float:
    comeco = time.monotonic()
    pad.pump_ff()
    return time.monotonic() - comeco


@pytest.mark.parametrize("flavor", ["xbox", "dualsense"])
@pytest.mark.parametrize("quem_sai", ["uhid", "uinput"])
def test_o_jogador_que_sai_devolve_na_hora_e_os_outros_seguem(
    mesa: Mesa, quem_sai: str, flavor: str
) -> None:
    """Quatro jogadores, dois no uhid e dois no uinput: quem sai devolve em menos de 20 ms.

    O `close` e o `UHID_DESTROY` dormem e o fio do rumble demora a sair; os outros três
    seguem no tique e o desfazer termina na fila, com a parada do serviço a esperá-lo.

    Mordida: o `stop()` do uinput de volta ao fio de quem chama (ou o `UHID_DESTROY` do
    uhid) reprova pela frase «o desfazer do pad parou quem chamou».
    """
    uhid_pads = [mesa.nascer(P1, 1), mesa.nascer(P2, 2)]
    uinput_pads = [mesa.uinput("aabbcc000003", 3, flavor), mesa.uinput("aabbcc000004", 4, flavor)]
    for pad in uhid_pads:
        assert pad.backend == "uhid"
        mesa.lentos.add(pad._fd)
    for pad in uinput_pads:
        mesa.com_o_fio_do_rumble_demorando(pad)
    sai = (uhid_pads if quem_sai == "uhid" else uinput_pads)[0]
    fd_de_quem_sai = sai._fd if quem_sai == "uhid" else None
    ficam = [p for p in uhid_pads + uinput_pads if p is not sai]

    comeco = time.monotonic()
    parar_fora_do_tique(sai)
    levou = time.monotonic() - comeco

    assert levou < TETO_DO_CHAMADOR_S, (
        f"o desfazer do pad parou quem chamou: {levou * 1000:.0f} ms"
    )
    assert [round(_tique(p) * 1000) < TETO_DO_CHAMADOR_S * 1000 for p in ficam] == [True] * 3
    if quem_sai == "uhid":
        assert fd_de_quem_sai in mesa.kernel.devices, "o desfazer não correu na fila"
    else:
        assert not sai.is_active(), "o pad que sai ainda aceita escrita"
        assert not mesa.nos[uinput_pads.index(sai)].fechado, "o desfazer não correu na fila"

    assert esperar_as_descidas(5.0), "a parada do serviço não esperou as descidas"
    if quem_sai == "uhid":
        assert fd_de_quem_sai not in mesa.kernel.devices
        assert uhid_gamepad._MACS_DOS_VPADS_VIVOS.vestido_por(sai) is None
    else:
        assert mesa.nos[uinput_pads.index(sai)].fechado
    assert all(p.is_active() for p in ficam)
    assert mesa.kernel.recusas == []


def test_sai_e_volta_o_mesmo_jogador_no_uhid_sem_trocar_de_endereco(mesa: Mesa) -> None:
    """O pad novo espera o velho descer e veste o mesmo endereço: o kernel não recusa."""
    velho = mesa.nascer(P2, 2)
    assert velho.backend == "uhid"
    endereco = velho.mac
    fd_velho = velho._fd
    mesa.lentos.add(fd_velho)

    comeco = time.monotonic()
    parar_fora_do_tique(velho)
    novo = mesa.nascer(P2, 2)
    levou = time.monotonic() - comeco

    assert novo.backend == "uhid" and novo.is_bound
    assert novo.mac == endereco
    assert mesa.kernel.recusas == []
    assert fd_velho not in mesa.kernel.devices
    assert levou < 1.0
    assert mesa.kernel.macs_na_lista() == [endereco]


@pytest.mark.parametrize("flavor", ["xbox", "dualsense"])
def test_sai_e_volta_o_mesmo_jogador_no_uinput_sem_dois_nos_no_jogo(
    mesa: Mesa, flavor: str
) -> None:
    """Quem para volta na hora; o nó novo nasce depois de o velho descer na fila."""
    velho = mesa.uinput(P1, 1, flavor)

    comeco = time.monotonic()
    parar_fora_do_tique(velho)
    levou = time.monotonic() - comeco
    novo = mesa.uinput(P1, 1, flavor)

    assert levou < TETO_DO_CHAMADOR_S
    assert novo is not velho and novo._device is not velho._device
    assert mesa.vivos_ao_nascer == [0, 0], "o nó novo nasceu com o velho ainda no jogo"
    assert esperar_as_descidas(5.0)
    assert not velho.is_active() and novo.is_active()
    assert [no.fechado for no in mesa.nos] == [True, False]


def _pad_de(mesa: Mesa, tipo: str, identidade: str, jogador: int) -> Any:
    if tipo == "uinput":
        return mesa.uinput(identidade, jogador, "xbox")
    pad = mesa.nascer(identidade, jogador)
    assert pad.backend == "uhid"
    return pad


@pytest.mark.parametrize(
    ("velho_tipo", "novo_tipo"),
    [("uinput", "uinput"), ("uinput", "uhid"), ("uhid", "uinput"), ("uhid", "uhid")],
)
def test_com_quatro_na_mesa_o_no_de_quem_volta_nunca_e_o_quinto(
    mesa: Mesa, velho_tipo: str, novo_tipo: str
) -> None:
    """O jogo dá ao nó novo a primeira vaga livre e ignora o quinto (XInput, SDL).

    Quatro jogadores; o P2 sai e volta (a recriação, a troca de modo, a promoção ao uhid):
    quem para segue sem esperar, e o nó novo só nasce depois de o velho sair do kernel.
    """
    outros = [
        mesa.uinput("aabbcc000001", 1, "xbox"),
        mesa.nascer("aabbcc000003", 3),
        mesa.uinput("aabbcc000004", 4, "xbox"),
    ]
    velho = _pad_de(mesa, velho_tipo, P2, 2)
    if velho_tipo == "uhid":
        mesa.lentos.add(velho._fd)
    else:
        mesa.com_o_fio_do_rumble_demorando(velho)
    assert mesa.vivos() == 4

    comeco = time.monotonic()
    parar_fora_do_tique(velho)
    levou = time.monotonic() - comeco
    _pad_de(mesa, novo_tipo, P2, 2)

    assert levou < TETO_DO_CHAMADOR_S, f"o desfazer do pad parou quem chamou: {levou * 1000:.0f} ms"
    assert mesa.vivos_ao_nascer[-1] == 3, (
        f"o nó novo nasceu com {mesa.vivos_ao_nascer[-1]} na mesa: o jogo o põe na quinta vaga"
    )
    assert mesa.vivos() == 4
    assert all(p.is_active() for p in outros)
    assert mesa.kernel.recusas == []
