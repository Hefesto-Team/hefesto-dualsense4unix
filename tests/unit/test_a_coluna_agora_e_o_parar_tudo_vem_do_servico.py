"""A coluna «Agora» e o «Parar tudo» da janela da extensão vêm do serviço.

O manifesto declara `agora` (nivel, perfil, aparelhos) e `parar_tudo`; a janela os desenha do último
`acessorios.estado` da extensão, que o serviço guarda por extensão e entrega por `mods.agora`, e o
«Parar tudo» publica `acessorios.gesto {gesto: "para", mod}` por `mods.parar_tudo`, só para ela.

MORDIDAS (19/10/2026, executadas sobre a cura e devolvidas):

- o `ja-parar` desenhado sem olhar o `parar_tudo` do manifesto reprova
  `test_sem_parar_tudo_no_manifesto_a_janela_nao_tem_o_botao`;
- a coluna desenhada com os três pedaços, sem olhar o `agora`, reprova
  `test_a_coluna_desenha_so_os_pedacos_que_o_manifesto_declara`;
- o filtro do `mod` tirado do `_encaminhar` da porta reprova
  `test_o_parar_tudo_chega_so_a_extensao_da_janela` (a outra extensão recebe o `para`);
- um nível de mentira de volta ao `comportamento.js`, sem olhar a coluna do serviço, reprova
  `test_o_clique_no_parar_tudo_nao_poe_numero_na_coluna_do_servico` (o «—» vira «0»; a mordida
  roda dentro do próprio teste).
"""

from __future__ import annotations

import asyncio
import json
import os
import pathlib
import shutil
import socket
import sys
import tempfile
from collections.abc import Iterator
from types import SimpleNamespace
from typing import Any

import pytest

from hefesto_dualsense4unix.core.events import EventBus
from hefesto_dualsense4unix.daemon.ipc_handlers import IpcHandlersMixin
from hefesto_dualsense4unix.mods.porta import Porta, estado_vazio_dos_acessorios
from tests.unit.test_a_aba_lancadores_ganha_as_modificacoes import (  # noqa: F401
    _a07,
    _fonte,
    _instalar,
    ctx,
    lar,
)

P1 = "aa:bb:cc:00:00:01"
GESTO = "ler:acessorios.gesto"
VIVO = {"ligado": True, "nivel": 4, "perfil": "Ondas", "aparelhos": ["Motor <b>", "Outro"]}


@pytest.fixture
def curto() -> Iterator[pathlib.Path]:
    base = "/var/tmp" if os.access("/var/tmp", os.W_OK) else None
    pasta = pathlib.Path(tempfile.mkdtemp(prefix="hc", dir=base))
    try:
        yield pasta
    finally:
        shutil.rmtree(pasta, ignore_errors=True)


class _Extensao:
    """A extensão de mentira: fala a porta por um socket e guarda os eventos que chegam."""

    def __init__(self, caminho: pathlib.Path) -> None:
        self.sock = socket.socket(socket.AF_UNIX)
        self.sock.connect(str(caminho))
        self.arquivo = self.sock.makefile("rb")
        self.proximo = 0
        self.eventos: list[dict[str, Any]] = []

    def pedir(self, metodo: str, params: dict[str, Any]) -> dict[str, Any]:
        self.proximo += 1
        linha = {"jsonrpc": "2.0", "id": self.proximo, "method": metodo, "params": params}
        self.sock.sendall(json.dumps(linha).encode() + b"\n")
        while True:
            resposta: dict[str, Any] = json.loads(self.arquivo.readline())
            if resposta.get("id") == self.proximo:
                return resposta
            self.eventos.append(resposta)

    def esperar_evento(self, segundos: float) -> dict[str, Any] | None:
        if self.eventos:
            return self.eventos.pop(0)
        self.sock.settimeout(segundos)
        try:
            linha = self.arquivo.readline()
        except (TimeoutError, OSError):
            return None
        finally:
            self.sock.settimeout(None)
        return json.loads(linha) if linha else None

    def fechar(self) -> None:
        self.arquivo.close()
        self.sock.close()


