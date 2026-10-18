"""O pedido do jogo ao brinquedo passa de uma extensão a outra pela porta.

O ``eventos.publicar`` ``{topico, dados}`` entrega um evento a quem tem ``ler:<tópico>``. O primeiro
tópico publicável é ``jogo.brinquedo`` (``{funcoes: {<função>: 0..1}, origem, t}``): pede
``publicar:jogo.brinquedo``, o serviço põe ``origem`` e ``t``, quem publicou nunca recebe o próprio
evento, e quando ele sai o serviço publica o zero que faltou.

Porta de verdade, em socket, com mods de mentira (a ficha e o PID são os do próprio teste).

MORDIDAS (executadas aqui): tirar o zero da desconexão reprova o caso de quem sai; aceitar sem a
permissão reprova o ``-32010``; deixar o publicador receber o próprio evento, aceitar valor acima de
1 e tirar o teto de 20 por segundo reprovam cada um o seu caso.
"""
from __future__ import annotations

import asyncio
import contextlib
import json
import os
import socket
import tempfile
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.core.events import EventBus, EventTopic
from hefesto_dualsense4unix.daemon.protocolo_do_ipc import CODE_INVALID_PARAMS
from hefesto_dualsense4unix.mods.manifesto import (
    FUNCOES_DO_BRINQUEDO,
    TOPICOS_DE_LEITURA,
    TOPICOS_DE_PUBLICACAO,
    Manifesto,
    permissao_valida,
)
from hefesto_dualsense4unix.mods.porta import CODE_SEM_PERMISSAO, Porta

RAIZ = Path(__file__).resolve().parents[2]
DOC = RAIZ / "docs" / "protocol" / "porta-das-modificacoes.md"
LER = "ler:jogo.brinquedo"
PUBLICAR = "publicar:jogo.brinquedo"
F = "funcoes"  # noqa-acento: chave do contrato
INVALIDO = CODE_INVALID_PARAMS


class _Relogio:
    def __init__(self) -> None:
        self.agora = 100.0

    def __call__(self) -> float:
        return self.agora


class _Mod:
    """Um cliente da porta que guarda os eventos que chegam enquanto espera uma resposta."""

    def __init__(self, caminho: Path) -> None:
        self.sock = socket.socket(socket.AF_UNIX)
        self.sock.settimeout(3)  # a leitura sem resposta estoura aqui, e o teste não fica preso
        self.sock.connect(str(caminho))
        self.arquivo = self.sock.makefile("rb")
        self.proximo = 0
        self.guardados: list[dict[str, Any]] = []

    def _pedir(self, metodo: str, params: dict[str, Any]) -> dict[str, Any]:
        self.proximo += 1
        linha = {"jsonrpc": "2.0", "id": self.proximo, "method": metodo, "params": params}
        self.sock.sendall(json.dumps(linha).encode() + b"\n")
        while True:
            resposta: dict[str, Any] = json.loads(self.arquivo.readline())
            if resposta.get("id") == self.proximo:
                return resposta
            self.guardados.append(resposta)

    def _evento(self) -> dict[str, Any]:
        if self.guardados:
            return self.guardados.pop(0)
        recebido: dict[str, Any] = json.loads(self.arquivo.readline())
        return recebido

    async def pedir(self, metodo: str, params: dict[str, Any]) -> dict[str, Any]:
        return await asyncio.to_thread(self._pedir, metodo, params)

    async def evento(self) -> dict[str, Any]:
        return await asyncio.to_thread(self._evento)

    async def dados(self) -> dict[str, Any]:
        e = await self.evento()
        assert e["params"]["topico"] == "jogo.brinquedo", e
        d: dict[str, Any] = e["params"]["dados"]
        return d

    async def publicar(self, funcoes: Any, topico: str = "jogo.brinquedo") -> dict[str, Any]:
        dados = {F: funcoes}
        return await self.pedir("eventos.publicar", {"topico": topico, "dados": dados})

    def fechar(self) -> None:
        for fechavel in (self.arquivo, self.sock):
            with contextlib.suppress(OSError):
                fechavel.close()


Corpo = Callable[[Porta, EventBus, dict[str, _Mod]], Awaitable[None]]


