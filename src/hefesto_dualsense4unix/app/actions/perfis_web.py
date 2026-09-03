"""perfis_web — o que a aba Perfis PINTA, como DADO e nunca como HTML.

A interface nova é o mockup aprovado rodando num ``WebKit2.WebView`` dentro de
uma janela GTK3 (``D-A-INTERFACE-NOVA-E-O-MOCKUP-DENTRO-DE-UMA-JANELA-GTK``). A
janela e as duas pontes são de todas as abas e moram em
:mod:`hefesto_dualsense4unix.gui.ponte_da_tela`; **este arquivo é a parte que é
da aba Perfis**: transformar os ``Profile`` do disco, o perfil ativo e a mesa de
controles no pacote que a página recebe em UMA chamada por tique.

O destino do módulo estava decidido por escrito antes desta leva:
``docs/process/sprints/2026-08-29-MIGRA-PERFIS-03-a-lista-de-perfis-chega-viva.md``
declara ``posse: src/hefesto_dualsense4unix/app/actions/perfis_web.py``, e as
sprints 04, 05 e 06 escrevem no mesmo arquivo. Escrever noutro lugar criaria o
segundo dono no dia em que aquelas sprints rodassem.

ELE NÃO EMITE UMA LINHA DE HTML, E É O PONTO CENTRAL
-----------------------------------------------------
Num ``Gtk.TreeView``, um perfil chamado ``<b>x</b>`` é o texto ``<b>x</b>``.
**Numa página, ele é markup.** Os nomes vêm de arquivo em disco — dela,
importados, ou gerados pelo "Detectar" a partir do TÍTULO DE UMA JANELA DE JOGO,
que é texto que ninguém desta casa controla. O mesmo vale para o "Quando usar"
(que carrega ``mk1.exe`` e o título da janela) e para a dica da disputa.

Por isso o contrato desta rota é: **o Python manda DADO, a página escreve
TEXTO**. Quem monta a linha na tela é o ajudante da página, clonando o ``<tr>``
que o gerador do mockup já escreveu e preenchendo cada endereço por
``textContent``. Assim o desenho continua tendo UM dono (o
``src/hefesto_dualsense4unix/interface/aba10.py``) e nenhum caractere dela atravessa a
fronteira como marcação.

O QUE ESTE MÓDULO NÃO FAZ, E É DE PROPÓSITO
--------------------------------------------
**Não grava nada.** Nenhuma função daqui escreve perfil, chama ``save_profile``
ou pronuncia um método de IPC de escrita. A aba viva desta leva é para ela
AVALIAR; o dono real de cada gesto está declarado em :data:`DONOS_DOS_GESTOS`,
num lugar só, com arquivo e linha. É a mesma disciplina do piloto da aba
Controles.

**Não decide o que é dela decidir.** Três perguntas da onda PERFIS continuam
abertas e aparecem aqui como ESTADO HONESTO, nunca como escolha silenciosa:

1. **cinco ou seis ambientes** — ``profiles_actions._APLICA_A_ITEMS`` tem SETE
   presets e o desenho tem CINCO opções. Os três que sobram
   (``browser``/``terminal``/``editor``) NÃO viram "Todos": eles caem no estado
   :data:`AMBIENTE_QUE_A_TELA_NAO_MOSTRA`, com a regra do disco intacta. Abrir
   dizendo "Todos" é o defeito R-12 pelo avesso, e o estrago dele já aconteceu
   nesta casa (``profiles/loader.py:1229-1237``);
2. **"Estilo de Jogo"** não existe em campo, widget ou preset nenhum. Ele nasce
   TRAVADO, com o motivo — um ``<select>`` que aceita escolha e não guarda nada
   é a pior das saídas;
3. **a prioridade arrastável** — o mockup desenha um trilho que não é controle,
   e ela pediu *"prioridade é slicer"*. Aqui ele é PINTADO e não tem gesto.
"""
from __future__ import annotations

from typing import Any

from hefesto_dualsense4unix.profiles.schema import (
    PRIORIDADE_MAXIMA,
    ControllerOverrides,
    MatchCriteria,
)

