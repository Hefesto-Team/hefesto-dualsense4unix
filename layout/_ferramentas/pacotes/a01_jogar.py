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

from . import Contexto, registrar


@registrar("01-jogar.html")
def pacote(ctx: Contexto) -> dict:
    """Os valores da aba Jogar, com os NOMES que a página tem.

    CADA CHAVE AQUI É UM `data-campo` DO `01-jogar.html`, e isso não é
    coincidência: até 01/09/2026 os dois lados foram escolhidos separadamente, e
    esta aba pintava UM valor de cinco. O pacote emitia `mascara` e a página
    tinha `identidade`; emitia `conta_b` e a página tinha `conta-b`. Nenhuma
    máquina sabia que eram a mesma coisa, e o `querySelector` de um endereço que
    não existe não levanta — devolve `null`, e a pintura escreve zero.

    `layout/_ferramentas/casamento.py` é a régua que passou a medir isso.
    """
    cartoes = {}
    for c in ctx.conectados:
        uniq = str(c.get("uniq") or "")
        # A IDENTIDADE É `nome · via`, como o desenho a escreve ("Cosmic Red
        # · USB") — e não a máscara. Sai da MESA, que é quem já leu a cor do
        # plástico; o `conectados` cru não tem o nome do modelo.
        casa = next((m for m in ctx.mesa if str(m.get("uniq") or "") == uniq), {})
        nome = casa.get("nome") or "—"
        via = casa.get("via") or (c.get("transport") or "").upper()
        cartoes[uniq] = {
            "jogador": f"Player {c.get('player') or '—'}",
            "bateria": f"{c.get('battery_pct')}%" if c.get("battery_pct") is not None else "—",
            "identidade": f"{nome} · {via}",
        }

    # O AVISO SAI DO MESMO EXAME DA ABA CONEXÕES, e não de uma segunda leitura:
    # `integrations/exame_da_mesa` é o dono, e duas contagens do mesmo fato
    # divergiriam no primeiro achado novo.
    achados = _do_exame()
    grave = next((a for a in achados if a["grave"]), None) or (achados[0] if achados else None)

    fora = {
        "atencao-conta": f"{len(achados)} aviso" + ("s" if len(achados) != 1 else ""),
        "cartoes": cartoes,
        "cobertura": {"pintados": 1 + len(cartoes) * 3 + (2 if grave else 0), "sem_dono": 0},
    }
    if grave:
        fora["aviso-selo"] = grave["selo"]
        fora["aviso-texto"] = grave["titulo"]
    # `perfil`, `conta` e `conta-b` NÃO saem daqui: são do cabeçalho, que é das
    # dez abas, e o dono deles é `pacotes.topo()`. Emiti-los aqui criava um
    # segundo dono — e foi assim que `conta_b` (com underscore) conviveu com o
    # `conta-b` da página sem nunca casar.
    return fora


def _do_exame() -> list[dict]:
    """Os achados do exame da mesa, ou lista vazia. Nunca levanta."""
    try:
        from . import a08_conexoes

        return [{"selo": "RÁDIO" if i["grave"] else "AVISO", **i}
                for i in a08_conexoes._exame()]
    except Exception:
        return []


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
#     painel.plano_do_modo(chave, mascara) -> [(metodo, params), ...]  # (noqa-acento)
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
    "mascara": (
        "a máscara do gamepad virtual é UMA para a máquina, não uma por "
        "controle: `gamepad.emulation.set` recebe `flavor` e não recebe `uniq` "
        "(`daemon/ipc_handlers.py:5060`). E 'Nintendo Pro' não é máscara do "
        "produto — o portão de entrada recusa em voz alta tudo o que não for "
        "`dualsense`/`xbox` e sinônimos (`ipc_handlers.py:5090`)."
    ),
}


