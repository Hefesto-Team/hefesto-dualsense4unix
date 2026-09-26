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

A FÍSICA QUE A LISTA DELA DE 25/09 MEDIU (A-CONEXOES-O-QUE-A-LISTA-DELA-ACHOU-01),
e até ela este dublê era MAIS FROUXO que o controle de verdade:

* **ligado, o PS + Create não faz nada** (passo c1: *«o controle nunca entra em
  modo de parear»*). O controle só entra em modo de pareamento DESLIGADO — e
  este dublê o deixava pareando conectado, o que escondia o mover que nunca
  desligava o controle;
* **o host que solta o enlace tira o controle do ar** (``Disconnect``), e ela
  desliga na mão segurando o PS (:meth:`RadioDeMentira.desligar`). Se ele
  APAGA ou fica procurando o host ninguém mediu (``energia.desligar@dualsense``
  no mapa): para o dublê, os dois são «fora do ar»;
* **o controle volta sozinho ao pareamento antigo quando ele existe** (passo
  c2: *«muda de adaptador, fica um tempo, e volta para o anterior»*): ele
  lembra os hosts de antes (``Fisico.antigos``), e
  :meth:`RadioDeMentira.voltar_sozinho` o leva de volta ao primeiro que ainda
  tem a chave dele. Sem a chave lá, não há para onde voltar.
  <!-- noqa-acento: citação literal dela -->

O ``Alias`` nasce igual ao ``Name`` de fábrica, como no BlueZ; o nome que ela
dá é o ``Alias`` diferente dele.

E A FÍSICA DO KERNEL E DO DAEMON, que o conferente da mesma sprint mediu (este
dublê respondia só pelo DualSense, e era mais frouxo que o real):

* **todo aparelho HID pelo rádio tem hidraw**, e o ``HID_PHYS`` dele é o
  adaptador — o teclado e o mouse também, e o de baixo consumo (sem ``Class``)
  também. :meth:`RadioDeMentira.onde_esta` responde por todos eles;
* **o daemon só mede o movimento do DualSense** (Sony ``054C``, ``0CE6`` e
  ``0DF2``): de um teclado, de um DualShock 4 ou de um 8BitDo, o
  :meth:`RadioDeMentira.hz` responde ``None`` — «não sei», como o
  ``SensorHub``.

Os dois botões de defeito que a régua aperta:

* ``pair_falha`` — o ``Pair`` responde erro;
* ``pair_mente`` — o ``Pair`` responde que deu, e o controle NÃO muda de host:
  é o «aplicar que falha» da sprint, que só o CONFERIR pega.

