"""O que o Hefesto sabe sobre a MÁQUINA — não sobre o controle (T-12, ONDA0-Z7).

Uma frase pura: recebe o dicionário do `state_full` e devolve markup, no
molde de ``daemon_actions.descrever_deteccao_de_janela`` (lê o par honesto em
vez do trinco de mão única, escapa o que vem de fora, degrada com frase em vez
de sumir). Ela não nomeia o mecanismo — diz o que aconteceu com a máquina do usuário,
nunca o nome do backend/protocolo.

* :func:`descrever_display_grafico` — lê ``window_detect_backend`` e
  ``window_detect_reason``. Complementa (não substitui)
  ``daemon_actions.descrever_deteccao_de_janela``: aquela fala da PROMESSA
  ("o perfil troca sozinho?"), esta fala do MECANISMO ("o Hefesto enxerga
  alguma janela, hoje?").

A frase não cita "cabo", "rádio", "Bluetooth" ou "sem fio": fala do display,
coisa do COMPUTADOR, não do controle. Quem a pendura na tela é a aba Sistema
(`interface/pacotes/a09_sistema.py`).
"""
from __future__ import annotations


def _escapar_markup(texto: str) -> str:
    """Escapa `&`, `<`, `>` para markup Pango — mesma régua de `daemon_actions`."""
    return texto.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def descrever_display_grafico(state: object) -> str:
    """O Hefesto enxerga QUALQUER janela nesta máquina, agora?"""
    if not isinstance(state, dict) or "window_detect_backend" not in state:
        return "Detector de janela: não consegui ler — o serviço pode estar desligado."
    backend = state.get("window_detect_backend")
    if not isinstance(backend, str) or backend in ("", "null"):
        return (
            "Detector de janela: nenhum caminho disponível nesta sessão "
            "gráfica."
        )
    seeing = bool(state.get("window_detect_seeing"))
    if seeing:
        return "Detector de janela: enxergando — o Hefesto vê qual programa está na frente."
    motivo = state.get("window_detect_reason")
    if isinstance(motivo, str) and motivo:
        return f"Detector de janela: sem ver nada agora ({_escapar_markup(motivo)})."
    return "Detector de janela: sem ver nada agora."


