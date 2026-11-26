"""A porta das modificações: ``$XDG_RUNTIME_DIR/hefesto-dualsense4unix/mods.sock``.

Nunca o socket principal: o enquadramento é o do IPC (um JSON-RPC 2.0 por linha), e a
tabela de métodos é pequena e fechada. ``mod.ola`` confere a ficha e o ``SO_PEERCRED``;
cada leitura pede ``ler:<tópico>``, cada publicação ``publicar:<tópico>``, cada escrita
``escrever:<canal>`` com o ``uniq`` de um controle e nunca num canal que o jogo escreve;
``lancador.jogos`` pede ``lancador``, e ``lancador.abrir``, ``pedir:lancador.abrir``. Cada
assinatura é uma fila do barramento que descarta o mais antigo quando enche; a de ``botoes``
junta as bordas de um botão e nunca perde a última. O contrato inteiro, com a vibração que se
solta na queda, está em ``docs/protocol/porta-das-modificacoes.md``.
"""
from __future__ import annotations

import asyncio
import contextlib
import dataclasses
import hashlib
import hmac
import inspect
import json
import math
import os
import re
import secrets
import shutil
import socket
import struct
import tempfile
import time
from collections import deque
from collections.abc import Awaitable, Callable, Coroutine, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from hefesto_dualsense4unix.core.events import DEFAULT_QUEUE_MAXSIZE, EventBus, EventTopic
from hefesto_dualsense4unix.core.roteador_de_movimento import PESO_DA_MIRA, TODOS_OS_CONTROLES
from hefesto_dualsense4unix.core.virtual_motion import chave_de_sensor
from hefesto_dualsense4unix.daemon.ipc_rumble_policy import ESCALA_DA_VIBRACAO
from hefesto_dualsense4unix.daemon.protocolo_do_ipc import (
    CODE_INVALID_PARAMS,
    CODE_INVALID_REQUEST,
    CODE_METHOD_NOT_FOUND,
    CODE_PARSE_ERROR,
    MAX_PAYLOAD_BYTES,
    PROTOCOL_VERSION,
)
from hefesto_dualsense4unix.integrations.leitor_do_estado import (
    TOPICO_DA_MEMORIA,
    ChavesDaMemoria,
    LeituraRecusadaError,
    anticheat_do_jogo,
    arquivo_das_chaves,
    caminho_do_soquete,
    entradas_da_receita,
)
from hefesto_dualsense4unix.integrations.tela_do_jogo import (
    HZ_DA_TELA,
    TOPICO_DA_TELA,
    Captura,
    FonteDaTela,
    Regiao,
    TelaDoJogo,
    TelaRecusadaError,
    fonte_do_sistema,
    regioes_da_receita,
)
from hefesto_dualsense4unix.mods import API_DAS_MODIFICACOES
from hefesto_dualsense4unix.mods.manifesto import (
    FUNCOES_POR_PEDIDO,
    NOME_DA_FUNCAO,
    PERMISSOES_DO_ESTADO,
    TOPICOS_DE_LEITURA,
    TOPICOS_DE_PUBLICACAO,
)
from hefesto_dualsense4unix.profiles.loader import gesto_de_agora
from hefesto_dualsense4unix.profiles.schema import extensao_do_modo
from hefesto_dualsense4unix.utils.logging_config import get_logger
from hefesto_dualsense4unix.utils.maquina import _CHAVE_DE_LANCADOR

logger = get_logger(__name__)

CODE_SEM_PERMISSAO = -32010
CODE_O_JOGO_ESCREVE = -32011
CODE_QUEM_E_VOCE = -32012
CODE_NAO_ESCREVEU = -32013
CODE_TETO_CHEIO = -32014
CODE_SEM_PONTE = -32015

JANELA_DA_VIBRACAO_DO_JOGO_S = 2.0

PUBLICACOES_POR_SEGUNDO = 20
APARELHOS_POR_SEGUNDO = 4

PRAZO_PARA_FECHAR_S = 2.0
PRAZO_DA_CAPTURA_SAIR_S = 2.0

JOGOS_POR_LANCADOR = 5000

ESTADOS_DO_ACESSORIO = ("ligado", "procurando", "desligado", "falhou")
ESTADOS_DA_CONEXAO = (*ESTADOS_DO_ACESSORIO, "esperando")
TRANSPORTES_DA_CONEXAO = ("usb", "bluetooth", "rede", "local")
TEXTO_DA_ACAO = 120
ITENS_DO_ESTADO = 32
ESCOLHAS_DA_CONEXAO = 8
LINHAS_DO_AGORA = 6
ROTULO_DA_LINHA = 20
VALOR_DA_LINHA = 40
SITUACOES = ("tocando", "calado", "esperando")
FRASE_DA_SITUACAO = 120
FRASE_DA_LEITURA = 60
CONTROLES_DO_APARELHO = 6
TIPOS_DO_CONTROLE = ("chave", "paleta", "escolha")
ICONES_DO_CONTROLE = ("lampada",)
OPCOES_DO_CONTROLE = 16
CORES_DO_PONTO = 3
_COR_DO_PONTO = re.compile(r"#[0-9a-fA-F]{6}")
_TERMO_DO_ABRIR = re.compile(r"\w[\w.+,()-]{0,511}")
EVENTO_DO_PARAR = "extensao.parar"
EVENTO_DA_ACAO = "extensao.acao"
EVENTO_DO_LIVRE = "extensao.livre"
EVENTO_DA_OPCAO = "extensao.opcao"
LIVRE_POR_SEGUNDO = 20
EVENTO_DA_MENSAGEM = "extensao.mensagem"
TETO_DA_MENSAGEM = 64_000
MENSAGENS_POR_SEGUNDO = 30
PRAZO_DA_RESPOSTA_S = 1.0
TOPICO_DOS_BOTOES = "botoes"
TOPICO_DAS_ENTRADAS = "entradas"
ENTRADAS_POR_SEGUNDO = 30
FAIXA_MORTA_DO_EIXO = 2
FAIXA_MORTA_DO_DEDO = 0.01
TOPICO_DO_MOVIMENTO = "movimento"
TOPICO_DO_ESTILO = "jogo.estilo"
MOVIMENTO_POR_SEGUNDO = 30
FAIXA_MORTA_DO_GIRO = 2.0
FAIXA_MORTA_DA_ACEL = 0.02
ARQUIVO_DO_PESO_DA_MIRA = "peso_da_mira_dos_jogos.json"
ESPERA_DO_LEITOR_S = 1.0
PRAZO_DO_LEITOR_S = 30.0

Escritor = Callable[[str, dict[str, Any]], Awaitable[Any]]
OJogoEscreve = Callable[[str, str], bool]
UniqDoPosto = Callable[[], str | None]
Controles = Callable[[], list[dict[str, Any]]]
Pulsador = Callable[[str, dict[str, Any]], dict[str, Any]]
LigarAChave = Callable[[str], Awaitable[bool]]
Arbitro = Callable[[], Any]
AbrirOJogo = Callable[[str, Sequence[str]], str]


def abrir_pelo_lancador(mod_id: str, argv: Sequence[str]) -> str:
    """Abre o jogo da extensão fora da caixa e fora do serviço, pelo ``hefesto-launch`` da
    Steam quando ele está instalado (o mesmo ambiente do jogo), com o ambiente limpo. Devolve o
    caminho que a abertura tomou."""
    from hefesto_dualsense4unix.integrations import fora_do_servico
    from hefesto_dualsense4unix.integrations.ambiente_do_jogo import ambiente_limpo
    from hefesto_dualsense4unix.integrations.steam_launch_options import WRAPPER_HOME_RELPATH
    from hefesto_dualsense4unix.utils import xdg_paths

    if fora_do_servico._a_suite_esta_rodando():
        raise OSError("a suíte está no ar e este é o computador de verdade")
    hefesto_launch = Path.home() / WRAPPER_HOME_RELPATH
    linha = [str(hefesto_launch), *argv] if os.access(hefesto_launch, os.X_OK) else list(argv)
    pasta = xdg_paths.runtime_dir() / "abrir-do-lancador"
    pasta.mkdir(mode=0o700, parents=True, exist_ok=True)
    abertura = fora_do_servico.abrir(linha, env=ambiente_limpo(os.environ),
                                     aplicativo=f"hefesto-mod-{mod_id}", pasta_de_trabalho=pasta)
    return str(abertura.caminho)


_NUNCA_FORA_DA_CAIXA = frozenset({
    "sh", "bash", "dash", "zsh", "fish", "ksh", "mksh", "oksh", "csh", "tcsh", "ash", "yash",
    "elvish", "nu", "xonsh", "pwsh", "env", "busybox", "toybox", "xargs", "nohup", "setsid",
    "flatpak-spawn", "flatpak", "sudo", "doas", "pkexec", "su", "runuser", "systemd-run",
    "nice", "ionice", "chrt", "taskset", "stdbuf", "timeout", "time", "strace", "ltrace", "gdb",
    "script", "expect", "watch", "unshare", "nsenter", "bwrap", "firejail", "chroot", "awk",
    "gawk", "mawk", "nawk", "sed", "find", "xdg-open", "gio", "hefesto-launch", "java",
    "jshell", "deno", "bun", "R", "Rscript", "julia", "guile", "racket", "sbcl", "clisp",
    "ocaml", "runghc", "ghci", "erl", "escript", "elixir", "iex", "swipl", "gjs", "dotnet",
    "mono", "qjs", "sg", "newgrp", "setpriv", "capsh", "flock", "prlimit", "setarch", "linux32",
    "linux64", "i386", "x86_64", "aa-exec", "runcon", "ssh-agent", "dbus-run-session",
    "dbus-launch", "xvfb-run", "xwfb-run", "fakeroot", "fakechroot", "faketime", "numactl",
    "cpulimit", "chpst", "torsocks", "torify", "proxychains", "proxychains4", "tsocks",
    "valgrind", "perf", "catchsegv", "start-stop-daemon", "daemonize", "parallel", "make",
    "gmake", "tmux", "screen", "byobu", "dtach", "abduco", "at", "batch", "systemd-cat",
    "systemd-inhibit", "systemd-nspawn", "rlwrap", "unbuffer", "run-parts", "ssh", "sshpass",
    "xdotool", "gtk-launch", "dex", "kstart", "kstart5", "x-terminal-emulator", "xterm",
    "uxterm", "kitty", "foot", "alacritty", "wezterm", "konsole", "gnome-terminal",
    "xfce4-terminal", "tilix", "terminator", "cosmic-term", "urxvt", "st", "npx", "npm",
    "pnpx", "pnpm", "yarn", "bunx", "pipx", "uv", "uvx", "pip", "pip3", "gem", "cargo", "go",
    "nix", "nix-shell", "guix", "raku", "rakudo", "php-cgi", "groovy", "scala", "kotlin",
    "clojure", "octave", "gnuplot", "m4", "dc", "bc", "vi", "vim", "nvim", "ex", "emacs",
    "rc", "es", "sash", "posh", "lksh", "loksh",
})
_INTERPRETADOR = re.compile(
    r"(python|pypy|perl|ruby|irb|node|nodejs|luajit|lua|php|tclsh|wish)[\d.]*(-dbg)?"
    r"|ld(-linux)?[\w.-]*\.so[\d.]*")


def _nunca_fora_da_caixa(nome: str) -> bool:
    return nome in _NUNCA_FORA_DA_CAIXA or bool(_INTERPRETADOR.fullmatch(nome))


def termos_do_abrir(termos: Sequence[str]) -> bool:
    """Os termos depois do comando são o id do jogo: sem «/», sem espaço (que faria de um termo
    uma linha de shell para um lançador que a roda) e nenhum é ele mesmo um comando recusado
    (que um lançador genérico fora da lista rodaria)."""
    return all(_TERMO_DO_ABRIR.fullmatch(t) and not _nunca_fora_da_caixa(t) for t in termos)


def pastas_que_a_caixa_escreve() -> tuple[Path, ...]:
    """O código e os dados de toda extensão, e o que a caixa monta por cima do sistema."""
    from hefesto_dualsense4unix.utils import xdg_paths

    return (xdg_paths.mods_codigo_dir(), xdg_paths.mods_dados_dir(), Path("/dev"), Path("/proc"))


def caminho_da_sessao() -> str:
    """O ``PATH`` com que o jogo abre: o do serviço, limpo como o ambiente do jogo."""
    from hefesto_dualsense4unix.integrations.ambiente_do_jogo import ambiente_limpo

    return ambiente_limpo(os.environ).get("PATH") or os.defpath


def _de_um_lancador_conhecido(nome: str, real: Path, caminho: str) -> bool:
    from hefesto_dualsense4unix.integrations import censo_dos_lancadores as censo

    return (nome in censo.comandos_dos_lancadores_de_fabrica()
            or real in censo.executaveis_dos_atalhos_de_jogo(caminho))


def comando_fora_da_caixa(nome: str, caminho: str, pastas: Sequence[Path]) -> str:
    """O arquivo que ``nome`` abre fora da caixa, ou ``ValueError`` com o motivo (que fica no
    diário). ``nome`` é nu, achado no ``caminho`` num executável de verdade que não é shell nem
    interpretador (pelo nome e pelo alvo do link), que não mora em nenhuma das ``pastas`` e que é
    de um lançador conhecido: o comando de um lançador de fábrica, ou o mesmo arquivo do ``Exec``
    de um atalho de jogo ou de emulador."""
    if not nome or "/" in nome or nome.startswith((".", "-")):
        raise ValueError("o comando não é um nome nu")
    if _nunca_fora_da_caixa(nome):
        raise ValueError("shell, interpretador ou lançador genérico")
    absolutas = os.pathsep.join(p for p in caminho.split(os.pathsep) if os.path.isabs(p))
    achado = shutil.which(nome, path=absolutas)
    if achado is None:
        raise ValueError("o comando não está no PATH")
    real = Path(os.path.realpath(achado))
    if not real.is_file() or not os.access(real, os.X_OK):
        raise ValueError("o comando não é um executável")
    if _nunca_fora_da_caixa(real.name):
        raise ValueError("o link aponta para shell, interpretador ou lançador genérico")
    if not _de_um_lancador_conhecido(nome, real, absolutas):
        raise ValueError("o comando não é de um lançador nem de um emulador instalado")
    for pasta in pastas:
        raiz = Path(os.path.realpath(pasta))
        if real.is_relative_to(raiz) or Path(achado).is_relative_to(raiz):
            raise ValueError(f"o comando mora em {raiz}, que a caixa alcança")
    return str(real)


class RecusaError(Exception):
    """Um pedido recusado, com o código e a frase da resposta."""

    def __init__(self, codigo: int, frase: str, dados: dict[str, Any] | None = None) -> None:
        super().__init__(frase)
        self.codigo = codigo
        self.frase = frase
        self.dados = dados


@dataclass
class _Credencial:
    """Quem o supervisor deixou entrar: a modificação, o PID que ele criou e as permissões."""

    mod_id: str
    pid: int
    permissoes: frozenset[str]
    comandos: frozenset[str] = frozenset()
    acoes_dos_aparelhos: frozenset[str] = frozenset()
    abrir_o_aparelho: Callable[[Any], int] | None = None


@dataclass(eq=False)
class _Assinatura:
    """O que um tópico assinado abriu na conexão: o ``eventos.desassinar`` fecha tudo isto."""

    barramento: list[tuple[str, asyncio.Queue[Any]]] = field(default_factory=list)
    filas: list[asyncio.Queue[Any]] = field(default_factory=list)
    tarefas: list[asyncio.Task[None]] = field(default_factory=list)


class _FilaDosBotoes(asyncio.Queue[dict[str, Any]]):
    """O tópico ``botoes`` de uma conexão: o aperto e a soltura numa fila só, na ordem do tique.

    No teto, as duas bordas seguidas mais antigas de um mesmo botão (o aperto e a soltura, ou
    a soltura e o reaperto) saem juntas, porque se anulam: nenhum botão perde a última borda.
    Sem par para juntar, cada borda na fila é de um botão diferente, e a fila passa do teto só até
    uma borda por botão de cada controle.
    """

    _queue: deque[dict[str, Any]]

    def __init__(self, teto: int = DEFAULT_QUEUE_MAXSIZE) -> None:
        super().__init__()
        self.teto = teto

    def por(self, carga: dict[str, Any]) -> None:
        """Nunca espera: quem publica é o tique."""
        if self.qsize() >= self.teto and self._juntou_a(carga):
            return
        self.put_nowait(carga)

    def _juntou_a(self, carga: dict[str, Any]) -> bool:
        """Tira o par mais antigo; ``True`` quando a própria ``carga`` era a segunda borda dele."""
        primeira: dict[tuple[Any, Any], int] = {}
        segunda: dict[tuple[Any, Any], int] = {}
        for indice, borda in enumerate([*self._queue, carga]):
            chave = borda.get("uniq"), borda.get("botao")
            if chave not in primeira:
                primeira[chave] = indice
            elif chave not in segunda:
                segunda[chave] = indice
        if not segunda:
            return False
        chave = min(segunda, key=primeira.__getitem__)
        antiga, seguinte = primeira[chave], segunda[chave]
        era_a_carga = seguinte == len(self._queue)
        if not era_a_carga:
            del self._queue[seguinte]
        del self._queue[antiga]
        return era_a_carga


@dataclass(eq=False)
class _Conexao:
    sessao: _Credencial | None = None
    deu_o_estado: bool = False
    funcoes_do_acessorio: dict[str, float] = field(default_factory=dict)
    vibrando: set[str] = field(default_factory=set)
    assinaturas: list[tuple[str, asyncio.Queue[Any]]] = field(default_factory=list)
    tarefas: list[asyncio.Task[None]] = field(default_factory=list)
    trava: asyncio.Lock = field(default_factory=asyncio.Lock)
    filas_dos_botoes: list[_FilaDosBotoes] = field(default_factory=list)
    filas_das_entradas: list[asyncio.Queue[Any]] = field(default_factory=list)
    quer_os_dedos: bool = False
    escritor: asyncio.StreamWriter | None = None
    fd_da_resposta: int | None = None
    filas_do_movimento: list[asyncio.Queue[Any]] = field(default_factory=list)
    assinados: dict[str, _Assinatura] = field(default_factory=dict)
    ve_a_tela: bool = False

    def no_barramento(self, feito: _Assinatura, topico: str, fila: asyncio.Queue[Any]) -> None:
        self.assinaturas.append((topico, fila))
        feito.barramento.append((topico, fila))

    def tarefa(self, feito: _Assinatura, corrotina: Coroutine[Any, Any, None], nome: str) -> None:
        tarefa = asyncio.create_task(corrotina, name=nome)
        self.tarefas.append(tarefa)
        feito.tarefas.append(tarefa)

    def desassinar(self, publico: str, bus: EventBus) -> None:
        """Tira as filas, cancela o encaminhamento e as quedas de ``publico``: nada dele sobra."""
        feito = self.assinados.pop(publico)
        for tarefa in feito.tarefas:
            tarefa.cancel()
        self.tarefas = [t for t in self.tarefas if t not in feito.tarefas]
        for topico, fila in feito.barramento:
            bus.unsubscribe(topico, fila)
        self.assinaturas = [a for a in self.assinaturas if a not in feito.barramento]
        self.filas_dos_botoes = [f for f in self.filas_dos_botoes
                                 if all(f is not g for g in feito.filas)]
        self.filas_das_entradas = [f for f in self.filas_das_entradas
                                   if all(f is not g for g in feito.filas)]
        self.filas_do_movimento = [f for f in self.filas_do_movimento
                                   if all(f is not g for g in feito.filas)]
        if publico == TOPICO_DAS_ENTRADAS:
            self.quer_os_dedos = False

    def acessorio_preso(self) -> bool:
        """Alguma função ficou acima de zero: se a conexão cair, o serviço publica o zero."""
        return any(v > 0 for v in self.funcoes_do_acessorio.values())


def credencial_do_par(sock: socket.socket | None) -> tuple[int, int, int] | None:
    """``(pid, uid, gid)`` do outro lado do socket Unix, pelo ``SO_PEERCRED``."""
    if sock is None:
        return None
    cru = sock.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, struct.calcsize("3i"))
    pid, uid, gid = struct.unpack("3i", cru)
    return pid, uid, gid


def entregar_com_o_fd(transporte: Any, linha: bytes, fd: int) -> None:
    """Manda ``linha`` com o ``fd`` (``SCM_RIGHTS``) pelo socket do transporte, que está vazio.

    O socket do ``asyncio`` não tem ``sendmsg``: a cópia do descritor fala pelo mesmo socket.
    """
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM,
                       fileno=os.dup(transporte.fileno())) as sock:
        sock.settimeout(PRAZO_PARA_FECHAR_S)
        if socket.send_fds(sock, [linha], [fd]) != len(linha):
            raise ConnectionError("a resposta com o fd saiu pela metade")


def _pai_de(pid: int) -> int | None:
    """O pai de ``pid`` pelo ``/proc``; ``None`` quando o processo já não existe.

    Um processo que some entre a pergunta e a leitura levanta, e a conexão
    dele fecha: na dúvida, a porta não abre.
    """
    stat = Path(f"/proc/{pid}/stat")
    if not stat.is_file():
        return None
    return int(stat.read_text(encoding="ascii", errors="replace").rsplit(")", 1)[-1].split()[1])


def descende_de(pid: int, criado: int, *, limite: int = 64) -> bool:
    """``pid`` é ``criado`` ou descende dele? (o ``bwrap`` põe um andar entre os dois)"""
    atual: int | None = pid
    for _ in range(limite):
        if atual is None or atual <= 1:
            return False
        if atual == criado:
            return True
        atual = _pai_de(atual)
    return False


def _jsonavel(valor: Any) -> Any:
    if dataclasses.is_dataclass(valor) and not isinstance(valor, type):
        return {f.name: _jsonavel(getattr(valor, f.name)) for f in dataclasses.fields(valor)}
    if isinstance(valor, dict):
        return {str(k): _jsonavel(v) for k, v in valor.items()}
    if isinstance(valor, (frozenset, set)):
        return sorted(_jsonavel(v) for v in valor)
    if isinstance(valor, (list, tuple)):
        return [_jsonavel(v) for v in valor]
    if isinstance(valor, (str, int, float, bool)) or valor is None:
        return valor
    return str(valor)