Faixa sintética da casa: ``aa:bb:cc``, octetos 4 e 5 zerados.
"""

from __future__ import annotations

import copy
import re
import threading
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
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

#: *Class of device* de um gamepad (periférico, menor 0x02), de um fone e de
#: um teclado (periférico, menor 0x10).
CLASSE_DE_CONTROLE = 0x002508
CLASSE_DE_FONE = 0x240404
CLASSE_DE_TECLADO = 0x002540

#: O ``Name`` de fábrica — o ``Alias`` nasce igual a ele.
NOME_DE_FABRICA: dict[int | None, str] = {CLASSE_DE_CONTROLE: "DualSense Wireless Controller",
                   CLASSE_DE_FONE: "Fone de mentira", CLASSE_DE_TECLADO: "BT5.0 Keyboard"}
#: O ``Modalias`` do DualSense (Sony 054C, produto 0CE6), como o BlueZ publica.
MODALIAS_DO_DUALSENSE = "bluetooth:v054Cp0CE6d0100"


def no_de(adaptador: str, aparelho: str) -> str:
    return f"{HCIS[adaptador]}/dev_{aparelho.upper().replace(':', '_')}"


def uniq(aparelho: str) -> str:
    return aparelho.replace(":", "")


@dataclass
class Fisico:
    """O aparelho na mão dela: o host que ELE guarda, e onde está conectado."""

    endereco: str
    #: ``None`` é o aparelho de baixo consumo, que não publica ``Class``.
    classe: int | None
    host: str = ""
    conectado_em: str = ""
    pareando: bool = False
    hz: float = 250.0
    #: Os hosts de ANTES do de agora, o mais recente primeiro — o pareamento
    #: antigo a que ele volta sozinho quando a chave ainda existe lá.
    antigos: list[str] = field(default_factory=list)
    #: O ``Modalias`` que o BlueZ publica; ``None`` = o da classe (o DualSense
    #: no controle, nada no resto).
    modalias: str | None = None
    #: O ``Icon`` que o BlueZ deriva — o único tipo do aparelho sem ``Class``.
    icone: str = ""
    #: Tem hidraw no rádio? ``None`` = pela classe (periférico, maior ``0x05``);
    #: o aparelho de baixo consumo, que não tem classe, diz aqui.
    hid: bool | None = None

    @property
    def modalias_publicado(self) -> str:
        if self.modalias is not None:
            return self.modalias
        return MODALIAS_DO_DUALSENSE if self.classe == CLASSE_DE_CONTROLE else ""

    @property
    def tem_hidraw(self) -> bool:
        if self.hid is not None:
            return self.hid
        return self.classe is not None and (self.classe >> 8) & 0x1F == 0x05

    @property
    def o_daemon_mede(self) -> bool:
        return re.search(r"v054Cp(0CE6|0DF2)", self.modalias_publicado, re.I) is not None


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
        #: ``(caminho, interface, método, argumentos)`` de toda chamada.
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
        #: Os PS + Create que ela segurou com o controle LIGADO — e não deram em nada.
        self.gestos_perdidos: list[str] = []
        self._ao_sinal: Callable[[bd.Sinal], None] | None = None

    # -- montar a mesa --------------------------------------------------------

    def pareado(
        self,
        adaptador: str,
        aparelho: str,
        *,
        classe: int | None = CLASSE_DE_CONTROLE,
        conectado: bool = True,
        host: bool = True,
        nome: str = "",
        modalias: str | None = None,
        icone: str = "",
        hid: bool | None = None,
    ) -> None:
        """Um bond que já existe. ``host`` diz se o CONTROLE guarda este adaptador.

        ``nome`` é o ``Alias`` que ela deu; sem ele, o de fábrica. ``classe``
        ``None`` é o aparelho de baixo consumo, que o BlueZ conhece pelo
        ``icone``."""
        fisico = self.fisicos.setdefault(
            aparelho, Fisico(aparelho, classe, modalias=modalias, icone=icone, hid=hid))
        if host:
            fisico.host = adaptador
            if conectado:
                fisico.conectado_em = adaptador
        fabrica = NOME_DE_FABRICA.get(classe, "aparelho de mentira")
        self.mesa[no_de(adaptador, aparelho)] = {
            bd.APARELHO: {
                "Address": aparelho.upper(),
                "Name": fabrica,
                "Alias": nome or fabrica,
                "Modalias": fisico.modalias_publicado,
                "Icon": fisico.icone,
                "Paired": True,
                "Bonded": True,
                "Trusted": True,
                "Connected": bool(host and conectado),
                "Class": classe,
            }
        }

    # -- a física, pela mão dela ----------------------------------------------

    def segurar_ps_create(self, aparelho: str) -> None:
        """Ela segura PS + Create: DESLIGADO, o controle anuncia que pareia.

        LIGADO, NADA ACONTECE — a lista dela de 25/09, passo c1: o DualSense
        conectado não entra em modo de parear. O gesto fica anotado em
        ``gestos_perdidos`` para a régua ver que ela apertou e nada veio.
        """
        with self.tranca:
            fisico = self.fisicos[aparelho]
            if fisico.conectado_em:
                self.gestos_perdidos.append(aparelho)
                return
            fisico.pareando = True
            for endereco, caminho in HCIS.items():
                adaptador = self.mesa.get(caminho, {}).get(bd.ADAPTADOR)
                if adaptador and adaptador.get("Discovering"):
                    self._achar(endereco, fisico)

    def desligar(self, aparelho: str) -> None:
        """Ela segura o PS até a luz apagar: o controle desliga, e o host fica."""
        with self.tranca:
            fisico = self.fisicos[aparelho]
            antes, fisico.conectado_em, fisico.pareando = fisico.conectado_em, "", False
            if antes and no_de(antes, aparelho) in self.mesa:
                self._mudar(no_de(antes, aparelho), bd.APARELHO, "Connected", False)

    def voltar_sozinho(self, aparelho: str) -> str:
        """O controle volta sozinho ao pareamento ANTIGO quando ele existe.

        É o passo c2 da lista dela: ele muda, fica um tempo, e volta para o
        anterior. Devolve o adaptador a que voltou, ou ``""`` quando nenhum dos
        hosts antigos ainda tem a chave dele — aí ele fica onde está.
        """
        with self.tranca:
            fisico = self.fisicos[aparelho]
            for antigo in fisico.antigos:
                objeto = self.mesa.get(no_de(antigo, aparelho), {}).get(bd.APARELHO)
                if not objeto or not objeto.get("Paired"):
                    continue
                if fisico.conectado_em and no_de(fisico.conectado_em, aparelho) in self.mesa:
                    self._mudar(no_de(fisico.conectado_em, aparelho), bd.APARELHO,
                                "Connected", False)
                fisico.antigos.remove(antigo)
                if fisico.host:
                    fisico.antigos.insert(0, fisico.host)
                fisico.host = fisico.conectado_em = antigo
                fisico.pareando = False
                self._mudar(no_de(antigo, aparelho), bd.APARELHO, "Connected", True)
                return antigo
        return ""

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
        """O ``HID_PHYS``: o adaptador em que o aparelho HID está conectado agora.

        TODO aparelho HID — o kernel dá hidraw ao teclado e ao mouse pelo rádio
        também, com o ``HID_PHYS`` no adaptador. O fone não é HID."""
        with self.tranca:
            for fisico in self.fisicos.values():
                if uniq(fisico.endereco) == u and fisico.tem_hidraw:
                    return fisico.conectado_em
        return ""

    def hz(self, u: str) -> float | None:
        """O movimento que o daemon mede — só do DualSense; do resto, ``None``."""
        with self.tranca:
            for fisico in self.fisicos.values():
                if uniq(fisico.endereco) == u:
                    if not fisico.o_daemon_mede:
                        return None
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
        fabrica = NOME_DE_FABRICA.get(fisico.classe, "aparelho de mentira")
        propriedades = {
            bd.APARELHO: {
                "Address": fisico.endereco.upper(),
                "Name": fabrica,
                "Alias": fabrica,
                # o Modalias chega com o pareamento (o registro PnP do SDP), e o
                # aparelho achado na busca ainda não o tem
                "Modalias": "",
                "Icon": fisico.icone,
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
            if fisico.modalias_publicado:
                self._mudar(caminho, bd.APARELHO, "Modalias", fisico.modalias_publicado)
            if self.pair_mente:
                return bd.Escrita(True, resposta=())
            fisico.pareando = False
            if fisico.host and fisico.host != adaptador:
                if fisico.host in fisico.antigos:
                    fisico.antigos.remove(fisico.host)
                fisico.antigos.insert(0, fisico.host)
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
            # O HOST QUE SOLTA O ENLACE TIRA O CONTROLE DO AR (o kernel tira o nó).
            self.linha_do_tempo.append(("Disconnect", adaptador, aparelho))
            if fisico is not None and fisico.conectado_em == adaptador:
                fisico.conectado_em = ""
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
