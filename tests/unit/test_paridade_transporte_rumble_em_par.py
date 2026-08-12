"""O keepalive do daemon não pode zerar o rumble de terceiros — nos DOIS transportes.

O QUE ESTE ARQUIVO GUARDA
-------------------------
A cura chamada `keepalive neutro` (GUERRA-01 item 2), em
`core/backend_pydualsense.py:_build_common`. Sem rumble NOSSO ativo, os bits que
autorizam vibração têm de sair DESLIGADOS do report — para que o firmware
conserve o motor que outro dono (um jogo por EV_FF, o Steam Input por hidraw)
deixou girando. Sem ela, cada report de keepalive matava a vibração alheia.

POR QUE ELE EXISTE, e o que ele NÃO prova
-----------------------------------------
Em 11/08/2026, com quatro DualSense na mesa dela (dois no cabo, dois no rádio),
o sintoma que esta cura previne foi medido de novo, com variável única e ida e
volta: com o daemon VIVO, 40 s de força-feedback por evdev produziram um único
pulso no controle do rádio e NADA no do cabo; com o daemon PARADO, os mesmos 40 s
saíram contínuos nos dois. Registrado em `docs/data/ensaios.csv`
(`rumble-ff-par-vivo-*` contra `rumble-ff-par-morto-*`).

Este arquivo NÃO reproduz aquele defeito — ele é de unidade, e o defeito mora no
encontro de dois escritores com o firmware. O que ele faz é impedir que a cura
seja removida sem alguém perceber: a premissa dela (o firmware conserva o motor
quando os bits de autorização saem desligados) continua sendo a próxima coisa a
medir na bancada, e enquanto isso a cura fica presa por teste.

MORDE? Arranque o bloco `if not rumble_asserted:` de `_build_common` e estes
testes reprovam nos dois transportes.
"""

from __future__ import annotations

import pytest

from hefesto_dualsense4unix.core import ds_output_report as rep

# Os dois bytes de motor dentro do bloco `common` de 47 bytes, do fonte do
# driver desta máquina (assets/dkms/hid-playstation/hid-playstation.c) e da
# linha `vibracao.rumble.esquerdo@dualsense` do mapa de canais.
COMMON_MOTOR_DIREITO = 2  # weak
COMMON_MOTOR_ESQUERDO = 3  # strong

BITS_QUE_AUTORIZAM_VIBRACAO = (
    ("flag0", 0, rep.VALID_FLAG0_COMPATIBLE_VIBRATION),
    ("flag0", 0, rep.VALID_FLAG0_HAPTICS_SELECT),
    ("flag1", 1, rep.VALID_FLAG1_MOTOR_POWER),
)


@pytest.fixture
def backend_sem_hardware():
    """Um handle da pydualsense com o suficiente para montar o `common`.

    Não abre hidraw, não fala com aparelho nenhum: `_build_common` é função do
    estado desejado, e é exatamente esse estado que queremos afirmar.
    """
    from hefesto_dualsense4unix.core.backend_pydualsense import _PinnedPyDualSense

    handle = _PinnedPyDualSense.__new__(_PinnedPyDualSense)
    handle.leftMotor = 0
    handle.rightMotor = 0
    handle._rumble_active = False
    handle._rumble_stop_pending = False
    handle._suppress_leds = False
    handle._volumes_audio = None
    handle._mic_mute_desejado = None
    handle._preamp_audio = None
    handle._raw_trigger_right = None
    handle._raw_trigger_left = None

    class _Valor:
        value = 0x00

    class _Luz:
        # Os nomes são os do upstream (`pydualsense.DSLight`) e `_build_common`
        # os lê por atributo — renomeá-los aqui seria dublar outra classe.
        ledOption = _Valor()  # noqa: N815
        pulseOptions = _Valor()  # noqa: N815
        brightness = _Valor()
        playerNumber = _Valor()  # noqa: N815
        TouchpadColor = (0, 0, 0)

    class _Gatilho:
        mode = _Valor()
        forces = (0,) * 7

    class _Audio:
        microphone_led = 0
        microphone_mute = 0

    handle.light = _Luz()
    handle.audio = _Audio()
    handle.triggerR = _Gatilho()
    handle.triggerL = _Gatilho()
    return handle


def test_sem_rumble_nosso_o_keepalive_nao_autoriza_vibracao(backend_sem_hardware):
    """A cura em si: report neutro não pede vibração ao firmware.

    Este é o teste que morde. Com o bloco `if not rumble_asserted:` arrancado de
    `_build_common`, os bits saem ligados com os motores em zero — que é
    literalmente "pare o motor" — e este teste reprova.
    """
    common = backend_sem_hardware._build_common(rumble_asserted=False)

    for nome, indice, bit in BITS_QUE_AUTORIZAM_VIBRACAO:
        assert not (common[indice] & bit), (
            f"o keepalive ligou {nome} bit {bit:#04x} sem rumble nosso ativo: "
            "com os motores em zero isso manda o firmware PARAR o motor de "
            "terceiros, e foi o defeito que GUERRA-01 curou"
        )


def test_com_rumble_nosso_a_vibracao_volta_a_ser_autorizada(backend_sem_hardware):
    """O outro lado da cura: quando o rumble é NOSSO, os bits têm de sair.

    Sem este par, alguém 'curaria' o teste acima desligando os bits para sempre,
    e o rumble do produto pararia de funcionar sem nenhum teste reclamar.
    """
    backend_sem_hardware.leftMotor = 200
    common = backend_sem_hardware._build_common(rumble_asserted=True)

    for nome, indice, bit in BITS_QUE_AUTORIZAM_VIBRACAO:
        assert common[indice] & bit, (
            f"{nome} bit {bit:#04x} saiu DESLIGADO com rumble nosso ativo: "
            "o motor não gira"
        )
    assert common[COMMON_MOTOR_ESQUERDO] == 200


@pytest.mark.parametrize("transporte", ["cabo", "radio"])
def test_o_rumble_de_terceiros_por_evdev_nao_e_zerado_pelo_keepalive(
    backend_sem_hardware, transporte
):
    """O envelope de CADA transporte carrega o mesmo `common` neutro.

    A paridade é o ponto: o defeito de 11/08 apareceu nos DOIS transportes, e um
    envelope que ligasse os bits de vibração por conta própria — ou que
    reposicionasse os bytes de motor — devolveria o defeito só de um lado, que é
    a forma de regressão que este mapa existe para pegar.
    """
    common = backend_sem_hardware._build_common(rumble_asserted=False)
    assert len(common) == rep.COMMON_LEN

    if transporte == "cabo":
        quadro = rep.build_usb_report(common)
        deslocamento = 1
    else:
        quadro = rep.build_bt_report(common)
        deslocamento = 3

    for nome, indice, bit in BITS_QUE_AUTORIZAM_VIBRACAO:
        assert not (quadro[deslocamento + indice] & bit), (
            f"no envelope de {transporte} o {nome} bit {bit:#04x} saiu LIGADO: "
            "o keepalive mataria o rumble de terceiros neste transporte"
        )

    assert quadro[deslocamento + COMMON_MOTOR_DIREITO] == 0
    assert quadro[deslocamento + COMMON_MOTOR_ESQUERDO] == 0
