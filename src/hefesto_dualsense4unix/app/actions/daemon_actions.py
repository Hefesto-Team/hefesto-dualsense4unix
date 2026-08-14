"""Aba Sistema: o Hefesto está funcionando? liga sozinho? está saudável?

LEIGO-03: a aba se chamava "Daemon" e mostrava a unit do systemd, a saída crua
de `systemctl status` e toasts com `rc=N`. O mecanismo continua igual — quem
manda no serviço ainda é o systemd `--user`; o que mudou é que ele não é mais
assunto de quem usa. Os nomes técnicos (`SERVICE_NORMAL`, rc, stderr) vivem no
código e no log; a tela responde às três perguntas do título, e o detalhe
técnico fica no painel "Detalhes técnicos" para quem for relatar um problema.

SIMPLIFY-UNIT-01: unit única `hefesto-dualsense4unix.service`. Sem dropdown de seleção.
BUG-DAEMON-STATUS-MISMATCH-01: `_daemon_status()` cruza 3 fontes (systemd
  is-active, is-enabled, pid file) para apresentar label PT-BR fiel ao estado
  real. Evita mostrar "failed" quando o daemon está vivo fora do systemd.
"""
# ruff: noqa: E402
from __future__ import annotations

import contextlib
import os
import re
import signal
import subprocess
from collections.abc import Sequence
from pathlib import Path
from typing import Any, Literal

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import GLib, Gtk

from hefesto_dualsense4unix.app.actions.base import WidgetAccessMixin
from hefesto_dualsense4unix.app.ipc_bridge import _get_executor
from hefesto_dualsense4unix.daemon.service_install import SERVICE_NORMAL, ServiceInstaller
from hefesto_dualsense4unix.integrations.steam_launch_options import juntar_rotulos
from hefesto_dualsense4unix.utils.logging_config import get_logger

logger = get_logger(__name__)

# Tipo canônico para o estado do daemon (BUG-DAEMON-STATUS-MISMATCH-01).
DaemonStatus = Literal["online_systemd", "online_avulso", "iniciando", "offline"]

#: LEIGO-03: o toast dizia "systemctl start hefesto-...service → rc=0" — o
#: comando cru e um código que só um dev distingue (rc=0 é sucesso, rc=1 é
#: falha, e os dois "pareciam" iguais na barra de status). Cada ação diz o que
#: MUDOU para quem usa; o rc vai para o log.
_SYSTEMCTL_OK_MSG: dict[str, str] = {
    "start": "Pronto — Hefesto ligado.",
    "stop": "Hefesto desligado.",
    "enable": "Pronto — o Hefesto vai ligar sozinho com o computador.",
    "disable": "Pronto — o Hefesto não vai mais ligar sozinho.",
}
_SYSTEMCTL_FAIL_MSG: dict[str, str] = {
    "start": "Não consegui ligar o Hefesto",
    "stop": "Não consegui desligar o Hefesto",
    "enable": "Não consegui deixar o Hefesto ligando sozinho",
    "disable": "Não consegui desligar o início automático",
}


#: JANELA-CEGA-01: os dez motivos de leitura cega do detector de janela,
#: traduzidos. As chaves são o vocabulário publicado em
#: `window_detect_reason` — as constantes moram em
#: `integrations/window_backends/xlib.py` (as seis do X11),
#: `integrations/window_backends/null.py` e `integrations/window_detect.py`.
#: Cada frase diz o que ACONTECEU com a janela dela, não o nome do mecanismo.
MOTIVO_DA_CEGUEIRA_EM_PORTUGUES: dict[str, str] = {
    # O caso desta máquina: em COSMIC/Wayland o detector só vê janelas abertas
    # pelo XWayland, e a janela da frente costuma ser nativa do Wayland.
    "sem_foco_x": (
        "a janela da frente é nativa do Wayland, e o Hefesto só enxerga as que "
        "passam pelo XWayland"
    ),
    "sem_conexao_x": "o Hefesto não conseguiu falar com o XWayland",
    "foco_sem_id": "o sistema não disse qual janela está na frente",
    "foco_sem_top_level": "a janela da frente não é a janela de um programa",
    "foco_discorda_do_net_active": (
        "o sistema deu duas respostas diferentes sobre qual janela está na frente"
    ),
    "erro_de_consulta": "deu erro ao perguntar qual janela está na frente",
    "sem_backend": (
        "neste sistema não há como perguntar qual janela está na frente"
    ),
    "cascata_wayland_sem_leitura": (
        "o Wayland deste computador não conta qual janela está na frente"
    ),
    "janela_sem_classe": "a janela da frente não se identifica",
    "backend_sem_motivo": "não sei dizer o motivo",
}

#: Nome do backend -> como ela chamaria a coisa. "xlib"/"portal"/"wlrctl"/"null"
#: são os valores publicados em `window_detect_backend`.
_BACKEND_EM_PORTUGUES: dict[str, str] = {
    "xlib": "pelo XWayland",
    "portal": "pelo portal do sistema",
    "wlrctl": "pelo wlrctl",
    "null": "por nenhum caminho",
}

#: O texto que abre a linha. Fica junto do valor porque a aba Sistema não tem
#: folga de altura para um rótulo de título só dele (medido: 30px de custo,
#: contra 74px de folga na aba).
_PREFIXO_DETECCAO = "<b>Trocar de perfil ao abrir o jogo:</b> "


def _escapar_markup(texto: str) -> str:
    """Escapa `&`, `<` e `>` para o rótulo com `use-markup`.

    Vale para QUALQUER coisa que venha do daemon: a wm_class e o motivo são
    strings de fora, e um `&` numa delas fecha o parser do Pango — o rótulo
    fica em branco e a linha honesta desaparece justamente quando o nome da
    janela é estranho. Mesma escapada que `_refresh_storm_diag` já faz.
    """
    return texto.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def descrever_deteccao_de_janela(state: object) -> str:
    """Markup da linha do detector de janela na aba Sistema (JANELA-CEGA-01).

    Pura de propósito. Lê os campos `window_detect_*` do `daemon.state_full`
    (publicados por `daemon/ipc_handlers.py:_window_detect_payload`) e responde,
    em linguagem de quem usa, à única pergunta que importa: **o perfil troca
    sozinho quando ela abre o jogo, agora?**

    Por que não basta ler `window_detect_healthy`: ele é um trinco de mão única
    (nunca cai depois de subir) e `window_detect_last_class` é sticky. Medido ao
    vivo em 28/07, os dois afirmavam saúde enquanto o backend devolvia `None` a
    2 Hz. Quem denuncia a cegueira é `window_detect_seeing` (decai e volta) com
    `window_detect_reason` ao lado — e é esse par que esta frase usa.
    """
    if not isinstance(state, dict) or "window_detect_backend" not in state:
        return (
            _PREFIXO_DETECCAO
            + "não consegui ler — o Hefesto pode estar desligado."
        )
    backend = state.get("window_detect_backend")
    if not isinstance(backend, str) or backend in ("", "null"):
        return (
            _PREFIXO_DETECCAO
            + '<span foreground="#ffb86c">não funciona neste sistema</span> — o '
            "Hefesto não tem como saber qual janela está na frente, então o "
            "perfil não troca sozinho. Troque pela aba Perfis ou por PS + D-pad."
        )
    vendo = bool(state.get("window_detect_seeing"))
    if vendo:
        classe = state.get("window_detect_current_class")
        if not isinstance(classe, str) or not classe or classe == "unknown":
            classe = state.get("window_detect_last_class")
        onde = (
            f" (na frente agora: {_escapar_markup(classe)})"
            if isinstance(classe, str) and classe and classe != "unknown"
            else ""
        )
        return (
            _PREFIXO_DETECCAO
            + f'<span foreground="#50fa7b">funcionando</span>{onde}.'
        )
    motivo = state.get("window_detect_reason")
    frase = (
        MOTIVO_DA_CEGUEIRA_EM_PORTUGUES.get(motivo)
        if isinstance(motivo, str)
        else None
    )
    if frase is None and isinstance(motivo, str) and motivo:
        # Motivo novo, vindo de um daemon mais novo que esta janela: dizer o
        # código cru é feio e honesto; inventar explicação é o defeito antigo.
        frase = f"motivo: {_escapar_markup(motivo)}"
    if frase is None:
        frase = MOTIVO_DA_CEGUEIRA_EM_PORTUGUES["backend_sem_motivo"]
    # O "por onde o Hefesto procura" só entra quando o motivo NÃO nomeia o
    # caminho: "a janela da frente é nativa do Wayland, e o Hefesto só enxerga
    # as que passam pelo XWayland. O Hefesto procura pelo XWayland." dizia a
    # mesma coisa duas vezes na frase que ela mais vai ler.
    caminho = _BACKEND_EM_PORTUGUES.get(backend, f"por {_escapar_markup(backend)}")
    nome_do_caminho = caminho.split(" ", 1)[-1]
    onde_procura = (
        "" if nome_do_caminho in frase else f" O Hefesto procura {caminho}."
    )
    return (
        _PREFIXO_DETECCAO
        + f'<span foreground="#ffb86c">sem ver a janela agora</span> — {frase}.'
        f"{onde_procura} Enquanto está assim, o perfil não troca sozinho."
    )


def _apply_result_count(value: object) -> int:
    """Conta um campo do resultado de ``apply_wrapper_to_all_games``.

    O contrato (PATH-06) devolve ``{applied, skipped, errors}``; cada campo
    pode vir como contagem (int) ou como lista de itens — tolera os dois.
    ``bool`` é rejeitado (subclasse de int) por blindagem de payload.
    """
    if isinstance(value, bool):
        return 0
    if isinstance(value, int):
        return max(value, 0)
    if isinstance(value, (list, tuple, set)):
        return len(value)
    return 0


def format_apply_wrapper_result(result: object) -> str:
    """Mensagem pro leigo a partir do dict do ``apply_wrapper_to_all_games``.

    Pura (testável sem GTK) — o miolo do toast do botão "Aplicar aos jogos da
    Steam". Resposta fora do contrato vira recusa honesta, nunca "Pronto".
    """
    if not isinstance(result, dict):
        return (
            "Não consegui aplicar — resposta inesperada; veja os "
            "'Detalhes técnicos'."
        )
    applied = _apply_result_count(result.get("applied"))
    skipped = _apply_result_count(result.get("skipped"))
    errors = _apply_result_count(result.get("errors"))
    if applied:
        msg = (
            f"Pronto — {applied} jogo(s) agora abrem pelo hefesto-launch "
            "(as suas opções foram preservadas; backup ao lado de cada "
            "arquivo)."
        )
    elif errors == 0:
        msg = (
            "Nada a mudar — os jogos já abrem pelo hefesto-launch (ou não "
            "encontrei jogos da Steam neste computador)."
        )
    else:
        msg = "Nenhum jogo foi alterado."
    if skipped:
        msg += f" {skipped} jogo(s) ficaram como estavam."
    if errors:
        msg += (
            f" Atenção: {errors} jogo(s) falharam — veja os "
            "'Detalhes técnicos'."
        )
    return msg


