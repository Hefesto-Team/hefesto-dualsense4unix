"""Factories dos presets de trigger: os onze da tela e as chaves velhas que seguem lidas."""
from __future__ import annotations

from collections.abc import Iterable, Sequence
from enum import IntEnum

from hefesto_dualsense4unix.core.controller import TriggerEffect
from hefesto_dualsense4unix.utils.logging_config import get_logger

logger = get_logger(__name__)

AMPLITUDE_SCALE = 32

MULTI_POSITION_MAX_STRENGTH = 7

#: A frequência da Vibração por posição quando o perfil não traz a dele (o
#: formato aninhado não tem onde guardá-la): o padrão do controle da tela, o
#: `_frequency(40, lo=1)` de `app/actions/trigger_specs.py`, preso por teste.
FREQUENCIA_PADRAO_DA_VIBRACAO_POR_POSICAO = 40


MODOS_DE_DEPURACAO: frozenset[int] = frozenset({0xFC, 0xFD, 0xFE})


class TriggerMode(IntEnum):
    """Modos do bloco de gatilho, com os nomes da enum OFICIAL da Sony."""

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

#: O bloco de um gatilho no report de saída: o modo e os dez parâmetros.
TAMANHO_DO_BLOCO_DO_GATILHO = 11


def bloco_do_gatilho(modo: int, forcas: Sequence[int]) -> bytes:
    """Os 11 bytes do gatilho no report: o modo, as forças 0 a 5 e a força 6 na nona casa.

    Dono único do bloco: o `_build_common` o escreve no `common[10]` (R2) e no
    `common[21]` (L2), e o servidor DSX o entrega à camada do jogo.
    """
    bloco = bytearray(TAMANHO_DO_BLOCO_DO_GATILHO)
    bloco[0] = int(modo) & 0xFF
    for indice in range(6):
        bloco[1 + indice] = int(forcas[indice]) & 0xFF
    bloco[9] = int(forcas[6]) & 0xFF
    return bytes(bloco)


def bloco_do_efeito(efeito: TriggerEffect) -> bytes:
    """O bloco de 11 bytes que o `efeito` vira no report."""
    return bloco_do_gatilho(int(efeito.mode), efeito.forces)

_ZONAS_DO_GATILHO = 10


def _bitmask_de_zonas(posicoes: Iterable[int]) -> int:
    """Bitmask u16 das zonas ativas: bit N ligado = posição N tem força."""
    total = 0
    for posicao in posicoes:
        total |= 1 << int(posicao)
    return total


def _forcas_em_tres_bits(forcas_por_zona: dict[int, int]) -> int:
    """As forças empacotadas em 3 bits por zona, com valor ``força - 1``."""
    empacotado = 0
    for zona, forca in forcas_por_zona.items():
        if forca <= 0:
            continue
        empacotado |= ((min(8, forca) - 1) & 0x07) << (3 * int(zona))
    return empacotado & 0xFFFFFFFF


def _forces_oficiais(
    zonas: int, forcas: int, *, extra9: int = 0
) -> tuple[int, int, int, int, int, int, int]:
    """Monta os sete slots de `forces` no layout dos modos oficiais."""
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
    """Da posição `inicio` até o fim do curso, todas com a mesma força."""
    if forca <= 0:
        return {}
    return {zona: forca for zona in range(inicio, _ZONAS_DO_GATILHO)}


def _forca_de_byte(valor: int) -> int:
    """Converte a força de byte (0-255, o que a tela do usuário mostra) para 1-8."""
    if valor <= 0:
        return 0
    return max(1, min(8, round(valor / 255 * 8)))


def _no_dominio(valor: int, lo: int, hi: int) -> int:
    """O valor dentro do domínio do modo; o que passa encosta no limite."""
    return max(lo, min(hi, int(valor)))


