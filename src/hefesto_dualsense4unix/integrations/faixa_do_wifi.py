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
import hashlib
import math
import os
import re
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, replace
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
#: Por quanto tempo o último valor BOM de uma rede se segura quando a leitura de agora falha: a
#: placa que cai e volta passa uns segundos sem ponto ativo (``ActiveAccessPoint`` vira ``/``) ou
#: some do NetworkManager e reaparece com outro nome (``wlan0`` → ``wlx…``) em outro nó. Mais
#: que isto a linha some de verdade (ausência é resposta). O refresco da tela é de 10 s.
SEGURA_O_ULTIMO_VALOR_S = 25.0

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
    """Uma rede ativa: onde ela mora (``""`` = dentro da máquina) e o que ela anuncia.

    ``chave`` é a identidade ESTÁVEL do aparelho (``usb:vid:pid`` ou ``pci:endereço``): nem o nó
    USB nem o nome da interface servem, os dois mudam quando a placa cai e volta. Ela só
    serve de memória dentro deste módulo e nunca sai dele (o ``wlx…`` carrega o endereço).
    """

    no: str
    frequencia_mhz: int
    largura_mhz: int | None
    chave: str = ""


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


def _ler_arquivo(caminho: str) -> str:
    try:
        with open(caminho, encoding="utf-8", errors="replace") as arquivo:
            return arquivo.read().strip()
    except OSError:
        return ""


def _chave_do_aparelho(
    interface: str,
    no: str,
    raiz_net: str,
    real: Callable[[str], str],
    ler: Callable[[str], str],
) -> str:
    """A identidade que sobrevive à queda: ``usb:vid:pid`` ou ``pci:endereço``.

    O nó USB (``4-1.1.4`` → ``3-1.2``) e o nome da interface (``wlan0`` → ``wlx…``) mudam toda
    vez que a placa cai e volta; o ``vid:pid`` e o endereço PCI, não.
    """
    if no:
        vid, pid = ler(os.path.join(no, "idVendor")), ler(os.path.join(no, "idProduct"))
        if vid and pid:
            return f"usb:{vid.lower()}:{pid.lower()}"
    dispositivo = os.path.basename(real(os.path.join(raiz_net, interface, "device")))
    if re.fullmatch(r"[0-9a-f]{4}:[0-9a-f]{2}:[0-9a-f]{2}\.[0-9a-f]", dispositivo):
        return f"pci:{dispositivo}"
    # Sem vid:pid nem PCI, o nome é a última identidade — e ele carrega o endereço (``wlx…``):
    # só o resumo dele serve de chave, e o nome nunca sai.
    return "if:" + hashlib.sha1(interface.encode()).hexdigest()[:8]


#: ``{chave: (instante, rede)}`` — a última leitura boa de cada aparelho, e só dentro do módulo.
_ULTIMAS: dict[str, tuple[float, RedeSemFio]] = {}


def _com_o_que_se_segura(
    redes: list[RedeSemFio],
    vistas: set[str],
    memoria: dict[str, tuple[float, RedeSemFio]],
    agora: float,
    segura_s: float,
) -> list[RedeSemFio]:
    """Junta à leitura de agora o último valor bom de quem sumiu há pouco (a placa que voltou)."""
    for chave in [c for c, (quando, _r) in memoria.items() if agora - quando > segura_s]:
        del memoria[chave]
    for chave, (_quando, rede) in memoria.items():
        if chave not in vistas:
            redes.append(rede)
    return redes


def ler_as_redes(
    barramento: _Barramento | None = None,
    *,
    raiz_net: str = "/sys/class/net",
    real: Callable[[str], str] = os.path.realpath,
    ler: Callable[[str], str] = _ler_arquivo,
    agora: Callable[[], float] = time.monotonic,
    memoria: dict[str, tuple[float, RedeSemFio]] | None = None,
    segura_s: float = SEGURA_O_ULTIMO_VALOR_S,
) -> list[RedeSemFio] | None:
    """As redes ativas, uma por interface sem fio; ``None`` quando nada se lê.

    Ausência é resposta: sem NetworkManager (iwd, systemd-networkd), sem
    permissão (Flatpak antigo), sem barramento (a suíte) ou sem rede ativa, é
    ``None`` — nunca a lista vazia, que diria «há zero redes» onde só não se sabe.

    **O último valor bom se segura por alguns segundos** (:data:`SEGURA_O_ULTIMO_VALOR_S`): a
    placa que cai do barramento e volta some do NetworkManager ou fica sem ponto ativo por
    instantes, e a linha dela na tela não pode sumir e voltar por isso.
    """
    # A memória do módulo é do produto (barramento do sistema); um dublê injetado nasce limpo,
    # para um teste nunca herdar a rede de outro.
    guarda = memoria if memoria is not None else _ULTIMAS if barramento is None else {}
    agora_s = agora()
    vistas: set[str] = set()
    redes: list[RedeSemFio] = []
    ponte = barramento if barramento is not None else _barramento_do_sistema()
    listadas = (
        ponte.chamar(SERVICO, RAIZ_DO_GERENTE, INTERFACE_DO_GERENTE, "GetDevices", "", (),
                     espera=ESPERA_DE_CADA_PERGUNTA_S)
        if ponte is not None else None)
    if ponte is not None and listadas is not None and listadas.feita and listadas.resposta:
        for caminho in listadas.resposta[0]:
            if _pedir(ponte, caminho, INTERFACE_DO_DISPOSITIVO, "DeviceType") != TIPO_WIFI:
                continue
            interface = _pedir(ponte, caminho, INTERFACE_DO_DISPOSITIVO, "Interface")
            no = _no_usb_da_interface(str(interface), raiz_net, real) if interface else ""
            chave = _chave_do_aparelho(str(interface or ""), no, raiz_net, real, ler)
            vistas.add(chave)
            rede = _rede_do_dispositivo(ponte, caminho, no, chave)
            if rede is not None:
                guarda[chave] = (agora_s, rede)
                redes.append(rede)
            elif chave in guarda and agora_s - guarda[chave][0] <= segura_s:
                redes.append(replace(guarda[chave][1], no=no or guarda[chave][1].no))
    redes = _com_o_que_se_segura(redes, vistas, guarda, agora_s, segura_s)
    return redes or None


def _rede_do_dispositivo(
    ponte: _Barramento, caminho: str, no: str, chave: str
) -> RedeSemFio | None:
    """A rede ativa de UMA interface sem fio, ou ``None`` (sem ponto ativo, sem frequência)."""
    ponto = _pedir(ponte, caminho, INTERFACE_SEM_FIO, "ActiveAccessPoint")
    if not ponto or ponto == SEM_PONTO_ATIVO:
        return None
    frequencia = _pedir(ponte, str(ponto), INTERFACE_DO_PONTO, "Frequency")
    if not isinstance(frequencia, int) or frequencia <= 0:
        return None
    largura = _pedir(ponte, str(ponto), INTERFACE_DO_PONTO, "Bandwidth")
    return RedeSemFio(
        no=no,
        frequencia_mhz=frequencia,
        largura_mhz=largura if isinstance(largura, int) and largura > 0 else None,
        chave=chave,
    )


__all__ = [
    "FORA",
    "PROVAVEL",
    "SEGURA_O_ULTIMO_VALOR_S",
    "SERVICO",
    "FaixaNoBluetooth",
    "RedeSemFio",
    "faixa_no_bluetooth",
    "ler_as_redes",
]
