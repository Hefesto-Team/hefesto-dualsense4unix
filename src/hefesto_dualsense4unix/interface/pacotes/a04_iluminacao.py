#!/usr/bin/env python3
"""O pacote da aba `04` Iluminação — a que MAIS tem dono das dez.

O QUE O DAEMON DEVOLVE, medido em 01/09/2026 com o DualSense dela no cabo:

    lightbar_rgb       [0, 0, 255]   a cor ACESA agora            ← tem dono
    lightbar_on        bool          a barra está acesa            ← tem dono
    lightbar_source    str           quem pediu a cor              ← tem dono
    lightbar_disputada bool          a Steam abriu o controle      ← tem dono
    player             1             o número, das cinco lâmpadas  ← tem dono
    leds.lightbar_brightness   o brilho, DO PERFIL          ← tem dono

O BRILHO ESTAVA MARCADO "SEM DONO" AQUI, E ERA MEU ERRO — corrigido em
01/09/2026, depois de ela perguntar: *"vc tá corrigindo na origem esses
problemas que tá relatando né?"*. O que estava escrito:

    "o DualSense não tem brilho de barra — o que a tela chama de brilho é a
     SATURAÇÃO da cor enviada (…) um 82% ali é a tela contando uma conta que
     ninguém faz do outro lado."

A frase sobre o APARELHO pode até se sustentar; a conclusão não. O
`profiles/schema.py` tem `LedsConfig.lightbar_brightness: float = 1.0`, com
faixa declarada (`ge=0.0, le=1.0`), e **os 33 perfis dela têm o campo
preenchido**. Havia dono, em disco, o tempo todo — eu perguntei só ao
`state_full` do daemon, que não publica isto, e li a ausência como inexistência.

A distinção que FICA, porque ela muda o que a tela diz: o brilho é o que está
**salvo no perfil**, e a cor é o que está **aceso agora** (o daemon publica
`lightbar_rgb`). Quando os dois discordam, quem manda na tela é o vivo.

E O `lightbar_rgb` É **PÓS-ESCALA DE BRILHO** — 03/09/2026, e é fato do
contrato do daemon, não interpretação. Estava escrito lá o tempo todo
(`ipc_handlers._enrich_controllers_per_controller`, "Contrato de cor (D8)")::

    expõe-se UMA cor, a efetiva conhecida (pós-escala de brilho — o
    `_DesiredOutput.led` já é pós-escala; o manager pré-escala na borda)

Esta aba o lia como PRÉ-escala, e a linha que estava aqui — *"é por isso que o
`hex` continua vindo do daemon"* — descrevia o defeito. Com o brilho abaixo de
100% a caixa mostrava uma cor que ela nunca pediu, a marca dos oito tons apagava
em todos e a tira escurecia duas vezes. Quem separa as duas escalas agora é
`cor_escolhida`; ver lá a medição e por que a inversão é uma varredura, não uma
divisão.

O PRODUTO ALCANÇOU A BANCADA no `players` e no `brilho`: a publicação de
02/09/2026 (`70b58116`) levou ao HTML publicado o `data-hef-alvo="largura"` do
trilho e o `data-campo="players"` do `.players`, e os quatro
`data-campo="player-N"` sumiram dos botões nos DOIS lados. A frase que estava
aqui — *"A BANCADA ANDOU E O PRODUTO NÃO"* — caducou no mesmo dia em que foi
escrita; medir vale mais que lembrar.

O QUE AINDA ESPERA A PUBLICAÇÃO é UM par, e é o do `.aceso`: a bancada diz
`data-campo="luz" data-hef-alvo="html"`, o publicado ainda diz
`data-campo="aceso"`. Ver `desenho_da_luz`.

`players` E `brilho-pct` NÃO SÃO ENDEREÇO MORTO — e a régua do mockup diz que
são. Medido em 02/09/2026, com dois controles na mesa e foto lida::

    p1·players     '1 2 3 4' ← ENDEREÇO MORTO      a fileira É pintada: o anel
                                                   do dono trocou do rosa do
                                                   mockup (cosmic-red) para o
                                                   plástico VIVO, na foto
    p2·brilho-pct  '100%'    ← ENDEREÇO MORTO      a largura É escrita; ela
                                                   coincide com o desenho

Nos DOIS o defeito é da régua, e é a mesma família que `_declarado_neste_elemento`
já documenta para os alvos `classe` e `cor`: entre o que o pacote EMITE e o que a
tela MOSTRA há uma tradução, e comparar os dois crus acusa endereço morto sobre o
produto que acertou. No alvo `largura` o `escrever()` faz `el.style.width = t +
'%'` e a régua compara o `100` declarado com o `'100%'` lido; no alvo `html` o
`LER_CAMPOS` cai no ramo padrão e lê `textContent`, então a fileira inteira é
comparada com `'1 2 3 4'`. **RELATADO** — a cura é em `interface/regua_do_mockup.py`
e `interface/hefesto_vivo.py`, fora do território deste arquivo. Emitir `"100%"`
daqui para "curar" o número poria `width:100%%` na tela.

DOIS ENDEREÇOS MORTOS MORRERAM AQUI — 02/09/2026, e o segundo não aparecia em
régua nenhuma::

    recado   emitido num `data-campo="recado"` que NENHUMA das duas páginas
             tem. A régua do mockup varre os endereços do ARQUIVO, e um campo
             emitido sem lugar nenhum não sai em arquivo algum; quem o via era
             o `casamento.py`, que o acusava como o único órfão da aba. A frase
             passou a viajar no `title` das três peças de `luz`, dentro da
             `dica_da_luz`.
    rgb      uma LISTA — e o pintor **pula lista em coluna**
             (`hefesto_vivo.py`, o laço das colunas: *"if(v !== null && typeof
             v === 'object') continue"*). Ele não podia ser pintado nem que a
             página tivesse onde. E o `casamento.py` também não o conta: ele
             filtra `if not isinstance(v, (dict, list))`. Dois instrumentos,
             ponto cego igual. O `hex` já leva a mesma cor na forma que a tela
             mostra.

A `lightbar_disputada` É O VALOR MAIS IMPORTANTE DESTA ABA, e é o que separa
esta tela de uma tela bonita: quando a Steam tem o controle aberto, a cor que o
daemon publica é a **pedida**, não a **acesa**. Pintar o hex sem dizer isso é
afirmar uma cor que pode não estar no plástico — e o produto já sabe a
diferença, é a tela que precisa contá-la.
"""
from __future__ import annotations

from typing import Any

from . import Contexto, perfil, registrar

#: Vazio, e o vazio é uma AFIRMAÇÃO: cada valor desta aba tem dono medido. A
#: régua reprova um pacote que pinta 0 e declara 0, de propósito.
SEM_DONO: dict[str, str] = {}


def _hex(rgb: Any) -> str:
    """`(0, 0, 255)` → `#0000FF`, e `—` quando não há cor.

    O travessão NÃO é enfeite: é a mesma marca de "não há valor" que os lugares
    vazios usam nas seis abas. Um `#000000` no lugar diria PRETO, que é uma cor.

    ELE SÓ FORMATA — 02/09/2026, e o guarda que estava aqui tinha dono. A linha
    era `if not rgb or len(rgb) < 3: return "—"`, que é o `_rgb3` do
    `app/widgets/controller_card.py`; o dono público dele é `cor_do_swatch`, e o
    docstring dele diz por que existe: *"Existe como função separada — em vez de
    um ``_rgb3`` repetido em cada chamador (…) com duas leituras do
    ``lightbar_rgb``, as duas abas divergiriam no primeiro caso de borda"*. A
    cópia daqui divergia em dois casos reais: uma lista de QUATRO canais passava
    (o dono recusa, porque está fora do contrato do IPC) e um canal fora de
    0..255 saía cru (o dono grampeia).
    """
    if not rgb:
        return "—"
    return "#{:02X}{:02X}{:02X}".format(*rgb)


#: Os quatro números que a página oferece, e o gerador desenha.
NUMEROS = (1, 2, 3, 4)

#: O ENDEREÇO DO ANELZINHO do dono, dentro de um botão da fileira.
#:
#: ELE NÃO É UM CAMPO QUE ALGUÉM PINTA, e é por isso que o nome tem ponto — a
#: gramática que a `10-perfis` já usa para um pedaço que mora DENTRO de um bloco
#: trocado inteiro (`perfis.linha.nome`). O que o `<i>` declara aqui é de quem
#: ele é: o pai é `data-campo="players" data-hef-alvo="html"`, e o produto
#: reescreve a fileira toda a cada tique, com `_cor_do_plastico` da mesa VIVA.
#:
#: SEM ELE A RÉGUA DA IDENTIDADE ACUSA O ANEL, e acusa com razão pela letra
#: dela: `--plastico:#hex` é julgado no elemento que o carrega, porque *"um pai
#: endereçado não dá ao filho o direito de trazer cor congelada"*. A exceção é
#: exatamente esta — o pai não "dá direito", ele REESCREVE o filho —, e um
#: endereço é a única forma de dizer isso no HTML.
#:
#: UM NOME PRÓPRIO, e nunca `players`: o pintor acha por
#: `[data-campo=X],[data-papel=X],[data-hef=X]` com `querySelectorAll`, então um
#: `<i>` que repetisse `players` receberia a fileira INTEIRA como `innerHTML`.
ANEL_DO_DONO = "players.dono"

#: O ENDEREÇO DO DESENHO DO CONTROLE, e o alvo que ele exige.
#:
#: A LEI DELA, 03/09/2026: *"os svgs do dualsense (…) mudam de acordo com o
#: controle identificado no canto superior. é white no p1, mas (…) os svgs não
#: são os que o meu mapa cataloga. isso tá errado"*.
#:
#: O QUE MUDA NO DESENHO É UM ATRIBUTO — `data-colorway` —, e é ele que escolhe,
#: na folha das cores, qual dos vinte e oito modelos pinta as dez zonas. O valor
#: que este pacote emite é o `colorway` do aparelho, que `mesa_viva.CORES` já
#: traduziu do código de fábrica lido pelo broker.
CAMPO_DO_DESENHO = "desenho"

#: O alvo que o `escrever()` do piloto precisa ter para este campo NÃO virar
#: desastre. Sem o ramo `atributo`, o pintor cai no padrão e faz
#: `el.textContent = "white"` — num `<svg>`, isso apaga o desenho inteiro e
#: deixa a palavra no lugar dele. É a regra da casa, escrita pela frente que
#: nasceu o alvo: *endereço com o alvo errado é pior que sem endereço*.
ALVO_DO_DESENHO = "atributo"

#: O que o desenho precisa dizer para receber o colorway. Os três andam juntos:
#: o endereço, o alvo, e o NOME do atributo a escrever.
_PEDE_O_DESENHO = (
    f'data-campo="{CAMPO_DO_DESENHO}"',
    f'data-hef-alvo="{ALVO_DO_DESENHO}"',
    'data-hef-atributo="data-colorway"',
)

_PINTA_O_DESENHO: bool | None = None


def a_pintura_alcanca_o_desenho() -> bool:
    """Dá para pintar o colorway do desenho HOJE, nesta árvore?

    DUAS PERGUNTAS, e as duas têm de responder sim — porque o desenho e o pacote
    chegam ao produto em tempos diferentes (é a régua
    `test_o_pacote_cabe_na_pagina_publicada`, e as três frentes devolvidas que a
    fizeram nascer):

    1. **a página PUBLICADA tem onde pôr?** Enquanto ela não mandar publicar a
       04, o produto renderiza o desenho de ontem, sem o endereço — e o valor
       seria órfão. É o mesmo `_so_se_a_pagina_tiver` da `a02_controles`, e
       `publicado=True` é deliberado: o piloto abre SEMPRE o publicado.
    2. **o PINTOR sabe escrever atributo?** O alvo `atributo` nasceu numa frente
       irmã. Sem ele, `escrever()` cai no ramo padrão e escreve o colorway como
       TEXTO dentro do `<svg>` — o desenho do controle some da tela dela e vira
       a palavra `white`. Esta metade FALHA FECHADA de propósito: qualquer coisa
       que ela não reconheça no fonte do piloto vira "não emita".

    LER O FONTE DO PILOTO É O CAMINHO CURTO, e é o mesmo que a régua da 05 já
    faz (`test_todo_alvo_que_a_pagina_pede_o_pintor_sabe_escrever`). Importá-lo
    traria GTK e WebKit para dentro de um pacote que roda a cada tique.
    """
    global _PINTA_O_DESENHO
    if _PINTA_O_DESENHO is None:
        from hefesto_dualsense4unix.interface import onde

        try:
            pagina = onde.pagina(PAGINA, publicado=True).read_text(encoding="utf-8")
        except OSError:
            pagina = ""
        try:
            piloto = (onde.AQUI / "hefesto_vivo.py").read_text(encoding="utf-8")
        except OSError:
            piloto = ""
        _PINTA_O_DESENHO = (all(p in pagina for p in _PEDE_O_DESENHO)
                            and f"alvo === '{ALVO_DO_DESENHO}'" in piloto)
    return _PINTA_O_DESENHO


