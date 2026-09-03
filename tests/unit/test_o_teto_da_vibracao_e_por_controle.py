#!/usr/bin/env python3
"""A RÉGUA DO "Teto da vibração" POR CONTROLE — aba Conexões, MIGRA-CONEXOES-11.

O CAMPO oferece três coisas por controle: *Segue o global / Sem teto / 30% da
força*. DUAS delas ganharam fonte em 01/09/2026, e a terceira RECUSA DIZENDO —
o que também é entrega, e tem caso próprio aqui.

POR QUE ELE PRECISA DE RÉGUA PRÓPRIA, e não de uma linha em `a08_conexoes.PROVAS`:
aquela régua passa um dublê de ponte e cobra QUAL função dela foi chamada. Este
gesto exige **perfil ativo**, que o `ctx` dela não tem, e o que ele muda primeiro
é o **disco** — o `profile.switch` vem depois. Uma prova que só olhasse a ponte
diria que ele funciona mesmo com o que foi para o arquivo errado.

A PONTE É DUBLÊ, SEMPRE. `perfil.gravar_e_reaplicar` chama
`p.profile_switch(...)` quando o nome casa o ativo, e uma ponte real mandaria
isso ao daemon DELA, que está vivo. Todo `uniq` daqui vem da faixa sintética
`aa:bb:cc:00:00:01` — há dois portões de anonimato que reprovam o contrário.

O QUE ELA COBRA, e cada item é um jeito diferente de o campo mentir:

1. "30% da força" vira `policy="economia"` no perfil, e mais nada.
2. O rótulo é REPRODUZIDO de `RUMBLE_POLICY_MULT["economia"]`, nunca digitado.
3. "Segue o global" APAGA o override, e o segundo clique igual não regrava.
4. "Sem teto" recusa dizendo, e não toca no arquivo.
5. O fator que chega ao motor é 0,3 — a conta inteira, do disco ao `_escalar_rumble`.
6. A borda recusa o clique sem dono (sem controle, MAC forjado, rótulo de fora).
7. A pintura mostra o que está no DISCO, e não o padrão do desenho.
8. Uma política que o campo não sabe mostrar é DECLARADA, não pintada errada.
9. A página publicada tem os DOIS endereços de pintura (o campo e o `?`).

E A SEÇÃO 8, DE 01/09/2026, mede a palavra "GLOBAL" — que tinha DOIS donos, e a
tela reportava o errado. Cada item ali é um jeito diferente de a frase mentir:

10. A dica diz o que chega AO MOTOR, e não o degrau nominal do rótulo — a cadeia
    inteira, do disco ao `_escalar_rumble`, para os três globais vivos.
11. O global do PERFIL é DENOMINADOR; quem multiplica é o do DAEMON.
12. O orçamento entra por CIMA da política viva, com `min`.
13. O que não se sabe não vira a afirmação "Sem teto" — nos três casos.
14. O orçamento sai da declaração já em cache, e sem arrastar GTK.
15. A frase do orçamento passa pelo dono do número; o 0,667 é derivado.
16. A chave que PINTA é a mesma que GRAVA (`_so_hex`).
17. A recusa sem endereço fala do teto, e não da ponte do microfone.
18. O piloto não escreve num `<select>` o que ele não oferece.
19. Os `<option>` da página são os que a borda aceita.

AS MORDIDAS ESTÃO NO DOCSTRING DE CADA CASO, uma a uma, com o que reprova.
"""
from __future__ import annotations

import json
import pathlib
import re
import sys
from typing import Any

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(RAIZ / "src/hefesto_dualsense4unix/interface"))

#: O ENDEREÇO DA BANCADA — faixa sintética, nunca um MAC de aparelho real.
UNIQ = "aa:bb:cc:00:00:01"
CHAVE = "aabbcc000001"

#: O MAC FORJADO pelo `usb_probe_degrade` quando não há endereço: `02` + VID +
#: PID + bus. Dois clones do mesmo modelo recebem o MESMO, e persistir isso
#: gravaria a FUSÃO de dois aparelhos num perfil.
UNIQ_FORJADO = "02:fe:00:00:00:33"


def _bancada(**campos):
    """A `Vibracao` de referência: global vivo `balanceado`, nada mais declarado.

    É o estado em que o rótulo do campo e o que chega ao motor COINCIDEM — e é o
    único em que coincidem. Passar `None` no lugar dela faria a dica dizer
    "não dá para dizer quanta força chega", que é honesto mas não mede nada.
    """
    from hefesto_dualsense4unix.gui.aba_conexoes import Vibracao

    return Vibracao(**{"a_viva": "balanceado", **campos})


class PonteDeMentira:
    """Guarda o que foi pedido ao daemon, na ordem. NUNCA fala com o de verdade."""

    def __init__(self) -> None:
        self.chamadas: list[tuple[str, tuple[Any, ...]]] = []

    def profile_switch(self, nome: str) -> bool:
        self.chamadas.append(("profile_switch", (nome,)))
        return True

    def chamar(self, metodo: str, **_: Any) -> bool:
        self.chamadas.append(("chamar", (metodo,)))
        return True


def _perfil(nome: str = "Bancada", **campos: Any) -> Any:
    """Um `Profile` DE VERDADE — o esquema é metade do que esta régua mede.

    Um dublê aceitaria `policy="furrufu"` e a régua ficaria verde sobre um
    perfil que o loader recusaria no disco dela.
    """
    from hefesto_dualsense4unix.profiles.schema import Profile

    return Profile.model_validate(
        {"name": nome, "match": {"type": "criteria"}, **campos})


@pytest.fixture
def pac():
    import pacotes

    return pacotes


@pytest.fixture
def a08():
    from pacotes import a08_conexoes

    return a08_conexoes


@pytest.fixture
def tela():
    from hefesto_dualsense4unix.gui import aba_conexoes

    return aba_conexoes


@pytest.fixture
def gesto(pac):
    fn = pac.gesto_da_pagina("08-conexoes.html", "teto-da-vibracao")
    assert fn is not None, (
        "08-conexoes.html:teto-da-vibracao perdeu o dono — o clique dela volta a "
        "não fazer nada.")
    return fn


@pytest.fixture
def disco(monkeypatch):
    """Um disco de mentira: guarda o que o gesto mandou gravar."""
    from hefesto_dualsense4unix.profiles import loader

    gravados: list[Any] = []
    estado: dict[str, Any] = {}

    def falso_load(nome: str) -> Any:
        return estado[nome]

    def falso_save(prof: Any, **_: Any) -> None:
        gravados.append(prof)

    monkeypatch.setattr(loader, "load_profile", falso_load, raising=False)
    monkeypatch.setattr(loader, "save_profile", falso_save, raising=False)
    return estado, gravados


def _ctx(pac, ativo: str = "Bancada", uniq: str = UNIQ):
    return pac.Contexto(
        state={"active_profile": ativo},
        mesa=[],
        conectados=[{"uniq": uniq, "connected": True, "transport": "bt", "index": 0}],
        estados={})


# ---------------------------------------------------------------------------
# 1. o que a escolha grava
# ---------------------------------------------------------------------------
def test_a_escolha_de_30_por_cento_vira_economia_no_perfil(
        pac, a08, tela, gesto, disco) -> None:
    """A opção do meio-degrau grava `economia`, e o número tem UM dono.

    MORDIDA: em `a08_conexoes.teto_da_vibracao`, troque a `policy` gravada por
    `"balanceado"` — este caso reprova, porque o mult de `balanceado` é 1,0 e o
    rótulo promete 30%.
    """
    estado, gravados = disco
    estado["Bancada"] = _perfil()
    p = PonteDeMentira()
    _, _, trinta = tela.opcoes_do_teto()

    gesto(_ctx(pac), {"uniq": UNIQ, "valor": trinta}, p)

    assert len(gravados) == 1, f"gravou {len(gravados)} vez(es), esperava uma"
    dele = (gravados[0].controllers or {}).get(CHAVE)
    assert dele is not None, (
        f"não há override para {CHAVE!r} no perfil gravado — as chaves são "
        f"{sorted((gravados[0].controllers or {}).keys())}. O mapa que chega ao "
        f"backend é chaveado pelo `uniq` normalizado (`set_rumble_scales`); "
        f"gravar sob outra chave faz a escolha dela sumir calada.")
    assert dele.rumble is not None and dele.rumble.policy == "economia", (
        f"gravou {dele.rumble!r}. O rótulo promete o degrau do "
        f"`RUMBLE_POLICY_MULT['economia']`, e nenhum outro.")
    # E MAIS NADA: um override que carregasse gatilho ou LED junto apagaria o
    # que ela já tinha escolhido noutra aba.
    assert dele.triggers is None and dele.leds is None, (
        f"o override trouxe outras seções junto: {dele!r}")


