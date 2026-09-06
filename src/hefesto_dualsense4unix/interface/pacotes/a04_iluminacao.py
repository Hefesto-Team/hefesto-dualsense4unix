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

#: A RAIZ DO ENDEREÇO DO ANELZINHO do dono, dentro de um botão da fileira.
#:
#: UM NOME PRÓPRIO, e nunca `players`: o pintor acha por
#: `[data-campo=X],[data-papel=X],[data-hef=X]` com `querySelectorAll`, então um
#: `<i>` que repetisse `players` receberia a fileira INTEIRA como `innerHTML`.
ANEL_DO_DONO = "players.dono"

#: O ALVO QUE ALCANÇA A COR DO PLÁSTICO — o mesmo que a moldura da `05-vibracao`
#: usa desde 03/09/2026. `escrever()` faz `el.style.setProperty('--plastico', …)`
#: e APAGA a variável no vazio, que é a regra dela: campo sem informação não
#: mostra nada.
ALVO_DO_PLASTICO = "plastico"


def endereco_do_anel(n: int) -> str:
    """O endereço do anel do dono do número ``n``, dentro de UMA coluna.

    POR QUE O NÚMERO ENTRA NO ENDEREÇO — 03/09/2026, e é o que fez este anel
    deixar de ser cor congelada. Os quatro anéis de uma coluna repetiam
    `players.dono`, e o pintor escreve por `querySelectorAll`: um valor só
    pintaria os quatro com a MESMA cor, quando cada um é de um dono diferente.
    Com o número no nome, o campo por controle (`colunas[uniq]`) endereça cada
    anel sozinho — e o `data-hef-alvo="plastico"` é o que o alcança.

    ERA ENDEREÇO SEM ALVO, E ISSO É METADE DE UMA FECHADURA. O `<i>` declarava
    `data-hef` e mais nada, contando com o pai (`data-campo="players"`, alvo
    `html`) para reescrevê-lo; a régua da identidade acusava, e acusava com
    razão pela letra dela — *"um pai endereçado não dá ao filho o direito de
    trazer cor congelada"*, porque `escrever()` escreve no elemento que ACHOU.
    Agora o anel tem os dois, e a régua do mockup vê o selo da visita nele.
    """
    return f"{ANEL_DO_DONO}.{int(n)}"


#: O ENDEREÇO DE UM ITEM DO ANTES/DEPOIS do rodapé — ver `item_da_troca`.
#:
#: ELE É UMA LISTA, e é o único jeito honesto: a seção desenha DOIS por controle
#: (a linha do ANTES e a do DEPOIS) e N muda com a mesa. O pintor distribui uma
#: lista pelos elementos de mesmo endereço, na ordem do documento — a mesma
#: forma com que a `08-conexoes` mostra os achados do exame.
ITEM_DA_TROCA = "troca.item"

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


def chave_do_override(uniq: str) -> str:
    """O `uniq` na forma em que o DISCO guarda a chave de `controllers`.

    UM DONO PARA O ENDEREÇO DO CONTROLE DENTRO DO PERFIL, e ele é o `norm_mac`
    do backend — o MESMO que `profiles/schema._validate_controllers_keys` usa
    para canonizar a chave na entrada. Escrever `d4:2f:…` onde o disco guarda
    `d42f…` criaria um segundo dono para o mesmo controle: o override que ela
    gravou pela tela e o que o backend enumera deixariam de ser o mesmo.

    POR QUE ELE PRECISOU EXISTIR AGORA: até 03/09/2026 esta aba só LIA o
    override (`brilho_do_controle`), e lia com a string crua. Isso funciona na
    mesa dela — medido no daemon vivo, o `state_full` publica
    `uniq='143a9a0000ab'`, já normalizado —, mas não é contrato: o `norm_mac`
    aceita as duas formas justamente porque as duas circulam, e a régua desta
    casa endereça com `aa:bb:cc:00:00:01`. Com o trilho passando a ESCREVER, ler
    numa forma e gravar noutra seria a divergência clássica: o brilho gravado no
    `aabbcc000001` e a coluna imprimindo o global, para sempre.

    `""` VOLTA `""` — quem decide o que fazer sem alvo é quem chamou (`_uniq`,
    que recusa dizendo). Inventar uma chave aqui gravaria no controle errado.
    """
    if not uniq:
        return ""
    from hefesto_dualsense4unix.core.sysfs_leds import norm_mac

    return norm_mac(uniq) or uniq


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
    #: OS DOIS LADOS PASSAM PELO DONO — ver `chave_do_override`. A comparação
    #: era `dict.get(uniq)`, string contra string, até 03/09/2026: funciona na
    #: mesa dela (o `state_full` publica `uniq='143a9a0000ab'`, já normalizado)
    #: e falha em toda outra forma do mesmo endereço. Com o trilho passando a
    #: ESCREVER — e a escrita tem de canonizar, porque é o que o esquema exige
    #: (`_validate_controllers_keys`) —, ler cru gravaria no `aabbcc000001` e
    #: imprimiria o global, para sempre.
    #:
    #: NORMALIZAR OS DOIS LADOS, e não só o de cá: as chaves do dicionário vêm
    #: do JSON, e um perfil editado à mão guarda `aa:bb:cc:…` — o próprio
    #: esquema aceita e canoniza essa forma na entrada.
    alvo = chave_do_override(uniq)
    meu = next((v for k, v in (p.get("controllers") or {}).items()
                if chave_do_override(str(k)) == alvo), None)
    seus = (meu.get("leds") or {}) if isinstance(meu, dict) else {}
    b = seus.get("lightbar_brightness", global_) if isinstance(seus, dict) else global_
    if b is None:
        return None
    try:
        return max(0.0, min(1.0, float(b)))
    except (TypeError, ValueError):
        return None


#: O ENDEREÇO DO INTERRUPTOR DO AUTOMÁTICO — D-13, 04/09/2026.
ENDERECO_DO_AUTOMATICO = "auto-cores"


def automatico_do_perfil(p: dict[str, Any] | None) -> bool:
    """O `leds.auto_player_colors` do perfil ativo — o martelo mais pesado da aba.

    ELE É **GLOBAL DO PERFIL**, e não por controle, e isso não é escolha minha:
    `profiles/schema.LedsConfig` diz, com todas as letras, que dentro de um
    override por-controle o campo *"é aceito pelo schema (reuso do modelo) mas
    ignorado — o toggle é do perfil, não do controle"*. Ler o override aqui
    inventaria uma camada que o backend não tem.

    A AUSÊNCIA É `True`, e o default também tem dono: `LedsConfig` declara
    `auto_player_colors: bool = True`, e o comentário de lá explica por quê — um
    perfil antigo sem o campo valida com o default, sem migração. Responder
    `False` na ausência faria a tela dizer DESLIGADO sobre trinta e três perfis
    dela que estão ligados.

    SEM PERFIL ATIVO A RESPOSTA TAMBÉM É `True`, e é o honesto: é o estado em
    que o produto nasce, e é o que o daemon aplica enquanto ninguém escolheu
    outra coisa.
    """
    if not isinstance(p, dict):
        return True
    leds = p.get("leds")
    if not isinstance(leds, dict) or "auto_player_colors" not in leds:
        return True
    return bool(leds.get("auto_player_colors"))


#: OS QUATRO GESTOS QUE NASCEM COM ELAS. Os nomes são o vocabulário do clique
#: (`data-gesto`), e ficam aqui em vez de digitados no gerador E no pacote: era
#: assim que o `ENDERECO_DO_AUTOMATICO` já vivia, e pela mesma razão.
GESTO_DA_LAMPADA = "luzes"
GESTO_DO_DESENHO_DE = "desenho-de"
GESTO_DO_REENVIO_DO_DESENHO = "reenviar-desenho"
GESTO_DO_AUTOMATICO_DE_TODOS = "auto-todos"

#: OS DOIS ATALHOS DO `desenho-de` QUE NÃO SÃO NÚMERO. "Todas apagadas" tem
#: significado no motor — desenho vazio quer dizer *"quem manda é o automático"*
#: —, e por isso ele não é enfeite do par (`lightbar_actions.py:1329`, `:1346`).
TODAS, NENHUMA = "todas", "nenhuma"


def desenho_gravado(p: dict[str, Any] | None, uniq: str) -> tuple[bool, ...] | None:
    """O `player_leds` que o perfil guarda para ESTE controle, ou `None`.

    **SÓ O OVERRIDE POR CONTROLE, e o global fica de fora de propósito.**
    `profiles/schema.LedsConfig` declara `player_leds: list[bool] =
    default_factory=lambda: [False] * 5` — todo perfil desta casa tem o campo
    global preenchido com cinco falsos **sem ninguém ter escolhido isso**. Lê-lo
    como escolha faria a tela afirmar *"as cinco apagadas"* em trinta e três
    perfis dela, e o gesto do reenvio mandaria o preto ao aparelho. O override
    por-`uniq`, ao contrário, é serializado com `exclude_unset`
    (`_com_o_desenho_gravado` diz onde), então a PRESENÇA da chave é a prova de
    que alguém escreveu.

    **É A ÚNICA FONTE VIVA QUE ESTA TELA TEM**, e isso está medido e escrito no
    vizinho `dica_da_luz`: o `state_full` publica, por controle, exatamente as
    chaves de `daemon/ipc_handlers._enrich_controllers_per_controller` —
    `lightbar_rgb`, `lightbar_on`, `player_slot`, `inputs`… — e **nenhum campo
    do desejado**. `aba02.py:1071` já dizia isso com todas as letras (*"publica
    o ``player_slot`` e NÃO publica ``player_leds``"*). Por isso o gesto das
    lâmpadas GRAVA no perfil além de escrever no fio: sem a gravação, o tique
    seguinte repintaria o padrão do número por cima da escolha dela, e o clique
    pareceria não ter funcionado.

    A CHAVE PASSA PELO DONO nos dois lados (`chave_do_override`) — a mesma cura
    que `brilho_do_controle` documenta, e pela mesma razão: as chaves vêm do
    JSON e um perfil editado à mão guarda `aa:bb:cc:…`.
    """
    if not isinstance(p, dict) or not uniq:
        return None
    alvo = chave_do_override(uniq)
    meu = next((v for k, v in (p.get("controllers") or {}).items()
                if chave_do_override(str(k)) == alvo), None)
    seus = (meu.get("leds") or {}) if isinstance(meu, dict) else {}
    bits = seus.get("player_leds") if isinstance(seus, dict) else None
    if not isinstance(bits, (list, tuple)) or len(bits) != 5:
        return None
    return tuple(bool(x) for x in bits)


#: A FOLHA QUE A BOTOEIRA PRECISA PARA NÃO SAIR NUA — LUZES-01, 06/09/2026.
#:
#: O QUE ESTA GUARDA IMPEDE, e ela nasceu de um risco MEDIDO, não previsto: o
#: bloco das cinco lâmpadas viaja pelo alvo `html` do campo `luz`, e esse
#: endereço **já está PUBLICADO**. Sem a guarda, o primeiro tique do produto
#: injetaria as doze teclas na página de ontem — que não tem uma linha de
#: `.pad .lamp` nem de `.desenhos` — e ela veria botões sem forma nenhuma na
#: célula LEDs, antes de aprovar o desenho. É o mesmo tempo descompassado que
#: `a_pintura_alcanca_o_desenho` já resolve para o colorway, e a resposta é a
#: mesma: **enquanto a página publicada não souber pintar, não emita.**
#:
#: A PERGUNTA É PELA FOLHA, e não pelo endereço: aqui não há `data-campo` novo a
#: procurar — o bloco entra por um endereço que já existe. O que separa o
#: publicado do que a bancada tem é a FOLHA, então é ela que se pergunta.
#: FALHA FECHADA, como a irmã: qualquer coisa que não se reconheça vira
#: "não emita".
_PEDE_A_BOTOEIRA = (".pad .lamp{", ".desenhos .dz{")

_PINTA_A_BOTOEIRA: bool | None = None


def a_folha_alcanca_a_botoeira() -> bool:
    """A página PUBLICADA sabe desenhar as doze teclas das luzes de jogador?

    Ver `_PEDE_A_BOTOEIRA`. `publicado=True` é deliberado e é o mesmo da irmã: o
    piloto abre SEMPRE o publicado, e é lá que a folha tem de estar.
    """
    global _PINTA_A_BOTOEIRA
    if _PINTA_A_BOTOEIRA is None:
        from hefesto_dualsense4unix.interface import onde

        try:
            pagina = onde.pagina(PAGINA, publicado=True).read_text(encoding="utf-8")
        except OSError:
            pagina = ""
        _PINTA_A_BOTOEIRA = all(p in pagina for p in _PEDE_A_BOTOEIRA)
    return _PINTA_A_BOTOEIRA


def desenho_de_agora(cru: dict[str, Any] | None, uniq: str,
                     numero: int) -> tuple[bool, ...]:
    """O desenho que ESTE controle está exibindo — na ordem do merge, até onde a tela vê.

    A ordem inteira é do backend (`core/backend_pydualsense._merged_desired_for_key`)::

        default global  <  camada AUTOMÁTICA  <  override por-uniq  <  co-op  <  jogo

    **DESTA TELA SÓ SE VEEM DUAS**, e a função diz exatamente essas duas:
    o override por-`uniq` do perfil (`desenho_gravado`), e — na falta dele — a
    camada automática, que é `core/led_control.player_led_pattern(numero)`, a
    MESMA tabela que o daemon acende e a mesma que `monta.luzinhas` desenha.

    O CO-OP E O JOGO FICAM DE FORA, e a ausência é declarada: com o co-op ligado
    quem escreve as cinco luzes é a camada dele, e `o_coop_manda` já é quem diz
    isso — é por isso que o banco nasce APAGADO nesse caso (ver `banco_de_luzes`),
    em vez de afirmar um desenho que não é o que está no plástico. É a mesma
    regra dela que `dica_da_luz` cita: *"se não tá mostrando agora, não tem info
    pra mostrar no produto"*.

    NADA DE TABELA DIGITADA: o padrão sai do dono. Uma segunda cópia dela é a
    espécie de segunda verdade que esta casa persegue desde 27/08 — e ela já
    custou, uma vez, quatro botões da GTK pintando o desenho antigo sem um único
    teste vermelho (`aplicar_desenho_do_jogador`, L9).
    """
    from hefesto_dualsense4unix.core.led_control import player_led_pattern

    gravado = desenho_gravado(cru, uniq)
    if gravado is not None:
        return gravado
    try:
        return tuple(bool(x) for x in player_led_pattern(int(numero)))
    except (TypeError, ValueError):
        return (False,) * 5


#: O NOME DO TRILHO PARA QUEM NÃO VÊ A TELA. O `aria-label` é a única coisa que
#: um leitor de tela anuncia num `<input type="range">` sem rótulo próprio — a
#: linha "Brilho" da primeira coluna é uma célula de grid, não um `<label>`.
ROTULO_DO_BRILHO = "Brilho da barra de luz deste controle"

#: A DICA DO TRILHO, e ela diz A CONSEQUÊNCIA — decisão dela, 03/09/2026:
#: perguntada se mexer no brilho grava o perfil na hora ou espera o "Salvar
#: Perfil", ela respondeu **"Grava na hora"**. Um gesto que escreve no disco
#: dela sem dizer que escreve é a metade do defeito que esta casa mais paga; a
#: outra metade é o botão que aceita o toque e não age, que era o que este
#: trilho fazia até hoje.
#:
#: ELA NÃO NOMEIA O PERFIL, e a razão é o canal: `title` é ATRIBUTO, e o gerador
#: só sabe o que sabia quando gerou. Uma frase com o nome do perfil ficaria
#: CONGELADA no nome de hoje na tela dela para sempre — é a mesma armadilha que
#: tirou a dica da célula `LEDs` do desenho, em 02/09.
DICA_DO_BRILHO = ("Arraste para mudar o brilho da barra deste controle. "
                  "Ao soltar, a barra acende no brilho novo e o valor é "
                  "gravado no perfil ativo — não espera o Salvar Perfil.")


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

