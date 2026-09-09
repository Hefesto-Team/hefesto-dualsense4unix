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

E A CURA É PROVISÓRIA POR DESENHO, o que cria um risco com data marcada: no dia
em que o daemon passar a multiplicar os dois fatores, a barra é contada DUAS
vezes e o que ela sente vira `base x barra² x degrau`. **A §3 deste arquivo é a
guarda desse dia** — três réguas que reprovam nomeando a dobra e dizendo o que
tirar da aba, para que a descoberta não seja pela mão dela.

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


# ---------------------------------------------------------------------------
# 3. A GUARDA DA CURA PROVISÓRIA — o dia em que o daemon curar
# ---------------------------------------------------------------------------
#
# A CURA DESTA SPRINT É PARTIDA EM DOIS POR DESENHO, e o risco tem nome: a ABA
# pré-multiplica o par pela barra de cada motor (`_par_das_barras`), e o DAEMON
# aplica só o degrau (`apply_rumble_policy` no `rumble.set`, `_effective_mult`
# no reassert de 5 Hz). O produto na mão dela é `base x barra x degrau`, com
# cada fator aplicado UMA vez, por quem já o aplicava.
#
# A CURA DEFINITIVA — as duas portas do rumble FIXADO passando por
# `gamepad._mults_por_motor`, que é o que cobre o `hef test rumble` e a janela
# GTK — **dobra a conta**: a barra entraria de novo, e o que ela sentiria seria
# `base x barra² x degrau`. Com a barra em 50 % o motor cairia para 25 %, e o
# instrumento que veria isso primeiro seria a MÃO DELA.
#
# ESTAS TRÊS RÉGUAS REPROVAM NAQUELE DIA, e é o ponto delas: elas não medem uma
# feature — medem a REPARTIÇÃO. Quem curar o daemon vê o vermelho, lê o recado,
# e tira o `_reduzido_pela_barra` da aba no MESMO commit. Sem elas, a descoberta
# seria por reclamação.
#
# Elas não impedem a cura definitiva. Uma régua que impedisse trabalho seria
# outra coisa: o que elas exigem é que as duas metades andem JUNTAS.

from tests.unit.test_cada_motor_tem_o_seu_multiplicador import (
    BRANCO,
    _Backend,
    _daemon,
    _degrau,
    _grava,
    perfis,  # noqa: F401 — fixture, e é a fixture que isola o disco de perfis
)


def test_o_rumble_fixado_aplica_um_fator_so_nos_dois_motores(perfis) -> None:  # noqa: F811
    """`rumble.set` com barra ASSIMÉTRICA no perfil -> os dois motores, o MESMO fator.

    É a porta por onde o par do "Testar" desta aba entra no daemon
    (`ipc_handlers._handle_rumble_set` -> `apply_rumble_policy`). Hoje ela
    aplica o degrau e mais nada, e é POR ISSO que a aba pode pré-multiplicar
    pela barra sem dobrar a conta.

    MORDIDA (é a cura definitiva, feita de propósito): em
    `daemon/ipc_rumble_policy.apply_rumble_policy`, troque o `mult` único pelos
    dois fatores de `gamepad._mults_por_motor` — o `strong` sai 75 onde este
    caso exige 150, e a régua nomeia a dobra.
    """
    from hefesto_dualsense4unix.daemon.ipc_rumble_policy import apply_rumble_policy

    _grava("Bancada", motor_forte_pct=50, motor_fraco_pct=100)
    d = _daemon(policy="max", perfil_ativo="Bancada")

    saiu = apply_rumble_policy(d, 100, 100)

    assert saiu == (150, 150), (
        f"`apply_rumble_policy` devolveu {saiu} para (100, 100) com a barra "
        f"forte em 50 % e o degrau em {_degrau('max')}. O caminho do rumble "
        f"FIXADO passou a aplicar a BARRA além do degrau — e a aba Vibração já "
        f"a aplica antes de mandar (`a05_vibracao._par_das_barras`). A conta "
        f"DOBROU: o que ela sente virou `base x barra² x degrau`. A cura é "
        f"tirar o `_reduzido_pela_barra` da aba NO MESMO COMMIT, e o par do "
        f"'Testar' volta a ser o `PAR_DE_TESTE` seco.")


