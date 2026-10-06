"""perfis_web — o que a aba Perfis PINTA, como DADO e nunca como HTML."""
from __future__ import annotations

from typing import Any

from hefesto_dualsense4unix.core import formas_do_endereco as _formas
from hefesto_dualsense4unix.profiles.schema import (
    PRIORIDADE_MAXIMA,
    ControllerOverrides,
    MatchCriteria,
)

# continuam morando onde estão — a sprint MIGRA-PERFIS-03 diz isso com todas as
from hefesto_dualsense4unix.app.actions.profiles_actions import (  # isort:skip
    explicacao_da_disputa,
    ordem_de_exibicao,
    rotulo_quando_usar,
)
from hefesto_dualsense4unix.profiles.simple_match import (  # isort:skip
    detect_simple_preset,
    simple_extra,
)

DONOS_DOS_GESTOS: dict[str, str] = {
    "linha": "profiles_actions.on_profile_selection_changed:2984 → "
    "_ha_trabalho_no_editor:1909 → _populate_editor:3952. O portão do meio é "
    "que impede o editor de ser repintado por cima de trabalho não salvo.",
    "ativar": "profiles_actions.on_profile_activate:3202 — grava fato em disco "
    "(session.json e active_profile.txt), os dois manual-only desde o PERFIL-03.",
    "novo": "profiles_actions.on_profile_new:3025 → _aplicar_nascimento_com_jogo:3097.",
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
    "Do lado HTML quem grava é `a10_perfis.editor_prioridade`, sobre o "
    "`<input type=range>` do `interface/aba10.py` — a faixa sai de "
    "`profiles/schema.PRIORIDADE_MINIMA/MAXIMA`, nunca digitada.",
    "editor.ambiente": "profiles_actions._select_radio:3749 e "
    "_selected_simple_choice:3733, sobre profiles/simple_match.SIMPLE_MATCH_PRESETS:157.",
    "editor.jogo": "o campo livre do editor simples; o texto sai de "
    "profiles/simple_match.simple_extra:305 e volta por from_simple_choice.",
    "salvar": "footer_actions.on_save_profile:838 — O ÚNICO Salvar, por ordem "
    "dela (\"Salvar este perfil\" saiu da tela, CORRECOES.md). E ele NÃO "
    "está ligado aqui: os dois Salvar miram alvos diferentes hoje (o do rodapé "
    "grava footer_actions._perfil_que_as_abas_editam:884; o do editor gravava o "
    "alvo memorizado), e fundir sem fechar a divergência é o caminho mais curto "
    "para gravar por cima do perfil errado. Quem fecha é a ONDA-PERFIS-08.",
    # MEDIDO contra o daemon `dev` desta árvore, por `daemon.state_full`: das 49
    # `profiles_actions._aplicar_nascimento_com_jogo:3097` usa
    "detectar": "TEM DONO, e ele é a CLASSE da janela: o `state_full` publica "
    "`window_detect_last_class` e `window_detect_current_class` "
    "(daemon/state_store.py:316). O TÍTULO é que não é publicado. Quem quiser o "
    "título espera a ONDA-PERFIS-03.",
    "voltar-a-de-ontem": "O MOTOR EXISTE E NUNCA TEVE TELA: "
    "profiles/loader.restaurar_do_historico:3090 e listar_historico:2809, com "
    "HISTORICO_MAX_VERSOES = 10 (loader.py:2776). Os únicos chamadores estão na "
    "CLI (cli/cmd_profile.py). Quem lhe dá tela é a ONDA-PERFIS-05.",
    # não ganhou campo de estilo, e não vai ganhar — ele é um verbo.
    "editor.estilo": "SÓ NO HTML: `profiles/estilos_de_jogo.py` traz as "
    "receitas que ela aprovou (gatilho + vibração + luz por unidade), e "
    "`a10_perfis.editor_estilo` as aplica no perfil. A GTK não tem widget "
    "equivalente. NÃO há campo em profiles/schema.Profile nem preset em "
    "profiles/simple_match.SIMPLE_MATCH_PRESETS, e não é falta: o estilo "
    "RESOLVE os três ajustes e sai de cena — não é um valor a guardar.",
}

