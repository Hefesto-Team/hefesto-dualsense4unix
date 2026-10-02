#!/usr/bin/env python3
"""O pacote da aba `01` Jogar — a que MAIS escreve, e a única com gesto ligado.

O QUE TEM DONO, medido no `state_full` de 01/09/2026:

    active_profile      o perfil em vigor                    ← tem dono
    controllers[]       a mesa: quantos, por qual transporte ← tem dono
    battery_pct         a carga de cada um                   ← tem dono
    player              o número de cada um                  ← tem dono
    vpad_backend        a máscara que o jogo vê              ← tem dono
    emulation_suppressed  o Hefesto está fora do meio?       ← tem dono

O MODO (o chip aceso da fileira) NÃO SAI DO STATE DIRETO: quem o lê é
`mode_transition.mode_of_state`, o ponto único de leitura do modo vivo, e ele
devolve TRÊS valores — nunca um quarto. O piloto já usa isso para acender o
interruptor, e é por isso que o botão da Jogar funciona hoje.
"""
from __future__ import annotations

import dataclasses
import html
import sys
import threading
import time
from typing import Any, NamedTuple

from . import TRAVESSAO, Contexto, confirmacao, jogador_de, registrar

CADEADO_CEGO = "cadeado-cego"

#: `cobertura` é a promessa que a régua confere: uma chave nova que não entre
DA_PAGINA: tuple[str, ...] = (
    # dela: *"em jogar remover essa seção do atenção, nenhum aviso esse —
    # `aviso-texto` e `aviso-vivo`.
    # ELES SAEM PORQUE A PÁGINA SAIU, e não por escolha: um endereço emitido sem
    #
    # `autoswitch_lock_text` e `texto_do_cadeado_cego`.
    # onde ligar o cadeado sem explicar por que ele importa.
    "cadeado",
    CADEADO_CEGO,
    "hef-posicao",
    # `data-hef-alvo="classe"` (existe / não existe) e o de dentro sem alvo (o
    "mascara-ressalva",
    "mesa-frase",
    "modo-aceso",
    # O CHIP DO STEAM INPUT TEM CAMPO PRÓPRIO — STEAM-INPUT-01, 20/09/2026, e o
    # — ele senta EM CIMA do caminho DualSense em vez de substituí-lo.
    "steam-input-aceso",
    "pendente",
    "pendente-alvo",
    "pendente-ha",
    "externos",
)

#: ser verdade no mesmo dia:** `gamepad.mask.set` nasceu recebendo `uniq`, o
#: o que o desenho dela mostra — os dois cartões acendiam o MESMO chip. A
POR_CARTAO: tuple[str, ...] = ("plastico", "desenho", "jogador", "jogador-espera",
                               "bateria", "identidade", "mascara-cartao",
                               "marcador-principal")


#: (`a08_conexoes._exame`). Uma lista que tentasse ranqueá-los aqui seria a
#: cheia de esconder um atrás do ``+N`` enquanto mostra o outro.
ORDEM_DA_GRAVIDADE: tuple[str, ...] = (
    "SERVIÇO",
    "PAUSA", "ERRO", "GAMEPAD", "MODO", "PONTE", "JOGO", "CONTROLE", "RÁDIO",
    "PERFIL",
)

SELO_DA_PONTE = "PONTE"

#: (o mixer UAC do DualSense martelando o EP0, `storm_doctor._SND_QUIRK_RE`), e
SELO_DA_CURA = "CONTROLE"

SELO_DO_SERVICO = "SERVIÇO"

#: Hefesto está desligado.")`` no ramo `offline`, e o `validar-palavra-de-tela`
#: DIVERGÊNCIA MORRE PELA RÉGUA:** `test_a_aba_01_jogar_fecha_as_linhas` lê o
SERVICO_DESLIGADO = "O Hefesto está desligado."

SERVICO_CALADO = (
    f"{SERVICO_DESLIGADO} Esta tela parou de ler o serviço. Ela volta sozinha "
    "quando ele responder."
)

MESA_VAZIA = (
    "Nenhum controle ligado. Conecte um pelo cabo ou pelo "
    "rádio: ele aparece aqui sozinho."
)

def lugares_da_mesa() -> int:
    """Quantos cartões a página publica. Lido de `monta.MESA`, nunca digitado."""
    return len(_monta().MESA)


#: O QUE FOI MEDIDO, e decide a forma desta cura: `gamepad.mask.set` grava
RESSALVA_DA_MASCARA = (
    "Guardada neste controle. Ela passa a valer quando o Hefesto voltar a "
    "entregá-lo ao jogo."
)

#: 23/07/2026.
#: exigiria montar a GTK dentro do pacote das dez abas, que é justamente o que
#: `_painel()` existe para evitar. **A DIVERGÊNCIA MORRE PELA RÉGUA, não pela
#: leitura:** `test_a_aba_01_jogar_fecha_as_linhas` lê o fonte da GTK e reprova
#: no dia em que as duas se afastarem. É a mesma escolha que a `MESA_VAZIA` já
#: fez com a frase gêmea da bancada, e pelo mesmo motivo.
#:
#: DECISÃO DELA, portanto — não minha: a palavra que vai à tela nova é a que ela
#: já leu na janela antiga.
#: A RAZÃO DO ESMAECIDO, no ponteiro do mouse — a segunda metade da decisão
#: [02]: *"o número perde a cor forte enquanto o daemon não confirmar o jogador,
#: e o porquê fica no ponteiro do mouse."*
#:
#: ELA É `title`, LOGO É CRAVADA, e isso aqui é seguro pela razão que o
#: `aba01.cartao` já escreve: o piloto **não tem alvo de pintura para atributo
#: de texto**, então toda dica congela no que o gerador soube. O que torna ESTA
#: honesta é ela não afirmar nada sobre um controle em particular — é a razão do
#: ESTADO, igual para os quatro cartões, e o estado quem diz é a classe.
#:
#: PROVISÓRIO — texto de tela é palavra dela (PROVA-DE-TELA-01).
ESPERA_DICA = (
    "O jogo ainda não recebeu este controle. "
    "O número acende quando ele entrar na partida."
)

CADEADO_ROTULO = "Modo Freestyle"
CADEADO_DICA = (
    "O perfil ativo continua valendo mesmo quando você abre outro jogo. "
    "Desligue para o Hefesto voltar a escolher sozinho."
)

#: e `None` quer dizer *não houve resposta* — serviço parado, socket recusado,
#: `test_a_palavra_do_cadeado_e_a_que_ela_ja_leu` confere as TRÊS contra o fonte
CADEADO_RECUSA = "O Hefesto está desligado: a trava não foi aplicada."


CADEADO_LIGADO = "LIGADO"
CADEADO_DESLIGADO = "DESLIGADO"


def _cadeado(state: dict[str, Any]) -> str:
    """``LIGADO`` · ``DESLIGADO`` · travessão — as três respostas da trava."""
    lido = state.get("freestyle_ligado")
    if lido is True:
        return CADEADO_LIGADO
    if lido is False:
        return CADEADO_DESLIGADO
    return TRAVESSAO


#: acrescenta exatamente ``"primário"`` quando ``is_primary``. O CSV nomeia esta
#: pedaço da frase seria mais frágil que a régua. **A DIVERGÊNCIA MORRE PELA
MARCA_DO_PRIMARIO = "primário"

#: (`is_primary`) — e é ele quem navega o PC"*), e é dele que o daemon publica a
#: `is_primary`"*). As duas coisas são medidas, e é isso que a dica diz.
PRIMARIO_DICA = (
    "É por este controle que o Hefesto navega o computador. "
    "Quem o escolhe é o serviço."
)


def _e_o_primario(c: dict[str, Any]) -> str:
    """``"1"`` no cartão do primário, ``""`` nos outros — na língua do `classe`.

    **Passo 3 da JOGAR-O-QUE-FALTA-01 (06/09/2026)**, linha 18 do CSV: *"`is_primary`
    não é lido em `interface/pacotes/`"*. Medido na mesa dela em 02/09, e está
    escrito no `pacotes/__init__.py`::

        uniq …0003 · bt  · player 1    · player_slot 1 · is_primary TRUE
        uniq …00d8 · usb · player None · player_slot 2 · is_primary false

    **SÓ O `True` LITERAL ACENDE.** É a mesma disciplina do `_cadeado` e do
    `wrapper_used`: chave ausente (daemon antigo, ou um controle que o co-op
    ainda não classificou) não é "não é o primário" — é *não sei* —, e a
    resposta a *não sei* nesta casa é não mostrar nada. `bool` é o único tipo
    que passa; um ``1`` inteiro vindo de payload malformado não acende.

    **ELE NÃO É O ALVO DE EDIÇÃO DA FITA.** A classe `.cartao.alvo` já existe e
    responde a outra pergunta — qual controle os ajustes das outras abas vão
    tocar —, e ela é escrita pelo piloto (`hefesto_vivo`, `carga["alvo"]`), não
    por este pacote. Os dois podem ser controles DIFERENTES, e é por isso que
    são dois endereços: o primário é fato do daemon, o alvo é escolha dela.
    """
    return "1" if c.get("is_primary") is True else ""


def _jogador_esperando(c: dict[str, Any]) -> str:
    """``"1"`` enquanto o jogo não recebeu este controle, ``""`` quando recebeu.

    A DECISÃO É [02] desta aba: *"'Player N', esmaecido enquanto espera."* — e o
    dano que ela mata está medido, em 02/09/2026, na mesa dela:

        uniq …0003 · bt  · player 1    · player_slot 1
        uniq …00d8 · usb · player None · player_slot 2   ← o cartão dizia "Player 2"

    **O `None` NÃO É DO TRANSPORTE**, e o `jogador_de` já carrega a medição que
    derrubou essa hipótese: quem volta ``None`` é quem o co-op ainda não promoveu
    a jogador — *"um secundário ainda aguardando o grab não tem vpad: reservou o
    índice, mas não é jogador nenhum até ser promovido"*
    (`daemon/subsystems/coop.CoopManager.player_indexes`).

    AS DUAS CHAVES SÃO LIDAS PELA MESMA ORDEM DO CARTÃO, e é o que impede esta
    função de discordar do número que ela esmaece: se `jogador_de` não achou
    número nenhum, o cartão mostra travessão e não há jogador a ressalvar —
    esmaecer um travessão prometeria que ALGUÉM está esperando.

    O ``player`` É LIDO CRU DE PROPÓSITO. `jogador_de` responde *"que número o
    cartão mostra"* e cai no `player_slot` primeiro; aqui a pergunta é outra —
    *"o JOGO já viu este controle?"* —, e só a chave `player` a responde.

    **A CONEXÃO NATIVA PAROU DE ESMAECER TUDO em 06/09/2026**
    (COOP-NA-CONEXAO-NATIVA-01, Caminho B), e a cura é do outro lado do fio:
    ``coop.resolve_player_numbers`` devolvia ``[None] * N`` naquele modo, então
    o ``player`` era ``None`` para TODOS os controles e esta função esmaecia a
    mesa inteira **para sempre** — prometendo uma promoção que nunca viria,
    porque na Conexão Nativa não há grab nem vpad a esperar. Agora o número vem
    do ``identity_registry`` e o cartão nasce aceso. **Nada mudou aqui**, e é
    isso que se quer registrar: a função já estava certa; quem mentia era a
    fonte.
    """
    if jogador_de(c) is None:
        return ""
    return "" if c.get("player") is not None else "1"


def mascaras_montaveis() -> frozenset[str]:
    """Os rótulos de máscara que o produto SABE MONTAR — para o desenho perguntar."""
    from hefesto_dualsense4unix.daemon.subsystems.external_mask import mascaras_validas
    from hefesto_dualsense4unix.interface.mesa_viva import NOME_DA_MASCARA

    return frozenset(
        NOME_DA_MASCARA[f] for f in mascaras_validas() if f in NOME_DA_MASCARA)


@registrar("01-jogar.html")
def pacote(ctx: Contexto) -> dict[str, Any]:
    """Os valores da aba Jogar, com os NOMES que a página tem."""
    da_sessao = _rotulo_da_mascara(_mascara_da_sessao(ctx.state))
    from hefesto_dualsense4unix.app.actions.home_actions import palavra_do_transporte

    cartoes = {}
    for c in ctx.conectados:
        uniq = str(c.get("uniq") or "")
        # A IDENTIDADE É `nome · transporte`, como o desenho a escreve
        casa = next((m for m in ctx.mesa if str(m.get("uniq") or "") == uniq), {})
        nome = casa.get("nome") or "—"
        via = palavra_do_transporte(casa.get("transporte") or c.get("transport"))
        cartoes[uniq] = {
            "plastico": _cor_do_plastico(str(casa.get("cor") or "")),
            # *"os svgs do dualsense (…) não são os que o meu mapa cataloga"*.
            # `""` QUANDO A COR NÃO É PINTÁVEL, pela mesma régua da borda: o
            "desenho": _colorway_do_desenho(str(casa.get("cor") or "")),
            # abaixo, mostrava com o botão 2 ACESO. O dono lê `player_slot`
            "jogador": f"Player {jogador_de(c) or '—'}",
            "jogador-espera": _jogador_esperando(c),
            "bateria": f"{c.get('battery_pct')}%" if c.get("battery_pct") is not None else "—",
            "identidade": f"{nome} · {via}",
            "mascara-cartao": _mascara_do_cartao(casa, da_sessao),
            "marcador-principal": _e_o_primario(c),
            # `title` que o WebKit nunca deixou acender.
        }


    _relatar_a_pendencia(_faixa_do_pendente(ctx.state)[0])
    tela = _a_fileira_com_a_mesa(_estado_da_tela(ctx.state), ctx.mesa)
    espera = _o_que_o_chip_diz(ctx.state, tela)

    fora: dict[str, Any] = {
        "mesa-frase": _frase_da_mesa(ctx),
        "mascara-ressalva": _ressalva_da_mascara(ctx.state),
        "cadeado": _cadeado(ctx.state),
        CADEADO_CEGO: _cadeado_cego(ctx.state),
        "cartoes": cartoes,
        **tela,
        "pendente": espera,
        "pendente-alvo": "",
        "pendente-ha": "1" if espera else "",
        "blocos": _o_rotulo_do_chip(ctx.state),
        "externos": _html_dos_externos(ctx),
    }
    fora["cobertura"] = {
        "pintados": len(DA_PAGINA) + len(cartoes) * len(POR_CARTAO),
        "sem_dono": 0,
    }
    # dez abas, e o dono deles é `pacotes.topo()`. Emiti-los aqui criava um
    return fora


def _cor_do_plastico(slug: str) -> str:
    """O hex da casca daquele modelo, ou `""` quando ninguém sabe ainda."""
    if not slug:
        return ""
    try:
        import monta

        # dela não têm hexa amostrado e devolvem `url(#hachura-sem-hex)`, que
        return str(monta.cor_de_css(slug))
    except BaseException:
        return ""


def _monta() -> Any:
    """O `monta`, importado tarde — o `pacotes/__init__` põe `interface/` no path."""
    import monta

    return monta


def _colorway_do_desenho(slug: str) -> str:
    """O slug que o `data-colorway` do SVG recebe, ou `""` quando não dá.

    ELA NÃO É UMA SEGUNDA TABELA — é a mesma pergunta de `_cor_do_plastico`,
    feita ao mesmo dono (`monta.cor_da_zona`, que lê a folha gerada do
    `docs/data/cores-do-dualsense.csv`), e o que muda é só o que se devolve: lá
    o HEX da borda, aqui o SLUG com que o desenho se pinta.

    A AMARRAÇÃO É O PONTO. Um slug que o SVG não conhece — modelo novo no CSV,
    ou colorway que o gerador ainda não emitiu — casaria regra nenhuma na folha
    e deixaria o desenho no cinza cru (`rgb(58, 63, 75)`).

    MAS A PERGUNTA MUDOU EM 03/09/2026, e a razão é medida. Aqui estava escrito
    `slug if _cor_do_plastico(slug) else ""`, com o argumento de que *"os dois
    calam juntos: sem cor, sem desenho colorido"*. Isso valia enquanto **sem
    hex** quisesse dizer **a folha não conhece**. Não quer: OITO dos vinte e
    oito modelos dela pintam com `<pattern>` ou gradiente, a folha os conhece, e
    o SVG os veste sem problema — é só a PELE que não pode receber um `url(…)`.

    Calá-los junto com a pele trocaria um defeito por outro maior: o controle
    ficaria SEM IDENTIDADE NENHUMA na tela, quando o aparelho tem identidade e o
    mapa dela a cataloga. A pergunta certa é `monta.o_desenho_conhece`.
    """
    return slug if slug and _monta().o_desenho_conhece(slug) else ""


