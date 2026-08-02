"""Aba Emulação: status do gamepad virtual Xbox360 + config."""
# ruff: noqa: E402
from __future__ import annotations

import contextlib
import glob
import os
import re
import subprocess
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
from hefesto_dualsense4unix.app.constants import ROOT_DIR
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

logger = get_logger(__name__)

UINPUT_DEV = "/dev/uinput"

# --- CONTAGEM-E-COOP-01 (E2): o campo "Gamepads:" para de contar NÓ ---------
# O rótulo dizia "N controles detectados pelo sistema" com `N = len(glob(
# "/dev/input/js*"))`. Medido nesta máquina em 31/07/2026, com UM DualSense no
# cabo, o vpad do Hefesto de pé e a Steam aberta, o campo dizia SEIS:
#
#   js0  Sony … DualSense Wireless Controller           uniq=<MAC dela>
#   js1  Sony … DualSense … Motion Sensors              uniq=<O MESMO MAC>
#   js2  Hefesto Virtual DualSense P1                   uniq=02:fe:00:00:00:01
#   js3  Hefesto Virtual DualSense P1 Motion Sensors    uniq=<O MESMO>
#   js4  Microsoft X-Box 360 pad 0    /devices/virtual/input/input329/js4
#   js5  Microsoft X-Box 360 pad 1    /devices/virtual/input/input61/js5
#
# Duas razões independentes, e as duas continuam valendo (a medição de 25/07
# que originou este código, no commit `0c08e77` da linhagem descartada, viu as
# mesmas duas com quatro controles e nove nós):
#
# 1. todo controle da classe DualSense abre DOIS nós (o gamepad e os sensores
#    de movimento) — contar nós é contar quase o dobro. O que colapsa os dois
#    é a IDENTIDADE do aparelho, o `uniq`;
# 2. o caminho no sysfs NÃO separa "nosso" de "dela": desde o BLUEZ-UHID-01 o
#    BlueZ cria o HID dos controles BLUETOOTH FÍSICOS em
#    `/devices/virtual/misc/uhid/`, exatamente onde mora o nosso vpad uhid.
#    Quem separa é o MAC forjado `02:fe:…`, o mesmo sinal que
#    `core.evdev_reader._is_virtual_evdev` já usa para não se auto-adotar.
#
# Duas correções ao código de origem, medidas aqui e não lá:
#
# (a) o `0c08e77` reconhecia o vpad por DUAS assinaturas (`uniq` `02:fe:` e
#     nome `Hefesto Virtual`), as duas do backend **uhid**. O fallback
#     degradado do VPAD-05 é **uinput**, não publica `uniq` e usa as máscaras
#     de `integrations.uinput_gamepad`: a xbox contém "Hefesto" mas não começa
#     com "Hefesto Virtual", e a dualsense (`DUALSENSE_EDGE_NAME`) não contém
#     "Hefesto" em lugar nenhum. Sem a quarta regra o nosso próprio vpad seria
#     acusado de "gamepad virtual de outro programa" — troca do silêncio de
#     hoje por uma mentira nova;
# (b) o agrupamento sem `uniq` subia TRÊS níveis do nó (`<hid>/input/inputNN/
#     jsN` → `<hid>`), o que está certo para device HID e erra para uinput:
#     `/devices/virtual/input/inputNN/jsN` não tem a camada `input/` do HID, e
#     três níveis chegam em `/devices/virtual`, colapsando TODOS os gamepads
#     de uinput num só. Na mesa medida acima, os dois pads da Steam virariam
#     um. Em uinput cada `inputNN` é um aparelho (um device de uinput publica
#     exatamente um nó evdev), então a chave para eles é o próprio `inputNN`.

#: Prefixo do MAC que o vpad **uhid** forja por jogador (`uhid_gamepad`).
#: Contrato de fio replicado aqui de propósito: importar o módulo do vpad uhid
#: só por causa de uma string acoplaria a aba a ele. O teste
#: `test_contagem_emulacao_conta_aparelho.py` trava as duas pontas.
_VPAD_UNIQ_PREFIX = "02:fe:"

#: Nome que o vpad uhid publica no evdev ("Hefesto Virtual DualSense P1").
_VPAD_NAME_PREFIX = "Hefesto Virtual"

#: Subárvore dos devices criados por uinput — Steam Input, teclado virtual do
#: daemon, qualquer programa. NÃO inclui `/devices/virtual/misc/uhid/`, que
#: hospeda tanto o nosso vpad quanto os controles BT físicos (BLUEZ-UHID-01).
_UINPUT_SUBTREE = "/devices/virtual/input/"

#: A QUARTA REGRA (item (a) acima): nomes exatos das máscaras do vpad em
#: uinput. Só valem DENTRO de `_UINPUT_SUBTREE` — restrição que o código não
#: mostra: um DualSense Edge REAL publica exatamente `DUALSENSE_EDGE_NAME`, e
#: o que o distingue da nossa máscara é morar sob o barramento (USB) ou sob
#: `/devices/virtual/misc/uhid/` (Bluetooth), nunca sob uinput.
_VPAD_NOMES_EM_UINPUT = (XBOX360_NAME, DUALSENSE_EDGE_NAME)