def _arma_oficial(start: int, end: int, force: int) -> TriggerEffect:
    """A arma oficial (`0x25`): o gatilho resiste entre `start` e `end`, estala
    e rearma sozinho quando o dedo volta para antes do início.

    O bloco leva a máscara `(1<<início)|(1<<fim)` nos bytes 1-2 e a força menos
    um no byte 3. O domínio do modo é o da Sony: início de 2 a 7, fim de
    `início + 1` a 8; a tela deixa mais folga que isso, e o que passa encosta
    no limite, sem recusar. A força chega em byte (0 a 255, o que a tela
    mostra) e vira 1 a 8; zero é sem força, e a arma sem força é o gatilho
    desligado.
    """
    _check_start_end(start, end)
    _byte(force, name="force")
    forca = _forca_de_byte(force)
    if forca <= 0:
        return off()
    inicio = _no_dominio(start, 2, 7)
    fim = _no_dominio(end, inicio + 1, 8)
    return TriggerEffect(
        mode=TriggerMode.WEAPON,
        forces=_forces_oficiais(
            _bitmask_de_zonas((inicio, fim)), forca - 1
        ),
    )


def _arco_do_firmware(start: int, end: int, force: int, snap: int) -> TriggerEffect:
    """O arco do firmware (`0x22`, vivo mas fora da lista oficial): tensão entre
    `start` e `end` e o estalo ao soltar.

    A máscara `(1<<início)|(1<<fim)` vai nos bytes 1-2, e a força menos um mais
    o estalo menos um, deslocado três bits, nos bytes 3-4. O domínio é o do
    arco no gerador do Nielk1: fim de `início + 1` a 8 (o arco não tem a zona
    9, que o galope tem), logo início de 0 a 7; o que passa encosta no limite.
    Força ou estalo zero deixa o gatilho desligado.
    """
    if force <= 0 or snap <= 0:
        return off()
    inicio = _no_dominio(start, 0, 7)
    fim = _no_dominio(end, inicio + 1, 8)
    forca = _no_dominio(force, 1, 8)
    estalo = _no_dominio(snap, 1, 8)
    return TriggerEffect(
        mode=TriggerMode.BOW,
        forces=_forces_oficiais(
            _bitmask_de_zonas((inicio, fim)),
            (forca - 1) | ((estalo - 1) << 3),
        ),
    )


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
    """As forças de cada zona da rampa: interpoladas de `start` a `end`, e da
    zona seguinte ao fim até a última do curso, a força final.

    Parar em `end` deixava o fundo do curso sem força (um degrau mole no fim);
    o gerador público do firmware e o KytyPS5 enchem as zonas depois do fim com
    a força final.
    """
    if end <= start:
        return {start: forca_inicial}
    passo = (forca_final - forca_inicial) / (end - start)
    zonas = {
        zona: max(1, min(8, round(forca_inicial + passo * (zona - start))))
        for zona in range(start, end + 1)
    }
    zonas.update(
        {zona: zonas[end] for zona in range(end + 1, _ZONAS_DO_GATILHO)}
    )
    return zonas


def _byte(value: int, *, name: str, lo: int = 0, hi: int = 255) -> int:
    if not (lo <= value <= hi):
        raise ValueError(f"{name} fora do range {lo}-{hi}: {value}")
    return value


def _amp(value: int, *, name: str) -> int:
    """Converte amplitude nomeada (0-8) para byte HID com clamp em 255."""
    _byte(value, name=name, lo=0, hi=8)
    return min(255, value * AMPLITUDE_SCALE)


def _pos(value: int, *, name: str) -> int:
    return _byte(value, name=name, lo=0, hi=9)


def off() -> TriggerEffect:
    return TriggerEffect(mode=TriggerMode.OFF, forces=ZERO7)


def rigid(position: int, force: int) -> TriggerEffect:
    """Barreira rígida a partir de uma posição."""
    return _feedback_oficial(
        _zonas_a_partir_de(
            _pos(position, name="position"),
            _forca_de_byte(_byte(force, name="force")),
        )
    )


def simple_rigid(strength: int) -> TriggerEffect:
    """Atalho: rígido em toda a extensão, com força em escala 0-8."""
    _byte(strength, name="strength", lo=0, hi=8)
    return _feedback_oficial(_zonas_a_partir_de(0, strength))


def pulse() -> TriggerEffect:
    return TriggerEffect(mode=TriggerMode.PULSE, forces=ZERO7)


def pulse_a(start: int, end: int, force: int) -> TriggerEffect:
    """O Pulso (curva A): o arco do firmware (`0x22`) entre `start` e `end`,
    com o estalo da mesma força. A força chega em byte (0 a 255) e vira 1 a 8."""
    _check_start_end(start, end)
    forca = _forca_de_byte(_byte(force, name="force"))
    return _arco_do_firmware(start, end, forca, forca)


