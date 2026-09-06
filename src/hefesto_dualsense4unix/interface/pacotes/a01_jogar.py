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

from typing import Any

from . import Contexto, jogador_de, registrar

#: OS ENDEREÇOS DA PÁGINA que esta aba promete pintar — os que valem para a tela
#: inteira. Eles existem como TUPLA, e não soltos no `return`, porque o
#: `cobertura` é a promessa que a régua confere: uma chave nova que não entre
#: aqui vira um contador que mente, e ele é O instrumento com que esta casa
#: prova que um endereço existe.
DA_PAGINA: tuple[str, ...] = (
    "atencao-conta",
    "aviso-selo",
    "aviso-texto",
    "aviso-vivo",
    # O CADEADO DA TROCA AUTOMÁTICA — 04/09/2026, decisão [03] do PO sobre esta
    # aba: *"Volta para a Jogar, embaixo de Modo."*
    #
    # O PEDIDO É DELA E É DE 23/07. A caixa saiu do desenho por escolha minha,
    # declarada na legenda desta página — *"A caixa saiu — o perfil ativo já diz
    # isso"* —, e o que mudou desde então é que a coluna **Atenção** passou a ler
    # `painel.AVISOS_DA_TELA`: `autoswitch_lock_text` e `texto_do_cadeado_cego`
    # são duas das seis fontes. Logo esta tela EXPLICA o cadeado hoje e não
    # oferece onde ligá-lo — em nenhuma das dez abas.
    "cadeado",
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
    "pendente",
    "pendente-alvo",
    "pendente-ha",
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
POR_CARTAO: tuple[str, ...] = ("plastico", "desenho", "jogador", "jogador-espera",
                               "bateria", "identidade", "mascara-cartao")

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
ORDEM_DA_GRAVIDADE: tuple[str, ...] = (
    "PAUSA", "ERRO", "GAMEPAD", "PONTE", "JOGO", "CONTROLE", "RÁDIO", "PERFIL",
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
    "Nenhum controle ligado agora. Conecte um pelo cabo ou pelo "
    "rádio — ele aparece sozinho, sem recarregar esta tela."
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
#: SEMPRE (`ipc_handlers.py:6139`, sem gate de modo), `set_mask` persiste em
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
    "Guardada por controle: o Hefesto não está entregando o controle ao jogo "
    "agora, e a escolha vale assim que ele voltar a entregar."
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
    "O lugar está reservado e o jogo ainda não recebeu este controle. "
    "O número fica forte quando ele entrar na partida."
)

CADEADO_ROTULO = "Não trocar de perfil sozinho ao abrir um jogo"
CADEADO_DICA = (
    "Congela a troca automática: o perfil que você deixou ativo continua "
    "valendo mesmo ao abrir qualquer jogo. "
    "Desmarque para o Hefesto voltar a escolher o perfil por você."
)


def _cadeado(state: dict[str, Any]) -> str:
    """``"sim"`` com o cadeado ligado, ``""`` quando não — na língua do `marcado`.

    O ALVO É O DÉCIMO (`hefesto_vivo`, `data-hef-alvo="marcado"`), e a língua
    dele é a MESMA do alvo `classe` booleano: ``sim`` liga, e vazio, travessão
    ou qualquer outra palavra DESLIGAM. Uma segunda palavra para o mesmo
    "ligado" seria a terceira maneira de dizer a mesma coisa.

    **SEM DAEMON A CAIXA DESMARCA, e isso é escolha declarada.** Um checkbox tem
    dois estados e o produto tem três — a aba inteira já resolve isso do mesmo
    jeito (`_estado_da_tela` devolve `""` e o interruptor apaga as duas
    posições). Marcar sobre um estado que ninguém leu seria a tela afirmando uma
    escolha dela que ela não fez; o inverso apenas mostra o padrão do produto,
    que é destravado.

    SÓ O ``True`` LITERAL LIGA, a mesma disciplina do `wrapper_used` e do
    `texto_da_pausa`: chave ausente (daemon antigo) ou valor de outro tipo não
    marcam a caixa.
    """
    return "sim" if state.get("autoswitch_locked") is True else ""


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
    """
    if jogador_de(c) is None:
        return ""
    return "" if c.get("player") is not None else "1"


def mascaras_montaveis() -> frozenset[str]:
    """Os rótulos de máscara que o produto SABE MONTAR — para o desenho perguntar.

    O gerador (`aba01._chips_de_mascara`) apaga o chip que não estiver aqui e
    põe a razão na dica: é a D-03 dela (*"cinza antes, com a razão na dica"*)
    aplicada ao único chip que recusa em TODO modo, o **Nintendo Pro**.

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
        }

    # A COLUNA ATENÇÃO — as fontes do PRODUTO, não uma segunda leitura. Ver
    # `_avisos`: todas já estavam escritas fora daqui (`app/actions/`, e desde
    # 06/09 também `integrations/storm_doctor`) e nenhuma frase nasce aqui.
    avisos = _avisos(ctx)
    selos, textos = _coluna_de_avisos(avisos)

    # A FAIXA LARANJA. Os dois endereços saem daqui SEMPRE — inclusive vazios —
    # porque o que estava cravado na página é uma frase, e uma frase só se apaga
    # escrevendo por cima. Ver `_faixa_do_pendente`.
    frase, alvo = _faixa_do_pendente(ctx.state)

    fora: dict[str, Any] = {
        # A CONTA É DO PRODUTO — `painel.texto_da_conta`, o mesmo que a bancada
        # já chamava. Ela sabe dizer "nenhum aviso", que o desenho não tem
        # (o mockup crava "1 aviso") e que é o estado normal de uma máquina
        # saudável.
        #
        # ELA CONTAVA ERRADO ATÉ 03/09/2026: era `len(achados)` do exame da
        # mesa INTEIRO, incluindo os `certo` — a tela dizia "3 avisos" sob o
        # cabeçalho laranja **Atenção** com três linhas em que duas eram boas
        # notícias. Agora conta o que a coluna mostra.
        "atencao-conta": _painel().texto_da_conta(len(avisos)),
        "aviso-selo": selos,
        "aviso-texto": textos,
        # O ACENDEDOR DAS LINHAS. Um `aviso-item` sem aviso não pode ficar com o
        # travessão à mostra: a coluna teria seis linhas de `— —` numa máquina
        # sem nada a dizer. O alvo `classe` sem `data-hef-quando` é BOOLEANO
        # (`hefesto_vivo.escrever`), e o travessão que o piloto escreve num
        # valor vazio conta como desligado — então a lista de `"1"` acende
        # exatamente as que têm texto.
        # O ACENDEDOR ACOMPANHA AS SEIS, e não só as acesas — ver a nota do
        # `_coluna_de_avisos`. Uma lista curta some inteira quando fica vazia, e
        # é justamente a coluna VAZIA que precisa apagar o aviso do desenho.
        "aviso-vivo": ["1" if s else "" for s in selos],
        # A FRASE DA MESA e a RESSALVA DA MÁSCARA — as duas saem SEMPRE,
        # inclusive vazias, pela mesma razão da faixa laranja: o que se apaga é
        # o que se escreve por cima. O `""` vira travessão no piloto, e o alvo
        # `classe` do elemento de fora lê travessão como desligado.
        "mesa-frase": _frase_da_mesa(ctx),
        "mascara-ressalva": _ressalva_da_mascara(ctx.state),
        # O CADEADO — decisão [03], 04/09/2026. A coluna Atenção já EXPLICA o
        # cadeado desde 03/09 (`autoswitch_lock_text` é uma das seis fontes); o
        # que faltava, em todas as dez abas, era onde ligá-lo. Ver `_cadeado`.
        "cadeado": _cadeado(ctx.state),
        "cartoes": cartoes,
        # O INTERRUPTOR E A FILEIRA, VIVOS — 03/09/2026. Ver `_estado_da_tela`.
        **_estado_da_tela(ctx.state),
        "pendente": frase,
        "pendente-alvo": alvo,
        # A FAIXA SÓ EXISTE COM PENDÊNCIA. Sem isto ela virava um travessão
        # solto na caixa tracejada, porque o piloto escreve `—` no lugar de um
        # valor vazio — medido em 02/09/2026. O espaço continua reservado
        # (`visibility`, não `display`): "muda tudo ao clicar" é queixa dela, e
        # a legenda desta aba promete que a tela não pula.
        "pendente-ha": "1" if frase else "",
    }
    fora["cobertura"] = {
        # A PROMESSA, e ela se conta sozinha: `DA_PAGINA` e `POR_CARTAO` são as
        # listas de endereço, e emitir uma chave sem pô-la lá deixa o contador
        # menor que o pacote — que é o defeito que este número existe para
        # denunciar.
        "pintados": len(DA_PAGINA) + len(cartoes) * len(POR_CARTAO),
        "sem_dono": 0,
    }
    # `perfil`, `conta` e `conta-b` NÃO saem daqui: são do cabeçalho, que é das
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
    """A coluna **Atenção**: ``[{"selo", "texto", "fonte"}, …]``, das fontes do produto.

    **NADA SE ESCREVE AQUI.** As fontes já existiam, e todas fora deste
    arquivo — o que faltava era o produto novo CHAMÁ-LAS. Medido em
    03/09/2026: quem consumia `painel.AVISOS_DA_TELA` era `interface/jogar_vivo.
    py`, que é BANCADA; a aba publicada mostrava, no lugar delas, o Check-up da
    aba Conexões — dois conjuntos DISJUNTOS, e o da GTK era o que respondia
    pelas perguntas desta tela.

    O QUE ENTRA, e em que ordem:

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
    4. **a cura do travamento do USB**
       (:func:`_aviso_da_cura_do_travamento`) — a fonte que nasceu em
       06/09/2026, ONDA5-01-01. Ela não é função de `state`: lê o disco, como
       a ponte lê a cor do produto;
    5. **os achados GRAVES do exame da mesa** (`a08_conexoes._exame`), que era o
       único que esta coluna já mostrava. Os ``certo`` ficam de fora: a coluna
       chama-se Atenção.

    **FATO SUBSTITUÍDO — 06/09/2026.** Estas linhas diziam *"as oito fontes"* e
    enumeravam TRÊS itens: o número foi escrito em 03/09 e a ponte entrou em
    04/09 sem ninguém somar. Contadas hoje, uma a uma, são **dez** (as seis
    puras mais quatro canais), e a décima é a desta sprint. Um número que
    envelhece a cada fonte nova é convite a esta mesma correção daqui a uma
    semana — por isso o que fica escrito é a LISTA, que se conta sozinha.

    O SELO DO OPT-OUT É ``GAMEPAD``, e não uma palavra nova: é o mesmo que
    `AVISOS_DA_TELA` dá ao vpad degradado, e os dois falam do mesmo assunto — o
    gamepad virtual que o jogo vê. Inventar um selo a mais poria uma palavra de
    tela num arquivo que não é o dono de nenhuma.
    """
    painel = _painel()
    fora: list[dict[str, str]] = list(painel.avisos_do_estado(ctx.state))

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

    # A CURA DO TRAVAMENTO DO USB — sob `try` PRÓPRIO, que é a política deste
    # arquivo: uma fonte que levanta não derruba a coluna, ela vira selo
    # ``ERRO``. Esta lê DOIS ARQUIVOS DO SISTEMA por chamada — se um `/sys`
    # remontado ou um `/etc` sem permissão levantar, as outras nove continuam
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
                     "texto": f"o exame da mesa não respondeu ({type(erro).__name__}).",
                     "fonte": "a08_conexoes._exame"})
    return fora


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
    from hefesto_dualsense4unix.gui.aba_sistema import sem_markup

    ruim = str(getattr(home_actions, "_COR_AVISO", "") or "")
    if not ruim:
        return None
    frase = home_actions.texto_da_ponte(state)
    if ruim not in frase:
        return None
    texto = sem_markup(frase)
    # O PREFIXO SAI porque o SELO É ELE. Deixar os dois escreveria
    # "PONTE  Ponte com o jogo: nenhuma —…" na mesma linha, que é a repetição
    # que esta casa tira do `<title>` do glifo e do `title` do cartão.
    if texto.startswith(home_actions.PONTE_PREFIXO):
        texto = texto[len(home_actions.PONTE_PREFIXO):]
    return {"selo": SELO_DA_PONTE, "texto": texto,
            "fonte": "home_actions.texto_da_ponte"}


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
        return (f"Há {quantos} controles na mesa e esta tela mostra "
                f"{lugares}: o cabeçalho conta todos.")
    return ""


