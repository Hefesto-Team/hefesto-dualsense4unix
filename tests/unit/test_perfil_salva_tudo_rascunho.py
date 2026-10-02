"""PERFIL-SALVA-TUDO-01 — "salvei em todas as abas e só parte ficou" (29/07)."""
from __future__ import annotations

from pathlib import Path

from hefesto_dualsense4unix.app.draft_config import DraftConfig
from hefesto_dualsense4unix.profiles.schema import (
    ControllerOverrides,
    LedsConfig,
    MatchAny,
    MatchCriteria,
    Profile,
    ProfileMicConfig,
    ProfileModeConfig,
    ProfileMouseConfig,
    RumbleConfig,
    TriggerConfig,
    TriggersConfig,
)

UNIQ = "aabbcc000001"

ROXO = (97, 53, 131)


def _perfil_com_todas_as_secoes(nome: str = "Pragmata") -> Profile:
    """Perfil com TODAS as seções do esquema preenchidas — a prova pedida."""
    return Profile(
        name=nome,
        match=MatchCriteria(window_class=["steam_app_3357650"]),
        priority=100,
        triggers=TriggersConfig(
            left=TriggerConfig(mode="SemiAutoGun", params=[3, 6, 8]),
            right=TriggerConfig(mode="Pulse", params=[]),
        ),
        leds=LedsConfig(
            lightbar=ROXO,
            player_leds=[True, False, True, False, True],
            lightbar_brightness=0.5,
            auto_player_colors=False,
        ),
        rumble=RumbleConfig(passthrough=True, policy="custom", custom_mult=0.75),
        key_bindings={"r1": ["KEY_DOT"]},
        mouse=ProfileMouseConfig(enabled=True, speed=9, scroll_speed=3),
        mic=ProfileMicConfig(button_toggles_system=False),
        mode=ProfileModeConfig(kind="gamepad", gamepad_flavor="dualsense"),
        suppress_desktop_emulation=True,
        controllers={UNIQ: ControllerOverrides(leds=LedsConfig(lightbar=ROXO))},
    )


class TestRoundTripDeTudo:
    def test_perfil_com_todas_as_secoes_volta_identico(self) -> None:
        """from_profile → to_profile com o MESMO nome não perde uma seção."""
        original = _perfil_com_todas_as_secoes()
        draft = DraftConfig.from_profile(original)

        salvo = draft.to_profile(original.name)

        assert salvo.model_dump(mode="python") == original.model_dump(mode="python")

    def test_override_por_controle_continua_parcial(self) -> None:
        """O override com SÓ a cor não pode densificar (R-09 item 2)."""
        original = _perfil_com_todas_as_secoes()
        salvo = DraftConfig.from_profile(original).to_profile(original.name)

        assert salvo.controllers is not None
        leds = salvo.controllers[UNIQ].leds
        assert leds is not None
        assert leds.model_fields_set == {"lightbar"}


class TestGatePorSlug:
    def test_mesmo_arquivo_com_acento_diferente_nao_rebaixa(self) -> None:
        """"Navegação" no disco, "Navegacao" digitado: é o MESMO arquivo."""
        origem = _perfil_com_todas_as_secoes("Navegação")
        draft = DraftConfig.from_profile(origem)

        salvo = draft.to_profile("Navegacao")

        assert isinstance(salvo.match, MatchCriteria)
        assert salvo.match.window_class == ["steam_app_3357650"]
        assert salvo.priority == 100
        assert salvo.mode is not None and salvo.mode.kind == "gamepad"
        assert salvo.suppress_desktop_emulation is True

    def test_nome_de_verdade_novo_continua_nascendo_sem_regra(self) -> None:
        """O outro lado da mordida: R-11 continua de pé."""
        origem = _perfil_com_todas_as_secoes("Fps")
        draft = DraftConfig.from_profile(origem)

        salvo = draft.to_profile("MadJack")

        assert isinstance(salvo.match, MatchAny), "nome novo não herda a regra"
        assert salvo.priority != 100, "nome novo não herda a prioridade"
        assert salvo.mode is None
        assert salvo.suppress_desktop_emulation is False
        assert tuple(salvo.leds.lightbar) == ROXO
        assert salvo.triggers.left.mode == "SemiAutoGun"
        assert salvo.controllers is not None and UNIQ in salvo.controllers


