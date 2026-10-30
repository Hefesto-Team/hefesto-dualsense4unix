"""O motor de um controle de fora pelo nó evdev dele: o ``FF_RUMBLE`` do kernel.

D-3010-OS-EXTERNOS-GANHAM-CONTROLE-VIRTUAL: o Pro Controller e o 8BitDo não têm handle no
backend do DualSense, e o rumble que o jogo escreve no pad virtual deles chega ao aparelho
pelo nó que o leitor do co-op já tem aberto. O ``hid-nintendo`` registra o ``ff-memless``, em
que ``replay.length`` zero é «até o próximo pedido»; o efeito sai sozinho quando o nó fecha.
"""
from __future__ import annotations

import threading
from typing import Any

from hefesto_dualsense4unix.utils.logging_config import get_logger

logger = get_logger(__name__)


def motor_em_16_bits(valor: int) -> int:
    """O motor de 0 a 255 na escala de 16 bits do ``ff_rumble_effect``."""
    return max(0, min(255, int(valor))) * 257


class MotorDoNo:
    """O rumble no nó que o leitor tem aberto agora, com um efeito só, reaproveitado."""

    def __init__(self, leitor: Any) -> None:
        self._leitor = leitor
        self._lock = threading.Lock()
        self._efeito: tuple[Any, int] | None = None

    def vibrar(self, fraco: int, forte: int) -> bool:
        """O par de motores (0 a 255); ``(0, 0)`` para o efeito em curso."""
        dev = getattr(self._leitor, "_active_dev", None)
        if dev is None:
            return False
        try:
            from evdev import ecodes, ff
        except ImportError:  # pragma: no cover
            return False
        with self._lock:
            efeito = self._efeito[1] if self._efeito and self._efeito[0] is dev else None
            try:
                if fraco <= 0 and forte <= 0:
                    if efeito is not None:
                        dev.write(ecodes.EV_FF, efeito, 0)
                    return True
                pedido = ff.Effect(
                    ecodes.FF_RUMBLE,
                    -1 if efeito is None else efeito,
                    0,
                    ff.Trigger(0, 0),
                    ff.Replay(0, 0),
                    ff.EffectType(
                        ff_rumble_effect=ff.Rumble(
                            strong_magnitude=motor_em_16_bits(forte),
                            weak_magnitude=motor_em_16_bits(fraco),
                        )
                    ),
                )
                efeito = dev.upload_effect(pedido)
                self._efeito = (dev, efeito)
                dev.write(ecodes.EV_FF, efeito, 1)
                return True
            except Exception as exc:
                self._efeito = None
                logger.debug("motor_do_no_falhou", err=str(exc))
                return False