def _correr(mods: dict[str, tuple[list[str], bool]], corpo: Corpo,
            relogio: _Relogio | None = None) -> None:
    """Sobe a porta, abre cada mod (``id: (permissões, assina)``) e entrega ao ``corpo``."""

    async def corrida() -> None:
        with tempfile.TemporaryDirectory(prefix="jb") as pasta:
            curto = Path(pasta)
            bus = EventBus()

            async def escritor(_m: str, _p: dict[str, Any]) -> Any:
                return {"status": "ok"}

            extra: dict[str, Any] = {} if relogio is None else {"relogio": relogio}
            porta = Porta(
                curto / "mods.sock", bus, escritor=escritor,
                o_jogo_escreve=lambda _u, _c: False, uniq_do_posto=lambda: "uniq", **extra,
            )
            await porta.iniciar()
            clientes: dict[str, _Mod] = {}
            try:
                for mod_id, (permissoes, assina) in mods.items():
                    porta.registrar(f"ficha-{mod_id}", mod_id, os.getpid(), permissoes)
                    cliente = _Mod(curto / "mods.sock")
                    clientes[mod_id] = cliente
                    ola = await cliente.pedir("mod.ola", {"ficha": f"ficha-{mod_id}"})
                    assert ola["result"]["id"] == mod_id
                    if assina:
                        ok = await cliente.pedir("eventos.assinar", {"topicos": ["jogo.brinquedo"]})
                        assert ok["result"] == {"assinados": ["jogo.brinquedo"]}
                await corpo(porta, bus, clientes)
            finally:
                for cliente in clientes.values():
                    cliente.fechar()
                await porta.parar()

    asyncio.run(corrida())


def _quem_publica_e_quem_le() -> dict[str, tuple[list[str], bool]]:
    return {"b": ([PUBLICAR], False), "a": ([LER], True)}


# 1. A permissão, o tópico e o envelope.

def test_o_topico_e_as_duas_permissoes_existem_e_a_lista_de_publicaveis_e_fechada() -> None:
    assert permissao_valida(LER) and permissao_valida(PUBLICAR)
    assert TOPICOS_DE_LEITURA["jogo.brinquedo"] == (EventTopic.JOGO_BRINQUEDO,)
    assert TOPICOS_DE_PUBLICACAO == {"jogo.brinquedo": EventTopic.JOGO_BRINQUEDO}
    assert not permissao_valida("publicar:estado"), "só os tópicos da lista fechada se publicam"
    assert FUNCOES_DO_BRINQUEDO == (
        "vibrar", "girar", "bombear", "empurrar", "sugar", "oscilar", "profundidade", "curso",
        "dedilhar")


def test_o_manifesto_aceita_publicar_e_ler_o_jogo_brinquedo_e_recusa_publicar_o_que_nao_existe(
) -> None:
    base: dict[str, Any] = {
        "id": "ponte", "nome": "Ponte", "versao": "0.1", "api": ">=1,<2", "licenca": "MIT",  # noqa-acento: chave do contrato
        "tipos": ["tema"], "tema": {},  # noqa-acento: chave do contrato
    }
    m = Manifesto(**base, permissoes=[LER, PUBLICAR])  # noqa-acento: chave do contrato
    assert set(m.permissoes) == {LER, PUBLICAR}
    with pytest.raises(ValueError, match="permissão desconhecida"):
        Manifesto(**base, permissoes=["publicar:jogo.vibracao"])  # noqa-acento: chave do contrato


def test_quem_le_recebe_com_a_origem_de_quem_publicou_e_o_t_do_servico() -> None:
    relogio = _Relogio()

    async def corpo(_p: Porta, _b: EventBus, c: dict[str, _Mod]) -> None:
        ok = await c["b"].publicar({"vibrar": 0.8, "girar": 0.25})
        assert ok["result"] == {"publicado": True}
        evento = await c["a"].evento()
        assert evento["params"]["topico"] == "jogo.brinquedo"
        assert evento["params"]["nome"] == EventTopic.JOGO_BRINQUEDO
        assert evento["params"]["dados"] == {
            F: {"vibrar": 0.8, "girar": 0.25}, "origem": "b", "t": 100.0}

    _correr(_quem_publica_e_quem_le(), corpo, relogio)


def test_a_origem_e_o_t_que_a_extensao_mandar_caem_e_vale_o_do_servico() -> None:
    async def corpo(_p: Porta, _b: EventBus, c: dict[str, _Mod]) -> None:
        await c["b"].pedir("eventos.publicar", {"topico": "jogo.brinquedo", "dados": {
            F: {"vibrar": 0.5}, "origem": "a", "t": -1}})
        dados = await c["a"].dados()
        assert dados["origem"] == "b" and dados["t"] != -1, "a origem não pode ser forjada"

    _correr(_quem_publica_e_quem_le(), corpo)


