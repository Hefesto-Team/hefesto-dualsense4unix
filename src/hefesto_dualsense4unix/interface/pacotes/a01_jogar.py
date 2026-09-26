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

#: O ENDEREÇO DA RESSALVA DO CADEADO — 07/09/2026, achado pela conferência desta
#: leva.
#:
#: Ele existe como CONSTANTE, e não como string solta, pela mesma razão que o
#: `ENDERECO_DA_RESSALVA` da aba 06: são TRÊS lugares que precisam concordar —
#: o desenho (`aba01.py`, que emite a `monta.ressalva`), a promessa
#: (:data:`DA_PAGINA`) e o emissor (:func:`pacote`). Um endereço digitado três
#: vezes é um typo à espera de virar linha que nunca pinta, calada.
CADEADO_CEGO = "cadeado-cego"

#: OS ENDEREÇOS DA PÁGINA que esta aba promete pintar — os que valem para a tela
#: inteira. Eles existem como TUPLA, e não soltos no `return`, porque o
#: `cobertura` é a promessa que a régua confere: uma chave nova que não entre
#: aqui vira um contador que mente, e ele é O instrumento com que esta casa
#: prova que um endereço existe.
DA_PAGINA: tuple[str, ...] = (
    # OS QUATRO ENDEREÇOS DA COLUNA ATENÇÃO SAÍRAM DAQUI — 07/09/2026, ordem
    # dela: *"em jogar remover essa seção do atenção, nenhum aviso esse —
    # deixar só o reconectar controles."* Eram `atencao-conta`, `aviso-selo`,
    # `aviso-texto` e `aviso-vivo`.
    #
    # ELES SAEM PORQUE A PÁGINA SAIU, e não por escolha: um endereço emitido sem
    # elemento onde pousar é ÓRFÃO, e o `casamento.py` o acusa. Foi assim que o
    # `recado` da aba 04 foi pego em 02/09 — a régua do mockup não o via, porque
    # ela varre os endereços do ARQUIVO e um campo sem lugar não sai em arquivo
    # nenhum.
    #
    # `_avisos` CONTINUA DE PÉ, com as onze fontes, e o docstring dele diz para
    # onde elas vão. O que morreu foi o POUSO, não o canal.
    # O CADEADO DA TROCA AUTOMÁTICA — 04/09/2026, decisão [03] do PO sobre esta
    # aba: *"Volta para a Jogar, embaixo de Modo."*
    #
    # O PEDIDO É DELA E É DE 23/07. A caixa saiu do desenho por escolha minha,
    # declarada na legenda desta página — *"A caixa saiu — o perfil ativo já diz
    # isso"* —, e a razão de ela ter voltado era a coluna **Atenção**, que lia
    # `autoswitch_lock_text` e `texto_do_cadeado_cego`.
    #
    # A COLUNA SAIU EM 07/09 E A CAIXA FICOU, o que deixava esta tela OFERECENDO
    # onde ligar o cadeado sem explicar por que ele importa.
    #
    # **CURADO NO MESMO DIA, pela conferência da leva** — e a cura é UMA linha,
    # não a coluna de volta. `CADEADO_CEGO` é a ressalva da D-02 dela (*"linha
    # fixa só quando HÁ ressalva"*) colada embaixo da caixa: ela nasce vazia,
    # não ocupa pixel enquanto o detector enxerga, e só aparece na máquina em
    # que o cadeado não tem sobre o que agir. A `CADEADO_DICA` no `title`
    # explica o que a caixa FAZ; esta linha diz quando ela não faz nada.
    "cadeado",
    CADEADO_CEGO,
    "hef-posicao",
    # A RESSALVA DA MÁSCARA e a FRASE DA MESA — 04/09/2026. As duas são
    # `data-campo` de UM valor pintado em DOIS elementos: o de fora com
    # `data-hef-alvo="classe"` (existe / não existe) e o de dentro sem alvo (o
    # texto). O piloto escreve o mesmo valor em todo elemento de mesmo endereço
    # e cada um decide pelo alvo dele (`hefesto_vivo`, passo 1), e `ligado('—')`
    # é falso — então a linha some sozinha quando não há o que dizer.
    #
    # É o par que o `pendente`/`pendente-ha` precisou de DOIS endereços para
    # fazer, com um a menos: lá a frase e a existência têm valores diferentes
    # (a frase é do produto, a existência é `"1"`), aqui é o MESMO texto que
    # decide as duas coisas.
    "mascara-ressalva",
    "mesa-frase",
    "modo-aceso",
    # O CHIP DO STEAM INPUT TEM CAMPO PRÓPRIO — STEAM-INPUT-01, 20/09/2026, e o
    # motivo é que ele deixou de ser mutuamente exclusivo com os outros.
    #
    # Os quatro chips compartilhavam `modo-aceso`, e o comentário do gerador
    # dizia por quê: *"Um segundo clique não pode deixar dois acesos porque não
    # há caminho em que duas chaves casem."* Isso era verdade enquanto os
    # quatro eram CAMINHOS (ou modos) — um por vez, por construção.
    #
    # O Steam Input é ORTOGONAL ao caminho: o degrau 4 da `ponte_escada.ESCADA`
    # é `Ponte(gamepad, dualsense, steam_input=True)` e tem `recria_vpad=False`
    # — ele senta EM CIMA do caminho DualSense em vez de substituí-lo.
    #
    # FATO SUBSTITUÍDO — 21/09/2026. Aqui se dizia que os dois acendiam juntos,
    # e era o padrão que a sprint deixou enquanto a D-2 esperava a palavra
    # dela. A palavra veio — *"dois botões ligados no modo"* — e acende UM, o
    # degrau em que se está (`_estado_da_tela`, UM ACESO SÓ). O campo próprio
    # ficou, e é por ele que o Python diz QUAL dos dois acende: o Steam Input
    # não tem caminho, e o laço do `modo-aceso` nunca o escolheria.
    #
    # CUSTO ZERO DE PIXEL, e foi o que decidiu o desenho: `data-campo`,
    # `data-hef-alvo` e `data-hef-quando` estão todos em
    # `scripts/check_o_desenho_aprovado.INVISIVEIS`, e a classe acesa continua
    # sendo a MESMA `on`. Uma marca visual distinta para o Steam Input custaria
    # CSS novo e `--publicar 01`, que é ato dela (§7 D-2 da sprint).
    "steam-input-aceso",
    "pendente",
    "pendente-alvo",
    "pendente-ha",
    # OS CONTROLES QUE O HEFESTO SÓ VÊ — EXTERNOS-01, 06/09/2026, linha 16 do
    # `docs/data/paridade-gtk-html.csv`.
    #
    # UM ENDEREÇO SÓ, e não o par `pendente`/`pendente-ha`: a peça é a
    # `monta.ressalva`, que já sabe NÃO OCUPAR NADA em repouso — `:empty` e
    # `:has(.nada)` estão no esqueleto compartilhado desde a D-02 dela. Um
    # segundo endereço para "existe?" seria reescrever em Python o que duas
    # regras de CSS já respondem, e um a mais para a régua do casamento conferir.
    #
    # O ALVO É `html` porque o bloco é TROCADO INTEIRO: quantos externos existem
    # é o que a máquina responde, e não há endereço para um cartão que ainda não
    # nasceu. É a mesma razão do mapa do gabinete e da régua do rádio na aba 08.
    "externos",
)

#: OS ENDEREÇOS DE DENTRO DE CADA CARTÃO.
#:
#: `desenho` É O SVG DO CONTROLE — 03/09/2026, e ele fecha a outra metade da
#: queixa dela: *"os svgs do dualsense (…) não são os que o meu mapa cataloga"*.
#: A `plastico` pinta a BORDA do cartão; esta escreve o `data-colorway` do
#: próprio desenho, que é o seletor com que a folha das 28 cores escolhe o
#: modelo. Sem ela a borda ficava White e o controle desenhado continuava
#: Cosmic Red, um centímetro abaixo.
#:
#: `mascara-cartao` MUDOU DE LADO EM 03/09/2026 — estava em `DA_PAGINA`, e o
#: comentário que a prendia lá dizia *"`gamepad.emulation.set` recebe `flavor` e
#: não recebe `uniq`, logo a máscara é UMA para a máquina"*. **Isso deixou de
#: ser verdade no mesmo dia:** `gamepad.mask.set` nasceu recebendo `uniq`, o
#: registro `external_mask` guarda a escolha por APARELHO desde 15/08, e o
#: daemon publica `gamepad_emulation.por_aparelho`.
#:
#: O QUE O LADO ERRADO CUSTAVA, e não era teórico: o piloto pinta os valores de
#: página em TODO elemento com aquele `data-campo` (`hefesto_vivo`, passo 1),
#: então a máscara da SESSÃO era escrita nos três chips de todos os cartões. Com
#: o P1 em `dualsense` e o P2 em `xbox` — que é o que o registro sabe guardar e
#: o que o desenho dela mostra — os dois cartões acendiam o MESMO chip. A
#: bancada já fazia certo (`jogar_vivo` pinta `[data-mascara]` dentro de cada
#: cartão, com o valor daquele `uniq`); quem discordava era o produto.
#: `jogador-espera` É O ESMAECIDO DO NÚMERO — decisão do PO, 04/09/2026, sobre a
#: pergunta [02] desta aba: *"'Player N', esmaecido enquanto espera."*
#:
#: ELE NÃO TOCA A PALAVRA, e é isso que o faz caber: a **D-04** dela fixou
#: *"Player N, como está hoje"* contra a minha recomendação, e é decisão dela.
#: O que sobra de dano é o cartão AFIRMAR um jogador que o jogo ainda não tem —
#: e esse se mata com tinta, não com texto.
#:
#: DOIS ENDEREÇOS PARA UM CARTÃO, e não um: o `jogador` é o TEXTO (`Player 2`) e
#: este é a CLASSE. Um elemento carrega um endereço só, e `escrever()` num
#: elemento com filho apagaria os filhos — é a armadilha medida do piloto da
#: Controles. O de fora acende a classe, a folha do de dentro esmaece.
#:
#: `marcador-principal` É O "primário" DO MOTOR — JOGAR-O-QUE-FALTA-01, Passo 3
#: (06/09/2026), e era a linha 18 do CSV. O SINAL daquela linha **é este
#: endereço**, escolhido pela `ONDA4-S10` em 06/09 justamente porque o anterior
#: era o nome de uma função de outra feature e disparou duas vezes sobre
#: trabalho legítimo. O nome é slug e slug não leva acento — a PALAVRA que a
#: tela mostra é `MARCA_DO_PRIMARIO`, e ela vem do dono.
#:
#: **ELE NÃO É A CLASSE `.cartao.alvo`, e a sprint avisa por quê:** aquela já
#: existe e responde a OUTRA pergunta — o alvo de edição da fita —, e reusá-la
#: faria os dois significados brigarem no mesmo pixel. O defeito só apareceria
#: quando ela editasse a fita com um controle que não é o primário, que é tarde.
#:
#: `degradou-cartao` SAIU — 13/09/2026, A-MARCA-DA-DEGRADACAO-01. Era a marca da
#: emulação degradada (Passo 4 da JOGAR-O-QUE-FALTA-01): um `<sup>*</sup>` com a
#: frase de `controller_card.texto_degradacao` no `title`, na gramática do cartão
#: da 02 (decisão [07] de 04/09, *"uma marca na palavra e o motivo no hover"*).
#:
#: **ELA NUNCA ACENDEU**, medido na validação da RESTOS-DA-ONDA-DOIS-01: a folha
#: a mostrava por `[title]`, e a camada de dicas do piloto leva o `title` para
#: `data-hef-dica`. **E ACESA SERIA AVISO NUMA DICA**, que a terceira lista dela
#: tira da tela. O daemon continua publicando `vpad_backend` e `vpad_motivo`, e
#: diz a queda para `uinput` no diário (`vpad_degradado`) — *"o layout não
#: informa os nossos defeitos"*, palavra dela de 07/09 citada em `aba01.py`.
#: Quem cobra que a marca não volte é
#: `tests/unit/test_a_marca_que_nunca_acende_e_o_gerador_que_confere.py`.
POR_CARTAO: tuple[str, ...] = ("plastico", "desenho", "jogador", "jogador-espera",
                               "bateria", "identidade", "mascara-cartao",
                               "marcador-principal")

#: QUANTOS `aviso-item` A COLUNA TEM. **Este é o dono do número**, e o gerador o
#: lê daqui (`aba01.py` importa esta constante) — a direção é essa e não a
#: inversa: o produto não pode depender do gerador, que puxa os SVGs e a folha
#: de estilo para montar uma página que ele nunca vai abrir.
#:
#: SÃO SEIS PORQUE SEIS É O QUE O PRODUTO SABE DIZER: `painel.AVISOS_DA_TELA`
#: tem seis fontes puras. O opt-out antigo e os achados graves do exame entram
#: por cima disso, e é por isso que a conta ao lado (`atencao-conta`) diz o
#: TOTAL e não o que coube — uma coluna que mostra 6 de 8 e escreve "6 avisos"
#: esconderia dois sem dizer que os escondeu.
AVISOS_VIVOS = 6

#: QUANTAS A COLUNA ACENDE — decisão dela, 04/09/2026 (D-09): *"Até três linhas,
#: o mais grave em cima."*, com ``+N`` se passar.
#:
#: SÃO DOIS NÚMEROS DIFERENTES, E ISSO NÃO É DESCUIDO. :data:`AVISOS_VIVOS` é
#: quantas linhas a PÁGINA publica (endereço, e endereço não move pixel); este é
#: quantas o PRODUTO acende. O quarto lugar recebe a linha do ``+N``, e os dois
#: que sobram ficam apagados — prontos para o dia em que ela subir o teto, o que
#: custa esta constante e nada mais. Cravar os dois no mesmo número faria a
#: coluna crescer até seis numa máquina ruim, que é o vão de 38 px que ela
#: reclamou em 31/08.
AVISOS_NA_COLUNA = 3

#: A ORDEM DA GRAVIDADE, do que mais dói para o que menos dói — a outra metade
#: da D-09 (*"o mais grave em cima"*).
#:
#: **O CRITÉRIO É "O QUE INVALIDA O QUÊ"**, e não uma escala de cor:
#:
#: 1. ``PAUSA`` — o produto inteiro está parado. Enquanto ela valer, TODAS as
#:    outras linhas descrevem coisas que não estão acontecendo;
#: 2. ``ERRO`` — uma fonte da coluna não respondeu. Não sabemos o que não
#:    estamos vendo, e isso vem antes de qualquer notícia que sobrou;
#: 3. ``GAMEPAD`` — o jogo recebe MENOS do que ela pediu (vpad degradado, ou a
#:    emulação desligada por uma escolha antiga);
#: 4. ``PONTE`` — por onde o jogo recebe o controle agora, quando a resposta é
#:    má notícia;
#: 5. ``JOGO`` — há jogo aberto fora do caminho do Hefesto;
#: 6. ``CONTROLE`` — o aparelho pode CAIR no meio da partida (a cura do
#:    travamento do USB não está de pé). Entra aqui, entre ``JOGO`` e
#:    ``RÁDIO``, pelo mesmo critério: a queda leva o controle inteiro, e o
#:    rádio frágil só atrapalha o jogo a enxergá-lo;
#: 7. ``RÁDIO`` — o transporte está frágil;
#: 8. ``PERFIL`` — o cadeado da troca automática e o detector cego.
#:
#: O QUE NÃO ESTÁ AQUI VAI DEPOIS, na ordem em que chegou: são os achados do
#: exame da mesa, que já vêm ordenados pelo dono deles
#: (`a08_conexoes._exame`). Uma lista que tentasse ranqueá-los aqui seria a
#: segunda cópia de uma escada que `secao_exame.ESCADA_DE_GRAVIDADE` já tem.
#:
#: **O SELO NOVO TINHA DE ENTRAR NA TUPLA, e não é asseio.** O que não está
#: aqui vai para DEPOIS DE TUDO (`posto.get(..., fim)` em
#: :func:`_coluna_de_avisos`) — que é o desenho certo para os achados do exame
#: e o errado para um selo nomeado neste arquivo: com a coluna mostrando três
#: de cada vez (:data:`AVISOS_NA_COLUNA`), um selo fora da escada é um selo que
#: a máquina cheia esconde atrás do ``+N``.
#: ``SERVIÇO`` ABRE A ESCADA — JOGAR-O-QUE-FALTA-01, Passo 5 (06/09/2026), e o
#: critério é o mesmo que já põe a ``PAUSA`` na frente: *o que invalida o quê*.
#: Com o serviço calado nem a PAUSA se sabe — ninguém respondeu se o produto
#: está parado ou correndo —, então toda outra linha desta coluna descreveria um
#: estado que a tela não leu.
#: ``MODO`` ENTRA AO LADO DE ``GAMEPAD`` — COOP-NA-CONEXAO-NATIVA-01, Caminho A
#: (06/09/2026), e o critério é o mesmo dos outros dois degraus nomeados aqui:
#: *o que invalida o quê*. Os dois respondem à MESMA pergunta — «como o jogo vê
#: os controles» — em modos que se excluem: o ``GAMEPAD`` fala do vpad
#: degradado, que só existe com o Hefesto no meio, e o ``MODO``
#: (``painel.aviso_do_modo_nativo``) só fala na Conexão Nativa, onde não há
#: vpad. Nunca disputam a mesma linha, e ficar vizinhos é o que impede a coluna
#: cheia de esconder um atrás do ``+N`` enquanto mostra o outro.
ORDEM_DA_GRAVIDADE: tuple[str, ...] = (
    "SERVIÇO",
    "PAUSA", "ERRO", "GAMEPAD", "MODO", "PONTE", "JOGO", "CONTROLE", "RÁDIO",
    "PERFIL",
)

#: O SELO DA PONTE. Não é um selo inventado: ``PONTE_PREFIXO`` do produto é
#: *"Ponte com o jogo: "* — a palavra é dele, e este selo é ela.
SELO_DA_PONTE = "PONTE"

#: O SELO DA CURA DO TRAVAMENTO — decisão dela, 06/09/2026: *"A cura do
#: travamento do USB entra na coluna Atenção"*, e o selo é ``CONTROLE``.
#:
#: **NÃO É ``RÁDIO``, E A DIFERENÇA IMPORTA NA TELA.** Esta cura é do **cabo**
#: (o mixer UAC do DualSense martelando o EP0, `storm_doctor._SND_QUIRK_RE`), e
#: quem já ocupa o selo ``RÁDIO`` é o `texto_do_radio_fragil`, que fala de
#: Bluetooth. Dois avisos com o mesmo selo, um do cabo e outro do rádio, é a
#: coluna mandando ela procurar no lugar errado.
#:
#: E NÃO É PALAVRA DE MÁQUINA: ``CONTROLE`` é o termo da tela para o aparelho
#: (`docs/A-LINGUA-DESTA-CASA`, §1) — o que cai no meio da partida é o
#: controle, e é isso que o selo diz.
SELO_DA_CURA = "CONTROLE"

#: O SELO DO SERVIÇO CALADO — Passo 5, e a palavra é a do glossário
#: (`docs/A-LINGUA-DESTA-CASA`, §1): na tela o `daemon` chama-se **serviço**.
SELO_DO_SERVICO = "SERVIÇO"

#: A FRASE DO SERVIÇO DESLIGADO — **é a da janela GTK, palavra por palavra**.
#: `home_actions._render_home` escreve ``self._home_session_label.set_text("O
#: Hefesto está desligado.")`` no ramo `offline`, e o `validar-palavra-de-tela`
#: já a declara como a tradução de "daemon offline" (`JARGAO_BANIDO`).
#:
#: POR QUE LITERAL AQUI, e não uma leitura: o dono dela é um `set_text` dentro de
#: um método de janela — lê-la em execução exigiria montar a GTK dentro do
#: pacote das dez abas, que é o que `_painel()` existe para evitar. **A
#: DIVERGÊNCIA MORRE PELA RÉGUA:** `test_a_aba_01_jogar_fecha_as_linhas` lê o
#: fonte da GTK e reprova no dia em que as duas se afastarem. É a mesma escolha
#: que a `MESA_VAZIA` e o `CADEADO_ROTULO` já fizeram, e pelo mesmo motivo.
SERVICO_DESLIGADO = "O Hefesto está desligado."

