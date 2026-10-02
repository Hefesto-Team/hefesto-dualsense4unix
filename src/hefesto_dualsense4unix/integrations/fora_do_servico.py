"""O aplicativo da pessoa nasce FORA do serviço do Hefesto — STEAM-FORA-DO-SERVICO-01."""
from __future__ import annotations

import contextlib
import os
import re
import secrets
import shutil
import subprocess
import sys
import threading
import time
from collections import deque
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

try:
    from .ambiente_do_jogo import VARIAVEIS_DO_INTERPRETADOR
except ImportError:  # pragma: no cover - executado como script avulso pelo install/uninstall
    from ambiente_do_jogo import VARIAVEIS_DO_INTERPRETADOR  # type: ignore[no-redef]

VARIAVEIS_DA_UNIDADE: tuple[str, ...] = (
    "INVOCATION_ID",
    "JOURNAL_STREAM",
    "MANAGERPID",
    "SYSTEMD_EXEC_PID",
    "MAINPID",
    "NOTIFY_SOCKET",
    "WATCHDOG_PID",
    "WATCHDOG_USEC",
    "LISTEN_FDS",
    "LISTEN_PID",
    "LISTEN_FDNAMES",
    "LOG_NAMESPACE",
    "MEMORY_PRESSURE_WATCH",
    "MEMORY_PRESSURE_WRITE",
    "RUNTIME_DIRECTORY",
    "STATE_DIRECTORY",
    "CACHE_DIRECTORY",
    "LOGS_DIRECTORY",
    "CONFIGURATION_DIRECTORY",
    "CREDENTIALS_DIRECTORY",
    "SERVICE_RESULT",
    "EXIT_CODE",
    "EXIT_STATUS",
    "MONITOR_SERVICE_RESULT",
    "MONITOR_EXIT_CODE",
    "MONITOR_EXIT_STATUS",
    "MONITOR_INVOCATION_ID",
    "MONITOR_UNIT",
    "PIDFILE",
    "FDSTORE",
    "REMOTE_ADDR",
    "REMOTE_PORT",
    "TRIGGER_UNIT",
    "TRIGGER_PATH",
    "TRIGGER_TIMER_REALTIME_USEC",
    "TRIGGER_TIMER_MONOTONIC_USEC",
)

#: As duas formas de o serviço deixar o lançador viver depois de o principal
FORMAS_DE_VIVER: tuple[str, ...] = ("ExitType=cgroup", "KillMode=process")

PREFIXO_DA_UNIDADE = "app-hefesto-"

ESPERA_DO_SYSTEMD_RUN_S = 2.0

_NOME_DE_VARIAVEL = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

_CONTROLE = re.compile(r"[\x00-\x08\x0a-\x1f\x7f]")

_PARTE_DO_NOME = re.compile(r"[^A-Za-z0-9_.]+")


@dataclass(frozen=True)
class Contexto:
    """O que decide a forma: o que um filho direto herdaria, e a quem pedir."""

    gerenciador: bool
    herdaria: str | None
    oom_do_gerenciador: int | None


@dataclass(frozen=True)
class Abertura:
    """Como o aplicativo saiu. ``unidade`` só quando nasceu fora."""

    caminho: str
    motivo: str
    unidade: str | None = None
    tentativas: tuple[str, ...] = field(default_factory=tuple)
    variaveis_fora: tuple[str, ...] = field(default_factory=tuple)
    processo: Any = field(default=None, compare=False, repr=False)


def _ler(caminho: str | Path) -> str | None:
    try:
        return Path(caminho).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None


def _cgroup_de(texto: str | None) -> str | None:
    """O caminho do cgroup v2 (linha ``0::``) de um ``/proc/<pid>/cgroup``."""
    for linha in (texto or "").splitlines():
        if linha.startswith("0::"):
            return linha[3:].strip()
    return None