def colorway_do_aparelho(casa: dict[str, Any]) -> str:
    """O `colorway` daquele controle, ou `""` quando ninguém o leu.

    O `""` É METADE DA REGRA, e é dela: *campo sem informação não mostra nada*.
    O alvo `atributo` APAGA o `data-colorway` num valor vazio, e o desenho cai
    nos `fill` crus do `ds_limpo.svg` — um DualSense sem identidade, que é o
    honesto quando o mapa de canais responde que a cor não se lê naquele
    transporte. Deixar o atributo faria o contrário: manteria o colorway do
    MOCKUP na tela sobre um aparelho que é outro, que é o defeito que esta
    entrega existe para matar.

    NÃO HÁ TABELA NOVA AQUI. `mesa_viva.CORES` já traduziu o código de fábrica
    do broker para o slug do desenho, e a mesa o carrega em `cor`.
    """
    return str(casa.get("cor") or "")
#: O ANEL DO "NÃO SEI" — a decisão 9 dela aplicada ao vizinho de cima.
#:
#: O DEFEITO, provado em 03/09/2026 com a própria função::
#:
#:     LIVRE   : <button … title="Player 3 — livre.">3</button>
#:     SEM COR : <button … title="Dar o Player 3 ao White: o Galactic Purple…">3</button>
#:     iguais SEM o title? True
#:
#: *"o Player 3 está LIVRE"* e *"o Player 3 é de um controle cuja cor eu ainda
#: não sei"* saíam byte a byte iguais na tela, e a ressalva viajava só no
#: `title` — quem não passa o mouse não vê, e quem navega pelo controle nunca
#: passa. É a MESMA forma da tira da luz (ver `ACESA/APAGADA/INCERTA`), uma
#: linha acima na mesma aba, e a cura é o MESMO idioma dela: *"tracejado para
#: 'não sei'"*, contorno e nunca cor nova.
#:
#: QUANDO ACONTECE DE VERDADE, e não é raro: a cor do plástico chega pelo broker
#: em thread, então o **primeiro tique de toda sessão** tem a mesa sem cor; e um
#: colorway que o SVG não conhece cai no `except` de `_cor_do_plastico` e fica
#: sem cor **para sempre**.
#:
#: O ESTILO É DE LINHA, e isso é o PISO — não decoração. A folha publicada diz
#: `.players .dono{…border:2px solid var(--plastico)}`; sem `--plastico` a
#: declaração inteira fica inválida no tempo de computar e o `border-style` cai
#: para `none` — o anel some outra vez, agora com a classe posta. Escrito na
#: linha, ele vale também na página que ela ainda não mandou publicar. É a mesma
#: lição que `TIRA_APAGADA` pagou na foto.
ANEL_INCERTO = "border:2px dashed var(--comment)"


def _tinta(rgb: Any) -> str:
    """A cor da tira NO TOM DESTA JANELA — ou `""`, que quer dizer APAGADA.

    DUAS ESCALAS DA MESMA COR, e a distinção é dela: *"a cor selecionada (…)
    precisa refletir no lightbar."* O `#0000FF` é o que vai ao plástico; o
    `#7EB8D4` é o azul que esta janela desenha, porque a paleta da casa não tem
    azul puro. `monta.tom_da_casa` é o dono da tradução, e é o MESMO que o
    gerador usa para pintar a guia de oito botões — pintar a tira com o hex CRU
    punha na tela uma cor que a guia não mostra em lugar nenhum.

    O `""` NÃO É "sem estilo": ele manda `desenho_da_luz` desenhar a tira
    APAGADA, com estilo explícito. Ver lá o que a ausência custou.
    """
    if not rgb:
        return ""
    import monta  # o `pacotes/__init__` põe `interface/` no `sys.path`

    return str(monta.tom_da_casa(_hex(rgb)))


def brilho_do_controle(p: dict[str, Any] | None, uniq: str) -> float | None:
    """O brilho da barra DAQUELE controle: o override, ou o do perfil.

    UM DONO, TRÊS CHAMADORES — e é por isso que ele saiu de dentro do `pacote()`
    em 03/09/2026. A conta estava escrita lá e em lugar nenhum mais, porque só a
    PINTURA a fazia; os gestos que ESCREVEM a cor não passavam brilho nenhum, e
    era exatamente esse o defeito (ver `_escrever_a_cor`). Curá-lo com uma
    segunda leitura do mesmo par de campos criaria a divergência clássica: a
    coluna mostrando um número e o fio levando outro, por dois códigos.

    A ORDEM É A DO MERGE, e ela tem dono: `ControllerOverrides.leds` vence o
    `LedsConfig` global — o mesmo que `profiles/schema.py` declara e que o
    backend resolve. Aqui só se lê o que o disco diz; quem resolve as cinco
    camadas é o daemon.

    `None` QUER DIZER "NÃO SEI", e não 1.0. A tela mostra `—` nesse caso, e o
    `led.set` recebe `brightness=None`, que o `_payload_led_set` OMITE do
    payload — o daemon então assume 1.0, que é o retrocompatível. Mandar `1.0`
    daqui diria "ela escolheu cheio" onde ninguém escolheu nada.
    """
    if not isinstance(p, dict):
        return None
    leds = p.get("leds")
    global_ = leds.get("lightbar_brightness") if isinstance(leds, dict) else None
    meu = (p.get("controllers") or {}).get(uniq)
    seus = (meu.get("leds") or {}) if isinstance(meu, dict) else {}
    b = seus.get("lightbar_brightness", global_) if isinstance(seus, dict) else global_
    if b is None:
        return None
    try:
        return max(0.0, min(1.0, float(b)))
    except (TypeError, ValueError):
        return None


def _com_o_brilho(rgb: tuple[int, int, int], brilho: float) -> tuple[int, int, int]:
    """`rgb` escalado pelo brilho — **pela função do produto**, nunca por conta.

    `core/led_control.LedSettings.apply_brightness` é o dono, e a conta dele é
    `max(0, min(255, int(c * level)))` por canal. Ela aparece em DOIS lugares do
    produto com o mesmo corpo — o `_handle_led_set` do daemon
    (`ipc_handlers.py`) e o provider da cor automática (D11) —, e é justamente
    por ser a mesma que a varredura de `cor_escolhida` pode ser exata. Digitar a
    multiplicação aqui seria a terceira cópia, e a que envelheceria calada no dia
    em que o produto ganhasse a curva de resposta não-linear que o docstring do
    dono já prevê.
    """
    from hefesto_dualsense4unix.core.led_control import LedSettings

    return LedSettings(lightbar=rgb).apply_brightness(brilho).lightbar


def tons_da_guia() -> tuple[tuple[int, int, int], ...]:
    """Os OITO tons que a guia desta aba oferece, na ordem em que o desenho os põe.

    NÃO SE DIGITA NENHUM: são `core/led_control.player_slot_color(1..8)`, a mesma
    paleta que acende as cinco lâmpadas, que o gerador usa para pintar os oito
    botões (`aba04.luz`) e que o daemon usa como cor automática de cada número.
    """
    from hefesto_dualsense4unix.core.led_control import player_slot_color

    return tuple(player_slot_color(n) for n in range(1, 9))


def cor_escolhida(efetiva: Any, brilho: float | None) -> Any:
    """A cor que ela PEDIU, a partir da que está ACESA e do brilho.

    O DEFEITO QUE ESTA FUNÇÃO MATA, e ele é do daemon para cima — está escrito
    no contrato dele (`ipc_handlers._enrich_controllers_per_controller`, o
    "Contrato de cor (D8)")::

        expõe-se UMA cor, a efetiva conhecida (PÓS-ESCALA DE BRILHO — o
        `_DesiredOutput.led` já é pós-escala; o manager pré-escala na borda)

    Esta aba lia esse `lightbar_rgb` como se fosse a cor ESCOLHIDA, e com o
    brilho abaixo de 100% isso quebra TRÊS coisas na mesma coluna, todas pela
    mesma raiz — medido em 03/09/2026 com `brilho=0.5` e o azul do P1::

        a caixa `#RRGGBB`   dizia `#00007F`, uma cor que ela nunca pediu
        a marca dos 8 tons  APAGAVA em todos — `data-hef-quando` compara com
                            `#0000FF`, e nenhum dos oito casa com `#00007F`
        a tira              pintava o hex CRU (o `tom_da_casa` só conhece os
                            oito CHEIOS) e ainda aplicava `opacity:0.5` por
                            cima — o brilho escurecendo DUAS vezes

    A CURA É A INVERSÃO PELA FÓRMULA DO PRODUTO, e não uma divisão: dividir
    `127/0.5` dá 254, e a marca continuaria apagada por um. O que se faz é
    aplicar a conta do dono (`_com_o_brilho`) nos OITO tons e ver qual produz a
    cor que está acesa — o mesmo desenho de `lightbar_actions.nome_do_desenho`,
    que varre os oito padrões canônicos para batizar um bitmask.

    SEM CASAMENTO, A EFETIVA VOLTA INTEIRA. É o caso da cor livre do seletor —
    `#12AB34` a 82% acende `#0E8C2A`, e não há como saber de qual pedido ele
    veio. Aí a tela mostra o que está no plástico, que é o honesto; inventar um
    pedido seria afirmar uma escolha que ninguém fez.

    :param efetiva: o `lightbar_rgb` do daemon, ou `None`/vazio quando não há.
    :param brilho: `brilho_do_controle`. `None` ou `1.0` devolvem a efetiva sem
        varrer nada — a 100% as duas escalas são a mesma, e varrer só gastaria.
    """
    if not efetiva:
        return efetiva
    if brilho is None or brilho >= 1.0:
        return efetiva
    alvo = tuple(efetiva)[:3]
    for tom in tons_da_guia():
        if _com_o_brilho(tom, brilho) == alvo:
            return tom
    return efetiva


#: A TIRA APAGADA — e ela é um ESTILO EXPLÍCITO, nunca a ausência de um.
#:
#: O DEFEITO QUE ESTA CONSTANTE MATA, medido em Chrome headless dentro da página
#: publicada, em 02/09/2026::
#:
#:     com `background:;color:;opacity:1.0`   box-shadow rgb(248,248,242) · opacity 1
#:     a tira ACESA do P1, no mesmo arquivo    box-shadow rgb(126,184,212) · opacity 0.82
#:
#: O halo da tira é `currentColor` (`.tira-luz.esq{box-shadow:-3px 0 12px 1px
#: currentColor}`), e um `color:` VAZIO não desliga a cor: ele deixa o valor
#: HERDADO valer — que nesta página é o `--fg`, `#f8f8f2`. A barra que o produto
#: diz estar APAGADA acendia BRANCA, e mais forte que a acesa a 82%. Fotografado
#: nas duas formas antes da cura.
#:
#: POR QUE `--panel` E NÃO UM HEX: é a variável de `:root` que o próprio desenho
#: usa para o touchpad (`.pad{background:var(--panel)}`) — a gramática desta
#: casa para *hardware que não está aceso*, do lado das cinco lâmpadas, que já
#: têm o seu `--led-apagado`. Ela existe no HTML publicado de hoje, e mesmo que
#: um dia falte, `background` não é herdado: a tira ficaria invisível, nunca
#: branca. O `color:transparent` é literal de propósito — é ele que mata o halo,
#: e ele não pode depender de variável nenhuma.
TIRA_APAGADA = "background:var(--panel);color:transparent;opacity:1"

#: OS TRÊS ESTADOS DA TIRA — decisão 9 dela, 03/09/2026:
#:
#:     "Tira da luz: tracejado para 'não sei'; lisa e vazia para 'apagada'."
#:
#: O DEFEITO QUE ELA VIU, e ele estava na tela: `"a barra está APAGADA"` e
#: `"não sei se está acesa"` pintavam a MESMA tira, byte por byte — as duas
#: caíam no `TIRA_APAGADA`, porque a única pergunta que esta função fazia era
#: *"há tinta?"*, e nos dois casos não há. A ressalva que separa os dois viajava
#: só no `title`: quem não passa o mouse não vê.
#:
#: SÃO TRÊS COISAS DIFERENTES, e o motor já as separava:
#:
#:     acesa     a barra está acesa e a cor é conhecida     tira na cor, com halo
#:     apagada   fonte NOSSA, e ela está desligada          tira lisa e vazia
#:     incerta   Nativo · Steam segurando · cor desconhecida  tira TRACEJADA
#:
#: O tracejado é CONTORNO, não cor — de propósito. Nesta aba tudo o que é CHEIO
#: de cor é LUZ (as tiras, as lâmpadas, os oito tons da guia); uma cor nova para
#: "não sei" seria lida como uma luz que ninguém mediu.
ACESA, APAGADA, INCERTA = "acesa", "apagada", "incerta"

