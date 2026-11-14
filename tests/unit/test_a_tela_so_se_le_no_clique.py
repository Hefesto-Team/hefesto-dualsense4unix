"""A tela do jogo só se lê no clique (A-TELA-SO-SE-LE-NO-CLIQUE-01).

A captura abre só com o ``tela.ver`` da porta, que a extensão manda no clique de «Ver a tela», e
fecha no ``tela.parar``, no jogo que fecha e na extensão que sai. A assinatura de ``jogo.tela``
sozinha não abre o portal. O install monta o portal da casa e pergunta a tela só com
``--com-tela``. O ``som.tocar`` aceita ``dura_s`` de 0,05 a 5 e corta o som naquela duração.
"""
from __future__ import annotations

import asyncio
import functools
import os
import re
import subprocess
import tempfile
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.core.events import EventBus, EventTopic
from hefesto_dualsense4unix.daemon.subsystems import tato_vivo as tv
from hefesto_dualsense4unix.integrations import tela_do_jogo as tj
from hefesto_dualsense4unix.integrations import transiente_do_jogo as tr
from hefesto_dualsense4unix.mods.manifesto import o_que_a_permissao_deixa
from hefesto_dualsense4unix.mods import porta as modulo_porta
from hefesto_dualsense4unix.mods.porta import CODE_INVALID_PARAMS, CODE_SEM_PERMISSAO, Porta
from tests.unit.test_a_porta_ouve_o_jogo_e_o_microfone import _Cliente

RAIZ = Path(__file__).resolve().parents[2]
INSTALL = (RAIZ / "install.sh").read_text(encoding="utf-8")
DOC = (RAIZ / "docs" / "protocol" / "porta-das-modificacoes.md").read_text(encoding="utf-8")
P = ("aa:bb:cc:00:00:31", "aa:bb:cc:00:00:32", "aa:bb:cc:00:00:33", "aa:bb:cc:00:00:34")
L, A = 64, 36
EXT = tv.PREFIXO_DA_EXTENSAO + "a"


class _PortalDeMentira:
    """A fonte do portal de mentira: cada abertura é o ``SelectSources`` e o ``Start``, cada
    fechamento o ``Close`` da sessão."""

    def __init__(self) -> None:
        self.chamadas: list[str] = []
        self.aberta = False

    def abrir(self) -> bool:
        self.chamadas += ["SelectSources", "Start"]
        self.aberta = True
        return True

    def quadro(self) -> tj.Quadro | None:
        return tj.Quadro(L, A, L * 4, "BGRx", bytes((30, 30, 200, 0)) * (L * A))

    def fechar(self) -> None:
        if self.aberta:
            self.chamadas.append("Close")
        self.aberta = False

    def interromper(self) -> None:
        return None

    def conta(self, nome: str) -> int:
        return self.chamadas.count(nome)


async def _esperar(condicao: Callable[[], bool], segundos: float = 5.0) -> bool:
    for _ in range(int(segundos / 0.02)):
        if condicao():
            return True
        await asyncio.sleep(0.02)
    return bool(condicao())


Roteiro = Callable[[Porta, EventBus, list[_Cliente]], Awaitable[Any]]


def _com_a_porta(portal: _PortalDeMentira, roteiro: Roteiro, *, extensoes: int = 1,
                 permissoes: tuple[str, ...] = ("ler:jogo.tela",)) -> Any:
    async def corrida() -> Any:
        with tempfile.TemporaryDirectory(prefix="tc") as pasta:
            caminho = Path(pasta) / "mods.sock"
            bus = EventBus()
            bus.bind_loop(asyncio.get_running_loop())

            async def escritor(_m: str, _p: dict[str, Any]) -> Any:
                return {"status": "ok"}

            porta = Porta(caminho, bus, escritor=escritor, o_jogo_escreve=lambda _u, _c: False,
                          uniq_do_posto=lambda: P[0], fonte_da_tela=lambda: portal)
            await porta.iniciar()
            clientes: list[_Cliente] = []
            try:
                for i in range(extensoes):
                    porta.registrar(f"ficha-{i}", f"imersao{i}", os.getpid(), list(permissoes))
                    cliente = _Cliente(caminho)
                    clientes.append(cliente)
                    await asyncio.to_thread(cliente.pedir, "mod.ola", {"ficha": f"ficha-{i}"})
                return await roteiro(porta, bus, clientes)
            finally:
                for cliente in clientes:
                    cliente.fechar()
                await porta.parar()

    return asyncio.run(corrida())