#: Teto de quebra do rótulo "Gamepads:", em caracteres. Ver a medição no corpo
#: de `_refresh_emulation_view`: ele existe para a frase longa não inflar a
#: largura NATURAL do cartão de diagnóstico (LARGURA-01).
LARGURA_MAXIMA_DO_ROTULO_DE_GAMEPADS = 52


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
    dir_input = os.path.dirname(sysfs)  # .../inputNN
    if _UINPUT_SUBTREE in sysfs:
        return dir_input
    return os.path.dirname(os.path.dirname(dir_input))  # o device HID


def _e_vpad_do_hefesto(no: dict[str, str]) -> bool:
    """True quando o aparelho é um gamepad virtual NOSSO — nos dois backends."""
    uniq = no.get("uniq", "").strip().lower()
    nome = no.get("name", "").strip()
    if uniq.startswith(_VPAD_UNIQ_PREFIX) or nome.startswith(_VPAD_NAME_PREFIX):
        return True
    return (
        _UINPUT_SUBTREE in no.get("sys", "") and nome in _VPAD_NOMES_EM_UINPUT
    )


def classificar_joysticks(nos: list[dict[str, str]]) -> tuple[int, int, int]:
    """`(físicos, nossos, de outros programas)` — APARELHOS, não nós.

    Função pura (recebe os atributos já lidos do sysfs) porque é ela que
    carrega o julgamento; a leitura de arquivo fica no chamador.
    """
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
    """Lê do sysfs o que :func:`classificar_joysticks` precisa julgar.

    Tolerante a tudo: nó que sumiu entre o `glob` e a leitura, atributo que o
    driver não publica, sysfs indisponível. Campo ilegível vira string vazia —
    o aparelho cai em "físico", que é a leitura CONSERVADORA (contá-lo como
    nosso inflaria o que dizemos ter criado).
    """
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
    """Texto do campo "Gamepads:" da aba Emulação.

    Diz o que aquilo É — quantos APARELHOS, separados por dono — e termina
    dizendo quantos NÓS de `/dev/input/js*` existem, que é o número cru que o
    campo mostrava sozinho. Os dois juntos EXPLICAM a diferença em vez de
    escondê-la: um controle na mesa pode render seis nós.
    """
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


# --- HONESTIDADE-STEAM-01: contrato de saída do disable_steam_input.sh ------
# O bug: o botão mostrava "desligando Steam Input (fecha e reabre a Steam)…",
# rodava `--apply-quiet` (que por contrato NUNCA fecha a Steam — se ela está
# viva, ADIA e sai 0) e em seguida anunciava "Steam Input desligado"
# incondicionalmente (`check=False` + `contextlib.suppress` engoliam tudo).
# Afirmação de sucesso sobre um no-op, com o tooltip mentindo junto.
#
# A cura tem três pernas: (1) o script passou a terminar com uma linha
# `[steam-input] resultado=<tag>`; (2) a GUI lê a tag E o rc; (3) o veredito
# final ainda é CONFERIDO relendo o vdf (`_steam_input_is_on`) — tag e rc
# dizem o que o script achou que fez, a releitura diz o que de fato ficou.
_RESULTADO_RE = re.compile(r"^\[steam-input\] resultado=(\S+)\s*$", re.MULTILINE)


def steam_input_result_tag(saida: str) -> str | None:
    """Tag `resultado=` da saída do script (a ÚLTIMA, se houver mais de uma).

    `None` quando o script é antigo (instalação anterior a esta onda) e não
    emite a linha — nesse caso a GUI cai no veredito por releitura do vdf, que
    nunca depende do script.
    """
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
            "instalação — rode ./install.sh para atualizar o Hefesto."
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
        # O caminho que a GUI ESCONDIA: o script adiou e nada mudou.
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


#: EMULACAO-NO-JOGO-01/E1(c): tradução do vocabulário FECHADO de ``bloqueio``,
#: publicado pelo daemon no bloco ``keyboard_emulation`` do ``daemon.status`` e
#: do ``daemon.state_full`` (``daemon/ipc_handlers.py:_keyboard_emulation_payload``;
#: a constante do último caso mora em ``daemon/lifecycle.CALADA_VPAD_SUSPENSO``).
#:
#: Invariante que o daemon deixou por escrito e que estas frases respeitam: nos
#: dois casos de PAUSA (``modo_jogo`` e ``vpad_suspenso_pelo_steam_input``) o
#: ``enabled`` continua TRUE. O teclado dela não foi desligado — ele saiu da
#: frente. Nenhuma dessas duas frases pode dizer "desligado".
BLOQUEIO_DO_TECLADO_EM_PORTUGUES: dict[str, str] = {
    "desligada": (
        "Desligado: o controle não digita mais nada — nem os atalhos da lista "
        "abaixo, nem o teclado na tela em L3/R3, nem as três regiões do "
        "touchpad (Backspace, Enter e Delete)."
    ),
    "sem_device": (
        "Ligado, mas o teclado virtual não subiu. Abra a aba Sistema e clique "
        "em “Aplicar correções”."
    ),
    "modo_jogo": (
        "Ligado, em pausa agora: o modo jogo está suspendendo mouse e teclado."
    ),
    "vpad_suspenso_pelo_steam_input": (
        "Ligado, em pausa agora: o jogo assumiu o controle. Não foi desligado — "
        "volta sozinho quando você fechar o jogo."
    ),
}

