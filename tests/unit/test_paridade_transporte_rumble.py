"""PARIDADE-BYTE-01 — os dois motores, nos dois transportes.

O rumble por BT foi **no-op durante meses** e ninguém viu: o report 0x31 que a
pydualsense 0.7.5 monta é malformado (off-by-one no envelope) e o firmware o
descarta inteiro. O BTREPORT-02 curou o envelope; o que continuava sem prova era
o andar de cima — que os bytes dos MOTORES e os bits que os autorizam saem
iguais no cabo e no rádio.

Três afirmações do produto vivem aqui, e nenhuma delas era checada nos dois
transportes:

- os motores caem em common[2] (direito/fraco) e common[3] (esquerdo/forte);
- **GUERRA-01 item 2**, o keepalive neutro: sem rumble NOSSO ativo, os bits de
  vibração saem DESLIGADOS (flag0 0x01|0x02, flag1 0x40, flag2 0x04) — senão o
  keepalive a 2 Hz zera o rumble de um jogo que escreve direto no hidraw;
- e a transição ativa→0 manda **um** report com os flags ligados e os motores em
  zero, para o firmware parar o motor de verdade.

ACHADO DE 11/08/2026, ao escrever esta camada: o bit `flag2 0x04`
(`COMPATIBLE_VIBRATION2`) **nunca é ligado por este projeto**, em transporte
nenhum — o `_build_common` só sabe DESLIGÁ-LO. Está registrado em
`test_o_bit_de_vibracao_v2_e_o_mesmo_nos_dois_transportes`, que trava a
PARIDADE do bit e não o valor de hoje: petrificar uma ausência seria pior que
não medi-la.

MORDIDA PROVADA (11/08/2026, `src/` copiado para fora da árvore, `PYTHONPATH`
apontado para a cópia — a árvore de trabalho nunca foi mutada): zerando
`common[2:4]` só quando `conType == BT`, este arquivo reprova **5**, quatro com
o id `[bt]` e o caso que compara os dois lados. Os `[usb]` seguem verdes.
"""
from __future__ import annotations

from typing import Any

import pytest

from hefesto_dualsense4unix.core import ds_output_report as rep

from tests.conftest import EnvelopeDeTransporte

#: Offsets dos motores dentro do common.
MOTOR_DIREITO, MOTOR_ESQUERDO = 2, 3

#: Pares (fraco/direito, forte/esquerdo) distinguíveis entre si — um par
#: simétrico passaria com os dois motores trocados e não provaria nada.
PARES_DE_MOTOR = [
    (0xFF, 0x00),
    (0x00, 0xFF),
    (0x20, 0xC0),
    (0x7F, 0x01),
]


def _bits_de_vibracao(common: bytes) -> tuple[int, int, int]:
    """Os três bits que autorizam o firmware a adotar os motores."""
    return (
        common[0] & (rep.VALID_FLAG0_COMPATIBLE_VIBRATION | rep.VALID_FLAG0_HAPTICS_SELECT),
        common[1] & rep.VALID_FLAG1_MOTOR_POWER,
        common[rep.COMMON_VALID_FLAG2] & rep.VALID_FLAG2_COMPATIBLE_VIBRATION2,
    )


@pytest.mark.parametrize(("fraco", "forte"), PARES_DE_MOTOR)
def test_os_dois_motores_saem_nos_bytes_certos_nos_dois_transportes(
    ds5_de_bancada: Any, transporte: EnvelopeDeTransporte, fraco: int, forte: int
) -> None:
    """common[2] é o motor direito (fraco), common[3] o esquerdo (forte)."""
    ds5_de_bancada.setRightMotor(fraco)
    ds5_de_bancada.setLeftMotor(forte)

    report = ds5_de_bancada.prepareReport()
    assert transporte.problemas_do_envelope(report) == []
    common = transporte.extrair_common(report)

    assert common[MOTOR_DIREITO] == fraco, (
        f"{transporte.nome}: o motor DIREITO saiu {common[MOTOR_DIREITO]} em "
        f"common[2], esperado {fraco}"
    )
    assert common[MOTOR_ESQUERDO] == forte, (
        f"{transporte.nome}: o motor ESQUERDO saiu {common[MOTOR_ESQUERDO]} em "
        f"common[3], esperado {forte}"
    )


def test_com_rumble_nosso_os_bits_de_vibracao_ligam_nos_dois(
    ds5_de_bancada: Any, transporte: EnvelopeDeTransporte
) -> None:
    """Motor escrito sem bit de validação é motor que o firmware ignora."""
    ds5_de_bancada.setLeftMotor(0xC0)
    common = transporte.extrair_common(ds5_de_bancada.prepareReport())
    flag0, flag1, _flag2 = _bits_de_vibracao(common)
    assert flag0 == (
        rep.VALID_FLAG0_COMPATIBLE_VIBRATION | rep.VALID_FLAG0_HAPTICS_SELECT
    ), f"{transporte.nome}: faltam os bits de vibração do flag0"
    assert flag1 == rep.VALID_FLAG1_MOTOR_POWER, (
        f"{transporte.nome}: falta a atenuação de motor (flag1 0x40)"
    )


