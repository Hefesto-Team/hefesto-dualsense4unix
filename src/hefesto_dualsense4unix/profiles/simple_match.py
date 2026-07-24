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

import re

from hefesto_dualsense4unix.profiles.schema import MatchAny, MatchCriteria

#: R-12: ``wm_class`` de jogo Steam (Proton ou nativo). Mesmo formato que
#: `app.actions.launch_wrapper_dialog._STEAM_APP_RE` reconhece no state_full.
_STEAM_APP_RE = re.compile(r"^steam_app_(\d+)$")

#: Aceita o que a usuária tem em mãos: o número puro da URL da loja
#: (``1599660``) ou a wm_class inteira, copiada de um doctor/journal.
_APPID_RE = re.compile(r"^\s*(?:steam_app_)?(\d+)\s*$", re.IGNORECASE)

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
    "O número do jogo na Steam é só dígitos (ex.: 1599660) — é o número que "
    "aparece na URL da loja."
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
    """
    if not raw:
        return None
    m = _APPID_RE.match(raw)
    return m.group(1) if m else None


def from_simple_choice(
    choice: str,
    custom_name: str | None = None,
) -> MatchCriteria | MatchAny:
    """Converte escolha do radio "Aplica a" em MatchCriteria ou MatchAny.

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
        return MatchCriteria(window_class=[f"steam_app_{appid}"])
    if choice == "game":
        if custom_name and custom_name.strip():
            return MatchCriteria(process_name=[custom_name.strip()])
        raise ValueError(MSG_JOGO_SEM_NOME)
    return SIMPLE_MATCH_PRESETS.get(choice, MatchAny())


def detect_simple_preset(
    match: MatchCriteria | MatchAny,
) -> str | None:
    """Detecta se match corresponde a algum preset simples.

    Retorna a chave do preset (ex.: "steam", "browser") ou None se nenhum bater.
    Para "game", retorna ("game", process_name[0]); empacota com `_detect_game`.
    Para "steam_game", o valor de acompanhamento é o appid (ver `simple_extra`).
    Uso interno: profiles_actions._populate_editor_v2.

    LEITURA É TOLERANTE (risco de regressão anotado no plano): um perfil já
    salvo com critério vazio continua carregando — só devolve ``None`` e cai no
    editor avançado. Quem recusa é a ESCRITA (`from_simple_choice`).
    """
    if isinstance(match, MatchAny):
        return "any"
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


def simple_extra(match: MatchCriteria | MatchAny) -> str:
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


def _detect_steam_appid(match: MatchCriteria | MatchAny) -> str | None:
    """Appid quando o match é EXATAMENTE "um jogo da Steam", senão None.

    Exige window_class com um único ``steam_app_<id>`` e nenhum outro campo:
    ``MatchCriteria.matches`` é AND entre campos preenchidos, então um regex de
    título junto mudaria o significado e o editor simples estaria mentindo
    sobre o que o perfil faz.
    """
    if not isinstance(match, MatchCriteria):
        return None
    if len(match.window_class) != 1 or match.window_title_regex or match.process_name:
        return None
    m = _STEAM_APP_RE.match(match.window_class[0].strip())
    return m.group(1) if m else None


def _criteria_equal(a: MatchCriteria, b: MatchCriteria) -> bool:
    """Compara dois MatchCriteria por igualdade de campos."""
    return (
        sorted(a.window_class) == sorted(b.window_class)
        and a.window_title_regex == b.window_title_regex
        and sorted(a.process_name) == sorted(b.process_name)
    )