def test_o_rotulo_nao_e_digitado(monkeypatch, tela) -> None:
    """A frase "30% da força" é REPRODUZIDA do produto, nunca digitada.

    MORDIDA: esta é a mordida — o monkeypatch abaixo troca o degrau do produto
    para 0,25. Se alguma das camadas tivesse a string digitada, o rótulo
    continuaria dizendo "30% da força" e este caso reprovaria. Uma régua que
    comparasse duas cópias digitadas passaria; esta não.
    """
    from hefesto_dualsense4unix.daemon.subsystems import rumble as subsistema

    antes = tela.opcoes_do_teto()
    assert "30% da força" in antes, f"o campo mudou de rótulo: {antes}"

    monkeypatch.setitem(subsistema.RUMBLE_POLICY_MULT, "economia", 0.25)
    depois = tela.opcoes_do_teto()

    assert "25% da força" in depois, (
        f"com `RUMBLE_POLICY_MULT['economia'] = 0.25` o campo continuou "
        f"oferecendo {depois}. Alguma camada tem a frase DIGITADA — é o mesmo "
        f"defeito que a dica desta aba tinha em 28/08, quando dizia 60% e o "
        f"produto cortava em 30.")
    assert "30% da força" not in depois, (
        f"o rótulo velho sobreviveu à troca do degrau: {depois}")
    # E A BORDA ACOMPANHA: o gesto confere o clique contra `opcoes_do_teto()`,
    # então o rótulo antigo tem de deixar de ser aceito no mesmo instante.
    with pytest.raises(ValueError):
        tela.politica_do_rotulo("30% da força")


def test_segue_o_global_limpa_o_override(pac, tela, gesto, disco) -> None:
    """A opção que não grava nada APAGA o que havia, e o clique repetido cala.

    MORDIDA: faça `_com_o_teto` gravar `ControllerRumbleOverride(policy=None)`
    em vez de `rumble=None`. O primeiro `assert` reprova: o campo `rumble` deixa
    de ser `None`, `_controllers_to_rumble_scales` não cai mais no desvio de
    `cfg.rumble is None` (`profiles/manager.py:1861`), e o "sem opinião" que o
    merge POR CAMPO promete vira uma opinião escrita.
    """
    estado, gravados = disco
    estado["Bancada"] = _perfil(
        controllers={CHAVE: {"rumble": {"policy": "economia"}}})
    p = PonteDeMentira()
    segue, _, _ = tela.opcoes_do_teto()

    gesto(_ctx(pac), {"uniq": UNIQ, "valor": segue}, p)

    assert len(gravados) == 1, f"gravou {len(gravados)} vez(es), esperava uma"
    dele = (gravados[0].controllers or {}).get(CHAVE)
    assert dele is not None and dele.rumble is None, (
        f"a seção `rumble` do override ficou {getattr(dele, 'rumble', '???')!r}. "
        f"'Segue o global' é a AUSÊNCIA da opinião, e o esquema já diz isso: "
        f"*campo não escrito = sem opinião*.")

    # O SEGUNDO CLIQUE IGUAL NÃO REGRAVA: um `profile.switch` no meio de uma
    # partida não é de graça, e regravar troca a data do arquivo.
    estado["Bancada"] = gravados[0]
    p2 = PonteDeMentira()
    gesto(_ctx(pac), {"uniq": UNIQ, "valor": segue}, p2)
    assert len(gravados) == 1, "regravou um perfil que já estava sem override"
    assert p2.chamadas == [], (
        f"pediu {p2.chamadas} ao daemon sem ter o que mudar")


def test_igual_ao_global_do_perfil_tambem_limpa(pac, tela, gesto, disco) -> None:
    """Override igual à política global não vira override — regra do produto.

    `app/draft_config.with_controller_rumble:1193-1223` já decidiu isso, e a
    razão é aritmética: `_controllers_to_rumble_scales` calcula `mult / base` e
    DESCARTA o fator 1,0 (`profiles/manager.py:1878-1879`).

    MORDIDA: tire o desvio `policy == global_` de `_com_o_teto` — o perfil passa
    a guardar um override que o motor ignora, e este caso reprova.
    """
    estado, gravados = disco
    estado["Bancada"] = _perfil(rumble={"policy": "economia"})
    p = PonteDeMentira()
    _, _, trinta = tela.opcoes_do_teto()

    gesto(_ctx(pac), {"uniq": UNIQ, "valor": trinta}, p)

    assert gravados == [], (
        "gravou um override igual à política global do perfil — o fator seria "
        "1,0, que `_controllers_to_rumble_scales` descarta de qualquer jeito.")


def test_sem_teto_recusa_dizendo_e_nao_grava(pac, tela, gesto, disco) -> None:
    """A opção sem tradução honesta RECUSA, e a recusa nomeia as duas leituras.

    MORDIDA: faça `politica_do_rotulo` devolver `"max"` para "Sem teto" — este
    caso reprova. É a mordida que impede a próxima pessoa de "completar" a
    feature adivinhando a resposta dela.
    """
    estado, gravados = disco
    estado["Bancada"] = _perfil()
    p = PonteDeMentira()
    _, sem_teto, _ = tela.opcoes_do_teto()

    with pytest.raises(ValueError) as erro:
        gesto(_ctx(pac), {"uniq": UNIQ, "valor": sem_teto}, p)

    frase = str(erro.value)
    assert "0,667" in frase or "0.667" in frase, (
        f"a recusa não nomeia a leitura que 'balanceado' produziria sob um "
        f"global 'max': {frase!r}")
    assert "max" in frase and "balanceado" in frase, (
        f"a recusa não nomeia as duas traduções possíveis: {frase!r}")
    assert gravados == [], "recusou dizendo E gravou assim mesmo"
    assert p.chamadas == [], f"falou com o daemon depois de recusar: {p.chamadas}"


# ---------------------------------------------------------------------------
# 2. a conta que chega ao motor
# ---------------------------------------------------------------------------
def test_o_fator_que_chega_ao_hardware_e_zero_ponto_tres(
        pac, tela, gesto, disco) -> None:
    """Do disco ao motor: `economia` sobre base `balanceado` vira `(200,200)→(60,60)`.

    É esta que prova que o rótulo diz a verdade sobre o MOTOR, e não só sobre o
    arquivo. Ela atravessa as três camadas que já existiam desde 10/08:
    `_controllers_to_rumble_scales` → `set_rumble_scales` → `_escalar_rumble`.

    MORDIDA: faça `_com_o_teto` gravar `balanceado` — o fator vira 1,0,
    `_controllers_to_rumble_scales` o descarta e este caso reprova com o par
    intacto. (A OUTRA mordida, arrancar a chamada a `set_rumble_scales` de
    `ProfileManager.apply`, é a do caso seguinte.)
    """
    from hefesto_dualsense4unix.profiles.manager import _controllers_to_rumble_scales

    estado, gravados = disco
    estado["Bancada"] = _perfil()
    p = PonteDeMentira()
    _, _, trinta = tela.opcoes_do_teto()
    gesto(_ctx(pac), {"uniq": UNIQ, "valor": trinta}, p)
    novo = gravados[0]

    escalas = _controllers_to_rumble_scales(novo.controllers, novo.rumble)
    assert escalas == {CHAVE: pytest.approx(0.3)}, (
        f"as escalas publicadas foram {escalas!r}. Sem opinião global, a base é "
        f"o `_RUMBLE_POLICY_PADRAO = 'balanceado'` (1,0), então o fator tem de "
        f"ser 0,3/1,0.")

    # O ÚLTIMO DEGRAU, com o backend de verdade e SEM abrir hardware nenhum:
    # `_escalar_rumble` é função pura sobre o mapa que `set_rumble_scales`
    # guardou.
    from hefesto_dualsense4unix.core.backend_pydualsense import PyDualSenseController

    motor = PyDualSenseController.__new__(PyDualSenseController)
    motor._rumble_scale_by_uniq = {}
    import threading

    motor._io_lock = threading.RLock()
    motor._key_to_uniq = lambda k: k  # type: ignore[method-assign]
    motor.set_rumble_scales(escalas)
    assert motor._escalar_rumble(CHAVE, 200, 200) == (60, 60), (
        f"o motor receberia {motor._escalar_rumble(CHAVE, 200, 200)} em vez de "
        f"(60, 60) — o rótulo promete 30% de 200.")
    # E QUEM NÃO TEM OVERRIDE NÃO É TOCADO: um arredondamento novo no caminho de
    # quem não pediu nada é regressão para os outros controles da mesa.
    assert motor._escalar_rumble("aabbcc000002", 200, 200) == (200, 200)