def _por_na_fila(fila: asyncio.Queue[Any], carga: Any) -> None:
    """Como o barramento: a fila cheia descarta o mais antigo, e quem publica nunca espera."""
    try:
        fila.put_nowait(carga)
    except asyncio.QueueFull:
        with contextlib.suppress(asyncio.QueueEmpty, asyncio.QueueFull):
            fila.get_nowait()
            fila.put_nowait(carga)


def _resposta(req_id: Any, resultado: Any) -> bytes:
    return json.dumps(
        {"jsonrpc": PROTOCOL_VERSION, "id": req_id, "result": resultado}, ensure_ascii=False
    ).encode("utf-8")


def _erro(req_id: Any, codigo: int, frase: str, dados: dict[str, Any] | None = None) -> bytes:
    erro: dict[str, Any] = {"code": codigo, "message": frase}
    if dados:
        erro["data"] = dados
    return json.dumps(
        {
            "jsonrpc": PROTOCOL_VERSION,
            "id": req_id,
            "error": erro,
        },
        ensure_ascii=False,
    ).encode("utf-8")


def _uniq_do_pedido(params: dict[str, Any], metodo: str) -> str:
    uniq = params.get("uniq")
    if not isinstance(uniq, str) or not uniq.strip():
        raise RecusaError(
            CODE_INVALID_PARAMS,
            f"{metodo} pede o uniq do controle: escrever em todos é proibido.",
        )
    return uniq.strip()


def _pedido_da_luz(params: dict[str, Any], uniq: str) -> dict[str, Any]:
    rgb = params.get("rgb")
    if not isinstance(rgb, list) or len(rgb) != 3:
        raise RecusaError(CODE_INVALID_PARAMS, "luz.set pede rgb com três números de 0 a 255.")
    pedido: dict[str, Any] = {"uniq": uniq, "rgb": rgb}
    if "brilho" in params:
        pedido["brightness"] = params["brilho"]
    return pedido


def _pedido_da_vibracao(params: dict[str, Any], uniq: str) -> dict[str, Any]:
    return {"uniq": uniq, "weak": params.get("fraco"), "strong": params.get("forte")}


def _pedido_do_gatilho(params: dict[str, Any], uniq: str) -> dict[str, Any]:
    lados = {"esquerdo": "left", "direito": "right"}
    lado = params.get("lado")
    if lado not in lados:
        raise RecusaError(CODE_INVALID_PARAMS, "gatilho.set pede lado esquerdo ou direito.")
    return {
        "uniq": uniq,
        "side": lados[str(lado)],
        "mode": params.get("modo"),
        "params": params.get("params", []),
    }


def _numero(valor: Any) -> bool:
    return isinstance(valor, (int, float)) and not isinstance(valor, bool) and math.isfinite(valor)


def _funcoes_do_acessorio(dados: Any) -> dict[str, float]:
    """O campo de funções do ``jogo.acessorio`` validado: nome curto, minúsculo, valor de 0 a 1."""
    corpo = dados if isinstance(dados, dict) else {}
    pedidas = corpo.get("funcoes")  # (noqa-acento)
    if not isinstance(pedidas, dict) or not pedidas:
        raise RecusaError(
            CODE_INVALID_PARAMS, "eventos.publicar pede dados.funcoes com ao menos uma função."
        )
    saida: dict[str, float] = {}
    for nome, valor in pedidas.items():
        if not isinstance(nome, str) or not NOME_DA_FUNCAO.fullmatch(nome):
            raise RecusaError(CODE_INVALID_PARAMS, f"nome de função fora da regra: {nome}")
        if not _numero(valor) or not 0 <= valor <= 1:
            raise RecusaError(CODE_INVALID_PARAMS, f"{nome} pede um valor de 0 a 1.")
        saida[nome] = float(valor)
    return saida


def _pedido_do_pulso(params: dict[str, Any]) -> dict[str, Any]:
    """O ``luz.pulso`` validado: ``{parar}`` ou ``{cor, cor_quente?, fundo, periodo_s}``."""
    if params.get("parar") is True:
        return {"parar": True}
    pedido: dict[str, Any] = {}
    for nome in ("cor", "cor_quente"):
        if nome not in params and nome == "cor_quente":
            continue
        valor = params.get(nome)
        if not isinstance(valor, list) or len(valor) != 3 or not all(
            _numero(c) and 0 <= c <= 255 for c in valor
        ):
            raise RecusaError(
                CODE_INVALID_PARAMS, f"luz.pulso pede {nome} com três números de 0 a 255."
            )
        pedido[nome] = [round(c) for c in valor]
    fundo = params.get("fundo", 0.0)
    if not _numero(fundo) or not 0 <= fundo <= 1:
        raise RecusaError(CODE_INVALID_PARAMS, "luz.pulso pede o fundo de 0 a 1.")
    periodo = params.get("periodo_s", 2.0)
    if not _numero(periodo):
        raise RecusaError(CODE_INVALID_PARAMS, "luz.pulso pede o período em segundos.")
    pedido["fundo"], pedido["periodo_s"] = float(fundo), float(periodo)
    return pedido


def _anotar_a_vibracao(con: _Conexao, params: dict[str, Any]) -> None:
    """Guarda o controle que ficou vibrando por esta conexão; o zero o tira da lista."""
    uniq = str(params.get("uniq") or "").strip()
    forca: list[Any] = [params.get("fraco"), params.get("forte")]
    if any(_numero(v) and v > 0 for v in forca):
        con.vibrando.add(uniq)
    else:
        con.vibrando.discard(uniq)


def _texto(valor: Any, onde: str, maximo: int, *, vazio: bool = False) -> str:
    if not isinstance(valor, str) or len(valor) > maximo or (not vazio and not valor.strip()):
        raise RecusaError(CODE_INVALID_PARAMS, f"lancador.jogos pede {onde} em texto curto.")
    return valor


def jogos_do_lancador(params: dict[str, Any], comandos: frozenset[str]) -> list[dict[str, Any]]:
    """A lista de ``lancador.jogos`` validada: ``[{chave, nome, abrir, janela}]``.

    ``abrir`` é o argv do jogo, e o primeiro termo é um dos ``comandos`` do manifesto;
    ``janela`` é o app-id da janela do jogo (vazio quando a extensão não sabe).
    """
    jogos = params.get("jogos")
    if not isinstance(jogos, list) or len(jogos) > JOGOS_POR_LANCADOR:
        raise RecusaError(CODE_INVALID_PARAMS,
                          f"lancador.jogos pede a lista jogos, até {JOGOS_POR_LANCADOR}.")
    saida: list[dict[str, Any]] = []
    vistas: set[str] = set()
    for jogo in jogos:
        if not isinstance(jogo, dict):
            raise RecusaError(CODE_INVALID_PARAMS, "lancador.jogos pede cada jogo em objeto.")
        chave = _texto(jogo.get("chave"), "a chave", 120)
        if chave in vistas:
            raise RecusaError(CODE_INVALID_PARAMS, f"chave repetida em lancador.jogos: {chave}")
        vistas.add(chave)
        abrir = jogo.get("abrir")
        if not isinstance(abrir, list) or not 1 <= len(abrir) <= 64:
            raise RecusaError(CODE_INVALID_PARAMS, "lancador.jogos pede abrir com o comando.")
        argv = [_texto(a, "cada termo de abrir", 4096, vazio=True) for a in abrir]
        if argv[0] not in comandos:
            raise RecusaError(
                CODE_SEM_PERMISSAO, f"o comando {argv[0]!r} não está em lancador.comandos")
        saida.append({
            "chave": chave,
            "nome": _texto(jogo.get("nome"), "o nome", 120),
            "abrir": argv,
            "janela": _texto(jogo.get("janela", ""), "a janela", 200, vazio=True),
        })
    return saida


_ESCRITAS: dict[str, tuple[str, str, Callable[[dict[str, Any], str], dict[str, Any]]]] = {
    "luz.set": ("luz", "led.set", _pedido_da_luz),
    "vibracao.set": ("vibracao", "rumble.set", _pedido_da_vibracao),
    "gatilho.set": ("gatilho", "trigger.set", _pedido_do_gatilho),
}

_NOME_DO_CANAL = {
    "luz": "a luz", "vibracao": "a vibração", "gatilho": "o gatilho", "haptica": "a háptica",
    "som": "o som", "leds": "as luzes de jogador",
}

_LADOS = ("esquerdo", "direito")

ACESO_DO_AO_VIVO_S = 2.0
CONTROLES_DO_AO_VIVO = 4

_DA_MEMORIA = {"memoria.varrer": "varrer", "memoria.refinar": "refinar"}


def _jogador_do_ao_vivo(jogador: Any) -> int | None:
    return jogador if isinstance(jogador, int) and not isinstance(jogador, bool) else None


def _pedido_da_memoria(params: dict[str, Any]) -> dict[str, Any]:
    """O ``memoria`` da assinatura de ``jogo.memoria``: as linhas que a receita declara e a faixa
    do ``buildid``, conferidas antes de chegar ao leitor."""
    memoria = params.get("memoria")
    if not isinstance(memoria, dict):
        raise RecusaError(CODE_INVALID_PARAMS, "jogo.memoria pede as entradas da receita")
    try:
        entradas_da_receita(memoria.get("entradas") or ())
    except LeituraRecusadaError as exc:
        raise RecusaError(CODE_INVALID_PARAMS, exc.frase) from exc
    faixa = memoria.get("faixa")
    if faixa is not None and not isinstance(faixa, dict):
        raise RecusaError(CODE_INVALID_PARAMS, "a faixa do buildid é {min, max}")
    return {"entradas": list(memoria["entradas"]), "faixa": faixa}


def _regioes_do_pedido(params: dict[str, Any]) -> tuple[Regiao, ...]:
    """As regiões que a receita declara em ``tela: {regioes: [...]}``; sem ``tela``, nenhuma."""
    tela = params.get("tela")
    if tela is None:
        return ()
    if not isinstance(tela, dict) or not isinstance(tela.get("regioes", []), list):
        raise RecusaError(CODE_INVALID_PARAMS, "jogo.tela pede tela: {regioes: [...]}")
    try:
        return regioes_da_receita(tela.get("regioes", []))
    except TelaRecusadaError as exc:
        raise RecusaError(CODE_INVALID_PARAMS, exc.frase) from exc


async def _perguntar(reader: asyncio.StreamReader, writer: asyncio.StreamWriter,
                     pedido: dict[str, Any]) -> dict[str, Any]:
    writer.write(json.dumps(pedido, ensure_ascii=False).encode("utf-8") + b"\n")
    await writer.drain()
    linha = await asyncio.wait_for(reader.readline(), timeout=PRAZO_DO_LEITOR_S)
    if not linha:
        raise asyncio.IncompleteReadError(b"", None)
    resposta = json.loads(linha.decode("utf-8"))
    if not isinstance(resposta, dict):
        raise ValueError("resposta do leitor fora da forma")
    return resposta


_DE_FORA = {
    "haptica.registrar": "haptica", "haptica.tocar": "haptica",
    "som.registrar": "som", "som.tocar": "som",
    "leds.set": "leds",
}


def _origem(sessao: Any) -> str:
    return f"extensao:{sessao.mod_id}"


def _ident(params: dict[str, Any], metodo: str) -> str:
    ident = params.get("id")
    if not isinstance(ident, str) or not re.fullmatch(r"[a-z0-9_-]{1,32}", ident):
        raise ValueError(f"{metodo} pede o id em minúsculas, de 1 a 32 letras")
    return ident


def _sem_recusa_solta(tarefa: asyncio.Task[Any]) -> None:
    if not tarefa.cancelled() and tarefa.exception() is not None:
        logger.warning("mods_porta_reescrita_falhou", err=str(tarefa.exception()))


def _prazo_do_pedido(params: dict[str, Any], metodo: str) -> float | None:
    ate_ms = params.get("ate_ms")
    if ate_ms is None:
        return None
    if not _numero(ate_ms) or ate_ms < 0:
        raise RecusaError(CODE_INVALID_PARAMS, f"{metodo} pede ate_ms em milissegundos.")
    return float(ate_ms) / 1000.0


def _vagas_do_pedido(canal: str, params: dict[str, Any]) -> dict[str, float]:
    """A força de cada vaga do canal, de 0 a 1: a régua do mais forte."""
    from hefesto_dualsense4unix.core.trigger_effects import bloco_do_efeito, build_from_name
    from hefesto_dualsense4unix.daemon.subsystems.tato_vivo import brilho_da_luz, forca_do_bloco

    if canal == "vibracao":
        fraco: Any = params.get("fraco")
        forte: Any = params.get("forte")
        if not all(_numero(v) and 0 <= v <= 255 for v in (fraco, forte)):
            raise RecusaError(CODE_INVALID_PARAMS, "vibracao.set pede fraco e forte de 0 a 255.")
        return {"esquerdo": float(forte) / 255.0, "direito": float(fraco) / 255.0}
    if canal == "gatilho":
        valores = params.get("params", [])
        try:
            efeito = build_from_name(str(params.get("modo")), list(valores or []))
        except (TypeError, ValueError) as exc:
            raise RecusaError(CODE_INVALID_PARAMS, f"gatilho.set: {exc}") from exc
        return {str(params.get("lado")): forca_do_bloco(bloco_do_efeito(efeito)) / 8.0}
    rgb = params.get("rgb")
    if not isinstance(rgb, list) or len(rgb) != 3 or not all(
            _numero(c) and 0 <= c <= 255 for c in rgb):
        raise RecusaError(CODE_INVALID_PARAMS, "luz.set pede rgb com três números de 0 a 255.")
    brilho = params.get("brilho", 1.0)
    if not _numero(brilho) or not 0 <= brilho <= 1:
        raise RecusaError(CODE_INVALID_PARAMS, "luz.set pede o brilho de 0 a 1.")
    return {"centro": brilho_da_luz(rgb, brilho)}


_FRASE_DO_MODO_QUE_CALA = {
    "nativo": "no Modo Nativo o jogo fala direto com o controle",
    "steam_input": "no Steam Input a Steam fala direto com o controle",
}


def _recusa_do_veredito(veredito: Any, canal: str) -> RecusaError:
    if veredito.motivo == "teto":
        return RecusaError(CODE_TETO_CHEIO, "o teto de efeitos deste controle está cheio",
                           {"canal": canal})
    if veredito.motivo == "sem_ponte":
        return RecusaError(CODE_SEM_PONTE, "o rádio deste controle está sem vaga para o som",
                           {"canal": canal})
    if veredito.motivo == "sem_no":
        return RecusaError(CODE_NAO_ESCREVEU, "o controle está sem o alto-falante agora")
    if veredito.motivo == "modo":
        return RecusaError(CODE_O_JOGO_ESCREVE, "no Modo Nativo o jogo fala direto com o controle",
                           {"vence": veredito.vence, "canal": canal, "modo": "nativo"})
    return RecusaError(
        CODE_O_JOGO_ESCREVE,
        f"{_NOME_DO_CANAL[canal]} deste controle tem um pedido mais forte vivo",
        {"vence": veredito.vence, "canal": canal})


def _bits_da_mascara(params: dict[str, Any]) -> list[bool]:
    mascara = params.get("mascara")
    if not isinstance(mascara, int) or isinstance(mascara, bool) or not 0 <= mascara <= 0b11111:
        raise RecusaError(CODE_INVALID_PARAMS, "leds.set pede a mascara de 0 a 31.")
    return [bool(mascara >> bit & 1) for bit in range(5)]


def estado_vazio_dos_acessorios(mod_id: str) -> dict[str, Any]:
    """O estado de quem não tem acessório nem conexão: os gestos do PS voltam a ser os de sempre."""
    return {
        "mod": mod_id, "ligado": False, "nivel": 0, "perfil": None, "aparelhos": [],
        "conexoes": [], "ajustes": {},  # (noqa-acento)
    }


def _recusa_do_estado(frase: str) -> RecusaError:
    return RecusaError(CODE_INVALID_PARAMS, f"acessorios.estado: {frase}")


def _curto(valor: Any, onde: str, maximo: int) -> str:
    if not isinstance(valor, str) or len(valor) > maximo or not valor.strip():
        raise _recusa_do_estado(f"{onde} é um texto de até {maximo} letras.")
    return valor.strip()


def _estado_do_item(bruto: dict[str, Any], onde: str,
                    aceitos: tuple[str, ...] = ESTADOS_DO_ACESSORIO) -> str:
    estado = bruto.get("estado", "ligado")
    if estado not in aceitos:
        raise _recusa_do_estado(f"o estado de {onde} é um de {', '.join(aceitos)}.")
    return str(estado)


def _aparelho(bruto: Any, ids_das_acoes: frozenset[str] = frozenset()) -> dict[str, Any]:
    """``{nome, tipo, estado, bateria, forca}``; o texto solto (o formato antigo) é só o nome.

    ``id`` (até 40 letras, o que a ação do aparelho leva como ``alvo``), ``ligado`` (a chave do
    cartão), ``barra`` (o valor da barra do cartão, um número) e ``controles`` (os que só este
    aparelho tem) só saem quando a extensão os manda.
    ``ids_das_acoes`` são os das ações dos aparelhos, que nenhum controle repete.
    """
    if isinstance(bruto, str):
        bruto = {"nome": bruto}
    if not isinstance(bruto, dict):
        raise _recusa_do_estado("cada aparelho é um objeto {nome, tipo, estado, bateria, forca}.")
    bateria, forca = bruto.get("bateria"), bruto.get("forca")
    if bateria is not None and (isinstance(bateria, bool) or not isinstance(bateria, int)
                                or not 0 <= bateria <= 100):
        raise _recusa_do_estado("a bateria de um aparelho vai de 0 a 100, ou nula.")
    if forca is not None and (not _numero(forca) or not 0.0 <= float(forca) <= 1.0):
        raise _recusa_do_estado("a força de um aparelho vai de 0 a 1, ou nula.")
    tipo = bruto.get("tipo")
    saida: dict[str, Any] = {
        "nome": _curto(bruto.get("nome"), "o nome do aparelho", 60),
        "tipo": None if tipo is None else _curto(tipo, "o tipo do aparelho", 30),
        "estado": _estado_do_item(bruto, "um aparelho"),
        "bateria": bateria,
        "forca": None if forca is None else round(float(forca), 3),
    }
    if bruto.get("id") is not None:
        saida["id"] = _curto(bruto.get("id"), "o id do aparelho", 40)
    if "ligado" in bruto:
        if not isinstance(bruto["ligado"], bool):
            raise _recusa_do_estado("o ligado de um aparelho é verdadeiro ou falso.")
        saida["ligado"] = bruto["ligado"]
    if bruto.get("barra") is not None:
        if "id" not in saida or not _numero(bruto["barra"]):
            raise _recusa_do_estado("a barra de um aparelho é um número, no aparelho com id.")
        saida["barra"] = float(bruto["barra"])
    if bruto.get("controles") is not None:
        saida["controles"] = _controles_do_aparelho(bruto["controles"], "id" in saida,
                                                    ids_das_acoes)
    return saida


def _controles_do_aparelho(bruto: Any, tem_id: bool,
                           ids_das_acoes: frozenset[str] = frozenset()) -> list[dict[str, Any]]:
    """Os ``controles`` de um aparelho: até ``CONTROLES_DO_APARELHO``, ids sem repetição, e só
    no aparelho com ``id`` (o clique volta com ele como ``alvo``). Nenhum repete o id de uma das
    ações dos aparelhos (``ids_das_acoes``): o clique dos dois chega à extensão com a mesma forma
    (a ação e o alvo), e o serviço o tomaria pela ação."""
    if not tem_id:
        raise _recusa_do_estado("o aparelho com controles tem id.")
    if not isinstance(bruto, list) or len(bruto) > CONTROLES_DO_APARELHO:
        raise _recusa_do_estado(
            f"os controles de um aparelho são uma lista de até {CONTROLES_DO_APARELHO}.")
    controles = [_controle(c) for c in bruto]
    if len({c["id"] for c in controles}) != len(controles):
        raise _recusa_do_estado("controle repetido num aparelho.")
    for controle in controles:
        if controle["id"] in ids_das_acoes:
            raise _recusa_do_estado(
                f"o controle «{controle['id']}» tem o id de uma ação dos aparelhos.")
    return controles


def _controle(bruto: Any) -> dict[str, Any]:
    """Um controle do aparelho: a chave leva o valor verdadeiro ou falso; a paleta e a escolha levam
    as opções e, no valor, o ``id`` de uma das opções (ou nulo). O rótulo, a dica e o ícone (um de
    ``ICONES_DO_CONTROLE``, o glifo do que a chave controla) são opcionais."""
    if not isinstance(bruto, dict):
        raise _recusa_do_estado(
            "cada controle é um objeto {id, tipo, valor, opcoes, dica}.")  # (noqa-acento)
    tipo = bruto.get("tipo")
    if tipo not in TIPOS_DO_CONTROLE:
        raise _recusa_do_estado(f"o tipo de um controle é um de {', '.join(TIPOS_DO_CONTROLE)}.")
    saida: dict[str, Any] = {"id": _curto(bruto.get("id"), "o id do controle", 40), "tipo": tipo}
    valor = bruto.get("valor")
    if tipo == "chave":
        if not isinstance(valor, bool):
            raise _recusa_do_estado("o valor da chave é verdadeiro ou falso.")
    else:
        saida["opcoes"] = _opcoes_do_controle(bruto.get("opcoes"), tipo)  # (noqa-acento)
        if valor is not None and valor not in {
            o["id"] for o in saida["opcoes"]}:  # (noqa-acento)
            raise _recusa_do_estado(f"o valor da {tipo} é o id de uma das opções, ou nulo.")
    saida["valor"] = valor
    if bruto.get("rotulo") is not None:
        saida["rotulo"] = _curto(bruto["rotulo"],
                                 "o rótulo de um controle", 30)
    if bruto.get("dica") is not None:
        saida["dica"] = _curto(bruto["dica"], "a dica de um controle", 120)
    if bruto.get("icone") is not None:
        if bruto["icone"] not in ICONES_DO_CONTROLE:
            raise _recusa_do_estado(
                f"o ícone de um controle é um de {', '.join(ICONES_DO_CONTROLE)}.")
        saida["icone"] = bruto["icone"]
    return saida


