"""Factories dos 19 presets de trigger conforme DSX Paliverse.

Cada factory produz um `TriggerEffect` (definido em `hefesto_dualsense4unix.core.controller`)
com `mode` low-level (valores do enum `pydualsense.TriggerModes`) e 7 bytes
de `forces` no formato HID. Ver `docs/protocol/trigger-modes.md` para a
tabela canônica e a distinção entre HID e presets.

Todas as factories validam `ranges`. As de modo LEGADO ou NÃO OFICIAL
convertem amplitudes nomeadas (0-8) em bytes HID (0-255) multiplicando por
`AMPLITUDE_SCALE`.

**TRIGGER-CANON-01: os modos OFICIAIS não usam essa escala.** Eles recebem um
bitmask de zonas ativas (u16) e forças de três bits com valor `força - 1`
(u32) — ver `_feedback_oficial` e `_vibracao_oficial`. Sete presets desta
árvore mandavam o modo errado, três deles o `0x05`, que é literalmente OFF, e
ela mediu pelo tato: *"rígido e desligado sem diferença"*. Uso típico:

    from hefesto_dualsense4unix.core.trigger_effects import galloping, machine
    controller.set_trigger("right", galloping(0, 9, 7, 7, 10))
    controller.set_trigger("left",  machine(0, 9, 3, 3, 50, 8))

`TriggerMode` expõe os valores do enum do pydualsense sem exigir
que o caller faça o import (mantém o backend trocável — ADR-001).
"""
from __future__ import annotations

from collections.abc import Iterable
from enum import IntEnum

from hefesto_dualsense4unix.core.controller import TriggerEffect
from hefesto_dualsense4unix.utils.logging_config import get_logger

logger = get_logger(__name__)

AMPLITUDE_SCALE = 32  # Normaliza 0-8 (DSX) -> 0-255 (HID byte)

# BUG-TRIGGER-MULTIPOS-FORCA8-01 — O REGISTRO ORIGINAL, e a REFUTAÇÃO dele.
#
# O que foi registrado em 2026 como medido: *"no bloco multi-position o report
# NÃO carrega um byte por posição — carrega um campo de TRÊS BITS por posição
# (10 x 3 = 30 bits). Logo o máximo REAL por posição é 7, não 8. A escala
# nomeada (DSX) vai a 8 e continua aceita, mas 8 SATURA em 7 com log
# explícito; antes o `& 0x7` cru fazia 8 virar 0, isto é, força máxima virava
# NENHUMA força — em silêncio."*
#
# ---- REFUTADO em 01/08/2026 (TRIGGER-CANON-01) ----
#
# **A observação estava certa e a conclusão errada.** O campo tem mesmo três
# bits. Mas a codificação não é a força crua: é `(força - 1) & 0x07`, com
# `força` em 1..8. Assim:
#
#   força 1 -> 0b000        força 8 -> 0b111
#
# **Os oito níveis SÃO expressáveis.** O que não cabe nos três bits é o ZERO —
# e zero não é um nível de força: é ZONA INATIVA, e isso se diz no bitmask de
# zonas ativas (bytes 1-2 do bloco), que esta árvore não escrevia.
#
# O sintoma que originou o bug (força máxima virando nenhuma força) era real;
# a causa era a falta do `- 1` e do bitmask, não um limite do campo. A cura de
# então — saturar 8 em 7 — não fazia mal, mas escondia a causa e custou um
# nível de força.
#
# Fontes: enum `ScePadTriggerEffectMode` (header da Sony no Steamworks SDK),
# gist do Nielk1 e wiki do Game Controller Collective, que concordam. Ver
# `docs/protocol/dualsense-referencia-canonica.md` §4.
#
# A constante fica, e é ONDE ela ainda vale: o valor máximo que os três bits
# guardam. O que caducou foi a leitura de que ela é o teto da FORÇA.
MULTI_POSITION_MAX_STRENGTH = 7


