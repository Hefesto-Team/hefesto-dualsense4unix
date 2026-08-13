"""Presets de match humanamente legíveis para o editor simples de perfis.

Cada chave de SIMPLE_MATCH_PRESETS mapeia um radio de "Aplica a" em MatchCriteria
ou MatchAny concreto. Helper `from_simple_choice` traduz a seleção do usuário.

R-12 (auditoria 23/07): o editor simples não tinha como dizer "este perfil é
DESTE jogo da Steam" — a única opção com alvo próprio era "Jogo específico", que
grava ``process_name`` (o basename do executável). Para jogo Proton o basename é
o binário do wine, e sob XWayland a única chave confiável do jogo é a
``wm_class`` ``steam_app_<appid>`` — que também é a chave do ``.env`` por appid
do launch_env. Daí a opção "steam_game".
"""
from __future__ import annotations

from hefesto_dualsense4unix.profiles.schema import Match, MatchAny, MatchCriteria
from hefesto_dualsense4unix.profiles.steam_app import (
    steam_appid_de_texto,
    steam_appid_from_wm_class,
)

# R-12 item 2 (auditoria 23/07): campo obrigatório em branco NÃO degrada em
# silêncio. Antes, "Jogo específico" sem nome devolvia `MatchAny()` — o perfil
# que ela criou PARA UM JOGO nascia valendo para TUDO, entrava na disputa com os
# catch-all (R-01) e o toast dizia "Perfil salvo". As frases moram aqui porque
# são contrato com a GUI: `_humanize_profile_error` as repassa inteiras em vez
# de traduzir para o texto genérico "Revise os campos do perfil".
MSG_JOGO_SEM_NOME = (
    "Diga o nome do programa do jogo (ex.: eldenring) ou escolha outro "
    "contexto em \"Aplica a\"."
)
MSG_STEAM_SEM_APPID = (
    "Diga o número do jogo na Steam (ex.: 1599660). Com o jogo aberto, o "
    "campo é preenchido sozinho."
)
MSG_STEAM_APPID_INVALIDO = (
    "O número do jogo na Steam é só dígitos (ex.: 1599660). Cole o endereço "
    "da página do jogo na loja e o número sai dele sozinho."
)

#: Frases que a GUI pode mostrar CRUAS para a usuária (ver `_humanize_profile_error`).
MENSAGENS_DE_GENTE: frozenset[str] = frozenset(
    {MSG_JOGO_SEM_NOME, MSG_STEAM_SEM_APPID, MSG_STEAM_APPID_INVALIDO}
)

# Presets prontos, indexados pela chave do radio.
SIMPLE_MATCH_PRESETS: dict[str, MatchCriteria | MatchAny] = {
    "any": MatchAny(),
    "steam": MatchCriteria(process_name=["steam"]),
    "browser": MatchCriteria(
        window_class=["firefox", "chromium", "brave", "google-chrome"]
    ),
    "terminal": MatchCriteria(
        window_class=["gnome-terminal", "alacritty", "kitty", "konsole"]
    ),
    "editor": MatchCriteria(window_class=["code", "zed", "neovide"]),
}


def normalize_appid(raw: str | None) -> str | None:
    """Extrai o appid de ``1599660`` / ``steam_app_1599660`` / ``  1599660 ``.

    Devolve ``None`` quando não há nada aproveitável — quem decide se isso é
    erro é o chamador (o editor levanta; a detecção do round-trip só ignora).

    13/08/2026: passou a aceitar também o ENDEREÇO da loja e o
    ``steam://rungameid/<id>``, delegando a `steam_app.steam_appid_de_texto`.
    Delegar, e não repetir o regex aqui, é o que faz o caminho do **Salvar**
    aceitar o endereço mesmo quando a janela não chegou a reescrever o campo —
    e é a disciplina que UNIFICA-PREDICADO-01 deixou escrita: a pergunta "que
    appid é este texto?" tem um dono só.
    """
    appid = steam_appid_de_texto(raw)
    return None if appid is None else str(appid)


