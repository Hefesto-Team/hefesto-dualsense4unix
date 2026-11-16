"""A porta liga o Som no corpo e os gatilhos que vibram (16/11/2026).

A-PORTA-LIGA-O-SOM-NO-CORPO-01. O ``corpo.ligar`` pede ao tato vivo, por controle e com prazo
renovável, o Som no corpo com uma força e o padrão dos motores no L2 e no R2 com o tipo e a força.
O motor é o mesmo do perfil (``Passo._levar_o_corpo`` e o ``AtuadorDosMotores``): o pedido soma pelo
mais forte, sai no prazo, e o Modo Nativo e o Steam Input calam como calam os outros canais.

MORDIDAS: tirar o corte do prazo em ``PedidosDoCorpo._vivos`` deixa o corpo tocando depois do
prazo; tirar ``_com_os_pedidos`` de ``Passo._da_receita`` deixa o perfil sem receita calado; tirar
o pedido do ``padrao_de`` de ``atuadores_de_producao`` deixa o L2 mudo.
"""
from __future__ import annotations

import asyncio
import math
import os
import tempfile
from array import array
from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from hefesto_dualsense4unix.core.events import EventBus
from hefesto_dualsense4unix.core.sysfs_leds import norm_mac
from hefesto_dualsense4unix.daemon import state_store
from hefesto_dualsense4unix.daemon.protocolo_do_ipc import CODE_INVALID_PARAMS
from hefesto_dualsense4unix.daemon.subsystems import diario_do_corpo as dc
from hefesto_dualsense4unix.daemon.subsystems import tato_vivo as tv
from hefesto_dualsense4unix.mods.manifesto import o_que_a_permissao_deixa, permissao_valida
from hefesto_dualsense4unix.mods.porta import (
    CODE_O_JOGO_ESCREVE,
    CODE_SEM_PERMISSAO,
    Porta,
)
from hefesto_dualsense4unix.profiles import formas_de_haptica as fh
from tests.unit.test_a_porta_ouve_o_jogo_e_o_microfone import _Cliente

P = tuple(f"aa:bb:cc:00:00:{i:02x}" for i in range(0x81, 0x85))
EXT = tv.PREFIXO_DA_EXTENSAO + "imersao"
EXT_A = tv.PREFIXO_DA_EXTENSAO + "a"
EXT_B = tv.PREFIXO_DA_EXTENSAO + "b"
COM_JOGO = tv.EstadoDoCanal(modo=tv.MODO_XBOX, ha_jogo=True)
COM_JOGO_SONY = tv.EstadoDoCanal(modo=tv.MODO_DUALSENSE, ha_jogo=True)
NO_NATIVO = tv.EstadoDoCanal(modo=tv.MODO_NATIVO, ha_jogo=True)


class _Relogio:
    def __init__(self) -> None:
        self.agora = 100.0

    def __call__(self) -> float:
        return self.agora


def _grave(segundos: float = 0.2) -> bytes:
    quadros = array("h")
    for i in range(round(fh.TAXA * segundos)):
        v = int(32767 * 0.6 * math.sin(2.0 * math.pi * 70 * i / fh.TAXA))
        quadros.extend((v, v))
    return quadros.tobytes()


class _Alto:
    def __init__(self) -> None:
        self.saida: dict[str, list[float]] = {}

    def tocar_o_corpo(self, uniq: str, amostras: Any, _lado: str = "centro") -> Any:
        self.saida.setdefault(uniq, []).extend(amostras)
        return dc.DesfechoDoCorpo(None)


def _passo(relogio: _Relogio) -> tuple[tv.Passo, _Alto]:
    alto = _Alto()
    motor = tv.TatoVivo([])
    motor.de_fora.relogio = relogio
    daemon = SimpleNamespace(_alto_falante_subsystem=alto, store=state_store.StateStore(),
                             _tato_vivo=motor)
    return tv.Passo(daemon, motor), alto