def test_a_ativacao_do_perfil_publica_as_escalas_no_backend(
        pac, tela, gesto, disco) -> None:
    """O elo que faz a escolha dela VALER AGORA — e que régua nenhuma cobria.

    `perfil.gravar_e_reaplicar` pede `profile.switch`; quem o atende chama
    `ProfileManager.apply`, e é ali (`profiles/manager.py:459-464`) que o mapa
    por-peça é publicado no backend. Sem esse elo o perfil muda no disco e o
    motor continua com a força velha até o próximo start do daemon.

    MEDIDO em 01/09/2026: nenhum teste desta casa cobria a chamada — o
    `test_por_unidade_01_todas_as_abas.py` mede as pontas
    (`_controllers_to_rumble_scales` e `_escalar_rumble`) e não o meio.

    MORDIDA: arranque o `escalar_rumble(escalas_rumble or None)` de
    `ProfileManager.apply` — este caso reprova dizendo que nada foi publicado.
    """
    from hefesto_dualsense4unix.profiles.manager import ProfileManager
    from hefesto_dualsense4unix.testing.fake_controller import FakeController

    estado, gravados = disco
    estado["Bancada"] = _perfil()
    _, _, trinta = tela.opcoes_do_teto()
    gesto(_ctx(pac), {"uniq": UNIQ, "valor": trinta}, PonteDeMentira())

    class Espiao(FakeController):
        def __init__(self, **kw: Any) -> None:
            super().__init__(**kw)
            self.publicadas: list[Any] = []

        def set_rumble_scales(self, scales: Any = None) -> None:
            self.publicadas.append(None if scales is None else dict(scales))

    fc = Espiao(transport="usb")
    fc.connect()
    ProfileManager(controller=fc).apply(gravados[0])

    assert fc.publicadas == [{CHAVE: pytest.approx(0.3)}], (
        f"a ativação publicou {fc.publicadas!r} no backend. Sem o mapa, o "
        f"`_escalar_rumble` não tem fator e o motor recebe a força inteira — o "
        f"perfil dela mudaria no disco e o aparelho não.")


# ---------------------------------------------------------------------------
# 3. a borda
# ---------------------------------------------------------------------------
def test_a_borda_recusa_o_clique_sem_dono(pac, tela, gesto, disco) -> None:
    """Três recusas, uma por vez — e nenhuma delas grava.

    MORDIDA: troque o `_chave_no_perfil` do gesto por
    `uniq.replace(":", "").lower()` — o MAC forjado que começa em `02` passa,
    dois clones do mesmo modelo viram UMA chave no perfil, e este caso reprova.
    """
    estado, gravados = disco
    estado["Bancada"] = _perfil()
    _, _, trinta = tela.opcoes_do_teto()

    # (a) o clique não disse em qual controle
    with pytest.raises(ValueError):
        gesto(_ctx(pac), {"uniq": "", "valor": trinta}, PonteDeMentira())

    # (b) o MAC FORJADO — dois clones do mesmo modelo o compartilham
    with pytest.raises(RuntimeError):
        gesto(_ctx(pac, uniq=UNIQ_FORJADO),
              {"uniq": UNIQ_FORJADO, "valor": trinta}, PonteDeMentira())

    # (c) um rótulo que não é opção desta lista
    with pytest.raises(ValueError):
        gesto(_ctx(pac), {"uniq": UNIQ, "valor": "Dobro da força"}, PonteDeMentira())

    assert gravados == [], f"uma das três recusas gravou assim mesmo: {gravados}"


def test_sem_perfil_ativo_recusa_dizendo_onde_escolher(pac, tela, gesto, disco) -> None:
    """A força de um controle é do PERFIL, não da máquina — e a tela diz onde.

    MEDIDO no daemon vivo dela em 01/09/2026: `active_profile = None`. Logo é
    ESTA a resposta que a tela dela dá hoje, e é a honesta — não um silêncio.

    MORDIDA: tire o desvio do nome vazio — o `load_profile("")` estoura com um
    `KeyError` cru, e a tela mostra um traceback em vez de uma frase.
    """
    estado, gravados = disco
    estado["Bancada"] = _perfil()
    _, _, trinta = tela.opcoes_do_teto()

    with pytest.raises(RuntimeError) as erro:
        gesto(_ctx(pac, ativo=""), {"uniq": UNIQ, "valor": trinta}, PonteDeMentira())

    frase = str(erro.value)
    assert "Perfis" in frase, (
        f"a recusa não diz em que aba escolher um perfil: {frase!r}")
    assert gravados == [], "recusou e gravou assim mesmo"


# ---------------------------------------------------------------------------
# 4. a pintura
# ---------------------------------------------------------------------------
def test_a_pintura_mostra_o_que_esta_no_disco(a08, tela) -> None:
    """O campo mostra o OVERRIDE, não o padrão do desenho.

    MORDIDA: arranque a leitura de `controllers[...]["rumble"]` de
    `_teto_do_controle` — volta sempre "Segue o global", e este caso reprova. É
    a mordida que mata o defeito nomeado no `sel()` do gerador: *o segundo
    clique parece o primeiro*.
    """
    segue, _, trinta = tela.opcoes_do_teto()
    sem_dono: dict[str, str] = {}

    com = a08._teto_do_controle(
        {CHAVE: {"rumble": {"policy": "economia"}}}, UNIQ, _bancada(), sem_dono)
    assert com[0] == trinta, (
        f"com `policy='economia'` no disco o campo mostrou {com[0]!r}")
    assert "sobrepõe" in com[1], f"o `?` não diz que este controle sobrepõe: {com[1]!r}"
    # A FRASE INTEIRA, e não só a cláusula do meio. Pintar é trocar o
    # `innerHTML`: o que não for pintado some da tela. MEDIDO na tela viva em
    # 01/09/2026 — o primeiro rascunho desta leva APAGAVA o ponteiro para a aba
    # onde o global se muda, e a foto o mostrou.
    #
    # MORDIDA: em `_teto_do_controle`, volte a `frase = teto_que_vale(...)[1]` —
    # este `assert` reprova.
    assert tela.ABA_DO_TETO_GLOBAL in com[1] and "RUMBLE_POLICY_MULT" in com[1], (
        f"a dica pintada perdeu o ponteiro para onde o global se muda: {com[1]!r}")

    sem = a08._teto_do_controle({}, UNIQ, _bancada(), sem_dono)
    assert sem[0] == segue, f"sem override o campo mostrou {sem[0]!r}"
    assert "segue o global" in sem[1], f"o `?` não diz que segue: {sem[1]!r}"
    assert sem_dono == {}, f"declarou sem_dono sem ter motivo: {sem_dono}"

    # A CHAVE É A NORMALIZADA. Procurar por `aa:bb:…` não acharia nada, e o
    # campo mostraria "Segue o global" para sempre sobre um disco que discorda.
    assert a08._teto_do_controle(
        {CHAVE: {"rumble": {"policy": "economia"}}}, UNIQ.upper(), _bancada(), {})[0] == trinta


