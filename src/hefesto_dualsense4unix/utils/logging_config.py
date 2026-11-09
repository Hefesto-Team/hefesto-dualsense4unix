"""Configuração de logging do daemon com structlog."""
from __future__ import annotations

import atexit
import contextlib
import datetime
import errno
import logging
import os
import re
import sys
import threading
import time
import traceback
import weakref
from collections import deque
from collections.abc import Callable, MutableMapping
from pathlib import Path
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
_o_padrao_do_reset = False
_ENTREGUES: weakref.WeakSet[Any] = globals().get("_ENTREGUES") or weakref.WeakSet()

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
        mascarado = mascarar_a_linha(renderizado)
        _REGISTRO.por(mascarado)
        return mascarado
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
    mascarado = mascarar_a_linha(texto)
    _REGISTRO.por(mascarado)
    saida = sys.stderr
    if saida is None or getattr(saida, "closed", False):
        return
    saida.write(mascarado)
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


EVENTOS_AGREGADOS: dict[str, tuple[str, ...]] = {
    "gatilho_armado": ("nome",),
    "ipc_lento": ("metodo",),  # (noqa-acento)
    "som_rotulo_velho_espera_o_silencio": ("uniq",),
    "haptics_select_borda": ("uniq",),
    "haptica_fina_saiu": ("controle",),
    "haptica_fina_de_pe": ("controle",),
    "som_radio_sem_ponte": ("uniq",),
    "som_radio_ponte_saiu": ("uniq",),
    "som_ponte_ganha_a_haptica": (),
    "som_ponte_solta_a_haptica": (),
    "backend_hotplug_reconcile": ("trigger",),
    "launch_env_materializado": (),
    "launch_env_rematerializado_no_sossego": (),
    "launch_env_ignore_omitido_sem_cobertura": (),
    "usb_ausente_neste_boot": (),
    "evdev_ressincronizado": ("path", "mudou"),
    "touchpad_ressincronizado": ("path",),
}
JANELA_DO_AGREGADO_S = 60.0
JANELA_MAXIMA_DO_AGREGADO_S = 900.0
_MARCA_DO_AGREGADO = "_agregado"

