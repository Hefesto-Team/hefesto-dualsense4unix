"""Aba Início — comutador de MODO do sistema + controles + desligar de verdade.

FEAT-GUI-HOME-TAB-01. A primeira aba responde as três perguntas que a interface
antiga espalhava por quatro lugares:

1. "Em que modo o sistema está?" — comutador Desktop / Jogo (gamepad) / Jogo
   nativo, com a máscara (DualSense/Xbox) quando faz sentido. Reflete também o
   modo ligado POR PERFIL (FEAT-PROFILE-MODE-01). LEIGO-01: não há mais toggle
   de co-op — cada controle é um jogador, sempre; a aba só INFORMA quantos.
2. "Quais controles estão conectados?" — um card por controle físico, com
   transporte, jogador (P1/P2…, o número que o JOGO vê — LEIGO-01b), bateria e o
   aviso de grab degradado (input dobrado). LEIGO-02: o fim do MAC saiu do card
   — ela distingue os controles pela COR da luz e pelo LED de jogador, não por
   um hash que não está escrito em lugar nenhum do aparelho.
2b. "Por onde o jogo está recebendo o controle, e a minha escolha chegou?" —
   PONTE-NA-TELA-01, a linha "Ponte com o jogo" e o aviso de divergência de
   máscara, os dois logo abaixo de "O jogo vê o controle como:".
3. "Como desligo o hefesto DE VERDADE?" — botão dedicado que para o daemon e
   NÃO o religa ao reabrir/atualizar a GUI (diferente do "Desligar o Hefesto"
   da aba Sistema, que o `ensure_daemon_running` ressuscitava sem avisar).

Todo widget é montado em código dentro de `tab_home_box` (Glade só reserva o
container) — padrão dos widgets dinâmicos, imune ao bug de popup do cosmic-comp
(botões sempre visíveis, sem dropdown).
"""
from __future__ import annotations

import contextlib
import re
from collections.abc import Sequence
from typing import Any, Final

from hefesto_dualsense4unix.app.actions.mode_transition import (
    MODE_DESKTOP,
    MODE_GAMEPAD,
    mode_of_state,
)
from hefesto_dualsense4unix.integrations.steam_launch_options import juntar_rotulos
from hefesto_dualsense4unix.utils.logging_config import get_logger

logger = get_logger(__name__)


# DualSense físico, sem intermediário (docs/usage/modos.md).
_MODE_ITEMS = [
    ("desktop", "Controlar o PC"),
    ("gamepad", "Jogar pelo Hefesto"),
    ("native", "Conexão Nativa (Sony)"),
]

# LEIGO-02: "(vibra)"/"(sem vibrar)" eram verdade enquanto a máscara DualSense
_FLAVOR_ITEMS = [
    ("xbox", "Xbox 360"),
    ("dualsense", "DualSense (botões PlayStation)"),
    ("nintendo", "Nintendo Pro (botões da Nintendo)"),
]


TEXTO_EM_PAUSA: Final[str] = (
    "O Hefesto está em pausa: nada disto está acontecendo agora — sem luzes, "
    "sem vibração e sem os seus ajustes. O controle segue funcionando nos "
    "jogos como um controle comum. Para voltar, use o atalho do controle "
    "(PS + Options) ou o botão “Retomar”, na aba Sistema."
)


def texto_da_pausa(state: dict[str, Any] | None) -> str | None:
    """O produto está PARADO? — função pura (I4, 25/08/2026)."""
    if not isinstance(state, dict):
        return None
    return TEXTO_EM_PAUSA if state.get("paused") is True else None


def autoswitch_lock_text(state: dict[str, Any] | None) -> str:
    """Frase do Modo Freestyle ligado — função PURA (UX-05)."""
    if not state or not state.get("freestyle_ligado"):
        return ""
    from hefesto_dualsense4unix.app.actions.profiles_actions import (
        perfil_que_esta_valendo,
    )

    ativo = perfil_que_esta_valendo(state).nome
    alvo = f" — vale o perfil “{ativo}”" if ativo else ""
    return f"Modo Freestyle ligado: o perfil não troca sozinho, nem no jogo{alvo}."


TEXTO_DETECTOR_CEGO: Final[str] = (
    "O Hefesto não está conseguindo ver qual programa está na frente, então o "
    "perfil não vai trocar sozinho de qualquer jeito — isto não é escolha sua. "
    "A aba Sistema diz por quê."
)


def texto_do_cadeado_cego(state: dict[str, Any] | None) -> str:
    """O mecanismo do cadeado está cego? — função PURA (I11, 25/08/2026)."""
    if not isinstance(state, dict) or "window_detect_seeing" not in state:
        return ""
    return "" if state.get("window_detect_seeing") else TEXTO_DETECTOR_CEGO


def _mode_label(mode_id: object) -> str:
    """Rótulo do modo como a usuária o lê no botão (LEIGO-02) — função pura."""
    return dict(_MODE_ITEMS).get(str(mode_id), str(mode_id))


def _flavor_label(flavor_id: object) -> str:
    """Idem para a aparência do controle no jogo ("xbox" → "Xbox 360")."""
    return dict(_FLAVOR_ITEMS).get(str(flavor_id), str(flavor_id))


VPAD_DEGRADED_TEXT = (
    "O gamepad virtual subiu no modo simples: a vibração e a separação do "
    "controle físico não estão garantidas. Reinicie o Hefesto na aba Sistema."
)

VPAD_COOP_DEGRADED_TEXT = (
    "O gamepad virtual de um dos jogadores do co-op subiu no modo simples: "
    "aquele jogador pode ficar sem vibração — e sem controle, se o jogo foi "
    "aberto com a desduplicação ligada. Reinicie o Hefesto na aba Sistema."
)

