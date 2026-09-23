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
  ``Pair``, ``Trusted`` e ``StartDiscovery``/``StopDiscovery`` do NOSSO
  cliente — toda escrita DENTRO da trava comum do rádio
  (``diario_do_radio.trava_do_radio``), e as que mudam o rádio com uma linha no
  diário comum;
* **RECUSA NA BORDA** toda escrita no BlueZ de verdade enquanto a suíte roda, e
  sob a suíte nem LÊ o barramento dela: só um ``busctl`` de mentira responde;
* o ENDEREÇO do adaptador vem do kernel (``ar_do_adaptador.LeitorDoKernel``, o
  ``HCIGETDEVINFO``), não do texto de ninguém; o LUGAR dele (D3) é o caminho PCI
  mais as portas do USB.

AUSÊNCIA É RESPOSTA. ``None`` quer dizer "não deu para perguntar", nunca "não
há". Quem lê decide o que dizer; este módulo não inventa o vazio.

AS DUAS EXCEÇÕES DA TRAVA, e as duas são de propósito:

* o ``StopDiscovery`` não espera ninguém — ele SOLTA o rádio (a busca custa de
  32% a 43% do adaptador), e esperar a trava por ele seria deixar a busca de pé
  enquanto o watchdog segura um tique inteiro;
* o agente próprio (``agente_de_pareamento``) nunca a pede: o ``Pair`` de quem
  pareia já a segura enquanto o BlueZ chama o agente, e pedir de novo seria uma
  espera de 10 a 30 s em cada pareamento.