def _nice_de(texto_do_stat: str | None) -> int | None:
    """O campo ``nice`` (19º) de um ``/proc/<pid>/stat``."""
    if not texto_do_stat or ")" not in texto_do_stat:
        return None
    campos = texto_do_stat[texto_do_stat.rindex(")") + 2 :].split()
    try:
        return int(campos[16])
    except (IndexError, ValueError):
        return None


def _inteiro(texto: str | None) -> int | None:
    try:
        return int((texto or "").strip())
    except ValueError:
        return None


def oom_do_gerenciador(
    *,
    cgroup: str | None,
    environ: Mapping[str, str],
    raiz_proc: str = "/proc",
    raiz_cgroup: str = "/sys/fs/cgroup",
) -> int | None:
    """O ``oom_score_adj`` do gerenciador de usuário, ou None."""
    pid = _inteiro(environ.get("MANAGERPID"))
    if pid is not None:
        valor = _inteiro(_ler(f"{raiz_proc}/{pid}/oom_score_adj"))
        if valor is not None:
            return valor
    if cgroup:
        partes = cgroup.strip("/").split("/")
        for i, parte in enumerate(partes):
            if re.fullmatch(r"user@\d+\.service", parte):
                base = "/".join(partes[: i + 1])
                procs = _ler(f"{raiz_cgroup}/{base}/init.scope/cgroup.procs") or ""
                for linha in procs.split():
                    valor = _inteiro(_ler(f"{raiz_proc}/{linha}/oom_score_adj"))
                    if valor is not None:
                        return valor
                break
    return None


def _ha_gerenciador(environ: Mapping[str, str]) -> bool:
    if shutil.which("systemd-run") is None:
        return False
    runtime = environ.get("XDG_RUNTIME_DIR") or f"/run/user/{os.getuid()}"
    return os.path.exists(os.path.join(runtime, "systemd", "private"))


def contexto_atual(
    *,
    environ: Mapping[str, str] | None = None,
    raiz_proc: str = "/proc",
    raiz_cgroup: str = "/sys/fs/cgroup",
) -> Contexto:
    """O contexto deste processo, lido de ``/proc/self``. Nunca levanta."""
    env = os.environ if environ is None else environ
    cgroup = _cgroup_de(_ler(f"{raiz_proc}/self/cgroup"))
    nice = _nice_de(_ler(f"{raiz_proc}/self/stat"))
    oom = _inteiro(_ler(f"{raiz_proc}/self/oom_score_adj"))
    do_gerenciador = oom_do_gerenciador(
        cgroup=cgroup, environ=env, raiz_proc=raiz_proc, raiz_cgroup=raiz_cgroup
    )
    return Contexto(
        gerenciador=_ha_gerenciador(env),
        herdaria=motivo_de_herdar(
            cgroup=cgroup, nice=nice, oom=oom, oom_do_gerenciador=do_gerenciador
        ),
        oom_do_gerenciador=do_gerenciador,
    )


def motivo_de_herdar(
    *,
    cgroup: str | None,
    nice: int | None,
    oom: int | None,
    oom_do_gerenciador: int | None,
) -> str | None:
    """Por que um filho DIRETO deste processo herdaria o que não é da pessoa."""
    ultimo = (cgroup or "").rstrip("/").rsplit("/", 1)[-1]
    if ultimo.endswith(".service"):
        return f"dentro do serviço {ultimo}"
    if nice is not None and nice > 0:
        return f"nice {nice}"
    if oom is not None and oom_do_gerenciador is not None and oom > oom_do_gerenciador:
        return f"oom_score_adj {oom}"
    return None


def ambiente_da_unidade(env: Mapping[str, str]) -> tuple[dict[str, str], tuple[str, ...]]:
    """O que vai por ``--setenv``, e os nomes que ficam de fora."""
    mantidas: dict[str, str] = {}
    fora: list[str] = []
    for nome, valor in env.items():
        if nome in VARIAVEIS_DA_UNIDADE or nome in VARIAVEIS_DO_INTERPRETADOR:
            fora.append(nome)
            continue
        if not _NOME_DE_VARIAVEL.match(nome) or _CONTROLE.search(valor):
            fora.append(nome)
            continue
        try:
            valor.encode("utf-8")
        except UnicodeEncodeError:
            fora.append(nome)
            continue
        mantidas[nome] = valor
    return mantidas, tuple(sorted(fora))


