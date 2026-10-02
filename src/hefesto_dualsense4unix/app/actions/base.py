"""Helpers compartilhados por todos os mixins da GUI."""
# ruff: noqa: E402
from __future__ import annotations

import contextlib
from collections.abc import Callable
from typing import Any

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import GLib, Gtk

from hefesto_dualsense4unix.app.actions import relancar
from hefesto_dualsense4unix.app.ipc_bridge import _get_executor
from hefesto_dualsense4unix.utils.logging_config import get_logger

logger = get_logger(__name__)


def numero_do_controle(entry: dict[str, Any]) -> int:
    """Número com que UM controle se identifica na interface inteira.

    Fonte única da regra (COR-01/D6): é o ``player_slot`` de sessão — a
    identidade ESTÁVEL, que sobrevive a desconectar e reconectar e que a CLI e o
    applet também usam. Sem slot (controle sem MAC, registro ainda ausente) cai
    na posição 1-based da lista.

    Existia uma cópia dessa regra em cada tela, e a aba Início usava a POSIÇÃO no
    loop em vez do slot: com um controle só, ela dizia "Controle 1" enquanto o
    cabeçalho, olhando o mesmo controle, dizia "Sony 3". Duas verdades na mesma
    janela sobre qual é o "Controle 1".

    ``player`` (o número do JOGADOR, que vem do daemon) responde uma pergunta
    diferente — "este controle está jogando agora, e como quem?" —, e por isso
    é ``None`` fora do co-op. Mas desde a MESA-CHEIA-12 (15/08/2026) ele já não
    é outro NÚMERO: `CoopManager.numeros_de_jogador()` o tira da mesma fila de
    chegada que dá o ``player_slot``, e é a mesma fila que escolhe o desenho
    aceso na barra do controle. Quando os dois existem, eles são iguais — antes
    disso divergiam, e o card dizia "jogador 2" no controle que acendia 4.
    """
    slot = entry.get("player_slot")
    if isinstance(slot, int) and not isinstance(slot, bool):
        return slot
    indice = entry.get("index")
    if isinstance(indice, int) and not isinstance(indice, bool):
        return indice + 1
    return 1


_MUDANCAS_QUE_SAO_ESCRITA: frozenset[str] = frozenset({"steam_input_do_jogo"})


