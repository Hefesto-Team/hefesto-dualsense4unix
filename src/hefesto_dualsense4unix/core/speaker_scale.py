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

import math
from itertools import pairwise
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


#: A CURVA MEDIDA em 01/08 (`tests/unit/test_status_som_02_controle_de_volume.py`): o
#: registrador -> a magnitude do tom de 1 kHz no microfone do próprio DualSense. O 38 (6,2) e
#: abaixo é o chão do instrumento e fica de fora; do 102 em diante satura. Entre 51 e 76 dá
#: ~1 dB por passo.
_CURVA_DE_0108: Final[tuple[tuple[int, float], ...]] = (
    (51, 35.0), (64, 172.0), (76, 687.0), (102, 8759.0),
)

#: A PLACA DE ANTES: até 14/10/2026 a placa do cabo ficava nos 40 % do WirePlumber (cúbico,
#: fator 0,064 na amplitude, -23,9 dB), e esse fator escalava o alto-falante e o fone. Desde
#: OS-QUATRO-EM-HARMONIA-01 a placa fica cheia (`alto_falante_bt.PISO_DOS_MOTORES`), e o
#: desconto passa ao registrador. O número segue a curva de 01/08, A CONFIRMAR NO APARELHO
#: com a placa cheia e o pré-amp de hoje.
FATOR_DA_PLACA_DE_ANTES: Final[float] = 0.4**3


def _db_do_registrador(registrador: float) -> float:
    """O nível, em dB, do registrador na curva de 01/08; fora dela, a inclinação da ponta."""
    pontos = [(float(b), 20.0 * math.log10(m)) for b, m in _CURVA_DE_0108]
    (x0, y0), (x1, y1) = pontos[0], pontos[1]
    for (xa, ya), (xb, yb) in pairwise(pontos):
        x0, y0, x1, y1 = xa, ya, xb, yb
        if registrador <= xb:
            break
    return y0 + (registrador - x0) * (y1 - y0) / (x1 - x0)


def _registrador_do_db(nivel: float) -> float:
    """O inverso de :func:`_db_do_registrador`, pelos mesmos segmentos."""
    pontos = [(float(b), 20.0 * math.log10(m)) for b, m in _CURVA_DE_0108]
    (x0, y0), (x1, y1) = pontos[0], pontos[1]
    for (xa, ya), (xb, yb) in pairwise(pontos):
        x0, y0, x1, y1 = xa, ya, xb, yb
        if nivel <= yb:
            break
    return x0 + (nivel - y0) * (x1 - x0) / (y1 - y0)


def registrador_no_firmware(volume: int, *, placa_cheia: bool) -> int:
    """O volume da tela (o registrador da régua acima) -> o byte que vai ao firmware.

    Com a placa cheia (o cabo), a mesma posição do controle deslizante soa como soava com a
    placa nos 40 %: o nível da curva de 01/08 menos os 23,9 dB da :data:`FATOR_DA_PLACA_DE_ANTES`.
    Sem ela (o rádio, que nunca passou pela placa), o byte é o da tela. Zero é mudo; acima de
    zero sai ao menos 1, e o teto é a saturação.
    """
    bruto = max(0, min(255, int(volume)))
    if bruto == 0 or not placa_cheia:
        return bruto
    alvo = _db_do_registrador(min(bruto, _SPEAKER_REG_SATURA_EM)) + 20.0 * math.log10(
        FATOR_DA_PLACA_DE_ANTES
    )
    return max(1, min(_SPEAKER_REG_SATURA_EM, round(_registrador_do_db(alvo))))


__all__ = [
    "FATOR_DA_PLACA_DE_ANTES",
    "fracao_do_volume",
    "percentual_do_volume",
    "registrador_no_firmware",
    "volume_do_percentual",
]