def nome_da_unidade(aplicativo: str, acaso: str | None = None) -> str:
    """``app-hefesto-<aplicativo>-<acaso>.service``, só com caracteres seguros."""
    parte = _PARTE_DO_NOME.sub("_", os.path.basename(aplicativo)).strip("_.") or "app"
    return f"{PREFIXO_DA_UNIDADE}{parte}-{acaso or secrets.token_hex(6)}.service"


def argv_da_unidade(
    argv: Sequence[str],
    env: Mapping[str, str],
    *,
    unidade: str,
    forma: str,
    oom: int | None,
    teto_s: int | None = None,
) -> list[str]:
    """A linha do ``systemd-run`` que abre ``argv`` numa unidade própria."""
    cmd = [
        "systemd-run",
        "--user",
        f"--unit={unidade}",
        f"--description={os.path.basename(argv[0])}, aberto pelo Hefesto",
        "--collect",
    ]
    if teto_s is None:
        cmd.append("--quiet")
    else:
        cmd.extend(["--wait", f"--property=RuntimeMaxSec={int(teto_s)}"])
    cmd += [
        "--property=Type=exec",
        f"--property={forma}",
        "--property=StandardOutput=null",
        "--property=StandardError=null",
    ]
    if oom is not None:
        cmd.append(f"--property=OOMScoreAdjust={oom}")
    cmd.append("--property=UnsetEnvironment=" + " ".join(VARIAVEIS_DO_INTERPRETADOR))
    cmd.extend(f"--setenv={nome}={valor}" for nome, valor in env.items())
    cmd.append("--")
    cmd.extend(a.replace("$", "$$") for a in argv)
    return cmd


def _a_suite_esta_rodando() -> bool:
    """A mesma pergunta de ``bluez_dbus.a_suite_esta_rodando``, sem escape."""
    return bool(os.environ.get("PYTEST_CURRENT_TEST")) or "pytest" in sys.modules


def _executar_de_verdade(
    cmd: Sequence[str], env: Mapping[str, str]
) -> subprocess.CompletedProcess[str]:
    if _a_suite_esta_rodando():
        raise OSError("a suíte está no ar e este é o gerenciador de verdade")
    return subprocess.run(
        list(cmd),
        capture_output=True,
        text=True,
        timeout=ESPERA_DO_SYSTEMD_RUN_S,
        env=dict(env),
        stdin=subprocess.DEVNULL,
        check=False,
    )


Executar = Callable[[Sequence[str], Mapping[str, str]], "subprocess.CompletedProcess[str]"]


