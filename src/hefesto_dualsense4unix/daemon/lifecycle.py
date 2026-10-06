"""Ciclo de vida do daemon: orquestrador slim (ADR-015)."""
from __future__ import annotations

import asyncio
import contextlib
import inspect
import os
import signal
import threading
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Any, Final, Literal, cast, get_args

from hefesto_dualsense4unix.core.controller import ControllerState, IController
from hefesto_dualsense4unix.core.ds_output_report import (
    SAIDA_L_FONE_R_ALTO_FALANTE,
    SAIDA_SO_NO_ALTO_FALANTE,
)
from hefesto_dualsense4unix.core.events import EventBus, EventTopic
from hefesto_dualsense4unix.daemon.battery_journal import (
    INTERVALO_SONDA_S,
    diario_da_bateria,
    registrar_queda_da_bateria,
)
from hefesto_dualsense4unix.daemon.protocols import GravaOModo, PortaQueGrava
from hefesto_dualsense4unix.daemon.state_store import StateStore
from hefesto_dualsense4unix.daemon.subsystems.gamepad import (
    EMU_BLOQUEADO_POR_JOGO,
    OrigemEmulacao,
    reconciliar_as_mascaras,
)
from hefesto_dualsense4unix.daemon.subsystems.poll import (
    BATTERY_DEBOUNCE_SEC,
    BATTERY_DELTA_THRESHOLD_PCT,
    BATTERY_MIN_INTERVAL_SEC,
    BatteryDebouncer,
)
from hefesto_dualsense4unix.daemon.subsystems.rumble import (
    AUTO_DEBOUNCE_SEC,
    RUMBLE_POLICY_MULT,
    escrever_rumble_no_dono,
    soltar_os_que_vibram,
)
from hefesto_dualsense4unix.utils.logging_config import get_logger
from hefesto_dualsense4unix.utils.maquina import MaquinaConfig

logger = get_logger(__name__)

DEFAULT_POLL_HZ = 60

INPUT_GRACE_SEC: float = 0.3

EVDEV_WATCHDOG_SEC: float = 2.0

GRAB_RECONCILE_SEC: float = 2.0

EXTERNAL_TICK_TIMEOUT_SEC: float = 10.0

EXTERNAL_TICK_MAX_TIMEOUTS: int = 2


RumblePolicy = Literal["economia", "balanceado", "max", "auto", "custom"]
RUMBLE_POLICIES: tuple[str, ...] = get_args(RumblePolicy)


def _caminho_da_secao(mode: Any) -> str | None:
    """O caminho que a seção `mode` de um perfil pede, ou ``None`` = sem opinião."""
    from hefesto_dualsense4unix.integrations.virtual_pad import normalizar_caminho

    return normalizar_caminho(getattr(mode, "caminho", None))


def _caminho_vivo(daemon: Any) -> str | None:
    """O caminho em que o vpad do P1 está AGORA — ``None`` sem vpad."""
    from hefesto_dualsense4unix.integrations.virtual_pad import caminho_resolvido

    device = getattr(daemon, "_gamepad_device", None)
    if device is None:
        return None
    return caminho_resolvido(
        getattr(getattr(daemon, "config", None), "gamepad_caminho", None),
        getattr(device, "flavor", None),
    )


def _caminho_do_dono(daemon: Any, motivo: str) -> str | None:
    """O modo da sessão para um restart que não escolhe modo, e o nome dele."""
    from hefesto_dualsense4unix.daemon.subsystems.gamepad import nomear_o_restart

    return nomear_o_restart(daemon, motivo)


def _velocidades_ou_as_da_sessao(
    speed: int | None, scroll: int | None
) -> tuple[int | None, int | None]:
    """``(speed, scroll_speed)`` do perfil; o que faltar sai do computador, e depois da sessão."""
    from hefesto_dualsense4unix.utils.session import load_mouse_preference

    if speed is None or scroll is None:
        from hefesto_dualsense4unix.profiles.o_padrao_do_computador import (
            velocidades_do_computador,
        )

        speed_pc, scroll_pc = velocidades_do_computador()
        speed = speed if speed is not None else speed_pc
        scroll = scroll if scroll is not None else scroll_pc
    if speed is None or scroll is None:
        _pref, speed_flag, scroll_flag = load_mouse_preference()
        speed = speed if speed is not None else speed_flag
        scroll = scroll if scroll is not None else scroll_flag
    return speed, scroll


def _o_perfil_diz_navegacao(profile: Any) -> bool:
    """O perfil tem a seção `mode` com ``kind == "desktop"``? Nunca levanta.

    O-MOUSE-SEGUE-A-NAVEGACAO-01 (29/09/2026): é o perfil que tem autoridade
    sobre o liga/desliga do mouse na ativação (`Daemon.apply_profile_mouse`) e
    que liga o mouse mesmo sem a seção `mouse` (`ProfileManager.apply_emulation`).
    """
    return getattr(getattr(profile, "mode", None), "kind", None) == "desktop"


def _o_modo_do_perfil_do_boot(
    store: Any = None, *, appid_em_cena: int | None = None,
) -> tuple[str | None, str | None, str | None]:
    """``(caminho, máscara, nome)`` do perfil que o boot restaura, ou vazios."""
    from hefesto_dualsense4unix.daemon.connection import perfil_que_o_boot_restaura
    from hefesto_dualsense4unix.integrations.uinput_gamepad import resolver_flavor

    try:
        perfil = perfil_que_o_boot_restaura(store, appid_em_cena=appid_em_cena)
    except Exception:
        return None, None, None
    if perfil is None:
        return None, None, None
    nome = getattr(perfil, "name", None)
    mode = getattr(perfil, "mode", None)
    if getattr(mode, "kind", None) != "gamepad":
        return None, None, nome
    bruta = getattr(mode, "gamepad_flavor", None)
    mascara = resolver_flavor(bruta) if bruta else None
    return _caminho_da_secao(mode), mascara, nome


def _o_appid_da_evidencia(inputs: dict[str, Any]) -> int | None:
    """O appid do jogo pela evidência do sinal: o marcador vivo, ou o processo."""
    from hefesto_dualsense4unix.daemon.launch_env import wrapper_game_running

    try:
        marker = inputs.get("marker")
        if marker is not None and wrapper_game_running(
            marker=marker,
            exit_marker=inputs.get("exit_marker"),
            pid_alive=bool(inputs.get("marker_pid_alive")),
            marker_pid=inputs.get("marker_pid"),
            exit_pid=inputs.get("exit_pid"),
            now=float(inputs.get("now") or time.time()),
        ):
            return int(marker[0])
        vivo = inputs.get("appid_de_jogo_vivo")
        if isinstance(vivo, int) and vivo > 0:
            return vivo
    except Exception:
        return None
    return None


def _soltar_o_pad_do_lancamento(daemon: Any) -> None:
    """O jogo devolveu a autoridade: a trava do lançamento acaba aqui."""
    travado = getattr(daemon, "_pad_travado_pelo_lancamento", None)
    if travado is None:
        return
    with contextlib.suppress(Exception):
        daemon._pad_travado_pelo_lancamento = None
    logger.info("pad_do_lancamento_destravado", motivo="o_jogo_devolveu_a_autoridade",
                appid=travado[0] if isinstance(travado, tuple) and travado else None)


def _mascara_da_maquina() -> str:
    """A máscara que O usuário escolheu para a máquina, ou a de fábrica da sessão.

    A-MASCARA-SEGUE-O-ESTADO-01 (25/09/2026). É o que o jogo sem opinião de
    máscara veste. O flag só é escrito por gesto do usuário que diz a máscara (ponto
    2 da MASCARA-CONTAGIO-01), então é a escolha do usuário e nunca a de um jogo.
    Sem flag, vale o `DaemonConfig.gamepad_flavor` (`dualsense`), e não o
    `normalize_flavor(None)`: o `DEFAULT_FLAVOR` daquele módulo é o `xbox`
    legado, e foi medindo que isso apareceu. Lido do disco a cada ativação,
    para um gesto novo dela valer no perfil seguinte sem reiniciar nada.
    """
    from hefesto_dualsense4unix.integrations.uinput_gamepad import resolver_flavor
    from hefesto_dualsense4unix.utils.session import load_gamepad_emulation

    try:
        _ligado, do_disco = load_gamepad_emulation()
    except Exception:
        do_disco = None
    escolhida = resolver_flavor(do_disco) if do_disco else None
    return escolhida or DaemonConfig.gamepad_flavor


def _a_maquina_deixa_o_pad_ligado() -> bool:
    """A preferência dela, no disco, é o pad virtual LIGADO? Nunca levanta."""
    from hefesto_dualsense4unix.utils.session import load_gamepad_preference

    try:
        ligado, _flavor = load_gamepad_preference()
    except Exception:
        return False
    return ligado is True


def _o_ramo_do_pad(
    daemon: Any, mode: Any | None, *, profile: Any | None, origin: str
) -> str:
    """O pad de pé no caminho e na máscara da seção — `None` é a da máquina."""
    if daemon._native_mode:
        daemon.set_native_mode(False, reapply=False, origin="profile")
    gamepad_on = (
        daemon.config.gamepad_emulation_enabled
        and daemon._gamepad_device is not None
    )
    flavor = getattr(mode, "gamepad_flavor", None)
    flavor_do_jogo = flavor if flavor is not None else _mascara_da_maquina()
    flavor_atual = getattr(daemon._gamepad_device, "flavor", None)
    caminho = _caminho_da_secao(mode)
    adiada_por_jogo = False
    if (
        not gamepad_on
        or flavor_do_jogo != _mascara_da_sessao(daemon)
        or _o_p1_vestiria(daemon, flavor_do_jogo) != flavor_atual
        or (caminho is not None and caminho != _caminho_vivo(daemon))
        or (caminho is None and getattr(daemon.config, "gamepad_caminho", None))
    ):
        adiada_por_jogo = daemon._pedir_mascara_do_perfil(
            flavor_do_jogo,
            profile=profile,
            origin=origin,
            **({"caminho": caminho} if caminho is not None else {}),
        )
    else:
        daemon._reavaliar_mascara_adiada(flavor_atual)
    return ADIADO_JOGO_ABERTO if adiada_por_jogo else APLICADO


def _mascara_da_sessao(daemon: Any) -> str:
    """A máscara do jogo que a sessão vale agora (a que os sem cartão herdam)."""
    from hefesto_dualsense4unix.integrations.uinput_gamepad import resolver_flavor

    vale = getattr(getattr(daemon, "config", None), "gamepad_flavor", None)
    return (resolver_flavor(vale) if vale else None) or DaemonConfig.gamepad_flavor


def _o_p1_vestiria(daemon: Any, flavor_do_jogo: str) -> str:
    """A máscara que o boneco do P1 vestiria com `flavor_do_jogo`, cartão incluído."""
    from hefesto_dualsense4unix.daemon.subsystems.external_mask import mascara_efetiva
    from hefesto_dualsense4unix.daemon.subsystems.gamepad import primary_identity

    return mascara_efetiva(primary_identity(daemon), flavor_do_jogo)


def _canal_mudaria(daemon: Any, caminho: str | None) -> bool:
    """Pedir `caminho` agora trocaria o CANAL do vpad do P1 (uhid ↔ uinput)?"""
    from hefesto_dualsense4unix.integrations.virtual_pad import (
        caminho_do_vpad,
        quer_uhid,
    )

    device = getattr(daemon, "_gamepad_device", None)
    if device is None or caminho is None:
        return False
    mascara = getattr(device, "flavor", None)
    return quer_uhid(caminho_do_vpad(device), mascara) != quer_uhid(caminho, mascara)


@dataclass
class DaemonConfig:
    poll_hz: int = DEFAULT_POLL_HZ
    auto_reconnect: bool = True
    reconnect_backoff_sec: float = 2.0
    ipc_enabled: bool = True
    udp_enabled: bool = True
    udp_host: str = "127.0.0.1"
    udp_port: int = 6969
    autoswitch_enabled: bool = True
    mouse_emulation_enabled: bool = False
    mouse_speed: int = 6
    mouse_scroll_speed: int = 1
    gamepad_emulation_enabled: bool = False
    # vpad é DualSense Edge por arquitetura (UHID-04) e a máscara dualsense
    gamepad_flavor: str = "dualsense"
    # dela: `"dualsense"` (o canal próprio do DualSense, vpad uhid) ou `"xbox"`
    gamepad_caminho: str | None = None
    gamepad_caminho_global: str | None = None
    coop_enabled: bool = True
    # do DualSense.
    # `keyboard_emulation.flag` persiste a escolha do usuário (lida no boot, abaixo em
    keyboard_emulation_enabled: bool = True
    ps_button_action: Literal["steam", "none", "custom"] = "steam"
    ps_button_command: list[str] = field(default_factory=list)
    ps_long_press_ms: int = 0
    rumble_active: tuple[int, int] | None = None
    #: MESA-CHEIA-05 (E0) — o DONO do par acima: o MAC do controle em que ele
    #: foi fixado, ou None para "a mesa inteira" (o alvo era "Todos", ou o
    #: alvo não tem MAC estável).
    #:
    #: **Por que o par não bastava.** `rumble_active` é um valor só para o
    #: daemon inteiro e o destino dele era o `_output_target_key` do backend —
    #: um ponteiro MUTÁVEL. Ela fixava 160/220 no Controle 2, trocava o seletor
    #: para o 3 por outro motivo qualquer e, 200 ms depois, o `reassert_rumble`
    #: marretava o Controle 3 com o valor do 2: o par fixado MIGRAVA de dono
    #: por um gesto que não fala de vibração.
    #:
    #: Guardar o endereço junto do valor é o que faz o reassert reescrever
    #: NAQUELE controle (via `set_rumble_for`, a rota por MAC que já existia e
    #: só o co-op e o force-feedback usavam). Isto NÃO é a D-4: a intensidade
    #: continua sendo uma só para a máquina — o que deixa de acontecer é a
    #: migração de dono.
    rumble_active_uniq: str | None = None
    #: QUANDO ALGUÉM DISSE "AINDA ESTOU SEGURANDO" — A-TELA-QUE-TRAVA-02,
    #: 15/09/2026. `monotonic` do último `rumble.set`/`rumble.stop`, ou `None`.
    #:
    #: Passado `subsystems/rumble.TETO_DO_RUMBLE_FIXADO_S` sem um carimbo novo, o
    #: `reassert_rumble` devolve os motores ao JOGO. É a rede para a janela que
    #: MORRE com o "Testar" ligado — até 15/09 isso deixava o jogo sem vibração
    #: até ela reabrir a aba Vibração e clicar em "Parar", e nada na tela dizia
    #: por quê, porque a tela já não estava lá.
    #:
    #: Quem rebate é `interface/pacotes/a05_vibracao._bater_o_coracao_do_teste`,
    #: a cada 1 s enquanto a janela vive. A ordem de produto: *"o testar e parar é
    #: sobre o teste naquele momento isso nao interfere in game"*  (noqa-acento: citação literal)
    rumble_active_em: float | None = None
    #: O par fixado de CADA controle, `{dono: (weak, strong, carimbo)}` (o `None` é a mesa
    #: inteira). `rumble_active`, `rumble_active_uniq` e `rumble_active_em` são o resumo
    #: dele (o par mais recente); quem escreve é `subsystems/rumble.pares_fixados`.
    rumble_fixados: dict[str | None, tuple[int, int, float | None]] = field(
        default_factory=dict
    )
    #: MESA-CHEIA-05 (E0, terceira rodada) — o controle que está vibrando POR
    #: NOSSA CONTA neste instante, ou None quando nenhum está.
    #:
    #: **Por que o dono não bastava.** Guardar o endereço fez o par parar de
    #: migrar — mas a mudança de dono passou a ABANDONAR quem vibrava. Medido
    #: em 14/08 contra `git archive HEAD`, com os quatro controles: ela fixa
    #: 160/220 no Controle 2, move o seletor para o 3 e clica «Parar» (ou
    #: aplica outro par). Nos dois mundos os zeros vão para o 3 e o 2 continua
    #: em 220/160 — mas no HEAD o reassert seguia o seletor, e **voltar o
    #: seletor ao 2 o silenciava**; com o dono congelado, voltar o seletor
    #: deixou de significar coisa alguma e o 2 vibra para sempre.
    #:
    rumble_dono_vibrando: str | None = None
    rumble_policy: RumblePolicy = "balanceado"
    rumble_policy_custom_mult: float = 0.7
    orcamento_da_mesa: Callable[[], str | None] | None = None
    mic_button_toggles_system: bool = True
    bt_mic_uniqs: Callable[[], frozenset[str]] | None = None
    bt_mic_recusados: Callable[[], frozenset[str]] | None = None
    metrics_enabled: bool = False
    metrics_port: int = 9090
    plugins_enabled: bool = False


#: `profile.switch` conta a verdade para a GUI.
APLICADO = "aplicado"
ADIADO_LOCK_MANUAL = "adiado_lock_manual"
IGNORADO_CATCH_ALL = "ignorado_catch_all"
IGNORADO_JANELA_DE_JOGO = "ignorado_janela_de_jogo"


def _a_mascara_dela_sem_o_vazamento(do_disco: object) -> str | None:
    """A máscara dela lida do disco, com o `xbox` do vazamento devolvido.

    MASCARA-CONTAGIO-01, ponto 3, 21/09/2026 — **irmã exata de
    :func:`_a_escolha_dela_sem_o_vazamento`, logo abaixo**, no outro eixo. A
    ordem de 19/09 nomeava os dois: *"sim tudo dualsense, tudo ligado
    mascara dualsense por default mas esse vazamento me preocupa"*.
    <!-- noqa-acento: citação literal -->

    O `gamepad_emulation.flag` da máquina do usuário diz `xbox` — e não por escolha
    do usuário para todos os jogos. Os pontos 1 e 2 desta sprint fecharam as DUAS
    portas que o escreviam sem pedido: o perfil do Future Knight promovendo a
    máscara dele a padrão da máquina, e o chip «Sony DualSense» re-carimbando o
    valor da memória a cada clique. O arquivo ficou com um valor que ninguém
    pediu, e todo controle sem entrada no registro nasce dele.

    **SÓ O VALOR QUE O VAZAMENTO ESCREVE É DEVOLVIDO**, e a assimetria é a
    mesma da irmã: `xbox` é a única máscara que as duas portas carimbavam sem
    ela pedir, e é a que tira giroscópio, acelerômetro e touchpad do jogo. Um
    `dualsense` no arquivo não precisa de conserto — já é o default.

    **E NENHUMA TELA ESCREVE `xbox` AQUI, medido em 21/09.** O chip de modo da
    aba Jogar não manda `flavor` desde MODO-DE-CONEXAO-01 (13/09) e o chip do
    CARTÃO usa `gamepad.mask.set`, que grava no registro por aparelho
    (`controller_masks.json` — os quatro dela em `dualsense`). O único caminho
    intencional é a CLI (`cli/cmd_gamepad.py:53`, com `--flavor`).

    **UMA VEZ, e não a cada boot**, pela marca `MARCA_DA_MASCARA_DEVOLVIDA`
    (O-MODO-XBOX-NAO-E-QUEDA-02, 27/09/2026). Até ali a docstring dizia que a
    volta seguinte lia `dualsense` e não fazia nada, e isso só valia enquanto
    ela não escolhesse Xbox: com a escolha, cada boot a desfazia.
    """
    from hefesto_dualsense4unix.integrations.uinput_gamepad import resolver_flavor
    from hefesto_dualsense4unix.utils.session import (
        MARCA_DA_MASCARA_DEVOLVIDA,
        migracao_ainda_nao_feita,
    )

    lido = resolver_flavor(do_disco) if do_disco else None
    if not migracao_ainda_nao_feita(MARCA_DA_MASCARA_DEVOLVIDA) or lido != "xbox":
        return lido
    with contextlib.suppress(Exception):
        from hefesto_dualsense4unix.utils.session import save_gamepad_emulation

        save_gamepad_emulation(True, "dualsense")
    logger.info(
        "mascara_global_devolvida_ao_default",
        era=lido,
        agora="dualsense",
        origem="desconhecida",
        migracao="única",
    )
    return "dualsense"


def _a_escolha_dela_sem_o_vazamento(
    do_disco: object, origem: str | None = None
) -> str | None:
    """A escolha do usuário lida do disco, com o `xbox` do vazamento devolvido."""
    from hefesto_dualsense4unix.integrations.virtual_pad import (
        CAMINHO_DUALSENSE,
        CAMINHO_XBOX,
        normalizar_caminho,
    )
    from hefesto_dualsense4unix.utils.session import (
        MARCA_DO_CAMINHO_DEVOLVIDO,
        ORIGEM_DA_MIGRACAO_UNICA,
        migracao_ainda_nao_feita,
    )

    lido = normalizar_caminho(do_disco)
    if origem is not None:
        return lido
    if not migracao_ainda_nao_feita(MARCA_DO_CAMINHO_DEVOLVIDO) or lido != CAMINHO_XBOX:
        return lido
    with contextlib.suppress(Exception):
        from hefesto_dualsense4unix.utils.session import save_gamepad_caminho

        save_gamepad_caminho(CAMINHO_DUALSENSE, origem=ORIGEM_DA_MIGRACAO_UNICA)
    logger.info(
        "caminho_global_devolvido_ao_default",
        era=lido,
        agora=CAMINHO_DUALSENSE,
        origem="desconhecida",
        migracao="única",
    )
    return CAMINHO_DUALSENSE
FALHOU = "falhou"

IGNORADO_SEM_CONTROLE = "ignorado_sem_controle"

ADIADO_JOGO_ABERTO = "adiado_jogo_aberto"


@dataclass
class ModoAdiado:
    """Pendência ÚNICA da seção `mode` adiada pelo lock de gesto manual (R-03).

    Sempre SOBRESCRITA, nunca enfileirada: se dois perfis forem ativados dentro
    da mesma janela de lock, quem vale é o último — enfileirar aplicaria um modo
    que já não corresponde ao perfil ativo.

    A variante "não gravar `_current_profile` no autoswitch para ele tentar de
    novo" foi REJEITADA na consolidação da auditoria: com o poll de 2 Hz ela
    faria `_activate` rodar ~60x em 30 s, reescrevendo gatilhos/LEDs e
    `reset_output_overrides` a cada tick — exatamente o flap que o MISC-08
    removeu. Aqui a ativação é commitada normalmente e só o `mode` fica
    pendente, drenado UMA vez pelo `_poll_loop`.

    Por que SÓ o `mode` tem pendência (e mouse/supressão/política de rumble
    apenas REPORTAM o adiamento): `mode` é o eixo que a usuária sente — máscara
    do vpad e co-op, o que faz o jogo funcionar a 4 — e o único cuja perda dura
    a sessão inteira. Um retry por eixo multiplicaria os caminhos assíncronos
    capazes de mexer no estado do controle sem gesto do usuário; os outros três voltam
    a ser avaliados na próxima ativação de perfil, que é barata e frequente.

    Campos:
      - `carimbo_manual` — valor de `_emu_manual_ts` na criação. Se o carimbo
        MUDAR, houve gesto manual NOVO (mais recente que o perfil) e a pendência
        é descartada: a última palavra é de produto, não do perfil de meia hora atrás.
      - `nao_antes_de` — `carimbo_manual + MANUAL_PROFILE_LOCK_SEC`; antes disso
        o lock ainda protege o gesto do usuário.
      - `esperando_jogo` — dedupe do log de espera (o dreno roda a ~1 Hz).
    """

    mode: Any
    profile: Any
    profile_name: str | None
    origin: str
    carimbo_manual: float
    nao_antes_de: float
    esperando_jogo: bool = False


ORIGEM_GAME_SIGNAL = "game_signal"

IGNORADO_SEM_JOGO = "ignorado_sem_jogo"
IGNORADO_GESTO_DELA = "ignorado_gesto_dela"

ORIGEM_EXCLUSAO: Final = "exclusão"

STASH_DA_EXCLUSAO = "exclusão"

IGNORADO_UM_CONTROLE_SO = "ignorado_um_controle_so"



@dataclass
class ModoJogoPadrao:
    """O modo jogo que o SINAL DE JOGO ligou, sem perfil nenhum (MODO-01/B3)."""

    ligou_gamepad: bool
    dono_anterior: str | None
    wm_class: str


