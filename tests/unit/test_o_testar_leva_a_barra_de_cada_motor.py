#!/usr/bin/env python3
"""VIBRA-MULT-01 — o "Testar" da aba Vibração leva a barra de CADA motor.

A QUEIXA É DELA, 08/09/2026
----------------------------
    *"na guia vibração os slicers não estão se multiplicando: motor esquerdo x
    força de vibração (ou personalizado), motor direito x força de vibração ou
    personalizado, pra cada controle — e funcionar dentro do jogo respeitando
    isso."*

A CONTA existia e estava certa desde 04/09 (`gamepad._mults_por_motor`, 55
réguas em `test_cada_motor_tem_o_seu_multiplicador.py`). A TELA passou a dizer
o produto em 09/09. **O que faltava era o botão que a mão dela aperta.**

O QUE FOI MEDIDO, e são dois defeitos empilhados
-------------------------------------------------
1. `a05_vibracao._par_das_barras` lia `last_weak`/`last_strong` de dentro do
   bloco `per_vpad` do `state_full`. **Aquele bloco não tem essas chaves** —
   elas moram no TOPO do `rumble_ff` (`daemon/ipc_handlers.py:3529`). As duas
   leituras davam `0` em toda execução de produção, e o "Testar" mandava o par
   fixo `(160, 220)` **fizesse ela o que fizesse com as barras**. Medido com a
   barra esquerda em ZERO: `rumble.set(160, 220)`.
2. O caminho do rumble FIXADO (`rumble.set` + o reassert de 5 Hz) aplica **um
   fator só, o degrau**, igual nos dois motores; a barra por motor só é
   aplicada em `gamepad.apply_game_rumble`, que é o FF do JOGO. Logo, mesmo com
   a leitura curada, o daemon não reduziria motor nenhum.

A CURA DESTA SPRINT é a metade que cabe na posse dela: a aba manda o par já
reduzido pela barra, e o degrau continua sendo dos três andares do daemon que
já o aplicavam. A outra metade — `_handle_rumble_set` e `reassert_rumble`
passando por `_mults_por_motor`, que cobriria também o `hef test rumble` e a
janela GTK — está relatada na entrega.

A MORDIDA DE CADA CASO está no docstring dele. A de todos:
em `a05_vibracao._par_das_barras`, troque o `return` por `return PAR_DE_TESTE`
— a barra some, o motor que ela calou volta a tremer, e os casos 1 a 4
reprovam nomeando os dois números.

Endereços: faixa sintética da casa (`aa:bb:cc:00:00:0N`). Há dois portões de
anonimato nesta árvore e eles não perdoam.
"""

from __future__ import annotations

from typing import Any

import pytest

# O HARNESS VEM DA RÉGUA IRMÃ, e não é preguiça: a `PonteDeMentira` de lá é um
# dublê que SABE RECUSAR, e uma segunda cópia dele aqui divergiria da ponte real
# no primeiro dia em que uma `*_checked` mudasse de forma. O import também traz
# o `sys.path` do `interface/`, que aquele arquivo monta.
from tests.unit.test_a05_a_vibracao_aplica_e_fala import PonteDeMentira

#: Os dois controles da bancada, com a máscara da casa.
P1 = "aa:bb:cc:00:00:01"
P2 = "aa:bb:cc:00:00:02"
CHAVE_P1 = "aabbcc000001"
CHAVE_P2 = "aabbcc000002"

#: O `rumble_ff` COMO O DAEMON O PUBLICA — o `per_vpad` cheio de tudo o que ele
#: tem, e sem `last_weak`/`last_strong`, que moram no topo. Ele está aqui de
#: propósito: é a prova de que o par do teste **não depende** do que o jogo
#: pediu, e é o que impede a leitura morta de voltar por outra porta.
FF_DO_DAEMON: dict[str, Any] = {
    "plays": 12,
    "last_weak": 90,
    "last_strong": 40,
    "per_vpad": [
        {"player": 1, "rumble_no_fisico": [90, 40], "ff_play_count": 12},
        {"player": 2, "rumble_no_fisico": [30, 10], "ff_play_count": 4},
    ],
}


@pytest.fixture
def pac():
    import pacotes

    return pacotes


@pytest.fixture
def a05():
    from pacotes import a05_vibracao

    return a05_vibracao


