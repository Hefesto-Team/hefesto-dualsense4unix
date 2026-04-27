"""Handlers do rodapé global: Aplicar, Salvar Perfil, Importar, Restaurar Default.

``FooterActionsMixin`` é incorporado na MRO de ``HefestoApp``. Todos os handlers
atuam sobre ``self.draft`` (DraftConfig) e instrumentam ``self._footer_toast``
para feedback ao usuário.

Padrão de thread:
- ``on_apply_draft``: usa ``ipc_bridge.call_async`` para não bloquear GTK.
- Demais: operações de I/O rápidas executadas na thread GTK diretamente.

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
    "trigger_left_mode_combo",
    "trigger_right_mode_combo",
    "rumble_weak_scale",
    "rumble_strong_scale",
    "mouse_toggle",
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
        bar: Any = self._get("status_bar")
        if bar is None:
            return
        ctx_id = bar.get_context_id(context)
        bar.push(ctx_id, msg)

    # ------------------------------------------------------------------
    # Handler: Aplicar
    # ------------------------------------------------------------------

    def on_apply_draft(self, _btn: Any = None) -> None:
        """Envia DraftConfig inteiro ao daemon via IPC ``profile.apply_draft``.

        Congela UI durante a transação (~500ms); callback via GLib.idle_add
        reabilita e exibe resultado na statusbar.
        """
        self._freeze_ui(True)
        self._footer_toast("Aplicando perfil inteiro...")

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
                "Perfil aplicado ao controle."
                if ok
                else "ERRO ao aplicar perfil (daemon offline?)."
            )
            self._footer_toast(msg)
            logger.info("footer_apply_draft_resultado", ok=ok)
            return False  # GLib.idle_add não repete

        def _on_err(exc: Exception) -> bool:
            self._freeze_ui(False)
            self._footer_toast(f"ERRO ao aplicar: {exc}")
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
        """
        window = self._get("main_window")
        active_name: str = getattr(self.draft, "_active_name", "") or ""
        nome = gui_dialogs.prompt_profile_name(parent=window, default_name=active_name)
        if nome is None:
            return  # usuário cancelou

        # Verifica conflito
        existentes = [p.name for p in load_all_profiles()]
        if nome in existentes:
            ok = gui_dialogs.prompt_overwrite_existing(parent=window, name=nome)
            if not ok:
                self._footer_toast("Operação cancelada.")
                return

        try:
            profile = self.draft.to_profile(nome)
            path = save_profile(profile)
        except Exception as exc:
            self._footer_toast(f"Falha ao salvar perfil: {exc}")
            logger.warning("footer_save_profile_falhou", nome=nome, erro=str(exc))
            return

        self._footer_toast(f"Perfil salvo em {path}")
        logger.info("footer_save_profile_ok", nome=nome, path=str(path))

        # Refresh aba Perfis se mixin disponível
        refresh = getattr(self, "_reload_profiles_store", None)
        if refresh is not None:
            refresh(select_name=nome)

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

        # Carrega e valida
        try:
            raw = json.loads(Path(filename).read_text(encoding="utf-8"))
            profile = Profile.model_validate(raw)
        except Exception as exc:
            self._footer_toast(f"Arquivo inválido: {exc}")
            logger.warning("footer_import_invalido", arquivo=filename, erro=str(exc))
            return

        nome = profile.name
        existentes = [p.name for p in load_all_profiles()]

        if nome in existentes:
            escolha = gui_dialogs.prompt_import_conflict(parent=window, name=nome)
            if escolha is None:
                self._footer_toast("Importação cancelada.")
                return
            if escolha == "renomear":
                novo_nome = gui_dialogs.prompt_profile_name(
                    parent=window, default_name=nome
                )
                if not novo_nome:
                    self._footer_toast("Importação cancelada.")
                    return
                dados = profile.model_dump(mode="python")
                dados["name"] = novo_nome
                try:
                    profile = Profile.model_validate(dados)
                except Exception as exc:
                    self._footer_toast(f"Nome inválido: {exc}")
                    return
                nome = novo_nome

        try:
            path = save_profile(profile)
        except OSError as exc:
            self._footer_toast(f"Falha ao importar: {exc}")
            logger.warning("footer_import_falhou", nome=nome, erro=str(exc))
            return

        self._footer_toast(f"Perfil importado: {nome} -> {path}")
        logger.info("footer_import_ok", nome=nome, path=str(path))

        refresh = getattr(self, "_reload_profiles_store", None)
        if refresh is not None:
            refresh(select_name=nome)

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
                "Asset 'meu_perfil.json' não encontrado — Restaurar Default indisponível."
            )
            logger.warning(
                "footer_restore_default_asset_ausente",
                path=str(_MEU_PERFIL_ASSET),
            )
            return

        if not gui_dialogs.confirm_restore_default(parent=window):
            self._footer_toast("Restauração cancelada.")
            return

        try:
            from hefesto_dualsense4unix.profiles.schema import Profile

            raw = json.loads(_MEU_PERFIL_ASSET.read_text(encoding="utf-8"))
            profile = Profile.model_validate(raw)
            save_profile(profile)
        except Exception as exc:
            self._footer_toast(f"Falha ao restaurar: {exc}")
            logger.warning("footer_restore_default_falhou", erro=str(exc))
            return

        # Recarrega DraftConfig a partir do perfil restaurado
        try:
            perfil_disco = load_profile(_MEU_PERFIL_NOME)
            self.draft = DraftConfig.from_profile(perfil_disco)
            logger.info("footer_restore_default_draft_recarregado")
        except Exception as exc:
            logger.warning("footer_restore_default_draft_falhou", erro=str(exc))

        destino = profiles_dir() / f"{_MEU_PERFIL_NOME}.json"
        self._footer_toast(f"meu_perfil restaurado para {destino}")

        _refresh_all_tabs(self)

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
        "_refresh_mouse_from_draft",
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
