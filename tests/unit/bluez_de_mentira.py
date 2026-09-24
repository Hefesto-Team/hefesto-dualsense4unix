"""Dois BlueZ de mentira para as réguas do dono do D-Bus — BLUEZ-UM-DONO-01.

**Este módulo não é um arquivo de teste** — é a bancada que três arquivos de
teste usam (`test_o_bluez_tem_um_dono.py`, `test_o_agente_proprio.py` e
`test_o_flatpak_alcanca_o_bluez.py`, que põe o proxy do Flatpak na frente).

1. :class:`BarramentoDeMentira` — em processo, sem D-Bus nenhum. Implementa a
   costura ``bluez_dbus.Barramento`` e deixa a régua EMITIR sinais à mão.
2. :class:`BluezParticular` — um ``dbus-daemon`` particular, um BlueZ de mentira
   exportado nele pelo Gio, e um ``bt-agent`` de mentira que pede para ser o
   padrão. O BlueZ de mentira escolhe o agente do ``Pair`` como o 5.86:
   ``agent_get(sender)`` — o agente do MESMO remetente, senão o padrão
   (``src/device.c:3374`` e ``src/agent.c:247``). É o que prova o caminho do
   Gio de verdade sem tocar no barramento de sistema dela.

Faixa sintética da casa: ``aa:bb:cc`` com os octetos 4 e 5 zerados, e ``hci9``,
fora da faixa da mesa dela.
"""

from __future__ import annotations

import copy
import shutil
import subprocess
import threading
import time
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

from hefesto_dualsense4unix.integrations import bluez_dbus as bd

ADAPTADOR = "aa:bb:cc:00:00:11"
CONTROLE = "aa:bb:cc:00:00:22"
OUTRO = "aa:bb:cc:00:00:33"
HCI = "/org/bluez/hci9"


def no_de(mac: str) -> str:
    """O caminho D-Bus deste endereço sob :data:`HCI`."""
    return f"{HCI}/dev_{mac.upper().replace(':', '_')}"


def mesa_inicial() -> dict[str, dict[str, dict[str, Any]]]:
    """Um adaptador parado, um controle ainda não pareado e um outro aparelho."""
    return {
        "/org/bluez": {bd.GERENTE_DE_AGENTES: {}},
        HCI: {
            bd.ADAPTADOR: {
                "Address": ADAPTADOR.upper(),
                "Alias": "Sala de mentira",
                "Name": "mentira",
                "Powered": True,
                "Discovering": False,
            }
        },
        no_de(CONTROLE): {
            bd.APARELHO: {
                "Address": CONTROLE.upper(),
                "Alias": "DualSense Wireless Controller",
                "Paired": False,
                "Bonded": False,
                "Trusted": False,
                "Connected": False,
                "Class": 9480,
                "Modalias": "usb:v054Cp0CE6d0100",
            }
        },
        no_de(OUTRO): {
            bd.APARELHO: {
                "Address": OUTRO.upper(),
                "Alias": "fone\tda\nvizinha",
                "Paired": False,
                "Connected": False,
            }
        },
    }


# ---------------------------------------------------------------------------
# 1. Em processo.
# ---------------------------------------------------------------------------


