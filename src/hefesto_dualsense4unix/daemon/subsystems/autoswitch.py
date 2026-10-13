"""Subsystem Autoswitch — gerencia troca automática de perfis por janela ativa."""
from __future__ import annotations

import contextlib
import os
import time
from typing import TYPE_CHECKING, Any

from hefesto_dualsense4unix.core.events import EventTopic
from hefesto_dualsense4unix.utils.logging_config import get_logger

if TYPE_CHECKING:
    from collections.abc import Callable

    from hefesto_dualsense4unix.core.events import EventBus
    from hefesto_dualsense4unix.daemon.context import DaemonContext
    from hefesto_dualsense4unix.daemon.lifecycle import DaemonConfig
    from hefesto_dualsense4unix.daemon.protocols import DaemonProtocol
    from hefesto_dualsense4unix.daemon.state_store import StateStore

logger = get_logger(__name__)


#: As variáveis do ambiente gráfico que o serviço precisa ter para o Xlib e o Wayland falarem:
#: o X recusa o cliente sem o arquivo de autorização (GNOME e KDE), e a cascata Wayland não vê nada.
_VARIAVEIS_DO_DISPLAY: tuple[str, ...] = ("WAYLAND_DISPLAY", "DISPLAY", "XAUTHORITY")


def _ensure_display_env() -> None:
    """Completa o que faltar de DISPLAY/WAYLAND_DISPLAY/XAUTHORITY pelo `systemctl --user`.

    Só pergunta ao `systemctl` quando alguma das três falta, e importa só a que falta: o resgate
    de 15 s traz a autorização que chegou depois do display.
    """
    if all(os.environ.get(chave) for chave in _VARIAVEIS_DO_DISPLAY):
        return
    import shutil
    import subprocess

    systemctl = shutil.which("systemctl")
    if systemctl is None:
        return
    try:
        result = subprocess.run(
            [systemctl, "--user", "show-environment"],
            capture_output=True,
            text=True,
            timeout=2,
            check=False,
        )
    except Exception as exc:
        logger.debug("autoswitch_display_env_probe_failed", err=str(exc))
        return
    for line in result.stdout.splitlines():
        key, _, value = line.partition("=")
        if key in _VARIAVEIS_DO_DISPLAY and value and not os.environ.get(key):
            os.environ[key] = value
            logger.info("autoswitch_display_env_imported", var=key)


def _o_jogo_em_cena_do_servico(daemon: object) -> Callable[[], int | None]:
    """O leitor do jogo em cena: o `appid_em_cena` do serviço, lido a cada tique (memória)."""

    def _ler() -> int | None:
        appid = getattr(daemon, "appid_em_cena", None)
        if isinstance(appid, int) and not isinstance(appid, bool) and appid > 0:
            return appid
        return None

    return _ler


class AnunciadorDoJogo:
    """Diz no barramento o perfil que mudou (`perfil.trocou`) e o jogo que fechou (`jogo.fechou`).

    A-VIBRACAO-DO-CONTROLE-CHEGA-AOS-ACESSORIOS-PELO-BUTTPLUG-01. Olha o que o serviço já
    sabe a cada leitura da janela, que é o tique do autoswitch: o perfil ativo do store, que
    toda ativação publica, de qualquer origem (a janela, o jogo em cena, a tela, o terminal), e
    o `appid_em_cena` do serviço. A primeira leitura diz o perfil de agora (a carga inicial), e
    o barramento o guarda para quem assina depois. A marca que muda no arquivo do perfil que
    já está ativo (a pessoa marca o jogo aberto) também é troca: o estado guardado não pode
    ficar velho. Quando o jogo fecha, quem vibrava recebe primeiro o zero que faltava e só
    depois sai `jogo.fechou`, e a batida para.
    """

    _NUNCA: object = object()

    def __init__(self, bus: EventBus, store: Any, daemon: Any) -> None:
        self._bus = bus
        self._store = store
        self._daemon = daemon
        self._perfil: object = self._NUNCA
        self._arquivo: object = self._NUNCA
        self._appid: int | None = None

    def ver(self) -> None:
        """Compara com o que disse da última vez e diz a diferença. Nunca levanta."""
        for passo in (self._ver_o_perfil, self._ver_o_jogo):
            try:
                passo()
            except Exception as exc:
                logger.debug("anunciador_do_jogo_falhou", passo=passo.__name__, err=str(exc))

    def _ver_o_perfil(self) -> None:
        nome = getattr(self._store, "active_profile", None)
        nome = nome if isinstance(nome, str) and nome else None
        arquivo = (nome, _carimbo_do_perfil(nome))
        if arquivo == self._arquivo:
            return
        self._arquivo = arquivo
        dito = (nome, _marcas_do_perfil(nome))
        if dito == self._perfil:
            return
        self._perfil = dito
        self._bus.publish(
            EventTopic.PERFIL_TROCOU,
            {"perfil": dito[0], "marcas": dito[1], "t": time.monotonic()},
        )

    def _ver_o_jogo(self) -> None:
        appid = getattr(self._daemon, "appid_em_cena", None)
        appid = appid if isinstance(appid, int) and not isinstance(appid, bool) else None
        anterior, self._appid = self._appid, appid
        if anterior is None or appid == anterior:
            return
        from hefesto_dualsense4unix.daemon.subsystems.vibracao_do_jogo import (
            esquecer_a_vibracao,
        )

        esquecer_a_vibracao(self._daemon)
        self._bus.publish(
            EventTopic.JOGO_FECHOU, {"appid": anterior, "t": time.monotonic()}
        )


