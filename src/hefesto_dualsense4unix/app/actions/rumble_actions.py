"""Aba Rumble: intensidade global (Economia/Balanceado/Máximo/Auto) + Testar motores.

FEAT-RUMBLE-POLICY-01: aba reestruturada em 2 cards:
  1. "Intensidade da vibração" — 4 GtkToggleButton agrupados + slider + label Auto.
  2. "Testar motores" — sliders de vibração leve/forte + botões Testar/Aplicar/Parar.

LEIGO-06: "política", "rumble", "weak"/"strong" e "throttle" saíram da TELA —
continuam sendo os nomes do IPC e do schema (`rumble.policy`, `policy="max"`),
que este módulo traduz na fronteira.

Política define multiplicador global aplicado pelo daemon sobre todo rumble,
inclusive passthrough de jogo (XInput virtual). Slider de intensidade ajusta
"custom" em 0-200% (mapeamento valor/100 nos dois sentidos).

HARM-19: o teto tem UM dono — ``profiles.schema.RUMBLE_CUSTOM_MULT_MAX``. Eram
três (2.0 no schema, 1.0 no handler ``rumble.policy_custom``, 200% no slider), e
de 101% em diante a usuária levava um erro de validação que esta aba nem
mostrava. Mexeu no teto? Mexa no schema — este slider é ``mult * 100``.

FEAT-RUMBLE-POLICY-PROFILE-01: cada escolha de política da usuária também é
gravada em ``self.draft.rumble`` — o "Salvar Perfil" do rodapé persiste no
perfil exatamente o que a aba mostra (aplicada de volta na ativação).
"""
# ruff: noqa: E402
from __future__ import annotations

import contextlib
from typing import Any

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import GLib, Gtk

from hefesto_dualsense4unix.app.actions.base import WidgetAccessMixin
from hefesto_dualsense4unix.app.actions.mode_transition import STATE_IPC_TIMEOUT_S
from hefesto_dualsense4unix.app.alvo_de_edicao import (
    AlvoDeEdicao,
    EstadoDoAlvo,
    alvo_de_edicao,
)
from hefesto_dualsense4unix.app.ipc_bridge import (
    call_async,
    rumble_passthrough,
    rumble_policy_custom,
    rumble_policy_set_checked,
    rumble_set_checked,
    rumble_stop,
    rumble_stop_checked,
)
from hefesto_dualsense4unix.daemon.subsystems.rumble import (
    RUMBLE_POLICY_MULT,
    sem_dono_do_rumble,
)

#: Mapeamento política -> mult canônico (para mover o deslizador ao clicar num
#: dos quatro botões).
#:
#: 11/08/2026: era uma CÓPIA à mão da tabela do daemon, e as duas divergiam no
#: dia em que um degrau mudasse — a classe de defeito que o HARM-19 já pagou no
#: teto do multiplicador. Agora deriva do dono único
#: (`daemon.subsystems.rumble.RUMBLE_POLICY_MULT`); o daemon é quem multiplica
#: de verdade, e a tela não pode oferecer um número que ele não aplique.
#: Precedente do import GUI→daemon: `app.actions.daemon_actions`, que importa
#: de `daemon.service_install` no topo.
#:
#: O ``auto`` é o único que não vem de lá, e de propósito: ele não tem mult
#: fixo (varia com a bateria em `core.rumble._effective_mult`) e este 1,0 é só
#: onde o deslizador para — o teto do Auto, que NUNCA amplifica.
_POLICY_MULT: dict[str, float] = {
    **RUMBLE_POLICY_MULT,
    "auto": 1.0,
}

#: O degrau que vale quando não se sabe qual é. Era o literal ``0.7`` repetido
#: em quatro lugares deste arquivo; quando o Balanceado virou 1,0 (11/08/2026),
#: o 0,7 deixou de ser degrau de coisa alguma e virou âncora morta — um número
#: que a tela mostrava sem nenhum botão correspondente.
_MULT_PADRAO = _POLICY_MULT["balanceado"]

#: LEIGO-06: o toast ecoava a CHAVE interna ("max", "economia") — palavra
#: diferente da que a usuária acabou de clicar no botão ("Máximo"). Os rótulos
#: são os do glade (main.glade, card "Intensidade da vibração").
_POLICY_LABEL: dict[str, str] = {
    "economia": "Economia",
    "balanceado": "Balanceado",
    "max": "Máximo",
    "auto": "Auto",
}

#: CONFIG-05 (22/08/2026): os MESMOS quatro rótulos, públicos, porque a seção
#: "Orçamento" da aba Configurações oferece as mesmas quatro opções — e o
#: vocabulário da mesa não pode divergir do vocabulário da aba de origem.
#:
#: Público em vez de importar o privado acima pelo mesmo motivo do
#: `BTN_GIVE_BACK_TO_GAME` logo abaixo: quem depende de um nome de outro módulo
#: precisa de um nome que aquele módulo se comprometeu a manter. Redigitar os
#: quatro seria a alternativa, e é a que a casa já pagou — duas listas de
#: rótulos divergem na primeira edição.
ROTULOS_DO_ORCAMENTO: dict[str, str] = dict(_POLICY_LABEL)

#: RUM-01: o texto dos toasts/estado mandava clicar "Devolver ao jogo" — botão
#: que NÃO existe. O botão real (main.glade) tem este rótulo; um único dono aqui
#: impede a dessincronia de voltar. Ao mexer no rótulo do glade, mexa aqui.
#: Rótulo do botão que devolve a vibração ao jogo. Público porque o banner
#: (status_actions) manda clicar nele — as duas telas não podem divergir no
#: nome do botão.
BTN_GIVE_BACK_TO_GAME = "Deixar o jogo controlar a vibração"
_BTN_GIVE_BACK_TO_GAME = BTN_GIVE_BACK_TO_GAME

#: JARG-01/LB-02: "daemon offline?" vaza jargão + palpite. O resto do app já
#: fala "ligue na aba Sistema" — a fronteira da GUI traduz aqui também.
_MSG_HEFESTO_OFF = "não consegui — o Hefesto pode estar desligado (ligue na aba Sistema)."


def _pedidos_por_jogador(ff: dict[str, Any]) -> str | None:
    """A contagem de pedidos POR JOGADOR; ``None`` = a soma responde melhor.

    RUM-9 (25/08/2026). O ``rumble_ff`` tem duas metades: o agregado (``plays``,
    ``nao_nulos``), que esta aba sempre leu, e o ``per_vpad``, que existe desde a
    RUMBLE-QUE-NÃO-SE-SENTE-01 e que **só o card do controle** lia
    (``widgets.controller_card._item_do_vpad``). Com a mesa cheia a soma manda
    caçar no lugar errado: *"o jogo pediu vibração 40x"* com o Jogador 2 mudo é
    verdade sobre a mesa e mentira sobre o jogador que reclamou.

    ``None`` nos quatro casos em que somar não perde nada — e afirmar por
    jogador perderia:

    1. **Não há lista** (``per_vpad`` ausente ou não-lista): daemon mais velho.
       Inventar jogadores a partir do agregado seria dado fabricado;
    2. **Um jogador só** (0 ou 1 entrada): a frase de hoje já é sobre ele, e a
       casa exige que ela fique **byte-idêntica** — quem joga sozinho não vê
       mudança nenhuma nesta leva;
    3. **Alguma entrada não traz ``ff_nao_nulo_count``** (daemon mais velho, ou
       vpad que não respondeu): a frase por jogador teria um buraco no meio, e
       "não sei" viraria "nenhuma" — as duas mandam caçar em lugares opostos;
    4. **Ninguém pediu nada** (nenhum ``play`` e nenhum ``nao_nulo``): a frase
       agregada *"o jogo ainda não pediu vibração nenhuma"* diz o mesmo com
       menos ruído, e repetir "nenhuma" por jogador não acrescenta um fato.

    A **ordem da verdade** de :func:`texto_dos_pedidos_de_vibracao` não muda:
    esta função entra depois de ``estranhos`` e ``descartados`` (que são defeito
    NOSSO e valem para a mesa inteira) e antes do ramo agregado — só o ESCOPO da
    resposta muda, nunca a ordem das perguntas.

    Cada jogador responde à mesma pergunta 5/6 do agregado, com as mesmas
    palavras: pediu FORÇA (``nao_nulo``), falou e pediu zero (``play`` sem
    ``nao_nulo``), ou não falou.
    """
    per_vpad = ff.get("per_vpad")
    if not isinstance(per_vpad, list) or len(per_vpad) < 2:
        return None
    linhas: list[tuple[int, str]] = []
    algum_pedido = False
    algum_nao_nulo = False
    for item in per_vpad:
        if not isinstance(item, dict):
            return None
        player = _inteiro(item.get("player"))
        nao_nulo = _inteiro(item.get("ff_nao_nulo_count"))
        plays = _inteiro(item.get("ff_play_count"))
        if player is None or nao_nulo is None or plays is None:
            return None
        if nao_nulo > 0:
            algum_pedido = True
            algum_nao_nulo = True
            linhas.append((player, f"Jogador {player}: {nao_nulo}x"))
        elif plays > 0:
            algum_pedido = True
            linhas.append(
                (player, f"Jogador {player}: {plays}x, todas com força zero")
            )
        else:
            linhas.append((player, f"Jogador {player}: nenhuma"))
    if not algum_pedido:
        return None
    linhas.sort(key=lambda par: par[0])
    corpo = " · ".join(texto for _, texto in linhas)
    if algum_nao_nulo:
        # A mesma oração final do agregado, e pelo mesmo motivo: quem pediu
        # força e não sentiu tem de saber que a caça é do nosso lado.
        return f"o jogo pediu vibração — {corpo} — se não sentiu, é aqui dentro"
    return f"o jogo pediu vibração — {corpo}"