#: O ENDEREÇO DA LINHA QUE DIZ **POR QUÊ** — D-02, e a decisão [01] desta aba em
#: 04/09/2026: *"Uma linha só quando há ressalva."*
#:
#: O TRACEJADO AVISA QUE ALGO MUDOU E NÃO DIZ O QUÊ. As três causas — o jogo é
#: dono do LED em Modo Nativo, a Steam está com o `fd` deste controle, ou a cor
#: é desconhecida — saem do MESMO motor que o `ENDERECO_DA_INCERTA` já consulta
#: (`controller_card.rotulo_lightbar`), e até hoje viajavam só no `title` das
#: tiras: some para quem não passa o rato. Aqui elas ganham linha.
#:
#: ELE É SEPARADO DO `luz` de propósito, e a razão é a mesma que criou o
#: `ENDERECO_DA_INCERTA`: o `luz` é alvo `html` e troca o miolo do `.aceso`
#: inteiro a cada tique. Uma frase escrita lá dentro seria destruída e recriada
#: com o desenho, e nenhuma régua a leria — os alvos `html` são lidos pelo TEXTO
#: visível, e o que se lê ali é o desenho, que não tem texto.
ENDERECO_DA_RESSALVA = "luz-ressalva"

#: "NÃO HÁ O QUE DIZER", dito de um jeito que a tela sabe APAGAR — o mesmo
#: marcador de `monta.NADA_A_DIZER`, e o mesmo motivo: `escrever()` troca valor
#: vazio por travessão, de propósito, e numa linha de ressalva isso vira um `—`
#: solto, que é ruído com cara de dado.
#:
#: A CHAVE CONTINUA SENDO EMITIDA em todo tique: é o que faz a linha SUMIR
#: quando a ressalva acaba. Omiti-la deixaria a frase velha na tela para sempre.
#:
#: DUAS CÓPIAS DO MESMO LITERAL, e é assim de propósito: importar `monta` de
#: dentro de um pacote puxaria o desenho inteiro (a mesa do mockup, o SVG, o
#: CSV das cores) para dentro de um módulo que tem de importar sem janela e sem
#: bancada. A `a06_navegacao` já convive com a mesma cópia, e a régua
#: `test_a_linha_de_ressalva_so_nasce_quando_ha` compara as duas para que não
#: divirjam caladas; a desta aba é comparada em
#: `test_a_aba_04_iluminacao_fecha_as_linhas`.
NADA_A_DIZER = '<i class="nada"></i>'


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
    do desejado; `interface/aba02.py:1071` já dizia isso com todas as letras
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

        # `cor_de_css` E NÃO `cor_da_zona` — 03/09/2026. Oito dos 28 modelos
        # dela não têm hexa amostrado e devolvem `url(#hachura-sem-hex)`, que
        # o CSSOM RECUSA EM SILÊNCIO num campo de cor — e o que ficava na
        # tela era o Cosmic Red do MOCKUP, sob um desenho que dizia outro
        # modelo. Ver a razão inteira em `monta.cor_de_css`.
        return str(monta.cor_de_css(slug))
    except Exception:
        # `cor_da_zona` levanta `SystemExit` para colorway que o SVG não tem.
        # Derrubar a pintura da aba por causa de um modelo novo seria trocar um
        # anel que falta por uma tela congelada.
        return ""


def fora_da_mesa() -> str:
    """A frase com que o produto RECUSA um número acima da mesa.

    DONO ÚNICO, e é por isso que ela é importada em vez de digitada:
    `app/ipc_bridge._MOTIVOS_NUMERO["numero_fora_da_mesa"]` já é a frase que a
    janela mostra quando `identity_number_set` recusa. Digitá-la aqui seria a
    segunda cópia de um texto de tela — e texto de tela é DELA; duas cópias são
    duas frases que podem divergir sem ninguém ver.

    O NOME É PRIVADO NO OUTRO MÓDULO e mesmo assim é ele que se lê: a
    alternativa era CLICAR para saber o motivo, que é exatamente o defeito que
    esta leitura existe para fechar. O import é TARDIO pela mesma razão que o
    do `hex_to_rgb` nos gestos — o pacote é carregado pelo gerador, que não
    tem daemon nem ponte.
    """
    from hefesto_dualsense4unix.app.ipc_bridge import _MOTIVOS_NUMERO

    return _MOTIVOS_NUMERO["numero_fora_da_mesa"]


def um_botao_de_player(nome: str, meu: int, n: int,
                       dono: dict[str, Any] | None, *, quantos: int) -> str:
    """Um número, na coluna de UM controle: dá-lo a este troca-o com o dono.

    ESTA FUNÇÃO TEM DOIS CHAMADORES E UM DONO. O gerador `aba04.py` a chama para
    desenhar a bancada; o pacote a chama a cada tique para pintar a fileira
    viva. Enquanto eram duas escritas, o botão do desenho e o botão do produto
    podiam divergir sem ninguém ver — e é o mesmo defeito que deixou a
    `novo-layout/` divergir 25 KB calada.

    O DONO SÓ EXISTE SE ELE ESTIVER NA MESA — 31/08/2026. O `title` dizia *"o
    Galactic Purple, que tem o 3 hoje"* com o Galactic Purple DESCONECTADO. Ele
    não tem o 3 hoje; ele não tem nada hoje.

    SÃO QUATRO ESTADOS, E A TELA MOSTRAVA DOIS — ver `ANEL_INCERTO`:

        livre          ninguém tem este número      sem anel
        tomado         e eu sei a cor do dono       anel cheio, na cor do plástico
        tomado, sem cor  o dono está aqui, a cor não chegou  anel TRACEJADO
        fora da mesa   não há controles bastante    apagado, e a dica diz por quê

    O terceiro caía no primeiro, e a diferença viajava só no `title`.

    O QUARTO NASCEU DE UM CLIQUE — 03/09/2026, medido no produto instalado com
    UM controle no cabo. A dica dizia **"Player 3 — livre."**, o botão era
    idêntico ao 1 (`disabled:false`, `cursor:pointer`, mesma borda), e clicar
    devolvia `RuntimeError: Esse número é maior do que a quantidade de controles
    ligados`. *Livre* quer dizer disponível; o número não estava disponível. A
    tela AFIRMAVA o contrário do que o produto faria — e com `quantos=1` isso
    valia para TRÊS dos quatro botões da fileira.

    `quantos` É A MESA, NÃO OS DONOS, e a distinção é o que faz a conta bater
    com a do daemon: quem recusa compara o número com **quantos controles estão
    ligados**, e `donos` só tem os que têm item de mesa. Contar `donos` diria
    "fora da mesa" a um número que o produto aceitaria.

    É KEYWORD-ONLY e SEM PADRÃO de propósito: um padrão faria o chamador que
    esquecesse voltar calado ao estado que este parágrafo descreve.
    """
    cor = _cor_do_plastico(str(dono.get("cor") or "")) if dono else ""
    #: O ENDEREÇO E O ALVO ANDAM JUNTOS — endereço sem alvo é meia fechadura, e
    #: era o que este anel tinha. Ver `endereco_do_anel`.
    onde = (f'data-hef="{endereco_do_anel(n)}" '
            f'data-hef-alvo="{ALVO_DO_PLASTICO}"')
    if dono is None:
        anel = ""
    elif cor:
        anel = f'<i class="dono" {onde} style="--plastico:{cor}"></i>'
    else:
        anel = f'<i class="dono incerta" {onde} style="{ANEL_INCERTO}"></i>'
    #: FORA DA MESA é o número que o daemon recusaria, e ele NÃO é "livre": um
    #: número tomado continua sendo o que a dica de troca descreve, mesmo acima
    #: da conta, porque quem tem dono está ligado.
    fora = dono is None and n > quantos
    if n == meu:
        dica = f"O {nome} É o Player {n} — é o número dele hoje."
    elif fora:
        dica = f"Player {n} — {fora_da_mesa()}."
    elif dono is None:
        dica = f"Player {n} — livre."
    else:
        dica = (f"Dar o Player {n} ao {nome}: o {dono['nome']} ({dono['via']}), "
                f"que tem o {n} hoje, fica com o {meu}. Os dois trocam de "
                f"lugar — ninguém repete número e ninguém fica sem.")
    #: O BOTÃO CONTINUA CLICÁVEL, e isso é escolha. `disabled` calaria a recusa:
    #: quem clicar mesmo assim tem de ouvir o motivo, que é a regra desta casa
    #: (*"vira botão que recusa dizendo"*). `aria-disabled` diz o estado a quem
    #: lê a tela por leitor, e a classe `fora` é o que os olhos leem.
    marca = " ".join(x for x in ("on" if n == meu else "", "fora" if fora else "") if x)
    #: MONTADO FORA DA `f-string`, e não por gosto: `f'{"a\"b" if x else ""}'`
    #: é SyntaxError em 3.10 e 3.11, e o `pyproject` pede `>=3.10`. A venv desta
    #: bancada é 3.12 e engoliu a primeira escrita calada.
    aria = ' aria-disabled="true"' if fora else ""
    return (f'<button class="{marca}"{aria} '
            f'data-gesto="player" data-player="{n}" title="{dica}">{anel}{n}</button>')