# As funções PURAS que já existem e que esta rota LIGA, não reescreve. Elas
# continuam morando onde estão — a sprint MIGRA-PERFIS-03 diz isso com todas as
# letras — e é por importá-las que a tela nova e a janela de hoje nunca podem
# discordar sobre qual perfil vence a disputa.
from hefesto_dualsense4unix.app.actions.profiles_actions import (  # isort:skip
    explicacao_da_disputa,
    ordem_de_exibicao,
    rotulo_quando_usar,
)
from hefesto_dualsense4unix.profiles.simple_match import (  # isort:skip
    detect_simple_preset,
    simple_extra,
)

#: O DONO REAL DE CADA GESTO, DECLARADO NUM LUGAR SÓ, com arquivo e linha.
#:
#: Nesta leva nenhum deles é chamado: o clique chega ao Python, é registrado e
#: ecoa de volta. Um gesto que grave sem ela mandar é dano — e três dos catorze
#: **não têm motor nenhum**, o que na tela vira botão visivelmente desligado com
#: a frase do que falta, no padrão da casa (o quê, por quê, o que fazer).
#: Botão que aceita clique e não faz nada é pior que botão ausente.
DONOS_DOS_GESTOS: dict[str, str] = {
    "linha": "profiles_actions.on_profile_selection_changed:2984 → "
    "_ha_trabalho_no_editor:1909 → _populate_editor:3952. O portão do meio é "
    "que impede o editor de ser repintado por cima de trabalho não salvo.",
    "ativar": "profiles_actions.on_profile_activate:3202 — grava fato em disco "
    "(session.json e active_profile.txt), os dois manual-only desde o PERFIL-03.",
    "novo": "profiles_actions.on_profile_new:3016 → _aplicar_nascimento_com_jogo:3088.",
    "remover": "profiles_actions.on_profile_remove:3162 — PERGUNTA ANTES, e a "
    "caixa é GTK. Ela continua GTK até ela dizer o contrário: caixa em HTML é "
    "desenho novo, e desenho novo é dela.",
    "duplicar": "profiles_actions.on_profile_duplicate:3144.",
    "recarregar": "profiles_actions.on_profile_reload:3319 → "
    "_reload_profiles_store:3772 (o disco em thread, a pintura pela idle_add).",
    "editor.nome": "o campo Nome do editor; quem o lê no Salvar é "
    "profiles_actions.on_profile_save:3323.",
    "editor.prioridade": "profiles_actions._on_prioridade_tocada:4081 arma a "
    "guarda SALVAR-NAO-REBAIXA-02 sobre a `Gtk.Scale` profile_priority_scale. "
    "NO DESENHO NÃO HÁ CONTROLE: o mockup traz `<span class=\"trilho\">`, que "
    "não se arrasta. Ela pediu *\"prioridade é slicer\"* (CORRECOES-DELA.md, "
    "27/08) e a cura é vestir um `<input type=range>` com o CSS do trilho — "
    "trabalho de pixel, e é dela aprovar. ATÉ LÁ ESTE GESTO NÃO EXISTE.",
    "editor.ambiente": "profiles_actions._select_radio:3749 e "
    "_selected_simple_choice:3733, sobre profiles/simple_match.SIMPLE_MATCH_PRESETS:157.",
    "editor.jogo": "o campo livre do editor simples; o texto sai de "
    "profiles/simple_match.simple_extra:305 e volta por from_simple_choice.",
    "salvar": "footer_actions.on_save_profile:838 — O ÚNICO Salvar, por ordem "
    "dela (\"Salvar este perfil\" saiu da tela, CORRECOES-DELA.md). E ele NÃO "
    "está ligado aqui: os dois Salvar miram alvos diferentes hoje (o do rodapé "
    "grava footer_actions._perfil_que_as_abas_editam:884; o do editor gravava o "
    "alvo memorizado), e fundir sem fechar a divergência é o caminho mais curto "
    "para gravar por cima do perfil errado. Quem fecha é a ONDA-PERFIS-08.",
    # FATO ERRADO PELA METADE, SUBSTITUÍDO em 01/09/2026. Aqui estava escrito
    # que "o IPC NÃO PUBLICA o título nem a classe". A CLASSE É PUBLICADA.
    #
    # MEDIDO contra o daemon `dev` desta árvore, por `daemon.state_full`: das 49
    # chaves da resposta, SETE são de detecção de janela —
    # `window_detect_backend`, `window_detect_healthy`,
    # `window_detect_last_class`, `window_detect_current_class`,
    # `window_detect_useful_age_sec`, `window_detect_seeing` e
    # `window_detect_reason`. E o produto já lê uma delas: o
    # `profiles_actions._aplicar_nascimento_com_jogo:3088` usa
    # `window_detect_last_class` desde o PERFIL-NASCE-CERTO-01.
    #
    # O que continua verdadeiro é a outra metade: o TÍTULO não é publicado. Para
    # um "Detectar" que preencha o nome do jogo, a classe basta — e é o que a
    # interface nova passou a usar.
    "detectar": "TEM DONO, e ele é a CLASSE da janela: o `state_full` publica "
    "`window_detect_last_class` e `window_detect_current_class` "
    "(daemon/state_store.py:714). O TÍTULO é que não é publicado. Quem quiser o "
    "título espera a ONDA-PERFIS-03.",
    "voltar-a-de-ontem": "O MOTOR EXISTE E NUNCA TEVE TELA: "
    "profiles/loader.restaurar_do_historico:1509 e listar_historico:1272, com "
    "HISTORICO_MAX_VERSOES = 10 (loader.py:1246). Os únicos chamadores estão na "
    "CLI (cli/cmd_profile.py). Quem lhe dá tela é a ONDA-PERFIS-05.",
    "editor.estilo": "NÃO EXISTE EM LUGAR NENHUM: não há campo em "
    "profiles/schema.Profile, não há widget no gui/main.glade e não há preset "
    "em profiles/simple_match.SIMPLE_MATCH_PRESETS. Os seis de gênero em "
    "assets/profiles_default/ são PERFIS, não estilos. Quem lhe dá motor é a "
    "ONDA-PERFIS-04.",
}

