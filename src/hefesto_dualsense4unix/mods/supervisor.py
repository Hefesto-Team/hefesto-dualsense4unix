"""O supervisor das modificações: abre, vigia, reabre e para os processos.

O registro (``mods.json``) diz o que está ligado; o supervisor obedece. Cada extensão ligada
do tipo ``processo`` vira um filho do serviço num grupo próprio, que morre com ele, e na caixa
do ``bwrap`` (:func:`comando_na_caixa`). Sem ``bwrap``, fica «recusada» (:data:`FALTA_O_BWRAP`),
a não ser com a chave «Rodar sem caixa» do registro (``Entrada.sem_caixa``). Volta com espera
crescente (:data:`ESPERAS_PARA_VOLTAR`) e para pelo PID que criou, nunca por nome. O estado
vivo vai para ``mods-estado.json``; o porquê de cada regra está no ADR-021.
"""
from __future__ import annotations

import asyncio
import contextlib
import ctypes
import errno
import functools
import json
import os
import re
import secrets
import shutil
import signal
import socket
import stat
import subprocess
import sys
import threading
import time
from collections import deque
from collections.abc import Callable, Collection, Sequence
from dataclasses import asdict, dataclass, field
from io import BytesIO
from pathlib import Path
from typing import IO, Any

from hefesto_dualsense4unix.core.events import EventBus, EventTopic
from hefesto_dualsense4unix.integrations.bluez_dbus import FILTRO_DO_BLUEZ
from hefesto_dualsense4unix.mods import API_DAS_MODIFICACOES, opcoes
from hefesto_dualsense4unix.mods.instalador import (
    CHAVES_OFICIAIS,
    Entrada,
    InstalacaoRecusadaError,
    Lugares,
    SemRespostaDoGitError,
    aceitos_de,
    atualizar,
    aviso_por_ver,
    commit_novo,
    dar_por_provada,
    gravar_registro,
    ler_registro,
    manifesto_instalado,
    migrar_os_alcances,
    migrar_os_aparelhos,
    pasta_da_pessoa,
    troca_viva,
    voltar_para_a_anterior,
)
from hefesto_dualsense4unix.mods.leitura_da_caixa import abrir_o_no_sem_seguir, abrir_sem_seguir
from hefesto_dualsense4unix.mods.manifesto import (
    Manifesto,
    ManifestoRecusadoError,
    ler_manifesto,
    o_que_a_permissao_deixa,
    pedidos_do_sim,
    permissoes_novas,
)
from hefesto_dualsense4unix.mods.porta import (
    Apelidos,
    Controles,
    Escritor,
    OJogoEscreve,
    Porta,
    Pulsador,
    UniqDoPosto,
    chave_dos_apelidos,
)
from hefesto_dualsense4unix.utils.espera import prontos_para_ler
from hefesto_dualsense4unix.utils.logging_config import get_logger
from hefesto_dualsense4unix.utils.xdg_paths import (
    IPC_SOCKET_DEFAULT_NAME,
    ipc_socket_name,
    mods_socket_path,
    state_dir,
)

logger = get_logger(__name__)

DIARIO_DA_MODIFICACAO = "diario.log"

TETO_DO_DIARIO_BYTES = 1 << 20

ESPERA_DO_DIARIO_S = 1.0

ESPERA_DA_PODA_S = 0.5

ESPERAS_PARA_VOLTAR: tuple[float, ...] = (1.0, 2.0, 4.0)

ESTAVEL_DEPOIS_DE_S = 60.0

PRAZO_PARA_PARAR_S = 3.0

INTERVALO_DO_REGISTRO_S = 1.0

PRAZO_DO_PARAR_CURTO_S = 0.3

TETO_DA_MEMORIA = "512M"

TETO_DAS_TAREFAS = 256

PESO_DA_CPU = 50

OOM_SCORE_DA_EXTENSAO = 500

TAMANHO_DO_TMP_BYTES = 128 << 20

CONTROLADORES_DO_TETO = frozenset({"cpu", "memory", "pids"})

PISO_DA_ATUALIZACAO_S = 60.0

ESPERA_DEPOIS_DA_FALHA_S = 600.0

ESPERA_DEPOIS_DO_SIGKILL_S = 2.0

ESPERA_DA_VIGIA_S = 1.0

FALTA_O_BWRAP = "Falta o bwrap: a extensão não abre sem a caixa."

FALTA_O_PROXY_DO_BLUETOOTH = "Falta o xdg-dbus-proxy: a extensão com Bluetooth não abre sem ele."

SOQUETE_DO_SISTEMA_NA_CAIXA = "/run/dbus/system_bus_socket"

BARRAMENTO_DO_SISTEMA_NA_CAIXA = f"unix:path={SOQUETE_DO_SISTEMA_NA_CAIXA}"

PRAZO_DO_PROXY_S = 5.0

ENTRAM_NA_CAIXA: tuple[str, ...] = (
    "/usr", "/etc", "/bin", "/sbin", "/lib", "/lib32", "/lib64", "/libx32")

COBERTOS_NA_CAIXA: tuple[str, ...] = ("/etc/machine-id",)

PASTA_DOS_PROGRAMAS = "/opt"

DEVOLVIDO_COM_A_PERMISSAO: dict[str, tuple[str, ...]] = {
    "bluetooth": ("/sys/class/bluetooth",),
    "aparelhos": ("/run/udev",),
}

DEVOLVIDO_COM_A_REDE: tuple[str, ...] = ("/run/systemd/resolve",)

NOS_QUE_A_CAIXA_ACEITA: tuple[str, ...] = ("/dev/hidraw", "/dev/tty", "/dev/bus/usb/")

RetratoDosHubs = dict[str, int | tuple[str, str]]

PASTA_DO_HID = "/sys/bus/hid/devices"

SINTETICA_COM_A_PERMISSAO: dict[str, str] = {"bluetooth": PASTA_DO_HID}

BARRAMENTO_DO_RADIO = "0005"

POR_DENTRO_DA_CAIXA = Path(__file__).with_name("por_dentro_da_caixa.py")

PRAZO_POR_DENTRO_S = 5.0

JANELA_DO_LACO_DOS_APARELHOS_S = 60.0

PASTA_DA_CAIXA: tuple[str, ...] = (
    "--config-net", "--quiet", "--foreground", "--no-map-gw", "-D", "none",
)

_PR_SET_PDEATHSIG = 1

PRAZO_PARA_A_PONTE_OUVIR_S = 10.0

PRAZO_DA_SONDA_S = 10.0

SONDA_DO_PASTA = "sonda-do-pasta.json"

PASSO_DA_PONTE_S = 0.05

_LOOPBACK_DA_CAIXA = frozenset({"0100007F", "00000000"})

_OUVINDO = "0A"


def _prctl() -> Callable[..., int] | None:
    """O ``prctl`` da libc já carregada no processo (a do próprio Python)."""
    funcao: Callable[..., int] | None = getattr(ctypes.CDLL(None, use_errno=True), "prctl", None)
    return funcao


def _comandos_do_lancador(manifesto: Manifesto) -> tuple[str, ...]:
    """Os ``lancador.comandos`` do manifesto: os únicos que um jogo de ``lancador.jogos`` abre."""
    if "lancador" not in manifesto.tipos or not isinstance(manifesto.lancador, dict):
        return ()
    comandos = manifesto.lancador.get("comandos")
    if not isinstance(comandos, list):
        return ()
    return tuple(c for c in comandos if isinstance(c, str) and c.strip())


def _acoes_dos_aparelhos(manifesto: Manifesto) -> tuple[str, ...]:
    """Os ids das ``aparelhos_acoes`` e da ``barra``: o controle de aparelho não repete um deles."""
    geridos = manifesto.aparelhos_acoes
    return geridos.ids if geridos else ()


def _subir_o_oom_score(alvo: int) -> None:
    """Põe o ``oom_score_adj`` do processo em ``alvo`` se ele estiver abaixo: a extensão é a
    primeira a morrer por falta de memória. Subir não pede privilégio; o que não grava fica como
    está, porque no filho não há a quem dizer."""
    with contextlib.suppress(OSError, ValueError), open("/proc/self/oom_score_adj", "r+") as f:
        if int(f.read() or 0) < alvo:
            f.seek(0)
            f.write(str(alvo))


def _morre_com_o_pai(prctl: Callable[..., int] | None) -> Callable[[], None]:
    """O ``preexec_fn`` do filho: ``PR_SET_PDEATHSIG`` com ``SIGKILL`` e o ``oom_score_adj``
    acima do do serviço (:data:`OOM_SCORE_DA_EXTENSAO`).

    A função da libc é resolvida ANTES do ``fork``: no filho só a chamada roda.
    """

    def antes_de_executar() -> None:
        if prctl is not None:
            prctl(_PR_SET_PDEATHSIG, int(signal.SIGKILL), 0, 0, 0)
        _subir_o_oom_score(OOM_SCORE_DA_EXTENSAO)

    return antes_de_executar


def systemd_run_com_teto(
    *, raiz: Path = Path("/sys/fs/cgroup"), uid: int | None = None,
    achar: Callable[[str], str | None] = shutil.which, execucao: str | None = None,
) -> str | None:
    """O ``systemd-run`` que abre a extensão numa unidade própria com teto, ou ``None``.

    Só com o barramento do gerenciador de usuário à vista e ``cpu memory pids`` delegados a ele
    (``cgroup.controllers`` do ``user@<uid>.service``); sem isso a unidade nasceria sem teto, ou
    nem nasceria, e a extensão cairia na abertura.
    """
    programa = achar("systemd-run")
    pasta = os.environ.get("XDG_RUNTIME_DIR") if execucao is None else execucao
    dono = os.getuid() if uid is None else uid
    if programa is None or not pasta or not (Path(pasta) / "bus").exists():
        return None
    gerenciador = raiz / "user.slice" / f"user-{dono}.slice" / f"user@{dono}.service"
    arquivo = gerenciador / "cgroup.controllers"
    if not arquivo.is_file():
        return None
    delegados = set(arquivo.read_text(encoding="utf-8").split())
    return programa if delegados >= CONTROLADORES_DO_TETO else None


def comando_com_teto(comando: list[str], systemd_run: str | None, mod_id: str) -> list[str]:
    """``comando`` aberto por ``systemd-run --user --scope`` com os tetos de fábrica de memória
    (sem trocar para o disco), de tarefas e de CPU; sem ``systemd_run``, o próprio ``comando``.

    O ``--scope`` troca o processo pelo ``comando``: o PID, o cano do diário e o ``wait`` de quem
    abre seguem os mesmos."""
    if systemd_run is None:
        return comando
    return [
        systemd_run, "--user", "--scope", "--quiet", f"--description=Extensão {mod_id}",
        "-p", f"MemoryMax={TETO_DA_MEMORIA}", "-p", "MemorySwapMax=0",
        "-p", f"TasksMax={TETO_DAS_TAREFAS}", "-p", f"CPUWeight={PESO_DA_CPU}",
        "--", *comando,
    ]


@dataclass
class EstadoDaModificacao:
    """A linha de uma modificação no ``mods-estado.json``."""

    estado: str
    pid: int | None = None
    caixa: str = ""
    motivo: str = ""
    ultima_linha: str = ""
    quedas: int = 0


@dataclass
class _Vigiada:
    mod_id: str
    tarefa: asyncio.Task[None] | None = None
    processo: asyncio.subprocess.Process | None = None
    copia: asyncio.Task[None] | None = None
    ficha: str = ""
    instalacao: tuple[str, str, str, bool] = ("", "", "", False)
    quer_parar: asyncio.Event = field(default_factory=asyncio.Event)
    pontes: tuple[int, ...] = ()
    escritor: _EscritorDoDiario | None = None
    manifesto: Manifesto | None = None
    aparelhos: tuple[str, ...] = ()
    pela_porta: frozenset[str] = frozenset()
    aparelho_novo: bool = False
    aparelho_em_laco: bool = False
    aceitos: tuple[str, ...] = ()
    retrato: RetratoDosHubs = field(default_factory=dict)
    hid: dict[str, str] = field(default_factory=dict)
    proxy: asyncio.subprocess.Process | None = None
    sincronia: int | None = None
    soquete: Path | None = None


_A_HORA_DA_LINHA = re.compile(r"^(?:\d{4}-\d{2}-\d{2} )?\d{2}:\d{2}:\d{2} ")


def diario_da_extensao(lugares: Lugares, mod_id: str) -> Path:
    """Onde mora o diário de ``mod_id``: toda leitura e toda escrita nascem deste caminho."""
    return lugares.pasta_do_diario(mod_id) / DIARIO_DA_MODIFICACAO


def _abrir_o_diario(caminho: Path, modo: str) -> IO[bytes]:
    return open(caminho, modo, opener=abrir_sem_seguir)


def ultima_linha_do_diario(caminho: Path, *, teto: int = 200, hora: bool = False) -> str:
    """A última linha não vazia do diário (o que a tela mostra quando parou).

    Com ``hora``, o diário é o que :func:`_copiar_para_o_diario` escreve, e a hora do começo sai.
    """
    try:
        with _abrir_o_diario(caminho, "rb") as arquivo:
            arquivo.seek(0, os.SEEK_END)
            tamanho = arquivo.tell()
            arquivo.seek(max(0, tamanho - 4096))
            fim = arquivo.read().decode("utf-8", errors="replace")
    except OSError:
        return ""
    for linha in reversed(fim.splitlines()):
        texto = (_A_HORA_DA_LINHA.sub("", linha, count=1) if hora else linha).strip()
        if texto:
            return texto[:teto]
    return ""


def _aparar_o_diario(caminho: Path, chegando: int = 0) -> None:
    """Com ``chegando`` bytes a mais passaria do teto: fica só a metade nova, de linha inteira.

    O diário é do supervisor: ninguém mais o abre, e só a cópia dele escreve.
    """
    with contextlib.suppress(FileNotFoundError), _abrir_o_diario(caminho, "r+b") as arquivo:
        tamanho = arquivo.seek(0, os.SEEK_END)
        corte = tamanho - TETO_DO_DIARIO_BYTES // 2
        if tamanho + chegando <= TETO_DO_DIARIO_BYTES or corte <= 0:
            return
        arquivo.seek(corte)
        resto = arquivo.read()
        quebra = resto.find(b"\n")
        arquivo.seek(0)
        arquivo.write(resto[quebra + 1:] if quebra >= 0 else b"")
        arquivo.truncate()