#: A SEGUNDA METADE, e ela é a que o Passo 5 comprou: **a tela dizendo que parou
#: de afirmar**. Só a primeira frase seria a notícia sem a consequência — e a
#: consequência é o que separa *"o serviço caiu"* de *"a tela quebrou"*.
#:
#: ELA NÃO NOMEIA BOTÃO NENHUM, de propósito: a janela GTK troca o rótulo para
#: "Ligar o Hefesto" (`home_actions._BTN_LABEL_OFFLINE`) e a interface nova não
#: tem esse botão com esse nome — mandar procurá-lo é a frase que o glossário
#: proíbe (*"qualquer frase que mande a pessoa procurar um botão ou uma janela
#: que não existe"*). O que ela promete é o que o produto de fato faz: o tique
#: continua correndo e a tela volta sozinha quando o serviço responder.
#:
#: PROVISÓRIO — texto de tela é palavra dela (PROVA-DE-TELA-01).
SERVICO_CALADO = (
    f"{SERVICO_DESLIGADO} Esta tela parou de ler o serviço. Ela volta sozinha "
    "quando ele responder."
)

#: A LINHA DO ``+N`` — o que a coluna diz quando não coube tudo.
#:
#: PROVISÓRIO — texto de tela é palavra dela (PROVA-DE-TELA-01). O que a D-09
#: fixou foi a FORMA (*"com `+N` se passar de três"*); a frase é minha até ela
#: ver. Ela nomeia as duas coisas que a pessoa precisa saber para não achar que
#: a coluna está mentindo: quantos ficaram de fora e por que critério.
def _linha_do_mais(quantos: int) -> tuple[str, str]:
    """``(selo, texto)`` da linha que fecha a coluna quando não coube tudo."""
    return (
        f"+{quantos}",
        f"mais {quantos} aviso" + ("s" if quantos != 1 else "")
        + f" — a coluna mostra {AVISOS_NA_COLUNA} de cada vez, do mais grave.",
    )


#: A FRASE DA MESA VAZIA — decisão dela, 04/09/2026 (D-07): *"Uma frase por cima
#: dos lugares apagados."*
#:
#: **ELA JÁ EXISTIA, E NO LUGAR ERRADO**: a bancada `interface/jogar_vivo.py`
#: escreve esta mesma sentença desde que nasceu, e o PRODUTO — a página
#: estática, que é a que ela abre — não a tinha. A cópia aqui é a mesma sequência
#: de bytes de propósito, e :func:`o_gemeo_da_bancada_ainda_bate` (na régua
#: `tests/unit/test_a01_a_mesa_vazia_fala.py`) reprova no dia em que as duas se
#: afastarem. Quem cuidar de `jogar_vivo.py` fecha isto com uma linha: importar
#: esta constante em vez de repetir a frase.
MESA_VAZIA = (
    "Nenhum controle ligado. Conecte um pelo cabo ou pelo "
    "rádio: ele aparece aqui sozinho."
)

#: QUANTOS LUGARES A PÁGINA TEM. O dono é o desenho (`monta.MESA`), e o número
#: se LÊ dele — cravar `4` aqui é o que faz a tela contar uma coisa e mostrar
#: outra, que é exatamente o defeito que a linha do ``+N`` existe para fechar.
def lugares_da_mesa() -> int:
    """Quantos cartões a página publica. Lido de `monta.MESA`, nunca digitado."""
    return len(_monta().MESA)


#: A RESSALVA DA MÁSCARA — 04/09/2026, e ela é a queixa 1 dela:
#: *"independente do modo a mascara deve funcionar ali sempre."*
#:
#: O QUE FOI MEDIDO, e decide a forma desta cura: `gamepad.mask.set` grava
#: SEMPRE (`ipc_handlers.py:6812`, sem gate de modo), `set_mask` persiste em
#: `controller_masks.json` e `mascara_efetiva` é consultada na criação de todo
#: gamepad virtual (`gamepad.py:2162`, `uinput_gamepad.py:419`). **Logo a
#: escolha dela JÁ vale sempre que pode valer** — o que faltava não era motor,
#: era a tela dizer que a escolha ficou guardada.
#:
#: POR QUE RESSALVA E NÃO CINZA, e é a diferença entre as duas metades da D-03:
#: um botão fica cinza quando ele **não pode funcionar**. Este pode: clicar fora
#: do modo jogo grava a escolha, e o vpad nasce com ela quando o modo voltar.
#: Apagar o chip diria *"você não pode escolher agora"*, que é FALSO — e trocaria
#: a queixa dela (*clico e não acontece nada*) por outra pior (*clico e nem
#: deixa*). O cinza fica onde ele é verdade: no chip que o produto não sabe
#: montar (ver :func:`mascaras_montaveis`).
#:
#: PROVISÓRIO — texto de tela é palavra dela.
RESSALVA_DA_MASCARA = (
    "Guardada neste controle. Ela passa a valer quando o Hefesto voltar a "
    "entregá-lo ao jogo."
)

#: O RÓTULO E A DICA DO CADEADO — **as duas palavras são da JANELA ANTIGA**, e
#: por isso não são texto novo de tela: o `Gtk.CheckButton` de
#: `home_actions._build_home` já as escreve, e o pedido da caixa é dela, de
#: 23/07/2026.
#:
#: POR QUE LITERAL AQUI, e não uma leitura: o dono delas é um `Gtk.CheckButton`
#: construído dentro de um método de janela — lê-las em tempo de execução
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

#: O RÓTULO É PALAVRA DELA, de 11/09/2026, e são três: **«Trava o perfil
#: ativo»**. A frase anterior — sete palavras descrevendo o mecanismo — passou a
#: ser dita pela `CADEADO_DICA`, que já a dizia melhor. O curto na tela, o longo
#: no ponteiro do mouse: é a mesma divisão que as outras dicas desta aba fazem.
#: Não se enfeita nem se alonga para preencher a linha do título do bloco.
#:
#: **QUEM TROCAR ESTA PALAVRA TROCA O `label=` DO `Gtk.CheckButton` JUNTO** —
#: `app/actions/home_actions._build_home` —, e lá o literal fica quebrado em
#: três linhas DE PROPÓSITO. Medido em 11/09/2026: colapsá-lo numa linha só
#: encurtou o `home_actions.py` em dois números, e o portão `citacoes-no-codigo`
#: reprovou com DUAS âncoras de linha — em `app/actions/footer_actions.py` e
#: neste arquivo — caindo em linha em branco. O texto muda; o tamanho do
#: arquivo, não.
#:
#: **A PALAVRA MUDOU EM 23/09/2026, e é dela** (D-2309-O-MODO-FREESTYLE):
#: *"o botão Trava o perfil Ativo na aba jogar. Vira Modo Freestyle o botão."*
#: O que o botão FAZ não mudou — é o mesmo `autoswitch.lock`, e a dica abaixo
#: continua a razão dele. O que mudou foi o nome, a letra e a altura, e os três
#: estão no DESENHO (`aba01.py`), publicado em 24/09/2026 por delegação dela.
CADEADO_ROTULO = "Modo Freestyle"
#: «Desmarque» virou «Desligue» em 24/09/2026 (O-MODO-FREESTYLE-02): a caixa
#: virou pílula em 19/09, e pílula se liga e se desliga. A gêmea da GTK foi junto.
CADEADO_DICA = (
    "O perfil ativo continua valendo mesmo quando você abre outro jogo. "
    "Desligue para o Hefesto voltar a escolher sozinho."
)

#: O QUE A TELA DIZ QUANDO O SERVIÇO NÃO CONFIRMOU O CADEADO — e a frase é da
#: janela antiga, palavra por palavra, como as duas acima.
#:
#: `ipc_bridge.autoswitch_lock_set` responde TRÊS coisas, e é a terceira que
#: obriga esta frase a existir: `True` e `False` são o estado que ficou valendo,
#: e `None` quer dizer *não houve resposta* — serviço parado, socket recusado,
#: o teto do `_safe_call` estourando. O `_on_home_autoswitch_lock_toggled` da
#: janela antiga já tratava os três, e esta é a frase que ele põe na tela dela
#: no terceiro caso.
#:
#: **REUSAR EM VEZ DE ESCREVER, e o motivo é o de sempre:** texto de tela novo é
#: palavra dela (PROVA-DE-TELA-01), e esta ela já leu. A régua
#: `test_a_palavra_do_cadeado_e_a_que_ela_ja_leu` confere as TRÊS contra o fonte
#: da GTK — no dia em que a janela antiga trocar a palavra, a tela nova não fica
#: falando sozinha.
CADEADO_RECUSA = "O Hefesto está desligado: a trava não foi aplicada."


#: AS TRÊS PALAVRAS DO INTERRUPTOR — e o dono delas é a aba Controles.
#:
#: `a02_controles._selo_do_sensor` emite exatamente estas para os botões do
#: Giroscópio e do Acelerômetro, e o desenho lê a do meio em
#: `data-hef-quando="DESLIGADO"`. **Não se importa a função** — importá-la
#: acoplaria dois pacotes de aba por uma constante de três palavras —, mas a
#: LÍNGUA é uma só, e é por isso que ela está nomeada aqui em vez de digitada
#: dentro do `return`. Duas palavras para o mesmo "ligado" seria a segunda
#: verdade que esta casa mata.
CADEADO_LIGADO = "LIGADO"
CADEADO_DESLIGADO = "DESLIGADO"


def _cadeado(state: dict[str, Any]) -> str:
    """``LIGADO`` · ``DESLIGADO`` · travessão — as três respostas da trava.

    **A LÍNGUA MUDOU EM 19/09/2026, com a caixa** (`TRAVA-PILULA-01`, pedido
    dela). Até aqui isto devolvia ``"sim"``/``""`` para o alvo `marcado`, o
    décimo da ponte e o único que escreve `el.checked`. A trava virou
    `<button class="cadeado">` com a gramática do `.sw` da aba Controles, e o
    alvo passou a ser `classe` + `data-hef-quando="DESLIGADO"`.

    **O TERCEIRO ESTADO DEIXOU DE SER MENTIRA, e é o que a troca ganha de
    graça.** Um checkbox tem DOIS estados e o produto tem três; a nota que
    morava aqui declarava o remendo: *"sem daemon a caixa desmarca"* — a tela
    mostrava DESTRAVADO sobre um estado que ninguém tinha lido. A pílula
    responde as três: acesa, apagada, ou nenhuma das duas quando o travessão
    chega e classe nenhuma casa.

    SÓ O ``True`` LITERAL LIGA, a mesma disciplina do `wrapper_used` e do
    `texto_da_pausa`: chave ausente (daemon antigo) ou valor de outro tipo
    **não** acendem — caem no travessão, que é o "não sei" honesto.
    """
    lido = state.get("autoswitch_locked")
    if lido is True:
        return CADEADO_LIGADO
    if lido is False:
        return CADEADO_DESLIGADO
    return TRAVESSAO


#: A PALAVRA DO MARCADOR — **é a da janela GTK**, e não uma escolha minha:
#: `home_actions._format_controller_subtitle` monta a linha secundária do card e
#: acrescenta exatamente ``"primário"`` quando ``is_primary``. O CSV nomeia esta
#: dívida pela palavra dela (*"o marcador 'primário' no card do controle
#: principal"*).
#:
#: POR QUE LITERAL, e não uma leitura: o dono a monta DENTRO de uma lista de
#: partes, colada por ``"  ·  "`` — importar aquela função para arrancar um
#: pedaço da frase seria mais frágil que a régua. **A DIVERGÊNCIA MORRE PELA
#: RÉGUA:** `test_a_aba_01_jogar_fecha_as_linhas` lê o fonte da GTK e reprova no
#: dia em que a palavra mudar de lá. Mesma escolha do `CADEADO_ROTULO`.
MARCA_DO_PRIMARIO = "primário"

#: A DICA DO MARCADOR. Ela é `title`, logo CRAVADA no desenho (o piloto não tem
#: alvo de pintura para atributo de texto), e o que a torna honesta é não
#: afirmar nada sobre um controle em particular: ela explica o ESTADO, igual
#: para os quatro cartões, e quem diz de quem é o estado é a classe.
#:
#: A FRASE NÃO É NOVA NO ASSUNTO: quem é o primário é quem navega o PC
#: (`a06_navegacao`, cabeçalho: *"O QUE TEM DONO: quem é o PRIMÁRIO
#: (`is_primary`) — e é ele quem navega o PC"*), e é dele que o daemon publica a
#: leitura de botões (`a02_controles`: *"o daemon só publica `inputs` para o
#: `is_primary`"*). As duas coisas são medidas, e é isso que a dica diz.
#:
#: PROVISÓRIO — texto de tela é palavra dela (PROVA-DE-TELA-01).
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
    """Os rótulos de máscara que o produto SABE MONTAR — para o desenho perguntar.

    O gerador (`aba01._chips_de_mascara`) apaga o chip que não estiver aqui e
    põe a razão na dica: é a D-03 dela (*"cinza antes, com a razão na dica"*).

    NOTA DATADA — 07/09/2026: até hoje havia UM chip que recusava em todo modo, o
    **Nintendo Pro**, e esta docstring o nomeava. A máscara nasceu (ordem dela),
    e o chip acendeu **sem uma linha de edição em lugar nenhum desta aba** —
    que é exatamente o que o parágrafo abaixo prometia, agora medido:
    `mascaras_montaveis()` devolve os três rótulos. Nenhum chip recusa em todo
    modo hoje.

    **NADA SE DIGITA.** `external_mask.mascaras_validas()` é o catálogo do vpad
    (ele próprio derivado de `uinput_gamepad.FLAVORS`) e `mesa_viva.
    NOME_DA_MASCARA` é a tradução flavor → rótulo que a pintura já usa. Uma
    máscara nova no produto acende o chip dela na próxima geração, sem uma linha
    de edição — e é isso que separa esta cura de apagar o chip à mão, que
    envelheceria no dia em que o produto aprendesse a montá-lo.

    O CHIP NÃO PERDE O CLIQUE ao ficar cinza, e é escolha: `mascara_do_controle`
    recusa DIZENDO o nome e as que existem. Tirar o `data-gesto` faria o clique
    sumir calado — que é o defeito que este arquivo inteiro persegue.
    """
    from hefesto_dualsense4unix.daemon.subsystems.external_mask import mascaras_validas
    from hefesto_dualsense4unix.interface.mesa_viva import NOME_DA_MASCARA

    return frozenset(
        NOME_DA_MASCARA[f] for f in mascaras_validas() if f in NOME_DA_MASCARA)


