"""A porta das modificações: ``$XDG_RUNTIME_DIR/hefesto-dualsense4unix/mods.sock``.

Nunca o socket principal. O enquadramento é o mesmo do IPC (um objeto
JSON-RPC 2.0 por linha), e a tabela de métodos é pequena e fechada:

* ``mod.ola`` — a primeira palavra, com a ficha que o supervisor passou ao
  filho (``HEFESTO_MOD_FICHA``). O ``SO_PEERCRED`` da conexão tem de ser o PID
  que o supervisor criou ou um descendente dele, do mesmo usuário;
* ``eventos.assinar`` — cada tópico pede ``ler:<tópico>``;
* ``luz.set``, ``vibracao.set``, ``gatilho.set`` — cada um pede
  ``escrever:<canal>``, sempre com o ``uniq`` do controle (escrever em todos é
  proibido, a mesma regra do BROADCAST-PROIBIDO-01) e nunca num canal que o
  jogo está escrevendo naquele controle («o jogo manda, o controle obedece»).

Cada assinatura é uma fila do barramento (``core/events.py``), que descarta o
evento mais antigo quando enche: a modificação que não lê perde eventos velhos,
e o tique do serviço nunca espera por ela. O contrato está em
``docs/protocol/porta-das-modificacoes.md``.
"""
from __future__ import annotations

import asyncio
import contextlib
import dataclasses
import json
import os
import socket
import struct
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from hefesto_dualsense4unix.core.events import EventBus
from hefesto_dualsense4unix.daemon.protocolo_do_ipc import (
    CODE_INVALID_PARAMS,
    CODE_INVALID_REQUEST,
    CODE_METHOD_NOT_FOUND,
    CODE_PARSE_ERROR,
    MAX_PAYLOAD_BYTES,
    PROTOCOL_VERSION,
)
from hefesto_dualsense4unix.mods import API_DAS_MODIFICACOES
from hefesto_dualsense4unix.mods.manifesto import TOPICOS_DE_LEITURA
from hefesto_dualsense4unix.utils.logging_config import get_logger

logger = get_logger(__name__)

#: Erros próprios da porta, ao lado dos do IPC (``protocolo_do_ipc``).
CODE_SEM_PERMISSAO = -32010
CODE_O_JOGO_ESCREVE = -32011
CODE_QUEM_E_VOCE = -32012
CODE_NAO_ESCREVEU = -32013

#: Quanto tempo a vibração que o jogo mandou ao vpad de um controle segura o
#: canal: dentro dele, a modificação não escreve vibração naquele controle.
JANELA_DA_VIBRACAO_DO_JOGO_S = 2.0

Escritor = Callable[[str, dict[str, Any]], Awaitable[Any]]
OJogoEscreve = Callable[[str, str], bool]
UniqDoPosto = Callable[[], str | None]


class RecusaError(Exception):
    """Um pedido recusado, com o código e a frase da resposta."""

    def __init__(self, codigo: int, frase: str) -> None:
        super().__init__(frase)
        self.codigo = codigo
        self.frase = frase


@dataclass
class _Credencial:
    """Quem o supervisor deixou entrar: a modificação, o PID que ele criou e as permissões."""

    mod_id: str
    pid: int
    permissoes: frozenset[str]


@dataclass(eq=False)
class _Conexao:
    sessao: _Credencial | None = None
    assinaturas: list[tuple[str, asyncio.Queue[Any]]] = field(default_factory=list)
    tarefas: list[asyncio.Task[None]] = field(default_factory=list)
    trava: asyncio.Lock = field(default_factory=asyncio.Lock)


def credencial_do_par(sock: socket.socket | None) -> tuple[int, int, int] | None:
    """``(pid, uid, gid)`` do outro lado do socket Unix, pelo ``SO_PEERCRED``."""
    if sock is None:
        return None
    try:
        cru = sock.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, struct.calcsize("3i"))
    except OSError:
        return None
    pid, uid, gid = struct.unpack("3i", cru)
    return pid, uid, gid


def _pai_de(pid: int) -> int | None:
    try:
        stat = Path(f"/proc/{pid}/stat").read_text(encoding="ascii", errors="replace")
    except OSError:
        return None
    # O nome do processo vem entre parênteses e pode ter espaço: o campo do pai
    # é o segundo depois do ÚLTIMO «)».
    resto = stat.rsplit(")", 1)[-1].split()
    try:
        return int(resto[1])
    except (IndexError, ValueError):
        return None


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