def _do_exame() -> list[dict[str, Any]]:
    """Os achados do exame da mesa, ou lista vazia. Nunca levanta.

    O SELO É DO PRODUTO, e esta função já mentiu — medido em 03/09/2026. Ela
    montava::

        {"selo": "RÁDIO" if i["grave"] else "AVISO", **i}

    e o ``**i`` que vem DEPOIS sobrescreve a chave que a linha acabou de
    escrever: `a08_conexoes._linha` já emite ``selo``, tirado de
    `interface.conexoes.SELO_DO_ESTADO`, que é o dono da palavra. As duas palavras
    digitadas aqui — "RÁDIO" e "AVISO" — **nunca chegaram a uma tela**; o que
    chegava era o selo do exame, que tem quatro estados e inclui o **CERTO**.
    Fotografado na 01 em 02/09: o selo `CERTO` sob o cabeçalho laranja
    **Atenção**, com o texto "Economia de energia desligada" — uma boa notícia
    vestida de alarme.

    A CURA NÃO É REPOR AS DUAS PALAVRAS. Elas eram uma segunda tradução de um
    estado que já tem dono, e repô-las devolveria a divergência no primeiro
    estado novo do exame. O que sai daqui é o que o exame diz; quem escolhe o
    que vai para a coluna **Atenção** é :func:`_avisos`, e ele só leva o que é
    ``grave`` — um "CERTO" não é um aviso.

    O `except` LARGO CONTINUA, e o preço dele está escrito no dono
    (`a08_conexoes._exame`): um `AttributeError` já virou lista vazia aqui e
    apagou meia coluna sem uma linha de erro. O que mudou é que o silêncio
    acabou — :func:`_avisos` transforma a falha num aviso com o selo ``ERRO``,
    que é a mesma política de `painel.avisos_do_estado`.
    """
    from . import a08_conexoes

    return list(a08_conexoes._exame())


def _avisos(ctx: Contexto) -> list[dict[str, str]]:
    """As onze fontes de aviso do produto: ``[{"selo", "texto", "fonte"}, …]``.

    **ELE PERDEU A TELA EM 07/09/2026, E NÃO PERDEU AS FONTES.** Ordem dela:
    *"em jogar remover essa seção do atenção, nenhum aviso esse — deixar só o
    reconectar controles."* A coluna **Atenção** da aba Jogar era o ÚNICO lugar
    publicado onde estas linhas pousavam, e ela saiu — os quatro endereços
    (`atencao-conta`, `aviso-selo`, `aviso-texto`, `aviso-vivo`) saíram de
    :data:`DA_PAGINA` junto, porque endereço sem elemento é órfão.

    **MEDIDO ANTES DE APAGAR, e é o número que decide:** das onze fontes abaixo,
    **só a 5** (o exame da mesa, `a08_conexoes._exame`) tem uma segunda casa
    publicada — a aba **Conexões**, de onde ela vem. As outras dez chegavam à
    tela SÓ por aqui. Na máquina dela, no instante da medição, a coluna mostrava
    UMA linha viva: `home_actions.texto_do_cadeado_cego`, *"O Hefesto não está
    conseguindo ver qual programa está na frente…"*.

    **PARA ONDE ELAS VÃO — a aba 09, Sistema**, e a proposta não é minha: é o
    que a própria frase viva já manda, com estas palavras, **A aba Sistema diz
    por quê**. A 09 é a página cujo trabalho inteiro é a máquina se explicar;
    ela já publica uma lista de achados com selo, glifo e frase
    (`exame-lista`, de `a09_sistema`) e já recebe uma das
    onze — a cura do travamento do USB. As dez órfãs cabem na MESMA lista, sem
    peça de tela nova.

    **E FORAM — 28/09/2026, A-TELA-PERGUNTA-AO-DONO-01.** O pacote da 09
    (`a09_sistema.pacote`) pergunta a :func:`coluna_de_atencao` e acrescenta as
    linhas ao exame, com o selo de aviso do exame. Vão as fontes SEM outra casa
    (:func:`_avisos_sem_outra_casa`); as que a tela já mostra em outro lugar
    ficam no canal e fora da 09 (:func:`_avisos_com_outra_casa`).

    **NADA SE ESCREVE AQUI.** As fontes já existiam, e todas fora deste
    arquivo — o que faltava era o produto novo CHAMÁ-LAS. Medido em
    03/09/2026: quem consumia `painel.AVISOS_DA_TELA` era `interface/jogar_vivo.
    py`, que é BANCADA; a aba publicada mostrava, no lugar delas, o Check-up da
    aba Conexões — dois conjuntos DISJUNTOS, e o da GTK era o que respondia
    pelas perguntas desta tela.

    O QUE ENTRA, e em que ordem:

    0. **o serviço calado** (:func:`_aviso_do_servico_calado`) — a única fonte
       desta coluna que responde sobre a AUSÊNCIA de estado, e a única que fala
       quando todas as outras calam. Ela vem primeiro na lista e primeira na
       escada (:data:`ORDEM_DA_GRAVIDADE`), pelo mesmo critério: com o serviço
       calado, toda outra linha descreveria um estado que a tela não leu;
    1. **as seis de `painel.AVISOS_DA_TELA`** — pausa, vpad degradado, rádio
       frágil, jogo sem wrapper, o cadeado da troca automática e o detector
       cego. São funções puras de `home_actions`, e `painel.avisos_do_estado` já
       trata a que levanta (vira selo ``ERRO`` em vez de derrubar a coluna);
    2. **o opt-out antigo** (`home_actions.aviso_de_opt_out_antigo`). Ele não
       está em `AVISOS_DA_TELA` porque pede dois argumentos que só a tela sabe —
       se a escolha de disco está DESLIGADA e quantos controles há na mesa — e
       os dois têm dono: `painel.modo_lembrado()` lê o
       ``gamepad_disabled.flag`` e `ctx.conectados` é a mesa. É a pergunta
       literal dela de 31/08 (*"não sei se segue desativado"*), e na máquina
       dela ela está QUENTE agora;
    3. **a ponte com o jogo** (:func:`_aviso_da_ponte`), e só quando ela é má
       notícia. Desde 28/09/2026 ela fica no canal e fora da 09
       (:func:`_avisos_com_outra_casa` diz por quê);
    3-bis. **a divergência de máscara**
       (:func:`_aviso_da_divergencia_de_mascara`), o ALARME que o daemon publica
       desde a MASCARA-01. Ela mora AQUI e não em `AVISOS_DA_TELA` porque volta
       em markup do Pango, como a ponte — o docstring dela diz por quê, e é
       portão;
    4. **a cura do travamento do USB**
       (:func:`_aviso_da_cura_do_travamento`) — a fonte que nasceu em
       06/09/2026, ONDA5-01-01. Ela não é função de `state`: lê o disco, como
       a ponte lê a cor do produto;
    5. **os achados GRAVES do exame da mesa** (`a08_conexoes._exame`), que era o
       único que esta coluna já mostrava. Os ``certo`` ficam de fora: a coluna
       chama-se Atenção.

    **FATO SUBSTITUÍDO — 06/09/2026, DUAS VEZES NO MESMO DIA.** Estas linhas
    diziam *"as oito fontes"* e enumeravam TRÊS itens; corrigidas para **dez**
    pela manhã, envelheceram de novo à tarde, quando o serviço calado virou a
    décima-primeira. **É a terceira vez que o número desta docstring erra**, e a
    lição não muda: o que fica escrito é a LISTA, que se conta sozinha. Se você
    veio acrescentar uma fonte, acrescente um item — não um número.

    O SELO DO OPT-OUT É ``GAMEPAD``, e não uma palavra nova: é o mesmo que
    `AVISOS_DA_TELA` dá ao vpad degradado, e os dois falam do mesmo assunto — o
    gamepad virtual que o jogo vê. Inventar um selo a mais poria uma palavra de
    tela num arquivo que não é o dono de nenhuma.
    """
    calado = _aviso_do_servico_calado(ctx)
    fora: list[dict[str, str]] = [calado] if calado else []
    fora += _avisos_sem_outra_casa(ctx)
    fora += _avisos_com_outra_casa(ctx)
    return fora


FONTES_DO_PAINEL_COM_OUTRA_CASA: dict[str, str] = {
    "home_actions.texto_da_pausa":
        "a linha «Serviço» do Status da 09 diz PAUSADO",
    "home_actions.texto_do_cadeado_cego":
        "a linha «Troca de perfil ao abrir o jogo» do Status da 09 diz SEM VER",
    "home_actions.autoswitch_lock_text":
        "a pílula «Modo Freestyle» da Jogar acende",
}


def _do_painel(ctx: Contexto, com_outra_casa: bool) -> list[dict[str, str]]:
    """As fontes de `painel.AVISOS_DA_TELA`, de um lado ou do outro da 09.

    Uma leitura do dono (`painel.avisos_do_estado`), cortada pelo nome da fonte
    em :data:`FONTES_DO_PAINEL_COM_OUTRA_CASA`. A linha de ``ERRO`` de uma fonte
    que levantou vai para o mesmo lado da fonte.
    """
    painel = _painel()
    return [a for a in painel.avisos_do_estado(ctx.state)
            if (a.get("fonte") in FONTES_DO_PAINEL_COM_OUTRA_CASA) is com_outra_casa]


def _avisos_sem_outra_casa(ctx: Contexto) -> list[dict[str, str]]:
    """As fontes que SÓ a coluna Atenção publicava — as que vão à aba Sistema.

    SEPARADAS DAS OUTRAS em 28/09/2026 (A-TELA-PERGUNTA-AO-DONO-01), quando a
    lista do exame da 09 passou a recebê-las (:func:`coluna_de_atencao`). As
    que ficam de fora já têm casa na tela, e levá-las à 09 poria a mesma
    notícia duas vezes: o serviço calado (o Status da 09 diz o estado do
    serviço), a ponte com o jogo (a fileira da Jogar acende o caminho vivo),
    a cura do travamento do USB (o exame da 09 a lê pelo mesmo dono,
    `storm_doctor.check_snd_quirk`, dentro do `storm_report`), os achados do
    exame dos controles (a aba Conexões, de onde eles vêm) e as três do
    `painel` de :data:`FONTES_DO_PAINEL_COM_OUTRA_CASA`.
    """
    painel = _painel()
    fora: list[dict[str, str]] = _do_painel(ctx, com_outra_casa=False)

    try:
        from hefesto_dualsense4unix.app.actions import home_actions

        texto = home_actions.aviso_de_opt_out_antigo(
            ctx.state,
            opt_out=painel.modo_lembrado().ligado is False,
            conectados=len(ctx.conectados),
        )
        if texto:
            fora.append({"selo": "GAMEPAD", "texto": str(texto),
                         "fonte": "home_actions.aviso_de_opt_out_antigo"})
    except Exception as erro:
        fora.append({"selo": "ERRO",
                     "texto": f"o opt-out antigo não respondeu ({type(erro).__name__}).",
                     "fonte": "home_actions.aviso_de_opt_out_antigo"})

    try:
        divergencia = _aviso_da_divergencia_de_mascara(ctx.state)
        if divergencia:
            fora.append(divergencia)
    except Exception as erro:
        fora.append({"selo": "ERRO",
                     "texto": f"a divergência de máscara não respondeu "
                              f"({type(erro).__name__}).",
                     "fonte": "home_actions.mascara_divergente_do_daemon"})

    return fora


def _avisos_com_outra_casa(ctx: Contexto) -> list[dict[str, str]]:
    """As fontes do canal que a tela já mostra em outro lugar."""
    fora: list[dict[str, str]] = _do_painel(ctx, com_outra_casa=True)
    ponte = _aviso_da_ponte(ctx.state)
    if ponte:
        fora.append(ponte)
    try:
        cura = _aviso_da_cura_do_travamento()
        if cura:
            fora.append(cura)
    except Exception as erro:
        fora.append({"selo": "ERRO",
                     "texto": f"a cura do travamento não respondeu ({type(erro).__name__}).",
                     "fonte": "storm_doctor.check_snd_quirk"})

    try:
        fora += [{"selo": str(i["selo"]), "texto": str(i["titulo"]),
                  "fonte": "a08_conexoes._exame"}
                 for i in _do_exame() if i.get("grave")]
    except Exception as erro:
        fora.append({"selo": "ERRO",
                     "texto": f"o exame dos controles não respondeu ({type(erro).__name__}).",
                     "fonte": "a08_conexoes._exame"})
    return fora


def _aviso_do_servico_calado(ctx: Contexto) -> dict[str, str] | None:
    """A linha *"O Hefesto está desligado"* — e ``None`` quando o serviço falou.

    **JOGAR-O-QUE-FALTA-01, Passo 5 (06/09/2026)**, e é a linha 38 do CSV da
    paridade — o passo que a sprint chama de *"o que mais vale"*. O veredito de
    lá, medido: *"o tique imprime `[daemon mudo] …` no stderr do processo e
    retorna sem pintar nada — a tela fica com os últimos valores"*, e a leitura:
    *"quem clica não lê terminal"*.

    **A OMISSÃO ERA A MENTIRA, e ela tinha número.** Medido nesta árvore, com o
    pacote recebendo um estado vazio: a coluna Atenção emitia
    ``atencao-conta = "nenhum aviso"`` e seis linhas em branco. *"Nenhum aviso"*
    é uma AFIRMAÇÃO — quer dizer "perguntei e não há nada" —, e o que havia era
    ninguém para perguntar. É a mesma forma do defeito que `_estado_da_tela` já
    fecha do outro lado (o interruptor aceso sobre um estado que ninguém leu).

    **AS DUAS METADES SÃO UMA SÓ, e a sprint diz por quê:** *"só dizer, deixando
    os números velhos na tela, ainda é mentira; só apagar, sem dizer, parece
    defeito"*. A metade de APAGAR já existe e não é desta aba —
    `pacotes.pacote_da_pagina` acrescenta o molde e
    `pacotes.apagar_os_lugares_sem_dono` escreve nos quatro lugares o que o desenho
    diz do vazio, medido nesta árvore com o estado vazio. O que faltava era a metade de DIZER,
    e é esta função.

    **O ESTADO VAZIO É O SINAL, e ele é o mesmo que a aba inteira já usa.**
    `_estado_da_tela`, `_frase_da_mesa`, `_ressalva_da_mascara` e `_pendencia`
    abrem todas com ``if not state``, e a razão está escrita em `_estado_da_tela`:
    ``mode_of_state({})`` devolve **desktop**, então quem não guardar esta porta
    afirma um modo sobre um tique sem resposta. Aqui a mesma porta é lida ao
    contrário — é ela que dá a notícia.

    **A VOLTA É SOZINHA e não se promete de graça:** o tique do piloto continua
    correndo (`hefesto_vivo.TIQUE_MS`, 100 ms) e o primeiro estado que voltar
    apaga esta linha pelo caminho normal da coluna. É o que a frase diz, e é o
    que o produto faz — nenhuma das duas metades é aspiração.

    **O QUE ESTA FUNÇÃO NÃO ALCANÇA, e está relatado:** hoje o piloto **não
    chama o pacote** quando `mesa_viva.estado_do_daemon()` levanta
    (`hefesto_vivo._tique`: imprime `[daemon mudo]` e `return True`), então esta
    linha só acende no dublê e no dia em que o piloto passar o estado vazio
    adiante. `interface/hefesto_vivo.py` é posse da `ONDA5-P-01` e `nao_toca`
    desta sprint — a metade de lá é uma linha, e ela está no relato.
    """
    return (None if getattr(ctx, "state", None)
            else {"selo": SELO_DO_SERVICO, "texto": SERVICO_CALADO,
                  "fonte": "home_actions._render_home (ramo offline)"})


def _aviso_da_ponte(state: dict[str, Any]) -> dict[str, str] | None:
    """A linha *"Ponte com o jogo"*, e só quando ela é MÁ NOTÍCIA.

    É a órfã que faltava da D-10 (*"Todas na coluna Atenção"*) — e a medição
    corrigiu o enunciado: das TRÊS frases que a decisão nomeia, **duas já
    estavam na coluna** desde 03/09. A PAUSA é `AVISOS_DA_TELA[0]` e o cadeado
    são as duas últimas (`autoswitch_lock_text` e `texto_do_cadeado_cego`). A
    ponte era a única sem canal em toda a interface nova.

    **QUEM DECIDE SE É MÁ NOTÍCIA É O PRODUTO, e a leitura é a cor dele.**
    `texto_da_ponte` devolve markup do Pango e pinta o veredito: `_COR_OK` nos
    dois desfechos bons ("direto (Sony)" e "pelo Hefesto"), `_COR_AVISO` nos
    dois ruins ("de pé, e vazia" e "nenhuma"), e cor NENHUMA no "não sei" de
    daemon desligado. Ler a cor é ler a escada de gravidade que a função já tem;
    reescrever aqui as quatro perguntas dela seria a segunda cópia da regra, e a
    de cá envelheceria no primeiro desfecho novo.

    A COLUNA CHAMA-SE ATENÇÃO, e é por isso que a boa notícia fica de fora — a
    mesma disciplina que já deixa os ``certo`` do exame de fora. E o "não sei"
    também: sem daemon não se afirma nada, que é a regra do `autoswitch_lock_
    text` e a razão de o `_estado_da_tela` não pintar sobre estado vazio.

    O MARKUP NÃO CHEGA À TELA: `interface.sistema.sem_markup` é o dono de tirá-lo
    (a `a09_sistema` já o usa), e sem ele o `<span foreground="#ffb86c">` iria
    LITERAL para o `textContent` — o piloto escreve texto, não HTML.

    A CONSTANTE PRIVADA É DE PROPÓSITO, e a guarda também: `_COR_AVISO` é o
    único lugar em que aquela função declara *"isto é ruim"*. Se ela sumir, esta
    régua **cala** em vez de alarmar — um `"" in frase` casaria com tudo e
    encheria a coluna de boa notícia vestida de alerta, que é exatamente o
    defeito que o `_do_exame` já custou nesta aba.
    """
    if not state:
        return None
    from hefesto_dualsense4unix.app.actions import home_actions

    ruim = str(getattr(home_actions, "_COR_AVISO", "") or "")
    if not ruim:
        return None
    frase = home_actions.texto_da_ponte(state)
    if ruim not in frase:
        return None
    texto = _sem_markup(frase)
    if texto.startswith(home_actions.PONTE_PREFIXO):
        texto = texto[len(home_actions.PONTE_PREFIXO):]
    return {"selo": SELO_DA_PONTE, "texto": texto,
            "fonte": "home_actions.texto_da_ponte"}