_COOP_DEGRADED_UM = (
    "O gamepad virtual do Jogador {quem} subiu no modo simples: esse jogador "
    "pode ficar sem vibração — e sem controle, se o jogo foi aberto com a "
    "desduplicação ligada. Reinicie o Hefesto na aba Sistema."
)
_COOP_DEGRADED_VARIOS = (
    "Os gamepads virtuais dos Jogadores {quem} subiram no modo simples: esses "
    "jogadores podem ficar sem vibração — e sem controle, se o jogo foi aberto "
    "com a desduplicação ligada. Reinicie o Hefesto na aba Sistema."
)

_JOGADOR_DEGRADADO_RE = re.compile(r"\bjogador_(\d+)_uinput\b")


def jogadores_degradados(motivo: object) -> list[int]:
    """Números dos jogadores citados no ``dedup_motivo`` — função pura."""
    if not isinstance(motivo, str):
        return []
    vistos: set[int] = set()
    for achado in _JOGADOR_DEGRADADO_RE.finditer(motivo):
        vistos.add(int(achado.group(1)))
    return sorted(vistos)


def texto_coop_degradado(jogadores: Sequence[int]) -> str:
    """Banner do co-op NOMEANDO quem caiu; genérico quando não há número.

    MESA-CHEIA-11/E2 — a entrega mais barata da onda: o dado já viajava no
    `state_full`, e a janela dizia "um dos jogadores" para uma mesa de quatro.
    """
    numeros = [n for n in jogadores if isinstance(n, int) and not isinstance(n, bool)]
    if not numeros:
        return VPAD_COOP_DEGRADED_TEXT
    quem = juntar_rotulos([str(n) for n in numeros])
    molde = _COOP_DEGRADED_UM if len(numeros) == 1 else _COOP_DEGRADED_VARIOS
    return molde.format(quem=quem)


# estruturalmente frágil — o SDL pode não enxergar o DualSense BT nem sem
NATIVE_BT_FRAGIL_TEXT = (
    "Modo Nativo com o controle em Bluetooth: alguns jogos não enxergam o "
    "DualSense por BT (limite do SDL). Se o jogo não vir o controle, use o "
    "cabo USB ou volte para a emulação de gamepad."
)

_NATIVE_BT_FRAGIL_UM = (
    "Modo Nativo com o Controle {quem} em Bluetooth: alguns jogos não o "
    "enxergam (limite do SDL). Se o jogo não vir esse controle, ligue-o no "
    "cabo USB ou volte para a emulação de gamepad."
)
_NATIVE_BT_FRAGIL_VARIOS = (
    "Modo Nativo com os Controles {quem} em Bluetooth: alguns jogos não os "
    "enxergam (limite do SDL). Se o jogo não vir esses controles, ligue-os no "
    "cabo USB ou volte para a emulação de gamepad."
)


def controles_bt_frageis(state: dict[str, Any] | None) -> list[int]:
    """Números dos controles frágeis por BT no Modo Nativo, do ``state_full``.

    MESA-CHEIA-11/E1. Quem decide QUAIS é o daemon
    (`daemon/ipc_handlers.controles_bt_frageis`), porque é ele que enxerga a
    mesa inteira; aqui só se lê a lista publicada, com a mesma defesa dos
    outros leitores de payload.

    **Lista vazia não quer dizer "nenhum frágil"** — quer dizer "não sei quais",
    e é o que um daemon antigo (sem a chave) ou um backend sem
    `describe_controllers` devolve. Por isso quem chama continua olhando também
    o booleano `native_bt_fragil`: o aviso acende, só que sem nomes.

    Ordena de novo o que o daemon já ordenou (`sorted(numeros)`, no fim do
    `daemon/ipc_handlers.controles_bt_frageis`). Não é desconfiança do daemon: é
    que esta é a ÚLTIMA parada antes do olho de quem confere, e a regra "os números saem
    crescentes" tem de valer mesmo quando quem publicou o payload for um daemon
    diferente do que está no fonte de hoje (install editable: o daemon vivo é
    mais velho que o código). Custo: uma ordenação de no máximo quatro números.
    """
    if not isinstance(state, dict):
        return []
    numeros = state.get("native_bt_fragil_controles")
    if not isinstance(numeros, list):
        return []
    return sorted(n for n in numeros if isinstance(n, int) and not isinstance(n, bool))


def texto_native_bt_fragil(numeros: Sequence[int]) -> str:
    """Banner do BT frágil NOMEANDO os controles; genérico sem número."""
    validos = [n for n in numeros if isinstance(n, int) and not isinstance(n, bool)]
    if not validos:
        return NATIVE_BT_FRAGIL_TEXT
    quem = juntar_rotulos([str(n) for n in validos])
    molde = _NATIVE_BT_FRAGIL_UM if len(validos) == 1 else _NATIVE_BT_FRAGIL_VARIOS
    return molde.format(quem=quem)


# `interface/pacotes/perfil.com_a_carona`, que o rodapé das dez abas chama no
WRAPPER_MISSING_TEXT = (
    "O jogo está rodando sem o atalho de inicialização — controles podem "
    "duplicar. Reponho o atalho no próximo Aplicar ou Salvar Perfil, com a "
    "Steam fechada."
)


