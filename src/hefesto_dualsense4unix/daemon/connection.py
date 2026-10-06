"""Funções de conexão, reconexão e shutdown do daemon."""
from __future__ import annotations

import asyncio
import contextlib
import os
import time
from collections.abc import Callable, Mapping, Sequence
from typing import Any

from hefesto_dualsense4unix.core import o_dono_do_evento as _ode
from hefesto_dualsense4unix.core.escritor_cru import (
    PASSO_DA_VIGIA_S,
    PassoDaVigia,
    SentinelaDeEscritorCru,
    Veredito,
    VigiaDoSequestro,
    firma_do_no,
)
from hefesto_dualsense4unix.core.evdev_reader import InputDirWatch
from hefesto_dualsense4unix.core.events import EventTopic
from hefesto_dualsense4unix.core.gatilho_fim_de_sequencia import (
    RegistroDeGatilhos,
    Tarefa,
)
from hefesto_dualsense4unix.core.lightbar_gatilho import (
    ATRASO_APOS_A_ULTIMA_CONEXAO_S,
)
from hefesto_dualsense4unix.core.lightbar_gatilho import (
    NOME_DO_GATILHO as NOME_DO_GATILHO_DA_LIGHTBAR,
)
from hefesto_dualsense4unix.daemon.battery_journal import registrar_queda_da_bateria
from hefesto_dualsense4unix.daemon.protocols import DaemonProtocol
from hefesto_dualsense4unix.integrations.sinal_da_barra import (
    CONFIANCA_NAO_SEI,
    CartorioDoNascimento,
    Instancia,
    Leitura,
    endereco_normalizado,
    instancias_dualsense,
    mascarar,
    veredito_do_nascimento,
)
from hefesto_dualsense4unix.utils.logging_config import get_logger

logger = get_logger(__name__)


BACKOFF_MAX_SEC: float = 30.0

#: Intervalo entre probes de hot-reconnect quando o controle está desconectado
RECONNECT_PROBE_INTERVAL_SEC: float = 5.0

RECONNECT_ONLINE_CHECK_INTERVAL_SEC: float = 30.0

TETO_DA_VOLTA_PELO_EVENTO_SEC: float = 300.0

#: DualSense novo passa de "até 30s" para ~2s até o backend abrir o handle
RECONNECT_HOTPLUG_POLL_INTERVAL_SEC: float = 2.0

PASSO_ENQUANTO_O_GATILHO_ESTA_ARMADO_SEC: float = 0.25

PASSO_ENQUANTO_UM_CONTROLE_TROCA_DE_TRANSPORTE_SEC: float = 0.5


async def connect_with_retry(daemon: DaemonProtocol) -> None:
    """Tenta conectar o controller com backoff exponencial. Publica CONTROLLER_CONNECTED."""
    backoff = daemon.config.reconnect_backoff_sec
    while True:
        try:
            await daemon._run_blocking(daemon.controller.connect)
            transport = daemon.controller.get_transport()
            daemon.bus.publish(EventTopic.CONTROLLER_CONNECTED, {"transport": transport})
            logger.info("controller_connected", transport=transport)
            await reaplicar_som_em_todos_os_alvos(daemon)
            return
        except Exception as exc:
            logger.warning("controller_connect_failed", err=str(exc), exc_info=True)
            if not daemon.config.auto_reconnect:
                raise
            stop_event = getattr(daemon, "_stop_event", None)
            if stop_event is not None:
                try:
                    await asyncio.wait_for(stop_event.wait(), timeout=backoff)
                    return
                except asyncio.TimeoutError:
                    pass
            else:
                await asyncio.sleep(backoff)
            backoff = min(backoff * 2, BACKOFF_MAX_SEC)


async def reapply_speaker_after_connect(
    daemon: DaemonProtocol, *, uniq: str | None = None
) -> None:
    """Reaplica o volume do perfil ATIVO no (re)connect (SOM-02/E4, armadilha 4)."""
    from functools import partial

    from hefesto_dualsense4unix.profiles.manager import ProfileManager

    applier = getattr(daemon, "apply_profile_speaker", None)
    store = getattr(daemon, "store", None)
    if applier is None or store is None:
        return
    manager = ProfileManager(
        controller=daemon.controller,
        store=store,
        speaker_applier=applier,
    )
    estado = await daemon._run_blocking(
        partial(manager.reapply_speaker_on_connect, uniq)
    )
    if estado is not None:
        logger.info("speaker_reaplicado_no_connect", estado=estado, uniq=uniq)


async def reapply_mic_after_connect(
    daemon: DaemonProtocol, *, uniq: str | None = None
) -> None:
    """Devolve o MUDO do microfone daquela peça no (re)connect."""
    from functools import partial

    from hefesto_dualsense4unix.profiles.manager import ProfileManager

    applier = getattr(daemon, "apply_profile_mic", None)
    store = getattr(daemon, "store", None)
    if applier is None or store is None:
        return
    manager = ProfileManager(
        controller=daemon.controller,
        store=store,
        mic_applier=applier,
    )
    estado = await daemon._run_blocking(
        partial(manager.reapply_mic_on_connect, uniq)
    )
    if estado is not None:
        logger.info("mic_reaplicado_no_connect", estado=estado, uniq=uniq)


def nascer_o_microfone_ao_conectar(
    daemon: DaemonProtocol, *, uniq: str | None = None
) -> asyncio.Task[bool] | None:
    """O microfone daquela peça NASCE NO AR no (re)connect (NASCE-LIGADO-MIC-01)."""
    from hefesto_dualsense4unix.daemon.subsystems.hotkey import (
        agendar_o_nascimento_do_microfone,
    )

    return agendar_o_nascimento_do_microfone(daemon, uniq=uniq)


def alvos_conectados_de(daemon: DaemonProtocol) -> dict[str, str | None] | None:
    """`{key: uniq}` dos controles conectados AGORA, ou None se ninguém sabe."""
    metodo = getattr(getattr(daemon, "controller", None), "alvos_conectados", None)
    if not callable(metodo):
        return None
    try:
        alvos = metodo()
    except Exception as exc:
        logger.debug("alvos_conectados_falhou", err=str(exc), exc_info=True)
        return None
    if not isinstance(alvos, dict):
        return None
    return dict(alvos)


async def reaplicar_som_em_todos_os_alvos(daemon: DaemonProtocol) -> None:
    """Reaplica o volume/rota do perfil ativo em CADA controle da mesa."""
    alvos = alvos_conectados_de(daemon)
    uniqs: list[str | None] = (
        [None] if not alvos else list(dict.fromkeys(alvos.values()))
    )
    for uniq in uniqs:
        with contextlib.suppress(Exception):
            await reapply_speaker_after_connect(daemon, uniq=uniq)
        with contextlib.suppress(Exception):
            await reapply_mic_after_connect(daemon, uniq=uniq)
        with contextlib.suppress(Exception):
            nascer_o_microfone_ao_conectar(daemon, uniq=uniq)


async def anunciar_bordas_por_alvo(
    daemon: DaemonProtocol,
    antes: dict[str, str | None],
    agora: dict[str, str | None],
) -> None:
    """As bordas que o agregado esconde: quem saiu da mesa e quem voltou a ela."""
    trocando = trocas_de_transporte_pendentes(daemon)
    for key in [k for k in antes if k not in agora]:
        uniq = antes[key]
        if uniq in trocando:
            logger.info(
                "controle_trocando_de_transporte", uniq=_endereco_mascarado(uniq)
            )
            continue
        daemon.bus.publish(
            EventTopic.CONTROLLER_DISCONNECTED,
            {"reason": "alvo_sumiu", "uniq": uniq},
        )
        logger.info("controller_disconnected", reason="alvo_sumiu", uniq=uniq)
    for key in [k for k in agora if k not in antes]:
        with contextlib.suppress(Exception):
            await reapply_speaker_after_connect(daemon, uniq=agora[key])
        with contextlib.suppress(Exception):
            await reapply_mic_after_connect(daemon, uniq=agora[key])
        with contextlib.suppress(Exception):
            nascer_o_microfone_ao_conectar(daemon, uniq=agora[key])


