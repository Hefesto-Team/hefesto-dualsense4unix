"""A porta vê a tela do jogo pelo portal (02/11/2026, ensaio).

Quadros sintéticos dão os cinco sinais de ``jogo.tela``: a borda vermelha que sobe é ``dano``, o
branco súbito é ``flash``, o preto é ``escuro``, o quadro deslocado é ``tremor`` e a cor viva é
``saturacao``. A região declarada publica só a fração; sem assinante a fonte não abre; a fonte que
cai vira ausente (``None``), nunca zero. Sem a permissão ``ler:jogo.tela``, a porta recusa.
"""
from __future__ import annotations

import asyncio
import os
import random
import tempfile
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.core.events import EventBus
from hefesto_dualsense4unix.integrations import tela_do_jogo as tj
from hefesto_dualsense4unix.mods.manifesto import TOPICOS_DE_LEITURA, o_que_a_permissao_deixa
from hefesto_dualsense4unix.mods.porta import CODE_SEM_PERMISSAO, Porta
from tests.unit.test_a_porta_ouve_o_jogo_e_o_microfone import P1, _Cliente

L, A = 64, 36
Pintor = Callable[[int, int], tuple[int, int, int]]


def _quadro(pintor: Pintor, largura: int = L, altura: int = A) -> tj.Quadro:
    dados = bytearray()
    for y in range(altura):
        for x in range(largura):
            r, g, b = pintor(x, y)
            dados += bytes((b, g, r, 0))
    return tj.Quadro(largura, altura, largura * 4, "BGRx", bytes(dados))


def _cinza(v: int) -> Pintor:
    return lambda _x, _y: (v, v, v)


def _borda_vermelha(x: int, y: int) -> tuple[int, int, int]:
    if x < 6 or x >= L - 6 or y < 4 or y >= A - 4:
        return 220, 20, 20
    return 90, 90, 90


def _medir(*pintores: Pintor) -> list[dict[str, Any]]:
    tela = tj.TelaDoJogo(relogio=lambda: 1.0)
    return [tela.medir(_quadro(p)) for p in pintores]


def test_a_borda_vermelha_que_sobe_e_dano() -> None:
    _, depois = _medir(_cinza(90), _borda_vermelha)
    assert depois["dano"] > 0.5
    _, igual = _medir(_borda_vermelha, _borda_vermelha)
    assert igual["dano"] == 0.0


def test_o_branco_subito_e_flash_e_o_preto_e_escuro() -> None:
    _, branco = _medir(_cinza(40), _cinza(255))
    assert branco["flash"] > 0.9
    assert branco["escuro"] == pytest.approx(0.0, abs=0.01)
    _, preto = _medir(_cinza(120), _cinza(0))
    assert preto["flash"] == 0.0
    assert preto["escuro"] == pytest.approx(1.0)