def test_a_assinatura_do_jogo_brinquedo_usa_a_fila_de_256() -> None:
    async def corpo(porta: Porta, _b: EventBus, _c: dict[str, _Mod]) -> None:
        filas = porta.assinaturas_de("a")
        assert [f.maxsize for f in filas] == [256]

    _correr(_quem_publica_e_quem_le(), corpo)


# 2. As recusas.

def test_sem_a_permissao_a_porta_recusa_com_32010_e_ninguem_recebe() -> None:
    async def corpo(_p: Porta, _b: EventBus, c: dict[str, _Mod]) -> None:
        recusa = await c["so_le"].publicar({"vibrar": 0.5})
        assert recusa["error"]["code"] == CODE_SEM_PERMISSAO
        assert recusa["error"]["message"] == "falta a permissão publicar:jogo.brinquedo"
        await c["b"].publicar({"vibrar": 0.1})
        assert (await c["a"].dados())["origem"] == "b", (
            "o pedido recusado chegou a quem assina")

    _correr({"so_le": ([LER], False), "b": ([PUBLICAR], False), "a": ([LER], True)}, corpo)


@pytest.mark.parametrize("topico", ["estado", "jogo.vibracao", "jogo.momento", "", None, 7])
def test_topico_fora_da_lista_de_publicaveis_e_recusado(topico: Any) -> None:
    async def corpo(_p: Porta, _b: EventBus, c: dict[str, _Mod]) -> None:
        recusa = await c["b"].publicar({"vibrar": 0.5}, topico=topico)
        assert recusa["error"]["code"] == INVALIDO, recusa

    _correr(_quem_publica_e_quem_le(), corpo)


@pytest.mark.parametrize("pedido", [
    {"vibrar": 1.5}, {"vibrar": -0.1}, {"vibrar": True}, {"vibrar": "0.5"}, {"vibrar": None},
    {"vibrar": float("nan")}, {"vibrar": float("inf")},
    {"cocegar": 0.5}, {"vibrar": 0.5, "cocegar": 0.5},
    {}, [], "vibrar", None,
])
def test_valor_ou_funcao_invalidos_sao_recusados_e_nada_chega(pedido: Any) -> None:
    async def corpo(_p: Porta, _b: EventBus, c: dict[str, _Mod]) -> None:
        recusa = await c["b"].publicar(pedido)
        assert recusa["error"]["code"] == INVALIDO, recusa
        await c["b"].publicar({"vibrar": 0.2})
        assert (await c["a"].dados())[F] == {"vibrar": 0.2}, (
            "o pedido inválido chegou a quem assina")

    _correr(_quem_publica_e_quem_le(), corpo)


def test_dados_ausentes_ou_que_nao_sao_objeto_sao_recusados() -> None:
    async def corpo(_p: Porta, _b: EventBus, c: dict[str, _Mod]) -> None:
        for dados in (None, 3, "x", [], {"vibrar": 0.5}):
            r = await c["b"].pedir("eventos.publicar", {"topico": "jogo.brinquedo", "dados": dados})
            assert r["error"]["code"] == INVALIDO, (dados, r)
        r = await c["b"].pedir("eventos.publicar", {"topico": "jogo.brinquedo"})
        assert r["error"]["code"] == INVALIDO

    _correr(_quem_publica_e_quem_le(), corpo)


# 3. Quem publica não recebe o próprio evento.

def test_quem_publica_nunca_recebe_o_proprio_evento() -> None:
    async def corpo(_p: Porta, _b: EventBus, c: dict[str, _Mod]) -> None:
        await c["b"].publicar({"vibrar": 0.1})
        await c["a"].publicar({"vibrar": 0.2})
        await c["c"].publicar({"vibrar": 0.3})
        assert [(await c["a"].dados())["origem"] for _ in range(2)] == ["b", "c"]
        assert [(await c["b"].dados())["origem"] for _ in range(2)] == ["a", "c"]
        assert [(await c["c"].dados())["origem"] for _ in range(2)] == ["b", "a"]

    todos = ([LER, PUBLICAR], True)
    _correr({"a": todos, "b": todos, "c": todos}, corpo)


# 4. O zero no fim.

