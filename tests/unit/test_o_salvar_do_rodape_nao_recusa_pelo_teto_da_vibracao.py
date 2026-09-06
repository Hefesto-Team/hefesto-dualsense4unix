#!/usr/bin/env python3
"""O «Salvar Perfil» do rodapé recusava com a máquina dela como está AGORA.

ACHADO ABRINDO A TELA E CLICANDO — 06/09/2026, ONDA5-07-02, com o daemon vivo
e um DualSense no cabo. O clique sintético em «Salvar Perfil» devolveu::

    [gesto falhou] 10-perfis.html · salvar: 1 validation error for RumbleConfig
      Value error, custom_mult só é válido com policy='custom'
      (policy='balanceado')

Não é tarja cosmética: o gesto LEVANTA, e um `RuntimeError`/`ValueError` de
gesto vira **tarja de recusa** no cartão (`hefesto_vivo._recusou_dizendo`). O
perfil dela **não é gravado**. Todo o resto do Salvar — cor, som, sensores,
mouse — morre junto, e o que o rodapé escreveria no disco não chega lá.

A CAUSA, MEDIDA NO DAEMON DELA
------------------------------
O daemon publica os três campos de vibração SEMPRE, e o teto é uma MEMÓRIA::

    rumble_policy             = 'balanceado'
    rumble_passthrough        = True
    rumble_policy_custom_mult = 0.7      <- o teto que ela usou quando o degrau
                                            era "custom"; continua publicado

`rodape._o_que_e_da_mesa_inteira` copiava os três para o rascunho sem
perguntar, e o `to_profile` monta um `RumbleConfig(policy='balanceado',
custom_mult=0.7)` — que o esquema recusa **de propósito**, e a razão dele está
certa (`profiles/schema.py`): *"custom_mult fora de policy='custom' é erro
semântico (o valor seria silenciosamente ignorado pelo daemon)"*.

**Quem estava errado era o rodapé**, não o esquema: o teto só existe sob
`custom`, e é a aba Vibração — a dona do par — que já escreve os dois JUNTOS
(`a05_vibracao.py:1287`). O rodapé lia os dois SOLTOS.

A MORDIDA: devolva a linha `mudancas["custom_mult"] = float(mult)` incondicional
a `_o_que_e_da_mesa_inteira` e o primeiro teste reprova com a mesma
`ValidationError` que a tela mostrou.
"""
from __future__ import annotations

from typing import Any

import pytest

from hefesto_dualsense4unix.profiles.schema import MatchAny, Profile

#: O ESTADO DELA, medido no daemon vivo em 06/09/2026 às 04h42. O `0.7` é o
#: teto lembrado de quando o degrau era "custom" — e é o que fazia o Salvar
#: recusar com o degrau em "Balanceado".
ESTADO_DELA = {
    "active_profile": "Personalizado",
    "rumble_policy": "balanceado",
    "rumble_passthrough": True,
    "rumble_policy_custom_mult": 0.7,
}


@pytest.fixture
def disco(tmp_path: Any, monkeypatch: pytest.MonkeyPatch) -> Any:
    """Pasta de perfis isolada — nada do disco dela é lido nem escrito."""
    import hefesto_dualsense4unix.profiles.loader as loader_mod

    destino = tmp_path / "profiles"
    destino.mkdir()
    monkeypatch.setattr(loader_mod, "profiles_dir", lambda ensure=False: destino)
    from hefesto_dualsense4unix.profiles.loader import save_profile

    save_profile(Profile(name="Personalizado", match=MatchAny(), priority=10))
    return destino


def _ctx(estado: dict[str, Any]) -> Any:
    from hefesto_dualsense4unix.interface.pacotes import Contexto

    return Contexto(state=estado)


def test_o_teto_lembrado_nao_derruba_o_salvar(disco: Any) -> None:
    """O caso EXATO da máquina dela: degrau "Balanceado", teto lembrado 0,7."""
    from hefesto_dualsense4unix.interface.pacotes import rodape

    draft = rodape._draft_do_ativo("Personalizado", _ctx(ESTADO_DELA))
    assert draft is not None

    # Sem a cura, esta linha levanta `ValidationError` — que é o que a tela
    # dela mostrou como tarja de recusa.
    prof = draft.to_profile("Personalizado", priority=10)

    assert prof.rumble.policy == "balanceado"
    assert prof.rumble.custom_mult is None
    assert prof.rumble.passthrough is True


def test_sob_custom_o_teto_continua_indo_para_o_perfil(disco: Any) -> None:
    """A cura não pode virar "o rodapé nunca grava o teto".

    Com o degrau em "custom" o número É o ajuste dela, e perdê-lo seria trocar
    uma recusa barulhenta por uma perda calada — a família de defeito que o
    item 13 de 05/09 nomeou.
    """
    from hefesto_dualsense4unix.interface.pacotes import rodape

    estado = {**ESTADO_DELA, "rumble_policy": "custom"}
    draft = rodape._draft_do_ativo("Personalizado", _ctx(estado))
    assert draft is not None

    prof = draft.to_profile("Personalizado", priority=10)
    assert prof.rumble.policy == "custom"
    assert prof.rumble.custom_mult == pytest.approx(0.7)


def test_o_teto_do_perfil_sai_quando_o_degrau_deixa_de_ser_custom(
    disco: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """O teto do DISCO também tem de sair, e este é o caminho que sobrava.

    Um perfil salvo sob "custom" carrega `custom_mult` no JSON. Se ela mudar o
    degrau para "Balanceado" e mandar Salvar, o rascunho traz a política NOVA
    do daemon e o teto VELHO do disco — o mesmo par proibido, por outra porta.
    Ler só o que o daemon publica deixaria esta metade viva.
    """
    from hefesto_dualsense4unix.interface.pacotes import rodape
    from hefesto_dualsense4unix.profiles.loader import save_profile
    from hefesto_dualsense4unix.profiles.schema import RumbleConfig

    save_profile(Profile(
        name="Personalizado", match=MatchAny(), priority=10,
        rumble=RumbleConfig(policy="custom", custom_mult=1.4),
    ))
    # O daemon diz "balanceado" e NÃO publica teto nenhum.
    estado = {"active_profile": "Personalizado", "rumble_policy": "balanceado"}
    draft = rodape._draft_do_ativo("Personalizado", _ctx(estado))
    assert draft is not None

    prof = draft.to_profile("Personalizado", priority=10)
    assert prof.rumble.policy == "balanceado"
    assert prof.rumble.custom_mult is None


def test_sem_vibracao_no_estado_o_rodape_nao_inventa(disco: Any) -> None:
    """Daemon calado sobre vibração: o rascunho fica com o que o perfil tinha.

    É o que impede a cura de virar "o Salvar zera o teto de quem não perguntou".
    """
    from hefesto_dualsense4unix.interface.pacotes import rodape
    from hefesto_dualsense4unix.profiles.loader import save_profile
    from hefesto_dualsense4unix.profiles.schema import RumbleConfig

    save_profile(Profile(
        name="Personalizado", match=MatchAny(), priority=10,
        rumble=RumbleConfig(policy="custom", custom_mult=1.4),
    ))
    draft = rodape._draft_do_ativo(
        "Personalizado", _ctx({"active_profile": "Personalizado"}))
    assert draft is not None

    prof = draft.to_profile("Personalizado", priority=10)
    assert prof.rumble.policy == "custom"
    assert prof.rumble.custom_mult == pytest.approx(1.4)