@dataclass
class ExclusaoViva:
    """O Modo Nativo que a lista de exclusão ligou (E3), e só ele."""

    chave: str
    ligou_nativo: bool
    dono_anterior: str | None


def exclusao_do_stash(stash: object) -> ExclusaoViva | None:
    """A posse que a exclusão anotou no stash do Modo Nativo, ou None."""
    anotada = stash.get(STASH_DA_EXCLUSAO) if isinstance(stash, dict) else None
    if not isinstance(anotada, dict) or not str(anotada.get("chave") or ""):
        return None
    dono = anotada.get("dono_anterior")
    return ExclusaoViva(
        chave=str(anotada["chave"]),
        ligou_nativo=True,
        dono_anterior=dono if isinstance(dono, str) else None,
    )


@dataclass
class MascaraAdiada:
    """A máscara que o perfil pediu e o gate R-04 recusou (VERDADE-01, 18/08)."""

    flavor: str | None
    profile_name: str | None
    anunciada: bool = False


@dataclass
class Daemon:
    """Orquestrador do daemon. API pública preservada (REFACTOR-LIFECYCLE-01).

    Atributos públicos (mantidos para backcompat de testes):
      controller, bus, store, config, _hotkey_manager, _audio, _mouse_device,
      _ipc_server, _udp_server, _autoswitch, _last_auto_mult, _last_auto_change_at.
    """

    controller: IController
    bus: EventBus = field(default_factory=EventBus)
    store: StateStore = field(default_factory=StateStore)
    config: DaemonConfig = field(default_factory=DaemonConfig)

    _stop_event: asyncio.Event | None = None
    _executor: ThreadPoolExecutor | None = None
    _external_executor: ThreadPoolExecutor | None = None
    _tasks: list[asyncio.Task[Any]] = field(default_factory=list)
    _ipc_server: Any = None
    _udp_server: Any = None
    _autoswitch: Any = None
    _mouse_device: Any = None
    _keyboard_device: Any = None
    _gamepad_device: Any = None
    _motion_reader: Any = None
    _hidraw_broker_client: Any = None
    _hidraw_broker_executor: Any = None
    _coop_manager: Any = None
    _hotkey_manager: Any = None
    _emulation_suppressed: bool = False
    _suppress_manual_ts: float = field(default=float("-inf"))
    _suppress_from_profile: bool = False
    _emu_manual_ts: float = field(default=float("-inf"))
    _mode_pendente: ModoAdiado | None = None
    _mascara_adiada_por_jogo: MascaraAdiada | None = None
    _modo_jogo_padrao: ModoJogoPadrao | None = None
    _exclusao_viva: ExclusaoViva | None = None
    _modo_jogo_padrao_log: str = ""
    _gamepad_multi_log: str = ""
    _profile_selector: Any = None
    # FEAT-NATIVE-MODE-01: Modo Nativo ativo ("release total" do controle). Não
    _native_mode: bool = False
    _native_emu_stash: dict[str, Any] = field(default_factory=dict)
    _nos_do_modo_nativo: set[str] = field(default_factory=set)
    _mode_from_profile: str | None = None
    _rumble_policy_from_profile: bool = False
    _rumble_policy_before_profile: tuple[RumblePolicy, float] | None = None
    _emu_lock: Any = field(default_factory=threading.RLock)
    _audio: Any = None
    _plugins_subsystem: Any = None
    _metrics_subsystem: Any = None
    _bt_mic_subsystem: Any = None
    _alto_falante_subsystem: Any = None
    _conexoes_subsystem: Any = None
    _reconnect_task: asyncio.Task[Any] | None = None
    _last_auto_mult: float = field(default=0.7)
    _last_auto_change_at: float = field(default=0.0)
    _last_rebackend_ts: float = field(default=float("-inf"))
    _input_ready_at: float = field(default=0.0)
    # _poll_loop. Permite que `daemon.state_full` reflita o tick atual em vez
    _last_state: ControllerState | None = None
    # FEAT-KEYBOARD-EMULATOR-01: criados em runtime por start_keyboard_emulation
    _osk_controller: Any = None
    _touchpad_reader: Any = None
    _paused: bool = field(default=False)
    _maquina: MaquinaConfig = field(default_factory=MaquinaConfig)
    # (nome -> erro). Um subsystem quebrado é isolado aqui em vez de derrubar o
    _failed_subsystems: dict[str, str] = field(default_factory=dict)
    identity_registry: Any = None
    external_registry: Any = None
    _external_led_sync: Any = None
    _external_tick_task: asyncio.Task[Any] | None = None
    _external_tick_timeouts: int = 0
    _external_tick_degraded: bool = False
    _external_tick_skipped: int = 0
    _diario_bateria: Any = None
    _external_tick_watch: Any = None
    _game_signal: Any = None
    _appid_da_evidencia: int | None = None
    _registro_de_gatilhos: Any = None
    _sentinela_de_escritor_cru: Any = None
    _cartorio_do_nascimento: Any = None
    _vigia_do_sequestro: Any = None


    async def run(self) -> None:
        """Entry point: subsystems → reconnect_loop em background → wait → shutdown."""
        from hefesto_dualsense4unix.daemon.connection import (
            reconnect_loop,
            shutdown,
        )
        from hefesto_dualsense4unix.daemon.subsystems.hotkey import (
            start_hotkey_manager,
            start_mic_do_jogo,
            start_mic_hotkey,
        )
        from hefesto_dualsense4unix.daemon.subsystems.luz_do_mic import start_luz_do_mic
        from hefesto_dualsense4unix.daemon.subsystems.ouvinte_do_som import (
            start_ouvinte_do_som,
        )

        loop = asyncio.get_running_loop()
        self.bus.bind_loop(loop)
        self._stop_event = asyncio.Event()
        self._executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="hefesto-hid")
        self._external_executor = ThreadPoolExecutor(
            max_workers=1, thread_name_prefix="hefesto-ext"
        )
        self._install_signal_handlers(loop)
        from hefesto_dualsense4unix.utils.session import load_paused_state
        self._paused = load_paused_state()
        from hefesto_dualsense4unix.profiles.loader import o_perfil_de_fora_do_jogo
        from hefesto_dualsense4unix.utils.session import load_freestyle_ligado
        with contextlib.suppress(Exception):
            o_perfil_de_fora_do_jogo()
        self.store.set_freestyle_ligado(load_freestyle_ligado())
        self._carregar_o_modo_nativo()
        from hefesto_dualsense4unix.daemon.subsystems.bt_mic import (
            uniqs_declarados,
            uniqs_recusados,
        )
        from hefesto_dualsense4unix.profiles.o_padrao_do_computador import migrar_uma_vez
        from hefesto_dualsense4unix.utils.maquina import carregar_maquina
        with contextlib.suppress(Exception):
            migrar_uma_vez()
        self._maquina = carregar_maquina()
        # teto de orçamento. A config leva a FONTE, não o valor — o `lambda`
        # fecha sobre `self`, então o rebind de `_maquina` que o
        # `machine.declare` faz no "Aplicar" já vale no cálculo seguinte. Ver o
        self.config.orcamento_da_mesa = lambda: self._maquina.orcamento.teto
        from hefesto_dualsense4unix.profiles.schema import (
            registrar_declaracao_da_mesa,
        )

        registrar_declaracao_da_mesa(lambda: self._maquina)
        if self.config.bt_mic_uniqs is None:
            self.config.bt_mic_uniqs = lambda: uniqs_declarados(self._maquina)
        if self.config.bt_mic_recusados is None:
            self.config.bt_mic_recusados = lambda: uniqs_recusados(self._maquina)
        if self._native_mode:
            self.store.set_native_mode_active(True)
        from hefesto_dualsense4unix.utils.session import load_mouse_emulation
        mouse_on, mouse_speed, mouse_scroll = load_mouse_emulation()
        if mouse_on and not self._native_mode:
            self.config.mouse_emulation_enabled = True
            from hefesto_dualsense4unix.integrations import uinput_mouse as _um

            if mouse_speed is not None:
                self.config.mouse_speed = max(
                    _um.MOUSE_SPEED_MIN, min(_um.MOUSE_SPEED_MAX, int(mouse_speed)))
            if mouse_scroll is not None:
                self.config.mouse_scroll_speed = max(
                    _um.SCROLL_SPEED_MIN, min(_um.SCROLL_SPEED_MAX, int(mouse_scroll)))
        from hefesto_dualsense4unix.utils.session import load_gamepad_emulation
        gp_enabled, gp_flavor = load_gamepad_emulation()
        if gp_enabled and not self._native_mode:
            self.config.gamepad_emulation_enabled = True
            gp_flavor = _a_mascara_dela_sem_o_vazamento(gp_flavor)
            if gp_flavor:
                self.config.gamepad_flavor = gp_flavor
            self.config.mouse_emulation_enabled = False
        from hefesto_dualsense4unix.utils.session import (
            load_gamepad_caminho_com_origem,
        )

        escolha_dela = _a_escolha_dela_sem_o_vazamento(*load_gamepad_caminho_com_origem())
        self.config.gamepad_caminho_global = escolha_dela
        self._caminho_do_boot: str | None = None
        self._wire_game_signal()
        with contextlib.suppress(Exception):
            await self._sync_game_signal()
        if not self._native_mode:
            caminho_do_boot, mascara_do_boot, perfil_do_boot = _o_modo_do_perfil_do_boot(
                self.store, appid_em_cena=self.appid_em_cena
            )
            self._caminho_do_boot = caminho_do_boot
            if mascara_do_boot is not None and self.config.gamepad_emulation_enabled:
                self.config.gamepad_flavor = mascara_do_boot
            if perfil_do_boot is not None:
                logger.info(
                    "modo_do_boot_pelo_perfil",
                    perfil=perfil_do_boot,
                    caminho=caminho_do_boot,
                    mascara=mascara_do_boot,
                )
        self.config.gamepad_caminho = self._caminho_do_boot
        # teclado era o único dos três sem flag em disco, e por isso o único que
        # não tinha como ser desligado). Três valores: `None` = nunca configurada
        # e o default da config vale (compat: continua ligado); `True`/`False` =
        # decisão de produto e vence o default, inclusive um default vindo do env.
        # Best-effort por construção (o load nunca levanta).
        from hefesto_dualsense4unix.utils.session import load_keyboard_preference
        kbd_pref = load_keyboard_preference()
        if kbd_pref is not None:
            self.config.keyboard_emulation_enabled = kbd_pref
        # FEAT-DSX-COOP-LOCAL-01 / LEIGO-01: apaga o opt-out gravado por versão
        # antiga (`coop_disabled.flag`) — one-shot, com marker próprio.
        #
        # COOP-SEM-INTERRUPTOR-01 (06/08/2026): aqui havia também
        # `if load_coop_enabled(): self.config.coop_enabled = True`. Saiu, e a
        # remoção é a entrega, não faxina: com ela, o piso do co-op passa a ter
        # UM dono só (`DaemonConfig.coop_enabled`, agora `True`). Enquanto o
        from hefesto_dualsense4unix.utils.session import migrate_coop_optout

        migrate_coop_optout()
        logger.info("daemon_starting", poll_hz=self.config.poll_hz, paused=self._paused)
        try:
            self._tasks = [asyncio.create_task(self._poll_loop(), name="poll_loop")]
            if self.config.ipc_enabled:
                await self._safe_start("ipc", self._start_ipc)
            if self.config.udp_enabled:
                await self._safe_start("udp", self._start_udp)
            if self.config.autoswitch_enabled:
                await self._safe_start("autoswitch", self._start_autoswitch)
            if self.config.mouse_emulation_enabled:
                await self._safe_start("mouse", self._start_mouse_emulation)
            if self.config.gamepad_emulation_enabled:
                await self._safe_start("gamepad", self._start_gamepad_emulation)
            if self.config.keyboard_emulation_enabled:
                await self._safe_start("keyboard", self._start_keyboard_emulation)
            await self._safe_start("hotkey", lambda: start_hotkey_manager(self))
            await self._safe_start("mic_do_jogo", lambda: start_mic_do_jogo(self))
            if self.config.mic_button_toggles_system:
                await self._safe_start("mic_hotkey", lambda: start_mic_hotkey(self))
            await self._safe_start("luz_do_mic", lambda: start_luz_do_mic(self))
            # PATH ele tenta, falha, espera e tenta de novo, sem derrubar nada.
            #
            # AQUI E NÃO ANTES: ele não é dono de nenhum nó, só observa. Subir
            # cedo faria a primeira leitura pegar o servidor de som antes de o
            # `bt_mic` e o `alto_falante` publicarem os nós deles, e a primeira
            # resposta da tela seria um mundo sem o controle do usuário.
            await self._safe_start(
                "ouvinte_do_som", lambda: start_ouvinte_do_som(self))
            # BT-MIC-REGISTRY-01: ponte de microfone por Bluetooth. O gate de
            # opt-in vive DENTRO do starter (`is_enabled`) — desligado, ele
            # devolve sem instanciar nada. Sobe aqui, ao lado do resto do
            # mundo de microfone e antes dos plugins (código de usuário).
            await self._safe_start("bt_mic", self._start_bt_mic)
            # SOM-FIADO-01: o nó de som por controle. Sobe LOGO DEPOIS do
            # microfone porque as duas metades leem a mesma lista de sysfs, e
            # na ordem inversa o som cai antes do IPC — o mesmo motivo do
            # `bt_mic`, do outro lado do áudio.
            await self._safe_start("alto_falante", self._start_alto_falante)
            # CONEXAO-ZUMBI-01: o vigia do link que conecta e NÃO vira controle. Sobe
            # depois do som porque lê o sysfs e o BlueZ por conta própria, e, na ordem
            # inversa, cai antes do IPC: o último a olhar a mesa não pode ser o primeiro
            # a acordar. Nome ASCII, como o dos irmãos. MOVER-UM-POR-VEZ-01: a central
            # do rádio vem logo depois, e abre o dono do BlueZ no arranque.
            await self._safe_start("conexoes", self._start_conexoes)  # (noqa-acento): nome ASCII
            await self._safe_start("central_do_radio", self._start_central_do_radio)
            await self._safe_start("plugins", self._start_plugins)
            # FEAT-METRICS-01: sobe o servidor de métricas Prometheus (gate
            # interno respeita metrics_enabled). Antes nunca era iniciado —
            # metrics_enabled/metrics_port eram config morta.
            await self._safe_start("metrics", self._start_metrics)
            # FEAT-CONFIG-AUDIT-BOOT-01: valida os perfis no boot e avisa se houver
            # corrompidos (em vez de só pulá-los silenciosamente no fallback).
            self._audit_config_on_boot()
            # FEAT-SYSTEM-AUTOREPAIR-BOOT-01: detecta infra quebrada (udev/WirePlumber)
            # e AVISA o comando de reparo — nunca roda sudo sozinho.
            self._check_system_on_boot()
            # COR-01/COR-03: fiação do registro de identidade + provider de
            # cor automática ANTES do connect inicial — o 1º reconcile do
            # backend (`_reapply_desired`) já resolve com o provider e os
            # slots restaurados do disco (a cor nasce certa no mesmo tick de
            # hotplug, D1). Fora do caminho quente (o load é um read único).
            self._wire_identity_registry()
            self._wire_external_registry()
            self._wire_feature_opener()
            self._wire_exposicao_do_no()
            # PyDualSenseController.connect() trata "No device detected" em
            try:
                await self._run_blocking(self.controller.connect)
                if self.controller.is_connected():
                    transport = self.controller.get_transport()
                    self.bus.publish(
                        EventTopic.CONTROLLER_CONNECTED, {"transport": transport}
                    )
                    logger.info("controller_connected", transport=transport)
                    with contextlib.suppress(Exception):
                        from hefesto_dualsense4unix.daemon.subsystems.gamepad import (
                            upgrade_primary_vpad_to_uhid,
                        )

                        upgrade_primary_vpad_to_uhid(self)
                    from hefesto_dualsense4unix.daemon.connection import (
                        reaplicar_som_em_todos_os_alvos,
                        restore_last_profile,
                    )

                    with contextlib.suppress(Exception):
                        await restore_last_profile(self)
                    # máquina nova é o primeiro caso: o `install.sh` reinicia o
                    with contextlib.suppress(Exception):
                        await reaplicar_som_em_todos_os_alvos(self)
            except Exception as exc:
                logger.warning(
                    "controller_initial_connect_failed",
                    err=str(exc),
                    exc_info=True,
                )
            with contextlib.suppress(Exception):
                from hefesto_dualsense4unix.daemon.launch_env import (
                    materialize_launch_env,
                )

                materialize_launch_env(self)
            self._reconnect_task = asyncio.create_task(
                reconnect_loop(self), name="reconnect_loop"
            )
            self._tasks.append(self._reconnect_task)
            await self._stop_event.wait()
        finally:
            try:
                await shutdown(self)
            finally:
                from hefesto_dualsense4unix.profiles.schema import (
                    registrar_declaracao_da_mesa as _soltar_a_mesa,
                )

                _soltar_a_mesa(None)

    def stop(self) -> None:
        """Sinaliza parada; idempotente."""
        if self._stop_event is not None and not self._stop_event.is_set():
            logger.info("daemon_stop_requested")
            self._stop_event.set()

    def pause(self) -> None:
        """Pausa o despacho de input (FEAT-DAEMON-PAUSE-RESUME-01)."""
        if not self._paused:
            self._paused = True
            from hefesto_dualsense4unix.utils.session import save_paused_state
            save_paused_state(True)
            logger.info("daemon_paused")

    def resume(self) -> None:
        """Retoma o despacho de input. Idempotente."""
        if self._paused:
            self._paused = False
            from hefesto_dualsense4unix.utils.session import save_paused_state
            save_paused_state(False)
            logger.info("daemon_resumed")

    def is_paused(self) -> bool:
        """True se o despacho de input está pausado."""
        return self._paused

    def is_native_mode(self) -> bool:
        """True se o Modo Nativo está ativo (controle solto para o jogo)."""
        return self._native_mode

    def set_native_mode(
        self,
        enabled: bool,
        *,
        reapply: bool = True,
        restore_stash: bool = False,
        origin: Literal["manual", "profile", "exclusão"],
        grava_o_modo: GravaOModo = False,
    ) -> bool:
        """Liga/desliga o Modo Nativo — "release total" do controle.

        FEAT-NATIVE-MODE-01. Para jogar Sackboy & cia com os gatilhos adaptativos
        NATIVOS da Sony (dirigidos pelo jogo), sem o hefesto no meio.

        `enabled=True`: solta o controle — gatilhos Off/Off (o jogo impõe os
        seus), rumble em passthrough (`rumble_active=None`, o hefesto não
        re-asserta), emulação de mouse E gamepad desligada (libera grab/uinput) —
        o ESTADO de emulação é guardado (stash) para restaurar depois. Gate
        `native_mode_active` (autoswitch/hotkey NÃO re-aplicam perfil). O poll
        loop consulta `_native_mode` DIRETAMENTE (não via `pause()`), então o
        dispatch fica congelado independente de pause/resume. Persiste flag+stash.

        `enabled=False`: limpa o gate, zera os motores (o jogo não é mais o dono
        do rumble — HARM-16), re-ativa o último perfil (gatilhos/rumble) e
        restaura a emulação do stash (gamepad tem precedência sobre mouse).
        `reapply=False` quando o chamador NÃO quer o last_profile re-aplicado
        (reversão por perfil: o perfil novo acabou de aplicar triggers/LEDs).
        `restore_stash=True` com `reapply=False` restaura SÓ a emulação do
        stash (BUG-NATIVE-REVERT-DROPS-STASH-01: a reversão por
        perfil-sem-opinião deixava a usuária SEM gamepad ao sair do jogo —
        flagrado ao vivo no Sackboy: alt-tab → nativo off → gamepad nunca
        voltava).

        NOTA (BUG-NATIVE-* da auditoria): o Modo Nativo NÃO usa mais `pause()` —
        gateia o dispatch pelo próprio flag. Assim `daemon.resume` não "des-solta"
        o controle e um pause manual anterior não é pisado.

        `grava_o_modo` (O-MODO-SE-GRAVA-ONDE-ELE-MUDA-01, 29/09/2026): a porta
        da escolha do usuário. LIGANDO, o modo `native` vai ao perfil ativo por
        :meth:`gravar_o_modo_escolhido`, também com o Nativo já ligado (o
        clique no «Desligado» aceso conserta um perfil que divergiu). A saída
        do Nativo não grava: quem grava é o modo que entra.

        Idempotente. Retorna o novo estado.
        """
        from hefesto_dualsense4unix.utils.session import (
            load_gamepad_emulation,
            load_mouse_emulation,
            save_native_mode,
        )

        if origin == "manual":
            self._emu_manual_ts = time.monotonic()
            self._mode_from_profile = None
        if enabled == self._native_mode:
            if enabled and grava_o_modo:
                self.gravar_o_modo_escolhido("native", porta=grava_o_modo)
            return self._native_mode
        if enabled:
            m_on, m_speed, m_scroll = load_mouse_emulation()
            g_on, g_flavor = load_gamepad_emulation()
            self._native_emu_stash = {
                "mouse": [bool(m_on), m_speed, m_scroll],
                "gamepad": [bool(g_on), self._mascara_viva() or g_flavor],
            }
            self._native_mode = True
            self.store.set_native_mode_active(True, origin=origin)
            save_native_mode(True, emu_stash=self._native_emu_stash)
            self._exposicao_do_modo_nativo(True)
            self._release_controller_to_game()
        else:
            self._native_mode = False
            self.store.set_native_mode_active(False)
            save_native_mode(False)
            unmute = getattr(self.controller, "set_output_mute", None)
            if callable(unmute):
                with contextlib.suppress(Exception):
                    unmute(False)
            self._zero_rumble_motors()
            if reapply:
                self._reapply_last_profile()
            if reapply or restore_stash:
                self._restore_emulation_from_stash()
            self._native_emu_stash = {}
            self._exposicao_do_modo_nativo(False)
        if origin == "manual":
            self._mode_from_profile = None
        with contextlib.suppress(Exception):
            from hefesto_dualsense4unix.daemon.launch_env import (
                materialize_launch_env,
            )

            materialize_launch_env(self)
        logger.info("native_mode_changed", native=enabled, origin=origin)
        if enabled and grava_o_modo:
            self.gravar_o_modo_escolhido("native", porta=grava_o_modo)
        return self._native_mode

    def _release_controller_to_game(self) -> None:
        """Neutraliza a saída do hefesto no controle (FEAT-NATIVE-MODE-01)."""
        from hefesto_dualsense4unix.core.trigger_effects import build_from_name

        with contextlib.suppress(Exception):
            off = build_from_name("Off", [])
            self.controller.set_trigger("left", off)
            self.controller.set_trigger("right", off)
        self.config.rumble_active = None
        self.config.rumble_active_uniq = None
        with contextlib.suppress(Exception):
            self.set_mouse_emulation(False, origin="profile")
        with contextlib.suppress(Exception):
            self.set_gamepad_emulation(False, origin="profile")
        mute = getattr(self.controller, "set_output_mute", None)
        if callable(mute):
            with contextlib.suppress(Exception):
                mute(True)

    def reaplicar_se_a_economia_mudou(self, antes: Any) -> bool:
        """Reaplica o perfil ativo quando a economia da declaração mudou."""
        from hefesto_dualsense4unix.profiles.schema import economia_da_declaracao
        if economia_da_declaracao(antes) == economia_da_declaracao(self._maquina):
            return False
        _soltar_o_teto_de_quem_entra(self, antes)
        if self._native_mode:
            return False
        self._reapply_last_profile()
        return True

    def _reapply_last_profile(self) -> None:
        """Re-ativa o perfil corrente ao sair do Modo Nativo (gatilhos/teclado)."""
        from hefesto_dualsense4unix.profiles.loader import NOME_DO_PADRAO
        from hefesto_dualsense4unix.profiles.manager import (
            gerente_do_daemon,
            o_freestyle_manda,
        )
        from hefesto_dualsense4unix.utils.session import a_escolha_dela

        manda = o_freestyle_manda(self.store)
        name = (NOME_DO_PADRAO if manda else None) or self.store.active_profile or (
            a_escolha_dela(freestyle_ligado=manda))
        if not name:
            return
        # `rumble_passthrough_applier`, e applier ausente NÃO levanta: a seção
        # `rumble.passthrough` era ignorada em silêncio, com a ativação
        manager = gerente_do_daemon(
            self,
            store=self.store,
            mode_applier=getattr(self, "_mode_applier_ao_sair_do_nativo", None),
        )
        with contextlib.suppress(Exception):
            manager.activate(name, origin="system")

    def _mode_applier_ao_sair_do_nativo(
        self,
        mode: Any | None,
        *,
        profile: Any | None = None,
        origin: str = "system",
    ) -> str:
        """`apply_profile_mode` menos o `kind="native"` (item 6 da leva de 05/08)."""
        if getattr(mode, "kind", None) == "native":
            logger.info(
                "profile_mode_skipped_saida_do_nativo",
                profile=getattr(profile, "name", None),
            )
            return IGNORADO_GESTO_DELA
        return self.apply_profile_mode(mode, profile=profile, origin=origin)

    def _zero_rumble_motors(self) -> None:
        """Zera os motores ao SAIR de um modo (HARM-16). Thin wrapper."""
        from hefesto_dualsense4unix.daemon.subsystems.rumble import (
            zero_motors_on_mode_exit,
        )

        zero_motors_on_mode_exit(self)

    def _restore_emulation_from_stash(self) -> None:
        """Restaura a emulação capturada antes do Modo Nativo (FEAT-NATIVE-MODE-01)."""
        stash = getattr(self, "_native_emu_stash", None) or {}
        g = stash.get("gamepad") or [False, None]
        m = stash.get("mouse") or [False, None, None]
        if g[0]:
            with contextlib.suppress(Exception):
                self.set_gamepad_emulation(
                    True,
                    g[1],
                    origin="profile",
                    caminho=_caminho_do_dono(self, "saida_do_modo_nativo"),
                )
        elif m[0]:
            with contextlib.suppress(Exception):
                self.set_mouse_emulation(
                    True, m[1], m[2], origin="profile"
                )

    def reload_config(self, new_config: DaemonConfig) -> None:
        """Aplica nova configuração em runtime sem reiniciar o daemon."""
        from hefesto_dualsense4unix.daemon.subsystems.hotkey import (
            start_hotkey_manager,
            stop_hotkey_manager,
        )

        old = self.config
        self.config = new_config
        stop_hotkey_manager(self)
        start_hotkey_manager(self)
        if old.mouse_emulation_enabled != new_config.mouse_emulation_enabled:
            self.set_mouse_emulation(
                new_config.mouse_emulation_enabled,
                speed=new_config.mouse_speed,
                scroll_speed=new_config.mouse_scroll_speed,
                origin="profile",
            )
        if old.keyboard_emulation_enabled != new_config.keyboard_emulation_enabled:
            if new_config.keyboard_emulation_enabled:
                self._start_keyboard_emulation()
            else:
                self._stop_keyboard_emulation()
        keys_changed = [
            k for k in new_config.__dataclass_fields__
            if getattr(old, k, None) != getattr(new_config, k)
        ]
        logger.info("daemon_config_reloaded", keys_changed=keys_changed)

    def set_mouse_emulation(
        self,
        enabled: bool,
        speed: int | None = None,
        scroll_speed: int | None = None,
        *,
        origin: Literal["manual", "profile"],
    ) -> bool:
        """Liga/desliga emulação de mouse e atualiza velocidades. Usado pelo IPC."""
        from hefesto_dualsense4unix.daemon.subsystems.mouse import (
            start_mouse_emulation,
            stop_mouse_emulation,
        )

        if origin == "manual":
            self._emu_manual_ts = time.monotonic()
        from hefesto_dualsense4unix.integrations import uinput_mouse as _um

        if speed is not None:
            self.config.mouse_speed = max(
                _um.MOUSE_SPEED_MIN, min(_um.MOUSE_SPEED_MAX, int(speed)))
        if scroll_speed is not None:
            self.config.mouse_scroll_speed = max(
                _um.SCROLL_SPEED_MIN, min(_um.SCROLL_SPEED_MAX, int(scroll_speed)))
        with self._emu_lock:
            if enabled:
                # FEAT-DSX-GAMEPAD-FLAVOR-01: mútua exclusão — ligar o mouse
                if self._gamepad_device is not None:
                    self._stop_gamepad_emulation()
                ok = start_mouse_emulation(self)
                if ok and self._mouse_device is not None:
                    self._mouse_device.set_speed(
                        mouse_speed=self.config.mouse_speed,
                        scroll_speed=self.config.mouse_scroll_speed,
                    )
                    with contextlib.suppress(Exception):
                        from hefesto_dualsense4unix.utils.session import (
                            save_mouse_emulation,
                        )

                        save_mouse_emulation(
                            True,
                            speed=self.config.mouse_speed,
                            scroll_speed=self.config.mouse_scroll_speed,
                        )
                return ok
            stop_mouse_emulation(self)
            return True

    def restore_mouse_preference(self) -> bool:
        """Aplica a preferência de mouse persistida (HARM-06). Retorna se ligou."""
        from hefesto_dualsense4unix.utils.session import load_mouse_preference

        pref, speed, scroll_speed = load_mouse_preference()
        if pref is None:
            pref = True
        ok = self.set_mouse_emulation(pref, speed, scroll_speed, origin="profile")
        logger.info("mouse_preference_restored", enabled=pref, ok=ok)
        return bool(pref and ok)

    def _perfil_do_arranjo(self) -> Any | None:
        """O perfil ATIVO carregado do disco, ou ``None`` — nunca levanta."""
        try:
            from hefesto_dualsense4unix.profiles.loader import load_profile
            from hefesto_dualsense4unix.profiles.manager import (
                nome_do_perfil_que_grava,
            )

            nome = nome_do_perfil_que_grava(
                getattr(getattr(self, "store", None), "active_profile", None)
            )
            if not nome:
                return None
            from hefesto_dualsense4unix.profiles.o_padrao_do_computador import o_que_vale

            return o_que_vale(load_profile(nome))
        except Exception as exc:
            logger.warning("arranjo_do_desktop_sem_perfil", err=str(exc))
            return None

    def aplicar_o_arranjo_do_desktop(
        self,
        *,
        origin: str = "manual",
        grava_o_modo: GravaOModo = False,
    ) -> dict[str, str]:
        """Carrega no aparelho o que a aba Navegação gravou no perfil ATIVO.

        POINT-AND-CLICK-01 (17/09/2026), pela ordem de produto olhando a aba
        principal: *"o modo point and click é o modo navegação (…) Ele ativa o
        modo configurado lá."* A primeira metade já existia — o chip
        **Navegação** entra em ``MODE_DESKTOP`` e grava ``mode.kind`` no perfil
        desde o MODO-DE-CONEXAO-01. A segunda metade é este método.

        O QUE HAVIA NO LUGAR DELE, e por que era o defeito: o terceiro passo do
        plano era `mouse.emulation.restore`, que chama
        :meth:`restore_mouse_preference` e lê a **flag de sessão no disco** —
        um arquivo único da máquina, que não abre perfil nenhum. Entrar no modo
        descartava, em silêncio, as CINCO coisas que a aba Navegação grava:
        ``mouse``, ``teclado_emulado``, ``key_bindings``, ``button_actions`` e a
        supressão. *A escolha do usuário morria antes do aparelho* — aqui pela
        variante mais cara: o produto perguntava ao arquivo de sessão quando
        devia perguntar ao perfil.

        **NÃO REIMPLEMENTA NADA.** As teclas e os botões vão pelo MESMO
        aplicador que `ProfileManager.activate` já injeta —
        `ProfileManager.apply_keyboard`, `ProfileManager.apply_button_actions`.
        E NÃO chama `activate()`: aquele caminho termina em `profile_switch`, o
        daemon reaplica o perfil INTEIRO, e a barra de luz que ela DESLIGOU
        acende de novo sem nada na tela dizer que ia acontecer (medido em 03/09,
        `a03_gatilhos._gravar_so_o_gatilho`).

        A ORDEM DAS SEÇÕES, e ela não é arbitrária:

        1. **mouse** — ENTRAR NA NAVEGAÇÃO LIGA O MOUSE, pelas duas portas (o
           chip e o PS + R3), com as velocidades do perfil, ou da flag de
           sessão quando o perfil não tem a seção. É a
           D-2909-A-NAVEGACAO-LIGA-O-MOUSE (O-MOUSE-SEGUE-A-NAVEGACAO-01,
           29/09/2026): o chip obedecia ao ``mouse.enabled`` do perfil, e o
           ``{false, 6, 1}`` que ele lia tinha a forma do estado vivo copiado,
           não de uma escolha do usuário — ela entrou no modo «controle vira mouse»
           e o cursor não andou. O PS + R3 ligava pelo socorro
           (``forcar_mouse``), e as duas portas faziam o contrário uma da
           outra. O ``enabled`` do perfil segue valendo na ATIVAÇÃO de um perfil
           que diz Navegação (:meth:`apply_profile_mouse`), e enquanto ela
           estiver na Navegação.
        2. **key_bindings** e **button_actions** — o teclado virtual recebe o
           que o usuário escreveu, com os mesmos `botoes_calados`.
        3. **teclado_emulado** — `schema.resolver_teclado_emulado` é a
           precedência PURA da T14 (24/08/2026), escrita, testada e até hoje
           **sem um único chamador de ativação real**. Ligá-la aqui é o lugar
           certo: é o único ponto do produto em que o teclado emulado tem
           contexto.
        4. **supressão** — ``set_emulation_suppressed(False)``, o que o PS + R3
           já faz. É ela que gateia o dispatch de mouse/teclado no laço do poll:
           sem derrubá-la a ponte sobe MUDA. O ``suppress_desktop_emulation`` do
           perfil **não** é aplicado por aqui — quem responde por ele é
           :meth:`apply_profile_suppression` na ATIVAÇÃO, com o lock manual de
           30 s, e um segundo escritor faria os dois discordarem.

        O TECLADO NÃO É RELIGADO PELA ENTRADA
        (D-2909-A-NAVEGACAO-NAO-RELIGA-O-TECLADO): ele tem uma lista dona dele
        (a «Função do teclado» da aba Navegação), e o «Desativado» dela é
        escolha legítima. O item 3 acima segue a precedência da T14.

        O TECLADO NÃO PERSISTE AQUI (``persist=False``), e é o contrário do que
        o PS + R3 fazia até hoje: gravar o valor RESOLVIDO em
        ``keyboard_emulation.flag`` faria a opinião do PERFIL virar a
        preferência GLOBAL, e a precedência da T14 deixaria de existir na
        ativação seguinte — o perfil que dissesse ``true`` uma vez mandaria para
        sempre, inclusive nos perfis sem opinião.

        QUEM GRAVA O MODO É A PORTA, E NÃO A ORIGEM (O-MODO-SE-GRAVA-ONDE-ELE-
        MUDA-01, 29/09/2026). Com ``grava_o_modo`` (o chip pelo
        ``desktop.arranjo.apply {origin: manual}`` e o PS + R3), o modo
        ``desktop`` vai ao perfil ativo depois do arranjo, por
        :meth:`gravar_o_modo_escolhido`. A ``origin`` não serve de sinal: ela é
        ``"manual"`` por padrão aqui, e quem chama o arranjo direto não escolheu
        modo nenhum. E NA MESMA GRAVAÇÃO vai o que a entrada ligou:
        ``mouse.enabled: true``, quando o mouse ficou de pé
        (O-MOUSE-SEGUE-A-NAVEGACAO-01). Assim o disco, o chip e o «Status do
        Modo» dizem a mesma coisa depois de cada entrada.

        O DIÁRIO DIZ O ESTADO: ``arranjo_do_desktop_aplicado`` leva
        ``mouse_vivo=ligado|desligado``, lido do device depois do setter, e não
        do pedido. A chave ``mouse`` do relatório segue no vocabulário do
        applier (``aplicado``, ``falhou``).

        Devolve ``seção → estado`` no vocabulário de
        :meth:`apply_profile_suppression` (``aplicado`` · ``adiado_lock_manual``
        · ``ignorado_*``), porque quem pergunta precisa distinguir *"não havia o
        que aplicar"* de *"não deu"*. NUNCA LEVANTA: falhar em carregar o
        arranjo não é falhar em entrar no modo.
        """
        relatorio: dict[str, str] = {}
        profile = self._perfil_do_arranjo()
        secao_mouse = getattr(profile, "mouse", None) if profile is not None else None

        speed, scroll = _velocidades_ou_as_da_sessao(
            getattr(secao_mouse, "speed", None),
            getattr(secao_mouse, "scroll_speed", None),
        )
        try:
            ok = self.set_mouse_emulation(
                True,
                speed,
                scroll,
                origin="manual" if origin == "manual" else "profile",
            )
            relatorio["mouse"] = APLICADO if ok else "falhou"
        except Exception as exc:
            relatorio["mouse"] = "falhou"
            logger.warning("arranjo_do_desktop_mouse_falhou", err=str(exc))
        mouse_vivo = bool(
            getattr(self.config, "mouse_emulation_enabled", False)
            and getattr(self, "_mouse_device", None) is not None
        )

        if profile is not None:
            try:
                from hefesto_dualsense4unix.profiles.manager import ProfileManager

                gerente = ProfileManager(
                    controller=self.controller,
                    store=self.store,
                    keyboard_device_provider=lambda: getattr(
                        self, "_keyboard_device", None
                    ),
                    mouse_device_provider=lambda: getattr(self, "_mouse_device", None),
                )
                gerente.apply_keyboard(profile, relatorio=relatorio)
                gerente.apply_button_actions(profile, relatorio=relatorio)
            except Exception as exc:
                relatorio["keyboard"] = "falhou"
                logger.warning("arranjo_do_desktop_teclas_falharam", err=str(exc))
        else:
            relatorio["keyboard"] = "ignorado_sem_perfil"

        try:
            from hefesto_dualsense4unix.profiles.schema import (
                resolver_teclado_emulado,
            )
            from hefesto_dualsense4unix.utils.session import (
                load_keyboard_preference,
            )

            flag = load_keyboard_preference()
            if flag is None:
                flag = bool(self.config.keyboard_emulation_enabled)
            desejado = resolver_teclado_emulado(profile, bool(flag))
            self.set_keyboard_emulation(bool(desejado), persist=False)
            relatorio["teclado_emulado"] = APLICADO
        except Exception as exc:
            relatorio["teclado_emulado"] = "falhou"
            logger.warning("arranjo_do_desktop_teclado_falhou", err=str(exc))

        try:
            self.set_emulation_suppressed(False)
            relatorio["supressao"] = APLICADO
        except Exception as exc:
            relatorio["supressao"] = "falhou"
            logger.warning("arranjo_do_desktop_supressao_falhou", err=str(exc))

        logger.info(
            "arranjo_do_desktop_aplicado",
            profile=getattr(profile, "name", None),
            origin=origin,
            mouse_vivo="ligado" if mouse_vivo else "desligado",
            **relatorio,
        )
        if grava_o_modo:
            self.gravar_o_modo_escolhido(
                "desktop",
                porta=grava_o_modo,
                mouse_ligado=True if mouse_vivo else None,
            )
        return relatorio

    def definir_o_status_da_navegacao(
        self,
        ligado: bool,
        *,
        origin: Literal["manual", "profile"],
        grava: GravaOModo = False,
    ) -> dict[str, Any]:
        """O «Status do Modo» da aba Navegação: mouse e teclado, e o perfil depois.

        O-MOUSE-SEGUE-A-NAVEGACAO-01 (29/09/2026), commit 3. O interruptor
        mandava `mouse.emulation.set` e `keyboard.emulation.set` e gravava
        ``mouse.enabled`` e ``teclado_emulado`` no perfil ativo pela janela,
        depois das duas respostas. É a forma que a O-MODO-SE-GRAVA-ONDE-ELE-MUDA-01
        curou para o modo: quem gravava era quem não tinha aplicado. Agora o ato
        e a gravação moram aqui, e a janela chama uma vez (`desktop.status.set`).

        A ORDEM É A DE ANTES, e tem razão: o MOUSE PRIMEIRO, porque é ele que tem
        exclusão mútua com o pad virtual; se ele falhar, o teclado não é tocado
        e não fica ligado sozinho. O teclado vai com o `persist` do
        `keyboard.emulation.set` (o padrão do setter): a flag de sessão segue
        guardando a escolha do interruptor, como sempre guardou.

        Com ``grava`` (a porta da escolha do usuário), ``mouse.enabled`` e
        ``teclado_emulado`` vão ao perfil ativo NA MESMA GRAVAÇÃO, por
        :func:`manager.gravar_a_navegacao_no_perfil_ativo`, e só se os DOIS
        lados chegaram: um teclado recusado não deixa meio-passo no disco.

        Devolve ``{"mouse": bool, "teclado": bool | None, "perfil": str | None,
        "gravado": bool}`` — ``teclado`` é ``None`` quando não foi tentado.
        O portão do modo (só vale na Navegação) é da tela, que o conhece e diz
        a frase; este método não o repete. NUNCA LEVANTA na gravação: o
        aparelho já mudou.
        """
        ligar = bool(ligado)
        desfecho: dict[str, Any] = {
            "mouse": False, "teclado": None, "perfil": None, "gravado": False,
        }
        desfecho["mouse"] = bool(self.set_mouse_emulation(ligar, origin=origin))
        if desfecho["mouse"]:
            desfecho["teclado"] = bool(self.set_keyboard_emulation(ligar))
        if grava and desfecho["mouse"] and desfecho["teclado"]:
            from hefesto_dualsense4unix.profiles.manager import (
                gravar_a_navegacao_no_perfil_ativo,
                nome_do_perfil_que_grava,
            )

            try:
                nome = nome_do_perfil_que_grava(
                    getattr(getattr(self, "store", None), "active_profile", None)
                )
                desfecho["perfil"] = nome
                salvo = gravar_a_navegacao_no_perfil_ativo(
                    nome,
                    ligado=ligar,
                    porta=grava,
                    velocidades=(self.config.mouse_speed, self.config.mouse_scroll_speed),
                )
                desfecho["gravado"] = salvo is not None
            except Exception as exc:
                logger.warning(
                    "status_da_navegacao_nao_gravou", porta=grava, err=str(exc)
                )
        logger.info(
            "status_da_navegacao_definido",
            ligado=ligar,
            origin=origin,
            porta=grava or None,
            **desfecho,
        )
        return desfecho

    def set_mouse_speed(
        self,
        speed: int | None = None,
        scroll_speed: int | None = None,
    ) -> bool:
        """Atualiza velocidades da emulação SEM ligar/desligar (speed-only)."""
        from hefesto_dualsense4unix.integrations import uinput_mouse as _um

        if speed is not None:
            self.config.mouse_speed = max(
                _um.MOUSE_SPEED_MIN, min(_um.MOUSE_SPEED_MAX, int(speed)))
        if scroll_speed is not None:
            self.config.mouse_scroll_speed = max(
                _um.SCROLL_SPEED_MIN, min(_um.SCROLL_SPEED_MAX, int(scroll_speed)))
        if self._mouse_device is not None:
            self._mouse_device.set_speed(
                mouse_speed=self.config.mouse_speed,
                scroll_speed=self.config.mouse_scroll_speed,
            )
        if self.config.mouse_emulation_enabled:
            with contextlib.suppress(Exception):
                from hefesto_dualsense4unix.utils.session import save_mouse_emulation

                save_mouse_emulation(
                    True,
                    speed=self.config.mouse_speed,
                    scroll_speed=self.config.mouse_scroll_speed,
                )
        return True

    def set_keyboard_emulation(self, enabled: bool, *, persist: bool = True) -> bool:
        """Liga/desliga a emulação de TECLADO. Usado pelo IPC `keyboard.emulation.set`.

        EMULACAO-NO-JOGO-01. É o interruptor que o teclado nunca teve — e ele
        tem dentes: desligar DESTRÓI o device virtual (via
        `stop_keyboard_emulation`), então o gate do poll loop
        (`_keyboard_device is not None`) fecha por consequência, do mesmo jeito
        que o mouse do usuário já estava honestamente desligado. Retorna o estado
        efetivo ao final (o pedido pode falhar por /dev/uinput).

        `persist=False` existe para o restore do boot e para os testes: o
        caminho normal (gesto do usuário) grava `keyboard_emulation.flag` para que a
        escolha atravesse restart/reboot — era exatamente o que faltava, já que
        o default da config é True e voltava a valer a cada boot.

        NÃO carimba `_emu_manual_ts` (diferente de `set_mouse_emulation`): não há
        applier de perfil para o teclado, então o carimbo só serviria para
        congelar por 30 s a aplicação de modo/mouse de perfil por causa de um
        toggle que nada tem a ver com eles.

        Desligar aqui tira também o teclado virtual do sistema (L3/R3) e as três
        regiões do touchpad — quem chama pela interface tem de dizer isso a ela.
        """
        with self._emu_lock:
            self.config.keyboard_emulation_enabled = bool(enabled)
            if enabled:
                self._start_keyboard_emulation()
            else:
                self._stop_keyboard_emulation()
            if persist:
                with contextlib.suppress(Exception):
                    from hefesto_dualsense4unix.utils.session import (
                        save_keyboard_emulation,
                    )

                    save_keyboard_emulation(bool(enabled))
            ativo = self._keyboard_device is not None
            logger.info(
                "keyboard_emulation_set",
                enabled=bool(enabled),
                device_ativo=ativo,
                persistido=bool(persist),
            )
            # pedido (`stop_keyboard_emulation` é idempotente e best-effort).
            return ativo if enabled else True

    def set_gamepad_emulation(
        self,
        enabled: bool,
        flavor: str | None = None,
        *,
        origin: OrigemEmulacao,
        caminho: str | None = None,
        caminho_e_escolha: bool = True,
        grava_o_modo: GravaOModo = False,
    ) -> bool:
        """Liga/desliga o gamepad virtual e define a máscara. Usado pelo IPC.

        MODO-DE-CONEXAO-01 (13/09/2026): `caminho` é o MODO de conexão, e é o
        que o chip da aba Jogar e o PS + R3 mandam. Quem não o manda (a CLI, com
        o `--flavor` que continua sendo máscara) não mexe no caminho.

        `caminho_e_escolha=False` (O-FREESTYLE-E-UMA-CAMADA-SO-01, 28/09/2026):
        o `caminho` veio do perfil ativo, perguntado pelo `gamepad.emulation.set`
        sem caminho — vale para o pad e nunca chega ao arquivo global dela.

        Fachada de `set_gamepad_emulation_desfecho` — o bool diz **ativo (ou
        parado) ao final**, nunca "aplicou o pedido". VERDADE-01 (18/08): era
        essa confusão que fazia o autoswitch registrar `mode=aplicado` numa
        troca de máscara RECUSADA pelo gate R-04 e tentar de novo na volta
        seguinte; quem precisa da verdade inteira chama a versão `_desfecho`.

        FEAT-DSX-GAMEPAD-FLAVOR-01. `flavor` em ('dualsense','xbox','nintendo'); None mantém
        o atual. Ligar desliga a emulação de mouse (mútua exclusão) e SAI do Modo
        Nativo (idem).

        BUG-PROFILE-MOUSE-KILLS-GAMEPAD-01: um `gamepad on` manual carimba
        `_emu_manual_ts` — assim um perfil point-and-click focado logo em seguida
        (autoswitch) NÃO mata o gamepad ligado na mão (lock de 30s).

        HARM-01: sair do nativo antes de ligar o vpad é garantido AQUI porque o
        daemon é o único ponto por onde todas as superfícies passam (GUI, applet,
        CLI, perfil, hotkey, autoswitch) — a CLI não pode importar o
        `app.actions.mode_transition` sem arrastar GTK. Sem isto, um `gamepad on`
        com o nativo ligado deixava os dois ligados juntos: o físico grabado pelo
        vpad e o dispatch congelado pelo gate do nativo = jogo sem controle
        nenhum. O caminho inverso (`native.mode.set True` com o vpad ligado) já
        era coberto pelo `_release_controller_to_game`.
        """
        from hefesto_dualsense4unix.daemon.subsystems.gamepad import (
            DESFECHOS_EMULACAO_ATIVA,
            EMU_DESLIGADO,
            EMU_JA_ESTAVA,
        )

        desfecho = self.set_gamepad_emulation_desfecho(
            enabled, flavor, origin=origin, caminho=caminho,
            caminho_e_escolha=caminho_e_escolha, grava_o_modo=grava_o_modo,
        )
        if enabled:
            return desfecho in DESFECHOS_EMULACAO_ATIVA
        return desfecho in (EMU_DESLIGADO, EMU_JA_ESTAVA)

    # acima fechou: um chamador distraído promovido a gesto do usuário, com o jogo da
    def set_gamepad_emulation_desfecho(
        self,
        enabled: bool,
        flavor: str | None = None,
        *,
        origin: OrigemEmulacao,
        caminho: str | None = None,
        caminho_e_escolha: bool = True,
        grava_o_modo: GravaOModo = False,
    ) -> str:
        """O mesmo pedido de `set_gamepad_emulation`, dizendo o que ACONTECEU.

        `caminho_e_escolha=False`: o `caminho` é o do dono da sessão, e não uma
        escolha do usuário (ver `gamepad.start_gamepad_emulation_desfecho`).

        `grava_o_modo` (O-MODO-SE-GRAVA-ONDE-ELE-MUDA-01, 29/09/2026): a porta
        da escolha do usuário. Ligando, com o desfecho `aplicado` ou `ja_estava`, o
        modo `gamepad` vai ao perfil ativo por :meth:`gravar_o_modo_escolhido`,
        FORA do `_emu_lock` — o disco não segura a próxima troca. O caminho vai
        quando é escolha (`caminho_e_escolha`); sem ele, o do perfil fica.
        `falhou` não grava, porque o aparelho não mudou; e o `ja_estava` grava,
        porque o clique no chip aceso conserta um perfil que divergiu.

        VERDADE-01 (18/08). Devolve o vocabulário `EMU_*` de
        `daemon.subsystems.gamepad`: `"aplicado"`, `"ja_estava"`,
        `"bloqueado_por_jogo"`, `"recusado_steam_input"`, `"falhou"` (pedido de
        ligar) e `"desligado"`/`"ja_estava"` (pedido de desligar).

        A distinção que faltava é `"bloqueado_por_jogo"`: o gate R-04 recusa
        recriar o vpad com jogo aberto e a emulação segue ATIVA com a máscara
        anterior — indistinguível de "aplicou" para quem só lia o bool. Sem ela,
        `apply_profile_mode` dizia `mode=aplicado` sobre uma troca recusada e
        pedia de novo na volta seguinte, num laço que destruía e recriava o vpad
        assim que a autoridade do jogo piscava (journal de 19/08 03:0x).
        """
        from hefesto_dualsense4unix.daemon.subsystems.gamepad import (
            EMU_APLICADO,
            EMU_DESLIGADO,
            EMU_JA_ESTAVA,
            start_gamepad_emulation_desfecho,
            stop_gamepad_emulation,
        )

        if origin == "manual":
            self._emu_manual_ts = time.monotonic()
            self._mode_from_profile = None
            self._esquecer_mascara_adiada("gesto_manual")
        with self._emu_lock:
            if enabled:
                if self._native_mode:
                    self.set_native_mode(
                        False, origin="manual" if origin == "manual" else "profile"
                    )
                device_antes = self._gamepad_device
                desfecho = start_gamepad_emulation_desfecho(
                    self,
                    flavor=flavor,
                    origin=origin,
                    caminho=caminho,
                    caminho_e_escolha=caminho_e_escolha,
                )
                ok = desfecho in (EMU_APLICADO, EMU_JA_ESTAVA)
                if ok and self._gamepad_device is not device_antes:
                    from hefesto_dualsense4unix.daemon.subsystems.coop import (
                        get_coop_manager,
                    )

                    with contextlib.suppress(Exception):
                        get_coop_manager(self).sync(force=True, origem=origin)
                elif ok:
                    logger.debug("gamepad_apply_identico_sem_recriacao")
            else:
                tinha_device = self._gamepad_device is not None
                stop_gamepad_emulation(self, persist=(origin == "manual"))
                return EMU_DESLIGADO if tinha_device else EMU_JA_ESTAVA
        if grava_o_modo and ok:
            self.gravar_o_modo_escolhido(
                "gamepad",
                caminho=caminho if caminho_e_escolha else None,
                porta=grava_o_modo,
            )
        return desfecho

    def gravar_o_modo_escolhido(
        self,
        kind: str,
        *,
        caminho: str | None = None,
        porta: PortaQueGrava,
        mouse_ligado: bool | None = None,
    ) -> str | None:
        """O modo que o usuário escolheu vai ao perfil ATIVO. Devolve o nome, ou None.

        O-MODO-SE-GRAVA-ONDE-ELE-MUDA-01 (29/09/2026): QUEM TROCA O MODO GRAVA O
        MODO. A escolha feita pelo chip da aba Jogar era gravada pela janela,
        depois da resposta: com quatro controles a troca leva ~2,9 s, a janela
        desiste aos 2,0 s, e o modo nunca chegava ao perfil — o Freestyle dela
        seguiu em Xbox depois do «Sony DualSense» das 01:43 de 29/09. O PS + R3
        gravava no daemon, e o cartão também. Agora há um escritor só, aqui, e
        os três setters do modo o chamam depois do aparelho, só quando a porta
        diz que é escolha do usuário (`grava_o_modo`).

        O perfil é o de :func:`manager.nome_do_perfil_que_grava` (o ativo: com o
        Freestyle ligado, o Freestyle; desligado, o do jogo que vale ou a
        escolha do usuário; «sem escolha», nenhum), e a regra da seção é a do dono,
        :func:`manager.secao_do_modo_com_o_caminho`: o modo não escreve a
        máscara, e nada mudou, nada se grava. `porta` vai ao `profile_salvo`.

        `mouse_ligado` (O-MOUSE-SEGUE-A-NAVEGACAO-01): a entrada na Navegação
        grava, na MESMA gravação, o ``mouse.enabled`` que ela deixou de pé,
        pela regra do dono (`manager.secao_do_mouse_da_navegacao`), com as
        velocidades vivas quando o perfil não tinha a seção.

        O CARIMBO VAI JUNTO (O-CARIMBO-DA-PONTE-SEGUE-A-ESCOLHA-DELA-01,
        03/10/2026): o daemon passa o jogo que vale (o appid do wrapper vivo, o
        mesmo que a escada usa) e o Steam Input dele (a allowlist que a escada
        lê), e o escritor carimba a ponte `por=escolha_dela` quando o perfil
        que grava é a regra desse jogo. A autoridade de exibição não entra: a
        escolha pela janela acontece com a janela do Hefesto em foco.

        NUNCA LEVANTA: o aparelho já trocou, e um `.json` ilegível não pode
        transformar a troca em recusa.
        """
        from hefesto_dualsense4unix.daemon import launch_env
        from hefesto_dualsense4unix.profiles.manager import (
            gravar_o_modo_no_perfil_ativo,
            nome_do_perfil_que_grava,
        )

        try:
            nome = nome_do_perfil_que_grava(
                getattr(getattr(self, "store", None), "active_profile", None)
            )
            velocidades = (
                (self.config.mouse_speed, self.config.mouse_scroll_speed)
                if mouse_ligado is not None
                else None
            )
            appid = launch_env.launch_session_appid()
            salvo = gravar_o_modo_no_perfil_ativo(
                nome,
                kind=kind,
                caminho=caminho,
                porta=porta,
                mouse_ligado=mouse_ligado,
                velocidades=velocidades,
                appid_do_jogo=appid,
                steam_input=appid is not None and appid in launch_env.steam_input_appids(),
            )
        except Exception as exc:
            logger.warning(
                "modo_escolhido_nao_gravou", kind=kind, porta=porta, err=str(exc)
            )
            return None
        return getattr(salvo, "name", None)

    def vestir_a_mascara_do_aparelho(self, uniq: str) -> str:
        """A máscara que o cartão acabou de gravar passa a valer COM O VPAD DE PÉ.

        MODO-DE-CONEXAO-01, §D.6 (13/09/2026). Medido pelo estudo da sprint: o
        `gamepad.mask.set` gravava o registro e o perfil e **não recriava o
        vpad** — o cartão acendia «Xbox 360» e o jogo continuava recebendo o
        DualSense; e reativar o perfil também não recriava, porque
        `apply_profile_mode` compara o `mode.gamepad_flavor`, não a máscara
        efetiva. Nada aplicava a máscara do cartão com o jogo aberto, e a regra
        de produto é *"eles precisam funcionar durante o jogo"*.

        O ATO MORA AQUI, e o handler só o chama: a máscara é gesto do usuário, logo
        `origin="manual"` — a origem que a trava R-04 deixa passar com o jogo
        aberto. O P1 é o vpad desta classe (`start_gamepad_emulation_desfecho`,
        que compara a máscara efetiva e só recria se ela mudou); os outros são
        do co-op, e o ciclo FORÇADO recria só quem ficou para trás
        (`external_mask.vpad_ficou_para_tras`).

        Devolve o desfecho `EMU_*` do P1, ``"coop"`` para um secundário, ou
        ``""`` quando não há vpad de pé — e aí nada é ligado: escolher máscara
        não liga o Hefesto.
        """
        from hefesto_dualsense4unix.daemon.subsystems.external_mask import (
            mesma_identidade,
        )
        from hefesto_dualsense4unix.daemon.subsystems.gamepad import primary_identity

        if not (
            self.config.gamepad_emulation_enabled and self._gamepad_device is not None
        ):
            return ""
        if mesma_identidade(uniq, primary_identity(self)):
            # caminho limpava o slot, e o Xbox da sessão voltava DualSense com
            return self.set_gamepad_emulation_desfecho(
                True,
                origin="manual",
                caminho=_caminho_do_dono(self, "mascara_do_cartao"),
                caminho_e_escolha=False,
            )
        from hefesto_dualsense4unix.daemon.subsystems.coop import get_coop_manager

        with contextlib.suppress(Exception):
            get_coop_manager(self).sync(force=True, origem="manual")
        return "coop"

    def set_coop_enabled(
        self,
        enabled: bool,
        *,
        origin: Literal["manual", "profile"],
    ) -> bool:
        """Liga o co-op local (FEAT-DSX-COOP-LOCAL-01). Usado pelo IPC."""
        self.config.coop_enabled = bool(enabled)
        if origin == "manual":
            self._emu_manual_ts = time.monotonic()
            self._mode_from_profile = None
            with contextlib.suppress(Exception):
                from hefesto_dualsense4unix.utils.session import save_coop_enabled

                save_coop_enabled(self.config.coop_enabled)
        from hefesto_dualsense4unix.daemon.subsystems.coop import get_coop_manager

        coop = get_coop_manager(self)
        if self.config.coop_enabled:
            coop.sync(force=True)
        else:
            coop.disable()
        logger.info(
            "coop_enabled_set",
            enabled=self.config.coop_enabled,
            players=coop.player_count(),
        )
        return self.config.coop_enabled

    def contar_controles_fisicos(self) -> int:
        """Quantos controles FÍSICOS o backend enxerga conectados agora (AUTO-01.1).

        Fonte: `describe_controllers` do backend — os mesmos getattrs baratos
        (sem HID I/O, sem varrer /dev/input) que o `_sync_identity_registry` já
        consome no tick lento. `discover_dualsense_evdevs` daria a mesma
        resposta e custaria 10-40 ms de enumeração por chamada: é justamente o
        que o PERF-MULTI-CONTROLLER-01 tirou do event loop.

        Controles EXTERNOS (8BitDo, Pro Controller) NÃO entram na conta, e isso
        é decisão: eles já chegam ao jogo como gamepad nativo (8BIT-02) e não
        dependem de gamepad virtual nenhum — a emulação existe para o DualSense,
        que sem ela alimenta o cursor em vez do jogo.

        Backend sem a API (fake/legado) ou payload estranho devolve 0: na
        dúvida, não há segundo controle e nada liga sozinho.
        """
        describe = getattr(self.controller, "describe_controllers", None)
        if not callable(describe):
            return 0
        try:
            infos = describe()
        except Exception as exc:
            logger.debug("contagem_de_controles_falhou", err=str(exc))
            return 0
        if not isinstance(infos, list):
            return 0
        return sum(
            1
            for info in infos
            if isinstance(info, dict) and bool(info.get("connected"))
        )

    def aplicar_gamepad_para_multiplos_controles(self) -> str:
        """Liga a emulação de gamepad quando há DOIS ou mais controles (AUTO-01.1).

        A queixa que isto cura: numa instalação nova, quatro DualSense plugados
        alimentam **um cursor só**. `DaemonConfig.gamepad_emulation_enabled`
        nasce `False`, o gate do co-op (`CoopManager.should_be_active`) exige o
        vpad do P1 de pé, e por isso o `coop_enabled=True` (o piso do
        `DaemonConfig`, desde 06/08) é decorativo sozinho: sem emulação não
        existe jogador 2. O caminho para os quatro
        jogadores passava por abrir um terminal ou caçar a aba certa.

        Um segundo controle na mesa é a declaração de intenção mais clara que
        existe — ninguém pluga dois DualSense para os dois moverem o mesmo
        cursor. Então o daemon liga a emulação sozinho, UMA vez, e só nas
        condições em que isso não pisa em decisão de ninguém. Na ordem
        (todas as guardas são baratas: isto roda no tick lento, ~2 s):

        1. **já ligada** — idempotente e é a saída do estado normal (um `and`
           por tique depois que a automação agiu ou que ela mesma ligou);
        2. **preferência persistida** — `load_gamepad_preference` distingue
           "nunca decidiu" de "DESLIGOU de propósito" (AUTO-01.1 no
           `utils.session`). Qualquer decisão gravada — ligada ou desligada —
           tira a automação de cena para sempre; ela existe só para quem nunca
           disse nada. Sem essa distinção, o "Controlar o PC" que ela acabou de
           escolher voltaria a ser "Jogar pelo Hefesto" em ~2 s;
        3. **lock de gesto manual (30 s)** — invariante forte do projeto: gesto
           do usuário cria trava de 30 s e nada reverte nesse período. Aqui o pedido
           apenas ESPERA (o tick lento repete, e ele entra quando o lock
           vencer), como no `aplicar_modo_jogo_padrao`;
        4. **Modo Nativo** — o controle está SOLTO para o jogo de propósito;
        5. **emulação de mouse VIVA** — ela está usando o controle como mouse
           agora (modo desktop, ou perfil com seção `mouse`). Ligar o vpad aqui
           derrubaria o mouse pela exclusão mútua e, no tique seguinte, o perfil
           o religaria: um flap sem fim entre cursor e vpad. Dois controles na
           mesa não são autorização para arrancar o cursor da mão do usuário;
        6. **um controle só** — nada a fazer.

        Chama com `origin="profile"` de propósito: NÃO é gesto do usuário, então não
        carimba `_emu_manual_ts` (não trava perfil nenhum por 30 s) e **não
        persiste** preferência (R-07 — só o gesto manual escreve em disco). A
        automação fica fora do disco por construção: se ela desligar depois, o
        opt-out vale para sempre; se nunca mexer, o daemon reavalia a cada boot.

        Retorno: o vocabulário de `APLICADO`/`ADIADO_LOCK_MANUAL`/`IGNORADO_*`,
        com o log deduplicado por estado (`_gamepad_multi_log`) — o pedido chega
        a cada 2 s e não pode virar enxurrada no journal.
        """
        from hefesto_dualsense4unix.daemon.state_store import (
            MANUAL_PROFILE_LOCK_SEC,
        )
        from hefesto_dualsense4unix.utils.session import load_gamepad_preference

        if self.config.gamepad_emulation_enabled and self._gamepad_device is not None:
            return APLICADO
        preferencia, _flavor = load_gamepad_preference()
        if preferencia is not None:
            return self._log_gamepad_multi(
                IGNORADO_GESTO_DELA,
                "ligada" if preferencia else "desligada_de_proposito",
                0,
            )
        if time.monotonic() - self._emu_manual_ts < MANUAL_PROFILE_LOCK_SEC:
            return self._log_gamepad_multi(
                ADIADO_LOCK_MANUAL, "gesto_manual_recente", 0
            )
        if self._native_mode or self.store.native_mode_active:
            return self._log_gamepad_multi(IGNORADO_GESTO_DELA, "modo_nativo", 0)
        if self._mouse_device is not None:
            return self._log_gamepad_multi(IGNORADO_GESTO_DELA, "mouse_em_uso", 0)
        controles = self.contar_controles_fisicos()
        if controles < 2:
            return self._log_gamepad_multi(
                IGNORADO_UM_CONTROLE_SO, "menos_de_dois_controles", controles
            )
        ok = self.set_gamepad_emulation(
            True,
            origin="profile",
            caminho=_caminho_do_dono(self, "dois_controles_na_mesa"),
        )
        if not ok:
            return self._log_gamepad_multi(FALHOU, "start_recusou", controles)
        self._gamepad_multi_log = APLICADO
        logger.info(
            "gamepad_ligado_por_multiplos_controles",
            controles=controles,
            flavor=self.config.gamepad_flavor,
            coop=self.config.coop_enabled,
        )
        return APLICADO

    def _log_gamepad_multi(self, estado: str, motivo: str, controles: int) -> str:
        """Loga o estado do auto-ligar do gamepad 1x por episódio (AUTO-01.1)."""
        if self._gamepad_multi_log != estado:
            self._gamepad_multi_log = estado
            logger.info(
                "gamepad_multiplos_controles_adiado",
                estado=estado,
                motivo=motivo,
                controles=controles,
            )
        return estado

    def set_emulation_suppressed(
        self,
        value: bool | None = None,
        *,
        origin: Literal["manual", "profile"] = "manual",
    ) -> bool:
        """Liga/desliga a supressão da emulação de mouse/teclado (modo jogo)."""
        from hefesto_dualsense4unix.integrations.desktop_notifications import (
            notify_emulation_suppressed,
        )

        new_state = (not self._emulation_suppressed) if value is None else bool(value)
        self._emulation_suppressed = new_state
        if origin == "manual":
            self._suppress_manual_ts = time.monotonic()
            self._suppress_from_profile = False
        if new_state:
            self._flush_emulation_devices()
        logger.info("emulation_suppressed_changed", suppressed=new_state)
        notify_emulation_suppressed(new_state)
        return new_state

    def apply_profile_suppression(
        self,
        desired: bool,
        *,
        profile: Any | None = None,
        origin: str = "autoswitch",
    ) -> str:
        """Aplica `suppress_desktop_emulation` de um perfil recém-ativado.

        FEAT-POINT-AND-CLICK-01. Injetado como `suppression_applier` do
        `ProfileManager` — chamado a CADA ativação de perfil (IPC, autoswitch,
        hotkey de ciclo, restore no boot), sempre com o valor do campo
        (inclusive o default False).

        Semântica escolhida (documentada aqui como fonte canônica):

        1. **Lock manual** — se a usuária alternou o modo-jogo manualmente
           (PS+Options, IPC, GUI) há menos de ``MANUAL_PROFILE_LOCK_SEC``
           (30s, mesma constante do lock de perfil manual), o perfil NÃO mexe
           na supressão em NENHUMA direção (nem liga, nem libera). Log
           informativo e retorno.
        2. **desired=True** — liga a supressão (idempotente: só chama o setter
           se o estado muda, evitando flush/notificação repetidos a cada tick
           do autoswitch) e marca origem "perfil". Se a supressão já estava
           ligada por gesto manual ANTIGO (lock expirado), o perfil a ADOTA:
           ao sair do jogo, o perfil do desktop libera — é a UX esperada do
           autoswitch dono do estado após a janela de respeito.
           PERFIL-REESCRITO-NA-PARTIDA-01 (05/08): **catch-all não liga**, pela
           mesma razão pela qual ele não libera (item 3) — ver o comentário no
           corpo. Sem essa metade, um catch-all com `suppress: true` (o
           `sackboy_nativo` do disco do usuário) criava um estado do qual nenhum
           outro catch-all conseguia sair.
        3. **desired=False** — LIBERA a supressão apenas se ela veio de perfil
           (`_suppress_from_profile`). Supressão de origem manual (lock já
           expirado, sem perfil que a adotasse) permanece intocada: quem ligou
           na mão, desliga na mão.

        R-03 (auditoria 23/07): `origin` é a origem da ATIVAÇÃO do perfil
        (`ProfileManager.activate`), não a do toggle. Com ``origin="manual"``
        (profile.switch pela GUI/CLI ou PS+D-pad) o item 1 é FURADO e o carimbo
        é consumido: escolher um perfil na mão é gesto MAIS NOVO que o modo-jogo
        que ela alternou segundos antes. Retorno: ver o vocabulário em
        `APLICADO`/`ADIADO_LOCK_MANUAL`/`IGNORADO_*`.
        """
        from hefesto_dualsense4unix.daemon.state_store import (
            MANUAL_PROFILE_LOCK_SEC,
        )

        now = time.monotonic()
        if origin == "manual":
            if now - self._suppress_manual_ts < MANUAL_PROFILE_LOCK_SEC:
                logger.info(
                    "profile_suppression_lock_furado_por_gesto_manual",
                    desired=desired,
                    profile=getattr(profile, "name", None),
                )
            self._suppress_manual_ts = float("-inf")
        elif now - self._suppress_manual_ts < MANUAL_PROFILE_LOCK_SEC:
            logger.info(
                "profile_suppression_skipped_manual_lock",
                desired=desired,
                remaining_sec=round(
                    MANUAL_PROFILE_LOCK_SEC - (now - self._suppress_manual_ts), 1
                ),
            )
            return ADIADO_LOCK_MANUAL
        if desired:
            if self._perfil_e_catch_all(profile):
                logger.info(
                    "profile_suppression_skipped",
                    motivo="catch_all_sem_opiniao",
                    desired=True,
                    profile=getattr(profile, "name", None),
                )
                return IGNORADO_CATCH_ALL
            if not self._emulation_suppressed:
                self.set_emulation_suppressed(True, origin="profile")
            self._suppress_from_profile = True
        elif self._emulation_suppressed and self._suppress_from_profile:
            if not self._perfil_tem_opiniao(profile):
                logger.info(
                    "profile_suppression_revert_skipped",
                    motivo="catch_all_sem_opiniao",
                    profile=getattr(profile, "name", None),
                )
                return IGNORADO_CATCH_ALL
            if self._janela_de_jogo_em_foco():
                logger.info(
                    "profile_suppression_revert_skipped",
                    motivo="janela_de_jogo_em_foco",
                    profile=getattr(profile, "name", None),
                )
                return IGNORADO_JANELA_DE_JOGO
            self.set_emulation_suppressed(False, origin="profile")
            self._suppress_from_profile = False
        return APLICADO

    def _furar_lock_de_emulacao(self, secao: str, *, agora: float) -> None:
        """R-03: consome o carimbo de gesto manual da EMULAÇÃO (`_emu_manual_ts`).

        Chamado pelos appliers quando a ativação veio com ``origin="manual"`` —
        `profile.switch` (GUI/CLI/applet) ou o ciclo por PS+D-pad. A regra é de
        ORDEM, não de hierarquia: o lock existe para o perfil não sequestrar o
        que ela acabou de fazer na mão; quando o gesto mais novo é justamente
        "ative este perfil", o perfil É a vontade dela e furar o lock é o certo.

        Zerar o carimbo (em vez de só ignorá-lo) é a segunda metade da cura: o
        perfil que acabou de entrar mexe na máscara/co-op via
        `set_*(origin="profile")` — que não re-carimba —, mas um carimbo VELHO
        sobrevivente continuaria bloqueando o PRÓXIMO perfil (o autoswitch ao
        abrir o jogo, por exemplo) por até 30 s. Um log por ativação: quem furar
        primeiro zera, os appliers seguintes já veem `-inf`.
        """
        from hefesto_dualsense4unix.daemon.state_store import (
            MANUAL_PROFILE_LOCK_SEC,
        )

        restante = MANUAL_PROFILE_LOCK_SEC - (agora - self._emu_manual_ts)
        if restante > 0:
            logger.info(
                "profile_lock_manual_furado",
                secao=secao,
                restante_sec=round(restante, 1),
            )
        self._emu_manual_ts = float("-inf")

    def apply_profile_mouse(
        self,
        enabled: bool,
        speed: int | None,
        scroll_speed: int | None,
        *,
        origin: str = "autoswitch",
        profile: Any | None = None,
    ) -> str:
        """Aplica a seção `mouse` de um perfil recém-ativado (BUG-PROFILE-MOUSE-"""
        from hefesto_dualsense4unix.daemon.state_store import (
            MANUAL_PROFILE_LOCK_SEC,
        )

        now = time.monotonic()
        if origin == "manual":
            self._furar_lock_de_emulacao("mouse", agora=now)
        elif now - self._emu_manual_ts < MANUAL_PROFILE_LOCK_SEC:
            logger.info(
                "profile_mouse_skipped_manual_lock",
                enabled=enabled,
                remaining_sec=round(
                    MANUAL_PROFILE_LOCK_SEC - (now - self._emu_manual_ts), 1
                ),
            )
            return ADIADO_LOCK_MANUAL
        nome = getattr(profile, "name", None)
        speed, scroll_speed = _velocidades_ou_as_da_sessao(speed, scroll_speed)
        if profile is not None and not _o_perfil_diz_navegacao(profile):
            self.set_mouse_speed(speed=speed, scroll_speed=scroll_speed)
            logger.info(
                "profile_mouse_aplicado", liga_desliga="nao_opina", profile=nome
            )
            return APLICADO
        actual_on = self.config.mouse_emulation_enabled and self._mouse_device is not None
        if enabled == actual_on:
            if enabled:
                self.set_mouse_speed(speed=speed, scroll_speed=scroll_speed)
            logger.info("profile_mouse_aplicado", liga_desliga="ficou", profile=nome)
            return APLICADO
        self.set_mouse_emulation(
            enabled, speed, scroll_speed, origin="profile"
        )
        logger.info(
            "profile_mouse_aplicado",
            liga_desliga="ligou" if enabled else "desligou",
            profile=nome,
        )
        return APLICADO

    def _perfil_tem_opiniao(self, profile: Any | None) -> bool:
        """False quando o perfil é catch-all (`MatchAny` ou criteria vazio)."""
        if profile is None:
            return False
        e_catch_all = getattr(profile, "e_catch_all", None)
        if e_catch_all is None:
            return False
        return not e_catch_all

    @staticmethod
    def _perfil_e_catch_all(profile: Any | None) -> bool:
        """True SÓ com evidência POSITIVA de que o perfil é catch-all.

        PERFIL-REESCRITO-NA-PARTIDA-01, item 2. É o irmão de
        `_perfil_tem_opiniao`, e a diferença entre os dois É a resposta na
        DÚVIDA — por isso são dois predicados e não uma negação:

        - ao reverter `mode`/supressão, a dúvida vale "sem opinião"
          (`_perfil_tem_opiniao`): aquelas guardas são antigas, todos os seus
          chamadores já passam `profile=`, e não reverter é o fail-safe;
        - aqui a dúvida NÃO bloqueia. Perfil ausente é o chamador direto
          (dublês da suíte, CLI) e `e_catch_all` ausente é um objeto parcial —
          nos dois casos a leitura honesta é "não sei se chegou por acidente",
          e uma guarda NOVA não pode transformar esse silêncio em recusa para
          quem nunca teve guarda nenhuma.

        Para um `Profile` de verdade os dois predicados coincidem, e em
        produção o perfil SEMPRE chega: `ProfileManager.apply_emulation` passa
        `profile=` a cada ativação. Usado ao LIGAR a supressão (item 2 da leva)
        e ao reverter a política de rumble (item 3).
        """
        return getattr(profile, "e_catch_all", None) is True

    def _janela_de_jogo_em_foco(self) -> bool:
        """True quando a janela em foco AGORA é de um JOGO — de qualquer lançador.

        R-02, decisão 3 do plano: leitura CRUA da janela, deliberadamente
        diferente do `display_authority` (que é sticky por 30 s). Aqui a
        pergunta é "reverter para desktop agora seria absurdo?", e para isso o
        sinal sticky congelaria a reversão legítima ao sair do jogo. O sinal
        sticky continua sendo o certo para operação DESTRUTIVA (recriar/parar
        vpad), onde fail-safe é não destruir.

        VPAD-NA-JANELA-DA-STEAM-01 (17/08/2026) — **o cliente Steam conta.**
        Até aqui esta guarda só reconhecia `steam_app_<id>`, e a janela do
        CLIENTE (`steam`) respondia `False`. Como o perfil de desktop do usuário casa
        com `steam` no `window_class`, alternar para a Steam no meio da partida
        autorizava a reversão de modo e **destruía o vpad**; o jogo, que já
        tinha enumerado aquele nó, ficava com um descritor órfão e um controle
        que não se mexe.

        Medido em 17/08 com par fechado, mesma máquina, mesmo minuto::

            profile activate "Dont Scream"  ->  /dev/hidraw4 NASCE
            profile activate "Navegação"    ->  /dev/hidraw4 SOME

        A pergunta desta guarda nunca foi "isto é um jogo?", e sim "reverter
        para desktop AGORA seria absurdo?". Com um jogo aberto atrás dela, a
        janela da Steam é o lugar mais comum de se estar durante a partida —
        conferir um preço, ler uma conquista — e reverter ali é absurdo pelo
        mesmo critério que já protegia o `steam_app_<id>`.

        **O preço, e o usuário decidiu pagá-lo (17/08):** com a Steam em foco, o modo
        vindo de PERFIL não reverte, mesmo sem jogo nenhum atrás. Na prática
        isso mantém o vpad de pé enquanto ela navega na Steam, que é o estado
        normal desta máquina. Fora da Steam (Firefox, terminal) a reversão
        continua imediata, e é por isso que o teste que finca a política de
        23/07 — `test_perfil_especifico_fora_de_jogo_reverte_normalmente`, que
        usa `firefox` — continua verde: esta mudança fecha um buraco, não abre
        a política.
        """
        from hefesto_dualsense4unix.profiles.steam_app import (
            e_janela_do_cliente_steam,
            steam_appid_from_wm_class,
        )

        wm_class = str(getattr(self.store, "window_detect_current_class", None) or "")
        if steam_appid_from_wm_class(wm_class) is not None:
            return True
        if e_janela_do_cliente_steam(wm_class):
            return True
        try:
            from hefesto_dualsense4unix.integrations.jogos_locais import (
                jogo_da_janela,
                jogos_de_janela,
            )

            return jogo_da_janela(wm_class, jogos_de_janela()) is not None
        except Exception as exc:  # pragma: no cover - disco hostil
            logger.debug("catalogo_de_janelas_indisponivel", err=str(exc))
            return False

    def apply_profile_mode(
        self,
        mode: Any | None,
        *,
        profile: Any | None = None,
        origin: str = "autoswitch",
    ) -> str:
        """Aplica a seção `mode` de um perfil recém-ativado (FEAT-PROFILE-MODE-01).

        Injetado como `mode_applier` nas rotas de ativação (IPC switch,
        autoswitch, hotkey de ciclo). NÃO usado no restore do boot (lá os flags
        persistidos governam — ver connection.py). É o que faz as features
        COEXISTIREM: o perfil do jogo em foco decide o modo, em vez de toggles
        globais brigando.

        Semântica (espelha `apply_profile_suppression`/`apply_profile_mouse`):

        1. **Lock manual** — gesto manual (gamepad/mouse/nativo/co-op) há menos
           de `MANUAL_PROFILE_LOCK_SEC` congela: o perfil não mexe no modo.
        2. **mode=None (perfil sem opinião)** — REVERTE apenas modo que outro
           PERFIL ligou (`_mode_from_profile`); estado de origem manual fica.
        3. **kind="native"** — liga o Modo Nativo (release total) com origem
           perfil; sair do foco (outro perfil ativar) reverte pelo item 2.
        4. **kind="gamepad"** — desliga nativo-de-perfil se preciso, liga o
           gamepad com a máscara pedida e sincroniza o co-op ao campo `coop`.
           VERDADE-01: se o gate R-04 recusar a troca de máscara porque há jogo
           com a autoridade, o resto da seção vale, a divergência fica guardada
           (`_pedir_mascara_do_perfil`) e o retorno é `ADIADO_JOGO_ABERTO` — não
           `APLICADO`, que era a mentira que fazia o chamador tentar de novo.
        5. **kind="desktop"** — declaração explícita: desliga nativo/gamepad
           mesmo os de origem manual JÁ EXPIRADA do lock (o perfil está
           dizendo "este app é desktop puro").

        LEIGO-01: a PREFERÊNCIA de co-op nunca é desligada por perfil que sai do
        gamepad (itens 2 e 5) — sem gamepad não há jogadores para desmontar, e
        zerá-la aqui deixaria o co-op morto pelo resto da sessão.

        Idempotente por checagem de estado antes de cada setter (autoswitch
        re-ativa o mesmo perfil sem flap).

        R-03 (auditoria 23/07) — o item 1 deixou de ser um buraco negro:

        - ``origin="manual"`` (profile.switch / PS+D-pad) **fura** o lock e
          consome o carimbo: o gesto mais novo dela é "ative este perfil".
        - Origem automática (autoswitch/system) **adia**: a ativação segue
          commitada normalmente — nada de flap a 2 Hz — e a seção fica numa
          pendência ÚNICA (`ModoAdiado`) que o `_poll_loop` drena UMA vez,
          quando o lock vencer. Era esta a queixa medida: ela mexia na máscara,
          abria o Sackboy em menos de 30 s, o `mode` do perfil era pulado em
          silêncio e a máscara ficava errada a SESSÃO INTEIRA, com a GUI
          mostrando o perfil ativo como se tudo tivesse valido.
        """
        from hefesto_dualsense4unix.daemon.state_store import (
            MANUAL_PROFILE_LOCK_SEC,
        )

        kind = getattr(mode, "kind", None) if mode is not None else None
        now = time.monotonic()
        if origin == "manual":
            self._furar_lock_de_emulacao("mode", agora=now)
        elif now - self._emu_manual_ts < MANUAL_PROFILE_LOCK_SEC:
            if kind is not None:
                logger.info(
                    "profile_mode_skipped_manual_lock",
                    kind=kind,
                    remaining_sec=round(
                        MANUAL_PROFILE_LOCK_SEC - (now - self._emu_manual_ts), 1
                    ),
                )
            self._agendar_modo_adiado(mode, profile, origin, agora=now)
            return ADIADO_LOCK_MANUAL

        self._mode_pendente = None
        if origin != ORIGEM_GAME_SIGNAL:
            self._modo_jogo_padrao = None
            self._modo_jogo_padrao_log = ""

        gamepad_on = (
            self.config.gamepad_emulation_enabled and self._gamepad_device is not None
        )

        if kind is None:
            if not self._perfil_tem_opiniao(profile):
                logger.info(
                    "profile_mode_revert_skipped",
                    motivo="catch_all_sem_opiniao",
                    profile=getattr(profile, "name", None),
                    mode_from_profile=self._mode_from_profile,
                )
                return IGNORADO_CATCH_ALL
            self.config.gamepad_flavor = _mascara_da_maquina()
            if self._janela_de_jogo_em_foco():
                logger.info(
                    "profile_mode_revert_skipped",
                    motivo="janela_de_jogo_em_foco",
                    profile=getattr(profile, "name", None),
                    mode_from_profile=self._mode_from_profile,
                )
                return IGNORADO_JANELA_DE_JOGO
            if self._mode_from_profile == "native" and self._native_mode:
                self.set_native_mode(
                    False, reapply=False, restore_stash=True, origin="profile"
                )
            elif self._mode_from_profile == "gamepad" and gamepad_on:
                if _a_maquina_deixa_o_pad_ligado():
                    self._mode_from_profile = None
                    return _o_ramo_do_pad(self, None, profile=profile, origin=origin)
                self.set_gamepad_emulation(False, origin="profile")
            self._mode_from_profile = None
            return APLICADO

        if kind == "native":
            if not self._native_mode:
                self.set_native_mode(True, origin="profile")
            self._mode_from_profile = "native"
            return APLICADO

        if kind == "gamepad":
            resultado = _o_ramo_do_pad(self, mode, profile=profile, origin=origin)
            self._mode_from_profile = "gamepad"
            return resultado

        if self._native_mode:
            self.set_native_mode(False, reapply=False, origin="profile")
        if gamepad_on:
            self.set_gamepad_emulation(False, origin="profile")
        self._mode_from_profile = None
        return APLICADO

    def _carregar_o_modo_nativo(self) -> None:
        """O Modo Nativo da sessão anterior, e a posse da exclusão junto."""
        from hefesto_dualsense4unix.utils.session import load_native_mode

        self._native_mode, self._native_emu_stash = load_native_mode()
        self._exclusao_viva = (
            exclusao_do_stash(self._native_emu_stash) if self._native_mode else None
        )

    def aplicar_a_exclusao(self, *, chave: str) -> str:
        """O jogo em foco está na lista de exclusão: o Hefesto fica fora dele."""
        if self._exclusao_viva is not None:
            return APLICADO
        from hefesto_dualsense4unix.utils.session import save_native_mode

        ligou = not self._native_mode
        dono = self._mode_from_profile
        if ligou:
            self.set_native_mode(True, origin=ORIGEM_EXCLUSAO)
            self._native_emu_stash = {
                **self._native_emu_stash,
                STASH_DA_EXCLUSAO: {"chave": chave, "dono_anterior": dono},
            }
            save_native_mode(True, emu_stash=self._native_emu_stash)
        self._exclusao_viva = ExclusaoViva(
            chave=chave, ligou_nativo=ligou, dono_anterior=dono
        )
        logger.info("exclusao_aplicada", chave=chave, ligou_nativo=ligou)
        return APLICADO

    def reverter_a_exclusao(self) -> str:
        """O jogo excluído saiu do foco: devolve o que a exclusão tirou."""
        viva = self._exclusao_viva
        if viva is None:
            return IGNORADO_SEM_JOGO
        self._exclusao_viva = None
        if viva.ligou_nativo and self._native_mode:
            self.set_native_mode(
                False, reapply=True, restore_stash=True, origin=ORIGEM_EXCLUSAO
            )
        self._mode_from_profile = viva.dono_anterior
        logger.info(
            "exclusao_revertida", chave=viva.chave, desligou_nativo=viva.ligou_nativo
        )
        return APLICADO

    def aplicar_modo_jogo_padrao(self, *, wm_class: str = "") -> str:
        """Liga o MODO JOGO PADRÃO — é um jogo e nenhum perfil opina (MODO-01/B3)."""
        from hefesto_dualsense4unix.daemon.state_store import (
            MANUAL_PROFILE_LOCK_SEC,
        )
        from hefesto_dualsense4unix.profiles.schema import (
            ProfileModeConfig,
            normalizar_gamepad_flavor,
        )

        if self.display_authority != "game":
            return self._log_modo_jogo_padrao(
                IGNORADO_SEM_JOGO, "sem_autoridade_de_jogo", wm_class
            )
        if self._modo_jogo_padrao is not None:
            return APLICADO
        if time.monotonic() - self._emu_manual_ts < MANUAL_PROFILE_LOCK_SEC:
            return self._log_modo_jogo_padrao(
                ADIADO_LOCK_MANUAL, "gesto_manual_recente", wm_class
            )
        if (
            self.store.native_mode_active
            and getattr(self.store, "native_mode_origin", None) != "profile"
        ):
            return self._log_modo_jogo_padrao(
                IGNORADO_GESTO_DELA, "modo_nativo_manual", wm_class
            )
        gamepad_antes = (
            self.config.gamepad_emulation_enabled and self._gamepad_device is not None
        )
        dono_anterior = self._mode_from_profile
        estado = self.apply_profile_mode(
            ProfileModeConfig(
                kind="gamepad",
                gamepad_flavor=normalizar_gamepad_flavor(self.config.gamepad_flavor),
            ),
            origin=ORIGEM_GAME_SIGNAL,
        )
        if estado != APLICADO:
            return self._log_modo_jogo_padrao(estado, "applier_recusou", wm_class)
        gamepad_agora = (
            self.config.gamepad_emulation_enabled and self._gamepad_device is not None
        )
        self._modo_jogo_padrao = ModoJogoPadrao(
            ligou_gamepad=(gamepad_agora and not gamepad_antes),
            dono_anterior=dono_anterior,
            wm_class=wm_class,
        )
        self._modo_jogo_padrao_log = APLICADO
        logger.info(
            "profile_mode_aplicado",
            origin=ORIGEM_GAME_SIGNAL,
            kind="gamepad",
            flavor=self.config.gamepad_flavor,
            wm_class=wm_class,
            ligou_gamepad=self._modo_jogo_padrao.ligou_gamepad,
        )
        return APLICADO

    def reverter_modo_jogo_padrao(self, *, wm_class: str = "") -> str:
        """Solta o modo jogo padrão ao sair do jogo (MODO-01/B3)."""
        from hefesto_dualsense4unix.daemon.state_store import (
            MANUAL_PROFILE_LOCK_SEC,
        )

        padrao = self._modo_jogo_padrao
        if padrao is None:
            return APLICADO
        self._modo_jogo_padrao = None
        self._modo_jogo_padrao_log = ""
        if time.monotonic() - self._emu_manual_ts < MANUAL_PROFILE_LOCK_SEC:
            logger.info(
                "modo_jogo_padrao_solto",
                motivo="gesto_manual_recente",
                wm_class=wm_class,
            )
            return ADIADO_LOCK_MANUAL
        gamepad_on = (
            self.config.gamepad_emulation_enabled and self._gamepad_device is not None
        )
        desligou = False
        if padrao.ligou_gamepad and gamepad_on:
            self.set_gamepad_emulation(False, origin="profile")
            desligou = True
        if self._mode_from_profile == "gamepad":
            self._mode_from_profile = padrao.dono_anterior
        logger.info(
            "modo_jogo_padrao_solto",
            motivo="janela_fora_do_jogo",
            wm_class=wm_class,
            de=padrao.wm_class,
            desligou_gamepad=desligou,
        )
        return APLICADO

    def _log_modo_jogo_padrao(self, estado: str, motivo: str, wm_class: str) -> str:
        """Loga o estado do pedido de modo jogo padrão 1x por episódio (B3/B5)."""
        if self._modo_jogo_padrao_log != estado:
            self._modo_jogo_padrao_log = estado
            logger.info(
                "modo_jogo_padrao_adiado",
                estado=estado,
                motivo=motivo,
                wm_class=wm_class,
            )
        return estado

    def _pedir_mascara_do_perfil(
        self,
        flavor: str | None,
        *,
        profile: Any | None,
        origin: str,
        caminho: str | None = None,
    ) -> bool:
        """Pede ao vpad a máscara do perfil. True = ADIADA porque há jogo aberto."""
        if self._mascara_ja_adiada_por_jogo(flavor):
            return True
        origem_emulacao: OrigemEmulacao = (
            "gesto_de_perfil" if origin == "manual" else "profile"
        )
        desfecho = self.set_gamepad_emulation_desfecho(
            True,
            flavor,
            origin=origem_emulacao,
            **cast("dict[str, Any]", {"caminho": caminho} if caminho is not None else {}),
        )
        if desfecho != EMU_BLOQUEADO_POR_JOGO:
            self._esquecer_mascara_adiada(desfecho)
            return False
        self._registrar_mascara_adiada(flavor, profile=profile)
        return True

    def _mascara_viva(self) -> str | None:
        """A máscara que o vpad está VESTINDO agora — ou None se não há vpad."""
        vivo = getattr(self._gamepad_device, "flavor", None)
        if isinstance(vivo, str) and vivo:
            return vivo
        return None

    def _gravar_mascara_do_perfil(self, flavor: str | None) -> None:
        """MASCARA-PERSISTE-01 — e a NOTA DATADA que a substituiu."""
        return

    def _mascara_ja_adiada_por_jogo(self, flavor: str | None) -> bool:
        """True se um pedido de máscara já foi recusado e o jogo segue na frente.

        O latch NÃO é chaveado pela máscara pedida, e isso é a lição do journal
        de 19/08: duas janelas se revezando (o perfil do jogo e o de uma janela
        invisível da Steam) pediam `xbox` e `dualsense` alternadamente, e um
        latch por máscara deixaria as duas passarem a cada volta. Com jogo na
        frente, NENHUMA troca automática de máscara é possível — o latch só
        guarda qual é a última pedida, para o diagnóstico dizer a verdade.
        """
        adiada = self._mascara_adiada_por_jogo
        if adiada is None:
            return False
        if self.display_authority != "game":
            self._esquecer_mascara_adiada("jogo_saiu_da_frente")
            return False
        if adiada.flavor != flavor:
            adiada.flavor = flavor
            logger.debug(
                "profile_mode_mascara_adiada_atualizada",
                pedida=flavor,
                vigente=getattr(self._gamepad_device, "flavor", None),
            )
        return True

    def _reavaliar_mascara_adiada(self, flavor_atual: str | None) -> None:
        """Encerra o latch quando a divergência REALMENTE deixou de existir."""
        adiada = self._mascara_adiada_por_jogo
        if adiada is None:
            return
        if self.display_authority != "game":
            self._esquecer_mascara_adiada("jogo_saiu_da_frente")
        elif adiada.flavor == flavor_atual:
            self._esquecer_mascara_adiada("convergiu")

    def _registrar_mascara_adiada(
        self, flavor: str | None, *, profile: Any | None
    ) -> None:
        """Grava a divergência e a anuncia UMA vez (VERDADE-01)."""
        anterior = self._mascara_adiada_por_jogo
        if anterior is not None and anterior.anunciada:
            anterior.flavor = flavor
            return
        adiada = MascaraAdiada(
            flavor=flavor,
            profile_name=getattr(profile, "name", None),
            anunciada=True,
        )
        self._mascara_adiada_por_jogo = adiada
        logger.warning(
            "profile_mode_mascara_adiada_jogo_aberto",
            pedida=flavor,
            vigente=getattr(self._gamepad_device, "flavor", None),
            profile=adiada.profile_name,
        )

    def _esquecer_mascara_adiada(self, motivo: str) -> None:
        """Apaga o latch da máscara adiada — a divergência deixou de existir."""
        adiada = self._mascara_adiada_por_jogo
        if adiada is None:
            return
        self._mascara_adiada_por_jogo = None
        logger.info(
            "profile_mode_mascara_adiada_encerrada",
            motivo=motivo,
            pedida=adiada.flavor,
            vigente=getattr(self._gamepad_device, "flavor", None),
        )

    def _agendar_modo_adiado(
        self, mode: Any | None, profile: Any | None, origin: str, *, agora: float
    ) -> None:
        """Guarda a pendência ÚNICA de `mode` adiada pelo lock (R-03)."""
        from hefesto_dualsense4unix.daemon.state_store import (
            MANUAL_PROFILE_LOCK_SEC,
        )

        anterior = self._mode_pendente
        pendencia = ModoAdiado(
            mode=mode,
            profile=profile,
            profile_name=getattr(profile, "name", None),
            origin=origin,
            carimbo_manual=self._emu_manual_ts,
            nao_antes_de=self._emu_manual_ts + MANUAL_PROFILE_LOCK_SEC,
        )
        self._mode_pendente = pendencia
        logger.info(
            "profile_mode_deferred",
            kind=getattr(mode, "kind", None),
            profile=pendencia.profile_name,
            origin=origin,
            expira_em_sec=round(max(0.0, pendencia.nao_antes_de - agora), 1),
            substituiu=(anterior.profile_name if anterior is not None else None),
        )

    def _modo_seria_destrutivo(self, mode: Any | None) -> bool:
        """True se aplicar `mode` AGORA pararia/recriaria o vpad do P1."""
        kind = getattr(mode, "kind", None) if mode is not None else None
        gamepad_on = (
            self.config.gamepad_emulation_enabled and self._gamepad_device is not None
        )
        if kind == "gamepad":
            flavor = getattr(mode, "gamepad_flavor", None)
            flavor_do_jogo = flavor if flavor is not None else _mascara_da_maquina()
            flavor_atual = getattr(self._gamepad_device, "flavor", None)
            return bool(
                gamepad_on
                and (
                    _o_p1_vestiria(self, flavor_do_jogo) != flavor_atual
                    or _canal_mudaria(self, _caminho_da_secao(mode))
                )
            )
        return bool(gamepad_on or self._native_mode)

    def _drenar_modo_pendente(self) -> None:
        """Aplica — UMA vez — a seção `mode` que o lock manual adiou (R-03)."""
        pendencia = self._mode_pendente
        if pendencia is None:
            return
        agora = time.monotonic()
        if agora < pendencia.nao_antes_de:
            return
        if self._emu_manual_ts != pendencia.carimbo_manual:
            self._mode_pendente = None
            logger.info(
                "profile_mode_pendencia_descartada",
                motivo="gesto_manual_novo",
                profile=pendencia.profile_name,
            )
            return
        ativo = self.store.active_profile
        if pendencia.profile_name is not None and ativo != pendencia.profile_name:
            self._mode_pendente = None
            logger.info(
                "profile_mode_pendencia_descartada",
                motivo="perfil_ativo_mudou",
                profile=pendencia.profile_name,
                ativo=ativo,
            )
            return
        from hefesto_dualsense4unix.daemon.subsystems.gamepad import (
            _recriacao_bloqueada_por_jogo,
        )

        if self._modo_seria_destrutivo(pendencia.mode) and _recriacao_bloqueada_por_jogo(
            self, origin="pendencia", motivo="modo_pendente"
        ):
            if not pendencia.esperando_jogo:
                pendencia.esperando_jogo = True
                logger.info(
                    "profile_mode_pendencia_aguardando_jogo",
                    profile=pendencia.profile_name,
                    kind=getattr(pendencia.mode, "kind", None),
                )
            return
        self._mode_pendente = None
        logger.info(
            "profile_mode_pendencia_aplicada",
            profile=pendencia.profile_name,
            kind=getattr(pendencia.mode, "kind", None),
            origin=pendencia.origin,
        )
        self.apply_profile_mode(
            pendencia.mode, profile=pendencia.profile, origin="pendencia"
        )

    def apply_profile_rumble_policy(
        self,
        policy: str | None,
        custom_mult: float | None = None,
        *,
        profile: Any | None = None,
        origin: str = "autoswitch",
    ) -> str:
        """Aplica a política de rumble de um perfil recém-ativado"""
        from hefesto_dualsense4unix.daemon.state_store import (
            MANUAL_PROFILE_LOCK_SEC,
        )

        now = time.monotonic()
        if origin == "manual":
            self._furar_lock_de_emulacao("rumble_policy", agora=now)
        elif now - self._emu_manual_ts < MANUAL_PROFILE_LOCK_SEC:
            if policy is not None:
                logger.info(
                    "profile_rumble_policy_skipped_manual_lock",
                    policy=policy,
                    remaining_sec=round(
                        MANUAL_PROFILE_LOCK_SEC - (now - self._emu_manual_ts), 1
                    ),
                )
            return ADIADO_LOCK_MANUAL

        if policy is None:
            if self._rumble_policy_from_profile:
                if self._perfil_e_catch_all(profile):
                    logger.info(
                        "profile_rumble_policy_revert_skipped",
                        motivo="catch_all_sem_opiniao",
                        profile=getattr(profile, "name", None),
                    )
                    return IGNORADO_CATCH_ALL
                if self._janela_de_jogo_em_foco():
                    logger.info(
                        "profile_rumble_policy_revert_skipped",
                        motivo="janela_de_jogo_em_foco",
                        profile=getattr(profile, "name", None),
                    )
                    return IGNORADO_JANELA_DE_JOGO
                before = self._rumble_policy_before_profile
                if before is not None:
                    self.config.rumble_policy = before[0]
                    self.config.rumble_policy_custom_mult = before[1]
                    logger.info(
                        "profile_rumble_policy_reverted",
                        policy=before[0],
                        mult=before[1],
                    )
                self._rumble_policy_from_profile = False
                self._rumble_policy_before_profile = None
                self._seed_rumble_mult_observability()
                self._reapply_rumble_policy_to_active()
            return APLICADO

        if policy not in RUMBLE_POLICIES:
            logger.warning("profile_rumble_policy_invalida", policy=policy)
            return FALHOU
        policy_lit = cast("RumblePolicy", policy)

        if not self._rumble_policy_from_profile:
            self._rumble_policy_before_profile = (
                self.config.rumble_policy,
                self.config.rumble_policy_custom_mult,
            )
        desired_mult = (
            max(0.0, min(2.0, float(custom_mult)))
            if custom_mult is not None
            else self.config.rumble_policy_custom_mult
        )
        changed = (
            self.config.rumble_policy != policy_lit
            or self.config.rumble_policy_custom_mult != desired_mult
        )
        self.config.rumble_policy = policy_lit
        self.config.rumble_policy_custom_mult = desired_mult
        self._rumble_policy_from_profile = True
        self._seed_rumble_mult_observability()
        if changed:
            logger.info(
                "profile_rumble_policy_applied",
                policy=policy_lit,
                mult=(
                    desired_mult
                    if policy_lit == "custom"
                    else RUMBLE_POLICY_MULT.get(policy_lit)
                ),
                custom_mult=desired_mult,
            )
            self._reapply_rumble_policy_to_active()
        return APLICADO

    def apply_profile_rumble_passthrough(self, passthrough: bool) -> None:
        """Aplica `rumble.passthrough` de um perfil recém-ativado (SPRINT-GAME-RUMBLE-01)."""
        if not passthrough:
            return
        if self.config.rumble_active is None:
            return
        soltos = soltar_os_que_vibram(self.config)
        if not soltos:
            return
        for dono in soltos:
            with contextlib.suppress(Exception):
                escrever_rumble_no_dono(self.controller, dono, 0, 0)
        logger.info("profile_rumble_passthrough_released")

    def apply_profile_speaker(
        self,
        volume: int,
        muted: bool = False,
        *,
        uniq: str | None = None,
        origin: str = "autoswitch",
        rota: int | None = None,
    ) -> str:
        """Aplica a seção `speaker` de um perfil recém-ativado (SOM-02/E4).

        Injetado como `speaker_applier` do `ProfileManager` nas rotas de
        ativação (IPC `profile.switch`, autoswitch, ciclo por hotkey e restore
        de boot) e consumido por `ProfileManager.apply_speaker` /
        `reapply_speaker_on_connect`, que já decidiram, ANTES de chegar aqui,
        que há opinião a aplicar: perfil sem a seção não chama este método (sem
        opinião é silêncio, não ordem — tomar a posse dos bytes de áudio por um
        perfil que não pediu nada é a queixa de que a configuração do usuário
        nunca é respeitada, do lado do som).

        POR QUE ISTO FALA DIRETO COM O BACKEND, e não pelo `speaker.set` do IPC
        (a armadilha desta entrega, e a razão de a chamada estar aqui e não lá):
        o handler `_handle_speaker_set` arma a categoria manual `"audio"`
        (`_marcar_audio_manual`, decisão da E3) — que é EXATAMENTE a trava que
        `ProfileManager.apply_speaker` consulta para NÃO escrever. Um applier de
        perfil que passasse por aquele caminho armaria a trava na primeira
        ativação e todas as seguintes seriam descartadas em silêncio: o perfil
        pararia de funcionar depois do primeiro uso. A trava é o registro de um
        gesto do usuário; perfil reaplicado não é gesto do usuário e não pode carimbá-la.

        Pelo mesmo eixo, o lock de 30 s de `_emu_manual_ts` (mouse/modo/política
        de rumble) NÃO é consultado aqui: o gesto manual de áudio tem trava
        própria, por categoria, e ela já foi consultada rio acima. Empilhar o
        lock de emulação faria mexer no mouse silenciar o volume do perfil por
        meio minuto, sem que ninguém tivesse tocado no som.

        `volume` é OBRIGATÓRIO e vai sempre junto do `muted` (armadilha 1,
        medida: `set_speaker_volume` sem volume e sem preferência guardada toma
        a posse e manda ZERO, publicando `{'volume': 0, 'muted': True}`). O
        esquema do perfil já recusa a seção sem volume e o manager faz
        `int(secao.volume)`; a guarda abaixo é a terceira cerca, para um dublê
        ou um chamador novo não conseguirem produzir a chamada vazia.

        Vocabulário de retorno (R-03): `APLICADO`, `IGNORADO_SEM_CONTROLE`
        (nenhum handle para o `uniq` — nada foi escrito e ninguém mentiu
        "aplicado") e `FALHOU`.

        `rota` é o CANAL de saída (SOM-ROTA-01) e vem do `speaker.rota` do
        perfil. `None` — o default, e o que todo perfil de antes desta linha
        carrega — quer dizer **não tocar no `common[7]`**: aquele byte guarda a
        rota de saída (bits 4-5) E o caminho do microfone (o resto), e
        escrevê-lo inteiro apagaria o caminho do mic em silêncio. Quem preserva
        os outros bits é o `_byte_da_rota` do backend, que lê o valor vigente
        do handle antes de trocar só os dois bits da rota.

        **E A ROTA 3 CHEGA AO APARELHO COMO 2** — 22/09/2026, a razão está no
        corpo. Só por aqui: o `speaker.set` do IPC continua escrevendo o 3.
        """
        if volume is None:
            logger.warning("profile_speaker_sem_volume_recusado", origin=origin)
            return FALHOU
        setter = getattr(self.controller, "set_speaker_volume", None)
        if not callable(setter):
            logger.debug("profile_speaker_backend_sem_suporte", origin=origin)
            return IGNORADO_SEM_CONTROLE
        # cartão dele sem botão aceso ao lado do P1 em «Sons do jogo». O 2 é o
        if rota == SAIDA_SO_NO_ALTO_FALANTE:
            logger.info("profile_speaker_rota_sem_botao", de=rota,
                        para=SAIDA_L_FONE_R_ALTO_FALANTE, uniq=uniq, origin=origin)
            rota = SAIDA_L_FONE_R_ALTO_FALANTE
        alvo = max(0, min(255, int(volume)))
        try:
            ok = bool(setter(alvo, muted=bool(muted), uniq=uniq, rota=rota))
        except Exception as exc:
            logger.warning(
                "profile_speaker_apply_failed",
                volume=alvo,
                muted=bool(muted),
                uniq=uniq,
                rota=rota,
                err=str(exc),
            )
            return FALHOU
        if not ok:
            logger.debug(
                "profile_speaker_sem_controle", uniq=uniq, origin=origin
            )
            return IGNORADO_SEM_CONTROLE
        logger.info(
            "profile_speaker_applied",
            volume=alvo,
            muted=bool(muted),
            uniq=uniq,
            rota=rota,
            origin=origin,
        )
        return APLICADO

    def apply_profile_mic(
        self,
        volume: int | None = None,
        muted: bool | None = None,
        *,
        uniq: str | None = None,
        origin: str = "autoswitch",
    ) -> str:
        """Aplica a seção `mic` de um perfil recém-ativado (18/08/2026).

        PERFIL-GUARDA-O-MIC-01. Injetado como `mic_applier` do `ProfileManager`
        e consumido por `ProfileManager.apply_mic`, que já decidiu, ANTES de
        chegar aqui: que há opinião a aplicar (perfil sem a seção não chama
        este método), que a trava manual de áudio não está armada, e se o
        `muted` atravessa. Desde a O-MUDO-E-DO-CONTROLE-01 o mudo é do controle
        e mora no `maquina.json`: ativação de perfil nenhuma o leva, e o único
        `muted` que chega aqui é o `True` do dono, pelo replug
        (`reapply_mic_on_connect`, `origin="replug"`). Aqui `muted=None`
        significa **não mexer no mudo**, e é o caso de toda ativação de perfil.

        DUAS CAMADAS, e por isso duas escritas separadas (a mesma separação que
        `mic.set` e `mic.volume.set` mantêm no IPC — juntá-las faria o produto
        prometer uma coisa e entregar outra):

        - `volume` tem DOIS DEGRAUS desde 09/09/2026 (MIC-VOLUME-02, decisão
          de produto `D-0909-O-VOLUME-DO-MIC-LIGA-O-BYTE-DO-APARELHO`): o ganho da
          FONTE de captura no PipeWire (camada 1) **e** o `common[6]` do
          aparelho, por `set_microphone_volume`. É a fonte no sistema que torna
          a feature universal — ela existe no cabo e no rádio —, e é o byte do
          aparelho que faz o número da tela ser o que a pessoa ouve do outro
          lado. **FATO SUBSTITUÍDO:** esta linha dizia que *"o DualSense não
          expõe registrador de ganho de microfone em transporte nenhum"*; o
          `hid-playstation` desta máquina NOMEIA o campo (`mic_volume`,
          `0x0 - 0x40`) e a bancada mediu a captura mudando com ele, no
          cabo (`docs/data/ensaios.csv`,
          `folha-mic-volume-o-byte-age-cabo-0909`).
          `sem_fonte` NÃO é falha — por Bluetooth sem a ponte de áudio de pé não
          existe fonte de captura nenhuma, e dizer "aplicado" ali seria mentir.
          **E o byte do aparelho só sai quando a fonte saiu**, de propósito: um
          "aplicado" pela metade é o que faz esta casa remedir o mesmo defeito.
        - `muted` é o mudo do FIRMWARE do controle (camada 3), o único que apaga
          a luz vermelha do microfone e o único que tira o botão físico dela
          enquanto vigora.

        POR QUE ISTO FALA DIRETO COM O BACKEND, e não pelos handlers do IPC:
        pela MESMA razão do `apply_profile_speaker` — `mic.set`/`mic.volume.set`
        armam a categoria manual `"audio"` (desde 18/08/2026), que é
        exatamente a trava que `ProfileManager.apply_mic` consulta para NÃO
        escrever. Um applier de perfil que passasse por lá armaria a trava na
        primeira ativação e todas as seguintes seriam descartadas em silêncio.
        A trava é o registro de um gesto do usuário; perfil reaplicado não é gesto
        do usuário e não pode carimbá-la.

        Vocabulário de retorno (R-03): `APLICADO`, `IGNORADO_SEM_CONTROLE`
        (não havia fonte de captura nem handle para escrever — nada foi feito e
        ninguém mentiu "aplicado") e `FALHOU`.
        """
        if volume is None and muted is None:
            logger.debug("profile_mic_sem_opiniao_noop", origin=origin)
            return IGNORADO_SEM_CONTROLE
        escreveu = False
        falhou = False
        if volume is not None:
            try:
                from hefesto_dualsense4unix.integrations.audio_control import (
                    definir_volume_da_captura,
                    fonte_de_captura_do_controle,
                    fonte_de_captura_do_uniq,
                )

                # com dois DualSense no cabo há DUAS placas de som
                fonte = (fonte_de_captura_do_uniq(uniq) if uniq
                         else fonte_de_captura_do_controle())
                if not fonte:
                    logger.debug("profile_mic_sem_fonte", origin=origin, uniq=uniq)
                elif definir_volume_da_captura(int(volume), fonte=fonte):
                    escreveu = True
                    aparelho = getattr(
                        getattr(self, "controller", None),
                        "set_microphone_volume", None)
                    if callable(aparelho):
                        with contextlib.suppress(Exception):
                            aparelho(int(volume), uniq=uniq)
                    logger.info(
                        "profile_mic_volume_applied",
                        volume=int(volume),
                        fonte=fonte,
                        origin=origin,
                    )
                else:
                    falhou = True
            except Exception as exc:
                falhou = True
                logger.warning(
                    "profile_mic_volume_apply_failed",
                    volume=volume,
                    origin=origin,
                    err=str(exc),
                )
        if muted is not None:
            setter = getattr(self.controller, "set_microphone_mute", None)
            if not callable(setter):
                logger.debug("profile_mic_backend_sem_suporte", origin=origin)
            else:
                try:
                    if bool(setter(bool(muted), uniq=uniq)):
                        escreveu = True
                        logger.info(
                            "profile_mic_mute_applied",
                            muted=bool(muted),
                            uniq=uniq,
                            origin=origin,
                        )
                    else:
                        logger.debug(
                            "profile_mic_sem_controle", uniq=uniq, origin=origin
                        )
                except Exception as exc:
                    falhou = True
                    logger.warning(
                        "profile_mic_mute_apply_failed",
                        muted=muted,
                        uniq=uniq,
                        origin=origin,
                        err=str(exc),
                    )
        if escreveu:
            return APLICADO
        return FALHOU if falhou else IGNORADO_SEM_CONTROLE

    def mark_rumble_policy_manual(self) -> None:
        """Registra gesto MANUAL na política de rumble"""
        self._emu_manual_ts = time.monotonic()
        self._rumble_policy_from_profile = False
        self._rumble_policy_before_profile = None

    def _seed_rumble_mult_observability(self) -> None:
        """Sincroniza `_last_auto_mult` com o mult efetivo da política vigente.

        MISC-08 item 1 (2026-07-18): `daemon._last_auto_mult` é a fonte do
        `rumble_mult_applied` do state_full, mas só era atualizado quando um
        caminho de rumble de fato COMPUTAVA (`reassert_rumble` exige rumble
        fixado; `_game_rumble_mult` exige FF do jogo). Em passthrough ocioso,
        aplicar um perfil com política fixa deixava o campo preso no default
        0.7 — ao vivo, `policy=max` + `rumble_mult_applied=0.7` no state_full
        parecia atenuação real do rumble do jogo. Política "auto" fica de
        fora de propósito: o valor dela é resolvido por bateria (com
        debounce) no próximo cômputo.
        """
        policy = self.config.rumble_policy
        if policy == "custom":
            self._last_auto_mult = float(self.config.rumble_policy_custom_mult)
        elif policy in RUMBLE_POLICY_MULT:
            self._last_auto_mult = RUMBLE_POLICY_MULT[policy]

    def _reapply_rumble_policy_to_active(self) -> None:
        """Re-aplica a política vigente ao rumble ATIVO (efeito imediato)."""
        active = self.config.rumble_active
        if active is None:
            return
        from hefesto_dualsense4unix.daemon.ipc_rumble_policy import (
            apply_rumble_policy,
        )

        with contextlib.suppress(Exception):
            eff_weak, eff_strong = apply_rumble_policy(self, active[0], active[1])
            escrever_rumble_no_dono(
                self.controller,
                self.config.rumble_active_uniq,
                eff_weak,
                eff_strong,
            )

    def _flush_emulation_devices(self) -> None:
        """Solta todas as teclas/botões dos devices virtuais (mouse+teclado)."""
        kbd = self._keyboard_device
        if kbd is not None:
            with contextlib.suppress(Exception):
                kbd.dispatch(frozenset())
        mouse = self._mouse_device
        if mouse is not None:
            with contextlib.suppress(Exception):
                mouse.dispatch(
                    lx=128, ly=128, rx=128, ry=128, l2=0, r2=0, buttons=frozenset()
                )


    def _start_hotkey_manager(self) -> None:
        """Thin wrapper — backcompat para testes que chamam daemon._start_hotkey_manager()."""
        from hefesto_dualsense4unix.daemon.subsystems.hotkey import start_hotkey_manager

        start_hotkey_manager(self)

    def _stop_hotkey_manager(self) -> None:
        """Thin wrapper — backcompat."""
        from hefesto_dualsense4unix.daemon.subsystems.hotkey import stop_hotkey_manager

        stop_hotkey_manager(self)

    def _start_mouse_emulation(self) -> bool:
        """Thin wrapper — backcompat."""
        from hefesto_dualsense4unix.daemon.subsystems.mouse import start_mouse_emulation

        return start_mouse_emulation(self)

    def _stop_mouse_emulation(self) -> None:
        """Thin wrapper — backcompat."""
        from hefesto_dualsense4unix.daemon.subsystems.mouse import stop_mouse_emulation

        stop_mouse_emulation(self)

    def _start_gamepad_emulation(self) -> bool:
        """Thin wrapper — gamepad virtual (FEAT-DSX-GAMEPAD-FLAVOR-01)."""
        from hefesto_dualsense4unix.daemon.subsystems.gamepad import start_gamepad_emulation

        return start_gamepad_emulation(
            self,
            flavor=self.config.gamepad_flavor,
            origin="profile",
            caminho=getattr(self, "_caminho_do_boot", None),
        )

    def _stop_gamepad_emulation(self) -> None:
        """Thin wrapper — para o gamepad virtual e libera o grab."""
        from hefesto_dualsense4unix.daemon.subsystems.gamepad import stop_gamepad_emulation

        stop_gamepad_emulation(self)

    def _dispatch_gamepad_emulation(self, state: Any, buttons_pressed: frozenset[str]) -> None:
        """Thin wrapper — chamado pelo poll loop a cada tick."""
        from hefesto_dualsense4unix.daemon.subsystems.gamepad import dispatch_gamepad

        dispatch_gamepad(self, state, buttons_pressed)

    def _start_keyboard_emulation(self) -> bool:
        """Thin wrapper — wire-up A-07 para FEAT-KEYBOARD-EMULATOR-01."""
        from hefesto_dualsense4unix.daemon.subsystems.keyboard import start_keyboard_emulation

        return start_keyboard_emulation(self)

    def _stop_keyboard_emulation(self) -> None:
        """Thin wrapper — backcompat e cleanup."""
        from hefesto_dualsense4unix.daemon.subsystems.keyboard import stop_keyboard_emulation

        stop_keyboard_emulation(self)

    def _dispatch_keyboard_emulation(self, buttons_pressed: frozenset[str]) -> None:
        """Thin wrapper — chamado pelo poll loop a cada tick."""
        from hefesto_dualsense4unix.daemon.subsystems.keyboard import dispatch_keyboard

        dispatch_keyboard(self, buttons_pressed)

    def _prime_keyboard_emulation(self, buttons_pressed: frozenset[str]) -> None:
        """Thin wrapper — semeia o edge-tracker do teclado sem emitir."""
        from hefesto_dualsense4unix.daemon.subsystems.keyboard import prime_keyboard

        prime_keyboard(self, buttons_pressed)

    def _reassert_rumble(self, now: float) -> None:
        """Thin wrapper — backcompat e chamado pelo poll loop."""
        from hefesto_dualsense4unix.daemon.subsystems.rumble import reassert_rumble

        reassert_rumble(self, now)

    async def _start_ipc(self) -> None:
        from hefesto_dualsense4unix.daemon.subsystems.ipc import start_ipc

        await start_ipc(self)

    async def _start_udp(self) -> None:
        from hefesto_dualsense4unix.daemon.subsystems.udp import start_udp

        await start_udp(self)

    async def _start_autoswitch(self) -> None:
        from hefesto_dualsense4unix.daemon.subsystems.autoswitch import start_autoswitch

        await start_autoswitch(self)

    def _start_mic_hotkey(self) -> None:
        """Thin wrapper — backcompat."""
        from hefesto_dualsense4unix.daemon.subsystems.hotkey import start_mic_hotkey

        start_mic_hotkey(self)

    async def _start_plugins(self) -> None:
        """Inicializa o PluginsSubsystem se ``plugins_enabled`` (``hefesto plugin ligar``)."""
        from hefesto_dualsense4unix.daemon.context import DaemonContext
        from hefesto_dualsense4unix.daemon.subsystems.plugins import PluginsSubsystem

        ps = PluginsSubsystem()
        if not ps.is_enabled(self.config):
            return

        ctx = DaemonContext(
            controller=self.controller,
            bus=self.bus,
            store=self.store,
            config=self.config,
            executor=self._executor,
        )
        await ps.start(ctx)
        self._plugins_subsystem = ps

    async def _stop_plugins(self) -> None:
        """Para o PluginsSubsystem de forma limpa."""
        if self._plugins_subsystem is not None:
            await self._plugins_subsystem.stop()
            self._plugins_subsystem = None

    async def _start_metrics(self) -> None:
        """Inicializa o MetricsSubsystem se metrics_enabled (FEAT-METRICS-01)."""
        from hefesto_dualsense4unix.daemon.context import DaemonContext
        from hefesto_dualsense4unix.daemon.subsystems.metrics import MetricsSubsystem

        ms = MetricsSubsystem()
        if not ms.is_enabled(self.config):
            return

        ctx = DaemonContext(
            controller=self.controller,
            bus=self.bus,
            store=self.store,
            config=self.config,
            executor=self._executor,
        )
        await ms.start(ctx)
        self._metrics_subsystem = ms

    async def _start_bt_mic(self) -> None:
        """Sobe o BtMicSubsystem se o opt-in estiver ligado (BT-MIC-REGISTRY-01)."""
        from hefesto_dualsense4unix.daemon.context import DaemonContext
        from hefesto_dualsense4unix.daemon.subsystems.bt_mic import BtMicSubsystem

        # pede o `player_slot` ao `identity_registry` — e quem tem o registro é
        bm = BtMicSubsystem(daemon=self)
        if not bm.is_enabled(self.config):
            return

        ctx = DaemonContext(
            controller=self.controller,
            bus=self.bus,
            store=self.store,
            config=self.config,
            executor=self._executor,
        )
        await bm.start(ctx)
        self._bt_mic_subsystem = bm

    async def _start_alto_falante(self) -> None:
        """Sobe o nó de som de cada DualSense — SOM-FIADO-01 (10/09/2026).

        POR QUE ELE FICOU FORA ATÉ HOJE, e os dois motivos MORRERAM
        -----------------------------------------------------------
        `daemon/subsystems/__init__.py` registrava a razão: o subsystem
        publicava um `module-null-sink` por controle e **nenhum
        `module-loopback`** — quatro entradas mudas na lista de som do usuário.

        * a rota do CABO chegou em 09/09 (SOM-POR-CONTROLE-01): o nó recebe
          uma `RotaDoNo` e sobe o `module-loopback` junto quando ela existe;
        * a rota do RÁDIO chegou em 10/09: o som saiu de verdade pelo report
          `0x35`, e `AltoFalanteSubsystem._casar_as_pontes` constrói uma
          `PonteDeSomPorRadio` por controle;
        * e a guarda que fecha o par vive em `GerenciadorDeNosDeSom.
          reconciliar`: **sem rota, sem nó**. Quem não entrega não é
          publicado, então o sumidouro não pode nascer nem por acidente.

        A régua que trava tudo isto é
        `tests/unit/test_o_no_de_som_nao_nasce_sumidouro.py`, e ela mede o
        PRODUTO — sobe um `Daemon` de verdade e conta o que foi ao `pactl`.

        Espelha `_start_bt_mic`: um erro aqui vira
        `_failed_subsystems["alto_falante"]` pelo `_safe_start` do chamador, e
        o boot segue. Som que não sobe não pode derrubar o resto da mesa.
        """
        from hefesto_dualsense4unix.daemon.context import DaemonContext
        from hefesto_dualsense4unix.daemon.subsystems.alto_falante import (
            AltoFalanteSubsystem,
        )

        af = AltoFalanteSubsystem(daemon=self)
        if not af.is_enabled(self.config):
            return

        ctx = DaemonContext(
            controller=self.controller,
            bus=self.bus,
            store=self.store,
            config=self.config,
            executor=self._executor,
        )
        await af.start(ctx)
        self._alto_falante_subsystem = af

    async def _stop_alto_falante(self) -> None:
        """Derruba os nós de som e as pontes de rádio. Idempotente."""
        if self._alto_falante_subsystem is not None:
            subsystem = self._alto_falante_subsystem
            self._alto_falante_subsystem = None
            await subsystem.stop()

    async def _start_conexoes(self) -> None:
        """Sobe o vigia das conexões de rádio (CONEXAO-ZUMBI-01)."""
        from hefesto_dualsense4unix.daemon.context import DaemonContext
        from hefesto_dualsense4unix.daemon.subsystems.conexoes import (
            ConexoesSubsystem,
        )

        vigia = ConexoesSubsystem()
        if not vigia.is_enabled(self.config):
            return
        ctx = DaemonContext(
            controller=self.controller,
            bus=self.bus,
            store=self.store,
            config=self.config,
            executor=self._executor,
        )
        await vigia.start(ctx)
        self._conexoes_subsystem = vigia

    async def _stop_conexoes(self) -> None:
        """Para o vigia das conexões. Idempotente."""
        if self._conexoes_subsystem is not None:
            subsystem = self._conexoes_subsystem
            self._conexoes_subsystem = None
            await subsystem.stop()

    async def _stop_bt_mic(self) -> None:
        """Para o BtMicSubsystem (DESLIGA o mic de cada controle). Idempotente."""
        if self._bt_mic_subsystem is not None:
            subsystem = self._bt_mic_subsystem
            self._bt_mic_subsystem = None
            await subsystem.stop()

    async def reconciliar_bt_mic(self) -> None:
        """Casa o subsystem com o que a declaração da mesa pede AGORA."""
        from hefesto_dualsense4unix.daemon.subsystems.bt_mic import BtMicSubsystem

        quer = BtMicSubsystem().is_enabled(self.config)
        try:
            if quer and self._bt_mic_subsystem is None:
                await self._start_bt_mic()
            elif not quer and self._bt_mic_subsystem is not None:
                await self._stop_bt_mic()
        except Exception as exc:
            logger.warning("bt_mic_reconciliacao_de_gesto_falhou", err=str(exc))

    async def _stop_metrics(self) -> None:
        """Para o MetricsSubsystem de forma limpa. Idempotente."""
        if self._metrics_subsystem is not None:
            await self._metrics_subsystem.stop()
            self._metrics_subsystem = None

    async def _safe_start(self, name: str, starter: Callable[[], Any]) -> None:
        """Inicia um subsystem isolando falhas (FEAT-DAEMON-RESILIENT-SUBSYSTEMS-01)."""
        try:
            result = starter()
            if inspect.isawaitable(result):
                await result
        except Exception as exc:
            self._failed_subsystems[name] = str(exc)
            logger.error(
                "subsystem_start_failed", subsystem=name, err=str(exc), exc_info=True
            )

    def _audit_config_on_boot(self) -> None:
        """Valida os perfis no boot e avisa o usuário se houver corrompidos"""
        try:
            from hefesto_dualsense4unix.profiles.loader import audit_profiles

            invalid = audit_profiles()
            if not invalid:
                return
            logger.warning(
                "config_audit_invalid_profiles",
                count=len(invalid),
                profiles=[name for name, _err in invalid],
            )
        except Exception as exc:
            logger.debug("config_audit_failed", err=str(exc))

    def _check_system_on_boot(self) -> None:
        """Detecta problemas de infra no boot (udev/WirePlumber) e AVISA o comando
        de reparo (FEAT-SYSTEM-AUTOREPAIR-BOOT-01). Nunca roda sudo/reparo sozinho.
        Best-effort: nunca derruba o boot.

        O aviso é só o log em `warning` (`journalctl --user -u
        hefesto-dualsense4unix.service | grep system_check_warning`): a
        notificação na área de trabalho saiu em 02/10/2026 com a chave que a
        ligava, que nada escrevia (OS-INTERRUPTORES-QUE-NINGUEM-LIGA-01).
        """
        try:
            from hefesto_dualsense4unix.core.system_check import system_warnings

            infra_warnings = system_warnings()
            if not infra_warnings:
                return
            for detail in infra_warnings:
                logger.warning("system_check_warning", detail=detail)
        except Exception as exc:
            logger.debug("system_check_failed", err=str(exc))

    def _evdev_buttons_once(self) -> frozenset[str]:
        """Thin wrapper — backcompat para testes que acessam o método diretamente."""
        from hefesto_dualsense4unix.daemon.subsystems.poll import evdev_buttons_once

        return evdev_buttons_once(self)

    def _dispatch_mouse_emulation(self, state: Any, buttons_pressed: frozenset[str]) -> None:
        """Thin wrapper — backcompat para testes que acessam o método diretamente."""
        from hefesto_dualsense4unix.daemon.subsystems.mouse import dispatch_mouse

        dispatch_mouse(self, state, buttons_pressed)

    # ------------------------------------------------------------------
    # Identidade dos controles (COR-01/COR-03)
    # ------------------------------------------------------------------

    def _wire_identity_registry(self) -> None:
        """Cria o registro de identidade e injeta o provider de cor no backend.

        COR-01/COR-03: SÓ quando o backend suporta a injeção
        (`set_auto_output_provider` — o PyDualSenseController real). Com o
        FakeController fica tudo desligado: `identity_registry` permanece
        None, nenhum `controllers.json` é lido/escrito e o reconcile do poll
        loop é no-op — testes/smoke herméticos por construção. Best-effort:
        falha aqui loga warning e o daemon segue (LEDs caem no broadcast
        histórico).
        """
        if not hasattr(self.controller, "set_auto_output_provider"):
            return
        try:
            from hefesto_dualsense4unix.daemon.subsystems.identity import (
                get_identity_registry,
                make_auto_output_provider,
            )

            registry = get_identity_registry()
            registry.load()
            self.identity_registry = registry
            self.controller.set_auto_output_provider(
                make_auto_output_provider(registry)
            )
            logger.info("identity_registry_wired")
        except Exception as exc:
            logger.warning("identity_registry_wire_failed", err=str(exc))

    def _sync_identity_registry(self) -> None:
        """Reconcilia o registro com os controles conectados (tick lento ~2s).

        COR-01 (D2): marca desconectados (slot vira RESERVA do MAC) — por isso
        roda TAMBÉM offline (o gate de `is_connected` do poll loop não pode
        engolir a transição para zero controles). Fonte do conjunto:
        `describe_controllers` do backend (getattrs baratos, sem HID I/O) —
        nunca no caminho quente por evento. No-op sem registro (backend fake)
        ou sem a API.

        R-24 (auditoria 25/07): a ORDEM importa agora. O `sync_connected`
        passou a ATRIBUIR slot a quem chegou sem número (era só o provider de
        cor que atribuía, e enquanto ele não rodava o piso lido pelos
        EXTERNOS valia 0 — o Pro Nintendo abocanhava o slot 1 e os DualSense
        nasciam 2 e 3). Isto aqui montava um `set`, que numeraria por hash;
        agora entrega a ordem de `describe_controllers` (primário primeiro),
        que é a mesma ordem que a GUI e a CLI listam.
        """
        registry = self.identity_registry
        if registry is None:
            return
        describe = getattr(self.controller, "describe_controllers", None)
        if not callable(describe):
            return
        try:
            infos = describe()
            uniqs = [
                info["uniq"]
                for info in infos
                if isinstance(info, dict)
                and info.get("connected")
                and isinstance(info.get("uniq"), str)
            ]
            registry.sync_connected(uniqs)
        except Exception as exc:
            logger.debug("identity_sync_falhou", err=str(exc))

    def _seguir_a_carta(self) -> None:
        """O primário segue a carta 1, no tique lento (O-MODO-XBOX-NAO-E-QUEDA-02)."""
        seguir = getattr(self.controller, "seguir_a_carta", None)
        if not callable(seguir):
            return
        try:
            seguir()
        except Exception as exc:
            logger.warning("seguir_a_carta_falhou", err=str(exc))

    def _amostrar_bateria(self, agora: float) -> None:
        """Sonda a carga de cada controle e deixa no journal o que valer linha."""
        describe = getattr(self.controller, "describe_controllers", None)
        if not callable(describe):
            return
        try:
            infos = describe()
            if not isinstance(infos, list):
                return
            diario_da_bateria(self).observar(infos, agora)
        except Exception as exc:
            logger.debug("bateria_amostra_falhou", err=str(exc))


    def _wire_external_registry(self) -> None:
        """Cria o registro de externos + o aplicador de LED do tick lento."""
        if self.identity_registry is None:
            return
        try:
            from hefesto_dualsense4unix.daemon.subsystems.external_identity import (
                ExternalIdentityRegistry,
                ExternalLedSync,
            )

            registry = ExternalIdentityRegistry()
            registry.load()
            self.external_registry = registry
            self._external_led_sync = ExternalLedSync(self, registry)
            # EXT-04: numeração global ÚNICA — o registro dos DualSense passa a
            # DualSense novo (evita duas frentes acenderem o mesmo "Controle
            # leem do lado DualSense; ninguém renumera quem já tem slot.
            self.identity_registry.set_external_reserve_provider(
                lambda: set(registry.snapshot().values())
            )
            logger.info("external_registry_wired")
        except Exception as exc:
            logger.warning("external_registry_wire_failed", err=str(exc))

    def _schedule_external_tick(self) -> None:
        """Agenda o tick de LED dos externos como TASK auxiliar (HANG-01)."""
        if self._external_led_sync is None:
            return
        if self._external_tick_degraded:
            watch = self._external_tick_watch
            if watch is None:
                from hefesto_dualsense4unix.core.evdev_reader import InputDirWatch

                watch = InputDirWatch()
                self._external_tick_watch = watch
                watch.poll()
                return
            if not watch.poll():
                return
            logger.info("external_tick_recuperado", motivo="input_dir_change")
            self._external_tick_degraded = False
            self._external_tick_timeouts = 0
        task = self._external_tick_task
        if task is not None and not task.done():
            self._external_tick_skipped += 1
            return
        self._external_tick_task = asyncio.create_task(
            self._sync_external_leds(), name="external_led_tick"
        )

    async def _sync_external_leds(self) -> None:
        """Corpo da TASK do tick de LED dos externos (HANG-01)."""
        sync = self._external_led_sync
        if sync is None:
            return
        try:
            await asyncio.wait_for(
                self._run_external_blocking(sync.tick),
                timeout=EXTERNAL_TICK_TIMEOUT_SEC,
            )
        except asyncio.TimeoutError:
            self._external_tick_timeouts += 1
            log = (
                logger.warning
                if self._external_tick_timeouts == 1
                else logger.error
            )
            log(
                "external_tick_pendurado",
                timeout_sec=EXTERNAL_TICK_TIMEOUT_SEC,
                consecutivos=self._external_tick_timeouts,
            )
            if self._external_tick_timeouts >= EXTERNAL_TICK_MAX_TIMEOUTS:
                self._external_tick_degraded = True
                logger.info(
                    "external_tick_degradado",
                    consecutivos=self._external_tick_timeouts,
                    instrucao=(
                        "inventário de externos congelado até o próximo "
                        "hotplug em /dev/input; ver doctor/reiniciar o serviço"
                    ),
                )
        except Exception as exc:
            logger.debug("external_led_sync_falhou", err=str(exc))
        else:
            self._external_tick_timeouts = 0


    @property
    def appid_em_cena(self) -> int | None:
        """O appid do jogo aberto AGORA, com o jogo na autoridade; senão ``None``."""
        if self.display_authority != "game":
            return None
        appid = self._appid_da_evidencia
        return appid if isinstance(appid, int) and appid > 0 else None

    @property
    def display_authority(self) -> str:
        """Autoridade de exibição CORRENTE ('game'|'daemon'|'unknown')."""
        signal = self._game_signal
        return signal.authority if signal is not None else "unknown"

    def _wire_game_signal(self) -> None:
        """Cria o `GameSignal` (NUMA-01) e injeta a autoridade no backend real."""
        from hefesto_dualsense4unix.daemon.subsystems.game_signal import GameSignal

        self._game_signal = GameSignal()
        if not hasattr(self.controller, "set_game_authority_provider"):
            return
        try:
            self.controller.set_game_authority_provider(
                lambda: self._game_signal.authority
            )
            logger.info("game_signal_wired")
        except Exception as exc:
            logger.warning("game_signal_wire_failed", err=str(exc))

    def _wire_feature_opener(self) -> None:
        """S-5: injeta o opener broker-aware no backend p/ a calibração 0x05."""
        if not hasattr(self.controller, "set_feature_opener"):
            return
        try:
            from hefesto_dualsense4unix.integrations.hidraw_broker_client import (
                make_broker_opener,
            )

            self.controller.set_feature_opener(make_broker_opener(self))
            logger.info("feature_opener_wired")
        except Exception as exc:
            logger.warning("feature_opener_wire_failed", err=str(exc))

    def _wire_exposicao_do_no(self) -> None:
        """O-NO-NASCE-FECHADO-01: injeta a fábrica de exposição no backend."""
        if not hasattr(self.controller, "set_exposicao_do_no"):
            return
        try:
            from hefesto_dualsense4unix.integrations.hidraw_broker_client import (
                make_exposicao_factory,
            )

            self.controller.set_exposicao_do_no(make_exposicao_factory(self))
            logger.info("exposicao_do_no_wired")
        except Exception as exc:
            logger.warning("exposicao_do_no_wire_failed", err=str(exc))

    def _nos_do_modo_nativo_vivos(self) -> set[str]:
        """Os nós que a exposição do Modo Nativo segura AGORA. Dono único."""
        nos = getattr(self, "_nos_do_modo_nativo", None)
        if not isinstance(nos, set):
            nos = set()
            self._nos_do_modo_nativo = nos
        return nos

    def no_exposto_pelo_modo_nativo(self, path: str) -> bool:
        """`path` está aberto por causa do Modo Nativo, e tem de continuar?

        Quem pergunta é o `make_exposicao_factory`, a fábrica do `with` que o
        `_open_one` do backend usa para abrir o handle de controle
        (`hidapi.Device(path=…)`, que não aceita fd).

        POR QUE A PERGUNTA EXISTE. A lease de exposição do broker é por
        CONEXÃO: o pedido do Modo Nativo e o `with` transitório do `_open_one`
        saem do MESMO cliente, logo da mesma conexão, logo do mesmo `held`. O
        `unexpose` do `finally` acharia o nó no `held`, veria `refcount == 1`
        e mandaria o nó para o REPOUSO — fechando, no meio do Modo Nativo, o
        nó que o jogo está usando. A reconciliação do tique reabriria em até
        2 s, e 2 s é exatamente a janela que a Steam usa.

        Então o `with` vira no-op quando o nó já está aberto pelo modo: não
        expõe (já está) e não desexpõe (não foi ele que pediu).
        """
        return path in self._nos_do_modo_nativo_vivos()

    @staticmethod
    def _no_de_fisico_esta_aberto(no: str) -> bool:
        """O nó responde a QUEM VAI ABRIR — o jogo, com o uid dela."""
        from hefesto_dualsense4unix.integrations.hidraw_broker_client import (
            nos_de_entrada_do_hidraw,
        )

        try:
            if not os.access(no, os.R_OK | os.W_OK):
                return False
            return all(
                os.access(entrada, os.R_OK | os.W_OK)
                for entrada in nos_de_entrada_do_hidraw(no)
            )
        except OSError:
            return False

    def _exposicao_do_modo_nativo(self, ligar: bool) -> None:
        """Abre (ou solta) o físico para o JOGO enquanto o Modo Nativo dura."""
        self._reconciliar_exposicao_do_modo_nativo(ligar=ligar)

    def _reconciliar_exposicao_do_modo_nativo(
        self, *, ligar: bool | None = None
    ) -> None:
        """A exposição do Modo Nativo segue o APARELHO, não o instante.

        AUDITORIA DA O-NO-NASCE-FECHADO-01 (20/09/2026), bloqueantes 1 e 2 —
        e os dois eram o MESMO defeito: a exposição era um ato único, disparado
        pelo gesto de ligar o modo. Um ato único não sobrevive a nada.

        1. **Não sobrevivia a REINICIAR o daemon.** No boot, `start()` lê o
           modo do disco (`load_native_mode`) e escreve o flag direto em
           `_native_mode` + `store` — `set_native_mode()` NÃO é chamado, e o
           early-return de idempotência dele (`if enabled == self._native_mode`)
           faz com que religar o modo pela tela também não chame. Resultado
           com a cura instalada: rebootar em Modo Nativo deixava o nó
           `0600 root` e o jogo levava `EACCES`, sem conserto pela interface.
        2. **Não sobrevivia a um REPLUG.** A lease apontava para um
           `/dev/hidrawN` CONCRETO. Cabo↔rádio, hub, controle que dorme: o nó
           renasce fechado pela regra udev e não há notificação udev→broker.
           Se o número mudasse, a lease ficava pendurada num nó morto; se
           fosse o mesmo, a contabilidade do broker seguia dizendo «exposto».

        A CURA NÃO PRECISOU DE PEÇA NOVA, e é por isso que ela cabe aqui: quem
        já sabe do aparelho a cada 2 s é o `_poll_loop`, e quem já reaplica a
        ACL sem acreditar em memória é o próprio broker — o `_cmd_expose`
        SEMPRE confere o fs e escreve o que difere antes de contabilizar («um
        nó recriado com o mesmo `hidrawN` nasceu FECHADO pela regra udev, e o
        estado em memória não é prova de nada»). Faltava alguém PERGUNTAR de
        novo. É este laço.

        TRÊS ATOS, nesta ordem, e nenhum é o mesmo:
          1. SOLTAR o que saiu da mesa — ou tudo, quando o modo desliga;
          2. EXPOR o que entrou;
          3. REAFIRMAR o que renasceu fechado — medido no nó (`os.access`),
             não na lembrança. Sem isto o replug que devolve o MESMO número
             passa despercebido.

        O custo por tique com tudo em ordem: um `os.access` por controle. O
        `_logar_transicao` do cliente já rebaixa reafirmação a `debug`, então
        isto não volta a encher o journal como o `hidraw_broker_hidden` de
        15/08 (717 linhas em 2 h 51).

        Best-effort integral: broker ausente ⇒ nada acontece e o modo segue
        (numa máquina sem a cura, o nó já está aberto).
        """
        with contextlib.suppress(Exception):
            if ligar is None:
                ligar = bool(getattr(self, "_native_mode", False))
            segurados = self._nos_do_modo_nativo_vivos()
            anteriores = set(segurados)
            alvo: set[str] = set()
            if ligar:
                nos_fn = getattr(self.controller, "nos_hidraw_por_uniq", None)
                if callable(nos_fn):
                    alvo = {
                        no
                        for no in (nos_fn() or {}).values()
                        if isinstance(no, str) and no.startswith("/dev/hidraw")
                    }
            if not alvo and not anteriores:
                return
            from hefesto_dualsense4unix.integrations.hidraw_broker_client import (
                broker_call_nonblocking,
                broker_client_for,
            )

            client = broker_client_for(self)

            def _pedido(no_alvo: str, expor: bool) -> Any:
                """Fecha sobre `no_alvo` de VERDADE — a lambda no laço não fecha."""
                if expor:
                    return lambda: client.expor(no_alvo, entradas=True)
                return lambda: client.desexpor(no_alvo)

            segurados.clear()
            segurados.update(alvo)
            for no in sorted(anteriores - alvo):
                broker_call_nonblocking(self, _pedido(no, False))
            for no in sorted(alvo - anteriores):
                broker_call_nonblocking(self, _pedido(no, True))
            for no in sorted(alvo & anteriores):
                if self._no_de_fisico_esta_aberto(no):
                    continue
                broker_call_nonblocking(self, _pedido(no, True))

    def _any_game_session_open(self) -> bool:
        """Agregado `game_open` de TODOS os vpads (P1 + co-op, NUMA-01)."""
        vpads: list[Any] = []
        primary = self._gamepad_device
        if primary is not None:
            vpads.append(primary)
        players = getattr(self._coop_manager, "_players", None)
        if isinstance(players, dict):
            for player in players.values():
                vpad = getattr(player, "vpad", None)
                if vpad is not None:
                    vpads.append(vpad)
        return any(bool(getattr(vpad, "game_open", False)) for vpad in vpads)

    def _manager_de_selecao(self) -> Any:
        """`ProfileManager` de LEITURA do daemon, cacheado (MODO-01/B5)."""
        if self._profile_selector is None:
            from hefesto_dualsense4unix.profiles.manager import ProfileManager

            self._profile_selector = ProfileManager(
                controller=self.controller, store=self.store
            )
        return self._profile_selector

    def _profile_rule_matches_game(
        self,
        wm_class: str | None,
        wm_name: str | None = None,
        exe_basename: str | None = None,
    ) -> bool:
        """NUMA-01 evidência #2: a janela corrente casa regra de jogo do
        autoswitch (`mode.kind == "gamepad"`, match ESPECÍFICO — não o
        `MatchAny` catch-all do perfil fallback). Cobre GOG/Heroic fora da
        Steam pelo MESMO mecanismo de seleção do autoswitch
        (`ProfileManager.select_for_window`). Best-effort: qualquer falha
        ao carregar perfis do disco devolve False — o chamador
        (`_gather_game_signal_inputs`) já roda protegido por try/except no
        tick.

        SINAL-DE-JOGO-01 (31/07): a pergunta passou a levar a janela INTEIRA.
        Ela chegava aqui com `wm_class` e mais nada, e o `MatchCriteria` é um E
        entre os campos preenchidos com alvo ausente reprovando por decisão
        escrita (`profiles/schema.py`, `_casa_sem_caixa`) — então qualquer perfil
        com `window_title_regex` ou `process_name` devolvia False SEMPRE, sem
        erro nenhum. Medido nos 15 perfis do disco do usuário: dos seis perfis de jogo,
        um só casava aqui, e por uma `wm_class` `steam_app_*` que a evidência
        nº 1 já pegava sozinha — a evidência nº 2 era letra morta.

        Tradeoff registrado (o mesmo que a AUTOMATISMO-MORTO-01 discute no
        cadeado, por outra porta): com o título valendo, um regex solto de
        título passa a poder declarar "é jogo" a partir de uma janela que não é
        jogo — medido no disco do usuário, uma aba de navegador chamada "Portal 2"
        casa o `coop_local` (prioridade 75, `mode: gamepad`, só título) e vence
        o `Navegação` (prioridade 50). Aqui o consumidor é o sinal de EXIBIÇÃO,
        não a troca de perfil; quem quiser fechar isso mexe no perfil, não neste
        probe.
        """
        if not (wm_class or wm_name or exe_basename):
            return False
        janela: dict[str, object] = {"wm_class": wm_class or ""}
        if wm_name:
            janela["wm_name"] = wm_name
        if exe_basename:
            janela["exe_basename"] = exe_basename
        profile = self._manager_de_selecao().select_for_window(janela)
        if profile is None:
            return False
        mode = getattr(profile, "mode", None)
        match = getattr(profile, "match", None)
        return (
            mode is not None
            and getattr(mode, "kind", None) == "gamepad"
            and getattr(match, "type", None) == "criteria"
        )

    def _gather_game_signal_inputs(self) -> dict[str, Any]:
        """Reúne TODA evidência de `classify()` (NUMA-01) — roda no executor."""
        from hefesto_dualsense4unix.daemon.launch_env import (
            pid_is_alive,
            read_last_exit_marker,
            read_last_exit_pid,
            read_last_run_marker,
            read_last_run_pid,
        )
        from hefesto_dualsense4unix.integrations.steam_launch_options import (
            steam_game_running_appid,
        )

        mono_now = time.monotonic()
        window_healthy = self.store.window_detect_healthy
        window_class_current = self.store.window_detect_current_class
        window_name_current = self.store.window_detect_current_name
        window_exe_current = self.store.window_detect_current_exe
        seen_at = self.store.game_window_seen_at
        window_seen_age = (mono_now - seen_at) if seen_at is not None else None
        marker = read_last_run_marker()
        marker_pid = read_last_run_pid()
        exit_marker = read_last_exit_marker()
        exit_pid = read_last_exit_pid()
        marker_pid_alive = pid_is_alive(marker_pid)
        return {
            "window_healthy": window_healthy,
            "window_class_current": window_class_current,
            "window_seen_age": window_seen_age,
            "profile_rule_match": self._profile_rule_matches_game(
                window_class_current, window_name_current, window_exe_current
            ),
            "marker": marker,
            "marker_pid_alive": marker_pid_alive,
            "marker_pid": marker_pid,
            "exit_marker": exit_marker,
            "exit_pid": exit_pid,
            "appid_de_jogo_vivo": steam_game_running_appid(),
            "session_open": self._any_game_session_open(),
            "now": time.time(),
        }

    async def _sync_game_signal(self) -> None:
        """Tick lento (~2s) do sinal "jogo real ativo" (NUMA-01)."""
        signal = self._game_signal
        if signal is None:
            return
        from hefesto_dualsense4unix.daemon.subsystems.game_signal import classify

        anterior = signal.authority
        try:
            inputs = await self._run_blocking(self._gather_game_signal_inputs)
        except Exception as exc:
            logger.warning("game_signal_degradado", motivo=str(exc))
            signal.mark_degraded(str(exc))
            self._appid_da_evidencia = None
        else:
            raw = classify(**inputs)
            signal.evaluate(raw, session_open=bool(inputs["session_open"]))
            self._appid_da_evidencia = _o_appid_da_evidencia(inputs)
        novo = signal.authority
        if novo == anterior:
            return
        if anterior == "game" and novo == "daemon":
            _soltar_o_pad_do_lancamento(self)
        with contextlib.suppress(Exception):
            from hefesto_dualsense4unix.daemon.connection import (
                armar_gatilho_da_cor_por_evento,
            )

            armar_gatilho_da_cor_por_evento(self, f"game_signal:{anterior}->{novo}")
        if novo == "daemon":
            with contextlib.suppress(Exception):
                defend = getattr(self.controller, "defend_display", None)
                if callable(defend):
                    defend()
        elif anterior == "daemon":
            with contextlib.suppress(Exception):
                replay = getattr(self.controller, "replay_retained_game_outputs", None)
                if callable(replay):
                    replay()


    _steam_jogo_task: asyncio.Task[Any] | None = None

    def _schedule_steam_jogo_tick(self) -> None:
        """Tique lento (~2 s) da pergunta *"há jogo da Steam aberto?"*.

        ABA-DO-JOGO-01 (10/08/2026). Nenhuma capacidade nova: quem responde é a
        `steam_game_running_appid`, que existe desde 08/08 (RELANCAR-AGORA-01) e
        até hoje só era chamada por gesto do usuário, dentro da janela. O que muda é
        que o fato passa a VIAJAR — o daemon o publica no store, o `state_full` o
        leva, e a janela deixa de ter que adivinhar.

        **Por que no daemon e não na janela**, que já tem executor próprio: a
        pergunta é uma varredura de `/proc` e as respostas seriam idênticas em
        três consumidores (janela, applet, CLI). Uma sonda a 0,5 Hz no daemon
        serve os três; três sondas a 0,5 Hz cada seriam a mesma resposta paga
        três vezes.

        **Por que agendado e não `await` inline** (HANG-01, a lição do tique dos
        externos, escrito duas telas acima): `pgrep` é `fork`+`exec`, e um `fork`
        que engasga — memória apertada, `/proc` gigante — pendura QUEM ESPERAR.
        O poll loop é a rota do controle para o jogo e não pode ficar pendurado
        por uma pergunta de cosmética de aba. Aqui ele só AGENDA; se a sonda
        anterior não voltou, este tique simplesmente não acontece.

        Falha é silêncio de propósito: sem resposta, `set_steam_jogo_appid` não é
        chamado, o `steam_jogo_lido` do store fica como está, e a janela mantém a
        aba exatamente como ela estava. O contrário — tratar "não consegui
        perguntar" como "não há jogo" — sumiria com a aba debaixo dela no meio da
        partida, que é o oposto do pedido.
        """
        task = self._steam_jogo_task
        if task is not None and not task.done():
            return
        self._steam_jogo_task = asyncio.create_task(
            self._sondar_steam_jogo(), name="steam_jogo_tick"
        )

    async def _sondar_steam_jogo(self) -> None:
        """Corpo da TASK da sonda (ABA-DO-JOGO-01). Ver `_schedule_steam_jogo_tick`."""
        from hefesto_dualsense4unix.integrations.steam_launch_options import (
            steam_game_running_appid,
        )

        try:
            appid = await self._run_blocking(steam_game_running_appid)
        except Exception as exc:
            logger.debug("steam_jogo_sonda_falhou", err=str(exc))
            return
        with contextlib.suppress(Exception):
            self.store.set_steam_jogo_appid(appid)


    async def _poll_loop(self) -> None:
        period = 1.0 / max(1, self.config.poll_hz)
        battery = BatteryDebouncer()
        loop = asyncio.get_running_loop()
        next_rumble_assert_at: float = 0.0
        evdev_watchdog_next_at: float = 0.0
        grab_reconcile_next_at: float = 0.0
        coop_sync_next_at: float = 0.0
        identity_sync_next_at: float = 0.0
        # merece número mesmo sem nenhum DualSense plugado. No-op sem fiação
        external_led_next_at: float = 0.0
        game_signal_next_at: float = 0.0
        # estar aberto com o DualSense carregando na mesa, e a aba "No jogo" tem
        steam_jogo_next_at: float = 0.0
        battery_journal_next_at: float = 0.0
        mode_pending_next_at: float = 0.0
        exposicao_nativa_next_at: float = 0.0
        from hefesto_dualsense4unix.daemon.subsystems.coop import get_coop_manager
        from hefesto_dualsense4unix.daemon.subsystems.quem_mexe import anotar_o_primario
        previous_buttons: frozenset[str] = frozenset()
        was_connected = False

        def esquecer_a_leitura_publicada() -> None:
            """A mesa vazia no store e no `_last_state` (ONDA0-Z5/T1)."""
            self.store.clear_controller_state()
            self._last_state = None

        while not self._is_stopping():
            tick_started = loop.time()
            if tick_started >= identity_sync_next_at:
                identity_sync_next_at = tick_started + 2.0
                self._sync_identity_registry()
                self._seguir_a_carta()
                # sem ela o co-op não existe e os quatro DualSense viram um
                with contextlib.suppress(Exception):
                    self.aplicar_gamepad_para_multiplos_controles()
            if tick_started >= battery_journal_next_at:
                battery_journal_next_at = tick_started + INTERVALO_SONDA_S
                self._amostrar_bateria(tick_started)
            if tick_started >= external_led_next_at:
                external_led_next_at = tick_started + 2.0
                self._schedule_external_tick()
            if tick_started >= game_signal_next_at:
                game_signal_next_at = tick_started + 2.0
                await self._sync_game_signal()
            if tick_started >= steam_jogo_next_at:
                steam_jogo_next_at = tick_started + 2.0
                self._schedule_steam_jogo_tick()
            if tick_started >= exposicao_nativa_next_at:
                exposicao_nativa_next_at = tick_started + 2.0
                self._reconciliar_exposicao_do_modo_nativo()
            if tick_started >= mode_pending_next_at:
                mode_pending_next_at = tick_started + 1.0
                with contextlib.suppress(Exception):
                    self._drenar_modo_pendente()
            # o `continue` levava tudo junto. Com o DualSense do P1 fora da mesa
            # DualSense plugado"* —, e vale ainda mais aqui: número é cosmética,
            grace_passed = tick_started >= self._input_ready_at
            if grace_passed:
                coop = get_coop_manager(self)
                if tick_started >= coop_sync_next_at:
                    coop.sync()
                    try:
                        reconciliar_as_mascaras(self)
                    except Exception as exc:
                        logger.warning("mascara_reconciliacao_falhou", err=str(exc))
                    coop_sync_next_at = tick_started + 2.0
                coop.forward_all()
            if not self.controller.is_connected():
                # que `daemon.state_full` prioriza, CLUSTER-IPC-STATE-PROFILE-01)
                # três handlers de estado (`daemon.status`, `state_full`,
                if was_connected:
                    esquecer_a_leitura_publicada()
                was_connected = False
                previous_buttons = frozenset()
                stop_event = self._stop_event
                assert stop_event is not None
                with contextlib.suppress(asyncio.TimeoutError):
                    await _esperar_o_tique(self, stop_event, period)
                    break
                continue
            try:
                state = await self._run_blocking(self.controller.read_state)
            except Exception as exc:
                logger.warning("poll_read_failed", err=str(exc), exc_info=True)
                registrar_queda_da_bateria(self, "poll_read_failed", tick_started)
                if was_connected:
                    esquecer_a_leitura_publicada()
                self.bus.publish(EventTopic.CONTROLLER_DISCONNECTED, {"reason": str(exc)})
                if self.config.auto_reconnect:
                    from hefesto_dualsense4unix.daemon.connection import reconnect

                    previous_buttons = frozenset()
                    was_connected = False
                    await reconnect(self)
                    continue
                break

            if not was_connected:
                self._input_ready_at = tick_started + INPUT_GRACE_SEC
                was_connected = True
                logger.info(
                    "input_settling_started",
                    grace_sec=INPUT_GRACE_SEC,
                    transport=state.transport,
                )

            self.store.update_controller_state(state)
            # no slot `_last_state` para `daemon.state_full` consumir
            self._last_state = state
            self.bus.publish(EventTopic.STATE_UPDATE, state)
            self.store.bump("poll.tick")

            if tick_started >= next_rumble_assert_at:
                self._reassert_rumble(tick_started)
                next_rumble_assert_at = tick_started + 0.200

            if tick_started >= evdev_watchdog_next_at:
                evdev_watchdog_next_at = tick_started + EVDEV_WATCHDOG_SEC
                heal = getattr(self.controller, "heal_evdev_if_stale", None)
                if heal is not None:
                    with contextlib.suppress(Exception):
                        if await self._run_blocking(heal):
                            self.store.bump("evdev.watchdog.reopen")

            if tick_started >= grab_reconcile_next_at:
                grab_reconcile_next_at = tick_started + GRAB_RECONCILE_SEC
                with contextlib.suppress(Exception):
                    from hefesto_dualsense4unix.daemon.subsystems.gamepad import (
                        reconciliar_grab_do_primario,
                    )

                    reconciliar_grab_do_primario(self)

            buttons_pressed = self._evdev_buttons_once()
            current_buttons = state.buttons_pressed

            grace_passed = tick_started >= self._input_ready_at
            if grace_passed:
                anotar_o_primario(self, state, buttons_pressed)
            gamepad_dispatched = False
            if grace_passed and self._gamepad_device is not None:
                self._dispatch_gamepad_emulation(state, buttons_pressed)
                if self._touchpad_reader is not None:
                    from hefesto_dualsense4unix.daemon.subsystems.mouse import (
                        discard_touchpad_motion,
                    )

                    discard_touchpad_motion(self)
                gamepad_dispatched = True


            input_ready = grace_passed and not self._paused and not self._native_mode
            if not input_ready:
                if self._touchpad_reader is not None:
                    from hefesto_dualsense4unix.daemon.subsystems.mouse import (
                        discard_touchpad_motion,
                    )

                    discard_touchpad_motion(self)
                if self._keyboard_device is not None:
                    self._prime_keyboard_emulation(buttons_pressed)
                previous_buttons = current_buttons
                self.store.bump("input.settling.tick")
                if battery.should_emit(state.battery_pct, tick_started):
                    self.bus.publish(EventTopic.BATTERY_CHANGE, state.battery_pct)
                    battery.mark_emitted(state.battery_pct, tick_started)
                    self.store.bump("battery.change.emitted")
                    if self._plugins_subsystem is not None:
                        self._plugins_subsystem.dispatch_battery_change(state.battery_pct)
                elapsed = loop.time() - tick_started
                sleep_for = period - elapsed
                if sleep_for > 0:
                    stop_event = self._stop_event
                    assert stop_event is not None
                    with contextlib.suppress(asyncio.TimeoutError):
                        await _esperar_o_tique(self, stop_event, sleep_for)
                        break
                continue

            emu_buttons = buttons_pressed
            if self._hotkey_manager is not None:
                blocked = self._hotkey_manager.combo_buttons_active(buttons_pressed)
                if blocked:
                    emu_buttons = buttons_pressed - blocked

            emu_active = not self._emulation_suppressed
            if not gamepad_dispatched:
                if self._mouse_device is not None and emu_active:
                    self._dispatch_mouse_emulation(state, emu_buttons)
                elif self._touchpad_reader is not None:
                    from hefesto_dualsense4unix.daemon.subsystems.mouse import (
                        discard_touchpad_motion,
                    )

                    discard_touchpad_motion(self)

                if self._keyboard_device is not None and emu_active:
                    self._dispatch_keyboard_emulation(emu_buttons)

            # `buttons_pressed` lá em cima, e só ele.
            from hefesto_dualsense4unix.daemon.subsystems.poll import observar_os_atalhos

            observar_os_atalhos(self, buttons_pressed, now=tick_started)

            if self._plugins_subsystem is not None:
                active_profile = self.store.active_profile
                self._plugins_subsystem.tick(state, active_profile)

            pressed_now = current_buttons - previous_buttons
            released_now = previous_buttons - current_buttons
            for name in sorted(pressed_now):
                self.bus.publish(EventTopic.BUTTON_DOWN, {"button": name, "pressed": True})
                self.store.bump("button.down.emitted")
                if self._plugins_subsystem is not None:
                    self._plugins_subsystem.dispatch_button_down(name)
            for name in sorted(released_now):
                self.bus.publish(EventTopic.BUTTON_UP, {"button": name, "pressed": False})
                self.store.bump("button.up.emitted")
            previous_buttons = current_buttons

            if battery.should_emit(state.battery_pct, tick_started):
                self.bus.publish(EventTopic.BATTERY_CHANGE, state.battery_pct)
                battery.mark_emitted(state.battery_pct, tick_started)
                self.store.bump("battery.change.emitted")
                if self._plugins_subsystem is not None:
                    self._plugins_subsystem.dispatch_battery_change(state.battery_pct)

            elapsed = loop.time() - tick_started
            sleep_for = period - elapsed
            if sleep_for > 0:
                stop_event = self._stop_event
                assert stop_event is not None
                with contextlib.suppress(asyncio.TimeoutError):
                    await _esperar_o_tique(self, stop_event, sleep_for)
                    break

        tick_task = self._external_tick_task
        if tick_task is not None and not tick_task.done():
            tick_task.cancel()
        steam_task = self._steam_jogo_task
        if steam_task is not None and not steam_task.done():
            steam_task.cancel()


    def _install_signal_handlers(self, loop: asyncio.AbstractEventLoop) -> None:
        for sig in (signal.SIGINT, signal.SIGTERM):
            with contextlib.suppress(NotImplementedError):
                loop.add_signal_handler(sig, self.stop)

    async def _run_blocking(self, fn: Callable[..., Any], *args: Any) -> Any:
        assert self._executor is not None, "executor não inicializado"
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(self._executor, fn, *args)

    async def _run_external_blocking(self, fn: Callable[..., Any], *args: Any) -> Any:
        """Como `_run_blocking`, mas no pool DEDICADO `hefesto-ext` (HANG-01)."""
        assert self._external_executor is not None, (
            "external executor não inicializado"
        )
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(self._external_executor, fn, *args)

    def _is_stopping(self) -> bool:
        return self._stop_event is not None and self._stop_event.is_set()

    def _arm_input_grace(self) -> None:
        """Rearma o período de assentamento pós-conexão (BUG-DAEMON-CONNECT-"""
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return
        self._input_ready_at = loop.time() + INPUT_GRACE_SEC


    _central_do_radio: Any = None

    async def _start_central_do_radio(self) -> None:
        """Sobe a central e abre o dono do BlueZ — decisão registrada, 23/09."""
        if os.environ.get("HEFESTO_DUALSENSE4UNIX_FAKE") == "1":
            return
        from hefesto_dualsense4unix.integrations.central_do_radio import CentralDoRadio

        central = CentralDoRadio(movimento=self._movimento_para_a_central)
        self._central_do_radio = central
        await asyncio.to_thread(central.ligar)
        central.comecar_a_faxina()

    def _movimento_para_a_central(self, uniq: str) -> float | None:
        """Os Hz do nó de movimento deste controle AGORA, pelo ``SensorHub`` do IPC"""
        servidor = self._ipc_server
        garantir = getattr(servidor, "_garantir_sensor_hub", None)
        if not callable(garantir):
            return None
        hz = garantir().hz_do_movimento(uniq)
        return float(hz) if isinstance(hz, (int, float)) and not isinstance(hz, bool) else None

    def _garantir_sensor_hub(self) -> Any:
        """O ``SensorHub`` da sessão — o MESMO do IPC —, para a mira do tique."""
        garantir = getattr(self._ipc_server, "_garantir_sensor_hub", None)
        if not callable(garantir):
            return HUB_AUSENTE
        return garantir()

    def _garantir_cursor_do_toque(self) -> Any:
        """O cursor que o touchpad move pelo Hefesto — um por sessão, ou ``None``."""
        cursor = getattr(self, "_cursor_do_toque", None)
        if cursor is not None:
            return cursor or None
        from hefesto_dualsense4unix.integrations.uinput_mouse import CursorDoToque

        novo = CursorDoToque()
        if not novo.start():
            self._cursor_do_toque: Any = False
            return None
        self._cursor_do_toque = novo
        return novo


