"""CACHE-SEM-PODA-01 — o controle sai, e o relógio deixa de ser quem decide.

A QUEIXA DELA, 19/09/2026:

    "noto que existe alguma espécie de cachê que demora a ser apagado.  # noqa-acento: dela
     Principalmente quando desconectamos controles e afins."

O QUE FOI MEDIDO NESTA ÁRVORE, em 20/09/2026, antes de escrever uma linha de
cura — e o número da sprint estava OTIMISTA. A tabela dela dá 2 s de vida ao
cache do som da aba 02; com a mesa esvaziando ele é **infinito**:

    com o controle na mesa   sono 'acordado' · sink 'sink-de-mentira'
    logo depois de sair      sono 'acordado' · sink 'sink-de-mentira'
    300 s depois             sono 'acordado' · sink 'sink-de-mentira'

A causa está na primeira linha de ``a02_controles._camada_1``:
``if not na_mesa: return _CAMADA_1``. Sem ninguém na mesa a thread de renovação
não roda, o ``clear()``/``update()`` dela nunca acontece, e a entrada do que
saiu espera — para ser servida, velha, no instante em que ele volta. O ``uniq``
é o MAC: **ele volta igual**.

E A SEGUNDA MEDIÇÃO DESFEZ UMA HIPÓTESE DA SPRINT: os seis caches da tabela dela
não são seis versões do mesmo defeito. A ``a07_lancadores`` não tem o que podar,
e isso foi medido com o canário destas réguas, não suposto — ver
:func:`test_a_biblioteca_dos_lancadores_nao_guarda_controle`.

O QUE ESTAS RÉGUAS TRANCAM, e por que cada uma existe:

* o ponto de poda é UM — o despachante decide QUANDO, a aba declara O QUE;
* ele acorda por EVENTO (alguém saiu), não por relógio, e não acorda quando
  alguém CHEGA nem quando a janela abre com a mesa cheia;
* o controle que volta não recebe a leitura da sessão anterior dele, nem
  depois de 300 s de mesa vazia;
* a leitura que estava EM VOO quando ele saiu não desfaz a poda ao pousar —
  esta é a que quase escapou: a cura duraria o que dura um ``pactl``;
* o painel técnico da 09 para de nomear quem saiu no MESMO tique.

**NENHUMA RÉGUA DESTE ARQUIVO FALA COM O SERVIDOR DE SOM DELA.** As três
leituras de sistema da ``a02`` e as cinco da ``a09`` são substituídas por
dublês; o que roda de verdade são as threads do produto, com o `pactl` trocado.

**A MORDIDA DE CADA UMA está no docstring dela, com o que reprovou.**
"""
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

#: OS DOIS CONTROLES DESTA RÉGUA, na faixa SINTÉTICA da casa. Nenhum octeto sai
#: da bancada dela — há dois portões de anonimato nesta árvore, e o de FORMA
#: pega sem consultar OUI nenhum.
P1 = "aa:bb:cc:00:00:01"
P2 = "aa:bb:cc:00:00:02"

#: O NOME DO CONTROLE QUE SAI, e ele é um canário: nada mais nesta árvore se
#: chama assim, então achá-lo na tela depois da saída é prova de que um cache o
#: segurou. Não é nome de plástico de verdade de propósito — um `White` casaria
#: com prosa de outro lugar e o achado seria ambíguo.
CANARIO = "ZZ-CANARIO-ZZ"