def _ressalva_da_mascara(state: dict[str, Any]) -> str:
    """A linha da máscara quando ela ainda não tem efeito — ``""`` quando tem.

    A QUEIXA É DELA, e é a primeira da lista de 04/09: *"independente do modo a
    mascara deve funcionar ali sempre."*

    O QUE ELA SENTE, medido: fora do modo `gamepad` **não existe gamepad
    virtual**, e `mascara_efetiva` só é lida na criação de um
    (`gamepad.py:2162`). O clique é aceito, gravado no disco e não muda nada que
    se veja. A janela GTK escondia a caixa inteira fora do modo `gamepad`
    (`home_actions.py:2648`); esta tela deixava clicar e ficava calada — que é
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
    if not state:
        return ""
    from hefesto_dualsense4unix.app.actions.mode_transition import MODE_GAMEPAD

    modo = _painel().modo_vivo(state)
    if modo is None or modo == MODE_GAMEPAD:
        return ""
    return RESSALVA_DA_MASCARA


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
    * `home_actions.mascara_do_aparelho` — a máscara que o JOGO vê agora, com a
      diferença entre a explícita e a deduzida do ``backend``, e ``None`` quando
      não dá para saber.

    O CHIP ACESO É O INVERSO DO `_plano_do_chip`, e sai da MESMA tabela
    (`painel.CHIPS_DA_ESCADA`): um chip com ``modo`` é um modo do produto (a
    **Navegação**), os outros são MÁSCARAS do modo ``gamepad``. Escrever aqui um
    ``if chave == "dualsense"`` seria a segunda cópia de uma tradução que já tem
    dono — a mesma que o gesto usa para o caminho de ida.

    O STEAM INPUT NUNCA ACENDE, e é a mesma guarda do gesto: ele nomeia a ponte
    do DualSense com ``steam_input=True``, e sem a guarda ele empataria com o
    chip **Sony DualSense** pela máscara. Quem fixa um degrau é o PS+R3, e não
    há IPC que o diga — acendê-lo por dedução seria a tela afirmando uma escolha
    que ninguém fez.

    DAEMON CALADO NÃO PINTA NADA, e esta é a armadilha desta função: `mode_of_
    state({})` devolve **desktop** — ele só devolve ``None`` para um
    não-dicionário —, então pintar sem esta guarda acenderia **Ligado** sobre um
    estado que ninguém leu. É a mesma guarda que `_pendencia` já tinha de ter, e
    pela mesma razão.
    """
    if not state:
        return {"hef-posicao": "", "modo-aceso": ""}

    from hefesto_dualsense4unix.app.actions.home_actions import mascara_do_aparelho
    from hefesto_dualsense4unix.integrations import ponte_escada

    painel = _painel()
    ligado = painel.hefesto_ligado(state)
    modo = painel.modo_vivo(state)
    mascara = mascara_do_aparelho(state)

    aceso = ""
    for chip in painel.CHIPS_DA_ESCADA:
        if chip.modo:
            if chip.modo == modo:
                aceso = str(chip.chave)
                break
            continue
        ponte = chip.ponte
        if ponte is None or ponte.steam_input or ponte.kind != ponte_escada.KIND_GAMEPAD:
            continue
        if modo == "gamepad" and mascara and ponte.mascara == mascara:
            aceso = str(chip.chave)
            break

    # A MÁSCARA DOS CARTÕES SAIU DAQUI — 03/09/2026. Ela era emitida como valor
    # DE PÁGINA, e o piloto escreve valor de página em TODO elemento com aquele
    # `data-campo`: a máscara da SESSÃO ia para os três chips dos quatro
    # cartões, e dois controles com escolhas diferentes acendiam o mesmo chip.
    # Agora ela sai por cartão (ver `_mascara_do_cartao`); o que fica aqui é o
    # que de fato é da máquina — a posição do interruptor e o chip da fileira.
    # A `mascara` acima continua sendo lida: é ela que decide o `modo-aceso`.
    return {
        # AS PALAVRAS SÃO AS DO DESENHO (`aba01.INTERRUPTOR`), e é o `data-hef-
        # quando` de cada rótulo que decide qual acende — o Python manda o
        # ESTADO, não a classe.
        "hef-posicao": "" if ligado is None else ("ligado" if ligado else "desligado"),
        "modo-aceso": aceso,
    }


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
    tela sabe nomear. É o que mantém o **Nintendo Pro** apagado — ele está
    desenhado e o produto não sabe montá-lo — e o que impede o travessão da mesa
    vazia de virar um rótulo. Sem correspondência a resposta é ``""``, e o alvo
    `classe` apaga os três chips: campo sem informação não mostra nada.
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
    tela e o produto não sabe montar (o **Nintendo Pro** — resposta ``""``, o
    chip fica apagado e isso é a verdade) de uma mesa que simplesmente não falou
    de máscara (resposta: a da sessão, que é o que valia antes).
    """
    import monta  # o `pacotes/__init__` põe `interface/` no `sys.path`

    return set(monta.MASCARAS)


def _rotulo_da_mascara(mascara: str | None) -> str:
    """A máscara do produto na palavra do DESENHO — ``""`` quando não há.

    São dois vocabulários, e as CHAVES não se digitam: `ponte_escada.MASCARA_*`
    é o dono delas, e uma renomeação lá apaga a linha aqui em vez de deixar duas
    verdades vivas. Os VALORES são os rótulos dos chips do cartão
    (`monta.MASCARAS`), que é tela — e tela é dela.

    **"Nintendo Pro" não tem entrada, e nunca terá enquanto o daemon recusar em
    voz alta tudo o que não for `dualsense`/`xbox`** (`ipc_handlers.py:5090`).
    O chip continua no cartão por ordem dela; apagado é a verdade sobre ele — e
    era exatamente o chip **Xbox 360** aceso no cartão do P2, com o daemon em
    `flavor=dualsense`, que esta função existe para apagar.
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

    `campo` é `"modo"` ou `"mascara"`, que são as duas chaves de
    `home_actions.reconciliar_pendente` — as mesmas da janela estável. Escrever
    um terceiro nome aqui faria a reconciliação passar batido por ele.
    """
    if not valor:
        return
    _ESCOLHA[campo] = valor
    _ROTULO[campo] = rotulo or _rotulo_de(campo, valor)


def _rotulo_de(campo: str, valor: str) -> str:
    """A palavra aprovada por ela para aquela chave, sem passar pela tela.

    Rede de segurança para quando o clique não trouxe `texto` (um dublê de
    régua, um botão que a pintura trocou no meio). Sai de
    `painel.CHIPS_DA_ESCADA`, que é o dono dos rótulos da fileira — digitá-los
    aqui seria a segunda cópia da palavra dela.
    """
    if campo == "mascara":
        for chip in _painel().CHIPS_DA_ESCADA:
            ponte = chip.ponte
            if ponte is not None and ponte.mascara == valor:
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
    """
    from hefesto_dualsense4unix.app.actions.relancar import (
        MARCADOR_PENDENTE,
        texto_do_pendente,
    )

    sobra = _pendencia(state)
    if not sobra:
        return "", ""
    rotulos = [_ROTULO.get(c, sobra[c]) for c in ("modo", "mascara") if c in sobra]
    frase = texto_do_pendente(
        modo=_ROTULO.get("modo", sobra.get("modo")) if "modo" in sobra else None,
        mascara=(_ROTULO.get("mascara", sobra.get("mascara"))
                 if "mascara" in sobra else None),
    )
    marca = f"{MARCADOR_PENDENTE} "
    if frase.startswith(marca):
        resto = frase[len(marca):]
        frase = marca + resto[:1].upper() + resto[1:]
    return frase, ", ".join(rotulos)


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
BOTOES_SEM_DONO: dict[str, str] = {
    "modo-steam": (
        "não há IPC de Steam Input entre os métodos que o daemon atende, e o "
        "degrau custa o que nenhum socket paga: `UseSteamControllerConfig` só "
        "sobrevive com a Steam FECHADA (a Steam regrava o `localconfig.vdf` ao "
        "sair — `integrations/steam_input_ponte.py`), então ligar exige fechar "
        "a Steam, reabrir a Steam e reabrir o jogo "
        "(`integrations/ponte_escada.py`, § OS DOIS TRAMOS)."
    ),
}