#: O que se diz de um gesto SEM linha na tabela acima. O gerador só emite chaves
#: conhecidas, mas quem lê a tabela não é só o gerador: é qualquer DOM,
#: inclusive um adulterado por régua. Um ``KeyError`` aqui derrubaria a janela
#: dela para relatar um dono desconhecido, que é o pior dos dois males.
SEM_DONO = (
    "SEM LINHA na tabela de donos — este gesto chegou de um endereço que o "
    "gerador não escreve. Nada foi aplicado."
)

#: Os gestos que a página tem de mostrar TRAVADOS, e o motivo curto de cada um.
#: A frase longa (o quê, por quê, o que fazer) sai de :data:`DONOS_DOS_GESTOS`.
GESTOS_SEM_MOTOR: dict[str, str] = {
    "detectar": "o daemon lê a janela em foco, mas o IPC não publica o título "
    "nem a classe — sem isso não há o que detectar. (ONDA-PERFIS-03)",
    "voltar-a-de-ontem": "cada gravação já guarda a anterior, e só a linha de "
    "comando sabe restaurar. Falta a tela. (ONDA-PERFIS-05)",
    "editor.estilo": "não existe campo de Estilo de Jogo no perfil, nem preset "
    "que o resolva. A lista está desenhada; o que cada um liga, não. "
    "(ONDA-PERFIS-04)",
}

#: O rótulo do seletor "Funciona em" para cada preset do produto — e ele tem
#: CINCO entradas porque o desenho aprovado tem cinco opções.
#:
#: ``profiles_actions._APLICA_A_ITEMS:130`` tem SETE. Os três que faltam aqui —
#: ``browser``, ``terminal``, ``editor`` — não estão esquecidos: estão do lado
#: de fora do desenho, e mapeá-los para "Todos" é o que esta rota RECUSA fazer
#: (ver :func:`_ambiente_do_perfil`).
AMBIENTE_DO_PRESET: dict[str, str] = {
    "any": "Todos",
    "steam": "Steam",
    "game": "Jogo",
    "steam_game": "Jogo da Steam",
}