#: O ENDEREÇO DO ESTADO DESCONHECIDO, e ele é `classe` porque o que muda na tela
#: é uma CLASSE, não uma palavra. Sem ele o tracejado viajaria só dentro do bloco
#: `luz` (alvo `html`), e régua nenhuma o veria: os alvos `html` e `fundo` são
#: lidos pelo TEXTO visível, e um desenho não tem texto.
ENDERECO_DA_INCERTA = "luz-incerta"

#: A CLASSE QUE DESENHA O TRACEJADO. A folha desta aba é dona do traço
#: (`aba04.CSS`, `.tira-luz.incerta`); aqui mora só o nome, para que o gerador e
#: o pintor não o escrevam em dois lugares.
CLASSE_DA_INCERTA = "incerta"


def estado_da_tira(recado: str | None) -> str:
    """Qual dos três estados a tira desenha — **perguntado ao motor**.

    O DISCRIMINADOR É O PRIMEIRO RETORNO de
    `app/widgets/controller_card.rotulo_lightbar`, e não o segundo: a docstring
    dele diz que a cor devolvida é *"a BASE do accent"*, e ela vem PREENCHIDA
    nos dois ramos em que o próprio motor avisa que a cor pode não estar no
    plástico (Nativo e Steam). Ler a base como "há luz?" colapsa dois estados —
    é o mesmo defeito que a `a02_controles` mediu com sonda em 02/09/2026.

    ONDE CAI CADA UM DOS CINCO RAMOS do motor (`controller_card.py:1181-1191`)::

        (None, rgb)                        cor conhecida e acesa      → acesa
        "Lightbar: apagada"                fonte NOSSA, desligada     → apagada
        "Em Nativo o jogo é dono do LED"   o jogo escreve por hidraw  → incerta
        "A Steam tem este controle aberto" quem segura o `fd`         → incerta
        "Lightbar: cor desconhecida"       sem fonte, ou sem rgb      → incerta

    A FRASE DA APAGADA NÃO SE DIGITA — ela se PERGUNTA. Das quatro que
    `rotulo_lightbar` devolve só uma é constante exportada
    (`ROTULO_LIGHTBAR_SEGURADA`), e `a02_controles.ROTULO_DA_LUZ_APAGADA` já
    resolveu isto para a aba irmã: perguntar ao motor com a entrada mínima que
    só o ramo "apagada" atende. **Reusar é o contrário de copiar** — uma segunda
    derivação aqui envelheceria calada no dia em que o motor trocasse a frase, e
    esta aba voltaria a colapsar "apagada" com "não sei" sem régua reprovar.
    """
    from .a02_controles import ROTULO_DA_LUZ_APAGADA

    if recado is None:
        return ACESA
    return APAGADA if recado == ROTULO_DA_LUZ_APAGADA else INCERTA


def o_coop_manda(state: dict[str, Any]) -> bool:
    """O co-op está DE FATO numerando mais de um controle?

    NÃO se lê `coop.enabled`, e a razão está MEDIDA no motor:
    `app/actions/status_actions.texto_do_coop_derrubado` diz, com todas as
    letras, que *"``CoopManager.disable()`` não zera ``coop_enabled``, então o
    ``state_full`` segue publicando ``coop.enabled=True`` com ``coop.players=1``
    — de fora, indistinguível de 'ela desligou o co-op'"*. Medido na mesa de
    02/09/2026, com o co-op parado e dois controles ligados::

        "coop": {"enabled": true, "players": 1, "mesa": [ … uma entrada … ]}

    Quem manda nas cinco lâmpadas é a CAMADA de co-op do merge
    (`core/backend_pydualsense._merged_desired_for_key`, a segunda de cinco), e
    ela só tem opinião quando há mais de um jogador. Ler o booleano faria a dica
    desta aba dizer *"quem manda é o co-op"* numa mesa em que ninguém está
    jogando em co-op.
    """
    coop = state.get("coop")
    if not isinstance(coop, dict):
        return False
    try:
        return int(coop.get("players") or 0) > 1
    except (TypeError, ValueError):
        return False


def dica_da_luz(nome: str, via: str, recado: str,
                coop_manda: bool = False) -> str:
    """A dica da célula LEDs: o controle VIVO, e só o que este pacote MEDE.

    DUAS DECISÕES DELA, de 02/09/2026, e esta função é as duas::

        7. "a palavra ACESO sai do texto"
        8. "a interface mostra o que tá conectado e não o controle do mockup"

    O que estava cravado no desenho — e portanto na tela dela — era::

        title="O Cosmic Red aceso: as duas tiras na cor escolhida, e as cinco
               lâmpadas no padrão do Player 1."

    Duas afirmações, as duas erradas ao mesmo tempo. **O nome** era o do mockup:
    com o controle de hoje na mesa, a MESMA coluna escreve `P1 • White • USB`
    no rótulo e `Cosmic Red` na dica, dez pixels abaixo. **E a palavra `aceso`**
    afirma um estado do aparelho que ninguém pode conferir: ela já tinha mandado
    tirá-la, a GTK obedeceu em 25/08 (`lightbar_actions._PREFIXO_DESENHO`
    passou a dizer *"Desenho que mandamos"*) e o mockup a reintroduziu.

    A FRASE DO DESENHO DAS 5 LUZES SAIU JUNTO — 02/09/2026, e é o mesmo defeito
    uma camada adiante. Ela dizia *"Desenho que mandamos: desenho do PN —
    automático, do número deste controle"*, e isso é uma afirmação sobre o MERGE
    do backend (`core/backend_pydualsense._merged_desired_for_key`)::

        default global do perfil  <  camada AUTOMÁTICA  <  override por-uniq
                                                        <  co-op  <  jogo

    **Este pacote não vê o override por-uniq.** O `state_full` publica, por
    controle, exatamente as chaves de
    `daemon/ipc_handlers._enrich_controllers_per_controller` — `lightbar_rgb`,
    `lightbar_on`, `lightbar_source`, `player_slot`, `inputs`… — e nenhum campo
    do desejado; `interface/aba02.py:809` já dizia isso com todas as letras
    (*"publica o ``player_slot`` e NÃO publica ``player_leds``"*). E o override
    é justamente onde a janela GTK escreve quando ela aplica um desenho:
    `lightbar_actions._enviar_player_leds` manda `player_leds_set_detalhado(…,
    uniq=…)` → `ipc_handlers._apply_por_uniq` → `apply_output_for`, *"que
    registra o override por-uniq"*.

    REPRODUZIDO em 02/09/2026, com o merge REAL do backend e nenhum aparelho
    (o dublê é o de `test_troca_de_player_01_a_escolha_sobrepoe.py`)::

        override por-uniq   o produto MANDA          a tela DIZIA
        nenhum              [F,T,F,T,F] (o do P2)    desenho do P2 — automático
        [T,F,F,F,T]         [T,F,F,F,T]              desenho do P2 — automático

    A segunda linha é a tela afirmando o contrário do que sai no fio. Vale a
    regra dela: *"se não tá mostrando agora, não tem info pra mostrar no
    produto"* — campo sem informação **não mostra nada**.

    O QUE SOBRA É O QUE SE MEDE, e as duas frases continuam tendo dono no motor:

    * a da BARRA é o primeiro retorno de `controller_card.rotulo_lightbar` — a
      mesma que os cards da GTK usam, e que sabe os quatro estados em que a cor
      publicada **não** é a que está no plástico. `""` quando não há ressalva;
    * a do CO-OP é `lightbar_actions.texto_do_desenho_aceso` no ramo 1, e essa
      camada o pacote VÊ: `o_coop_manda` a lê de `coop.players`, e ela está
      acima do override no merge — ligado o co-op, é ele que numera, tenha ela
      escolhido desenho ou não. Os dois primeiros argumentos vão nos sentinelas
      de "não sei" (`(False,) * 5` e `None`) porque o ramo devolve ANTES de
      olhar qualquer um dos dois; há teste que morde se o motor mudar isso.

    :param nome: o modelo VIVO, o que a mesa sabe — nunca o do desenho.
    :param via: `USB`/`BT` de agora. `—` ou vazio some da frase em vez de
        virar `(—)`: um travessão entre parênteses não diz nada a ninguém.
    :param recado: o primeiro retorno de `rotulo_lightbar`, ou `""`.
    :param coop_manda: `o_coop_manda(state)` — ver lá por que não é
        `coop.enabled`.
    """
    from hefesto_dualsense4unix.app.actions.lightbar_actions import (
        texto_do_desenho_aceso,
    )

    frases = [recado] if recado else []
    if coop_manda:
        #: O ÚNICO RAMO QUE ESTE PACOTE PODE AFIRMAR — ver o docstring.
        frases.append(texto_do_desenho_aceso(
            (False,) * 5, None, coop_ligado=True))
    quem = f"{nome} ({via})" if via and via != "—" else nome
    #: SEM FRASE, SÓ O NOME — e nunca `"Nome · "` com o separador órfão.
    return (f"{quem} · " + " · ".join(frases)) if frases else quem


def _da_mesa(ctx: Contexto, uniq: str) -> dict[str, Any]:
    """O item da MESA daquele controle, ou `{}`.

    A MESA é quem sabe o `nome` do modelo e a `via` — o `conectados` cru não
    sabe. É a mesma porta que `a01_jogar.py:44` usa, e usar outra criaria uma
    segunda verdade sobre o mesmo controle na mesma janela.
    """
    for m in ctx.mesa:
        if str(m.get("uniq") or "") == uniq:
            return m
    return {}


def _numero(ctx: Contexto, c: dict[str, Any]) -> int:
    """O número deste controle, pela regra do MOTOR — e ela tem UM dono.

    `app/actions/base.numero_do_controle` é a fonte única (COR-01/D6): o
    `player_slot` de sessão, que sobrevive a desconectar e reconectar, com queda
    para a posição. O docstring dele conta por que existe: *"Existia uma cópia
    dessa regra em cada tela (…) Duas verdades na mesma janela sobre qual é o
    'Controle 1'."*

    ESTA ABA TINHA A TERCEIRA CÓPIA, e ela era a errada: o rótulo lia só
    `player`, que é `None` para quem não é jogador do co-op — e a mesma aba
    escrevia `Modelo: P—` no rótulo com o botão `2` ACESO logo abaixo (D2,
    fotografado em 02/09/2026). A quarta cópia estava no gesto `auto`
    (`player_slot or player or 1`).

    A MESA JÁ CHAMA O MOTOR: `mesa_viva.mesa_do_estado:324` põe
    `numero_do_controle(entrada)` em `jogador`. Ler dela é o caminho mais curto
    e é o que faz esta aba concordar com a fita e o cabeçalho acima dela;
    perguntar direto ao motor é a queda para quando o controle não está na mesa.
    """
    da_mesa = _da_mesa(ctx, str(c.get("uniq") or "")).get("jogador")
    if isinstance(da_mesa, int) and not isinstance(da_mesa, bool):
        return da_mesa
    from hefesto_dualsense4unix.app.actions.base import numero_do_controle

    return numero_do_controle(c)


def _cor_do_plastico(slug: str) -> str:
    """O hex da casca daquele modelo, ou `""` quando ninguém sabe ainda.

    `monta.cor_da_zona` é o dono — ele LÊ a folha que pinta o desenho
    (`scripts/gerar_cores_do_dualsense.py`) em vez de digitar o hex, e é por
    isso que o Cosmic Red do mockup deixou de divergir da amostragem.

    O `""` NÃO é desistência: a cor do plástico chega pelo broker, uma vez por
    endereço e em thread, então o primeiro tique de uma sessão sempre tem a mesa
    sem cor.

    FATO ERRADO, SUBSTITUÍDO (03/09/2026): esta linha dizia que sem hex *"o
    botão sai SEM anel — que é exatamente o que o desenho faz com um número cujo
    dono não está aqui"*, e descrevia o defeito como se fosse o desenho. Não é:
    um número TOMADO por um controle sem cor conhecida pintava igual a um número
    LIVRE, e só o `title` os separava. Hoje ele sai com o anel TRACEJADO —
    ver `ANEL_INCERTO`.
    """
    if not slug:
        return ""
    try:
        import monta  # o `pacotes/__init__` põe `interface/` no `sys.path`

        return str(monta.cor_da_zona(slug))
    except Exception:
        # `cor_da_zona` levanta `SystemExit` para colorway que o SVG não tem.
        # Derrubar a pintura da aba por causa de um modelo novo seria trocar um
        # anel que falta por uma tela congelada.
        return ""


