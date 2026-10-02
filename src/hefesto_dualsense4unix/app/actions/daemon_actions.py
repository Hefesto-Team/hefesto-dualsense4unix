"""Aba Sistema: o Hefesto está funcionando? liga sozinho? está saudável?"""
# ruff: noqa: E402
from __future__ import annotations

import contextlib
import os
import re
import signal
import subprocess
import traceback
from collections.abc import Sequence
from pathlib import Path
from typing import Any, ClassVar, Literal

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import GLib, Gtk

from hefesto_dualsense4unix.app.actions.base import WidgetAccessMixin
from hefesto_dualsense4unix.app.ipc_bridge import _get_executor
from hefesto_dualsense4unix.daemon.service_install import SERVICE_NORMAL, ServiceInstaller
from hefesto_dualsense4unix.integrations.steam_launch_options import juntar_rotulos
from hefesto_dualsense4unix.utils import repo_files
from hefesto_dualsense4unix.utils.logging_config import get_logger
from hefesto_dualsense4unix.utils.repo_files import (
    bases_de_instalacao,
    encontrar_arquivo_do_repo,
)

logger = get_logger(__name__)

DaemonStatus = Literal["online_systemd", "online_avulso", "iniciando", "offline"]

_SYSTEMCTL_OK_MSG: dict[str, str] = {
    "start": "Pronto — Hefesto ligado.",
    "stop": "Hefesto desligado.",
    "enable": "Pronto — o Hefesto vai ligar sozinho com o computador.",
    "disable": "Pronto — o Hefesto não vai mais ligar sozinho.",
}
MIGRAR_DEU_CERTO = (
    "Pronto — o Hefesto agora liga sozinho e volta sozinho se travar."
)
MIGRAR_NAO_DEU = (
    "Não consegui corrigir o modo de execução — veja os 'Detalhes "
    "técnicos' aqui embaixo."
)
_SYSTEMCTL_FAIL_MSG: dict[str, str] = {
    "start": "Não consegui ligar o Hefesto",
    "stop": "Não consegui desligar o Hefesto",
    "enable": "Não consegui deixar o Hefesto ligando sozinho",
    "disable": "Não consegui desligar o início automático",
}


