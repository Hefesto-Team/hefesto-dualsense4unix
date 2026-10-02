"""Aba Emulação: status do gamepad virtual Xbox360 + config."""
# ruff: noqa: E402
from __future__ import annotations

import contextlib
import glob
import html
import os
import re
import subprocess
from collections.abc import Sequence
from pathlib import Path
from typing import Any, ClassVar

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import GLib, Gtk

from hefesto_dualsense4unix.app.actions.base import WidgetAccessMixin
from hefesto_dualsense4unix.app.actions.home_actions import registrar_modo_no_rascunho
from hefesto_dualsense4unix.app.actions.mode_transition import (
    MODE_DESKTOP,
    MODE_GAMEPAD,
    MODE_NATIVE,
    STATE_IPC_TIMEOUT_S,
    apply_mode,
    mode_of_state,
)
from hefesto_dualsense4unix.app.draft_config import DraftConfig
from hefesto_dualsense4unix.app.ipc_bridge import _get_executor, call_async, run_in_thread
from hefesto_dualsense4unix.integrations.hotkey_daemon import DEFAULT_BUFFER_MS
from hefesto_dualsense4unix.integrations.uinput_gamepad import (
    DEVICE_NAME,
    DUALSENSE_EDGE_NAME,
    XBOX360_NAME,
    XBOX360_PRODUCT,
    XBOX360_VENDOR,
)
from hefesto_dualsense4unix.utils.logging_config import get_logger
from hefesto_dualsense4unix.utils.repo_files import (
    como_atualizar_esta_instalacao,
    encontrar_arquivo_do_repo,
)

logger = get_logger(__name__)

UINPUT_DEV = "/dev/uinput"

# "/dev/input/js*"))`. Medido nesta máquina em 31/07/2026, com UM DualSense no
#   js0  Sony … DualSense Wireless Controller           uniq=<MAC dela>
#   js1  Sony … DualSense … Motion Sensors              uniq=<O MESMO MAC>
#   js2  DualSense Wireless Controller (Hefesto P1)    uniq=02:fe:00:00:00:01
#   js3  DualSense … (Hefesto P1) Motion Sensors        uniq=<O MESMO>
#   (o nome do vpad era `Hefesto Virtual DualSense P1` quando isto foi medido;
# 1. todo controle da classe DualSense abre DOIS nós (o gamepad e os sensores

_VPAD_UNIQ_PREFIX = "02:fe:"

#: publica `DualSense Wireless Controller (Hefesto P{n})`
#: POR QUE SUBSTRING E NÃO PREFIXO: o nome de hoje COMEÇA por "DualSense
_VPAD_MARCA_NO_NOME = "(Hefesto P"

_UINPUT_SUBTREE = "/devices/virtual/input/"

#: mostra: um DualSense Edge REAL publica exatamente `DUALSENSE_EDGE_NAME`, e
_VPAD_NOMES_EM_UINPUT = (XBOX360_NAME, DUALSENSE_EDGE_NAME)

LARGURA_MAXIMA_DO_ROTULO_DE_GAMEPADS = 52


# DualSense "funcionam completos: vibração, giroscópio e lightbar". O mapa de

RESSALVA_DE_TRANSPORTE: dict[str, str] = {}

AFIRMACOES_DE_TRANSPORTE_DA_ABA: dict[str, tuple[str, ...]] = {
    "emulation_gamepad_dualsense_button": ("vibracao.rumble.passthrough@dualsense",),
    "emulation_gamepad_xbox_button": (
        "vibracao.rumble.passthrough@dualsense",
        "movimento.giroscopio.jogo@dualsense",
    ),
    "emulation_gamepad_hint_label": (
        "vibracao.rumble.passthrough@dualsense",
        "movimento.giroscopio.jogo@dualsense",
        "luz.lightbar.cor@dualsense",
    ),
}

RADICAIS_DE_TRANSPORTE: dict[str, str] = {
    "vibracao.rumble.passthrough@dualsense": "vibra",
    "movimento.giroscopio.jogo@dualsense": "giroscóp",
    "luz.lightbar.cor@dualsense": "lightbar",
}


def _chave_do_aparelho(no: dict[str, str]) -> str:
    """Identidade do APARELHO por trás de um nó de joystick.

    O `uniq` (MAC) é o que colapsa "DualSense" e "DualSense Motion Sensors"
    num controle só. Sem ele, a chave vem do sysfs — e o número de níveis a
    subir depende do barramento (ver o item (b) do bloco acima).
    """
    uniq = no.get("uniq", "").strip().lower()
    if uniq:
        return uniq
    sysfs = no.get("sys", "")
    if not sysfs:
        return no.get("path", "")
    dir_input = os.path.dirname(sysfs)
    if _UINPUT_SUBTREE in sysfs:
        return dir_input
    return os.path.dirname(os.path.dirname(dir_input))


def _e_vpad_do_hefesto(no: dict[str, str]) -> bool:
    """True quando o aparelho é um gamepad virtual NOSSO — nos dois backends."""
    uniq = no.get("uniq", "").strip().lower()
    nome = no.get("name", "").strip()
    if uniq.startswith(_VPAD_UNIQ_PREFIX) or _VPAD_MARCA_NO_NOME in nome:
        return True
    return (
        _UINPUT_SUBTREE in no.get("sys", "") and nome in _VPAD_NOMES_EM_UINPUT
    )


def classificar_joysticks(nos: list[dict[str, str]]) -> tuple[int, int, int]:
    """`(físicos, nossos, de outros programas)` — APARELHOS, não nós."""
    por_aparelho: dict[str, dict[str, str]] = {}
    for no in nos:
        por_aparelho.setdefault(_chave_do_aparelho(no), no)
    fisicos = nossos = outros = 0
    for no in por_aparelho.values():
        if _e_vpad_do_hefesto(no):
            nossos += 1
        elif _UINPUT_SUBTREE in no.get("sys", ""):
            outros += 1
        else:
            fisicos += 1
    return fisicos, nossos, outros


def _atributos_do_joystick(caminho: str) -> dict[str, str]:
    """Lê do sysfs o que :func:`classificar_joysticks` precisa julgar."""
    nome_no = os.path.basename(caminho)
    base = f"/sys/class/input/{nome_no}"
    atributos = {"path": caminho, "name": "", "uniq": "", "sys": ""}
    with contextlib.suppress(OSError):
        atributos["sys"] = os.path.realpath(base)
    for campo in ("name", "uniq"):
        with contextlib.suppress(OSError), open(
            f"{base}/device/{campo}", encoding="utf-8"
        ) as fh:
            atributos[campo] = fh.read().strip()
    return atributos


def rotulo_gamepads(fisicos: int, nossos: int, outros: int, nos: int) -> str:
    """Texto do campo "Gamepads:" da aba Emulação."""
    if nos <= 0:
        return "Nenhum controle detectado pelo sistema"
    partes: list[str] = []
    if fisicos:
        partes.append(
            "1 controle físico" if fisicos == 1 else f"{fisicos} controles físicos"
        )
    if nossos:
        partes.append(
            "1 gamepad virtual do Hefesto"
            if nossos == 1
            else f"{nossos} gamepads virtuais do Hefesto"
        )
    if outros:
        partes.append(
            "1 gamepad virtual de outro programa (Steam Input)"
            if outros == 1
            else f"{outros} gamepads virtuais de outros programas (Steam Input)"
        )
    if not partes:
        partes.append("Nenhum aparelho reconhecido")
    return f"{', '.join(partes)} — {nos} nós em /dev/input/js*"


_RESULTADO_RE = re.compile(r"^\[steam-input\] resultado=(\S+)\s*$", re.MULTILINE)


