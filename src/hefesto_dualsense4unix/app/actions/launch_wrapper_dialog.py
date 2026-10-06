"""Lembrete do wrapper `hefesto-launch` — diálogo "1x por jogo" (DEDUP-05)."""
# ruff: noqa: E402
from __future__ import annotations

import json
import os
import tempfile
from collections.abc import Collection, Mapping
from pathlib import Path
from typing import Any

import gi

gi.require_version("Gtk", "3.0")

from hefesto_dualsense4unix.app.actions.mode_transition import (
    MODE_GAMEPAD,
    mode_of_state,
)
from hefesto_dualsense4unix.utils.logging_config import get_logger

logger = get_logger(__name__)


DECISION_SKIP = "skip"
DECISION_READ_VDF = "read_vdf"
DECISION_PROMPT = "prompt"


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


def wrapper_dialog_decision(
    state: dict[str, Any] | None,
    *,
    vdf_cache: Mapping[str, bool],
    dismissed: Collection[str],
    shown_this_session: Collection[str],
    popup_open: bool,
    dialog_open: bool,
) -> tuple[str, str | None]:
    """Decisão PURA do gatilho do diálogo — todas as condições a-e num lugar só.

    Retorna ``(ação, appid)``:

    - ``(DECISION_SKIP, None)`` — nada a fazer neste tick;
    - ``(DECISION_READ_VDF, appid)`` — falta o veredito do vdf para este appid
      (o adaptador lê UMA vez em worker e memoiza);
    - ``(DECISION_PROMPT, appid)`` — mostrar o diálogo agora.

    Ordem dos gates (baratos primeiro; a leitura de vdf é a única cara):

    - (e) nenhum diálogo NOSSO aberto (``dialog_open``) — antes de tudo;
    - (b) a janela em foco é jogo Steam (``window_detect_last_class``);
    - (a) emulação de gamepad ativa (``mode_of_state`` — o nativo vence e
      não tem vpad, então não conta como emulação ativa);
    - anti-spam: no máximo 1 exibição por appid POR SESSÃO, mesmo sem
      dispensa;
    - (d) o appid não foi dispensado ("Não perguntar para este jogo",
      persistido);
    - (e) nenhum popup/grab GTK aberto (``popup_open`` — o gate
      ``_popup_is_open`` da aba Status) — também segura a LEITURA do vdf,
      que pode esperar o próximo tick;
    - (c) o LaunchOptions do appid ainda não chama o wrapper (cache do vdf:
      ``True`` = precisa do lembrete, ``False`` = já usa o wrapper ou não há
      Steam elegível, ausente = ainda não lido).
    """
    if dialog_open:
        return DECISION_SKIP, None
    if not isinstance(state, dict):
        return DECISION_SKIP, None
    appid = extract_steam_appid(state.get("window_detect_last_class"))
    if appid is None:
        return DECISION_SKIP, None
    if mode_of_state(state) != MODE_GAMEPAD:
        return DECISION_SKIP, None
    if appid in shown_this_session:
        return DECISION_SKIP, None
    if appid in dismissed:
        return DECISION_SKIP, None
    if popup_open:
        return DECISION_SKIP, None
    needs = vdf_cache.get(appid)
    if needs is None:
        return DECISION_READ_VDF, appid
    if not needs:
        return DECISION_SKIP, None
    return DECISION_PROMPT, appid


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


def remove_dismissed_appid(appid: str) -> bool:
    """DESFAZ a dispensa de UM appid. Devolve se ele saiu da lista.

    O PAR QUE FALTAVA, e a falta era um caminho só de ida: até 02/09/2026 este
    módulo só sabia ``add_dismissed_appid`` — o botão *"Não perguntar para este
    jogo"* do lembrete. Clicar produzia um silêncio PERMANENTE, sem tela que o
    mostrasse e sem gesto que o desfizesse; a única saída era editar o
    ``launch_dialog_dismissed.json`` à mão. Decisão, 02/09/2026: nasce o
    desfazer, e a aba Lançadores ganha o botão *"Voltar a perguntar"*.

    MESMA ESCRITA DO ``add``: merge com o disco, ``mkstemp`` + ``os.replace`` no
    MESMO diretório (atômico no POSIX). Duas telas escrevendo o arquivo não se
    atropelam, e um disco cheio não deixa o JSON pela metade.

    ELE DEVOLVE ``bool``, E O ``add`` NÃO — a diferença é deliberada. O ``add``
    roda no tique da GUI, onde engolir a falha é o certo (o pior caso é o
    lembrete voltar uma vez). Este roda no CLIQUE DO USUÁRIO, e um clique que falha
    calado é o defeito mais caro desta casa: a linha continuaria na tela e o
    segundo clique pareceria o primeiro. Quem chama levanta a recusa com a
    frase; ver ``interface/pacotes/a07_lancadores.voltar_a_perguntar``.

    ``False`` também quando o appid **já não estava** na lista: nos dois casos a
    verdade para quem clicou é a mesma — *nada mudou por causa deste clique*.
    """
    alvo = str(appid).strip()
    try:
        atual = load_dismissed_appids()
        if alvo not in atual:
            logger.debug("launch_dialog_dismiss_remover_inexistente", appid=alvo)
            return False
        atual.discard(alvo)
        path = _dismissed_path(ensure=True)
        data = json.dumps({_DISMISSED_KEY: sorted(atual)}, ensure_ascii=False)
        fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".launch_dialog_")
        try:
            os.write(fd, data.encode())
        finally:
            os.close(fd)
        os.replace(tmp, path)
    except Exception as exc:
        logger.debug("launch_dialog_dismiss_remover_falhou", erro=str(exc))
        return False
    logger.debug("launch_dialog_dismiss_removido", appid=alvo)
    return True


__all__ = [
    "DECISION_PROMPT",
    "DECISION_READ_VDF",
    "DECISION_SKIP",
    "extract_steam_appid",
    "load_dismissed_appids",
    "wrapper_dialog_decision",
]