EVENTOS_DE_ESTADO_NORMAL: frozenset[str] = frozenset({
    "autoswitch_fica_no_ultimo_jogo", "autoswitch_janela_propria_ignorada",
    "autoswitch_window_info_unavailable", "x11_focus_gate_no_x_focus",
    "speaker_volume_set", "microphone_volume_set", "microphone_led_set", "microphone_mute_set",
    "profile_speaker_applied", "profile_mic_volume_applied", "profile_mic_mute_applied",
    "profile_speaker_rota_sem_botao", "luz_do_mic_escrita", "luz_do_mic_peca_ligada",
    "gatilho_da_cor_por_numeracao", "gatilho_registrado", "gatilho_disparou",
    "speaker_reaplicado_no_connect", "mic_reaplicado_no_connect", "volume_padrao_na_adocao",
    "som_do_sistema_mudou",
    "game_session_devolvida", "mascara_do_perfil_convergiu",
    "som_gravador_alvo_nao_conferido",
    "som_radio_gravador_colhido", "haptica_radio_gravador_colhido", "som_radio_fonte_secou",
    "som_ponte_ociosa_descida", "som_sink_publicado", "som_sink_removido", "som_no_derrubado",
    "bt_mic_source_publicada", "bt_mic_source_removida",
    "hidraw_broker_fd_recebido", "hidraw_broker_lease_open", "hidraw_broker_exposto",
    "hidraw_broker_desexposto", "hidraw_broker_restored",
    "sensor_hub_reader_iniciado", "evdev_started", "motion_sensors_started",
    "touchpad_reader_started", "touchpad_reader_dono_do_cursor", "motion_reader_spawned",
    "firmware_do_controle_lido", "plastico_do_controle_lido", "lampadas_liberadas",
    "input_settling_started", "sysfs_led_cobertura", "primario_deposto_reservado",
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
    vencida e a conta ainda aberta é essa mesma linha. A janela começa em ``janela_s``
    e dobra enquanto o evento volta antes de duas janelas, até ``janela_max_s``. O que
    ficou contado quando o processo sai se escreve no ``atexit``, e se perde calado
    quando o destino do diário já fechou.
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
        self.diario: Any = None
        self._trava = threading.Lock()
        self._janelas: dict[tuple[Any, ...], _Janela] = {}
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
        try:
            getattr(diario, janela.nivel)(janela.recente.get("event"), **campos)
        except (ValueError, OSError) as erro:
            if not _o_destino_fechou(erro):
                raise


def _o_destino_fechou(erro: BaseException) -> bool:
    """O erro de escrever num arquivo fechado ou num cano sem leitor, e só ele."""
    if isinstance(erro, OSError):
        return erro.errno in (errno.EPIPE, errno.EBADF)
    return isinstance(erro, ValueError) and "closed file" in str(erro)


NOME_DO_REGISTRO = "servico.log"
TETO_DO_REGISTRO = 4 << 20
GERACOES_DO_REGISTRO = 2
TETO_DA_FILA_DO_REGISTRO = 1 << 18
ESPERA_DO_REGISTRO_NA_SAIDA_S = 2.0
_JA_TEM_HORA = re.compile(rb"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}")


def _a_hora() -> bytes:
    return datetime.datetime.now().isoformat(timespec="milliseconds").encode()


class RegistroDoServico:
    """O arquivo do serviço: ``por`` só enfileira, e o disco é de um fio próprio.

    Recebe a linha já pela máscara e sem depender do diário do sistema, que outro programa pode
    encher. Acima do teto da fila sai a linha mais velha, e o arquivo conta quantas saíram. O
    arquivo gira antes de passar de :data:`TETO_DO_REGISTRO`. Fechado, ``por`` não faz nada: é o
    caso de todo processo que não é o serviço.
    """

    def __init__(self) -> None:
        self._vez = threading.Condition()
        self._linhas: deque[bytes] = deque()
        self._na_fila = 0
        self._perdidas = 0
        self._no_disco = False
        self._parar = False
        self._caminho: Path | None = None
        self._fio: threading.Thread | None = None
        self._arquivo: int | None = None
        self._tamanho = 0

    @property
    def aberto(self) -> bool:
        return self._caminho is not None

    def abrir(self, caminho: Path) -> None:
        """Abre o arquivo e põe o fio de pé; o :class:`OSError` de abrir sobe a quem pediu."""
        caminho.parent.mkdir(parents=True, exist_ok=True)
        self._caminho = caminho
        try:
            self._arquivo = self._abrir_o_arquivo(caminho)
        except OSError:
            self._caminho = None
            raise
        self._parar = False
        self._fio = threading.Thread(target=self._rodar, name="registro-do-servico", daemon=True)
        self._fio.start()

    def _abrir_o_arquivo(self, caminho: Path) -> int:
        arquivo = os.open(caminho, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
        self._tamanho = os.fstat(arquivo).st_size
        return arquivo

    def por(self, texto: str) -> None:
        """Enfileira a linha, com a hora na frente quando vem sem hora. Nunca escreve."""
        if self._caminho is None:
            return
        linha = _COR_DO_TERMINAL.sub("", texto).encode("utf-8", "replace")
        if not _JA_TEM_HORA.match(linha):
            linha = _a_hora() + b" " + linha
        linha = linha[:TETO_DA_FILA_DO_REGISTRO - 1] + b"\n"
        with self._vez:
            self._linhas.append(linha)
            self._na_fila += len(linha)
            while self._na_fila > TETO_DA_FILA_DO_REGISTRO and len(self._linhas) > 1:
                self._na_fila -= len(self._linhas.popleft())
                self._perdidas += 1
            self._vez.notify_all()

    def _tirar_da_fila(self) -> bytes | None:
        with self._vez:
            self._no_disco = False
            self._vez.notify_all()
            while not self._linhas:
                if self._parar:
                    return None
                self._vez.wait()
            self._no_disco = True
            dados = b"".join(self._linhas)
            self._linhas.clear()
            self._na_fila = 0
        return dados

    def _girar(self, caminho: Path) -> None:
        if self._arquivo is not None:
            os.close(self._arquivo)
            self._arquivo = None
        for geracao in range(GERACOES_DO_REGISTRO, 0, -1):
            velho = caminho.with_name(f"{caminho.name}.{geracao - 1}") if geracao > 1 else caminho
            with contextlib.suppress(FileNotFoundError):
                os.replace(velho, caminho.with_name(f"{caminho.name}.{geracao}"))
        self._tamanho = 0

    def _gravar(self, dados: bytes) -> None:
        caminho = self._caminho
        if caminho is None:
            return
        if self._tamanho and self._tamanho + len(dados) > TETO_DO_REGISTRO:
            self._girar(caminho)
        if self._arquivo is None:
            self._arquivo = self._abrir_o_arquivo(caminho)
        resto = memoryview(dados)
        while resto:
            escrito = os.write(self._arquivo, resto)
            self._tamanho += escrito
            resto = resto[escrito:]

    def _gravar_contando(self, dados: bytes) -> None:
        """Grava com o aviso do que saiu antes. O que o disco recusa entra na conta do próximo."""
        with self._vez:
            perdidas = self._perdidas
        aviso = b""
        if perdidas:
            frase = "1 linha saiu" if perdidas == 1 else f"{perdidas} linhas saíram"
            aviso = _a_hora() + f" ({frase}: o disco não acompanhou)\n".encode()
        try:
            self._gravar(aviso + dados)
        except OSError:
            with self._vez:
                self._perdidas += dados.count(b"\n")
        else:
            with self._vez:
                self._perdidas -= perdidas

    def _rodar(self) -> None:
        while (dados := self._tirar_da_fila()) is not None:
            self._gravar_contando(dados)

    def escoar(self, prazo: float) -> bool:
        """Espera a fila chegar ao disco. Diz se chegou; o disco parado nunca segura a saída."""
        with self._vez:
            return self._vez.wait_for(
                lambda: self._caminho is None or (not self._linhas and not self._no_disco),
                timeout=prazo,
            )

    def fechar(self) -> None:
        """Escoa, para o fio e fecha o arquivo."""
        fio = self._fio
        if fio is None:
            return
        self.escoar(ESPERA_DO_REGISTRO_NA_SAIDA_S)
        with self._vez:
            self._parar = True
            self._caminho = None
            self._vez.notify_all()
        fio.join(ESPERA_DO_REGISTRO_NA_SAIDA_S)
        self._fio = None
        if self._arquivo is not None:
            with contextlib.suppress(OSError):
                os.close(self._arquivo)
            self._arquivo = None


class _ManipuladorDoRegistro(logging.Handler):
    """A linha de biblioteca no registro do serviço, pelo mesmo filtro do diário."""

    def __init__(self) -> None:
        super().__init__()
        self.setFormatter(logging.Formatter("%(message)s"))
        self.addFilter(MascaraDoDiario())

    def emit(self, record: logging.LogRecord) -> None:
        _REGISTRO.por(self.format(record))


_REGISTRO = RegistroDoServico()
atexit.register(_REGISTRO.escoar, ESPERA_DO_REGISTRO_NA_SAIDA_S)

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
    """Configura logging stdlib + structlog. Idempotente, salvo sobre o padrão do reset."""
    global _configured, _o_padrao_do_reset
    if _configured and not _o_padrao_do_reset:
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
        instalar_os_ganchos_do_fio_que_cai()

    _soltar_os_entregues()
    structlog.configure(
        processors=cadeia_do_diario(log_fmt, stream),
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(file=stream),
        cache_logger_on_first_use=True,
    )

    _configured = True
    _o_padrao_do_reset = False


def _soltar_os_entregues() -> None:
    """O logger entregue que guardou a montagem volta a montar no próximo uso.

    O guardado prende a lista de processadores, o nível e o destino da configuração de antes, e
    cada ``configure`` do structlog troca a lista por outra.
    """
    for logger in list(_ENTREGUES):
        vars(logger).pop("bind", None)


def caminho_do_registro() -> Path:
    from hefesto_dualsense4unix.utils.xdg_paths import state_dir

    return state_dir() / NOME_DO_REGISTRO


def geracoes_do_registro(atual: Path) -> list[Path]:
    """O arquivo de agora e os girados, do mais novo ao mais velho."""
    return [atual, *(atual.with_name(f"{atual.name}.{n}")
                     for n in range(1, GERACOES_DO_REGISTRO + 1))]


def guardar_o_registro_do_servico(caminho: Path | None = None) -> None:
    """Liga o registro próprio do serviço. Quem chama é o único escritor do arquivo."""
    if _REGISTRO.aberto:
        return
    try:
        _REGISTRO.abrir(caminho or caminho_do_registro())
    except OSError as erro:
        get_logger(__name__).warning("registro_do_servico_sem_arquivo", err=str(erro))
        return
    logging.getLogger().addHandler(_ManipuladorDoRegistro())


def get_logger(name: str | None = None) -> Any:
    """Retorna um logger structlog. Configura automaticamente se preciso."""
    if not _configured:
        configure_logging()
    logger = structlog.get_logger(name)
    _ENTREGUES.add(logger)
    return logger


def reset_for_tests() -> None:
    """Reseta o estado interno — uso exclusivo em testes.

    Devolve o estado de recém-importado: configurado no padrão, como o ``get_logger`` do import
    deixa. Sem isso, o primeiro ``get_logger`` depois do reset configura sozinho, e dentro de um
    ``capture_logs`` troca a lista que ele esvaziou. Um ``configure_logging`` depois do reset vale.
    """
    global _configured, _nivel_minimo, _o_padrao_do_reset
    _REGISTRO.fechar()
    raiz = logging.getLogger()
    for manipulador in list(raiz.handlers):
        if isinstance(manipulador, _ManipuladorDoRegistro):
            raiz.removeHandler(manipulador)
    _configured = False
    _nivel_minimo = logging.INFO
    structlog.reset_defaults()
    configure_logging()
    _o_padrao_do_reset = True


__all__ = [
    "EVENTOS_AGREGADOS",
    "EVENTOS_DE_ESTADO_NORMAL",
    "NOME_DO_REGISTRO",
    "AgregadoDoDiario",
    "MascaraDoDiario",
    "RegistroDoServico",
    "cadeia_do_diario",
    "caminho_do_registro",
    "configure_logging",
    "desce_o_estado_normal",
    "geracoes_do_registro",
    "get_logger",
    "guardar_o_registro_do_servico",
    "instalar_os_ganchos_do_fio_que_cai",
    "mascarar_a_linha",
    "reset_for_tests",
]