def steam_input_result_tag(saida: str) -> str | None:
    """Tag `resultado=` da saída do script (a ÚLTIMA, se houver mais de uma)."""
    achados = _RESULTADO_RE.findall(saida or "")
    return achados[-1] if achados else None


def format_steam_input_result(
    *,
    status: str,
    rc: int = 0,
    tag: str | None = None,
    ainda_ligado: bool | None = None,
) -> str:
    """Toast do botão "Desligar Steam Input" — pura, o miolo testável.

    Regra inegociável (HONESTIDADE-STEAM-01): NENHUM caminho devolve "Pronto"
    sem evidência. "Evidência" aqui é a releitura do vdf (`ainda_ligado`), não
    a palavra do script — script pode sair 0 tendo adiado.

    `status` é o que a GUI decidiu ANTES de rodar: ``sem_script`` |
    ``jogo_aberto`` | ``cancelado`` | ``nao_fechou`` | ``executado``.
    """
    if status == "sem_script":
        return (
            "Não encontrei o script que desliga o Steam Input nesta "
            f"instalação — {como_atualizar_esta_instalacao()}."
        )
    if status == "jogo_aberto" or tag == "recusado-jogo-aberto":
        return (
            "Tem um jogo aberto — não fecho a Steam agora (você perderia o "
            "progresso não salvo). Feche o jogo e clique de novo. "
            "Nada foi mudado."
        )
    if status == "cancelado":
        return (
            "Nada foi mudado — a Steam continua aberta. Clique de novo quando "
            "puder deixá-la fechada por uns 20 segundos."
        )
    if status == "nao_fechou" or tag == "steam-nao-fechou":
        return (
            "A Steam não fechou — não mexi em nada. Com ela viva a mudança "
            "seria perdida (a Steam regrava o arquivo ao sair). Feche-a pela "
            "própria Steam e clique de novo."
        )
    if tag == "adiado-steam-aberta":
        return (
            "A Steam está aberta — a correção foi ADIADA e nada mudou. "
            "Feche a Steam e clique de novo."
        )
    if rc != 0 or tag == "erro":
        return (
            f"Não consegui desligar o Steam Input (o script terminou com "
            f"erro {rc}) — veja os 'Detalhes técnicos'."
        )
    if ainda_ligado is True:
        return (
            "O script rodou sem erro, mas o Steam Input CONTINUA ligado — "
            "nada foi desligado. Veja os 'Detalhes técnicos'."
        )
    if tag == "nada-a-fazer":
        return "Nada a mudar — o Steam Input já estava desligado."
    if ainda_ligado is False:
        return "Pronto — Steam Input desligado."
    return (
        "O script rodou sem erro, mas não consegui conferir o resultado "
        "(não achei os arquivos da Steam)."
    )


STEAM_NAO_ENCONTRADA = (
    "Steam não encontrada — procurei em ~/.steam, ~/.local/share/Steam, "
    "Flatpak e Snap"
)


def markup_status_steam_input(
    on: bool | None,
    jogos: Sequence[str],
    excecoes: Sequence[int],
) -> str:
    """Markup da linha "Steam Input" da aba Emulação — pura, testável sem GTK."""
    if on is None:
        markup = f'<span foreground="#8b8fa8">{STEAM_NAO_ENCONTRADA}</span>'
    elif on:
        if jogos:
            corpo = f"Ligado em {len(jogos)} {'jogo' if len(jogos) == 1 else 'jogos'}"
        else:
            corpo = "Ligado no ajuste global da Steam"
        markup = f'<span foreground="#ffb86c">{html.escape(corpo)}</span>'
    else:
        markup = '<span foreground="#50fa7b">Desligado — tudo certo</span>'
    if excecoes:
        markup += (
            f' <span foreground="#8b8fa8">· Exceção por jogo: '
            f'{len(excecoes)} jogo(s)</span>'
        )
    return markup


#: publicado pelo daemon no bloco ``keyboard_emulation`` do ``daemon.status`` e
#: do ``daemon.state_full`` (``daemon/ipc_handlers.py:_keyboard_emulation_payload``;
BLOQUEIO_DO_TECLADO_EM_PORTUGUES: dict[str, str] = {
    "desligada": (
        "Desligado: o controle não digita mais nada — nem os atalhos da lista "
        "abaixo, nem o teclado na tela em L3/R3, nem as três regiões do "
        "touchpad (Backspace, Enter e Delete)."
    ),
    "sem_device": (
        "Ligado, mas o teclado virtual não subiu. Abra a aba Sistema e clique "
        "em “Consertar problemas conhecidos”."
    ),
    "modo_jogo": (
        "Ligado, em pausa agora: o modo jogo está suspendendo mouse e teclado."
    ),
    # inteira, com a nota datada de 07/08 que ela já custou (abaixo). Marcar
    "vpad_suspenso_pelo_steam_input": (
        "Ligado, em pausa agora: neste jogo quem entrega o controle é a Steam, "
        "e o controle virtual foi recolhido. Não foi desligado — volta sozinho "
        "quando você fechar o jogo."
    ),
}

BLOQUEIO_SEM_CAMINHO_DE_PRODUCAO: dict[str, str] = {
    "vpad_suspenso_pelo_steam_input": (
        "MEDIDO em 25/08/2026 (VPAD-SUSPENSO-MORTO-01/E1, reconferido aqui). O "
        "predicado de daemon/lifecycle.py:1581 só devolve esta constante sob a "
        "flag do vpad suspenso, e nada em produção a põe em True: o armador de "
        "daemon/subsystems/gamepad.py:461 tem zero chamadores em src/. A causa "
        "é decisão dela (ESCONDER-EM-VEZ-DE-SAIR-01, `d8022ea`, 09/08/2026), e "
        "reviver ou apagar a frase é da mantenedora — a pergunta aberta é se o "
        "par (excecao ativa, vpad suspenso) vira um estado só."
    ),
}

TECLADO_SEM_ESTADO = (
    "Não consegui ler o estado do teclado emulado — o Hefesto pode estar "
    "desligado. Veja a aba Sistema."
)


def descrever_teclado_emulado(bloco: object) -> tuple[bool | None, str]:
    """(posição do interruptor, frase embaixo dele) a partir do bloco do daemon."""
    if not isinstance(bloco, dict) or not isinstance(bloco.get("enabled"), bool):
        return None, TECLADO_SEM_ESTADO
    ligado = bool(bloco["enabled"])
    bloqueio = bloco.get("bloqueio")
    if bloqueio is None:
        return ligado, ""
    if not isinstance(bloqueio, str):
        return ligado, ""
    texto = BLOQUEIO_DO_TECLADO_EM_PORTUGUES.get(bloqueio)
    if texto is not None:
        return ligado, texto
    return ligado, f"Ligado, em pausa agora (motivo: {bloqueio})."


MODO_JOGO_GUARDADO_SEM_REGRA = (
    "Modo jogo ligado — mouse e teclado suspensos agora, e guardei no perfil. "
    "Como ele vale para qualquer janela, o Hefesto não liga o modo jogo sozinho "
    "na próxima ativação (senão o desktop acordaria sem mouse). Dê uma regra a "
    "ele na aba Perfis para ele voltar ligado."
)


def perfil_do_rascunho_tem_opiniao(draft: DraftConfig | None) -> bool:
    """Espelha `lifecycle._perfil_tem_opiniao` para o perfil de ORIGEM do rascunho."""
    from hefesto_dualsense4unix.profiles.schema import Profile

    match = getattr(draft, "source_match", None)
    if match is None:
        return False
    try:
        sonda = Profile(name="sonda", match=match)
    except Exception:
        return False
    return not sonda.e_catch_all


