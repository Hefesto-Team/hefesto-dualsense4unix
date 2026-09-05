"""Seção 0 da aba Configurações — o exame da mesa, com resposta em uma linha.

O `scripts/doctor.sh` tem milhares de linhas de diagnóstico e é invisível para
quem não abre terminal, que é a maior parte de quem usa o produto. Esta seção
dá cara de gente ao que já existe: um selo com o veredito, o botão que refaz o
exame, os CARDS do que fazer, e as linhas do que foi conferido.

DUAS ZONAS, E O QUE MANDA VEM EM CIMA (25/08/2026)
----------------------------------------------------

Até esta data a seção publicava cinco palavras e mais nada: a cura de quatro
das cinco conferências existia, e chegava à tela SÓ dentro de um
`set_tooltip_text` (`_dica_do_item`, e não havia um segundo caminho). Quem não
passasse o mouse por cima da palavra certa nunca descobria o que fazer — a
`A-CASA-SABE-E-O-PRODUTO-NAO-FAZ` na forma mais barata de consertar.

Agora há duas zonas: em cima os cards do que fazer, embaixo a tira do que foi
conferido. Um card de ORDEM (`integrations/ordens_da_mesa.Ordem`) traz o
imperativo e as TRÊS linhas de porquê, cada uma com o selo de procedência; um
card de CURA traz o que fazer e o que se mediu, sem selo, porque uma cura de
conferência não tem medição por trás dizendo de onde vem o conselho.

**A terceira linha é sempre visível**, inclusive quando confessa que o ganho não
foi medido. É ela que impede raciocínio de se vestir de medição: uma ordem que
manda mover sem dizer quanto se ganha é honesta; a mesma com o ganho escondido é
palpite com cara de laudo.

Fonte única: a seção NÃO reimplementa checagem nenhuma. Toda medição vem de
`integrations/exame_da_mesa.py`, e o SELO vem de `exame_da_mesa.veredito()` —
nunca de uma conta feita aqui. Isso é regra, não estilo: a casa pagou duas
vezes em agosto (`6c86e295`, `c3d3518f`) por uma tela que mostrava verde em
cima de vermelho, e a cicatriz está escrita em `scripts/doctor.sh:1586-1590`.
Um segundo lugar decidindo a cor do topo é como aquilo volta.

O QUE MORA AQUI E NÃO LÁ: a cor, o glifo, e o texto que a pessoa lê. O módulo
devolve chave, estado e um porquê; a tradução para tela é desta camada, e é
por isso que nenhuma mensagem do doctor chega à janela — as de lá carregam
`sudo` e carregam endereço de rádio, e esta tela é fotografada e versionada
pelo `scripts/gui-captura/retratar_abas.py`.

QUANDO O EXAME RODA: ao ENTRAR na aba e no botão. Nunca na montagem, que
acontece no arranque da janela — é o caminho por onde o retrato das abas passa,
e um exame ali poria leitura viva de `/sys` e do rádio dentro de um PNG que
entra em `docs/usage/assets/` sem revisão humana.

O CARD RESPONDE (26/08/2026)
-----------------------------

Até esta data o card de ordem era só leitura: ela lia "mova o aparelho", ia lá,
movia — e não tinha como dizer isso ao produto. A seção tinha UM botão
("Examinar de novo") e o conselho dispensado nunca sumia. A lógica inteira já
estava escrita e medida em `integrations/ordens_da_mesa.py`
(`resposta_ao_ja_movi`, `ordens_novas`, `ordens_caladas`, `cabecalho`,
`identidades`) e não tinha um único chamador: era a
`A-CASA-SABE-E-O-PRODUTO-NAO-FAZ` na forma cara — cinco funções medidas e
nenhuma tela.

Agora cada card de ordem traz `[Já movi — reexaminar]` e `[Ignorar]`:

* **Já movi** refaz o exame e COMPARA o arranjo, respondendo uma das quatro
  frases de `FRASE_DA_RESPOSTA`. A resposta FICA na tela até o próximo exame —
  um card que simplesmente some é indistinguível de um card que nunca foi
  desenhado, e ela apertou um botão e precisa ver o que ele fez;
* **Ignorar** grava a dispensa no rascunho da máquina, chaveada pelo ARRANJO
  (`D-ORDEM-IGNORADA-VOLTA`). Ela mexeu nos cabos e a mesma regra disparou com
  arranjo novo? é fato novo, e a ordem VOLTA.

O TOPO, E QUEM DECIDE A COR (26/08/2026)
------------------------------------------

O selo passa a dizer o texto de `ordens_da_mesa.cabecalho()` — os quatro
cabeçalhos da §8.3 da ORDEM-DE-SERVIÇO-01, que curam a queixa dela de que
*"o 'está tudo certo' não fala nada"*: o estado bom passa a contar QUANTA coisa
foi conferida, e o "não soube" deixa de se disfarçar dele.

**A cor continua sendo de `exame_da_mesa.veredito()`, e por uma razão medida:**
`cabecalho()` não vê `ESTADO_PROBLEMA` — a assinatura dele conhece ordens e duas
contagens, e nada mais. Um selo pintado só por ele mostraria "Nada a mudar" em
VERDE com a linha de pareamentos em VERMELHO logo abaixo, que é a cicatriz de
`6c86e295` voltando pela porta dos fundos. Por isso o topo é o estado MAIS
GRAVE entre os dois, e quem for mais grave também é quem dá a frase. Escalar
nunca inventa um verde; só o apaga.

TERRITÓRIO DE CONFIG-09. Quem trabalha nesta seção escreve AQUI — o título, a
dica e todo widget dela. O montador da aba (`mixin.py`) só cria a moldura e
chama `montar`; ele não sabe o que há dentro, e é assim que cinco seções
crescem sem se pisarem.
"""
from __future__ import annotations

import contextlib
import time
from collections.abc import Mapping, Sequence
from dataclasses import replace
from datetime import date
from typing import Any

# `rotulo_de_apoio` saiu do import em 26/08/2026 junto com o parágrafo do
# `ESCOPO` (LEX-2, item 1): esta seção não imprime mais nenhum parágrafo de
# apoio na página.
from hefesto_dualsense4unix.app.actions.config.moldura import QUANDO_VALE
from hefesto_dualsense4unix.integrations.exame_da_mesa import (
    ESTADO_ATENCAO,
    ESTADO_CERTO,
    ESTADO_NAO_SEI,
    ESTADO_PROBLEMA,
    ROTULOS_DA_ORDEM,
    Item,
    veredito,
)
from hefesto_dualsense4unix.integrations.ordens_da_mesa import (
    CONFIRMEI,
    FRASE_DA_RESPOSTA,
    MOVEU_E_CONTINUA,
    NAO_CONSEGUI_CONFIRMAR,
    SEM_MUDANCA,
    TEXTO_DO_SELO,
    Identidade,
    Ordem,
    cabecalho,
    identidades,
    ordens_caladas,
    ordens_novas,
    resposta_ao_ja_movi,
)
from hefesto_dualsense4unix.utils.i18n import _
from hefesto_dualsense4unix.utils.logging_config import get_logger

logger = get_logger(__name__)

#: O título como ela o lê na tela.
TITULO = "Está tudo certo?"