async def _porta(curto: pathlib.Path, bus: EventBus) -> Porta:
    async def escritor(metodo: str, pedido: dict[str, Any]) -> Any:
        return {"status": "ok"}

    porta = Porta(curto / "mods.sock", bus, escritor=escritor,
                  o_jogo_escreve=lambda uniq, canal: False, uniq_do_posto=lambda: P1)
    await porta.iniciar()
    porta.registrar("ficha-a", "acessorios", os.getpid(), [GESTO])
    porta.registrar("ficha-b", "outra", os.getpid(), [GESTO])
    return porta


async def _entrar(curto: pathlib.Path, ficha: str, estado: dict[str, Any]) -> _Extensao:
    ext = _Extensao(curto / "mods.sock")
    await asyncio.to_thread(ext.pedir, "mod.ola", {"ficha": ficha})
    assinou = await asyncio.to_thread(
        ext.pedir, "eventos.assinar", {"topicos": ["acessorios.gesto"]})
    assert "result" in assinou, assinou
    ok = await asyncio.to_thread(ext.pedir, "acessorios.estado", estado)
    assert ok.get("result") == {"recebido": True}, ok
    return ext


# -- a porta guarda o estado de CADA extensão e manda o «para» só a uma ------------------


def test_o_agora_e_de_cada_extensao_e_volta_vazio_quando_a_conexao_cai(curto) -> None:
    async def corrida() -> None:
        porta = await _porta(curto, EventBus())
        a = await _entrar(curto, "ficha-a", VIVO)
        b = await _entrar(curto, "ficha-b", {**VIVO, "nivel": 7, "perfil": "Calmo"})
        try:
            assert porta.agora_de("acessorios")["nivel"] == 4, "o último global era o da outra"
            assert porta.agora_de("outra")["perfil"] == "Calmo"
            assert porta.agora_de("ninguem") == estado_vazio_dos_acessorios("ninguem")
        finally:
            a.fechar()
        for _ in range(100):
            if porta.agora_de("acessorios")["ligado"] is False:
                break
            await asyncio.sleep(0.02)
        assert porta.agora_de("acessorios") == estado_vazio_dos_acessorios("acessorios")
        assert porta.agora_de("outra")["nivel"] == 7
        b.fechar()
        await porta.parar()

    asyncio.run(corrida())


def test_o_parar_tudo_chega_so_a_extensao_da_janela(curto) -> None:
    async def corrida() -> None:
        porta = await _porta(curto, EventBus())
        a = await _entrar(curto, "ficha-a", VIVO)
        b = await _entrar(curto, "ficha-b", VIVO)
        try:
            assert porta.parar_tudo("acessorios") is True
            chegou = await asyncio.to_thread(a.esperar_evento, 2.0)
            assert chegou is not None, "a extensão da janela não recebeu o para"
            dados = chegou["params"]["dados"]
            assert chegou["params"]["nome"] == "acessorios.gesto"
            assert dados["gesto"] == "para" and dados["mod"] == "acessorios"
            assert dados["uniq"] is None, "o «Parar tudo» não é de controle nenhum"
            vazou = await asyncio.to_thread(b.esperar_evento, 0.4)
            assert vazou is None, f"a outra extensão recebeu o para da janela: {vazou}"
        finally:
            a.fechar()
            b.fechar()
            await porta.parar()

    asyncio.run(corrida())


def test_o_parar_tudo_sem_a_extensao_conectada_nao_publica(curto) -> None:
    async def corrida() -> None:
        bus = EventBus()
        porta = await _porta(curto, bus)
        try:
            from hefesto_dualsense4unix.core.events import EventTopic

            fila = bus.subscribe(EventTopic.ACESSORIOS_GESTO)
            assert porta.parar_tudo("acessorios") is False
            assert fila.empty()
        finally:
            await porta.parar()

    asyncio.run(corrida())