def _sem_markup(frase: str) -> str:
    """O texto de uma frase do produto, sem o markup do Pango. UMA porta só."""
    from hefesto_dualsense4unix.interface.sistema import sem_markup

    return sem_markup(frase)


def _aviso_da_divergencia_de_mascara(state: dict[str, Any]) -> dict[str, str] | None:
    """A escolha de máscara que não chegou ao aparelho; ``None`` quando chegou."""
    if not state:
        return None
    from hefesto_dualsense4unix.app.actions import home_actions

    alarme = home_actions.mascara_divergente_do_daemon(state)
    if alarme is None:
        return None
    frase = home_actions.texto_da_divergencia(
        alarme.get("mascara_perfil"),
        alarme.get("mascara_viva"),
        jogo_aberto=home_actions.jogo_com_autoridade(state),
        fonte=home_actions.FONTE_PERFIL,
        perfil=alarme.get("profile"),
    )
    if not frase:
        return None
    return {"selo": "GAMEPAD", "texto": _sem_markup(frase),
            "fonte": "home_actions.mascara_divergente_do_daemon"}


def _aviso_da_cura_do_travamento() -> dict[str, str] | None:
    """A linha da **cura do travamento do USB**, e só quando ela pede ação.

    **A PALAVRA DELA, 05/09/2026**, sobre o aviso do Modo Nativo: *"Não me
    lembro disso acontecer. E não deveria. Mas caso ocorra na coluna atenção"* —
    e a medição diz que ela tem razão nas três. O Hefesto **conserta** a causa
    desde a SPRINT-GAME-RUMBLE-01 (o quirk `054c:0ce6:…ignore_ctl_error` do
    `snd_usb_audio`, que torna o probe do mixer UAC tolerante e para de martelar
    o EP0), e o `install.sh` a instala. Ela não se lembra porque **na máquina
    dela a cura está de pé** — medido em 06/09/2026, ``[ OK ]``. O dia em que
    esta linha aparece é o dia em que a cura cai: um kernel novo, um
    `/etc/modprobe.d` limpo, uma instalação ainda sem replug.

    **O DEFEITO QUE ELA FECHA: as duas telas discordavam sobre a mesma
    máquina.** `check_snd_quirk` já chegava à aba **Sistema**, empacotada em
    `storm_report` (`a09_sistema._achados`) — e a aba **Jogar**, que é a que
    fica aberta enquanto o jogo roda, dizia *"nenhum aviso"*.

    **NADA SE DIGITA AQUI.** A frase inteira vem de
    `storm_doctor.check_snd_quirk`, com o ``O que fazer:`` que o
    ``PREFIXO_DA_CURA`` já põe e com o gesto do formato desta instalação
    (`gesto_de_atualizar`). Reescrevê-la neste arquivo seria a segunda cópia de
    uma palavra que tem dono — o defeito que `_do_exame` já custou a esta aba,
    quando digitou "RÁDIO" e "AVISO" por cima de um selo que o produto emitia.

    **SÓ ``check_snd_quirk``, NUNCA ``storm_report``**: o pacote da 09 roda seis
    exames, e cinco deles não têm nada a ver com esta coluna.

    **O QUE ENTRA, E O QUE NÃO ENTRA.** ``[WARN]`` (a cura em lugar nenhum) e
    ``[INFO]`` (a cura agendada, esperando o replug) são trabalho pendente e
    entram. ``[ OK ]`` **fica de fora**: boa notícia não é Atenção, e a coluna
    chama-se assim — a mesma disciplina que já deixa os ``certo`` do exame de
    fora e que fez :func:`_aviso_da_ponte` recusar os dois desfechos bons. Foi
    um ``CERTO`` sob o cabeçalho laranja, fotografado em 02/09, que ensinou.

    **O CUSTO POR TIQUE, MEDIDO ANTES DE LIGAR** (06/09/2026, a máquina dela,
    `.venv` da raiz; a 09 declara os dela por este mesmo motivo):

    * **0,030 ms** por chamada no caminho ``[ OK ]``, que é o desta máquina —
      são os dois ``open`` de `/sys/module/snd_usb_audio/parameters/quirk_flags`
      e `/etc/modprobe.d/hefesto-dualsense-storm.conf`;
    * **0,075 ms** no caminho ``[WARN]``, que ainda chama `gesto_de_atualizar`;
    * **0,79 ms** na PRIMEIRA chamada do caminho ``[WARN]``, uma vez por
      processo: é o `main.glade` sendo lido para o rótulo do botão, e ele fica
      em `_ROTULOS_EM_CACHE`.

    **O TIQUE DESTA JANELA É DE 100 ms** (`interface/hefesto_vivo.TIQUE_MS`).
    O pior caso mede **0,8%** dele, e o normal **0,03%** — por isso **não há
    cache aqui**. Cachear teria custo: o que estes dois arquivos dizem muda no
    replug e no boot, e uma memória nesta função faria a coluna continuar
    alarmando depois de a pessoa fazer exatamente o que a frase mandou.

    A MORDIDA está em `tests/unit/test_a01_a_coluna_atencao_acende_o_mais_grave.py`.
    """
    from hefesto_dualsense4unix.integrations import storm_doctor

    selo, frase = storm_doctor.check_snd_quirk()
    if selo == storm_doctor.OK:
        return None
    return {"selo": SELO_DA_CURA, "texto": str(frase),
            "fonte": "storm_doctor.check_snd_quirk"}


def _em_ordem(avisos: list[dict[str, str]]) -> list[dict[str, str]]:
    """Os avisos com o mais grave em cima — a metade da D-09 que sobreviveu."""
    posto = {selo: i for i, selo in enumerate(ORDEM_DA_GRAVIDADE)}
    fim = len(ORDEM_DA_GRAVIDADE)
    return sorted(avisos, key=lambda a: posto.get(str(a.get("selo") or ""), fim))


def coluna_de_atencao(ctx: Contexto) -> list[dict[str, str]]:
    """Os avisos que SÓ a coluna Atenção publicava, o mais grave em cima."""
    return _em_ordem(_avisos_sem_outra_casa(ctx))


def _frase_da_mesa(ctx: Contexto) -> str:
    """A linha por cima dos lugares apagados — ``""`` quando a mesa cabe na tela."""
    if not ctx.state:
        return ""
    quantos = len(ctx.conectados)
    if quantos == 0:
        return MESA_VAZIA
    lugares = lugares_da_mesa()
    if quantos > lugares:
        return (f"Há {quantos} controles ligados e esta tela mostra "
                f"{lugares}: o cabeçalho conta todos.")
    return ""


def _html_dos_externos(ctx: Contexto) -> str:
    """Um cartão por controle que o Hefesto VÊ e NÃO adota — ``""`` sem nenhum.

    **A LINHA 16 DO CSV DA PARIDADE**, e o defeito que ela nomeia é uma
    regressão: *"com dois DualSense e um 8BitDo na mesa a aba dizia '2
    controles' ao lado de três cards noutra tela"*. A janela antiga fechou isso
    em 25/08 (a `I5`) e a tela nova nasceu com ele de volta — não por falta de
    dado (`controller.list {external: true}` responde), mas porque ninguém
    perguntava.

    **NADA DE TEXTO SE ESCREVE AQUI, e é o ponto inteiro.** As três frases têm
    dono na janela antiga, e são elas que chegam:

    * ``_format_external_title`` — *"Controle 3 — 8BitDo"*. O número é o SLOT
      GLOBAL de co-op, **o mesmo que o Hefesto escreve no LED de player do
      aparelho**; a marca vem de ``external_controllers.brand_of``, que é a
      única que sabe desmentir o VID mentido pelo clone em modo DualShock4
      (o OUI do MAC vence, e ele é o único sinal que os separa);
    * ``_format_external_subtitle`` — *"cabo · o Hefesto só vê"*, e a palavra do
      transporte sai de ``home_actions.palavra_do_transporte``, que é o §2 do
      "o que se mede antes de escrever" desta sprint;
    * ``external_controllers.nintendo_bt_warning`` — a armadilha do
      ``hid-nintendo``, que é o SINAL da linha 305 do mesmo CSV. Ela só existe
      no rádio e só para VID Nintendo; ``None`` nos outros, e aí a linha não
      nasce.

    **O CARTÃO NÃO TEM COR DE PLÁSTICO, E ISSO É HONESTO.** A folha das 28 é dos
    DualSense (`docs/data/cores-do-dualsense.csv`); um 8BitDo não tem linha
    nela. Inventar uma borda seria a tela afirmando um modelo que ninguém mediu
    — a mesma regra que faz `_cor_do_plastico` devolver `""` para o que o SVG
    não conhece.

    **NEM NÚMERO DE JOGADOR ESMAECIDO, NEM BATERIA.** O externo não é jogador do
    co-op (`plataforma.vpad@sn30` está em `existe: desconhecido` no mapa de
    canais) e o daemon não lê a carga dele. Campo sem informação não mostra
    nada, que é regra dela.

    **ELE NASCE DENTRO DA GRADE DOS QUATRO ASSENTOS — escolha DELA, 06/09/2026.**
    A EXTERNOS-01 entregou os cartões numa faixa à parte, embaixo, e PERGUNTOU:
    faixa à parte, ou o mesmo frame, como a janela GTK fazia? A resposta foi o
    mesmo frame. O que muda deste lado é só o cabeçalho da seção, que morreu com
    a seção; o cartão em si já tinha a forma certa. Quem faz o cartão virar item
    da grade é o CSS da bancada (`aba01.py`, `.pecas .ext-vaga{display:contents}`)
    — este pacote continua devolvendo só os cartões, e não sabe onde eles caem.

    **NÃO É UM CARTÃO `.cartao`, e entrar na grade não mudou isso.** A classe é
    outra de propósito: `.cartao` é dos quatro assentos, tem
    `data-controle="pN"`, entra na conta de `apagar_os_lugares_sem_dono` e
    recebe o alvo de edição da fita. Um externo não tem assento — dar-lhe a
    mesma classe faria as duas coisas brigarem no mesmo pixel, que é o erro que
    o `marcador-principal` já pagou uma vez. **Estar no mesmo frame é uma
    escolha de DESENHO; ser um assento é uma afirmação sobre o aparelho**, e
    esta função não faz a segunda.

    **QUEM O DISTINGUE É A MARCA**, e é o que a janela GTK fazia
    (`app/widgets/external_card.py`, o título): o assento diz *"Sony · Player
    1"*, o externo diz *"Controle 3 — 8BitDo"*. A palavra da marca vem de
    ``external_controllers.brand_of`` por dentro de ``_format_external_title`` —
    nenhuma marca se digita aqui.
    """
    if not ctx.externos:
        return str(_monta().NADA_A_DIZER)
    from hefesto_dualsense4unix.app.actions.external_controllers import (
        nintendo_bt_warning,
    )
    from hefesto_dualsense4unix.app.actions.home_actions import (
        _format_external_subtitle,
        _format_external_title,
    )
    def _e(x: object) -> str:
        """Escapa para HTML — pelo `html.escape` da biblioteca, e não pelo `_e`"""
        return html.escape(str(x), quote=True)

    fora = []
    for entrada in ctx.externos:
        aviso = nintendo_bt_warning(entrada)
        linha_do_aviso = (f'<div class="ext-aviso">{_e(aviso)}</div>'
                          if aviso else "")
        fora.append(
            '<div class="ext-cartao">'
            f'<div class="ext-nome">{_e(_format_external_title(entrada))}</div>'
            f'<div class="ext-via">{_e(_format_external_subtitle(entrada))}</div>'
            f'{linha_do_aviso}</div>')
    return "".join(fora)


def _cadeado_cego(state: dict[str, Any]) -> str:
    """A ressalva do cadeado: o detector está cego? — marcador quando não.

    **POR QUE ELA EXISTE, e é de 07/09/2026.** A caixa *"Não trocar de perfil
    sozinho ao abrir um jogo"* governa a troca automática POR JANELA. Quando o
    detector de janela está cego, essa troca **não acontece de jeito nenhum** —
    e a caixa passa a oferecer o congelamento de algo que já está parado.

    Até 07/09 quem dizia isso era a coluna **Atenção**, que saiu da aba por
    ordem dela. A frase era a única linha acesa da coluna na máquina dela, no
    instante em que a leva foi medida, e sem ela a tela oferece um controle sem
    dizer que ele não tem sobre o que agir.

    **A FONTE É A DA JANELA ANTIGA, e não uma frase nova**:
    `home_actions.texto_do_cadeado_cego`, palavra por palavra. Texto de tela é
    decisão dela; texto que ela já leu, não — a mesma regra que trouxe
    `CADEADO_ROTULO` e `CADEADO_DICA` para cá.

    **A AUSÊNCIA DA CHAVE CONTA COMO "NÃO SEI"**, e o dono já garante isso: um
    daemon mais velho não publica `window_detect_seeing`, e a função devolve
    `""` em vez de acender um aviso sobre um detector que ninguém leu. É a
    disciplina que os outros avisos desta aba seguem de propósito.

    **O MARCADOR NO LUGAR DO VAZIO** é `monta.NADA_A_DIZER`, pela razão que o
    bloco dos externos pagou em 06/09: `escrever()` troca valor vazio por `—`,
    e numa linha de ressalva isso vira um travessão solto — ruído com cara de
    dado. A `monta.ressalva` já nasce com esse marcador no desenho; a chave tem
    de devolvê-lo também, senão a PRIMEIRA pintura o substitui por um traço.
    """
    from hefesto_dualsense4unix.app.actions.home_actions import (
        texto_do_cadeado_cego,
    )

    return texto_do_cadeado_cego(state) or str(_monta().NADA_A_DIZER)


def _ressalva_da_mascara(state: dict[str, Any]) -> str:
    """A linha da máscara fora do modo jogo — ``""`` em TODO estado desde 13/09/2026.

    NOTA DATADA — 13/09/2026, JOGAR-A-FAIXA-QUE-PULA-01 §3.1. Até hoje ela
    devolvia `RESSALVA_DA_MASCARA` em Modo Nativo e na Navegação, e a frase era
    pintada a cada tique, até sem máscara nenhuma escolhida. A palavra dela
    sobre as frases de status — *"em todas as abas da interface"* (TELA-CALADA-01)
    — a tirou da tela. O FATO que ela dizia continua verdadeiro e continua com
    régua (`test_a01_a_mascara_vale_sempre_que_pode`): `gamepad.mask.set` grava
    sem gate de modo, e o chip do CARTÃO acende a escolha pelo `por_aparelho`
    do daemon (`ipc_handlers._mascaras_por_aparelho`). O argumento abaixo,
    *"esta tela deixava clicar e ficava calada"*, era de antes de o chip ser por
    controle (03/09): hoje é o chip que responde ao clique.

    ELA CONTINUA SENDO A DONA DA LINHA, e não um literal no `pacote()`: o
    endereço `mascara-ressalva` segue na página, e a frase volta mudando UMA
    função. O que vem abaixo é o raciocínio de 04/09, e fica como registro.

    A QUEIXA É DELA, e é a primeira da lista de 04/09: *"independente do modo a
    mascara deve funcionar ali sempre."*

    O QUE ELA SENTE, medido: fora do modo `gamepad` **não existe gamepad
    virtual**, e `mascara_efetiva` só é lida na criação de um
    (`gamepad.py:1736`). O clique é aceito, gravado no disco e não muda nada que
    se veja. A janela GTK escondia a caixa inteira fora do modo `gamepad`
    (`home_actions.py:1857`, `set_visible(modo_exibido == "gamepad")`); esta
    tela deixava clicar e ficava calada — que é
    pior, porque o silêncio se lê como defeito.

    **A ESCOLHA NÃO SE PERDE, e é isso que esta linha diz.** `gamepad.mask.set`
    grava sempre e `set_mask` persiste em `controller_masks.json`; quando o vpad
    nascer, ele nasce com a máscara que ela escolheu. Esconder a caixa como a
    GTK faz apagaria uma escolha que É possível fazer agora.

    QUEM RESPONDE PELO MODO É `painel.modo_vivo`, o ponto único de leitura — o
    mesmo que acende o interruptor. Comparar `native_mode` e
    `gamepad_emulation.enabled` aqui seria o terceiro leitor do modo nesta aba.

    A FRASE NÃO NOMEIA O MODO de propósito. São DOIS os modos sem vpad — o
    Nativo e a Navegação —, e na Navegação o interruptor está em **Ligado**
    (`painel.MODOS_LIGADOS` tem `gamepad` e `desktop`): uma frase que dissesse
    "ligue o Hefesto" mandaria ligar o que já está ligado.
    """
    return ""


# `TIQUE_MS = 100` e `pacote_da_pagina` roda SÍNCRONO no laço do GTK
#     _qual_jogo()        0,11 ms    os dois markers, só com a lista cheia
TTL_DO_STEAM_INPUT_S = 20.0

#: O VALOR QUE ACENDE O CHIP. É a `chave` do chip em `painel.CHIPS_DA_ESCADA`,
CHIP_DO_STEAM_INPUT = "steam"


