"""MIC-EXPOSE-01 — `mic_button_toggles_system` deixa de ser campo secreto.

O campo existia SÓ dentro do `DaemonConfig` (`daemon/lifecycle.py`): gateava o
subsystem `mic_hotkey` no boot e não aparecia na GUI, no draft nem no schema
de perfil. Quem quisesse mudá-lo tinha de editar código.

Agora: seção `mic` no perfil (opcional, None = sem opinião), sub-draft
`MicDraft` com a mesma disciplina dirty/in_profile do mouse, seção no
`apply_draft` e o valor efetivo no `daemon.state_full`.
"""
from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest
from pydantic import ValidationError

from hefesto_dualsense4unix.app.draft_config import DraftConfig, MicDraft
from hefesto_dualsense4unix.profiles.schema import (
    MatchAny,
    Profile,
    ProfileMicConfig,
)


class TestSchema:
    def test_perfil_sem_secao_mic_continua_valido(self) -> None:
        """Aditivo ao v1: perfis legados não ganham seção fantasma."""
        perfil = Profile(name="p", match=MatchAny())
        assert perfil.mic is None

    def test_secao_mic_persistida(self) -> None:
        perfil = Profile(
            name="live", match=MatchAny(),
            mic=ProfileMicConfig(button_toggles_system=False),
        )
        assert perfil.mic is not None
        assert perfil.mic.button_toggles_system is False

    def test_campo_desconhecido_e_rejeitado(self) -> None:
        """`extra="forbid"`: um campo que não existe no schema é recusado."""
        with pytest.raises(ValidationError):
            ProfileMicConfig(  # type: ignore[call-arg]
                button_toggles_system=True, ganho_do_preamp=3
            )

    def test_o_volume_e_o_mudo_agora_sao_campos(self) -> None:
        """MIC-VOLUME-01: o par que faltava para o mic ter a mesma gramática"""
        mic = ProfileMicConfig(button_toggles_system=True, volume=70, muted=False)
        assert mic.volume == 70
        assert mic.muted is False

    def test_sem_opiniao_continua_sendo_o_default(self) -> None:
        """Perfil que não pediu volume não pode tomar posse do microfone."""
        mic = ProfileMicConfig(button_toggles_system=True)
        assert mic.volume is None
        assert mic.muted is None

    @pytest.mark.parametrize("fora", [-1, 101, 255])
    def test_volume_fora_da_faixa_e_recusado(self, fora: int) -> None:
        """0-100 por cento. O 255 entra de propósito: é a escala do"""
        with pytest.raises(ValidationError):
            ProfileMicConfig(button_toggles_system=True, volume=fora)


def _applier() -> tuple[Any, Any]:
    """Applier com daemon de mentira e o flag do mic LIGADO, como no boot."""
    from hefesto_dualsense4unix.daemon.ipc_draft_applier import DraftApplier
    from hefesto_dualsense4unix.daemon.state_store import StateStore
    from hefesto_dualsense4unix.testing import FakeController

    daemon = MagicMock()
    daemon.config = MagicMock(mic_button_toggles_system=True)
    applier = DraftApplier(
        controller=FakeController(transport="usb"),
        store=StateStore(),
        daemon=daemon,
    )
    return applier, daemon


class TestDraft:
    def test_o_default_do_rascunho_e_nao_ter_opiniao(self) -> None:
        """NOTA DATADA — 22/08/2026 (MIC-GATE-POR-CAMPO-01)."""
        assert DraftConfig.default().mic.button_toggles_system is None

    def test_round_trip_perfil_para_draft_e_de_volta(self) -> None:
        origem = Profile(
            name="live", match=MatchAny(),
            mic=ProfileMicConfig(button_toggles_system=False),
        )
        draft = DraftConfig.from_profile(origem)
        assert draft.mic.button_toggles_system is False
        assert draft.mic.in_profile is True

        salvo = draft.to_profile("live")
        assert salvo.mic is not None
        assert salvo.mic.button_toggles_system is False

    def test_perfil_sem_secao_nao_ganha_secao_no_save(self) -> None:
        """Sem toque e sem origem, o round-trip não inventa a seção."""
        origem = Profile(name="p", match=MatchAny())
        salvo = DraftConfig.from_profile(origem).to_profile("p")
        assert salvo.mic is None

    def test_to_ipc_dict_so_emite_quando_tocado(self) -> None:
        """Mesma regra do mouse: "Aplicar" de outra aba não mexe no botão."""
        limpo = DraftConfig.default()
        assert limpo.to_ipc_dict()["mic"] is None

        tocado = limpo.model_copy(
            update={"mic": MicDraft(button_toggles_system=False, dirty=True)}
        )
        assert tocado.to_ipc_dict()["mic"] == {
            "button_toggles_system": False,
            "volume": None,
        }