#: FATO ERRADO, SUBSTITUÍDO — 04/09/2026. Havia aqui uma segunda entrada,
#: `"mascara"`, dizendo *"a máscara do gamepad virtual é UMA para a máquina, não
#: uma por controle: `gamepad.emulation.set` recebe `flavor` e não recebe
#: `uniq`"*. **As duas metades caíram no mesmo dia em que foram escritas**, e o
#: próprio arquivo já dizia o contrário trinta linhas adiante: `gamepad.mask.set`
#: nasceu em 03/09 recebendo `uniq` (`ipc_handlers.py:6139`), o registro
#: `external_mask` guarda a escolha por APARELHO desde 15/08, e o gesto
#: `mascara_do_controle` existe e é `@gesto`. Um botão listado como SEM DONO com
#: o dono declarado no mesmo arquivo manda a próxima pessoa construir o que já
#: está construído — e é como a régua `chips_sem_dono` acusaria falso.
#:
#: O QUE ERA VERDADE E MUDOU DE LUGAR: o 'Nintendo Pro' continua não sendo
#: máscara do produto. Isso deixou de ser "botão sem dono" e virou **botão
#: cinza com a razão na dica**, que é a D-03 dela — ver
#: :func:`mascaras_montaveis` e `aba01._chips_de_mascara`.
_MASCARA_SAIU_DOS_SEM_DONO = (
    "gamepad.mask.set recebe `uniq` e o gesto `mascara` tem dono desde "
    "03/09/2026; o que sobrou do achado antigo é o Nintendo Pro, que agora "
    "fica cinza com a razão na dica em vez de constar como sem dono."
)


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


