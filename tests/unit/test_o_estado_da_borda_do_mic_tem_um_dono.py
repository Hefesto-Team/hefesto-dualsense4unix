"""O estado da eleição do mic tem UM dono, e nenhum dublê precisa redigitá-lo.

O DEFEITO, e ele é de FAMÍLIA — 10/09/2026
-------------------------------------------
`_PinnedPyDualSense` é construído por ``__new__`` em **dezesseis** arquivos
desta suíte: abrir aparelho num teste é proibido nesta casa, então cada dublê
lista à mão os campos de que precisa. É o desenho certo — e é o desenho que
quebra toda vez que o produto ganha um campo.

Em 10/09 a cura da sustentação (`SUSTENTACAO_DO_MUDO_S`) acrescentou dois
campos ao estado da borda, e **nove testes caíram com `AttributeError` em
quatro arquivos diferentes**, nenhum deles falando de sustentação. O sintoma
não aponta para a causa: quem lê `'_PinnedPyDualSense' object has no attribute
'_mudos_que_pedimos'` procura o campo, não a cura que o criou.

**A cura errada seria redigitar o campo em dezesseis lugares** — é a mesma
família de defeito com outra roupa: *dois lugares que precisam concordar e são
digitados separadamente*.

O QUE ESTE ARQUIVO TRAVA
-------------------------
Que o produto **não dependa** de nenhum dublê saber a lista. Um handle
construído por ``__new__`` puro — sem `__init__`, sem campo nenhum — tem de
atravessar os dois pontos de entrada do estado sem levantar.

A MORDIDA: apague `self._garantir_estado_da_borda_do_mic()` de
`_registrar_borda_do_mic` e o primeiro teste reprova com o `AttributeError`
exato que custou a manhã.
"""
from __future__ import annotations

from typing import Any

import pytest

from hefesto_dualsense4unix.core.backend_pydualsense import _PinnedPyDualSense
from hefesto_dualsense4unix.integrations.dualsense_bt_audio import STATUS_MIC_MUDO


def _handle_cru() -> Any:
    """O dublê mais POBRE possível: nada além do que `__new__` dá.

    De propósito. Se o produto aguenta este, aguenta os dezesseis.
    """
    return _PinnedPyDualSense.__new__(_PinnedPyDualSense)


def test_a_borda_atravessa_um_handle_sem_init() -> None:
    """`_registrar_borda_do_mic` se vira sozinho."""
    h = _handle_cru()
    h._registrar_borda_do_mic(0x00)
    h._registrar_borda_do_mic(STATUS_MIC_MUDO)

    assert h._mic_mudo is True
    assert isinstance(h._mic_mudo_seq, int)
    assert h._mudos_que_pedimos == []


def test_a_marca_do_eco_atravessa_um_handle_sem_init() -> None:
    """O outro ponto de entrada: quem ANOTA o que nós pedimos.

    Sem a garantia aqui, `set_microphone_mute` num handle cru levantaria — e
    é ele quem o daemon chama quando ela aperta o botão.
    """
    h = _handle_cru()
    h._mic_mute_desejado = None
    h._marcar_o_mudo_que_pedimos(True)

    assert h._mudos_que_pedimos == [True]


def test_zerar_e_idempotente_e_nao_apaga_o_status_lido() -> None:
    """Chamar o dono duas vezes não inventa nem apaga estado.

    `_audio_status` fica de fora de propósito: ele é o último byte LIDO do
    aparelho, e zerá-lo transformaria *"ainda não vi report íntegro"* em *"vi,
    e estava limpo"* — que é a diferença entre não saber e afirmar errado.
    """
    h = _handle_cru()
    h._audio_status = STATUS_MIC_MUDO
    h.zerar_estado_da_borda_do_mic()
    h.zerar_estado_da_borda_do_mic()

    assert h._audio_status == STATUS_MIC_MUDO
    assert h._mic_mudo is None
    assert h._mic_mudo_seq == 0
    assert h._borda_armada is None


def test_a_garantia_nao_pisa_no_estado_de_quem_ja_tem() -> None:
    """Idempotência de verdade: quem já contou bordas não volta a zero.

    Se `_garantir_…` zerasse a cada report, o contador nunca passaria de zero
    e a eleição do microfone morria em silêncio — um defeito muito pior que o
    `AttributeError` que ele cura.
    """
    h = _handle_cru()
    h._registrar_borda_do_mic(0x00)
    h._mic_mudo_seq = 7
    h._mudos_que_pedimos = [True]

    h._garantir_estado_da_borda_do_mic()

    assert h._mic_mudo_seq == 7, "a garantia zerou o contador de quem já tinha"
    assert h._mudos_que_pedimos == [True]


@pytest.mark.parametrize(
    "campo",
    ["_mic_mudo", "_mic_mudo_seq", "_mudos_que_pedimos", "_borda_armada",
     "_mic_mudo_em"],
)
def test_todo_campo_do_estado_nasce_no_dono_unico(campo: str) -> None:
    """A lista COMPLETA vive num lugar só — e é esta régua que impede a volta.

    Acrescentar um campo ao estado da borda fora de
    `zerar_estado_da_borda_do_mic` faz este teste reprovar no dia em que o
    campo for acrescentado, e não semanas depois, num dublê distante.
    """
    h = _handle_cru()
    h.zerar_estado_da_borda_do_mic()
    assert campo in h.__dict__, (
        f"`{campo}` não nasce em `zerar_estado_da_borda_do_mic` — algum outro "
        "lugar o cria, e os dezesseis dublês desta suíte não sabem disso"
    )