#: A dica do título, palavra por palavra como saiu do desenho aprovado
#: (`TOOLTIPS.md`). Ela não se reescreve na hora.
#: E5 da leva: a janela passa a ter DUAS telas de saúde, e cada uma declara o
#: seu escopo. Sem esta linha, a pessoa tem de adivinhar por que há dois
#: diagnósticos e qual deles responde à pergunta dela.
#: A PALAVRA "mesa" SAIU DA TELA em 05/09/2026, ordem dela. A frase já dizia o
#: que "a mesa" era — os dois-pontos logo à frente listam portas, energia e
#: rádio —, então a palavra não carregava nada que a lista não carregue.
ESCOPO = (
    "Este exame olha o que está ligado: portas, energia e rádio. O estado do "
    "Hefesto e do som fica na aba Sistema."
)

#: **A `ESCOPO` foi ANEXADA aqui em 26/08/2026 (LEX-2, item 1).** Ela era um
#: parágrafo esmaecido no alto da seção, e dizia a mesma coisa com a mesa vazia
#: e com a mesa cheia — logo é explicação, e explicação vai para o hover pela
#: regra do léxico desta aba. Anexada, e não substituída: as duas metades
#: respondem perguntas diferentes ("o que este exame faz" e "onde está o
#: resto").
#:
#: DERIVADA da constante, nunca copiada: a frase digitada duas vezes divergiria
#: na primeira correção, e as duas versões viveriam lado a lado — que é o
#: defeito que a régua de fato errado desta casa existe para matar.
DICA: str | None = (
    "O mesmo exame que o Hefesto já sabe fazer pelo terminal, agora com "
    f"resposta em uma linha. Só lê — não muda nada na máquina. {ESCOPO}"
)

#: O nome do método que a seção pendura no hospedeiro, e que a costura da aba
#: liga em `_REFRESH_POR_ABA` (`app/app.py:925`) para o exame rodar ao ENTRAR na
#: aba. Constante, e não literal solto nos dois lados: uma string repetida em
#: dois arquivos é a forma clássica de um refresher nascer morto em silêncio
#: (BUG-GUI-EMULATION-HANDLERS-UNWIRED-01).
NOME_DO_REFRESH = "_refresh_saude_da_mesa"

#: A frase do selo, por estado. Ela responde à pergunta do título, e responde
#: em português de gente — as chaves de estado do módulo são vocabulário de
#: máquina, e nenhuma delas chega à tela.
FRASE_DO_SELO = {
    ESTADO_CERTO: "Pronto para jogar",
    ESTADO_ATENCAO: "Dá para jogar, mas vale um ajuste",
    ESTADO_PROBLEMA: "Há algo atrapalhando o jogo",
    ESTADO_NAO_SEI: "Não deu para conferir tudo",
}

#: O que o selo diz antes do primeiro exame. A montagem NÃO examina (ver o
#: cabeçalho), então este é o estado que o retrato das abas fotografa.
FRASE_ANTES_DO_EXAME = "Ainda não examinei"

#: E o que ele diz enquanto o worker trabalha.
FRASE_EXAMINANDO = "Examinando…"

#: O glifo de cada estado. E2 da leva: o sinal de conferido (U+2713) colorido,
#: FORMAS GEOMÉTRICAS, e não o sinal de conferido, e a razão é dupla.
#:
#: A primeira é de portão: o sanitizador global do ambiente dela recusa o bloco
#: U+2700 inteiro, e o CHECK MARK U+2713 mora lá. O `validar-glifos.py` deste
#: projeto o aceitaria — ele deriva a proibição de `Emoji_Presentation`, e o
#: U+2713 não está nela —, mas os dois portões precisam concordar, e o mais
#: estrito manda. O `docs/adr/011-glyphs-vs-emojis.md` já tinha respondido a
#: pergunta por escrito: Geometric Shapes (U+25A0 a U+25FF) são o vocabulário
#: permitido, e o BLACK CIRCLE é o exemplo canônico que a casa já usa nos
#: cabeçalhos Pango e no medidor de bateria da TUI.
#:
#: A segunda é de leitura: a FORMA muda junto com a cor. Quem não distingue
#: verde de laranja ainda vê círculo, triângulo e quadrado — o triângulo é o
#: sinal de alerta em qualquer lugar do mundo, e o quadrado para o olho. Um
#: check verde e um check laranja seriam o mesmo desenho duas vezes.
#:
#: O pedido dela era "ficando verde com um check". O verde ficou onde importa:
#: no selo do topo, que é o que responde em uma linha.
GLIFO = {
    ESTADO_CERTO: "●",
    ESTADO_ATENCAO: "▲",
    ESTADO_PROBLEMA: "■",
    ESTADO_NAO_SEI: "○",
}

#: O glifo de "ainda não olhei". Distinto do "?" de propósito: "não medi" e
#: "medi e não soube" são estados diferentes, e cinco interrogações na tela de
#: uma aba recém-aberta leriam como cinco falhas.
GLIFO_PENDENTE = "·"

#: A cor de cada estado, nos tokens da casa (`gui/theme.css:21-54`). LARANJA e
#: não amarelo para atenção: o `theme.css:13` fixa "VERDE confirma, LARANJA
#: alerta, VERMELHO destrói, CIANO informa", e o `daemon_actions.py:754` já
#: pinta `[WARN]` de `#ffb86c` NESTA MESMA JANELA. Duas cores para o mesmo
#: estado na mesma janela é dívida de tela.
COR = {
    ESTADO_CERTO: "#50fa7b",
    ESTADO_ATENCAO: "#ffb86c",
    ESTADO_PROBLEMA: "#ff5555",
    ESTADO_NAO_SEI: "#8b8fa8",
}

#: Cor do glifo pendente e do carimbo — o cinza de "item não selecionado".
COR_APAGADA = "#8b8fa8"

#: A dica de cada linha, por chave do exame. Palavra por palavra do desenho
#: aprovado (`TOOLTIPS.md:77-81`); não se reescreve na hora.
#:
#: Elas descrevem o que a linha PROMETE, não o que se mediu agora — e é por
#: isso que `_dica_do_item` cola a medição embaixo. Uma dica que afirma "todos
#: os controles têm pareamento salvo e válido" enquanto o exame achou o
#: contrário é a mesma mentira do selo verde sobre linha vermelha, em letra
#: menor.
DICAS_DAS_LINHAS = {
    "energia_do_radio": (
        "O sistema está proibido de desligar os adaptadores para poupar "
        "energia. Se desligar, o controle cai sozinho no meio do jogo."
    ),
    "energia_das_portas": (
        "Nenhuma porta está entregando menos corrente do que o aparelho pede."
    ),
    "pareamentos": (
        "Todos os controles têm pareamento salvo e válido. Pareamento pela "
        "metade faz o controle cair logo depois de conectar."
    ),
    "suporte_ao_controle": "O módulo que fala com o DualSense está carregado.",
    "vizinhanca_das_portas": (
        "Há um Wi-Fi USB 3.0 na porta ao lado de um adaptador Bluetooth. Ele "
        "emite ruído bem em cima da faixa dos controles. Vale mudar de porta."
    ),
}

#: O prefixo da cura, e ele tem UM dono. Nasceu dentro de `_dica_do_item` e
#: passou a valer também para o card, quando a cura deixou de morar só no
#: tooltip: duas cópias da mesma palavra divergiriam na primeira edição, e a
#: pessoa leria "O que fazer" na dica e outra coisa no card.
PREFIXO_DA_CURA = "O que fazer: "

#: A moldura de um card de ordem. A gramática visual é a mesma dos cards das
#: outras abas: um `Gtk.Frame` sem rótulo, com margem interna — uma aba nova sem
#: `Gtk.Frame` já leu como quebrada nesta casa (22/08/2026).
MARGEM_DO_CARD = 8

