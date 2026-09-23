"""bluez_dbus.py — o D-Bus do BlueZ com UM dono.

BLUEZ-UM-DONO-01 (23/09/2026). Nove leitores falavam com o BlueZ, cada um com o
próprio subprocesso: quatro desembrulhos, três prazos, polling em todos, e
ninguém assinava o ``ObjectManager``. A guarda contra a suíte estava em um
executor de cinco. Este módulo é o dono:

* **LÊ** assinando o ``ObjectManager`` do barramento de sistema pelo Gio
  (``InterfacesAdded``/``InterfacesRemoved``, ``PropertiesChanged`` e
  ``NameOwnerChanged``). A leitura sai de uma foto em memória — zero
  subprocesso por pergunta;
* **CAI** no ``busctl --json=short`` quando o Gio não alcança o barramento
  (Flatpak sem ``--socket=system-bus``, ``gi`` ausente), com o desembrulho que
  não mutila nome com espaço — o de ``apelido_do_dongle``, que mora aqui agora;
* **ESCREVE** ``Alias``, ``Connect``, ``Disconnect``, ``RemoveDevice``,
  ``Pair``, ``Trusted`` e ``StartDiscovery``/``StopDiscovery`` do NOSSO cliente;
* **RECUSA NA BORDA** toda escrita no BlueZ de verdade enquanto a suíte roda.
  A política D-Bus desta máquina deixa qualquer uid local chamar qualquer
  método do ``org.bluez`` (``/usr/share/dbus-1/system.d/bluetooth.conf``) —
  inclusive a suíte, que em 22/09/2026 derrubou os quatro DualSense dela;
* o ENDEREÇO do adaptador vem do ioctl do kernel (``HCIGETDEVINFO``), não do
  texto de ninguém; o LUGAR dele (D3) é o caminho PCI mais as portas do USB.

AUSÊNCIA É RESPOSTA. ``None`` quer dizer "não deu para perguntar", nunca "não
há". Quem lê decide o que dizer; este módulo não inventa o vazio.

DONOS EXTERNOS, declarados e não absorvidos: os scripts root
(``bt_ponte_privilegiada.sh``, ``bt_active_mode.sh``, ``bt_health_watchdog.sh``)
e o ``hefesto-bt-agent``. São shell e root; o que o D-Bus não alcança como uid
1000 continua com eles.
"""

from __future__ import annotations

import array
import atexit
import contextlib
import fcntl
import json
import os
import re
import shutil
import socket
import struct
import subprocess
import sys
import threading
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

# ---------------------------------------------------------------------------
# Os nomes — escritos UMA vez, aqui. A régua de dono reprova a segunda grafia.
# ---------------------------------------------------------------------------

SERVICO = "org.bluez"
ADAPTADOR = "org.bluez.Adapter1"
APARELHO = "org.bluez.Device1"
GERENTE_DE_AGENTES = "org.bluez.AgentManager1"
AGENTE = "org.bluez.Agent1"
PROPRIEDADES = "org.freedesktop.DBus.Properties"
OBJETOS = "org.freedesktop.DBus.ObjectManager"
BARRAMENTO_DBUS = "org.freedesktop.DBus"
RAIZ_DO_BLUEZ = "/org/bluez"

#: O programa do caminho de reserva. O único lugar do produto onde ele se chama.
FERRAMENTA = "busctl"

ERRO_REJEITADO = "org.bluez.Error.Rejected"
ERRO_CANCELADO = "org.bluez.Error.Canceled"
ERRO_JA_EXISTE = "org.bluez.Error.AlreadyExists"
ERRO_ACESSO_NEGADO = "org.freedesktop.DBus.Error.AccessDenied"

#: Os motivos de uma escrita que não chegou ao BlueZ. Não são erros D-Bus: são
#: o dono dizendo por que nem tentou.
RECUSA_DA_SUITE = "hefesto.RecusaDaSuite"
SEM_BARRAMENTO = "hefesto.SemBarramento"
SEM_AGENTE = "hefesto.SemAgente"

#: Teto de cada pergunta pelo caminho de reserva. O número que ``exame_da_mesa``,
#: ``apelido_do_dongle`` e ``gesto_de_reconexao`` repetiam, cada um no seu.
ESPERA_DO_BUSCTL_S = 5.0

#: O ``Connect`` CHAMA o aparelho. Medido na mesa dela em 22/09/2026: a recusa
#: de um controle dormindo volta em menos de 2 s, e um acordado responde em
#: 3-4 s. Cinco segundos chamariam de "não deu" o que só estava demorando.
ESPERA_DO_CONNECT_S = 12.0

#: O ``Pair`` espera o gesto de PS + Create. É o mesmo teto do verbo ``parear``
#: da ponte (``timeout 45 busctl call … Pair``).
ESPERA_DO_PAIR_S = 45.0

#: Quanto a primeira foto do barramento pode custar ao ligar o dono.
ESPERA_DA_FOTO_S = 3.0

#: Depois de o Gio falhar, quanto tempo o dono espera para tentar de novo. Sem
#: isto, uma máquina sem barramento (Flatpak) pagaria a tentativa a cada leitura.
TENTAR_O_GIO_DE_NOVO_S = 60.0

_CAMINHO_DE_ADAPTADOR = re.compile(r"^/org/bluez/(hci[0-9]+)$")
_CAMINHO_DE_APARELHO = re.compile(
    r"^(/org/bluez/hci[0-9]+)/dev_([0-9A-Fa-f]{2}(?:_[0-9A-Fa-f]{2}){5})$"
)
_MINIMO_POR_PERGUNTA = 0.02


# ---------------------------------------------------------------------------
# A guarda contra a suíte — a borda, e o escape declarado.
# ---------------------------------------------------------------------------

#: O ESCAPE. Quem declara ``HEFESTO_RADIO_DE_VERDADE=1`` assume o rádio dela.
RADIO_DE_VERDADE_NA_SUITE = "HEFESTO_RADIO_DE_VERDADE"


def a_suite_esta_rodando() -> bool:
    """A suíte está no ar? Então nada daqui escreve no BlueZ dela.

    É o mesmo sinal que ``gesto_de_reconexao`` usava sozinho desde 22/09/2026,
    quando a primeira corrida de 457 testes chamou ``Disconnect`` e ``Connect``
    nos quatro DualSense da mesa dela, ao vivo. Agora ele guarda a BORDA: toda
    escrita passa por :meth:`LeitorDoBluez.chamar` ou
    :meth:`LeitorDoBluez.escrever_propriedade`, e as duas perguntam aqui.
    """
    if os.environ.get(RADIO_DE_VERDADE_NA_SUITE) == "1":
        return False
    return bool(os.environ.get("PYTEST_CURRENT_TEST")) or "pytest" in sys.modules


# ---------------------------------------------------------------------------
# O diário — sem terceiro no import, porque o doctor carrega este módulo.
# ---------------------------------------------------------------------------


def _registrar(evento: str, *, nivel: str = "info", **campos: Any) -> None:
    """Uma linha no diário do processo. Nunca levanta.

    O ``structlog`` entra tarde e dentro de ``try``: o ``exame_da_mesa`` chega
    aqui pelo ``python`` que o doctor escolher, e uma dependência de terceiro no
    import viraria uma linha muda na conferência.
    """
    try:
        from hefesto_dualsense4unix.utils.logging_config import get_logger

        getattr(get_logger(__name__), nivel)(evento, **campos)
    except Exception:
        return


