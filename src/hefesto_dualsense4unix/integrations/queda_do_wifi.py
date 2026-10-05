"""queda_do_wifi.py — quantas vezes cada aparelho USB caiu do barramento NESTE boot.

O-WIFI-SE-LE-NAS-DUAS-BANDAS-01 (04/10/2026). O «cai do nada» do Wi-Fi USB é a placa sumindo do
barramento: o diário do kernel diz ``USB disconnect`` e, segundos depois, ``New USB device found``
com o MESMO ``idVendor:idProduct``. Este módulo só LÊ esse diário (``journalctl -k -b``, o mesmo
precedente de ``o_cabo_em_espera.ler_o_diario_do_kernel``) e conta.

* **A identidade é o ``vid:pid``**, nunca o nó (``4-1.2`` vira ``3-1.2`` quando a placa volta em
  outro barramento) nem o nome da interface.
* **Uma queda é o disconnect seguido da re-enumeração do mesmo ``vid:pid`` em até**
  :data:`REENUMERA_EM_S`. Quedas coladas (menos de :data:`DEBOUNCE_S`) valem uma. Sem a volta
  não é queda: é a placa tirada da porta.
* **Não distingue** a queda do replug de propósito (nem da troca de modo USB do sistema, que
  também re-enumera): o diário não diz. A tela diz «caiu», nunca a causa.
* A leitura é lenta (um processo): quem chama a faz em fundo. Sob a suíte nada roda.
"""

from __future__ import annotations

import os
import re
import subprocess
import time
from collections.abc import Callable
from dataclasses import dataclass

from hefesto_dualsense4unix.integrations import bluez_dbus
from hefesto_dualsense4unix.utils.logging_config import get_logger

logger = get_logger(__name__)

REENUMERA_EM_S = 10.0
DEBOUNCE_S = 5.0
ESPERA_DO_DIARIO_S = 4.0
#: A partir de quantas quedas a conexão «sofre» (abaixo disso só «aperta»).
QUEDAS_QUE_SOFREM = 3
#: ``≥`` isto, o tempo se diz em horas.
MINUTOS_EM_HORAS = 120

COMANDO = ["journalctl", "-k", "-b", "-o", "short-monotonic", "--no-pager"]

_TEMPO = re.compile(r"^\[\s*(?P<t>\d+(?:\.\d+)?)\]")
_NASCEU = re.compile(
    r"usb (?P<no>\d+-[\d.]+): New USB device found, "
    r"idVendor=(?P<vid>[0-9a-fA-F]{4}), idProduct=(?P<pid>[0-9a-fA-F]{4})"
)
_SUMIU = re.compile(r"usb (?P<no>\d+-[\d.]+): USB disconnect")


@dataclass(frozen=True)
class Quedas:
    """As quedas de um ``vid:pid``: quantas, e há quantos minutos foi a primeira."""

    n: int
    minutos: int


def quedas_do_diario(texto: str, agora_s: float) -> dict[str, Quedas]:
    """``{"usb:vid:pid": Quedas}`` do texto de ``journalctl -k -b -o short-monotonic``.

    ``agora_s`` é o relógio monotônico de agora (o do diário, em segundos desde o boot).
    """
    moradores: dict[str, str] = {}
    sumiu_em: dict[str, float] = {}
    quedas: dict[str, list[float]] = {}
    for linha in texto.splitlines():
        marca = _TEMPO.match(linha)
        if not marca:
            continue
        quando = float(marca.group("t"))
        achou = _NASCEU.search(linha)
        if achou:
            chave = f"usb:{achou.group('vid').lower()}:{achou.group('pid').lower()}"
            moradores[achou.group("no")] = chave
            partiu = sumiu_em.pop(chave, None)
            if partiu is not None and quando - partiu <= REENUMERA_EM_S:
                lista = quedas.setdefault(chave, [])
                if not lista or partiu - lista[-1] >= DEBOUNCE_S:
                    lista.append(partiu)
            continue
        foi = _SUMIU.search(linha)
        if foi:
            chave = moradores.pop(foi.group("no"), "")
            if chave:
                sumiu_em[chave] = quando
    return {
        chave: Quedas(n=len(lista), minutos=max(1, round((agora_s - lista[0]) / 60)))
        for chave, lista in quedas.items() if lista
    }


def ler_as_quedas(
    executor: Callable[[list[str]], str | None] | None = None,
    agora: Callable[[], float] = time.monotonic,
) -> dict[str, Quedas] | None:
    """As quedas deste boot por ``vid:pid``; ``None`` quando o diário não se lê.

    Sem ``executor`` e sob a suíte, nada roda (o diário real não é de teste).
    """
    if executor is not None:
        texto = executor(list(COMANDO))
    elif bluez_dbus.a_suite_esta_rodando():
        return None
    else:
        ambiente = dict(os.environ)
        ambiente["LC_ALL"] = "C"
        try:
            feito = subprocess.run(
                COMANDO, capture_output=True, text=True, timeout=ESPERA_DO_DIARIO_S,
                check=False, env=ambiente,
            )
        except (OSError, subprocess.SubprocessError) as erro:
            logger.debug("diario_do_kernel_nao_lido", erro=type(erro).__name__)
            return None
        texto = feito.stdout if feito.returncode == 0 else None
    if not texto:
        return None
    return quedas_do_diario(texto, agora())


def em_palavras(q: Quedas) -> str:
    """«caiu 12 vezes em 24 min» na tela, com o sinal de vezes (a partir de duas horas, em h)."""
    quando = (f"{round(q.minutos / 60)} h" if q.minutos >= MINUTOS_EM_HORAS
              else f"{q.minutos} min")
    return f"caiu {q.n}× em {quando}"  # noqa: RUF001


def nivel(q: Quedas) -> str:
    """``sofrendo`` a partir de :data:`QUEDAS_QUE_SOFREM`; abaixo, ``apertada``."""
    return "sofrendo" if q.n >= QUEDAS_QUE_SOFREM else "apertada"


__all__ = [
    "COMANDO",
    "DEBOUNCE_S",
    "QUEDAS_QUE_SOFREM",
    "REENUMERA_EM_S",
    "Quedas",
    "em_palavras",
    "ler_as_quedas",
    "nivel",
    "quedas_do_diario",
]
