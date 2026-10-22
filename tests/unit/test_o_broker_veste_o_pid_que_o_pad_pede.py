"""O broker veste o PID que o pad pede (O-BROKER-VESTE-O-PID-QUE-O-PAD-PEDE-01).

O PID do pad tem um dono, o pad (o campo ``product`` do ``UhidDualSense``), e um
porteiro, o broker, que veste o par pedido só se ele estiver na lista fechada
``PAD_USB_VESTIDOS``. Tudo roda no configfs de mentira da régua do gadget; o
esperado vem do pedido, e o observado, do arquivo que o broker escreveu.
"""
from __future__ import annotations

import ast
import importlib.util
import inspect
import json
import os
import sys
from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.broker import hidraw_broker as broker
from hefesto_dualsense4unix.integrations import uhid_gamepad
from hefesto_dualsense4unix.integrations.hidraw_broker_client import HidrawBrokerClient
from tests.unit.test_o_pad_nasce_no_mesmo_usb_do_som import (
    KernelDeMentira,
    _descritor,
    _pedido,
    _serial,
)

RAIZ = Path(__file__).resolve().parents[2]
SONY = 0x054C
EDGE = 0x0DF2
COMUM = 0x0CE6
JOGADORES = (1, 2, 3, 4)


@pytest.fixture
def kernel(tmp_path: Path) -> KernelDeMentira:
    return KernelDeMentira(tmp_path)


def _corpo(serial: str, **campos: object) -> bytes:
    corpo: dict[str, object] = {"cmd": "pad_usb_montar", "serial": serial,
                                "descritor": _descritor().hex()}
    corpo.update(campos)
    return json.dumps(corpo).encode()


def _attach(kernel: KernelDeMentira) -> str:
    return kernel.lido(Path(kernel.raizes.plataforma) / "vhci_hcd.0/attach")


# --- 1. O broker escreve o par que chegou --------------------------------------


@pytest.mark.parametrize("produto", [EDGE, COMUM])
def test_o_broker_escreve_o_par_que_chegou_nos_quatro(
    kernel: KernelDeMentira, produto: int
) -> None:
    lista = broker.PAD_USB_VESTIDOS
    estado = kernel.estado()
    for jogador in JOGADORES:
        resposta, fd = estado.handle_line(
            jogador, 1000, _pedido(_serial(jogador), par=(SONY, produto)))
        assert resposta["ok"] is True, resposta
        assert fd is not None
        os.close(fd)
        g = kernel.gadget(str(resposta["gadget"]))
        assert kernel.lido(g / "idVendor") == f"0x{SONY:04x}"
        assert kernel.lido(g / "idProduct") == f"0x{produto:04x}"
        assert kernel.lido(g / "strings/0x409/product") == lista[(SONY, produto)]
        assert kernel.lido(g / "strings/0x409/serialnumber") == _serial(jogador)
    assert sorted(os.listdir(kernel.raizes.configfs)) == [
        f"hefesto-pad-{n}" for n in range(4)]


# --- 2. Fora da lista, nada nasce ------------------------------------------------


@pytest.mark.parametrize("campos", [
    {"vendor": SONY, "product": 0x05C4},
    {"vendor": SONY},
    {"product": EDGE},
    {},
    {"vendor": SONY, "product": str(EDGE)},
    {"vendor": True, "product": EDGE},
    {"vendor": 0x045E, "product": EDGE},
])
def test_fora_da_lista_nada_nasce(kernel: KernelDeMentira, campos: dict[str, object]) -> None:
    resposta, fd = kernel.estado().handle_line(7, 1000, _corpo(_serial(1), **campos))
    assert fd is None
    assert resposta == {"ok": False, "cmd": "pad_usb_montar", "error": "reject_bad_product"}
    assert os.listdir(kernel.raizes.configfs) == []
    assert _attach(kernel) == ""


def test_a_lista_de_verdade_veste_as_duas_roupas() -> None:
    """Entra o ``0ce6`` (D-2210-O-PAD-PODE-VESTIR-O-DUALSENSE-COMUM): fechada nas duas roupas."""
    assert broker.PAD_USB_VESTIDOS == {
        (SONY, EDGE): "DualSense Edge Wireless Controller",
        (SONY, COMUM): "DualSense Wireless Controller",
    }


