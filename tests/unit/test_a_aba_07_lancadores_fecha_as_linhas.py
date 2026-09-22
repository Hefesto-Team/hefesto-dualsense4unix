#!/usr/bin/env python3
"""AS QUATRO DECISÕES DA ABA LANÇADORES, cobradas uma a uma.

Elas são do PO, 04/09/2026
(`docs/process/2026-09-04-O-PO-DECIDE-as-54-e-os-sete-conflitos.md` §2,
`07-lancadores`), e a sprint que as executa é a `ONDA2-07-LANCADORES-01`:

    [01] o reparo manual sem caminho   a linha à mostra, SÓ no estado em que
                                       o cartão já diz «linha intocável» (o
                                       botão «Copiar a linha» saiu em 21/09)
    [02] a frase que manda a um botão  ela para de nomear lugar. **O texto tem
         inexistente                   UM dono para as duas telas, e ele NÃO é
                                       desta posse** — o que esta régua cobra é
                                       que a aba não escreva uma SEGUNDA frase
    [03] de onde o aviso some          as DUAS recusas calam: a lista antiga
                                       do «Não perguntar» e o «Tirar daqui»
    [04] 63 e 22 na mesma tela         CADUCOU em 21/09: a frase do atalho
                                       saiu do corpo, e o corpo de todo cartão
                                       é o mesmo contador de pontes

O QUE ELAS CURAM, e cada uma é um defeito medido:

* a tela prometia um **reparo manual** e não oferecia caminho nenhum para
  fazê-lo — **não existia UM botão de copiar em toda a interface nova**;
* a frase do aviso manda copiar as opções *"na aba Sistema"*, e a aba Sistema
  da interface nova tem doze botões e **nenhum copia coisa alguma**;
* o *"Não usar neste jogo"* — a lista que o produto INTEIRO respeita no
  reparo — **não calava tela nenhuma**: ela tirava o jogo de propósito e o
  aviso voltava toda vez que ele abrisse;
* o cartão dizia `22 jogos instalados` e, uma linha abaixo, *"o atalho está no
  lugar em 63 jogos da sua biblioteca"* — as duas verdadeiras, e nada na tela
  dizendo que contam conjuntos diferentes.

A MORDIDA DE CADA UMA está colada no relatório desta frente
(`docs/process/agentes/2026-09-04/ONDA2-07.md`), e o resumo é este:

    apague o `if lida.intocaveis and lida.linha:` de `cartao_da_steam`
        → 1 reprova (o bloco some do corpo)
    torne o mesmo `if` incondicional
        → 1 reprova (o bloco nasce no dia bom)
    apague `linha=slo.WRAPPER_LAUNCH` de `_ler_do_disco`
        → 1 reprova (a linha nunca chega ao desenho)
    tire `lida.recusados` de `calados`
        → 1 reprova (o «Tirar daqui» volta a não calar o aviso)
"""

from __future__ import annotations

import pathlib
import sys
import types

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
INTERFACE = RAIZ / "src" / "hefesto_dualsense4unix" / "interface"
sys.path.insert(0, str(INTERFACE))

PAGINA = "07-lancadores.html"


@pytest.fixture(scope="module")
def desenho():
    from hefesto_dualsense4unix.interface import desenho_dos_lancadores as dl

    return dl


@pytest.fixture(scope="module")
def a07():
    from hefesto_dualsense4unix.interface.pacotes import a07_lancadores

    return a07_lancadores