def test_a_politica_que_a_tela_nao_oferece_e_declarada(a08, tela) -> None:
    """`max` no disco: o campo NÃO escolhe nenhuma das três, e a razão fica escrita.

    MORDIDA: faça `rotulo_da_politica` cair em `fala_do_teto(policy)` — `max`
    passa a ser traduzido como "Sem teto", que É opção do campo, e este caso
    reprova. Foi exatamente esse o defeito no primeiro rascunho desta leva.
    """
    sem_dono: dict[str, str] = {}
    campo, frase = a08._teto_do_controle(
        {CHAVE: {"rumble": {"policy": "max"}}}, UNIQ, _bancada(), sem_dono)

    assert campo is None, (
        f"o campo escolheu {campo!r} para uma política que ele não sabe mostrar "
        f"— isso é a tela afirmando um estado que o disco contradiz.")
    assert "max" in frase, f"o `?` não diz o que há no disco: {frase!r}"
    assert sem_dono, "a política não declarada não entrou em `sem_dono`"
    assert "max" in next(iter(sem_dono.values()))

    # E `balanceado` CAI NO MESMO LUGAR — é o par que `fala_do_teto` traduziria
    # como "Sem teto", a única opção sem tradução.
    assert a08._teto_do_controle(
        {CHAVE: {"rumble": {"policy": "balanceado"}}}, UNIQ, _bancada(), {})[0] is None


def test_o_pacote_publica_os_dois_enderecos(pac, a08, tela, monkeypatch) -> None:
    """O `pacote()` inteiro entrega o campo E o `?` de cada controle da mesa.

    MORDIDA: tire a linha `"teto-explica": teto_frase` do `pacote()` — este caso
    reprova, e sem ele a caixa diria "30% da força" com a dica ao lado dizendo
    "este controle segue o global": uma contradição NOVA, nossa.
    """
    monkeypatch.setattr(
        a08.perfil, "ativo",
        lambda _nome: {"controllers": {CHAVE: {"rumble": {"policy": "economia"}}}})
    monkeypatch.setattr(a08, "_orcamento_da_mesa", lambda: (None, True))

    saida = a08.pacote(_ctx(pac))
    coluna = saida["colunas"][UNIQ]

    _, _, trinta = tela.opcoes_do_teto()
    assert coluna["teto-da-vibracao"] == trinta, (
        f"o campo veio {coluna.get('teto-da-vibracao')!r}")
    assert "teto-explica" in coluna and "<b>" in coluna["teto-explica"], (
        f"a dica do `?` não veio pintada: {coluna.get('teto-explica')!r}")


# ---------------------------------------------------------------------------
# 5. a página publicada
# ---------------------------------------------------------------------------
def _pagina_publicada() -> str:
    import onde

    return (onde.PUBLICADO / "08-conexoes.html").read_text(encoding="utf-8")


def test_a_pagina_publicada_tem_os_dois_enderecos() -> None:
    """Sem `data-campo` o campo é cena estática — e a dica seria texto literal.

    MORDIDA: tire o `campo="teto-da-vibracao"` da chamada de `sel()` em
    `interface/aba08.py`, regere num desvio `HEFESTO_BANCADA` (NUNCA sobre o
    mockup dela) e publique — este caso reprova.
    """
    doc = _pagina_publicada()
    selects = re.findall(r"<select[^>]*data-gesto=\"teto-da-vibracao\"[^>]*>", doc)
    assert selects, "a página publicada não tem o `<select>` do teto da vibração"
    for tag in selects:
        assert 'data-campo="teto-da-vibracao"' in tag, (
            f"o campo do teto não tem endereço de pintura: {tag}")
        assert 'data-hef-alvo="valor"' in tag, (
            f"sem `data-hef-alvo=\"valor\"` o piloto escreveria o texto DENTRO "
            f"do `<select>` em vez de escolher a opção: {tag}")

    dicas = re.findall(r"<span class=\"dica\"[^>]*data-campo=\"teto-explica\"[^>]*>", doc)
    assert len(dicas) == len(selects), (
        f"{len(selects)} campo(s) de teto e {len(dicas)} dica(s) endereçada(s) — "
        f"ligar só a caixa cria a contradição entre o campo e o `?`.")
    for tag in dicas:
        assert 'data-hef-alvo="html"' in tag, (
            f"a dica do teto traz `<b>` e `<code>`; sem o alvo `html` o "
            f"`textContent` os escreveria como texto literal: {tag}")


def test_o_piloto_sabe_pintar_html() -> None:
    """O `BOOTSTRAP` tem o ramo `html` — sem ele a dica mostraria os marcadores.

    MORDIDA: tire o ramo `if(alvo === 'html')` do `escrever()` — este caso
    reprova, e na tela a dica passaria a exibir `<b>` como texto.
    """
    from hefesto_dualsense4unix.interface import hefesto_vivo

    assert "alvo === 'html'" in hefesto_vivo.BOOTSTRAP, (
        "o `escrever()` do piloto não tem o alvo `html`")
    assert "el.innerHTML = t" in hefesto_vivo.BOOTSTRAP, (
        "o alvo `html` existe e não escreve `innerHTML`")


# ---------------------------------------------------------------------------
# 6. a contabilidade da aba
# ---------------------------------------------------------------------------
def test_o_gesto_saiu_do_inventario_do_que_falta(a08) -> None:
    """Um gesto ligado não pode continuar listado como "sem dono".

    MORDIDA: devolva a entrada `teto-da-vibracao` a `SEM_GESTO` — este caso
    reprova, e o piloto voltaria a imprimir `[gesto sem dono]` sobre um botão
    que funciona.
    """
    assert "teto-da-vibracao" not in a08.SEM_GESTO, (
        "o gesto tem dono e continua na lista do que falta")
    assert "teto-da-vibracao" in a08.SEM_ECO, (
        "o `state_full` não publica override por controle nenhum — a prova "
        "deste gesto é o ARQUIVO, e ele tem de estar declarado sem eco.")
    assert a08.PISO_DA_ABA >= 16, (
        f"o piso da aba é {a08.PISO_DA_ABA} e só sobe — com 15 a régua dos "
        f"botões passaria com este gesto apagado.")


def test_a_recusa_velha_saiu_dos_dois_lugares(a08, tela) -> None:
    """O fato errado sai de TODOS os lugares — regra dela, 11/08/2026.

    A afirmação *"o produto aplica `min` … sobrepor mudaria o daemon"* estava em
    DOIS: no `SEM_GESTO` deste pacote e no `SEM_FONTE` da camada de tela. Uma
    correção pela metade deixa as duas versões vivas, que é o defeito que a
    regra existe para matar.
    """
    enderecos = {linha[0] for linha in tela.SEM_FONTE}
    assert "controle.*.vibracao.teto" not in enderecos, (
        "a linha antiga continua em `SEM_FONTE` dizendo que a tela inteira não "
        "tem fonte — duas das três opções têm.")
    sobrou = [linha for linha in tela.SEM_FONTE
              if linha[0] == "controle.*.vibracao.sem-teto"]
    assert sobrou, "a recusa que SOBRA ('Sem teto') não está declarada"
    assert "MIGRA-CONEXOES-11" in sobrou[0][2], (
        f"a linha que sobrou não nomeia a dona: {sobrou[0][2]!r}")


# ---------------------------------------------------------------------------
# 7. o desenho dela não mudou
# ---------------------------------------------------------------------------
# O `_sem_o_quarto_selo` MORREU EM 03/09/2026, junto com a comparação byte a
# byte que ele servia. Ele desfazia no texto da bancada a cura do quarto selo
# para o resto poder ser comparado; era a primeira linha de uma lista de
# descontos, e uma lista de descontos que cresce a cada sprint fica verde por
# construção. Ver o caso abaixo.

#: O que a tela MOSTRA em palavras: sem `<style>`, sem `<script>`, sem
#: comentário, sem tag e sem espaço sobrando. É o que uma pessoa lê na aba.
_FOLHA = re.compile(r"<(style|script)\b.*?</\1>", re.S | re.I)
_COMENTARIO_HTML = re.compile(r"<!--.*?-->", re.S)
_TAG = re.compile(r"<[^>]+>")