def trocas_de_transporte_pendentes(daemon: DaemonProtocol) -> frozenset[str]:
    """Os MACs fora da mesa por estarem trocando de transporte (O-CABO-ASSUME-DO-RADIO-01)."""
    pergunta = getattr(getattr(daemon, "controller", None), "trocas_de_transporte_pendentes", None)
    if not callable(pergunta):
        return frozenset()
    try:
        return frozenset(pergunta() or ())
    except Exception as exc:
        logger.debug("trocas_de_transporte_falhou", err=str(exc))
        return frozenset()


def transportes_dos_alvos_de(daemon: DaemonProtocol) -> dict[str, str] | None:
    """`{key: transporte}` dos controles na mesa, ou None se o backend não sabe."""
    metodo = getattr(getattr(daemon, "controller", None), "transportes_dos_alvos", None)
    if not callable(metodo):
        return None
    try:
        transportes = metodo()
    except Exception as exc:
        logger.debug("transportes_dos_alvos_falhou", err=str(exc))
        return None
    return dict(transportes) if isinstance(transportes, dict) else None


async def reaplicar_som_de_quem_trocou_de_transporte(
    daemon: DaemonProtocol,
    alvos_antes: dict[str, str | None],
    alvos_agora: dict[str, str | None],
    transportes_antes: dict[str, str],
    transportes_agora: dict[str, str],
) -> int:
    """O controle que trocou de transporte ENTRE dois tiques ganha o som de volta."""
    trocaram = {
        key: uniq
        for key, uniq in alvos_agora.items()
        if key in alvos_antes
        and key in transportes_antes
        and key in transportes_agora
        and transportes_antes[key] != transportes_agora[key]
    }
    for key, uniq in trocaram.items():
        logger.info(
            "controle_trocou_de_transporte",
            uniq=_endereco_mascarado(uniq),
            antes=transportes_antes[key],
            agora=transportes_agora[key],
        )
    if trocaram:
        await anunciar_bordas_por_alvo(daemon, {}, trocaram)
    return len(trocaram)


def vigia_do_cabo_de(daemon: DaemonProtocol) -> Any:
    """A `VigiaDoCabo` DESTE daemon, criada na primeira consulta (O-CABO-ASSUME-DO-RADIO-01)."""
    from hefesto_dualsense4unix.integrations.o_cabo_em_espera import VigiaDoCabo

    vigia = getattr(daemon, "_vigia_do_cabo_em_espera", None)
    if isinstance(vigia, VigiaDoCabo):
        return vigia
    vigia = VigiaDoCabo()
    with contextlib.suppress(Exception):
        setattr(daemon, "_vigia_do_cabo_em_espera", vigia)  # noqa: B010 — fora do protocolo
    return vigia


def _o_barramento_hid_mudou(daemon: DaemonProtocol) -> bool:
    """O barramento HID mudou, ou um cabo que espera ficou maduro? (O-CABO-ASSUME-DO-RADIO-01)"""
    ctrl = getattr(daemon, "controller", None)
    if not callable(getattr(ctrl, "iniciar_troca_de_transporte", None)):
        return False
    from hefesto_dualsense4unix.integrations import o_cabo_em_espera

    watch = getattr(daemon, "_watch_do_barramento_hid", None)
    if not isinstance(watch, InputDirWatch):
        watch = InputDirWatch(root=o_cabo_em_espera.RAIZ_DO_BARRAMENTO_HID)
        watch.poll()
        with contextlib.suppress(Exception):
            setattr(daemon, "_watch_do_barramento_hid", watch)  # noqa: B010
        return False
    if watch.poll():
        logger.debug("barramento_hid_mudou")
        return True
    return bool(vigia_do_cabo_de(daemon).quer_olhar_de_novo(time.monotonic()))


async def vigiar_o_cabo_em_espera(
    daemon: DaemonProtocol,
    *,
    agora: float | None = None,
    leitor_do_bluez: Any = None,
    ler_o_diario: Any = None,
) -> int:
    """O controle do rádio que ganhou cabo passa para o cabo. Devolve quantos passaram."""
    ctrl = getattr(daemon, "controller", None)
    iniciar = getattr(ctrl, "iniciar_troca_de_transporte", None)
    descrever = getattr(ctrl, "describe_controllers", None)
    if not callable(iniciar) or not callable(descrever):
        return 0
    from hefesto_dualsense4unix.integrations import o_cabo_em_espera as oce

    vigia = vigia_do_cabo_de(daemon)
    agora = time.monotonic() if agora is None else float(agora)
    try:
        mesa = [item for item in descrever() or () if item.get("connected") and item.get("uniq")]
        no_radio = {
            str(item["uniq"]): item.get("battery_state")
            for item in mesa
            if item.get("transport") == "bt"
        }
        no_cabo = [str(item["uniq"]) for item in mesa if item.get("transport") == "usb"]
        cabos = oce.cabos_em_espera()
    except Exception as exc:
        logger.debug("o_cabo_em_espera_leitura_falhou", err=str(exc))
        return 0
    vigia.observar_a_carga(no_radio, agora)
    vigia.observar_quem_esta_no_cabo(no_cabo)
    pendentes = vigia.observar_os_cabos(cabos, agora)
    if not pendentes:
        return 0
    if _modo_nativo(daemon):
        for cabo in pendentes:
            if vigia.primeira_vez(f"nativo:{cabo.instancia}"):
                logger.info("o_cabo_espera_o_modo_nativo", instancia=cabo.instancia)
        return 0
    impedimentos = oce.impedimentos_da_troca()
    if impedimentos:
        if vigia.primeira_vez("impedida"):
            logger.warning("o_cabo_em_espera_impedido", motivos=impedimentos)
        return 0
    ler = ler_o_diario if callable(ler_o_diario) else oce.ler_o_diario_do_kernel
    try:
        texto = await asyncio.to_thread(ler)
    except Exception as exc:
        logger.debug("o_cabo_em_espera_diario_falhou", err=str(exc))
        texto = None
    diario = oce.enderecos_recusados(texto) if texto else None
    passaram = 0
    for cabo in pendentes:
        decisao = vigia.decidir(cabo, diario=diario, no_radio=no_radio, agora=agora)
        if decisao.par is None:
            if decisao.desistir:
                vigia.resolver(cabo.instancia)
                logger.info(
                    "o_cabo_em_espera_fica_no_radio",
                    instancia=cabo.instancia,
                    motivo=decisao.motivo,
                )
            continue
        vigia.resolver(cabo.instancia)
        par = decisao.par
        if not iniciar(par, motivo="o_cabo_chegou"):
            continue

        def _derrubar(uniq: str = par) -> tuple[bool, str]:
            return oce.derrubar_o_radio(uniq, leitor=leitor_do_bluez)

        try:
            feito, motivo = await asyncio.to_thread(_derrubar)
        except Exception as exc:
            feito, motivo = False, str(exc)
        if not feito:
            cancelar = getattr(ctrl, "cancelar_troca_de_transporte", None)
            if callable(cancelar):
                with contextlib.suppress(Exception):
                    cancelar(par, motivo="o_radio_nao_caiu")
            tenta_de_novo = vigia.recusado(cabo.instancia, agora)
            logger.warning(
                "o_cabo_nao_assumiu",
                uniq=oce.mascarar(par),
                instancia=cabo.instancia,
                motivo=motivo,
                tenta_de_novo=tenta_de_novo,
            )
            continue
        vigia.derrubou(par, agora)
        passaram += 1
        logger.info(
            "o_cabo_assume",
            uniq=oce.mascarar(par),
            instancia=cabo.instancia,
            fonte=decisao.fonte,
        )
    return passaram


