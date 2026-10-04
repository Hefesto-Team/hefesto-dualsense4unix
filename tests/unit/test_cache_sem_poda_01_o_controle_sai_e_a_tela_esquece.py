"""CACHE-SEM-PODA-01 — o controle sai, e o relógio deixa de ser quem decide."""
from __future__ import annotations

import threading
import time
from typing import Any

import pytest

from tests.conftest import exigir_gi_real

exigir_gi_real("importa `interface.pacotes`, que carrega o GTK")

from hefesto_dualsense4unix.interface import desenho_dos_lancadores as desenho
from hefesto_dualsense4unix.interface import pacotes
from hefesto_dualsense4unix.interface.pacotes import a02_controles as a02
from hefesto_dualsense4unix.interface.pacotes import a07_lancadores as a07
from hefesto_dualsense4unix.interface.pacotes import a09_sistema as a09

P1 = "aa:bb:cc:00:00:01"
P2 = "aa:bb:cc:00:00:02"

CANARIO = "ZZ-CANARIO-ZZ"

TETO_S = 5.0


def _controle(uniq: str, jogador: int, nome: str) -> dict[str, Any]:
    """Uma entrada de mesa/estado, com o mínimo que as três abas leem."""
    return {"uniq": uniq, "pref": f"p{jogador}", "jogador": jogador,
            "nome": nome, "via": "USB", "transporte": "usb",
            "connected": True, "transport": "usb", "player_slot": jogador,
            "serial": None, "modelo": None, "cor": "white", "alvo": jogador == 1}


def _ctx(*controles: dict[str, Any]) -> pacotes.Contexto:
    """O `Contexto` de um tique com esses controles de pé."""
    lista = list(controles)
    return pacotes.Contexto(state={"controllers": lista}, mesa=lista,
                            conectados=lista)


class _RotaFalsa:
    """O que `audio_saida.ler_as_duas_camadas` devolveria — e nada além."""

    def __init__(self, sink: str) -> None:
        self.sink_do_controle = sink
        self.monitor = f"{sink}.monitor"
        self.botao_aceso = "pc"
        self.recado = ""


class _JanelaDeMentira:
    """O dublê do `DaemonActionsMixin` — e ele NÃO fala com o systemd.

    Sem ele, `_repouso_do_painel` roda `systemctl status` de verdade na máquina
    de quem executa a régua. É o mesmo dublê que
    `test_aba09_a_identidade_de_fabrica_vem_de_cima` já usa, pela mesma razão.
    """

    def _systemctl_status_text(self, unit: str) -> str:
        return "● unidade ativa"


@pytest.fixture
def mesa() -> Any:
    """Devolve os caches de módulo como estavam. **Sem ela, esta régua envenena.**"""
    guardado = {
        "camada1": dict(a02._CAMADA_1), "sono": dict(a02._SONO),
        "ganho": dict(a02._GANHO), "quando": a02._CAMADA_1_QUANDO[0],
        "selo": a02._CAMADA_1_SELO[0], "voo": a02._CAMADA_1_EM_VOO[0],
        "lento": dict(a09._LENTO), "lento_selo": a09._LENTO_SELO[0],
        "lento_voo": a09._LENTO_EM_VOO[0], "antes": pacotes._NA_MESA_ANTES[0],
        "vigia": (a07.VIGIA._dado, a07.VIGIA._quando, a07.VIGIA._em_curso),
    }
    a09._JANELA_ANTIGA[:] = [_JanelaDeMentira()]
    yield
    _esperar_o_voo_da_02_pousar()
    for cache in (a02._CAMADA_1, a02._SONO, a02._GANHO, a09._LENTO):
        cache.clear()
    a02._CAMADA_1.update(guardado["camada1"])
    a02._SONO.update(guardado["sono"])
    a02._GANHO.update(guardado["ganho"])
    a02._CAMADA_1_QUANDO[0] = guardado["quando"]
    a02._CAMADA_1_SELO[0] = guardado["selo"]
    a02._CAMADA_1_EM_VOO[0] = guardado["voo"]
    a09._LENTO.update(guardado["lento"])
    a09._LENTO_SELO[0] = guardado["lento_selo"]
    a09._LENTO_EM_VOO[0] = guardado["lento_voo"]
    pacotes._NA_MESA_ANTES[0] = guardado["antes"]
    a07.VIGIA._dado, a07.VIGIA._quando, a07.VIGIA._em_curso = guardado["vigia"]
    a09._JANELA_ANTIGA.clear()