class BarramentoDeMentira:
    """A costura ``Barramento`` sem D-Bus. Anota tudo o que o dono pede.

    ``pair_chama_o_agente``: o ``Pair`` faz o que o BlueZ faz — procura o agente
    registrado pelo remetente (o nosso nome único) e, sem ele, o padrão.
    """

    NOME = ":1.42"
    DONO_DO_BLUEZ = ":1.7"

    def __init__(self, *, e_do_sistema: bool = False) -> None:
        self.e_do_sistema = e_do_sistema
        self.mesa = mesa_inicial()
        self.bluez_de_pe = True
        self.chamadas: list[tuple[str, str, str, tuple[Any, ...], float]] = []
        self.escritas: list[tuple[str, str, str, Any]] = []
        self.exportados: dict[str, Callable[[str, str, tuple[Any, ...]], Any]] = {}
        self.agentes: dict[str, tuple[str, str]] = {}
        self.padrao: list[str] = ["bt-agent"]
        self.o_padrao_atendeu: list[str] = []
        self.durante_a_foto: Callable[[], None] | None = None
        #: Quantas fotos ainda saem SEM resposta com o BlueZ de pé — o
        #: ``GetManagedObjects`` que estoura o prazo de um ``bluetoothd`` lento.
        self.fotos_que_falham = 0
        #: Quantos ``GetManagedObjects`` o dono pediu.
        self.fotos = 0
        self._ao_sinal: Callable[[bd.Sinal], None] | None = None
        self.fechado = False

    # -- a costura -----------------------------------------------------------

    def vivo(self) -> bool:
        return not self.fechado

    def nome_unico(self) -> str:
        return self.NOME

    def dono_do_nome(self, nome: str) -> str:
        return self.DONO_DO_BLUEZ if self.bluez_de_pe else ""

    def objetos(self, *, espera: float) -> dict[str, dict[str, dict[str, Any]]] | None:
        self.fotos += 1
        if self.bluez_de_pe and self.fotos_que_falham > 0:
            self.fotos_que_falham -= 1
            return None
        foto = copy.deepcopy(self.mesa) if self.bluez_de_pe else None
        if self.durante_a_foto is not None:
            self.durante_a_foto()
        return foto

    def assinar(self, ao_sinal: Callable[[bd.Sinal], None]) -> bool:
        self._ao_sinal = ao_sinal
        return True

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
    ) -> bd.Escrita:
        self.chamadas.append((caminho, interface, metodo, tuple(argumentos), time.monotonic()))
        if interface == bd.GERENTE_DE_AGENTES and metodo == "RegisterAgent":
            if self.NOME in self.agentes:
                return bd.Escrita(False, bd.ERRO_JA_EXISTE)
            self.agentes[self.NOME] = (str(argumentos[0]), str(argumentos[1]))
            return bd.Escrita(True, resposta=())
        if interface == bd.GERENTE_DE_AGENTES and metodo == "UnregisterAgent":
            self.agentes.pop(self.NOME, None)
            return bd.Escrita(True, resposta=())
        if interface == bd.GERENTE_DE_AGENTES and metodo == "RequestDefaultAgent":
            self.padrao.insert(0, self.NOME)
            return bd.Escrita(True, resposta=())
        if interface == bd.APARELHO and metodo == "Pair":
            return self._parear(caminho)
        return bd.Escrita(True, resposta=())

    def escrever(
        self, caminho: str, interface: str, nome: str, assinatura: str, valor: Any, *, espera: float
    ) -> bd.Escrita:
        self.escritas.append((caminho, interface, nome, valor))
        self.mesa.setdefault(caminho, {}).setdefault(interface, {})[nome] = valor
        return bd.Escrita(True)

    def exportar(
        self, caminho: str, xml: str, tratador: Callable[[str, str, tuple[Any, ...]], Any]
    ) -> bool:
        self.exportados[caminho] = tratador
        return True

    def retirar(self, caminho: str) -> None:
        self.exportados.pop(caminho, None)

    def fechar(self) -> None:
        self.fechado = True

    # -- o que a régua faz ----------------------------------------------------

    def emitir(self, sinal: bd.Sinal) -> None:
        """Um sinal do barramento, como se o BlueZ o tivesse mandado."""
        assert self._ao_sinal is not None, "o dono não assinou nada"
        self._ao_sinal(sinal)

    def metodos(self) -> list[str]:
        return [metodo for _c, _i, metodo, _a, _t in self.chamadas]

    def _parear(self, caminho: str) -> bd.Escrita:
        agente = self.agentes.get(self.NOME)
        if agente is None:
            self.o_padrao_atendeu.append(caminho)
            return bd.Escrita(True, resposta=())
        tratador = self.exportados.get(agente[0])
        if tratador is None:
            return bd.Escrita(False, "org.bluez.Error.AuthenticationFailed")
        try:
            tratador(self.DONO_DO_BLUEZ, "RequestConfirmation", (caminho, 123456))
        except bd.RecusaNoBarramento as recusa:
            return bd.Escrita(False, recusa.nome, recusa.mensagem)
        self.mesa[caminho][bd.APARELHO]["Paired"] = True
        return bd.Escrita(True, resposta=())


# ---------------------------------------------------------------------------
# 2. Um dbus-daemon particular, com um BlueZ e um bt-agent de mentira.
# ---------------------------------------------------------------------------

_CONFIG = """<!DOCTYPE busconfig PUBLIC "-//freedesktop//DTD D-BUS Bus Configuration 1.0//EN"
 "http://www.freedesktop.org/standards/dbus/1.0/busconfig.dtd">
<busconfig>
  <type>session</type>
  <listen>unix:path={soquete}</listen>
  <auth>EXTERNAL</auth>
  <policy context="default">
    <allow send_destination="*" eavesdrop="true"/>
    <allow eavesdrop="true"/>
    <allow own="*"/>
  </policy>
</busconfig>
"""