def _o_nome_que_o_boot_restaura(store: Any, *, appid_em_cena: int | None = None) -> str | None:
    """O nome da escolha do usuário para o boot, com a memória do botão quando há.

    `D-2909-O-HEFESTO-ABRE-NA-ESCOLHA-DELA`, item 4: o boot e a reconexão
    restauram a escolha do usuário, com regra de janela ou sem. A pergunta é a do
    dono (`utils.session.resolve_boot_profile`, que pergunta a
    `a_escolha_dela`); a memória do Modo Freestyle (`o_freestyle_manda`) vale
    quando há `store`, e o disco quando o boot pergunta antes de haver memória.
    O Freestyle desligado nunca volta (item 6). Levanta só o que o dono levanta.

    O JOGO EM CENA VEM ANTES DA ESCOLHA — A-TRAVA-DO-JOGO-ABERTO-TEM-UM-DONO-01
    (01/10/2026, `D-3009-O-REINICIO-COM-O-JOGO-ABERTO-NASCE-NO-PERFIL-DO-JOGO`,
    a validar pelo usuário). Com um jogo aberto na hora do boot (o «Reiniciar», o
    install, uma queda do serviço), o perfil cuja regra `steam_app_<appid>`
    casa com ele é o que vale, e o primeiro pad nasce no modo dele: o
    autoswitch o poria nove segundos depois, com a trava já protegendo o modo
    de fora do jogo. Com o Freestyle ligado, vale o Freestyle, como sempre.
    `appid_em_cena` é o do sinal de jogo (`Daemon.appid_em_cena`); sem ele, a
    escolha do usuário.

    NOTA DATADA — 01/10/2026: aqui morava a RESTORE-ESCOPO-01 (22/07), que
    pulava todo perfil com regra de janela, e o Freestyle entrava no lugar
    (O-MODO-FREESTYLE-03). No disco do usuário isso é todo perfil que não é o
    Freestyle: medido no diário de 28 e 29/09, seis boots com a sessão em Pro
    Jank Footy, e nenhum abriu no perfil que ela tinha ativado. A fala do usuário de
    29/09 revogou a regra para a escolha do usuário.
    """
    from hefesto_dualsense4unix.profiles.loader import NOME_DO_PADRAO
    from hefesto_dualsense4unix.profiles.manager import e_o_freestyle, o_freestyle_manda
    from hefesto_dualsense4unix.utils.session import (
        a_escolha_dela,
        load_freestyle_ligado,
        resolve_boot_profile,
    )

    manda = o_freestyle_manda(store) if store is not None else load_freestyle_ligado()
    if manda:
        return NOME_DO_PADRAO
    if appid_em_cena is not None:
        from hefesto_dualsense4unix.profiles.manager import perfil_do_appid

        do_jogo = perfil_do_appid(appid_em_cena)
        if do_jogo is not None and not e_o_freestyle(do_jogo.name):
            return str(do_jogo.name)
    nome = resolve_boot_profile()
    if e_o_freestyle(nome):
        nome = a_escolha_dela(freestyle_ligado=False)
    if not nome or e_o_freestyle(nome):
        return None
    return nome


def perfil_que_o_boot_restaura(
    store: Any = None, *, appid_em_cena: int | None = None,
) -> Any | None:
    """O perfil que o `restore_last_profile` vai ativar, lido sem ativar nada.

    O-MODO-XBOX-NAO-E-QUEDA-02 (28/09/2026), item 3 da cura consolidada. O
    boot sobe o pad do P1 ANTES do `controller.connect()` e do restore
    (VPAD-03/BT-01), e o restore não aplica o modo
    (BUG-BOOT-RESTORE-FLIPS-EMULATION-01). Medido nos três boots de 27/09 às
    21h: com foco X o autoswitch ativava o Freestyle e recriava o pad em Xbox;
    sem foco o modo ficava DualSense e a tela dizia «Freestyle». Quem pergunta
    aqui é o boot, para o primeiro pad nascer no modo do perfil que vai valer.

    A mesma pergunta do restore (:func:`_o_nome_que_o_boot_restaura`): com o
    Modo Freestyle ligado, o Freestyle, e o primeiro pad nasce no modo DELE;
    desligado, a escolha do usuário, com regra de janela ou sem — escolher o Future
    Knight à mão deixa o controle no Xbox fora do jogo, que é o que o «Ativar»
    já faz. Com um jogo aberto na hora do boot (`appid_em_cena`, desde a
    A-TRAVA-DO-JOGO-ABERTO-TEM-UM-DONO-01), o perfil do jogo vem antes da
    escolha. Nunca levanta: sem perfil legível, ``None`` e o boot de sempre.
    """
    try:
        from hefesto_dualsense4unix.profiles.loader import load_profile

        nome = _o_nome_que_o_boot_restaura(store, appid_em_cena=appid_em_cena)
        return load_profile(nome) if nome else None
    except Exception:
        return None


async def restore_last_profile(daemon: DaemonProtocol) -> None:
    """Reativa a escolha do usuário no boot e na reconexão (FEAT-PERSIST-SESSION-01)."""
    from functools import partial

    from hefesto_dualsense4unix.profiles.loader import o_perfil_de_fora_do_jogo
    from hefesto_dualsense4unix.profiles.manager import (
        ProfileManager,
        _canal_do_ps,
        ligar_o_freestyle,
        o_freestyle_manda,
    )
    from hefesto_dualsense4unix.profiles.slug import mesmo_slug

    store = getattr(daemon, "store", None)
    if o_freestyle_manda(store) and not o_perfil_de_fora_do_jogo():
        logger.warning("freestyle_ligado_sem_o_perfil", acao="desligado")
        ligar_o_freestyle(store, False)
    appid_em_cena = getattr(daemon, "appid_em_cena", None)
    if not isinstance(appid_em_cena, int) or isinstance(appid_em_cena, bool):
        appid_em_cena = None
    name = _o_nome_que_o_boot_restaura(store, appid_em_cena=appid_em_cena)
    if not name:
        logger.info("boot_sem_escolha")
        return
    if appid_em_cena is not None:
        logger.info("boot_com_o_jogo_em_cena", appid=appid_em_cena, perfil=name)
    if getattr(daemon, "_native_mode", False):
        logger.info("last_profile_restore_skipped_native_mode", name=name)
        return
    ja_vale = getattr(store, "active_profile", None)
    if isinstance(ja_vale, str) and ja_vale and not mesmo_slug(ja_vale, name):
        logger.info("a_escolha_nao_entra_por_cima", name=name, ja_vale=ja_vale)
        return
    manager = ProfileManager(
        controller=daemon.controller,
        store=daemon.store,
        keyboard_device_provider=lambda: getattr(
            daemon, "_keyboard_device", None
        ),
        # `button_actions` não tem flag persistido próprio, então o perfil é a
        mouse_device_provider=lambda: getattr(daemon, "_mouse_device", None),
        mouse_applier=None,
        suppression_applier=getattr(daemon, "apply_profile_suppression", None),
        mode_applier=None,
        rumble_policy_applier=getattr(
            daemon, "apply_profile_rumble_policy", None
        ),
        rumble_passthrough_applier=getattr(
            daemon, "apply_profile_rumble_passthrough", None
        ),
        # flag persistido próprio — o DualSense não devolve o valor que o
        speaker_applier=getattr(daemon, "apply_profile_speaker", None),
        mic_applier=getattr(daemon, "apply_profile_mic", None),
        ps_action_sink=_canal_do_ps(daemon),
    )

    try:
        await daemon._run_blocking(partial(manager.activate, name, origin="system"))
    except Exception as exc:
        logger.warning("last_profile_restore_failed", name=name, err=str(exc))
        return
    logger.info("last_profile_restored", name=name)


def _broker_restore_for_recovery(daemon: DaemonProtocol) -> list[str]:
    """Restaura hidraws escondidos pelo broker cujo nó AINDA EXISTE no disco."""
    from hefesto_dualsense4unix.integrations.hidraw_broker_client import (
        broker_client_for,
    )

    client = broker_client_for(daemon)
    response = client.status()
    hidden = response.get("hidden") if isinstance(response, dict) else None
    restored: list[str] = []
    for node in hidden or []:
        if not isinstance(node, str) or not os.path.exists(node):
            continue
        if client.restore(node):
            restored.append(node)
    return restored


