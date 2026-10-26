"""Subsystem Autoswitch — gerencia troca automática de perfis por janela ativa."""
from __future__ import annotations

import os
import time
from typing import TYPE_CHECKING, Any

from hefesto_dualsense4unix.core.events import EventTopic
from hefesto_dualsense4unix.utils.logging_config import get_logger

if TYPE_CHECKING:
    from collections.abc import Callable

    from hefesto_dualsense4unix.core.events import EventBus
    from hefesto_dualsense4unix.daemon.protocols import DaemonProtocol
    from hefesto_dualsense4unix.daemon.state_store import StateStore

logger = get_logger(__name__)


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

    O `perfil.trocou` diz QUAL jogo é, e nunca leva marca: `perfil`, `jogo` (`steam_app_<N>`,
    ou `None` fora de jogo), `estilo` e `controles` (jogador, perfil, jogo e estilo de cada um).
    Publica só quando o dito muda; a primeira leitura é a carga inicial, que o barramento guarda.
    Quando o jogo fecha, sai o zero de quem vibrava, depois `jogo.fechou`, depois o perfil sem jogo.
    `jogo_de(uniq)` dá o appid de UM controle; sem ele, todos estão no jogo em cena do serviço.
    """

    _NUNCA: object = object()

    def __init__(
        self,
        bus: EventBus,
        store: Any,
        daemon: Any,
        jogo_de: Callable[[str], int | None] | None = None,
    ) -> None:
        self._bus = bus
        self._store = store
        self._daemon = daemon
        self._jogo_de = jogo_de
        self._perfil: object = self._NUNCA
        self._arquivo: object = self._NUNCA
        self._estilo: str | None = None
        self._appid: int | None = None

    def ver(self) -> None:
        """Compara com o que disse da última vez e diz a diferença. Nunca levanta."""
        for passo in (self._ver_o_jogo, self._ver_o_perfil):
            try:
                passo()
            except Exception as exc:
                logger.debug("anunciador_do_jogo_falhou", passo=passo.__name__, err=str(exc))

    def _ver_o_perfil(self) -> None:
        nome = getattr(self._store, "active_profile", None)
        nome = nome if isinstance(nome, str) and nome else None
        arquivo = (nome, _carimbo_do_perfil(nome))
        if arquivo != self._arquivo:
            self._estilo = _estilo_do_perfil(nome)
            self._arquivo = arquivo
        controles = self._controles(nome)
        dito = (nome, self._estilo, _chave_do_jogo(self._em_cena()), controles)
        if dito == self._perfil:
            return
        self._perfil = dito
        self._bus.publish(
            EventTopic.PERFIL_TROCOU,
            {
                "perfil": dito[0],
                "estilo": dito[1],
                "jogo": dito[2],
                "controles": [dict(c) for c in controles],
                "t": time.monotonic(),
            },
        )

    def _em_cena(self) -> int | None:
        appid = getattr(self._daemon, "appid_em_cena", None)
        return appid if isinstance(appid, int) and not isinstance(appid, bool) else None

    def _controles(self, nome: str | None) -> tuple[tuple[tuple[str, Any], ...], ...]:
        """Um item por controle, na ordem do serviço; cada item é um mapa congelado (comparável)."""
        from hefesto_dualsense4unix.daemon.subsystems.tato_vivo import controles_do_daemon
        from hefesto_dualsense4unix.daemon.subsystems.vibracao_do_jogo import _jogador_de

        itens = []
        for controle in controles_do_daemon(self._daemon):
            appid = self._jogo_de(controle.uniq) if self._jogo_de is not None else self._em_cena()
            itens.append((
                ("jogador", _jogador_de(self._daemon, controle.uniq)),
                ("perfil", nome),
                ("jogo", _chave_do_jogo(appid)),
                ("estilo", self._estilo),
            ))
        return tuple(itens)

    def _ver_o_jogo(self) -> None:
        appid = self._em_cena()
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
    """O `st_mtime_ns` do arquivo do perfil: um `stat` por leitura, sem decodificar o JSON.

    O arquivo que some entre o `exists` e o `stat` levanta, e o `ver` do anunciador o registra e
    tenta de novo na leitura seguinte.
    """
    if nome is None:
        return None
    from hefesto_dualsense4unix.profiles.slug import slugify
    from hefesto_dualsense4unix.utils.xdg_paths import profiles_dir

    alvo = profiles_dir() / f"{slugify(nome)}.json"
    return alvo.stat().st_mtime_ns if alvo.exists() else None


def _estilo_do_perfil(nome: str | None) -> str | None:
    """O estilo que o arquivo do perfil guarda agora, sem semear nem varrer o disco."""
    if nome is None:
        return None
    from hefesto_dualsense4unix.profiles.loader import perfil_em_disco

    estilo = getattr(perfil_em_disco(nome), "estilo", None)
    return estilo if isinstance(estilo, str) and estilo else None


def _chave_do_jogo(appid: int | None) -> str | None:
    """A chave do jogo no evento: a classe de janela da Steam, ou `None` fora de jogo."""
    return f"steam_app_{appid}" if appid is not None and appid > 0 else None


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


__all__ = ["AnunciadorDoJogo", "start_autoswitch"]
