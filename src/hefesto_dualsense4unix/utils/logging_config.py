"""Configuração de logging do daemon com structlog."""
from __future__ import annotations

import atexit
import logging
import os
import re
import sys
import threading
import time
import traceback
from collections.abc import Callable, MutableMapping
from typing import TYPE_CHECKING, Any

import structlog

from hefesto_dualsense4unix.core import formas_do_endereco as _formas

if TYPE_CHECKING:
    from structlog.typing import Processor
else:
    try:
        from structlog.typing import Processor
    except ImportError:
        try:
            from structlog.types import Processor
        except ImportError:
            Processor = Callable[..., Any]  # type: ignore[misc,assignment]

_configured = False

#: As cores do terminal que o ``ConsoleRenderer`` põe em volta de cada valor.
_COR_DO_TERMINAL = re.compile(r"(\x1b\[[0-9;]*m)")


def mascarar_a_linha(texto: str) -> str:
    """A linha do diário na máscara da casa. Nunca levanta."""
    try:
        if "\x1b[" not in texto:
            return _formas.mascarar(texto)
        partes = _COR_DO_TERMINAL.split(texto)
        return "".join(
            parte if i % 2 else _formas.mascarar(parte) for i, parte in enumerate(partes)
        )
    except Exception as erro:
        return f"mascara_do_diario_falhou erro={type(erro).__name__} caracteres={len(texto)}"


def _mascarar_o_renderizado(_logger: Any, _metodo: str, renderizado: Any) -> Any:
    """O último processador da cadeia: o texto já renderizado, pelo dono."""
    if isinstance(renderizado, str):
        return mascarar_a_linha(renderizado)
    return renderizado


class MascaraDoDiario(logging.Filter):
    """A linha de biblioteca (a que sai pelo ``logging``) pelo mesmo dono."""

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            texto = record.getMessage()
        except Exception as erro:
            texto = f"mensagem_ilegivel erro={type(erro).__name__}"
        record.msg, record.args = mascarar_a_linha(texto), None
        if record.exc_info and not record.exc_text:
            try:
                record.exc_text = logging.Formatter().formatException(record.exc_info)
            except Exception as erro:
                record.exc_text = f"traceback_ilegivel erro={type(erro).__name__}"
        if record.exc_text:
            record.exc_text = mascarar_a_linha(record.exc_text)
        if record.stack_info:
            record.stack_info = mascarar_a_linha(record.stack_info)
        return True


def _escrever_no_stderr(texto: str) -> None:
    """O texto no stderr de agora, já pelo dono; sem stderr aberto, não há onde escrever.

    Se a escrita num stderr aberto falhar, o erro sobe ao interpretador, que é o
    dono da falha de um gancho, e ele tenta o mesmo stderr: nada sai cru por outra porta.
    """
    saida = sys.stderr
    if saida is None or getattr(saida, "closed", False):
        return
    saida.write(mascarar_a_linha(texto))
    saida.flush()


def _o_fio_que_cai(argumentos: threading.ExceptHookArgs) -> None:
    """O `Exception in thread <nome>:` do gancho padrão, com o nome e o traceback pelo dono."""
    if argumentos.exc_type is SystemExit:
        return
    fio = argumentos.thread
    nome = fio.name if fio is not None else str(threading.get_ident())
    corpo = "".join(
        traceback.format_exception(
            argumentos.exc_type, argumentos.exc_value, argumentos.exc_traceback
        )
    )
    _escrever_no_stderr(f"Exception in thread {nome}:\n{corpo}")


def _o_processo_que_cai(tipo: type[BaseException], valor: BaseException, rastro: Any) -> None:
    """O traceback que o interpretador escreve ao morrer, pelo dono."""
    _escrever_no_stderr("".join(traceback.format_exception(tipo, valor, rastro)))


def instalar_os_ganchos_do_fio_que_cai() -> None:
    """O fio e o processo que caem escrevem pelo dono: o nome do fio e o traceback saem crus
    pelo stderr, por fora do ``logging``, e o filtro do diário não os vê."""
    threading.excepthook = _o_fio_que_cai
    sys.excepthook = _o_processo_que_cai