async def _restore_hidden_before_reopen(daemon: DaemonProtocol) -> None:
    """Agenda o `_broker_restore_for_recovery` no executor DEDICADO do broker."""
    with contextlib.suppress(Exception):
        from hefesto_dualsense4unix.integrations.hidraw_broker_client import (
            broker_executor_for,
        )

        restored = await asyncio.get_running_loop().run_in_executor(
            broker_executor_for(daemon), _broker_restore_for_recovery, daemon
        )
        if restored:
            logger.info("hidraw_broker_restore_recovery", nodes=restored)


async def reconnect(daemon: DaemonProtocol) -> None:
    """Desconecta e tenta reconectar com backoff."""
    with contextlib.suppress(Exception):
        await daemon._run_blocking(daemon.controller.disconnect)
    await asyncio.sleep(daemon.config.reconnect_backoff_sec)
    await _restore_hidden_before_reopen(daemon)
    await connect_with_retry(daemon)
    daemon._arm_input_grace()


async def reconnect_loop(
    daemon: DaemonProtocol, *, input_watch: InputDirWatch | None = None
) -> None:
    """Probe não-bloqueante de conexão com o DualSense (BUG-DAEMON-NO-DEVICE-FATAL-01).

    Diferente de `connect_with_retry` (legado, bloqueante e reusado pela CLI):
      - Nunca bloqueia o boot — `Daemon.run()` cria esta task em background.
      - Respeita `daemon._stop_event` durante todos os waits.
      - Loga transições offline→online e online→offline em INFO; tentativas
        falhadas em DEBUG (evita inundar journal a cada 5s).
      - Restaura último perfil exatamente uma vez na primeira conexão bem-sucedida.

    O loop coopera com o poll_loop: quando `read_state` levanta após perda de
    conexão, o poll loop dispara `reconnect()` (legado) e o probe deste loop
    detectará a transição back-online no próximo tick.

    FEAT-BACKEND-HOTPLUG-FAST-01: quando ONLINE, o sleep de 30s é fatiado em
    `RECONNECT_HOTPLUG_POLL_INTERVAL_SEC` consultando um `InputDirWatch`
    (mudança em /dev/input = hotplug/unplug de controle). Mudou → reconcilia já
    (`controller.connect()` no executor); sem mudança, o custo por fatia é um
    listdir (~µs) e o check de 30s permanece como fallback. Reentrância segura:
    `connect()` é idempotente e tem a guarda `_opening` sob `_io_lock` no
    backend — um `reconnect()` concorrente do poll loop não duplica abertura.
    `input_watch` é injetável para testes; None cria o watch real.

    GATILHO-DA-COR-01: este laço é também o RELÓGIO ÚNICO do mecanismo de
    reafirmação no fim de sequência (`core/gatilho_fim_de_sequencia.py`),
    porque é aqui que o produto já enxerga conexão nova. A cada volta ele ARMA
    o gatilho da lightbar com o que o `connect()` contou, e a espera online
    avalia o DISPARO de TODOS os gatilhos registrados entre as fatias — o do
    co-op inclusive, quando ele existir.
    """
    from hefesto_dualsense4unix.daemon.connection import (
        restore_last_profile as _restore_last_profile,
    )

    armou = input_watch is None and _ode.armar()
    try:
        dono = _ode.dono_armado()
        if input_watch is not None:
            watch = input_watch
        elif dono is not None:
            watch = InputDirWatch(root=dono.raiz_das_entradas)
        else:
            watch = InputDirWatch()
        nos = InputDirWatch(root=dono.raiz_dos_nos) if dono is not None else None
        with contextlib.suppress(Exception):
            setattr(daemon, "_watch_dos_hidraw", nos)  # noqa: B010 — fora do protocolo
        registrar_gatilho_da_lightbar(daemon)
        watch.poll()
        if nos is not None:
            nos.poll()

        initial_connected = bool(daemon.controller.is_connected())
        restored = initial_connected
        was_connected = initial_connected
        alvos_antes = alvos_conectados_de(daemon) or {}
        transportes_antes = transportes_dos_alvos_de(daemon) or {}
        while not daemon._is_stopping():
            try:
                await daemon._run_blocking(daemon.controller.connect)
            except Exception as exc:
                logger.debug("reconnect_probe_failed", err=str(exc), exc_info=True)
                await _restore_hidden_before_reopen(daemon)
                await _wait_or_stop(daemon, RECONNECT_PROBE_INTERVAL_SEC)
                continue

            armar_gatilho_da_cor(daemon)
            armar_gatilho_da_cor_por_numeracao(daemon)
            await vigiar_escritor_cru(daemon, forcar=True)
            await carimbar_o_nascimento(daemon)
            await vigiar_o_cabo_em_espera(daemon)

            is_connected = bool(daemon.controller.is_connected())
            alvos_agora = alvos_conectados_de(daemon)
            transportes_agora = transportes_dos_alvos_de(daemon)
            trocando = trocas_de_transporte_pendentes(daemon)
            if is_connected and not was_connected:
                daemon._arm_input_grace()
                transport = daemon.controller.get_transport()
                daemon.bus.publish(
                    EventTopic.CONTROLLER_CONNECTED, {"transport": transport}
                )
                logger.info("controller_connected", transport=transport)
                with contextlib.suppress(Exception):
                    from hefesto_dualsense4unix.daemon.subsystems.gamepad import (
                        upgrade_primary_vpad_to_uhid,
                    )

                    def _promover_vpad() -> bool:
                        with getattr(daemon, "_emu_lock", contextlib.nullcontext()):
                            return upgrade_primary_vpad_to_uhid(daemon)

                    await daemon._run_blocking(_promover_vpad)
                if not restored:
                    with contextlib.suppress(Exception):
                        await _restore_last_profile(daemon)
                    restored = True
                await reaplicar_som_em_todos_os_alvos(daemon)
                was_connected = True
            elif not is_connected and was_connected and trocando:
                await anunciar_bordas_por_alvo(daemon, alvos_antes, alvos_agora or {})
            elif not is_connected and was_connected:
                registrar_queda_da_bateria(
                    daemon, "probe_offline", asyncio.get_running_loop().time()
                )
                daemon.bus.publish(
                    EventTopic.CONTROLLER_DISCONNECTED, {"reason": "probe_offline"}
                )
                logger.info("controller_disconnected", reason="probe_offline")
                was_connected = False
            elif alvos_agora is not None:
                await anunciar_bordas_por_alvo(daemon, alvos_antes, alvos_agora)
                if transportes_agora is not None:
                    await reaplicar_som_de_quem_trocou_de_transporte(
                        daemon, alvos_antes, alvos_agora, transportes_antes, transportes_agora
                    )

            if alvos_agora is not None:
                alvos_antes = alvos_agora
            if transportes_agora is not None:
                transportes_antes = transportes_agora

            if is_connected:
                with contextlib.suppress(Exception):
                    from hefesto_dualsense4unix.daemon.subsystems.gamepad import (
                        rehide_physical_hidraw,
                    )
                    from hefesto_dualsense4unix.integrations.hidraw_broker_client import (
                        broker_executor_for,
                    )

                    await asyncio.get_running_loop().run_in_executor(
                        broker_executor_for(daemon), rehide_physical_hidraw, daemon
                    )
                if await _wait_online_or_hotplug(daemon, watch):
                    logger.info(
                        "backend_hotplug_reconcile", trigger="input_dir_change"
                    )
            else:
                gatilho_lightbar = registro_de_gatilhos_de(daemon).obter(
                    NOME_DO_GATILHO_DA_LIGHTBAR
                )
                if gatilho_lightbar is not None:
                    gatilho_lightbar.desarmar()
                await _wait_or_stop(
                    daemon,
                    PASSO_ENQUANTO_UM_CONTROLE_TROCA_DE_TRANSPORTE_SEC
                    if trocando
                    else RECONNECT_PROBE_INTERVAL_SEC,
                )
    finally:
        if armou:
            _ode.desarmar()