def test_o_parar_curto_da_janela_confere_o_estado_da_propria_extensao(curto) -> None:
    """O último estado do barramento é da outra extensão: o parar curto confere o da alvo."""
    from tests.unit.test_os_gestos_do_ps_comandam_os_acessorios import _filho, _supervisor

    from hefesto_dualsense4unix.core.events import EventTopic
    from hefesto_dualsense4unix.mods.supervisor import _Vigiada

    async def corrida() -> tuple[bool, bool]:
        bus = EventBus()
        sup = _supervisor(bus, curto)
        processo, marca = await _filho(curto)
        sup._vigiadas["acessorios"] = _Vigiada("acessorios", processo=processo)
        guardado = {**VIVO, "mod": "acessorios"}
        sup.porta.ultimo_estado_de = lambda mod: guardado if mod == "acessorios" else None  # type: ignore[method-assign]
        bus.publish(EventTopic.ACESSORIOS_ESTADO, {**VIVO, "mod": "outra", "ligado": False})
        encerrou = await sup.conferir_o_parar("acessorios")
        for _ in range(100):
            if marca.exists():
                break
            await asyncio.sleep(0.01)
        if processo.returncode is None:
            processo.kill()
        return encerrou, marca.exists()

    encerrou, sinal = asyncio.run(corrida())
    assert encerrou and sinal, "o «Parar tudo» olhou o estado da outra extensão"


# -- o IPC da interface --------------------------------------------------------------------


def _servico(supervisor: Any) -> Any:
    return SimpleNamespace(daemon=SimpleNamespace(_mods_supervisor=supervisor),
                           _mod_do_pedido=IpcHandlersMixin._mod_do_pedido)


def _instalada(lugares: Any, **extra: Any) -> None:
    pasta = lugares.codigo / "acessorios"
    pasta.mkdir(parents=True)
    manifesto = {"id": "acessorios", "nome": "Acessórios", "versao": "0.1", "api": ">=1,<3",  # noqa-acento: chave
                 "licenca": "MIT", "tipos": ["tema"], "tema": {},  # noqa-acento: chave
                 "permissoes": [GESTO], **extra}  # noqa-acento: chave do manifesto
    (pasta / "hefesto-mod.json").write_text(json.dumps(manifesto), encoding="utf-8")


def test_o_ipc_do_agora_sem_servico_de_modificacoes_e_o_estado_vazio() -> None:
    corpo = asyncio.run(IpcHandlersMixin._handle_mods_agora(_servico(None), {"mod": "acessorios"}))
    assert corpo == estado_vazio_dos_acessorios("acessorios")
    with pytest.raises(ValueError, match="mod"):
        asyncio.run(IpcHandlersMixin._handle_mods_agora(_servico(None), {}))


def test_o_ipc_do_parar_recusa_quem_nao_declara_parar_tudo(lar) -> None:  # noqa: F811
    _instalada(lar, agora=["nivel"])
    publicados: list[str] = []
    sup = SimpleNamespace(lugares=lar, porta=SimpleNamespace(parar_tudo=publicados.append))
    with pytest.raises(ValueError, match="não declara o «Parar tudo»"):
        asyncio.run(IpcHandlersMixin._handle_mods_parar_tudo(_servico(sup), {"mod": "acessorios"}))
    assert publicados == []
    with pytest.raises(ValueError, match=r"não está instalada|não"):
        asyncio.run(IpcHandlersMixin._handle_mods_parar_tudo(_servico(sup), {"mod": "nenhuma"}))


# -- a janela -----------------------------------------------------------------------------


class _Ponte:
    """O ``p`` do gesto: ``mods.agora`` devolve o estado do teste; o resto é anotado."""

    def __init__(self, estado: dict[str, Any] | None = None, *, falha: bool = False) -> None:
        self.estado = estado
        self.falha = falha
        self.chamadas: list[tuple[str, dict[str, Any]]] = []

    def resultado(self, metodo: str, **params: Any) -> Any:
        self.chamadas.append((metodo, params))
        if self.falha:
            raise RuntimeError(f"o daemon não respondeu a {metodo}")
        if metodo == "mods.parar_tudo":
            return {"parado": True}
        return {"mod": params.get("mod"), **(self.estado or {})}

    def chamar_detalhado(self, metodo: str, **params: Any) -> tuple[bool, str | None]:
        self.chamadas.append((metodo, params))
        return (not self.falha, "recusado" if self.falha else None)

    def escolher_arquivo(self, *_: Any, **__: Any) -> str | None:
        return None