#: TRIGGER-CANON-01 — os modos que CORROMPEM o estado do gatilho.
#:
#: `0xFC`-`0xFE` são modos de depuração do firmware. Depois deles o gatilho
#: fica num estado que só sai desligando o controle. O `CALIBRATION = 0xFC`
#: era membro público desta enum e alcançável pelo preset `Custom` — que a
#: própria docstring anuncia como "útil para experimentação".
#:
#: Fonte: gist do Nielk1 e a wiki do Game Controller Collective, que
#: concordam. Ver `docs/protocol/dualsense-referencia-canonica.md` §4.
MODOS_DE_DEPURACAO: frozenset[int] = frozenset({0xFC, 0xFD, 0xFE})


class TriggerMode(IntEnum):
    """Modos do bloco de gatilho, com os nomes da enum OFICIAL da Sony.

    TRIGGER-CANON-01. Os nomes antigos (`RIGID_A/B/AB`, `PULSE_A/B/AB`) vieram
    de uma engenharia reversa de 2020 e **não descrevem o que o firmware
    faz** — `RIGID_B` vale `0x05`, que é literalmente OFF, e três presets desta
    árvore o mandavam achando que endureciam o gatilho. Ela mediu pelo tato:
    *"rígido e desligado sem diferença"*.

    Os nomes canônicos vêm de `ScePadTriggerEffectMode`, o header da Sony que
    a Valve redistribui verbatim no Steamworks SDK (>= 1.55), triangulado com
    três engenharias reversas independentes que concordam entre si. O header é
    marcado "SIE CONFIDENTIAL" e **não é copiado para cá** — só a semântica.
    Ver `docs/protocol/dualsense-referencia-canonica.md` §1 e §4.

    **Os nomes antigos ficam como ALIAS**, e isso não é indecisão: eles estão
    em perfis no disco dela e no `docs/protocol/trigger-modes.md`. Num
    `IntEnum` os dois nomes resolvem para o MESMO membro, então nada quebra e
    o código novo lê o nome honesto.
    """

    # --- oficiais (a enum da Sony) -----------------------------------------
    OFF = 0x00
    #: O OFF que o firmware entende no bloco de gatilho. Distinto do `0x00`:
    #: este é o que a enum da Sony chama de `MODE_OFF`.
    DESLIGADO_OFICIAL = 0x05
    FEEDBACK = 0x21
    WEAPON = 0x25
    VIBRATION = 0x26

    # --- não oficiais, vivos no firmware ------------------------------------
    BOW = 0x22
    GALLOPING = 0x23
    MACHINE = 0x27

    # --- legado (aceito, sem validação de parâmetros) -----------------------
    RIGID = 0x01
    PULSE = 0x02
    SIMPLE_VIBRATION = 0x06

    # --- os nomes de 2020, agora ALIAS dos de cima --------------------------
    RIGID_A = 0x21
    RIGID_B = 0x05
    RIGID_AB = 0x25
    PULSE_A = 0x22
    PULSE_B = 0x06
    PULSE_AB = 0x26


ZERO7 = (0, 0, 0, 0, 0, 0, 0)

#: As dez posições que o gatilho distingue (0 = solto, 9 = fundo).
_ZONAS_DO_GATILHO = 10


# ---------------------------------------------------------------------------
# TRIGGER-CANON-01 / E2 — o empacotamento que os modos OFICIAIS exigem
# ---------------------------------------------------------------------------
#
# Os modos oficiais **não recebem posições cruas**. Recebem:
#
#   bytes 1-2  bitmask u16 LE das ZONAS ATIVAS (bit N = posição N, 0..9)
#   bytes 3-6  as FORÇAS, 3 bits por zona, u32 LE, com valor `força - 1`
#
# E é isso que explica a medição dela. O `0x25` é o Weapon OFICIAL, e ele não
# fez NADA nas mãos dela (*"resistência nada também"*) mesmo estando com o
# número de modo certo: sem bitmask, o firmware vê **nenhuma zona ativa**.
#
# Por que os cinco presets de `0x26` funcionavam mesmo com o empacotamento
# errado: os modos oficiais VALIDAM os parâmetros, os não oficiais e os
# legados não. E os `forces[0]`/`forces[1]` que esta árvore escrevia caíam
# exatamente em cima do bitmask — cada preset produzia um bitmask acidental
# diferente, e o firmware respondia a cada um de um jeito. Foi por isso que
# ela disse *"eles são bem diferentes viu"*, contra a previsão de que seriam
# idênticos.


