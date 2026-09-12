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
    # O QUE A RÉGUA PROCURA MUDOU EM 11/09/2026 — A2-057, aprovada por ela: a
    # recusa dizia «área de transferência» (o mecanismo) e nomeava o cartão;
    # agora diz «copiar» (o ato) e aponta o lugar — *"logo acima deste botão"*.
    # O que ela cobra é o mesmo: a segunda saída, com a tecla.
    assert "Ctrl+C" in frase and "acima deste botão" in frase, (
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

    ELA LÊ AS DUAS PONTAS: o texto que a aba põe na tela tem de ser, palavra
    por palavra, o que a função dona devolve.
    """
    from hefesto_dualsense4unix.app.actions import home_actions as ha

    state = {"gamepad_emulation": {"enabled": True, "wrapper_used": False}}
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


# ==========================================================================
# O STEAM INPUT — o que a Steam põe ENTRE o controle e o jogo
#
# DECISÃO DELA, 06/09/2026 (`D-0609-STEAM-DIVIDIDO`): **o Steam Input e a lista
# de exceções ficam nesta aba**; "Consertar", "Restaurar de fábrica" e "Aplicar
# aos jogos" ficam na 09.
#
# O QUE ESTAVA MEDIDO (`docs/data/paridade-gtk-html.csv`, linhas 250, 251, 254):
# a janela velha desliga o Steam Input, marca o jogo que não funciona e faz as
# duas coisas de uma vez; a interface nova não fazia NENHUMA das três, em aba
# nenhuma.
#
# A PROVA DESTE BLOCO É O ARQUIVO, e não o código que o escreve. As duas réguas
# que decidem — `test_o_desligar_le_o_arquivo_de_volta_antes_de_dizer_pronto` e
# a irmã dela — montam um `localconfig.vdf` de MENTIRA num `HOME` de mentira,
# rodam o gesto com um script que EDITA o arquivo, e cobram o que ficou EM
# DISCO. Um script que não escreve nada faz a tela RECUSAR — que é o defeito
# que a `HONESTIDADE-STEAM-01` nomeou (*o script pode sair 0 tendo adiado*).
# ==========================================================================
VDF_LIGADO = '''"UserLocalConfigStore"
{
\t"Software"
\t{
\t\t"Valve"
\t\t{
\t\t\t"Steam"
\t\t\t{
\t\t\t\t"apps"
\t\t\t\t{
\t\t\t\t\t"9990001"
\t\t\t\t\t{
\t\t\t\t\t\t"UseSteamControllerConfig"\t\t"2"
\t\t\t\t\t}
\t\t\t\t}
\t\t\t}
\t\t}
\t}
}
'''


@pytest.fixture
def vdf_de_mentira(tmp_path, monkeypatch):
    """Um `localconfig.vdf` de MENTIRA, num `HOME` de mentira, com um appid que
    não existe na Steam de ninguém.

    O `9990001` É SINTÉTICO DE PROPÓSITO, e é a mesma escolha da frente irmã
    (`ONDA5-07-01`): um appid real faria a régua falar de um jogo que pode estar
    na biblioteca de alguém. E o `HOME` é `tmp_path` — **nada do disco dela é
    aberto por este arquivo**, o que a régua de isolamento desta aba já cobra em
    `test_a_aba_lancadores_diz_a_verdade.py`.
    """
    lar = tmp_path / "lar"
    alvo = lar / ".steam/steam/userdata/123/config/localconfig.vdf"
    alvo.parent.mkdir(parents=True)
    alvo.write_text(VDF_LIGADO, encoding="utf-8")
    monkeypatch.setenv("HOME", str(lar))
    monkeypatch.setattr(pathlib.Path, "home", classmethod(lambda cls: lar))
    return alvo


class _PonteDeMentira:
    """Registra o que o gesto mandou ao serviço. Nunca abre socket nenhum."""

    def __init__(self) -> None:
        self.chamados: list[str] = []

    def chamar(self, metodo: str, **params: object) -> bool:
        self.chamados.append(metodo)
        return True


def _com_steam_input(desenho, **extra):
    """Uma leitura em que a biblioteca foi lida E o Steam Input está ligado."""
    return desenho.Leitura(
        com_wrapper=("620",), instalados=1,
        steam_input="<b>Ligado para Um Jogo</b>", steam_input_ligado=True,
        **extra)


# --------------------------------------------------------------------------
# PASSO 1 — conferir e desligar
# --------------------------------------------------------------------------
def test_a_tela_diz_coisas_diferentes_com_o_steam_input_ligado_e_desligado(
        a07, monkeypatch):
    """A MORDIDA DO PASSO 1: dois dublês, duas telas.

    ELA MEDE O PRODUTO, e não o texto do código: o que se compara é o CORPO DO
    CARTÃO que a pintura emite (`steam-diz`), montado a partir da leitura que a
    vigia faz do disco. Com o dublê dizendo "ligado" e com o dublê dizendo
    "desligado", o cartão tem de dizer coisas diferentes — e as palavras têm de
    ser as do DONO (`emulation_actions.markup_status_steam_input`), nunca uma
    segunda redação desta aba.

    ARRANQUE `steam_input=frase_do_steam_input` de `_ler_do_disco` e as duas
    telas voltam a ser a mesma: o cartão fica calado sobre o Steam Input, e a
    tela nova volta a não saber o que a janela velha sabe.
    """
    from hefesto_dualsense4unix.app.actions import emulation_actions as ea

    def _dublê(ligado, jogos=(), excecoes=(), efetiva=None):
        monkeypatch.setattr(ea.EmulationActionsMixin, "_steam_input_is_on",
                            staticmethod(lambda: ligado))
        monkeypatch.setattr(ea.EmulationActionsMixin, "_steam_input_appids_ligados",
                            staticmethod(lambda: list(jogos)))
        monkeypatch.setattr(ea.EmulationActionsMixin, "_steam_input_excecao_status",
                            staticmethod(lambda: (list(excecoes), efetiva)))
        return a07._o_que_a_steam_poe_no_meio()

    ligado, e_ligado = _dublê(True, jogos=["9990001"])
    desligado, e_desligado = _dublê(False)
    assert (e_ligado, e_desligado) == (True, False)
    assert ligado != desligado, (
        "a tela diz a MESMA coisa com o Steam Input ligado e desligado — é "
        "verde sobre nada")
    # AS PALAVRAS SÃO DO DONO, e a régua PERGUNTA a ele em vez de digitar: um
    # literal aqui daria verde no dia em que a frase dele mudasse e a tela
    # ficasse com a antiga.
    assert "Desligado" in ea.markup_status_steam_input(False, [], [], None)
    assert desligado in ea.markup_status_steam_input(False, [], [], None), (
        "a frase do estado desligado não é a do dono — esta aba redigiu a sua")
    assert ligado.startswith("<b>") and ligado.endswith("</b>"), (
        "o estado LIGADO perdeu a ênfase: `.lanc-diz b` é o laranja da aba, e "
        "sem ele a notícia que pede ação sai com o peso de quem não pede")
    assert "<span" not in ligado and "foreground" not in ligado, (
        "o markup do Pango vazou para a tela — um `foreground=` não pinta nada "
        "num navegador, e o atributo morto fica lá")


def test_o_botao_de_desligar_so_nasce_com_o_steam_input_ligado(a07, desenho):
    """"Desligar o Steam Input" não aparece onde ele não teria o que desligar.

    Três estados, três respostas: LIGADO oferece o botão; DESLIGADO não; e a
    leitura que NÃO FALA de Steam Input (a primeira meia volta, e toda régua que
    monte uma `Leitura` à mão) também não — porque ali o produto não mediu, e um
    botão sobre uma medição que não aconteceu é o defeito que esta aba nasceu
    para matar.
    """
    def _fileira(lida):
        cartoes = a07.com_o_que_o_daemon_diz(desenho.cartoes(lida), None, lida)
        return desenho.acoes_html(cartoes[0])

    ligado = _fileira(_com_steam_input(desenho))
    desligado = _fileira(desenho.Leitura(com_wrapper=("620",), instalados=1,
                                         steam_input="Desligado — tudo certo",
                                         steam_input_ligado=False))
    calado = _fileira(desenho.Leitura(com_wrapper=("620",), instalados=1))

    alvo = f'data-gesto="{desenho.DESLIGAR_STEAM_INPUT}"'
    assert alvo in ligado, "o botão não nasce com o Steam Input ligado"
    assert alvo not in desligado, (
        "o botão aparece com o Steam Input JÁ desligado — clicar não mudaria "
        "nada, e botão que não muda nada é botão que finge")
    assert alvo not in calado, (
        "o botão aparece numa leitura que não mediu o Steam Input")
    assert desenho.DESLIGAR_STEAM_INPUT_ROTULO in ligado


def test_o_desligar_recusa_com_jogo_aberto_e_a_frase_e_do_dono(a07, ctx, monkeypatch):
    """Jogo aberto: NADA acontece, e a frase é a da janela velha.

    `steam -shutdown` com jogo aberto MATA o jogo e o progresso não salvo. É o
    primeiro portão do dono (`emulation_actions._steam_input_decidir`) e ele
    vem antes de tudo — inclusive antes de perguntar qualquer coisa.
    """
    from hefesto_dualsense4unix.app.actions.emulation_actions import (
        format_steam_input_result,
    )
    from hefesto_dualsense4unix.integrations import steam_launch_options as slo

    monkeypatch.setattr(a07, "_o_script_que_desliga", lambda: "/bin/true")
    monkeypatch.setattr(slo, "steam_game_running", lambda: True)

    def _nunca(*a, **kw):
        raise AssertionError("fechou a Steam com um jogo aberto")

    monkeypatch.setattr(slo, "with_steam_closed", _nunca)
    a07._desarmar()
    with pytest.raises(RuntimeError) as erro:
        a07.desligar_o_steam_input(ctx, {"v": "steam"}, None)
    assert str(erro.value) == format_steam_input_result(status="jogo_aberto")


def test_o_desligar_com_a_steam_aberta_pergunta_antes_de_fechar(
        a07, ctx, desenho, monkeypatch):
    """DOIS cliques, e o primeiro não fecha nada.

    A MORDIDA: faça `_este_clique_confirma` devolver `True` sempre e o primeiro
    clique passa a fechar a Steam DELA — que é exatamente o que a
    `--prova-gesto` faria na volta seguinte, com o `data-v` que o DOM tinha.
    """
    from hefesto_dualsense4unix.integrations import steam_launch_options as slo

    monkeypatch.setattr(a07, "_o_script_que_desliga", lambda: "/bin/true")
    monkeypatch.setattr(slo, "steam_game_running", lambda: False)
    monkeypatch.setattr(slo, "steam_running", lambda: True)
    monkeypatch.setattr(a07.VIGIA, "agora", lambda: _com_steam_input(desenho))

    fechou: list[str] = []
    monkeypatch.setattr(slo, "with_steam_closed",
                        lambda t, **kw: (fechou.append("fechou"),
                                         (slo.STEAM_JANELA_OK, t()))[1])
    a07._desarmar()
    carga = a07.desligar_o_steam_input(ctx, {"v": desenho.STEAM}, None)
    assert fechou == [], "o PRIMEIRO clique já fechou a Steam dela"
    assert carga["recado"] == a07.PERGUNTA_DA_STEAM
    assert a07._armado_agora() == desenho.DESLIGAR_STEAM_INPUT

    # E o cartão ARMADO oferece o `data-v` que o segundo clique exige — o
    # guarda e a tela têm um dono só.
    lida = _com_steam_input(desenho)
    armado = desenho.acoes_html(
        a07.com_o_que_o_daemon_diz(desenho.cartoes(lida), None, lida)[0])
    assert f'data-v="{a07._confirmo(desenho.DESLIGAR_STEAM_INPUT)}"' in armado
    assert a07.CONFIRMA_A_STEAM in armado


def test_o_consentimento_de_um_ato_nao_vale_para_o_outro(a07, desenho):
    """Armar "Deixar tudo pronto" NÃO confirma "Desligar o Steam Input".

    ERA UM RELÓGIO SÓ até 06/09/2026, e com três botões que fecham a Steam isso
    passou a ser um buraco: o sim dado a um ato valeria para o outro. **O
    consentimento é do ATO, nunca da aba.**

    A MORDIDA: volte `_confirmo` a devolver uma constante única (`"steam:
    confirmo"`) e o `data-v` de um botão passa a confirmar o outro.
    """
    a07._armar(desenho.TUDO_PRONTO)
    assert a07._armado_agora() == desenho.TUDO_PRONTO
    assert a07._confirmo(desenho.TUDO_PRONTO) != a07._confirmo(
        desenho.DESLIGAR_STEAM_INPUT)
    # o `data-v` do outro ato ARMA o outro ato, e não confirma este
    assert a07._este_clique_confirma(
        desenho.DESLIGAR_STEAM_INPUT,
        {"v": a07._confirmo(desenho.TUDO_PRONTO)}) is False
    assert a07._armado_agora() == desenho.DESLIGAR_STEAM_INPUT, (
        "armar um ato não desarmou o outro — dois consentimentos pendurados "
        "sobre a mesma Steam, e nenhum dizendo a qual a confirmação responde")
    a07._desarmar()


def test_o_desligar_le_o_arquivo_de_volta_antes_de_dizer_pronto(
        a07, ctx, desenho, vdf_de_mentira, monkeypatch):
    """A PROVA É O ARQUIVO — o que ficou em disco, lido de volta.

    O script de mentira EDITA o `localconfig.vdf` (é o que o de verdade faz), e
    a régua cobra as duas coisas: o arquivo mudou, e a tela disse que deu certo.

    A MORDIDA, e ela é a do defeito real: troque o script por um que não escreva
    nada. O `rc` continua 0, a tag continua ausente — e a tela tem de RECUSAR,
    porque a releitura ainda diz que está ligado. Era exatamente assim que a
    janela velha mentia antes da `HONESTIDADE-STEAM-01`: *"Steam Input
    desligado"*, incondicional, sobre um no-op.
    """
    from hefesto_dualsense4unix.app.actions.emulation_actions import (
        format_steam_input_result,
    )
    from hefesto_dualsense4unix.integrations import steam_launch_options as slo

    monkeypatch.setattr(slo, "steam_game_running", lambda: False)
    monkeypatch.setattr(slo, "steam_running", lambda: False)
    monkeypatch.setattr(a07.VIGIA, "agora", lambda: None)
    monkeypatch.setattr(a07.VIGIA, "ler", lambda: None)
    monkeypatch.setattr(a07, "_o_script_que_desliga", lambda: "/bin/true")

    assert '"UseSteamControllerConfig"\t\t"2"' in vdf_de_mentira.read_text()

    # 1. O SCRIPT QUE NÃO ESCREVE NADA — a tela RECUSA.
    monkeypatch.setattr(a07, "_rodar_o_script", lambda s: (0, ""))
    a07._desarmar()
    with pytest.raises(RuntimeError) as erro:
        a07.desligar_o_steam_input(ctx, {"v": desenho.STEAM}, None)
    assert erro.value.args[0] == format_steam_input_result(
        status="executado", rc=0, tag=None, ainda_ligado=True), (
        "a tela disse outra coisa que não a frase do dono para 'rodou e "
        "continua ligado'")
    assert '"UseSteamControllerConfig"\t\t"2"' in vdf_de_mentira.read_text(), (
        "o dublê que não escreve nada escreveu alguma coisa")

    # 2. O SCRIPT QUE DE FATO DESLIGA — a tela diz que deu certo.
    def _desliga(_script):
        vdf_de_mentira.write_text(
            vdf_de_mentira.read_text(encoding="utf-8").replace(
                '"UseSteamControllerConfig"\t\t"2"',
                '"UseSteamControllerConfig"\t\t"0"'),
            encoding="utf-8")
        return 0, "[steam-input] resultado=aplicado\n"

    monkeypatch.setattr(a07, "_rodar_o_script", _desliga)
    carga = a07.desligar_o_steam_input(ctx, {"v": desenho.STEAM}, None)
    assert '"UseSteamControllerConfig"\t\t"0"' in vdf_de_mentira.read_text(), (
        "o arquivo não mudou — e a tela ia dizer que mudou")
    assert carga["recado"] == format_steam_input_result(
        status="executado", rc=0, tag="aplicado", ainda_ligado=False)


# --------------------------------------------------------------------------
# PASSO 2 — "Este jogo não funciona"
# --------------------------------------------------------------------------
def test_o_jogo_marcado_chega_na_lista_de_excecoes_e_o_servico_recarrega(
        a07, ctx, monkeypatch, tmp_path):
    """A MORDIDA DO PASSO 2, e ela tem DUAS metades — as duas cobradas aqui.

    1. **o appid chegou ao arquivo.** A régua lê a lista de volta pelo LEITOR do
       produto (`parse_steam_input_allowlist`), nunca por um `in` no texto: um
       appid comentado passaria por substring e não vale como marca;
    2. **o serviço foi avisado.** Sem a recarga a marca só valeria no próximo
       arranque, e ela clicaria de novo achando que o primeiro clique não pegou.

    ARRANQUE o `p.chamar(METODO_DA_RECARGA)` e a segunda metade reprova.
    """
    from hefesto_dualsense4unix.integrations import steam_launch_options as slo

    lista = tmp_path / "steam_input_apps.txt"
    monkeypatch.setattr(slo, "steam_input_allowlist_path", lambda *a, **kw: lista)
    monkeypatch.setattr(a07, "a_escada_do_jogo", lambda _s: (9990001, a07.FECHADO))
    monkeypatch.setattr(a07.VIGIA, "ler", lambda: None)
    ponte = _PonteDeMentira()

    carga = a07.este_jogo_nao_funciona(ctx, {"v": "steam"}, ponte)

    assert slo.parse_steam_input_allowlist(lista.read_text(encoding="utf-8")) == [
        "9990001"], f"o appid não chegou à lista: {lista.read_text()!r}"
    assert ponte.chamados == [a07.METODO_DA_RECARGA], (
        "o serviço não foi avisado — a marca só valeria no próximo arranque, e "
        "o segundo clique dela pareceria o primeiro")
    assert carga["recado"], "o gesto marcou o jogo e não disse nada na tela"


def test_o_jogo_nao_funciona_recusa_quando_nao_sabe_qual_jogo_e(
        a07, ctx, monkeypatch):
    """Sem jogo, a recusa é a frase do dono — nunca um palpite de appid."""
    from hefesto_dualsense4unix.app.actions.daemon_actions import (
        format_game_broken_result,
    )
    from hefesto_dualsense4unix.integrations import steam_launch_options as slo

    monkeypatch.setattr(a07, "a_escada_do_jogo", lambda _s: (None, a07.FECHADO))

    def _nunca(*a, **kw):
        raise AssertionError("marcou um jogo escolhido por acaso")

    monkeypatch.setattr(slo, "add_appid_to_steam_input_allowlist", _nunca)
    with pytest.raises(RuntimeError) as erro:
        a07.este_jogo_nao_funciona(ctx, {"v": "steam"}, _PonteDeMentira())
    assert str(erro.value) == format_game_broken_result(status="sem_jogo")


def test_o_jogo_nao_funciona_nao_pede_consentimento(a07, desenho):
    """Ele é REVERSÍVEL: não fecha nada e não edita arquivo da Steam.

    Por isso a janela velha não abre diálogo aqui, e esta tela não abre também.
    Pedir consentimento para um ato reversível ensina que todo botão pede
    consentimento — e aí o consentimento que importa deixa de ser lido.
    """
    lida = _com_steam_input(desenho)
    fileira = desenho.acoes_html(
        a07.com_o_que_o_daemon_diz(desenho.cartoes(lida), None, lida)[0])
    assert f'data-gesto="{desenho.JOGO_NAO_FUNCIONA}"' in fileira
    assert (f'data-gesto="{desenho.JOGO_NAO_FUNCIONA}" '
            f'data-v="{a07._confirmo(desenho.JOGO_NAO_FUNCIONA)}"') not in fileira


# --------------------------------------------------------------------------
# PASSO 3 — "Deixar tudo pronto", com UM consentimento
# --------------------------------------------------------------------------
def test_deixar_tudo_pronto_faz_os_dois_dentro_de_um_consentimento_so(
        a07, ctx, desenho, monkeypatch):
    """A MORDIDA DO PASSO 3: UM consentimento, e os DOIS trabalhos dentro dele.

    A régua conta as janelas de Steam fechada (tem de ser UMA) e cobra que as
    duas pernas rodaram DENTRO dela — o script primeiro, o atalho depois.

    A razão de não serem dois diálogos está no motor: os dois cabem numa janela
    de `with_steam_closed`, e pedir duas vezes é fazer a pessoa pagar duas vezes
    pelo mesmo fechamento da Steam.
    """
    from hefesto_dualsense4unix.app.actions import daemon_actions as da
    from hefesto_dualsense4unix.integrations import steam_launch_options as slo

    ordem: list[str] = []
    monkeypatch.setattr(a07, "_o_script_que_desliga", lambda: "/bin/true")
    monkeypatch.setattr(a07, "_rodar_o_script",
                        lambda s: (ordem.append("script"), (0, ""))[1])
    monkeypatch.setattr(slo, "apply_wrapper_to_all_games",
                        lambda *a, **kw: (ordem.append("wrapper"),
                                          {"applied": ["9990001"]})[1])
    monkeypatch.setattr(da, "medir_jogos_com_steam_input", lambda: ["Um Jogo"])
    monkeypatch.setattr(a07, "_o_steam_input_continua_ligado", lambda: False)
    monkeypatch.setattr(a07.VIGIA, "agora", lambda: _com_steam_input(desenho))
    monkeypatch.setattr(a07.VIGIA, "ler", lambda: None)

    janelas: list[str] = []

    def _janela(tarefa, **kw):
        janelas.append("abriu")
        return slo.STEAM_JANELA_OK, tarefa()

    monkeypatch.setattr(slo, "with_steam_closed", _janela)

    a07._desarmar()
    # 1º clique: pergunta, e NADA roda.
    primeiro = a07.deixar_tudo_pronto(ctx, {"v": desenho.STEAM}, None)
    assert janelas == [] and ordem == [], "o primeiro clique já fechou a Steam"
    # A FRASE DO CONSENTIMENTO É A DO MOTOR, palavra por palavra.
    assert primeiro["recado"] == " ".join(
        da.DaemonActionsMixin._STEAM_READY_CORPO.split()), (
        "o consentimento foi redigido aqui em vez de vir do dono")

    # 2º clique: UMA janela, os DOIS trabalhos, nesta ordem.
    carga = a07.deixar_tudo_pronto(
        ctx, {"v": a07._confirmo(desenho.TUDO_PRONTO)}, None)
    assert janelas == ["abriu"], (
        f"{len(janelas)} janelas de Steam fechada — a pessoa pagaria "
        f"{len(janelas)} vezes pelo mesmo fechamento")
    assert ordem == ["script", "wrapper"]
    assert carga["recado"] == da.format_steam_ready_result(
        janela=slo.STEAM_JANELA_OK,
        dados={"script": (0, ""), "wrapper": {"applied": ["9990001"]},
               "steam_input_jogos": ["Um Jogo"]})


def test_deixar_tudo_pronto_so_nasce_quando_os_dois_tem_trabalho(a07, desenho):
    """Ele é o botão do consentimento ÚNICO — e só faz falta onde há dois atos.

    Com um lado só pendente, o botão daquele lado já resolve com um
    consentimento igual; um terceiro botão ali seria escolha oferecida sem
    diferença, que é o que a decisão dela tirou da tela em primeiro lugar.
    """
    def _fileira(lida):
        return desenho.acoes_html(
            a07.com_o_que_o_daemon_diz(desenho.cartoes(lida), None, lida)[0])

    alvo = f'data-gesto="{desenho.TUDO_PRONTO}"'
    so_steam_input = _com_steam_input(desenho)
    os_dois = _com_steam_input(
        desenho, reparaveis=(("70", "Um Jogo", "nunca recebeu o atalho"),))
    so_wrapper = desenho.Leitura(
        com_wrapper=("620",), instalados=1, steam_input="Desligado — tudo certo",
        steam_input_ligado=False,
        reparaveis=(("70", "Um Jogo", "nunca recebeu o atalho"),))

    assert alvo in _fileira(os_dois)
    assert alvo not in _fileira(so_steam_input)
    assert alvo not in _fileira(so_wrapper)


def test_a_leitura_do_disco_leva_o_steam_input_ate_o_cartao(
        a07, desenho, vdf_de_mentira, monkeypatch):
    """A PONTE INTEIRA, do disco ao corpo do cartão — e é ela que morde.

    A régua de cima prova que o produto SABE dizer coisas diferentes; esta prova
    que o que ele sabe CHEGA à tela. São dois defeitos diferentes, e o segundo é
    o mais silencioso: uma leitura certa que ninguém emite deixa o cartão calado
    e nada acusa.

    A MORDIDA: arranque `steam_input=` e `steam_input_ligado=` da `Leitura` que
    `_ler_do_disco` devolve. A frase some do corpo do cartão e o botão de
    desligar não nasce — com o arquivo em disco dizendo que está LIGADO.
    """
    assert '"UseSteamControllerConfig"\t\t"2"' in vdf_de_mentira.read_text()
    lida = a07._ler_do_disco()
    assert lida.steam_input_ligado is True, (
        "o produto leu o arquivo, viu ligado, e a leitura não conta isso a "
        "ninguém")
    assert lida.steam_input, "a frase não chegou à `Leitura`"

    cartoes = a07.com_o_que_o_daemon_diz(desenho.cartoes(lida), None, lida)
    quadro = desenho.Quadro(lancadores=cartoes).valores()
    assert lida.steam_input in quadro["steam-diz"], (
        "a frase está na leitura e não no corpo do cartão — pintura perdida")
    assert f'data-gesto="{desenho.DESLIGAR_STEAM_INPUT}"' in quadro["steam-acoes"]


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


def test_com_as_quatro_verdadeiras_o_lembrete_nasce_e_traz_o_botao_de_dispensar(
        a07, desenho):
    """A outra metade: sem ela a régua acima passaria com o aviso morto.

    Uma régua que só cobra AUSÊNCIA fica verde sobre um aviso que nunca nasce —
    é o defeito que esta casa nomeou no `--prova-gesto` do microfone.
    """
    lida = desenho.Leitura(com_wrapper=("620",), instalados=1)
    aviso, appid = a07.aviso_do_jogo_aberto(_mesa_com_jogo_sem_atalho(), lida)
    assert aviso and appid == "9990001"

    cartoes = a07.com_o_que_o_daemon_diz(
        desenho.cartoes(lida), _mesa_com_jogo_sem_atalho(), lida)
    fileira = desenho.acoes_html(cartoes[0])
    assert f'data-gesto="nao-perguntar" data-v="{appid}"' in fileira, (
        "o aviso nasceu sem o botão que o dispensa — o lembrete voltaria a "
        "cada tique e ela não teria como calá-lo")
