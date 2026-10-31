"""O recibo dos efeitos: o que o daemon confirma que está no fio de cada controle.

Compara o handle de cada controle com o último report que a volta escreveu
(`_last_out_report`): o bloco de cada gatilho e a cor da barra. Cada campo vira
`{"chegou": bool, "porque": str | None}` (na luz, mais `"anima"`); `porque` é `fora_do_fio`,
`jogo` (o Modo Nativo cala a saída, ou o bloco cru do jogo) ou `a_caminho`. A háptica e os
motores só ganham os dois primeiros. Leitura de memória sob o `_io_lock`, sem tocar o aparelho.
"""
from __future__ import annotations

import contextlib
from typing import Any

from hefesto_dualsense4unix.core import ds_output_report as rep
from hefesto_dualsense4unix.core.trigger_effects import (
    TAMANHO_DO_BLOCO_DO_GATILHO,
    bloco_do_gatilho,
)

GATILHOS = (("gatilho_e", "left", 21), ("gatilho_d", "right", 10))
CAMPOS = ("gatilho_e", "gatilho_d", "luz", "haptica", "motores")
FORA_DO_FIO = "fora_do_fio"
JOGO = "jogo"
A_CAMINHO = "a_caminho"
_BYTES_DA_BARRA = slice(44, 47)


def _inicio_do_comum(report: Any) -> int | None:
    """Onde o bloco comum começa no report escrito: 1 no cabo (`0x02`), 3 no rádio (`0x31`)."""
    if not isinstance(report, list | bytes | bytearray) or not report:
        return None
    if report[0] == rep.USB_REPORT_ID and len(report) >= 1 + rep.COMMON_LEN:
        return 1
    if report[0] == rep.BT_REPORT_ID and len(report) >= 3 + rep.COMMON_LEN:
        return 3
    return None


def _bloco_cru(handle: Any, lado: str) -> bytes | None:
    cru = getattr(handle, f"_raw_trigger_{lado}", None)
    if isinstance(cru, bytes | bytearray) and len(cru) == TAMANHO_DO_BLOCO_DO_GATILHO:
        return bytes(cru)
    return None


def _bloco_do_handle(handle: Any, lado: str) -> bytes | None:
    """O bloco que a volta monta para este lado agora, com a escala da intensidade."""
    from hefesto_dualsense4unix.core.backend_pydualsense import _forca_do_gatilho

    gatilho = getattr(handle, "triggerL" if lado == "left" else "triggerR", None)
    modo = getattr(getattr(gatilho, "mode", None), "value", None)
    forcas = getattr(gatilho, "forces", None)
    if not isinstance(modo, int) or not isinstance(forcas, list | tuple) or len(forcas) < 7:
        return None
    return bytes(_forca_do_gatilho(handle, bloco_do_gatilho(modo, forcas)))


def _rgb(valor: Any) -> tuple[int, int, int] | None:
    """Três inteiros de cor, cada um num byte; outra forma não é cor."""
    if not isinstance(valor, list | tuple) or len(valor) != 3:
        return None
    if not all(isinstance(v, int) for v in valor):
        return None
    r, g, b = (v & 0xFF for v in valor)
    return (r, g, b)


def _cor_da_barra(handle: Any) -> tuple[int, int, int] | None:
    return _rgb(getattr(getattr(handle, "light", None), "TouchpadColor", None))


def _todos(porque: str) -> dict[str, dict[str, Any]]:
    campos: dict[str, dict[str, Any]] = {c: {"chegou": False, "porque": porque} for c in CAMPOS}
    campos["luz"]["anima"] = False
    return campos


def recibo_do_handle(
    handle: Any,
    *,
    mudo: bool = False,
    escrito_no_no: tuple[int, int, int] | None = None,
    anima: bool = False,
) -> dict[str, dict[str, Any]]:
    """O recibo de um handle: a comparação do estado dele com o último report no fio.

    ``escrito_no_no`` é a cor que o backend escreveu no nó de LED do kernel (no cabo a barra pode
    ir por ali, e o report leva os bytes da barra calados). Com ``anima``, o quadro muda a cada
    33 ms e a cor do handle pode estar um quadro à frente: basta a barra acesa no fio.
    """
    if handle is None or not getattr(handle, "connected", False):
        return _todos(FORA_DO_FIO)
    if mudo or getattr(handle, "_output_muted", False):
        return _todos(JOGO)
    fio = getattr(handle, "_last_out_report", None)
    inicio = _inicio_do_comum(fio)
    recibo: dict[str, dict[str, Any]] = {}
    for campo, lado, deslocamento in GATILHOS:
        if _bloco_cru(handle, lado) is not None:
            recibo[campo] = {"chegou": False, "porque": JOGO}
            continue
        esperado = _bloco_do_handle(handle, lado)
        chegou = False
        if inicio is not None and esperado is not None:
            comeco = inicio + deslocamento
            chegou = bytes(fio[comeco:comeco + len(esperado)]) == esperado
        recibo[campo] = {"chegou": chegou, "porque": None if chegou else A_CAMINHO}
    cor = _cor_da_barra(handle)
    na_barra = None
    if inicio is not None:
        trecho = fio[inicio + _BYTES_DA_BARRA.start:inicio + _BYTES_DA_BARRA.stop]
        na_barra = tuple(int(v) for v in trecho)
    luz = cor is not None and (na_barra == cor or escrito_no_no == cor)
    if anima and not luz:
        luz = na_barra is not None and na_barra != (0, 0, 0)
    recibo["luz"] = {"chegou": luz, "porque": None if luz else A_CAMINHO, "anima": anima}
    return recibo


def recibo_do_controle(daemon: Any, controller: Any, uniq: str | None) -> dict[str, dict[str, Any]]:
    """O recibo de `uniq` no `state_full`; sem `uniq` ou sem backend, tudo fica fora do fio."""
    if not uniq:
        return _todos(FORA_DO_FIO)
    tocando = getattr(getattr(daemon, "_luz_animada", None), "tocando", frozenset())
    anima = isinstance(tocando, frozenset | set) and uniq in tocando
    procurar = getattr(controller, "_key_for_uniq", None)
    handles = getattr(controller, "_handles", None)
    if not callable(procurar) or not isinstance(handles, dict):
        return _todos(FORA_DO_FIO)
    trava = getattr(controller, "_io_lock", None) or contextlib.nullcontext()
    with trava:
        chave = procurar(uniq)
        handle = handles.get(chave) if chave is not None else None
        escritos = getattr(controller, "_sysfs_written", None)
        no_no = escritos.get(chave) if isinstance(escritos, dict) and chave else None
        mudo = bool(getattr(controller, "_output_mute", False))
        return recibo_do_handle(handle, mudo=mudo, escrito_no_no=_rgb(no_no), anima=anima)
