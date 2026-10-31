"""O recibo dos efeitos: o que o daemon confirma que está no fio de cada controle.

O gatilho: o bloco que o handle monta agora contra o último report que o fio aceitou inteiro
(`_no_fio`). A luz: a cor que o daemon resolve para o controle (`resolved_led_for`) contra a que
saiu pela rota que alcança aquele transporte: os bytes da barra no report quando ele a leva, ou
`_cor_no_fio` (o nó do kernel no cabo, o `0x31` da barra no rádio). Cada campo vira
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


def _cor_que_saiu(handle: Any, fio: Any, inicio: int | None) -> tuple[int, int, int] | None:
    """A cor da barra que chegou ao controle: a do report, quando ele leva a barra; senão a da rota
    de fora (`_cor_no_fio`)."""
    if getattr(handle, "_suppress_leds", False):
        return _rgb(getattr(handle, "_cor_no_fio", None))
    if inicio is None:
        return None
    return _rgb(list(fio[inicio + _BYTES_DA_BARRA.start:inicio + _BYTES_DA_BARRA.stop]))


def _todos(porque: str) -> dict[str, dict[str, Any]]:
    campos: dict[str, dict[str, Any]] = {c: {"chegou": False, "porque": porque} for c in CAMPOS}
    campos["luz"]["anima"] = False
    return campos


def recibo_do_handle(
    handle: Any,
    *,
    mudo: bool = False,
    desejada: tuple[int, int, int] | None = None,
    anima: bool = False,
) -> dict[str, dict[str, Any]]:
    """O recibo de um handle: o que ele quer contra o que o controle aceitou.

    ``desejada`` é a cor que o daemon resolve para este controle. Com ``anima``, o quadro muda a
    cada 33 ms sem passar pela cor resolvida: basta a barra acesa no fio.
    """
    if handle is None or not getattr(handle, "connected", False):
        return _todos(FORA_DO_FIO)
    if mudo or getattr(handle, "_output_muted", False):
        return _todos(JOGO)
    fio: Any = getattr(handle, "_no_fio", None)
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
    saiu = _cor_que_saiu(handle, fio, inicio)
    luz = saiu is not None and saiu == desejada
    if anima and not luz:
        luz = saiu is not None and saiu != (0, 0, 0)
    recibo["luz"] = {"chegou": luz, "porque": None if luz else A_CAMINHO, "anima": anima}
    return recibo


def recibo_do_controle(daemon: Any, controller: Any, uniq: str | None) -> dict[str, dict[str, Any]]:
    """O recibo de `uniq` no `state_full`; sem `uniq` ou sem backend, tudo fica fora do fio."""
    if not uniq:
        return _todos(FORA_DO_FIO)
    tocando: Any = getattr(getattr(daemon, "_luz_animada", None), "tocando", frozenset())
    anima = isinstance(tocando, frozenset | set) and uniq in tocando
    procurar = getattr(controller, "_key_for_uniq", None)
    handles = getattr(controller, "_handles", None)
    if not callable(procurar) or not isinstance(handles, dict):
        return _todos(FORA_DO_FIO)
    resolver = getattr(controller, "resolved_led_for", None)
    trava = getattr(controller, "_io_lock", None) or contextlib.nullcontext()
    with trava:
        chave = procurar(uniq)
        handle = handles.get(chave) if chave is not None else None
        desejada = _rgb(resolver(uniq)) if callable(resolver) and handle is not None else None
        mudo = bool(getattr(controller, "_output_mute", False))
        return recibo_do_handle(handle, mudo=mudo, desejada=desejada, anima=anima)
