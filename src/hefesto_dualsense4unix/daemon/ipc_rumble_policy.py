"""Aplicação da política global de rumble sobre pares (weak, strong)."""
from __future__ import annotations

import contextlib
import time as _time
from typing import Any

from hefesto_dualsense4unix.utils.logging_config import get_logger

logger = get_logger(__name__)


def memoria_viva_do_auto(daemon: Any) -> tuple[float, float]:
    """O estado de debounce do "auto" que vale AGORA: (mult, instante)."""
    mult = getattr(daemon, "_last_auto_mult", None)
    quando = getattr(daemon, "_last_auto_change_at", None)
    if isinstance(mult, bool) or not isinstance(mult, (int, float)):
        mult = 0.7
    if isinstance(quando, bool) or not isinstance(quando, (int, float)):
        quando = 0.0
    return float(mult), float(quando)


def _uniq_do_primario(controller: Any) -> str | None:
    """O MAC do primário, normalizado, ou ``None``."""
    from hefesto_dualsense4unix.core.sysfs_leds import norm_mac

    primario = getattr(controller, "primary_uniq", None)
    valor_do_primario: Any = None
    try:
        valor_do_primario = primario() if callable(primario) else primario
    except Exception:
        logger.debug("rumble_primario_indisponivel", exc_info=True)
    if not isinstance(valor_do_primario, str) or not valor_do_primario:
        return None
    return norm_mac(valor_do_primario)


def _bateria_para_a_forca(
    daemon: Any, uniq: str | None, *, do_primario: bool = False
) -> int | None:
    """A bateria do controle ``uniq``, lida da memória do backend, sem I/O.

    Backend que lê por controle (``bateria_de``): a daquele controle, e
    ``None`` quando ele ainda não reportou. Backend sem essa leitura (o
    ``FakeController``, que é um controle só): a do estado publicado, que é
    a dele. O primário sem leitura viva (o posto guardado, com o dono fora)
    também lê o estado publicado, que segue com a carga do dono do posto.
    """
    controller = getattr(daemon, "controller", None)
    ler = getattr(controller, "bateria_de", None)
    if callable(ler):
        valor: Any = None
        if uniq:
            try:
                valor = ler(uniq)
            except Exception:
                logger.debug("rumble_bateria_indisponivel", uniq=uniq, exc_info=True)
        if isinstance(valor, int) and not isinstance(valor, bool):
            return int(valor)
        if not do_primario:
            return None
    store = getattr(daemon, "store", None)
    if store is None:
        return None
    try:
        ctrl = store.snapshot().controller
    except Exception:
        logger.debug("rumble_policy_state_read_fallback", exc_info=True)
        return None
    if ctrl is None or ctrl.battery_pct is None:
        return None
    return int(ctrl.battery_pct)


def memoria_do_auto_por_controle(daemon: Any) -> dict[str, tuple[float, float]]:
    """O debounce do ``auto`` de cada controle: ``{uniq: (âncora, instante)}``."""
    memoria = getattr(daemon, "_auto_por_controle", None)
    if not isinstance(memoria, dict):
        memoria = {}
        try:
            daemon._auto_por_controle = memoria
        except Exception:
            logger.debug("rumble_memoria_sem_lugar", exc_info=True)
    return memoria