# --- 3. O pad manda o PID dele, pela cadeia inteira -----------------------------


class Gravador:
    """O fim da cadeia do daemon: guarda o que iria ao socket e recusa."""

    def __init__(self) -> None:
        self.pedidos: list[dict[str, Any]] = []

    def responder(self, payload: dict[str, Any]) -> tuple[dict[str, Any], list[int]]:
        self.pedidos.append(dict(payload))
        return {"ok": False, "cmd": payload.get("cmd"), "error": "reject_bad_product"}, []


@pytest.fixture
def gravador(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Gravador:
    g = Gravador()
    monkeypatch.setattr(HidrawBrokerClient, "_request_with_fds",
                        lambda _cliente, payload: g.responder(payload))
    monkeypatch.setattr(uhid_gamepad, "PEDIR_O_PAD_USB", uhid_gamepad._pedir_ao_broker)
    monkeypatch.setattr(uhid_gamepad, "CONTRATO_QUE_FALTA", lambda **_kw: [])
    monkeypatch.setattr(uhid_gamepad, "QUIRK_DO_PAR", lambda _par: False)
    monkeypatch.setattr(uhid_gamepad, "_GADGETS_ESTACIONADOS",
                        uhid_gamepad._GadgetsEstacionados())
    uhid_falso = tmp_path / "uhid-de-mentira"
    uhid_falso.write_bytes(b"")
    monkeypatch.setattr(uhid_gamepad, "UHID_NODE", str(uhid_falso))
    return g


@pytest.mark.parametrize("jogador", JOGADORES)
@pytest.mark.parametrize("produto", [COMUM, EDGE])
def test_o_pad_manda_o_pid_dele_ate_o_socket(
    gravador: Gravador, tmp_path: Path, jogador: int, produto: int
) -> None:
    from hefesto_dualsense4unix.integrations.uhid_blueprint import canonical_blueprint

    pad = uhid_gamepad.UhidDualSense(
        player=jogador, product=produto, blueprint=canonical_blueprint(),
        identity=f"aa:bb:cc:00:00:{jogador:02x}")
    try:
        assert pad.start() is True
    finally:
        pad.stop()
    assert len(gravador.pedidos) == 1, gravador.pedidos
    pedido = gravador.pedidos[0]
    assert pedido["cmd"] == "pad_usb_montar"
    assert (pedido["vendor"], pedido["product"]) == (SONY, produto)
    criado = (tmp_path / "uhid-de-mentira").read_bytes()
    assert int.from_bytes(criado[268:272], "little") == produto, "o CREATE2 não levou o PID do pad"


# --- 4. O ramo não troca de lugar --------------------------------------------------


def _check_a_origem() -> Any:
    spec = importlib.util.spec_from_file_location(
        "check_a_origem_da_regua", RAIZ / "scripts" / "check_a_origem.py")
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.mark.parametrize("alvo", [
    uhid_gamepad._o_pad_em_usb,
    broker.BrokerState._cmd_pad_usb_montar,
    broker.PadUsbOps.montar,
])
def test_nenhum_ramo_de_modelo_nas_funcoes_da_cura(alvo: Any) -> None:
    """Sobre o módulo inteiro (as constantes nomeadas resolvem), só as linhas da função."""
    regua = _check_a_origem()
    modulo = inspect.getmodule(alvo)
    assert modulo is not None
    fonte = inspect.getsource(modulo)
    ast.parse(fonte)
    linhas, inicio = inspect.getsourcelines(alvo)
    fim = inicio + len(linhas)
    ramos = [(n, eixo) for n, eixo in regua.ramos_de_eixo(fonte)
             if inicio <= n < fim and eixo == "modelo"]
    assert ramos == [], f"{alvo.__qualname__}: ramo de modelo em {ramos}"


def test_a_regua_dos_ramos_ve_o_ramo_de_modelo() -> None:
    """Sem isto a régua de cima passaria vazia: o ramo de antes conta."""
    regua = _check_a_origem()
    fonte = ("VPAD_PRODUCT = 0x0DF2\n\ndef f(pad):\n"
             "    if pad.product != VPAD_PRODUCT:\n        return 1\n")
    assert regua.ramos_de_eixo(fonte) == [(4, "modelo")]
