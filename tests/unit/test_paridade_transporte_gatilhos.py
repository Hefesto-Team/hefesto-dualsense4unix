"""PARIDADE-BYTE-01 — os gatilhos adaptativos, byte a byte, no cabo e no rádio.

O segundo caso do diagnóstico de 10/08/2026: matar os gatilhos adaptativos **só
no BT**, com envelope e CRC perfeitos, reprovava **1 teste em 8589** — e era o
genérico *"o payload sai verbatim"*, que não sabe o que é gatilho. Modo, zonas e
forças não eram olhados em transporte nenhum.

O bloco de gatilho tem DOIS donos possíveis, e os dois estão cobertos aqui:

- o **perfil** (rota `DSTrigger`): modo em common[10], seis forças em
  common[11..16] e a sétima em common[19] — e o espelho do esquerdo em
  common[21], [22..27] e [30];
- o **jogo** (REPLICA-03, rota crua): 11 bytes VERBATIM em common[10..20] e
  common[21..31], que é o layout do `DS5EffectsState_t` do SDL.

MORDIDA PROVADA (11/08/2026, `src/` copiado para fora da árvore, `PYTHONPATH`
apontado para a cópia — a árvore de trabalho nunca foi mutada):

- zerando `common[10:32]` só quando `conType == BT` (a mutação exata do
  diagnóstico), este arquivo reprova **12 de 25**: onze com o id `[bt]` e o
  caso que compara os dois lados. Antes desta camada a mesma morte reprovava 1
  teste em 8589, e era um genérico que não sabia o que estava medindo;
- a mesma morte SÓ no cabo reprova **12**, e desta vez os onze são `[usb]` —
  a rede não tem lado preferido, que é o ponto.
"""
from __future__ import annotations

from typing import Any

import pytest

from hefesto_dualsense4unix.core import ds_output_report as rep

from tests.conftest import EnvelopeDeTransporte

#: Offsets do bloco de gatilho DENTRO do common, por lado.
#: (modo, primeira das seis forças, a sétima força avulsa)
OFFSETS_DO_GATILHO = {"right": (10, 11, 19), "left": (21, 22, 30)}

#: Tamanho do bloco cru do jogo (REPLICA-03) — modo + 10 parâmetros.
BLOCO_CRU_LEN = 11

#: Efeitos de gatilho com modo E forças distinguíveis. `Rigid_B` e `Pulse_AB`
#: existem aqui porque os valores deles (5 e 38) não são 1 nem 2: um teste que
#: só usasse `Rigid` passaria com o modo truncado para o bit baixo.
EFEITOS = [
    (1, (0xFF, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00)),  # Rigid
    (2, (0x10, 0x20, 0x30, 0x00, 0x00, 0x00, 0x00)),  # Pulse
    (5, (0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07)),  # Rigid_B
    (38, (0x90, 0x80, 0x70, 0x60, 0x50, 0x40, 0x30)),  # Pulse_AB
]


def _aplicar_efeito(handle: Any, lado: str, modo: int, forcas: tuple[int, ...]) -> None:
    """Aplica um efeito pela MESMA rota da produção (`_apply_trigger`)."""
    from hefesto_dualsense4unix.core.backend_pydualsense import PyDualSenseController
    from hefesto_dualsense4unix.core.controller import TriggerEffect

    PyDualSenseController._apply_trigger(handle, lado, TriggerEffect(modo, forcas))


@pytest.mark.parametrize("lado", ["right", "left"])
@pytest.mark.parametrize(("modo", "forcas"), EFEITOS)
def test_modo_e_forcas_saem_nos_offsets_certos_nos_dois_transportes(
    ds5_de_bancada: Any,
    transporte: EnvelopeDeTransporte,
    lado: str,
    modo: int,
    forcas: tuple[int, ...],
) -> None:
    """Modo, as seis forças contíguas e a sétima avulsa — no cabo E no rádio."""
    _aplicar_efeito(ds5_de_bancada, lado, modo, forcas)
    report = ds5_de_bancada.prepareReport()
    assert transporte.problemas_do_envelope(report) == []
    common = transporte.extrair_common(report)

    off_modo, off_forcas, off_setima = OFFSETS_DO_GATILHO[lado]
    assert common[off_modo] == modo, (
        f"{transporte.nome}/{lado}: modo {common[off_modo]} em common"
        f"[{off_modo}], esperado {modo}"
    )
    assert list(common[off_forcas : off_forcas + 6]) == list(forcas[:6]), (
        f"{transporte.nome}/{lado}: as seis forças não bateram"
    )
    assert common[off_setima] == forcas[6], (
        f"{transporte.nome}/{lado}: a sétima força mora em common"
        f"[{off_setima}], e saiu {common[off_setima]} no lugar de {forcas[6]}"
    )


