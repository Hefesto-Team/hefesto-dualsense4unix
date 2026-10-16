"""A-VOLTA-DOS-ACESSORIOS-SE-SENTE-NO-CONTROLE-E-NA-LUZ-01: o toque, as luzinhas e o pulso da barra.

Relógio injetado e escritores de mentira que guardam o que o controle receberia. A porta é a de
verdade, num socket de verdade, com o pulsador ligado à volta.
"""
from __future__ import annotations

import asyncio
import os
import shutil
import socket
import tempfile
from collections.abc import Iterator
from dataclasses import dataclass, field
from itertools import pairwise
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from hefesto_dualsense4unix.core.events import EventBus, EventTopic
from hefesto_dualsense4unix.core.led_control import player_bitmask
from hefesto_dualsense4unix.daemon.protocolo_do_ipc import CODE_INVALID_PARAMS
from hefesto_dualsense4unix.daemon.subsystems import tato_vivo as tv
from hefesto_dualsense4unix.daemon.subsystems.volta_dos_acessorios import (
    DEGRAU_DO_MEDIDOR,
    Ligacoes,
    VoltaDosAcessorios,
    lampadas_do_nivel,
)
from hefesto_dualsense4unix.mods.manifesto import permissao_valida
from hefesto_dualsense4unix.mods.porta import (
    CODE_O_JOGO_ESCREVE,
    CODE_SEM_PERMISSAO,
    Porta,
    estado_dos_acessorios,
)

P1 = "aabbcc000001"
P2 = "aabbcc000002"
ORIGINAL = (False, False, True, False, False)  # o número do jogador que o controle acende
VERMELHO = [122, 0, 16]


@dataclass
class Mesa:
    """O controle de mentira: o que ele recebeu e o que as guardas respondem."""

    agora: float = 1000.0
    motores: list[tuple[float, str, int, int]] = field(default_factory=list)
    luzinhas: list[tuple[str, tuple[bool, ...], int]] = field(default_factory=list)
    barra: list[tuple[float, str, tuple[int, int, int]]] = field(default_factory=list)
    soltas: list[str] = field(default_factory=list)
    pode: bool = True
    vibra: bool = False
    pinta: bool = False
    marcas: frozenset[str] = frozenset({"adulto"})

    def ligacoes(self) -> Ligacoes:
        return Ligacoes(
            motores=lambda uniq, fraco, forte: self.motores.append(
                (self.agora, uniq, fraco, forte)),
            ler_luzinhas=lambda uniq: (ORIGINAL, 1),
            luzinhas=lambda uniq, acesas, degrau: self.luzinhas.append((uniq, acesas, degrau)),
            barra=lambda uniq, rgb: self.barra.append((self.agora, uniq, rgb)),
            soltar_barra=self.soltas.append,
            pode_falar=lambda uniq: self.pode,
            o_jogo_vibra=lambda uniq: self.vibra,
            o_jogo_pinta=lambda uniq: self.pinta,
            marcas=lambda: self.marcas,
        )


def _andar(volta: VoltaDosAcessorios, mesa: Mesa, ate: float, passo: float = 0.005) -> None:
    """Anda o relógio da mesa até ``ate`` (instante absoluto), um tique por ``passo``."""
    while mesa.agora < ate:
        mesa.agora = round(mesa.agora + passo, 6)
        volta.tique(mesa.agora)


def _estado(nivel: int = 0, **ajustes: Any) -> dict[str, Any]:
    return {"ligado": True, "nivel": nivel, "aparelhos": ["Um"], "ajustes": ajustes}


def _gesto(uniq: str, gesto: str, valor: float = 1) -> dict[str, Any]:
    return {"uniq": uniq, "jogador": 1, "gesto": gesto, "valor": valor}


def _volta(**ajustes: Any) -> tuple[VoltaDosAcessorios, Mesa]:
    mesa = Mesa()
    volta = VoltaDosAcessorios(mesa.ligacoes())
    volta.ao_estado(_estado(0, **ajustes), mesa.agora)
    return volta, mesa


def _com_o_pulso(sem_pisca: bool = False, nivel: int = 3) -> tuple[VoltaDosAcessorios, Mesa]:
    volta, mesa = _volta(pulso_da_barra=True, **({"sem_pisca": True} if sem_pisca else {}))
    volta.ao_estado(_estado(nivel, pulso_da_barra=True, sem_pisca=sem_pisca), mesa.agora)
    return volta, mesa


