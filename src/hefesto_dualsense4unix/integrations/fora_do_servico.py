"""O aplicativo da pessoa nasce FORA do serviço do Hefesto — STEAM-FORA-DO-SERVICO-01.

**O DEFEITO, medido em 26/09/2026** (estudo do engasgo do Sackboy, §3.4, e a
conferência, §6): o botão PS abriu a Steam por ``Popen`` de dentro do daemon.
A Steam e o jogo nasceram no cgroup ``hefesto-dualsense4unix.service``, com o
``nice 5`` do daemon (``daemon/main.py``) e o ``oom_score_adj 200`` que o
gerenciador de usuário dá a todo serviço dele. E a unit mata o grupo inteiro
ao parar (``KillMode=control-group``, o padrão): o restart que o install faz
derrubava a Steam e o jogo abertos pelo botão.

**A FORMA FOI ESCOLHIDA POR MEDIÇÃO**, não pelo manual (26/09/2026, 18h03): um
processo em ``nice 5`` e ``oom 200`` abriu ``sh -c 'sleep 60 & exec sleep 3'``
de sete jeitos, e o neto de longa vida foi lido em ``/proc``:

======================================  ====  ===  ==================================
forma                                   nice  oom  o neto, depois de o principal sair
======================================  ====  ===  ==================================
``Popen`` de hoje                       5     200  vive, no cgroup de quem chamou
``systemd-run --user --scope``          5     200  vive (o scope é filho do chamador)
serviço transitório, padrão             0     200  **MORTO** junto com o principal
serviço + ``ExitType=cgroup``           0     200  vive, unidade ativa
serviço + ``KillMode=process``          0     200  vive, unidade dada como morta
serviço + ``OOMScoreAdjust=100``        0     100  vive
serviço + ``OOMScoreAdjust=0``          0     100  vive — o kernel não desce abaixo
======================================  ====  ===  ==================================

Daí a forma: **serviço transitório** do gerenciador de usuário (nasce dele, e
não de quem chama), ``Type=exec`` (o ``systemd-run`` só volta depois do
``execve``, e um binário ausente volta como erro), ``ExitType=cgroup`` (um
lançador que se bifurca e sai não leva a Steam junto; o ``ExitType`` é do
systemd 250 — antes dele, ``KillMode=process``, medido com o mesmo efeito) e
``OOMScoreAdjust`` igual ao do próprio gerenciador. O ``0`` que os
aplicativos do painel têm é inalcançável daqui: o gerenciador nasce do PID 1
com ``100``, e esse é o piso de tudo o que descende dele (medido acima).

**O AMBIENTE VAI JUNTO, e só o que é da pessoa.** O serviço nasce com o
ambiente do gerenciador; o de quem chama (já passado por
``ambiente_do_jogo.ambiente_limpo``) vai por ``--setenv``, e a classe do
interpretador sai também do lado do gerenciador (``UnsetEnvironment=``). Não
vão as variáveis que o systemd escreve PARA UMA UNIDADE (``INVOCATION_ID``,
``JOURNAL_STREAM``, ``MEMORY_PRESSURE_WATCH``…): as do daemon apontariam a
Steam para o diário e a pressão de memória de outro serviço.

**QUANDO NÃO HÁ O QUE CURAR, NADA MUDA.** Quem chama de um lugar que já é da
pessoa — a janela aberta pelo painel, num scope com ``nice 0`` e ``oom 0`` —
abre por ``Popen`` como sempre: o filho herda o que a pessoa tem, e o
gerenciador só teria o ``100`` a oferecer. Sem systemd de usuário, também
``Popen`` (``start_new_session=True``), o de hoje.

**SOB A SUÍTE, O ``systemd-run`` DE VERDADE RECUSA.** Ele fala com o
gerenciador pelo soquete ``$XDG_RUNTIME_DIR/systemd/private``, que nenhum
barramento de mentira desvia: um teste que chegasse a ele abriria unidade na
sessão de quem roda a suíte. Quem testa injeta ``executar``.

Módulo 100% stdlib DE PROPÓSITO: ``steam_launch_options`` o importa, e o
install/uninstall rodam aquele arquivo como script avulso.
"""
from __future__ import annotations

import os
import re
import secrets
import shutil
import subprocess
import sys
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

try:  # importado como módulo do pacote (GUI/daemon/testes)
    from .ambiente_do_jogo import VARIAVEIS_DO_INTERPRETADOR
except ImportError:  # pragma: no cover - executado como script avulso pelo install/uninstall
    from ambiente_do_jogo import VARIAVEIS_DO_INTERPRETADOR  # type: ignore[no-redef]

#: O que o systemd escreve no ambiente de UMA unidade (``systemd.exec(5)``,
#: «Environment Variables in Spawned Processes»). As do daemon não são da
#: Steam; a unidade nova ganha as dela.
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
#: sair, na ordem em que se tentam: a do systemd 250 em diante, e a de antes.
FORMAS_DE_VIVER: tuple[str, ...] = ("ExitType=cgroup", "KillMode=process")

#: Prefixo do nome da unidade: ``app-hefesto-<aplicativo>-<acaso>.service``.
#: Sem o ``@`` de instância de propósito — medido em 26/09: com ele o
#: gerenciador cria uma fatia por aplicativo (``app-app\\x2dhefesto…slice``)
#: que fica ativa, vazia, depois de o aplicativo fechar.
PREFIXO_DA_UNIDADE = "app-hefesto-"