async def _pedir(cliente: _Cliente, metodo: str, params: dict[str, Any]) -> dict[str, Any]:
    return await asyncio.to_thread(cliente.pedir, metodo, params)


def test_a_subida_e_a_assinatura_sem_tela_ver_nao_abrem_o_portal() -> None:
    portal = _PortalDeMentira()

    async def roteiro(_porta: Porta, _bus: EventBus, clientes: list[_Cliente]) -> Any:
        await asyncio.sleep(0.4)
        na_subida = list(portal.chamadas)
        aceito = await _pedir(clientes[0], "eventos.assinar", {"topicos": ["jogo.tela"]})
        await asyncio.sleep(1.0)
        return na_subida, aceito

    na_subida, aceito = _com_a_porta(portal, roteiro)
    assert na_subida == []
    assert aceito["result"] == {"assinados": ["jogo.tela"]}
    assert portal.conta("SelectSources") == 0 and portal.conta("Start") == 0


def test_o_tela_ver_abre_uma_vez_e_o_tela_parar_fecha() -> None:
    portal = _PortalDeMentira()

    async def roteiro(_porta: Porta, _bus: EventBus, clientes: list[_Cliente]) -> Any:
        cliente = clientes[0]
        await _pedir(cliente, "eventos.assinar", {"topicos": ["jogo.tela"]})
        visto = await _pedir(cliente, "tela.ver", {})
        evento = await asyncio.wait_for(asyncio.to_thread(cliente.evento), 5)
        await asyncio.sleep(0.5)
        abertas = portal.conta("Start")
        parado = await _pedir(cliente, "tela.parar", {})
        fechou = await _esperar(lambda: portal.conta("Close") == 1)
        await asyncio.sleep(0.5)
        return visto, evento, abertas, parado, fechou

    visto, evento, abertas, parado, fechou = _com_a_porta(portal, roteiro)
    assert visto["result"] == {"status": "ok"}
    assert evento["params"]["nome"] == "jogo.tela"
    assert abertas == 1 and portal.conta("SelectSources") == 1
    assert parado["result"] == {"status": "ok"}
    assert fechou and portal.conta("Start") == 1


def test_o_jogo_que_fecha_fecha_a_captura_e_a_assinatura_nao_a_reabre() -> None:
    portal = _PortalDeMentira()

    async def roteiro(_porta: Porta, bus: EventBus, clientes: list[_Cliente]) -> Any:
        cliente = clientes[0]
        await _pedir(cliente, "eventos.assinar", {"topicos": ["jogo.tela"]})
        await _pedir(cliente, "tela.ver", {})
        aberta = await _esperar(lambda: portal.conta("Start") == 1)
        bus.publish(EventTopic.JOGO_FECHOU, {"chave": "steam:1"})
        fechou = await _esperar(lambda: portal.conta("Close") == 1)
        await _pedir(cliente, "eventos.desassinar", {"topicos": ["jogo.tela"]})
        await _pedir(cliente, "eventos.assinar", {"topicos": ["jogo.tela"]})
        await asyncio.sleep(1.0)
        return aberta, fechou

    aberta, fechou = _com_a_porta(portal, roteiro)
    assert aberta and fechou
    assert portal.conta("Start") == 1


def test_a_extensao_que_sai_fecha_a_captura() -> None:
    portal = _PortalDeMentira()

    async def roteiro(_porta: Porta, _bus: EventBus, clientes: list[_Cliente]) -> Any:
        cliente = clientes[0]
        await _pedir(cliente, "eventos.assinar", {"topicos": ["jogo.tela"]})
        await _pedir(cliente, "tela.ver", {})
        aberta = await _esperar(lambda: portal.conta("Start") == 1)
        cliente.fechar()
        clientes.clear()
        return aberta, await _esperar(lambda: portal.conta("Close") == 1)

    assert _com_a_porta(portal, roteiro) == (True, True)


