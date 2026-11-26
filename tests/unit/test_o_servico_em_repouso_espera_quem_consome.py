"""O serviço em repouso espera quem consome.

Repouso é «nenhum consumidor com algo a tocar ou desenhar», não «sem jogo»: o laço do tato vivo
repousa quando a receita está desligada, nenhuma extensão assina o som do jogo, a fonte de fora
não tem pedido nem toque, a volta dos acessórios e os meus toques não têm trabalho; o laço da luz
repousa quando o plano de todos os controles está vazio. Em repouso o passo é de 250 ms, e o
pedido de uma extensão, o gesto de um acessório e a saída de uma extensão acordam o laço do tato
no mesmo instante. Com consumidor, o passo é o de sempre.

Não há estado por controle nesta cura: o repouso é do serviço, e a pergunta «alguém consome?»
olha os pedidos de todos os controles de uma vez. A prova usa quatro controles só para mostrar
que o pedido de qualquer um deles acorda o laço.

O governador do rádio só tem fio enquanto houver ponte, pedido, espera ou autorização: sem
controle no rádio, o fio que fechou as pontes fantasmas sai, e o ar se mede só quando alguém
pergunta (a aba Conexões segue com a medida).

MORDIDAS: o fio do governador que nunca repousa dá fio vivo e amostras sem pedido; o
``pedir_vaga`` sem ``_garantir_o_fio`` deixa a ponte sem tique; o ``repouso`` sempre falso no
laço do tato dá o passo de 60 Hz em repouso; sem o ``_acordar_o_laco`` do ``pedir`` o pedido
espera o passo de repouso; sem o ``_acordar_com`` dos gestos o gesto espera o passo de repouso;
sem o ``em_repouso`` da luz o laço da luz segue a 30 Hz com o plano vazio.
"""
from __future__ import annotations

import asyncio
import threading
import time
from types import SimpleNamespace
from typing import Any

import pytest

from hefesto_dualsense4unix.core.events import EventBus, EventTopic
from hefesto_dualsense4unix.daemon.subsystems import governador_do_radio as gov
from hefesto_dualsense4unix.daemon.subsystems import luz_animada as luz
from hefesto_dualsense4unix.daemon.subsystems import tato_vivo as tv
from tests.unit.test_a_luz_animada_obedece_a_bateria_longa import (
    _declaracao,
    _passo,
    economia,  # noqa: F401
)

UNIQS = tuple(f"aa:bb:cc:00:00:{n:02x}" for n in (0x61, 0x62, 0x63, 0x64))
EXT = tv.PREFIXO_DA_EXTENSAO + "imersao"


class _Cena:
    def __init__(self, monkeypatch: pytest.MonkeyPatch, *, bus: Any = None,
                 volta: Any = None) -> None:
        self.tiques: list[float] = []
        monkeypatch.setattr(
            tv.Passo, "tique_do_laco", lambda _p, agora: self.tiques.append(agora) or 0)
        self.parar = asyncio.Event()
        self.daemon = SimpleNamespace(_is_stopping=self.parar.is_set, bus=bus)
        self.motor = tv.TatoVivo([])
        self.motor.ouvido = SimpleNamespace(parar=lambda: None)
        self.motor.volta = volta
        self.laco: asyncio.Task[None] | None = None

    def subir(self) -> None:
        self.laco = asyncio.create_task(tv.tato_vivo_loop(self.daemon, self.motor))

    async def descer(self) -> None:
        self.parar.set()
        assert self.laco is not None
        await asyncio.wait_for(self.laco, 3.0)

    async def contar(self, segundos: float) -> int:
        antes = len(self.tiques)
        await asyncio.sleep(segundos)
        return len(self.tiques) - antes


def _correr(roteiro: Any, monkeypatch: pytest.MonkeyPatch, **cena: Any) -> Any:
    async def corrida() -> Any:
        mesa = _Cena(monkeypatch, **cena)
        mesa.subir()
        try:
            return await roteiro(mesa)
        finally:
            await mesa.descer()

    return asyncio.run(corrida())


def test_sem_consumidor_o_laco_do_tato_nao_roda_a_60_hz(monkeypatch: pytest.MonkeyPatch) -> None:
    """D-2111-O-LACO-EM-REPOUSO-TEM-O-PASSO-DE-250-MS: sem consumidor o laço repousa no passo de
    250 ms e o pedido de uma extensão o acorda no mesmo instante."""
    async def roteiro(mesa: _Cena) -> int:
        await asyncio.sleep(0.1)
        return await mesa.contar(1.0)

    tiques = _correr(roteiro, monkeypatch)
    assert tiques <= 6, f"o laço sem consumidor rodou {tiques} vezes em 1 s"


