"""PARIDADE-BYTE-01 — a COR da lightbar sai igual no cabo e no rádio.

Este é o caso que abriu o diagnóstico de 10/08/2026: **trocar R por B dentro de
`_build_common`** — a lightbar mandando azul onde o produto pediu vermelho —
deixava a suíte INTEIRA verde, 8584 passaram. Nenhum dos 8589 testes olhava o
byte da cor dentro do envelope de nenhum dos dois transportes.

O que trava a porta aqui:

- a cor é lida DE DENTRO do envelope de cada transporte (offset 44/45/46 do
  common, que mora em `[1..47]` no 0x02 e em `[3..49]` no 0x31), pela fixture
  `transporte`, que MEDE o deslocamento no builder de produção;
- os vetores de cor são todos ASSIMÉTRICOS em R e B de propósito: uma cor cinza
  (r == g == b) passaria com os canais trocados e não provaria nada;
- e o caso roda DUAS vezes, com ids `[usb]` e `[bt]`, então "quebrou" nunca mais
  é uma resposta sem lado.

MORDIDA PROVADA (11/08/2026, com o `src/` COPIADO para fora da árvore e o
`PYTHONPATH` apontado para a cópia — a árvore de trabalho nunca foi mutada):

- trocando `TouchpadColor[0]` por `TouchpadColor[2]` dentro de `_build_common`
  (vermelho vira azul), este arquivo reprova **12 de 17**, seis `[usb]` e seis
  `[bt]`. Antes desta camada a mesma mutação reprovava **0** na suíte inteira;
- zerando `common[44..46]` só quando `conType == BT`, reprovam **7**: os seis
  `[bt]` e o caso que compara os dois lados. Os `[usb]` seguem verdes, que é
  exatamente o defeito que a dona descreveu — *"tínhamos algo para o cabo e na
  hora do vamos ver a versão de BT não funcionava"*.
"""
from __future__ import annotations

from typing import Any

import pytest

from hefesto_dualsense4unix.core import ds_output_report as rep

from tests.conftest import EnvelopeDeTransporte

#: Offsets da cor dentro do common (espelho do `dualsense_output_report_common`).
COR_R, COR_G, COR_B = 44, 45, 46

#: Vetores de cor com R != B SEMPRE — é o que faz a troca de canais reprovar.
#: `(0xFF, 0x00, 0x00)` e `(0x00, 0x00, 0xFF)` estão aqui nomeadamente porque
#: são o vermelho e o azul da mutação do diagnóstico.
CORES = [
    (0xFF, 0x00, 0x00),
    (0x00, 0x00, 0xFF),
    (0x2A, 0x40, 0xC8),
    (0xC8, 0x40, 0x2A),
    (0x10, 0xFF, 0x80),
]


def _com_leds_do_hefesto(handle: Any) -> Any:
    """Tira a supressão de LED: o report volta a ser a rota da cor.

    `_suppress_leds` NASCE True em produção (LIGHTBAR-BT-ADOPT-01: a janela de
    ~3,4 s pós-connect por BT em que um report malformado LATCHEIA a lightbar
    apagada até o power-off). Quando o sysfs do kernel não é gravável,
    `_refresh_sysfs_leds` o desliga e a cor volta a sair pelo report — é ESSE o
    estado que este arquivo mede, e ele está declarado aqui em vez de escondido
    numa fixture.
    """
    handle._suppress_leds = False
    return handle


@pytest.mark.parametrize("cor", CORES)
def test_a_cor_sai_nos_bytes_certos_nos_dois_transportes(
    ds5_de_bancada: Any, transporte: EnvelopeDeTransporte, cor: tuple[int, int, int]
) -> None:
    """A cor pedida chega intacta a common[44..46], no cabo E no rádio."""
    handle = _com_leds_do_hefesto(ds5_de_bancada)
    r, g, b = cor
    handle.light.setColorI(r, g, b)

    report = handle.prepareReport()
    assert transporte.problemas_do_envelope(report) == []
    common = transporte.extrair_common(report)

    assert (common[COR_R], common[COR_G], common[COR_B]) == (r, g, b), (
        f"transporte {transporte.nome}: pedi RGB {cor} e saiu "
        f"{(common[COR_R], common[COR_G], common[COR_B])} — se R e B estão "
        "invertidos, é a mutação de 10/08 (vermelho vira azul) viva"
    )


