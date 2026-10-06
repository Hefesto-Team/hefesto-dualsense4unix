"""Salvar não pode desfazer o que a aba já gravou.

MEDIDO EM 05/09/2026, atrás do  Um ciclo inteiro — perfil no disco, ela configura nas
abas 02, 04, 05 e 06, volta e clica **Salvar** no rodapé — mostrou que **5 de
11 campos sobreviviam**, e que três deles não se perdiam por esquecimento: o
produto já tinha gravado o valor certo no disco e o Salvar o **desfazia**.

AS DUAS CAUSAS DE 05/09, e onde cada uma mora hoje:

1. ``lightbar_brightness`` e ``player_leds`` do override — o Salvar montava a
   luz DAQUELE controle com a seção GLOBAL. Desde 27/09
   (`D-2709-O-SALVAR-LE-O-PERFIL`) o Salvar não monta luz nenhuma: ele lê o
   disco, e o override sai como a aba 04 o gravou (§1).
2. ``button_actions`` e ``teclado_emulado`` — ``DraftConfig.to_profile`` não
   os emitia, e todo Salvar os zerava. A cura é do ``to_profile``, e o Salvar
   de hoje passa por ele (§2).

E O QUE O APARELHO PUBLICA NÃO ENTRA (§3): cada aba grava a escolha do usuário no
clique (o som na 02, a luz na 04, a força na 05, o mouse na 06, o sensor pelo
``sensor.set`` do daemon), e o Salvar regrava isso, com o aparelho dizendo
outra coisa.

A MORDIDA, por seção:

- devolva ao ``rodape.salvar`` a luz acesa por cima do disco (a cor e o
  brilho do aparelho no override) e §1 reprova;
- apague a linha ``button_actions=self.source_button_actions`` de
  ``to_profile`` e :func:`test_as_acoes_de_botao_sobrevivem_ao_salvar` reprova;
- devolva ao ``rodape.salvar`` o microfone do aparelho e §3 reprova no
  ``mic.muted``.

Irmão deste arquivo: ``test_salvar_nao_apaga_a_cor.py``.
"""

from __future__ import annotations

from typing import Any

import pytest

from tests.conftest import exigir_gi_real
from tests.unit.ponte_do_rodape import PonteDoRodape

exigir_gi_real("importa `interface.pacotes`, que carrega o GTK")

from hefesto_dualsense4unix.interface.pacotes import rodape

UNIQ = "aabbcc0000ff"

#: elas: o esquema do disco guarda 0,0-1,0 (`LedsConfig.lightbar_brightness`) e
BRILHO_DELA_NO_DISCO = 0.25
LAMPADAS_DELAS = (True, True, False, False, False)
COR_DELA = (0, 0, 255)


class _Ctx:
    """O mínimo de ``Contexto`` que o «Salvar» do rodapé recebe."""

    def __init__(self, conectados: list[dict[str, Any]],
                 state: dict[str, Any] | None = None) -> None:
        self.conectados = conectados
        self.mesa = conectados
        self.state = state or {}


COR_ACESA = (255, 0, 255)


def _controle_aceso() -> dict[str, Any]:
    """Um controle com a barra ACESA noutra cor e noutro brilho que o disco."""
    return {"uniq": UNIQ, "lightbar_rgb": list(COR_ACESA),
            "lightbar_on": True, "lightbar_source": "sysfs",
            "brilho_da_barra": 0.9, "brilho_das_luzes": "forte"}


def _salvar(perfil: str, ctx: _Ctx) -> Any:
    """O «Salvar Perfil» do rodapé com este perfil valendo, e o que ficou no disco."""
    from hefesto_dualsense4unix.profiles.loader import load_profile

    ctx.state = {**ctx.state, "active_profile": perfil}
    rodape.salvar(ctx, {"gesto": "salvar"}, PonteDoRodape())
    return load_profile(perfil)


@pytest.fixture
def perfil_configurado(monkeypatch: pytest.MonkeyPatch) -> str:
    """Um perfil no disco de mentira com os cinco campos JÁ gravados."""
    from hefesto_dualsense4unix.profiles.loader import load_profile, save_profile
    from hefesto_dualsense4unix.profiles.schema import (
        ControllerOverrides, LedsConfig, MatchAny, Profile,
    )

    nome = "perfil-que-ela-configurou"
    p = Profile(name=nome, match=MatchAny(), priority=100)
    p.controllers = {UNIQ: ControllerOverrides(leds=LedsConfig(
        lightbar=COR_DELA,
        lightbar_brightness=BRILHO_DELA_NO_DISCO,
        player_leds=list(LAMPADAS_DELAS),
    ))}
    p.button_actions = {"circle": "KEY_ESC"}
    p.teclado_emulado = True
    save_profile(p, origem="teste")

    de_volta = load_profile(nome)
    assert de_volta.controllers[UNIQ].leds.lightbar_brightness == BRILHO_DELA_NO_DISCO
    assert de_volta.button_actions == {"circle": "KEY_ESC"}
    return nome


def _leds_gravados(prof: Any) -> Any:
    """A seção ``leds`` que o disco guarda PARA ESTE controle."""
    dono = (prof.controllers or {}).get(UNIQ)
    assert dono is not None and getattr(dono, "leds", None) is not None, (
        "o disco perdeu o override deste controle — a régua mediria o vazio")
    return dono.leds


