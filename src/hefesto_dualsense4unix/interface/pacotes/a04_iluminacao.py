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

A BANCADA ANDOU E O PRODUTO NÃO — 02/09/2026, e é de propósito. O
`mockup/04-iluminacao.html` ganhou três atributos de ENDEREÇO
(`data-hef-alvo="largura"` no trilho do brilho; `data-campo="players"` +
`data-hef-alvo="html"` no `.players`; e os quatro `data-campo="player-N"` saíram
dos botões). Publicar é ato DELA. O `check_o_desenho_aprovado.py` fica VERDE sem
declaração porque ele compara `o_que_se_ve()` — o HTML **sem** os endereços de
pintura —, e é ele quem prova, sozinho, que nenhum pixel mudou.

O QUE A PUBLICAÇÃO CONSERTA, medido em Chrome headless com o BOOTSTRAP real::

    publicado   trilho: texto '' -> '100'   largura 141.641px -> 141.641px
    bancada     trilho: texto '' -> ''      largura 141.641px -> 172.75px
    publicado   o botão aceso continua o do DESENHO; a dica idem
    bancada     o botão aceso segue o número vivo, e a dica diz o transporte de agora

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
    """`[0, 0, 255]` → `#0000FF`, e `—` quando não há cor.

    O travessão NÃO é enfeite: é a mesma marca de "não há valor" que os lugares
    vazios usam nas seis abas. Um `#000000` no lugar diria PRETO, que é uma cor.
    """
    if not rgb or len(rgb) < 3:
        return "—"
    return "#{:02X}{:02X}{:02X}".format(*(int(x) for x in rgb[:3]))


#: Os quatro números que a página oferece, e o gerador desenha.
NUMEROS = (1, 2, 3, 4)


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
    from hefesto_dualsense4unix.app.widgets.controller_card import rotulo_lightbar

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
        rgb = c.get("lightbar_rgb") or []
        meu = overrides.get(uniq) or {}
        seus = (meu.get("leds") or {}) if isinstance(meu, dict) else {}
        b = seus.get("lightbar_brightness", brilho)
        pct = None if b is None else round(float(b) * 100)
        casa = _da_mesa(ctx, uniq)
        n = _numero(ctx, c)
        nome = str(casa.get("nome") or "—")
        via = str(casa.get("via") or (c.get("transport") or "").upper() or "—")
        recado, _base = rotulo_lightbar(c, ctx.state)
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
            "hex": _hex(rgb),
            "rgb": list(rgb[:3]) if len(rgb) >= 3 else [],
            # `aceso`, e não `acesa`: é o `data-campo` que a página tem. Uma
            # letra separava o valor do lugar onde ele cabia.
            "aceso": "Aceso" if c.get("lightbar_on", True) else "Apagado",
            #: O RÓTULO INTEIRO, e não só o número. O desenho escreve
            #: `P1 • Cosmic Red • USB`; emitir só o `P1` fazia o primeiro tique
            #: APAGAR o nome do controle e o transporte da tela dela — a
            #: pintura escreve `textContent`, e três pedaços viravam um.
            "identidade": f"P{n} • {nome} • {via}",
            #: A FILEIRA DOS QUATRO NÚMEROS, viva. O `on` sai daqui, e as dicas
            #: também: as do HTML publicado estão CONGELADAS do desenho e
            #: nomeiam controle por transporte que já mudou.
            "players": fileira_de_players(nome, n, donos),
            "recado": recado or "",
        }
    return {
        "colunas": colunas,
        "perfil": ctx.state.get("active_profile") or "",
        "sem_dono": {},
        #: O NÚMERO SAI DO DICIONÁRIO, nunca de uma constante escrita à mão —
        #: foi assim que a curva da aba Gatilhos ficou fora da cobertura.
        #: `player` e `fonte` saíram em 02/09/2026: os dois eram ÓRFÃOS
        #: (`casamento.py` os listava, a página não tem onde pôr), e o que eles
        #: diziam passou a viver em `identidade` e em `recado`.
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

    O `data-hex` do botão traz `#RRGGBB` e o bridge quer `(r, g, b)`. A conversão
    mora aqui porque é assunto da TELA — o JS manda o que a tela tem.
    """
    uniq, hexa = _uniq(o), str(o.get("hex") or "").lstrip("#")
    if not uniq or len(hexa) != 6:
        raise ValueError(f"cor: preciso do controle e de um #RRGGBB (veio {o.get('hex')!r})")
    p.led_set(tuple(int(hexa[i:i + 2], 16) for i in (0, 2, 4)), uniq=uniq)


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