def abrir(
    argv: Sequence[str],
    *,
    env: Mapping[str, str],
    aplicativo: str | None = None,
    contexto: Contexto | None = None,
    executar: Executar | None = None,
    popen: Callable[..., Any] | None = None,
) -> Abertura:
    """Abre ``argv`` com o ambiente ``env``, fora do serviço quando é preciso."""
    # `ps_button_command` chega assim de um `daemon.reload` com texto;
    argv = [argv] if isinstance(argv, str) else list(argv)
    ctx = contexto if contexto is not None else contexto_atual()
    abrir_direto = popen if popen is not None else subprocess.Popen

    def _pelo_popen(motivo: str, tentativas: tuple[str, ...] = ()) -> Abertura:
        processo = abrir_direto(
            list(argv),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
            env=dict(env),
        )
        return Abertura(
            caminho="popen", motivo=motivo, tentativas=tentativas, processo=processo
        )

    if ctx.herdaria is None:
        return _pelo_popen("quem chama já é da pessoa")
    if not ctx.gerenciador:
        return _pelo_popen(f"sem systemd de usuário ({ctx.herdaria})")

    run = executar if executar is not None else _executar_de_verdade
    do_setenv, fora = ambiente_da_unidade(env)
    tentativas: list[str] = []
    for forma in FORMAS_DE_VIVER:
        unidade = nome_da_unidade(aplicativo or argv[0])
        cmd = argv_da_unidade(
            argv, do_setenv, unidade=unidade, forma=forma, oom=ctx.oom_do_gerenciador
        )
        try:
            feito = run(cmd, env)
        except subprocess.TimeoutExpired:
            return Abertura(
                caminho="unidade",
                motivo=f"o systemd-run não respondeu em {ESPERA_DO_SYSTEMD_RUN_S:.0f} s",
                unidade=unidade,
                tentativas=(*tentativas, f"{forma}: sem resposta"),
                variaveis_fora=fora,
            )
        except OSError as erro:
            tentativas.append(f"{forma}: {erro}")
            break
        if feito.returncode == 0:
            return Abertura(
                caminho="unidade",
                motivo=ctx.herdaria,
                unidade=unidade,
                tentativas=tuple(tentativas),
                variaveis_fora=fora,
            )
        erro_dito = (feito.stderr or "").strip().splitlines()
        tentativas.append(f"{forma}: rc={feito.returncode} {erro_dito[-1] if erro_dito else ''}")
    return _pelo_popen(f"o systemd-run recusou ({ctx.herdaria})", tuple(tentativas))


FOLGA_DO_TETO_S = 5.0

_O_FIM_DA_UNIDADE = re.compile(r"Finished with result:\s*(\S+)")


@dataclass(frozen=True)
class Desfecho:
    """Como o programa esperado terminou."""

    rodou: bool
    saiu_com: int | None
    estourou: bool
    caminho: str
    motivo: str = ""
    tentativas: tuple[str, ...] = field(default_factory=tuple)


def _executar_esperando(teto_s: float) -> Executar:
    def _run(cmd: Sequence[str], env: Mapping[str, str]) -> subprocess.CompletedProcess[str]:
        if _a_suite_esta_rodando():
            raise OSError("a suíte está no ar e este é o gerenciador de verdade")
        return subprocess.run(
            list(cmd),
            capture_output=True,
            text=True,
            timeout=teto_s + FOLGA_DO_TETO_S,
            env=dict(env),
            stdin=subprocess.DEVNULL,
            check=False,
        )

    return _run


def _esperar_pelo_popen(
    argv: Sequence[str],
    env: Mapping[str, str],
    teto_s: float,
    abrir_direto: Callable[..., Any],
    motivo: str,
    tentativas: tuple[str, ...],
) -> Desfecho:
    """O caminho sem gerenciador: o ``Popen`` com o mesmo teto."""
    try:
        processo = abrir_direto(
            list(argv),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
            env=dict(env),
        )
    except OSError as erro:
        return Desfecho(False, None, False, "nenhum", str(erro), tentativas)
    try:
        codigo = processo.wait(timeout=teto_s)
    except subprocess.TimeoutExpired:
        for sinal in (15, 9):
            with contextlib.suppress(OSError):
                os.killpg(processo.pid, sinal)
            try:
                processo.wait(timeout=2.0)
                break
            except subprocess.TimeoutExpired:
                continue
        return Desfecho(True, None, True, "popen", motivo, tentativas)
    return Desfecho(True, int(codigo), False, "popen", motivo, tentativas)


