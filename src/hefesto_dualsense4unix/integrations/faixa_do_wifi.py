"""A faixa que cada rede Wi-Fi ocupa, lida do NetworkManager sem varrer.

O canal e a largura da rede em uso estão no NetworkManager, sem root e sem
varredura: a ``ActiveAccessPoint`` de cada interface sem fio tem ``Frequency``
e, no 1.46, ``Bandwidth``. Este módulo só LÊ. Nunca chama ``RequestScan`` (varrer
tira a rede do ar por instantes), nunca lê ``Ssid`` nem ``HwAddress``, e o nome
da interface (``wlx…``, que carrega o endereço do adaptador) nunca sai daqui.

A conversa com o barramento de sistema passa pela borda que o ``bluez_dbus``
já tem (:class:`~hefesto_dualsense4unix.integrations.bluez_dbus.BarramentoGio`):
a guarda da suíte vale de graça, e só o ``bluez_dbus`` abre o ``BusType.SYSTEM``.

A conta é a do padrão: o canal Bluetooth ``k`` está em ``2402 + k`` MHz, e a rede
ocupa de ``f - largura/2`` a ``f + largura/2``.
"""

from __future__ import annotations

import atexit
import math
import os
import re
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Protocol

from hefesto_dualsense4unix.integrations import bluez_dbus
from hefesto_dualsense4unix.integrations.ar_do_adaptador import CANAIS_DO_BT

SERVICO = "org.freedesktop.NetworkManager"
RAIZ_DO_GERENTE = "/org/freedesktop/NetworkManager"
INTERFACE_DO_GERENTE = "org.freedesktop.NetworkManager"
INTERFACE_DO_DISPOSITIVO = "org.freedesktop.NetworkManager.Device"
INTERFACE_SEM_FIO = "org.freedesktop.NetworkManager.Device.Wireless"
INTERFACE_DO_PONTO = "org.freedesktop.NetworkManager.AccessPoint"
PROPRIEDADES = "org.freedesktop.DBus.Properties"

TIPO_WIFI = 2
SEM_PONTO_ATIVO = "/"
CANAL_ZERO_DO_BT_MHZ = 2402
FIM_DA_BANDA_DE_2_4_GHZ_MHZ = 2500
LARGURA_MINIMA_EM_2_4_GHZ_MHZ = 20

PROVAVEL = "provavel"
FORA = "fora"

ESPERA_DE_CADA_PERGUNTA_S = 1.5

_NO_DA_INTERFACE_USB = re.compile(r"\d+-[\d.]+:\d+\.\d+")


class _Barramento(Protocol):
    def chamar(
        self,
        destino: str,
        caminho: str,
        interface: str,
        metodo: str,
        assinatura: str,
        argumentos: Any,
        *,
        espera: float,
    ) -> bluez_dbus.Escrita: ...


@dataclass(frozen=True)
class RedeSemFio:
    """Uma rede ativa: onde ela mora (``""`` = dentro da máquina) e o que ela anuncia."""

    no: str
    frequencia_mhz: int
    largura_mhz: int | None


@dataclass(frozen=True)
class FaixaNoBluetooth:
    """Os canais Bluetooth sob a rede, na forma dos evitados (``ini`` dentro, ``fim`` fora)."""

    como: str
    ini: int
    fim: int
    largura_informada: bool


def faixa_no_bluetooth(rede: RedeSemFio) -> FaixaNoBluetooth:
    """Os canais Bluetooth que a rede cobre; acima de 2,5 GHz ela está ``fora``."""
    informada = rede.largura_mhz is not None and rede.largura_mhz > 0
    largura = rede.largura_mhz if informada and rede.largura_mhz else LARGURA_MINIMA_EM_2_4_GHZ_MHZ
    if rede.frequencia_mhz >= FIM_DA_BANDA_DE_2_4_GHZ_MHZ:
        return FaixaNoBluetooth(FORA, 0, 0, informada)
    primeiro = max(0, math.ceil(rede.frequencia_mhz - largura / 2 - CANAL_ZERO_DO_BT_MHZ))
    ultimo = min(
        CANAIS_DO_BT - 1, math.floor(rede.frequencia_mhz + largura / 2 - CANAL_ZERO_DO_BT_MHZ)
    )
    if ultimo < primeiro:
        return FaixaNoBluetooth(FORA, 0, 0, informada)
    return FaixaNoBluetooth(PROVAVEL, primeiro, ultimo + 1, informada)