def test_o_quadro_deslocado_e_tremor() -> None:
    sorteio = random.Random(7)
    celulas = [[sorteio.randrange(256) for _ in range(tj.GRADE_X + 4)]
               for _ in range(tj.GRADE_Y)]

    def deslocado(passo: int) -> Pintor:
        return lambda x, y: (celulas[y // 2][x // 2 + passo],) * 3

    _, parado = _medir(deslocado(2), deslocado(2))
    assert parado["tremor"] == 0.0
    _, tremeu = _medir(deslocado(2), deslocado(0))
    assert tremeu["tremor"] == pytest.approx(2 / (2 * 2 ** 0.5))


def test_a_luz_que_muda_devagar_numa_cena_lisa_nao_e_tremor() -> None:
    """Prova da D-IMERSAO-TREMOR-PISO."""
    def rampa(soma: int) -> Pintor:
        return lambda x, _y: ((x // 2) * 4 + soma,) * 3

    _, clareou = _medir(rampa(0), rampa(3))
    assert clareou["tremor"] == 0.0


def test_a_cor_viva_e_saturacao() -> None:
    cinza, = _medir(_cinza(128))
    viva, = _medir(lambda _x, _y: (250, 10, 200))
    assert cinza["saturacao"] == 0.0
    assert viva["saturacao"] > 0.9
    assert set(viva) == {"t", *tj.SINAIS}


def test_a_regiao_publica_so_a_fracao() -> None:
    barra, = tj.regioes_da_receita([dict(nome="vida", x=0.1, y=0.1, largura=0.5, altura=0.1,
                                         cor=[200, 30, 30])])

    def vida_em(fracao_cheia: float) -> Pintor:
        def pintor(x: int, y: int) -> tuple[int, int, int]:
            dentro = 14 <= y < 29 and 26 <= x < (0.1 + 0.5 * fracao_cheia) * 256
            return (200, 30, 30) if dentro else (20, 20, 20)
        return pintor

    tela = tj.TelaDoJogo([barra], relogio=lambda: 1.0)
    carga = tela.medir(_quadro(vida_em(0.75), 256, 144))
    assert carga["regioes"]["vida"] == pytest.approx(0.75, abs=1 / tj.AMOSTRAS_DA_REGIAO)
    assert set(carga) == {"t", *tj.SINAIS, "regioes"}
    assert all(isinstance(v, float) for k, v in carga.items() if k != "regioes")


def test_a_regiao_fora_da_forma_e_recusada() -> None:
    base = dict(nome="vida", x=0.1, y=0.1, largura=0.5, altura=0.1, cor=[1, 2, 3])
    for errada in ({**base, "x": 0.8}, {**base, "cor": [1, 2]}, {**base, "cor": [1, 2, 300]},
                   {**base, "nome": "Vida!"}, {k: v for k, v in base.items() if k != "y"}):
        with pytest.raises(tj.TelaRecusadaError):
            tj.regioes_da_receita([errada])
    for medida in ("x", "y", "largura", "altura"):
        with pytest.raises(tj.TelaRecusadaError, match="sai da tela"):
            tj.regioes_da_receita([{**base, medida: float("nan")}])
    with pytest.raises(tj.TelaRecusadaError):
        tj.regioes_da_receita([base] * (tj.REGIOES_POR_RECEITA + 1))
    with pytest.raises(tj.TelaRecusadaError, match="repete"):
        tj.regioes_da_receita([base, base])


def test_o_quadro_menor_do_que_declara_e_recusado() -> None:
    with pytest.raises(tj.TelaRecusadaError):
        tj.Quadro(64, 36, 256, "BGRx", b"\0" * 100)
    with pytest.raises(tj.TelaRecusadaError):
        tj.Quadro(64, 36, 256, "YUV", b"\0" * 256 * 36)


class _Fonte:
    def __init__(self, abre: bool = True) -> None:
        self.abre = abre
        self.abertas = 0
        self.fechadas = 0
        self.quadros: list[tj.Quadro | None] = []

    def abrir(self) -> bool:
        self.abertas += 1
        return self.abre

    def quadro(self) -> tj.Quadro | None:
        return self.quadros.pop(0) if self.quadros else _quadro(_cinza(100))

    def fechar(self) -> None:
        self.fechadas += 1


def _captura(fonte: _Fonte, assinantes: list[int], agora: list[float]
             ) -> tuple[tj.Captura, list[dict[str, Any]]]:
    publicadas: list[dict[str, Any]] = []
    captura = tj.Captura(fonte, tj.TelaDoJogo(relogio=lambda: agora[0]),
                         publicar=publicadas.append, assinantes=lambda: assinantes[0],
                         nascidas=lambda: 1,
                         espera=2.0, relogio=lambda: agora[0])
    return captura, publicadas


def test_sem_assinante_a_fonte_nao_abre_e_ao_largar_fecha() -> None:
    fonte, assinantes, agora = _Fonte(), [0], [0.0]
    captura, publicadas = _captura(fonte, assinantes, agora)
    for _ in range(5):
        captura.passo()
    assert fonte.abertas == 0 and publicadas == []
    assinantes[0] = 1
    captura.passo()
    captura.passo()
    assert fonte.abertas == 1 and len(publicadas) == 2
    assinantes[0] = 0
    captura.passo()
    assert fonte.fechadas == 1 and not captura.aberta


def test_a_fonte_que_cai_vira_ausente_uma_vez_e_volta_sozinha() -> None:
    fonte, assinantes, agora = _Fonte(), [1], [0.0]
    captura, publicadas = _captura(fonte, assinantes, agora)
    captura.passo()
    fonte.quadros = [None]
    captura.passo()
    captura.passo()
    agora[0] = 1.0
    captura.passo()
    assert [p["dano"] for p in publicadas] == [0.0, None]
    assert all(publicadas[1][s] is None for s in tj.SINAIS)
    assert fonte.abertas == 1 and fonte.fechadas == 1
    agora[0] = 2.5
    captura.passo()
    assert fonte.abertas == 2
    assert publicadas[-1]["escuro"] is not None


def test_a_fonte_que_falta_e_ausente_e_nunca_zero() -> None:
    """Prova da D-IMERSAO-AUSENTE-NONE."""
    fonte, assinantes, agora = _Fonte(abre=False), [1], [0.0]
    captura, publicadas = _captura(fonte, assinantes, agora)
    for _ in range(3):
        captura.passo()
    agora[0] = 2.5
    captura.passo()
    assert fonte.abertas == 2
    assert len(publicadas) == 1
    assert all(publicadas[0][s] is None for s in tj.SINAIS)


def test_a_permissao_e_o_topico_da_tela() -> None:
    assert TOPICOS_DE_LEITURA["jogo.tela"] == (tj.TOPICO_DA_TELA,)
    frase = o_que_a_permissao_deixa("ler:jogo.tela")
    assert "imagem" in frase and frase != "ler:jogo.tela"


def test_sem_a_permissao_a_porta_recusa_e_com_a_permissao_entrega_so_os_numeros() -> None:
    async def corrida() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
        with tempfile.TemporaryDirectory(prefix="pt") as pasta:
            caminho = Path(pasta) / "mods.sock"
            bus = EventBus()

            async def escritor(_m: str, _p: dict[str, Any]) -> Any:
                return {"status": "ok"}

            porta = Porta(caminho, bus, escritor=escritor,
                          o_jogo_escreve=lambda _u, _c: False, uniq_do_posto=lambda: P1)
            await porta.iniciar()
            porta.registrar("ficha-com", "com", os.getpid(), ["ler:jogo.tela"])
            porta.registrar("ficha-sem", "sem", os.getpid(), ["ler:jogo.som"])
            com, sem = _Cliente(caminho), _Cliente(caminho)
            try:
                await asyncio.to_thread(com.pedir, "mod.ola", {"ficha": "ficha-com"})
                await asyncio.to_thread(sem.pedir, "mod.ola", {"ficha": "ficha-sem"})
                recusa = await asyncio.to_thread(
                    sem.pedir, "eventos.assinar", {"topicos": ["jogo.tela"]})
                assert bus.subscriber_count(tj.TOPICO_DA_TELA) == 0
                aceito = await asyncio.to_thread(
                    com.pedir, "eventos.assinar", {"topicos": ["jogo.tela"]})
                assert bus.subscriber_count(tj.TOPICO_DA_TELA) == 1
                tela = tj.TelaDoJogo(relogio=lambda: 3.0)
                bus.publish(tj.TOPICO_DA_TELA, tela.medir(_quadro(_cinza(30))))
                evento = await asyncio.wait_for(asyncio.to_thread(com.evento), 3)
            finally:
                com.fechar()
                sem.fechar()
                await porta.parar()
            return recusa, aceito, evento

    recusa, aceito, evento = asyncio.run(corrida())
    assert recusa["error"]["code"] == CODE_SEM_PERMISSAO
    assert aceito["result"] == {"assinados": ["jogo.tela"]}
    assert evento["params"]["nome"] == "jogo.tela"
    assert set(evento["params"]["dados"]) == {"t", *tj.SINAIS}


def test_o_custo_por_quadro_fica_medido() -> None:
    quadro = _quadro(_borda_vermelha, 320, 180)
    tela = tj.TelaDoJogo()
    tela.medir(quadro)
    inicio = time.perf_counter()
    for _ in range(15):
        tela.medir(quadro)
    por_quadro = (time.perf_counter() - inicio) / 15
    assert por_quadro < 1 / tj.HZ_DA_TELA, f"{por_quadro * 1000:.2f} ms por quadro"
