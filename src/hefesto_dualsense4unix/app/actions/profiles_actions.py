"""Aba Perfis: lista + editor de matcher com persistência em disco.

Dois modos de editor:
- simples   (default): radios "Aplica a" + slider Prioridade humanamente legíveis.
- avancado  (toggle):  campos crus window_class / title_regex / process_name.

A preferência de modo persiste em ~/.config/hefesto-dualsense4unix/gui_preferences.json via
gui_prefs.load_gui_prefs / gui_prefs.set_pref.
"""
# ruff: noqa: E402
from __future__ import annotations

import contextlib
from typing import Any

import gi
from pydantic import ValidationError

gi.require_version("Gtk", "3.0")
from gi.repository import GObject, Gtk

from hefesto_dualsense4unix.app.actions.base import WidgetAccessMixin
from hefesto_dualsense4unix.app.actions.home_actions import (
    texto_do_custo_da_mascara,
)
from hefesto_dualsense4unix.app.gui_prefs import load_gui_prefs, set_pref
from hefesto_dualsense4unix.app.ipc_bridge import (
    PROFILE_SWITCH_TIMEOUT_S,
    active_profile_name,
    call_async,
    profile_switch,
    run_in_thread,
)
from hefesto_dualsense4unix.app.widgets import SegmentedSelector
from hefesto_dualsense4unix.profiles import schema as _schema
from hefesto_dualsense4unix.profiles.loader import (
    delete_profile,
    load_all_profiles,
    save_profile,
)
from hefesto_dualsense4unix.profiles.schema import (
    Match,
    MatchAny,
    MatchCriteria,
    MatchManual,
    Profile,
    ProfileModeConfig,
    normalizar_gamepad_flavor,
)
from hefesto_dualsense4unix.profiles.simple_match import (
    MENSAGENS_DE_GENTE,
    detect_simple_preset,
    from_simple_choice,
    simple_extra,
)
from hefesto_dualsense4unix.profiles.slug import find_by_slug, mesmo_slug
from hefesto_dualsense4unix.utils.logging_config import get_logger

logger = get_logger(__name__)

# Mapeamento radio-id -> chave de preset
# R-12 (auditoria 23/07): "steam_game" entrou porque o editor simples não tinha
# como expressar "este perfil é DESTE jogo da Steam" — e é a única regra que o
# autoswitch reconhece como regra de jogo (R-01, `perfil_e_regra_de_jogo` exige
# `window_class` com a `steam_app_<id>` em foco) e a única chave do `.env` por
# appid do launch_env.
_RADIO_IDS = ("any", "steam", "browser", "terminal", "editor", "game", "steam_game")

#: R-12: ids do seletor que exigem o campo livre preenchido.
_IDS_COM_CAMPO_LIVRE = ("game", "steam_game")

#: Teto da escala de prioridade, com dono em `profiles/schema.py` — é lá que se
#: muda, e é lá que está a história do número (PERFIL-NASCE-CERTO-01, entrega
#: 2, item 1: 100 -> 200). O glade tem de acompanhar na mão (`upper` do
#: `profile_priority_adj`), e há portão que reprova a divergência.
#:
#: UNIFICA-CONSTANTE-01 (05/08/2026): era um `200` escrito aqui, e este módulo
#: era a "fonte" que `profiles/sanidade.py` e o comentário do glade citavam —
#: sem nenhum portão ligando os dois primeiros. Vira reexport em vez de sumir
#: porque `pa.PRIORIDADE_MAXIMA` é o nome que os testes da aba Perfis usam.
PRIORIDADE_MAXIMA = _schema.PRIORIDADE_MAXIMA

#: PERFIL-NASCE-CERTO-01 (entrega 1): folga com que um perfil recém-nascido de
#: JOGO passa por cima do catch-all mais alto do disco. Dez pontos deixam
#: espaço para ela ajustar para os dois lados sem empatar por acidente.
_FOLGA_ACIMA_DO_CATCH_ALL = 10

#: R-12: placeholder/tooltip do campo livre por escolha — o glade tem um só
#: rótulo ("Nome do jogo:") para dois significados MUITO diferentes. Sem isto,
#: "Jogo específico" continuaria pedindo em silêncio o basename do executável,
#: que em jogo Proton é o binário do wine e nunca é o nome do jogo.
_CAMPO_LIVRE_DICAS: dict[str, tuple[str, str]] = {
    "game": (
        "ex.: eldenring",
        "Nome do programa Linux do jogo (o basename de /proc/PID/exe). "
        "Em jogo da Steam/Proton isso costuma ser o binário do wine — nesse "
        "caso use \"Jogo da Steam\".",
    ),
    "steam_game": (
        "ex.: 1599660",
        "Número do jogo na Steam (o da URL da loja). Com o jogo aberto, o "
        "campo é preenchido sozinho.",
    ),
}

# FEAT-DSX-COMBO-TO-SEGMENTED-01: itens do seletor "Aplica a:" (id, rótulo curto).
# Antes vinham do `<items>` do GtkComboBoxText no Glade; agora alimentam o
# SegmentedSelector no código. Rótulos curtos para caber na aba; o contexto
# completo fica no tooltip do seletor.
_APLICA_A_ITEMS: list[tuple[str, str]] = [
    ("any", "Qualquer"),
    ("steam", "Steam"),
    ("browser", "Navegador"),
    ("terminal", "Terminal"),
    ("editor", "Editor"),
    ("game", "Jogo"),
    ("steam_game", "Jogo da Steam"),
]

# FEAT-PROFILE-MODE-GUI-01: itens da seção "Modo" do editor (id, rótulo curto).
# "none" = perfil SEM a seção `mode` (ativar não mexe no modo do sistema);
# os demais ids espelham ProfileModeConfig.kind.
# UX-MODE-TERMS-01: mesmos rótulos da aba Início (ação da usuária, sem jargão).
# UX-MODE-TERMS-02 (06/08/2026): "Jogar direto (Sony)" virou "Conexão Nativa
# (Sony)" por decisão dela — a nota completa está na frase-dona, em
# `home_actions._MODE_ITEMS`. O id `native` NÃO muda: é chave de perfil.
_MODE_KIND_ITEMS: list[tuple[str, str]] = [
    # LEIGO-06: "Sem opinião" é o programa se descrevendo por dentro (o perfil
    # sem a seção `mode`). O rótulo diz o que ATIVAR o perfil faz — ou melhor,
    # o que ele NÃO faz.
    ("none", "Não mexer no modo"),
    ("desktop", "Controlar o PC"),
    ("gamepad", "Jogar pelo Hefesto"),
    ("native", "Conexão Nativa (Sony)"),
]

# Máscara do gamepad virtual (só faz sentido com kind == "gamepad").
_MODE_FLAVOR_ITEMS: list[tuple[str, str]] = [
    ("dualsense", "DualSense (botões PlayStation)"),
    ("xbox", "Xbox 360"),
]

# LEIGO-06: a coluna "Quando usar" mostrava o valor CRU do schema ("any",
# "criteria") — o nome do campo, não uma resposta. `MatchAny` é o fallback que
# vale sempre; `MatchCriteria` casa por janela/processo.
#: R-12 item 5: o que a coluna diz de um `criteria` SEM nenhum campo.
LABEL_SO_MANUAL = "Só manual (nunca ativa sozinho)"

_MATCH_LABELS: dict[str, str] = {
    "any": "Sempre",
    "criteria": "Só neste programa",
    # R-12 item 3: o sentinel `MatchManual` diz a MESMA coisa que o criteria
    # vazio, só que de propósito — logo, a mesma frase. A coluna não é o lugar
    # de ensinar a diferença entre intenção e acidente (isso é o doctor).
    "manual": LABEL_SO_MANUAL,
}


def _match_label(match: object) -> str:
    """Rótulo da coluna "Quando usar" (função pura — testável sem GTK).

    Aceita o OBJETO ``profile.match`` (contrato novo, R-12) ou o discriminador
    cru em string (contrato antigo — mantido porque é o que os testes de
    vocabulário e qualquer chamador de fora usam, e porque um perfil gravado
    por uma versão mais nova continua caindo no próprio valor em vez de deixar
    a célula vazia).

    R-12 (auditoria 23/07): ``MatchCriteria`` com TODOS os campos vazios é o
    caso do preset ``coop_local`` de fábrica — ``MatchCriteria.matches``
    devolve ``False`` sem condição alguma (schema.py:52), então o perfil é
    INALCANÇÁVEL pelo autoswitch. A coluna dizia "Só neste programa", o que é
    falso duas vezes: não há programa nenhum, e ele nunca entra sozinho.
    """
    tipo = getattr(match, "type", None)
    if tipo == "criteria" and not (
        getattr(match, "window_class", None)
        or getattr(match, "window_title_regex", None)
        or getattr(match, "process_name", None)
    ):
        return LABEL_SO_MANUAL
    if tipo is not None:
        return _MATCH_LABELS.get(str(tipo), str(tipo))
    return _MATCH_LABELS.get(str(match), str(match))


# --- EMPATE-01 (E2): a coluna "Quando usar" diz que HÁ disputa e quem ganha --
# `_match_label` traduz `MatchAny` para "Sempre" e a coluna termina aí. Medido
# no disco dela em 31/07/2026 — QUATRO perfis dizem "Sempre" ao mesmo tempo:
#
#   fallback     prioridade 0     meu_perfil   prioridade 1
#   vitoria      prioridade 0     Pragmata     prioridade 5
#
# (eram cinco até esta madrugada; o `pragmata2.json` virou regra do jogo —
# `window_class: steam_app_3357650`, prioridade 85 — e saiu da disputa.)
#
# Quatro linhas idênticas na coluna, um vencedor, e nenhuma palavra sobre o
# porquê. É o mecanismo direto da queixa mais antiga desta casa, *"a config que
# eu deixo nunca é respeitada"*: ela troca a cor no `vitoria`, o `Pragmata`
# ganha, e a tela não deu um sinal.
#
# O desempate REAL vive em `profiles/manager.py` e é o que estas funções
# espelham — nunca reimplementam com critério próprio:
#
#   `_chave_de_selecao` (:632-640)  (not e_catch_all, priority), maior vence;
#   `_melhor_candidato` (:668-706)  empate → INCUMBENTE; sem incumbente entre
#                                   os empatados, o primeiro da ordem de carga
#                                   (`sorted(glob("*.json"))` do loader:568 —
#                                   a ordem alfabética do ARQUIVO, que não é
#                                   critério de ninguém);
#   o veto R-21          (:620-630) em janela de JOGO, se todos os candidatos
#                                   forem catch-all, NÃO se troca de perfil.
#
# Daí a frase do tooltip sobre jogo ser verdade nos dois ramos: ou todos os
# candidatos são "Sempre" e o veto recusa, ou existe um perfil com regra
# própria — e aí ele vence qualquer "Sempre" pelo primeiro termo da chave.

#: Quem entra na disputa: só o `MatchAny`. Um `MatchCriteria` vazio também é
#: `e_catch_all` para o manager, mas `MatchCriteria.matches` devolve False sem
#: condição alguma — ele nunca vira candidato, e a coluna já o chama de
#: `LABEL_SO_MANUAL`. Somá-lo aqui inflaria o número da disputa com um perfil
#: que não disputa nada.
def perfis_em_disputa(perfis: list[Any]) -> list[Any]:
    """Os perfis que dizem "Sempre" — os que casam com QUALQUER janela."""
    return [p for p in perfis if getattr(getattr(p, "match", None), "type", None) == "any"]


def vencedor_da_disputa(
    disputantes: list[Any], incumbente: str | None = None
) -> Any | None:
    """Qual "Sempre" ganha — mesma ordem de desempate do `ProfileManager`.

    Recebe a lista JÁ na ordem de carga do loader, porque o terceiro termo do
    desempate é exatamente essa ordem. Devolve ``None`` para lista vazia.
    """
    if not disputantes:
        return None
    maior = max(int(getattr(p, "priority", 0)) for p in disputantes)
    empatados = [p for p in disputantes if int(getattr(p, "priority", 0)) == maior]
    if len(empatados) == 1 or not incumbente:
        return empatados[0]
    for candidato in empatados:
        if mesmo_slug(incumbente, str(getattr(candidato, "name", ""))):
            return candidato
    return empatados[0]


def rotulo_quando_usar(
    profile: Any, perfis: list[Any], incumbente: str | None = None
) -> str:
    """Texto da coluna "Quando usar" — função pura, testável sem GTK.

    Só o "Sempre" muda, e só quando há mais de um: com um catch-all no disco
    não existe disputa, e a coluna continua dizendo a palavra de sempre (que
    também é o caso do usuário recém-instalado, com o `fallback` sozinho).
    """
    base = _match_label(getattr(profile, "match", None))
    if base != _MATCH_LABELS["any"]:
        return base
    disputantes = perfis_em_disputa(perfis)
    if len(disputantes) < 2:
        return base
    vencedor = vencedor_da_disputa(disputantes, incumbente)
    quantos = len(disputantes)
    nome = str(getattr(vencedor, "name", ""))
    if nome == str(getattr(profile, "name", "")):
        return f"Sempre — {quantos} disputam, este vence"
    return f"Sempre — {quantos} disputam, vence {nome}"


def explicacao_da_disputa(
    profile: Any, perfis: list[Any], incumbente: str | None = None
) -> str:
    """Tooltip da linha: a disputa inteira, com a ordem do desempate.

    A coluna cabe em uma linha (o `hscrollbar-policy` da lista é ``never``:
    texto largo empurra a aba inteira, lição da LARGURA-01), então o preço
    completo vive aqui.
    """
    disputantes = perfis_em_disputa(perfis)
    if getattr(getattr(profile, "match", None), "type", None) != "any":
        return ""
    if len(disputantes) < 2:
        return (
            "Este perfil vale para qualquer janela — é o que entra quando "
            "nenhuma regra específica casa."
        )
    vencedor = vencedor_da_disputa(disputantes, incumbente)
    nomes = ", ".join(str(getattr(p, "name", "")) for p in disputantes)
    nome_vencedor = str(getattr(vencedor, "name", ""))
    prioridade = int(getattr(vencedor, "priority", 0))
    return (
        f"{len(disputantes)} perfis dizem “Sempre” e disputam toda janela em "
        f"que nenhuma regra específica casa: {nomes}.\n\n"
        f"Hoje quem vence é “{nome_vencedor}” (prioridade {prioridade}). O "
        "desempate, nesta ordem: um perfil com regra própria ganha de qualquer "
        "“Sempre”; depois vence a maior prioridade; e em empate de prioridade "
        "continua valendo o que já estava ativo.\n\n"
        "Dentro de um jogo nenhum destes entra sozinho: com o jogo em foco o "
        "Hefesto só troca de perfil por uma regra do próprio jogo."
    )


# --- SALVAR-NAO-REBAIXA-02: a prioridade também cai calada ------------------
# O aviso de rebaixamento desta casa (`confirm_downgrade_match_to_any`) só
# dispara quando o match ORIGINAL é específico. Os perfis dela JÁ ESTÃO em
# `MatchAny` — foram rebaixados pelo defeito de 27/07 — e para esses a janela
# não tinha uma palavra a dizer: o que ainda podia sumir calado era a
# PRIORIDADE, que é exatamente o termo que decide qual dos "Sempre" vence
# (ver `explicacao_da_disputa`). Medido em 05/08: salvar por cima levava
# `prio=200, criteria` para `prio=0, any`.

#: Queda de prioridade a partir da qual a janela PERGUNTA. Dez pontos é a mesma
#: folga com que um perfil de jogo nasce acima do catch-all
#: (`_FOLGA_ACIMA_DO_CATCH_ALL`): abaixo disso a queda não muda quem vence
#: nenhuma disputa desta casa, e um diálogo por ponto perdido viraria o ruído
#: que se aprende a clicar sem ler — o que mataria também o aviso que importa.
QUEDA_DE_PRIORIDADE_QUE_PEDE_AVISO = 10


def queda_de_prioridade_pede_aviso(antes: int, depois: int) -> bool:
    """Esta queda de prioridade precisa de confirmação? (função pura)."""
    return int(depois) < int(antes) and (
        int(antes) - int(depois)
    ) >= QUEDA_DE_PRIORIDADE_QUE_PEDE_AVISO


# --- ATIVAR-NAO-MENTE-01: a janela passa a LER o relatório do daemon --------
# `profile.switch` responde a verdade desde a R-03 (`secoes`, `mode_aplicado`,
# `motivo`) e a janela descartava o resultado inteiro (`lambda _result:`) —
# os únicos leitores no repositório eram testes. O toast dizia "Perfil ativado"
# mesmo quando o lock de gesto manual fizera os appliers descartarem a seção
# que ela SENTE, que é o mecanismo direto da queixa "às vezes pega".
#
# `mode_aplicado` e `motivo` NÃO são lidos aqui de propósito: os dois derivam
# de `secoes["mode"]` (daemon/ipc_handlers.py:470-477), e ler a fonte em vez
# dos derivados é o que impede as duas leituras de divergirem.