def um_botao_de_player(nome: str, meu: int, n: int,
                       dono: dict[str, Any] | None) -> str:
    """Um número, na coluna de UM controle: dá-lo a este troca-o com o dono.

    ESTA FUNÇÃO TEM DOIS CHAMADORES E UM DONO. O gerador `aba04.py` a chama para
    desenhar a bancada; o pacote a chama a cada tique para pintar a fileira
    viva. Enquanto eram duas escritas, o botão do desenho e o botão do produto
    podiam divergir sem ninguém ver — e é o mesmo defeito que deixou a
    `novo-layout/` divergir 25 KB calada.

    O DONO SÓ EXISTE SE ELE ESTIVER NA MESA — 31/08/2026. O `title` dizia *"o
    Galactic Purple, que tem o 3 hoje"* com o Galactic Purple DESCONECTADO. Ele
    não tem o 3 hoje; ele não tem nada hoje. Um número sem dono na mesa é um
    número **livre**, e é isso que a dica diz.

    SÃO TRÊS ESTADOS, E A TELA MOSTRAVA DOIS — 03/09/2026, e ver `ANEL_INCERTO`:

        livre          ninguém tem este número      sem anel
        tomado         e eu sei a cor do dono       anel cheio, na cor do plástico
        tomado, sem cor  o dono está aqui, a cor não chegou  anel TRACEJADO

    O terceiro caía no primeiro, e a diferença viajava só no `title`.
    """
    cor = _cor_do_plastico(str(dono.get("cor") or "")) if dono else ""
    if dono is None:
        anel = ""
    elif cor:
        anel = (f'<i class="dono" data-hef="{ANEL_DO_DONO}" '
                f'style="--plastico:{cor}"></i>')
    else:
        anel = (f'<i class="dono incerta" data-hef="{ANEL_DO_DONO}" '
                f'style="{ANEL_INCERTO}"></i>')
    if n == meu:
        dica = f"O {nome} É o Player {n} — é o número dele hoje."
    elif dono is None:
        dica = f"Player {n} — livre."
    else:
        dica = (f"Dar o Player {n} ao {nome}: o {dono['nome']} ({dono['via']}), "
                f"que tem o {n} hoje, fica com o {meu}. Os dois trocam de "
                f"lugar — ninguém repete número e ninguém fica sem.")
    return (f'<button class="{"on" if n == meu else ""}" '
            f'data-gesto="player" data-player="{n}" title="{dica}">{anel}{n}</button>')


def fileira_de_players(nome: str, meu: int, donos: dict[int, dict[str, Any]],
                       recuo: str = "") -> str:
    """Os quatro botões de uma coluna, em HTML — o miolo de `.players`.

    POR QUE A FILEIRA INTEIRA, e não um endereço por botão: o que muda com o
    dado é **qual botão fica `on`** e **o texto da dica**, e a pintura desta
    casa (`hefesto_vivo.escrever`) sabe escrever texto, largura, fundo, valor e
    HTML — **classe, não**. Com um `data-campo` por botão, os quatro só podiam
    receber texto, e texto num `<button>` apaga o anel do dono que está dentro
    dele. A fileira inteira pelo alvo `html` é o mesmo degrau que a fita e o
    mapa do gabinete já usam: um bloco cujo conteúdo muda com a mesa se troca
    inteiro. O ouvinte de clique é delegado no documento, então trocar o HTML
    não desliga botão nenhum.
    """
    return "\n".join(recuo + um_botao_de_player(nome, meu, n, donos.get(n))
                     for n in NUMEROS)


def desenho_da_luz(tinta: str, brilho: float, jogador: int, dica: str = "",
                   recuo: str = "", estado: str = "") -> str:
    """O miolo do `.aceso`: as duas tiras e as cinco lâmpadas, VIVAS.

    O DEFEITO QUE ESTA FUNÇÃO MATA está fotografado na tela dela em
    02/09/2026, com dois controles na mesa::

        a célula LEDs das colunas P1 e P2 mostrando a palavra `Aceso`

    O `.aceso` é um DESENHO — duas tiras de luz e as cinco lâmpadas do
    indicador —, e o pacote escrevia nele a palavra `Aceso` por um `data-campo`
    de alvo `texto`. `escrever()` faz `el.textContent = t`, que **apaga os
    filhos**: as duas tiras e as cinco lâmpadas sumiam no primeiro tique, e a
    régua do mockup contava isso como PRODUTO, porque o valor MUDOU. É a mesma
    família do `balanceado` escrito dentro dos quatro botões da Vibração e da
    contagem escrita dentro do `<tbody>` da Perfis.

    A PERGUNTA QUE SEPARA OS DOIS CASOS, e vale para toda aba: *isto é um DADO
    ou é o DESENHO?* Um desenho cujo conteúdo muda com o dado se troca INTEIRO,
    pelo alvo `html` — o mesmo degrau que a fita, o mapa do gabinete e a fileira
    de players já usam.

    UM DONO, DOIS CHAMADORES: o gerador `aba04.py` desenha a bancada com esta
    função e o pacote pinta o produto com ela a cada tique. Enquanto eram duas
    escritas, o desenho e o produto podiam divergir sem ninguém ver.

    NADA AQUI É NOVO — tudo tem dono no motor:

    * as cinco lâmpadas saem de `monta.luzinhas`, que lê
      `core/led_control.player_led_pattern` (o MESMO padrão que o daemon acende);
    * a tinta é `_tinta`, isto é `monta.tom_da_casa` do hex vivo;
    * quem decide se HÁ cor a afirmar é `controller_card.rotulo_lightbar` — o
      chamador passa `""` quando não há;
    * a `dica` inteira é `dica_da_luz` — o nome VIVO mais as frases do motor
      que este pacote pode conferir, e nada além delas (ver lá).

    A DICA VIAJA NAS TRÊS PEÇAS, e não na célula em volta. O `title` da célula
    é um ATRIBUTO, e o piloto não tem alvo de pintura para atributo — os alvos
    são `texto`, `largura`, `fundo`, `valor`, `html`, `classe` e `cor`
    (`hefesto_vivo.escrever`). Um `title` na célula, portanto, fica CONGELADO no
    que o gerador escreveu: era ele que dizia *"O Cosmic Red aceso…"* na coluna
    de um controle branco. Posto nas peças, ele entra pelo mesmo alvo `html` que
    troca o desenho, e muda com a mesa. **RELATO:** um alvo `titulo` no piloto
    resolveria isto para as dezenove dicas congeladas desta aba de uma vez.

    :param tinta: o hex JÁ no tom da casa. `""` desenha a tira APAGADA
        (`TIRA_APAGADA`), e nunca uma tira sem estilo — ver a constante. Com
        `estado=INCERTA` a tinta não é olhada: quem não sabe não pinta.
    :param brilho: de 0.0 a 1.0, a opacidade das duas tiras ACESAS. A apagada
        não tem brilho: uma barra desligada a 30% seria 30% de nada.
    :param jogador: o número deste controle, para o padrão das lâmpadas.
    :param dica: a frase de `dica_da_luz`, ou `""`. Sem ela as peças saem sem
        `title`, que é o que o desenho fazia antes de haver frase viva.
    :param estado: `ACESA`, `APAGADA` ou `INCERTA` — o que `estado_da_tira`
        respondeu. `""` quer dizer **sem estado declarado**, e aí a tinta
        decide: é o que a BANCADA sabe, porque o gerador não tem motor a
        perguntar. Nunca vale `INCERTA` por omissão — inventar "não sei" onde
        ninguém perguntou seria a tela afirmando uma dúvida que não existe.
    """
    import monta  # o `pacotes/__init__` põe `interface/` no `sys.path`

    # A TIRA TRACEJADA — decisão 9 dela. Ver `ACESA/APAGADA/INCERTA`.
    #
    # O TRACEJADO É DA FOLHA (`aba04.CSS`, `.tira-luz.incerta`), e o que sai
    # daqui é só a CLASSE — o nome do estado, uma vez. O contorno escrito inline
    # seria um segundo dono do traço, e inline vence folha: no dia em que o
    # desenho do contorno mudasse, o produto ficaria com o antigo, calado.
    #
    # MAS O ESTILO DE LINHA NÃO SOME, e isto é o PISO, não decoração. Uma página
    # cuja folha ainda não conhece `.tira-luz.incerta` — o publicado de hoje, até
    # ela mandar publicar a 04 — deixaria a tira sem `background` E sem `color`:
    # o halo é `box-shadow: … currentColor` (`.tira-luz.esq`/`.dir`), e `color`
    # herdado nesta página é o `--fg`, `#f8f8f2`. A tira do "não sei" ACENDERIA
    # BRANCA. É o mesmo defeito que `TIRA_APAGADA` já aprendeu na foto, e por
    # isso o piso é o DELA, literalmente a mesma constante: sem halo, sem cor
    # herdada. Onde a folha é a nova, ela ACRESCENTA o contorno tracejado — não
    # disputa nada com o estilo de linha; onde é a velha, a tira fica como está
    # hoje, e nada se perde enquanto a publicação não vem.
    incerta = estado == INCERTA
    estilo = (TIRA_APAGADA if (incerta or estado == APAGADA or not tinta)
              else f"background:{tinta};color:{tinta};opacity:{brilho}")
    veste = f' style="{estilo}"'
    # O ENDEREÇO DO ESTADO VIAJA NA TIRA, e não na célula em volta: a célula é o
    # bloco de alvo `html` que se troca inteiro, e um segundo `data-campo` nela
    # não cabe. Aqui ele é a marca que o pintor confirma a cada tique e que a
    # régua do mockup consegue LER — um desenho não tem texto, e `html` é lido
    # pelo texto.
    marca = (f' data-campo="{ENDERECO_DA_INCERTA}" data-hef-alvo="classe"'
             f' data-hef-classe="{CLASSE_DA_INCERTA}"')
    aviso = f" {CLASSE_DA_INCERTA}" if incerta else ""
    diz = f' title="{dica}"' if dica else ""
    tira = f'<span class="tira-luz %s{aviso}"{veste}{marca}{diz}></span>'
    try:
        lampadas = monta.luzinhas(jogador)
    except KeyError:
        # O DONO SABE O OVERFLOW E O ATALHO DA BANCADA NÃO. `player_led_pattern`
        # devolve um padrão para qualquer número — o docstring dele diz que *"um
        # DualSense pode legitimamente cair no slot 5+"* e que *"≥9 cai no padrão
        # de overflow"* —, mas `monta.PADRAO_JOGADOR` só precomputa 1..8 e
        # `monta.luzinhas(9)` levanta `KeyError`. Medido em 02/09/2026.
        #
        # Enquanto só o gerador a chamava, o número era 1..4 e ninguém via; o
        # produto passa a chamá-la com o número VIVO. Um número que a bancada
        # nunca teve não pode congelar a aba inteira — é o mesmo cuidado de
        # `_cor_do_plastico`. Sem padrão conhecido o indicador sai VAZIO, que é o
        # honesto: inventar o do Player 1 diria um número que não é o dele.
        #
        # A CURA DE VERDADE mora em `interface/monta.py`, que não é território
        # deste arquivo: `luzinhas` deve chamar `player_led_pattern` em vez de
        # indexar o dicionário. RELATADO.
        lampadas = ""
    return "\n".join(recuo + linha for linha in (
        tira % "esq",
        f'<span class="pad"{diz}>{lampadas}</span>',
        tira % "dir",
    ))


#: O SELETOR DO ANTES/DEPOIS do rodapé — CSS, e não `data-campo`, porque é um
#: `blocos:` (`hefesto_vivo`, o laço `for(const [seletor, html] of
#: Object.entries(p.blocos || {}))`). É a mesma escolha do `SELETOR_DA_LISTA` da
#: `10-perfis`: o número de filhos muda com a mesa, e não há endereço para um
#: filho que ainda não existe.
SECAO_DA_TROCA = ".nota-troca"

#: O título da seção, num lugar só: ele sai do gerador E do pacote.
TITULO_DA_TROCA = "Trocar o número: o antes e o depois"

#: A CAIXA DE UM LUGAR DA MESA nesta aba — o que a 06 chama de `.nav-ctl`. Ela
#: entra na folha viva do plástico (`folha_do_plastico`), e o par
#: `.ctrl[data-controle="p1"] .ds-svg` vale (0,3,0), que vence o
#: `svg[data-colorway="…"]` (0,1,1) embutido no próprio SVG.
CAIXA_DA_COLUNA = ".ctrl"


