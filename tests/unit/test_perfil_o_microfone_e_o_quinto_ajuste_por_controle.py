"""MIC-QUINTO-AJUSTE-01 (03/09/2026) — o microfone entra no perfil POR CONTROLE."""
from __future__ import annotations

from typing import Any

import pytest

from hefesto_dualsense4unix.profiles.manager import ProfileManager
from hefesto_dualsense4unix.profiles.schema import (
    ControllerMicOverride,
    ControllerOverrides,
    MatchAny,
    Profile,
    ProfileMicConfig,
)
from tests.unit.test_por_unidade_01_todas_as_abas import (
    BRANCO,

    PRETO,
    _StoreSemTrava,
)


class _StoreComTrava(_StoreSemTrava):
    """A trava manual de áudio ARMADA — ela acabou de mexer no mic na mão."""

    manual_override_categories: tuple[str, ...] = ("audio",)


def _gerente(applier: Any, *, store: Any = None) -> ProfileManager:
    return ProfileManager(
        controller=object(),  # type: ignore[arg-type]
        store=store if store is not None else _StoreSemTrava(),  # type: ignore[arg-type]
        mic_applier=applier,
    )


def _espiao() -> tuple[Any, list[tuple[int | None, bool | None, str | None, str]]]:
    """Applier de dublê que anota ``(volume, muted, uniq, origin)`` de cada ordem."""
    chamadas: list[tuple[int | None, bool | None, str | None, str]] = []

    def applier(
        volume: int | None = None,
        muted: bool | None = None,
        *,
        uniq: str | None = None,
        origin: str = "autoswitch",
    ) -> str:
        chamadas.append((volume, muted, uniq, origin))
        return "aplicado"

    return applier, chamadas


def test_o_microfone_e_o_quinto_ajuste_por_controle() -> None:
    """O ``mic`` é o QUINTO, depois de luz, gatilhos, vibração e alto-falante."""
    assert list(ControllerOverrides.model_fields)[:5] == [
        "leds",
        "triggers",
        "rumble",
        "speaker",
        "mic",
    ]


def test_o_override_e_subconjunto_estrito_do_global() -> None:
    """``ControllerMicOverride`` só pode ter campos que o global também tem."""
    do_override = set(ControllerMicOverride.model_fields)
    do_global = set(ProfileMicConfig.model_fields)
    assert do_override <= do_global, (
        f"campo(s) só no override: {sorted(do_override - do_global)} — "
        "`apply_mic` lê a seção por getattr e não os veria"
    )
    assert do_override <= do_global, (
        f"o override tem campo que o global não tem: {do_override - do_global}. "
        "O override é subconjunto do global por construção — `apply_mic` lê a "
        "seção por `getattr`, e um campo só daqui não teria quem o lesse.")
    assert do_override, "o override ficou vazio — nenhum ajuste de mic por peça"
    assert "button_toggles_system" not in do_override, (
        "`button_toggles_system` entrou no override: ele é UM por máquina "
        "(`hotkey.mic_button_loop` lê `daemon.config`, sem consultar uniq), e "
        "quatro controles gravariam quatro opiniões sobre um interruptor só")


def test_o_que_continua_recusado_diz_a_medicao_na_mensagem() -> None:
    """"Extra inputs are not permitted" mandaria procurar no lugar errado."""
    assert ControllerMicOverride.model_validate({"volume": 50}).volume == 50
    assert ControllerOverrides.model_validate(
        {"mic": {"volume": 50}}).mic.volume == 50

    for erro in (pytest.raises(ValueError, match="UM por"),
                 pytest.raises(ValueError, match="interruptor só")):
        with erro:
            ControllerMicOverride.model_validate(
                {"button_toggles_system": True})


def test_o_interruptor_do_botao_por_peca_e_recusado_com_a_razao() -> None:
    """Um por MÁQUINA — quatro controles não têm quatro opiniões sobre ele."""
    with pytest.raises(ValueError, match="MÁQUINA"):
        ControllerMicOverride.model_validate({"button_toggles_system": True})
    with pytest.raises(ValueError, match=r"hotkey\.mic_button_loop"):
        ControllerOverrides.model_validate({"mic": {"button_toggles_system": False}})


def test_o_perfil_antigo_sem_o_campo_carrega_e_vale() -> None:
    """Aditivo, sem bump de versão — é o contrato do ``speaker`` e do ``mode``."""
    perfil = Profile.model_validate(
        {
            "name": "jogo_de_ontem",
            "version": 1,
            "match": {"type": "any"},
            "mic": {"button_toggles_system": True, "muted": True},
            "controllers": {BRANCO: {"leds": {"lightbar": [1, 2, 3]}}},
        }
    )
    assert perfil.controllers is not None
    assert perfil.controllers[BRANCO].mic is None
    assert perfil.mic is not None and perfil.mic.muted is True


def test_a_ida_e_volta_pelo_disco_preserva_o_mudo_da_peca() -> None:
    """Grava, lê de volta, e o ``muted`` daquela peça volta igual."""
    perfil = Profile(
        name="mic_por_peca",
        match=MatchAny(),
        controllers={
            BRANCO: ControllerOverrides(mic=ControllerMicOverride(muted=True)),
            PRETO: ControllerOverrides(mic=ControllerMicOverride(muted=False)),
        },
    )
    cru = perfil.model_dump(mode="json", exclude_none=True)
    assert cru["controllers"] == {
        BRANCO: {"mic": {"muted": True}},
        PRETO: {"mic": {"muted": False}},
    }
    de_volta = Profile.model_validate(cru)
    assert de_volta.controllers is not None
    assert de_volta.controllers[BRANCO].mic is not None
    assert de_volta.controllers[BRANCO].mic.muted is True
    assert de_volta.controllers[PRETO].mic is not None
    assert de_volta.controllers[PRETO].mic.muted is False

    sem_opiniao = Profile(
        name="sem_mic",
        match=MatchAny(),
        controllers={BRANCO: ControllerOverrides(mic=ControllerMicOverride())},
    )
    magro = sem_opiniao.model_dump(mode="json", exclude_none=True)
    assert magro["controllers"] == {BRANCO: {"mic": {}}}, (
        "sem opinião continua sendo silêncio: nenhum valor inventado vai ao "
        "disco por uma peça que não pediu nada"
    )


