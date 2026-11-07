"""O diário diz o que o corpo tocou (O-DIARIO-DIZ-O-QUE-O-CORPO-TOCOU-01).

A linha do minuto, a recusa com motivo, a borda do ouvido surdo e o ganho do cabo confirmado.
Tudo com o ``Passo``, o ``AltoFalante`` e o ``DiarioDoCorpo`` do produto; só o relógio e o tocador
são dublês.
"""
from __future__ import annotations

import asyncio
import threading
from array import array
from types import MappingProxyType, SimpleNamespace
from typing import Any

import pytest
import structlog.testing

from hefesto_dualsense4unix.cli import cmd_doctor, ipc_client
from hefesto_dualsense4unix.core.sysfs_leds import norm_mac
from hefesto_dualsense4unix.daemon import state_store
from hefesto_dualsense4unix.daemon.subsystems import alto_falante as af
from hefesto_dualsense4unix.daemon.subsystems import diario_do_corpo as dc
from hefesto_dualsense4unix.daemon.subsystems import tato_vivo as tv
from hefesto_dualsense4unix.integrations import transiente_do_jogo as tj
from hefesto_dualsense4unix.integrations.haptica_do_cabo import HapticaDoCabo, RotaDoCabo
from hefesto_dualsense4unix.profiles import formas_de_haptica as fh
from hefesto_dualsense4unix.utils import logging_config as lc

P = tuple(f"aa:bb:cc:00:00:{i:02x}" for i in range(1, 5))
COR = dict(zip(P, ("Cosmic Red", "Starlight Blue", "White", "Galactic Purple"), strict=True))
_XBOX = tv.EstadoDoCanal(modo=tv.MODO_XBOX, ha_jogo=True)
_NATIVO = tv.EstadoDoCanal(modo=tv.MODO_NATIVO, ha_jogo=True)
_JOGO_NO_ENDPOINT = tv.EstadoDoCanal(
    modo=tv.MODO_DUALSENSE, visto_ha_s={"audio_do_jogo": 0.2}, sessao_aberta=True, ha_jogo=True)