def _folha_do_plastico(mesa: list[dict[str, Any]], caixa: str) -> str:
    """A folha viva do casco, com o dono que a aba Navegação já tem.

    IMPORTA TARDE de propósito, como o `import monta` das outras funções deste
    módulo: os pacotes das dez abas se registram no import, e uma dependência no
    topo entre dois deles amarraria a ordem de carga a um detalhe de quem
    escreveu primeiro.

    UM DONO, DOIS CHAMADORES — a mesma disciplina da `fileira_de_players` e do
    `desenho_da_luz`. Copiar a função para cá daria duas leituras do
    `ds_limpo.svg` que divergem no primeiro modelo novo.
    """
    from . import a06_navegacao

    return a06_navegacao.folha_do_plastico(mesa, caixa)


def _luzinhas(numero: int) -> str:
    """As cinco lâmpadas daquele número, ou `""` quando ninguém sabe o padrão.

    O guarda é o mesmo de `desenho_da_luz`, e pela mesma razão medida:
    `monta.PADRAO_JOGADOR` só precomputa 1..8 e `monta.luzinhas(9)` levanta
    `KeyError`, enquanto `core/led_control.player_led_pattern` responde a
    qualquer número. Enquanto só o gerador chamava, o número era 1..4.
    """
    import monta  # o `pacotes/__init__` põe `interface/` no `sys.path`

    try:
        return str(monta.luzinhas(int(numero)))
    except (KeyError, TypeError, ValueError):
        return ""


def item_da_troca(nome: str, numero: int, plastico: str,
                  mexeu: bool = False) -> str:
    """Um controle com um número, no antes/depois do rodapé.

    `data-hef` PELA MESMA RAZÃO DO ANEL DA FILEIRA: o `--plastico` mora no
    `style` DESTE elemento, e a régua da identidade julga o `--plastico` no
    elemento que o carrega. Aqui ele não é congelado — a seção inteira é um
    `blocos:` que o produto reescreve com a mesa viva —, e o endereço é o que
    diz isso.

    O ANEL TRACEJADO CHEGA AQUI TAMBÉM — 03/09/2026, e pela mesma razão do
    vizinho (`ANEL_INCERTO`). Todo item desta seção É um controle na mesa, então
    aqui não há "livre" a confundir; o que havia era o anel SUMINDO. Sem
    `--plastico`, a folha (`border:2px solid var(--plastico)`) fica inválida no
    tempo de computar, o `border-style` cai para `none` e a linha perde a marca
    de identidade que as vizinhas têm — sem nada dizer que a diferença é *"não
    sei a cor"*, e não *"este é de outro tipo"*.

    :param plastico: o hex da casca, ou `""` — e sem hex o item sai com o anel
        TRACEJADO, que é como esta aba diz "não sei" desde a decisão 9 dela.
    """
    veste = f' style="--plastico:{plastico}"' if plastico else ""
    # O ESTILO VAI NO `<i>`, e nunca no pai: a folha pinta `.troca-item .dono`,
    # e um `style=` no pai não alcança a `border` do filho.
    anel = ('<i class="dono"></i>' if plastico
            else f'<i class="dono incerta" style="{ANEL_INCERTO}"></i>')
    return (f'<span class="troca-item{" mexeu" if mexeu else ""}"'
            f' data-hef="troca.item"{veste}>'
            f'{anel}<span class="np">P{numero}</span>'
            f'<span>{nome}</span>{_luzinhas(numero)}</span>')


def secao_da_troca(mesa: list[dict[str, Any]], recuo: str = "  ") -> str:
    """A seção "Trocar o número" inteira, com a mesa que lhe derem.

    POR QUE ELA DEIXOU DE SER TEXTO FIXO — 03/09/2026, a lei dela: *"se no topo
    tá mostrando controle white player 1, então cada aba vai usar os controles
    lá de cima. Não mistura com a info dos mockups."* Esta seção é o exemplo do
    caso REAL dela, de 26/08 (*"o meu controle azul é o player 2 e antes de
    irmos pro jogo ele tem que ser o player 1"*) — e o exemplo estava escrito
    com os dois controles do DESENHO, num rodapé que o produto renderiza.

    UM DONO, DOIS CHAMADORES, como a fileira de players e o desenho da luz: o
    gerador desenha a bancada com esta função e o pacote a manda a cada tique
    por `blocos:`. Enquanto fossem duas escritas, as duas podiam divergir.

    A TROCA PRECISA DE DOIS. Com menos de dois controles na mesa não há exemplo
    a contar, e a seção diz isso em vez de inventar um segundo controle — é a
    regra dela: campo sem informação não mostra nada.
    """
    r = recuo
    ordenada = sorted(mesa, key=lambda c: int(c.get("jogador") or 0))
    cabeca = f"{r}<h2>{TITULO_DA_TROCA}</h2>"
    if len(ordenada) < 2:
        quantos = "nenhum controle" if not ordenada else "um controle só"
        return (f"{cabeca}\n"
                f"{r}<p>A troca acontece entre <b>dois</b> controles, e a mesa tem "
                f"{quantos} agora. Com dois ligados, esta seção mostra o antes e "
                f"o depois com eles.</p>")

    from hefesto_dualsense4unix.core.led_control import player_slot_color

    tem, quer = ordenada[0], ordenada[1]
    #: O DEPOIS é uma PERMUTAÇÃO, e é o que a frase dela exige: *"nunca fica um
    #: número repetido nem um controle sem número"*. Os dois trocam, os outros
    #: ficam onde estão.
    depois = {c["pref"]: int(c["jogador"] or 0) for c in ordenada}
    depois[quer["pref"]] = int(tem["jogador"] or 0)
    depois[tem["pref"]] = int(quer["jogador"] or 0)

    def _linha(rotulo: str, numero_de: Any, mexeu_de: Any) -> str:
        itens = "\n".join(
            f"{r}    " + item_da_troca(str(c.get("nome") or "—"), numero_de(c),
                                       _cor_do_plastico(str(c.get("cor") or "")),
                                       mexeu_de(c))
            for c in ordenada)
        return (f'{r}  <div class="troca-linha">'
                f'<span class="troca-rot">{rotulo}</span>\n{itens}\n{r}  </div>')

    numeros = " · ".join(str(int(c["jogador"] or 0)) for c in ordenada)
    return "\n".join([
        cabeca,
        f'{r}<p>O caso é o seu, de 26/08 — <i>"o meu controle azul é o player 2 e '
        f"antes de irmos pro\n{r}jogo ele tem que ser o player 1\"</i>. Na coluna "
        f'do <b>{quer["nome"]}</b>, clique no\n{r}<b>{tem["jogador"]}</b>:</p>',
        "",
        f'{r}<div class="troca">',
        _linha("Antes", lambda c: int(c["jogador"] or 0), lambda c: c is quer),
        f'{r}  <div class="troca-gesto">↓ clique no <b>{tem["jogador"]}</b> na '
        f'coluna do\n{r}    <b>{quer["nome"]}</b></div>',
        _linha("Depois", lambda c: depois[c["pref"]],
               lambda c: depois[c["pref"]] != int(c["jogador"] or 0)),
        f"{r}</div>",
        "",
        f"{r}<ul>",
        f"{r}  <li><b>Os dois trocam, os outros não se mexem.</b> É uma permutação: "
        f"ninguém repete\n{r}      número e ninguém fica sem. Por isso a fileira "
        f'oferece\n{r}      <span class="marca">{numeros}</span> — os números que'
        f"\n{r}      existem na mesa. Um número livre não teria com quem trocar, e "
        f"dá-lo deixaria um\n{r}      controle sem número.</li>",
        f"{r}  <li><b>As luzinhas seguem o número</b>, no padrão do produto: 1 é a "
        f"do <b>meio</b>,\n{r}      2 são as duas de dentro, 3 são as pontas e o "
        f"meio, 4 são quatro sem a do meio\n{r}      "
        f"(<code>core/led_control.py::player_led_pattern</code>).</li>",
        f"{r}  <li><b>E a cor da barra segue junto</b>, porque sem escolha à mão "
        f"ela é a cor do\n{r}      <i>número</i>: depois da troca o "
        f'{quer["nome"]} acende\n{r}      <span class="marca">'
        # `_hex` É O DONO DA FORMA `#RRGGBB` neste arquivo, e usá-lo aqui evita a
        # segunda escrita da mesma conversão — a que já divergiu uma vez.
        f'{_hex(player_slot_color(int(tem["jogador"] or 0)))}</span> e o '
        f'{tem["nome"]} acende\n{r}      <span class="marca">'
        f'{_hex(player_slot_color(int(quer["jogador"] or 0)))}</span>'
        f"\n{r}      (<code>core/led_control.py::player_slot_color</code>).</li>",
        f"{r}</ul>",
    ])