#: Sem o bloco não se sabe a posição do interruptor — e oferecer um interruptor
#: cuja posição você não conhece é exatamente o que mentia no lado do mouse
#: (HARM-05). A frase diz o que fazer, não o que faltou no protocolo.
TECLADO_SEM_ESTADO = (
    "Não consegui ler o estado do teclado emulado — o Hefesto pode estar "
    "desligado. Veja a aba Sistema."
)


def descrever_teclado_emulado(bloco: object) -> tuple[bool | None, str]:
    """(posição do interruptor, frase embaixo dele) a partir do bloco do daemon.

    Pura de propósito: é o miolo que decide o que ela vê, e ele precisa ter
    teste sem montar janela. ``None`` na primeira posição significa "não sei" —
    o interruptor fica insensível e nada é afirmado.
    """
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
    # Motivo NOVO, vindo de um daemon mais novo que esta janela: dizer o código
    # cru é feio, mas é honesto — e é melhor que afirmar que está funcionando.
    return ligado, f"Ligado, em pausa agora (motivo: {bloqueio})."


# --- PERFIL-SALVA-TUDO-01/E3: o "modo jogo" chega ao RASCUNHO ---------------
#
# Ela ESCLARECEU (29/07) que o "modo jogo" dela é suspender mouse e teclado. O
# toggle desta aba só mandava `daemon.emulation.suppress` — o próprio comentário
# do `on_emulation_pause` diz "NÃO persiste" — então o gesto morria com a sessão
# e o "Salvar Perfil" gravava `suppress_desktop_emulation: false` por cima.
#
# REGISTRAR não é APLICAR: a mesma linha do HARM-05 que vale para o modo (ver o
# cabeçalho de `rascunho_com_modo`, em home_actions). Quem suspende ao vivo é o
# IPC, no clique dela; aqui só se anota o que ficou.


#: Frase para o caso que este código RECUSA guardar. Ela precisa saber que o
#: interruptor pegou AGORA e que o perfil não vai lembrar — silêncio aqui seria
#: a janela mentindo a favor dela, que é o defeito-mãe desta sprint.
MODO_JOGO_NAO_GUARDADO = (
    "Modo jogo ligado — mouse e teclado suspensos agora. Não guardei no perfil: "
    "ele vale para qualquer janela, e guardado ali suspenderia mouse e teclado "
    "em toda ativação, até quando o Hefesto liga. Dê uma regra a ele na aba "
    "Perfis."
)


def perfil_do_rascunho_tem_opiniao(draft: DraftConfig | None) -> bool:
    """Espelha `lifecycle._perfil_tem_opiniao` para o perfil de ORIGEM do rascunho.

    Pergunta o MESMO predicado do daemon (`Profile.e_catch_all`, dono único do
    R-01: `MatchAny` e `MatchCriteria` vazio contam igual) sondando o `match` que
    a fotografia do rascunho guardou. Sem `match` legível responde False — o
    fail-safe daqui é NÃO guardar.
    """
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
    """(rascunho, guardei?) para o "modo jogo". Pura: NÃO aplica nada.

    O ramo de DESLIGAR sempre entra no rascunho. É gesto dela e é seguro: `False`
    é o default do esquema, e na ativação o applier só LIBERA quando a supressão
    veio de perfil e o perfil tem opinião (R-02). Sem este ramo, salvar um perfil
    que dizia `suppress: true` (o `sackboy_nativo` e o `coop_local` dela) ia
    ressuscitar a supressão que ela acabou de desligar.

    O ramo de LIGAR é RECUSADO em perfil catch-all, e isto foi MEDIDO em
    `daemon/lifecycle.apply_profile_suppression`: o ramo ``if desired:`` liga sem
    passar pelo `_perfil_tem_opiniao` — só o ramo de LIBERAR passa. Como os cinco
    perfis "vale sempre" dela não têm opinião, um `suppress: true` gravado num
    deles seria alçapão de mão única: liga em TODA ativação (inclusive no restauro
    do último perfil no boot) e o caminho de volta está fechado justamente pelo
    R-02 — mouse e teclado suspensos no desktop dela, sem ela pedir. Trocar a
    perda de configuração por um desktop sem ponteiro não é cura.

    Quando o gate do daemon existir no ramo de ligar (ver o contrato relatado
    nesta entrega), esta recusa pode cair — e o teste que a trava vai apontar
    exatamente para cá.
    """
    if draft is None:
        return draft, False
    if ligado and not perfil_do_rascunho_tem_opiniao(draft):
        return draft, False
    return draft.with_suppress(ligado), True


