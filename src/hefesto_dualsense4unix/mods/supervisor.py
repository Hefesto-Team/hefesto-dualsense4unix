"""O supervisor das modificações: abre, vigia, reabre e para os processos.

O registro (``mods.json``) diz o que está ligado; o supervisor obedece. Cada
modificação ligada do tipo ``processo`` vira um processo filho do serviço:

* num grupo próprio (``setsid``), com ``PR_SET_PDEATHSIG``: se o serviço
  morre, o filho morre junto;
* com caixa quando o ``bwrap`` existe: raiz só de leitura, ``HOME`` vazia,
  código só de leitura, dados graváveis, o socket principal escondido (só a
  porta das modificações aparece) e ``--unshare-net`` quando a rede é
  ``nenhuma``. Sem ``bwrap``, roda sem caixa, e o estado diz isso numa linha;
* reaberto com espera crescente (:data:`ESPERAS_PARA_VOLTAR`) nas três
  primeiras quedas; na quarta, fica «parou», com a última linha do diário;
* parado com ``SIGTERM`` ao grupo e ``SIGKILL`` no fim do prazo, sempre pelo
  PID que o supervisor criou, nunca por nome.

O estado vivo de cada uma vai para ``mods-estado.json`` no diretório de
execução, que a linha de comando e a tela leem.
"""
from __future__ import annotations

import asyncio
import contextlib
import ctypes
import json
import os
import secrets
import shutil
import signal
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from hefesto_dualsense4unix.core.events import EventBus
from hefesto_dualsense4unix.mods import API_DAS_MODIFICACOES
from hefesto_dualsense4unix.mods.instalador import (
    Entrada,
    InstalacaoRecusadaError,
    Lugares,
    ler_registro,
)
from hefesto_dualsense4unix.mods.manifesto import (
    Manifesto,
    ManifestoRecusadoError,
    ler_manifesto,
    permissoes_novas,
)
from hefesto_dualsense4unix.mods.porta import (
    Escritor,
    OJogoEscreve,
    Porta,
    UniqDoPosto,
)
from hefesto_dualsense4unix.utils.logging_config import get_logger
from hefesto_dualsense4unix.utils.xdg_paths import mods_socket_path

logger = get_logger(__name__)

#: O diário de cada modificação (saída e erro do processo), na pasta de dados.
DIARIO_DA_MODIFICACAO = "diario.log"

#: O diário cresce até isto; ao abrir de novo, a metade velha sai.
TETO_DO_DIARIO_BYTES = 1 << 20

#: As esperas antes de reabrir, uma por queda; a queda seguinte é «parou».
ESPERAS_PARA_VOLTAR: tuple[float, ...] = (1.0, 2.0, 4.0)

#: Um processo que fica de pé por este tempo zera a contagem de quedas.
ESTAVEL_DEPOIS_DE_S = 60.0

#: Do ``SIGTERM`` ao ``SIGKILL``.
PRAZO_PARA_PARAR_S = 3.0

#: De quanto em quanto tempo o supervisor relê o registro.
INTERVALO_DO_REGISTRO_S = 1.0

#: Depois do ``SIGKILL``, quanto se espera o kernel recolher o grupo.
ESPERA_DEPOIS_DO_SIGKILL_S = 2.0

#: Depois de parar o processo, quanto se espera a tarefa que o vigiava terminar.
ESPERA_DA_VIGIA_S = 1.0

#: Sem a permissão da chave, a caixa cobre estes caminhos com um ``tmpfs`` vazio.
ESCONDIDO_SEM_A_PERMISSAO: dict[str, tuple[str, ...]] = {
    "bluetooth": ("/run/dbus",),
}

_PR_SET_PDEATHSIG = 1


def _prctl() -> Callable[..., int] | None:
    """O ``prctl`` da libc já carregada no processo (a do próprio Python)."""
    funcao: Callable[..., int] | None = getattr(ctypes.CDLL(None, use_errno=True), "prctl", None)
    return funcao


def _morre_com_o_pai(prctl: Callable[..., int] | None) -> Callable[[], None]:
    """O ``preexec_fn`` do filho: ``PR_SET_PDEATHSIG`` com ``SIGKILL``.

    A função da libc é resolvida ANTES do ``fork``: no filho só a chamada roda.
    """

    def antes_de_executar() -> None:
        if prctl is not None:
            prctl(_PR_SET_PDEATHSIG, int(signal.SIGKILL), 0, 0, 0)

    return antes_de_executar


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
    ficha: str = ""
    quer_parar: asyncio.Event = field(default_factory=asyncio.Event)