def rodar_e_esperar(
    argv: Sequence[str],
    *,
    env: Mapping[str, str],
    teto_s: float,
    aplicativo: str | None = None,
    contexto: Contexto | None = None,
    executar: Executar | None = None,
    popen: Callable[..., Any] | None = None,
) -> Desfecho:
    """Roda ``argv`` fora do serviço, ESPERA ele terminar, e diz como terminou."""
    argv = list(argv)
    ctx = contexto if contexto is not None else contexto_atual()
    if popen is None and _a_suite_esta_rodando():
        abrir_direto: Callable[..., Any] = _recusar_sob_a_suite
    else:
        abrir_direto = popen if popen is not None else subprocess.Popen
    if ctx.herdaria is None:
        return _esperar_pelo_popen(argv, env, teto_s, abrir_direto,
                                   "quem chama já é da pessoa", ())
    if not ctx.gerenciador:
        return _esperar_pelo_popen(argv, env, teto_s, abrir_direto,
                                   f"sem systemd de usuário ({ctx.herdaria})", ())

    run = executar if executar is not None else _executar_esperando(teto_s)
    do_setenv, _fora = ambiente_da_unidade(env)
    tentativas: list[str] = []
    for forma in FORMAS_DE_VIVER:
        unidade = nome_da_unidade(aplicativo or argv[0])
        cmd = argv_da_unidade(
            argv, do_setenv, unidade=unidade, forma=forma,
            oom=ctx.oom_do_gerenciador, teto_s=int(teto_s),
        )
        try:
            feito = run(cmd, env)
        except subprocess.TimeoutExpired:
            return Desfecho(True, None, True, "unidade", ctx.herdaria,
                            (*tentativas, f"{forma}: sem resposta"))
        except OSError as erro:
            tentativas.append(f"{forma}: {erro}")
            break
        fim = _O_FIM_DA_UNIDADE.search(feito.stderr or "")
        if feito.returncode == 0:
            return Desfecho(True, 0, False, "unidade", ctx.herdaria, tuple(tentativas))
        if fim is not None:
            estourou = fim.group(1) == "timeout"
            return Desfecho(True, None if estourou else int(feito.returncode),
                            estourou, "unidade", ctx.herdaria, tuple(tentativas))
        erro_dito = (feito.stderr or "").strip().splitlines()
        tentativas.append(f"{forma}: rc={feito.returncode} {erro_dito[-1] if erro_dito else ''}")
    return _esperar_pelo_popen(argv, env, teto_s, abrir_direto,
                               f"o systemd-run recusou ({ctx.herdaria})", tuple(tentativas))


def _recusar_sob_a_suite(*_args: Any, **_kwargs: Any) -> Any:
    raise OSError("a suíte está no ar e este é o Popen de verdade")


RAIZ_DO_CGROUP = "/sys/fs/cgroup"
RAIZ_DO_PROC = "/proc"


def _base_do_gerenciador(raiz_proc: str) -> str:
    """O cgroup do ``user@<uid>.service`` de quem chama, sem a barra inicial."""
    proprio = _cgroup_de(_ler(f"{raiz_proc}/self/cgroup")) or ""
    partes = proprio.strip("/").split("/")
    for i, parte in enumerate(partes):
        if re.fullmatch(r"user@\d+\.service", parte):
            return "/".join(partes[: i + 1])
    uid = os.getuid()
    return f"user.slice/user-{uid}.slice/user@{uid}.service"


def _pids_de(arquivo: str) -> tuple[int, ...] | None:
    """Os PIDs de um ``cgroup.procs``, ou None quando a pasta não existe."""
    texto = _ler(arquivo)
    if texto is None:
        return None
    return tuple(int(linha) for linha in texto.split() if linha.isdigit())


