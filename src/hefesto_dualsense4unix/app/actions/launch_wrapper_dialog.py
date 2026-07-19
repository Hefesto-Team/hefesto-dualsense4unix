"""Lembrete do wrapper `hefesto-launch` — diálogo "1x por jogo" (DEDUP-05).

Aprovado pela mantenedora (sessão 2026-07-16, checkpoint das Fases 1-3): quando
ela está JOGANDO com a emulação ligada e o jogo em foco ainda não abre pelo
wrapper, a GUI mostra UM diálogo com a string constante e o botão de copiar;
se ela dispensou ("Não perguntar para este jogo"), nunca mais insiste naquele
appid. Texto honesto exigido pelo sprint doc: sem o clique, o comportamento é
controle DUPLICADO no jogo — nunca zero controles.

Decisões de desenho (não relaxar):

- **GTK dialog, nunca popover/dropdown** (cosmic-epoch#2497 + NVIDIA derruba
  qualquer popup no COSMIC — regra histórica do projeto). E NÃO-modal: o
  gatilho dispara com o jogo em foco (a GUI está em segundo plano) e um modal
  seguraria um grab GTK que pausa os renders periódicos da aba Status
  (`_popup_is_open`) enquanto ela joga.
- **Zero timers novos**: o gatilho engancha no tick lento (2 Hz) que a GUI JÁ
  tem — `HefestoApp._render_slow_state` chama `_maybe_prompt_wrapper_dialog`
  depois do render normal da aba Status.
- **Sem botão "Aplicar…"** — de propósito: o gatilho deste diálogo é
  exatamente "jogo aberto", e o fluxo assistido da Fase 2 RECUSA nesse estado
  duas vezes (`steam_game_running()` — `steam -shutdown` mataria o jogo — e
  `steam_running()` — a Steam regrava o vdf ao sair). Um botão perenemente
  desabilitado seria ruído; o texto aponta o caminho real (botão "Aplicar aos
  jogos da Steam" da aba Sistema, com o jogo e a Steam fechados).
- **Cache do vdf por appid**: a leitura do localconfig.vdf acontece UMA vez
  por appid por sessão (em thread worker), nunca a cada tick. Staleness é
  inofensiva: o anti-spam limita a 1 exibição por appid por sessão.
- **Dispensa persistente SÓ pelo botão explícito**, em JSON atômico próprio
  (`launch_dialog_dismissed.json` no config do app, padrão `utils/session.py`).
"""
# ruff: noqa: E402
from __future__ import annotations

import contextlib
import json
import os
import re
import tempfile
from collections.abc import Collection, Mapping
from pathlib import Path
from typing import Any

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

from hefesto_dualsense4unix.app.actions.base import WidgetAccessMixin
from hefesto_dualsense4unix.app.actions.mode_transition import (
    MODE_GAMEPAD,
    mode_of_state,
)
from hefesto_dualsense4unix.app.ipc_bridge import run_in_thread
from hefesto_dualsense4unix.integrations.steam_launch_options import (
    WRAPPER_LAUNCH,
    appid_needs_wrapper,
)
from hefesto_dualsense4unix.utils.logging_config import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Decisão pura do gatilho (condições a-e do pedido aprovado)
# ---------------------------------------------------------------------------

#: wm_class de jogo Steam sob Proton/nativo: `steam_app_<appid>`.
_STEAM_APP_RE = re.compile(r"^steam_app_(\d+)$")

#: Ações que a decisão pura devolve para o adaptador do tick.
DECISION_SKIP = "skip"
DECISION_READ_VDF = "read_vdf"
DECISION_PROMPT = "prompt"

#: Response ids dos botões próprios (positivos para não colidir com os
#: `Gtk.ResponseType` nativos, que são negativos).
RESPONSE_COPY = 101
RESPONSE_DISMISS = 102


def extract_steam_appid(wm_class: object) -> str | None:
    """Appid do jogo Steam em foco a partir do ``window_detect_last_class``.

    ``steam_app_1599660`` → ``"1599660"``; qualquer outra coisa (None, classe
    de app comum, "unknown") → None. O campo do state_full é a última wm_class
    ÚTIL vista pelo detector — pode ficar "grudado" no jogo por alguns
    segundos depois de o foco mudar; inofensivo aqui, porque o anti-spam
    limita a 1 exibição por appid por sessão.
    """
    if not isinstance(wm_class, str):
        return None
    m = _STEAM_APP_RE.match(wm_class.strip().lower())
    return m.group(1) if m else None


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