def _bitmask_de_zonas(posicoes: Iterable[int]) -> int:
    """Bitmask u16 das zonas ativas: bit N ligado = posição N tem força."""
    total = 0
    for posicao in posicoes:
        total |= 1 << int(posicao)
    return total


def _forcas_em_tres_bits(forcas_por_zona: dict[int, int]) -> int:
    """As forças empacotadas em 3 bits por zona, com valor ``força - 1``.

    `força` vai de 1 a 8 e ocupa 0..7 nos três bits. **A força 0 não é
    representável aqui, e não precisa ser**: zona sem força é zona INATIVA, e
    isso se expressa no bitmask.

    É esta a codificação que refuta o `BUG-TRIGGER-MULTIPOS-FORCA8-01`, que
    concluiu *"o campo tem 3 bits, logo o máximo é 7 e a força 8 satura"*. Os
    oito níveis SÃO expressáveis — o que não cabe é o zero, e o zero não é um
    nível de força.
    """
    empacotado = 0
    for zona, forca in forcas_por_zona.items():
        if forca <= 0:
            continue
        empacotado |= ((min(8, forca) - 1) & 0x07) << (3 * int(zona))
    return empacotado & 0xFFFFFFFF


def _forces_oficiais(
    zonas: int, forcas: int, *, extra9: int = 0
) -> tuple[int, int, int, int, int, int, int]:
    """Monta os sete slots de `forces` no layout dos modos oficiais.

    O mapeamento para o fio está em `backend_pydualsense`: `forces[0..5]` vão
    para os bytes 1-6 do bloco e **`forces[6]` vai para o byte 9** — que é
    onde mora a `frequency` do `Vibration` oficial. Nenhuma mudança de
    protocolo foi necessária para esta sprint, só de empacotamento.
    """
    return (
        zonas & 0xFF,
        (zonas >> 8) & 0xFF,
        forcas & 0xFF,
        (forcas >> 8) & 0xFF,
        (forcas >> 16) & 0xFF,
        (forcas >> 24) & 0xFF,
        extra9 & 0xFF,
    )


def _zonas_a_partir_de(inicio: int, forca: int) -> dict[int, int]:
    """Da posição `inicio` até o fim do curso, todas com a mesma força.

    É o que "rígido a partir daqui" e "resistência a partir daqui" significam
    no firmware: um bloco contíguo de zonas ativas. Força 0 devolve dicionário
    vazio — nenhuma zona ativa, que é o jeito honesto de dizer "sem efeito".
    """
    if forca <= 0:
        return {}
    return {zona: forca for zona in range(inicio, _ZONAS_DO_GATILHO)}


def _forca_de_byte(valor: int) -> int:
    """Converte a força de byte (0-255, o que a tela dela mostra) para 1-8.

    A faixa 0-255 é CONTRATO: está nos perfis dela e nos limites dos controles
    deslizantes da aba Gatilhos (`trigger_specs`). O firmware quer 1..8. A
    conversão mora aqui, num lugar só, em vez de mudar a faixa do parâmetro e
    invalidar os perfis salvos.
    """
    if valor <= 0:
        return 0
    return max(1, min(8, round(valor / 255 * 8)))


def _feedback_oficial(forcas_por_zona: dict[int, int]) -> TriggerEffect:
    """Modo `FEEDBACK` (0x21) com zonas e forças no formato do firmware."""
    zonas = _bitmask_de_zonas(z for z, f in forcas_por_zona.items() if f > 0)
    return TriggerEffect(
        mode=TriggerMode.FEEDBACK,
        forces=_forces_oficiais(zonas, _forcas_em_tres_bits(forcas_por_zona)),
    )


def _vibracao_oficial(
    forcas_por_zona: dict[int, int], frequencia: int
) -> TriggerEffect:
    """Modo `VIBRATION` (0x26) com zonas, amplitudes e frequência."""
    zonas = _bitmask_de_zonas(z for z, f in forcas_por_zona.items() if f > 0)
    return TriggerEffect(
        mode=TriggerMode.VIBRATION,
        forces=_forces_oficiais(
            zonas,
            _forcas_em_tres_bits(forcas_por_zona),
            extra9=_byte(frequencia, name="frequency"),
        ),
    )