CAMPOS_DO_TETO_DA_ECONOMIA: Final[tuple[str, ...]] = (
    "led", "player_led_brightness", "trigger_left", "trigger_right",
)


def _soltar_o_teto_de_quem_entra(daemon: Any, antes: Any) -> None:
    """Solta da camada da usuária o teto de quem ENTRA na economia."""
    from hefesto_dualsense4unix.profiles.schema import economia_da_declaracao

    mesa_antes, ligados_antes = economia_da_declaracao(antes)
    mesa, ligados = economia_da_declaracao(daemon._maquina)
    if mesa and mesa_antes:
        return
    entraram: frozenset[str] | None = None if mesa else ligados - ligados_antes
    if entraram is not None and not entraram:
        return
    soltar = getattr(getattr(daemon, "controller", None), "clear_user_output_fields", None)
    if callable(soltar):
        with contextlib.suppress(Exception):
            soltar(entraram, CAMPOS_DO_TETO_DA_ECONOMIA)


class _HubAusente:
    """O hub que ainda não há: as duas torneiras do roteador respondem ``None``."""

    def velocidade_do_movimento(self, uniq: str) -> None:
        return None

    def angulo_do_movimento(self, uniq: str) -> None:
        return None

    def aceleracao_do_movimento(self, uniq: str) -> None:
        return None

    def toque_da_peca(self, uniq: str) -> None:
        return None