def rascunho_com_modo_jogo(
    draft: DraftConfig | None, ligado: bool
) -> tuple[DraftConfig | None, bool]:
    """(rascunho, guardei?) para o "modo jogo". Pura: NÃO aplica nada."""
    if draft is None:
        return draft, False
    return draft.with_suppress(ligado), True


def frase_do_modo_jogo(
    padrao: str, *, ligado: bool, guardado: bool, tem_regra: bool
) -> str:
    """Toast do botão "Modo jogo" — pura, o miolo testável sem GTK.

    Três casos, e nenhum deles pode afirmar mais do que aconteceu:

    - DESLIGAR, ou perfil COM regra: a frase normal do gesto. Guardou, e na
      próxima ativação o daemon liga de novo (é o ramo `if desired:` com opinião);
    - LIGAR em perfil catch-all: guardou também (decisão dela de 09/08), mas o
      daemon não liga sozinho depois — e é isso que a frase acrescenta;
    - sem rascunho (janela sem perfil aberto): a frase normal. Não há perfil para
      guardar nem promessa a desmentir; inventar aviso aqui seria ruído.
    """
    if ligado and guardado and not tem_regra:
        return MODO_JOGO_GUARDADO_SEM_REGRA
    return padrao


def registrar_modo_jogo_no_rascunho(janela: Any, ligado: bool) -> bool:
    """Anota o "modo jogo" na janela; devolve se ele foi GUARDADO no rascunho."""
    draft = getattr(janela, "draft", None)
    if draft is None:
        return False
    novo, guardado = rascunho_com_modo_jogo(draft, ligado)
    if guardado and novo is not None:
        janela.draft = novo
    if ligado and guardado and not perfil_do_rascunho_tem_opiniao(draft):
        logger.info(
            "modo_jogo_guardado_em_perfil_sem_regra",
            motivo="catch_all_sem_opiniao",
            perfil=getattr(draft, "source_name", None),
        )
    return guardado


def frase_do_censo(
    prefixos: Sequence[Any], *, bibliotecas: int = 1
) -> tuple[str, bool, bool]:
    """Texto do diálogo + (tem o que tirar, tem o que devolver)."""
    if not bibliotecas:
        return (
            "Não achei nenhuma biblioteca da Steam nesta máquina, então não "
            "tenho onde olhar. Isto não quer dizer que os seus jogos estejam "
            "limpos — quer dizer que eu não consegui abrir a lista.",
            False,
            False,
        )
    if not prefixos:
        return (
            "Olhei os jogos instalados e nenhum deles tem sobreposição extra "
            "pendurada por dentro. Não há o que tirar.",
            False,
            False,
        )
    linhas: list[str] = []
    tem_sobra = False
    tem_devolucao = False
    for prefixo in prefixos:
        linhas.append(f"{prefixo.rotulo}")
        for camada in prefixo.camadas:
            if camada.e_o_driver:
                continue
            if camada.preservada_por is not None:
                linhas.append(
                    f"    {camada.nome_curto} — fica: {camada.preservada_por}"
                )
            elif not camada.ligada:
                tem_devolucao = True
                linhas.append(f"    {camada.nome_curto} — já desligada")
            elif not camada.presente:
                tem_sobra = True
                linhas.append(
                    f"    {camada.nome_curto} — pendurada, mas o arquivo não "
                    "está no disco"
                )
            else:
                tem_sobra = True
                linhas.append(f"    {camada.nome_curto} — ligada")
    corpo = "\n".join(linhas)
    if tem_sobra:
        rodape = (
            "\n\nO que estiver ligado acima só é lido por um jogo que traga o "
            "próprio Vulkan do Windows, o que é raro: tirar quase nunca muda a "
            "imagem, e não cura engasgo. Tirar não apaga nada: "
            "eu só marco a sobreposição como desligada no jogo, guardo cópia "
            "do arquivo antes, e você pode devolver aqui mesmo."
        )
    else:
        rodape = (
            "\n\nNão há nada ligado para tirar. O que está desligado foi eu "
            "que desliguei, e dá para devolver."
        )
    return corpo + rodape, tem_sobra, tem_devolucao


def frase_do_resultado(resultados: Sequence[Any], *, devolver: bool) -> str:
    """A frase do rodapé depois de agir. Nunca some, nunca mente."""
    mexidos = [r for r in resultados if r.desligadas or r.religadas]
    erros = [r for r in resultados if r.erro]
    respeitados = [r for r in resultados if r.respeitadas and not r.mexeu]
    partes: list[str] = []
    if mexidos:
        nomes = sorted({n for r in mexidos for n in (r.religadas if devolver else r.desligadas)})
        verbo = "Devolvi" if devolver else "Tirei"
        jogos = "1 jogo" if len(mexidos) == 1 else f"{len(mexidos)} jogos"
        partes.append(f"{verbo} em {jogos}: " + ", ".join(nomes) + ".")
    if respeitados:
        partes.append(
            f"Deixei como estava em {len(respeitados)} jogo(s) — você já tinha "
            "escolhido manter."
        )
    if erros:
        partes.append(f"Não consegui em {len(erros)} jogo(s): {erros[0].erro}")
    if not partes:
        return "Nada mudou — não havia sobreposição para mexer."
    if not devolver and mexidos:
        partes.append("Feche e abra o jogo para valer.")
    return " ".join(partes)