_TRANCA = threading.Lock()
_DO_SISTEMA: bluez_dbus.BarramentoGio | None = None
_FALHOU_EM: float | None = None


def _barramento_do_sistema() -> _Barramento | None:
    """A conexão de sistema, aberta UMA vez e guardada; ``None`` quando não deu."""
    global _DO_SISTEMA, _FALHOU_EM
    with _TRANCA:
        if _DO_SISTEMA is not None and _DO_SISTEMA.vivo():
            return _DO_SISTEMA
        agora = time.monotonic()
        if _FALHOU_EM is not None and agora - _FALHOU_EM < bluez_dbus.TENTAR_O_GIO_DE_NOVO_S:
            return None
        novo = bluez_dbus.BarramentoGio()
        if not novo.abrir():
            _FALHOU_EM = agora
            return None
        _DO_SISTEMA, _FALHOU_EM = novo, None
        atexit.register(novo.fechar)
        return novo


def _pedir(
    barramento: _Barramento, caminho: str, interface: str, nome: str
) -> Any:
    """O valor de uma propriedade, ou ``None`` quando o NetworkManager não a tem."""
    escrita = barramento.chamar(
        SERVICO, caminho, PROPRIEDADES, "Get", "ss", (interface, nome),
        espera=ESPERA_DE_CADA_PERGUNTA_S,
    )
    if not escrita.feita or not escrita.resposta:
        return None
    return escrita.resposta[0]


def _no_usb_da_interface(
    interface: str, raiz_net: str, real: Callable[[str], str]
) -> str:
    """O nó USB debaixo do qual a interface mora, ou ``""`` (PCI, SDIO, interna)."""
    dispositivo = real(os.path.join(raiz_net, interface, "device"))
    if _NO_DA_INTERFACE_USB.fullmatch(os.path.basename(dispositivo)):
        return os.path.dirname(dispositivo)
    return ""


def ler_as_redes(
    barramento: _Barramento | None = None,
    *,
    raiz_net: str = "/sys/class/net",
    real: Callable[[str], str] = os.path.realpath,
) -> list[RedeSemFio] | None:
    """As redes ativas, uma por interface sem fio; ``None`` quando nada se lê.

    Ausência é resposta: sem NetworkManager (iwd, systemd-networkd), sem
    permissão (Flatpak antigo), sem barramento (a suíte) ou sem rede ativa, é
    ``None`` — nunca a lista vazia, que diria «há zero redes» onde só não se sabe.
    """
    ponte = barramento if barramento is not None else _barramento_do_sistema()
    if ponte is None:
        return None
    listadas = ponte.chamar(
        SERVICO, RAIZ_DO_GERENTE, INTERFACE_DO_GERENTE, "GetDevices", "", (),
        espera=ESPERA_DE_CADA_PERGUNTA_S,
    )
    if not listadas.feita or not listadas.resposta:
        return None
    redes: list[RedeSemFio] = []
    for caminho in listadas.resposta[0]:
        if _pedir(ponte, caminho, INTERFACE_DO_DISPOSITIVO, "DeviceType") != TIPO_WIFI:
            continue
        ponto = _pedir(ponte, caminho, INTERFACE_SEM_FIO, "ActiveAccessPoint")
        if not ponto or ponto == SEM_PONTO_ATIVO:
            continue
        frequencia = _pedir(ponte, str(ponto), INTERFACE_DO_PONTO, "Frequency")
        if not isinstance(frequencia, int) or frequencia <= 0:
            continue
        largura = _pedir(ponte, str(ponto), INTERFACE_DO_PONTO, "Bandwidth")
        interface = _pedir(ponte, caminho, INTERFACE_DO_DISPOSITIVO, "Interface")
        no = _no_usb_da_interface(str(interface), raiz_net, real) if interface else ""
        redes.append(
            RedeSemFio(
                no=no,
                frequencia_mhz=frequencia,
                largura_mhz=largura if isinstance(largura, int) and largura > 0 else None,
            )
        )
    return redes or None


__all__ = [
    "FORA",
    "PROVAVEL",
    "SERVICO",
    "FaixaNoBluetooth",
    "RedeSemFio",
    "faixa_no_bluetooth",
    "ler_as_redes",
]