def _painel():
    """`app/actions/jogar/painel` — o dono das perguntas desta aba.

    Importado DENTRO das funções, e não no topo: `painel` puxa `home_actions`,
    que puxa GTK. As funções de pacote são puras por contrato
    (`pacotes/__init__`), e um import de GTK no topo faria as dez abas o
    carregarem para pintar um travessão.
    """
    from hefesto_dualsense4unix.app.actions.jogar import painel

    return painel


def _plano(chave: str, mascara: str | None = None) -> list[tuple[str, dict]]:
    """A sequência de IPC daquele modo — DELEGADA, sem uma linha de regra aqui.

    `painel.plano_do_modo` devolve `None` quando o botão não tem escritor, e o
    motivo em português é de `painel.porque_nao_aplica`. Levantar com ELE é o
    que faz o botão recusar DIZENDO, em vez de falhar calado.
    """
    painel = _painel()
    plano = painel.plano_do_modo(chave, mascara)
    if plano is None:
        raise RuntimeError(painel.porque_nao_aplica(chave))
    return plano


def _aplicar(p, plano: list[tuple[str, dict]]) -> None:
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


#: ACHADO, 01/09/2026 — e ele fica escrito porque muda o que este arquivo pode
#: prometer: **`pacotes/ponte.chamar` não tem folga de tempo.** Ele chama
#: `_safe_call(metodo, params)` com o default de **250 ms**, que é o timeout de  # (noqa-acento)
#: LEITURA da ponte, e desde o BUG-IPC-READ-NO-TIMEOUT-01 esse prazo cobre
#: também a resposta (`ipc_bridge._run_call`).
#:
#: Só que trocar de modo não é leitura: cria uinput e faz grab, e o produto
#: declara **2,0 s** para isso (`mode_transition.MODE_IPC_TIMEOUT_S`, cujo
#: comentário diz com todas as letras: *"sem folga o toast dizia 'Falha' com o
#: modo JÁ aplicado"*). O `profile.switch` teve a mesma cicatriz e ganhou 3,0 s
#: (`ipc_bridge.PROFILE_SWITCH_TIMEOUT_S`).
#:
#: CONSEQUÊNCIA PARA ESTES GESTOS: um `p.chamar("gamepad.emulation.set", …)`
#: pode voltar `False` com o modo aplicado. Por isso `_aplicar` **não** levanta
#: com o retorno — levantar aqui reintroduziria exatamente o defeito que o
#: `MODE_IPC_TIMEOUT_S` curou, e a tela diria "não deu" sobre um gesto que deu.
#: A cura de verdade é `chamar` aceitar `timeout=`, e ela mora em `ponte.py`,
#: que não é território desta aba.
ACHADO_DO_TIMEOUT = (
    "ponte.chamar() chama _safe_call com o timeout de LEITURA (250 ms); "
    "mode_transition.MODE_IPC_TIMEOUT_S declara 2,0 s para trocar de modo."
)