def fileira_de_players(nome: str, meu: int, donos: dict[int, dict[str, Any]],
                       recuo: str = "", *, quantos: int) -> str:
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

    `quantos` ATRAVESSA — ver `um_botao_de_player`, onde está a medição.
    """
    return "\n".join(recuo + um_botao_de_player(nome, meu, n, donos.get(n),
                                                quantos=quantos)
                     for n in NUMEROS)


#: O QUE CADA UMA DAS SEIS TECLAS DE DESENHO FAZ, na língua da tela.
#:
#: A PALAVRA "número" APARECE EM TODAS, e é o ponto inteiro desta sprint: os
#: botões `1 2 3 4` da linha Jogador e as teclas `P1..P4` desta linha **parecem a
#: mesma coisa e são opostos**. A janela GTK já dizia isso no próprio `title`
#: (*"Não muda o número deste controle"*), e a frase vem daí — não de mim.
#:
#: NENHUMA NOMEIA UM CONTROLE, e a razão é o canal: `title` é ATRIBUTO, e o
#: pintor não tem alvo para atributo (`hefesto_vivo.escrever`). Uma frase com o
#: nome do plástico ficaria congelada no que o gerador soube — é a armadilha que
#: tirou a dica da célula `LEDs` do desenho em 02/09, e que os oito botões de
#: `tom` já pagaram.
_DICA_DO_DESENHO_DE = ("Dá a este controle o desenho de luzes do Player {n} — "
                       "e NÃO muda o número dele.")
_DICA_DE_TODAS = "Acende as cinco luzes de jogador deste controle."
#: A SEGUNDA METADE NÃO É ENFEITE — `lightbar_actions.py:1346`, e o motor a
#: declara: desenho vazio quer dizer *"quem manda é o automático"*. É o ÚNICO
#: caminho de volta que esta tela tem, porque um override por-`uniq` PRENDE as
#: cinco lâmpadas acima da camada automática no merge do backend (a medição está
#: em `_acender_o_numero`).
_DICA_DE_NENHUMA = ("Apaga as cinco e devolve as luzes de jogador ao "
                    "automático — o número volta a mandar nelas.")
#: A DICA DA LÂMPADA. Ela diz o que o clique FAZ e o que ele NÃO faz, porque a
#: segunda metade é a queixa que abriu a sprint: até hoje toda escrita de lâmpada
#: vinha de carona numa renumeração.
_DICA_DA_LAMPADA = ("Acende ou apaga a luz {n} deste controle, sem mudar o "
                    "número dele.")
#: E A DO REENVIO — o gêmeo da caixa `#RRGGBB`, que é botão desde a decisão [03]
#: dela: *"A caixa do hexadecimal vira o botão."* O mesmo desenho que está na
#: tela volta ao aparelho, e serve depois de reconectar o controle ou trocar de
#: perfil (`lightbar_actions.on_player_leds_apply`).
DICA_DO_REENVIO_DO_DESENHO = ("Manda este desenho ao controle de novo — o "
                              "mesmo que está aceso aqui.")


def _lampada(n: int, acesa: bool) -> str:
    """Uma das cinco luzes de jogador, CLICÁVEL.

    `aria-pressed` E NÃO `checked`: é um `<button>` de dois estados, e é isso que
    um leitor de tela precisa ouvir. O olho lê a classe `on`, que é a MESMA que
    `monta.CSS_LUZINHAS` já usa para a lâmpada acesa do indicador — um par de
    cores, um dono (ver `token_das_luzinhas`).
    """
    marca = ' class="lamp on"' if acesa else ' class="lamp"'
    return (f'<button{marca} data-gesto="{GESTO_DA_LAMPADA}" data-lampada="{n}"'
            f' aria-pressed="{"true" if acesa else "false"}"'
            f' title="{_DICA_DA_LAMPADA.format(n=n)}"></button>')


def _tecla_de_desenho(qual: str, bits: tuple[bool, ...], dica: str,
                      rotulo: str = "") -> str:
    """Uma tecla de desenho: os quatro números, "todas" e "nenhuma".

    **OS QUATRO NÚMEROS DIZEM `P1`..`P4` E OS DOIS ATALHOS MOSTRAM O DESENHO**, e
    a divisão é medida, não de gosto. A coluna tem 220px e as doze teclas desta
    célula cabem em 212 com rótulos de 17px; escrever "Todas" e "Nenhuma" por
    extenso pedia 236 e estourava a coluna — mas `P1`..`P4` cabem, e são a
    palavra que o glossário desta casa manda usar. Os dois atalhos, que não têm
    palavra curta, mostram o que vão acender: cinco pontinhos cheios e cinco
    vazios. O `title` diz tudo por extenso nos seis, que é onde esta aba põe
    explicação desde 28/08.

    O DESENHO NÃO SE DIGITA — quem o produz é `player_led_pattern` do lado de
    quem chama, e aqui ele só vira pontinhos.
    """
    dentro = rotulo or "".join('<i class="on"></i>' if b else "<i></i>"
                               for b in bits)
    marca = ' class="dz num"' if rotulo else ' class="dz"'
    return (f'<button{marca} data-gesto="{GESTO_DO_DESENHO_DE}"'
            f' data-desenho="{qual}" title="{dica}">{dentro}</button>')


def banco_de_luzes(bits: tuple[bool, ...], coop_manda: bool = False) -> tuple[str, str]:
    """As cinco luzes de jogador e as seis teclas de desenho de UMA coluna.

    **UM DONO, DOIS CHAMADORES** — a mesma disciplina de `fileira_de_players` e
    `desenho_da_luz`: o gerador `aba04.py` desenha a bancada com esta função e o
    pacote pinta o produto com ela a cada tique. Enquanto fossem duas escritas, o
    desenho e o produto poderiam divergir sem ninguém ver.

    **É UM BLOCO DE ALVO `html`, e não onze endereços**, pela razão que
    `fileira_de_players` já mediu: o que muda com o dado é QUAL lâmpada está
    acesa — uma CLASSE — e o pintor só sabe escrever classe onde há endereço
    próprio. Trocar o bloco inteiro é o degrau que a fita, o mapa do gabinete e a
    fileira de números já usam, e o ouvinte de clique é delegado no documento
    (`hefesto_vivo.manda_do_alvo`), então trocar o HTML não desliga botão nenhum.

    **NENHUM `data-controle` NASCE AQUI, e a omissão é medida.** O clique resolve
    o dono por `alvo.closest('[data-controle],[data-uniq]')`, e o `<svg>` do
    desenho grande carrega `data-controle="dualsense"` — o MODELO, não o assento.
    Um alvo clicável posto dentro do SVG chegaria ao Python dizendo que o
    controle se chama `dualsense`. Este bloco mora na célula `.cel-luzes`, irmã
    do `.moldura`, e o `closest` sobe direto ao `.ctrl[data-controle="p1"]`.

    **COM O CO-OP LIGADO O BANCO NASCE APAGADO E A TECLA `on` NÃO ACENDE**, e é a
    mesma honestidade de `dica_da_luz`: quem escreve as cinco luzes nesse caso é
    a camada do co-op, que está ACIMA do override no merge — o que esta tela
    guarda não é o que está no plástico. Afirmar um desenho aqui seria a tela
    dizendo o contrário do fio, que é o defeito que a MESA-CHEIA-09 mediu.

    :param bits: o desenho de agora, de `desenho_de_agora` — cinco booleanos.
    :param coop_manda: `o_coop_manda(ctx.state)`. Ver acima por que ele muda o
        que se AFIRMA, e não o que se oferece: as teclas continuam clicáveis, e
        quem recusa dizendo é o gesto.
    :return: o par `(lâmpadas, teclas)` — as cinco vão DENTRO do `.pad`, que é a
        moldura do reenvio, e as seis ao lado dele. `desenho_da_luz` é quem os
        monta na `.aceso`; devolver os dois separados é o que permite ao `.pad`
        continuar sendo UM alvo clicável com cinco alvos dentro.
    """
    from hefesto_dualsense4unix.core.led_control import player_led_pattern

    mostra = (False,) * 5 if coop_manda else tuple(bits)[:5]
    lampadas = "".join(_lampada(n, mostra[n - 1]) for n in (1, 2, 3, 4, 5))
    teclas = "".join(
        _tecla_de_desenho(str(n), tuple(player_led_pattern(n)),
                          _DICA_DO_DESENHO_DE.format(n=n), rotulo=f"P{n}")
        for n in NUMEROS)
    teclas += _tecla_de_desenho(TODAS, (True,) * 5, _DICA_DE_TODAS)
    teclas += _tecla_de_desenho(NENHUMA, (False,) * 5, _DICA_DE_NENHUMA)
    return lampadas, f'<span class="desenhos">{teclas}</span>'


def desenho_da_luz(tinta: str, brilho: float, jogador: int, dica: str = "",
                   recuo: str = "", estado: str = "",
                   bits: tuple[bool, ...] | None = None,
                   coop_manda: bool = False) -> str:
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
    #: A BOTOEIRA SUBSTITUIU O INDICADOR — LUZES-01, 06/09/2026. As cinco
    #: lâmpadas continuam MOSTRANDO o desenho e passaram a poder MUDÁ-LO; e a
    #: `KeyError` de `monta.luzinhas` foi embora junto, porque
    #: `desenho_de_agora` pergunta a `core/led_control.player_led_pattern`, que
    #: responde a qualquer número (o `monta.PADRAO_JOGADOR` só precomputa 1..8).
    #: A cura de fundo continua relatada e continua sendo de `monta.py`.
    if bits is not None:
        lampadas, teclas = banco_de_luzes(tuple(bits), coop_manda=coop_manda)
        frase = " · ".join(x for x in (dica, DICA_DO_REENVIO_DO_DESENHO) if x)
        #: A BARRA É UM GRUPO, e as teclas são outro — ver a folha (`aba04.CSS`,
        #: `.aceso .barra`). Sem o grupo, os três vãos de 16px da `.aceso`
        #: somavam 48 e as duas tiras de luz encolhiam a ZERO: elas não tinham
        #: `flex-shrink:0`, e num flex apertado a largura é um pedido.
        return "\n".join(recuo + linha for linha in (
            '<span class="barra">',
            "  " + tira % "esq",
            f'  <span class="pad reenvia"'
            f' data-gesto="{GESTO_DO_REENVIO_DO_DESENHO}" title="{frase}"'
            f'>{lampadas}</span>',
            "  " + tira % "dir",
            "</span>",
            teclas,
        ))
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
    #: O RAMO SEM `bits` É O DA BANCADA VELHA e o das outras chamadas que ainda
    #: não sabem o desenho: indicador de leitura, sem gesto nenhum. Ele fica
    #: porque um lugar sem desenho conhecido não pode oferecer um clique que
    #: mandaria ao aparelho o padrão de um número que talvez não seja o dele.
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


#: O GRUPO DA BARRA e os cinco `<rect>` do indicador, DENTRO do desenho grande.
#: A âncora é o SUFIXO do `id`, e não a posição inteira: `monta.svg` prefixa todo
#: `id` com o nome do lugar (`il-p1-lightbar` aqui, `jg-p1-lightbar` na Jogar), e
#: um seletor com o prefixo escrito envelheceria no dia em que ele mudasse.
ALVO_DA_BARRA = '[id$="-lightbar"]'
ALVO_DAS_LAMPADAS = '[id*="-led-jogador-"]'

#: O DESLIGADO DA BARRA é `initial`, e não um cinza escrito aqui. Uma
#: propriedade personalizada em `initial` fica *guaranteed-invalid*, e é isso que
#: faz o `fill:var(--luz,var(--luz-apagada))` da folha cair no SEGUNDO argumento
#: — o mesmo caminho de uma coluna que nasce sem `--luz`. Escrever um hexadecimal
#: aqui seria um segundo "apagado" ao lado do que a aba já declara, e o
#: `drop-shadow(… var(--luz))` continuaria aceso em volta de uma barra apagada.
BARRA_APAGADA = "initial"

#: O CINZA DE UMA BARRA SEM LUZ — o valor que o CSS do gerador declara em
#: `.luzes,.troca`. Ele NÃO é redeclarado por este pacote: `.luzes` é o quadro
#: que ENVOLVE a `.luz-grade` (medido no HTML publicado, linhas 1643 e 1658), e
#: variável de CSS herda para baixo, então a barra do desenho sempre a alcançou.
#:
#: FATO ERRADO, SUBSTITUÍDO no mesmo dia em que foi escrito (03/09/2026): a
#: primeira volta desta cura afirmou que o `--luz-apagada` tinha a mesma doença
#: das lâmpadas e acrescentou `.luz-grade` ao seletor. A MORDIDA desmentiu — com
#: as declarações arrancadas, a barra continuou no `(63, 67, 80)` deste valor, e
#: só as lâmpadas caíram. Ele está aqui porque o ENSAIO precisa perguntar a
#: alguém qual é o cinza do apagado, e não para ser declarado de novo.
LUZ_APAGADA = "#3f4350"

#: A GRADE DA ABA — o escopo em que o desenho grande mora, e o que faltava às
#: duas cores das lâmpadas. Ver `token_das_luzinhas`.
ESCOPO_DO_DESENHO = ".luz-grade"


def token_das_luzinhas(nome: str) -> str:
    """O valor de um token do `CSS_LUZINHAS` — PERGUNTADO a ele, nunca digitado.

    POR QUE ESTA FUNÇÃO PRECISOU EXISTIR, e a medição está no DOM vivo de
    03/09/2026, na mesa dela, com o produto instalado e UM controle no cabo
    (``ensaios/a_luz_do_desenho_e_a_luz_do_aparelho.py``)::

        as cinco lâmpadas do DESENHO GRANDE do P1, número 1   nenhuma acesa

    `--led-apagado` e `--led-aceso` são declarados em `.luzinhas`
    (`monta.CSS_LUZINHAS`), que é o indicador PEQUENO da célula LEDs. As regras
    do desenho — `.luz-grade [id*="-led-jogador-"]` e `.luz-grade .led-on` —
    usam o mesmo par, e um `<rect>` dentro do SVG **não é descendente de
    `.luzinhas` nenhum**: as duas variáveis chegam lá vazias, o
    `fill:var(--led-aceso)` fica inválido no tempo de computar e a lâmpada herda
    o cinza do casco. As cinco saíam iguais — com o `title` da moldura
    prometendo que *"as cinco lâmpadas dizem qual é [o número]"*.

    É O DEFEITO QUE O PRÓPRIO `CSS_LUZINHAS` JÁ TINHA PAGADO, um andar acima:
    *"Um bloco reusável que depende de um seletor da aba que o pariu não é
    reusável"*. Esta aba o repetiu ao usar os tokens fora do seletor deles.

    A CURA NÃO É DIGITAR OS DOIS HEXADECIMAIS. Duas cópias divergem no primeiro
    ajuste, e a lâmpada pequena e a grande da MESMA célula passariam a ter dois
    brancos. O dono do par é o `CSS_LUZINHAS`; esta função o LÊ.

    FALHA FECHADA, como o `_cores_do_mapa` do gerador: um token que sumir do dono
    levanta com o nome dele, em vez de devolver uma folha que apaga a lâmpada de
    novo — que é o estado que ninguém viu por semanas.
    """
    import re

    import monta  # o `pacotes/__init__` põe `interface/` no `sys.path`

    achado = re.search(rf"{re.escape(nome)}\s*:\s*([^;}}]+)", monta.CSS_LUZINHAS)
    if achado is None:
        raise SystemExit(
            f"ERRO em 04-iluminacao: `{nome}` sumiu do `monta.CSS_LUZINHAS` — o "
            f"desenho grande lê de lá o par de cores das lâmpadas.")
    return achado.group(1).strip()


def tokens_da_luz() -> str:
    """As duas cores das lâmpadas, declaradas onde o DESENHO as alcança.

    UM DONO, DOIS CHAMADORES — a mesma disciplina da `fileira_de_players`. O
    gerador as põe na folha da página, que é o que a bancada precisa para se ver
    sozinha, sem daemon; este pacote as põe na folha VIVA, porque a página
    PUBLICADA ainda não as tem — e o publicado é o que está na tela dela hoje.
    Duas escritas do mesmo par dariam dois brancos na mesma célula.

    O `--luz-apagada` NÃO ENTRA, e a mordida é que decidiu: ver `LUZ_APAGADA`.
    """
    return (f"{ESCOPO_DO_DESENHO}{{"
            f"--led-apagado:{token_das_luzinhas('--led-apagado')};"
            f"--led-aceso:{token_das_luzinhas('--led-aceso')}}}")


def folha_da_luz(luzes: dict[str, tuple[str, int | None]],
                 caixa: str = CAIXA_DA_COLUNA) -> str:
    """A folha viva da LUZ: a barra e as cinco lâmpadas do DESENHO GRANDE.

    POR QUE ELA PRECISOU EXISTIR, e a medição está no DOM vivo de 03/09/2026, na
    mesa dela, com UM controle no cabo (``ensaios/a_luz_do_desenho_e_a_luz_do_aparelho.py``)::

        p1   o aparelho diz (0, 0, 255)   e o desenho acende (126, 184, 212)
        p1   o número 1 pede a lâmpada 3  e o desenho não acende nenhuma

    O `#7EB8D4` é o `--luz` que o GERADOR crava no `<g>` — a cor do MOCKUP,
    parada na tela dela debaixo de um hexadecimal que já dizia `#0000FF`. A
    mesma célula afirmando duas cores, e quem olha lê o desenho antes do número.

    POR QUE UMA FOLHA, e não um campo — a mesma razão de `folha_do_plastico`: o
    pintor sabe escrever texto, largura, fundo, valor, `innerHTML`, classe, cor,
    atributo e `--plastico`, e **nenhum deles escreve um `--luz`**. Reescrever o
    SVG inteiro pelo `innerHTML` custaria as 370 linhas do desenho a cada meio
    segundo e nunca sossegaria (o navegador normaliza marcação). O `innerHTML` de
    um `<style>` é TEXTO, e texto volta como foi escrito.

    O `!important` NÃO É FORÇA BRUTA, e é o único caminho: o `--luz` do mockup
    mora no atributo `style` do `<g>`, e declaração de linha vence folha. A marca
    `led-on` das lâmpadas tem o mesmo problema — ela é cravada pelo gerador nos
    `<rect>` que o MOCKUP escolheu, e some do cálculo assim que uma regra
    `!important` de igual especificidade pinta as cinco.

    A ORDEM DAS DUAS REGRAS DE LÂMPADA É O QUE DECIDE: as cinco apagam primeiro,
    as do padrão acendem depois. As duas valem (0,3,0) e as duas são
    `!important`, então quem vem por último ganha — escrever na ordem inversa
    apagaria a lâmpada que acabou de acender.

    SEM COR A AFIRMAR, A BARRA APAGA. É a regra dela — *"se não tá mostrando
    agora, não tem info pra mostrar no produto"* — e ela vale para os quatro
    lugares: um lugar sem controle recebe as regras de apagado do mesmo jeito,
    senão o `--luz` do mockup fica aceso num lugar que diz "Desconectado".

    :param luzes: por lugar (`p1`…`p4`), o par `(hexadecimal da barra, número)`.
        O hexadecimal vazio ou `—` apaga a barra; o número `None` apaga as cinco
        lâmpadas. Um lugar ausente do dicionário é tratado como apagado.
    """
    from hefesto_dualsense4unix.core.led_control import player_led_pattern

    from . import TODOS_OS_LUGARES, TRAVESSAO

    #: AS TRÊS VARIÁVEIS VÊM JUNTO, e é o que faz esta cura chegar HOJE: a
    #: página publicada declara o par das lâmpadas só em `.luzinhas`, e sem elas
    #: no escopo do desenho as regras abaixo seriam inválidas no tempo de
    #: computar — a folha viva pintaria o nada, com todo o mecanismo montado.
    regras: list[str] = [tokens_da_luz()]
    for pref in sorted(TODOS_OS_LUGARES | set(luzes)):
        onde = f'{caixa}[data-controle="{pref}"]'
        cor, numero = luzes.get(pref) or ("", None)
        cor = "" if str(cor).strip() in ("", TRAVESSAO) else str(cor).strip()
        regras.append(f"{onde} {ALVO_DA_BARRA}"
                      f"{{--luz:{cor or BARRA_APAGADA} !important}}")
        #: AS CINCO APAGAM PRIMEIRO, E O PADRÃO ACENDE DEPOIS. As duas regras
        #: valem (0,3,0) e as duas são `!important`, então entre iguais decide a
        #: ORDEM — inverter as duas linhas apaga a lâmpada que acabou de
        #: acender, e a tela volta às cinco iguais. Medido nos dois lugares:
        #: reprova no teste de unidade e reprova no DOM vivo.
        regras.append(f"{onde} {ALVO_DAS_LAMPADAS}"
                      f"{{fill:var(--led-apagado) !important;"
                      f"filter:none !important}}")
        #: O PADRÃO SAI DE `player_led_pattern`, a tabela que o DAEMON acende —
        #: nunca da classe `led-on` do arquivo, que é o desenho perguntando a si
        #: mesmo. Ele responde a qualquer número (o `monta.PADRAO_JOGADOR` só
        #: precomputa 1..8 e levanta `KeyError` fora disso), e é por isso que a
        #: leitura é esta e não a da bancada.
        if not isinstance(numero, int) or isinstance(numero, bool):
            continue
        for i, acesa in enumerate(player_led_pattern(numero), 1):
            if acesa:
                regras.append(
                    f'{onde} [id$="-led-jogador-{i}"]'
                    f"{{fill:var(--led-aceso) !important;"
                    f"filter:drop-shadow(0 0 .5px var(--led-aceso)) !important}}")
    return "".join(regras)


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

    E O ENDEREÇO GANHOU O ALVO EM 03/09/2026, porque só ele NÃO bastava. O
    `blocos:` reescreve o miolo por `document.querySelector`, e nem a régua da
    identidade nem a do mockup têm como saber disso lendo o HTML — a troca mora
    no JavaScript, não na marcação. Com `data-hef-alvo="plastico"` o pintor
    escreve a variável no PRÓPRIO item (`cores_da_troca` manda a lista, na
    ordem do documento), e o que era invisível às duas réguas passa a deixar o
    selo da visita.

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
            f' data-hef="{ITEM_DA_TROCA}"'
            f' data-hef-alvo="{ALVO_DO_PLASTICO}"{veste}>'
            f'{anel}<span class="np">P{numero}</span>'
            f'<span>{nome}</span>{_luzinhas(numero)}</span>')


def _ordem_da_troca(mesa: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """A ordem em que a seção da troca desenha os controles.

    UM DONO PARA A ORDEM, e ele existe porque duas coisas dependem dela: o HTML
    que `secao_da_troca` monta e a LISTA que `cores_da_troca` manda ao pintor.
    O pintor distribui a lista pelos itens na ordem do DOCUMENTO — se as duas
    ordens divergissem, cada controle receberia a cor do vizinho, calado.
    """
    return sorted(mesa, key=lambda c: int(c.get("jogador") or 0))


def cores_da_troca(mesa: list[dict[str, Any]]) -> list[str]:
    """A cor do plástico de cada `.troca-item`, na ordem do documento.

    SÃO DUAS LINHAS COM OS MESMOS CONTROLES — o ANTES e o DEPOIS —, e o que
    muda entre elas é o número, nunca a casca: a troca dá um número a outro
    aparelho, não repinta plástico nenhum. Por isso a lista é a mesma sequência
    duas vezes.

    VAZIA QUANDO NÃO HÁ TROCA A CONTAR: com menos de dois controles a seção não
    desenha item nenhum (ver `secao_da_troca`), e uma lista com valor a mais
    escreveria num item que não existe.
    """
    ordenada = _ordem_da_troca(mesa)
    if len(ordenada) < 2:
        return []
    cores = [_cor_do_plastico(str(c.get("cor") or "")) for c in ordenada]
    return cores + cores


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
    ordenada = _ordem_da_troca(mesa)
    cabeca = f"{r}<h2>{TITULO_DA_TROCA}</h2>"
    if len(ordenada) < 2:
        quantos = "nenhum controle" if not ordenada else "um controle só"
        return (f"{cabeca}\n"
                f"{r}<p>A troca acontece entre <b>dois</b> controles, e há "
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
        f"\n{r}      existem agora. Um número livre não teria com quem trocar, e "
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
    #: A LUZ DO DESENHO GRANDE, por LUGAR — ver `folha_da_luz`. Ela nasce vazia
    #: e só recebe quem tem controle: `folha_da_luz` APAGA todo lugar que não
    #: aparecer aqui, que é como o `--luz` do mockup morre num lugar vazio.
    luz_do_desenho: dict[str, tuple[str, int | None]] = {}
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
        #: A LUZ DO DESENHO GRANDE, por LUGAR e não por `uniq` — ela viaja numa
        #: folha de estilo (`folha_da_luz`), e um seletor CSS endereça o `p1`,
        #: que é o que a página tem. A cor é a `acesa`, isto é, a que o daemon
        #: publica: ela já vem PÓS-ESCALA de brilho por contrato (D8), então o
        #: desenho mostra a cor JÁ escalada sem esta aba refazer a conta — que é o
        #: mesmo que a prévia da GTK pinta (`_on_lightbar_preview_draw`).
        #: `None` nos quatro estados de ressalva, e aí a barra APAGA.
        if casa.get("pref"):
            luz_do_desenho[str(casa["pref"])] = (_hex(acesa) if acesa else "", n)
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
            #: E ELE LEVA O DESENHO DE AGORA desde a LUZES-01 — com `bits`, o
            #: indicador das cinco lâmpadas vira a BOTOEIRA: mostra o desenho e
            #: deixa mudá-lo, sem tocar no número. O valor sai do dado
            #: (`desenho_de_agora`: o override do perfil e, na falta dele, o
            #: padrão do número), nunca de memória do gerador.
            "luz": desenho_da_luz(_tinta(cor_escolhida(acesa, b)),
                                  1.0 if b is None else float(b), n,
                                  dica_da_luz(nome, via, recado or "",
                                              o_coop_manda(ctx.state)),
                                  estado=estado,
                                  #: E SÓ COM A FOLHA NO LUGAR — ver
                                  #: `a_folha_alcanca_a_botoeira`. Sem ela o
                                  #: `bits=None` mantém o indicador de leitura
                                  #: que o publicado de hoje sabe desenhar.
                                  bits=(desenho_de_agora(p, uniq, n)
                                        if a_folha_alcanca_a_botoeira() else None),
                                  coop_manda=o_coop_manda(ctx.state)),
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
            #: A RAZÃO DO TRACEJADO, EM UMA LINHA — D-02, decisão [01] de
            #: 04/09/2026. Ela é o PRIMEIRO retorno de `rotulo_lightbar`, o
            #: mesmo que decide `acesa` e `estado` acima: uma leitura só, três
            #: consequências. Uma frase escrita aqui a partir do `estado` seria
            #: a segunda verdade sobre o mesmo fato — e a que perderia a
            #: distinção entre "a Steam está com ele" e "em Nativo o jogo é
            #: dono", que é justamente a pergunta que esta linha responde.
            #:
            #: SEM RESSALVA, O MARCADOR — e a chave vai em TODO tique. Omiti-la
            #: quando não há nada a dizer deixaria a frase do estado anterior na
            #: tela para sempre; mandar `""` a trocaria por um travessão solto,
            #: porque `escrever()` faz isso de propósito. Ver `NADA_A_DIZER`.
            ENDERECO_DA_RESSALVA: recado or NADA_A_DIZER,
            #: O RÓTULO INTEIRO, e não só o número. O desenho escreve
            #: `P1 • Cosmic Red • USB`; emitir só o `P1` fazia o primeiro tique
            #: APAGAR o nome do controle e o transporte da tela dela — a
            #: pintura escreve `textContent`, e três pedaços viravam um.
            "identidade": f"P{n} • {nome} • {via}",
            #: A FILEIRA DOS QUATRO NÚMEROS, viva. O `on` sai daqui, e as dicas
            #: também: as do HTML publicado estão CONGELADAS do desenho e
            #: nomeiam controle por transporte que já mudou.
            #: `quantos` É `ctx.conectados`, a mesma conta que o daemon faz para
            #: recusar — ver `um_botao_de_player`. Não é `len(donos)`: quem não
            #: tem item de mesa fica fora dos donos e continua ligado.
            "players": fileira_de_players(nome, n, donos,
                                          quantos=len(ctx.conectados)),
            #: O ANEL DE CADA NÚMERO, e ele vem DEPOIS do `players` de propósito
            #: — a mesma lição que `ENDERECO_DA_INCERTA` pagou uma linha acima.
            #: O `players` troca o miolo da fileira inteira (alvo `html`) e
            #: RECRIA os quatro `<i>`; escrever a cor antes seria escrevê-la em
            #: elementos que a linha de cima está prestes a destruir — e com
            #: eles iria o selo da visita, que é o que prova à régua do mockup
            #: que este endereço não é morto.
            #:
            #: A COR É A DO DONO DO NÚMERO, nunca a da coluna: o anel diz de
            #: QUEM é o número que este botão oferece. Um número livre não tem
            #: `<i>` nenhum, e o `""` não acha onde pousar — calado e correto.
            **{endereco_do_anel(k):
               _cor_do_plastico(str((donos.get(k) or {}).get("cor") or ""))
               for k in NUMEROS},
        }
    return {
        "colunas": colunas,
        #: A COR DE CADA ITEM DO ANTES/DEPOIS, na ordem em que a seção os
        #: desenha. Ela vem por CAMPO e não só pelo `blocos:` abaixo porque o
        #: `blocos:` é invisível às duas réguas desta casa — a troca mora no
        #: JavaScript, e o que se lê no HTML é um `--plastico` com endereço sem
        #: alvo, que é a forma exata da cor congelada. Ver `cores_da_troca`.
        ITEM_DA_TROCA: cores_da_troca(ctx.mesa),
        #: O INTERRUPTOR DO AUTOMÁTICO — D-13. Ele é da MESA e não da coluna: o
        #: campo é um só para o perfil inteiro, e emiti-lo por controle
        #: desenharia quatro interruptores para um valor só.
        #:
        #: A LÍNGUA É `sim`/`""`, e é a do alvo `marcado` do piloto — a mesma do
        #: alvo `classe` booleano. `str(True)` seria `"True"`, o JS escreveria
        #: `"true"`, e as duas réguas desta casa que traduzem o declarado dizem,
        #: por escrito, que erram nesse par.
        ENDERECO_DO_AUTOMATICO: "sim" if automatico_do_perfil(p) else "",
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
        #:
        #: E A LUZ VIAJA NO MESMO `<style>` — 03/09/2026. O `id` dele diz
        #: "plastico" porque foi o casco que o pariu, e ele fica: **ele já está
        #: PUBLICADO**, e é isso que decide. Um `<style id="luz-viva">` novo só
        #: chegaria à tela dela no dia em que ela mandasse publicar a 04, e a
        #: barra continuaria com a cor do mockup até lá. As duas folhas não se
        #: cruzam — uma pinta `.ds-svg`, a outra o grupo do lightbar e os cinco
        #: `<rect>` do indicador —, e a ordem entre elas não muda nada.
        "blocos": {SECAO_DA_TROCA: secao_da_troca(ctx.mesa),
                   "#plastico-vivo": (_folha_do_plastico(ctx.mesa, CAIXA_DA_COLUNA)
                                      + folha_da_luz(luz_do_desenho))},
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

    E ELE VALE PARA O TRILHO PELO MESMO MOTIVO, com o tempo invertido —
    03/09/2026. Um `<input type="range">` clicado na pista dispara `input`,
    depois `change` e depois `click`; o BOOTSTRAP escuta `change` e `click`, e
    sem este guarda cada clique na pista viraria DUAS gravações no perfil dela e
    DUAS escritas no rádio. No seletor de cor o `click` chega ANTES da escolha e
    carrega o valor velho; no trilho ele chega DEPOIS e carrega o mesmo valor.
    Nos dois casos ele não é um pedido — o pedido é o `change` —, e nos dois a
    resposta certa é sair calado: recusar dizendo poria uma frase de erro na
    tela dela por um gesto que ela fez uma vez só.
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

    def _quantos_recebem_o_desenho(self) -> int:
        """ZERO, e o zero é um FATO desta aba — não um valor de conveniência.

        É o único degrau que `lightbar_actions._msg_do_desenho` pede além dos
        seis campos acima, e ele existe lá para o aviso *"o mesmo desenho foi
        para N controles"* do "Todos" da janela GTK. **Esta aba nunca escreve
        sem `uniq`** — está dito no `_janela_do_desfecho`, e os dois gestos que
        chegam aqui recusam antes com *"o clique não disse em qual controle"*.
        Com alvo por controle, a própria GTK devolve 0 nesse método.

        Escrever `0` aqui é declarar a ausência do ramo, e não copiar a regra:
        a leitura de "Todos" mora em `_edit_uniq`/`_uniqs_conectados`, e nenhum
        dos dois é alcançado por um caminho que sempre tem alvo. Se um dia esta
        aba ganhar um "Todos", o lugar de emendar é aqui — e o método some em
        favor do da GTK, com o mixin emprestando os dois degraus.
        """
        return 0


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


#: "PERGUNTE AO PERFIL" — o brilho que `_escrever_a_cor` usa quando quem chama
#: não tem um na mão. Ele não é `None`: `None` é um valor legítimo deste
#: parâmetro e quer dizer *"não sei o brilho"* (o `led.set` sai sem o campo e o
#: daemon assume 1.0). Um default `None` faria o gesto do trilho não ter como
#: dizer "mande SEM brilho" — e, pior, faria os três gestos de cor perderem a
#: leitura do perfil no dia em que alguém passasse `None` por engano.
_DO_PERFIL: Any = object()


def _escrever_a_cor(ctx: Contexto, p: Any, uniq: str,
                    rgb: tuple[int, int, int], *,
                    apagando: bool = False,
                    brilho: Any = _DO_PERFIL) -> None:
    """O CAMINHO ÚNICO de escrita de cor desta aba — com o brilho e com a frase.

    O `brilho` CHEGA PRONTO OU SE PERGUNTA AO PERFIL, e o parâmetro nasceu em
    03/09/2026 com o trilho que grava. Os três gestos de COR não têm brilho na
    mão — eles pintam com o que já está guardado —, e para eles nada muda: o
    default `_DO_PERFIL` lê `brilho_do_controle`, que é o MESMO número que a
    coluna imprime. Quem passa o valor é o gesto `brilho`, e a razão é de ORDEM:
    ele precisa aplicar no aparelho o número que ela ACABOU de escolher, e não
    depender de a gravação em disco ter acontecido primeiro. Sem o parâmetro,
    "aplicar" e "guardar" ficariam presos numa ordem só — e um disco que
    recusasse a escrita levaria junto a aplicação, que não tem nada a ver.

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

    POR QUE O `RuntimeError` NO RAMO DO GUARDADO, e ele não é "recusa": entre a
    frase no cartão e o silêncio, o silêncio é a mentira — quem clica conclui
    que a cor foi. A GTK diz a mesma frase num toast neutro.

    **FATO SUBSTITUÍDO — 04/09/2026.** Estas linhas diziam que *"o único canal
    que esta tela tem é o `_recusou_dizendo`, e ele só carrega `RuntimeError`"*,
    com um RELATO pedindo um canal de aviso. **O canal existe:** a ONDA0-P o
    entregou com a D-01, e um gesto que devolve `{"recado": …}` pousa no MESMO
    cartão com tom de sucesso e vida de 6 s — o `brilho` desta aba já o usa.

    **E MESMO ASSIM ELE NÃO SERVE AQUI**, e a razão não é de infraestrutura:
    este caminho **não sabe qual dos dois desfechos aconteceu**. Quem lê o corpo
    do daemon é `frase_do_desfecho`, e o que volta é UMA frase — as quatro
    razões (recusa explicada, aplicado, guardado, nada aconteceu) chegam aqui já
    colapsadas em texto. Escolher o tom exigiria reler `destinos_da_aplicacao`
    deste lado, que é a segunda verdade sobre o mesmo payload, e é exatamente o
    que a ELO-MUDO-01 inverteu. Enquanto o dono não separar os dois, o laranja é
    o erro mais barato: diz demais sobre um guardado, e não de menos sobre uma
    recusa. **RELATO:** um segundo retorno de `frase_do_desfecho`, dizendo QUAL
    dos quatro destinos venceu, fecharia isto para as dez abas — é
    `app/textos_de_aplicacao.py`, fora do território deste arquivo.

    A COMPARAÇÃO É COM A FRASE FELIZ, e não com `aplicado_em`: quem lê os dois
    destinos é `frase_do_desfecho`, que conhece as QUATRO razões do daemon e a
    ordem entre elas — recusa explicada, aplicado, guardado, nada aconteceu.
    Reler `destinos_da_aplicacao` deste lado para decidir seria a segunda
    verdade sobre o mesmo payload, e é exatamente o que a ELO-MUDO-01 inverteu:
    *"antes a janela deduzia e o daemon era ignorado"*. Aqui a janela só
    pergunta *"a frase que saiu é a do caminho feliz?"* — e cala quando é.
    """
    from hefesto_dualsense4unix.app.actions.lightbar_actions import frase_do_envio

    if brilho is _DO_PERFIL:
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


@gesto("04-iluminacao.html", "reenviar")
def reenviar(ctx: Contexto, o: dict[str, Any], p: Any) -> None:
    """A caixa `#RRGGBB` é o botão: a cor que está escrita vai ao controle de novo.

    DECISÃO DELA, 04/09/2026, na pergunta [03] desta aba, contra as outras duas
    opções que eu ofereci (deixar como está, ou um terceiro botão em Opções):
    *"A caixa do hexadecimal vira o botão."*

    O BURACO QUE ISSO FECHA, e ele só existe para UMA das duas portas de cor: um
    `<button>` da guia sempre dispara, então clicar de novo no mesmo tom
    reenvia. O `<input type="color">` não — ele só avisa no `change`, e reabrir
    o seletor para confirmar a MESMA cor não manda nada ao aparelho (ver
    `_so_abriu_o_seletor`, que é quem descarta o `click` de abertura, e tem de
    descartar). Quando um controle cai e volta, ou quando ela quer conferir se a
    cor chegou, a cor que ela escolheu à mão era justamente a única sem porta de
    volta. A janela GTK tem um botão dedicado para isso.

    O VALOR VEM DO `texto`, e não de um `data-hex`, e essa é a parte que
    importa: `data-hex` é escrito pelo GERADOR e fica congelado no que o mockup
    sabia — reenviar por ele mandaria ao plástico dela a cor do desenho. O
    `textContent` desta caixa é reescrito a cada tique pelo `data-campo="hex"`,
    com a cor PEDIDA (pré-escala de brilho — ver `cor_escolhida`), então o que
    sai daqui é exatamente o que ela está lendo na tela.

    NÃO É UM SEGUNDO CAMINHO DE ESCRITA. Ele passa pelo `_escrever_a_cor` como
    os outros três, então herda o brilho do perfil e a leitura do desfecho. Uma
    chamada direta ao `led_set` aqui reintroduziria, nesta porta, os dois
    defeitos que aquele caminho único nasceu para curar.

    O TRAVESSÃO É RECUSA. Numa coluna que esvaziou, o molde do lugar sem dono
    escreve `—` nesta caixa; a folha desta aba já lhe tira o clique
    (`pointer-events:none`), e esta guarda é a segunda trava — a que vale se
    alguém alcançar o gesto por outro caminho. `hex_to_rgb` recusaria dizendo,
    mas com uma frase que fala de formato, não do que aconteceu.
    """
    from hefesto_dualsense4unix.core.led_control import hex_to_rgb

    uniq = _uniq(o)
    if not uniq:
        raise ValueError("reenviar: o clique não disse em qual controle")
    escrito = str(o.get("texto") or "").strip()
    if not escrito or not escrito.startswith("#"):
        raise ValueError(
            f"reenviar: a caixa do hexadecimal não tem uma cor a reenviar "
            f"({escrito!r}) — este lugar está sem controle.")
    _escrever_a_cor(ctx, p, uniq, hex_to_rgb(escrito))


@gesto("04-iluminacao.html", "auto")
def automatico(ctx: Contexto, o: dict[str, Any], p: Any) -> None:
    """"Automático": LARGAR a luz, para o jogo escolher a cor.

    DECISÃO DELA, 01/09/2026, e ela corrigiu a minha leitura: *"voltar ao
    automático nesse caso é deixar o jogo escolher."* Não é devolver a cor do
    número do jogador — é o Hefesto soltar o claim da barra.

    `lightbar.reset` é exatamente isso, e o `ipc_handlers.py:4655` diz com
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


