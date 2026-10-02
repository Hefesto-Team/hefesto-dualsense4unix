"""O-APLICAR-E-A-ATIVACAO-SAO-UMA-SO-01 — o «Aplicar» e a ativação são uma só.

O defeito, medido (proposta A3 do relatório 04 da auditoria de 27/09): o
«Aplicar» mandava `profile.apply_draft` (o `DraftApplier`), e a ativação roda
`ProfileManager.activate`. Eram duas máquinas, e o «Aplicar» levava menos da
metade do perfil: ficavam de fora o volume e o ganho do microfone, os
sensores, a máscara, a mira, o modo e a política global de vibração.

A cura: `ProfileManager.reaplicar` roda a cadeia do `activate`, com todas as
camadas, sem os efeitos do gesto de escolha (a sessão, o marcador, o Modo
Freestyle e a trava da troca à mão); o `profile.reaplicar` do daemon o chama, e
o «Aplicar» do rodapé chama o `profile.reaplicar`.

A RÉGUA 1 enumera os campos de `Profile` e de `ControllerOverrides` PELO
ESQUEMA (nunca por lista digitada): cada campo é lido pela cadeia do
`reaplicar`, ou está em :data:`FORA` com a razão. O perfil passa por um espião
que anota cada campo que a cadeia LÊ; os quatro controles (dois no cabo, dois
no rádio: o gerente publica por `uniq`, e o transporte não entra na conta) têm
cada um os seus campos, e o controle de mentira anota o que chegou a cada um.

MORDIDA: tire `self.apply_controller_mascaras(...)` de
`ProfileManager.apply_emulation` e a régua nomeia `controllers.<uniq>.mascara`.
"""
from __future__ import annotations

import asyncio
from typing import Any

import pytest

from hefesto_dualsense4unix.core.controller import OutputSpec
from hefesto_dualsense4unix.daemon.state_store import StateStore
from hefesto_dualsense4unix.profiles import loader
from hefesto_dualsense4unix.profiles import manager as manager_mod
from hefesto_dualsense4unix.profiles.manager import ProfileManager
from hefesto_dualsense4unix.profiles.schema import (
    ControllerMicOverride,
    ControllerOverrides,
    ControllerRumbleOverride,
    ControllerSensoresOverride,
    LedsConfig,
    MatchCriteria,
    Profile,
    ProfileMicConfig,
    ProfileModeConfig,
    ProfileMouseConfig,
    ProfileMovimentoConfig,
    ProfileSpeakerConfig,
    RumbleConfig,
    TriggerConfig,
    TriggersConfig,
)
from hefesto_dualsense4unix.testing import FakeController
from hefesto_dualsense4unix.utils import session

#: Os quatro controles, da faixa forjada da casa: dois no cabo, dois no rádio.
CABO = ("aabbcc000001", "aabbcc000002")
RADIO = ("02fe00000003", "02fe00000004")
UNIQS = CABO + RADIO
NOME = "Jogo da Régua"

#: O que a cadeia da ativação NÃO aplica, e por quê. Cada linha é uma decisão;
#: um campo novo no esquema que a cadeia não lê e que não está aqui reprova.
FORA: dict[str, str] = {
    "name": "é o nome do arquivo, não um ajuste",
    "version": "é a versão do formato, não um ajuste",
    "match": "decide QUANDO o perfil entra (a seleção), não o que ele aplica",
    "priority": "decide QUEM ganha na seleção, não o que ele aplica",
    "ponte": "é o carimbo da escada do lançamento, lido por ela no jogo",
    # Medido por esta régua em 01/10/2026: a ativação nunca leu o campo. Quem o
    # lê é a entrada na Navegação (`Daemon.aplicar_o_arranjo_do_desktop`, por
    # `schema.resolver_teclado_emulado`), e a regra dela é que entrar na
    # Navegação não religa o teclado (D-2909-A-NAVEGACAO-NAO-RELIGA-O-TECLADO).
    "teclado_emulado": "é lido na entrada da Navegação, pelo arranjo do desktop",
}
FORA_POR_CONTROLE: dict[str, str] = {}


