"""Seção 4 da aba Configurações — ajustes do programa, não dos controles."""
from __future__ import annotations

import contextlib
import html
from typing import Any

from hefesto_dualsense4unix.app.actions.config.moldura import (
    RECIBO_GUARDADO,
    VALE_JA,
    rotulo_de_apoio,
)
from hefesto_dualsense4unix.app.ambiente import (
    AMBIENTES,
    ambiente_efetivo,
    ambiente_lido,
    frase_do_detectado,
    gravar_correcao_de_ambiente,
    mensagem_da_bandeja,
)
from hefesto_dualsense4unix.app.escala import (
    CHAVE_ESCALA,
    DEGRAUS_DE_ESCALA,
    degrau_da_escala,
    escala_gravada,
)
from hefesto_dualsense4unix.app.gui_prefs import set_pref
from hefesto_dualsense4unix.app.ipc_bridge import run_in_thread
from hefesto_dualsense4unix.app.widgets.segmented_selector import SegmentedSelector
from hefesto_dualsense4unix.integrations.desktop_notifications import (
    statusnotifierwatcher_available,
)
from hefesto_dualsense4unix.utils.i18n import _
from hefesto_dualsense4unix.utils.logging_config import get_logger

logger = get_logger(__name__)

TITULO = "A janela"

DICA: str | None = None

_ESPACAMENTO_DA_FILEIRA = 8

#: `rumble_actions.py:688`.
_COR_DE_ATENCAO = "#ffb86c"

_COR_DE_CONFIRMACAO = "#50fa7b"

_QUANDO_O_TAMANHO_APARECE = "O tamanho novo vale na próxima vez que você abrir o Hefesto."

_ONDE_SE_LIGA_JUNTO = (
    "Este valor é um espelho. Quem liga e desliga é o interruptor da aba "
    "Sistema."
)

_ROTULOS_DE_DEGRAU = {
    "compacto": "Compacto",
    "normal": "Normal",
    "grande": "Grande",
}


def montar(host: Any, caixa: Any) -> None:
    """Monta a seção dentro de `caixa` — a caixa interna da moldura."""
    host._config_recibos = []

    caixa.pack_start(_fileira_do_tamanho(host), False, False, 0)
    caixa.pack_start(_fileira_do_ambiente(host), False, False, 0)
    caixa.pack_start(rotulo_de_apoio(frase_do_detectado(ambiente_lido())), False, False, 0)

    bandeja = rotulo_de_apoio("Conferindo o ícone na barra do sistema.")
    host._config_bandeja_rotulo = bandeja
    host._config_bandeja_watcher = None
    caixa.pack_start(bandeja, False, False, 0)
    _sondar_a_bandeja(host)

    espelho = _fileira_do_autostart(host)
    if espelho is not None:
        caixa.pack_start(espelho, False, False, 0)


def _fileira_do_tamanho(host: Any) -> Any:
    """A fileira do tamanho: rótulo, três degraus, e o que está gravado marcado."""
    linha, _rotulo = _fileira(
        "Tamanho do texto:",
        dica=f"{_QUANDO_O_TAMANHO_APARECE} {VALE_JA}",
    )
    seletor = SegmentedSelector(wrap=True)
    seletor.set_items(
        [
            (nome, _ROTULOS_DE_DEGRAU.get(nome, nome.capitalize()))
            for nome in DEGRAUS_DE_ESCALA
        ]
    )
    with contextlib.suppress(Exception):
        seletor.set_active_id(degrau_da_escala(escala_gravada()))
    seletor.set_hexpand(False)
    seletor.connect("changed", lambda sel: _ao_trocar_o_tamanho(host, sel))
    host._config_escala_seletor = seletor
    linha.pack_start(seletor, False, False, 0)
    host._config_recibo_do_tamanho = _recibo(host, linha)
    return linha


def _ao_trocar_o_tamanho(host: Any, seletor: Any) -> None:
    """Grava o degrau escolhido e ESCREVE O RECIBO."""
    nome = seletor.get_active_id()
    valor = DEGRAUS_DE_ESCALA.get(nome) if nome is not None else None
    if valor is None:
        return
    set_pref(CHAVE_ESCALA, valor)
    logger.info("config_escala_gravada", degrau=nome, delta=valor)
    _escrever_o_recibo(host, getattr(host, "_config_recibo_do_tamanho", None))


def _fileira_do_ambiente(host: Any) -> Any:
    """A fileira do ambiente: rótulo com a dica do desenho, e os três nomes."""
    linha, _rotulo = _fileira(
        "Ambiente:",
        dica=(
            "O ícone na barra do sistema depende do ambiente. No COSMIC aparece "
            "sozinho; no GNOME precisa de uma extensão instalada. "
            + VALE_JA
        ),
    )
    seletor = SegmentedSelector(wrap=True)
    seletor.set_items(list(AMBIENTES))
    with contextlib.suppress(Exception):
        seletor.set_active_id(ambiente_efetivo())
    seletor.set_hexpand(False)
    seletor.connect("changed", lambda sel: _ao_corrigir_o_ambiente(host, sel))
    host._config_ambiente_seletor = seletor
    linha.pack_start(seletor, False, False, 0)
    host._config_recibo_do_ambiente = _recibo(host, linha)
    return linha