def texto_dos_pedidos_de_vibracao(state: dict[str, Any]) -> str | None:
    """O pedaço da linha que conta os pedidos de vibração DO JOGO.

    ``None`` = **não sei**, e aí a linha não diz nada sobre pedidos. É o único
    silêncio que sobra: antes desta função o silêncio significava as duas
    coisas ao mesmo tempo, porque a contagem só aparecia com ``plays > 0``.

    O caso ruim era justamente o mudo. Medido na mesa dela em 08-09/08:
    ``rumble_ff = {plays: 0, vpads: 0}`` durante dias de zero vibração em
    qualquer jogo — a aba tinha o número na mão, sabia que o jogo nunca pediu
    nada, e não dizia. Quatro agentes foram investigar o que a linha podia ter
    respondido sozinha.

    As perguntas estão na ORDEM DA VERDADE, que é a mesma de
    ``widgets.controller_card.estado_do_recurso`` e não pode ser trocada:

    1. **Conexão Nativa (Sony)?** Não há gamepad virtual porque não deve
       haver — o jogo abre o hidraw do controle físico e vibra por lá. Contar
       pedidos ao vpad aqui não faz sentido, e responder "ninguém pediu" seria
       mentira. A frase é a que as outras duas telas já usam
       (``emulation_actions`` e ``controller_card``: *"o jogo fala direto com
       o controle"*);
    2. **O dado veio?** ``rumble_ff`` ausente (daemon sem config no
       ``state_full``, resposta que não chegou, daemon mais velho) ou ``plays``
       que não é inteiro: silêncio. Afirmar zero com o campo ausente é a
       família de erro que o ``gyro_do_inputs`` já paga para não cometer —
       "zero" e "não sei" levam a caças completamente diferentes;
    3. **Chegou report que nem chegamos a abrir?** (``estranhos``) QUEM
       ESCREVEU-01, 09/08/2026. O vpad só lê o envelope 0x02; qualquer outro
       report id era descartado na PRIMEIRA linha do ``_handle_output``, antes
       até de o ``output_count`` subir. Ou seja: dado chegando produzia
       exatamente o mesmo painel zerado que "nenhum jogo enxergou o gamepad
       virtual" — e as duas conclusões mandam caçar em pontas opostas (uma
       manda olhar dedup/udev/máscara, a outra manda olhar o nosso parser).
       Vem antes do descarte porque é mais a montante: aqui nem o layout foi
       lido;
    4. **Chegou pedido que não soubemos ler?** (``descartados``) O jogo mandou
       motor não-nulo num report cujos bits de vibração não reconhecemos.
       Dizer "o jogo não pediu" aqui seria a mentira mais cara da aba;
    5. **Alguém pediu FORÇA?** (``nao_nulos``) Este é o número que vale. Ver
       RUMBLE-QUE-NAO-SE-SENTE-01: medido na mesa dela em 09/08, ``plays=117``
       com ela sem sentir nada — e ``plays`` sobe na PARADA também, porque o
       ``+= 1`` do vpad acontece antes de os bytes dos motores serem lidos.
       Anunciar "o jogo pediu vibração 117x" quando as 117 podiam ser pedidos
       de força ZERO mandaria caçar no lugar errado;
    6. **Falou de vibração e pediu zero?** (``plays > 0``, ``nao_nulos == 0``)
       É o jogo pedindo SILÊNCIO — conclusão oposta à de cima, e a caça é no
       jogo/máscara, nunca no nosso caminho de saída;
    7. **Há gamepad virtual?** ``vpads == 0`` e ``plays == 0`` não é o jogo
       calado: é jogo NENHUM tendo onde pedir. Conclusão oposta à de baixo — um
       manda ligar a emulação, o outro manda olhar o jogo — e é por isso que as
       duas frases são distintas. ``vpads`` ausente não autoriza nenhuma das
       duas afirmações: cai no caso geral, que só fala do que ``plays`` prova.

    **Daemon mais velho** não manda ``nao_nulos``/``descartados``. Aí a função
    volta EXATAMENTE ao texto antigo (o número de ``plays``): com o campo
    ausente não se sabe qual das duas causas é, e inventar uma seria repetir o
    defeito que esta função existe para curar.

    **RUM-9 (25/08/2026): as perguntas 5 e 6 passaram a ter ESCOPO.** Com dois
    ou mais gamepads virtuais na mesa, quem responde é
    :func:`_pedidos_por_jogador` — a ordem acima fica inteira, e só o escopo da
    resposta muda. Com um jogador só a frase é byte-idêntica à de sempre.
    """
    if bool(state.get("native_mode")):
        return "Conexão Nativa (Sony): o jogo fala direto com o controle"
    ff = state.get("rumble_ff")
    if not isinstance(ff, dict):
        return None
    plays = ff.get("plays")
    if not isinstance(plays, int) or isinstance(plays, bool):
        return None
    estranhos = _inteiro(ff.get("estranhos"))
    if estranhos:
        return (
            f"o jogo escreveu {estranhos}x no controle virtual num envelope que "
            "o Hefesto nem abriu — é defeito nosso, mande esta tela para o suporte"
        )
    descartados = _inteiro(ff.get("descartados"))
    if descartados:
        return (
            f"o jogo pediu vibração {descartados}x num formato que o Hefesto "
            "não reconheceu — é defeito nosso, mande esta tela para o suporte"
        )
    # RUM-9: com a mesa cheia, a resposta é POR JOGADOR. `None` = a soma
    # responde melhor (os quatro casos estão no docstring de lá), e aí a função
    # segue exatamente como sempre foi.
    por_jogador = _pedidos_por_jogador(ff)
    if por_jogador is not None:
        return por_jogador
    nao_nulos = _inteiro(ff.get("nao_nulos"))
    if nao_nulos is None:
        # Daemon antigo: só o número ambíguo, e nenhuma afirmação além dele.
        if plays > 0:
            return f"o jogo pediu vibração {plays}x"
    elif nao_nulos > 0:
        return f"o jogo pediu vibração {nao_nulos}x — se não sentiu, é aqui dentro"
    elif plays > 0:
        return f"o jogo falou de vibração {plays}x, mas pediu força zero em todas"
    vpads = ff.get("vpads")
    if isinstance(vpads, int) and not isinstance(vpads, bool) and vpads == 0:
        return "não há gamepad virtual — nenhum jogo tem onde pedir vibração"
    return "o jogo ainda não pediu vibração nenhuma"