class TestGatePorCampo:
    """MIC-GATE-POR-CAMPO-01 (22/08/2026) — o gate era por SEÇÃO."""

    def test_o_gesto_do_volume_nao_arrasta_o_botao_junto(self) -> None:
        """O molde é o `rota` do alto-falante: sem opinião, a chave não viaja."""
        depois_do_slider = DraftConfig.default().with_mic(volume=70)
        secao = depois_do_slider.to_ipc_dict()["mic"]

        assert secao == {"volume": 70}, (
            f"a seção do microfone saiu como {secao!r} — o gesto do volume "
            "levou junto um campo que ninguém escolheu"
        )

    def test_o_aplicar_do_volume_nao_derruba_o_flag_vivo_do_daemon(self) -> None:
        """A ponta que dói: a config VIVA do daemon, escrita pelas costas dela."""
        applier, daemon = _applier()
        daemon.config.mic_button_toggles_system = False

        payload = DraftConfig.default().with_mic(volume=70).to_ipc_dict()
        aplicadas = applier.apply({"mic": payload["mic"]})

        assert daemon.config.mic_button_toggles_system is False, (
            "o Aplicar religou o botão de mic do sistema — o gesto foi no "
            "controle deslizante do volume"
        )
        assert "mic" in aplicadas, "sem opinião não é FALHA — é nada a fazer"

    def test_a_chave_nula_e_silencio_e_nao_falha_a_secao(self) -> None:
        """Nulo explícito é "sem opinião", não payload torto."""
        applier, daemon = _applier()

        aplicadas = applier.apply(
            {"mic": {"volume": 70, "muted": None, "button_toggles_system": None}}
        )

        assert "mic" in aplicadas
        assert applier.failed == {}
        assert daemon.config.mic_button_toggles_system is True

    def test_com_opiniao_a_chave_viaja_e_e_aplicada(self) -> None:
        """A outra metade: quem escolher o campo continua sendo obedecido."""
        draft = DraftConfig.default().model_copy(
            update={"mic": MicDraft(button_toggles_system=False, dirty=True)}
        )
        applier, daemon = _applier()

        applier.apply({"mic": draft.to_ipc_dict()["mic"]})

        assert daemon.config.mic_button_toggles_system is False

    def test_o_disco_continua_lembrando_do_que_ela_desligou(self) -> None:
        """Sem opinião no rascunho não pode virar `False` no arquivo."""
        salvo = DraftConfig.default().with_mic(volume=70).to_profile("p")
        assert salvo.mic is not None
        assert salvo.mic.button_toggles_system is True
        assert salvo.mic.volume == 70

        de_volta = DraftConfig.from_profile(
            Profile(
                name="live",
                match=MatchAny(),
                mic=ProfileMicConfig(button_toggles_system=False, volume=40),
            )
        )
        assert de_volta.mic.button_toggles_system is False
        assert de_volta.to_profile("live").mic.button_toggles_system is False


class TestApplier:

    def test_apply_draft_escreve_na_config_viva(self) -> None:
        applier, daemon = _applier()
        aplicadas = applier.apply({"mic": {"button_toggles_system": False}})
        assert "mic" in aplicadas
        assert daemon.config.mic_button_toggles_system is False

    def test_secao_ausente_nao_toca_no_flag(self) -> None:
        applier, daemon = _applier()
        applier.apply({"rumble": {"weak": 0, "strong": 0}})
        assert daemon.config.mic_button_toggles_system is True

    def test_valor_invalido_nao_corrompe_a_config(self) -> None:
        """`_apply_section` engole a exceção — mas nada é escrito."""
        applier, daemon = _applier()
        aplicadas = applier.apply({"mic": {"button_toggles_system": "sim"}})
        assert "mic" not in aplicadas
        assert daemon.config.mic_button_toggles_system is True


class TestLacoDoBotao:
    @pytest.mark.asyncio
    async def test_flag_desligado_no_runtime_impede_o_toggle(self) -> None:
        """O laço consulta o flag A CADA evento — sem restart do daemon."""
        import asyncio

        from hefesto_dualsense4unix.core.events import EventBus, EventTopic
        from hefesto_dualsense4unix.daemon.subsystems.hotkey import mic_button_loop

        bus = EventBus()
        bus.bind_loop(asyncio.get_running_loop())
        daemon = MagicMock()
        daemon.bus = bus
        daemon.config = MagicMock(mic_button_toggles_system=False)
        daemon._audio = MagicMock()
        parando = {"v": False}
        daemon._is_stopping = lambda: parando["v"]

        task = asyncio.create_task(mic_button_loop(daemon))
        await asyncio.sleep(0.05)
        bus.publish(EventTopic.BUTTON_DOWN, {"button": "mic_btn"})
        await asyncio.sleep(0.15)
        parando["v"] = True
        await asyncio.wait_for(task, timeout=2.0)

        daemon._audio.toggle_default_source_mute.assert_not_called()