def _pct_pedido(o: dict[str, Any]) -> int:
    """Os 0-100 que o trilho mandou, validados PELO ESQUEMA e não por mim.

    A FAIXA TEM DONO: `app/draft_config.LedsDraft.lightbar_brightness` é
    `int, ge=0, le=100` — o mesmo campo que o `GtkScale` da janela estável
    alimenta. Digitar `0 <= n <= 100` aqui seria a segunda declaração da mesma
    faixa, e a que envelheceria calada no dia em que o produto mudasse a escala.
    Aqui só se traduz a recusa do pydantic para uma frase de tela.

    `valor` É A PORTA, e é o que o BOOTSTRAP manda de todo elemento que tem
    `value` — num `<input type="range">` é a posição do polegar, como string.
    """
    from hefesto_dualsense4unix.app.draft_config import LedsDraft

    cru = str(o.get("valor") or "").strip()
    try:
        return int(LedsDraft(lightbar_brightness=int(float(cru))).lightbar_brightness)
    except (TypeError, ValueError) as erro:
        raise ValueError(
            f"brilho: o trilho mandou {cru!r}, que não é uma porcentagem de "
            f"0 a 100 ({erro})") from erro


def _fracao_do_disco(pct: int) -> float:
    """Os 0-100 da TELA na escala em que o PERFIL guarda o brilho (0.0-1.0).

    A CONTA TEM DONO, e ela é `app/draft_config._leds_draft_to_config` — o
    `leds.lightbar_brightness / 100.0` que o "Salvar Perfil" da janela estável
    já faz com o mesmo número. As duas escalas convivem de propósito e estão
    declaradas nos dois esquemas: `LedsDraft` é `int 0-100` (é o que a tela
    mostra) e `LedsConfig` é `float 0.0-1.0` (é o que o disco guarda). Digitar
    o `/100` aqui seria a terceira cópia, e a primeira a errar no dia em que a
    escala mudar.

    ELE É PRIVADO POR CONVENÇÃO DE NOME, e não por contrato — do mesmo jeito que
    este arquivo já lê `lightbar_actions._AVISO_HEFESTO_DESLIGADO`.
    **RELATADO:** a conversão entre as duas escalas merece nome público; é
    `app/draft_config.py`, fora do território deste arquivo.
    """
    from hefesto_dualsense4unix.app.draft_config import (
        LedsDraft,
        _leds_draft_to_config,
    )

    so_o_brilho = _leds_draft_to_config(LedsDraft(lightbar_brightness=pct),
                                        only_fields={"lightbar_brightness"})
    return float(so_o_brilho.lightbar_brightness)