HUB_AUSENTE = _HubAusente()


INTERVALO_MINIMO_DA_VOLTA_S = 0.004


class _OAperto:
    """O evento do aperto de UM laço, e a hora da última volta do jogo."""

    __slots__ = ("evento", "laco", "ultima_volta")

    def __init__(self, laco: asyncio.AbstractEventLoop) -> None:
        from hefesto_dualsense4unix.core.evdev_reader import definir_o_despertador

        self.laco = laco
        self.evento = asyncio.Event()
        self.ultima_volta = laco.time()
        evento = self.evento

        def acordar() -> None:
            if not laco.is_closed():
                laco.call_soon_threadsafe(evento.set)

        definir_o_despertador(acordar)


def _o_aperto_do_laco(daemon: Any) -> _OAperto:
    """O `_OAperto` do laço que roda agora, ligado ao despertador do leitor."""
    laco = asyncio.get_running_loop()
    aperto = getattr(daemon, "_o_aperto_do_laco", None)
    if not isinstance(aperto, _OAperto) or aperto.laco is not laco:
        aperto = _OAperto(laco)
        daemon._o_aperto_do_laco = aperto
    return aperto


async def _esperar_o_tique(daemon: Any, stop_event: asyncio.Event, timeout: float) -> None:
    """A espera do laço, que acorda com a parada OU com o aperto."""
    aperto = _o_aperto_do_laco(daemon)
    laco = aperto.laco
    prazo = laco.time() + timeout
    aperto.ultima_volta = laco.time()
    parada = laco.create_task(stop_event.wait())
    try:
        while True:
            resto = prazo - laco.time()
            if resto <= 0:
                raise asyncio.TimeoutError
            acordou = laco.create_task(aperto.evento.wait())
            try:
                await asyncio.wait(
                    (parada, acordou), timeout=resto, return_when=asyncio.FIRST_COMPLETED
                )
            finally:
                acordou.cancel()
            if stop_event.is_set():
                return
            if not aperto.evento.is_set():
                continue
            aperto.evento.clear()
            cedo = aperto.ultima_volta + INTERVALO_MINIMO_DA_VOLTA_S - laco.time()
            if cedo > 0:
                await asyncio.wait((parada,), timeout=min(cedo, max(prazo - laco.time(), 0.0)))
                if stop_event.is_set():
                    return
            if prazo - laco.time() < INTERVALO_MINIMO_DA_VOLTA_S:
                continue
            _volta_do_aperto(daemon)
            aperto.ultima_volta = laco.time()
    finally:
        parada.cancel()


def _volta_do_aperto(daemon: Any) -> None:
    """A volta que o aperto acorda: SÓ o caminho do jogo. Nunca levanta."""
    try:
        if asyncio.get_running_loop().time() < daemon._input_ready_at:
            return
        from hefesto_dualsense4unix.daemon.subsystems.coop import get_coop_manager

        daemon.store.bump("poll.volta_do_aperto")
        get_coop_manager(daemon).forward_all()
        estado = getattr(daemon, "_last_state", None)
        if (
            daemon._gamepad_device is not None
            and estado is not None
            and daemon.controller.is_connected()
        ):
            daemon._dispatch_gamepad_emulation(estado, daemon._evdev_buttons_once())
    except Exception as exc:
        logger.debug("volta_do_aperto_falhou", err=str(exc))


__all__ = [
    "AUTO_DEBOUNCE_SEC",
    "BATTERY_DEBOUNCE_SEC",
    "BATTERY_DELTA_THRESHOLD_PCT",
    "BATTERY_MIN_INTERVAL_SEC",
    "DEFAULT_POLL_HZ",
    "RUMBLE_POLICY_MULT",
    "BatteryDebouncer",
    "Daemon",
    "DaemonConfig",
]