def test_o_tela_ver_e_um_so_para_a_maquina_e_o_evento_chega_as_quatro() -> None:
    portal = _PortalDeMentira()

    async def roteiro(_porta: Porta, _bus: EventBus, clientes: list[_Cliente]) -> Any:
        for cliente in clientes:
            await _pedir(cliente, "eventos.assinar", {"topicos": ["jogo.tela"]})
        await asyncio.sleep(0.4)
        antes = portal.conta("Start")
        await _pedir(clientes[2], "tela.ver", {})
        await _pedir(clientes[0], "tela.ver", {})
        eventos = await asyncio.gather(*(
            asyncio.wait_for(asyncio.to_thread(c.evento), 5) for c in clientes))
        await asyncio.sleep(0.5)
        return antes, eventos

    antes, eventos = _com_a_porta(portal, roteiro, extensoes=4)
    assert antes == 0
    assert [e["params"]["nome"] for e in eventos] == ["jogo.tela"] * 4
    assert portal.conta("SelectSources") == 1 and portal.conta("Start") == 1


def test_o_tela_ver_pede_a_permissao_da_tela() -> None:
    portal = _PortalDeMentira()

    async def roteiro(_porta: Porta, _bus: EventBus, clientes: list[_Cliente]) -> Any:
        return (await _pedir(clientes[0], "tela.ver", {}),
                await _pedir(clientes[0], "tela.parar", {}))

    ver, parar = _com_a_porta(portal, roteiro, permissoes=("ler:jogo.som",))
    assert ver["error"]["code"] == CODE_SEM_PERMISSAO
    assert parar["error"]["code"] == CODE_SEM_PERMISSAO
    assert portal.chamadas == []


def test_a_doc_e_o_manifesto_dizem_o_clique() -> None:
    assert "| `tela.ver` |" in DOC and "| `tela.parar` |" in DOC
    assert "dura_s" in DOC
    assert "Ver a tela" in o_que_a_permissao_deixa("ler:jogo.tela")


def _bloco_do_install(passo: str) -> str:
    """O ``if`` que chama o passo ``passo`` do install, inteiro."""
    marca = INSTALL.index(f'    step "{passo}"')
    inicio = INSTALL.rindex("\nif ", 0, marca) + 1
    fim = INSTALL.index("\nfi\n", marca) + len("\nfi\n")
    return INSTALL[inicio:fim]


def _rodar_os_passos_da_tela(tmp_path: Path, com_tela: int) -> str:
    falsos = tmp_path / "falsos"
    falsos.mkdir()
    for nome in ("dpkg-query", "dpkg", "sudo"):
        (falsos / nome).write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        (falsos / nome).chmod(0o755)
    script = (
        "set -euo pipefail\n"
        f"COM_TELA={com_tela}\nSKIP_UDEV=0\nDESKTOP_IS_COSMIC=1\nDRY_RUN=1\n"
        "step() { echo \"[$1] $2\"; }\n"
        "_pc_portal_no_cosmic() { return 0; }\n"
        "install_portal_cosmic_da_casa() { echo 'FARIA construir o portal da casa'; }\n"
        "escolher_a_tela_do_jogo() { echo 'FARIA abrir a escolha da tela'; }\n"
        + _bloco_do_install("3f-ter") + _bloco_do_install("3f-quater")
    )
    r = subprocess.run(["bash", "-c", script], capture_output=True, text=True, timeout=15,
                       env={"PATH": f"{falsos}:/usr/bin:/bin"}, check=False)
    assert r.returncode == 0, r.stderr
    return r.stdout


def test_o_install_sem_com_tela_nao_monta_o_portal_nem_pergunta_a_tela(tmp_path: Path) -> None:
    assert _rodar_os_passos_da_tela(tmp_path, 0) == ""


