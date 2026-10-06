"""ALLOWLIST-SO-A-MASCARA-01 — a máscara do perfil atravessa a allowlist; o `kind`, não."""
from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from hefesto_dualsense4unix.daemon import launch_env as le


class _DaemonDeMesa:
    """A bancada: emulação ligada, quatro vpads uinput, máscara `xbox`."""

    def __init__(
        self,
        *,
        emulacao: bool = True,
        vpad: bool = True,
        native: bool = False,
        flavor_vivo: str = "xbox",
        tem_applier: bool = True,
    ) -> None:
        self.chamadas: list[tuple[Any, Any, str]] = []
        self.config = SimpleNamespace(
            gamepad_emulation_enabled=emulacao, gamepad_flavor=flavor_vivo
        )
        self._gamepad_device = SimpleNamespace(backend="uinput") if vpad else None
        self._coop_manager = None
        self.controller = SimpleNamespace()
        self._native = native
        if tem_applier:
            self.apply_profile_mode = self._apply_profile_mode  # type: ignore[method-assign]

    def is_native_mode(self) -> bool:
        return self._native

    def _apply_profile_mode(
        self, mode: Any, *, profile: Any = None, origin: str = "autoswitch"
    ) -> str:
        self.chamadas.append((mode, profile, origin))
        return "aplicado"


def _modo(kind: str | None, flavor: str | None = "dualsense") -> Any:
    if kind is None:
        return None
    return SimpleNamespace(kind=kind, gamepad_flavor=flavor, coop=True)


PERFIL = SimpleNamespace(name="Sackboy")


def test_na_allowlist_a_mascara_do_perfil_chega_ao_applier() -> None:
    """A metade que a medição de 22/08 derrubou."""
    daemon = _DaemonDeMesa()
    aplicar = le._mode_applier_so_a_mascara(daemon)

    devolvido = aplicar(_modo("gamepad", "dualsense"), profile=PERFIL, origin="launch")

    assert devolvido == "aplicado"
    assert len(daemon.chamadas) == 1, (
        "a máscara do perfil não chegou ao `apply_profile_mode`. Com o físico "
        "escondido o vpad é tudo o que o jogo tem, e um vpad Xbox não tem "
        "touchpad, giroscópio nem acelerômetro no descritor HID"
    )
    mode, profile, origin = daemon.chamadas[0]
    assert getattr(mode, "gamepad_flavor", None) == "dualsense"
    assert profile is PERFIL and origin == "launch", (
        "o embrulho tem de repassar QUEM mandou e de ONDE — sem isso o applier "
        "não distingue perfil do jogo de catch-all (R-02)"
    )


def test_quem_escreve_a_mascara_continua_sendo_o_applier_do_daemon() -> None:
    """Não é um segundo escritor: o embrulho só decide se a chamada acontece."""
    daemon = _DaemonDeMesa()

    def _adiado(mode: Any, *, profile: Any = None, origin: str = "launch") -> str:
        daemon.chamadas.append((mode, profile, origin))
        return "adiado_jogo_aberto"

    daemon.apply_profile_mode = _adiado  # type: ignore[method-assign, assignment]

    devolvido = le._mode_applier_so_a_mascara(daemon)(
        _modo("gamepad"), profile=PERFIL, origin="launch"
    )

    assert devolvido == "adiado_jogo_aberto", (
        "o embrulho engoliu o veredito do gate R-04. O relatório da ativação "
        "passaria a dizer `aplicado` para uma máscara que não trocou"
    )


@pytest.mark.parametrize("kind", ["native", "desktop", None])
def test_na_allowlist_o_kind_que_e_pura_disputa_nao_passa(kind: str | None) -> None:
    """`native`/`desktop` são disputa pura, e `None` não traz máscara nenhuma."""
    daemon = _DaemonDeMesa()

    devolvido = le._mode_applier_so_a_mascara(daemon)(
        _modo(kind), profile=PERFIL, origin="launch"
    )

    assert devolvido == le.IGNORADO_DISPUTA_DA_ALLOWLIST
    assert daemon.chamadas == [], (
        f"`kind={kind}` atravessou a allowlist. Isso é largar o físico, soltar "
        "o grab ou desligar o vpad — a disputa pelo controle que ela decidiu pular"
    )


@pytest.mark.parametrize(
    ("rotulo", "mesa"),
    [
        ("emulacao_desligada", {"emulacao": False}),
        ("sem_vpad_de_pe", {"vpad": False}),
        ("modo_nativo_ligado", {"native": True}),
    ],
)
def test_fora_da_precondicao_nem_a_mascara_passa(
    rotulo: str, mesa: dict[str, Any]
) -> None:
    """A precondição é o que garante que SÓ a máscara passa — e é medida, não confiada."""
    daemon = _DaemonDeMesa(**mesa)

    devolvido = le._mode_applier_so_a_mascara(daemon)(
        _modo("gamepad"), profile=PERFIL, origin="launch"
    )

    assert devolvido == le.IGNORADO_DISPUTA_DA_ALLOWLIST
    assert daemon.chamadas == [], (
        f"com {rotulo} o embrulho chamou o applier — e aí não é mais só a "
        "máscara que passa: é ligar o vpad, que é a disputa pelo controle"
    )


def test_daemon_sem_applier_nao_derruba_a_ativacao() -> None:
    """Dublê da suíte e rota de CLI sem daemon existem, e não podem levantar."""
    daemon = _DaemonDeMesa(tem_applier=False)

    assert le._mode_applier_so_a_mascara(daemon)(
        _modo("gamepad"), profile=PERFIL, origin="launch"
    ) == le.IGNORADO_DISPUTA_DA_ALLOWLIST


def test_o_estado_barrado_e_distinguivel_de_aplicado_e_de_falhou() -> None:
    """Sem palavra própria, o journal não diz qual dos quatro aconteceu."""
    from hefesto_dualsense4unix.daemon.lifecycle import (
        ADIADO_JOGO_ABERTO,
        APLICADO,
        IGNORADO_GESTO_DELA,
    )

    barrado = le.IGNORADO_DISPUTA_DA_ALLOWLIST
    assert barrado.startswith("ignorado_"), (
        "o dialeto do `lifecycle` é `ignorado_*`; sair dele quebra quem filtra "
        "o journal por prefixo"
    )
    assert barrado not in {APLICADO, ADIADO_JOGO_ABERTO, IGNORADO_GESTO_DELA, "falhou"}