#: Rótulo e dica do botão (`TOOLTIPS.md:75`).
ROTULO_DO_BOTAO = "Examinar de novo"
DICA_DO_BOTAO = "Refaz o exame agora. Leva alguns segundos e não altera nada."

#: Os dois botões de um card de ordem, palavra por palavra como estão escritos
#: na `2026-08-24-ORDEM-DE-SERVICO-01`, §7 — não se reescrevem na hora.
ROTULO_JA_MOVI = "Já movi — reexaminar"
ROTULO_IGNORAR = "Ignorar"

#: O estado (logo, a cor e o glifo) de cada uma das quatro respostas ao
#: "Já movi". Os quatro saem da §7.2: verde só quando a regra parou de disparar;
#: laranja quando ela moveu e continua apertado; cinza nos dois casos em que o
#: produto não tem o que afirmar. A FRASE vem de `FRASE_DA_RESPOSTA`, no módulo
#: — aqui mora só a tradução para cor, que é o que esta camada decide.
ESTADO_DA_RESPOSTA = {
    CONFIRMEI: ESTADO_CERTO,
    MOVEU_E_CONTINUA: ESTADO_ATENCAO,
    SEM_MUDANCA: ESTADO_NAO_SEI,
    NAO_CONSEGUI_CONFIRMAR: ESTADO_NAO_SEI,
}

#: A escada de gravidade, do mais grave ao menos. É a MESMA de
#: `exame_da_mesa.veredito()` e existe aqui por uma razão só: comparar dois
#: estados que vieram de duas perguntas diferentes (o veredito das linhas e o
#: cabeçalho das ordens). Nenhum estado nasce daqui — só se escolhe entre dois
#: que já existem, e a escolha é sempre a do PIOR.
ESCADA_DE_GRAVIDADE = (
    ESTADO_PROBLEMA,
    ESTADO_ATENCAO,
    ESTADO_NAO_SEI,
    ESTADO_CERTO,
)

#: Colunas da grade de linhas. Duas, como no desenho — e sem homogeneidade:
#: coluna homogênea numa fileira de rótulo longo já custou 1004 dos 1066px da
#: largura mínima da janela, que abre com 1180 e não tem rolagem horizontal.
COLUNAS = 2


def _escapar(texto: str) -> str:
    """Escapa o que o Pango leria como marcação."""
    return texto.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def frase_de_quando(idade_s: float) -> str:
    """O carimbo "Há N minutos", a partir da idade do exame em segundos.

    Função pura e separada do widget para poder ser medida sem GTK. O
    arredondamento é grosso de propósito: o valor exato não muda decisão
    nenhuma, e "Há 3 minutos" é mais fácil de ler que "Há 187 segundos".
    """
    if idade_s < 45:
        return "Agora mesmo"
    if idade_s < 90:
        return "Há 1 minuto"
    if idade_s < 3600:
        return f"Há {int(idade_s // 60)} minutos"
    return "Há mais de uma hora"


def _dica_do_item(item: Item) -> str:
    """A dica aprovada, mais a medição desta rodada embaixo.

    As duas metades têm papéis distintos e nenhuma substitui a outra: a de cima
    diz o que a linha significa, a de baixo diz o que o exame achou agora. Sem
    a de baixo, a dica de "Pareamentos salvos" continuaria afirmando que está
    tudo salvo com a linha pintada de vermelho ao lado — é a
    LED-QUE-NÃO-AFIRMA-01 aplicada a uma dica.

    A CURA CONTINUA AQUI, E DEIXOU DE SER SÓ AQUI. Até 25/08/2026 este era o
    ÚNICO caminho de `Item.cura` até a tela, e quem não passasse o mouse por
    cima da palavra certa nunca descobria o que fazer. Agora ela também sai em
    card (:meth:`PainelDoExame._desenhar_o_que_fazer`); a dica a mantém porque
    quem já está com o ponteiro na linha não deve ter de procurar embaixo.
    """
    partes = [_(DICAS_DAS_LINHAS.get(item.chave, ""))]
    if item.porque:
        partes.append(_(item.porque))
    if item.cura:
        partes.append(_(PREFIXO_DA_CURA) + _(item.cura))
    return "\n\n".join(p for p in partes if p)


def _linha_da_ordem(rotulo: str, texto: str, selo: str) -> str:
    """Uma das três frases de uma ordem, com o selo de procedência à direita.

    O selo vai na MESMA linha e em cinza: ele qualifica a frase, e uma linha
    própria o transformaria numa quarta afirmação.

    A `fonte` da linha NÃO chega aqui, e a ausência é decisão de tela: no módulo
    ela é um caminho de arquivo desta árvore (`docs/protocol/…`), porque é isso
    que um portão consegue conferir em disco. Caminho de repositório na tela
    dela é jargão do mesmo tipo de `usb1-port5` — quem usa o produto não tem
    esta árvore. O que ela lê é "especificação de terceiro", que é a afirmação
    honesta; QUEM é o terceiro ainda não existe em forma de nome legível, e
    inventá-lo aqui seria a tela pondo palavra na boca do módulo.
    """
    return (
        f"<b>{_escapar(_(rotulo))}:</b> {_escapar(_(texto))} "
        f'<span foreground="{COR_APAGADA}" size="small">'
        f"[{_escapar(_(TEXTO_DO_SELO.get(selo, selo)))}]</span>"
    )


def _markup_da_resposta(resposta: str) -> str:
    """A frase do "Já movi", com o glifo e a cor do estado dela.

    A FRASE não é escrita aqui: ela vem de `ordens_da_mesa.FRASE_DA_RESPOSTA`,
    que é o dono único das quatro. O que esta camada decide é a cor — e ela é a
    mesma escada de sempre, para que "Confirmei" leia verde e os dois casos em
    que o produto não sabe leiam cinza, nunca verde.
    """
    estado = ESTADO_DA_RESPOSTA.get(resposta, ESTADO_NAO_SEI)
    frase = FRASE_DA_RESPOSTA.get(resposta, "")
    return (
        f'<span foreground="{COR[estado]}" weight="bold">'
        f"{_escapar(GLIFO[estado])}</span> {_escapar(_(frase))}"
    )


def o_mais_grave(primeiro: str, segundo: str) -> str:
    """O pior dos dois estados — e, no empate, o segundo.

    Existe porque DUAS perguntas respondem sobre o topo da seção e nenhuma das
    duas vê a outra: `exame_da_mesa.veredito()` lê as cinco linhas conferidas e
    conhece `ESTADO_PROBLEMA`; `ordens_da_mesa.cabecalho()` lê as ordens e as
    contagens e **não** conhece. Um selo pintado só pelo segundo diria "Nada a
    mudar" em verde com a linha de pareamentos em vermelho — a cicatriz de
    `6c86e295`, que a casa pagou duas vezes em agosto.

    Escalar não é uma segunda conta: nenhum estado nasce aqui, e o resultado é
    sempre um dos dois que entraram. O que ela não consegue fazer é inventar um
    verde, e é essa a propriedade que interessa.

    O empate devolve `segundo` de propósito: quem chama passa o cabeçalho ali, e
    é ele que tem a FRASE que conta quanta coisa foi conferida — a queixa dela
    de que *"o 'está tudo certo' não fala nada"*.
    """
    for estado in ESCADA_DE_GRAVIDADE:
        if segundo == estado:
            return segundo
        if primeiro == estado:
            return primeiro
    return segundo