#: A frase do terceiro estado do seletor — o perfil cuja regra a tela não sabe
#: mostrar. **É válvula de segurança, não acabamento.** O editor de hoje tem uma
#: página avançada que existe exatamente para isto, e o docstring do produto
#: escreve o contrato: *"não bate → força modo avançado para não perder
#: informação"* (``profiles_actions._populate_editor:3952``). O desenho tem UMA
#: página; sem esta válvula, sete dos nove perfis de fábrica abririam dizendo
#: "Todos" — MEDIDO em ``assets/profiles_default/``: cinco casam por
#: ``window_title_regex`` e dois por lista de ``window_class``.
AMBIENTE_QUE_A_TELA_NAO_MOSTRA = (
    "Este perfil casa por uma regra que esta tela não sabe mostrar — o seletor "
    "fica travado para que salvar não a rebaixe. Para editá-la, use "
    "`hefesto-dualsense4unix profile` na linha de comando."
)

#: O texto no lugar da lista quando não há perfil nenhum no disco. Zero perfis é
#: estado LEGÍTIMO (usuária recém-instalada), e não é tabela vazia com cabeçalho
#: sozinho.
LISTA_VAZIA = (
    "Nenhum perfil no disco ainda. Ajuste o que quiser nas outras abas e clique "
    "em “Salvar Perfil” no rodapé — o primeiro perfil nasce daí."
)

#: O texto no lugar da tabela "Ajuste próprio" quando não há controle na mesa.
#: A tabela é POR CONTROLE PRESENTE: sem mesa não há linha a mostrar, e inventar
#: uma seria a tela afirmando um controle que não está aí.
GUARDA_SEM_MESA = (
    "Nenhum controle na mesa agora. Conecte um pelo cabo ou pelo rádio — a "
    "tabela aparece sozinha, sem recarregar esta tela."
)

#: O texto no lugar da tabela quando o Hefesto está desligado. É DIFERENTE de
#: "mesa vazia": ali o produto sabe que não há controle; aqui ele não sabe de
#: nada, e dizer "nenhum controle" seria afirmar o que não se mediu.
GUARDA_SEM_DAEMON = (
    "Hefesto desligado — abra a aba Sistema e clique em “Ligar o Hefesto”. "
    "Enquanto ele estiver parado, esta tela não sabe quais controles estão na "
    "mesa; o que o perfil guarda para cada peça continua no disco, intacto."
)

#: As seções que o perfil guarda por controle, na ordem do desenho. Não é
#: escolha de tela: são os campos de ``ControllerOverrides``, nem um a mais.
#: Campo ``None`` = sem opinião — aquele controle herda a seção global do perfil
#: (merge por campo, PERFIL-01).
#:
#: **SAI DO ESQUEMA, E NÃO DA MÃO — 03/09/2026.** Esta linha foi durante um dia
#: a tupla ``("leds", "triggers", "rumble", "speaker")``, digitada, com a
#: docstring prometendo *"são os quatro campos de `ControllerOverrides`, nem um
#: a mais"*. A promessa caiu por SEIS MINUTOS: `3f757b77` (02:50) pôs o ``mic``
#: em ``ControllerOverrides`` e `7e64c2e3` (02:56), em outra worktree, desenhou
#: a quinta coluna escrevendo no commit *"`ControllerOverrides.mic` ainda não
#: existe"*. O merge levou os dois, e o que sobrou foi a pior das combinações:
#: o daemon aplicando o mudo só daquele controle (``apply_controller_mics``), a
#: coluna com cinco glifos na tela, e o quinto APAGADO À FORÇA em todo perfil —
#: ``pintaGuarda`` faz ``!!linha.secoes['mic']``, e a chave não saía daqui.
#:
#: Derivar do esquema é o que impede a terceira vez. ``model_fields`` preserva a
#: ordem de declaração, que é a ordem do desenho (``aba10.SECOES``), e o dia em
#: que um campo novo entrar em ``ControllerOverrides`` ele aparece aqui sozinho
#: — sem ninguém precisar lembrar. Quem cobra a ordem contra o desenho é
#: ``tests/unit/test_a_coluna_do_ajuste_proprio_acende_pela_classe.py``.
SECOES_POR_CONTROLE: tuple[str, ...] = tuple(ControllerOverrides.model_fields)


def _texto_da_conta(quantos: int) -> str:
    """``"14 perfis"`` — e ``"1 perfil"``, que a tela precisa saber dizer."""
    return f"{quantos} perfil" if quantos == 1 else f"{quantos} perfis"


