"""A ação da extensão devolve a resposta (16/11/2026).

O-TESTAR-DA-EXTENSAO-DIZ-SE-TOCOU-01, o lado genérico do Hefesto. A ação que o manifesto declara
com ``responde: true`` leva um ``id`` no ``extensao.acao``, e o ``mods.acao`` espera a
``extensao.resposta {para: id, dados}`` por até ``PRAZO_DA_RESPOSTA_S`` e a devolve em
``{enviada, respondeu, resposta}``. Sem ``responde``, nada espera: volta ``{enviada}`` como antes.

MORDIDAS: devolver só o ``enviada`` em ``_handle_mods_acao`` (tirar o ramo do ``responde``) e a
resposta some; tirar o ``id`` dos ``dados`` em ``_esperar_a_resposta`` e a extensão não tem a
que responder.
"""
from __future__ import annotations

import asyncio
import functools
import json
import os
import pathlib
import shutil
import socket
import tempfile
import time
from collections.abc import Iterator
from types import SimpleNamespace
from typing import Any

import pytest

from hefesto_dualsense4unix.core.events import EventBus
from hefesto_dualsense4unix.daemon.ipc_handlers import IpcHandlersMixin
from hefesto_dualsense4unix.mods import porta as modulo_da_porta
from hefesto_dualsense4unix.mods.instalador import Lugares
from hefesto_dualsense4unix.mods.manifesto import Manifesto
from hefesto_dualsense4unix.mods.porta import Porta

P1 = "aa:bb:cc:00:00:91"
VEREDITO = {"controles": [
    {"uniq": P1, "tocou": False, "motivo": "no Modo Nativo o jogo fala direto com o controle"}]}


@pytest.fixture
def curto() -> Iterator[pathlib.Path]:
    pasta = pathlib.Path(tempfile.mkdtemp(prefix="ar"))
    try:
        yield pasta
    finally:
        shutil.rmtree(pasta, ignore_errors=True)


class _Extensao:
    """A extensão de mentira, numa thread: responde (ou não) a cada ``extensao.acao``."""

    def __init__(self, caminho: pathlib.Path, resposta: Any, *, responde: bool) -> None:
        self.sock = socket.socket(socket.AF_UNIX)
        self.sock.connect(str(caminho))
        self.arquivo = self.sock.makefile("rb")
        self.resposta = resposta
        self.responde = responde
        self.acoes: list[dict[str, Any]] = []
        self.entregas: list[dict[str, Any]] = []
        self.proximo = 0

    def _linha(self, metodo: str, params: dict[str, Any]) -> None:
        self.proximo += 1
        linha = {"jsonrpc": "2.0", "id": self.proximo, "method": metodo, "params": params}
        self.sock.sendall(json.dumps(linha).encode() + b"\n")

    def ola(self) -> dict[str, Any]:
        self._linha("mod.ola", {"ficha": "ficha"})
        return dict(json.loads(self.arquivo.readline()))

    def atender(self, segundos: float) -> None:
        self.sock.settimeout(segundos)
        try:
            while True:
                linha = self.arquivo.readline()
                if not linha:
                    return
                msg = json.loads(linha)
                if msg.get("method") == "evento" and msg["params"]["nome"] == "extensao.acao":
                    dados = msg["params"]["dados"]
                    self.acoes.append(dados)
                    if self.responde and "id" in dados:
                        self._linha("extensao.resposta", {"para": dados["id"],
                                                          "dados": self.resposta})
                elif "result" in msg:
                    self.entregas.append(msg["result"])
        except (TimeoutError, OSError):
            return

    def fechar(self) -> None:
        self.arquivo.close()
        self.sock.close()


def _manifesto(responde: bool) -> dict[str, Any]:
    testar: dict[str, Any] = {"id": "testar-golpe", "rotulo": "Testar o golpe", "icone": "testar"}
    if responde:
        testar["responde"] = True
    return {"id": "imersao", "nome": "Imersão", "versao": "0.1", "api": ">=1,<3",  # (noqa-acento)
            "licenca": "MIT", "tipos": ["tema"], "tema": {},
            "permissoes": ["publicar:acessorios.estado"],  # (noqa-acento)
            "acoes": [testar, {"id": "parear", "rotulo": "Parear"}]}  # (noqa-acento)


def _lugares(raiz: pathlib.Path, manifesto: dict[str, Any]) -> Lugares:
    lugares = Lugares(codigo=raiz / "codigo", dados=raiz / "dados",  # (noqa-acento)
                      registro=raiz / "config" / "mods.json",
                      estado=raiz / "run" / "mods-estado.json")
    pasta = lugares.codigo / "imersao"
    pasta.mkdir(parents=True)
    (pasta / "hefesto-mod.json").write_text(json.dumps(manifesto), encoding="utf-8")
    return lugares


def _servico(lugares: Lugares, porta: Any) -> Any:
    servico: Any = SimpleNamespace(
        daemon=SimpleNamespace(_mods_supervisor=SimpleNamespace(lugares=lugares, porta=porta)),
        _mod_do_pedido=IpcHandlersMixin._mod_do_pedido)
    servico._manifesto_da_janela = functools.partial(IpcHandlersMixin._manifesto_da_janela,
                                                     servico)
    return servico