def _rampa_de_zonas(
    start: int, end: int, forca_inicial: int, forca_final: int
) -> dict[int, int]:
    """As forças de cada zona entre `start` e `end`, interpoladas linearmente.

    Uma zona só (start == end) recebe a força inicial — sem isto a divisão por
    `end - start` estouraria, e "rampa de um ponto só" é um ponto.
    """
    if end <= start:
        return {start: forca_inicial}
    passo = (forca_final - forca_inicial) / (end - start)
    return {
        zona: max(1, min(8, round(forca_inicial + passo * (zona - start))))
        for zona in range(start, end + 1)
    }


def _byte(value: int, *, name: str, lo: int = 0, hi: int = 255) -> int:
    if not (lo <= value <= hi):
        raise ValueError(f"{name} fora do range {lo}-{hi}: {value}")
    return value


def _amp(value: int, *, name: str) -> int:
    """Converte amplitude nomeada (0-8) para byte HID com clamp em 255.

    Fator 32 expande 0-7 para 0-224; 8 satura em 255 (byte máximo).
    """
    _byte(value, name=name, lo=0, hi=8)
    return min(255, value * AMPLITUDE_SCALE)


def _pos(value: int, *, name: str) -> int:
    return _byte(value, name=name, lo=0, hi=9)


# ---------------------------------------------------------------------------
# Presets nomeados (19 itens conforme docs/protocol/trigger-modes.md)
# ---------------------------------------------------------------------------


def off() -> TriggerEffect:
    return TriggerEffect(mode=TriggerMode.OFF, forces=ZERO7)


def rigid(position: int, force: int) -> TriggerEffect:
    """Barreira rígida a partir de uma posição.

    TRIGGER-CANON-01: mandava `RIGID_B`, que vale `0x05` — o OFF do bloco de
    gatilho. Ela mediu: *"rígido e desligado sem diferença"*. Agora manda o
    `FEEDBACK` oficial (0x21), com as zonas de `position` até o fim marcadas
    no bitmask, que é o que "rígido a partir daqui" significa no firmware.

    A `force` continua chegando como byte 0-255 (é o que a tela mostra e o
    que os perfis dela guardam) e é convertida para a escala de 1 a 8 das
    forças oficiais aqui dentro — o `name` e a faixa do parâmetro são
    contrato, e não mudam.
    """
    return _feedback_oficial(
        _zonas_a_partir_de(
            _pos(position, name="position"),
            _forca_de_byte(_byte(force, name="force")),
        )
    )


def simple_rigid(strength: int) -> TriggerEffect:
    """Atalho: rígido em toda a extensão, com força em escala 0-8.

    TRIGGER-CANON-01: mandava `RIGID_B` = `0x05` = OFF, como o `rigid`. Agora
    é o `FEEDBACK` oficial com TODAS as dez zonas ativas — que é o que "rígido
    simples" quer dizer: firmeza uniforme do começo ao fim do curso.
    """
    _byte(strength, name="strength", lo=0, hi=8)
    return _feedback_oficial(_zonas_a_partir_de(0, strength))


def pulse() -> TriggerEffect:
    return TriggerEffect(mode=TriggerMode.PULSE, forces=ZERO7)


def pulse_a(start: int, end: int, force: int) -> TriggerEffect:
    _check_start_end(start, end)
    s = _pos(start, name="start")
    e = _pos(end, name="end")
    f = _byte(force, name="force")
    return TriggerEffect(mode=TriggerMode.PULSE_A, forces=(s, e, f, 0, 0, 0, 0))


def pulse_b(start: int, end: int, force: int) -> TriggerEffect:
    _check_start_end(start, end)
    s = _pos(start, name="start")
    e = _pos(end, name="end")
    f = _byte(force, name="force")
    return TriggerEffect(mode=TriggerMode.PULSE_B, forces=(s, e, f, 0, 0, 0, 0))