class LinhaDaFileira(NamedTuple):
    """O que o clique num chip da fileira faz — uma linha de :func:`o_que_o_chip_faz`."""

    modo: str
    caminho: str | None
    steam_input: bool


def o_que_o_chip_faz(chave: str) -> LinhaDaFileira:
    """A TABELA DA FILEIRA — o dono único do que cada um dos quatro chips faz.

    O-MODO-QUE-NAO-SAI-DO-STEAM-INPUT-01, 23/09/2026, pela regra dela: *"fez
    errado a idea é eu poder escolher qualquer que seja o modo independnete da
    ordem."* A fileira é um grupo de rádio: clicar em qualquer chip deixa
    AQUELE aceso, vindo de qualquer outro, e clicar no aceso REAPLICA.

    | chip | modo | caminho | o jogo da vez no Steam Input |
    | --- | --- | --- | --- |
    | Sony DualSense | gamepad | dualsense | tira |
    | Xbox | gamepad | xbox | tira |
    | Steam Input | gamepad | dualsense | põe |
    | Navegação | desktop | — | tira |

    O QUE CADA CLIQUE FAZ NÃO DEPENDE DO CHIP DE ANTES — é a regra inteira. A
    primeira cura desta sprint perguntava de onde ela vinha (o «Xbox» só
    tirava o jogo da lista se o Steam Input estava aceso), e a fileira ficou
    dependente da ordem. «Xbox» e «Navegação» tiram o jogo porque, com ele na
    lista, a Steam pegaria o controle do jogo por baixo do chip aceso.

    A TABELA NÃO É DIGITADA: cada linha sai da `ponte` do chip em
    `painel.CHIPS_DA_ESCADA`. O caminho do Steam Input é o da ponte dele —
    `ESCADA[3]` é `Ponte(gamepad, dualsense, steam_input=True)`, o degrau que
    senta SOBRE o caminho DualSense —, e o `steam_input` é o terceiro termo da
    mesma ponte. Digitar ``"dualsense"`` aqui seria a segunda cópia de um valor
    que a escada já tem. Quem traduz a máscara da ponte em caminho é o dono da
    regra, `virtual_pad.caminho_resolvido` (*"sem escolha, o que sai da
    máscara"*), e não uma coincidência de nomes.
    """
    from hefesto_dualsense4unix.integrations.virtual_pad import caminho_resolvido

    chip = next((c for c in _painel().CHIPS_DA_ESCADA if c.chave == chave), None)
    if chip is None or chip.ponte is None:
        raise ValueError(f"modo: {chave!r} não é chip da fileira desta aba")
    ponte = chip.ponte
    if chip.modo:
        return LinhaDaFileira(str(chip.modo), None, bool(ponte.steam_input))
    return LinhaDaFileira(str(ponte.kind),
                          caminho_resolvido(chip.caminho, ponte.mascara),
                          bool(ponte.steam_input))


@dataclasses.dataclass(frozen=True)
class _DoSteamInput:
    """O que a TELA precisa saber sobre o Steam Input, e nada mais."""

    lista: frozenset[str] = frozenset()
    ligados: frozenset[str] = frozenset()
    pendentes: frozenset[str] = frozenset()
    frase: str = ""
    o_guarda_liga: bool = False


class _VigiaDoSteamInput:
    """Guarda a última leitura do disco e a refaz FORA da thread da janela."""

    def __init__(self) -> None:
        self._dado: _DoSteamInput | None = None
        self._quando = 0.0
        self._em_curso = False
        self._trava = threading.Lock()
        self._geracao = 0

    def agora(self) -> _DoSteamInput | None:
        """O que se sabe AGORA. Nunca bloqueia, nunca levanta."""
        if self._precisa():
            self._disparar()
        return self._dado

    def _precisa(self) -> bool:
        return not self._em_curso and (
            self._dado is None
            or (time.monotonic() - self._quando) > TTL_DO_STEAM_INPUT_S
        )

    def _disparar(self) -> None:
        with self._trava:
            if self._em_curso:
                return
            self._em_curso = True
        threading.Thread(
            target=self._corpo, name="hefesto-steam-input", daemon=True
        ).start()

    def _corpo(self) -> None:
        try:
            self.ler()
        except Exception:
            pass
        finally:
            self._em_curso = False

    def esquecer(self) -> None:
        """Invalida o cache — a próxima :meth:`agora` dispara a releitura."""
        self._quando = 0.0

    def renovar(self) -> None:
        """Relê AGORA — é o que o gesto faz depois de escrever. Nunca levanta."""
        with self._trava:
            self._geracao += 1
        try:
            self.ler()
        except Exception:
            self.esquecer()

    def ler(self) -> _DoSteamInput:
        """BLOQUEIA — lê o disco. Só de thread worker ou de gesto, nunca do tique."""
        geracao = self._geracao
        ponte = _ponte_do_steam_input()
        lista = ponte.ler_allowlist()
        if not lista:
            # precisa ser aberto para dizer isso. A frase continua sendo a do
            dado = _DoSteamInput(frase=ponte.Estado().frase())
        else:
            estado = ponte.estado_da_ponte(allowlist=lista)
            dado = _DoSteamInput(
                lista=frozenset(estado.lista),
                ligados=frozenset(estado.ligados),
                pendentes=frozenset(p.appid for p in estado.pendentes),
                frase=estado.frase(),
                o_guarda_liga=o_guarda_liga_o_steam_input(),
            )
        with self._trava:
            if geracao == self._geracao:
                self._dado = dado
                self._quando = time.monotonic()
        return dado


VIGIA_DO_STEAM_INPUT = _VigiaDoSteamInput()


def _ponte_do_steam_input() -> Any:
    """`integrations/steam_input_ponte` — o dono da ponte. Importado TARDE."""
    from hefesto_dualsense4unix.integrations import steam_input_ponte

    return steam_input_ponte


def _qual_jogo(state: dict[str, Any] | None) -> tuple[int | None, str]:
    """`(appid, "aberto"|"fechado")` — as TRÊS evidências, e ela NÃO é daqui."""
    from .a07_lancadores import a_escada_do_jogo

    return a_escada_do_jogo(state)


def _steam_input_da_tela(state: dict[str, Any]) -> str:
    """O chip «Steam Input» acende? — a ESCOLHA dela, e não o arquivo da Steam.

    | o que se sabe | como | a tela |
    | --- | --- | --- |
    | **LIGADO** | o jogo da vez está na lista dela **e** o vdf vivo diz
      diferente de `"0"` | chip aceso |
    | **PENDENTE** | na lista dela, e o vdf ainda diz `"0"` | chip **aceso**, e
      «Liga quando a Steam fechar» na faixa (:func:`_o_que_o_chip_diz`) |
    | **DESLIGADO** | não está na lista | chip apagado |
    | **NÃO SE SABE** | sem appid, ou a vigia ainda não voltou | chip apagado |

    FATO SUBSTITUÍDO — O-MODO-QUE-NAO-SAI-DO-STEAM-INPUT-01, 23/09/2026, pela
    regra dela. Aqui se dizia que o PENDENTE ficava apagado, porque acender ali
    seria a tela afirmando uma ponte que não está de pé (o `excecao_inerte` da
    PONTE-STEAM-INPUT-01). Na fileira que é grupo de rádio, o chip aceso é o que
    ela ESCOLHEU: com a Steam aberta o clique no «Steam Input» voltava apagado,
    e o «cliquei e nada acendeu» é a queixa dela. A ponte que ainda não subiu
    não some da tela — ela vai para a faixa, com a frase curta dela, e o
    guarda do vdf completa quando a Steam fechar.

    E O QUARTO NÃO É BURACO: acender um chip por padrão seria afirmar uma
    escolha que ninguém fez.

    A ESCOLHA É **POR JOGO**, e é ordem dela: *"setar o jogo pra funcionar
    usando os controladores da própria steam"*. A chave da Steam é indexada por
    appid (`UseSteamControllerConfig`), então um chip que acendesse para a
    MÁQUINA mentiria em 15 dos 16 jogos dela.
    """
    return (CHIP_DO_STEAM_INPUT
            if _o_jogo_na_lista(state, VIGIA_DO_STEAM_INPUT.agora())
            else "")


def _o_jogo_na_lista(state: dict[str, Any] | None,
                     dado: _DoSteamInput | None) -> str:
    """O appid do jogo da vez se ele está na lista do Steam Input — `""` se não.

    UM ALVO SÓ PARA ACENDER E PARA CLICAR — O-MODO-QUE-NAO-SAI-DO-STEAM-INPUT-01,
    23/09/2026: o jogo da vez de `a_escada_do_jogo`, ABERTO OU FECHADO. É o
    mesmo que :func:`_o_clique_da_fileira` põe ou tira da lista.

    FATO SUBSTITUÍDO: a primeira cura desta sprint (22/09) só acendia para o
    jogo ABERTO e gravava para o fechado. Era a assimetria do «cliquei e nada
    acendeu»: com o jogo fechado, clicar no «Steam Input» gravava a lista e a
    tela continuava no «Sony DualSense».
    """
    if dado is None or not dado.lista:
        return ""
    appid, _quando = _qual_jogo(state)
    if appid is None:
        return ""
    return str(appid) if str(appid) in dado.lista else ""


def _a_ponte_que_falta(state: dict[str, Any] | None) -> str:
    """A frase do dono quando o jogo da vez está na lista e o vdf ainda não."""
    dado = VIGIA_DO_STEAM_INPUT.agora()
    if dado is None or not dado.pendentes:
        return ""
    appid, _quando = _qual_jogo(state)
    if appid is None or str(appid) not in dado.pendentes:
        return ""
    return dado.frase


def _unidade_do_guarda() -> str:
    from hefesto_dualsense4unix.app.actions.daemon_actions import (
        GUARDA_STEAM_INPUT_TIMER,
    )

    return GUARDA_STEAM_INPUT_TIMER.rsplit(".", 1)[0]


def o_guarda_liga_o_steam_input() -> bool:
    """O vigia do vdf vai ligar (e desligar) o Steam Input quando a Steam fechar?"""
    import os

    from hefesto_dualsense4unix.daemon.service_install import user_unit_dir

    try:
        base = _unidade_do_guarda()
        pasta = user_unit_dir()
        texto = (pasta / f"{base}.service").read_text(encoding="utf-8")
        habilitado = any(os.path.lexists(pasta / quer / f"{base}.{tipo}")
                         for quer, tipo in (("default.target.wants", "path"),
                                            ("timers.target.wants", "timer")))
    except Exception:
        return False
    liga = any(linha.startswith("ExecStart=") and "disable_steam_input.sh" in linha
               and "--apply-quiet" in linha for linha in texto.splitlines())
    return liga and habilitado


STEAM_INPUT_ESPERA = "Liga quando a Steam fechar"


def _o_que_o_chip_diz(state: dict[str, Any] | None, tela: dict[str, str]) -> str:
    """A faixa de baixo com a frase dela — `""` quando o chip não está esperando."""
    if tela.get("steam-input-aceso") != CHIP_DO_STEAM_INPUT:
        return ""
    if not _a_ponte_que_falta(state):
        return ""
    dado = VIGIA_DO_STEAM_INPUT.agora()
    if dado is None or not dado.o_guarda_liga:
        return ""
    from hefesto_dualsense4unix.app.actions.relancar import MARCADOR_PENDENTE

    return f"{MARCADOR_PENDENTE} {STEAM_INPUT_ESPERA}"


def _a_fileira_com_a_mesa(tela: dict[str, str], mesa: list[dict[str, Any]]) -> dict[str, str]:
    """SEM CONTROLE NA MESA, NENHUM BOTÃO DO MODO ACENDE — 22/09/2026.

    Pedido dela, olhando a aba sem controle nenhum e o «Steam Input» aceso:
    *"ligado mesmo sem controle"*. O daemon continua dizendo o caminho, e a
    lista dela continua dizendo Steam Input para o último jogo — mas o Modo é o
    caminho de UM CONTROLE até o jogo, e sem controle não há caminho em uso.
    Acender o «Sony DualSense» no lugar seria o mesmo botão aceso sobre nada.

    O INTERRUPTOR FICA: `Ligado` é o serviço, que está de pé com ou sem
    controle. E `_estado_da_tela` continua respondendo sobre o DAEMON; quem
    decide que a tela cala é esta função, que é quem conhece a mesa.
    """
    if mesa:
        return tela
    return {**tela, "modo-aceso": "", "steam-input-aceso": ""}


def _estado_da_tela(state: dict[str, Any]) -> dict[str, str]:
    """A POSIÇÃO DO INTERRUPTOR e o CHIP ACESO — os dois lidos, nunca cravados.

    É o defeito de maior alcance desta aba, e ele foi fotografado: com o daemon
    dela em ``native_mode false`` e ``gamepad_emulation.enabled false`` — logo
    `mode_of_state` = **desktop** — a página mostrava o interruptor em
    **Ligado** e o chip **Sony DualSense** aceso, porque nem o rótulo do
    interruptor nem os chips da fileira tinham endereço: o que estava na tela
    era o que o gerador cravou em 31/08 e mais nada o repintava.

    OS DOIS LEITORES SÃO DO PRODUTO e não se reescrevem:

    * `painel.hefesto_ligado` — ``True`` Ligado · ``False`` Desligado · ``None``
      não se sabe. Ele é DERIVADO de propósito (Ligado é ``gamepad`` **ou**
      ``desktop``): comparar um botão só deixaria a tela muda na Navegação, e
      mudo é pior que errado porque parece defeito;
    * `painel.caminho_vivo` — o CAMINHO que o daemon publica
      (`gamepad_emulation.caminho`), e ``None`` quando não dá para saber.

    O CHIP ACESO É O INVERSO DO `_plano_do_chip`, e sai da MESMA tabela
    (`painel.CHIPS_DA_ESCADA`): um chip com ``modo`` é um modo do produto (a
    **Navegação**), os outros são CAMINHOS do modo ``gamepad``. Escrever aqui um
    ``if chave == "dualsense"`` seria a segunda cópia de uma tradução que já tem
    dono — a mesma que o gesto usa para o caminho de ida.

    FATO SUBSTITUÍDO — MODO-DE-CONEXAO-01, 13/09/2026: o chip acendia pela
    MÁSCARA (`home_actions.mascara_do_aparelho`), e ela mentia com máscara no
    cartão — no `uinput` ela cai no `flavor` da sessão, e com o cartão do P1 em
    Xbox 360 o «Sony DualSense» ficava aceso. O chip de modo não lê a máscara.

    FATO SUBSTITUÍDO — STEAM-INPUT-01, 20/09/2026. Aqui se dizia que *"o Steam
    Input NUNCA ACENDE: ele não tem caminho (`Chip.caminho` é `None`), e não há
    IPC que o diga"*. A primeira metade continua verdadeira e é o desenho (§4.1
    da sprint: o `caminho` escolhe o CANAL do vpad, e o Steam Input senta EM
    CIMA do canal DualSense em vez de ser um terceiro); a segunda caiu — quem o
    diz não é IPC nenhum, é o `localconfig.vdf` contra a lista dela, e o leitor
    é `ponte.estado_da_ponte`, read-only e capaz de rodar com a Steam aberta.
    Ele acende por :func:`_steam_input_da_tela`, em CAMPO PRÓPRIO, e a razão de
    não compartilhar o `modo-aceso` está em :data:`DA_PAGINA`.

    DAEMON CALADO NÃO PINTA NADA, e esta é a armadilha desta função: `mode_of_
    state({})` devolve **desktop** — ele só devolve ``None`` para um
    não-dicionário —, então pintar sem esta guarda acenderia **Ligado** sobre um
    estado que ninguém leu. É a mesma guarda que `_pendencia` já tinha de ter, e
    pela mesma razão.
    """
    if not state:
        return {"hef-posicao": "", "modo-aceso": "", "steam-input-aceso": ""}

    ligado = _painel().hefesto_ligado(state)
    aceso = _chip_do_caminho(state)

    # da escada (`ponte_escada.ESCADA[3]`: gamepad + DualSense + Steam Input), e
    # e o «Sony DualSense» apaga. Sobre o Xbox ou na Navegação o degrau 4 não
    steam = ""
    sob = o_que_o_chip_faz(CHIP_DO_STEAM_INPUT)
    embaixo = o_que_o_chip_faz(aceso) if aceso else None
    if embaixo is not None and (embaixo.modo, embaixo.caminho) == (sob.modo, sob.caminho):
        steam = _steam_input_da_tela(state)
    if steam:
        aceso = ""
    return {
        "hef-posicao": "" if ligado is None else ("ligado" if ligado else "desligado"),
        "modo-aceso": aceso,
        "steam-input-aceso": steam,
    }


def _chip_do_caminho(state: dict[str, Any]) -> str:
    """A chave do chip que o modo e o caminho VIVOS acendem, sem o Steam Input.

    É o inverso de :func:`o_que_o_chip_faz`, lido da MESMA tabela: o chip cujo
    modo é o modo vivo e cujo caminho é o caminho vivo (a Navegação não
    escolhe caminho). O Steam Input fica de fora porque ele não é um caminho
    — senta sobre o do «Sony DualSense» —, e quem diz se ele está de pé é a
    lista (:func:`_estado_da_tela`). `""` quando nenhum casa: o Nativo, ou um
    caminho que o daemon não publicou.
    """
    painel = _painel()
    modo = painel.modo_vivo(state)
    caminho = painel.caminho_vivo(state)
    for chip in painel.CHIPS_DA_ESCADA:
        linha = o_que_o_chip_faz(str(chip.chave))
        if linha.steam_input or linha.modo != modo:
            continue
        if linha.caminho is None or linha.caminho == caminho:
            return str(chip.chave)
    return ""


