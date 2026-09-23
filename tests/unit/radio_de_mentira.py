"""Um rádio de mentira com FÍSICA, para as réguas da central — MOVER-UM-POR-VEZ-01.

**Este módulo não é um arquivo de teste** — é a bancada que
``test_mover_um_por_vez.py`` e ``test_a_central_confere_o_que_aplicou.py``
usam, como o ``bluez_de_mentira.py`` é a do dono.

O QUE ELE TEM QUE O ``bluez_de_mentira`` NÃO TEM
================================================
Vários adaptadores e um CONTROLE que obedece à física medida em 23/09:

* o controle guarda UM host. Segurar PS + Create o solta do host de agora e o
  põe em modo de pareamento; só um adaptador que está BUSCANDO o acha;
* o ``Pair`` só dá com o aparelho em modo de pareamento, e com o agente certo —
  o do remetente, senão o padrão (``agent_get(sender)`` do 5.86); objeto que
  não existe é ``UnknownObject``, bond que já existe é ``AlreadyExists``;
* o ``Connect`` só dá no adaptador que o controle guarda como host;
* o ``RemoveDevice`` de objeto que não existe é ``DoesNotExist``;
* o ``StartDiscovery`` exige o adaptador ligado (``NotReady``), e o
  ``StopDiscovery`` recolhe o que a busca achou e ninguém pareou.

Tudo que muda sai como SINAL (``entrou``/``saiu``/``mudou``), que é a única
coisa que o ``DonoVivo`` de verdade lê. A régua usa o ``DonoVivo`` real por
cima disto — a borda, a trava, o diário e o agente próprio são os do produto.

O ``HID_PHYS`` é :meth:`RadioDeMentira.onde_esta`: o adaptador em que o
controle está CONECTADO agora; o movimento é :meth:`RadioDeMentira.hz`.

Os dois botões de defeito que a régua aperta:

* ``pair_falha`` — o ``Pair`` responde erro;
* ``pair_mente`` — o ``Pair`` responde que deu, e o controle NÃO muda de host:
  é o «aplicar que falha» da sprint, que só o CONFERIR pega.

Faixa sintética da casa: ``aa:bb:cc``, octetos 4 e 5 zerados.
"""

from __future__ import annotations

import copy
import threading
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any

from hefesto_dualsense4unix.integrations import bluez_dbus as bd

#: Três adaptadores. O ``hci`` é sorteio de enumeração, como na vida.
SALA = "aa:bb:cc:00:00:a1"
QUARTO = "aa:bb:cc:00:00:b2"
VARANDA = "aa:bb:cc:00:00:c3"
HCIS = {SALA: "/org/bluez/hci7", QUARTO: "/org/bluez/hci8", VARANDA: "/org/bluez/hci9"}

VERMELHO = "aa:bb:cc:00:00:01"
AZUL = "aa:bb:cc:00:00:02"
VERDE = "aa:bb:cc:00:00:03"
ROXO = "aa:bb:cc:00:00:04"
FONE = "aa:bb:cc:00:00:f0"

#: *Class of device* de um gamepad (periférico, menor 0x02) e de um fone.
CLASSE_DE_CONTROLE = 0x002508
CLASSE_DE_FONE = 0x240404


def no_de(adaptador: str, aparelho: str) -> str:
    return f"{HCIS[adaptador]}/dev_{aparelho.upper().replace(':', '_')}"


def uniq(aparelho: str) -> str:
    return aparelho.replace(":", "")


@dataclass
class Fisico:
    """O aparelho na mão dela: o host que ELE guarda, e onde está conectado."""

    endereco: str
    classe: int
    host: str = ""
    conectado_em: str = ""
    pareando: bool = False
    hz: float = 250.0


