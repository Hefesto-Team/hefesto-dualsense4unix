"""A voz de cada controle passa pelo filtro do PipeWire antes de chegar aos jogos.

Um processo ``pipewire -c <conf>`` por controle carrega o
``libpipewire-module-echo-cancel`` com o WebRTC (supressão de ruído e
cancelamento de eco), lê o canal cru ``hefesto_mic_<marca>`` e publica a voz
``hefesto_mic_voz_<marca>``. A referência do eco é o monitor da saída padrão
(``monitor.mode``): nenhuma saída nova aparece na lista do sistema. O processo
morre com o dono e leva os nós junto.
"""

from __future__ import annotations

import atexit
import contextlib
import json
import os
import shutil
import subprocess
import tempfile
import threading
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from hefesto_dualsense4unix.integrations import audio_control
from hefesto_dualsense4unix.integrations.dualsense_bt_audio import (
    PRIORIDADE_SESSAO_DA_PONTE,
)
from hefesto_dualsense4unix.integrations.filho_de_som import morrer_com_o_pai
from hefesto_dualsense4unix.integrations.fontes_de_captura import (
    PREFIXO_SOURCE_VOZ_FILTRADA,
    sufixo_do_canal_do_mic,
)
from hefesto_dualsense4unix.utils.logging_config import get_logger

logger = get_logger(__name__)

__all__ = [
    "AJUSTES_DO_FILTRO",
    "BIBLIOTECA_DO_FILTRO",
    "PAPEL_DO_FILTRO",
    "PRIORIDADE_DA_VOZ",
    "abrir",
    "conf_do_filtro",
    "de_pe",
    "descricao_da_voz",
    "fechar",
    "fechar_todos",
    "nome_da_voz",
    "voz_de",
    "voz_no_ar",
]

BIBLIOTECA_DO_FILTRO = "aec/libspa-aec-webrtc"

AJUSTES_DO_FILTRO: tuple[tuple[str, str], ...] = (
    ("webrtc.noise_suppression", "true"),
    ("webrtc.high_pass_filter", "true"),
    ("webrtc.extended_filter", "true"),
    ("webrtc.delay_agnostic", "true"),
    ("webrtc.gain_control", "false"),
)

PRIORIDADE_DA_VOZ = PRIORIDADE_SESSAO_DA_PONTE + 1

PAPEL_DO_FILTRO = "voz-filtrada"

SUFIXO_DA_DESCRICAO = " (voz limpa)"

_ESPERA_PELO_FIM_S = 2.0


def nome_da_voz(canal: str) -> str:
    """``hefesto_mic_voz_<marca>`` do canal cru ``hefesto_mic_<marca>`` — "" sem marca."""
    marca = sufixo_do_canal_do_mic(canal)
    return f"{PREFIXO_SOURCE_VOZ_FILTRADA}{marca}" if marca else ""


def descricao_da_voz(descricao: str) -> str:
    """O rótulo que os aplicativos mostram para a voz filtrada."""
    base = descricao.strip() or "Microfone do Controle"
    return f"{base}{SUFIXO_DA_DESCRICAO}"


def conf_do_filtro(
    canal: str, descricao: str, *, prioridade: int = PRIORIDADE_DA_VOZ
) -> str:
    """O arquivo de configuração do processo do filtro. "" quando o canal não tem marca."""
    voz = nome_da_voz(canal)
    if not voz:
        return ""
    marca = sufixo_do_canal_do_mic(canal)
    q = json.dumps
    ajustes = " ".join(f"{chave} = {valor}" for chave, valor in AJUSTES_DO_FILTRO)
    papel = f"hefesto.papel = {q(PAPEL_DO_FILTRO)}"
    entrada = (
        f"node.name = {q('hefesto-voz-entrada-' + marca)} target.object = {q(canal)} "
        f"node.passive = true node.dont-reconnect = true {papel}"
    )
    saida = (
        f"node.name = {q(voz)} node.description = {q(descricao_da_voz(descricao))} "
        f"media.class = Audio/Source priority.session = {int(prioridade)}"
    )
    referencia = (
        f"node.name = {q('hefesto-voz-referencia-' + marca)} node.passive = true {papel}"
    )
    return "\n".join([
        "context.properties = { log.level = 0 }",
        "context.spa-libs = {",
        "    audio.convert.* = audioconvert/libspa-audioconvert",
        "    support.* = support/libspa-support",
        "}",
        "context.modules = [",
        "    { name = libpipewire-module-rt args = { } flags = [ ifexists nofail ] }",
        "    { name = libpipewire-module-protocol-native }",
        "    { name = libpipewire-module-client-node }",
        "    { name = libpipewire-module-adapter }",
        "    { name = libpipewire-module-echo-cancel",
        "        args = {",
        f"            library.name = {BIBLIOTECA_DO_FILTRO}",
        "            monitor.mode = true",
        "            audio.channels = 1",
        "            audio.position = [ MONO ]",
        f"            aec.args = {{ {ajustes} }}",
        f"            capture.props = {{ {entrada} }}",
        f"            source.props = {{ {saida} }}",
        f"            sink.props = {{ {referencia} }}",
        "        }",
        "    }",
        "]",
        "",
    ])