def _mascara_da_sessao(state: dict[str, Any] | None) -> str | None:
    """A máscara do PROCESSO — a herança de quem não escolheu, e nada mais.

    Um degrau só, e ele existe para que `pacote()` não importe `home_actions`
    no meio do laço dos cartões. O leitor continua sendo o do produto; esta
    função não decide nada.
    """
    if not state:
        return None
    from hefesto_dualsense4unix.app.actions.home_actions import mascara_do_aparelho

    return mascara_do_aparelho(state)


def _mascara_do_cartao(casa: dict[str, Any], da_sessao: str) -> str:
    """A máscara DAQUELE aparelho, na palavra do desenho — ``""`` quando não há.

    O DONO DO VALOR É A MESA, e ela já o resolveu: `mesa_viva.mesa_do_estado` lê
    `gamepad_emulation.por_aparelho` (o `{uniq: máscara efetiva}` que o daemon
    publica desde 03/09) e cai na máscara da sessão para quem não escolheu —
    que é a regra de herança do `external_mask`, escrita uma vez, lá. Reler o
    ``state`` aqui seria a segunda cópia dessa regra, e a de cá envelheceria no
    dia em que a herança mudasse.

    O FILTRO É `NOME_DA_MASCARA`, e não uma lista digitada: só passa o que a
    tela sabe nomear, e é o que impede o travessão da mesa vazia de virar um
    rótulo. NOTA DATADA — 07/09/2026: este parágrafo dizia que o filtro *"mantém o
    Nintendo Pro apagado, porque o produto não sabe montá-lo"*. O produto sabe
    desde hoje; o filtro continua igual e agora deixa o rótulo passar, que é o
    comportamento que ele sempre teve para máscara que existe.

    Sem correspondência a resposta é ``""``, e o alvo `classe` apaga os três
    chips: campo sem informação não mostra nada.
    """
    from hefesto_dualsense4unix.interface.mesa_viva import NOME_DA_MASCARA

    rotulo = str(casa.get("mascara") or "")
    if rotulo in set(NOME_DA_MASCARA.values()):
        return rotulo
    return da_sessao if not rotulo or rotulo not in _MASCARAS_DESENHADAS() else ""


def _MASCARAS_DESENHADAS() -> set[str]:  # noqa: N802  (é uma constante lida tarde)
    """Os rótulos que o DESENHO tem, do dono deles (`monta.MASCARAS`).

    Existe para separar duas ausências que se pareciam: um rótulo que ESTÁ na
    tela e o produto não sabe montar (resposta ``""``, o chip fica apagado e
    isso é a verdade) de uma mesa que simplesmente não falou de máscara
    (resposta: a da sessão, que é o que valia antes).

    NOTA DATADA — 07/09/2026: o exemplo do primeiro caso era o **Nintendo Pro**, e ele
    deixou de servir de exemplo — a máscara existe. A separação continua
    valendo; o que falta é um rótulo que a ilustre, e não haver nenhum hoje é
    um estado do catálogo, não um defeito desta função.
    """
    import monta

    return set(monta.MASCARAS)


def _rotulo_da_mascara(mascara: str | None) -> str:
    """A máscara do produto na palavra do DESENHO — ``""`` quando não há."""
    from hefesto_dualsense4unix.integrations import ponte_escada

    return {
        ponte_escada.MASCARA_DUALSENSE: "DualSense",
        ponte_escada.MASCARA_XBOX: "Xbox 360",
    }.get(str(mascara or ""), "")


#:     ● Vai mudar para **Sony DualSense** quando você clicar em **Aplicar**
#: e, na MESMA foto, o chip **Sony DualSense** já estava aceso na fileira Modo.
#: 1. **"Vai mudar para Sony DualSense"** é tautologia. O gerador deriva a
#:    SEGUNDO ramo (`_aplicar_escolha_pendente` → `apply_mode`), que guarda a
#: que ela pediu — e é justamente aí que a tela estava MUDA. `_aplicar` não
_ESCOLHA: dict[str, str] = {}
#: o desenho. O `painel.CHIPS_DA_ESCADA` é a rede de segurança, e a chave crua é
_ROTULO: dict[str, str] = {}


def _lembrar(campo: str, valor: str, rotulo: str) -> None:
    """Anota o que ela acabou de pedir. Escritor ÚNICO dos dois dicionários."""
    if not valor:
        return
    _ESCOLHA[campo] = valor
    _ROTULO[campo] = rotulo or _rotulo_de(campo, valor)


#: teto dela é 2,0 s, e o «Sony DualSense» das 01:43 de 29/09 trocou os quatro
#: (`Daemon.gravar_o_modo_escolhido`), com ou sem a resposta chegar aqui a


def _rotulo_de(campo: str, valor: str) -> str:
    """A palavra aprovada por ela para aquela chave, sem passar pela tela.

    Rede de segurança para quando o clique não trouxe `texto` (um dublê de
    régua, um botão que a pintura trocou no meio). Sai de
    `painel.CHIPS_DA_ESCADA`, que é o dono dos rótulos da fileira — digitá-los
    aqui seria a segunda cópia da palavra dela.
    """
    if campo == "caminho":
        for chip in _painel().CHIPS_DA_ESCADA:
            if chip.caminho == valor:
                return str(chip.rotulo)
    return valor


def _pendencia(state: dict[str, Any]) -> dict[str, str]:
    """O que ela pediu MENOS o que o daemon já alcançou. Devolve o que sobra.

    A REGRA NÃO SE REESCREVE: `home_actions.reconciliar_pendente` é a dona dela
    desde a AGORA-E-DEPOIS-01, e a frase que a define está lá — *"uma pendência
    só existe enquanto DIVERGE do vigente"*. Ela lê tudo por `getattr`, então
    serve a qualquer objeto: aqui vai um `SimpleNamespace`, porque esta
    interface não tem uma `janela` onde pendurar a escolha.

    AS DUAS PONTAS TAMBÉM TÊM DONO: o modo vivo é `mode_transition.mode_of_state`
    (o mesmo que acende o interruptor) e a máscara viva é
    `home_actions.mascara_do_aparelho` — que sabe a diferença entre a máscara
    EXPLÍCITA e a deduzida do `backend`, e devolve `None` quando não dá para
    saber. Comparar contra um `None` não apaga pendência nenhuma, que é o
    comportamento certo: não saber não é ter alcançado.

    DAEMON CALADO NÃO RECONCILIA. É o ramo `visivel=False` do
    `home_actions.render_pendente`: *"sem daemon não há como aplicar, mas o que
    ela decidiu não pode evaporar por causa de um engasgo de IPC"*. Sem isto o
    `mode_of_state({})` devolveria `desktop` — ele só devolve `None` para um
    não-dicionário — e um pedido de Navegação seria dado por cumprido por um
    tique sem resposta.
    """
    if not state:
        return dict(_ESCOLHA)
    from types import SimpleNamespace

    from hefesto_dualsense4unix.app.actions.home_actions import (
        mascara_do_aparelho,
        reconciliar_pendente,
    )
    from hefesto_dualsense4unix.app.actions.mode_transition import mode_of_state

    lembrete = SimpleNamespace(
        _escolha_pendente=dict(_ESCOLHA) or None,
        _modo_vigente_do_daemon=mode_of_state(state),
        _caminho_vigente_do_daemon=_painel().caminho_vivo(state),
        _mascara_vigente_do_daemon=mascara_do_aparelho(state),
    )
    sobra: dict[str, str] = dict(reconciliar_pendente(lembrete) or {})
    _ESCOLHA.clear()
    _ESCOLHA.update(sobra)
    for campo in [c for c in _ROTULO if c not in sobra]:
        del _ROTULO[campo]
    return sobra


def _faixa_do_pendente(state: dict[str, Any]) -> tuple[str, str]:
    """`(frase, alvo)` da faixa laranja — `("", "")` quando não há pendência.

    A FRASE É DO PRODUTO: `relancar.texto_do_pendente` é função pura (zero GTK,
    zero import além do `typing`) e é a MESMA que a janela estável escreve na
    linha do pendente. O marcador `●` vem de lá também
    (`relancar.MARCADOR_PENDENTE`).

    A MAIÚSCULA É REGRA DESTA LINHA, e é dela — 28/08/2026, e o comentário do
    gerador a guarda: *"o `●` que vem antes é MARCADOR, não palavra: a frase
    começa aqui"*. A janela estável escreve a mesma frase em minúscula porque lá
    ela é um rótulo no meio de outros; aqui é a linha inteira, isolada na caixa
    tracejada. É a única coisa que este arquivo faz com o texto do produto, e
    fazê-la aqui é o que evita uma segunda cópia da frase.

    O VAZIO É `""` DE PROPÓSITO: o piloto escreve `—` no lugar de um valor vazio
    (`hefesto_vivo.BOOTSTRAP`, `escrever`), que é a palavra desta casa para *"não
    há"* — a mesma de `painel.SEM_LEITOR`. Só que uma faixa tracejada com um
    travessão solto não diz "nada pendente": diz que alguma coisa faltou, e foi
    o que se fotografou em 02/09. Por isso, desde 03/09, quem some é a CAIXA
    inteira, por `pendente-ha` (alvo `classe`, na `.faixa-final`) — e some por
    `visibility`, não por `display`: o espaço dela é reservado para a tela não
    pular, que é queixa dela e é promessa escrita na legenda desta aba.

    O `pendente-alvo` MORRE NA PRIMEIRA PINTURA, e isto fica escrito porque é
    medido: o `<b>` dele está DENTRO do `<div data-campo="pendente">`, e o alvo
    padrão do piloto é `textContent` — escrever a frase apaga os filhos. A TELA
    NÃO MENTE POR ISSO: a frase inteira já nomeia o alvo, e é a mesma função do
    produto que a escreve. O que se perde é o ENDEREÇO, que deixa de existir no
    DOM depois do primeiro tique. Curá-lo pede uma de duas coisas, e nenhuma é
    desta aba sozinha: um alvo de pintura que escreva TRECHO de um nó (é do
    piloto), ou o desenho parar de repetir o alvo dentro da frase (é dela).

    A PONTE DO STEAM INPUT QUE AINDA NÃO SUBIU ENTRA AQUI — O-MODO-QUE-NAO-SAI-
    DO-STEAM-INPUT-01, 23/09/2026. O chip acende pela escolha dela, e o que
    falta aplicar é pendência como o caminho que o daemon ainda não alcançou: a
    frase é a do dono (:func:`_a_ponte_que_falta`), depois da do modo.
    """
    from hefesto_dualsense4unix.app.actions.relancar import (
        MARCADOR_PENDENTE,
        texto_do_pendente,
    )

    sobra = _pendencia(state)
    da_ponte = _a_ponte_que_falta(state)
    marca = f"{MARCADOR_PENDENTE} "
    if not sobra:
        return (marca + da_ponte, _rotulo_do_chip(CHIP_DO_STEAM_INPUT)) if da_ponte else ("", "")
    rotulos = [_ROTULO.get(c, sobra[c])
               for c in ("modo", "caminho", "mascara") if c in sobra]
    eixo_do_modo = next((c for c in ("modo", "caminho") if c in sobra), None)
    frase = texto_do_pendente(
        modo=(_ROTULO.get(eixo_do_modo, sobra[eixo_do_modo])
              if eixo_do_modo else None),
        mascara=(_ROTULO.get("mascara", sobra.get("mascara"))
                 if "mascara" in sobra else None),
    )
    if frase.startswith(marca):
        resto = frase[len(marca):]
        frase = marca + resto[:1].upper() + resto[1:]
    if da_ponte:
        frase = f"{frase} {da_ponte}"
        rotulos.append(_rotulo_do_chip(CHIP_DO_STEAM_INPUT))
    return frase, ", ".join(rotulos)


def _rotulo_do_chip(chave: str) -> str:
    """A palavra aprovada por ela para o chip, de `painel.CHIPS_DA_ESCADA`."""
    return next((str(c.rotulo) for c in _painel().CHIPS_DA_ESCADA
                 if c.chave == chave), chave)


_PENDENCIA_RELATADA = ""


def _relatar_a_pendencia(frase: str) -> None:
    """Leva a pendência ao diário da janela — e não mais à tela."""
    global _PENDENCIA_RELATADA
    if frase == _PENDENCIA_RELATADA:
        return
    _PENDENCIA_RELATADA = frase
    if frase:
        print(f"[relato] {PAGINA} · pendente: {frase}", file=sys.stderr)


# tela. Quem a possui é `app/actions/mode_transition.plan_mode_transition`,
#     painel.plano_do_modo(chave, mascara) -> [(metodo, params), ...]  # (noqa-acento) id
# digitada: sai de `painel.CHIPS_DA_ESCADA`, que é onde a casa guarda qual ponte
from . import gesto  # noqa: E402

BOTOES_SEM_DONO: dict[str, str] = {}

#: próprio arquivo já dizia o contrário trinta linhas adiante: `gamepad.mask.set`
#: tique — e este trazia `gamepad.mask.set` e `uniq` na frase. Como comentário
#:   `gamepad.mask.set` recebe `uniq` e o gesto `mascara` tem dono desde


def _painel() -> Any:
    """`app/actions/jogar/painel` — o dono das perguntas desta aba."""
    from hefesto_dualsense4unix.app.actions.jogar import painel

    return painel


def _plano(
    chave: str, mascara: str | None = None, caminho: str | None = None
) -> list[tuple[str, dict[str, Any]]]:
    """A sequência de IPC daquele modo — DELEGADA, sem uma linha de regra aqui."""
    painel = _painel()
    plano: list[tuple[str, dict[str, Any]]] | None = painel.plano_do_modo(
        chave, mascara, **({"caminho": caminho} if caminho else {}))
    if plano is None:
        raise RuntimeError(painel.porque_nao_aplica(chave))
    return plano


def _aplicar(p: Any, plano: list[tuple[str, dict[str, Any]]]) -> bool:
    """Despacha o plano na ORDEM, pelo degrau 3 da ponte."""
    confirmou = True
    for metodo, params in plano:
        if not p.chamar(metodo, **params):
            confirmou = False
    return confirmou


MODO_SEM_CONFIRMACAO = (
    "O Hefesto demorou a responder, e a troca pode não ter acontecido. Se o "
    "botão não acender, clique de novo."
)


def _dizer_se_nao_confirmou(confirmou: bool) -> None:
    """Levanta com :data:`MODO_SEM_CONFIRMACAO` quando `_aplicar` voltou falso."""
    if not confirmou:
        raise RuntimeError(MODO_SEM_CONFIRMACAO)


#: daquele conjunto têm teto próprio e declarado: `gamepad.mask.set` (2,0 s, e
#: «Xbox» dela no `interface.log` de 22/09 — `modo-xbox → aplicado`, depois
ACHADO_DO_TIMEOUT = (
    "ponte.TETOS dá 2,0 s aos cinco métodos desta aba, o mesmo valor de "
    "mode_transition.MODE_IPC_TIMEOUT_S; o teto de 250 ms é só o dos métodos "
    "fora da tabela."
)


@gesto("01-jogar.html", "hefesto",
       grava="o modo no perfil ativo, pelo native.mode.set e pelo "
             "gamepad.emulation.set à mão (o daemon grava)")
def hefesto(ctx: Contexto, o: dict[str, Any], p: Any) -> None:
    """O INTERRUPTOR: Ligado (`gamepad`) ou Desligado (`native`).

    QUAL POSIÇÃO É O `data-modo` do rótulo clicado, e ele chega em `o["modo"]`
    já — o mesmo endereço que a pintura viva usa para acender a posição a partir
    de `mode_of_state`. Um segundo atributo só para o clique faria a tela ter um
    endereço para ler e outro para escrever.

    **"Desligado" É O MODO NATIVO, e não "parar o Hefesto"** — decisão dela,
    31/08/2026: *"o modo nativo já existe ali (…) e se eu quiser desligar modo
    hefesto clico em desligado e o modo nativo fica online."* **Parar** o serviço
    continua sendo só a aba Sistema: este gesto nunca chama `daemon.pause` nem
    manda `stop` a coisa nenhuma.

    **LIGADO PASSOU A LIGAR O SERVIÇO TAMBÉM — decisão dela, 03/09/2026:**
    *"Adiciona essa função extra quando clicar em ligar. E em sistema um
    específico pra parar o Daemon E Ativar o Daemon (sendo que em jogar também
    consegue isso)."*

    E ELE VEM ANTES DO PLANO, não depois, porque sem o daemon de pé não há a
    quem mandar: os três IPCs deste gesto atravessam a ponte, e com o serviço
    parado a ponte não tem socket. A ordem inversa recusaria o clique e deixaria
    o serviço parado — o gesto falhando exatamente no caso que ela pediu que
    passasse a funcionar.

    O ATO NÃO É REESCRITO AQUI: `a09_sistema.ativar_o_servico()` é o mesmo que o
    botão "Ativar o serviço" da aba Sistema aciona, com o `_user_stopped_daemon`
    desarmado junto — sem ele o `ensure_daemon_running` volta a matar o daemon
    na próxima abertura da janela por um caminho e não pelo outro. Duas cópias
    deste ato é como as duas se afastariam.

    SÓ NAS POSIÇÕES **LIGADAS**, e quem diz quais são é o produto
    (`painel.MODOS_LIGADOS`): o `gamepad` e o `desktop` são o Hefesto no meio; o
    `native` é ele fora do meio. Ligar o serviço no clique do "Desligado" seria
    subir o que ela acabou de mandar sair da frente.
    """
    if str(o.get("modo") or "") in _painel().MODOS_LIGADOS:
        from . import a09_sistema

        a09_sistema.ativar_o_servico()
    return _hefesto_o_modo(ctx, o, p)