# ---------------------------------------------------------------------------
# Persistência das dispensas (JSON atômico, padrão utils/session.py)
# ---------------------------------------------------------------------------

_DISMISSED_FILE = "launch_dialog_dismissed.json"
_DISMISSED_KEY = "dismissed_appids"


def _dismissed_path(*, ensure: bool = False) -> Path:
    """Caminho do JSON de dispensas no config do app.

    Import lazy de ``config_dir`` para preservar o ponto de monkeypatch dos
    testes (``monkeypatch.setattr(xdg_paths, "config_dir", ...)``) — o mesmo
    padrão documentado em ``utils.session.save_active_marker``.
    """
    from hefesto_dualsense4unix.utils.xdg_paths import config_dir

    return config_dir(ensure=ensure) / _DISMISSED_FILE


def load_dismissed_appids() -> set[str]:
    """Appids cuja dispensa foi persistida ("Não perguntar para este jogo").

    Tolerante a arquivo ausente/corrompido/formato inesperado: devolve
    ``set()`` — o pior caso é o lembrete aparecer UMA vez de novo (o anti-spam
    de sessão segura o resto). Nunca propaga exceção.
    """
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
            # Tolerância a appid gravado como número por edição manual.
            out.add(str(item))
    return out


def add_dismissed_appid(appid: str) -> None:
    """Persiste a dispensa de UM appid (escrita atômica, best-effort).

    Merge com o que já está no disco antes de gravar; escrita via
    ``mkstemp`` + ``os.replace`` no MESMO diretório (atômica no POSIX),
    espelhando ``utils.session.save_last_profile``. Nunca propaga exceção —
    falha de disco não pode derrubar o tick da GUI.
    """
    try:
        path = _dismissed_path(ensure=True)
        atual = load_dismissed_appids()
        atual.add(str(appid).strip())
        data = json.dumps({_DISMISSED_KEY: sorted(atual)}, ensure_ascii=False)
        fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".launch_dialog_")
        try:
            os.write(fd, data.encode())
        finally:
            os.close(fd)
        os.replace(tmp, path)
        logger.debug("launch_dialog_dismiss_salvo", appid=appid)
    except Exception as exc:
        logger.debug("launch_dialog_dismiss_save_falhou", erro=str(exc))


# ---------------------------------------------------------------------------
# Mixin da GUI
# ---------------------------------------------------------------------------

#: Texto principal do diálogo (o appid entra no fim, entre parênteses).
_DIALOG_TITLE = "Este jogo ainda não abre pelo launcher do Hefesto"

#: Texto honesto exigido pelo DEDUP-05 (item 6): sem o clique, o comportamento
#: é controle DUPLICADO no jogo — nunca zero. A string constante fica visível
#: e selecionável no próprio diálogo (além do botão de copiar).
_DIALOG_BODY = (
    "Sem o launcher, o jogo pode ver o controle DUPLICADO (o físico e o "
    "virtual ao mesmo tempo) — mas nunca zero controles: nada quebra, só "
    "duplica.\n\n"
    "Para este jogo usar o launcher, cole esta linha em Steam → jogo "
    "(botão direito) → Propriedades → Opções de inicialização:\n\n"
    f"{WRAPPER_LAUNCH}\n\n"
    "Com o jogo aberto não dá para aplicar automaticamente (a Steam "
    "regrava esse arquivo ao fechar e a mudança se perderia). Com o jogo e "
    "a Steam fechados, o botão \"Aplicar aos jogos da Steam\" na aba "
    "Sistema faz isso em um clique."
)


