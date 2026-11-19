"""RADIO-COLADO-SO-CONTA-QUEM-IRRADIA-JUNTO-DO-BLUETOOTH-01 — o par colado tem um adaptador."""

from __future__ import annotations

import os
from types import SimpleNamespace
from typing import Any

import pytest

from hefesto_dualsense4unix.integrations import exame_da_mesa, mesa_de_radio
from hefesto_dualsense4unix.utils import maquina

RAIZ_BT = "/mentira/class/bluetooth"
RAIZ_USB = "/mentira/bus/usb/devices"
USB1 = "/mentira/devices/pci0000:00/0000:aa:00.0/usb1"


def _no(porta: str, vid: str, pid: str) -> dict[str, str]:
    return {"idVendor": vid, "idProduct": pid, "bDeviceClass": "00", "busnum": "1",
            "devnum": porta, "devpath": porta, "speed": "480"}


class Sysfs:
    """Um ``/sys`` em memória: dois adaptadores longe, e o que mais estiver nas portas."""

    def __init__(self, aparelhos: dict[str, dict[str, str]], wifi: tuple[str, ...] = ()) -> None:
        todos = {"1-1": _no("1", "0bda", "8771"), "1-9": _no("9", "0bda", "8771"), **aparelhos}
        nos = {nome: f"{USB1}/{nome}" for nome in todos}
        self.conteudo = {
            os.path.join(nos[nome], chave): f"{valor}\n"
            for nome, campos in todos.items() for chave, valor in campos.items()
        }
        interfaces = {f"{nome}:1.0": f"{nos[nome]}/{nome}:1.0" for nome in ("1-1", "1-9", *wifi)}
        self.reais = {f"{RAIZ_BT}/hci0": interfaces["1-1:1.0"]}
        self.reais[f"{RAIZ_BT}/hci1"] = interfaces["1-9:1.0"]
        self.reais |= {os.path.join(RAIZ_USB, nome): no for nome, no in (nos | interfaces).items()}
        self.listagens = {
            RAIZ_BT: ["hci0", "hci1"],
            RAIZ_USB: sorted([*nos, *interfaces]),
            **{interfaces[f"{nome}:1.0"]: ["ieee80211"] for nome in wifi},
        }

    def listar(self, raiz: str) -> list[str]:
        if raiz not in self.listagens:
            raise OSError(2, "não existe", raiz)
        return list(self.listagens[raiz])

    def fontes(self) -> dict[str, Any]:
        return {
            "raiz_bt": RAIZ_BT,
            "raiz_usb": RAIZ_USB,
            "listar": self.listar,
            "ler": lambda caminho: self.conteudo.get(caminho, ""),
            "existe": lambda caminho: caminho in self.conteudo,
            "real": lambda caminho: self.reais.get(caminho, caminho),
        }


def _vizinhanca(sysfs: Sysfs) -> exame_da_mesa.Item:
    return exame_da_mesa.vizinhanca_das_portas(
        leitura=lambda: mesa_de_radio.ler_a_mesa(**sysfs.fontes()).apertadas
    )


def test_pendrive_e_receptores_colados_longe_do_bluetooth_nao_acusam() -> None:
    """D-1911-O-RADIO-COLADO-PEDE-UM-ADAPTADOR-NO-PAR: a mesa medida em 19/11."""
    sysfs = Sysfs({
        "1-3": _no("3", "0781", "5583"),
        "1-4": _no("4", "1d57", "fa20"),
        "1-5": _no("5", "046d", "c52b"),
    })
    item = _vizinhanca(sysfs)
    assert item.estado == exame_da_mesa.ESTADO_CERTO, item.porque


def test_o_wifi_colado_no_adaptador_acusa() -> None:
    """O Wi-Fi que o kernel ligou, na porta vizinha de um adaptador: um par, em atenção."""
    sysfs = Sysfs({"1-2": _no("2", "0bda", "b812"), "1-4": _no("4", "1d57", "fa20")}, wifi=("1-2",))
    item = _vizinhanca(sysfs)
    assert item.estado == exame_da_mesa.ESTADO_ATENCAO
    assert item.porque.startswith("1 par"), item.porque


def test_o_receptor_declarado_colado_no_adaptador_acusa() -> None:
    """O tipo que a pessoa declarou faz o receptor irradiar, como na R2."""
    sysfs = Sysfs({"1-2": _no("2", "1d57", "fa20")})
    mesa = mesa_de_radio.ler_a_mesa(**sysfs.fontes(), tipos_declarados={"1d57:fa20": "teclado"})
    assert len(mesa.apertadas) == 1
    sem_tipo = mesa_de_radio.ler_a_mesa(**sysfs.fontes())
    assert sem_tipo.apertadas == ()


def test_o_check_up_le_o_tipo_declarado_da_maquina(monkeypatch: pytest.MonkeyPatch) -> None:
    """O item do Check-up, sem leitura injetada, passa o tipo declarado à mesa."""
    sysfs = Sysfs({"1-2": _no("2", "1d57", "fa20")})
    ler_a_mesa = mesa_de_radio.ler_a_mesa
    monkeypatch.setattr(
        mesa_de_radio, "ler_a_mesa", lambda **pedido: ler_a_mesa(**sysfs.fontes(), **pedido)
    )
    declarada = SimpleNamespace(mesa=SimpleNamespace(radios={
        "1d57:fa20": SimpleNamespace(tipo="teclado"),
    }))
    monkeypatch.setattr(maquina, "carregar_maquina", lambda: declarada)
    item = exame_da_mesa.vizinhanca_das_portas()
    assert item.estado == exame_da_mesa.ESTADO_ATENCAO, item.porque