def _brilhos(mesa: Mesa, uniq: str = P1) -> list[tuple[float, int]]:
    return [(t, max(rgb)) for t, u, rgb in mesa.barra if u == uniq]


# -- as luzinhas medidor ---------------------------------------------------------------------


@pytest.mark.parametrize(
    ("nivel", "lampadas"), [(0, 0), (1, 1), (2, 1), (3, 2), (7, 4), (9, 5), (10, 5)])
def test_as_lampadas_sao_o_nivel_dividido_por_dois_para_cima(nivel: int, lampadas: int) -> None:
    assert lampadas_do_nivel(nivel) == lampadas


def test_o_nivel_7_acende_quatro_lampadas_sem_esmaecer_e_volta_em_2_s() -> None:
    volta, mesa = _volta()
    volta.ao_estado(_estado(7), mesa.agora)
    inicio = mesa.agora
    volta.ao_gesto(_gesto(P1, "sobe"), inicio)
    uniq, acesas, degrau = mesa.luzinhas[-1]
    assert (uniq, acesas) == (P1, (True, True, True, True, False))
    assert degrau == DEGRAU_DO_MEDIDOR == 0, "o brilho forte"
    assert player_bitmask(acesas) < 0x20, "o bit de esmaecer (0x20) nunca é escrito"  # type: ignore[arg-type]
    _andar(volta, mesa, inicio + 1.9)
    assert mesa.luzinhas[-1][1] == (True, True, True, True, False), "antes de 2 s segue no nível"
    _andar(volta, mesa, inicio + 2.05)
    assert mesa.luzinhas[-1] == (P1, ORIGINAL, 1), "volta ao número do jogador e ao brilho de antes"
    escritas = len(mesa.luzinhas)
    _andar(volta, mesa, inicio + 4.0)
    assert len(mesa.luzinhas) == escritas, "e não escreve mais nada"


def test_o_medidor_segue_o_nivel_que_chega_depois_do_gesto() -> None:
    volta, mesa = _volta()
    volta.ao_estado(_estado(2), mesa.agora)
    volta.ao_gesto(_gesto(P1, "sobe"), mesa.agora)
    assert mesa.luzinhas[-1][1] == (True, False, False, False, False)
    volta.ao_estado(_estado(3), mesa.agora)
    _andar(volta, mesa, mesa.agora + 0.02)
    assert mesa.luzinhas[-1][1] == (True, True, False, False, False)


def test_o_para_apaga_as_luzinhas() -> None:
    volta, mesa = _volta()
    volta.ao_estado(_estado(6), mesa.agora)
    volta.ao_gesto(_gesto(P1, "para"), mesa.agora)
    assert mesa.luzinhas[-1][1] == (False,) * 5


def test_na_camada_de_uma_mao_o_medidor_fica_enquanto_ela_vale() -> None:
    volta, mesa = _volta()
    volta.ao_estado(_estado(4), mesa.agora)
    inicio = mesa.agora
    volta.ao_gesto(_gesto(P1, "camada", 1), inicio)
    _andar(volta, mesa, inicio + 10.0)
    assert mesa.luzinhas[-1][1] == (True, True, False, False, False), "10 s depois ainda no medidor"
    volta.ao_gesto(_gesto(P1, "camada", 0), mesa.agora)
    _andar(volta, mesa, mesa.agora + 2.05)
    assert mesa.luzinhas[-1] == (P1, ORIGINAL, 1), "desligada a camada, volta ao número"


def test_o_medidor_so_mexe_nas_luzinhas_do_controle_do_gesto() -> None:
    volta, mesa = _volta()
    volta.ao_estado(_estado(5), mesa.agora)
    volta.ao_gesto(_gesto(P2, "sobe"), mesa.agora)
    assert {u for u, _, _ in mesa.luzinhas} == {P2}


# -- o toque de resposta ---------------------------------------------------------------------