def contagens_do_cabecalho(itens: Sequence[Item]) -> tuple[int, int]:
    """Quantas checagens responderam, e quantas rodaram sem saber.

    As duas contagens são de propósito diferentes, e `cabecalho()` as recebe
    separadas: *"conferi 5 coisas"* e *"5 coisas não deram resposta"* são
    afirmações opostas, e a tela que as colapsa é a tela que mente de verde.

    Só CONFERÊNCIA entra na conta. Um item com `ordem` é uma ordem de serviço, e
    ordem não é coisa conferida — ela já é contada pelo primeiro cabeçalho, e
    somá-la aqui faria o número da tela crescer com o problema em vez de com o
    exame. A linha `CHAVE_DAS_ORDENS`, ao contrário, ENTRA: ela é o catálogo
    confessando que não conseguiu olhar, e é exatamente o que `sem_resposta`
    existe para contar.
    """
    conferencias = [item for item in itens if item.ordem is None]
    sem_resposta = sum(
        1 for item in conferencias if item.estado == ESTADO_NAO_SEI
    )
    return len(conferencias) - sem_resposta, sem_resposta


def _leitura_das_ordens(maquina: Any) -> Any:
    """O que o catálogo de ordens lê — o barramento MAIS o desenho dela.

    O módulo do exame é 100% stdlib e não pode abrir o `maquina.json` (contrato
    de CONFIG-09, T3 da CONFIGURAÇÕES-FECHA-01): quem carrega a declaração é
    esta seção e passa por argumento. Aqui isso vale para cinco campos de uma
    vez, e cada um muda o que a ordem consegue AFIRMAR:

    * `vizinhas` e `ocupante_da_entrada` — sem o desenho dela, R2 cala. Calar é
      a resposta certa: rádio colado a rádio é uma afirmação sobre o METAL, e o
      `/sys` não sabe onde os buracos ficam no gabinete;
    * `entradas_livres_declaradas` — é o que troca "para uma entrada do próprio
      computador" por "para a entrada 4". Sem desenho, a ordem manda, e diz que
      só ela pode dizer para onde;
    * `nomes_declarados` — é o que autoriza a ordem a chamar o aparelho de
      5 Gbps pelo nome DELA. Sem isso ele é "um aparelho que você ainda não
      identificou", e nunca "Wi-Fi": ler o `product` para nomear é adivinhar por
      texto;
    * `tipos_declarados` — é o filtro que impede a webcam de cabo de ser acusada
      de irradiar 2,4 GHz, que foi o falso positivo que fez esta sprint existir.

    A varredura mora aqui e não na montagem: ela roda no worker do exame, que é
    o mesmo lugar onde as outras cinco leituras já rodam.
    """
    from hefesto_dualsense4unix.integrations import (
        censo_do_barramento,
        entradas_do_gabinete,
        mapa_das_portas,
        ordens_da_mesa,
    )

    censo = censo_do_barramento.ler_o_barramento()
    mapa = maquina.mapa
    radios = maquina.mesa.radios
    return ordens_da_mesa.Leitura(
        censo=censo,
        entradas=entradas_do_gabinete.listar_entradas(),
        vizinhas=mapa_das_portas.vizinhas_de_verdade(mapa, censo),
        ocupante_da_entrada={
            numero: (mapa_das_portas.caminho_de(mapa, numero) or "")
            for numero in mapa.portas
        },
        entradas_livres_declaradas=mapa_das_portas.portas_livres(mapa, censo),
        nomes_declarados={
            chave: radio.apelido
            for chave, radio in radios.items()
            if radio.apelido
        },
        tipos_declarados={
            chave: radio.tipo for chave, radio in radios.items() if radio.tipo
        },
    )


