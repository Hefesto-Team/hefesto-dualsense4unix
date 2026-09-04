#!/usr/bin/env python3
"""O override por controle NÃO carrega o `auto_player_colors` — e não pode.

A REGRA É DELA, 03/09/2026: *"nenhuma cor dos controles nunca pode ser a mesma,
mesmo no mesmo perfil e estilo de jogo."*

ESTE ARQUIVO NASCEU DE UM ALARME FALSO, e o registro é a metade útil dele. Ao
triar as features abertas em 04/09/2026, a linha do CSV da aba Iluminação dizia:

    "o 'Salvar' do rodapé grava `auto_player_colors=False` FIXO no override"

E a leitura do `rodape.py:117` confirmava — `auto_player_colors=False` está lá,
escrito. O raciocínio que se seguiu era coerente e inteiro: com o automático
desligado em cada controle da mesa, o que chegasse depois cairia na cor GLOBAL
do perfil, e o seguinte também — dois controles com a mesma cor, que é o que a
regra dela proíbe.

**MEDIDO, O CAMINHO NÃO EXISTE.** O valor daquela linha é DESCARTADO:
``with_controller_leds`` chama ``_leds_draft_to_config`` sem ``include_auto``, e
o default é ``False`` — o campo nunca entra na seção do override. A decisão é
antiga e está escrita nas duas pontas (``LedsDraft.auto_player_colors`` e
``_leds_draft_to_config``): *o toggle é do PERFIL*, e um override que o
gravasse densificaria uma seção parcial com um campo que o backend ignora.

O QUE ESTE ARQUIVO PASSA A GUARDAR É ISSO, e é o que a regra dela depende:
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

from hefesto_dualsense4unix.app.draft_config import DraftConfig, LedsDraft
from hefesto_dualsense4unix.core.led_control import player_slot_color
from hefesto_dualsense4unix.profiles.schema import MatchAny, Profile

#: A COR GLOBAL DO PERFIL, e o número vem do perfil DELA, medido em 04/09/2026.
#: É a cor que um controle sem override herdaria — o caso que o alarme falso
#: imaginava perigoso.
COR_GLOBAL = (40, 80, 180)

#: OS ENDEREÇOS SÃO FORJADOS. `aa:bb:cc` não é OUI de fabricante nenhum, e é a
#: mesma convenção dos outros fixtures desta casa.
P1 = "aa:bb:cc:00:00:01"
P2 = "aa:bb:cc:00:00:02"


def _draft_de_mentira() -> DraftConfig:
    """Um draft com a cor global e o automático LIGADO — o estado dela."""
    molde = Profile(name="duble-da-paleta", match=MatchAny())
    molde.leds.lightbar = COR_GLOBAL
    molde.leds.auto_player_colors = True
    return DraftConfig.from_profile(molde)


def _com_cor(draft: DraftConfig, uniq: str, rgb: tuple[int, int, int],
             auto: bool) -> DraftConfig:
    """Grava a cor daquele controle, do jeito que o rodapé grava."""
    return draft.with_controller_leds(uniq, LedsDraft(
        lightbar_rgb=rgb,
        lightbar_brightness=draft.leds.lightbar_brightness,
        player_leds=tuple(draft.leds.player_leds),  # type: ignore[arg-type]
        auto_player_colors=auto,
    ))


@pytest.mark.parametrize("auto", [True, False])
def test_o_override_de_cor_nao_opina_sobre_o_automatico(auto: bool) -> None:
    """O campo não entra no override — nem ligado, nem desligado.

    É a régua do ATO, e ela mede os DOIS valores de propósito: se só medisse o
    `False`, alguém poderia "curar" passando `True` e a régua ficaria verde
    sobre um override que voltou a densificar a seção.
    """
    d = _com_cor(_draft_de_mentira(), P1, (200, 10, 10), auto=auto)
    over = d.controller_override(P1)
    assert over is not None and over.leds is not None
    assert "auto_player_colors" not in over.leds.model_fields_set, (
        "o override daquele controle passou a ter opinião sobre a paleta "
        "automática. Com isso, congelar a cor de quem está na mesa passa a "
        "desligar o automático dele — e o controle que chegar depois cai na "
        "cor GLOBAL do perfil, repetindo a de outro. É a regra dela que quebra.")


def test_o_perfil_gravado_mantem_o_automatico_global() -> None:
    """E o que vai para o DISCO continua com o automático ligado no global.

    Esta é a outra ponta: não basta o override calar, o global tem de continuar
    dizendo `True` — é ele que pinta o controle que chega depois.
    """
    d = _com_cor(_draft_de_mentira(), P1, (200, 10, 10), auto=False)
    d = _com_cor(d, P2, (10, 200, 10), auto=False)
    perfil = d.to_profile("duble-da-paleta")
    assert perfil.leds.auto_player_colors is True, (
        "gravar a cor de dois controles desligou a paleta automática do "
        "perfil inteiro")


def test_a_cor_igual_a_global_nao_vira_override() -> None:
    """Quem está com a cor do perfil não ganha seção própria.

    `with_controller_leds` limpa a seção quando nada diverge — e é isso que
    impede o Salvar de encher o perfil de overrides que só repetem o global.
    """
    d = _com_cor(_draft_de_mentira(), P1, COR_GLOBAL, auto=False)
    over = d.controller_override(P1)
    assert over is None or over.leds is None, (
        "um controle com a cor do próprio perfil ganhou override de LED")


@pytest.mark.parametrize("slot", [1, 2, 3, 4, 5, 6, 7, 8])
def test_a_paleta_do_numero_continua_dando_cor_distinta(slot: int) -> None:
    """E a paleta que o automático usa dá cor DIFERENTE a cada número.

    É a garantia final da regra dela: com o override calado sobre o automático,
    quem chega recebe a cor do seu número — e nenhuma delas repete outra.
    """
    minha = player_slot_color(slot)
    outras = [player_slot_color(s) for s in range(1, 9) if s != slot]
    assert minha not in outras, (
        f"a paleta dá ao jogador {slot} uma cor que já é de outro")