def _texto_do_ajuste(com_ajuste: int, total: int) -> str:
    """``"3 de 4 controles com ajuste próprio neste perfil"``.

    Sem mesa (daemon parado ou nenhum controle) o número seria inventado: o
    total é a quantidade de controles PRESENTES, e ninguém a sabe. Devolve o
    traço, que é o "não sei" honesto desta casa.
    """
    if total <= 0:
        return "— controles com ajuste próprio neste perfil"
    peca = "controle" if total == 1 else "controles"
    return f"{com_ajuste} de {total} {peca} com ajuste próprio neste perfil"


def _id_visivel(uniq: str) -> str:
    """``"aabbcc000001"`` → ``"AA:BB:CC:00:00:01"``, que é como o desenho mostra.

    A chave do dado continua sendo o ``uniq`` cru — é ela que vai no
    ``data-hef-uniq``, porque é a chave de ``Profile.controllers``
    (``profiles/schema.py:1038``, canonizada em ``:1139``). Endereço que não é a
    chave do dado obriga a inventar uma tradução, e a tradução é onde nasce a
    segunda verdade.
    """
    cru = uniq.strip().replace(":", "").replace("-", "").lower()
    if len(cru) != 12:
        return uniq or "—"
    return ":".join(cru[i : i + 2] for i in range(0, 12, 2)).upper()


def _ambiente_do_perfil(profile: Any) -> tuple[str | None, str]:
    """``(rótulo do seletor, frase do estado honesto)`` — nunca os dois cheios.

    Rótulo ``None`` quer dizer: **o seletor não sabe descrever este perfil**.
    Aí ele vai travado com a frase, e o ``match`` do disco fica intacto.

    As duas portas para o ``None``:

    1. o preset é ``browser``/``terminal``/``editor`` — existe no produto
       (``_APLICA_A_ITEMS`` tem sete) e não existe no desenho (cinco). É a
       contradição de DUAS decisões dela do MESMO dia
       (``docs/data/decisoes-dela.csv:55`` fecha em cinco; ``:84`` diz cinco
       mais "Programas"), e nenhuma lápide explica qual caducou;
    2. ``detect_simple_preset`` devolveu ``None`` — regra por título de janela,
       por lista de classes, ou ``MatchManual``. Sete dos nove perfis de fábrica
       estão aqui, MEDIDO.
    """
    match = getattr(profile, "match", None)
    preset = detect_simple_preset(match) if match is not None else None
    if preset in AMBIENTE_DO_PRESET:
        return (AMBIENTE_DO_PRESET[preset], "")
    return (None, f"{AMBIENTE_QUE_A_TELA_NAO_MOSTRA} ({_como_e_a_regra(match, preset)})")


def _como_e_a_regra(match: Any, preset: str | None) -> str:
    """Em UMA linha, o que a regra é — para ela saber o que a tela não mostra.

    Nada aqui vem de texto dela: são nomes de CAMPO do esquema e o nome do
    preset. O conteúdo (o regex, as classes) fica de fora de propósito — ele é
    dado dela, e esta frase vai para um ``title``, não para uma célula.
    """
    if preset in ("browser", "terminal", "editor"):
        rotulos = {"browser": "Navegador", "terminal": "Terminal", "editor": "Editor"}
        return f"o preset “{rotulos[preset]}” existe no produto e não no desenho"
    if isinstance(match, MatchCriteria):
        partes = []
        if match.window_title_regex:
            partes.append("título de janela")
        if match.window_class:
            partes.append(f"{len(match.window_class)} classe(s) de janela")
        if match.process_name:
            partes.append(f"{len(match.process_name)} nome(s) de programa")
        if partes:
            return "casa por " + " e ".join(partes)
        return "critério vazio: nunca ativa sozinho"
    tipo = str(getattr(match, "type", "") or "?")
    return f"regra do tipo “{tipo}”"