def _opcoes_do_controle(bruto: Any, tipo: str) -> list[dict[str, Any]]:
    """As opções da paleta (``{id, cor, rotulo?}``, o rótulo é a dica do ponto) ou da escolha
    (``{id, rotulo}``), de 1 a ``OPCOES_DO_CONTROLE``, ids sem repetição."""
    if not isinstance(bruto, list) or not 1 <= len(bruto) <= OPCOES_DO_CONTROLE:
        raise _recusa_do_estado(f"a {tipo} de um aparelho leva de 1 a {OPCOES_DO_CONTROLE} opções.")
    saida = []
    for item in bruto:
        if not isinstance(item, dict):
            raise _recusa_do_estado(f"cada opção da {tipo} é um objeto com id.")
        certo: dict[str, Any] = {"id": _curto(item.get("id"), "o id de uma opção", 40)}
        if tipo == "paleta":
            certo["cor"] = _cor_do_ponto(item.get("cor"))
            if item.get("rotulo") is not None:
                certo["rotulo"] = _curto(item["rotulo"],
                                         "o rótulo de uma cor", 30)
        else:
            certo["rotulo"] = _curto(item.get("rotulo"),
                                     "o rótulo de uma opção", 30)
        saida.append(certo)
    if len({o["id"] for o in saida}) != len(saida):
        raise _recusa_do_estado(f"opção repetida na {tipo} de um aparelho.")
    return saida


def _cor_do_ponto(cor: Any) -> str | list[str]:
    """A cor de um ponto da paleta: ``#rrggbb``, ou uma lista de até ``CORES_DO_PONTO`` cores."""
    cores = cor if isinstance(cor, list) else [cor]
    if not 1 <= len(cores) <= CORES_DO_PONTO or not all(
            isinstance(c, str) and _COR_DO_PONTO.fullmatch(c) for c in cores):
        raise _recusa_do_estado(
            f"a cor de uma paleta é #rrggbb, ou uma lista de até {CORES_DO_PONTO} cores.")
    return [c.lower() for c in cores] if isinstance(cor, list) else str(cor).lower()


def _escolhas_da_conexao(bruto: dict[str, Any]) -> dict[str, Any]:
    """``escolhas`` (até ``ESCOLHAS_DA_CONEXAO`` nomes curtos) e ``escolha`` (um deles): os nomes
    que a linha da conexão oferece, como os adaptadores do computador."""
    escolhas, escolha = bruto.get("escolhas"), bruto.get("escolha")
    if escolhas is None and escolha is None:
        return {}
    if not isinstance(escolhas, list) or not escolhas:
        raise _recusa_do_estado("as escolhas de uma conexão são uma lista de nomes.")
    nomes = list(dict.fromkeys(
        _curto(n, "a escolha de uma conexão", 40) for n in escolhas[:ESCOLHAS_DA_CONEXAO]))
    if not isinstance(escolha, str) or escolha.strip() not in nomes:
        raise _recusa_do_estado("a escolha de uma conexão é uma das escolhas publicadas.")
    return {"escolhas": nomes, "escolha": escolha.strip()}


def _conexao_do_estado(bruto: Any) -> dict[str, Any]:
    """``{id, tipo, transporte, estado, motivo}``: uma ponte da extensão (um adaptador, a rede),
    com ``escolhas`` e ``escolha`` quando a linha oferece nomes."""
    if not isinstance(bruto, dict):
        raise _recusa_do_estado("cada conexão é um objeto {id, tipo, transporte, estado, motivo}.")
    transporte, motivo = bruto.get("transporte"), bruto.get("motivo")
    if transporte not in TRANSPORTES_DA_CONEXAO:
        raise _recusa_do_estado(
            f"o transporte de uma conexão é um de {', '.join(TRANSPORTES_DA_CONEXAO)}.")
    return {
        "id": _curto(bruto.get("id"), "o id da conexão", 40),
        "tipo": _curto(bruto.get("tipo"), "o tipo da conexão", 30),
        "transporte": transporte,
        "estado": _estado_do_item(bruto, "uma conexão", ESTADOS_DA_CONEXAO),
        "motivo": None if motivo in (None, "") else _curto(motivo, "o motivo da conexão", 120),
        **_escolhas_da_conexao(bruto),
    }


def estado_dos_acessorios(mod_id: str, params: dict[str, Any], *,
                          acoes_dos_aparelhos: frozenset[str] = frozenset()) -> dict[str, Any]:
    """O ``acessorios.estado`` validado, com o ``mod`` de quem o mandou.

    Cada aparelho sai ``{nome, tipo, estado, bateria, forca}`` (o texto solto vira o nome) e cada
    conexão ``{id, tipo, transporte, estado, motivo}``, até ``ITENS_DO_ESTADO`` de cada. ``ajustes``
    leva só o que a modificação declara e o Hefesto entende (limiar do fundo do L2, acelerador,
    camada, lado único, gestos no Modo Nativo, toque de confirmação, pulso da barra e «Sem pisca»);
    o resto cai. Nenhum controle de aparelho repete um dos ``acoes_dos_aparelhos``.
    """
    ligado = params.get("ligado", False)
    nivel = params.get("nivel", 0)
    perfil = params.get("perfil")
    aparelhos = params.get("aparelhos", [])
    conexoes = params.get("conexoes", [])  # (noqa-acento)
    opcoes = params.get("ajustes", {})
    if not isinstance(ligado, bool):
        raise RecusaError(CODE_INVALID_PARAMS, "acessorios.estado pede ligado verdadeiro ou falso.")
    if isinstance(nivel, bool) or not isinstance(nivel, int) or not 0 <= nivel <= 10:
        raise RecusaError(CODE_INVALID_PARAMS, "acessorios.estado pede o nível de 0 a 10.")
    if perfil is not None and not isinstance(perfil, str):
        raise RecusaError(CODE_INVALID_PARAMS, "acessorios.estado pede o perfil como texto.")
    if not isinstance(aparelhos, list) or not isinstance(conexoes, list) \
            or not isinstance(opcoes, dict):
        raise RecusaError(
            CODE_INVALID_PARAMS,
            "acessorios.estado pede aparelhos e conexões em lista e ajustes em objeto.",
        )
    as_conexoes = [_conexao_do_estado(c) for c in conexoes[:ITENS_DO_ESTADO]]
    return {
        "mod": mod_id,
        "ligado": ligado,
        "nivel": nivel,
        "perfil": perfil,
        "aparelhos": [_aparelho(a, acoes_dos_aparelhos) for a in aparelhos[:ITENS_DO_ESTADO]],
        "conexoes": as_conexoes,  # (noqa-acento)
        "ajustes": {k: v for k, v in opcoes.items() if k in OPCOES_DOS_GESTOS},
        **_linhas_e_presentes(params),
    }


def _linhas_e_presentes(params: dict[str, Any]) -> dict[str, Any]:
    """``linhas`` (o pedaço «linhas» do «Agora»: até ``LINHAS_DO_AGORA`` pares ``{rotulo,
    valor}``, o resto cai), ``presentes`` (os nomes que o ``aparece_com`` de ``@presente`` lê, até
    ``ITENS_DO_ESTADO``), ``limiar`` (de 0 a 10, a linha tracejada do pedaço «clima»),
    situação (a faixa do alto da janela), ``leituras`` (o que cada sentido lê agora, até
    ``ITENS_DO_ESTADO``) e as ações pedidas (:func:`_acoes_do_estado`); cada um só sai quando a
    extensão o manda."""
    saida: dict[str, Any] = {}
    if params.get("linhas") is not None:
        linhas = params["linhas"]
        if not isinstance(linhas, list) or not all(isinstance(x, dict) for x in linhas):
            raise _recusa_do_estado("as linhas do «Agora» são uma lista de {rotulo, valor}.")
        saida["linhas"] = [
            {"rotulo": _curto(x.get("rotulo"), "o rótulo de uma linha", ROTULO_DA_LINHA),
             "valor": _curto(x.get("valor"), "o valor de uma linha", VALOR_DA_LINHA)}
            for x in linhas[:LINHAS_DO_AGORA]]
    if params.get("presentes") is not None:
        presentes = params["presentes"]
        if not isinstance(presentes, list):
            raise _recusa_do_estado("os presentes são uma lista de nomes.")
        saida["presentes"] = list(dict.fromkeys(
            _curto(n, "um presente", 40) for n in presentes[:ITENS_DO_ESTADO]))
    if params.get("limiar") is not None:
        limiar = params["limiar"]
        if isinstance(limiar, bool) or not isinstance(limiar, int) or not 0 <= limiar <= 10:
            raise _recusa_do_estado("o limiar do clima é um número de 0 a 10.")
        saida["limiar"] = limiar
    if params.get("situacao") is not None:  # (noqa-acento)
        saida["situacao"] = _situacao_do_estado(params["situacao"])  # (noqa-acento)
    if params.get("leituras") is not None:
        leituras = params["leituras"]
        if not isinstance(leituras, list):
            raise _recusa_do_estado("as leituras são uma lista de {opcao, nivel, frase}.")
        saida["leituras"] = [_leitura_do_estado(x) for x in leituras[:ITENS_DO_ESTADO]]
    if params.get("acoes") is not None:  # (noqa-acento)
        saida["acoes"] = _acoes_do_estado(params["acoes"])  # (noqa-acento)
    return saida


def _acoes_do_estado(bruto: Any) -> dict[str, str]:
    """``{id da ação: texto}``: as ações ``pedida`` que aparecem agora e o texto ao lado de cada
    botão. O texto vem de fora (o endereço de uma página, por exemplo) e se corta em
    ``TEXTO_DA_ACAO`` letras em vez de recusar o estado inteiro."""
    if not isinstance(bruto, dict) or not all(isinstance(t, str) for t in bruto.values()):
        raise _recusa_do_estado("as ações do estado são um objeto {id da ação: texto}.")
    return {_curto(k, "o id de uma ação do estado", 40): t[:TEXTO_DA_ACAO]
            for k, t in list(bruto.items())[:ITENS_DO_ESTADO]}


def _situacao_do_estado(bruto: Any) -> dict[str, Any]:
    """``{estado, frase}``: a faixa do alto da janela. ``estado`` é ``tocando``, ``calado`` ou
    ``esperando``; ``frase`` (até ``FRASE_DA_SITUACAO`` letras, ou nula) é o jogo de agora, ou o
    motivo do calado."""
    if not isinstance(bruto, dict) or bruto.get("estado") not in SITUACOES:
        raise _recusa_do_estado(
            f"a situação é um objeto {{estado, frase}}, com o estado um de {', '.join(SITUACOES)}.")
    frase = bruto.get("frase")
    return {"estado": bruto["estado"],
            "frase": None if frase in (None, "") else _curto(frase, "a frase da situação",
                                                              FRASE_DA_SITUACAO)}


def _leitura_do_estado(bruto: Any) -> dict[str, Any]:
    """O que um sentido lê agora, ao lado da opção que a leitura nomeia: ``nivel`` vai de 0 a
    100, ou nulo; ``frase`` (até ``FRASE_DA_LEITURA`` letras) diz o que ele lê; ``cego`` marca o
    sentido que não lê nada agora."""
    if not isinstance(bruto, dict):
        raise _recusa_do_estado("cada leitura é um objeto {opcao, nivel, frase}.")
    nivel, frase, cego = bruto.get("nivel"), bruto.get("frase"), bruto.get("cego", False)
    if nivel is not None and (isinstance(nivel, bool) or not isinstance(nivel, int)
                              or not 0 <= nivel <= 100):
        raise _recusa_do_estado("o nível de uma leitura vai de 0 a 100, ou nulo.")
    if not isinstance(cego, bool):
        raise _recusa_do_estado("o cego de uma leitura é verdadeiro ou falso.")
    opcao = _curto(bruto.get("opcao"), "a opção de uma leitura", 40)  # (noqa-acento)
    if not _CHAVE_DE_LANCADOR.match(opcao):
        raise _recusa_do_estado("a opção de uma leitura é o id de uma opção do manifesto.")
    return {"opcao": opcao,  # (noqa-acento)
            "nivel": nivel,
            "frase": None if frase in (None, "") else _curto(frase, "a frase de uma leitura",
                                                              FRASE_DA_LEITURA),
            "cego": cego}


OPCOES_DOS_GESTOS = frozenset({
    "limiar_fundo", "acelerador", "camada", "camada_s", "lado_unico", "gestos_no_nativo",
    "toque_de_confirmacao", "pulso_da_barra", "sem_pisca",
})


_Valores = tuple[int, int, int, int, int, int, tuple[tuple[float, float], ...]]
REPOUSO_DAS_ENTRADAS: _Valores = (128, 128, 128, 128, 0, 0, ())
_PONTAS = ((0, 128, 255),) * 4 + ((0, 255),) * 2


def _mudou(antes: _Valores | None, agora: _Valores) -> bool:
    """``agora`` sai? Um eixo passou da faixa morta ou chegou a uma ponta; um dedo chegou, saiu
    ou andou além da faixa dele. Com ``antes`` ``None`` (quem acabou de assinar), sai sempre."""
    if antes is None:
        return agora != REPOUSO_DAS_ENTRADAS
    for velho, novo, pontas in zip(antes[:6], agora[:6], _PONTAS, strict=True):
        if novo != velho and (abs(novo - velho) > FAIXA_MORTA_DO_EIXO or novo in pontas):
            return True
    dedos_antes, dedos_agora = antes[6], agora[6]
    return len(dedos_antes) != len(dedos_agora) or any(
        abs(a - b) > FAIXA_MORTA_DO_DEDO
        for velho, novo in zip(dedos_antes, dedos_agora, strict=True)
        for a, b in zip(velho, novo, strict=True)
    )


def _carga_das_entradas(uniq: str | None, jogador: Any, via: Any, valores: _Valores
                        ) -> dict[str, Any]:
    lx, ly, rx, ry, l2, r2, dedos = valores
    return {"uniq": uniq, "jogador": jogador, "transporte": via,
            "lx": lx, "ly": ly, "rx": rx, "ry": ry, "l2": l2, "r2": r2,
            "dedos": [{"x": x, "y": y} for x, y in dedos]}


_Movimento = tuple[tuple[float, float, float], tuple[float, float, float]]
REPOUSO_DO_MOVIMENTO: _Movimento = ((0.0, 0.0, 0.0), (0.0, 0.0, 0.0))


def _o_movimento_mudou(antes: _Movimento | None, agora: _Movimento) -> bool:
    """``agora`` sai? Um eixo do giro ou da aceleração passou da faixa morta dele, contada do
    último que saiu. Com ``antes`` ``None`` (quem acabou de assinar), sai o que não é repouso."""
    if antes is None:
        return agora != REPOUSO_DO_MOVIMENTO
    return any(
        abs(novo - velho) > faixa
        for (lado_antes, lado_agora), faixa in zip(
            zip(antes, agora, strict=True), (FAIXA_MORTA_DO_GIRO, FAIXA_MORTA_DA_ACEL),
            strict=True)
        for velho, novo in zip(lado_antes, lado_agora, strict=True)
    )


def _carga_do_movimento(uniq: str | None, jogador: Any, via: Any, valores: _Movimento
                        ) -> dict[str, Any]:
    (gx, gy, gz), (ax, ay, az) = valores
    return {"uniq": uniq, "jogador": jogador, "transporte": via,
            "giro": {"x": round(gx, 2), "y": round(gy, 2), "z": round(gz, 2)},
            "acel": {"x": round(ax, 3), "y": round(ay, 3), "z": round(az, 3)}}


def _estilo_do_catalogo(valor: Any) -> str | None:
    from hefesto_dualsense4unix.profiles.estilos_de_jogo import POR_CHAVE, chave_do_catalogo

    chave = chave_do_catalogo(valor)
    return chave if isinstance(chave, str) and chave in POR_CHAVE else None


def _esta_em_cena(dito: dict[str, Any]) -> bool:
    em_cena = dito.get("em_cena")
    if isinstance(em_cena, bool):
        return em_cena
    jogo = dito.get("jogo")
    return isinstance(jogo, str) and bool(jogo)


def _estilo_com_o_jogo(dito: dict[str, Any]) -> str | None:
    return _estilo_do_catalogo(dito.get("estilo")) if _esta_em_cena(dito) else None


def carga_do_estilo(carga: Any) -> dict[str, Any] | None:
    """O ``jogo.estilo`` que sai do ``perfil.trocou``: ``{estilo, jogo, controles: [{jogador,
    estilo}]}``, a chave do catálogo dos estilos (ou ``None``), sem o ``t``.

    O estilo do perfil só vale com o jogo aberto, pelo ``em_cena`` (o do serviço, ou o de cada
    controle), a mesma pergunta do modo: o jogo nativo sem appid também está em cena. Sem jogo, o
    estilo sai ``None``, mesmo com o perfil do jogo fechado ainda em vigor. A carga que não traz o
    ``em_cena`` está em cena quando traz ``jogo``."""
    if not isinstance(carga, dict):
        return None
    jogo = carga.get("jogo")
    controles = carga.get("controles")
    return {
        "estilo": _estilo_com_o_jogo(carga),
        "jogo": jogo if isinstance(jogo, str) and jogo else None,
        "controles": [
            {"jogador": c.get("jogador"), "estilo": _estilo_com_o_jogo(c)}
            for c in (controles if isinstance(controles, list) else []) if isinstance(c, dict)
        ],
    }


async def _traduzir_o_estilo(entrada: asyncio.Queue[Any], saida: asyncio.Queue[Any]) -> None:
    """Do ``perfil.trocou`` ao ``jogo.estilo``: só sai quando o estilo, o jogo ou o estilo de um
    controle muda; o primeiro é o de agora, que o barramento guarda."""
    antes: dict[str, Any] | None = None
    while True:
        agora = carga_do_estilo(await entrada.get())
        if agora is None or agora == antes:
            continue
        antes = agora
        _por_na_fila(saida, {**agora, "t": time.monotonic()})


@dataclass
class _Compasso:
    """O compasso do arrastar de um ``livre``: o valor que espera e o relógio que o solta."""

    pendente: dict[str, Any] | None = None
    relogio: asyncio.TimerHandle | None = None

    def cancelar(self) -> None:
        if self.relogio is not None:
            self.relogio.cancel()
        self.pendente = self.relogio = None


PREFIXO_DO_APELIDO = "ctl-"
UNIQS_SEM_CONTROLE = frozenset({"", "todos"})
_UNIQ_NA_LINHA = re.compile(rb'("uniq"\s*:\s*")((?:[^"\\]|\\.)*)(")')
TAMANHO_DA_CHAVE_DOS_APELIDOS = 32


def chave_dos_apelidos(caminho: Path) -> bytes:
    """A chave da casa para os apelidos, em ``caminho`` (``0600``): nasce na primeira vez e
    sobrevive ao reinício. A que não se lê inteira dá lugar a uma nova."""
    try:
        chave = caminho.read_bytes()
        if len(chave) == TAMANHO_DA_CHAVE_DOS_APELIDOS:
            return chave
    except OSError as exc:
        logger.info("mods_chave_dos_apelidos_nova", motivo=type(exc).__name__)
    chave = secrets.token_bytes(TAMANHO_DA_CHAVE_DOS_APELIDOS)
    caminho.parent.mkdir(parents=True, exist_ok=True)
    fd, nome = tempfile.mkstemp(prefix=".chave-", dir=caminho.parent)
    try:
        with os.fdopen(fd, "wb") as arquivo:
            arquivo.write(chave)
        os.replace(nome, caminho)
    except BaseException:
        with contextlib.suppress(FileNotFoundError):
            os.unlink(nome)
        raise
    return chave


class Apelidos:
    """O apelido estável de cada controle, um por extensão: o HMAC-SHA256 do ``uniq`` com a chave
    da casa e o id da extensão. A extensão conhece só o apelido, e a porta traduz de volta o
    que chega da extensão. ``""``, ``"todos"`` e o que já é apelido passam como estão."""

    def __init__(self, chave: bytes | Callable[[], bytes],
                 controles: Callable[[], Sequence[str]] = tuple) -> None:
        self._chave = chave
        self._controles = controles
        self._de_volta: dict[tuple[str, str], str] = {}

    def _a_chave(self) -> bytes:
        if callable(self._chave):
            self._chave = self._chave()
        return self._chave

    def de(self, mod_id: str, uniq: str) -> str:
        if uniq in UNIQS_SEM_CONTROLE or uniq.startswith(PREFIXO_DO_APELIDO):
            return uniq
        marca = hmac.new(self._a_chave(), f"{mod_id}\0{uniq}".encode(), hashlib.sha256)
        return PREFIXO_DO_APELIDO + marca.hexdigest()[:20]

    def uniq_de(self, mod_id: str, apelido: str) -> str:
        """O ``uniq`` do apelido, achado pelos controles de agora (o que a extensão guardou antes
        do reinício também). Só os controles de verdade entram na volta: o texto que a extensão
        põe num campo ``uniq`` não a faz crescer."""
        if not apelido.startswith(PREFIXO_DO_APELIDO):
            return apelido
        if (mod_id, apelido) not in self._de_volta:
            try:
                for uniq in self._controles():
                    if isinstance(uniq, str) and uniq not in UNIQS_SEM_CONTROLE:
                        self._de_volta[(mod_id, self.de(mod_id, uniq))] = uniq
            except Exception as exc:
                logger.debug("mods_apelido_sem_os_controles", err=str(exc))
        return self._de_volta.get((mod_id, apelido), apelido)

    def na_linha(self, mod_id: str, linha: bytes) -> bytes:
        """A linha JSON que vai à extensão com cada ``"uniq": "…"`` trocado pelo apelido."""
        def trocar(achado: re.Match[bytes]) -> bytes:
            try:
                uniq = json.loads(b'"' + achado.group(2) + b'"')
            except ValueError:
                return achado.group(0)
            apelido = json.dumps(self.de(mod_id, uniq), ensure_ascii=False)[1:-1]
            return achado.group(1) + apelido.encode("utf-8") + achado.group(3)

        return _UNIQ_NA_LINHA.sub(trocar, linha) if b'"uniq"' in linha else linha

    def no_pedido(self, mod_id: str, valor: Any) -> Any:
        """O que a extensão mandou, com o apelido de cada chave ``uniq`` trocado pelo ``uniq``."""
        if isinstance(valor, dict):
            return {k: (self.uniq_de(mod_id, v) if k == "uniq" and isinstance(v, str)
                        else self.no_pedido(mod_id, v)) for k, v in valor.items()}
        if isinstance(valor, list):
            return [self.no_pedido(mod_id, v) for v in valor]
        return valor


