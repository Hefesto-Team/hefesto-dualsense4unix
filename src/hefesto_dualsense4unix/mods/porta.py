"""A porta das modificações: ``$XDG_RUNTIME_DIR/hefesto-dualsense4unix/mods.sock``.

Nunca o socket principal: o enquadramento é o do IPC (um JSON-RPC 2.0 por linha), e a
tabela de métodos é pequena e fechada. ``mod.ola`` confere a ficha e o ``SO_PEERCRED``;
cada leitura pede ``ler:<tópico>``, cada publicação ``publicar:<tópico>``, cada escrita
``escrever:<canal>`` com o ``uniq`` de um controle e nunca num canal que o jogo escreve;
``lancador.jogos`` pede ``lancador``. Cada assinatura é uma fila do barramento que
descarta o mais antigo quando enche. O contrato inteiro, com a vibração que se solta na
queda, está em ``docs/protocol/porta-das-modificacoes.md``.
"""
from __future__ import annotations

import asyncio
import contextlib
import dataclasses
import json
import math
import os
import socket
import struct
import time
from collections import deque
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from hefesto_dualsense4unix.core.events import DEFAULT_QUEUE_MAXSIZE, EventBus, EventTopic
from hefesto_dualsense4unix.daemon.protocolo_do_ipc import (
    CODE_INVALID_PARAMS,
    CODE_INVALID_REQUEST,
    CODE_METHOD_NOT_FOUND,
    CODE_PARSE_ERROR,
    MAX_PAYLOAD_BYTES,
    PROTOCOL_VERSION,
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

#: Quantos ``eventos.publicar`` aceitos por segundo de cada extensão; a 21ª é recusada.
PUBLICACOES_POR_SEGUNDO = 20

#: Ao parar, quanto a porta espera as conexões abertas fecharem.
PRAZO_PARA_FECHAR_S = 2.0

#: Quantos jogos um ``lancador.jogos`` entrega, no máximo.
JOGOS_POR_LANCADOR = 5000

#: O ``estado`` de uma conexão e de um aparelho em ``acessorios.estado``: a cor da janela.
ESTADOS_DO_ACESSORIO = ("ligado", "procurando", "desligado", "falhou")
#: Por onde uma conexão fala: o ícone da janela e da aba Conexões.
TRANSPORTES_DA_CONEXAO = ("usb", "bluetooth", "rede", "local")
#: Quantas conexões e quantos aparelhos um ``acessorios.estado`` leva, no máximo.
ITENS_DO_ESTADO = 32
#: O evento que o «Parar tudo» da janela entrega à extensão que não lê o gesto ``para``.
EVENTO_DO_PARAR = "extensao.parar"
#: O clique num botão de ação da janela e o arrastar do ``livre``, só para a extensão dona.
EVENTO_DA_ACAO = "extensao.acao"
EVENTO_DO_LIVRE = "extensao.livre"
#: O arrastar do ``livre`` sai no compasso de ``1 / LIVRE_POR_SEGUNDO`` s, com o valor mais novo ao
#: fim de cada compasso; o soltar sai na hora, fora do compasso, e leva o valor final.
LIVRE_POR_SEGUNDO = 20
#: O tópico ``botoes``: o serviço entrega o aperto de TODO controle, cada um com o dele.
TOPICO_DOS_BOTOES = "botoes"
#: O tópico ``entradas``: os analógicos, os gatilhos e o touchpad de TODO controle.
TOPICO_DAS_ENTRADAS = "entradas"
#: Quantas ``entradas`` de um controle saem por segundo, no máximo.
ENTRADAS_POR_SEGUNDO = 30
#: Quanto um analógico ou um gatilho (de 0 a 255) anda antes de sair; as pontas saem sempre.
FAIXA_MORTA_DO_EIXO = 2
#: Quanto um dedo (de 0 a 1) anda antes de sair; o dedo que chega ou levanta sai sempre.
FAIXA_MORTA_DO_DEDO = 0.01

Escritor = Callable[[str, dict[str, Any]], Awaitable[Any]]
OJogoEscreve = Callable[[str, str], bool]
UniqDoPosto = Callable[[], str | None]
#: ``controles()``: os controles ligados agora, cada um ``{uniq, jogador}``.
Controles = Callable[[], list[dict[str, Any]]]
#: ``pulsador(uniq, pedido)``: o motor da luz começa, retoca ou solta o pulso da barra do controle.
Pulsador = Callable[[str, dict[str, Any]], dict[str, Any]]


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
    #: Os ``lancador.comandos`` do manifesto: o primeiro termo de todo ``abrir``.
    comandos: frozenset[str] = frozenset()


@dataclass(eq=False)
class _Conexao:
    sessao: _Credencial | None = None
    #: A modificação desta conexão devolveu o estado dos acessórios: ao cair, o estado se apaga.
    deu_o_estado: bool = False
    #: O último valor de cada função que esta conexão publicou em ``jogo.acessorio``. Uma
    #: publicação pode trazer só parte delas, e a que ela não traz segue com o valor de antes.
    funcoes_do_acessorio: dict[str, float] = field(default_factory=dict)
    #: Os controles em que o último ``vibracao.set`` desta conexão deixou motor ligado.
    vibrando: set[str] = field(default_factory=set)
    assinaturas: list[tuple[str, asyncio.Queue[Any]]] = field(default_factory=list)
    tarefas: list[asyncio.Task[None]] = field(default_factory=list)
    trava: asyncio.Lock = field(default_factory=asyncio.Lock)
    #: As filas do tópico ``botoes`` (``button.down``, ``button.up``): o serviço as enche com o
    #: aperto de cada controle (:meth:`Porta.botoes_do_tique`), não pelo barramento.
    filas_dos_botoes: list[tuple[str, asyncio.Queue[Any]]] = field(default_factory=list)
    #: As filas do tópico ``entradas``, cheias pelo serviço (:meth:`Porta.entradas_do_tique`).
    filas_das_entradas: list[asyncio.Queue[Any]] = field(default_factory=list)
    #: O ``eventos.assinar`` das ``entradas`` pediu os dedos (``dedos: true``): o serviço mantém
    #: o leitor de toque de cada controle vivo enquanto esta conexão durar.
    quer_os_dedos: bool = False
    #: O socket desta conexão: o «Parar tudo» fala por ele sem assinatura nenhuma.
    escritor: asyncio.StreamWriter | None = None

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


def _pai_de(pid: int) -> int | None:
    """O pai de ``pid`` pelo ``/proc``; ``None`` quando o processo já não existe.

    Um processo que some entre a pergunta e a leitura levanta, e a conexão
    dele fecha: na dúvida, a porta não abre.
    """
    stat = Path(f"/proc/{pid}/stat")
    if not stat.is_file():
        return None
    # O nome do processo vem entre parênteses e pode ter espaço: o campo do pai
    # é o segundo depois do ÚLTIMO «)».
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


def _numero(valor: Any) -> bool:
    return isinstance(valor, (int, float)) and not isinstance(valor, bool) and math.isfinite(valor)


def _funcoes_do_acessorio(dados: Any) -> dict[str, float]:
    """O campo de funções do ``jogo.acessorio`` validado: nome curto, minúsculo, valor de 0 a 1."""
    corpo = dados if isinstance(dados, dict) else {}
    pedidas = corpo.get("funcoes")  # noqa-acento: chave do contrato
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


#: método da porta → (canal, método do serviço que aplica, tradutor do pedido)
_ESCRITAS: dict[str, tuple[str, str, Callable[[dict[str, Any], str], dict[str, Any]]]] = {
    "luz.set": ("luz", "led.set", _pedido_da_luz),
    "vibracao.set": ("vibracao", "rumble.set", _pedido_da_vibracao),
    "gatilho.set": ("gatilho", "trigger.set", _pedido_do_gatilho),
}

_NOME_DO_CANAL = {"luz": "a luz", "vibracao": "a vibração", "gatilho": "o gatilho"}


def estado_vazio_dos_acessorios(mod_id: str) -> dict[str, Any]:
    """O estado de quem não tem acessório nem conexão: os gestos do PS voltam a ser os de sempre."""
    return {
        "mod": mod_id, "ligado": False, "nivel": 0, "perfil": None, "aparelhos": [],
        "conexoes": [], "ajustes": {},  # (noqa-acento): a chave do estado
    }


def _recusa_do_estado(frase: str) -> RecusaError:
    return RecusaError(CODE_INVALID_PARAMS, f"acessorios.estado: {frase}")


def _curto(valor: Any, onde: str, maximo: int) -> str:
    if not isinstance(valor, str) or len(valor) > maximo or not valor.strip():
        raise _recusa_do_estado(f"{onde} é um texto de até {maximo} letras.")
    return valor.strip()


def _estado_do_item(bruto: dict[str, Any], onde: str) -> str:
    estado = bruto.get("estado", "ligado")
    if estado not in ESTADOS_DO_ACESSORIO:
        raise _recusa_do_estado(f"o estado de {onde} é um de {', '.join(ESTADOS_DO_ACESSORIO)}.")
    return str(estado)


def _aparelho(bruto: Any) -> dict[str, Any]:
    """``{nome, tipo, estado, bateria, forca}``; o texto solto (o formato antigo) é só o nome.

    ``id`` (até 40 letras, o que a ação do aparelho leva como ``alvo``) e ``ligado`` (a chave do
    cartão) só saem quando a extensão os manda.
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
    saida = {
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
    return saida


def _conexao_do_estado(bruto: Any) -> dict[str, Any]:
    """``{id, tipo, transporte, estado, motivo}``: uma ponte da extensão (um adaptador, a rede)."""
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
        "estado": _estado_do_item(bruto, "uma conexão"),
        "motivo": None if motivo in (None, "") else _curto(motivo, "o motivo da conexão", 120),
    }


def estado_dos_acessorios(mod_id: str, params: dict[str, Any]) -> dict[str, Any]:
    """O ``acessorios.estado`` validado, com o ``mod`` de quem o mandou.

    Cada aparelho sai ``{nome, tipo, estado, bateria, forca}`` (o texto solto vira o nome) e cada
    conexão ``{id, tipo, transporte, estado, motivo}``, até ``ITENS_DO_ESTADO`` de cada. ``ajustes``
    leva só o que a modificação declara e o Hefesto entende (limiar do fundo do L2, acelerador,
    camada, lado único, gestos no Modo Nativo, toque de confirmação, pulso da barra e «Sem pisca»);
    o resto cai.
    """
    ligado = params.get("ligado", False)
    nivel = params.get("nivel", 0)
    perfil = params.get("perfil")
    aparelhos = params.get("aparelhos", [])
    conexoes = params.get("conexoes", [])  # (noqa-acento): a chave do estado
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
        "aparelhos": [_aparelho(a) for a in aparelhos[:ITENS_DO_ESTADO]],
        "conexoes": as_conexoes,  # (noqa-acento): a chave do estado
        "ajustes": {k: v for k, v in opcoes.items() if k in OPCOES_DOS_GESTOS},
    }


#: As opções da modificação que o Hefesto lê (as que mexem nos gestos do PS e na confirmação).
OPCOES_DOS_GESTOS = frozenset({
    "limiar_fundo", "acelerador", "camada", "camada_s", "lado_unico", "gestos_no_nativo",
    "toque_de_confirmacao", "pulso_da_barra", "sem_pisca",
})


#: As ``entradas`` de um controle: ``lx, ly, rx, ry, l2, r2`` (0 a 255) e os dedos ``(x, y)``.
_Valores = tuple[int, int, int, int, int, int, tuple[tuple[float, float], ...]]
#: O controle parado: os analógicos no centro, os gatilhos soltos e nenhum dedo.
REPOUSO_DAS_ENTRADAS: _Valores = (128, 128, 128, 128, 0, 0, ())
#: As pontas de cada eixo (os analógicos e os gatilhos): chegar a uma delas sai sempre.
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


@dataclass
class _Compasso:
    """O compasso do arrastar de um ``livre``: o valor que espera e o relógio que o solta."""

    pendente: dict[str, Any] | None = None
    relogio: asyncio.TimerHandle | None = None

    def cancelar(self) -> None:
        if self.relogio is not None:
            self.relogio.cancel()
        self.pendente = self.relogio = None


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
        relogio: Callable[[], float] = time.monotonic,
    ) -> None:
        self.caminho = caminho
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
        #: Os instantes dos últimos ``eventos.publicar`` aceitos de cada extensão (a janela de 1 s).
        self._publicacoes: dict[str, deque[float]] = {}
        #: O último ``acessorios.estado`` de cada extensão: a coluna «Agora» da janela dela.
        self._estados_dos_acessorios: dict[str, dict[str, Any]] = {}
        #: O último ``lancador.jogos`` de cada extensão de lançador.
        self._jogos_dos_lancadores: dict[str, list[dict[str, Any]]] = {}
        #: Os botões de cada controle no último tique entregue ao tópico ``botoes``; ``None``
        #: enquanto ninguém o lê (o primeiro tique com leitor só guarda, sem borda inventada).
        self._botoes_antes: dict[str | None, frozenset[str]] | None = None
        #: O que saiu por último no tópico ``entradas``, por controle: ``(valores, instante,
        #: jogador, transporte)``. Quem nunca saiu do repouso não está aqui.
        self._entradas_enviadas: dict[str | None, tuple[_Valores | None, float, Any, Any]] = {}
        #: Quantos ``acessorios.estado`` cada extensão já devolveu: a janela vê a resposta à ação.
        self._series: dict[str, int] = {}
        #: O arrastar do ``livre`` de cada ``(mod, opção)``: o valor que espera o fim do compasso.
        self._livres: dict[tuple[str, str], _Compasso] = {}

    # -- quem pode entrar -------------------------------------------------

    def registrar(self, ficha: str, mod_id: str, pid: int, permissoes: list[str],
                  *, comandos: tuple[str, ...] = ()) -> None:
        """O supervisor diz: esta ficha é da modificação ``mod_id``, no PID ``pid``."""
        self._fichas[ficha] = _Credencial(
            mod_id, pid, frozenset(permissoes), frozenset(comandos))

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
                await asyncio.wait_for(server.wait_closed(), timeout=PRAZO_PARA_FECHAR_S)
        if self._inode is not None:
            with contextlib.suppress(FileNotFoundError):
                if self.caminho.stat().st_ino == self._inode:
                    self.caminho.unlink()
            self._inode = None

    # -- uma conexão ------------------------------------------------------

    async def _atender(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        con = _Conexao(escritor=writer)
        self._conexoes.add(con)
        try:
            par = credencial_do_par(writer.get_extra_info("socket"))
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
            for tarefa in con.tarefas:
                tarefa.cancel()
            for topico, fila in con.assinaturas:
                self.bus.unsubscribe(topico, fila)
            if con.deu_o_estado and con.sessao is not None:
                vazio = estado_vazio_dos_acessorios(con.sessao.mod_id)
                self._estados_dos_acessorios[con.sessao.mod_id] = vazio
                if "ler:acessorios.gesto" in con.sessao.permissoes:
                    self.bus.publish(EventTopic.ACESSORIOS_ESTADO, vazio)
            if con.acessorio_preso() and con.sessao is not None:
                self._soltar_o_acessorio(con.sessao.mod_id, con.funcoes_do_acessorio)
            if con.vibrando and con.sessao is not None:
                await self._soltar_a_vibracao(con.sessao, con.vibrando)
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
                    "permissoes": sorted(con.sessao.permissoes),  # (noqa-acento): contrato ASCII
                })
            if metodo == "eventos.assinar":
                return _resposta(req_id, self._assinar(con, writer, params))
            if metodo == "eventos.publicar":
                return _resposta(req_id, self._publicar(con, params))
            if metodo == "acessorios.estado":
                return _resposta(req_id, self._estado_dos_acessorios(con, params))
            if metodo == "luz.pulso":
                return _resposta(req_id, self._pulsar(con.sessao, params))
            if metodo == "lancador.jogos":
                return _resposta(req_id, self._jogos_do_lancador(con.sessao, params))
            if metodo == "controles.lista":
                # Fora do laço: a descrição dos controles toma a trava de E/S do backend.
                return _resposta(req_id, await asyncio.to_thread(
                    self._lista_dos_controles, con.sessao))
            if metodo in _ESCRITAS:
                # Como o IPC (``ipc:<método>``): quem grava no meio da escrita sabe de
                # onde ela veio, e a modificação deixa de escrever como «ninguém».
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
        dedos = params.get("dedos", False)
        if not isinstance(dedos, bool) or (dedos and TOPICO_DAS_ENTRADAS not in topicos):
            raise RecusaError(CODE_INVALID_PARAMS, "dedos é true ou false, com o tópico entradas")
        con.quer_os_dedos = con.quer_os_dedos or dedos
        for publico in topicos:
            for topico in TOPICOS_DE_LEITURA[publico]:
                if publico == TOPICO_DOS_BOTOES:
                    if not self.le_os_botoes():
                        # O primeiro leitor começa do zero: o retrato do último tique com leitor
                        # (o laço não chama ninguém sem ele) inventaria a borda de um aperto velho.
                        self._botoes_antes = None
                    fila: asyncio.Queue[Any] = asyncio.Queue(maxsize=DEFAULT_QUEUE_MAXSIZE)
                    con.filas_dos_botoes.append((topico, fila))
                elif publico == TOPICO_DAS_ENTRADAS:
                    # Quem chega começa do repouso: o controle fora dele sai de novo no tique
                    # seguinte, a todos (o valor repetido não muda nada a quem já o tinha).
                    self._entradas_enviadas = {
                        uniq: (None, quando, jogador, via)
                        for uniq, (_valores, quando, jogador, via)
                        in self._entradas_enviadas.items()
                    } if self.le_as_entradas() else {}
                    fila = asyncio.Queue(maxsize=DEFAULT_QUEUE_MAXSIZE)
                    con.filas_das_entradas.append(fila)
                    # A mesa que cai inteira não tem tique que leia: a queda leva o repouso.
                    saidas = self.bus.subscribe(EventTopic.CONTROLLER_DISCONNECTED)
                    con.assinaturas.append((EventTopic.CONTROLLER_DISCONNECTED, saidas))
                    con.tarefas.append(asyncio.create_task(
                        self._repousar_quem_sai(saidas),
                        name=f"mods-{con.sessao.mod_id}-entradas-quedas",
                    ))
                else:
                    fila = self.bus.subscribe(topico)
                    con.assinaturas.append((topico, fila))
                con.tarefas.append(asyncio.create_task(
                    self._encaminhar(con, writer, publico, topico, fila),
                    name=f"mods-{con.sessao.mod_id}-{topico}",
                ))
        return {"assinados": list(topicos)}

    def _lista_dos_controles(self, sessao: _Credencial) -> dict[str, Any]:
        """Os controles ligados agora, ``{controles: [{uniq, jogador}]}``, a quem lê a conexão.

        Sem a lista do serviço, vale o controle do posto. Nunca levanta: a lista que falha é vazia.
        """
        if "ler:conexao" not in sessao.permissoes:  # (noqa-acento): contrato ASCII
            raise RecusaError(CODE_SEM_PERMISSAO, "falta a permissão ler:conexao")  # noqa-acento: contrato
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
            controles.append({"uniq": uniq, "jogador": jogador if ok else None})
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
        evento = {"funcoes": pedidas, "origem": mod_id, "t": agora}  # noqa-acento: chave do contrato
        self.bus.publish(TOPICOS_DE_PUBLICACAO[topico], evento)
        con.funcoes_do_acessorio.update(pedidas)
        return {"publicado": True}

    def _soltar_o_acessorio(self, mod_id: str, funcoes: dict[str, float]) -> None:
        """Quem publicou saiu: o serviço publica, em nome dele, o zero de cada função usada."""
        self.bus.publish(EventTopic.JOGO_ACESSORIO, {
            "funcoes": dict.fromkeys(funcoes, 0.0),  # noqa-acento: chave do contrato
            "origem": mod_id,
            "t": self._relogio(),
        })

    def _estado_dos_acessorios(self, con: _Conexao, params: dict[str, Any]) -> dict[str, Any]:
        """O estado que a extensão devolve: a janela dela e a aba Conexões o mostram.

        Só com ``ler:acessorios.gesto`` ele vai ao barramento e liga os gestos do PS; com
        ``publicar:acessorios.estado`` ele só se mostra, e os gestos ficam os de sempre.
        """
        assert con.sessao is not None
        if not con.sessao.permissoes & set(PERMISSOES_DO_ESTADO):
            raise RecusaError(
                CODE_SEM_PERMISSAO,
                "falta a permissão publicar:acessorios.estado ou ler:acessorios.gesto",
            )
        estado = estado_dos_acessorios(con.sessao.mod_id, params)
        con.deu_o_estado = True
        serie = self._series[con.sessao.mod_id] = self._series.get(con.sessao.mod_id, 0) + 1
        self._estados_dos_acessorios[con.sessao.mod_id] = {**estado, "serie": serie}
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

    async def _soltar_a_vibracao(self, sessao: _Credencial, uniqs: set[str]) -> None:
        """Quem vibrou saiu: os motores que ele deixou ligados param, se o jogo não os tem."""
        for uniq in sorted(uniqs):
            if self._o_jogo_escreve(uniq, "vibracao"):
                continue
            try:
                await self._escritor("rumble.set", {"uniq": uniq, "weak": 0, "strong": 0})
            except Exception as exc:
                logger.warning("mods_porta_vibracao_nao_soltou", mod=sessao.mod_id,
                               err=type(exc).__name__)

    # -- a janela da extensão, pelo IPC principal ---------------------------

    def jogos_de(self, mod_id: str) -> list[dict[str, Any]]:
        """O último ``lancador.jogos`` de ``mod_id``; sem conexão viva, a lista vazia."""
        viva = any(
            con.sessao is not None and con.sessao.mod_id == mod_id for con in self._conexoes
        )
        return [dict(j) for j in self._jogos_dos_lancadores.get(mod_id, [])] if viva else []

    def agora_de(self, mod_id: str) -> dict[str, Any]:
        """O último ``acessorios.estado`` de ``mod_id``; sem conexão viva, o estado vazio.

        A coluna «Agora» da janela lê daqui: extensão parada ou que nunca devolveu o estado
        mostra a coluna vazia, sem número inventado.
        """
        estado = self.ultimo_estado_de(mod_id)
        return estado_vazio_dos_acessorios(mod_id) if estado is None else dict(estado)

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
        recebe por ali, o supervisor confere o parar dela, e a outra extensão não o recebe.
        ``False`` quando a extensão não está conectada à porta (nada a parar).
        """
        delas = [con for con in self._conexoes
                 if con.sessao is not None and con.sessao.mod_id == mod_id]
        if not delas:
            return False
        for con in delas:
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
        delas = self._conexoes_de(mod_id)
        for con in delas:
            assert con.escritor is not None
            self._avisar(con, con.escritor, nome, dados)
        return bool(delas)

    def acao(self, mod_id: str, acao: str, *, alvo: str | None = None,
             valor: bool | None = None) -> bool:
        """O clique numa ação da janela: ``extensao.acao`` só para as conexões de ``mod_id``.

        ``alvo`` é o ``id`` do aparelho (as ``aparelhos_acoes``); ``valor`` é a chave ``ligar``
        (``True`` liga). ``False`` quando a extensão não está conectada à porta.
        """
        dados: dict[str, Any] = {"mod": mod_id, "acao": acao, "alvo": alvo}  # noqa-acento: contrato
        if valor is not None:
            dados["valor"] = valor
        return self._avisar_a(mod_id, EVENTO_DA_ACAO, dados)

    def livre(self, mod_id: str, opcao_id: str, valor: float, *, soltou: bool) -> bool:
        """O arrastar do ``livre``: ``extensao.livre {mod, id, valor, soltou}`` só para ``mod_id``.

        No máximo ``LIVRE_POR_SEGUNDO`` eventos por segundo: o primeiro arrastar abre um compasso
        de ``1 / LIVRE_POR_SEGUNDO`` s, e ao fim dele sai o valor mais novo. O soltar sai na hora,
        cancela o que esperava e leva o valor final. ``False`` sem a extensão na porta.
        """
        if not self._conexoes_de(mod_id):
            return False
        dados = {"mod": mod_id, "id": opcao_id, "valor": round(min(1.0, max(0.0, valor)), 3),
                 "soltou": soltou}
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

    def _fim_do_compasso(self, chave: tuple[str, str]) -> None:
        compasso = self._livres.get(chave)
        if compasso is None:
            return
        dados, compasso.pendente, compasso.relogio = compasso.pendente, None, None
        if dados is not None:
            self._avisar_a(chave[0], EVENTO_DO_LIVRE, dados)

    # -- o tópico ``botoes``, de todo controle ------------------------------

    def le_os_botoes(self) -> bool:
        """Alguma extensão assinou o tópico ``botoes``? Sem ela, o tique não lê controle nenhum."""
        return any(con.filas_dos_botoes for con in self._conexoes)

    def botoes_do_tique(
        self,
        apertados: dict[str | None, frozenset[str]],
        jogador_de: Callable[[str | None], int | None],
    ) -> None:
        """As bordas deste tique, de cada controle: ``button.down`` e ``button.up`` com o dele.

        ``apertados`` é ``{uniq: botões}`` de todo controle lido no tique. O controle que
        sumiu solta o que segurava. Roda no laço do serviço; nunca espera o socket (a fila que
        enche descarta o mais antigo, como a do barramento).
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
            for nome, apertado, botoes in (
                (EventTopic.BUTTON_DOWN, True, descidos), (EventTopic.BUTTON_UP, False, subidos),
            ):
                for botao in botoes:
                    carga = {"button": botao, "botao": botao, "pressed": apertado,
                             "uniq": uniq, "jogador": jogador}
                    for topico, fila in filas:
                        if topico == nome:
                            _por_na_fila(fila, carga)

    # -- o tópico ``entradas``, de todo controle -----------------------------

    def le_as_entradas(self) -> bool:
        """Alguma extensão assinou o tópico ``entradas``? Sem ela, o tique não lê controle."""
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
                continue  # quem publicou nunca recebe o próprio evento
            if (
                topico == EventTopic.ACESSORIOS_GESTO
                and isinstance(carga, dict)
                and con.sessao is not None
                and carga.get("mod") not in (None, con.sessao.mod_id)
            ):
                continue  # o «Parar tudo» de uma janela vai só à extensão dela
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
    """Os controles que o backend adotou e estão ligados, com o número que cada um acende."""

    def controles() -> list[dict[str, Any]]:
        from hefesto_dualsense4unix.daemon.subsystems.vibracao_do_jogo import _jogador_de

        descrever = getattr(getattr(daemon, "controller", None), "describe_controllers", None)
        if not callable(descrever):
            posto = _primario(getattr(daemon, "controller", None))
            return [{"uniq": posto, "jogador": _jogador_de(daemon, posto)}] if posto else []
        saida: list[dict[str, Any]] = []
        for item in descrever():
            uniq = item.get("uniq") if isinstance(item, dict) else None
            if isinstance(uniq, str) and uniq and item.get("connected"):
                saida.append({"uniq": uniq, "jogador": _jogador_de(daemon, uniq)})
        return saida

    return controles


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


#: Os eixos do ``ControllerState`` do posto, na ordem das ``entradas``, com o valor do repouso.
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


def _primario(controle: Any) -> str | None:
    """O ``primary_uniq`` do backend (uma propriedade; num dublê, pode ser método)."""
    valor = getattr(controle, "primary_uniq", None)
    if callable(valor):
        valor = valor()
    return valor if isinstance(valor, str) and valor else None


__all__ = [
    "CODE_NAO_ESCREVEU",
    "CODE_O_JOGO_ESCREVE",
    "CODE_QUEM_E_VOCE",
    "CODE_SEM_PERMISSAO",
    "ENTRADAS_POR_SEGUNDO",
    "EVENTO_DA_ACAO",
    "EVENTO_DO_LIVRE",
    "EVENTO_DO_PARAR",
    "JANELA_DA_VIBRACAO_DO_JOGO_S",
    "LIVRE_POR_SEGUNDO",
    "PUBLICACOES_POR_SEGUNDO",
    "Controles",
    "Porta",
    "RecusaError",
    "botoes_de_todo_controle_no_servico",
    "controles_no_servico",
    "credencial_do_par",
    "descende_de",
    "entradas_de_todo_controle_no_servico",
    "escritor_do_servico",
    "estado_dos_acessorios",
    "estado_vazio_dos_acessorios",
    "o_jogo_escreve_no_servico",
    "pulsar_no_servico",
    "topicos_de_todo_controle_no_servico",
    "uniq_do_posto_no_servico",
]
