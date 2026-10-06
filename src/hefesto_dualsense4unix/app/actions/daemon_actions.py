"""Aba Sistema: o Hefesto está funcionando? liga sozinho? está saudável?"""
# ruff: noqa: E402
from __future__ import annotations

import subprocess
from collections.abc import Sequence
from pathlib import Path
from typing import ClassVar, Literal

import gi

gi.require_version("Gtk", "3.0")

from hefesto_dualsense4unix.app.actions.base import WidgetAccessMixin
from hefesto_dualsense4unix.daemon.service_install import SERVICE_NORMAL
from hefesto_dualsense4unix.integrations.steam_launch_options import juntar_rotulos
from hefesto_dualsense4unix.utils import repo_files
from hefesto_dualsense4unix.utils.logging_config import get_logger
from hefesto_dualsense4unix.utils.repo_files import (
    bases_de_instalacao,
    encontrar_arquivo_do_repo,
)

logger = get_logger(__name__)

DaemonStatus = Literal["online_systemd", "online_avulso", "iniciando", "offline"]

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
    aberto, na máquina do usuário —, e uma divergência entre ele e o disco é
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
    (ESCONDER-EM-VEZ-DE-SAIR-01, decisão de produto, commit `d8022ea5`): a marca
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


    def _find_repo_file(self, relpath: str) -> Path | None:
        """Localiza um arquivo do repo (ex.: scripts/install_snd_quirk.sh).

        A busca é de `utils/repo_files` — esta era uma das cinco listas de
        "onde estão os scripts", e a que contava a raiz do checkout à mão já
        pagou a BUG-GUI-REPO-ROOT-OFFBYONE-01 (os botões do cartão anti-storm
        viravam no-op SILENCIOSO: toast de sucesso, nada executado).
        """
        return encontrar_arquivo_do_repo(relpath, bases=BASES_DE_INSTALACAO)


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


    _ESTADOS_COM_DAEMON_DE_PE: ClassVar[frozenset[str]] = frozenset(
        {"online_systemd", "online_avulso", "iniciando"}
    )


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


    # que trata erro com diálogo não-bloqueante e tem regra de sensibilidade própria.


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