@pytest.fixture(autouse=True)
def _a_maquina_nao_entra_na_regua(monkeypatch):
    """Nenhum teste daqui depende de haver jogo da Steam aberto na máquina.

    O VAZAMENTO, MEDIDO EM 13/09/2026: um gesto que devolvia `VIGIA.agora()`
    disparava a thread `hefesto-lancadores`, que rodava o `_ler_do_disco` de
    verdade — e o censo pergunta `steam_game_running()` ao `/proc` real.
    Quatro testes reprovavam só porque a máquina estava jogando. Os botões
    daquele vazamento saíram em 21/09/2026; o dublê fica, porque o censo
    continua perguntando.

    O DUBLÊ VAI NOS DOIS LUGARES, e os dois foram medidos: a sentinela guarda a
    própria cópia de `steam_game_running` (`from .steam_launch_options import`),
    e um dublê só em `steam_launch_options` deixa a outra cópia viva. Quem
    precisa de outro valor sobrescreve no próprio teste.
    """
    from hefesto_dualsense4unix.integrations import sentinela_do_wrapper as sw
    from hefesto_dualsense4unix.integrations import steam_launch_options as slo

    for dono in (slo, sw):
        monkeypatch.setattr(dono, "steam_game_running", lambda: False)
        monkeypatch.setattr(dono, "steam_running", lambda: False)


@pytest.fixture(scope="module")
def linha_do_motor() -> str:
    """A linha de inicialização, PERGUNTADA ao dono — nunca digitada aqui.

    143 caracteres com aspas, cifrões e `%command%`: digitá-los nesta régua
    seria a quarta cópia de um literal que já tem dono, e a régua daria verde
    no dia em que o wrapper mudasse de caminho e a tela ficasse com o antigo.
    """
    from hefesto_dualsense4unix.integrations.steam_launch_options import (
        WRAPPER_LAUNCH,
    )

    return WRAPPER_LAUNCH


@pytest.fixture
def ctx():
    import pacotes

    return pacotes.Contexto(state={}, mesa=[], conectados=[], estados={})


def _fileira(desenho, lida) -> str:
    """A fileira de botões DO CARTÃO DA STEAM, como a pintura a emite.

    ELA LÊ O VALOR QUE VAI PARA A TELA (`Quadro.valores()["steam-acoes"]`), e
    não a lista de botões guardada no cartão: um botão que existisse no objeto
    e sumisse na marcação passaria por uma régua que olhasse só o objeto.
    """
    return desenho.Quadro(lancadores=desenho.cartoes(lida)).valores()["steam-acoes"]


def _corpo(desenho, lida) -> str:
    """O corpo do cartão da Steam, como a pintura o emite."""
    return desenho.Quadro(lancadores=desenho.cartoes(lida)).valores()["steam-diz"]


def _com_intocavel(desenho, linha: str, **extra):
    """Uma leitura em que HÁ jogo com a linha intocável."""
    return desenho.Leitura(
        com_wrapper=("620", "440"),
        intocaveis=(("70", "Jogo de linha editada",
                     "linha editada à mão — não vou tocar"),),
        instalados=2, linha=linha, **extra)


def _em_ordem(desenho, linha: str, **extra):
    """Uma leitura em que a biblioteca está inteira em ordem — o dia bom."""
    return desenho.Leitura(com_wrapper=("620", "440"), instalados=2,
                           linha=linha, **extra)


# --------------------------------------------------------------------------
# [01] o reparo manual sem caminho — OS DOIS, SÓ QUANDO FAZ FALTA
# --------------------------------------------------------------------------
#: O gesto do botão que SAIU em 21/09/2026 — escrito aqui como literal porque o
#: desenho não tem mais a constante, e a régua cobra que ele não volte.
COPIAR_QUE_SAIU = 'data-gesto="copiar-a-linha"'


def test_o_estado_intocavel_traz_a_linha_a_mostra(desenho, linha_do_motor):
    """Com jogo intocável, o cartão mostra a linha — e o «Copiar» não volta.

    O BOTÃO SAIU EM 21/09/2026 com os outros botões que só a Steam tinha,
    palavra dela: *"a ideia é termos os mesmos botões pra todos os lançadores.
    sempre."* A linha à mostra fica, e é a metade da decisão `07[01]` que a
    cópia calada nunca garantiu: com ela na tela, um `Ctrl+C` salva o dia.
    """
    lida = _com_intocavel(desenho, linha_do_motor)
    corpo = _corpo(desenho, lida)

    assert COPIAR_QUE_SAIU not in _fileira(desenho, lida), (
        "o «Copiar a linha» voltou ao cartão da Steam — um botão que os outros "
        "sete cartões não têm")
    assert 'class="linha-do-wrapper"' in corpo, (
        "a linha à mostra não entrou no corpo do cartão — o carimbo diz «só "
        "reparo manual» e a tela ficaria sem o que copiar")
    assert desenho._e(linha_do_motor) in corpo, (
        "o bloco à mostra não traz a linha do motor. Uma linha diferente da "
        "que o produto grava faria ela colar à mão uma opção que o Hefesto "
        "não reconhece depois.")


