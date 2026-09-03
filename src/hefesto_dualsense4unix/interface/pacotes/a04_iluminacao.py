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
`lightbar_rgb`). Quando os dois discordam, quem manda na tela é o vivo — e é por
isso que o `hex` continua vindo do daemon e só o brilho vem do disco.

O PRODUTO ALCANÇOU A BANCADA no `players` e no `brilho`: a publicação de
02/09/2026 (`70b58116`) levou ao HTML publicado o `data-hef-alvo="largura"` do
trilho e o `data-campo="players"` do `.players`, e os quatro
`data-campo="player-N"` sumiram dos botões nos DOIS lados. A frase que estava
aqui — *"A BANCADA ANDOU E O PRODUTO NÃO"* — caducou no mesmo dia em que foi
escrita; medir vale mais que lembrar.

O QUE AINDA ESPERA A PUBLICAÇÃO é UM par, e é o do `.aceso`: a bancada diz
`data-campo="luz" data-hef-alvo="html"`, o publicado ainda diz
`data-campo="aceso"`. Ver `desenho_da_luz`.

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
    sem cor. Sem hex, o botão sai SEM anel — que é exatamente o que o desenho
    faz com um número cujo dono não está aqui.
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
    """
    cor = _cor_do_plastico(str(dono.get("cor") or "")) if dono else ""
    anel = f'<i class="dono" style="--plastico:{cor}"></i>' if dono is not None and cor else ""
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
                   recuo: str = "") -> str:
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
        (`TIRA_APAGADA`), e nunca uma tira sem estilo — ver a constante.
    :param brilho: de 0.0 a 1.0, a opacidade das duas tiras ACESAS. A apagada
        não tem brilho: uma barra desligada a 30% seria 30% de nada.
    :param jogador: o número deste controle, para o padrão das lâmpadas.
    :param dica: a frase de `dica_da_luz`, ou `""`. Sem ela as peças saem sem
        `title`, que é o que o desenho fazia antes de haver frase viva.
    """
    import monta  # o `pacotes/__init__` põe `interface/` no `sys.path`

    estilo = (f"background:{tinta};color:{tinta};opacity:{brilho}" if tinta
              else TIRA_APAGADA)
    diz = f' title="{dica}"' if dica else ""
    tira = f'<span class="tira-luz %s" style="{estilo}"{diz}></span>'
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


@registrar("04-iluminacao.html")
def pacote(ctx: Contexto) -> dict[str, Any]:
    p = perfil.ativo(ctx.state.get("active_profile"))
    leds = (p.get("leds") or {}) if p else {}
    #: O BRILHO É DO PERFIL, e é um só para a mesa — como o gatilho. O
    #: `ControllerOverrides.leds` do schema permite por controle, e quando ele
    #: estiver preenchido esta função o lê antes; enquanto não, repetir é o que
    #: corresponde ao que o produto faz.
    brilho = leds.get("lightbar_brightness")
    overrides = (p.get("controllers") or {}) if p else {}

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
        meu = overrides.get(uniq) or {}
        seus = (meu.get("leds") or {}) if isinstance(meu, dict) else {}
        b = seus.get("lightbar_brightness", brilho)
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
            #: A COR CRUA, que é o que a caixa `#RRGGBB` mostra — e ela não
            #: some quando a barra apaga: o hex diz QUAL cor está gravada, o
            #: desenho abaixo diz se ela está acesa.
            "hex": _hex(crua),
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
            "luz": desenho_da_luz(_tinta(acesa),
                                  1.0 if b is None else float(b), n,
                                  dica_da_luz(nome, via, recado or "",
                                              o_coop_manda(ctx.state))),
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
    p.led_set(hex_to_rgb(pedido), uniq=uniq)


@gesto("04-iluminacao.html", "apagar")
def apagar(ctx: Contexto, o: dict[str, Any], p: Any) -> None:
    """"Desligar": a barra vai a preto.

    NÃO é `lightbar.reset` — esse devolve a cor AUTOMÁTICA, que é o outro botão.
    Apagar e voltar ao automático são coisas diferentes, e o desenho dela as
    separa em dois botões de cores diferentes.
    """
    uniq = _uniq(o)
    if not uniq:
        raise ValueError("apagar: o clique não disse em qual controle")
    p.led_set((0, 0, 0), uniq=uniq)


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
    p.chamar("lightbar.reset", uniq=uniq)

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
    dele = ctx.por_uniq(uniq) or {}
    p.led_set(tuple(player_slot_color(_numero(ctx, dele or {"uniq": uniq}))), uniq=uniq)


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
PONTE = {"led_set", "identity_number_set", "chamar"}
METODOS = {"lightbar.reset"}


#: O QUE ESTA ABA DECLARA À RÉGUA — o piso e as provas moram AQUI, e não no
#: teste, para que ligar uma aba não exija editar um arquivo que oito pessoas
#: editariam ao mesmo tempo.
PAGINA = "04-iluminacao.html"
PISO_DA_ABA = 4
PROVAS = [
    {"pagina": PAGINA, "gesto": "cor", "clique": {"hex": "#FF8000"},  # (noqa-acento) id
     "chama": [("led_set", [(255, 128, 0)], {"uniq": "aa:bb:cc:00:00:01"})]},
    {"pagina": PAGINA, "gesto": "apagar", "clique": {},  # (noqa-acento) chave do contrato
     "chama": [("led_set", [(0, 0, 0)], {"uniq": "aa:bb:cc:00:00:01"})]},
    # DUAS chamadas, e a ordem importa: largar o claim e SÓ ENTÃO pintar.
    {"pagina": PAGINA, "gesto": "auto", "clique": {},  # (noqa-acento) chave do contrato
     "chama": [("chamar", ["lightbar.reset"], {"uniq": "aa:bb:cc:00:00:01"}),
               ("led_set", [(0, 0, 255)], {"uniq": "aa:bb:cc:00:00:01"})]},
    {"pagina": PAGINA, "gesto": "player", "clique": {"player": "2"},  # (noqa-acento) id
     "chama": [("identity_number_set", ["aa:bb:cc:00:00:01", 2], {})]},
]