def resistance(start: int, force: int) -> TriggerEffect:
    """Resistência constante a partir de uma posição.

    TRIGGER-CANON-01: mandava `RIGID_AB` = `0x25`, que é o **Weapon
    oficial** — o número do modo estava até certo para um "arma", mas os
    parâmetros não. Ela mediu: *"resistência nada também"*. É essa medição que
    prova que o defeito do empacotamento é INDEPENDENTE do defeito do modo:
    com o modo oficial certo e sem bitmask, o firmware vê zero zonas ativas e
    não faz nada.

    Semanticamente isto é feedback, não arma: resistência constante do ponto
    `start` até o fim do curso.
    """
    return _feedback_oficial(
        _zonas_a_partir_de(
            _pos(start, name="start"), _byte(force, name="force", lo=0, hi=8)
        )
    )


def bow(start: int, end: int, force: int, snap: int) -> TriggerEffect:
    """Simula arco: tensão crescente entre `start` e `end`, `snap` ao soltar."""
    _byte(start, name="start", lo=0, hi=8)
    _byte(end, name="end", lo=1, hi=9)
    if end <= start:
        raise ValueError(f"bow: end ({end}) deve ser > start ({start})")
    return TriggerEffect(
        mode=TriggerMode.PULSE_AB,
        forces=(start, end, _amp(force, name="force"), _amp(snap, name="snap"), 0, 0, 0),
    )


def galloping(
    start: int, end: int, first_foot: int, second_foot: int, frequency: int
) -> TriggerEffect:
    """Cadência de galope (5 params canônicos; HID usa 7 forces)."""
    _byte(start, name="start", lo=0, hi=8)
    _byte(end, name="end", lo=1, hi=9)
    if end <= start:
        raise ValueError(f"galloping: end ({end}) deve ser > start ({start})")
    _byte(first_foot, name="first_foot", lo=0, hi=7)
    _byte(second_foot, name="second_foot", lo=0, hi=7)
    _byte(frequency, name="frequency")
    return TriggerEffect(
        mode=TriggerMode.PULSE_AB,
        forces=(start, end, first_foot, second_foot, frequency, 0, 0),
    )


def semi_auto_gun(start: int, end: int, force: int) -> TriggerEffect:
    _byte(start, name="start", lo=2, hi=7)
    _byte(end, name="end", lo=start + 1, hi=8)
    return TriggerEffect(
        mode=TriggerMode.PULSE_AB,
        forces=(start, end, _amp(force, name="force"), 0, 0, 0, 0),
    )


def auto_gun(start: int, strength: int, frequency: int) -> TriggerEffect:
    return TriggerEffect(
        mode=TriggerMode.PULSE_AB,
        forces=(
            _pos(start, name="start"),
            _amp(strength, name="strength"),
            _byte(frequency, name="frequency"),
            0,
            0,
            0,
            0,
        ),
    )


def machine(
    start: int, end: int, amp_a: int, amp_b: int, frequency: int, period: int
) -> TriggerEffect:
    """Machine gun style. 6 params nomeados, HID usa 7 forces (última zero)."""
    _check_start_end(start, end)
    return TriggerEffect(
        mode=TriggerMode.PULSE_AB,
        forces=(
            start,
            end,
            _byte(amp_a, name="amp_a"),
            _byte(amp_b, name="amp_b"),
            _byte(frequency, name="frequency"),
            _byte(period, name="period"),
            0,
        ),
    )


def feedback(position: int, strength: int) -> TriggerEffect:
    """O `Feedback` OFICIAL da Sony: resistência a partir de uma posição.

    TRIGGER-CANON-01: este é o preset cujo nome sempre foi o certo e cujo
    modo sempre foi o errado — ele mandava `0x05` (OFF) e o modo que leva
    exatamente este nome na enum da Sony é o `0x21`.
    """
    _byte(strength, name="strength", lo=0, hi=8)
    return _feedback_oficial(
        _zonas_a_partir_de(_pos(position, name="position"), strength)
    )


def weapon(start: int, end: int, force: int) -> TriggerEffect:
    _check_start_end(start, end)
    return TriggerEffect(
        mode=TriggerMode.PULSE_B,
        forces=(start, end, _byte(force, name="force"), 0, 0, 0, 0),
    )


def vibration(position: int, amplitude: int, frequency: int) -> TriggerEffect:
    return TriggerEffect(
        mode=TriggerMode.PULSE_A,
        forces=(
            _pos(position, name="position"),
            _amp(amplitude, name="amplitude"),
            _byte(frequency, name="frequency"),
            0,
            0,
            0,
            0,
        ),
    )