def test_no_dia_bom_nada_disso_ocupa_a_tela(desenho, linha_do_motor):
    """Sem jogo intocável, o bloco da linha não nasce — a outra metade da decisão.

    *"No dia bom o cartão fica exatamente como está"*: nos outros estados o
    vigia (`hefesto-steam-input-guard`) repõe o atalho sozinho.
    """
    assert "linha-do-wrapper" not in _corpo(desenho, _em_ordem(desenho, linha_do_motor)), (
        "o bloco da linha apareceu numa biblioteca em ordem")


def test_sem_a_linha_o_cartao_cala_em_vez_de_inventar(desenho):
    """Leitura com intocáveis e SEM linha: nenhum bloco.

    O DESENHO NÃO IMPORTA O PRODUTO — é o que deixa o gerador rodar como script
    solto —, então a linha chega pelo contrato frio. Sem ela, o bloco mostraria
    um `<code>` em branco onde a tela promete uma linha para colar.
    """
    assert "linha-do-wrapper" not in _corpo(desenho, _com_intocavel(desenho, ""))


def test_o_produto_enche_a_linha_com_a_constante_do_motor(
        a07, desenho, linha_do_motor, monkeypatch):
    """`_ler_do_disco` põe `WRAPPER_LAUNCH` na `Leitura` — LIDO, não digitado.

    SEM ESTA RÉGUA o desenho poderia estar perfeito e o botão **nunca nascer na
    máquina dela**: `lida.linha` ficaria vazia para sempre, o `if` do cartão
    nunca casaria, e nada acusaria — a forma exata do defeito que esta casa
    chama de *pintura perdida*.

    O CENSO É DUBLÊ porque o disco desta máquina não tem jogo intocável nenhum,
    e uma régua que dependesse da biblioteca dela mediria a mesa, não o código.
    """
    from hefesto_dualsense4unix.integrations import sentinela_do_wrapper as sw

    censo = types.SimpleNamespace(
        com_wrapper=["620"], reparaveis=[], intocaveis=[], recusados=[],
        erros=[], jogo_aberto=False, steam_aberta=False)
    monkeypatch.setattr(sw, "censo_do_wrapper", lambda **_: censo)
    monkeypatch.setattr(sw, "frase_do_aviso", lambda _c: "")
    lida = a07._ler_do_disco()
    assert lida.linha == linha_do_motor, (
        f"`_ler_do_disco` devolveu linha={lida.linha!r}. Ela tem de ser a "
        f"constante do motor: é a MESMA que o reparo grava no vdf e a MESMA "
        f"que o botão da janela velha copia.")