def test_o_sobe_toca_o_motor_direito_fino_e_o_desce_o_esquerdo_grosso() -> None:
    volta, mesa = _volta()
    volta.ao_estado(_estado(5), mesa.agora)
    volta.ao_gesto(_gesto(P1, "sobe"), mesa.agora)
    assert mesa.motores[0][1:] == (P1, 200, 0), "fraco (direito) 200, forte (esquerdo) 0"
    _andar(volta, mesa, mesa.agora + 0.2)
    assert mesa.motores[-1][2:] == (0, 0), "e termina em zero"
    volta.ao_gesto(_gesto(P1, "desce"), mesa.agora)
    assert mesa.motores[-1][1:] == (P1, 0, 220)


def test_o_para_toca_dois_toques_longos_nos_dois_motores() -> None:
    volta, mesa = _volta()
    volta.ao_estado(_estado(8), mesa.agora)
    inicio = mesa.agora
    volta.ao_gesto(_gesto(P1, "para"), inicio)
    _andar(volta, mesa, inicio + 0.6, passo=0.002)
    pares = [(round(t - inicio, 2), f, s) for t, _, f, s in mesa.motores]
    assert [(f, s) for _, f, s in pares] == [(255, 255), (0, 0), (255, 255), (0, 0)]
    cheios = [t for t, f, _ in pares if f == 255]
    assert cheios[0] <= 0.01 and 0.25 <= cheios[1] <= 0.28, "dois toques, o segundo depois do vazio"


def test_no_nivel_10_o_sobe_toca_duas_vezes() -> None:
    volta, mesa = _volta()
    volta.ao_estado(_estado(10), mesa.agora)
    volta.ao_gesto(_gesto(P1, "sobe"), mesa.agora)
    _andar(volta, mesa, mesa.agora + 0.3, passo=0.002)
    assert [m[2] for m in mesa.motores].count(200) == 2, "o teto: toque duplo"


def test_trinta_gestos_em_um_segundo_nao_passam_de_doze_toques() -> None:
    volta, mesa = _volta()
    volta.ao_estado(_estado(5), mesa.agora)
    for i in range(30):
        volta.ao_gesto(_gesto(P1, "sobe"), mesa.agora)
        _andar(volta, mesa, 1000.0 + (i + 1) / 30.0, passo=0.004)
    toques = [m for m in mesa.motores if m[2] == 200]
    assert 10 <= len(toques) <= 12, f"{len(toques)} toques"


def test_sem_o_toque_de_confirmacao_o_motor_nao_toca_e_as_luzinhas_sim() -> None:
    volta, mesa = _volta(toque_de_confirmacao=False)
    volta.ao_estado(_estado(4, toque_de_confirmacao=False), mesa.agora)
    volta.ao_gesto(_gesto(P1, "sobe"), mesa.agora)
    _andar(volta, mesa, mesa.agora + 0.3)
    assert mesa.motores == []
    assert mesa.luzinhas, "as luzinhas seguem"


def test_o_gesto_que_nao_e_de_nivel_nao_toca() -> None:
    volta, mesa = _volta()
    volta.ao_estado(_estado(4), mesa.agora)
    for gesto in ("perfil_seguinte", "perfil_anterior", "nivel_ao_vivo", "surto"):
        volta.ao_gesto(_gesto(P1, gesto, 0.5), mesa.agora)
    assert mesa.motores == []


def test_o_toque_soma_ao_jogo_e_nao_escreve_o_zero_que_o_calaria() -> None:
    volta, mesa = _volta()
    volta.ao_estado(_estado(4), mesa.agora)
    mesa.vibra = True
    volta.ao_gesto(_gesto(P1, "sobe"), mesa.agora)
    _andar(volta, mesa, mesa.agora + 0.3)
    assert [m[2:] for m in mesa.motores] == [(200, 0)], "o jogo vibra: o quadro dele retoma"
    mesa.vibra = False
    volta.ao_gesto(_gesto(P1, "sobe"), mesa.agora)
    _andar(volta, mesa, mesa.agora + 0.3)
    assert mesa.motores[-1][2:] == (0, 0), "sem jogo vibrando, o toque devolve o zero"