def registrar_modo_jogo_no_rascunho(janela: Any, ligado: bool) -> bool:
    """Anota o "modo jogo" na janela; devolve se ele foi GUARDADO no rascunho.

    Função de MÓDULO pela mesma razão de `registrar_modo_no_rascunho` (dono
    único, e dublê parcial de teste não pode quebrar por causa da MRO).

    O ``False`` não é erro: é a recusa deliberada de plantar `suppress: true`
    num perfil catch-all (ver `rascunho_com_modo_jogo`). Quem chama usa a
    resposta para dizer a VERDADE na barra de status — e o log fica, porque
    "não guardei" precisa deixar rastro tanto quanto "guardei".
    """
    draft = getattr(janela, "draft", None)
    if draft is None:
        return False
    novo, guardado = rascunho_com_modo_jogo(draft, ligado)
    if guardado and novo is not None:
        janela.draft = novo
    elif ligado:
        logger.info(
            "modo_jogo_nao_guardado_no_perfil",
            motivo="catch_all_sem_opiniao",
            perfil=getattr(draft, "source_name", None),
        )
    return guardado


class EmulationActionsMixin(WidgetAccessMixin):
    """Controla a aba Emulação."""

    def install_emulation_tab(self) -> None:
        self._get("emulation_device_name_label").set_text(DEVICE_NAME)
        self._get("emulation_vidpid_label").set_text(
            f"{XBOX360_VENDOR:04X}:{XBOX360_PRODUCT:04X} (Xbox 360)"
        )
        # FEAT-HOTKEY-PROFILE-CYCLE-01: os combos PS+D-pad ciclam o perfil
        # (next=PS+↑, prev=PS+↓), aplicando triggers/LEDs/bindings e piscando o
        # lightbar como feedback. Ligado em subsystems/hotkey.py.
        self._get("emulation_combo_next_label").set_markup(
            "PS + ↑ (D-pad) — próximo perfil"
        )
        self._get("emulation_combo_prev_label").set_markup(
            "PS + ↓ (D-pad) — perfil anterior"
        )
        # BUG-EMULATION-HOTKEY-CARD-FIXO-01: estas duas linhas escreviam a
        # CONSTANTE de compilação uma única vez e ninguém mais as tocava — a
        # tela afirmava "buffer 150" e "Passthrough: Não" como se fossem estado
        # lido do daemon, mesmo com o daemon offline. Agora saem rotuladas como
        # padrão e o `_sync_hotkey_card` as substitui pelo valor efetivo assim
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
        # releitura vai pelo `_refresh_emulation_tab` logo abaixo. Por que ele NÃO
        # está no gancho da aba Navegação: ver `app._REFRESH_POR_ABA`.
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
            # EMULACAO-NO-JOGO-01/E1: o interruptor do teclado. Ele DESENHA na
            # aba Navegação, mas o assunto é emulação e o dono é este mixin —
            # e é por aqui que ele é relido no botão "Atualizar" e ao entrar na
            # aba Emulação. Ver o comentário em `app._REFRESH_POR_ABA` para por
            # que ele não entrou no gancho da aba Navegação.
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

    # BOTÃO-QUE-NÃO-MENTE-01 (entregas 5 e 6): o `on_emulation_open_toml` SAIU.
    #
    # A entrega 3 tirou do glade o botão "Ver daemon.toml (referência)" e
    # deixou a decisão sobre o Python escrita ali (`gui/main.glade:2564-2569`):
    # *"quem cuida do Python nesta leva decide se o código sai junto"*. Ele
    # ficou — handler vivo, registrado em `app/app.py`, sem nada que o
    # chamasse. Isto é o que sai agora.
    #
    # Por que remover em vez de deixar dormindo: o método CRIAVA
    # `~/.config/hefesto-dualsense4unix/daemon.toml` no disco dela, um arquivo
    # com cara de configuração que o daemon não lê
    # (`BUG-DAEMON-TOML-DEAD-01` — a configuração efetiva vem de variáveis de
    # ambiente e do canal `daemon.reload`). Enquanto o código existisse, bastava
    # alguém reconectar o nome no glade para o arquivo fantasma voltar a
    # nascer: armadilha carregada, que é o mesmo padrão que a CÓDIGO-MORTO-01
    # descreveu no `xlib_window`.
    #
    # Volta quando (e se) existir arquivo de configuração de verdade — proposto
    # no bloco C da PROMESSA-NÃO-CUMPRIDA-01. Aí o botão e o handler nascem
    # juntos, apontando para um arquivo que o daemon lê de fato.

    # --- helpers ---

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
            # ADR-011: &#9679; (BLACK CIRCLE) via NCR — sobrevive ao sanitizer.
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
        # A frase honesta é ~4x mais longa que o "N controles" que substituiu, e
        # o rótulo do glade quebra linha (`wrap=True`). Medido em
        # `Gtk.OffscreenWindow` com o glade real, largura PEDIDA pelo rótulo:
        #
        #                                    mínimo   natural
        #   "6 controles detectados …"          67       220
        #   a frase nova, sem teto              64       799
        #   a frase nova, com o teto abaixo     64       363
        #
        # O teto existe pelo NATURAL, que é o que o GTK entrega quando há folga:
        # sem ele este cartão pediria 799px de largura numa janela larga, quase
        # o dobro dos 454px que o grid inteiro pedia antes (LARGURA-01).
        #
        # O que ele NÃO faz, e a medição foi clara: não desespreme a coluna. O
        # MÍNIMO do rótulo é a maior palavra (64px) e é o mínimo que esta aba
        # recebe hoje — o `emulation_diagnostico_row` é alocado em 721px, o
        # próprio mínimo dele. Por isso a frase quebra em muitas linhas (51px de
        # altura viraram 204px). Alargar o mínimo com `set_width_chars` curaria
        # a aparência e SUBIRIA o mínimo da aba inteira — é exatamente a
        # regressão que o comentário do glade sobre esta linha registra ter
        # custado rolagem em TODAS as páginas do notebook. Fica assim de
        # propósito: o espremido é da aba, não desta frase.
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
    # Liga/desliga o mic embutido reusando o mesmo caminho do CLI/install
    # (scripts/fix_wireplumber_default_source.sh). Mic ON = sem os drop-ins de
    # supressão 52/53; OFF = com eles. O quirk segura o storm com o mic ligado.

    _WP_DROPIN_DIR = Path.home() / ".config" / "wireplumber" / "wireplumber.conf.d"
    _WP_DISABLE_DROPINS = (
        "52-hefesto-dualsense-disable-source.conf",
        "53-hefesto-dualsense-disable-output.conf",
    )

    def _mic_script(self) -> Path | None:
        for cand in (
            ROOT_DIR / "scripts" / "fix_wireplumber_default_source.sh",
            Path("/usr/share/hefesto-dualsense4unix/scripts/fix_wireplumber_default_source.sh"),
            Path(
                "/usr/local/share/hefesto-dualsense4unix/scripts/"
                "fix_wireplumber_default_source.sh"
            ),
        ):
            if cand.is_file():
                return cand
        return None

    def _mic_is_on(self) -> bool:
        """Mic ON quando nenhum drop-in de supressão (52/53) está presente."""
        return not any(
            (self._WP_DROPIN_DIR / name).exists() for name in self._WP_DISABLE_DROPINS
        )

    # BUG-MIC-ON-SEM-QUIRK-REABRE-STORM-01: o quirk de áudio USB
    # (usbcore.quirks=054c:0ce6:gn) é o que segura o storm -71 COM o mic ligado.
    _USB_QUIRK_MARKER = "054c:0ce6:gn"
    _USB_QUIRK_PATHS: ClassVar[tuple[str, ...]] = (
        "/proc/cmdline",
        "/sys/module/usbcore/parameters/quirks",
    )

    @staticmethod
    def _usb_quirk_active() -> bool:
        """True se o quirk de áudio USB protege a SESSÃO ATUAL.

        Só /proc/cmdline (ATIVO) ou /sys/module/usbcore/parameters/quirks
        (runtime) valem agora; o agendado no bootloader só pega no próximo boot.
        Espelha o check_usb_quirk do doctor.sh, restrito aos sinais da sessão.
        """
        marker = EmulationActionsMixin._USB_QUIRK_MARKER
        for path in EmulationActionsMixin._USB_QUIRK_PATHS:
            with contextlib.suppress(OSError):
                if marker in Path(path).read_text(encoding="utf-8", errors="ignore"):
                    return True
        return False

    def _refresh_mic_status(self) -> None:
        label = self._get("emulation_mic_status_label")
        if label is None:
            return
        if self._mic_is_on():
            label.set_markup('<span foreground="#50fa7b">Ligado</span>')
        else:
            label.set_markup('<span foreground="#ffb86c">Desligado (suprimido)</span>')

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
        # BUG-MIC-ON-SEM-QUIRK-REABRE-STORM-01: a GUI não vê o stderr do script —
        # então, se o quirk de áudio USB não estiver ativo nesta sessão, o aviso
        # vai na mensagem FINAL (persiste no status bar). Um toast ANTES de ligar
        # seria sobrescrito pelo "aplicando no microfone..." do _run_mic e ficaria
        # invisível. Ligar sem o quirk pode reabrir o storm -71; não bloqueia e
        # NÃO mexemos no cmdline (gerido pela toolchain pessoal Aurora).
        if self._usb_quirk_active():
            done = "Mic do DualSense ligado"
        else:
            done = (
                "Mic ligado — atenção: sem o ajuste de áudio o controle pode "
                "travar no meio do jogo. Abra a aba Sistema e clique em "
                "“Aplicar correções” (vale no próximo boot)."
            )
        self._run_mic("--enable-mic", done)

    def on_emulation_mic_off(self, _btn: Gtk.Button) -> None:
        self._run_mic("--disable-source", "Mic do DualSense desligado")

    # --- gamepad virtual + modo-jogo (FEAT-DSX-GAMEPAD-FLAVOR-01) ---
    # Tudo via IPC pro daemon (gamepad.emulation.set / daemon.pause|resume),
    # que é o único leitor do controle — sem o input dobrado do bridge avulso.

    # Seletor de gamepad: 3 botões = 3 modos. Realçamos o ativo (GtkButton não
    # tem :checked, então marcamos a classe .hefesto-active-mode via código).
    _GAMEPAD_BUTTON_IDS: ClassVar[dict[str, str]] = {
        "off": "emulation_gamepad_off_button",
        "dualsense": "emulation_gamepad_dualsense_button",
        "xbox": "emulation_gamepad_xbox_button",
    }

    def _highlight_gamepad(self, active_key: str | None) -> None:
        """Destaca o botão do modo de gamepad atual (off/dualsense/xbox).

        ``None`` (daemon offline / estado desconhecido) limpa o realce de todos.
        """
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
        """HARM-03/EMU-07: "Modo jogo" só faz sentido "jogando pelo Hefesto".

        Em "Controlar o PC" o controle SÓ faz mouse/teclado — suspendê-los
        deixava o controle sem função nenhuma. Em "Jogar direto (Sony)" o jogo
        fala direto com o controle: não há mouse/teclado nem gamepad virtual
        para suspender, e o toast ainda afirmava "gamepad ativo". Nos dois casos
        o botão fica desabilitado com a razão em texto simples ao lado.

        "Sair do modo jogo" continua sensível em TODOS os modos: é a saída de
        emergência de quem caiu em desktop+suspenso pelo combo PS+Options.
        """
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
                "Em \"Jogar direto (Sony)\" o jogo fala direto com o controle — "
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
            # HARM-01: no Modo Nativo o vpad está desligado, mas dizer só
            # "desligado" (e realçar "Desligado") fazia esta aba contradizer a
            # Início, que mostra "Jogar direto (Sony)". Nenhum dos três botões
            # é a verdade aqui — o realce sai e o label conta o modo real.
            if mode == MODE_NATIVE:
                active_key = None
                if gp_label is not None:
                    gp_label.set_markup(
                        '<span foreground="#ffb86c">Jogar direto (Sony) — o jogo '
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
            # BUG-EMULATION-UINPUT-CARD-STALE-01: o cartão UINPUT mostrava
            # SEMPRE "X-Box 360 / 045E:028E" (constantes de install) mesmo com
            # a máscara real em DualSense — informação contraditória na mesma
            # tela. Reflete o device/VID:PID do vpad REALMENTE ativo.
            self._sync_uinput_card(active_key)
            self._sync_hotkey_card(state)
            gm_label = self._get("emulation_gamemode_status_label")
            if gm_label is not None and isinstance(state, dict):
                # BUG-GAMEMODE-LABEL-AMBIGUO-01: o label dizia "ativo" quando o
                # modo jogo estava DESLIGADO (referia-se à emulação) — lido como
                # "Modo jogo: ativo", significava o CONTRÁRIO do exibido.
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
            # BUG-EMULATION-UINPUT-CARD-STALE-02: offline, o cartão UINPUT não
            # pode seguir afirmando o device/VID:PID do último estado online.
            sync_card = getattr(self, "_sync_uinput_card", None)
            if sync_card is not None:
                sync_card(None)
            # Offline o buffer/passthrough voltam a ser "padrão", não o último
            # valor lido — a mesma regra do cartão UINPUT logo acima.
            sync_hotkey = getattr(self, "_sync_hotkey_card", None)
            if sync_hotkey is not None:
                sync_hotkey(None)
            # HARM-03: sem estado não dá para saber se "Modo jogo" faz sentido;
            # oferecê-lo às cegas pode cair no caso que mata o controle.
            self._sync_gamemode_button(None)
            return False

        # HARM-15: a folga do state_full vale AQUI também — sem ela esta aba
        # (para onde a UI inteira manda a usuária quando algo dá errado) se pinta
        # de "daemon offline" com o daemon VIVO, sempre que ele passa dos 0,25s
        # default (hotplug, co-op subindo). O timeout mora no mode_transition
        # junto do `mode_of_state`: é a mesma leitura.
        call_async(
            "daemon.state_full", {}, on_success=_on_state, on_failure=_on_err,
            timeout_s=STATE_IPC_TIMEOUT_S,
        )

    def _apply_mode(self, mode_id: str, flavor: str | None, msg: str) -> None:
        """Muda o modo pelo MESMO caminho da Início (HARM-01).

        Antes esta aba chamava `gamepad.emulation.set` cru, sem sair do Modo
        Nativo: nativo + gamepad ligados juntos = físico grabado pelo jogo +
        vpad congelado, ou seja, JOGO SEM CONTROLE NENHUM — e a Início ainda
        exibia "Jogar direto (Sony)", escondendo o estado real. Delegar a
        `mode_transition` mantém um dono só para a sequência e o timeout.
        """
        def _on_ok(_res: Any) -> bool:
            # PERFIL-SALVA-TUDO-01/E3: o modo entra no rascunho DEPOIS da
            # confirmação do daemon — o rascunho guarda o que ficou de pé, não a
            # intenção. Registrar não aplica nada (`rascunho_com_modo`).
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
        # "Desligado" = o modo "Controlar o PC" da Início. Desligar só o vpad
        # deixaria o Modo Nativo de pé com o botão realçado como "Desligado" —
        # duas abas contando histórias diferentes sobre o mesmo estado.
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
        self._apply_mode(MODE_GAMEPAD, "xbox", "Gamepad Xbox 360 ligado (vibra no jogo)")

    def _set_suppress(self, suppressed: bool, msg: str) -> None:
        def _on_ok(_res: Any) -> bool:
            # PERFIL-SALVA-TUDO-01/E3: o "modo jogo" dela vira configuração do
            # perfil — quando o perfil pode recebê-lo. A frase troca quando a
            # resposta é "não guardei": a janela não pode ficar calada sobre o
            # que ela vai perder no próximo boot.
            guardado = registrar_modo_jogo_no_rascunho(self, suppressed)
            self._refresh_gamepad_and_gamemode()
            self._toast_emulation(
                msg if (guardado or not suppressed) else MODO_JOGO_NAO_GUARDADO
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
        # FEAT-DSX-GAMEMODE-SUPPRESS-01: o botão "Modo jogo" usa
        # daemon.emulation.suppress (transitório, paridade real com o combo
        # PS+Options) em vez de daemon.pause. daemon.pause persistia paused.flag
        # e o daemon RENASCIA pausado no boot (controle morto no jogo até
        # "Retomar"), além de ser um kill-switch mais amplo (parava gatilhos/LED/
        # edges). Suppress suspende SÓ mouse/teclado e NÃO persiste; o gamepad
        # segue vivo no jogo (FEAT-DSX-GAMEPAD-ALWAYS-LIVE-01). Como o label
        # 'Modo jogo' lê emulation_suppressed, ele passa a refletir o estado certo.
        self._set_suppress(True, "Modo jogo ligado — mouse e teclado suspensos")

    def on_emulation_resume(self, _btn: Gtk.Button) -> None:
        self._set_suppress(False, "Modo jogo desligado: mouse/teclado retomados")

    # --- interruptor do teclado emulado (EMULACAO-NO-JOGO-01/E1) -----------
    # O teclado emulado não tinha interruptor NENHUM: o único switch da aba
    # dizia "Emular mouse+teclado" e governava só o mouse. A cura do motor
    # (`keyboard.emulation.set` + bloco `keyboard_emulation`) já está no daemon;
    # aqui é a chave que a alcança.

    #: Guard contra loop switch -> IPC -> refresh -> switch. Em GTK3
    #: `set_active` reemite `state-set` SINCRONAMENTE — `return True` no handler
    #: não evita (repro real do lado do mouse: 999 reentradas + RecursionError).
    _keyboard_guard_refresh: bool = False

    #: Última posição CONFIRMADA pelo daemon. É para ela que uma falha reverte,
    #: e NÃO para `not enabled` capturado no clique: com dois cliques rápidos e
    #: o daemon travado, o `not enabled` do segundo RPC deixava o interruptor
    #: preso na posição errada (BUG-MOUSE-TOGGLE-STALE-REVERT-01, mesma classe).
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
        # ela a chave nasce cinza com o daemon VIVO sempre que ele passa dos
        # 0,25s default (hotplug, co-op subindo).
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
                # O custo de desligar NÃO é óbvio e foi medido: sai o teclado na
                # tela (L3/R3) e as três regiões do touchpad, não só o Alt+Tab.
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
        # Otimista: o handler default do GtkSwitch aplica a posição; a falha
        # reverte no callback.
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

    # --- Steam Input (FEAT-STEAM-INPUT-SELF-HEAL-01 via GUI) ---
    # Steam Input PSSupport ligado SEQUESTRA o controle e conflita com o daemon
    # (touchpad/teclado vazam, mic spam). Botão pra verificar/desligar.

    def _steam_input_script(self) -> Path | None:
        for cand in (
            ROOT_DIR / "scripts" / "disable_steam_input.sh",
            Path("/usr/share/hefesto-dualsense4unix/scripts/disable_steam_input.sh"),
            Path("/usr/local/share/hefesto-dualsense4unix/scripts/disable_steam_input.sh"),
        ):
            if cand.is_file():
                return cand
        return None

    @staticmethod
    def _steam_input_is_on() -> bool | None:
        """True/False se Steam Input CONFLITANTE está ligado; None se indeterminado.

        STEAM-INPUT-ALLOWLIST-01: usa o mesmo walker de blocos do storm_doctor —
        opt-in per-app deliberado (jogos cujo DualSense é entregue pela Steam,
        ex.: MMJ na allowlist) NÃO conta como conflito; as chaves globais
        (PSSupport/SwitchSupport) e per-app fora da allowlist contam.
        """
        from hefesto_dualsense4unix.integrations.storm_doctor import (
            steam_input_allowlist,
            steam_input_on_fora_da_allowlist,
        )

        vdfs = glob.glob(
            str(Path.home() / ".steam" / "steam" / "userdata" / "*" / "config" / "localconfig.vdf")
        )
        if not vdfs:
            return None
        allow = steam_input_allowlist()
        for vdf in vdfs:
            with contextlib.suppress(OSError):
                texto = Path(vdf).read_text(encoding="utf-8", errors="ignore")
                if steam_input_on_fora_da_allowlist(texto, allow):
                    return True
        return False

    @staticmethod
    def _steam_input_excecao_status() -> tuple[list[int], bool | None]:
        """(appids da allowlist, exceção EFETIVA agora) — R-06 item 3.

        "Configurada" e "efetiva" são coisas diferentes e a confusão entre elas
        é o que deixou a allowlist inerte por meses: o appid estava no arquivo,
        o guard de VDF o respeitava, e mesmo assim o daemon seguia escondendo o
        hidraw do controle físico — o jogo não via DualSense nenhum. Aqui:

        - **configurada** = appids em `steam_input_apps.txt`;
        - **efetiva** = TODO hidraw de DualSense físico está legível por ESTE
          uid agora (é a permissão da usuária que decide, e a GUI roda como
          ela). `None` quando não há físico visível no sysfs — não dá para
          afirmar nem negar, e mentir aqui seria repetir o erro original.
        """
        from hefesto_dualsense4unix.broker.hidraw_broker import (
            physical_nodes_exposure,
        )
        from hefesto_dualsense4unix.daemon.launch_env import steam_input_appids

        appids = sorted(steam_input_appids())
        exposicao: dict[str, bool] = {}
        with contextlib.suppress(Exception):
            exposicao = physical_nodes_exposure(os.getuid())
        if not exposicao:
            return appids, None
        return appids, all(exposicao.values())

    def _refresh_steam_input_status(self) -> None:
        label = self._get("emulation_steam_input_status_label")
        if label is None:
            return

        def _check() -> tuple[bool | None, list[int], bool | None]:
            return (self._steam_input_is_on(), *self._steam_input_excecao_status())

        def _on_ok(dados: tuple[bool | None, list[int], bool | None]) -> bool:
            on, appids, efetiva = dados
            if on is None:
                markup = '<span foreground="#8b8fa8">Steam não encontrado</span>'
            elif on:
                markup = (
                    '<span foreground="#ffb86c">Ligado — conflita com o Hefesto</span>'
                )
            else:
                markup = '<span foreground="#50fa7b">Desligado — tudo certo</span>'
            if appids:
                # R-06: a usuária precisa ver se o opt-in dela está VALENDO, não
                # só se está escrito no arquivo.
                if efetiva is None:
                    extra = "sem controle físico visível"
                elif efetiva:
                    extra = "controle liberado agora"
                else:
                    extra = "só valendo durante o jogo"
                markup += (
                    f' <span foreground="#8b8fa8">· Exceção por jogo: '
                    f'{len(appids)} jogo(s) — {extra}</span>'
                )
            label.set_markup(markup)
            return False

        run_in_thread(_check, on_success=_on_ok)

    def on_emulation_steam_input_check(self, _btn: Gtk.Button) -> None:
        self._refresh_steam_input_status()
        self._toast_emulation("Steam Input verificado")

    def on_emulation_steam_input_disable(self, _btn: Gtk.Button) -> None:
        """Desliga o Steam Input — com consentimento e com veredito conferido.

        HONESTIDADE-STEAM-01. Antes: toast "desligando Steam Input (fecha e
        reabre a Steam)…" → `--apply-quiet` (que NÃO fecha nada; com a Steam
        viva ele ADIA) → toast "Steam Input desligado", incondicional. Duas
        mentiras encadeadas — a promessa de fechar e a afirmação de sucesso.

        Agora, no clique:

        1. JOGO aberto ⇒ RECUSA. `steam -shutdown` mataria o jogo (progresso
           não salvo perdido) — mesma decisão do DEDUP-05 no lado Python;
        2. só a Steam aberta ⇒ DIÁLOGO pedindo permissão para fechá-la por
           ~20 s (e avisando para pausar downloads). Sem sim explícito nada
           acontece: `stop_steam()` escala para `pkill -TERM/-KILL` depois de
           30 s, e isso jamais pode rodar às costas da usuária;
        3. Steam fechada ⇒ aplica direto.

        O toast final sai de `format_steam_input_result`, que exige EVIDÊNCIA
        (releitura do vdf) antes de dizer "Pronto".

        A SONDAGEM (dois `pgrep` com timeout de 5 s cada) roda em worker, não
        na thread GTK: no clique, o pior caso seriam 10 s de janela congelada
        — o mesmo modo de falha que BUG-GUI-DAEMON-STATUS-INITIAL-01 já pagou
        na aba Sistema. O diálogo volta pela `GLib.idle_add` (widget só na
        thread GTK).
        """
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

        # Steam viva: pede consentimento ANTES de qualquer coisa.
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
        return False  # GLib.idle_add: não reagenda

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
                # Veredito por EVIDÊNCIA: relê os vdf em vez de crer no rc.
                ainda_ligado = (
                    self._steam_input_is_on() if status == "executado" else None
                )
            except Exception as exc:
                # `except Exception` largo DE PROPÓSITO: este worker roda no
                # executor, onde exceção não propagada morre calada — e toast
                # que nunca chega é a mesma doença do "Steam Input desligado"
                # incondicional, só que ao contrário. Falha vira frase.
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
