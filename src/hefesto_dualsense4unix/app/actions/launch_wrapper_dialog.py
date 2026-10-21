"""O que sobra do lembrete do wrapper `hefesto-launch` (DEDUP-05): o appid em foco e as dispensas.

O gatilho do lembrete (`wrapper_dialog_decision`) e o «Voltar a perguntar»
(`remove_dismissed_appid`) saíram em 19/10/2026, sem chamador desde a 07 antiga
(O-QUE-A-07-ANTIGA-FAZIA-SEM-TELA-VOLTA-OU-SAI-01, a resposta de 19/10: «Saem do produto»).
A dispensa que já está no disco continua calando o aviso da Jogar
(`home_actions.aviso_do_wrapper`).
"""
from __future__ import annotations

import json
from pathlib import Path


def extract_steam_appid(wm_class: object) -> str | None:
    """Appid do jogo Steam em foco a partir do ``window_detect_last_class``.

    ``steam_app_1599660`` → ``"1599660"``; qualquer outra coisa (None, classe
    de app comum, "unknown") → None. O campo do state_full é a última wm_class
    ÚTIL vista pelo detector — pode ficar "grudado" no jogo por alguns
    segundos depois de o foco mudar; inofensivo aqui, porque o anti-spam
    limita a 1 exibição por appid por sessão.

    UNIFICA-PREDICADO-01: o reconhecimento em si vem da fonte única
    (`profiles/steam_app.py`), que já era insensível a caixa e a espaço como
    este callsite precisa. O que continua morando aqui é o TIPO: a fonte
    devolve `int` e todo este módulo trabalha com `str` (chave do
    `_wrapper_dialog_vdf_cache`, do `dismissed` em JSON e da string de
    LaunchOptions). A conversão é explícita de propósito — um `==` entre `int`
    e `str` seria sempre False, em silêncio, e o diálogo simplesmente nunca
    apareceria.

    Import tardio no idioma dos vizinhos (`daemon_actions`, `emulation_actions`):
    não vale puxar o módulo em todo import desta janela.
    """
    from hefesto_dualsense4unix.profiles.steam_app import steam_appid_from_wm_class

    if not isinstance(wm_class, str):
        return None
    appid = steam_appid_from_wm_class(wm_class)
    return None if appid is None else str(appid)


_DISMISSED_FILE = "launch_dialog_dismissed.json"
_DISMISSED_KEY = "dismissed_appids"


def _dismissed_path(*, ensure: bool = False) -> Path:
    """Caminho do JSON de dispensas no config do app."""
    from hefesto_dualsense4unix.utils.xdg_paths import config_dir

    return config_dir(ensure=ensure) / _DISMISSED_FILE


def load_dismissed_appids() -> set[str]:
    """Appids cuja dispensa foi persistida ("Não perguntar para este jogo")."""
    try:
        raw = _dismissed_path().read_text(encoding="utf-8")
        data = json.loads(raw)
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return set()
    except Exception:
        return set()
    if not isinstance(data, dict):
        return set()
    items = data.get(_DISMISSED_KEY)
    if not isinstance(items, list):
        return set()
    out: set[str] = set()
    for item in items:
        if isinstance(item, str) and item.strip():
            out.add(item.strip())
        elif isinstance(item, int) and not isinstance(item, bool):
            out.add(str(item))
    return out


__all__ = [
    "extract_steam_appid",
    "load_dismissed_appids",
]