@dataclass
class _Filtro:
    canal: str
    voz: str
    descricao: str
    conf: str
    proc: Any
    visto: bool = False

    def vivo(self) -> bool:
        try:
            return self.proc.poll() is None
        except Exception:
            return False


_DE_PE: dict[str, _Filtro] = {}
_TRANCA = threading.Lock()


def _lancar_processo(argv: list[str]) -> Any:
    """O ``Popen`` de verdade: sem cano, e preso ao pai."""
    return subprocess.Popen(
        argv,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        preexec_fn=morrer_com_o_pai,
    )


def _pasta_dos_confs() -> str:
    return os.environ.get("XDG_RUNTIME_DIR") or tempfile.gettempdir()


def _escrever_o_conf(texto: str) -> str:
    fd, caminho = tempfile.mkstemp(prefix="hefesto-voz-", suffix=".conf", dir=_pasta_dos_confs())
    with os.fdopen(fd, "w", encoding="utf-8") as arquivo:
        arquivo.write(texto)
    return caminho


def _derrubar(filtro: _Filtro) -> None:
    proc = filtro.proc
    if proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=_ESPERA_PELO_FIM_S)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
    with contextlib.suppress(OSError):
        os.unlink(filtro.conf)


def abrir(
    uniq: str,
    canal: str,
    descricao: str,
    *,
    lancar: Callable[[list[str]], Any] | None = None,
) -> str:
    """Sobe o filtro deste controle sobre ``canal``. Devolve o nome da voz, "" se não subiu.

    A voz que subiu é avisada ao dono do volume (:func:`audio_control.avisar_no_de_pe`): o nó
    novo nasce no volume de nascença e o do controle volta a ele quando ele aparece no grafo.
    """
    voz = nome_da_voz(canal)
    if not uniq or not voz:
        return ""
    with _TRANCA:
        ja = _DE_PE.get(uniq)
        if ja is not None and ja.vivo() and ja.canal == canal and ja.descricao == descricao:
            return voz
    fechar(uniq)
    if lancar is None and shutil.which("pipewire") is None:
        logger.info("microfone_filtrado_sem_pipewire", voz=voz)
        return ""
    try:
        caminho = _escrever_o_conf(conf_do_filtro(canal, descricao))
    except OSError:
        logger.warning("microfone_filtrado_sem_conf", exc_info=True)
        return ""
    try:
        proc = (lancar or _lancar_processo)(["pipewire", "-c", caminho])
    except (OSError, ValueError, subprocess.SubprocessError):
        logger.warning("microfone_filtrado_nao_lancou", exc_info=True)
        with contextlib.suppress(OSError):
            os.unlink(caminho)
        return ""
    with _TRANCA:
        _DE_PE[uniq] = _Filtro(canal, voz, descricao, caminho, proc)
    logger.info("microfone_filtrado_de_pe", voz=voz)
    audio_control.avisar_no_de_pe(uniq, voz)
    return voz


def fechar(uniq: str) -> bool:
    """Derruba o filtro deste controle. ``False`` = não havia."""
    with _TRANCA:
        filtro = _DE_PE.pop(uniq, None)
    if filtro is None:
        return False
    _derrubar(filtro)
    logger.info("microfone_filtrado_fechado", voz=filtro.voz)
    return True


def voz_de(uniq: str) -> str:
    """O nome da voz filtrada deste controle com o processo vivo AGORA — "" sem filtro."""
    with _TRANCA:
        filtro = _DE_PE.get(uniq)
    return filtro.voz if filtro is not None and filtro.vivo() else ""


def voz_no_ar(uniq: str, no_ar_no_servidor: Callable[[str], bool | None]) -> bool | None:
    """O filtro deste controle está de pé NO SERVIDOR: o processo vive e a voz está na lista.

    ``no_ar_no_servidor`` pergunta ao servidor por um nome (``True``, ``False``, ou ``None`` se ele
    não respondeu). ``False``: o processo morreu, ou a voz que já esteve listada sumiu (o servidor
    reiniciou). ``None``: não há filtro, o servidor não respondeu, ou a voz ainda não apareceu.
    """
    with _TRANCA:
        filtro = _DE_PE.get(uniq)
    if filtro is None:
        return None
    if not filtro.vivo():
        return False
    na_lista = no_ar_no_servidor(filtro.voz)
    if na_lista is None:
        return None
    if na_lista:
        filtro.visto = True
        return True
    return False if filtro.visto else None


def de_pe() -> dict[str, str]:
    """``{uniq: voz}`` dos filtros com processo vivo. Cópia."""
    with _TRANCA:
        filtros = dict(_DE_PE)
    return {uniq: f.voz for uniq, f in filtros.items() if f.vivo()}


def fechar_todos() -> int:
    """Derruba todos os filtros e devolve quantos eram."""
    return sum(1 for uniq in list(_DE_PE) if fechar(uniq))


atexit.register(fechar_todos)