def test_o_brilho_daquele_controle_sobrevive_ao_salvar(
        perfil_configurado: str) -> None:
    """O brilho do override é DELE: nem o global de 100, nem o aceso de 90."""
    salvo = _salvar(perfil_configurado, _Ctx([_controle_aceso()]))
    assert _leds_gravados(salvo).lightbar_brightness == BRILHO_DELA_NO_DISCO, (
        "o Salvar regravou outro brilho por cima do que a aba 04 gravou para "
        "este controle")


def test_as_lampadas_daquele_controle_sobrevivem_ao_salvar(
        perfil_configurado: str) -> None:
    """As cinco lâmpadas são do override, e não as do global."""
    salvo = _salvar(perfil_configurado, _Ctx([_controle_aceso()]))
    assert tuple(_leds_gravados(salvo).player_leds) == LAMPADAS_DELAS, (
        "o Salvar apagou as lâmpadas deste controle com as do global")


def test_a_cor_acesa_nao_vence_o_disco(perfil_configurado: str) -> None:
    """A cor que o aparelho acende não é a escolha do usuário; a do disco é.

    Até 27/09 a cor viva vencia o disco no Salvar (medido em 01/09, quando o
    clique na cor ainda não gravava). Desde 09/09 o clique grava
    (`a04_iluminacao._guardar_a_cor_no_perfil`, medido em
    `test_a_cor_escolhida_vai_ao_disco_e_o_trilho_nao_reescala.py`), e a luz
    acesa que difere do disco é camada, teto ou automático.
    """
    salvo = _salvar(perfil_configurado, _Ctx([_controle_aceso()]))
    assert tuple(_leds_gravados(salvo).lightbar) == COR_DELA, (
        f"o Salvar gravou a cor acesa {COR_ACESA} como a escolha dela")


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
    """Salvar COM OUTRO NOME leva os dois junto — eles são config, não regra."""
    saiu = _round_trip("um-nome-que-nao-existia", perfil_configurado)
    assert saiu.button_actions == {"circle": "KEY_ESC"}
    assert saiu.teclado_emulado is True


VIVO_DA_PECA: dict[str, Any] = {
    "speaker": {"volume": 30, "muted": True},
    "audio": {"mic_mudo": False, "volume_captura": 90},
    "sensores": {"giroscopio_ligado": True, "acelerometro_ligado": False},
}

VIVO_DA_MESA: dict[str, Any] = {
    "rumble_policy": "economia",
    "rumble_passthrough": True,
    "rumble_policy_custom_mult": 0.7,
    "mouse_emulation": {"enabled": False, "speed": 3, "scroll_speed": 1},
}


@pytest.fixture
def perfil_das_abas(perfil_configurado: str) -> str:
    """O perfil como as abas o deixam, cada uma no seu clique.

    A 02 grava o alto-falante e o microfone (`_lembrar_do_som`), o sensor
    desligado vai pelo `sensor.set` do daemon, a 05 a política e a 06 o mouse.
    """
    from hefesto_dualsense4unix.profiles.loader import load_profile, save_profile
    from hefesto_dualsense4unix.profiles.schema import (
        ControllerMicOverride,
        ControllerSensoresOverride,
        ProfileMouseConfig,
        ProfileSpeakerConfig,
        RumbleConfig,
    )

    p = load_profile(perfil_configurado)
    dele = p.controllers[UNIQ].model_copy(update={
        "speaker": ProfileSpeakerConfig(volume=102, muted=False),
        "mic": ControllerMicOverride(muted=True, volume=44),
        "sensores": ControllerSensoresOverride(giroscopio=False),
    })
    save_profile(p.model_copy(update={
        "controllers": {UNIQ: dele},
        "rumble": RumbleConfig(policy="max", passthrough=False),
        "mouse": ProfileMouseConfig(enabled=True, speed=11, scroll_speed=4),
    }), origem="teste")
    return perfil_configurado


def _ctx_do_aparelho() -> _Ctx:
    controle = _controle_aceso()
    controle.update(VIVO_DA_PECA)
    return _Ctx([controle], state=dict(VIVO_DA_MESA))


@pytest.mark.parametrize(("campo", "esperado"), [
    ("speaker.volume", 102),
    ("speaker.muted", False),
    ("mic.muted", True),
    ("mic.volume", 44),
    ("sensores.giroscopio", False),
    ("sensores.acelerometro", None),
])
def test_o_que_a_aba_gravou_por_peca_sobrevive_ao_salvar(
        perfil_das_abas: str, campo: str, esperado: Any) -> None:
    """O alto-falante, o microfone e os sensores daquela peça saem como a aba os gravou."""
    salvo = _salvar(perfil_das_abas, _ctx_do_aparelho())
    secao, chave = campo.split(".")
    cfg = getattr(salvo.controllers[UNIQ], secao, None)
    assert cfg is not None, f"o Salvar apagou a seção `{secao}` desta peça"
    assert getattr(cfg, chave) == esperado, (
        f"`{campo}` saiu {getattr(cfg, chave)!r} do Salvar, e a aba gravou "
        f"{esperado!r} — o aparelho entrou no disco")


@pytest.mark.parametrize(("caminho", "esperado"), [
    ("rumble.policy", "max"),
    ("rumble.passthrough", False),
    ("rumble.custom_mult", None),
    ("mouse.speed", 11),
    ("mouse.scroll_speed", 4),
    ("mouse.enabled", True),
])
def test_o_que_e_da_mesa_inteira_sobrevive_ao_salvar(
        perfil_das_abas: str, caminho: str, esperado: Any) -> None:
    """A política de vibração e o mouse saem como o disco os tinha."""
    salvo = _salvar(perfil_das_abas, _ctx_do_aparelho())
    secao, chave = caminho.split(".")
    assert getattr(getattr(salvo, secao), chave) == esperado