#: Quanto uma régua espera por uma thread do produto antes de desistir. Generoso
#: de propósito: o que se mede aqui é ORDEM, não velocidade, e um teto curto
#: viraria vermelho intermitente numa máquina carregada.
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
    """O que `audio_saida.ler_as_duas_camadas` devolveria — e nada além.

    Os quatro atributos são exatamente os que `sink_do_cache`, `aceso_da_rota` e
    `recado_da_rota` leem, e estão escritos nos docstrings deles. Um dublê com
    menos campos daria verde sobre uma leitura que o produto faz.
    """

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
    """Devolve os caches de módulo como estavam. **Sem ela, esta régua envenena.**

    Os três caches da 02, o `_LENTO` da 09, a vigia da 07 e o `_NA_MESA_ANTES`
    do despachante são estado de MÓDULO — é o que os faz caches. Uma régua que
    escreve neles e não devolve contamina a irmã por ORDEM DE TESTE, que é um
    defeito que esta casa já pagou (o dublê do co-op, 04/09/2026).
    """
    guardado = {
        "camada1": dict(a02._CAMADA_1), "sono": dict(a02._SONO),
        "nativo": dict(a02._MIC_NATIVO), "quando": a02._CAMADA_1_QUANDO[0],
        "selo": a02._CAMADA_1_SELO[0], "voo": a02._CAMADA_1_EM_VOO[0],
        "lento": dict(a09._LENTO), "lento_selo": a09._LENTO_SELO[0],
        "lento_voo": a09._LENTO_EM_VOO[0], "antes": pacotes._NA_MESA_ANTES[0],
        "vigia": (a07.VIGIA._dado, a07.VIGIA._quando, a07.VIGIA._em_curso),
    }
    a09._JANELA_ANTIGA[:] = [_JanelaDeMentira()]
    yield
    _esperar_o_voo_da_02_pousar()
    for cache in (a02._CAMADA_1, a02._SONO, a02._MIC_NATIVO, a09._LENTO):
        cache.clear()
    a02._CAMADA_1.update(guardado["camada1"])
    a02._SONO.update(guardado["sono"])
    a02._MIC_NATIVO.update(guardado["nativo"])
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
    """Troca as três leituras de sistema da 02 por dublês. Nada abre subprocesso.

    O que continua rodando é a THREAD do produto — é ela que esta régua mede.
    """
    monkeypatch.setattr(
        a02, "_ler_a_camada_1",
        ler or (lambda _e, na_mesa: {u: _RotaFalsa(f"sink-novo-{u[-2:]}")
                                     for u in na_mesa}))
    monkeypatch.setattr(a02, "_ler_o_sono",
                        lambda lido: dict.fromkeys(lido, "dormindo"))
    monkeypatch.setattr(a02, "_ler_o_nativo",
                        lambda na_mesa: dict.fromkeys(na_mesa, False))
    monkeypatch.setattr(a02.audio_saida, "regra_nunca_dorme_instalada",
                        lambda *_a, **_k: True)
    monkeypatch.setattr(a02, "_seguir_as_ondas", lambda _alvos: None)


def _esperar_o_voo_da_02_pousar() -> None:
    """Segura até a thread da camada 1 pousar. Nunca levanta."""
    fim = time.time() + TETO_S
    while a02._CAMADA_1_EM_VOO[0] and time.time() < fim:
        time.sleep(0.005)


def _encher_o_cache_da_02(*uniqs: str) -> None:
    """Põe uma leitura de camada 1 para cada um — o ponto de injeção declarado.

    `_camada_1` diz no próprio docstring que este é o lugar: *"quem quiser medir
    o desacordo das duas camadas escreve em `_CAMADA_1` e não espera thread
    nenhuma — uma régua que dependesse de um relógio seria uma corrida"*.
    """
    for uniq in uniqs:
        a02._CAMADA_1[uniq] = _RotaFalsa(f"sink-de-{uniq[-2:]}")
        a02._SONO[uniq] = "acordado"
        a02._MIC_NATIVO[uniq] = True
    a02._CAMADA_1_QUANDO[0] = time.monotonic()
    a02._CAMADA_1_EM_VOO[0] = False