def slope_feedback(
    start: int, end: int, start_strength: int, end_strength: int
) -> TriggerEffect:
    """Firmeza que varia em RAMPA entre duas posições.

    TRIGGER-CANON-01: mandava `RIGID_AB` = `0x25` com posições cruas, e não
    fazia nada — mesma causa do `resistance`. A enum da Sony chama isto de
    `SLOPE_FEEDBACK` e **ele não tem byte de modo próprio**: é o `Feedback`
    (0x21) com o array de zonas preenchido em rampa. Foi essa descoberta que
    fechou a conta dos sete modos da enum contra os bytes do fio.
    """
    _check_start_end(start, end)
    _byte(start_strength, name="start_strength", lo=1, hi=8)
    _byte(end_strength, name="end_strength", lo=1, hi=8)
    return _feedback_oficial(
        _rampa_de_zonas(start, end, start_strength, end_strength)
    )


def multi_position_feedback(strengths: list[int]) -> TriggerEffect:
    """Força por posição (array de 10) — a curva de força inteira.

    TRIGGER-CANON-01. Duas coisas mudaram, e a segunda refuta um bug
    registrado como medido:

    1. o modo era `0x25` (Weapon) e passa a ser o `FEEDBACK` oficial (0x21).
       `MultiPositionFeedback` também não tem byte próprio na enum da Sony —
       é o Feedback com o array de zonas;
    2. **os oito níveis de força SÃO expressáveis.** O
       `BUG-TRIGGER-MULTIPOS-FORCA8-01` concluiu *"o campo tem 3 bits, logo o
       máximo real é 7 e a força 8 satura"*. A codificação real é
       `(força - 1) & 0x07` com força em 1..8: o que NÃO cabe nos três bits é
       o zero, e o zero não é um nível de força — é zona inativa, e isso se
       diz no bitmask. Ver `_forcas_em_tres_bits`.
    """
    if len(strengths) != 10:
        raise ValueError(
            f"multi_position_feedback: precisa 10 strengths, recebeu {len(strengths)}"
        )
    for idx, s in enumerate(strengths):
        _byte(s, name=f"strengths[{idx}]", lo=0, hi=8)
    return _feedback_oficial(dict(enumerate(strengths)))


def multi_position_vibration(frequency: int, strengths: list[int]) -> TriggerEffect:
    """Amplitude por posição (array de 10) + frequência.

    TRIGGER-CANON-01: mandava `PULSE_A` = `0x22`, que é o **Bow** — e com a
    frequência no slot errado. Agora manda o `VIBRATION` oficial (0x26), com
    as amplitudes no array de zonas e a frequência no byte 9 do bloco, que é
    onde ela mora e onde `forces[6]` cai.
    """
    if len(strengths) != 10:
        raise ValueError(
            f"multi_position_vibration: precisa 10 strengths, recebeu {len(strengths)}"
        )
    for idx, s in enumerate(strengths):
        _byte(s, name=f"strengths[{idx}]", lo=0, hi=8)
    return _vibracao_oficial(
        dict(enumerate(strengths)), _byte(frequency, name="frequency")
    )


def custom(mode: int, forces: tuple[int, ...]) -> TriggerEffect:
    """Escape hatch: envia mode + forces cru. Útil para experimentação.

    TRIGGER-CANON-01: recusa os modos de DEPURAÇÃO (`0xFC`-`0xFE`). Eles
    corrompem o estado do gatilho, e só sair dele desligando o controle — e
    este era o caminho por onde eles estavam alcançáveis, já que o
    `CALIBRATION = 0xFC` era membro público da enum.

    A recusa é um `ValueError`, e não um clamp: quem passou `0xFC` passou de
    propósito, e trocar o valor em silêncio seria mentir sobre o que foi
    enviado ao controle.
    """
    if mode in MODOS_DE_DEPURACAO:
        raise ValueError(
            f"modo 0x{mode:02X} é de depuração do firmware e corrompe o "
            "estado do gatilho — o controle só volta ao normal desligando"
        )
    if len(forces) != 7:
        raise ValueError(f"custom: forces precisa 7 elementos, recebeu {len(forces)}")
    fixed: tuple[int, int, int, int, int, int, int] = (
        forces[0], forces[1], forces[2], forces[3], forces[4], forces[5], forces[6]
    )
    return TriggerEffect(mode=mode, forces=fixed)