def registro_de_gatilhos_de(daemon: DaemonProtocol) -> RegistroDeGatilhos:
    """O `RegistroDeGatilhos` DESTE daemon, criado na primeira consulta."""
    registro = getattr(daemon, "_registro_de_gatilhos", None)
    if isinstance(registro, RegistroDeGatilhos):
        return registro
    registro = RegistroDeGatilhos()
    with contextlib.suppress(Exception):
        daemon._registro_de_gatilhos = registro
    return registro


def registrar_gatilho(
    daemon: DaemonProtocol,
    nome: str,
    tarefa: Tarefa,
    *,
    atraso_s: float | None = None,
) -> None:
    """Registra (ou re-registra) a ``tarefa`` nomeada a reafirmar no silêncio."""
    with contextlib.suppress(Exception):
        registro_de_gatilhos_de(daemon).registrar(nome, tarefa, atraso_s=atraso_s)


def armar_gatilho(daemon: DaemonProtocol, nome: str, *, evento: str, quantos: int = 1) -> bool:
    """Arma o gatilho ``nome`` por um evento conhecido. RE-ADIA se já armado."""
    registro = registro_de_gatilhos_de(daemon)
    if not registro.armar(nome, time.monotonic(), quantos=quantos):
        logger.debug("gatilho_armar_sem_registro", nome=nome, evento=evento)
        return False
    gatilho = registro.obter(nome)
    logger.info(
        "gatilho_armado",
        nome=nome,
        evento=evento,
        quantos=quantos,
        na_sequencia=gatilho.eventos_armados if gatilho else quantos,
        atraso_s=gatilho.atraso_s if gatilho else None,
    )
    return True


def registrar_gatilho_da_lightbar(daemon: DaemonProtocol) -> None:
    """Fia o caso da LIGHTBAR no mecanismo genérico (GATILHO-DA-COR-01)."""

    def _reafirmar() -> object:
        fora: dict[str, object] = {}
        escrever = getattr(daemon.controller, "reescrever_lightbar_por_hidraw", None)
        if callable(escrever):
            fora["radio"] = escrever()
        cabo = getattr(daemon.controller, "repintar_o_cabo_por_sysfs", None)
        if callable(cabo):
            with contextlib.suppress(Exception):
                fora["cabo"] = cabo()
        return fora or None

    registrar_gatilho(
        daemon,
        NOME_DO_GATILHO_DA_LIGHTBAR,
        _reafirmar,
        atraso_s=ATRASO_APOS_A_ULTIMA_CONEXAO_S,
    )


def _preparar_a_lightbar(daemon: DaemonProtocol) -> None:
    """O PREPARO do gatilho da lightbar: solta as lâmpadas e republica o co-op."""
    with contextlib.suppress(Exception):
        soltar = getattr(
            getattr(daemon, "identity_registry", None), "liberar_as_lampadas", None
        )
        if callable(soltar):
            soltar()
    publicar = getattr(getattr(daemon, "_coop_manager", None), "publicar_os_numeros", None)
    if callable(publicar):
        try:
            publicar(escrever=False)
        except Exception as exc:
            logger.warning("gatilho_da_cor_preparo_falhou", err=str(exc))


_PREPAROS: dict[str, Callable[[DaemonProtocol], None]] = {
    NOME_DO_GATILHO_DA_LIGHTBAR: _preparar_a_lightbar,
}


def armar_gatilho_da_cor_por_evento(daemon: DaemonProtocol, evento: str) -> None:
    """Arma o gatilho da lightbar por um evento que NÃO é conexão nova."""
    registrar_gatilho_da_lightbar(daemon)
    armar_gatilho(daemon, NOME_DO_GATILHO_DA_LIGHTBAR, evento=evento)


def armar_gatilho_da_cor(daemon: DaemonProtocol) -> int:
    """Arma o gatilho da lightbar com as conexões novas que o backend contou."""
    consumir = getattr(daemon.controller, "consumir_conexoes_bt_novas", None)
    if not callable(consumir):
        return 0
    try:
        novas = int(consumir() or 0)
    except Exception as exc:
        logger.debug("gatilho_da_cor_sinal_falhou", err=str(exc))
        return 0
    if novas <= 0:
        return 0
    armar_gatilho(
        daemon, NOME_DO_GATILHO_DA_LIGHTBAR, evento="conexao_bt_nova", quantos=novas
    )
    return novas


_ATRIBUTO_DA_NUMERACAO = "_ultima_numeracao_da_mesa"


def armar_gatilho_da_cor_por_numeracao(daemon: DaemonProtocol) -> bool:
    """Arma o gatilho quando o NÚMERO de alguém muda. Devolve se armou."""
    registro = getattr(daemon, "identity_registry", None)
    ler = getattr(registro, "numeros_da_mesa", None)
    if not callable(ler):
        return False
    try:
        agora = dict(ler() or {})
    except Exception as exc:
        logger.debug("gatilho_da_cor_numeracao_falhou", err=str(exc))
        return False
    antes = getattr(daemon, _ATRIBUTO_DA_NUMERACAO, None)
    with contextlib.suppress(Exception):
        setattr(daemon, _ATRIBUTO_DA_NUMERACAO, agora)
    if antes is None or antes == agora:
        return False
    registrar_gatilho_da_lightbar(daemon)
    armar_gatilho(
        daemon,
        NOME_DO_GATILHO_DA_LIGHTBAR,
        evento="numeracao_da_mesa_mudou",
        quantos=len(agora),
    )
    logger.info("gatilho_da_cor_por_numeracao", antes=antes, agora=agora)
    return True


def sentinela_de_escritor_cru_de(daemon: DaemonProtocol) -> SentinelaDeEscritorCru:
    """O `SentinelaDeEscritorCru` DESTE daemon, criado na primeira consulta."""
    sentinela = getattr(daemon, "_sentinela_de_escritor_cru", None)
    if isinstance(sentinela, SentinelaDeEscritorCru):
        return sentinela
    sentinela = SentinelaDeEscritorCru()
    with contextlib.suppress(Exception):
        daemon._sentinela_de_escritor_cru = sentinela
    return sentinela