# ---------------------------------------------------------------------------
# 1. O PONTO DE PODA É UM, E ELE ACORDA POR EVENTO
# ---------------------------------------------------------------------------
def test_a_poda_so_acorda_quando_alguem_sai(mesa: Any) -> None:
    """Chegar não poda; ficar não poda; SAIR poda.

    A sprint mandou um ponto único *"chamado quando a mesa muda"*, e a diferença
    entre MUDAR e ENCOLHER é o que esta régua trava: um controle que chega não
    deixa lixo em cache nenhum, e varrer seis caches a cada chegada é trabalho
    por nada.

    **A MORDIDA:** troque o `if not saiu:` de `podar_o_que_saiu` por
    `if antes == agora:` — a poda passa a acordar a cada MUDANÇA da mesa, que é
    o que a sprint pedia ao pé da letra. Executada em 20/09/2026:

        AssertionError: a chegada do P2 podou: [frozenset({'aa:bb:cc:00:00:01',
        'aa:bb:cc:00:00:02'})]
    """
    chamadas: list[frozenset[str]] = []
    pacotes.PODAS.append(chamadas.append)
    try:
        pacotes._NA_MESA_ANTES[0] = frozenset()
        # A JANELA ABRE com um controle: não é ninguém saindo.
        assert pacotes.podar_o_que_saiu(_ctx(_controle(P1, 1, "um"))) == frozenset()
        assert chamadas == [], f"a abertura da janela podou: {chamadas}"
        # CHEGA O SEGUNDO.
        dois = (_controle(P1, 1, "um"), _controle(P2, 2, CANARIO))
        assert pacotes.podar_o_que_saiu(_ctx(*dois)) == frozenset()
        assert chamadas == [], f"a chegada do P2 podou: {chamadas}"
        # O TIQUE SEGUINTE, com a mesa igual.
        assert pacotes.podar_o_que_saiu(_ctx(*dois)) == frozenset()
        assert chamadas == [], f"um tique sem novidade podou: {chamadas}"
        # O P2 SAI — e agora sim.
        saiu = pacotes.podar_o_que_saiu(_ctx(_controle(P1, 1, "um")))
        assert saiu == frozenset({P2}), saiu
        assert chamadas == [frozenset({P1})], (
            f"a poda tinha de receber QUEM FICOU, e uma vez só: {chamadas}")
    finally:
        pacotes.PODAS.remove(chamadas.append)


def test_o_tique_poda_antes_de_pintar(mesa: Any) -> None:
    """A poda pega carona no que o piloto já chama todo tique, e ANTES da pintura.

    `hefesto_vivo._tique` chama `bater_os_coracoes(ctx, ponte)` e, logo depois,
    `pacote_da_pagina()`. Se a poda não estiver pendurada na primeira, a aba
    pinta o tique com o cache sujo — e a prova de pronto da sprint é *"em menos
    de um tique"*.

    **A MORDIDA:** tire a linha `podar_o_que_saiu(ctx)` de `bater_os_coracoes`.
    Executada em 20/09/2026:

        AssertionError: o tique não podou: o cache do som ainda tem
        'aa:bb:cc:00:00:02' depois de ele sair da mesa
    """
    _encher_o_cache_da_02(P1, P2)
    pacotes._NA_MESA_ANTES[0] = frozenset({P1, P2})
    pacotes.bater_os_coracoes(_ctx(_controle(P1, 1, "um")), None)
    assert P2 not in a02._CAMADA_1, (
        f"o tique não podou: o cache do som ainda tem {P2!r} depois de ele "
        "sair da mesa")
    assert P2 not in a02._SONO and P2 not in a02._MIC_NATIVO, (
        "a poda alcançou uma das três leituras por controle e não as outras: "
        f"sono={sorted(a02._SONO)} nativo={sorted(a02._MIC_NATIVO)}")
    assert P1 in a02._CAMADA_1, "a poda levou junto quem ficou"