def _mascara(mac: str) -> str:
    """O endereço com os octetos 4 e 5 zerados — o único que vai ao diário."""
    from hefesto_dualsense4unix.integrations.gesto_de_reconexao import mascarar

    return mascarar(mac)


def _mac(valor: object) -> str | None:
    """Endereço limpo, minúsculo e com dois-pontos — ou ``None``."""
    from hefesto_dualsense4unix.integrations.conexao_zumbi import mac_limpo

    return mac_limpo(valor if isinstance(valor, str) else None)


# ---------------------------------------------------------------------------
# O resultado de uma escrita.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Escrita:
    """O que aconteceu com UMA escrita no BlueZ. Imutável, nunca uma exceção.

    ``erro`` é o nome D-Bus do erro quando o BlueZ respondeu que não
    (``org.bluez.Error.Failed``), ou um dos motivos do dono (:data:`RECUSA_DA_SUITE`,
    :data:`SEM_BARRAMENTO`, :data:`SEM_AGENTE`) quando nem se tentou.
    """

    feita: bool
    erro: str = ""
    mensagem: str = ""
    resposta: Any = None

    @property
    def nem_tentou(self) -> bool:
        """O dono recusou antes de falar com o BlueZ — não houve tentativa."""
        return self.erro in (RECUSA_DA_SUITE, SEM_BARRAMENTO, SEM_AGENTE)


class RecusaNoBarramento(Exception):  # noqa: N818 — nome de domínio, não de erro
    """Levantada por quem atende um objeto exportado: vira erro D-Bus na resposta."""

    def __init__(self, nome: str, mensagem: str = "") -> None:
        super().__init__(mensagem or nome)
        self.nome = nome
        self.mensagem = mensagem or nome


# ---------------------------------------------------------------------------
# O desembrulho — UM só, e é o que não mutila nome com espaço.
# ---------------------------------------------------------------------------

_INTEIROS_DO_DBUS = frozenset("ynqiuxth")


def desembrulhar(bruto: str | None) -> Any | None:
    """O valor de uma resposta do ``busctl``: JSON na frente, texto atrás.

    Veio de ``apelido_do_dongle._desembrulhar``, o único dos quatro que não
    mutilava ``s "Nintendo MeowSystem"`` — o ``texto.split()[-1]`` dos outros
    devolvia ``MeowSystem"``. Agora devolve o valor TIPADO: ``b true`` é
    ``True``, ``u 9480`` é ``9480``. O texto continua atendido como plano B
    (``busctl`` sem ``--json``, ou um dublê que responde no formato humano).
    """
    if bruto is None:
        return None
    texto = bruto.strip()
    if not texto:
        return None
    try:
        dado = json.loads(texto)
    except ValueError:
        pass
    else:
        if isinstance(dado, dict) and "data" in dado:
            return dado["data"]
        return dado
    tipo, _, resto = texto.partition(" ")
    resto = resto.strip()
    if tipo == "b":
        if resto in ("true", "false"):
            return resto == "true"
        return None
    if tipo in ("s", "o", "g"):
        if len(resto) >= 2 and resto.startswith('"') and resto.endswith('"'):
            return resto[1:-1].replace('\\"', '"').replace("\\\\", "\\")
        return resto
    if len(tipo) == 1 and tipo in _INTEIROS_DO_DBUS:
        try:
            return int(resto)
        except ValueError:
            return None
    return resto.strip('"') if resto else texto


def como_booleano(valor: object) -> bool | None:
    """``True``/``False`` para o que o BlueZ disse, ``None`` para "não sei".

    Aceita o booleano tipado e as grafias de texto que os leitores antigos
    aceitavam (``true``/``yes``/``1``) — a troca de dono não muda resposta.
    """
    if isinstance(valor, bool):
        return valor
    if isinstance(valor, int):
        return bool(valor) if valor in (0, 1) else None
    if isinstance(valor, str):
        texto = valor.strip().strip('"').lower()
        if texto in ("true", "yes", "1"):
            return True
        if texto in ("false", "no", "0"):
            return False
    return None


# ---------------------------------------------------------------------------
# O caminho de reserva — o ÚNICO subprocesso de ``busctl`` do produto.
# ---------------------------------------------------------------------------

#: Os verbos que só LEEM. Todo o resto escreve, e a borda o recusa sob a suíte.
_LEITURAS_DO_BUSCTL = frozenset({"tree", "get-property", "introspect"})

#: O que roda UMA pergunta de ``busctl``: recebe os argumentos (sem o nome do
#: programa) e devolve a saída, ou ``None`` quando não deu. É a forma que os
#: dublês da suíte sempre tiveram.
Executar = Callable[[Sequence[str]], "str | None"]