def _texto_visivel(bruto: bytes) -> str:
    texto = _FOLHA.sub(" ", bruto.decode("utf-8"))
    texto = _COMENTARIO_HTML.sub(" ", texto)
    return " ".join(_TAG.sub(" ", texto).split())


def test_o_desenho_dela_so_mudou_no_que_esta_declarado() -> None:
    """A bancada e o publicado dizem as MESMAS PALAVRAS, byte a byte.

    **ESTE CASO ENCOLHEU EM 03/09/2026, e a razão é a sprint
    `IDENTIDADE-VEM-DE-CIMA-01`.** Ele exigia igualdade byte a byte entre a
    bancada e o publicado, descontada UMA cura nomeada (o quarto selo). A
    sprint da identidade mudou a FORMA de três coisas nesta aba — a cor do
    plástico saiu de um `--plastico` inline e virou a tinta de um `<i>` de 3px;
    a régua do rádio ganhou um recipiente com endereço; a lista de aparelhos
    ganhou o dela —, e nenhuma delas move um pixel.

    **UMA LISTA DE DESCONTOS QUE CRESCE A CADA SPRINT NÃO É RÉGUA, É DIÁRIO.**
    Ela ficaria verde por construção — cada leva acrescentaria a própria linha
    —, que é o defeito que esta casa chama de *régua que digita o que devia
    ler*. Então ele passou a medir o que continua sendo verdade e o que ele
    consegue ler sem lista nenhuma: **as palavras da tela.**

    O QUE ELE AINDA PEGA: uma palavra trocada, uma frase que sumiu, um número
    que mudou, uma dica reescrita — tudo o que chega aos olhos como TEXTO.

    O QUE ELE DEIXOU DE PEGAR, e está dito porque um buraco calado é pior que
    um buraco: uma COR mudada, uma medida de CSS, um bloco movido. Quem cobre
    isso são dois outros, e os dois estão ligados: o portão `desenho-aprovado`
    reprova QUALQUER divergência entre bancada e publicado que não esteja
    declarada em `mockup/DIVERGENCIAS.md` — e a declaração é o que ela lê antes
    de publicar —, e a `scripts/check_identidade_vem_de_cima.py` cobra que
    nenhuma cor de plástico fique congelada na página.

    **O NOME PROMETIA O QUE O CORPO NÃO FAZIA — corrigido em 03/09/2026.** Ele
    se chama *"só mudou no que está DECLARADO"* e nunca abriu a declaração:
    exigia igualdade de texto sempre, e por isso ficava vermelho no instante em
    que alguém fazia a coisa certa — adiantar a bancada e declarar a divergência
    em `mockup/DIVERGENCIAS.md`, que é o processo desta casa. Reprovava o
    processo, não o defeito.

    Em 03/09 a `08-conexoes` foi declarada duas vezes (o `MIGRA-08-01`, com dez
    endereços de pintura, e o desenho do controle que passou a vestir o
    aparelho), e a declaração diz o que ela vê hoje sem publicar. A régua passou
    a ler a MESMA fonte que o portão `desenho-aprovado` lê — `declaradas()`, do
    próprio script —, e a cobrar cada caso no seu estado:

    * **não declarada** → as palavras têm de bater. É a mordida original, e é a
      que pega a palavra trocada de fininho;
    * **declarada** → a bancada pode estar à frente, e o que se cobra é que a
      declaração exista de verdade. Some no dia do `--publicar`, e a igualdade
      volta a ser exigida sozinha.

    MORDIDAS (duas): mude uma palavra visível de um `<option>` no gerador,
    regere e tire a seção da `DIVERGENCIAS.md` — reprova com a palavra na
    mensagem; ou deixe a seção lá com o corpo vazio — reprova dizendo que
    declaração sem razão não é declaração.
    """
    import importlib.util

    import onde

    alvo = RAIZ / "scripts/check_o_desenho_aprovado.py"
    spec = importlib.util.spec_from_file_location("check_desenho_da_regua", alvo)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules["check_desenho_da_regua"] = mod
    spec.loader.exec_module(mod)

    bancada = _texto_visivel(mod.o_que_se_ve(onde.BANCADA / "08-conexoes.html"))
    publicado = _texto_visivel(mod.o_que_se_ve(onde.PUBLICADO / "08-conexoes.html"))

    if "08-conexoes.html" not in mod.declaradas():
        assert bancada == publicado, (
            "a bancada da 08 passou a DIZER uma coisa que o publicado não diz — "
            "e palavra de tela é decisão dela, não de quem gera a página. Se "
            "isso é adiantamento com razão, declare em `mockup/DIVERGENCIAS.md`.")
        return

    # DECLARADA: a bancada pode estar à frente, e é a razão escrita que faz a
    # diferença entre adiantar com método e adiantar por descuido. Cobrar o
    # FORMATO da razão faria a régua brigar com quem escreve bem (a lição do
    # `SERVE_UM_LADO_SO`), então cobra-se que exista corpo — não como ele é.
    texto = (RAIZ / "mockup/DIVERGENCIAS.md").read_text(encoding="utf-8")
    corpo = texto.split("\n---\n", 1)[-1]
    secao = corpo.split("## 08-conexoes.html", 1)[-1].split("\n## ", 1)[0]
    assert secao.strip(), (
        "a `08-conexoes.html` está declarada em `mockup/DIVERGENCIAS.md` com a "
        "seção VAZIA. Um título sem razão isenta a aba do portão sem contar a "
        "ninguém o que mudou — que é o oposto do que a declaração existe para "
        "fazer.")


def test_a_divergencia_do_quarto_selo_esta_declarada() -> None:
    """Bancada à frente do publicado só vale DECLARADA — é o portão do desenho.

    Sem a seção em `mockup/DIVERGENCIAS.md`, o `desenho-aprovado` reprova a aba
    inteira; com ela, o que espera a palavra dela fica escrito onde ela lê.
    """
    texto = (RAIZ / "mockup/DIVERGENCIAS.md").read_text(encoding="utf-8")
    corpo = texto.split("\n---\n", 1)[-1]
    assert "## 08-conexoes.html" in corpo, (
        "a bancada da 08 andou à frente do publicado e ninguém declarou — o "
        "portão `desenho-aprovado` reprova, e com razão")


def test_o_json_do_perfil_sobrevive_ao_disco(tmp_path, pac, tela, gesto,
                                             monkeypatch) -> None:
    """A prova do DISCO: o que o gesto grava volta a ser lido pelo loader.

    Sem ela, tudo acima mede objetos em memória — e o esquema recusa o documento
    INTEIRO quando uma chave não casa (`_validate_controllers_keys`), o que na
    tela dela vira "não consegui gravar" sem dizer o quê.

    O `XDG_CONFIG_HOME` aponta para o `tmp_path` do pytest: nada é escrito na
    pasta de perfis DELA, e o daemon vivo não vê nada. A ponte é dublê.
    """
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    from hefesto_dualsense4unix.profiles import loader
    from hefesto_dualsense4unix.utils import xdg_paths

    pasta = tmp_path / "hefesto-dualsense4unix" / "profiles"
    pasta.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(xdg_paths, "profiles_dir",
                        lambda ensure=False: pasta, raising=False)
    monkeypatch.setattr(loader, "_profiles_dir", lambda: pasta, raising=False)

    prof = _perfil("Descartavel")
    loader.save_profile(prof, origem="regua-do-teto")
    antes = sorted(p.name for p in pasta.glob("*.json"))
    assert antes, f"o loader não gravou nada em {pasta}"

    p = PonteDeMentira()
    _, _, trinta = tela.opcoes_do_teto()
    gesto(_ctx(pac, ativo="Descartavel"), {"uniq": UNIQ, "valor": trinta}, p)

    depois = sorted(p_.name for p_ in pasta.glob("*.json"))
    assert depois == antes, (
        f"o gesto criou ou apagou arquivo: {antes} -> {depois}")

    cru = json.loads((pasta / antes[0]).read_text(encoding="utf-8"))
    assert cru["controllers"][CHAVE]["rumble"]["policy"] == "economia", (
        f"o JSON em disco ficou {cru.get('controllers')!r}")
    relido = loader.load_profile("Descartavel")
    assert relido.controllers[CHAVE].rumble.policy == "economia", (
        "o loader não conseguiu reler o que o gesto gravou")
    # E O `profile.switch` FOI PEDIDO, porque o nome casa o ativo — é o que faz
    # `apply_profile` publicar as escalas no backend e a escolha VALER AGORA.
    assert ("profile_switch", ("Descartavel",)) in p.chamadas, (
        f"o gesto fez {p.chamadas} e não pediu o `profile.switch`")