def test_o_install_com_tela_monta_o_portal_e_pergunta_a_tela(tmp_path: Path) -> None:
    saida = _rodar_os_passos_da_tela(tmp_path, 1)
    assert "[3f-ter]" in saida and "construir o portal da casa" in saida
    assert "[3f-quater]" in saida and "abrir a escolha da tela" in saida


def test_a_flag_com_tela_existe_nasce_desligada_e_a_ajuda_a_diz() -> None:
    assert re.search(r"^COM_TELA=0$", INSTALL, re.MULTILINE)
    assert re.search(r"^\s+--com-tela\)\s+COM_TELA=1 ;;$", INSTALL, re.MULTILINE)
    ajuda = INSTALL[:INSTALL.index("\nAJUDA\n")]
    assert "--com-tela" in ajuda


def _fonte_do_som() -> tuple[tv.FonteDeFora, list[Any]]:
    tocados: list[Any] = []

    def tocar(_u: str, recorte: Any) -> bool:
        tocados.append(recorte)
        return True

    fonte = tv.FonteDeFora(tv.Teto(), modo_de=lambda _u: tv.MODO_DUALSENSE,
                           tocar_som=tocar, relogio=lambda: 0.0)
    return fonte, tocados


@pytest.mark.parametrize("dura_s", [0.01, 0.049, 5.01, 60, "1", True])
def test_o_dura_s_fora_da_faixa_recusa(dura_s: Any) -> None:
    fonte, tocados = _fonte_do_som()
    fonte.registrar_som(EXT, "susto", tv.padrao_de(
        {"golpes": [[0, 300, 60, 1.0]]}))

    async def roteiro(_porta: Porta, _bus: EventBus, clientes: list[_Cliente]) -> Any:
        return await _pedir(clientes[0], "som.tocar",
                            {"uniq": P[0], "som": "susto", "volume": 1.0, "dura_s": dura_s})

    resposta = _som_pela_porta(fonte, roteiro)
    assert resposta["error"]["code"] == CODE_INVALID_PARAMS
    assert "dura_s" in resposta["error"]["message"]
    assert tocados == []


def _som_pela_porta(fonte: tv.FonteDeFora, roteiro: Roteiro) -> Any:
    async def corrida() -> Any:
        with tempfile.TemporaryDirectory(prefix="tc") as pasta:
            caminho = Path(pasta) / "mods.sock"

            async def escritor(_m: str, _p: dict[str, Any]) -> Any:
                return {"status": "ok"}

            porta = Porta(caminho, EventBus(), escritor=escritor,
                          o_jogo_escreve=lambda _u, _c: False, uniq_do_posto=lambda: P[0],
                          arbitro=lambda: fonte)
            await porta.iniciar()
            porta.registrar("ficha", "a", os.getpid(), ["escrever:som"])
            cliente = _Cliente(caminho)
            try:
                await asyncio.to_thread(cliente.pedir, "mod.ola", {"ficha": "ficha"})
                return await roteiro(porta, EventBus(), [cliente])
            finally:
                cliente.fechar()
                await porta.parar()

    return asyncio.run(corrida())


@pytest.mark.parametrize("uniq", P)
def test_o_dura_s_corta_o_recorte_do_jogo_em_qualquer_controle(uniq: str) -> None:
    fonte, tocados = _fonte_do_som()
    um_segundo = b"\x10\x00\x10\x00" * tr.TAXA
    fonte.guardar_o_estalo(tr.Transiente(2.0, tr.LADO_CENTRO, 0.5,
                                         recorte=tr.recorte_pronto(um_segundo, 2.0)))

    async def roteiro(_porta: Porta, _bus: EventBus, clientes: list[_Cliente]) -> Any:
        return await _pedir(clientes[0], "som.tocar", {
            "uniq": uniq, "som": "recorte", "volume": 1.0, "t": 2.0, "dura_s": 0.25})

    resposta = _som_pela_porta(fonte, roteiro)
    assert resposta["result"]["status"] == "ok", resposta
    assert len(tocados) == 1 and tocados[0].pronto
    assert tocados[0].duracao_s == pytest.approx(0.25, abs=1e-3)
    assert tocados[0].pcm[-4:] == b"\x00\x00\x00\x00"