class _AHoraDeCadaLinha:
    """Põe ``AAAA-MM-DD HH:MM:SS`` no começo de cada linha.

    A data vai em toda linha: com a data só na primeira e na troca do dia, a poda do teto levava a
    linha da data, e o resto do diário ficava sem dia (medido em 28/10/2026).
    Só a linha inteira sai; o pedaço sem quebra espera a quebra, até ``teto`` bytes ou o fim.
    As linhas de um mesmo pedaço do cano chegaram juntas e levam a mesma hora, lida uma vez.
    """

    def __init__(self, relogio: Callable[[], time.struct_time], teto: int) -> None:
        self.relogio = relogio
        self.teto = teto
        self.no_meio = False
        self.resto = b""

    def carimbo(self) -> bytes:
        return time.strftime("%Y-%m-%d %H:%M:%S ", self.relogio()).encode()

    def _carimbos(self) -> tuple[bytes, bytes]:
        carimbo = self.carimbo()
        return carimbo, carimbo

    def marcar(self, pedaco: bytes, *, fim: bool = False) -> bytes:
        dados = self.resto + pedaco
        corte = dados.rfind(b"\n") + 1
        if fim or len(dados) - corte > self.teto:
            corte = len(dados)
        dados, self.resto = dados[:corte], dados[corte:]
        saida = b""
        if dados:
            inteira = dados.endswith(b"\n")
            miolo = dados[:-1] if inteira else dados
            primeiro, hora = (self._carimbos() if b"\n" in miolo or not self.no_meio
                              else (b"", b""))
            saida = ((b"" if self.no_meio else primeiro) + miolo.replace(b"\n", b"\n" + hora)
                     + (b"\n" if inteira else b""))
            self.no_meio = not inteira
        if fim and self.no_meio:
            self.no_meio = False
            saida += b"\n"
        return saida


_TRAVAS_DOS_DIARIOS: dict[str, threading.Lock] = {}


def _mudar_o_diario_velho(velho: Path, diario: Path) -> None:
    """O diário da pasta que a caixa escreve vem para a do supervisor, uma vez.

    Vem o conteúdo, até o teto, pelo descritor: o link e o FIFO se recusam ao abrir, e o inode que
    a caixa conheceu fica para trás.
    """
    if os.path.lexists(diario):
        return
    with contextlib.suppress(FileNotFoundError, FileExistsError):
        with _abrir_o_diario(velho, "rb") as antigo:
            antigo.seek(max(0, antigo.seek(0, os.SEEK_END) - TETO_DO_DIARIO_BYTES))
            conteudo = antigo.read(TETO_DO_DIARIO_BYTES)
        with _abrir_o_diario(diario, "xb") as novo:
            novo.write(conteudo)
        velho.unlink()


def _preparar_na_vez_do_arquivo(velho: Path, diario: Path, prazo: float) -> None:
    """A mudança e a poda da abertura, nunca junto com o escritor que sobrou da abertura anterior.

    Passado o ``prazo`` sem a vez, pula: o escritor poda a cada gravação. A recusa fica no registro
    e não segura a abertura.
    """
    trava = _TRAVAS_DOS_DIARIOS.setdefault(str(diario), threading.Lock())
    if not trava.acquire(timeout=prazo):
        logger.warning("mods_diario_sem_a_vez", diario=str(diario))
        return
    try:
        diario.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        _mudar_o_diario_velho(velho, diario)
        _aparar_o_diario(diario)
    except OSError as exc:
        logger.warning("mods_diario_recusado", diario=str(diario), err=str(exc))
    finally:
        trava.release()


async def _preparar_com_teto(velho: Path, diario: Path, prazo: float) -> None:
    """:func:`_preparar_na_vez_do_arquivo` num fio próprio, com a espera até ``prazo``.

    Fora do executor padrão: um disco preso seguraria aquele fio e, com ele, a saída do serviço.
    """
    laco = asyncio.get_running_loop()
    feito = asyncio.Event()

    def preparar() -> None:
        try:
            _preparar_na_vez_do_arquivo(velho, diario, prazo)
        finally:
            with contextlib.suppress(RuntimeError):
                laco.call_soon_threadsafe(feito.set)

    threading.Thread(target=preparar, name=f"mods-preparo-{diario.parent.name}",
                     daemon=True).start()
    with contextlib.suppress(asyncio.TimeoutError):
        await asyncio.wait_for(feito.wait(), prazo)


class _EscritorDoDiario:
    """O fio que grava o diário de uma extensão, atrás de uma fila com teto em bytes.

    O laço só enfileira: nem ``stat``, nem ``open``, nem ``write``. O teto da fila é o maior
    pedaço do diário, para a poda nunca levar junto a conta: acima dele sai a linha mais velha,
    e o diário diz quantas saíram, no ponto em que saíram. A trava é do arquivo: o escritor da
    abertura anterior pode ainda estar no disco quando a extensão reabre.
    """

    def __init__(self, caminho: Path, pedaco_max: int, hora: _AHoraDeCadaLinha,
                 ao_terminar: Callable[[], None]) -> None:
        self.caminho = caminho
        self.pedaco_max = pedaco_max
        self.hora = hora
        self.ao_terminar = ao_terminar
        self._vez = threading.Condition()
        self._linhas: deque[bytes] = deque()
        self._na_fila = 0
        self._perdidas = 0
        self._fechou = False
        self._recusou = False
        self._trava = _TRAVAS_DOS_DIARIOS.setdefault(str(caminho), threading.Lock())
        threading.Thread(target=self._rodar, name=f"mods-diario-{caminho.parent.name}",
                         daemon=True).start()

    def por(self, dados: bytes) -> None:
        """Enfileira sem tocar no disco. Nunca espera: o cano não para."""
        with self._vez:
            for linha in BytesIO(dados):
                self._linhas.append(linha)
                self._na_fila += len(linha)
            while self._na_fila > self.pedaco_max and len(self._linhas) > 1:
                self._na_fila -= len(self._linhas.popleft())
                self._perdidas += 1
            self._vez.notify()

    def fechar(self) -> None:
        """Não entra mais nada: o fio escoa o que está na fila e sai."""
        with self._vez:
            self._fechou = True
            self._vez.notify()

    def _gravar(self, dados: bytes) -> None:
        with self._trava:
            for inicio in range(0, len(dados), self.pedaco_max):
                parte = dados[inicio:inicio + self.pedaco_max]
                try:
                    _aparar_o_diario(self.caminho, len(parte))
                    with _abrir_o_diario(self.caminho, "ab") as diario:
                        diario.write(parte)
                except OSError as exc:
                    if not self._recusou:
                        logger.warning("mods_diario_recusado", diario=str(self.caminho),
                                       err=str(exc))
                    self._recusou = True

    def _a_linha_das_perdidas(self, perdidas: int) -> bytes:
        if not perdidas:
            return b""
        frase = "1 linha saiu" if perdidas == 1 else f"{perdidas} linhas saíram"
        return self.hora.carimbo() + f"({frase}: o disco não acompanhou)\n".encode()

    def _rodar(self) -> None:
        try:
            while True:
                with self._vez:
                    while not self._linhas and not self._fechou:
                        self._vez.wait()
                    if not self._linhas:
                        return
                    dados = b"".join(self._linhas)
                    perdidas, self._perdidas = self._perdidas, 0
                    self._linhas.clear()
                    self._na_fila = 0
                self._gravar(self._a_linha_das_perdidas(perdidas) + dados)
        finally:
            with contextlib.suppress(RuntimeError):
                self.ao_terminar()