@pytest.fixture
def janela(lar, ctx, tmp_path, monkeypatch):  # noqa: F811
    """Abre a janela da extensão ``toque`` com o manifesto que o teste pedir."""
    a07 = _a07()
    monkeypatch.setattr(a07, "_AGORA", a07._Agora())

    def abrir(ponte: _Ponte, **extra: Any) -> dict[str, Any]:
        _instalar(a07, ctx, _fonte(tmp_path, permissoes=(GESTO,), extra=extra))
        return a07.configurar_modificacao(ctx, {"v": "toque"}, ponte)

    return a07, abrir


def test_a_coluna_desenha_so_os_pedacos_que_o_manifesto_declara(janela) -> None:
    _, abrir = janela
    carga = abrir(_Ponte(VIVO), agora=["nivel", "aparelhos"])
    html = carga["blocos"]["#mod-janela"]
    assert 'id="mod-agora"' in html and 'data-agora="nivel"' in html
    assert 'data-agora="aparelhos"' in html and 'data-agora="perfil"' not in html, (
        "a coluna trouxe um pedaço que o manifesto não declara")
    coluna = carga["blocos"]["#mod-agora"]
    assert "<b>4</b>" in coluna and coluna.count('class="on"') == 4
    assert "Motor &lt;b&gt;" in coluna, "nome de terceiro escapado"
    assert coluna.count('<div class="ap">') == 2, "um aparelho por linha"


def test_sem_agora_no_manifesto_a_janela_fica_como_era(janela) -> None:
    _, abrir = janela
    ponte = _Ponte(VIVO)
    carga = abrir(ponte)
    assert "ja-agora" not in carga["blocos"]["#mod-janela"]
    assert "#mod-agora" not in carga["blocos"]


def test_extensao_parada_mostra_a_coluna_vazia_sem_numero(janela, ctx) -> None:  # noqa: F811
    a07, abrir = janela
    vazio = {k: v for k, v in estado_vazio_dos_acessorios("toque").items() if k != "mod"}
    coluna = abrir(_Ponte(vazio), agora=["nivel", "perfil", "aparelhos"])["blocos"]["#mod-agora"]
    assert "<b>0</b>" not in coluna and "<b>—</b>" in coluna and 'class="on"' not in coluna
    assert "Desligada" in coluna and '<div class="ap vazio">' in coluna
    assert '<div class="ap">' not in coluna, "a extensão parada não tem aparelho"
    sem_servico = a07.configurar_modificacao(
        ctx, {"v": "toque"}, _Ponte(falha=True))["blocos"]["#mod-agora"]
    assert "<b>—</b>" in sem_servico, "sem resposta do serviço, a coluna inventou um nível"


def test_sem_parar_tudo_no_manifesto_a_janela_nao_tem_o_botao(janela) -> None:
    _, abrir = janela
    html = abrir(_Ponte(VIVO), agora=["nivel"])["blocos"]["#mod-janela"]
    assert "ja-parar" not in html and "parar-tudo-da-modificacao" not in html


def test_o_clique_no_parar_tudo_pede_ao_servico_so_esta_extensao(janela, ctx) -> None:  # noqa: F811
    a07, abrir = janela
    ponte = _Ponte(VIVO)
    html = abrir(ponte, parar_tudo=True)["blocos"]["#mod-janela"]
    assert 'class="ja-parar" data-gesto="parar-tudo-da-modificacao" data-v="toque"' in html
    carga = a07.parar_tudo_da_modificacao(ctx, {"v": "toque"}, ponte)
    assert ("mods.parar_tudo", {"mod": "toque"}) in ponte.chamadas
    assert "Parar tudo" in carga["recado"]
    with pytest.raises(RuntimeError, match="Nada foi parado"):
        a07.parar_tudo_da_modificacao(ctx, {"v": "toque"}, _Ponte(falha=True))


