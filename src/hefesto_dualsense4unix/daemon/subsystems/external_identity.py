"""Identidade e LED dos controles EXTERNOS (EXT-04, sprint 2026-07-18).

Bug grave provado ao vivo (estudo §P3-BÔNUS): `_external_inventory` escrevia
os LEDs como efeito colateral de TODA leitura `controller.list{external:true}`
e a GUI polla a cada 4s sem comparar estado → bombardeio de subcomandos BT no
firmware clone → `joycon_enforce_subcmd_rate: exceeded max attempts` em loop →
o hid-nintendo DESREGISTROU o 8BitDo (a "morte por BT" era agravada por nós).
E o slot era `ds_count + índice-do-poll + 1`, recalculado a cada enumeração —
o LED mudava sozinho a cada poll/replug (ao vivo: o 8BitDo foi 2 de madrugada
e 4 à noite sem ninguém pedir).

A cura, em três peças:

1. :class:`ExternalIdentityRegistry` — slots ESTÁVEIS por ``uniq`` (MAC),
   análogo ao ``ControllerIdentityRegistry`` dos DualSense: menor slot livre
   ACIMA da reserva dos DualSense, slot RESERVADO no disconnect (replug
   recupera o número), persistência POR BOOT no MESMO ``controllers.json``
   (namespace separado ``externals`` — cada registro preserva o namespace do
   outro no read-modify-write).
2. :class:`ExternalLedSync` — o LED é aplicado pelo TICK do daemon (poll
   lento ~2s do lifecycle), com cache por-VALOR (escreve SÓ em mudança) +
   rate-limit de ``LED_MIN_INTERVAL_SEC`` por dispositivo + telemetria INFO
   ``external_led_written`` (antes era silencioso via contextlib.suppress).
3. A leitura IPC (`_external_inventory`) vira PURA: consulta ``peek`` (nunca
   atribui, nunca escreve LED).

Hermeticidade: a fiação do daemon (`_wire_external_registry`) só liga isto
quando o ``identity_registry`` dos DualSense existe (backend real) — com o
FakeController nada de /dev/input é enumerado e nenhum LED é tocado.
"""
from __future__ import annotations

import contextlib
import json
import os
import re
import tempfile
import threading
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any

from hefesto_dualsense4unix.utils.logging_config import get_logger

if TYPE_CHECKING:
    from collections.abc import Iterable

logger = get_logger(__name__)

#: Mesmo arquivo do registro dos DualSense — namespace separado (``externals``).
_CONTROLLERS_FILE = "controllers.json"

#: MAC "de verdade" (mesma regra estrita do registro DualSense): 12 hex, com
#: ou sem ``:``/``-``. Qualquer outra key é identidade VOLÁTIL de sessão.
_MAC_RE = re.compile(
    r"^(?:[0-9a-fA-F]{12}|(?:[0-9a-fA-F]{2}[:-]){5}[0-9a-fA-F]{2})$"
)

#: Rate-limit mínimo entre escritas de LED no MESMO dispositivo (EXT-04c).
#: O hid-nintendo tem enforcement de taxa de subcomando BT
#: (``joycon_enforce_subcmd_rate``) e firmware clone estoura fácil — 2s por
#: device é ordens de magnitude abaixo do bombardeio de 4-5 nós por poll que
#: matou o 8BitDo ao vivo.
LED_MIN_INTERVAL_SEC = 2.0


def _read_boot_id() -> str | None:
    """boot_id do kernel (None se ilegível) — sessão morta se difere no load."""
    try:
        with open("/proc/sys/kernel/random/boot_id", encoding="utf-8") as fh:
            value = fh.read().strip()
        return value or None
    except OSError:
        return None