def _resposta(req_id: Any, resultado: Any) -> bytes:
    return json.dumps(
        {"jsonrpc": PROTOCOL_VERSION, "id": req_id, "result": resultado}, ensure_ascii=False
    ).encode("utf-8")


def _erro(req_id: Any, codigo: int, frase: str) -> bytes:
    return json.dumps(
        {
            "jsonrpc": PROTOCOL_VERSION,
            "id": req_id,
            "error": {"code": codigo, "message": frase},
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


#: método da porta → (canal, método do serviço que aplica, tradutor do pedido)
_ESCRITAS: dict[str, tuple[str, str, Callable[[dict[str, Any], str], dict[str, Any]]]] = {
    "luz.set": ("luz", "led.set", _pedido_da_luz),
    "vibracao.set": ("vibracao", "rumble.set", _pedido_da_vibracao),
    "gatilho.set": ("gatilho", "trigger.set", _pedido_do_gatilho),
}

_NOME_DO_CANAL = {"luz": "a luz", "vibracao": "a vibração", "gatilho": "o gatilho"}


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
    ) -> None:
        self.caminho = caminho
        self.bus = bus
        self._escritor = escritor
        self._o_jogo_escreve = o_jogo_escreve
        self._uniq_do_posto = uniq_do_posto
        self._fichas: dict[str, _Credencial] = {}
        self._server: asyncio.AbstractServer | None = None
        self._inode: int | None = None
        self._conexoes: set[_Conexao] = set()

    # -- quem pode entrar -------------------------------------------------

    def registrar(self, ficha: str, mod_id: str, pid: int, permissoes: list[str]) -> None:
        """O supervisor diz: esta ficha é da modificação ``mod_id``, no PID ``pid``."""
        self._fichas[ficha] = _Credencial(mod_id, pid, frozenset(permissoes))

    def esquecer(self, ficha: str) -> None:
        self._fichas.pop(ficha, None)

    def assinaturas_de(self, mod_id: str) -> list[asyncio.Queue[Any]]:
        """As filas do barramento abertas por ``mod_id`` (para a régua e o diagnóstico)."""
        return [
            fila
            for con in self._conexoes
            if con.sessao is not None and con.sessao.mod_id == mod_id
            for _topico, fila in con.assinaturas
        ]

    # -- ciclo de vida ----------------------------------------------------

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
        logger.info("mods_porta_aberta", caminho=str(self.caminho))

    async def parar(self) -> None:
        server, self._server = self._server, None
        if server is not None:
            server.close()
        for con in list(self._conexoes):
            for tarefa in con.tarefas:
                tarefa.cancel()
        if server is not None:
            with contextlib.suppress(Exception):
                await asyncio.wait_for(server.wait_closed(), timeout=2.0)
        if self._inode is not None:
            with contextlib.suppress(FileNotFoundError):
                if self.caminho.stat().st_ino == self._inode:
                    self.caminho.unlink()
            self._inode = None

    # -- uma conexão ------------------------------------------------------

    async def _atender(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        con = _Conexao()
        self._conexoes.add(con)
        par = credencial_do_par(writer.get_extra_info("socket"))
        try:
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
        except (ConnectionError, asyncio.IncompleteReadError):
            pass
        except Exception as exc:
            logger.warning("mods_porta_erro", err=str(exc), exc_info=True)
        finally:
            for tarefa in con.tarefas:
                tarefa.cancel()
            for topico, fila in con.assinaturas:
                self.bus.unsubscribe(topico, fila)
            self._conexoes.discard(con)
            with contextlib.suppress(Exception):
                writer.close()
                await writer.wait_closed()

    async def _enviar(self, con: _Conexao, writer: asyncio.StreamWriter, linha: bytes) -> None:
        async with con.trava:
            writer.write(linha + b"\n")
            await writer.drain()

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
        try:
            if con.sessao is None:
                if metodo != "mod.ola":
                    raise RecusaError(CODE_QUEM_E_VOCE, "a primeira palavra é mod.ola")
                con.sessao = self._apresentar(params, par)
                return _resposta(req_id, {
                    "id": con.sessao.mod_id,
                    "api": API_DAS_MODIFICACOES,
                    "permissoes": sorted(con.sessao.permissoes),
                })
            if metodo == "eventos.assinar":
                return _resposta(req_id, self._assinar(con, writer, params))
            if metodo in _ESCRITAS:
                return _resposta(req_id, await self._escrever(con.sessao, metodo, params))
            raise RecusaError(CODE_METHOD_NOT_FOUND, f"método desconhecido: {metodo}")
        except RecusaError as recusa:
            return _erro(req_id, recusa.codigo, recusa.frase)

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
        for publico in topicos:
            for topico in TOPICOS_DE_LEITURA[publico]:
                fila = self.bus.subscribe(topico)
                con.assinaturas.append((topico, fila))
                con.tarefas.append(asyncio.create_task(
                    self._encaminhar(con, writer, publico, topico, fila),
                    name=f"mods-{con.sessao.mod_id}-{topico}",
                ))
        return {"assinados": list(topicos)}

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
            uniq = carga.get("uniq") if isinstance(carga, dict) else None
            if not isinstance(uniq, str) or not uniq:
                uniq = self._uniq_do_posto()
            evento = {
                "jsonrpc": PROTOCOL_VERSION,
                "method": "evento",
                "params": {
                    "topico": publico,
                    "nome": topico,
                    "uniq": uniq,
                    "dados": _jsonavel(carga),
                },
            }
            await self._enviar(con, writer, json.dumps(evento, ensure_ascii=False).encode())

    async def _escrever(
        self, sessao: _Credencial, metodo: str, params: dict[str, Any]
    ) -> Any:
        canal, metodo_do_servico, traduzir = _ESCRITAS[metodo]
        if f"escrever:{canal}" not in sessao.permissoes:
            raise RecusaError(CODE_SEM_PERMISSAO, f"falta a permissão escrever:{canal}")
        uniq = _uniq_do_pedido(params, metodo)
        pedido = traduzir(params, uniq)
        if self._o_jogo_escreve(uniq, canal):
            raise RecusaError(
                CODE_O_JOGO_ESCREVE,
                f"o jogo está escrevendo {_NOME_DO_CANAL[canal]} deste controle",
            )
        try:
            return await self._escritor(metodo_do_servico, pedido)
        except ValueError as exc:
            raise RecusaError(CODE_INVALID_PARAMS, str(exc)) from exc
        except Exception as exc:
            logger.warning("mods_porta_escrita_falhou", metodo=metodo, err=str(exc))
            raise RecusaError(CODE_NAO_ESCREVEU, f"não escreveu: {type(exc).__name__}") from exc


# -- as ligações com o serviço vivo ----------------------------------------


def escritor_do_servico(daemon: Any) -> Escritor:
    """As escritas vão pelos MESMOS handlers do IPC (``led.set``, ``rumble.set``,
    ``trigger.set``), com ``uniq``: a política de cada canal (Modo Nativo, alvo
    fora da mesa, teto da vibração) tem um dono só, e a porta não a copia."""

    async def escrever(metodo: str, pedido: dict[str, Any]) -> Any:
        servidor = getattr(daemon, "_ipc_server", None)
        tabela = getattr(servidor, "_handlers", None)
        handler = tabela.get(metodo) if isinstance(tabela, dict) else None
        if handler is None:
            raise RuntimeError("o serviço está sem o IPC principal")
        return await handler(pedido)

    return escrever


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


def uniq_do_posto_no_servico(daemon: Any) -> UniqDoPosto:
    """O ``uniq`` do controle do posto: o dono do estado que o tique publica."""

    def uniq_do_posto() -> str | None:
        return _primario(getattr(daemon, "controller", None))

    return uniq_do_posto


def _primario(controle: Any) -> str | None:
    """O ``primary_uniq`` do backend (uma propriedade; num dublê, pode ser método)."""
    try:
        valor = getattr(controle, "primary_uniq", None)
        if callable(valor):
            valor = valor()
    except Exception:
        return None
    return valor if isinstance(valor, str) and valor else None


__all__ = [
    "CODE_NAO_ESCREVEU",
    "CODE_O_JOGO_ESCREVE",
    "CODE_QUEM_E_VOCE",
    "CODE_SEM_PERMISSAO",
    "JANELA_DA_VIBRACAO_DO_JOGO_S",
    "Porta",
    "RecusaError",
    "credencial_do_par",
    "descende_de",
    "escritor_do_servico",
    "o_jogo_escreve_no_servico",
    "uniq_do_posto_no_servico",
]
