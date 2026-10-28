"""O-GESTO-QUE-PEDE-O-P1-RESPONDE-QUANDO-ELE-EXISTE-01 — o desfecho de verdade.

A bancada é a do P1 que nasce pelo fio (o `Daemon` real, o `CoopManager` real, o fio de
nascimento e o broker de mentira de 2 s), com o P1 dono de um endereço forjado, para que
a máscara dele se escolha. Três pontas:

1. o `gamepad.mask.set` (e o PS + L3, pelo mesmo escritor) responde depois do pad, e o
   perfil só recebe o modo que ficou de pé;
2. o pedido igual em voo se junta ao primeiro, e o que segue o pad roda uma vez, depois;
3. o teto da interface dos dois métodos sai do prazo do daemon, de uma constante só.

Nenhum endereço real: faixa forjada ``aa:bb:cc`` com os octetos 4 e 5 zerados.

NOTA DATADA, 27/10/2026 (O-MODO-UNICO-VALE-PARA-TODOS-OS-CONTROLES-01): a máscara é o
modo único. Saíram o registro por aparelho e a escolha que esperava no registro enquanto
outro P1 nascia; o que se mede é o par que o perfil recebe pelo escritor único.
"""

from __future__ import annotations

import asyncio
import inspect
import time
from collections.abc import Callable, Coroutine, Iterator
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest

from hefesto_dualsense4unix.app import ipc_bridge
from hefesto_dualsense4unix.daemon import protocolo_do_ipc
from hefesto_dualsense4unix.daemon.subsystems import external_mask as em
from hefesto_dualsense4unix.daemon.subsystems import gamepad as gp
from hefesto_dualsense4unix.daemon.subsystems import hotkey
from hefesto_dualsense4unix.integrations import virtual_pad as vp
from hefesto_dualsense4unix.utils import xdg_paths
from tests.unit.test_o_p1_que_nasce_fora_do_tique_nasce_no_fio_de_nascimento import (
    _BROKER_S,
    _TIQUE_S,
    _ate,
    _Ipc,
    _Pad,
    _tique,
    _tique_sem_dormir,
    mesa,
)

__all__ = ["mesa"]

_P1 = "aabbcc000001"
_PEDIDAS = ("xbox", "nintendo")