def pulse_b(start: int, end: int, force: int) -> TriggerEffect:
    """O Pulso (curva B): a arma oficial (`0x25`) entre `start` e `end`, o
    mesmo bloco do Disparo (ver `_arma_oficial`)."""
    return _arma_oficial(start, end, force)


def resistance(start: int, force: int) -> TriggerEffect:
    """Resistência constante a partir de uma posição."""
    return _feedback_oficial(
        _zonas_a_partir_de(
            _pos(start, name="start"), _byte(force, name="force", lo=0, hi=8)
        )
    )


def bow(start: int, end: int, force: int, snap: int) -> TriggerEffect:
    """Simula arco: tensão crescente entre `start` e `end`, `snap` ao soltar.

    Os bytes de 01/08 (a mão do usuário aprovou), mantidos até a sessão às cegas de
    `O-ARCO-E-O-GALOPE-MANDAM-O-MODO-QUE-O-CONTROLE-LE-01`; o bloco do modo
    próprio (`0x22`) é o do `pulse_a`.
    """
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
    """Cadência de galope (5 params canônicos; HID usa 7 forces).

    Os bytes de 01/08 (a mão do usuário aprovou), mantidos até a sessão às cegas de
    `O-ARCO-E-O-GALOPE-MANDAM-O-MODO-QUE-O-CONTROLE-LE-01`. Neste layout a
    frequência cai nos bytes de amplitude do `0x26`, e o byte de frequência
    do modo fica em zero: ela é inerte.
    """
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
    """Os bytes de 01/08 (a mão do usuário aprovou), mantidos até a sessão às cegas de
    `O-DISPARO-E-A-ARMA-SEMI-AUTOMATICA-MANDAM-O-MODO-DE-ARMA-01`; a arma
    oficial (`0x25`) é o bloco do `weapon`."""
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


def _encostar(valor: int, lo: int, hi: int) -> int:
    """O valor dentro da faixa: o que passa dela encosta no limite mais perto."""
    return max(lo, min(hi, int(valor)))


def machine(start: int, end: int, strength: int, frequency: int) -> TriggerEffect:
    """A Metralhadora: a vibração da lista oficial (`0x26`), que bate enquanto
    o dedo aperta.

    Do início ao fim do curso (as duas pontas incluídas), todas as zonas levam
    a mesma força (1 a 8), e a frequência vai no byte que o controle lê, em
    batidas por segundo (1 a 255; zero é desligado para o controle). O bloco
    é o mesmo da Vibração por posição com as zonas todas iguais.

    Valor fora da faixa encosta no limite mais perto, sem recusar: é o que um
    perfil escrito antes da faixa nova pode trazer. Fim que não passa do início
    vira o início mais um.
    """
    inicio, fim, forca, frequencia = _metralhadora_na_faixa(
        start, end, strength, frequency
    )
    zonas = {zona: forca for zona in range(inicio, fim + 1)}
    return _vibracao_oficial(zonas, frequencia)


def _metralhadora_na_faixa(
    start: int, end: int, strength: int, frequency: int
) -> tuple[int, int, int, int]:
    """Os quatro ajustes da Metralhadora como o efeito os manda: cada um na
    faixa dele, e o fim sempre depois do início."""
    inicio = _encostar(start, 0, 8)
    fim = _encostar(end, 1, 9)
    if fim <= inicio:
        fim = inicio + 1
    return inicio, fim, _encostar(strength, 1, 8), _encostar(frequency, 1, 255)


def feedback(position: int, strength: int) -> TriggerEffect:
    """O `Feedback` OFICIAL da Sony: resistência a partir de uma posição."""
    _byte(strength, name="strength", lo=0, hi=8)
    return _feedback_oficial(
        _zonas_a_partir_de(_pos(position, name="position"), strength)
    )


def weapon(start: int, end: int, force: int) -> TriggerEffect:
    """O Disparo: a arma oficial (`0x25`), que resiste, estala e rearma sozinha."""
    return _arma_oficial(start, end, force)


def vibration(position: int, amplitude: int, frequency: int) -> TriggerEffect:
    """A Vibração: o gatilho treme da `position` ao fim do curso, no modo oficial
    da vibração (`0x26`), o mesmo da Metralhadora.

    Amplitude 0 ou frequência 0 apaga o gatilho. Saía no `0x22`, que é o modo do
    Arco, e por isso a vibração pedida chegava ao controle como outro efeito.
    """
    _pos(position, name="position")
    _byte(amplitude, name="amplitude", lo=0, hi=8)
    _byte(frequency, name="frequency")
    if amplitude <= 0 or frequency <= 0:
        return off()
    return machine(position, 9, amplitude, frequency)


