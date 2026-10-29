"""Os deslizantes da janela da extensão valem ao arrastar (28/10/2026).

Ela: «os slicers da Lovense aplicam ao soltar». O deslizante gravava só no ``change``, e a extensão
lia o ``opcoes.json`` a cada segundo: o brinquedo só mudava depois de soltar. Agora o arrastar é um
gesto vivo que manda ``mods.opcao``; a porta leva ``extensao.opcao`` só à extensão dona, em no
máximo 20 por segundo, e o soltar continua gravando.
"""
from __future__ import annotations

import asyncio
import pathlib
from typing import Any

import pytest

from hefesto_dualsense4unix.core.events import EventBus
from hefesto_dualsense4unix.daemon.ipc_handlers import IpcHandlersMixin
from hefesto_dualsense4unix.interface import desenho_da_experimental as exp
from hefesto_dualsense4unix.interface import pacotes
from tests.unit.test_a_aba_lancadores_ganha_as_modificacoes import (  # noqa: F401
    ctx,
    lar,
)
from tests.unit.test_a_coluna_agora_e_o_parar_tudo_vem_do_servico import (  # noqa: F401
    _entrar,
    _porta,
    curto,
)
from tests.unit.test_a_janela_da_extensao_age_e_gere_os_aparelhos import (  # noqa: F401
    VIVO,
    _instalada,
    _pecas,
    _Ponte,
    _servico,
    janela,
)

FORCA = {"id": "forca", "rotulo": "Força", "tipo": "deslizante",
         "minimo": 0, "maximo": 100,  # (noqa-acento)
         "passo": 1, "padrao": 50, "unidade": "%"}  # (noqa-acento)


def _com_o_deslizante() -> dict[str, Any]:
    pecas = _pecas()
    pecas["opcoes"].append(dict(FORCA))  # (noqa-acento)
    return pecas


def test_o_deslizante_arrasta_vivo_e_solta_gravando() -> None:
    opcao = exp.OpcaoDaJanela(mod="toque", id="forca", rotulo="Força", tipo="deslizante",
                              valor=40, minimo=0, maximo=100, passo=1)
    html = exp._controle_da_opcao(opcao)
    assert f'data-hef-vivo="{exp.GESTO_DA_OPCAO_VIVA}"' in html, "o arrastar não sai vivo"
    assert 'data-gesto="guardar-opcao-da-modificacao"' in html, "o soltar parou de gravar"
    assert pacotes.gesto_da_pagina("07-lancadores.html", exp.GESTO_DA_OPCAO_VIVA) is not None
    grava = (pacotes.GESTOS_QUE_MEXEM.get(("07-lancadores.html", exp.GESTO_DA_OPCAO_VIVA))
             or pacotes.GESTOS_QUE_MEXEM.get(("*", exp.GESTO_DA_OPCAO_VIVA)))
    assert not grava, "o gesto vivo declara gravação e o piloto o recusa"


def test_arrastar_um_segundo_sai_em_no_maximo_vinte_so_a_dona(
        curto: pathlib.Path) -> None:  # noqa: F811
    """Prova da D-2810-OS-DESLIZANTES-DA-EXTENSAO-VALEM-AO-ARRASTAR."""
    async def corrida() -> list[dict[str, Any]]:
        porta = await _porta(curto, EventBus())
        a = await _entrar(curto, "ficha-a", {"ligado": True})
        b = await _entrar(curto, "ficha-b", {"ligado": True})
        try:
            for n in range(60):
                assert porta.opcao_viva("acessorios", "forca", n) is True
                await asyncio.sleep(1 / 60)
            await asyncio.sleep(0.3)
            chegaram = []
            while (evento := await asyncio.to_thread(a.esperar_evento, 0.2)) is not None:
                chegaram.append(evento["params"])
            vazou = await asyncio.to_thread(b.esperar_evento, 0.2)
            assert vazou is None, f"a outra extensão recebeu o arrastar: {vazou}"
            assert porta.opcao_viva("ninguem", "forca", 3) is False
            return chegaram
        finally:
            a.fechar()
            b.fechar()
            await porta.parar()

    chegaram = asyncio.run(corrida())
    assert {c["nome"] for c in chegaram} == {"extensao.opcao"}
    assert 5 <= len(chegaram) <= 21, f"{len(chegaram)} eventos num segundo de arrastar"
    assert chegaram[-1]["dados"] == {"mod": "acessorios", "id": "forca", "valor": 59}
    valores = [c["dados"]["valor"] for c in chegaram]
    assert valores == sorted(valores) and valores[0] > 0, valores


def test_o_ipc_so_leva_o_deslizante_declarado_e_na_faixa(lar: Any) -> None:  # noqa: F811
    _instalada(lar, **_com_o_deslizante())
    arrastou: list[tuple[Any, ...]] = []

    def opcao_viva(mod: str, i: str, v: float) -> bool:
        arrastou.append((mod, i, v))
        return True

    from types import SimpleNamespace

    servico = _servico(SimpleNamespace(lugares=lar, porta=SimpleNamespace(opcao_viva=opcao_viva)))

    def arrastar(**params: Any) -> Any:
        return asyncio.run(IpcHandlersMixin._handle_mods_opcao(servico, {"mod": "toque", **params}))

    assert arrastar(id="forca", valor=4) == {"enviado": True}
    with pytest.raises(ValueError, match="não declara o deslizante «toques»"):
        arrastar(id="toques", valor=4)
    with pytest.raises(ValueError, match="vai de 0 a 100"):
        arrastar(id="forca", valor=101)
    with pytest.raises(ValueError, match="é um número"):
        arrastar(id="forca", valor=True)
    assert arrastou == [("toque", "forca", 4)]
    sem = asyncio.run(IpcHandlersMixin._handle_mods_opcao(
        _servico(None), {"mod": "toque", "id": "forca", "valor": 4}))
    assert sem == {"enviado": False}


def test_o_arrastar_fora_de_ordem_e_depois_do_soltar_cai(janela: Any, ctx: Any) -> None:  # noqa: F811
    a07, instalar, abrir = janela
    instalar(**_com_o_deslizante())
    ponte = _Ponte(VIVO)
    abrir(ponte)

    def arrastar(valor: int, carimbo: float) -> None:
        resposta = a07.arrastar_a_opcao_da_modificacao(
            ctx, {"v": "toque:forca", "valor": str(valor), "carimbo": str(carimbo),
                  "evento": "input"}, ponte)
        assert resposta == {}, "o gesto vivo pintou"

    arrastar(30, 100.0)
    arrastar(10, 99.0)
    arrastar(4, 101.0)
    a07.guardar_opcao_da_modificacao(
        ctx, {"v": "toque:forca", "valor": "4", "carimbo": "120", "evento": "change"}, ponte)
    arrastar(90, 110.0)
    feitas = [p["valor"] for m, p in ponte.chamadas if m == "mods.opcao"]
    assert feitas == [30, 4], feitas
