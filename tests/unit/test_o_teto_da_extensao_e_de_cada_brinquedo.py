"""A barra de cada aparelho gerido mora no cartão dele, na linha do nome (25/11/2026).

A força mais alta de uma extensão de brinquedos era uma barra só, na aba «Força», para todos os
brinquedos. Agora o manifesto declara, junto das ações dos aparelhos, uma ``barra`` por aparelho
(id, rótulo, faixa e degraus), e o estado que a extensão publica traz o valor de cada um. A janela
a desenha entre a bateria e a chave; arrastar chega à extensão pela ``extensao.acao`` com o alvo
(no compasso de 20 por segundo) e soltar grava, e a janela mostra o que a extensão publica. Sem a
declaração, nada muda para as outras extensões.

Prova da D-2511-O-TETO-DA-EXTENSAO-E-DE-CADA-BRINQUEDO.
"""
from __future__ import annotations

import asyncio
import copy
import pathlib
import re
from types import SimpleNamespace
from typing import Any

import pytest
from pydantic import ValidationError

from hefesto_dualsense4unix.core.events import EventBus
from hefesto_dualsense4unix.daemon.ipc_handlers import IpcHandlersMixin
from hefesto_dualsense4unix.interface import desenho_da_experimental as exp
from hefesto_dualsense4unix.interface import pacotes
from hefesto_dualsense4unix.mods import porta as porta_das_extensoes
from hefesto_dualsense4unix.mods.manifesto import Manifesto
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
    APARELHOS,
    _instalada,
    _manifesto,
    _pecas,
    _Ponte,
    _servico,
    janela,
)

TETO = {"id": "teto", "rotulo": "Teto", "minimo": 0, "maximo": 100,  # (noqa-acento)
        "passo": 1, "degraus": 20, "dica": "A força mais alta que vai a este aparelho"}
COM_O_TETO = [{**ap, "barra": 20 * n} for n, ap in enumerate(APARELHOS, 1)]
VIVO_COM_O_TETO = {"ligado": True, "nivel": 3, "perfil": "Ondas", "aparelhos": COM_O_TETO,
                   "serie": 1}


def _com_a_barra(grupo: str | None = "Aparelhos") -> dict[str, Any]:
    pecas = _pecas(grupo)
    pecas["aparelhos_acoes"]["barra"] = copy.deepcopy(TETO)  # (noqa-acento)
    return pecas


def _gestao(barra: exp.BarraDaJanela | None, aparelhos: list[dict[str, Any]], *,
            desligada: bool = False) -> exp.Gestao:
    acoes = (exp.AcaoDaJanela("ligar", "Ligar", icone="ligar"),
             exp.AcaoDaJanela("testar", "Testar", icone="testar"))
    return exp.Gestao("toque", exp.AparelhosDaJanela(acoes, "Aparelhos", barra),
                      {"aparelhos": aparelhos}, desligada=desligada)


BARRA = exp.BarraDaJanela("teto", "Teto", 0, 100, 1, 20, "A força mais alta")


def _cartao(html: str, alvo: str) -> str:
    cartao = re.search(rf'data-alvo="{alvo}".*?(?=data-alvo="|$)', html, re.S)
    assert cartao, f"o aparelho {alvo} não tem cartão"
    return cartao.group(0)


@pytest.fixture
def barras(janela: Any, monkeypatch: pytest.MonkeyPatch) -> Any:  # noqa: F811
    a07 = janela[0]
    monkeypatch.setattr(a07, "_BARRAS", a07._Barras())
    return janela


def test_o_manifesto_declara_uma_barra_por_aparelho_e_a_confere() -> None:
    m = Manifesto.model_validate(_manifesto(**_com_a_barra()))
    assert m.aparelhos_acoes is not None and m.aparelhos_acoes.barra is not None
    assert m.aparelhos_acoes.ids == ("ligar", "testar", "teto")
    sem_grupo = _com_a_barra(grupo=None)
    with pytest.raises(ValidationError, match="pede o grupo"):
        Manifesto.model_validate(_manifesto(**sem_grupo))
    repetida = _com_a_barra()
    repetida["aparelhos_acoes"]["barra"]["id"] = "testar"  # (noqa-acento)
    with pytest.raises(ValidationError, match="repete o id da ação testar"):
        Manifesto.model_validate(_manifesto(**repetida))
    torta = _com_a_barra()
    torta["aparelhos_acoes"]["barra"]["maximo"] = 0  # (noqa-acento)
    with pytest.raises(ValidationError, match="faixa fora de ordem"):
        Manifesto.model_validate(_manifesto(**torta))
    assert Manifesto.model_validate(_manifesto(**_pecas())).aparelhos_acoes.barra is None  # type: ignore[union-attr]