class RadioDeMentira:
    """A costura ``bluez_dbus.Barramento``, com a física de cima."""

    NOME = ":1.42"
    DONO_DO_BLUEZ = ":1.7"

    def __init__(self, *, adaptadores: Sequence[str] = (SALA, QUARTO, VARANDA)) -> None:
        self.e_do_sistema = False
        self.tranca = threading.RLock()
        self.mesa: dict[str, dict[str, dict[str, Any]]] = {
            "/org/bluez": {bd.GERENTE_DE_AGENTES: {}}
        }
        for endereco in adaptadores:
            self.mesa[HCIS[endereco]] = {
                bd.ADAPTADOR: {
                    "Address": endereco.upper(),
                    "Alias": f"adaptador {endereco[-2:]}",
                    "Powered": True,
                    "Pairable": False,
                    "Discovering": False,
                }
            }
        self.fisicos: dict[str, Fisico] = {}
        self.bluez_de_pe = True
        self.fechado = False
        self.pair_falha = False
        self.pair_mente = False
        self.exportar_da = True
        #: ``(caminho, interface, metodo, argumentos)`` de toda chamada.
        self.chamadas: list[tuple[str, str, str, tuple[Any, ...]]] = []
        #: ``(caminho, interface, nome, valor)`` de toda escrita de propriedade.
        self.escritas: list[tuple[str, str, str, Any]] = []
        self.exportados: dict[str, Callable[[str, str, tuple[Any, ...]], Any]] = {}
        self.agentes: dict[str, str] = {}
        self.o_padrao_atendeu: list[str] = []
        self.o_nosso_atendeu: list[str] = []
        #: As lápides que a ponte de mentira escreveu: ``(adaptador, aparelho)``.
        self.lapides: list[tuple[str, str]] = []
        #: Tudo em ordem, para a régua da ORDEM: ``("Pair", adaptador, aparelho)``…
        self.linha_do_tempo: list[tuple[str, str, str]] = []
        self._ao_sinal: Callable[[bd.Sinal], None] | None = None

    # -- montar a mesa --------------------------------------------------------

    def pareado(
        self,
        adaptador: str,
        aparelho: str,
        *,
        classe: int = CLASSE_DE_CONTROLE,
        conectado: bool = True,
        host: bool = True,
    ) -> None:
        """Um bond que já existe. ``host`` diz se o CONTROLE guarda este adaptador."""
        fisico = self.fisicos.setdefault(aparelho, Fisico(aparelho, classe))
        if host:
            fisico.host = adaptador
            if conectado:
                fisico.conectado_em = adaptador
        self.mesa[no_de(adaptador, aparelho)] = {
            bd.APARELHO: {
                "Address": aparelho.upper(),
                "Alias": "controle de mentira",
                "Paired": True,
                "Bonded": True,
                "Trusted": True,
                "Connected": bool(host and conectado),
                "Class": classe,
            }
        }

    # -- a física, pela mão dela ----------------------------------------------

    def segurar_ps_create(self, aparelho: str) -> None:
        """Ela segura PS + Create: o controle solta o host e anuncia que pareia."""
        with self.tranca:
            fisico = self.fisicos[aparelho]
            antes = fisico.conectado_em
            fisico.conectado_em = ""
            fisico.pareando = True
            if antes:
                self._mudar(no_de(antes, aparelho), bd.APARELHO, "Connected", False)
            for endereco, caminho in HCIS.items():
                adaptador = self.mesa.get(caminho, {}).get(bd.ADAPTADOR)
                if adaptador and adaptador.get("Discovering"):
                    self._achar(endereco, fisico)

    def apertar_ps(self, aparelho: str) -> None:
        """Ela aperta PS: o controle volta para o host que ELE guarda."""
        with self.tranca:
            fisico = self.fisicos[aparelho]
            fisico.pareando = False
            caminho = no_de(fisico.host, aparelho) if fisico.host else ""
            if caminho in self.mesa:
                fisico.conectado_em = fisico.host
                self._mudar(caminho, bd.APARELHO, "Connected", True)

    def onde_esta(self, u: str) -> str:
        """O ``HID_PHYS``: o adaptador em que o controle está conectado agora."""
        with self.tranca:
            for fisico in self.fisicos.values():
                if uniq(fisico.endereco) == u and fisico.classe == CLASSE_DE_CONTROLE:
                    return fisico.conectado_em
        return ""

    def hz(self, u: str) -> float | None:
        with self.tranca:
            for fisico in self.fisicos.values():
                if uniq(fisico.endereco) == u:
                    return fisico.hz if fisico.conectado_em else 0.0
        return None

    def esquecer_na_ponte(self, adaptador: str, aparelho: str) -> tuple[bool, str]:
        """O verbo ``esquecer`` da ponte: tira o objeto (como root) e enterra."""
        with self.tranca:
            self.lapides.append((adaptador, aparelho))
            self.linha_do_tempo.append(("esquecer", adaptador, aparelho))
            caminho = no_de(adaptador, aparelho)
            if caminho in self.mesa:
                self._remover(caminho)
        return True, ""

    # -- a costura Barramento -------------------------------------------------

    def vivo(self) -> bool:
        return not self.fechado

    def nome_unico(self) -> str:
        return self.NOME

    def dono_do_nome(self, nome: str) -> str:
        return self.DONO_DO_BLUEZ if self.bluez_de_pe else ""

    def objetos(self, *, espera: float) -> dict[str, dict[str, dict[str, Any]]] | None:
        with self.tranca:
            return copy.deepcopy(self.mesa) if self.bluez_de_pe else None

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
        with self.tranca:
            self.chamadas.append((caminho, interface, metodo, tuple(argumentos)))
            if interface == bd.GERENTE_DE_AGENTES:
                return self._agentes(metodo, argumentos)
            if caminho not in self.mesa:
                return bd.Escrita(False, "org.freedesktop.DBus.Error.UnknownObject")
            if interface == bd.ADAPTADOR:
                return self._no_adaptador(caminho, metodo, argumentos)
            if interface == bd.APARELHO:
                return self._no_aparelho(caminho, metodo)
            return bd.Escrita(False, "org.freedesktop.DBus.Error.UnknownMethod")

    def escrever(
        self, caminho: str, interface: str, nome: str, assinatura: str, valor: Any, *, espera: float
    ) -> bd.Escrita:
        with self.tranca:
            self.escritas.append((caminho, interface, nome, valor))
            if caminho not in self.mesa:
                return bd.Escrita(False, "org.freedesktop.DBus.Error.UnknownObject")
            self._mudar(caminho, interface, nome, valor)
            return bd.Escrita(True)

    def exportar(
        self, caminho: str, xml: str, tratador: Callable[[str, str, tuple[Any, ...]], Any]
    ) -> bool:
        if not self.exportar_da:
            return False
        self.exportados[caminho] = tratador
        return True

    def retirar(self, caminho: str) -> None:
        self.exportados.pop(caminho, None)

    def fechar(self) -> None:
        self.fechado = True

    # -- o que a régua lê ------------------------------------------------------

    def metodos(self, metodo: str) -> list[tuple[str, tuple[Any, ...]]]:
        return [(c, a) for c, _i, m, a in self.chamadas if m == metodo]

    def objeto(self, adaptador: str, aparelho: str) -> dict[str, Any] | None:
        return self.mesa.get(no_de(adaptador, aparelho), {}).get(bd.APARELHO)

    def propriedade_do_adaptador(self, adaptador: str, nome: str) -> Any:
        return self.mesa[HCIS[adaptador]][bd.ADAPTADOR].get(nome)

    def escritas_no(self, adaptador: str, nome: str) -> list[Any]:
        return [v for c, _i, n, v in self.escritas if c == HCIS[adaptador] and n == nome]

    # -- por dentro -----------------------------------------------------------

    def _emitir(self, sinal: bd.Sinal) -> None:
        if self._ao_sinal is not None:
            self._ao_sinal(sinal)

    def _mudar(self, caminho: str, interface: str, nome: str, valor: Any) -> None:
        self.mesa.setdefault(caminho, {}).setdefault(interface, {})[nome] = valor
        self._emitir(bd.Sinal("mudou", caminho=caminho, interface=interface, mudadas={nome: valor}))

    def _remover(self, caminho: str) -> None:
        interfaces = tuple(self.mesa.pop(caminho, {}))
        self._emitir(bd.Sinal("saiu", caminho=caminho, interfaces_que_sairam=interfaces))

    def _achar(self, adaptador: str, fisico: Fisico) -> None:
        caminho = no_de(adaptador, fisico.endereco)
        if caminho in self.mesa:
            return
        propriedades = {
            bd.APARELHO: {
                "Address": fisico.endereco.upper(),
                "Alias": "achado na busca",
                "Paired": False,
                "Bonded": False,
                "Trusted": False,
                "Connected": False,
                "Class": fisico.classe,
            }
        }
        self.mesa[caminho] = copy.deepcopy(propriedades)
        self._emitir(bd.Sinal("entrou", caminho=caminho, propriedades=propriedades))

    def _endereco_do_hci(self, caminho: str) -> str:
        return next(e for e, c in HCIS.items() if c == caminho)

    def _agentes(self, metodo: str, argumentos: Sequence[Any]) -> bd.Escrita:
        if metodo == "RegisterAgent":
            if self.NOME in self.agentes:
                return bd.Escrita(False, bd.ERRO_JA_EXISTE)
            self.agentes[self.NOME] = str(argumentos[0])
        elif metodo == "UnregisterAgent":
            self.agentes.pop(self.NOME, None)
        return bd.Escrita(True, resposta=())

    def _no_adaptador(self, caminho: str, metodo: str, argumentos: Sequence[Any]) -> bd.Escrita:
        endereco = self._endereco_do_hci(caminho)
        propriedades = self.mesa[caminho][bd.ADAPTADOR]
        if metodo == "StartDiscovery":
            if not propriedades.get("Powered"):
                return bd.Escrita(False, "org.bluez.Error.NotReady")
            self.linha_do_tempo.append(("StartDiscovery", endereco, ""))
            self._mudar(caminho, bd.ADAPTADOR, "Discovering", True)
            for fisico in self.fisicos.values():
                if fisico.pareando:
                    self._achar(endereco, fisico)
            return bd.Escrita(True, resposta=())
        if metodo == "StopDiscovery":
            if not propriedades.get("Discovering"):
                return bd.Escrita(False, "org.bluez.Error.Failed")
            self.linha_do_tempo.append(("StopDiscovery", endereco, ""))
            self._mudar(caminho, bd.ADAPTADOR, "Discovering", False)
            for no in [n for n in self.mesa if n.startswith(caminho + "/")]:
                if not self.mesa[no][bd.APARELHO].get("Paired"):
                    self._remover(no)
            return bd.Escrita(True, resposta=())
        if metodo == "RemoveDevice":
            alvo = str(argumentos[0])
            if alvo not in self.mesa:
                return bd.Escrita(False, "org.bluez.Error.DoesNotExist")
            aparelho = bd.endereco_do_aparelho(alvo) or ""
            self.linha_do_tempo.append(("RemoveDevice", endereco, aparelho))
            fisico = self.fisicos.get(aparelho)
            if fisico is not None and fisico.conectado_em == endereco:
                fisico.conectado_em = ""
            self._remover(alvo)
            return bd.Escrita(True, resposta=())
        return bd.Escrita(False, "org.freedesktop.DBus.Error.UnknownMethod")

    def _no_aparelho(self, caminho: str, metodo: str) -> bd.Escrita:
        adaptador = self._endereco_do_hci(caminho.rsplit("/", 1)[0])
        aparelho = bd.endereco_do_aparelho(caminho) or ""
        fisico = self.fisicos.get(aparelho)
        propriedades = self.mesa[caminho][bd.APARELHO]
        if metodo == "Pair":
            self.linha_do_tempo.append(("Pair", adaptador, aparelho))
            if propriedades.get("Paired"):
                return bd.Escrita(False, bd.ERRO_JA_EXISTE)
            if self.pair_falha or fisico is None or not fisico.pareando:
                return bd.Escrita(False, "org.bluez.Error.AuthenticationFailed")
            recusa = self._perguntar_ao_agente(caminho)
            if recusa is not None:
                return recusa
            self._mudar(caminho, bd.APARELHO, "Paired", True)
            self._mudar(caminho, bd.APARELHO, "Bonded", True)
            if self.pair_mente:
                return bd.Escrita(True, resposta=())
            fisico.pareando = False
            fisico.host = adaptador
            fisico.conectado_em = adaptador
            self._mudar(caminho, bd.APARELHO, "Connected", True)
            return bd.Escrita(True, resposta=())
        if metodo == "Connect":
            self.linha_do_tempo.append(("Connect", adaptador, aparelho))
            if fisico is None or fisico.host != adaptador or not propriedades.get("Paired"):
                return bd.Escrita(False, "org.bluez.Error.Failed")
            fisico.conectado_em = adaptador
            self._mudar(caminho, bd.APARELHO, "Connected", True)
            return bd.Escrita(True, resposta=())
        if metodo == "Disconnect":
            self._mudar(caminho, bd.APARELHO, "Connected", False)
            return bd.Escrita(True, resposta=())
        return bd.Escrita(False, "org.freedesktop.DBus.Error.UnknownMethod")

    def _perguntar_ao_agente(self, caminho: str) -> bd.Escrita | None:
        """``agent_get(sender)``: o agente do remetente, senão o padrão (o piso)."""
        agente = self.agentes.get(self.NOME)
        if agente is None:
            self.o_padrao_atendeu.append(caminho)
            return None
        tratador = self.exportados.get(agente)
        if tratador is None:
            return bd.Escrita(False, "org.bluez.Error.AuthenticationFailed")
        try:
            tratador(self.DONO_DO_BLUEZ, "RequestConfirmation", (caminho, 123456))
        except bd.RecusaNoBarramento as recusa:
            return bd.Escrita(False, recusa.nome, recusa.mensagem)
        self.o_nosso_atendeu.append(caminho)
        return None


class Relogio:
    """O relógio da central: ``dormir`` anda o tempo e roda o que ela agendou."""

    def __init__(self) -> None:
        self.agora = 1000.0
        self._agenda: list[tuple[float, Callable[[], None]]] = []
        self.durante: Callable[[], None] | None = None

    def __call__(self) -> float:
        return self.agora

    def agendar(self, depois_de: float, tarefa: Callable[[], None]) -> None:
        self._agenda.append((self.agora + depois_de, tarefa))

    def dormir(self, segundos: float) -> None:
        self.agora += segundos
        if self.durante is not None:
            self.durante()
        vencidas = [t for t in self._agenda if t[0] <= self.agora]
        self._agenda = [t for t in self._agenda if t[0] > self.agora]
        for _quando, tarefa in vencidas:
            tarefa()