async def _copiar_para_o_diario(
    leitor: asyncio.StreamReader,
    caminho: Path,
    *,
    relogio: Callable[[], time.struct_time] = time.localtime,
    ao_abrir: Callable[[_EscritorDoDiario], None] | None = None,
) -> None:
    """A saída e o erro do processo vão para o diário com a hora de cada linha, sem passar do teto.

    O cano é lido até o fim, e o disco fica no :class:`_EscritorDoDiario`: um cano parado trava
    o processo no ``print`` seguinte, e a recusa do disco vai ao log uma vez. O pedaço sem quebra
    que sobra entra quando o cano fecha, ou quando a cópia é cancelada. Nos dois casos a cópia
    espera o escritor escoar a fila, até :data:`ESPERA_DO_DIARIO_S`.
    """
    pedaco_max = max(1, TETO_DO_DIARIO_BYTES // 4)
    hora = _AHoraDeCadaLinha(relogio, pedaco_max)
    laco = asyncio.get_running_loop()
    escoou = asyncio.Event()

    def ao_terminar() -> None:
        laco.call_soon_threadsafe(escoou.set)

    escritor = _EscritorDoDiario(caminho, pedaco_max, hora, ao_terminar)
    if ao_abrir is not None:
        ao_abrir(escritor)
    try:
        while pedaco := await leitor.read(pedaco_max):
            escritor.por(hora.marcar(pedaco))
    finally:
        escritor.por(hora.marcar(b"", fim=True))
        escritor.fechar()
        with contextlib.suppress(asyncio.TimeoutError):
            await asyncio.wait_for(escoou.wait(), ESPERA_DO_DIARIO_S)


async def _esvaziar_a_copia(copia: asyncio.Task[None] | None, prazo: float) -> None:
    """Espera a cópia ler o que sobrou no cano e escoar a fila.

    Quem segura o cano além do prazo perde a cópia; o disco preso além do prazo perde a espera, e
    o escritor segue sozinho até esvaziar a fila.
    """
    if copia is None:
        return
    await asyncio.wait({copia}, timeout=prazo)
    if not copia.done():
        copia.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await copia
    elif not copia.cancelled() and (erro := copia.exception()) is not None:
        logger.warning("mods_diario_falhou", err=str(erro))


CHAVE_DOS_APELIDOS = "mods-apelidos.chave"


def _uniqs_de_agora(controles: Callable[[], Any] | None,
                    uniq_do_posto: Callable[[], str | None]) -> list[str]:
    """Os ``uniq`` dos controles ligados agora, para achar o apelido guardado pela extensão."""
    brutos = controles() if controles is not None else []
    uniqs = [c["uniq"] for c in brutos if isinstance(c, dict) and isinstance(c.get("uniq"), str)]
    posto = uniq_do_posto()
    return [*uniqs, *([posto] if isinstance(posto, str) and posto else [])]


def comando_na_caixa(
    *,
    bwrap: str,
    comando: list[str],
    codigo: Path,
    dados: Path,
    porta: Path,
    manifesto: Manifesto,
    casa: Path,
    da_pessoa: Path | None = None,
    execucao: tuple[Path, ...],
    jogos: tuple[Path, ...] = (),
    pasta: str | None = None,
    ocupada: Callable[[int, bool], bool] | None = None,
    aparelhos: tuple[str, ...] = (),
    pela_porta: tuple[str, ...] = (),
    retrato: RetratoDosHubs | None = None,
    hid: dict[str, str] | None = None,
    bluez: str | None = None,
) -> list[str]:
    """A linha do ``bwrap`` para ``comando``; com rede e com o ``pasta``, dentro dele.

    Entra só :data:`ENTRAM_NA_CAIXA`, com :data:`COBERTOS_NA_CAIXA` vazios; ``/var``, ``/sys``, a
    ``HOME`` e a execução nascem vazios; o ``/dev`` traz só os ``aparelhos``, o ``/sys`` só eles e
    os ``pela_porta`` (``retrato`` recebe os hubs vivos), o :data:`PASTA_DO_HID` só o ``hid``. O
    ``--unshare-pid`` leva junto TUDO o que a modificação abriu; dentro do ``pasta`` o ``bwrap``
    devolve o ``uid`` e o ``gid`` de quem roda. O barramento do sistema nunca entra: ``bluez`` é
    o soquete do proxy (:data:`FILTRO_DO_BLUEZ`), montado onde o barramento mora. Só ``dados``
    se escreve; ``da_pessoa``, o que é da pessoa, entra só de leitura.
    """
    entram = ENTRAM_NA_CAIXA
    propria = pasta is not None and manifesto.rede != "nenhuma"
    argv = [bwrap]
    if propria:
        argv += ["--unshare-user", "--uid", str(os.getuid()), "--gid", str(os.getgid())]
    if bwrap_fecha_o_userns(bwrap):
        argv += [*([] if propria else ["--unshare-user"]), "--disable-userns"]
    argv += _o_que_entra(entram)
    for coberto in COBERTOS_NA_CAIXA:
        if os.path.isfile(coberto):
            argv += ["--ro-bind", "/dev/null", coberto]
    argv += [
        "--unshare-pid", "--unshare-ipc", "--unshare-uts", "--unshare-cgroup-try",
        "--proc", "/proc",
        *(["--size", str(TAMANHO_DO_TMP_BYTES)] if bwrap_aceita_o_tamanho(bwrap) else []),
        "--tmpfs", "/tmp", "--dir", "/var", "--tmpfs", "/sys",
    ]
    for coberta in (str(casa), *map(str, execucao)):
        argv += ["--tmpfs", coberta]
    argv += ["--dev", "/dev"]
    if "aparelhos" in manifesto.permissoes:
        nos = [no for no in aparelhos if no.startswith(NOS_QUE_A_CAIXA_ACEITA) and ".." not in no]
        for no in nos:
            argv += ["--dev-bind-try", no, no]
        argv += _o_sys_dos_aparelhos(
            [*nos, *(no for no in pela_porta
                     if no.startswith(NOS_QUE_A_CAIXA_ACEITA) and ".." not in no)], retrato)
    for caminho in _devolvidos(manifesto, entram):
        argv += ["--ro-bind", caminho, caminho]
    if bluez is not None:
        argv += ["--bind", bluez, SOQUETE_DO_SISTEMA_NA_CAIXA]
    if PASTA_DO_HID in _sinteticas(manifesto):
        argv += a_pasta_do_hid(hid_da_caixa(manifesto, ()) if hid is None else hid)
    comando = _executavel_a_vista(comando, entram, argv)
    argv += [
        "--ro-bind", str(codigo), str(codigo),
        "--bind", str(dados), str(dados),
        *(["--ro-bind", str(da_pessoa), str(da_pessoa)] if da_pessoa is not None else []),
        "--ro-bind", str(porta), str(porta),
    ]
    if "jogos" in manifesto.permissoes:
        argv += [arg for p in jogos for arg in ("--ro-bind", str(p), str(p))]
    if manifesto.rede == "nenhuma":
        argv.append("--unshare-net")
    argv += ["--die-with-parent", "--new-session", "--chdir", str(codigo), "--", *comando]
    if propria:
        assert pasta is not None
        so_a_casa = linha_da_rede_da_casa() if manifesto.rede == "local" else []
        return [*linha_do_pasta(pasta, manifesto, ocupada or ocupada_na_casa), "--", *so_a_casa,
                *argv]
    return argv


def _ler(arquivo: Path) -> str:
    try:
        return arquivo.read_text(encoding="ascii", errors="replace").strip()
    except OSError:
        return ""


def _vid_pid_do_usb(dispositivo: Path) -> tuple[str, str] | None:
    """O ``idVendor``/``idProduct`` do aparelho USB acima de ``dispositivo`` no ``/sys``."""
    atual = Path(os.path.realpath(dispositivo))
    for pasta in (atual, *atual.parents):
        vid, pid = _ler(pasta / "idVendor"), _ler(pasta / "idProduct")
        if vid and pid:
            return vid.lower(), pid.lower()
    return None


def _vid_pid_do_hid(dispositivo: Path) -> tuple[str, str] | None:
    """O ``HID_ID`` do ``uevent`` (``0003:00001A86:0000E429``): vale no USB e no Bluetooth."""
    for linha in _ler(dispositivo / "uevent").splitlines():
        if linha.startswith("HID_ID="):
            partes = linha.split("=", 1)[1].split(":")
            if len(partes) == 3:
                return partes[1][-4:].lower(), partes[2][-4:].lower()
    return None


_Achado = tuple[tuple[str, str] | None, str, Path]


def _nos_de_classe(onde: str, ler: Callable[[Path], tuple[str, str] | None]
                   ) -> Callable[[Path], list[_Achado]]:
    def nos(sys_raiz: Path) -> list[_Achado]:
        with contextlib.suppress(OSError):
            return [(ler(no / "device"), f"/dev/{no.name}", no)
                    for no in sorted((sys_raiz / onde).iterdir())]
        return []
    return nos


def _nos_do_usb(sys_raiz: Path) -> list[_Achado]:
    fora: list[_Achado] = []
    with contextlib.suppress(OSError):
        for usb in sorted((sys_raiz / "bus/usb/devices").iterdir()):
            barramento, numero = _ler(usb / "busnum"), _ler(usb / "devnum")
            if barramento.isdigit() and numero.isdigit():
                ids = (_ler(usb / "idVendor").lower(), _ler(usb / "idProduct").lower())
                fora.append((ids, f"/dev/bus/usb/{int(barramento):03d}/{int(numero):03d}", usb))
    return fora


_NOS_POR_CLASSE: dict[str, Callable[[Path], list[_Achado]]] = {
    "hidraw": _nos_de_classe("class/hidraw", _vid_pid_do_hid),
    "tty": _nos_de_classe("class/tty", _vid_pid_do_usb),
    "usb": _nos_do_usb,
}


CLASSES_PELA_PORTA: tuple[str, ...] = ("hidraw", "tty")

USOS_QUE_NUNCA_SAEM: frozenset[tuple[int, int]] = frozenset(
    (0x01, uso) for uso in (0x01, 0x02, 0x04, 0x05, 0x06, 0x07))

CLASSE_HID_DO_USB = "03"


def colecoes_de_aplicacao(descritor: bytes) -> set[tuple[int, int]]:
    """As coleções de aplicação de primeiro nível do descritor HID, como ``(página, uso)``."""
    pagina = uso = fundo = i = 0
    achadas: set[tuple[int, int]] = set()
    while i < len(descritor):
        prefixo = descritor[i]
        if prefixo == 0xFE:
            i += 3 + (descritor[i + 1] if i + 1 < len(descritor) else 0)
            continue
        tamanho = (0, 1, 2, 4)[prefixo & 0x03]
        dado = int.from_bytes(descritor[i + 1:i + 1 + tamanho], "little")
        etiqueta = prefixo & 0xFC
        if etiqueta == 0x04:
            pagina = dado
        elif etiqueta == 0x08:
            uso = dado
        elif etiqueta == 0xA0:
            if fundo == 0 and dado == 0x01:
                achadas.add((uso >> 16, uso & 0xFFFF) if tamanho == 4 else (pagina, uso))
            fundo += 1
        elif etiqueta == 0xC0:
            fundo = max(0, fundo - 1)
        if etiqueta in (0x80, 0x90, 0xA0, 0xB0, 0xC0):
            uso = 0
        i += 1 + tamanho
    return achadas


def _hidraw_de_gente(onde: Path) -> bool:
    try:
        descritor = (onde / "device" / "report_descriptor").read_bytes()
    except OSError:
        return True
    return bool(colecoes_de_aplicacao(descritor) & USOS_QUE_NUNCA_SAEM)


def _usb_de_gente(onde: Path) -> bool:
    with contextlib.suppress(OSError):
        return any(_ler(i / "bInterfaceClass") == CLASSE_HID_DO_USB
                   for i in onde.iterdir() if (i / "bInterfaceClass").is_file())
    return True


_DE_GENTE_POR_CLASSE: dict[str, Callable[[Path], bool]] = {
    "hidraw": _hidraw_de_gente,
    "usb": _usb_de_gente,
}


def _e_entrada_de_gente(classe: str, onde: Path) -> bool:
    """O nó é de um teclado, de um mouse ou de um controle: nenhuma extensão o abre.

    O ``hidraw`` se lê pelo descritor (o que não se lê recusa); o ``usb`` cru, por qualquer
    interface HID; o ``tty`` é só a serial.
    """
    ler = _DE_GENTE_POR_CLASSE.get(classe)
    return ler is not None and ler(onde)


def _casam(manifesto: Manifesto, aceitos: Collection[str], sys_raiz: Path, *,
           so_os_da_caixa: bool, classes: tuple[str, ...] = tuple(_NOS_POR_CLASSE),
           so_pela_porta: bool = False) -> dict[str, Path]:
    if "aparelhos" not in manifesto.permissoes:
        return {}
    pedidos = {(a.classe, a.vid, a.pid) for a in manifesto.aparelhos
               if not (so_os_da_caixa and a.pela_porta)
               and not (so_pela_porta and not a.pela_porta)
               and f"{a.classe}:{a.vid}:{a.pid}" in aceitos}
    nos: dict[str, Path] = {}
    for classe, achar in _NOS_POR_CLASSE.items():
        if classe in classes and any(p[0] == classe for p in pedidos):
            for ids, no, onde in achar(sys_raiz):
                if ids and (classe, *ids) in pedidos and not _e_entrada_de_gente(classe, onde):
                    nos.setdefault(no, onde)
    return nos


def aparelhos_que_casam(manifesto: Manifesto, aceitos: Collection[str],
                        sys_raiz: Path = Path("/sys")) -> tuple[str, ...]:
    """Os nós de ``/dev`` dos aparelhos declarados e aceitos que estão ligados agora e entram na
    caixa.

    Só ``hidraw``, ``tty`` e ``usb``: o ``uinput``, o ``uhid`` e o ``input/`` nunca entram, nem o
    teclado, o mouse e o controle (:func:`_e_entrada_de_gente`). ``aceitos`` são os
    ``classe:vid:pid`` que tiveram o «sim» (o registro, não o manifesto de agora). O declarado
    ``pela_porta`` também fica fora: a extensão o pede à porta (:func:`abrir_o_aparelho`).
    """
    return tuple(_casam(manifesto, aceitos, sys_raiz, so_os_da_caixa=True))


def nos_pela_porta(manifesto: Manifesto, aceitos: Collection[str],
                   sys_raiz: Path = Path("/sys")) -> dict[str, Path]:
    """Os nós ``hidraw`` e ``tty`` dos aparelhos declarados e aceitos ligados agora, com a pasta
    do ``/sys`` de cada um: só eles saem pela porta, nunca o ``usb`` cru."""
    return _casam(manifesto, aceitos, sys_raiz, so_os_da_caixa=False, classes=CLASSES_PELA_PORTA)


def pastas_pela_porta(manifesto: Manifesto, aceitos: Collection[str],
                      sys_raiz: Path = Path("/sys")) -> dict[str, str]:
    """Os nós dos aparelhos declarados ``pela_porta`` e aceitos ligados agora, com a pasta do
    aparelho de cada um (:func:`_o_aparelho_do_sys`): o nó fica fora da caixa, e o ``/sys`` dele
    entra, para a extensão o achar."""
    casam = _casam(manifesto, aceitos, sys_raiz, so_os_da_caixa=False,
                   classes=CLASSES_PELA_PORTA, so_pela_porta=True)
    return {no: _o_aparelho_do_sys(os.path.realpath(onde))[0] for no, onde in casam.items()}


def abrir_o_aparelho(manifesto: Manifesto, no: Any, aceitos: Collection[str],
                     sys_raiz: Path = Path("/sys"), dev_raiz: Path = Path("/dev")) -> int:
    """Abre, fora da caixa, o nó ``no`` (``hidraw7``) de um aparelho declarado e aceito.

    Só ``hidraw`` e ``tty``, e a classe vem do ``/sys``: o nó tem de estar na pasta da classe,
    com o VID:PID declarado e aceito, neste instante. O que abriu (sem seguir link) tem de ser o
    dispositivo de caractere com o número que o ``/sys`` dá a ele: o nó que renasceu com outro
    aparelho no meio recusa. Levanta ``ValueError`` com a frase da recusa.
    """
    if not isinstance(no, str) or not no or "/" in no or no in (".", ".."):
        raise ValueError("aparelho.abrir: o no é o nome do nó, como hidraw7")
    onde = nos_pela_porta(manifesto, aceitos, sys_raiz).get(f"/dev/{no}")
    if onde is None:
        raise ValueError(f"aparelho.abrir: {no} não é de um aparelho aceito ligado agora")
    maior, _, menor = _ler(onde / "dev").partition(":")
    if not (maior.isdigit() and menor.isdigit()):
        raise ValueError(f"aparelho.abrir: o /sys não diz o número de {no}")
    try:
        return abrir_o_no_sem_seguir(dev_raiz / no, os.makedev(int(maior), int(menor)))
    except OSError as exc:
        if exc.errno != errno.ENXIO:
            raise
        raise ValueError(f"aparelho.abrir: {no} mudou de aparelho no meio da abertura") from exc


def nome_no_sys(classe: str, vid: str, pid: str, sys_raiz: Path = Path("/sys"), *,
                ler_o_usb: bool = False) -> str:
    """O nome que o aparelho ligado agora dá a si mesmo; vazio desligado.

    O ``hidraw`` diz o ``HID_NAME`` do ``uevent``, que não toma a trava do USB. O ``product`` do
    USB toma (``usb_lock_device``) e pode esperar a enumeração: só com ``ler_o_usb``, fora da
    janela.
    """
    for ids, _no, onde in _NOS_POR_CLASSE[classe](sys_raiz):
        if ids != (vid, pid):
            continue
        if classe == "hidraw":
            for linha in _ler(onde / "device" / "uevent").splitlines():
                if linha.startswith("HID_NAME="):
                    return linha.split("=", 1)[1].strip()[:80]
        elif ler_o_usb:
            atual = Path(os.path.realpath(onde / "device"))
            for pasta in (atual, *atual.parents):
                if (pasta / "idVendor").is_file():
                    return _ler(pasta / "product")[:80]
    return ""


def frase_do_pedido(palavra: str, manifesto: Manifesto, sys_raiz: Path = Path("/sys"), *,
                    ler_o_usb: bool = False) -> str:
    """A linha do «sim» de ``palavra`` (de :func:`pedidos_do_sim`).

    O aparelho diz o rótulo do autor e, ao lado, o que o autor não escolhe: a classe, o VID:PID
    e, ligado agora, o nome que o próprio aparelho dá.
    """
    classe, _, vid_pid = palavra.removeprefix("aparelho:").partition(":")
    vid, _, pid = vid_pid.partition(":")
    declarado = next((a for a in manifesto.aparelhos
                      if (a.classe, a.vid, a.pid) == (classe, vid, pid)), None)
    if not palavra.startswith("aparelho:") or declarado is None:
        return o_que_a_permissao_deixa(palavra)
    nome = nome_no_sys(classe, vid, pid, sys_raiz, ler_o_usb=ler_o_usb)
    ligado = f", ligado agora: «{nome}»" if nome else ""
    return f"Abrir «{declarado.nome}» ({classe} {vid}:{pid}{ligado})."


def frase_dos_aparelhos(manifesto: Manifesto, sys_raiz: Path = Path("/sys"), *,
                        ler_o_usb: bool = True) -> str:
    """Os aparelhos que a caixa abre, com a classe e o VID:PID ao lado do rótulo; sem a
    permissão, nada."""
    if "aparelhos" not in manifesto.permissoes:
        return ""
    linhas = [frase_do_pedido(p, manifesto, sys_raiz, ler_o_usb=ler_o_usb).removeprefix(
        "Abrir ").removesuffix(".") for p in pedidos_do_sim(manifesto) if p.startswith("aparelho:")]
    if not linhas:
        return "A extensão não abre aparelho nenhum: o manifesto não declara qual."
    return f"Dos aparelhos ligados ao computador, a extensão abre só: {'; '.join(linhas)}."


def rede_propria_da_caixa() -> str | None:
    """O ``pasta``, que dá à caixa com rede um espaço de rede próprio; ``None`` sem ele."""
    return shutil.which("pasta")


def ocupada_na_casa(porta: int, udp: bool) -> bool:
    """Outro programa já escuta em ``127.0.0.1:porta`` da casa.

    O ``pasta`` não abre com uma ponte ocupada, e a extensão inteira ficaria fechada: a porta
    ocupada fica de fora, como ficava quando a própria extensão a abria no espaço da casa.
    """
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM if udp else socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            s.bind(("127.0.0.1", porta))
        except OSError:
            return True
    return False


def linha_do_pasta(pasta: str, manifesto: Manifesto,
                   ocupada: Callable[[int, bool], bool]) -> list[str]:
    """O ``pasta`` com as ``portas`` do manifesto e nenhuma outra.

    ``-T``/``-U`` levam a porta do ``127.0.0.1`` da caixa à da casa (``da_casa``); ``-t``/``-u``
    trazem a do ``127.0.0.1`` da casa, e só dele, à da caixa (``para_a_casa``). O que não se
    declara fica em ``none``: o padrão do ``pasta`` encaminha toda porta que se escuta, e o
    ``--no-map-gw`` tira o caminho do gateway até o loopback da casa.
    """
    portas = manifesto.portas
    da_casa = portas.da_casa if portas else []
    para_a_casa = [p for p in (portas.para_a_casa if portas else []) if not ocupada(p.porta, p.udp)]
    linha = [pasta, *PASTA_DA_CAIXA]
    for opcao, lista, udp, endereco in (("-t", para_a_casa, False, "127.0.0.1/"),
                                        ("-u", para_a_casa, True, "127.0.0.1/"),
                                        ("-T", da_casa, False, ""),
                                        ("-U", da_casa, True, "")):
        numeros = [f"{endereco}{p.porta}" for p in lista if p.udp == udp]
        linha += [arg for n in numeros for arg in (opcao, n)] or [opcao, "none"]
    return linha


FAIXAS_DA_CASA = {
    "4": ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16", "169.254.0.0/16"),
    "6": ("fc00::/7", "fe80::/10"),
}

SO_A_REDE_DA_CASA = (
    'if ! command -v ip >/dev/null 2>&1; then\n'
    '  echo "rede:local pede o ip (iproute2); a extensão não liga." >&2; exit 1\n'
    'fi\n'
    'for v in 4 6; do\n'
    '  gw=; dev=; antes=\n'
    '  set -f\n'
    '  for palavra in $(ip -"$v" route show default 2>/dev/null | head -n 1); do\n'
    '    case "$antes" in via) gw=$palavra ;; dev) dev=$palavra ;; esac\n'
    '    antes=$palavra\n'
    '  done\n'
    '  set +f\n'
    '  ip -"$v" route flush table main 2>/dev/null || :\n'
    '  if ip -"$v" route show table main 2>/dev/null | grep -q .; then\n'
    '    echo "rede:local: as rotas de fora não saíram; a extensão não liga." >&2; exit 1\n'
    '  fi\n'
    '  [ -n "$gw" ] && [ -n "$dev" ] || continue\n'
    '  if [ "$v" = 4 ]; then faixas="' + " ".join(FAIXAS_DA_CASA["4"]) + '"; '
    'else faixas="' + " ".join(FAIXAS_DA_CASA["6"]) + '"; fi\n'
    '  for faixa in $faixas; do\n'
    '    ip -"$v" route add "$faixa" via "$gw" dev "$dev" onlink || exit 1\n'
    '  done\n'
    'done\n'
    'exec "$@"\n'
)


def linha_da_rede_da_casa() -> list[str]:
    """O que roda entre o ``pasta`` e o ``bwrap`` na caixa com ``rede:local``: tira toda rota do
    espaço de rede da caixa e põe de volta só as :data:`FAIXAS_DA_CASA` (privadas e link-local),
    pelo gateway que o ``pasta`` deu; sem ``ip``, ou com rota que não sai, a extensão não liga.
    O ``bwrap`` abre depois, num espaço de usuário sem poder sobre a rede."""
    return ["sh", "-c", SO_A_REDE_DA_CASA, "rede-da-casa"]


A_REDE_INCLUI_A_MAQUINA = (
    "A rede da extensão inclui a internet e os serviços desta máquina, "
    "inclusive o controle pelo protocolo do DSX.")

A_REDE_INCLUI_A_INTERNET = "A rede da extensão inclui a internet."


def frase_da_ponte_calada(porta: int) -> str:
    """A linha do diário para a ponte declarada em que a extensão não ouve, no ``pasta`` bom."""
    return (f"A ponte {porta} não atende: a extensão não ouve nessa porta, e os programas desta "
            f"máquina não a alcançam.")


_O_OUVINTE_DA_SONDA = (
    "import socket, sys\n"
    "s = socket.socket()\n"
    "s.bind(('127.0.0.1', int(sys.argv[1])))\n"
    "s.listen(1)\n"
    "s.settimeout(float(sys.argv[2]))\n"
    "print('ouvindo', flush=True)\n"
    "c, _ = s.accept()\n"
    "c.sendall(b'1')\n"
    "c.close()\n"
)

_SONDAS: dict[tuple[str, int, int], bool] = {}

_VEZ_DA_SONDA = threading.Lock()


def _a_chave_do_pasta(pasta: str) -> tuple[str, int, int] | None:
    real = os.path.realpath(pasta)
    if not os.path.isfile(real):
        return None
    visto = os.stat(real)
    return real, visto.st_mtime_ns, visto.st_size


def _sondas_guardadas(caminho: Path) -> dict[str, bool]:
    try:
        bruto = json.loads(caminho.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    if not isinstance(bruto, dict):
        return {}
    return {k: v for k, v in bruto.items() if isinstance(k, str) and isinstance(v, bool)}


def _guardar_as_sondas(caminho: Path, sondas: dict[str, bool]) -> None:
    try:
        caminho.parent.mkdir(parents=True, exist_ok=True)
        temporario = caminho.with_name(f".{caminho.name}.{os.getpid()}")
        temporario.write_text(json.dumps(sondas, ensure_ascii=False), encoding="utf-8")
        os.replace(temporario, caminho)
    except OSError as exc:
        logger.warning("mods_sonda_nao_gravou", err=str(exc))


def _porta_livre_da_casa() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as livre:
        livre.bind(("127.0.0.1", 0))
        return int(livre.getsockname()[1])


def sondar_o_pasta(pasta: str, prazo: float = PRAZO_DA_SONDA_S) -> bool:
    """O ``pasta`` entrega o ``-t``? Um ouvinte do supervisor, sem extensão nenhuma, responde um
    byte no ``127.0.0.1`` de dentro, e a casa liga no próprio ``127.0.0.1``."""
    porta = _porta_livre_da_casa()
    argv = [pasta, *PASTA_DA_CAIXA, "-t", f"127.0.0.1/{porta}", "-u", "none", "-T", "none",
            "-U", "none", "--", sys.executable, "-I", "-c", _O_OUVINTE_DA_SONDA, str(porta),
            str(prazo)]
    fim = time.monotonic() + prazo
    try:
        filho = subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                 stderr=subprocess.DEVNULL, start_new_session=True)
    except OSError:
        return False
    try:
        assert filho.stdout is not None
        prontos = prontos_para_ler([filho.stdout], prazo)
        if not prontos or filho.stdout.readline().strip() != b"ouvindo":
            return False
        resta = max(PASSO_DA_PONTE_S, fim - time.monotonic())
        with socket.create_connection(("127.0.0.1", porta), timeout=resta) as casa:
            return casa.recv(1) == b"1"
    except OSError:
        return False
    finally:
        with contextlib.suppress(OSError):
            os.killpg(filho.pid, signal.SIGKILL)
        filho.wait()


def o_pasta_entrega_a_ponte(pasta: str) -> bool:
    """A sonda do supervisor, uma vez por binário: guardada pelo caminho real, a hora e o tamanho
    do ``pasta``, na memória e no estado do produto."""
    chave = _a_chave_do_pasta(pasta)
    if chave is None:
        return False
    with _VEZ_DA_SONDA:
        if chave in _SONDAS:
            return _SONDAS[chave]
        caminho = state_dir() / SONDA_DO_PASTA
        guardadas = _sondas_guardadas(caminho)
        nome = "|".join(map(str, chave))
        if nome not in guardadas:
            guardadas[nome] = sondar_o_pasta(chave[0])
            _guardar_as_sondas(caminho, guardadas)
            logger.info("mods_sonda_do_pasta", pasta=chave[0], entrega=guardadas[nome])
        _SONDAS[chave] = guardadas[nome]
        return guardadas[nome]


def pasta_da_caixa(manifesto: Manifesto) -> str | None:
    """O ``pasta`` da caixa com rede, escolhido antes de abrir e igual para toda extensão.

    Com ponte declarada (``para_a_casa``), só o ``pasta`` que a sonda do supervisor provou
    entregar; sem ele, a caixa fica no espaço de rede da casa. O que a extensão faz dentro da
    caixa nunca troca o caminho.
    """
    pasta = rede_propria_da_caixa()
    portas = manifesto.portas
    if pasta is None or manifesto.rede == "nenhuma" or not (portas and portas.para_a_casa):
        return pasta
    return pasta if o_pasta_entrega_a_ponte(pasta) else None


def pontes_que_o_pasta_traz(manifesto: Manifesto,
                            ocupada: Callable[[int, bool], bool]) -> tuple[int, ...]:
    """As pontes TCP (``para_a_casa``) que o ``pasta`` traz: a ocupada na casa fica de fora."""
    portas = manifesto.portas
    if manifesto.rede == "nenhuma" or portas is None:
        return ()
    return tuple(p.porta for p in portas.para_a_casa if not p.udp and not ocupada(p.porta, False))


def _filhos(pid: int) -> list[int]:
    filhos: list[int] = []
    for tarefa in sorted(Path(f"/proc/{pid}/task").glob("*/children")):
        with contextlib.suppress(OSError, ValueError):
            filhos += [int(texto) for texto in tarefa.read_text().split()]
    return filhos


def portas_no_loopback_da_caixa(pid: int) -> dict[int, set[str]]:
    """As portas TCP do ``127.0.0.1`` da caixa, com os estados de cada uma.

    ``pid`` é o do ``pasta``: o filho dele roda no espaço de rede da caixa, e o
    ``/proc/<filho>/net/tcp`` é a tabela desse espaço.
    """
    portas: dict[int, set[str]] = {}
    for filho in _filhos(pid)[:1]:
        with contextlib.suppress(OSError):
            for linha in Path(f"/proc/{filho}/net/tcp").read_text().splitlines()[1:]:
                campos = linha.split()
                endereco, _, porta = campos[1].partition(":") if len(campos) > 3 else ("", "", "")
                if endereco in _LOOPBACK_DA_CAIXA:
                    portas.setdefault(int(porta, 16), set()).add(campos[3])
    return portas


async def as_pontes_caladas(
    pid: int, pontes: Sequence[int],
    ler: Callable[[int], dict[int, set[str]]] = portas_no_loopback_da_caixa,
) -> list[int]:
    """As pontes em que a extensão não ouve no prazo; a extensão segue na caixa mesmo assim."""
    fim = time.monotonic() + PRAZO_PARA_A_PONTE_OUVIR_S
    caladas = list(pontes)
    while caladas and time.monotonic() < fim:
        caladas = [p for p in caladas if _OUVINDO not in ler(pid).get(p, set())]
        if caladas:
            await asyncio.sleep(PASSO_DA_PONTE_S)
    return caladas


def _as_portas_pelo_nome(lista: Sequence[Any]) -> str:
    nomes: dict[str, list[str]] = {}
    for p in lista:
        nomes.setdefault(p.nome, []).append(f"{p.porta}{'/udp' if p.udp else ''}")
    return "; ".join(f"{nome} ({', '.join(numeros)})" for nome, numeros in nomes.items())


def frase_da_rede(manifesto: Manifesto) -> str:
    """O que a rede do «sim» abre de fato.

    Com o ``pasta``, a internet (só no ``rede:internet``: o ``rede:local`` alcança as
    :data:`FAIXAS_DA_CASA`) e, do ``127.0.0.1`` da casa, só as ``portas`` declaradas, pelo nome
    de cada uma. Sem ele, a caixa fica no espaço de rede da casa, e a frase diz que a rede
    inclui os serviços desta máquina: um espaço próprio sem as portas tirava das extensões a ponte
    que o jogo alcança e o app que a pessoa abriu na máquina (medido em 14/11/2026).
    """
    if manifesto.rede == "nenhuma":
        return ""
    if pasta_da_caixa(manifesto) is None:
        return A_REDE_INCLUI_A_MAQUINA
    frase = [A_REDE_INCLUI_A_INTERNET] if manifesto.rede == "internet" else []
    portas = manifesto.portas
    if portas and portas.da_casa:
        frase.append(f"Desta máquina, a extensão alcança só: "
                     f"{_as_portas_pelo_nome(portas.da_casa)}.")
    if portas and portas.para_a_casa:
        frase.append(f"Os programas desta máquina alcançam: "
                     f"{_as_portas_pelo_nome(portas.para_a_casa)}.")
    return " ".join(frase)


def _o_que_entra(entram: Sequence[str]) -> list[str]:
    """As raízes que existem entram como estão; a que é link entra como link, e só quando o
    alvo resolvido mora numa raiz que entra de verdade."""
    reais = [p for p in entram if os.path.isdir(p) and not os.path.islink(p)]
    argv: list[str] = []
    for raiz in reais:
        argv += ["--ro-bind", raiz, raiz]
    for raiz in entram:
        if os.path.islink(raiz) and _sob(os.path.realpath(raiz), reais):
            argv += ["--symlink", os.readlink(raiz), raiz]
    return argv


def _o_aparelho_do_sys(real: str) -> tuple[str, bool]:
    """A pasta do aparelho dono de ``real`` (a pasta de um nó no ``/sys``) e se o aparelho é USB:
    o aparelho USB inteiro; fora do USB (o HID do rádio), a pasta dona da classe do nó, e nunca um
    balde inteiro de ``/sys/devices`` (o ``/dev/null`` traz só a pasta dele)."""
    pasta = real
    while pasta not in ("/sys/devices", os.path.dirname(pasta)):
        if os.path.isfile(os.path.join(pasta, "idVendor")):
            return pasta, True
        pasta = os.path.dirname(pasta)
    dono = os.path.dirname(os.path.dirname(real))
    balde = os.path.dirname(dono) in ("/sys", "/sys/devices", "/sys/devices/virtual")
    return (real if balde else dono), False


_NOME_DO_USB = re.compile(r"\d+-\d+(?:\.\d+)*")


def _aparelhos_do_hub(hub: str) -> dict[str, int]:
    """Os aparelhos USB filhos de ``hub``, com o ``inode`` que a listagem dá: pelo nome que o
    kernel dá (``3-1.4``) ou pelo ``idVendor``, também o que ainda nasce; nunca a interface
    (``3-1:1.0``) nem um link. Levanta ``OSError`` quando o hub saiu."""
    with os.scandir(hub) as filhos:
        return {f.path: f.inode() for f in sorted(filhos, key=lambda f: f.name)
                if not f.is_symlink() and (_NOME_DO_USB.fullmatch(f.name)
                                           or os.path.isfile(os.path.join(f.path, "idVendor")))}


def _ids_do_usb(pasta: str) -> tuple[str, str]:
    return (_ler(Path(pasta) / "idVendor").lower(), _ler(Path(pasta) / "idProduct").lower())


def _filhos_do_hub_vivo(hub: str) -> dict[str, int] | None:
    with contextlib.suppress(OSError):
        return _aparelhos_do_hub(hub)
    return None


def irmaos_a_vista(retrato: RetratoDosHubs) -> tuple[dict[str, int], list[str]]:
    """Os aparelhos USB dos hubs vivos que a caixa não cobre, com o ``inode`` de cada um (o ligado
    depois da abertura e o coberto que saiu e voltou: a montagem sai com o nó que morreu), e os
    hubs que saíram, cuja montagem a caixa perdeu.

    ``retrato`` vem de :func:`_o_sys_dos_achados`: o coberto segue coberto enquanto o ``inode`` é o
    mesmo; o declarado à vista segue aceito enquanto o VID:PID é o mesmo (o ``RESET;`` volta na
    mesma porta), ou enquanto ainda nasce sem ele.
    """
    a_vista: dict[str, int] = {}
    sairam: list[str] = []
    for hub in sorted({os.path.dirname(p) for p in retrato}):
        filhos = _filhos_do_hub_vivo(hub)
        if filhos is None:
            sairam.append(hub)
            continue
        for filho, inode in filhos.items():
            visto = retrato.get(filho)
            aceito = (_ids_do_usb(filho) in (visto, ("", "")) if isinstance(visto, tuple)
                      else visto == inode)
            if not aceito:
                a_vista[filho] = inode
    return a_vista, sairam


def hid_da_caixa(manifesto: Manifesto, aceitos: Collection[str],
                 sys_raiz: Path = Path("/sys")) -> dict[str, str]:
    """Os links que a pasta sintética :data:`PASTA_DO_HID` leva, com o alvo de cada um: com
    ``bluetooth``, os HID do rádio (barramento :data:`BARRAMENTO_DO_RADIO`) e os do VID:PID
    declarado e aceito; nenhum outro nome, nem o do teclado ou do controle pelo cabo."""
    if PASTA_DO_HID not in _sinteticas(manifesto):
        return {}
    declarados = {(a.vid, a.pid) for a in manifesto.aparelhos
                  if "aparelhos" in manifesto.permissoes
                  and f"{a.classe}:{a.vid}:{a.pid}" in aceitos}
    links: dict[str, str] = {}
    with contextlib.suppress(OSError), os.scandir(sys_raiz / "bus" / "hid" / "devices") as itens:
        for item in sorted(itens, key=lambda i: i.name):
            partes = item.name.split(".", 1)[0].split(":")
            if len(partes) != 3:
                continue
            ids = (partes[1][-4:].lower(), partes[2][-4:].lower())
            if partes[0][-4:] == BARRAMENTO_DO_RADIO or ids in declarados:
                with contextlib.suppress(OSError):
                    links[item.name] = os.readlink(item.path)
    return links


def a_pasta_do_hid(hid: dict[str, str]) -> list[str]:
    """A pasta sintética :data:`PASTA_DO_HID` na linha do ``bwrap``, com os links ``hid``."""
    argv = ["--dir", PASTA_DO_HID]
    for nome, alvo in sorted(hid.items()):
        argv += ["--symlink", alvo, f"{PASTA_DO_HID}/{nome}"]
    return argv


def a_caixa_quer_saber(campos: dict[str, str]) -> bool:
    """Um aparelho USB inteiro entrou, ou um HID entrou ou saiu: a vigia confere na hora."""
    acao, sistema = campos.get("ACTION"), campos.get("SUBSYSTEM")
    return ((sistema == "usb" and campos.get("DEVTYPE") == "usb_device" and acao == "add")
            or (sistema == "hid" and acao in ("add", "remove")))


def _os_da_caixa(pid: int, dentro: int) -> list[int]:
    """Os processos que descendem de ``pid`` e moram no espaço de PID de ``dentro``, ou num mais
    fundo: a caixa. O ``bwrap`` de fora e o ``pasta``, cada um no seu espaço, não contam."""
    fundo = len(_campo(dentro, "NSpid"))
    fila, caixa = _filhos(pid), []
    while fila:
        atual = fila.pop(0)
        if len(_campo(atual, "NSpid")) >= fundo:
            caixa.append(atual)
        fila += _filhos(atual)
    return caixa


def a_caixa_escapa(pid: int, dentro: int) -> bool:
    """Algum processo da caixa de ``pid`` mora noutro espaço de montagem que o de ``dentro``: a
    cobertura feita ali não chega nele. É a reserva do ``bwrap`` sem ``--disable-userns``
    (:func:`bwrap_fecha_o_userns`); a caixa que não se lê conta como escape."""
    try:
        montagem = os.readlink(f"/proc/{dentro}/ns/mnt")
    except OSError:
        return True
    for processo in _os_da_caixa(pid, dentro):
        with contextlib.suppress(OSError):
            if os.readlink(f"/proc/{processo}/ns/mnt") != montagem:
                return True
    return False


@functools.lru_cache(maxsize=4)
def bwrap_fecha_o_userns(bwrap: str) -> bool:
    """O ``bwrap`` aceita ``--disable-userns`` (0.8.0 em diante) e não é setuid: a caixa nasce
    sem poder abrir espaço de usuário, e com ele um espaço de montagem que a cobertura por dentro
    não alcança. O setuid fica fora porque nele o ``--unshare-user`` que a opção pede pode
    falhar."""
    try:
        if os.stat(bwrap).st_mode & stat.S_ISUID:
            return False
        ajuda = subprocess.run([bwrap, "--help"], capture_output=True, text=True, check=False)
    except OSError as exc:
        logger.info("mods_bwrap_sem_ajuda", bwrap=bwrap, err=str(exc))
        return False
    return "--disable-userns" in ajuda.stdout + ajuda.stderr


@functools.lru_cache(maxsize=4)
def bwrap_aceita_o_tamanho(bwrap: str) -> bool:
    """O ``bwrap`` aceita ``--size`` antes do ``--tmpfs`` (0.8.0 em diante): o ``/tmp`` da caixa
    nasce com teto. O que não responde à ajuda fica sem a opção, porque uma opção que ele não
    conhece o impediria de abrir."""
    try:
        ajuda = subprocess.run([bwrap, "--help"], capture_output=True, text=True, check=False)
    except OSError as exc:
        logger.info("mods_bwrap_sem_ajuda", bwrap=bwrap, err=str(exc))
        return False
    return "--size BYTES" in ajuda.stdout + ajuda.stderr


async def mudar_por_dentro_da_caixa(pid: int, pedido: dict[str, Any]) -> dict[str, Any] | None:
    """Roda :data:`POR_DENTRO_DA_CAIXA` no espaço de montagem de ``pid`` com ``pedido``; a
    resposta, ou ``None`` quando ele não respondeu no :data:`PRAZO_POR_DENTRO_S`."""
    processo = await asyncio.create_subprocess_exec(
        sys.executable, "-I", "-S", str(POR_DENTRO_DA_CAIXA), str(pid),
        stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.DEVNULL)
    try:
        saida, _ = await asyncio.wait_for(processo.communicate(json.dumps(pedido).encode()),
                                          PRAZO_POR_DENTRO_S)
    except asyncio.TimeoutError:
        processo.kill()
        await processo.wait()
        logger.warning("mods_por_dentro_sem_resposta", pid=pid)
        return None
    try:
        resposta: dict[str, Any] = json.loads(saida)
    except ValueError:
        logger.warning("mods_por_dentro_resposta_torta", pid=pid, saida=saida[-200:])
        return None
    return resposta


def _o_sys_dos_aparelhos(nos: Sequence[str], retrato: RetratoDosHubs | None = None) -> list[str]:
    """Do ``/sys``, só o aparelho de cada nó (:func:`_o_sys_dos_achados`)."""
    achados: list[tuple[str, str]] = []
    for no in dict.fromkeys(nos):
        try:
            numero = os.stat(no).st_rdev
        except OSError as exc:
            logger.info("mods_aparelho_saiu_antes_da_caixa", no=no, err=str(exc))
            continue
        liga = f"/sys/dev/char/{os.major(numero)}:{os.minor(numero)}"
        real = os.path.realpath(liga)
        if real.startswith("/sys/devices/"):
            achados.append((liga, real))
    return _o_sys_dos_achados(achados, retrato)


def _o_sys_dos_achados(achados: Sequence[tuple[str, str]],
                       retrato: RetratoDosHubs | None = None) -> list[str]:
    """O aparelho de cada ``(link, pasta do nó)`` e os links que o acham: o
    ``/sys/dev/char/<maior>:<menor>``, o ``/sys/class/<classe>/<nó>`` e, no USB, o
    ``/sys/bus/usb/devices/<aparelho>``.

    O aparelho USB vem pelo hub dele, vivo, com os outros aparelhos do hub cobertos: o que sai do
    USB e volta na mesma porta (o ``RESET;`` do adaptador) segue à vista da caixa. Fora do USB
    vem a pasta de :func:`_o_aparelho_do_sys`. ``retrato`` recebe, de cada filho dos hubs, o
    ``inode`` do coberto e o VID:PID do que fica à vista: a vigia (:func:`irmaos_a_vista`) reabre
    a caixa quando o hub mostra o que a caixa não cobre.
    """
    donos = [(liga, real, *_o_aparelho_do_sys(real)) for liga, real in achados]
    usb = {pasta for _, _, pasta, e_usb in donos if e_usb}
    argv: list[str] = []
    for hub in sorted({os.path.dirname(p) for p in usb}, key=lambda p: p.count("/")):
        try:
            filhos = _aparelhos_do_hub(hub)
        except OSError as exc:
            logger.info("mods_aparelho_saiu_antes_da_caixa", no=hub, err=str(exc))
            continue
        argv += ["--ro-bind", hub, hub]
        for filho, inode in filhos.items():
            declarado = any(_sob(p, (filho,)) for p in usb)
            if not declarado:
                argv += ["--tmpfs", filho]
            if retrato is not None:
                retrato[filho] = _ids_do_usb(filho) if declarado else inode
    for pasta in dict.fromkeys(p for _, _, p, e_usb in donos if not e_usb):
        argv += ["--ro-bind", pasta, pasta]
    for liga, real, _pasta, _e_usb in donos:
        classe = f"/sys/class/{os.path.basename(os.path.dirname(real))}/{os.path.basename(real)}"
        argv += ["--symlink", real, liga, "--symlink", real, classe]
    for pasta in sorted(usb):
        argv += ["--symlink", pasta, f"/sys/bus/usb/devices/{os.path.basename(pasta)}"]
    return argv


def _sinteticas(manifesto: Manifesto) -> list[str]:
    """As pastas sintéticas que a permissão pede (:data:`SINTETICA_COM_A_PERMISSAO`)."""
    return [pasta for permissao, pasta in SINTETICA_COM_A_PERMISSAO.items()
            if permissao in manifesto.permissoes]


def _devolvidos(manifesto: Manifesto, entram: Sequence[str]) -> list[str]:
    """O que volta do que não entra: o barramento com ``bluetooth``, o DNS com rede."""
    caminhos = [c for permissao, lista in DEVOLVIDO_COM_A_PERMISSAO.items()
                if permissao in manifesto.permissoes for c in lista]
    if manifesto.rede != "nenhuma":
        caminhos += list(DEVOLVIDO_COM_A_REDE)
        resolv = os.path.realpath("/etc/resolv.conf")
        if not _sob(resolv, entram) and not _sob(resolv, DEVOLVIDO_COM_A_REDE):
            caminhos.append(resolv)
    return [c for c in dict.fromkeys(caminhos) if os.path.exists(c)]


def _sob(caminho: str, raizes: Sequence[str]) -> bool:
    return any(caminho == raiz or caminho.startswith(f"{raiz}/") for raiz in raizes)


def _executavel_a_vista(comando: list[str], entram: Sequence[str],
                        argv: list[str]) -> list[str]:
    """O executável fora das raízes que entram (o ``python3`` de um venv) roda pelo alvo real;
    o alvo que também fica fora entra sozinho, ou com a pasta dele no ``/opt``."""
    if not comando or not comando[0].startswith("/") or _sob(comando[0], entram):
        return comando
    real = os.path.realpath(comando[0])
    if _sob(real, (PASTA_DOS_PROGRAMAS,)):
        programa = os.path.relpath(real, PASTA_DOS_PROGRAMAS).split(os.sep)[0]
        pasta = os.path.join(PASTA_DOS_PROGRAMAS, programa)
        argv += ["--ro-bind", pasta, pasta]
    elif not _sob(real, entram):
        argv += ["--ro-bind", real, real]
    return [real, *comando[1:]]


def pastas_dos_jogos(manifesto: Manifesto, casa: Path) -> tuple[Path, ...]:
    """As pastas ``steamapps`` reais de toda biblioteca da casa, só com a permissão ``jogos``."""
    if "jogos" not in manifesto.permissoes:
        return ()
    from hefesto_dualsense4unix.integrations.steam_launch_options import pastas_steamapps

    pastas: list[Path] = []
    for pasta in pastas_steamapps(casa):
        with contextlib.suppress(OSError):
            real = pasta.resolve()
            if real.is_dir() and real not in pastas:
                pastas.append(real)
    return tuple(pastas)


def _execucao_da_sessao(xdg: str | None, porta: Path) -> tuple[Path, ...]:
    """Os diretórios de execução que a caixa esconde.

    A porta mora em ``<execução da sessão>/<produto>/mods.sock``, ao lado do
    socket principal. Sem ``XDG_RUNTIME_DIR`` no ambiente, o ``platformdirs``
    ainda resolve ``/run/user/<uid>``, e não a ``HOME``: o avô da porta é o
    diretório que guarda o socket principal e os da sessão (barramento,
    servidor de som, Wayland), e ele se esconde junto com o ``XDG_RUNTIME_DIR``.
    """
    pastas: list[Path] = []
    for pasta in (Path(xdg) if xdg else None, porta.parent.parent):
        if pasta is not None and pasta != Path(pasta.anchor) and pasta not in pastas:
            pastas.append(pasta)
    return tuple(pastas)


def _resolver_o_comando(codigo: Path, executar: list[str]) -> list[str] | None:
    primeiro = codigo / executar[0]
    if primeiro.is_file():
        return [str(primeiro), *executar[1:]]
    if "/" not in executar[0]:
        achado = shutil.which(executar[0])
        if achado:
            return [achado, *executar[1:]]
    return None


def _ha_jogo_aberto() -> bool:
    """A pergunta que a troca no fim do jogo faz; na dúvida, há jogo."""
    from hefesto_dualsense4unix.app.actions.troca_no_fim_do_jogo import _jogo_aberto

    return _jogo_aberto()


def _instalacao(entrada: Entrada) -> tuple[str, str, str, bool]:
    return (entrada.commit, entrada.instalada_em, entrada.ligada_em, entrada.sem_caixa)


class Supervisor:
    """Obedece ao registro: abre o que está ligado, para o que não está."""

    def __init__(
        self,
        bus: EventBus,
        *,
        escritor: Escritor,
        o_jogo_escreve: OJogoEscreve,
        uniq_do_posto: UniqDoPosto,
        pulsador: Pulsador | None = None,
        controles: Controles | None = None,
        lugares: Lugares | None = None,
        porta: Path | None = None,
        bwrap: str | None = None,
        procurar_bwrap: bool = True,
        proxy_dbus: str | None = None,
        procurar_proxy_dbus: bool = True,
        esperas: tuple[float, ...] = ESPERAS_PARA_VOLTAR,
        estavel_s: float = ESTAVEL_DEPOIS_DE_S,
        prazo_para_parar_s: float = PRAZO_PARA_PARAR_S,
        intervalo_s: float = INTERVALO_DO_REGISTRO_S,
        chaves: Sequence[str] = CHAVES_OFICIAIS,
        jogo_aberto: Callable[[], bool] = _ha_jogo_aberto,
        systemd_run: str | None = None,
    ) -> None:
        self.lugares = lugares or Lugares.do_xdg()
        self.porta = Porta(
            porta or mods_socket_path(),
            bus,
            escritor=escritor,
            o_jogo_escreve=o_jogo_escreve,
            uniq_do_posto=uniq_do_posto,
            pulsador=pulsador,
            controles=controles,
            ligar_a_chave=self._ligar_a_chave,
            apelidos=Apelidos(
                lambda: chave_dos_apelidos(self.lugares.registro.with_name(CHAVE_DOS_APELIDOS)),
                lambda: _uniqs_de_agora(controles, uniq_do_posto)),
        )
        self.bwrap = bwrap or (shutil.which("bwrap") if procurar_bwrap else None)
        self.proxy_dbus = proxy_dbus or (
            shutil.which("xdg-dbus-proxy") if procurar_proxy_dbus else None)
        self.esperas = esperas
        self.estavel_s = estavel_s
        self.prazo_para_parar_s = prazo_para_parar_s
        self.intervalo_s = intervalo_s
        self._vigiadas: dict[str, _Vigiada] = {}
        self._reaberta_pelo_aparelho: dict[str, float] = {}
        self._estados: dict[str, EstadoDaModificacao] = {}
        self._laco: asyncio.Task[None] | None = None
        self._marca_do_registro: tuple[int, int] | None = None
        self._prctl = _prctl()
        self._gravou_o_estado = False
        self.bus = bus
        self.prazo_do_parar_curto_s = PRAZO_DO_PARAR_CURTO_S
        self._ouvinte_do_parar: asyncio.Task[None] | None = None
        self._parar_curtos: set[asyncio.Task[bool]] = set()
        self.chaves = tuple(chaves)
        self._jogo_aberto = jogo_aberto
        self.systemd_run = systemd_run
        self.piso_da_atualizacao_s = PISO_DA_ATUALIZACAO_S
        self.espera_depois_da_falha_s = ESPERA_DEPOIS_DA_FALHA_S
        self._proxima_conferencia: dict[str, float] = {}
        self._registro_lido: dict[str, Entrada] = {}
        self._atualizando: asyncio.Task[bool] | None = None
        self._ouvido: asyncio.Task[None] | None = None
        self._vez_da_vigia = asyncio.Lock()

    def estado_de(self, mod_id: str) -> EstadoDaModificacao | None:
        return self._estados.get(mod_id)

    def pid_de(self, mod_id: str) -> int | None:
        vigiada = self._vigiadas.get(mod_id)
        processo = vigiada.processo if vigiada else None
        return processo.pid if processo is not None and processo.returncode is None else None

    def _marcar(self, mod_id: str, estado: EstadoDaModificacao) -> None:
        self._estados[mod_id] = estado
        self._gravar_estado()

    def _gravar_estado(self) -> None:
        corpo = {
            "api": API_DAS_MODIFICACOES,
            "caixa": "bwrap" if self.bwrap else "",
            "mods": {k: asdict(v) for k, v in sorted(self._estados.items())},
        }
        caminho = self.lugares.estado
        try:
            caminho.parent.mkdir(parents=True, exist_ok=True)
            temporario = caminho.with_name(f".{caminho.name}.{os.getpid()}")
            temporario.write_text(json.dumps(corpo, ensure_ascii=False), encoding="utf-8")
            os.chmod(temporario, 0o600)
            os.replace(temporario, caminho)
            self._gravou_o_estado = True
        except OSError as exc:
            logger.warning("mods_estado_nao_gravou", err=str(exc))

    async def iniciar(self) -> None:
        await self.reconciliar()
        self._laco = asyncio.create_task(self._vigiar_o_registro(), name="mods-registro")
        self._ouvido = asyncio.create_task(self._ouvir_o_barramento(), name="mods-barramento")
        fila = self.bus.subscribe(EventTopic.ACESSORIOS_GESTO)
        self._ouvinte_do_parar = asyncio.create_task(
            self._ouvir_o_parar(fila), name="mods-parar-curto"
        )

    async def parar(self) -> None:
        laco, self._laco = self._laco, None
        ouvinte, self._ouvinte_do_parar = self._ouvinte_do_parar, None
        atualizando, self._atualizando = self._atualizando, None
        ouvido, self._ouvido = self._ouvido, None
        for tarefa in (laco, ouvinte, atualizando, ouvido, *self._parar_curtos):
            if tarefa is not None:
                tarefa.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await tarefa
        await asyncio.gather(
            *(self._parar_uma(mod_id) for mod_id in list(self._vigiadas)),
            return_exceptions=True,
        )
        await self.porta.parar()
        if self._gravou_o_estado:
            with contextlib.suppress(FileNotFoundError):
                self.lugares.estado.unlink()

    async def _ouvir_o_parar(self, fila: asyncio.Queue[Any]) -> None:
        """O gesto ``para`` abre uma conferência de :attr:`prazo_do_parar_curto_s`."""
        try:
            while True:
                gesto = await fila.get()
                if isinstance(gesto, dict) and gesto.get("gesto") == "para":
                    alvo = gesto.get("mod") if isinstance(gesto.get("mod"), str) else None
                    tarefa = asyncio.create_task(
                        self.conferir_o_parar(alvo), name="mods-parar-curto-1"
                    )
                    self._parar_curtos.add(tarefa)
                    tarefa.add_done_callback(self._parar_curtos.discard)
        finally:
            self.bus.unsubscribe(EventTopic.ACESSORIOS_GESTO, fila)

    async def conferir_o_parar(self, mod: str | None = None) -> bool:
        """Depois do ``para``, a modificação devolveu ``ligado: false`` a tempo? Senão, é encerrada.

        Devolve ``True`` quando o supervisor a encerrou. Quem já estava desligada (``ligado: false``
        antes do gesto) ou não tem processo do supervisor fica como está. Sempre pelo PID que o
        supervisor criou, nunca por nome; a vigia reabre a modificação como reabre qualquer queda.
        ``mod`` é o alvo do «Parar tudo» da janela: o estado de outra extensão não é conferido.
        """
        antes = self._estado_para_o_parar(mod)
        if not isinstance(antes, dict) or antes.get("ligado") is False:
            return False
        await asyncio.sleep(self.prazo_do_parar_curto_s)
        depois = self._estado_para_o_parar(mod)
        if isinstance(depois, dict) and depois is not antes and depois.get("ligado") is False:
            return False
        vigiada = self._vigiadas.get(str(antes.get("mod", "")))
        processo = vigiada.processo if vigiada is not None else None
        if processo is None or processo.returncode is not None:
            return False
        logger.warning("mods_parar_curto", mod=antes.get("mod"), pid=processo.pid)
        await parar_o_grupo(processo, self.prazo_para_parar_s)
        return True

    def _estado_para_o_parar(self, mod: str | None) -> Any:
        """O último estado que o parar confere: o do barramento, ou o da extensão ``mod``."""
        if mod is None:
            return self.bus.ultimo(EventTopic.ACESSORIOS_ESTADO)
        return self.porta.ultimo_estado_de(mod)

    async def _vigiar_o_registro(self) -> None:
        while True:
            await asyncio.sleep(self.intervalo_s)
            await self._conferir_o_registro()
            await self._conferir_os_aparelhos()
            self._talvez_atualizar()

    async def _ouvir_o_barramento(self) -> None:
        """Cada aparelho USB que entra e cada HID que entra ou sai acorda a vigia na hora
        (:meth:`_conferir_os_aparelhos`); sem o uevent do kernel, fica a volta do registro."""
        from hefesto_dualsense4unix.daemon.subsystems.ouvido_do_usb import (
            abrir_o_netlink,
            eventos_de,
        )
        sock = abrir_o_netlink()
        if sock is None:
            return
        laco = asyncio.get_running_loop()
        try:
            while True:
                campos = eventos_de(await laco.sock_recv(sock, 1 << 16))
                if a_caixa_quer_saber(campos):
                    await self._conferir_os_aparelhos()
        finally:
            sock.close()

    async def _conferir_os_aparelhos(self) -> None:
        """A caixa aberta segue o que o ``/sys`` mostra, e a cada volta só um passa por aqui.

        Por dentro, sem reabrir (:meth:`_mudar_por_dentro`): cobre o aparelho que o hub vivo
        mostra e refaz a pasta sintética do HID. Se não dá, reabre. O declarado que entrou
        depois reabre em duas voltas seguidas com o nó novo; o ``pela_porta``, só fora do
        ``/sys`` da caixa; a segunda antes de :data:`JANELA_DO_LACO_DOS_APARELHOS_S` não sai.
        """
        async with self._vez_da_vigia:
            for mod_id, vigiada in list(self._vigiadas.items()):
                await self._conferir_uma(mod_id, vigiada)

    async def _mudar_por_dentro(self, mod_id: str, vigiada: _Vigiada) -> str | None:
        """Cobre os irmãos à vista e refaz os links do HID na caixa aberta; devolve o motivo de
        reabrir (``hub_saiu``, ``cobertura_falhou``, ``escape``: :func:`a_caixa_escapa`), ou
        ``None`` quando a caixa segue aberta."""
        manifesto, processo = vigiada.manifesto, vigiada.processo
        assert manifesto is not None and processo is not None
        irmaos, sairam = ((await asyncio.to_thread(irmaos_a_vista, vigiada.retrato))
                          if vigiada.retrato else ({}, []))
        hid = await asyncio.to_thread(hid_da_caixa, manifesto, vigiada.aceitos)
        ligar = {nome: alvo for nome, alvo in hid.items() if vigiada.hid.get(nome) != alvo}
        desligar = sorted(set(vigiada.hid) - set(hid))
        if sairam:
            return "hub_saiu"
        if not (irmaos or ligar or desligar):
            return None
        dentro = await asyncio.to_thread(a_extensao_na_caixa, processo.pid)
        if dentro is None:
            return None
        inicio = time.monotonic()
        resposta = await mudar_por_dentro_da_caixa(dentro, {
            "cobrir": sorted(irmaos), "pasta_dos_links": PASTA_DO_HID if hid or desligar else "",
            "ligar": ligar, "desligar": desligar})
        if (resposta is None or resposta.get("falhas")
                or set(resposta.get("cobertos", [])) != set(irmaos)):
            logger.warning("mods_por_dentro_falhou", mod=mod_id,
                           falhas=(resposta or {}).get("falhas"))
            return "cobertura_falhou"
        vigiada.retrato.update(irmaos)
        vigiada.hid = hid
        if irmaos:
            logger.info("mods_irmao_coberto", mod=mod_id, quantos=len(irmaos),
                        ms=round((time.monotonic() - inicio) * 1000, 1))
            if await asyncio.to_thread(a_caixa_escapa, processo.pid, dentro):
                return "escape"
        return None

    async def _conferir_uma(self, mod_id: str, vigiada: _Vigiada) -> None:
        manifesto = vigiada.manifesto
        processo = vigiada.processo
        if (manifesto is None or not self.bwrap or processo is None
                or processo.returncode is not None):
            return
        if (motivo := await self._mudar_por_dentro(mod_id, vigiada)) is not None:
            logger.warning("mods_caixa_reabre", mod=mod_id, motivo=motivo)
            if (entrada := self._registro_lido.get(mod_id)) is not None:
                await self._comecar(entrada)
            return
        if not manifesto.aparelhos or vigiada.aparelho_em_laco:
            return
        agora = await asyncio.to_thread(aparelhos_que_casam, manifesto, vigiada.aceitos)
        pela_porta = await asyncio.to_thread(pastas_pela_porta, manifesto, vigiada.aceitos)
        novos = set(agora) - set(vigiada.aparelhos)
        novos |= {no for no, pasta in pela_porta.items() if pasta not in vigiada.pela_porta}
        if not novos:
            vigiada.aparelho_novo = False
        elif not vigiada.aparelho_novo:
            vigiada.aparelho_novo = True
        elif (entrada := self._registro_lido.get(mod_id)) is not None:
            antes = self._reaberta_pelo_aparelho.get(mod_id)
            if antes is not None and time.monotonic() - antes < JANELA_DO_LACO_DOS_APARELHOS_S:
                vigiada.aparelho_em_laco = True
                logger.warning("mods_aparelho_em_laco", mod=mod_id, nos=sorted(novos))
                return
            self._reaberta_pelo_aparelho[mod_id] = time.monotonic()
            logger.info("mods_aparelho_novo_reabre", mod=mod_id, nos=sorted(novos))
            await self._comecar(entrada)

    def _talvez_atualizar(self) -> None:
        """Abre a conferência da primeira extensão do git cujo intervalo passou.

        Uma por vez, numa tarefa à parte: o ``atualizar`` desliga a extensão viva e espera
        a vigia pará-la, e a vigia é esta volta, que não pode esperar por ele.
        """
        if self._atualizando is not None and not self._atualizando.done():
            return
        registro = self._registro_lido
        agora = time.monotonic()
        for mod_id in [m for m in self._proxima_conferencia if m not in registro]:
            self._proxima_conferencia.pop(mod_id, None)
        for entrada in registro.values():
            if entrada.origem == "local" or not entrada.atualiza_sozinha:
                continue
            if agora < self._proxima_conferencia.get(entrada.id, agora):
                continue
            self._atualizando = asyncio.create_task(
                self.atualizar_sozinha(entrada), name="mods-atualizar-sozinha"
            )
            return

    def _espera_curta(self, entrada: Entrada) -> float:
        """A volta que a conferência faz depois de uma falha ou de um jogo aberto."""
        intervalo = max(float(entrada.intervalo_da_atualizacao_s), self.piso_da_atualizacao_s)
        return min(intervalo, max(self.espera_depois_da_falha_s, self.piso_da_atualizacao_s))

    async def atualizar_sozinha(self, entrada: Entrada) -> bool:
        """Pergunta ao endereço se há commit novo e, havendo, atualiza como o «Atualizar».

        Devolve ``True`` quando o código trocou. Sem rede, sem novidade ou com a versão nova
        esperando o «Atualizar» (permissão nova, tag que deixou de ser a oficial), a extensão
        fica na versão de agora, viva como estava. A extensão com processo vivo não troca com
        jogo aberto (a pergunta roda fora do laço, só quando há commit novo): a conferência volta
        na espera de depois de uma falha.
        """
        intervalo = max(float(entrada.intervalo_da_atualizacao_s), self.piso_da_atualizacao_s)
        espera = self._espera_curta(entrada)
        self._proxima_conferencia[entrada.id] = time.monotonic() + intervalo
        try:
            novo = await asyncio.to_thread(commit_novo, entrada, lugares=self.lugares)
            if novo is None:
                return False
            if entrada.id in self._vigiadas and await asyncio.to_thread(self._jogo_aberto):
                logger.info("mods_atualizacao_espera_o_jogo", mod=entrada.id)
                self._proxima_conferencia[entrada.id] = time.monotonic() + espera
                return False
            feito = await asyncio.to_thread(
                atualizar, entrada.id, lugares=self.lugares, chaves=self.chaves, sozinha=True
            )
        except SemRespostaDoGitError as exc:
            logger.info("mods_sem_rede_para_conferir", mod=entrada.id, motivo=exc.motivo,
                        proxima_as=time.strftime("%H:%M:%S", time.localtime(time.time() + espera)))
        except InstalacaoRecusadaError as exc:
            logger.warning("mods_atualizacao_recusada", mod=entrada.id, err=exc.frase)
        except Exception as exc:
            logger.warning("mods_atualizacao_falhou", mod=entrada.id, err=str(exc), exc_info=True)
        else:
            if feito.trocou:
                logger.info("mods_atualizada_sozinha", mod=entrada.id, versao=feito.entrada.versao)
            else:
                logger.info(
                    "mods_versao_esperando", mod=entrada.id, motivo=feito.entrada.motivo_da_espera
                )
            return feito.trocou
        self._proxima_conferencia[entrada.id] = time.monotonic() + espera
        return False

    async def _conferir_o_registro(self) -> None:
        """Uma volta da vigia: o registro mudou (outro mtime ou outro inode), ou a troca que
        segurava uma extensão parada acabou sem ele mudar?"""
        try:
            if self._marca() != self._marca_do_registro or self._troca_que_acabou():
                await self.reconciliar()
        except Exception as exc:
            logger.warning("mods_registro_falhou", err=str(exc), exc_info=True)

    def _troca_que_acabou(self) -> bool:
        return any(
            estado.estado == "atualizando"
            and (m not in self._registro_lido or not troca_viva(self._registro_lido[m]))
            for m, estado in self._estados.items()
        )

    def _marca(self) -> tuple[int, int] | None:
        if not self.lugares.registro.is_file():
            return None
        st = self.lugares.registro.stat()
        return (st.st_mtime_ns, st.st_ino)

    async def reconciliar(self) -> None:
        """Lê o registro e põe os processos de acordo com ele."""
        self._marca_do_registro = self._marca()
        try:
            registro = ler_registro(self.lugares.registro)
        except InstalacaoRecusadaError as exc:
            logger.warning("mods_registro_ilegivel", err=exc.frase)
            self._registro_lido = {}
            return
        if migradas := list(dict.fromkeys([*migrar_os_aparelhos(self.lugares, registro),
                                            *migrar_os_alcances(self.lugares, registro)])):
            try:
                gravar_registro(self.lugares.registro, registro)
                self._marca_do_registro = self._marca()
                logger.info("mods_sim_aceito_migrado", mods=migradas)
            except OSError as exc:
                logger.warning("mods_sim_aceito_sem_gravar", err=str(exc))
        self._registro_lido = registro
        em_troca = {k for k, v in registro.items() if v.ligada and troca_viva(v)}
        ligadas = {k: v for k, v in registro.items() if v.ligada and k not in em_troca}
        for mod_id in [m for m in self._vigiadas if m not in ligadas]:
            await self._parar_uma(mod_id, "atualizando" if mod_id in em_troca else "desligada")
        for mod_id in [m for m in self._estados if m not in registro]:
            self._estados.pop(mod_id, None)
        for mod_id, entrada in registro.items():
            if not entrada.ligada:
                self._estados[mod_id] = EstadoDaModificacao("desligada")
            elif mod_id in em_troca:
                self._estados[mod_id] = EstadoDaModificacao("atualizando")
        for mod_id, entrada in ligadas.items():
            vigiada = self._vigiadas.get(mod_id)
            if vigiada is None or vigiada.instalacao != _instalacao(entrada):
                await self._comecar(entrada)
        if self._estados or self._gravou_o_estado:
            self._gravar_estado()

    def _o_que_impede(self, entrada: Entrada) -> tuple[str, Manifesto | None]:
        try:
            manifesto = ler_manifesto(self.lugares.codigo / entrada.id)
        except ManifestoRecusadoError as exc:
            return exc.frase, None
        novas = permissoes_novas(aceitos_de(entrada), pedidos_do_sim(manifesto))
        if novas:
            return (
                f"«{manifesto.nome}» pede {', '.join(novas)}, que ainda não teve o «sim».",
                None,
            )
        if aviso_por_ver(entrada, manifesto):
            return f"«{manifesto.nome}» traz um aviso que ainda não teve o «sim».", None
        return "", manifesto

    async def _comecar(self, entrada: Entrada) -> None:
        if entrada.id in self._vigiadas:
            await self._parar_uma(entrada.id)
        motivo, manifesto = self._o_que_impede(entrada)
        if manifesto is None:
            self._estados[entrada.id] = EstadoDaModificacao("recusada", motivo=motivo)
            return
        if manifesto.processo is None:
            self._estados[entrada.id] = EstadoDaModificacao("declarativa")
            return
        if not self.bwrap and not entrada.sem_caixa:
            self._estados[entrada.id] = EstadoDaModificacao("recusada", motivo=FALTA_O_BWRAP)
            return
        if self._pede_o_filtro(manifesto) and not self.proxy_dbus:
            self._estados[entrada.id] = EstadoDaModificacao(
                "recusada", motivo=FALTA_O_PROXY_DO_BLUETOOTH)
            return
        if not self.porta.aberta:
            await self.porta.iniciar()
        vigiada = _Vigiada(entrada.id, instalacao=_instalacao(entrada))
        self._vigiadas[entrada.id] = vigiada
        vigiada.tarefa = asyncio.create_task(
            self._cuidar(vigiada, manifesto), name=f"mods-{entrada.id}"
        )

    async def _cuidar(self, vigiada: _Vigiada, manifesto: Manifesto) -> None:
        mod_id = vigiada.mod_id
        quedas = 0
        diario = diario_da_extensao(self.lugares, mod_id)
        caixa = "bwrap" if self.bwrap else ""
        sem_caixa = "" if self.bwrap else "Roda sem caixa: o bwrap não está instalado."
        while not vigiada.quer_parar.is_set():
            self._marcar(mod_id, EstadoDaModificacao(
                "ligando" if quedas == 0 else "voltando",
                caixa=caixa, motivo=sem_caixa, quedas=quedas))
            try:
                processo = await self._abrir(vigiada, manifesto, diario)
            except (OSError, ValueError) as exc:
                await self._soltar_o_proxy(vigiada)
                self._marcar(mod_id, EstadoDaModificacao(
                    "parou", caixa=caixa, motivo=f"Não abriu: {exc}", quedas=quedas))
                return
            if processo is None:
                return
            self._marcar(mod_id, EstadoDaModificacao(
                "rodando", pid=processo.pid, caixa=caixa, motivo=sem_caixa, quedas=quedas))
            aberto_em = time.monotonic()
            vigia = asyncio.create_task(self._avisar_as_pontes_caladas(vigiada, processo.pid))
            prova = asyncio.create_task(
                self._provar_depois_de_estavel(self._registro_lido.get(mod_id)))
            codigo = await processo.wait()
            await self._soltar_o_proxy(vigiada)
            vigia.cancel()
            prova.cancel()
            await asyncio.wait({vigia, prova})
            copia, vigiada.copia = vigiada.copia, None
            await _esvaziar_a_copia(copia, ESPERA_DO_DIARIO_S)
            self.porta.esquecer(vigiada.ficha)
            if vigiada.quer_parar.is_set():
                return
            if time.monotonic() - aberto_em >= self.estavel_s:
                quedas = 0
            quedas += 1
            ultima = ultima_linha_do_diario(diario, hora=True)
            logger.warning("mods_caiu", mod=mod_id, codigo=codigo, quedas=quedas)
            if quedas > len(self.esperas):
                if volta := await self._voltar_para_a_anterior(mod_id):
                    self._marcar(mod_id, EstadoDaModificacao(
                        "voltando", caixa=caixa, motivo=volta, ultima_linha=ultima,
                        quedas=quedas))
                    return
                self._marcar(mod_id, EstadoDaModificacao(
                    "parou",
                    caixa=caixa,
                    motivo=f"Caiu {quedas} vezes seguidas (código {codigo}).",
                    ultima_linha=ultima,
                    quedas=quedas,
                ))
                return
            self._marcar(mod_id, EstadoDaModificacao(
                "voltando", caixa=caixa, motivo=f"Caiu (código {codigo}).",
                ultima_linha=ultima, quedas=quedas))
            with contextlib.suppress(asyncio.TimeoutError):
                await asyncio.wait_for(
                    vigiada.quer_parar.wait(), timeout=self.esperas[quedas - 1]
                )

    async def _provar_depois_de_estavel(self, entrada: Entrada | None) -> None:
        """A versão recém-trocada que fica estável deixa de poder voltar para a guardada."""
        if entrada is None or not entrada.em_prova:
            return
        await asyncio.sleep(self.estavel_s)
        try:
            await asyncio.to_thread(dar_por_provada, self.lugares, entrada.id, entrada.commit)
        except (OSError, InstalacaoRecusadaError) as exc:
            logger.warning("mods_prova_nao_gravou", mod=entrada.id, err=str(exc))

    async def _voltar_para_a_anterior(self, mod_id: str) -> str:
        """A versão recém-trocada que caiu até parar volta para a guardada; devolve o motivo,
        ou vazio quando não havia para onde voltar. A vigia reabre a extensão pelo registro."""
        entrada = self._registro_lido.get(mod_id)
        if entrada is None or not entrada.em_prova:
            return ""
        try:
            voltou = await asyncio.to_thread(
                voltar_para_a_anterior, self.lugares, mod_id, entrada.commit)
        except (OSError, InstalacaoRecusadaError) as exc:
            logger.warning("mods_volta_falhou", mod=mod_id, err=str(exc))
            return ""
        if voltou is None:
            return ""
        logger.warning("mods_voltou_para_a_anterior", mod=mod_id, versao=voltou.versao,
                       caiu=voltou.versao_esperando)
        return voltou.motivo_da_espera

    async def _avisar_as_pontes_caladas(self, vigiada: _Vigiada, pid: int) -> None:
        if not vigiada.pontes:
            return
        for porta in await as_pontes_caladas(pid, vigiada.pontes):
            logger.warning("mods_ponte_calada", mod=vigiada.mod_id, porta=porta)
            if vigiada.escritor is not None:
                vigiada.escritor.por(vigiada.escritor.hora.carimbo()
                                     + frase_da_ponte_calada(porta).encode() + b"\n")

    async def _abrir(
        self, vigiada: _Vigiada, manifesto: Manifesto, diario: Path
    ) -> asyncio.subprocess.Process | None:
        """O processo, ou ``None`` quando a parada chegou no meio: nada fica aberto."""
        assert manifesto.processo is not None
        codigo = self.lugares.codigo / manifesto.id
        dados = self.lugares.dados / manifesto.id
        dados.mkdir(parents=True, exist_ok=True)
        da_pessoa = pasta_da_pessoa(manifesto.id, self.lugares)
        da_pessoa.mkdir(mode=0o700, parents=True, exist_ok=True)
        with contextlib.suppress(InstalacaoRecusadaError):
            opcoes.deixar_a_copia(manifesto.id, self.lugares)
        comando = _resolver_o_comando(codigo, manifesto.processo.executar)
        if comando is None:
            raise ValueError(f"o comando {manifesto.processo.executar[0]} não existe")
        vigiada.ficha = secrets.token_urlsafe(32)
        casa = Path(os.environ.get("HOME") or "/nonexistent")
        execucao_bruta = os.environ.get("XDG_RUNTIME_DIR")
        ambiente = {
            "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
            "LANG": os.environ.get("LANG", "C.UTF-8"),
            "HOME": str(casa),
            "PYTHONDONTWRITEBYTECODE": "1",
            "HEFESTO_MOD_ID": manifesto.id,
            "HEFESTO_MOD_SOCKET": str(self.porta.caminho),
            "HEFESTO_MOD_FICHA": vigiada.ficha,
            "HEFESTO_MOD_DADOS": str(dados),
            "HEFESTO_MOD_OPCOES": str(da_pessoa / opcoes.NOME_DO_ARQUIVO),
            "HEFESTO_MOD_API": str(API_DAS_MODIFICACOES),
        }
        if execucao_bruta:
            ambiente["XDG_RUNTIME_DIR"] = execucao_bruta
        jogos = pastas_dos_jogos(manifesto, casa)
        if jogos:
            ambiente["HEFESTO_MOD_JOGOS"] = os.pathsep.join(str(p) for p in jogos)
        pasta = await asyncio.to_thread(pasta_da_caixa, manifesto) if self.bwrap else None
        portas = manifesto.portas
        ocupadas = {(p.porta, p.udp) for p in (portas.para_a_casa if portas else [])
                    if pasta and ocupada_na_casa(p.porta, p.udp)}

        def ocupada(porta: int, udp: bool) -> bool:
            return (porta, udp) in ocupadas

        vigiada.pontes = ()
        if self.bwrap and pasta:
            vigiada.pontes = pontes_que_o_pasta_traz(manifesto, ocupada)
        vigiada.manifesto = manifesto
        lida = self._registro_lido.get(manifesto.id)
        vigiada.aceitos = tuple(lida.aparelhos_aceitos or []) if lida is not None else ()
        vigiada.aparelhos = aparelhos_que_casam(manifesto, vigiada.aceitos) if self.bwrap else ()
        pela_porta = pastas_pela_porta(manifesto, vigiada.aceitos) if self.bwrap else {}
        vigiada.pela_porta = frozenset(pela_porta.values())
        vigiada.aparelho_novo = False
        vigiada.retrato = {}
        vigiada.hid = hid_da_caixa(manifesto, vigiada.aceitos) if self.bwrap else {}
        if self._pede_o_filtro(manifesto):
            ambiente["DBUS_SYSTEM_BUS_ADDRESS"] = BARRAMENTO_DO_SISTEMA_NA_CAIXA
            try:
                await self._abrir_o_proxy(vigiada, manifesto.id)
            except BaseException:
                await self._soltar_o_proxy(vigiada)
                raise
        if self.bwrap:
            argv = comando_na_caixa(
                bwrap=self.bwrap,
                comando=comando,
                codigo=codigo,
                dados=dados,
                da_pessoa=da_pessoa,
                porta=self.porta.caminho,
                manifesto=manifesto,
                casa=casa,
                execucao=_execucao_da_sessao(execucao_bruta, self.porta.caminho),
                jogos=jogos,
                pasta=pasta,
                ocupada=ocupada,
                aparelhos=vigiada.aparelhos,
                pela_porta=tuple(pela_porta),
                retrato=vigiada.retrato,
                hid=vigiada.hid,
                bluez=str(vigiada.soquete) if vigiada.proxy is not None else None,
            )
        else:
            argv = comando
        argv = comando_com_teto(argv, self.systemd_run, manifesto.id)
        if self.systemd_run is None:
            logger.info("mods_sem_teto_do_systemd", mod=manifesto.id,
                        oom_score_adj=OOM_SCORE_DA_EXTENSAO, tmp_bytes=TAMANHO_DO_TMP_BYTES)
        await _preparar_com_teto(dados / DIARIO_DA_MODIFICACAO, diario, ESPERA_DA_PODA_S)
        if vigiada.quer_parar.is_set():
            await self._soltar_o_proxy(vigiada)
            return None
        processo = await asyncio.create_subprocess_exec(
            *argv,
            cwd=str(codigo),
            env=ambiente,
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            start_new_session=True,
            preexec_fn=_morre_com_o_pai(self._prctl),
        )
        vigiada.processo = processo
        assert processo.stdout is not None
        vigiada.copia = asyncio.create_task(
            _copiar_para_o_diario(processo.stdout, diario,
                                  ao_abrir=lambda escritor: setattr(vigiada, "escritor", escritor)),
            name=f"mods-diario-{manifesto.id}",
        )
        if vigiada.quer_parar.is_set():
            await parar_o_grupo(processo, self.prazo_para_parar_s)
            copia, vigiada.copia = vigiada.copia, None
            await _esvaziar_a_copia(copia, ESPERA_DO_DIARIO_S)
            return None
        self.porta.registrar(vigiada.ficha, manifesto.id, processo.pid, manifesto.permissoes,
                             comandos=_comandos_do_lancador(manifesto),
                             acoes_dos_aparelhos=_acoes_dos_aparelhos(manifesto),
                             abrir_o_aparelho=self._abridor_dos_aparelhos(manifesto,
                                                                          vigiada.ficha))
        logger.info("mods_aberta", mod=manifesto.id, pid=processo.pid, caixa=bool(self.bwrap),
                    teto=bool(self.systemd_run))
        return processo

    def _pede_o_filtro(self, manifesto: Manifesto) -> bool:
        """A extensão com ``bluetooth`` na caixa fala com o BlueZ pelo proxy, nunca pelo
        barramento do sistema inteiro."""
        return bool(self.bwrap) and "bluetooth" in manifesto.permissoes

    async def _abrir_o_proxy(self, vigiada: _Vigiada, mod_id: str) -> None:
        """Abre o ``xdg-dbus-proxy`` de ``mod_id`` com o :data:`FILTRO_DO_BLUEZ` e espera o aviso
        de pronto. A ponta de leitura do cano fica aberta: ao fechar, o proxy sai."""
        assert self.proxy_dbus is not None
        soquete = self.porta.caminho.parent / f"bluez-{mod_id}.sock"
        soquete.unlink(missing_ok=True)
        vigiada.soquete = soquete
        de_cima = os.environ.get("DBUS_SYSTEM_BUS_ADDRESS") or BARRAMENTO_DO_SISTEMA_NA_CAIXA
        leitura, escrita = os.pipe()
        vigiada.sincronia = leitura
        try:
            vigiada.proxy = await asyncio.create_subprocess_exec(
                self.proxy_dbus, f"--fd={escrita}", de_cima, str(soquete), *FILTRO_DO_BLUEZ,
                pass_fds=(escrita,), stdin=asyncio.subprocess.DEVNULL,
                stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL,
                start_new_session=True,
            )
        finally:
            os.close(escrita)
        loop = asyncio.get_running_loop()
        pronto: asyncio.Future[bytes] = loop.create_future()

        def avisou() -> None:
            loop.remove_reader(leitura)
            pronto.set_result(os.read(leitura, 1))

        loop.add_reader(leitura, avisou)
        try:
            aviso = await asyncio.wait_for(pronto, PRAZO_DO_PROXY_S)
        except asyncio.TimeoutError:
            raise OSError("o xdg-dbus-proxy não ficou pronto a tempo") from None
        finally:
            loop.remove_reader(leitura)
        if not aviso:
            raise OSError("o xdg-dbus-proxy saiu antes de abrir o soquete")

    async def _soltar_o_proxy(self, vigiada: _Vigiada) -> None:
        """Fecha o cano, para o proxy e apaga o soquete; sem proxy aberto, não faz nada."""
        proxy, vigiada.proxy = vigiada.proxy, None
        sincronia, vigiada.sincronia = vigiada.sincronia, None
        soquete, vigiada.soquete = vigiada.soquete, None
        if sincronia is not None:
            os.close(sincronia)
        if proxy is not None:
            with contextlib.suppress(ProcessLookupError):
                proxy.terminate()
            try:
                await asyncio.wait_for(proxy.wait(), self.prazo_para_parar_s)
            except asyncio.TimeoutError:
                with contextlib.suppress(ProcessLookupError):
                    proxy.kill()
                await proxy.wait()
        if soquete is not None:
            soquete.unlink(missing_ok=True)

    def _abridor_dos_aparelhos(self, manifesto: Manifesto,
                               ficha: str) -> Callable[[Any], int] | None:
        """O que a porta chama no ``aparelho.abrir`` desta execução; ``None`` sem aparelho
        declarado. A cada pedido, o «sim» e a chave se conferem de novo (:meth:`_o_sim_vale`)."""
        if "aparelhos" not in manifesto.permissoes or not manifesto.aparelhos:
            return None

        def abrir(no: Any) -> int:
            return abrir_o_aparelho(manifesto, no, self._o_sim_vale(manifesto.id, ficha))
        return abrir

    def _o_sim_vale(self, mod_id: str, ficha: str) -> list[str]:
        """O registro de agora diz que a extensão está ligada e que ``aparelhos`` tem o «sim», e
        a execução que pede é a que está de pé; devolve os aparelhos aceitos. Senão,
        ``ValueError`` com a frase da recusa."""
        try:
            entrada = ler_registro(self.lugares.registro).get(mod_id)
        except InstalacaoRecusadaError as exc:
            raise ValueError(f"aparelho.abrir: o registro não se lê: {exc.frase}") from exc
        if entrada is None or not entrada.ligada:
            raise ValueError("aparelho.abrir: a extensão não está ligada")
        if "aparelhos" not in entrada.permissoes_aceitas:
            raise ValueError("aparelho.abrir: a permissão aparelhos não tem o «sim»")
        vigiada = self._vigiadas.get(mod_id)
        if vigiada is None or vigiada.ficha != ficha:
            raise ValueError("aparelho.abrir: esta execução da extensão não está mais de pé")
        return list(entrada.aparelhos_aceitos or [])

    async def _ligar_a_chave(self, mod_id: str) -> bool:
        """A chave da extensão ``mod_id`` gravada ligada, como o clique da janela; ``False`` sem a
        ``chave`` no manifesto instalado."""
        try:
            manifesto = await asyncio.to_thread(manifesto_instalado, mod_id, lugares=self.lugares)
            if not manifesto.chave:
                return False
            await asyncio.to_thread(opcoes.guardar, manifesto, manifesto.chave, True, self.lugares)
        except (InstalacaoRecusadaError, OSError) as exc:
            logger.warning("mods_chave_nao_ligou", mod=mod_id, err=str(exc))
            return False
        logger.info("mods_chave_ligada_pela_extensao", mod=mod_id)
        return True

    async def _parar_uma(self, mod_id: str, estado: str = "desligada") -> None:
        vigiada = self._vigiadas.pop(mod_id, None)
        if vigiada is None:
            return
        vigiada.quer_parar.set()
        processo = vigiada.processo
        if processo is not None and processo.returncode is None:
            await parar_o_grupo(processo, self.prazo_para_parar_s)
        if vigiada.tarefa is not None:
            await asyncio.wait({vigiada.tarefa}, timeout=ESPERA_DA_VIGIA_S)
        copia, vigiada.copia = vigiada.copia, None
        await _esvaziar_a_copia(copia, 0)
        await self._soltar_o_proxy(vigiada)
        self.porta.esquecer(vigiada.ficha)
        self._marcar(mod_id, EstadoDaModificacao(estado))


def _campo(pid: int, nome: str) -> list[str]:
    try:
        status = Path(f"/proc/{pid}/status").read_text(encoding="utf-8")
    except OSError:
        return []
    return next((linha.split()[1:] for linha in status.splitlines()
                 if linha.startswith(f"{nome}:")), [])


def _mais_fundo(pid: int, alvo: int) -> bool:
    nspid = _campo(alvo, "NSpid")
    return len(nspid) > len(_campo(pid, "NSpid")) and nspid[-1] != "1"


def _desce_de(pid: int, alvo: int) -> bool:
    atual = alvo
    while (pai := _campo(atual, "PPid")) and (atual := int(pai[0])) > 0:
        if atual == pid:
            return True
    return False


def a_extensao_na_caixa(pid: int) -> int | None:
    """Na caixa, ``pid`` é o ``bwrap`` (ou o ``pasta``) de fora, e a extensão é o primeiro
    descendente, em largura, que mora num espaço de PID mais fundo sem ser o ``init`` dele.
    Sem caixa, nenhum."""
    fila = _filhos(pid)
    while fila:
        atual = fila.pop(0)
        if _mais_fundo(pid, atual):
            return atual
        fila += _filhos(atual)
    return None


def _avisar_o_grupo_preso(pid: int, alvo: int) -> bool:
    try:
        descritor = os.pidfd_open(alvo)
    except OSError:
        return False
    try:
        if not (_desce_de(pid, alvo) and _mais_fundo(pid, alvo)):
            return False
        grupo = os.getpgid(alvo)
        signal.pidfd_send_signal(descritor, 0)
        if grupo == os.getpgrp():
            return False
        os.killpg(grupo, signal.SIGTERM)
        return True
    except OSError:
        return False
    finally:
        os.close(descritor)


def avisar_o_grupo_da_extensao(pid: int) -> None:
    """``SIGTERM`` ao grupo da extensão na caixa (:func:`a_extensao_na_caixa`), que o
    ``--new-session`` pôs fora do grupo de ``pid``. O alvo fica preso por ``pidfd`` antes do
    sinal: com o descritor aberto, ele ainda desce de ``pid``, ainda mora no espaço mais fundo
    e ainda vive; o grupo de quem sinaliza nunca é alvo. Sem caixa, ou se uma conferência
    falha, o ``SIGTERM`` vai ao grupo de ``pid``."""
    alvo = a_extensao_na_caixa(pid)
    if alvo is not None and _avisar_o_grupo_preso(pid, alvo):
        return
    with contextlib.suppress(ProcessLookupError, PermissionError):
        os.killpg(pid, signal.SIGTERM)


async def parar_o_grupo(processo: asyncio.subprocess.Process, prazo: float) -> int | None:
    """``SIGTERM`` ao grupo da extensão (:func:`avisar_o_grupo_da_extensao`); ``SIGKILL`` ao
    grupo do PID criado no fim do prazo."""
    pid = processo.pid
    avisar_o_grupo_da_extensao(pid)
    espera = asyncio.ensure_future(processo.wait())
    await asyncio.wait({espera}, timeout=prazo)
    if not espera.done():
        with contextlib.suppress(ProcessLookupError, PermissionError):
            os.killpg(pid, signal.SIGKILL)
        await asyncio.wait({espera}, timeout=ESPERA_DEPOIS_DO_SIGKILL_S)
    if not espera.done():
        espera.cancel()
        return None
    return espera.result()


def supervisor_do_servico(daemon: Any) -> Supervisor | None:
    """O supervisor ligado ao serviço vivo (barramento, IPC e estado do jogo).

    ``None`` na instância isolada (o ``--fake`` e todo socket de nome próprio):
    a instância divide a casa com o serviço de verdade, e abrir as modificações dali
    trocaria a porta dele pela sua e abriria cada modificação duas vezes. É a
    mesma regra que já isola o socket e a trava de instância do ``--fake``.
    """
    if ipc_socket_name() != IPC_SOCKET_DEFAULT_NAME:
        logger.info("mods_fora_da_instancia_isolada", socket=ipc_socket_name())
        return None
    from hefesto_dualsense4unix.mods.porta import (
        controles_no_servico,
        escritor_do_servico,
        o_jogo_escreve_no_servico,
        pulsar_no_servico,
        uniq_do_posto_no_servico,
    )

    return Supervisor(
        daemon.bus,
        escritor=escritor_do_servico(daemon),
        o_jogo_escreve=o_jogo_escreve_no_servico(daemon),
        uniq_do_posto=uniq_do_posto_no_servico(daemon),
        pulsador=pulsar_no_servico(daemon),
        controles=controles_no_servico(daemon),
        systemd_run=systemd_run_com_teto(),
    )


__all__ = [
    "A_REDE_INCLUI_A_INTERNET",
    "A_REDE_INCLUI_A_MAQUINA",
    "CLASSES_PELA_PORTA",
    "COBERTOS_NA_CAIXA",
    "CONTROLADORES_DO_TETO",
    "DEVOLVIDO_COM_A_PERMISSAO",
    "DEVOLVIDO_COM_A_REDE",
    "DIARIO_DA_MODIFICACAO",
    "ENTRAM_NA_CAIXA",
    "ESPERAS_PARA_VOLTAR",
    "ESPERA_DA_PODA_S",
    "ESPERA_DA_VIGIA_S",
    "ESPERA_DEPOIS_DO_SIGKILL_S",
    "ESPERA_DO_DIARIO_S",
    "ESTAVEL_DEPOIS_DE_S",
    "FAIXAS_DA_CASA",
    "FALTA_O_BWRAP",
    "FALTA_O_PROXY_DO_BLUETOOTH",
    "FILTRO_DO_BLUEZ",
    "JANELA_DO_LACO_DOS_APARELHOS_S",
    "NOS_QUE_A_CAIXA_ACEITA",
    "OOM_SCORE_DA_EXTENSAO",
    "PASTA_DA_CAIXA",
    "PASTA_DO_HID",
    "PESO_DA_CPU",
    "PRAZO_DO_PARAR_CURTO_S",
    "PRAZO_PARA_PARAR_S",
    "TAMANHO_DO_TMP_BYTES",
    "TETO_DAS_TAREFAS",
    "TETO_DA_MEMORIA",
    "EstadoDaModificacao",
    "Supervisor",
    "a_caixa_escapa",
    "a_caixa_quer_saber",
    "a_extensao_na_caixa",
    "abrir_o_aparelho",
    "aparelhos_que_casam",
    "avisar_o_grupo_da_extensao",
    "bwrap_aceita_o_tamanho",
    "bwrap_fecha_o_userns",
    "colecoes_de_aplicacao",
    "comando_com_teto",
    "comando_na_caixa",
    "diario_da_extensao",
    "frase_da_rede",
    "frase_do_pedido",
    "frase_dos_aparelhos",
    "hid_da_caixa",
    "irmaos_a_vista",
    "linha_da_rede_da_casa",
    "linha_do_pasta",
    "mudar_por_dentro_da_caixa",
    "nome_no_sys",
    "nos_pela_porta",
    "ocupada_na_casa",
    "parar_o_grupo",
    "pastas_dos_jogos",
    "pastas_pela_porta",
    "rede_propria_da_caixa",
    "supervisor_do_servico",
    "systemd_run_com_teto",
    "ultima_linha_do_diario",
]