@registrar("04-iluminacao.html")
def pacote(ctx: Contexto) -> dict[str, Any]:
    p = perfil.ativo(ctx.state.get("active_profile"))
    #: O BRILHO É DO PERFIL, e é um só para a mesa quando não há override — como
    #: o gatilho. A leitura tem UM dono desde 03/09/2026 (`brilho_do_controle`),
    #: porque os gestos que escrevem a cor passaram a precisar do mesmo número.

    # A FRASE DA DISPUTA É DO MOTOR, e não se reescreve.
    # `app/widgets/controller_card.rotulo_lightbar` é a mesma que os cards da
    # GUI estável já usam, e ela sabe QUATRO estados onde este pacote sabia um:
    # Nativo (o jogo é dono do LED), a Steam segurando o `fd`, cor desconhecida
    # e apagada. O texto que estava aqui era a segunda verdade — e ainda dizia
    # mais do que o campo mede: `lightbar_disputada` sai de quem SEGURA o
    # `fd`, não de quem escreve (426 reports contra 1, medido em 22/08).
    #
    # E ELA DECIDE MAIS DO QUE A FRASE: o SEGUNDO valor de retorno é a cor BASE,
    # e ele é `None` exatamente nos dois estados em que não há cor a afirmar —
    # "cor desconhecida" e "apagada". Este pacote jogava esse valor fora
    # (`recado, _base = …`) e decidia de novo, com `c.get("lightbar_on", True)`
    # — uma segunda verdade, e com o default INVERTIDO: sem o campo, ela
    # afirmava ACESA. `cor_do_swatch` é o dono da leitura crua, para o `hex`.
    from hefesto_dualsense4unix.app.widgets.controller_card import (
        cor_do_swatch,
        rotulo_lightbar,
    )

    # OS DONOS DOS NÚMEROS, uma vez para a mesa inteira: cada coluna precisa
    # saber de QUEM é o número que ela oferece, e não só do próprio.
    donos: dict[int, dict[str, Any]] = {}
    for c in ctx.conectados:
        casa_dele = _da_mesa(ctx, str(c.get("uniq") or ""))
        # SEM ITEM DE MESA NÃO HÁ DONO A NOMEAR. A dica do botão diz o `nome` e
        # a `via` de quem tem o número, e os dois moram na mesa; inventá-los
        # seria a oitava aparição da *frase que nomeia um controle que não
        # está lá*. Sem eles o número sai como LIVRE, que é o honesto.
        if casa_dele:
            donos[_numero(ctx, c)] = casa_dele

    colunas: dict[str, dict[str, Any]] = {}
    for c in ctx.conectados:
        uniq = str(c.get("uniq") or "")
        crua = cor_do_swatch(c)
        b = brilho_do_controle(p, uniq)
        pct = None if b is None else round(float(b) * 100)
        casa = _da_mesa(ctx, uniq)
        n = _numero(ctx, c)
        nome = str(casa.get("nome") or "—")
        via = str(casa.get("via") or (c.get("transport") or "").upper() or "—")
        recado, base = rotulo_lightbar(c, ctx.state)
        #: A TIRA PERGUNTA OUTRA COISA, e o segundo retorno não responde a ela.
        #: `rotulo_lightbar` devolve `(ressalva, COR BASE DO ACCENT)`, e a base
        #: é a ÚLTIMA COR CONHECIDA — devolvida também nos dois estados em que
        #: o próprio motor avisa que ela pode não estar no plástico:
        #:
        #:     native_mode           → ("Em Nativo o jogo é dono do LED", rgb)
        #:     lightbar_disputada    → ("a Steam tem este controle aberto", rgb)
        #:
        #: Nos DOIS a base volta preenchida **com `lightbar_on` falso**, porque
        #: a pergunta que ela responde é *"de que cor pinto o traço do card?"* e
        #: não *"a barra está acesa?"*. Este pacote lia a base como se fosse a
        #: segunda pergunta — e a tira acendia sob Steam ou sob Nativo com a
        #: barra apagada. Medido em 02/09/2026 com o dublê de estado.
        #:
        #: QUEM RESPONDE A PERGUNTA DA TIRA É O PRIMEIRO RETORNO: `rotulo_lightbar`
        #: devolve `None` no rótulo em UM único ramo — o último, *"cor conhecida
        #: e acesa"*. Nos outros quatro há ressalva, e ressalva é exatamente
        #: "não afirme". É a regra dela de hoje, aplicada ao desenho: *"se não
        #: tá mostrando agora, não tem info pra mostrar no produto"*.
        acesa = base if recado is None else None
        #: A COR QUE ELA PEDIU, e não a que o daemon publica — ver
        #: `cor_escolhida`. O `lightbar_rgb` é PÓS-ESCALA de brilho por
        #: contrato do daemon, e esta aba o tratava como pré-escala: com o
        #: brilho abaixo de 100% a caixa mostrava uma cor que ela nunca pediu,
        #: a marca dos oito tons apagava e a tira escurecia duas vezes.
        pedida = cor_escolhida(crua, b)
        #: QUAL DOS TRÊS ESTADOS A TIRA DESENHA — decisão 9 dela. Ele sai do
        #: MESMO primeiro retorno que decide `acesa`, e não de uma segunda
        #: leitura: "apagada" e "não sei" só se separam pela frase do motor.
        estado = estado_da_tira(recado)
        colunas[uniq] = {
            #: A TELA MOSTRA PORCENTAGEM, e o `%` é DELA: o desenho escreve
            #: `82%` nesta caixa. Emitir o `0.82` cru — o que esta linha fazia
            #: até 02/09/2026 — punha um `1` ao lado de uma barra parada, que é
            #: metade do defeito D7 fotografado naquele dia.
            "brilho": "—" if pct is None else f"{pct}%",
            #: A OUTRA METADE é a LARGURA da barra, e ela depende de a página
            #: trazer `data-hef-alvo="largura"` — as abas 02 e 05 têm, esta não
            #: tinha, e por isso o `100` era impresso DENTRO do trilho.
            "brilho-pct": pct,
            #: A COR ESCOLHIDA, que é o que a caixa `#RRGGBB` mostra — e ela não
            #: some quando a barra apaga: o hex diz QUAL cor está gravada, o
            #: desenho abaixo diz se ela está acesa.
            #:
            #: ELE ERA `_hex(crua)` ATÉ 03/09/2026, e a cor crua é a PÓS-ESCALA
            #: de brilho do daemon. Este mesmo campo endereça DUAS coisas na
            #: página: a caixa de texto e os OITO tons da guia, que acendem o
            #: `on` por `data-hef-quando="#0000FF"` — os oito CHEIOS. Com o
            #: brilho em 50% o daemon publica `#00007F`, e a marca apagava em
            #: todos: a tela deixava de dizer qual cor está escolhida
            #: exatamente quando ela mexia no brilho. Ver `cor_escolhida`.
            "hex": _hex(pedida),
            #: A COR DO PLÁSTICO, e ela é a lei dela de 03/09/2026: *"se
            #: identificou o controle como modelo White a cor do card em volta
            #: tem que ser branco. Temos isso no mapa."*
            #:
            #: A BORDA DA MOLDURA ERA A DO DESENHO, e isso está FOTOGRAFADO em
            #: 03/09: a fita e o rótulo diziam `P1 • White • USB` e a moldura
            #: logo abaixo estava vermelha — o Cosmic Red do mockup. Não é uma
            #: palavra errada: é a cor, que é como esta aba diz de quem é a luz
            #: (`D-A-BORDA-E-A-IDENTIDADE-DA-PECA`).
            #:
            #: O ALVO É `cor`, e não um alvo de variável CSS: o pintor sabe
            #: `texto`, `largura`, `fundo`, `valor`, `html`, `classe` e `cor`, e
            #: nenhum deles escreve um `--plastico`. A folha desta aba passou a
            #: ler a borda de `currentColor`, que é o que o alvo `cor` escreve.
            #:
            #: VAZIO APAGA, e é a regra dela: campo sem informação não mostra
            #: nada. `escrever` devolve `el.style.color = ''` e a borda cai para
            #: `var(--linha)` da folha — neutra. Sem cor do broker (o primeiro
            #: tique de toda sessão, e o rádio enquanto a leitura não chega) a
            #: moldura fica cinza, e nunca com a cor de um controle que não é o
            #: dela.
            "plastico": _cor_do_plastico(str(casa.get("cor") or "")),
            #: O DESENHO DO CONTROLE, e ele é o maior objeto desta tela: 146 px
            #: de altura por coluna. A moldura já vestia o aparelho desde hoje
            #: de manhã, e o que ficava dentro dela era o mockup — fotografado
            #: nesta árvore com a mesa dela: rótulo `P1 • White • USB` e um
            #: DualSense Cosmic Red desenhado a três centímetros dele.
            #:
            #: ELE SÓ SAI SE HOUVER ONDE PÔR E QUEM PINTE — ver
            #: `a_pintura_alcanca_o_desenho`. Enquanto a 04 não for publicada, o
            #: produto renderiza o desenho de ontem, que não tem este endereço;
            #: e sem o alvo `atributo` no piloto, escrever aqui APAGARIA o
            #: desenho em vez de vesti-lo.
            **({CAMPO_DO_DESENHO: colorway_do_aparelho(casa)}
               if a_pintura_alcanca_o_desenho() else {}),
            #: O DESENHO DA LUZ, e não a PALAVRA. Até 02/09/2026 esta linha era
            #: `"aceso": "Aceso" if …`, escrita num `data-campo` de alvo
            #: `texto` — e `el.textContent = "Aceso"` **apagava** as duas tiras
            #: e as cinco lâmpadas do `.aceso`. Fotografado na tela dela.
            #:
            #: O NOME MUDOU DE PROPÓSITO, e é o que faz a cura valer HOJE: o
            #: HTML publicado ainda diz `data-campo="aceso"`, e publicar é ato
            #: DELA. Com o endereço novo, o produto de agora não acha onde
            #: escrever e o desenho fica INTEIRO — em vez de virar uma palavra.
            #: No dia em que ela publicar, o mesmo valor passa a pintar.
            #:
            #: QUEM DECIDE SE HÁ COR É O MOTOR, e a leitura certa do que ele
            #: devolve está anotada em `acesa`, acima. A leitura que estava aqui
            #: antes de 02/09 (`c.get("lightbar_on", True)`) era uma segunda
            #: verdade, e o default dela AFIRMAVA aceso na ausência do campo —
            #: que é o estado de partida de um controle no rádio.
            #: A TINTA SAI DA COR PEDIDA, e o brilho entra UMA VEZ SÓ, na
            #: `opacity` — 03/09/2026. Ela saía de `_tinta(acesa)`, e `acesa` é
            #: a pós-escala do daemon: a 50% o `tom_da_casa` não reconhecia
            #: `#00007F` (a tabela tem os oito CHEIOS) e devolvia o hex CRU, que
            #: é a cor que a guia não mostra em lugar nenhum — e a `opacity` a
            #: escurecia de novo. Com a pedida, a tira volta ao modelo da GTK:
            #: tom da casa vezes o brilho, que é o que `_on_lightbar_preview_draw`
            #: desenha (o `rgb` do rascunho vezes o brilho).
            "luz": desenho_da_luz(_tinta(cor_escolhida(acesa, b)),
                                  1.0 if b is None else float(b), n,
                                  dica_da_luz(nome, via, recado or "",
                                              o_coop_manda(ctx.state)),
                                  estado=estado),
            #: O TRACEJADO, COM ENDEREÇO PRÓPRIO — e ele vem DEPOIS do `luz` de
            #: propósito. O `luz` troca o miolo do `.aceso` inteiro (alvo
            #: `html`) e recria as duas tiras; o pintor percorre os campos na
            #: ordem em que este dicionário os declara, então escrever a classe
            #: antes seria escrevê-la num elemento que a linha de cima está
            #: prestes a substituir.
            #:
            #: O HTML EMITIDO JÁ TRAZ A CLASSE — este campo não a acrescenta,
            #: ele a CONFIRMA. E confirmar é o que faltava: sem um endereço que
            #: a régua saiba ler, o único sinal do estado morava dentro de um
            #: bloco `html`, que é lido pelo TEXTO visível — e um desenho não
            #: tem texto.
            #:
            #: `"sim"`/`""` E NUNCA UM BOOLEANO: `str(True)` é `"True"` e o JS
            #: escreveria `"true"`; as duas réguas desta casa que traduzem o
            #: declarado dizem, por escrito, que erram nesse par.
            ENDERECO_DA_INCERTA: "sim" if estado == INCERTA else "",
            #: O RÓTULO INTEIRO, e não só o número. O desenho escreve
            #: `P1 • Cosmic Red • USB`; emitir só o `P1` fazia o primeiro tique
            #: APAGAR o nome do controle e o transporte da tela dela — a
            #: pintura escreve `textContent`, e três pedaços viravam um.
            "identidade": f"P{n} • {nome} • {via}",
            #: A FILEIRA DOS QUATRO NÚMEROS, viva. O `on` sai daqui, e as dicas
            #: também: as do HTML publicado estão CONGELADAS do desenho e
            #: nomeiam controle por transporte que já mudou.
            "players": fileira_de_players(nome, n, donos),
        }
    return {
        "colunas": colunas,
        "perfil": ctx.state.get("active_profile") or "",
        "sem_dono": {},
        #: O ANTES/DEPOIS DO RODAPÉ, com a mesa VIVA — ver `secao_da_troca`.
        #: Ele pousa por `document.querySelector`, então numa página que ainda
        #: não tem a seção (o publicado de hoje, enquanto ela não publicar) o
        #: laço não acha nada e não escreve — calado e correto.
        #:
        #: E O CASCO DO DESENHO GRANDE, pelo mesmo caminho — 03/09/2026. Era a
        #: maior identidade congelada desta aba, e a cura de hoje tinha parado na
        #: MOLDURA: medido nos pixels da tela dela, a borda da célula do P1 saía
        #: `rgb(228,224,216)` (o White, vivo) em volta de um controle desenhado
        #: em `rgb(174,51,90)` — o Cosmic Red do mockup. A mesma célula dizendo
        #: duas coisas, com o rótulo certo logo abaixo. Ver `folha_do_plastico`.
        "blocos": {SECAO_DA_TROCA: secao_da_troca(ctx.mesa),
                   "#plastico-vivo": _folha_do_plastico(ctx.mesa, CAIXA_DA_COLUNA)},
        #: O NÚMERO SAI DO DICIONÁRIO, nunca de uma constante escrita à mão —
        #: foi assim que a curva da aba Gatilhos ficou fora da cobertura.
        #: `player`, `fonte`, `recado` e `rgb` saíram em 02/09/2026: os quatro
        #: eram ÓRFÃOS — nenhuma das duas páginas tem onde pô-los —, e o que
        #: eles diziam passou a viver em `identidade`, no `hex` e no `title` das
        #: tiras de `luz`.
        "cobertura": {"pintados": sum(len(v) for v in colunas.values()),
                      "sem_dono": len(SEM_DONO)},
    }


# ---------------------------------------------------------------------------
# OS GESTOS — o clique dela chegando ao aparelho
# ---------------------------------------------------------------------------
# ESTE BLOCO É O EXEMPLO das outras nove abas. Quatro coisas, nesta ordem:
#
#   1. **NADA SE REESCREVE.** O `p` é `pacotes/ponte.py`, que expõe as 36
#      funções do `app/ipc_bridge.py` — a mesma camada que a GUI estável usa
#      para falar com o daemon, com o payload montado, o timeout pensado e a
#      recusa traduzida. Chamar o socket cru daqui perderia tudo isso, e foi o
#      que a pergunta dela corrigiu em 01/09: *"não estamos refazendo do zero
#      né?"*
#   2. o `uniq` chega em `o["uniq"]`, já traduzido pelo piloto: a tela endereça
#      por `pref` (`p1`) e o daemon por `uniq` (`d4:2f:00:00:…`).
#   3. a ponte é INJETADA — a função não importa o bridge, recebe. Por isso a
#      régua a testa com um dublê e cobra QUAL função foi chamada e com quê.
#   4. o que o produto não faz não vira botão que finge: vira botão que recusa
#      dizendo, e o nome sai no relato do piloto.
from . import gesto  # noqa: E402


def _uniq(o: dict[str, Any]) -> str:
    """O `uniq` do controle onde ela clicou. Vazio = clique solto, e recusa.

    `""` NÃO vira "todos": um "Desligar" sem dono apagaria a barra dos quatro
    controles em vez de um.
    """
    return str(o.get("uniq") or "")