def ultima_linha_do_diario(caminho: Path, *, teto: int = 200) -> str:
    """A última linha não vazia do diário (o que a tela mostra quando parou)."""
    try:
        with caminho.open("rb") as arquivo:
            arquivo.seek(0, os.SEEK_END)
            tamanho = arquivo.tell()
            arquivo.seek(max(0, tamanho - 4096))
            fim = arquivo.read().decode("utf-8", errors="replace")
    except OSError:
        return ""
    for linha in reversed(fim.splitlines()):
        if linha.strip():
            return linha.strip()[:teto]
    return ""


def _aparar_o_diario(caminho: Path) -> None:
    """Passou do teto: fica só a metade nova (o diário é do supervisor, ninguém mais o abre)."""
    if not caminho.is_file():
        return
    tamanho = caminho.stat().st_size
    if tamanho <= TETO_DO_DIARIO_BYTES:
        return
    with caminho.open("rb") as arquivo:
        arquivo.seek(tamanho - TETO_DO_DIARIO_BYTES // 2)
        resto = arquivo.read()
    caminho.write_bytes(resto)


def comando_na_caixa(
    *,
    bwrap: str,
    comando: list[str],
    codigo: Path,
    dados: Path,
    porta: Path,
    manifesto: Manifesto,
    casa: Path,
    execucao: Path | None,
) -> list[str]:
    """A linha do ``bwrap`` para ``comando``.

    Os ``tmpfs`` vêm antes das pastas montadas por cima deles: a ``HOME`` e o
    diretório de execução nascem vazios, e só o código (leitura), os dados
    (escrita) e a porta das modificações aparecem dentro deles.
    """
    argv = [
        bwrap,
        "--ro-bind", "/", "/",
        "--proc", "/proc",
        "--tmpfs", "/tmp",
        "--tmpfs", str(casa),
    ]
    if execucao is not None:
        argv += ["--tmpfs", str(execucao)]
    if "aparelhos" in manifesto.permissoes:
        argv += ["--dev-bind", "/dev", "/dev"]
    else:
        argv += ["--dev", "/dev"]
    for permissao, caminhos in ESCONDIDO_SEM_A_PERMISSAO.items():
        if permissao not in manifesto.permissoes:
            argv += [arg for c in caminhos if Path(c).is_dir() for arg in ("--tmpfs", c)]
    argv += [
        "--ro-bind", str(codigo), str(codigo),
        "--bind", str(dados), str(dados),
        "--ro-bind", str(porta), str(porta),
    ]
    if manifesto.rede == "nenhuma":
        argv.append("--unshare-net")
    argv += ["--die-with-parent", "--new-session", "--chdir", str(codigo), "--", *comando]
    return argv


def _resolver_o_comando(codigo: Path, executar: list[str]) -> list[str] | None:
    primeiro = codigo / executar[0]
    if primeiro.is_file():
        return [str(primeiro), *executar[1:]]
    if "/" not in executar[0]:
        achado = shutil.which(executar[0])
        if achado:
            return [achado, *executar[1:]]
    return None


class Supervisor:
    """Obedece ao registro: abre o que está ligado, para o que não está."""

    def __init__(
        self,
        bus: EventBus,
        *,
        escritor: Escritor,
        o_jogo_escreve: OJogoEscreve,
        uniq_do_posto: UniqDoPosto,
        lugares: Lugares | None = None,
        porta: Path | None = None,
        bwrap: str | None = None,
        procurar_bwrap: bool = True,
        esperas: tuple[float, ...] = ESPERAS_PARA_VOLTAR,
        estavel_s: float = ESTAVEL_DEPOIS_DE_S,
        prazo_para_parar_s: float = PRAZO_PARA_PARAR_S,
        intervalo_s: float = INTERVALO_DO_REGISTRO_S,
    ) -> None:
        self.lugares = lugares or Lugares.do_xdg()
        self.porta = Porta(
            porta or mods_socket_path(),
            bus,
            escritor=escritor,
            o_jogo_escreve=o_jogo_escreve,
            uniq_do_posto=uniq_do_posto,
        )
        self.bwrap = bwrap or (shutil.which("bwrap") if procurar_bwrap else None)
        self.esperas = esperas
        self.estavel_s = estavel_s
        self.prazo_para_parar_s = prazo_para_parar_s
        self.intervalo_s = intervalo_s
        self._vigiadas: dict[str, _Vigiada] = {}
        self._estados: dict[str, EstadoDaModificacao] = {}
        self._laco: asyncio.Task[None] | None = None
        self._marca_do_registro: tuple[int, int] | None = None
        self._prctl = _prctl()
        self._gravou_o_estado = False

    # -- o estado ----------------------------------------------------------

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

    # -- ciclo de vida -----------------------------------------------------

    async def iniciar(self) -> None:
        await self.reconciliar()
        self._laco = asyncio.create_task(self._vigiar_o_registro(), name="mods-registro")

    async def parar(self) -> None:
        laco, self._laco = self._laco, None
        if laco is not None:
            laco.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await laco
        await asyncio.gather(
            *(self._parar_uma(mod_id) for mod_id in list(self._vigiadas)),
            return_exceptions=True,
        )
        await self.porta.parar()
        if self._gravou_o_estado:
            with contextlib.suppress(FileNotFoundError):
                self.lugares.estado.unlink()

    async def _vigiar_o_registro(self) -> None:
        while True:
            await asyncio.sleep(self.intervalo_s)
            await self._conferir_o_registro()

    async def _conferir_o_registro(self) -> None:
        """Uma volta da vigia: o registro mudou (outro mtime ou outro inode)?"""
        try:
            if self._marca() != self._marca_do_registro:
                await self.reconciliar()
        except Exception as exc:
            logger.warning("mods_registro_falhou", err=str(exc), exc_info=True)

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
            return
        ligadas = {k: v for k, v in registro.items() if v.ligada}
        for mod_id in [m for m in self._vigiadas if m not in ligadas]:
            await self._parar_uma(mod_id)
        for mod_id in [m for m in self._estados if m not in registro]:
            self._estados.pop(mod_id, None)
        for mod_id, entrada in registro.items():
            if not entrada.ligada:
                self._estados[mod_id] = EstadoDaModificacao("desligada")
        for mod_id, entrada in ligadas.items():
            vigiada = self._vigiadas.get(mod_id)
            if vigiada is None or vigiada.tarefa is None or vigiada.tarefa.done():
                await self._comecar(entrada)
        # Sem modificação instalada, o supervisor não deixa arquivo nenhum.
        if self._estados or self._gravou_o_estado:
            self._gravar_estado()

    # -- uma modificação ---------------------------------------------------

    def _o_que_impede(self, entrada: Entrada) -> tuple[str, Manifesto | None]:
        try:
            manifesto = ler_manifesto(self.lugares.codigo / entrada.id)
        except ManifestoRecusadoError as exc:
            return exc.frase, None
        novas = permissoes_novas(entrada.permissoes_aceitas, manifesto.permissoes)
        if novas:
            return (
                f"«{manifesto.nome}» pede {', '.join(novas)}, que ainda não teve o «sim».",
                None,
            )
        return "", manifesto

    async def _comecar(self, entrada: Entrada) -> None:
        motivo, manifesto = self._o_que_impede(entrada)
        if manifesto is None:
            self._estados[entrada.id] = EstadoDaModificacao("recusada", motivo=motivo)
            return
        if manifesto.processo is None:
            self._estados[entrada.id] = EstadoDaModificacao("declarativa")
            return
        if not self.porta.aberta:
            await self.porta.iniciar()
        vigiada = _Vigiada(entrada.id)
        self._vigiadas[entrada.id] = vigiada
        vigiada.tarefa = asyncio.create_task(
            self._cuidar(vigiada, manifesto), name=f"mods-{entrada.id}"
        )

    async def _cuidar(self, vigiada: _Vigiada, manifesto: Manifesto) -> None:
        mod_id = vigiada.mod_id
        quedas = 0
        diario = self.lugares.dados / mod_id / DIARIO_DA_MODIFICACAO
        caixa = "bwrap" if self.bwrap else ""
        sem_caixa = "" if self.bwrap else "Roda sem caixa: o bwrap não está instalado."
        while not vigiada.quer_parar.is_set():
            self._marcar(mod_id, EstadoDaModificacao(
                "ligando" if quedas == 0 else "voltando",
                caixa=caixa, motivo=sem_caixa, quedas=quedas))
            try:
                processo = await self._abrir(vigiada, manifesto, diario)
            except (OSError, ValueError) as exc:
                self._marcar(mod_id, EstadoDaModificacao(
                    "parou", caixa=caixa, motivo=f"Não abriu: {exc}", quedas=quedas))
                return
            self._marcar(mod_id, EstadoDaModificacao(
                "rodando", pid=processo.pid, caixa=caixa, motivo=sem_caixa, quedas=quedas))
            aberto_em = time.monotonic()
            codigo = await processo.wait()
            self.porta.esquecer(vigiada.ficha)
            if vigiada.quer_parar.is_set():
                return
            if time.monotonic() - aberto_em >= self.estavel_s:
                quedas = 0
            quedas += 1
            ultima = ultima_linha_do_diario(diario)
            logger.warning("mods_caiu", mod=mod_id, codigo=codigo, quedas=quedas)
            if quedas > len(self.esperas):
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

    async def _abrir(
        self, vigiada: _Vigiada, manifesto: Manifesto, diario: Path
    ) -> asyncio.subprocess.Process:
        assert manifesto.processo is not None
        codigo = self.lugares.codigo / manifesto.id
        dados = self.lugares.dados / manifesto.id
        dados.mkdir(parents=True, exist_ok=True)
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
            "HEFESTO_MOD_API": str(API_DAS_MODIFICACOES),
        }
        if execucao_bruta:
            ambiente["XDG_RUNTIME_DIR"] = execucao_bruta
        if self.bwrap:
            # Sem XDG_RUNTIME_DIR, o socket principal mora no cache, dentro da
            # HOME, e o tmpfs dela já o esconde.
            execucao = Path(execucao_bruta) if execucao_bruta else None
            argv = comando_na_caixa(
                bwrap=self.bwrap,
                comando=comando,
                codigo=codigo,
                dados=dados,
                porta=self.porta.caminho,
                manifesto=manifesto,
                casa=casa,
                execucao=execucao,
            )
        else:
            argv = comando
        _aparar_o_diario(diario)
        with diario.open("ab") as saida:
            processo = await asyncio.create_subprocess_exec(
                *argv,
                cwd=str(codigo),
                env=ambiente,
                stdin=asyncio.subprocess.DEVNULL,
                stdout=saida,
                stderr=saida,
                start_new_session=True,
                preexec_fn=_morre_com_o_pai(self._prctl),
            )
        vigiada.processo = processo
        self.porta.registrar(vigiada.ficha, manifesto.id, processo.pid, manifesto.permissoes)
        logger.info("mods_aberta", mod=manifesto.id, pid=processo.pid, caixa=bool(self.bwrap))
        return processo

    async def _parar_uma(self, mod_id: str) -> None:
        vigiada = self._vigiadas.pop(mod_id, None)
        if vigiada is None:
            return
        vigiada.quer_parar.set()
        processo = vigiada.processo
        if processo is not None and processo.returncode is None:
            await parar_o_grupo(processo, self.prazo_para_parar_s)
        if vigiada.tarefa is not None:
            await asyncio.wait({vigiada.tarefa}, timeout=ESPERA_DA_VIGIA_S)
        self.porta.esquecer(vigiada.ficha)
        self._marcar(mod_id, EstadoDaModificacao("desligada"))