def _plano(chave: str, mascara: str | None = None) -> list[tuple[str, dict[str, Any]]]:
    """A sequência de IPC daquele modo — DELEGADA, sem uma linha de regra aqui.

    `painel.plano_do_modo` devolve `None` quando o botão não tem escritor, e o
    motivo em português é de `painel.porque_nao_aplica`. Levantar com ELE é o
    que faz o botão recusar DIZENDO, em vez de falhar calado.
    """
    painel = _painel()
    plano: list[tuple[str, dict[str, Any]]] | None = painel.plano_do_modo(
        chave, mascara)
    if plano is None:
        raise RuntimeError(painel.porque_nao_aplica(chave))
    return plano


def _aplicar(p: Any, plano: list[tuple[str, dict[str, Any]]]) -> None:
    """Despacha o plano na ORDEM, pelo degrau 3 da ponte.

    NENHUM DESTES QUATRO MÉTODOS TEM FUNÇÃO NO `app/ipc_bridge.py` — conferido
    nas 36 que ele expõe: `native.mode.set`, `gamepad.emulation.set`,
    `mouse.emulation.restore` e `coop.sync` não estão lá. Então é `p.chamar`,
    que passa pelo mesmo `_safe_call` do bridge e herda o tratamento de erro.

    A ORDEM É A ENTREGA, e ela não é enfeite: `plan_mode_transition` põe o
    `native.mode.set {enabled: false}` ANTES do `gamepad.emulation.set` porque,
    invertidos, *"o vpad nasceria com o físico ainda grabado pelo jogo"*.

    O RETORNO NÃO VIRA ERRO, e o motivo está medido — ver `ACHADO_DO_TIMEOUT`.
    """
    for metodo, params in plano:
        p.chamar(metodo, **params)