def _ctx(pac, barras: dict[str, dict[str, int]], *, ff: dict[str, Any] | None = None):
    """A mesa com os DOIS controles e as barras de cada um, do `state_full`.

    `barras` é `{chave_no_perfil: {"forte_pct": …, "fraco_pct": …}}` — a mesma
    forma que `state_full.rumble_motores` publica, porque é dela que
    `_barras_dos_motores` lê. Peça sem opinião não entra no mapa (a disciplina
    do `set_rumble_scales`), e é por isso que a ausência é um caso de teste.
    """
    return pac.Contexto(
        state={
            "active_profile": "Bancada",
            "rumble_policy": "max",
            "rumble_motor_pct_padrao": 100,
            "rumble_motores": barras,
            "rumble_ff": FF_DO_DAEMON if ff is None else ff,
        },
        mesa=[
            {"pref": "p1", "jogador": 1, "uniq": P1, "nome": "Régua 1",
             "via": "USB", "cor": "starlight-blue"},
            {"pref": "p2", "jogador": 2, "uniq": P2, "nome": "Régua 2",
             "via": "BT", "cor": "midnight-black"},
        ],
        conectados=[
            {"uniq": P1, "connected": True, "transport": "usb",
             "index": 0, "player": 1},
            {"uniq": P2, "connected": True, "transport": "bluetooth",
             "index": 1, "player": 2},
        ],
        estados={})


def _testar(pac, a05, ctx, uniq: str, controle: str) -> tuple[int, ...]:
    """Clica "Testar" naquela coluna e devolve o par que foi ao motor."""
    a05.parar_o_teste()
    p = PonteDeMentira()
    fn = pac.gesto_da_pagina("05-vibracao.html", "testar")
    assert fn is not None, "05-vibracao.html:testar perdeu o dono"
    fn(ctx, {"uniq": uniq, "controle": controle}, p)
    pares = [a for n, a, _k in p.chamadas if n == "rumble_set_checked"]
    assert pares, f"o Testar não mandou par nenhum — as chamadas foram {p.nomes}"
    a05.parar_o_teste()
    return tuple(pares[0])


# ---------------------------------------------------------------------------
# 1. A BARRA REDUZ O PAR — o caso dela, por extenso
# ---------------------------------------------------------------------------
def test_a_barra_esquerda_pela_metade_corta_o_strong_pela_metade(pac, a05) -> None:
    """Motor esquerdo em 50 % -> o `strong` sai pela metade, e o `weak` inteiro.

    É A FRASE DELA na linguagem do fio: *"se so a do motor fraco tiver 100 e a
    outrqa 50% então será 150 em um e 75% no outro"*.  <!-- noqa-acento: citação dela -->
    O degrau (os 150 %) é do daemon; o que esta régua cobra é o SEGUNDO fator,
    que é o que nunca saía da tela.

    MORDIDA: em `_par_das_barras`, devolva `PAR_DE_TESTE` sem reduzir — o
    `strong` volta a 220 e este `assert` nomeia os dois números.
    """
    ctx = _ctx(pac, {CHAVE_P1: {"forte_pct": 50, "fraco_pct": 100}})

    par = _testar(pac, a05, ctx, P1, "p1")

    assert par == (160, 110), (
        f"o par que foi ao motor é {par}; com a barra esquerda em 50 % o "
        f"`strong` (o motor da ESQUERDA) tem de sair 110 e o `weak` 160")


def test_o_motor_posto_em_zero_nao_treme(pac, a05) -> None:
    """Barra em 0 -> aquele motor fica PARADO no "Testar".

    O `0` é escolha válida (*"este motor não treme neste perfil"*, o mesmo
    contrato que `a05_vibracao.motor` declara), e era o caso mais gritante do
    defeito: o motor que ela mandou calar tremia a 220 igual ao outro. Não é
    número errado numa tela — é o aparelho fazendo o contrário do pedido.

    MORDIDA: a mesma do caso acima — sem a redução o `strong` volta a 220, e um
    motor "desligado" treme mais que o ligado.
    """
    ctx = _ctx(pac, {CHAVE_P1: {"forte_pct": 0, "fraco_pct": 100}})

    assert _testar(pac, a05, ctx, P1, "p1") == (160, 0), (
        "o motor posto em ZERO continuou recebendo força no Testar")