def wrapper_banner_text(state: dict[str, Any] | None) -> str | None:
    """Texto do banner "jogo sem wrapper"; ``None`` quando não há aviso.

    Contrato do `state_full.gamepad_emulation.wrapper_used` (produzido pelo
    daemon cruzando o marker do `hefesto-launch` com a janela steam_app):

    - ``False`` = há jogo aberto E ele NÃO passou pelo wrapper → banner;
    - ``True`` = o jogo abriu pelo wrapper → sem banner;
    - ``None``/ausente = sem jogo aberto, ou daemon antigo sem o campo →
      sem banner (nunca alarme falso por payload incompleto).

    Só o ``False`` LITERAL acende — função pura, consumida pelas abas Início
    e Status (mesmo desenho do `vpad_degradation_text`).
    """
    if not isinstance(state, dict):
        return None
    gamepad = state.get("gamepad_emulation")
    if not isinstance(gamepad, dict):
        return None
    if gamepad.get("wrapper_used") is False:
        return WRAPPER_MISSING_TEXT
    return None


def appid_do_jogo_em_foco(state: dict[str, Any] | None) -> str:
    """O appid da Steam do jogo que está na frente, ou "" — função pura."""
    if not isinstance(state, dict):
        return ""
    from hefesto_dualsense4unix.app.actions import launch_wrapper_dialog as _lwd

    classe = state.get("window_detect_current_class") or state.get(
        "window_detect_last_class"
    )
    return _lwd.extract_steam_appid(classe) or ""


def ela_ja_respondeu_sobre(appid: str) -> bool:
    """O usuário já disse "eu sei, deixa assim" sobre este jogo? — as DUAS recusas.

    São duas listas e as duas contam, porque as duas são o usuário dizendo a mesma
    coisa: `launch_dialog_dismissed.json` ("Não perguntar para este jogo") e
    `jogos_sem_wrapper.txt` ("Tirar daqui").

    Best-effort de propósito: qualquer falha de disco devolve ``False`` — na
    dúvida, o aviso aparece. Esconder um aviso por causa de um erro de leitura
    é pior que mostrá-lo duas vezes.

    ELA TOCA O DISCO, E O CUSTO ESTÁ MEDIDO — 06/09/2026, ONDA5-07-03. Duas
    leituras de arquivo por chamada, e quem chama é a pintura da aba Jogar, dez
    vezes por segundo (`jogar/painel.AVISOS_DA_TELA`). A
    `a07_lancadores.calados` avisa, por escrito, que reler duas listas a cada
    tique é *"disco na thread da janela"* — e o número diz que este caminho não
    o sente: **0,050 ms por tique** com os dois arquivos existindo e povoados,
    contra 2,85 ms de mediana do tique inteiro. Duas razões, e as duas são de
    desenho: `aviso_do_wrapper` só chega aqui quando há **jogo aberto sem o
    atalho** (o caso raro), e sem appid a função devolve na primeira linha, sem
    abrir nada. Trocar isto por uma vigia em segundo plano custaria uma thread e
    um TTL para poupar 0,05 ms — e deixaria a Início e a Status, que não têm
    tique, dependendo de um relógio da janela.
    """
    if not appid:
        return False
    from hefesto_dualsense4unix.app.actions import launch_wrapper_dialog as _lwd
    from hefesto_dualsense4unix.integrations import steam_launch_options as _slo

    alvo = str(appid)
    with contextlib.suppress(Exception):
        if alvo in {str(a) for a in _lwd.load_dismissed_appids()}:
            return True
    with contextlib.suppress(Exception):
        if alvo in {str(a) for a in _slo.ler_jogos_sem_wrapper()}:
            return True
    return False


def aviso_do_wrapper(state: dict[str, Any] | None) -> str | None:
    """O banner "jogo sem wrapper", CALADO quando ela já respondeu. **UM dono.**

    Nasceu em 05/09/2026, e a razão é um defeito medido: ela dispensava o aviso
    na aba Lançadores e **três outras telas continuavam acusando** — a Início, a
    Status e a coluna Atenção da aba Jogar
    (`app/actions/jogar/painel.py:358`), porque as três chamavam
    `wrapper_banner_text` direto, sem consultar lista nenhuma.

    A decisão, 05/09/2026 (pergunta `07-Q3`): *"as duas recusas calam
    tudo"*. E a `a07_lancadores.calados` já dizia, por escrito, que a conta
    precisava de um dono para a outra metade não a redigitar.

    `wrapper_banner_text` continua puro e continua existindo: ele responde
    *"há jogo sem wrapper agora?"*. Esta função responde a pergunta que as telas
    de fato fazem — *"há algo a dizer a ela sobre isso?"* — e é ela que as
    telas chamam.

    O SILÊNCIO MORA AQUI, E NÃO NO PACOTE DA ABA — ONDA5-07-03, 06/09/2026. A
    sprint desenhava a cura como um parâmetro nomeado em
    `jogar/painel.avisos_do_estado`, com a aba Jogar entregando a lista lida
    pela vigia da aba Lançadores. **O caminho que ficou é melhor por uma razão
    medida:** com a conta dentro da função dona, a BANCADA
    (`interface/jogar_vivo.py`, que chama `avisos_do_estado` em dois pontos)
    mede exatamente o que o produto mostra, sem ninguém ter de lembrar de
    passar a lista. Um dublê mais frouxo que a função real já envenenou outro
    arquivo por ordem de teste, em 04/09; um parâmetro que a bancada esquece de
    passar seria a mesma família de defeito.
    """
    texto = wrapper_banner_text(state)
    if texto is None:
        return None
    if ela_ja_respondeu_sobre(appid_do_jogo_em_foco(state)):
        return None
    return texto