class TestPrioridadeSemNumeroInventado:
    def test_sem_origem_e_sem_chamador_usa_o_default_do_esquema(self) -> None:
        """``to_profile("novo")`` não pode inventar 5."""
        salvo = DraftConfig.default().to_profile("novo")

        assert salvo.priority == Profile.model_fields["priority"].default
        assert salvo.priority != 5

    def test_prioridade_da_origem_vence_o_default(self) -> None:
        """Salvar por cima do mesmo perfil preserva a prioridade DELE."""
        origem = _perfil_com_todas_as_secoes("Pragmata")
        salvo = DraftConfig.from_profile(origem).to_profile("Pragmata")
        assert salvo.priority == 100

    def test_chamador_explicito_continua_mandando_em_perfil_novo(self) -> None:
        """Quem calcula a prioridade (aba Perfis) segue no comando."""
        salvo = DraftConfig.default().to_profile("novo", priority=110)
        assert salvo.priority == 110

    def test_nenhuma_assinatura_de_gravacao_tem_o_cinco_magico(self) -> None:
        """Portão de busca (pedido da sprint, E2)."""
        raiz = Path(__file__).resolve().parents[2] / "src"
        ofensores = [
            str(caminho.relative_to(raiz))
            for caminho in raiz.rglob("*.py")
            if "priority: int = 5" in caminho.read_text(encoding="utf-8")
        ]
        assert ofensores == []


class TestModoEModoJogoTemDono:
    def test_modo_editado_na_aba_sobrevive_ao_nome_novo(self) -> None:
        """O gesto DELA não é a regra de outro perfil — e por isso viaja."""
        origem = _perfil_com_todas_as_secoes("Pragmata")
        draft = DraftConfig.from_profile(origem)

        draft = draft.with_mode(
            ProfileModeConfig(kind="gamepad", gamepad_flavor="dualsense")
        )
        salvo = draft.to_profile("Pragmata3")

        assert salvo.mode is not None
        assert salvo.mode.kind == "gamepad"
        assert salvo.mode.gamepad_flavor == "dualsense"
        assert isinstance(salvo.match, MatchAny)

    def test_modo_jogo_ligado_na_aba_sobrevive_ao_nome_novo(self) -> None:
        """"Modo jogo" = suspender mouse e teclado (o esclarecimento dela)."""
        draft = DraftConfig.default().with_suppress(True)

        salvo = draft.to_profile("Pragmata3")

        assert salvo.suppress_desktop_emulation is True

    def test_desligar_o_modo_jogo_tambem_e_gesto(self) -> None:
        """Desligar é opinião como ligar — o False dela tem de sobreviver."""
        origem = _perfil_com_todas_as_secoes("Pragmata")
        draft = DraftConfig.from_profile(origem)
        assert draft.source_suppress is True

        salvo = draft.with_suppress(False).to_profile("Pragmata")

        assert salvo.suppress_desktop_emulation is False

    def test_sem_gesto_nenhum_o_nome_novo_nasce_sem_opiniao(self) -> None:
        """A guarda R-11 continua valendo para quem NÃO mexeu nas abas."""
        origem = _perfil_com_todas_as_secoes("Pragmata")
        salvo = DraftConfig.from_profile(origem).to_profile("Pragmata3")

        assert salvo.mode is None
        assert salvo.suppress_desktop_emulation is False

    def test_depois_de_gravar_a_identidade_baixa_os_flags(self) -> None:
        """``with_profile_identity`` fecha o ciclo: o rascunho descreve o DISCO."""
        draft = DraftConfig.default().with_mode(
            ProfileModeConfig(kind="native")
        ).with_suppress(True)
        gravado = draft.to_profile("Pragmata3")
        assert gravado.mode is not None and gravado.suppress_desktop_emulation is True

        draft = draft.with_profile_identity(gravado)
        assert draft.mode_dirty is False
        assert draft.suppress_dirty is False

        outro = draft.to_profile("Outro Perfil")
        assert outro.mode is None
        assert outro.suppress_desktop_emulation is False

    def test_o_aplicar_nao_leva_modo_nem_modo_jogo(self) -> None:
        """HARM-05, na seção pior de todas."""
        draft = DraftConfig.default().with_mode(
            ProfileModeConfig(kind="gamepad", gamepad_flavor="xbox")
        ).with_suppress(True)

        payload = draft.to_ipc_dict()

        assert "mode" not in payload
        assert "suppress_desktop_emulation" not in payload
        assert "suppress" not in payload