def test_no_modo_nativo_nada_se_escreve() -> None:
    volta, mesa = _volta(pulso_da_barra=True)
    volta.ao_estado(_estado(4, pulso_da_barra=True), mesa.agora)
    mesa.pode = False
    volta.ao_gesto(_gesto(P1, "sobe"), mesa.agora)
    _andar(volta, mesa, mesa.agora + 0.5)
    resposta = volta.pulsar(P1, {"cor": VERMELHO, "periodo_s": 2}, mesa.agora)
    assert resposta == {"aplicado": False, "motivo": "modo_nativo"}
    assert (mesa.motores, mesa.luzinhas, mesa.barra) == ([], [], [])


# -- o pulso da barra ------------------------------------------------------------------------


def test_o_periodo_de_02_s_sai_como_1_s_e_nunca_passa_de_um_ciclo_por_segundo() -> None:
    volta, mesa = _com_o_pulso()
    resposta = volta.pulsar(P1, {"cor": VERMELHO, "periodo_s": 0.2}, mesa.agora)
    assert resposta["aplicado"] is True and resposta["periodo_s"] == 1.0
    inicio = mesa.agora
    _andar(volta, mesa, inicio + 3.0, passo=0.004)
    brilhos = _brilhos(mesa)
    teto = max(b for _, b in brilhos)
    cruzamentos = sum(
        1 for (_, antes), (_, depois) in pairwise(brilhos)
        if antes < teto / 2 <= depois
    )
    assert 2 <= cruzamentos <= 3, f"três segundos, no máximo três ciclos ({cruzamentos})"


def test_o_periodo_de_9_s_sai_como_4_s() -> None:
    volta, mesa = _com_o_pulso()
    assert volta.pulsar(P1, {"cor": VERMELHO, "periodo_s": 9}, mesa.agora)["periodo_s"] == 4.0


def test_o_pulso_sai_em_curva_a_partir_do_vale_e_com_no_maximo_15_escritas_por_segundo() -> None:
    volta, mesa = _com_o_pulso()
    volta.pulsar(P1, {"cor": [200, 0, 0], "fundo": 0.2, "periodo_s": 2}, mesa.agora)
    inicio = mesa.agora
    _andar(volta, mesa, inicio + 2.0, passo=0.002)
    brilhos = [b for _, b in _brilhos(mesa)]
    assert brilhos[0] == 40, "começa no vale: 20 % do brilho"
    assert max(brilhos) == 200 and brilhos.index(200) > 3, "sobe em curva ao pico e não pula"
    por_segundo = [t for t, _ in _brilhos(mesa) if t <= inicio + 1.0]
    assert len(por_segundo) <= 16, f"{len(por_segundo)} escritas no primeiro segundo"


def test_o_quadro_igual_ao_anterior_nao_sai() -> None:
    volta, mesa = _com_o_pulso(sem_pisca=True, nivel=10)
    volta.pulsar(P1, {"cor": [200, 100, 50], "periodo_s": 2}, mesa.agora)
    _andar(volta, mesa, mesa.agora + 3.0)
    assert len(mesa.barra) == 1, "o brilho está no teto: um quadro só"


def test_sem_a_marca_adulto_nada_se_escreve() -> None:
    volta, mesa = _com_o_pulso()
    mesa.marcas = frozenset({"visual_novel"})
    resposta = volta.pulsar(P1, {"cor": VERMELHO, "periodo_s": 2}, mesa.agora)
    assert resposta == {"aplicado": False, "motivo": "sem_a_marca_adulto"}
    _andar(volta, mesa, mesa.agora + 1.0)
    assert mesa.barra == []


def test_com_a_opcao_desligada_nada_se_escreve() -> None:
    volta, mesa = _volta()
    volta.ao_estado(_estado(3), mesa.agora)
    resposta = volta.pulsar(P1, {"cor": VERMELHO, "periodo_s": 2}, mesa.agora)
    assert resposta == {"aplicado": False, "motivo": "pulso_desligado"}
    assert mesa.barra == []


def test_o_jogo_que_pinta_a_barra_vence_e_o_pulso_em_curso_solta() -> None:
    volta, mesa = _com_o_pulso()
    mesa.pinta = True
    assert volta.pulsar(P1, {"cor": VERMELHO}, mesa.agora) == {
        "aplicado": False, "motivo": "o_jogo_pinta_a_barra"}
    assert mesa.barra == []
    mesa.pinta = False
    volta.pulsar(P1, {"cor": VERMELHO, "periodo_s": 2}, mesa.agora)
    _andar(volta, mesa, mesa.agora + 0.3)
    assert mesa.barra and volta.segurando_a_barra() == {P1}
    mesa.pinta = True
    _andar(volta, mesa, mesa.agora + 0.05)
    assert volta.segurando_a_barra() == frozenset() and mesa.soltas == [P1]