DONOS EXTERNOS, declarados e não absorvidos: os scripts root
(``bt_ponte_privilegiada.sh``, ``bt_active_mode.sh``, ``bt_health_watchdog.sh``)
e o ``hefesto-bt-agent``. São shell e root; o que o D-Bus não alcança como uid
1000 continua com eles, e a trava é de quem os chama.
"""

from __future__ import annotations

import atexit
import contextlib
import fcntl
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
from collections.abc import Callable, Iterator, Mapping, Sequence
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

#: Os motivos de uma escrita que não chegou ao BlueZ. Não são erros D-Bus: são
#: o dono dizendo por que nem tentou.
RECUSA_DA_SUITE = "hefesto.RecusaDaSuite"
SEM_BARRAMENTO = "hefesto.SemBarramento"
SEM_AGENTE = "hefesto.SemAgente"
TRAVA_OCUPADA = "hefesto.TravaOcupada"

#: Como a borda assina no diário e na trava quando quem escreve não se nomeou.
QUEM_PADRAO = "hefesto"

#: O ``o_que`` da linha que a borda deixa no diário comum a cada escrita que
#: MUDA o rádio. Um só texto para todo motor, com a ``chamada`` ao lado: o leitor
#: (o sino) procura por esta constante, e um sinônimo seria linha que ninguém acha.
ESCREVEU_NO_BLUEZ = "escreveu no BlueZ"

#: Os métodos que mudam o rádio — e só eles vão ao diário. ``Alias`` e
#: ``Trusted`` são propriedade, não ar: entram na trava e ficam fora do sino.
_METODOS_DO_DIARIO = frozenset(
    {"Connect", "Disconnect", "Pair", "RemoveDevice", "StartDiscovery", "StopDiscovery"}
)

#: As escritas que NÃO esperam a trava. Ver o cabeçalho; a régua cobra que a
#: lista seja exatamente esta.
METODOS_SEM_TRAVA = frozenset({"StopDiscovery"})

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

#: Depois de uma foto que NÃO veio com o ``bluetoothd`` de pé (o
#: ``GetManagedObjects`` estourou os :data:`ESPERA_DA_FOTO_S`, ou o BlueZ
#: respondeu erro), quanto tempo o dono espera para tirar outra. Sem isto o dono
#: ficava cego até o ``bluetoothd`` reiniciar: o único gatilho de foto nova era o
#: ``NameOwnerChanged``, e um BlueZ lento que se recupera sozinho não o emite.
REFOTOGRAFAR_S = 5.0

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
    """A suíte está no ar? Então nada daqui escreve no BlueZ dela, nem o lê.

    É o sinal que ``gesto_de_reconexao`` usava sozinho desde 22/09/2026, quando
    a primeira corrida de 457 testes chamou ``Disconnect`` e ``Connect`` nos
    quatro DualSense da mesa dela, ao vivo. Agora ele guarda a BORDA: toda
    escrita passa por :meth:`LeitorDoBluez.chamar` ou
    :meth:`LeitorDoBluez.escrever_propriedade`, e as duas perguntam aqui.
    """
    if os.environ.get(RADIO_DE_VERDADE_NA_SUITE) == "1":
        return False
    return bool(os.environ.get("PYTEST_CURRENT_TEST")) or "pytest" in sys.modules


# ---------------------------------------------------------------------------
# O diário do processo e o endereço — sem terceiro no import: o doctor chega
# aqui pelo ``exame_da_mesa``.
# ---------------------------------------------------------------------------


def _registrar(evento: str, *, nivel: str = "info", **campos: Any) -> None:
    """Uma linha no log do processo. Nunca levanta."""
    try:
        from hefesto_dualsense4unix.utils.logging_config import get_logger

        getattr(get_logger(__name__), nivel)(evento, **campos)
    except Exception:
        return


def _mac(valor: object) -> str | None:
    """Endereço limpo, minúsculo e com dois-pontos — ou ``None``."""
    from hefesto_dualsense4unix.integrations.conexao_zumbi import mac_limpo

    return mac_limpo(valor if isinstance(valor, str) else None)


def endereco_do_aparelho(caminho: str) -> str | None:
    """O endereço de um aparelho pelo caminho: ``…/dev_AA_BB_…`` → ``aa:bb:…``."""
    forma = _CAMINHO_DE_APARELHO.match(caminho)
    return _mac(forma.group(2).replace("_", ":")) if forma else None


def _hci_de(caminho: str) -> str:
    achado = _CAMINHO_DE_ADAPTADOR.match(caminho)
    return achado.group(1) if achado else ""


# ---------------------------------------------------------------------------
# O resultado de uma escrita.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Escrita:
    """O que aconteceu com UMA escrita no BlueZ. Imutável, nunca uma exceção.

    ``erro`` é o nome D-Bus do erro quando o BlueZ respondeu que não
    (``org.bluez.Error.Failed``), ou um dos motivos do dono
    (:data:`RECUSA_DA_SUITE`, :data:`SEM_BARRAMENTO`, :data:`SEM_AGENTE`,
    :data:`TRAVA_OCUPADA`) quando nem se tentou.
    """

    feita: bool
    erro: str = ""
    mensagem: str = ""
    resposta: Any = None

    @property
    def nem_tentou(self) -> bool:
        """O dono recusou antes de falar com o BlueZ — não houve tentativa."""
        return self.erro in (RECUSA_DA_SUITE, SEM_BARRAMENTO, SEM_AGENTE, TRAVA_OCUPADA)


class RecusaNoBarramento(Exception):  # noqa: N818 — nome de domínio, não de erro
    """Levantada por quem atende um objeto exportado: vira erro D-Bus na resposta."""

    def __init__(self, nome: str, mensagem: str = "") -> None:
        super().__init__(mensagem or nome)
        self.nome = nome
        self.mensagem = mensagem or nome


# ---------------------------------------------------------------------------
# A trava — reentrante por fio, porque o motor que segura um gesto inteiro
# (Disconnect + Connect) passa pela borda de novo a cada escrita.
# ---------------------------------------------------------------------------

_POR_FIO = threading.local()


@contextlib.contextmanager
def na_trava(quem: str = QUEM_PADRAO, *, prazo_s: float | None = None) -> Iterator[float]:
    """Segura a trava comum do rádio enquanto o bloco roda. Entrega quanto esperou.

    Reentrante NO MESMO FIO: um ``flock`` pedido de novo pelo mesmo processo
    num descritor novo esperaria por ele mesmo até o prazo. Quem já está dentro
    passa direto.

    Levanta ``diario_do_radio.TravaOcupadaError`` quando o prazo acaba — a borda
    a traduz em :data:`TRAVA_OCUPADA`; um motor que segura o gesto inteiro a
    traduz na frase dele. Sem conseguir nem ABRIR a trava (``OSError``), segue
    sem ela e diz no log: é o precedente do vigia de zumbis
    (``daemon/subsystems/conexoes.py``), e um gesto dela não pode morrer porque
    o install ainda não criou a pasta.
    """
    if getattr(_POR_FIO, "dentro", 0):
        _POR_FIO.dentro += 1
        try:
            yield 0.0
        finally:
            _POR_FIO.dentro -= 1
        return
    from hefesto_dualsense4unix.integrations import diario_do_radio

    prazo = diario_do_radio.PRAZO_DA_TRAVA_S if prazo_s is None else prazo_s
    with contextlib.ExitStack() as pilha:
        try:
            espera = pilha.enter_context(diario_do_radio.trava_do_radio(quem, prazo_s=prazo))
        except OSError as problema:
            _registrar("bluez_escrita_sem_trava", nivel="warning", motivo=str(problema)[:200])
            espera = 0.0
        _POR_FIO.dentro = 1
        try:
            yield espera
        finally:
            _POR_FIO.dentro = 0


def _no_diario(quem: str, metodo: str, caminho: str, escrita: Escrita) -> None:
    """A linha da borda no diário comum. Nunca levanta: a escrita já aconteceu."""
    if metodo not in _METODOS_DO_DIARIO:
        return
    try:
        from hefesto_dualsense4unix.integrations import diario_do_radio

        diario_do_radio.registrar(
            quem,
            ESCREVEU_NO_BLUEZ,
            metodo,
            depois={"feita": escrita.feita, "erro": escrita.erro or None},
            chamada=metodo,
            hci=_hci_de(caminho) or _hci_de(caminho.rsplit("/dev_", 1)[0]) or None,
            controle=endereco_do_aparelho(caminho),
        )
    except Exception:
        _registrar("bluez_diario_nao_gravou", nivel="warning")


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
        return resto == "true" if resto in ("true", "false") else None
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

#: O ``PATH`` de um sistema sem ninguém na frente. É por ele que se sabe qual
#: ``busctl`` é o do sistema — o que fala com o barramento dela.
_PATH_DO_SISTEMA = "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"

#: O que roda UMA pergunta de ``busctl``: recebe os argumentos (sem o nome do
#: programa) e devolve a saída, ou ``None`` quando não deu. É a forma que os
#: dublês da suíte sempre tiveram.
Executar = Callable[[Sequence[str]], "str | None"]


def _e_o_do_sistema(achado: str) -> bool:
    """Este ``busctl`` é o do sistema, e não um de mentira posto no ``PATH``?"""
    do_sistema = shutil.which(FERRAMENTA, path=_PATH_DO_SISTEMA)
    if do_sistema is None:
        return False
    return os.path.realpath(achado) == os.path.realpath(do_sistema)


def busctl(argumentos: Sequence[str], *, espera: float = ESPERA_DO_BUSCTL_S) -> str | None:
    """Roda um ``busctl`` de usuário no barramento de sistema. ``None`` = não deu.

    Ferramenta ausente, código diferente de zero e teto estourado colapsam em
    ``None``. Saída vazia com código ``0`` é SUCESSO — é o que o
    ``set-property`` devolve.

    SOB A SUÍTE: escrita nunca; leitura só por um ``busctl`` de mentira que a
    régua pôs na frente do ``PATH``. O do sistema é o barramento DELA, e uma
    régua que o lê mede a máquina de quem mantém o projeto, não o produto.

    ``--json=short`` vai DEPOIS do verbo, e só no ``get-property``: o
    ``busctl`` aceita a opção em qualquer posição, e os ``busctl`` de mentira da
    suíte casam o verbo pela primeira palavra. ``LC_ALL=C`` não é zelo: o
    ``pactl`` desta casa já cegou um leitor duas vezes traduzindo a própria
    saída.
    """
    verbo = argumentos[0] if argumentos else ""
    achado = shutil.which(FERRAMENTA)
    if achado is None:
        return None
    if a_suite_esta_rodando() and (verbo not in _LEITURAS_DO_BUSCTL or _e_o_do_sistema(achado)):
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
# O kernel: o endereço de cada adaptador, e o lugar pelo sysfs.
# ---------------------------------------------------------------------------


def enderecos_pelo_kernel(leitor: Any = None) -> dict[str, str] | None:
    """``{hciN: endereço}`` direto do kernel, sem ``bluetoothd`` e sem texto.

    O dono do ioctl é ``ar_do_adaptador.LeitorDoKernel`` (AR-MEDIDO-01): um
    socket HCI cru, ``HCIGETDEVLIST`` e ``HCIGETDEVINFO``, que respondem como
    uid 1000 e não dependem do ``bluetoothd``. Escrever um segundo leitor do
    mesmo ioctl aqui seria a segunda verdade sobre o mesmo número.

    ``None`` é "não deu": sem ``AF_BLUETOOTH`` neste Python, socket recusado
    (Flatpak), ou a suíte no ar — a suíte não lê a mesa dela por aqui.
    """
    if leitor is None and a_suite_esta_rodando():
        return None
    try:
        if leitor is None:
            from hefesto_dualsense4unix.integrations.ar_do_adaptador import LeitorDoKernel

            leitor = LeitorDoKernel()
        numeros = leitor.adaptadores()
        if numeros is None:
            return None
        achados: dict[str, str] = {}
        for numero in numeros:
            leitura = leitor.ler(numero)
            if leitura is None or leitura.endereco == "00:00:00:00:00:00":
                continue
            achados[f"hci{int(numero)}"] = leitura.endereco
        return achados
    except Exception:
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
        from hefesto_dualsense4unix.integrations.mesa_de_radio import adaptadores_bluetooth

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
        """O fato, curto, para o diário — é de lá que a tela o lê."""
        if self.tipo == "trocado":
            return "O adaptador desta porta foi trocado."
        return "Este adaptador mudou de porta."


#: O ``o_que`` da linha do diário quando um dongle troca de lugar.
MUDOU_DE_LUGAR = "adaptador mudou de lugar"


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


def _guardar_e_comparar(
    arquivo: Path, agora: Mapping[str, str]
) -> tuple[MudancaDeLugar, ...]:
    """Lê a memória, compara e grava a de agora — sob ``flock``, porque o
    daemon e a janela ligam cada um o seu dono e perguntariam juntos."""
    arquivo.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(arquivo, os.O_RDWR | os.O_CREAT | os.O_CLOEXEC | os.O_NOFOLLOW, 0o644)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        bruto = os.read(fd, 1 << 20).decode("utf-8", "replace")
        try:
            lido = json.loads(bruto) if bruto.strip() else {}
        except ValueError:
            lido = {}
        antes = (
            {str(k): str(v) for k, v in lido.items()} if isinstance(lido, dict) else {}
        )
        mudancas = perceber_as_mudancas(antes, agora)
        guardado = dict(antes)
        for mudanca in mudancas:
            if mudanca.lugar_antigo and guardado.get(mudanca.lugar_antigo) == mudanca.endereco:
                del guardado[mudanca.lugar_antigo]
        guardado.update(agora)
        texto = json.dumps(guardado, ensure_ascii=False, indent=1, sort_keys=True)
        os.lseek(fd, 0, os.SEEK_SET)
        os.ftruncate(fd, 0)
        os.write(fd, texto.encode("utf-8"))
        return mudancas
    finally:
        os.close(fd)


# ---------------------------------------------------------------------------
# As leituras compostas.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class AdaptadorDoBluez:
    """Um adaptador. ``caminho`` e ``hci`` caducam entre boots: nunca guarde.

    ``lugar`` é a chave D3 (:func:`lugar_de`) — é ela, e não o endereço, que
    segue o nome que ela deu à porta.
    """

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
    """Um aparelho que o BlueZ conhece, num adaptador (``adaptador`` é o caminho)."""

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


def _inteiro(valor: object) -> int | None:
    return valor if isinstance(valor, int) and not isinstance(valor, bool) else None


# ---------------------------------------------------------------------------
# O leitor — o contrato comum aos dois caminhos.
# ---------------------------------------------------------------------------


class LeitorDoBluez:
    """O que todo leitor e escritor do BlueZ responde, pelo caminho que tiver.

    Duas subclasses: :class:`DonoVivo` (o Gio, a foto ao vivo) e
    :class:`PeloBusctl` (o caminho de reserva, e a forma dos dublês da suíte).
    As escritas passam TODAS por :meth:`chamar` e :meth:`escrever_propriedade`,
    que é onde moram a guarda da suíte, a trava e o diário.
    """

    #: ``True`` quando o destino é o BlueZ de verdade. Só esses a guarda da
    #: suíte recusa: um dublê não é o rádio dela.
    toca_o_sistema: bool = False

    #: ``True`` só onde há conexão viva para registrar o agente próprio (R5) e
    #: manter uma busca de pé (a busca é POR CLIENTE).
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
        self, caminho: str, interface: str, nome: str, assinatura: str, valor: Any, espera: float
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
            return Escrita(False, RECUSA_DA_SUITE, "a suíte está no ar e este é o BlueZ de verdade")
        return None

    def _na_borda(
        self, quem: str, metodo: str, caminho: str, fazer: Callable[[], Escrita]
    ) -> Escrita:
        """Guarda da suíte, trava e diário — nesta ordem, para toda escrita."""
        recusa = self._recusa()
        if recusa is not None:
            return recusa
        if metodo in METODOS_SEM_TRAVA:
            escrita = fazer()
        else:
            from hefesto_dualsense4unix.integrations.diario_do_radio import TravaOcupadaError

            try:
                with na_trava(quem):
                    escrita = fazer()
            except TravaOcupadaError as ocupada:
                return Escrita(False, TRAVA_OCUPADA, str(ocupada))
        _no_diario(quem, metodo, caminho, escrita)
        return escrita

    def chamar(
        self,
        caminho: str,
        interface: str,
        metodo: str,
        assinatura: str = "",
        argumentos: Sequence[Any] = (),
        *,
        espera: float = ESPERA_DO_BUSCTL_S,
        quem: str = QUEM_PADRAO,
    ) -> Escrita:
        """Chama um método do BlueZ — pela borda."""
        return self._na_borda(
            quem,
            metodo,
            caminho,
            lambda: self._chamar(caminho, interface, metodo, assinatura, argumentos, espera),
        )

    def escrever_propriedade(
        self,
        caminho: str,
        interface: str,
        nome: str,
        assinatura: str,
        valor: Any,
        *,
        espera: float = ESPERA_DO_BUSCTL_S,
        quem: str = QUEM_PADRAO,
    ) -> Escrita:
        """Grava uma propriedade do BlueZ — pela mesma borda de :meth:`chamar`."""
        return self._na_borda(
            quem,
            nome,
            caminho,
            lambda: self._escrever(caminho, interface, nome, assinatura, valor, espera),
        )

    # -- as leituras compostas -----------------------------------------------

    def endereco_do_adaptador(
        self,
        caminho: str,
        *,
        espera: float | None = None,
        kernel: Mapping[str, str] | None = None,
    ) -> str | None:
        """O endereço deste adaptador: o do kernel quando dá, o do D-Bus quando não."""
        do_kernel = self._enderecos_do_kernel() if kernel is None else kernel
        hci = _hci_de(caminho)
        if do_kernel and hci in do_kernel:
            return do_kernel[hci]
        return _mac(self.propriedade(caminho, ADAPTADOR, "Address", espera=espera))

    def adaptadores(self) -> tuple[AdaptadorDoBluez, ...] | None:
        """Os adaptadores, em ordem de caminho. ``None`` = não deu para perguntar."""
        caminhos = self.caminhos()
        if caminhos is None:
            return None
        kernel = self._enderecos_do_kernel() or {}
        lugares = self._lugares()
        achados: list[AdaptadorDoBluez] = []
        for caminho in caminhos:
            hci = _hci_de(caminho)
            if not hci:
                continue
            endereco = self.endereco_do_adaptador(caminho, kernel=kernel)
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
                    varrendo=como_booleano(self.propriedade(caminho, ADAPTADOR, "Discovering")),
                    lugar=lugares.get(hci, ""),
                )
            )
        return tuple(achados)

    def aparelhos(self, *, adaptador: str | None = None) -> tuple[AparelhoDoBluez, ...] | None:
        """Os aparelhos — de todos os adaptadores, ou só do CAMINHO ``adaptador``."""
        caminhos = self.caminhos()
        if caminhos is None:
            return None
        achados: list[AparelhoDoBluez] = []
        for caminho in caminhos:
            forma = _CAMINHO_DE_APARELHO.match(caminho)
            if forma is None or (adaptador is not None and forma.group(1) != adaptador):
                continue
            endereco = endereco_do_aparelho(caminho)
            if endereco is None:
                continue
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
                    rssi=_inteiro(self.propriedade(caminho, APARELHO, "RSSI")),
                    classe=_inteiro(self.propriedade(caminho, APARELHO, "Class")),
                    modalias=str(self.propriedade(caminho, APARELHO, "Modalias") or ""),
                )
            )
        return tuple(achados)

    def caminho_do_adaptador(self, endereco: str) -> str | None:
        """O ``/org/bluez/hciN`` de AGORA deste endereço. Resolvido, nunca guardado."""
        alvo = _mac(endereco)
        if alvo is None:
            return None
        kernel = self._enderecos_do_kernel() or {}
        for caminho in self.caminhos() or ():
            if _hci_de(caminho) and self.endereco_do_adaptador(caminho, kernel=kernel) == alvo:
                return caminho
        return None

    def caminho_do_aparelho(self, endereco: str, *, adaptador: str | None = None) -> str | None:
        """O caminho deste aparelho — em QUALQUER adaptador, ou no de endereço ``adaptador``.

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
        for caminho in caminhos:
            forma = _CAMINHO_DE_APARELHO.match(caminho)
            if forma is None or endereco_do_aparelho(caminho) != alvo:
                continue
            if pai is None or forma.group(1) == pai:
                return caminho
        return None

    # -- as escritas nomeadas ------------------------------------------------

    def escrever_alias(
        self, caminho_do_adaptador: str, texto: str, *, quem: str = QUEM_PADRAO
    ) -> Escrita:
        """O ``Alias`` do adaptador. Sem privilégio: medido como uid 1000 em 22/08."""
        return self.escrever_propriedade(
            caminho_do_adaptador, ADAPTADOR, "Alias", "s", texto, quem=quem
        )

    def conectar(
        self, caminho: str, *, espera: float = ESPERA_DO_CONNECT_S, quem: str = QUEM_PADRAO
    ) -> Escrita:
        """``Connect`` — chama o aparelho, e ele pode estar dormindo."""
        return self.chamar(caminho, APARELHO, "Connect", espera=espera, quem=quem)

    def desconectar(self, caminho: str, *, quem: str = QUEM_PADRAO) -> Escrita:
        """``Disconnect`` — derruba a conexão; o bond fica."""
        return self.chamar(caminho, APARELHO, "Disconnect", quem=quem)

    def remover_aparelho(self, caminho_do_aparelho: str, *, quem: str = QUEM_PADRAO) -> Escrita:
        """``RemoveDevice`` no adaptador pai — esquece o bond NESTE adaptador só.

        O resto em disco (a pasta do bond com o dongle fora, o cache SDP) e a
        lápide são da ponte root (``esquecer``): o D-Bus não alcança o disco.
        """
        forma = _CAMINHO_DE_APARELHO.match(caminho_do_aparelho)
        if forma is None:
            return Escrita(False, SEM_BARRAMENTO, "isto não é caminho de aparelho")
        return self.chamar(
            forma.group(1), ADAPTADOR, "RemoveDevice", "o", (caminho_do_aparelho,), quem=quem
        )

    def confiar(self, caminho: str, sim: bool = True, *, quem: str = QUEM_PADRAO) -> Escrita:
        """``Trusted`` — o aparelho reconecta sem pedir licença ao agente."""
        return self.escrever_propriedade(caminho, APARELHO, "Trusted", "b", bool(sim), quem=quem)

    def parear(
        self, caminho: str, *, espera: float = ESPERA_DO_PAIR_S, quem: str = QUEM_PADRAO
    ) -> Escrita:
        """``Pair`` e, se deu, ``Trusted`` — os dois na mesma trava.

        Por aqui, sem conexão viva, não há agente próprio: quem atende é o
        padrão (o ``hefesto-bt-agent``, o piso). :class:`DonoVivo` troca isto
        pelo agente nosso (R5).
        """
        from hefesto_dualsense4unix.integrations.diario_do_radio import TravaOcupadaError

        recusa = self._recusa()
        if recusa is not None:
            return recusa
        try:
            with na_trava(quem):
                escrita = self.chamar(caminho, APARELHO, "Pair", espera=espera, quem=quem)
                if escrita.feita:
                    self.confiar(caminho, quem=quem)
        except TravaOcupadaError as ocupada:
            return Escrita(False, TRAVA_OCUPADA, str(ocupada))
        return escrita

    def comecar_busca(self, caminho_do_adaptador: str, *, quem: str = QUEM_PADRAO) -> Escrita:
        """``StartDiscovery`` — só vale numa conexão que fica: a busca é POR CLIENTE."""
        return Escrita(False, SEM_BARRAMENTO, "a busca só vale numa conexão que fica")

    def parar_busca(self, caminho_do_adaptador: str, *, quem: str = QUEM_PADRAO) -> Escrita:
        """``StopDiscovery`` do NOSSO cliente — a busca alheia não se para de fora."""
        return Escrita(False, SEM_BARRAMENTO, "a busca só vale numa conexão que fica")

    # -- o lugar (D3) ---------------------------------------------------------

    def conferir_os_lugares(self, *, memoria: Path | None = None) -> tuple[MudancaDeLugar, ...]:
        """Compara o lugar de cada adaptador com o da última vez, e guarda o de agora.

        Trocar o dongle de porta é PERCEBIDO e dito: cada mudança vai ao diário
        comum com a frase (:attr:`MudancaDeLugar.frase`), que é de onde a tela a
        lê. A memória é nossa (``~/.local/state``), nunca do BlueZ nem do
        ``maquina.json`` dela. Nunca levanta.
        """
        adaptadores = self.adaptadores()
        agora = {a.lugar: a.endereco for a in adaptadores or () if a.lugar}
        if not agora:
            return ()
        try:
            mudancas = _guardar_e_comparar(
                memoria if memoria is not None else _memoria_dos_lugares(), agora
            )
        except OSError:
            _registrar("bluez_lugares_sem_memoria", nivel="warning")
            return ()
        for mudanca in mudancas:
            try:
                from hefesto_dualsense4unix.integrations import diario_do_radio

                diario_do_radio.registrar(
                    QUEM_PADRAO,
                    MUDOU_DE_LUGAR,
                    mudanca.tipo,
                    antes={"lugar": mudanca.lugar_antigo or None,
                           "endereco": mudanca.endereco_antigo or None},
                    depois={"lugar": mudanca.lugar, "endereco": mudanca.endereco},
                    adaptador=mudanca.endereco,
                    porta=mudanca.lugar,
                    frase=mudanca.frase,
                )
            except Exception:
                _registrar("bluez_lugar_sem_diario", nivel="warning")
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
        bruto = self._rodar(["get-property", SERVICO, caminho, interface, nome], espera)
        return desembrulhar(bruto)

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
        self, caminho: str, interface: str, nome: str, assinatura: str, valor: Any, espera: float
    ) -> Escrita:
        bruto = self._rodar(
            ["set-property", SERVICO, caminho, interface, nome, assinatura,
             _texto_do_busctl(valor)],
            espera,
        )
        if bruto is None:
            return Escrita(False, mensagem="o busctl não confirmou")
        return Escrita(True, resposta=bruto)

    def _enderecos_do_kernel(self) -> Mapping[str, str] | None:
        return enderecos_pelo_kernel() if self._executar is None else None

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
        self, caminho: str, interface: str, nome: str, assinatura: str, valor: Any, *, espera: float
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
    ``src/device.c:3374`` do 5.86). Fio próprio porque sinal e objeto exportado
    são entregues no contexto do fio que os assinou: um ``GLib.MainLoop`` num
    contexto privado não disputa nada com o laço do GTK nem com o asyncio.

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
        """Liga o fio e a conexão. ``False`` quando não deu, com :attr:`erro`.

        SOB A SUÍTE o barramento de SISTEMA não abre: é o BlueZ dela, e a borda
        só recusaria as escritas — a foto, a assinatura e o ``GetNameOwner``
        leriam a mesa dela, que é o que o ``busctl`` já recusa. Uma régua que
        precisa do Gio passa o endereço de um ``dbus-daemon`` particular.
        """
        if self.e_do_sistema and a_suite_esta_rodando():
            self.erro = "a suíte não abre o barramento de sistema"
            return False
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
            endereco = self._endereco or gio.dbus_address_get_for_bus_sync(gio.BusType.SYSTEM, None)
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

    def _no_fio(self, tarefa: Callable[[], Any], *, espera: float = 5.0) -> Any:
        """Roda a ``tarefa`` no fio do barramento e devolve o resultado (``None`` no prazo)."""
        if threading.current_thread() is self._fio:
            return tarefa()
        caixa: dict[str, Any] = {}
        feito = threading.Event()

        def rodar(*_dados: Any) -> bool:
            try:
                caixa["valor"] = tarefa()
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
        return str(self._conexao.get_unique_name() or "") if self._conexao is not None else ""

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
        escrita = self.chamar(SERVICO, "/", OBJETOS, "GetManagedObjects", "", (), espera=espera)
        if not escrita.feita or not escrita.resposta:
            return None
        return {
            str(caminho): {str(i): dict(p) for i, p in interfaces.items()}
            for caminho, interfaces in escrita.resposta[0].items()
        }

    def assinar(self, ao_sinal: Callable[[Sinal], None]) -> bool:
        gio = self._gio

        def chegou(
            _conexao: Any,
            _remetente: str,
            caminho: str,
            _interface: str,
            nome: str,
            parametros: Any,
            *_dados: Any,
        ) -> None:
            try:
                valores = parametros.unpack()
                if nome == "InterfacesAdded":
                    ao_sinal(Sinal("entrou", caminho=valores[0], propriedades=valores[1]))
                elif nome == "InterfacesRemoved":
                    saiu = tuple(valores[1])
                    ao_sinal(Sinal("saiu", caminho=valores[0], interfaces_que_sairam=saiu))
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
                _registrar("bluez_sinal_nao_entendido", nivel="warning")

        def assinar_no_fio() -> bool:
            conexao = self._conexao
            nenhum = gio.DBusSignalFlags.NONE
            self._assinaturas = [
                *(
                    conexao.signal_subscribe(SERVICO, OBJETOS, sinal, None, None, nenhum, chegou)
                    for sinal in ("InterfacesAdded", "InterfacesRemoved")
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
        parametros = glib.Variant(f"({assinatura})", tuple(argumentos)) if assinatura else None
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
            return Escrita(False, gio.DBusError.get_remote_error(problema) or "", problema.message)
        except Exception as problema:
            return Escrita(False, SEM_BARRAMENTO, str(problema))
        return Escrita(True, resposta=resposta.unpack() if resposta is not None else ())

    def escrever(
        self, caminho: str, interface: str, nome: str, assinatura: str, valor: Any, *, espera: float
    ) -> Escrita:
        """``Properties.Set`` no ``org.bluez``, com o valor já no tipo do D-Bus."""
        if self._conexao is None:
            return Escrita(False, SEM_BARRAMENTO, self.erro)
        variante = self._glib.Variant(assinatura, valor)
        return self.chamar(
            SERVICO, caminho, PROPRIEDADES, "Set", "ssv", (interface, nome, variante), espera=espera
        )

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

    Assina ANTES de tirar a foto, e os sinais que chegam DURANTE a foto ficam
    numa fila e são reaplicados, na ordem, por cima dela: reaplicar um valor
    que a foto já trazia não muda nada, e o que mudou depois dela não se perde.

    ``kernel`` e ``lugares`` são injetáveis para a régua; no sistema, o
    ``HCIGETDEVINFO`` e o sysfs.
    """

    atende_o_proprio_pareamento = True

    def __init__(
        self,
        barramento: Barramento,
        *,
        kernel: Callable[[], Mapping[str, str] | None] | None = None,
        lugares: Callable[[], Mapping[str, str]] | None = None,
    ) -> None:
        self._barramento = barramento
        self.toca_o_sistema = bool(getattr(barramento, "e_do_sistema", False))
        self._kernel = kernel
        self._lugares_de = lugares
        self._tranca = threading.Lock()
        self._tranca_da_foto = threading.Lock()
        self._objetos: dict[str, dict[str, dict[str, Any]]] = {}
        self._fila: list[Sinal] | None = None
        self._bluez_de_pe = False
        self._dono_do_bluez = ""
        self._ultima_foto: float | None = None
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
        if self.toca_o_sistema:
            self._em_segundo_plano(self.conferir_os_lugares)
        return True

    def fechar(self) -> None:
        """Desregistra o agente próprio e fecha a conexão. Idempotente."""
        with self._tranca_do_agente:
            agente, self._agente = self._agente, None
        if agente is not None:
            agente.desregistrar()
        self._barramento.fechar()

    @staticmethod
    def _em_segundo_plano(tarefa: Callable[[], Any]) -> None:
        """Trabalho que o fio do barramento não pode fazer: ele entrega os sinais."""

        def rodar() -> None:
            try:
                tarefa()
            except Exception:
                _registrar("bluez_trabalho_de_fundo_falhou", nivel="warning")

        threading.Thread(target=rodar, name="hefesto-bluez-fundo", daemon=True).start()

    def _fotografar(self) -> None:
        with self._tranca_da_foto:
            with self._tranca:
                self._fila = []
                self._ultima_foto = time.monotonic()
            foto = self._barramento.objetos(espera=ESPERA_DA_FOTO_S)
            dono = self._barramento.dono_do_nome(SERVICO) if foto is not None else ""
            with self._tranca:
                self._objetos = foto or {}
                self._bluez_de_pe = foto is not None
                self._dono_do_bluez = dono
                fila, self._fila = self._fila or [], None
                for sinal in fila:
                    self._aplicar(sinal)

    def _ao_sinal(self, sinal: Sinal) -> None:
        if sinal.tipo == "dono":
            if sinal.dono_novo:
                _registrar("bluez_voltou_ao_barramento")
                self._em_segundo_plano(self._fotografar)
                return
            with self._tranca:
                self._objetos = {}
                self._bluez_de_pe = False
                self._dono_do_bluez = ""
            with self._tranca_do_agente:
                if self._agente is not None:
                    self._agente.invalidar()
            _registrar("bluez_saiu_do_barramento", nivel="warning")
            return
        with self._tranca:
            if self._fila is not None:
                self._fila.append(sinal)
                return
            self._aplicar(sinal)
        adaptador_novo = sinal.tipo == "entrou" and ADAPTADOR in (sinal.propriedades or {})
        if self.toca_o_sistema and adaptador_novo:
            self._em_segundo_plano(self.conferir_os_lugares)

    def _aplicar(self, sinal: Sinal) -> None:
        """Um sinal na foto. Chamado com :attr:`_tranca` na mão."""
        if sinal.tipo == "entrou":
            objeto = self._objetos.setdefault(sinal.caminho, {})
            for interface, propriedades in (sinal.propriedades or {}).items():
                objeto[interface] = dict(propriedades)
        elif sinal.tipo == "saiu":
            restante = self._objetos.get(sinal.caminho)
            if restante is not None:
                for interface in sinal.interfaces_que_sairam:
                    restante.pop(interface, None)
                if not restante:
                    del self._objetos[sinal.caminho]
        elif sinal.tipo == "mudou":
            objeto = self._objetos.setdefault(sinal.caminho, {})
            propriedades = objeto.setdefault(sinal.interface, {})
            propriedades.update(sinal.mudadas or {})
            for nome in sinal.invalidadas:
                propriedades.pop(nome, None)

    # -- leitura: a foto ------------------------------------------------------

    def pode_perguntar(self) -> bool:
        return self._barramento.vivo()

    def caminhos(self, *, espera: float | None = None) -> tuple[str, ...] | None:
        """A árvore da foto; ``None`` = não sei.

        Sem foto de pé, a leitura responde ``None`` AGORA e pede outra foto em
        segundo plano, no máximo uma a cada :data:`REFOTOGRAFAR_S` — quem lê tem
        orçamento (a varredura, meio segundo) e não pode pagar o
        ``GetManagedObjects`` inteiro.
        """
        with self._tranca:
            if self._bluez_de_pe:
                return tuple(sorted(self._objetos))
            agora = time.monotonic()
            vencida = self._ultima_foto is None or agora - self._ultima_foto >= REFOTOGRAFAR_S
            if vencida:
                self._ultima_foto = agora
        if vencida:
            self._em_segundo_plano(self._refotografar_se_o_bluez_esta_la)
        return None

    def _refotografar_se_o_bluez_esta_la(self) -> None:
        """A foto de novo — só se o ``org.bluez`` tem dono AGORA.

        Perguntar ao ``org.bluez`` sem dono pediria ao barramento que o ATIVASSE
        (``org.bluez.service``): quem parou o ``bluetoothd`` de propósito o veria
        voltar sozinho. Sem dono, quem refotografa é o ``NameOwnerChanged``.
        """
        if self._barramento.dono_do_nome(SERVICO):
            self._fotografar()

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
        if self._kernel is not None:
            return self._kernel()
        return enderecos_pelo_kernel() if self.toca_o_sistema else None

    def _lugares(self) -> Mapping[str, str]:
        if self._lugares_de is not None:
            return self._lugares_de()
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
        self, caminho: str, interface: str, nome: str, assinatura: str, valor: Any, espera: float
    ) -> Escrita:
        return self._barramento.escrever(caminho, interface, nome, assinatura, valor, espera=espera)

    def comecar_busca(self, caminho_do_adaptador: str, *, quem: str = QUEM_PADRAO) -> Escrita:
        """``StartDiscovery`` pela NOSSA conexão — a busca vive enquanto ela viver."""
        return self.chamar(caminho_do_adaptador, ADAPTADOR, "StartDiscovery", quem=quem)

    def parar_busca(self, caminho_do_adaptador: str, *, quem: str = QUEM_PADRAO) -> Escrita:
        """``StopDiscovery`` — só a busca que NÓS abrimos; a alheia recusa por si."""
        return self.chamar(caminho_do_adaptador, ADAPTADOR, "StopDiscovery", quem=quem)

    def parear(
        self, caminho: str, *, espera: float = ESPERA_DO_PAIR_S, quem: str = QUEM_PADRAO
    ) -> Escrita:
        """``Pair`` atendido pelo NOSSO agente (R5), e ``Trusted`` se deu.

        O BlueZ 5.86 escolhe o agente do pareamento por ``agent_get(sender)``
        (``src/device.c:3374``, ``pair_device``), e a autenticação do bond usa
        esse mesmo agente (``device.c:7599``): quem chama ``Pair`` com agente
        registrado é atendido pelo PRÓPRIO agente, seja quem for o padrão. Por
        isso o agente mora nesta conexão e o ``Pair`` sai por ela. Nunca
        ``RequestDefaultAgent``: o ``hefesto-bt-agent`` continua o padrão, de
        piso, para o que chega sozinho — e a capacidade dos adaptadores só muda
        com o padrão (``adapter.c:9400``), então ela não muda.
        """
        from hefesto_dualsense4unix.integrations.diario_do_radio import TravaOcupadaError

        recusa = self._recusa()
        if recusa is not None:
            return recusa
        agente = self._agente_pronto()
        if agente is None:
            return Escrita(False, SEM_AGENTE, "o agente próprio não se registrou")
        try:
            with na_trava(quem), agente.esperando(caminho):
                escrita = self.chamar(caminho, APARELHO, "Pair", espera=espera, quem=quem)
                if escrita.feita:
                    self.confiar(caminho, quem=quem)
        except TravaOcupadaError as ocupada:
            return Escrita(False, TRAVA_OCUPADA, str(ocupada))
        return escrita

    def _agente_pronto(self) -> Any:
        from hefesto_dualsense4unix.integrations.agente_de_pareamento import AgenteDePareamento

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
    Uma régua que precisa de outro dono o põe em ``_DONO``.
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
    "ERRO_CANCELADO",
    "ERRO_JA_EXISTE",
    "ERRO_REJEITADO",
    "ESCREVEU_NO_BLUEZ",
    "ESCRITAS",
    "ESPERA_DO_BUSCTL_S",
    "ESPERA_DO_CONNECT_S",
    "ESPERA_DO_PAIR_S",
    "FERRAMENTA",
    "GERENTE_DE_AGENTES",
    "LEITURAS",
    "METODOS_SEM_TRAVA",
    "MUDOU_DE_LUGAR",
    "QUEM_PADRAO",
    "RADIO_DE_VERDADE_NA_SUITE",
    "RAIZ_DO_BLUEZ",
    "RECUSA_DA_SUITE",
    "SEM_AGENTE",
    "SEM_BARRAMENTO",
    "SERVICO",
    "TRAVA_OCUPADA",
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
    "endereco_do_aparelho",
    "enderecos_pelo_kernel",
    "lugar_de",
    "lugares_dos_adaptadores",
    "na_trava",
    "pela_linha_de_comando",
    "pelo_executor",
    "perceber_as_mudancas",
]