#: Os eventos que se repetem em rajada, e os campos que separam uma rajada da outra.
#: Contados no syslog de 18/10 a 21/10/2026 (34.837 linhas do daemon): `gatilho_armado`
#: chegou a 186 por minuto, `ipc_lento` a 79, `som_rotulo_velho_espera_o_silencio` a 21
#: e `haptics_select_borda` a 19. A primeira de cada janela sai inteira; as outras viram
#: UMA linha no fim da janela, com `vezes=` e os campos da última.
EVENTOS_AGREGADOS: dict[str, tuple[str, ...]] = {
    "gatilho_armado": ("nome",),
    "ipc_lento": ("metodo",),  # (noqa-acento) chave do diário
    "som_rotulo_velho_espera_o_silencio": ("uniq",),
    "haptics_select_borda": ("uniq",),
    # A borda de cada peça do som e da háptica que vai e volta: a rajada de um controle.
    "haptica_fina_saiu": ("controle",),
    "haptica_fina_de_pe": ("controle",),
    "haptica_portao_fechado": ("uniq",),
    "som_radio_sem_ponte": ("uniq",),
    "som_radio_ponte_saiu": ("uniq",),
    "som_ponte_ganha_a_haptica": (),
    "som_ponte_solta_a_haptica": (),
    "backend_hotplug_reconcile": ("trigger",),
    # O ambiente do jogo reescrito e o aviso fixo do dispositivo ausente.
    "launch_env_materializado": (),
    "launch_env_rematerializado_no_sossego": (),
    "launch_env_ignore_omitido_sem_cobertura": (),
    "usb_ausente_neste_boot": (),
}
JANELA_DO_AGREGADO_S = 60.0
#: A janela de um evento que não para dobra a cada volta, até aqui: um laço que repete
#: uma vez por minuto custa duas linhas por quarto de hora, não mil e quatrocentas por dia.
JANELA_MAXIMA_DO_AGREGADO_S = 900.0
_MARCA_DO_AGREGADO = "_agregado"

#: O que o daemon só confirma: a escrita de rotina que deu certo, o estado de novo dito
#: e o inventário da subida. Desce ao debug (22/10/2026, D-2210-O-DIARIO-CABE-EM-MIL-LINHAS):
#: no syslog de 18/10 a 21/10 eram 34.837 linhas do daemon, 76 subidas. O aviso e o erro
#: do mesmo nome seguem escritos, e `HEFESTO_DUALSENSE4UNIX_LOG_LEVEL=DEBUG` devolve tudo.
#: NUNCA entra aqui evento que outro código, um documento de protocolo ou uma bancada lê no
#: diário (régua: só o emissor conhece o nome): `uhid_motion_streaming` é a prova do degrau 2
#: do giro pelo rádio, e `game_trigger_provou` é o que a bancada do gatilho conta.
EVENTOS_DE_ESTADO_NORMAL: frozenset[str] = frozenset({
    # a janela em foco, dita a cada troca
    "autoswitch_fica_no_ultimo_jogo", "autoswitch_janela_propria_ignorada",
    "autoswitch_window_info_unavailable", "x11_focus_gate_no_x_focus",
    # a escrita de rotina que deu certo
    "speaker_volume_set", "microphone_volume_set", "microphone_led_set", "microphone_mute_set",
    "profile_speaker_applied", "profile_mic_volume_applied", "profile_mic_mute_applied",
    "profile_speaker_rota_sem_botao", "luz_do_mic_escrita", "luz_do_mic_peca_ligada",
    "gatilho_da_cor_por_numeracao", "gatilho_registrado", "gatilho_disparou",
    "speaker_reaplicado_no_connect", "mic_reaplicado_no_connect", "volume_padrao_na_adocao",
    "som_do_sistema_mudou",
    # a conta de cada jogo e a ponte do rádio
    "game_session_devolvida", "mascara_do_perfil_convergiu",
    "haptica_do_cabo_portao", "som_gravador_alvo_nao_conferido",
    "som_radio_gravador_colhido", "haptica_radio_gravador_colhido", "som_radio_fonte_secou",
    "som_ponte_ociosa_descida", "som_sink_publicado", "som_sink_removido", "som_no_derrubado",
    "bt_mic_source_publicada", "bt_mic_source_removida",
    # o encanamento do broker do hidraw
    "hidraw_broker_fd_recebido", "hidraw_broker_lease_open", "hidraw_broker_exposto",
    "hidraw_broker_desexposto", "hidraw_broker_restored",
    # o inventário de cada controle que liga
    "sensor_hub_reader_iniciado", "evdev_started", "motion_sensors_started",
    "touchpad_reader_started", "touchpad_reader_dono_do_cursor", "motion_reader_spawned",
    "firmware_do_controle_lido", "plastico_do_controle_lido", "lampadas_liberadas",
    "input_settling_started", "sysfs_led_cobertura", "primario_deposto_reservado",
    # a subida e a descida do daemon: ficam `daemon_main`, `daemon_starting`,
    # `ipc_server_listening` e `servico_pronto_avisado`; o resto do inventário é debug
    "hotkey_manager_started", "single_instance_adquirido", "game_signal_wired",
    "gamepad_multiplos_controles_adiado", "dsu_servidor_iniciado", "udp_server_listening",
    "mic_da_mesa_iniciado", "mic_do_jogo_iniciado", "mic_hotkey_iniciado", "luz_do_mic_iniciado",
    "tato_vivo_iniciado", "luz_animada_iniciada", "ouvinte_do_som_iniciado",
    "bt_mic_subsystem_iniciado", "governador_do_radio_iniciado", "som_subsystem_iniciado",
    "conexoes_subsystem_iniciado", "bluez_dono_vivo", "central_do_radio_ligada",
    "ouvido_do_usb_iniciado", "identity_fila_restaurada", "identity_registry_wired",
    "external_registry_wired", "feature_opener_wired", "abridor_do_handle_wired", "usb_ouvindo",
    "ouvinte_do_som_ligado", "cosmic_toplevel_ligado", "identity_slots_restaurados_de_outro_boot",
    "janela_lida_pelo_wayland_nativo", "daemon_shutting_down", "bt_mic_subsystem_parado",
    "som_subsystem_parado", "conexoes_subsystem_parado", "dsu_servidor_parado",
    "usb_parou_de_ouvir",
})
#: O nível mínimo que o diário escreve agora; o `configure_logging` o grava.
_nivel_minimo = logging.INFO