# ---------------------------------------------------------------------------
# 8. A PALAVRA "GLOBAL" TEM UM DONO SÓ — os quatro bloqueantes de 01/09/2026
#
# A leva entregou o campo GRAVANDO e a frase do `?` ao lado dele MENTINDO: ela
# chamava de "o global" o ORÇAMENTO DA MESA (`maquina.json`) e ignorava as duas
# coisas que decidem a força de verdade —
#
#   `state['rumble_policy']`   o que MULTIPLICA no funil (`_effective_mult`)
#   `Profile.rumble.policy`    o DENOMINADOR do fator por peça
#
# Medido: com a política viva em `economia` e nenhum override, o motor recebia
# 30% e o `?` afirmava, em negrito, "o global vale **Sem teto**". Com um
# override `economia` sob global vivo `max`, o campo dizia "30% da força" e o
# motor recebia 45% — um campo chamado TETO entregando acima do teto.
# ---------------------------------------------------------------------------
def _fator_no_motor(fator: dict[str, float], mult: float, pedido: int = 200) -> int:
    """O que o `_escalar_rumble` do backend entrega, com o funil já aplicado.

    É a PONTA da cadeia, e não um dublê dela: o mesmo método que as duas rotas
    de escrita do DualSense chamam antes de tocar o motor.
    """
    import threading

    from hefesto_dualsense4unix.core.backend_pydualsense import PyDualSenseController

    m = PyDualSenseController.__new__(PyDualSenseController)
    m._rumble_scale_by_uniq = {}
    m._io_lock = threading.RLock()
    m.set_rumble_scales(fator)
    return int(m._escalar_rumble(UNIQ, int(pedido * mult), int(pedido * mult))[0])


@pytest.mark.parametrize("viva", ["balanceado", "economia", "max"])
def test_a_dica_diz_o_que_chega_ao_motor_e_nao_o_degrau_do_rotulo(tela, a08, viva) -> None:
    """A CADEIA INTEIRA, medida: a frase do `?` == o que sai no `_escalar_rumble`.

    É o elo que régua nenhuma desta casa cobria, e a ausência dele deixou passar
    o bloqueante: o fator por peça é RELATIVO ao global do PERFIL
    (`profiles/manager.fator_da_unidade`) e quem multiplica é a política VIVA do
    DAEMON (`core.rumble.forca_do_global`). Os dois divergem com dois cliques
    dentro desta mesma interface — a aba Vibração grava `daemon_cfg.rumble_policy`
    e `apply_profile_rumble_policy` deixa política de origem MANUAL intocada.

    MEDIDO em 01/09/2026, com um override `economia` (rótulo "30% da força")::

        global vivo   motor        o que a frase dizia ANTES
        balanceado    60/200=30%   "30% da força"  (a única em que era verdade)
        economia      18/200= 9%   "30% da força"
        max           90/200=45%   "30% da força"  — acima do teto que promete

    MORDIDA: em `gui.aba_conexoes.forca_no_motor`, devolva o degrau nominal
    (`RUMBLE_POLICY_MULT[v.do_controle]`) ignorando o global vivo — os casos
    `economia` e `max` reprovam. Outra: apague o `global_ * fator` e devolva só
    `global_` — os três reprovam.
    """
    from hefesto_dualsense4unix.core.rumble import _effective_mult
    from hefesto_dualsense4unix.daemon.lifecycle import DaemonConfig
    from hefesto_dualsense4unix.profiles.manager import _controllers_to_rumble_scales

    prof = _perfil()
    fator = _controllers_to_rumble_scales(
        a08._com_o_teto(prof, CHAVE, "economia").controllers, prof.rumble)
    cfg = DaemonConfig()
    cfg.rumble_policy = viva
    mult, _, _ = _effective_mult(cfg, 100, 0.0, 1.0, 0.0)
    saiu = _fator_no_motor(fator, mult)

    v = tela.Vibracao(do_controle="economia", do_perfil=prof.rumble.policy, a_viva=viva)
    campo, frase = tela.teto_que_vale(v)
    esperado = tela.por_cento(saiu / 200)
    assert f"<b>{esperado}</b>" in frase, (
        f"com o global vivo em {viva!r} o motor recebe {saiu}/200 = {esperado}, "
        f"e a dica disse: {re.sub('<[^>]+>', '', frase)!r}")
    # A CAIXA CONTINUA MOSTRANDO O DEGRAU ESCOLHIDO — ela é a escolha dela, não o
    # resultado. Quando os dois divergem, a frase DIZ que o degrau é relativo; é a
    # diferença entre a tela explicar e a tela mentir.
    _, _, trinta = tela.opcoes_do_teto()
    assert campo == trinta, f"a caixa deixou de mostrar a escolha dela: {campo!r}"
    if esperado != trinta:
        assert "RELATIVO" in frase, (
            f"o motor entrega {esperado} com a caixa em {trinta}, e a dica não "
            f"explica a diferença: {re.sub('<[^>]+>', '', frase)!r}")


def test_o_global_do_perfil_nao_e_o_que_multiplica(tela) -> None:
    """`Profile.rumble.policy` é DENOMINADOR, e não o global que a tela reporta.

    O bloqueante em uma linha: com `meu_perfil.rumble.policy = "economia"` no
    disco, a dica escrevia *"este controle segue o global, que vale **Sem
    teto**"*. Sem override, o que chega ao motor é o que a política VIVA deixa
    passar — e o global do perfil só entra como base do fator de quem sobrepõe.

    MORDIDA: em `teto_que_vale`, volte a `global_ = fala_do_teto(v.orcamento)` e
    à frase `"que vale <b>{global_}</b>"` — os dois `assert` abaixo reprovam.
    """
    from hefesto_dualsense4unix.core.rumble import SEM_TETO

    segue = tela.teto_que_vale(tela.Vibracao(do_perfil="economia", a_viva="balanceado"))
    assert SEM_TETO not in segue[1], (
        f"a dica afirma {SEM_TETO!r} com a política viva em `balanceado`: {segue[1]!r}")
    assert "<b>100% da força</b>" in segue[1], (
        f"sem override, o motor recebe o que a viva deixa passar (1,0): {segue[1]!r}")

    # E O DENOMINADOR IMPORTA PARA QUEM SOBREPÕE: a mesma peça em `economia`, sob
    # um perfil cujo global JÁ é `economia`, tem fator 1,0 — logo entrega o que o
    # global entrega, e não 30% de novo.
    sobre = tela.teto_que_vale(
        tela.Vibracao(do_controle="economia", do_perfil="economia", a_viva="balanceado"))
    assert "<b>100% da força</b>" in sobre[1], (
        f"o fator relativo ao próprio global do perfil é 1,0: {sobre[1]!r}")


def test_o_teto_do_orcamento_entra_por_cima_da_politica_viva(tela) -> None:
    """O `maquina.json` limita a viva com `min`, e a dica mostra o resultado.

    MORDIDA: em `core.rumble.forca_do_global`, tire o `_sob_o_teto` e devolva
    `RUMBLE_POLICY_MULT[policy]` cru — este caso reprova com 150%, e o
    `_effective_mult` do daemon perde o teto junto (é o mesmo corpo).
    """
    sob_teto = tela.teto_que_vale(tela.Vibracao(a_viva="max", orcamento="economia"))[1]
    assert "<b>30% da força</b>" in sob_teto, (
        f"o orçamento `economia` não limitou o global `max`: {sob_teto!r}")
    sem_teto = tela.teto_que_vale(tela.Vibracao(a_viva="max", orcamento=None))[1]
    assert "<b>150% da força</b>" in sem_teto, (
        f"sem orçamento declarado o `max` passa inteiro: {sem_teto!r}")


