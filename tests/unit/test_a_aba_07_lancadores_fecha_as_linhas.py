#!/usr/bin/env python3
"""AS QUATRO DECISÕES DA ABA LANÇADORES, cobradas uma a uma.

Elas são do PO, 04/09/2026
(`docs/process/2026-09-04-O-PO-DECIDE-as-54-e-os-sete-conflitos.md` §2,
`07-lancadores`), e a sprint que as executa é a `ONDA2-07-LANCADORES-01`:

    [01] o reparo manual sem caminho   os DOIS — botão «Copiar a linha» E a
                                       linha à mostra —, e SÓ no estado em que
                                       o cartão já diz «linha intocável»
    [02] a frase que manda a um botão  ela para de nomear lugar. **O texto tem
         inexistente                   UM dono para as duas telas, e ele NÃO é
                                       desta posse** — o que esta régua cobra é
                                       que a aba não escreva uma SEGUNDA frase
    [03] de onde o aviso some          as DUAS recusas calam: «Não perguntar
                                       para este jogo» e «Tirar daqui»
    [04] 63 e 22 na mesma tela         o corpo nomeia o conjunto —
                                       «da sua biblioteca (instalados ou não)»

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
        → 2 reprovam (o botão e o bloco somem da fileira pintada)
    torne o mesmo `if` incondicional
        → 1 reprova (o cartão em ordem passa a carregar botão e bloco)
    apague `linha=slo.WRAPPER_LAUNCH` de `_ler_do_disco`
        → 1 reprova (a linha nunca chega ao desenho, e o botão nunca nasce)
    faça `para_a_area_de_transferencia` devolver sempre `True`
        → 1 reprova (o gesto passa a dizer "Copiado!" sem ter copiado)
    tire `lida.recusados` de `calados`
        → 1 reprova (o «Tirar daqui» volta a não calar o aviso)
    tire `(instalados ou não)` do corpo do cartão
        → 1 reprova
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
def test_o_estado_intocavel_traz_o_botao_e_a_linha(desenho, linha_do_motor):
    """Com jogo intocável, o cartão oferece as DUAS saídas da decisão.

    E as duas juntas não são luxo: a cópia pode falhar CALADA — pôr texto na
    área de transferência não devolve resposta nenhuma —, e a linha à mostra
    ainda salva.
    """
    lida = _com_intocavel(desenho, linha_do_motor)
    fileira = _fileira(desenho, lida)
    corpo = _corpo(desenho, lida)

    assert f'data-gesto="{desenho.COPIAR}"' in fileira, (
        f"o cartão com jogo intocável não traz o botão {desenho.COPIAR!r}. O "
        f"carimbo dele já diz 'só reparo manual' e a tela continuaria sem "
        f"oferecer um caminho para fazê-lo.")
    assert desenho.COPIAR_ROTULO in fileira, (
        f"o botão existe e não tem o rótulo que ela decidiu "
        f"({desenho.COPIAR_ROTULO!r})")
    assert 'class="linha-do-wrapper"' in corpo, (
        "a linha à mostra não entrou no corpo do cartão — sem ela, uma cópia "
        "que falhe em silêncio deixa a pessoa sem saída nenhuma")
    assert desenho._e(linha_do_motor) in corpo, (
        "o bloco à mostra não traz a linha do motor. Uma linha diferente da "
        "que o produto grava faria ela colar à mão uma opção que o Hefesto "
        "não reconhece depois.")


def test_no_dia_bom_nada_disso_ocupa_a_tela(desenho, linha_do_motor):
    """Sem jogo intocável, o cartão sai como saía antes — a outra metade da decisão.

    *"No dia bom o cartão fica exatamente como está"*. Um botão de copiar
    permanente seria trabalho manual oferecido a quem não precisa dele: nos
    outros estados a `_VigiaDaSteam` repõe sozinha assim que o jogo e a Steam
    fecham.
    """
    fileira = _fileira(desenho, _em_ordem(desenho, linha_do_motor))
    corpo = _corpo(desenho, _em_ordem(desenho, linha_do_motor))
    assert f'data-gesto="{desenho.COPIAR}"' not in fileira, (
        "o «Copiar a linha» apareceu numa biblioteca em ordem — a decisão é "
        "«só quando faz falta»")
    assert "linha-do-wrapper" not in corpo, (
        "o bloco da linha apareceu numa biblioteca em ordem")


def test_sem_a_linha_o_cartao_cala_em_vez_de_inventar(desenho):
    """Leitura com intocáveis e SEM linha: nem botão, nem bloco.

    O DESENHO NÃO IMPORTA O PRODUTO — é o que deixa o gerador rodar como script
    solto —, então a linha chega pelo contrato frio. Sem ela, um botão de
    copiar copiaria o vazio e diria "Copiado!", e o bloco mostraria um `<code>`
    em branco onde a tela promete uma linha para colar.
    """
    lida = _com_intocavel(desenho, "")
    assert f'data-gesto="{desenho.COPIAR}"' not in _fileira(desenho, lida)
    assert "linha-do-wrapper" not in _corpo(desenho, lida)


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


def test_o_gesto_copia_a_linha_do_motor_e_diz_o_que_fez(
        a07, ctx, linha_do_motor, monkeypatch):
    """O clique põe a linha na área de transferência e devolve o recibo dela.

    O RECIBO É O CANAL DE SUCESSO DA D-01 (`{"recado": …}`), e o texto é o da
    decisão `07[01]` — a mesma primeira oração que a janela velha já diz.
    """
    copiado: list[str] = []
    monkeypatch.setattr(a07, "para_a_area_de_transferencia",
                        lambda t: (copiado.append(t), True)[1])
    resposta = a07.copiar_a_linha(ctx, {"v": "steam"}, None)
    assert copiado == [linha_do_motor], (
        f"o gesto mandou copiar {copiado!r} — e o que se cola na Steam é a "
        f"linha do motor")
    assert resposta.get("recado") == a07.COPIADO, (
        "o gesto copiou e não disse nada. Sem o `recado`, o único sinal de que "
        "o clique funcionou é a área de transferência — que ela não vê.")
    assert "mesa" in resposta, (
        "o gesto não devolveu a carga da pintura: o cartão ficaria com o "
        "estado do tique anterior até o próximo")


def test_o_gesto_recusa_dizendo_quando_a_area_nao_confirma(
        a07, ctx, monkeypatch):
    """O DUBLÊ SABE RECUSAR, e é a metade que prova que a régua mede algo.

    Pôr texto na área de transferência não devolve resposta nenhuma — a
    própria janela velha conclui `copied = True` por não ter levantado, dentro
    de um `suppress(Exception)`. Aqui a confirmação é LIDA DE VOLTA, e quando
    ela não vem a tela DIZ, apontando a segunda saída que está logo acima do
    botão.
    """
    monkeypatch.setattr(a07, "para_a_area_de_transferencia", lambda _t: False)
    with pytest.raises(RuntimeError) as caiu:
        a07.copiar_a_linha(ctx, {"v": "steam"}, None)
    frase = str(caiu.value)
    assert "Ctrl+C" in frase and "cartão" in frase, (
        f"a recusa não manda ela para a linha à mostra: {frase!r}. Uma recusa "
        f"que só diz 'não consegui' deixa a pessoa onde o defeito a deixava.")


def test_a_area_de_transferencia_recusa_sem_laco_de_gtk(a07):
    """Sem janela viva, `para_a_area_de_transferencia` devolve `False`.

    É O COMPORTAMENTO CERTO, e não uma limitação: uma régua que chame o gesto
    sem janela nenhuma **não tem** área de transferência, e dizer "copiei" ali
    seria o instrumento provando o que não aconteceu. Ela também não pode
    LEVANTAR: quem chama é um gesto, e um traceback aqui trocaria a frase da
    recusa por um erro que ela não lê.
    """
    assert a07.para_a_area_de_transferencia("") is False, (
        "copiar o vazio não é copiar")
    assert a07.para_a_area_de_transferencia("qualquer coisa") is False, (
        "a função afirmou ter copiado sem um laço de GTK para confirmar")


# --------------------------------------------------------------------------
# [02] a frase que manda a um botão inexistente — UMA FRASE, UM DONO
# --------------------------------------------------------------------------
def test_a_aba_nao_escreve_uma_segunda_frase_do_aviso(a07):
    """O texto do aviso sai de `home_actions`, e esta aba não o redige.

    A DECISÃO `07[02]` é que a frase **pare de nomear lugar** — e a linha a
    mudar está em `app/actions/home_actions.py:559-562`, que **não é a posse
    desta frente**. O que esta régua impede é o conserto errado: escrever aqui
    uma segunda redação faria as duas janelas do mesmo produto falarem línguas
    diferentes, que é exatamente o que a opção *"duas frases, uma por tela"*
    fazia — e ela foi recusada.

    ELA LÊ AS DUAS PONTAS: o texto que a aba põe na tela tem de ser, palavra
    por palavra, o que a função dona devolve.
    """
    from hefesto_dualsense4unix.app.actions import home_actions as ha

    state = {"gamepad_emulation": {"wrapper_used": False}}
    aviso, _ = a07.aviso_do_jogo_aberto(state, None)
    assert aviso, "o aviso do jogo aberto sumiu da aba"
    dono = ha.wrapper_banner_text(state) or ""
    assert dono and a07._texto(dono) in aviso, (
        f"a aba escreveu um aviso que não é o da função dona. O dono diz "
        f"{dono!r} e a tela mostra {aviso!r} — duas frases para o mesmo fato "
        f"envelhecem separadas.")


# --------------------------------------------------------------------------
# [03] de onde o aviso some — AS DUAS RECUSAS CALAM
# --------------------------------------------------------------------------
def _state_com_jogo(appid: str) -> dict:
    """O `state` do daemon com um jogo Steam aberto SEM o wrapper.

    As duas chaves são as que o produto lê: `wrapper_used is False` é o daemon
    afirmando o fato, e a `window_detect_last_class` é de onde
    `launch_wrapper_dialog.extract_steam_appid` tira o appid.
    """
    return {"gamepad_emulation": {"wrapper_used": False},
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
# [04] 63 e 22 na mesma tela — O CORPO NOMEIA O CONJUNTO
# --------------------------------------------------------------------------
def test_o_corpo_nomeia_o_conjunto_dos_dois_numeros(desenho, linha_do_motor):
    """As duas contagens continuam as medidas, e a tela diz que são conjuntos diferentes.

    ELA COBRA OS DOIS NÚMEROS JUNTOS, que é como o defeito aparece: o canto diz
    `2 jogos instalados` e o corpo diz `5 jogos da sua biblioteca` a uma linha
    de distância. Quem lê vê 5 > 2 e conclui que um dos dois mente.

    O LITERAL ESTÁ AQUI porque ele É a decisão: `07[04]` escolheu *"o corpo
    nomeia o conjunto"* contra as outras duas opções — contar só instalados
    (que apagaria as dezenas de jogos já preparados) e pôr os dois números no
    canto (que disputa a linha com o selo em janela estreita). Texto de tela é
    dela, e uma régua que aceitasse qualquer redação não cobraria a escolha.
    """
    lida = desenho.Leitura(com_wrapper=tuple(str(n) for n in range(5)),
                           instalados=2, linha=linha_do_motor)
    cartao = desenho.cartao_da_steam(lida)
    assert cartao.jogos == "2 jogos instalados"
    assert "5 jogos da sua biblioteca (instalados ou não)" in cartao.diz, (
        f"o corpo não nomeia o conjunto: {cartao.diz!r}. Sem as três palavras, "
        f"os dois números do cartão continuam parecendo contradição.")