def sem_resposta_do_daemon() -> str:
    """A frase de "o Hefesto não respondeu" — e ela é do MOTOR, não daqui.

    OS TRÊS BOTÕES QUE ESCREVEM NO APARELHO SAÍAM CALADOS até 02/09/2026:
    `cor`, `apagar` e `auto` chamavam `p.led_set(...)` e `p.chamar(...)` e
    **jogavam fora o booleano**. `ipc_bridge._safe_call` devolve `(False, None)`
    para daemon offline, socket ausente, timeout de conexão e erro JSON-RPC —
    e nesses casos o clique dela sumia: a barra não mudava, a tela não dizia
    nada, e o segundo clique parecia o primeiro. É o defeito que o BRIEFING
    desta casa nomeia como o mais caro, e o quarto gesto desta MESMA aba
    (`player`) já o evitava lendo `(ok, motivo)`.

    A FRASE NÃO SE ESCREVE AQUI. `lightbar_actions._AVISO_HEFESTO_DESLIGADO` é
    a que a janela GTK mostra neste mesmo evento — o ramo em que o `led.set`
    por `uniq` volta sem corpo (`lightbar_actions.py:950-951`). Duas telas do
    mesmo produto dizendo coisas diferentes sobre o mesmo daemon desligado é a
    segunda verdade que esta casa persegue.

    ELA É PRIVADA POR CONVENÇÃO DE NOME, e não por contrato — do mesmo jeito
    que o próprio `lightbar_actions` lê `footer_actions._lista_de_secoes` e
    `._mensagem_de_aplicacao`. **RELATADO:** ela merece nome público, e isso é
    `app/actions/lightbar_actions.py`, fora do território deste arquivo.

    E ELA JÁ VEM HEDGED, o que é o ponto: *"o Hefesto **pode** estar
    desligado"*. O `bool` do bridge colapsa quatro causas numa só (offline,
    socket, timeout e erro do servidor), então afirmar a causa seria inventar
    um diagnóstico — a frase aponta a mais provável e diz onde olhar.
    """
    from hefesto_dualsense4unix.app.actions import lightbar_actions

    return str(lightbar_actions._AVISO_HEFESTO_DESLIGADO)


def _so_abriu_o_seletor(o: dict[str, Any]) -> bool:
    """O clique é a ABERTURA de um `<input>`, e não uma escolha dela.

    Os dois campos são do BOOTSTRAP e chegam em todo clique: `tipo` é o
    `tagName` do alvo e `evento` é o `ev.type`. Um `<input type="color">`
    dispara `click` ao abrir — com o valor VELHO — e `change` quando ela
    confirma; só o segundo é um pedido.

    SEM `evento` NO CLIQUE, NADA MUDA. As provas do contrato e a régua chamam o
    gesto com a carga mínima, e uma carga sem `evento` não é a abertura de nada
    — o guarda só fecha quando os DOIS campos dizem que foi abertura.
    """
    return (str(o.get("tipo") or "").lower() == "input"
            and str(o.get("evento") or "").lower() == "click")


class _Janela:
    """O "host" mínimo que `app/textos_de_aplicacao.py` sabe interrogar.

    ELE NÃO É UMA JANELA E NÃO PRECISA SER. As três leituras que decidem a
    frase de um desfecho — `alvo_fora_da_mesa`, `modo_nativo_manda_no_output` e
    `mesa_vazia` — perguntam por `getattr` a um objeto qualquer; a GUI estável
    passa a si mesma porque é ela quem tem os campos, e a aba Status é quem os
    publica a cada tique do `state_full` (`status_actions.py`: o
    `_target_uniq_by_index` em `_update_target_maps`, o `_modo_nativo_ligado` em
    `_sync_modo_nativo_manda_no_output`, o `_coop_ligado` em
    `_sync_coop_governa_luzes`).

    Esta interface tem os MESMOS dados, da MESMA fonte — o `ctx.state` é o
    `state_full` —, e o que faltava era o objeto que os apresenta com os nomes
    que o dono da frase conhece. É a ponte inteira: nenhuma regra de texto se
    reescreve deste lado.
    """

    #: OS SEIS CAMPOS ANOTADOS, e não só listados no `__slots__`: os quatro
    #: primeiros são postos por `definir_alvo` (o dono do alvo de edição), e uma
    #: classe com `__slots__` sem anotação faz o mypy recusar a escrita dos dois
    #: últimos — que é o mesmo que dizer que este objeto não cumpre o contrato
    #: que `textos_de_aplicacao` interroga.
    _alvo_de_edicao: Any
    _edit_target_uniq: str | None
    _edit_target_label: str | None
    _target_uniq_by_index: dict[int, str | None]
    _modo_nativo_ligado: bool
    _coop_ligado: bool

    __slots__ = ("_alvo_de_edicao", "_coop_ligado", "_edit_target_label",
                 "_edit_target_uniq", "_modo_nativo_ligado", "_target_uniq_by_index")


def _janela_do_desfecho(ctx: Contexto, uniq: str, rotulo: str = "") -> Any:
    """Um `_Janela` com o estado DESTA mesa, para a frase do desfecho.

    O ALVO É POSTO PELO DONO, e não por atribuição: `alvo_de_edicao.definir_alvo`
    é quem sabe que `uniq` preenchido quer dizer CONTROLE e vazio quer dizer
    "Todos", e é quem espelha os dois atributos legados. Escrevê-los à mão aqui
    seria a segunda cópia da regra que aquele módulo nasceu para ter sozinho —
    e a aba nunca escreve sem `uniq`, então o ramo "Todos" não se alcança daqui.

    O `_coop_ligado` SAI DE `o_coop_manda`, e não de `coop.enabled`. A GTK lê o
    booleano e por isso diz *"quem manda é o co-op"* numa mesa com um jogador
    só — está medido em `o_coop_manda`, com a saída do daemon dela. Repetir o
    defeito para "ficar igual" seria portar a mentira junto com a frase. Na
    prática ele nem é consultado pelos gestos de COR (`coop_aplica=False`: a
    camada de co-op tem vocabulário de um campo só, `player_leds`), e está aqui
    para o dia em que o desenho das cinco luzes chegar ao HTML.
    """
    from hefesto_dualsense4unix.app.alvo_de_edicao import definir_alvo

    janela = _Janela()
    definir_alvo(janela, uniq or None, rotulo or None)
    janela._target_uniq_by_index = {
        int(c.get("index") or i): (str(c.get("uniq") or "") or None)
        for i, c in enumerate(ctx.conectados)}
    janela._modo_nativo_ligado = bool(ctx.state.get("native_mode"))
    janela._coop_ligado = o_coop_manda(ctx.state)
    return janela


def _nome_da_coluna(ctx: Contexto, uniq: str) -> str:
    """O rótulo daquele controle para a frase de guardado — o nome VIVO da mesa.

    `frase_de_guardado` diz *"vale quando o {alvo} voltar"*, e o {alvo} sai de
    `nome_curto_do_alvo(host._edit_target_label)`. Sem rótulo ele cai em
    `ALVO_SEM_NOME`, que é a frase genérica; com o nome da mesa a tela dela diz
    qual controle. É a mesma porta que a coluna já usa (`_da_mesa`).
    """
    casa = _da_mesa(ctx, uniq)
    return str(casa.get("nome") or "")


def _textos_do_desfecho(brilho: float | None, apagando: bool) -> tuple[str, str]:
    """O par (assunto, frase feliz) daquele gesto — e os quatro saem da GTK.

    `_ASSUNTO_COR` / `_TOAST_COR_ENVIADA` para quem pinta, `_ASSUNTO_APAGAR` /
    `_TOAST_LIGHTBAR_APAGADA` para quem desliga. Os dois pares vivem em
    `app/actions/lightbar_actions.py` com a medição ao lado, e o `(N% de brilho)`
    é decisão registrada lá: *"é o que ela usa para saber que o seletor viajou
    junto"*. Digitar qualquer um deles aqui seria a segunda escrita da mesma
    frase — o defeito que a RADAR-01 mediu, duas superfícies do mesmo produto
    dizendo coisas diferentes sobre o mesmo evento.

    O PERCENTUAL É O QUE FOI ENVIADO. Com o brilho desconhecido o produto manda
    sem o campo e o daemon assume cheio; a tela diz 100%, que é o que saiu.

    ELAS SÃO PRIVADAS POR CONVENÇÃO DE NOME, e não por contrato — do mesmo jeito
    que `lightbar_actions` lê `footer_actions._lista_de_secoes`. Ver
    `sem_resposta_do_daemon`, que já carrega o mesmo relato.
    """
    from hefesto_dualsense4unix.app.actions import lightbar_actions

    if apagando:
        return (str(lightbar_actions._ASSUNTO_APAGAR),
                str(lightbar_actions._TOAST_LIGHTBAR_APAGADA))
    pct = 100 if brilho is None else round(brilho * 100)
    return (str(lightbar_actions._ASSUNTO_COR).format(pct=pct),
            str(lightbar_actions._TOAST_COR_ENVIADA).format(pct=pct))


def _escrever_a_cor(ctx: Contexto, p: Any, uniq: str,
                    rgb: tuple[int, int, int], *,
                    apagando: bool = False) -> None:
    """O CAMINHO ÚNICO de escrita de cor desta aba — com o brilho e com a frase.

    ELE É O `_aplicar_cor_no_controle` DA GTK, no que esta tela pode ter
    (`app/actions/lightbar_actions.py:881`). Duas coisas que faltavam, e as duas
    estavam medidas:

    **1. O BRILHO VIAJA JUNTO.** A linha era `p.led_set(rgb, uniq=uniq)`, sem o
    argumento — e o `_payload_led_set` só põe o campo quando ele é passado, então
    o `led.set` do daemon caía no default *"Ausente ou inválido -> assume 1.0"*
    (`ipc_handlers._handle_led_set`). Consequência na tela dela: a mesma coluna
    que mostra `50%` no trilho mandava a cor a 100%, e um clique num tom
    DESFAZIA o brilho que ela tinha escolhido na janela GTK — sem uma palavra.
    A GTK manda `brightness=self._current_brightness` em toda escrita
    (`lightbar_actions.py:944`); aqui o número sai de `brilho_do_controle`, que
    é o MESMO que a coluna imprime.

    **2. O DESFECHO SE LÊ DO CORPO DO DAEMON.** A porta era `led_set` (`bool`), e
    um `True` dele significa só *"o daemon respondeu"*. O corpo do `led.set`
    publica `aplicado_em`/`guardado_em` desde a APLICAR-VERDADE-01, e
    `led_set_detalhado` já os entregava — sem um chamador em `interface/` até
    hoje. Sem eles, um clique com o Modo Nativo ligado (o backend muta toda
    escrita de output) ou com o controle recém-saído da mesa saía **calado**: o
    piloto anotava "aplicou", a barra não mudava, e o segundo clique parecia o
    primeiro. É o defeito que esta casa nomeia como o mais caro.

    QUEM DECIDE A FRASE É `textos_de_aplicacao.frase_do_desfecho`, e só ele —
    `frase_do_envio` o chama e troca *"aplicado"* por *"enviada"* no ramo feliz,
    porque por Bluetooth o firmware ACEITA E IGNORA escritas de cor (a medição
    está em `_TOAST_COR_ENVIADA`, 330 mil escritas ignoradas com a barra
    apagada). Nada de texto nasce deste lado.

    POR QUE O `RuntimeError` NO RAMO DO GUARDADO, e ele não é "recusa": o único
    canal que esta tela tem para falar com quem clicou é o cartão do
    `hefesto_vivo._recusou_dizendo`, e ele só carrega `RuntimeError`. A GTK diz
    a mesma frase num toast neutro. Entre a frase no cartão e o silêncio, o
    silêncio é a mentira — quem clica conclui que a cor foi. **RELATO:** um
    canal de AVISO (nem recusa nem silêncio) no piloto resolveria isto para as
    dez abas; é `interface/hefesto_vivo.py`, fora do território deste arquivo.

    A COMPARAÇÃO É COM A FRASE FELIZ, e não com `aplicado_em`: quem lê os dois
    destinos é `frase_do_desfecho`, que conhece as QUATRO razões do daemon e a
    ordem entre elas — recusa explicada, aplicado, guardado, nada aconteceu.
    Reler `destinos_da_aplicacao` deste lado para decidir seria a segunda
    verdade sobre o mesmo payload, e é exatamente o que a ELO-MUDO-01 inverteu:
    *"antes a janela deduzia e o daemon era ignorado"*. Aqui a janela só
    pergunta *"a frase que saiu é a do caminho feliz?"* — e cala quando é.
    """
    from hefesto_dualsense4unix.app.actions.lightbar_actions import frase_do_envio

    brilho = brilho_do_controle(perfil.ativo(ctx.state.get("active_profile")), uniq)
    corpo = p.led_set_detalhado(rgb, brightness=brilho, uniq=uniq)
    if corpo is None:
        raise RuntimeError(sem_resposta_do_daemon())
    assunto, enviado = _textos_do_desfecho(brilho, apagando)
    frase = frase_do_envio(assunto, enviado, corpo,
                           _janela_do_desfecho(ctx, uniq, _nome_da_coluna(ctx, uniq)))
    if frase != enviado:
        raise RuntimeError(frase)