@pytest.fixture(autouse=True)
def _lar(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """O `config_dir` num diretório de mentira, novo a cada teste."""
    monkeypatch.setattr(xdg_paths, "config_dir", lambda ensure=False: tmp_path)
    yield


@pytest.fixture
def bancada(mesa: SimpleNamespace, monkeypatch: pytest.MonkeyPatch) -> SimpleNamespace:
    """A mesa do fio com o P1 dono de `_P1`, de pé num pad DualSense velho."""
    monkeypatch.setattr(mesa.daemon.controller, "primary_uniq", _P1, raising=False)
    original = vp.make_virtual_pad

    def _fabrica(flavor: Any, **kwargs: Any) -> Any:
        """O P1 (o dono de `_P1`) espera o broker de mentira e veste a máscara efetiva."""
        if kwargs.get("identity") == _P1:
            flavor = em.mascara_efetiva(_P1, flavor)
            kwargs = {**kwargs, "identity": None}
        return original(flavor, **kwargs)

    monkeypatch.setattr(vp, "make_virtual_pad", _fabrica)
    gravadas: list[tuple[str | None, Any]] = []

    def _gravar(modo: str, **kw: Any) -> str:
        pad = mesa.daemon._gamepad_device
        mesa.gravados.append((modo, pad))
        gravadas.append((kw.get("mascara"), pad))
        return "Bancada"

    monkeypatch.setattr(mesa.daemon, "gravar_o_modo_escolhido", _gravar)
    tabelas: list[Any] = []
    monkeypatch.setattr(mesa.daemon, "_devolver_as_tabelas_do_perfil",
                        lambda: tabelas.append(mesa.daemon._gamepad_device))
    velho = _Pad(None, "dualsense", vp.CAMINHO_DUALSENSE, None)
    mesa.daemon._gamepad_device = velho
    mesa.daemon.config.gamepad_emulation_enabled = True
    return SimpleNamespace(m=mesa, velho=velho, gravadas=gravadas, tabelas=tabelas)


def _o_p1_novo(b: SimpleNamespace) -> Any:
    """O pad que o broker de mentira entregou ao P1, já instalado, ou ``None``."""
    novo = b.m.estado.pads.get("None")
    atual = b.m.daemon._gamepad_device
    return atual if atual is not None and atual is novo else None


def _no_laco(
    b: SimpleNamespace, pedido: Callable[[], Coroutine[Any, Any, Any]],
) -> tuple[Any, float]:
    """O pedido no mesmo laço do asyncio que roda o tique, como no daemon."""

    async def _correr() -> tuple[Any, float]:
        parar = asyncio.Event()

        async def _laco() -> None:
            while not parar.is_set():
                _tique_sem_dormir(b.m)
                await asyncio.sleep(_TIQUE_S)

        laco = asyncio.create_task(_laco())
        await asyncio.sleep(_TIQUE_S)
        inicio = time.monotonic()
        try:
            resposta = await pedido()
        finally:
            gasto = time.monotonic() - inicio
            parar.set()
            await laco
        return resposta, gasto

    return asyncio.run(_correr())


def _mascara_pela_ipc(b: SimpleNamespace, flavor: str) -> tuple[Any, float]:
    ipc = _Ipc(b.m.daemon)
    cast(Any, ipc).store = None
    return _no_laco(b, lambda: ipc._handle_gamepad_mask_set({"flavor": flavor}))


@pytest.mark.parametrize("pedida", _PEDIDAS)
def test_o_modo_pela_ipc_diz_falhou_e_nao_grava(
    bancada: SimpleNamespace, pedida: str,
) -> None:
    """A fábrica do P1 demora e falha: a resposta é «falhou», e o perfil não muda."""
    bancada.m.estado.falhar = True
    resposta, gasto = _mascara_pela_ipc(bancada, pedida)
    assert gasto >= _BROKER_S, f"o modo respondeu antes do desfecho ({gasto * 1000:.0f} ms)"
    assert resposta["status"] == "failed" and resposta["enabled"] is False, resposta
    assert resposta["motivo"] == "aparelho_nao_vestiu", resposta
    assert bancada.gravadas == [], "o perfil guardou o modo que não vestiu"


@pytest.mark.parametrize("pedida", _PEDIDAS)
def test_o_modo_pela_ipc_responde_depois_do_pad_vestido(
    bancada: SimpleNamespace, pedida: str,
) -> None:
    resposta, gasto = _mascara_pela_ipc(bancada, pedida)
    novo = _o_p1_novo(bancada)
    assert novo is not None and novo.flavor == pedida, "o P1 não nasceu no modo pedido"
    assert gasto >= _BROKER_S, f"o modo respondeu antes do pad ({gasto * 1000:.0f} ms)"
    assert resposta["status"] == "ok" and resposta["flavor"] == pedida, resposta
    assert bancada.gravadas == [(pedida, novo)], (
        "o perfil guarda o modo uma vez, depois de o pad existir", bancada.gravadas)


@pytest.mark.parametrize("falha", [False, True], ids=["nasce", "falha"])
def test_o_ps_l3_grava_quando_o_p1_existe(bancada: SimpleNamespace, falha: bool) -> None:
    """O gesto espera o desfecho no laço, e o perfil só recebe o modo que ficou de pé."""
    bancada.m.estado.falhar = falha
    _no_laco(bancada, hotkey.build_next_mask_callback(bancada.m.daemon))
    _tique(bancada.m)
    if falha:
        assert bancada.gravadas == [], "o modo que não vestiu foi ao perfil"
    else:
        novo = _o_p1_novo(bancada)
        assert novo is not None and novo.flavor == "xbox"
        assert bancada.gravadas == [("xbox", novo)], bancada.gravadas


@pytest.mark.parametrize("ponte", [hotkey.PONTE_XBOX, hotkey.PONTE_DUALSENSE])
def test_o_ps_r3_repetido_em_voo_grava_o_modo_uma_vez_depois_do_pad(
    bancada: SimpleNamespace, ponte: str,
) -> None:
    """D-2510-O-PEDIDO-IGUAL-EM-VOO-SE-JUNTA-AO-PRIMEIRO."""
    if ponte == hotkey.PONTE_DUALSENSE:
        bancada.velho.caminho = vp.CAMINHO_XBOX
        bancada.velho.flavor = "xbox"
    hotkey._aplicar_ponte(bancada.m.daemon, ponte)
    _tique(bancada.m)
    assert gp.o_p1_que_nasce(bancada.m.daemon) is not None, "o primeiro pedido não está em voo"
    hotkey._aplicar_ponte(bancada.m.daemon, ponte)
    assert bancada.m.gravados == [], (
        "o pedido repetido gravou o modo antes de o pad existir", bancada.m.gravados)
    assert bancada.tabelas == [], "as tabelas do perfil voltaram antes de o pad existir"
    _ate(bancada.m, lambda: _o_p1_novo(bancada) is not None)
    _tique(bancada.m)
    novo = _o_p1_novo(bancada)
    assert len(bancada.m.estado.pedidos) == 1, "o pedido igual pediu outro pad"
    assert bancada.m.gravados == [("gamepad", novo)], bancada.m.gravados
    assert bancada.tabelas == [novo], bancada.tabelas


def test_dois_pedidos_iguais_pela_ipc_esperam_o_mesmo_pad(bancada: SimpleNamespace) -> None:
    """O duplo clique: as duas respostas dizem o desfecho, e o que segue roda uma vez."""
    bancada.m.daemon._gamepad_device = None
    bancada.m.daemon.config.gamepad_emulation_enabled = False
    ipc = _Ipc(bancada.m.daemon)
    params = {"enabled": True, "caminho": "xbox", "origin": "manual"}

    async def _dois() -> list[Any]:
        primeiro = asyncio.ensure_future(ipc._handle_gamepad_emulation_set(dict(params)))
        await asyncio.sleep(2 * _TIQUE_S)
        segundo = asyncio.ensure_future(ipc._handle_gamepad_emulation_set(dict(params)))
        return list(await asyncio.gather(primeiro, segundo))

    respostas, gasto = _no_laco(bancada, _dois)
    novo = _o_p1_novo(bancada)
    assert novo is not None and len(bancada.m.estado.pedidos) == 1
    assert gasto >= _BROKER_S, "uma das respostas veio antes do pad"
    assert all(r["status"] == "ok" and r["enabled"] is True for r in respostas), respostas
    assert bancada.m.gravados == [("gamepad", novo)], bancada.m.gravados
    assert bancada.tabelas == [novo], bancada.tabelas


@pytest.mark.parametrize("rota", ["gamepad.emulation.set", "gamepad.mask.set"])
def test_o_teto_da_interface_e_o_prazo_do_daemon_com_folga(rota: str) -> None:
    teto = getattr(protocolo_do_ipc, "TETO_DO_GESTO_QUE_PEDE_O_P1_S", None)
    prazo = getattr(protocolo_do_ipc, "PRAZO_DO_P1_QUE_NASCE_S", None)
    assert teto is not None and prazo is not None, "o prazo e o teto não moram juntos"
    assert getattr(gp, "PRAZO_DO_P1_QUE_NASCE_S", None) is prazo, "o daemon espera por outro número"
    espera = inspect.signature(gp.esperar_o_p1_que_nasce).parameters["prazo_s"].default
    assert espera == prazo
    assert ipc_bridge.TETOS[rota] == teto > prazo, (
        f"{rota}: a interface desiste aos {ipc_bridge.TETOS[rota]} s, e o daemon "
        f"espera o P1 por {prazo} s")



@pytest.mark.parametrize("modo", ["gamepad", "desktop", "native"])
def test_a_transicao_de_modo_espera_cada_passo_pelo_teto_dele(
    monkeypatch: pytest.MonkeyPatch, modo: str,
) -> None:
    """O `apply_mode` (o dono da sequência) dá a cada passo o teto do método, e o
    `gamepad.emulation.set` espera o P1 que nasce como a ponte.

    Mordida: devolva o `timeout_s=MODE_IPC_TIMEOUT_S` ao `apply_mode`, e o pedido do P1
    desiste aos 2 s, antes do prazo do daemon.
    """
    from hefesto_dualsense4unix.app.actions import mode_transition as mt

    chamadas: list[tuple[str, Any]] = []
    monkeypatch.setattr(mt, "call_async", lambda metodo, _p, _ok, _err, timeout_s=None:
                        chamadas.append((metodo, timeout_s)))
    mt.apply_mode(modo, on_done=lambda _r: False, on_fail=lambda _e: False)
    assert chamadas, "a transição não despachou nada"
    for metodo, prazo in chamadas:
        assert prazo == ipc_bridge.teto(metodo), (
            f"{metodo}: a transição espera {prazo} s, e a ponte declara "
            f"{ipc_bridge.teto(metodo)} s")
    if modo == "gamepad":
        assert dict(chamadas)["gamepad.emulation.set"] == (
            protocolo_do_ipc.TETO_DO_GESTO_QUE_PEDE_O_P1_S)