def _hefesto_o_modo(ctx: Contexto, o: dict[str, Any], p: Any) -> None:
    """O interruptor propriamente dito: o plano do modo, e a anotação da faixa."""
    chave = str(o.get("modo") or "")
    if not chave:
        raise ValueError(
            "hefesto: o clique não disse qual posição do interruptor — o "
            "`data-modo` do rótulo não chegou")
    confirmou = _aplicar(p, _plano(chave))
    _lembrar("modo", chave, str(o.get("texto") or ""))
    _dizer_se_nao_confirmou(confirmou)


def _plano_do_chip(chave: str) -> list[tuple[str, dict[str, Any]]]:
    """A sequência daquele chip da fileira — o modo e o CAMINHO saem da tabela.

    Quem diz qual modo e qual caminho cada chip escolhe é :func:`o_que_o_chip_faz`,
    que os lê de `painel.CHIPS_DA_ESCADA`. Digitar `"dualsense"` aqui seria a
    segunda cópia de um valor que já tem dono.

    DOIS EIXOS, e a diferença é a que `painel` documenta: a **Navegação** É um
    modo do produto e vai por ele; os outros são CAMINHOS do mesmo modo
    `gamepad`, e vão pelo `caminho` do plano — o «Steam Input» também, com o
    caminho sobre o qual o degrau 4 senta (O-MODO-QUE-NAO-SAI-DO-STEAM-INPUT-01,
    23/09/2026). Sem ele, o «Steam Input» clicado vindo do «Xbox» mexia só na
    lista, e o «Xbox» continuava aceso.

    FATO SUBSTITUÍDO — MODO-DE-CONEXAO-01, 13/09/2026: o plano levava a MÁSCARA
    da ponte do chip (`flavor`), que no daemon é só o padrão da máscara — com
    máscara no cartão do P1 o daemon respondia `ja_estava` e o piloto escrevia
    «aplicado» sobre nada. A máscara não sai mais daqui.
    """
    from hefesto_dualsense4unix.app.actions.mode_transition import MODE_GAMEPAD

    linha = o_que_o_chip_faz(chave)
    if linha.modo != MODE_GAMEPAD:
        return _plano(linha.modo)
    if not linha.caminho:
        raise RuntimeError(BOTOES_SEM_DONO.get(f"modo-{chave}", "sem dono no produto"))
    return _plano(MODE_GAMEPAD, caminho=linha.caminho)


def _lembrar_do_chip(chave: str, o: dict[str, Any]) -> None:
    """Anota o que o chip clicado pediu, no EIXO dele — e só nele.

    UM CHIP MEXE NUM EIXO SÓ, e é o que o `_plano_do_chip` já diz: a Navegação
    **é** um modo, os outros são CAMINHOS do mesmo modo `gamepad`. Anotar
    `modo=gamepad` junto com o caminho poria na faixa a palavra do CHIP
    ("Xbox") sob o rótulo do INTERRUPTOR ("Ligado") — duas coisas com nomes
    diferentes na tela dela, coladas numa linha só.

    FATO SUBSTITUÍDO — MODO-DE-CONEXAO-01, 13/09/2026: o chip anotava a MÁSCARA
    no campo `"mascara"`, comparado com a máscara viva — com o cartão do P1 em
    DualSense, «● Vai mudar para: Xbox» nunca sumia. Ele anota o `"caminho"`.

    Qual eixo é de cada chip sai de :func:`o_que_o_chip_faz`, e não de um `if`
    por nome: é o mesmo lugar de onde `_plano_do_chip` tira o caminho.
    """
    from hefesto_dualsense4unix.app.actions.mode_transition import MODE_GAMEPAD

    try:
        linha = o_que_o_chip_faz(chave)
    except ValueError:
        return
    # «Sony DualSense», e a rede de `_rotulo_de` nomearia o vizinho na faixa.
    rotulo = str(o.get("texto") or "") or _rotulo_do_chip(chave)
    if linha.modo != MODE_GAMEPAD:
        _lembrar("modo", linha.modo, rotulo)
        return
    if linha.caminho:
        _lembrar("caminho", linha.caminho, rotulo)


def _o_clique_da_fileira(ctx: Contexto, o: dict[str, Any], p: Any,
                         chave: str) -> dict[str, Any] | None:
    """O CLIQUE NUM CHIP DO MODO — os quatro gestos passam por aqui, e só por aqui."""
    from hefesto_dualsense4unix.app.actions.daemon_actions import (
        format_game_broken_result,
    )
    from hefesto_dualsense4unix.integrations import steam_launch_options as slo

    from .a07_lancadores import METODO_DA_RECARGA

    linha = o_que_o_chip_faz(chave)
    _desarmar_o_chip()
    appid, _quando = _qual_jogo(ctx.state)
    if linha.steam_input and appid is None:
        raise RuntimeError(str(format_game_broken_result(status="sem_jogo")))

    confirmou = _aplicar(p, _plano_do_chip(chave))
    _lembrar_do_chip(chave, o)

    recado = ""
    if appid is not None:
        alvo = str(appid)
        if linha.steam_input:
            status = slo.add_appid_to_steam_input_allowlist(alvo, nota=NOTA_DA_ESCOLHA)
        else:
            status = slo.remove_appid_from_steam_input_allowlist(alvo)
        if status in ("appid_invalido", "erro"):
            raise RuntimeError(str(format_game_broken_result(status=status, appid=alvo)))
        if status != "nao_estava":
            p.chamar(METODO_DA_RECARGA)
            try:
                recado = _reconciliar_o_vdf(alvo, linha.steam_input)
            finally:
                VIGIA_DO_STEAM_INPUT.renovar()

    _dizer_se_nao_confirmou(confirmou)
    # `{"recado": ""}` pousaria uma caixa verde VAZIA sobre a fileira.
    return {"recado": recado} if recado else None


@gesto("01-jogar.html", "modo-dualsense",
       grava="o caminho no perfil ativo, pelo gamepad.emulation.set à mão "
             "(o daemon grava)")
def modo_dualsense(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any] | None:
    """"Sony DualSense": o Hefesto entrega o controle pelo canal do DualSense.

    É o CAMINHO `uhid` — o relatório do DualSense, por onde voltam do jogo
    gatilho, luz e LED de jogador —, e ele é o PRIMEIRO degrau que o produto
    tenta, `ponte_escada.ESCADA[0]`. A razão está contada no cabeçalho de lá:
    **dez** linhas do `mapa-controles.csv` só chegam ao jogo por `uhid`.

    O modo continua sendo `gamepad`: o que muda entre este chip e o "Xbox" é o
    CAMINHO, não o modo nem a máscara. A máscara é do cartão de cada controle
    (MODO-DE-CONEXAO-01, 13/09/2026): com máscara Xbox 360 no cartão este
    caminho fica escolhido e aceso, e o aparelho sai no canal comum — o `uhid`
    só se constrói com máscara DualSense (`virtual_pad.quer_uhid`).

    E TIRA O JOGO DA VEZ DO STEAM INPUT — a linha dele em
    :func:`o_que_o_chip_faz`; o clique é :func:`_o_clique_da_fileira`.
    """
    return _o_clique_da_fileira(ctx, o, p, "dualsense")


@gesto("01-jogar.html", "modo-xbox",
       grava="o caminho no perfil ativo, pelo gamepad.emulation.set à mão "
             "(o daemon grava)")
def modo_xbox(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any] | None:
    """"Xbox": o canal comum, o do controle de Xbox — o SEGUNDO que o Hefesto tenta.

    ESTE CHIP NASCEU EM 31/08/2026 E É UMA DÍVIDA PAGA: `Ponte(gamepad, xbox)` é
    degrau da `ESCADA` desde 19/08 e **nenhum chip o nomeava** — era o que a
    conferência da escada contra a tela denunciava. A escada automática passava por ele
    e a tela não tinha onde mostrá-lo.

    É o CAMINHO `uinput` (MODO-DE-CONEXAO-01, 13/09/2026), e ele NÃO escolhe a
    máscara: com o cartão do P1 em DualSense o jogo continua vendo o DualSense,
    agora pelo canal comum. Até 13/09 este chip mandava a máscara Xbox 360, e com
    máscara no cartão dizia «aplicado» sem mudar nada — a queixa dela.

    E TIRA O JOGO DA VEZ DO STEAM INPUT, venha ela de onde vier — com ele na
    lista, a Steam pegaria o controle do jogo por baixo do «Xbox» aceso. Ver
    :func:`o_que_o_chip_faz`.
    """
    return _o_clique_da_fileira(ctx, o, p, "xbox")


#     steam_launch_options.add_appid_to_steam_input_allowlist  a vontade dela
#     steam_launch_options.with_steam_closed                 fechar e reabrir
NOTA_DA_ESCOLHA = "escolhido na aba Jogar: usar os controles da própria Steam"

def _o_que_o_vdf_diz(alvo: str) -> str | None:
    """O `UseSteamControllerConfig` do appid na árvore VIVA, relido do zero.

    **O VEREDITO É O ARQUIVO** — regra que a HONESTIDADE-STEAM-01 deixou, e que
    a aba 07 já aplica ao desligar: o `rc` de uma escrita pode ser 0 e o valor
    não ter mudado. Depois de escrever, esta função abre o vdf de novo e diz o
    que ficou lá; é ela que separa o recado VERDE da recusa.

    `None` = o produto não sabe: nenhum vdf legível, árvore viva não provada, ou
    o jogo não está neste vdf. Nunca `"0"` por omissão — *ausência é resposta*,
    e responder "desligado" sobre o que não se leu é a forma de defeito que esta
    casa mede toda semana.
    """
    ponte = _ponte_do_steam_input()
    from hefesto_dualsense4unix.integrations import steam_launch_options as slo

    for vdf in slo.discover_vdfs(None):
        if slo.is_sandboxed_layout(vdf):
            continue
        try:
            texto = vdf.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        viva = ponte.arvore_viva(ponte.ler_arvores(texto))
        if viva is None:
            continue
        achado = viva.chaves.get(alvo)
        if achado is not None:
            return str(achado[0]).strip()
    return None


def _os_que_ficam(alvo: str) -> list[str]:
    """Os appids que o DESLIGAR tem de preservar — tudo menos o `alvo`."""
    ponte = _ponte_do_steam_input()
    from hefesto_dualsense4unix.integrations import steam_launch_options as slo

    todos: set[str] = set()
    for vdf in slo.discover_vdfs(None):
        if slo.is_sandboxed_layout(vdf):
            continue
        pasta = ponte.pasta_das_configs_por_jogo(vdf)
        if pasta is None:
            continue
        configurados = ponte.configuracao_por_jogo(pasta)
        if configurados:
            todos |= configurados
    return sorted(todos - {alvo})


STEAM_INPUT_SAIU_E_A_STEAM_ESTA_ABERTA = (
    "Tirei este jogo da lista. A Steam sai do comando dele quando você fechar "
    "a Steam."
)
STEAM_INPUT_NAO_MUDOU_O_ARQUIVO = (
    "Anotei este jogo, mas a Steam ainda não mudou de lado para ele. Abra-o "
    "uma vez pela Steam e clique aqui de novo."
)
STEAM_INPUT_SAIU_E_A_STEAM_CONTINUA = (
    "Tirei este jogo da lista, mas a Steam continua no comando dele."
)
STEAM_INPUT_SAIU_MAS_CONTINUA = (
    f"{STEAM_INPUT_SAIU_E_A_STEAM_CONTINUA} O Hefesto a tira de lá em até meia "
    "hora, ou na próxima vez que a Steam fechar."
)


def _reconciliar_o_vdf(alvo: str, ligar: bool) -> str:
    """Faz o `localconfig.vdf` concordar com a vontade dela — ou diz o que falta.

    **A ESCRITA É DO DONO, INTEIRA:** backup `.bak.…` ao lado, `tmp` + `replace`,
    e a segunda régua conferindo o texto antes de trocar o arquivo
    (`steam_input_ponte`). Nada disso se reescreve aqui, e a ORDEM DOS PORTÕES é
    a dele: jogo aberto, Steam aberta, e só então a escrita.

    **ESTA FUNÇÃO NUNCA FECHA A STEAM DELA.** Com a Steam aberta o dono ADIA, e
    quem pode fechá-la é só o segundo clique no chip, já armado
    (:func:`_fechar_a_steam_e_ligar`). Sem ele, o produto completa sozinho:
    `hefesto-steam-input-guard.path` (**active** e **enabled** na máquina dela
    em 20/09/2026, `PathChanged=%h/.steam/steam/userdata`) acorda quando a
    Steam acaba de sair, que é o único instante em que a escrita sobrevive, e
    roda `disable_steam_input.sh --apply-quiet`: ele zera o
    `UseSteamControllerConfig` de todo jogo FORA da lista dela e liga os que
    estão nela. **Os dois sentidos, sem ninguém clicar de novo.**

    **O QUE A STEAM AINDA NÃO FEZ NÃO É RECUSA** — O-MODO-QUE-NAO-SAI-DO-STEAM-
    INPUT-01, 23/09/2026. Até aqui o adiamento levantava, e a tela piscava
    recusa sobre um clique que valeu: a lista mudou, o caminho mudou, o chip
    acende. Agora o LIGAR adiado volta calado e a frase do dono
    (`Estado.frase()`, que nomeia o jogo e diz quando) vai à faixa de
    pendência (:func:`_a_ponte_que_falta`); o DESLIGAR adiado, que o dono não
    sabe dizer, volta como recado. A única que levanta é a Steam FECHADA sem
    o arquivo mudar: o jogo não está no vdf, e o que ela faz a seguir é abri-lo
    uma vez pela Steam.

    **O VEREDITO É O ARQUIVO.** O `status` do dono não basta: ele diz
    `nada_a_fazer` tanto sobre um jogo que já estava certo quanto sobre um que
    o vdf desconhece, e os dois desfechos são opostos para a tela. Quem separa
    é a releitura — a regra que a HONESTIDADE-STEAM-01 deixou.
    """
    from hefesto_dualsense4unix.integrations import steam_launch_options as slo

    ponte = _ponte_do_steam_input()

    def _acao() -> Any:
        if ligar:
            return ponte.garantir_ponte(allowlist=[alvo])
        return ponte.garantir_fora_da_lista_desligado(allowlist=_os_que_ficam(alvo))

    resultado = _acao()

    atual = _o_que_o_vdf_diz(alvo)
    adiado = (resultado[0] in (ponte.PONTE_ADIADA_JOGO, ponte.PONTE_ADIADA_STEAM)
              or slo.steam_running())
    if ligar:
        if atual == ponte.LIGADO or adiado:
            return ""
        raise RuntimeError(STEAM_INPUT_NAO_MUDOU_O_ARQUIVO)
    if atual in (None, ponte.DESLIGADO):
        return ""
    if not o_guarda_liga_o_steam_input():
        return STEAM_INPUT_SAIU_E_A_STEAM_CONTINUA
    return STEAM_INPUT_SAIU_E_A_STEAM_ESTA_ABERTA if adiado else STEAM_INPUT_SAIU_MAS_CONTINUA


GESTO_DO_STEAM_INPUT = "modo-steam"


@gesto("01-jogar.html", GESTO_DO_STEAM_INPUT,
       grava="add_appid_to_steam_input_allowlist")