def _com_o_brilho_gravado(prof: Any, uniq: str, pct: int) -> Any:
    """O perfil com o brilho DESTE controle trocado, ou `None` se nada mudou.

    `None` EVITA O BARULHO, e é a mesma regra do `_com_os_gatilhos` da aba
    Gatilhos: regravar um perfil idêntico troca a data do arquivo e cria um
    backup em `.historico/` por um arraste que voltou ao mesmo lugar.

    O ALVO É O OVERRIDE DO CONTROLE, e não a seção global — decisão do enunciado
    desta frente, e ela tem base medida: `ControllerOverrides.leds` existe desde
    a PERFIL-02 e `manager._controllers_to_led_scales` já distribui o brilho por
    MAC. **E esta aba não tem outro alvo possível:** a fita do topo é INERTE
    aqui desde 28/08 (decisão dela — os quatro controles ficam lado a lado e
    *"não há escolhido"*), então cada trilho pertence a UMA coluna e a uma só.
    Gravar no global faria o trilho do P2 mudar o brilho do P1, que é a mesma
    contradição que o `_janela_do_desfecho` já anota sobre o ramo "Todos".

    A FUSÃO É POR CAMPO, e o esquema a escreve: um override PARCIAL nunca apaga
    o global no replug (PERFIL-01). Por isso o ramo do `model_copy` existe — os
    overrides do disco dela HOJE são `{"lightbar": [255, 0, 0]}` e nada mais, e
    trocar a seção inteira por uma que só fala de brilho apagaria a cor que ela
    escolheu para aquele controle. `save_profile` serializa as entradas do mapa
    com `exclude_unset`, então o que não foi tocado continua ausente do arquivo.
    """
    from hefesto_dualsense4unix.profiles.schema import ControllerOverrides

    fracao = _fracao_do_disco(pct)
    chave = chave_do_override(uniq)
    atuais = dict(prof.controllers or {})
    dele = atuais.get(chave) or ControllerOverrides()
    antes = dele.leds
    if antes is None:
        from hefesto_dualsense4unix.app.draft_config import (
            LedsDraft,
            _leds_draft_to_config,
        )

        novos = _leds_draft_to_config(LedsDraft(lightbar_brightness=pct),
                                      only_fields={"lightbar_brightness"})
    else:
        if antes.lightbar_brightness == fracao:
            return None
        novos = antes.model_copy(update={"lightbar_brightness": fracao})
    atuais[chave] = dele.model_copy(update={"leds": novos})
    return prof.model_copy(update={"controllers": atuais})


@gesto("04-iluminacao.html", "brilho", grava="save_profile")
def brilho(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any] | None:
    """Ela arrastou o trilho. O brilho vai AO APARELHO e AO DISCO, na hora.

    DECISÃO DELA, 03/09/2026. Perguntada se mexer no brilho grava o perfil na
    hora ou espera o "Salvar Perfil": **"Grava na hora"**.

    O QUE ISSO DESFAZ, e estava na tela: o trilho JÁ ERA DESENHADO como slider —
    a regra `.cheio::after` punha um knob de 12px na ponta da barra roxa — e não
    fazia nada. Ela via `100%`, arrastava, e o número não mudava. O
    `docs/data/paridade-gtk-html.csv` a chamava de *"a maior falta desta aba"*.

    POR QUE GRAVAR É A ÚNICA SAÍDA COERENTE, e a razão é medida: esta interface
    NÃO TEM RASCUNHO (decisão dela de 01/09 — *"clicar na cor já deveria aplicar
    a cor no controle"*), e o número que a coluna imprime é lido do PERFIL EM
    DISCO por `brilho_do_controle`. Sem gravar, o valor voltaria sozinho ao
    velho no tique seguinte, e o gesto seria mais um botão que aceita o toque e
    não age — a família de defeito que o mapa desta casa nomeia dezesseis vezes.

    OS TRÊS TEMPOS, E A ORDEM IMPORTA:

        1. a COR PEDIDA sai da tela com o brilho VELHO — `cor_escolhida` inverte
           a escala do daemon (D8: o `lightbar_rgb` é PÓS-escala), e invertê-la
           com o brilho NOVO devolveria uma cor que ela nunca pediu;
        2. o DISCO recebe o número novo. Ele é a promessa do gesto, e é o que
           sobrevive a um `profile.switch`;
        3. o APARELHO recebe a mesma cor com o brilho NOVO, passado no
           parâmetro — e não relido do disco. Assim a aplicação não depende de a
           gravação ter dado certo, e um disco cheio não apaga a barra dela.

    ESCREVE NO DISCO DELA, e por isso ele entra em `hefesto_vivo.PERIGOSOS`: a
    prova botão a botão roda aba por aba e arrastaria este trilho para o valor
    que estivesse na tela, gravando no perfil ATIVO. É o molde do `("*",
    "salvar")` e do `guardar` da aba Gatilhos, pelo mesmo motivo.

    NÃO É `perfil.gravar_e_reaplicar`, e o preço está medido em 03/09 no
    `a03_gatilhos._gravar_so_o_gatilho`: aquele caminho termina em
    `profile_switch`, que manda o daemon reaplicar o perfil INTEIRO — e a barra
    que ela tinha DESLIGADO acende de novo, sem nada na tela dizer que ia
    acontecer. Um trilho de brilho é o escopo mais estreito desta aba; ele não
    pode ser o gesto que desfaz escolha viva dela em outra célula.

    O `click` QUE VEM DEPOIS DO `change` NÃO É UM SEGUNDO PEDIDO. Medido no
    contrato do próprio ouvinte: um `<input type="range">` clicado na pista
    dispara `input`, `change` e `click`, nesta ordem, e o BOOTSTRAP escuta os
    dois últimos. Sem o guarda, um clique na pista gravaria DUAS vezes e mandaria
    DUAS escritas ao rádio. `_so_abriu_o_seletor` já era exatamente esse guarda,
    do outro lado do mesmo problema.

    SEM COR CONHECIDA, GUARDA E DIZ. Nos quatro estados de ressalva do motor
    (Nativo, a Steam segurando o `fd`, cor desconhecida) não há cor a reescalar,
    e mandar preto APAGARIA a barra por um arraste de brilho. O número vai para
    o disco — que é o que ela pediu — e o cartão diz que a barra não mudou
    agora. Entre a frase no cartão e o silêncio, o silêncio é a mentira.

    **A FRASE ENCOLHEU — 04/09/2026, decisão [04] dela**, entre três opções: a
    frase inteira, uma frase curta, e o silêncio. Ela escolheu a curta, e a
    razão que ela deu é a que este arquivo já sabia: a versão longa gastava três
    linhas de cartão *"repetindo com palavras o que a tira tracejada já mostra
    sem palavra nenhuma"*. O que saiu foi a explicação do *"porque não há cor a
    reacender"*; o que ficou é o que só a frase pode dizer — quanto foi guardado
    e qual é a causa, e a causa continua vindo do MOTOR, palavra por palavra.

    **E ELE DEIXOU DE MENTIR SOBRE O PRÓPRIO DESFECHO, no mesmo dia.** A frase
    saía por `RuntimeError`, que no piloto é o canal da RECUSA — cartão laranja,
    30 s, a mesma cara de *"o produto não fez"*. E o produto FEZ: o brilho está
    no disco dela, que é a promessa inteira deste gesto. O relato desta função
    pedia por escrito *"um canal de AVISO (nem recusa nem silêncio)"*, e a
    ONDA0-P o entregou com a D-01: um gesto que devolve `{"recado": …}` deposita
    no MESMO cartão com tom de sucesso e vida de 6 s. É o que ele faz agora —
    e o pedido some do relato porque foi atendido.

    :return: `{"recado": …}` quando o número foi guardado e a barra não pôde
        mudar; `None` no caminho feliz, em que o cartão diz a frase padrão.
    """
    uniq = _uniq(o)
    if not uniq:
        raise ValueError("brilho: o clique não disse em qual controle")
    if _so_abriu_o_seletor(o):
        return None
    pct = _pct_pedido(o)

    nome = str(ctx.state.get("active_profile") or "").strip()
    if not nome:
        raise RuntimeError(
            "não há perfil ativo agora, e o brilho da barra é do perfil — não "
            "da máquina. Escolha um perfil na aba Perfis.")

    #: A COR PEDIDA COM O BRILHO VELHO — ver o tempo 1 da docstring.
    from hefesto_dualsense4unix.app.widgets.controller_card import (
        cor_do_swatch,
        rotulo_lightbar,
    )

    dele = next((c for c in ctx.conectados if str(c.get("uniq") or "") == uniq), None)
    if dele is None:
        raise RuntimeError(
            "este controle não está ligado agora — não há barra em que "
            "aplicar o brilho.")
    velho = brilho_do_controle(perfil.ativo(nome), uniq)
    recado, _base = rotulo_lightbar(dele, ctx.state)
    pedida = cor_escolhida(cor_do_swatch(dele), velho)

    loader = perfil._com_o_src()
    novo = _com_o_brilho_gravado(loader.load_profile(nome), uniq, pct)
    if novo is not None:
        loader.save_profile(novo, origem="interface-nova")

    # O BRILHO APLICA, NÃO JUSTIFICA A FALHA — 05/09/2026, decisão dela:
    #
    #     "O Hefesto não pode ter essa falha. Isso tem que APLICAR, não
    #      justificar a falha"  (pergunta 04-Q4)
    #
    # Até hoje esta linha era `if recado is not None or not pedida: return
    # {"recado": …}`: com o motor sem afirmar a cor — Modo Nativo, a Steam com o
    # `fd`, ou cor desconhecida, que é o estado de PARTIDA de toda sessão antes
    # de o produto escrever a primeira cor — o trilho gravava o percentual no
    # disco e devolvia a desculpa. O trilho virava o botão que aceita o toque e
    # não age, que é a família de defeito que este gesto nasceu para curar.
    #
    # E a resposta já estava escrita NESTE arquivo, no vizinho `_a_cor_de_agora`
    # (logo abaixo), que trata o MESMO "não sei a cor" e responde o contrário,
    # com a razão por extenso: *"A QUEDA É A COR DO SLOT, e ela é a resposta
    # CERTA e não um remendo: nos quatro estados em que o motor não afirma cor
    # o que o automático estava dando àquele controle era exatamente
    # `player_slot_color(numero)`"*. Duas funções do mesmo arquivo, o mesmo
    # fato, duas respostas — e a errada era a que ela via.
    #
    # A janela estável nunca teve este buraco: `lightbar_actions.py:830` escreve
    # SEMPRE, com a cor do perfil (`_current_rgb`, semeado de
    # `draft.effective_leds_for`). Aqui a escada é a mesma, um degrau mais
    # funda: cor pedida -> cor do perfil -> cor do slot do jogador.
    alvo = tuple(pedida)[:3] if pedida else _a_cor_de_agora(ctx, perfil.ativo(nome), dele)
    _escrever_a_cor(ctx, p, uniq, alvo, brilho=_fracao_do_disco(pct))
    if recado is not None:
        # A ressalva NÃO some: ela diz que o motor não afirma a cor, e isso
        # continua verdade. O que mudou é que a barra acendeu.
        return {"recado": f"Brilho em {pct}%. {recado}."}
    return None


def _a_cor_de_agora(ctx: Contexto, cru: dict[str, Any],
                    c: dict[str, Any]) -> tuple[int, int, int]:
    """A cor que ESTE controle está acendendo agora — a que o desligamento grava.

    ELA É A PEDIDA, e não a publicada: `lightbar_rgb` vem PÓS-escala de brilho
    por contrato do daemon (D8), e gravar esse valor faria a cor do perfil
    escurecer a cada volta — a 50% de brilho, `#0000FF` viraria `#00007F` no
    disco e o brilho o escalaria de novo na aplicação seguinte. `cor_escolhida`
    é quem inverte a escala, e é o mesmo caminho que a caixa `#RRGGBB` usa.

    A QUEDA É A COR DO SLOT, e ela é a resposta CERTA e não um remendo: nos
    quatro estados em que o motor não afirma cor (Nativo, a Steam com o `fd`,
    cor desconhecida) o que o automático estava dando àquele controle era
    exatamente `player_slot_color(numero)` — é essa a paleta que ele governa. Um
    preto aqui apagaria a barra dela por um clique num interruptor; um branco
    inventaria uma cor que ninguém escolheu.

    :param cru: o perfil como DICIONÁRIO (`perfil.ativo`), e não o `Profile` do
        pydantic: `brilho_do_controle` lê o JSON cru, e um modelo passado aqui
        devolveria `None` em silêncio — o brilho sumiria da inversão de escala e
        a cor gravada sairia escurecida.
    """
    from hefesto_dualsense4unix.app.widgets.controller_card import cor_do_swatch
    from hefesto_dualsense4unix.core.led_control import player_slot_color

    uniq = str(c.get("uniq") or "")
    pedida = cor_escolhida(cor_do_swatch(c), brilho_do_controle(cru, uniq))
    if pedida:
        r, g, b = tuple(pedida)[:3]
        return (int(r), int(g), int(b))
    return player_slot_color(_numero(ctx, c))