# ---------------------------------------------------------------------------
# Helpers internos
# ---------------------------------------------------------------------------


def _check_start_end(start: int, end: int) -> None:
    _pos(start, name="start")
    _pos(end, name="end")
    if end <= start:
        raise ValueError(f"end ({end}) deve ser > start ({start})")


def _flatten_multi_position(nested: list[list[int]]) -> list[int]:
    """Achata params aninhado em lista de 10 strengths para multi_position_*.

    Aceita três dimensões canônicas:

    - **10 sublistas** (1:1): cada `[v]` vira uma posição — se a sublista tem
      mais de um valor, usa o primeiro e descarta o restante. Uso típico:
      `[[0],[1],[2],[3],[4],[5],[6],[7],[8],[8]]`.
    - **5 sublistas** (2 posições por zona): cada `[a, b]` expande para
      duas posições consecutivas (a, b). Espera `len(item) == 2` em cada
      sublista; erro se diferente.
    - **2 sublistas** (5 posições por zona): primeira sublista define 5
      posições iniciais, segunda define 5 finais. Espera `len(item) == 5`.

    Qualquer outra dimensão levanta `ValueError`. Os valores finais devem
    caber em 0-8 (range canônico do DualSense para multi-position).
    """
    n = len(nested)
    if n == 10:
        flat: list[int] = []
        for idx, sub in enumerate(nested):
            if not sub:
                raise ValueError(
                    f"_flatten_multi_position(10): sublista [{idx}] vazia"
                )
            flat.append(int(sub[0]))
        return flat
    if n == 5:
        flat = []
        for idx, sub in enumerate(nested):
            if len(sub) != 2:
                raise ValueError(
                    f"_flatten_multi_position(5): sublista [{idx}] "
                    f"precisa exatamente 2 valores, recebeu {len(sub)}"
                )
            flat.extend(int(v) for v in sub)
        return flat
    if n == 2:
        flat = []
        for idx, sub in enumerate(nested):
            if len(sub) != 5:
                raise ValueError(
                    f"_flatten_multi_position(2): sublista [{idx}] "
                    f"precisa exatamente 5 valores, recebeu {len(sub)}"
                )
            flat.extend(int(v) for v in sub)
        return flat
    raise ValueError(
        f"_flatten_multi_position: dimensão {n} não suportada "
        "(esperado 2, 5 ou 10 sublistas)"
    )


# ---------------------------------------------------------------------------
# Registry de presets por nome (CLI e perfis JSON referenciam por string).
# ---------------------------------------------------------------------------


PRESET_FACTORIES = {
    "Off": off,
    "Rigid": rigid,
    "SimpleRigid": simple_rigid,
    "Pulse": pulse,
    "PulseA": pulse_a,
    "PulseB": pulse_b,
    "Resistance": resistance,
    "Bow": bow,
    "Galloping": galloping,
    "SemiAutoGun": semi_auto_gun,
    "AutoGun": auto_gun,
    "Machine": machine,
    "Feedback": feedback,
    "Weapon": weapon,
    "Vibration": vibration,
    "SlopeFeedback": slope_feedback,
    "MultiPositionFeedback": multi_position_feedback,
    "MultiPositionVibration": multi_position_vibration,
    "Custom": custom,
}