def _sem_pactl(monkeypatch: pytest.MonkeyPatch, ler: Any = None) -> None:
    """Troca as três leituras de sistema da 02 por dublês. Nada abre subprocesso."""
    monkeypatch.setattr(
        a02, "_ler_a_camada_1",
        ler or (lambda _e, na_mesa: {u: _RotaFalsa(f"sink-novo-{u[-2:]}")
                                     for u in na_mesa}))
    monkeypatch.setattr(a02, "_ler_o_sono",
                        lambda lido: dict.fromkeys(lido, "dormindo"))
    monkeypatch.setattr(a02, "_ler_o_ganho",
                        lambda na_mesa: dict.fromkeys(na_mesa, (50, -6.0)))
    monkeypatch.setattr(a02.audio_saida, "regra_nunca_dorme_instalada",
                        lambda *_a, **_k: True)
    monkeypatch.setattr(a02, "_seguir_as_ondas", lambda _alvos: None)


def _esperar_o_voo_da_02_pousar() -> None:
    """Segura até a thread da camada 1 pousar. Nunca levanta."""
    fim = time.time() + TETO_S
    while a02._CAMADA_1_EM_VOO[0] and time.time() < fim:
        time.sleep(0.005)


def _encher_o_cache_da_02(*uniqs: str) -> None:
    """Põe uma leitura de camada 1 para cada um — o ponto de injeção declarado."""
    for uniq in uniqs:
        a02._CAMADA_1[uniq] = _RotaFalsa(f"sink-de-{uniq[-2:]}")
        a02._SONO[uniq] = "acordado"
        a02._GANHO[uniq] = (100, 0.0)
    a02._CAMADA_1_QUANDO[0] = time.monotonic()
    a02._CAMADA_1_EM_VOO[0] = False


def test_a_poda_so_acorda_quando_alguem_sai(mesa: Any) -> None:
    """Chegar não poda; ficar não poda; SAIR poda."""
    chamadas: list[frozenset[str]] = []
    pacotes.PODAS.append(chamadas.append)
    try:
        pacotes._NA_MESA_ANTES[0] = frozenset()
        assert pacotes.podar_o_que_saiu(_ctx(_controle(P1, 1, "um"))) == frozenset()
        assert chamadas == [], f"a abertura da janela podou: {chamadas}"
        dois = (_controle(P1, 1, "um"), _controle(P2, 2, CANARIO))
        assert pacotes.podar_o_que_saiu(_ctx(*dois)) == frozenset()
        assert chamadas == [], f"a chegada do P2 podou: {chamadas}"
        assert pacotes.podar_o_que_saiu(_ctx(*dois)) == frozenset()
        assert chamadas == [], f"um tique sem novidade podou: {chamadas}"
        saiu = pacotes.podar_o_que_saiu(_ctx(_controle(P1, 1, "um")))
        assert saiu == frozenset({P2}), saiu
        assert chamadas == [frozenset({P1})], (
            f"a poda tinha de receber QUEM FICOU, e uma vez só: {chamadas}")
    finally:
        pacotes.PODAS.remove(chamadas.append)


def test_o_tique_poda_antes_de_pintar(mesa: Any) -> None:
    """A poda pega carona no que o piloto já chama todo tique, e ANTES da pintura."""
    _encher_o_cache_da_02(P1, P2)
    pacotes._NA_MESA_ANTES[0] = frozenset({P1, P2})
    pacotes.bater_os_coracoes(_ctx(_controle(P1, 1, "um")), None)
    assert P2 not in a02._CAMADA_1, (
        f"o tique não podou: o cache do som ainda tem {P2!r} depois de ele "
        "sair da mesa")
    assert P2 not in a02._SONO and P2 not in a02._GANHO, (
        "a poda alcançou uma das três leituras por controle e não as outras: "
        f"sono={sorted(a02._SONO)} ganho={sorted(a02._GANHO)}")
    assert P1 in a02._CAMADA_1, "a poda levou junto quem ficou"