async def parar_o_grupo(processo: asyncio.subprocess.Process, prazo: float) -> int | None:
    """``SIGTERM`` ao grupo do PID criado; ``SIGKILL`` no fim do prazo."""
    pid = processo.pid
    with contextlib.suppress(ProcessLookupError, PermissionError):
        os.killpg(pid, signal.SIGTERM)
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


def supervisor_do_servico(daemon: Any) -> Supervisor:
    """O supervisor ligado ao serviço vivo (barramento, IPC e estado do jogo)."""
    from hefesto_dualsense4unix.mods.porta import (
        escritor_do_servico,
        o_jogo_escreve_no_servico,
        uniq_do_posto_no_servico,
    )

    return Supervisor(
        daemon.bus,
        escritor=escritor_do_servico(daemon),
        o_jogo_escreve=o_jogo_escreve_no_servico(daemon),
        uniq_do_posto=uniq_do_posto_no_servico(daemon),
    )


__all__ = [
    "DIARIO_DA_MODIFICACAO",
    "ESCONDIDO_SEM_A_PERMISSAO",
    "ESPERAS_PARA_VOLTAR",
    "ESPERA_DA_VIGIA_S",
    "ESPERA_DEPOIS_DO_SIGKILL_S",
    "ESTAVEL_DEPOIS_DE_S",
    "PRAZO_PARA_PARAR_S",
    "EstadoDaModificacao",
    "Supervisor",
    "comando_na_caixa",
    "parar_o_grupo",
    "supervisor_do_servico",
    "ultima_linha_do_diario",
]