@registrar("01-jogar.html")
def pacote(ctx: Contexto) -> dict[str, Any]:
    """Os valores da aba Jogar, com os NOMES que a página tem.

    CADA CHAVE AQUI É UM `data-campo` DO `01-jogar.html`, e isso não é
    coincidência: até 01/09/2026 os dois lados foram escolhidos separadamente, e
    esta aba pintava UM valor de cinco. O pacote emitia `mascara` e a página
    tinha `identidade`; emitia `conta_b` e a página tinha `conta-b`. Nenhuma
    máquina sabia que eram a mesma coisa, e o `querySelector` de um endereço que
    não existe não levanta — devolve `null`, e a pintura escreve zero.

    `src/hefesto_dualsense4unix/interface/casamento.py` é a régua que passou a medir isso.
    """
    # A MÁSCARA DA SESSÃO, uma vez: ela é a HERANÇA de quem não escolheu, e não
    # o valor. Quem sabe a diferença é `mascara_efetiva`, no daemon; aqui ela só
    # entra como último recurso, quando a mesa chega sem a chave — uma régua com
    # mesa de mentira, ou um daemon velho, anterior ao `por_aparelho`.
    da_sessao = _rotulo_da_mascara(_mascara_da_sessao(ctx.state))
    # A PALAVRA DO TRANSPORTE VEM DA FUNÇÃO DONA — ONDA4-S10, 06/09/2026, e a
    # decisão é dela (D-05): *"cabo / rádio, pela função que já existe."* O
    # import é TARDIO pela rota das dez abas (ver `:685`, `:875`, `:922`,
    # `:1092`): `pacotes/__init__.py` declara por escrito que importar GTK no
    # topo deste módulo é o que se evita aqui.
    from hefesto_dualsense4unix.app.actions.home_actions import palavra_do_transporte

    cartoes = {}
    for c in ctx.conectados:
        uniq = str(c.get("uniq") or "")
        # A IDENTIDADE É `nome · transporte`, como o desenho a escreve
        # ("Cosmic Red · cabo") — e não a máscara. Sai da MESA, que é quem já
        # leu a cor do plástico; o `conectados` cru não tem o nome do modelo.
        casa = next((m for m in ctx.mesa if str(m.get("uniq") or "") == uniq), {})
        nome = casa.get("nome") or "—"
        # O TERCEIRO DIALETO MORREU AQUI — ONDA4-S10, 06/09/2026. Esta linha
        # era `casa.get("via") or (c.get("transport") or "").upper()`: o degrau
        # de reserva GRITAVA o valor cru em maiúsculas quando a mesa não trazia
        # `via`, e devolvia `""` quando o daemon não publicava o transporte —
        # um `·` seguido de nada no cartão dela. A dona tem resposta melhor
        # para os dois casos: a palavra do mapa de canais, e
        # `"não sei por onde"` para a AUSÊNCIA. Ler a `via` da mesa aqui seria
        # a sigla de máquina (`USB`/`BT`) na frase de quem joga.
        via = palavra_do_transporte(casa.get("transporte") or c.get("transport"))
        cartoes[uniq] = {
            # A COR DO PLÁSTICO — 03/09/2026, IDENTIDADE-VEM-DE-CIMA-01. Ela é a
            # borda do cartão, e até hoje vinha cravada do desenho: com o
            # controle DELA no cabo (White) a borda continuava Cosmic Red, três
            # centímetros abaixo de uma fita que já dizia White. A lei é dela:
            # *"se no topo tá mostrando controle white player 1, então cada aba
            # vai usar os controles lá de cima. Não mistura com a info dos
            # mockups."*
            #
            # `""` QUANDO NÃO SE SABE, e não é desistência: a cor chega pelo
            # broker, uma vez por endereço e em thread, então o primeiro tique
            # de uma sessão tem a mesa sem cor — e o controle por RÁDIO pode não
            # ter cor nenhuma enquanto a ONDA-CONEXOES-11 não entrar. O alvo
            # `cor` apaga o `style.color` no vazio e a pele volta ao neutro do
            # CSS. Regra dela: campo sem informação não mostra nada.
            "plastico": _cor_do_plastico(str(casa.get("cor") or "")),
            # O DESENHO — 03/09/2026, e ele é a outra metade da mesma queixa:
            # *"os svgs do dualsense (…) não são os que o meu mapa cataloga"*.
            # O valor é o SLUG do colorway (`white`, `galactic-purple`), que é
            # o que o `svg[data-colorway="…"]` da folha das 28 casa — e não o
            # hex, que é o que a `plastico` acima escreve.
            #
            # `""` QUANDO A COR NÃO É PINTÁVEL, pela mesma régua da borda: o
            # `_cor_do_plastico` já devolve `""` para slug vazio e para modelo
            # que o SVG não conhece, e amarrar as duas aqui é o que impede a
            # tela de afirmar um modelo cuja cor ela não consegue mostrar. Sem
            # atributo, nenhuma regra casa e o desenho vai ao neutro — que é a
            # regra dela: campo sem informação não mostra nada.
            "desenho": _colorway_do_desenho(str(casa.get("cor") or "")),
            # `jogador_de` E NÃO `c.get("player")`: o daemon publica DUAS
            # chaves, e o `player` volta `None` no controle que o co-op não
            # numerou — medido em 02/09/2026 com o do CABO. Ler só ele escrevia
            # "Player —" na tela para um controle que a Iluminação, três linhas
            # abaixo, mostrava com o botão 2 ACESO. O dono lê `player_slot`
            # antes, que é a ordem da GTK (`controller_card.py:1059-1067`).
            "jogador": f"Player {jogador_de(c) or '—'}",
            # O ESMAECIDO — decisão [02], 04/09/2026. A palavra fica (D-04
            # dela); o que sai é a AFIRMAÇÃO de um jogador que o jogo ainda não
            # recebeu. Ver `_jogador_esperando`.
            "jogador-espera": _jogador_esperando(c),
            "bateria": f"{c.get('battery_pct')}%" if c.get("battery_pct") is not None else "—",
            "identidade": f"{nome} · {via}",
            # A MÁSCARA DESTE APARELHO — ver `_mascara_do_cartao` e a nota do
            # `POR_CARTAO`. Ela é a decisão dela de 03/09: *"É uma máscara por
            # controle."*
            "mascara-cartao": _mascara_do_cartao(casa, da_sessao),
            # QUEM É O PRIMÁRIO — Passo 3. `"1"`/`""` na língua do alvo `classe`
            # booleano, a mesma do `jogador-espera` logo acima: a PALAVRA está
            # no arquivo e o produto só decide se ela aparece. Ver
            # `_e_o_primario`.
            "marcador-principal": _e_o_primario(c),
            # A MARCA DA EMULAÇÃO DEGRADADA SAIU DAQUI — 13/09/2026. O cartão
            # não emite mais `degradou-cartao`, e a razão está na nota do
            # `POR_CARTAO`. O daemon continua publicando `vpad_backend` e
            # `vpad_motivo` no estado e dizendo a queda no diário
            # (`vpad_degradado`); o que parou foi a tela repetir o aviso num
            # `title` que o WebKit nunca deixou acender.
        }

    # A COLUNA ATENÇÃO NÃO É MAIS PINTADA NESTA ABA — 07/09/2026, ordem dela. As
    # onze fontes continuam vivas em `_avisos`, que continua sendo chamado por
    # quem quiser mostrá-las; esta função parou de emitir os quatro endereços
    # porque a página parou de ter onde pousá-los.

    # A FAIXA LARANJA NÃO FALA MAIS — 13/09/2026, JOGAR-A-FAIXA-QUE-PULA-01 §3.2.
    # A pendência continua medida pela dona (`_faixa_do_pendente`) e vai para o
    # diário da janela. Os três endereços seguem saindo em TODO tique, porque o
    # que estava cravado na página é uma frase, e uma frase só se apaga
    # escrevendo por cima.
    #
    # A ÚNICA FRASE QUE ELA FALA é a do «Steam Input» que espera a Steam fechar
    # — 24/09/2026, a escolha dela (`D-2309-STEAM-INPUT-A-FRASE-E-O-CLIQUE`):
    # *"frase curta"*, e não *"sem frase"*. Ver :func:`_o_que_o_chip_diz`.
    _relatar_a_pendencia(_faixa_do_pendente(ctx.state)[0])
    tela = _a_fileira_com_a_mesa(_estado_da_tela(ctx.state), ctx.mesa)
    espera = _o_que_o_chip_diz(ctx.state, tela)

    fora: dict[str, Any] = {
        # A FRASE DA MESA e a RESSALVA DA MÁSCARA — as duas saem SEMPRE,
        # inclusive vazias, pela mesma razão da faixa laranja: o que se apaga é
        # o que se escreve por cima. O `""` vira travessão no piloto, e o alvo
        # `classe` do elemento de fora lê travessão como desligado.
        "mesa-frase": _frase_da_mesa(ctx),
        "mascara-ressalva": _ressalva_da_mascara(ctx.state),
        # O CADEADO — decisão [03], 04/09/2026. Ver `_cadeado`.
        "cadeado": _cadeado(ctx.state),
        # E A RESSALVA DELE — 07/09/2026. Emitida em TODO tique, vazia
        # inclusive, pela mesma razão das duas acima: chave ausente deixaria a
        # frase velha na tela depois de o detector voltar a enxergar, e a linha
        # passaria a ressalvar um estado que acabou. Ver `_cadeado_cego`.
        CADEADO_CEGO: _cadeado_cego(ctx.state),
        "cartoes": cartoes,
        # O INTERRUPTOR E A FILEIRA, VIVOS — 03/09/2026. Ver `_estado_da_tela`;
        # e a fileira apaga com a mesa vazia, ver `_a_fileira_com_a_mesa`.
        **tela,
        "pendente": espera,
        "pendente-alvo": "",
        # O INTERRUPTOR DA FAIXA, e é ele que esconde a caixa tracejada: sem
        # `.ha` o travessão que o piloto escreve no vazio não aparece (medido
        # em 02/09/2026). O espaço continua reservado, então o «Reconectar
        # controles» não anda quando a frase acende.
        "pendente-ha": "1" if espera else "",
        # O RÓTULO DO CHIP «STEAM INPUT» — ele muda enquanto está armado. Ver
        # :func:`_o_rotulo_do_chip`; sai em TODO tique para REPOR o rótulo
        # quando o relógio vence.
        "blocos": _o_rotulo_do_chip(ctx.state),
        # OS CONTROLES QUE O HEFESTO SÓ VÊ — EXTERNOS-01. Ver
        # :func:`_html_dos_externos`.
        "externos": _html_dos_externos(ctx),
    }
    fora["cobertura"] = {
        # A PROMESSA, e ela se conta sozinha: `DA_PAGINA` e `POR_CARTAO` são as
        # listas de endereço, e emitir uma chave sem pô-la lá deixa o contador
        # menor que o pacote — que é o defeito que este número existe para
        # denunciar.
        "pintados": len(DA_PAGINA) + len(cartoes) * len(POR_CARTAO),
        "sem_dono": 0,
    }
    # `perfil` e `conta-b` NÃO saem daqui: são do cabeçalho, que é das
    # dez abas, e o dono deles é `pacotes.topo()`. Emiti-los aqui criava um
    # segundo dono — e foi assim que `conta_b` (com underscore) conviveu com o
    # `conta-b` da página sem nunca casar.
    return fora


def _cor_do_plastico(slug: str) -> str:
    """O hex da casca daquele modelo, ou `""` quando ninguém sabe ainda.

    O DONO DO HEX É `monta.cor_da_zona`, e ele não se digita: ele LÊ a folha que
    pinta o desenho (`scripts/gerar_cores_do_dualsense.py`), que por sua vez sai
    do `docs/data/cores-do-dualsense.csv` — 28 modelos e 10 zonas. É a mesma
    fonte que o chip da fita usa, e é o que faz a borda do cartão não poder
    discordar do chip três linhas acima.

    POR QUE ESTA GUARDA EXISTE EM VEZ DE CHAMAR `cor_da_zona` DIRETO:
    `cor_da_zona` levanta `SystemExit` para colorway que o SVG não tem, e um
    modelo novo derrubaria a pintura da aba INTEIRA — trocaríamos uma borda que
    falta por uma tela congelada. O `""` é o caminho honesto: sem hex, sem cor.

    ELA É GÊMEA DA `a04_iluminacao._cor_do_plastico`, e a cópia é deliberada.
    Importar a privada de outra aba acopla esta aba ao arquivo que outra frente
    está editando no mesmo dia; o que NÃO se duplica é o dado — o hex continua
    tendo um dono só, e é o `cor_da_zona` que as duas chamam.

    O `except` PEGA `BaseException` DE PROPÓSITO, e não é descuido: `SystemExit`
    **não** herda de `Exception`, então um `except Exception` aqui deixaria
    passar exatamente o caso que esta guarda existe para segurar. A gêmea da
    `a04` escreve `except Exception` e por isso não segura nada — está anotado
    para quem cuidar daquela aba.
    """
    if not slug:
        return ""
    try:
        import monta  # o `pacotes/__init__` põe `interface/` no `sys.path`

        # `cor_de_css` E NÃO `cor_da_zona` — 03/09/2026. Oito dos 28 modelos
        # dela não têm hexa amostrado e devolvem `url(#hachura-sem-hex)`, que
        # o CSSOM RECUSA EM SILÊNCIO num campo de cor — e o que ficava na
        # tela era o Cosmic Red do MOCKUP, sob um desenho que dizia outro
        # modelo. Ver a razão inteira em `monta.cor_de_css`.
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
    `gui.aba_conexoes.SELO_DO_ESTADO`, que é o dono da palavra. As duas palavras
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

    **ISTO É PROPOSTA, NÃO ENTREGA.** `aba09.py` e `a09_sistema.py` são de outra
    frente, e escrever nelas no mesmo dia é a colisão que esta casa evita por
    posse de arquivo. Enquanto a 09 não os recebe, **as dez estão caladas no
    produto** — está RELATADO, e é o preço declarado da ordem dela, não um
    esquecimento.

    **NÃO APAGUE ESTA FUNÇÃO POR ESTAR SEM CHAMADOR NA TELA.** Ela é o único
    ponto do produto novo que reúne as onze; apagá-la faria a frente da 09
    reescrever de zero as onze chamadas, com os quatro `try` próprios e a ordem
    de gravidade que já estão medidos aqui.

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
       notícia;
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
    painel = _painel()
    # O SERVIÇO CALADO VEM ANTES DE TUDO, e é a única fonte desta coluna que
    # RESPONDE SOBRE A AUSÊNCIA de estado — ver `_aviso_do_servico_calado`. As
    # outras perguntam ao `state`; sem ele, todas calam, e o silêncio delas
    # era a tela dizendo "nenhum aviso" sobre um estado que ninguém leu.
    calado = _aviso_do_servico_calado(ctx)
    fora: list[dict[str, str]] = [calado] if calado else []
    fora += list(painel.avisos_do_estado(ctx.state))

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

    ponte = _aviso_da_ponte(ctx.state)
    if ponte:
        fora.append(ponte)

    # A DIVERGÊNCIA DE MÁSCARA — JOGAR-OS-SEIS-AVISOS-01, 06/09/2026, e ela vem
    # logo depois da ponte porque é a irmã dela: as duas voltam em markup do
    # Pango e passam por `_sem_markup`. Sob `try` PRÓPRIO, que é a política
    # deste arquivo — uma fonte que levanta vira selo `ERRO`, nunca uma coluna
    # que some.
    try:
        divergencia = _aviso_da_divergencia_de_mascara(ctx.state)
        if divergencia:
            fora.append(divergencia)
    except Exception as erro:
        fora.append({"selo": "ERRO",
                     "texto": f"a divergência de máscara não respondeu "
                              f"({type(erro).__name__}).",
                     "fonte": "home_actions.mascara_divergente_do_daemon"})

    # A CURA DO TRAVAMENTO DO USB — sob `try` PRÓPRIO, que é a política deste
    # arquivo: uma fonte que levanta não derruba a coluna, ela vira selo
    # ``ERRO``. Esta lê DOIS ARQUIVOS DO SISTEMA por chamada — se um `/sys`
    # remontado ou um `/etc` sem permissão levantar, as outras continuam
    # valendo.
    #
    # FATO SUBSTITUÍDO — 06/09/2026, ONDA5-07-03. Estas linhas diziam que esta
    # é *"a primeira desta coluna que toca o disco a cada tique"*, e não é: o
    # aviso do selo ``JOGO`` (`home_actions.aviso_do_wrapper`, uma das seis de
    # `AVISOS_DA_TELA`) lê as duas listas de recusa dela desde 05/09 — só que
    # SÓ quando há jogo aberto sem o atalho, que é o caso raro. As duas somadas
    # foram medidas: 0,050 ms por tique, contra 2,85 ms de mediana do tique.
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

    O MARKUP NÃO CHEGA À TELA: `gui.aba_sistema.sem_markup` é o dono de tirá-lo
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
    # O PREFIXO SAI porque o SELO É ELE. Deixar os dois escreveria
    # "PONTE  Ponte com o jogo: nenhuma —…" na mesma linha, que é a repetição
    # que esta casa tira do `<title>` do glifo e do `title` do cartão.
    if texto.startswith(home_actions.PONTE_PREFIXO):
        texto = texto[len(home_actions.PONTE_PREFIXO):]
    return {"selo": SELO_DA_PONTE, "texto": texto,
            "fonte": "home_actions.texto_da_ponte"}


def _sem_markup(frase: str) -> str:
    """O texto de uma frase do produto, sem o markup do Pango. UMA porta só.

    **ELA EXISTE PARA A CITAÇÃO SER UMA, e isso é portão** — 06/09/2026,
    JOGAR-OS-SEIS-AVISOS-01. Duas fontes desta coluna voltam em markup (a ponte
    e a divergência de máscara), e quem sabe tirá-lo mora na janela que está
    saindo. `scripts/check_nada_aponta_para_a_janela.py` congela o inventário e
    reprova tanto uma citação NOVA quanto um par declarado cuja **contagem
    cresce** — este arquivo tem uma linha declarada, e ela tem de continuar
    sendo uma. Um segundo `import` ao lado do outro aviso reprovaria o portão
    sem acrescentar uma linha de valor.

    **E NÃO SE REESCREVE A REGEX AQUI.** `sem_markup` é o dono, e a expressão
    dele desescapa a entidade HTML além de tirar a tag — um `re.sub` local
    deixaria `&quot;` na tela. Quando o motor mudar de casa
    (`MOTOR-MUDA-DE-CASA`, a razão declarada no inventário), é esta linha que
    troca de endereço, e uma só.
    """
    from hefesto_dualsense4unix.gui.aba_sistema import sem_markup

    return sem_markup(frase)


def _aviso_da_divergencia_de_mascara(state: dict[str, Any]) -> dict[str, str] | None:
    """A escolha de máscara que não chegou ao aparelho; ``None`` quando chegou.

    **O DAEMON PUBLICA ISTO DESDE A MASCARA-01 e a interface nova nunca leu** —
    é o mesmo defeito que a I3 nomeou na janela antiga (*"o ALARME que ele já
    publicava e que esta janela nunca leu"*), reintroduzido na migração.
    JOGAR-OS-SEIS-AVISOS-01, 06/09/2026.

    **POR QUE AQUI E NÃO EM `painel.AVISOS_DA_TELA`, que é onde moram as outras
    onze.** Ela é a irmã do `_aviso_da_ponte` logo acima em UMA coisa que decide
    o endereço: as duas voltam em **markup do Pango**, e tirá-lo custa uma
    citação a `gui/`. De `app/actions/` aquela citação seria NOVA, e o portão
    `nada-aponta-para-a-janela` reprova — a janela está saindo
    (`D-0609-GTK-LEVA-INTEIRA`) e o inventário só encolhe. Aqui ela é a
    declarada, e passa por `_sem_markup`, que é a porta única.

    DUAS FUNÇÕES DO DONO, e nenhuma regra escrita aqui:

    * `home_actions.mascara_divergente_do_daemon` escolhe **o alarme**, e não a
      lista irmã: ``mascara_divergencias`` é antecipação de jogo FECHADO, e
      mostrar divergência de jogo que não está em cena seria aviso sobre coisa
      que não está em uso;
    * `home_actions.texto_da_divergencia` escreve a frase, e escolhe entre as
      QUATRO que ela tem — jogo aberto ou não, gesto dela ou perfil.

    **A FONTE É O PERFIL, e não o dedo dela, porque é o que o alarme sabe.** O
    payload traz ``profile`` e ``mascara_perfil``: quem pediu aquela máscara foi
    o perfil, que entra sozinho pelo autoswitch. Dizer *"você escolheu"* sobre
    ele é a acusação que a I3 tirou da tela — e aqui não há sequer de onde
    inventar o gesto, porque o ``_home_flavor_pedido`` era um atributo de janela
    e a janela saiu.

    O SELO É ``GAMEPAD``, o mesmo do vpad degradado e do grab dobrado: os três
    respondem à mesma pergunta — **como o jogo vê os controles**. Um selo novo
    aqui ficaria fora de `ORDEM_DA_GRAVIDADE` e a máquina cheia o esconderia
    atrás do ``+N``.
    """
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
    # IMPORT TARDIO, pela rota das dez abas (`pacotes/__init__.py` declara por
    # escrito que se evita importar no topo deste módulo).
    from hefesto_dualsense4unix.integrations import storm_doctor

    selo, frase = storm_doctor.check_snd_quirk()
    if selo == storm_doctor.OK:
        return None
    return {"selo": SELO_DA_CURA, "texto": str(frase),
            "fonte": "storm_doctor.check_snd_quirk"}


def _coluna_de_avisos(avisos: list[dict[str, str]]) -> tuple[list[str], list[str]]:
    """``(selos, textos)`` da coluna — o mais grave em cima, e o ``+N`` no fim.

    A D-09 dela, em duas metades: *"Até três linhas, o mais grave em cima"*,
    *"com `+N` se passar de três"*.

    A ORDENAÇÃO É ESTÁVEL, e isso é o que faz a coluna parar quieta: dois
    avisos do mesmo selo mantêm a ordem em que as fontes falaram, então a linha
    não troca de lugar a cada tique só porque um dicionário mudou de humor. O
    que não está em :data:`ORDEM_DA_GRAVIDADE` cai depois de tudo, na ordem de
    chegada — são os achados do exame, que já vêm ordenados pelo dono.

    O ``+N`` OCUPA UMA LINHA, e ela não sai do teto: com quatro avisos a coluna
    mostra três e diz "+1". Somar o ``+N`` ao teto faria a coluna mostrar três
    avisos e a linha do "+1" só a partir do QUINTO, escondendo o quarto sem
    contá-lo — que é o defeito que esta linha existe para fechar.

    E A CONTA AO LADO CONTINUA DIZENDO O TOTAL (`atencao-conta`, do
    `painel.texto_da_conta`): ela conta os avisos, não as linhas. Uma coluna que
    mostrasse 3 e escrevesse "3 avisos" com cinco na máquina esconderia dois sem
    dizer que os escondeu.
    """
    posto = {selo: i for i, selo in enumerate(ORDEM_DA_GRAVIDADE)}
    fim = len(ORDEM_DA_GRAVIDADE)
    ordenados = sorted(avisos, key=lambda a: posto.get(str(a.get("selo") or ""), fim))

    selos = [str(a["selo"]) for a in ordenados[:AVISOS_NA_COLUNA]]
    textos = [str(a["texto"]) for a in ordenados[:AVISOS_NA_COLUNA]]
    sobra = len(ordenados) - AVISOS_NA_COLUNA
    if sobra > 0:
        selo, texto = _linha_do_mais(sobra)
        selos.append(selo)
        textos.append(texto)
    # AS SEIS SAEM SEMPRE, com `""` no que não tem aviso — e esta linha é uma
    # CURA, não asseio. Medida no DOM vivo em 04/09/2026, com a máquina dela sem
    # um aviso: a coluna mostrava *"RÁDIO · Dois rádios da bancada estão em
    # portas vizinhas"* ao lado de *"nenhum aviso"* — a mesma tela afirmando duas
    # coisas contrárias. A frase é do MOCKUP (`aba01.AVISOS`, cena declarada), e
    # ninguém a apagava.
    #
    # A CAUSA NÃO É DAQUI, e está nomeada para quem cuidar do despachante:
    # `pacotes.normalizar` descarta lista VAZIA (`if valor and all(...)`, e
    # `all([])` já seria `True`), então os três endereços não chegavam ao JS e o
    # piloto **nunca visitava** os seis elementos — medido pelo selo da visita,
    # `data-hef-visto` ausente nos seis. Vale para toda aba que emita lista: os
    # achados do exame na 08 e a lista de perfis na 10 têm o mesmo caminho.
    #
    # A CURA DAQUI É CERTA POR SI: quem publica seis lugares tem de dizer o que
    # cada um dos seis mostra. Depender do `i < v.length ? v[i] : ''` do piloto
    # é depender de um comportamento; declarar as seis é afirmá-lo — e é o que
    # faz o endereço vazio APAGAR em vez de deixar o desenho à mostra.
    vazias = [""] * (AVISOS_VIVOS - len(selos))
    return (selos + vazias)[:AVISOS_VIVOS], (textos + vazias)[:AVISOS_VIVOS]