def build_consentimento_dialog(
    parent: Any,
    *,
    titulo: str,
    corpo: str,
    botoes: Sequence[tuple[str, int]],
    on_response: Any,
    destrutivo: int | None = None,
) -> Gtk.MessageDialog:
    """O construtor de diálogo de consentimento — um dono do widget, N políticas.

    RELANCAR-01 (08/08/2026): extraído de `build_steam_close_consent_dialog`,
    que passou a ser uma casca sobre ele. O motivo de extrair em vez de copiar é
    o mesmo que fez o original existir: consentimento pesado não pode divergir
    entre botões. Duas cópias divergem no primeiro conserto.

    `botoes` é `[(rótulo, resposta), ...]`, na ordem em que entram — a resposta
    de cancelar deve vir primeiro, e é ela o `set_default_response` (a tecla Esc
    e o Enter distraído caem no que não faz nada).

    `destrutivo` marca UMA resposta com a classe `destructive-action`, a mesma do
    botão "Desligar Hefesto": é o que separa visualmente o botão que toca no
    processo dela dos que não tocam.

    Temado e NÃO-bloqueante (`connect("response")`, nunca `run()`) — há portão
    AST que reprova o contrário.
    """
    dialog = Gtk.MessageDialog(
        transient_for=parent,
        flags=0,
        message_type=Gtk.MessageType.QUESTION,
        buttons=Gtk.ButtonsType.NONE,
        text=titulo,
    )
    with contextlib.suppress(Exception):
        dialog.get_style_context().add_class("hefesto-dualsense4unix-window")
    dialog.format_secondary_text(corpo)
    for rotulo, resposta in botoes:
        botao = dialog.add_button(rotulo, resposta)
        if destrutivo is not None and resposta == destrutivo:
            with contextlib.suppress(Exception):
                botao.get_style_context().add_class("destructive-action")
    if botoes:
        dialog.set_default_response(botoes[0][1])
    dialog.connect("response", on_response)
    return dialog


def build_steam_close_consent_dialog(
    parent: Any,
    *,
    titulo: str,
    corpo: str,
    rotulo_ok: str,
    on_response: Any,
) -> Gtk.MessageDialog:
    """Diálogo ÚNICO de "posso fechar a Steam?" — HONESTIDADE-STEAM-01.

    Existe UM lugar que pede este consentimento porque a consequência é
    pesada e não pode divergir entre botões: `stop_steam()` manda
    `steam -shutdown` e, se a Steam não sair em 30 s, ESCALA para
    `pkill -TERM` e depois `-KILL`. Matar processo da usuária às costas dela
    é exatamente o que a auditoria proíbe — daí o sim explícito ser
    pré-requisito de todo caminho que fecha a Steam (aba Sistema E aba
    Emulação; a de Emulação importa esta função em vez de duplicar o texto).

    Temado e NÃO-bloqueante (`connect("response")`, nunca `run()`), padrão de
    `_build_proton_lock_confirm_dialog`/`gui_dialogs._apply_app_theme`.
    """
    # RELANCAR-01: o widget passou a ser construído por
    # `build_consentimento_dialog`; esta função continua sendo o ÚNICO lugar que
    # define a POLÍTICA de "posso fechar a Steam?" — os dois botões, o rótulo e
    # o default. Quem chamava não muda uma linha.
    return build_consentimento_dialog(
        parent,
        titulo=titulo,
        corpo=corpo,
        botoes=[
            ("Cancelar", Gtk.ResponseType.CANCEL),
            (rotulo_ok, Gtk.ResponseType.OK),
        ],
        on_response=on_response,
    )


def format_steam_janela_recusa(janela: object) -> str | None:
    """Recusa de `with_steam_closed`, ou None quando a ação chegou a rodar.

    Traduz o status do contrato (`ok`/`jogo_aberto`/`nao_fechou`) para o toast.
    Status desconhecido vira recusa honesta — nunca "Pronto" por omissão.
    """
    if janela == "ok":
        return None
    if janela == "jogo_aberto":
        return (
            "Tem um jogo aberto — não fecho a Steam agora (você perderia o "
            "progresso não salvo). Feche o jogo e clique de novo. Nada foi "
            "mudado."
        )
    if janela == "nao_fechou":
        return (
            "A Steam não fechou — não mexi em nada. Com ela viva a mudança "
            "seria perdida, porque a Steam regrava o arquivo ao sair. "
            "Feche-a pela própria Steam e clique de novo."
        )
    return (
        "Não consegui mexer nos arquivos da Steam — resposta inesperada; "
        "veja os 'Detalhes técnicos'."
    )


def _frase_steam_input(
    rc: int, tag: str | None, jogos: Sequence[str] | None = None
) -> str:
    """Meia-frase sobre o desligar do Steam Input, a partir de rc + tag.

    Fonte da tag: a linha `[steam-input] resultado=<tag>` que o
    `disable_steam_input.sh` passou a emitir (HONESTIDADE-STEAM-01). Sem ela
    (script de instalação antiga) o texto DIZ que não houve confirmação, em
    vez de fingir que houve.

    `jogos` são os rótulos (`rotulo_do_jogo`) dos jogos que estavam com Steam
    Input ligado FORA da allowlist ANTES da execução — medidos por quem chama,
    porque o script não relata appid nenhum na saída. `None` = ninguém mediu.

    D-33 (05/08/2026): o ramo `aplicado` dizia *"a Steam não sequestra mais o
    seu controle"*. Duas mentiras numa frase de sete palavras: nada dizia QUAL
    jogo tinha sido mexido, e "sequestra" descreve como roubo o gesto que ela
    mesma fez na janela da Steam. O que aconteceu de fato é que o Hefesto
    desligou a entrada da Steam num jogo — e a frase agora diz isso, com nome.

    MODO-SIMPLES (mantido): nenhuma destas meias-frases pronuncia o jargão
    "Steam Input". Elas são coladas depois de ``"Controle: "`` no botão
    "Deixar tudo pronto", cujo ponto inteiro é a usuária não precisar aprender
    o vocabulário da Steam para usar o controle dela.
    """
    if tag == "recusado-jogo-aberto":
        return "NÃO mudou — havia um jogo aberto."
    if tag == "adiado-steam-aberta":
        return "NÃO mudou — a Steam continuou aberta."
    if tag == "steam-nao-fechou":
        return "NÃO mudou — a Steam não fechou."
    if rc != 0 or tag == "erro":
        return f"NÃO mudou — a correção falhou (erro {rc})."
    if tag == "nada-a-fazer":
        return "já estava do jeito certo."
    if tag == "aplicado":
        if jogos:
            sujeito = "esse jogo não está" if len(jogos) == 1 else "esses jogos não estão"
            return (
                f"o controle de {juntar_rotulos(jogos)} voltou a ser entregue "
                f"pelo Hefesto, porque {sujeito} na sua lista de exceções."
            )
        if jogos is not None:
            # Medido e vazio: só a chave GLOBAL da Steam foi desligada — não
            # havia jogo fora da lista de exceções, e dizer o contrário seria
            # inventar um jogo.
            return (
                "desliguei o ajuste geral da Steam que assume o controle em "
                "todo jogo; nenhum jogo da sua lista de exceções foi tocado."
            )
        return (
            "o controle voltou a ser entregue pelo Hefesto nos jogos fora da "
            "sua lista de exceções."
        )
    return "a correção rodou sem erro (versão antiga do script, sem confirmação)."


def format_steam_ready_result(
    *,
    janela: object,
    dados: object,
    script_ok: bool = True,
    wrapper_ok: bool = True,
) -> str:
    """Toast do botão "Deixar tudo pronto" — pura, o miolo testável.

    Junta os dois passos que a usuária não deveria precisar distinguir
    ("tem jogos que precisam ativar entrada steam, outros que precisam de
    comandos de inicialização — é uma confusão real") num relato único, e
    reporta cada perna pelo que ela DE FATO fez.
    """
    recusa = format_steam_janela_recusa(janela)
    if recusa is not None:
        return recusa
    if not isinstance(dados, dict):
        return (
            "Não consegui deixar tudo pronto — resposta inesperada; veja os "
            "'Detalhes técnicos'."
        )
    if not script_ok and not wrapper_ok:
        return (
            "Esta instalação está incompleta (faltam as peças que fazem o "
            "ajuste) — rode ./install.sh para atualizar o Hefesto."
        )
    partes: list[str] = []
    if script_ok:
        bruto = dados.get("script")
        if isinstance(bruto, tuple) and len(bruto) == 2:
            rc, saida = bruto
        else:
            rc, saida = 1, ""
        partes.append(
            "Controle: "
            + _frase_steam_input(
                int(rc),
                _tag_do_script(saida),
                _jogos_do_relatorio(dados.get("steam_input_jogos")),
            )
        )
    else:
        partes.append(
            "Controle: não encontrei o script desta correção nesta "
            "instalação (rode ./install.sh)."
        )
    if wrapper_ok:
        partes.append("Jogos: " + format_apply_wrapper_result(dados.get("wrapper")))
    else:
        partes.append(
            "Jogos: esta instalação ainda não sabe ajustar todos de uma vez "
            "— rode ./install.sh."
        )
    return " ".join(partes)


def _tag_do_script(saida: object) -> str | None:
    """`steam_input_result_tag` com import lazy (evita ciclo entre mixins)."""
    from hefesto_dualsense4unix.app.actions.emulation_actions import (
        steam_input_result_tag,
    )

    return steam_input_result_tag(saida if isinstance(saida, str) else "")


def _jogos_do_relatorio(bruto: object) -> list[str] | None:
    """Rótulos de jogo guardados no relatório do worker, ou `None`.

    `None` significa "ninguém mediu" (relatório antigo, medição falhou) — e o
    formatter então evita nomear jogo nenhum em vez de chutar.
    """
    if isinstance(bruto, list) and all(isinstance(x, str) for x in bruto):
        return list(bruto)
    return None


def medir_jogos_com_steam_input() -> list[str] | None:
    """Rótulos dos jogos com Steam Input ligado FORA da allowlist, AGORA.

    D-33: o `disable_steam_input.sh` não diz na saída QUAIS appids mexeu — ele
    só emite `resultado=<tag>`. Quem sabe é o `localconfig.vdf`, e só ANTES da
    execução (depois já foi zerado). Por isso os dois workers medem primeiro e
    guardam o resultado no relatório.

    `None` = não deu para medir; lista vazia = medido, e não havia jogo fora da
    lista de exceções (o caso da chave GLOBAL da Steam).
    """
    try:
        from hefesto_dualsense4unix.app.actions.emulation_actions import (
            EmulationActionsMixin,
        )
        from hefesto_dualsense4unix.integrations.steam_launch_options import (
            rotulo_do_jogo,
        )

        return [
            rotulo_do_jogo(appid)
            for appid in EmulationActionsMixin._steam_input_appids_ligados()
        ]
    except Exception as exc:  # pragma: no cover - defesa; nunca derruba o botão
        logger.warning("steam_input_medicao_falhou", erro=str(exc))
        return None


def format_fix_safe_result(relatorio: object) -> str:
    """Toast do botão "Aplicar correções" (sem senha) — pura, testável.

    HONESTIDADE-STEAM-01. A versão anterior dizia "Correções aplicadas (sem
    senha)" SEMPRE — inclusive quando o `--apply-quiet` tinha adiado tudo por
    causa da Steam aberta (o caminho mais comum, já que a usuária clica no
    Hefesto justamente enquanto joga). O relato agora separa o que rodou do
    que foi adiado, e nomeia o botão que resolve o adiamento.
    """
    if not isinstance(relatorio, dict):
        return (
            "Não consegui aplicar as correções — resposta inesperada; veja "
            "os 'Detalhes técnicos'."
        )
    if not relatorio.get("ran") and relatorio.get("missing"):
        return "Não encontrei os scripts de correção nesta instalação."
    partes = ["Correções aplicadas (sem senha)."]
    bruto = relatorio.get("steam_input")
    if isinstance(bruto, tuple) and len(bruto) == 2:
        rc, saida = bruto
        tag = _tag_do_script(saida)
        jogos = _jogos_do_relatorio(relatorio.get("steam_input_jogos"))
        if tag in ("adiado-steam-aberta", "recusado-jogo-aberto"):
            partes.append(
                "Só o Steam Input NÃO foi desligado: "
                + _frase_steam_input(int(rc), tag, jogos)
                + " Use o botão 'Deixar tudo pronto' — ele pede sua permissão "
                "para fechar a Steam e faz o resto sozinho."
            )
        else:
            partes.append("Steam Input: " + _frase_steam_input(int(rc), tag, jogos))
    partes.append(
        "A cura anti-storm do áudio já é persistente (install) — reconecte o "
        "controle para ela pegar nesta sessão."
    )
    return " ".join(partes)


