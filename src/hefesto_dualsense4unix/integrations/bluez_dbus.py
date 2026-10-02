"""bluez_dbus.py — o D-Bus do BlueZ com UM dono."""

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

from hefesto_dualsense4unix.utils.lugar import lugar_de


SERVICO = "org.bluez"
ADAPTADOR = "org.bluez.Adapter1"
APARELHO = "org.bluez.Device1"
GERENTE_DE_AGENTES = "org.bluez.AgentManager1"
AGENTE = "org.bluez.Agent1"
PROPRIEDADES = "org.freedesktop.DBus.Properties"
OBJETOS = "org.freedesktop.DBus.ObjectManager"
BARRAMENTO_DBUS = "org.freedesktop.DBus"
RAIZ_DO_BLUEZ = "/org/bluez"

FERRAMENTA = "busctl"

ERRO_REJEITADO = "org.bluez.Error.Rejected"
ERRO_CANCELADO = "org.bluez.Error.Canceled"
ERRO_JA_EXISTE = "org.bluez.Error.AlreadyExists"

RECUSA_DA_SUITE = "hefesto.RecusaDaSuite"
SEM_BARRAMENTO = "hefesto.SemBarramento"
SEM_AGENTE = "hefesto.SemAgente"
TRAVA_OCUPADA = "hefesto.TravaOcupada"

QUEM_PADRAO = "hefesto"

ESCREVEU_NO_BLUEZ = "escreveu no BlueZ"

_METODOS_DO_DIARIO = frozenset(
    {"Connect", "Disconnect", "Pair", "RemoveDevice", "StartDiscovery", "StopDiscovery"}
)

METODOS_SEM_TRAVA = frozenset({"StopDiscovery"})

AVISO_DESLIGOU = "desligou"
AVISO_SAIU_PAREADO = "saiu_pareado"
Ouvinte = Callable[[str, Mapping[str, Any]], None]

#: ``apelido_do_dongle`` e ``gesto_de_reconexao`` repetiam, cada um no seu.
ESPERA_DO_BUSCTL_S = 5.0

ESPERA_DO_CONNECT_S = 12.0

ESPERA_DO_PAIR_S = 45.0

ESPERA_DA_FOTO_S = 3.0

TENTAR_O_GIO_DE_NOVO_S = 60.0

REFOTOGRAFAR_S = 5.0

_CAMINHO_DE_ADAPTADOR = re.compile(r"^/org/bluez/(hci[0-9]+)$")
_CAMINHO_DE_APARELHO = re.compile(
    r"^(/org/bluez/hci[0-9]+)/dev_([0-9A-Fa-f]{2}(?:_[0-9A-Fa-f]{2}){5})$"
)
_MINIMO_POR_PERGUNTA = 0.02


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


@dataclass(frozen=True)
class Escrita:
    """O que aconteceu com UMA escrita no BlueZ. Imutável, nunca uma exceção."""

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


_POR_FIO = threading.local()


@contextlib.contextmanager
def _pela_borda() -> Iterator[None]:
    """Marca o fio como DENTRO da borda enquanto a escrita roda."""
    anterior = getattr(_POR_FIO, "na_borda", False)
    _POR_FIO.na_borda = True
    try:
        yield
    finally:
        _POR_FIO.na_borda = anterior


@contextlib.contextmanager
def na_trava(quem: str = QUEM_PADRAO, *, prazo_s: float | None = None) -> Iterator[float]:
    """Segura a trava comum do rádio enquanto o bloco roda. Entrega quanto esperou."""
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


def a_trava_esta_tomada() -> bool:
    """A trava comum do rádio está na mão de alguém AGORA — deste fio, de outro"""
    if getattr(_POR_FIO, "dentro", 0):
        return True
    from hefesto_dualsense4unix.integrations import diario_do_radio

    try:
        fd = os.open(diario_do_radio.caminho_da_trava(),
                     os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW)
    except OSError:
        return False
    try:
        fcntl.flock(fd, fcntl.LOCK_SH | fcntl.LOCK_NB)
    except BlockingIOError:
        return True
    except OSError:
        return False
    else:
        fcntl.flock(fd, fcntl.LOCK_UN)
        return False
    finally:
        os.close(fd)


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