class EmulationActionsMixin(WidgetAccessMixin):
    """Controla a aba Emulação."""

    def install_emulation_tab(self) -> None:
        self._get("emulation_device_name_label").set_text(DEVICE_NAME)
        self._get("emulation_vidpid_label").set_text(
            f"{XBOX360_VENDOR:04X}:{XBOX360_PRODUCT:04X} (Xbox 360)"
        )
        self._get("emulation_combo_next_label").set_markup(
            "PS + ↑ (D-pad) — próximo perfil"
        )
        self._get("emulation_combo_prev_label").set_markup(
            "PS + ↓ (D-pad) — perfil anterior"
        )
        # que o `state_full` traz o bloco `hotkey`.
        self._sync_hotkey_card(None)
        self._refresh_emulation_view()
        self._refresh_mic_status()
        self._refresh_gamepad_and_gamemode()
        self._refresh_steam_input_status()
        # EMULACAO-NO-JOGO-01/E1: o interruptor do teclado vive na coluna
        # Teclado da aba Navegação (ao lado do do mouse, que é o lugar onde ela
        # o procurou), mas o dono do assunto "emulação" é este mixin. O
        # bootstrap é chamado daqui porque `install_mouse_tab` tem outro dono; a
        # releitura vai pelo `_refresh_emulation_tab` logo abaixo e, desde
        # 22/08/2026, também pelo gancho da aba onde ele DESENHA — o gesto
        # PS + R3 virou um segundo escritor da flag (SEGUNDO-ESCRITOR-01, em
        # `app._REFRESH_POR_ABA`).
        self._refresh_keyboard_switch()

    # --- handlers ---

    def on_emulation_refresh(self, _btn: Gtk.Button) -> None:
        self._refresh_emulation_tab()
        self._toast_emulation("Atualizado")

    def _refresh_emulation_tab(self) -> None:
        """Reconcilia TODOS os status da aba Emulação de uma vez.

        Idempotente e seguro de chamar ao ENTRAR na aba (switch-page chama este
        agregador via getattr — o nome precisa ser exatamente
        ``_refresh_emulation_tab``) e pelo botão "Atualizar". Cada refresh só
        LÊ estado e atualiza labels — uinput/js (sysfs), gamepad+modo-jogo (IPC
        read-only ``daemon.state_full``), mic (drop-ins do WirePlumber) e Steam
        Input (localconfig.vdf) — sem NENHUM efeito colateral no hardware. Cada
        chamada é guardada defensivamente (getattr) porque a Sprint 1 aciona
        este método por nome via switch-page.
        """
        for name in (
            "_refresh_emulation_view",
            "_refresh_gamepad_and_gamemode",
            "_refresh_mic_status",
            "_refresh_steam_input_status",
            "_refresh_keyboard_switch",
        ):
            fn = getattr(self, name, None)
            if callable(fn):
                fn()

    def _sync_hotkey_card(self, state: Any) -> None:
        """Atualiza buffer e passthrough com o valor EFETIVO do daemon.

        Contrato: o `daemon.state_full` traz (ou não) um bloco ``hotkey`` com
        ``buffer_ms`` e ``passthrough_in_emulation``. Quando o bloco não vem —
        daemon offline, versão antiga do daemon ou campo ausente — a tela NÃO
        finge conhecer o estado: mostra o padrão de fábrica com o sufixo
        "(padrão)", que é a verdade disponível. É a mesma disciplina do cartão
        UINPUT (BUG-EMULATION-UINPUT-CARD-STALE-02): sem estado, nada de
        afirmar número.
        """
        bloco = state.get("hotkey") if isinstance(state, dict) else None
        bloco = bloco if isinstance(bloco, dict) else {}

        buffer_lbl = self._get("emulation_combo_buffer_label")
        if buffer_lbl is not None:
            valor = bloco.get("buffer_ms")
            if isinstance(valor, int) and not isinstance(valor, bool):
                buffer_lbl.set_text(str(valor))
            else:
                buffer_lbl.set_text(f"{DEFAULT_BUFFER_MS} (padrão)")

        pass_lbl = self._get("emulation_passthrough_label")
        if pass_lbl is not None:
            ativo = bloco.get("passthrough_in_emulation")
            if isinstance(ativo, bool):
                pass_lbl.set_text("Sim" if ativo else "Não")
            else:
                pass_lbl.set_text("Não (padrão)")

    def _sync_uinput_card(self, active_key: str | None) -> None:
        """Atualiza device/VID:PID do cartão UINPUT conforme a máscara REAL."""
        from hefesto_dualsense4unix.integrations.uinput_gamepad import FLAVORS

        name_label = self._get("emulation_device_name_label")
        vid_label = self._get("emulation_vidpid_label")
        if active_key in FLAVORS:
            spec = FLAVORS[active_key]
            nice = "DualSense" if active_key == "dualsense" else "Xbox 360"
            if name_label is not None:
                name_label.set_text(str(spec["name"]))
            if vid_label is not None:
                vid_label.set_text(
                    f"{spec['vendor']:04X}:{spec['product']:04X} ({nice})"
                )
        else:
            if name_label is not None:
                name_label.set_text("— (gamepad virtual desligado)")
            if vid_label is not None:
                vid_label.set_text("—")

    def on_emulation_test_device(self, _btn: Gtk.Button) -> None:
        try:
            import uinput  # noqa: F401
        except ImportError:
            self._toast_emulation(
                "O gamepad virtual não está disponível — reinstale o Hefesto."
            )
            return
        if not os.access(UINPUT_DEV, os.W_OK):
            self._toast_emulation(
                "O Hefesto não tem acesso ao gamepad virtual — reinstale o Hefesto."
            )
            return
        try:
            from hefesto_dualsense4unix.integrations.uinput_gamepad import UinputGamepad

            gp = UinputGamepad()
            ok = gp.start()
            gp.stop()
        except (OSError, RuntimeError):
            self._toast_emulation(
                "Não consegui criar o gamepad virtual — reinstale o Hefesto."
            )
            return
        if ok:
            self._toast_emulation("Gamepad virtual criado com sucesso")
        else:
            self._toast_emulation(
                "Não consegui criar o gamepad virtual — reinstale o Hefesto."
            )
        self._refresh_emulation_view()

    # ambiente e do canal `daemon.reload`). Enquanto o código existisse, bastava


    def _refresh_emulation_view(self) -> None:
        uinput_label = self._get("emulation_uinput_label")
        try:
            import uinput  # noqa: F401
            module_ok = True
        except ImportError:
            module_ok = False

        dev_exists = os.path.exists(UINPUT_DEV)
        dev_writable = os.access(UINPUT_DEV, os.W_OK) if dev_exists else False

        if module_ok and dev_writable:
            uinput_label.set_markup(
                '<span foreground="#50fa7b">&#9679; Gamepad virtual pronto</span>'
            )
        elif module_ok and dev_exists:
            uinput_label.set_markup(
                '<span foreground="#ffb86c">Gamepad virtual sem acesso — '
                'reinstale o Hefesto</span>'
            )
        elif module_ok:
            uinput_label.set_markup(
                '<span foreground="#ffb86c">Gamepad virtual indisponível — '
                'reinstale o Hefesto</span>'
            )
        else:
            uinput_label.set_markup(
                '<span foreground="#ff5555">Gamepad virtual indisponível — '
                'reinstale o Hefesto</span>'
            )

        js_label = self._get("emulation_js_label")
        with contextlib.suppress(Exception):
            js_label.set_line_wrap(True)
            js_label.set_max_width_chars(LARGURA_MAXIMA_DO_ROTULO_DE_GAMEPADS)

        js_nodes = sorted(glob.glob("/dev/input/js*"))
        if js_nodes:
            fisicos, nossos, outros = classificar_joysticks(
                [_atributos_do_joystick(caminho) for caminho in js_nodes]
            )
            js_label.set_text(
                rotulo_gamepads(fisicos, nossos, outros, len(js_nodes))
            )
        else:
            js_label.set_markup('<i>Nenhum controle detectado pelo sistema</i>')

    # --- microfone do DualSense (FEAT-DUALSENSE-MIC-TOGGLE-01) ---
    # (scripts/fix_wireplumber_default_source.sh). Mic ON = sem os drop-ins de

    @staticmethod
    def _wp_dropin_dir() -> Path:
        """Diretório dos drop-ins do WirePlumber, resolvido a cada chamada.

        T-05 (ONDA0-Z7, 24/08): dono único em `xdg_paths.wireplumber_config_dir`
        — honra `XDG_CONFIG_HOME`, que o WirePlumber em si honra e este ponto
        ignorava calado.
        """
        from hefesto_dualsense4unix.utils.xdg_paths import wireplumber_config_dir

        return wireplumber_config_dir()

    _WP_DISABLE_DROPINS = (
        "52-hefesto-dualsense-disable-source.conf",
        "53-hefesto-dualsense-disable-output.conf",
    )

    _WP_PROMOTER_DROPIN = "51-hefesto-dualsense-no-default-source.conf"

    MIC_SUPRIMIDO = "suprimido"
    MIC_SEM_PROMOTOR = "sem-promotor"
    MIC_LIGADO = "ligado"

    #: placa de áudio do controle no sistema o ramo era o mesmo, e a tela
    MIC_SEM_ALVO = "sem-alvo"

    #: de PLACA ALSA do DualSense em `/proc/asound/cards`, contada pela função
    _PLACAS_ALSA = "/proc/asound/cards"

    def _mic_script(self) -> Path | None:
        """BG-BASES-01 (26/08/2026): eram três bases à mão, hoje é a busca única."""
        return encontrar_arquivo_do_repo(
            "scripts/fix_wireplumber_default_source.sh"
        )

    @staticmethod
    def _placas_de_microfone() -> int:
        """Quantas placas ALSA de DualSense este computador tem AGORA.

        Zero também quando `/proc/asound/cards` não dá para ler — e é honesto
        chamar isso de zero na frase que a tela mostra, porque ela diz que o
        Hefesto **não encontrou** placa nenhuma, não que não exista nenhuma.
        """
        from hefesto_dualsense4unix.integrations.storm_doctor import (
            contar_placas_dualsense,
        )

        try:
            texto = Path(EmulationActionsMixin._PLACAS_ALSA).read_text(
                encoding="utf-8", errors="ignore"
            )
        except OSError:
            return 0
        return contar_placas_dualsense(texto)

    def _mic_state(self) -> str:
        """O que os drop-ins do WirePlumber dizem sobre o mic, em quatro estados."""
        dropins = self._wp_dropin_dir()
        if any((dropins / name).exists() for name in self._WP_DISABLE_DROPINS):
            return self.MIC_SUPRIMIDO
        if not (dropins / self._WP_PROMOTER_DROPIN).exists():
            return self.MIC_SEM_PROMOTOR
        if self._placas_de_microfone() == 0:
            return self.MIC_SEM_ALVO
        return self.MIC_LIGADO

    def _mic_is_on(self) -> bool:
        """Mic ligado DE VERDADE: sem supressão (52/53) **e** com o promotor (51)."""
        return self._mic_state() == self.MIC_LIGADO

    # BUG-MIC-ON-SEM-QUIRK-REABRE-STORM-01: o quirk de áudio USB
    _USB_QUIRK_MARKER = "054c:0ce6:gn"
    _USB_QUIRK_PATHS: ClassVar[tuple[str, ...]] = (
        "/proc/cmdline",
        "/sys/module/usbcore/parameters/quirks",
    )

    @staticmethod
    def _usb_quirk_active() -> bool:
        """True se o quirk de áudio USB protege a SESSÃO ATUAL."""
        marker = EmulationActionsMixin._USB_QUIRK_MARKER
        for path in EmulationActionsMixin._USB_QUIRK_PATHS:
            with contextlib.suppress(OSError):
                if marker in Path(path).read_text(encoding="utf-8", errors="ignore"):
                    return True
        return False

    _MIC_ROTULOS: ClassVar[dict[str, tuple[str, str, str]]] = {
        MIC_LIGADO: (
            "#50fa7b",
            "Ligado",
            "O microfone do controle está livre e com prioridade acima do eco "
            "da saída.",
        ),
        MIC_SEM_PROMOTOR: (
            "#ffb86c",
            "Ligado sem prioridade",
            "O microfone está livre, mas sem a prioridade que o mantém acima "
            "do eco da saída — do jeito que está, o que os aplicativos gravam "
            "pode ser o som do sistema em vez da sua voz. Clique em “Ligar” "
            "para armar de novo.",
        ),
        MIC_SUPRIMIDO: (
            "#ffb86c",
            "Desligado (suprimido)",
            "O microfone do controle está desligado por escolha — clique em "
            "“Ligar” para liberá-lo.",
        ),
        MIC_SEM_ALVO: (
            "#ffb86c",
            "Sem microfone à vista",
            "Os ajustes estão no lugar, mas o Hefesto não encontrou a placa de "
            "áudio de nenhum DualSense neste computador — então não há o que "
            "estes dois botões liguem agora. É o normal quando o controle está "
            "no rádio: por Bluetooth ele não cria placa de áudio. Ligue o "
            "controle no cabo e clique em “Atualizar”.",
        ),
    }

    ESCOPO_DO_MICROFONE_DESTA_ABA = (
        "Isto vale para o computador inteiro, não para este jogo: não entra no "
        "perfil e não mexe na ponte de microfone por Bluetooth (aba "
        "Configurações)."
    )

    def _refresh_mic_status(self) -> None:
        label = self._get("emulation_mic_status_label")
        if label is None:
            return
        cor, texto, dica = self._MIC_ROTULOS[self._mic_state()]
        label.set_markup(f'<span foreground="{cor}">{texto}</span>')
        with contextlib.suppress(Exception):
            label.set_tooltip_text(f"{dica} {self.ESCOPO_DO_MICROFONE_DESTA_ABA}")

    def _run_mic(self, flag: str, done_msg: str) -> None:
        script = self._mic_script()
        if script is None:
            self._toast_emulation("Script do WirePlumber não encontrado")
            return
        self._toast_emulation("Aplicando no microfone...")

        def _worker() -> None:
            with contextlib.suppress(OSError, subprocess.SubprocessError):
                subprocess.run(["bash", str(script), flag], check=False, timeout=30)
            GLib.idle_add(self._on_mic_done, done_msg)

        _get_executor().submit(_worker)

    def _on_mic_done(self, msg: str) -> bool:
        self._refresh_mic_status()
        self._toast_emulation(msg)
        return False

    def on_emulation_mic_on(self, _btn: Gtk.Button) -> None:
        if self._usb_quirk_active():
            done = "Mic do DualSense ligado"
        else:
            from hefesto_dualsense4unix.integrations.storm_doctor import (
                rotulo_do_botao,
            )

            botao = rotulo_do_botao(
                "btn_storm_fix_safe", "Refazer os consertos automáticos")
            done = (
                "Mic ligado — atenção: sem o ajuste de áudio o controle pode "
                "travar no meio do jogo. Abra a aba Sistema e clique em "
                f"“{botao}” (vale no próximo boot)."
            )
        self._run_mic("--enable-mic", done)

    def on_emulation_mic_off(self, _btn: Gtk.Button) -> None:
        self._run_mic("--disable-source", "Mic do DualSense desligado")


    _GAMEPAD_BUTTON_IDS: ClassVar[dict[str, str]] = {
        "off": "emulation_gamepad_off_button",
        "dualsense": "emulation_gamepad_dualsense_button",
        "xbox": "emulation_gamepad_xbox_button",
    }

    def _highlight_gamepad(self, active_key: str | None) -> None:
        """Destaca o botão do modo de gamepad atual (off/dualsense/xbox)."""
        for key, wid in self._GAMEPAD_BUTTON_IDS.items():
            btn = self._get(wid)
            if btn is None:
                continue
            ctx = btn.get_style_context()
            if key == active_key:
                ctx.add_class("hefesto-active-mode")
            else:
                ctx.remove_class("hefesto-active-mode")

    def _sync_gamemode_button(self, mode: str | None) -> None:
        """HARM-03/EMU-07: "Modo jogo" só faz sentido "jogando pelo Hefesto"."""
        pause_btn = self._get("emulation_pause_button")
        hint = self._get("emulation_gamemode_hint_label")
        blocked = mode is None or mode in {MODE_DESKTOP, MODE_NATIVE}
        if pause_btn is not None:
            pause_btn.set_sensitive(not blocked)
        if hint is None:
            return
        if mode == MODE_DESKTOP:
            hint.set_text(
                "Em \"Controlar o PC\" o controle só faz mouse/teclado — "
                "suspendê-los deixaria o controle sem função nenhuma."
            )
        elif mode == MODE_NATIVE:
            hint.set_text(
                "Em \"Conexão Nativa (Sony)\" o jogo fala direto com o controle — "
                "não há mouse/teclado para suspender."
            )
        else:
            hint.set_text("")

    def _refresh_gamepad_and_gamemode(self) -> None:
        """Lê daemon.state_full e atualiza os labels de gamepad + modo-jogo."""
        def _on_state(state: Any) -> bool:
            mode = mode_of_state(state if isinstance(state, dict) else None)
            gp = state.get("gamepad_emulation") if isinstance(state, dict) else None
            gp_label = self._get("emulation_gamepad_status_label")
            if mode == MODE_NATIVE:
                active_key = None
                if gp_label is not None:
                    gp_label.set_markup(
                        '<span foreground="#ffb86c">Conexão Nativa (Sony) — o jogo '
                        'fala direto com o controle</span>'
                    )
            elif isinstance(gp, dict) and gp.get("enabled"):
                flavor = gp.get("flavor") or "?"
                active_key = "xbox" if flavor == "xbox" else "dualsense"
                nice = "DualSense (PS)" if active_key == "dualsense" else "Xbox 360"
                if gp_label is not None:
                    gp_label.set_markup(f'<span foreground="#50fa7b">Ligado — {nice}</span>')
            else:
                active_key = "off"
                if gp_label is not None:
                    gp_label.set_markup('<span foreground="#8b8fa8">Desligado</span>')
            self._highlight_gamepad(active_key)
            self._sync_gamemode_button(mode)
            # a máscara real em DualSense — informação contraditória na mesma
            self._sync_uinput_card(active_key)
            self._sync_hotkey_card(state)
            gm_label = self._get("emulation_gamemode_status_label")
            if gm_label is not None and isinstance(state, dict):
                if state.get("emulation_suppressed"):
                    gm_label.set_markup(
                        '<span foreground="#ffb86c">LIGADO — mouse/teclado suspensos</span>'
                    )
                elif state.get("paused"):
                    gm_label.set_markup(
                        '<span foreground="#ffb86c">O Hefesto está em pausa</span>'
                    )
                else:
                    gm_label.set_markup(
                        '<span foreground="#50fa7b">Desligado — emulação normal</span>'
                    )
            return False

        def _on_err(_exc: Exception) -> bool:
            lbl = self._get("emulation_gamepad_status_label")
            if lbl is not None:
                lbl.set_markup('<span foreground="#8b8fa8">O Hefesto está desligado</span>')
            self._highlight_gamepad(None)
            sync_card = getattr(self, "_sync_uinput_card", None)
            if sync_card is not None:
                sync_card(None)
            sync_hotkey = getattr(self, "_sync_hotkey_card", None)
            if sync_hotkey is not None:
                sync_hotkey(None)
            self._sync_gamemode_button(None)
            return False

        # HARM-15: a folga do state_full vale AQUI também — sem ela esta aba
        # junto do `mode_of_state`: é a mesma leitura.
        call_async(
            "daemon.state_full", {}, on_success=_on_state, on_failure=_on_err,
            timeout_s=STATE_IPC_TIMEOUT_S,
        )

    def _apply_mode(self, mode_id: str, flavor: str | None, msg: str) -> None:
        """Muda o modo pelo MESMO caminho da Início (HARM-01)."""
        def _on_ok(_res: Any) -> bool:
            registrar_modo_no_rascunho(self, mode_id, flavor)
            self._refresh_gamepad_and_gamemode()
            self._toast_emulation(msg)
            return False

        def _on_err(_exc: Exception) -> bool:
            self._toast_emulation(
                "Não consegui mudar o controle — o Hefesto pode estar "
                "desligado. Veja a aba Sistema."
            )
            self._refresh_gamepad_and_gamemode()
            return False

        apply_mode(mode_id, flavor=flavor, on_done=_on_ok, on_fail=_on_err)

    def on_emulation_gamepad_off(self, _btn: Gtk.Button) -> None:
        self._apply_mode(
            MODE_DESKTOP, None, "Gamepad virtual desligado — o controle controla o PC"
        )

    def on_emulation_gamepad_dualsense(self, _btn: Gtk.Button) -> None:
        self._apply_mode(
            MODE_GAMEPAD,
            "dualsense",
            "Gamepad DualSense ligado — o jogo mostra os botões da Sony",
        )

    def on_emulation_gamepad_xbox(self, _btn: Gtk.Button) -> None:
        self._apply_mode(
            MODE_GAMEPAD,
            "xbox",
            "Gamepad Xbox 360 ligado — o jogo mostra os botões do Xbox",
        )

    def _set_suppress(self, suppressed: bool, msg: str) -> None:
        def _on_ok(_res: Any) -> bool:
            guardado = registrar_modo_jogo_no_rascunho(self, suppressed)
            self._refresh_gamepad_and_gamemode()
            self._toast_emulation(
                frase_do_modo_jogo(
                    msg,
                    ligado=suppressed,
                    guardado=guardado,
                    tem_regra=perfil_do_rascunho_tem_opiniao(
                        getattr(self, "draft", None)
                    ),
                )
            )
            return False

        def _on_err(_exc: Exception) -> bool:
            self._toast_emulation(
                "Não consegui aplicar — o Hefesto pode estar desligado. "
                "Veja a aba Sistema."
            )
            return False

        call_async(
            "daemon.emulation.suppress",
            {"suppressed": suppressed},
            on_success=_on_ok,
            on_failure=_on_err,
        )

    def on_emulation_pause(self, _btn: Gtk.Button) -> None:
        self._set_suppress(True, "Modo jogo ligado — mouse e teclado suspensos")

    def on_emulation_resume(self, _btn: Gtk.Button) -> None:
        self._set_suppress(False, "Modo jogo desligado: mouse/teclado retomados")

    # (`keyboard.emulation.set` + bloco `keyboard_emulation`) já está no daemon;

    _keyboard_guard_refresh: bool = False

    _keyboard_confirmado: bool = True

    def _refresh_keyboard_switch(self) -> None:
        """Lê o bloco ``keyboard_emulation`` do ``state_full`` e pinta a chave.

        O estado vem do DAEMON, não do rascunho: o teclado não tem seção no
        perfil e quem persiste a escolha dela é o daemon
        (``keyboard_emulation.flag``, gravado a cada ``keyboard.emulation.set``).
        A janela não escreve arquivo nenhum aqui.
        """
        def _on_state(state: Any) -> bool:
            bloco = state.get("keyboard_emulation") if isinstance(state, dict) else None
            self._aplicar_keyboard_switch(bloco)
            return False

        def _on_err(_exc: Exception) -> bool:
            self._aplicar_keyboard_switch(None)
            return False

        # HARM-15: a mesma folga do resto da casa para LER o `state_full` — sem
        call_async(
            "daemon.state_full", {}, on_success=_on_state, on_failure=_on_err,
            timeout_s=STATE_IPC_TIMEOUT_S,
        )

    def _aplicar_keyboard_switch(self, bloco: object) -> None:
        """Põe o interruptor e a frase na tela. Tolerante a glade sem os widgets."""
        ligado, dica = descrever_teclado_emulado(bloco)
        switch = self._get("keyboard_emulation_toggle")
        if switch is not None:
            switch.set_sensitive(ligado is not None)
            if ligado is not None:
                self._keyboard_confirmado = ligado
                anterior = self._keyboard_guard_refresh
                self._keyboard_guard_refresh = True
                try:
                    switch.set_active(ligado)
                finally:
                    self._keyboard_guard_refresh = anterior
        hint = self._get("keyboard_emulation_hint_label")
        if hint is None:
            return
        hint.set_text(dica)
        hint.set_visible(bool(dica))

    def on_keyboard_toggle_set(self, switch: Gtk.Switch, _state: Any) -> bool:
        """Liga/desliga o teclado emulado pelo IPC ``keyboard.emulation.set``.

        O daemon devolve o bloco já atualizado no próprio resultado, então não
        há segunda chamada de ``state_full`` para saber se pegou.
        """
        if self._keyboard_guard_refresh:
            return False
        ligado = bool(switch.get_active())

        def _on_ok(result: Any) -> bool:
            if not isinstance(result, dict) or result.get("status") != "ok":
                return _on_err(RuntimeError("daemon respondeu status=failed"))
            self._aplicar_keyboard_switch(result.get("keyboard_emulation"))
            if ligado:
                self._toast_keyboard("Teclado emulado ligado")
            else:
                self._toast_keyboard(
                    "Teclado emulado desligado — saem também o teclado na tela "
                    "(L3/R3) e as três regiões do touchpad"
                )
            return False

        def _on_err(_exc: Exception) -> bool:
            self._toast_keyboard(
                "Não consegui mudar o teclado emulado — o Hefesto pode estar "
                "desligado. Veja a aba Sistema."
            )
            self._reverter_keyboard_switch(self._keyboard_confirmado)
            return False

        call_async(
            "keyboard.emulation.set",
            {"enabled": ligado},
            on_success=_on_ok,
            on_failure=_on_err,
        )
        return False

    def _reverter_keyboard_switch(self, ativo: bool) -> None:
        """Devolve a chave à posição confirmada SEM reentrar no handler."""
        switch = self._get("keyboard_emulation_toggle")
        if switch is None:
            return
        anterior = self._keyboard_guard_refresh
        self._keyboard_guard_refresh = True
        try:
            switch.set_active(ativo)
        finally:
            self._keyboard_guard_refresh = anterior

    def _toast_keyboard(self, msg: str) -> None:
        self._status_toast("keyboard_emulation", msg)


    def _steam_input_script(self) -> Path | None:
        """BG-BASES-01 (26/08/2026): a lista curta é que fazia o botão calar."""
        return encontrar_arquivo_do_repo("scripts/disable_steam_input.sh")

    @staticmethod
    def _steam_input_is_on() -> bool | None:
        """True/False se Steam Input CONFLITANTE está ligado; None se indeterminado.

        STEAM-INPUT-ALLOWLIST-01: usa o mesmo walker de blocos do storm_doctor —
        opt-in per-app deliberado (os jogos que ela marcou, e nos quais o
        controle físico fica escondido; ex.: MMJ na allowlist) NÃO conta como
        conflito; as chaves globais (PSSupport/SwitchSupport) e per-app fora
        da allowlist contam.

        T-07 (25/08/2026): esta docstring dizia *"jogos cujo DualSense é
        entregue pela Steam"*, o enquadramento que ela derrubou em 09/08
        (ESCONDER-EM-VEZ-DE-SAIR-01). Docstring não é tela, mas é o que a
        próxima pessoa lê antes de escrever a próxima frase de tela — deixar
        a versão morta aqui é como o defeito volta.

        AMBIENTE-PRESUMIDO-01 (23/08/2026): a busca era um `glob` cravado em
        ``~/.steam/steam``, e por isso o cartão dizia "Steam não encontrado"
        para quem instalou a Steam pela Flatpak, pela Snap ou pelo instalador
        que cai em ``~/.local/share/Steam`` — na MESMA máquina em que o
        `doctor` do CLI acusava o Steam Input ligado, porque ele já usava o
        `find_localconfig_vdfs`. Régua única agora, e é a que já era testada.
        """
        from hefesto_dualsense4unix.integrations.storm_doctor import (
            find_localconfig_vdfs,
            steam_input_allowlist,
            steam_input_on_fora_da_allowlist,
        )

        vdfs = find_localconfig_vdfs(Path.home())
        if not vdfs:
            return None
        allow = steam_input_allowlist()
        for vdf in vdfs:
            with contextlib.suppress(OSError):
                texto = vdf.read_text(encoding="utf-8", errors="ignore")
                if steam_input_on_fora_da_allowlist(texto, allow):
                    return True
        return False

    @staticmethod
    def _steam_input_appids_ligados() -> list[str]:
        """AppIDs com Steam Input per-app ligado FORA da allowlist, sem repetir."""
        from hefesto_dualsense4unix.integrations.storm_doctor import (
            find_localconfig_vdfs,
            steam_input_allowlist,
            steam_input_fora_da_allowlist,
        )

        vdfs = find_localconfig_vdfs(Path.home())
        allow = steam_input_allowlist()
        achados: list[str] = []
        for vdf in vdfs:
            with contextlib.suppress(OSError):
                texto = vdf.read_text(encoding="utf-8", errors="ignore")
                for appid in steam_input_fora_da_allowlist(texto, allow)[0]:
                    if appid not in achados:
                        achados.append(appid)
        return achados

    @staticmethod
    def _steam_input_excecoes() -> list[int]:
        """Os appids da lista de exceções do Steam Input — R-06 item 3.

        "Configurada" e "efetiva" são coisas diferentes e a confusão entre elas
        é o que deixou a allowlist inerte por meses: o appid estava no arquivo,
        o guard de VDF o respeitava, e mesmo assim o daemon seguia escondendo o
        hidraw do controle físico — o jogo não via DualSense nenhum. Aqui:

        - **configurada** = appids em `steam_input_apps.txt`, o que esta
          função devolve;
        - **efetiva** = TODO hidraw de DualSense físico legível por ESTE uid
          agora. Quem mede é `broker.hidraw_broker.physical_nodes_exposure`, e
          o `doctor.sh` continua perguntando a ele.

        NOTA DATADA, 13/09/2026 (RESTOS-DA-ONDA-DOIS-01). Esta função chamava-se
        `_steam_input_excecao_status` e devolvia as duas, varrendo os hidraw a
        cada leitura. A efetiva saiu da tela na FRASES-E-DICAS-03, e nada vivo a
        lia: o refresh GTK desta aba perdeu a janela em 06/09
        (`D-0609-GTK-LEVA-INTEIRA`), e nenhuma classe do `src/` herda este mixin;
        o cartão da Steam na aba 07 só a passava a `markup_status_steam_input`,
        que a ignorava. A varredura saiu daqui.
        """
        from hefesto_dualsense4unix.daemon.launch_env import steam_input_appids

        return sorted(steam_input_appids())

    def _refresh_steam_input_status(self) -> None:
        label = self._get("emulation_steam_input_status_label")
        if label is None:
            return

        def _check() -> tuple[bool | None, list[str], list[int]]:
            from hefesto_dualsense4unix.integrations.steam_launch_options import (
                rotulo_do_jogo,
            )

            on = self._steam_input_is_on()
            jogos = (
                [rotulo_do_jogo(a) for a in self._steam_input_appids_ligados()]
                if on
                else []
            )
            return (on, jogos, self._steam_input_excecoes())

        def _on_ok(dados: tuple[bool | None, list[str], list[int]]) -> bool:
            label.set_markup(markup_status_steam_input(*dados))
            return False

        run_in_thread(_check, on_success=_on_ok)

    def on_emulation_steam_input_check(self, _btn: Gtk.Button) -> None:
        self._refresh_steam_input_status()
        self._toast_emulation("Steam Input verificado")

    def on_emulation_steam_input_disable(self, _btn: Gtk.Button) -> None:
        """Desliga o Steam Input — com consentimento e com veredito conferido."""
        script = self._steam_input_script()
        if script is None:
            self._toast_emulation(format_steam_input_result(status="sem_script"))
            return
        self._toast_emulation("Verificando a Steam…")

        def _sondar() -> None:
            from hefesto_dualsense4unix.integrations import (
                steam_launch_options as slo,
            )

            try:
                jogo = slo.steam_game_running()
                steam = False if jogo else slo.steam_running()
            except Exception as exc:  # pragma: no cover - sondagem best-effort
                logger.warning("steam_input_sonda_falhou", erro=str(exc))
                jogo, steam = False, False
            GLib.idle_add(self._steam_input_decidir, script, jogo, steam)

        _get_executor().submit(_sondar)

    def _steam_input_decidir(self, script: Path, jogo: bool, steam: bool) -> bool:
        """Decide na thread GTK: recusar, perguntar ou aplicar direto."""
        if jogo:
            self._toast_emulation(format_steam_input_result(status="jogo_aberto"))
            return False
        if not steam:
            self._toast_emulation("Desligando Steam Input…")
            self._steam_input_apply_async(script, fechar_a_steam=False)
            return False

        from hefesto_dualsense4unix.app.actions.daemon_actions import (
            build_steam_close_consent_dialog,
        )

        def _resposta(dialog: Any, response: int) -> None:
            with contextlib.suppress(Exception):
                dialog.destroy()
            if response != Gtk.ResponseType.OK:
                self._toast_emulation(
                    format_steam_input_result(status="cancelado")
                )
                return
            self._toast_emulation("Fechando a Steam para desligar o Steam Input…")
            self._steam_input_apply_async(script, fechar_a_steam=True)

        build_steam_close_consent_dialog(
            getattr(self, "window", None),
            titulo="Posso fechar a Steam por uns 20 segundos?",
            corpo=(
                "Para desligar o Steam Input eu preciso FECHAR a Steam e "
                "abrir de novo — com ela viva, ela regrava o arquivo ao sair "
                "e a mudança seria perdida.\n\n"
                "Antes de continuar: pause os downloads. Fica um backup ao "
                "lado de cada arquivo da Steam.\n\n"
                "Se algum jogo estiver aberto eu não faço nada."
            ),
            rotulo_ok="Fechar e desligar",
            on_response=_resposta,
        ).show_all()
        return False

    def _steam_input_apply_async(self, script: Path, *, fechar_a_steam: bool) -> None:
        """Roda o script em worker e devolve o veredito CONFERIDO à GUI.

        Com `fechar_a_steam=True` o fechamento é nosso (`with_steam_closed`,
        o mesmo fluxo provado do `install.sh --migrate --stop-steam`) e o
        script roda em `--apply-quiet`: assim quem fecha/reabre a Steam é UM
        só dono, e o script nunca precisa decidir sozinho matar processo.
        """

        def _rodar() -> tuple[int, str]:
            proc = subprocess.run(
                ["bash", str(script), "--apply-quiet"],
                check=False,
                timeout=180,
                capture_output=True,
                text=True,
            )
            return proc.returncode, (proc.stdout or "") + (proc.stderr or "")

        def _worker() -> None:
            status = "executado"
            rc, saida = 0, ""
            try:
                if fechar_a_steam:
                    from hefesto_dualsense4unix.integrations import (
                        steam_launch_options as slo,
                    )

                    janela, resultado = slo.with_steam_closed(_rodar)
                    if janela == slo.STEAM_JANELA_JOGO_ABERTO:
                        status = "jogo_aberto"
                    elif janela == slo.STEAM_JANELA_NAO_FECHOU:
                        status = "nao_fechou"
                    else:
                        rc, saida = resultado
                else:
                    rc, saida = _rodar()
                tag = steam_input_result_tag(saida)
                ainda_ligado = (
                    self._steam_input_is_on() if status == "executado" else None
                )
            except Exception as exc:
                logger.warning("steam_input_script_falhou", erro=str(exc))
                GLib.idle_add(
                    self._on_steam_input_done,
                    f"Não consegui rodar o script: {exc}",
                )
                return
            GLib.idle_add(
                self._on_steam_input_done,
                format_steam_input_result(
                    status=status, rc=rc, tag=tag, ainda_ligado=ainda_ligado
                ),
            )

        _get_executor().submit(_worker)

    def _on_steam_input_done(self, msg: str) -> bool:
        self._refresh_steam_input_status()
        self._toast_emulation(msg)
        return False

    def _toast_emulation(self, msg: str) -> None:
        self._status_toast("emulation", msg)


    def _toast_camadas(self, msg: str) -> None:
        """Rodapé das camadas. Contexto próprio para não brigar com os outros."""
        self._status_toast("camadas_vulkan", msg)

    def on_camadas_engasgo(self, _btn: object) -> None:
        """Botão "Tirar a sobreposição Vulkan" (bloco Avançado, aba Sistema)."""
        self._toast_camadas("Olhando os jogos instalados…")

        def _worker() -> None:
            try:
                from hefesto_dualsense4unix.integrations import camadas_vulkan as cv

                prefixos = cv.censo()
                bibliotecas = len(cv.pastas_compatdata())
            except Exception as exc:  # pragma: no cover - defesa de worker
                logger.warning("censo_de_camadas_falhou", erro=str(exc))
                GLib.idle_add(
                    self._toast_camadas,
                    "Não consegui olhar os jogos — veja os 'Detalhes técnicos'.",
                )
                return
            GLib.idle_add(self._abrir_dialogo_camadas, prefixos, bibliotecas)

        _get_executor().submit(_worker)

    def _abrir_dialogo_camadas(
        self, prefixos: Sequence[Any], bibliotecas: int = 1
    ) -> bool:
        """Monta e mostra o diálogo. Sempre no thread do GTK (via idle_add)."""
        self._toast_camadas("")
        dialog = self._build_camadas_dialog(prefixos, bibliotecas=bibliotecas)
        dialog.show_all()
        return False

    def _build_camadas_dialog(
        self, prefixos: Sequence[Any], *, bibliotecas: int = 1
    ) -> Gtk.MessageDialog:
        """Monta o diálogo (sem exibir) — separado para o teste alcançar."""
        corpo, tem_sobra, tem_devolucao = frase_do_censo(
            prefixos, bibliotecas=bibliotecas
        )
        window: Gtk.Window | None = getattr(self, "window", None)
        dialog = Gtk.MessageDialog(
            transient_for=window,
            flags=0,
            message_type=Gtk.MessageType.QUESTION,
            buttons=Gtk.ButtonsType.NONE,
            text="O que está pendurado por dentro dos seus jogos",
        )
        with contextlib.suppress(Exception):
            dialog.get_style_context().add_class("hefesto-dualsense4unix-window")
        dialog.format_secondary_text(corpo)
        dialog.add_button("Fechar", Gtk.ResponseType.CANCEL)
        if tem_devolucao:
            dialog.add_button("Devolver", Gtk.ResponseType.APPLY)
        if tem_sobra:
            dialog.add_button("Tirar", Gtk.ResponseType.OK)
        dialog.set_default_response(Gtk.ResponseType.CANCEL)
        dialog.connect("response", self._on_camadas_response)
        return dialog

    def _on_camadas_response(self, dialog: Any, response: int) -> None:
        """Só OK (tirar) e APPLY (devolver) agem; o resto fecha e pronto."""
        with contextlib.suppress(Exception):
            dialog.destroy()
        if response == int(Gtk.ResponseType.OK):
            self._camadas_worker(devolver=False)
        elif response == int(Gtk.ResponseType.APPLY):
            self._camadas_worker(devolver=True)

    def _camadas_worker(self, *, devolver: bool) -> None:
        """Aplica em todos os prefixos, em worker, com o portão do jogo aberto."""
        self._toast_camadas("Devolvendo…" if devolver else "Tirando…")

        def _worker() -> None:
            try:
                from hefesto_dualsense4unix.integrations import camadas_vulkan as cv
                from hefesto_dualsense4unix.integrations import (
                    lista_de_exclusao,
                )
                from hefesto_dualsense4unix.integrations import (
                    steam_launch_options as slo,
                )

                if slo.steam_game_running():
                    GLib.idle_add(
                        self._toast_camadas,
                        "Tem jogo aberto — feche-o e clique de novo. Com o "
                        "jogo vivo o Windows do Proton regrava esse ajuste ao "
                        "sair, e a mudança seria perdida.",
                    )
                    return
                resultados = cv.curar_todos(
                    religar=devolver, forcar=True,
                    excluir=lista_de_exclusao.ids_dos_prefixos(),
                )
            except Exception as exc:
                logger.warning("cura_de_camadas_falhou", erro=str(exc))
                GLib.idle_add(
                    self._toast_camadas,
                    "Não consegui mexer nas sobreposições — veja os 'Detalhes "
                    "técnicos'.",
                )
                return
            GLib.idle_add(
                self._toast_camadas, frase_do_resultado(resultados, devolver=devolver)
            )

        _get_executor().submit(_worker)