def forca_para(daemon: Any, uniq: str | None, agora: float | None = None) -> float:
    """A força de vibração de ``uniq`` agora: o funil único, com as entradas dele.

    Junta o que :func:`core.rumble.forca_do_controle` pede — a bateria DE
    ``uniq`` (:func:`_bateria_para_a_forca`), o fator da peça dele
    (``escala_de`` do backend) e a memória do ``auto`` por controle — e
    devolve a fração. ``uniq`` ``None`` é o primário.

    O ``state_full.rumble_mult_applied`` segue dizendo o do primário: a
    política dele, sob o teto e sem a peça, vai a ``daemon._last_auto_mult``.
    """
    daemon_cfg = getattr(daemon, "config", None) if daemon else None
    if daemon_cfg is None:
        return 1.0

    from hefesto_dualsense4unix.core.rumble import (
        _orcamento_declarado,
        _sob_o_teto,
        forca_do_controle,
        teto_do_orcamento,
    )
    from hefesto_dualsense4unix.core.sysfs_leds import norm_mac
    from hefesto_dualsense4unix.daemon.lifecycle import AUTO_DEBOUNCE_SEC

    controller = getattr(daemon, "controller", None)
    primario = _uniq_do_primario(controller)
    alvo = (norm_mac(uniq) or uniq) if uniq else primario
    memoria = memoria_do_auto_por_controle(daemon)
    chave = alvo or ""
    e_o_primario = alvo is None or alvo == primario
    if e_o_primario and chave not in memoria:
        memoria[chave] = memoria_viva_do_auto(daemon)
    escala: float | None = None
    ler_escala = getattr(controller, "escala_de", None)
    if callable(ler_escala) and alvo:
        with contextlib.suppress(Exception):
            valor = ler_escala(alvo)
            escala = float(valor) if isinstance(valor, (int, float)) else None
    mult = forca_do_controle(
        daemon_cfg,
        alvo,
        _bateria_para_a_forca(daemon, alvo, do_primario=e_o_primario),
        memoria,
        _time.monotonic() if agora is None else agora,
        escala=escala,
        auto_debounce_sec=AUTO_DEBOUNCE_SEC,
    )
    if e_o_primario:
        ancora, quando = memoria[chave]
        teto = teto_do_orcamento(_orcamento_declarado(daemon_cfg))
        with contextlib.suppress(Exception):
            daemon._last_auto_mult = _sob_o_teto(ancora, teto)
            daemon._last_auto_change_at = quando
    return mult


def apply_rumble_policy(
    daemon: Any, weak: int, strong: int, uniq: str | None = None
) -> tuple[int, int]:
    """O par ``(weak, strong)`` com a força de ``uniq`` (``None``: o primário)."""
    daemon_cfg = getattr(daemon, "config", None) if daemon else None
    if daemon_cfg is None:
        return weak, strong
    mult = forca_para(daemon, uniq)
    eff_weak = max(0, min(255, round(weak * mult)))
    eff_strong = max(0, min(255, round(strong * mult)))
    return eff_weak, eff_strong


def quem_recebe_sem_dono(controller: Any) -> list[str]:
    """Os MACs que o ``set_rumble`` sem endereço alcançaria, para escrever um a um.

    É o alvo de output quando há um (a rota sem endereço segue o seletor), e
    senão cada controle conectado. Vazio quando o backend não escreve por
    controle (``set_rumble_for``) ou não diz quem está conectado: quem chama
    volta ao ``set_rumble`` de sempre.
    """
    describe = getattr(controller, "describe_controllers", None)
    if not callable(describe) or not callable(getattr(controller, "set_rumble_for", None)):
        return []
    alvo = uniq_do_alvo_de_output(controller)
    if alvo is not None:
        return [alvo]
    try:
        entradas = describe()
    except Exception:
        logger.debug("rumble_mesa_indisponivel", exc_info=True)
        return []
    uniqs: list[str] = []
    for entrada in entradas if isinstance(entradas, list) else []:
        if not isinstance(entrada, dict) or not entrada.get("connected"):
            continue
        uniq = entrada.get("uniq")
        if isinstance(uniq, str) and uniq and uniq not in uniqs:
            uniqs.append(uniq)
    return uniqs


def uniq_do_alvo_de_output(controller: Any) -> str | None:
    """MAC do alvo de output NESTE instante, ou None para "a mesa inteira"."""
    getter = getattr(controller, "get_output_target_uniq", None)
    if not callable(getter):
        return None
    try:
        alvo = getter()
    except Exception:
        logger.debug("output_target_uniq_indisponivel", exc_info=True)
        return None
    return alvo if isinstance(alvo, str) and alvo else None


_apply_rumble_policy = apply_rumble_policy


__all__ = [
    "_apply_rumble_policy",
    "apply_rumble_policy",
    "forca_para",
    "memoria_do_auto_por_controle",
    "memoria_viva_do_auto",
    "quem_recebe_sem_dono",
    "uniq_do_alvo_de_output",
]
