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
UNIQ_FORJADO = "02:11:22:00:00:33"


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
        {CHAVE: {"rumble": {"policy": "economia"}}}, UNIQ, None, sem_dono)
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

    sem = a08._teto_do_controle({}, UNIQ, None, sem_dono)
    assert sem[0] == segue, f"sem override o campo mostrou {sem[0]!r}"
    assert "segue o global" in sem[1], f"o `?` não diz que segue: {sem[1]!r}"
    assert sem_dono == {}, f"declarou sem_dono sem ter motivo: {sem_dono}"

    # A CHAVE É A NORMALIZADA. Procurar por `aa:bb:…` não acharia nada, e o
    # campo mostraria "Segue o global" para sempre sobre um disco que discorda.
    assert a08._teto_do_controle(
        {CHAVE: {"rumble": {"policy": "economia"}}}, UNIQ.upper(), None, {})[0] == trinta


def test_a_politica_que_a_tela_nao_oferece_e_declarada(a08, tela) -> None:
    """`max` no disco: o campo NÃO escolhe nenhuma das três, e a razão fica escrita.

    MORDIDA: faça `rotulo_da_politica` cair em `fala_do_teto(policy)` — `max`
    passa a ser traduzido como "Sem teto", que É opção do campo, e este caso
    reprova. Foi exatamente esse o defeito no primeiro rascunho desta leva.
    """
    sem_dono: dict[str, str] = {}
    campo, frase = a08._teto_do_controle(
        {CHAVE: {"rumble": {"policy": "max"}}}, UNIQ, None, sem_dono)

    assert campo is None, (
        f"o campo escolheu {campo!r} para uma política que ele não sabe mostrar "
        f"— isso é a tela afirmando um estado que o disco contradiz.")
    assert "max" in frase, f"o `?` não diz o que há no disco: {frase!r}"
    assert sem_dono, "a política não declarada não entrou em `sem_dono`"
    assert "max" in next(iter(sem_dono.values()))

    # E `balanceado` CAI NO MESMO LUGAR — é o par que `fala_do_teto` traduziria
    # como "Sem teto", a única opção sem tradução.
    assert a08._teto_do_controle(
        {CHAVE: {"rumble": {"policy": "balanceado"}}}, UNIQ, None, {})[0] is None


def test_o_pacote_publica_os_dois_enderecos(pac, a08, tela, monkeypatch) -> None:
    """O `pacote()` inteiro entrega o campo E o `?` de cada controle da mesa.

    MORDIDA: tire a linha `"teto-explica": teto_frase` do `pacote()` — este caso
    reprova, e sem ele a caixa diria "30% da força" com a dica ao lado dizendo
    "este controle segue o global": uma contradição NOVA, nossa.
    """
    monkeypatch.setattr(
        a08.perfil, "ativo",
        lambda _nome: {"controllers": {CHAVE: {"rumble": {"policy": "economia"}}}})
    monkeypatch.setattr(a08, "_orcamento_da_mesa", lambda: None)

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
def test_o_desenho_dela_nao_mudou() -> None:
    """Os dois endereços novos são INVISÍVEIS para o portão do desenho.

    `scripts/check_o_desenho_aprovado.py` compara `o_que_se_ve()`, que APAGA
    `data-campo` e `data-hef-alvo` antes do sha256. Este caso confere que o
    mockup e o publicado têm a MESMA aparência — que é a prova de que a feature
    entrou sem tocar no que ela aprovou.

    MORDIDA: mude uma palavra visível de um `<option>` no gerador e regere — os
    dois sha divergem e este caso reprova.
    """
    import importlib.util

    import onde

    alvo = RAIZ / "scripts/check_o_desenho_aprovado.py"
    spec = importlib.util.spec_from_file_location("check_desenho_da_regua", alvo)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules["check_desenho_da_regua"] = mod
    spec.loader.exec_module(mod)

    assert mod.o_que_se_ve(onde.BANCADA / "08-conexoes.html") == mod.o_que_se_ve(
        onde.PUBLICADO / "08-conexoes.html"), (
        "o que o produto RENDERIZA divergiu do desenho que ela aprovou — e a "
        "divergência não é de atributo, porque `o_que_se_ve` já os apaga.")


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