def _ao_corrigir_o_ambiente(host: Any, seletor: Any) -> None:
    """Grava a correção, escreve o RECIBO e repinta a mensagem da bandeja."""
    escolha = seletor.get_active_id()
    if escolha is None:
        return
    gravar_correcao_de_ambiente(escolha)
    logger.info("config_ambiente_corrigido", escolha=escolha)
    _escrever_o_recibo(host, getattr(host, "_config_recibo_do_ambiente", None))
    _pintar_a_bandeja(host)


def _recibo(host: Any, linha: Any) -> Any:
    """Um rótulo VAZIO no fim da fileira, e o registro dele na lista do host."""
    from gi.repository import Gtk

    rotulo = Gtk.Label(label="")
    rotulo.set_xalign(0.0)
    linha.pack_start(rotulo, False, False, 0)
    with contextlib.suppress(Exception):
        host._config_recibos.append(rotulo)
    return rotulo


def _escrever_o_recibo(host: Any, rotulo: Any) -> None:
    """Escreve o recibo NESTA fileira e apaga o das outras."""
    if rotulo is None:
        return
    with contextlib.suppress(Exception):
        for outro in getattr(host, "_config_recibos", ()):
            if outro is not rotulo:
                outro.set_text("")
    with contextlib.suppress(Exception):
        rotulo.set_markup(
            f'<span foreground="{_COR_DE_CONFIRMACAO}">'
            f"{html.escape(_(RECIBO_GUARDADO), quote=False)}</span>"
        )


def _sondar_a_bandeja(host: Any) -> None:
    """Pergunta, FORA da thread do GTK, se a barra do sistema recebe o ícone."""

    def _pousou(presente: Any) -> bool:
        host._config_bandeja_watcher = bool(presente)
        _pintar_a_bandeja(host)
        return False

    def _falhou(exc: Exception) -> bool:
        logger.debug("config_bandeja_sonda_falhou", erro=str(exc))
        host._config_bandeja_watcher = False
        _pintar_a_bandeja(host)
        return False

    run_in_thread(statusnotifierwatcher_available, _pousou, _falhou)


def _pintar_a_bandeja(host: Any) -> None:
    """Escreve no rótulo o estado do ícone — e a instrução quando ele não sobe."""
    rotulo = getattr(host, "_config_bandeja_rotulo", None)
    presente = getattr(host, "_config_bandeja_watcher", None)
    if rotulo is None or presente is None:
        return
    with contextlib.suppress(Exception):
        texto = _(mensagem_da_bandeja(ambiente_efetivo(), presente))
        if presente:
            rotulo.set_text(texto)
            return
        rotulo.set_markup(
            f'<span foreground="{_COR_DE_ATENCAO}">'
            f"{html.escape(texto, quote=False)}</span>"
        )


def _fileira_do_autostart(host: Any) -> Any:
    """O espelho do interruptor da aba Sistema. Só o espelho, desde a LEX-4."""
    interruptor = host._get("daemon_autostart_switch")
    if interruptor is None:
        return None

    linha, _rotulo = _fileira("Ligar junto com o computador")
    estado = _rotulo_simples("")
    with contextlib.suppress(Exception):
        estado.set_tooltip_text(_(_ONDE_SE_LIGA_JUNTO))
    host._config_autostart_estado = estado
    linha.pack_start(estado, False, False, 0)

    _espelhar_o_autostart(estado, interruptor)
    interruptor.connect(
        "notify::active", lambda widget, _pspec: _espelhar_o_autostart(estado, widget)
    )
    return linha


def _espelhar_o_autostart(estado: Any, interruptor: Any) -> None:
    """Copia o estado do interruptor para o rótulo. Uma direção só."""
    with contextlib.suppress(Exception):
        estado.set_text(_("Ligado") if interruptor.get_active() else _("Desligado"))


# `_abrir_a_aba_sistema` VIVEU AQUI e saiu com o botão dela (LEX-4, 25/08/2026).


def _fileira(titulo: str, *, dica: str | None = None) -> tuple[Any, Any]:
    """Uma fileira "rótulo + controle", devolvida como `(caixa, rótulo)`."""
    from gi.repository import Gtk

    caixa = Gtk.Box(
        orientation=Gtk.Orientation.HORIZONTAL, spacing=_ESPACAMENTO_DA_FILEIRA
    )
    rotulo = _rotulo_simples(titulo)
    if dica is not None:
        rotulo.set_tooltip_text(_(dica))
    caixa.pack_start(rotulo, False, False, 0)
    return caixa, rotulo


def _rotulo_simples(texto: str) -> Any:
    """Rótulo curto de fileira: alinhado à esquerda, sem quebra."""
    from gi.repository import Gtk

    rotulo = Gtk.Label(label=_(texto))
    rotulo.set_xalign(0.0)
    return rotulo
