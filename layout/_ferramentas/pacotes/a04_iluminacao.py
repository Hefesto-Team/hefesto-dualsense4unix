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

A `lightbar_disputada` É O VALOR MAIS IMPORTANTE DESTA ABA, e é o que separa
esta tela de uma tela bonita: quando a Steam tem o controle aberto, a cor que o
daemon publica é a **pedida**, não a **acesa**. Pintar o hex sem dizer isso é
afirmar uma cor que pode não estar no plástico — e o produto já sabe a
diferença, é a tela que precisa contá-la.
"""
from __future__ import annotations

from . import Contexto, perfil, registrar

#: Vazio, e o vazio é uma AFIRMAÇÃO: cada valor desta aba tem dono medido. A
#: régua reprova um pacote que pinta 0 e declara 0, de propósito.
SEM_DONO: dict[str, str] = {}


def _hex(rgb) -> str:
    """`[0, 0, 255]` → `#0000FF`, e `—` quando não há cor.

    O travessão NÃO é enfeite: é a mesma marca de "não há valor" que os lugares
    vazios usam nas seis abas. Um `#000000` no lugar diria PRETO, que é uma cor.
    """
    if not rgb or len(rgb) < 3:
        return "—"
    return "#{:02X}{:02X}{:02X}".format(*(int(x) for x in rgb[:3]))


@registrar("04-iluminacao.html")
def pacote(ctx: Contexto) -> dict:
    p = perfil.ativo(ctx.state.get("active_profile"))
    leds = (p.get("leds") or {}) if p else {}
    #: O BRILHO É DO PERFIL, e é um só para a mesa — como o gatilho. O
    #: `ControllerOverrides.leds` do schema permite por controle, e quando ele
    #: estiver preenchido esta função o lê antes; enquanto não, repetir é o que
    #: corresponde ao que o produto faz.
    brilho = leds.get("lightbar_brightness")
    overrides = (p.get("controllers") or {}) if p else {}

    colunas: dict[str, dict] = {}
    for c in ctx.conectados:
        uniq = str(c.get("uniq") or "")
        rgb = c.get("lightbar_rgb") or []
        disputada = bool(c.get("lightbar_disputada"))
        meu = overrides.get(uniq) or {}
        seus = (meu.get("leds") or {}) if isinstance(meu, dict) else {}
        b = seus.get("lightbar_brightness", brilho)
        colunas[uniq] = {
            "brilho": b,
            #: A TELA MOSTRA PORCENTAGEM e o disco guarda 0..1. A conversão mora
            #: aqui, não no JS: um `0.82` chegando cru viraria "0,82%" na tela.
            "brilho-pct": None if b is None else round(float(b) * 100),
            "hex": _hex(rgb),
            "rgb": list(rgb[:3]) if len(rgb) >= 3 else [],
            # `aceso`, e não `acesa`: é o `data-campo` que a página tem. Uma
            # letra separava o valor do lugar onde ele cabia.
            "aceso": "Aceso" if c.get("lightbar_on", True) else "Apagado",
            "identidade": f"P{c.get('player') or '—'}",
            "player": c.get("player"),
            "fonte": c.get("lightbar_source") or "",
            # O RECADO SÓ APARECE QUANDO A DISPUTA EXISTE. Um aviso permanente
            # vira paisagem, e paisagem ninguém lê — é a regra desta casa.
            "recado": ("A Steam tem este controle aberto: a cor publicada é a "
                       "PEDIDA, e pode não ser a acesa." if disputada else ""),
        }
    return {
        "colunas": colunas,
        "perfil": ctx.state.get("active_profile") or "",
        "sem_dono": {},
        #: SETE, não cinco: o brilho e a porcentagem entraram. Contar por uma
        #: constante escrita à mão foi o que deixou a curva da aba Gatilhos fora
        #: da cobertura na mesma leva — o número tem de sair do dicionário.
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
#      por `pref` (`p1`) e o daemon por `uniq` (`d4:2f:…`).
#   3. a ponte é INJETADA — a função não importa o bridge, recebe. Por isso a
#      régua a testa com um dublê e cobra QUAL função foi chamada e com quê.
#   4. o que o produto não faz não vira botão que finge: vira botão que recusa
#      dizendo, e o nome sai no relato do piloto.
from . import gesto  # noqa: E402


def _uniq(o: dict) -> str:
    """O `uniq` do controle onde ela clicou. Vazio = clique solto, e recusa.

    `""` NÃO vira "todos": um "Desligar" sem dono apagaria a barra dos quatro
    controles em vez de um.
    """
    return str(o.get("uniq") or "")


@gesto("04-iluminacao.html", "cor")
def cor(ctx: Contexto, o: dict, p) -> None:
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
def apagar(ctx: Contexto, o: dict, p) -> None:
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
def automatico(ctx: Contexto, o: dict, p) -> None:
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

    dele = ctx.por_uniq(uniq) or {}
    slot = dele.get("player_slot") or dele.get("player") or 1
    p.led_set(tuple(player_slot_color(int(slot))), uniq=uniq)


@gesto("04-iluminacao.html", "player")
def player(ctx: Contexto, o: dict, p) -> None:
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