class Porta:
    """O servidor da porta das modificações, dentro do laço do serviço."""

    def __init__(
        self,
        caminho: Path,
        bus: EventBus,
        *,
        escritor: Escritor,
        o_jogo_escreve: OJogoEscreve,
        uniq_do_posto: UniqDoPosto,
        pulsador: Pulsador | None = None,
        controles: Controles | None = None,
        ligar_a_chave: LigarAChave | None = None,
        relogio: Callable[[], float] = time.monotonic,
        arbitro: Arbitro | None = None,
        fonte_da_tela: Callable[[], FonteDaTela] = fonte_do_sistema,
        abrir_o_jogo: AbrirOJogo = abrir_pelo_lancador,
        apelidos: Apelidos | None = None,
    ) -> None:
        self.caminho = caminho
        self.apelidos = apelidos
        self._abrir_o_jogo = abrir_o_jogo
        self._fonte_da_tela = fonte_da_tela
        self._regioes_da_tela: dict[str, Regiao] = {}
        self._pedidos_da_tela = 0
        self._captura_da_tela: asyncio.Task[None] | None = None
        self._vigia_do_peso: asyncio.Task[None] | None = None
        self._prazo_do_peso: asyncio.TimerHandle | None = None
        self._acordar_o_vigia: asyncio.Event | None = None
        self._escalas: set[tuple[str, str]] = set()
        self._anticheat_por_appid: dict[str, str] = {}
        self._arbitro: Arbitro | None = (
            arbitro if arbitro is not None
            else escritor.arbitro if isinstance(escritor, EscritorDoServico) else None)
        self._ligar_a_chave = ligar_a_chave
        self._controles = controles
        self.bus = bus
        self._pulsador = pulsador
        self._escritor = escritor
        self._o_jogo_escreve = o_jogo_escreve
        self._uniq_do_posto = uniq_do_posto
        self._fichas: dict[str, _Credencial] = {}
        self._server: asyncio.AbstractServer | None = None
        self._inode: int | None = None
        self._conexoes: set[_Conexao] = set()
        self._relogio = relogio
        self._publicacoes: dict[str, deque[float]] = {}
        self._aparelhos_pedidos: dict[str, deque[float]] = {}
        self._estados_dos_acessorios: dict[str, dict[str, Any]] = {}
        self._escritas: dict[str, dict[str, dict[str, float]]] = {}
        self._jogos_dos_lancadores: dict[str, list[dict[str, Any]]] = {}
        self._botoes_antes: dict[str | None, frozenset[str]] | None = None
        self._entradas_enviadas: dict[str | None, tuple[_Valores | None, float, Any, Any]] = {}
        self._series: dict[str, int] = {}
        self._livres: dict[tuple[str, str], _Compasso] = {}
        self._opcoes_vivas: dict[tuple[str, str], _Compasso] = {}
        self._barras: dict[tuple[str, str], _Compasso] = {}
        self._movimento_enviado: dict[str | None, tuple[_Movimento | None, float, Any, Any]] = {}
        self._vivas_de_antes: frozenset[str] = frozenset()
        self._mensagens: dict[str, deque[float]] = {}
        self._esperas: dict[str, tuple[str, asyncio.Future[Any]]] = {}
        self._serie_da_mensagem = 0

    def registrar(self, ficha: str, mod_id: str, pid: int, permissoes: list[str],
                  *, comandos: tuple[str, ...] = (),
                  acoes_dos_aparelhos: tuple[str, ...] = (),
                  abrir_o_aparelho: Callable[[Any], int] | None = None) -> None:
        """O supervisor diz: esta ficha é da modificação ``mod_id``, no PID ``pid``."""
        self._fichas[ficha] = _Credencial(
            mod_id, pid, frozenset(permissoes), frozenset(comandos),
            frozenset(acoes_dos_aparelhos), abrir_o_aparelho)

    def esquecer(self, ficha: str) -> None:
        self._fichas.pop(ficha, None)

    def vivas(self) -> frozenset[str]:
        """As extensões com a sessão aberta agora: o modo de aba de cada uma vale."""
        return frozenset(con.sessao.mod_id for con in self._conexoes if con.sessao is not None)

    def _mudaram_as_vivas(self) -> None:
        """Quem entra ou sai pode mudar o efeito fixo de uma seção: o perfil que nomeia o modo
        de quem mudou volta ao aparelho, e o tato vivo relê no tique seguinte."""
        if not isinstance(self._escritor, EscritorDoServico):
            return
        nome = self._escritor.perfil_que_nomeia(self.vivas() ^ self._vivas_de_antes)
        self._vivas_de_antes = self.vivas()
        if nome is None:
            return
        try:
            laco = asyncio.get_running_loop()
        except RuntimeError:
            logger.warning("mods_porta_modo_sem_laco", perfil=nome)
            return
        tarefa = laco.create_task(self._levar("profile.reaplicar", "profile.reaplicar",
                                              {"name": nome}))
        tarefa.add_done_callback(_sem_recusa_solta)

    def assinaturas_de(self, mod_id: str) -> list[asyncio.Queue[Any]]:
        """As filas do barramento abertas por ``mod_id`` (para a régua e o diagnóstico)."""
        return [
            fila
            for con in self._conexoes
            if con.sessao is not None and con.sessao.mod_id == mod_id
            for _topico, fila in con.assinaturas
        ]

    @property
    def aberta(self) -> bool:
        return self._server is not None

    async def iniciar(self) -> None:
        self.caminho.parent.mkdir(parents=True, exist_ok=True)
        with contextlib.suppress(FileNotFoundError):
            self.caminho.unlink()
        antiga = os.umask(0o177)
        try:
            self._server = await asyncio.start_unix_server(
                self._atender, path=str(self.caminho), limit=MAX_PAYLOAD_BYTES + 1024
            )
        finally:
            os.umask(antiga)
        os.chmod(self.caminho, 0o600)
        self._inode = self.caminho.stat().st_ino
        _A_PORTA["viva"] = self
        logger.info("mods_porta_aberta", caminho=str(self.caminho))

    async def parar(self) -> None:
        if _A_PORTA["viva"] is self:
            _A_PORTA["viva"] = None
        server, self._server = self._server, None
        if server is not None:
            server.close()
        captura_da_tela = self._captura_da_tela
        if captura_da_tela is not None:
            captura_da_tela.cancel()
            await asyncio.wait({captura_da_tela}, timeout=PRAZO_DA_CAPTURA_SAIR_S)
        if self._vigia_do_peso is not None:
            self._vigia_do_peso.cancel()
        if self._prazo_do_peso is not None:
            self._prazo_do_peso.cancel()
        for con in list(self._conexoes):
            for tarefa in con.tarefas:
                tarefa.cancel()
        if server is not None:
            with contextlib.suppress(Exception):
                await asyncio.wait_for(server.wait_closed(), timeout=PRAZO_PARA_FECHAR_S)
        if self._inode is not None:
            with contextlib.suppress(FileNotFoundError):
                if self.caminho.stat().st_ino == self._inode:
                    self.caminho.unlink()
            self._inode = None

    async def _atender(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        con = _Conexao(escritor=writer)
        self._conexoes.add(con)
        try:
            par = credencial_do_par(writer.get_extra_info("socket"))
            from hefesto_dualsense4unix.daemon.ipc_handlers import Chamador, chamador_de_agora

            chamador_de_agora.set(Chamador(pid=par[0] if par and par[0] > 0 else None))
            while True:
                try:
                    cru = await reader.readline()
                except (asyncio.LimitOverrunError, ValueError):
                    await self._enviar(con, writer, _erro(
                        None, CODE_INVALID_REQUEST,
                        f"pedido maior que {MAX_PAYLOAD_BYTES} bytes"))
                    break
                if not cru:
                    break
                resposta = await self._despachar(con, writer, cru, par)
                if resposta is not None:
                    await self._enviar(con, writer, resposta)
                if con.sessao is None:
                    break
        except (ConnectionError, asyncio.IncompleteReadError) as exc:
            logger.debug("mods_porta_caiu", mod=con.sessao.mod_id if con.sessao else None,
                         err=type(exc).__name__)
        except Exception as exc:
            logger.warning("mods_porta_erro", err=str(exc), exc_info=True)
        finally:
            await self._limpar_a_conexao(con)
            with contextlib.suppress(Exception):
                writer.close()
                await writer.wait_closed()

    async def _limpar_a_conexao(self, con: _Conexao) -> None:
        """A conexão que sai: cada passo roda mesmo quando o de antes falha, para que a vibração
        nunca fique presa nem a conexão fique na porta."""
        sessao = con.sessao

        def soltar_a_vibracao() -> Any:
            if con.vibrando and sessao is not None:
                return self._soltar_a_vibracao(sessao, con.vibrando)
            return None

        def esquecer_as_escritas() -> None:
            if sessao is not None and sessao.mod_id not in self.vivas():
                self._esquecer_as_escritas(sessao.mod_id)

        def cancelar_as_tarefas() -> None:
            for tarefa in con.tarefas:
                tarefa.cancel()

        def soltar_as_assinaturas() -> None:
            for topico, fila in con.assinaturas:
                self.bus.unsubscribe(topico, fila)

        passos: list[tuple[str, Callable[[], Any]]] = [
            ("tarefas", cancelar_as_tarefas),
            ("assinaturas", soltar_as_assinaturas),
            ("estado", lambda: self._esvaziar_o_estado(con)),
            ("acessorio", lambda: self._soltar_o_acessorio(sessao.mod_id, con.funcoes_do_acessorio)
             if con.acessorio_preso() and sessao is not None else None),
            ("fonte", lambda: self._esquecer_na_fonte(sessao)),
            ("motores", soltar_a_vibracao),
            ("porta", lambda: self._conexoes.discard(con)),
            ("escritas", esquecer_as_escritas),
            ("ajustes", lambda: self._soltar_os_ajustes(sessao.mod_id)
             if sessao is not None else None),
            ("vivas", lambda: self._mudaram_as_vivas() if sessao is not None else None),
        ]
        for nome, passo in passos:
            try:
                retorno = passo()
                if inspect.isawaitable(retorno):
                    await retorno
            except Exception:
                logger.warning("mods_porta_limpeza_falhou", passo=nome,
                               mod=sessao.mod_id if sessao else None, exc_info=True)

    def _esvaziar_o_estado(self, con: _Conexao) -> None:
        if not con.deu_o_estado or con.sessao is None:
            return
        vazio = estado_vazio_dos_acessorios(con.sessao.mod_id)
        self._estados_dos_acessorios[con.sessao.mod_id] = vazio
        if "ler:acessorios.gesto" in con.sessao.permissoes:
            self.bus.publish(EventTopic.ACESSORIOS_ESTADO, vazio)

    def _esquecer_na_fonte(self, sessao: _Credencial | None) -> None:
        fonte = self._fonte()
        if fonte is not None and sessao is not None:
            fonte.esquecer(_origem(sessao))

    async def _enviar(self, con: _Conexao, writer: asyncio.StreamWriter, linha: bytes) -> None:
        if self.apelidos is not None and con.sessao is not None:
            linha = self.apelidos.na_linha(con.sessao.mod_id, linha)
        async with con.trava:
            fd, con.fd_da_resposta = con.fd_da_resposta, None
            if fd is None:
                writer.write(linha + b"\n")
                await writer.drain()
                return
            try:
                entregar_com_o_fd(writer.get_extra_info("socket"), linha + b"\n", fd)
            finally:
                os.close(fd)

    async def _despachar(
        self,
        con: _Conexao,
        writer: asyncio.StreamWriter,
        cru: bytes,
        par: tuple[int, int, int] | None,
    ) -> bytes | None:
        try:
            pedido = json.loads(cru.decode("utf-8").strip() or "null")
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            return _erro(None, CODE_PARSE_ERROR, f"parse: {exc}")
        if not isinstance(pedido, dict):
            return _erro(None, CODE_PARSE_ERROR, "o pedido não é objeto")
        req_id = pedido.get("id")
        metodo = pedido.get("method")
        params = pedido.get("params") or {}
        if not isinstance(metodo, str) or not isinstance(params, dict):
            return _erro(req_id, CODE_INVALID_REQUEST, "method e params são obrigatórios")
        if self.apelidos is not None and con.sessao is not None:
            params = self.apelidos.no_pedido(con.sessao.mod_id, params)
        try:
            if con.sessao is None and metodo == "aparelho.abrir":
                return _resposta(req_id, await self._abrir_o_aparelho(con, params, par))
            if con.sessao is None:
                if metodo != "mod.ola":
                    raise RecusaError(CODE_QUEM_E_VOCE, "a primeira palavra é mod.ola")
                con.sessao = self._apresentar(params, par)
                self._mudaram_as_vivas()
                return _resposta(req_id, {
                    "id": con.sessao.mod_id,
                    "api": API_DAS_MODIFICACOES,
                    "permissoes": sorted(con.sessao.permissoes),  # (noqa-acento)
                })
            if metodo == "eventos.assinar":
                return _resposta(req_id, self._assinar(con, writer, params))
            if metodo == "eventos.desassinar":
                return _resposta(req_id, self._desassinar(con, params))
            if metodo == "eventos.publicar":
                return _resposta(req_id, self._publicar(con, params))
            if metodo in ("tela.ver", "tela.parar"):
                return _resposta(req_id, self._ver_a_tela(con, metodo, params))
            if metodo == "acessorios.estado":
                return _resposta(req_id, self._estado_dos_acessorios(con, params))
            if metodo == "luz.pulso":
                return _resposta(req_id, self._pulsar(con.sessao, params))
            if metodo == "lancador.jogos":
                return _resposta(req_id, self._jogos_do_lancador(con.sessao, params))
            if metodo == "lancador.abrir":
                return _resposta(req_id, await self._abrir_do_lancador(con.sessao, params))
            if metodo == "chave.ligar":
                return _resposta(req_id, await self._ligar_a_chave_de(con.sessao))
            if metodo == "controles.lista":
                return _resposta(req_id, await asyncio.to_thread(
                    self._lista_dos_controles, con.sessao))
            if metodo == "mira.peso":
                return _resposta(req_id, await self._pesar_a_mira(con.sessao, params))
            if metodo == "mira.ligada":
                return _resposta(req_id, await self._ligar_a_mira(con.sessao, params))
            if metodo == "vibracao.escala":
                return _resposta(req_id, self._escalar_a_vibracao(con.sessao, params))
            if metodo == "corpo.ligar":
                return _resposta(req_id, self._ligar_o_corpo(con.sessao, params))
            if metodo in _DA_MEMORIA:
                return _resposta(req_id, await self._varrer(con.sessao, metodo, params))
            if metodo in _DE_FORA:
                return _resposta(req_id, await self._de_fora(con.sessao, metodo, params))
            if metodo == "extensao.resposta":
                return _resposta(req_id, self._responder(con.sessao.mod_id, params))
            if metodo in _ESCRITAS:
                marca_do_gesto = gesto_de_agora.set(f"mod:{con.sessao.mod_id}:{metodo}")
                try:
                    feito = await self._escrever(con.sessao, metodo, params)
                finally:
                    gesto_de_agora.reset(marca_do_gesto)
                if metodo == "vibracao.set":
                    _anotar_a_vibracao(con, params)
                return _resposta(req_id, feito)
            raise RecusaError(CODE_METHOD_NOT_FOUND, f"método desconhecido: {metodo}")
        except RecusaError as recusa:
            return _erro(req_id, recusa.codigo, recusa.frase, recusa.dados)

    async def _abrir_o_aparelho(self, con: _Conexao, params: dict[str, Any],
                                par: tuple[int, int, int] | None) -> dict[str, Any]:
        """A primeira e única palavra da conexão: o fd do nó declarado vai junto da resposta.

        O nó abre fora da caixa, na hora do pedido: o aparelho que reiniciou e voltou com outro
        nó se pede de novo, sem reabrir a caixa.
        """
        credencial = self._apresentar(params, par)
        if credencial.abrir_o_aparelho is None:
            raise RecusaError(CODE_SEM_PERMISSAO,
                              "aparelho.abrir pede a permissão aparelhos e o aparelho declarado")
        agora = self._relogio()
        janela = self._aparelhos_pedidos.setdefault(credencial.mod_id, deque())
        while janela and agora - janela[0] >= 1.0:
            janela.popleft()
        if len(janela) >= APARELHOS_POR_SEGUNDO:
            raise RecusaError(CODE_TETO_CHEIO, f"aparelho.abrir aceita até {APARELHOS_POR_SEGUNDO} "
                                               "por segundo por extensão.")
        janela.append(agora)
        no = params.get("no")
        try:
            fd = await asyncio.to_thread(credencial.abrir_o_aparelho, no)
        except (OSError, ValueError) as exc:
            logger.info("mods_porta_aparelho_recusado", mod=credencial.mod_id, no=str(no)[:40],
                        err=str(exc))
            raise RecusaError(CODE_INVALID_PARAMS, str(exc)) from exc
        con.fd_da_resposta = fd
        logger.info("mods_porta_aparelho_entregue", mod=credencial.mod_id, no=no)
        return {"no": no}

    def _apresentar(
        self, params: dict[str, Any], par: tuple[int, int, int] | None
    ) -> _Credencial:
        ficha = params.get("ficha")
        credencial = self._fichas.get(ficha) if isinstance(ficha, str) else None
        if credencial is None:
            raise RecusaError(CODE_QUEM_E_VOCE, "ficha desconhecida")
        if par is None:
            raise RecusaError(CODE_QUEM_E_VOCE, "sem credencial do processo")
        pid, uid, _gid = par
        if uid != os.getuid() or not descende_de(pid, credencial.pid):
            logger.warning(
                "mods_porta_processo_estranho",
                mod=credencial.mod_id,
                pid=pid,
                criado=credencial.pid,
            )
            raise RecusaError(CODE_QUEM_E_VOCE, "este processo não é o que o Hefesto abriu")
        return credencial

    def _assinar(
        self, con: _Conexao, writer: asyncio.StreamWriter, params: dict[str, Any]
    ) -> dict[str, Any]:
        assert con.sessao is not None
        topicos = params.get("topicos")
        if not isinstance(topicos, list) or not topicos:
            raise RecusaError(CODE_INVALID_PARAMS, "eventos.assinar pede a lista topicos")
        for publico in topicos:
            if publico not in TOPICOS_DE_LEITURA:
                raise RecusaError(CODE_INVALID_PARAMS, f"tópico desconhecido: {publico}")
            if f"ler:{publico}" not in con.sessao.permissoes:
                raise RecusaError(CODE_SEM_PERMISSAO, f"falta a permissão ler:{publico}")
        dedos = params.get("dedos", False)
        if not isinstance(dedos, bool) or (dedos and TOPICO_DAS_ENTRADAS not in topicos):
            raise RecusaError(CODE_INVALID_PARAMS, "dedos é true ou false, com o tópico entradas")
        con.quer_os_dedos = con.quer_os_dedos or dedos
        memoria = _pedido_da_memoria(params) if TOPICO_DA_MEMORIA in topicos else None
        regioes = _regioes_do_pedido(params) if TOPICO_DA_TELA in topicos else ()
        for publico in topicos:
            feito = con.assinados.setdefault(publico, _Assinatura())
            if publico == TOPICO_DOS_BOTOES:
                if not self.le_os_botoes():
                    self._botoes_antes = None
                bordas = _FilaDosBotoes()
                con.filas_dos_botoes.append(bordas)
                feito.filas.append(bordas)
                con.tarefa(feito, self._encaminhar(con, writer, publico, publico, bordas),
                           f"mods-{con.sessao.mod_id}-{publico}")
                continue
            for topico in TOPICOS_DE_LEITURA[publico]:
                fila: asyncio.Queue[Any]
                if publico == TOPICO_DAS_ENTRADAS:
                    self._entradas_enviadas = {
                        uniq: (None, quando, jogador, via)
                        for uniq, (_valores, quando, jogador, via)
                        in self._entradas_enviadas.items()
                    } if self.le_as_entradas() else {}
                    fila = asyncio.Queue(maxsize=DEFAULT_QUEUE_MAXSIZE)
                    con.filas_das_entradas.append(fila)
                    feito.filas.append(fila)
                    saidas = self.bus.subscribe(EventTopic.CONTROLLER_DISCONNECTED)
                    con.no_barramento(feito, EventTopic.CONTROLLER_DISCONNECTED, saidas)
                    con.tarefa(feito, self._repousar_quem_sai(saidas),
                               f"mods-{con.sessao.mod_id}-entradas-quedas")
                elif publico == TOPICO_DO_MOVIMENTO:
                    fila = self._assinar_o_movimento(con, feito)
                elif publico == TOPICO_DO_ESTILO:
                    fila = asyncio.Queue(maxsize=DEFAULT_QUEUE_MAXSIZE)
                    feito.filas.append(fila)
                    perfis = self.bus.subscribe(EventTopic.PERFIL_TROCOU)
                    con.no_barramento(feito, EventTopic.PERFIL_TROCOU, perfis)
                    con.tarefa(feito, _traduzir_o_estilo(perfis, fila),
                               f"mods-{con.sessao.mod_id}-estilo")
                elif publico == TOPICO_DA_MEMORIA and memoria is not None:
                    fila = asyncio.Queue(maxsize=DEFAULT_QUEUE_MAXSIZE)
                    feito.filas.append(fila)
                    con.tarefa(feito, self._ler_a_memoria(fila, memoria),
                               f"mods-{con.sessao.mod_id}-memoria-leitor")
                else:
                    fila = self.bus.subscribe(topico)
                    con.no_barramento(feito, topico, fila)
                    if topico == EventTopic.MODO_ABA:
                        from hefesto_dualsense4unix.daemon.subsystems.tato_vivo import (
                            modos_da_aba_ditos,
                        )

                        for carga in modos_da_aba_ditos():
                            _por_na_fila(fila, carga)
                con.tarefa(feito, self._encaminhar(con, writer, publico, topico, fila),
                           f"mods-{con.sessao.mod_id}-{topico}")
        if TOPICO_DA_TELA in topicos:
            self._regioes_da_tela.update({r.nome: r for r in regioes})
            if con.ve_a_tela:
                self._ligar_a_captura()
        return {"assinados": list(topicos)}

    def _ver_a_tela(self, con: _Conexao, metodo: str, params: dict[str, Any]) -> dict[str, Any]:
        """O ``tela.ver`` do clique em «Ver a tela» abre a captura (sem ficha, a escolha do portal
        sai neste clique) para quem assina ``jogo.tela`` e fecha no ``tela.parar``, no jogo que
        fecha e na extensão que sai. A captura é uma só para a máquina."""
        assert con.sessao is not None
        if f"ler:{TOPICO_DA_TELA}" not in con.sessao.permissoes:
            raise RecusaError(CODE_SEM_PERMISSAO, f"falta a permissão ler:{TOPICO_DA_TELA}")
        if metodo == "tela.parar":
            con.ve_a_tela = False
            return {"status": "ok"}
        self._regioes_da_tela.update({r.nome: r for r in _regioes_do_pedido(params)})
        con.ve_a_tela = True
        self._pedidos_da_tela += 1
        self._ligar_a_captura()
        return {"status": "ok"}

    def _quem_ve_a_tela(self) -> int:
        return sum(1 for con in self._conexoes
                   if con.ve_a_tela and TOPICO_DA_TELA in con.assinados)

    async def _pesar_a_mira(self, sessao: _Credencial,
                            params: dict[str, Any]) -> dict[str, Any]:
        """O ``mira.peso``: o ganho do giro de um controle (ou de ``todos``) por ``ate_ms``. Num
        jogo com anticheat, só com a chave «Peso da mira» do jogo ligada."""
        if "escrever:mira" not in sessao.permissoes:
            raise RecusaError(CODE_SEM_PERMISSAO, "falta a permissão escrever:mira")
        alvo = params.get("uniq")
        ganho, ate_ms = params.get("ganho"), params.get("ate_ms")
        if not isinstance(alvo, str) or not alvo:
            raise RecusaError(CODE_INVALID_PARAMS, "mira.peso pede o uniq, ou «todos»")
        if (isinstance(ganho, bool) or not isinstance(ganho, (int, float))
                or isinstance(ate_ms, bool) or not isinstance(ate_ms, int)):
            raise RecusaError(CODE_INVALID_PARAMS, "mira.peso pede ganho e ate_ms em números")
        if barra := await self._anticheat_que_barra(self._jogo_aberto()):
            raise RecusaError(
                CODE_NAO_ESCREVEU,
                f"este jogo usa {barra}: o peso da mira pede a chave do jogo ligada")
        no_modo = self._no_modo_da_extensao(sessao)
        alvos = sorted(no_modo) if alvo == TODOS_OS_CONTROLES else [
            a for a in (chave_de_sensor(alvo),) if a in no_modo]
        if not alvos:
            raise RecusaError(
                CODE_NAO_ESCREVEU, "a seção Controles deste controle não está no modo da extensão")
        try:
            for um in alvos:
                PESO_DA_MIRA.pedir(sessao.mod_id, um, float(ganho), ate_ms)
        except ValueError as exc:
            raise RecusaError(CODE_INVALID_PARAMS, str(exc)) from exc
        self._vigiar_o_peso()
        self._anotar_a_escrita(sessao.mod_id, "mira", "" if alvo == TODOS_OS_CONTROLES else alvo)
        return {"status": "ok"}

    @staticmethod
    def _no_modo_da_extensao(sessao: _Credencial) -> frozenset[str]:
        from hefesto_dualsense4unix.daemon.subsystems.tato_vivo import modos_da_aba_ditos

        return frozenset(
            chave_de_sensor(c["uniq"]) for c in modos_da_aba_ditos()
            if isinstance(c.get("uniq"), str) and isinstance(c.get("secoes"), dict)
            and c["secoes"].get("controles") == _origem(sessao))

    def _anticheat_do_jogo(self, jogo: str) -> str:
        from hefesto_dualsense4unix.integrations.prontuario_dos_jogos import jogos_instalados

        appid = jogo.removeprefix("steam_app_")
        if appid not in self._anticheat_por_appid:
            raiz = next((r for a, _nome, r in jogos_instalados() if a == appid), None)
            self._anticheat_por_appid[appid] = anticheat_do_jogo(raiz, appid)
        return self._anticheat_por_appid[appid]

    async def _anticheat_que_barra(self, jogo: str | None) -> str:
        """O anticheat de ``jogo`` quando a chave «Peso da mira» dele está desligada; vazio quando
        nada barra o peso e o giro desligado."""
        if jogo is None:
            return ""
        anticheat = await asyncio.to_thread(self._anticheat_do_jogo, jogo)
        if not anticheat:
            return ""
        chaves = ChavesDaMemoria(arquivo_das_chaves().with_name(ARQUIVO_DO_PESO_DA_MIRA))
        liberada = await asyncio.to_thread(chaves.liberada, jogo, anticheat)
        return "" if liberada else anticheat

    async def _soltar_no_jogo_com_anticheat(self, jogo: str) -> None:
        try:
            barra = await self._anticheat_que_barra(jogo)
        except Exception as exc:
            logger.warning("mods_porta_anticheat_ilegivel", jogo=jogo, err=type(exc).__name__)
            barra = "anticheat ilegível"
        if not barra:
            return
        logger.info("mods_porta_giro_religado_pelo_anticheat", jogo=jogo, anticheat=barra)
        PESO_DA_MIRA.soltar()
        for dono in PESO_DA_MIRA.donos_do_giro():
            PESO_DA_MIRA.religar_de(dono)

    def _jogo_aberto(self) -> str | None:
        identidade = self.bus.ultimo(EventTopic.JOGO_IDENTIDADE)
        chave = identidade.get("chave") if isinstance(identidade, dict) else None
        return chave if isinstance(chave, str) and chave else None

    def _vigiar_o_peso(self) -> None:
        loop = asyncio.get_running_loop()
        if self._prazo_do_peso is not None:
            self._prazo_do_peso.cancel()
        ultimo = PESO_DA_MIRA.ultimo_prazo()
        self._prazo_do_peso = None if ultimo is None else loop.call_later(
            max(0.0, ultimo - PESO_DA_MIRA.relogio()), PESO_DA_MIRA.vencer)
        if self._vigia_do_peso is None or self._vigia_do_peso.done():
            self._vigia_do_peso = asyncio.get_running_loop().create_task(
                self._soltar_o_peso_quando_preciso(), name="mods-porta-peso-da-mira")

    async def _soltar_o_peso_quando_preciso(self) -> None:
        """O peso volta a 1 quando o jogo fecha; o peso, o giro desligado e a escala da vibração
        saem quando a seção Controles de um controle deixa o modo de quem pediu; o peso e o giro
        saem quando o jogo troca para um com anticheat e a chave dele está desligada. A vigia
        acaba quando nada disso tem dono (o prazo, a queda da extensão), pelo aviso dele."""
        loop = asyncio.get_running_loop()
        vazio = asyncio.Event()
        self._acordar_o_vigia = vazio
        fechou = self.bus.subscribe(EventTopic.JOGO_FECHOU)
        modos = self.bus.subscribe(EventTopic.MODO_ABA)
        identidades = self.bus.subscribe(EventTopic.JOGO_IDENTIDADE)
        conferido: str | None = None

        def avisar() -> None:
            if not loop.is_closed():
                loop.call_soon_threadsafe(vazio.set)

        esquecer = PESO_DA_MIRA.ao_esvaziar(avisar)
        try:
            while True:
                vazio.clear()
                jogo = self._jogo_aberto()
                if jogo is not None and jogo != conferido:
                    conferido = jogo
                    await self._soltar_no_jogo_com_anticheat(jogo)
                if (not PESO_DA_MIRA.donos() and not PESO_DA_MIRA.donos_do_giro()
                        and not self._escalas):
                    break
                do_fim = asyncio.ensure_future(fechou.get())
                do_modo = asyncio.ensure_future(modos.get())
                do_jogo = asyncio.ensure_future(identidades.get())
                do_vazio = asyncio.ensure_future(vazio.wait())
                feitos, pendentes = await asyncio.wait(
                    {do_fim, do_modo, do_jogo, do_vazio}, return_when=asyncio.FIRST_COMPLETED)
                for pendente in pendentes:
                    pendente.cancel()
                if do_fim in feitos:
                    PESO_DA_MIRA.soltar()
                if do_modo in feitos:
                    self._soltar_fora_do_modo(do_modo.result())
        finally:
            esquecer()
            if self._acordar_o_vigia is vazio:
                self._acordar_o_vigia = None
            self.bus.unsubscribe(EventTopic.JOGO_FECHOU, fechou)
            self.bus.unsubscribe(EventTopic.MODO_ABA, modos)
            self.bus.unsubscribe(EventTopic.JOGO_IDENTIDADE, identidades)

    def _soltar_fora_do_modo(self, carga: Any) -> None:
        if not isinstance(carga, dict) or not isinstance(carga.get("secoes"), dict):
            return
        modo = carga["secoes"].get("controles")
        uniq = carga.get("uniq")
        for dono in PESO_DA_MIRA.donos():
            if modo != f"extensao:{dono}":
                PESO_DA_MIRA.soltar(dono, uniq if isinstance(uniq, str) else None)
        if not isinstance(uniq, str) or not uniq:
            return
        for dono in PESO_DA_MIRA.donos_do_giro():
            if modo != f"extensao:{dono}":
                PESO_DA_MIRA.ligar(dono, uniq)
        chave = chave_de_sensor(uniq)
        for dono, escalado in sorted(self._escalas):
            if chave_de_sensor(escalado) == chave and modo != f"extensao:{dono}":
                ESCALA_DA_VIBRACAO.pedir(dono, escalado, 1.0)
                self._escalas.discard((dono, escalado))

    def _ligar_a_captura(self) -> None:
        if self._captura_da_tela is None or self._captura_da_tela.done():
            self._captura_da_tela = asyncio.get_running_loop().create_task(
                self._capturar_a_tela(), name="mods-porta-tela")

    async def _capturar_a_tela(self) -> None:
        """Um passo da :class:`Captura` por vez, fora do laço: a fonte abre só com quem pediu
        ``tela.ver`` e assina ``jogo.tela``; sem nenhum, ou com o jogo que fecha, fecha. O jogo que
        fecha e a escolha cancelada apagam o pedido de todos, e a tarefa acaba quando ninguém
        mais pediu."""
        laco = asyncio.get_running_loop()
        fonte = self._fonte_da_tela()
        fechou = self.bus.subscribe(EventTopic.JOGO_FECHOU)
        vendo = [self._quem_ve_a_tela()]

        def publicar(carga: dict[str, Any]) -> None:
            laco.call_soon_threadsafe(self.bus.publish, TOPICO_DA_TELA, carga)

        captura = Captura(fonte, TelaDoJogo(tuple(self._regioes_da_tela.values())),
                          publicar=publicar,
                          assinantes=lambda: vendo[0],
                          nascidas=lambda: self._pedidos_da_tela)
        passo: asyncio.Future[None] | None = None
        recusas = 0
        try:
            while True:
                if not fechou.empty():
                    while not fechou.empty():
                        fechou.get_nowait()
                    for con in self._conexoes:
                        con.ve_a_tela = False
                vendo[0] = self._quem_ve_a_tela()
                captura.tela.regioes = tuple(self._regioes_da_tela.values())
                passo = laco.run_in_executor(None, captura.passo)
                await asyncio.shield(passo)
                if captura.recusas != recusas:
                    recusas = captura.recusas
                    for con in self._conexoes:
                        con.ve_a_tela = False
                if not captura.aberta and not any(con.ve_a_tela for con in self._conexoes):
                    return
                await asyncio.sleep(1.0 / HZ_DA_TELA)
        finally:
            self.bus.unsubscribe(EventTopic.JOGO_FECHOU, fechou)
            if passo is not None and not passo.done():
                captura.parar()
                await asyncio.wait({passo}, timeout=PRAZO_DA_CAPTURA_SAIR_S)
            if self.bus.subscriber_count(TOPICO_DA_TELA) <= 0:
                self._regioes_da_tela.clear()
            if captura.aberta:
                fonte.fechar()

    def _desassinar(self, con: _Conexao, params: dict[str, Any]) -> dict[str, Any]:
        """Larga cada tópico: sem fila de ``movimento`` (ou de dedos), o tique para de pedir o
        leitor e o prazo da demanda o fecha. Um tópico não assinado recusa tudo, sem efeito."""
        topicos = params.get("topicos")
        if not isinstance(topicos, list) or not topicos:
            raise RecusaError(CODE_INVALID_PARAMS, "eventos.desassinar pede a lista topicos")
        for publico in topicos:
            if not isinstance(publico, str) or publico not in con.assinados:
                raise RecusaError(CODE_INVALID_PARAMS, f"tópico não assinado: {publico}")
        largados = list(dict.fromkeys(topicos))
        for publico in largados:
            con.desassinar(publico, self.bus)
        return {"desassinados": largados}

    async def _ligar_a_chave_de(self, sessao: _Credencial) -> dict[str, Any]:
        """O ``chave.ligar``: a extensão liga a própria chave, gravada como o clique da janela.
        Só a da extensão que pede, e só com a ``chave`` no manifesto instalado."""
        if self._ligar_a_chave is None or not await self._ligar_a_chave(sessao.mod_id):
            raise RecusaError(CODE_SEM_PERMISSAO, "a extensão não declara a chave")
        return {"ligada": True}

    def _lista_dos_controles(self, sessao: _Credencial) -> dict[str, Any]:
        """Os controles ligados agora, ``{controles: [{uniq, jogador, cor?}]}``, a quem lê a
        conexão; ``cor`` é o nome do plástico, quando o serviço o sabe.

        Sem a lista do serviço, vale o controle do posto. Nunca levanta: a lista que falha é vazia.
        """
        if "ler:conexao" not in sessao.permissoes:  # (noqa-acento)
            raise RecusaError(CODE_SEM_PERMISSAO,
                              "falta a permissão ler:conexao")  # (noqa-acento)
        try:
            if self._controles is not None:
                brutos = self._controles()
            else:
                posto = self._uniq_do_posto()
                brutos = [{"uniq": posto, "jogador": None}] if posto else []
        except Exception as exc:
            logger.debug("mods_porta_lista_dos_controles_falhou", err=str(exc))
            brutos = []
        controles: list[dict[str, Any]] = []
        for bruto in brutos:
            uniq = bruto.get("uniq") if isinstance(bruto, dict) else None
            if not isinstance(uniq, str) or not uniq or any(c["uniq"] == uniq for c in controles):
                continue
            jogador = bruto.get("jogador")
            ok = isinstance(jogador, int) and not isinstance(jogador, bool) and jogador >= 1
            cor = bruto.get("cor")
            controles.append({"uniq": uniq, "jogador": jogador if ok else None,
                              **({"cor": cor.strip()[:40]}
                                 if isinstance(cor, str) and cor.strip() else {})})
        return {"controles": controles}

    def _publicar(self, con: _Conexao, params: dict[str, Any]) -> dict[str, Any]:
        """O ``eventos.publicar``: confere a permissão e os dados, e põe ``origem`` e ``t``."""
        assert con.sessao is not None
        topico = params.get("topico")
        if not isinstance(topico, str) or topico not in TOPICOS_DE_PUBLICACAO:
            raise RecusaError(CODE_INVALID_PARAMS, f"tópico que não se publica: {topico}")
        if f"publicar:{topico}" not in con.sessao.permissoes:
            raise RecusaError(CODE_SEM_PERMISSAO, f"falta a permissão publicar:{topico}")
        pedidas = _funcoes_do_acessorio(params.get("dados"))
        if len(set(con.funcoes_do_acessorio) | set(pedidas)) > FUNCOES_POR_PEDIDO:
            raise RecusaError(
                CODE_INVALID_PARAMS,
                f"eventos.publicar aceita até {FUNCOES_POR_PEDIDO} funções por extensão.",
            )
        mod_id = con.sessao.mod_id
        agora = self._relogio()
        janela = self._publicacoes.setdefault(mod_id, deque())
        while janela and agora - janela[0] >= 1.0:
            janela.popleft()
        if len(janela) >= PUBLICACOES_POR_SEGUNDO:
            raise RecusaError(
                CODE_INVALID_PARAMS,
                f"eventos.publicar aceita até {PUBLICACOES_POR_SEGUNDO} por segundo por extensão.",
            )
        janela.append(agora)
        evento = {"funcoes": pedidas, "origem": mod_id, "t": agora}  # (noqa-acento)
        self.bus.publish(TOPICOS_DE_PUBLICACAO[topico], evento)
        con.funcoes_do_acessorio.update(pedidas)
        return {"publicado": True}

    def _soltar_o_acessorio(self, mod_id: str, funcoes: dict[str, float]) -> None:
        """Quem publicou saiu: o serviço publica, em nome dele, o zero de cada função usada."""
        self.bus.publish(EventTopic.JOGO_ACESSORIO, {
            "funcoes": dict.fromkeys(funcoes, 0.0),  # (noqa-acento)
            "origem": mod_id,
            "t": self._relogio(),
        })

    def _estado_dos_acessorios(self, con: _Conexao, params: dict[str, Any]) -> dict[str, Any]:
        """O estado que a extensão devolve: a janela da extensão e a aba Conexões o mostram.

        Só com ``ler:acessorios.gesto`` ele vai ao barramento e liga os gestos do PS; com
        ``publicar:acessorios.estado`` ele só se mostra, e os gestos ficam os de sempre.
        """
        assert con.sessao is not None
        if not con.sessao.permissoes & set(PERMISSOES_DO_ESTADO):
            raise RecusaError(
                CODE_SEM_PERMISSAO,
                "falta a permissão publicar:acessorios.estado ou ler:acessorios.gesto",
            )
        estado = estado_dos_acessorios(con.sessao.mod_id, params,
                                       acoes_dos_aparelhos=con.sessao.acoes_dos_aparelhos)
        con.deu_o_estado = True
        serie = self._series[con.sessao.mod_id] = self._series.get(con.sessao.mod_id, 0) + 1
        self._estados_dos_acessorios[con.sessao.mod_id] = {**estado, "serie": serie}
        if estado.get("ligado") is not True:
            self._esquecer_as_escritas(con.sessao.mod_id)
        if "ler:acessorios.gesto" in con.sessao.permissoes:
            self.bus.publish(EventTopic.ACESSORIOS_ESTADO, estado)
        return {"recebido": True}

    def _jogos_do_lancador(self, sessao: _Credencial, params: dict[str, Any]) -> dict[str, Any]:
        """O ``lancador.jogos``: a lista inteira substitui a anterior desta extensão."""
        if "lancador" not in sessao.permissoes:
            raise RecusaError(CODE_SEM_PERMISSAO, "falta a permissão lancador")
        if not sessao.comandos:
            raise RecusaError(
                CODE_INVALID_PARAMS, "o manifesto não declara lancador.comandos")
        jogos = jogos_do_lancador(params, sessao.comandos)
        self._jogos_dos_lancadores[sessao.mod_id] = jogos
        return {"recebidos": len(jogos)}

    async def _abrir_do_lancador(self, sessao: _Credencial,
                                 params: dict[str, Any]) -> dict[str, Any]:
        """O ``lancador.abrir {chave}``: o jogo que a própria extensão entregou no
        ``lancador.jogos`` abre fora da caixa, pelo ``hefesto-launch``; nunca o de outra."""
        if "pedir:lancador.abrir" not in sessao.permissoes:
            raise RecusaError(CODE_SEM_PERMISSAO, "falta a permissão pedir:lancador.abrir")
        chave = params.get("chave")
        if not isinstance(chave, str) or not chave:
            raise RecusaError(CODE_INVALID_PARAMS, "lancador.abrir pede a chave do jogo")
        jogo = next((j for j in self._jogos_dos_lancadores.get(sessao.mod_id, [])
                     if j["chave"] == chave), None)
        if jogo is None:
            de_outra = any(j["chave"] == chave for mod, jogos in self._jogos_dos_lancadores.items()
                           if mod != sessao.mod_id for j in jogos)
            raise RecusaError(
                CODE_SEM_PERMISSAO if de_outra else CODE_INVALID_PARAMS,
                f"o jogo {chave} é de outra extensão" if de_outra
                else f"o jogo {chave} não está no lancador.jogos desta extensão")
        argv = list(jogo["abrir"])
        if argv[0] not in sessao.comandos:
            raise RecusaError(
                CODE_SEM_PERMISSAO, f"o comando {argv[0]!r} não está em lancador.comandos")
        if not termos_do_abrir(argv[1:]):
            raise RecusaError(
                CODE_SEM_PERMISSAO,
                "o jogo só abre com o comando e o id dele: sem opção, sem endereço e sem «=»")
        try:
            argv[0] = await asyncio.to_thread(
                comando_fora_da_caixa, argv[0], caminho_da_sessao(), pastas_que_a_caixa_escreve())
        except ValueError as exc:
            logger.warning("mods_porta_comando_recusado", mod=sessao.mod_id, err=str(exc))
            raise RecusaError(CODE_NAO_ESCREVEU, "o jogo não abriu") from exc
        try:
            caminho = await asyncio.to_thread(self._abrir_o_jogo, sessao.mod_id, argv)
        except Exception as exc:
            logger.warning("mods_porta_jogo_nao_abriu", mod=sessao.mod_id, err=str(exc))
            raise RecusaError(CODE_NAO_ESCREVEU, "o jogo não abriu") from exc
        logger.info("mods_porta_jogo_aberto", mod=sessao.mod_id, chave=chave, caminho=caminho)
        return {"aberto": True, "chave": chave}

    async def _ligar_a_mira(self, sessao: _Credencial,
                            params: dict[str, Any]) -> dict[str, Any]:
        """O ``mira.ligada {uniq|"todos", ligada}``: o giroscópio de um controle cuja seção
        Controles está no modo da extensão, desligado enquanto a extensão vale; num jogo com
        anticheat, só com a chave «Peso da mira» do jogo ligada. Volta no ``ligada: true``, quando
        a seção sai do modo, na saída da extensão e no «Parar tudo»."""
        if "escrever:mira" not in sessao.permissoes:
            raise RecusaError(CODE_SEM_PERMISSAO, "falta a permissão escrever:mira")
        alvo, ligada = params.get("uniq"), params.get("ligada")
        if not isinstance(alvo, str) or not alvo.strip():
            raise RecusaError(CODE_INVALID_PARAMS, "mira.ligada pede o uniq, ou «todos»")
        if not isinstance(ligada, bool):
            raise RecusaError(CODE_INVALID_PARAMS, "mira.ligada pede ligada true ou false")
        alvo = alvo.strip()
        if ligada:
            PESO_DA_MIRA.ligar(sessao.mod_id, alvo)
            return {"status": "ok", "ligada": True}
        if barra := await self._anticheat_que_barra(self._jogo_aberto()):
            raise RecusaError(
                CODE_NAO_ESCREVEU,
                f"este jogo usa {barra}: desligar o giroscópio pede a chave do jogo ligada")
        no_modo = self._no_modo_da_extensao(sessao)
        alvos = sorted(no_modo) if alvo == TODOS_OS_CONTROLES else [
            a for a in (chave_de_sensor(alvo),) if a in no_modo]
        if not alvos:
            raise RecusaError(
                CODE_NAO_ESCREVEU, "a seção Controles deste controle não está no modo da extensão")
        for um in alvos:
            PESO_DA_MIRA.desligar(sessao.mod_id, um)
        self._vigiar_o_peso()
        return {"status": "ok", "ligada": False}

    def _escalar_a_vibracao(self, sessao: _Credencial,
                            params: dict[str, Any]) -> dict[str, Any]:
        """O ``vibracao.escala {uniq, escala}``: de 0 a 1, multiplica a força de tudo o que vai
        ao motor daquele controle, o jogo e as extensões; 1 devolve a força inteira. Abaixo de 1,
        só no controle cuja seção Controles está no modo da extensão, e sai quando a seção deixa o
        modo."""
        if "escrever:vibracao" not in sessao.permissoes:
            raise RecusaError(CODE_SEM_PERMISSAO, "falta a permissão escrever:vibracao")
        uniq = _uniq_do_pedido(params, "vibracao.escala")
        escala: Any = params.get("escala")
        if not _numero(escala) or not 0 <= escala <= 1:
            raise RecusaError(CODE_INVALID_PARAMS, "vibracao.escala pede a escala de 0 a 1")
        chave = chave_de_sensor(uniq)
        if escala < 1 and chave not in self._no_modo_da_extensao(sessao):
            raise RecusaError(
                CODE_NAO_ESCREVEU, "a seção Controles deste controle não está no modo da extensão")
        ESCALA_DA_VIBRACAO.pedir(sessao.mod_id, uniq, float(escala))
        self._escalas = {(d, u) for d, u in self._escalas
                         if d != sessao.mod_id or chave_de_sensor(u) != chave}
        if escala < 1:
            self._escalas.add((sessao.mod_id, uniq))
            self._vigiar_o_peso()
        return {"status": "ok", "escala": float(escala)}

    def _ligar_o_corpo(self, sessao: _Credencial, params: dict[str, Any]) -> dict[str, Any]:
        """O ``corpo.ligar {uniq, som_no_corpo?, gatilhos?: {tipo, forca}, ate_ms}``: o Som no
        corpo e o padrão dos motores no L2 e no R2 do tato vivo, num controle, até ``ate_ms``; o
        pedido se renova pedindo de novo, e o vazio solta. O que o perfil liga segue valendo, e
        o mais forte vale; no Modo Nativo e no Steam Input o jogo fala direto com o controle.

        Com o Som no corpo pedido, a resposta diz o desfecho de agora em ``corpo``: ``tocando``, ou
        ``cedeu`` com o ``motivo`` (``sem_aparelho``, ``forca_zero``, ``sem_endpoint``,
        ``jogo_no_endpoint``, ``radio_cede``). O Modo Nativo e o Steam Input recusam com
        ``CODE_O_JOGO_ESCREVE``."""
        from hefesto_dualsense4unix.daemon.subsystems.tato_vivo import (
            PedidoDoCorpo,
            o_modo_cala_a_extensao,
        )

        if "escrever:corpo" not in sessao.permissoes:
            raise RecusaError(CODE_SEM_PERMISSAO, "falta a permissão escrever:corpo")
        uniq = _uniq_do_pedido(params, "corpo.ligar")
        ate_ms, corpo = params.get("ate_ms"), params.get("som_no_corpo", 0.0)
        gatilhos = params.get("gatilhos")
        if isinstance(ate_ms, bool) or not isinstance(ate_ms, int):
            raise RecusaError(CODE_INVALID_PARAMS, "corpo.ligar pede ate_ms em milissegundos")
        if not _numero(corpo):
            raise RecusaError(CODE_INVALID_PARAMS, "corpo.ligar pede o som_no_corpo de 0 a 1")
        if gatilhos is not None and not (
                isinstance(gatilhos, dict) and isinstance(gatilhos.get("tipo"), str)
                and _numero(gatilhos.get("forca"))):
            raise RecusaError(CODE_INVALID_PARAMS, "corpo.ligar pede gatilhos: {tipo, forca}")
        fonte = self._fonte()
        if fonte is None:
            raise RecusaError(CODE_NAO_ESCREVEU, "o tato vivo não subiu")
        modo = fonte.modo_de(uniq)
        if modo is None:
            raise RecusaError(CODE_NAO_ESCREVEU, "corpo.ligar: nenhum controle tem esse uniq")
        if o_modo_cala_a_extensao(modo):
            raise RecusaError(CODE_O_JOGO_ESCREVE, _FRASE_DO_MODO_QUE_CALA.get(
                str(modo), _FRASE_DO_MODO_QUE_CALA["nativo"]), {"canal": "corpo", "modo": modo})
        pedido = PedidoDoCorpo(
            float(corpo),
            None if gatilhos is None else str(gatilhos["tipo"]),
            0.0 if gatilhos is None else float(gatilhos["forca"]))
        try:
            fonte.corpo.pedir(_origem(sessao), uniq, pedido, ate_ms)
        except ValueError as exc:
            raise RecusaError(CODE_INVALID_PARAMS, f"corpo.ligar: {exc}") from exc
        resposta: dict[str, Any] = {"status": "ok"}
        if pedido.som_no_corpo > 0:
            self._anotar_a_escrita(sessao.mod_id, "haptica", uniq)
            motivo = fonte.desfecho_do_corpo(uniq)
            resposta.update({"corpo": "tocando"} if motivo is None else {
                "corpo": "cedeu", "motivo": motivo})
        if pedido.tipo is not None:
            self._anotar_a_escrita(sessao.mod_id, "vibracao", uniq)
        return resposta

    def _soltar_os_ajustes(self, mod_id: str) -> None:
        PESO_DA_MIRA.soltar(mod_id)
        PESO_DA_MIRA.religar_de(mod_id)
        ESCALA_DA_VIBRACAO.soltar(mod_id)
        self._escalas = {(d, u) for d, u in self._escalas if d != mod_id}
        if self._acordar_o_vigia is not None:
            self._acordar_o_vigia.set()

    async def _soltar_a_vibracao(self, sessao: _Credencial, uniqs: set[str]) -> None:
        """Quem vibrou saiu: os motores que ele deixou ligados param, se o jogo não os tem."""
        fonte = self._fonte()
        for uniq in sorted(uniqs):
            if fonte is None and self._o_jogo_escreve(uniq, "vibracao"):
                continue
            agora = fonte.relogio() if fonte is not None else 0.0
            if fonte is not None and any(
                    fonte.rival(uniq, "vibracao", lado, "", agora)[1] > 0 for lado in _LADOS):
                continue
            try:
                await self._escritor("rumble.set", {"uniq": uniq, "weak": 0, "strong": 0})
            except Exception as exc:
                logger.warning("mods_porta_vibracao_nao_soltou", mod=sessao.mod_id,
                               err=type(exc).__name__)

    def jogos_de(self, mod_id: str) -> list[dict[str, Any]]:
        """O último ``lancador.jogos`` de ``mod_id``; sem conexão viva, a lista vazia."""
        viva = any(
            con.sessao is not None and con.sessao.mod_id == mod_id for con in self._conexoes
        )
        return [dict(j) for j in self._jogos_dos_lancadores.get(mod_id, [])] if viva else []

    def agora_de(self, mod_id: str) -> dict[str, Any]:
        """O último ``acessorios.estado`` de ``mod_id``; sem conexão viva, o estado vazio.

        A coluna «Agora» da janela lê daqui: extensão parada ou que nunca devolveu o estado
        mostra a coluna vazia, sem número inventado. Com um jogo em cena, ``jogo`` é a chave
        dele, a da linha «Memória neste jogo».
        """
        estado = self.ultimo_estado_de(mod_id)
        saida = estado_vazio_dos_acessorios(mod_id) if estado is None else dict(estado)
        jogo = self._jogo_aberto()
        if estado is not None:
            saida["ao_vivo"] = self.ao_vivo_de(mod_id)
        return {**saida, "jogo": jogo} if jogo else saida

    def _anotar_a_escrita(self, mod_id: str, canal: str, uniq: str) -> None:
        """O que chegou ao controle, para o controle aceso da janela: só o que foi escrito de fato
        (nem a recusa, nem o pedido coberto por um mais forte); o ``uniq`` vazio é o de todos.
        Guarda só a última escrita de cada canal, de no máximo ``CONTROLES_DO_AO_VIVO``
        controles (o seguinte tira o que escreveu há mais tempo) e mais a de todos."""
        porcontrole = self._escritas.setdefault(mod_id, {})
        if uniq not in porcontrole and uniq and sum(
                1 for u in porcontrole if u) >= CONTROLES_DO_AO_VIVO:
            velho = min((u for u in porcontrole if u),
                        key=lambda u: max(porcontrole[u].values(), default=0.0))
            del porcontrole[velho]
        porcontrole.setdefault(uniq, {})[canal] = self._relogio()

    def _esquecer_as_escritas(self, mod_id: str) -> None:
        """A extensão desligou ou saiu: o controle da janela fica apagado."""
        self._escritas.pop(mod_id, None)

    def _controles_do_ao_vivo(self) -> list[dict[str, Any]]:
        if self._controles is None:
            return []
        try:
            brutos = self._controles()
        except Exception:
            logger.debug("mods_porta_ao_vivo_sem_controles", exc_info=True)
            return []
        return [c for c in brutos if isinstance(c, dict) and isinstance(c.get("uniq"), str)]

    def ao_vivo_de(self, mod_id: str) -> dict[str, Any]:
        """O ``ao_vivo`` do ``mods.agora``: os controles ligados (``{jogador, cor}``) e o que a
        extensão escreveu há no máximo ``ACESO_DO_AO_VIVO_S``, uma ``escrita`` por canal e
        controle, ``{canal, controle, ha_ms, todos?}``; ``controle`` é o lugar na lista, nulo
        para o controle fora da lista. Nunca leva o ``uniq``."""
        agora = self._relogio()
        porcontrole = self._escritas.get(mod_id) or {}
        controles = self._controles_do_ao_vivo()
        posicao_de = {c["uniq"]: n for n, c in enumerate(controles)}
        escritas: list[dict[str, Any]] = []
        for uniq, canais in porcontrole.items():
            for canal, t in canais.items():
                if agora - t > ACESO_DO_AO_VIVO_S:
                    continue
                escritas.append({"canal": canal, "controle": posicao_de.get(uniq),
                                 "ha_ms": max(0, round((agora - t) * 1000)),
                                 **({"todos": True} if not uniq else {})})
        escritas.sort(key=lambda e: (e["ha_ms"], e["canal"]))
        return {"controles": [{"jogador": _jogador_do_ao_vivo(c.get("jogador")),
                               "cor": str(c.get("cor") or "")} for c in controles],
                "escritas": escritas}

    def ultimo_estado_de(self, mod_id: str) -> dict[str, Any] | None:
        """O ``acessorios.estado`` guardado de ``mod_id`` (o próprio objeto), com conexão viva."""
        viva = any(
            con.sessao is not None and con.sessao.mod_id == mod_id for con in self._conexoes
        )
        return self._estados_dos_acessorios.get(mod_id) if viva else None

    def parar_tudo(self, mod_id: str) -> bool:
        """O «Parar tudo» da janela, só para ``mod_id``.

        A conexão que não lê o gesto recebe o evento ``extensao.parar`` pelo próprio socket, sem
        assinatura. O gesto ``para`` sai sempre no tópico do gesto do PS (``acessorios.gesto``),
        com ``mod`` dizendo a quem ele vai e sem controle (``uniq`` nulo): a extensão que o lê o
        recebe por ali, o supervisor confere o parar da extensão, e a outra extensão não o recebe.
        ``False`` quando a extensão não está conectada à porta (nada a parar).
        """
        conexoes_do_mod = [con for con in self._conexoes
                 if con.sessao is not None and con.sessao.mod_id == mod_id]
        if not conexoes_do_mod:
            return False
        self._soltar_os_ajustes(mod_id)
        for con in conexoes_do_mod:
            assert con.sessao is not None
            if "ler:acessorios.gesto" not in con.sessao.permissoes and con.escritor is not None:
                self._avisar(con, con.escritor, EVENTO_DO_PARAR, {"mod": mod_id})
        self.bus.publish(EventTopic.ACESSORIOS_GESTO, {
            "uniq": None, "jogador": None, "gesto": "para", "valor": 0, "mod": mod_id,
        })
        return True

    def _avisar(self, con: _Conexao, writer: asyncio.StreamWriter, nome: str,
                dados: dict[str, Any]) -> None:
        """Um ``evento`` fora de assinatura (``topico`` = ``nome``), sem esperar o socket."""
        linha = json.dumps({
            "jsonrpc": PROTOCOL_VERSION, "method": "evento",
            "params": {"topico": nome, "nome": nome, "uniq": None, "dados": dados},
        }, ensure_ascii=False).encode()
        tarefa = asyncio.get_running_loop().create_task(self._enviar(con, writer, linha))
        con.tarefas.append(tarefa)
        tarefa.add_done_callback(lambda t: con.tarefas.remove(t) if t in con.tarefas else None)

    def _conexoes_de(self, mod_id: str) -> list[_Conexao]:
        return [con for con in self._conexoes
                if con.sessao is not None and con.sessao.mod_id == mod_id
                and con.escritor is not None]

    def _avisar_a(self, mod_id: str, nome: str, dados: dict[str, Any]) -> bool:
        """O evento ``nome`` a cada conexão de ``mod_id``, e a nenhuma outra."""
        conexoes_do_mod = self._conexoes_de(mod_id)
        for con in conexoes_do_mod:
            assert con.escritor is not None
            self._avisar(con, con.escritor, nome, dados)
        return bool(conexoes_do_mod)

    def acao(self, mod_id: str, acao: str, *, alvo: str | None = None,
             valor: bool | str | None = None) -> bool:
        """O clique numa ação da janela: ``extensao.acao`` só para as conexões de ``mod_id``.

        ``alvo`` é o ``id`` do aparelho (as ``aparelhos_acoes`` e os ``controles`` dele); ``valor``
        é a chave ``ligar`` ou a de um controle (``True`` liga), ou o ``id`` da opção escolhida
        numa paleta ou numa escolha. ``False`` quando a extensão não está conectada à porta.
        """
        dados: dict[str, Any] = {"mod": mod_id, "acao": acao, "alvo": alvo}  # (noqa-acento)
        if valor is not None:
            dados["valor"] = valor
        return self._avisar_a(mod_id, EVENTO_DA_ACAO, dados)

    def barra(self, mod_id: str, barra_id: str, alvo: str, valor: float, *,
              soltou: bool) -> bool:
        """A barra de um aparelho: ``extensao.acao`` com o ``alvo``, o ``valor`` e o ``soltou``,
        só para ``mod_id``. O arrastar vai no compasso do ``livre`` (o valor mais novo a cada
        ``1 / LIVRE_POR_SEGUNDO`` s); o soltar sai na hora, cancela o que esperava e leva o valor
        final, que a extensão grava. ``False`` sem a extensão na porta."""
        if not self._conexoes_de(mod_id):
            return False
        numero: int | float = int(valor) if float(valor).is_integer() else float(valor)
        dados: dict[str, Any] = {"mod": mod_id, "acao": barra_id, "alvo": alvo,  # (noqa-acento)
                                 "valor": numero, "soltou": soltou}
        chave = (mod_id, f"{barra_id}:{alvo}")
        if soltou:
            compasso = self._barras.pop(chave, None)
            if compasso is not None:
                compasso.cancelar()
            return self._avisar_a(mod_id, EVENTO_DA_ACAO, dados)
        compasso = self._barras.setdefault(chave, _Compasso())
        compasso.pendente = dados
        if compasso.relogio is None:
            compasso.relogio = asyncio.get_running_loop().call_later(
                1.0 / LIVRE_POR_SEGUNDO, self._fim_do_compasso, chave, self._barras,
                EVENTO_DA_ACAO)
        return True

    async def acao_com_resposta(self, mod_id: str, acao: str, *, alvo: str | None = None,
                                valor: bool | str | None = None) -> dict[str, Any]:
        """A ação que o manifesto declara com ``responde``: o ``extensao.acao`` leva o ``id`` e a
        porta espera a ``extensao.resposta {para: id, dados}`` por até
        :data:`PRAZO_DA_RESPOSTA_S`. ``{enviada, respondeu, resposta}``: ``enviada`` falso sem a
        extensão na porta; ``respondeu`` falso sem a resposta no prazo."""
        if not self._conexoes_de(mod_id):
            return {"enviada": False, "respondeu": False, "resposta": None}
        dados: dict[str, Any] = {"mod": mod_id, "acao": acao, "alvo": alvo}  # (noqa-acento)
        if valor is not None:
            dados["valor"] = valor
        respondeu, resposta = await self._esperar_a_resposta(mod_id, EVENTO_DA_ACAO, dados, "a")
        return {"enviada": True, "respondeu": respondeu, "resposta": resposta}

    async def _esperar_a_resposta(self, mod_id: str, evento: str, dados: dict[str, Any],
                                  prefixo: str) -> tuple[bool, Any]:
        """Avisa ``mod_id`` com um ``id`` novo nos ``dados`` e espera a ``extensao.resposta``
        dele: ``(respondeu, resposta)``."""
        self._serie_da_mensagem += 1
        ident = f"{prefixo}{self._serie_da_mensagem}"
        espera: asyncio.Future[Any] = asyncio.get_running_loop().create_future()
        self._esperas[ident] = (mod_id, espera)
        try:
            self._avisar_a(mod_id, evento, {**dados, "id": ident})
            try:
                return True, await asyncio.wait_for(espera, PRAZO_DA_RESPOSTA_S)
            except asyncio.TimeoutError:
                return False, None
        finally:
            self._esperas.pop(ident, None)

    def livre(self, mod_id: str, opcao_id: str, valor: float, *, soltou: bool,
              modo: str | None = None) -> bool:
        """O arrastar do ``livre``: ``extensao.livre {mod, id, valor, soltou, modo?}`` só para
        ``mod_id``; ``modo`` vai só quando o ``livre`` declara ``modos``.

        No máximo ``LIVRE_POR_SEGUNDO`` eventos por segundo: o primeiro arrastar abre um compasso
        de ``1 / LIVRE_POR_SEGUNDO`` s, e ao fim dele sai o valor mais novo. O soltar sai na hora,
        cancela o que esperava e leva o valor final. ``False`` sem a extensão na porta.
        """
        if not self._conexoes_de(mod_id):
            return False
        dados: dict[str, Any] = {"mod": mod_id, "id": opcao_id,
                                 "valor": round(min(1.0, max(0.0, valor)), 3), "soltou": soltou}
        if modo is not None:
            dados["modo"] = modo
        chave = (mod_id, opcao_id)
        compasso = self._livres.setdefault(chave, _Compasso())
        if soltou:
            compasso.cancelar()
            self._livres.pop(chave, None)
            return self._avisar_a(mod_id, EVENTO_DO_LIVRE, dados)
        compasso.pendente = dados
        if compasso.relogio is None:
            compasso.relogio = asyncio.get_running_loop().call_later(
                1.0 / LIVRE_POR_SEGUNDO, self._fim_do_compasso, chave)
        return True

    def _fim_do_compasso(self, chave: tuple[str, str],
                         compassos: dict[tuple[str, str], _Compasso] | None = None,
                         evento: str = EVENTO_DO_LIVRE) -> None:
        compasso = (self._livres if compassos is None else compassos).get(chave)
        if compasso is None:
            return
        dados, compasso.pendente, compasso.relogio = compasso.pendente, None, None
        if dados is not None:
            self._avisar_a(chave[0], evento, dados)

    def opcao_viva(self, mod_id: str, opcao_id: str, valor: float) -> bool:
        """O arrastar de um deslizante da janela: ``extensao.opcao {mod, id, valor}`` só para
        ``mod_id``, no compasso do ``livre`` (o valor mais novo a cada ``1 / LIVRE_POR_SEGUNDO``
        s). Quem grava é o soltar, no ``opcoes.json``. ``False`` sem a extensão na porta."""
        if not self._conexoes_de(mod_id):
            return False
        chave = (mod_id, opcao_id)
        compasso = self._opcoes_vivas.setdefault(chave, _Compasso())
        compasso.pendente = {"mod": mod_id, "id": opcao_id, "valor": valor}
        if compasso.relogio is None:
            compasso.relogio = asyncio.get_running_loop().call_later(
                1.0 / LIVRE_POR_SEGUNDO, self._fim_do_compasso, chave, self._opcoes_vivas,
                EVENTO_DA_OPCAO)
        return True

    async def mensagem(self, mod_id: str, dados: Any) -> dict[str, Any]:
        """O que a página da janela de ``mod_id`` mandou: ``extensao.mensagem {mod, id, dados}``
        só para ``mod_id``, que responde com ``extensao.resposta {para: id, dados}`` em até
        :data:`PRAZO_DA_RESPOSTA_S`. ``dados`` cabe em :data:`TETO_DA_MENSAGEM` bytes, e passam
        até :data:`MENSAGENS_POR_SEGUNDO` por segundo por extensão (o resto é recusado).

        ``{enviada, respondeu, resposta}``: ``enviada`` falso sem a extensão na porta;
        ``respondeu`` falso quando a extensão não respondeu a tempo.
        """
        if _tamanho_da_mensagem(dados) > TETO_DA_MENSAGEM:
            raise RecusaError(CODE_INVALID_PARAMS, "a mensagem da página passa de 64 KB")
        if not self._conexoes_de(mod_id):
            return {"enviada": False, "respondeu": False, "resposta": None}
        agora = self._relogio()
        janela = self._mensagens.setdefault(mod_id, deque())
        while janela and agora - janela[0] >= 1.0:
            janela.popleft()
        if len(janela) >= MENSAGENS_POR_SEGUNDO:
            raise RecusaError(
                CODE_INVALID_PARAMS,
                f"a página manda até {MENSAGENS_POR_SEGUNDO} mensagens por segundo")
        janela.append(agora)
        respondeu, resposta = await self._esperar_a_resposta(
            mod_id, EVENTO_DA_MENSAGEM, {"mod": mod_id, "dados": dados}, "m")
        return {"enviada": True, "respondeu": respondeu, "resposta": resposta}

    def _responder(self, mod_id: str, params: dict[str, Any]) -> dict[str, Any]:
        """``extensao.resposta {para, dados}``: a resposta à mensagem ``para`` volta à página; só a
        extensão a quem a mensagem foi pode respondê-la, e uma vez."""
        para = params.get("para")
        achada = self._esperas.get(para) if isinstance(para, str) else None
        if achada is None or achada[0] != mod_id or achada[1].done():
            raise RecusaError(CODE_INVALID_PARAMS,
                              "extensao.resposta pede o id de uma mensagem desta extensão")
        dados = params.get("dados")
        if _tamanho_da_mensagem(dados) > TETO_DA_MENSAGEM:
            raise RecusaError(CODE_INVALID_PARAMS, "a resposta à página passa de 64 KB")
        achada[1].set_result(dados)
        return {"entregue": True}

    def le_os_botoes(self) -> bool:
        """Alguma extensão assinou o tópico ``botoes``? Sem assinante, o tique não lê controle."""
        return any(con.filas_dos_botoes for con in self._conexoes)

    def botoes_do_tique(
        self,
        apertados: dict[str | None, frozenset[str]],
        jogador_de: Callable[[str | None], int | None],
    ) -> None:
        """As bordas deste tique, de cada controle: ``button.down`` e ``button.up`` com o dele.

        ``apertados`` é ``{uniq: botões}`` de todo controle lido no tique. O controle que
        sumiu solta o que segurava. Roda no laço do serviço; nunca espera o socket (a fila
        cheia junta as bordas de um botão, :class:`_FilaDosBotoes`).
        """
        filas = [f for con in self._conexoes for f in con.filas_dos_botoes]
        antes, self._botoes_antes = self._botoes_antes, dict(apertados) if filas else None
        if not filas or antes is None:
            return
        for uniq in dict.fromkeys([*antes, *apertados]):
            agora, de_antes = apertados.get(uniq, frozenset()), antes.get(uniq, frozenset())
            descidos, subidos = sorted(agora - de_antes), sorted(de_antes - agora)
            if not descidos and not subidos:
                continue
            jogador = jogador_de(uniq)
            for apertado, botoes in ((True, descidos), (False, subidos)):
                for botao in botoes:
                    carga = {"button": botao, "botao": botao, "pressed": apertado,
                             "uniq": uniq, "jogador": jogador}
                    for fila in filas:
                        fila.por(carga)

    def le_as_entradas(self) -> bool:
        """Alguma extensão assinou o tópico ``entradas``? Sem assinante, o tique não lê controle."""
        return any(con.filas_das_entradas for con in self._conexoes)

    def pede_os_dedos(self) -> bool:
        """Alguma extensão inscrita em ``entradas`` pediu os dedos (``dedos: true``)?"""
        return any(con.quer_os_dedos and con.filas_das_entradas for con in self._conexoes)

    def entradas_do_tique(self, leituras: dict[str | None, dict[str, Any]]) -> None:
        """As ``entradas`` deste tique: ``{uniq: {jogador, transporte, valores}}`` de todo controle.

        Cada controle sai quando algo passou da faixa morta (:func:`_mudou`), no máximo
        :data:`ENTRADAS_POR_SEGUNDO` vezes por segundo; o que o teto segura sai num tique
        seguinte, então o último valor sempre chega. O controle que sumiu fora do repouso sai
        uma vez em repouso. Roda no laço do serviço e nunca espera o socket.
        """
        filas = [f for con in self._conexoes for f in con.filas_das_entradas]
        if not filas:
            self._entradas_enviadas = {}
            return
        agora = self._relogio()
        intervalo = 1.0 / ENTRADAS_POR_SEGUNDO
        for uniq in dict.fromkeys([*self._entradas_enviadas, *leituras]):
            leitura = leituras.get(uniq)
            antes = self._entradas_enviadas.get(uniq)
            if leitura is None:
                self._repouso_de(uniq)
                continue
            valores: _Valores = leitura["valores"]
            base = antes[0] if antes is not None else REPOUSO_DAS_ENTRADAS
            if not _mudou(base, valores):
                continue
            if antes is not None and agora - antes[1] < intervalo:
                continue
            jogador, via = leitura.get("jogador"), leitura.get("transporte")
            self._entradas_enviadas[uniq] = (valores, agora, jogador, via)
            carga = _carga_das_entradas(uniq, jogador, via, valores)
            for fila in filas:
                _por_na_fila(fila, carga)

    def _repouso_de(self, uniq: str | None) -> None:
        """Quem saiu fora do repouso sai uma vez em repouso: o aparelho não fica preso."""
        antes = self._entradas_enviadas.pop(uniq, None)
        if antes is None or antes[0] == REPOUSO_DAS_ENTRADAS:
            return
        carga = _carga_das_entradas(uniq, antes[2], antes[3], REPOUSO_DAS_ENTRADAS)
        for fila in (f for con in self._conexoes for f in con.filas_das_entradas):
            _por_na_fila(fila, carga)

    async def _repousar_quem_sai(self, saidas: asyncio.Queue[Any]) -> None:
        """Cada ``controller.disconnected`` leva o repouso daquele controle, com tique ou sem."""
        while True:
            carga = await saidas.get()
            uniq = carga.get("uniq") if isinstance(carga, dict) else None
            self._repouso_de(uniq if isinstance(uniq, str) and uniq else None)

    def le_o_movimento(self) -> bool:
        """Alguma extensão assinou o tópico ``movimento``? Sem assinante, ninguém pede o leitor."""
        return any(con.filas_do_movimento for con in self._conexoes)

    def _assinar_o_movimento(self, con: _Conexao, feito: _Assinatura) -> asyncio.Queue[Any]:
        """A fila do ``movimento`` desta conexão, e a queda de um controle levando o repouso."""
        assert con.sessao is not None
        self._movimento_enviado = {
            uniq: (None, quando, jogador, via)
            for uniq, (_valores, quando, jogador, via) in self._movimento_enviado.items()
        } if self.le_o_movimento() else {}
        fila: asyncio.Queue[Any] = asyncio.Queue(maxsize=DEFAULT_QUEUE_MAXSIZE)
        con.filas_do_movimento.append(fila)
        feito.filas.append(fila)
        saidas = self.bus.subscribe(EventTopic.CONTROLLER_DISCONNECTED)
        con.no_barramento(feito, EventTopic.CONTROLLER_DISCONNECTED, saidas)
        con.tarefa(feito, self._repousar_o_movimento_de_quem_sai(saidas),
                   f"mods-{con.sessao.mod_id}-movimento-quedas")
        return fila

    def movimento_do_tique(self, leituras: dict[str | None, dict[str, Any]]) -> None:
        """O ``movimento`` deste tique: ``{uniq: {jogador, transporte, valores}}`` de todo controle.

        Cada controle sai quando um eixo passou da faixa morta (:func:`_o_movimento_mudou`), no
        máximo :data:`MOVIMENTO_POR_SEGUNDO` vezes por segundo; o que o teto segura sai num tique
        seguinte. O controle que sumiu sai uma vez em repouso. Nunca espera o socket.
        """
        filas = [f for con in self._conexoes for f in con.filas_do_movimento]
        if not filas:
            self._movimento_enviado = {}
            return
        agora = self._relogio()
        intervalo = 1.0 / MOVIMENTO_POR_SEGUNDO
        for uniq in dict.fromkeys([*self._movimento_enviado, *leituras]):
            leitura = leituras.get(uniq)
            antes = self._movimento_enviado.get(uniq)
            if leitura is None:
                self._repouso_do_movimento(uniq)
                continue
            valores: _Movimento = leitura["valores"]
            base = antes[0] if antes is not None else None
            if not _o_movimento_mudou(base, valores):
                continue
            if antes is not None and agora - antes[1] < intervalo:
                continue
            jogador, via = leitura.get("jogador"), leitura.get("transporte")
            self._movimento_enviado[uniq] = (valores, agora, jogador, via)
            carga = _carga_do_movimento(uniq, jogador, via, valores)
            for fila in filas:
                _por_na_fila(fila, carga)

    def _repouso_do_movimento(self, uniq: str | None) -> None:
        """Quem saiu sai uma vez em repouso: o aparelho que segue o movimento não fica preso."""
        antes = self._movimento_enviado.pop(uniq, None)
        if antes is None or antes[0] == REPOUSO_DO_MOVIMENTO:
            return
        carga = _carga_do_movimento(uniq, antes[2], antes[3], REPOUSO_DO_MOVIMENTO)
        for fila in (f for con in self._conexoes for f in con.filas_do_movimento):
            _por_na_fila(fila, carga)

    async def _repousar_o_movimento_de_quem_sai(self, saidas: asyncio.Queue[Any]) -> None:
        """Cada ``controller.disconnected`` leva o repouso do movimento daquele controle."""
        while True:
            carga = await saidas.get()
            uniq = carga.get("uniq") if isinstance(carga, dict) else None
            self._repouso_do_movimento(uniq if isinstance(uniq, str) and uniq else None)

    def _pulsar(self, sessao: _Credencial, params: dict[str, Any]) -> dict[str, Any]:
        """O pulso da barra: a porta valida e recusa, e o motor da luz decide e escreve."""
        if "pedir:luz.pulso" not in sessao.permissoes:
            raise RecusaError(CODE_SEM_PERMISSAO, "falta a permissão pedir:luz.pulso")
        uniq = _uniq_do_pedido(params, "luz.pulso")
        pedido = _pedido_do_pulso(params)
        if not pedido.get("parar") and self._o_jogo_escreve(uniq, "luz"):
            raise RecusaError(
                CODE_O_JOGO_ESCREVE, "o jogo está escrevendo a luz deste controle"
            )
        if self._pulsador is None:
            raise RecusaError(CODE_NAO_ESCREVEU, "não escreveu: o motor da luz não subiu")
        try:
            return self._pulsador(uniq, pedido)
        except Exception as exc:
            logger.warning("mods_porta_pulso_falhou", err=str(exc))
            raise RecusaError(CODE_NAO_ESCREVEU, f"não escreveu: {type(exc).__name__}") from exc

    async def _encaminhar(
        self,
        con: _Conexao,
        writer: asyncio.StreamWriter,
        publico: str,
        topico: str,
        fila: asyncio.Queue[Any],
    ) -> None:
        """Da fila do barramento ao socket. Bloquear aqui nunca bloqueia o tique."""
        while True:
            carga = await fila.get()
            if (
                topico in TOPICOS_DE_PUBLICACAO.values()
                and isinstance(carga, dict)
                and con.sessao is not None
                and carga.get("origem") == con.sessao.mod_id
            ):
                continue
            if (
                topico == EventTopic.ACESSORIOS_GESTO
                and isinstance(carga, dict)
                and con.sessao is not None
                and carga.get("mod") not in (None, con.sessao.mod_id)
            ):
                continue
            uniq = carga.get("uniq") if isinstance(carga, dict) else None
            if not isinstance(uniq, str) or not uniq:
                uniq = self._uniq_do_posto()
            nome = topico
            if publico == TOPICO_DOS_BOTOES:
                nome = EventTopic.BUTTON_DOWN if carga["pressed"] else EventTopic.BUTTON_UP
            evento = {
                "jsonrpc": PROTOCOL_VERSION,
                "method": "evento",
                "params": {
                    "topico": publico,
                    "nome": nome,
                    "uniq": uniq,
                    "dados": _jsonavel(carga),
                },
            }
            await self._enviar(con, writer, json.dumps(evento, ensure_ascii=False).encode())

    def _fonte(self) -> Any:
        return self._arbitro() if self._arbitro is not None else None

    async def _ler_a_memoria(self, fila: asyncio.Queue[Any], pedido: dict[str, Any]) -> None:
        """Pede ao leitor, pai do jogo, os valores declarados; sem leitor (sem jogo, ou com a
        chave desligada), espera e tenta de novo, sem nada publicar."""
        passo = 1.0 / max(float(e.get("hz", 30)) for e in pedido["entradas"])
        while True:
            try:
                reader, writer = await asyncio.open_unix_connection(str(caminho_do_soquete()))
            except OSError:
                await asyncio.sleep(ESPERA_DO_LEITOR_S)
                continue
            try:
                while True:
                    resposta = await _perguntar(reader, writer, {"verbo": "ler", **pedido})
                    valores = resposta.get("valores")
                    if isinstance(valores, dict) and len(valores) > 1:
                        _por_na_fila(fila, valores)
                    elif "recusa" in resposta:
                        await asyncio.sleep(ESPERA_DO_LEITOR_S)
                        continue
                    await asyncio.sleep(passo)
            except (OSError, ValueError, asyncio.IncompleteReadError, asyncio.TimeoutError):
                await asyncio.sleep(ESPERA_DO_LEITOR_S)
            finally:
                writer.close()

    async def _varrer(self, sessao: _Credencial, metodo: str,
                      params: dict[str, Any]) -> dict[str, Any]:
        """O caçador: ``memoria.varrer`` e ``memoria.refinar`` vão ao leitor, que guarda os
        candidatos; volta ``{token, contagem}``, e o ``endereco`` só quando sobra um."""
        if f"ler:{TOPICO_DA_MEMORIA}" not in sessao.permissoes:
            raise RecusaError(CODE_SEM_PERMISSAO, f"falta a permissão ler:{TOPICO_DA_MEMORIA}")
        pedido: dict[str, Any] = {
            k: params[k] for k in ("tipo", "valor", "token", "comparacao") if k in params}
        try:
            reader, writer = await asyncio.open_unix_connection(str(caminho_do_soquete()))
        except OSError as exc:
            raise RecusaError(CODE_NAO_ESCREVEU, "nenhum jogo aberto com a chave Memória") from exc
        try:
            resposta = await _perguntar(reader, writer, {"verbo": _DA_MEMORIA[metodo], **pedido})
        except (OSError, ValueError, asyncio.IncompleteReadError, asyncio.TimeoutError) as exc:
            raise RecusaError(CODE_NAO_ESCREVEU, "o leitor do jogo não respondeu") from exc
        finally:
            writer.close()
        if "recusa" in resposta:
            raise RecusaError(CODE_NAO_ESCREVEU, str(resposta["recusa"]))
        return resposta

    async def _escrever(
        self, sessao: _Credencial, metodo: str, params: dict[str, Any]
    ) -> Any:
        canal, metodo_do_servico, traduzir = _ESCRITAS[metodo]
        if f"escrever:{canal}" not in sessao.permissoes:
            raise RecusaError(CODE_SEM_PERMISSAO, f"falta a permissão escrever:{canal}")
        uniq = _uniq_do_pedido(params, metodo)
        pedido = traduzir(params, uniq)
        fonte = self._fonte()
        if fonte is None:
            if self._o_jogo_escreve(uniq, canal):
                raise RecusaError(
                    CODE_O_JOGO_ESCREVE,
                    f"o jogo está escrevendo {_NOME_DO_CANAL[canal]} deste controle",
                    {"vence": "jogo", "canal": canal},
                )
            resposta = await self._levar(metodo, metodo_do_servico, pedido)
            self._anotar_a_escrita(sessao.mod_id, canal, uniq)
            return resposta
        vagas = _vagas_do_pedido(canal, params)
        soltar_a_camada = self._soltar_a_camada_da_extensao(canal, uniq, params)
        if soltar_a_camada is not None:
            from hefesto_dualsense4unix.daemon.ipc_handlers import CAMADA_DA_EXTENSAO

            pedido = {**pedido, "camada": CAMADA_DA_EXTENSAO}
        veredito = fonte.pedir(
            _origem(sessao), canal, uniq, vagas, fonte.relogio(),
            ate_s=_prazo_do_pedido(params, metodo),
            reescrever=lambda: self._reescrever(metodo, metodo_do_servico, pedido),
            ao_vencer=None if soltar_a_camada is None else (
                lambda: self._reescrever(metodo, metodo_do_servico, soltar_a_camada)),
        )
        if not veredito.vale:
            raise _recusa_do_veredito(veredito, canal)
        if veredito.coberto:
            return {"status": "coberto", "vence": veredito.vence}
        if veredito.motivo == "solto" and any(f > 0 for f in veredito.fortes.values()):
            return {"status": "solto"}
        if veredito.motivo == "solto" and soltar_a_camada is not None:
            return await self._levar(metodo, metodo_do_servico, soltar_a_camada)
        if canal == "vibracao":
            pedido = {**pedido, "weak": round(veredito.fortes["direito"] * 255),
                      "strong": round(veredito.fortes["esquerdo"] * 255)}
        resposta = await self._levar(metodo, metodo_do_servico, pedido)
        self._anotar_a_escrita(sessao.mod_id, canal, uniq)
        return resposta

    async def _levar(self, metodo: str, metodo_do_servico: str, pedido: dict[str, Any]) -> Any:
        try:
            return await self._escritor(metodo_do_servico, pedido)
        except ValueError as exc:
            raise RecusaError(CODE_INVALID_PARAMS, str(exc)) from exc
        except Exception as exc:
            logger.warning("mods_porta_escrita_falhou", metodo=metodo, err=str(exc))
            raise RecusaError(CODE_NAO_ESCREVEU, f"não escreveu: {type(exc).__name__}") from exc

    @staticmethod
    def _soltar_a_camada_da_extensao(
        canal: str, uniq: str, params: dict[str, Any],
    ) -> dict[str, Any] | None:
        """O pedido que devolve ao controle o que a extensão tomou na luz ou num gatilho: o mesmo
        método do serviço, com ``soltar``, no controle e no lado do pedido. Os outros canais não
        têm camada própria."""
        from hefesto_dualsense4unix.daemon.ipc_handlers import CAMADA_DA_EXTENSAO

        if canal == "luz":
            return {"uniq": uniq, "camada": CAMADA_DA_EXTENSAO, "soltar": True}
        if canal == "gatilho":
            return {"uniq": uniq, "camada": CAMADA_DA_EXTENSAO, "soltar": True,
                    "side": _pedido_do_gatilho(params, uniq)["side"]}
        return None

    def _reescrever(self, metodo: str, metodo_do_servico: str, pedido: dict[str, Any]) -> None:
        """O pedido com prazo que voltou a ser o mais forte sai de novo, no laço do serviço."""
        try:
            laco = asyncio.get_running_loop()
        except RuntimeError:
            logger.warning("mods_porta_reescrita_sem_laco", metodo=metodo)
            return
        tarefa = laco.create_task(self._levar(metodo, metodo_do_servico, pedido))
        tarefa.add_done_callback(_sem_recusa_solta)

    async def _de_fora(self, sessao: _Credencial, metodo: str, params: dict[str, Any]) -> Any:
        """A háptica, o som e as luzes de jogador: só pelo tato vivo, que divide o teto."""
        from hefesto_dualsense4unix.daemon.subsystems.tato_vivo import padrao_de

        canal = _DE_FORA[metodo]
        if f"escrever:{canal}" not in sessao.permissoes:
            raise RecusaError(CODE_SEM_PERMISSAO, f"falta a permissão escrever:{canal}")
        fonte = self._fonte()
        if fonte is None:
            raise RecusaError(CODE_NAO_ESCREVEU, "o tato vivo não subiu")
        origem = _origem(sessao)
        try:
            if metodo == "haptica.registrar":
                fonte.registrar(origem, _ident(params, metodo), padrao_de(params))
                return {"status": "ok"}
            if metodo == "som.registrar":
                fonte.registrar_som(origem, _ident(params, metodo), padrao_de(params))
                return {"status": "ok"}
            uniq = _uniq_do_pedido(params, metodo)
            agora = fonte.relogio()
            if metodo == "haptica.tocar":
                veredito = self._tocar_a_haptica(fonte, origem, uniq, params, agora)
            elif metodo == "som.tocar":
                veredito = self._tocar_o_som(fonte, origem, uniq, params, agora)
            else:
                resposta_dos_leds = await self._acender_os_leds(fonte, origem, uniq, params, agora)
                if resposta_dos_leds.get("status") == "ok":
                    self._anotar_a_escrita(sessao.mod_id, canal, uniq)
                return resposta_dos_leds
        except ValueError as exc:
            raise RecusaError(CODE_INVALID_PARAMS, f"{metodo}: {exc}") from exc
        if not veredito.vale:
            raise _recusa_do_veredito(veredito, canal)
        if not veredito.coberto:
            self._anotar_a_escrita(sessao.mod_id, canal, uniq)
        resposta: dict[str, Any] = {"status": "coberto" if veredito.coberto else "ok"}
        if metodo == "haptica.tocar":
            toque = fonte.toques.get((uniq, params.get("lado")))
            resposta["pelo_motor"] = bool(toque is not None and toque.pelo_motor)
        return resposta

    @staticmethod
    def _tocar_a_haptica(
        fonte: Any, origem: str, uniq: str, params: dict[str, Any], agora: float,
    ) -> Any:
        lado = params.get("lado")
        if lado not in _LADOS:
            raise ValueError("pede o lado esquerdo ou direito")
        forca: Any = params.get("forca")
        bpm: Any = params.get("bpm")
        if not _numero(forca) or not 0 <= forca <= 1:
            raise ValueError("pede a força de 0 a 1")
        if bpm is not None and (not _numero(bpm) or not 20 <= bpm <= 240):
            raise ValueError("pede o bpm de 20 a 240")
        return fonte.tocar(origem, uniq, str(lado), _ident(params, "haptica.tocar"), float(forca),
                           None if bpm is None else float(bpm), agora,
                           _prazo_do_pedido(params, "haptica.tocar"))

    @staticmethod
    def _tocar_o_som(
        fonte: Any, origem: str, uniq: str, params: dict[str, Any], agora: float,
    ) -> Any:
        som, volume, t = params.get("som"), params.get("volume", 1.0), params.get("t")
        if not isinstance(som, str) or not som:
            raise ValueError("pede o som pelo id, ou recorte")
        if not _numero(volume) or not 0 <= volume <= 1:
            raise ValueError("pede o volume de 0 a 1")
        if t is not None and not _numero(t):
            raise ValueError("pede o t do jogo.som")
        dura_s: Any = params.get("dura_s")
        if dura_s is not None and (not _numero(dura_s) or not 0.05 <= dura_s <= 5):
            raise ValueError("pede o dura_s de 0,05 a 5")
        return fonte.som(origem, uniq, som, float(volume), agora,
                         None if t is None else float(t),
                         dura_s=None if dura_s is None else float(dura_s))

    async def _acender_os_leds(
        self, fonte: Any, origem: str, uniq: str, params: dict[str, Any], agora: float,
    ) -> Any:
        bits = _bits_da_mascara(params)
        anteriores = self._luzes_do_numero(uniq)
        veredito = fonte.pedir(
            origem, "leds", uniq, {"centro": sum(bits) / 5.0}, agora,
            ate_s=_prazo_do_pedido(params, "leds.set"),
            ao_vencer=lambda: self._reescrever(
                "leds.set", "led.player_set", {"uniq": uniq, "bits": anteriores}),
        )
        if not veredito.vale:
            raise _recusa_do_veredito(veredito, "leds")
        if veredito.coberto:
            return {"status": "coberto", "vence": veredito.vence}
        await self._levar("leds.set", "led.player_set", {"uniq": uniq, "bits": bits})
        return {"status": "ok"}

    def _luzes_do_numero(self, uniq: str) -> list[bool]:
        escritor = self._escritor
        lidas = escritor.luzes_do_numero(uniq) if isinstance(escritor, EscritorDoServico) else None
        if isinstance(lidas, (list, tuple)) and len(lidas) == 5:
            return [bool(b) for b in lidas]
        return [False] * 5

class EscritorDoServico:
    """As escritas vão pelos MESMOS handlers do IPC (``led.set``, ``rumble.set``,
    ``trigger.set``, ``led.player_set``), com ``uniq``: a política de cada canal (Modo Nativo,
    alvo fora da mesa, teto da vibração) tem um dono só, e a porta não a copia. O árbitro é a
    fonte de fora do tato vivo do mesmo serviço."""

    def __init__(self, daemon: Any) -> None:
        self._daemon = daemon

    async def __call__(self, metodo: str, pedido: dict[str, Any]) -> Any:
        servidor = getattr(self._daemon, "_ipc_server", None)
        tabela = getattr(servidor, "_handlers", None)
        handler = tabela.get(metodo) if isinstance(tabela, dict) else None
        if handler is None:
            raise RuntimeError("o serviço está sem o IPC principal")
        return await handler(pedido)

    def arbitro(self) -> Any:
        from hefesto_dualsense4unix.daemon.subsystems.tato_vivo import motor_do

        motor = motor_do(self._daemon)
        return None if motor is None else motor.de_fora

    def luzes_do_numero(self, uniq: str) -> Any:
        ler = getattr(getattr(self._daemon, "controller", None), "resolved_player_leds_for", None)
        return ler(uniq) if callable(ler) else None

    def perfil_que_nomeia(self, extensoes: frozenset[str]) -> str | None:
        """O perfil ativo, quando alguma seção dele está no modo de uma destas extensões."""
        from hefesto_dualsense4unix.daemon.subsystems.tato_vivo import modos_do_perfil_ativo

        nome, secoes = modos_do_perfil_ativo(self._daemon)
        donas = {extensao_do_modo(modo) for modo in secoes.values()}
        return nome if nome and donas & extensoes else None


_A_PORTA: dict[str, Porta | None] = {"viva": None}


def extensoes_vivas() -> frozenset[str]:
    """As extensões com a sessão aberta na porta do serviço; sem porta, nenhuma."""
    porta = _A_PORTA["viva"]
    return porta.vivas() if porta is not None else frozenset()


def escritor_do_servico(daemon: Any) -> Escritor:
    return EscritorDoServico(daemon)


def pulsar_no_servico(daemon: Any) -> Pulsador:
    """O pulso da barra vai ao motor do tato vivo, que o anda no relógio dele."""

    def pulsar(uniq: str, pedido: dict[str, Any]) -> dict[str, Any]:
        import time

        from hefesto_dualsense4unix.daemon.subsystems.tato_vivo import motor_do

        motor = motor_do(daemon)
        volta = None if motor is None else motor.volta
        if volta is None:
            raise RuntimeError("o motor da luz não subiu")
        resposta: dict[str, Any] = volta.pulsar(uniq, pedido, time.monotonic())
        return resposta

    return pulsar


def _chave(uniq: object) -> str | None:
    from hefesto_dualsense4unix.core.sysfs_leds import norm_mac

    return norm_mac(str(uniq)) if uniq else None


def o_jogo_escreve_no_servico(daemon: Any) -> OJogoEscreve:
    """O canal ``canal`` do controle ``uniq`` está com o jogo agora?

    A luz e o gatilho: o que o jogo pintou no vpad daquele controle e o
    backend retém como camada do jogo (``_game_output_by_uniq``,
    ``_game_triggers_by_uniq``). A vibração: o Modo Nativo (o jogo manda nos
    motores de todos) ou o vpad daquele controle com vibração do jogo há menos
    de :data:`JANELA_DA_VIBRACAO_DO_JOGO_S`.
    """

    def o_jogo_escreve(uniq: str, canal: str) -> bool:
        chave = _chave(uniq)
        controle = getattr(daemon, "controller", None)
        if canal == "vibracao":
            from hefesto_dualsense4unix.daemon.subsystems.rumble import (
                modo_nativo_manda_nos_motores,
            )

            if modo_nativo_manda_nos_motores(daemon):
                return True
            return any(
                _vibrou_ha_pouco(vpad)
                for dono, vpad in _vpads_por_controle(daemon, controle)
                if _chave(dono) == chave
            )
        pintado = getattr(controle, "_game_output_by_uniq", None)
        saida = pintado.get(chave) if isinstance(pintado, dict) else None
        if canal == "luz":
            return getattr(saida, "led", None) is not None
        gatilhos = getattr(controle, "_game_triggers_by_uniq", None)
        do_jogo = gatilhos.get(chave) if isinstance(gatilhos, dict) else None
        return bool(do_jogo) or any(
            getattr(saida, campo, None) is not None
            for campo in ("trigger_left", "trigger_right")
        )

    return o_jogo_escreve


def _vpads_por_controle(daemon: Any, controle: Any) -> list[tuple[str | None, Any]]:
    pares: list[tuple[str | None, Any]] = [
        (_primario(controle), getattr(daemon, "_gamepad_device", None))
    ]
    jogadores = getattr(getattr(daemon, "_coop_manager", None), "_players", None)
    if isinstance(jogadores, dict):
        for identidade, jogador in list(jogadores.items()):
            pares.append((identidade, getattr(jogador, "vpad", None)))
    return pares


def _vibrou_ha_pouco(vpad: Any) -> bool:
    ha = getattr(vpad, "rumble_no_fisico_ha_s", None)
    return isinstance(ha, (int, float)) and ha < JANELA_DA_VIBRACAO_DO_JOGO_S


def controles_no_servico(daemon: Any) -> Controles:
    """Os controles que o backend adotou e estão ligados, com o número que cada um acende e o
    nome do plástico, quando se sabe."""

    def controles() -> list[dict[str, Any]]:
        from hefesto_dualsense4unix.daemon.subsystems.vibracao_do_jogo import _jogador_de

        def um(uniq: str) -> dict[str, Any]:
            cor = cor_do_plastico_no_servico(daemon, uniq)
            return {"uniq": uniq, "jogador": _jogador_de(daemon, uniq),
                    **({"cor": cor} if cor else {})}

        descrever = getattr(getattr(daemon, "controller", None), "describe_controllers", None)
        if not callable(descrever):
            posto = _primario(getattr(daemon, "controller", None))
            return [um(posto)] if posto else []
        return [um(item["uniq"]) for item in descrever()
                if isinstance(item, dict) and isinstance(item.get("uniq"), str)
                and item["uniq"] and item.get("connected")]

    return controles


def cor_do_plastico_no_servico(daemon: Any, uniq: str) -> str:
    """O nome do plástico que a interface mostra: o que quem usa declarou e, sem ele, o de
    fábrica já lido; vazio quando não se sabe. Só leitura, sem perguntar ao aparelho."""
    declaracao = getattr(getattr(getattr(daemon, "_maquina", None), "controles", None),
                         "get", lambda _u: None)(uniq)
    declarado = getattr(declaracao, "cor", None)
    if isinstance(declarado, str) and declarado.strip():
        return declarado.strip()
    registro = getattr(daemon, "identity_registry", None)
    ler = getattr(registro, "identidade_de_fabrica", None)
    achado = ler(uniq) if callable(ler) else None
    nome = getattr(getattr(achado, "cor", None), "nome", None)
    return nome if isinstance(nome, str) else ""


def uniq_do_posto_no_servico(daemon: Any) -> UniqDoPosto:
    """O ``uniq`` do controle do posto: o dono do estado que o tique publica."""

    def uniq_do_posto() -> str | None:
        return _primario(getattr(daemon, "controller", None))

    return uniq_do_posto


def botoes_de_todo_controle_no_servico(
    daemon: Any, botoes_do_posto: frozenset[str], botoes_do_leitor: frozenset[str]
) -> None:
    """O tópico ``botoes`` do tique: a borda de cada controle, cabo ou rádio, do P1 ao P4.

    O dono do posto entra com ``botoes_do_posto`` (o mesmo estado do ``button.down`` do
    barramento); os outros, com o leitor que os atalhos do PS já leem
    (:func:`~hefesto_dualsense4unix.daemon.subsystems.poll.botoes_de_cada_controle`). Sem
    extensão que assine ``botoes``, não lê nada. Nunca levanta: o tique segue.
    """
    porta = getattr(getattr(daemon, "_mods_supervisor", None), "porta", None)
    if not isinstance(porta, Porta) or not porta.le_os_botoes():
        return
    try:
        from hefesto_dualsense4unix.daemon.subsystems.poll import botoes_de_cada_controle
        from hefesto_dualsense4unix.daemon.subsystems.vibracao_do_jogo import _jogador_de

        apertados = dict(botoes_de_cada_controle(daemon, botoes_do_leitor))
        apertados[_primario(getattr(daemon, "controller", None))] = botoes_do_posto
        porta.botoes_do_tique(apertados, lambda uniq: _jogador_de(daemon, uniq))
    except Exception as exc:
        logger.debug("mods_porta_botoes_do_tique_falhou", err=type(exc).__name__)


def topicos_de_todo_controle_no_servico(
    daemon: Any, estado_do_posto: Any, botoes_do_posto: frozenset[str],
    botoes_do_leitor: frozenset[str],
) -> None:
    """Os tópicos ``botoes`` e ``entradas`` do tique, nos dois ramos do laço (um dono só).

    O tique comum e o congelado (o Modo Nativo, a pausa, a carência) chamam daqui: a extensão
    que reage ao controle não emudece quando o jogo fala com ele. ``estado_do_posto`` é o
    ``ControllerState`` do tique, ``botoes_do_posto`` os botões dele e ``botoes_do_leitor`` o
    que os atalhos do PS leem.
    """
    botoes_de_todo_controle_no_servico(daemon, botoes_do_posto, botoes_do_leitor)
    entradas_de_todo_controle_no_servico(daemon, estado_do_posto)


def entradas_de_todo_controle_no_servico(daemon: Any, estado_do_posto: Any) -> None:
    """O tópico ``entradas`` do tique: os analógicos, os gatilhos e os dedos de cada controle.

    O dono do posto entra com ``estado_do_posto`` (o ``ControllerState`` do tique, ou ``None``
    sem leitura); os outros, com as fontes dos atalhos (``poll.entradas_de_cada_controle``). Os
    dedos são os que o ``SensorHub`` já lê (``toque_visto``, sem demanda nem grab); o leitor de
    toque vive pela tela ou pela extensão que pediu os dedos (``pedir_os_dedos``). Vale em todo
    modo, inclusive o Nativo. Sem extensão que assine ``entradas``, não lê nada. Nunca levanta.
    """
    porta = getattr(getattr(daemon, "_mods_supervisor", None), "porta", None)
    if not isinstance(porta, Porta) or not porta.le_as_entradas():
        return
    try:
        from hefesto_dualsense4unix.daemon.subsystems.poll import entradas_de_cada_controle
        from hefesto_dualsense4unix.daemon.subsystems.vibracao_do_jogo import _jogador_de

        eixos: dict[str | None, tuple[int, ...]] = {
            uniq: tuple(e[1:]) for uniq, e in entradas_de_cada_controle(daemon).items()
        }
        posto = _primario(getattr(daemon, "controller", None))
        if estado_do_posto is not None:
            eixos[posto] = tuple(_eixo(getattr(estado_do_posto, campo, None), padrao)
                                 for campo, padrao in _EIXOS_DO_POSTO)
        vias = _transportes_por_controle(daemon)
        if estado_do_posto is not None and posto not in vias:
            vias[posto] = getattr(estado_do_posto, "transport", None)
        hub = _o_hub(daemon)
        if hub is not None and porta.pede_os_dedos():
            for uniq in eixos:
                if uniq:
                    hub.pedir_os_dedos(uniq)
        porta.entradas_do_tique({
            uniq: {
                "jogador": _jogador_de(daemon, uniq),
                "transporte": vias.get(uniq),
                "valores": (*valores, _dedos(hub, uniq)),
            }
            for uniq, valores in eixos.items()
        })
    except Exception as exc:
        logger.debug("mods_porta_entradas_do_tique_falhou", err=type(exc).__name__)


_EIXOS_DO_POSTO = (("raw_lx", 128), ("raw_ly", 128), ("raw_rx", 128), ("raw_ry", 128),
                   ("l2_raw", 0), ("r2_raw", 0))


def _eixo(valor: Any, padrao: int) -> int:
    if not isinstance(valor, int) or isinstance(valor, bool):
        return padrao
    return min(255, max(0, valor))


def _transportes_por_controle(daemon: Any) -> dict[str | None, Any]:
    """``{uniq: 'usb' | 'bt'}`` dos controles na mesa, pelo backend (sem E/S)."""
    from hefesto_dualsense4unix.daemon.connection import (
        alvos_conectados_de,
        transportes_dos_alvos_de,
    )

    alvos = alvos_conectados_de(daemon) or {}
    vias = transportes_dos_alvos_de(daemon) or {}
    return {uniq: vias[chave] for chave, uniq in alvos.items() if uniq and chave in vias}


def _o_hub(daemon: Any) -> Any:
    """O ``SensorHub`` da sessão, se ele sabe ver o toque sem pedi-lo; ``None`` sem ele."""
    garantir = getattr(daemon, "_garantir_sensor_hub", None)
    if not callable(garantir):
        return None
    hub = garantir()
    return hub if callable(getattr(hub, "toque_visto", None)) else None


def _dedos(hub: Any, uniq: str | None) -> tuple[tuple[float, float], ...]:
    """Os dedos que o hub já lê no touchpad de ``uniq``, de 0 a 1 pela área; nenhum sem leitor."""
    if hub is None or not uniq:
        return ()
    try:
        toque = hub.toque_visto(uniq)
    except Exception as exc:
        logger.debug("mods_porta_sem_o_toque", err=type(exc).__name__)
        return ()
    if not isinstance(toque, dict):
        return ()
    largura = max(1, int(toque.get("width") or 1) - 1)
    altura = max(1, int(toque.get("height") or 1) - 1)
    pontos = toque.get("pontos")
    if not isinstance(pontos, list):
        pontos = [toque] if toque.get("touching") else []
    return tuple(
        (round(min(1.0, max(0.0, int(p["x"]) / largura)), 3),
         round(min(1.0, max(0.0, int(p["y"]) / altura)), 3))
        for p in pontos if isinstance(p, dict)
    )


def movimento_de_todo_controle_no_servico(daemon: Any, estado_do_posto: Any) -> None:
    """O tópico ``movimento`` do tique: o giroscópio e o acelerômetro de cada controle.

    Os controles são os da mesa (``alvos_conectados``, sem E/S) e o dono do posto. Só com
    extensão inscrita em ``movimento`` o serviço pede o leitor de movimento de cada um
    (``pedir_o_movimento``, sem o touchpad e sem grab) e lê o que ele já vê
    (``movimento_visto``). Os dois ramos do laço chamam daqui: vale em todo modo, inclusive o
    Nativo e a pausa. ``estado_do_posto`` dá o transporte do posto quando o backend não o diz.
    Nunca levanta: o tique segue.
    """
    porta = getattr(getattr(daemon, "_mods_supervisor", None), "porta", None)
    if not isinstance(porta, Porta) or not porta.le_o_movimento():
        return
    try:
        from hefesto_dualsense4unix.daemon.subsystems.poll import _na_mesa
        from hefesto_dualsense4unix.daemon.subsystems.vibracao_do_jogo import _jogador_de

        controle = getattr(daemon, "controller", None)
        posto = _primario(controle)
        hub = _o_hub_do_movimento(daemon)
        vias = _transportes_por_controle(daemon)
        if estado_do_posto is not None and posto and posto not in vias:
            vias[posto] = getattr(estado_do_posto, "transport", None)
        leituras: dict[str | None, dict[str, Any]] = {}
        for uniq in dict.fromkeys([posto, *_na_mesa(controle)]):
            if not uniq or hub is None:
                continue
            hub.pedir_o_movimento(uniq)
            visto = hub.movimento_visto(uniq)
            if visto is not None:
                leituras[uniq] = {"jogador": _jogador_de(daemon, uniq),
                                  "transporte": vias.get(uniq), "valores": visto}
        porta.movimento_do_tique(leituras)
    except Exception as exc:
        logger.debug("mods_porta_movimento_do_tique_falhou", err=type(exc).__name__)


def _o_hub_do_movimento(daemon: Any) -> Any:
    """O ``SensorHub`` da sessão, se ele sabe pedir e ver o movimento; ``None`` sem ele."""
    garantir = getattr(daemon, "_garantir_sensor_hub", None)
    if not callable(garantir):
        return None
    hub = garantir()
    sabe = callable(getattr(hub, "pedir_o_movimento", None)) and callable(
        getattr(hub, "movimento_visto", None))
    return hub if sabe else None


def _primario(controle: Any) -> str | None:
    """O ``primary_uniq`` do backend (uma propriedade; num dublê, pode ser método)."""
    valor = getattr(controle, "primary_uniq", None)
    if callable(valor):
        valor = valor()
    return valor if isinstance(valor, str) and valor else None


def _tamanho_da_mensagem(dados: Any) -> int:
    """O tamanho de ``dados`` na linha mais larga que ele atravessa: o ``json.dumps`` padrão, com os
    espaços dos separadores e o escape de todo caractere fora do ASCII: o teto da linha da
    interface até o serviço, na ida e na volta."""
    try:
        return len(json.dumps(dados))
    except (TypeError, ValueError):
        return TETO_DA_MENSAGEM + 1


__all__ = [
    "APARELHOS_POR_SEGUNDO",
    "CODE_NAO_ESCREVEU",
    "CODE_O_JOGO_ESCREVE",
    "CODE_QUEM_E_VOCE",
    "CODE_SEM_PERMISSAO",
    "ENTRADAS_POR_SEGUNDO",
    "EVENTO_DA_ACAO",
    "EVENTO_DA_MENSAGEM",
    "EVENTO_DA_OPCAO",
    "EVENTO_DO_LIVRE",
    "EVENTO_DO_PARAR",
    "JANELA_DA_VIBRACAO_DO_JOGO_S",
    "LINHAS_DO_AGORA",
    "LIVRE_POR_SEGUNDO",
    "MENSAGENS_POR_SEGUNDO",
    "MOVIMENTO_POR_SEGUNDO",
    "PRAZO_DA_RESPOSTA_S",
    "PREFIXO_DO_APELIDO",
    "PUBLICACOES_POR_SEGUNDO",
    "TETO_DA_MENSAGEM",
    "TOPICO_DO_ESTILO",
    "Apelidos",
    "Controles",
    "Porta",
    "RecusaError",
    "abrir_pelo_lancador",
    "botoes_de_todo_controle_no_servico",
    "caminho_da_sessao",
    "carga_do_estilo",
    "chave_dos_apelidos",
    "comando_fora_da_caixa",
    "controles_no_servico",
    "cor_do_plastico_no_servico",
    "credencial_do_par",
    "descende_de",
    "entradas_de_todo_controle_no_servico",
    "entregar_com_o_fd",
    "escritor_do_servico",
    "estado_dos_acessorios",
    "estado_vazio_dos_acessorios",
    "movimento_de_todo_controle_no_servico",
    "o_jogo_escreve_no_servico",
    "pastas_que_a_caixa_escreve",
    "pulsar_no_servico",
    "termos_do_abrir",
    "topicos_de_todo_controle_no_servico",
    "uniq_do_posto_no_servico",
]
