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

from collections.abc import Callable, Iterable

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
#: A IRMÃ DO `MSG_JOGO_SEM_NOME`, e ela nasceu com a sexta forma (ONDA5-10-01,
#: 06/09/2026). O "janela" tem UM campo obrigatório — a classe da janela do
#: jogo —, e vazio ele degradaria em `MatchCriteria(window_class=[""])`, que é
#: um critério que nunca casa e não diz por quê. É o mesmo R-12 item 2.
MSG_JANELA_SEM_CLASSE = (
    "Diga a janela do jogo (ex.: GrimFandango) ou escolha outro contexto em "
    "\"Funciona em\". Com o jogo em foco, o botão Detectar preenche sozinho."
)

#: A TERCEIRA IRMÃ, e ela nasceu com «de onde o jogo vem» (C4-FUNCIONA-EM,
#: 11/09/2026). Trocar a procedência para um lançador enquanto o campo de baixo
#: guarda um jogo de OUTRO lugar é uma frase pela metade: o endereço que está
#: lá não vale naquele lançador, e gravá-lo assim mesmo faria nascer uma regra
#: que nunca casa — o R-12, de novo.
#:
#: **ELA MANDA PARA A LISTA, e não para a linha de comando.** O caminho existe
#: e está a um campo de distância: escolhido o lançador, o campo de baixo passa
#: a oferecer os jogos DELE pelo nome, e escolher um grava a regra inteira.
#:
#: FORA DE `MENSAGENS_DE_GENTE` de propósito: aquele conjunto é comparado por
#: igualdade EXATA, e um molde com `{procedencia}` dentro nunca casaria — ele
#: entraria como uma linha morta que dá a impressão de cobrir o caso. Quem a
#: levanta é a aba, que já mostra a frase crua na tarja.
MSG_ESCOLHA_O_JOGO = (
    "Escolha o jogo na lista de baixo — “{procedencia}” mostra os jogos que "
    "vêm de lá pelo nome."
)

#: Frases que a GUI pode mostrar CRUAS para a usuária (ver `_humanize_profile_error`).
MENSAGENS_DE_GENTE: frozenset[str] = frozenset(
    {MSG_JOGO_SEM_NOME, MSG_STEAM_SEM_APPID, MSG_STEAM_APPID_INVALIDO,
     MSG_JANELA_SEM_CLASSE}
)

# --- Os três botões de programa, e por que a lista cresceu ------------------
# PERFIS-ABRE-O-QUE-GUARDA-01/P5 (25/08/2026). As três listas tinham DOZE
# programas ao todo, e eram os programas DESTA BANCADA em julho. O preço não
# era teórico: quem instalasse outro terminal, clicasse "Terminal" e salvasse
# ganhava um perfil que **nunca casa**, sem uma palavra na tela — o perfil não
# entra, `matches()` devolve `False` em silêncio, e não há erro nenhum a ler.
#
# Medido em 25/08, antes de qualquer linha de cura, com o `matches()` do
# esquema: `ptyxis` (o terminal padrão do COSMIC, que é o desktop DESTA
# máquina), `foot`, `wezterm`, `xterm`, `vivaldi`, `zen`, `org.gnome.Epiphany`,
# `gedit`, `org.kde.kate`, `emacs` e `vim` — os ONZE reprovavam.
#
# **Lista declarada, nunca detecção mágica.** Adivinhar "isto é um editor" pelo
# nome do processo é a classe de contorno que esta casa recusa: acerta na
# bancada de quem escreveu e erra no computador de quem usa, sem jeito de a
# pessoa ver por quê. Aqui é lista, com dono e com data.
#
# A comparação é SEM CAIXA (`schema._casa_sem_caixa`), então cada programa
# aparece uma vez só — `Navigator` e `navigator` são a mesma entrada. O que
# muda de verdade entre as grafias é o SUFIXO do empacotamento
# (`chromium-browser`, `brave-browser`) e o identificador em ponto do Wayland
# (`org.gnome.Epiphany`), e esses são nomes diferentes, não caixas diferentes.