@pytest.mark.parametrize("campos,porque", [
    ({"a_viva": None}, "o serviço não publicou o `rumble_policy`"),
    ({"a_viva": "auto"}, "o degrau do `auto` muda com a bateria a cada tique"),
    ({"a_viva": "balanceado", "a_mesa_respondeu": False},
     "o `maquina.json` não deu para ler"),
])
def test_o_que_nao_se_sabe_nao_vira_a_afirmacao_sem_teto(tela, campos, porque) -> None:
    """"Não sei" é uma resposta; "Sem teto" é uma AFIRMAÇÃO sobre um limite.

    Os três casos abaixo viravam a palavra em negrito **"Sem teto"** antes de
    01/09/2026 — a ausência de notícia lida como sucesso, no campo que ela
    clica. O dono da fonte proíbe a troca com todas as letras
    (`secao_orcamento.orcamento_em_vigor`: *"None aqui significa 'não sei',
    nunca 'sem teto'"*), e o `_orcamento_da_mesa` tinha um `except Exception:
    return None` que a fazia em silêncio.

    MORDIDA: em `forca_no_motor`, troque o `return None` do desvio do
    `a_mesa_respondeu` por `return 1.0` — o terceiro caso reprova, porque a tela
    passa a afirmar 100% sobre um arquivo que não foi lido.
    """
    from hefesto_dualsense4unix.core.rumble import SEM_TETO

    frase = tela.teto_que_vale(tela.Vibracao(**campos))[1]
    assert SEM_TETO not in frase, f"afirmou {SEM_TETO!r} quando {porque}: {frase!r}"
    assert "% da força" not in frase, (
        f"afirmou um percentual quando {porque}: {frase!r}")
    assert tela.NAO_SEI_A_FORCA in frase, (
        f"não disse que não sabe quando {porque}: {frase!r}")


def test_o_orcamento_sai_da_declaracao_que_o_modulo_ja_tem_e_sem_gtk(a08, tela) -> None:
    """`_orcamento_da_mesa` lê o cache do `maquina.json`, e distingue os dois `None`.

    DUAS COISAS, e as duas eram defeito:

    1. ele abria o arquivo DE NOVO a cada tique, por
       `secao_orcamento.orcamento_em_vigor()`, que arrasta `gi`/`Gtk` para o
       processo — com a resposta já em memória a 470 linhas de distância
       (`_DECLARACAO`, o `maquina.json` inteiro já validado);
    2. o `except Exception: return None` fazia "não consegui ler" e "ninguém
       declarou" virarem o mesmo valor.

    MORDIDA: devolva `(chave, True)` incondicionalmente — o `assert` do par
    reprova. Outra: volte ao `orcamento_em_vigor()` em `_orcamento_da_mesa` ou ao
    `from ...secao_orcamento import SEM_TETO` em `fala_do_teto` — o subprocesso
    do Gtk reprova.
    """
    tela.opcoes_do_teto()
    tela.teto_que_vale(tela.Vibracao(a_viva="balanceado"))
    a08._orcamento_da_mesa()

    guardado_cache, guardada = a08._DECLARACAO, a08._declaracao
    passou: list[bool] = []

    def _mudo(recarregar: bool = False) -> None:
        passou.append(True)
        return None

    try:
        a08._DECLARACAO = None
        a08._declaracao = _mudo
        assert a08._orcamento_da_mesa() == (None, False), (
            "com o `maquina.json` ilegível, `_orcamento_da_mesa` tem de dizer que "
            "a mesa NÃO respondeu — senão a dica publica `Sem teto` sobre um "
            "arquivo que ninguém leu.")
        assert passou, "não passou pelo `_declaracao()` deste módulo"
    finally:
        a08._declaracao = guardada
        a08._DECLARACAO = guardado_cache


def test_a_frase_do_orcamento_passa_pelo_dono_do_numero(tela, monkeypatch) -> None:
    """`fala_do_teto` deriva de `core.rumble.teto_do_orcamento`, o dono declarado.

    ERA A QUARTA GRAFIA da regra "chave de orçamento → frase do teto", e a única
    que não passava pelo dono: as outras três (`gui.aba_sistema.forca_do_perfil`,
    `secao_orcamento.celula_do_teto` e `_dica_da_bateria_longa`) já o chamavam.
    Medido com o dono mordido para 0,5: a aba Sistema dizia "50% da força" e esta
    aba dizia "30%" — duas abas do mesmo produto, dois números para o mesmo fato.

    MORDIDA: esta é a mordida — o monkeypatch abaixo troca o DONO. Com a conta
    escrita à mão em `fala_do_teto` (o `if chave != _ORCAMENTO_COM_TETO` indo
    direto ao `RUMBLE_POLICY_MULT`), este caso reprova.
    """
    import hefesto_dualsense4unix.core.rumble as nucleo

    monkeypatch.setattr(nucleo, "teto_do_orcamento",
                        lambda o: 0.5 if o == "economia" else None)
    assert tela.fala_do_teto("economia") == "50% da força", (
        f"a frase não seguiu o dono do número: {tela.fala_do_teto('economia')!r}")


def test_o_numero_da_recusa_e_derivado_e_nao_digitado(tela, monkeypatch) -> None:
    """O `0,667` da recusa de "Sem teto" sai da tabela, não de três literais.

    Ele estava DIGITADO em três lugares — o `SEM_FONTE`, a mensagem do
    `ValueError` e um `assert "0,667" in frase` desta régua —, e a régua guardava
    o número digitado: com o degrau `max` mordido para 2,0, os 18 casos ficavam
    verdes e a frase mentia na cara dela.

    MORDIDA: esta é a mordida — o monkeypatch troca o degrau. Com o número
    digitado, este caso reprova.
    """
    from hefesto_dualsense4unix.daemon.subsystems import rumble as subsistema

    monkeypatch.setitem(subsistema.RUMBLE_POLICY_MULT, "max", 2.0)
    with pytest.raises(ValueError) as erro:
        tela.politica_do_rotulo("Sem teto")
    assert "1/2 = 0,500" in str(erro.value), (
        f"a conta da recusa não acompanhou o degrau: {erro.value}")


def test_a_chave_da_pintura_e_a_mesma_da_gravacao(a08, tela) -> None:
    """As duas passam pelo `_so_hex`, e um `uniq` sujo não separa o par.

    A leva escreveu a expressão `replace(":","").replace("-","").lower()` mais
    DUAS vezes — uma em `_chave_no_perfil` (a chave que GRAVA) e outra em
    `_teto_do_controle` (a que PINTA) —, e a segunda já nascia sem o `.strip()`
    do helper. Um `uniq` com espaço ou quebra fazia a gravação cair em
    `aabbcc000001` e a pintura procurar outra coisa: a tela mostraria "Segue o
    global" para sempre sobre um disco que diz `economia`.

    MORDIDA: volte a expressão à mão em `_teto_do_controle`, sem o `.strip()` —
    este caso reprova.
    """
    sujo = UNIQ + "\n"
    assert a08._so_hex(sujo) == CHAVE
    _, _, trinta = tela.opcoes_do_teto()
    campo, _frase = a08._teto_do_controle(
        {CHAVE: {"rumble": {"policy": "economia"}}}, sujo, _bancada(), {})
    assert campo == trinta, (
        f"a pintura não achou no disco o que a gravação escreveu: {campo!r}")