def from_simple_choice(
    choice: str,
    custom_name: str | None = None,
    regra_do_disco: Match | None = None,
) -> MatchCriteria | MatchAny:
    """Converte escolha do radio "Aplica a" em MatchCriteria ou MatchAny.

    ``regra_do_disco`` é a regra que este Salvar vai sobrescrever, e existe só
    para o "steam_game": a página simples tem um campo (o número do jogo) e o
    perfil no disco pode ter também um ``process_name`` do MESMO jogo, que ela
    nunca viu na tela e portanto nunca pediu para tirar
    (ESCONDER-EM-VEZ-DE-SAIR-01; ver `_process_name_a_preservar`). Omitir o
    parâmetro é o comportamento histórico — nada a preservar.

    Regras:
    - "steam_game" + appid    → MatchCriteria(window_class=["steam_app_<id>"])
    - "steam_game" sem appid  → ValueError (frase de gente)
    - "game" + custom_name    → MatchCriteria(process_name=[custom_name])
    - "game" sem custom_name  → ValueError (frase de gente)
    - qualquer outra chave de SIMPLE_MATCH_PRESETS → preset correspondente
    - chave desconhecida               → MatchAny()

    R-12 item 3: o nome do programa é gravado **como ela digitou**. Antes vinha
    um ``.lower()`` aqui, e o casamento do outro lado
    (``MatchCriteria.matches``) compara com o basename CRU de ``/proc/PID/exe``
    — ``Cyberpunk2077.exe`` nunca casaria com ``cyberpunk2077.exe``. Os presets
    de fábrica (``fps.json``, ``acao.json``…) já gravam o basename com as
    maiúsculas originais; o helper é que estava corrompendo o dado. A cura
    completa (comparar sem diferenciar maiúsculas) mora no matcher do schema e
    não neste módulo.
    """
    if choice == "steam_game":
        appid = normalize_appid(custom_name)
        if appid is None:
            if custom_name and custom_name.strip():
                raise ValueError(MSG_STEAM_APPID_INVALIDO)
            raise ValueError(MSG_STEAM_SEM_APPID)
        return MatchCriteria(
            window_class=[f"steam_app_{appid}"],
            process_name=_process_name_a_preservar(regra_do_disco, appid),
        )
    if choice == "game":
        if custom_name and custom_name.strip():
            return MatchCriteria(process_name=[custom_name.strip()])
        raise ValueError(MSG_JOGO_SEM_NOME)
    return SIMPLE_MATCH_PRESETS.get(choice, MatchAny())


def detect_simple_preset(
    match: Match,
) -> str | None:
    """Detecta se match corresponde a algum preset simples.

    Retorna a chave do preset (ex.: "steam", "browser") ou None se nenhum bater.
    Para "game", retorna ("game", process_name[0]); empacota com `_detect_game`.
    Para "steam_game", o valor de acompanhamento é o appid (ver `simple_extra`).
    Uso interno: profiles_actions._populate_editor_v2.

    LEITURA É TOLERANTE (risco de regressão anotado no plano): um perfil já
    salvo com critério vazio continua carregando — só devolve ``None`` e cai no
    editor avançado. Quem recusa é a ESCRITA (`from_simple_choice`).

    ``MatchManual`` (R-12 item 3) também cai em ``None``: o seletor "Aplica a"
    não tem — nem deve ter — um botão para "nunca". O perfil manual abre no
    editor avançado com os três campos vazios, que é exatamente a forma que o
    `_build_profile_from_editor` volta a gravar como manual; o round-trip
    fecha sem inventar alvo nenhum.
    """
    if isinstance(match, MatchAny):
        return "any"
    # R-12 item 3: qualquer sentinel sem campos de critério (hoje
    # `MatchManual`) sai aqui. Sem esta guarda o laço abaixo chamaria
    # `_criteria_equal`, que lê `window_class`/`process_name` do objeto e
    # estouraria com AttributeError ao abrir o perfil na aba Perfis.
    if not isinstance(match, MatchCriteria):
        return None
    # R-12: jogo da Steam ANTES dos presets fixos — `steam_app_<id>` é um
    # window_class como outro qualquer, e sem esta checagem o round-trip
    # (salvar → reabrir) jogaria o perfil no editor avançado.
    if _detect_steam_appid(match) is not None:
        return "steam_game"
    for key, preset in SIMPLE_MATCH_PRESETS.items():
        if key == "any":
            continue
        if isinstance(preset, MatchCriteria) and _criteria_equal(match, preset):
            return key
    # Tenta detectar "jogo específico": process_name com 1 elemento, demais vazios
    if (
        isinstance(match, MatchCriteria)
        and len(match.process_name) == 1
        and not match.window_class
        and not match.window_title_regex
    ):
        return "game"
    return None


