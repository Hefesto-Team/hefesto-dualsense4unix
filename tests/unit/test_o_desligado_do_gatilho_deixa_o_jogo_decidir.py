"""O-DESLIGADO-DEIXA-O-JOGO-DECIDIR-01 — o gatilho: UMA entrada, e ela diz o que faz.

A foto dela, 03/10/2026 ~18h20 (aba Gatilhos, P1, L2): a lista do modo oferecia
`—` e `Desligado`, que pareciam a mesma entrada. A regra de produto, ~18h15:
*«o certo seria os controles obedecerem quando o jogo manda e na
ausencia disso o perfil ganha»*  (noqa-acento: citação)
Então o «Desligado» do gatilho é «O jogo decide» (desde 06/10/2026, por ordem de produto, o rótulo
é «Sem efeito»; a regra é a mesma): sem jogo pintando, o
gatilho fica como o controle vem de fábrica (`trigger.reset`), e o que o jogo
pintar chega. A chave no perfil continua `Off` (a forma do perfil não muda); o
lado do daemon, que não trava o campo quando ele é `Off`, é do conjunto Microfone.

AS MORDIDAS:

* devolva o rótulo «Desligado» ao «Sem efeito» (`ROTULO_DO_SEM_IMERSAO` do pacote) →
  `test_ha_uma_entrada_de_o_jogo_decide_e_nenhuma_de_desligado` reprova;
* tire o `hidden` do `—` (`_op_vazio`) → `test_o_travessao_nao_e_uma_linha_da_lista`
  reprova, nos oito campos e na lista que o pacote monta;
* troque o `Off` do gesto por `trigger_set` → a prova do gesto em `a03.PROVAS`
  (`test_os_botoes_tem_dono`) reprova;
* devolva o `return` puro da graça em `uhid_gamepad._replicate_from_output` →
  `test_o_jogo_decide_o_efeito_da_graca_chega_e_o_perfil_nao_o_apaga` reprova.
"""
from __future__ import annotations

import pathlib
import re
import sys
from typing import Any

import pytest

from hefesto_dualsense4unix.core import backend_pydualsense as bp
from hefesto_dualsense4unix.core import trigger_effects
from hefesto_dualsense4unix.integrations.uhid_gamepad import (
    UHID_OPEN,
    UHID_START,
    UhidDualSense,
)
from tests.unit.test_o_jogo_manda_e_na_ausencia_o_perfil_ganha import (
    BLOCO_DO_JOGO,
    EFEITO_DO_PERFIL,
    MAC_1,
    SEM_EFEITO,
    UNIQ_1,
    _controle,
)
from tests.unit.test_uhid_replica import (
    _blueprint,
    _Clock,
    _edge_report,
    _evento,
    _FakeFd,
    _output_event,
    fake_uhid,
)

__all__ = ["fake_uhid"]

RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(RAIZ / "src/hefesto_dualsense4unix/interface"))

_SELECT = re.compile(r'<select[^>]*class="g2-imersao"[^>]*>(?P<dentro>.*?)</select>', re.S)
_OPCAO = re.compile(r"<option(?P<attrs>[^>]*)>(?P<texto>[^<]*)</option>")


def _listas_da_bancada() -> list[str]:
    from hefesto_dualsense4unix.interface import onde

    doc = onde.pagina("03-gatilhos.html").read_text(encoding="utf-8")
    return [m.group("dentro") for m in _SELECT.finditer(doc)]


def _listas_do_pacote() -> list[str]:
    import pacotes  # noqa: F401
    from pacotes import a03_gatilhos

    return [a03_gatilhos.html_das_opcoes_de_imersao()]


def _visiveis(dentro: str) -> list[str]:
    """O que a lista MOSTRA: as opções sem `hidden`."""
    return [m.group("texto") for m in _OPCAO.finditer(dentro)
            if "hidden" not in m.group("attrs")]


@pytest.mark.parametrize("fonte", [_listas_da_bancada, _listas_do_pacote])
def test_ha_uma_entrada_de_o_jogo_decide_e_nenhuma_de_desligado(fonte) -> None:
    listas = fonte()
    assert listas, "nenhuma lista de modo encontrada"
    for dentro in listas:
        vistas = _visiveis(dentro)
        assert vistas.count("Sem efeito") == 1, vistas
        assert len(vistas) > 10, "a lista do efeito do gatilho veio vazia"
        assert "Desligado" not in vistas, (
            "o «Desligado» voltou à lista: o gatilho tem duas palavras para a mesma coisa")