def test_o_estado_leva_o_valor_da_barra_de_cada_aparelho() -> None:
    aparelho = porta_das_extensoes._aparelho({"id": "ap-1", "nome": "Lush", "barra": 80})
    assert aparelho["barra"] == 80.0
    assert "barra" not in porta_das_extensoes._aparelho({"id": "ap-1", "nome": "Lush"})
    for torto in ({"id": "ap-1", "nome": "Lush", "barra": "80"},
                  {"id": "ap-1", "nome": "Lush", "barra": True},
                  {"nome": "Lush", "barra": 80}):
        with pytest.raises(porta_das_extensoes.RecusaError, match="barra de um aparelho"):
            porta_das_extensoes._aparelho(torto)


def test_a_barra_mora_na_linha_do_nome_entre_a_bateria_e_a_chave() -> None:
    html = exp.aparelhos_geridos_html(_gestao(BARRA, COM_O_TETO))
    cabeca = re.search(r'<div class="mj-ap-cab">(.*?)</div>', _cartao(html, "ap-4"), re.S)
    assert cabeca, "o cartão perdeu a linha do nome"
    linha = cabeca.group(1)
    ordem = [linha.find(p) for p in ('class="mj-ap-nome"', 'class="mj-pct"',
                                     'class="mj-ap-barra"', 'class="mj-chave')]
    assert -1 not in ordem and ordem == sorted(ordem), f"a ordem da linha do nome: {ordem}"
    barra = re.search(r'<input type="range"[^>]*>', linha)
    assert barra, "a barra não está na linha do nome"
    entrada = barra.group(0)
    assert 'value="80"' in entrada and 'min="0"' in entrada and 'max="100"' in entrada
    assert f'data-gesto="{exp.GESTO_DE_SOLTAR_A_BARRA}"' in entrada
    assert f'data-hef-vivo="{exp.GESTO_DA_BARRA_VIVA}"' in entrada
    assert 'data-v="toque:teto:ap-4"' in entrada, "a barra leva o aparelho do cartão"
    assert ">Teto<" in linha and ">16/20<" in linha, "o rótulo e o número (degrau) ao lado"
    assert html.count('class="mj-ap-barra"') == 4, "uma barra em cada cartão"
    assert html.count('class="mj-ap-pe"') == 4 and 'class="mj-ap-barra"' not in re.sub(
        r'<div class="mj-ap-cab">.*?</div>', "", html, flags=re.S), "a barra só na linha do nome"


def test_sem_a_barra_declarada_ou_sem_o_valor_nada_muda() -> None:
    sem_barra = exp.aparelhos_geridos_html(_gestao(None, COM_O_TETO))
    assert "mj-ap-barra" not in sem_barra and 'type="range"' not in sem_barra
    sem_valor = exp.aparelhos_geridos_html(_gestao(BARRA, APARELHOS))
    assert "mj-ap-barra" not in sem_valor, "a janela inventou um valor que a extensão não publicou"
    assert sem_barra == sem_valor


def test_com_a_chave_desligada_a_barra_fica_a_vista_e_parada() -> None:
    html = exp.aparelhos_geridos_html(_gestao(BARRA, COM_O_TETO, desligada=True))
    assert html.count('class="mj-ap-barra"') == 4
    assert exp.GESTO_DA_BARRA_VIVA not in html and exp.GESTO_DE_SOLTAR_A_BARRA not in html
    assert html.count('type="range"') == html.count(" disabled aria-disabled") == 4


