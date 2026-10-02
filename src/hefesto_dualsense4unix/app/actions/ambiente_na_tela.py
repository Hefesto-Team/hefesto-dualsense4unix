"""O que o Hefesto sabe sobre a MÁQUINA — não sobre o controle (T-12, ONDA0-Z7).

Arquivo NOVO, nasce vazio de dono de propósito (§5 da sprint O AMBIENTE
PRESUMIDO 01): três frases puras — recebem o dicionário do `state_full` e
devolvem markup, no molde de
``daemon_actions.descrever_deteccao_de_janela``, que é o exemplo bom desta
casa (lê o par honesto em vez do trinco de mão única, escapa o que vem de
fora, degrada com frase em vez de sumir). Nenhuma delas nomeia o mecanismo —
dizem o que aconteceu com a máquina dela, nunca o nome do backend/protocolo.

As três:

* :func:`descrever_teclado_na_tela` — lê ``osk_disponivel``. Publicada por
  ``daemon/ipc_handlers.py:1861`` desde 10/08/2026 (TECLADO-QUE-NAO-DIGITA-01)
  e **zero leitores em `app/`** até aqui (medido em §3.6 da sprint) — é a
  chave órfã que o portão de completude, em
  ``tests/unit/test_ambiente_presumido_01_o_que_a_maquina_nao_tem.py``, existe
  para nunca mais deixar acontecer;
* :func:`descrever_display_grafico` — lê ``window_detect_backend`` e
  ``window_detect_reason``. Complementa (não substitui)
  ``daemon_actions.descrever_deteccao_de_janela``: aquela fala da PROMESSA
  ("o perfil troca sozinho?"), esta fala do MECANISMO ("o Hefesto enxerga
  alguma janela, hoje?") — as duas cabem lado a lado sem se repetir porque
  perguntam coisas diferentes;
* :func:`descrever_steam_encontrada` — o layout de Steam achado, ou onde
  procurou. **Ainda sem publicador**: nenhuma frente desta sprint escreve a
  chave em `state_full` (Z7-C só entrega `proton_pin.steam_root_ou_recusa`,
  sem tocar `ipc_handlers.py` — ver §5/§10 da sprint). Por isso a função
  nasce sempre no ramo "não consegui ler" contra um daemon de hoje — o que é
  a resposta HONESTA, não um defeito desta função. Publicar a chave
  (``steam_layout_achado``, o nome que esta função lê) é gancho da Onda 5 ou
  da Onda 11, nomeado em §10 da sprint.

O QUE ESTE ARQUIVO NÃO FAZ (§7 da sprint, regra para toda a frente): nenhuma
das três frases cita "cabo", "rádio", "Bluetooth" ou "sem fio" — elas falam de
display, teclado e Steam, coisas do COMPUTADOR, não do controle. Uma frase de
ambiente que mencionasse transporte seria uma promessa que ninguém mediu
(nenhuma das 308 linhas do mapa de canais alcança esta frente — §3.8).

Quem PENDURA estas frases na tela é a Onda 10 · Navegação (a do teclado) e a
Onda 11 · Sistema (a do display e da Steam) — ver §10 da sprint. Este módulo
só entrega a primitiva; não importa GTK, não sabe que existe uma janela.
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


