"""Handlers do rodapé global: Aplicar, Salvar Perfil, Importar, Restaurar Default.

``FooterActionsMixin`` é incorporado na MRO de ``HefestoApp``. Todos os handlers
atuam sobre ``self.draft`` (DraftConfig) e instrumentam ``self._footer_toast``
para feedback ao usuário.

Padrão de thread:
- ``on_apply_draft``: usa ``ipc_bridge.call_async`` para não bloquear GTK.
- ``on_save_profile`` / ``on_import_profile`` / ``on_restore_default``: diálogos
  na thread GTK, mas o I/O de disco (carregar/checar conflito/salvar) é despachado
  para um worker via ``ipc_bridge.run_in_thread`` e renderizado no callback
  (``GLib.idle_add``) — PERF-FOOTER-ASYNC-IO-01.

Importações de topo para permitir patch nos testes:
- ``ipc_bridge`` exposto como variável de módulo.
- ``gui_dialogs`` exposto como variável de módulo.
- Funções de loader importadas em nível de módulo.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from hefesto_dualsense4unix.app import gui_dialogs, ipc_bridge
from hefesto_dualsense4unix.app.actions.base import WidgetAccessMixin
from hefesto_dualsense4unix.app.constants import ROOT_DIR
from hefesto_dualsense4unix.profiles.loader import load_all_profiles, load_profile, save_profile
from hefesto_dualsense4unix.utils.i18n import _
from hefesto_dualsense4unix.utils.logging_config import get_logger
from hefesto_dualsense4unix.utils.xdg_paths import profiles_dir

logger = get_logger(__name__)

# Asset canônico do perfil do usuário (FEAT-PROFILES-PRESET-06).
_MEU_PERFIL_ASSET = ROOT_DIR / "assets" / "profiles_default" / "meu_perfil.json"
_MEU_PERFIL_NOME = "meu_perfil"

# Widgets congelados durante operação de aplicar draft.
FROZEN_WIDGET_IDS: tuple[str, ...] = (
    "btn_footer_apply",
    "btn_footer_save_profile",
    "btn_footer_import",
    "btn_footer_restore_default",
    "lightbar_color_button",
    "lightbar_brightness_scale",
    # BUG-FROZEN-WIDGET-IDS-01: IDs reais do glade (eram *_combo / mouse_toggle,
    # que não existem -> freeze nunca cobria triggers nem o toggle de mouse).
    # FEAT-DSX-COMBO-TO-SEGMENTED-01: o combo de modo virou um slot (GtkBox) com
    # o SegmentedSelector dentro; congelar o slot propaga insensitive aos botões.
    "trigger_left_mode_slot",
    "trigger_right_mode_slot",
    "rumble_weak_scale",
    "rumble_strong_scale",
    "mouse_emulation_toggle",
    # BUG-MOUSE-GUI-SYNC-01: os sliders da aba Mouse também disparam IPC —
    # precisam congelar junto durante a transação do Aplicar.
    "mouse_speed_scale",
    "mouse_scroll_speed_scale",
)


class FooterActionsMixin(WidgetAccessMixin):
    """Handlers dos 4 botões do rodapé global da GUI."""

    # Referência ao draft central (definida em HefestoApp.__init__).
    draft: Any  # DraftConfig — evita import circular; validado em runtime

    # ------------------------------------------------------------------
    # Controle de freeze
    # ------------------------------------------------------------------

    def _freeze_ui(self, freeze: bool) -> None:
        """Habilita ou desabilita widgets conhecidos durante operação longa.

        Itera ``FROZEN_WIDGET_IDS`` e seta ``sensitive`` conforme ``freeze``.
        Widgets ausentes no builder são ignorados silenciosamente.
        """
        sensitive = not freeze
        for widget_id in FROZEN_WIDGET_IDS:
            widget = self._get(widget_id)
            if widget is not None:
                widget.set_sensitive(sensitive)

    # ------------------------------------------------------------------
    # Statusbar
    # ------------------------------------------------------------------

    def _footer_toast(self, msg: str, context: str = "footer") -> None:
        """Empurra mensagem na statusbar com contexto ``context``."""
        self._status_toast(context, msg)

    # ------------------------------------------------------------------
    # Handler: Aplicar
    # ------------------------------------------------------------------

    def on_apply_draft(self, _btn: Any = None) -> None:
        """Envia DraftConfig inteiro ao daemon via IPC ``profile.apply_draft``.

        Congela UI durante a transação (~500ms); callback via GLib.idle_add
        reabilita e exibe resultado na statusbar.
        """
        self._freeze_ui(True)
        self._footer_toast(_("Aplicando perfil inteiro..."))

        draft_dict = self.draft.to_ipc_dict()

        def _on_ok(result: Any) -> bool:
            self._freeze_ui(False)
            if isinstance(result, bool):
                ok = result
            elif isinstance(result, dict):
                ok = result.get("status") == "ok"
            else:
                ok = bool(result)
            msg = (
                _("Perfil aplicado ao controle.")
                if ok
                else _("ERRO ao aplicar perfil (daemon offline?).")
            )
            self._footer_toast(msg)
            logger.info("footer_apply_draft_resultado", ok=ok)
            return False  # GLib.idle_add não repete

        def _on_err(exc: Exception) -> bool:
            self._freeze_ui(False)
            self._footer_toast(_("ERRO ao aplicar: {erro}").format(erro=exc))
            logger.warning("footer_apply_draft_falhou", erro=str(exc))
            return False

        ipc_bridge.call_async(
            "profile.apply_draft",
            draft_dict,
            on_success=_on_ok,
            on_failure=_on_err,
            timeout_s=1.5,
        )

    # ------------------------------------------------------------------
    # Handler: Salvar Perfil
    # ------------------------------------------------------------------

    def on_save_profile(self, _btn: Any = None) -> None:
        """Abre diálogo de nome e persiste DraftConfig como perfil nomeado.

        Usa ``DraftConfig.to_profile(name)`` e ``save_profile(profile)``.
        Após salvar, dispara refresh da aba Perfis se disponível.

        PERF-FOOTER-ASYNC-IO-01: o diálogo de nome roda na thread GTK, mas o I/O
        de disco (checagem de conflito + gravação) é despachado para um worker via
        ``ipc_bridge.run_in_thread``, com o resultado renderizado no callback
        (``GLib.idle_add``). A checagem de conflito é feita NO DISCO dentro do
        worker (nunca no cache em memória), evitando decisão com estado stale.
        """
        window = self._get("main_window")
        # BUG-FOOTER-ACTIVE-NAME-01: DraftConfig é frozen e nunca teve `_active_name`
        # (getattr morto -> default sempre vazio). O nome do perfil ativo agora vive
        # em HefestoApp._active_profile_name (populado por _bootstrap_draft_async).
        active_name: str = getattr(self, "_active_profile_name", "") or ""
        nome = gui_dialogs.prompt_profile_name(parent=window, default_name=active_name)
        if nome is None:
            return  # usuário cancelou

        # Worker: lê os nomes existentes do disco (sem cache) p/ checar conflito.
        def _existing_names() -> list[str]:
            return [p.name for p in load_all_profiles()]

        def _on_checked(existentes: list[str]) -> bool:
            if nome in existentes and not gui_dialogs.prompt_overwrite_existing(
                parent=window, name=nome
            ):
                self._footer_toast(_("Operação cancelada."))
                return False
            self._persist_profile_async(nome)
            return False

        ipc_bridge.run_in_thread(_existing_names, on_success=_on_checked)

    def _persist_profile_async(self, nome: str) -> None:
        """Grava o DraftConfig como perfil ``nome`` em worker (I/O fora da thread GTK)."""
        draft = self.draft

        def _save() -> Path:
            return save_profile(draft.to_profile(nome))

        def _on_saved(path: Path) -> bool:
            self._footer_toast(_("Perfil salvo em {caminho}").format(caminho=path))
            logger.info("footer_save_profile_ok", nome=nome, path=str(path))
            # mantém o pré-preenchimento coerente nos próximos "Salvar Perfil".
            self._active_profile_name = nome
            refresh = getattr(self, "_reload_profiles_store", None)
            if refresh is not None:
                refresh(select_name=nome)
            return False

        def _on_err(exc: Exception) -> bool:
            self._footer_toast(_("Falha ao salvar perfil: {erro}").format(erro=exc))
            logger.warning("footer_save_profile_falhou", nome=nome, erro=str(exc))
            return False

        ipc_bridge.run_in_thread(_save, on_success=_on_saved, on_failure=_on_err)

    # ------------------------------------------------------------------
    # Handler: Importar
    # ------------------------------------------------------------------

    def on_import_profile(self, _btn: Any = None) -> None:
        """Abre FileChooserDialog para importar perfil JSON.

        Valida via ``Profile.model_validate``, copia para profiles_dir e
        resolve conflito de nome se necessário.
        """
        # Import tardio de Gtk para permitir testes sem GTK instalado.
        import gi
        gi.require_version("Gtk", "3.0")
        from gi.repository import Gtk

        from hefesto_dualsense4unix.profiles.schema import Profile

        window = self._get("main_window")

        chooser = Gtk.FileChooserDialog(
            title="Importar Perfil",
            parent=window,
            action=Gtk.FileChooserAction.OPEN,
        )
        chooser.add_button("Cancelar", Gtk.ResponseType.CANCEL)
        chooser.add_button("Abrir", Gtk.ResponseType.OK)
        chooser.set_default_response(Gtk.ResponseType.OK)

        filtro = Gtk.FileFilter()
        filtro.set_name("Perfis JSON (*.json)")
        filtro.add_pattern("*.json")
        chooser.add_filter(filtro)

        response = chooser.run()
        filename = chooser.get_filename()
        chooser.destroy()

        if response != Gtk.ResponseType.OK or not filename:
            return

        # PERF-FOOTER-ASYNC-IO-01: o FileChooser tem que rodar na thread GTK, mas
        # ler/validar o arquivo e listar os perfis existentes (p/ checar conflito)
        # é I/O de disco — vai para um worker. A checagem de conflito é feita no
        # disco (não no cache) e o diálogo de conflito decide no callback GTK.
        def _read() -> tuple[Profile, list[str]]:
            raw = json.loads(Path(filename).read_text(encoding="utf-8"))
            profile = Profile.model_validate(raw)
            existentes = [p.name for p in load_all_profiles()]
            return profile, existentes

        def _on_read(payload: tuple[Profile, list[str]]) -> bool:
            profile, existentes = payload
            nome = profile.name
            if nome in existentes:
                escolha = gui_dialogs.prompt_import_conflict(parent=window, name=nome)
                if escolha is None:
                    self._footer_toast(_("Importação cancelada."))
                    return False
                if escolha == "renomear":
                    novo_nome = gui_dialogs.prompt_profile_name(
                        parent=window, default_name=nome
                    )
                    if not novo_nome:
                        self._footer_toast(_("Importação cancelada."))
                        return False
                    dados = profile.model_dump(mode="python")
                    dados["name"] = novo_nome
                    try:
                        profile = Profile.model_validate(dados)
                    except Exception as exc:
                        self._footer_toast(_("Nome inválido: {erro}").format(erro=exc))
                        return False
            self._import_save_async(profile)
            return False

        def _on_read_err(exc: Exception) -> bool:
            self._footer_toast(_("Arquivo inválido: {erro}").format(erro=exc))
            logger.warning("footer_import_invalido", arquivo=filename, erro=str(exc))
            return False

        ipc_bridge.run_in_thread(_read, on_success=_on_read, on_failure=_on_read_err)

    def _import_save_async(self, profile: Any) -> None:
        """Grava o perfil importado em worker (I/O fora da thread GTK)."""
        def _save() -> Path:
            return save_profile(profile)

        def _on_saved(path: Path) -> bool:
            self._footer_toast(
                _("Perfil importado: {nome} -> {caminho}").format(
                    nome=profile.name, caminho=path
                )
            )
            logger.info("footer_import_ok", nome=profile.name, path=str(path))
            refresh = getattr(self, "_reload_profiles_store", None)
            if refresh is not None:
                refresh(select_name=profile.name)
            return False

        def _on_err(exc: Exception) -> bool:
            self._footer_toast(_("Falha ao importar: {erro}").format(erro=exc))
            logger.warning("footer_import_falhou", nome=profile.name, erro=str(exc))
            return False

        ipc_bridge.run_in_thread(_save, on_success=_on_saved, on_failure=_on_err)

    # ------------------------------------------------------------------
    # Handler: Restaurar Default
    # ------------------------------------------------------------------

    def on_restore_default(self, _btn: Any = None) -> None:
        """Restaura meu_perfil ao estado do asset original.

        Confirma com usuário, copia asset -> profiles_dir/meu_perfil.json,
        recarrega DraftConfig e dispara refresh de todas as abas.
        """
        from hefesto_dualsense4unix.app.draft_config import DraftConfig

        window = self._get("main_window")

        if not _MEU_PERFIL_ASSET.exists():
            self._footer_toast(
                _(
                    "Asset 'meu_perfil.json' não encontrado — "
                    "Restaurar Default indisponível."
                )
            )
            logger.warning(
                "footer_restore_default_asset_ausente",
                path=str(_MEU_PERFIL_ASSET),
            )
            return

        if not gui_dialogs.confirm_restore_default(parent=window):
            self._footer_toast(_("Restauração cancelada."))
            return

        # PERF-FOOTER-ASYNC-IO-01: a confirmação roda na thread GTK, mas ler o
        # asset, gravar o perfil e recarregar o DraftConfig é I/O de disco — vai
        # para um worker; o resultado é aplicado no callback (GLib.idle_add).
        def _restore() -> Any:
            from hefesto_dualsense4unix.profiles.schema import Profile

            raw = json.loads(_MEU_PERFIL_ASSET.read_text(encoding="utf-8"))
            profile = Profile.model_validate(raw)
            save_profile(profile)
            # Recarrega DraftConfig a partir do perfil restaurado (best-effort:
            # falha aqui não invalida o restore em disco, só mantém o draft antigo).
            try:
                return DraftConfig.from_profile(load_profile(_MEU_PERFIL_NOME))
            except Exception as exc:
                logger.warning("footer_restore_default_draft_falhou", erro=str(exc))
                return None

        def _on_restored(novo_draft: Any) -> bool:
            if novo_draft is not None:
                self.draft = novo_draft
                logger.info("footer_restore_default_draft_recarregado")
            destino = profiles_dir() / f"{_MEU_PERFIL_NOME}.json"
            self._footer_toast(
                _("meu_perfil restaurado para {destino}").format(destino=destino)
            )
            _refresh_all_tabs(self)
            return False

        def _on_err(exc: Exception) -> bool:
            self._footer_toast(_("Falha ao restaurar: {erro}").format(erro=exc))
            logger.warning("footer_restore_default_falhou", erro=str(exc))
            return False

        ipc_bridge.run_in_thread(_restore, on_success=_on_restored, on_failure=_on_err)

    # ------------------------------------------------------------------
    # Instalação (documentação de ponto canônico)
    # ------------------------------------------------------------------

    def install_footer_actions(self) -> None:
        """Ponto de instalação documentado dos handlers do rodapé.

        O builder.connect_signals() em HefestoApp.__init__ já registra os
        handlers via _signal_handlers; este método existe como referência
        canônica e para testes que injetam botões programaticamente.
        """
        pass


# ------------------------------------------------------------------
# Helpers de módulo
# ------------------------------------------------------------------


def _refresh_all_tabs(mixin: Any) -> None:
    """Dispara refresh das abas que têm método _refresh_*_from_draft."""
    for method_name in (
        "_refresh_lightbar_from_draft",
        "_refresh_triggers_from_draft",
        "_refresh_rumble_from_draft",
        # BUG-MOUSE-RESTORE-DEFAULT-LIES-01: usa _refresh_mouse_TAB (draft +
        # sync com o estado vivo do daemon), não _refresh_mouse_from_draft — se
        # não, após "Restaurar Default" com a emulação viva (ligada por CLI/
        # applet) a aba mostra toggle OFF enquanto o cursor continua andando.
        "_refresh_mouse_tab",
        # BUG-KEYBOARD-TAB-NO-REFRESH-01: faltava a aba Teclado -> Restaurar
        # Default (e qualquer recarga via _refresh_all_tabs) deixava os bindings
        # stale, podendo reverter o restore ao editar.
        "_refresh_key_bindings_from_draft",
    ):
        fn = getattr(mixin, method_name, None)
        if fn is not None:
            try:
                fn()
            except Exception as exc:
                logger.warning(
                    "footer_refresh_aba_falhou",
                    metodo=method_name,
                    erro=str(exc),
                )

    reload_fn = getattr(mixin, "_reload_profiles_store", None)
    if reload_fn is not None:
        try:
            reload_fn()
        except Exception as exc:
            logger.warning("footer_refresh_perfis_falhou", erro=str(exc))


__all__ = [
    "FROZEN_WIDGET_IDS",
    "FooterActionsMixin",
]