def test_a_barra_direita_mexe_no_weak_e_nao_no_strong(pac, a05) -> None:
    """A INVERSÃO, que é a armadilha deste assunto — e ela tem de estar certa.

    `weak` é o motor da DIREITA (`d`) e `strong` o da ESQUERDA (`e`)
    (`core/backend_pydualsense.py:3840`: `setLeftMotor(eff_strong)`). Uma troca
    aqui daria uma régua verde sobre um produto que reduz o punho errado — e a
    mão dela é o único instrumento que veria.

    MORDIDA: troque `barras["d"]` por `barras["e"]` nas duas linhas do `return`
    de `_par_das_barras`: este caso sai `(160, 110)` onde tem de sair
    `(80, 220)`.
    """
    ctx = _ctx(pac, {CHAVE_P1: {"forte_pct": 100, "fraco_pct": 50}})

    assert _testar(pac, a05, ctx, P1, "p1") == (80, 220), (
        "a barra da DIREITA mexeu no motor errado — `weak` é o da direita")


# ---------------------------------------------------------------------------
# 2. O QUE NÃO MUDA — e é metade da prova
# ---------------------------------------------------------------------------
def test_sem_barra_escrita_o_par_e_o_de_sempre(pac, a05) -> None:
    """Peça sem opinião -> `(160, 220)`, byte-idêntico ao de antes desta cura.

    A peça que ninguém ajustou **não entra** no `rumble_motores`, e o padrão
    chega ao lado (`rumble_motor_pct_padrao`). Uma redução nova no caminho de
    quem não pediu nada seria regressão silenciosa em toda mesa do mundo — é o
    mesmo contrato que `TestOQueNaoMuda` cobra do lado do daemon.
    """
    assert _testar(pac, a05, _ctx(pac, {}), P1, "p1") == (160, 220)


def test_as_duas_em_cem_entregam_o_par_de_teste_inteiro(pac, a05) -> None:
    """Barras em 100 -> nada é reduzido. O 100 é o neutro, não um degrau."""
    ctx = _ctx(pac, {CHAVE_P1: {"forte_pct": 100, "fraco_pct": 100}})

    assert _testar(pac, a05, ctx, P1, "p1") == (160, 220)


def test_o_par_do_teste_nao_vem_do_que_o_jogo_pediu(pac, a05) -> None:
    """A régua contra a VOLTA do defeito, e ela mede COMPORTAMENTO.

    O `rumble_ff` desta mesa está cheio — `last_weak=90`, `last_strong=40` no
    topo e `rumble_no_fisico` em cada vpad. Se alguém religar a leitura do
    pedido do jogo aqui (foi de lá que veio a chave morta), o par deixa de
    seguir a barra e passa a seguir o jogo, e este caso reprova.

    Ler o pedido do jogo seria pior que morto: `rumble_no_fisico` é o par **já
    multiplicado**, e realimentá-lo no `rumble.set` aplicaria o degrau duas
    vezes.
    """
    ctx = _ctx(pac, {CHAVE_P1: {"forte_pct": 50, "fraco_pct": 100}})

    par = _testar(pac, a05, ctx, P1, "p1")

    assert par == (160, 110), (
        f"o par saiu {par} — com `last_weak=90`/`last_strong=40` no estado, um "
        f"par que siga o JOGO em vez das barras aparece aqui")


# ---------------------------------------------------------------------------
# 3. POR CONTROLE — "cada um com o seu, e trocar um não mexe no outro"
# ---------------------------------------------------------------------------
def test_cada_coluna_leva_a_barra_da_peca_dela(pac, a05) -> None:
    """P1 inteiro e P2 pela metade, na MESMA mesa e no mesmo tique.

    É a terceira exigência da frase dela — *"pra cada controle"* — e o critério
    de pronto da sprint: `P1 em 100 % e P2 em 50 % ao mesmo tempo, e trocar um
    não mexe no outro`.

    MORDIDA: em `_barras_dos_motores`, ignore o `uniq` e devolva sempre o mapa
    da primeira peça — os dois pares saem iguais e este caso nomeia qual coluna
    recebeu a barra da outra.
    """
    ctx = _ctx(pac, {
        CHAVE_P1: {"forte_pct": 100, "fraco_pct": 100},
        CHAVE_P2: {"forte_pct": 50, "fraco_pct": 100},
    })

    assert _testar(pac, a05, ctx, P1, "p1") == (160, 220), "o P1 levou a barra do P2"
    assert _testar(pac, a05, ctx, P2, "p2") == (160, 110), "o P2 não levou a sua barra"