def _pacote_do_editor(profile: Any) -> dict[str, Any]:
    """Os cinco campos do editor, do ``Profile`` — e nenhum deles inventado."""
    ambiente, recado = _ambiente_do_perfil(profile)
    prioridade = int(getattr(profile, "priority", 0) or 0)
    match = getattr(profile, "match", None)
    # A LARGURA DO TRILHO SAI DE `PRIORIDADE_MAXIMA`, e não de 100. O mockup
    # desenha `width:90%` para a prioridade 90, o que só fecha se o teto fosse
    # 100 — e o teto do produto é 200 (`profiles/schema.py:970`, com portão
    # próprio: `test_teto_da_prioridade_tem_uma_fonte_so.py`). Pintar 90% seria
    # a tela dizendo "quase no máximo" sobre um perfil que está na metade.
    if PRIORIDADE_MAXIMA <= 0:  # pragma: no cover — defesa contra teto zerado
        pct = 0.0
    else:
        pct = max(0.0, min(100.0, prioridade * 100.0 / PRIORIDADE_MAXIMA))
    return {
        "nome": str(getattr(profile, "name", "") or ""),
        "prioridade": f"{pct:.0f}%",
        "prioridade_n": str(prioridade),
        # A FRASE É DELA, aprovada em 02/09/2026 — antes disso ela estava
        # marcada PROVISÓRIO na ROTA-G. A anterior era *"Prioridade {n} de 200.
        # O maior vence a disputa quando dois perfis poderiam entrar."*, e a
        # queixa dela foi literal: *"esse texto em perfis nem faz sentido
        # mais"*. Com o trilho de volta, o número já está ao lado — a frase
        # repetia o que se vê e ainda dizia "prioridade", que é o rótulo do
        # campo. **Não é constante de módulo de propósito:** ela não depende de
        # nada do perfil, e um `f""` sem campo enganaria quem lesse esperando
        # ver o número aqui.
        "prioridade_dica": (
            "Quando dois perfis servem ao mesmo tempo, o de número maior entra."
        ),
        "ambiente": ambiente,
        "ambiente_travado": ambiente is None,
        "ambiente_recado": recado,
        "jogo": simple_extra(match) if match is not None else "",
        # O Estilo de Jogo NÃO tem campo no perfil: pintar qualquer opção seria
        # a tela afirmando um valor que ninguém guarda.
        "estilo": None,
        "estilo_travado": True,
        "estilo_recado": GESTOS_SEM_MOTOR["editor.estilo"],
    }


def _linhas_da_lista(
    perfis: list[Any], ativo: str | None, incumbente: str | None
) -> list[dict[str, Any]]:
    """Uma linha por perfil, na ordem da tela — DADO, nunca marcação.

    ``ordem_de_exibicao`` reordena só a ITERAÇÃO; ``rotulo_quando_usar`` e
    ``explicacao_da_disputa`` continuam recebendo a lista na ordem de CARGA,
    porque o terceiro termo do desempate é exatamente essa ordem. Passar a lista
    reordenada faria a tela recitar a fila numa ordem que não é a do daemon.
    """
    return [
        {
            "perfil": str(getattr(p, "name", "") or ""),
            "nome": str(getattr(p, "name", "") or ""),
            "prioridade": str(int(getattr(p, "priority", 0) or 0)),
            "quando": rotulo_quando_usar(p, perfis, incumbente),
            "ativo": bool(ativo) and str(getattr(p, "name", "")) == ativo,
            "dica": explicacao_da_disputa(p, perfis, incumbente),
        }
        for p in ordem_de_exibicao(perfis, ativo)
    ]


#: O NÚMERO POR EXTENSO, para a frase da linha nunca discordar da lista. Ela
#: dizia *"herda os quatro ajustes do perfil"* com a palavra digitada, e por um
#: dia a tela mostrou cinco glifos ao lado da palavra "quatro". Sai de
#: ``len(SECOES_POR_CONTROLE)``, como o ``QUANTAS_SECOES`` do gerador.
_EXTENSO: dict[int, str] = {
    1: "um", 2: "dois", 3: "três", 4: "quatro", 5: "cinco", 6: "seis",
}


def _quantos_ajustes_por_extenso() -> str:
    """``"cinco"`` — e o número cru quando a lista passar do que se escreve."""
    return _EXTENSO.get(len(SECOES_POR_CONTROLE), str(len(SECOES_POR_CONTROLE)))


def _secoes_do_controle(overrides: Any) -> dict[str, bool]:
    """Quais ajustes este perfil guarda SÓ deste controle.

    ``None`` no campo = sem opinião: o controle herda a seção global. Apagado é
    a resposta certa para a maioria dos controles na maioria dos perfis, e uma
    tela que acende tudo ensinaria o contrário.
    """
    return {
        secao: getattr(overrides, secao, None) is not None
        for secao in SECOES_POR_CONTROLE
    }