def test_a_extensao_que_publicou_e_sai_deixa_o_zero_para_quem_assina() -> None:
    async def corpo(_p: Porta, _b: EventBus, c: dict[str, _Mod]) -> None:
        await c["b"].publicar({"vibrar": 0.8})
        assert (await c["a"].dados())[F] == {"vibrar": 0.8}
        c["b"].fechar()
        zero = await c["a"].dados()
        assert zero["origem"] == "b"
        assert zero[F] == dict.fromkeys(FUNCOES_DO_BRINQUEDO, 0.0), (
            "o último pedido ficou preso: faltou o zero")

    _correr(_quem_publica_e_quem_le(), corpo)


def test_quem_ja_tinha_zerado_ou_nunca_publicou_nao_deixa_zero_nenhum() -> None:
    async def corpo(_p: Porta, _b: EventBus, c: dict[str, _Mod]) -> None:
        await c["zerou"].publicar({"vibrar": 0.8})
        await c["zerou"].publicar({"vibrar": 0.0})
        c["zerou"].fechar()
        c["mudo"].fechar()
        await c["b"].publicar({"vibrar": 0.5})
        vistos = [(await c["a"].dados())[F] for _ in range(3)]
        assert vistos == [{"vibrar": 0.8}, {"vibrar": 0.0}, {"vibrar": 0.5}], (
            "o serviço repetiu o zero de quem já zerou, ou inventou o de quem nunca publicou")

    _correr({
        "zerou": ([PUBLICAR], False), "mudo": ([PUBLICAR], False),
        "b": ([PUBLICAR], False), "a": ([LER], True)}, corpo)


def test_a_publicacao_parcial_nao_esconde_a_funcao_que_ficou_acima_de_zero() -> None:
    """Quem manda só a função que mudou (vibrar, depois girar em 0) deixa o vibrar preso."""

    async def corpo(_p: Porta, _b: EventBus, c: dict[str, _Mod]) -> None:
        await c["b"].publicar({"vibrar": 0.8})
        await c["b"].publicar({"girar": 0.0})
        assert (await c["a"].dados())[F] == {"vibrar": 0.8}
        assert (await c["a"].dados())[F] == {"girar": 0.0}
        c["b"].fechar()
        zero = await c["a"].dados()
        assert zero[F] == dict.fromkeys(FUNCOES_DO_BRINQUEDO, 0.0), (
            "o vibrar ficou preso: a última publicação só zerou o girar")

    _correr(_quem_publica_e_quem_le(), corpo)


# 5. O teto de 20 por segundo por extensão.

def test_a_21a_publicacao_no_mesmo_segundo_e_recusada_e_o_segundo_seguinte_libera() -> None:
    relogio = _Relogio()

    async def corpo(_p: Porta, _b: EventBus, c: dict[str, _Mod]) -> None:
        for i in range(20):
            ok = await c["b"].publicar({"vibrar": (i % 10) / 10})
            assert ok["result"] == {"publicado": True}, i
        recusa = await c["b"].publicar({"vibrar": 0.5})
        assert recusa["error"]["code"] == INVALIDO
        assert "20 por segundo" in recusa["error"]["message"]
        outra = await c["outra"].publicar({"vibrar": 0.5})
        assert outra["result"] == {"publicado": True}, "o teto é de cada extensão, não de todas"
        relogio.agora += 1.0
        assert (await c["b"].publicar({"vibrar": 0.5}))["result"] == {"publicado": True}

    _correr({"b": ([PUBLICAR], False), "outra": ([PUBLICAR], False), "a": ([LER], True)},
            corpo, relogio)


def test_a_publicacao_recusada_nao_conta_no_teto() -> None:
    relogio = _Relogio()

    async def corpo(_p: Porta, _b: EventBus, c: dict[str, _Mod]) -> None:
        for _ in range(30):
            assert "error" in await c["b"].publicar({"vibrar": 2})
        for i in range(20):
            assert (await c["b"].publicar({"vibrar": 0.5}))["result"] == {"publicado": True}, i

    _correr(_quem_publica_e_quem_le(), corpo, relogio)


# 6. O documento da porta.

def test_a_doc_da_porta_descreve_o_metodo_o_topico_o_zero_e_o_teto() -> None:
    texto = DOC.read_text(encoding="utf-8")
    for pedaco in ("eventos.publicar", "publicar:jogo.brinquedo", "ler:jogo.brinquedo",
                   "jogo.brinquedo", "-32010", "20 publicações", "as nove funções em 0",
                   "nunca recebe o próprio evento"):
        assert pedaco in texto, f"a doc da porta não diz «{pedaco}»"
    for funcao in FUNCOES_DO_BRINQUEDO:
        assert f"`{funcao}`" in texto, funcao
