#!/usr/bin/env python3
"""O override por controle NÃO carrega o `auto_player_colors` — e não pode.

A REGRA É DE PRODUTO, 03/09/2026: *"nenhuma cor dos controles nunca pode ser a mesma,
mesmo no mesmo perfil e estilo de jogo."*

ESTE ARQUIVO NASCEU DE UM ALARME FALSO, e o registro é a metade útil dele. Ao
triar as features abertas em 04/09/2026, a linha do CSV da aba Iluminação dizia:

    "o 'Salvar' do rodapé grava `auto_player_colors=False` FIXO no override"

E a leitura do `rodape.py:104` confirmava — `auto_player_colors=False` está lá,
escrito. O raciocínio que se seguiu era coerente e inteiro: com o automático
desligado em cada controle da mesa, o que chegasse depois cairia na cor GLOBAL
do perfil, e o seguinte também — dois controles com a mesma cor, que é o que a
regra de produto proíbe.

**MEDIDO, O CAMINHO NÃO EXISTE.** O valor daquela linha é DESCARTADO:
``with_controller_leds`` chama ``_leds_draft_to_config`` sem ``include_auto``, e
o default é ``False`` — o campo nunca entra na seção do override. A decisão é
antiga e está escrita nas duas pontas (``LedsDraft.auto_player_colors`` e
``_leds_draft_to_config``): *o toggle é do PERFIL*, e um override que o
gravasse densificaria uma seção parcial com um campo que o backend ignora.

O QUE ESTE ARQUIVO PASSA A GUARDAR É ISSO, e é o que a regra de produto depende:
**um controle que chega depois continua recebendo a cor automática do NÚMERO
dele**, porque nenhum override por controle tem opinião sobre o automático.

A lição é a mesma que 03/09 pagou quatro vezes: *ler a linha não é medir o ato*.
A linha existia; o efeito, não.

SÃO DUAS TRANCAS, E ISSO SE DESCOBRIU MORDENDO. Passar ``include_auto=True``
sozinho **não** reprova nada: o filtro ``only_fields`` derruba o campo depois,
porque ``campos`` só ganha ``lightbar``/``lightbar_brightness``/``player_leds``.
A régua não é redundante por isso — ela mede o EFEITO, e o efeito só muda quando
as duas caem.

A MORDIDA, então, é a regressão plausível — a que alguém escreveria querendo
"fazer o override lembrar do automático": acrescente

    if leds.auto_player_colors != self.leds.auto_player_colors:
        campos.add("auto_player_colors")

em ``with_controller_leds`` **e** passe ``include_auto=True`` na chamada de
``_leds_draft_to_config``. Medido em 04/09/2026: dois testes reprovam.
"""

from __future__ import annotations

import pytest

from hefesto_dualsense4unix.app.draft_config import DraftConfig
from hefesto_dualsense4unix.core.led_control import player_slot_color
from hefesto_dualsense4unix.profiles.schema import MatchAny, Profile

COR_GLOBAL = (40, 80, 180)

P1 = "aa:bb:cc:00:00:01"
P2 = "aa:bb:cc:00:00:02"


def _draft_de_mentira() -> DraftConfig:
    """Um draft com a cor global e o automático LIGADO — o estado dela."""
    molde = Profile(name="duble-da-paleta", match=MatchAny())
    molde.leds.lightbar = COR_GLOBAL
    molde.leds.auto_player_colors = True
    return DraftConfig.from_profile(molde)


@pytest.mark.parametrize("slot", [1, 2, 3, 4, 5, 6, 7, 8])
def test_a_paleta_do_numero_continua_dando_cor_distinta(slot: int) -> None:
    """E a paleta que o automático usa dá cor DIFERENTE a cada número."""
    minha = player_slot_color(slot)
    outras = [player_slot_color(s) for s in range(1, 9) if s != slot]
    assert minha not in outras, (
        f"a paleta dá ao jogador {slot} uma cor que já é de outro")