def _com_a_cor_gravada(prof: Any, uniq: str, rgb: tuple[int, int, int]) -> Any:
    """O perfil com a cor DESTE controle escrita no override dele.

    É O IRMÃO DE `_com_o_brilho_gravado`, campo por campo, e a razão de ser um
    segundo é a mesma que aquele documenta: **a fusão é POR CAMPO**. Um override
    do disco dela hoje é `{"lightbar": [255, 0, 0]}` e nada mais; trocar a seção
    inteira por uma que só fale de cor apagaria o brilho próprio daquele
    controle. `save_profile` serializa com `exclude_unset`, então o que não foi
    tocado continua ausente do arquivo.

    NÃO DEVOLVE `None` QUANDO NADA MUDA, ao contrário do irmão, e é de
    propósito: aqui a escrita não é o pedido dela — é a **consequência** do
    pedido, e ela tem de acontecer nas duas hipóteses. Uma cor que por acaso já
    é a do override precisa continuar lá depois de o automático sair; devolver
    `None` faria o chamador achar que não havia o que gravar naquele controle e
    seguir sem ele.
    """
    from hefesto_dualsense4unix.profiles.schema import ControllerOverrides, LedsConfig

    chave = chave_do_override(uniq)
    atuais = dict(prof.controllers or {})
    dele = atuais.get(chave) or ControllerOverrides()
    antes = dele.leds
    novos = (LedsConfig(lightbar=rgb) if antes is None
             else antes.model_copy(update={"lightbar": rgb}))
    atuais[chave] = dele.model_copy(update={"leds": novos})
    return prof.model_copy(update={"controllers": atuais})


#: O QUE O CARTÃO DIZ QUANDO O AUTOMÁTICO SAI. A frase é do PRODUTO e nasce
#: aqui porque é aqui que o ato mora — não há dono anterior: a janela GTK
#: desliga este mesmo campo sem gravar cor nenhuma, que é justamente o caminho
#: que a D-13 recusou. Ela conta as DUAS metades do que aconteceu, porque as
#: duas foram feitas no mesmo clique e a segunda é a que ela aceitou por
#: escrito: *"ok aceito o caminho"*.
_RECADO_DO_AUTOMATICO_SAIU = (
    "Cores automáticas desligadas. Guardei a cor de cada controle no perfil, "
    "para nenhuma se perder e nenhuma se repetir.")

#: E QUANDO ELE VOLTA. Curta porque não há consequência a confessar: as cores
#: gravadas continuam no perfil e a camada automática passa a vencer no merge
#: por campo do backend — nada se apaga.
_RECADO_DO_AUTOMATICO_VOLTOU = (
    "Cores automáticas ligadas. Cada controle volta a acender a cor do número "
    "dele.")


@gesto("04-iluminacao.html", "auto-cores", grava="gravar_e_reaplicar")
def auto_cores(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any] | None:
    """O interruptor do "Cores automáticas por controle" — e ele MUDA o perfil.

    **DECISÃO DELA, 04/09/2026 (D-13), contra a recomendação escrita.** A lista
    desta aba propunha que o botão "Automático" só MOSTRASSE o estado, e que
    mudá-lo continuasse na aba Perfis. Ela recusou as duas primeiras opções e
    escolheu a terceira, com estas palavras:

        *"Um interruptor no topo da aba Iluminação."*

    Mostrar sem poder mudar é menos do que ela pediu — e o campo é o martelo
    mais pesado desta aba: ele governa a paleta automática **e** a numeração,
    inclusive a dos controles de outras marcas.

    **A CONTRADIÇÃO QUE ELE ABRE, E O CAMINHO QUE ELA ACEITOU.** A regra dela de
    03/09 é *"nenhuma cor dos controles nunca pode ser a mesma"*. Com o
    automático desligado, um controle que chega depois não tem cor própria e cai
    na cor GLOBAL do perfil — o seguinte também, e dois ficam iguais. Hoje isso
    não acontece só porque não HÁ como desligar o automático pela interface
    nova; o interruptor tira essa proteção acidental. Ofereci avisar, recusar ou
    gravar, e ela respondeu:

        *"ok aceito o caminho"*

    **Então desligar GRAVA a cor de cada controle no ato.** O automático sai,
    nenhuma cor se perde e nenhuma se repete, e o produto nunca precisa dizer
    não a ela.

    **A ORDEM É A DA GTK, e ela está medida lá:** os overrides por MAC vão
    ANTES da mudança global (`lightbar_actions._persist_leds_update`, a nota da
    R-14). Aqui os dois caem no MESMO `save_profile`, então a ordem não é de
    escrita e sim de LEITURA: a cor de cada controle é lida com o automático
    ainda valendo, que é o único instante em que ela existe para ser guardada.

    **NÃO SE DEDUZ O ESTADO DO CLIQUE, PERGUNTA-SE AO DISCO.** O `value` de um
    `<input type="checkbox">` é a string `"on"` em qualquer estado, e o piloto
    manda o `value` — não o `checked`. Ler o clique daria sempre a mesma
    resposta. O disco é a fonte que a tela já pinta a cada tique
    (`automatico_do_perfil`), então virar o que está lá é o único jeito de o
    interruptor e o perfil nunca discordarem.

    **O `click` NÃO É UM SEGUNDO PEDIDO.** Um checkbox dispara `click` e
    `change` no mesmo ato, e o BOOTSTRAP escuta os dois. Sem o guarda,
    UM clique dela viraria DUAS inversões — e o interruptor voltaria sozinho ao
    lugar, com duas gravações no perfil pelo caminho. `_so_abriu_o_seletor` já é
    exatamente esse guarda: ele descarta o `click` de todo `<input>` e deixa o
    `change`, que é o que carrega o ato.

    **REAPLICAR É METADE DO GESTO**, e sem ela ele seria o botão que aceita o
    toque e não age: `auto_player_colors` só entra em vigor na ATIVAÇÃO do
    perfil (`ProfileManager._configure_auto_player_colors`, chamado por
    `apply_profile`). `perfil.gravar_e_reaplicar` é o dono dos três tempos —
    disco, `profile.switch`, `launch_env.refresh` — e já tinha dois chamadores.

    E AQUI REAPLICAR NÃO DESFAZ ESCOLHA VIVA DELA, que é a razão pela qual o
    gesto `brilho` o recusa: as cores que o `switch` vai reaplicar são as que
    este mesmo gesto acabou de gravar, controle a controle. O que ele pinta é o
    que já estava aceso.

    :return: `{"recado": …}` — o cartão verde da D-01, dizendo qual das duas
        metades aconteceu.
    """
    if _so_abriu_o_seletor(o):
        return None

    nome = str(ctx.state.get("active_profile") or "").strip()
    if not nome:
        raise RuntimeError(
            "não há perfil ativo agora, e as cores automáticas são do perfil — "
            "não da máquina. Escolha um perfil na aba Perfis.")

    loader = perfil._com_o_src()
    prof = loader.load_profile(nome)
    cru = perfil.ativo(nome)
    ligado = automatico_do_perfil(cru)

    if ligado:
        #: AS CORES PRIMEIRO, e com o automático AINDA valendo — ver a ordem na
        #: docstring. Só os CONECTADOS: um controle que não está na mesa não tem
        #: cor de agora a guardar, e inventar uma seria escrever no perfil dela
        #: um valor que ninguém escolheu.
        for c in ctx.conectados:
            uniq = str(c.get("uniq") or "")
            if uniq:
                prof = _com_a_cor_gravada(prof, uniq, _a_cor_de_agora(ctx, cru, c))

    leds = prof.leds.model_copy(update={"auto_player_colors": not ligado})
    perfil.gravar_e_reaplicar(prof.model_copy(update={"leds": leds}), ctx, p)
    return {"recado": (_RECADO_DO_AUTOMATICO_SAIU if ligado
                       else _RECADO_DO_AUTOMATICO_VOLTOU)}


#: O MÉTODO QUE RECONCILIA O CO-OP — ver `_acender_o_numero`. Ele tem teto
#: declarado na ponte (`ponte.TETOS["coop.sync"] = 2.0`), e é preciso: um ciclo
#: cheio do co-op pode derrubar e recriar um vpad, e o teto padrão de 250 ms do
#: `_safe_call` devolveria `False` com o trabalho feito.
_RECONCILIAR_O_COOP = "coop.sync"


def _pares_da_troca(ctx: Contexto, uniq: str, n: int) -> list[tuple[str, int]]:
    """Quem fica com que número DEPOIS da troca — o alvo e o parceiro dele.

    `identity.number.set` **PERMUTA**: o alvo vai para o número pedido e quem
    tinha aquele número fica com o do alvo, e mais ninguém se mexe. Está no
    daemon (`_set_number_locked`: *"trocar de lugar o alvo e quem tem o número
    pedido — os dois, e mais ninguém"*) e está nos dezessete lugares do desenho
    que ela aprovou (*"Os dois trocam, os outros não se mexem"*).

    POR QUE O PARCEIRO ENTRA, e ele não é zelo: as cinco lâmpadas de um
    controle preso num override velho continuariam acesas no número que o
    OUTRO acabou de receber — dois controles com o mesmo desenho, que é
    exatamente a colisão que a numeração única (R-24) existe para matar.
    Curar só o alvo trocaria uma queixa por outra, na mesma tela.

    A CONTA É DAQUI E NÃO DO DAEMON porque a resposta não a traz: o
    `identity.number.set` devolve `changed` com quem mudou de lugar, e
    `ipc_bridge.identity_number_set` reduz tudo a `(ok, motivo)`. Ler o
    `state_full` DEPOIS seria mais fiel; custa uma volta ao daemon e um dublê
    que saiba responder. **RELATADO:** uma `identity_number_set_detalhado`
    que entregue o `changed` é `app/ipc_bridge.py`, fora deste arquivo.

    Números saem de `_numero` — o dono único (`app/actions/base`), o MESMO que
    pinta a fileira de botões. Sem parceiro (número livre na mesa) a lista tem
    um par só, e é o caso da mesa de um controle.
    """
    velho = 0
    parceiro = ""
    for c in ctx.conectados:
        chave = str(c.get("uniq") or "")
        if not chave:
            continue
        numero = _numero(ctx, c)
        if chave == uniq:
            velho = numero
        elif numero == n:
            parceiro = chave
    pares = [(uniq, n)]
    if parceiro and velho:
        pares.append((parceiro, velho))
    return pares


def _acender_o_numero(ctx: Contexto, p: Any, uniq: str, n: int) -> None:
    """As cinco lâmpadas SEGUEM o número que ela acabou de escolher.

    **A QUEIXA DELA, 04/09/2026:** *"escolha do jogador no iluminação não
    funciona"*. O gesto renumerava e parava aí — e renumerar não move lâmpada
    nenhuma por conta própria. Medido na mesa dela, com os dois DualSense
    ligados e o daemon vivo, lendo `/sys/class/leds` a cada passo::

        estado de partida            slot=2 → lâmpadas do 2 · slot=1 → do 1
        1. identity.number.set       slot=1 → lâmpadas do 2 · slot=2 → do 1   ✗
        2. + led.player_set por uniq slot=1 → lâmpadas do 2 · slot=2 → do 1   ✗
        3. + coop.sync               slot=1 → lâmpadas do 1 · slot=2 → do 2   ✓

    **A LINHA 2 É O ACHADO, e ela derruba a cura óbvia.** O daemon respondeu
    `{"status":"ok","aplicado_em":["<o controle>"],"guardado_em":[]}` às DUAS
    escritas — e nenhuma lâmpada se mexeu. O byte saiu; a camada do co-op o
    repintou por cima no mesmo instante, porque no merge por campo do backend
    (`core/backend_pydualsense._merged_desired_for_key`) ela está ACIMA do
    override por-uniq::

        default global < camada AUTOMÁTICA < override por-uniq < CO-OP < jogo

    Escrever o override e ler o `aplicado_em` como sucesso teria posto na tela
    dela um "aplicado" sobre duas lâmpadas paradas — a mesma mentira que a
    MESA-CHEIA-09 mediu na janela GTK, reproduzida aqui.

    **POR QUE A CAMADA DO CO-OP FICA VELHA, e é o defeito de fundo.** Ela é um
    mapa PUBLICADO, não uma leitura: `coop._apply_coop_player_leds` calcula
    `numeros_de_jogador()` — que pergunta o número ao MESMO
    `identity_registry` que o `identity.number.set` acabou de escrever — e
    publica o resultado em `_desired_coop_by_uniq`. Só que ele roda no fim de
    um ciclo CHEIO do co-op, e um ciclo cheio pede `/dev/input` ter mudado, ou
    um grab degradado, ou `force`. Renumerar não é nenhum dos três. O
    `reassert_resolved_outputs()` que o próprio handler dispara reafirma então
    a camada VELHA, com os números de antes — e ela fica assim até o próximo
    hotplug. Na mesa dela estava assim quando esta medição começou.

    **RELATADO, e a cura estrutural é de UMA linha, no daemon:** o
    `_handle_identity_number_set` já adianta duas repinturas no ramo `changed`
    (`reassert_resolved_outputs` e `_schedule_external_tick`); falta a
    terceira, `get_coop_manager(daemon).sync(force=True)` — ou o
    `_apply_coop_player_leds` direto. É `daemon/ipc_handlers.py`, fora do
    território deste arquivo, e com ela este ramo daqui vira redundância
    barata em vez de cura.

    **OS DOIS RAMOS, e cada um trata do dono das lâmpadas naquele momento:**

    * **o co-op manda** (`o_coop_manda`: mais de um jogador na mesa) — quem
      escreve as cinco luzes é a camada dele, e a ÚNICA coisa que a move é
      recalculá-la. `coop.sync` é o gesto que o produto já tem para isso, e a
      docstring dele é explícita: *"Não liga nem desliga nada"*, *"reconciliar
      nunca ressuscita o que o jogo suspendeu"*. Escrever o override aqui
      seria escrever debaixo de quem manda;
    * **o co-op não manda** — sobra a camada automática, e ela SEGUE o número
      sozinha no `reassert` do handler… a menos que um override por-uniq esteja
      preso acima dela. É o que a janela GTK deixa para trás toda vez que ela
      usa "Desenho do PN" (`lightbar_actions._enviar_player_leds`), e ela USA a
      GTK. Aqui o override é reescrito com o padrão do número de AGORA, pelo
      dono da tabela (`core/led_control.player_led_pattern`, a mesma que o
      daemon acende e a mesma que `luzinhas` desenha nesta aba).

    **O PREÇO DO SEGUNDO RAMO, escrito porque ele é real:** um override
    por-uniq PRENDE as lâmpadas acima da camada automática, e daí em diante um
    controle que saia da mesa não faz mais os outros reacenderem sozinhos. É o
    mesmo preço que a GTK já paga desde sempre, e não há IPC que limpe o
    override (`lightbar.reset` é da barra, não das lâmpadas). Ele só se paga
    quando o co-op não manda — no ramo de cima nenhum override é escrito.

    A ORDEM É RENUMERAR PRIMEIRO, e ela decide o desfecho: o padrão das
    lâmpadas é função do número NOVO, então sem o número não há o que acender.
    E se a renumeração passar e a lâmpada não, **a renumeração VALE** — ela já
    está gravada no registro, desfazê-la seria uma segunda escrita que também
    pode falhar, e o cartão diz o que aconteceu com as luzes. O contrário —
    calar sobre a lâmpada — é o silêncio que esta casa nomeia como a mentira.
    """
    from hefesto_dualsense4unix.core.led_control import player_led_pattern

    if o_coop_manda(ctx.state):
        if not p.chamar(_RECONCILIAR_O_COOP):
            raise RuntimeError(
                f"o número deste controle mudou para {n}, mas as cinco "
                f"lâmpadas não acompanharam: com o co-op ligado quem as "
                f"acende é ele, e o Hefesto não respondeu ao pedido de "
                f"reconciliar os controles. {sem_resposta_do_daemon()}")
        return

    for alvo, numero in _pares_da_troca(ctx, uniq, n):
        bits = tuple(player_led_pattern(numero))
        corpo = p.player_leds_set_detalhado(bits, uniq=alvo)
        if corpo is None:
            raise RuntimeError(sem_resposta_do_daemon())
        _cobrar_a_frase_do_desenho(ctx, alvo, bits, corpo)