def desce_o_estado_normal(
    _logger: Any, nivel: str, evento: MutableMapping[str, Any]
) -> MutableMapping[str, Any]:
    """O primeiro processador da cadeia: o `info` de estado normal só vale no DEBUG."""
    if nivel == "info" and _nivel_minimo > logging.DEBUG:
        nome = evento.get("event")
        if isinstance(nome, str) and nome in EVENTOS_DE_ESTADO_NORMAL:
            raise structlog.DropEvent
    return evento


class _Janela:
    __slots__ = ("contagem", "inicio", "largura", "nivel", "recente")

    def __init__(self, inicio: float, largura: float) -> None:
        self.inicio = inicio
        self.largura = largura
        self.contagem = 0
        self.nivel = "info"
        self.recente: dict[str, Any] = {}


class AgregadoDoDiario:
    """O processador que junta a rajada de um evento repetido numa linha por janela.

    A primeira ocorrência de cada (evento, campos da chave) sai na hora. As seguintes,
    dentro da janela, não escrevem: contam. No fim sai uma linha com ``vezes=<as
    contadas>``, ``janela_s=`` e os campos da última; a ocorrência que chega com a janela
    vencida e a conta ainda aberta é ela mesma essa linha. A janela começa em ``janela_s``
    e dobra enquanto o evento volta antes de duas janelas, até ``janela_max_s``. O que
    ficou contado quando o processo sai se escreve no ``atexit``.
    """

    def __init__(
        self,
        eventos: dict[str, tuple[str, ...]] | None = None,
        janela_s: float = JANELA_DO_AGREGADO_S,
        relogio: Callable[[], float] = time.monotonic,
        janela_max_s: float = JANELA_MAXIMA_DO_AGREGADO_S,
    ) -> None:
        self.eventos = EVENTOS_AGREGADOS if eventos is None else eventos
        self.janela_s = janela_s
        self.janela_max_s = max(janela_s, janela_max_s)
        self.relogio = relogio
        #: quem escreve a linha do fim da janela; None = o logger do produto.
        self.diario: Any = None
        self._trava = threading.Lock()
        self._janelas: dict[tuple[Any, ...], _Janela] = {}
        #: por chave, quando a ocorrência veio por último e a largura da janela de então.
        self._ultimas: dict[tuple[Any, ...], tuple[float, float]] = {}

    def _largura_da_nova(self, chave: tuple[Any, ...], agora: float) -> float:
        """A janela que abre agora: dobra se o evento voltou antes de duas janelas."""
        if len(self._ultimas) > 512:
            corte = agora - 2 * self.janela_max_s
            self._ultimas = {k: v for k, v in self._ultimas.items() if v[0] >= corte}
        ultima = self._ultimas.get(chave)
        if ultima is None or agora - ultima[0] >= 2 * ultima[1]:
            return self.janela_s
        return min(ultima[1] * 2, self.janela_max_s)

    def __call__(
        self, _logger: Any, nivel: str, evento: MutableMapping[str, Any]
    ) -> MutableMapping[str, Any]:
        if evento.pop(_MARCA_DO_AGREGADO, False):
            return evento
        nome = evento.get("event")
        campos = self.eventos.get(nome) if isinstance(nome, str) else None
        if campos is None:
            return evento
        chave = (nome, *(repr(evento.get(c)) for c in campos))
        with self._trava:
            agora = self.relogio()
            janela = self._janelas.get(chave)
            if janela is not None and agora - janela.inicio < janela.largura:
                janela.contagem += 1
                janela.nivel = nivel
                janela.recente = dict(evento)
                self._ultimas[chave] = (agora, janela.largura)
                if janela.contagem == 1:
                    self._agendar(chave, janela, janela.largura - (agora - janela.inicio))
                raise structlog.DropEvent
            largura = self._largura_da_nova(chave, agora)
            self._janelas[chave] = _Janela(agora, largura)
            self._ultimas[chave] = (agora, largura)
            if janela is not None and janela.contagem:
                evento["vezes"] = janela.contagem + 1
                evento["janela_s"] = janela.largura
        return evento

    def _agendar(self, chave: tuple[Any, ...], janela: _Janela, segundos: float) -> None:
        fio = threading.Timer(max(segundos, 0.0), self._fechar, args=(chave, janela))
        fio.daemon = True
        fio.name = "agregado-do-diario"
        fio.start()

    def _fechar(self, chave: tuple[Any, ...], janela: _Janela) -> None:
        with self._trava:
            if self._janelas.get(chave) is not janela or not janela.contagem:
                return
            del self._janelas[chave]
        self._escrever(janela)

    def fechar_tudo(self) -> None:
        """Escreve agora toda conta aberta (o ``atexit`` do processo)."""
        with self._trava:
            abertas = [j for j in self._janelas.values() if j.contagem]
            self._janelas.clear()
        for janela in abertas:
            self._escrever(janela)

    def _escrever(self, janela: _Janela) -> None:
        campos = {k: v for k, v in janela.recente.items() if k not in ("event", "log_level")}
        campos.update(vezes=janela.contagem, janela_s=janela.largura)
        campos[_MARCA_DO_AGREGADO] = True
        diario = self.diario if self.diario is not None else structlog.get_logger("agregado")
        getattr(diario, janela.nivel)(janela.recente.get("event"), **campos)


