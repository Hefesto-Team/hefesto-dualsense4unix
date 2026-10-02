"""Aba Emulação: status do gamepad virtual Xbox360 + config."""
# ruff: noqa: E402
from __future__ import annotations

import contextlib
import re
from collections.abc import Sequence
from pathlib import Path
from typing import Any, ClassVar

import gi

gi.require_version("Gtk", "3.0")

from hefesto_dualsense4unix.app.actions.base import WidgetAccessMixin
from hefesto_dualsense4unix.app.actions.mode_transition import (
    MODE_DESKTOP,
    MODE_NATIVE,
)
from hefesto_dualsense4unix.integrations.uinput_gamepad import (
    DUALSENSE_EDGE_NAME,
    XBOX360_NAME,
)
from hefesto_dualsense4unix.utils.logging_config import get_logger

logger = get_logger(__name__)


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


# DualSense "funcionam completos: vibração, giroscópio e lightbar". O mapa de


def _e_vpad_do_hefesto(no: dict[str, str]) -> bool:
    """True quando o aparelho é um gamepad virtual NOSSO — nos dois backends."""
    uniq = no.get("uniq", "").strip().lower()
    nome = no.get("name", "").strip()
    if uniq.startswith(_VPAD_UNIQ_PREFIX) or _VPAD_MARCA_NO_NOME in nome:
        return True
    return (
        _UINPUT_SUBTREE in no.get("sys", "") and nome in _VPAD_NOMES_EM_UINPUT
    )


_RESULTADO_RE = re.compile(r"^\[steam-input\] resultado=(\S+)\s*$", re.MULTILINE)


def steam_input_result_tag(saida: str) -> str | None:
    """Tag `resultado=` da saída do script (a ÚLTIMA, se houver mais de uma)."""
    achados = _RESULTADO_RE.findall(saida or "")
    return achados[-1] if achados else None


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


    # --- handlers ---


    # ambiente e do canal `daemon.reload`). Enquanto o código existisse, bastava


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


    _GAMEPAD_BUTTON_IDS: ClassVar[dict[str, str]] = {
        "off": "emulation_gamepad_off_button",
        "dualsense": "emulation_gamepad_dualsense_button",
        "xbox": "emulation_gamepad_xbox_button",
    }


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


    # (`keyboard.emulation.set` + bloco `keyboard_emulation`) já está no daemon;

    _keyboard_guard_refresh: bool = False

    _keyboard_confirmado: bool = True


    def _toast_keyboard(self, msg: str) -> None:
        self._status_toast("keyboard_emulation", msg)


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


    def _toast_emulation(self, msg: str) -> None:
        self._status_toast("emulation", msg)


    def _toast_camadas(self, msg: str) -> None:
        """Rodapé das camadas. Contexto próprio para não brigar com os outros."""
        self._status_toast("camadas_vulkan", msg)