SEM_DONO = (
    "SEM LINHA na tabela de donos — este gesto chegou de um endereço que o "
    "gerador não escreve. Nada foi aplicado."
)

#:   publicada** — medido em 01/09 contra o `state_full`, e a substituição já
GESTOS_SEM_MOTOR: dict[str, str] = {}

#: :data:`AMBIENTE_QUE_A_TELA_NAO_MOSTRA` e de :data:`LISTA_VAZIA`.
#: estilo**, e não porque a escolha se perdeu.
ESTILO_APLICA_E_SAI = (
    "Escolher um estilo ajusta o gatilho, a vibração e a cor de cada controle "
    "de uma vez. O perfil guarda os três — não o nome do estilo —, então o "
    "campo volta ao travessão e você continua ajustando o que quiser nas abas."
)

#: produto sabe guardá-la (``simple_match.from_simple_choice("janela", …)``) e a
#: tela sabe MOSTRÁ-LA — que é a ordem certa: gravar uma forma que o seletor não
#: conhece empurraria o perfil para fora da tela.
AMBIENTE_DO_PRESET: dict[str, str] = {
    "any": "Todos",
    "steam": "Steam",
    "game": "Jogo",
    "steam_game": "Jogo da Steam",
    "janela": "Jogo (pela janela)",
}

#: régua nova varre toda chave que ``from_simple_choice`` sabe escrever e exige
#: rótulo em :data:`AMBIENTE_DO_PRESET` **ou** uma linha aqui.

MODO_SEM_OPINIAO = "none"

FORA_DO_DESENHO: dict[str, str] = {
    "browser": "o preset “Navegador” existe no produto e não no desenho dela",
    "terminal": "o preset “Terminal” existe no produto e não no desenho dela",
    "editor": "o preset “Editor” existe no produto e não no desenho dela",
}

#:
AMBIENTE_QUE_A_TELA_NAO_MOSTRA = (
    "Este perfil casa por uma regra que esta tela não sabe mostrar — o seletor "
    "fica travado para que salvar não a rebaixe."
)

#: sozinho.
LISTA_VAZIA = (
    "Nenhum perfil no disco ainda. Ajuste o que quiser nas outras abas e clique "
    "em “Salvar Perfil” no rodapé — o primeiro perfil nasce daí."
)

GUARDA_SEM_MESA = (
    "Nenhum controle ligado agora. Conecte um pelo cabo ou pelo rádio — a "
    "tabela aparece sozinha, sem recarregar esta tela."
)

GUARDA_SEM_DAEMON = (
    "Hefesto desligado — abra a aba Sistema e clique em “Ligar o Hefesto”. "
    "Enquanto ele estiver parado, esta tela não sabe quais controles estão "
    "ligados; o que o perfil guarda para cada peça continua no disco, intacto."
)

#: (merge por campo, PERFIL-01).
#: a tupla ``("leds", "triggers", "rumble", "speaker")``, digitada, com a
#: existe"*. O merge levou os dois, e o que sobrou foi a pior das combinações:
#: o daemon aplicando o mudo só daquele controle (``apply_controller_mics``), a
SECOES_POR_CONTROLE: tuple[str, ...] = tuple(ControllerOverrides.model_fields)


def _texto_da_conta(quantos: int) -> str:
    """``"14 perfis"`` — e ``"1 perfil"``, que a tela precisa saber dizer."""
    return f"{quantos} perfil" if quantos == 1 else f"{quantos} perfis"


def _texto_do_ajuste(com_ajuste: int, total: int) -> str:
    """``"3 de 4 controles com ajuste próprio"``."""
    if total <= 0:
        return "— controles com ajuste próprio"
    peca = "controle" if total == 1 else "controles"
    return f"{com_ajuste} de {total} {peca} com ajuste próprio"