_AGREGADO = AgregadoDoDiario()
atexit.register(_AGREGADO.fechar_tudo)


def cadeia_do_diario(fmt: str = "console", stream: Any = None) -> list[Processor]:
    """Os processadores do structlog do produto, na ordem, com o dono no fim."""
    shared_processors: list[Processor] = [
        desce_o_estado_normal,
        _AGREGADO,
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.TimeStamper(fmt="iso", utc=False),
    ]

    if fmt == "json":
        renderer: Processor = structlog.processors.JSONRenderer()
    else:
        colors = stream.isatty() if hasattr(stream, "isatty") else False
        # O traceback puro (D-1310-O-DIARIO-ESCREVE-O-TRACEBACK-SEM-OS-LOCAIS): o padrão
        # com o rich desenha os locais de cada quadro, e o laço do daemon parava por ele.
        renderer = structlog.dev.ConsoleRenderer(
            colors=colors, exception_formatter=structlog.dev.plain_traceback
        )

    return [*shared_processors, renderer, _mascarar_o_renderizado]


def configure_logging(
    *,
    level: str | None = None,
    fmt: str | None = None,
    stream: Any = None,
) -> None:
    """Configura logging stdlib + structlog. Idempotente."""
    global _configured
    if _configured:
        return

    level_name = (level or os.getenv("HEFESTO_DUALSENSE4UNIX_LOG_LEVEL") or "INFO").upper()
    log_fmt = (fmt or os.getenv("HEFESTO_DUALSENSE4UNIX_LOG_FORMAT") or "console").lower()
    stream = stream or sys.stderr

    global _nivel_minimo
    log_level = getattr(logging, level_name, logging.INFO)
    _nivel_minimo = log_level
    raiz = logging.getLogger()
    antes = list(raiz.handlers)
    logging.basicConfig(
        format="%(message)s",
        stream=stream,
        level=log_level,
    )
    for manipulador in raiz.handlers:
        if manipulador not in antes:
            manipulador.addFilter(MascaraDoDiario())
    if any(manipulador not in antes for manipulador in raiz.handlers):
        # A mesma guarda do filtro: só quando o manipulador é do produto. Sob o pytest ou
        # dentro de outro programa o raiz já tinha manipulador, e o gancho global não é nosso.
        instalar_os_ganchos_do_fio_que_cai()

    structlog.configure(
        processors=cadeia_do_diario(log_fmt, stream),
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(file=stream),
        cache_logger_on_first_use=True,
    )

    _configured = True


def get_logger(name: str | None = None) -> Any:
    """Retorna um logger structlog. Configura automaticamente se preciso."""
    if not _configured:
        configure_logging()
    return structlog.get_logger(name)


def reset_for_tests() -> None:
    """Reseta o estado interno — uso exclusivo em testes."""
    global _configured, _nivel_minimo
    _configured = False
    _nivel_minimo = logging.INFO
    structlog.reset_defaults()


__all__ = [
    "EVENTOS_AGREGADOS",
    "EVENTOS_DE_ESTADO_NORMAL",
    "AgregadoDoDiario",
    "MascaraDoDiario",
    "cadeia_do_diario",
    "configure_logging",
    "desce_o_estado_normal",
    "get_logger",
    "instalar_os_ganchos_do_fio_que_cai",
    "mascarar_a_linha",
    "reset_for_tests",
]