def test_vermelho_puro_nao_pode_sair_azul(
    ds5_de_bancada: Any, transporte: EnvelopeDeTransporte
) -> None:
    """O caso do diagnóstico, isolado e com nome — vermelho é 44, não 46."""
    handle = _com_leds_do_hefesto(ds5_de_bancada)
    handle.light.setColorI(0xFF, 0x00, 0x00)
    common = transporte.extrair_common(handle.prepareReport())
    assert common[COR_R] == 0xFF, (
        f"{transporte.nome}: o vermelho não está em common[44] — "
        "R e B trocados dentro de `_build_common`"
    )
    assert common[COR_B] == 0x00, (
        f"{transporte.nome}: saiu azul no lugar do vermelho"
    )


def test_o_flag1_autoriza_a_lightbar_nos_dois_transportes(
    ds5_de_bancada: Any, transporte: EnvelopeDeTransporte
) -> None:
    """Byte certo sem bit de validação é byte que o firmware ignora."""
    handle = _com_leds_do_hefesto(ds5_de_bancada)
    handle.light.setColorI(0x2A, 0x40, 0xC8)
    common = transporte.extrair_common(handle.prepareReport())
    assert common[1] & rep.VALID_FLAG1_LIGHTBAR_CONTROL_ENABLE, (
        f"{transporte.nome}: a cor foi escrita mas o bit 0x04 do flag1 não "
        "autoriza o firmware a adotá-la"
    )


def test_a_cor_e_identica_nos_dois_e_so_o_envelope_muda(
    transportes: tuple[EnvelopeDeTransporte, ...], fabrica_de_bancada: Any
) -> None:
    """O common de 47 bytes é o MESMO; o que muda é o que o embrulha.

    É a afirmação que o cabeçalho de `ds_output_report.py` faz em prosa desde o
    BTREPORT-02 e que nenhum caso checava: *"o payload common tem 47 bytes e é
    IDÊNTICO nos dois transportes; muda só o envelope"*.
    """
    commons: dict[str, bytes] = {}
    envelopes: dict[str, bytes] = {}
    for envelope in transportes:
        handle = _com_leds_do_hefesto(fabrica_de_bancada(envelope))
        handle.light.setColorI(0x2A, 0x40, 0xC8)
        report = bytes(handle.prepareReport())
        commons[envelope.nome] = envelope.extrair_common(report)
        envelopes[envelope.nome] = report

    assert commons["usb"] == commons["bt"], (
        "o payload de 47 bytes divergiu entre cabo e rádio — a cor deixou de "
        "ser a mesma feature nos dois transportes"
    )
    assert envelopes["usb"] != envelopes["bt"]
    assert len(envelopes["usb"]) == rep.USB_REPORT_LEN
    assert len(envelopes["bt"]) == rep.BT_REPORT_LEN


def test_sob_supressao_a_cor_nao_sai_em_nenhum_dos_dois(
    ds5_de_bancada: Any, transporte: EnvelopeDeTransporte
) -> None:
    """Com o kernel dono do LED, o report é LED-neutro — nos dois transportes.

    LIGHTBAR-BT-KEEPALIVE-01: sob supressão não basta zerar os bytes de cor; os
    bits de SETUP/BRILHO do flag2 (0x02|0x01) também têm de cair, senão o
    keepalive a 2 Hz reengata a máquina de estados da lightbar do firmware e a
    barra trava apagada. O defeito foi medido no BT — e a regra vale nos dois,
    que é o que este caso trava.
    """
    handle = ds5_de_bancada
    handle._suppress_leds = True
    handle.light.setColorI(0xFF, 0x00, 0x00)
    common = transporte.extrair_common(handle.prepareReport())

    assert (common[COR_R], common[COR_G], common[COR_B]) == (0, 0, 0)
    assert common[1] & rep.VALID_FLAG1_LIGHTBAR_CONTROL_ENABLE == 0
    assert (
        common[rep.COMMON_VALID_FLAG2]
        & (
            rep.VALID_FLAG2_LIGHTBAR_SETUP_CONTROL_ENABLE
            | rep.VALID_FLAG2_LED_BRIGHTNESS_CONTROL_ENABLE
        )
        == 0
    ), f"{transporte.nome}: o keepalive reengatou o setup da lightbar"