_INTEIROS_DO_DBUS = frozenset("ynqiuxth")


def desembrulhar(bruto: str | None) -> Any | None:
    """O valor de uma resposta do ``busctl``: JSON na frente, texto atrás."""
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
    """``True``/``False`` para o que o BlueZ disse, ``None`` para "não sei"."""
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


_LEITURAS_DO_BUSCTL = frozenset({"tree", "get-property", "introspect"})

_PATH_DO_SISTEMA = "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"

Executar = Callable[[Sequence[str]], "str | None"]


def _e_o_do_sistema(achado: str) -> bool:
    """Este ``busctl`` é o do sistema, e não um de mentira posto no ``PATH``?"""
    do_sistema = shutil.which(FERRAMENTA, path=_PATH_DO_SISTEMA)
    if do_sistema is None:
        return False
    return os.path.realpath(achado) == os.path.realpath(do_sistema)


def busctl(argumentos: Sequence[str], *, espera: float = ESPERA_DO_BUSCTL_S) -> str | None:
    """Roda um ``busctl`` de usuário no barramento de sistema. ``None`` = não deu."""
    verbo = argumentos[0] if argumentos else ""
    if verbo not in _LEITURAS_DO_BUSCTL and not getattr(_POR_FIO, "na_borda", False):
        _registrar("bluez_escrita_fora_da_borda", nivel="warning", verbo=verbo)
        return None
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


def enderecos_pelo_kernel(leitor: Any = None) -> dict[str, str] | None:
    """``{hciN: endereço}`` direto do kernel, sem ``bluetoothd`` e sem texto."""
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


def lugares_dos_adaptadores() -> dict[str, str]:
    """``{hciN: lugar}`` pelo sysfs, pelo dono do sysfs (``mesa_de_radio``)."""
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
    """Um dongle que mudou desde a última vez que o dono olhou (D3)."""

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


MUDOU_DE_LUGAR = "adaptador mudou de lugar"


def perceber_as_mudancas(
    antes: Mapping[str, str], agora: Mapping[str, str]
) -> tuple[MudancaDeLugar, ...]:
    """As mudanças entre duas leituras ``{lugar: endereço}``. Função pura."""
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
    """Lê a memória, compara e grava a de agora — sob ``flock``, porque o"""
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
    icone: str = ""


def _inteiro(valor: object) -> int | None:
    return valor if isinstance(valor, int) and not isinstance(valor, bool) else None


class LeitorDoBluez:
    """O que todo leitor e escritor do BlueZ responde, pelo caminho que tiver."""

    toca_o_sistema: bool = False

    atende_o_proprio_pareamento: bool = False


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
            with _pela_borda():
                escrita = fazer()
        else:
            from hefesto_dualsense4unix.integrations.diario_do_radio import TravaOcupadaError

            try:
                with na_trava(quem), _pela_borda():
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
                    icone=str(self.propriedade(caminho, APARELHO, "Icon") or ""),
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

    def caminhos_do_aparelho(self, endereco: str) -> tuple[str, ...] | None:
        """Todos os objetos deste aparelho — um por adaptador que o conhece."""
        alvo = _mac(endereco)
        caminhos = self.caminhos()
        if alvo is None or caminhos is None:
            return None
        return tuple(
            caminho for caminho in caminhos
            if _CAMINHO_DE_APARELHO.match(caminho) and endereco_do_aparelho(caminho) == alvo
        )

    def caminho_do_aparelho(self, endereco: str, *, adaptador: str | None = None) -> str | None:
        """O caminho deste aparelho — em QUALQUER adaptador, ou no de endereço ``adaptador``."""
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
        """``RemoveDevice`` no adaptador pai — esquece o bond NESTE adaptador só."""
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
        """``Pair`` e, se deu, ``Trusted`` — os dois na mesma trava."""
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


    def conferir_os_lugares(self, *, memoria: Path | None = None) -> tuple[MudancaDeLugar, ...]:
        """Compara o lugar de cada adaptador com o da última vez, e guarda o de agora."""
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
    "caminhos_do_aparelho",
    "conferir_os_lugares",
    "dono_do_bluez",
    "entrada",
)
CICLO = ("ligar", "fechar", "ouvir")