def simple_extra(match: Match) -> str:
    """Texto que acompanha o preset detectado no campo livre do editor.

    "game" → o nome do programa; "steam_game" → o appid; o resto → "".
    Existe para o `_populate_editor` não repetir a lógica de extração (e não
    voltar a mostrar ``steam_app_1599660`` num campo que pede o número).
    """
    appid = _detect_steam_appid(match)
    if appid is not None:
        return appid
    if (
        isinstance(match, MatchCriteria)
        and len(match.process_name) == 1
        and not match.window_class
        and not match.window_title_regex
    ):
        return match.process_name[0]
    return ""


def _detect_steam_appid(match: Match) -> str | None:
    """Appid quando o match é "um jogo da Steam", senão None.

    Exige window_class com um único ``steam_app_<id>`` e NENHUM
    ``window_title_regex``: ``MatchCriteria.matches`` é AND entre campos
    preenchidos, então um regex de título junto ESTREITA o perfil para um
    subconjunto das janelas daquele jogo (uma tela, um mapa, um título
    traduzido). O editor simples não tem como exprimir esse recorte, e mostrar
    o perfil como "Jogo da Steam <id>" seria mentir sobre o que ele faz.

    NOTA DATADA — 10/08/2026 (ESCONDER-EM-VEZ-DE-SAIR-01, relatado por ela:
    *"sumiu a opção de entregar o controle pra Steam? pq ela é que impedia o
    dual input em jogos como pragmata"*). A regra estrita também recusava
    ``process_name``, e ESSA metade caducou. O parágrafo acima continua
    valendo inteiro para ``window_title_regex``.

    Por que ``process_name`` é diferente — e é MEDIDO, não deduzido:

    1. Ele designa o MESMO jogo que a ``steam_app_<id>``, não um segundo alvo.
       Trocar "3357650 E PRAGMATA.exe" por "Jogo da Steam 3357650" na tela não
       muda a resposta a *de qual jogo é este perfil*, que é a única pergunta
       que o seletor "Aplica a" faz.
    2. A precisão que a recusa dizia proteger não existia. No journal dela de
       10/08, com a janela ``steam_app_3357650`` em foco, o daemon registrou
       ``profile_select_catch_all_sem_autoridade_em_jogo candidatos=['fallback']``
       — o perfil ``Pragmata`` NÃO era candidato ao próprio jogo. Sob Proton o
       basename de ``/proc/PID/exe`` é o binário do wine, nunca ``PRAGMATA.exe``
       (é a razão de "steam_game" existir; ver o cabeçalho deste módulo), então
       o AND com ``process_name`` não estreita o casamento: ele o ANULA.
    3. O preço da recusa era a janela. Com ``detect_simple_preset`` devolvendo
       ``None``, o perfil abria no editor avançado com o seletor rebaixado a
       "Vale sempre", e a caixinha "Esconder o controle físico neste jogo" só
       nasce com "Jogo da Steam" escolhido
       (``profiles_actions._mostrar_caixa_do_steam_input``). O único gesto que
       ela tinha para desfazer a duplicação de controle sumia da tela.

    Reconhecer NÃO é apagar: ``from_simple_choice`` preserva o ``process_name``
    do disco quando o appid não mudou (ver ``_process_name_a_preservar``). Sem
    isso, reabrir e salvar tiraria da regra dela um campo que ela não pediu
    para tirar — que é exatamente o round-trip quebrado de onde o R-12 nasceu.

    UNIFICA-PREDICADO-01: o reconhecimento vem da fonte única
    (`profiles/steam_app.py`), que já absorveu o ``.strip()`` daqui. O
    alargamento para caixa é a cura de uma mentira do editor: um perfil salvo
    com ``Steam_App_2111190`` CASA com o jogo (o matcher compara sem caixa) e
    abria no editor AVANÇADO, como se não fosse perfil de jogo da Steam — e
    ``simple_extra`` devolvia "" no campo que pede o número. A conversão para
    `str` é do callsite: a fonte devolve `int` e a GUI escreve texto no campo.
    """
    if not isinstance(match, MatchCriteria):
        return None
    if len(match.window_class) != 1 or match.window_title_regex:
        return None
    appid = steam_appid_from_wm_class(match.window_class[0])
    return None if appid is None else str(appid)