async def vigiar_escritor_cru(daemon: DaemonProtocol, *, forcar: bool) -> int:
    """Sonda quem segura o hidraw e ARMA o gatilho da cor quando é o caso.

    ESCRITOR-CRU-01 — a metade que faltava do GATILHO-DA-COR-01. O gatilho já
    existia, já escrevia o report que venceu a Steam na bancada de 12/08, e já
    esperava a rajada passar; o que ele **não** tinha era um evento para a
    situação que a madrugada de 16/08 mediu. Dois eventos entram aqui, e cada
    um responde a uma metade da medição:

    - ``pintura_com_escritor_cru``. O produto pintou (contador do `_pintar_por_hidraw_bt`) e
      há um escritor cru segurando o nó: quem escrever por ÚLTIMO ganha, e
      hoje é ela. O gatilho reafirma 1,5 s depois que a sequência de comandos
      sossega — uma escrita por rajada, não uma por comando;
    - ``escritor_cru_novo`` — *"o daemon NÃO reagiu em 60 s"*. Um nó que estava
      livre passou a ser segurado: é a assinatura da Steam subindo, que é
      exatamente quando ela repinta tudo o que enxerga (medido em 12/08:
      98 reports de saída numa probe com ela viva, contra 6 sem ela).

    **Modo Nativo é no-op TOTAL — nem sonda.** Regra de produto, literal. Ali o dono do hidraw é o
    jogo, e um escritor cru não
    é intruso: é o dono. Sondar seria gastar `pgrep` para concluir que sim, o
    jogo está lá. 24/09/2026 (`D-2309-NO-NATIVO-A-LUZ-E-O-NUMERO-SAO-DO-
    HEFESTO`): a barra e o número passaram a ser do Hefesto no Nativo também, e
    quem os defende ali é a `VigiaDoSequestro` (em até 1 s); esta sonda segue
    calada para não pagar o `pgrep` duas vezes pelo mesmo nó.

    ``forcar`` é o tique de 30 s do `reconnect_loop` (o único com orçamento
    para o `pgrep`); sem ele, só sonda quando o produto acabou de pintar, e
    ainda assim reaproveita a foto dentro da validade. Em mesa parada com a
    Steam aberta o dia inteiro isto custa **duas sondas por minuto e ZERO
    escritas** — o custo de não sondar seria a barra apagada dela.

    Devolve quantos eventos armaram o gatilho (0 = nada a fazer). Best-effort:
    nada aqui pode derrubar o laço de reconexão.

    Preço declarado: a sonda vai pelo `_run_blocking` (executor de 2 threads,
    o mesmo do `connect`/`read_state`) e o pior caso dela são os dois `pgrep`
    com 1 s de timeout cada. É o mesmo custo que a sonda de holders do
    inventário de externos já paga; fica registrado porque um `pgrep`
    pendurado ocupa um worker, e este laço divide o executor com o poll loop.
    """
    with contextlib.suppress(Exception):
        if daemon.is_native_mode():
            return 0
    consumir = getattr(daemon.controller, "consumir_pinturas_de_lightbar", None)
    pinturas = 0
    if callable(consumir):
        with contextlib.suppress(Exception):
            pinturas = int(consumir() or 0)
    if not forcar and pinturas <= 0:
        return 0
    nos_por_uniq: dict[str, str] = {}
    mapear = getattr(daemon.controller, "nos_hidraw_por_uniq", None)
    if callable(mapear):
        with contextlib.suppress(Exception):
            nos_por_uniq = dict(mapear() or {})
    if not nos_por_uniq:
        return 0
    sentinela = sentinela_de_escritor_cru_de(daemon)
    nos = sorted(set(nos_por_uniq.values()))
    agora = time.monotonic()

    def _sondar() -> tuple[Veredito, tuple[str, ...]]:
        return sentinela.sondar(nos, agora, forcar=forcar)

    try:
        veredito, novos = await daemon._run_blocking(_sondar)
    except Exception as exc:
        logger.debug("escritor_cru_vigia_falhou", err=str(exc))
        return 0
    armados = 0
    if novos:
        logger.info(
            "lightbar_escritor_cru_detectado",
            nos=list(novos),
            pids=sorted({p for n in novos for p in veredito.pids(n)}),
        )
        registrar_gatilho_da_lightbar(daemon)
        if armar_gatilho(
            daemon,
            NOME_DO_GATILHO_DA_LIGHTBAR,
            evento="escritor_cru_novo",
            quantos=len(novos),
        ):
            armados += 1
    elif pinturas > 0 and veredito.algum:
        registrar_gatilho_da_lightbar(daemon)
        if armar_gatilho(
            daemon,
            NOME_DO_GATILHO_DA_LIGHTBAR,
            evento="pintura_com_escritor_cru",
            quantos=pinturas,
        ):
            armados += 1
    return armados


def vigia_do_sequestro_de(daemon: DaemonProtocol) -> VigiaDoSequestro:
    """A `VigiaDoSequestro` DESTE daemon, criada na primeira consulta."""
    vigia = getattr(daemon, "_vigia_do_sequestro", None)
    if isinstance(vigia, VigiaDoSequestro):
        return vigia
    vigia = VigiaDoSequestro()
    with contextlib.suppress(Exception):
        daemon._vigia_do_sequestro = vigia
    return vigia


MARCOS_DA_REESCRITA: tuple[int, ...] = (10, 100, 1_000, 10_000, 100_000)


def _endereco_mascarado(valor: object) -> str:
    """O endereço de rádio, em qualquer grafia (com `:` ou sem), com a máscara."""
    hexa = endereco_normalizado(valor)
    if len(hexa) != 12:
        return str(valor)
    return mascarar(":".join(hexa[i : i + 2] for i in range(0, 12, 2)))


def _nascimentos_condenados_entre(
    daemon: DaemonProtocol, uniqs: Sequence[str]
) -> list[str]:
    """Os controles, entre estes, cujo nascimento o cartório carimbou condenado."""
    cartorio = getattr(daemon, "_cartorio_do_nascimento", None)
    if not isinstance(cartorio, CartorioDoNascimento):
        return []
    condenados: list[str] = []
    for uniq in uniqs:
        with contextlib.suppress(Exception):
            carimbo = cartorio.do_uniq(uniq)
            if carimbo is not None and carimbo.pede_reconexao:
                condenados.append(uniq)
    return condenados


async def vigiar_o_sequestro(
    daemon: DaemonProtocol, *, agora: float | None = None
) -> int:
    """Reescreve a barra e o número de quem outro processo sequestrou."""
    vigia = vigia_do_sequestro_de(daemon)
    nos_por_uniq: dict[str, str] = {}
    mapear = getattr(daemon.controller, "nos_hidraw_por_uniq", None)
    if callable(mapear):
        with contextlib.suppress(Exception):
            nos_por_uniq = dict(mapear() or {})
    agora = time.monotonic() if agora is None else float(agora)
    nos = sorted(set(nos_por_uniq.values()))
    passo: PassoDaVigia
    try:
        sondar = vigia.quer_sondar(nos, agora)
        if sondar:
            def _passo() -> PassoDaVigia:
                return vigia.passo(nos, agora, sondar=True)

            passo = await daemon._run_blocking(_passo)
        else:
            passo = vigia.passo(nos, agora, sondar=False)
    except Exception as exc:
        logger.debug("vigia_do_sequestro_falhou", err=str(exc))
        return 0
    for no in passo.novos:
        logger.info(
            "sequestro_detectado",
            no=no,
            pids=list(passo.pids.get(no, ())),
            modo_nativo=_modo_nativo(daemon),
        )
    for no in passo.soltos:
        logger.info(
            "sequestro_encerrado",
            no=no,
            pids=list(passo.pids.get(no, ())),
            reescritas=vigia.encerrar(no),
        )
    if not passo.a_reafirmar:
        return 0
    alvos = set(passo.a_reafirmar)
    uniqs = sorted(u for u, no in nos_por_uniq.items() if no in alvos)
    reafirmar = getattr(daemon.controller, "reafirmar_barra_e_numero", None)
    if not uniqs or not callable(reafirmar):
        return 0

    def _reafirmar() -> object:
        return reafirmar(uniqs)

    try:
        resultado = await daemon._run_blocking(_reafirmar)
    except Exception as exc:
        logger.warning("vigia_do_sequestro_reafirmar_falhou", err=str(exc))
        return 0
    vigia.reafirmado(passo.a_reafirmar, agora)
    if passo.novos:
        campos: dict[str, object] = {
            "uniqs": [_endereco_mascarado(u) for u in uniqs],
            "escrita_aceita": (
                {_endereco_mascarado(k): bool(v) for k, v in resultado.items()}
                if isinstance(resultado, Mapping)
                else resultado
            ),
        }
        condenados = _nascimentos_condenados_entre(daemon, uniqs)
        if condenados:
            campos["nascimento_condenado"] = [_endereco_mascarado(u) for u in condenados]
        logger.info("sequestro_reescrito", **campos)
    for no in passo.a_reafirmar:
        reescritas = vigia.reescritas(no)
        if reescritas in MARCOS_DA_REESCRITA:
            logger.info(
                "sequestro_segue",
                no=no,
                reescritas=reescritas,
                pids=list(vigia.sequestrados.get(no, ())),
            )
    return len(uniqs)


def _modo_nativo(daemon: DaemonProtocol) -> bool:
    """O daemon está em Modo Nativo? Para o diário, e para o cabo que espera o jogo soltar."""
    with contextlib.suppress(Exception):
        return bool(daemon.is_native_mode())
    return False


def cartorio_do_nascimento_de(daemon: DaemonProtocol) -> CartorioDoNascimento:
    """O `CartorioDoNascimento` DESTE daemon, criado na primeira consulta."""
    cartorio = getattr(daemon, "_cartorio_do_nascimento", None)
    if isinstance(cartorio, CartorioDoNascimento):
        return cartorio
    cartorio = CartorioDoNascimento()
    with contextlib.suppress(Exception):
        daemon._cartorio_do_nascimento = cartorio
    return cartorio