def modo_steam(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any] | None:
    """"Steam Input": a Steam entrega a ENTRADA **daquele jogo**, e só dele.

    O ESCOPO É POR JOGO, e é ordem dela: *"setar **o jogo** pra funcionar usando
    os controladores da própria steam"*. A chave da Steam é indexada por appid
    (`UseSteamControllerConfig`, `steam_input_ponte:137`), e um chip que
    escrevesse para a MÁQUINA aplicaria silenciosamente ao jogo que por acaso
    estivesse aberto — que é a `CAMINHO-CONTAGIO-01` repetida com outro campo.

    **O CAMINHO É O DA PONTE DELE** — O-MODO-QUE-NAO-SAI-DO-STEAM-INPUT-01,
    23/09/2026. O degrau 4 da `ESCADA` é gamepad + DualSense + Steam Input, com
    `recria_vpad=False`: o Steam Input senta EM CIMA do caminho DualSense. O
    clique manda esse caminho (:func:`o_que_o_chip_faz`), e é o que faz o chip
    acender vindo do «Xbox» ou da «Navegação». O `Chip.caminho` de `painel`
    continua vazio, e não é gosto: o terceiro termo da `Ponte` já tem casa no
    disco — o `steam_input_apps.txt` e o carimbo `PonteConfirmada.steam_input`
    —, e escrevê-lo no `mode` criaria o segundo dono de um valor que já tem um.

    **O CLIQUE PÕE, SEMPRE — não é mais interruptor.** FATO SUBSTITUÍDO: até
    22/09 o sentido saía da ponte do jogo da vez (de pé desligava, fora
    ligava). Na fileira que é grupo de rádio, clicar no aceso REAPLICA — e é o
    que completa a ponte PENDENTE —; quem tira o jogo da lista é clicar em
    qualquer um dos outros três.

    AS DUAS METADES TÊM PREÇOS DIFERENTES, e só uma acontece sempre:

    1. **a vontade dela** — uma linha num arquivo NOSSO, reversível, com a
       recarga logo atrás: a lista é relida do disco a cada consulta, mas o que
       entrega a entrada daquele jogo ao controle só nasce quando o daemon
       rematerializa o `steam_app_<appid>.env`. Sem `launch_env.refresh` a marca
       só valeria no próximo arranque, e ela clicaria de novo achando que o
       primeiro clique não pegou;
    2. **a ponte** — reescreve o `localconfig.vdf` DELA, e para isso a Steam tem
       de estar FECHADA (ela regrava o arquivo ao sair e engole a edição). Com
       a Steam aberta o dono ADIA; o chip acende pela escolha dela, e a faixa
       diz «Liga quando a Steam fechar» (:func:`_o_que_o_chip_diz`).

    **O PRIMEIRO CLIQUE AVISA, O SEGUNDO FECHA** — escolha dela, 23/09/2026
    (`D-2309-STEAM-INPUT-A-FRASE-E-O-CLIQUE`). Com a Steam aberta, sem jogo
    aberto e o jogo ainda em `"0"`, o primeiro clique ARMA
    (:func:`_armar_se_a_steam_segura`): o rótulo do chip vira
    «Fechar a Steam?» por `confirmacao.SEGUNDOS_PARA_CONFIRMAR`. O segundo
    clique traz esse rótulo — ele só existe no chip armado — e fecha a Steam,
    liga e a reabre (:func:`_fechar_a_steam_e_ligar`). Com jogo aberto nada
    arma: fechar a Steam derrubaria o jogo, e o guarda do vdf completa quando
    os dois saírem.

    FATO SUBSTITUÍDO — 24/09/2026. Aqui se dizia que este gesto *"não fecha a
    Steam dela"*, por recuo medido: *"um chip é um `<span>` estático, não tem
    rótulo para trocar"*. O `blocos:` troca o miolo dele como troca o dos
    botões armados da aba 09 (:func:`_o_rotulo_do_chip`), e é esse rótulo, lido
    de volta no clique, que prova que ela LEU a pergunta.

    **O VEREDITO É O ARQUIVO.** Nenhum desfecho verde sai daqui sem
    :func:`_o_que_o_vdf_diz` reler o vdf e confirmar. Um `status` de sucesso
    sobre um arquivo que não mudou é o `excecao_inerte` que a
    PONTE-STEAM-INPUT-01 existiu para matar — *"a lista só preserva o que já
    estava ligado, ela nunca liga"* — e foi assim que a janela velha cantou
    "Steam Input desligado" sobre um no-op até a HONESTIDADE-STEAM-01.

    SEM JOGO, NADA ACONTECE: a recusa é a frase do dono
    (`format_game_broken_result(status="sem_jogo")`), e nem a lista, nem o vdf,
    nem o caminho são tocados. É o quarto estado de :func:`_steam_input_da_tela`
    do lado do clique — *não sei* dito com todas as letras, em vez de escolher
    um jogo qualquer.
    """
    confirmado = _o_clique_que_confirma(ctx, o)
    if confirmado:
        return _fechar_a_steam_e_ligar(confirmado)
    recado = _o_clique_da_fileira(ctx, o, p, CHIP_DO_STEAM_INPUT)
    return recado or _armar_se_a_steam_segura(ctx)


STEAM_INPUT_ARMADO = "Fechar a Steam?"


def _chave_do_chip(appid: object) -> str:
    """A chave do chip «Steam Input» armado para AQUELE jogo."""
    return confirmacao.chave(PAGINA, GESTO_DO_STEAM_INPUT, appid)


def _desarmar_o_chip() -> None:
    """Desarma o chip, e SÓ ele: o botão armado da aba 09 não é desta fileira."""
    if confirmacao.armado_agora().startswith(_chave_do_chip("")):
        confirmacao.desarmar()


def _o_rotulo_do_chip(state: dict[str, Any] | None) -> dict[str, str]:
    """O `blocos:` do chip — «Fechar a Steam?» armado, «Steam Input» em repouso.

    SAI EM TODO TIQUE, como os botões da aba 09 (`a09_sistema.blocos_dos_botoes`):
    o gesto arma e o tique REPÕE o rótulo quando o relógio vence. O piloto só
    reescreve o miolo quando ele muda, então o tique em repouso não custa nada
    na página. E SÓ PERGUNTA QUAL É O JOGO QUANDO HÁ ALGO ARMADO nesta fileira —
    em repouso, zero disco.

    O RÓTULO EM REPOUSO É O DE `painel.CHIPS_DA_ESCADA` (:func:`_rotulo_do_chip`),
    o mesmo que o gerador escreve; digitá-lo aqui seria a segunda cópia.
    """
    rotulo = _rotulo_do_chip(CHIP_DO_STEAM_INPUT)
    armado = confirmacao.armado_agora()
    if armado.startswith(_chave_do_chip("")):
        appid, _quando = _qual_jogo(state)
        if appid is not None and armado == _chave_do_chip(appid):
            rotulo = STEAM_INPUT_ARMADO
    return {f'[data-gesto="{GESTO_DO_STEAM_INPUT}"]': html.escape(rotulo)}


def _armar_se_a_steam_segura(ctx: Contexto) -> dict[str, Any] | None:
    """O PRIMEIRO CLIQUE AVISA — arma o chip se só a Steam aberta segura a ponte.

    ARMA COM AS TRÊS CONDIÇÕES, e cada uma é pergunta ao dono, na hora:

    * o vdf diz `"0"` para o jogo (:func:`_o_que_o_vdf_diz`) — a ponte ainda
      não subiu, e fechar a Steam a faria subir. Sem o jogo no vdf (`None`),
      fechar a Steam não muda nada, e não se oferece;
    * a Steam está aberta (`steam_running`) — é ela que segura a escrita;
    * NENHUM jogo aberto (`steam_game_running`) — fechar a Steam mataria o
      jogo, e `with_steam_closed` recusaria de qualquer jeito. Oferecer um
      segundo clique que só pode recusar é pedir consentimento para nada.

    Devolve o `blocos:` com o rótulo armado, para a troca ser INSTANTÂNEA; o
    tique também o põe (:func:`_o_rotulo_do_chip`). `None` quando não arma: a
    piscada verde diz que a escolha dela foi anotada.
    """
    from hefesto_dualsense4unix.integrations import steam_launch_options as slo

    appid, _quando = _qual_jogo(ctx.state)
    if appid is None:
        return None
    alvo = str(appid)
    if _o_que_o_vdf_diz(alvo) != _ponte_do_steam_input().DESLIGADO:
        return None
    if not slo.steam_running() or slo.steam_game_running():
        return None
    confirmacao.armar(_chave_do_chip(alvo))
    return {"blocos": _o_rotulo_do_chip(ctx.state)}


def _o_clique_que_confirma(ctx: Contexto, o: dict[str, Any]) -> str:
    """O appid, se ESTE clique é o segundo — `""` se é um primeiro clique."""
    if str(o.get("texto") or "").strip() != STEAM_INPUT_ARMADO:
        return ""
    appid, _quando = _qual_jogo(ctx.state)
    armado = confirmacao.armado_agora()
    confirmacao.desarmar()
    if appid is None or armado != _chave_do_chip(appid):
        raise RuntimeError(STEAM_INPUT_A_PERGUNTA_VENCEU)
    return str(appid)


STEAM_INPUT_A_PERGUNTA_VENCEU = (
    f"Passaram-se mais de {int(confirmacao.SEGUNDOS_PARA_CONFIRMAR)} segundos "
    "desde a pergunta — não fechei a Steam. Clique de novo para começar.")


def _fechar_a_steam_e_ligar(alvo: str) -> dict[str, Any]:
    """O SEGUNDO CLIQUE: fecha a Steam, liga o jogo no vdf e a reabre.

    **NADA AQUI É MECANISMO NOVO.** `with_steam_closed` é o mesmo fluxo que o
    «Aplicar aos jogos da Steam» da aba 09 usa: o portão de JOGO aberto vem
    antes de tudo (fechar a Steam com jogo aberto o mata), a Steam que não fecha
    não é editada, e a reabertura é `finally`. A escrita é `garantir_ponte`,
    com o filtro por appid (`allowlist=[alvo]`), a mesma do primeiro clique.
    A recusa é a frase do dono (`daemon_actions.format_steam_janela_recusa`).

    A LISTA É GARANTIDA ANTES: o primeiro clique já a gravou, e um segundo
    `add_…` devolve `ja_estava`. Sem ela, o guarda do vdf desligaria o jogo na
    próxima saída da Steam.

    **O VEREDITO É O ARQUIVO**, como no primeiro clique (:func:`_o_que_o_vdf_diz`).
    """
    from hefesto_dualsense4unix.app.actions.daemon_actions import (
        format_game_broken_result,
        format_steam_janela_recusa,
    )
    from hefesto_dualsense4unix.integrations import steam_launch_options as slo

    ponte = _ponte_do_steam_input()
    status = slo.add_appid_to_steam_input_allowlist(alvo, nota=NOTA_DA_ESCOLHA)
    if status in ("appid_invalido", "erro"):
        raise RuntimeError(str(format_game_broken_result(status=status, appid=alvo)))
    try:
        if _o_que_o_vdf_diz(alvo) == ponte.LIGADO:
            return {"blocos": _o_rotulo_do_chip(None)}
        janela, _resultado = slo.with_steam_closed(
            lambda: ponte.garantir_ponte(allowlist=[alvo]))
        recusa = format_steam_janela_recusa(janela)
        if recusa is not None:
            raise RuntimeError(recusa)
        if _o_que_o_vdf_diz(alvo) != ponte.LIGADO:
            raise RuntimeError(STEAM_INPUT_NAO_MUDOU_O_ARQUIVO)
    finally:
        VIGIA_DO_STEAM_INPUT.renovar()
    return {"blocos": _o_rotulo_do_chip(None)}


MASCARA_VALE_SEM_PERFIL = (
    "A máscara vale agora, mas não ficou guardada. Escolha um perfil na aba "
    "Perfis para ela ser lembrada."
)
MASCARA_VALE_SEM_ENDERECO = (
    "A máscara vale agora, mas o perfil não consegue guardá-la só para este "
    "controle."
)
MASCARA_VALE_SEM_GUARDAR = (
    "A máscara vale agora, mas não consegui guardá-la no perfil."
)

_FRASE_DA_MASCARA_NAO_GUARDADA = {
    "sem_perfil": MASCARA_VALE_SEM_PERFIL,
    "sem_endereco": MASCARA_VALE_SEM_ENDERECO,
    "sem_mudanca": "",
}


def _recado_da_mascara(motivo: str | None) -> str:
    """A frase do cartão para o `motivo` que o daemon devolveu — `""` se calou."""
    if not motivo:
        return ""
    return _FRASE_DA_MASCARA_NAO_GUARDADA.get(motivo, MASCARA_VALE_SEM_GUARDAR)


@gesto("01-jogar.html", "mascara", grava="gamepad.mask.set")
def mascara_do_controle(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any] | None:
    """A máscara de UM aparelho — os chips dentro do cartão de cada controle.

    O PEDIDO É DELA, 03/09/2026: *"É uma máscara por controle. Mesmo caso do
    anterior."* — e o "anterior" é a decisão dos quatro lugares, no mesmo dia.

    ESTES SEIS CHIPS ESTAVAM MORTOS. A leva que clicou as dez abas mediu:
    *"`mascara` (6 chips nos cartões) · máscara POR CONTROLE · **NADA. SEM
    DONO**"*. Clicar não mudava um campo do daemon e não dizia uma palavra.

    E A CASA JÁ TINHA A METADE DIFÍCIL FEITA. `external_mask` guarda a escolha
    por APARELHO desde 15/08/2026 (MÁSCARA-POR-JOGADOR-01, decisão dela), e
    `mascara_efetiva` é consultada na criação de todo gamepad virtual — os três
    degraus do daemon fecharam em 29/08. Faltava só a rota de escrita, que o
    próprio módulo nomeava: *"quem grava a escolha dela é a rota IPC, que ainda
    só conhece a máscara da sessão."* Ela nasceu hoje: `gamepad.mask.set`.

    AS TRÊS MÁSCARAS EXISTEM, E OS TRÊS CHIPS TÊM MOTOR (desde 07/09/2026).
    `mascaras_validas()` devolve `{dualsense, xbox, nintendo}`, e é dele que a
    recusa sai — nunca de uma lista digitada aqui. Um rótulo fora do catálogo
    continua RECUSANDO DIZENDO em vez de gravar um valor que o daemon não sabe
    montar; escolher o silêncio seria repetir o defeito que este gesto veio
    curar. O que mudou é que o "Nintendo Pro" saiu do lado errado dessa
    fronteira.

    O ALCANCE É O CARTÃO. Sem `uniq` não há a quem aplicar, e "todos" seria a
    máscara da sessão — que é outro botão, o de cima. A recusa separa os dois
    casos como a `03-gatilhos` faz: coluna vazia é uma frase, clique sem
    controle é outra.
    """
    from hefesto_dualsense4unix.daemon.subsystems.external_mask import (
        mascaras_validas,
        normalizar_mascara,
    )
    from hefesto_dualsense4unix.interface.mesa_viva import NOME_DA_MASCARA

    uniq = str(o.get("uniq") or "").strip()
    if not uniq:
        lugar = str(o.get("controle") or "").strip()
        if lugar:
            raise RuntimeError(
                f"Não há controle no lugar {lugar.upper()}. Ligue um controle "
                "aqui para ele receber a máscara.")
        raise ValueError("mascara: o clique não disse em qual controle")

    rotulo = str(o.get("mascara") or o.get("rotulo") or "").strip()
    if not rotulo:
        raise ValueError("mascara: o chip não disse qual máscara")

    por_rotulo = {v: k for k, v in NOME_DA_MASCARA.items()}
    flavor = por_rotulo.get(rotulo) or normalizar_mascara(rotulo)
    if flavor is None or flavor not in mascaras_validas():
        tem = ", ".join(NOME_DA_MASCARA[f] for f in sorted(mascaras_validas())
                        if f in NOME_DA_MASCARA)
        raise RuntimeError(
            f"“{rotulo}” está desenhado na tela e o Hefesto não sabe montar "
            f"essa máscara. As que existem: {tem}.")

    # Ela estava escrita `p.chamar("gamepad.mask.set", {"uniq": …, "flavor": …})`,
    # `ponte.chamar(metodo, timeout=None, **params)`: o 2º posicional é o  # (parâmetro) noqa-acento
    # TIMEOUT. O dicionário virava o prazo, `teto(metodo)` o  # (parâmetro) noqa-acento
    # o chip DualSense do P1 não criava o `controller_masks.json` e não mexia em
    # POR QUE NINGUÉM VIU: `gamepad.mask.set` não estava em `METODOS` (a régua
    # deu"*). `gamepad.mask.set` responde `{"gravado": false, "motivo": …}`
    ok, motivo = p.chamar_detalhado("gamepad.mask.set", uniq=uniq, flavor=flavor)
    if not ok:
        # `gamepad.mask.set` recusa em voz alta com o catálogo do que aceita.
        if motivo:
            raise RuntimeError(motivo)
        return None
    recado = _recado_da_mascara(motivo)
    return {"recado": recado} if recado else None


@gesto("01-jogar.html", "modo-navegacao",
       grava="liga o mouse emulado e o ponteiro anda na tela dela")
def modo_navegacao(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any] | None:
    """"Navegação": o controle vira teclado e mouse do computador.

    O CASO DO MEIO, e `painel` o explica melhor do que eu resumiria: a Navegação
    **não é degrau da `ESCADA`** (`KIND_DESKTOP` existe como constante e
    `indice_do_degrau` devolve -1) e **tem escritor**:
    `apply_mode('desktop')` funciona hoje. Confundir as duas
    perguntas pintaria "sem dono" sobre um botão que dá.

    SÃO TRÊS IPCs, e o terceiro é o que faz a diferença entre entrar no modo e
    entrar num modo sem função. Sem ele, o modo desktop desligava os outros dois
    e deixava o controle sem fazer nada até alguém achar a aba Mouse — foi o
    `MODO-QUE-NAO-CONTROLA-01`, medido com ela ao vivo: *"cliquei em aplicar e
    nada"*. E ele vem POR ÚLTIMO: ligar o mouse antes de o gamepad sair faria a
    exclusão mútua do daemon derrubar o mouse recém-ligado. A ordem é do plano,
    não daqui.

    O TERCEIRO PASSO TROCOU DE FONTE — POINT-AND-CLICK-01, 17/09/2026, pela
    ordem dela: *"o modo point and click é o modo navegação e o modo que nós
    mesmos podemos usar e configurar na aba navegação. **Ele ativa o modo
    configurado lá.**"* Era `mouse.emulation.restore`, que lê a flag de sessão
    da MÁQUINA; é `desktop.arranjo.apply`, que lê o PERFIL ATIVO — mouse,
    `key_bindings`, `button_actions`, `teclado_emulado` e a queda da supressão.
    As cinco coisas que a aba Navegação grava chegavam ao disco e não voltavam,
    e o laço se fechava: a aba Navegação manda ir à aba Jogar para trocar o
    modo, o chip daqui é a única porta, e a porta entrava num modo que não
    carregava nada do que ela havia configurado.

    FATO SUBSTITUÍDO NO PARÁGRAFO ACIMA: dizia-se aqui que *"o PS+R3 não para
    aqui"*. Ele para desde 13/09/2026 (`hotkey.CICLO_DE_PONTES`), e desde 17/09
    entra pela MESMA porta deste clique. O que a Navegação não tem é degrau na
    `ESCADA` automática — que é outra pergunta.

    E TIRA O JOGO DA VEZ DO STEAM INPUT, como o «Xbox» — a linha dela em
    :func:`o_que_o_chip_faz`, e o clique é :func:`_o_clique_da_fileira`.
    """
    return _o_clique_da_fileira(ctx, o, p, "navegacao")