class WidgetAccessMixin:
    """Acesso comum ao `Gtk.Builder` via `self.builder`."""

    builder: Gtk.Builder

    _escolha_pendente: dict[str, str] | None = None

    _maquina_pendente: dict[str, Any] | None = None


    _RESP_DEPOIS = 210
    _RESP_FECHAR_E_ABRIR = 211

    def _perguntar_antes_de_relancar(
        self,
        *,
        mudanca: str,
        valor: str | None,
        aplicar: Callable[[], None],
        ao_nao_relancar: Callable[[str], None] | None = None,
    ) -> bool:
        """True se assumiu o gesto (vai perguntar); False para aplicar direto."""
        if mudanca not in relancar.EXIGEM_RELANCAR:
            return False
        jogo_aberto = bool(getattr(self, "_jogo_aberto", False))
        if not relancar.precisa_perguntar(
            mudanca=mudanca, jogo_aberto=jogo_aberto
        ):
            return False
        try:
            self._relancar_decidir(mudanca, valor, True, aplicar, ao_nao_relancar)
        except Exception as exc:
            logger.warning("relancar_dialogo_nao_nasceu", erro=str(exc))
            return False
        return True

    def _relancar_decidir(
        self,
        mudanca: str,
        valor: str | None,
        jogo: object,
        aplicar: Callable[[], None],
        ao_nao_relancar: Callable[[str], None] | None = None,
    ) -> bool:
        """Na thread do GTK: sem jogo aplica; com jogo, pergunta."""
        nome_do_jogo = jogo if isinstance(jogo, str) and jogo else None

        def _resposta(dialog: Any, resposta: int) -> None:
            with contextlib.suppress(Exception):
                dialog.destroy()
            if resposta == self._RESP_FECHAR_E_ABRIR:
                aplicar()
                self._toast_do_relancar(
                    relancar.toast_da_escolha("fechar_e_abrir", jogo=nome_do_jogo)
                )
                self._relancar_o_jogo()
            elif resposta == self._RESP_DEPOIS:
                if mudanca in _MUDANCAS_QUE_SAO_ESCRITA:
                    aplicar()
                else:
                    logger.info(
                        "relancar_adiado_sem_guardar", mudanca=mudanca
                    )
                self._toast_do_relancar(
                    relancar.toast_da_escolha(
                        "na_proxima_abertura",
                        jogo=nome_do_jogo,
                        guardou=mudanca in _MUDANCAS_QUE_SAO_ESCRITA,
                    )
                )
                if ao_nao_relancar is not None:
                    with contextlib.suppress(Exception):
                        ao_nao_relancar("na_proxima_abertura")
            else:
                self._toast_do_relancar(relancar.toast_da_escolha("cancelar"))
                if ao_nao_relancar is not None:
                    with contextlib.suppress(Exception):
                        ao_nao_relancar("cancelar")
                with contextlib.suppress(Exception):
                    sincronizar = getattr(self, "_sincronizar_caixa_do_steam_input", None)
                    if callable(sincronizar):
                        sincronizar()

        from hefesto_dualsense4unix.app.actions.daemon_actions import (
            build_consentimento_dialog,
        )

        dialog = build_consentimento_dialog(
            getattr(self, "window", None),
            titulo=relancar.TITULO,
            corpo=relancar.corpo_do_dialogo(
                mudanca=mudanca, valor=valor, jogo=nome_do_jogo
            ),
            botoes=[
                (relancar.ROTULO_CANCELAR, Gtk.ResponseType.CANCEL),
                (relancar.ROTULO_DEPOIS, self._RESP_DEPOIS),
                (relancar.ROTULO_FECHAR, self._RESP_FECHAR_E_ABRIR),
            ],
            on_response=_resposta,
            destrutivo=self._RESP_FECHAR_E_ABRIR,
        )
        with contextlib.suppress(Exception):
            dialog.show_all()
        return False

    def _relancar_o_jogo(self) -> None:
        """Fecha a Steam e o jogo, espera, e ABRE o jogo de novo."""

        def _fazer() -> None:
            from hefesto_dualsense4unix.integrations import (
                steam_launch_options as slo,
            )

            appid = None
            with contextlib.suppress(Exception):
                appid = slo.steam_game_running_appid()

            fechou = False
            with contextlib.suppress(Exception):
                fechou = bool(slo.stop_steam())

            reabriu = False
            if appid is not None:
                with contextlib.suppress(Exception):
                    reabriu = bool(slo.start_steam_game(appid))

            GLib.idle_add(
                self._toast_do_relancar,
                relancar.toast_do_relancamento(
                    fechou=fechou, reabriu=reabriu, appid=appid
                ),
            )

        with contextlib.suppress(Exception):
            _get_executor().submit(_fazer)

    def _toast_do_relancar(self, texto: str) -> None:
        """Onde o resultado do diálogo aparece. A aba dona pode especializar."""
        for nome in ("_toast_profile", "_status_toast_home", "_status_toast"):
            metodo = getattr(self, nome, None)
            if callable(metodo):
                with contextlib.suppress(Exception):
                    if nome == "_status_toast":
                        metodo("home", texto)
                    else:
                        metodo(texto)
                    return
        logger.info("relancar_toast_sem_destino", texto=texto)

    def _get(self, widget_id: str) -> Any:
        return self.builder.get_object(widget_id)

    def _set_label(self, widget_id: str, text: str) -> None:
        widget = self._get(widget_id)
        if widget is not None:
            widget.set_text(text)

    def _status_toast(self, context: str, msg: str) -> None:
        """Mostra ``msg`` na statusbar, mantendo no máximo 1 mensagem por contexto."""
        bar = self._get("status_bar")
        if bar is None:
            return
        ctx_id = bar.get_context_id(context)
        bar.pop(ctx_id)
        bar.push(ctx_id, msg)


__all__ = ["WidgetAccessMixin", "numero_do_controle"]