def texto_do_radio_fragil(state: dict[str, Any] | None) -> str | None:
    """O aviso de rádio frágil no Modo Nativo, ou ``None``. **UM dono.**

    Extraído de `vpad_degradation_text` em 25/08/2026
    (PERFIS-ABRE-O-QUE-GUARDA-01/§P8) porque ganhou a **segunda** aba: a Perfis
    é quem OFERECE o Modo Nativo (um dos quatro botões do editor) e não dizia
    uma palavra sobre a fragilidade — `native_bt_fragil` tinha leitor num
    arquivo só, medido com `grep -rln` em 24/08. Duas leitoras e uma frase
    escrita duas vezes é exatamente como esta casa ganhou os oito pares da F5;
    então a decisão virou função com nome, e as duas a chamam.

    O comportamento é o mesmo, byte a byte: a LISTA manda quando existe (nomeia
    quem está frágil) e o booleano continua acendendo o aviso genérico, que é o
    que um daemon mais VELHO que esta janela sabe dizer — install editable
    deixa os dois convivendo até o próximo start (MESA-CHEIA-11/E1).
    """
    if not isinstance(state, dict):
        return None
    frageis = controles_bt_frageis(state)
    if frageis or state.get("native_bt_fragil") is True:
        return texto_native_bt_fragil(frageis)
    return None


def vpad_degradation_text(state: dict[str, Any] | None) -> str | None:
    """Texto do banner de degradação do vpad; ``None`` quando não há aviso.

    UX-03: o `state_full.gamepad_emulation` expõe `backend` ("uhid" = DualSense
    Edge real com hidraw; "uinput" = fallback sem hidraw). Máscara DualSense no
    backend uinput significa vibração in-game morta e separação do controle
    físico não garantida — sem o banner, a usuária conclui que "o hefesto não
    funciona". Função pura (padrão `_flavor_label`), consumida pelas abas
    Início e Status.

    DEDUP-06 (o guard anti-veneno): o banner também fala pelos jogadores do
    co-op — `dedup_ok=False` com motivo `jogador_N_uinput` acende o aviso
    mesmo com o vpad primário saudável — e pelo estado BT+Nativo
    (`native_bt_fragil` do state_full, hoje acompanhado da lista
    `native_bt_fragil_controles`), que tem aviso próprio e NOMEIA quais.

    Sem alarme falso: backend ausente/"" é transitório real (vpad subindo, o
    `_gamepad_device` ainda None — o `ipc_handlers` só emite a chave com device
    vivo) e NÃO acende o banner; `dedup_motivo="vpad_ausente"` idem (mesmo
    transitório visto pelo guard); máscara xbox em uinput é o desenho normal;
    fora do modo gamepad não há vpad a avaliar.
    """
    if not isinstance(state, dict):
        return None
    do_radio = texto_do_radio_fragil(state)
    if do_radio is not None:
        return do_radio
    if mode_of_state(state) != MODE_GAMEPAD:
        return None
    gamepad = state.get("gamepad_emulation")
    if not isinstance(gamepad, dict):
        return None
    if gamepad.get("flavor") != "dualsense":
        return None
    if gamepad.get("degraded") is True:
        return VPAD_DEGRADED_TEXT
    motivo = gamepad.get("dedup_motivo")
    if (
        gamepad.get("dedup_ok") is False
        and isinstance(motivo, str)
        and "jogador" in motivo
    ):
        return texto_coop_degradado(jogadores_degradados(motivo))
    return None


# explicação do que NÃO vai acontecer, com o botão de pé.
RECONCILIAR_JOGO_ABERTO_TEXT = (
    "Com o jogo aberto os jogadores voltam, mas a numeração não muda — "
    "evita repintar o controle em uso no meio da partida."
)


def jogo_com_autoridade(state: dict[str, Any] | None) -> bool:
    """O jogo está com a autoridade de exibição AGORA? — função pura.

    Uma fonte só (``state_full.game_signal.authority == "game"``) para as três
    coisas desta aba que dependem dela: o aviso do "Reconciliar jogadores", o
    motivo da divergência de máscara (PONTE-NA-TELA-01) e o ``_jogo_aberto``
    que a aba Perfis lê. É o MESMO critério que o daemon usa no gate R-04
    (`subsystems/gamepad._recriacao_bloqueada_por_jogo` → `_autoridade_do_jogo`)
    e no handler de ``identity.renumber``: nunca uma segunda fonte da verdade.

    Sinal ausente/desconhecido devolve ``False`` — sem alarme falso.
    """
    if not isinstance(state, dict):
        return False
    game_signal = state.get("game_signal")
    if not isinstance(game_signal, dict):
        return False
    return bool(game_signal.get("authority") == "game")


def _reconciliar_gate_text(state: dict[str, Any] | None) -> str | None:
    """Aviso do "Reconciliar jogadores"; ``None`` = nada a dizer — função pura
    (padrão ``vpad_degradation_text``/``wrapper_banner_text``).

    Espelha o MESMO critério do handler de ``identity.renumber``
    (``display_authority == 'game'`` via ``state_full.game_signal.
    authority``, lido por `jogo_com_autoridade`) — nunca uma segunda fonte da
    verdade; se o daemon ainda não fiou o sinal (``game_signal`` ausente/
    authority desconhecida), não há aviso (sem alarme falso).
    """
    if not isinstance(state, dict):
        return None
    return RECONCILIAR_JOGO_ABERTO_TEXT if jogo_com_autoridade(state) else None


# O daemon fez o certo, e continua fazendo: `mouse.emulation.restore` RESTAURA a
TEXTO_DESKTOP_SEM_MOUSE: Final[str] = (
    "Você está em \"Controlar o PC\", mas o mouse emulado está desligado — o "
    "controle não move o cursor. Ligue \"Emular mouse\" na aba Navegação."
)

TEXTO_DESKTOP_SEM_TECLADO: Final[str] = (
    "Você está em \"Controlar o PC\", mas o teclado emulado está desligado — o "
    "controle não digita. Ligue \"Emular teclado\" na aba Navegação."
)

TEXTO_DESKTOP_SEM_MOUSE_NEM_TECLADO: Final[str] = (
    "Você está em \"Controlar o PC\", mas o mouse e o teclado emulados estão "
    "desligados — o controle não move o cursor nem digita. Ligue os dois na "
    "aba Navegação."
)