def coluna_de_atencao(ctx: Contexto) -> dict[str, Any]:
    """Os quatro valores que a coluna Atenção pintava — **hoje sem tela**.

    NASCEU EM 07/09/2026, NO DIA EM QUE A COLUNA SAIU DA JOGAR, e é a metade que
    a ordem dela não podia levar junto: *"em jogar remover essa seção do
    atenção, nenhum aviso esse — deixar só o reconectar controles."* A seção
    saiu; as onze fontes de :func:`_avisos` não têm por que sair com ela.

    **É PÚBLICA DE PROPÓSITO, e é o handoff.** A frente que der casa a estas
    linhas — a aba 09, Sistema, pela razão que :func:`_avisos` mede — chama ESTA
    função e recebe pronto o que a 01 pintava: a conta do produto, os selos, os
    textos e o acendedor, já ordenados pela gravidade e já cortados em
    :data:`AVISOS_NA_COLUNA` com o ``+N``. Sem ela, a próxima frente reescreveria
    de zero quatro linhas que já custaram três medições.

    **`pacote()` NÃO A CHAMA**, e isso é o ponto: os quatro endereços saíram de
    :data:`DA_PAGINA` porque a página não os tem mais, e emitir um endereço sem
    elemento onde pousar é o órfão que o `casamento.py` acusa.

    **AS CHAVES SÃO OS `data-campo` de então**, e não nomes novos: quem receber o
    canal recebe também o vocabulário com que ele já foi medido, e as onze
    réguas que o cobram não precisam aprender uma segunda língua.
    """
    avisos = _avisos(ctx)
    selos, textos = _coluna_de_avisos(avisos)
    return {
        # A CONTA É DO PRODUTO — `painel.texto_da_conta`, o mesmo que a bancada
        # já chamava. Ela sabe dizer "nenhum aviso", que o desenho não tinha (o
        # mockup cravava "1 aviso") e que é o estado normal de uma máquina
        # saudável. Ela CONTA OS AVISOS, não as linhas: uma coluna que mostrasse
        # três e escrevesse "3 avisos" com cinco na máquina esconderia dois.
        "atencao-conta": _painel().texto_da_conta(len(avisos)),
        "aviso-selo": selos,
        "aviso-texto": textos,
        # O ACENDEDOR DAS LINHAS. Uma linha sem aviso não pode ficar com o
        # travessão à mostra: seriam seis linhas de `— —` numa máquina sem nada
        # a dizer. O alvo `classe` sem `data-hef-quando` é BOOLEANO
        # (`hefesto_vivo.escrever`), e o travessão que o piloto escreve num valor
        # vazio conta como desligado — então a lista de `"1"` acende exatamente
        # as que têm texto.
        # ELE ACOMPANHA AS SEIS, e não só as acesas — ver a nota do
        # `_coluna_de_avisos`. Uma lista curta some inteira quando fica vazia, e
        # é justamente a coluna VAZIA que precisa apagar o aviso do desenho.
        "aviso-vivo": ["1" if s else "" for s in selos],
    }


def _frase_da_mesa(ctx: Contexto) -> str:
    """A linha por cima dos lugares apagados — ``""`` quando a mesa cabe na tela.

    D-07 dela, 04/09/2026: *"Uma frase por cima dos lugares apagados."*, e o
    ``+N`` do quinto na mesma linha. A decisão de 31/08 fica de pé — **os
    lugares continuam**: *"o lugar apagado ensina que ali cabe um"*. O que muda
    é o estado vazio deixar de ser MUDO.

    DOIS ESTADOS, E OS DOIS SÃO A MESMA CONTRADIÇÃO VISTA DOS DOIS LADOS:

    * **mesa vazia** — quatro lugares apagados e nenhuma palavra. Quem abre a
      aba não sabe se o Hefesto não vê o controle, se o controle está fora, ou
      se a tela quebrou;
    * **mais controles que lugares** — o cabeçalho conta a mesa inteira
      (`mesa_viva`) e a fileira mostra quatro. `hefesto_vivo.pintar` procura
      `[data-controle="p5"]`, não acha, e segue **sem contar pintura nem erro**:
      o quinto some calado e a MESMA tela afirma dois números.

    SEM DAEMON NÃO SE AFIRMA NADA, e é a mesma guarda do `_estado_da_tela`:
    `ctx.conectados` vazio pode ser "não há controle" ou "ninguém respondeu", e
    escrever "nenhum controle na mesa" sobre um tique sem resposta seria a tela
    afirmando o que não leu.

    O NÚMERO DE LUGARES SE LÊ do desenho (:func:`lugares_da_mesa`). Cravar
    ``4`` aqui poria nesta frase o mesmo defeito que ela denuncia.
    """
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


# O TÍTULO DA SEÇÃO DOS EXTERNOS SAIU EM 06/09/2026, e não é palavra apagada
# por gosto: ele existia porque os cards vinham num BLOCO à parte, e o bloco
# acabou. Escolha dela, no mesmo dia, entre as duas maquetes — *no mesmo frame
# dos assentos*, como a janela GTK fazia. Um cabeçalho dentro de uma grade de
# quatro colunas ou vira um quinto item (uma coluna de texto ao lado dos
# cartões) ou uma faixa de largura inteira — que é a faixa à parte de volta,
# com outro nome.
#
# NADA DE INFORMAÇÃO SE PERDEU: a frase que ele promovia a cabeçalho é a que
# `home_actions._format_external_subtitle` já escreve em CADA cartão — *"o
# Hefesto só vê"* —, e ela continua lá, uma vez por aparelho. O cabeçalho era a
# cópia; o dono ficou.


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
    # SEM EXTERNO, O MARCADOR — E NÃO `""` — 07/09/2026, e é o travessão solto
    # que ela viu logo abaixo dos quatro cartões, na mesma ordem em que mandou a
    # coluna Atenção sair. **ESTE `return` É O CAMINHO QUE A MÁQUINA DELA
    # PERCORRE**: sem externo na mesa o resto da função nem roda.
    #
    # A CAUSA MEDIDA: `escrever()` troca valor vazio por `—` de propósito
    # (`hefesto_vivo.py`), porque um lugar vazio da mesa tem de APAGAR o que
    # estava lá. O `.ext-vaga` é `display:contents`, então esse travessão vira um
    # item anônimo da grade `.pecas` — o quinto assento, na linha de baixo,
    # encostado à esquerda. O `<i class="nada">` que a página traz de nascença
    # sobrevive só até a PRIMEIRA pintura: o alvo `html` troca o miolo inteiro.
    #
    # `monta.NADA_A_DIZER` É A PEÇA DA CASA PARA EXATAMENTE ISTO, e o docstring
    # dela já nomeava o defeito — *"numa linha de ressalva isso vira um `—`
    # solto, que é ruído com cara de dado"*. O bloco dos externos nasceu em
    # 06/09 sem ela, e por isso pagou o preço que ela existe para não pagar.
    #
    # A CHAVE CONTINUA SAINDO EM TODO TIQUE, inclusive vazia: é o que apaga o
    # cartão do externo que foi desligado. Omiti-la deixaria o cartão velho na
    # tela para sempre — o defeito oposto, e pior.
    #
    # A GÊMEA DA ABA 08 TEM O MESMO DEFEITO (`a08_conexoes._html_dos_externos`
    # devolve `""` para o mesmo `.ext-vaga`, `aba08.py:4220`). **RELATADO** —
    # aquele arquivo é de outra frente.
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
        """Escapa para HTML — pelo `html.escape` da biblioteca, e não pelo `_e`
        da janela GTK.

        `gui.aba_conexoes._e` é exatamente esta linha, e importá-lo seria uma
        citação NOVA para uma janela que está saindo (`D-0609-GTK-LEVA-INTEIRA`):
        o portão `nada-aponta-para-a-janela` reprovou a primeira volta desta
        sprint por isso, e a regra é que aquela lista só diminui. **O que se
        reusa da janela é o MOTOR** — as frases, que vêm de `app/actions/` —,
        nunca a janela. É a mesma escolha que `a09_sistema.py` já faz.
        """
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
    # SEM `or NADA_A_DIZER` AQUI, e isso foi MEDIDO — 07/09/2026. A primeira
    # volta desta cura pôs o marcador nos DOIS `return`, e a mordida mostrou que
    # o de baixo não é alcançável: `fora` ganha uma entrada não-vazia por externo,
    # então `"".join(fora)` só é `""` quando `ctx.externos` é vazio — e esse
    # caminho já saiu pela guarda lá em cima. Uma cura que nenhuma mordida
    # derruba é uma cura que não está curando nada.
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
    (`gamepad.py:2162`). O clique é aceito, gravado no disco e não muda nada que
    se veja. A janela GTK escondia a caixa inteira fora do modo `gamepad`
    (`home_actions.py:2889`, `set_visible(modo_exibido == "gamepad")`); esta
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


# ---------------------------------------------------------------------------
# O STEAM INPUT — o disco fica FORA do tique
#
# STEAM-INPUT-01, 20/09/2026. O chip «Steam Input» passou a acender, e o dado
# que o acende mora em DISCO: a lista de exceções dela
# (`~/.config/hefesto-dualsense4unix/steam_input_apps.txt`) contra o que o
# `localconfig.vdf` da Steam realmente diz.
#
# **MEDIDO ANTES DE ESCREVER, na máquina dela em 20/09/2026:**
#
#     discover_vdfs()      1,6 ms   1 arquivo, 163.824 bytes
#     ler_allowlist()      0,04 ms  (o arquivo não existe: devolve [])
#     estado_da_ponte()    25 a 40 ms  — MESMO com a lista vazia
#
# `TIQUE_MS = 100` e `pacote_da_pagina` roda SÍNCRONO no laço do GTK
# (`hefesto_vivo._tique`): 25 ms ali é um quarto de cada tique, dez vezes por
# segundo. É a forma exata do defeito que a A-TELA-QUE-TRAVA-01 curou em 15/09
# — *"as DUAS VIAGENS de IPC são SÍNCRONAS — elas seguram o laço do GTK
# inteiro"*. Então o disco vai para uma vigia, como a da aba 07.
#
# E HÁ UM ATALHO HONESTO, que é o caso dela hoje: **sem lista, não há o que
# medir.** `ler_allowlist()` custa 0,04 ms e responde a pergunta inteira — com
# a lista vazia o chip está apagado, e o vdf nem precisa ser aberto.
# `estado_da_ponte` não faz esse atalho de propósito (ela varre os vdfs para
# contar `sandbox` e `incertos`, que o doctor consome); aqui, onde a pergunta é
# só "qual chip acende", ele vale.
#
# **O QUE O TIQUE PAGA, DEPOIS — medido na mesma máquina, com o dado quente:**
#
#     _estado_da_tela()   0,001 ms   com a lista VAZIA (o caso dela hoje)
#     _qual_jogo()        0,11 ms    os dois markers, só com a lista cheia
#
# Contra os 25-40 ms de antes e os 100 ms do tique inteiro. Com lista, o disco
# é pago UMA vez a cada 20 s, numa thread, e o tique lê o que estiver guardado.
# ---------------------------------------------------------------------------
#: Quanto tempo a leitura do Steam Input vale. É o mesmo número da vigia da aba
#: 07 (`a07_lancadores.TTL_S`), e pela mesma razão: o que ele guarda são fatos
#: do DISCO, que só mudam por um clique dela ou pela Steam saindo.
TTL_DO_STEAM_INPUT_S = 20.0

#: O VALOR QUE ACENDE O CHIP. É a `chave` do chip em `painel.CHIPS_DA_ESCADA`,
#: que é o mesmo `data-hef-quando` que o gerador escreve — digitá-lo em dois
#: lugares é como os dois algarismos da fileira divergiram em 31/08.
CHIP_DO_STEAM_INPUT = "steam"


class LinhaDaFileira(NamedTuple):
    """O que o clique num chip da fileira faz — uma linha de :func:`o_que_o_chip_faz`."""

    #: o modo do produto (`mode_transition`): ``gamepad`` ou ``desktop``
    modo: str
    #: o caminho do vpad (`gamepad.emulation.set {caminho}`); ``None`` na Navegação
    caminho: str | None
    #: o jogo da vez ENTRA (``True``) ou SAI (``False``) da lista do Steam Input
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
    """O que a TELA precisa saber sobre o Steam Input, e nada mais.

    **NÃO É a `ponte.Estado`, e a diferença é deliberada.** A `Estado` carrega
    `steam_aberta` e `jogo_aberto`, que são fatos de AGORA — e esta fotografia
    pode ter vinte segundos. Guardar os dois aqui seria oferecer a quem lê um
    "a Steam está fechada" vencido, e a decisão de fechar a Steam dela não pode
    sair de um dado velho. Quem precisa deles pergunta ao dono na hora, que é o
    que :func:`modo_steam` faz (a `garantir_ponte` mede sozinha, por dentro).
    """

    #: Os appids da lista de exceções dela.
    lista: frozenset[str] = frozenset()
    #: Os que a lista promete e o vdf CONFIRMA — a ponte de pé.
    ligados: frozenset[str] = frozenset()
    #: Os que a lista promete e o vdf desmente, ainda em `"0"`.
    pendentes: frozenset[str] = frozenset()
    #: A frase do dono (`ponte.Estado.frase`), lida — nunca digitada de novo.
    frase: str = ""
    #: O vigia do vdf liga sozinho quando a Steam fecha? (:func:`o_guarda_liga_o_steam_input`)
    #: `False` por padrão: ausência de leitura não promete nada.
    o_guarda_liga: bool = False


class _VigiaDoSteamInput:
    """Guarda a última leitura do disco e a refaz FORA da thread da janela.

    É a MESMA classe da aba 07 (`a07_lancadores._Vigia`), com o mesmo contrato,
    e a repetição é consciente: os pacotes são território exclusivo por desenho,
    e o que se compartilha entre abas é o que tem dono único (`pacotes/perfil`,
    `pacotes/confirmacao`). Um cache é do módulo que o enche.

    O CONTRATO É "NUNCA BLOQUEIE": :meth:`agora` devolve o que tem — ``None`` na
    primeira volta — e dispara a releitura quando o dado passou do TTL. Quem
    precisa do valor de verdade (um gesto, uma régua) chama :meth:`ler`, que
    bloqueia; os gestos já rodam em thread (`hefesto_vivo._gesto`).

    UMA LEITURA POR VEZ: duas varreduras do mesmo `localconfig.vdf` não
    corrompem nada (a leitura é read-only por desenho, `steam_input_ponte:613`),
    mas dobrariam o I/O sem dar resposta mais nova.
    """

    def __init__(self) -> None:
        self._dado: _DoSteamInput | None = None
        self._quando = 0.0
        self._em_curso = False
        self._trava = threading.Lock()
        #: Sobe a cada escrita do gesto (:meth:`renovar`). Uma leitura só
        #: guarda o que leu se ninguém escreveu enquanto ela lia.
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
            # Uma leitura que levanta não pode deixar a vigia travada em
            # `_em_curso` para sempre — a aba pararia de se atualizar em
            # silêncio, que é o defeito desta casa com nome.
            pass
        finally:
            self._em_curso = False

    def esquecer(self) -> None:
        """Invalida o cache — a próxima :meth:`agora` dispara a releitura."""
        self._quando = 0.0

    def renovar(self) -> None:
        """Relê AGORA — é o que o gesto faz depois de escrever. Nunca levanta.

        :meth:`esquecer` sozinho não basta: :meth:`agora` devolve o guardado
        enquanto a thread relê, e o guardado é a leitura que o próprio gesto
        fez ANTES de escrever. O tique seguinte ao clique pintava o «Steam
        Input» que ela acabara de desligar. Se o disco falhar aqui, a escrita
        já valeu: cai para :meth:`esquecer`, e a thread tenta no tique.

        E A THREAD DO TIQUE PODE ESTAR NO MEIO DE UMA LEITURA de antes da
        escrita: terminando depois desta, ela guardaria o disco velho por um
        TTL inteiro. A geração sobe aqui, e :meth:`ler` descarta o que começou
        a ler antes dela.
        """
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
            # O ATALHO MEDIDO: sem lista não há ponte, e o vdf de 164 KB não
            # precisa ser aberto para dizer isso. A frase continua sendo a do
            # dono — `Estado().frase()` devolve "Nenhum jogo na lista de
            # exceções do Steam Input.".
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


#: A vigia é do MÓDULO, e não do `Contexto`: o pacote é recriado a cada tique, e
#: um cache dentro dele releria o disco dez vezes por segundo — que é
#: exatamente o que esta classe existe para impedir.
VIGIA_DO_STEAM_INPUT = _VigiaDoSteamInput()


def _ponte_do_steam_input() -> Any:
    """`integrations/steam_input_ponte` — o dono da ponte. Importado TARDE.

    Pela mesma razão de :func:`_painel`: um import de topo puxaria o módulo (e
    o `steam_launch_options` com ele) para dentro de toda importação desta aba,
    inclusive nas réguas que só querem a pintura.
    """
    from hefesto_dualsense4unix.integrations import steam_input_ponte

    return steam_input_ponte


def _qual_jogo(state: dict[str, Any] | None) -> tuple[int | None, str]:
    """`(appid, "aberto"|"fechado")` — as TRÊS evidências, e ela NÃO é daqui.

    É `a07_lancadores.a_escada_do_jogo`, a MESMA função que o «Este jogo não
    funciona» usa, e não uma cópia. A ordem dos três degraus (sessão do wrapper
    viva → janela em foco → o último marker, mesmo com o jogo já fechado) é da
    janela velha, e o terceiro é o que faz o botão servir ao caso REAL: *"o jogo
    não funcionou, ela fechou, e só então veio reclamar"*.

    UM PACOTE IMPORTANDO OUTRO É EXCEÇÃO NESTA CASA, e esta é declarada: a
    regra (`a07_lancadores._ok_e_motivo`) fala de território exclusivo para o
    que é DESENHO de aba. Qual jogo está aberto não é desenho de aba nenhuma —
    é um fato da máquina com um dono só, e uma segunda escada aqui divergiria
    da dela no primeiro degrau que mudasse. O símbolo é PÚBLICO de propósito.

    NUNCA LEVANTA, porque a de lá não levanta: os três degraus leem disco, e
    disco falha; cada um vai no seu `try` lá dentro.
    """
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

    E O QUARTO NÃO É BURACO: é a mesma honestidade de `painel.degrau_vivo`,
    *"acender um chip por padrão seria afirmar uma escolha que ninguém fez."*

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
        # Sem leitura ainda, ou sem lista: não se sabe / não está. Nos dois
        # casos nada se afirma — e o custo é ZERO tique.
        return ""
    appid, _quando = _qual_jogo(state)
    if appid is None:
        return ""
    return str(appid) if str(appid) in dado.lista else ""


def _a_ponte_que_falta(state: dict[str, Any] | None) -> str:
    """A frase do dono quando o jogo da vez está na lista e o vdf ainda não.

    É o PENDENTE de :func:`_steam_input_da_tela`, dito ao DIÁRIO da janela
    (:func:`_faixa_do_pendente`): a frase é `ponte.Estado.frase`, guardada pela
    vigia, e ela NOMEIA o jogo — é o que quem depura precisa ler. Na TELA vai a
    frase curta dela (:func:`_o_que_o_chip_diz`). Nunca bloqueia: lê o que a
    vigia tem.
    """
    dado = VIGIA_DO_STEAM_INPUT.agora()
    if dado is None or not dado.pendentes:
        return ""
    appid, _quando = _qual_jogo(state)
    if appid is None or str(appid) not in dado.pendentes:
        return ""
    return dado.frase


#: A UNIDADE DO VIGIA DO VDF — o nome sai do dono do timer
#: (`daemon_actions.GUARDA_STEAM_INPUT_TIMER`), nunca digitado aqui.
def _unidade_do_guarda() -> str:
    from hefesto_dualsense4unix.app.actions.daemon_actions import (
        GUARDA_STEAM_INPUT_TIMER,
    )

    return GUARDA_STEAM_INPUT_TIMER.rsplit(".", 1)[0]


def o_guarda_liga_o_steam_input() -> bool:
    """O vigia do vdf vai ligar (e desligar) o Steam Input quando a Steam fechar?

    O-MODO-FREESTYLE-02, item 6 — achado da conferência da STEAM-INPUT-01. A
    faixa «Liga quando a Steam fechar» e as frases do desligar prometiam o que o
    guarda faz sozinho, e numa máquina instalada com `--keep-steam-input` ele
    não faz: o `install.sh` tira da unidade a linha
    `disable_steam_input.sh --apply-quiet` (a mesma forma do `--no-proton-pin`,
    que o `doctor.sh` já lê em `_o_vigia_recusou_o_pino`). Os pacotes (.deb,
    AppImage, Flatpak) nem instalam o vigia (`build_deb.sh`), e quem o desliga
    à mão (`troubleshooting-8bitdo.md`) também fica sem ele.

    O RASTRO É O DISCO, e é o mesmo que o `install.sh` escreve: a unidade
    `.service` com a linha, e o `.path` ou o `.timer` habilitados (o `enable`
    deixa o atalho em `default.target.wants`/`timers.target.wants`). Sem os
    dois, `False` — e a tela só diz o que vai acontecer.

    Lê disco: chame da vigia (thread) ou de um gesto, nunca do tique.
    NUNCA LEVANTA.
    """
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