def texto_do_alcance_da_intensidade(state: dict[str, Any]) -> str | None:
    """O aviso de que a intensidade escolhida NÃO chega à vibração dos jogos.

    ``None`` = ela chega, ou não se sabe — e nos dois casos a linha não aparece.

    **O defeito**, medido no journal da máquina dela em 11/08/2026:
    ``launch_env_materializado ... backends=[] emulacao=False
    mascara=dualsense native=False``. Sem gamepad virtual **e** sem Conexão
    Nativa (Sony) ao mesmo tempo. Nesse estado o multiplicador dos quatro
    botões não age sobre a vibração do jogo, porque ele mora no caminho de
    saída do gamepad virtual — ``daemon.subsystems.gamepad.apply_game_rumble``,
    alcançado só pelo sink de ``make_primary_rumble_sink``. Sem gamepad
    virtual, esse sink nunca é criado. E a aba seguia mostrando
    Economia/Balanceado/Máximo como se valessem, sem uma palavra.

    **QUEM DECIDE O QUADRANTE NÃO É ESTA FUNÇÃO** — é
    ``daemon.subsystems.rumble.sem_dono_do_rumble``, o mesmo predicado que faz o
    daemon gritar ``rumble_sem_dono`` no journal, com a medição RUMBLE-SEM-DONO-01
    atrás dele. Por algumas horas em 11/08 houve dois critérios paralelos para o
    mesmo buraco (a borda olhava ``backends``, esta tela olhava ``vpads``), e
    dois critérios divergem na primeira mudança. O ``state_full`` não manda os
    NOMES dos backends, manda a CONTAGEM de gamepads virtuais; como o predicado
    só olha a verdade/falsidade da sequência, a contagem responde a mesma
    pergunta e a tradução acontece aqui, na fronteira.

    A ordem das perguntas é a mesma de ``texto_dos_pedidos_de_vibracao``, e
    pelo mesmo motivo:

    1. **O dado veio?** ``rumble_ff`` ausente, ou ``vpads`` que não é inteiro
       (daemon mais velho, resposta que não chegou): silêncio. Afirmar "não
       alcança" com o campo ausente seria inventar um defeito — "não sei" e
       "não chega" mandam caçar em lugares opostos;
    2. **É o quadrante sem dono?** Pergunta feita ao predicado. Se for, é a
       frase do defeito, com o gesto que o resolve;
    3. **Conexão Nativa (Sony) sem gamepad virtual?** A intensidade também não
       alcança, mas isso é o modo funcionando como deve — não é defeito, e por
       isso não é o quadrante. A frase é a que as outras telas já usam (*"o jogo
       fala direto com o controle"*), e não manda consertar nada;
    4. **Sobrou.** Há gamepad virtual e a intensidade alcança: nada a dizer.

    As duas frases terminam dizendo o que a intensidade AINDA faz — ela vale
    para a vibração fixada em "Testar motores", pelo caminho do
    ``reassert_rumble`` e do ``apply_rumble_policy``, que não dependem de
    gamepad virtual nenhum. Sem essa metade, o aviso viraria "esta parte da
    tela não serve para nada", que é falso.

    **A PRIMEIRA FRASE ENCURTOU — 02/09/2026, decisão dela, ciente do custo.**
    Ela tinha 211 caracteres, e na aba HTML ocupava 1072 px de 1072
    disponíveis: quebrava em DUAS sublinhas, o quadro passava a rolar 40 px e a
    segunda metade — *"que você fixar aqui embaixo."* — ficava CORTADA pela
    borda de baixo do miolo. Medido no WebKit da janela do produto (1180x757,
    ``gui/ponte_da_tela.TAMANHO_NA_TELA``), com a mesa dela e ``vpads == 0``.

    A frase de hoje tem 162 caracteres, ocupa 942 px e cabe em UMA sublinha. As
    quatro informações continuam lá: o que não está acontecendo, por quê, o que
    fazer, e o que a intensidade ainda faz. Ela escolheu encurtar em vez de
    deixar a aba rolar — *"uma frase, um dono"*: **esta função é a única cópia,
    e encurtar aqui muda a janela GTK junto**, de propósito. Escrever uma
    segunda versão para a tela nova é o defeito que esta casa passou o dia
    matando.
    """
    ff = state.get("rumble_ff")
    if not isinstance(ff, dict):
        return None
    vpads = ff.get("vpads")
    if not isinstance(vpads, int) or isinstance(vpads, bool):
        return None
    native = bool(state.get("native_mode"))
    # A tradução da fronteira: o predicado quer a sequência de backends e a
    # tela só tem quantos gamepads virtuais existem. Ele pergunta "há algum?".
    backends = ("vpad",) * max(0, vpads)
    if sem_dono_do_rumble(native=native, backends=backends):
        # "NA ABA INÍCIO" MANDA A UM LUGAR QUE A INTERFACE NOVA NÃO TEM — achado
        # em 03/09/2026, na foto da aba Vibração do produto. As abas de lá são
        # Jogar · Controles · Gatilhos · Iluminação · Vibração · Navegação ·
        # Lançadores · Conexões · Sistema · Perfis: não existe "Início", e o
        # interruptor que a frase pede chama-se "Status" na aba **Jogar**.
        # A frase está CERTA na janela GTK, que tem a aba Início — é UMA string
        # com DUAS telas, e o dia em que a segunda renomeou a aba, ela ficou meio
        # verdadeira. Não a reescrevi: texto de tela é decisão dela, e o conserto
        # certo (uma frase que sirva às duas, ou o nome vindo de quem desenha a
        # aba) é escolha, não digitação.
        return (
            "A intensidade não está chegando a jogo nenhum: falta o gamepad "
            "virtual, por onde ela passa. Ligue “Jogar pelo Hefesto” na aba "
            "Início. Aqui embaixo ela ainda vale."
        )
    if vpads == 0 and native:
        # NATIVO-RUMBLE-01 (19/08/2026): a oração final desta frase dizia "Ela
        # continua valendo para a vibração que você fixar aqui embaixo" — e a
        # medição do mesmo dia mostrou que essa vibração produz **zero write no
        # fio** sob Modo Nativo. Era a frase mais precisa da aba a afirmar
        # exatamente o contrário do que o aparelho faz. Substituída, e não
        # anotada ao lado: número errado não é decisão medida.
        return (
            "Conexão Nativa (Sony): o jogo fala direto com o controle, e a "
            "intensidade acima não passa por ele. Enquanto o modo estiver "
            "ligado, fixar vibração aqui embaixo também não chega ao motor — "
            "quem manda nele é o jogo."
        )
    return None


def texto_do_teto_do_orcamento(
    pedido: float | None, orcamento: str | None
) -> str | None:
    """A linha *"150% · limitado a 30% pelo orçamento"*, ou ``None``.

    CONFIG-05 (22/08/2026), e ela é a metade visível da invariante **teto, não
    troca**: o orçamento CALCULA, a aba de origem só EXIBE. Nada aqui reescreve
    a escolha dela — os quatro botões seguem afundando onde ela os pôs, o
    deslizador segue mostrando o número que ela escolheu, e voltar o orçamento
    para Balanceado devolve tudo sem um clique a mais. Espelhar estado entre
    abas é a classe de defeito que a `ABAS-01` curou, e esta linha é o formato
    que não a repete.

    ``None`` = **a linha não aparece**, e são quatro os silêncios, na ordem em
    que a função pergunta. A disciplina é a do
    :func:`texto_do_alcance_da_intensidade` acima, palavra por palavra: *"não
    sei" e "não chega" mandam caçar em lugares opostos*.

    1. **Ninguém declarou orçamento** (``orcamento is None``). Afirmar um teto
       aqui seria inventar um limite que o daemon não impõe.
    2. **O orçamento não impõe teto** — ``balanceado``, ``max``, e também o
       ``auto``, cujo teto é MÓVEL: ele muda a cada tique com a bateria, e a
       casa já decidiu não prometer número móvel na tela
       (`profiles/manager.py:1556-1567`). Um "limitado a 70%" que vira 30% no
       minuto seguinte ensina a desconfiar da tela inteira.
    3. **Não se sabe o que a aba está pedindo** (``pedido is None``): política
       fora dos degraus conhecidos, deslizador ainda não lido.
    4. **O teto não morde** (``pedido <= teto``): o número que a aba mostra é
       exatamente o que chega ao controle, e dizer "limitado" seria falso.

    O percentual do teto sai de :func:`core.rumble.teto_do_orcamento`, que o
    deriva de ``RUMBLE_POLICY_MULT``. Esta aba não recalcula degrau nenhum: a
    única cópia autorizada em ``app/`` é o ``_POLICY_MULT`` do topo deste
    arquivo, e há teste que vigia isso por grep.
    """
    from hefesto_dualsense4unix.core.rumble import teto_do_orcamento

    if pedido is None:
        return None
    teto = teto_do_orcamento(orcamento)
    if teto is None or pedido <= teto:
        return None
    return (
        f"{round(pedido * 100)}% · limitado a {round(teto * 100)}% pelo orçamento"
    )