class _ControleQueAnota(FakeController):
    """O controle de mentira que anota o que chegou a cada `uniq`."""

    def __init__(self) -> None:
        super().__init__(transport="usb")
        self.padrao: list[OutputSpec] = []
        self.por_uniq: dict[str, OutputSpec] = {}

    def apply_output_defaults(self, spec: OutputSpec) -> None:
        self.padrao.append(spec)

    def reset_output_overrides(self, overrides: Any = None, **_kw: Any) -> None:
        self.por_uniq = dict(overrides or {})

    def apply_output_for(self, uniq: str, spec: OutputSpec, **_kw: Any) -> str:
        self.por_uniq[uniq] = spec
        return "escreveu"


def _espiao(modelo: Any, caminho: str, lidos: set[str]) -> Any:
    """O mesmo modelo, numa subclasse que anota cada CAMPO lido por atributo."""
    base = type(modelo)
    campos = frozenset(base.model_fields)

    class _Espia(base):  # type: ignore[valid-type,misc]
        def __getattribute__(self, nome: str) -> Any:
            if nome in campos:
                lidos.add(f"{caminho}{nome}")
            return super().__getattribute__(nome)

    _Espia.__name__ = base.__name__
    copia = _Espia.model_construct(_fields_set=modelo.model_fields_set,
                                   **dict(modelo.__dict__))
    return copia


def _o_perfil_inteiro() -> Profile:
    """Um perfil em que todo campo diz alguma coisa, nos quatro controles."""
    def _peca(n: int) -> ControllerOverrides:
        return ControllerOverrides(
            leds=LedsConfig(lightbar=(10 * n, 20, 30), lightbar_brightness=0.5,
                            player_led_brightness="forte"),
            triggers=TriggersConfig(left=TriggerConfig(mode="Rigid", params=[5, 200])),
            rumble=ControllerRumbleOverride(motor_forte_pct=50),
            speaker=ProfileSpeakerConfig(volume=40 + n, muted=False),
            mic=ControllerMicOverride(volume=30 + n),
            sensores=ControllerSensoresOverride(giroscopio=False),
            mascara="xbox" if n % 2 else "dualsense",
            movimento=ProfileMovimentoConfig(),
        )

    return Profile(
        name=NOME,
        match=MatchCriteria(window_class=["steam_app_480"]),
        priority=80,
        triggers=TriggersConfig(right=TriggerConfig(mode="Rigid", params=[5, 100])),
        leds=LedsConfig(lightbar=(1, 2, 3)),
        rumble=RumbleConfig(passthrough=True, policy="max"),
        key_bindings={"cross": ["KEY_ENTER"]},
        button_actions={"cross": "BTN_LEFT"},
        remapeamento={"cross": "circle"},
        movimento=ProfileMovimentoConfig(),
        mouse=ProfileMouseConfig(enabled=True, speed=7, scroll_speed=2),
        teclado_emulado=True,
        mic=ProfileMicConfig(button_toggles_system=False, volume=55),
        speaker=ProfileSpeakerConfig(volume=60, muted=False),
        mode=ProfileModeConfig(kind="gamepad", caminho="dualsense"),
        suppress_desktop_emulation=True,
        controllers={uniq: _peca(n) for n, uniq in enumerate(UNIQS, start=1)},
    )


def _anotador() -> tuple[dict[str, list[Any]], dict[str, Any]]:
    """Os appliers do daemon, de mentira: cada um anota o que recebeu."""
    chegou: dict[str, list[Any]] = {}

    def _anota(nome: str) -> Any:
        def _applier(*args: Any, **kwargs: Any) -> str:
            chegou.setdefault(nome, []).append((args, kwargs))
            return "aplicado"
        return _applier

    appliers = {
        nome: _anota(nome)
        for nome in ("mouse_applier", "suppression_applier", "mode_applier",
                     "rumble_policy_applier", "rumble_passthrough_applier",
                     "speaker_applier", "mic_applier")
    }
    return chegou, appliers


def _gerente(controle: _ControleQueAnota, store: StateStore) -> tuple[ProfileManager, Any]:
    chegou, appliers = _anotador()
    gerente = ProfileManager(controller=controle, store=store, **appliers)
    return gerente, chegou


