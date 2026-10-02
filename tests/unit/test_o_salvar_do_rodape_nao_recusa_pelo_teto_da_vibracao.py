#!/usr/bin/env python3
"""O «Salvar Perfil» do rodapé recusava com a máquina dela como está AGORA.

ACHADO ABRINDO A TELA E CLICANDO — 06/09/2026, ONDA5-07-02, com o daemon vivo
e um DualSense no cabo. O clique sintético em «Salvar Perfil» devolveu::

    [gesto falhou] 10-perfis.html · salvar: 1 validation error for RumbleConfig
      Value error, custom_mult só é válido com policy='custom'
      (policy='balanceado')

O daemon publica o teto de vibração como MEMÓRIA (`rumble_policy_custom_mult`
= 0,7, de quando o degrau era "custom") ao lado do degrau de hoje
(`balanceado`), e o Salvar copiava os dois soltos para o rascunho: o esquema
recusa o par, com razão (*"o valor seria silenciosamente ignorado pelo
daemon"*), e o perfil dela não era gravado.

DESDE 27/09 (`D-2709-O-SALVAR-LE-O-PERFIL`) o Salvar não lê a vibração do
aparelho: o teto lembrado não tem como chegar ao rascunho (§1). O teto É
escolha dela quando ela arrasta a barra «Personalizado» da coluna de um
controle, e quem o grava, junto com o degrau, é o gesto da aba Vibração
(`a05_vibracao._gravar_a_forca`), no clique (§2).

A MORDIDA: devolva ao ``rodape.salvar`` o degrau e o teto do daemon, soltos
(``policy`` e ``custom_mult`` do estado no rascunho), e o primeiro teste
reprova com a mesma `ValidationError` que a tela mostrou.
"""
from __future__ import annotations

from typing import Any

import pytest

from hefesto_dualsense4unix.profiles.schema import MatchAny, Profile
from tests.unit.ponte_do_rodape import PonteDoRodape

ESTADO_DELA = {
    "active_profile": "Personalizado",
    "rumble_policy": "balanceado",
    "rumble_passthrough": True,
    "rumble_policy_custom_mult": 0.7,
}

UNIQ = "aabbcc0000c1"


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


def _salvar(estado: dict[str, Any]) -> Profile:
    from hefesto_dualsense4unix.interface.pacotes import rodape
    from hefesto_dualsense4unix.profiles.loader import load_profile

    rodape.salvar(_ctx(estado), {"gesto": "salvar"}, PonteDoRodape())
    return load_profile("Personalizado")


class _Ponte:
    """O que o gesto da Vibração chama para reaplicar o perfil."""

    def profile_switch(self, nome: str) -> bool:
        return True

    def profile_reaplicar(self, nome: str) -> bool:
        return True

    def chamar(self, metodo: str, *a: Any, **kw: Any) -> Any:
        return True

    def resultado(self, metodo: str, *a: Any, **kw: Any) -> Any:
        return {}


def test_o_teto_lembrado_nao_derruba_o_salvar(disco: Any) -> None:
    """O caso EXATO da máquina dela: degrau "Balanceado", teto lembrado 0,7."""
    prof = _salvar(ESTADO_DELA)
    assert prof.rumble.policy is None, (
        f"o Salvar gravou a política do aparelho ({prof.rumble.policy!r}) num "
        "perfil sem opinião sobre ela")
    assert prof.rumble.custom_mult is None


def test_sob_custom_no_aparelho_o_salvar_nao_inventa_o_teto(disco: Any) -> None:
    """Nem sob "custom" o teto do aparelho vira escolha dela pelo Salvar."""
    prof = _salvar({**ESTADO_DELA, "rumble_policy": "custom"})
    assert (prof.rumble.policy, prof.rumble.custom_mult) == (None, None)


def test_o_teto_do_disco_sobrevive_ao_salvar(disco: Any) -> None:
    """Daemon dizendo outra coisa: o perfil sai com o par que o disco tinha."""
    from hefesto_dualsense4unix.profiles.loader import save_profile
    from hefesto_dualsense4unix.profiles.schema import RumbleConfig

    save_profile(Profile(
        name="Personalizado", match=MatchAny(), priority=10,
        rumble=RumbleConfig(policy="custom", custom_mult=1.4),
    ))
    prof = _salvar({"active_profile": "Personalizado", "rumble_policy": "balanceado"})
    assert prof.rumble.policy == "custom"
    assert prof.rumble.custom_mult == pytest.approx(1.4)


def test_a_barra_personalizada_grava_o_teto_com_o_degrau(disco: Any) -> None:
    """Arrastar a barra grava `custom` e o número; outro degrau tira o número."""
    from hefesto_dualsense4unix.interface.pacotes import a05_vibracao

    from hefesto_dualsense4unix.profiles.o_padrao_do_computador import (
        carregar_o_que_vale,
    )

    ctx = _ctx({"active_profile": "Personalizado"})
    a05_vibracao._gravar_a_forca(ctx, _Ponte(), UNIQ, "custom", custom=0.7)
    dele = carregar_o_que_vale("Personalizado").controllers[UNIQ].rumble
    assert (dele.policy, dele.custom_mult) == ("custom", pytest.approx(0.7))

    a05_vibracao._gravar_a_forca(ctx, _Ponte(), UNIQ, "max")
    dele = carregar_o_que_vale("Personalizado").controllers[UNIQ].rumble
    assert dele.policy == "max" and dele.custom_mult is None, (
        f"o degrau novo levou o teto do antigo: {dele}")