#: RUM-1 (25/08/2026) — a frase que a docstring de
#: :meth:`RumbleActionsMixin._gravar_intensidade_no_rascunho` já escreveu em
#: 10/08 e que nunca chegou à tela: *"o que ela ouve na hora é o global; o que
#: ela SALVA é da peça"*.
#:
#: **O defeito que ela confessa.** Com um controle escolhido no seletor, o
#: clique grava a intensidade no override daquela peça E manda
#: ``rumble.policy_set`` **sem endereço** — que é da máquina inteira. A tela
#: afirmava o alvo três centímetros acima e não dizia uma palavra sobre isso.
#:
#: **Isto é o ramo "rótulo honesto agora" da D-G dela**, e não a cura da
#: divergência: a intensidade por peça ao vivo é a E1 da MESA-CHEIA-05
#: (~11 h medidas) e a palavra é dela. A mentira é o que fere; a granularidade
#: é conforto.
#:
#: Público porque a mordida de ``tests/unit/test_rumble_por_jogador_01.py`` o
#: lê daqui em vez de redigitar a frase — duas cópias de um texto de tela
#: divergem na primeira edição, e esta casa já pagou por isso.
TEXTO_ONDE_GRAVA_E_ONDE_MANDA = (
    "Com um controle escolhido: a intensidade acima vale agora para todos os "
    "controles ligados — só o que você salvar no perfil fica deste controle."
)


#: RUM-3 (25/08/2026) — a oração que o toast ganha quando o gesto APAGOU o
#: ajuste próprio da peça escolhida.
#:
#: **O defeito, medido em 24/08.** Com uma peça no seletor, clicar "Auto"
#: limpa o override dela (``draft_config.with_controller_rumble``: o esquema
#: recusa ``auto`` por unidade, porque ele escala pela bateria do controle
#: PRINCIPAL). A regra está certa e é deliberada; o que a tela fazia era
#: afundar o botão, mandar ``auto`` global e dizer só *"Intensidade da
#: vibração: Auto"* — indistinguível do caso "Todos", com o ajuste daquela
#: peça apagado em silêncio.
#:
#: Começa com " — " porque é sufixo do toast, e o toast é uma linha só.
TEXTO_A_PECA_VOLTOU_AO_AJUSTE_GERAL = (
    " — e este controle voltou ao ajuste geral: o Auto escala pela bateria do "
    "controle principal, então ele vale para a mesa toda, nunca para um só."
)


def texto_de_onde_grava_e_onde_manda(alvo: AlvoDeEdicao) -> str | None:
    """O aviso de alcance do GESTO; ``None`` = não há divergência a confessar.

    Três estados, três respostas — o contrato do
    :mod:`app.alvo_de_edicao`, na letra:

    * ``CONTROLE`` → a frase. É o único estado em que a aba grava num lugar
      (o override da peça) e manda em outro (a política global do daemon);
    * ``TODOS`` → ``None``. Ali o que ela grava e o que ela manda são a mesma
      coisa: não há divergência, e um aviso permanente viraria ruído crônico —
      a mesma disciplina do :func:`texto_do_alcance_da_intensidade`;
    * ``DESCONHECIDO`` → ``None``. A janela não sabe o alvo, e portanto não
      escreve nada no rascunho (``_gravar_intensidade_no_rascunho`` recusa).
      Prometer "fica deste controle" sem saber qual seria inventar um fato.
    """
    if alvo.estado is EstadoDoAlvo.CONTROLE:
        return TEXTO_ONDE_GRAVA_E_ONDE_MANDA
    return None


def _rotulo_do_teto(host: Any) -> Any:
    """O rótulo da linha de teto, criado na primeira vez que faz falta.

    Nasce em código e não no Glade porque o dono do Glade nesta leva é outra
    frente, e um rótulo a mais no XML seria conflito garantido no mesmo bloco.
    O molde: cria ao lado de um widget que já existe, devolve ``None`` quando não
    há onde pendurá-lo, e nunca levanta.

    Vai para o fim da caixa do card "Intensidade da vibração", logo abaixo do
    `rumble_policy_aviso` — que é o último filho dela no `main.glade`. Os dois
    são vizinhos de propósito: um diz que a intensidade não ALCANÇA o jogo, o
    outro diz que ela alcança mas CHEGA limitada, e são as duas metades da
    mesma pergunta ("por que não sinto o que escolhi?").
    """
    existente = getattr(host, "_rumble_teto_label", None)
    if existente is not None:
        return existente
    try:
        aviso = host._get("rumble_policy_aviso")
        if aviso is None:
            return None
        caixa = aviso.get_parent()
        if caixa is None:
            return None
        rotulo = Gtk.Label()
        rotulo.set_use_markup(True)
        rotulo.set_xalign(0.0)
        rotulo.set_line_wrap(True)
        rotulo.set_no_show_all(True)
        caixa.pack_start(rotulo, False, False, 0)
        rotulo.hide()
    except Exception:
        return None
    host._rumble_teto_label = rotulo
    return rotulo


def _pintar_a_linha_do_teto(host: Any, policy: str, custom_mult: float | None) -> None:
    """Acende (ou apaga) a linha de teto do orçamento na aba Rumble.

    Função de módulo, e não método do mixin, por uma razão medida: o dublê de
    ``tests/unit/test_rumble_actions.py`` monta a aba por COMPOSIÇÃO, ligando
    uma lista EXPLÍCITA de métodos — todo método novo no mixin nasce ausente
    lá, e o primeiro sintoma é um ``AttributeError`` no meio de uma tela que não
    tem nada a ver com a mudança. A mesma armadilha está escrita no docstring de
    ``_update_rumble_state_label``.

    O rótulo é procurado ANTES da leitura do orçamento, e a ordem importa: sem
    rótulo não há o que pintar, e assim a montagem sem Glade (dublê, retrato)
    não encosta no disco.
    """
    rotulo = _rotulo_do_teto(host)
    if rotulo is None:
        return
    from hefesto_dualsense4unix.app.actions.config.secao_orcamento import (
        orcamento_em_vigor,
    )

    pedido = custom_mult if policy == "custom" else _POLICY_MULT.get(policy)
    texto = texto_do_teto_do_orcamento(pedido, orcamento_em_vigor(host))
    if texto is None:
        rotulo.set_visible(False)
        return
    # `#ffb86c` é o token de ALERTA da casa (`gui/theme.css`), o mesmo do aviso
    # de alcance logo acima. O texto não leva `<`, `&` nem aspas, então entra
    # inteiro no markup do Pango — mesma costura do rótulo de estado.
    rotulo.set_markup(f'<span foreground="#ffb86c">{texto}</span>')
    rotulo.set_visible(True)


def _rotulo_do_alcance_do_gesto(host: Any) -> Any:
    """O rótulo da frase de RUM-1, criado na primeira vez que faz falta.

    Nasce em código e não no Glade pelo motivo já registrado no
    :func:`_rotulo_do_teto`: ``main.glade`` é XML único, sem seções nomeadas, e
    conflito de merge nele é irrecuperável na prática. O molde é o mesmo — cria
    ao lado de um widget que já existe, devolve ``None`` quando não há onde
    pendurá-lo, e nunca levanta.

    Vizinho dos outros dois avisos do card "Intensidade da vibração", e a
    ordem entre eles é a ordem das perguntas: *"ela alcança o jogo?"*
    (``rumble_policy_aviso``), *"ela chega inteira?"* (o teto) e *"ela vale
    para quem?"* (esta). As três metades da mesma dúvida.
    """
    existente = getattr(host, "_rumble_alcance_do_gesto_label", None)
    if existente is not None:
        return existente
    try:
        aviso = host._get("rumble_policy_aviso")
        if aviso is None:
            return None
        caixa = aviso.get_parent()
        if caixa is None:
            return None
        rotulo = Gtk.Label()
        rotulo.set_use_markup(True)
        rotulo.set_xalign(0.0)
        rotulo.set_line_wrap(True)
        rotulo.set_no_show_all(True)
        caixa.pack_start(rotulo, False, False, 0)
        rotulo.hide()
    except Exception:
        return None
    host._rumble_alcance_do_gesto_label = rotulo
    return rotulo