def test_os_gestos_da_barra_sao_da_aba_e_o_vivo_nao_grava() -> None:
    for gesto in (exp.GESTO_DA_BARRA_VIVA, exp.GESTO_DE_SOLTAR_A_BARRA):
        assert pacotes.gesto_da_pagina("07-lancadores.html", gesto) is not None, gesto
    grava = (pacotes.GESTOS_QUE_MEXEM.get(("07-lancadores.html", exp.GESTO_DA_BARRA_VIVA))
             or pacotes.GESTOS_QUE_MEXEM.get(("*", exp.GESTO_DA_BARRA_VIVA)))
    assert not grava, "o gesto vivo declara gravação e o piloto o recusa"


def test_o_ipc_leva_a_barra_na_faixa_com_o_soltou(lar: Any) -> None:  # noqa: F811
    _instalada(lar, **_com_a_barra())
    levadas: list[tuple[Any, ...]] = []

    def barra(mod: str, barra_id: str, alvo: str, valor: float, *, soltou: bool) -> bool:
        levadas.append((mod, barra_id, alvo, valor, soltou))
        return True

    servico = _servico(SimpleNamespace(lugares=lar, porta=SimpleNamespace(barra=barra)))

    def pedir(**params: Any) -> Any:
        return asyncio.run(IpcHandlersMixin._handle_mods_acao(servico, {"mod": "toque", **params}))

    assert pedir(acao="teto", alvo="ap-1", valor=35, soltou=False) == {"enviada": True}
    assert pedir(acao="teto", alvo="ap-1", valor=40, soltou=True) == {"enviada": True}
    with pytest.raises(ValueError, match="vai de 0 a 100"):
        pedir(acao="teto", alvo="ap-1", valor=101, soltou=True)
    with pytest.raises(ValueError, match="vai de 0 a 100"):
        pedir(acao="teto", alvo="ap-1", valor=True, soltou=True)
    with pytest.raises(ValueError, match="soltou da barra"):
        pedir(acao="teto", alvo="ap-1", valor=40)
    with pytest.raises(ValueError, match="verdadeiro, falso ou o id"):
        pedir(acao="testar", alvo="ap-1", valor=40)
    assert levadas == [("toque", "teto", "ap-1", 35.0, False),
                       ("toque", "teto", "ap-1", 40.0, True)]


def test_o_arrastar_sai_no_compasso_e_o_soltar_na_hora_so_a_dona(
        curto: pathlib.Path) -> None:  # noqa: F811
    """MORDIDA: sem o soltar tirar o arrastar que esperava, ele sai depois e desfaz o soltar."""
    async def corrida() -> tuple[list[dict[str, Any]], bool]:
        porta = await _porta(curto, EventBus())
        a = await _entrar(curto, "ficha-a", {"ligado": True})
        b = await _entrar(curto, "ficha-b", {"ligado": True})
        try:
            for n in range(30):
                assert porta.barra("acessorios", "teto", "ap-1", n, soltou=False) is True
                await asyncio.sleep(1 / 60)
            assert porta.barra("acessorios", "teto", "ap-1", 32, soltou=False) is True
            assert porta.barra("acessorios", "teto", "ap-1", 33, soltou=True) is True
            await asyncio.sleep(0.3)
            chegaram = []
            while (evento := await asyncio.to_thread(a.esperar_evento, 0.2)) is not None:
                chegaram.append(evento["params"])
            vazou = await asyncio.to_thread(b.esperar_evento, 0.2) is not None
            assert porta.barra("ninguem", "teto", "ap-1", 3, soltou=True) is False
            return chegaram, vazou
        finally:
            a.fechar()
            b.fechar()
            await porta.parar()

    chegaram, vazou = asyncio.run(corrida())
    assert not vazou, "a outra extensão recebeu a barra"
    assert {c["nome"] for c in chegaram} == {"extensao.acao"}
    assert 3 <= len(chegaram) <= 12, f"{len(chegaram)} eventos em meio segundo de arrastar"
    ultimo = {"mod": "acessorios", "acao": "teto", "alvo": "ap-1",  # (noqa-acento)
              "valor": 33, "soltou": True}
    assert chegaram[-1]["dados"] == ultimo, "o soltar sai por último"
    assert all(c["dados"]["soltou"] is False for c in chegaram[:-1])
    assert 32 not in [c["dados"]["valor"] for c in chegaram], \
        "o arrastar que esperava o compasso saiu depois do soltar"


