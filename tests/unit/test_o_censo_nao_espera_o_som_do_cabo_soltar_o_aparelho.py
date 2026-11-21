"""O censo não espera o som do cabo soltar o aparelho USB para ler quem entra.

Medido em 20/11/2026, 00:34: um DualSense entrou no cabo, e o Edge, ligado 1 s depois noutra porta,
só chegou ao diário 9,2 s depois do kernel, junto com o fim da probe do som do primeiro. O censo
relia a cada passo `manufacturer`, `product`, `bMaxPower`, `bmAttributes` e `bos_descriptors` de
todo aparelho, e o kernel serve os cinco sob a trava do aparelho que a probe segura.

O `/sys` de mentira fica no lugar (o caminho de um aparelho não muda enquanto ele está ligado), e
o aparelho em probe tem os quatro atributos trocados por FIFO sem escritor: quem os abre fica preso,
como atrás da trava. MORDIDA: em `ler_o_barramento`, trocar a memória do processo por uma nova a
cada leitura (`memoria = _MemoriaDaTrava()`).
"""
from __future__ import annotations

import contextlib
import os
import threading
from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.daemon.subsystems import ouvido_do_usb as ou
from hefesto_dualsense4unix.integrations import diario_do_usb as du
from hefesto_dualsense4unix.integrations.censo_do_barramento import Censo, ler_o_barramento
from hefesto_dualsense4unix.utils.texto_do_sysfs import ler_texto

PRAZO_S = 2.0
SONY = "Sony Interactive Entertainment"
CONTROLES = (
    ("054c", "0ce6", SONY, "DualSense Wireless Controller", "500mA"),
    ("054c", "0df2", SONY, "DualSense Edge Wireless Controller", "500mA"),
    ("2dc8", "3106", "8BitDo", "8BitDo Pro 2", "100mA"),
    ("054c", "0ce6", SONY, "DualSense Wireless Controller", "500mA"),
)
RADIO = ("0bda", "8771", "Realtek", "Bluetooth Radio", "500mA")
TRAVADOS = ("manufacturer", "product", "bMaxPower", "bmAttributes")


class _Barramento:
    """Um `/sys/bus/usb/devices` com o hub-raiz `usb3` e os aparelhos pendurados nele."""

    def __init__(self, raiz: Path) -> None:
        self.devices = raiz / "devices" / "pci0000:00" / "0000:0b:00.3"
        self.bus = raiz / "bus" / "usb" / "devices"
        self.bus.mkdir(parents=True)
        self.presos: list[Path] = []
        self._devnum = 1
        self._por("usb3", ("1d6b", "0002", "Linux", "xHCI Host Controller", "0mA"), raiz_hub=True)

    def _por(self, nome: str, aparelho: tuple[str, ...], *, raiz_hub: bool = False) -> None:
        vid, pid, fabricante, produto, corrente = aparelho
        pasta = self.devices / nome if raiz_hub else self.devices / "usb3" / nome
        pasta.mkdir(parents=True)
        atributos = {
            "idVendor": vid, "idProduct": pid, "manufacturer": fabricante, "product": produto,
            "bMaxPower": corrente, "bmAttributes": "e0" if raiz_hub else "80",
            "busnum": "3", "devpath": "0" if raiz_hub else nome.split("-", 1)[1],
            "devnum": str(self._devnum), "speed": "480", "version": " 2.00",
            "bDeviceClass": "09" if raiz_hub else "00", "maxchild": "4" if raiz_hub else "0",
        }
        self._devnum += 1
        for atributo, valor in atributos.items():
            (pasta / atributo).write_text(f"{valor}\n", encoding="utf-8")
        (self.bus / nome).symlink_to(pasta)

    def por(self, porta: int, aparelho: tuple[str, ...]) -> None:
        self._por(f"3-{porta}", aparelho)

    def tirar(self, porta: int) -> None:
        nome = f"3-{porta}"
        (self.bus / nome).unlink()
        pasta = self.devices / "usb3" / nome
        for arquivo in pasta.iterdir():
            arquivo.unlink()
        pasta.rmdir()

    def em_probe(self, porta: int) -> None:
        """A probe de um driver segura a trava do aparelho: os quatro atributos prendem quem lê."""
        pasta = self.devices / "usb3" / f"3-{porta}"
        for atributo in TRAVADOS:
            (pasta / atributo).unlink()
            os.mkfifo(pasta / atributo)
            self.presos.append(pasta / atributo)

    def soltar(self) -> None:
        for fifo in self.presos:
            with contextlib.suppress(OSError):
                os.close(os.open(fifo, os.O_WRONLY | os.O_NONBLOCK))

    def ler(self) -> Censo:
        return ler_o_barramento(raiz_usb=str(self.bus), base=lambda _s, _n: None)


@pytest.fixture
def barramento(tmp_path: Path) -> Any:
    lido = _Barramento(tmp_path / "sys")
    yield lido
    lido.soltar()


def _no_prazo(funcao: Any) -> tuple[bool, list[Any]]:
    saida: list[Any] = []
    fio = threading.Thread(target=lambda: saida.append(funcao()), daemon=True)
    fio.start()
    fio.join(PRAZO_S)
    return not fio.is_alive(), saida


def _vistos(censo: Censo) -> dict[str, tuple[Any, ...]]:
    return {
        a.nome_do_kernel: (a.vid, a.pid, a.fabricante, a.produto, a.energia, a.especie)
        for a in censo.conectados()
    }