#: Nomes das seções que só o `profile.switch` relata. O mapa do rodapé
#: (`footer_actions._NOMES_DE_SECAO`) nasceu para o `profile.apply_draft`, que
#: não tem `mode`/`suppression`/`rumble_policy`/`speaker`. Este dicionário
#: COMPLEMENTA aquele, nunca o substitui: as seções comuns continuam saindo de
#: lá, dona única da frase (a lição do `texto_do_custo_da_mascara`).
_NOMES_DAS_SECOES_DA_ATIVACAO: dict[str, str] = {
    "mode": "modo",
    "suppression": "modo jogo",
    "rumble_policy": "vibração",
    "speaker": "alto-falante",
}


def relato_da_ativacao(result: Any) -> dict[str, Any] | None:
    """O relatório do ``profile.switch`` no vocabulário que o rodapé já fala.

    O daemon responde ``{"secoes": {seção: estado}}`` com o vocabulário do
    `lifecycle` (``"aplicado"``, ``"adiado_lock_manual"``, ``"ignorado_*"``,
    ``"falhou"``); o rodapé fala ``applied``/``failed`` (APLICAR-VERDADE-01/02).
    São a MESMA informação em dois formatos, então esta função TRADUZ e deixa a
    frase com quem já a tem.

    Devolve ``None`` quando não há relatório (daemon antigo, ou o ``True`` cru
    da ponte): sem informação não há do que desconfiar — a mesma regra do irmão.
    """
    if not isinstance(result, dict):
        return None
    secoes = result.get("secoes")
    if not isinstance(secoes, dict) or not secoes:
        return None
    aplicadas = [str(s) for s, estado in secoes.items() if str(estado) == "aplicado"]
    nao_entraram = {
        _NOMES_DAS_SECOES_DA_ATIVACAO.get(str(s), str(s)): str(estado)
        for s, estado in secoes.items()
        if str(estado) != "aplicado"
    }
    return {"applied": aplicadas, "failed": nao_entraram}


def mensagem_de_ativacao(name: str, result: Any = None) -> str:
    """O que o rodapé diz depois de um ``profile.switch`` ACEITO.

    Tudo aplicado (ou daemon sem relatório) mantém a frase de sempre. Com seção
    de fora, o texto do que NÃO entrou é o do rodapé — reusado, não reescrito:
    dois donos da mesma frase derivam, e esta casa tem a regra escrita.
    """
    relato = relato_da_ativacao(result)
    if relato is None or not relato["failed"]:
        return f"Perfil ativado: {name}"
    # Import adiado: o módulo do rodapé sobe `gui_dialogs`, e a aba Perfis é
    # importada por testes que montam `gi` falso antes de qualquer diálogo.
    from hefesto_dualsense4unix.app.actions.footer_actions import (
        _mensagem_de_aplicacao,
    )

    return f"Perfil ativado: {name} — {_mensagem_de_aplicacao(relato)}"


def texto_da_marca_do_steam_input(
    status: str, appid: object = None, controles: int | None = None
) -> str:
    """Toast da caixinha do Steam Input — pura, testável sem GTK.

    O texto obedece ao que ELA mediu em 06/08/2026
    (`CONTROLE-SONY-MEDIDO-01`, seção *A INVERSÃO*), e não à frase antiga da
    casa: com o jogo marcado, o Hefesto entrega a **entrada** (solta o grab e
    derruba o gamepad virtual, o que acaba com o controle dobrado) e **mantém a
    saída** — os gatilhos dela seguraram e a cor dela ficou, com o jogo aberto.
    Fora da lista é que os ajustes dela perdem para o jogo.

    Por isso aqui não se escreve "o Hefesto sai da frente": é meia verdade
    medida, e a metade que falta é justamente a que ela usa.

    QUEM-DA-O-JOGADOR-2-01 (08/08/2026) — o que faltava dizer.
    ----------------------------------------------------------
    O texto contava a metade da SAÍDA e calava a metade que só aparece com **dois
    controles na mesa**: a exceção recolhia os gamepads virtuais dos secundários,
    e o co-op do Hefesto saía de cena junto (`coop_derrubado_pela_excecao_steam_
    input` no journal dela, sete vezes em 08/08 quando isto foi escrito, vinte no
    fim do dia). Isso mudava **quem entrega o jogador 2**: passava a ser o Steam
    Input, não nós.

    Com um controle só, a frase antiga estava completa e nada mudava. Com dois ou
    mais, ela omitia a troca — e omissão numa caixinha que ela marca no meio da
    noite custou a ela uma sessão inteira de Sackboy.

    NOTA DATADA — 09/08/2026 (ESCONDER-EM-VEZ-DE-SAIR-01, decisão dela)
    ------------------------------------------------------------------
    **O aviso acima saiu porque o defeito que ele avisava foi curado, não porque
    incomodava.** A marca mudou de lado: em vez de recolher os controles
    virtuais, ela esconde o controle FÍSICO. Os virtuais ficam de pé, um por
    controle, e o jogador 2 continua sendo do Hefesto — que é justamente o que o
    aviso dizia que se perdia. Manter a frase agora seria a doença de sempre pelo
    avesso: a tela avisando de um preço que o produto parou de cobrar.

    O que este texto continua NÃO prometendo, e pelo mesmo motivo de antes: que o
    jogo vai LISTAR dois jogadores. Isso depende do jogo, ninguém mediu nesta
    máquina, e a prova é dela — abrir o jogo marcado com dois controles e contar.

    O que ele PASSOU a dizer, e não é enfeite: **"feche e abra o jogo"**, em toda
    marcação. Metade da marca é a env que o jogo lê UMA vez, na abertura
    (`assets/hefesto-launch.sh`, `exec env "$@"`); marcar com o jogo aberto muda
    o daemon e não muda o que aquele processo já enumerou. Foi assim que nasceu o
    "Jogador 3" fantasma de 08/08.
    """
    if status == "appid_invalido":
        return "Esse não é um número de jogo da Steam — nada foi mudado."
    if status == "erro":
        return "Não consegui gravar a marca deste jogo — nada foi mudado."
    if status == "ja_estava":
        return f"O jogo {appid} já estava marcado."
    if status == "nao_estava":
        return f"O jogo {appid} não estava marcado."
    if status == "removido":
        return (
            f"Tirei a marca do jogo {appid}: ele volta a enxergar também o "
            "controle físico. Feche e abra o jogo para valer."
        )
    jogadores = (
        f" Os seus {controles} controles continuam sendo do Hefesto, um jogador "
        "cada — confira na tela do jogo."
        if controles is not None and controles >= 2
        else ""
    )
    return (
        f"Marquei o jogo {appid}: o controle físico fica escondido e ele passa a "
        "ver só o controle do Hefesto, sem o controle dobrado — a sua cor, os "
        f"seus gatilhos e a sua vibração continuam valendo.{jogadores} Feche e "
        "abra o jogo para valer."
    )


#: R-10: respostas do diálogo de rename (ids positivos não colidem com os
#: `Gtk.ResponseType` nativos, que são negativos — mesmo padrão do
#: `launch_wrapper_dialog`).
_RESP_RENOMEAR = 201
_RESP_COPIA = 202


def _motivo_do_cancelamento() -> str:
    """A frase da barra depois de um diálogo que devolveu "não".

    DIÁLOGO-QUE-MATA-A-JANELA-01 (06/08/2026): quando o envelope da casa
    desiste de um diálogo que não conseguiu aparecer, ele responde CANCELAR
    por ela — e um "Operação cancelada." seco a mandaria procurar um clique
    que ela nunca deu. Aqui a barra diz o que de fato aconteceu.
    """
    from hefesto_dualsense4unix.app import gui_dialogs

    if gui_dialogs.ultimo_socorro() is not None:
        return (
            "O aviso não conseguiu aparecer na tela — nada foi alterado. "
            "Tente salvar de novo."
        )
    return "Operação cancelada."


def dialogo_renomear_ou_copiar(
    parent: Any, antigo: str, novo: str
) -> str | None:
    """"Renomear" ou "Salvar como cópia" — devolve "renomear"/"copia"/None.

    R-10 (auditoria 23/07): trocar o nome no campo Nome e clicar Salvar
    gravava `<slug(novo)>.json` e DEIXAVA `<slug(antigo)>.json` no disco. Os
    dois nascem com o mesmo `match` e a mesma prioridade, então passam a
    disputar as mesmas janelas e o perfil "que ela renomeou" continua
    ativando sozinho. Nenhuma das duas leituras possíveis ("quis renomear" ou
    "quis criar uma variante") pode ser adivinhada — logo, pergunta.

    Mora aqui, e não em `app.gui_dialogs`, para esta correção não colidir com
    o outro trabalho em curso naquele módulo; a assinatura segue o padrão de
    lá (parent + strings, sem IPC).

    DIÁLOGO-QUE-MATA-A-JANELA-01 (06/08/2026): morar fora do módulo dos
    diálogos não o dispensa do envelope da casa — este era um dos DEZ
    `dialog.run()` capazes de deixar a janela dela morta, e agora passa por
    `gui_dialogs.executar_dialogo` como os outros nove.
    """
    from hefesto_dualsense4unix.app import gui_dialogs

    dialog = Gtk.MessageDialog(
        parent=parent,
        modal=True,
        destroy_with_parent=True,
        message_type=Gtk.MessageType.QUESTION,
        buttons=Gtk.ButtonsType.NONE,
        text=f"Renomear '{antigo}' para '{novo}'?",
    )
    with contextlib.suppress(Exception):
        dialog.get_style_context().add_class("hefesto-dualsense4unix-window")
    dialog.format_secondary_text(
        f"'Renomear' apaga o perfil '{antigo}'. 'Salvar como cópia' mantém "
        f"os dois — e os dois vão disputar as mesmas janelas."
    )
    dialog.add_button("Cancelar", Gtk.ResponseType.CANCEL)
    dialog.add_button("Salvar como cópia", _RESP_COPIA)
    dialog.add_button("Renomear", _RESP_RENOMEAR)
    dialog.set_default_response(_RESP_RENOMEAR)

    response = gui_dialogs.executar_dialogo(dialog, nome="renomear_ou_copiar")
    dialog.destroy()
    if response == _RESP_RENOMEAR:
        return "renomear"
    if response == _RESP_COPIA:
        return "copia"
    return None