def _tique(passo: tv.Passo, estados: dict[str, tv.EstadoDoCanal]) -> tv.Receita:
    receita = passo._com_os_pedidos(passo.receita_vigente)
    passo.motor.ligado = receita.ligada
    passo.alimentar_o_corpo(_grave())
    passo._levar_o_corpo(receita, tuple(estados), estados.get)
    return receita


def _pico(amostras: list[float]) -> float:
    return max((abs(x) for x in amostras), default=0.0)


def test_os_pedidos_valem_pelo_mais_forte_e_saem_no_prazo() -> None:
    relogio = _Relogio()
    pedidos = tv.PedidosDoCorpo(relogio)
    pedidos.pedir(EXT_A, P[0], tv.PedidoDoCorpo(0.4, "tranco", 0.3), 500)
    pedidos.pedir(EXT_B, P[0].upper(), tv.PedidoDoCorpo(0.8, "onda", 0.9), 2000)
    assert pedidos.de(P[0]) == tv.PedidoDoCorpo(0.8, "onda", 0.9)
    assert pedidos.de(P[1]) is None
    assert pedidos.pedem() == (True, True)
    relogio.agora += 1.0
    assert pedidos.de(P[0]) == tv.PedidoDoCorpo(0.8, "onda", 0.9)
    relogio.agora += 1.5
    assert pedidos.de(P[0]) is None, "o pedido que não se renovou ficou depois do prazo"
    assert pedidos.pedem() == (False, False)


def test_renovar_segura_o_pedido_e_o_vazio_solta() -> None:
    relogio = _Relogio()
    pedidos = tv.PedidosDoCorpo(relogio)
    for _ in range(5):
        pedidos.pedir(EXT_A, P[2], tv.PedidoDoCorpo(som_no_corpo=0.5), 400)
        relogio.agora += 0.3
    assert pedidos.de(P[2]) is not None
    pedidos.pedir(EXT_A, P[2], tv.PedidoDoCorpo(), 400)
    assert pedidos.de(P[2]) is None


@pytest.mark.parametrize("ruim", [
    {"ate_ms": 0}, {"ate_ms": 10_001}, {"pedido": tv.PedidoDoCorpo(1.5)},
    {"pedido": tv.PedidoDoCorpo(0.5, "inventado", 0.5)},
])
def test_o_pedido_fora_da_forma_e_recusado(ruim: dict[str, Any]) -> None:
    pedidos = tv.PedidosDoCorpo(_Relogio())
    with pytest.raises(ValueError):
        pedidos.pedir(EXT_A, P[0], ruim.get("pedido", tv.PedidoDoCorpo(0.5)),
                      ruim.get("ate_ms", 100))


def test_a_extensao_que_sai_leva_os_proprios_pedidos() -> None:
    fonte = tv.FonteDeFora(tv.Teto(), relogio=_Relogio())
    fonte.corpo.pedir(EXT, P[0], tv.PedidoDoCorpo(0.6), 1000)
    fonte.corpo.pedir(EXT_B, P[1], tv.PedidoDoCorpo(0.6), 1000)
    fonte.esquecer(EXT)
    assert fonte.corpo.de(P[0]) is None and fonte.corpo.de(P[1]) is not None


@pytest.mark.parametrize("estados", [
    dict.fromkeys(P, COM_JOGO),
    dict(zip(P, (COM_JOGO, COM_JOGO_SONY, COM_JOGO, COM_JOGO_SONY), strict=True)),
    {P[3]: COM_JOGO_SONY},
])
def test_o_pedido_liga_o_corpo_sem_receita_no_perfil_e_solta_no_prazo(
    estados: dict[str, tv.EstadoDoCanal],
) -> None:
    relogio = _Relogio()
    passo, alto = _passo(relogio)
    passo.receita_vigente = tv.DESLIGADA
    for uniq in estados:
        passo.motor.de_fora.corpo.pedir(EXT, uniq, tv.PedidoDoCorpo(0.5), 1000)

    receita = _tique(passo, estados)

    assert receita.ligada and receita.som_no_corpo_escolhido
    assert passo._o_tato_quer_o_som()
    assert all(_pico(alto.saida.get(u, [])) > 0.0 for u in estados), "o corpo pedido não tocou"
    relogio.agora += 1.5
    alto.saida.clear()
    assert not _tique(passo, estados).ligada
    assert not any(alto.saida.values()), "o corpo seguiu depois do prazo"