# --------------------------------------------------------------------------
# [02] a frase que manda a um botão inexistente — UMA FRASE, UM DONO
# --------------------------------------------------------------------------
def test_a_aba_nao_escreve_uma_segunda_frase_do_aviso(a07):
    """O texto do aviso sai de `home_actions`, e esta aba não o redige.

    A DECISÃO `07[02]` DO PO CADUCOU em 05/09, e quem a derrubou foi ELA: a
    `07-Q2` recusou as três opções oferecidas — só o fato, apontar o Consertar,
    duas frases — e respondeu com uma quarta, *"O produto aplica ela"*. A frase
    do dono (`home_actions.WRAPPER_MISSING_TEXT`) diz hoje o fato **mais** a
    promessa que o produto cumpre, e a ONDA5-07-03 a entregou em 06/09.

    **O QUE ESTA RÉGUA COBRA NÃO MUDOU COM ISSO**, e é por isso que ela
    sobreviveu à troca sem uma linha nova: ela não conhece a frase — ela
    PERGUNTA ao dono e compara. Escrever aqui uma segunda redação faria as duas
    janelas do mesmo produto falarem línguas diferentes, que é exatamente o que
    a opção *"duas frases, uma por tela"* fazia — e ela foi recusada.

    **O CONTRATO MUDOU EM 13/09/2026 — TELA-CALADA-02.** A palavra dela sobre
    as frases de status é *"em todas as abas da interface"*, e o cartão deixou
    de pintar a frase do dono a cada tique: escreve o rótulo de estado
    `a07.JOGO_ABERTO_SEM_O_ATALHO`. A régua passou a cobrar as duas metades do
    que sobrou da decisão acima: o dono continua decidindo SE acende, e a aba
    continua sem uma SEGUNDA REDAÇÃO da frase dele — nem inteira, nem pedaço.
    """
    from hefesto_dualsense4unix.app.actions import home_actions as ha

    state = {"gamepad_emulation": {"enabled": True, "wrapper_used": False}}
    aviso, _ = a07.aviso_do_jogo_aberto(state, None)
    assert aviso, "o aviso do jogo aberto sumiu da aba"
    dono = ha.wrapper_banner_text(state) or ""
    assert dono, "o dono deixou de acender — a régua mediria o silêncio"
    assert a07._texto(dono) not in aviso and "Reponho" not in aviso, (
        f"a frase do dono voltou ao cartão, a cada tique: {aviso!r}")
    assert a07.JOGO_ABERTO_SEM_O_ATALHO in aviso, (
        f"o cartão acendeu sem o rótulo de estado: {aviso!r}")


# --------------------------------------------------------------------------
# [03] de onde o aviso some — AS DUAS RECUSAS CALAM
# --------------------------------------------------------------------------
def _state_com_jogo(appid: str) -> dict:
    """O `state` do daemon com um jogo Steam aberto SEM o wrapper.

    As três chaves são as que o produto lê: `wrapper_used is False` é o daemon
    afirmando o fato, a `window_detect_last_class` é de onde
    `launch_wrapper_dialog.extract_steam_appid` tira o appid, e o `enabled` é a
    emulação de gamepad em pé.

    O `enabled` ENTROU EM 06/09/2026, e a falta dele era uma leitura FROUXA do
    estado, não um detalhe do dublê: sem gamepad virtual não há o que duplicar,
    e o aviso deste cartão fala justamente de duplicação. A aba passou a
    perguntar isso ao dono (`launch_wrapper_dialog.wrapper_dialog_decision`), e
    um estado de mentira sem `enabled` deixou de descrever alguém que está
    jogando — descreve alguém em Modo Nativo, onde o aviso é falso.
    """
    return {"gamepad_emulation": {"enabled": True, "wrapper_used": False},
            "window_detect_last_class": f"steam_app_{appid}"}


def test_o_tirar_daqui_cala_o_aviso_do_cartao(a07, desenho):
    """«Não usar neste jogo» silencia o aviso — a metade que faltava.

    A lista `jogos_sem_wrapper.txt` é respeitada pelo produto INTEIRO no
    reparo (`reparar_ou_adiar` passa `excluir=censo.recusados`) e **não calava
    tela nenhuma**. Ela tirava o jogo de propósito e a tela reclamava dele toda
    vez que ele abrisse.
    """
    lida = desenho.Leitura(recusados=(("70", "Jogo tirado"),))
    aviso, _ = a07.aviso_do_jogo_aberto(_state_com_jogo("70"), lida)
    assert aviso == "", (
        f"o aviso sobreviveu ao «Não usar neste jogo»: {aviso!r}. Um aviso que "
        f"sobrevive à resposta dela ensina que o botão não obedece.")


def test_o_nao_perguntar_continua_calando(a07, desenho):
    """A dispensa continua valendo — a metade que já existia não pode cair."""
    lida = desenho.Leitura(dispensados=(("70", "Jogo dispensado"),))
    aviso, _ = a07.aviso_do_jogo_aberto(_state_com_jogo("70"), lida)
    assert aviso == "", "o «Não perguntar para este jogo» parou de calar"