@gesto("01-jogar.html", "hefesto")
def hefesto(ctx: Contexto, o: dict, p) -> None:
    """O INTERRUPTOR: Ligado (`gamepad`) ou Desligado (`native`).

    QUAL POSIÇÃO É O `data-modo` do rótulo clicado, e ele chega em `o["modo"]`
    já — o mesmo endereço que a pintura viva usa para acender a posição a partir
    de `mode_of_state`. Um segundo atributo só para o clique faria a tela ter um
    endereço para ler e outro para escrever.

    **"Desligado" É O MODO NATIVO, e não "parar o Hefesto"** — decisão dela,
    31/08/2026: *"o modo nativo já existe ali (…) e se eu quiser desligar modo
    hefesto clico em desligado e o modo nativo fica online."* Parar o serviço
    continua sendo a aba Sistema, e é por isso que este gesto nunca chama
    `daemon.pause` nem toca em `systemctl`.

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


def _plano_do_chip(chave: str) -> list[tuple[str, dict]]:
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


@gesto("01-jogar.html", "modo-dualsense")
def modo_dualsense(ctx: Contexto, o: dict, p) -> None:
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


@gesto("01-jogar.html", "modo-xbox")
def modo_xbox(ctx: Contexto, o: dict, p) -> None:
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


@gesto("01-jogar.html", "modo-navegacao")
def modo_navegacao(ctx: Contexto, o: dict, p) -> None:
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


@gesto("01-jogar.html", "reconectar")
def reconectar(ctx: Contexto, o: dict, p) -> None:
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


#: AS FUNÇÕES DA PONTE QUE ESTA ABA USA. Uma só, e o `chamar` é o degrau 3: os
#: quatro métodos abaixo não têm invólucro no `app/ipc_bridge.py` — conferido nas
#: 36 funções que ele expõe.
PONTE = {"chamar"}
#: OS MÉTODOS CRUS. A régua confere um a um contra o `ipc_server.py`, e um nome
#: inventado reprova AQUI, não na mão de quem clica.
METODOS = {
    "native.mode.set",
    "gamepad.emulation.set",
    "mouse.emulation.restore",
    "coop.sync",
    "identity.renumber",
}


#: O QUE ESTA ABA DECLARA À RÉGUA. O piso é CINCO, e não seis: o `modo-steam`
#: está marcado no desenho e **não** tem `@gesto` (ver `BOTOES_SEM_DONO`).
PAGINA = "01-jogar.html"
PISO_DA_ABA = 5

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
    {"pagina": PAGINA, "gesto": "hefesto", "clique": {"modo": "gamepad"},  # (noqa-acento)
     "chama": [("chamar", ["native.mode.set"], _MANUAL_OFF),
               ("chamar", ["gamepad.emulation.set"], _MANUAL_ON)]},
    # DESLIGADO é o Modo Nativo, e é UM passo só — decisão dela, 31/08.
    {"pagina": PAGINA, "gesto": "hefesto", "clique": {"modo": "native"},  # (noqa-acento)
     "chama": [("chamar", ["native.mode.set"], _MANUAL_ON)]},
    # O CHIP MUDA A MÁSCARA, NÃO O MODO: o `flavor` é a única diferença entre
    # este e o Xbox logo abaixo. Ele sai de `painel.CHIPS_DA_ESCADA`, não é
    # digitado no gesto — o que está digitado aqui é a EXPECTATIVA.
    {"pagina": PAGINA, "gesto": "modo-dualsense", "clique": {},  # (noqa-acento)
     "chama": [("chamar", ["native.mode.set"], _MANUAL_OFF),
               ("chamar", ["gamepad.emulation.set"],
                {**_MANUAL_ON, "flavor": "dualsense"})]},
    {"pagina": PAGINA, "gesto": "modo-xbox", "clique": {},  # (noqa-acento)
     "chama": [("chamar", ["native.mode.set"], _MANUAL_OFF),
               ("chamar", ["gamepad.emulation.set"],
                {**_MANUAL_ON, "flavor": "xbox"})]},
    # TRÊS, e o terceiro é o que separa "entrei no modo" de "entrei num modo sem
    # função": `mouse.emulation.restore` liga o mouse conforme a preferência
    # persistida (HARM-06), e vem POR ÚLTIMO de propósito.
    {"pagina": PAGINA, "gesto": "modo-navegacao", "clique": {},  # (noqa-acento)
     "chama": [("chamar", ["native.mode.set"], _MANUAL_OFF),
               ("chamar", ["gamepad.emulation.set"], _MANUAL_OFF),
               ("chamar", ["mouse.emulation.restore"], {})]},
    # RECONCILIAR ANTES DE RENUMERAR: renumerar primeiro compactaria uma mesa
    # que ainda não está completa (`home_actions.py:3122`).
    {"pagina": PAGINA, "gesto": "reconectar", "clique": {},  # (noqa-acento)
     "chama": [("chamar", ["coop.sync"], {}),
               ("chamar", ["identity.renumber"], {})]},
]