def _texto_do_busctl(valor: Any) -> str:
    if isinstance(valor, bool):
        return "true" if valor else "false"
    return str(valor)


class PeloBusctl(LeitorDoBluez):
    """O BlueZ por ``busctl``, uma pergunta por subprocesso."""

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
    """Um leitor sobre um executor de LINHA INTEIRA (o de ``conexao_zumbi``)."""

    def rodar(argumentos: Sequence[str]) -> str | None:
        return executor([FERRAMENTA, *argumentos]) or None

    return PeloBusctl(rodar)


@dataclass(frozen=True)
class Sinal:
    """Um sinal do barramento, já traduzido para Python."""

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
    """O barramento de verdade, por uma conexão PRÓPRIA e um fio PRÓPRIO."""

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
        self._cancelar: Any = None
        self._assinaturas: list[int] = []
        self._exportados: dict[str, int] = {}
        self.erro = ""

    def abrir(self, *, espera: float = 2.0) -> bool:
        """Liga o fio e a conexão. ``False`` quando não deu, com :attr:`erro`."""
        if self.e_do_sistema and a_suite_esta_rodando():
            self.erro = "a suíte não abre o barramento de sistema"
            return False
        try:
            from gi.repository import Gio, GLib
        except Exception as problema:
            self.erro = f"sem Gio: {problema}"
            return False
        self._gio, self._glib = Gio, GLib
        self._contexto = GLib.MainContext.new()
        self._laco = GLib.MainLoop.new(self._contexto, False)
        self._cancelar = Gio.Cancellable.new()
        self._fio = threading.Thread(target=self._viver, name="hefesto-bluez", daemon=True)
        self._fio.start()
        if not self._pronto.wait(espera):
            self._cancelar.cancel()
            self.erro = "o barramento não respondeu a tempo"
            return False
        return self._conexao is not None

    def _viver(self) -> None:
        gio = self._gio
        self._contexto.push_thread_default()
        try:
            endereco = self._endereco or gio.dbus_address_get_for_bus_sync(
                gio.BusType.SYSTEM, self._cancelar
            )
            conexao = gio.DBusConnection.new_for_address_sync(
                endereco,
                gio.DBusConnectionFlags.AUTHENTICATION_CLIENT
                | gio.DBusConnectionFlags.MESSAGE_BUS_CONNECTION,
                None,
                self._cancelar,
            )
            conexao.set_exit_on_close(False)
            if self._cancelar.is_cancelled():
                with contextlib.suppress(Exception):
                    conexao.close_sync(None)
                raise RuntimeError("o barramento respondeu depois do prazo")
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
    """O dono de verdade: a foto do ``ObjectManager``, mantida pelos sinais."""

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
        self._ouvintes: list[Ouvinte] = []
        self._entradas: dict[str, int] = {}


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
            avisos: list[tuple[str, dict[str, Any]]] = []
            with self._tranca:
                self._objetos = foto or {}
                self._bluez_de_pe = foto is not None
                self._dono_do_bluez = dono
                fila, self._fila = self._fila or [], None
                for sinal in fila:
                    avisos.extend(self._aplicar(sinal))
            self._avisar(avisos)

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
            avisos = self._aplicar(sinal)
        self._avisar(avisos)
        adaptador_novo = sinal.tipo == "entrou" and ADAPTADOR in (sinal.propriedades or {})
        if self.toca_o_sistema and adaptador_novo:
            self._em_segundo_plano(self.conferir_os_lugares)

    def _aplicar(self, sinal: Sinal) -> list[tuple[str, dict[str, Any]]]:
        """Um sinal na foto. Chamado com :attr:`_tranca` na mão. Devolve os"""
        avisos: list[tuple[str, dict[str, Any]]] = []
        if sinal.tipo == "entrou":
            objeto = self._objetos.setdefault(sinal.caminho, {})
            for interface, propriedades in (sinal.propriedades or {}).items():
                objeto[interface] = dict(propriedades)
            if APARELHO in (sinal.propriedades or {}):
                self._entradas[sinal.caminho] = self._entradas.get(sinal.caminho, 0) + 1
        elif sinal.tipo == "saiu":
            restante = self._objetos.get(sinal.caminho)
            if restante is not None:
                antes = dict(restante.get(APARELHO) or {})
                for interface in sinal.interfaces_que_sairam:
                    restante.pop(interface, None)
                if not restante:
                    del self._objetos[sinal.caminho]
                if APARELHO in sinal.interfaces_que_sairam and como_booleano(
                        antes.get("Paired")) is True:
                    avisos.append((AVISO_SAIU_PAREADO, {
                        **self._de_quem(sinal.caminho), "dono": self._dono_do_bluez}))
        elif sinal.tipo == "mudou":
            objeto = self._objetos.setdefault(sinal.caminho, {})
            propriedades = objeto.setdefault(sinal.interface, {})
            estava = como_booleano(propriedades.get("Connected"))
            propriedades.update(sinal.mudadas or {})
            for nome in sinal.invalidadas:
                propriedades.pop(nome, None)
            if (sinal.interface == APARELHO and estava is True
                    and como_booleano(propriedades.get("Connected")) is False
                    and como_booleano(propriedades.get("Paired")) is True):
                avisos.append((AVISO_DESLIGOU, self._de_quem(sinal.caminho)))
        return avisos

    def _de_quem(self, caminho: str) -> dict[str, Any]:
        """O aparelho e o adaptador de um caminho, pela foto. Com a tranca na mão."""
        pai = caminho.rsplit("/", 1)[0]
        endereco = self._objetos.get(pai, {}).get(ADAPTADOR, {}).get("Address")
        return {"caminho": caminho, "aparelho": endereco_do_aparelho(caminho) or "",
                "adaptador": str(endereco or "")}

    def _avisar(self, avisos: Sequence[tuple[str, dict[str, Any]]]) -> None:
        """Entrega os avisos a quem ouve, FORA da tranca. A remoção que chegou"""
        if not avisos:
            return
        with self._tranca:
            ouvintes = list(self._ouvintes)
        if not ouvintes:
            return
        for aviso, dados in avisos:
            if aviso == AVISO_SAIU_PAREADO:
                dados = {**dados, "pela_trava": a_trava_esta_tomada()}
            for ouvinte in ouvintes:
                try:
                    ouvinte(aviso, dados)
                except Exception:
                    _registrar("bluez_ouvinte_levantou", nivel="warning", aviso=aviso)

    def ouvir(self, ouvinte: Ouvinte) -> None:
        """Assina os avisos deste dono. Idempotente pelo ouvinte."""
        with self._tranca:
            if ouvinte not in self._ouvintes:
                self._ouvintes.append(ouvinte)

    def entrada(self, caminho: str) -> int:
        """Quantas vezes o objeto em ``caminho`` entrou desde a foto (0: estava"""
        with self._tranca:
            return self._entradas.get(caminho, 0)


    def pode_perguntar(self) -> bool:
        return self._barramento.vivo()

    def caminhos(self, *, espera: float | None = None) -> tuple[str, ...] | None:
        """A árvore da foto; ``None`` = não sei."""
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
        """A foto de novo — só se o ``org.bluez`` tem dono AGORA."""
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
        """``Pair`` atendido pelo NOSSO agente (R5), e ``Trusted`` se deu."""
        from hefesto_dualsense4unix.integrations.diario_do_radio import TravaOcupadaError

        recusa = self._recusa()
        if recusa is not None:
            return recusa
        agente = self._agente_pronto()
        if agente is None:
            _registrar("bluez_parear_pelo_piso", nivel="warning")
            return super().parear(caminho, espera=espera, quem=quem)
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
    """O dono do BlueZ deste processo: o vivo quando o Gio alcança, o ``busctl`` quando não."""
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