def _carimbo_do_perfil(nome: str | None) -> int | None:
    """O `st_mtime_ns` do arquivo do perfil: um `stat` por leitura, sem decodificar o JSON."""
    if nome is None:
        return None
    from hefesto_dualsense4unix.profiles.slug import slugify
    from hefesto_dualsense4unix.utils.xdg_paths import profiles_dir

    try:
        return (profiles_dir() / f"{slugify(nome)}.json").stat().st_mtime_ns
    except (OSError, ValueError):
        return None


def _marcas_do_perfil(nome: str | None) -> list[str]:
    """As marcas que o arquivo do perfil guarda agora, sem semear nem varrer o disco."""
    if nome is None:
        return []
    from hefesto_dualsense4unix.profiles.loader import perfil_em_disco

    perfil = perfil_em_disco(nome)
    marcas = getattr(perfil, "marcas", None)
    return [m for m in marcas if isinstance(m, str)] if marcas else []


def _anunciador_do(bus: object, store: Any, daemon: object) -> AnunciadorDoJogo | None:
    """O anunciador do serviço, ou `None` sem barramento (um dublê enxuto de teste)."""
    publicar = getattr(bus, "publish", None)
    return AnunciadorDoJogo(bus, store, daemon) if callable(publicar) else None  # type: ignore[arg-type]


def _anunciando(
    leitor: Callable[[], dict[str, Any]], anunciador: AnunciadorDoJogo | None
) -> Callable[[], dict[str, Any]]:
    """O leitor de janela do autoswitch, que a cada leitura deixa o anunciador olhar o serviço."""
    if anunciador is None:
        return leitor

    def _le() -> dict[str, Any]:
        info = leitor()
        anunciador.ver()
        return info

    return _le


def _build_diag_window_reader(store: StateStore) -> Callable[[], dict[str, Any]]:
    """Constrói o window reader e o instrumenta com diagnóstico no store."""
    from hefesto_dualsense4unix.integrations.window_detect import build_window_reader

    reader = build_window_reader()

    def _backend_name() -> str | None:
        name = getattr(reader, "backend_name", None)
        return name if isinstance(name, str) else None

    def _saude_com_prova(backend: str | None) -> bool:
        """`healthy` inicial de um backend recém-escolhido, com PROVA."""
        if backend != "xlib":
            return False
        reader()
        conexao_provada = getattr(reader, "conexao_provada", None)
        return callable(conexao_provada) and conexao_provada() is True

    initial_backend = _backend_name()
    initial_healthy = _saude_com_prova(initial_backend)
    store.set_window_detect_backend(initial_backend, healthy=initial_healthy)
    logger.info(
        "window_detect_diag_seeded",
        backend=initial_backend,
        healthy=initial_healthy,
    )

    _recover_next = [0.0]

    def _read() -> dict[str, Any]:
        recover = getattr(reader, "maybe_recover", None)
        precisa = getattr(reader, "precisa_de_resgate", None)
        cego = precisa() if callable(precisa) else (_backend_name() == "null")
        if callable(recover) and cego:
            import time

            agora = time.monotonic()
            if agora >= _recover_next[0]:
                _recover_next[0] = agora + 15.0
                _ensure_display_env()
                if recover():
                    nome = _backend_name()
                    store.set_window_detect_backend(
                        nome, healthy=_saude_com_prova(nome)
                    )
                    logger.info(
                        "window_detect_backend_recuperado", backend=nome
                    )
        info = reader()
        wm_class = info.get("wm_class")
        store.record_window_detect_read(
            _backend_name(),
            wm_class if isinstance(wm_class, str) else None,
            reason=getattr(reader, "last_reason", None),
        )
        return info

    return _read


