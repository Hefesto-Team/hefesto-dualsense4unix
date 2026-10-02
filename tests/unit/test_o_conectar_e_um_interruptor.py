"""O «Conectar» é um interruptor — O-CONECTAR-E-UM-INTERRUPTOR-01."""

from __future__ import annotations

import asyncio
import re
import threading
import time
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest


RAIZ = Path(__file__).resolve().parents[2]
INTERFACE = RAIZ / "src" / "hefesto_dualsense4unix" / "interface"
FIO_DA_CENTRAL = "hefesto-central-mover"


class Parada:
    """Segura o fio da central quando o relógio de mentira chega a um instante."""


    def _durante(self) -> None:
        if threading.current_thread().name != FIO_DA_CENTRAL:
            return
        ate = self.ate
        if ate is None or self.relogio.agora < ate:
            return
        self.ate = None
        self.parou.set()
        self._siga.wait(30.0)
        self._siga.clear()

    def segurar_em(self, instante: float) -> None:
        self.parou.clear()
        self.ate = instante

    def seguir(self) -> None:
        self._siga.set()

    def soltar(self) -> None:
        self.ate = None
        self._siga.set()


def aos(ctx: Any, segundos: float) -> Any:
    """O que a central publica ``segundos`` depois do começo: o ``quando`` dos"""
    from hefesto_dualsense4unix.interface.pacotes import Contexto

    estado = dict(ctx.state)
    central = dict(estado["radio_central"])
    central["movimentos"] = [dict(m, quando=float(m["quando"]) - segundos)
                             for m in central.get("movimentos") or ()]
    if isinstance(central.get("busca"), dict):
        busca = central["busca"]
        central["busca"] = dict(busca, desde=busca["desde"] - segundos,
                                ate=busca["ate"] - segundos)
    estado["radio_central"] = central
    return Contexto(state=estado, conectados=ctx.conectados, mesa=ctx.mesa)


def nao_conectou(cena: dict[str, Any]) -> list[tuple[str, str]]:
    return [(str(a["lugar"]), str(a.get("aparelho") or "")) for a in cena["aparelhos"]
            if a.get("nao_conectou")]


def _folha(fonte: str, prefixo: str) -> dict[str, dict[str, str]]:
    """As regras ``.cadeado…`` de uma folha, por seletor, sem o ``prefixo``."""
    regras: dict[str, dict[str, str]] = {}
    for seletor, corpo in re.findall(r"^\s*(" + re.escape(prefixo) + r"\.cadeado[^{]*)\{([^}]*)\}",
                                     fonte, re.M):
        chave = seletor[len(prefixo):].strip()
        regras[chave] = dict(
            (p.split(":", 1)[0].strip(), p.split(":", 1)[1].strip())
            for p in corpo.split(";") if ":" in p)
    return regras


def test_a_peca_e_a_do_modo_freestyle() -> None:
    """A folha ``.cadeado`` da seção do rádio tem os mesmos valores da aba"""
    jogar = _folha((INTERFACE / "aba01.py").read_text(encoding="utf-8"), "")
    radio = _folha((INTERFACE / "aba08.py").read_text(encoding="utf-8"), ".radio ")
    assert set(jogar) == {".cadeado", ".cadeado .p", ".cadeado.ligada", ".cadeado.ligada .p"}
    assert radio == jogar
    assert jogar[".cadeado"]["height"] == "26px"


class _JanelaQueDorme:
    def fechar(self) -> None:
        time.sleep(2.0)


class _CentralQueDemora:
    """A central de mentira cujo ``fechar`` da janela dorme 2 s."""

    def __init__(self) -> None:
        self.janela = _JanelaQueDorme()

    def ligar_a_busca(self, ligada: bool, destino: str | None = None) -> dict[str, Any]:
        if not ligada:
            self.janela.fechar()
        return {"status": "ok", "busca": None}


@pytest.mark.asyncio
async def test_o_verbo_nao_segura_o_laco_do_servico() -> None:
    """Uma tarefa do laço que acorda a cada 10 ms continua rodando durante o"""
    from hefesto_dualsense4unix.daemon.ipc_handlers import IpcHandlersMixin

    class _Daemon(IpcHandlersMixin):
        pass

    eu = _Daemon()
    eu.daemon = SimpleNamespace(_central_do_radio=_CentralQueDemora())  # type: ignore[attr-defined]
    voltas = 0

    async def laco() -> None:
        nonlocal voltas
        while True:
            await asyncio.sleep(0.01)
            voltas += 1

    tarefa = asyncio.create_task(laco())
    try:
        await asyncio.sleep(0.05)
        antes = voltas
        resposta = await eu._handle_radio_busca_set({"ligada": False})
        durante = voltas - antes
    finally:
        tarefa.cancel()
    assert resposta == {"status": "ok", "busca": None}
    assert durante >= 50, f"o laço deu {durante} voltas em 2 s"


@pytest.mark.parametrize("params", [{}, {"ligada": "sim"}, {"ligada": True, "destino": 7}])
def test_o_verbo_recusa_o_que_nao_e_o_contrato(params: dict[str, Any]) -> None:
    """``ligada`` é booleano e ``destino``, quando vem, é o endereço."""
    from hefesto_dualsense4unix.daemon.ipc_handlers import IpcHandlersMixin

    class _Daemon(IpcHandlersMixin):
        pass

    eu = _Daemon()
    eu.daemon = SimpleNamespace(_central_do_radio=_CentralQueDemora())  # type: ignore[attr-defined]
    with pytest.raises(ValueError):
        asyncio.run(eu._handle_radio_busca_set(params))