#: O QUE O CHIP DIZ ENQUANTO ESPERA — 23/09/2026, escolha dela entre «frase
#: curta», «frase longa» e «sem frase» (`D-2309-STEAM-INPUT-A-FRASE-E-O-CLIQUE`).
#: A longa era a do dono (`ponte.Estado.frase`), que nomeia o jogo; ela ficou no
#: diário. Esta é a da tela, palavra por palavra.
STEAM_INPUT_ESPERA = "Liga quando a Steam fechar"


def _o_que_o_chip_diz(state: dict[str, Any] | None, tela: dict[str, str]) -> str:
    """A faixa de baixo com a frase dela — `""` quando o chip não está esperando.

    ELA SÓ FALA COM O CHIP ACESO, e a razão é a da própria faixa: ela diz o que
    FALTA ao que está marcado. Com a mesa vazia a fileira apaga
    (:func:`_a_fileira_com_a_mesa`), e fora do degrau 4 o chip não acende
    (:func:`_estado_da_tela`) — nos dois casos a frase falaria de um botão que
    a tela não mostra aceso. Por isso ela lê a `tela` JÁ decidida, e não o
    disco de novo.

    O QUE ELA ESPERA é o `localconfig.vdf`: o jogo está na lista dela e a Steam
    ainda diz `"0"` para ele (:func:`_a_ponte_que_falta`). O `hefesto-steam-
    input-guard.path` completa quando a Steam sai — ou o segundo clique no chip
    (:func:`modo_steam`), que fecha a Steam e liga na hora.
    """
    if tela.get("steam-input-aceso") != CHIP_DO_STEAM_INPUT:
        return ""
    if not _a_ponte_que_falta(state):
        return ""
    # SÓ PROMETE O QUE VAI ACONTECER — O-MODO-FREESTYLE-02, item 6. Sem o
    # vigia que liga (`--keep-steam-input`, pacote, vigia desligado), fechar a
    # Steam não liga nada: só o segundo clique, e o chip já pergunta
    # «Fechar a Steam?». A faixa cala em vez de prometer.
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

    # A MÁSCARA DOS CARTÕES SAIU DAQUI — 03/09/2026. Ela era emitida como valor
    # DE PÁGINA, e o piloto escreve valor de página em TODO elemento com aquele
    # `data-campo`: a máscara da SESSÃO ia para os três chips dos quatro
    # cartões, e dois controles com escolhas diferentes acendiam o mesmo chip.
    # Agora ela sai por cartão (ver `_mascara_do_cartao`); o que fica aqui é o
    # que de fato é da máquina — a posição do interruptor e o chip da fileira.
    # Quem decide o `modo-aceso` é o caminho (`_chip_do_caminho`), nunca a máscara
    # (MODO-DE-CONEXAO-01, 13/09/2026).
    #
    # UM ACESO SÓ — a D-2 da STEAM-INPUT-01, decidida por ela em 21/09/2026 com
    # a aba aberta: *"dois botões ligados no modo"*. O Steam Input é um DEGRAU
    # da escada (`ponte_escada.ESCADA[3]`: gamepad + DualSense + Steam Input), e
    # o degrau em que se está é um só: com o jogo da vez NA LISTA e o caminho
    # que o Steam Input escolhe (:func:`o_que_o_chip_faz`), quem acende é ele,
    # e o «Sony DualSense» apaga. Sobre o Xbox ou na Navegação o degrau 4 não
    # está de pé, e acende o chip de verdade. O campo continua PRÓPRIO
    # (:data:`DA_PAGINA`): é o que deixa o Python dizer qual dos dois, em vez de
    # o último escrito apagar o outro.
    #
    # A PERGUNTA SÓ VAI AO DISCO QUANDO O CAMINHO É O DELE: fora do degrau a
    # lista não muda o que acende, e o tique não paga a escada do jogo.
    steam = ""
    sob = o_que_o_chip_faz(CHIP_DO_STEAM_INPUT)
    embaixo = o_que_o_chip_faz(aceso) if aceso else None
    if embaixo is not None and (embaixo.modo, embaixo.caminho) == (sob.modo, sob.caminho):
        steam = _steam_input_da_tela(state)
    if steam:
        aceso = ""
    return {
        # AS PALAVRAS SÃO AS DO DESENHO (`aba01.INTERRUPTOR`), e é o `data-hef-
        # quando` de cada rótulo que decide qual acende — o Python manda o
        # ESTADO, não a classe.
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
    # A MESA NÃO TROUXE MÁSCARA NOMEÁVEL. Duas causas, e as duas caem aqui de
    # propósito: a mesa de uma régua (sem a chave) e o daemon velho (sem o
    # `por_aparelho`, quando `mesa_viva` já devolveu a da sessão). O caminho da
    # sessão é o comportamento ANTERIOR a este campo existir — meia cura que
    # muda comportamento é pior que nenhuma.
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
    import monta  # o `pacotes/__init__` põe `interface/` no `sys.path`

    return set(monta.MASCARAS)


def _rotulo_da_mascara(mascara: str | None) -> str:
    """A máscara do produto na palavra do DESENHO — ``""`` quando não há.

    São dois vocabulários, e as CHAVES não se digitam: `ponte_escada.MASCARA_*`
    é o dono delas, e uma renomeação lá apaga a linha aqui em vez de deixar duas
    verdades vivas. Os VALORES são os rótulos dos chips do cartão
    (`monta.MASCARAS`), que é tela — e tela é dela.

    NOTA DATADA — 07/09/2026: aqui estava escrito que *"'Nintendo Pro' não tem entrada,
    e nunca terá enquanto o daemon recusar tudo o que não for dualsense/xbox"*.
    O "nunca" durou até hoje: o daemon aceita `nintendo`, e a entrada existe. O
    que a função faz não mudou — era exatamente o chip **Xbox 360** aceso no
    cartão do P2, com o daemon em `flavor=dualsense`, que ela existe para
    apagar.
    """
    from hefesto_dualsense4unix.integrations import ponte_escada

    return {
        ponte_escada.MASCARA_DUALSENSE: "DualSense",
        ponte_escada.MASCARA_XBOX: "Xbox 360",
    }.get(str(mascara or ""), "")


# ---------------------------------------------------------------------------
# A FAIXA LARANJA — o que ela escolheu e o daemon ainda NÃO alcançou
# ---------------------------------------------------------------------------
#: O QUE A FAIXA DIZIA, E POR QUE ISSO ERA FALSO — medido em 02/09/2026, na foto
#: da aba com os dois controles dela na mesa:
#:
#:     ● Vai mudar para **Sony DualSense** quando você clicar em **Aplicar**
#:
#: e, na MESMA foto, o chip **Sony DualSense** já estava aceso na fileira Modo.
#: As duas metades da frase estão erradas, e cada uma por um motivo diferente:
#:
#: 1. **"Vai mudar para Sony DualSense"** é tautologia. O gerador deriva a
#:    palavra de `aba01.MODO_ACESO` desde 31/08 — a cura que ela encomendou ao
#:    ver a faixa anunciar "Modo Nativo" com o interruptor em Ligado. A cura
#:    matou a CONTRADIÇÃO e deixou no lugar uma frase que só sabe prometer o que
#:    já está valendo: cravada em `MODO_ACESO`, ela nunca poderá dizer outra
#:    coisa.
#: 2. **"quando você clicar em Aplicar"** é falso em TODO estado desta interface.
#:    O Aplicar daqui é `pacotes/rodape.aplicar`, que manda
#:    `profile.apply_draft` com o `to_ipc_dict()` do rascunho — e o contrato
#:    desse payload, escrito no próprio produto (`app/draft_config.to_ipc_dict`,
#:    PERFIL-SALVA-TUDO-01), é: *"`mode` e `suppress_desktop_emulation` … NÃO
#:    viajam no 'Aplicar'"*. **Clicar em Aplicar não troca modo nem máscara.**
#:    Na janela GTK a frase era verdadeira porque `footer_actions.on_apply_draft`
#:    tem um SEGUNDO ramo (`_aplicar_escolha_pendente` → `apply_mode`); o rodapé
#:    desta interface não tem, e a docstring dele já dizia isso com todas as
#:    letras — *"a interface nova ainda não guarda"*.
#:
#: O QUE A FAIXA PASSA A DIZER, e é o que ela SEMPRE existiu para dizer
#: (AGORA-E-DEPOIS-01, `relancar.texto_do_pendente`): *"esta é a única prova de
#: que o clique registrou"*. Nesta interface o clique aplica na hora (decisão
#: dela, 01/09), então uma pendência só nasce quando o daemon **não alcançou** o
#: que ela pediu — e é justamente aí que a tela estava MUDA. `_aplicar` não
#: levanta com o retorno de propósito (ver `ACHADO_DO_TIMEOUT`), então um clique
#: que não pega hoje não deixa rastro nenhum na tela.
_ESCOLHA: dict[str, str] = {}
#: A PALAVRA QUE ELA LEU NA TELA, por campo pendente. Ela NÃO é digitada aqui e
#: não sai de tabela nenhuma: chega no clique, em `o["texto"]` — o
#: `textContent` do próprio botão que ela apertou (`hefesto_vivo.BOOTSTRAP`,
#: `manda_do_alvo`). É a única fonte que não pode divergir do desenho, porque É
#: o desenho. O `painel.CHIPS_DA_ESCADA` é a rede de segurança, e a chave crua é
#: o último degrau — nunca um nome inventado.
_ROTULO: dict[str, str] = {}


def _lembrar(campo: str, valor: str, rotulo: str) -> None:
    """Anota o que ela acabou de pedir. Escritor ÚNICO dos dois dicionários.

    `campo` é `"modo"`, `"caminho"` ou `"mascara"`, que são as chaves de
    `home_actions.reconciliar_pendente` — o `"caminho"` entrou lá e aqui no
    mesmo dia (MODO-DE-CONEXAO-01, 13/09/2026). Escrever um nome que a
    reconciliação não conhece faria ela passar batido por ele.
    """
    if not valor:
        return
    _ESCOLHA[campo] = valor
    _ROTULO[campo] = rotulo or _rotulo_de(campo, valor)


#: O MODO QUE ELA CLICA AQUI ENTRA NO PERFIL ATIVO — JOGAR-O-QUE-FALTA-01,
#: Passo 1 (06/09/2026), e era a linha 5 do CSV da paridade. O veredito de lá
#: nomeava o que faltava com todas as letras: *"nada. `_ESCOLHA`/`_ROTULO` são
#: dicionários de módulo lidos só dentro do próprio arquivo"*, e a consequência
#: medida: *"ela escolhe 'Xbox' na 01, clica em 'Salvar Perfil' na 10, e o
#: perfil grava a máscara que estava no disco — a escolha dela não entra."*
#:
#: **UM DONO, DUAS TELAS.** O escritor é `pacotes.perfil.gravar_o_modo_no_ativo`,
#: o mesmo módulo compartilhado de `gravar_e_reaplicar` e `com_a_carona` — e a
#: regra da seção (o `"none"` que REMOVE, a máscara zerada fora do modo jogo, o
#: `ProfileModeConfig` reconstruído em vez de `model_copy`ado) mora em
#: `perfil.secao_do_modo`, não aqui. A sprint nomeia o perigo desta entrega:
#: *"se você criar um segundo caminho de gravação, o que ela escolher numa aba
#: some quando ela mexer na outra"*.
#:
#: **A DIFERENÇA ENTRE ESTA GRAVAÇÃO E A DA ABA 10** é o tempo, não o lugar: lá
#: o clique escolhe *o que ativar o perfil vai ligar*; aqui ele TROCA o modo
#: agora, e a gravação é o que faz a escolha sobreviver à próxima ativação.
#: Por isso ela vem DEPOIS de `_aplicar` e nunca levanta.
def _gravar_o_modo(
    ctx: Contexto,
    kind: str,
    flavor: str | None = None,
    caminho: str | None = None,
) -> str:
    """Leva o modo clicado à seção `mode` do perfil ativo. Nunca levanta.

    O chip de modo manda o ``caminho`` e nunca o ``flavor`` (MODO-DE-CONEXAO-01,
    13/09/2026): o modo não escreve a máscara do perfil.

    O NOME DE VOLTA É PARA A RÉGUA, não para a tela: ele diz qual perfil recebeu
    a escolha (``""`` quando não houve escrita), e é o que a mordida do Passo 1
    mede — clicar na 01 e ler o valor pela aba 10.

    O `kind` NÃO É FILTRADO AQUI. Quem recusa um valor fora da faixa é o
    `ProfileModeConfig` do esquema, dentro do `try` do dono — filtrar aqui seria
    a segunda cópia de uma lista que o pydantic já tem, e ela envelheceria no
    dia em que um quinto modo nascesse.
    """
    from . import perfil as _perfil

    # O `caminho` só vai quando veio: quem já dubla o escritor com a assinatura
    # de antes (o interruptor, a Navegação) não passa a quebrar por ele.
    return _perfil.gravar_o_modo_no_ativo(
        getattr(ctx, "state", None), kind, flavor,
        **({"caminho": caminho} if caminho else {}))


def _gravar_o_modo_do_chip(ctx: Contexto, chave: str) -> str:
    """O mesmo, para um chip da fileira — e o EIXO sai da tabela, não de um `if`.

    É a mesma leitura de `_lembrar_do_chip` e de `_plano_do_chip`, e as três
    perguntam ao mesmo dono (:func:`o_que_o_chip_faz`): a Navegação **é** um
    modo do produto, os outros são CAMINHOS do mesmo modo ``gamepad``. Escrever
    aqui um ``if chave == "xbox"`` seria a segunda cópia dessa tabela.

    O «STEAM INPUT» GRAVA O CAMINHO DELE — O-MODO-QUE-NAO-SAI-DO-STEAM-INPUT-01,
    23/09/2026: o ``dualsense`` sobre o qual o degrau 4 senta. O terceiro termo
    da ponte (o jogo na lista) não entra no perfil: a casa dele é o
    `steam_input_apps.txt`.

    FATO SUBSTITUÍDO — MODO-DE-CONEXAO-01, 13/09/2026: esta função gravava a
    MÁSCARA da ponte do chip em ``mode.gamepad_flavor``, e o perfil ativo passava
    a dizer `xbox` com o jogo recebendo o DualSense. Ela grava o caminho.
    """
    from hefesto_dualsense4unix.app.actions.mode_transition import MODE_GAMEPAD

    try:
        linha = o_que_o_chip_faz(chave)
    except ValueError:
        return ""
    if linha.modo != MODE_GAMEPAD:
        return _gravar_o_modo(ctx, linha.modo)
    if not linha.caminho:
        return ""
    return _gravar_o_modo(ctx, linha.modo, caminho=linha.caminho)


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
        # MODO-DE-CONEXAO-01: o chip de modo pede um CAMINHO, e é com o caminho
        # vivo que ele se compara — nunca com a máscara.
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
    # O CAMINHO É UM MODO na frase: «Vai mudar para: Xbox» nomeia o chip que ela
    # clicou, e o `texto_do_pendente` só conhece os dois eixos de antes.
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


#: A última pendência que foi ao diário — para escrever a linha quando ela
#: MUDA, e não dez vezes por segundo.
_PENDENCIA_RELATADA = ""


def _relatar_a_pendencia(frase: str) -> None:
    """Leva a pendência ao diário da janela — e não mais à tela.

    13/09/2026, JOGAR-A-FAIXA-QUE-PULA-01 §3.2, MEDIDO NO CÓDIGO E EM DUBLÊ, não
    no aparelho: o chip da fileira manda `gamepad.emulation.set` com
    `origin="manual"` (`painel.plano_do_modo`); a trava de jogo aberto nunca
    segura essa origem (`gamepad._recriacao_bloqueada_por_jogo`,
    `ORIGENS_GESTO_DELA`); e a sprint decidiu por esse ramo: a faixa não acende.

    FATO SUBSTITUÍDO — MODO-DE-CONEXAO-01, 13/09/2026. Aqui se dizia que o chip
    mostrava a escolha, e com máscara no cartão ele não mostrava: o chip mandava a
    máscara, o daemon respondia `ja_estava` sem gravar nada, e a tela acendia
    pela máscara. Desde a cura o chip manda o CAMINHO, o daemon o grava
    depois de o vpad alcançá-lo (`gamepad._guardar_o_caminho`), e
    `_estado_da_tela` acende pelo caminho publicado (`painel.caminho_vivo`).

    Uma pendência que PERSISTE é o daemon que não alcançou o pedido, e isso é
    assunto de quem depura: vai para o `interface.log`, na forma do
    `[desfecho]` da aba 10 (`a10_perfis._anotar`).
    """
    global _PENDENCIA_RELATADA
    if frase == _PENDENCIA_RELATADA:
        return
    _PENDENCIA_RELATADA = frase
    if frase:
        print(f"[relato] {PAGINA} · pendente: {frase}", file=sys.stderr)


# ---------------------------------------------------------------------------
# OS GESTOS — o clique dela chegando ao daemon
# ---------------------------------------------------------------------------
# NADA SE REESCREVE, e nesta aba isso é mais que uma regra de estilo: a
# sequência de IPC de cada modo é uma DEFINIÇÃO do produto, não um detalhe de
# tela. Quem a possui é `app/actions/mode_transition.plan_mode_transition`,
# desde o HARM-01 — o sprint que nasceu porque o modo tinha DOIS donos e eles
# discordavam (a Início saía do Modo Nativo antes de ligar o gamepad; a Emulação
# chamava `gamepad.emulation.set` cru, e os dois ficavam ligados juntos: o
# físico grabado pelo jogo e o vpad congelado — jogo sem controle nenhum).
#
# Escrever aqui `p.chamar("gamepad.emulation.set", enabled=True)` seria o
# terceiro dono. Então esta aba **pergunta**:
#
#     painel.plano_do_modo(chave, mascara) -> [(metodo, params), ...]  # (noqa-acento) id
#
# que delega ao `plan_mode_transition` sem uma linha de regra própria, e devolve
# `None` quando o botão não tem escritor. A tradução chip → máscara também não é
# digitada: sai de `painel.CHIPS_DA_ESCADA`, que é onde a casa guarda qual ponte
# cada chip da fileira nomeia.
from . import gesto  # noqa: E402

#: OS BOTÕES DESTA ABA QUE **NINGUÉM ATENDE**, com o motivo medido. Eles saem do
#: gerador COM `data-gesto` e sem `@gesto`: o piloto recusa dizendo o nome, e o
#: nome aparece no relato como inventário do que falta. É a única forma honesta
#: — sem o endereço o clique some calado, e quem clicou conclui que funcionou.
#:
#: **HOJE ELE ESTÁ VAZIO — STEAM-INPUT-01, 20/09/2026, e é a dívida paga.** A
#: única entrada era o `modo-steam`, e ela dizia: *"não há IPC de Steam Input
#: entre os métodos que o daemon atende, e o degrau custa o que nenhum socket
#: paga"*. A primeira metade continua verdadeira — e a conclusão que se tirava
#: dela é que era falsa: **o Steam Input não precisa de IPC nenhum**. Ele é um
#: arquivo da Steam, e o produto sabe escrevê-lo desde 19/08/2026 (a
#: `PONTE-STEAM-INPUT-01`, com backup, escrita atômica e duas réguas). O que
#: faltava era o gatilho, e o fonte do dono dizia isso por escrito havia um mês
#: (`steam_launch_options:1744`). O gesto é :func:`modo_steam`.
#:
#: A SEGUNDA METADE ERA VERDADE E VIROU DESENHO: ligar exige a Steam fechada, e
#: com ela aberta o dono ADIA a escrita — o primeiro clique avisa, e o segundo
#: fecha a Steam (:func:`_fechar_a_steam_e_ligar`, escolha dela de 23/09/2026).
#:
#: O DICIONÁRIO FICA DE PÉ, como o `a05_vibracao.SEM_DONO` vazio: ele é a
#: gramática desta casa para *"botão que aparece e diz que ainda não tem quem o
#: atenda"*, e `_plano_do_chip` continua lendo dele. A próxima fileira que
#: precisar dele não vai ter de reinventá-lo.
BOTOES_SEM_DONO: dict[str, str] = {}

#: FATO ERRADO, SUBSTITUÍDO — 04/09/2026. Havia aqui uma segunda entrada,
#: `"mascara"`, dizendo *"a máscara do gamepad virtual é UMA para a máquina, não
#: uma por controle: `gamepad.emulation.set` recebe `flavor` e não recebe
#: `uniq`"*. **As duas metades caíram no mesmo dia em que foram escritas**, e o
#: próprio arquivo já dizia o contrário trinta linhas adiante: `gamepad.mask.set`
#: nasceu em 03/09 recebendo `uniq` (`ipc_handlers.py:6812`), o registro
#: `external_mask` guarda a escolha por APARELHO desde 15/08, e o gesto
#: `mascara_do_controle` existe e é `@gesto`. Um botão listado como SEM DONO com
#: o dono declarado no mesmo arquivo manda a próxima pessoa construir o que já
#: está construído — e é como a régua `chips_sem_dono` acusaria falso.
#:
#: NOTA DATADA — 07/09/2026: este texto dizia que *"o 'Nintendo Pro' continua não
#: sendo máscara do produto"* e que ele ficava cinza com a razão na dica. A
#: máscara nasceu hoje, por ordem dela, e o chip acende como os outros dois —
#: o resto do achado (o `uniq` e o dono do gesto) segue valendo.
#: ERA UM LITERAL DE MÓDULO ATÉ 11/09/2026, e ninguém o chamava: prosa de
#: 04/09 guardada como string. Um literal de pacote é exatamente o que a régua
#: das palavras banidas vigia, porque é por ele que o texto CHEGA à tela pelo
#: tique — e este trazia `gamepad.mask.set` e `uniq` na frase. Como comentário
#: ele diz a mesma coisa a quem lê o código e não pode escorregar para a tela.
#:
#:   `gamepad.mask.set` recebe `uniq` e o gesto `mascara` tem dono desde
#:   03/09/2026; e o Nintendo Pro, que era o que sobrava do achado antigo,
#:   virou máscara de verdade em 07/09/2026 — o chip acende como os outros dois.


def _painel() -> Any:
    """`app/actions/jogar/painel` — o dono das perguntas desta aba.

    Importado DENTRO das funções, e não no topo: `painel` puxa `home_actions`,
    que puxa GTK.

    FATO ERRADO, SUBSTITUÍDO — 02/09/2026. Esta linha dizia que sem o import
    tardio *"as dez abas carregariam GTK para pintar um travessão"*. **GTK já
    chega antes de qualquer aba**, e a medição é de uma linha:

        import pacotes            ->  38 módulos `gi` carregados
        import pacotes.a01_jogar  ->  os mesmos 38, nenhum a mais

    Quem o traz é o próprio despachante, por `app/actions/base.py:9`. O import
    tardio segue valendo, e o motivo verdadeiro é OUTRO e menor: `painel` puxa a
    escada, as pontes e o prontuário dos jogos (217 ms de import frio contra
    166 ms do `mode_transition`, que não puxa GTK nenhum). É custo de partida,
    não de pureza — as funções de pacote continuam sem TOCAR GTK, que é o que o
    contrato do `pacotes/__init__` pede.
    """
    from hefesto_dualsense4unix.app.actions.jogar import painel

    return painel


def _plano(
    chave: str, mascara: str | None = None, caminho: str | None = None
) -> list[tuple[str, dict[str, Any]]]:
    """A sequência de IPC daquele modo — DELEGADA, sem uma linha de regra aqui.

    `painel.plano_do_modo` devolve `None` quando o botão não tem escritor, e o
    motivo em português é de `painel.porque_nao_aplica`. Levantar com ELE é o
    que faz o botão recusar DIZENDO, em vez de falhar calado.
    """
    painel = _painel()
    plano: list[tuple[str, dict[str, Any]]] | None = painel.plano_do_modo(
        chave, mascara, **({"caminho": caminho} if caminho else {}))
    if plano is None:
        raise RuntimeError(painel.porque_nao_aplica(chave))
    return plano


def _aplicar(p: Any, plano: list[tuple[str, dict[str, Any]]]) -> bool:
    """Despacha o plano na ORDEM, pelo degrau 3 da ponte.

    NENHUM DESTES QUATRO MÉTODOS TEM FUNÇÃO NO `app/ipc_bridge.py` — conferido
    nas 36 que ele expõe: `native.mode.set`, `gamepad.emulation.set`,
    `desktop.arranjo.apply` e `coop.sync` não estão lá. Então é `p.chamar`,
    que passa pelo mesmo `_safe_call` do bridge e herda o tratamento de erro.

    A ORDEM É A ENTREGA, e ela não é enfeite: `plan_mode_transition` põe o
    `native.mode.set {enabled: false}` ANTES do `gamepad.emulation.set` porque,
    invertidos, *"o vpad nasceria com o físico ainda grabado pelo jogo"*.

    DEVOLVE se o daemon CONFIRMOU todos os passos. Não levanta: quem chama
    anota a pendência antes de dizer a falha — ver `ACHADO_DO_TIMEOUT`.
    """
    confirmou = True
    for metodo, params in plano:
        if not p.chamar(metodo, **params):
            confirmou = False
    return confirmou


#: O QUE O BOTÃO DIZ QUANDO O DAEMON NÃO CONFIRMOU A TROCA — ver
#: `ACHADO_DO_TIMEOUT`. Vai ao diário e à piscada de recusa; o chip aceso,
#: lido do caminho vivo, continua sendo quem diz o que valeu.
#: PROVISÓRIO — texto de tela é palavra dela.
MODO_SEM_CONFIRMACAO = (
    "O Hefesto demorou a responder, e a troca pode não ter acontecido. Se o "
    "botão não acender, clique de novo."
)


def _dizer_se_nao_confirmou(confirmou: bool) -> None:
    """Levanta com :data:`MODO_SEM_CONFIRMACAO` quando `_aplicar` voltou falso."""
    if not confirmou:
        raise RuntimeError(MODO_SEM_CONFIRMACAO)


#: FATO CADUCO, SUBSTITUÍDO — 03/09/2026. Este bloco afirmava que
#: **`pacotes/ponte.chamar` não tem folga de tempo** e que ele chamava
#: `_safe_call` com o default de 250 ms, o teto de LEITURA da ponte; e mandava
#: quem lesse construir a cura em `ponte.py`, *"que não é território desta aba"*.
#:
#: **A CURA JÁ ESTÁ LÁ, e a medição é de uma linha:** `ponte.TETOS`
#: (`pacotes/ponte.py`) declara **2,0 s** para os métodos da TROCA DE MODO desta
#: aba — `native.mode.set`, `gamepad.emulation.set`, `coop.sync` e
#: `identity.renumber` —, que é o mesmo valor de
#: `mode_transition.MODE_IPC_TIMEOUT_S`, e `ponte.teto()` só cai nos 250 ms para
#: método que não esteja na tabela. Conferido método a método contra
#: `a01_jogar.METODOS_DA_TROCA_DE_MODO`: estão todos lá. Os dois de FORA
#: daquele conjunto têm teto próprio e declarado: `gamepad.mask.set` (2,0 s, e
#: ele não é troca de modo) e `desktop.arranjo.apply` (**3,0 s**, porque abre um
#: perfil do disco — POINT-AND-CLICK-01, 17/09/2026).
#:
#: POR QUE ISTO NÃO É NOTA DE RODAPÉ: quem lesse o texto antigo iria construir
#: uma cura já construída, e a regra desta casa é que fato errado se SUBSTITUI —
#: mantê-lo ao lado do certo obriga a próxima pessoa a escolher entre duas
#: afirmações.
#:
#: FATO SUBSTITUÍDO — O-MODO-QUE-NAO-SAI-DO-STEAM-INPUT-01, 22/09/2026. Aqui se
#: dizia que o retorno não virava erro porque a FAIXA LARANJA respondia pelo
#: prazo estourado. A faixa não fala desde 13/09 (JOGAR-A-FAIXA-QUE-PULA-01): a
#: pendência só vai ao diário, e o chip piscava VERDE sobre um `False`. Foi o
#: «Xbox» dela no `interface.log` de 22/09 — `modo-xbox → aplicado`, depois
#: `[daemon mudo] timed out` e `pendente: ● Vai mudar para: Xbox`.
#:
#: A PENDÊNCIA NÃO TEM RELÓGIO: `reconciliar_pendente` só a apaga quando o
#: caminho vivo alcança o pedido, ou quando outro clique no mesmo eixo a
#: sobrescreve. Um pedido que o daemon perdeu fica anotado para sempre, e calado.
#:
#: O QUE CONTINUA VALENDO: a folga é 2,0 s, e um `False` pode vir com o modo
#: aplicado. Por isso o gesto anota a pendência ANTES de levantar (ela some
#: sozinha se o daemon alcançar tarde), não grava o perfil sobre um pedido não
#: confirmado, e a frase (:data:`MODO_SEM_CONFIRMACAO`) diz *pode não ter
#: acontecido* — nunca *não aconteceu*.
ACHADO_DO_TIMEOUT = (
    "ponte.TETOS dá 2,0 s aos cinco métodos desta aba, o mesmo valor de "
    "mode_transition.MODE_IPC_TIMEOUT_S; o teto de 250 ms é só o dos métodos "
    "fora da tabela."
)


@gesto("01-jogar.html", "hefesto", grava="gravar_o_modo_no_ativo")
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
    """O interruptor propriamente dito: o plano do modo, e a anotação da faixa.

    SEPARADO DE :func:`hefesto` para que o docstring de lá — que é onde moram as
    DUAS decisões dela sobre este botão — não fique com o corpo no fim de trinta
    linhas de prosa.

    POR QUE `plano_do_modo` E NÃO `apply_mode`: os dois delegam ao mesmo
    `plan_mode_transition`, mas `apply_mode` despacha por `call_async`, que
    devolve o resultado por `GLib.idle_add` — laço GTK, que o gesto não tem (ele
    roda numa thread do piloto). `plano_do_modo` devolve a MESMA sequência como
    dado, e quem a despacha é a ponte. Zero regra reescrita.

    O QUE ELE GRAVA NO DISCO, e é a resposta à pergunta dela *"não sei se segue
    desativado"*: o passo `gamepad.emulation.set` com `origin='manual'` é o que
    escreve (ou apaga) o `gamepad_disabled.flag` — `utils/session.
    save_gamepad_emulation`, citado em `painel.ESCRITOR_DOS_MODOS`. O
    `origin='manual'` não é decoração: sem ele o daemon lê o pedido como
    reconciliação automática e o recusa quando há Steam Input na jogada
    (ORIGEM-QUE-MENTE-01). Ele vem no plano, não é digitado aqui.
    """
    chave = str(o.get("modo") or "")
    if not chave:
        raise ValueError(
            "hefesto: o clique não disse qual posição do interruptor — o "
            "`data-modo` do rótulo não chegou")
    confirmou = _aplicar(p, _plano(chave))
    # DEPOIS de despachar, nunca antes: `_plano` levanta para um botão sem
    # escritor, e anotar uma pendência que não chegou a sair prometeria uma
    # mudança que ninguém pediu ao daemon.
    _lembrar("modo", chave, str(o.get("texto") or ""))
    _dizer_se_nao_confirmou(confirmou)
    # E A ESCOLHA ENTRA NO PERFIL ATIVO — Passo 1. Pela mesma razão de ordem:
    # gravar antes de o plano sair prometeria, no disco dela, um modo que o
    # daemon recusou. Ver `_gravar_o_modo`.
    _gravar_o_modo(ctx, chave)


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
        # A Navegação: `apply_mode('desktop')`, os três IPCs em ordem.
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
    # O RÓTULO DO CHIP, e não o do caminho: o «Steam Input» pede o caminho do
    # «Sony DualSense», e a rede de `_rotulo_de` nomearia o vizinho na faixa.
    rotulo = str(o.get("texto") or "") or _rotulo_do_chip(chave)
    if linha.modo != MODE_GAMEPAD:
        _lembrar("modo", linha.modo, rotulo)
        return
    if linha.caminho:
        _lembrar("caminho", linha.caminho, rotulo)


def _o_clique_da_fileira(ctx: Contexto, o: dict[str, Any], p: Any,
                         chave: str) -> dict[str, Any] | None:
    """O CLIQUE NUM CHIP DO MODO — os quatro gestos passam por aqui, e só por aqui.

    O-MODO-QUE-NAO-SAI-DO-STEAM-INPUT-01, 23/09/2026, pela regra dela: *"fez
    errado a idea é eu poder escolher qualquer que seja o modo independnete da
    ordem."* O clique faz a linha do chip em :func:`o_que_o_chip_faz` — o
    modo, o caminho e o jogo da vez dentro ou fora da lista do Steam Input — e
    NADA aqui pergunta qual chip estava aceso antes. Clicar no aceso reaplica.

    FATO SUBSTITUÍDO — a primeira cura desta sprint (22/09) perguntava ao Modo
    de onde ela saía: o «Xbox» e a «Navegação» só tiravam o jogo da lista com o
    Steam Input aceso, o «Steam Input» clicado vindo do «Xbox» não mudava o
    caminho, e com um jogo da Steam aberto o clique recusava. Era a fileira
    dependente da ordem que ela recusou.

    O JOGO É O DA VEZ, ABERTO OU FECHADO — `a_escada_do_jogo`, o mesmo alvo
    que acende o chip (:func:`_o_jogo_na_lista`). Sem jogo nenhum conhecido, o
    «Steam Input» é a ÚNICA recusa que sobra (a frase do dono, `sem_jogo`), e
    ela vem antes de tudo: não há jogo a que aplicar, e nada muda. Os outros
    três chips só trocam o caminho.

    A LISTA É GRAVADA COM O JOGO ABERTO. O portão que recusava aqui
    (`steam_game_running`, nascido com o chip em `c417498e0`, 20/09) não tinha
    razão MEDIDA para a lista, e o git diz de onde ele veio: o desenho da
    STEAM-INPUT-01 (§4.2) punha o portão só no passo 3, a PONTE, e com a razão
    *"fechar a Steam mataria o jogo"* — o passo 2, a lista, *"não pergunta"*.
    O mesmo commit recuou de fechar a Steam (um `<span>` não tem como pedir
    consentimento), e o portão ficou de pé na frente das DUAS metades,
    protegendo *"o que o daemon entrega ao jogo em curso"*. Isso não foi
    medido, e o fonte diz o contrário: desde a ESCONDER-EM-VEZ-DE-SAIR-01
    (09/08) a lista só decide a exceção (`gamepad.esconder_o_fisico_para_o_jogo`,
    que *"não cria, não destrói e não recria device nenhum"* — só reafirma o
    estado canônico) e o arming do PRÓXIMO lançamento. O que precisa do jogo
    e da Steam fechados é o `localconfig.vdf`, e os dois escritores do dono
    continuam ADIANDO sozinhos, na ordem jogo → Steam → escrita
    (`garantir_ponte` e `garantir_fora_da_lista_desligado`); o guarda do vdf
    completa quando a Steam sai.

    A LISTA VEM DEPOIS DO PLANO E ANTES DE DIZER A FALHA: ela é arquivo nosso,
    não depende do daemon, e deixá-la para trás quando o IPC estoura o prazo
    deixaria o «Xbox» aceso com a Steam no comando do jogo. A recarga
    (`METODO_DA_RECARGA`) e o veredito relido do vdf só vão quando a lista
    mudou — ou quando o «Steam Input» reaplica, que pode completar a ponte
    PENDENTE. A vigia é relida mesmo quando o veredito levanta.

    O QUE A STEAM AINDA NÃO FEZ NÃO É RECUSA: ligar adiado vai à faixa de
    pendência (:func:`_a_ponte_que_falta`), desligar adiado volta como recado
    (:func:`_reconciliar_o_vdf`). A gravação no perfil fica no CORPO de cada
    gesto, para a régua das portas (`test_todo_gesto_que_grava_esta_protegido`)
    achá-la dentro do teto dela, e depois desta função — que levanta com
    :data:`MODO_SEM_CONFIRMACAO` quando o daemon não confirmou o plano.
    """
    from hefesto_dualsense4unix.app.actions.daemon_actions import (
        format_game_broken_result,
    )
    from hefesto_dualsense4unix.integrations import steam_launch_options as slo

    from .a07_lancadores import METODO_DA_RECARGA

    linha = o_que_o_chip_faz(chave)
    # TODO CLIQUE NA FILEIRA DESARMA O «FECHAR A STEAM?» — o consentimento era
    # sobre o «Steam Input» daquele jogo; outro chip é outra escolha, e um
    # rótulo armado sobrando ali fecharia a Steam por um jogo que saiu da lista.
    _desarmar_o_chip()
    appid, _quando = _qual_jogo(ctx.state)
    if linha.steam_input and appid is None:
        raise RuntimeError(str(format_game_broken_result(status="sem_jogo")))

    confirmou = _aplicar(p, _plano_do_chip(chave))
    # DEPOIS de despachar, nunca antes — a mesma ordem do interruptor
    # (`_hefesto_o_modo`): anotar um pedido que não chegou a sair prometeria
    # uma mudança que ninguém pediu ao daemon.
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
    # SEM NOTÍCIA, SEM FRASE — JOGAR-02, 09/09/2026: `None` faz a tela responder
    # com a piscada verde do botão, que é como esta casa diz "deu certo". Um
    # `{"recado": ""}` pousaria uma caixa verde VAZIA sobre a fileira.
    return {"recado": recado} if recado else None


@gesto("01-jogar.html", "modo-dualsense", grava="gravar_o_modo_no_ativo")
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
    recado = _o_clique_da_fileira(ctx, o, p, "dualsense")
    _gravar_o_modo_do_chip(ctx, "dualsense")
    return recado


@gesto("01-jogar.html", "modo-xbox", grava="gravar_o_modo_no_ativo")
def modo_xbox(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any] | None:
    """"Xbox": o canal comum, o do controle de Xbox — o SEGUNDO que o Hefesto tenta.

    ESTE CHIP NASCEU EM 31/08/2026 E É UMA DÍVIDA PAGA: `Ponte(gamepad, xbox)` é
    degrau da `ESCADA` desde 19/08 e **nenhum chip o nomeava** — era o que
    `painel.degraus_sem_chip()` denunciava. A escada automática passava por ele
    e a tela não tinha onde mostrá-lo.

    É o CAMINHO `uinput` (MODO-DE-CONEXAO-01, 13/09/2026), e ele NÃO escolhe a
    máscara: com o cartão do P1 em DualSense o jogo continua vendo o DualSense,
    agora pelo canal comum. Até 13/09 este chip mandava a máscara Xbox 360, e com
    máscara no cartão dizia «aplicado» sem mudar nada — a queixa dela.

    E TIRA O JOGO DA VEZ DO STEAM INPUT, venha ela de onde vier — com ele na
    lista, a Steam pegaria o controle do jogo por baixo do «Xbox» aceso. Ver
    :func:`o_que_o_chip_faz`.
    """
    recado = _o_clique_da_fileira(ctx, o, p, "xbox")
    _gravar_o_modo_do_chip(ctx, "xbox")
    return recado


# ---------------------------------------------------------------------------
# O CHIP «STEAM INPUT» — STEAM-INPUT-01, 20/09/2026
#
# A ORDEM DELA, verbatim: *"Aqui no steam input é meio óbvio é basicamente setar
# o jogo pra funcionar usando os controladores da própria steam. Fazer tal jogo
# usar ela e funcionar."* — e, sobre a gravidade: *"Achei que elas tivessem
# configuradas. Isso é importantíssimo que resolvamos. Pois estão na aba
# principal da interface"*.
#
# O DEFEITO, em uma frase: o Steam Input era o único dos quatro chips da fileira
# cuja implementação **já estava pronta e provada** — escrita atômica, backup,
# duas réguas, gate de Steam, cura automática no prontuário, teste que morde — e
# o único que a TELA não alcançava. Desde 31/08/2026 o chip saía do gerador
# marcado e sem `@gesto`: o clique chegava, o piloto recusava dizendo o nome, e
# nenhum byte era escrito em lugar nenhum.
#
# NADA AQUI É MOTOR NOVO, e cada peça tem endereço e dono:
#
#     a07_lancadores.a_escada_do_jogo                        qual jogo é
#     steam_launch_options.add_appid_to_steam_input_allowlist  a vontade dela
#     steam_launch_options.remove_appid_from_steam_input_allowlist   a volta
#     steam_launch_options.with_steam_closed                 fechar e reabrir
#     steam_input_ponte.garantir_ponte                       ligar no vdf
#     steam_input_ponte.garantir_fora_da_lista_desligado     desligar no vdf
#     steam_input_ponte.estado_da_ponte                      ler sem tocar
#     steam_input_ponte.Estado.frase                         a frase do diário
#     pacotes/confirmacao                                    o relógio dos dois cliques
#     a07_lancadores.METODO_DA_RECARGA                       valer AGORA
#
# A confissão que ficou meses no fonte do dono
# (`steam_launch_options:1744`) dizia o resto: *"Falta só o gatilho e a frase do
# toast; a decisão e a escrita moram aqui."* Este bloco é o gatilho.
#
# DOIS PASSOS COM PREÇOS DIFERENTES, e por isso só UM pergunta:
#
#   2. A VONTADE DELA — uma linha num arquivo NOSSO, reversível, barata. **Não
#      pergunta**, e a razão é a que a aba 07 já escreveu: *"pedir consentimento
#      para um ato reversível ensina que todo botão pede consentimento, e aí o
#      consentimento que importa deixa de ser lido."*
#   3. A PONTE — reescreve o `localconfig.vdf` DELA, e para isso a Steam tem de
#      estar fechada (ela regrava o arquivo ao sair). Com ela aberta o dono
#      ADIA, a faixa diz «Liga quando a Steam fechar», e o chip ARMA: o rótulo
#      vira «Fechar a Steam?» e o SEGUNDO clique fecha a Steam, liga e a reabre.
#      Sem o segundo clique, o guarda do vdf completa quando ela sair.
#
# FATO SUBSTITUÍDO — 24/09/2026. Aqui se dizia que o chip *"não pergunta e não
# fecha a Steam"*, porque um `<span>` estático não tinha rótulo para trocar. Ele
# tem: o `blocos:` troca o miolo dele como troca o dos botões armados da aba 09.
# A decisão é dela (`D-2309-STEAM-INPUT-A-FRASE-E-O-CLIQUE`, 23/09): *"o
# primeiro clique avisa, o segundo fecha"*.
# ---------------------------------------------------------------------------
#: A nota que acompanha o appid na lista dela. Ela distingue, no arquivo, o que
#: ELA escolheu na aba Jogar do que o «Este jogo não funciona» marcou porque
#: algo quebrou — dois gestos, a mesma lista, intenções opostas.
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
    """Os appids que o DESLIGAR tem de preservar — tudo menos o `alvo`.

    **ESTE É O FILTRO POR APPID, e ele é a trava contra a CAMINHO-CONTAGIO-01.**

    `garantir_fora_da_lista_desligado` escolhe os alvos por subtração: escreve
    `"0"` em todo jogo que a Steam configurou POR JOGO e que **não** está na
    lista que recebe. Passar a lista dela ali desligaria, de uma vez, todo jogo
    configurado que ela nunca escolheu — um clique dela em UM jogo mexendo em
    trinta, que é exatamente a forma do defeito que a `CAMINHO-CONTAGIO-01`
    nasceu para curar (o `mode.caminho` de um jogo virando lei sobre os outros).
    Passando "tudo o que a Steam configurou, MENOS este", o único alvo é ele.

    **O LIMITE, DECLARADO porque é medido:** o dono só enxerga o que tem
    configuração POR JOGO (pasta `<appid>/` ou entrada com `autosave` num
    `configset_*.vdf`, `steam_input_ponte.configuracao_por_jogo`). Um jogo que
    ligamos pelo chip e que a Steam ainda não configurou não está nesse
    conjunto: o `"0"` não é escrito, e :func:`modo_steam` **diz isso** em vez de
    cantar vitória. Curar esse vão é escrever um desligador por appid dentro de
    `integrations/steam_input_ponte.py`, que esta sprint tem em `nao_toca`.
    """
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


#: O QUE A TELA DIZ QUANDO A VONTADE FOI GRAVADA E A PONTE NÃO SUBIU.
#:
#: PROVISÓRIO — texto de tela é palavra dela (§7 D-4 da sprint). As três nomeiam
#: o que ELA faz a seguir, e nenhuma confessa estado interno nosso: é regra dela
#: de 07/09, *"o layout não informa os nossos defeitos"*.
STEAM_INPUT_SAIU_E_A_STEAM_ESTA_ABERTA = (
    "Tirei este jogo da lista. A Steam sai do comando dele quando você fechar "
    "a Steam."
)
STEAM_INPUT_NAO_MUDOU_O_ARQUIVO = (
    "Anotei este jogo, mas a Steam ainda não mudou de lado para ele. Abra-o "
    "uma vez pela Steam e clique aqui de novo."
)
#: FATO SUBSTITUÍDO — conferência da STEAM-INPUT-01, 24/09/2026. Esta frase
#: mandava usar «Desligar o Steam Input», na aba Lançadores, e o botão saiu em
#: 21/09 com os outros do cartão da Steam — é o mesmo defeito do «Consertar»
#: da aba 07. Quem desliga hoje é o guarda do vdf (`hefesto-steam-input-guard`:
#: o `.timer` de 30 min e o `.path`, que acorda quando a Steam grava ao sair).
#: SEM O VIGIA QUE DESLIGA (O-MODO-FREESTYLE-02, item 6), a frase para no que
#: é verdade: ninguém tira a Steam de lá sozinho (:func:`o_guarda_liga_o_steam_input`).
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
        # O FILTRO POR APPID — ver :func:`_os_que_ficam`. Sem ele, desligar UM
        # jogo desligaria todo jogo configurado que não está na lista dela.
        return ponte.garantir_fora_da_lista_desligado(allowlist=_os_que_ficam(alvo))

    resultado = _acao()

    # A RELEITURA, e é o único veredito que este gesto aceita.
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


#: O NOME DO GESTO, e ele é o `data-gesto` do chip (`aba01._chip_do_modo`
#: escreve `modo-<chave>`). Ele existe como constante porque o decorador e as
#: réguas que conferem o registro têm de concordar com o que o gerador
#: escreve — um nome digitado em três lugares é um typo à espera.
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
    _gravar_o_modo_do_chip(ctx, CHIP_DO_STEAM_INPUT)
    return recado or _armar_se_a_steam_segura(ctx)


# ---------------------------------------------------------------------------
# OS DOIS CLIQUES — 24/09/2026, D-2309-STEAM-INPUT-A-FRASE-E-O-CLIQUE
#
# O RELÓGIO É O DE `pacotes/confirmacao`, o mesmo da aba 09: armar o chip
# desarma o botão armado de lá, e vice-versa. A CHAVE leva o jogo — o
# consentimento dela é para AQUELE jogo, e o chip armado para um não fecha a
# Steam por outro.
# ---------------------------------------------------------------------------
#: O RÓTULO DO CHIP ARMADO. Ele AVISA o que o segundo clique faz, na forma dos
#: botões armados da aba 09 (`a09_sistema.CONFIRMA`, «Confirma?»), com o verbo.
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
    """O appid, se ESTE clique é o segundo — `""` se é um primeiro clique.

    OS DOIS GUARDAS SÃO OS DA ABA 09 (`a09_sistema._confirmado`), e são
    independentes:

    1. o clique traz o rótulo ARMADO em `o["texto"]` — o piloto manda o
       `textContent` do chip clicado, e «Fechar a Steam?» só existe nele depois
       de armado. É o que prova que ela LEU a pergunta;
    2. o relógio de `pacotes/confirmacao` está armado para ESTE jogo.

    O RÓTULO SEM O RELÓGIO LEVANTA, em vez de agir ou de rearmar calado: a
    pergunta venceu (ou o jogo da vez mudou), e o segundo clique não pode valer
    por um consentimento que já não existe. O tique repõe «Steam Input».
    """
    if str(o.get("texto") or "").strip() != STEAM_INPUT_ARMADO:
        return ""
    appid, _quando = _qual_jogo(ctx.state)
    armado = confirmacao.armado_agora()
    confirmacao.desarmar()
    if appid is None or armado != _chave_do_chip(appid):
        raise RuntimeError(STEAM_INPUT_A_PERGUNTA_VENCEU)
    return str(appid)


#: A RECUSA DO SEGUNDO CLIQUE FORA DO PRAZO — a mesma forma da aba 09. Vai ao
#: diário (TELA-CALADA-01), e o chip pisca a recusa. O número é o do relógio.
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
        # A PONTE JÁ SUBIU ENTRE OS DOIS CLIQUES (ela fechou a Steam sozinha, e
        # o guarda do vdf completou): fechar a Steam agora seria por nada.
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


#: O QUE A TELA DIZ QUANDO A MÁSCARA VALE E NÃO FICA GUARDADA — as duas metades
#: (`AS-DUAS-ABAS-FALAM-01`), e a forma é a do `a02_controles.SOM_SEM_ENDERECO`,
#: que já resolveu esta mesma pergunta para o som.
#:
#: A-PERNA-QUE-FALTA-01, 11/09/2026. Até hoje o gesto chamava `ponte.chamar`, que
#: devolve `bool`: o `motivo` que o daemon acabava de mandar morria na ponte, e
#: a tela piscava VERDE sobre um perfil byte-idêntico. A `§3` desta sprint tirou
#: a causa comum (o daemon calado com um perfil valendo no disco); estas frases
#: fecham a CLASSE — no dia em que o daemon recusar por outra razão, a tela diz.
#:
#: NENHUMA DELAS NOMEIA O ESTADO INTERNO, e é regra dela (07/09): *"o layout não
#: informa os nossos defeitos"*. `sem_perfil` vira o que ELA faz a seguir.
#:
#: PROVISÓRIO — texto de tela é palavra dela.
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

#: A TRADUÇÃO DA RECUSA DO CORPO, e o `None` é o caso comum.
#:
#: `sem_mudanca` NÃO É RECUSA e por isso não está aqui: ele quer dizer que o
#: perfil JÁ guardava essa máscara. Falar seria transformar um clique sem efeito
#: nenhum num aviso de 6 s — e a piscada verde já responde por ele.
#:
#: O DESCONHECIDO CAI NA FRASE GENÉRICA de propósito: um motivo que esta tabela
#: não conhece é um token interno, e mandá-lo cru para o cartão seria a tela
#: falando a língua do daemon.
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

    # A TRADUÇÃO TEM DONO e é lida ao contrário: `NOME_DA_MASCARA` é
    # `{flavor: rótulo}` e serve à pintura desde que a mesa viva nasceu.
    # Digitar aqui um segundo mapa faria a tela e o gesto discordarem no dia em
    # que um rótulo mudasse.
    por_rotulo = {v: k for k, v in NOME_DA_MASCARA.items()}
    flavor = por_rotulo.get(rotulo) or normalizar_mascara(rotulo)
    if flavor is None or flavor not in mascaras_validas():
        tem = ", ".join(NOME_DA_MASCARA[f] for f in sorted(mascaras_validas())
                        if f in NOME_DA_MASCARA)
        raise RuntimeError(
            f"“{rotulo}” está desenhado na tela e o Hefesto não sabe montar "
            f"essa máscara. As que existem: {tem}.")

    # OS PARÂMETROS VÃO POR NOME, e esta linha é a CURA da queixa 1 dela —
    # 04/09/2026, achada CLICANDO o chip com o daemon vivo.
    #
    # Ela estava escrita `p.chamar("gamepad.mask.set", {"uniq": …, "flavor": …})`,
    # com o dicionário POSICIONAL. A assinatura é
    # `ponte.chamar(metodo, timeout=None, **params)`: o 2º posicional é o  # (parâmetro) noqa-acento
    # TIMEOUT. O dicionário virava o prazo, `teto(metodo)` o  # (parâmetro) noqa-acento
    # mantinha (dicionário é verdadeiro), e o `_safe_call` estourava lá dentro
    # com `'<=' not supported between instances of 'dict' and 'int'`.
    #
    # **LOGO ESTE GESTO NUNCA GRAVOU UM BYTE.** Medido na máquina dela: clicar
    # o chip DualSense do P1 não criava o `controller_masks.json` e não mexia em
    # `gamepad_emulation.por_aparelho`. Era a queixa dela em estado puro —
    # *"clico e não acontece nada"* —, e a causa não era o MODO: era a chamada.
    #
    # POR QUE NINGUÉM VIU: `gamepad.mask.set` não estava em `METODOS` (a régua
    # que confere nome contra o `ipc_server`) e o gesto `mascara` não tinha
    # linha em `PROVAS` (a régua que confere a CHAMADA). As duas nasceram com
    # esta cura, e é a de `PROVAS` que morde a assinatura.
    #
    # `chamar_detalhado` E NÃO `chamar` — A-PERNA-QUE-FALTA-01, 11/09/2026. O
    # `chamar` devolve `bool` e o `motivo` que o daemon acabou de mandar morria
    # aqui; a docstring dele já dizia isso UMA LINHA ACIMA da própria chamada
    # (*"perde a tradução da recusa, que é o que faz a tela dizer por que não
    # deu"*). `gamepad.mask.set` responde `{"gravado": false, "motivo": …}`
    # numa resposta BEM-SUCEDIDA, e é `ponte.chamar_detalhado` que junta as duas
    # formas de o daemon dizer não.
    ok, motivo = p.chamar_detalhado("gamepad.mask.set", uniq=uniq, flavor=flavor)
    if not ok:
        # A FRASE DA RECUSA É DO DAEMON, e ela é escrita para ela: o
        # `gamepad.mask.set` recusa em voz alta com o catálogo do que aceita.
        # Sem motivo é falha de transporte — o gesto continua calado, como
        # sempre foi, porque a tela inteira já está parada nesse caso.
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
    perguntas pintaria "sem dono" sobre um botão que dá — é a diferença entre
    `chips_sem_degrau()` e `chips_sem_dono()`.

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
    `ESCADA` automática — que é outra pergunta, e é a de `chips_sem_degrau()`.

    E TIRA O JOGO DA VEZ DO STEAM INPUT, como o «Xbox» — a linha dela em
    :func:`o_que_o_chip_faz`, e o clique é :func:`_o_clique_da_fileira`.
    """
    recado = _o_clique_da_fileira(ctx, o, p, "navegacao")
    _gravar_o_modo_do_chip(ctx, "navegacao")
    return recado


@gesto("01-jogar.html", "cadeado", grava="autoswitch_lock_set")
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

    O ESCRITOR JÁ EXISTIA: `ponte.autoswitch_lock_set` expõe o
    `app/ipc_bridge.autoswitch_lock_set`, que é o mesmo que o
    `_on_home_autoswitch_lock_toggled` da janela antiga aciona. Zero regra
    reescrita.

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
    escrita por clique: `save_autoswitch_locked` grava (`ipc_handlers.py:2536`).
    O `change` é o escolhido porque é o único que só dispara quando a caixa de
    fato MUDOU — clique em rótulo, tecla de espaço e `el.click()` sintético
    passam pelos três caminhos. Um clique sem `evento` (a régua dos botões, que
    monta o recado à mão) continua valendo: o padrão é `change`.

    A VERDADE VOLTA DO DAEMON, não deste gesto: o alvo `marcado` repinta a caixa
    a cada tique a partir de `autoswitch_locked`. Se a escrita não pegar, a
    caixa **volta sozinha** — que é o oposto de uma tela que finge ter guardado.

    RELATO FECHADO — 06/09/2026, pela `ONDA3-GESTO-DECLARA-01`. Aqui estava
    escrito que este gesto pertencia a `hefesto_vivo.PERIGOSOS` e que a linha
    não podia ser escrita *"porque os dois arquivos são de outro dono"*. Esse
    é exatamente o defeito que a sprint matou: a declaração passou a morar no
    PRÓPRIO decorador (`grava="autoswitch_lock_set"`), e `PERIGOSOS` é derivada
    dela. Quem escreve o gesto fecha o próprio contrato.

    **FATO SUBSTITUÍDO — 06/09/2026, e a conclusão dele fica de pé por outro
    motivo.** Este fecho dizia que a caixa só existia no desenho da BANCADA e
    que o piloto abre o publicado, e por isso o `--prova-gesto` não a clicava.
    A primeira metade caducou: a caixa está na página publicada, que é a que o
    produto renderiza (`onde.PUBLICADO`), e a régua
    `test_o_cadeado_esta_publicado` mede isso LENDO o arquivo — não este
    parágrafo. **A conclusão continua certa, e a razão é `PERIGOSOS`:** clicar
    esta caixa GRAVA no disco dela (`utils/session.save_autoswitch_locked`, pelo
    `autoswitch.lock`), e uma régua de clique que mudasse uma preferência dela
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
    lixo.** `ipc_bridge.autoswitch_lock_set` devolve o estado que FICOU valendo,
    e `None` quando não houve resposta. Sem ler isso, um clique com o serviço
    parado piscava VERDE e a caixa desmarcava no tique seguinte (`_cadeado` sem
    `autoswitch_locked` devolve `""`): a tela dizia *guardei* e *não está
    guardado* com 100 ms entre as duas. É a metade que separa **o produto
    confirmou** de **a tela pintou sozinha**.

    A GUARDA É `is None` E NÃO UMA COMPARAÇÃO, e a medição diz por quê:
    `_handle_autoswitch_lock` (`daemon/ipc_handlers.py`) faz `novo = bool(pedido)`
    quando o `locked` vem no pedido — o toggle é só para quem NÃO manda valor, e
    este gesto sempre manda. Um bool que discordasse do pedido é ramo que este
    daemon não tem como produzir, e escrevê-lo seria inventar um desfecho para
    poder tratá-lo.
    """
    # O EVENTO É `click` DESDE 19/09/2026, e a troca é obrigatória, não
    # cosmética: um `<button>` NÃO emite `change` — só `<input>`, `<select>` e
    # `<textarea>` emitem. Deixar o filtro em `change` faria este gesto voltar
    # cedo em TODO clique, e a trava viraria enfeite: a tela pisca e o disco
    # não muda, que é a queixa dela em estado puro.
    #
    # E A DUPLA ENTREGA QUE O `change` FILTRAVA SUMIU COM A CAIXA: o ouvinte
    # único do piloto está em `click` e em `change`, e um checkbox disparava os
    # dois. Um botão dispara UM. O filtro fica porque a régua dos botões monta
    # o recado à mão e pode mandar outro evento — mas o que ele protege agora é
    # o contrato, não um defeito vivo.
    if str(o.get("evento") or "click") != "click":
        return
    pedido = _cadeado(ctx.state) != CADEADO_LIGADO
    if p.autoswitch_lock_set(locked=pedido) is None:
        raise RuntimeError(CADEADO_RECUSA)


def _o_radio_de_volta(ctx: Contexto) -> tuple[int, int]:
    """PASSO 0 — o RÁDIO. Devolve `(voltaram, esperam_o_ps)`.

    **ORDEM DELA, 22/09/2026:** *"pera o reconectar deveria sim tocar no radio.
    não faz sentido ele ficar de fora."* <!-- noqa-acento: citação dela -->
    Ela revoga a regra de 12/08 que este botão citava — *"o botão PS é dela;
    `reconectar` não existe de propósito"* —, e o dia mediu por quê: a mesa
    dela caiu num estado em que o BlueZ dizia `Connected` para quatro controles
    com o kernel sem HID nenhum deles. **O PS não resolve esse**: para o rádio
    já está tudo certo. Quem destrava é derrubar o elo morto, e isso é nosso.

    QUEM ESTÁ NA MESA NÃO É TOCADO, e é a linha que impede o botão de derrubar
    o controle que está jogando: mexer no rádio de quem o daemon já enxerga
    seria trocar um problema que não existe por três segundos sem controle.

    NUNCA LEVANTA: o rádio é acréscimo. Se o `busctl` não responder, o gesto
    segue para os jogadores — que é o que ele sempre fez.
    """
    from hefesto_dualsense4unix.core.sysfs_leds import norm_mac
    from hefesto_dualsense4unix.integrations import gesto_de_reconexao as radio

    na_mesa = {
        norm_mac(str(peca.get("uniq") or "")) or ""
        for peca in (ctx.mesa or [])
        if isinstance(peca, dict)
    }
    voltaram = esperam = 0
    try:
        conhecidos = radio.dualsenses_do_radio()
    except Exception:  # best-effort: o rádio não derruba o gesto
        return (0, 0)
    for mac, _conectado in conhecidos:
        if (norm_mac(mac) or "") in na_mesa:
            continue
        try:
            desfecho = radio.reconectar(mac)
        except Exception:
            continue
        if desfecho.estado == radio.ESTADO_VOLTOU:
            voltaram += 1
        elif desfecho.estado == radio.ESTADO_SO_O_PS:
            esperam += 1
    return (voltaram, esperam)


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
    (`ipc_handlers.py:5249`).

    PASSO 2 — `identity.renumber`: compacta a numeração preservando a ordem
    relativa. **A ORDEM É A ENTREGA** e está escrita no botão antigo
    (`home_actions.py:3122`): *"renumerar antes de reconciliar compactaria uma
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
    interno de propósito (`app/ipc_bridge.py:92-96`). Deixá-los subir daqui
    mataria o gesto sem uma palavra na tela, que é o defeito que este passo
    cura.
    """
    # PASSO 0 — O RÁDIO, ordem dela de 22/09/2026. Ver `_o_radio_de_volta`.
    # Ele vem ANTES do `coop.sync` pela mesma razão que a numeração vem depois
    # da reconciliação: um controle que volta pelo rádio agora é um jogador que
    # o passo 1 ainda alcança nesta mesma execução.
    voltaram, esperam_o_ps = _o_radio_de_volta(ctx)
    try:
        sync = p.resultado("coop.sync")
    except Exception as erro:
        raise RuntimeError(_painel().RECONECTAR_SEM_SERVICO) from erro
    jogadores = sync.get("players") if isinstance(sync, dict) else None
    try:
        renumerou = p.resultado("identity.renumber")
    except Exception:
        renumerou = None
    #: **SEM NOTÍCIA, SEM FRASE — JOGAR-02, 09/09/2026.** O recibo devolve `""`
    #: quando não houve o que contar, e um `{"recado": ""}` não é o mesmo que
    #: nenhum recado: o piloto pousaria uma caixa verde VAZIA em cima da
    #: identidade do cartão. `None` é o que faz a tela responder com a piscada
    #: verde no botão, que é como esta casa diz "deu certo" desde a 03-Q4.
    recibo = _painel().recibo_do_reconectar(jogadores, renumerou)
    # O RECADO DO RÁDIO VEM NA FRENTE: ele é o que pede alguma coisa dela (o
    # PS), e o recibo dos jogadores é o que já aconteceu.
    do_radio = _painel().recado_do_radio(voltaram, esperam_o_ps)
    junto = " ".join(parte for parte in (do_radio, recibo) if parte)
    return {"recado": junto} if junto else None


#: OS DOIS DESTA ABA NA LISTA DOS DEZESSEIS, classificados um a um — 02/09/2026.
#:
#: A régua do `--prova-no-aparelho` os marcou como *"sem efeito e sem `SEM_ECO`"*
#: (`docs/process/2026-09-02-O-MAPA-DA-INTERFACE-…` §2.3). **Nenhum dos dois é
#: caso de `SEM_ECO`**, e por isso esta aba continua sem declarar um: `SEM_ECO`
#: quer dizer *"o daemon não publica este assunto"* (é o caso do `trigger.set`,
#: que o DualSense não devolve). Os dois daqui o daemon publica — os cinco
#: métodos de `METODOS` mexem em `native_mode`, `gamepad_emulation`, `coop` e
#: `controllers[].player`, e as quatro chaves estão no `state_full`. Declará-los
#: `SEM_ECO` calaria a régua para sempre sobre um caminho que ela consegue medir.
#:
#: O QUE ELES SÃO, medido contra o estado vivo dela em 02/09 às 04:20
#: (`native_mode false` · `gamepad_emulation.enabled true` · `flavor dualsense`
#: · `coop.players 1` · dois controles, numeração já compacta):
#:
#:     hefesto      A prova clica o rótulo `data-modo="gamepad"`, que é a posição
#:                  **Ligado** — e o daemon JÁ ESTAVA em `gamepad`. Os dois IPCs
#:                  do plano são idempotentes: `native.mode.set{enabled:false}`
#:                  sobre um nativo já desligado e `gamepad.emulation.set
#:                  {enabled:true}` sobre uma emulação já ligada não mudam campo
#:                  nenhum. O gesto NÃO mentiu: ele foi aceito e não havia o que
#:                  mudar.
#:     reconectar   `coop.sync` é um ciclo FORÇADO de reconciliação e
#:                  `identity.renumber` compacta a numeração. Com a mesa já
#:                  reconciliada e já compacta, os dois são no-ops — e quando há
#:                  o que fazer, os dois aparecem em `coop` e em
#:                  `controllers[].player`.
#:
#: LOGO A LISTA DOS DEZESSEIS PRECISA DE UMA QUARTA CAIXA, e é a que faltava no
#: enunciado: além de *"recusou e o instrumento não leu"*, *"o daemon não ecoa"*
#: e *"mentiu"*, existe **"aplicou e não havia o que mudar"**. A régua não sabe
#: separá-la porque ela lê só o `state_full` ANTES e DEPOIS; separar exigiria
#: comparar o estado de ANTES com o que o gesto PEDIU, e isso é do piloto.
#:
#: O QUE ESTA ABA PODE FAZER, E FAZ A PARTIR DE HOJE: **dizer na tela quando o
#: pedido NÃO chegou.** É a faixa laranja (`_faixa_do_pendente`) — até agora um
#: clique que não pegava não deixava rastro nenhum, porque `_aplicar` engole o
#: retorno de propósito (`ACHADO_DO_TIMEOUT`).
#: NOTA DATADA — 13/09/2026, JOGAR-A-FAIXA-QUE-PULA-01: o rastro continua, mas
#: no DIÁRIO da janela (`_relatar_a_pendencia`), e não mais na tela.
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

#: AS FUNÇÕES DA PONTE QUE ESTA ABA USA. Uma só, e o `chamar` é o degrau 3: os
#: quatro métodos abaixo não têm invólucro no `app/ipc_bridge.py` — conferido nas
#: 36 funções que ele expõe.
#: `autoswitch_lock_set` É DEGRAU 2 — 04/09/2026. Ele TEM invólucro no
#: `app/ipc_bridge.py` (o mesmo que a janela antiga aciona no `toggled` do
#: checkbox), e por isso não desce ao `chamar` cru: o degrau 3 é só para o que
#: não tem função em lugar nenhum. Chamá-lo por `chamar("autoswitch.lock", …)`
#: seria a segunda rota para um ato que já tem uma, e a de cá não saberia ler o
#: `autoswitch_locked` que o handler devolve.
#: `resultado` É DEGRAU 3 TAMBÉM, e entrou em 06/09/2026 com o recibo do
#: "Reconectar Controles". Ela é o `chamar` que **não joga o corpo fora**: os
#: dois métodos do botão respondem `{status, players, active}` e
#: `{ok, renumbered}`, e é desse corpo que sai a frase do recibo. Um `chamar`
#: ali devolveria `bool` — o botão que responde calado, que é o defeito que a
#: JOGAR-OS-SEIS-AVISOS-01 fecha.
#: `chamar_detalhado` ENTROU EM 11/09/2026 (A-PERNA-QUE-FALTA-01), e é o
#: `chamar` que **não joga o MOTIVO fora**. A `mascara_do_controle` precisa
#: dele porque `gamepad.mask.set` responde `{"gravado": false, "motivo": …}`
#: dentro de uma resposta bem-sucedida: com `chamar` a tela piscava verde
#: sobre um perfil que não mudou.
PONTE = {"chamar", "chamar_detalhado", "autoswitch_lock_set", "resultado"}
#: OS MÉTODOS CRUS. A régua confere um a um contra o `ipc_server.py`, e um nome
#: inventado reprova AQUI, não na mão de quem clica.
#: OS CINCO DA TROCA DE MODO — os que `ponte.TETOS` cobre com os 2,0 s do
#: produto. Eles são um SUBCONJUNTO de :data:`METODOS`, e a separação nasceu em
#: 04/09/2026 junto com o `gamepad.mask.set`: a folga de 2,0 s existe porque
#: trocar de modo CRIA uinput e faz grab (`mode_transition.MODE_IPC_TIMEOUT_S`),
#: e gravar a máscara de um aparelho não faz nem uma coisa nem outra.
METODOS_DA_TROCA_DE_MODO = {
    "native.mode.set",
    "gamepad.emulation.set",
    "coop.sync",
    "identity.renumber",
    # O `mouse.emulation.restore` SAIU DAQUI em 17/09/2026 (POINT-AND-CLICK-01)
    # porque saiu do PLANO: o terceiro passo do modo Navegação passou a ser o
    # `desktop.arranjo.apply`, logo abaixo. O método continua de pé no daemon —
    # ele é o RECUO para o perfil que não opina —, mas quem o chama é o próprio
    # arranjo, em processo. Declarar aqui um método que esta aba não pede seria
    # a régua verde sobre uma ponte que ninguém atravessa.
}
METODOS = METODOS_DA_TROCA_DE_MODO | {
    # O ARRANJO DO DESKTOP, E ELE FICA FORA DO CONJUNTO ACIMA DE PROPÓSITO —
    # 17/09/2026. Aquele conjunto é uma família de TEMPO: "os que `ponte.TETOS`
    # cobre com os 2,0 s do `MODE_IPC_TIMEOUT_S`". O arranjo tem **3,0 s**,
    # porque abre um `.json` de perfil do disco além de falar com os devices —
    # é a família do `profile.switch`, e a razão está escrita em `ponte.TETOS`.
    # É o mesmo arranjo declarado do `gamepad.mask.set` logo abaixo, pelo
    # motivo simétrico: cobrar dele os 2,0 s mandaria consertar no lugar errado.
    "desktop.arranjo.apply",
    # A MÁSCARA DE UM APARELHO — 04/09/2026, e a AUSÊNCIA dela desta lista é
    # parte da história do defeito que a `mascara_do_controle` acabou de curar:
    # sem o nome aqui, `test_nenhum_pacote_cita_metodo_que_o_daemon_nao_atende`
    # nunca olhou para este método, e a única régua que sobrava era o clique na
    # mão dela.
    #
    # A DÍVIDA DECLARADA AQUI FOI PAGA DOS DOIS LADOS, e o fato velho sai em vez
    # de ficar ao lado do certo. Ela dizia que `gamepad.mask.set` não estava em
    # `ponte.TETOS` e que este gesto não lia o retorno:
    #
    #   * o teto entrou em 04/09/2026 — `ponte.TETOS["gamepad.mask.set"] = 2.0`,
    #     com a razão escrita lá (a máscara grava em disco e pode recriar o
    #     vpad, mesma família do `gamepad.emulation.set`);
    #   * o retorno passou a ser lido em 11/09/2026 (A-PERNA-QUE-FALTA-01): o
    #     gesto chama `chamar_detalhado` e traduz o `motivo` para o cartão.
    "gamepad.mask.set",
    # A RECARGA DO CHIP «STEAM INPUT» — 21/09/2026. O chip a chama desde que
    # nasceu, e quem a DECLARAVA era a aba 07, pelo «Este jogo não funciona»,
    # que saiu com a lista de exclusão. O nome continua vindo de lá
    # (`a07_lancadores.METODO_DA_RECARGA`); a declaração vem para quem chama.
    "launch_env.refresh",
}


#: O QUE ESTA ABA DECLARA À RÉGUA. O piso foi SEIS de 04/09 a 20/09/2026 — o
#: sexto é o `cadeado`, a caixa que ela pediu em 23/07 e que voltou para esta
#: aba pela decisão [03].
#:
#: **O SÉTIMO É O `modo-steam` — STEAM-INPUT-01, 20/09/2026.** Esta linha dizia
#: que ele *"continua marcado no desenho e sem `@gesto` (ver
#: `BOTOES_SEM_DONO`), e por isso ele não conta"*. Ele conta: o gesto é
#: :func:`modo_steam`, e o `BOTOES_SEM_DONO` ficou vazio.
PAGINA = "01-jogar.html"
PISO_DA_ABA = 7

#: AS PROVAS SÃO LITERAIS, E É ESCOLHA — a tentação era montá-las chamando o
#: mesmo `_plano()` que o gesto chama, para "não digitar o que tem dono". Isso
#: teria custado as duas coisas que uma régua existe para dar:
#:
#:   1. **a régua viraria tautologia.** Os dois lados perguntariam ao mesmo
#:      `plan_mode_transition`, e um gesto que passasse a chave ERRADA (o chip
#:      Xbox pedindo a máscara `dualsense`) daria verde nos dois lados;
#:   2. **o pacote deixaria de ser puro.** `PROVAS` é lido no IMPORT, e montá-lo
#:      com `_plano()` puxaria `painel` → `home_actions` → GTK para dentro do
#:      import das dez abas — o contrário do que `_painel()` existe para evitar.
#:
#: O preço, declarado: se o produto mudar a sequência de um modo, ESTA LISTA
#: reprova. É o preço certo — é a régua avisando que a definição do modo se
#: moveu, que é exatamente a notícia que se quer ter.
#:
#: `origin="manual"` aparece em todo passo que DEFINE modo, e não é enfeite: sem
#: ele o daemon lê o pedido como reconciliação automática e o recusa quando há
#: Steam Input na jogada (ORIGEM-QUE-MENTE-01, medido na máquina dela — o botão
#: "Jogar pelo Hefesto" parou de funcionar com o Sackboy marcado).
_MANUAL_ON = {"enabled": True, "origin": "manual"}
_MANUAL_OFF = {"enabled": False, "origin": "manual"}

PROVAS = [
    # LIGADO: sai do Modo Nativo e SÓ ENTÃO liga o gamepad. Invertidos, o vpad
    # nasceria com o físico ainda grabado pelo jogo (HARM-01).
    {"pagina": PAGINA, "gesto": "hefesto", "clique": {"modo": "gamepad"},  # (noqa-acento) id
     "chama": [("chamar", ["native.mode.set"], _MANUAL_OFF),
               ("chamar", ["gamepad.emulation.set"], _MANUAL_ON)]},
    # DESLIGADO é o Modo Nativo, e é UM passo só — decisão dela, 31/08.
    {"pagina": PAGINA, "gesto": "hefesto", "clique": {"modo": "native"},  # (noqa-acento) id
     "chama": [("chamar", ["native.mode.set"], _MANUAL_ON)]},
    # O CHIP ESCOLHE O CAMINHO, NÃO A MÁSCARA (MODO-DE-CONEXAO-01, 13/09/2026):
    # o `caminho` é a única diferença entre este e o Xbox logo abaixo, e sai
    # de `painel.CHIPS_DA_ESCADA` — o que está digitado aqui é a EXPECTATIVA.
    {"pagina": PAGINA, "gesto": "modo-dualsense", "clique": {},  # (noqa-acento) chave do contrato
     "chama": [("chamar", ["native.mode.set"], _MANUAL_OFF),
               ("chamar", ["gamepad.emulation.set"],
                {**_MANUAL_ON, "caminho": "dualsense"})]},
    {"pagina": PAGINA, "gesto": "modo-xbox", "clique": {},  # (noqa-acento) chave do contrato
     "chama": [("chamar", ["native.mode.set"], _MANUAL_OFF),
               ("chamar", ["gamepad.emulation.set"],
                {**_MANUAL_ON, "caminho": "xbox"})]},
    # TRÊS, e o terceiro é o que separa "entrei no modo" de "entrei num modo sem
    # função". Ele vem POR ÚLTIMO de propósito (HARM-06), e desde 17/09/2026 ele
    # lê o PERFIL ATIVO em vez da flag de sessão da máquina
    # (POINT-AND-CLICK-01): mouse, teclas, botões, `teclado_emulado` e a queda
    # da supressão. `origin: manual` porque é gesto dela — sem ele o daemon lê
    # como reconciliação e o lock de 30 s do `apply_profile_mouse` não é furado.
    {"pagina": PAGINA, "gesto": "modo-navegacao", "clique": {},  # (noqa-acento) chave do contrato
     "chama": [("chamar", ["native.mode.set"], _MANUAL_OFF),
               ("chamar", ["gamepad.emulation.set"], _MANUAL_OFF),
               ("chamar", ["desktop.arranjo.apply"], {"origin": "manual"})]},
    # RECONCILIAR ANTES DE RENUMERAR: renumerar primeiro compactaria uma mesa
    # que ainda não está completa (`home_actions.py:3122`).
    #
    # `resultado`, E NÃO `chamar` — 06/09/2026. A prova mudou junto com o gesto,
    # e a troca é a entrega: `chamar` devolve `bool` e o botão respondia calado;
    # `resultado` traz o corpo, que é de onde sai quantos jogadores voltaram e
    # se a numeração compactou. Se alguém devolver o `chamar` para cá, esta
    # linha reprova — que é exatamente a notícia que se quer ter.
    {"pagina": PAGINA, "gesto": "reconectar", "clique": {},  # (noqa-acento) chave do contrato
     "chama": [("resultado", ["coop.sync"], {}),
               ("resultado", ["identity.renumber"], {})]},
    # A MÁSCARA DE UM APARELHO — a prova que FALTAVA, e a falta custou o gesto
    # inteiro. Ela é a única desta lista que mede os PARÂMETROS POR NOME, e é
    # exatamente o que o defeito de 03/09 escondia: o dicionário ia posicional,
    # caía no `timeout` do `ponte.chamar`, e o gesto estourava dentro da ponte
    # sem gravar nada. A régua compara os posicionais tupla a tupla — com o
    # dicionário no lugar errado, `a` é uma 2-tupla contra a 1-tupla esperada.
    #
    # O RÓTULO DA TELA VIRA `flavor` PELO DONO (`mesa_viva.NOME_DA_MASCARA`),
    # nunca por um mapa digitado aqui: o que está declarado é a EXPECTATIVA.
    #
    # A FUNÇÃO DA PONTE MUDOU EM 11/09/2026 (A-PERNA-QUE-FALTA-01) e esta linha
    # foi junto: `chamar_detalhado`, porque o `motivo` da resposta é o que faz a
    # tela dizer que a máscara vale e NÃO ficou guardada. A régua continua
    # medindo os parâmetros por nome, que é o que o defeito de 03/09 escondia.
    {"pagina": PAGINA, "gesto": "mascara",  # (noqa-acento) chave do contrato
     "clique": {"uniq": "aa:bb:cc:00:00:01", "mascara": "Xbox 360"},
     "chama": [("chamar_detalhado", ["gamepad.mask.set"],
                {"uniq": "aa:bb:cc:00:00:01", "flavor": "xbox"})]},
    # O CADEADO — 04/09/2026. Ele NÃO passa pelo `chamar`: `autoswitch_lock_set`
    # é função da ponte (degrau 2), a mesma que a janela antiga aciona.
    #
    # O `locked` VAI POR NOME e vai ABSOLUTO, e a régua mede as duas coisas: um
    # `locked=None` daria toggle no daemon e a prova passaria com `kw` vazio,
    # que é exatamente o defeito que este gesto não pode ter (um clique chega
    # DUAS vezes ao ouvinte único — `click` e `change` — e dois toggles são um
    # no-op). O `ctx` da régua tem `autoswitch_locked` ausente, logo o cadeado
    # está DESTRAVADO e o clique pede `True`.
    {"pagina": PAGINA,  # (noqa-acento) chave do contrato
     "gesto": "cadeado", "clique": {"evento": "click"},
     "chama": [("autoswitch_lock_set", [], {"locked": True})]},
]