MOTIVO_DA_CEGUEIRA_EM_PORTUGUES: dict[str, str] = {
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

_BACKEND_EM_PORTUGUES: dict[str, str] = {
    "xlib": "pelo XWayland",
    "portal": "pelo portal do sistema",
    "wlrctl": "pelo wlrctl",
    "null": "por nenhum caminho",
}

_PREFIXO_DETECCAO = "<b>Trocar de perfil ao abrir o jogo:</b> "


def _escapar_markup(texto: str) -> str:
    """Escapa `&`, `<` e `>` para o rótulo com `use-markup`."""
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
        frase = f"motivo: {_escapar_markup(motivo)}"
    if frase is None:
        frase = MOTIVO_DA_CEGUEIRA_EM_PORTUGUES["backend_sem_motivo"]
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
    """O construtor de diálogo de consentimento — um dono do widget, N políticas."""
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
    """Diálogo ÚNICO de "posso fechar a Steam?" — HONESTIDADE-STEAM-01."""
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


def frase_sem_aplicacao_em_massa() -> str:
    """A recusa de quem tem uma instalação velha, sem `apply_wrapper_to_all_games`.

    ERA UM LITERAL EM TRÊS LUGARES a partir de 06/09/2026 — os dois caminhos
    deste módulo (com a Steam fechada e com ela aberta) e o gesto da interface
    nova. A frase é UMA; o `getattr` que a dispara é do contrato PATH-06, e uma
    frase com três donos diverge no primeiro dia em que alguém mexe num deles.
    """
    return (
        "Esta instalação ainda não tem a aplicação em massa — "
        f"{como_atualizar_esta_instalacao()}."
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
    """Meia-frase sobre o desligar do Steam Input, a partir de rc + tag."""
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
            return (
                "desliguei o ajuste geral da Steam que assume o controle em "
                "todo jogo; nenhum jogo da sua lista de exceções foi tocado."
            )
        return (
            "o controle voltou a ser entregue pelo Hefesto nos jogos fora da "
            "sua lista de exceções."
        )
    return "a correção rodou sem erro (versão antiga do script, sem confirmação)."


DO_JOGO = "jogo"
DA_MAQUINA = "maquina"

DONO_DO_GESTO: dict[str, tuple[str, str]] = {
    "daemon_start_button": (DA_MAQUINA, "systemctl --user start"),
    "daemon_stop_button": (DA_MAQUINA, "systemctl --user stop"),
    "btn_restart_daemon": (DA_MAQUINA, "systemctl --user restart"),
    "btn_migrate_to_systemd": (DA_MAQUINA, "instala/migra a unidade do usuário"),
    "daemon_autostart_switch": (DA_MAQUINA, "systemctl --user enable/disable"),
    "daemon_refresh_button": (DA_MAQUINA, "só relê o estado; não grava nada"),
    "daemon_logs_button": (DA_MAQUINA, "só lê o journal; não grava nada"),
    "btn_storm_copy_launch": (
        DA_MAQUINA,
        "copia uma CONSTANTE para a área de transferência — a opção de "
        "inicialização é idêntica em qualquer máscara/backend (DEDUP-04/UX-05)",
    ),
    "btn_storm_fix_safe": (
        DA_MAQUINA,
        "drop-in do WirePlumber + quirk anti-storm do módulo de som — "
        "arquivos de configuração do sistema, sem appid nenhum",
    ),
    "btn_steam_game_broken": (
        DO_JOGO,
        "grava UM appid em steam_input_apps.txt — é o gesto mais claramente "
        "por jogo da aba, e é o da T-11",
    ),
    "btn_proton_lock": (
        DO_JOGO,
        "escreve CompatToolMapping por appid no config.vdf (além do default "
        "global) — proton_pin.build_compat_tool_mapping",
    ),
    "btn_camadas_engasgo": (
        DO_JOGO,
        "reescreve o system.reg de CADA prefixo Wine — integrations/"
        "camadas_vulkan.censo(); prefixo é o jogo",
    ),
    # --- os dois em lote, e é aqui que a leitura é discutível -------------
    "btn_steam_ready": (
        DA_MAQUINA,
        "PROVISÓRIO — decisão dela. Escreve a chave GLOBAL do Steam Input E a "
        "opção de inicialização de TODO jogo instalado. O estado por jogo "
        "existe, mas o gesto não sabe escolher um jogo: ele é 'deixe esta "
        "máquina pronta'. Lido como da máquina PELO QUE FAZ HOJE; se ela "
        "decidir que a receita do jogo manda aqui, esta linha vira DO_JOGO",
    ),
    "btn_steam_apply_launch": (
        DA_MAQUINA,
        "PROVISÓRIO — decisão dela. Mesma leitura do btn_steam_ready: "
        "apply_wrapper_to_all_games varre todos os jogos; não há um jogo "
        "escolhido",
    ),
}


BASES_DE_INSTALACAO: tuple[Path, ...] = bases_de_instalacao()


def esta_instalacao_e_um_checkout() -> bool:
    """Há um `install.sh` ao lado deste código?"""
    return repo_files.esta_instalacao_e_um_checkout(BASES_DE_INSTALACAO)


def como_atualizar_esta_instalacao() -> str:
    """O gesto de atualizar que serve para ESTA instalação, sem jargão.

    O texto NÃO se redige aqui — os dois extremos da escada moram em
    `utils/repo_files.FRASE_DE_ATUALIZAR` e os cinco degraus do meio em
    `integrations/storm_doctor.GESTO_DE_ATUALIZAR`, comparados palavra por
    palavra com os do `scripts/doctor.sh` por portão. A **pergunta** é a deste
    módulo, para que trocar `esta_instalacao_e_um_checkout` aqui mude a
    resposta aqui.

    BG-06b (26/08/2026): antes desta linha a resposta parava em dois casos —
    "rode ./install.sh" para quem clonou, e a genérica *"pelo mesmo caminho por
    onde você o instalou"* para todo o resto. Honesta e universal, ela não
    dizia o GESTO; agora o formato é medido e o gesto tem nome
    (`flatpak update`, `pacman -Syu`, …), com a genérica de último degrau para
    o formato que ninguém assume.
    """
    from hefesto_dualsense4unix.integrations.storm_doctor import gesto_de_atualizar

    return gesto_de_atualizar(e_checkout=esta_instalacao_e_um_checkout())


def frase_sem_o_proton_pinado() -> str:
    """A frase de quando o Proton pinado não está nesta máquina."""
    return (
        "Esta instalação ainda não tem o Proton pinado — "
        f"{como_atualizar_esta_instalacao()}."
    )


def format_steam_ready_result(
    *,
    janela: object,
    dados: object,
    script_ok: bool = True,
    wrapper_ok: bool = True,
) -> str:
    """Toast do botão "Deixar tudo pronto" — pura, o miolo testável."""
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
            f"ajuste) — {como_atualizar_esta_instalacao()}."
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
            f"instalação ({como_atualizar_esta_instalacao()})."
        )
    if wrapper_ok:
        partes.append("Jogos: " + format_apply_wrapper_result(dados.get("wrapper")))
    else:
        partes.append(
            "Jogos: esta instalação ainda não sabe ajustar todos de uma vez "
            f"— {como_atualizar_esta_instalacao()}."
        )
    return " ".join(partes)


def _tag_do_script(saida: object) -> str | None:
    """`steam_input_result_tag` com import lazy (evita ciclo entre mixins)."""
    from hefesto_dualsense4unix.app.actions.emulation_actions import (
        steam_input_result_tag,
    )

    return steam_input_result_tag(saida if isinstance(saida, str) else "")


def _jogos_do_relatorio(bruto: object) -> list[str] | None:
    """Rótulos de jogo guardados no relatório do worker, ou `None`."""
    if isinstance(bruto, list) and all(isinstance(x, str) for x in bruto):
        return list(bruto)
    return None


def medir_jogos_com_steam_input() -> list[str] | None:
    """Rótulos dos jogos com Steam Input ligado FORA da allowlist, AGORA."""
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


GUARDA_STEAM_INPUT_TIMER = "hefesto-steam-input-guard.timer"

_GUARDA_PROPRIEDADES = (
    "LoadState",
    "UnitFileState",
    "ActiveState",
    "SubState",
    "NextElapseUSecMonotonic",
    "NextElapseUSecRealtime",
)

_GUARDA_HABILITADO = frozenset({"enabled", "enabled-runtime"})


def interpretar_guarda_do_steam_input(saida: object) -> tuple[str, str] | None:
    """Achado do cartão "Saúde do sistema" sobre o vigia — ou `None` para calar."""
    if not isinstance(saida, str) or not saida.strip():
        return None
    campos: dict[str, str] = {}
    for linha in saida.splitlines():
        chave, sep, valor = linha.partition("=")
        if sep:
            campos[chave.strip()] = valor.strip()
    if not campos:
        return None
    if campos.get("LoadState") != "loaded":
        return None
    if campos.get("UnitFileState") not in _GUARDA_HABILITADO:
        return None

    realtime = campos.get("NextElapseUSecRealtime", "")
    monotonic = campos.get("NextElapseUSecMonotonic", "")
    vivo = bool(realtime and realtime != "n/a") or bool(
        monotonic and monotonic not in {"n/a", "infinity", "0"}
    )
    if vivo:
        return None

    from hefesto_dualsense4unix.integrations import storm_doctor

    if campos.get("ActiveState") != "active":
        motivo = "está habilitada, mas não está rodando"
    else:
        motivo = "consta ligada, mas não tem próximo disparo"
    # dois defeitos das outras doze juntos — dizia "Conserto:" onde as outras
    return (
        storm_doctor.WARN,
        "Steam Input: a rede de segurança "
        f"{motivo} — a Steam pode religar a entrada Steam nos jogos e nada vai "
        f"desfazer. {storm_doctor.PREFIXO_DA_CURA}{como_atualizar_esta_instalacao()}.",
    )


def medir_guarda_do_steam_input() -> tuple[str, str] | None:
    """Lê o estado do vigia no systemd `--user` e devolve o achado, ou `None`."""
    try:
        result = subprocess.run(
            [
                "systemctl",
                "--user",
                "show",
                GUARDA_STEAM_INPUT_TIMER,
                *[f"--property={nome}" for nome in _GUARDA_PROPRIEDADES],
            ],
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )
    except (FileNotFoundError, subprocess.SubprocessError) as exc:
        logger.debug("guarda_steam_input_indisponivel", erro=str(exc))
        return None
    return interpretar_guarda_do_steam_input(result.stdout)


def interpretar_prontuario_dos_jogos(censo: object) -> tuple[str, str] | None:
    """A linha do cartão sobre as pontes que o disco DESMENTE, ou ``None``.

    T-10 (SISTEMA-O-VIGIA-VIVO-01, 25/08/2026). `prontuario_dos_jogos.py` são
    1.037 linhas com **zero chamadores de produção** desde que nasceu — a
    família F2 no seu exemplar mais caro desta casa. Ligar não é "chamar em
    qualquer lugar": o lugar é o cartão "Saúde do sistema" desta aba, no molde
    do `medir_guarda_do_steam_input` — **uma linha só quando há divergência,
    calada quando está alinhado**, que é a regra que ela deu em 22/08 para o
    vigia.

    O que a linha nomeia é `Prontuario.ponte_divergente`: existe um carimbo
    dizendo que a ponte daquele jogo foi confirmada COM Steam Input, e a
    allowlist de hoje diz o contrário (ou vice-versa). O carimbo é evidência
    de outra natureza — ele diz que aquilo já pegou uma vez, com o jogo
    aberto, na máquina dela —, e uma divergência entre ele e o disco é
    exatamente o tipo de coisa que ninguém descobre sem ser avisado.

    **Nomeia, nunca só conta.** É a regra do WRAPPER-EM-TODOS-01, e a razão de
    ela existir tem nome próprio: *"3 jogos com pendência"* é o texto que
    deixou o Pragmata quebrado a noite inteira.

    Pura de propósito (recebe o censo pronto): a leitura do disco é lenta o
    bastante para nunca rodar na linha do GTK, e uma função pura é o que
    permite a mordida existir sem plantar uma biblioteca Steam inteira.
    """
    from hefesto_dualsense4unix.integrations.storm_doctor import PREFIXO_DA_CURA

    jogos = getattr(censo, "jogos", None)
    if not jogos:
        return None
    divergentes = [j for j in jogos if getattr(j, "ponte_divergente", False)]
    if not divergentes:
        return None
    nomes = ", ".join(str(getattr(j, "nome", "?")) for j in divergentes[:3])
    resto = f" e mais {len(divergentes) - 3}" if len(divergentes) > 3 else ""
    return (
        "[WARN]",
        f"Ponte confirmada que não bate com a lista de hoje: {nomes}{resto} — "
        "o jogo foi marcado (ou desmarcado) depois que a ponte pegou. "
        f"{PREFIXO_DA_CURA}abra o perfil dele na aba Perfis e "
        "confira a caixinha do Steam Input.",
    )


def medir_prontuario_dos_jogos() -> tuple[str, str] | None:
    """Levanta o censo do disco e devolve a linha do cartão, ou ``None``."""
    try:
        from hefesto_dualsense4unix.integrations import prontuario_dos_jogos

        censo = prontuario_dos_jogos.levantar_censo()
    except Exception as exc:
        logger.debug("prontuario_dos_jogos_indisponivel", erro=str(exc))
        return None
    return interpretar_prontuario_dos_jogos(censo)


def format_fix_safe_result(relatorio: object) -> str:
    """Toast do botão "Aplicar correções" (sem senha) — pura, testável."""
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
    usuária só declara que o jogo falhou, e o app troca de estratégia (naquele
    jogo o controle FÍSICO fica escondido, e some o controle dobrado).

    NOTA DATADA — 07/08/2026. Este toast dizia *"o Hefesto sai da frente
    dele"*, e a frase está **refutada** pela medição dela de 06/08
    (`CONTROLE-SONY-MEDIDO-01`, seção *A INVERSÃO*, grau MEDIDO): com o jogo
    marcado o Hefesto **mantém a saída inteira** — os gatilhos dela seguraram
    duros e o vermelho dela ficou na lightbar, com o Mullet Mad Jack aberto.
    Quem lia "sai da frente" esperava perder cor e gatilho, que é o contrário
    do que acontece.

    FATO ERRADO, SUBSTITUÍDO (28/08/2026, S4). Até hoje esta docstring e as
    três frases de tela abaixo diziam que a marca *entrega a ENTRADA pela
    Steam*, faz *o jogo enxergar o DualSense físico direto* e **custa o
    co-op**. Os três morreram em **09/08/2026**
    (ESCONDER-EM-VEZ-DE-SAIR-01, decisão dela, commit `d8022ea5`): a marca
    inverteu de lado e passou a **esconder o controle físico**, com os
    virtuais de pé — um por jogador, co-op incluído. O mecanismo vivo está em
    `daemon/subsystems/gamepad.sync_steam_input_exception`, que chama
    `esconder_o_fisico_para_o_jogo`. O ponteiro para o badge do co-op
    derrubado também saiu: `status_actions.tooltip_do_coop_derrubado` não
    existe mais na árvore, porque o estrago que ele anunciava acabou.
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
    # DUPLO-REGISTRO-01 mediu o Pragmata com `UseSteamControllerConfig "2"` no
    # enxergar o DualSense físico direto. A saída — cor, gatilhos, vibração —
    resto = (
        " Feche e abra o jogo de novo: nele os controles físicos ficam "
        "escondidos e o jogo passa a ver só os do Hefesto — você não precisa "
        "configurar nada na Steam, e a marca sobrevive a reiniciar a "
        "máquina. Se ainda assim o jogo não responder, o guia é "
        "docs/usage/jogos-e-mascaras.md."
    )
    if status == "ja_estava":
        return (
            f"O jogo {appid} já estava marcado — nele o controle físico já "
            f"fica escondido, sem o controle dobrado.{resto}"
        )
    return (
        f"Anotei: no jogo {appid} o controle físico fica escondido e o jogo "
        f"vê só os do Hefesto, sem o controle dobrado — e a sua cor, os seus "
        f"jogadores e os seus gatilhos continuam valendo.{resto}"
    )


_RECUSAS_DO_PROTON: dict[str, str] = {
    "jogo_da_steam_aberto": (
        "NÃO travei nada — havia um jogo aberto. Feche o jogo e clique de novo."
    ),
    "steam_aberta": (
        "NÃO travei nada — a Steam continuou aberta. Feche a Steam e clique "
        "de novo."
    ),
    "outra_trava_em_curso": (
        "NÃO travei nada — outro processo do Hefesto estava mexendo na "
        "configuração da Steam (o vigia da Steam ou o instalador). Clique de "
        "novo em seguida."
    ),
}

_RECUSA_DO_PROTON_SEM_MOTIVO = (
    "NÃO travei nada — a Steam recusou a mudança; veja os "
    "'Detalhes técnicos'."
)


def _frase_de_recusa_do_proton(result: dict[str, object]) -> str | None:
    """A frase da RECUSA, ou ``None`` quando não houve recusa.

    T-04. `lock_games_to_pinned_proton` já devolvia
    ``status="recusado"`` com o motivo, e `lock_proton_for_all_games`
    traduzia o retorno jogando os dois fora: sobrava
    ``errors = 1 if status == "erro" else 0``, e recusa NÃO é erro para essa
    conta. O dicionário que chegava aqui era ``{locked:0, skipped:0,
    errors:0}`` — byte-idêntico ao de "não havia nada a fazer" — e o ramo
    ``elif errors == 0`` comemorava *"os jogos já estão no Proton
    validado"* logo depois de o gate ter recusado.

    É a família F1 na forma mais pura: a verdade estava calculada e a ponte
    a descartava. A cura é aqui e não no ramo de baixo porque a recusa tem
    de vencer ANTES de qualquer contagem — contar zero e concluir "então
    estava tudo certo" é justamente o raciocínio errado.

    Compatível com quem ainda não manda `status` (a chave é opcional): sem
    ela, devolve ``None`` e o comportamento é o de antes.
    """
    if result.get("status") != "recusado":
        return None
    motivo = result.get("reason")
    if motivo == "pino_ausente":
        return frase_sem_o_proton_pinado()
    if isinstance(motivo, str) and motivo in _RECUSAS_DO_PROTON:
        return _RECUSAS_DO_PROTON[motivo]
    return _RECUSA_DO_PROTON_SEM_MOTIVO


def format_proton_lock_result(result: object) -> str:
    """Mensagem pro leigo a partir do dict do ``lock_proton_for_all_games``.

    Pura (testável sem GTK) — o miolo do toast do botão "Travar Proton
    validado" (PLAT-01). Contrato esperado da lane do pin
    (``integrations/proton_pin``): ``{locked, skipped, errors}`` com
    contagens (int) ou listas de itens — ``applied`` é aceito como sinônimo
    de ``locked`` — e, opcionais, ``tool`` (str, o nome da versão pinada) e
    o par ``status``/``reason`` (T-04, 25/08/2026).
    Resposta fora do contrato vira recusa honesta, nunca "Pronto".
    """
    if not isinstance(result, dict):
        return (
            "Não consegui travar o Proton — resposta inesperada; veja os "
            "'Detalhes técnicos'."
        )
    recusa = _frase_de_recusa_do_proton(result)
    if recusa is not None:
        return recusa
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
    _daemon_autostart_attempts: int = 0

    def install_daemon_tab(self) -> None:
        self._daemon_autostart_guard = False
        # Inicializa contador anti-loop por instância (bootstrap da GUI).
        self._daemon_autostart_attempts = 0
        self._set_daemon_status_consulting()
        self._refresh_daemon_view_async()
        self._sync_restart_daemon_button_sensitivity()
        self._refresh_storm_diag()
        self._refresh_window_detect_diag()  # JANELA-CEGA-01
        self._wire_steam_simple_buttons()

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


    def _find_repo_file(self, relpath: str) -> Path | None:
        """Localiza um arquivo do repo (ex.: scripts/install_snd_quirk.sh).

        A busca é de `utils/repo_files` — esta era uma das cinco listas de
        "onde estão os scripts", e a que contava a raiz do checkout à mão já
        pagou a BUG-GUI-REPO-ROOT-OFFBYONE-01 (os botões do cartão anti-storm
        viravam no-op SILENCIOSO: toast de sucesso, nada executado).
        """
        return encontrar_arquivo_do_repo(relpath, bases=BASES_DE_INSTALACAO)

    def _refresh_storm_diag(self) -> None:
        """Popula o cartão anti-storm (read-only) em thread worker."""
        def _worker() -> None:
            try:
                from hefesto_dualsense4unix.integrations import storm_doctor

                # ele, um DualSense com áudio responderia pelos quatro. O
                # state_full é best-effort: daemon offline devolve None e o
                # check volta a responder presente/ausente (nunca alarme falso
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

            with contextlib.suppress(Exception):
                achado = medir_guarda_do_steam_input()
                if achado is not None:
                    rows = [*rows, achado]
            with contextlib.suppress(Exception):
                achado = medir_prontuario_dos_jogos()
                if achado is not None:
                    rows = [*rows, achado]
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
        return False


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
                # o daemon VIVO sempre que o `state_full` passa dos 0,25s default.
                timeout_s=STATE_IPC_TIMEOUT_S,
            )
        except Exception as exc:  # pragma: no cover — rede de segurança da aba
            logger.debug("window_detect_diag_indisponivel", err=str(exc))

    def on_storm_fix_safe(self, _btn: object) -> None:
        """Reaplica os fixes SEGUROS (sem sudo): Steam Input OFF + WirePlumber."""
        self._toast_daemon("Aplicando correções (não pede senha)…")

        def _worker() -> None:
            relatorio: dict[str, Any] = {
                "ran": 0,
                "missing": 0,
                "steam_input": None,
                "steam_input_jogos": medir_jogos_com_steam_input(),
            }
            for relpath, args in (
                ("scripts/disable_steam_input.sh", ["--apply-quiet"]),
                ("scripts/fix_wireplumber_default_source.sh", ["--install"]),
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
                        relatorio["steam_input"] = (
                            proc.returncode,
                            (proc.stdout or "") + (proc.stderr or ""),
                        )
            GLib.idle_add(self._refresh_storm_diag)
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
        del flavor, backend
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

    def on_storm_copy_launch(self, _btn: object) -> None:
        """Copia a Opção de Inicialização da Steam — a chamada do wrapper."""
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
                f"({como_atualizar_esta_instalacao()}) — a opção continua "
                "abrindo o jogo, mas "
                "sem esconder o controle físico (pode duplicar) até o "
                "install completar."
            )
        if copied:
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

    _STEAM_APPLY_CORPO = (
        "O Hefesto entra nos jogos da Steam, do Heroic, do Lutris e dos emuladores. "
        "As opções que você já tem nos jogos são preservadas: na Steam fica um "
        "backup ao lado de cada arquivo, e nos outros eu anoto o que pus, para "
        "tirar quando o Hefesto for desinstalado.\n\n"
        "Nos outros lançadores eu escrevo na hora, sem fechar nada, e vale na "
        "próxima vez que cada um abrir. A Steam só aceita fechada: se ela estiver "
        "aberta eu peço a sua permissão antes de fechá-la por uns 20 segundos e "
        "abro de novo em seguida. Com um jogo aberto, a Steam fica para depois."
    )

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
        with contextlib.suppress(Exception):
            dialog.get_style_context().add_class(
                "hefesto-dualsense4unix-window"
            )
        dialog.format_secondary_text(self._STEAM_APPLY_CORPO)
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
                        self._toast_daemon, frase_sem_aplicacao_em_massa()
                    )
                    return
                if slo.steam_game_running():
                    GLib.idle_add(
                        self._toast_daemon,
                        format_steam_janela_recusa("jogo_aberto"),
                    )
                    return
                if slo.steam_running():
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
                    self._detalhe_tecnico,
                    traceback.format_exc(),
                )
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
        """Mostra o consentimento e, com o sim, roda `prosseguir()` em worker."""

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
                    self._toast_daemon, frase_sem_aplicacao_em_massa()
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
            GLib.idle_add(self._detalhe_tecnico, traceback.format_exc())
            GLib.idle_add(
                self._toast_daemon,
                "Não consegui aplicar — veja os 'Detalhes técnicos'.",
            )

    # --- Modo simples: dois botões que escondem os conceitos --------------
    # continuam existindo; o que sai da tela é a ESCOLHA entre eles.
    #                               (e só ela — ver `format_game_broken_result`).

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
        """Botão "Este jogo não funciona" — troca a estratégia DESTE jogo."""
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
                        "Esta instalação ainda não sabe marcar jogos — "
                        f"{como_atualizar_esta_instalacao()}.",
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
        """Botão "Travar Proton validado" (PLAT-01, aba Sistema)."""
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
                    GLib.idle_add(self._toast_daemon, frase_sem_o_proton_pinado())
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
                result = lock_fn(todos=True)
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
        """Mostra o estado transitório "Consultando..." no label da aba Sistema."""
        label = self._get("daemon_status_label")
        if label is None:
            return
        label.set_markup('<span foreground="#8b8fa8"> Verificando…</span>')
        label.set_tooltip_text("Verificando se o Hefesto está rodando. Aguarde.")

    def _refresh_daemon_view_async(self) -> None:
        """Dispara `_refresh_daemon_view` em thread worker, sem bloquear o GTK."""
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
        """Aplica o resultado do refresh assíncrono na thread GTK."""
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

        self._aplicar_sensibilidade_ligar_desligar(status)

        self._set_daemon_text(text)
        return False

    _ESTADOS_COM_DAEMON_DE_PE: ClassVar[frozenset[str]] = frozenset(
        {"online_systemd", "online_avulso", "iniciando"}
    )

    def _aplicar_sensibilidade_ligar_desligar(self, status: DaemonStatus) -> None:
        """Cinza o botão que não tem o que fazer neste estado."""
        de_pe = status in self._ESTADOS_COM_DAEMON_DE_PE

        btn_start = self._get("daemon_start_button")
        if btn_start is not None:
            btn_start.set_sensitive(not de_pe)
            btn_start.set_tooltip_text(
                "O Hefesto já está ligado."
                if de_pe
                else "Liga o Hefesto agora."
            )

        btn_stop = self._get("daemon_stop_button")
        if btn_stop is not None:
            btn_stop.set_sensitive(de_pe)
            btn_stop.set_tooltip_text(
                "Desliga o Hefesto — o controle volta ao modo puro do Linux."
                if de_pe
                else "O Hefesto já está desligado."
            )

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
        """Retorna True se o pid file do daemon aponta para processo vivo."""
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

        from hefesto_dualsense4unix.utils import chave as _chave

        _motivo = _chave.motivo_do_desligamento()
        if _motivo is not None:
            logger.warning("daemon_nao_subiu_chave_posta", motivo=_motivo)
            return -1

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
                "O Hefesto ainda não foi instalado como serviço — "
                f"{como_atualizar_esta_instalacao()}."
            )


    def on_daemon_start(self, _btn: Gtk.Button) -> None:
        self._user_stopped_daemon = False
        self._run_systemctl_async("start")

    def on_daemon_stop(self, _btn: Gtk.Button) -> None:
        """Desliga o Hefesto — e o desligamento PEGA, como o da aba Início.

        T-06 (25/08/2026): o flag `_user_stopped_daemon` é armado em
        `_on_systemctl_done`, no SUCESSO — não aqui. Armar no clique repetiria
        o defeito que a BUG-HOME-SHUTDOWN-FALSE-OK-01 já pagou na Início: um
        `systemctl` com `rc != 0` (sem sessão systemd, daemon avulso) não
        desligou nada, e o flag armado à toa faria a GUI recusar-se a
        ressuscitar um daemon que nunca parou.

        Por que isto importa: sem o flag, `ensure_daemon_running` religa o
        daemon na próxima abertura da janela, e o "Desligar" desta aba dura
        até o próximo `F5`. A aba Início arma o flag desde sempre
        (`home_actions.py`); esta não armava — e quando o desligamento da
        Início falha, ela manda a pessoa *"tentar pela aba Sistema"*, ou
        seja, para o caminho mais fraco dos dois.
        """
        self._run_systemctl_async("stop")

    # que trata erro com diálogo não-bloqueante e tem regra de sensibilidade própria.

    def _refresh_daemon_tab_on_show(self) -> None:
        """Reconcilia a aba Sistema ao ser exibida (M7): status do daemon + o"""
        self._refresh_daemon_view_async()
        self._refresh_storm_diag()
        self._refresh_window_detect_diag()

    def on_daemon_refresh(self, _btn: Gtk.Button) -> None:
        self._refresh_daemon_view_async()
        self._refresh_storm_diag()
        self._refresh_window_detect_diag()
        self._sync_restart_daemon_button_sensitivity()

    def on_daemon_service_restart(self, _btn: Gtk.Button) -> None:
        """Handler do botão 'Reiniciar daemon' (UX-RECONNECT-01)."""
        self._toast_daemon("Reiniciando o Hefesto…")

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
                f"Hefesto usa — {como_atualizar_esta_instalacao()}."
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
            self._show_restart_error(
                "O Hefesto não reiniciou. Tente 'Desligar o Hefesto' e "
                "'Ligar o Hefesto'; os 'Detalhes técnicos' aqui embaixo "
                "mostram o motivo."
            )
            return False
        logger.info("daemon_restart_ok", unit=SERVICE_NORMAL)
        self._toast_daemon("Hefesto reiniciado.")
        self._refresh_daemon_view_async()
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
        with contextlib.suppress(Exception):
            dialog.get_style_context().add_class(
                "hefesto-dualsense4unix-window"
            )
        dialog.format_secondary_text(message)
        dialog.connect("response", lambda d, _r: d.destroy())
        dialog.show_all()

    def on_daemon_view_logs(self, _btn: Gtk.Button) -> None:
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


    def on_daemon_migrate_to_systemd(self, _btn: Gtk.Button) -> None:
        """Handler do botão 'Migrar para systemd' (BUG-DAEMON-STATUS-MISMATCH-01)."""
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
            self._toast_daemon(MIGRAR_DEU_CERTO)
        else:
            logger.warning("daemon_migrate_falhou", unit=SERVICE_NORMAL, rc=rc)
            self._toast_daemon(MIGRAR_NAO_DEU)
        self._refresh_daemon_view_async()
        return False


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
        """Atualiza a aba Sistema com base no estado canônico do daemon."""
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

        btn_migrate = self._get("btn_migrate_to_systemd")
        if btn_migrate is not None:
            btn_migrate.set_visible(status == "online_avulso")

        text = self._systemctl_status_text(SERVICE_NORMAL)
        self._set_daemon_text(text)

    def _run_systemctl_async(self, action: str) -> None:
        """Executa systemctl em thread worker para não bloquear a thread GTK."""
        unit = SERVICE_NORMAL

        def _worker() -> None:
            if action in ("start", "restart"):
                self._invoke_systemctl(["reset-failed", unit], check=False)
            result = self._invoke_systemctl([action, unit], capture=True)
            rc = result.returncode if result is not None else -1
            erro = (getattr(result, "stderr", "") or "") if result is not None else ""
            GLib.idle_add(self._on_systemctl_done, action, unit, rc, erro)

        _get_executor().submit(_worker)

    def _on_systemctl_done(
        self, action: str, unit: str, rc: int, detalhe: str = ""
    ) -> bool:
        """Callback pós-systemctl — executa na thread principal GTK."""
        if rc == 0:
            if action == "stop":
                self._user_stopped_daemon = True
            self._limpar_detalhe_tecnico()
            self._toast_daemon(
                _SYSTEMCTL_OK_MSG.get(action, "Pronto.")
            )
        else:
            logger.warning("systemctl_acao_falhou", acao=action, unit=unit, rc=rc)
            falha = _SYSTEMCTL_FAIL_MSG.get(action, "Não consegui")
            self._detalhe_tecnico(
                detalhe or f"systemctl {action} {unit} devolveu rc={rc}",
                assunto=f"systemctl {action}",
            )
            self._toast_daemon(
                f"{falha} — veja 'Detalhes técnicos' aqui embaixo."
            )
        self._refresh_daemon_view_async()
        return False

    def _set_daemon_status_markup(
        self, status: DaemonStatus, enabled: str
    ) -> None:
        """Pinta o label de status com cor e tooltip PT-BR conforme estado canônico."""
        label = self._get("daemon_status_label")
        if label is None:
            return

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
        """Troca o CORPO do painel — o `systemctl status` e afins."""
        self._texto_base_do_painel = text
        self._pintar_painel_tecnico()

    def _detalhe_tecnico(self, texto: object, *, assunto: str = "") -> bool:
        """Põe a saída CRUA de uma falha no painel "Detalhes técnicos"."""
        bruto = "" if texto is None else str(texto).strip()
        if not bruto:
            return False
        cabecalho = f"--- {assunto} ---" if assunto else "--- detalhe do erro ---"
        self._ultimo_detalhe_tecnico = f"{cabecalho}\n{bruto}"
        self._pintar_painel_tecnico()
        return False

    def _limpar_detalhe_tecnico(self) -> None:
        """Apaga o rodapé de erro — chamado quando a ação seguinte dá certo."""
        self._ultimo_detalhe_tecnico = ""
        self._pintar_painel_tecnico()

    def _pintar_painel_tecnico(self) -> None:
        """Corpo + rodapé, sem escapes ANSI, rolado até o fim."""
        try:
            view: Gtk.TextView = self._get("daemon_status_text")
        except Exception:
            logger.debug("painel_tecnico_sem_widget", exc_info=True)
            return
        if view is None:
            return
        base = getattr(self, "_texto_base_do_painel", "") or ""
        detalhe = getattr(self, "_ultimo_detalhe_tecnico", "") or ""
        text = f"{base}\n\n{detalhe}" if detalhe else base
        buf: Gtk.TextBuffer = view.get_buffer()
        text = re.sub(r"\x1b\[[0-9;]*m", "", text)
        buf.set_text(text)
        self._scroll_textview_to_end(view)
        GLib.idle_add(self._scroll_textview_to_end, view)

    @staticmethod
    def _scroll_textview_to_end(view: Gtk.TextView) -> bool:
        buf = view.get_buffer()
        end_iter = buf.get_end_iter()
        view.scroll_to_iter(end_iter, 0.0, True, 0.0, 1.0)
        return False

    def _systemctl_oneline(self, args: list[str]) -> str:
        result = self._invoke_systemctl(args, capture=True, check=False)
        if result is None:
            return ""
        return (result.stdout or "").strip().splitlines()[:1][0] if result.stdout.strip() else ""

    def _systemctl_status_text(self, unit: str) -> str:
        result = self._invoke_systemctl(
            ["status", unit, "--no-pager", "-n", "0"], capture=True, check=False
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