class ProfilesActionsMixin(WidgetAccessMixin):
    """Controla a aba Perfis."""

    _profiles_store: Gtk.ListStore
    _mode_advanced: bool = False  # True = editor avançado ativo; default seguro sem GTK
    # PERF-GUI-PROFILE-LOAD-NONBLOCKING-01: cache em memória dos perfis. Evita
    # load_all_profiles() síncrono na thread GTK a cada clique/tecla. Populado
    # por _reload_profiles_store (thread worker); lido por
    # on_profile_selection_changed e _build_profile_from_editor.
    _profiles_cache: list[Profile]
    # BUG-ADVANCED-TOGGLE-CLOBBER-01: guard para set_active() programático em
    # _populate_editor não disparar on_profile_advanced_toggle (que persistiria
    # 'advanced_editor' indevidamente). Substitui o handler_block dummy que vazava.
    _suppress_advanced_toggle: bool = False
    # BUG-DUPLICATE-NO-CONFIG-COPY-01: perfil-fonte de uma duplicação em curso;
    # usado como base em _build_profile_from_editor para copiar triggers/LEDs/etc.
    _duplicate_source: Profile | None = None
    # FEAT-DSX-COMBO-TO-SEGMENTED-01: seletor "Aplica a:" em botões segmentados
    # (substitui o GtkComboBoxText `profile_aplica_a_combo`, fechado no clique
    # pelo cosmic-comp). Mesma API por-ID do combo.
    _aplica_a: Any
    # FEAT-PROFILE-MODE-GUI-01: widgets da seção "Modo" do editor, montados no
    # código dentro do slot do glade (padrão home_actions). `None` quando o
    # glade não tem o slot (fallback: o mode do perfil sobrevive por herança).
    _mode_kind_selector: Any = None
    _mode_flavor_selector: Any = None
    _mode_gamepad_opts: Any = None
    # SALVAR-NAO-REBAIXA-01: fotografia do perfil que o editor está mostrando —
    # o valor do DISCO e o que a tela conseguiu representar dele. `None` = o
    # editor não mostra perfil nenhum do disco (perfil novo, dublê de teste),
    # e aí o que está nos widgets é a fonte, como sempre foi.
    _regra_do_disco: Match | None = None
    _assinatura_da_regra_ao_abrir: tuple[object, ...] | None = None
    _prioridade_do_disco: int | None = None
    _prioridade_ao_abrir: int | None = None
    # Gesto DELA sobre o seletor "Aplica a" desde a abertura do perfil. Existe
    # porque comparar valores não basta: num perfil de match complexo a página
    # simples já abre em "Qualquer", e escolher "Qualquer" precisa contar.
    _regra_tocada: bool = False
    # Mesmo motivo, na escala de prioridade. A escala tem teto, então um perfil
    # com prioridade acima dele (escrita à mão no JSON) abre CLAMPADO: 250 no
    # disco aparece como 200 na tela. Sem esta marca, arrastar a escala até 200
    # de propósito seria indistinguível de não ter tocado, e o salvamento
    # devolveria 250 ao disco — a guarda viraria o mesmo cadeado que ela existe
    # para impedir, só que no outro sentido.
    _prioridade_tocada: bool = False
    # PERFIL-SALVA-TUDO-01: gesto DELA sobre o seletor de Modo desde que o editor
    # abriu este perfil. Mesma razão do `_regra_tocada`, agora com um segundo
    # escritor em cena: o modo passou a ter dono no RASCUNHO (a aba Emulação
    # escreve por `DraftConfig.with_mode`), e sem esta marca salvar pela aba
    # Perfis reescreveria o modo com a leitura da tela — que abre com o valor do
    # DISCO. Seria o SALVAR-NAO-REBAIXA-01 de novo, na seção `mode`: ela liga o
    # modo jogo na aba Emulação, salva pela aba Perfis e o modo evapora.
    _modo_tocado: bool = False
    # NUNCA-TROCA-O-ALVO-01 (06/08/2026): a seleção da lista está sendo movida
    # pelo CÓDIGO, e não pelo dedo dela. Mesmo padrão (e mesma razão) do
    # `_suppress_advanced_toggle`: o sinal `changed` do GtkTreeSelection não
    # sabe distinguir quem o emitiu, e o handler repopulava o editor nos dois
    # casos. Ver `_ha_trabalho_no_editor` para a história inteira.
    _selecao_programatica: bool = False
    # NUNCA-TROCA-O-ALVO-01: o perfil do DISCO que o editor está editando — o
    # ALVO do botão "Salvar este perfil". Escrito só por `_populate_editor`
    # (que só roda por gesto dela ou com o editor limpo) e pelo próprio Salvar.
    # `None` = o editor não mira arquivo nenhum (perfil novo, cópia, dublê de
    # teste), e aí quem responde volta a ser a linha selecionada.
    _alvo_do_salvar: str | None = None

    def install_profiles_tab(self) -> None:
        """Inicializa a aba Perfis: lista, colunas, handlers e estado inicial do toggle."""
        tree: Gtk.TreeView = self._get("profiles_tree")
        # UX-PROFILES-ACTIVE-HIGHLIGHT-01: 4ª coluna (peso da fonte) marca o
        # perfil ATIVO em negrito — a lista não dizia qual estava valendo.
        # EMPATE-01/E2: a 5ª coluna é o TOOLTIP da linha (nunca desenhada) —
        # a explicação da disputa não cabe na célula sem empurrar a aba.
        store = Gtk.ListStore(
            GObject.TYPE_STRING,
            GObject.TYPE_INT,
            GObject.TYPE_STRING,
            GObject.TYPE_INT,
            GObject.TYPE_STRING,
        )
        tree.set_model(store)
        self._profiles_store = store

        # LEIGO-06: "Prio" e "Match" eram abreviação de dev + o nome do campo
        # do schema. O conteúdo da 3ª coluna responde "quando este perfil
        # entra?", então é esse o título.
        for idx, title in ((0, "Nome"), (1, "Prioridade"), (2, "Quando usar")):
            renderer = Gtk.CellRendererText()
            column = Gtk.TreeViewColumn(title, renderer, text=idx, weight=3)
            if idx == 2:
                # EMPATE-01/E2: esta coluna passou a carregar a disputa e é a
                # única que cresce com o NOME de outro perfil. O scroller da
                # lista tem `hscrollbar-policy=never` (glade:1562), então
                # largura demais aqui empurra a aba inteira — LARGURA-01. O
                # teto + reticências seguram isso; o texto completo está no
                # tooltip da linha, que nunca é cortado.
                # O `Pango` entra AQUI, e não no topo do módulo: os testes que
                # plantam `gi` falso fornecem `Gtk` e `GObject` e mais nada, e um
                # import de topo derruba a COLETA inteira desses módulos no
                # runner sem PyGObject — cinco deles, medido no CI de 31/07.
                with contextlib.suppress(Exception):
                    from gi.repository import Pango

                    renderer.set_property("ellipsize", Pango.EllipsizeMode.END)
                    column.set_resizable(True)
                    column.set_max_width(320)
            tree.append_column(column)
        with contextlib.suppress(Exception):
            tree.set_tooltip_column(4)

        tree.get_selection().connect(
            "changed", self.on_profile_selection_changed
        )

        # UI-PROFILES-RADIO-GROUP-REDESIGN-01 + FEAT-DSX-COMBO-TO-SEGMENTED-01:
        # 6 radios viraram combo e agora viram botões segmentados (sem popup;
        # imune ao bug do cosmic-comp). Mesma API por-ID; "changed" é emitido por
        # set_active_id, então os handlers rodam igual ao combo antigo.
        sel = SegmentedSelector(wrap=True)
        sel.set_items(_APLICA_A_ITEMS)
        sel.set_tooltip_text("Contexto em que este perfil será aplicado")
        slot = self._get("profile_aplica_a_slot")
        if slot is not None:
            # BUG-APLICA-A-CLIP-01: sem expand/fill o SegmentedSelector colapsa
            # à largura mínima (o ScrolledWindow interno reporta mínimo ~0) e
            # os botões saem CORTADOS — mesma família do BUG-HOME-MASK-CLIP-01.
            slot.pack_start(sel, True, True, 0)
            sel.show_all()
        self._aplica_a = sel
        sel.connect("changed", self._on_aplica_a_changed)
        sel.set_active_id("any")

        # A caixinha que TIRA um jogo do Steam Input (decisão dela, 07/08).
        # Ligada em código, e não por `<signal>` no glade, pelo mesmo motivo dos
        # botões da aba Sistema: o app conecta sinais por dict literal em
        # `_signal_handlers()`, e um handler declarado no glade que não esteja
        # naquele dicionário faz o `connect_signals` reclamar.
        self._suppress_steam_input_toggle = False
        check = self._get("profile_steam_input_check")
        if check is not None:
            with contextlib.suppress(Exception):
                check.connect("toggled", self.on_profile_steam_input_toggled)
        campo_do_jogo = self._get("profile_simple_custom_name")
        if campo_do_jogo is not None:
            # Trocar o número do jogo troca o jogo de que a caixinha fala; sem
            # isto ela continuaria mostrando a marca do appid ANTERIOR.
            with contextlib.suppress(Exception):
                campo_do_jogo.connect("changed", self._on_campo_do_jogo_mudou)

        # SALVAR-NAO-REBAIXA-01: o gesto dela sobre a escala de prioridade. O
        # `_populate_editor` zera a marca DEPOIS de posicionar os widgets, então
        # o `set_value` de abertura não conta como toque.
        escala_prio = self._get("profile_priority_scale")
        if escala_prio is not None:
            with contextlib.suppress(Exception):
                escala_prio.connect("value-changed", self._on_prioridade_tocada)

        # FEAT-PROFILE-MODE-GUI-01: seção "Modo" (o que o perfil liga ao ativar).
        self._install_mode_section()

        # Estado inicial do toggle a partir das preferências persistidas
        prefs = load_gui_prefs()
        self._mode_advanced = bool(prefs.get("advanced_editor", False))
        switch: Gtk.Switch = self._get("profile_advanced_switch")
        # T7: set_active programático no boot dispara on_profile_advanced_toggle,
        # que persistiria a pref no disco na thread GTK. Guard igual ao usado em
        # _populate_editor / on_profile_new.
        self._suppress_advanced_toggle = True
        try:
            switch.set_active(self._mode_advanced)
        finally:
            self._suppress_advanced_toggle = False
        self._apply_editor_mode()

        self._profiles_cache = []
        self._reload_profiles_store(on_done=self._sync_selection_with_active_profile)

    def _install_mode_section(self) -> None:
        """Monta a seção "Modo" do editor (FEAT-PROFILE-MODE-GUI-01).

        Widgets dinâmicos dentro do slot do glade (padrão home_actions):
        SegmentedSelector do kind + CheckButton de co-op + seletor de máscara,
        os dois últimos visíveis/sensíveis só com kind == "gamepad". Nunca
        GtkComboBox (o cosmic-comp fecha o popup do combo no clique).
        """
        slot = self._get("profile_mode_slot")
        if slot is None:
            # Glade desatualizado: editor segue funcional sem a seção — o mode
            # do perfil sobrevive por herança em _build_profile_from_editor.
            self._mode_kind_selector = None
            return

        kind_sel = SegmentedSelector(wrap=True)
        kind_sel.set_items(_MODE_KIND_ITEMS)
        kind_sel.set_tooltip_text(
            "O que ativar este perfil liga: controlar o PC, jogar pelo "
            "Hefesto ou a conexão nativa (Sony)"
        )
        slot.pack_start(kind_sel, False, False, 0)
        self._mode_kind_selector = kind_sel

        # Opções específicas do gamepad: co-op e máscara em LINHAS separadas —
        # na mesma HBox o seletor de máscara estourava a largura do frame e era
        # cortado na borda direita (BUG-HOME-MASK-CLIP-01, visto ao vivo também
        # aqui no editor em 2026-07-13). A linha própria dá a largura toda.
        opts = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        # LEIGO-01: aqui havia um checkbox "Co-op local (cada controle = um
        # jogador)" — o MESMO conceito da aba Início com outro nome, e o pior dos
        # dois: salvar qualquer perfil gravava `coop: false` e desligava o co-op
        # ao ativá-lo. Cada controle é um jogador sempre, então não há campo.
        mask_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        # LEIGO-06: "Máscara" é a palavra do código (SPRINT-GAME-RUMBLE-01);
        # a usuária pergunta como o jogo vai mostrar os botões.
        flavor_label = Gtk.Label(label="O jogo vê o controle como:")
        mask_row.pack_start(flavor_label, False, False, 0)
        flavor_sel = SegmentedSelector(wrap=True)
        flavor_sel.set_items(_MODE_FLAVOR_ITEMS)
        flavor_sel.set_tooltip_text(
            "Quais desenhos de botão o jogo mostra na tela"
        )
        # ESCOLHA-DELA-VENCE-01/E4, pedido dela: *"ao deixar o mouse sobre a
        # opção Xbox, ele falaria que o Xbox não tem tais features"*.
        #
        # O texto do preço JÁ EXISTIA e vivia só na aba Início — que não é
        # onde ela escolhe por jogo. Ele é REUSADO da função pura, e não
        # reescrito: dois donos da mesma frase derivam, e esta casa tem a
        # regra escrita.
        flavor_sel.set_tooltips(
            {
                sabor: texto_do_custo_da_mascara(sabor)
                for sabor, _rotulo in _MODE_FLAVOR_ITEMS
                if texto_do_custo_da_mascara(sabor)
            }
        )
        self._mode_flavor_selector = flavor_sel
        mask_row.pack_start(flavor_sel, True, True, 0)
        opts.pack_start(mask_row, False, False, 0)
        self._mode_gamepad_opts = opts
        slot.pack_start(opts, False, False, 0)

        hint = Gtk.Label(
            label=(
                "\"Não mexer no modo\" = ativar este perfil deixa o sistema "
                "exatamente como está."
            )
        )
        hint.set_xalign(0.0)
        hint.set_line_wrap(True)
        hint.get_style_context().add_class("dim-label")
        slot.pack_start(hint, False, False, 0)
        slot.show_all()

        # Contrato do sinal (BUG-HOME-SEGMENTED-SIGNATURE-01): "changed" do
        # SegmentedSelector é emitido SEM argumentos — o handler recebe só o
        # seletor e lê get_active_id().
        kind_sel.connect("changed", self._on_mode_kind_changed)
        # PERFIL-SALVA-TUDO-01: a MÁSCARA também é gesto de modo. Sem este sinal,
        # trocar só "o jogo vê o controle como" não contava como toque e o
        # `mode` do rascunho venceria a escolha que ela acabou de fazer aqui.
        flavor_sel.connect("changed", self._on_mode_flavor_changed)

        kind_sel.set_active_id("none")
        flavor_sel.set_active_id("xbox")
        self._sync_mode_options_visibility("none")
        # Os dois `set_active_id` acima são montagem, não gesto dela.
        self._modo_tocado = False

    def _sync_mode_options_visibility(self, kind: str) -> None:
        """Mostra/habilita a máscara apenas com kind == "gamepad"."""
        opts = self._mode_gamepad_opts
        if opts is None:
            return
        is_gamepad = kind == "gamepad"
        opts.set_visible(is_gamepad)
        # no_show_all: um window.show_all() posterior não deve reexibir a linha
        # escondida (mesmo padrão de profile_game_entry_box / aba Início).
        opts.set_no_show_all(not is_gamepad)
        opts.set_sensitive(is_gamepad)

    def _on_mode_kind_changed(self, selector: Any) -> None:
        """Handler do kind: sincroniza a visibilidade das opções do modo."""
        kind = selector.get_active_id() or "none"
        # PERFIL-SALVA-TUDO-01: gesto no seletor conta. O populate programático
        # (`_set_mode_editor`) também dispara este handler — ele BAIXA a marca
        # depois, então o que sobra ligado aqui é toque dela.
        self._modo_tocado = True
        self._sync_mode_options_visibility(kind)

    def _on_mode_flavor_changed(self, _selector: Any = None) -> None:
        """Handler da máscara: só marca o gesto (a visibilidade é do kind)."""
        self._modo_tocado = True

    def _set_mode_editor(self, mode: ProfileModeConfig | None) -> None:
        """Preenche a seção "Modo" a partir de ``profile.mode`` (None → "none").

        O único handler de modo que sobrou (`_on_mode_kind_changed`) apenas
        sincroniza visibilidade — é idempotente, então o populate programático
        pode dispará-lo à vontade e o guard anti-loop deixou de ser necessário.
        """
        kind_sel = self._mode_kind_selector
        if kind_sel is None:
            return
        kind = mode.kind if mode is not None else "none"
        # ESCOLHA-DELA-VENCE-01/E1 — o `or "xbox"` SAIU daqui, e ele era um
        # defeito ativo sem teste nenhum que o pegasse.
        #
        # Um perfil pode dizer `{"kind": "gamepad", "gamepad_flavor": null}`, e
        # `null` significa, no applier, "MANTÉM a máscara atual". O editor
        # convertia isso em "xbox" nas DUAS pontas: ela abria um perfil sem
        # opinião sobre máscara, salvava qualquer outra coisa nele, e o perfil
        # passava a EXIGIR Xbox — apagando giroscópio e touchpad naquele jogo.
        # Ela nunca pediu isso.
        #
        # Com `None`, o seletor fica SEM NENHUM ativo (das duas saídas da
        # sprint, a recomendada): mostrar um dos dois botões marcado seria a
        # tela afirmando uma escolha que ninguém fez.
        flavor = mode.gamepad_flavor if mode is not None else None
        kind_sel.set_active_id(kind)
        if self._mode_flavor_selector is not None:
            if flavor is None:
                self._mode_flavor_selector.limpar_ativo()
            else:
                self._mode_flavor_selector.set_active_id(flavor)
        # set_active_id só emite quando o id muda — sincroniza explicitamente
        # para a visibilidade ficar certa mesmo sem emissão.
        self._sync_mode_options_visibility(kind)
        # PERFIL-SALVA-TUDO-01: este caminho é o POPULATE (perfil aberto na
        # lista, prefill do perfil novo). Os `set_active_id` acima acabaram de
        # disparar os handlers de gesto — baixar a marca AQUI, no fim, é o que
        # separa "a tela mostrou o que estava no disco" de "ela escolheu".
        self._modo_tocado = False

    def _mode_section_from_editor(self) -> dict[str, Any] | None:
        """Monta o dict da seção ``mode`` a partir dos widgets do editor.

        "none" (sem opinião) → ``None``: a seção é REMOVIDA do perfil salvo.
        ``gamepad_flavor`` só vale com kind == "gamepad" — para os demais kinds
        gravamos ``None`` (JSON limpo, sem sobras).

        LEIGO-01: ``coop`` NÃO é emitido. O editor não pergunta mais (cada
        controle é um jogador, sempre), e omitir a chave faz o perfil HERDAR o
        default do esquema — gravar o valor de hoje congelaria a decisão no
        disco de novo, que foi exatamente o defeito que a migração teve de
        limpar.
        """
        kind_sel = self._mode_kind_selector
        kind = (kind_sel.get_active_id() if kind_sel is not None else None) or "none"
        if kind == "none":
            return None
        flavor: str | None = None
        if kind == "gamepad":
            # ESCOLHA-DELA-VENCE-01/E1: sem botão marcado, grava `None` — que
            # é "mantém a máscara atual", e é o que estava no disco. O
            # `or "xbox"` que estava aqui era a segunda ponta do mesmo defeito:
            # bastava salvar o perfil para ele passar a exigir Xbox.
            flavor_sel = self._mode_flavor_selector
            flavor = flavor_sel.get_active_id() if flavor_sel is not None else None
        return {"kind": kind, "gamepad_flavor": flavor}

    def _sync_selection_with_active_profile(self) -> None:
        """Consulta o daemon e seleciona a linha do perfil ativo (FEAT-GUI-LOAD-LAST-PROFILE-01).

        Reusa o handler IPC canônico ``daemon.status`` (que já retorna
        ``active_profile``). Chama via ``call_async`` para não bloquear a thread
        GTK. Se o daemon estiver offline, se ``active_profile`` for ``None`` ou
        se o perfil citado não existir no store atual, a chamada é no-op e a
        seleção fallback (primeiro da lista) feita por ``_reload_profiles_store``
        é preservada.
        """
        call_async(
            method="daemon.status",
            params=None,
            on_success=self._on_daemon_status_for_sync,
            on_failure=self._on_daemon_status_sync_failed,
            timeout_s=0.5,
        )

    def _on_daemon_status_for_sync(self, result: Any) -> bool:
        """Callback GTK: recebe daemon.status e seleciona perfil ativo se casar."""
        try:
            if not isinstance(result, dict):
                return False
            active = result.get("active_profile")
            if not isinstance(active, str) or not active:
                return False
            # UX-PROFILES-ACTIVE-HIGHLIGHT-01: negrito na linha do ativo.
            self._mark_active_profile_row(active)
            self._select_profile_by_name(active)
        except Exception as exc:
            logger.warning("profile_sync_callback_falhou", err=str(exc))
        return False  # GLib.idle_add: não repetir

    def _on_daemon_status_sync_failed(self, exc: Exception) -> bool:
        """Callback GTK: falha silenciosa — mantém fallback (primeiro da lista)."""
        logger.debug("profile_sync_daemon_offline", err=str(exc))
        return False

    def _select_profile_by_name(self, name: str) -> bool:
        """Seleciona a linha do store cujo nome bate com ``name``.

        Retorna True se encontrou e selecionou; False caso contrário (perfil não
        existe no store — ex.: deletado entre refresh e resposta IPC).

        NUNCA-TROCA-O-ALVO-01: com trabalho não salvo no editor, este caminho
        NÃO mexe na seleção. Ele não é chamado por gesto dela — é o daemon
        dizendo qual perfil está ativo agora —, e a lista já responde a isso do
        jeito certo: o NEGRITO de `_mark_active_profile_row`, que é chamado
        logo antes e não depende da seleção. Mover a barra azul além disso
        arrastaria junto o editor, o "Ativar", o "Duplicar" e o "Remover", que
        leem a linha selecionada. Recusar é o menor espanto possível: a lista
        continua dizendo quem está ativo, e o que ela estava editando continua
        aberto e apontado para o mesmo arquivo.
        """
        if not self._selecao_pode_se_mover_sozinha(name):
            logger.info(
                "perfis_selecao_automatica_recusada",
                pedido=name,
                editando=getattr(self, "_alvo_do_salvar", None),
            )
            return False
        store = self._profiles_store
        tree: Gtk.TreeView = self._get("profiles_tree")
        tree_iter = store.get_iter_first()
        while tree_iter is not None:
            if str(store.get_value(tree_iter, 0)) == name:
                self._mover_selecao_sem_gesto(tree_iter)
                path = store.get_path(tree_iter)
                tree.scroll_to_cell(path, None, False, 0.0, 0.0)
                return True
            tree_iter = store.iter_next(tree_iter)
        return False

    def _selecao_pode_se_mover_sozinha(self, destino: str) -> bool:
        """A seleção pode pular para ``destino`` sem que ela tenha pedido?

        Pode quando o editor está limpo — ou quando o destino JÁ é o perfil
        aberto no editor, caso em que "pular" não muda alvo nenhum.
        """
        alvo = getattr(self, "_alvo_do_salvar", None)
        if alvo and (destino == alvo or mesmo_slug(destino, alvo)):
            return True
        return not self._ha_trabalho_no_editor()

    def _mover_selecao_sem_gesto(self, linha: Any) -> None:
        """Seleciona ``linha`` marcando que quem mexeu foi o CÓDIGO.

        NUNCA-TROCA-O-ALVO-01. ``select_iter`` emite `changed` na hora, e o
        handler não tem como saber quem o emitiu — a marca é lida por
        `on_profile_selection_changed`. Mesmo `try/finally` do
        `_suppress_advanced_toggle`, pelo mesmo motivo: uma exceção no meio
        deixaria a janela inteira achando que todo clique dela é do código.

        Restaura o valor ANTERIOR em vez de baixar a marca: a repintura de
        `_populate_profiles_store` já corre marcada e chama isto por dentro —
        zerar aqui desmarcaria o resto dela pela metade.
        """
        tree: Gtk.TreeView = self._get("profiles_tree")
        anterior = self._selecao_programatica
        self._selecao_programatica = True
        try:
            tree.get_selection().select_iter(linha)
        finally:
            self._selecao_programatica = anterior

    def _ha_trabalho_no_editor(self) -> bool:
        """Há trabalho NÃO SALVO que uma repintura do editor destruiria?

        NUNCA-TROCA-O-ALVO-01 (06/08/2026). A queixa dela: *"clico em salvar e
        ele salva com um nome aleatório ou de outro perfil"*. Medido: o campo
        Nome trocava sozinho porque `_populate_editor` reescreve o editor
        inteiro e é disparado pelo sinal `changed` da SELEÇÃO — que a própria
        janela emite em três caminhos sem ela encostar na lista (o sync com o
        perfil ativo ao voltar para a aba, o "Recarregar lista" e o
        `install_profiles_tab`). O Salvar seguinte gravava no perfil que a
        janela pôs no campo, e o trabalho dela evaporava.

        Respondem "sim" aqui, nesta ordem de custo:

        - ``_new_profile`` / ``_duplicate_source``: o editor descreve um perfil
          que ainda NÃO existe em disco. Repintar é apagar o que ela digitou.
        - as marcas de gesto do SALVAR-NAO-REBAIXA-01/02 e da
          PERFIL-SALVA-TUDO-01 (regra, prioridade, modo): elas existem porque
          "ela mexeu nisto" já era uma pergunta que a aba precisava responder.
        - o campo Nome divergindo do perfil aberto: ela está renomeando.
        - ``_tem_edicao_pendente`` (R-08): as OUTRAS abas têm alteração por
          salvar. É o caminho 1 da queixa — ela mexe na cor, o jogo abre, o
          autoswitch troca o perfil ativo e a volta para a aba Perfis reescreve
          o campo Nome. O Salvar da aba Perfis emite o rascunho inteiro
          (`_edita_o_perfil_do_rascunho`), então a cor dela é trabalho que este
          botão grava — e trocar o alvo por baixo dele é perdê-la.

        Por que a resposta é esta e não uma flag de supressão sozinha: suprimir
        só o `changed` deixaria a barra azul numa linha e o editor em outra, e o
        `on_profile_save` lê AS DUAS (a linha responde "quem estou editando?" e
        o campo responde "com que nome vou gravar?"). Divergentes, elas viram um
        RENAME aos olhos do R-10 — a janela perguntaria "renomear 'sackboy' para
        'vitoria'?" por causa de um sinal que ninguém emitiu. Por isso a cura é
        em três peças que se sustentam: a lista não se move sozinha, o editor
        não é repintado por seleção que não é dela, e o Salvar mira o alvo
        MEMORIZADO (`_alvo_do_salvar`) em vez do widget.
        """
        if getattr(self, "_new_profile", False):
            return True
        if getattr(self, "_duplicate_source", None) is not None:
            return True
        if (
            getattr(self, "_regra_tocada", False)
            or getattr(self, "_prioridade_tocada", False)
            or getattr(self, "_modo_tocado", False)
        ):
            return True
        alvo = getattr(self, "_alvo_do_salvar", None)
        if alvo:
            try:
                digitado = (self._get("profile_name_entry").get_text() or "").strip()
            except Exception:
                digitado = ""
            if digitado and not mesmo_slug(digitado, alvo):
                return True
        checar = getattr(self, "_tem_edicao_pendente", None)
        if callable(checar):
            try:
                if bool(checar()):
                    return True
            except Exception as exc:
                # NUNCA-TROCA-O-ALVO-01/M2 (06/08/2026): este portão FECHA no
                # escuro. "Não sei responder" não pode virar "não há trabalho a
                # proteger" — foi medido: forçando `_tem_edicao_pendente` a
                # estourar, o defeito INTEIRO volta (o editor pula para o perfil
                # do jogo, o Salvar grava lá, e a cor dela some sem diálogo). Um
                # falso "sim" custa uma seleção que não acompanha o perfil ativo
                # até ela clicar; um falso "não" custa o trabalho dela. Não há
                # gatilho conhecido em produção (`self.draft != baseline` são
                # dois pydantic), e é por isso mesmo que a resposta é barata.
                logger.warning("perfis_edicao_pendente_indeterminada", err=str(exc))
                return True
        return False

    def _alvo_do_salvar_do_editor(self) -> str | None:
        """Qual perfil do disco o "Salvar este perfil" vai gravar por cima.

        NUNCA-TROCA-O-ALVO-01: a pergunta era feita ao WIDGET
        (`_selected_profile_name`), e por isso a resposta mudava sempre que a
        janela mexia na lista por conta própria. Passa a ser o alvo memorizado
        no gesto — o perfil que `_populate_editor` de fato abriu.

        O fallback para a linha selecionada não é preguiça: sem nenhum
        `_populate_editor` na história (dublê de teste, glade degradado, uma
        aba montada sozinha) o widget é a única fonte que existe, e era o
        comportamento de sempre.
        """
        alvo = getattr(self, "_alvo_do_salvar", None)
        if alvo:
            return str(alvo)
        try:
            return self._selected_profile_name()
        except Exception:
            return None

    # --- handlers de toggle e radio ---

    def on_profile_advanced_toggle(
        self,
        switch: Gtk.Switch,
        state: bool,
    ) -> bool:
        """Alterna entre modo simples e avançado; persiste preferência."""
        # BUG-ADVANCED-TOGGLE-CLOBBER-01: ignora chamadas programáticas (set_active
        # em _populate_editor) — só persiste quando o usuário move o switch.
        if self._suppress_advanced_toggle:
            return False
        self._mode_advanced = state
        self._apply_editor_mode()
        set_pref("advanced_editor", state)
        return False  # retorno False = deixa o GTK atualizar o estado visual

    def _on_aplica_a_changed(self, combo: Any) -> None:
        """Mostra o campo livre nas escolhas que exigem alvo ("game"/"steam_game").

        ``combo`` é o ``SegmentedSelector`` (FEAT-DSX-COMBO-TO-SEGMENTED-01);
        mantém a mesma API por-ID do GtkComboBoxText anterior.

        R-12: as duas escolhas compartilham o mesmo widget mas pedem coisas
        MUITO diferentes (basename do executável e appid da Steam) — o
        placeholder e o tooltip são trocados aqui, porque o rótulo do glade
        ("Nome do jogo:") serve para as duas e sozinho não desambigua.
        """
        active_id = combo.get_active_id() or "any"
        # SALVAR-NAO-REBAIXA-01: trocar o "Aplica a" é um gesto DELA sobre a
        # regra, e precisa contar mesmo quando o valor final coincide com a
        # fotografia. O caso: um perfil de match complexo abre no editor
        # avançado e a página simples mostra "Qualquer" sem ela ter escolhido
        # nada; sem esta marca, escolher "Qualquer" de propósito seria
        # indistinguível de não ter tocado, e a guarda viraria um cadeado.
        # `_populate_editor` zera a marca DEPOIS de posicionar os widgets, então
        # a seleção programática de abertura não conta.
        self._regra_tocada = True
        entry = self._get("profile_simple_custom_name")
        dica = _CAMPO_LIVRE_DICAS.get(active_id)
        if entry is not None and dica is not None:
            placeholder, tooltip = dica
            # Widgets fake dos testes não têm as duas APIs — a dica é cosmética
            # e não pode derrubar a troca de contexto.
            with contextlib.suppress(Exception):
                entry.set_placeholder_text(placeholder)
            with contextlib.suppress(Exception):
                entry.set_tooltip_text(tooltip)
        box: Gtk.Box = self._get("profile_game_entry_box")
        if box is None:
            return
        if active_id in _IDS_COM_CAMPO_LIVRE:
            # CAMPO-QUE-NAO-NASCE-01 (05/08/2026, relatado por ela: "quando eu
            # clico em jogo da steam não aparece nenhum campo pra digitar").
            #
            # O box do glade nasce com `no-show-all=True` — de propósito, para
            # que o `show_all()` da janela não o revele antes da hora. O efeito
            # colateral é que esse mesmo `show_all()` **não desce nos filhos**:
            # o rótulo e o `GtkEntry` nunca são mostrados. Um `box.show()` aqui
            # revela a CAIXA e mais nada, e ela vê um vão vazio no lugar do
            # campo — sem erro, sem log, sem jeito de digitar o appid.
            #
            # `show_all()` direto também não resolve: a doutrina do GTK é que
            # `no_show_all` faz o `show_all()` ignorar o widget, inclusive
            # quando chamado NELE. Por isso a ordem é desarmar e só então
            # mostrar; o `no_show_all` é redundante depois que o box passa a ser
            # gerido por este handler, que o esconde de volta no `else`.
            box.set_no_show_all(False)
            box.show_all()
        else:
            box.hide()
        # MODO-01/B1: escolher "jogo"/"jogo da Steam" num perfil NOVO já
        # pré-seleciona o modo jogo. O gate de "perfil novo" fica visível AQUI
        # (e não só dentro do helper) porque é ele que explica por que trocar o
        # "Aplica a" de um perfil salvo não mexe no modo dele.
        if active_id in _IDS_COM_CAMPO_LIVRE and getattr(self, "_new_profile", False):
            self._prefill_modo_de_jogo()
        if active_id == "steam_game":
            self._prefill_steam_appid()
        self._mostrar_caixa_do_steam_input(active_id == "steam_game")

    # --- A caixinha que TIRA um jogo do Steam Input ------------------------
    # DECISÃO DELA, 07/08/2026: "no editor do perfil, logo abaixo do jogo
    # escolhido". O que faltava era só o gatilho: `add_appid_to_steam_input_
    # allowlist` já tinha o botão da aba Sistema, e o gêmeo `remove_...` tinha
    # nove testes, uma linha de comando e ZERO chamadores na janela — pôr um
    # jogo na lista era um clique, tirar exigia editor de texto.
    #
    # A marca é do JOGO (uma linha de appid num txt nosso), não do perfil: ela
    # vale na hora e não espera o "Salvar este perfil". Por isso a caixa não
    # entra em `_build_profile_from_editor` nem no `Profile` do disco — o que
    # entraria ali seria um segundo dono do mesmo fato.

    def _mostrar_caixa_do_steam_input(self, mostrar: bool) -> None:
        """Revela (ou esconde) a caixinha, e sincroniza o estado dela.

        A ordem `set_no_show_all(False)` ANTES do `show_all()` não é ornamento:
        é a cura da CAMPO-QUE-NAO-NASCIA-01 — `no_show_all` faz o `show_all()`
        ignorar o widget INCLUSIVE quando chamado nele mesmo, e um `show()` seco
        revelaria a caixa sem descer nos filhos (ela veria um vão vazio).
        """
        box = self._get("profile_steam_input_box")
        if box is None:
            return
        if mostrar:
            self._sincronizar_caixa_do_steam_input()
            with contextlib.suppress(Exception):
                box.set_no_show_all(False)
            box.show_all()
        else:
            box.hide()

    @staticmethod
    def _appids_do_steam_input() -> set[str]:
        """AppIDs marcados hoje, lidos do arquivo dela. Erro = conjunto vazio.

        Fonte única: o mesmo módulo que escreve (`steam_launch_options`), com o
        mesmo caminho XDG que o guard em bash e o daemon leem. Uma segunda
        leitura do formato aqui viraria um segundo dono do arquivo.
        """
        try:
            from hefesto_dualsense4unix.integrations.steam_launch_options import (
                parse_steam_input_allowlist,
                steam_input_allowlist_path,
            )

            caminho = steam_input_allowlist_path()
            return set(parse_steam_input_allowlist(caminho.read_text(encoding="utf-8")))
        except Exception:
            # Arquivo ausente é allowlist vazia — é o mesmo critério do
            # `remove_appid_from_steam_input_allowlist`, que devolve
            # "nao_estava" sem criar nada.
            return set()

    def _sincronizar_caixa_do_steam_input(self) -> None:
        """Põe a caixinha no estado do DISCO, sem disparar o handler.

        O guard existe porque `set_active` emite "toggled" igual a um clique: sem
        ele, abrir um perfil de jogo já marcado reescreveria a allowlist dela.
        """
        check = self._get("profile_steam_input_check")
        if check is None:
            return
        appid = self._appid_do_editor()
        marcado = appid is not None and appid in self._appids_do_steam_input()
        self._suppress_steam_input_toggle = True
        try:
            with contextlib.suppress(Exception):
                check.set_active(marcado)
            with contextlib.suppress(Exception):
                # Sem appid não há o que marcar — e uma caixa clicável que não
                # sabe sobre qual jogo age é pior que uma caixa apagada.
                check.set_sensitive(appid is not None)
        finally:
            self._suppress_steam_input_toggle = False

    def _appid_do_editor(self) -> str | None:
        """O appid digitado no campo do jogo, ou None se não houver um válido."""
        if self._selected_simple_choice() != "steam_game":
            return None
        entry = self._get("profile_simple_custom_name")
        if entry is None:
            return None
        try:
            texto = (entry.get_text() or "").strip()
        except Exception:
            return None
        return texto if texto.isdigit() else None

    def _on_campo_do_jogo_mudou(self, _entry: object = None) -> None:
        """Digitar outro appid muda de qual jogo a caixinha está falando."""
        if self._selected_simple_choice() == "steam_game":
            self._sincronizar_caixa_do_steam_input()

    def on_profile_steam_input_toggled(self, check: Any = None) -> None:
        """Marca/desmarca ESTE jogo na allowlist do Steam Input.

        Sem diálogo, pelo mesmo motivo do botão "Este jogo não funciona": a ação
        não fecha nada, não edita arquivo da Steam, e agora tem volta — a volta
        é desmarcar a própria caixa, que é o que esta entrega existe para dar.

        Escrita síncrona de propósito: é um txt de poucas linhas no `~/.config`
        dela, e o `add`/`remove` já fazem escrita atômica (o guard pode estar
        lendo o arquivo neste instante). O que vai para segundo plano é só o
        aviso ao daemon, que é best-effort.
        """
        if getattr(self, "_suppress_steam_input_toggle", False):
            return
        if check is None:
            check = self._get("profile_steam_input_check")
        try:
            marcar = bool(check.get_active())
        except Exception:
            return
        appid = self._appid_do_editor()
        if appid is None:
            self._toast_profile(
                "Escreva o número do jogo da Steam antes de marcar."
            )
            self._sincronizar_caixa_do_steam_input()
            return
        # RELANCAR-01 (08/08/2026): marcar/desmarcar cria uma BORDA em
        # `sync_steam_input_exception`, que mexe no controle AO VIVO. Com o jogo
        # aberto essa mudança não chega ao processo dele (o wrapper faz
        # `exec env`) — foi o que a deixou sem controle nenhum no meio da
        # partida. Então: sonda primeiro, e se houver jogo aberto, PERGUNTA
        # antes de escrever no disco.
        #
        # NOTA DATADA — 09/08/2026 (ESCONDER-EM-VEZ-DE-SAIR-01): a frase antiga
        # dizia que a borda *"faz ungrab e suspende os vpads"*. Não faz mais: a
        # marca inverteu de lado e a borda agora GRABA o físico e esconde o
        # hidraw dele. A pergunta continua obrigatória, e a razão ficou mais
        # forte — com o jogo aberto, marcar tira dele exatamente o dispositivo
        # que ele já enumerou, e o vpad que o substitui só existe para o
        # processo seguinte, porque quem apaga o físico da lista do SDL é a env
        # lida uma vez na abertura.
        if self._perguntar_antes_de_relancar(
            mudanca="steam_input_do_jogo",
            valor="marcado" if marcar else "desmarcado",
            aplicar=lambda: self._gravar_marca_do_steam_input(appid, marcar),
        ):
            return
        self._gravar_marca_do_steam_input(appid, marcar)

    def _gravar_marca_do_steam_input(self, appid: str, marcar: bool) -> None:
        """Escreve a marca no disco e avisa o daemon. Separado de propósito.

        RELANCAR-01: o gesto e a ESCRITA viraram funções diferentes porque, com
        um jogo aberto, entre um e outro pode haver um diálogo e uma decisão
        dela. Enquanto era um bloco só, não havia onde perguntar.
        """
        try:
            from hefesto_dualsense4unix.integrations import (
                steam_launch_options as slo,
            )

            if marcar:
                status = slo.add_appid_to_steam_input_allowlist(
                    appid, nota="marcado no editor de perfil"
                )
            else:
                status = slo.remove_appid_from_steam_input_allowlist(appid)
        except Exception as exc:
            logger.warning("steam_input_do_perfil_falhou", err=str(exc))
            status = "erro"
        self._toast_profile(
            texto_da_marca_do_steam_input(status, appid, self._controles_na_mesa())
        )
        if status in ("adicionado", "removido"):
            self._avisar_o_daemon_da_allowlist()
        # O disco é a verdade: se a escrita não valeu, a caixa volta ao que o
        # arquivo diz em vez de mentir que valeu.
        self._sincronizar_caixa_do_steam_input()

    def _controles_na_mesa(self) -> int | None:
        """Quantos controles CONECTADOS o daemon reporta, ou None se não der.

        QUEM-DA-O-JOGADOR-2-01: é o que decide se a caixinha precisa avisar da
        troca de dono do jogador 2. Lê o mesmo campo que a aba Início já usa
        (`state["controllers"]`, filtrado por `connected`), para não haver duas
        contagens divergentes na mesma janela.

        **Devolve None em vez de zero quando não consegue ler**, e a diferença
        importa: zero significaria "não há controle, não avise", e um palpite
        errado aqui faria a caixinha CALAR justamente quando ela tem dois na
        mesa. None faz o texto voltar à forma antiga, que é verdadeira para um
        controle e apenas incompleta para dois — falha para o lado de dizer
        menos, nunca de dizer errado.

        **Por que não perguntar ao daemon aqui:** o toast é síncrono e a ponte
        IPC desta janela é assíncrona (`call_async`). Uma chamada nova ou
        bloquearia a interface, ou chegaria depois do texto já mostrado. A aba
        Início já busca esse estado a cada tique e agora guarda a contagem — ler
        dali é de graça e mantém UMA contagem só na janela inteira.
        """
        contagem = getattr(self, "_controles_conectados", None)
        return contagem if isinstance(contagem, int) else None

    def _avisar_o_daemon_da_allowlist(self) -> None:
        """Faz a marca VALER agora, sem reiniciar nada.

        A allowlist é relida do disco a cada consulta; o que NÃO é relido é a
        materialização do `steam_app_<appid>.env`. É o mesmo aviso best-effort
        que `daemon_actions._recarregar_apos_allowlist` manda depois do botão da
        aba Sistema — reusado quando a janela real tem os dois mixins, e
        substituído pelo IPC nu quando não tem (host de teste).
        """
        recarregar = getattr(self, "_recarregar_apos_allowlist", None)
        if callable(recarregar):
            with contextlib.suppress(Exception):
                recarregar()
            return
        with contextlib.suppress(Exception):
            call_async(
                method="launch_env.refresh",
                params={},
                on_success=lambda _r: False,
                on_failure=lambda _e: False,
            )

    def _prefill_modo_de_jogo(self) -> None:
        """Perfil NOVO de jogo nasce com o modo jogo pré-selecionado (MODO-01/B1).

        Era o maior dos defeitos da sprint: o fluxo simples montava o critério de
        janela certinho e deixava o modo em `"none"` — *"Não mexer no modo"*. Ela
        criava o perfil do jogo, ele entrava, e não ligava nada. O caminho que a
        interface oferece como solução não solucionava.

        Regras, deliberadamente estreitas:

        - só em perfil NOVO (`_new_profile`). Trocar o "Aplica a" de um perfil
          JÁ SALVO não pode reescrever a escolha de modo que ela fez antes;
        - só quando o modo está em `"none"`. Um `desktop`/`native` escolhido à
          mão é opinião dela, não um campo em branco;
        - a máscara é a CORRENTE do daemon (`gamepad_emulation.flavor`), lida em
          segundo plano: pré-selecionar uma máscara diferente da que está de pé
          faria o perfil recriar o vpad ao entrar — e recriar vpad com o jogo
          aberto invalida os handles que ele já abriu.

        Best-effort: sem widgets de modo (dublê de teste/glade antigo) é no-op;
        daemon offline mantém a máscara que o seletor já mostra.
        """
        if not getattr(self, "_new_profile", False):
            return
        kind_sel = getattr(self, "_mode_kind_selector", None)
        if kind_sel is None:
            return
        with contextlib.suppress(Exception):
            if (kind_sel.get_active_id() or "none") != "none":
                return
        # Preserva a máscara que o seletor já mostra até a resposta do daemon
        # chegar — `_set_mode_editor(None)` a deixaria em "xbox" e uma troca
        # visível para a máscara real logo depois pareceria bug.
        bruto: object = None
        flavor_sel = getattr(self, "_mode_flavor_selector", None)
        if flavor_sel is not None:
            with contextlib.suppress(Exception):
                bruto = flavor_sel.get_active_id()
        self._set_mode_editor(
            ProfileModeConfig(
                kind="gamepad", gamepad_flavor=normalizar_gamepad_flavor(bruto)
            )
        )

        def _on_state(result: Any) -> bool:
            try:
                if not isinstance(result, dict):
                    return False
                gamepad = result.get("gamepad_emulation")
                flavor = (gamepad or {}).get("flavor") if isinstance(gamepad, dict) else None
                if flavor not in ("dualsense", "xbox"):
                    return False
                seletor = getattr(self, "_mode_flavor_selector", None)
                kind_atual = getattr(self, "_mode_kind_selector", None)
                if seletor is None or kind_atual is None:
                    return False
                # A resposta pode chegar depois de ela mexer no editor — só
                # escreve se o modo AINDA é o gamepad que acabamos de propor.
                if (kind_atual.get_active_id() or "none") != "gamepad":
                    return False
                seletor.set_active_id(flavor)
            except Exception as exc:
                logger.debug("prefill_modo_jogo_falhou", err=str(exc))
            return False

        call_async(
            method="daemon.state_full",
            params=None,
            on_success=_on_state,
            on_failure=lambda _exc: False,
            timeout_s=0.5,
        )

    def _prefill_steam_appid(self) -> None:
        """Preenche o appid a partir do jogo em foco (R-12 item 1).

        A usuária não tem como saber o appid de cabeça, e digitá-lo errado
        produz um perfil que nunca entra — exatamente a queixa "o perfil do
        jogo nunca é respeitado". O daemon já publica a última ``wm_class``
        útil em ``window_detect_last_class``; com o jogo aberto (ou recém
        fechado) isso é ``steam_app_<id>``.

        Só preenche campo VAZIO: sobrescrever o que ela digitou seria pior que
        não ajudar. Best-effort e assíncrono — daemon offline é silêncio.
        """
        entry = self._get("profile_simple_custom_name")
        if entry is None:
            return
        try:
            if (entry.get_text() or "").strip():
                return
        except Exception:
            return

        def _on_state(result: Any) -> bool:
            try:
                if not isinstance(result, dict):
                    return False
                from hefesto_dualsense4unix.app.actions.launch_wrapper_dialog import (
                    extract_steam_appid,
                )

                appid = extract_steam_appid(result.get("window_detect_last_class"))
                if not appid:
                    return False
                alvo = self._get("profile_simple_custom_name")
                if alvo is None or (alvo.get_text() or "").strip():
                    return False
                if self._selected_simple_choice() != "steam_game":
                    return False
                alvo.set_text(appid)
                self._toast_profile(f"Jogo em foco detectado: appid {appid}")
            except Exception as exc:
                logger.debug("prefill_appid_falhou", err=str(exc))
            return False

        call_async(
            method="daemon.state_full",
            params=None,
            on_success=_on_state,
            on_failure=lambda _exc: False,
            timeout_s=0.5,
        )

    # --- handlers da lista ---

    def on_profile_selection_changed(self, selection: Gtk.TreeSelection) -> None:
        name = self._selected_profile_name(selection)
        if name is None:
            return
        # PERF-GUI-PROFILE-LOAD-NONBLOCKING-01: lê do cache em memória em vez de
        # reler todos os perfis do disco a cada clique (load_all_profiles travava
        # a thread GTK).
        profile = self._find_cached_profile(name)
        if profile is None:
            return
        # NUNCA-TROCA-O-ALVO-01: a janela nunca troca o alvo do Salvar sem gesto
        # dela. Seleção que o CÓDIGO moveu (repintura da lista depois de
        # `store.clear()`, sync com o perfil ativo) atualiza a LISTA e para por
        # aí enquanto houver trabalho não salvo — repintar aqui é apagar o que
        # ela ainda não gravou e mirar o Salvar noutro arquivo.
        if self._selecao_programatica and self._ha_trabalho_no_editor():
            logger.info(
                "perfis_editor_preservado_em_selecao_automatica",
                linha=name,
                editando=getattr(self, "_alvo_do_salvar", None),
            )
            return
        self._populate_editor(profile)

    # ONDA-U (U3-B): `on_profile_row_activated` foi REMOVIDO junto com o
    # binding `row-activated` do glade — duplo-clique na lista ativava o
    # perfil na hora (profile.switch sem confirmação), atropelando edição em
    # andamento (selecionar texto/navegar vira 2 cliques rápidos por
    # acidente). O botão "Ativar" (`on_profile_activate`) já cobre o gesto
    # explícito; remover o binding é menos intrusivo que somar uma
    # confirmação a um segundo caminho para a mesma ação.

    def on_profile_new(self, _btn: Gtk.Button | None) -> None:
        self._duplicate_source = None  # perfil novo parte de defaults, não de cópia
        # R-09: marca a intenção "perfil NOVO" para o build não cair no
        # `selected_source` (que existe para rename/duplicação). Sem esta flag,
        # criar um perfil com "Navegação" selecionado fazia o arquivo novo
        # nascer com os overrides por-MAC e o `suppress_desktop_emulation` dele.
        # `unselect_all()` seria o caminho óbvio e está DESCARTADO: dispara
        # repopulação do editor e apagaria o que ela acabou de digitar.
        self._new_profile = True
        # NUNCA-TROCA-O-ALVO-01: um perfil novo não mira arquivo nenhum ainda.
        self._alvo_do_salvar = None
        self._get("profile_name_entry").set_text("Novo perfil")
        self._get("profile_priority_scale").set_value(0)
        self._select_radio("any")
        self._get("profile_window_class_entry").set_text("")
        self._get("profile_title_regex_entry").set_text("")
        self._get("profile_process_name_entry").set_text("")
        self._get("profile_simple_custom_name").set_text("")
        # FEAT-PROFILE-MODE-GUI-01: perfil novo nasce "sem opinião" de modo.
        self._set_mode_editor(None)
        # BUG-PROFILE-NEW-STALE-MODE-01: se o usuário vinha de um perfil de match
        # COMPLEXO, o editor ficou em modo avançado (stack/switch/_mode_advanced).
        # Sem resetar, "Salvar" monta um MatchCriteria VAZIO (não casa com nada),
        # em vez do "Qualquer" que o radio passou a mostrar. Volta ao modo simples
        # espelhando o ramo simples de _populate_editor.
        self._mode_advanced = False
        stack: Gtk.Stack = self._get("profile_editor_stack")
        if stack is not None:
            stack.set_visible_child_name("simples")
        switch: Gtk.Switch = self._get("profile_advanced_switch")
        if switch is not None:
            self._suppress_advanced_toggle = True
            try:
                switch.set_active(False)
            finally:
                self._suppress_advanced_toggle = False
        # SALVAR-NAO-REBAIXA-01: não há valor de disco a preservar num perfil
        # que ainda não existe — os widgets voltam a ser a única fonte.
        #
        # SALVAR-NAO-REBAIXA-02: e vem POR ÚLTIMO, depois de posicionar os
        # widgets, exatamente como em `_populate_editor`. Chamado antes (como
        # estava), o `set_value(0)` e o `set_active_id("any")` logo acima
        # levantavam as marcas de gesto — e "Novo perfil" nascia dizendo que ela
        # tinha escolhido prioridade 0 e "Qualquer". Num Salvar por cima de um
        # arquivo EXISTENTE, essa mentira virava rebaixamento: as guardas
        # reabilitadas em `_build_profile_from_editor` acreditavam nas marcas.
        # O prefill do jogo em foco (assíncrono, logo abaixo) marca de verdade,
        # e continua vencendo — ali a escolha É do editor.
        self._esquecer_a_fotografia_do_editor()
        self._toast_profile("Novo perfil: edite e clique Salvar")
        # PERFIL-NASCE-CERTO-01: com um jogo em foco, criar um perfil JÁ É a
        # declaração de intenção "quero que isto valha neste jogo".
        self._nascer_com_o_jogo_em_foco()

    def _nascer_com_o_jogo_em_foco(self) -> None:
        """Pergunta ao daemon qual janela está em foco e nasce com a regra dela.

        Assíncrono e best-effort, como os demais prefills desta aba: daemon
        offline é silêncio, e o perfil nasce catch-all como sempre nasceu.
        """
        def _on_state(result: Any) -> bool:
            self._aplicar_nascimento_com_jogo(result)
            return False

        call_async(
            method="daemon.state_full",
            params=None,
            on_success=_on_state,
            on_failure=lambda _exc: False,
            timeout_s=0.5,
        )

    def _aplicar_nascimento_com_jogo(self, result: Any) -> bool:
        """Aplica ao editor o nascimento com a regra do jogo em foco.

        Separado do IPC para ser exercitável sem daemon. Devolve True quando
        de fato mexeu no editor.

        PERFIL-NASCE-CERTO-01 (entrega 1). Medido em 26/07, com ela jogando: o
        perfil que ela criou para o Pragmata nasceu `match:any` e prioridade 0,
        e por isso NUNCA valia no jogo — a regra R-21 nega autoridade a
        catch-all em janela de jogo, e o catch-all dela (prioridade 100) vencia
        em todo o resto. Ela não errou a configuração: a janela não tinha saída.

        Guardas deliberadamente estreitas — este caminho só age sobre um
        editor ainda intocado:

        - só em perfil NOVO (`_new_profile`);
        - só se o "Aplica a" ainda estiver em "Qualquer" (o default do nascer);
        - só com o campo do alvo VAZIO. Se ela já escolheu ou digitou algo, a
          resposta do daemon chegou tarde e não tem direito de atropelar.

        Sem jogo em foco, nada acontece e o perfil continua nascendo catch-all
        — que é o certo para um perfil de desktop.
        """
        try:
            if not isinstance(result, dict):
                return False
            if not getattr(self, "_new_profile", False):
                return False
            from hefesto_dualsense4unix.app.actions.launch_wrapper_dialog import (
                extract_steam_appid,
            )

            appid = extract_steam_appid(result.get("window_detect_last_class"))
            if not appid:
                return False
            if self._selected_simple_choice() != "any":
                return False
            entry = self._get("profile_simple_custom_name")
            if entry is not None and (entry.get_text() or "").strip():
                return False
            self._select_radio("steam_game")
            if entry is not None:
                entry.set_text(appid)
            prioridade = self._prioridade_acima_dos_catch_all()
            escala = self._get("profile_priority_scale")
            if escala is not None:
                escala.set_value(prioridade)
            self._toast_profile(
                f"Perfil novo para o jogo em foco (número {appid}), prioridade "
                f"{prioridade} — acima dos perfis que valem sempre."
            )
            return True
        except Exception as exc:
            logger.debug("nascer_com_o_jogo_em_foco_falhou", err=str(exc))
            return False

    def on_profile_duplicate(self, _btn: Gtk.Button | None) -> None:
        name = self._selected_profile_name()
        if name is None:
            self._toast_profile("Selecione um perfil para duplicar")
            return
        # BUG-DUPLICATE-NO-CONFIG-COPY-01: guarda o perfil-fonte para que
        # _build_profile_from_editor copie triggers/lightbar/LEDs/etc — antes a
        # cópia só mudava o nome e o resto virava default (perda da config real).
        self._duplicate_source = self._find_cached_profile(name)
        # R-09: duplicar É partir de uma fonte — sai do estado "perfil novo".
        self._new_profile = False
        # NUNCA-TROCA-O-ALVO-01: a cópia vai para um arquivo NOVO — o Salvar
        # deixa de mirar o perfil-fonte no mesmo instante em que ela clica aqui.
        self._alvo_do_salvar = None
        current = self._get("profile_name_entry").get_text()
        self._get("profile_name_entry").set_text(f"{current} (cópia)")
        self._toast_profile("Editor preenchido com cópia completa; ajuste o nome e Salvar")

    def on_profile_remove(self, _btn: Gtk.Button | None) -> None:
        name = self._selected_profile_name()
        if name is None:
            self._toast_profile("Selecione um perfil para remover")
            return
        # BUG-DELETE-NO-CONFIRM-01: remoção é permanente — pedir confirmação
        # (espelha o padrão de confirm_restore_default do rodapé e do CLI).
        from hefesto_dualsense4unix.app import gui_dialogs

        window = self._get("main_window")
        if not gui_dialogs.confirm_delete_profile(parent=window, name=name):
            self._toast_profile("Remoção cancelada.")
            return
        try:
            delete_profile(name)
        except (FileNotFoundError, OSError) as exc:
            self._toast_profile(f"Falha ao remover: {exc}")
            return
        # NUNCA-TROCA-O-ALVO-01: aqui NÃO se zera `_alvo_do_salvar`, e a razão
        # foi medida ao arrancar a cura para ver o teste morder. Zerar faz o
        # alvo cair no fallback (a linha selecionada), que depois da recarga é
        # OUTRO perfil — e um Salvar em seguida viraria um RENAME dele, com o
        # diálogo do R-10 se oferecendo para apagá-lo. Mantido apontado para o
        # arquivo que morreu, todas as guardas degradam sozinhas: o
        # `find_by_slug` no cache novo devolve `None` e nenhum perfil vivo é
        # posto em risco. A repintura logo abaixo reaponta o editor sempre que
        # ele estiver limpo, que é o caso normal.
        self._reload_profiles_store()
        self._toast_profile(f"Perfil removido: {name}")
        # DEDUP-04: o daemon rematerializa o launch_env (o steam_app_<id>.env
        # do perfil apagado precisa sumir junto — senão fica rançoso).
        self._notify_launch_env_refresh()

    def on_profile_activate(self, _btn: Gtk.Button | None) -> None:
        name = self._selected_profile_name()
        if name is None:
            self._toast_profile("Selecione um perfil para ativar")
            return
        # T4: profile.switch é I/O do daemon (asyncio.run no _safe_call síncrono
        # travava a thread GTK até o timeout). call_async despacha ao worker e
        # devolve o toast/refresh via GLib.idle_add — mesmo padrão async da aba.
        #
        # ATIVAR-NAO-MENTE-01: o `timeout_s` era o default de LEITURA da ponte
        # (250 ms) e o handler `profile.switch` levou ~1,2 s MEDIDOS no journal
        # dela. Toda ativação caía no `_on_profile_switch_failure` — "Falha
        # (daemon offline?)" com o perfil JÁ ativo —, o caminho de sucesso nunca
        # rodava, e ela clicava de novo: cada clique uma ativação real.
        #
        # ATIVAR-NAO-MENTE-01: e o `_result` deixou de ser descartado. A
        # resposta traz o relatório da R-03 (`secoes`), que é a diferença entre
        # "ativado" e "ativado, menos o que o lock manual descartou".
        call_async(
            method="profile.switch",
            params={"name": name},
            on_success=lambda result: self._on_profile_switch_success(name, result),
            on_failure=self._on_profile_switch_failure,
            timeout_s=PROFILE_SWITCH_TIMEOUT_S,
        )

    def _on_profile_switch_success(self, name: str, result: Any = None) -> bool:
        """Callback GTK do switch de perfil: toast + re-sincroniza a seleção."""
        # ATIVAR-NAO-MENTE-01: o toast diz o que NÃO entrou, no vocabulário do
        # rodapé (`_mensagem_de_aplicacao`) — nunca um segundo vocabulário.
        self._toast_profile(mensagem_de_ativacao(name, result))
        # UX-PROFILES-ACTIVE-HIGHLIGHT-01: negrito imediato na linha ativada.
        self._mark_active_profile_row(name)
        # Preserva o comportamento visível: seleção acompanha o perfil ativo
        # reportado pelo daemon após o switch.
        self._sync_selection_with_active_profile()
        # ATIVAR-NAO-MENTE-01: e as abas passam a mostrar o perfil ativado AGORA.
        self._refazer_as_abas_apos_ativar(name)
        return False  # GLib.idle_add: não repetir

    def _refazer_as_abas_apos_ativar(self, name: str) -> None:
        """As abas passam a mostrar o perfil ATIVADO, na hora.

        ATIVAR-NAO-MENTE-01 (leva 2, 05/08). Queixa literal dela: *"o perfil
        que eu ativei não aplica imediatamente as features das abas"*. E era
        verdade — `on_profile_activate` não refazia aba nenhuma. As abas só
        acompanhavam pelo tique de 2 Hz, e esse caminho
        (`_reconciliar_draft_com_perfil_ativo`) tem um portão que DESISTE
        quando há edição pendente: com uma cor mexida e não salva, a ativação
        explícita dela não mudava a tela nunca.

        Recarregar em silêncio seria trocar um jeito de perder trabalho por
        outro (é o que a R-08 já tinha decidido para o tique). Ignorar em
        silêncio deixa as abas mentindo. Então a decisão é DELA, por diálogo —
        e o default do diálogo é MANTER o que ela não salvou.
        """
        pendente = False
        checar = getattr(self, "_tem_edicao_pendente", None)
        if callable(checar):
            with contextlib.suppress(Exception):
                pendente = bool(checar())
        if pendente:
            from hefesto_dualsense4unix.app import gui_dialogs

            editando = getattr(self, "_active_profile_name", "") or None
            if not gui_dialogs.confirm_discard_pending_edits(
                parent=self._get("main_window"), ativado=name, editando=editando
            ):
                self._toast_profile(
                    f"Perfil ativado: {name}. As abas seguem mostrando as suas "
                    f"alterações não salvas de '{editando or '—'}'."
                )
                return
        self._recarregar_as_abas_do_perfil_ativo()

    def _recarregar_as_abas_do_perfil_ativo(self) -> None:
        """Relê o perfil ativo do disco e repinta TODAS as abas.

        O caminho canônico é o `_bootstrap_draft_async` da janela: ele carrega
        o rascunho do perfil ativo em worker (nada de disco na thread do GTK) e
        chama `_refresh_all_tabs` no callback. Sem ele (dublê de teste, mixin
        montado sozinho), o refresh direto ainda repinta o que já está em
        memória — melhor que não repintar nada.
        """
        recarregar = getattr(self, "_bootstrap_draft_async", None)
        if callable(recarregar):
            try:
                recarregar()
                return
            except Exception as exc:
                logger.warning("ativar_recarregar_rascunho_falhou", err=str(exc))
        from hefesto_dualsense4unix.app.actions.footer_actions import (
            _refresh_all_tabs,
        )

        try:
            _refresh_all_tabs(self)
        except Exception as exc:
            logger.warning("ativar_refazer_abas_falhou", err=str(exc))

    def _on_profile_switch_failure(self, exc: Exception) -> bool:
        """Callback GTK de falha do switch (daemon offline / erro de transporte)."""
        logger.debug("profile_switch_falhou", err=str(exc))
        self._toast_profile("Falha (daemon offline?)")
        return False

    def on_profile_reload(self, _btn: Gtk.Button | None) -> None:
        self._reload_profiles_store()
        self._toast_profile("Lista recarregada")

    def on_profile_save(self, _btn: Gtk.Button | None) -> None:
        try:
            profile = self._build_profile_from_editor()
        except (ValueError, ValidationError) as exc:
            # COR-D: nada de despejar o dump cru do pydantic (nome de campo
            # interno + URL de erro) no rodapé de uma linha — traduz o erro
            # para uma frase que o usuário entende e sabe o que fazer.
            self._toast_profile(self._humanize_profile_error(exc))
            return
        # NUNCA-TROCA-O-ALVO-01: quem responde "que perfil eu estou editando?" é
        # o alvo MEMORIZADO na abertura do editor, não a linha que estiver
        # selecionada agora — a lista se move sozinha (sync com o perfil ativo,
        # repintura depois de recarregar) e arrastava o Salvar junto.
        selected = self._alvo_do_salvar_do_editor()
        # R-10 (auditoria 23/07): a identidade do arquivo é o SLUG
        # (`save_profile` grava `<slugify(name)>.json`), e as duas guardas
        # comparavam NOME DE EXIBIÇÃO. Com "Navegação" no disco, salvar
        # "Navegacao" caía fora das duas e substituía `navegacao.json` sem
        # aviso nenhum. Daqui para baixo quem responde "quem vou sobrescrever?"
        # é `find_by_slug`, e o diálogo cita o perfil REALMENTE afetado.
        cache: list[Profile] = getattr(self, "_profiles_cache", [])
        selecionado = find_by_slug(selected, cache) if selected else None
        e_novo = bool(getattr(self, "_new_profile", False))
        duplicando = self._duplicate_source is not None

        # R-10: RENAME. Trocar o nome no campo Nome gerava um arquivo NOVO e
        # deixava o antigo em disco — dois perfis com o mesmo `match` e a mesma
        # prioridade disputando as mesmas janelas, e o "removido" voltando a
        # ativar sozinho. Pergunta explicitamente o que ela quis dizer.
        renomeando_de: str | None = None
        if (
            not e_novo
            and not duplicando
            and selecionado is not None
            and not mesmo_slug(selecionado.name, profile.name)
        ):
            escolha = self._prompt_rename_or_copy(selecionado.name, profile.name)
            if escolha is None:
                self._toast_profile(_motivo_do_cancelamento())
                return
            if escolha == "renomear":
                renomeando_de = selecionado.name

        # BUG-PROFILE-SAVE-SILENT-OVERWRITE-01 + R-10: avisa ao gravar por cima
        # de OUTRO perfil (não na edição in-place do próprio selecionado). Um
        # perfil NOVO/duplicado nunca é edição in-place, mesmo com uma linha
        # selecionada na lista — era por aí que "Novo perfil" chamado
        # "Navegacao" comia a "Navegação" dela em silêncio.
        alvo = find_by_slug(profile.name, cache)
        editando_em_lugar = (
            not e_novo
            and not duplicando
            and alvo is not None
            and selecionado is not None
            and mesmo_slug(alvo.name, selecionado.name)
        )
        if alvo is not None and not editando_em_lugar:
            from hefesto_dualsense4unix.app import gui_dialogs

            window = self._get("main_window")
            # `alvo.name` e não `profile.name`: quem some é o perfil do disco.
            if not gui_dialogs.prompt_overwrite_existing(parent=window, name=alvo.name):
                self._toast_profile(_motivo_do_cancelamento())
                return
        # COR-A: salvar um perfil que ANTES valia só num programa específico
        # (MatchCriteria) como MatchAny apaga o alvo em silêncio — o caminho
        # clássico é o leigo desligar o "Modo avançado" (a página simples herda
        # 'Qualquer'/Sempre) e clicar Salvar sem perceber. Confirma a perda.
        # R-10: num rename, o "antes" é o perfil sendo RENOMEADO, não quem
        # ocupa o slug de destino.
        # SALVAR-NAO-REBAIXA-02: a guarda era `isinstance(original.match,
        # MatchCriteria)` e deixava de fora o perfil "Só manual (nunca ativa
        # sozinho)" — tanto o `MatchManual` de propósito quanto o `criteria`
        # vazio. Virar "vale para TUDO" é, nesses dois, a mudança mais violenta
        # que a aba sabe fazer, e era a única que passava calada. Agora a
        # pergunta é a certa: o perfil deixa de ter alvo? Então avisa.
        original = selecionado if renomeando_de is not None else alvo
        if (
            isinstance(profile.match, MatchAny)
            and original is not None
            and not isinstance(original.match, MatchAny)
        ):
            from hefesto_dualsense4unix.app import gui_dialogs

            window = self._get("main_window")
            # O rótulo do que ele É HOJE é o MESMO da coluna "Quando usar" —
            # o diálogo não pode chamar de "programas específicos" um perfil
            # que a lista chama de "Só manual".
            if not gui_dialogs.confirm_downgrade_match_to_any(
                parent=window,
                name=original.name,
                regra_atual=_match_label(original.match),
            ):
                self._toast_profile(_motivo_do_cancelamento())
                return
        # SALVAR-NAO-REBAIXA-02: e a PRIORIDADE, que nos perfis dela (já em
        # `MatchAny` desde o defeito de 27/07) é a única coisa que ainda podia
        # cair calada — e é o termo que decide qual dos "Sempre" vence.
        if original is not None and queda_de_prioridade_pede_aviso(
            original.priority, profile.priority
        ):
            from hefesto_dualsense4unix.app import gui_dialogs

            window = self._get("main_window")
            if not gui_dialogs.confirm_downgrade_priority(
                parent=window,
                name=original.name,
                de=int(original.priority),
                para=int(profile.priority),
            ):
                self._toast_profile(_motivo_do_cancelamento())
                return
        # R-10: quem estava ativo ANTES do save — é com esse nome que o daemon
        # conhece o perfil renomeado. Lido aqui (e não depois do delete) porque
        # o `profile.switch` de migração precisa da foto anterior.
        try:
            ativo_antes = active_profile_name()
        except Exception:
            ativo_antes = None
        try:
            save_profile(profile)
        except OSError as exc:
            self._toast_profile(f"Falha ao salvar: {exc}")
            return
        # R-10: rename é MOVER, não copiar — o antigo só morre DEPOIS do save
        # bem-sucedido (o `delete_profile` de um preset é definitivo: o marker
        # `.seeded_presets` respeita a deleção e ele não volta a ser semeado).
        if renomeando_de is not None:
            try:
                delete_profile(renomeando_de)
            except (FileNotFoundError, OSError, ValueError) as exc:
                logger.warning(
                    "profile_rename_delete_falhou", antigo=renomeando_de, err=str(exc)
                )
                self._toast_profile(
                    f"Salvo como {profile.name}, mas o antigo "
                    f"'{renomeando_de}' não pôde ser removido: {exc}"
                )
        self._duplicate_source = None  # duplicação concluída
        # R-09: salvo em disco, o perfil deixa de ser "novo" — o próximo Salvar
        # sobre ele é edição normal e deve reusar a config gravada.
        self._new_profile = False
        # NUNCA-TROCA-O-ALVO-01: o que estava no editor VIROU disco. O alvo
        # passa a ser o arquivo gravado (é o gesto dela que o move, e este é o
        # gesto), e as marcas de "ela mexeu" caem — sem isso o editor seguiria
        # dado como sujo pelo resto da sessão e a repintura logo abaixo não
        # poderia mais mostrar a ele o que acabou de ser gravado.
        self._alvo_do_salvar = profile.name
        self._regra_tocada = False
        self._prioridade_tocada = False
        self._modo_tocado = False
        # ABAS-01: o disco mudou; o rascunho tem de saber. Sem esta linha, o
        # "Salvar Perfil" do rodapé reemitia a fotografia do BOOT e apagava a
        # seção `mode` (e a regra, e a prioridade) recém-gravada aqui.
        self._reconciliar_rascunho_com_perfil_salvo(profile, renomeando_de)
        self._reload_profiles_store(select_name=profile.name)
        # PERFIL-SAVE-APPLY-01 (22/07): o daemon NÃO relê JSON de perfil por
        # conta própria (sem watch de arquivo) — salvar o perfil que está
        # ATIVO agora reaplica na hora via `profile.switch` (relê o disco).
        # Sem isso, "Salvar" só gravava o arquivo e nada mudava no controle,
        # lido pela usuária como "não está salvando". Best-effort: daemon
        # offline segue o fluxo antigo (o boot reaplica).
        #
        # R-10: no rename, o daemon continua com o nome ANTIGO marcado como
        # ativo — e o arquivo dele acabou de ser apagado. Sem migrar o marker,
        # o boot seguinte procuraria um perfil que não existe mais e cairia no
        # fallback (catch-all), que é justamente o cenário da queixa (1).
        reaplicado = False
        try:
            if ativo_antes is not None and (
                ativo_antes == profile.name or ativo_antes == renomeando_de
            ):
                reaplicado = profile_switch(profile.name)
        except Exception:
            reaplicado = False
        if renomeando_de is not None:
            self._toast_profile(
                f"Perfil renomeado: {renomeando_de} → {profile.name}"
                + (" (reaplicado no controle)" if reaplicado else "")
            )
        else:
            self._toast_profile(
                f"Perfil salvo e reaplicado no controle: {profile.name}"
                if reaplicado
                else f"Perfil salvo: {profile.name}"
            )
        # DEDUP-04: perfil novo/editado pode ter steam_app_<id> no match — o
        # daemon rematerializa a antecipação por appid do launch_env AGORA
        # (sem isso, o primeiro launch do jogo cairia no default.env rançoso).
        self._notify_launch_env_refresh()

    # --- helpers internos ---

    def _prompt_rename_or_copy(self, antigo: str, novo: str) -> str | None:
        """Ponte para o diálogo de rename (R-10) — ponto único de override.

        Método (e não chamada direta) para os testes decidirem a resposta sem
        subir GTK, do mesmo jeito que o resto da aba faz com `gui_dialogs`.
        """
        return dialogo_renomear_ou_copiar(
            self._get("main_window"), antigo, novo
        )

    def _notify_launch_env_refresh(self) -> None:
        """Avisa o daemon que o conjunto de perfis mudou (`launch_env.refresh`).

        save/delete de perfil rodam no processo da GUI, direto no disco — o
        daemon não vê (achado MED da revisão adversarial da Fase 2).
        Best-effort: daemon offline é normal (rematerializa no boot).
        """
        call_async(
            method="launch_env.refresh",
            params={},
            on_success=lambda _result: False,
            on_failure=lambda _exc: False,
        )

    def _apply_editor_mode(self) -> None:
        """Aplica a página correta da stack conforme _mode_advanced."""
        stack: Gtk.Stack = self._get("profile_editor_stack")
        page = "avancado" if self._mode_advanced else "simples"
        stack.set_visible_child_name(page)

    def _selected_simple_choice(self) -> str:
        """Retorna o id ativo do seletor "Aplica a:".

        UI-PROFILES-RADIO-GROUP-REDESIGN-01: antes iterava 6 GtkRadioButton.
        FEAT-DSX-COMBO-TO-SEGMENTED-01: agora lê `get_active_id()` do
        SegmentedSelector (`self._aplica_a`). Fallback "any" preserva o
        comportamento anterior quando o seletor ainda não foi populado.
        """
        combo = getattr(self, "_aplica_a", None)
        if combo is None:
            return "any"
        active_id = combo.get_active_id()
        if active_id in _RADIO_IDS:
            return str(active_id)
        return "any"

    def _select_radio(self, choice: str) -> None:
        """Seleciona o id correspondente no seletor "Aplica a:".

        Nome histórico preservado para facilitar grep pelo contexto antigo;
        a implementação usa `set_active_id()` do SegmentedSelector em vez de
        `set_active(True)` num radio específico.
        """
        combo = getattr(self, "_aplica_a", None)
        if combo is None:
            return
        target_id = choice if choice in _RADIO_IDS else "any"
        combo.set_active_id(target_id)

    def _selected_profile_name(
        self,
        selection: Gtk.TreeSelection | None = None,
    ) -> str | None:
        sel = selection or self._get("profiles_tree").get_selection()
        model, tree_iter = sel.get_selected()
        if tree_iter is None:
            return None
        return str(model.get_value(tree_iter, 0))

    def _reload_profiles_store(
        self,
        select_name: str | None = None,
        on_done: Any | None = None,
    ) -> None:
        """Recarrega a lista de perfis SEM bloquear a thread GTK.

        PERF-GUI-PROFILE-LOAD-NONBLOCKING-01: load_all_profiles() (glob + FileLock
        + parse Pydantic) roda em thread worker; o store e o cache em memória
        (`_profiles_cache`) são atualizados no callback, na thread GTK. `on_done`
        (opcional) roda após popular o store (ex.: sincronizar a seleção com o
        perfil ativo no boot).
        """
        def _load() -> list[Profile]:
            return list(load_all_profiles())

        def _on_loaded(profiles: Any) -> bool:
            self._profiles_cache = list(profiles)
            self._populate_profiles_store(profiles, select_name)
            if on_done is not None:
                on_done()
            return False  # GLib.idle_add: não repetir

        run_in_thread(_load, _on_loaded)

    def _populate_profiles_store(
        self, profiles: list[Profile], select_name: str | None
    ) -> None:
        """Popula o ListStore a partir da lista de perfis (thread GTK).

        NUNCA-TROCA-O-ALVO-01: sem ``select_name``, a linha que volta a ficar
        selecionada é A MESMA de antes — e o primeiro da lista é fallback só
        quando não havia nada selecionado (o boot) ou quando o que estava
        selecionado sumiu do disco (a remoção). Era daqui que saía o "nome
        aleatório" da queixa: `on_profile_remove`, `on_profile_reload` (o botão
        "Recarregar lista") e `install_profiles_tab` chamam
        `_reload_profiles_store()` SEM alvo, e o editor pulava para o PRIMEIRO
        arquivo em ordem de carga — no disco dela, "Ação". O Salvar seguinte
        gravava lá.

        A repintura INTEIRA corre marcada como programática, e não só a
        reseleção do fim. Medido em 06/08: `store.clear()` apaga as linhas uma a
        uma e o GtkTreeView emite `changed` no meio disso, com a seleção ainda
        resolvendo para uma linha viva — o editor era repintado ANTES de a
        função chegar a selecionar coisa alguma. Marcar só o `select_iter`
        curava o caminho errado e deixava o mesmo defeito entrar pela porta do
        `clear`.
        """
        store = self._profiles_store
        # Lido ANTES do `clear()`: depois dele não há mais linha selecionada.
        atual: str | None = None
        if select_name is None:
            with contextlib.suppress(Exception):
                atual = self._selected_profile_name()
        anterior = self._selecao_programatica
        self._selecao_programatica = True
        try:
            store.clear()
            select_iter = None
            first_iter = None
            active = getattr(self, "_active_profile_hint", None)
            for profile in profiles:
                weight = 700 if profile.name == active else 400
                row_iter = store.append(
                    [
                        profile.name,
                        profile.priority,
                        # R-12: o OBJETO, não o discriminador — só ele distingue
                        # "criteria com alvo" de "criteria vazio" (só manual).
                        # EMPATE-01/E2: `profiles` chega na ORDEM DE CARGA do
                        # loader, e é dela que sai o terceiro termo do desempate
                        # — reordenar esta lista mudaria o vencedor anunciado.
                        rotulo_quando_usar(profile, profiles, active),
                        weight,
                        explicacao_da_disputa(profile, profiles, active),
                    ]
                )
                if first_iter is None:
                    first_iter = row_iter
                desejado = select_name if select_name is not None else atual
                if desejado is not None and profile.name == desejado:
                    select_iter = row_iter
            target = select_iter if select_iter is not None else first_iter
            if target is not None:
                self._mover_selecao_sem_gesto(target)
        finally:
            self._selecao_programatica = anterior

    def _mark_active_profile_row(self, active: str | None) -> None:
        """Realça (negrito) a linha do perfil ATIVO no ListStore, in-place.

        EMPATE-01/E2: o perfil ativo é também o INCUMBENTE, que é o terceiro
        termo do desempate entre os "Sempre" — trocar de perfil pode trocar o
        vencedor anunciado. Por isso as colunas da disputa (2 e 4) são
        recalculadas aqui junto com o negrito, e não só na recarga do disco.
        """
        self._active_profile_hint = active
        store = getattr(self, "_profiles_store", None)
        if store is None:
            return
        cache: list[Profile] = list(getattr(self, "_profiles_cache", []) or [])
        por_nome = {p.name: p for p in cache}
        row = store.get_iter_first()
        while row is not None:
            name = store.get_value(row, 0)
            store.set_value(row, 3, 700 if name == active else 400)
            perfil = por_nome.get(name)
            if perfil is not None:
                with contextlib.suppress(Exception):
                    store.set_value(
                        row, 2, rotulo_quando_usar(perfil, cache, active)
                    )
                    store.set_value(
                        row, 4, explicacao_da_disputa(perfil, cache, active)
                    )
            row = store.iter_next(row)

    def _find_cached_profile(self, name: str) -> Profile | None:
        """Retorna o perfil do cache em memória pelo nome, ou None."""
        cache: list[Profile] = getattr(self, "_profiles_cache", [])
        for profile in cache:
            if profile.name == name:
                return profile
        return None

    def _populate_editor(self, profile: Profile) -> None:
        """Preenche o editor com os dados do perfil.

        Detecta automaticamente se o match bate com um preset simples:
        - bate → modo simples, seleciona radio correspondente.
        - não bate → força modo avançado para não perder informação.

        NUNCA-TROCA-O-ALVO-01: esta é a linha em que a janela decide o que ela
        está editando, e ela SÓ é chamada por gesto dela (clique na lista) ou
        com o editor limpo — quem faz esse portão é
        `on_profile_selection_changed`, e a razão inteira está em
        `_ha_trabalho_no_editor`. Aqui só se registra a decisão:
        `_alvo_do_salvar` passa a ser este perfil, e é ele — não a linha
        selecionada — que o `on_profile_save` vai gravar por cima.
        """
        # Selecionar um perfil existente cancela qualquer duplicação em curso.
        self._duplicate_source = None
        # R-09: e também cancela o estado "perfil novo" — o editor passou a
        # mostrar um perfil que existe.
        self._new_profile = False
        self._alvo_do_salvar = profile.name
        self._get("profile_name_entry").set_text(profile.name)
        prio = max(0, min(PRIORIDADE_MAXIMA, profile.priority))
        self._get("profile_priority_scale").set_value(prio)
        # FEAT-PROFILE-MODE-GUI-01: seção "Modo" reflete profile.mode
        # (None → "Não mexer no modo").
        self._set_mode_editor(profile.mode)

        match = profile.match
        preset_key = detect_simple_preset(match)

        if preset_key is not None:
            # Match reconhecido como preset simples — usa modo simples
            self._select_radio(preset_key)
            # R-12: o campo livre serve "game" (nome do programa) E
            # "steam_game" (appid) — `simple_extra` é quem sabe extrair cada
            # um. Sem isso o round-trip de um perfil da Steam mostraria o campo
            # vazio e salvar por cima levantaria "diga o número do jogo".
            if preset_key in _IDS_COM_CAMPO_LIVRE:
                self._get("profile_simple_custom_name").set_text(simple_extra(match))
            else:
                self._get("profile_simple_custom_name").set_text("")
            # Vai para página simples sem alterar a preferência persistida
            stack: Gtk.Stack = self._get("profile_editor_stack")
            stack.set_visible_child_name("simples")
            switch: Gtk.Switch = self._get("profile_advanced_switch")
            # BUG-ADVANCED-TOGGLE-CLOBBER-01: guard flag em vez de bloquear um
            # handler dummy recém-conectado (que vazava e não bloqueava o real).
            self._suppress_advanced_toggle = True
            try:
                switch.set_active(False)
            finally:
                self._suppress_advanced_toggle = False
            self._mode_advanced = False
        else:
            # Match complexo — força modo avançado.
            # BUG-PROFILE-SIMPLE-STALE-01: zera o editor simples para não vazar
            # estado de um perfil simples anterior ('game' + nome). Sem isso, se o
            # usuário depois desligar o switch Avançado, a página simples reaparece
            # com o preset/nome herdados e salvar sobrescreveria este match complexo.
            self._select_radio("any")
            self._get("profile_simple_custom_name").set_text("")
            if isinstance(match, MatchCriteria):
                self._get("profile_window_class_entry").set_text(
                    ",".join(match.window_class)
                )
                self._get("profile_title_regex_entry").set_text(
                    match.window_title_regex or ""
                )
                self._get("profile_process_name_entry").set_text(
                    ",".join(match.process_name)
                )
            else:
                self._get("profile_window_class_entry").set_text("")
                self._get("profile_title_regex_entry").set_text("")
                self._get("profile_process_name_entry").set_text("")
            stack = self._get("profile_editor_stack")
            stack.set_visible_child_name("avancado")
            switch = self._get("profile_advanced_switch")
            self._suppress_advanced_toggle = True
            try:
                switch.set_active(True)
            finally:
                self._suppress_advanced_toggle = False
            self._mode_advanced = True

        # SALVAR-NAO-REBAIXA-01: a fotografia do que o editor MOSTRA agora, e o
        # que o disco realmente diz. `_build_profile_from_editor` compara as
        # duas para saber se ela MEXEU na regra/prioridade nesta edição —
        # ver `_regra_foi_mexida` / `_prioridade_foi_mexida`.
        self._regra_do_disco = profile.match
        self._assinatura_da_regra_ao_abrir = self._assinatura_da_regra_no_editor()
        self._prioridade_do_disco = profile.priority
        self._prioridade_ao_abrir = prio
        # Zeradas por ÚLTIMO: as seleções feitas acima são de abertura, não dela.
        self._regra_tocada = False
        self._prioridade_tocada = False

    def _assinatura_da_regra_no_editor(self) -> tuple[object, ...]:
        """Fotografia dos widgets que definem a REGRA de janela do perfil.

        Duas fotografias iguais querem dizer "ela não tocou na regra" — e é só
        isso que esta assinatura precisa responder. Tolerante a widget ausente
        (dublê de teste, glade antigo): campo que não dá para ler entra vazio,
        do mesmo jeito nas duas fotos.

        O switch "Modo avançado" fica DE FORA de propósito: ele escolhe qual
        página ela está olhando, não o que o perfil casa. Incluí-lo devolveria
        o BUG-PROFILE-SIMPLE-STALE-01 pelo avesso — desligar o avançado para
        conferir alguma coisa e clicar Salvar rebaixaria a regra do perfil para
        "Qualquer", que é justamente o estrago que esta guarda existe para
        impedir. Mudar de página e MEXER num campo continua contando, porque é
        o campo que entra na fotografia.
        """
        def texto(widget_id: str) -> str:
            widget = self._get(widget_id)
            try:
                return (widget.get_text() or "").strip()
            except Exception:
                return ""

        return (
            self._selected_simple_choice(),
            texto("profile_simple_custom_name"),
            texto("profile_window_class_entry"),
            texto("profile_title_regex_entry"),
            texto("profile_process_name_entry"),
        )

    def _on_prioridade_tocada(self, _escala: object = None) -> None:
        """A escala de prioridade se mexeu — marca o gesto (SALVAR-NAO-REBAIXA-01)."""
        self._prioridade_tocada = True

    def _regra_foi_mexida(self) -> bool:
        """Ela mudou a regra de janela desde que este perfil abriu no editor?

        Sem fotografia guardada (perfil novo, duplicação de fonte externa,
        dublê) a resposta é SIM: o comportamento histórico — gravar o que está
        nos widgets — continua valendo em todo caminho que esta guarda não
        conhece.
        """
        ao_abrir = self._assinatura_da_regra_ao_abrir
        if ao_abrir is None:
            return True
        if self._regra_tocada:
            return True
        return self._assinatura_da_regra_no_editor() != ao_abrir

    def _prioridade_foi_mexida(self) -> bool:
        """Ela moveu a escala de prioridade desde que o perfil abriu no editor?

        Duas respostas somadas: o gesto (`_prioridade_tocada`, marcado pelo
        próprio widget) e a comparação de valor. O gesto cobre o caso em que o
        valor volta a coincidir com o da abertura — inclusive o perfil clampado,
        que abre mostrando o teto e cujo "arrastar até o teto" precisa contar.
        """
        if self._prioridade_tocada:
            return True
        ao_abrir = self._prioridade_ao_abrir
        if ao_abrir is None:
            return True
        try:
            return int(self._get("profile_priority_scale").get_value()) != int(ao_abrir)
        except Exception:
            return True

    def _perfil_que_o_salvar_sobrescreve(self, name: str) -> Profile | None:
        """O perfil JÁ EM DISCO que este Salvar vai gravar por cima, ou ``None``.

        SALVAR-NAO-REBAIXA-02: quem responde "quem vou sobrescrever?" é o SLUG,
        nunca o nome de exibição — a lição do R-10, e a mesma pergunta que
        `on_profile_save` já faz com `find_by_slug` para decidir o diálogo de
        sobrescrita. Lê o cache em memória, nunca o disco: este caminho roda na
        thread do GTK (PERF-GUI-PROFILE-LOAD-NONBLOCKING-01).
        """
        cache: list[Profile] = getattr(self, "_profiles_cache", None) or []
        try:
            return find_by_slug(name, cache)
        except Exception:
            return None

    def _regra_do_disco_ao_salvar(self, name: str) -> Match | None:
        """A regra que este Salvar sobrescreve — para NÃO apagar o que a tela não mostra.

        ESCONDER-EM-VEZ-DE-SAIR-01 (10/08/2026). A página simples do "Jogo da
        Steam" tem um campo só, o número; um perfil pode ter no disco também um
        ``process_name`` do mesmo jogo. ``from_simple_choice`` precisa dele para
        preservar o campo invisível — ver `profiles/simple_match.py`.

        Duas fontes, na mesma ordem que as guardas SALVAR-NAO-REBAIXA já usam:
        a fotografia tirada quando o perfil ABRIU (o caso normal) e, quando não
        há fotografia (perfil "novo" salvando por cima de um arquivo que
        existe — o buraco que a SALVAR-NAO-REBAIXA-02 mediu), o próprio disco
        pelo slug.

        Vale SÓ para o editor simples, e é de propósito: no avançado o
        ``process_name`` está na tela, e apagá-lo ali é um gesto dela. Devolver
        esta regra para lá desfaria a exclusão que ela acabou de fazer.
        """
        regra = self._regra_do_disco
        if regra is not None:
            return regra
        alvo = self._perfil_que_o_salvar_sobrescreve(name)
        return alvo.match if alvo is not None else None

    def _esquecer_a_fotografia_do_editor(self) -> None:
        """Zera as fotografias — o editor deixou de mostrar um perfil do disco.

        Chamado por "Novo perfil": ali não há valor de disco a preservar, e o
        que está nos widgets É a intenção dela. O que EXISTE em disco continua
        protegido na hora de salvar, por ``_perfil_que_o_salvar_sobrescreve``
        (SALVAR-NAO-REBAIXA-02) — esquecer aqui não pode virar rebaixar lá.
        """
        self._regra_do_disco = None
        self._assinatura_da_regra_ao_abrir = None
        self._prioridade_do_disco = None
        self._prioridade_ao_abrir = None
        self._regra_tocada = False
        self._prioridade_tocada = False

    def _prioridade_acima_dos_catch_all(self) -> int:
        """Prioridade que vence TODO perfil "vale sempre" hoje em disco.

        PERFIL-NASCE-CERTO-01: o perfil do jogo nascia em 0 e perdia até para
        os presets de fábrica (50-80), quanto mais para o catch-all dela em
        100. O número é CALCULADO, não digitado — ela não precisa saber que
        existe prioridade para que o perfil do jogo dela valha no jogo.

        Lê o cache em memória da lista (nunca o disco: este caminho roda na
        thread do GTK). Sem cache, devolve a folga sozinha.
        """
        cache: list[Profile] = getattr(self, "_profiles_cache", None) or []
        tetos = [p.priority for p in cache if p.e_catch_all]
        base = max(tetos) if tetos else 0
        return max(0, min(PRIORIDADE_MAXIMA, base + _FOLGA_ACIMA_DO_CATCH_ALL))

    def _edita_o_perfil_do_rascunho(self, name: str) -> bool:
        """O "Salvar" em curso está gravando o perfil que o RASCUNHO representa?

        ABAS-03 (25/07). A mesclagem com o rascunho só acontecia quando o nome
        digitado batia com o do perfil ativo — o que exclui justamente o
        RENAME, onde o nome já mudou. Nesse caminho a base vinha do disco e, em
        seguida, `on_profile_save` apagava o perfil antigo: toda a edição de
        cor, gatilho, vibração e teclado feita na sessão evaporava, sem aviso e
        sem chance de desfazer (o arquivo de origem já não existia).

        Quem responde "qual perfil o rascunho é" é `_active_profile_name`, não
        o campo Nome. Então a resposta é sim quando:

        - o nome digitado ocupa o MESMO ARQUIVO do perfil ativo — comparação
          por SLUG, a lição do R-10: "Navegacao" e "Navegação" são o mesmo
          `navegacao.json`, e comparar nome de exibição deixava a edição do
          próprio perfil ativo cair no ramo do disco; ou
        - o PERFIL ABERTO NO EDITOR é o perfil ativo e este save não é "Novo
          perfil" nem duplicação — ou seja, é o rename dele.

        NUNCA-TROCA-O-ALVO-01: "o perfil aberto no editor" era lido da linha
        selecionada, e a lista se move sozinha — o rename do perfil ativo caía
        no ramo do disco assim que o autoswitch pulava a seleção para outra
        linha, que é o mesmo estrago que esta guarda existe para impedir.

        As duas exclusões são as mesmas do R-09: "Novo perfil" parte de
        defaults (não pode clonar overrides por-MAC de quem estava
        selecionado) e a duplicação parte da fonte guardada.
        """
        ativo = getattr(self, "_active_profile_name", "") or ""
        if not ativo:
            return False
        if name == ativo or mesmo_slug(name, ativo):
            return True
        if getattr(self, "_new_profile", False):
            return False
        if getattr(self, "_duplicate_source", None) is not None:
            return False
        try:
            no_editor = self._alvo_do_salvar_do_editor() or ""
        except Exception:
            return False
        return bool(no_editor) and mesmo_slug(no_editor, ativo)

    def _reconciliar_rascunho_com_perfil_salvo(
        self, profile: Profile, renomeando_de: str | None
    ) -> None:
        """Reaponta o rascunho para o perfil ACABADO DE GRAVAR (ABAS-01).

        A aba Perfis é a única superfície que edita e persiste perfil, e ela
        nunca escrevia de volta em `self.draft` — não havia uma única
        atribuição a ele no arquivo. As seções que só ela edita (`mode`,
        `match`, `priority`, `suppress_desktop_emulation`) iam direto para o
        disco, enquanto o rascunho seguia com a fotografia tirada no boot da
        janela. Aí o "Salvar Perfil" do rodapé, que reemite essa fotografia,
        desfazia o trabalho:

            aba Perfis → Modo = "Jogar pelo Hefesto" → Salvar *(grava certo)*
            → aba Lightbar → muda a cor → rodapé "Salvar Perfil" →
            a seção `mode` SOME do arquivo.

        É o mesmo estrago do MODO-01 visto de outro ângulo: ela faz tudo certo
        e o modo do perfil evapora. Vale igual para regra de janela,
        prioridade e supressão.

        Só reaponta quando o perfil gravado É o do rascunho (mesmo arquivo que
        o ativo, ou o rename dele) — salvar OUTRO perfil pela aba Perfis não
        pode mexer no que as demais abas estão editando. No rename, o nome do
        perfil ativo migra junto: sem isso a reconciliação do tick de 2 Hz
        veria o `profile.switch` de migração como "trocaram de perfil por fora"
        e recarregaria o rascunho por baixo dela.

        A linha de base do "há edição pendente" (R-08) também acompanha: o que
        estava em memória acabou de virar disco, então a sessão volta a ficar
        limpa e a reconciliação com o perfil ativo continua funcionando pelo
        resto dela.
        """
        draft = getattr(self, "draft", None)
        if draft is None:
            return
        ativo = getattr(self, "_active_profile_name", "") or ""
        if not ativo:
            return
        e_do_rascunho = mesmo_slug(profile.name, ativo) or (
            renomeando_de is not None and mesmo_slug(renomeando_de, ativo)
        )
        if not e_do_rascunho:
            return
        self.draft = draft.with_profile_identity(profile)
        self._active_profile_name = profile.name
        self._draft_baseline = self.draft

    def _build_profile_from_editor(self) -> Profile:
        """Constrói Profile a partir do editor (modo simples ou avançado)."""
        name = self._get("profile_name_entry").get_text().strip()
        priority = int(self._get("profile_priority_scale").get_value())

        match: Match
        if self._mode_advanced:
            wc = self._split_csv(
                self._get("profile_window_class_entry").get_text()
            )
            regex = self._get("profile_title_regex_entry").get_text().strip() or None
            pn = self._split_csv(
                self._get("profile_process_name_entry").get_text()
            )
            if not wc and not regex and not pn:
                # R-12 item 3: avançado com os TRÊS campos vazios é a única
                # forma de dizer "só ativo na mão" pela GUI — grava o sentinel
                # em vez do `MatchCriteria` vazio. Os dois nunca casam, mas só
                # o sentinel diz que foi de propósito: o criteria vazio fica
                # reservado ao ACIDENTE, que é o que o doctor denuncia. Também
                # é o que fecha o round-trip do perfil manual, que abre no
                # avançado justamente com os três campos em branco.
                match = MatchManual()
            else:
                match = MatchCriteria(
                    window_class=wc,
                    window_title_regex=regex,
                    process_name=pn,
                )
        else:
            choice = self._selected_simple_choice()
            custom = self._get("profile_simple_custom_name").get_text().strip() or None
            # ESCONDER-EM-VEZ-DE-SAIR-01: a página simples do jogo da Steam
            # mostra o NÚMERO e mais nada — a regra do disco vai junto para que
            # um `process_name` do mesmo jogo sobreviva ao round-trip em vez de
            # evaporar por falta de campo na tela.
            match = from_simple_choice(
                choice=choice,
                custom_name=custom,
                regra_do_disco=self._regra_do_disco_ao_salvar(name),
            )

        # PERF-GUI-PROFILE-LOAD-NONBLOCKING-01: usa o cache — este método roda a
        # cada montagem do perfil, e reler o disco aqui travava a thread GTK.
        existing = self._find_cached_profile(name)
        # BUG-DUPLICATE-NO-CONFIG-COPY-01: numa duplicação o nome novo ainda não
        # existe no cache -> sem o perfil-fonte a config viraria default. Usa a
        # fonte guardada por on_profile_duplicate como base.
        # BUG-RENAME-DROPS-CONFIG-01: renomear pelo campo Nome (nome novo, sem
        # passar por Duplicar) também não pode nascer com config default — o
        # perfil SELECIONADO na lista é a fonte natural do rename. Best-effort:
        # sem tree/seleção utilizável (preview cedo, stubs), segue sem fonte.
        selected_source = None
        try:
            selected_source = self._find_cached_profile(
                self._selected_profile_name() or ""
            )
        except Exception:
            selected_source = None
        # R-09 item 3 (auditoria 23/07): "Novo perfil" NÃO herda o perfil
        # selecionado na lista. `selected_source` existe para o RENAME
        # (BUG-RENAME-DROPS-CONFIG-01) e para a DUPLICAÇÃO; num perfil novo ele
        # fazia o arquivo nascer clonando overrides por-MAC e
        # `suppress_desktop_emulation` de outro perfil, sem nada dizendo isso.
        if getattr(self, "_new_profile", False):
            source = existing or self._duplicate_source
        else:
            source = existing or self._duplicate_source or selected_source

        # R-09 item 1 (auditoria 23/07): quando o perfil sendo editado é o que
        # o DRAFT representa, a base é o draft — não o disco.
        #
        # As abas Lightbar/Gatilhos/Rumble/Mouse/Teclado gravam EXCLUSIVAMENTE
        # em `self.draft`, e este módulo não lia o draft em nenhuma linha. Salvar
        # pela aba Perfis descartava tudo que ela tinha ajustado nas outras abas
        # — e é pior que perder o arquivo: `on_profile_save` chama
        # `profile_switch` quando o perfil salvo é o ativo, então o daemon relia
        # o JSON velho e REVERTIA no hardware a cor/gatilho que ela acabara de
        # ver funcionando. Daí a conclusão dela: "as configs que eu faço não
        # impactam".
        draft = getattr(self, "draft", None)
        ativo = getattr(self, "_active_profile_name", "") or ""
        base: dict[str, Any]
        # PERFIL-SALVA-TUDO-01: a base saiu do RASCUNHO? É o que decide se o
        # `mode` dele pode vencer a leitura da tela mais abaixo.
        base_veio_do_rascunho = False
        if draft is not None and ativo and self._edita_o_perfil_do_rascunho(name):
            try:
                # ABAS-03: `to_profile(ativo)`, não `to_profile(name)`. Num
                # RENAME o nome já mudou, e `to_profile` só reemite as seções
                # que o rascunho não edita (`suppress_desktop_emulation` entre
                # elas) quando o nome pedido é o do perfil de ORIGEM — pedir
                # pelo nome novo faria o perfil renomeado nascer sem elas.
                # Nome, prioridade, regra e modo vêm do EDITOR logo abaixo,
                # então renomear continua sendo renomear.
                do_draft = draft.to_profile(ativo)
            except Exception as exc:  # draft inconsistente não pode travar o save
                logger.warning("profile_build_draft_falhou", erro=str(exc))
                do_draft = None
            if do_draft is not None:
                base = do_draft.model_dump(mode="python")
                base["controllers"] = do_draft.controllers
                source = do_draft
                base_veio_do_rascunho = True
            else:
                base = source.model_dump(mode="python") if source else {}
        else:
            base = source.model_dump(mode="python") if source else {}
        # R-09 item 2: `model_dump` DENSIFICA — os defaults do schema saem
        # marcados como explícitos e o `model_fields_set` original se perde. Num
        # override por-controle parcial (ex.: só brilho), isso vira
        # `lightbar:[0,0,0]` e APAGA a lightbar daquele controle, além de matar
        # a herança do global para sempre. `draft_config.to_profile` já tem essa
        # guarda (reinjetar as INSTÂNCIAS validadas, que pydantic com
        # `revalidate_instances="never"` preserva); aqui faltava.
        if source is not None:
            base["controllers"] = source.controllers

        # FEAT-LED-BRIGHTNESS-03: brightness pendente do slider só é aplicado
        # quando o perfil-base NÃO tem brilho próprio. BUG-PROFILE-BRIGHTNESS-OVERWRITE-01:
        # antes sobrescrevia incondicionalmente com o global (default 1.0),
        # apagando o brilho persistido do perfil ao salvar pela aba Perfis.
        pending_brightness: float = getattr(self, "_pending_brightness", 1.0)
        leds_base: dict[str, Any] = dict(base.get("leds") or {})
        leds_base.setdefault("lightbar_brightness", pending_brightness)
        base["leds"] = leds_base

        # FEAT-PROFILE-MODE-GUI-01: a seção `mode` vem dos widgets do editor.
        # kind "none" (sem opinião) REMOVE a seção (mode=None). Sem a seção
        # montada (glade antigo), o mode do perfil-base sobrevive por herança,
        # como antes desta sprint.
        #
        # PERFIL-SALVA-TUDO-01: com uma exceção, do mesmo tamanho da do
        # SALVAR-NAO-REBAIXA-01 logo abaixo. O `mode` ganhou um segundo escritor
        # — a aba Emulação, por `DraftConfig.with_mode` — e o seletor daqui abre
        # com o valor do DISCO. Reescrever sempre significaria: ela liga o modo
        # jogo na aba Emulação, salva pela aba Perfis, e o modo evapora. Então o
        # editor só reescreve quando ELA mexeu no seletor nesta edição
        # (`_modo_tocado`) ou quando o rascunho não tem opinião pendente. A
        # exceção só vale com a base VINDA DO RASCUNHO: em perfil novo/duplicação
        # a base é o disco e o editor (inclusive o prefill do modo jogo) segue
        # sendo a fonte, como antes.
        if self._mode_kind_selector is not None:
            modo_do_rascunho_vence = (
                base_veio_do_rascunho
                and bool(getattr(draft, "mode_dirty", False))
                and not self._modo_tocado
            )
            if not modo_do_rascunho_vence:
                base["mode"] = self._mode_section_from_editor()

        # SALVAR-NAO-REBAIXA-01 (sprint 27/07): o `base.update` abaixo
        # sobrescrevia `match` e `priority` SEMPRE, com o que estivesse nos
        # widgets. Isso reduz todo salvamento a um rebaixamento silencioso do
        # que ela consertou fora da janela — evidência datada no disco dela:
        # `Pragmata` era regra de jogo com prioridade 100 em 26/07 às 23h40 e
        # amanheceu catch-all em 27/07 às 23h04; o `vitoria` caiu de 100 para 0.
        # O caminho é banal: a escala tinha teto 100 (uma prioridade 110 do
        # disco já abria clampada) e o editor simples mostra "Qualquer" para
        # todo match que ele não reconhece — salvar a cor pela aba Perfis
        # gravava de volta a leitura empobrecida da tela.
        #
        # Agora regra e prioridade só são reescritas quando ela MEXEU nelas
        # nesta edição. Mexer continua valendo na hora, e num perfil novo (sem
        # fotografia) nada muda: os widgets seguem sendo a fonte.
        #   — nota de 05/08: essa última frase CADUCOU pela metade. Vale quando
        #   o perfil novo estreia um arquivo; quando o Salvar vai por cima de um
        #   que EXISTE, a fotografia é relida logo abaixo e as guardas voltam a
        #   valer. Ver SALVAR-NAO-REBAIXA-02, a seguir.
        #
        # SALVAR-NAO-REBAIXA-02 (leva 2, 05/08): as guardas acima DESLIGAVAM
        # sozinhas. `on_profile_new` chama `_esquecer_a_fotografia_do_editor`, e
        # com as duas fotografias em `None` os dois `if` eram pulados e os
        # widgets venciam — inclusive quando o Salvar ia por cima de um arquivo
        # que EXISTE. Medido em 05/08: um perfil `prio=200, criteria` no disco
        # virava `prio=0, any`, que é o defeito de 27/07 de volta por outra
        # porta.
        #
        # A cura é de ESCOPO, não de remoção: esquecer a fotografia continua
        # certo (perfil que não existe não tem valor de disco a preservar), e o
        # que faltava era reler a fotografia NA HORA DE SALVAR, quando o alvo já
        # existe. Aí a única evidência de intenção é o GESTO dela — não há
        # assinatura de abertura para comparar, porque o editor nunca mostrou
        # este perfil.
        prioridade_do_disco = self._prioridade_do_disco
        regra_do_disco = self._regra_do_disco
        prioridade_mexida = self._prioridade_foi_mexida()
        regra_mexida = self._regra_foi_mexida()
        if prioridade_do_disco is None or regra_do_disco is None:
            alvo_no_disco = self._perfil_que_o_salvar_sobrescreve(name)
            if alvo_no_disco is not None:
                if prioridade_do_disco is None:
                    prioridade_do_disco = alvo_no_disco.priority
                    prioridade_mexida = self._prioridade_tocada
                if regra_do_disco is None:
                    regra_do_disco = alvo_no_disco.match
                    regra_mexida = self._regra_tocada
        prioridade_final = priority
        if prioridade_do_disco is not None and not prioridade_mexida:
            prioridade_final = int(prioridade_do_disco)
        regra_final = match
        if regra_do_disco is not None and not regra_mexida:
            regra_final = regra_do_disco

        base.update(
            {
                "name": name,
                "priority": prioridade_final,
                "match": regra_final.model_dump(mode="python"),
            }
        )
        return Profile.model_validate(base)

    @staticmethod
    def _split_csv(raw: str) -> list[str]:
        return [item.strip() for item in raw.split(",") if item.strip()]

    @staticmethod
    def _humanize_profile_error(exc: Exception) -> str:
        """Traduz erros de validação do perfil para frase de gente (COR-D).

        O ``str`` de uma ``ValidationError`` do pydantic traz o nome do campo
        interno e uma URL de documentação — ilegível no rodapé de uma linha.
        Mapeia os casos comuns; só cai no texto genérico quando não reconhece.
        """
        text = str(exc)
        # R-12 item 2: as frases do editor simples já são para gente — traduzi-las
        # de novo viraria o genérico "Revise os campos", que não diz O QUE falta.
        if text in MENSAGENS_DE_GENTE:
            return text
        if "name não pode ser vazio" in text:
            return "Dê um nome ao perfil."
        if "caractere inválido" in text:
            return "O nome não pode ter barra ( / ) nem dois pontos ( .. )."
        if "não produz slug válido" in text:
            return "Use letras ou números no nome do perfil."
        return "Não foi possível salvar. Revise os campos do perfil."

    def _toast_profile(self, msg: str) -> None:
        self._status_toast("profiles", msg)