def _traduzir_params_nomeados(
    name: str, params: dict[str, int]
) -> dict[str, object]:
    """Traduz os nomes da TELA para os kwargs da factory, onde eles diferem.

    TRIGGER-CANON-01. O `trigger_specs` descreve os controles deslizantes da
    aba Gatilhos, e para os presets por posição ele expõe DEZ controles
    (`pos_0`..`pos_9`) — porque é assim que se ajusta uma curva na tela. As
    factories recebem uma LISTA. O caminho posicional já resolvia isso; o
    nomeado levantava `TypeError`.

    Isto não é conveniência: um perfil salvo com parâmetros nomeados usa este
    caminho, e `Custom`, `MultiPositionFeedback` e `MultiPositionVibration`
    simplesmente não abriam por ele.
    """
    if name in ("MultiPositionFeedback", "MultiPositionVibration"):
        strengths = [int(params[f"pos_{i}"]) for i in range(10) if f"pos_{i}" in params]
        if len(strengths) != 10:
            return dict(params)  # formato já é o da factory (`strengths=[...]`)
        if name == "MultiPositionFeedback":
            return {"strengths": strengths}
        return {"frequency": int(params.get("frequency", 0)), "strengths": strengths}
    if name == "Custom" and "force_0" in params:
        return {
            "mode": int(params.get("mode", 0)),
            "forces": tuple(int(params.get(f"force_{i}", 0)) for i in range(7)),
        }
    return dict(params)


def build_from_name(
    name: str,
    params: list[int] | list[list[int]] | dict[str, int],
) -> TriggerEffect:
    """Resolve preset por nome + params. Aceita posicional (list), nomeado (dict) ou aninhado.

    Formato aninhado (`list[list[int]]`) é canônico para os modos
    `MultiPositionFeedback` e `MultiPositionVibration`: permite expressar
    os 10 strengths em JSON com agrupamento por zona (2/5/10 sublistas).
    Ver `_flatten_multi_position` para a expansão.

    Para `MultiPositionVibration`, `frequency` é implicitamente 0 quando
    o formato aninhado é usado — ajuste fino de frequency exige formato
    dict (`{"frequency": N, "strengths": [...]}`) ou posicional.
    """
    from typing import Any, cast
    factory = cast("Any", PRESET_FACTORIES.get(name))
    if factory is None:
        raise ValueError(f"preset desconhecido: {name}")

    # Detecta formato aninhado e expande para a assinatura correta da factory.
    if (
        isinstance(params, list)
        and params
        and isinstance(params[0], list)
    ):
        # mypy infere `params` como `list[list[int] | Any]` aqui; o
        # isinstance(params[0], list) já garante runtime safe — atribuição
        # via name-binding mantém o tipo concreto sem cast redundante.
        nested: list[list[int]] = params
        if name == "MultiPositionFeedback":
            strengths = _flatten_multi_position(nested)
            result = factory(strengths)
        elif name == "MultiPositionVibration":
            strengths = _flatten_multi_position(nested)
            result = factory(0, strengths)
        else:
            raise ValueError(
                f"params aninhado só é aceito para MultiPositionFeedback "
                f"ou MultiPositionVibration; recebido: {name}"
            )
    elif isinstance(params, dict):
        result = factory(**_traduzir_params_nomeados(name, params))
    elif name == "MultiPositionFeedback":
        # BUG-TRIGGER-FLAT-MULTIPOS-01: lista posicional PLANA de 10 strengths.
        # A factory tem assinatura factory(strengths: list) — não 10 posicionais —
        # então NÃO pode cair em factory(*params). Empacota como uma lista única.
        flat = cast("list[int]", params)
        result = factory([int(x) for x in flat])
    elif name == "MultiPositionVibration" and params:
        # flat posicional [frequency, s0..s9] -> factory(frequency, strengths)
        flat = cast("list[int]", params)
        result = factory(int(flat[0]), [int(x) for x in flat[1:]])
    elif name == "Custom" and params:
        # flat posicional [mode, f0..f6] -> factory(mode, forces)
        flat = cast("list[int]", params)
        result = factory(int(flat[0]), tuple(int(x) for x in flat[1:]))
    else:
        result = factory(*params)
    assert isinstance(result, TriggerEffect)
    return result


__all__ = [
    "AMPLITUDE_SCALE",
    "MULTI_POSITION_MAX_STRENGTH",
    "PRESET_FACTORIES",
    "TriggerMode",
    "auto_gun",
    "bow",
    "build_from_name",
    "custom",
    "feedback",
    "galloping",
    "machine",
    "multi_position_feedback",
    "multi_position_vibration",
    "off",
    "pulse",
    "pulse_a",
    "pulse_b",
    "resistance",
    "rigid",
    "semi_auto_gun",
    "simple_rigid",
    "slope_feedback",
    "vibration",
    "weapon",
]