def _pintar_a_linha_do_alcance_do_gesto(host: Any) -> None:
    """Acende (ou apaga) a frase de RUM-1 na aba Rumble.

    Função de módulo, e não método do mixin, pela razão medida que já está no
    :func:`_pintar_a_linha_do_teto`: o dublê de ``test_rumble_actions.py`` monta
    a aba por COMPOSIÇÃO, ligando uma lista EXPLÍCITA de métodos, e todo método
    novo no mixin nasce ausente lá.

    O alvo é lido pelo dono único (``alvo_de_edicao``), nunca pelo ``getattr``
    do atributo legado — a queda silenciosa que o P3 curou.
    """
    rotulo = _rotulo_do_alcance_do_gesto(host)
    if rotulo is None:
        return
    texto = texto_de_onde_grava_e_onde_manda(alvo_de_edicao(host))
    if texto is None:
        rotulo.set_visible(False)
        return
    # `#8be9fd` é o token de INFO da casa (`gui/theme.css`): a frase explica,
    # não alarma — quem alarma é o aviso de alcance, em laranja, logo acima. O
    # texto não leva `<`, `&` nem aspas retas, então entra inteiro no markup do
    # Pango, mesma costura dos outros dois rótulos deste card.
    rotulo.set_markup(f'<span foreground="#8be9fd">{texto}</span>')
    rotulo.set_visible(True)


def _inteiro(valor: Any) -> int | None:
    """O inteiro do payload, ou ``None`` quando o campo não veio (daemon velho).

    RUMBLE-QUE-NAO-SE-SENTE-01. `bool` é `int` em Python e entraria como 0/1 —
    a mesma blindagem que o resto desta aba já faz.
    """
    if isinstance(valor, int) and not isinstance(valor, bool):
        return valor
    return None