def pids_da_unidade(
    unidade: str,
    *,
    raiz_cgroup: str | None = None,
    raiz_proc: str | None = None,
) -> tuple[int, ...]:
    """Quem está de pé na unidade que ``abrir`` criou, pergunta feita ao kernel."""
    if not unidade.startswith(PREFIXO_DA_UNIDADE) or "/" in unidade:
        return ()
    cgroup = RAIZ_DO_CGROUP if raiz_cgroup is None else raiz_cgroup
    proc = RAIZ_DO_PROC if raiz_proc is None else raiz_proc
    base = os.path.join(cgroup, _base_do_gerenciador(proc))
    pastas = [os.path.join(base, "app.slice", unidade), os.path.join(base, unidade)]
    try:
        with os.scandir(base) as entradas:
            pastas.extend(
                os.path.join(e.path, unidade)
                for e in entradas
                if e.name.endswith(".slice") and e.name != "app.slice" and e.is_dir()
            )
    except OSError:
        pass
    for pasta in pastas:
        pids = _pids_de(os.path.join(pasta, "cgroup.procs"))
        if pids is not None:
            return pids
    achados: list[int] = []
    try:
        nomes = os.listdir(proc)
    except OSError:
        return ()
    for nome in nomes:
        if nome.isdigit() and _esta_na_unidade(_ler(f"{proc}/{nome}/cgroup"), unidade):
            achados.append(int(nome))
    return tuple(sorted(achados))


def _esta_na_unidade(texto: str | None, unidade: str) -> bool:
    """Alguma hierarquia de um ``/proc/<pid>/cgroup`` termina na unidade."""
    for linha in (texto or "").splitlines():
        caminho = linha.split(":", 2)[-1].strip().rstrip("/")
        if caminho and caminho.rsplit("/", 1)[-1] == unidade:
            return True
    return False


class FioDeTrabalho:
    """O laço de leitura dispara, e quem espera o gerenciador é este fio."""

    def __init__(
        self,
        nome: str,
        *,
        espera: int = 0,
        ao_falhar: Callable[[BaseException], object] | None = None,
    ) -> None:
        self.nome = nome
        self._espera = max(0, int(espera))
        self._ao_falhar = ao_falhar
        self._tranca = threading.Lock()
        self._fila: deque[Callable[[], object]] = deque()
        self._fio: threading.Thread | None = None

    def disparar(self, alvo: Callable[[], object]) -> bool:
        """Põe ``alvo`` no fio. False (e nada corre) quando não cabe."""
        with self._tranca:
            ocupado = self._fio is not None
            if ocupado and len(self._fila) >= self._espera:
                return False
            self._fila.append(alvo)
            if ocupado:
                return True
            fio = threading.Thread(target=self._drenar, name=self.nome, daemon=True)
            self._fio = fio
        fio.start()
        return True

    def _drenar(self) -> None:
        while True:
            with self._tranca:
                if not self._fila:
                    self._fio = None
                    return
                alvo = self._fila.popleft()
            try:
                alvo()
            except Exception as erro:
                if self._ao_falhar is not None:
                    with contextlib.suppress(Exception):
                        self._ao_falhar(erro)

    def no_fio(self) -> bool:
        """Quem pergunta é o próprio fio (e não pode esperar por si)."""
        return threading.current_thread() is self._fio

    def descartar(self) -> int:
        """Tira da fila o que ainda não começou. Devolve quantos saíram."""
        with self._tranca:
            quantos = len(self._fila)
            self._fila.clear()
        return quantos

    def esperar(self, teto: float | None = None) -> bool:
        """Espera o fio esvaziar. True = nada em voo nem na fila."""
        limite = None if teto is None else time.monotonic() + teto
        while True:
            with self._tranca:
                fio = self._fio
            if fio is None:
                return True
            if fio is threading.current_thread():
                return False
            resta = None if limite is None else limite - time.monotonic()
            if resta is not None and resta <= 0:
                return False
            fio.join(resta)


__all__ = [
    "FORMAS_DE_VIVER",
    "PREFIXO_DA_UNIDADE",
    "VARIAVEIS_DA_UNIDADE",
    "Abertura",
    "Contexto",
    "Desfecho",
    "FioDeTrabalho",
    "abrir",
    "ambiente_da_unidade",
    "argv_da_unidade",
    "contexto_atual",
    "motivo_de_herdar",
    "nome_da_unidade",
    "oom_do_gerenciador",
    "pids_da_unidade",
    "rodar_e_esperar",
]