def test_o_controle_que_volta_nao_recebe_a_leitura_da_sessao_passada(
        mesa: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    """Ele sai, passam 300 s, ele volta — e a aba não repete o que era antes."""
    _encher_o_cache_da_02(P1)
    pacotes._NA_MESA_ANTES[0] = frozenset({P1})

    relogio = [time.monotonic()]
    monkeypatch.setattr(time, "monotonic", lambda: relogio[0])

    pacotes.bater_os_coracoes(_ctx(), None)

    for _ in range(10):
        relogio[0] += 30.0
        a02._camada_1((), ())

    lendo, solta = threading.Event(), threading.Event()

    def _preso(_entradas: Any, na_mesa: tuple[str, ...]) -> dict[str, Any]:
        lendo.set()
        solta.wait(TETO_S)
        return {u: _RotaFalsa("sink-novo") for u in na_mesa}

    _sem_pactl(monkeypatch, ler=_preso)
    try:
        a02._camada_1(((P1, 3),), (P1,))
        assert lendo.wait(TETO_S), (
            "o tique da volta não disparou releitura nenhuma — a aba ficaria "
            "com o que o cache tivesse")
        assert a02.sono_do_canal(P1) == "", (
            "o controle que voltou recebeu o sono da sessão anterior dele, "
            f"300 s depois: {a02.sono_do_canal(P1)!r}")
        assert a02.sink_do_cache(P1) == "", (
            "o controle que voltou recebeu o sink da sessão anterior dele, "
            f"300 s depois: {a02.sink_do_cache(P1)!r}")
        assert a02._GANHO.get(P1) != (100, 0.0), (
            "o controle que voltou recebeu o ganho do microfone da sessão "
            f"anterior dele: {a02._GANHO.get(P1)!r}")
    finally:
        solta.set()
        _esperar_o_voo_da_02_pousar()


def test_a_volta_no_tique_seguinte_ja_rele(
        mesa: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    """Zerar o cache sem zerar o relógio curaria pela metade."""
    _encher_o_cache_da_02(P1)
    pacotes._NA_MESA_ANTES[0] = frozenset({P1})
    pacotes.bater_os_coracoes(_ctx(), None)

    lendo = threading.Event()

    def _avisa(_entradas: Any, na_mesa: tuple[str, ...]) -> dict[str, Any]:
        lendo.set()
        return {u: _RotaFalsa("sink-novo") for u in na_mesa}

    _sem_pactl(monkeypatch, ler=_avisa)
    a02._camada_1(((P1, 3),), (P1,))
    assert lendo.wait(TETO_S), (
        "o tique da volta não disparou releitura: a aba fica no byte até o "
        "relógio de 2 s vencer")
    _esperar_o_voo_da_02_pousar()


def test_a_leitura_em_voo_nao_desfaz_a_poda(
        mesa: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    """A thread que partiu com a mesa de antes não repõe quem saiu."""
    lendo, solta = threading.Event(), threading.Event()

    def _preso(_entradas: Any, na_mesa: tuple[str, ...]) -> dict[str, Any]:
        lendo.set()
        solta.wait(TETO_S)
        return {u: _RotaFalsa(f"sink-velho-{u[-2:]}") for u in na_mesa}

    _sem_pactl(monkeypatch, ler=_preso)
    _encher_o_cache_da_02(P1, P2)
    a02._CAMADA_1_QUANDO[0] = 0.0
    try:
        a02._camada_1(((P1, 3), (P2, 3)), (P1, P2))
        assert lendo.wait(TETO_S), "o tique não disparou leitura nenhuma"
        pacotes._NA_MESA_ANTES[0] = frozenset({P1, P2})
        pacotes.bater_os_coracoes(_ctx(_controle(P1, 1, "um")), None)
        assert P2 not in a02._CAMADA_1, "a poda não chegou a acontecer"
    finally:
        solta.set()
        _esperar_o_voo_da_02_pousar()
    assert not a02._CAMADA_1_EM_VOO[0], "a leitura não pousou dentro do teto"
    assert P2 not in a02._CAMADA_1, (
        "a leitura em voo repôs o controle que saiu: o cache tem "
        f"{sorted(a02._CAMADA_1)}")


def _a09_sem_disco(monkeypatch: pytest.MonkeyPatch) -> None:
    """As quatro leituras caras da faixa lenta viram dublês. O painel fica real."""
    monkeypatch.setattr(a09, "_autostart", lambda: "enabled")
    monkeypatch.setattr(a09, "_achados", lambda *_a, **_k: [])
    monkeypatch.setattr(a09, "_perfil_da_bateria", lambda: None)
    monkeypatch.setattr(a09, "_status_do_daemon", lambda _s: "online_systemd")


def test_o_painel_tecnico_para_de_nomear_quem_saiu(
        mesa: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    """A faixa lenta foi montada com a mesa de antes, e o painel a escreve."""
    _a09_sem_disco(monkeypatch)
    a09._LENTO.clear()

    dois = (_controle(P1, 1, "um"), _controle(P2, 2, CANARIO))
    cheio = _ctx(*dois)
    *_, painel = a09._faixa_lenta(cheio.state, cheio.mesa)
    assert CANARIO in painel, (
        f"a régua não mediu nada: o painel nunca nomeou o controle: {painel!r}")

    pacotes._NA_MESA_ANTES[0] = frozenset({P1, P2})
    so_um = _ctx(_controle(P1, 1, "um"))
    pacotes.bater_os_coracoes(so_um, None)
    *_, agora = a09._faixa_lenta(so_um.state, so_um.mesa)
    assert CANARIO not in agora, (
        f"o painel técnico ainda nomeia {CANARIO!r} depois de ele sair da "
        f"mesa: {agora!r}")


def test_a_releitura_em_voo_da_09_nao_desfaz_a_poda(
        mesa: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    """A mesma corrida da 02, no outro arquivo — e a mesma cura."""
    _a09_sem_disco(monkeypatch)
    a09._LENTO.clear()

    dois = (_controle(P1, 1, "um"), _controle(P2, 2, CANARIO))
    cheio = _ctx(*dois)
    selo = a09._LENTO_SELO[0]
    pacotes._NA_MESA_ANTES[0] = frozenset({P1, P2})
    pacotes.bater_os_coracoes(_ctx(_controle(P1, 1, "um")), None)
    a09._guardar_a_faixa_lenta(cheio.state, cheio.mesa, selo)
    assert not a09._LENTO, (
        "a releitura em voo repôs a mesa de antes no painel: "
        f"{a09._LENTO.get('valor')!r}")


def test_a_releitura_sem_selo_continua_valendo(
        mesa: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    """A cura não pode custar o que já funcionava."""
    _a09_sem_disco(monkeypatch)
    a09._LENTO.clear()
    cheio = _ctx(_controle(P2, 2, CANARIO))
    a09._guardar_a_faixa_lenta(cheio.state, cheio.mesa)
    assert a09._LENTO.get("valor"), "a releitura sem carimbo não guardou nada"
    assert CANARIO in a09._LENTO["valor"][-1]


def test_a_biblioteca_dos_lancadores_nao_guarda_controle(mesa: Any) -> None:
    """O canário: com a vigia CONGELADA, nada do controle atravessa a saída dele."""
    a07.VIGIA._dado = desenho.Leitura()
    a07.VIGIA._quando = time.monotonic()
    a07.VIGIA._em_curso = True

    dois = (_controle(P1, 1, "um"), _controle(P2, 2, CANARIO))
    com_mesa = repr(a07.pacote(_ctx(*dois)))
    assert a07.VIGIA._dado is not None, "a vigia descongelou no meio da medição"
    sem_mesa = repr(a07.pacote(_ctx()))

    assert CANARIO not in com_mesa and P2 not in com_mesa, (
        "a 07 passou a nomear o controle — e então ela TEM o que podar: "
        "registre uma poda com `@poda` neste arquivo")
    assert CANARIO not in sem_mesa and P2 not in sem_mesa, (
        "a vigia congelada devolveu o controle que já saiu da mesa: "
        f"{sem_mesa[:400]}")


def test_o_molde_do_lugar_nao_guarda_controle_nenhum(
        mesa: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    """O `_MOLDE` é por (página, perfil) e não precisa de poda. Medido."""
    _sem_pactl(monkeypatch)
    molde = pacotes.molde_do_lugar("02-controles.html", _ctx(), {})
    assert molde, ("o molde saiu vazio e a régua não mediu nada — a página "
                   "publicada não abriu")
    assert all(v == pacotes.TRAVESSAO for v in molde.values()), molde
    assert pacotes._CONTROLE_DE_MENTIRA["uniq"] not in repr(molde), molde
    _esperar_o_voo_da_02_pousar()