#: Quanto se espera o ``systemd-run`` voltar. Medido em 26/09: 6 a 12 ms ele
#: sozinho, 12 a 20 ms o ``abrir`` inteiro. O teto é o do ``pgrep`` e do
#: ``wmctrl`` do mesmo toque (``steam_launcher``): o botão PS chama isto INLINE
#: no laço de leitura do daemon, e um gerenciador que não responde seguraria a
#: entrada dos quatro controles pelo tempo inteiro da espera.
ESPERA_DO_SYSTEMD_RUN_S = 2.0

#: ``systemd-run`` recusa nome de variável fora disto (medido com
#: ``BASH_FUNC_x%%``: «Cannot assign environment variable»).
_NOME_DE_VARIAVEL = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

#: Caracteres de controle que um systemd antigo recusa no valor (o
#: ``Environment=`` de antes do 245 aceitava só a tabulação).
_CONTROLE = re.compile(r"[\x00-\x08\x0a-\x1f\x7f]")

_PARTE_DO_NOME = re.compile(r"[^A-Za-z0-9_.]+")


@dataclass(frozen=True)
class Contexto:
    """O que decide a forma: o que um filho direto herdaria, e a quem pedir."""

    #: Há gerenciador de usuário a quem pedir (``systemd-run`` e o soquete dele).
    gerenciador: bool
    #: Por que um filho direto herdaria o que não é da pessoa, ou None.
    herdaria: str | None
    #: O ``oom_score_adj`` do gerenciador, que é o piso da árvore dele.
    oom_do_gerenciador: int | None


@dataclass(frozen=True)
class Abertura:
    """Como o aplicativo saiu. ``unidade`` só quando nasceu fora."""

    caminho: str  # "unidade" | "popen"
    motivo: str
    unidade: str | None = None
    tentativas: tuple[str, ...] = field(default_factory=tuple)
    variaveis_fora: tuple[str, ...] = field(default_factory=tuple)


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
    """O ``oom_score_adj`` do gerenciador de usuário, ou None.

    Primeiro pelo ``MANAGERPID`` que o gerenciador põe no ambiente dos
    serviços dele; fora de um serviço, pelo ``init.scope`` do
    ``user@<uid>.service`` no caminho do próprio cgroup.
    """
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
    """Por que um filho DIRETO deste processo herdaria o que não é da pessoa.

    Três respostas, cada uma medida: dentro de um SERVIÇO o filho morre com o
    restart dele; com ``nice`` acima de zero o filho nasce com ele; com
    ``oom_score_adj`` acima do piso do gerenciador, também. None = o filho
    direto já nasce com o que a pessoa tem.
    """
    ultimo = (cgroup or "").rstrip("/").rsplit("/", 1)[-1]
    if ultimo.endswith(".service"):
        return f"dentro do serviço {ultimo}"
    if nice is not None and nice > 0:
        return f"nice {nice}"
    if oom is not None and oom_do_gerenciador is not None and oom > oom_do_gerenciador:
        return f"oom_score_adj {oom}"
    return None


def ambiente_da_unidade(env: Mapping[str, str]) -> tuple[dict[str, str], tuple[str, ...]]:
    """O que vai por ``--setenv``, e os nomes que ficam de fora.

    Saem as variáveis da unidade de quem chama, as da classe do interpretador
    (quem chama já as tirou, e a régua cobra) e as que o ``systemd-run``
    recusaria — nome fora de ``[A-Za-z_][A-Za-z0-9_]*``, valor com caractere de
    controle ou que não é UTF-8. Uma recusada derrubaria a abertura inteira.
    """
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
) -> list[str]:
    """A linha do ``systemd-run`` que abre ``argv`` numa unidade própria.

    O ``$`` do comando vira ``$$``: o gerenciador expande ``$NOME`` no
    ``ExecStart`` de todo serviço, e um argumento da pessoa não é variável.
    """
    cmd = [
        "systemd-run",
        "--user",
        f"--unit={unidade}",
        f"--description={os.path.basename(argv[0])}, aberto pelo Hefesto",
        "--collect",
        "--quiet",
        "--property=Type=exec",
        f"--property={forma}",
        # O `DEVNULL` do `Popen` de sempre: sem isto a saída do aplicativo iria
        # para o diário (o padrão de todo serviço), e a Steam fala muito.
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
    """Abre ``argv`` com o ambiente ``env``, fora do serviço quando é preciso.

    ``aplicativo`` dá nome à unidade (o id do flatpak diz mais que
    ``flatpak``); sem ele, o nome do programa. Nunca espera o aplicativo.
    Levanta só o que o ``Popen`` de hoje levantaria (``FileNotFoundError`` e
    ``OSError``), e só quando ele é o caminho.
    """
    ctx = contexto if contexto is not None else contexto_atual()
    abrir_direto = popen if popen is not None else subprocess.Popen

    def _pelo_popen(motivo: str, tentativas: tuple[str, ...] = ()) -> Abertura:
        abrir_direto(
            list(argv),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
            env=dict(env),
        )
        return Abertura(caminho="popen", motivo=motivo, tentativas=tentativas)

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
            # A unidade pode ter nascido: abrir de novo por Popen daria duas.
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


__all__ = [
    "FORMAS_DE_VIVER",
    "PREFIXO_DA_UNIDADE",
    "VARIAVEIS_DA_UNIDADE",
    "Abertura",
    "Contexto",
    "abrir",
    "ambiente_da_unidade",
    "argv_da_unidade",
    "contexto_atual",
    "motivo_de_herdar",
    "nome_da_unidade",
    "oom_do_gerenciador",
]