#: Navegadores. `Navigator` é a `wm_class` do Firefox sob XWayland — a mesma
#: janela chega como `firefox` no Wayland nativo e como `Navigator` no X, e sem
#: as duas o preset cobre metade das sessões.
_NAVEGADORES = [
    "firefox",
    "Navigator",
    "librewolf",
    "waterfox",
    "zen",
    "zen-alpha",
    "chromium",
    "chromium-browser",
    "brave",
    "brave-browser",
    "google-chrome",
    "google-chrome-stable",
    "vivaldi",
    "vivaldi-stable",
    "microsoft-edge",
    "opera",
    "falkon",
    "org.gnome.Epiphany",
    "epiphany",
    "qutebrowser",
    "org.qutebrowser.qutebrowser",
]

#: Terminais. `ptyxis` encabeça por medição, não por gosto: é o terminal padrão
#: do COSMIC, o desktop desta máquina, e era o buraco mais caro dos três.
#: `gnome-terminal-server` é o processo que carrega as janelas do
#: `gnome-terminal` — quem some da lista some da detecção.
_TERMINAIS = [
    "ptyxis",
    "org.gnome.Ptyxis",
    "gnome-terminal",
    "gnome-terminal-server",
    "org.gnome.Terminal",
    "alacritty",
    "org.alacritty.Alacritty",
    "kitty",
    "konsole",
    "org.kde.konsole",
    "foot",
    "footclient",
    "wezterm",
    "org.wezfurlong.wezterm",
    "xterm",
    "urxvt",
    "st",
    "terminator",
    "tilix",
    "xfce4-terminal",
    "io.elementary.terminal",
    "org.contourterminal.Contour",
]

#: Editores — de código e de texto. O critério de entrada é "programa em que se
#: escreve", não "IDE": `gedit` e `kate` são o editor de muita gente, e deixá-los
#: de fora era a mesma omissão do `ptyxis`.
_EDITORES = [
    "code",
    "code-oss",
    "vscodium",
    "cursor",
    "zed",
    "dev.zed.Zed",
    "neovide",
    "nvim",
    "vim",
    "gvim",
    "emacs",
    "gedit",
    "org.gnome.gedit",
    "org.gnome.TextEditor",
    "kate",
    "org.kde.kate",
    "kwrite",
    "sublime_text",
    "org.gnome.Builder",
    "jetbrains-idea",
    "jetbrains-idea-ce",
    "jetbrains-pycharm",
    "jetbrains-pycharm-ce",
    "jetbrains-clion",
    "jetbrains-rider",
    "jetbrains-webstorm",
]

# Presets prontos, indexados pela chave do radio.
SIMPLE_MATCH_PRESETS: dict[str, MatchCriteria | MatchAny] = {
    "any": MatchAny(),
    "steam": MatchCriteria(process_name=["steam"]),
    "browser": MatchCriteria(window_class=list(_NAVEGADORES)),
    "terminal": MatchCriteria(window_class=list(_TERMINAIS)),
    "editor": MatchCriteria(window_class=list(_EDITORES)),
}