def test_o_bit_de_vibracao_v2_e_o_mesmo_nos_dois_transportes(
    transportes: tuple[EnvelopeDeTransporte, ...], fabrica_de_bancada: Any
) -> None:
    """O flag2 0x04 (`COMPATIBLE_VIBRATION2`) tem de valer o mesmo dos dois lados.

    NOTA DATADA DE 11/08/2026, medida ao escrever esta camada: hoje esse bit
    **nunca liga**, nem no cabo nem no rádio. O `_build_common` monta o flag2 a
    partir do `light.ledOption` (que vale no máximo 3) e só sabe DESLIGAR o
    0x04 quando não há rumble nosso — ninguém o LIGA em lugar nenhum. Ou seja:
    a vibração v2 nunca é autorizada, e a assimetria aqui é ZERO porque a
    feature está ausente dos dois lados.

    Por isso o caso trava a PARIDADE, e não o valor: no dia em que alguém ligar
    o bit — e ele tem dono no `hid-playstation` — este teste continua valendo e
    reprova se a autorização sair num transporte só. Travar o valor de hoje
    seria petrificar uma ausência.
    """
    vistos: dict[str, int] = {}
    for envelope in transportes:
        handle = fabrica_de_bancada(envelope)
        handle.setLeftMotor(0xC0)
        common = envelope.extrair_common(handle.prepareReport())
        vistos[envelope.nome] = common[rep.COMMON_VALID_FLAG2] & (
            rep.VALID_FLAG2_COMPATIBLE_VIBRATION2
        )

    assert vistos["usb"] == vistos["bt"], (
        "a autorização de vibração v2 (flag2 0x04) saiu diferente entre cabo e "
        f"rádio: {vistos} — é a assinatura do defeito de 10/08"
    )


def test_sem_rumble_nosso_o_keepalive_e_neutro_nos_dois(
    ds5_de_bancada: Any, transporte: EnvelopeDeTransporte
) -> None:
    """GUERRA-01 item 2 — e a regra vale nos DOIS transportes.

    O defeito original foi sentido no Sackboy com o jogo escrevendo direto no
    hidraw: nosso keepalive, com os bits de vibração sempre ligados e motores
    em zero, zerava o rumble de terceiros a cada meio segundo.
    """
    common = transporte.extrair_common(ds5_de_bancada.prepareReport())
    assert _bits_de_vibracao(common) == (0, 0, 0), (
        f"{transporte.nome}: o keepalive saiu asserindo vibração sem ter "
        "rumble nosso — ele zera o rumble de quem estiver tocando"
    )
    assert (common[MOTOR_DIREITO], common[MOTOR_ESQUERDO]) == (0, 0)


def test_a_transicao_ativa_para_zero_manda_um_stop_nos_dois(
    ds5_de_bancada: Any, transporte: EnvelopeDeTransporte
) -> None:
    """Ao zerar, UM report sai com flags ligados e motores 0; o seguinte é neutro.

    Sem esse report o motor não para de verdade — e sem ele nos dois
    transportes, o rumble "cola" no rádio e não no cabo (ou o contrário), que é
    a assimetria que esta camada existe para pegar.
    """
    ds5_de_bancada.setLeftMotor(0xA0)
    ds5_de_bancada.prepareReport()
    ds5_de_bancada.setLeftMotor(0)

    parada = transporte.extrair_common(ds5_de_bancada.prepareReport())
    assert (parada[MOTOR_DIREITO], parada[MOTOR_ESQUERDO]) == (0, 0)
    assert _bits_de_vibracao(parada) != (0, 0, 0), (
        f"{transporte.nome}: a transição ativa→0 não mandou o report de STOP "
        "— o motor continua girando"
    )

    depois = transporte.extrair_common(ds5_de_bancada.prepareReport())
    assert _bits_de_vibracao(depois) == (0, 0, 0), (
        f"{transporte.nome}: o report seguinte ao STOP não voltou ao neutro"
    )


def test_o_rumble_e_identico_nos_dois_e_so_o_envelope_muda(
    transportes: tuple[EnvelopeDeTransporte, ...], fabrica_de_bancada: Any
) -> None:
    """Os mesmos motores no cabo e no rádio produzem o MESMO common."""
    commons: dict[str, bytes] = {}
    for envelope in transportes:
        handle = fabrica_de_bancada(envelope)
        handle.setRightMotor(0x20)
        handle.setLeftMotor(0xC0)
        commons[envelope.nome] = envelope.extrair_common(handle.prepareReport())

    assert commons["usb"][MOTOR_DIREITO:MOTOR_ESQUERDO + 1] == b"\x20\xc0"
    assert commons["usb"] == commons["bt"], (
        "o rumble divergiu entre cabo e rádio — a vibração deixou de ser a "
        "mesma feature nos dois transportes"
    )