@gesto("01-jogar.html", "cadeado", grava="freestyle_set")
def cadeado(ctx: Contexto, o: dict[str, Any], p: Any) -> None:
    """O botão «Modo Freestyle» — até 23/09/2026, a caixa «Trava o perfil ativo».

    PEDIDO NOMEADO DELA, de 23/07/2026, e ele saiu do desenho por escolha minha
    — declarada na legenda desta própria página: *"A caixa saiu — o perfil ativo
    já diz isso"*. O que mudou desde então está medido: a coluna **Atenção**
    passou a ler `painel.AVISOS_DA_TELA`, e `autoswitch_lock_text` e
    `texto_do_cadeado_cego` são duas das seis fontes. **A tela EXPLICA o cadeado
    e não oferece onde ligá-lo, em nenhuma das dez abas.** A decisão [03] do PO
    o traz de volta para cá: *"Volta para a Jogar, embaixo de Modo"* — a única
    posição em que a frase que explica e o botão que resolve ficam na mesma
    tela.

    O ESCRITOR JÁ EXISTIA: `ponte.freestyle_set` expõe o
    `app/ipc_bridge.freestyle_set`, que é o mesmo que o
    `_on_home_autoswitch_lock_toggled` da janela antiga aciona. Zero regra
    reescrita. Desde 28/09/2026 (O-FREESTYLE-E-UMA-CAMADA-SO-01) ligar é o
    «Ativar» do Freestyle na aba Perfis, e ele manda em todo jogo.

    **O VALOR VAI ABSOLUTO, NUNCA COMO TOGGLE, e é a metade que decide.** A
    ponte aceita `locked=None` e o daemon inverte sozinho; usar isso aqui seria
    o defeito, por duas razões medidas:

    1. **um clique chega DUAS vezes.** O ouvinte único do piloto está em `click`
       **e** em `change` (`hefesto_vivo.BOOTSTRAP`), e um `<input
       type="checkbox">` dispara os dois — o `change` nasceu para os `<select>`
       e os campos de texto, que nunca dão clique com o valor novo. Dois
       toggles seriam um NO-OP: ela clica e nada acontece, que é a queixa dela
       em estado puro;
    2. **o daemon poderia inverter a partir de outro estado.** O valor absoluto
       é a escolha DELA lida da tela; o toggle é a tela obedecendo a um estado
       que ela não viu.

    E O `evento` FILTRA A SEGUNDA ENTREGA, para o disco dela receber UMA
    escrita por clique: `profiles.manager.ligar_o_freestyle` grava.
    O `change` é o escolhido porque é o único que só dispara quando a caixa de
    fato MUDOU — clique em rótulo, tecla de espaço e `el.click()` sintético
    passam pelos três caminhos. Um clique sem `evento` (a régua dos botões, que
    monta o recado à mão) continua valendo: o padrão é `change`.

    A VERDADE VOLTA DO DAEMON, não deste gesto: o alvo `marcado` repinta a caixa
    a cada tique a partir de `freestyle_ligado`. Se a escrita não pegar, a
    caixa **volta sozinha** — que é o oposto de uma tela que finge ter guardado.

    RELATO FECHADO — 06/09/2026, pela `ONDA3-GESTO-DECLARA-01`. Aqui estava
    escrito que este gesto pertencia a `hefesto_vivo.PERIGOSOS` e que a linha
    não podia ser escrita *"porque os dois arquivos são de outro dono"*. Esse
    é exatamente o defeito que a sprint matou: a declaração passou a morar no
    PRÓPRIO decorador (`grava="freestyle_set"`), e `PERIGOSOS` é derivada
    dela. Quem escreve o gesto fecha o próprio contrato.

    **FATO SUBSTITUÍDO — 06/09/2026, e a conclusão dele fica de pé por outro
    motivo.** Este fecho dizia que a caixa só existia no desenho da BANCADA e
    que o piloto abre o publicado, e por isso o `--prova-gesto` não a clicava.
    A primeira metade caducou: a caixa está na página publicada, que é a que o
    produto renderiza (`onde.PUBLICADO`), e a régua
    `test_o_cadeado_esta_publicado` mede isso LENDO o arquivo — não este
    parágrafo. **A conclusão continua certa, e a razão é `PERIGOSOS`:** clicar
    esta caixa GRAVA no disco dela (`utils/session.save_freestyle_ligado`, pelo
    `freestyle.set`), e uma régua de clique que mudasse uma preferência dela
    para provar que sabe clicar seria pior que a cobertura que ela compra.

    **O VERDE É O RECIBO, e ele só acende quando o serviço confirmou** —
    05/09/2026, decisão dela na `03-Q4`: *"O campo que você acabou de mexer
    ganha uma borda verde por cerca de um segundo e meio"*, *"nenhuma palavra
    nova entra na tela"*. Este é o gesto da aba que mais precisava dele, e a
    razão é medida: é o único cujo efeito **não aparece em lugar nenhum da
    tela**. Trocar de modo acende um chip; trocar a máscara muda o cartão; o
    cadeado só muda um booleano no disco, e a caixa que ela acabou de clicar já
    está marcada pelo próprio clique.

    **PEDIR O VERDE É VOLTAR SEM LEVANTAR**, e o mecanismo é o do piloto, não
    uma peça deste arquivo: `hefesto_vivo._gesto` anota `"aplicou"` no ramo sem
    exceção, e o `finally` leva esse desfecho ao pouso, que acende
    `hef-deu-certo` por `MS_DA_PISCADA` no elemento que ela clicou. Nada a
    inventar aqui, e endereço nenhum a criar.

    **O QUE FALTAVA ERA O DIREITO DE PEDI-LO: a resposta da ponte ia para o
    lixo.** `ipc_bridge.freestyle_set` devolve o estado que FICOU valendo,
    e `None` quando não houve resposta. Sem ler isso, um clique com o serviço
    parado piscava VERDE e a caixa desmarcava no tique seguinte (`_cadeado` sem
    `freestyle_ligado` devolve `""`): a tela dizia *guardei* e *não está
    guardado* com 100 ms entre as duas. É a metade que separa **o produto
    confirmou** de **a tela pintou sozinha**.

    A GUARDA É `is None` E NÃO UMA COMPARAÇÃO, e a medição diz por quê:
    `_handle_freestyle_set` (`daemon/ipc_handlers.py`) usa o `ligado`
    quando ele vem no pedido — o toggle é só para quem NÃO manda valor, e
    este gesto sempre manda. Um bool que discordasse do pedido é ramo que este
    daemon não tem como produzir, e escrevê-lo seria inventar um desfecho para
    poder tratá-lo.
    """
    if str(o.get("evento") or "click") != "click":
        return
    pedido = _cadeado(ctx.state) != CADEADO_LIGADO
    if p.freestyle_set(ligado=pedido) is None:
        raise RuntimeError(CADEADO_RECUSA)


def _o_radio_de_volta(ctx: Contexto) -> tuple[int, int]:
    """PASSO 0 — o RÁDIO. Devolve `(voltaram, esperam_o_ps)`."""
    from . import perfil

    return perfil.o_radio_de_volta(ctx)


@gesto("01-jogar.html", "reconectar")
def reconectar(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any] | None:
    """"Reconectar Controles": os jogadores voltam, e a numeração se ajeita.

    O NOME DA TELA É DELA E É NOVO; o gesto não é. A legenda desta aba registra
    a troca — *"'Reconciliar jogadores' virou 'Reconectar Controles'"* — e o
    botão antigo é `home_actions._on_home_reconciliar_clicked`, que faz
    exatamente estes dois passos, encadeados.

    **NÃO É O `Connect` DO BLUEZ, e isso é decisão dela.** O
    `integrations/gesto_de_reconexao.py` diz com todas as letras: *"Não
    reconectar é decisão dela, e é o contrato deste módulo. O botão PS é dela;
    `reconectar` não existe aqui de propósito. Um `Connect` nosso devolveria o
    controle sem o gesto físico — e a instância que voltaria seria nossa, não
    dela."* O que este botão traz de volta é o JOGADOR, não o rádio.

    PASSO 1 — `coop.sync`: um ciclo FORÇADO de reconciliação
    (`CoopManager.sync(force=True)`). É o único caminho capaz de trazer de volta
    o jogador cujo grab foi recusado ou cujo vpad morreu sem que `/dev/input`
    mudasse: o ciclo normal do poll loop só reenumera quando `/dev/input` muda,
    e um vpad morto pode esperar o próximo hotplug para sempre
    (`ipc_handlers.py:3851`).

    PASSO 2 — `identity.renumber`: compacta a numeração preservando a ordem
    relativa. **A ORDEM É A ENTREGA** e está escrita no botão antigo
    (`home_actions.py:1975`): *"renumerar antes de reconciliar compactaria uma
    mesa que ainda não está completa."*

    E A RECUSA DO SEGUNDO NÃO É ERRO: com o jogo aberto o daemon recusa
    renumerar (repintar o LED do controle em uso no meio da partida é o defeito
    que a NUMA-03 fechou), e os jogadores já voltaram no passo 1. Tratar isso
    como falha seria a interface mentindo — é a mesma regra do
    `reported_step_index`. Por isso o segundo passo vai sem levantar.

    **O BOTÃO DEIXA DE RESPONDER CALADO — JOGAR-OS-SEIS-AVISOS-01, 06/09/2026.**
    Até aqui as duas linhas eram `p.chamar(…)`, e `chamar` devolve um `bool` que
    ninguém lia: clicar com o serviço fora do ar e clicar com ele vivo
    produziam **exatamente a mesma tela**. A janela antiga tem QUATRO desfechos
    nomeados neste mesmo gesto (`home_actions._on_home_reconciliar_clicked`), e
    nenhum deles chegava aqui.

    `resultado` E NÃO `chamar_detalhado`, e a razão é o CORPO da resposta:
    `chamar_detalhado` devolve ``(ok, motivo)`` e joga o corpo fora. O passo 2
    precisa dele porque a recusa por jogo aberto chega DENTRO de uma resposta
    bem-sucedida (``{ok: false, reason: "sessao_de_jogo_aberta"}``), e é o
    corpo que a separa da falha de verdade. NOTA DATADA — 24/09/2026: até aqui
    este parágrafo dizia que o ``renumbered`` separava *"compactei N
    controles"* de *"já estava compacta"*; a numeração que deu certo deixou de
    ter frase pela decisão dela (`D-2409-O-RECONECTAR-NAO-DIZ-NADA`), e o
    ``renumbered`` não é mais lido — ver `painel.recibo_do_reconectar`.

    **A FALHA DO PASSO 1 LEVANTA; A DO PASSO 2, NÃO.** É o encadeamento da
    janela antiga, linha por linha: o `coop.sync` é quem responde *"meus
    jogadores voltaram?"*, e sem ele não há gesto — vira `RuntimeError`, que é
    o canal da recusa laranja. O `identity.renumber` é acabamento: se ele não
    responder, o recibo diz que a numeração não foi conferida
    (`painel._NAO_CONFERIU`) e os jogadores continuam de pé.

    O `except Exception` LARGO nos dois é de propósito e tem endereço: `ponte.
    resultado` levanta `RuntimeError` quando o daemon não atende, mas o
    `_safe_call` por baixo dela **propaga** `ValueError`/`TypeError` de bug
    interno de propósito (`app/ipc_bridge.py:61-65`). Deixá-los subir daqui
    mataria o gesto sem uma palavra na tela, que é o defeito que este passo
    cura.
    """
    voltaram, esperam_o_ps = _o_radio_de_volta(ctx)
    from . import perfil

    try:
        sync, renumerou = perfil.os_jogadores_de_volta(p)
    except Exception as erro:
        raise RuntimeError(_painel().RECONECTAR_SEM_SERVICO) from erro
    jogadores = sync.get("players") if isinstance(sync, dict) else None
    #: quando não houve o que contar, e um `{"recado": ""}` não é o mesmo que
    recibo = _painel().recibo_do_reconectar(jogadores, renumerou)
    do_radio = _painel().recado_do_radio(voltaram, esperam_o_ps)
    junto = " ".join(parte for parte in (do_radio, recibo) if parte)
    return {"recado": junto} if junto else None


#: que o DualSense não devolve). Os dois daqui o daemon publica — os cinco
#: `controllers[].player`, e as quatro chaves estão no `state_full`. Declará-los
#: separá-la porque ela lê só o `state_full` ANTES e DEPOIS; separar exigiria
#: clique que não pegava não deixava rastro nenhum, porque `_aplicar` engole o
OS_DOIS_DA_LISTA_DOS_DEZESSEIS: dict[str, str] = {
    "hefesto": (
        "aplicou e não havia o que mudar: a prova clica a posição Ligado e o "
        "daemon já estava em `gamepad` (`native_mode false`, "
        "`gamepad_emulation.enabled true`). Os dois IPCs são idempotentes."
    ),
    "reconectar": (
        "aplicou e não havia o que mudar: `coop.sync` reconcilia uma lista já "
        "reconciliada e `identity.renumber` compacta uma numeração já compacta. "
        "Os dois ecoam em `coop` e em `controllers[].player` quando há o que fazer."
    ),
}

#: dele porque `gamepad.mask.set` responde `{"gravado": false, "motivo": …}`
PONTE = {"chamar", "chamar_detalhado", "freestyle_set", "resultado"}
#: 04/09/2026 junto com o `gamepad.mask.set`: a folga de 2,0 s existe porque
METODOS_DA_TROCA_DE_MODO = {
    "native.mode.set",
    "gamepad.emulation.set",
    "coop.sync",
    "identity.renumber",
    # O `mouse.emulation.restore` SAIU DAQUI em 17/09/2026 (POINT-AND-CLICK-01)
    # a régua verde sobre uma ponte que ninguém atravessa.
}
METODOS = METODOS_DA_TROCA_DE_MODO | {
    # é a família do `profile.switch`, e a razão está escrita em `ponte.TETOS`.
    # É o mesmo arranjo declarado do `gamepad.mask.set` logo abaixo, pelo
    "desktop.arranjo.apply",
    # de ficar ao lado do certo. Ela dizia que `gamepad.mask.set` não estava em
    #   * o teto entrou em 04/09/2026 — `ponte.TETOS["gamepad.mask.set"] = 2.0`,
    "gamepad.mask.set",
    "launch_env.refresh",
}


PAGINA = "01-jogar.html"
PISO_DA_ABA = 7

_MANUAL_ON = {"enabled": True, "origin": "manual"}
_MANUAL_OFF = {"enabled": False, "origin": "manual"}

PROVAS = [
    {"pagina": PAGINA, "gesto": "hefesto", "clique": {"modo": "gamepad"},  # (noqa-acento) id
     "chama": [("chamar", ["native.mode.set"], _MANUAL_OFF),
               ("chamar", ["gamepad.emulation.set"], _MANUAL_ON)]},
    {"pagina": PAGINA, "gesto": "hefesto", "clique": {"modo": "native"},  # (noqa-acento) id
     "chama": [("chamar", ["native.mode.set"], _MANUAL_ON)]},
    # de `painel.CHIPS_DA_ESCADA` — o que está digitado aqui é a EXPECTATIVA.
    {"pagina": PAGINA, "gesto": "modo-dualsense", "clique": {},  # (noqa-acento) chave do contrato
     "chama": [("chamar", ["native.mode.set"], _MANUAL_OFF),
               ("chamar", ["gamepad.emulation.set"],
                {**_MANUAL_ON, "caminho": "dualsense"})]},
    {"pagina": PAGINA, "gesto": "modo-xbox", "clique": {},  # (noqa-acento) chave do contrato
     "chama": [("chamar", ["native.mode.set"], _MANUAL_OFF),
               ("chamar", ["gamepad.emulation.set"],
                {**_MANUAL_ON, "caminho": "xbox"})]},
    {"pagina": PAGINA, "gesto": "modo-navegacao", "clique": {},  # (noqa-acento) chave do contrato
     "chama": [("chamar", ["native.mode.set"], _MANUAL_OFF),
               ("chamar", ["gamepad.emulation.set"], _MANUAL_OFF),
               ("chamar", ["desktop.arranjo.apply"], {"origin": "manual"})]},
    {"pagina": PAGINA, "gesto": "reconectar", "clique": {},  # (noqa-acento) chave do contrato
     "chama": [("resultado", ["coop.sync"], {}),
               ("resultado", ["identity.renumber"], {})]},
    {"pagina": PAGINA, "gesto": "mascara",  # (noqa-acento) chave do contrato
     "clique": {"uniq": "aa:bb:cc:00:00:01", "mascara": "Xbox 360"},
     "chama": [("chamar_detalhado", ["gamepad.mask.set"],
                {"uniq": "aa:bb:cc:00:00:01", "flavor": "xbox"})]},
    {"pagina": PAGINA,  # (noqa-acento) chave do contrato
     "gesto": "cadeado", "clique": {"evento": "click"},
     "chama": [("freestyle_set", [], {"ligado": True})]},
]