def test_a_marca_que_cai_com_o_perfil_solta_o_pulso() -> None:
    volta, mesa = _com_o_pulso()
    volta.pulsar(P1, {"cor": VERMELHO, "periodo_s": 2}, mesa.agora)
    mesa.marcas = frozenset()
    _andar(volta, mesa, mesa.agora + 0.05)
    assert volta.segurando_a_barra() == frozenset() and mesa.soltas == [P1]


def test_o_pulso_de_um_controle_nao_mexe_na_barra_do_outro() -> None:
    volta, mesa = _com_o_pulso()
    volta.pulsar(P2, {"cor": [0, 0, 255], "periodo_s": 2}, mesa.agora)
    _andar(volta, mesa, mesa.agora + 1.0)
    assert {u for _, u, _ in mesa.barra} == {P2}
    assert volta.segurando_a_barra() == {P2}
    volta.pulsar(P1, {"cor": VERMELHO, "periodo_s": 2}, mesa.agora)
    volta.pulsar(P2, {"parar": True}, mesa.agora)
    assert volta.segurando_a_barra() == {P1} and mesa.soltas == [P2]


def test_o_ligado_falso_solta_o_pulso_o_medidor_e_o_toque() -> None:
    volta, mesa = _com_o_pulso()
    volta.pulsar(P1, {"cor": VERMELHO, "periodo_s": 2}, mesa.agora)
    volta.ao_gesto(_gesto(P1, "para"), mesa.agora)
    _andar(volta, mesa, mesa.agora + 0.05)
    volta.ao_estado({"ligado": False, "nivel": 0, "aparelhos": [], "ajustes": {}}, mesa.agora)
    assert volta.segurando_a_barra() == frozenset() and mesa.soltas == [P1]
    assert mesa.luzinhas[-1] == (P1, ORIGINAL, 1), "as luzinhas voltam ao número"
    assert mesa.motores[-1][2:] == (0, 0), "e o toque no meio zera os motores"


def test_sem_pisca_o_brilho_so_acompanha_o_nivel_e_devagar() -> None:
    volta, mesa = _com_o_pulso(sem_pisca=True, nivel=1)
    volta.pulsar(P1, {"cor": [200, 100, 50]}, mesa.agora)
    assert mesa.barra[0][2] == (20, 10, 5), "nível 1 = 10 % da cor"
    volta.ao_estado(_estado(10, pulso_da_barra=True, sem_pisca=True), mesa.agora)
    _andar(volta, mesa, mesa.agora + 0.1)
    assert max(mesa.barra[-1][2]) < 100, "devagar: 0,1 s depois ainda está longe do teto"
    _andar(volta, mesa, mesa.agora + 3.0)
    assert mesa.barra[-1][2] == (200, 100, 50), "nível 10 = o brilho todo da cor"
    sequencia = [max(rgb) for _, _, rgb in mesa.barra]
    assert sequencia == sorted(sequencia), "sobe sem piscar"


def test_a_cor_que_esquenta_mistura_pela_nivel() -> None:
    volta, mesa = _com_o_pulso(sem_pisca=True, nivel=10)
    volta.pulsar(P1, {"cor": [0, 0, 200], "cor_quente": [200, 0, 0]}, mesa.agora)
    assert mesa.barra[0][2] == (200, 0, 0), "no 10, a cor quente inteira"
    volta, mesa = _com_o_pulso(sem_pisca=True, nivel=1)
    volta.pulsar(P1, {"cor": [0, 0, 200], "cor_quente": [200, 0, 0]}, mesa.agora)
    assert mesa.barra[0][2] == (0, 0, 20), "no 1, a cor fria a 10 %"


def test_o_parar_solta_a_barra() -> None:
    volta, mesa = _com_o_pulso()
    volta.pulsar(P1, {"cor": VERMELHO, "periodo_s": 2}, mesa.agora)
    assert volta.pulsar(P1, {"parar": True}, mesa.agora) == {"aplicado": True, "motivo": "solto"}
    assert mesa.soltas == [P1] and volta.segurando_a_barra() == frozenset()
    assert volta.pulsar(P1, {"parar": True}, mesa.agora)["aplicado"] is False