_XML_DO_BLUEZ = f"""<node>
<interface name='{bd.OBJETOS}'>
  <method name='GetManagedObjects'><arg type='a{{oa{{sa{{sv}}}}}}' direction='out'/></method>
</interface>
<interface name='{bd.GERENTE_DE_AGENTES}'>
  <method name='RegisterAgent'><arg type='o' direction='in'/><arg type='s' direction='in'/></method>
  <method name='UnregisterAgent'><arg type='o' direction='in'/></method>
  <method name='RequestDefaultAgent'><arg type='o' direction='in'/></method>
</interface>
<interface name='{bd.ADAPTADOR}'>
  <method name='StartDiscovery'/>
  <method name='StopDiscovery'/>
  <method name='RemoveDevice'><arg type='o' direction='in'/></method>
</interface>
<interface name='{bd.APARELHO}'>
  <method name='Pair'/>
  <method name='Connect'/>
  <method name='Disconnect'/>
</interface>
<interface name='{bd.PROPRIEDADES}'>
  <method name='Set'>
    <arg type='s' direction='in'/><arg type='s' direction='in'/><arg type='v' direction='in'/>
  </method>
</interface>
</node>"""

_XML_DO_AGENTE = f"""<node><interface name='{bd.AGENTE}'>
  <method name='Release'/>
  <method name='RequestConfirmation'>
    <arg type='o' direction='in'/><arg type='u' direction='in'/>
  </method>
  <method name='RequestAuthorization'><arg type='o' direction='in'/></method>
  <method name='Cancel'/>
</interface></node>"""

#: O tipo D-Bus de cada propriedade da mesa de mentira.
_TIPOS = {"Class": "u", "RSSI": "n"}


def _tipo(nome: str, valor: Any) -> str:
    if nome in _TIPOS:
        return _TIPOS[nome]
    return "b" if isinstance(valor, bool) else "s"


def ha_dbus_daemon() -> bool:
    """O ``dbus-daemon`` e o Gio estão nesta máquina? Sem eles, a régua pula."""
    if shutil.which("dbus-daemon") is None:
        return False
    try:
        from gi.repository import Gio  # noqa: F401
    except Exception:
        return False
    return True


class _Fio:
    """Uma conexão Gio com laço próprio — o jeito de o BlueZ e o bt-agent de
    mentira atenderem enquanto o fio da régua espera um ``Pair``."""

    def __init__(self, endereco: str, nome: str) -> None:
        from gi.repository import Gio, GLib

        self.Gio, self.GLib = Gio, GLib
        self.contexto = GLib.MainContext.new()
        self.laco = GLib.MainLoop.new(self.contexto, False)
        self.pronto = threading.Event()
        self.conexao: Any = None
        self._endereco = endereco
        self.fio = threading.Thread(target=self._viver, name=nome, daemon=True)
        self.fio.start()
        assert self.pronto.wait(5), f"{nome} não conectou"

    def _viver(self) -> None:
        self.contexto.push_thread_default()
        self.conexao = self.Gio.DBusConnection.new_for_address_sync(
            self._endereco,
            self.Gio.DBusConnectionFlags.AUTHENTICATION_CLIENT
            | self.Gio.DBusConnectionFlags.MESSAGE_BUS_CONNECTION,
            None,
            None,
        )
        self.conexao.set_exit_on_close(False)
        self.pronto.set()
        self.laco.run()
        self.contexto.pop_thread_default()

    def no_fio(self, tarefa: Callable[[], Any]) -> Any:
        caixa: dict[str, Any] = {}
        feito = threading.Event()

        def rodar(*_dados: Any) -> bool:
            caixa["v"] = tarefa()
            feito.set()
            return False

        fonte = self.GLib.idle_source_new()
        fonte.set_callback(rodar)
        fonte.attach(self.contexto)
        assert feito.wait(5)
        return caixa.get("v")

    def exportar(self, caminho: str, xml: str, atender: Callable[..., None]) -> None:
        for info in self.Gio.DBusNodeInfo.new_for_xml(xml).interfaces:
            self.no_fio(
                lambda i=info: self.conexao.register_object(caminho, i, atender, None, None)
            )

    def chamar(
        self, destino: str, caminho: str, interface: str, metodo: str, parametros: Any = None
    ) -> Any:
        return self.conexao.call_sync(
            destino, caminho, interface, metodo, parametros, None,
            self.Gio.DBusCallFlags.NONE, 5000, None,
        )

    def fechar(self) -> None:
        conexao = self.conexao
        if conexao is not None and not conexao.is_closed():
            conexao.close_sync(None)
        self.laco.quit()
        self.fio.join(timeout=2)