def _process_name_a_preservar(regra_do_disco: Match | None, appid: str) -> list[str]:
    """O ``process_name`` que o editor simples não mostra, mas não pode apagar.

    ESCONDER-EM-VEZ-DE-SAIR-01 (10/08/2026). ``_detect_steam_appid`` passou a
    reconhecer o jogo da Steam mesmo com ``process_name`` junto — e a página
    simples tem UM campo, o do número. Sem esta preservação, reabrir o perfil
    ``Pragmata`` dela e salvar gravaria ``window_class`` sozinho: o
    ``PRAGMATA.exe`` evaporaria porque a tela não tinha onde mostrá-lo, que é
    o mesmo defeito de round-trip que o R-12 catalogou.

    **Só do MESMO jogo.** Se ela digitar outro appid no campo, o perfil passou
    a ser de OUTRO jogo, e carregar junto o nome do programa do jogo anterior
    seria pior que apagar: o perfil novo nasceria com um AND que nunca casa,
    sem nada na tela dizendo por quê. Regra de disco que não é jogo da Steam
    (ou ausente) também não empresta nada.
    """
    if regra_do_disco is None:
        return []
    if _detect_steam_appid(regra_do_disco) != appid:
        return []
    return list(getattr(regra_do_disco, "process_name", None) or [])


def _criteria_equal(a: MatchCriteria, b: MatchCriteria) -> bool:
    """Compara dois MatchCriteria por igualdade de campos."""
    return (
        sorted(a.window_class) == sorted(b.window_class)
        and a.window_title_regex == b.window_title_regex
        and sorted(a.process_name) == sorted(b.process_name)
    )


def exigencia_invisivel(match: Match) -> str:
    """O que o perfil exige e a página SIMPLES não mostra. "" = nada escondido.

    A-REGRA-QUE-A-TELA-NAO-MOSTRA-01 (10/08/2026), e nasceu de uma foto dela.

    O editor simples do "Jogo da Steam" tem um campo só — o número. O
    `from_simple_choice` PRESERVA um `process_name` que já esteja no disco, e
    isso é certo: salvar pela janela não pode apagar o que a tela não mostra
    (ESCONDER-EM-VEZ-DE-SAIR-01). O que estava errado era o silêncio em volta.

    Na foto do editor dela, o perfil "Pragmata" aparecia assim:

        Aplica a: [Jogo da Steam]   Nome do jogo: 3357650

    e no arquivo estava `process_name: ["PRAGMATA.exe"]`. O `matches` é AND, e o
    campo invisível é o que decidia — o perfil não entrava sozinho, medido seis
    vezes num intervalo de dois minutos com ela jogando. A tela mostrava uma
    regra que não era a regra.

    Preservar o invisível continua certo. Esconder que ele EXISTE é que não.

    A frase é factual e não manda apagar nada: quem escreveu o critério foi ela,
    e a decisão de mudá-lo é dela. Diz o que há e onde mexer.
    """
    if not isinstance(match, MatchCriteria):
        return ""
    if _detect_steam_appid(match) is None:
        return ""
    partes: list[str] = []
    if match.process_name:
        nomes = ", ".join(f'"{n}"' for n in match.process_name)
        partes.append(f"nome do processo {nomes}")
    if match.window_title_regex:
        partes.append(f'título da janela "{match.window_title_regex}"')
    if not partes:
        return ""
    return (
        f"Este perfil também exige {' e '.join(partes)}, e só entra quando isso "
        "bater junto com o número do jogo. Ligue o Modo avançado para ver e "
        "mudar."
    )