def test_a_recusa_sem_endereco_fala_do_teto_e_nao_do_microfone(pac, gesto, tela) -> None:
    """Duas recusas diferentes, duas frases — a do teto deixou de ser a do mic.

    Ela escolhia um teto de VIBRAÇÃO e a tela respondia falando de "a quem esta
    PONTE pertence" (`secao_controles.DICA_MIC_SEM_ENDERECO`), e num arquivo que
    este gesto nem escreve: o teto vai para o PERFIL, a ponte para o
    `maquina.json`. É a razão pela qual o próprio `_sem_endereco` existe separado
    da frase do cabo — *"uma frase só para os dois mandaria a pessoa procurar
    cabo onde o problema é endereço"*.

    MORDIDA: volte o `raise RuntimeError(_sem_endereco())` — este caso reprova.
    """
    ctx = pac.Contexto(
        state={"active_profile": "Bancada"}, mesa=[],
        conectados=[{"uniq": UNIQ_FORJADO, "connected": True,
                     "transport": "usb", "index": 0}],
        estados={})

    class _PonteQueAceitaTudo:
        def __getattr__(self, _nome):
            return lambda *a, **k: True

    _, _, trinta = tela.opcoes_do_teto()
    with pytest.raises(RuntimeError) as erro:
        gesto(ctx, {"uniq": UNIQ_FORJADO, "valor": trinta}, _PonteQueAceitaTudo())

    frase = str(erro.value)
    assert "PONTE" not in frase and "ponte" not in frase, (
        f"a recusa do teto fala da ponte do microfone: {frase!r}")
    assert "perfil" in frase, (
        f"a recusa não diz onde o teto seria guardado: {frase!r}")


def test_o_select_do_piloto_nao_conta_pintura_sobre_valor_que_nao_e_opcao() -> None:
    """Escrever `—` num `<select>` deixa `selectedIndex = -1` e mente para sempre.

    MEDIDO em 01/09/2026, com o piloto oculto e um controle só na mesa: o lugar
    VAZIO (P2) recebe o travessão de `dict.fromkeys(chaves, "—")`, o `<select>`
    do teto renderiza EM BRANCO e, como `el.value` nunca volta igual a `"—"`, o
    contador soma +1 por tique — 4/tique em regime permanente contra 3 com o
    endereço arrancado da página. **O contador é O instrumento com que esta casa
    prova que um endereço existe**; um contador que mente é pior que um campo
    parado.

    É o mesmo defeito que `gui.aba_conexoes.teto_que_vale` já evitava do lado
    Python (devolvendo `None` para a política que o campo não sabe mostrar) e que
    voltou pela porta do lugar vazio. A cura mora no piloto porque nenhuma aba
    deve ter de lembrar-se dela.

    MORDIDA: tire a guarda `el.tagName === 'SELECT'` do ramo `valor` do
    `BOOTSTRAP` — este caso reprova.
    """
    from hefesto_dualsense4unix.interface import hefesto_vivo

    ramo = hefesto_vivo.BOOTSTRAP.split("if(alvo === 'valor')", 1)
    assert len(ramo) == 2, "o ramo `valor` do BOOTSTRAP mudou de forma"
    corpo = ramo[1].split("if(alvo === 'html')", 1)[0]
    assert "SELECT" in corpo and "el.options" in corpo, (
        "o ramo `valor` voltou a escrever em qualquer elemento sem conferir se um "
        "`<select>` oferece a opção — o contador de pinturas passa a mentir a cada "
        f"tique no lugar vazio da mesa. Corpo: {corpo!r}")


def test_a_camada_de_tela_desta_aba_continua_sem_gtk() -> None:
    """A linha 1 de `gui/aba_conexoes.py` promete *"sem GTK"*, e o teto o quebrou.

    O `fala_do_teto` da leva importava `SEM_TETO` de
    `app/actions/config/secao_orcamento.py`, que puxa `gi` + `gi.repository.Gtk`
    no import (pelo `app.widgets.segmented_selector`). O import era tardio, mas
    isso muda QUANDO falha, não SE falha: quem chamasse `opcoes_do_teto()` ou
    `html_das_linhas()` — que é o que a janela renderiza — trazia a janela GTK
    inteira para dentro do processo. E `app/actions/` é justamente a camada que
    a regra desta casa manda NÃO reusar. A cura foi `SEM_TETO` mudar de casa
    para `core.rumble`, ao lado do `teto_do_orcamento` cujo `None` ela traduz.

    EM SUBPROCESSO, e não neste: `pacotes/__init__` já traz GTK para o processo
    da suíte por outro caminho (medido), então um `sys.modules` medido aqui não
    responderia pela promessa DESTE módulo.

    MORDIDA: volte o `from ...secao_orcamento import SEM_TETO` em `fala_do_teto`
    — este caso reprova.
    """
    import subprocess

    codigo = (
        "import sys\n"
        "from hefesto_dualsense4unix.gui import aba_conexoes as t\n"
        "t.opcoes_do_teto()\n"
        "t.fala_do_teto('economia')\n"
        "t.teto_que_vale(t.Vibracao(a_viva='balanceado'))\n"
        "c = t.Controle(uniq='aa:bb:cc:00:00:01', jogador=1, via='usb', bateria=50,\n"
        "               plastico='#fff', cor_nome='Branco', fabricante='Sony',\n"
        "               mic_ligado=False)\n"
        "t.html_das_linhas([c], 'aa:bb:cc:**:**:01')\n"
        "print('gi.repository.Gtk' in sys.modules)\n"
    )
    saida = subprocess.run(
        [sys.executable, "-c", codigo], check=True, capture_output=True, text=True,
        env={"PYTHONPATH": str(RAIZ / "src"), "PATH": "/usr/bin:/bin",
             "HOME": "/nao-existe"},
    )
    assert saida.stdout.strip() == "False", (
        "o caminho do teto da vibração puxou `gi.repository.Gtk` para o processo, "
        "e a linha 1 deste módulo promete `sem GTK` — com três consequências "
        f"medidas escritas logo abaixo dela. Saída: {saida.stdout!r}")


def test_as_opcoes_que_ela_clica_sao_as_que_a_borda_aceita(tela) -> None:
    """Os `<option>` da PÁGINA contra a lista do produto — as duas pontas do clique.

    O RÓTULO QUE CHEGA AO DEDO DELA é o `<option>` do HTML publicado, que é
    DIGITADO e só muda quando alguém regera. `test_o_rotulo_nao_e_digitado`
    declara que "a frase é REPRODUZIDA do produto" e mede só o lado Python;
    `check_o_desenho_aprovado` compara mockup↔publicado, que são as duas cópias
    congeladas e por isso sempre iguais. Portão nenhum comparava gerador↔página.

    O QUE ISSO DEIXAVA PASSAR, medido em 01/09/2026: com o degrau `economia`
    mudado para 0,25, `opcoes_do_teto()` passa a oferecer "25% da força", a
    página continua oferecendo "30% da força", `politica_do_rotulo` RECUSA a
    própria opção que a tela mostra — e o campo morre em silêncio, porque a
    recusa só existe no `stderr` de um terminal que ela não olha.

    MORDIDA: troque um `<option>` da página publicada por outro texto — este
    caso reprova nomeando a página, que é o que faz alguém regerar em vez de
    consertar o teste.
    """
    doc = _pagina_publicada()
    blocos = re.findall(
        r"<select[^>]*data-gesto=\"teto-da-vibracao\"[^>]*>(.*?)</select>", doc, re.S)
    assert blocos, "a página publicada não tem o `<select>` do teto da vibração"
    do_produto = list(tela.opcoes_do_teto())
    for bloco in blocos:
        na_pagina = re.findall(r"<option[^>]*>([^<]+)</option>", bloco)
        assert na_pagina == do_produto, (
            f"a página publicada oferece {na_pagina} e o produto aceita "
            f"{do_produto}. REGERE a aba — "
            f"`python3 src/hefesto_dualsense4unix/interface/aba08.py` e "
            f"`scripts/check_o_desenho_aprovado.py --publicar 08` — em vez de "
            f"acertar este teste: o que ela clica é o `<option>`, e a borda "
            f"recusa em SILÊNCIO o rótulo que não conhece.")
        # E A BORDA ACEITA CADA UM, que é a outra metade: uma lista igual com uma
        # opção sem tradução seria um campo que oferece o que não sabe gravar.
        for rotulo in na_pagina:
            try:
                tela.politica_do_rotulo(rotulo)
            except ValueError as recusa:
                assert rotulo == do_produto[1], (
                    f"a página oferece {rotulo!r} e a borda o recusa: {recusa}")