def texto_do_desktop_sem_emulacao(
    state: dict[str, Any] | None,
    *,
    modo_exibido: object = None,
    modo_mudou_agora: bool = False,
) -> str | None:
    """Aviso do "Controlar o PC" calado; ``None`` = nada a dizer — função pura.

    MODO-QUE-NAO-CONTROLA-01. Mesmo desenho de `vpad_degradation_text` e
    `wrapper_banner_text`: quem decide é uma função sem GTK e sem daemon, e a
    aba só escreve o que ela devolve.

    As três condições, e cada uma existe para não acender alarme falso:

    1. **o modo VIGENTE é desktop** (`mode_of_state`) — em "Jogar pelo Hefesto"
       e no Modo Nativo o mouse está desligado pela exclusão mútua do daemon, o
       que é o desenho normal e não tem nada de errado;
    2. **o modo EXIBIDO também é desktop** — com uma escolha pendente de SAIR do
       desktop, avisar sobre o modo que ela está deixando responderia a pergunta
       errada (a caixa mostra a escolha do usuário, não o vigente: AGORA-E-DEPOIS-01);
    3. **o modo não mudou NESTE tique** — a transição para desktop dispara três
       IPCs e o `mouse.emulation.restore` é o ÚLTIMO deles. Julgar a emulação no
       mesmo tique em que o modo mudou acenderia o aviso enquanto a cura ainda
       está em voo, e ele sumiria sozinho 2 s depois. Um aviso que pisca é
       ruído; este espera um tique e só fala do que ficou de pé.

    Só o ``False`` LITERAL acende, para mouse e teclado: bloco ausente (daemon
    antigo, payload incompleto) ou chave ausente não viram aviso — a mesma
    disciplina do ``wrapper_used``.

    O teclado entra aqui pela mesma razão que o mouse: "Controlar o PC" promete
    mouse E teclado (`_MODE_DESCRIPTIONS["desktop"]`), e o teclado emulado tem
    interruptor próprio na mesma aba Navegação desde a EMULACAO-NO-JOGO-01. A
    diferença é que o "off" do teclado é SEMPRE gesto do usuário — nenhum caminho
    automático escreve `keyboard_emulation_enabled` (só o boot, lendo o flag
    dela, e o `keyboard.emulation.set`) —, então aqui não há nem a dúvida que o
    mouse tem.
    """
    if not isinstance(state, dict):
        return None
    if modo_mudou_agora:
        return None
    if mode_of_state(state) != MODE_DESKTOP:
        return None
    if modo_exibido is not None and modo_exibido != MODE_DESKTOP:
        return None
    mouse = state.get("mouse_emulation")
    teclado = state.get("keyboard_emulation")
    mouse_off = isinstance(mouse, dict) and mouse.get("enabled") is False
    teclado_off = isinstance(teclado, dict) and teclado.get("enabled") is False
    if mouse_off and teclado_off:
        return TEXTO_DESKTOP_SEM_MOUSE_NEM_TECLADO
    if mouse_off:
        return TEXTO_DESKTOP_SEM_MOUSE
    if teclado_off:
        return TEXTO_DESKTOP_SEM_TECLADO
    return None


#    DualSense. O gate R-04 do daemon (`_recriacao_bloqueada_por_jogo`) tinha
#    cai para False e `mode_of_state` chama isso de Controlar o PC — a aba

_COR_OK = "#50fa7b"
_COR_AVISO = "#ffb86c"

#: features do DualSense".
PONTE_PREFIXO = "Ponte com o jogo: "

#: explicação") do `PONTE_PREFIXO` e do detector de janela da aba Sistema.
DIVERGENCIA_PREFIXO = "Sua escolha: "