def test_a_janela_arrasta_vivo_solta_e_mostra_o_que_a_extensao_publica(
        barras: Any, ctx: Any) -> None:  # noqa: F811
    """O arrastar manda o valor sem gravar e segura a lista sob o dedo; o soltar manda o
    ``soltou``, e a barra mostra o valor pedido até a extensão publicar o estado novo, e então o
    que a extensão publicou. MORDIDA: sem a barra na linha do nome, o cartão não a tem."""
    a07, instalar, abrir = barras
    instalar(**_com_a_barra())
    ponte = _Ponte(VIVO_COM_O_TETO)
    html = abrir(ponte)["blocos"]["#mod-janela"]
    assert 'data-v="toque:teto:ap-2"' in html and 'value="40"' in html

    def arrastar(valor: int, carimbo: float) -> Any:
        return a07.arrastar_a_barra_do_aparelho(
            ctx, {"v": "toque:teto:ap-2", "valor": str(valor), "carimbo": str(carimbo),
                  "evento": "input"}, ponte)

    assert arrastar(55, 100.0) == {}, "o gesto vivo pintou"
    assert arrastar(50, 99.0) == {}
    assert arrastar(60, 101.0) == {}
    a07._AGORA.ler("toque", ponte)
    assert "#mod-aparelhos" not in a07._com_os_aparelhos({"blocos": {}})["blocos"], \
        "o tique trocou a barra sob o dedo"
    assert a07.soltar_a_barra_do_aparelho(
        ctx, {"v": "toque:teto:ap-2", "valor": "60", "carimbo": "102", "evento": "click"},
        ponte) is None, "o clique na barra não é o soltar"
    a07.soltar_a_barra_do_aparelho(
        ctx, {"v": "toque:teto:ap-2", "valor": "60", "carimbo": "103", "evento": "change"}, ponte)
    feitas = [(p["valor"], p["soltou"]) for m, p in ponte.chamadas
              if m == "mods.acao" and p.get("acao") == "teto"]  # (noqa-acento)
    assert feitas == [(55, False), (60, False), (60, True)], feitas
    a07._AGORA.ler("toque", ponte)
    bloco = a07._com_os_aparelhos({"blocos": {}})["blocos"]["#mod-aparelhos"]
    assert 'value="60"' in _cartao(bloco, "ap-2"), \
        "a barra voltou ao valor de antes enquanto a extensão gravava"
    ponte.estado = {**VIVO_COM_O_TETO, "serie": 2, "aparelhos": [
        {**ap, "barra": 55} if ap["id"] == "ap-2" else ap for ap in COM_O_TETO]}
    a07._AGORA.ler("toque", ponte)
    bloco = a07._com_os_aparelhos({"blocos": {}})["blocos"]["#mod-aparelhos"]
    assert 'value="55"' in _cartao(bloco, "ap-2"), "a barra mostra o que a extensão publica"


def test_o_soltar_que_nao_chega_devolve_a_barra_ao_que_vale(barras: Any, ctx: Any) -> None:  # noqa: F811
    a07, instalar, abrir = barras
    instalar(**_com_a_barra())
    ponte = _Ponte(VIVO_COM_O_TETO, rodando=False)
    abrir(ponte)
    a07._AGORA.ler("toque", ponte)
    antes = a07._com_os_aparelhos({"blocos": {}})["blocos"]["#mod-aparelhos"]
    with pytest.raises(RuntimeError, match="não está rodando"):
        a07.soltar_a_barra_do_aparelho(
            ctx, {"v": "toque:teto:ap-2", "valor": "90", "carimbo": "5", "evento": "change"},
            ponte)
    a07._AGORA.ler("toque", ponte)
    depois = a07._com_os_aparelhos({"blocos": {}})["blocos"]["#mod-aparelhos"]
    assert 'value="40"' in _cartao(depois, "ap-2"), "a barra ficou no valor que não valeu"
    assert depois != antes, "a barra não se repinta, e a tela segue no valor arrastado"