#: As listas de ANTES de 25/08/2026, guardadas para a LEITURA continuar
#: reconhecendo o que já está no disco.
#:
#: Sem isto, crescer as listas quebraria o round-trip que o R-12 existe para
#: proteger: um perfil salvo em julho com "Terminal" tem os quatro nomes
#: daquele dia gravados, `_criteria_equal` compara por igualdade EXATA de
#: conjunto, e reabrir o perfil o jogaria no editor avançado — o seletor
#: rebaixado, sem ninguém ter mexido em nada. É o mesmo defeito que a
#: `ESCONDER-EM-VEZ-DE-SAIR-01` mediu pelo outro lado.
#:
#: **Só a LEITURA é tolerante.** A escrita (`from_simple_choice`) grava sempre
#: a lista de hoje: reabrir um "Terminal" de julho e salvar ALARGA o perfil
#: para os terminais de hoje, que é exatamente o que o rótulo "Terminal"
#: promete — e alargar nunca tira dela um casamento que ela já tinha.
_PRESETS_HISTORICOS: dict[str, tuple[list[str], ...]] = {
    "browser": (["firefox", "chromium", "brave", "google-chrome"],),
    "terminal": (["gnome-terminal", "alacritty", "kitty", "konsole"],),
    "editor": (["code", "zed", "neovide"],),
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
    - "janela" + custom_name  → MatchCriteria(window_class=[custom_name])
    - "janela" sem custom_name → ValueError (frase de gente)
    - qualquer outra chave de SIMPLE_MATCH_PRESETS → preset correspondente
    - chave desconhecida               → MatchAny()

    A SEXTA FORMA — "janela", ONDA5-10-01 (06/09/2026). O detector de janela do
    daemon entrega uma ``wm_class`` (``window_detect_last_class``), e até aqui o
    produto só sabia guardá-la quando ela era um ``steam_app_<id>``. Para jogo
    de fora da Steam o botão "Detectar" RECUSAVA — e mandava a pessoa para a
    linha de comando, que é o defeito que esta sprint fechou. **Se gravar a
    regra empurra o perfil para fora da tela, o conserto é a tela aprender a
    regra, não o botão desistir.**

    POR QUE O NOME É "janela": é o que o dado É. "app"/"programa" colidiria com
    o ``"game"``, que é OUTRO campo do esquema (``process_name``, o basename de
    ``/proc/PID/exe``) — e confundir os dois faz o perfil casar por acaso.

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
    if choice == "janela":
        # A CLASSE VAI COMO ELA VEIO, sem `.lower()`, pela MESMA razão do
        # "game" (R-12 item 3): `MatchCriteria.matches` compara com a
        # `wm_class` crua do detector, e `GrimFandango` não é `grimfandango`.
        # O matcher do esquema é que compara sem caixa — não este helper.
        if custom_name and custom_name.strip():
            return MatchCriteria(window_class=[custom_name.strip()])
        raise ValueError(MSG_JANELA_SEM_CLASSE)
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
    # P5 (25/08/2026): e as listas de ANTES, para o perfil que já está no disco
    # continuar abrindo na página simples. Ver `_PRESETS_HISTORICOS`.
    historico = _preset_historico(match)
    if historico is not None:
        return historico
    # Tenta detectar "jogo específico": process_name com 1 elemento, demais vazios
    if (
        isinstance(match, MatchCriteria)
        and len(match.process_name) == 1
        and not match.window_class
        and not match.window_title_regex
    ):
        return "game"
    # A SEXTA FORMA — "janela", ONDA5-10-01 (06/09/2026). O ESPELHO do "game"
    # logo acima: uma classe de janela SÓ, sem nome de programa e sem título.
    #
    # ELA VEM DEPOIS DE TUDO, e a ordem é o contrato:
    #   * `_detect_steam_appid` já correu lá em cima — um `steam_app_<id>` é um
    #     `window_class` de UM elemento, e tem de continuar saindo como
    #     "steam_game" ou o round-trip do R-12 quebra;
    #   * os presets fixos e os `_PRESETS_HISTORICOS` também já correram — um
    #     "Terminal" de julho com uma classe só continuaria sendo "Terminal".
    #     (Hoje nenhum deles tem lista de um elemento; a ordem é que garante.)
    if (
        isinstance(match, MatchCriteria)
        and len(match.window_class) == 1
        and not match.process_name
        and not match.window_title_regex
    ):
        return "janela"
    return None


def simple_extra(match: Match) -> str:
    """Texto que acompanha o preset detectado no campo livre do editor.

    "game" → o nome do programa; "steam_game" → o appid; "janela" → a classe
    da janela; o resto → "".
    Existe para o `_populate_editor` não repetir a lógica de extração (e não
    voltar a mostrar ``steam_app_1599660`` num campo que pede o número).

    A ORDEM É A DE `detect_simple_preset`, e tem de continuar sendo: o appid
    primeiro (um `steam_app_<id>` é `window_class` de um elemento), o
    `process_name` depois, a classe por último.
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
    if (
        isinstance(match, MatchCriteria)
        and len(match.window_class) == 1
        and not match.process_name
        and not match.window_title_regex
    ):
        return match.window_class[0]
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


def _preset_historico(match: MatchCriteria) -> str | None:
    """A chave do preset quando o perfil guarda uma lista ANTIGA. Senão None.

    P5 (25/08/2026). Ver `_PRESETS_HISTORICOS` para o porquê: crescer as três
    listas sem isto rebaixaria para o editor avançado todo perfil "Navegador",
    "Terminal" ou "Editor" que ela já tem no disco — sem ninguém ter mexido em
    nada, e sem uma palavra na tela.

    A comparação é a MESMA do laço dos presets de hoje (`_criteria_equal`, por
    conjunto), e por isso um perfil histórico só é reconhecido quando os
    OUTROS campos também batem: `process_name` e `window_title_regex` vazios.
    Um "Terminal" de julho com um `process_name` somado à mão continua caindo
    no editor avançado — que é o certo, porque a página simples não sabe
    mostrar esse campo (é a mesma disciplina do `exigencia_invisivel`).
    """
    for key, listas in _PRESETS_HISTORICOS.items():
        for window_class in listas:
            if _criteria_equal(match, MatchCriteria(window_class=list(window_class))):
                return key
    return None


#: O CAMINHO DA JANELA GTK, e ele mora aqui por um motivo só: é a janela cujo
#: botão tem este nome, e a constante precisa de UM dono para a régua da aba 10
#: poder cobrar a troca. Quem a CONCATENA é `profiles_actions`, não esta função
#: — uma tela sem "Modo avançado" nunca a vê.
CAMINHO_DA_JANELA_GTK = "Ligue o Modo avançado para ver e mudar."


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
    e a decisão de mudá-lo é dela. Diz o que há.

    **ELA DIZIA "ONDE MEXER", E ISSO SAIU EM 05/09/2026.** O fim da frase era
    *"Ligue o Modo avançado para ver e mudar."* — e o "Modo avançado" é uma
    peça da JANELA GTK, um interruptor do `main.glade`. Um matcher de
    `profiles/` não pode nomear um botão de uma tela: quando nasceu a interface
    nova, que não tem esse interruptor, a frase passou a mandar a pessoa a um
    lugar que não existe, e a aba 10 teve de REMENDÁ-LA na saída — trocando o
    fim exato por outro, com uma régua guardando a troca.

    A REPARTIÇÃO É A ÓBVIA, e é a que o relatório daquela frente pediu: o FATO
    mora aqui, porque é do critério; o CAMINHO mora em cada tela, porque só ela
    sabe que botões desenhou. Ver
    :data:`CAMINHO_DA_JANELA_GTK`, e o `FIM_DA_EXIGENCIA_AQUI` da aba 10.
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
        "bater junto com o número do jogo."
    )


# --- AS PROCEDÊNCIAS — «de onde o jogo vem», e as seis formas que isso vira ---
#
# C4-FUNCIONA-EM, 11/09/2026. Desenho DELA, confirmado com todas as letras
# (*"isso mesmo."*), e a ordem original foi esta:
#
#     "seria legal nome do programa launcher aqui: A gente adicionaria  (noqa-acento) cita ela
#      Navegação, remopve jogo da steam, jogo, jogo pela janela, estilo de
#      jogo, e colocariamos os launchers. Isso deveria ajudar a identificar
#      mais rápido o nome do jogo depois"
#
# **O QUE ELA MANDOU TIRAR ERA JARGÃO DE IMPLEMENTAÇÃO NA CARA DE QUEM JOGA.**
# "Jogo" contra "Jogo pela janela" pedia dela exatamente o conhecimento que o
# produto tem e ela não: por qual chave aquele jogo é reconhecível — o
# `process_name` (basename de `/proc/PID/exe`) ou a `wm_class`. A pergunta que
# ela SABE responder é outra: *de onde vem este jogo?*
#
# **A REGRA QUE ISSO IMPÕE, e é o §4 da sprint:** a tela ganha uma tradução; o
# `MatchCriteria` NÃO MUDA. «lançador» não vira um tipo novo de casamento no
# disco — quem escolhe a forma técnica é o produto, aqui, com o que o lançador
# entrega. O arquivo continua guardando `steam_app_1245620` ou `gotg.exe`.
#
# **E ESTAS FUNÇÕES NÃO IMPORTAM `integrations`, de propósito.** Quem sabe que
# lançadores a máquina tem é o censo, e quem sabe de qual deles vem uma chave é
# o catálogo — os dois são leitura de disco, e `profiles/` é o esquema. A ponte
# é o parâmetro `lancador_da_chave`: a TELA passa a função, este módulo decide a
# forma. Sem isso, uma régua daqui precisaria da biblioteca dela para rodar.

#: O perfil do desktop, sem jogo. **Atrás dele está o preset `browser`** — a
#: lista declarada de navegadores de `_NAVEGADORES`, que existia no produto e
#: não no desenho dela (`perfis_web.FORA_DO_DESENHO`). Esta sprint o traz para
#: a tela com a palavra DELA, e é por isso que ela é a primeira da lista: não é
#: procedência de jogo nenhum, é o que vale quando não há jogo.
PROCEDENCIA_DA_NAVEGACAO = "Navegação"

#: O catch-all — `MatchAny`. Última da lista pela mesma razão que o `fallback`
#: tem prioridade zero: ele só entra quando nenhum outro serve.
PROCEDENCIA_DE_QUALQUER_JOGO = "Qualquer jogo"

#: A Steam. **Ela não vem do censo dos lançadores** (`censo_dos_lancadores` lê
#: os CINCO que não são a Steam): quem responde por ela é o
#: `jogos_locais.jogos_da_biblioteca_steam`. Para esta tradução isso é
#: indiferente — o que chega aqui é o NOME, e a Steam é o único nome que tem
#: duas formas atrás (ver `forma_da_procedencia`).
PROCEDENCIA_DA_STEAM = "Steam"

#: As duas que NÃO são lançador e existem em toda máquina — inclusive numa
#: recém-instalada, sem Steam, sem Heroic e sem Lutris. É a ordem dela de
#: 11/09/2026: *"a ideia é que todas as features mesmo do app funcionem  (noqa-acento)
#: nao so pra mim mas pra qualquer outro user"*.  (noqa-acento) cita ela
_FORMA_FIXA: dict[str, str] = {
    PROCEDENCIA_DA_NAVEGACAO: "browser",
    PROCEDENCIA_DE_QUALQUER_JOGO: "any",
}

#: O CAMINHO DE VOLTA das duas fixas — a inversão de `_FORMA_FIXA`, e não uma
#: segunda tabela.
_FIXA_DO_PRESET: dict[str, str] = {v: k for k, v in _FORMA_FIXA.items()}


def forma_da_procedencia(
    procedencia: str,
    jogo: str = "",
    *,
    forma_do_catalogo: str = "",
) -> str:
    """A chave de `from_simple_choice` que ESTA procedência pede. É o §4.

    As quatro respostas, e cada uma tem razão medida:

    * **«Navegação»** → ``browser``. O preset dos navegadores, que já existia.
    * **«Qualquer jogo»** → ``any``.
    * **«Steam»** → ``steam_game`` com jogo, ``steam`` sem. **As duas formas
      continuam alcançáveis, e isso não é esperteza — é a única saída que não
      perde uma.** A Steam é o único nome deste campo com DOIS significados no
      disco: o CLIENTE aberto (``process_name=["steam"]``) e UM JOGO dela
      (``steam_app_<id>``). Mapear «Steam» só para o jogo faria todo perfil do
      cliente abrir travado; só para o cliente faria o campo de baixo não
      valer nada. Quem separa os dois é o campo de baixo estar cheio, que é
      exatamente a pergunta *"é um jogo da Steam ou é a Steam?"*.
    * **um lançador** (Heroic, Lutris, RetroArch, «Instalado aqui»…) → o que o
      CATÁLOGO daquele jogo declarar (`jogos_locais.JogoLocal.forma`), e
      ``janela`` quando ele não está no catálogo. **Nunca ``game``**: o que
      esses lançadores entregam é a `wm_class` (o basename do
      ``install.executable`` do Heroic, do ``executable`` do `pga.db` do
      Lutris), e gravá-la como ``process_name`` é o defeito que
      `_forma_do_que_ela_escolheu` mediu na tela viva em 10/09/2026 — outro
      dado, que casa por acaso.

    **ELA NÃO LEVANTA, e a recusa continua sendo de `from_simple_choice`.** As
    frases de gente já estão escritas lá (`MSG_STEAM_SEM_APPID`,
    `MSG_JANELA_SEM_CLASSE`), e duplicá-las aqui seria a segunda verdade sobre
    o que falta no campo.
    """
    fixa = _FORMA_FIXA.get(procedencia)
    if fixa is not None:
        return fixa
    if procedencia == PROCEDENCIA_DA_STEAM:
        return "steam_game" if jogo.strip() else "steam"
    return forma_do_catalogo or "janela"


def procedencia_do_match(
    match: Match | None,
    lancador_da_chave: Callable[[str], str] | None = None,
) -> str | None:
    """De onde vem o jogo deste perfil — ou ``None``, e aí a tela não sabe.

    É o CAMINHO DE VOLTA de `forma_da_procedencia`, e o ``None`` é o estado
    honesto que o produto já tinha: `perfis_web._ambiente_do_perfil` devolve
    ``None`` para a regra que este seletor não sabe descrever (título de
    janela, lista de classes, `MatchManual`), o campo abre TRAVADO com a frase
    do que ele é, e o `match` do disco fica intacto. Isto não inventa um sexto
    estado: reusa aquele.

    **O ``game`` E O ``janela`` PERGUNTAM AO CATÁLOGO**, e é aí que a §5 da
    sprint se cumpre — *"um perfil que já existe com forma escolhida à mão
    continua válido e continua sendo mostrado"*. A chave que o perfil guarda
    (``gotg.exe``, ``mk1.exe``) é levada ao `lancador_da_chave`, que responde
    «Heroic», «Lutris» ou o que for; quem não está no catálogo cai no rótulo
    residual que a TELA escolhe (`jogos_locais.LANCADOR_DIRETO`, *"Instalado
    aqui"*), e continua editável. **Medido nos 27 perfis dela em 11/09/2026:**
    25 são `steam_game` (→ «Steam»), um é `game` (``guard``) e um é `janela`
    (``Hefesto-Dualsense4Unix``) — os dois últimos são exatamente os que
    dependem desta porta para não abrirem travados.

    Sem `lancador_da_chave` a resposta é ``None``: afirmar uma procedência sem
    ter a quem perguntar seria a tela adivinhando de onde o jogo dela veio.
    """
    preset = detect_simple_preset(match) if match is not None else None
    if preset is None:
        return None
    fixa = _FIXA_DO_PRESET.get(preset)
    if fixa is not None:
        return fixa
    if preset in ("steam", "steam_game"):
        return PROCEDENCIA_DA_STEAM
    if preset in ("game", "janela"):
        # O `match is None` já saiu na primeira linha desta função — o
        # `detect_simple_preset` só devolve preset para um `Match` de verdade —,
        # e esta guarda repete o fato para o verificador de tipo, que não
        # consegue seguir a implicação por duas chamadas.
        if lancador_da_chave is None or match is None:
            return None
        return lancador_da_chave(simple_extra(match)) or None
    # `terminal` e `editor` continuam FORA do desenho dela, e continuam caindo
    # no campo travado com a frase — o que é o certo: nenhum dos dois responde
    # *"de onde vem o jogo?"*, porque nenhum dos dois é jogo.
    return None


def oferta_do_funciona_em(
    lancadores_da_maquina: Iterable[str],
    atual: str = "",
) -> list[str]:
    """O que o campo «Funciona em:» oferece NESTA máquina, na ordem da tela.

    ``[«Navegação»] + os lançadores que existem + [«Qualquer jogo»]``.

    **A LISTA NÃO É DIGITADA** — os lançadores vêm do censo, e um que a máquina
    não tem não aparece. Numa instalação sem Steam, sem Heroic e sem Lutris
    sobram as duas fixas, **e a tela continua certa**: sem linha vazia, sem
    erro e sem uma palavra que pressuponha Steam. É a §6.4 da sprint, e a razão
    é a ordem dela: o produto é para qualquer pessoa, não para esta bancada.

    **O `atual` ENTRA SEMPRE, e sem ele a tela mentiria.** Um ``<select>`` só
    mostra o que oferece: se ela desinstalar o Heroic, o perfil de um jogo do
    Heroic continua no disco e continua válido, e sem esta linha o campo cairia
    para a primeira opção — a tela AFIRMANDO uma regra que o arquivo não tem.
    É o mesmo defeito que o `opts(travessao=True)` do desenho veio curar, medido
    no DOM vivo em 04/09/2026.

    Duplicata não entra duas vezes, e a ordem de chegada manda: quem ordena os
    lançadores é quem os conta.
    """
    fora = [PROCEDENCIA_DA_NAVEGACAO]
    for nome in list(lancadores_da_maquina) + ([atual] if atual else []):
        limpo = str(nome or "").strip()
        if limpo and limpo not in fora and limpo != PROCEDENCIA_DE_QUALQUER_JOGO:
            fora.append(limpo)
    fora.append(PROCEDENCIA_DE_QUALQUER_JOGO)
    return fora