# ---------------------------------------------------------------------------
# 4. O "AO VIVO" — o arraste que ainda não voltou do daemon
# ---------------------------------------------------------------------------
def test_o_arraste_reenvia_o_valor_que_acabou_de_gravar(pac, a05, monkeypatch) -> None:
    """Arrastar a barra com o teste ligado manda o valor NOVO, não o do tique.

    O `ctx` de um gesto é o retrato ANTERIOR ao `rumble.motores.set` que acabou
    de responder: `state.rumble_motores` ainda traz a barra velha. Sem o
    `acabou_de_gravar`, o reenvio faria a mão dela sentir o valor de antes do
    arraste — o "ao vivo" atrasado em um tique, que é a forma mais convincente
    de um ajuste parecer que não funciona.

    MORDIDA: tire o `acabou_de_gravar=(lado, pontos)` da chamada de
    `_refrescar_o_teste` no gesto `motor` — o reenvio volta a mandar `220`, o
    valor do estado, e este caso reprova nomeando os dois.
    """
    from pacotes import a05_vibracao as a05_mod

    # O ESTADO AINDA DIZ 100, que é o retrato de antes do arraste.
    ctx = _ctx(pac, {CHAVE_P1: {"forte_pct": 100, "fraco_pct": 100}})
    p = PonteDeMentira()
    # A ponte responde ao `rumble.motores.set` como a real: `(ok, corpo)`.
    monkeypatch.setattr(
        p, "rumble_motores_set",
        lambda **kw: (p.chamadas.append(("rumble_motores_set", (), kw)),
                      (True, {"status": "ok"}))[1],
        raising=False)

    a05_mod.parar_o_teste()
    _testar(pac, a05, ctx, P1, "p1")          # (não deixa o teste ligado)
    a05_mod._EM_TESTE[0] = P1                  # o "Testar" está ligado NESTE
    fn = pac.gesto_da_pagina("05-vibracao.html", "motor")
    assert fn is not None, "05-vibracao.html:motor perdeu o dono"
    fn(ctx, {"uniq": P1, "lado": "e", "valor": "25"}, p)
    a05_mod.parar_o_teste()

    reenvios = [a for n, a, _k in p.chamadas if n == "rumble_set_checked"]
    assert reenvios, f"o arraste não reenviou o par — as chamadas foram {p.nomes}"
    assert tuple(reenvios[-1]) == (160, 55), (
        f"o reenvio levou {tuple(reenvios[-1])}; a barra que ela ACABOU de "
        f"gravar é 25 %, e 220 x 25 % é 55 — o estado ainda diz 100")


def test_o_arraste_no_p2_nao_sacode_o_p1_em_teste(pac, a05, monkeypatch) -> None:
    """Teste ligado no P1, barra arrastada no P2 -> o P1 fica quieto.

    Sem esta guarda o "ao vivo" viraria vazamento: ela ajusta a coluna do P2 e
    quem treme na mão dela é o P1, com um número que não é de nenhum dos dois.
    """
    from pacotes import a05_vibracao as a05_mod

    ctx = _ctx(pac, {CHAVE_P1: {"forte_pct": 100, "fraco_pct": 100},
                     CHAVE_P2: {"forte_pct": 100, "fraco_pct": 100}})
    p = PonteDeMentira()
    monkeypatch.setattr(
        p, "rumble_motores_set",
        lambda **kw: (p.chamadas.append(("rumble_motores_set", (), kw)),
                      (True, {"status": "ok"}))[1],
        raising=False)

    a05_mod._EM_TESTE[0] = P1
    fn = pac.gesto_da_pagina("05-vibracao.html", "motor")
    assert fn is not None
    fn(ctx, {"uniq": P2, "lado": "e", "valor": "25"}, p)
    a05_mod.parar_o_teste()

    assert "rumble_set_checked" not in p.nomes, (
        f"arrastar a barra do P2 mandou vibração ({p.nomes}) com o teste ligado "
        f"no P1")