class BluezParticular:
    """Um ``dbus-daemon`` particular, o BlueZ de mentira e o ``bt-agent`` padrão."""

    def __init__(self, raiz: Path) -> None:
        self.raiz = raiz
        self.mesa = mesa_inicial()
        self.agentes: dict[str, tuple[str, str]] = {}
        self.padroes: list[str] = []
        self.chamadas: list[tuple[str, str, str, str]] = []
        self.dono_da_busca = ""
        self.o_padrao_atendeu: list[str] = []
        self._processo: subprocess.Popen[str] | None = None
        self._fios: list[_Fio] = []
        self.endereco = ""

    # -- subir e descer -------------------------------------------------------

    def __enter__(self) -> BluezParticular:
        soquete = self.raiz / "barramento"
        config = self.raiz / "barramento.conf"
        config.write_text(_CONFIG.format(soquete=soquete), encoding="utf-8")
        self._processo = subprocess.Popen(
            ["dbus-daemon", "--config-file", str(config), "--print-address", "--nofork",
             "--nopidfile"],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
        )
        assert self._processo.stdout is not None
        self.endereco = self._processo.stdout.readline().strip()
        assert self.endereco, "o dbus-daemon particular não disse o endereço"
        self._subir_o_bluez("bluez-de-mentira")
        # O bt-agent de mentira: registra e pede para ser o PADRÃO, como o
        # `hefesto-bt-agent.service` faz na máquina dela.
        self.bt_agent = _Fio(self.endereco, "bt-agent-de-mentira")
        self._fios.append(self.bt_agent)
        self.bt_agent.exportar("/btagent", _XML_DO_AGENTE, self._atender_o_bt_agent)
        self._registrar_o_bt_agent()
        return self

    def _subir_o_bluez(self, nome: str) -> None:
        self.bluez = _Fio(self.endereco, nome)
        self._fios.append(self.bluez)
        self.bluez.chamar(
            bd.BARRAMENTO_DBUS, "/org/freedesktop/DBus", bd.BARRAMENTO_DBUS, "RequestName",
            self.bluez.GLib.Variant("(su)", (bd.SERVICO, 4)),
        )
        for caminho in ("/", *self.mesa):
            self.bluez.exportar(caminho, _XML_DO_BLUEZ, self._atender)

    def _registrar_o_bt_agent(self) -> None:
        variante = self.bt_agent.GLib.Variant
        self.bt_agent.chamar(bd.SERVICO, "/org/bluez", bd.GERENTE_DE_AGENTES, "RegisterAgent",
                             variante("(os)", ("/btagent", "NoInputNoOutput")))
        self.bt_agent.chamar(bd.SERVICO, "/org/bluez", bd.GERENTE_DE_AGENTES,
                             "RequestDefaultAgent", variante("(o)", ("/btagent",)))

    def reiniciar(self) -> None:
        """O ``bluetoothd`` reinicia: o ``org.bluez`` troca de nome único, e o
        novo não conhece agente nenhum. O ``bt-agent`` de mentira volta a se
        registrar e a pedir o padrão, como o serviço do sistema."""
        self._fios.remove(self.bluez)
        self.bluez.fechar()
        self.agentes.clear()
        self.padroes.clear()
        self.dono_da_busca = ""
        self._subir_o_bluez("bluez-de-mentira-de-novo")
        self._registrar_o_bt_agent()

    @property
    def nome_do_bluez(self) -> str:
        return str(self.bluez.conexao.get_unique_name())

    def __exit__(self, *_: object) -> None:
        for fio in reversed(self._fios):
            fio.fechar()
        if self._processo is not None:
            self._processo.terminate()
            try:
                self._processo.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._processo.kill()
                self._processo.wait(timeout=5)

    @property
    def nome_do_bt_agent(self) -> str:
        return str(self.bt_agent.conexao.get_unique_name())

    def outro_cliente(self) -> _Fio:
        """Um cliente sem agente nenhum — o watchdog chamando ``Pair`` por conta própria."""
        fio = _Fio(self.endereco, "outro-cliente")
        self._fios.append(fio)
        return fio

    # -- o BlueZ de mentira ----------------------------------------------------

    def _foto(self) -> Any:
        variante = self.bluez.GLib.Variant
        return {
            caminho: {
                interface: {nome: variante(_tipo(nome, v), v) for nome, v in props.items()}
                for interface, props in interfaces.items()
            }
            for caminho, interfaces in self.mesa.items()
        }

    def _mudou(self, caminho: str, interface: str, nome: str, valor: Any) -> None:
        self.mesa[caminho][interface][nome] = valor
        variante = self.bluez.GLib.Variant
        self.bluez.conexao.emit_signal(
            None, caminho, bd.PROPRIEDADES, "PropertiesChanged",
            variante("(sa{sv}as)", (interface, {nome: variante(_tipo(nome, valor), valor)}, [])),
        )

    def _atender(
        self, _c: Any, remetente: str, caminho: str, interface: str, metodo: str,
        parametros: Any, invocacao: Any,
    ) -> None:
        argumentos = parametros.unpack()
        self.chamadas.append((remetente, caminho, interface, metodo))
        variante = self.bluez.GLib.Variant
        if metodo == "GetManagedObjects":
            invocacao.return_value(variante("(a{oa{sa{sv}}})", (self._foto(),)))
        elif metodo == "RegisterAgent":
            if remetente in self.agentes:
                invocacao.return_dbus_error(bd.ERRO_JA_EXISTE, "Already Exists")
                return
            self.agentes[remetente] = (argumentos[0], argumentos[1])
            invocacao.return_value(None)
        elif metodo == "UnregisterAgent":
            self.agentes.pop(remetente, None)
            self.padroes = [p for p in self.padroes if p != remetente]
            invocacao.return_value(None)
        elif metodo == "RequestDefaultAgent":
            self.padroes.insert(0, remetente)
            invocacao.return_value(None)
        elif metodo == "StartDiscovery":
            self.dono_da_busca = remetente
            self._mudou(caminho, bd.ADAPTADOR, "Discovering", True)
            invocacao.return_value(None)
        elif metodo == "StopDiscovery":
            if remetente != self.dono_da_busca:
                invocacao.return_dbus_error("org.bluez.Error.Failed", "No discovery started")
                return
            self.dono_da_busca = ""
            self._mudou(caminho, bd.ADAPTADOR, "Discovering", False)
            invocacao.return_value(None)
        elif metodo == "Pair":
            self._parear(remetente, caminho, invocacao)
        elif metodo == "Set":
            self._mudou(caminho, argumentos[0], argumentos[1], argumentos[2])
            invocacao.return_value(None)
        else:
            invocacao.return_value(None)

    def _parear(self, remetente: str, caminho: str, invocacao: Any) -> None:
        """``agent_get(sender)`` do 5.86: o agente do remetente, senão o padrão."""
        dono_do_agente = remetente if remetente in self.agentes else (
            self.padroes[0] if self.padroes else ""
        )
        if not dono_do_agente:
            invocacao.return_dbus_error("org.bluez.Error.AuthenticationFailed", "No agent")
            return
        caminho_do_agente = self.agentes[dono_do_agente][0]
        if dono_do_agente == self.nome_do_bt_agent:
            self.o_padrao_atendeu.append(caminho)
        try:
            self.bluez.chamar(
                dono_do_agente, caminho_do_agente, bd.AGENTE, "RequestConfirmation",
                self.bluez.GLib.Variant("(ou)", (caminho, 123456)),
            )
        except self.bluez.GLib.Error as problema:
            invocacao.return_dbus_error("org.bluez.Error.AuthenticationRejected", problema.message)
            return
        self._mudou(caminho, bd.APARELHO, "Paired", True)
        invocacao.return_value(None)

    def _atender_o_bt_agent(
        self, _c: Any, _r: str, _caminho: str, _i: str, _metodo: str, _p: Any, invocacao: Any
    ) -> None:
        # NoInputNoOutput: aceita tudo, como o `bt-agent` do bluez-tools.
        invocacao.return_value(None)


def esperar(condicao: Callable[[], bool], teto: float = 3.0) -> bool:
    """Espera um sinal chegar pelo barramento particular, sem dormir às cegas."""
    fim = time.monotonic() + teto
    while time.monotonic() < fim:
        if condicao():
            return True
        time.sleep(0.01)
    return condicao()