def test_os_dois_lados_convivem_sem_se_pisar(
    ds5_de_bancada: Any, transporte: EnvelopeDeTransporte
) -> None:
    """Direito e esquerdo ao mesmo tempo, valores distintos, nos dois transportes."""
    _aplicar_efeito(ds5_de_bancada, "right", 1, (0xAA, 0, 0, 0, 0, 0, 0x11))
    _aplicar_efeito(ds5_de_bancada, "left", 2, (0xBB, 0, 0, 0, 0, 0, 0x22))
    common = transporte.extrair_common(ds5_de_bancada.prepareReport())

    assert (common[10], common[11], common[19]) == (1, 0xAA, 0x11)
    assert (common[21], common[22], common[30]) == (2, 0xBB, 0x22)


def test_o_flag0_autoriza_os_dois_gatilhos_nos_dois_transportes(
    ds5_de_bancada: Any, transporte: EnvelopeDeTransporte
) -> None:
    """Bloco escrito sem bit de validação é bloco que o firmware ignora."""
    _aplicar_efeito(ds5_de_bancada, "right", 1, (0xFF, 0, 0, 0, 0, 0, 0))
    common = transporte.extrair_common(ds5_de_bancada.prepareReport())
    assert common[0] & rep.VALID_FLAG0_RIGHT_TRIGGER_FFB, (
        f"{transporte.nome}: o gatilho direito saiu sem o bit 0x04 do flag0"
    )
    assert common[0] & rep.VALID_FLAG0_LEFT_TRIGGER_FFB, (
        f"{transporte.nome}: o gatilho esquerdo saiu sem o bit 0x08 do flag0"
    )


@pytest.mark.parametrize("lado", ["right", "left"])
def test_o_bloco_cru_do_jogo_sai_verbatim_nos_dois_transportes(
    ds5_de_bancada: Any, transporte: EnvelopeDeTransporte, lado: str
) -> None:
    """REPLICA-03: os 11 bytes do jogo entram inteiros, sem passar pela DSTrigger.

    A `DSTrigger` só representa 7 forças; se o bloco do jogo passasse por ela,
    os parâmetros 8, 9 e 10 do efeito virariam zero. Este caso trava os onze
    bytes, e trava nos dois transportes.
    """
    bloco = bytes(range(0x81, 0x81 + BLOCO_CRU_LEN))
    atributo = "_raw_trigger_right" if lado == "right" else "_raw_trigger_left"
    setattr(ds5_de_bancada, atributo, bloco)

    common = transporte.extrair_common(ds5_de_bancada.prepareReport())
    inicio = 10 if lado == "right" else 21
    assert bytes(common[inicio : inicio + BLOCO_CRU_LEN]) == bloco, (
        f"{transporte.nome}/{lado}: o bloco cru do jogo não saiu verbatim"
    )


def test_o_bloco_de_gatilho_e_identico_nos_dois_e_so_o_envelope_muda(
    transportes: tuple[EnvelopeDeTransporte, ...], fabrica_de_bancada: Any
) -> None:
    """A morte que reprovava 1 teste em 8589 passa a reprovar aqui, com lado.

    Este é o caso que enxerga os DOIS transportes de uma vez: se o gatilho
    morrer só de um lado, o bloco de 22 bytes deixa de ser o mesmo e a
    mensagem diz qual lado ficou zerado.
    """
    blocos: dict[str, bytes] = {}
    for envelope in transportes:
        handle = fabrica_de_bancada(envelope)
        _aplicar_efeito(handle, "right", 5, (1, 2, 3, 4, 5, 6, 7))
        _aplicar_efeito(handle, "left", 38, (9, 8, 7, 6, 5, 4, 3))
        common = envelope.extrair_common(handle.prepareReport())
        blocos[envelope.nome] = bytes(common[10:32])

    assert any(blocos["usb"]), "o gatilho saiu zerado no CABO"
    assert any(blocos["bt"]), "o gatilho saiu zerado no RÁDIO"
    assert blocos["usb"] == blocos["bt"], (
        "o bloco de gatilho divergiu entre cabo e rádio — é a assinatura do "
        "defeito de 10/08: a feature vale num transporte só"
    )
