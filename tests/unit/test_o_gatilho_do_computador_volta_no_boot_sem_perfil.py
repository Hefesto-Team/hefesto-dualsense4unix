"""D-1810-A-LUZ-E-O-GATILHO-LEEM-O-COMPUTADOR-SEM-PERFIL-ATIVO: o gatilho guardado volta no boot.

Medido antes de curar (25/11/2026), com o `restore_last_profile` do produto e um backend de mentira
que anota cada chamada: sem perfil e sem Freestyle, o efeito e a intensidade do gatilho de cada
controle estavam no `maquina.json` e a aba os pintava, mas o boot registrava `boot_sem_escolha` e
voltava; o backend não recebia nenhuma chamada de gatilho (zero efeitos, zero escalas). O lar é de
mentira (o `conftest` desvia `HOME` e os `XDG_*`).

A cura: o boot sem escolha leva ao aparelho a parte do computador que a vista sem perfil devolve
para os gatilhos (o efeito de cada controle, a intensidade e o global), sem luz, sem sessão e sem
virar escolha; no Nativo, ou com um perfil já valendo, não toca nada.

MORDIDAS: arrancar a chamada `devolver_os_gatilhos_do_computador` do ramo `boot_sem_escolha`
reprova todos os casos de aplicar; arrancar o teste do `_native_mode` reprova o do Nativo;
arrancar o do `active_profile` reprova o do perfil que já vale; trocar o
`reset_profile_overrides` por nada reprova o efeito de cada controle.
"""
from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any

from hefesto_dualsense4unix.daemon import connection
from hefesto_dualsense4unix.daemon.state_store import StateStore
from hefesto_dualsense4unix.profiles.o_padrao_do_computador import gravar_pelo_gesto
from hefesto_dualsense4unix.profiles.schema import (
    ControllerOverrides,
    TriggerConfig,
    TriggersConfig,
)

CABO = "aabbcc000001"
RADIO = "aabbcc000002"
SEM_NADA = "aabbcc000003"


class _Backend:
    """O backend de mentira: anota o que o boot entrega, sem tocar aparelho nenhum."""

    def __init__(self) -> None:
        self.padrao: list[Any] = []
        self.camada: list[dict[str, Any]] = []
        self.escalas: list[Any] = []
        self.por_controle: list[tuple[str, Any]] = []

    def apply_output_defaults(self, spec: Any) -> str:
        self.padrao.append(spec)
        return "aplicado"

    def reset_profile_overrides(self, overrides: Any = None, *, procedencias: Any = None) -> None:
        self.camada.append(dict(overrides or {}))

    def set_trigger_scales(self, escalas: Any = None) -> None:
        self.escalas.append(dict(escalas) if escalas else None)

    def apply_output_for(self, uniq: str, spec: Any, **_: Any) -> str:
        self.por_controle.append((uniq, spec))
        return "aplicado"

    def __getattr__(self, nome: str) -> Any:
        def nada(*a: Any, **k: Any) -> None:
            return None

        return nada


def _guardar_no_computador() -> None:
    """Um efeito e uma intensidade por controle, no `maquina.json`, sem perfil: o cabo guarda o
    esquerdo e a intensidade, o rádio o direito, e o terceiro nada."""
    gravar_pelo_gesto(
        "gatilho", "",
        lambda v: v.model_copy(update={"controllers": {
            CABO: ControllerOverrides(triggers=TriggersConfig(
                left=TriggerConfig(mode="Galloping", params=[0, 9, 7, 7, 10]),
                intensidade=0.5))}}),
        uniq=CABO)
    gravar_pelo_gesto(
        "gatilho", "",
        lambda v: v.model_copy(update={"controllers": {
            RADIO: ControllerOverrides(triggers=TriggersConfig(
                right=TriggerConfig(mode="Rigid", params=[5, 200])))}}),
        uniq=RADIO)


def _boot(backend: _Backend, *, nativo: bool = False, ativo: str | None = None) -> StateStore:
    store = StateStore()
    if ativo is not None:
        store.set_active_profile(ativo)

    async def bloqueante(fn: Any, *args: Any) -> Any:
        return fn(*args)

    daemon = SimpleNamespace(
        controller=backend, store=store, _run_blocking=bloqueante,
        _native_mode=nativo, _keyboard_device=None)
    asyncio.run(connection.restore_last_profile(daemon))  # type: ignore[arg-type]
    return store


def test_o_boot_sem_perfil_leva_o_efeito_de_cada_controle_ao_aparelho() -> None:
    _guardar_no_computador()
    backend = _Backend()
    store = _boot(backend)

    assert store.active_profile is None, "o boot não pode virar escolha"
    assert len(backend.camada) == 1, f"a camada dos controles não foi entregue: {backend.camada}"
    camada = backend.camada[0]
    assert set(camada) == {CABO, RADIO}, f"controles com efeito guardado: {sorted(camada)}"
    assert camada[CABO].trigger_left is not None and camada[CABO].trigger_right is None
    assert camada[RADIO].trigger_right is not None and camada[RADIO].trigger_left is None
    assert type(camada[CABO].trigger_left).__name__ != type(camada[RADIO].trigger_right).__name__
    assert all(s.led is None and s.player_leds is None for s in camada.values()), (
        "o boot sem perfil só leva gatilho; a luz não é desta cura")


def test_o_boot_sem_perfil_leva_a_intensidade_de_cada_controle() -> None:
    _guardar_no_computador()
    backend = _Backend()
    _boot(backend)

    assert backend.escalas == [{CABO: 0.5}], (
        f"a intensidade guardada no computador não chegou ao backend: {backend.escalas}")


def test_o_boot_sem_perfil_leva_o_global_sem_luz() -> None:
    backend = _Backend()
    _boot(backend)

    assert len(backend.padrao) == 1
    spec = backend.padrao[0]
    assert spec.trigger_left is not None and spec.trigger_right is not None
    assert spec.led is None and spec.player_leds is None and spec.mic_led is None


def test_cada_controle_leva_o_proprio_efeito_e_nao_o_do_primeiro() -> None:
    _guardar_no_computador()
    backend = _Backend()
    _boot(backend)

    camada = backend.camada[0]
    assert SEM_NADA not in camada, "o controle sem efeito guardado recebeu o de outro"
    assert camada[CABO] != camada[RADIO]


def test_no_nativo_o_servico_nao_toca_o_gatilho() -> None:
    _guardar_no_computador()
    backend = _Backend()
    _boot(backend, nativo=True)

    assert backend.padrao == [] and backend.camada == [] and backend.escalas == [], (
        "no Modo Nativo o serviço escreveu no gatilho")


def test_com_um_perfil_ja_valendo_o_computador_nao_passa_por_cima() -> None:
    _guardar_no_computador()
    backend = _Backend()
    _boot(backend, ativo="Jogo")

    assert backend.padrao == [] and backend.camada == [] and backend.escalas == [], (
        "o gatilho do computador foi por cima do perfil que já valia")


def test_o_backend_sem_camada_cai_no_apply_output_for() -> None:
    _guardar_no_computador()
    backend = _Backend()
    backend.reset_profile_overrides = None  # type: ignore[assignment,method-assign]
    _boot(backend)

    assert {u for u, _s in backend.por_controle} == {CABO, RADIO}