@pytest.mark.parametrize("fonte", [_listas_da_bancada, _listas_do_pacote])
def test_o_travessao_nao_e_uma_linha_da_lista(fonte) -> None:
    """O `—` fica no `<select>` (o piloto o escreve no lugar vazio), mas escondido."""
    for dentro in fonte():
        travessoes = [m for m in _OPCAO.finditer(dentro) if m.group("texto") == "—"]
        assert len(travessoes) == 1
        atributos = travessoes[0].group("attrs")
        assert "hidden" in atributos and "disabled" in atributos, atributos
        assert "—" not in _visiveis(dentro)


def test_o_gesto_e_o_rotulo_falam_a_mesma_coisa() -> None:
    import pacotes  # noqa: F401
    from pacotes import a03_gatilhos

    assert a03_gatilhos._rotulo_do_modo("Off") == a03_gatilhos.ROTULO_DO_JOGO_DECIDE
    assert "Desligado" not in a03_gatilhos.DICA_DO_MODO["Off"]
    assert a03_gatilhos._rotulo_do_modo("Rigid") == "Rígido"



def _vpad_ligado_ao_fisico(
    fake: _FakeFd, campos_do_perfil: dict[str, Any]
) -> tuple[bp.PyDualSenseController, Any, UhidDualSense, _Clock]:
    ctl, _no, handle = _controle(campos_dela=campos_do_perfil)
    clock = _Clock()

    def _no_fisico(lado: str, bloco: bytes) -> None:
        ctl.set_game_trigger_for(MAC_1, "left" if lado == "left" else "right", bloco)

    pad = UhidDualSense(
        player=1, blueprint=_blueprint(), time_fn=clock, sleep_fn=lambda _s: None,
        trigger_sink=_no_fisico,
    )
    assert pad.start() is True
    fake.reads.append(_evento(UHID_START))
    fake.reads.append(_evento(UHID_OPEN))
    pad.pump_ff()
    return ctl, handle, pad, clock


def _o_jogo_escreve(fake: _FakeFd, pad: UhidDualSense, bloco: bytes) -> None:
    fake.reads.append(_output_event(_edge_report(flag0=0x04, trigger_r=bloco)))
    pad.pump_ff()


def test_o_jogo_decide_o_efeito_da_graca_chega_e_o_perfil_nao_o_apaga(
    fake_uhid: _FakeFd,
) -> None:
    """MORDIDA: a graça que descarta e o físico nunca tem o bloco (o jogo calou)."""
    ctl, handle, pad, clock = _vpad_ligado_ao_fisico(
        fake_uhid, {"trigger_right": trigger_effects.off()})
    clock.t = 0.2
    _o_jogo_escreve(fake_uhid, pad, BLOCO_DO_JOGO)
    assert handle._raw_trigger_right is None

    clock.t = 0.6
    pad.pump_ff()
    assert handle._raw_trigger_right == BLOCO_DO_JOGO

    with ctl._io_lock:
        ctl._desired_by_uniq[UNIQ_1] = bp._DesiredOutput(trigger_right=trigger_effects.off())
        ctl._stamp_owner_locked(UNIQ_1, ("trigger_right",), bp._LAYER_PROFILE)
    clock.t = 5.0
    pad.pump_ff()
    assert handle._raw_trigger_right == BLOCO_DO_JOGO


def test_o_sem_efeito_da_graca_e_ausencia_e_o_perfil_vale(fake_uhid: _FakeFd) -> None:
    ctl, handle, pad, clock = _vpad_ligado_ao_fisico(
        fake_uhid, {"trigger_right": EFEITO_DO_PERFIL})
    clock.t = 0.2
    _o_jogo_escreve(fake_uhid, pad, SEM_EFEITO)
    clock.t = 0.6
    pad.pump_ff()

    assert handle._raw_trigger_right is None
    with ctl._io_lock:
        assert ctl._merged_desired_for_key(MAC_1).trigger_right == EFEITO_DO_PERFIL