def format_game_broken_result(*, status: str, appid: object = None) -> str:
    """Toast do botão "Este jogo não funciona" — pura, testável.

    Deliberadamente SEM os termos "Steam Input" e "opção de inicialização": a
    usuária só declara que o jogo falhou, e o app troca de estratégia (o jogo
    passa a receber a ENTRADA pela Steam, e some o controle dobrado).

    NOTA DATADA — 07/08/2026. Este toast dizia *"o Hefesto sai da frente
    dele"*, e a frase está **refutada pela metade** pela medição dela de
    06/08 (`CONTROLE-SONY-MEDIDO-01`, seção *A INVERSÃO*, grau MEDIDO): com o
    jogo marcado o Hefesto entrega a **entrada** (solta o grab e derruba o
    gamepad virtual, o que acaba com o dobrado) e **mantém a saída inteira** —
    os gatilhos dela seguraram duros e o vermelho dela ficou na lightbar, com
    o Mullet Mad Jack aberto. Quem lia "sai da frente" esperava perder cor e
    gatilho, que é o contrário do que acontece; e o que de fato se perde ali
    é o co-op (os secundários caem junto com os vpads), que o toast não
    escondia e continua não escondendo — ver o badge da aba Status
    (`app/actions/status_actions.tooltip_do_coop_derrubado`).
    """
    if status == "sem_jogo":
        return (
            "Não descobri qual é o jogo. Abra o jogo pela Steam (de "
            "preferência deixe-o aberto) e clique de novo."
        )
    if status == "appid_invalido":
        return "Não consegui identificar o jogo — nada foi anotado."
    if status == "erro":
        return (
            "Não consegui anotar este jogo — veja os 'Detalhes técnicos'."
        )
    # STEAM-INPUT-01 (entrega 1): aqui morava a única frase do produto que
    # ENSINAVA o gesto de ligar a entrada da Steam pela janela da própria Steam
    # (menu do jogo, aba do controle, "Ativar" — "agora o Hefesto respeita essa
    # escolha em vez de desfazê-la"). Ela só era verdadeira para um appid JÁ na
    # allowlist; como regra geral é falsa, e foi assim que ela a leu: a
    # DUPLO-REGISTRO-01 mediu o Pragmata com `UseSteamControllerConfig "2"` no
    # `localconfig.vdf` e AUSENTE do `steam_input_apps.txt` — o segundo
    # cadastro, o único que o Hefesto consulta. Ligar pela Steam não escreve na
    # allowlist, e o guarda (`scripts/disable_steam_input.sh`) zera o per-app de
    # quem está fora dela. O texto novo responde à mesma pergunta legítima ("e
    # se não funcionar?") sem mandar ninguém à Steam e sem prometer o que o
    # clique não faz: ele NÃO liga a entrada da Steam em lugar nenhum — só
    # entrega a ENTRADA daquele jogo (ungrab + restore do broker + vpad
    # suspenso, em `daemon/subsystems/gamepad.py`), e é isso que faz o jogo
    # enxergar o DualSense físico direto. A saída — cor, gatilhos, vibração —
    # não passa por nenhum desses portões: os oito chamadores de
    # `steam_input_excecao_ativa` estão todos em `gamepad.py`, nenhum em
    # `core/` (MEDIDO por grep, 06/08).
    resto = (
        " Feche e abra o jogo de novo: ele passa a enxergar o controle "
        "físico direto e você não precisa configurar nada na Steam — a marca "
        "é do Hefesto e sobrevive a reiniciar a máquina. Se ainda assim o "
        "jogo não responder, o guia é docs/usage/jogos-e-mascaras.md."
    )
    if status == "ja_estava":
        return (
            f"O jogo {appid} já estava marcado — ele já recebe o controle "
            f"direto pela Steam, sem o controle dobrado.{resto}"
        )
    return (
        f"Anotei: o jogo {appid} passa a receber o controle direto pela "
        f"Steam, sem o controle dobrado — e a sua cor e os seus gatilhos "
        f"continuam valendo.{resto}"
    )


def format_proton_lock_result(result: object) -> str:
    """Mensagem pro leigo a partir do dict do ``lock_proton_for_all_games``.

    Pura (testável sem GTK) — o miolo do toast do botão "Travar Proton
    validado" (PLAT-01). Contrato esperado da lane do pin
    (``integrations/proton_pin``): ``{locked, skipped, errors}`` com
    contagens (int) ou listas de itens — ``applied`` é aceito como sinônimo
    de ``locked`` — e, opcional, ``tool`` (str, o nome da versão pinada).
    Resposta fora do contrato vira recusa honesta, nunca "Pronto".
    """
    if not isinstance(result, dict):
        return (
            "Não consegui travar o Proton — resposta inesperada; veja os "
            "'Detalhes técnicos'."
        )
    locked = _apply_result_count(result.get("locked", result.get("applied")))
    skipped = _apply_result_count(result.get("skipped"))
    errors = _apply_result_count(result.get("errors"))
    tool = result.get("tool")
    tool_txt = f" ({tool})" if isinstance(tool, str) and tool else ""
    if locked:
        msg = (
            f"Pronto — {locked} jogo(s) travados no Proton validado"
            f"{tool_txt}; atualizações da Steam não trocam mais a versão "
            "(backup do arquivo da Steam feito)."
        )
    elif errors == 0:
        msg = (
            f"Nada a mudar — os jogos já estão no Proton validado{tool_txt} "
            "(ou não encontrei jogos da Steam neste computador)."
        )
    else:
        msg = "Nenhum jogo foi alterado."
    if skipped:
        msg += f" {skipped} jogo(s) ficaram como estavam."
    if errors:
        msg += (
            f" Atenção: {errors} jogo(s) falharam — veja os "
            "'Detalhes técnicos'."
        )
    return msg