#: FATO CADUCO, SUBSTITUÍDO — 03/09/2026. Este bloco afirmava que
#: **`pacotes/ponte.chamar` não tem folga de tempo** e que ele chamava
#: `_safe_call` com o default de 250 ms, o teto de LEITURA da ponte; e mandava
#: quem lesse construir a cura em `ponte.py`, *"que não é território desta aba"*.
#:
#: **A CURA JÁ ESTÁ LÁ, e a medição é de uma linha:** `ponte.TETOS`
#: (`pacotes/ponte.py`) declara **2,0 s** para os CINCO métodos desta aba —
#: `native.mode.set`, `gamepad.emulation.set`, `mouse.emulation.restore`,
#: `coop.sync` e `identity.renumber` —, que é o mesmo valor de
#: `mode_transition.MODE_IPC_TIMEOUT_S`, e `ponte.teto()` só cai nos 250 ms para
#: método que não esteja na tabela. Conferido método a método contra
#: `a01_jogar.METODOS`: os cinco estão lá.
#:
#: POR QUE ISTO NÃO É NOTA DE RODAPÉ: quem lesse o texto antigo iria construir
#: uma cura já construída, e a regra desta casa é que fato errado se SUBSTITUI —
#: mantê-lo ao lado do certo obriga a próxima pessoa a escolher entre duas
#: afirmações.
#:
#: O QUE CONTINUA VALENDO, e é o motivo de `_aplicar` não levantar com o retorno:
#: a folga é 2,0 s, não infinito. Um `p.chamar("gamepad.emulation.set", …)` ainda
#: pode voltar `False` com o modo aplicado se o daemon passar do prazo, e
#: levantar aí reintroduziria o defeito que o `MODE_IPC_TIMEOUT_S` curou — a tela
#: dizendo "não deu" sobre um gesto que deu. Quem responde por isso é a FAIXA
#: LARANJA: uma pendência só nasce quando o daemon não alcançou o pedido, e ela
#: some sozinha quando alcança.
ACHADO_DO_TIMEOUT = (
    "ponte.TETOS dá 2,0 s aos cinco métodos desta aba, o mesmo valor de "
    "mode_transition.MODE_IPC_TIMEOUT_S; o teto de 250 ms é só o dos métodos "
    "fora da tabela."
)