def _nos_segurados_agora(daemon: DaemonProtocol) -> frozenset[str]:
    """Os nós que a sonda do PRÓPRIO daemon vê segurados na foto mais recente."""
    with contextlib.suppress(Exception):
        veredito = sentinela_de_escritor_cru_de(daemon).veredito
        if veredito.sondado:
            return frozenset(veredito.nos_segurados_de_fato())
    return frozenset()


def _uniqs_que_o_backend_segura(daemon: DaemonProtocol) -> frozenset[str]:
    """Os endereços dos controles que o produto tem ABERTOS agora, NORMALIZADOS.

    É o mesmo `nos_hidraw_por_uniq` que o vigia de escritor cru usa — nenhum
    segundo vigia, nenhuma segunda verdade sobre quem está na mesa. Vazio
    quando o controller é enxuto (dublês da suíte) ou nada está aberto, e aí o
    carimbo é no-op TOTAL.

    A normalização é a cura de 25/08/2026, e ela vale por si: o backend chaveia
    sem os dois-pontos (`_key_to_uniq` → `norm_mac` → `a0fa9c…`) e o sysfs
    devolve com (`HID_UNIQ=a0:fa:9c:…`, MEDIDO no `uevent` do DualSense do cabo
    desta máquina). Enquanto os dois lados eram comparados crus, o filtro logo
    abaixo descartava TODAS as instâncias e o tique carimbava zero — a E1 da
    SINAL-NO-NASCIMENTO-01 estava declarada entregue e não rodava em produção.
    """
    mapear = getattr(daemon.controller, "nos_hidraw_por_uniq", None)
    if not callable(mapear):
        return frozenset()
    try:
        return frozenset(
            chave for chave in (endereco_normalizado(u) for u in (mapear() or {})) if chave
        )
    except Exception as exc:
        logger.debug("carimbo_do_nascimento_mapa_falhou", err=str(exc))
        return frozenset()


def _sem_sonda_no_modo_nativo(alvos: Sequence[Instancia]) -> list[Leitura]:
    """O veredito honesto do Modo Nativo: `nao_sei`, e nunca `limpa`."""
    return [
        Leitura(
            alvo=alvo,
            confianca=CONFIANCA_NAO_SEI,
            porque=(
                "o Modo Nativo devolve o controle à Steam e o produto não sonda "
                "quem segura o nó — não dá para saber como esta conexão nasceu"
            ),
        )
        for alvo in alvos
    ]


async def carimbar_o_nascimento(
    daemon: DaemonProtocol, *, agora: float | None = None
) -> int:
    """Carimba, no tique de hotplug, como cada conexão VIVA nasceu."""
    cartorio = cartorio_do_nascimento_de(daemon)
    nossos = _uniqs_que_o_backend_segura(daemon)
    if not nossos:
        return 0
    try:
        vivas = await daemon._run_blocking(instancias_dualsense)
    except Exception as exc:
        logger.debug("carimbo_do_nascimento_sysfs_falhou", err=str(exc))
        return 0
    # DualSense da máquina, e carimbar um que o produto não segura seria falar
    vivas = [alvo for alvo in vivas if endereco_normalizado(alvo.uniq) in nossos]
    agora = time.monotonic() if agora is None else float(agora)
    try:
        faltam = cartorio.observar(vivas, agora)
    except Exception as exc:  # pragma: no cover — cartório é puro
        logger.debug("carimbo_do_nascimento_cartorio_falhou", err=str(exc))
        return 0
    if not faltam:
        return 0

    nativo = False
    with contextlib.suppress(Exception):
        nativo = bool(daemon.is_native_mode())
    if nativo:
        leituras = _sem_sonda_no_modo_nativo(faltam)
    else:
        def _diagnosticar() -> list[Leitura]:
            return veredito_do_nascimento(instancias=faltam)

        try:
            leituras = await daemon._run_blocking(_diagnosticar)
        except Exception as exc:
            logger.debug("carimbo_do_nascimento_diario_falhou", err=str(exc))
            return 0

    nos = frozenset() if nativo else _nos_segurados_agora(daemon)
    try:
        gravados = cartorio.carimbar(leituras, agora, nos_segurados=nos)
    except Exception as exc:  # pragma: no cover — cartório é puro
        logger.debug("carimbo_do_nascimento_gravacao_falhou", err=str(exc))
        return 0
    for carimbo in gravados:
        if carimbo.pede_reconexao:
            logger.info(
                "nascimento_condenado",
                instancia=carimbo.instancia,
                uniq=mascarar(carimbo.uniq),
                hw_version=carimbo.hw_version,
                pids=list(carimbo.leitura.pids_do_escritor),
                porque=carimbo.porque,
            )
        else:
            logger.debug(
                "nascimento_carimbado",
                instancia=carimbo.instancia,
                uniq=mascarar(carimbo.uniq),
                confianca=carimbo.confianca,
                firme=carimbo.firme,
            )
    return len(gravados)


async def disparar_gatilhos_devidos(daemon: DaemonProtocol) -> int:
    """Chama a tarefa de todo gatilho cuja sequência sossegou. Devolve quantos."""
    registro = registro_de_gatilhos_de(daemon)
    prontos = registro.devidos(time.monotonic())
    for gatilho, eventos in prontos:
        preparo = _PREPAROS.get(gatilho.nome)
        if preparo is not None:
            preparo(daemon)
        try:
            resultado = await daemon._run_blocking(gatilho.tarefa)
        except Exception as exc:
            logger.warning("gatilho_disparo_falhou", nome=gatilho.nome, err=str(exc))
            continue
        logger.info(
            "gatilho_disparou",
            nome=gatilho.nome,
            eventos_na_sequencia=eventos,
            resultado=resultado,
        )
    return len(prontos)


def _firmas_dos_nos(daemon: DaemonProtocol) -> dict[str, tuple[int, int] | None]:
    """`{nó: firma}` dos `hidraw` dos controles abertos — um `stat` por nó."""
    nos: dict[str, str] = {}
    mapear = getattr(daemon.controller, "nos_hidraw_por_uniq", None)
    if callable(mapear):
        with contextlib.suppress(Exception):
            nos = dict(mapear() or {})
    return {no: firma_do_no(no) for no in sorted(set(nos.values()))}


def _permissoes_das_entradas() -> tuple[int, ...] | None:
    """A geração de PERMISSÕES de `/dev/input` no dono do evento; None sem ele."""
    dono = _ode.dono_armado()
    if dono is None:
        return None
    return dono.ficha((dono.raiz_das_entradas, _ode.PERMISSOES))


async def _wait_online_or_hotplug(
    daemon: DaemonProtocol, watch: InputDirWatch
) -> bool:
    """Espera o intervalo online em fatias, sondando o watch de /dev/input."""
    await vigiar_o_sequestro(daemon)
    pelo_evento = _ode.dono_armado() is not None
    teto = (
        TETO_DA_VOLTA_PELO_EVENTO_SEC if pelo_evento else RECONNECT_ONLINE_CHECK_INTERVAL_SEC
    )
    firmas = _firmas_dos_nos(daemon) if pelo_evento else None
    permissoes = _permissoes_das_entradas() if pelo_evento else None
    nos = getattr(daemon, "_watch_dos_hidraw", None) if pelo_evento else None
    elapsed = 0.0
    while elapsed < teto:
        step = min(
            RECONNECT_HOTPLUG_POLL_INTERVAL_SEC,
            teto - elapsed,
        )
        if registro_de_gatilhos_de(daemon).algum_armado():
            step = min(step, PASSO_ENQUANTO_O_GATILHO_ESTA_ARMADO_SEC)
        if vigia_do_sequestro_de(daemon).vigilante:
            step = min(step, PASSO_DA_VIGIA_S)
        await _wait_or_stop(daemon, step)
        if daemon._is_stopping():
            return False
        elapsed += step
        await vigiar_escritor_cru(daemon, forcar=False)
        await vigiar_o_sequestro(daemon)
        await disparar_gatilhos_devidos(daemon)
        armar_gatilho_da_cor_por_numeracao(daemon)
        if watch.poll():
            return True
        if isinstance(nos, InputDirWatch) and _ode.armado() and nos.poll():
            logger.debug("volta_acordada", pelo="hidraw_novo")
            return True
        if firmas is not None and _firmas_dos_nos(daemon) != firmas:
            logger.debug("volta_acordada", pelo="firma_do_no")
            return True
        if permissoes is not None and _permissoes_das_entradas() != permissoes:
            logger.debug("volta_acordada", pelo="permissao_de_entrada")
            return True
        if _o_barramento_hid_mudou(daemon):
            return True
    return False