class PainelDoExame:
    """Os widgets da seção e o ciclo do exame — montar, examinar, aplicar.

    Uma classe, e não três métodos no mixin, por uma razão de território: cinco
    frentes escrevem esta aba ao mesmo tempo, e cada método a mais no mixin é
    uma colisão a mais. O que o hospedeiro ganha é UM atributo — o refresher,
    pendurado por `montar` — e é o que a costura da aba precisa.
    """

    def __init__(self, host: Any = None) -> None:
        self.host = host
        self.selo: Any = None
        self.quando: Any = None
        self.botao: Any = None
        self.botao_do_cabecalho: Any = None
        self.linhas: dict[str, Any] = {}
        self.cards: Any = None
        self._examinando = False
        #: Os itens da última rodada. Guardados porque "Ignorar" e "Ver"
        #: redesenham a zona SEM refazer o exame: apertar um botão dela não
        #: pode custar uma varredura do barramento inteiro.
        self._itens: list[Item] = []
        #: O selo que `veredito()` devolveu para esses itens.
        self._veredito: str = ESTADO_NAO_SEI
        #: `{chave da regra: arranjo dispensado}` — o disco com o rascunho por
        #: cima, mais o que ela dispensou nesta sessão.
        self._dispensadas: dict[str, str] = {}
        #: `{nome do kernel: Identidade}` da última leitura. É o que separa dois
        #: aparelhos de mesmo `vid:pid` pelo serial, e é o que impede o produto
        #: de dizer "Confirmei" quando não sabe qual dos dois ela moveu.
        self._identidades: dict[str, Identidade] = {}
        #: As ordens que estavam na tela quando ela apertou "Já movi", à espera
        #: do exame novo para comparar o arranjo.
        self._aguardando: dict[str, Ordem] = {}
        #: `{chave da regra: (resposta, a ordem de antes)}` — o que o "Já movi"
        #: respondeu, e que FICA na tela até o próximo exame.
        self._respostas: dict[str, tuple[str, Ordem]] = {}
        #: O `[Ver]` do cabeçalho está apertado? Só ele revela as caladas.
        self._mostrar_caladas = False

    # --- montagem -------------------------------------------------------

    def montar(self, caixa: Any) -> None:
        """Desenha o cabeçalho, o escopo e a grade das linhas. NÃO examina."""
        from gi.repository import Gtk

        fileira = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.selo = Gtk.Label()
        self.selo.set_xalign(0.0)
        self.selo.set_markup(
            self._markup_do_selo(GLIFO_PENDENTE, COR_APAGADA, _(FRASE_ANTES_DO_EXAME))
        )
        fileira.pack_start(self.selo, False, False, 0)

        # O `[Ver]` da §8.2 — e ele só existe quando há o que revelar. As
        # ordens que ela dispensou são a ÚNICA coisa desta seção que fica
        # escondida: a tira do que foi conferido está sempre embaixo, então
        # `[Ver o que conferi]` e `[Ver quais]` abririam o que já está aberto.
        # O rótulo vem de `Cabecalho.botao` e nunca é escrito aqui.
        self.botao_do_cabecalho = Gtk.Button()
        self.botao_do_cabecalho.set_no_show_all(True)
        self.botao_do_cabecalho.connect("clicked", self._ao_ver_as_caladas)
        fileira.pack_start(self.botao_do_cabecalho, False, False, 0)

        self.quando = Gtk.Label()
        self.quando.set_xalign(1.0)
        with contextlib.suppress(Exception):
            self.quando.get_style_context().add_class("dim-label")

        self.botao = Gtk.Button(label=_(ROTULO_DO_BOTAO))
        self.botao.set_tooltip_text(_(DICA_DO_BOTAO))
        # Ligado AQUI, e não no `_signal_handlers()` do `app.py`: o botão nasce
        # nesta função e morre com ela, então dono único é quem o criou. Um
        # handler declarado noutro arquivo para um widget criado aqui é como
        # botão nasce morto em silêncio nesta casa.
        self.botao.connect("clicked", self._ao_clicar)
        # A ordem do `pack_end` é da direita para a esquerda: o carimbo encosta
        # na borda e o botão fica à esquerda dele.
        fileira.pack_end(self.quando, False, False, 0)
        fileira.pack_end(self.botao, False, False, 0)
        caixa.pack_start(fileira, False, False, 0)

        # LEX-2, ITEM 1 — O PARÁGRAFO DO ESCOPO SAIU DA PÁGINA (26/08/2026).
        # `ESCOPO` era um `rotulo_de_apoio` aqui, e dizia a mesma coisa com a
        # mesa vazia e com a mesa cheia: é explicação, e foi anexada à `DICA`
        # do título "Está tudo certo?" (ver a constante lá em cima).
        #
        # A `QUANDO_VALE` que viajava de carona nele muda de casa em vez de
        # sumir: a seção deixou de ser só leitura em 26/08 (o `[Ignorar]` de um
        # card acumula no rascunho e espera o "Aplicar" do rodapé), e quem
        # clica sem ver nada acontecer conclui que não salvou.
        #
        # O SELO É A CASA CERTA, e a razão é de portão: o `[Ignorar]` nasce e
        # morre com o card, então numa mesa sem nenhuma ordem a frase ficaria
        # sem widget nenhum — e
        # `test_a_aba_diz_quando_a_escolha_fica_guardada.py` monta a seção com
        # hospedeiro VAZIO, exatamente esse caso. O selo é a única linha desta
        # seção que existe sempre, e é ela que a pessoa está lendo quando o
        # exame responde.
        with contextlib.suppress(Exception):
            self.selo.set_tooltip_text(_(QUANDO_VALE))

        # A ZONA DOS CARDS, e ela nasce VAZIA. A montagem não examina (ver o
        # cabeçalho), então não há ordem nenhuma para desenhar aqui — e uma
        # caixa vazia não ocupa altura, então a seção recém-montada continua
        # com a cara que o retrato das abas fotografa.
        #
        # Em CIMA da tira de propósito: o que MANDA vem antes do que foi
        # conferido. A tira responde "está tudo certo?"; o card responde "o que
        # eu faço?", e é a segunda pergunta que traz alguém a esta aba.
        self.cards = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        caixa.pack_start(self.cards, False, False, 0)

        grade = Gtk.Grid()
        grade.set_column_spacing(24)
        grade.set_row_spacing(4)
        for indice, (chave, rotulo) in enumerate(self._linhas_do_desenho()):
            etiqueta = Gtk.Label()
            etiqueta.set_xalign(0.0)
            etiqueta.set_line_wrap(True)
            etiqueta.set_max_width_chars(46)
            etiqueta.set_markup(
                f'<span foreground="{COR_APAGADA}">{GLIFO_PENDENTE}</span> '
                f"{_escapar(_(rotulo))}"
            )
            etiqueta.set_tooltip_text(_(DICAS_DAS_LINHAS.get(chave, "")))
            grade.attach(etiqueta, indice % COLUNAS, indice // COLUNAS, 1, 1)
            self.linhas[chave] = etiqueta
        caixa.pack_start(grade, False, False, 0)

    @staticmethod
    def _linhas_do_desenho() -> list[tuple[str, str]]:
        """As cinco linhas na ordem da tela, com os rótulos do módulo.

        Chamar `exame()` para descobrir os rótulos leria `/sys` na montagem, que
        é justamente o que a montagem não pode fazer. Os rótulos vêm das
        constantes do módulo, que é o mesmo lugar de onde o exame os tira.
        """
        from hefesto_dualsense4unix.integrations import exame_da_mesa

        return [
            ("energia_do_radio", exame_da_mesa.ROTULO_ENERGIA_DO_RADIO),
            ("energia_das_portas", exame_da_mesa.ROTULO_ENERGIA_DAS_PORTAS),
            ("pareamentos", exame_da_mesa.ROTULO_PAREAMENTOS),
            ("suporte_ao_controle", exame_da_mesa.ROTULO_SUPORTE_AO_CONTROLE),
            ("vizinhanca_das_portas", exame_da_mesa.ROTULO_VIZINHANCA),
        ]

    @staticmethod
    def _markup_do_selo(glifo: str, cor: str, frase: str) -> str:
        return (
            f'<span foreground="{cor}" weight="bold">{_escapar(glifo)}</span> '
            f"<b>{_escapar(frase)}</b>"
        )

    # --- os cards: onde a cura deixa de morar no tooltip ------------------

    @staticmethod
    def _etiqueta(markup: str, *, margem: int = 0) -> Any:
        """Um rótulo de card: quebra linha, alinhado à esquerda, com markup.

        `set_line_wrap` não é enfeite — a frase de uma ordem tem duas linhas de
        texto, e um rótulo sem quebra empurra a largura mínima da janela para
        além dos 1180 px com que ela abre.
        """
        from gi.repository import Gtk

        etiqueta = Gtk.Label()
        etiqueta.set_xalign(0.0)
        etiqueta.set_line_wrap(True)
        etiqueta.set_max_width_chars(70)
        etiqueta.set_margin_start(margem)
        etiqueta.set_markup(markup)
        return etiqueta

    def _card(self, filhos: list[Any]) -> Any:
        """A moldura de um card, com os rótulos já prontos dentro."""
        from gi.repository import Gtk

        corpo = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        for filho in filhos:
            corpo.pack_start(filho, False, False, 0)
        for lado in ("start", "end", "top", "bottom"):
            with contextlib.suppress(Exception):
                getattr(corpo, f"set_margin_{lado}")(MARGEM_DO_CARD)
        moldura = Gtk.Frame()
        moldura.add(corpo)
        return moldura

    def _card_da_ordem(
        self, ordem: Ordem, *, resposta: str = "", calada: bool = False
    ) -> Any:
        """O card de uma ordem de serviço: o imperativo e as TRÊS linhas.

        AS TRÊS, SEMPRE — inclusive a que confessa que o ganho não foi medido.
        Uma ordem que manda mover um aparelho sem dizer quanto se ganha é uma
        ordem honesta; a mesma ordem com o ganho escondido é um palpite com cara
        de laudo, e esconder a terceira linha custaria uma linha de tela e a
        confiança inteira.

        Uma ordem sem destino nasce sem imperativo, e o card respeita isso: um
        imperativo que manda mover para lugar nenhum é pior que silêncio. Nesse
        caso o glifo encabeça a primeira das três linhas, para o card não
        começar sem sinal.

        `resposta` é a chave devolvida por `resposta_ao_ja_movi` na rodada em
        que ela apertou o botão, e entra como uma QUARTA linha somada — nunca
        no lugar de uma das três. A ordem continua valendo: o que a resposta
        acrescenta é o que mudou desde que ela leu.

        `calada` é uma ordem que ela dispensou e que o `[Ver]` do cabeçalho
        revelou. Ela vem SEM os dois botões: "Já movi" e "Ignorar" são gestos
        sobre um conselho vivo, e um conselho que ela já mandou calar não tem
        o que confirmar nem o que dispensar de novo.
        """
        glifo = (
            f'<span foreground="{COR[ESTADO_ATENCAO]}" weight="bold">'
            f"{_escapar(GLIFO[ESTADO_ATENCAO])}</span> "
        )
        filhos: list[Any] = []
        recuo = 0
        if ordem.tem_acao:
            filhos.append(
                self._etiqueta(f"{glifo}<b>{_escapar(_(ordem.acao))}</b>")
            )
            glifo = ""
            recuo = 12
        for rotulo, linha in zip(ROTULOS_DA_ORDEM, ordem.linhas, strict=True):
            filhos.append(
                self._etiqueta(
                    glifo + _linha_da_ordem(rotulo, linha.texto, linha.selo),
                    margem=recuo,
                )
            )
            glifo = ""
            recuo = 12
        if resposta:
            filhos.append(self._etiqueta(_markup_da_resposta(resposta), margem=12))
        if not calada:
            filhos.append(self._botoes_da_ordem(ordem))
        return self._card(filhos)

    def _botoes_da_ordem(self, ordem: Ordem) -> Any:
        """A fileira `[Já movi — reexaminar] [Ignorar]` de um card.

        Os dois `connect` moram AQUI, e não no `_signal_handlers()` do
        `app.py`, pela mesma razão do botão do cabeçalho: o widget nasce nesta
        função e morre com ela a cada redesenho da zona: um handler declarado
        noutro arquivo para um widget que é destruído e recriado é como botão
        nasce morto em silêncio nesta casa.

        A ordem viaja como dado do `connect`, e é ela que o handler recebe:
        procurar a ordem pela chave na hora do clique faria o botão agir sobre a
        leitura de AGORA enquanto ela leu a de ANTES — e "antes contra agora" é
        precisamente o que o "Já movi" compara.
        """
        from gi.repository import Gtk

        fileira = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        fileira.set_margin_top(6)
        ja_movi = Gtk.Button(label=_(ROTULO_JA_MOVI))
        ja_movi.connect("clicked", self._ao_ja_movi, ordem)
        fileira.pack_start(ja_movi, False, False, 0)
        ignorar = Gtk.Button(label=_(ROTULO_IGNORAR))
        ignorar.set_tooltip_text(_(QUANDO_VALE))
        ignorar.connect("clicked", self._ao_ignorar, ordem)
        fileira.pack_start(ignorar, False, False, 0)
        return fileira

    def _card_da_resposta(self, resposta: str) -> Any:
        """O card que sobra quando a regra PAROU de disparar.

        Sem ele, "Confirmei" não teria onde aparecer: a ordem sumiu do exame, e
        um card que simplesmente some é indistinguível de um card que nunca foi
        desenhado. Ela apertou um botão, mudou o mundo, e o produto tem de
        dizer o que mudou — é o F7 aplicado ao próprio gesto dela.
        """
        return self._card([self._etiqueta(_markup_da_resposta(resposta))])

    def _card_da_cura(self, item: Item) -> Any:
        """O card de uma conferência que tem cura e não tem ordem.

        Quatro das cinco conferências escrevem uma cura, e até 25/08/2026 as
        quatro morriam dentro de um `set_tooltip_text`. Este card é o caminho
        que faltava — e ele é MENOR que o da ordem de propósito: uma cura de
        conferência não traz selo de procedência, porque não há medição por trás
        dela dizendo de onde vem o conselho. Pôr um selo aqui seria dar ao
        raciocínio a roupa da medição, que é o que o selo existe para impedir.
        """
        cor = COR.get(item.estado, COR_APAGADA)
        return self._card(
            [
                self._etiqueta(
                    f'<span foreground="{cor}" weight="bold">'
                    f"{_escapar(GLIFO.get(item.estado, '?'))}</span> "
                    f"<b>{_escapar(_(PREFIXO_DA_CURA) + _(item.cura or ''))}</b>"
                ),
                self._etiqueta(_escapar(_(item.porque)), margem=12),
            ]
        )

    def _desenhar_o_que_fazer(self, itens: list[Item]) -> None:
        """Refaz a zona de cards a partir dos itens desta rodada.

        Destrói e reconstrói em vez de atualizar no lugar: o número de cards
        muda a cada exame, e uma zona que só acrescenta acumularia a
        recomendação de dois exames atrás — o defeito de tela mais barato de
        cometer e o mais difícil de notar, porque ele parece uma tela cheia de
        informação.

        As ordens vêm antes das curas de conferência: uma ordem sabe de onde
        veio cada frase dela, e uma cura de conferência não. O que afirma mais
        vem primeiro.

        A DISPENSA DELA FILTRA AQUI, e por `ordens_novas` — nunca por uma
        comparação escrita nesta camada. A chave do dispensado é o ARRANJO
        (`D-ORDEM-IGNORADA-VOLTA`): a decisão dela vale para a mesa que ela viu,
        e uma regra que volta a disparar com arranjo novo é FATO NOVO. Filtrar
        pelo slug faria a decisão de ontem calar uma medição de hoje, que é o
        defeito que a decisão dela existe para impedir.
        """
        if self.cards is None:
            return
        with contextlib.suppress(Exception):
            for filho in self.cards.get_children():
                self.cards.remove(filho)
                filho.destroy()
        todas = [item.ordem for item in itens if item.ordem is not None]
        novas = ordens_novas(todas, self._dispensadas)
        chaves_novas = {ordem.chave for ordem in novas}
        desenhados: list[Any] = []
        for ordem in novas:
            respondida = self._respostas.get(ordem.chave)
            desenhados.append(
                self._card_da_ordem(
                    ordem, resposta="" if respondida is None else respondida[0]
                )
            )
        # A regra parou de disparar depois do "Já movi": não há card de ordem
        # para pendurar a resposta, e a resposta é justamente o que ela precisa
        # ver. Sem esta passagem, "Confirmei" morre com o card que sumiu.
        for chave, (resposta, _antes) in self._respostas.items():
            if chave not in chaves_novas:
                desenhados.append(self._card_da_resposta(resposta))
        for item in itens:
            if item.ordem is None and item.cura and item.estado != ESTADO_CERTO:
                desenhados.append(self._card_da_cura(item))
        if self._mostrar_caladas:
            for ordem in ordens_caladas(todas, self._dispensadas):
                desenhados.append(self._card_da_ordem(ordem, calada=True))
        with contextlib.suppress(Exception):
            for card in desenhados:
                self.cards.pack_start(card, False, False, 0)
            self.cards.show_all()

    def _escrever_o_cabecalho(self, itens: Sequence[Item]) -> None:
        """O selo do topo: a frase de `cabecalho()` e a cor do estado mais grave.

        Duas perguntas respondem sobre este selo e nenhuma vê a outra — está
        escrito no cabeçalho deste arquivo e em :func:`o_mais_grave`.

        O veredito que entra na conta é o dos itens que ela NÃO calou. Não é
        uma segunda fórmula: é a MESMA `exame_da_mesa.veredito()`, com a lista
        de que ela retirou o que dispensou. Sem isso, uma ordem dispensada
        seguraria o topo em laranja para sempre e o `[Ignorar]` não faria nada
        visível — que é a definição de botão morto.
        """
        if self.selo is None:
            return
        todas = [item.ordem for item in itens if item.ordem is not None]
        novas = ordens_novas(todas, self._dispensadas)
        caladas = ordens_caladas(todas, self._dispensadas)
        conferidas, sem_resposta = contagens_do_cabecalho(itens)
        topo = cabecalho(
            ordens=novas,
            conferidas=conferidas,
            sem_resposta=sem_resposta,
            dispensadas=len(caladas),
        )
        chaves_caladas = {ordem.chave for ordem in caladas}
        vivos = [
            item
            for item in itens
            if item.ordem is None or item.ordem.chave not in chaves_caladas
        ]
        estado = o_mais_grave(
            self._veredito if not caladas else veredito(vivos), topo.estado
        )
        frase = topo.texto if estado == topo.estado else FRASE_DO_SELO[estado]
        with contextlib.suppress(Exception):
            self.selo.set_markup(
                self._markup_do_selo(GLIFO[estado], COR[estado], _(frase))
            )
        self._mostrar_o_botao_do_cabecalho(topo.botao, bool(caladas))

    def _mostrar_o_botao_do_cabecalho(self, rotulo: str, ha_caladas: bool) -> None:
        """O `[Ver]` da §8.2 — e só ele, porque só ele revela algo.

        `Cabecalho.botao` traz também `[Ver o que conferi]` e `[Ver quais]`, e
        os dois abririam o que já está aberto: a tira do que foi conferido mora
        logo abaixo, sempre visível, com o glifo de cada estado. Um botão que
        não muda a tela ensina que os botões desta seção não fazem nada.
        """
        if self.botao_do_cabecalho is None:
            return
        with contextlib.suppress(Exception):
            if rotulo and ha_caladas:
                self.botao_do_cabecalho.set_label(_(rotulo))
                self.botao_do_cabecalho.show()
            else:
                self._mostrar_caladas = False
                self.botao_do_cabecalho.hide()

    def _redesenhar(self) -> None:
        """Refaz as duas zonas com os itens que já estão em mãos.

        NÃO reexamina. "Ignorar" e "Ver" mudam o que a tela mostra, não o que a
        máquina é: pagar uma varredura do barramento por clique dela seria
        cobrar segundos por um gesto que não mediu nada.
        """
        self._desenhar_o_que_fazer(list(self._itens))
        self._escrever_o_cabecalho(self._itens)

    # --- os dois botões do card ------------------------------------------

    def _com_ambiguidade_fina(self, ordem: Ordem) -> Ordem:
        """A ordem com a ambiguidade que só o SERIAL enxerga.

        `ordens_da_mesa._identidade_do_caminho` marca `ambigua` quando há dois
        aparelhos de mesmo `vid:pid` na mesa — e nesta casa os três adaptadores
        Bluetooth são `2357:0604`, então TODA ordem sobre eles nasceria ambígua
        e nenhuma jamais poderia dizer "Confirmei". Quem separa é o serial, e
        quem o lê (e o descarta na mesma função) é `identidades`.

        O serial não chega aqui: o que volta de `identidades` é a `Identidade`,
        que não tem campo para ele. É assim que ele não entra no PNG que o
        retrato das abas versiona.
        """
        fina = self._identidades.get(ordem.alvo.caminho)
        if fina is None:
            return ordem
        return replace(ordem, alvo=replace(ordem.alvo, ambigua=fina.ambigua))

    def _ao_ja_movi(self, _botao: Any, ordem: Ordem) -> None:
        """Guarda a ordem que ela leu e refaz o exame para comparar o arranjo.

        A ordem de ANTES tem de ser guardada antes do exame novo: é ela que
        `resposta_ao_ja_movi` compara com a de agora, e ela deixa de existir no
        instante em que o exame novo chega.
        """
        self._aguardando[ordem.chave] = ordem
        self.reexaminar()

    def _responder_ao_ja_movi(self, itens: Sequence[Item]) -> None:
        """Compara o antes e o depois de cada ordem que ela disse ter movido."""
        if not self._aguardando:
            return
        agora = {
            item.ordem.chave: item.ordem for item in itens if item.ordem is not None
        }
        for chave, antes in self._aguardando.items():
            depois = agora.get(chave)
            self._respostas[chave] = (
                resposta_ao_ja_movi(
                    self._com_ambiguidade_fina(antes),
                    None if depois is None else self._com_ambiguidade_fina(depois),
                ),
                antes,
            )
        self._aguardando = {}

    def _ao_ignorar(self, _botao: Any, ordem: Ordem) -> None:
        """Cala esta ordem NESTE arranjo, e grava a decisão no rascunho.

        A chave do dispensado é o ARRANJO, não a recomendação
        (`D-ORDEM-IGNORADA-VOLTA`): ela mexeu nos cabos, o conselho pode ter
        mudado, e um conselho dispensado sobre um arranjo que não existe mais
        não é o mesmo conselho.

        A tela obedece na hora e o disco espera o "Aplicar" do rodapé — mesmo
        contrato de `secao_mesa._ao_declarar` e de `secao_orcamento`: chamar
        `machine.declare` daqui criaria um segundo dono do gesto de gravar, que
        é a classe de defeito que a `ABAS-01` curou.
        """
        self._dispensadas[ordem.chave] = ordem.arranjo
        self._respostas.pop(ordem.chave, None)
        self._gravar_a_dispensa(ordem)
        self._redesenhar()

    def _gravar_a_dispensa(self, ordem: Ordem) -> None:
        """Acumula a dispensa em `host._maquina_pendente`, sob `mesa`.

        Fusão e não substituição: as cinco seções da aba escrevem no MESMO
        rascunho pelo mesmo gesto, e a última a clicar apagaria as outras
        quatro se cada uma trocasse o documento.

        `quando` é só a DATA. A hora não muda nenhuma decisão do produto e é um
        dado a mais sobre a rotina dela num arquivo que ela cola em relato de
        defeito — `OrdemDispensada._so_a_data` reprova qualquer outra forma.
        """
        from hefesto_dualsense4unix.utils.maquina import fundir_declaracao

        with contextlib.suppress(Exception):
            self.host._maquina_pendente = fundir_declaracao(
                getattr(self.host, "_maquina_pendente", None),
                {
                    "mesa": {
                        "ordens_dispensadas": {
                            ordem.chave: {
                                "quando": date.today().isoformat(),
                                "arranjo": ordem.arranjo,
                            }
                        }
                    }
                },
            )
        marcar = getattr(self.host, "_marcar_declaracao_por_aplicar", None)
        if marcar is not None:
            with contextlib.suppress(Exception):
                marcar()

    def _ao_ver_as_caladas(self, _botao: Any) -> None:
        """O `[Ver]`: mostra as ordens que a decisão dela está segurando.

        Dispensa que some sem deixar marca é a mesma classe de defeito do card
        que some: ela deixaria de saber que existe uma decisão dela ali.
        """
        self._mostrar_caladas = not self._mostrar_caladas
        self._redesenhar()

    # --- o exame --------------------------------------------------------

    def _ao_clicar(self, _botao: Any) -> None:
        self.reexaminar()

    def reexaminar(self) -> None:
        """Roda o exame num worker e devolve o resultado pela thread do GTK.

        Nunca na thread do GTK: BUG-GUI-SYSTEMCTL-SYNC-NA-THREAD-GTK-01
        (`daemon_actions.py:1817-1827`) — um `subprocess.run` síncrono com teto
        de 10 s congelou a janela inteira, e em D-state nem o kill chegava. O
        exame chama `busctl`, que é subprocesso.

        Reentrância barrada por um sinalizador: entrar na aba e clicar no botão
        no mesmo segundo enfileiraria dois exames no executor de UM worker, e o
        segundo só serviria para o carimbo pular duas vezes.

        AS RESPOSTAS DO "JÁ MOVI" SÃO LIMPAS AQUI, e é o que faz "fica na tela
        até ela sair da aba" ser verdade sem um relógio: o refresher da aba
        chama este mesmo método ao ENTRAR, então a frase sobrevive a tudo menos
        a um exame novo — que é exatamente quando ela deixa de ser notícia. As
        que este ciclo produzir são escritas depois, em :meth:`aplicar`.
        """
        if self._examinando:
            return
        self._examinando = True
        self._respostas = {}
        self._marcar_examinando()

        def _trabalho() -> None:
            # DIAGNÓSTICO-NAO-DERRUBA-A-ABA-01 (`daemon_actions.py:1194`): o que
            # se perde no pior caso é uma frase na tela; o que se protege é a
            # aba inteira, e com ela a janela.
            try:
                from gi.repository import GLib

                from hefesto_dualsense4unix.integrations import exame_da_mesa
                from hefesto_dualsense4unix.utils.maquina import carregar_maquina

                # T3, CONFIGURAÇÕES-FECHA-01: o exame é 100% stdlib e não lê o
                # `maquina.json` sozinho (contrato de CONFIG-09) — quem carrega
                # a declaração é esta seção, e passa por argumento.
                maquina = carregar_maquina()
                mesa = maquina.mesa
                # A leitura do catálogo é guardada de passagem, e continua
                # PREGUIÇOSA: `_itens_das_ordens` embrulha esta chamada num
                # `try`, e uma varredura feita aqui fora derrubaria o exame
                # inteiro por uma falha que hoje vira uma linha "não sei".
                guardado: dict[str, Any] = {}

                def _ler_as_ordens() -> Any:
                    guardado["leitura"] = _leitura_das_ordens(maquina)
                    return guardado["leitura"]

                itens = exame_da_mesa.exame(
                    altura_da_antena=mesa.altura_da_antena,
                    linha_de_visada=mesa.linha_de_visada,
                    leitura_das_ordens=_ler_as_ordens,
                )
                selo = exame_da_mesa.veredito(itens)
                quem: dict[str, Identidade] = {}
                leitura = guardado.get("leitura")
                if leitura is not None:
                    with contextlib.suppress(Exception):
                        quem = identidades(leitura.censo)
                dispensadas = {
                    chave: dispensa.arranjo
                    for chave, dispensa in mesa.ordens_dispensadas.items()
                }
                dispensadas.update(self._dispensas_do_rascunho())
            except Exception as exc:
                logger.warning("exame_da_mesa_falhou", erro=str(exc))
                self._examinando = False
                return
            GLib.idle_add(
                self.aplicar, itens, selo, time.time(), quem, dispensadas
            )

        try:
            from hefesto_dualsense4unix.app.ipc_bridge import _get_executor

            _get_executor().submit(_trabalho)
        except Exception as exc:  # pragma: no cover - sem executor não há janela
            logger.warning("exame_da_mesa_sem_worker", erro=str(exc))
            self._examinando = False

    def _dispensas_do_rascunho(self) -> dict[str, str]:
        """O que ela dispensou e ainda não aplicou — `{chave: arranjo}`.

        O rascunho é mais novo que o disco, e mostrar o disco faria o clique
        dela parecer perdido ao trocar de aba e voltar. É a mesma ordem de
        `secao_mesa._mesa_em_vigor` e de `secao_controles._declarado_hoje`.
        """
        pendente = getattr(self.host, "_maquina_pendente", None)
        if not isinstance(pendente, Mapping):
            return {}
        mesa = pendente.get("mesa")
        if not isinstance(mesa, Mapping):
            return {}
        dispensadas = mesa.get("ordens_dispensadas")
        if not isinstance(dispensadas, Mapping):
            return {}
        return {
            str(chave): str(valor.get("arranjo", ""))
            for chave, valor in dispensadas.items()
            if isinstance(valor, Mapping)
        }

    def _marcar_examinando(self) -> None:
        if self.selo is not None:
            with contextlib.suppress(Exception):
                self.selo.set_markup(
                    self._markup_do_selo(
                        GLIFO_PENDENTE, COR_APAGADA, _(FRASE_EXAMINANDO)
                    )
                )
        if self.botao is not None:
            with contextlib.suppress(Exception):
                self.botao.set_sensitive(False)

    def aplicar(
        self,
        itens: list[Item],
        selo: str,
        quando: float,
        quem: Mapping[str, Identidade] | None = None,
        dispensadas: Mapping[str, str] | None = None,
    ) -> bool:
        """Escreve o resultado nos widgets. Roda na thread do GTK.

        Devolve `False` porque é alvo de `GLib.idle_add`: um `True` faria o
        GTK repetir a chamada para sempre.

        `selo` chega pronto de `exame_da_mesa.veredito()` e NÃO é recalculado
        aqui — ver o cabeçalho deste arquivo.

        `quando` é o instante em que o worker terminou, não o instante em que o
        GTK chegou a atender o `idle_add`. A diferença é o que o carimbo mostra,
        e ela não é sempre zero: numa janela ocupada o `idle_add` espera.

        `quem` e `dispensadas` chegam do WORKER, e não são buscados aqui: as
        duas leituras são disco e `/sys`, e esta função roda na thread do GTK.
        `None` mantém o que a rodada anterior trouxe — é o que permite a esta
        função ser chamada com três argumentos por quem só quer pintar itens.
        """
        self._examinando = False
        if quem is not None:
            self._identidades = dict(quem)
        if dispensadas is not None:
            self._dispensadas = dict(dispensadas)
        self._itens = list(itens)
        self._veredito = selo
        self._responder_ao_ja_movi(itens)
        for item in itens:
            etiqueta = self.linhas.get(item.chave)
            if etiqueta is None:
                continue
            with contextlib.suppress(Exception):
                etiqueta.set_markup(
                    f'<span foreground="{COR.get(item.estado, COR_APAGADA)}">'
                    f"{_escapar(GLIFO.get(item.estado, '?'))}</span> "
                    f"{_escapar(_(item.rotulo))}"
                )
                etiqueta.set_tooltip_text(_dica_do_item(item))
        self._desenhar_o_que_fazer(list(itens))
        self._escrever_o_cabecalho(itens)
        if self.quando is not None:
            with contextlib.suppress(Exception):
                self.quando.set_markup(
                    f'<span foreground="{COR_APAGADA}">'
                    f"{_escapar(_(frase_de_quando(time.time() - quando)))}</span>"
                )
        if self.botao is not None:
            with contextlib.suppress(Exception):
                self.botao.set_sensitive(True)
        return False


def montar(host: Any, caixa: Any) -> None:
    """Monta a seção dentro de `caixa` — a caixa interna da moldura.

    `host` é o `HefestoApp`: dele vêm `_get` (widgets do Glade) e o que os
    outros mixins já penduraram. `caixa` é um `Gtk.Box` vertical, com as
    margens da casa já aplicadas.

    Ao fim, pendura em `host` o refresher `_refresh_saude_da_mesa`
    (`NOME_DO_REFRESH`), que é o que a costura da aba liga em
    `_REFRESH_POR_ABA` para o exame rodar ao ENTRAR na aba. Pendurar em vez de
    declarar no mixin é o que mantém esta seção dentro de um arquivo só; e se a
    montagem falhar, o atributo não existe e o `getattr(self, nome, None)` de
    `app/app.py:993` simplesmente não chama nada.

    Contrato, e ele vale para as cinco: **nunca levantar**. Uma seção que
    falha ao montar não pode derrubar a aba, e uma aba que falha não pode
    derrubar a janela. Quem chama já embrulha em `contextlib.suppress`, mas a
    tolerância começa aqui.
    """
    painel = PainelDoExame(host)
    painel.montar(caixa)
    host._painel_do_exame = painel
    setattr(host, NOME_DO_REFRESH, painel.reexaminar)