class RumbleActionsMixin(WidgetAccessMixin):
    """Controla a aba Rumble."""

    # Guard para evitar loop widget->draft->refresh->widget.
    _rumble_guard_refresh: bool = False
    # Política corrente (espelhada localmente para guard de toggle).
    _rumble_policy: str = "balanceado"

    # --- instalação ---

    def install_rumble_tab(self) -> None:
        """Inicializa estado da aba Rumble a partir de state_full ou defaults.

        Configura o toggle ativo conforme política e atualiza slider.
        """
        self._sync_policy_from_state()

    def _sync_policy_from_state(self, *, indicar_sem_opiniao: bool = False) -> None:
        """Lê política atual via state_full e sincroniza widgets.

        BUG-RUMBLE-POLICY-DRAFT-DIVERGE-01: o estado do daemon é SÓ exibição —
        nunca é gravado no draft (senão todo perfil ganharia opinião de
        política só de abrir a aba). Com ``indicar_sem_opiniao``, avisa na
        statusbar que o perfil não tem opinião (o "Salvar Perfil" do rodapé
        não vai persistir política até a usuária escolher uma).
        """
        def _on_state(result: Any) -> bool:
            if isinstance(result, dict):
                policy = result.get("rumble_policy", "balanceado")
                custom_mult = result.get("rumble_policy_custom_mult", _MULT_PADRAO)
            else:
                policy = "balanceado"
                custom_mult = _MULT_PADRAO
            self._apply_policy_to_widgets(str(policy), float(custom_mult))
            # Feature #4 (auditoria): consome rumble_passthrough / rumble_active /
            # rumble_ff do state_full — antes nada na GUI mostrava se a vibração
            # estava DEVOLVIDA ao jogo ou FIXA, nem se o jogo pediu FF.
            self._update_rumble_state_label(result if isinstance(result, dict) else {})
            if indicar_sem_opiniao:
                self._toast_rumble(
                    "Política exibida = estado atual do daemon; o perfil não "
                    "tem opinião (escolha uma política para salvá-la no perfil)."
                )
            return False

        def _on_err(_exc: Exception) -> bool:
            # Sem resposta, a aba NÃO SABE a política — e afirmar uma é mentir.
            # Pintava "Balanceado / 70%" por cima da política real (repro: daemon
            # em "max", state_full passando dos 250ms durante um hotplug), e o
            # que ela via passava a divergir do que o controle faz.
            return False

        call_async(
            "daemon.state_full",
            {},
            on_success=_on_state,
            on_failure=_on_err,
            # HARM-15: o daemon monta o state_full varrendo os controles; sob
            # carga (hotplug, co-op subindo) não cabe nos 0.25s default.
            timeout_s=STATE_IPC_TIMEOUT_S,
        )

    def _apply_policy_to_widgets(self, policy: str, custom_mult: float) -> None:
        """Reflete política e mult nos widgets sem disparar callbacks de sinal."""
        if self._rumble_guard_refresh:
            return
        self._rumble_guard_refresh = True
        self._rumble_policy = policy
        try:
            # Ativa o toggle correto.
            btn_id = {
                "economia": "rumble_policy_economia",
                "balanceado": "rumble_policy_balanceado",
                "max": "rumble_policy_max",
                "auto": "rumble_policy_auto",
                "custom": None,
            }.get(policy)

            for pid in ("rumble_policy_economia", "rumble_policy_balanceado",
                        "rumble_policy_max", "rumble_policy_auto"):
                btn: Gtk.ToggleButton = self._get(pid)
                if btn is not None:
                    btn.set_active(pid == btn_id)

            # Slider de intensidade.
            slider: Gtk.Scale = self._get("rumble_policy_slider")
            if slider is not None:
                if policy == "custom":
                    slider.set_value(custom_mult * 100.0)
                elif policy in _POLICY_MULT:
                    slider.set_value(_POLICY_MULT[policy] * 100.0)

            # Label Auto: visível só em modo auto.
            lbl: Gtk.Label = self._get("rumble_policy_auto_label")
            if lbl is not None:
                lbl.set_visible(policy == "auto")
        finally:
            self._rumble_guard_refresh = False
        # CONFIG-05: FORA do guard. O guard existe para não reentrar em handler
        # de sinal, e pintar um rótulo não dispara nenhum; dentro dele, uma
        # exceção da pintura deixaria o guard preso em True e a aba inteira
        # muda para sempre.
        _pintar_a_linha_do_teto(self, policy, custom_mult)
        # RUM-1: e a mesma pintura para o alcance do GESTO — é aqui que a aba
        # se monta, e é montada que ela precisa confessar onde grava e onde
        # manda. Sem esta linha a frase só apareceria depois de um clique.
        _pintar_a_linha_do_alcance_do_gesto(self)

    # --- handlers dos toggles de política ---

    def on_rumble_policy_economia(self, _btn: Gtk.ToggleButton) -> None:
        # A1: NÃO curto-circuitar em get_active()==False. Os 4 toggles são
        # GtkToggleButton independentes: clicar num já-ativo o desmarca
        # (get_active()==False), e o antigo `not btn.get_active(): return`
        # virava clique morto (nenhuma política afundada + IPC não reenviado).
        # Agora todo clique cai em _set_policy, que re-afirma o botão certo
        # (desmarcando os irmãos) e reenvia o IPC — sempre exatamente 1 afundado.
        if self._rumble_guard_refresh:
            return
        self._set_policy("economia")

    def on_rumble_policy_balanceado(self, _btn: Gtk.ToggleButton) -> None:
        if self._rumble_guard_refresh:
            return
        self._set_policy("balanceado")

    def on_rumble_policy_max(self, _btn: Gtk.ToggleButton) -> None:
        if self._rumble_guard_refresh:
            return
        self._set_policy("max")

    def on_rumble_policy_auto(self, _btn: Gtk.ToggleButton) -> None:
        if self._rumble_guard_refresh:
            return
        self._set_policy("auto")

    def _set_policy(self, policy: str) -> None:
        """Envia política ao daemon e atualiza slider para valor canônico."""
        self._rumble_policy = policy
        slider: Gtk.Scale = self._get("rumble_policy_slider")
        # A1: exclusão mútua ANTES do IPC — desmarca os irmãos e re-afirma o
        # botão certo (mesmo quando o clique num já-ativo o desmarcou), sob guard
        # para os "toggled" reentrantes dos irmãos não reentrarem nos handlers de
        # política. Junto, move o slider para o valor canônico (feedback visual).
        self._rumble_guard_refresh = True
        try:
            self._activate_policy_toggle(policy)
            if slider is not None:
                pct = int(_POLICY_MULT.get(policy, _MULT_PADRAO) * 100)
                slider.set_value(float(pct))
        finally:
            self._rumble_guard_refresh = False

        # Label Auto.
        lbl: Gtk.Label = self._get("rumble_policy_auto_label")
        if lbl is not None:
            lbl.set_visible(policy == "auto")

        # CONFIG-05: o degrau novo pode passar a bater no teto do orçamento (ou
        # deixar de bater), e a linha tem de acompanhar o clique — não só a
        # entrada na aba.
        _pintar_a_linha_do_teto(self, policy, None)
        # RUM-1: o seletor pode ter mudado desde a montagem, e a confissão de
        # alcance vale para o clique de AGORA.
        _pintar_a_linha_do_alcance_do_gesto(self)

        # FEAT-RUMBLE-POLICY-PROFILE-01: além do daemon vivo, grava a escolha
        # no draft — o "Salvar Perfil" do rodapé persiste a política que a
        # usuária vê. Preset zera custom_mult (o valor só faz sentido em
        # policy="custom"; o schema do perfil rejeita a combinação).
        apagou_o_ajuste_da_peca = self._gravar_intensidade_no_rascunho(policy, None)

        # HARM-19: recusa do daemon VIVO (motivo preenchido) não pode virar
        # acusação de daemon morto — é o tratamento que os gatilhos já têm.
        ok, motivo = rumble_policy_set_checked(policy, timeout=STATE_IPC_TIMEOUT_S)
        if ok:
            texto = f"Intensidade da vibração: {_POLICY_LABEL.get(policy, policy)}"
            # RUM-3: o gesto apagou o ajuste próprio daquela peça. O toast tem
            # de NOMEAR o apagamento — sem esta oração ele é indistinguível do
            # caso "Todos", e o override some sem uma palavra.
            if apagou_o_ajuste_da_peca:
                texto += TEXTO_A_PECA_VOLTOU_AO_AJUSTE_GERAL
        elif motivo:
            texto = f"O Hefesto não aceitou essa intensidade: {motivo}"
        else:
            texto = "O Hefesto não está rodando — ligue na aba Sistema."
        self._toast_rumble(texto)

    # --- handler do slider de intensidade ---

    def on_rumble_policy_slider_changed(self, slider: Gtk.Scale) -> None:
        """Deslizador movido: a intensidade vira um ajuste dela (mult = valor/100).

        **O silêncio que isto cura** (11/08/2026): mover o deslizador para fora
        dos degraus dos quatro botões APAGAVA os quatro — nenhum ficava
        afundado — e não dizia uma palavra. O irmão deste caminho (`_set_policy`,
        o clique num botão) sempre falou na barra de estado; este não, e a
        palavra "personalizado" não existe em lugar nenhum da tela. A usuária
        ficava olhando quatro botões apagados sem saber que tinha escolhido algo,
        nem o quê.

        Agora ele fala no MESMO formato do irmão — ``"Intensidade da vibração:
        …"`` — e diz o número, que é a única coisa que a tela ainda mostra
        depois de apagar os botões. E fala também quando o Hefesto recusa: o
        ``rumble.policy_custom`` já devolvia False sem ninguém olhar.
        """
        if self._rumble_guard_refresh:
            return
        mult = slider.get_value() / 100.0
        # Se o mult coincide exatamente com um preset, escolhê-lo.
        for policy, canon_mult in _POLICY_MULT.items():
            if policy == "auto":
                continue
            if abs(mult - canon_mult) < 0.005:
                if self._rumble_policy != policy:
                    self._rumble_guard_refresh = True
                    try:
                        self._activate_policy_toggle(policy)
                    finally:
                        self._rumble_guard_refresh = False
                    self._set_policy(policy)
                return

        # Mult não é preset: modo custom.
        self._rumble_guard_refresh = True
        try:
            for pid in ("rumble_policy_economia", "rumble_policy_balanceado",
                        "rumble_policy_max", "rumble_policy_auto"):
                btn: Gtk.ToggleButton = self._get(pid)
                if btn is not None:
                    btn.set_active(False)
            lbl: Gtk.Label = self._get("rumble_policy_auto_label")
            if lbl is not None:
                lbl.set_visible(False)
        finally:
            self._rumble_guard_refresh = False

        self._rumble_policy = "custom"
        # CONFIG-05: o deslizador é o caminho que mais bate no teto — ele sobe
        # até 200%, e o Economia da mesa limita em 30%.
        _pintar_a_linha_do_teto(self, "custom", mult)
        # RUM-1: o ajuste do deslizador grava na peça e manda na mesa pelo
        # MESMO par de caminhos do clique num botão — a confissão vale igual.
        _pintar_a_linha_do_alcance_do_gesto(self)
        # FEAT-RUMBLE-POLICY-PROFILE-01: persiste o custom no draft (mesma
        # razão do preset em `_set_policy` — o rodapé salva o que ela vê).
        self._gravar_intensidade_no_rascunho("custom", mult)
        ok = rumble_policy_custom(mult)
        self._toast_rumble(
            f"Intensidade da vibração: {round(mult * 100)}% "
            "(ajuste seu — nenhum dos quatro botões vale agora)"
            if ok
            else "O Hefesto não está rodando — ligue na aba Sistema."
        )

    # --- POR-UNIDADE-01 (10/08/2026): a intensidade é da PEÇA ---

    def _rumble_edit_uniq(self) -> AlvoDeEdicao:
        """O alvo de edição escolhido no seletor (PERFIL-04).

        MESMA fonte da Lightbar e dos Gatilhos (`app/alvo_de_edicao.py`, o
        dono único) — o seletor é UM só, e o selo ao lado dele já diz qual
        peça está sendo editada. Z2-1 (24/08/2026): antes lia o atributo
        legado por `getattr` cru — o `None` da janela que não sabia o alvo
        virava, silenciosamente, "Todos".
        """
        return alvo_de_edicao(self)

    def _gravar_intensidade_no_rascunho(
        self, policy: str, mult: float | None
    ) -> bool:
        """Anota a intensidade escolhida no rascunho — global ou da peça.

        Devolve **``True`` quando o gesto APAGOU o ajuste próprio da peça**
        escolhida (RUM-3, 25/08/2026) — a única informação que o chamador não
        tem como recuperar depois, e a que ele precisa para dizer o que
        aconteceu. ``False`` em todos os outros caminhos, inclusive no "Todos"
        e no alvo desconhecido.

        POR-UNIDADE-01, pedido dela em 10/08/2026: *"uma guia específica do
        perfil X pro controle branco e outra pro mesmo perfil pra um controle
        preto"*. O molde é o da Lightbar, linha por linha: alvo "Todos" grava
        o GLOBAL e LIMPA o campo dos overrides (senão a peça ressuscitaria a
        intensidade velha na próxima ativação — o fix HIGH de 2026-07-16, que
        vale igual aqui); alvo específico grava só na peça, semeado com o
        efetivo em tela.

        NOTA HONESTA sobre o daemon vivo: o ``rumble.policy_set``/
        ``policy_custom`` que sai logo depois deste registro é GLOBAL — não há
        IPC de política por unidade, e inventar um seria mecanismo novo. O que
        vale por peça chega ao hardware pelo "Aplicar" do rodapé e pela
        ativação do perfil (a escala do backend, ``set_rumble_scales``). Com
        uma peça selecionada, portanto, o que ela ouve na hora é o global; o
        que ela SALVA é da peça. **Essa frase virou tela em RUM-1**
        (:data:`TEXTO_ONDE_GRAVA_E_ONDE_MANDA`); ela passou de 10/08 a 25/08
        escrita só aqui dentro, onde nenhuma usuária lê.
        """
        draft = getattr(self, "draft", None)
        if draft is None:
            return False
        estado_alvo = self._rumble_edit_uniq()
        if estado_alvo.desconhecido:
            # Z2-1: a janela não sabe o alvo — zero escrita no rascunho, e
            # nunca cai no ramo "Todos" (que limparia os overrides de peça).
            return False
        uniq = estado_alvo.uniq
        if uniq is None:
            new_rumble = draft.rumble.model_copy(
                update={"policy": policy, "custom_mult": mult}
            )
            draft = draft.model_copy(update={"rumble": new_rumble})
            self.draft = draft.with_override_fields_cleared(
                "rumble", {"policy", "custom_mult"}
            )
            return False
        # RUM-3: o ANTES da peça, lido antes de escrever. `with_controller_rumble`
        # LIMPA o override em três casos (igual ao global, `policy=None` e
        # `auto`), e o "Auto" é o que a tela não contava: o botão afunda, o
        # daemon recebe `auto` global, o toast diz "Auto" — e o ajuste próprio
        # daquela peça sumiu sem uma palavra. A regra está certa (o esquema
        # recusa `auto` por unidade, porque ele escala pela bateria do controle
        # PRINCIPAL); o que faltava era contar.
        antes = getattr(draft.controller_override(uniq), "rumble", None)
        base = draft.effective_rumble_for(uniq)
        novo = draft.with_controller_rumble(
            uniq, base.model_copy(update={"policy": policy, "custom_mult": mult})
        )
        self.draft = novo
        depois = getattr(novo.controller_override(uniq), "rumble", None)
        return antes is not None and depois is None

    def _activate_policy_toggle(self, policy: str) -> None:
        """Ativa o toggle correspondente à política (sem guard)."""
        btn_map = {
            "economia": "rumble_policy_economia",
            "balanceado": "rumble_policy_balanceado",
            "max": "rumble_policy_max",
            "auto": "rumble_policy_auto",
        }
        target_id = btn_map.get(policy)
        for pid in btn_map.values():
            btn: Gtk.ToggleButton = self._get(pid)
            if btn is not None:
                btn.set_active(pid == target_id)

    # --- handlers de teste de motores ---

    # M6 (auditoria): id do timer do teste de 500ms em curso (GLib source), para
    # cancelá-lo se a usuária clicar Parar/Aplicar/Devolver ou testar de novo
    # dentro da janela — senão o `_rumble_test_stop` pendente desfazia a ação.
    _rumble_test_source: int | None = None

    def _cancel_rumble_test_timer(self) -> None:
        src = self._rumble_test_source
        if src is not None:
            with contextlib.suppress(Exception):
                GLib.source_remove(src)
            self._rumble_test_source = None

    def on_rumble_apply(self, _btn: Gtk.Button) -> None:
        self._cancel_rumble_test_timer()
        weak, strong = self._read_scales()
        # Persiste no draft antes de enviar via IPC.
        draft = getattr(self, "draft", None)
        if draft is not None:
            new_rumble = draft.rumble.model_copy(update={"weak": weak, "strong": strong})
            self.draft = draft.model_copy(update={"rumble": new_rumble})
        # NATIVO-RUMBLE-01 (19/08/2026): o `ok` mudo dizia "travada" com o motor
        # parado. A recusa do daemon vem no CORPO da resposta (`status`), não
        # como erro JSON-RPC — por isso `rumble_set_checked` e não o
        # `_call_checked` da aba Gatilhos. Com motivo preenchido o daemon está
        # VIVO e recusou: acusá-lo de desligado mandaria ela caçar o problema no
        # lugar errado, que é o defeito que o HARM-19 já pagou uma vez.
        ok, motivo = rumble_set_checked(weak, strong)
        if motivo:
            self._toast_rumble(motivo)
        else:
            self._toast_rumble(
                f"Vibração travada (fraca={weak}, forte={strong}) — enquanto travada o "
                f"jogo NÃO controla a vibração; clique “{_BTN_GIVE_BACK_TO_GAME}” "
                "para jogar"
                if ok
                else f"Vibração {_MSG_HEFESTO_OFF}"
            )

    def on_rumble_test_500ms(self, _btn: Gtk.Button) -> None:
        # Cancela um teste anterior ainda em curso antes de armar o novo.
        self._cancel_rumble_test_timer()
        weak, strong = self._read_scales()
        if weak == 0 and strong == 0:
            weak = 160
            strong = 220
            self._set_scales(weak, strong)
        # NATIVO-RUMBLE-01: e o teste não arma o temporizador de 500 ms quando o
        # daemon recusou — sem isso o `_rumble_test_stop` dispararia um `Parar`
        # sobre um pedido que nunca existiu.
        ok, motivo = rumble_set_checked(weak, strong)
        if motivo:
            self._toast_rumble(motivo)
            return
        if not ok:
            self._toast_rumble(f"Teste {_MSG_HEFESTO_OFF}")
            return
        self._toast_rumble(f"Testando por meio segundo (fraca={weak}, forte={strong})")
        self._rumble_test_source = GLib.timeout_add(500, self._rumble_test_stop)

    def _zerar_rumble_no_rascunho(self, *, passthrough: bool | None = None) -> None:
        """Baixa ``weak``/``strong`` do rascunho — e, opcionalmente, ``passthrough``.

        ABAS-04 (25/07): "Parar" e "Deixar o jogo controlar a vibração" zeravam
        os controles deslizantes e mandavam o IPC, mas NÃO escreviam no
        rascunho. As consequências, as duas medidas:

        1. o rascunho seguia com os valores antigos, e ``to_ipc_dict`` emite a
           seção ``rumble`` SEMPRE — então o próximo "Aplicar" de QUALQUER aba
           (mexer no brilho já basta) re-travava a vibração que ela acabara de
           mandar parar;
        2. voltar à aba Rumble chamava ``_refresh_rumble_from_draft``, que
           repinta os deslizantes a partir do rascunho — os valores antigos
           reapareciam. A aba MENTIA sobre o estado parado.

        ``passthrough`` só é escrito com ``True``, e deliberadamente. O campo é
        persistido no perfil (``RumbleConfig.passthrough``) e, na ativação,
        ``True`` é o que SOLTA um rumble fixado em valor não-zero — a segunda
        metade da cura do "testei os motores e o jogo não vibra mais"
        (SPRINT-GAME-RUMBLE-01) e a rede de segurança do RUMBLE-PRESO-01.
        Gravar ``False`` a partir do "Aplicar"/"Parar" congelaria a trava no
        JSON e ressuscitaria as duas queixas; o silêncio deliberado do "Parar"
        já sobrevive à ativação por conta própria (o applier preserva ``(0,0)``,
        M2 da auditoria), então não precisa desse campo para nada.
        """
        draft = getattr(self, "draft", None)
        if draft is None:
            return
        update: dict[str, Any] = {"weak": 0, "strong": 0}
        if passthrough is not None:
            update["passthrough"] = passthrough
        self.draft = draft.model_copy(
            update={"rumble": draft.rumble.model_copy(update=update)}
        )

    def on_rumble_stop(self, _btn: Gtk.Button) -> None:
        """Para rumble via rumble.stop (BUG-RUMBLE-APPLY-IGNORED-01).

        Usa rumble_stop() em vez de rumble_set(0, 0) para que o daemon
        persista (0, 0) e o poll loop re-afirme silêncio continuamente,
        evitando que write HID residual reative os motores.

        ABAS-04: zera o rascunho junto — sem isso o próximo "Aplicar" de
        qualquer aba re-travava a vibração parada (ver
        ``_zerar_rumble_no_rascunho``).
        """
        self._cancel_rumble_test_timer()
        self._set_scales(0, 0)
        self._zerar_rumble_no_rascunho()
        # NATIVO-RUMBLE-01, segunda metade (20/08/2026): este era o terceiro
        # botão, e o único que ficou mentindo depois da leva de 19/08. No Modo
        # Nativo o daemon não trava silêncio — ele SOLTA o par e diz que não
        # alcança o motor do jogo. Anunciar "travada em silêncio" ali era prometer
        # exatamente o que não aconteceu.
        _ok, motivo = rumble_stop_checked()
        self._toast_rumble(
            motivo
            or (
                f"Vibração parada (travada em silêncio) — clique "
                f"“{_BTN_GIVE_BACK_TO_GAME}” para o jogo voltar a controlar a vibração"
            )
        )

    def on_rumble_passthrough(self, _btn: Gtk.Button) -> None:
        """Devolve o controle da vibração ao JOGO (FEAT-RUMBLE-PASSTHROUGH-GUI-01).

        Chama rumble.passthrough(True): o daemon zera rumble_active (None) e o poll
        loop PARA de re-afirmar (0,0), deixando o jogo controlar os motores. É o
        antídoto do 'Parar' (que fixa silêncio). Sem este botão, depois de 'Parar'
        só dava pra devolver o rumble pela CLI — a auditoria flagou a lacuna de
        auto-suficiência.

        ABAS-04: é o único gesto da janela que diz "o JOGO manda na vibração",
        e é aqui que ``RumbleDraft.passthrough`` finalmente é escrito — o campo
        existia desde a v1 do perfil e NENHUMA superfície o editava, apesar de
        o botão estar na tela. Num perfil que trazia ``passthrough: false``, o
        clique não sobrevivia ao "Salvar Perfil": a ativação seguinte
        re-travava a vibração.
        """
        self._cancel_rumble_test_timer()
        self._set_scales(0, 0)
        self._zerar_rumble_no_rascunho(passthrough=True)
        ok = rumble_passthrough(True)
        self._toast_rumble(
            "Pronto — agora o jogo controla a vibração"
            if ok
            else f"Vibração {_MSG_HEFESTO_OFF}"
        )

    # --- refresh do draft ---

    def _refresh_rumble_from_draft(self) -> None:
        """Popula widgets da aba Rumble a partir de self.draft.rumble e state_full.

        Protegido por _rumble_guard_refresh para não disparar handlers de sinal
        durante a atualização programática dos sliders.
        """
        if self._rumble_guard_refresh:
            return
        draft = getattr(self, "draft", None)
        if draft is None:
            return
        # POR-UNIDADE-01: a aba exibe a intensidade EFETIVA do alvo escolhido
        # no seletor — o override da peça quando existe, senão o global. Mesma
        # regra de `_refresh_lightbar_from_draft`. `weak`/`strong` (o teste de
        # motores) vêm sempre do global: nunca foram do perfil.
        rumble = draft.effective_rumble_for(self._rumble_edit_uniq().uniq)
        self._rumble_guard_refresh = True
        try:
            weak_scale: Gtk.Scale = self._get("rumble_weak_scale")
            strong_scale: Gtk.Scale = self._get("rumble_strong_scale")
            if weak_scale is not None:
                weak_scale.set_value(float(rumble.weak))
            if strong_scale is not None:
                strong_scale.set_value(float(rumble.strong))
        finally:
            self._rumble_guard_refresh = False
        # BUG-RUMBLE-POLICY-DRAFT-DIVERGE-01: a política destacada na tela tem
        # de ser a MESMA que o "Salvar Perfil" do rodapé grava (draft.policy).
        if rumble.policy is not None:
            # Perfil tem opinião (ou a usuária já tocou): widgets refletem o
            # DRAFT — não o daemon, que pode estar noutra política (CLI/applet).
            mult = (
                rumble.custom_mult
                if rumble.custom_mult is not None
                else _POLICY_MULT.get(rumble.policy, _MULT_PADRAO)
            )
            self._apply_policy_to_widgets(rumble.policy, mult)
            # Feature #4: mesmo com política do perfil, o indicador de estado da
            # vibração (jogo controla / fixo + FF do jogo) vem do daemon VIVO.
            self._refresh_rumble_state_label_async()
        else:
            # Perfil SEM opinião: exibe o estado vivo do daemon como referência
            # (async — não bloqueia GTK), com indicação na statusbar e SEM
            # gravar o valor do daemon no draft. (Já atualiza o indicador.)
            self._sync_policy_from_state(indicar_sem_opiniao=True)

    def _refresh_rumble_state_label_async(self) -> None:
        """Atualiza só o indicador de estado da vibração via state_full (async)."""
        def _on_state(result: Any) -> bool:
            self._update_rumble_state_label(result if isinstance(result, dict) else {})
            return False

        call_async(
            "daemon.state_full",
            {},
            on_success=_on_state,
            on_failure=lambda _e: False,
            # HARM-15: mesma leitura, mesma folga (o indicador some por um tick
            # em vez de mostrar estado inventado).
            timeout_s=STATE_IPC_TIMEOUT_S,
        )

    # --- helpers ---

    def _read_scales(self) -> tuple[int, int]:
        # B1-rumble: None-guard — _get pode devolver None se o widget não existe
        # no builder (evita AttributeError ao desreferenciar).
        w = self._get("rumble_weak_scale")
        s = self._get("rumble_strong_scale")
        weak = int(w.get_value()) if w is not None else 0
        strong = int(s.get_value()) if s is not None else 0
        return weak, strong

    def _set_scales(self, weak: int, strong: int) -> None:
        # B1-rumble: None-guard antes de desreferenciar cada scale.
        w = self._get("rumble_weak_scale")
        if w is not None:
            w.set_value(weak)
        s = self._get("rumble_strong_scale")
        if s is not None:
            s.set_value(strong)

    def _rumble_test_stop(self) -> bool:
        # SPRINT-GAME-RUMBLE-01: fim do teste = zera os motores E DEVOLVE o
        # rumble ao jogo (passthrough). Antes fixava (0, 0), o que deixava o
        # rumble "travado em silêncio" e o FF do jogo IGNORADO (apply_game_rumble
        # só passa com rumble_active is None) até a usuária clicar "Devolver ao
        # jogo" na mão — era a origem do "testei os motores e aí o jogo não
        # vibra mais". rumble_stop() zera o motor primeiro; passthrough solta.
        # ABAS-04: o fim do teste também escreve no rascunho. Ele termina em
        # passthrough, então é o mesmo gesto do botão "Deixar o jogo controlar
        # a vibração" — e sem isto o "Aplicar" seguinte reenviava os 160/220
        # do teste como se fossem escolha dela.
        self._rumble_test_source = None  # o timer disparou; não há o que cancelar
        rumble_stop()
        rumble_passthrough(True)
        self._set_scales(0, 0)
        self._zerar_rumble_no_rascunho(passthrough=True)
        self._toast_rumble("Teste encerrado — vibração devolvida ao jogo")
        return False

    def _update_rumble_state_label(self, state: dict[str, Any]) -> None:
        """Feature #4: mostra o estado vivo da vibração na aba Rumble.

        `rumble_passthrough` True = o JOGO controla (o esperado para jogar);
        False = FIXO pela GUI (o FF do jogo é ignorado).

        A metade dos PEDIDOS DO JOGO (`rumble_ff`) é decidida pela função pura
        ``texto_dos_pedidos_de_vibracao`` — inclusive o caso em que ela ficava
        muda, que era o caso em que ela tinha algo a dizer. O que sobra aqui é
        a costura: nenhuma das frases de lá leva ``<``, ``&`` ou aspas, então
        elas entram inteiras no markup do Pango, sem escapar.

        **O aviso de alcance sai daqui também, e no MESMO ciclo** — os dois se
        alimentam do ``daemon.state_full``, e uma segunda chamada de IPC só
        para o aviso seria mais uma resposta a esperar pela mesma verdade. Ele
        fica ANTES do ``return`` do rótulo de estado de propósito: o aviso mora
        no card de cima e não pode sumir por causa de um widget do card de
        baixo que o builder não tinha.

        Não há método separado para ele, e isto é deliberado: o dublê de
        ``test_rumble_actions`` monta a aba por COMPOSIÇÃO, ligando uma lista
        explícita de métodos — todo método novo aqui nasce ausente lá, e o
        primeiro sintoma é um ``AttributeError`` no meio de uma tela que não
        tem nada a ver com a mudança.

        Escondido quando ``texto_do_alcance_da_intensidade`` devolve ``None``:
        o silêncio ali é "a intensidade alcança, ou não sei", e nos dois casos
        uma linha de alerta na tela seria pior que nenhuma."""
        aviso = self._get("rumble_policy_aviso")
        if aviso is not None:
            alcance = texto_do_alcance_da_intensidade(state)
            if alcance is None:
                aviso.set_visible(False)
            else:
                # As duas frases da função não levam `<`, `&` nem aspas retas —
                # as aspas são as tipográficas “ ”, que o Pango passa inteiras.
                # Mesma costura do rótulo de estado logo abaixo. `#ffb86c` é o
                # token de ALERTA da casa, o mesmo da vibração travada.
                aviso.set_markup(f'<span foreground="#ffb86c">{alcance}</span>')
                aviso.set_visible(True)

        label = self._get("rumble_state_label")
        if label is None:
            return
        passthrough = state.get("rumble_passthrough")
        active = state.get("rumble_active")
        if passthrough is True:
            estado = '<span foreground="#50fa7b">o JOGO controla a vibração</span>'
        elif isinstance(active, list) and len(active) == 2:
            if active == [0, 0]:
                estado = (
                    '<span foreground="#ffb86c">travada em silêncio '
                    f'(clique “{_BTN_GIVE_BACK_TO_GAME}”)</span>'
                )
            else:
                estado = (
                    f'<span foreground="#ffb86c">travada em fraca={active[0]}, '
                    f'forte={active[1]} (clique “{_BTN_GIVE_BACK_TO_GAME}” '
                    "para jogar)</span>"
                )
        else:
            estado = "—"
        pedidos = texto_dos_pedidos_de_vibracao(state)
        plays_txt = f"  ·  {pedidos}" if pedidos else ""
        label.set_markup(f"Estado da vibração: {estado}{plays_txt}")

    def _toast_rumble(self, msg: str) -> None:
        self._status_toast("rumble", msg)