def _id_visivel(uniq: str) -> str:
    """``"aabbcc000001"`` → ``"AA:BB:CC:00:00:01"``, na máscara da casa.

    A chave do dado continua sendo o ``uniq`` cru — é ela que vai no
    ``data-hef-uniq``, porque é a chave de ``Profile.controllers``
    (``profiles/schema.py:1270``, canonizada em ``:1387``). Endereço que não é a
    chave do dado obriga a inventar uma tradução, e a tradução é onde nasce a
    segunda verdade.

    O TEXTO DA COLUNA SAI MASCARADO desde 28/09/2026 (O-REGISTRO-COPIADO-NAO-
    ENTREGA-O-ENDERECO-01): até ali a coluna «ID da peça» mostrava o endereço
    inteiro, e a tela é o que se fotografa num relato. Quem mascara é o dono,
    ``core/formas_do_endereco``; o que não é um endereço passa pela máscara do
    texto e volta.
    """
    mascarado = _formas.mascarar_endereco(uniq)
    if mascarado is None:
        return _formas.mascarar(uniq or "") or "—"
    return mascarado.upper()


def _ambiente_do_perfil(profile: Any) -> tuple[str | None, str]:
    """``(rótulo do seletor, frase do estado honesto)`` — nunca os dois cheios."""
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
    if preset in FORA_DO_DESENHO:
        return FORA_DO_DESENHO[str(preset)]
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
    if PRIORIDADE_MAXIMA <= 0:  # pragma: no cover — defesa contra teto zerado
        pct = 0.0
    else:
        pct = max(0.0, min(100.0, prioridade * 100.0 / PRIORIDADE_MAXIMA))
    return {
        "nome": str(getattr(profile, "name", "") or ""),
        "prioridade": f"{pct:.0f}%",
        "prioridade_n": str(prioridade),
        # A FRASE É DO USUÁRIO, aprovada em 02/09/2026 — antes disso ela estava
        "prioridade_dica": (
            "Quando dois perfis servem ao mesmo tempo, entra o de número maior."
        ),
        "ambiente": ambiente,
        "ambiente_travado": ambiente is None,
        "ambiente_recado": recado,
        "jogo": simple_extra(match) if match is not None else "",
        "estilo": None,
        "estilo_travado": False,
        "estilo_recado": ESTILO_APLICA_E_SAI,
        # SEM SEÇÃO É "none", E ISSO NÃO É UM DEFAULT: um perfil sem `mode` NÃO
        "modo": str(getattr(getattr(profile, "mode", None), "kind", "")
                    or MODO_SEM_OPINIAO),
    }


def _linhas_da_lista(
    perfis: list[Any], ativo: str | None, incumbente: str | None
) -> list[dict[str, Any]]:
    """Uma linha por perfil, na ordem da tela — DADO, nunca marcação."""
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


SECOES_ESPERANDO_A_SESSAO_DELA: frozenset[str] = frozenset()

SECOES_NA_TELA: tuple[str, ...] = tuple(
    s for s in SECOES_POR_CONTROLE if s not in SECOES_ESPERANDO_A_SESSAO_DELA
)

_EXTENSO: dict[int, str] = {
    1: "um", 2: "dois", 3: "três", 4: "quatro", 5: "cinco", 6: "seis",
    7: "sete", 8: "oito",
}


def _quantos_ajustes_por_extenso() -> str:
    """``"cinco"`` — e o número cru quando a lista passar do que se escreve."""
    return _EXTENSO.get(len(SECOES_NA_TELA), str(len(SECOES_NA_TELA)))


def _secoes_do_controle(overrides: Any) -> dict[str, bool]:
    """Quais ajustes este perfil guarda SÓ deste controle."""
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
        quantos = sum(1 for secao in SECOES_NA_TELA if secoes.get(secao))
        total = len(SECOES_NA_TELA)
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
                "entrada": dict(controle.get("entrada") or {}),
                "mascara": str(controle.get("mascara") or ""),
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
    :meth:`hefesto_dualsense4unix.interface.janela.PonteDaTela.dizer`.
    """
    incumbente = incumbente if incumbente is not None else ativo
    linhas = _linhas_da_lista(perfis, ativo, incumbente)

    alvo = editado
    if alvo is None:
        alvo = next((p for p in perfis if str(getattr(p, "name", "")) == ativo), None)
    if alvo is None and perfis:
        alvo = perfis[0]

    mesa_de_agora = list(mesa or [])
    guarda = _linhas_da_guarda(mesa_de_agora, alvo)
    com_ajuste = sum(
        1 for linha in guarda if any(linha["secoes"].get(s) for s in SECOES_NA_TELA))

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