def _linhas_da_guarda(mesa: list[dict[str, Any]], profile: Any) -> list[dict[str, Any]]:
    """Uma linha por controle PRESENTE, com o que o perfil guarda só dele."""
    controllers = getattr(profile, "controllers", None) or {}
    linhas = []
    for controle in mesa:
        uniq = str(controle.get("uniq") or "")
        secoes = _secoes_do_controle(controllers.get(uniq))
        quantos = sum(1 for ligada in secoes.values() if ligada)
        total = len(SECOES_POR_CONTROLE)
        quanto = (
            f"{quantos} de {total} ajustes só deste controle"
            if quantos
            else f"nada só dele — herda os {_quantos_ajustes_por_extenso()} "
            f"ajustes do perfil"
        )
        linhas.append(
            {
                "uniq": uniq,
                "id": _id_visivel(uniq),
                "plastico": str(controle.get("plastico") or ""),
                "nome": str(controle.get("rotulo") or ""),
                "secoes": secoes,
                "dica": f"{controle.get('nome') or '—'} — {quanto}.",
            }
        )
    return linhas


def pacote_da_aba(
    perfis: list[Any],
    *,
    ativo: str | None = None,
    mesa: list[dict[str, Any]] | None = None,
    daemon_vivo: bool = True,
    incumbente: str | None = None,
    editado: Any = None,
) -> dict[str, Any]:
    """O pacote inteiro da aba Perfis, em UMA chamada por tique.

    :param perfis: os ``Profile`` **na ordem de carga do loader**
        (``profiles/loader.load_all_profiles:1157``). A ordem importa: é o
        terceiro termo do desempate da disputa.
    :param ativo: o nome do perfil ativo (``daemon.state_full``, campo
        ``active_profile``). ``None`` = ninguém ativo, que é estado legítimo.
    :param mesa: os controles PRESENTES, no formato que
        ``mesa_viva.mesa_do_estado`` devolve mais ``rotulo`` e ``plastico``.
        ``None`` = o daemon não respondeu.
    :param daemon_vivo: separa "mesa vazia" de "Hefesto desligado". São dois
        estados diferentes e a tela diz coisas diferentes em cada um; juntá-los
        seria a tela afirmando "nenhum controle" sem ter perguntado a ninguém.
    :param incumbente: quem já estava ativo, para o desempate da disputa.
        ``None`` cai no ``ativo``.
    :param editado: o ``Profile`` que está no editor. ``None`` = o ativo; e se
        não houver ativo, o primeiro da lista.

    **UMA chamada por TIQUE, não por valor.** Com catorze perfis e quatro
    controles, uma chamada por valor seriam centenas de travessias de fronteira
    por segundo — a conta está em
    :meth:`hefesto_dualsense4unix.gui.ponte_da_tela.PonteDaTela.dizer`.
    """
    incumbente = incumbente if incumbente is not None else ativo
    linhas = _linhas_da_lista(perfis, ativo, incumbente)

    alvo = editado
    if alvo is None:
        alvo = next((p for p in perfis if str(getattr(p, "name", "")) == ativo), None)
    if alvo is None and perfis:
        alvo = perfis[0]

    mesa_de_agora = list(mesa or [])
    guarda = _linhas_da_guarda(mesa_de_agora, alvo) if alvo is not None else []
    com_ajuste = sum(1 for linha in guarda if any(linha["secoes"].values()))

    if mesa is None and not daemon_vivo:
        guarda_vazia = GUARDA_SEM_DAEMON
    elif not mesa_de_agora:
        guarda_vazia = GUARDA_SEM_MESA
    else:
        guarda_vazia = ""

    return {
        "conta": _texto_da_conta(len(perfis)),
        "com_ajuste": _texto_do_ajuste(com_ajuste, len(mesa_de_agora)),
        "lista": linhas,
        "lista_vazia": "" if linhas else LISTA_VAZIA,
        "editor": _pacote_do_editor(alvo) if alvo is not None else None,
        "guarda": guarda,
        "guarda_vazia": guarda_vazia,
        "travados": dict(GESTOS_SEM_MOTOR),
    }