def test_o_tique_do_laco_liga_o_tato_pelo_pedido_e_desliga_no_prazo(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    relogio = _Relogio()
    passo, _alto = _passo(relogio)
    monkeypatch.setattr(passo, "receita_de_agora", lambda _agora: tv.DESLIGADA)
    passo._da_receita(relogio.agora)
    assert not passo.motor.ligado
    passo.motor.de_fora.corpo.pedir(EXT, P[0], tv.PedidoDoCorpo(tipo="batida",
                                                               forca_dos_motores=0.5), 1000)
    passo._da_receita(relogio.agora)
    assert passo.motor.ligado, "o pedido da extensão não ligou o tato sem receita no perfil"
    relogio.agora += 1.5
    passo._da_receita(relogio.agora)
    assert not passo.motor.ligado


def test_o_pedido_soma_pelo_mais_forte_com_o_corpo_do_perfil() -> None:
    relogio = _Relogio()
    passo, alto = _passo(relogio)
    passo.receita_vigente = tv.Receita(som_no_corpo_escolhido=True)
    passo.motor.escolhas = {norm_mac(P[0]): fh.SOM_NO_CORPO}
    passo.motor.de_fora.corpo.pedir(EXT, P[0], tv.PedidoDoCorpo(0.2), 1000)
    passo.motor.de_fora.corpo.pedir(EXT, P[1], tv.PedidoDoCorpo(0.2), 1000)
    _tique(passo, {P[0]: COM_JOGO, P[1]: COM_JOGO})
    assert _pico(alto.saida[P[0]]) > 2.0 * _pico(alto.saida[P[1]]), (
        "o pedido mais fraco baixou o corpo que o perfil liga")


@pytest.mark.parametrize("modo", [tv.MODO_NATIVO, "steam_input"])
def test_no_modo_que_cala_o_pedido_nao_toca(modo: str) -> None:
    passo, alto = _passo(_Relogio())
    passo.receita_vigente = tv.DESLIGADA
    passo.motor.de_fora.corpo.pedir(EXT, P[0], tv.PedidoDoCorpo(1.0), 1000)
    _tique(passo, {P[0]: tv.EstadoDoCanal(modo=modo, ha_jogo=True)})
    assert not alto.saida.get(P[0])


def test_sem_jogo_o_corpo_pedido_nao_toca() -> None:
    passo, alto = _passo(_Relogio())
    passo.receita_vigente = tv.DESLIGADA
    estados = dict(zip(P, (tv.EstadoDoCanal(modo=tv.MODO_XBOX, ha_jogo=False),
                           tv.EstadoDoCanal(modo=tv.MODO_DUALSENSE, ha_jogo=False)) * 2,
                       strict=True))
    for uniq in estados:
        passo.motor.de_fora.corpo.pedir(EXT, uniq, tv.PedidoDoCorpo(1.0), 1000)
    _tique(passo, estados)
    assert not any(alto.saida.values()), "o corpo pedido tocou sem jogo aberto"


def test_na_bateria_longa_o_pedido_cala_o_corpo_e_desce_os_motores_so_naquele_controle(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    economia = norm_mac(P[1])
    monkeypatch.setattr(tv, "_controle_na_economia", lambda uniq: norm_mac(uniq) == economia)
    relogio = _Relogio()
    passo, alto = _passo(relogio)
    passo.receita_vigente = tv.DESLIGADA
    estados = dict(zip(P, (COM_JOGO, COM_JOGO_SONY) * 2, strict=True))
    for uniq in estados:
        passo.motor.de_fora.corpo.pedir(EXT, uniq, tv.PedidoDoCorpo(1.0), 1000)
    _tique(passo, estados)
    assert not alto.saida.get(P[1]), "o corpo pedido tocou na Bateria longa"
    assert all(_pico(alto.saida.get(u, [])) > 0.0 for u in P if u != P[1])

    atuador, motor = _motores(relogio)
    for uniq in P:
        motor.de_fora.corpo.pedir(EXT, uniq, tv.PedidoDoCorpo(tipo="tranco",
                                                             forca_dos_motores=0.9), 1000)
    assert atuador._forca_de(P[1]) == pytest.approx(tv.FORCA_NA_ECONOMIA)
    assert [atuador._forca_de(u) for u in P if u != P[1]] == [pytest.approx(0.9)] * 3


def _motores(relogio: _Relogio, padroes: dict[str, str] | None = None
             ) -> tuple[tv.AtuadorDosMotores, tv.TatoVivo]:
    motor = tv.TatoVivo([])
    motor.de_fora.relogio = relogio
    motor.escolhas_de_imersao = padroes or {}
    daemon = SimpleNamespace(_tato_vivo=motor, store=state_store.StateStore())
    atuador = next(a for a in tv.atuadores_de_producao(daemon)
                   if isinstance(a, tv.AtuadorDosMotores))
    return atuador, motor


def test_o_pedido_dos_gatilhos_toca_o_padrao_no_l2_com_a_forca_pedida() -> None:
    relogio = _Relogio()
    atuador, motor = _motores(relogio)
    aperto = tv.Evento(relogio.agora, P[0], tv.TIPO_DEDO, tv.LADO_ESQUERDO, 1.0)
    assert not atuador.responde_a(aperto, tv.DESLIGADA)
    motor.de_fora.corpo.pedir(EXT, P[0], tv.PedidoDoCorpo(tipo="tranco", forca_dos_motores=0.7),
                              1000)
    assert atuador.responde_a(aperto, tv.DESLIGADA)
    assert atuador._forca_de(P[0]) == pytest.approx(0.7)
    relogio.agora += 1.5
    assert not atuador.responde_a(aperto, tv.DESLIGADA), "o L2 seguiu vibrando depois do prazo"


def test_o_padrao_do_perfil_segue_valendo_e_a_forca_e_a_mais_forte() -> None:
    relogio = _Relogio()
    atuador, motor = _motores(relogio, {norm_mac(P[0]): "onda"})
    motor.de_fora.corpo.pedir(EXT, P[0], tv.PedidoDoCorpo(tipo="tranco", forca_dos_motores=0.3),
                              1000)
    assert atuador._padrao_de(P[0]) == "onda"
    assert atuador._forca_de(P[0]) == pytest.approx(1.0)


def test_a_permissao_nova_tem_frase_propria() -> None:
    assert permissao_valida("escrever:corpo")
    assert o_que_a_permissao_deixa("escrever:corpo") != "escrever:corpo"


def _pela_porta(fonte: tv.FonteDeFora, roteiro: Callable[..., Any],
                permissoes: list[str]) -> Any:
    async def corrida() -> Any:
        with tempfile.TemporaryDirectory(prefix="pc") as pasta:
            caminho = Path(pasta) / "mods.sock"

            async def escritor(_m: str, _p: dict[str, Any]) -> Any:
                return {"status": "ok"}

            porta = Porta(caminho, EventBus(), escritor=escritor,
                          o_jogo_escreve=lambda _u, _c: False, uniq_do_posto=lambda: P[0],
                          arbitro=lambda: fonte)
            await porta.iniciar()
            porta.registrar("ficha", "imersao", os.getpid(), permissoes)
            cliente = _Cliente(caminho)
            try:
                await asyncio.to_thread(cliente.pedir, "mod.ola", {"ficha": "ficha"})

                async def pedir(metodo: str, params: dict[str, Any]) -> dict[str, Any]:
                    return await asyncio.to_thread(cliente.pedir, metodo, params)

                return await roteiro(pedir)
            finally:
                cliente.fechar()
                await porta.parar()

    return asyncio.run(corrida())


def test_a_porta_leva_o_pedido_ao_tato_vivo_por_controle() -> None:
    fonte = tv.FonteDeFora(tv.Teto(), modo_de=lambda _u: tv.MODO_XBOX, relogio=_Relogio())

    async def roteiro(pedir: Callable[..., Any]) -> list[Any]:
        return [
            await pedir("corpo.ligar", {"uniq": P[1], "som_no_corpo": 0.6,
                                        "gatilhos": {"tipo": "tranco", "forca": 0.5},
                                        "ate_ms": 2000}),
            await pedir("corpo.ligar", {"uniq": P[2], "som_no_corpo": 0.4, "ate_ms": 2000}),
            await pedir("corpo.ligar", {"uniq": P[1], "som_no_corpo": 2, "ate_ms": 2000}),
            await pedir("corpo.ligar", {"uniq": P[1], "som_no_corpo": 0.5}),
            await pedir("corpo.ligar", {"uniq": P[1], "gatilhos": {"tipo": "x", "forca": 1},
                                        "ate_ms": 100}),
            await pedir("corpo.ligar", {"som_no_corpo": 0.5, "ate_ms": 100}),
            [fonte.corpo.de(u) for u in P[:3]],
        ]

    *respostas, vistos = _pela_porta(fonte, roteiro, ["escrever:corpo"])
    assert [r.get("result") for r in respostas[:2]] == [{"status": "ok"}] * 2
    assert [r["error"]["code"] for r in respostas[2:]] == [CODE_INVALID_PARAMS] * 4
    assert vistos == [None, tv.PedidoDoCorpo(0.6, "tranco", 0.5), tv.PedidoDoCorpo(0.4)]


def test_a_porta_recusa_sem_a_permissao() -> None:
    fonte = tv.FonteDeFora(tv.Teto(), modo_de=lambda _u: tv.MODO_XBOX, relogio=_Relogio())

    async def roteiro(pedir: Callable[..., Any]) -> dict[str, Any]:
        return await pedir("corpo.ligar", {"uniq": P[0], "som_no_corpo": 0.5, "ate_ms": 500})

    resposta = _pela_porta(fonte, roteiro, ["escrever:vibracao", "escrever:haptica"])
    assert resposta["error"]["code"] == CODE_SEM_PERMISSAO
    assert fonte.corpo.de(P[0]) is None


@pytest.mark.parametrize("modo", [tv.MODO_NATIVO, "steam_input"])
def test_no_modo_que_cala_a_porta_recusa_com_o_motivo(modo: str) -> None:
    fonte = tv.FonteDeFora(tv.Teto(), modo_de=lambda _u: modo, relogio=_Relogio())

    async def roteiro(pedir: Callable[..., Any]) -> dict[str, Any]:
        return await pedir("corpo.ligar", {"uniq": P[0], "som_no_corpo": 0.5, "ate_ms": 500})

    resposta = _pela_porta(fonte, roteiro, ["escrever:corpo"])
    assert resposta["error"]["code"] == CODE_O_JOGO_ESCREVE
    assert resposta["error"]["data"]["modo"] == modo
    assert "fala direto com o controle" in resposta["error"]["message"]
    assert fonte.corpo.de(P[0]) is None


def test_a_extensao_que_fecha_a_conexao_solta_o_corpo() -> None:
    fonte = tv.FonteDeFora(tv.Teto(), modo_de=lambda _u: tv.MODO_DUALSENSE, relogio=_Relogio())

    async def roteiro(pedir: Callable[..., Any]) -> dict[str, Any]:
        return await pedir("corpo.ligar", {"uniq": P[3], "som_no_corpo": 1, "ate_ms": 5000})

    assert _pela_porta(fonte, roteiro, ["escrever:corpo"])["result"] == {"status": "ok"}
    assert fonte.corpo.de(P[3]) is None, "a extensão saiu e o corpo pedido ficou"