class LaunchWrapperDialogMixin(WidgetAccessMixin):
    """Mostra o lembrete do wrapper no tick de estado existente da GUI.

    Estado por sessão (contêineres criados por INSTÂNCIA no bootstrap lazy —
    mutáveis em nível de classe vazariam entre instâncias/testes):

    - ``_wrapper_dialog_vdf_cache``: appid → "precisa do lembrete?" (o vdf é
      lido UMA vez por appid, em worker; nunca a cada tick);
    - ``_wrapper_dialog_shown_appids``: anti-spam — 1 exibição por appid por
      sessão, mesmo sem dispensa;
    - ``_wrapper_dialog_dismissed``: dispensas persistidas (lazy-load do
      JSON; só o botão explícito acrescenta).
    """

    _wrapper_dialog_open: bool = False
    _wrapper_dialog_vdf_inflight: bool = False
    _wrapper_dialog_dismissed: set[str] | None = None
    _wrapper_dialog_widget: Any = None
    _wrapper_dialog_vdf_cache: dict[str, bool]
    _wrapper_dialog_shown_appids: set[str]

    # --- estado -----------------------------------------------------------

    def _wrapper_dialog_bootstrap(self) -> None:
        """Cria os contêineres mutáveis por instância (idempotente)."""
        if not hasattr(self, "_wrapper_dialog_vdf_cache"):
            self._wrapper_dialog_vdf_cache = {}
        if not hasattr(self, "_wrapper_dialog_shown_appids"):
            self._wrapper_dialog_shown_appids = set()

    def _wrapper_dialog_dismissed_set(self) -> set[str]:
        """Dispensas persistidas, carregadas UMA vez por sessão (lazy)."""
        if self._wrapper_dialog_dismissed is None:
            self._wrapper_dialog_dismissed = load_dismissed_appids()
        return self._wrapper_dialog_dismissed

    # --- gatilho (chamado pelo tick lento existente) ------------------------

    def _maybe_prompt_wrapper_dialog(self, state: dict[str, Any] | None) -> None:
        """Avalia o gatilho a cada tick de estado; nunca propaga exceção.

        Chamado por ``HefestoApp._render_slow_state`` DEPOIS do render normal
        (2 Hz — o tick que a GUI já tem; zero timers novos). Toda a decisão é
        da função pura ``wrapper_dialog_decision``; aqui só moram o cache, o
        worker de leitura e a exibição.
        """
        try:
            self._wrapper_dialog_bootstrap()
            popup_gate = getattr(self, "_popup_is_open", None)
            popup_open = bool(popup_gate()) if callable(popup_gate) else False
            action, appid = wrapper_dialog_decision(
                state,
                vdf_cache=self._wrapper_dialog_vdf_cache,
                dismissed=self._wrapper_dialog_dismissed_set(),
                shown_this_session=self._wrapper_dialog_shown_appids,
                popup_open=popup_open,
                dialog_open=self._wrapper_dialog_open,
            )
            if action == DECISION_READ_VDF and appid is not None:
                self._wrapper_dialog_read_vdf(appid)
            elif action == DECISION_PROMPT and appid is not None:
                # Anti-spam ANTES do show: mesmo que o GTK falhe, o appid não
                # volta a disparar nesta sessão (sem loop de erro a 2 Hz).
                self._wrapper_dialog_shown_appids.add(appid)
                self._wrapper_dialog_open = True
                try:
                    self._show_wrapper_dialog(appid)
                except Exception:
                    self._wrapper_dialog_open = False
                    raise
        except Exception as exc:
            logger.warning("launch_dialog_tick_falhou", erro=str(exc))

    def _wrapper_dialog_read_vdf(self, appid: str) -> None:
        """Lê o localconfig.vdf UMA vez por appid (worker) e memoiza o veredito.

        Cache por appid: o tick de 2 Hz NUNCA relê o arquivo — a leitura só
        acontece quando um appid inédito entra em foco. Falha de leitura
        memoiza ``False`` (fail-quiet: melhor não lembrar do que insistir num
        I/O quebrado a 2 Hz). Roda via ``run_in_thread`` para a thread GTK
        nunca esperar disco.
        """
        if self._wrapper_dialog_vdf_inflight:
            return
        self._wrapper_dialog_vdf_inflight = True

        def _read() -> bool:
            return appid_needs_wrapper(appid)

        def _ok(needs: Any) -> bool:
            self._wrapper_dialog_vdf_inflight = False
            self._wrapper_dialog_vdf_cache[appid] = bool(needs)
            return False  # contrato do GLib.idle_add

        def _fail(exc: Exception) -> bool:
            self._wrapper_dialog_vdf_inflight = False
            self._wrapper_dialog_vdf_cache[appid] = False
            logger.debug(
                "launch_dialog_vdf_read_falhou", appid=appid, erro=str(exc)
            )
            return False

        run_in_thread(_read, _ok, _fail)

    # --- diálogo ------------------------------------------------------------

    def _build_wrapper_dialog(self, appid: str) -> Gtk.MessageDialog:
        """Monta o GtkMessageDialog (sem exibir) — separado para os testes.

        NÃO-modal de propósito: o diálogo nasce com o jogo em foco e pode
        ficar aberto durante a partida; um modal seguraria um grab GTK que
        pausa os renders periódicos (gate ``_popup_is_open`` da aba Status).
        """
        window = getattr(self, "window", None)
        dialog = Gtk.MessageDialog(
            transient_for=window,
            flags=0,
            message_type=Gtk.MessageType.INFO,
            buttons=Gtk.ButtonsType.NONE,
            text=f"{_DIALOG_TITLE} (app {appid})",
        )
        # GUI-05/P5: sem a classe de tema, o diálogo herdava o tema do sistema
        # — sob XWayland no COSMIC isso é Adwaita CLARO, destoando do app
        # inteiro (precedente: gui_dialogs._apply_app_theme).
        with contextlib.suppress(Exception):
            dialog.get_style_context().add_class("hefesto-dualsense4unix-window")
        dialog.format_secondary_text(_DIALOG_BODY)
        dialog.add_button("Copiar opções", RESPONSE_COPY)
        dialog.add_button("Não perguntar para este jogo", RESPONSE_DISMISS)
        dialog.add_button("Fechar", Gtk.ResponseType.CLOSE)
        # A linha do wrapper precisa ser SELECIONÁVEL (copiável na mão) mesmo
        # se o clipboard falhar — labels do message area viram selecionáveis.
        with contextlib.suppress(Exception):
            for child in dialog.get_message_area().get_children():
                if hasattr(child, "set_selectable"):
                    child.set_selectable(True)
        dialog.connect(
            "response",
            lambda dlg, resp: self._on_wrapper_dialog_response(dlg, resp, appid),
        )
        return dialog

    def _show_wrapper_dialog(self, appid: str) -> None:
        """Cria e exibe o diálogo (bookkeeping fica no chamador)."""
        dialog = self._build_wrapper_dialog(appid)
        self._wrapper_dialog_widget = dialog
        dialog.show()
        logger.info("launch_dialog_exibido", appid=appid)

    def _on_wrapper_dialog_response(
        self, dialog: Any, response: int, appid: str
    ) -> None:
        """Handler do sinal ``response`` — roda na thread GTK.

        "Copiar opções" NÃO fecha o diálogo (dá para copiar e em seguida
        dispensar); qualquer outra resposta (dispensa, Fechar, Esc/X) fecha.
        A dispensa persistente acontece SÓ pelo botão explícito.
        """
        if response == RESPONSE_COPY:
            if self._copy_wrapper_launch_to_clipboard():
                self._status_toast(
                    "launch_dialog",
                    "Copiado! Cole em: Steam → jogo → Propriedades → "
                    "Opções de inicialização.",
                )
            else:
                self._status_toast(
                    "launch_dialog",
                    "Não consegui copiar — selecione a linha no próprio "
                    "aviso e copie com Ctrl+C.",
                )
            return
        if response == RESPONSE_DISMISS:
            self._wrapper_dialog_dismissed_set().add(appid)
            add_dismissed_appid(appid)
            logger.info("launch_dialog_dispensado", appid=appid)
            self._status_toast(
                "launch_dialog", "Certo — não pergunto mais para este jogo."
            )
        self._wrapper_dialog_open = False
        self._wrapper_dialog_widget = None
        with contextlib.suppress(Exception):
            dialog.destroy()

    @staticmethod
    def _copy_wrapper_launch_to_clipboard() -> bool:
        """Copia a string constante do wrapper para o clipboard.

        Mesmo caminho do botão "Copiar opções p/ jogos" da aba Sistema
        (``DaemonActionsMixin.on_storm_copy_launch``). True se o clipboard
        aceitou; falha silenciosa devolve False (o texto do diálogo continua
        selecionável).
        """
        with contextlib.suppress(Exception):
            from gi.repository import Gdk, Gtk

            clip = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
            clip.set_text(WRAPPER_LAUNCH, -1)
            clip.store()
            return True
        return False


__all__ = [
    "DECISION_PROMPT",
    "DECISION_READ_VDF",
    "DECISION_SKIP",
    "RESPONSE_COPY",
    "RESPONSE_DISMISS",
    "LaunchWrapperDialogMixin",
    "add_dismissed_appid",
    "extract_steam_appid",
    "load_dismissed_appids",
    "wrapper_dialog_decision",
]