def _cobrar_a_frase_do_desenho(ctx: Contexto, uniq: str,
                               bits: tuple[bool, ...], corpo: Any) -> None:
    """Levanta com a frase da GTK quando o desenho NÃO foi para o aparelho.

    NADA DE TEXTO NASCE DESTE LADO, e é o mesmo contrato de `_escrever_a_cor`:
    quem compõe é `lightbar_actions._msg_do_desenho`, o dono ÚNICO da frase do
    desenho das cinco luzes desde a MESA-CHEIA-09/E3 — três caminhos da janela
    GTK passam por ele. Ele é chamado DESLIGADO da instância, com o mesmo
    `_Janela` que a frase da cor já usa: o método lê o estado por funções de
    `app/textos_de_aplicacao` que interrogam um objeto qualquer por `getattr`,
    e o único degrau que ele pede a mais é o `_quantos_recebem_o_desenho` — ver
    lá por que ele é zero nesta aba.

    OS TRÊS ARGUMENTOS DE TEXTO SÃO OS DO GÊMEO — `descricao` de  # (argumento) noqa-acento
    `_descreve_player_leds`, `feito="atualizado"`, `fazer="atualizar"`. É o
    que a GTK passa em `_set_player_leds`, que é para onde vão os botões
    "Desenho do PN" dela; passar outra coisa faria as duas telas do mesmo
    produto contarem o mesmo evento com palavras diferentes.

    **A FRASE FELIZ É PERGUNTADA, NUNCA DIGITADA**, e essa é a diferença para o
    `_escrever_a_cor`: lá o par `(assunto, frase feliz)` existe como constante
    na GTK e se lê de lá; aqui ele é montado DENTRO do `_msg_do_desenho` e não
    tem nome público. Digitá-lo deste lado seria a segunda escrita da mesma
    frase — o defeito que a RADAR-01 mediu. Então pergunta-se ao dono: o MESMO
    método, com um corpo sinteticamente feliz (`aplicado_em` com um destino),
    devolve exatamente o que ele diria se tudo tivesse dado certo. Comparar
    contra isso é perguntar *"a frase que saiu é a do caminho feliz?"* sem
    conhecer uma sílaba dela.

    O CORPO SINTÉTICO NÃO É UM DUBLÊ DO DAEMON: ele nunca vai ao aparelho e
    nunca é lido como resposta. É a pergunta *"o que você diria no melhor
    caso, para este controle, com este desenho?"* — e as duas chamadas usam o
    MESMO `_Janela`, então toda pendência do estado (Modo Nativo, alvo fora da
    mesa) vale igual nas duas e não some na comparação.

    ESTE CAMINHO SÓ CORRE COM O CO-OP FORA. Com ele ligado, `_acender_o_numero`
    volta antes — e é bom que volte: o ramo do co-op no `_msg_do_desenho`
    responde a mesma frase para os dois corpos, e a comparação ficaria cega.
    """
    from hefesto_dualsense4unix.app.actions.lightbar_actions import (
        LightbarActionsMixin,
    )

    janela = _janela_do_desfecho(ctx, uniq, _nome_da_coluna(ctx, uniq))
    descricao = LightbarActionsMixin._descreve_player_leds(bits)

    def diz(qual: Any) -> str:
        return str(LightbarActionsMixin._msg_do_desenho(
            janela, ok=True, motivo=None, corpo=qual, descricao=descricao,
            feito="atualizado", fazer="atualizar"))

    feliz = diz({"status": "ok", "aplicado_em": [uniq], "guardado_em": []})
    frase = diz(corpo)
    if frase != feliz:
        raise RuntimeError(frase)