def test_com_a_fonte_de_fora_viva_o_laco_anda_a_60_hz_e_depois_do_prazo_repousa(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def roteiro(mesa: _Cena) -> tuple[int, int]:
        await asyncio.sleep(0.1)
        agora = time.monotonic()
        assert mesa.motor.de_fora.pedir(EXT, "luz", UNIQS[2], {"centro": 0.5}, agora,
                                        ate_s=0.6).vale
        durante = await mesa.contar(0.4)
        await asyncio.sleep(0.5)
        return durante, await mesa.contar(1.0)

    durante, depois = _correr(roteiro, monkeypatch)
    assert durante >= 10, f"com o pedido vivo o laço rodou só {durante} vezes em 0,4 s"
    assert depois <= 6, f"vencido o prazo o laço seguiu a {depois} por segundo"


def test_com_os_meus_toques_a_andar_o_laco_nao_repousa(monkeypatch: pytest.MonkeyPatch) -> None:
    async def roteiro(mesa: _Cena) -> int:
        mesa.motor.meus_toques = SimpleNamespace(precisa_andar=lambda: True)
        await asyncio.sleep(0.3)
        return await mesa.contar(0.5)

    assert _correr(roteiro, monkeypatch) >= 15


@pytest.mark.parametrize("i", range(4))
def test_o_pedido_de_qualquer_controle_acorda_o_laco_de_repouso(
    monkeypatch: pytest.MonkeyPatch, i: int,
) -> None:
    async def roteiro(mesa: _Cena) -> int:
        await asyncio.sleep(0.4)
        assert mesa.motor.de_fora.pedir(EXT, "luz", UNIQS[i], {"centro": 0.5},
                                        time.monotonic(), ate_s=5.0).vale
        return await mesa.contar(0.15)

    tiques = _correr(roteiro, monkeypatch)
    assert tiques >= 4, f"o pedido do controle {i} esperou o passo de repouso ({tiques} tiques)"


def test_o_pedido_do_corpo_e_a_saida_da_extensao_acordam_o_laco(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def roteiro(mesa: _Cena) -> tuple[int, int]:
        await asyncio.sleep(0.4)
        mesa.motor.de_fora.corpo.pedir(
            EXT, UNIQS[1], tv.PedidoDoCorpo(0.5, None, 0.0), 300)
        do_corpo = await mesa.contar(0.15)
        await asyncio.sleep(0.6)
        await mesa.contar(0.4)
        mesa.motor.de_fora.esquecer(EXT)
        return do_corpo, await mesa.contar(0.15)

    do_corpo, da_saida = _correr(roteiro, monkeypatch)
    assert do_corpo >= 4, f"o pedido do corpo esperou o passo de repouso ({do_corpo} tiques)"
    assert da_saida >= 1


def test_o_gesto_do_acessorio_acorda_o_laco_de_repouso(monkeypatch: pytest.MonkeyPatch) -> None:
    drenados: list[float] = []

    class _Volta:
        def drenar(self, gestos: asyncio.Queue[Any], estados: asyncio.Queue[Any],
                   _agora: float) -> None:
            while not gestos.empty():
                gestos.get_nowait()
                drenados.append(time.monotonic())
            while not estados.empty():
                estados.get_nowait()

        def soltar_tudo(self, _agora: float) -> None:
            return None

    bus = EventBus()

    async def roteiro(mesa: _Cena) -> float:
        await asyncio.sleep(0.3)
        visto = len(mesa.tiques)
        while len(mesa.tiques) == visto:
            await asyncio.sleep(0.001)
        publicado = time.monotonic()
        bus.publish(EventTopic.ACESSORIOS_GESTO, {"uniq": UNIQS[0], "gesto": "sobe"})
        await asyncio.sleep(0.2)
        assert drenados, "o gesto não chegou à volta"
        return drenados[0] - publicado

    espera = _correr(roteiro, monkeypatch, bus=bus, volta=_Volta())
    assert espera < 0.1, f"o gesto esperou {espera:.3f} s pelo passo de repouso"


def test_o_passo_diz_ocioso_so_sem_nenhum_consumidor() -> None:
    motor = tv.TatoVivo([])
    passo = tv.Passo(SimpleNamespace(bus=None), motor)
    assert passo.ocioso()
    motor.ligado = True
    assert not passo.ocioso()
    motor.ligado = False
    motor.meus_toques = SimpleNamespace(precisa_andar=lambda: True)
    assert not passo.ocioso()
    motor.meus_toques = None
    motor.volta = SimpleNamespace(_toques={UNIQS[0]: object()})
    assert not passo.ocioso()
    motor.volta = None
    motor.de_fora.pedir(EXT, "luz", UNIQS[3], {"centro": 0.5}, time.monotonic(), ate_s=1.0)
    assert not passo.ocioso()
    bus = EventBus()
    bus.subscribe(EventTopic.JOGO_SOM)
    assert not tv.Passo(SimpleNamespace(bus=bus), tv.TatoVivo([])).ocioso()


def test_o_laco_da_luz_repousa_com_o_plano_vazio_e_volta_ao_passo_com_efeito(
    monkeypatch: pytest.MonkeyPatch, economia: dict[str, Any],  # noqa: F811
) -> None:
    passo, _barra = _passo(monkeypatch)
    assert passo(10.0) == 1
    assert not passo.em_repouso, "com efeito no perfil a luz não repousa"
    economia["declaracao"] = _declaracao(mesa=True)
    passo(11.0)
    assert passo.em_repouso, "sem plano a luz não repousou"
    economia["declaracao"] = _declaracao()
    passo(12.0)
    assert not passo.em_repouso, "o efeito voltou e a luz seguiu em repouso"


def test_o_laco_da_luz_dorme_o_passo_de_repouso_quando_em_repouso(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tiques: list[float] = []

    def tique(passo: Any, agora: float) -> int:
        tiques.append(agora)
        passo.em_repouso = True
        return 0

    monkeypatch.setattr(luz.Passo, "tique_do_laco", tique)
    parar = asyncio.Event()
    daemon = SimpleNamespace(_is_stopping=parar.is_set)
    laco = SimpleNamespace(parar_tudo=lambda: None)

    async def corrida() -> None:
        tarefa = asyncio.create_task(luz.luz_animada_loop(daemon, laco))
        await asyncio.sleep(1.0)
        parar.set()
        await asyncio.wait_for(tarefa, 3.0)

    asyncio.run(corrida())
    assert len(tiques) <= 6, f"a luz sem plano rodou {len(tiques)} vezes em 1 s"


ADAPTADOR = "aa:bb:cc:00:00:a1"


class _Medidor:
    def __init__(self) -> None:
        self.amostras = 0

    def amostrar(self) -> dict[str, Any]:
        self.amostras += 1
        return {ADAPTADOR: SimpleNamespace(motivo="")}


def _governador(medidor: _Medidor, periodo_s: float = 0.01) -> gov.GovernadorDoRadio:
    return gov.GovernadorDoRadio(
        medidor=medidor,
        n_max=len(UNIQS),
        adaptador_de=lambda _u: ADAPTADOR,
        registrar=lambda *_a, **_k: None,
        ler_o_diario=lambda: [],
        periodo_s=periodo_s,
    )


def _o_fio_saiu(governador: gov.GovernadorDoRadio, prazo_s: float = 3.0) -> bool:
    limite = time.monotonic() + prazo_s
    while time.monotonic() < limite:
        if governador.em_repouso():
            return True
        time.sleep(0.005)
    return False


def _fios_do_governador() -> list[threading.Thread]:
    return [f for f in threading.enumerate() if f.name == "hefesto-governador" and f.is_alive()]


def test_o_governador_sem_controle_no_radio_nao_tem_fio_nem_mede_sozinho() -> None:
    medidor = _Medidor()
    governador = _governador(medidor)
    governador.iniciar()
    try:
        assert _o_fio_saiu(governador), "sem ponte nem pedido, o fio do governador seguiu de pé"
        assert not _fios_do_governador()
        antes = medidor.amostras
        time.sleep(0.2)
        assert medidor.amostras == antes, "o governador em repouso mediu o ar sem ninguém pedir"
    finally:
        governador.parar()


def test_o_pedido_de_vaga_sobe_o_fio_e_a_saida_da_ultima_ponte_o_derruba() -> None:
    medidor = _Medidor()
    governador = _governador(medidor)
    governador.iniciar()
    try:
        assert _o_fio_saiu(governador)
        vaga = governador.pedir_vaga("aa:bb:cc:00:00:01", "som")
        assert isinstance(vaga, gov.Vaga)
        vaga.subiu()
        assert not governador.em_repouso(), "a ponte de pé ficou sem o tique do governador"
        antes = medidor.amostras
        time.sleep(0.1)
        assert medidor.amostras > antes, "com ponte de pé o governador não mediu o ar"
        vaga.soltar()
        assert _o_fio_saiu(governador), "a última ponte saiu e o fio do governador seguiu"
    finally:
        governador.parar()


def test_quatro_controles_no_radio_um_fio_so_ate_o_ultimo_sair() -> None:
    governador = _governador(_Medidor())
    governador.iniciar()
    try:
        assert _o_fio_saiu(governador)
        vagas = []
        for uniq in UNIQS:
            vaga = governador.pedir_vaga(uniq, "som")
            assert isinstance(vaga, gov.Vaga)
            vaga.subiu()
            vagas.append(vaga)
        assert len(_fios_do_governador()) == 1
        for vaga in vagas[:-1]:
            vaga.soltar()
            time.sleep(0.03)
            assert not governador.em_repouso(), "o fio saiu com um controle ainda no rádio"
        vagas[-1].soltar()
        assert _o_fio_saiu(governador)
    finally:
        governador.parar()


def test_em_repouso_a_aba_que_pergunta_o_ar_recebe_a_medida_de_agora() -> None:
    medidor = _Medidor()
    governador = _governador(medidor, periodo_s=0.05)
    governador.iniciar()
    try:
        assert _o_fio_saiu(governador)
        time.sleep(0.06)
        antes = medidor.amostras
        assert governador.ultima_amostra() is not None
        assert medidor.amostras == antes + 1
        governador.ultima_amostra()
        assert medidor.amostras == antes + 1, "duas perguntas no mesmo período mediram duas vezes"
    finally:
        governador.parar()


def test_parado_o_governador_nao_sobe_fio_no_pedido() -> None:
    governador = _governador(_Medidor())
    governador.iniciar()
    governador.parar()
    governador.pedir_vaga("aa:bb:cc:00:00:01", "som")
    assert not _fios_do_governador()