@gesto("04-iluminacao.html", "cor")
def cor(ctx: Contexto, o: dict[str, Any], p: Any) -> None:
    """Ela clicou num tom. A cor vai AO CONTROLE NA HORA.

    DECISÃO DELA, 01/09/2026: *"clicar na cor já deveria aplicar a cor no
    controle."* Isso decide o modelo da interface inteira, e não só deste botão:
    **o gesto age na hora**, e não junta mudanças num rascunho à espera de um
    "Aplicar".

    A GUI estável tem as duas rotas — o `led.set` direto e o
    `profile.apply_draft` do rascunho — e o próprio `on_lightbar_apply` chama a
    primeira de "a cor já acende ao soltar o seletor". Aqui a primeira é a
    regra, e o "Salvar Perfil" continua sendo o que grava.

    A CONVERSÃO NÃO MORA AQUI, e morava até 02/09/2026. A linha era::

        p.led_set(tuple(int(hexa[i:i + 2], 16) for i in (0, 2, 4)), uniq=uniq)

    Isso é `core/led_control.hex_to_rgb`, que já existia, que este arquivo já
    alcançava (ele importa `player_slot_color` do mesmo módulo) e que **RECUSA
    DIZENDO**: `ValueError` com a razão escrita — *"hex_to_rgb espera formato
    RRGGBB"*, *"componente não numérico"*.

    DUAS PORTAS PARA O MESMO GESTO, e a segunda é o seletor livre: os oito
    botões da guia trazem a cor em `data-hex`, e o `<input type="color">` a traz
    em `value`, que o ouvinte manda como `valor`.

    ABRIR O SELETOR NÃO É APLICAR — e esta é a razão de `_so_abriu_o_seletor`
    existir. Medido em 02/09/2026 com o BOOTSTRAP REAL avaliado dentro de um
    Chrome, com `window.webkit.messageHandlers` dublado::

        ela ABRE o seletor   {gesto:'cor', hex:'', valor:'#0000ff',
                              tipo:'input', evento:'click'}
        ela ESCOLHE a cor    {gesto:'cor', hex:'', valor:'#12ab34',
                              tipo:'input', evento:'change'}

    O ouvinte escuta `click` E `change`, e um `<input type="color">` dispara
    `click` no instante em que ela o ABRE — carregando o valor VELHO, que é a
    cor cravada no arquivo pelo gerador. Ler o `valor` nesse clique manda a
    barra dela para `#0000FF` (p1) ou `#FF0000` (p2) antes de ela escolher
    qualquer coisa; se ela CANCELAR, a barra fica na cor que ela nunca pediu.

    UM CONTROLE QUE AGE SEM ELA PEDIR é da mesma família do que aceita o toque e
    não age, e MUDA O APARELHO. O ato é o `change`; a abertura não é gesto
    nenhum, e por isso o gesto sai calado — recusar dizendo poria uma frase de
    erro na tela dela só por ela ter aberto um seletor.

    E O DESFECHO SE LÊ — 02/09/2026. A linha era `p.led_set(...)` sem olhar o
    retorno; ver `sem_resposta_do_daemon` para o que isso custava.

    E O BRILHO VIAJA JUNTO — 03/09/2026. Ver `_escrever_a_cor`: até aqui este
    gesto DESFAZIA o brilho dela a cada clique num tom.
    """
    from hefesto_dualsense4unix.core.led_control import hex_to_rgb

    uniq = _uniq(o)
    if not uniq:
        raise ValueError("cor: o clique não disse em qual controle")
    # O `data-hex` MANDA, e o `valor` é a queda: um botão da guia tem os dois
    # (o `value` de um `<button>` é vazio) e o seletor livre só tem o segundo.
    pedido = str(o.get("hex") or "")
    if not pedido:
        if _so_abriu_o_seletor(o):
            return
        pedido = str(o.get("valor") or "")
    _escrever_a_cor(ctx, p, uniq, hex_to_rgb(pedido))


@gesto("04-iluminacao.html", "apagar")
def apagar(ctx: Contexto, o: dict[str, Any], p: Any) -> None:
    """"Desligar": a barra vai a preto.

    NÃO é `lightbar.reset` — esse devolve a cor AUTOMÁTICA, que é o outro botão.
    Apagar e voltar ao automático são coisas diferentes, e o desenho dela as
    separa em dois botões de cores diferentes.

    E O DESFECHO SE LÊ, pelo mesmo motivo do `cor` — ver
    `sem_resposta_do_daemon`. Aqui o silêncio enganava mais: "Desligar" sem
    resposta deixa a barra ACESA, que é exatamente a cara de "não cliquei
    direito".

    O BRILHO VIAJA JUNTO E NÃO MUDA NADA AQUI — `int(0 * b)` é `0` para qualquer
    `b`. Ele vai assim mesmo porque o caminho de escrita é UM só
    (`_escrever_a_cor`); uma rota paralela "sem brilho" para o preto seria a
    segunda escrita da mesma cor, que é como as duas divergiriam depois.
    """
    uniq = _uniq(o)
    if not uniq:
        raise ValueError("apagar: o clique não disse em qual controle")
    _escrever_a_cor(ctx, p, uniq, (0, 0, 0), apagando=True)


@gesto("04-iluminacao.html", "auto")
def automatico(ctx: Contexto, o: dict[str, Any], p: Any) -> None:
    """"Automático": LARGAR a luz, para o jogo escolher a cor.

    DECISÃO DELA, 01/09/2026, e ela corrigiu a minha leitura: *"voltar ao
    automático nesse caso é deixar o jogo escolher."* Não é devolver a cor do
    número do jogador — é o Hefesto soltar o claim da barra.

    `lightbar.reset` é exatamente isso, e o `ipc_handlers.py:4159` diz com
    todas as letras: *"o 0x08 devolve o claim da lightbar ao host"*. O nome do
    método engana — o docstring dele começa chamando-o de INSTRUMENTO de
    medição — e foi por isso que eu quase o troquei por outra coisa. **O nome do
    método não diz o que ele faz; o handler diz.**

    A RESSALVA ESTÁ MEDIDA NO PRÓPRIO HANDLER e vale para a tela: *"a suspeita é
    que ele só TRAVA quando mandado dentro da janela de ~3,4 s pós-conexão"*.
    Fora dela o claim pode voltar sozinho. Quando alguém puder medir isso na
    tela, é aqui que a nota entra.

    E A BARRA NÃO FICA PRETA. Largar o claim sozinho deixa a última cor no
    plástico — e se a última foi um "Desligar", ela fica apagada, o que parece
    defeito. Ordem dela: *"deixa em uma das cores default se o jogo não escolher
    ou não tiver rodando."* Então o gesto larga E pinta a cor do slot, da
    paleta que o produto já tem.

    `lightbar.reset` não tem função no `ipc_bridge` — é o degrau 3 da ponte, e
    passa pelo mesmo `_safe_call`, com o mesmo timeout.
    """
    uniq = _uniq(o)
    if not uniq:
        raise ValueError("auto: o clique não disse em qual controle")

    # 1. LARGA O CLAIM — daí em diante quem manda na barra é o jogo.
    #
    #    E SE ELE NÃO FOR LARGADO, A SEGUNDA CHAMADA NÃO CORRE — 02/09/2026.
    #    O gesto seguia para o `led_set` mesmo com o `chamar` devolvendo
    #    `False`: a barra ganhava uma cor nova com o claim ainda no Hefesto, que
    #    é o OPOSTO do que este botão promete (*"deixar o jogo escolher"*), e
    #    sem uma palavra na tela. Medido com o dublê de ponte muda.
    if not p.chamar("lightbar.reset", uniq=uniq):
        raise RuntimeError(sem_resposta_do_daemon())

    # 2. E DEIXA A COR PADRÃO, para não ficar PRETO quando ninguém escreve.
    #    Ordem dela, 01/09/2026: *"deixa em uma das cores default se o jogo não
    #    escolher ou não tiver rodando"* — e *"o resto já deveria estar
    #    registrado e acho que está"*. Está: `core/led_control.player_slot_color`
    #    é o dono da paleta, a MESMA que acende as cinco lâmpadas.
    #
    #    NÃO SE DIGITA A COR AQUI. Ela sai da função, e muda no dia em que a
    #    paleta mudar — é a regra da casa: o que tem dono não se digita.
    from hefesto_dualsense4unix.core.led_control import player_slot_color

    # O NÚMERO SAI DO MOTOR, e não de uma queda escrita aqui. Esta linha era
    # `dele.get("player_slot") or dele.get("player") or 1` — a QUARTA cópia de
    # uma regra que tem dono (`app/actions/base.numero_do_controle`), e o `or 1`
    # dela era a POSIÇÃO disfarçada de default: um controle sem número nenhum
    # ganharia a cor do P1.
    #    E O BRILHO VIAJA JUNTO — 03/09/2026. A cor do slot é a IDENTIDADE, e o
    #    `core/led_control` diz isso com todas as letras: *"A cor daqui é a
    #    IDENTIDADE (pré-brilho, D8); quem escala pelo `lightbar_brightness` do
    #    perfil é o provider (D11)"*. Mandá-la sem o brilho fazia este botão
    #    acender a barra CHEIA num perfil de brilho reduzido — e ficar mais forte
    #    do que a cor automática que ele promete devolver.
    dele = ctx.por_uniq(uniq) or {}
    _escrever_a_cor(ctx, p, uniq,
                    player_slot_color(_numero(ctx, dele or {"uniq": uniq})))


@gesto("04-iluminacao.html", "player")
def player(ctx: Contexto, o: dict[str, Any], p: Any) -> None:
    """"Dar o Player N a este controle." `ipc_bridge.identity_number_set`.

    NÃO é `identity.renumber`, e a diferença está escrita no
    `app/ipc_bridge.py:712`: o `renumber` COMPACTA todos preservando a ordem
    relativa, e mora na aba Início. Dizer "este controle é o 2" foi o comando
    que faltou ao projeto até 25/07.

    A FUNÇÃO DEVOLVE `(ok, motivo)`, e o motivo já vem traduzido para frase de
    tela (`_MOTIVOS_NUMERO`): "O jogo está aberto", "Esse número é maior do que
    a quantidade de controles ligados". Levantar com ele é o que faz o botão
    RECUSAR DIZENDO em vez de falhar calado.
    """
    uniq = _uniq(o)
    try:
        n = int(str(o.get("player") or "0"))
    except ValueError:
        n = 0
    if not uniq or not 1 <= n <= 4:
        raise ValueError(f"player: preciso do controle e de um número 1..4 (veio {n})")
    ok, motivo = p.identity_number_set(uniq, n)
    if not ok:
        raise RuntimeError(motivo or "não consegui trocar o número")


#: AS FUNÇÕES DA PONTE QUE ESTA ABA USA. A régua confere que existem — um nome
#: inventado aparece aqui, e não na mão de quem clica.
#: A PORTA DA COR É A `_detalhado` DESDE 03/09/2026, e `led_set` saiu daqui: o
#: `bool` dela não carrega `aplicado_em`/`guardado_em`, e sem eles os três
#: gestos que escrevem cor diziam "aplicou" para um clique que não acendeu nada.
#: Ver `_escrever_a_cor`.
PONTE = {"led_set_detalhado", "identity_number_set", "chamar"}
METODOS = {"lightbar.reset"}


#: O QUE ESTA ABA DECLARA À RÉGUA — o piso e as provas moram AQUI, e não no
#: teste, para que ligar uma aba não exija editar um arquivo que oito pessoas
#: editariam ao mesmo tempo.
PAGINA = "04-iluminacao.html"
PISO_DA_ABA = 4
PROVAS = [
    {"pagina": PAGINA, "gesto": "cor", "clique": {"hex": "#FF8000"},  # (noqa-acento) id
     "chama": [("led_set_detalhado", [(255, 128, 0)],
                {"uniq": "aa:bb:cc:00:00:01"})]},
    {"pagina": PAGINA, "gesto": "apagar", "clique": {},  # (noqa-acento) chave do contrato
     "chama": [("led_set_detalhado", [(0, 0, 0)],
                {"uniq": "aa:bb:cc:00:00:01"})]},
    # DUAS chamadas, e a ordem importa: largar o claim e SÓ ENTÃO pintar.
    {"pagina": PAGINA, "gesto": "auto", "clique": {},  # (noqa-acento) chave do contrato
     "chama": [("chamar", ["lightbar.reset"], {"uniq": "aa:bb:cc:00:00:01"}),
               ("led_set_detalhado", [(0, 0, 255)],
                {"uniq": "aa:bb:cc:00:00:01"})]},
    {"pagina": PAGINA, "gesto": "player", "clique": {"player": "2"},  # (noqa-acento) id
     "chama": [("identity_number_set", ["aa:bb:cc:00:00:01", 2], {})]},
]