@gesto("04-iluminacao.html", "player")
def player(ctx: Contexto, o: dict[str, Any], p: Any) -> None:
    """"Dar o Player N a este controle" — o número E as cinco lâmpadas.

    NÃO é `identity.renumber`, e a diferença está escrita no
    `app/ipc_bridge.py:712`: o `renumber` COMPACTA todos preservando a ordem
    relativa, e mora na aba Início. Dizer "este controle é o 2" foi o comando
    que faltou ao projeto até 25/07.

    A FUNÇÃO DEVOLVE `(ok, motivo)`, e o motivo já vem traduzido para frase de
    tela (`_MOTIVOS_NUMERO`): "O jogo está aberto", "Esse número é maior do que
    a quantidade de controles ligados". Levantar com ele é o que faz o botão
    RECUSAR DIZENDO em vez de falhar calado.

    **ELE ERA MEIO GESTO ATÉ 04/09/2026**, e a metade que faltava é a que ela
    olha: `identity.number.set` troca o NÚMERO EXIBIDO, e as cinco lâmpadas do
    controle não vêm com ele. Ver `_acender_o_numero` para o que foi medido na
    mesa dela — inclusive a razão de a cura óbvia (escrever o desenho por
    `uniq`) não funcionar com o co-op ligado.
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
    _acender_o_numero(ctx, p, uniq, n)


# ---------------------------------------------------------------------------
# AS CINCO LUZES DE JOGADOR — LUZES-01, 06/09/2026
#
# A QUEIXA QUE ABRIU A SPRINT, e ela é do CSV da paridade: *"SEMPRE junto com a
# renumeração, nunca sozinhos"*. Dar a este controle o desenho do P3 mantendo o
# número dele era impossível pelo HTML — toda escrita de lâmpada vinha de carona
# num `identity.number.set`. Os quatro gestos abaixo são o caminho SEM o número.
#
# NADA DE GUARDA ANTI-RAJADA AQUI, e a ausência é DECLARADA. A da janela GTK
# (`lightbar_actions.on_player_led_toggled`, o `_player_leds_batch_guard`) existe
# porque lá um preset MEXE NOS CINCO CHECKBOXES, e cada `toggled` dispararia um
# IPC — cinco pedidos para um clique. Aqui a forma é outra: um clique é um
# bitmask e um `player_leds_set_detalhado`, e o preset é UM clique. A guarda não
# tem o que guardar; escrevê-la seria copiar a forma sem o defeito.
# ---------------------------------------------------------------------------


def _leds_sem(antes: Any, campos: set[str]) -> Any:
    """Um `LedsConfig` de override SEM os campos pedidos — e sem os densificar.

    **É `model_dump(exclude_unset=True)` E NÃO `model_copy`, e a diferença é o
    ponto inteiro.** `profiles/manager._controllers_to_specs` só põe no
    `OutputSpec` os campos que estão em `model_fields_set`; um `model_copy` com
    `update={"player_leds": None}` deixaria a chave MARCADA como escrita, e o
    esquema recusa `None` ali. Reconstruir a partir do `dump` sem a chave é o
    único jeito de o campo voltar a ser *"sem opinião"* — que é o que faz a
    camada AUTOMÁTICA voltar a vencer no merge por campo do backend.

    E É POR AQUI QUE O OVERRIDE **SAI**, não zera: `LedsConfig(player_leds=[False]*5)`
    é uma escolha explícita de deixar as cinco apagadas, e o backend a respeita
    como qualquer outra. Ver `devolver_o_desenho_ao_automatico`.
    """
    from hefesto_dualsense4unix.profiles.schema import LedsConfig

    dados = {k: v for k, v in (antes.model_dump(exclude_unset=True)
                               if antes is not None else {}).items()
             if k not in campos}
    return LedsConfig(**dados)


def _com_o_desenho_gravado(prof: Any, uniq: str,
                           bits: tuple[bool, ...] | None) -> Any:
    """O perfil com o desenho DESTE controle escrito no override dele.

    É O TERCEIRO IRMÃO de `_com_o_brilho_gravado` e `_com_a_cor_gravada`, e a
    razão de ser um terceiro é a que os dois já documentam: **a fusão é POR
    CAMPO**. Um override do disco dela hoje é `{"lightbar": [255, 0, 0]}` e nada
    mais; trocar a seção inteira por uma que só fale de desenho apagaria a cor e
    o brilho que ela escolheu para aquele controle.

    POR QUE GRAVAR, se o desenho já foi ao aparelho: porque **esta tela não vê o
    que foi ao aparelho**. O `state_full` não publica `player_leds` (a medição
    está em `desenho_gravado`), então sem a gravação o tique seguinte repintaria
    o padrão do número por cima da escolha dela — o clique acenderia a lâmpada e
    a tela a apagaria um décimo de segundo depois.

    :param bits: os cinco booleanos, ou `None` para **tirar** o campo do
        override — que é o caminho de volta ao automático, e não o mesmo que
        gravar cinco falsos.
    """
    from hefesto_dualsense4unix.profiles.schema import ControllerOverrides, LedsConfig

    chave = chave_do_override(uniq)
    atuais = dict(prof.controllers or {})
    dele = atuais.get(chave) or ControllerOverrides()
    antes = dele.leds
    if bits is None:
        novos = _leds_sem(antes, {"player_leds"})
    else:
        lista = [bool(b) for b in bits]
        novos = (LedsConfig(player_leds=lista) if antes is None
                 else antes.model_copy(update={"player_leds": lista},
                                       deep=False))
        if antes is not None:
            #: `model_copy` NÃO MARCA O CAMPO como escrito, e sem a marca o
            #: `_controllers_to_specs` o ignora e o `save_profile` o omite —
            #: a gravação sairia silenciosamente vazia. É a mesma pegadinha que
            #: `_leds_sem` explora do lado inverso.
            novos.model_fields_set.add("player_leds")
    atuais[chave] = dele.model_copy(update={"leds": novos})
    return prof.model_copy(update={"controllers": atuais})


def _perfil_ativo_ou_recusa(ctx: Contexto, oque: str) -> str:
    """O nome do perfil ativo, ou a recusa que DIZ — como o `auto_cores` já faz."""
    nome = str(ctx.state.get("active_profile") or "").strip()
    if not nome:
        raise RuntimeError(
            f"não há perfil ativo agora, e {oque} é do perfil — não da "
            f"máquina. Escolha um perfil na aba Perfis.")
    return nome


def _o_coop_recusa(ctx: Contexto) -> None:
    """Com o co-op ligado, quem acende as cinco luzes é ele — e a tela diz isso.

    A MEDIÇÃO É A DE `_acender_o_numero`, e ela não se repete aqui: a camada do
    co-op está ACIMA do override por-`uniq` no merge por campo do backend, então
    escrever o desenho aqui seria **escrever debaixo de quem manda** — o daemon
    responderia `aplicado_em` e as lâmpadas não se moveriam. Foi exatamente esse
    "aplicado" sobre lâmpadas paradas que a mesa dela mediu em 04/09.

    RECUSAR DIZENDO é a resposta desta casa para o que o produto não faz, e aqui
    ela é ainda a mais barata: o caminho que MOVE as luzes com o co-op ligado já
    existe e é outro — dar o número ao controle (`player`), que reconcilia a
    mesa pelo `coop.sync`.
    """
    if o_coop_manda(ctx.state):
        raise RuntimeError(
            "um jogo em co-op está mandando nas cinco luzes deste controle — "
            "enquanto ele estiver, o desenho vem do jogo e não daqui. Para "
            "mudar quem é quem agora, use os números da linha Jogador.")


def _escrever_o_desenho(ctx: Contexto, p: Any, uniq: str,
                        bits: tuple[bool, ...]) -> None:
    """O CAMINHO ÚNICO de escrita das cinco luzes — disco e aparelho, nesta ordem.

    UM SÓ, pela mesma razão que `_escrever_a_cor` é um só para as quatro portas
    de cor: quatro rotas paralelas divergiriam no primeiro ajuste, e a primeira
    coisa a se perder seria a leitura do desfecho.

    A ORDEM É DISCO E DEPOIS APARELHO, e é a do gesto `brilho`. Ela decide o que
    acontece quando o fio falha: a escolha dela fica na tela e no perfil, o
    cartão diz que o aparelho não recebeu, e o "Aplicar o desenho" (o clique no
    próprio indicador) é a tentativa seguinte. O contrário — mandar primeiro e
    gravar depois — perderia a escolha exatamente no caso em que ela precisa ser
    guardada.

    A FRASE DO DESFECHO É A DA GTK, perguntada ao dono: `_cobrar_a_frase_do_desenho`
    compara o que `lightbar_actions._msg_do_desenho` diria no caminho feliz com
    o que ele diz para o corpo real. Nenhuma sílaba de texto nasce deste lado.
    """
    _o_coop_recusa(ctx)
    nome = _perfil_ativo_ou_recusa(ctx, "o desenho das luzes de jogador")
    loader = perfil._com_o_src()
    loader.save_profile(_com_o_desenho_gravado(loader.load_profile(nome),
                                               uniq, tuple(bits)),
                        origem="interface-nova")
    corpo = p.player_leds_set_detalhado(tuple(bits), uniq=uniq)
    if corpo is None:
        raise RuntimeError(sem_resposta_do_daemon())
    _cobrar_a_frase_do_desenho(ctx, uniq, tuple(bits), corpo)


#: O QUE O CARTÃO DIZ QUANDO O DESENHO VOLTA AO AUTOMÁTICO. Ela conta as duas
#: metades porque as duas aconteceram no mesmo clique — o override saiu, e quem
#: passa a mandar é o número.
_RECADO_DO_DESENHO_AUTOMATICO = (
    "Luzes de jogador no automático. O desenho próprio deste controle saiu do "
    "perfil, e o número dele volta a mandar nas cinco.")


def devolver_o_desenho_ao_automatico(ctx: Contexto, p: Any, uniq: str) -> None:
    """"Todas apagadas": o override **SAI**, e não fica zerado.

    **ESTE É O CAMINHO DE VOLTA, e até hoje ele não existia no HTML.** Com o
    co-op fora, toda escrita de lâmpada grava um override por-`uniq` que fica
    ACIMA da camada automática no merge do backend — as cinco lâmpadas ficam
    PRESAS, e um controle que saia da mesa não faz mais os outros reacenderem
    sozinhos. O preço está escrito em `_acender_o_numero`; o que faltava era a
    porta de saída.

    **GRAVAR `[False] * 5` NÃO É O CAMINHO DE VOLTA — é o oposto**, e foi medido
    no motor antes de virar código: `manager._controllers_to_specs` monta o
    `OutputSpec` a partir de `model_fields_set`, então cinco falsos EXPLÍCITOS
    são uma escolha que o backend respeita, e as lâmpadas ficariam presas
    apagadas. O que solta é o campo deixar de existir (`_leds_sem`).

    **E O DAEMON PRECISA OUVIR, senão só o disco muda.** A cadeia inteira é a do
    `profile.switch`, e ela solta as DUAS camadas:

    * `ProfileManager.apply(origin="manual")` chama `clear_user_output_overrides()`
      — é o único caminho que solta a camada da USUÁRIA, onde o
      `player_leds_set_detalhado` escreveu (`manager.py:425`, R-20);
    * `reset_profile_overrides(overrides)` republica a camada do PERFIL sem o
      campo, e `reassert_resolved_outputs()` repinta o resolvido — que agora é a
      camada automática, isto é, o padrão do número deste controle.

    `perfil.gravar_e_reaplicar` é o dono dos três tempos (disco, `profile.switch`,
    `launch_env.refresh`) e já tinha seis chamadores. Não se refaz aqui.

    E NADA VAI AO FIO POR ESTE CAMINHO: mandar `player_leds_set_detalhado((False,)*5)`
    antes do switch reescreveria a camada da usuária que a linha seguinte existe
    para soltar — o override sairia e voltaria no mesmo clique.
    """
    _o_coop_recusa(ctx)
    nome = _perfil_ativo_ou_recusa(ctx, "o desenho das luzes de jogador")
    loader = perfil._com_o_src()
    prof = _com_o_desenho_gravado(loader.load_profile(nome), uniq, None)
    perfil.gravar_e_reaplicar(prof, ctx, p)


@gesto("04-iluminacao.html", GESTO_DA_LAMPADA, grava="save_profile")
def luzes(ctx: Contexto, o: dict[str, Any], p: Any) -> None:
    """Uma das cinco luzes de jogador acende ou apaga — **sem tocar no número**.

    É A LINHA `Marcar/desmarcar cada uma das 5 luzes de jogador` do CSV da
    paridade, e o gêmeo dela na janela estável é `on_player_led_toggled`.

    O ESTADO DE PARTIDA VEM DO DADO, e não de memória do gerador nem do clique:
    `desenho_de_agora` lê o override do perfil e, na falta dele, o padrão do
    número — a mesma escada que a tela pinta a cada tique. Ler o `aria-pressed`
    do botão daria a resposta da TELA, que é a mesma coisa só enquanto ninguém
    mexer no perfil por outro caminho.

    E O NÚMERO NÃO ENTRA: nenhum `identity_number_set` sai daqui. É a diferença
    inteira entre este gesto e o `player`, e é o que a régua desta sprint morde.
    """
    uniq = _uniq(o)
    if not uniq:
        raise ValueError("luzes: o clique não disse em qual controle")
    try:
        n = int(str(o.get("lampada") or "0"))
    except ValueError:
        n = 0
    if not 1 <= n <= 5:
        raise ValueError(
            f"luzes: preciso saber qual das cinco luzes (veio {n})")
    nome = _perfil_ativo_ou_recusa(ctx, "o desenho das luzes de jogador")
    dele = ctx.por_uniq(uniq) or {"uniq": uniq}
    bits = list(desenho_de_agora(perfil.ativo(nome), uniq, _numero(ctx, dele)))
    bits[n - 1] = not bits[n - 1]
    _escrever_o_desenho(ctx, p, uniq, tuple(bits))


@gesto("04-iluminacao.html", GESTO_DO_DESENHO_DE, grava="save_profile")
def desenho_de(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any] | None:
    """As seis teclas de desenho: os quatro números, "todas" e "nenhuma".

    **O NOME ENGANA, e o CSV avisa de propósito:** os botões `1 2 3 4` da linha
    Jogador e as teclas `P1..P4` desta linha *parecem a mesma coisa e são
    opostos*. Aquele DÁ o número (e as lâmpadas vão junto); esta dá o DESENHO do
    número e não mexe no número nenhum. A janela estável diz isso no próprio
    `title` desde sempre — *"Não muda o número deste controle"* — e a frase foi
    lida de lá, não inventada aqui.

    A TABELA É DO DAEMON: `core/led_control.player_led_pattern`, a mesma que o
    daemon acende, que cobre 1..8 e que `monta.luzinhas` desenha. Uma segunda
    cópia dela já custou a esta casa quatro botões da GTK pintando o desenho
    antigo sem um único teste vermelho (L9, `aplicar_desenho_do_jogador`).

    :return: `{"recado": …}` só no ramo "nenhuma", que é o único cujo efeito não
        se vê no próprio botão — o cartão conta que o override saiu.
    """
    from hefesto_dualsense4unix.core.led_control import player_led_pattern

    uniq = _uniq(o)
    if not uniq:
        raise ValueError("desenho-de: o clique não disse em qual controle")
    qual = str(o.get("desenho") or "").strip().lower()
    if qual == NENHUMA:
        devolver_o_desenho_ao_automatico(ctx, p, uniq)
        return {"recado": _RECADO_DO_DESENHO_AUTOMATICO}
    if qual == TODAS:
        _escrever_o_desenho(ctx, p, uniq, (True,) * 5)
        return None
    try:
        n = int(qual)
    except ValueError:
        n = 0
    if not 1 <= n <= 8:
        raise ValueError(
            f"desenho-de: preciso do desenho de um jogador de 1 a 8, de "
            f"{TODAS!r} ou de {NENHUMA!r} (veio {qual!r})")
    _escrever_o_desenho(ctx, p, uniq, tuple(player_led_pattern(n)))
    return None


@gesto("04-iluminacao.html", GESTO_DO_REENVIO_DO_DESENHO)
def reenviar_desenho(ctx: Contexto, o: dict[str, Any], p: Any) -> None:
    """O indicador das cinco lâmpadas é o botão: o desenho vai ao controle de novo.

    O GÊMEO DA CAIXA `#RRGGBB`, e a decisão é a mesma dela ([03], 04/09/2026):
    *"A caixa do hexadecimal vira o botão."* Na janela estável isto é o botão
    "Aplicar LEDs" (`on_player_leds_apply`), e serve para o mesmo: depois de
    reconectar o controle ou trocar de perfil, reemitir o bitmask sem mudar
    nada.

    **ELE NÃO GRAVA, e a ausência é a escolha.** Reenviar não é uma escolha
    nova — é repetir a que já está na tela. Gravar aqui criaria um override para
    um controle que talvez não tivesse nenhum: quem só está exibindo o padrão
    automático do número passaria a tê-lo PRESO por um clique cujo texto promete
    "de novo". A camada da usuária que o `player_leds_set_detalhado` escreve no
    daemon é solta pelo próximo `profile.switch`, e o valor dela é, nesse caso,
    exatamente o que o automático daria.

    O TRAVESSÃO É RECUSA, como no `reenviar` da cor: numa coluna sem controle o
    molde do lugar sem dono não emite este bloco, e esta guarda é a segunda
    trava — a que vale se alguém alcançar o gesto por outro caminho.
    """
    uniq = _uniq(o)
    if not uniq:
        raise ValueError("reenviar-desenho: o clique não disse em qual controle")
    _o_coop_recusa(ctx)
    nome = _perfil_ativo_ou_recusa(ctx, "o desenho das luzes de jogador")
    dele = ctx.por_uniq(uniq) or {"uniq": uniq}
    bits = desenho_de_agora(perfil.ativo(nome), uniq, _numero(ctx, dele))
    corpo = p.player_leds_set_detalhado(bits, uniq=uniq)
    if corpo is None:
        raise RuntimeError(sem_resposta_do_daemon())
    _cobrar_a_frase_do_desenho(ctx, uniq, bits, corpo)


#: O QUE O CARTÃO DIZ DEPOIS DO "Todos no automático". A frase é do PRODUTO e
#: conta o que a da GTK conta (`on_lightbar_auto_reset_all`: *"Cores automáticas
#: religadas para todos os controles"*), sem a metade que só vale lá — *"aplique
#: ou salve o perfil para valer"*. Aqui vale na hora: `gravar_e_reaplicar` grava
#: e manda o daemon reaplicar no mesmo clique, que é a lei desta interface desde
#: a D-01 (*"clicar já aplica e já grava"*).
_RECADO_DO_AUTOMATICO_DE_TODOS = (
    "Cores automáticas religadas para todos os controles. As cores próprias "
    "saíram do perfil, e cada controle volta a acender a cor do número dele.")


@gesto("04-iluminacao.html", GESTO_DO_AUTOMATICO_DE_TODOS, grava="gravar_e_reaplicar")
def automatico_de_todos(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any]:
    """"Todos no automático" — o único desfazer de uma vez que ela tem.

    O GÊMEO É `lightbar_actions.on_lightbar_auto_reset_all`, e o que ele faz
    está copiado CAMPO A CAMPO, não de memória: limpa `lightbar` e
    `lightbar_brightness` de TODOS os overrides por controle e religa
    `auto_player_colors`. **O desenho das cinco luzes e os gatilhos FICAM** — é
    o que a GTK preserva, e mexer neles aqui faria as duas telas do mesmo
    produto responderem coisas diferentes ao mesmo botão.

    POR QUE ELE PRECISOU EXISTIR: o CSV da paridade mediu o perfil dela e achou
    **dois `uniq` com `leds.lightbar` gravado**. Sem este botão, cada cor
    própria teria de ser desfeita por outro meio — e o HTML não tinha meio
    nenhum, porque não havia um só gesto de escopo global na aba.

    ELE MORA NA FAIXA DO TÍTULO, ao lado do interruptor da D-13, e pela mesma
    razão medida: a faixa tem 17px de altura e mais de mil de largura vaga, e a
    grade das colunas está a poucos pixels do teto. Um botão de escopo global
    dentro de uma coluna também mentiria sobre o alcance dele.

    O RÓTULO NÃO É "Voltar ao automático": essa é a frase LONGA que ela mandou
    encurtar em 31/08 (*"aonde tem Voltar ao automático deixa só Automático"*),
    e ela agora é o botão POR CONTROLE de cada coluna. Duas coisas diferentes na
    mesma tela não podem ter o mesmo nome.
    """
    nome = _perfil_ativo_ou_recusa(ctx, "as cores próprias de cada controle")
    loader = perfil._com_o_src()
    prof = loader.load_profile(nome)
    atuais = dict(prof.controllers or {})
    for chave, dele in list(atuais.items()):
        atuais[chave] = dele.model_copy(
            update={"leds": _leds_sem(dele.leds,
                                      {"lightbar", "lightbar_brightness"})})
    leds = prof.leds.model_copy(update={"auto_player_colors": True})
    perfil.gravar_e_reaplicar(
        prof.model_copy(update={"controllers": atuais, "leds": leds}), ctx, p)
    return {"recado": _RECADO_DO_AUTOMATICO_DE_TODOS}


#: AS FUNÇÕES DA PONTE QUE ESTA ABA USA. A régua confere que existem — um nome
#: inventado aparece aqui, e não na mão de quem clica.
#: A PORTA DA COR É A `_detalhado` DESDE 03/09/2026, e `led_set` saiu daqui: o
#: `bool` dela não carrega `aplicado_em`/`guardado_em`, e sem eles os três
#: gestos que escrevem cor diziam "aplicou" para um clique que não acendeu nada.
#: Ver `_escrever_a_cor`.
#: A PORTA DAS CINCO LÂMPADAS É A `_detalhado` DESDE 04/09/2026, e nasceu já
#: assim: o `player_leds_set` devolve `bool`, e um `True` dele significa só *"o
#: daemon respondeu"* — foi com um `aplicado_em` desses que a medição da mesa
#: dela mostrou duas lâmpadas paradas. Ver `_acender_o_numero`.
PONTE = {"led_set_detalhado", "identity_number_set",
         "player_leds_set_detalhado", "chamar", "profile_switch"}
#: `coop.sync` É O ÚNICO JEITO DE MOVER AS LÂMPADAS COM O CO-OP LIGADO —
#: medido, e o porquê está em `_acender_o_numero`.
METODOS = {"lightbar.reset", "coop.sync"}


#: O QUE ESTA ABA DECLARA À RÉGUA — o piso e as provas moram AQUI, e não no
#: teste, para que ligar uma aba não exija editar um arquivo que oito pessoas
#: editariam ao mesmo tempo.
PAGINA = "04-iluminacao.html"
#: 4 → 5 EM 03/09/2026: o `brilho` nasceu, e com ele o trilho passou a gravar.
#: O PISO SÓ SOBE, e uma queda não aparece na tela — o arraste simplesmente
#: deixaria de fazer alguma coisa, que é exatamente o que ele fazia antes.
#:
#: 5 → 7 EM 04/09/2026, com as decisões [02] e [03] dela: o `auto-cores`
#: (o interruptor da D-13) e o `reenviar` (a caixa do hexadecimal).
#:
#: 7 → 11 EM 06/09/2026, com a LUZES-01: as cinco lâmpadas ganharam gesto
#: próprio (`luzes`), as seis teclas de desenho ganharam o delas (`desenho-de`),
#: o indicador virou o botão de reenvio (`reenviar-desenho`) e a faixa do título
#: ganhou o escopo global (`auto-todos`). São as cinco linhas `FALTA_NO_HTML`
#: que o CSV da paridade cobrava desta aba.
PISO_DA_ABA = 11
PROVAS = [
    {"pagina": PAGINA, "gesto": "cor", "clique": {"hex": "#FF8000"},  # (noqa-acento) id
     "chama": [("led_set_detalhado", [(255, 128, 0)],
                {"uniq": "aa:bb:cc:00:00:01"})]},
    {"pagina": PAGINA, "gesto": "apagar", "clique": {},  # (noqa-acento) chave do contrato
     "chama": [("led_set_detalhado", [(0, 0, 0)],
                {"uniq": "aa:bb:cc:00:00:01"})]},
    # O REENVIO LÊ O TEXTO DA CAIXA, e o clique de prova o traz — é o mesmo
    # `textContent` que o piloto manda. Um `hex` aqui passaria pela porta
    # errada e a régua ficaria verde sobre um gesto que na tela não acha valor
    # nenhum: na caixa `#RRGGBB` não há `data-hex`, de propósito.
    {"pagina": PAGINA, "gesto": "reenviar", "clique": {"texto": "#12AB34"},  # (noqa-acento) id
     "chama": [("led_set_detalhado", [(18, 171, 52)],
                {"uniq": "aa:bb:cc:00:00:01"})]},
    # DUAS chamadas, e a ordem importa: largar o claim e SÓ ENTÃO pintar.
    {"pagina": PAGINA, "gesto": "auto", "clique": {},  # (noqa-acento) chave do contrato
     "chama": [("chamar", ["lightbar.reset"], {"uniq": "aa:bb:cc:00:00:01"}),
               ("led_set_detalhado", [(0, 0, 255)],
                {"uniq": "aa:bb:cc:00:00:01"})]},
    # DUAS chamadas, e a ordem é o desfecho: sem o número novo não há padrão
    # de lâmpada a acender. A mesa da régua tem UM controle, então o parceiro
    # da troca não existe e só o alvo recebe o desenho — ver `_pares_da_troca`.
    # O segundo par (`(False, True, False, True, False)`) é `player_led_pattern(2)`,
    # e está escrito aqui de propósito: se alguém trocar a tabela do daemon, a
    # régua reprova em vez de a lâmpada acender o desenho de outro jogador.
    {"pagina": PAGINA, "gesto": "player", "clique": {"player": "2"},  # (noqa-acento) id
     "chama": [("identity_number_set", ["aa:bb:cc:00:00:01", 2], {}),
               ("player_leds_set_detalhado", [(False, True, False, True, False)],
                {"uniq": "aa:bb:cc:00:00:01"})]},
    # O REENVIO DO DESENHO É O ÚNICO DOS QUATRO NOVOS QUE CABE AQUI, e a razão
    # é a mesma que tira os outros três: ele NÃO grava no disco. Ele lê o
    # desenho de agora — sem override no perfil de quem roda a régua, o padrão
    # do número — e o remanda. A mesa da régua tem UM controle no P1, então o
    # bitmask é `player_led_pattern(1)`, escrito aqui de propósito: se alguém
    # trocar a tabela do daemon, a régua reprova em vez de a lâmpada acender o
    # desenho de outro jogador. É o mesmo cuidado da prova do `player`.
    {"pagina": PAGINA, "gesto": GESTO_DO_REENVIO_DO_DESENHO,  # (noqa-acento) id
     "clique": {},
     "chama": [("player_leds_set_detalhado",
                [(False, False, True, False, False)],
                {"uniq": "aa:bb:cc:00:00:01"})]},
    # `luzes`, `desenho-de` e `auto-todos` NÃO ESTÃO AQUI pela MESMA razão que
    # tira o `brilho` e o `auto-cores`, e ela vale em dobro para eles: os três
    # ESCREVEM NO DISCO (`loader.save_profile`), e dois ainda chamam
    # `profile.switch` — numa régua que roda com o perfil ATIVO da máquina, uma
    # prova deles trocaria o desenho das luzes de quem rodou o teste.
    # Quem os morde é `tests/unit/test_a_04_as_cinco_lampadas_sem_o_numero.py`,
    # com a pasta de perfis desviada para um lar de mentira.
    #
    # `brilho` E `auto-cores` NÃO ESTÃO AQUI, e a ausência é declarada: os dois
    # ESCREVEM NO DISCO (`loader.save_profile`), e esta régua roda com o perfil
    # ATIVO da máquina em que ela roda. Uma prova deles aqui gravaria no perfil
    # de quem rodou o teste — que é o oposto do que uma régua faz.
    # Quem os morde é `tests/unit/test_a_aba_04_iluminacao_fecha_as_linhas.py`,
    # com a pasta de perfis desviada para um lar de mentira.
]