@gesto("01-jogar.html", "hefesto")
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
    _aplicar(p, _plano(chave))
    # DEPOIS de despachar, nunca antes: `_plano` levanta para um botão sem
    # escritor, e anotar uma pendência que não chegou a sair prometeria uma
    # mudança que ninguém pediu ao daemon.
    _lembrar("modo", chave, str(o.get("texto") or ""))


def _plano_do_chip(chave: str) -> list[tuple[str, dict[str, Any]]]:
    """A sequência daquele chip da fileira — a máscara sai do PRODUTO.

    `painel.CHIPS_DA_ESCADA` é quem guarda qual ponte cada chip nomeia
    (`Ponte(KIND_GAMEPAD, MASCARA_DUALSENSE)` para o "Sony DualSense", `…XBOX`
    para o "Xbox"). Digitar `"dualsense"` aqui seria a segunda cópia de um valor
    que já tem dono — e que muda de lugar quando a `ESCADA` mudar.

    DOIS CAMINHOS, e a diferença é a que `painel` documenta: um chip com `modo`
    (a **Navegação**) É um modo do produto e vai por ele; os outros são
    MÁSCARAS do mesmo modo `gamepad`, e vão pelo `flavor` do plano.
    """
    from hefesto_dualsense4unix.app.actions.mode_transition import MODE_GAMEPAD
    from hefesto_dualsense4unix.integrations import ponte_escada

    chip = next((c for c in _painel().CHIPS_DA_ESCADA if c.chave == chave), None)
    if chip is None:
        raise ValueError(f"modo: {chave!r} não é chip da fileira desta aba")
    if chip.modo:
        # A Navegação: `apply_mode('desktop')`, os três IPCs em ordem.
        return _plano(chip.modo)
    ponte = chip.ponte
    if ponte is None or ponte.kind != ponte_escada.KIND_GAMEPAD or ponte.steam_input:
        raise RuntimeError(BOTOES_SEM_DONO.get(f"modo-{chave}", "sem dono no produto"))
    return _plano(MODE_GAMEPAD, ponte.mascara)


def _lembrar_do_chip(chave: str, o: dict[str, Any]) -> None:
    """Anota o que o chip clicado pediu, no EIXO dele — e só nele.

    UM CHIP MEXE NUM EIXO SÓ, e é o que o `_plano_do_chip` já diz: a Navegação
    **é** um modo (`chip.modo`), os outros são MÁSCARAS do mesmo modo `gamepad`
    (`chip.ponte.mascara`). Anotar `modo=gamepad` junto com a máscara poria na
    faixa a palavra do CHIP ("Xbox") sob o rótulo do INTERRUPTOR ("Ligado") —
    duas coisas com nomes diferentes na tela dela, coladas numa linha só.

    Qual eixo é de cada chip sai de `painel.CHIPS_DA_ESCADA`, e não de um `if`
    por nome: é o mesmo lugar de onde `_plano_do_chip` tira a ponte.
    """
    chip = next((c for c in _painel().CHIPS_DA_ESCADA if c.chave == chave), None)
    if chip is None:
        return
    rotulo = str(o.get("texto") or "")
    if chip.modo:
        _lembrar("modo", chip.modo, rotulo)
        return
    ponte = chip.ponte
    if ponte is not None and ponte.mascara:
        _lembrar("mascara", str(ponte.mascara), rotulo)


@gesto("01-jogar.html", "modo-dualsense")
def modo_dualsense(ctx: Contexto, o: dict[str, Any], p: Any) -> None:
    """"Sony DualSense": o jogo desenha os botões do PlayStation.

    É a máscara `054c:0df2`, e ela é o PRIMEIRO degrau que o produto tenta —
    `ponte_escada.ESCADA[0]`. A razão está contada no cabeçalho de lá: **dez**
    linhas do `mapa-controles.csv` só chegam ao jogo por `uhid` (giroscópio,
    acelerômetro, touchpad, bateria, o jack de áudio, o rumble por FF…), e a
    máscara Xbox não tem onde pôr nenhuma delas. *"Errar para DualSense custa um
    aperto de botão; errar para Xbox custa dez linhas do mapa, e custa em
    silêncio."*

    O modo continua sendo `gamepad`: o que muda entre este chip e o "Xbox" é o
    `flavor`, não o modo. É por isso que o plano tem os mesmos dois passos.
    """
    _aplicar(p, _plano_do_chip("dualsense"))
    _lembrar_do_chip("dualsense", o)