def _escapar(texto: object) -> str:
    """Escapa markup Pango. Os rótulos de máscara são literais, mas o"""
    return (
        str(texto)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def mascara_viva(state: dict[str, Any] | None) -> str | None:
    """A máscara que o gamepad virtual VIVO está usando; ``None`` = não sei.

    Duas fontes, nesta ordem:

    1. um campo explícito do daemon, se ele existir. A leitura é por
       ``getattr``/``get`` tolerante porque a lane do daemon publica esse campo
       em paralelo a esta: com um daemon que ainda não o traz, a função
       simplesmente cai no item 2 em vez de estourar;
    2. o ``backend``, que já existe e já é publicado. ``backend == "uhid"``
       implica máscara DualSense e não pode ser outra coisa: o
       `virtual_pad._try_uhid` recusa o uhid para Xbox de saída ("Xbox não é
       trabalho do uhid" — o `hid_playstation` só faz bind em produto Sony).

    ``backend == "uinput"`` é AMBÍGUO de propósito (Xbox normal ou DualSense
    degradado usam o mesmo backend) e devolve ``None``: dizer "não sei" é o
    comportamento honesto, e quem chama trata o ``None`` como "sem divergência
    a afirmar". Enquanto o campo explícito não existir, a divergência é medida
    contra `gamepad_emulation.flavor` — que serve, porque o daemon só grava
    `config.gamepad_flavor` DEPOIS de o vpad novo nascer
    (`subsystems/gamepad.py:1576`); uma troca recusada pelo gate volta com a
    máscara antiga no payload.
    """
    if not isinstance(state, dict):
        return None
    gamepad = state.get("gamepad_emulation")
    if not isinstance(gamepad, dict):
        return None
    for chave in ("flavor_vivo", "live_flavor", "flavor_ativo"):
        valor = gamepad.get(chave)
        if isinstance(valor, str) and valor:
            return valor
    if gamepad.get("backend") == "uhid":
        return "dualsense"
    return None


def mascara_do_aparelho(state: dict[str, Any] | None) -> str | None:
    """A máscara que o JOGO vê agora; ``None`` = não sei (offline/sem vpad)."""
    viva = mascara_viva(state)
    if viva:
        return viva
    if not isinstance(state, dict):
        return None
    gamepad = state.get("gamepad_emulation")
    if not isinstance(gamepad, dict):
        return None
    valor = gamepad.get("flavor")
    return valor if isinstance(valor, str) and valor else None


FONTE_GESTO_DELA: Final[str] = "gesto"
FONTE_PERFIL: Final[str] = "perfil"

DIVERGENCIA_DO_PERFIL_PREFIXO: Final[str] = "O perfil ativo: "


def mascara_divergente_do_daemon(
    state: dict[str, Any] | None,
) -> dict[str, Any] | None:
    """A divergência que o daemon apontou para o jogo EM CENA; ``None`` se não há."""
    if not isinstance(state, dict):
        return None
    gamepad = state.get("gamepad_emulation")
    if not isinstance(gamepad, dict):
        return None
    alarme = gamepad.get("mascara_divergente")
    return alarme if isinstance(alarme, dict) and alarme else None


def texto_da_divergencia(
    escolhida: object,
    no_aparelho: object,
    *,
    jogo_aberto: bool,
    fonte: object = FONTE_GESTO_DELA,
    perfil: object = None,
) -> str | None:
    """A frase da divergência entre o que o usuário escolheu e o que o jogo vê."""
    if not isinstance(escolhida, str) or not escolhida:
        return None
    if not isinstance(no_aparelho, str) or not no_aparelho:
        return None
    if escolhida == no_aparelho:
        return None
    quero = _escapar(_flavor_label(escolhida))
    tenho = _escapar(_flavor_label(no_aparelho))
    if fonte == FONTE_PERFIL:
        nome = _escapar(perfil) if isinstance(perfil, str) and perfil else None
        quem = f"o perfil “{nome}” pede" if nome else "o perfil ativo pede"
        prefixo = DIVERGENCIA_DO_PERFIL_PREFIXO
    else:
        quem = "você escolheu"
        prefixo = DIVERGENCIA_PREFIXO
    if jogo_aberto:
        return (
            prefixo
            + f'<span foreground="{_COR_AVISO}">ainda não chegou ao '
            f"aparelho</span> — {quem} {quero}; o jogo aberto ainda vê "
            f"{tenho}. Trocar agora arrancaria o controle do jogo no meio da "
            "partida, então a escolha vale quando o jogo fechar e abrir "
            "de novo."
        )
    return (
        prefixo
        + f'<span foreground="{_COR_AVISO}">não chegou ao aparelho</span> — '
        f"{quem} {quero}; o Hefesto está com {tenho}. Escolha de novo."
    )


def controles_na_mesa(state: dict[str, Any] | None) -> int:
    """Quantos controles CONECTADOS o daemon reporta — função pura."""
    if not isinstance(state, dict):
        return 0
    entradas = state.get("controllers") or []
    return len(
        [c for c in entradas if isinstance(c, dict) and c.get("connected")]
    )


def texto_da_ponte(state: dict[str, Any] | None) -> str:
    """Markup da linha "Ponte com o jogo" — função pura, voz da aba Sistema.

    Responde a pergunta que a janela inteira não respondia: **por onde o jogo
    está recebendo o controle agora?** A ordem das perguntas é a ordem em que
    uma resposta invalida a seguinte:

    1. sem daemon não há o que afirmar (mesma disciplina do `autoswitch_lock_
       text`: offline é "não sei", nunca "nenhuma");
    2. Modo Nativo — o físico vai para o jogo e o Hefesto não está no caminho;
    3. gamepad do Hefesto, dizendo QUAL máscara o jogo vê — e, com a mesa
       vazia, dizendo que a ponte está de pé e sem quem a atravesse;
    4. nenhuma — e aí a frase aponta o botão que constrói uma.

    ERAM CINCO, e a segunda saiu — I6, ramo 2, 25/08/2026
    -----------------------------------------------------

    A pergunta que saiu era *"exceção de Steam Input com o vpad suspenso"*, e a
    frase de produto dizia: *"pelo Steam Input — neste jogo a Steam entrega os botões,
    e o Hefesto segue cuidando dos gatilhos, da cor e da vibração."* Ela nunca
    apareceu na tela, e não pode voltar como estava. Três medições, nesta ordem:

    1. **A condição é inalcançável** — `VPAD-SUSPENSO-MORTO-01`/E1, MEDIDO em
       25/08/2026: `daemon._steam_input_vpad_suspenso` só anda para `False`
       desde o commit `d8022ea` (09/08/2026), e esta era uma das CINCO leituras
       de produção de um valor impossível. O flag e as cinco leituras saíram
       em 02/10/2026 (O-CODIGO-SEM-CHAMADOR-LIGA-OU-SAI-01).
    2. **Trocar a condição por `excecao_ativa` sozinho — a saída recomendada
       para o PAR — publicaria aqui uma frase que a medição derruba.** Desde a
       `ESCONDER-EM-VEZ-DE-SAIR-01` (09/08/2026, decisão de produto: *a allowlist do
       Steam Input NÃO tira o Hefesto da frente*), a exceção **esconde o
       físico** (`esconder_o_fisico_para_o_jogo`) e **mantém o vpad de pé**. Ou
       seja: na exceção quem alimenta o jogo continua sendo o gamepad do
       Hefesto — o oposto do que a frase dizia.
    3. **E há medição em jogo, não só leitura de código** —
       `docs/protocol/pilha-steam-input-xpad-sdl.md`, §2.4-bis, MEDIDO em
       11/08/2026 com um appid da allowlist DO USUÁRIO em sessão: **zero espelhos**
       da Steam no sistema, os dois vpads do Hefesto de pé, quatro controles
       com jogador e vibração, e o aceite de produto. A Steam não estava entregando
       botão nenhum.

    Logo, com a exceção ativa, a resposta verdadeira é a da terceira pergunta —
    que é a que a aba já dá. **Silêncio aqui não é buraco:** quem tem a fita da
    exceção de Steam Input é a aba Emulação (`markup_status_steam_input`), e é
    lá que ela é nomeada.

    O que fica em aberto, e é DO USUÁRIO: se a Início deve NOMEAR a exceção (algo
    como "…e a Steam está no meio neste jogo"). É texto novo na primeira tela,
    e texto de tela é palavra de produto — PROVA-DE-TELA-01.
    """
    if not isinstance(state, dict):
        return PONTE_PREFIXO + "não sei — o Hefesto está desligado."
    if state.get("native_mode"):
        return (
            PONTE_PREFIXO
            + f'<span foreground="{_COR_OK}">direto (Sony)</span> — o jogo fala '
            "com o DualSense sem o Hefesto no meio."
        )
    gamepad = state.get("gamepad_emulation")
    if isinstance(gamepad, dict) and gamepad.get("enabled"):
        # atravesse. MEDIDO na bancada de 23/08 com ZERO DualSense na casa: o
        if not controles_na_mesa(state):
            return (
                PONTE_PREFIXO
                + f'<span foreground="{_COR_AVISO}">de pé, e vazia</span> — o '
                "gamepad do Hefesto está montado, e não há nenhum controle "
                "ligado para alimentá-lo. Ligue um controle para o jogo "
                "receber alguma coisa."
            )
        no_aparelho = mascara_do_aparelho(state)
        visto = (
            _escapar(_flavor_label(no_aparelho)) if no_aparelho else "um controle"
        )
        return (
            PONTE_PREFIXO
            + f'<span foreground="{_COR_OK}">pelo Hefesto</span> — o jogo '
            f"recebe o controle do gamepad do Hefesto, e o vê como {visto}."
        )
    return (
        PONTE_PREFIXO
        + f'<span foreground="{_COR_AVISO}">nenhuma</span> — nenhum jogo está '
        'recebendo controle do Hefesto. Escolha "Jogar pelo Hefesto" para o '
        "jogo ver um controle."
    )


#: minúsculo. Escreva: Cabo ou BT"*; <!-- noqa-acento: citação literal -->
#: existia para escolher uma. O usuário escolheu.
_PALAVRA_DO_TRANSPORTE: Final[dict[str, str]] = {
    "usb": "USB",
    "cabo": "USB",
    "bt": "BT",
    "bluetooth": "BT",
    "radio": "BT",
    "rádio": "BT",
}

PALAVRA_DE_TRANSPORTE_DESCONHECIDO: Final[str] = "não sei por onde"


def palavra_do_transporte(transporte: object) -> str:
    """O transporte na língua do mapa de canais — função pura (I9)."""
    if transporte is None or transporte == "":
        return PALAVRA_DE_TRANSPORTE_DESCONHECIDO
    bruto = str(transporte).strip()
    return _PALAVRA_DO_TRANSPORTE.get(bruto.lower(), bruto)


#:    bancada em 25/08/2026: o `hide` do broker age em UMA superfície
#: CLASSE DE TELA: ESTRUTURAL — frase reescrita, e um hover onde não havia.
AVISO_DE_GRAB_LINHA: Final[str] = "O jogo pode receber cada botão duas vezes"

AVISO_DE_GRAB_PORQUE: Final[str] = (
    "Outro programa pegou este controle antes e não solta, então o Hefesto não "
    "conseguiu ficar com ele só para si. Enquanto isso durar, o jogo pode "
    "enxergar o controle físico E o do Hefesto ao mesmo tempo. O Hefesto tenta "
    "de novo sozinho a cada 2 segundos; se o aviso não sair, feche os outros "
    "programas que usam controle e ligue o Hefesto de novo."
)


def aviso_de_grab(
    grab_state: object, *, is_primary: bool, gamepad_on: bool
) -> tuple[str, str] | None:
    """A linha e o porquê do aviso de duplicação — função pura (I9).

    Devolve ``(linha, porquê)`` ou ``None`` quando não há o que avisar. A
    CONDIÇÃO mora aqui junto do texto de propósito: ela é a parte que já estava
    certa (`is_primary and gamepad_on and grab_state == "failed"`) e tirá-la do
    meio do montador de widgets é o que torna a frase testável sem GTK.

    Só ``"failed"`` acende. ``"pending"`` é o estado de quem ainda não abriu o
    dispositivo — acender ali seria alarme na partida inteira de quem acabou de
    ligar o controle. E o aviso é do PRIMÁRIO com o gamepad de pé: sem gamepad
    do Hefesto no caminho não há segundo dispositivo para dobrar com o físico.
    """
    if not is_primary or not gamepad_on:
        return None
    if grab_state != "failed":
        return None
    return AVISO_DE_GRAB_LINHA, AVISO_DE_GRAB_PORQUE


def _format_external_title(entry: dict[str, Any]) -> str:
    """Título do card de um externo — "Controle 3 — 8BitDo" (I5, 25/08/2026)."""
    from hefesto_dualsense4unix.app.actions.external_controllers import (
        brand_of,
        slot_label,
        slot_of,
    )

    slot = slot_of(entry, 0, 0)
    marca = brand_of(entry)
    return f"Controle {slot_label(slot)} — {marca}"


def _format_external_subtitle(entry: dict[str, Any]) -> str:
    """Linha secundária do card de um externo, no MESMO formato do adotado.

    Mesma pontuação e mesmo vocabulário de transporte do card do DualSense — é
    o mesmo frame, e dois dialetos lado a lado é o defeito de forma que a I9
    fecha. A segunda metade diz o que o Hefesto NÃO faz com este aparelho, que
    é a informação que a pessoa procura ao ver um controle que não acende.

    PROVISÓRIO — decisão de produto.
    """
    bus = entry.get("bus")
    return "  ·  ".join([palavra_do_transporte(bus), "o Hefesto só vê"])


def externos_na_mesa(
    state: dict[str, Any] | None, cache: Sequence[dict[str, Any]] = ()
) -> list[dict[str, Any]]:
    """Os controles que o Hefesto VÊ e não adota — I5 (25/08/2026).

    Duas fontes, nesta ordem, e a primeira é a que a foto usa:

    1. ``state_full["external"]``, quando o payload o trouxer. **Medido por
       leitura de código em 25/08/2026: o `daemon.state_full` de HOJE não
       publica essa chave** — ela existe só na resposta de ``controller.list
       {"external": true}``. Isto resolve a hipótese 3 do §2.5 da sprint ("o
       daemon publica `external` quando há um externo na mesa?"): **não
       publica**, e o `external=null` medido na bancada não distinguia as duas
       coisas porque a chave nunca existiu ali. O ramo fica porque é por ele
       que o dublê da foto alimenta a aba, e porque um daemon mais novo que
       passe a publicá-la é atendido sem uma linha a mais;
    2. o inventário que a própria aba pediu ao daemon no tique lento
       (``_maybe_fetch_externos``), que é como a aba Configurações e a aba
       Status já fazem — a enumeração de evdev mais a sonda de holders custa
       10-40 ms e um subprocess, e não pode entrar no caminho quente.

    Lista vazia é "não há" **ou** "ainda não perguntei", e quem chama trata as
    duas do mesmo jeito: não desenha card nenhum. A diferença só importaria
    para acusar ausência, e esta aba não acusa.
    """
    if isinstance(state, dict):
        do_payload = state.get("external")
        if isinstance(do_payload, list):
            return [e for e in do_payload if isinstance(e, dict)]
    return [e for e in (cache or ()) if isinstance(e, dict)]


# acima, e a contagem vem do `daemon.state_full` (campo `player` por controle,


# `tests/unit/test_perfil_salva_tudo_registrar_nao_e_aplicar.py`, por AST, para


def reconciliar_pendente(janela: Any) -> dict[str, str]:
    """A escolha do usuário MENOS o que o daemon já alcançou. Devolve o que sobra."""
    pendente = dict(getattr(janela, "_escolha_pendente", None) or {})
    if "modo" in pendente and pendente["modo"] == getattr(
        janela, "_modo_vigente_do_daemon", None
    ):
        pendente.pop("modo")
    # máscara, o chip «Xbox» com o cartão em DualSense deixava na linha um
    if "caminho" in pendente and pendente["caminho"] == getattr(
        janela, "_caminho_vigente_do_daemon", None
    ):
        pendente.pop("caminho")
    if "mascara" in pendente and pendente["mascara"] == getattr(
        janela, "_mascara_vigente_do_daemon", None
    ):
        pendente.pop("mascara")
    janela._escolha_pendente = pendente or None
    return pendente


__all__ = [
    "DIVERGENCIA_DO_PERFIL_PREFIXO",
    "DIVERGENCIA_PREFIXO",
    "FONTE_GESTO_DELA",
    "FONTE_PERFIL",
    "PALAVRA_DE_TRANSPORTE_DESCONHECIDO",
    "PONTE_PREFIXO",
    "RECONCILIAR_JOGO_ABERTO_TEXT",
    "TEXTO_DESKTOP_SEM_MOUSE",
    "TEXTO_DESKTOP_SEM_MOUSE_NEM_TECLADO",
    "TEXTO_DESKTOP_SEM_TECLADO",
    "TEXTO_DETECTOR_CEGO",
    "TEXTO_EM_PAUSA",
    "VPAD_DEGRADED_TEXT",
    "WRAPPER_MISSING_TEXT",
    "appid_do_jogo_em_foco",
    "aviso_do_wrapper",
    "controles_bt_frageis",
    "controles_na_mesa",
    "ela_ja_respondeu_sobre",
    "externos_na_mesa",
    "jogadores_degradados",
    "jogo_com_autoridade",
    "mascara_divergente_do_daemon",
    "mascara_do_aparelho",
    "mascara_viva",
    "palavra_do_transporte",
    "texto_coop_degradado",
    "texto_da_divergencia",
    "texto_da_pausa",
    "texto_da_ponte",
    "texto_do_cadeado_cego",
    "texto_do_desktop_sem_emulacao",
    "texto_do_radio_fragil",
    "texto_native_bt_fragil",
    "vpad_degradation_text",
    "wrapper_banner_text",
]


def aviso_de_opt_out_antigo(
    state: dict[str, Any] | None, *, opt_out: bool, conectados: int
) -> str | None:
    """O produto está inerte por uma escolha ANTIGA dela. ``None`` = nada a dizer."""
    if not isinstance(state, dict) or not opt_out or conectados < 1:
        return None
    if state.get("native_mode"):
        return None
    gamepad = state.get("gamepad_emulation")
    if isinstance(gamepad, dict) and gamepad.get("enabled"):
        return None
    return (
        "O controle está em “Controlar o PC” porque a emulação foi desligada "
        "numa sessão anterior, e essa escolha vale até você mudá-la. Enquanto "
        "estiver assim, o giroscópio e a vibração não chegam a jogo nenhum — "
        "escolha “Jogar pelo Hefesto” ou “Conexão Nativa (Sony)” aqui em cima."
    )