def busctl(argumentos: Sequence[str], *, espera: float = ESPERA_DO_BUSCTL_S) -> str | None:
    """Roda um ``busctl`` de usuário no barramento de sistema. ``None`` = não deu.

    Ferramenta ausente, código diferente de zero e teto estourado colapsam em
    ``None``. Saída vazia com código ``0`` é SUCESSO — é o que o
    ``set-property`` devolve.

    ``--json=short`` vai DEPOIS do verbo, e só no ``get-property``: o
    ``busctl`` aceita a opção em qualquer posição, e os ``busctl`` de mentira da
    suíte casam o verbo pela primeira palavra. ``LC_ALL=C`` não é zelo: o
    ``pactl`` desta casa já cegou um leitor duas vezes traduzindo a própria
    saída.
    """
    verbo = argumentos[0] if argumentos else ""
    if verbo not in _LEITURAS_DO_BUSCTL and a_suite_esta_rodando():
        return None
    if shutil.which(FERRAMENTA) is None:
        return None
    modo = ["--json=short"] if verbo == "get-property" else []
    ambiente = dict(os.environ)
    ambiente["LC_ALL"] = "C"
    try:
        saida = subprocess.run(
            [FERRAMENTA, *argumentos, *modo],
            capture_output=True,
            text=True,
            timeout=max(_MINIMO_POR_PERGUNTA, espera),
            check=False,
            env=ambiente,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return saida.stdout if saida.returncode == 0 else None


# ---------------------------------------------------------------------------
# O kernel: o endereço de cada adaptador pelo ioctl, e o lugar pelo sysfs.
# ---------------------------------------------------------------------------

#: ``_IOR('H', 210, int)`` e ``_IOR('H', 211, int)`` — ``include/net/bluetooth/hci_sock.h``.
_HCIGETDEVLIST = 0x800448D2
_HCIGETDEVINFO = 0x800448D3
_HCI_MAX_DEV = 16
#: ``sizeof(struct hci_dev_info)`` é 92; o buffer tem folga.
_TAMANHO_DO_INFO = 128


def enderecos_pelo_ioctl() -> dict[str, str] | None:
    """``{hciN: endereço}`` direto do kernel, sem ``bluetoothd`` e sem texto.

    É o que o ``hciconfig`` lê: um socket HCI cru e dois ioctl de leitura
    (``HCIGETDEVLIST``, ``HCIGETDEVINFO``). Responde como uid 1000 — medido na
    mesa dela em 23/09/2026, os dois adaptadores de pé. Não depende do
    ``bluetoothd``, e é por isso que o endereço sai daqui e não do ``Address``
    do D-Bus: o texto é do terceiro, o número é do kernel.

    ``None`` é "não deu": sem ``AF_BLUETOOTH`` neste Python, socket recusado
    (Flatpak), ou a suíte no ar — a suíte não lê a mesa dela por aqui.
    """
    if a_suite_esta_rodando():
        return None
    familia = getattr(socket, "AF_BLUETOOTH", None)
    protocolo = getattr(socket, "BTPROTO_HCI", None)
    if familia is None or protocolo is None:
        return None
    try:
        with socket.socket(familia, socket.SOCK_RAW, protocolo) as tomada:
            lista = array.array(
                "B", struct.pack("=H", _HCI_MAX_DEV) + bytes(2 + 8 * _HCI_MAX_DEV)
            )
            fcntl.ioctl(tomada.fileno(), _HCIGETDEVLIST, lista, True)
            quantos = min(struct.unpack_from("=H", lista, 0)[0], _HCI_MAX_DEV)
            achados: dict[str, str] = {}
            for indice in range(quantos):
                (numero,) = struct.unpack_from("=H", lista, 4 + 8 * indice)
                info = array.array(
                    "B", struct.pack("=H", numero) + bytes(_TAMANHO_DO_INFO - 2)
                )
                fcntl.ioctl(tomada.fileno(), _HCIGETDEVINFO, info, True)
                cru = info.tobytes()
                nome = cru[2:10].split(b"\0", 1)[0].decode("ascii", "replace")
                endereco = ":".join(f"{octeto:02x}" for octeto in reversed(cru[10:16]))
                if nome and endereco != "00:00:00:00:00:00":
                    achados[nome] = endereco
            return achados
    except OSError:
        return None


def lugar_de(controlador_pci: str, devpath: str) -> str:
    """O LUGAR de um adaptador (D3): o controlador PCI e as portas do USB.

    A grafia é a do ``ID_PATH`` do udev (``pci-0000:0c:00.3-usb-0:1.1.4``):
    sem o número do barramento, que é ordem de enumeração, e com a cadeia de
    portas, que é o metal. ``""`` quando não há controlador — "não sei onde".
    """
    if not controlador_pci:
        return ""
    if not devpath:
        return f"pci-{controlador_pci}"
    return f"pci-{controlador_pci}-usb-0:{devpath}"


def lugares_dos_adaptadores() -> dict[str, str]:
    """``{hciN: lugar}`` pelo sysfs, pelo dono do sysfs (``mesa_de_radio``).

    Vazio sob a suíte: a suíte não lê a mesa dela por aqui.
    """
    if a_suite_esta_rodando():
        return {}
    try:
        from hefesto_dualsense4unix.integrations.mesa_de_radio import (
            adaptadores_bluetooth,
        )

        return {
            a.interface: lugar_de(a.controlador_pci, a.devpath)
            for a in adaptadores_bluetooth()
        }
    except Exception:
        return {}


@dataclass(frozen=True)
class MudancaDeLugar:
    """Um dongle que mudou desde a última vez que o dono olhou (D3).

    ``trocado``: endereço novo numa porta conhecida — o dongle foi trocado.
    ``mudou_de_porta``: endereço conhecido numa porta nova.
    """

    tipo: str
    lugar: str
    endereco: str
    lugar_antigo: str = ""
    endereco_antigo: str = ""

    @property
    def frase(self) -> str:
        """O fato, curto, para a tela e para o diário."""
        if self.tipo == "trocado":
            return "O adaptador desta porta foi trocado."
        return "Este adaptador mudou de porta."


def perceber_as_mudancas(
    antes: Mapping[str, str], agora: Mapping[str, str]
) -> tuple[MudancaDeLugar, ...]:
    """As mudanças entre duas leituras ``{lugar: endereço}``. Função pura.

    Uma porta nova com um endereço nunca visto não é mudança: é um adaptador
    novo, e não há o que dizer.
    """
    onde_estava = {endereco: lugar for lugar, endereco in antes.items()}
    achadas: list[MudancaDeLugar] = []
    for lugar, endereco in sorted(agora.items()):
        if antes.get(lugar) == endereco:
            continue
        anterior = onde_estava.get(endereco)
        if anterior is not None and anterior != lugar:
            achadas.append(
                MudancaDeLugar("mudou_de_porta", lugar, endereco, lugar_antigo=anterior)
            )
        elif lugar in antes:
            achadas.append(
                MudancaDeLugar("trocado", lugar, endereco, endereco_antigo=antes[lugar])
            )
    return tuple(achadas)


def _memoria_dos_lugares() -> Path:
    from hefesto_dualsense4unix.utils.xdg_paths import state_dir

    return state_dir() / "lugares-dos-adaptadores.json"


# ---------------------------------------------------------------------------
# As leituras compostas.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class AdaptadorDoBluez:
    """Um adaptador. ``caminho`` e ``hci`` caducam entre boots: nunca guarde."""

    caminho: str
    hci: str
    endereco: str
    alias: str = ""
    nome: str = ""
    ligado: bool | None = None
    varrendo: bool | None = None
    lugar: str = ""


@dataclass(frozen=True)
class AparelhoDoBluez:
    """Um aparelho que o BlueZ conhece, num adaptador."""

    caminho: str
    adaptador: str
    endereco: str
    nome: str = ""
    conectado: bool | None = None
    pareado: bool | None = None
    vinculado: bool | None = None
    confiavel: bool | None = None
    rssi: int | None = None
    classe: int | None = None
    modalias: str = ""


def _hci_de(caminho: str) -> str:
    achado = _CAMINHO_DE_ADAPTADOR.match(caminho)
    return achado.group(1) if achado else ""


def _no_de_aparelho(endereco: str) -> str:
    return "dev_" + endereco.upper().replace(":", "_")


# ---------------------------------------------------------------------------
# O leitor — o contrato comum aos dois caminhos.
# ---------------------------------------------------------------------------


class LeitorDoBluez:
    """O que todo leitor e escritor do BlueZ responde, pelo caminho que tiver.

    Duas subclasses: :class:`DonoVivo` (o Gio, a foto ao vivo) e
    :class:`PeloBusctl` (o caminho de reserva, e a forma dos dublês da suíte).
    As escritas passam TODAS por :meth:`chamar` e :meth:`escrever_propriedade`,
    que é onde a guarda da suíte mora.
    """

    #: ``True`` quando o destino é o BlueZ de verdade (o barramento de sistema
    #: ou o ``busctl`` do sistema). Só esses a guarda da suíte recusa: um dublê
    #: não é o rádio dela.
    toca_o_sistema: bool = False

    #: ``True`` só onde há conexão viva para registrar o agente próprio (R5).
    atende_o_proprio_pareamento: bool = False

    # -- o transporte (cada subclasse) ---------------------------------------

    def pode_perguntar(self) -> bool:
        raise NotImplementedError

    def caminhos(self, *, espera: float | None = None) -> tuple[str, ...] | None:
        raise NotImplementedError

    def propriedade(
        self, caminho: str, interface: str, nome: str, *, espera: float | None = None
    ) -> Any | None:
        raise NotImplementedError

    def _chamar(
        self,
        caminho: str,
        interface: str,
        metodo: str,
        assinatura: str,
        argumentos: Sequence[Any],
        espera: float,
    ) -> Escrita:
        raise NotImplementedError

    def _escrever(
        self,
        caminho: str,
        interface: str,
        nome: str,
        assinatura: str,
        valor: Any,
        espera: float,
    ) -> Escrita:
        raise NotImplementedError

    def _enderecos_do_kernel(self) -> Mapping[str, str] | None:
        return None

    def _lugares(self) -> Mapping[str, str]:
        return {}

    def dono_do_bluez(self) -> str:
        """O nome único do ``bluetoothd`` de agora; ``""`` quando não se sabe."""
        return ""

    # -- A BORDA: toda escrita passa por estes dois ---------------------------

    def _recusa(self) -> Escrita | None:
        if self.toca_o_sistema and a_suite_esta_rodando():
            _registrar("bluez_escrita_recusada_pela_suite", nivel="warning")
            return Escrita(
                False,
                RECUSA_DA_SUITE,
                "a suíte está no ar e este é o BlueZ de verdade",
            )
        return None

    def chamar(
        self,
        caminho: str,
        interface: str,
        metodo: str,
        assinatura: str = "",
        argumentos: Sequence[Any] = (),
        *,
        espera: float = ESPERA_DO_BUSCTL_S,
    ) -> Escrita:
        """Chama um método do BlueZ. A borda: sob a suíte, o sistema recusa."""
        recusa = self._recusa()
        if recusa is not None:
            return recusa
        return self._chamar(caminho, interface, metodo, assinatura, argumentos, espera)

    def escrever_propriedade(
        self,
        caminho: str,
        interface: str,
        nome: str,
        assinatura: str,
        valor: Any,
        *,
        espera: float = ESPERA_DO_BUSCTL_S,
    ) -> Escrita:
        """Grava uma propriedade do BlueZ. A mesma borda de :meth:`chamar`."""
        recusa = self._recusa()
        if recusa is not None:
            return recusa
        return self._escrever(caminho, interface, nome, assinatura, valor, espera)

    # -- as leituras compostas -----------------------------------------------

    def endereco_do_adaptador(
        self, caminho: str, *, espera: float | None = None
    ) -> str | None:
        """O endereço deste adaptador: o do ioctl quando dá, o do D-Bus quando não."""
        kernel = self._enderecos_do_kernel()
        hci = _hci_de(caminho)
        if kernel and hci in kernel:
            return kernel[hci]
        return _mac(self.propriedade(caminho, ADAPTADOR, "Address", espera=espera))

    def adaptadores(self) -> tuple[AdaptadorDoBluez, ...] | None:
        """Os adaptadores, em ordem de caminho. ``None`` = não deu para perguntar."""
        caminhos = self.caminhos()
        if caminhos is None:
            return None
        lugares = self._lugares()
        achados: list[AdaptadorDoBluez] = []
        for caminho in caminhos:
            hci = _hci_de(caminho)
            if not hci:
                continue
            endereco = self.endereco_do_adaptador(caminho)
            if endereco is None:
                continue
            achados.append(
                AdaptadorDoBluez(
                    caminho=caminho,
                    hci=hci,
                    endereco=endereco,
                    alias=str(self.propriedade(caminho, ADAPTADOR, "Alias") or ""),
                    nome=str(self.propriedade(caminho, ADAPTADOR, "Name") or ""),
                    ligado=como_booleano(self.propriedade(caminho, ADAPTADOR, "Powered")),
                    varrendo=como_booleano(
                        self.propriedade(caminho, ADAPTADOR, "Discovering")
                    ),
                    lugar=lugares.get(hci, ""),
                )
            )
        return tuple(achados)

    def aparelhos(self) -> tuple[AparelhoDoBluez, ...] | None:
        """Os aparelhos de todos os adaptadores. ``None`` = não deu para perguntar."""
        caminhos = self.caminhos()
        if caminhos is None:
            return None
        achados: list[AparelhoDoBluez] = []
        for caminho in caminhos:
            forma = _CAMINHO_DE_APARELHO.match(caminho)
            if forma is None:
                continue
            endereco = _mac(forma.group(2).replace("_", ":"))
            if endereco is None:
                continue
            rssi = self.propriedade(caminho, APARELHO, "RSSI")
            classe = self.propriedade(caminho, APARELHO, "Class")
            achados.append(
                AparelhoDoBluez(
                    caminho=caminho,
                    adaptador=forma.group(1),
                    endereco=endereco,
                    nome=str(self.propriedade(caminho, APARELHO, "Alias") or ""),
                    conectado=como_booleano(self.propriedade(caminho, APARELHO, "Connected")),
                    pareado=como_booleano(self.propriedade(caminho, APARELHO, "Paired")),
                    vinculado=como_booleano(self.propriedade(caminho, APARELHO, "Bonded")),
                    confiavel=como_booleano(self.propriedade(caminho, APARELHO, "Trusted")),
                    rssi=rssi if isinstance(rssi, int) and not isinstance(rssi, bool) else None,
                    classe=classe
                    if isinstance(classe, int) and not isinstance(classe, bool)
                    else None,
                    modalias=str(self.propriedade(caminho, APARELHO, "Modalias") or ""),
                )
            )
        return tuple(achados)

    def caminho_do_adaptador(self, endereco: str) -> str | None:
        """O ``/org/bluez/hciN`` de AGORA deste endereço. Resolvido, nunca guardado."""
        alvo = _mac(endereco)
        if alvo is None:
            return None
        for caminho in self.caminhos() or ():
            if _hci_de(caminho) and self.endereco_do_adaptador(caminho) == alvo:
                return caminho
        return None

    def caminho_do_aparelho(
        self, endereco: str, *, adaptador: str | None = None
    ) -> str | None:
        """O caminho deste aparelho — em QUALQUER adaptador, ou no ``adaptador`` dado.

        Casa pelo endereço, que é o que não muda; o ``hciN`` é sorteio de
        enumeração. Sem ``adaptador``, o primeiro achado na ordem da árvore.
        """
        alvo = _mac(endereco)
        if alvo is None:
            return None
        caminhos = self.caminhos()
        if caminhos is None:
            return None
        pai = self.caminho_do_adaptador(adaptador) if adaptador is not None else None
        if adaptador is not None and pai is None:
            return None
        no = _no_de_aparelho(alvo)
        for caminho in caminhos:
            forma = _CAMINHO_DE_APARELHO.match(caminho)
            if forma is None or not caminho.endswith("/" + no):
                continue
            if pai is None or forma.group(1) == pai:
                return caminho
        return None

    # -- as escritas nomeadas ------------------------------------------------

    def escrever_alias(self, caminho_do_adaptador: str, texto: str) -> Escrita:
        """O ``Alias`` do adaptador. Sem privilégio: medido como uid 1000 em 22/08."""
        return self.escrever_propriedade(caminho_do_adaptador, ADAPTADOR, "Alias", "s", texto)

    def conectar(self, caminho: str, *, espera: float = ESPERA_DO_CONNECT_S) -> Escrita:
        """``Connect`` — chama o aparelho, e ele pode estar dormindo."""
        return self.chamar(caminho, APARELHO, "Connect", espera=espera)

    def desconectar(self, caminho: str) -> Escrita:
        """``Disconnect`` — derruba a conexão; o bond fica."""
        return self.chamar(caminho, APARELHO, "Disconnect")

    def remover_aparelho(self, caminho_do_aparelho: str) -> Escrita:
        """``RemoveDevice`` no adaptador pai — esquece o bond NESTE adaptador só."""
        forma = _CAMINHO_DE_APARELHO.match(caminho_do_aparelho)
        if forma is None:
            return Escrita(False, SEM_BARRAMENTO, "isto não é caminho de aparelho")
        return self.chamar(
            forma.group(1), ADAPTADOR, "RemoveDevice", "o", (caminho_do_aparelho,)
        )

    def confiar(self, caminho: str, sim: bool = True) -> Escrita:
        """``Trusted`` — o aparelho reconecta sem pedir licença ao agente."""
        return self.escrever_propriedade(caminho, APARELHO, "Trusted", "b", bool(sim))

    def parear(self, caminho: str, *, espera: float = ESPERA_DO_PAIR_S) -> Escrita:
        """``Pair`` e, se deu, ``Trusted``. Aqui sem agente próprio: o BlueZ usa o padrão."""
        escrita = self.chamar(caminho, APARELHO, "Pair", espera=espera)
        if escrita.feita:
            self.confiar(caminho)
        return escrita

    def comecar_busca(self, caminho_do_adaptador: str) -> Escrita:
        """``StartDiscovery`` — só vale na conexão viva: a busca é POR CLIENTE."""
        return Escrita(False, SEM_BARRAMENTO, "a busca só vale numa conexão que fica")

    def parar_busca(self, caminho_do_adaptador: str) -> Escrita:
        """``StopDiscovery`` do NOSSO cliente — a busca alheia não se para de fora."""
        return Escrita(False, SEM_BARRAMENTO, "a busca só vale numa conexão que fica")

    # -- o lugar (D3) ---------------------------------------------------------

    def conferir_os_lugares(
        self, *, memoria: Path | None = None
    ) -> tuple[MudancaDeLugar, ...]:
        """Compara o lugar de cada adaptador com o da última vez, e guarda o de agora.

        Trocar o dongle de porta é PERCEBIDO e dito: cada mudança vai ao diário
        com a frase dela; a tela lê o que esta função devolve. A memória é nossa
        (``~/.local/state``), nunca do BlueZ nem do ``maquina.json`` dela.
        """
        adaptadores = self.adaptadores()
        if not adaptadores:
            return ()
        agora = {a.lugar: a.endereco for a in adaptadores if a.lugar}
        if not agora:
            return ()
        arquivo = memoria if memoria is not None else _memoria_dos_lugares()
        try:
            antes_bruto = json.loads(arquivo.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            antes_bruto = {}
        antes = {
            str(lugar): str(endereco)
            for lugar, endereco in (antes_bruto.items() if isinstance(antes_bruto, dict) else ())
        }
        mudancas = perceber_as_mudancas(antes, agora)
        guardado = dict(antes)
        for mudanca in mudancas:
            if mudanca.lugar_antigo and guardado.get(mudanca.lugar_antigo) == mudanca.endereco:
                del guardado[mudanca.lugar_antigo]
        guardado.update(agora)
        with contextlib.suppress(OSError):
            arquivo.parent.mkdir(parents=True, exist_ok=True)
            temporario = arquivo.with_suffix(".tmp")
            temporario.write_text(
                json.dumps(guardado, ensure_ascii=False, indent=1, sort_keys=True),
                encoding="utf-8",
            )
            temporario.replace(arquivo)
        for mudanca in mudancas:
            _registrar(
                "bluez_adaptador_mudou_de_lugar",
                tipo=mudanca.tipo,
                lugar=mudanca.lugar,
                lugar_antigo=mudanca.lugar_antigo,
                endereco=_mascara(mudanca.endereco),
            )
        return mudancas


#: As escritas no BlueZ. Todo método público de :class:`LeitorDoBluez` e das
#: subclasses está numa destas três listas — a régua cobra.
ESCRITAS = (
    "chamar",
    "escrever_propriedade",
    "escrever_alias",
    "conectar",
    "desconectar",
    "remover_aparelho",
    "confiar",
    "parear",
    "comecar_busca",
    "parar_busca",
)
LEITURAS = (
    "pode_perguntar",
    "caminhos",
    "propriedade",
    "endereco_do_adaptador",
    "adaptadores",
    "aparelhos",
    "caminho_do_adaptador",
    "caminho_do_aparelho",
    "conferir_os_lugares",
    "dono_do_bluez",
)
CICLO = ("ligar", "fechar")


# ---------------------------------------------------------------------------
# O caminho de reserva: ``busctl``. E a forma dos dublês.
# ---------------------------------------------------------------------------


def _texto_do_busctl(valor: Any) -> str:
    if isinstance(valor, bool):
        return "true" if valor else "false"
    return str(valor)


class PeloBusctl(LeitorDoBluez):
    """O BlueZ por ``busctl``, uma pergunta por subprocesso.

    ``executar`` injetado é um DUBLÊ (a forma que a suíte sempre usou): ele não
    é o sistema, então a guarda não o recusa, e o kernel e o sysfs não são
    consultados — o dublê responde pela mesa inteira.
    """

    def __init__(self, executar: Executar | None = None) -> None:
        self._executar = executar
        self.toca_o_sistema = executar is None

    def _rodar(self, argumentos: Sequence[str], espera: float | None) -> str | None:
        if self._executar is not None:
            return self._executar(argumentos)
        return busctl(argumentos, espera=ESPERA_DO_BUSCTL_S if espera is None else espera)

    def pode_perguntar(self) -> bool:
        return self._executar is not None or shutil.which(FERRAMENTA) is not None

    def caminhos(self, *, espera: float | None = None) -> tuple[str, ...] | None:
        bruto = self._rodar(["tree", SERVICO, "--list"], espera)
        if bruto is None:
            return None
        return tuple(linha.strip() for linha in bruto.splitlines() if linha.strip())

    def propriedade(
        self, caminho: str, interface: str, nome: str, *, espera: float | None = None
    ) -> Any | None:
        return desembrulhar(
            self._rodar(["get-property", SERVICO, caminho, interface, nome], espera)
        )

    def _chamar(
        self,
        caminho: str,
        interface: str,
        metodo: str,
        assinatura: str,
        argumentos: Sequence[Any],
        espera: float,
    ) -> Escrita:
        linha = ["call", SERVICO, caminho, interface, metodo]
        if assinatura:
            linha += [assinatura, *(_texto_do_busctl(a) for a in argumentos)]
        bruto = self._rodar(linha, espera)
        if bruto is None:
            return Escrita(False, mensagem="o busctl não confirmou")
        return Escrita(True, resposta=bruto)

    def _escrever(
        self,
        caminho: str,
        interface: str,
        nome: str,
        assinatura: str,
        valor: Any,
        espera: float,
    ) -> Escrita:
        bruto = self._rodar(
            ["set-property", SERVICO, caminho, interface, nome, assinatura, _texto_do_busctl(valor)],
            espera,
        )
        if bruto is None:
            return Escrita(False, mensagem="o busctl não confirmou")
        return Escrita(True, resposta=bruto)

    def _enderecos_do_kernel(self) -> Mapping[str, str] | None:
        return enderecos_pelo_ioctl() if self._executar is None else None

    def _lugares(self) -> Mapping[str, str]:
        return lugares_dos_adaptadores() if self._executar is None else {}


def pelo_executor(executar: Executar) -> PeloBusctl:
    """Um leitor sobre um executor no formato ``busctl`` — o dublê da suíte."""
    return PeloBusctl(executar)


def pela_linha_de_comando(executor: Callable[[Sequence[str]], str]) -> PeloBusctl:
    """Um leitor sobre um executor de LINHA INTEIRA (o de ``conexao_zumbi``).

    Aquele executor recebe o comando com o programa na frente e devolve ``""``
    quando não deu; aqui ele ganha a forma dos outros dublês.
    """

    def rodar(argumentos: Sequence[str]) -> str | None:
        return executor([FERRAMENTA, *argumentos]) or None

    return PeloBusctl(rodar)


# ---------------------------------------------------------------------------
# O caminho vivo: Gio, a assinatura do ObjectManager e a foto em memória.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Sinal:
    """Um sinal do barramento, já traduzido para Python.

    ``tipo``: ``entrou`` (``InterfacesAdded``), ``saiu`` (``InterfacesRemoved``),
    ``mudou`` (``PropertiesChanged``) ou ``dono`` (``NameOwnerChanged`` do
    ``org.bluez``; ``dono_novo`` vazio quer dizer que o ``bluetoothd`` saiu).
    """

    tipo: str
    caminho: str = ""
    interface: str = ""
    propriedades: Mapping[str, Mapping[str, Any]] | None = None
    mudadas: Mapping[str, Any] | None = None
    invalidadas: tuple[str, ...] = ()
    interfaces_que_sairam: tuple[str, ...] = ()
    dono_novo: str = ""


class Barramento(Protocol):
    """A costura entre o dono e um barramento. O de verdade é :class:`BarramentoGio`."""

    e_do_sistema: bool

    def vivo(self) -> bool: ...

    def nome_unico(self) -> str: ...

    def dono_do_nome(self, nome: str) -> str: ...

    def objetos(self, *, espera: float) -> dict[str, dict[str, dict[str, Any]]] | None: ...

    def assinar(self, ao_sinal: Callable[[Sinal], None]) -> bool: ...

    def chamar(
        self,
        destino: str,
        caminho: str,
        interface: str,
        metodo: str,
        assinatura: str,
        argumentos: Sequence[Any],
        *,
        espera: float,
    ) -> Escrita: ...

    def escrever(
        self,
        caminho: str,
        interface: str,
        nome: str,
        assinatura: str,
        valor: Any,
        *,
        espera: float,
    ) -> Escrita: ...

    def exportar(
        self, caminho: str, xml: str, tratador: Callable[[str, str, tuple[Any, ...]], Any]
    ) -> bool: ...

    def retirar(self, caminho: str) -> None: ...

    def fechar(self) -> None: ...


class BarramentoGio:
    """O barramento de verdade, por uma conexão PRÓPRIA e um fio PRÓPRIO.

    Conexão própria porque o agente (R5) se registra pelo nome único dela, e o
    BlueZ atende o ``Pair`` pelo agente do MESMO remetente (``agent_get(sender)``,
    ``src/agent.c``). Fio próprio porque sinal e objeto exportado são entregues
    no contexto do fio que os assinou: um ``GLib.MainLoop`` num contexto privado
    não disputa nada com o laço do GTK nem com o asyncio do daemon.

    ``endereco`` ``None`` é o barramento de sistema; a suíte passa o endereço de
    um ``dbus-daemon`` particular.
    """

    def __init__(self, endereco: str | None = None) -> None:
        self.e_do_sistema = endereco is None
        self._endereco = endereco
        self._gio: Any = None
        self._glib: Any = None
        self._contexto: Any = None
        self._laco: Any = None
        self._conexao: Any = None
        self._fio: threading.Thread | None = None
        self._pronto = threading.Event()
        self._assinaturas: list[int] = []
        self._exportados: dict[str, int] = {}
        self.erro = ""

    def abrir(self, *, espera: float = 2.0) -> bool:
        """Liga o fio e a conexão. ``False`` quando não deu, com :attr:`erro`."""
        try:
            from gi.repository import Gio, GLib
        except Exception as problema:  # ImportError, ValueError ou stub sem Gio
            self.erro = f"sem Gio: {problema}"
            return False
        self._gio, self._glib = Gio, GLib
        self._contexto = GLib.MainContext.new()
        self._laco = GLib.MainLoop.new(self._contexto, False)
        self._fio = threading.Thread(target=self._viver, name="hefesto-bluez", daemon=True)
        self._fio.start()
        if not self._pronto.wait(espera):
            self.erro = "o barramento não respondeu a tempo"
            return False
        return self._conexao is not None

    def _viver(self) -> None:
        gio = self._gio
        self._contexto.push_thread_default()
        try:
            endereco = self._endereco or gio.dbus_address_get_for_bus_sync(
                gio.BusType.SYSTEM, None
            )
            conexao = gio.DBusConnection.new_for_address_sync(
                endereco,
                gio.DBusConnectionFlags.AUTHENTICATION_CLIENT
                | gio.DBusConnectionFlags.MESSAGE_BUS_CONNECTION,
                None,
                None,
            )
            conexao.set_exit_on_close(False)
            self._conexao = conexao
        except Exception as problema:
            self.erro = str(problema)
            self._pronto.set()
            self._contexto.pop_thread_default()
            return
        self._pronto.set()
        try:
            self._laco.run()
        finally:
            self._contexto.pop_thread_default()

    def _no_fio(self, funcao: Callable[[], Any], *, espera: float = 2.0) -> Any:
        """Roda ``funcao`` no fio do barramento e devolve o resultado."""
        if threading.current_thread() is self._fio:
            return funcao()
        caixa: dict[str, Any] = {}
        feito = threading.Event()

        def rodar() -> bool:
            try:
                caixa["valor"] = funcao()
            except Exception as problema:
                caixa["erro"] = problema
            feito.set()
            return False

        fonte = self._glib.idle_source_new()
        fonte.set_callback(rodar)
        fonte.attach(self._contexto)
        if not feito.wait(espera):
            return None
        return caixa.get("valor")

    def vivo(self) -> bool:
        conexao = self._conexao
        return (
            conexao is not None
            and not conexao.is_closed()
            and self._fio is not None
            and self._fio.is_alive()
        )

    def nome_unico(self) -> str:
        return self._conexao.get_unique_name() if self._conexao is not None else ""

    def dono_do_nome(self, nome: str) -> str:
        escrita = self.chamar(
            BARRAMENTO_DBUS,
            "/org/freedesktop/DBus",
            BARRAMENTO_DBUS,
            "GetNameOwner",
            "s",
            (nome,),
            espera=ESPERA_DO_BUSCTL_S,
        )
        if not escrita.feita or not escrita.resposta:
            return ""
        return str(escrita.resposta[0])

    def objetos(self, *, espera: float) -> dict[str, dict[str, dict[str, Any]]] | None:
        escrita = self.chamar(
            SERVICO, "/", OBJETOS, "GetManagedObjects", "", (), espera=espera
        )
        if not escrita.feita or not escrita.resposta:
            return None
        bruto = escrita.resposta[0]
        return {
            str(caminho): {str(i): dict(p) for i, p in interfaces.items()}
            for caminho, interfaces in bruto.items()
        }

    def assinar(self, ao_sinal: Callable[[Sinal], None]) -> bool:
        gio = self._gio

        def chegou(
            _conexao: Any,
            _remetente: str,
            caminho: str,
            interface: str,
            nome: str,
            parametros: Any,
            *_dados: Any,
        ) -> None:
            try:
                valores = parametros.unpack()
                if nome == "InterfacesAdded":
                    ao_sinal(Sinal("entrou", caminho=valores[0], propriedades=valores[1]))
                elif nome == "InterfacesRemoved":
                    ao_sinal(
                        Sinal("saiu", caminho=valores[0], interfaces_que_sairam=tuple(valores[1]))
                    )
                elif nome == "PropertiesChanged":
                    ao_sinal(
                        Sinal(
                            "mudou",
                            caminho=caminho,
                            interface=valores[0],
                            mudadas=valores[1],
                            invalidadas=tuple(valores[2]),
                        )
                    )
                elif nome == "NameOwnerChanged" and valores[0] == SERVICO:
                    ao_sinal(Sinal("dono", dono_novo=valores[2]))
            except Exception:
                return

        def assinar_no_fio() -> bool:
            conexao = self._conexao
            nenhum = gio.DBusSignalFlags.NONE
            self._assinaturas = [
                conexao.signal_subscribe(
                    SERVICO, OBJETOS, "InterfacesAdded", None, None, nenhum, chegou
                ),
                conexao.signal_subscribe(
                    SERVICO, OBJETOS, "InterfacesRemoved", None, None, nenhum, chegou
                ),
                conexao.signal_subscribe(
                    SERVICO,
                    PROPRIEDADES,
                    "PropertiesChanged",
                    None,
                    SERVICO,
                    gio.DBusSignalFlags.MATCH_ARG0_NAMESPACE,
                    chegou,
                ),
                conexao.signal_subscribe(
                    BARRAMENTO_DBUS,
                    BARRAMENTO_DBUS,
                    "NameOwnerChanged",
                    "/org/freedesktop/DBus",
                    SERVICO,
                    nenhum,
                    chegou,
                ),
            ]
            return True

        return bool(self._no_fio(assinar_no_fio))

    def chamar(
        self,
        destino: str,
        caminho: str,
        interface: str,
        metodo: str,
        assinatura: str,
        argumentos: Sequence[Any],
        *,
        espera: float,
    ) -> Escrita:
        conexao = self._conexao
        if conexao is None:
            return Escrita(False, SEM_BARRAMENTO, self.erro)
        glib, gio = self._glib, self._gio
        parametros = (
            glib.Variant(f"({assinatura})", tuple(argumentos)) if assinatura else None
        )
        try:
            resposta = conexao.call_sync(
                destino,
                caminho,
                interface,
                metodo,
                parametros,
                None,
                gio.DBusCallFlags.NONE,
                int(max(_MINIMO_POR_PERGUNTA, espera) * 1000),
                None,
            )
        except glib.Error as problema:
            nome = gio.DBusError.get_remote_error(problema) or ""
            return Escrita(False, nome, problema.message)
        except Exception as problema:
            return Escrita(False, SEM_BARRAMENTO, str(problema))
        return Escrita(True, resposta=resposta.unpack() if resposta is not None else ())

    def escrever(
        self, caminho: str, interface: str, nome: str, assinatura: str, valor: Any, *, espera: float
    ) -> Escrita:
        """``Properties.Set`` no ``org.bluez``, com o valor já no tipo do D-Bus."""
        conexao = self._conexao
        if conexao is None:
            return Escrita(False, SEM_BARRAMENTO, self.erro)
        glib, gio = self._glib, self._gio
        try:
            conexao.call_sync(
                SERVICO,
                caminho,
                PROPRIEDADES,
                "Set",
                glib.Variant("(ssv)", (interface, nome, glib.Variant(assinatura, valor))),
                None,
                gio.DBusCallFlags.NONE,
                int(max(_MINIMO_POR_PERGUNTA, espera) * 1000),
                None,
            )
        except glib.Error as problema:
            return Escrita(False, gio.DBusError.get_remote_error(problema) or "", problema.message)
        except Exception as problema:
            return Escrita(False, SEM_BARRAMENTO, str(problema))
        return Escrita(True)

    def exportar(
        self, caminho: str, xml: str, tratador: Callable[[str, str, tuple[Any, ...]], Any]
    ) -> bool:
        gio, glib = self._gio, self._glib
        if self._conexao is None or caminho in self._exportados:
            return caminho in self._exportados
        info = gio.DBusNodeInfo.new_for_xml(xml).interfaces[0]

        def atender(
            _conexao: Any,
            remetente: str,
            _caminho: str,
            _interface: str,
            metodo: str,
            parametros: Any,
            invocacao: Any,
        ) -> None:
            try:
                resultado = tratador(remetente, metodo, tuple(parametros.unpack()))
            except RecusaNoBarramento as recusa:
                invocacao.return_dbus_error(recusa.nome, recusa.mensagem)
                return
            except Exception:
                invocacao.return_dbus_error(ERRO_REJEITADO, "o agente não conseguiu atender")
                return
            saidas = info.lookup_method(metodo).out_args or []
            assinatura = "".join(argumento.signature for argumento in saidas)
            if assinatura:
                invocacao.return_value(glib.Variant(f"({assinatura})", tuple(resultado)))
            else:
                invocacao.return_value(None)

        def registrar_no_fio() -> int:
            return int(self._conexao.register_object(caminho, info, atender, None, None))

        numero = self._no_fio(registrar_no_fio)
        if not numero:
            return False
        self._exportados[caminho] = numero
        return True

    def retirar(self, caminho: str) -> None:
        numero = self._exportados.pop(caminho, 0)
        if numero and self._conexao is not None:
            self._no_fio(lambda: self._conexao.unregister_object(numero))

    def fechar(self) -> None:
        conexao = self._conexao
        if conexao is None:
            return

        def fechar_no_fio() -> bool:
            for numero in self._assinaturas:
                conexao.signal_unsubscribe(numero)
            self._assinaturas = []
            for numero in self._exportados.values():
                conexao.unregister_object(numero)
            self._exportados = {}
            with contextlib.suppress(Exception):
                conexao.close_sync(None)
            self._laco.quit()
            return True

        self._no_fio(fechar_no_fio)
        if self._fio is not None and self._fio is not threading.current_thread():
            self._fio.join(timeout=2.0)


class DonoVivo(LeitorDoBluez):
    """O dono de verdade: a foto do ``ObjectManager``, mantida pelos sinais.

    Assina ANTES de tirar a primeira foto: um sinal que chegue no meio é
    reaplicado depois dela, e reaplicar o mesmo valor não muda nada.
    """

    atende_o_proprio_pareamento = True

    def __init__(self, barramento: Barramento) -> None:
        self._barramento = barramento
        self.toca_o_sistema = bool(getattr(barramento, "e_do_sistema", False))
        self._tranca = threading.Lock()
        self._objetos: dict[str, dict[str, dict[str, Any]]] = {}
        self._bluez_de_pe = False
        self._dono_do_bluez = ""
        self._agente: Any = None
        self._tranca_do_agente = threading.Lock()

    # -- ciclo ----------------------------------------------------------------

    def ligar(self) -> bool:
        """Assina os sinais e tira a primeira foto. ``False`` se o barramento não deu."""
        if not self._barramento.vivo():
            return False
        if not self._barramento.assinar(self._ao_sinal):
            return False
        self._fotografar()
        return True

    def fechar(self) -> None:
        """Desregistra o agente próprio e fecha a conexão. Idempotente."""
        with self._tranca_do_agente:
            agente, self._agente = self._agente, None
        if agente is not None:
            agente.desregistrar()
        self._barramento.fechar()

    def _fotografar(self) -> None:
        foto = self._barramento.objetos(espera=ESPERA_DA_FOTO_S)
        dono = self._barramento.dono_do_nome(SERVICO)
        with self._tranca:
            self._objetos = foto or {}
            self._bluez_de_pe = foto is not None
            self._dono_do_bluez = dono

    def _ao_sinal(self, sinal: Sinal) -> None:
        if sinal.tipo == "dono":
            if not sinal.dono_novo:
                with self._tranca:
                    self._objetos = {}
                    self._bluez_de_pe = False
                    self._dono_do_bluez = ""
                with self._tranca_do_agente:
                    if self._agente is not None:
                        self._agente.invalidar()
                _registrar("bluez_saiu_do_barramento", nivel="warning")
            else:
                self._fotografar()
                _registrar("bluez_voltou_ao_barramento")
            return
        with self._tranca:
            if sinal.tipo == "entrou":
                objeto = self._objetos.setdefault(sinal.caminho, {})
                for interface, propriedades in (sinal.propriedades or {}).items():
                    objeto[interface] = dict(propriedades)
            elif sinal.tipo == "saiu":
                objeto = self._objetos.get(sinal.caminho)
                if objeto is not None:
                    for interface in sinal.interfaces_que_sairam:
                        objeto.pop(interface, None)
                    if not objeto:
                        del self._objetos[sinal.caminho]
            elif sinal.tipo == "mudou":
                propriedades = self._objetos.setdefault(sinal.caminho, {}).setdefault(
                    sinal.interface, {}
                )
                propriedades.update(sinal.mudadas or {})
                for nome in sinal.invalidadas:
                    propriedades.pop(nome, None)

    # -- leitura: a foto ------------------------------------------------------

    def pode_perguntar(self) -> bool:
        return self._barramento.vivo()

    def caminhos(self, *, espera: float | None = None) -> tuple[str, ...] | None:
        with self._tranca:
            if not self._bluez_de_pe:
                return None
            return tuple(sorted(self._objetos))

    def propriedade(
        self, caminho: str, interface: str, nome: str, *, espera: float | None = None
    ) -> Any | None:
        with self._tranca:
            return self._objetos.get(caminho, {}).get(interface, {}).get(nome)

    def dono_do_bluez(self) -> str:
        """O nome único do ``bluetoothd`` de agora — o único que pode chamar o agente."""
        with self._tranca:
            return self._dono_do_bluez

    def _enderecos_do_kernel(self) -> Mapping[str, str] | None:
        return enderecos_pelo_ioctl() if self.toca_o_sistema else None

    def _lugares(self) -> Mapping[str, str]:
        return lugares_dos_adaptadores() if self.toca_o_sistema else {}

    # -- escrita: a conexão ---------------------------------------------------

    def _chamar(
        self,
        caminho: str,
        interface: str,
        metodo: str,
        assinatura: str,
        argumentos: Sequence[Any],
        espera: float,
    ) -> Escrita:
        return self._barramento.chamar(
            SERVICO, caminho, interface, metodo, assinatura, argumentos, espera=espera
        )

    def _escrever(
        self,
        caminho: str,
        interface: str,
        nome: str,
        assinatura: str,
        valor: Any,
        espera: float,
    ) -> Escrita:
        return self._barramento.escrever(
            caminho, interface, nome, assinatura, valor, espera=espera
        )

    def comecar_busca(self, caminho_do_adaptador: str) -> Escrita:
        """``StartDiscovery`` pela NOSSA conexão — a busca vive enquanto ela viver."""
        return self.chamar(caminho_do_adaptador, ADAPTADOR, "StartDiscovery")

    def parar_busca(self, caminho_do_adaptador: str) -> Escrita:
        """``StopDiscovery`` — só a busca que NÓS abrimos; a alheia recusa por si."""
        return self.chamar(caminho_do_adaptador, ADAPTADOR, "StopDiscovery")

    def parear(self, caminho: str, *, espera: float = ESPERA_DO_PAIR_S) -> Escrita:
        """``Pair`` atendido pelo NOSSO agente (R5), e ``Trusted`` se deu.

        O BlueZ 5.86 escolhe o agente do pareamento por ``agent_get(sender)``
        (``src/device.c``, ``pair_device``): quem chama ``Pair`` com agente
        registrado é atendido pelo PRÓPRIO agente, seja quem for o padrão. Por
        isso o agente mora nesta conexão e o ``Pair`` sai por ela. Nunca
        ``RequestDefaultAgent``: o ``hefesto-bt-agent`` continua o padrão, de
        piso, para o que chega sozinho.
        """
        recusa = self._recusa()
        if recusa is not None:
            return recusa
        agente = self._agente_pronto()
        if agente is None:
            return Escrita(False, SEM_AGENTE, "o agente próprio não se registrou")
        with agente.esperando(caminho):
            escrita = self.chamar(caminho, APARELHO, "Pair", espera=espera)
        if escrita.feita:
            self.confiar(caminho)
        return escrita

    def _agente_pronto(self) -> Any:
        from hefesto_dualsense4unix.integrations.agente_de_pareamento import (
            AgenteDePareamento,
        )

        with self._tranca_do_agente:
            if self._agente is None:
                self._agente = AgenteDePareamento(self._barramento, self.dono_do_bluez)
            return self._agente if self._agente.registrar() else None


# ---------------------------------------------------------------------------
# O dono do processo.
# ---------------------------------------------------------------------------

_DONO: LeitorDoBluez | None = None
_GIO_FALHOU_EM: float | None = None
_TRANCA_DO_DONO = threading.Lock()


def _ligar_o_dono_do_sistema() -> DonoVivo | None:
    barramento = BarramentoGio()
    if not barramento.abrir():
        _registrar("bluez_sem_gio", motivo=barramento.erro[:200])
        return None
    vivo = DonoVivo(barramento)
    if not vivo.ligar():
        barramento.fechar()
        return None
    atexit.register(vivo.fechar)
    _registrar("bluez_dono_vivo", nome=barramento.nome_unico())
    return vivo


def dono() -> LeitorDoBluez:
    """O dono do BlueZ deste processo: o vivo quando o Gio alcança, o ``busctl`` quando não.

    Sob a suíte NUNCA nasce o vivo do sistema: a suíte lê pelo ``busctl`` do
    ``PATH`` (que a régua troca por um de mentira) e a borda recusa a escrita.
    """
    global _DONO, _GIO_FALHOU_EM
    with _TRANCA_DO_DONO:
        atual = _DONO
        if atual is not None and atual.pode_perguntar():
            return atual
        if a_suite_esta_rodando():
            return PeloBusctl()
        agora = time.monotonic()
        if _GIO_FALHOU_EM is None or agora - _GIO_FALHOU_EM >= TENTAR_O_GIO_DE_NOVO_S:
            vivo = _ligar_o_dono_do_sistema()
            if vivo is not None:
                _DONO = vivo
                _GIO_FALHOU_EM = None
                return vivo
            _GIO_FALHOU_EM = agora
        return PeloBusctl()


__all__ = [
    "ADAPTADOR",
    "AGENTE",
    "APARELHO",
    "CICLO",
    "ERRO_ACESSO_NEGADO",
    "ERRO_CANCELADO",
    "ERRO_JA_EXISTE",
    "ERRO_REJEITADO",
    "ESCRITAS",
    "ESPERA_DO_BUSCTL_S",
    "ESPERA_DO_CONNECT_S",
    "ESPERA_DO_PAIR_S",
    "FERRAMENTA",
    "GERENTE_DE_AGENTES",
    "LEITURAS",
    "RADIO_DE_VERDADE_NA_SUITE",
    "RECUSA_DA_SUITE",
    "SEM_AGENTE",
    "SEM_BARRAMENTO",
    "SERVICO",
    "AdaptadorDoBluez",
    "AparelhoDoBluez",
    "Barramento",
    "BarramentoGio",
    "DonoVivo",
    "Escrita",
    "LeitorDoBluez",
    "MudancaDeLugar",
    "PeloBusctl",
    "RecusaNoBarramento",
    "Sinal",
    "a_suite_esta_rodando",
    "busctl",
    "como_booleano",
    "desembrulhar",
    "dono",
    "enderecos_pelo_ioctl",
    "lugar_de",
    "lugares_dos_adaptadores",
    "pela_linha_de_comando",
    "pelo_executor",
    "perceber_as_mudancas",
]