def test_todo_campo_do_perfil_e_de_cada_controle_e_levado_pelo_aplicar(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Cada campo do esquema é lido pela cadeia do `reaplicar`, ou está em `FORA`.

    MORDIDA: tire a máscara do aplicador (`apply_controller_mascaras` em
    `apply_emulation`) e a régua nomeia o campo de cada controle.
    """
    loader.save_profile(_o_perfil_inteiro(), origem="régua")
    lidos: set[str] = set()

    def _carregar_espiado(nome: str) -> Profile:
        perfil = loader.load_profile(nome)
        controles = {
            uniq: _espiao(peca, f"controllers.{uniq}.", lidos)
            for uniq, peca in (perfil.controllers or {}).items()
        }
        espiado = _espiao(perfil, "", lidos)
        object.__setattr__(espiado, "controllers", controles)
        return espiado

    monkeypatch.setattr(manager_mod, "load_profile", _carregar_espiado)
    controle = _ControleQueAnota()
    gerente, chegou = _gerente(controle, StateStore())

    gerente.reaplicar(NOME)

    faltam = sorted(
        campo for campo in Profile.model_fields
        if campo not in lidos and campo not in FORA
    )
    for uniq in UNIQS:
        faltam += sorted(
            f"controllers.{uniq}.{campo}" for campo in ControllerOverrides.model_fields
            if f"controllers.{uniq}.{campo}" not in lidos
            and campo not in FORA_POR_CONTROLE
        )
    assert not faltam, (
        "o «Aplicar» (a cadeia da ativação) não leva estes campos, e nenhum está "
        "declarado fora com a razão:\n  " + "\n  ".join(faltam))
    assert set(controle.por_uniq) == set(UNIQS), (
        f"a luz e o gatilho por controle não chegaram aos quatro: {sorted(controle.por_uniq)}")
    for nome in ("mode_applier", "rumble_policy_applier", "mic_applier",
                 "speaker_applier", "suppression_applier", "mouse_applier"):
        assert chegou.get(nome), f"o {nome} não recebeu nada no «Aplicar»"


def test_o_aplicar_nao_e_escolha_nem_liga_o_freestyle() -> None:
    """O `reaplicar` não grava a sessão nem o marcador, e não mexe no Freestyle.

    MORDIDA: chame o `_ativar` do `reaplicar` com `e_a_escolha=True` e o
    `session.json` passa a dizer o perfil reaplicado.
    """
    loader.save_profile(_o_perfil_inteiro(), origem="régua")
    store = StateStore()
    gerente, _chegou = _gerente(_ControleQueAnota(), store)
    session.save_last_profile("A Escolha Dela")

    gerente.reaplicar(NOME)

    assert session.load_last_profile() == "A Escolha Dela", (
        "o «Aplicar» gravou a escolha dela")
    assert session.read_active_marker() is None, "o «Aplicar» escreveu o marcador"
    assert store.freestyle_ligado is False
    assert store.active_profile == NOME


def test_o_profile_reaplicar_do_daemon_nao_arma_a_trava_da_troca_a_mao() -> None:
    """O handler do `profile.reaplicar` responde como o switch e não arma a trava.

    MORDIDA: arme `mark_manual_profile_lock` no handler e a trava aparece.
    """
    import time

    from hefesto_dualsense4unix.daemon.ipc_handlers import IpcHandlersMixin

    loader.save_profile(_o_perfil_inteiro(), origem="régua")
    store = StateStore()
    gerente, chegou = _gerente(_ControleQueAnota(), store)

    class _Handlers(IpcHandlersMixin):
        def __init__(self) -> None:
            self.daemon = None  # type: ignore[assignment]
            self.store = store
            self.profile_manager = gerente

    resposta = asyncio.run(_Handlers()._handle_profile_reaplicar({"name": NOME}))

    assert resposta["active_profile"] == NOME
    assert resposta["mode_aplicado"] is True and "mode" in resposta["secoes"]
    assert not store.manual_profile_lock_active(time.monotonic()), (
        "o «Aplicar» armou a trava da troca à mão")
    (_args, kwargs), = chegou["mode_applier"]
    assert kwargs["origin"] == "manual", (
        "o «Aplicar» é gesto dela: a R-04 vale igual à da ativação")