def test_o_jogo_que_ela_nao_recusou_continua_avisando(a07, desenho):
    """O OUTRO LADO DA RÉGUA: calar demais é pior que não calar.

    Uma régua que só provasse o silêncio ficaria verde sobre um
    `aviso_do_jogo_aberto` que devolvesse `""` sempre — e o aviso que a aba
    existe para dar morreria sem ninguém ver.
    """
    lida = desenho.Leitura(recusados=(("70", "Jogo tirado"),),
                           dispensados=(("80", "Jogo dispensado"),))
    aviso, appid = a07.aviso_do_jogo_aberto(_state_com_jogo("90"), lida)
    assert aviso and appid == "90", (
        "o aviso calou para um jogo sobre o qual ela não respondeu nada")


def test_as_duas_listas_entram_na_conta_dos_calados(a07, desenho):
    """`calados()` soma as DUAS listas — e é o nome que a outra tela vai usar.

    A coluna Atenção da aba Jogar acende o MESMO aviso pela MESMA função
    (`app/actions/jogar/painel.AVISOS_DA_TELA`) e não consulta lista nenhuma.
    Aquele arquivo é de outra posse; o que esta frente deixa pronto é a conta
    com nome, para a outra metade não a redigitar.
    """
    lida = desenho.Leitura(recusados=(("70", "a"),), dispensados=(("80", "b"),))
    assert a07.calados(lida) == {"70", "80"}
    assert a07.calados(None) == set(), (
        "sem leitura não há resposta dela — calar aqui apagaria o aviso na "
        "primeira meia volta, antes de o disco ter respondido")


# --------------------------------------------------------------------------
# PASSO 2 — "Este jogo não funciona" SAIU, e a exclusão entrou no lugar
# --------------------------------------------------------------------------
def test_o_jogo_nao_funciona_saiu_e_a_exclusao_entrou_no_lugar(a07, desenho):
    """21/09/2026, o desenho aprovado por ela (OS-LANCADORES-IGUAIS-E-A-LISTA-
    DE-EXCLUSAO-01): no lugar do «Este jogo não funciona» entrou o «Adicionar à
    lista de exclusão», nos oito cartões.

    A lista do Steam Input que o botão velho escrevia NÃO é exclusão — ela põe o
    Hefesto NA FRENTE do jogo (§11 da sprint) —, e continua alcançável pelo chip
    «Steam Input» da aba Jogar, que escreve a mesma lista jogo por jogo. Os três
    testes que provavam o gesto velho (a marca no arquivo, a recarga, a recusa
    sem jogo) saíram com ele; o chip tem os dele em
    `test_steam_input_01_o_chip_que_acende_por_jogo.py`.

    A MORDIDA: devolva o botão velho à `acoes_do_steam_input` e a primeira linha
    reprova; tire a `fileira_comum` do cartão da Steam e a segunda reprova.
    """
    lida = desenho.Leitura(com_wrapper=("620",), instalados=1)
    fileira = desenho.acoes_html(
        a07.com_o_que_o_daemon_diz(desenho.cartoes(lida), None, lida)[0])
    assert 'data-gesto="este-jogo-nao-funciona"' not in fileira
    assert f'data-gesto="{desenho.EXCLUIR}"' in fileira
    assert not hasattr(a07, "este_jogo_nao_funciona"), (
        "o gesto velho continua registrado sem botão na tela — um clique que "
        "nenhuma página oferece")