# -- o laço do tato vivo ----------------------------------------------------------------------


def test_o_passo_anda_a_volta_mesmo_sem_receita_e_sem_jogo() -> None:
    volta, mesa = _volta()
    motor = tv.TatoVivo()
    motor.volta = volta
    volta.ao_estado(_estado(4), mesa.agora)
    volta.ao_gesto(_gesto(P1, "sobe"), mesa.agora)
    tv.Passo(SimpleNamespace(), motor)(mesa.agora + 2.5)
    assert mesa.luzinhas[-1] == (P1, ORIGINAL, 1), "o tique do passo devolveu as luzinhas"
    assert motor.ligado is False, "e a receita seguiu desligada"


def test_o_efeito_do_perfil_espera_pela_barra_que_o_pulso_segura() -> None:
    volta, mesa = _com_o_pulso()
    motor = tv.TatoVivo()
    motor.volta = volta
    assert motor.segurando(tv.CANAL_LUZ) == frozenset()
    volta.pulsar(P1, {"cor": VERMELHO, "periodo_s": 2}, mesa.agora)
    assert motor.segurando(tv.CANAL_LUZ) == {P1}


def test_a_fila_traz_os_gestos_antes_do_estado_que_vem_depois() -> None:
    async def corrida() -> None:
        bus = EventBus()
        gestos = bus.subscribe(EventTopic.ACESSORIOS_GESTO)
        estados = bus.subscribe(EventTopic.ACESSORIOS_ESTADO)
        volta, mesa = _volta()
        volta.ao_estado(_estado(10), mesa.agora)
        bus.publish(EventTopic.ACESSORIOS_GESTO, _gesto(P1, "sobe"))
        bus.publish(EventTopic.ACESSORIOS_ESTADO, _estado(9))
        volta.drenar(gestos, estados, mesa.agora)
        assert mesa.luzinhas[-1][1] == (True, True, True, True, True), "o estado de 9 chegou"
        _andar(volta, mesa, mesa.agora + 0.3, passo=0.002)
        assert [m[2] for m in mesa.motores].count(200) == 2, "o 10 valia quando o gesto chegou"

    asyncio.run(corrida())


# -- a porta -----------------------------------------------------------------------------------


@pytest.fixture
def curto() -> Iterator[Path]:
    base = "/var/tmp" if os.access("/var/tmp", os.W_OK) else None
    pasta = Path(tempfile.mkdtemp(prefix="hv", dir=base))
    try:
        yield pasta
    finally:
        shutil.rmtree(pasta, ignore_errors=True)


class _Cliente:
    def __init__(self, caminho: Path) -> None:
        import json

        self._json = json
        self.sock = socket.socket(socket.AF_UNIX)
        self.sock.connect(str(caminho))
        self.arquivo = self.sock.makefile("rb")
        self.proximo = 0

    def pedir(self, metodo: str, params: dict[str, Any]) -> dict[str, Any]:
        self.proximo += 1
        linha = {"jsonrpc": "2.0", "id": self.proximo, "method": metodo, "params": params}
        self.sock.sendall(self._json.dumps(linha).encode() + b"\n")
        while True:
            resposta: dict[str, Any] = self._json.loads(self.arquivo.readline())
            if resposta.get("id") == self.proximo:
                return resposta

    def fechar(self) -> None:
        self.arquivo.close()
        self.sock.close()


async def _porta(
    curto: Path, permissoes: list[str], volta: VoltaDosAcessorios, mesa: Mesa,
    o_jogo_escreve: Any = lambda uniq, canal: False,
) -> Porta:
    async def escritor(metodo: str, pedido: dict[str, Any]) -> Any:
        return {"status": "ok"}

    porta = Porta(
        curto / "mods.sock", EventBus(), escritor=escritor, o_jogo_escreve=o_jogo_escreve,
        uniq_do_posto=lambda: P1,
        pulsador=lambda uniq, pedido: volta.pulsar(uniq, pedido, mesa.agora))
    await porta.iniciar()
    porta.registrar("ficha", "brinquedos", os.getpid(), permissoes)
    return porta