def test_o_dura_s_corta_o_recorte_que_ainda_se_completa() -> None:
    fonte, tocados = _fonte_do_som()
    recorte = tr.Recorte(3.0)
    fonte.guardar_o_estalo(tr.Transiente(3.0, tr.LADO_CENTRO, 0.5, recorte=recorte))
    fonte.som(EXT, P[3], tv.SOM_DO_RECORTE, 1.0, 0.0, 3.0, dura_s=0.05)
    assert len(tocados) == 1 and not tocados[0].pronto
    recorte.fechar()
    recorte.pcm = b"\x10\x00\x10\x00" * tr.TAXA
    assert tocados[0].pronto
    assert tocados[0].duracao_s == pytest.approx(0.05, abs=1e-3)


def test_o_dura_s_corta_o_som_registrado_e_sem_ele_o_som_fica_inteiro() -> None:
    fonte, tocados = _fonte_do_som()
    fonte.registrar_som(EXT, "susto", tv.padrao_de({"golpes": [[0, 300, 60, 1.0]]}))
    fonte.som(EXT, P[1], "susto", 1.0, 0.0, dura_s=0.1)
    fonte.som(EXT, P[2], "susto", 1.0, 10.0)
    fonte.som(EXT, P[0], "susto", 1.0, 20.0, dura_s=5.0)
    assert [round(r.duracao_s, 3) for r in tocados] == [0.1, 0.3, 0.3]


class _PortalQueCancela(_PortalDeMentira):
    """A pessoa cancela a escolha do portal: cada abertura é um ``SelectSources`` recusado."""

    def abrir(self) -> bool:
        self.chamadas.append("SelectSources")
        raise tj.EscolhaCanceladaError("a escolha foi cancelada")


def test_a_escolha_cancelada_so_volta_no_clique_seguinte_nunca_na_assinatura(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(modulo_porta, "Captura", functools.partial(tj.Captura, espera=0.2))
    portal = _PortalQueCancela()

    async def roteiro(_porta: Porta, _bus: EventBus, clientes: list[_Cliente]) -> Any:
        cliente = clientes[0]
        await _pedir(cliente, "eventos.assinar", {"topicos": ["jogo.tela"]})
        await _pedir(cliente, "tela.ver", {})
        primeira = await _esperar(lambda: portal.conta("SelectSources") == 1)
        await _pedir(cliente, "eventos.desassinar", {"topicos": ["jogo.tela"]})
        await asyncio.sleep(0.5)
        await _pedir(cliente, "eventos.assinar", {"topicos": ["jogo.tela"]})
        await _pedir(cliente, "eventos.assinar", {"topicos": ["jogo.tela"]})
        await asyncio.sleep(0.8)
        sem_clique = portal.conta("SelectSources")
        await _pedir(cliente, "tela.ver", {})
        no_clique = await _esperar(lambda: portal.conta("SelectSources") == 2)
        await asyncio.sleep(0.5)
        return primeira, sem_clique, no_clique

    primeira, sem_clique, no_clique = _com_a_porta(portal, roteiro)
    assert primeira
    assert sem_clique == 1
    assert no_clique and portal.conta("SelectSources") == 2


def test_o_jogo_que_fecha_antes_da_assinatura_apaga_o_clique() -> None:
    portal = _PortalDeMentira()

    async def roteiro(_porta: Porta, bus: EventBus, clientes: list[_Cliente]) -> Any:
        cliente = clientes[0]
        await _pedir(cliente, "tela.ver", {})
        await asyncio.sleep(0.4)
        bus.publish(EventTopic.JOGO_FECHOU, {"chave": "steam:1"})
        await asyncio.sleep(0.4)
        await _pedir(cliente, "eventos.assinar", {"topicos": ["jogo.tela"]})
        await asyncio.sleep(1.0)
        sem_clique = portal.conta("Start")
        await _pedir(cliente, "tela.ver", {})
        no_clique = await _esperar(lambda: portal.conta("Start") == 1)
        return sem_clique, no_clique

    sem_clique, no_clique = _com_a_porta(portal, roteiro)
    assert sem_clique == 0
    assert no_clique