def test_o_reassert_de_5hz_aplica_um_fator_so_nos_dois_motores(perfis) -> None:  # noqa: F811
    """A segunda porta do rumble FIXADO — o laço que re-afirma o par a cada 200 ms.

    Ela é o outro caminho que o par da aba percorre, e sozinha bastaria para
    dobrar a conta: o "Testar" desta aba fica LIGADO (`_EM_TESTE`), então o
    reassert reescreve aquele par cinco vezes por segundo enquanto a mão dela
    está no plástico.

    MORDIDA: em `daemon/subsystems/rumble.reassert_rumble`, troque
    `weak_raw * mult` / `strong_raw * mult` pelos dois fatores de
    `_mults_por_motor` — o par escrito no controle sai `(150, 75)`.
    """
    from hefesto_dualsense4unix.daemon.subsystems.rumble import reassert_rumble

    _grava("Bancada", motor_forte_pct=50, motor_fraco_pct=100)
    backend = _Backend()
    d = _daemon(policy="max", perfil_ativo="Bancada", controller=backend)
    d.config.rumble_active = (100, 100)
    d.config.rumble_active_uniq = BRANCO

    reassert_rumble(d, 0.0)

    assert backend.rumbles == [(BRANCO, 150, 150)], (
        f"o reassert escreveu {backend.rumbles} — esperado "
        f"[({BRANCO!r}, 150, 150)]. Se o `strong` saiu 75, o laço de 5 Hz "
        f"passou a aplicar a barra que a aba Vibração já aplicou: a conta "
        f"dobrou, e o motor que ela pôs em 50 % está em 25 %.")


def test_a_conta_inteira_da_barra_vale_uma_vez_so(pac, a05, perfis) -> None:  # noqa: F811
    """A CONTA DE PONTA A PONTA: o clique dela, a aba, o daemon, o número final.

    É a régua que diz a repartição por extenso, com um número que ninguém
    precisa derivar:

        base 220 · barra forte 50 % · degrau máximo 1,5  ->  **165**

    `165` é `base x barra x degrau`. `82` seria `base x barra² x degrau` — a
    barra contada duas vezes, que é exatamente o que a cura definitiva do
    daemon produz se ninguém tirar a metade da aba. **O número da dobra foi
    MEDIDO, não derivado:** a mordida deste caso saiu `(240, 82)`, e não `83`,
    porque `round(82.5)` em Python arredonda para o PAR. Uma mensagem que
    nomeia um número que o leitor não vai ver é uma mentira pequena.

    A MESMA PEÇA DOS DOIS LADOS: `CHAVE_P1` é `aabbcc000001`, que é o `BRANCO`
    com que o perfil no disco foi gravado. A barra é uma só, e é a que os dois
    lados leem.

    MORDIDA: qualquer uma das duas metades sozinha. Arranque a redução da aba
    (`_par_das_barras` devolvendo `PAR_DE_TESTE`) e o final vira `330 -> 255`;
    acrescente a barra ao daemon e ele vira `83`.
    """
    from hefesto_dualsense4unix.daemon.ipc_rumble_policy import apply_rumble_policy

    assert CHAVE_P1 == BRANCO, (
        "a peça da aba e a do perfil no disco deixaram de ser a mesma — esta "
        "régua estaria compondo a barra de um controle com o degrau de outro")

    # 1. A METADE DA ABA: o clique dela sai com a barra aplicada.
    _grava("Bancada", motor_forte_pct=50, motor_fraco_pct=100)
    ctx = _ctx(pac, {CHAVE_P1: {"forte_pct": 50, "fraco_pct": 100}})
    da_aba = _testar(pac, a05, ctx, P1, "p1")
    assert da_aba == (160, 110), f"a aba mandou {da_aba}, e devia mandar (160, 110)"

    # 2. A METADE DO DAEMON: o degrau, e SÓ o degrau, sobre o par que chegou.
    d = _daemon(policy="max", perfil_ativo="Bancada")
    no_motor = apply_rumble_policy(d, *da_aba)

    assert no_motor == (240, 165), (
        f"o par que chega ao motor é {no_motor}. O contrato é "
        f"`base x barra x degrau` = 220 x 50 % x 1,5 = 165 no motor esquerdo. "
        f"Se saiu 82, a barra foi contada DUAS vezes — uma na aba e outra no "
        f"daemon — e o que ela sente é `barra²`. Ver o comentário desta seção: "
        f"as duas metades têm de andar juntas.")