async def _pedir(curto: Path, metodo: str, params: dict[str, Any]) -> dict[str, Any]:
    cliente = _Cliente(curto / "mods.sock")
    try:
        await asyncio.to_thread(cliente.pedir, "mod.ola", {"ficha": "ficha"})
        return await asyncio.to_thread(cliente.pedir, metodo, params)
    finally:
        cliente.fechar()


def test_sem_a_permissao_a_porta_recusa_com_o_nome_dela(curto: Path) -> None:
    async def corrida() -> None:
        volta, mesa = _com_o_pulso()
        porta = await _porta(curto, ["ler:acessorios.gesto"], volta, mesa)
        resposta = await _pedir(curto, "luz.pulso", {"uniq": P1, "cor": VERMELHO})
        assert resposta["error"]["code"] == CODE_SEM_PERMISSAO
        assert "pedir:luz.pulso" in resposta["error"]["message"]
        assert mesa.barra == []
        await porta.parar()

    asyncio.run(corrida())


def test_com_a_permissao_a_porta_aplica_e_o_periodo_curto_sai_como_1_s(curto: Path) -> None:
    async def corrida() -> None:
        volta, mesa = _com_o_pulso()
        porta = await _porta(curto, ["pedir:luz.pulso"], volta, mesa)
        resposta = await _pedir(
            curto, "luz.pulso", {"uniq": P1, "cor": VERMELHO, "fundo": 0, "periodo_s": 0.2})
        assert resposta["result"]["aplicado"] is True
        assert resposta["result"]["periodo_s"] == 1.0
        assert {u for _, u, _ in mesa.barra} == {P1}
        await porta.parar()

    asyncio.run(corrida())


def test_o_jogo_que_pinta_a_barra_faz_a_porta_recusar(curto: Path) -> None:
    async def corrida() -> None:
        volta, mesa = _com_o_pulso()
        porta = await _porta(
            curto, ["pedir:luz.pulso"], volta, mesa, lambda uniq, canal: canal == "luz")
        resposta = await _pedir(curto, "luz.pulso", {"uniq": P1, "cor": VERMELHO})
        assert resposta["error"]["code"] == CODE_O_JOGO_ESCREVE
        assert mesa.barra == []
        await porta.parar()

    asyncio.run(corrida())


def test_o_pedido_do_pulso_sem_uniq_ou_com_cor_ruim_e_recusado(curto: Path) -> None:
    async def corrida() -> None:
        volta, mesa = _com_o_pulso()
        porta = await _porta(curto, ["pedir:luz.pulso"], volta, mesa)
        for params in (
            {"cor": VERMELHO},
            {"uniq": P1, "cor": [1, 2]},
            {"uniq": P1, "cor": [1, 2, 300]},
            {"uniq": P1, "cor": VERMELHO, "fundo": 3},
            {"uniq": P1, "cor": VERMELHO, "periodo_s": "rápido"},
        ):
            resposta = await _pedir(curto, "luz.pulso", params)
            assert resposta["error"]["code"] == CODE_INVALID_PARAMS, params
        assert mesa.barra == []
        await porta.parar()

    asyncio.run(corrida())


def test_o_parar_pela_porta_solta_a_barra_do_controle(curto: Path) -> None:
    async def corrida() -> None:
        volta, mesa = _com_o_pulso()
        porta = await _porta(curto, ["pedir:luz.pulso"], volta, mesa)
        await _pedir(curto, "luz.pulso", {"uniq": P1, "cor": VERMELHO})
        resposta = await _pedir(curto, "luz.pulso", {"uniq": P1, "parar": True})
        assert resposta["result"] == {"aplicado": True, "motivo": "solto"}
        assert mesa.soltas == [P1]
        await porta.parar()

    asyncio.run(corrida())


def test_a_permissao_nova_e_conhecida_e_as_opcoes_do_pulso_passam_pelo_estado() -> None:
    assert permissao_valida("pedir:luz.pulso")
    estado = estado_dos_acessorios("brinquedos", {
        "ligado": True, "nivel": 3, "aparelhos": ["Um"],
        "ajustes": {"pulso_da_barra": True, "sem_pisca": True, "segredo": 1}})
    assert estado["ajustes"] == {"pulso_da_barra": True, "sem_pisca": True}