def slope_feedback(
    start: int, end: int, start_strength: int, end_strength: int
) -> TriggerEffect:
    """Firmeza que varia em RAMPA entre duas posições."""
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

    Frequência 0 com alguma amplitude maior que zero recusa: o controle lê o
    bloco como desligado, e quem pediu a vibração ficaria sem ela calado.
    """
    if len(strengths) != 10:
        raise ValueError(
            f"multi_position_vibration: precisa 10 strengths, recebeu {len(strengths)}"
        )
    for idx, s in enumerate(strengths):
        _byte(s, name=f"strengths[{idx}]", lo=0, hi=8)
    _byte(frequency, name="frequency")
    if frequency == 0 and any(s > 0 for s in strengths):
        raise ValueError(
            "multi_position_vibration: frequency 0 com amplitude maior que zero, "
            "que o controle lê como desligado"
        )
    return _vibracao_oficial(dict(enumerate(strengths)), frequency)


def custom(mode: int, forces: tuple[int, ...]) -> TriggerEffect:
    """Escape hatch: envia mode + forces cru. Útil para experimentação."""
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


#: Os seis valores que a Metralhadora guardava antes de 08/10/2026, na ordem:
#: início, fim, amplitude A, amplitude B, frequência e período.
_SEIS_DA_METRALHADORA_ANTIGA = 6


def _metralhadora_de_seis(valores: list[int]) -> list[int]:
    """Início, fim, força e frequência a partir dos seis valores antigos.

    A amplitude A vira a força e a frequência fica onde estava; a amplitude B
    e o período não têm lugar no efeito oficial e saem. Perfil gravado, mod do
    DSX e linha de comando continuam abrindo a Metralhadora.
    """
    return [valores[0], valores[1], valores[2], valores[4]]


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
            return dict(params)
        if name == "MultiPositionFeedback":
            return {"strengths": strengths}
        return {
            "frequency": int(
                params.get("frequency", FREQUENCIA_PADRAO_DA_VIBRACAO_POR_POSICAO)
            ),
            "strengths": strengths,
        }
    if name == "Machine" and "amp_a" in params:
        antigo = [int(params.get(k, 0)) for k in
                  ("start", "end", "amp_a", "amp_b", "frequency", "period")]
        inicio, fim, forca, frequencia = _metralhadora_de_seis(antigo)
        return {"start": inicio, "end": fim, "strength": forca, "frequency": frequencia}
    if name == "Custom" and "force_0" in params:
        return {
            "mode": int(params.get("mode", 0)),
            "forces": tuple(int(params.get(f"force_{i}", 0)) for i in range(7)),
        }
    return dict(params)


#: As frequências que o relógio de 1 kHz do gatilho entrega exatas acima de
#: 33 Hz: as que dividem 1000 [comunidade]. Até 33 Hz qualquer valor serve.
FREQUENCIAS_LIMPAS_ACIMA_DE_33_HZ: tuple[int, ...] = (40, 50, 100, 125, 200, 250)

_LIMITE_DAS_FREQUENCIAS_LIVRES = 33


def frequencia_limpa(frequencia: int) -> int:
    """A frequência no divisor limpo mais próximo (60 vira 50; no empate, a menor)."""
    if frequencia <= _LIMITE_DAS_FREQUENCIAS_LIVRES:
        return max(1, int(frequencia))
    return min(
        FREQUENCIAS_LIMPAS_ACIMA_DE_33_HZ,
        key=lambda limpa: (abs(limpa - int(frequencia)), limpa),
    )


#: O padrão do Disparo da tela (início, fim, força em byte), para onde vai o `Pulse`.
_DISPARO_PADRAO: tuple[int, int, int] = (2, 5, 200)

#: Os nomes e os padrões dos ajustes das chaves que saíram da lista de onze, na
#: ordem em que o perfil antigo os guardava. É o que lê um perfil gravado com
#: ajustes nomeados.
_AJUSTES_DAS_CHAVES_VELHAS: dict[str, tuple[tuple[str, int], ...]] = {
    "Rigid": (("position", 5), ("force", 200)),
    "SimpleRigid": (("strength", 6),),
    "Feedback": (("position", 5), ("strength", 4)),
    "Pulse": (),
    "PulseA": (("start", 2), ("end", 7), ("force", 180)),
    "PulseB": (("start", 2), ("end", 7), ("force", 180)),
    "SemiAutoGun": (("start", 3), ("end", 6), ("force", 5)),
    "AutoGun": (("start", 2), ("strength", 6), ("frequency", 60)),
}


def _de_rigid(p: list[int]) -> tuple[str, list[int]]:
    """Rígido: a Resistência com início na posição, a força de byte em 0 a 8."""
    return "Resistance", [p[0], _forca_de_byte(_byte(p[1], name="force"))]


def _de_rigido_simples(p: list[int]) -> tuple[str, list[int]]:
    """Rígido simples: a Resistência com início 0."""
    return "Resistance", [0, _byte(p[0], name="strength", lo=0, hi=8)]


def _de_ponto_duro(p: list[int]) -> tuple[str, list[int]]:
    """Ponto duro (`Feedback`): a Resistência com início na posição."""
    return "Resistance", [p[0], _byte(p[1], name="strength", lo=0, hi=8)]


def _de_pulso_b(p: list[int]) -> tuple[str, list[int]]:
    """Pulso (curva B): o Disparo, com os mesmos três ajustes."""
    return "Weapon", [p[0], p[1], p[2]]


def _de_semi_automatica(p: list[int]) -> tuple[str, list[int]]:
    """Arma semi-automática: o Disparo, com a força de 0 a 8 posta em byte."""
    inicio = _byte(p[0], name="start", lo=2, hi=7)
    fim = _byte(p[1], name="end", lo=inicio + 1, hi=8)
    forca = _byte(p[2], name="force", lo=0, hi=8)
    return "Weapon", [inicio, fim, min(255, round(forca * 255 / 8))]


def _de_automatica(p: list[int]) -> tuple[str, list[int]]:
    """Arma automática: a Metralhadora do início ao fim do curso, na frequência limpa.

    Força 0 ou frequência 0 deixavam o gatilho calado, e a tradução o deixa desligado.
    """
    inicio = _pos(p[0], name="start")
    forca = _byte(p[1], name="strength", lo=0, hi=8)
    frequencia = _byte(p[2], name="frequency")
    if forca <= 0 or frequencia <= 0:
        return "Off", []
    return "Machine", [inicio, 9, forca, frequencia_limpa(frequencia)]


def _de_pulso(p: list[int]) -> tuple[str, list[int]]:
    """Pulso (modo legado `0x02`): o Disparo no padrão."""
    return "Weapon", list(_DISPARO_PADRAO)


def _de_pulso_a_para_a_tela(p: list[int]) -> tuple[str, list[int]]:
    """Pulso (curva A) como a tela o mostra: o Arco, com a força nos dois ajustes.

    SÓ PARA A TELA. O byte segue o `_arco_do_firmware` (`0x22`) até a sessão do Arco.
    """
    forca = _forca_de_byte(_byte(p[2], name="force"))
    return "Bow", [
        _encostar(p[0], 0, 8), _encostar(max(p[1], p[0] + 1), 1, 9), forca, forca,
    ]


#: A tabela fechada: a chave velha → o acionamento da lista de onze, com os ajustes
#: dele. Perfil gravado com uma chave velha abre pela linha nova, nos quatro
#: controles e nas duas conexões, porque quem monta o bloco é o `build_from_name`.
#: `PulseA` NÃO está aqui: a chave segue dando o bloco `0x22` de hoje.
TRADUCAO_DAS_CHAVES_VELHAS = {
    "Rigid": _de_rigid,
    "SimpleRigid": _de_rigido_simples,
    "Feedback": _de_ponto_duro,
    "PulseB": _de_pulso_b,
    "SemiAutoGun": _de_semi_automatica,
    "AutoGun": _de_automatica,
    "Pulse": _de_pulso,
}


def traduzir_chave_velha(
    name: str,
    params: object,
    *,
    para_a_tela: bool = False,
) -> tuple[str, list[int]] | None:
    """A linha nova de uma chave velha: `(chave, ajustes posicionais)`, ou `None`.

    `None` quando a chave não saiu da lista, ou quando os ajustes não são os
    dela (a quantidade errada segue recusada pela fábrica velha, como sempre).
    Os ajustes nomeados (`dict`) entram na ordem do perfil antigo. Com
    `para_a_tela`, o `PulseA` também sobe para o Arco, só para a tela o mostrar;
    o bloco que sai dele não muda.
    """
    ordem = _AJUSTES_DAS_CHAVES_VELHAS.get(name)
    if ordem is None:
        return None
    if isinstance(params, dict):
        if set(params) != {nome for nome, _ in ordem}:
            return None
        valores = [int(params[nome]) for nome, _ in ordem]
    elif isinstance(params, (list, tuple)) and all(
        isinstance(v, int) and not isinstance(v, bool) for v in params
    ):
        valores = [int(v) for v in params]
    else:
        return None
    if len(valores) != len(ordem):
        return None
    if name == "PulseA":
        return _de_pulso_a_para_a_tela(valores) if para_a_tela else None
    return TRADUCAO_DAS_CHAVES_VELHAS[name](valores)


def build_from_name(
    name: str,
    params: list[int] | list[list[int]] | dict[str, int],
) -> TriggerEffect:
    """Resolve preset por nome + params. Aceita posicional (list), nomeado (dict) ou aninhado.

    Formato aninhado (`list[list[int]]`) é canônico para os modos
    `MultiPositionFeedback` e `MultiPositionVibration`: permite expressar
    os 10 strengths em JSON com agrupamento por zona (2/5/10 sublistas).
    Ver `_flatten_multi_position` para a expansão.

    Para `MultiPositionVibration`, o formato aninhado não tem onde guardar a
    `frequency`: ela sai como `FREQUENCIA_PADRAO_DA_VIBRACAO_POR_POSICAO`
    (40, o padrão da tela). Frequência própria exige o formato dict
    (`{"frequency": N, "strengths": [...]}`) ou o posicional.
    """
    from typing import Any, cast
    if name not in PRESET_FACTORIES:
        raise ValueError(f"preset desconhecido: {name}")
    traduzida = traduzir_chave_velha(name, params)
    if traduzida is not None:
        name, params = traduzida
    factory = cast("Any", PRESET_FACTORIES.get(name))

    if (
        isinstance(params, list)
        and params
        and isinstance(params[0], list)
    ):
        nested: list[list[int]] = params
        if name == "MultiPositionFeedback":
            strengths = _flatten_multi_position(nested)
            result = factory(strengths)
        elif name == "MultiPositionVibration":
            strengths = _flatten_multi_position(nested)
            result = factory(FREQUENCIA_PADRAO_DA_VIBRACAO_POR_POSICAO, strengths)
        else:
            raise ValueError(
                f"params aninhado só é aceito para MultiPositionFeedback "
                f"ou MultiPositionVibration; recebido: {name}"
            )
    elif isinstance(params, dict):
        result = factory(**_traduzir_params_nomeados(name, params))
    elif name == "MultiPositionFeedback":
        flat = cast("list[int]", params)
        result = factory([int(x) for x in flat])
    elif name == "MultiPositionVibration" and params:
        flat = cast("list[int]", params)
        result = factory(int(flat[0]), [int(x) for x in flat[1:]])
    elif name == "Custom" and params:
        flat = cast("list[int]", params)
        result = factory(int(flat[0]), tuple(int(x) for x in flat[1:]))
    elif name == "Machine" and len(params) == _SEIS_DA_METRALHADORA_ANTIGA:
        flat = cast("list[int]", params)
        result = factory(*_metralhadora_de_seis([int(x) for x in flat]))
    else:
        result = factory(*params)
    assert isinstance(result, TriggerEffect)
    return result


__all__ = [
    "AMPLITUDE_SCALE",
    "FREQUENCIAS_LIMPAS_ACIMA_DE_33_HZ",
    "FREQUENCIA_PADRAO_DA_VIBRACAO_POR_POSICAO",
    "MULTI_POSITION_MAX_STRENGTH",
    "PRESET_FACTORIES",
    "TAMANHO_DO_BLOCO_DO_GATILHO",
    "TRADUCAO_DAS_CHAVES_VELHAS",
    "TriggerMode",
    "auto_gun",
    "bloco_do_efeito",
    "bloco_do_gatilho",
    "bow",
    "build_from_name",
    "custom",
    "feedback",
    "frequencia_limpa",
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
    "traduzir_chave_velha",
    "vibration",
    "weapon",
]