class AutoswitchSubsystem:
    """Subsystem que gerencia o AutoSwitcher de perfis."""

    name = "autoswitch"
    _autoswitch: Any = None

    async def start(self, ctx: DaemonContext) -> None:
        """Inicia o AutoSwitcher com as dependências do DaemonContext."""
        from hefesto_dualsense4unix.integrations import lista_de_exclusao
        from hefesto_dualsense4unix.profiles.autoswitch import AutoSwitcher
        from hefesto_dualsense4unix.profiles.manager import gerente_do_daemon

        _ensure_display_env()
        daemon = getattr(ctx, "daemon", None)
        manager = gerente_do_daemon(daemon, controller=ctx.controller, store=ctx.store)
        self._autoswitch = AutoSwitcher(
            manager=manager,
            window_reader=_anunciando(
                _build_diag_window_reader(ctx.store),
                _anunciador_do(getattr(ctx, "bus", None), ctx.store, daemon),
            ),
            store=ctx.store,
            modo_jogo_padrao_applier=getattr(
                daemon, "aplicar_modo_jogo_padrao", None
            ),
            modo_jogo_padrao_reverter=getattr(
                daemon, "reverter_modo_jogo_padrao", None
            ),
            exclusao_applier=getattr(daemon, "aplicar_a_exclusao", None),
            exclusao_reverter=getattr(daemon, "reverter_a_exclusao", None),
            exclusao_reader=lista_de_exclusao.contem,
            jogo_em_cena_reader=_o_jogo_em_cena_do_servico(daemon),
        )
        if not self._autoswitch.disabled():
            self._autoswitch.start()
            logger.info("autoswitch_subsystem_started")
        else:
            logger.info("autoswitch_subsystem_disabled_by_config")

    async def stop(self) -> None:
        """Para o AutoSwitcher de forma limpa. Idempotente."""
        if self._autoswitch is not None:
            with contextlib.suppress(Exception):
                self._autoswitch.stop()
            self._autoswitch = None
            logger.info("autoswitch_subsystem_stopped")

    def is_enabled(self, config: DaemonConfig) -> bool:
        return config.autoswitch_enabled


async def start_autoswitch(daemon: DaemonProtocol) -> None:
    """Função utilitária: inicia o AutoSwitcher usando o Daemon diretamente."""
    from hefesto_dualsense4unix.integrations import lista_de_exclusao
    from hefesto_dualsense4unix.profiles.autoswitch import AutoSwitcher
    from hefesto_dualsense4unix.profiles.manager import gerente_do_daemon

    _ensure_display_env()
    manager = gerente_do_daemon(daemon, store=daemon.store)
    daemon._autoswitch = AutoSwitcher(
        manager=manager,
        window_reader=_anunciando(
            _build_diag_window_reader(daemon.store),
            _anunciador_do(getattr(daemon, "bus", None), daemon.store, daemon),
        ),
        store=daemon.store,
        modo_jogo_padrao_applier=getattr(daemon, "aplicar_modo_jogo_padrao", None),
        modo_jogo_padrao_reverter=getattr(daemon, "reverter_modo_jogo_padrao", None),
        exclusao_applier=getattr(daemon, "aplicar_a_exclusao", None),
        exclusao_reverter=getattr(daemon, "reverter_a_exclusao", None),
        exclusao_reader=lista_de_exclusao.contem,
        jogo_em_cena_reader=_o_jogo_em_cena_do_servico(daemon),
    )
    if not daemon._autoswitch.disabled():
        daemon._autoswitch.start()


__all__ = ["AnunciadorDoJogo", "AutoswitchSubsystem", "start_autoswitch"]
