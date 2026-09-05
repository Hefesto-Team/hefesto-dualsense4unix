"""Salvar não pode desfazer o que a aba já gravou — os TRÊS campos atropelados.

MEDIDO EM 05/09/2026, atrás do pedido dela: *"aplicar aplica todas as configs
naquele perfil e salvar se lembra disso quando eu for jogar o jogo e no dia
seguinte e por diante"*. Um ciclo inteiro — perfil no disco, ela configura nas
abas 02, 04, 05 e 06, volta e clica **Salvar** no rodapé — mostrou que **5 de
11 campos sobreviviam**, e que três deles não se perdiam por esquecimento: o
produto já tinha gravado o valor certo no disco e o Salvar o **desfazia**.

OS TRÊS, e as duas causas:

1. ``lightbar_brightness`` e ``player_leds`` — ``rodape._draft_do_ativo``
   montava o override DAQUELE controle lendo ``draft.leds.*``, que é a seção
   **GLOBAL**. Só a cor vinha do controle certo. Com a aba 04 tendo gravado
   brilho 0,25 e as lâmpadas 1 e 2 do P1, o Salvar regravava o cheio e as cinco
   apagadas. A cura é chamar ``effective_leds_for(uniq)``, que já existia,
   já é público e já faz o merge POR CAMPO.

2. ``button_actions`` e ``teclado_emulado`` — ``DraftConfig.to_profile`` monta
   o ``Profile(...)`` com catorze campos e **estes dois não estavam lá**; os
   nomes apareciam ZERO vezes no arquivo. Todo Salvar os zerava, mesmo no
   round-trip mais favorável (mesmo nome). E o alcance passava da interface
   nova: ``footer_actions.py`` (janela GTK) e ``profiles_actions.py`` (aba
   Perfis) chamam o mesmo método.

A MORDIDA, campo por campo:

- troque ``efetivo.lightbar_brightness`` de volta por
  ``draft.leds.lightbar_brightness`` em ``rodape._draft_do_ativo`` e
  :func:`test_o_brilho_daquele_controle_sobrevive_ao_salvar` reprova;
- idem com ``player_leds`` e
  :func:`test_as_lampadas_daquele_controle_sobrevivem_ao_salvar`;
- apague a linha ``button_actions=self.source_button_actions`` de
  ``to_profile`` e :func:`test_as_acoes_de_botao_sobrevivem_ao_salvar` reprova.

Irmão deste arquivo, mesma função e mesmo dia de origem diferente:
``test_salvar_nao_apaga_a_cor_dela.py``.
"""

from __future__ import annotations

from typing import Any

import pytest

from hefesto_dualsense4unix.interface.pacotes import rodape

#: O ENDEREÇO DE RÁDIO DA BANCADA, com a máscara da casa (octetos 4 e 5
#: zerados), e SEM os dois-pontos — é assim que o daemon publica o `uniq` e
#: assim que o mapa `source_controllers` o guarda. Pedir com dois-pontos não
#: dá erro: dá override nenhum, que se lê como "a cura não gravou".
UNIQ = "aabbcc0000ff"

#: O QUE ELA CONFIGUROU NAQUELE CONTROLE, e nenhum destes é o default do
#: esquema — um valor igual ao default não distingue "sobreviveu" de "nasceu
#: assim", que é a forma mais fácil de uma régua desta família dar verde sobre
#: o defeito.
#: DUAS UNIDADES PARA O MESMO BRILHO, e a régua atravessa a fronteira entre
#: elas: o esquema do disco guarda 0,0-1,0 (`LedsConfig.lightbar_brightness`) e
#: o rascunho da GUI guarda 0-100 inteiro (`LedsDraft`). Escrever 25 no disco
#: não dá "brilho de 25%" — dá `ValidationError`.
BRILHO_DELA_NO_DISCO = 0.25
LAMPADAS_DELAS = (True, True, False, False, False)
COR_DELA = (0, 0, 255)


class _Ctx:
    """O mínimo de ``Contexto`` que ``_draft_do_ativo`` lê."""

    def __init__(self, conectados: list[dict[str, Any]],
                 state: dict[str, Any] | None = None) -> None:
        self.conectados = conectados
        self.state = state or {}


def _controle_aceso() -> dict[str, Any]:
    """Um controle com a barra ACESA — o único estado em que há cor a gravar.

    Com a barra apagada `_draft_do_ativo` sai fora antes do `with_controller_leds`
    (é o que o arquivo irmão mede), e o override nem chega a ser montado: a
    régua daria verde sem exercitar uma linha do que se quer medir.
    """
    return {"uniq": UNIQ, "lightbar_rgb": list(COR_DELA),
            "lightbar_on": True, "lightbar_source": "sysfs"}