def test_a_pintura_nao_pergunta_ao_servico_no_tique(janela, ctx, monkeypatch) -> None:  # noqa: F811
    """A pintura devolve o que tem; a pergunta sai numa thread, nunca no tique."""
    a07, abrir = janela
    abrir(_Ponte(VIVO), agora=["nivel"])
    lento = _Ponte({**VIVO, "nivel": 9})
    disparos: list[Any] = []
    monkeypatch.setattr(a07.threading, "Thread", lambda **kw: SimpleNamespace(
        start=lambda: disparos.append(kw)))
    a07._AGORA.abrir("toque", lento)
    carga = a07.pacote(ctx)
    assert lento.chamadas == [], "a pintura perguntou ao serviço no próprio tique"
    assert disparos and disparos[0]["target"] == a07._AGORA._corpo
    assert 'data-agora="nivel"' in carga["blocos"]["#mod-agora"]


def test_o_metodo_e_o_gesto_estao_declarados() -> None:
    a07 = _a07()
    assert {"mods.agora", "mods.parar_tudo"} <= a07.METODOS
    assert "parar-tudo-da-modificacao" in a07.SEM_ECO
    sys.path.insert(0, str(pathlib.Path(a07.__file__).parent))
    from hefesto_dualsense4unix.interface.pacotes import camada

    assert camada.CAMADA[("07-lancadores.html", "parar-tudo-da-modificacao")] == camada.ATO


CHROME = pathlib.Path("/usr/bin/google-chrome")


def _o_nivel_depois_dos_cliques(miolo: str, script: str) -> tuple[str, int]:
    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        nav = pw.chromium.launch(executable_path=str(CHROME), args=["--no-sandbox"])
        try:
            pg = nav.new_page()
            pg.set_content(f'<div class="tn-cx" id="mod-janela">{miolo}</div>'
                           f'<script>{script}</script>')
            # Sem a folha da página o degrau não tem tamanho: o clique vai pelo evento do DOM.
            pg.dispatch_event("#mod-janela .ja-degraus i:nth-child(3)", "click")
            pg.dispatch_event("#mod-janela .ja-parar", "click")
            return (pg.inner_text("#mod-janela .ja-nivel b"),
                    pg.locator("#mod-janela .ja-degraus i.on").count())
        finally:
            nav.close()


def test_o_clique_no_parar_tudo_nao_poe_numero_na_coluna_do_servico(janela) -> None:
    """A coluna do serviço mostra o que a extensão deu: o clique nunca põe ali um número.

    O ``comportamento.js`` zerava o nível de toda a página no clique de qualquer ``.ja-parar``
    (era o nível de mentira da janela dos acessórios do desenho, que saiu em 19/10/2026): a janela
    da extensão parada passava a dizer «Nível 0», um número que a extensão não deu. A mordida põe
    de volta um nível de mentira que não olha a coluna do serviço.
    """
    if not CHROME.exists():
        pytest.skip("sem o Chrome do sistema")
    from hefesto_dualsense4unix.interface import desenho_da_experimental as exp

    _, abrir = janela
    vazio = {k: v for k, v in estado_vazio_dos_acessorios("toque").items() if k != "mod"}
    miolo = abrir(_Ponte(vazio), agora=["nivel"], parar_tudo=True)["blocos"]["#mod-janela"]
    assert _o_nivel_depois_dos_cliques(miolo, exp.SCRIPT) == ("—", 0), "o clique pôs um número"
    de_mentira = exp.SCRIPT + """
document.addEventListener('click', function(e){
  var g = e.target.closest('.ja-degraus i');
  if (g) g.classList.add('on');
  if (e.target.closest('.ja-parar')) document.querySelector('.ja-nivel b').textContent = '0';
});"""
    assert _o_nivel_depois_dos_cliques(miolo, de_mentira) != ("—", 0), "a régua não morde"
