"""A régua de volume do alto-falante do DualSense — a conta, e só ela.

Este módulo existe porque a mesma grandeza é falada por TRÊS superfícies: a
barra de leitura e o controle deslizante da aba Status, e o comando
`speaker volume` da linha de comando. Enquanto a conta viveu junto dos widgets,
a linha de comando tinha uma cópia linear dela — e `speaker volume 60` mandava
para o registrador um valor diferente dos 60 % do controle deslizante, no mesmo
hardware, com resultado audível diferente. Duas contas para a mesma grandeza é
a classe de defeito que esta casa mais paga.

Mora em `core/` e não em `app/` por dois motivos, e o segundo é o duro:

1. a curva é propriedade do **DualSense**, não do desenho da tela — quem a
   mediu foi o microfone do controle, não o GTK;
2. `app/widgets/` puxa GTK no import do pacote, e a linha de comando roda em
   servidor sem interface. Importar a régua de lá fazia `speaker volume`
   carregar a interface gráfica inteira para escrever um byte. Há teste
   travando isso (`tests/unit/test_speaker_regua_unica_cli_e_janela.py`).

Python puro de propósito: nenhum import de `gi`, de widget ou de daemon. O
`sensor_widgets` reexporta o que está aqui, para o código de tela continuar
lendo como sempre leu.
"""

from __future__ import annotations

from typing import Final

#: do protocolo: tom de 1 kHz no sink, o microfone do próprio DualSense como
_SPEAKER_REG_MUDO_ATE: Final[int] = 38
_SPEAKER_REG_SATURA_EM: Final[int] = 102


def fracao_do_volume(volume: int) -> float:
    """Volume bruto 0-255 do alto-falante -> fração 0.0-1.0 da barra."""
    bruto = max(0, min(255, int(volume)))
    if bruto <= _SPEAKER_REG_MUDO_ATE:
        return 0.0
    if bruto >= _SPEAKER_REG_SATURA_EM:
        return 1.0
    faixa = _SPEAKER_REG_SATURA_EM - _SPEAKER_REG_MUDO_ATE
    return (bruto - _SPEAKER_REG_MUDO_ATE) / faixa


def percentual_do_volume(volume: int) -> int:
    """Volume bruto 0-255 -> a porcentagem que a tela mostra (0-100)."""
    return round(fracao_do_volume(volume) * 100)


def volume_do_percentual(percentual: float) -> int:
    """Porcentagem da tela (0-100) -> volume bruto 0-255 do protocolo."""
    pct = max(0.0, min(100.0, float(percentual)))
    if pct <= 0.0:
        return 0
    faixa = _SPEAKER_REG_SATURA_EM - _SPEAKER_REG_MUDO_ATE
    passo = max(1, round(pct * faixa / 100.0))
    return max(0, min(255, _SPEAKER_REG_MUDO_ATE + passo))


__all__ = [
    "fracao_do_volume",
    "percentual_do_volume",
    "volume_do_percentual",
]