def _clicar(curto: pathlib.Path, *, responde_no_manifesto: bool, responde_na_extensao: bool,
            acoes: tuple[str, ...] = ("testar-golpe",), alvo: str | None = None,
            manifesto: dict[str, Any] | None = None) -> tuple[list[Any], _Extensao, float]:
    lugares = _lugares(curto, manifesto or _manifesto(responde_no_manifesto))

    async def corrida() -> tuple[list[Any], _Extensao, float]:
        async def escritor(_m: str, _p: dict[str, Any]) -> Any:
            return {"status": "ok"}

        porta = Porta(curto / "mods.sock", EventBus(), escritor=escritor,
                      o_jogo_escreve=lambda _u, _c: False, uniq_do_posto=lambda: P1)
        await porta.iniciar()
        porta.registrar("ficha", "imersao", os.getpid(), ["publicar:acessorios.estado"])
        ext = _Extensao(curto / "mods.sock", VEREDITO, responde=responde_na_extensao)
        assert "result" in await asyncio.to_thread(ext.ola)
        atendente = asyncio.create_task(asyncio.to_thread(ext.atender, 3.0))
        servico = _servico(lugares, porta)
        try:
            inicio = time.monotonic()
            respostas = [await IpcHandlersMixin._handle_mods_acao(
                servico, {"mod": "imersao", "acao": a, "alvo": alvo})  # (noqa-acento)
                for a in acoes]
            gasto = time.monotonic() - inicio
            await asyncio.sleep(0.3)
        finally:
            ext.sock.shutdown(socket.SHUT_RDWR)
            await atendente
            ext.fechar()
            await porta.parar()
        return respostas, ext, gasto

    return asyncio.run(corrida())


def test_o_manifesto_declara_a_acao_que_responde() -> None:
    m = Manifesto.model_validate(_manifesto(True))
    assert [a.responde for a in m.acoes] == [True, False]


def test_a_acao_que_responde_devolve_o_veredito_da_extensao(curto: pathlib.Path) -> None:
    respostas, ext, _gasto = _clicar(curto, responde_no_manifesto=True, responde_na_extensao=True)
    assert respostas == [{"enviada": True, "respondeu": True, "resposta": VEREDITO}]
    primeira = ext.acoes[0]
    assert primeira["acao"] == "testar-golpe" and isinstance(primeira["id"], str)  # (noqa-acento)
    assert {"entregue": True} in ext.entregas


def test_a_extensao_que_nao_responde_segue_enviada_no_prazo(
    curto: pathlib.Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(modulo_da_porta, "PRAZO_DA_RESPOSTA_S", 0.3)
    respostas, ext, gasto = _clicar(curto, responde_no_manifesto=True, responde_na_extensao=False)
    assert respostas == [{"enviada": True, "respondeu": False, "resposta": None}]
    assert len(ext.acoes) == 1
    assert 0.25 <= gasto < 2.0


def test_a_acao_sem_responde_nao_espera_nem_leva_id(curto: pathlib.Path) -> None:
    respostas, ext, gasto = _clicar(curto, responde_no_manifesto=False, responde_na_extensao=True,
                                    acoes=("testar-golpe", "parear"))
    assert respostas == [{"enviada": True}, {"enviada": True}]
    assert gasto < 0.5, "a ação sem resposta esperou a extensão"
    assert [a.get("id") for a in ext.acoes] == [None, None]


def test_a_acao_do_aparelho_que_responde_devolve_a_resposta_com_o_alvo(
    curto: pathlib.Path,
) -> None:
    manifesto = _manifesto(False)
    manifesto["aparelhos_acoes"] = {"grupo": "Aparelhos", "acoes": [  # (noqa-acento)
        {"id": "testar", "rotulo": "Testar", "icone": "testar", "responde": True},
        {"id": "esquecer", "rotulo": "Esquecer", "icone": "esquecer"}]}
    respostas, ext, _gasto = _clicar(curto, responde_no_manifesto=False,
                                     responde_na_extensao=True, acoes=("testar", "esquecer"),
                                     alvo="lampada", manifesto=manifesto)
    assert respostas == [{"enviada": True, "respondeu": True, "resposta": VEREDITO},
                         {"enviada": True}]
    assert [(a["alvo"], "id" in a) for a in ext.acoes] == [("lampada", True), ("lampada", False)]


def test_sem_a_extensao_na_porta_nada_e_enviado(curto: pathlib.Path) -> None:
    lugares = _lugares(curto, _manifesto(True))

    async def corrida() -> Any:
        async def escritor(_m: str, _p: dict[str, Any]) -> Any:
            return {"status": "ok"}

        porta = Porta(curto / "mods.sock", EventBus(), escritor=escritor,
                      o_jogo_escreve=lambda _u, _c: False, uniq_do_posto=lambda: P1)
        await porta.iniciar()
        try:
            return await IpcHandlersMixin._handle_mods_acao(
                _servico(lugares, porta),
                {"mod": "imersao", "acao": "testar-golpe"})  # (noqa-acento)
        finally:
            await porta.parar()

    assert asyncio.run(corrida()) == {"enviada": False, "respondeu": False, "resposta": None}