# --------------------------------------------------------------------------
# PASSO 4 — o lembrete "este jogo ainda não abre pelo atalho do Hefesto"
#
# ELE JÁ EXISTIA PELA METADE, e a medição de 06/09/2026 é esta: a aba acendia o
# aviso desde 03/09 (`aviso_do_jogo_aberto`, do `wrapper_used` do daemon) e
# calava nas duas recusas dela desde 04/09 — mas **não perguntava pelo MODO**.
# No Modo Nativo não existe gamepad virtual, logo não há o que duplicar, e a
# tela avisava assim mesmo. A janela velha nunca teve esse defeito porque a
# decisão dela é uma função PURA, e a cura foi IMPORTÁ-LA.
# --------------------------------------------------------------------------
def _mesa_com_jogo_sem_atalho(**troca):
    """O `state_full` de quem está jogando um jogo Steam SEM o atalho."""
    estado = {
        "gamepad_emulation": {"enabled": True, "wrapper_used": False},
        "window_detect_last_class": "steam_app_9990001",
    }
    estado.update(troca)
    return estado


@pytest.mark.parametrize(
    ("qual", "estado"),
    [
        # (b) SEM JOGO STEAM EM FOCO o daemon devolve `None`, e não `False` —
        # `wrapper_used` é *"o jogo em foco passou pelo atalho?"*, e sem jogo
        # não há pergunta. Um `False` com a janela do navegador em foco é um
        # estado que o daemon não produz.
        ("(b) a janela em foco não é jogo Steam",
         {"gamepad_emulation": {"enabled": True, "wrapper_used": None},
          "window_detect_last_class": "firefox"}),
        ("(c) o jogo passou pelo atalho",
         {"gamepad_emulation": {"enabled": True, "wrapper_used": True},
          "window_detect_last_class": "steam_app_9990001"}),
        ("(a) o Modo Nativo está ligado — não há vpad a duplicar",
         _mesa_com_jogo_sem_atalho(native_mode=True)),
        ("(a) a emulação de gamepad está desligada",
         {"gamepad_emulation": {"enabled": False, "wrapper_used": False},
          "window_detect_last_class": "steam_app_9990001"}),
    ],
)
def test_com_cada_condicao_falsa_o_lembrete_nao_nasce(a07, qual, estado):
    """AS QUATRO CONDIÇÕES, UMA A UMA — e com cada uma falsa a tela cala.

    A QUARTA — a dispensa — tem régua própria mais acima
    (`test_o_tirar_daqui_cala_o_aviso_do_cartao` e as irmãs), porque ela é a
    decisão `07[03]` dela e cala pelas DUAS listas, não só pela da janela velha.

    A MORDIDA: tire a consulta a `wrapper_dialog_decision` de
    `aviso_do_jogo_aberto` e os DOIS casos de modo passam a avisar — um alarme
    sobre uma duplicação que não pode acontecer.
    """
    aviso, _appid = a07.aviso_do_jogo_aberto(estado, None)
    assert aviso == "", f"o lembrete nasceu com {qual}"


def test_com_as_quatro_verdadeiras_o_lembrete_nasce(a07, desenho):
    """A outra metade: sem ela a régua acima passaria com o aviso morto.

    Uma régua que só cobra AUSÊNCIA fica verde sobre um aviso que nunca nasce —
    é o defeito que esta casa nomeou no `--prova-gesto` do microfone.

    O «NÃO PERGUNTAR» SAIU EM 21/09/2026 com os outros botões que só a Steam
    tinha. O aviso é um rótulo de estado, e quem o cala continua sendo a
    resposta dela: o «Não usar neste jogo» da lista e a lista de exclusão, que
    escreve no mesmo `jogos_sem_wrapper.txt`.
    """
    lida = desenho.Leitura(com_wrapper=("620",), instalados=1)
    aviso, appid = a07.aviso_do_jogo_aberto(_mesa_com_jogo_sem_atalho(), lida)
    assert aviso and appid == "9990001"

    cartoes = a07.com_o_que_o_daemon_diz(
        desenho.cartoes(lida), _mesa_com_jogo_sem_atalho(), lida)
    assert cartoes[0].diz.startswith(aviso), (
        "o aviso nasceu e não chegou ao corpo do cartão da Steam")
    assert 'data-gesto="nao-perguntar"' not in desenho.acoes_html(cartoes[0]), (
        "o «Não perguntar» voltou ao cartão — um botão que os outros sete não têm")