@gesto("01-jogar.html", "modo-xbox")
def modo_xbox(ctx: Contexto, o: dict[str, Any], p: Any) -> None:
    """"Xbox": o formato que todo jogo entende — o SEGUNDO que o Hefesto tenta.

    ESTE CHIP NASCEU EM 31/08/2026 E É UMA DÍVIDA PAGA: `Ponte(gamepad, xbox)` é
    degrau da `ESCADA` desde 19/08 e **nenhum chip o nomeava** — era o que
    `painel.degraus_sem_chip()` denunciava. A escada automática passava por ele
    e a tela não tinha onde mostrá-lo.

    O preço dele está medido e não se esconde: `045e:028e` é `uinput`, o pacote
    do Xbox 360 é fixo desde 2005, e quem escolhe esta máscara *"escolhe rumble
    por evdev que funciona em tudo e paga com as cinco features"*
    (`docs/protocol/pilha-steam-input-xpad-sdl.md` §1.5).
    """
    _aplicar(p, _plano_do_chip("xbox"))
    _lembrar_do_chip("xbox", o)


@gesto("01-jogar.html", "mascara", grava="gamepad.mask.set")
def mascara_do_controle(ctx: Contexto, o: dict[str, Any], p: Any) -> None:
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

    DUAS MÁSCARAS EXISTEM, E TRÊS CHIPS ESTÃO DESENHADOS. `mascaras_validas()`
    devolve `{dualsense, xbox}` — o "Nintendo Pro" é desenho sem motor, e aqui
    ele RECUSA DIZENDO em vez de gravar um valor que o daemon não sabe montar.
    Escolher o silêncio seria repetir o defeito que este gesto veio curar.

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
                f"Não há controle no lugar {lugar.upper()}. A máscara é de um "
                "aparelho: ligue um controle aqui e ele recebe a escolha.")
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
    p.chamar("gamepad.mask.set", uniq=uniq, flavor=flavor)


@gesto("01-jogar.html", "modo-navegacao",
       grava="liga o mouse emulado e o ponteiro anda na tela dela")
def modo_navegacao(ctx: Contexto, o: dict[str, Any], p: Any) -> None:
    """"Navegação": o controle vira teclado e mouse do computador.

    O CASO DO MEIO, e `painel` o explica melhor do que eu resumiria: a Navegação
    **não é degrau da `ESCADA`** (`KIND_DESKTOP` existe como constante e
    `indice_do_degrau` devolve -1 — por isso o PS+R3 não para aqui) e **tem
    escritor**: `apply_mode('desktop')` funciona hoje. Confundir as duas
    perguntas pintaria "sem dono" sobre um botão que dá — é a diferença entre
    `chips_sem_degrau()` e `chips_sem_dono()`.

    SÃO TRÊS IPCs, e o terceiro é o que faz a diferença entre entrar no modo e
    entrar num modo sem função: `mouse.emulation.restore` LIGA o mouse conforme
    a preferência que o daemon persistiu (HARM-06). Sem ele, o modo desktop
    desligava os outros dois e deixava o controle sem fazer nada até alguém
    achar a aba Mouse — foi o `MODO-QUE-NAO-CONTROLA-01`, medido com ela ao
    vivo: *"cliquei em aplicar e nada"*. E ele vem POR ÚLTIMO: ligar o mouse
    antes de o gamepad sair faria a exclusão mútua do daemon derrubar o mouse
    recém-ligado. A ordem é do plano, não daqui.
    """
    _aplicar(p, _plano_do_chip("navegacao"))
    _lembrar_do_chip("navegacao", o)


@gesto("01-jogar.html", "cadeado", grava="autoswitch_lock_set")
def cadeado(ctx: Contexto, o: dict[str, Any], p: Any) -> None:
    """A caixa "Não trocar de perfil sozinho ao abrir um jogo".

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
    """
    if str(o.get("evento") or "change") != "change":
        return
    p.autoswitch_lock_set(locked=_cadeado(ctx.state) != "sim")