class ExternalIdentityRegistry:
    """``uniq`` de externo → slot GLOBAL de co-op, com reserva de sessão.

    Espelha o desenho do ``ControllerIdentityRegistry`` (D1/D2/D9), com duas
    diferenças de domínio:

    - o menor slot livre respeita a RESERVA dos DualSense (``reserve``):
      externos continuam a contagem (1º externo = reserva+1) — mas um slot já
      atribuído NUNCA é renumerado quando a reserva muda depois (estabilidade
      vence: é o fim do "LED muda sozinho");
    - sem expiração por sessão-esvaziou: a persistência é POR BOOT (o load
      ignora arquivo de outro boot) e o disconnect apenas RESERVA o slot.

    Thread-safety: os métodos são chamados pelo tick do lifecycle (via
    executor) e pela leitura IPC (``asyncio.to_thread``) — RLock próprio.
    O save é read-modify-write no ``controllers.json``: preserva ``slots``
    (namespace dos DualSense) e grava só ``externals``.
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._slots: dict[str, int] = {}
        self._volatile: set[str] = set()
        self._connected: set[str] = set()
        self._dirty = False
        self._loaded = False

    @staticmethod
    def _canonical(uniq: str) -> tuple[str, bool]:
        """``(key, persistível)`` — MAC 12-hex canônico ou key volátil crua."""
        value = uniq.strip()
        if _MAC_RE.match(value):
            return value.lower().replace(":", "").replace("-", ""), True
        return value, False

    def slot_for(
        self, uniq: str | None, *, reserve: int = 0, assign: bool = True
    ) -> int | None:
        """Slot do externo ``uniq``; atribui o menor livre > ``reserve`` na 1ª vez.

        ``assign=False`` é leitura pura (não atribui, não marca conectado) —
        é o modo da rota IPC. SEM I/O de disco (a persistência fica com
        ``sync_connected``, no tick lento).
        """
        if not uniq or not isinstance(uniq, str):
            return None
        key, persistable = self._canonical(uniq)
        if not key:
            return None
        with self._lock:
            slot = self._slots.get(key)
            if slot is not None:
                if assign:
                    self._connected.add(key)
                return slot
            if not assign:
                return None
            used = set(self._slots.values())
            slot = max(1, int(reserve) + 1)
            while slot in used:
                slot += 1
            self._slots[key] = slot
            if persistable:
                self._dirty = True
            else:
                self._volatile.add(key)
            self._connected.add(key)
            logger.info(
                "external_slot_atribuido",
                uniq=key,
                slot=slot,
                reserva_dualsense=reserve,
                volatil=not persistable,
            )
            return slot

    def peek(self, uniq: str | None) -> int | None:
        """Leitura PURA do slot (rota IPC): nunca atribui, nunca persiste."""
        return self.slot_for(uniq, assign=False)

    def sync_connected(self, uniqs: Iterable[str]) -> None:
        """Reconcilia com os uniqs presentes AGORA (tick ~2s) e persiste.

        Quem saiu vira RESERVA (slot preso ao uniq — replug recupera o
        número). Diferente do registro DualSense, não há expiração por
        sessão-esvaziou: um externo BT que dorme não pode perder o número
        (era exatamente o sintoma). ÚNICO ponto de escrita em disco fora do
        ``load()``.
        """
        vivos: set[str] = set()
        for uniq in uniqs:
            if not uniq or not isinstance(uniq, str):
                continue
            key, _ = self._canonical(uniq)
            vivos.add(key)
        with self._lock:
            self._connected = vivos
            if self._dirty:
                self._save_locked()
                self._dirty = False

    def snapshot(self) -> dict[str, int]:
        """Cópia do mapa key→slot (conectados + reservas). Leitura pura."""
        with self._lock:
            return dict(self._slots)

    # -- persistência (namespace ``externals`` do controllers.json) -------

    def load(self) -> None:
        """Carrega o namespace ``externals`` — só se do MESMO boot da máquina."""
        with self._lock:
            if self._loaded:
                return
            self._loaded = True
            try:
                data = json.loads(self._path().read_text(encoding="utf-8"))
            except (FileNotFoundError, json.JSONDecodeError, OSError):
                return
            except Exception as exc:  # defensivo — load jamais derruba o boot
                logger.debug("external_identity_load_falhou", err=str(exc))
                return
            boot_id = _read_boot_id()
            if not isinstance(data, dict):
                return
            if not boot_id or data.get("boot_id") != boot_id:
                return
            externals = data.get("externals")
            if not isinstance(externals, dict):
                return
            usados: set[int] = set()
            for raw_key, raw_slot in externals.items():
                if not isinstance(raw_key, str) or not isinstance(raw_slot, int):
                    continue
                if isinstance(raw_slot, bool) or raw_slot < 1:
                    continue
                key, persistable = self._canonical(raw_key)
                if not persistable:
                    continue
                if key in self._slots or raw_slot in usados:
                    continue
                self._slots[key] = raw_slot
                usados.add(raw_slot)
            if self._slots:
                logger.info(
                    "external_slots_restaurados", slots=dict(self._slots)
                )

    @staticmethod
    def _path() -> Path:
        """Path do ``controllers.json`` — import LAZY (monkeypatch dos testes)."""
        from hefesto_dualsense4unix.utils.xdg_paths import config_dir

        return config_dir(ensure=True) / _CONTROLLERS_FILE

    def _save_locked(self) -> None:
        """Read-modify-write atômico: grava ``externals`` preservando o resto.

        O ``ControllerIdentityRegistry`` (DualSense) grava ``boot_id`` +
        ``slots`` no mesmo arquivo — cada lado preserva o namespace do outro.
        Nunca propaga exceção: perder um save = renumerar no próximo boot.
        """
        try:
            path = self._path()
            data: dict[str, Any] = {}
            with contextlib.suppress(Exception):
                loaded = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(loaded, dict):
                    data = loaded
            data["boot_id"] = _read_boot_id()
            data["externals"] = {
                key: slot
                for key, slot in self._slots.items()
                if key not in self._volatile
            }
            payload = json.dumps(data, ensure_ascii=False)
            fd, tmp = tempfile.mkstemp(
                dir=os.path.dirname(os.fspath(path)), prefix=".controllers_"
            )
            try:
                os.write(fd, payload.encode())
            finally:
                os.close(fd)
            os.replace(tmp, path)
            logger.debug("external_slots_salvos", externals=data["externals"])
        except Exception as exc:
            logger.debug("external_identity_save_falhou", err=str(exc))


class ExternalLedSync:
    """Aplica o LED de posição dos externos no TICK do daemon (EXT-04, item 3).

    ``tick()`` é BLOQUEANTE (enumeração evdev de 10-40 ms + sysfs) — o
    lifecycle a despacha via ``_run_blocking`` (executor), nunca no event
    loop. Disciplina de escrita, na ordem:

    a. cache por-VALOR: escreve SÓ quando o slot a exibir mudou para aquele
       dispositivo (a chave inclui o hidraw — replug ganha nó novo e o LED
       renasce naturalmente);
    b. rate-limit ``LED_MIN_INTERVAL_SEC`` entre escritas no MESMO
       dispositivo (mesmo quando o valor mudou);
    c. telemetria INFO ``external_led_written slot=N uniq=...`` a cada
       escrita EFETIVA (nunca mais silencioso).

    Falha de escrita (sem a regra udev 79) não entra no cache — o retry
    natural do tick fica limitado pelo rate-limit e custa só um
    ``os.path.exists`` False (nenhum tráfego HID).
    """

    def __init__(self, daemon: Any, registry: ExternalIdentityRegistry) -> None:
        self._daemon = daemon
        self._registry = registry
        #: (uniq-ou-vazio, hidraw) → último slot ESCRITO com sucesso.
        self._last_value: dict[tuple[str, str], int] = {}
        #: (uniq-ou-vazio, hidraw) → monotonic da última TENTATIVA de escrita.
        self._last_write_at: dict[tuple[str, str], float] = {}

    def _ds_reserve(self) -> int:
        """Maior slot dos DualSense (conectados + reservas) — piso dos externos."""
        registry = getattr(self._daemon, "identity_registry", None)
        snap = getattr(registry, "snapshot", None) if registry is not None else None
        if not callable(snap):
            return 0
        with contextlib.suppress(Exception):
            slots = snap()
            if isinstance(slots, dict) and slots:
                return max(int(v) for v in slots.values())
        return 0

    def tick(self, *, now: float | None = None) -> None:
        """Enumera, reconcilia o registro e aplica LEDs (com cache/rate-limit)."""
        from hefesto_dualsense4unix.core.evdev_reader import (
            discover_external_gamepads,
        )
        from hefesto_dualsense4unix.core.external_leds import apply_player_number

        try:
            inventory = discover_external_gamepads()
        except Exception as exc:  # nunca derruba o poll loop
            logger.debug("external_led_tick_enumeracao_falhou", err=str(exc))
            return
        agora = time.monotonic() if now is None else now
        reserve = self._ds_reserve()
        self._registry.sync_connected(
            e["uniq"] for e in inventory if isinstance(e.get("uniq"), str)
        )
        vivos: set[tuple[str, str]] = set()
        for entry in inventory:
            uniq = entry.get("uniq")
            uniq = uniq if isinstance(uniq, str) and uniq else None
            hidraw = entry.get("hidraw")
            # Identidade volátil (sem MAC): o evdev_path vale pela sessão.
            identity = uniq or f"path:{entry.get('evdev_path')}"
            slot = self._registry.slot_for(identity, reserve=reserve)
            if slot is None or not isinstance(hidraw, str) or not hidraw:
                continue
            key = (uniq or "", hidraw)
            vivos.add(key)
            if self._last_value.get(key) == slot:
                continue  # (a) cache por-valor: nada mudou, nada a escrever
            if agora - self._last_write_at.get(key, float("-inf")) < (
                LED_MIN_INTERVAL_SEC
            ):
                continue  # (b) rate-limit por dispositivo
            self._last_write_at[key] = agora
            escreveu = False
            with contextlib.suppress(Exception):
                escreveu = bool(apply_player_number(hidraw, slot))
            if escreveu:
                self._last_value[key] = slot
                logger.info(
                    "external_led_written", slot=slot, uniq=uniq, hidraw=hidraw
                )
        # Poda: devices que sumiram saem do cache — o replug (nó novo ou o
        # mesmo nome reusado) reescreve o LED naturalmente.
        for key in list(self._last_value):
            if key not in vivos:
                self._last_value.pop(key, None)
                self._last_write_at.pop(key, None)


__all__ = [
    "LED_MIN_INTERVAL_SEC",
    "ExternalIdentityRegistry",
    "ExternalLedSync",
]