@pytest.fixture
def perfil_configurado(monkeypatch: pytest.MonkeyPatch) -> str:
    """Um perfil no disco de mentira com os cinco campos JÁ gravados.

    É o estado real depois de ela passar pelas abas: a 04 grava brilho e
    lâmpadas por controle no clique, a 06 grava as ações de botão. O disco
    chega ao rodapé assim, e é isto que o Salvar não pode desfazer.
    """
    from hefesto_dualsense4unix.profiles.loader import load_profile, save_profile
    from hefesto_dualsense4unix.profiles.schema import (
        ControllerOverrides, LedsConfig, MatchAny, Profile,
    )

    nome = "perfil-que-ela-configurou"
    p = Profile(name=nome, match=MatchAny(), priority=100)
    # A ABA 04, no clique: o override DAQUELE controle, com os três campos.
    p.controllers = {UNIQ: ControllerOverrides(leds=LedsConfig(
        lightbar=COR_DELA,
        lightbar_brightness=BRILHO_DELA_NO_DISCO,
        player_leds=list(LAMPADAS_DELAS),
    ))}
    # A ABA 06, no clique.
    p.button_actions = {"circle": "KEY_ESC"}
    p.teclado_emulado = True
    save_profile(p, origem="teste")

    de_volta = load_profile(nome)
    assert de_volta.controllers[UNIQ].leds.lightbar_brightness == BRILHO_DELA_NO_DISCO
    assert de_volta.button_actions == {"circle": "KEY_ESC"}
    return nome


def _leds_gravados(draft: Any) -> Any:
    """A seção ``leds`` que o rascunho levaria ao disco PARA ESTE controle."""
    dono = draft.controller_override(UNIQ)
    assert dono is not None and getattr(dono, "leds", None) is not None, (
        "o rascunho não montou override nenhum para este controle — a régua "
        "mediria o vazio")
    return dono.leds


# --------------------------------------------------------------------------
# 1. o rodapé para de atropelar o override com a seção global
# --------------------------------------------------------------------------
def test_o_brilho_daquele_controle_sobrevive_ao_salvar(
        perfil_configurado: str) -> None:
    """O brilho do override é DELE, e não o global de 100."""
    ctx = _Ctx([_controle_aceso()])
    draft = rodape._draft_do_ativo(perfil_configurado, ctx)
    assert draft is not None
    assert _leds_gravados(draft).lightbar_brightness == BRILHO_DELA_NO_DISCO, (
        "o Salvar regravou o brilho GLOBAL por cima do que a aba 04 gravou "
        "para este controle")


def test_as_lampadas_daquele_controle_sobrevivem_ao_salvar(
        perfil_configurado: str) -> None:
    """As cinco lâmpadas são do override, e não as do global."""
    ctx = _Ctx([_controle_aceso()])
    draft = rodape._draft_do_ativo(perfil_configurado, ctx)
    assert draft is not None
    assert tuple(_leds_gravados(draft).player_leds) == LAMPADAS_DELAS, (
        "o Salvar apagou as lâmpadas deste controle com as do global")


def test_a_cor_viva_continua_vencendo_o_disco(perfil_configurado: str) -> None:
    """A cura não pode desfazer o que o rodapé JÁ acertava.

    O ponto inteiro de `_draft_do_ativo` é a cor VIVA vencer o disco (medido
    em 01/09). Se `effective_leds_for` passasse a mandar nos três campos, a
    cura de hoje quebraria a de 01/09 — e o defeito voltaria pelo outro lado.
    """
    viva = (255, 0, 255)
    controle = _controle_aceso()
    controle["lightbar_rgb"] = list(viva)
    draft = rodape._draft_do_ativo(perfil_configurado, _Ctx([controle]))
    assert draft is not None
    assert tuple(_leds_gravados(draft).lightbar) == viva, (
        "a cor que está acesa AGORA deixou de vencer o disco")


# --------------------------------------------------------------------------
# 2. os dois campos que o `to_profile` não emitia
# --------------------------------------------------------------------------
def _round_trip(nome_de_saida: str, perfil: str) -> Any:
    """Disco → `DraftConfig` → `Profile`, que é o caminho de todo Salvar."""
    from hefesto_dualsense4unix.app.draft_config import DraftConfig
    from hefesto_dualsense4unix.profiles.loader import load_profile

    return DraftConfig.from_profile(load_profile(perfil)).to_profile(nome_de_saida)


def test_as_acoes_de_botao_sobrevivem_ao_salvar(perfil_configurado: str) -> None:
    """`button_actions` atravessa o round-trip com o mesmo nome."""
    saiu = _round_trip(perfil_configurado, perfil_configurado)
    assert saiu.button_actions == {"circle": "KEY_ESC"}, (
        "o Salvar zerou as ações de botão que a aba 06 gravou")


def test_o_teclado_emulado_sobrevive_ao_salvar(perfil_configurado: str) -> None:
    """`teclado_emulado` atravessa o round-trip — e ela nem precisa tocá-lo."""
    saiu = _round_trip(perfil_configurado, perfil_configurado)
    assert saiu.teclado_emulado is True, (
        "o Salvar zerou o `teclado_emulado`, que ela nem tinha tocado")


def test_os_dois_viajam_com_nome_novo(perfil_configurado: str) -> None:
    """Salvar COM OUTRO NOME leva os dois junto — eles são config, não regra.

    É a decisão do R-11 aplicada: `match`/`mode`/`priority` são identidade do
    perfil e ficam; `controllers`, `key_bindings` e agora estes dois são
    configuração DELA e viajam, porque "Salvar como" significa *"guarde o que
    eu tenho agora"*.
    """
    saiu = _round_trip("um-nome-que-nao-existia", perfil_configurado)
    assert saiu.button_actions == {"circle": "KEY_ESC"}
    assert saiu.teclado_emulado is True