@gesto("01-jogar.html", "reconectar")
def reconectar(ctx: Contexto, o: dict[str, Any], p: Any) -> None:
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
    (`ipc_handlers.py:5190`).

    PASSO 2 — `identity.renumber`: compacta a numeração preservando a ordem
    relativa. **A ORDEM É A ENTREGA** e está escrita no botão antigo
    (`home_actions.py:3122`): *"renumerar antes de reconciliar compactaria uma
    mesa que ainda não está completa."*

    E A RECUSA DO SEGUNDO NÃO É ERRO: com o jogo aberto o daemon recusa
    renumerar (repintar o LED do controle em uso no meio da partida é o defeito
    que a NUMA-03 fechou), e os jogadores já voltaram no passo 1. Tratar isso
    como falha seria a interface mentindo — é a mesma regra do
    `reported_step_index`. Por isso os dois passos vão sem levantar.
    """
    p.chamar("coop.sync")
    p.chamar("identity.renumber")


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
OS_DOIS_DA_LISTA_DOS_DEZESSEIS: dict[str, str] = {
    "hefesto": (
        "aplicou e não havia o que mudar: a prova clica a posição Ligado e o "
        "daemon já estava em `gamepad` (`native_mode false`, "
        "`gamepad_emulation.enabled true`). Os dois IPCs são idempotentes."
    ),
    "reconectar": (
        "aplicou e não havia o que mudar: `coop.sync` reconcilia uma mesa já "
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
PONTE = {"chamar", "autoswitch_lock_set"}
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
    "mouse.emulation.restore",
    "coop.sync",
    "identity.renumber",
}
METODOS = METODOS_DA_TROCA_DE_MODO | {
    # A MÁSCARA DE UM APARELHO — 04/09/2026, e a AUSÊNCIA dela desta lista é
    # parte da história do defeito que a `mascara_do_controle` acabou de curar:
    # sem o nome aqui, `test_nenhum_pacote_cita_metodo_que_o_daemon_nao_atende`
    # nunca olhou para este método, e a única régua que sobrava era o clique na
    # mão dela.
    #
    # DÍVIDA DECLARADA, e ela é de `pacotes/ponte.py`: `gamepad.mask.set` não
    # está em `ponte.TETOS`, logo cai nos 250 ms do bridge — que cobrem também
    # a LEITURA da resposta. `set_mask` grava um JSON no disco; sob carga, o
    # `chamar` pode voltar `False` com a escolha JÁ gravada, e este gesto não
    # lê o retorno. Uma linha em `TETOS` (2,0 s) fecha isso, e ela não é desta
    # aba.
    "gamepad.mask.set",
}


#: O QUE ESTA ABA DECLARA À RÉGUA. O piso é SEIS desde 04/09/2026 — o sexto é o
#: `cadeado`, a caixa que ela pediu em 23/07 e que voltou para esta aba pela
#: decisão [03]. O `modo-steam` continua marcado no desenho e **sem** `@gesto`
#: (ver `BOTOES_SEM_DONO`), e por isso ele não conta.
PAGINA = "01-jogar.html"
PISO_DA_ABA = 6

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
    # O CHIP MUDA A MÁSCARA, NÃO O MODO: o `flavor` é a única diferença entre
    # este e o Xbox logo abaixo. Ele sai de `painel.CHIPS_DA_ESCADA`, não é
    # digitado no gesto — o que está digitado aqui é a EXPECTATIVA.
    {"pagina": PAGINA, "gesto": "modo-dualsense", "clique": {},  # (noqa-acento) chave do contrato
     "chama": [("chamar", ["native.mode.set"], _MANUAL_OFF),
               ("chamar", ["gamepad.emulation.set"],
                {**_MANUAL_ON, "flavor": "dualsense"})]},
    {"pagina": PAGINA, "gesto": "modo-xbox", "clique": {},  # (noqa-acento) chave do contrato
     "chama": [("chamar", ["native.mode.set"], _MANUAL_OFF),
               ("chamar", ["gamepad.emulation.set"],
                {**_MANUAL_ON, "flavor": "xbox"})]},
    # TRÊS, e o terceiro é o que separa "entrei no modo" de "entrei num modo sem
    # função": `mouse.emulation.restore` liga o mouse conforme a preferência
    # persistida (HARM-06), e vem POR ÚLTIMO de propósito.
    {"pagina": PAGINA, "gesto": "modo-navegacao", "clique": {},  # (noqa-acento) chave do contrato
     "chama": [("chamar", ["native.mode.set"], _MANUAL_OFF),
               ("chamar", ["gamepad.emulation.set"], _MANUAL_OFF),
               ("chamar", ["mouse.emulation.restore"], {})]},
    # RECONCILIAR ANTES DE RENUMERAR: renumerar primeiro compactaria uma mesa
    # que ainda não está completa (`home_actions.py:3122`).
    {"pagina": PAGINA, "gesto": "reconectar", "clique": {},  # (noqa-acento) chave do contrato
     "chama": [("chamar", ["coop.sync"], {}),
               ("chamar", ["identity.renumber"], {})]},
    # A MÁSCARA DE UM APARELHO — a prova que FALTAVA, e a falta custou o gesto
    # inteiro. Ela é a única desta lista que mede os PARÂMETROS POR NOME, e é
    # exatamente o que o defeito de 03/09 escondia: o dicionário ia posicional,
    # caía no `timeout` do `ponte.chamar`, e o gesto estourava dentro da ponte
    # sem gravar nada. A régua compara os posicionais tupla a tupla — com o
    # dicionário no lugar errado, `a` é uma 2-tupla contra a 1-tupla esperada.
    #
    # O RÓTULO DA TELA VIRA `flavor` PELO DONO (`mesa_viva.NOME_DA_MASCARA`),
    # nunca por um mapa digitado aqui: o que está declarado é a EXPECTATIVA.
    {"pagina": PAGINA, "gesto": "mascara",  # (noqa-acento) chave do contrato
     "clique": {"uniq": "aa:bb:cc:00:00:01", "mascara": "Xbox 360"},
     "chama": [("chamar", ["gamepad.mask.set"],
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
     "gesto": "cadeado", "clique": {"evento": "change"},
     "chama": [("autoswitch_lock_set", [], {"locked": True})]},
]