async def _wait_or_stop(daemon: DaemonProtocol, timeout: float) -> None:
    """Dorme `timeout` segundos respeitando `_stop_event`."""
    stop_event = getattr(daemon, "_stop_event", None)
    if stop_event is None:
        await asyncio.sleep(timeout)
        return
    with contextlib.suppress(asyncio.TimeoutError):
        await asyncio.wait_for(stop_event.wait(), timeout=timeout)


_TETO_DA_TAREFA_S = 5.0


async def _esperar_a_tarefa_cair(task: asyncio.Future[Any]) -> None:
    """Espera a tarefa cancelada terminar, cancelando de novo a cada 0,5 s."""
    relogio = asyncio.get_running_loop()
    prazo = relogio.time() + _TETO_DA_TAREFA_S
    while not task.done():
        if relogio.time() >= prazo:
            nome = getattr(task, "get_name", lambda: repr(task))()
            logger.warning("shutdown_tarefa_nao_caiu", tarefa=nome)
            return
        await asyncio.wait({task}, timeout=0.5)
        if not task.done():
            task.cancel()
    if not task.cancelled():
        with contextlib.suppress(BaseException):
            task.exception()


async def shutdown(daemon: DaemonProtocol) -> None:
    """Encerra todos os recursos do daemon de forma limpa."""
    logger.info("daemon_shutting_down")
    parar_bt_mic = getattr(daemon, "_stop_bt_mic", None)
    if getattr(daemon, "_bt_mic_subsystem", None) is not None and callable(parar_bt_mic):
        with contextlib.suppress(Exception):
            await parar_bt_mic()
    parar_som = getattr(daemon, "_stop_alto_falante", None)
    if getattr(daemon, "_alto_falante_subsystem", None) is not None and callable(
        parar_som
    ):
        with contextlib.suppress(Exception):
            await parar_som()
    central = getattr(daemon, "_central_do_radio", None)
    if central is not None:
        with contextlib.suppress(Exception):
            await asyncio.to_thread(central.fechar)
    parar_conexoes = getattr(daemon, "_stop_conexoes", None)
    if getattr(daemon, "_conexoes_subsystem", None) is not None and callable(
        parar_conexoes
    ):
        with contextlib.suppress(Exception):
            await parar_conexoes()
    if daemon._plugins_subsystem is not None:
        with contextlib.suppress(Exception):
            await daemon._plugins_subsystem.stop()
        daemon._plugins_subsystem = None
    parar_metrics = getattr(daemon, "_stop_metrics", None)
    if getattr(daemon, "_metrics_subsystem", None) is not None and callable(parar_metrics):
        with contextlib.suppress(Exception):
            await parar_metrics()
    daemon._hotkey_manager = None
    daemon._audio = None
    if getattr(daemon, "_coop_manager", None) is not None:
        with contextlib.suppress(Exception):
            daemon._coop_manager.stop_all()
        daemon._coop_manager = None
    if daemon._mouse_device is not None:
        with contextlib.suppress(Exception):
            daemon._mouse_device.stop()
        daemon._mouse_device = None
    if getattr(daemon, "_gamepad_device", None) is not None:
        with contextlib.suppress(Exception):
            from hefesto_dualsense4unix.daemon.subsystems.gamepad import (
                stop_gamepad_emulation,
            )

            stop_gamepad_emulation(daemon, persist=False)
    broker_executor = getattr(daemon, "_hidraw_broker_executor", None)
    if broker_executor is not None:
        with contextlib.suppress(Exception):
            broker_executor.shutdown(wait=False, cancel_futures=True)
        daemon._hidraw_broker_executor = None
    client = getattr(daemon, "_hidraw_broker_client", None)
    if client is not None:
        with contextlib.suppress(Exception):
            client.close()
        daemon._hidraw_broker_client = None
    if getattr(daemon, "_keyboard_device", None) is not None:
        with contextlib.suppress(Exception):
            daemon._keyboard_device.stop()
        daemon._keyboard_device = None
    # `osk.close()` DIRETO, e não `stop_keyboard_emulation`: aquele derruba
    # limpeza quebrada nunca derruba a parada. Vem DEPOIS do device: o
    # `virtual_token_callback` do device aponta para `osk.dispatch_token`, e
    osk = getattr(daemon, "_osk_controller", None)
    if osk is not None:
        with contextlib.suppress(Exception):
            osk.close()
        daemon._osk_controller = None
    if daemon._ipc_server is not None:
        with contextlib.suppress(Exception):
            await asyncio.wait_for(daemon._ipc_server.stop(), timeout=2.0)
        daemon._ipc_server = None
    if daemon._udp_server is not None:
        with contextlib.suppress(Exception):
            await asyncio.wait_for(daemon._udp_server.stop(), timeout=2.0)
        daemon._udp_server = None
    if daemon._autoswitch is not None:
        with contextlib.suppress(Exception):
            daemon._autoswitch.stop()
        daemon._autoswitch = None
    daemon._last_state = None
    for task in daemon._tasks:
        task.cancel()
    for task in daemon._tasks:
        await _esperar_a_tarefa_cair(task)
    daemon._reconnect_task = None
    try:
        await daemon._run_blocking(daemon.controller.disconnect)
    except Exception as exc:
        logger.warning("controller_disconnect_failed", err=str(exc))
    if daemon._executor is not None:
        daemon._executor.shutdown(wait=False, cancel_futures=True)
        daemon._executor = None
    if daemon._external_executor is not None:
        daemon._external_executor.shutdown(wait=False, cancel_futures=True)
        daemon._external_executor = None
    daemon._tasks.clear()
    logger.info("daemon_stopped")


__all__ = [
    "BACKOFF_MAX_SEC",
    "PASSO_ENQUANTO_O_GATILHO_ESTA_ARMADO_SEC",
    "PASSO_ENQUANTO_UM_CONTROLE_TROCA_DE_TRANSPORTE_SEC",
    "RECONNECT_HOTPLUG_POLL_INTERVAL_SEC",
    "RECONNECT_ONLINE_CHECK_INTERVAL_SEC",
    "RECONNECT_PROBE_INTERVAL_SEC",
    "TETO_DA_VOLTA_PELO_EVENTO_SEC",
    "Tarefa",
    "armar_gatilho",
    "armar_gatilho_da_cor",
    "armar_gatilho_da_cor_por_evento",
    "armar_gatilho_da_cor_por_numeracao",
    "connect_with_retry",
    "disparar_gatilhos_devidos",
    "reaplicar_som_de_quem_trocou_de_transporte",
    "reapply_mic_after_connect",
    "reapply_speaker_after_connect",
    "reconnect",
    "reconnect_loop",
    "registrar_gatilho",
    "registrar_gatilho_da_lightbar",
    "registro_de_gatilhos_de",
    "restore_last_profile",
    "sentinela_de_escritor_cru_de",
    "shutdown",
    "transportes_dos_alvos_de",
    "trocas_de_transporte_pendentes",
    "vigia_do_cabo_de",
    "vigia_do_sequestro_de",
    "vigiar_escritor_cru",
    "vigiar_o_cabo_em_espera",
    "vigiar_o_sequestro",
]