def _pcm(quadros: int, nivel: int = 12000) -> bytes:
    fase = []
    for i in range(quadros):
        v = nivel if (i // 240) % 2 == 0 else -nivel
        fase += [v, v]
    return array("h", fase).tobytes()


class _Alto:
    """O ``tocar_o_corpo`` que responde o desfecho pedido para cada controle."""

    def __init__(self, recusas: dict[str, str] | None = None) -> None:
        self.recusas = recusas or {}
        self.tocados: list[str] = []

    def tocar_o_corpo(self, uniq: str, _amostras: Any, _lado: str = "centro") -> dc.DesfechoDoCorpo:
        self.tocados.append(uniq)
        return dc.DesfechoDoCorpo(self.recusas.get(uniq))


def _passo(alto: Any, *, cores: dict[str, str] | None = None) -> tv.Passo:
    motor = tv.TatoVivo([])
    motor.escolhas = {norm_mac(u): fh.SOM_NO_CORPO for u in P}
    tabela = COR if cores is None else cores
    registro = SimpleNamespace(
        identidade_de_fabrica=lambda u: SimpleNamespace(cor=SimpleNamespace(nome=tabela.get(u))))
    daemon = SimpleNamespace(
        _alto_falante_subsystem=alto, identity_registry=registro,
        store=state_store.StateStore())
    passo = tv.Passo(daemon, motor)
    passo.receita_vigente = tv.Receita(som_no_corpo_escolhido=True)
    return passo


def _levar(passo: tv.Passo, uniqs: tuple[str, ...], estado_de: Any = lambda _u: _XBOX) -> None:
    passo.alimentar_o_corpo(_pcm(960))
    passo._levar_o_corpo(passo.receita_vigente, uniqs, estado_de)


def _fechar(passo: tv.Passo, *, jogo: bool = True) -> list[dict[str, Any]]:
    passo.jogo = jogo
    with structlog.testing.capture_logs() as linhas:
        passo.andar_o_diario(0.0)
        passo.andar_o_diario(dc.JANELA_DO_MINUTO_S)
    return [x for x in linhas if x["event"] == "tato_corpo_minuto"]


def test_a_recusa_sobe_o_contador_certo_e_a_linha_traz_o_numero() -> None:
    passo = _passo(_Alto({P[0]: dc.RECUSA_RADIO_CEDE}))
    for _ in range(3):
        _levar(passo, (P[0],))
    [linha] = _fechar(passo)
    assert linha["controles"] == {"Cosmic Red": {"blocos": 0, "recusas": {"radio_cede": 3}}}
    assert linha["pcm_lido"] == 3 * 960 * 4
    assert passo.daemon.store.counter("corpo.controle.Cosmic Red.recusa.radio_cede") == 3


def test_o_que_tocou_conta_e_sobe_ao_store_so_no_minuto() -> None:
    passo = _passo(_Alto())
    _levar(passo, (P[0], P[1]))
    store = passo.daemon.store
    assert store.counter("corpo.controle.Cosmic Red.blocos") == 0, "subiu a cada bloco"
    [linha] = _fechar(passo)
    assert linha["controles"]["Cosmic Red"]["blocos"] == 1
    assert linha["controles"]["Starlight Blue"]["blocos"] == 1
    assert store.counter("corpo.controle.Cosmic Red.blocos") == 1
    assert store.counter(dc.CHAVE_DO_PCM) == 960 * 4


def test_bloco_sem_sinal_nao_conta_como_tocado() -> None:
    alto = _Alto()
    passo = _passo(alto)
    passo.alimentar_o_corpo(bytes(3840))
    passo._levar_o_corpo(passo.receita_vigente, (P[0],), lambda _u: _XBOX)
    assert alto.tocados == [P[0]]
    [linha] = _fechar(passo)
    assert linha["controles"] == {}


def test_passo_do_diario_que_falha_nao_derruba_a_tarefa(monkeypatch: pytest.MonkeyPatch) -> None:
    passo = _passo(_Alto())

    def quebra() -> None:
        raise OSError("lista ilegível")

    monkeypatch.setattr(passo, "_ler_a_lista_do_steam_input", quebra)
    passo.andar_o_diario(0.0)


def test_minuto_sem_jogo_nao_tem_linha() -> None:
    passo = _passo(_Alto())
    _levar(passo, (P[0],))
    assert _fechar(passo, jogo=False) == []


def test_minuto_com_jogo_sem_ninguem_pedir_o_som_nao_tem_linha() -> None:
    passo = _passo(_Alto())
    passo.receita_vigente = tv.DESLIGADA
    assert _fechar(passo) == []


def test_a_linha_sai_uma_vez_por_minuto() -> None:
    passo = _passo(_Alto())
    passo.jogo = passo.motor.ligado = True
    with structlog.testing.capture_logs() as linhas:
        for t in range(0, 300, 5):
            passo.andar_o_diario(float(t))
    assert len([x for x in linhas if x["event"] == "tato_corpo_minuto"]) == 4


def test_no_nativo_nada_toca_e_nada_e_recusa() -> None:
    alto = _Alto()
    passo = _passo(alto)
    _levar(passo, (P[0],), lambda _u: _NATIVO)
    assert alto.tocados == []
    [linha] = _fechar(passo)
    assert linha["controles"] == {}


def test_jogo_no_endpoint_e_recusa_com_nome_proprio() -> None:
    passo = _passo(_Alto())
    _levar(passo, (P[0],), lambda _u: _JOGO_NO_ENDPOINT)
    [linha] = _fechar(passo)
    assert linha["controles"]["Cosmic Red"]["recusas"] == {dc.RECUSA_JOGO_NO_ENDPOINT: 1}


def test_a_economia_diz_que_calou(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(tv, "_controle_na_economia", lambda _u: True)
    passo = _passo(_Alto())
    _levar(passo, (P[0],))
    [linha] = _fechar(passo)
    assert linha["controles"]["Cosmic Red"]["recusas"] == {dc.RECUSA_ECONOMIA: 1}


def test_pro_e_8bitdo_nao_geram_recusa_falsa() -> None:
    passo = _passo(_Alto({P[0]: dc.RECUSA_SEM_APARELHO}))
    passo._externos = frozenset({P[0]})
    _levar(passo, (P[0],))
    [linha] = _fechar(passo)
    assert linha["controles"] == {}


def test_o_controle_externo_vem_marcado_do_coop() -> None:
    pad = SimpleNamespace(externo=True, reader=None, vpad=None)
    daemon = SimpleNamespace(_coop_manager=SimpleNamespace(_players={P[0]: pad}))
    assert [c.externo for c in tv.controles_do_daemon(daemon)] == [True]


def test_a_continua_tambem_conta_a_recusa() -> None:
    passo = _passo(_Alto({P[0]: dc.RECUSA_FORCA_ZERO}))
    passo._levar_a_continua(P[0], array("f", [0.5]))
    [linha] = _fechar(passo)
    assert linha["controles"]["Cosmic Red"]["recusas"] == {dc.RECUSA_FORCA_ZERO: 1}


@pytest.mark.parametrize(
    "mesa",
    [(P[0], P[1], P[2], P[3]), (P[2],), (P[0], P[2]), (P[3], P[0], P[1])],
    ids=["os-quatro", "so-o-p3", "buraco-no-meio", "ordem-trocada"],
)
def test_a_linha_separa_cada_controle_com_o_proprio_motivo(mesa: tuple[str, ...]) -> None:
    """A conexão não entra na conta: um motivo por controle, em qualquer lugar da mesa."""
    motivos = dict(zip(P, (dc.RECUSA_RADIO_CEDE, None, dc.RECUSA_SEM_ENDPOINT,
                           dc.RECUSA_FORCA_ZERO), strict=True))
    passo = _passo(_Alto({u: m for u, m in motivos.items() if m is not None}))
    _levar(passo, mesa)
    [linha] = _fechar(passo)
    for uniq in mesa:
        conta = linha["controles"][COR[uniq]]
        motivo = motivos[uniq]
        assert conta == (
            {"blocos": 0, "recusas": {motivo: 1}} if motivo else {"blocos": 1, "recusas": {}})
    assert len(linha["controles"]) == len(mesa)


def test_dois_da_mesma_cor_nao_se_misturam() -> None:
    passo = _passo(_Alto({P[1]: dc.RECUSA_RADIO_CEDE}), cores={P[0]: "White", P[1]: "White"})
    _levar(passo, (P[0], P[1]))
    [linha] = _fechar(passo)
    assert linha["controles"] == {
        "White": {"blocos": 1, "recusas": {}},
        "White #2": {"blocos": 0, "recusas": {"radio_cede": 1}},
    }


def test_sem_cor_lida_o_rotulo_nao_vira_endereco() -> None:
    passo = _passo(_Alto(), cores={})
    _levar(passo, (P[0], P[1]))
    passo.jogo = True
    [linha] = _fechar(passo)
    assert sorted(linha["controles"]) == [dc.SEM_COR, f"{dc.SEM_COR} #2"]
    assert not [c for c in passo.daemon.store.snapshot().counters if ":" in c or "aabbcc" in c]


def test_a_cor_lida_depois_troca_o_rotulo_provisorio() -> None:
    cores: dict[str, str] = {}
    passo = _passo(_Alto(), cores=cores)
    assert passo.diario_do_corpo.rotulo(P[0]) == dc.SEM_COR
    assert passo.diario_do_corpo.rotulo(P[1]) == f"{dc.SEM_COR} #2"
    cores[P[0]] = "White"
    assert passo.diario_do_corpo.rotulo(P[0]) == "White"
    assert passo.diario_do_corpo.rotulo(P[2]) == dc.SEM_COR
    assert passo.diario_do_corpo.rotulo(P[1]) == f"{dc.SEM_COR} #2"
    cores[P[0]] = "Cosmic Red"
    assert passo.diario_do_corpo.rotulo(P[0]) == "White", "a cor lida fica para a sessão"


def test_o_pcm_lido_so_para_a_porta_tambem_se_conta() -> None:
    passo = _passo(_Alto())
    passo.receita_vigente = tv.DESLIGADA
    passo.som_assinado = lambda: True  # type: ignore[method-assign]
    passo.alimentar_o_corpo(_pcm(960))
    [linha] = _fechar(passo)
    assert linha["pcm_lido"] == 960 * 4


class _Ouvido:
    def __init__(self, surdo: float = 0.0) -> None:
        self.surdo = surdo

    def surdo_ha_s(self) -> float:
        return self.surdo

    def comecar(self) -> None:
        return None

    def tirar(self) -> list[Any]:
        return []


def test_ouvido_surdo_e_um_warning_na_borda_sem_repetir() -> None:
    passo = _passo(_Alto())
    passo.jogo = True
    ouvido = passo.motor.ouvido = _Ouvido(dc.PRAZO_DO_SURDO_S - 1)
    passo.motor.ligado = True
    with structlog.testing.capture_logs() as linhas:
        passo.andar_o_diario(0.0)
        assert not [x for x in linhas if x["event"] == "tato_ouvido_surdo"]
        ouvido.surdo = dc.PRAZO_DO_SURDO_S
        for t in range(1, 20):
            passo.andar_o_diario(t * 5.0)
            ouvido.surdo += 5.0
        ouvido.surdo = 0.0
        passo.andar_o_diario(200.0)
    surdos = [x for x in linhas if x["event"] == "tato_ouvido_surdo"]
    assert len(surdos) == 1 and surdos[0]["log_level"] == "warning"
    assert surdos[0]["ha_s"] == dc.PRAZO_DO_SURDO_S
    assert [x for x in linhas if x["event"] == "tato_ouvido_voltou_a_ouvir"]
    assert passo.daemon.store.counter(dc.CHAVE_DO_SURDO) == 1


def test_o_jogo_que_fecha_surdo_nao_diz_que_voltou_a_ouvir() -> None:
    passo = _passo(_Alto())
    passo.jogo = True
    passo.motor.ouvido = _Ouvido(dc.PRAZO_DO_SURDO_S)
    passo.motor.ligado = True
    with structlog.testing.capture_logs() as linhas:
        passo.andar_o_diario(0.0)
        passo.jogo = False
        passo.andar_o_diario(5.0)
        passo.jogo = True
        passo.andar_o_diario(10.0)
    assert not [x for x in linhas if x["event"] == "tato_ouvido_voltou_a_ouvir"]
    assert len([x for x in linhas if x["event"] == "tato_ouvido_surdo"]) == 2


def test_sem_jogo_ou_sem_pedido_nao_ha_surdo() -> None:
    passo = _passo(_Alto())
    passo.motor.ouvido = _Ouvido(9999.0)
    passo.motor.ligado = True
    passo.jogo = False
    with structlog.testing.capture_logs() as linhas:
        passo.andar_o_diario(0.0)
    assert not [x for x in linhas if x["event"] == "tato_ouvido_surdo"]


class _Relogio:
    def __init__(self) -> None:
        self.agora = 100.0

    def __call__(self) -> float:
        return self.agora


def test_o_ouvido_conta_o_surdo_e_a_pausa_nao_e_surdez() -> None:
    relogio = _Relogio()
    fluxo = tj.FluxoDoJogo(1, 2, "jogo", 3, pausado=True)
    gravador = SimpleNamespace(stdout=SimpleNamespace(read=lambda _n: b""), poll=lambda: None)
    ouvido = tj.OuvidoDoJogo(
        lambda: True, achar_o_fluxo=lambda: fluxo, montar_argv=lambda _f: ["x"],
        abrir=lambda _a: gravador, derrubar=lambda _p, **_k: None,
        conferir_o_alvo=lambda _r: "jogo", relogio=relogio)
    assert ouvido.surdo_ha_s() == 0.0, "antes do pedido não há surdez"
    ouvido.uma_volta()
    relogio.agora += tj.PRAZO_DO_SILENCIO_S
    assert ouvido.surdo_ha_s() == tj.PRAZO_DO_SILENCIO_S
    ouvido.uma_volta()
    assert ouvido.pausado and ouvido.surdo_ha_s() == 0.0


def test_o_ouvido_sem_fluxo_com_jogo_aberto_tambem_esta_surdo() -> None:
    relogio = _Relogio()
    ouvido = tj.OuvidoDoJogo(lambda: True, achar_o_fluxo=lambda: None, relogio=relogio)
    ouvido.uma_volta()
    relogio.agora += 40.0
    assert ouvido.surdo_ha_s() == 40.0


def test_o_diario_escreve_fora_do_tique() -> None:
    """O passo do diário é a tarefa dele: o tique de 60 Hz não fecha o minuto."""
    passo = _passo(_Alto())
    passo.jogo = True
    with structlog.testing.capture_logs() as linhas:
        for t in range(0, 300):
            passo.tique_do_laco(float(t))
    assert not [x for x in linhas if x["event"] == "tato_corpo_minuto"]


def _subsistema(monkeypatch: pytest.MonkeyPatch, *, ganho: int = 100) -> af.AltoFalanteSubsystem:
    from hefesto_dualsense4unix.daemon import ganho_da_haptica

    monkeypatch.setattr(ganho_da_haptica.GANHO, "pct", lambda _c: ganho)
    return af.AltoFalanteSubsystem()


def _endpoint() -> SimpleNamespace:
    return SimpleNamespace(module_id=7, nome="hefesto_haptica_x")


@pytest.mark.parametrize("motivo", [
    dc.RECUSA_SEM_APARELHO, dc.RECUSA_SEM_ENDPOINT, dc.RECUSA_JOGO_NO_ENDPOINT,
    dc.RECUSA_RADIO_CEDE, dc.RECUSA_FORCA_ZERO,
])
def test_o_tocar_o_corpo_diz_o_motivo(motivo: str, monkeypatch: pytest.MonkeyPatch) -> None:
    sub = _subsistema(monkeypatch, ganho=0 if motivo == dc.RECUSA_FORCA_ZERO else 100)
    if motivo != dc.RECUSA_SEM_APARELHO:
        sub._aparelho_de = {P[0]: "m"}
    if motivo not in (dc.RECUSA_SEM_APARELHO, dc.RECUSA_SEM_ENDPOINT):
        sub._endpoints = {"m": _endpoint()}
    if motivo == dc.RECUSA_JOGO_NO_ENDPOINT:
        sub._aparelhos_com_jogo = frozenset({"m"})
    if motivo == dc.RECUSA_RADIO_CEDE:
        sub._esperando_vaga = frozenset({(P[0], "som")})
    desfecho = sub.tocar_o_corpo(P[0], array("f", [0.1]))
    assert not desfecho
    assert desfecho.motivo == motivo


def test_o_tocar_o_corpo_que_toca_e_verdadeiro(monkeypatch: pytest.MonkeyPatch) -> None:
    sub = _subsistema(monkeypatch)
    sub._aparelho_de = {P[0]: "m"}
    sub._endpoints = {"m": _endpoint()}
    levados: list[Any] = []
    tocador = SimpleNamespace(levar_o_corpo=lambda *a, **_k: levados.append(a))
    sub._tocadores = MappingProxyType({"m": tocador})
    assert sub.tocar_o_corpo(P[0], array("f", [0.1]))
    assert levados


def _cabo() -> tuple[HapticaDoCabo, dict[str, Any]]:
    lacos = SimpleNamespace(
        esta_ligado=lambda _c: estado["ligado"], desligar=lambda _c: None,
        ligar=lambda *_a, **_k: estado.__setitem__("ligado", True) or True)
    estado: dict[str, Any] = {"ligado": False}
    fluxo = SimpleNamespace(indice="9", motores=None)
    cabo = HapticaDoCabo(
        lacos=lacos, pactl=lambda _a: "", ler_o_fluxo=lambda _n: fluxo,
        conferir=lambda _n: None)
    return cabo, estado


def test_o_ganho_do_cabo_confirmado_sai_uma_vez_por_laco_refeito() -> None:
    assert "haptica_do_cabo_portao" not in lc.EVENTOS_DE_ESTADO_NORMAL, (
        "o sucesso do portão voltou ao filtro: o que confirma o ganho some do diário")
    cabo, estado = _cabo()
    rota = RotaDoCabo(captura="a", destino="b", origem="", dono=P[0])
    with structlog.testing.capture_logs() as linhas:
        cabo.casar({"m": rota}, {"m": 1.0})
        cabo.casar({"m": rota}, {"m": 1.0})
        cabo.casar({"m": rota}, {"m": 0.5})
        cabo.casar({}, {})
        estado["ligado"] = False
        cabo.casar({"m": rota}, {"m": 0.5})
    ditos = [x["log_level"] for x in linhas if x["event"] == "haptica_do_cabo_portao"]
    assert ditos.count("info") == 2, ditos


def test_o_doctor_diz_o_numero_de_cada_controle() -> None:
    counters = {
        "corpo.controle.Cosmic Red.blocos": 1200,
        "corpo.controle.Cosmic Red.recusa.radio_cede": 3,
        "corpo.controle.White.blocos": 0,
        "corpo.controle.White.recusa.sem_endpoint": 40,
        "corpo.ouvido_surdo": 2,
        "poll.tique.medidos": 9,
    }
    linhas = cmd_doctor._linhas_do_corpo(counters)
    assert linhas == [
        ("[ OK ]", "Som no corpo, Cosmic Red: 1200 blocos com sinal; recusas: o rádio sem fatia 3"),
        ("[WARN]", "Som no corpo, White: 0 blocos com sinal; recusas: sem endpoint 40"),
        ("[WARN]", "ouvido do jogo ficou surdo 2 vez(es) com jogo aberto"),
    ]


def test_o_doctor_le_do_daemon_o_que_o_minuto_subiu(monkeypatch: pytest.MonkeyPatch) -> None:
    passo = _passo(_Alto({P[1]: dc.RECUSA_SEM_ENDPOINT}))
    _levar(passo, (P[0], P[1]))
    _fechar(passo)
    contadores = passo.daemon.store.snapshot().counters

    class _Cliente:
        async def __aenter__(self) -> _Cliente:
            return self

        async def __aexit__(self, *_a: Any) -> None:
            return None

        async def call(self, metodo: str, *_a: Any, **_k: Any) -> dict[str, Any]:
            if metodo == "daemon.state_full":
                return {"counters": contadores}
            return {"profiles": []} if metodo == "profile.list" else {"paused": False}

    monkeypatch.setattr(ipc_client.IpcClient, "connect", lambda *_a, **_k: _Cliente())
    linhas = asyncio.run(cmd_doctor._daemon_checks())
    assert ("[ OK ]", "Som no corpo, Cosmic Red: 1 blocos com sinal; recusas: nenhuma") in linhas
    assert ("[WARN]", "Som no corpo, Starlight Blue: 0 blocos com sinal; recusas: sem endpoint 1"
            ) in linhas


def test_o_doctor_sem_contas_nao_inventa_linha() -> None:
    assert cmd_doctor._linhas_do_corpo({}) == []
    assert cmd_doctor._linhas_do_corpo(None) == []


@pytest.mark.asyncio
async def test_o_laco_do_tato_anda_o_diario_fora_do_fio_dele(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """O diário só escreve se alguém o anda: o laço de produção, em outro fio, até parar."""
    fios: list[threading.Thread] = []
    monkeypatch.setattr(tv, "PASSO_DO_DIARIO_S", 0.001)
    monkeypatch.setattr(
        tv.Passo, "andar_o_diario", lambda _p, _a: fios.append(threading.current_thread()))
    monkeypatch.setattr(tv.Passo, "tique_do_laco", lambda _p, _a: 0)
    parar = asyncio.Event()
    daemon = SimpleNamespace(_is_stopping=parar.is_set, bus=None)
    motor = tv.TatoVivo([])
    motor.ouvido = SimpleNamespace(parar=lambda: None)
    laco = asyncio.create_task(tv.tato_vivo_loop(daemon, motor))
    for _ in range(2000):
        if fios:
            break
        await asyncio.sleep(0.001)
    assert fios, "o laço não andou o diário"
    monkeypatch.setattr(tv, "PASSO_DO_DIARIO_S", 3600.0)
    await asyncio.sleep(0.02)
    parar.set()
    await asyncio.wait_for(laco, 2.0)
    assert threading.main_thread() not in fios
    assert not [t for t in asyncio.all_tasks() if t.get_name() == "tato_diario_do_corpo"]