# ---------------------------------------------------------------------------
# 2. O CONTROLE QUE VOLTA — e é onde o defeito chega na tela dela
# ---------------------------------------------------------------------------
def test_o_controle_que_volta_nao_recebe_a_leitura_da_sessao_passada(
        mesa: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    """Ele sai, passam 300 s, ele volta — e a aba não repete o que era antes.

    **ELA VIVE NO TEMPO, E TEM DE VIVER.** Com a mesa vazia a thread de
    `_camada_1` não roda (`if not na_mesa: return`), então esperar não cura: o
    relógio anda **300 segundos** aqui — o TTL do cache mais longo desta
    interface — e o que se prova é que **o tempo não é quem apaga**. Quem apaga
    é o evento.

    E A LEITURA DA VOLTA FICA PRESA DE PROPÓSITO: o que se mede é o que a aba
    serve no PRIMEIRO tique da volta, enquanto o `pactl` ainda não respondeu.
    Sem essa trava a régua seria uma corrida — mediria às vezes o cache, às
    vezes a resposta nova.

    **A MORDIDA:** tire o corpo de `_esquecer_o_som_de_quem_saiu`. Executada em
    20/09/2026:

        AssertionError: o controle que voltou recebeu o sink da sessão
        anterior dele, 300 s depois: 'sink-de-01'
    """
    _encher_o_cache_da_02(P1)
    pacotes._NA_MESA_ANTES[0] = frozenset({P1})

    relogio = [time.monotonic()]
    monkeypatch.setattr(time, "monotonic", lambda: relogio[0])

    # ELE SAI.
    pacotes.bater_os_coracoes(_ctx(), None)

    # O RELÓGIO ANDA 300 s com a mesa vazia, um tique de cada vez.
    for _ in range(10):
        relogio[0] += 30.0
        a02._camada_1((), ())

    # ELE VOLTA, com o MESMO `uniq` — porque o `uniq` é o MAC.
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
        assert a02._MIC_NATIVO.get(P1) is None, (
            "o controle que voltou recebeu o microfone nativo da sessão "
            f"anterior dele: {a02._MIC_NATIVO.get(P1)!r}")
    finally:
        solta.set()
        _esperar_o_voo_da_02_pousar()


def test_a_volta_no_tique_seguinte_ja_rele(
        mesa: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    """Zerar o cache sem zerar o relógio curaria pela metade.

    Com `_CAMADA_1_QUANDO` intacto, o controle que volta DENTRO dos 2 s encontra
    o cache vazio (bom) e a leitura *não devida* (ruim): a aba cairia no byte
    por mais dois segundos, que é meia cura vendida como cura.

    Aqui não há relógio falso: ele volta no tique seguinte ao de ter saído, que
    é o pior caso e o mais comum (o cabo que encosta mal). O oráculo é a thread
    ter partido — não o número guardado.

    **A MORDIDA:** tire o `_CAMADA_1_QUANDO[0] = 0.0` da poda. Executada em
    20/09/2026:

        AssertionError: o tique da volta não disparou releitura: a aba fica no
        byte até o relógio de 2 s vencer
    """
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
    """A thread que partiu com a mesa de antes não repõe quem saiu.

    **ESTA É A QUE QUASE ESCAPOU.** `renovar` publica com `clear()` + `update()`
    do dicionário INTEIRO, carregando a mesa congelada do instante do disparo.
    Se o controle sai enquanto o `pactl` responde, a poda tira a entrada dele e
    a thread **a repõe ao pousar**: a cura duraria o que dura um `pactl` e
    voltaria sozinha, sem ninguém ver.

    A régua roda a thread DE VERDADE e a segura no meio — é a única forma de
    medir uma corrida sem depender de sorte.

    **A MORDIDA:** tire o `if _CAMADA_1_SELO[0] != selo: return` do
    `renovar`. Executada em 20/09/2026:

        AssertionError: a leitura em voo repôs o controle que saiu: o cache tem
        ['aa:bb:cc:00:00:01', 'aa:bb:cc:00:00:02']
    """
    lendo, solta = threading.Event(), threading.Event()

    def _preso(_entradas: Any, na_mesa: tuple[str, ...]) -> dict[str, Any]:
        lendo.set()
        solta.wait(TETO_S)
        return {u: _RotaFalsa(f"sink-velho-{u[-2:]}") for u in na_mesa}

    _sem_pactl(monkeypatch, ler=_preso)
    _encher_o_cache_da_02(P1, P2)
    a02._CAMADA_1_QUANDO[0] = 0.0  # a leitura está devida
    try:
        # O TIQUE DISPARA a leitura com os DOIS na mesa…
        a02._camada_1(((P1, 3), (P2, 3)), (P1, P2))
        assert lendo.wait(TETO_S), "o tique não disparou leitura nenhuma"
        # …o P2 SAI enquanto ela lê…
        pacotes._NA_MESA_ANTES[0] = frozenset({P1, P2})
        pacotes.bater_os_coracoes(_ctx(_controle(P1, 1, "um")), None)
        assert P2 not in a02._CAMADA_1, "a poda não chegou a acontecer"
    finally:
        # …e a leitura POUSA, com a mesa de antes nas mãos.
        solta.set()
        _esperar_o_voo_da_02_pousar()
    assert not a02._CAMADA_1_EM_VOO[0], "a leitura não pousou dentro do teto"
    assert P2 not in a02._CAMADA_1, (
        "a leitura em voo repôs o controle que saiu: o cache tem "
        f"{sorted(a02._CAMADA_1)}")


# ---------------------------------------------------------------------------
# 3. O PAINEL TÉCNICO DA 09 — o cache que não é por controle, e mesmo assim mente
# ---------------------------------------------------------------------------
def _a09_sem_disco(monkeypatch: pytest.MonkeyPatch) -> None:
    """As quatro leituras caras da faixa lenta viram dublês. O painel fica real."""
    monkeypatch.setattr(a09, "_autostart", lambda: "enabled")
    monkeypatch.setattr(a09, "_achados", lambda *_a, **_k: [])
    monkeypatch.setattr(a09, "_perfil_da_bateria", lambda: None)
    monkeypatch.setattr(a09, "_status_do_daemon", lambda _s: "online_systemd")


def test_o_painel_tecnico_para_de_nomear_quem_saiu(
        mesa: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    """A faixa lenta foi montada com a mesa de antes, e o painel a escreve.

    `_repouso_do_painel` escreve uma linha de identidade por controle de pé, e
    ela fica dentro de `_LENTO["valor"]` por `LENTO_S`. Sem poda, o painel
    continua nomeando o controle que a fita, dois centímetros acima, já
    esqueceu — a mesma tela dizendo as duas coisas, que é a queixa dela.

    O ORÁCULO NÃO SE MONTA COM O QUE O CÓDIGO LÊ: o nome procurado é o do
    controle que a régua pôs na mesa ANTES, e ele não existe em constante
    nenhuma do produto.

    **A MORDIDA:** tire o `_LENTO.clear()` de `_esquecer_a_mesa_de_antes`.
    Executada em 20/09/2026:

        AssertionError: o painel técnico ainda nomeia 'ZZ-CANARIO-ZZ' depois de
        ele sair da mesa
    """
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
    """A mesma corrida da 02, no outro arquivo — e a mesma cura.

    `_guardar_a_faixa_lenta` roda em thread com a mesa congelada e escreve
    `_LENTO["valor"]` ao pousar. Sem o selo, ela apaga a poda que aconteceu
    no meio do voo.

    **A MORDIDA:** tire o `selo == _LENTO_SELO[0]` de
    `_guardar_a_faixa_lenta`. Executada em 20/09/2026:

        AssertionError: a releitura em voo repôs a mesa de antes no painel
    """
    _a09_sem_disco(monkeypatch)
    a09._LENTO.clear()

    dois = (_controle(P1, 1, "um"), _controle(P2, 2, CANARIO))
    cheio = _ctx(*dois)
    selo = a09._LENTO_SELO[0]
    # O P2 SAI enquanto a releitura, disparada com os dois, ainda lê.
    pacotes._NA_MESA_ANTES[0] = frozenset({P1, P2})
    pacotes.bater_os_coracoes(_ctx(_controle(P1, 1, "um")), None)
    # E ela POUSA, carimbada com o selo de antes.
    a09._guardar_a_faixa_lenta(cheio.state, cheio.mesa, selo)
    assert not a09._LENTO, (
        "a releitura em voo repôs a mesa de antes no painel: "
        f"{a09._LENTO.get('valor')!r}")


def test_a_releitura_sem_selo_continua_valendo(
        mesa: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    """A cura não pode custar o que já funcionava.

    `_guardar_a_faixa_lenta` tem chamadores que não carimbam selo nenhum —
    as réguas desta casa. `None` é *"ninguém disse"*, e aí não há o que
    conferir: o valor entra como sempre entrou.

    **A MORDIDA:** troque o `selo is None or` por `selo is not None and`.
    Executada em 20/09/2026: `_LENTO` fica vazio e esta régua reprova.
    """
    _a09_sem_disco(monkeypatch)
    a09._LENTO.clear()
    cheio = _ctx(_controle(P2, 2, CANARIO))
    a09._guardar_a_faixa_lenta(cheio.state, cheio.mesa)
    assert a09._LENTO.get("valor"), "a releitura sem carimbo não guardou nada"
    assert CANARIO in a09._LENTO["valor"][-1]


# ---------------------------------------------------------------------------
# 4. A 07 NÃO TEM O QUE PODAR — medido, e trancado para quando mudar
# ---------------------------------------------------------------------------
def test_a_biblioteca_dos_lancadores_nao_guarda_controle(mesa: Any) -> None:
    """O canário: com a vigia CONGELADA, nada do controle atravessa a saída dele.

    A sprint listou os 20 s desta vigia entre os caches que *"não escutam a
    saída de um controle"*. Ela não tem o que escutar, e é isto que a régua
    mede: a MESMA `Leitura` serve as duas pinturas, e mesmo assim nem o nome nem
    o `uniq` do controle aparecem em qualquer uma.

    **ELA É UM ORÁCULO PARA O FUTURO**, que é a razão de existir: se um dia a
    `Leitura` ganhar um campo por `uniq`, a primeira pintura o grava no cache
    congelado e ele reaparece na segunda — com o controle já fora da mesa. Aí
    esta régua reprova nomeando, e a 07 ganha a poda dela.

    **A MORDIDA:** não há cura a arrancar; é uma afirmação sobre o produto de
    hoje. Ponha `fora["canario"] = ctx.mesa[0]["nome"]` em `a07_lancadores.pacote`
    e as duas asserções reprovam — a primeira por a aba passar a nomear, a
    segunda por o nome atravessar a saída dele.
    """
    a07.VIGIA._dado = desenho.Leitura()
    a07.VIGIA._quando = time.monotonic()
    a07.VIGIA._em_curso = True  # é o que impede a thread de partir

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


# ---------------------------------------------------------------------------
# 5. O MOLDE — a outra suspeita da sprint, e ela também cai
# ---------------------------------------------------------------------------
def test_o_molde_do_lugar_nao_guarda_controle_nenhum(
        mesa: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    """O `_MOLDE` é por (página, perfil) e não precisa de poda. Medido.

    A sprint o apontou por não ser chaveado por controle. Ele não é chaveado por
    controle porque **não guarda nenhum**: só os NOMES dos campos sobrevivem, e
    todos valem travessão — o `_CONTROLE_DE_MENTIRA` que o monta é jogado fora.

    **A MORDIDA:** faça `molde_do_lugar` guardar o `seria` em vez de
    `dict.fromkeys(…, TRAVESSAO)`. Executada em 20/09/2026: o molde passa a
    carregar o `uniq` do controle de mentira e esta régua reprova.
    """
    _sem_pactl(monkeypatch)
    molde = pacotes.molde_do_lugar("02-controles.html", _ctx(), {})
    assert molde, ("o molde saiu vazio e a régua não mediu nada — a página "
                   "publicada não abriu")
    assert all(v == pacotes.TRAVESSAO for v in molde.values()), molde
    assert pacotes._CONTROLE_DE_MENTIRA["uniq"] not in repr(molde), molde
    _esperar_o_voo_da_02_pousar()