def test_cada_peca_recebe_o_proprio_volume_na_ativacao() -> None:
    """Duas unidades, dois volumes, um perfil só — o pedido por microfone."""
    applier, chamadas = _espiao()
    gerente = _gerente(applier)
    perfil = Profile(
        name="mic_por_peca",
        match=MatchAny(),
        mic=ProfileMicConfig(button_toggles_system=True, volume=50),
        controllers={
            BRANCO: ControllerOverrides(mic=ControllerMicOverride(volume=30)),
            PRETO: ControllerOverrides(mic=ControllerMicOverride(volume=80)),
        },
    )

    relatorio: dict[str, str] = {}
    gerente.apply_mic(perfil, relatorio=relatorio)
    gerente.apply_controller_mics(perfil, relatorio=relatorio)

    assert chamadas == [
        (50, None, None, "manual"),
        (30, None, BRANCO, "manual"),
        (80, None, PRETO, "manual"),
    ]
    assert relatorio[f"mic:{BRANCO}"] == "aplicado"
    assert relatorio[f"mic:{PRETO}"] == "aplicado"


def test_a_ativacao_do_perfil_chama_o_por_peca_depois_do_global() -> None:
    """A ordem é a entrega: invertê-la faria o global apagar a peça."""
    applier, chamadas = _espiao()
    gerente = _gerente(applier)
    perfil = Profile(
        name="ativacao_inteira",
        match=MatchAny(),
        mic=ProfileMicConfig(button_toggles_system=True, volume=50),
        controllers={BRANCO: ControllerOverrides(mic=ControllerMicOverride(volume=30))},
    )

    relatorio = gerente.apply_emulation(perfil, origin="manual")

    assert [(c[0], c[2]) for c in chamadas] == [(50, None), (30, BRANCO)]
    assert relatorio["mic"] == "aplicado"
    assert relatorio[f"mic:{BRANCO}"] == "aplicado"


def test_a_peca_sem_opiniao_nao_produz_ordem_nenhuma() -> None:
    """``mic=None`` é ausência de opinião — e ausência não vira chamada vazia."""
    applier, chamadas = _espiao()
    gerente = _gerente(applier)
    perfil = Profile(
        name="sem_opiniao",
        match=MatchAny(),
        controllers={
            BRANCO: ControllerOverrides(),
            PRETO: ControllerOverrides(mic=ControllerMicOverride()),
        },
    )

    relatorio = gerente.apply_controller_mics(perfil)

    assert chamadas == []
    assert relatorio == {}


def test_o_mudo_da_peca_nao_atravessa_ativacao_nenhuma() -> None:
    """A guarda do mudo vale igual por peça — e é a guarda mais cara de perder."""
    applier, chamadas = _espiao()
    gerente = _gerente(applier)
    perfil = Profile(
        name="gravacao",
        match=MatchAny(),
        controllers={BRANCO: ControllerOverrides(mic=ControllerMicOverride(muted=True))},
    )

    for origem in ("autoswitch", "system", "manual"):
        assert gerente.apply_controller_mics(perfil, origin=origem) == {}
    assert chamadas == [], "o mudo da peça atravessou uma ativação de perfil"


def test_o_applier_que_cai_nao_aborta_a_ativacao_e_diz_qual_peca() -> None:
    """Best-effort como os irmãos — e a falha tem endereço, não um rótulo só."""

    def applier(
        volume: int | None = None,
        muted: bool | None = None,
        *,
        uniq: str | None = None,
        origin: str = "autoswitch",
    ) -> str:
        if uniq == BRANCO:
            raise RuntimeError("hidraw ocupado")
        return "aplicado"

    gerente = _gerente(applier)
    perfil = Profile(
        name="uma_cai_a_outra_nao",
        match=MatchAny(),
        controllers={
            BRANCO: ControllerOverrides(mic=ControllerMicOverride(volume=30)),
            PRETO: ControllerOverrides(mic=ControllerMicOverride(volume=30)),
        },
    )

    relatorio = gerente.apply_controller_mics(perfil, origin="manual")

    assert relatorio == {
        f"mic:{BRANCO}": "falhou",
        f"mic:{PRETO}": "aplicado",
    }


def test_o_override_da_peca_nao_suja_o_perfil_em_memoria() -> None:
    """A vista é uma CÓPIA: o ``mic`` global do perfil sai da ativação intacto."""
    applier, _ = _espiao()
    gerente = _gerente(applier)
    global_original = ProfileMicConfig(button_toggles_system=True, muted=False)
    perfil = Profile(
        name="nao_suja",
        match=MatchAny(),
        mic=global_original,
        controllers={BRANCO: ControllerOverrides(mic=ControllerMicOverride(muted=True))},
    )

    gerente.apply_controller_mics(perfil, origin="manual")

    assert perfil.mic is global_original
    assert perfil.mic.muted is False