class DaemonActionsMixin(WidgetAccessMixin):
    """Controla a aba Sistema (o `daemon_box` do Glade)."""

    _daemon_autostart_guard: bool = False
    # Contador anti-loop de tentativas de autostart por sessão da GUI.
    # Máximo 2 tentativas: após a segunda falha, o helper vira no-op até
    # a próxima reabertura do processo (BUG-DAEMON-AUTOSTART-01).
    _daemon_autostart_attempts: int = 0

    def install_daemon_tab(self) -> None:
        self._daemon_autostart_guard = False
        # Inicializa contador anti-loop por instância (bootstrap da GUI).
        self._daemon_autostart_attempts = 0
        # BUG-GUI-DAEMON-STATUS-INITIAL-01: o refresh da view chama
        # `systemctl is-active/is-enabled/status` — cada um com timeout 5 s.
        # Em bootstrap, rodar síncrono bloquearia a thread GTK por até 15 s
        # em sistemas onde systemctl trava (ex.: usuário sem unit instalada
        # combinado com journal lento). Descarregamos em thread worker e
        # atualizamos a view via `GLib.idle_add` quando os dados chegam. O
        # label default do Glade ("—" neutro) mostra o estado "Consultando"
        # até o resultado pintar — em vez do falso-negativo "Offline".
        self._set_daemon_status_consulting()
        self._refresh_daemon_view_async()
        self._sync_restart_daemon_button_sensitivity()
        self._refresh_storm_diag()  # FEAT-DSX-UNIFY-01
        self._refresh_window_detect_diag()  # JANELA-CEGA-01
        self._wire_steam_simple_buttons()  # FEAT-STEAM-SIMPLES-01

    def _wire_steam_simple_buttons(self) -> None:
        """Liga os dois botões do modo simples em CÓDIGO, não pelo Glade.

        Precedente explícito no `app.py` (FEAT-DSX-COMBO-TO-SEGMENTED-01): o
        app conecta sinais por um dict literal em `_signal_handlers()`, então
        um `<signal handler="...">` no Glade sem entrada nesse dict vira botão
        MORTO (BUG-GUI-EMULATION-HANDLERS-UNWIRED-01 — "clico e não aplica").
        Ligar aqui mantém dono único: o Glade descreve o widget, este mixin
        (que já é o dono da aba Sistema) descreve o comportamento.

        Tolerante a widget ausente: instalação com um main.glade mais antigo
        simplesmente não tem os botões — nada a ligar, nada a quebrar.
        """
        for widget_id, handler in (
            ("btn_steam_ready", self.on_steam_ready),
            ("btn_steam_game_broken", self.on_steam_game_broken),
        ):
            botao = self._get(widget_id)
            if botao is None:
                continue
            with contextlib.suppress(Exception):
                botao.connect("clicked", handler)

    # --- anti-storm / sistema (FEAT-DSX-UNIFY-01) ------------------------

    def _find_repo_file(self, relpath: str) -> Path | None:
        """Localiza um arquivo do repo (ex.: scripts/install_snd_quirk.sh) em layouts conhecidos.

        BUG-GUI-REPO-ROOT-OFFBYONE-01: `parents[3]` resolvia para `<repo>/src`
        (este arquivo está em src/hefesto_dualsense4unix/app/actions/) — nenhum
        script era encontrado e os botões do cartão anti-storm eram no-op
        SILENCIOSO (toast de sucesso, nada executado). A raiz do repo é
        `parents[4]`. Coberto por teste de regressão.
        """
        for base in (
            Path(__file__).resolve().parents[4],
            Path("/usr/share/hefesto-dualsense4unix"),
            Path("/usr/local/share/hefesto-dualsense4unix"),
        ):
            candidate = base / relpath
            if candidate.is_file():
                return candidate
        return None

    def _refresh_storm_diag(self) -> None:
        """Popula o cartão anti-storm (read-only) em thread worker."""
        def _worker() -> None:
            try:
                from hefesto_dualsense4unix.integrations import storm_doctor

                # MESA-CHEIA-11/E3: o check de áudio agora CONTA, e o
                # denominador é quantos controles estão no cabo AGORA — sem
                # ele, um DualSense com áudio responderia pelos quatro. O
                # state_full é best-effort: daemon offline devolve None e o
                # check volta a responder presente/ausente (nunca alarme falso
                # por payload ausente).
                no_cabo: int | None = None
                with contextlib.suppress(Exception):
                    from hefesto_dualsense4unix.app.ipc_bridge import (
                        daemon_state_full,
                    )

                    no_cabo = storm_doctor.controles_no_cabo(daemon_state_full())
                rows = storm_doctor.storm_report(controles_no_cabo=no_cabo)
            except Exception as exc:
                logger.warning("storm_diag_falhou", erro=str(exc))
                return
            colors = {"[ OK ]": "#50fa7b", "[WARN]": "#ffb86c", "[INFO]": "#8b8fa8"}

            def _esc(text: str) -> str:
                return (
                    text.replace("&", "&amp;")
                    .replace("<", "&lt;")
                    .replace(">", "&gt;")
                )

            lines = [
                f'<span foreground="{colors.get(tag, "#c8ccda")}">{_esc(tag)}</span> '
                f"{_esc(msg)}"
                for tag, msg in rows
            ]
            GLib.idle_add(self._apply_storm_diag, "\n".join(lines))

        _get_executor().submit(_worker)

    def _apply_storm_diag(self, markup: str) -> bool:
        label = self._get("storm_diag_label")
        if label is not None:
            label.set_markup(markup)
        return False  # GLib.idle_add: não repete

    # --- detector de janela (JANELA-CEGA-01, a linha honesta) --------------

    def _refresh_window_detect_diag(self) -> None:
        """Pinta a linha "Trocar de perfil ao abrir o jogo" com o estado do daemon.

        Assíncrono (`call_async`) e read-only: só lê `daemon.state_full`. Falha
        de IPC não é engolida — vira a frase de "não consegui ler", que é a
        verdade disponível (mesma disciplina do cartão UINPUT).

        DIAGNÓSTICO-NAO-DERRUBA-A-ABA-01 (30/07). Todo o corpo está dentro de um
        `try`, e isso não é preguiça: esta função é chamada de DENTRO do refresh
        da aba Sistema (`:519`), e uma linha informativa não pode levar a aba
        junto quando falha. O caso que provou isso foi o CI reprovando a tag
        v0.4.0: os imports abaixo puxam o `ipc_bridge`, que precisa de GLib, e no
        runner headless — onde `test_daemon_status_initial.py` planta um Gtk
        falso — a importação estourava e derrubava TRÊS testes do estado do
        daemon, que nada têm a ver com detector de janela.

        O `Exception` largo é deliberado e é o mesmo padrão do resto desta base
        para trabalho decorativo: o que se perde no pior caso é uma frase na
        tela; o que se protege é a aba inteira.
        """
        try:
            from hefesto_dualsense4unix.app.actions.mode_transition import (
                STATE_IPC_TIMEOUT_S,
            )
            from hefesto_dualsense4unix.app.ipc_bridge import call_async

            def _pintar(state: object) -> bool:
                label = self._get("window_detect_diag_label")
                if label is not None:
                    label.set_markup(descrever_deteccao_de_janela(state))
                return False

            call_async(
                "daemon.state_full",
                {},
                on_success=_pintar,
                on_failure=lambda _exc: _pintar(None),
                # HARM-15: sem a folga a linha se pinta de "não consegui ler" com
                # o daemon VIVO sempre que o `state_full` passa dos 0,25s default.
                timeout_s=STATE_IPC_TIMEOUT_S,
            )
        except Exception as exc:  # pragma: no cover — rede de segurança da aba
            logger.debug("window_detect_diag_indisponivel", err=str(exc))

    def on_storm_fix_safe(self, _btn: object) -> None:
        """Reaplica os fixes SEGUROS (sem sudo): Steam Input OFF + WirePlumber.

        HONESTIDADE-STEAM-01: este botão NÃO fecha a Steam (é o botão do "sem
        senha, sem susto") — o `--apply-quiet` continua adiando quando ela
        está viva. O que mudou é que o toast passou a DIZER que adiou, em vez
        de anunciar "Correções aplicadas" sobre um no-op, e a apontar o botão
        que resolve ("Deixar tudo pronto", que pede permissão para fechar).
        """
        self._toast_daemon("Aplicando correções (não pede senha)…")

        def _worker() -> None:
            relatorio: dict[str, Any] = {
                "ran": 0,
                "missing": 0,
                "steam_input": None,
                # D-33: medido ANTES de rodar — depois os appids já foram
                # zerados no vdf e não haveria mais como nomear o jogo.
                "steam_input_jogos": medir_jogos_com_steam_input(),
            }
            for relpath, args in (
                ("scripts/disable_steam_input.sh", ["--apply-quiet"]),
                ("scripts/fix_wireplumber_default_source.sh", ["--install"]),
                # BUG-C: o quirk anti-storm NÃO entra aqui de propósito. Escrevê-lo
                # a quente era `sudo tee` no /sys/module/snd_usb_audio/parameters/
                # quirk_flags (param de MÓDULO, root-only, fora do alcance do
                # uaccess) — o ÚNICO sudo em runtime da GUI, e sem ticket cacheado
                # falhava calado enquanto o botão dizia "não pede senha" (mentira).
                # A versão persistente (/etc/modprobe.d) é default no install e pega
                # no próximo replug do controle; o toast instrui isso. Assim o botão
                # roda 100% sem senha (os dois scripts acima são user-space).
            ):
                script = self._find_repo_file(relpath)
                if script is None:
                    relatorio["missing"] += 1
                    continue
                with contextlib.suppress(Exception):
                    proc = subprocess.run(
                        ["bash", str(script), *args],
                        check=False,
                        timeout=30,
                        capture_output=True,
                        text=True,
                    )
                    relatorio["ran"] += 1
                    if "disable_steam_input" in relpath:
                        # rc + saída CRUA: o veredito honesto sai da tag
                        # `resultado=` que o script emite, não do rc (o
                        # "adiei" e o "apliquei" saem 0 os dois).
                        relatorio["steam_input"] = (
                            proc.returncode,
                            (proc.stdout or "") + (proc.stderr or ""),
                        )
            GLib.idle_add(self._refresh_storm_diag)
            # M9 (auditoria): toast FINAL — antes a statusbar congelava em
            # "Reaplicando..." para sempre. Distingue "rodou" de "scripts não
            # encontrados" (H3/M10 — instalação de pacote sem os scripts).
            GLib.idle_add(self._toast_daemon, format_fix_safe_result(relatorio))

        _get_executor().submit(_worker)

    @classmethod
    def compose_launch(cls, flavor: str, backend: str) -> tuple[str, str]:
        """(string de Launch Option, dica extra) — agora a chamada do WRAPPER.

        Pura e sem GTK — é o miolo testável do botão `on_storm_copy_launch`.

        DEDUP-04/UX-05: o botão parou de recomendar o veneno estático. A env
        colada de antes (`SDL_GAMECONTROLLER_IGNORE_DEVICES=0x054c/0x0ce6`
        persistida por jogo) pressupunha um estado DINÂMICO — vpad vivo como
        Edge 0df2; quando o pressuposto falhava (EIO de BT, hotplug, modo
        Nativo, daemon morto) ela escondia o ÚNICO controle que restou e o
        jogo ficava com ZERO controles ("em BT nada funciona", provado ao
        vivo). A string devolvida aqui é CONSTANTE e idêntica para QUALQUER
        (máscara, backend): quem decide as envs é o wrapper `hefesto-launch`
        NA HORA do launch, consultando o estado real do daemon via IPC — e a
        própria string degrada para `exec env "$@"` quando o wrapper faltar
        (o jogo SEMPRE abre; pior caso: controle duplicado, nunca zero).

        Os parâmetros (flavor, backend) permanecem na assinatura por
        compatibilidade com quem consulta o estado antes de copiar — são
        deliberadamente IGNORADOS.
        """
        del flavor, backend  # a string é constante — decisão é do wrapper
        from hefesto_dualsense4unix.integrations.steam_launch_options import (
            WRAPPER_LAUNCH,
        )

        return WRAPPER_LAUNCH, ""

    @staticmethod
    def _wrapper_installed() -> bool:
        """True se o wrapper hefesto-launch está instalado e executável."""
        from hefesto_dualsense4unix.integrations.steam_launch_options import (
            WRAPPER_HOME_RELPATH,
        )

        wrapper = Path.home() / WRAPPER_HOME_RELPATH
        return wrapper.is_file() and os.access(wrapper, os.X_OK)

    def _query_gamepad_state(self) -> tuple[str, str]:
        """(flavor, backend) do gamepad virtual ativo via state_full.

        Fallback ('xbox', '') quando o estado não veio — a variante Xbox é a mais
        conservadora (desduplica com qualquer vpad de VID/PID próprio).
        """
        try:
            from hefesto_dualsense4unix.app.ipc_bridge import daemon_state_full

            state = daemon_state_full()
            if isinstance(state, dict):
                gp = state.get("gamepad_emulation")
                if isinstance(gp, dict):
                    fl = gp.get("flavor")
                    bk = gp.get("backend")
                    flavor = fl if isinstance(fl, str) and fl else "xbox"
                    backend = bk if isinstance(bk, str) else ""
                    return flavor, backend
        except Exception:
            logger.debug("storm_copy_state_probe_falhou", exc_info=True)
        return "xbox", ""

    def on_storm_copy_launch(self, _btn: object) -> None:
        """Copia a Opção de Inicialização da Steam — a chamada do wrapper.

        DEDUP-04/UX-05: a string é CONSTANTE (idêntica em qualquer máscara/
        backend) — o wrapper `hefesto-launch` decide as envs na hora do
        launch consultando o daemon via IPC, e degrada sozinho quando o
        daemon está morto/degradado (nenhuma env => físico visível => o jogo
        sempre abre com controle). Fallback honesto: com o wrapper ainda não
        instalado, a string continua abrindo o jogo — só não desduplica.
        """
        launch, extra = self.compose_launch("", "")
        copied = False
        with contextlib.suppress(Exception):
            from gi.repository import Gdk, Gtk

            clip = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
            clip.set_text(launch, -1)
            clip.store()
            copied = True
        if not self._wrapper_installed():
            extra = (
                f"{extra}  Atenção: o wrapper ainda não está instalado "
                "(rode ./install.sh) — a opção continua abrindo o jogo, mas "
                "sem esconder o controle físico (pode duplicar) até o "
                "install completar."
            )
        if copied:
            # A string termina em `%command%`. Se o jogo JÁ tem opções, o certo
            # é o botão 'Aplicar aos jogos da Steam' (funde sozinho, removendo
            # as opções antigas do Hefesto); manualmente: manter as opções do
            # usuário ENTRE `hefesto-launch` e o `%command%` final, com UM só
            # `%command%` na linha.
            self._toast_daemon(
                "Copiado! Cole em: Steam → jogo → Propriedades → Opções de "
                "inicialização. Se já houver algo lá, prefira o botão 'Aplicar "
                "aos jogos da Steam' — ele funde sem apagar as suas opções."
                f"{extra}"
            )
        else:
            self._toast_daemon(f"Copie manualmente: {launch}{extra}")

    def on_steam_apply_launch(self, _btn: object) -> None:
        """Botão "Aplicar aos jogos da Steam" — agora com confirmação (PATH-06).

        A ação deixou de ser só migração das linhas envenenadas: aplica o
        wrapper a TODOS os jogos instalados (`apply_wrapper_to_all_games`,
        integrations/steam_launch_options), preservando as opções existentes
        (o launcher entra na frente). Por mexer em todos os jogos, pede
        confirmação num diálogo TEMADO e NÃO-bloqueante (padrão
        `_show_restart_error`: `connect("response")`, nunca `run()`).
        """
        dialog = self._build_steam_apply_confirm_dialog()
        dialog.show_all()

    def _build_steam_apply_confirm_dialog(self) -> Gtk.MessageDialog:
        """Monta o diálogo de confirmação (sem exibir) — separado p/ testes."""
        window: Gtk.Window | None = getattr(self, "window", None)
        dialog = Gtk.MessageDialog(
            transient_for=window,
            flags=0,
            message_type=Gtk.MessageType.QUESTION,
            buttons=Gtk.ButtonsType.NONE,
            text="Aplicar o hefesto-launch aos jogos da Steam?",
        )
        # GUI-05/P5: classe de tema (precedente gui_dialogs._apply_app_theme).
        with contextlib.suppress(Exception):
            dialog.get_style_context().add_class(
                "hefesto-dualsense4unix-window"
            )
        dialog.format_secondary_text(
            "Cada jogo instalado passa a abrir pelo launcher do Hefesto — é "
            "isso que evita o controle duplicado no jogo.\n\n"
            "As opções que você já tem nos jogos são preservadas (o launcher "
            "entra na frente delas) e fica um backup ao lado de cada "
            "arquivo.\n\n"
            # HONESTIDADE-STEAM-01: este parágrafo dizia "A Steam precisa
            # estar FECHADA — se estiver aberta, eu aviso e não mexo em nada",
            # que virou mentira no momento em que o botão passou a saber
            # fechá-la. O texto agora descreve o que o botão faz de verdade.
            "A edição só vale com a Steam fechada — se ela estiver aberta eu "
            "peço a sua permissão antes de fechá-la por uns 20 segundos e "
            "abro de novo em seguida. Com um jogo aberto eu não mexo em nada."
        )
        dialog.add_button("Cancelar", Gtk.ResponseType.CANCEL)
        dialog.add_button("Aplicar a todos", Gtk.ResponseType.OK)
        dialog.set_default_response(Gtk.ResponseType.CANCEL)
        dialog.connect("response", self._on_steam_apply_confirm_response)
        return dialog

    def _on_steam_apply_confirm_response(
        self, dialog: Any, response: int
    ) -> None:
        """Handler do diálogo de confirmação — só o OK dispara o worker."""
        with contextlib.suppress(Exception):
            dialog.destroy()
        if response != Gtk.ResponseType.OK:
            return
        self._steam_apply_launch_worker()

    def _steam_apply_launch_worker(self) -> None:
        """Aplica o wrapper em massa (confirmado) — em thread worker.

        HONESTIDADE-STEAM-01. Antes este caminho SEMPRE recusava com a Steam
        aberta ("feche-a e clique de novo") — e a usuária, que clica no
        Hefesto justamente enquanto a Steam está aberta, batia nessa parede
        toda vez. A maquinaria de fechar/reabrir existia (`stop_steam`/
        `reopen_steam`, exercitada só pelo `install.sh --migrate
        --stop-steam`) e era só a GUI que não a usava.

        Agora a parede vira uma PERGUNTA:

        - JOGO aberto ⇒ recusa (mantido; `steam -shutdown` mataria o jogo);
        - só a Steam aberta ⇒ diálogo de consentimento e, com o sim, o fluxo
          `with_steam_closed` (fecha uma vez, aplica, reabre uma vez);
        - Steam fechada ⇒ aplica direto, sem diálogo nenhum.

        Sudo-zero: o vdf é arquivo do usuário. Import lazy + `getattr`: a
        função de massa é do contrato PATH-06 (`{applied, skipped, errors}`);
        numa instalação antiga sem ela, recusa com o caminho do install.
        """
        self._toast_daemon("Verificando os arquivos da Steam…")

        def _worker() -> None:
            try:
                from hefesto_dualsense4unix.integrations import (
                    steam_launch_options as slo,
                )

                apply_fn = getattr(slo, "apply_wrapper_to_all_games", None)
                if apply_fn is None:
                    GLib.idle_add(
                        self._toast_daemon,
                        "Esta instalação ainda não tem a aplicação em massa "
                        "— rode ./install.sh para atualizar o Hefesto.",
                    )
                    return
                if slo.steam_game_running():
                    GLib.idle_add(
                        self._toast_daemon,
                        format_steam_janela_recusa("jogo_aberto"),
                    )
                    return
                if slo.steam_running():
                    # Consentimento SEMPRE na thread GTK (diálogo é widget).
                    GLib.idle_add(
                        self._pedir_para_fechar_a_steam,
                        self._steam_apply_launch_fechando,
                        "Nada foi mudado — a Steam continua aberta. Clique de "
                        "novo quando puder deixá-la fechada por uns 20 segundos.",
                        "Para ajustar as opções dos jogos eu preciso FECHAR a "
                        "Steam por uns 20 segundos e abrir de novo — com ela "
                        "viva, ela regrava o arquivo ao sair e a mudança seria "
                        "perdida.\n\n"
                        "Antes de continuar: pause os downloads. As suas opções "
                        "são preservadas e fica um backup ao lado de cada "
                        "arquivo.\n\n"
                        "Se algum jogo estiver aberto eu não faço nada.",
                    )
                    return
                result = apply_fn()
                GLib.idle_add(
                    self._toast_daemon, format_apply_wrapper_result(result)
                )
            except Exception as exc:
                logger.warning("steam_apply_launch_falhou", erro=str(exc))
                GLib.idle_add(
                    self._toast_daemon,
                    "Não consegui aplicar — veja os 'Detalhes técnicos'.",
                )

        _get_executor().submit(_worker)

    def _pedir_para_fechar_a_steam(
        self,
        prosseguir: Any,
        cancelado_msg: str,
        corpo: str,
        titulo: str = "Posso fechar a Steam por uns 20 segundos?",
        rotulo_ok: str = "Fechar e continuar",
    ) -> bool:
        """Mostra o consentimento e, com o sim, roda `prosseguir()` em worker.

        Sempre chamado via `GLib.idle_add` a partir do worker (widget só na
        thread GTK). Retorna False para o idle_add não reagendar.
        """

        def _resposta(dialog: Any, response: int) -> None:
            with contextlib.suppress(Exception):
                dialog.destroy()
            if response != Gtk.ResponseType.OK:
                self._toast_daemon(cancelado_msg)
                return
            _get_executor().submit(prosseguir)

        build_steam_close_consent_dialog(
            getattr(self, "window", None),
            titulo=titulo,
            corpo=corpo,
            rotulo_ok=rotulo_ok,
            on_response=_resposta,
        ).show_all()
        return False

    def _steam_apply_launch_fechando(self) -> None:
        """Aplica o wrapper com a Steam fechada por NÓS (já consentido)."""
        GLib.idle_add(self._toast_daemon, "Fechando a Steam (uns 20 segundos)…")
        try:
            from hefesto_dualsense4unix.integrations import (
                steam_launch_options as slo,
            )

            apply_fn = getattr(slo, "apply_wrapper_to_all_games", None)
            if apply_fn is None:
                GLib.idle_add(
                    self._toast_daemon,
                    "Esta instalação ainda não tem a aplicação em massa — "
                    "rode ./install.sh para atualizar o Hefesto.",
                )
                return
            janela, result = slo.with_steam_closed(apply_fn)
            recusa = format_steam_janela_recusa(janela)
            GLib.idle_add(
                self._toast_daemon,
                recusa if recusa is not None else format_apply_wrapper_result(result),
            )
        except Exception as exc:
            logger.warning("steam_apply_launch_fechando_falhou", erro=str(exc))
            GLib.idle_add(
                self._toast_daemon,
                "Não consegui aplicar — veja os 'Detalhes técnicos'.",
            )

    # --- Modo simples: dois botões que escondem os conceitos --------------
    # FEAT-STEAM-SIMPLES-01 (25/07). Pedido literal da usuária final: "tem
    # jogos que precisamos ativar entrada steam, outros que temos que colocar
    # comandos de inicialização — é uma confusão real". Os dois mecanismos
    # continuam existindo; o que sai da tela é a ESCOLHA entre eles.
    #
    #   "Deixar tudo pronto"     -> encadeia disable_steam_input + wrapper em
    #                               todos os jogos, com UM consentimento só.
    #   "Este jogo não funciona" -> marca o jogo ativo na allowlist do Steam
    #                               Input: o Hefesto entrega a ENTRADA DELE
    #                               (e só ela — ver `format_game_broken_result`).
    #
    # Nenhum dos dois pronuncia "Steam Input" nem "opção de inicialização".

    #: Corpo do diálogo do "Deixar tudo pronto". Um consentimento só (o de
    #: fechar a Steam) porque é a única consequência que a usuária sente.
    _STEAM_READY_CORPO = (
        "Eu ajusto de uma vez as duas coisas que costumam brigar com o "
        "controle: quem entrega o controle para o jogo e como cada jogo é "
        "aberto.\n\n"
        "Para isso a Steam precisa estar fechada — se ela estiver aberta eu "
        "fecho por uns 20 segundos e abro de novo. Pause os downloads antes.\n\n"
        "Se algum jogo estiver aberto eu não faço NADA (fechar a Steam mataria "
        "o jogo). Fica um backup ao lado de cada arquivo da Steam."
    )

    def on_steam_ready(self, _btn: object = None) -> None:
        """Botão "Deixar tudo pronto" — confirmação e depois o worker."""
        self._build_steam_ready_confirm_dialog().show_all()

    def _build_steam_ready_confirm_dialog(self) -> Gtk.MessageDialog:
        """Monta o diálogo (sem exibir) — separado p/ testes."""
        return build_steam_close_consent_dialog(
            getattr(self, "window", None),
            titulo="Deixar tudo pronto para jogar?",
            corpo=self._STEAM_READY_CORPO,
            rotulo_ok="Deixar tudo pronto",
            on_response=self._on_steam_ready_response,
        )

    def _on_steam_ready_response(self, dialog: Any, response: int) -> None:
        with contextlib.suppress(Exception):
            dialog.destroy()
        if response != Gtk.ResponseType.OK:
            self._toast_daemon("Nada foi mudado.")
            return
        self._steam_ready_worker()

    def _steam_ready_worker(self) -> None:
        """Encadeia as duas correções com a Steam fechada UMA vez.

        Ordem e dono do fechamento importam: quem fecha/reabre a Steam é o
        `with_steam_closed` (um dono só), e o script roda em `--apply-quiet`
        DENTRO dessa janela — assim ele nunca precisa decidir sozinho matar
        processo, e as duas edições acontecem no mesmo intervalo em que a
        Steam está garantidamente fora do caminho (ela regrava o
        localconfig.vdf ao sair; duas janelas separadas seriam duas chances
        de a edição ser pisada).
        """
        self._toast_daemon("Deixando tudo pronto…")

        def _worker() -> None:
            try:
                from hefesto_dualsense4unix.integrations import (
                    steam_launch_options as slo,
                )

                script = self._find_repo_file("scripts/disable_steam_input.sh")
                apply_fn = getattr(slo, "apply_wrapper_to_all_games", None)

                def _acao() -> dict[str, Any]:
                    saida: dict[str, Any] = {
                        "script": None,
                        "wrapper": None,
                        # D-33: a medição acontece DENTRO da janela de Steam
                        # fechada e ANTES do script — é o último instante em
                        # que o vdf ainda diz de qual jogo estamos falando.
                        "steam_input_jogos": medir_jogos_com_steam_input(),
                    }
                    if script is not None:
                        proc = subprocess.run(
                            ["bash", str(script), "--apply-quiet"],
                            check=False,
                            timeout=180,
                            capture_output=True,
                            text=True,
                        )
                        saida["script"] = (
                            proc.returncode,
                            (proc.stdout or "") + (proc.stderr or ""),
                        )
                    if apply_fn is not None:
                        saida["wrapper"] = apply_fn()
                    return saida

                janela, dados = slo.with_steam_closed(_acao)
                GLib.idle_add(self._refresh_storm_diag)
                GLib.idle_add(
                    self._toast_daemon,
                    format_steam_ready_result(
                        janela=janela,
                        dados=dados,
                        script_ok=script is not None,
                        wrapper_ok=apply_fn is not None,
                    ),
                )
            except Exception as exc:
                logger.warning("steam_ready_falhou", erro=str(exc))
                GLib.idle_add(
                    self._toast_daemon,
                    "Não consegui deixar tudo pronto — veja os 'Detalhes "
                    "técnicos'.",
                )

        _get_executor().submit(_worker)

    @staticmethod
    def _appid_do_jogo_ativo() -> int | None:
        """Appid do jogo que a usuária tem em mente ao clicar, ou None.

        Três evidências, nesta ordem — da mais forte para a mais tolerante:

        1. `launch_session_appid()`: jogo lançado PELO wrapper e ainda vivo
           (marker no disco + pid vivo). Autoritativo e imune a alt-tab — que
           é exatamente o que acontece aqui: para clicar no Hefesto ela SAI do
           jogo, então "janela em foco" nunca serviria sozinha;
        2. `window_detect_last_class` do `state_full`: última wm_class ÚTIL
           vista pelo daemon; só conta se casar `steam_app_<id>`. Cobre jogo
           aberto sem o wrapper;
        3. marker `last_run` cru: o ÚLTIMO jogo lançado pelo wrapper, mesmo já
           fechado. É o caso real do botão — o jogo não funcionou, ela fechou,
           e só então veio reclamar.
        """
        from hefesto_dualsense4unix.daemon.launch_env import (
            launch_session_appid,
            read_last_run_marker,
            steam_appid_from_wm_class,
        )

        with contextlib.suppress(Exception):
            vivo = launch_session_appid()
            if vivo is not None:
                return vivo
        with contextlib.suppress(Exception):
            from hefesto_dualsense4unix.app.ipc_bridge import daemon_state_full

            state = daemon_state_full()
            if isinstance(state, dict):
                foco = steam_appid_from_wm_class(state.get("window_detect_last_class"))
                if foco is not None:
                    return foco
        with contextlib.suppress(Exception):
            marker = read_last_run_marker()
            if marker is not None:
                return marker[0]
        return None

    def on_steam_game_broken(self, _btn: object = None) -> None:
        """Botão "Este jogo não funciona" — troca a estratégia DESTE jogo.

        Sem diálogo de confirmação de propósito: a ação não fecha nada, não
        edita arquivo da Steam e é reversível (uma linha num txt nosso, e
        desde 07/08 a caixinha do editor de perfil também a desfaz). O que
        ela custa é o Hefesto entregar a ENTRADA daquele jogo — que é
        justamente o que a usuária está pedindo ao clicar. A saída fica: em
        06/08 os gatilhos dela seguraram e a cor dela ficou com o jogo
        marcado aberto (`CONTROLE-SONY-MEDIDO-01`, *A INVERSÃO*).
        """
        self._toast_daemon("Procurando qual jogo é…")

        def _worker() -> None:
            try:
                from hefesto_dualsense4unix.integrations import (
                    steam_launch_options as slo,
                )

                appid = self._appid_do_jogo_ativo()
                if appid is None:
                    GLib.idle_add(
                        self._toast_daemon,
                        format_game_broken_result(status="sem_jogo"),
                    )
                    return
                escrever = getattr(
                    slo, "add_appid_to_steam_input_allowlist", None
                )
                if escrever is None:
                    GLib.idle_add(
                        self._toast_daemon,
                        "Esta instalação ainda não sabe marcar jogos — rode "
                        "./install.sh para atualizar o Hefesto.",
                    )
                    return
                status = escrever(
                    appid, nota="marcado pela GUI: 'este jogo não funciona'"
                )
                GLib.idle_add(self._recarregar_apos_allowlist)
                GLib.idle_add(
                    self._toast_daemon,
                    format_game_broken_result(status=status, appid=appid),
                )
            except Exception as exc:
                logger.warning("steam_game_broken_falhou", erro=str(exc))
                GLib.idle_add(
                    self._toast_daemon,
                    format_game_broken_result(status="erro"),
                )

        _get_executor().submit(_worker)

    def _recarregar_apos_allowlist(self) -> bool:
        """Faz a marcação VALER agora, sem reiniciar nada.

        A allowlist é relida do disco a cada consulta (guard em bash,
        `storm_doctor`, `launch_env.steam_input_appids`) — nada a invalidar
        ali. O que NÃO é relido é a materialização das envs de launch: o
        `steam_app_<appid>.env` que entrega a entrada daquele jogo ao físico
        só nasce quando `materialize_launch_env` roda. `launch_env.refresh` é o
        mesmo aviso best-effort que a aba Perfis manda ao salvar um perfil
        (daemon offline é normal — ele rematerializa sozinho no boot).
        """
        from hefesto_dualsense4unix.app import ipc_bridge

        with contextlib.suppress(Exception):
            ipc_bridge.call_async(
                method="launch_env.refresh",
                params={},
                on_success=lambda _r: False,
                on_failure=lambda _e: False,
            )
        self._refresh_storm_diag()
        return False

    def on_proton_lock(self, _btn: object) -> None:
        """Botão "Travar Proton validado" (PLAT-01, aba Sistema).

        Aponta o `CompatToolMapping` do config.vdf da Steam para a versão de
        Proton que o Hefesto validou (a semântica do winebus MUDOU entre
        Proton 9→10 — travar imuniza contra upgrade que mude comportamento).
        Por mexer no arquivo global da Steam, pede confirmação num diálogo
        TEMADO e NÃO-bloqueante (padrão do "Aplicar aos jogos da Steam":
        `connect("response")`, nunca `run()`).
        """
        dialog = self._build_proton_lock_confirm_dialog()
        dialog.show_all()

    def _build_proton_lock_confirm_dialog(self) -> Gtk.MessageDialog:
        """Monta o diálogo de confirmação (sem exibir) — separado p/ testes."""
        window: Gtk.Window | None = getattr(self, "window", None)
        dialog = Gtk.MessageDialog(
            transient_for=window,
            flags=0,
            message_type=Gtk.MessageType.QUESTION,
            buttons=Gtk.ButtonsType.NONE,
            text="Travar os jogos no Proton validado?",
        )
        # GUI-05/P5: classe de tema (precedente gui_dialogs._apply_app_theme).
        with contextlib.suppress(Exception):
            dialog.get_style_context().add_class(
                "hefesto-dualsense4unix-window"
            )
        dialog.format_secondary_text(
            "O Proton é a peça da Steam que roda os jogos de Windows no "
            "Linux. Quando a Steam o atualiza sozinha, o comportamento do "
            "controle pode mudar do nada — travar deixa todos os jogos na "
            "versão que o Hefesto validou, e ela só muda quando VOCÊ rodar "
            "o install de novo.\n\n"
            "Fica um backup do arquivo da Steam antes de qualquer "
            "mudança.\n\n"
            "A Steam precisa estar FECHADA — se estiver aberta, eu aviso e "
            "não mexo em nada."
        )
        dialog.add_button("Cancelar", Gtk.ResponseType.CANCEL)
        dialog.add_button("Travar Proton", Gtk.ResponseType.OK)
        dialog.set_default_response(Gtk.ResponseType.CANCEL)
        dialog.connect("response", self._on_proton_lock_confirm_response)
        return dialog

    def _on_proton_lock_confirm_response(
        self, dialog: Any, response: int
    ) -> None:
        """Handler do diálogo de confirmação — só o OK dispara o worker."""
        with contextlib.suppress(Exception):
            dialog.destroy()
        if response != Gtk.ResponseType.OK:
            return
        self._proton_lock_worker()

    def _proton_lock_worker(self) -> None:
        """Trava o Proton pinado em todos os jogos (confirmado) — em worker.

        Codifica CONTRA O CONTRATO da lane do pin (PLAT-01): import lazy de
        `integrations.proton_pin` + `getattr` defensivo em
        `lock_proton_for_all_games` — instalação sem o módulo ou sem a
        função recusa honesta apontando ./install.sh, nunca AttributeError.
        Recusa com a Steam aberta (ela regrava o config.vdf ao sair e a
        edição seria perdida) — gate do próprio proton_pin quando existir,
        senão o `steam_running` de steam_launch_options. Sudo-zero: o vdf é
        arquivo do usuário.
        """
        self._toast_daemon("Verificando o Proton pinado…")

        def _worker() -> None:
            try:
                import importlib

                try:
                    pp: object = importlib.import_module(
                        "hefesto_dualsense4unix.integrations.proton_pin"
                    )
                except ImportError:
                    pp = None
                lock_fn = getattr(pp, "lock_proton_for_all_games", None)
                if lock_fn is None:
                    GLib.idle_add(
                        self._toast_daemon,
                        "Esta instalação ainda não tem o Proton pinado — "
                        "rode ./install.sh para atualizar o Hefesto.",
                    )
                    return
                steam_running = getattr(pp, "steam_running", None)
                if steam_running is None:
                    from hefesto_dualsense4unix.integrations import (
                        steam_launch_options as slo,
                    )

                    steam_running = slo.steam_running
                if steam_running():
                    GLib.idle_add(
                        self._toast_daemon,
                        "A Steam está aberta — feche-a e clique de novo. "
                        "Não travo o Proton com a Steam viva porque ela "
                        "regrava o arquivo ao sair e a mudança seria "
                        "perdida.",
                    )
                    return
                result = lock_fn()
                GLib.idle_add(
                    self._toast_daemon, format_proton_lock_result(result)
                )
            except Exception as exc:
                logger.warning("proton_lock_falhou", erro=str(exc))
                GLib.idle_add(
                    self._toast_daemon,
                    "Não consegui travar o Proton — veja os 'Detalhes "
                    "técnicos'.",
                )

        _get_executor().submit(_worker)

    def _set_daemon_status_consulting(self) -> None:
        """Mostra o estado transitório "Consultando..." no label da aba Sistema.

        Usado no bootstrap da aba, antes do primeiro `_refresh_daemon_view_async`
        retornar. Evita falso-negativo "Offline" em cenário onde o daemon está
        ativo mas `systemctl` ainda não respondeu (BUG-GUI-DAEMON-STATUS-INITIAL-01).
        """
        label = self._get("daemon_status_label")
        if label is None:
            return
        label.set_markup('<span foreground="#8b8fa8"> Verificando…</span>')
        label.set_tooltip_text("Verificando se o Hefesto está rodando. Aguarde.")

    def _refresh_daemon_view_async(self) -> None:
        """Dispara `_refresh_daemon_view` em thread worker, sem bloquear o GTK.

        BUG-GUI-DAEMON-STATUS-INITIAL-01: a versão síncrona chama 3 subprocess
        `systemctl ...` com timeout 5 s cada. No bootstrap da GUI isso pode
        atrasar o primeiro frame visível — o usuário vê o label default antes
        do refresh terminar. Em thread worker, a UI renderiza imediatamente e
        o label é pintado quando `systemctl` retorna (tipicamente < 200 ms).
        """
        def _worker() -> None:
            try:
                status = self._daemon_status()
                enabled = self._systemctl_oneline(["is-enabled", SERVICE_NORMAL])
                text = self._systemctl_status_text(SERVICE_NORMAL)
            except Exception as exc:
                logger.warning("daemon_view_async_falhou", erro=str(exc))
                return
            GLib.idle_add(self._apply_daemon_view, status, enabled, text)

        _get_executor().submit(_worker)

    def _apply_daemon_view(
        self, status: DaemonStatus, enabled: str, text: str
    ) -> bool:
        """Aplica o resultado do refresh assíncrono na thread GTK.

        Espelha `_refresh_daemon_view` mas sem reexecutar subprocess — recebe
        os valores já consultados em thread worker. Retorna `False` para que
        `GLib.idle_add` não reagende.
        """
        self._set_daemon_status_markup(status, enabled)

        self._daemon_autostart_guard = True
        try:
            sw = self._get("daemon_autostart_switch")
            if sw is not None:
                sw.set_active(enabled == "enabled")
        finally:
            self._daemon_autostart_guard = False

        btn_migrate = self._get("btn_migrate_to_systemd")
        if btn_migrate is not None:
            btn_migrate.set_visible(status == "online_avulso")

        self._set_daemon_text(text)
        return False  # não repetir via GLib

    def ensure_daemon_running(self) -> None:
        """Garante daemon ativo no bootstrap da GUI (BUG-DAEMON-AUTOSTART-01).

        Executado em thread worker via `_get_executor()` — nunca bloqueia
        a thread GTK. Fluxo:

          1. Se `detect_installed_unit()` retorna `None`, no-op (usuário
             sem unit instalada, provavelmente nunca rodou `install.sh`).
          2. Se `systemctl --user is-active hefesto-dualsense4unix.service` já retorna
             `active`, no-op (daemon já está rodando).
          3. Caso contrário, dispara `systemctl --user start hefesto-dualsense4unix.service`
             com timeout de 5s. Falha silenciosa via `logger.warning`.

        Anti-loop: limite de 2 tentativas por sessão (`_daemon_autostart_attempts`).
        Após a segunda falha, o helper vira no-op até a próxima abertura
        do processo da GUI.

        FEAT-GUI-HOME-TAB-01: respeita o "Desligar Hefesto" da aba Início —
        com `_user_stopped_daemon` armado, NÃO ressuscita o daemon (a usuária
        pediu o desligamento de verdade; religa só por gesto explícito).
        """
        if getattr(self, "_user_stopped_daemon", False):
            logger.info("autostart_respeitando_desligamento_manual")
            return
        if self._daemon_autostart_attempts >= 2:
            return

        def _worker() -> None:
            try:
                installed = ServiceInstaller().detect_installed_unit()
            except Exception as exc:
                logger.warning("autostart_detect_falhou", erro=str(exc))
                return
            if installed is None:
                logger.debug("autostart_sem_unit_instalada")
                return

            active = self._is_service_active()
            if active == "active":
                logger.debug("autostart_daemon_ja_ativo")
                return

            # BUG-MULTI-INSTANCE-01: se o pid file do daemon aponta para um
            # processo vivo (ex.: daemon rodando fora do systemd via CLI),
            # não disparar systemctl start — evita spawn duplicado.
            if self._daemon_pid_alive():
                logger.debug("autostart_daemon_vivo_via_pid_file")
                return

            self._daemon_autostart_attempts += 1
            logger.info(
                "autostart_disparando",
                tentativa=self._daemon_autostart_attempts,
                estado_anterior=active,
            )
            rc = self._start_service_blocking()
            if rc == 0:
                logger.info("autostart_ok", unit=SERVICE_NORMAL)
            else:
                logger.warning(
                    "autostart_falhou",
                    unit=SERVICE_NORMAL,
                    rc=rc,
                    tentativa=self._daemon_autostart_attempts,
                )

        _get_executor().submit(_worker)

    def _daemon_pid_alive(self) -> bool:
        """Retorna True se o pid file do daemon aponta para processo vivo.

        Usado pelo `ensure_daemon_running` para não duplicar spawn quando
        o daemon foi lançado fora do systemd (BUG-MULTI-INSTANCE-01).
        """
        try:
            from hefesto_dualsense4unix.utils.single_instance import is_alive
            from hefesto_dualsense4unix.utils.xdg_paths import runtime_dir
        except Exception:
            return False
        pid_file = runtime_dir() / "daemon.pid"
        try:
            raw = pid_file.read_text(encoding="ascii").strip()
        except (FileNotFoundError, OSError):
            return False
        if not raw.isdigit():
            return False
        return is_alive(int(raw))

    def _is_service_active(self) -> str:
        """Retorna saída de `systemctl --user is-active hefesto-dualsense4unix.service`.

        Retorna string vazia se systemctl indisponível.
        """
        result = self._invoke_systemctl(
            ["is-active", SERVICE_NORMAL], capture=True, check=False
        )
        if result is None:
            return ""
        return (result.stdout or "").strip()

    def _start_service_blocking(self) -> int:
        """Sobe o daemon. systemctl primeiro, fallback Popen em sandbox (Flatpak).

        Retorna 0 se subiu com sucesso (systemctl OK ou Popen vivo após probe),
        ou returncode != 0 / -1 em falha.

        Em ambiente Flatpak (FLATPAK_ID definido) ou quando systemctl
        retorna FileNotFoundError, o fallback usa subprocess.Popen do
        binário do app, mantendo o daemon como child do processo da GUI.
        Bloqueia — chamar apenas de thread worker.
        """
        import os
        import sys
        from pathlib import Path

        is_sandbox = bool(os.environ.get("FLATPAK_ID")) or not Path("/run/systemd/system").exists()

        if not is_sandbox:
            try:
                # reset-failed limpa StartLimitBurst-hit se daemon morreu por
                # kill anterior (ex.: _kill_previous_instances da GUI).
                subprocess.run(
                    ["systemctl", "--user", "reset-failed", SERVICE_NORMAL],
                    capture_output=True, timeout=3, check=False,
                )
                result = subprocess.run(
                    ["systemctl", "--user", "start", SERVICE_NORMAL],
                    capture_output=True,
                    text=True,
                    check=False,
                    timeout=5,
                )
                if result.returncode == 0:
                    return 0
                logger.warning(
                    "systemctl_start_falhou_tentando_popen",
                    rc=result.returncode,
                    stderr=(result.stderr or "")[:200],
                )
            except (FileNotFoundError, subprocess.SubprocessError) as exc:
                logger.info("systemctl_indisponivel_usando_popen", erro=str(exc))

        # Fallback: spawn do daemon como child via Popen.
        # Slot self._daemon_popen é cleanado em _shutdown_backend.
        try:
            existing = getattr(self, "_daemon_popen", None)
            if existing is not None and existing.poll() is None:
                logger.debug("daemon_popen_ja_ativo", pid=existing.pid)
                return 0
            cmd = [sys.executable, "-m", "hefesto_dualsense4unix",
                   "daemon", "start", "--foreground"]
            popen = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
            self._daemon_popen = popen
            logger.info("daemon_popen_iniciado", pid=popen.pid, sandbox=is_sandbox)
            # Probe rápido — daemon deve estar vivo após 500ms.
            import time
            time.sleep(0.5)
            if popen.poll() is None:
                return 0
            logger.warning("daemon_popen_morreu_no_boot", rc=popen.returncode)
            return popen.returncode if popen.returncode is not None else -1
        except (FileNotFoundError, subprocess.SubprocessError) as exc:
            logger.warning("daemon_popen_falhou", erro=str(exc))
            return -1

    def _sync_restart_daemon_button_sensitivity(self) -> None:
        """Habilita/desabilita o botão 'Reiniciar daemon' conforme unit presente.

        Se nenhum unit foi instalado, o botão vira cinza com tooltip guiando
        o usuário para `install.sh`. Idempotente e seguro em bootstrap.
        """
        btn = self._get("btn_restart_daemon")
        if btn is None:
            return
        installed = ServiceInstaller().detect_installed_unit()
        if installed:
            btn.set_sensitive(True)
            btn.set_tooltip_text(
                "Desliga e liga o Hefesto de novo — resolve a maioria dos "
                "travamentos."
            )
        else:
            btn.set_sensitive(False)
            btn.set_tooltip_text(
                "O Hefesto ainda não foi instalado como serviço. Rode o "
                "instalador (install.sh) uma vez."
            )

    # --- handlers ---

    def on_daemon_start(self, _btn: Gtk.Button) -> None:
        # FEAT-GUI-HOME-TAB-01: "Iniciar" é gesto explícito — desarma o
        # "Desligar Hefesto" da aba Início (o autostart volta a valer).
        self._user_stopped_daemon = False
        self._run_systemctl_async("start")

    def on_daemon_stop(self, _btn: Gtk.Button) -> None:
        self._run_systemctl_async("stop")

    # on_daemon_restart removido (T5): o botão "Reiniciar" redundante saiu do glade;
    # o caminho único de restart é on_daemon_service_restart (btn_restart_daemon),
    # que trata erro com diálogo não-bloqueante e tem regra de sensibilidade própria.

    def _refresh_daemon_tab_on_show(self) -> None:
        """Reconcilia a aba Sistema ao ser exibida (M7): status do daemon + o
        cartão anti-storm (que antes só era populado no bootstrap da aba)."""
        self._refresh_daemon_view_async()
        self._refresh_storm_diag()
        # JANELA-CEGA-01: o detector CEGA e VOLTA a ver conforme a janela em
        # foco (`window_detect_seeing` decai e volta), então esta linha tem de
        # ser relida ao entrar na aba — senão ela mostra a foto do bootstrap.
        self._refresh_window_detect_diag()

    def on_daemon_refresh(self, _btn: Gtk.Button) -> None:
        self._refresh_daemon_view_async()  # BUG-DAEMON-VIEW-SYNC-FREEZE-01: não bloquear GTK
        # M7 (auditoria): o cartão anti-storm também é reavaliado no "Atualizar" —
        # antes só rodava no bootstrap da aba e ao clicar "Reaplicar fixes
        # seguros", então o diagnóstico ficava stale a sessão inteira (ex.: a
        # usuária instala a cura por fora e o WARN nunca somia).
        self._refresh_storm_diag()
        self._refresh_window_detect_diag()  # JANELA-CEGA-01
        self._sync_restart_daemon_button_sensitivity()

    def on_daemon_service_restart(self, _btn: Gtk.Button) -> None:
        """Handler do botão 'Reiniciar daemon' (UX-RECONNECT-01).

        Executa `systemctl --user restart hefesto-dualsense4unix.service` em
        thread worker (BUG-GUI-SYSTEMCTL-SYNC-NA-THREAD-GTK-01). Antes rodava
        `subprocess.run` síncrono com `timeout=10s` na thread GTK — bloqueava
        toda a UI por até 10s e, se `systemctl` entrasse em D-state (journal
        lento, dbus congestionado), o sinal de kill também era ignorado pelo
        GLib mainloop. Agora o worker faz o subprocess e devolve resultado via
        `GLib.idle_add`. Cobre ausência de systemd e falha do unit exibindo
        MessageDialog não-bloqueante (response handler em vez de `dialog.run()`).
        """
        self._toast_daemon("Reiniciando daemon...")

        def _worker() -> None:
            err_type: str | None = None
            rc: int = -1
            stderr: str = ""
            try:
                result = subprocess.run(
                    ["systemctl", "--user", "restart", SERVICE_NORMAL],
                    capture_output=True,
                    text=True,
                    timeout=10,
                    check=False,
                )
                rc = result.returncode
                stderr = result.stderr or ""
            except FileNotFoundError:
                logger.error("systemctl_missing", unit=SERVICE_NORMAL)
                err_type = "missing"
            except subprocess.SubprocessError as exc:
                logger.error("systemctl_subprocess_error", err=str(exc))
                err_type = "subprocess"
                stderr = str(exc)
            GLib.idle_add(self._on_service_restart_done, rc, stderr, err_type)

        _get_executor().submit(_worker)

    def _on_service_restart_done(
        self, rc: int, stderr: str, err_type: str | None
    ) -> bool:
        """Callback do worker de restart — roda na thread GTK."""
        if err_type == "missing":
            self._show_restart_error(
                "Este computador não tem o gerenciador de serviços que o "
                "Hefesto usa. Rode o instalador (install.sh) uma vez."
            )
            return False
        if err_type == "subprocess":
            logger.error("daemon_restart_subprocess", err=stderr)
            self._show_restart_error(
                "Algo deu errado ao reiniciar. Tente de novo; se insistir, "
                "veja os 'Detalhes técnicos'."
            )
            return False
        if rc != 0:
            stderr_clean = stderr.strip() or "(sem stderr)"
            logger.error(
                "daemon_restart_failed",
                unit=SERVICE_NORMAL,
                rc=rc,
                stderr=stderr_clean,
            )
            # LEIGO-03: o diálogo mostrava "systemctl restart ...service falhou
            # (rc=1)" + o stderr cru. O motivo técnico continua existindo — no
            # log, onde serve para quem for depurar.
            self._show_restart_error(
                "O Hefesto não reiniciou. Tente 'Desligar o Hefesto' e "
                "'Ligar o Hefesto'; os 'Detalhes técnicos' aqui embaixo "
                "mostram o motivo."
            )
            return False
        logger.info("daemon_restart_ok", unit=SERVICE_NORMAL)
        self._toast_daemon("Hefesto reiniciado.")
        self._refresh_daemon_view_async()  # BUG-DAEMON-VIEW-SYNC-FREEZE-01: não bloquear GTK
        return False

    def _show_restart_error(self, message: str) -> None:
        """Diálogo de erro NÃO-BLOQUEANTE (BUG-DIALOG-RUN-BLOQUEIA-GTK-MAINLOOP-01).

        `Gtk.MessageDialog.run()` é modal síncrono — bloqueia a thread GTK
        principal até o usuário clicar OK. Durante esse bloqueio, NENHUM
        callback agendado via `GLib.idle_add` executa, o que inclui o
        signal handler de SIGTERM (que faz `idle_add(quit_app)`). Resultado:
        o app fica "imkillable" enquanto o diálogo está aberto. Em vez de
        `run()/destroy()`, conectamos ao sinal `response` e destruímos no
        callback — a UI segue responsiva e sinais funcionam.
        """
        window: Gtk.Window | None = getattr(self, "window", None)
        dialog = Gtk.MessageDialog(
            transient_for=window,
            flags=0,
            message_type=Gtk.MessageType.ERROR,
            buttons=Gtk.ButtonsType.CLOSE,
            text="Não foi possível reiniciar o Hefesto",
        )
        # GUI-05/P5: classe de tema (precedente gui_dialogs._apply_app_theme).
        with contextlib.suppress(Exception):
            dialog.get_style_context().add_class(
                "hefesto-dualsense4unix-window"
            )
        dialog.format_secondary_text(message)
        dialog.connect("response", lambda d, _r: d.destroy())
        dialog.show_all()

    def on_daemon_view_logs(self, _btn: Gtk.Button) -> None:
        # BUG-DAEMON-VIEW-SYNC-FREEZE-01: journalctl tem timeout de 5s — rodar
        # síncrono congelaria a thread GTK. Worker + repinta via GLib.idle_add.
        self._set_daemon_text("Consultando logs...")

        def _worker() -> None:
            logs = self._journalctl_tail(SERVICE_NORMAL, lines=80)
            GLib.idle_add(self._set_daemon_text, logs or "(sem saída)")

        _get_executor().submit(_worker)

    def on_daemon_autostart_toggled(
        self, _switch: Gtk.Switch, state: bool
    ) -> bool:
        if self._daemon_autostart_guard:
            return False
        action = "enable" if state else "disable"
        self._run_systemctl_async(action)
        return False

    # --- handlers do botão "Migrar para systemd" ---

    def on_daemon_migrate_to_systemd(self, _btn: Gtk.Button) -> None:
        """Handler do botão 'Migrar para systemd' (BUG-DAEMON-STATUS-MISMATCH-01).

        Visível apenas quando o daemon está no estado `online_avulso`.
        Sequência:
          1. Lê pid do arquivo do daemon.
          2. Envia SIGTERM ao processo avulso (grace via single_instance).
          3. Dispara `systemctl --user start hefesto-dualsense4unix.service`.
          4. Atualiza a view.
        Executado em thread worker para não bloquear a thread GTK.
        """
        def _worker() -> None:
            pid = self._read_daemon_pid()
            if pid is not None:
                try:
                    from hefesto_dualsense4unix.utils.single_instance import is_alive
                    if is_alive(pid):
                        logger.info(
                            "daemon_migrate_sigterm",
                            pid=pid,
                        )
                        try:
                            os.kill(pid, signal.SIGTERM)
                        except (ProcessLookupError, PermissionError) as exc:
                            logger.warning(
                                "daemon_migrate_sigterm_falhou",
                                pid=pid,
                                err=str(exc),
                            )
                except Exception as exc:
                    logger.warning("daemon_migrate_import_falhou", err=str(exc))

            rc = self._start_service_blocking()
            if rc == 0:
                logger.info("daemon_migrate_start_ok", unit=SERVICE_NORMAL)
            else:
                logger.warning(
                    "daemon_migrate_start_falhou",
                    unit=SERVICE_NORMAL,
                    rc=rc,
                )
            GLib.idle_add(self._on_migrate_done, rc)

        _get_executor().submit(_worker)

    def _on_migrate_done(self, rc: int) -> bool:
        """Callback pós-migração — executa na thread principal GTK."""
        if rc == 0:
            self._toast_daemon(
                "Pronto — o Hefesto agora liga sozinho e volta sozinho se "
                "travar."
            )
        else:
            logger.warning("daemon_migrate_falhou", unit=SERVICE_NORMAL, rc=rc)
            self._toast_daemon(
                "Não consegui corrigir o modo de execução — veja os 'Detalhes "
                "técnicos' aqui embaixo."
            )
        self._refresh_daemon_view_async()  # BUG-DAEMON-VIEW-SYNC-FREEZE-01: não bloquear GTK
        return False

    # --- helpers ---

    def _read_daemon_pid(self) -> int | None:
        """Lê o PID do arquivo de pid do daemon; retorna None se ausente/inválido."""
        try:
            from hefesto_dualsense4unix.utils.xdg_paths import runtime_dir
        except Exception:
            return None
        pid_file = runtime_dir() / "daemon.pid"
        try:
            raw = pid_file.read_text(encoding="ascii").strip()
        except (FileNotFoundError, OSError):
            return None
        if not raw.isdigit():
            return None
        pid = int(raw)
        return pid if pid > 0 else None

    def _daemon_status(self) -> DaemonStatus:
        """Determina o estado canônico do daemon cruzando 3 fontes.

        Fontes consultadas:
          1. `systemctl --user is-active hefesto-dualsense4unix.service` → systemd_active.
          2. `systemctl --user is-enabled hefesto-dualsense4unix.service` → systemd_enabled.
          3. `is_alive(pid)` via pid file → process_alive.

        Matriz de decisão (BUG-DAEMON-STATUS-MISMATCH-01):
          systemd active + process_alive + enabled  → online_systemd
          systemd active + process_alive            → online_systemd
          systemd inactive/failed + process_alive   → online_avulso
          systemd active + not process_alive        → iniciando
          systemd inactive/failed + not process_alive → offline
        """
        systemd_active = (
            self._systemctl_oneline(["is-active", SERVICE_NORMAL]) == "active"
        )
        pid = self._read_daemon_pid()
        process_alive: bool
        if pid is not None:
            try:
                from hefesto_dualsense4unix.utils.single_instance import is_alive
                process_alive = is_alive(pid)
            except Exception:
                process_alive = False
        else:
            process_alive = False

        if systemd_active and process_alive:
            return "online_systemd"
        if not systemd_active and process_alive:
            return "online_avulso"
        if systemd_active and not process_alive:
            return "iniciando"
        return "offline"

    def _refresh_daemon_view(self) -> None:
        """Atualiza a aba Sistema com base no estado canônico do daemon.

        Consulta `_daemon_status()` (3 fontes) e pinta o label com cor e
        tooltip PT-BR amigável. Também atualiza o switch auto-start e o
        botão "Migrar para systemd" (visível apenas em `online_avulso`).
        """
        status = self._daemon_status()
        enabled = self._systemctl_oneline(["is-enabled", SERVICE_NORMAL])
        self._set_daemon_status_markup(status, enabled)

        self._daemon_autostart_guard = True
        try:
            sw = self._get("daemon_autostart_switch")
            if sw is not None:
                sw.set_active(enabled == "enabled")
        finally:
            self._daemon_autostart_guard = False

        # Botão "Migrar para systemd" visível apenas em estado online_avulso.
        btn_migrate = self._get("btn_migrate_to_systemd")
        if btn_migrate is not None:
            btn_migrate.set_visible(status == "online_avulso")

        text = self._systemctl_status_text(SERVICE_NORMAL)
        self._set_daemon_text(text)

    def _run_systemctl_async(self, action: str) -> None:
        """Executa systemctl em thread worker para não bloquear a thread GTK.

        Para start/restart, primeiro faz reset-failed para limpar
        StartLimitBurst-hit caso o usuário tenha clicado várias vezes ou o
        kill rigoroso da GUI tenha disparado auto-restart no systemd. Sem
        isso, restart imediato falha com 'start-limit-hit'.
        """
        unit = SERVICE_NORMAL

        def _worker() -> None:
            if action in ("start", "restart"):
                self._invoke_systemctl(["reset-failed", unit], check=False)
            result = self._invoke_systemctl([action, unit], capture=True)
            rc = result.returncode if result is not None else -1
            GLib.idle_add(self._on_systemctl_done, action, unit, rc)

        _get_executor().submit(_worker)

    def _on_systemctl_done(self, action: str, unit: str, rc: int) -> bool:
        """Callback pós-systemctl — executa na thread principal GTK."""
        if rc == 0:
            self._toast_daemon(
                _SYSTEMCTL_OK_MSG.get(action, "Pronto.")
            )
        else:
            logger.warning("systemctl_acao_falhou", acao=action, unit=unit, rc=rc)
            falha = _SYSTEMCTL_FAIL_MSG.get(action, "Não consegui")
            self._toast_daemon(
                f"{falha} — veja 'Detalhes técnicos' aqui embaixo."
            )
        self._refresh_daemon_view_async()  # BUG-DAEMON-VIEW-SYNC-FREEZE-01: não bloquear GTK
        return False  # não repetir via GLib

    def _set_daemon_status_markup(
        self, status: DaemonStatus, enabled: str
    ) -> None:
        """Pinta o label de status com cor e tooltip PT-BR conforme estado canônico.

        Cores:
          verde (#50fa7b)  — online_systemd
          laranja (#ffb86c) — online_avulso, iniciando
          vermelho (#ff5555) — offline
        """
        label = self._get("daemon_status_label")
        if label is None:
            return

        # LEIGO-03: o estado interno continua o mesmo (a matriz de 3 fontes é
        # que dá a verdade); o que muda é a leitura. Quem usa pergunta três
        # coisas — está funcionando? liga sozinho? preciso fazer algo? —, e não
        # o que o systemd acha da unit.
        status_map: dict[DaemonStatus, tuple[str, str, str]] = {
            "online_systemd": (
                "#50fa7b",
                " Funcionando (liga sozinho com o computador)"
                if enabled == "enabled"
                else " Funcionando",
                "O Hefesto está rodando. Se travar, ele volta sozinho.",
            ),
            "online_avulso": (
                "#ffb86c",
                " Funcionando (modo improvisado)",
                "O Hefesto está rodando, mas de um jeito improvisado: não liga "
                "sozinho com o computador nem volta sozinho se travar. "
                "Clique em 'Corrigir modo de execução'.",
            ),
            "iniciando": (
                "#ffb86c",
                " Ligando...",
                "O Hefesto está terminando de ligar. Aguarde alguns segundos e "
                "clique em Atualizar.",
            ),
            "offline": (
                "#ff5555",
                " Desligado",
                "O Hefesto não está rodando — o controle funciona, mas sem "
                "luzes, gatilhos nem os seus ajustes. "
                "Clique em 'Ligar o Hefesto'.",
            ),
        }
        color, text, tooltip = status_map[status]
        label.set_markup(f'<span foreground="{color}">{text}</span>')
        label.set_tooltip_text(tooltip)

    def _set_daemon_text(self, text: str) -> None:
        view: Gtk.TextView = self._get("daemon_status_text")
        buf: Gtk.TextBuffer = view.get_buffer()
        text = re.sub(r"\x1b\[[0-9;]*m", "", text)
        buf.set_text(text)
        # UI-DAEMON-LOG-AUTOSCROLL-01: rola até o fim com alinhamento explícito
        # (use_align=True, yalign=1.0) e novamente no próximo idle do GTK — o
        # primeiro scroll roda antes do TextView relayoutar o texto novo, então
        # sem o defer o fim do log fica fora do viewport quando o conteúdo
        # cresce.
        self._scroll_textview_to_end(view)
        GLib.idle_add(self._scroll_textview_to_end, view)

    @staticmethod
    def _scroll_textview_to_end(view: Gtk.TextView) -> bool:
        buf = view.get_buffer()
        end_iter = buf.get_end_iter()
        view.scroll_to_iter(end_iter, 0.0, True, 0.0, 1.0)
        return False  # one-shot quando chamado via GLib.idle_add

    def _systemctl_oneline(self, args: list[str]) -> str:
        result = self._invoke_systemctl(args, capture=True, check=False)
        if result is None:
            return ""
        return (result.stdout or "").strip().splitlines()[:1][0] if result.stdout.strip() else ""

    def _systemctl_status_text(self, unit: str) -> str:
        result = self._invoke_systemctl(
            ["status", unit, "--no-pager"], capture=True, check=False
        )
        if result is None:
            return "(systemctl indisponível)"
        return (result.stdout or "") + (result.stderr or "")

    def _journalctl_tail(self, unit: str, lines: int = 80) -> str:
        try:
            result = subprocess.run(
                [
                    "journalctl",
                    "--user",
                    "-u",
                    unit,
                    "-n",
                    str(lines),
                    "--no-pager",
                ],
                capture_output=True,
                text=True,
                check=False,
                timeout=5,
            )
        except (FileNotFoundError, subprocess.SubprocessError) as exc:
            return f"journalctl indisponível: {exc}"
        return (result.stdout or "") + (result.stderr or "")

    def _invoke_systemctl(
        self,
        args: list[str],
        *,
        capture: bool = False,
        check: bool = False,
    ) -> subprocess.CompletedProcess[str] | None:
        try:
            return subprocess.run(
                ["systemctl", "--user", *args],
                capture_output=capture,
                text=True,
                check=check,
                timeout=5,
            )
        except (FileNotFoundError, subprocess.SubprocessError):
            return None

    def _toast_daemon(self, msg: str) -> None:
        self._status_toast("daemon", msg)