def _mesa(barramento: _Barramento) -> None:
    for porta, controle in enumerate(CONTROLES, start=1):
        barramento.por(porta, controle)


@pytest.mark.parametrize("preso", range(4), ids=[f"P{n + 1}" for n in range(4)])
def test_o_radio_que_entra_nao_espera_o_controle_em_probe(
    barramento: _Barramento, preso: int
) -> None:
    """De P1 a P4, DualSense, Edge e controle de terceiro: o rádio entra e o censo responde."""
    _mesa(barramento)
    antes = _vistos(barramento.ler())
    barramento.em_probe(preso + 1)
    barramento.por(5, RADIO)

    terminou, saida = _no_prazo(barramento.ler)

    assert terminou, f"o censo esperou a trava do controle em probe ({PRAZO_S:g} s)"
    depois = _vistos(saida[0])
    assert {k: v for k, v in depois.items() if k != "3-5"} == antes
    assert depois["3-5"][2:4] == ("Realtek", "Bluetooth Radio")


@pytest.mark.parametrize("ordem", ["sai-antes-da-trava", "sai-depois-da-trava"])
@pytest.mark.parametrize("preso", range(4), ids=[f"P{n + 1}" for n in range(4)])
def test_quem_sai_e_volta_se_le_de_novo_sem_esperar_o_controle_em_probe(
    barramento: _Barramento, preso: int, ordem: str
) -> None:
    """O vizinho sai e volta renumerado, em qualquer ordem: é lido de novo, e o preso não."""
    _mesa(barramento)
    barramento.ler()
    vizinho = (preso + 1) % 4 + 1
    passos = [lambda: barramento.tirar(vizinho), lambda: barramento.em_probe(preso + 1)]
    for passo in passos if ordem == "sai-antes-da-trava" else passos[::-1]:
        passo()
        terminou, _ = _no_prazo(barramento.ler)
        assert terminou, f"o censo esperou a trava do controle em probe ({PRAZO_S:g} s)"
    volta = ("054c", "0df2", SONY, "DualSense Edge Wireless Controller", "500mA")
    barramento.por(vizinho, volta)

    terminou, saida = _no_prazo(barramento.ler)

    assert terminou, f"o censo esperou a trava do controle em probe ({PRAZO_S:g} s)"
    lido = _vistos(saida[0])
    assert lido[f"3-{vizinho}"][1:4] == ("0df2", SONY, "DualSense Edge Wireless Controller")
    assert lido[f"3-{preso + 1}"][3] == CONTROLES[preso][3]


def test_a_memoria_diz_o_mesmo_que_a_leitura_direta(barramento: _Barramento) -> None:
    """Nada se perde: o nome, o fabricante, a energia e o Edge saem iguais à leitura sem memória."""
    _mesa(barramento)
    barramento.por(5, RADIO)
    direta = ler_o_barramento(raiz_usb=str(barramento.bus), ler=ler_texto, base=lambda _s, _n: None)

    primeira, segunda = barramento.ler(), barramento.ler()

    assert primeira == direta
    assert segunda == direta
    nomes = {a.nome_do_kernel: (a.pid, a.produto) for a in direta.conectados()}
    assert nomes["3-2"] == ("0df2", "DualSense Edge Wireless Controller")
    assert nomes["3-3"] == ("3106", "8BitDo Pro 2")


def test_o_diario_registra_o_radio_que_entra_com_o_controle_em_probe(
    barramento: _Barramento, tmp_path: Path
) -> None:
    """O ouvido do USB, de ponta a ponta: a linha `entrou` do rádio sai sem esperar a probe."""
    ouvido = ou.Ouvido(
        ler_censo=barramento.ler,
        diario=tmp_path / "estado" / du.NOME_DO_DIARIO,
        boot_id="boot-a",
        relogio=lambda: 0.0,
        agora=lambda: 1_700_000_000.0,
    )
    _mesa(barramento)
    ouvido.comecar(com_netlink=True)
    barramento.em_probe(1)
    barramento.por(5, RADIO)

    terminou, _ = _no_prazo(lambda: ouvido.passo(mudou=True))

    assert terminou, f"o ouvido esperou a trava do controle em probe ({PRAZO_S:g} s)"
    entradas = [
        linha for linha in du.ler(tmp_path / "estado" / du.NOME_DO_DIARIO)
        if linha["o_que"] == du.ENTROU
    ]
    assert [(e["no"], e["produto"]) for e in entradas] == [("3-5", "Bluetooth Radio")]


def test_o_devnum_que_o_kernel_reusa_no_mesmo_caminho_nao_devolve_o_aparelho_de_antes(
    barramento: _Barramento,
) -> None:
    """Dois aparelhos passam pela porta entre um censo e outro, e o terceiro recebe o devnum do
    primeiro: o censo lê o terceiro, porque a leitura nova do caminho apagou a velha."""
    _mesa(barramento)
    barramento.ler()
    devnum_do_primeiro = (barramento.bus / "3-1" / "devnum").read_text(encoding="utf-8")
    barramento.tirar(1)
    barramento.por(1, RADIO)
    barramento.ler()
    barramento.tirar(1)
    barramento.por(1, CONTROLES[1])
    (barramento.bus / "3-1" / "devnum").write_text(devnum_do_primeiro, encoding="utf-8")

    lido = _vistos(barramento.ler())

    assert lido["3-1"][1:4] == ("0df2", SONY, "DualSense Edge Wireless Controller")
