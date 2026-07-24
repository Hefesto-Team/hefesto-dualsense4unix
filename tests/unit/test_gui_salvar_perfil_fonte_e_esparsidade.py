"""R-09 (auditoria 23/07) — "Salvar" da aba Perfis: fonte certa e sem densificar.

Três defeitos que compunham a queixa "as configs que eu faço não impactam":

1. **Fonte errada** — `_build_profile_from_editor` montava o perfil a partir do
   CACHE DE DISCO e não consultava `self.draft` em nenhuma linha. As abas
   Lightbar/Gatilhos/Rumble/Mouse/Teclado gravam EXCLUSIVAMENTE no draft, então
   salvar pela aba Perfis descartava tudo. Pior: `on_profile_save` chama
   `profile_switch` quando o perfil salvo é o ativo → o daemon relia o JSON
   velho e REVERTIA no hardware a cor/gatilho que ela acabara de ver funcionando.

2. **Densificação** — `model_dump()` marca os defaults do schema como
   explícitos e perde o `model_fields_set`. Um override por-controle PARCIAL
   (ex.: só brilho) virava `lightbar:[0,0,0]`: a lightbar daquele controle
   **apaga** e o override para de herdar o global para sempre.

3. **"Novo perfil" clonando** — nascia com os overrides por-MAC e o
   `suppress_desktop_emulation` do perfil selecionado na lista.

O item 2 é testado aqui de forma independente de GTK, porque é o comportamento
do schema que importa — e é o caso que `test_profile_editor_roundtrip.py` não
cobria (não tem um único `controllers`).
"""

from __future__ import annotations

import json
from pathlib import Path

from hefesto_dualsense4unix.profiles.schema import (
    ControllerOverrides,
    LedsConfig,
    MatchCriteria,
    Profile,
)

MAC = "aabbcc000002"


def _perfil_com_override_parcial() -> Profile:
    """Perfil cujo override por-controle mexe SÓ no brilho.

    É o gesto real: ela seleciona um DualSense e ajusta só o brilho da lightbar,
    esperando que a COR continue vindo do global/automático.
    """
    return Profile(
        name="perfil_parcial",
        match=MatchCriteria(window_class=["jogo"]),
        priority=10,
        leds=LedsConfig(lightbar=[200, 20, 20]),
        controllers={
            MAC: ControllerOverrides(leds=LedsConfig(lightbar_brightness=0.5))
        },
    )


class TestEsparsidadeDoOverridePorControle:
    def test_model_dump_densifica_e_apaga_a_lightbar(self) -> None:
        """Documenta o MECANISMO do defeito (é o que o fix tem de evitar)."""
        p = _perfil_com_override_parcial()
        override = p.controllers[MAC]
        assert override.leds is not None
        assert "lightbar" not in override.leds.model_fields_set, (
            "pré-condição: o override é PARCIAL — não fala de cor"
        )

        densificado = Profile.model_validate(p.model_dump(mode="python"))
        leds_dens = densificado.controllers[MAC].leds
        assert leds_dens is not None
        assert "lightbar" in leds_dens.model_fields_set, (
            "model_dump marca o default do schema como explícito — é exatamente "
            "assim que o override parcial vira lightbar:[0,0,0]"
        )

    def test_reinjetar_as_instancias_preserva_a_parcialidade(self) -> None:
        """O fix: a guarda que `draft_config.to_profile` já tinha."""
        p = _perfil_com_override_parcial()
        payload = p.model_dump(mode="python")
        payload["controllers"] = p.controllers  # <- a guarda

        salvo = Profile.model_validate(payload)
        leds = salvo.controllers[MAC].leds
        assert leds is not None
        assert "lightbar" not in leds.model_fields_set, (
            "o override tem de continuar PARCIAL — senão a cor daquele controle "
            "para de herdar o global e a lightbar apaga"
        )
        assert leds.lightbar_brightness == 0.5

    def test_roundtrip_em_disco_preserva_a_parcialidade(self, tmp_path: Path) -> None:
        """Ida e volta pelo JSON, que é o que o loader faz de verdade."""
        p = _perfil_com_override_parcial()
        payload = p.model_dump(mode="python")
        payload["controllers"] = p.controllers
        salvo = Profile.model_validate(payload)

        caminho = tmp_path / "p.json"
        caminho.write_text(
            json.dumps(salvo.model_dump(mode="json", exclude_unset=True), indent=2),
            encoding="utf-8",
        )
        relido = Profile.model_validate(json.loads(caminho.read_text(encoding="utf-8")))

        leds = relido.controllers[MAC].leds
        assert leds is not None
        assert leds.lightbar_brightness == 0.5
        assert "lightbar" not in leds.model_fields_set


class TestFonteDoBuild:
    """O build tem de ler o DRAFT quando edita o perfil que o draft representa."""

    def test_o_codigo_consulta_o_draft(self) -> None:
        """Guarda de arquitetura: o módulo não lia `self.draft` em linha alguma.

        Um teste de comportamento exigiria GTK montado; o que importa travar é
        que a fonte deixou de ser exclusivamente o disco.
        """
        fonte = (
            Path(__file__).resolve().parents[2]
            / "src/hefesto_dualsense4unix/app/actions/profiles_actions.py"
        ).read_text(encoding="utf-8")
        build = fonte.split("_build_profile_from_editor", 1)[1]
        assert 'getattr(self, "draft", None)' in build, (
            "salvar pela aba Perfis tem de partir do draft quando o perfil "
            "editado é o do draft — senão descarta o que as outras abas fizeram"
        )
        assert 'base["controllers"] = ' in build, (
            "sem reinjetar as instâncias validadas, o override parcial densifica"
        )

    def test_perfil_novo_nao_herda_o_selecionado(self) -> None:
        fonte = (
            Path(__file__).resolve().parents[2]
            / "src/hefesto_dualsense4unix/app/actions/profiles_actions.py"
        ).read_text(encoding="utf-8")
        build = fonte.split("_build_profile_from_editor", 1)[1]
        assert '_new_profile' in build, (
            '"Novo perfil" não pode cair no selected_source (que existe para '
            "rename e duplicação) — nasceria clonando overrides por-MAC"
        )
        # E a flag precisa ser zerada nos caminhos que saem do estado "novo",
        # senão o Salvar seguinte sobre um perfil existente perderia a config.
        assert fonte.count("self._new_profile = False") >= 3


class TestR11SourceNameGateiaAsRegras:
    """R-11 — `to_profile` reemitia match/priority/mode para QUALQUER nome.

    Os campos `source_*` são um snapshot tirado no bootstrap, e nenhum handler
    da aba Perfis os atualiza. Dois estragos distintos saíam daí:

    1. **nome NOVO** — o perfil nascia com a regra de casamento e a prioridade
       de OUTRO perfil. Medido: com o FPS ativo, "Salvar Perfil" como "MadJack"
       produzia um perfil com o regex de título do FPS e prioridade 60, e
       nenhuma regra para o jogo dela;
    2. **mesmo nome** — ela configurava o Modo na aba Perfis e salvava (o JSON
       ganhava `mode`), ia à Lightbar mudar a cor e clicava "Salvar Perfil" no
       rodapé → `to_profile` reemitia `mode=source_mode`, ainda o valor do BOOT
       (None), e a seção `mode` era APAGADA do JSON.
    """

    @staticmethod
    def _draft_do_fps():
        from hefesto_dualsense4unix.app.draft_config import DraftConfig
        from hefesto_dualsense4unix.profiles.schema import ProfileModeConfig

        fps = Profile(
            name="FPS",
            match=MatchCriteria(window_title_regex=".*(Counter-Strike|Control).*"),
            priority=60,
            mode=ProfileModeConfig(kind="gamepad", gamepad_flavor="dualsense"),
            suppress_desktop_emulation=True,
        )
        return DraftConfig.from_profile(fps), fps

    def test_nome_novo_nao_herda_a_regra_do_perfil_ativo(self) -> None:
        draft, _fps = self._draft_do_fps()
        novo = draft.to_profile("MadJack")

        assert novo.match.type == "any", (
            "o perfil novo nasceu com o regex de título do FPS — ele casaria "
            "com as janelas do FPS e não com o jogo dela"
        )
        assert novo.priority != 60
        assert novo.mode is None, "modo do outro perfil não é regra deste"
        assert novo.suppress_desktop_emulation is False

    def test_mesmo_nome_preserva_as_secoes_que_o_draft_nao_edita(self) -> None:
        """A proteção do BUG-FOOTER-SAVE-DROPS-SECTIONS-01 continua valendo."""
        draft, fps = self._draft_do_fps()
        salvo = draft.to_profile("FPS")

        assert salvo.match == fps.match
        assert salvo.priority == 60
        assert salvo.mode is not None and salvo.mode.kind == "gamepad"
        assert salvo.suppress_desktop_emulation is True

    def test_mode_configurado_na_aba_perfis_sobrevive_ao_salvar_do_rodape(self) -> None:
        """O estrago nº 2, na ordem exata de cliques que ela faz.

        Depois de salvar pela aba Perfis, a reconciliação (R-08) recarrega o
        draft do disco — e é DAÍ que o snapshot passa a ter o `mode` novo.
        """
        from hefesto_dualsense4unix.app.draft_config import DraftConfig
        from hefesto_dualsense4unix.profiles.schema import ProfileModeConfig

        # Boot: o perfil ainda não tem `mode`.
        no_boot = Profile(
            name="FPS", match=MatchCriteria(window_class=["x"]), priority=60
        )
        draft_boot = DraftConfig.from_profile(no_boot)
        assert draft_boot.to_profile("FPS").mode is None

        # Aba Perfis grava o Modo; a reconciliação recarrega o draft.
        com_mode = no_boot.model_copy(
            update={"mode": ProfileModeConfig(kind="gamepad", gamepad_flavor="xbox")}
        )
        draft_novo = DraftConfig.from_profile(com_mode)

        salvo = draft_novo.to_profile("FPS")
        assert salvo.mode is not None and salvo.mode.gamepad_flavor == "xbox", (
            "o rodapé apagou a seção `mode` que ela acabou de configurar"
        )

    def test_draft_sem_origem_nao_inventa_regra(self) -> None:
        """`DraftConfig.default()` não tem `source_name` — nada a reemitir."""
        from hefesto_dualsense4unix.app.draft_config import DraftConfig

        p = DraftConfig.default().to_profile("qualquer")
        assert p.match.type == "any"
        assert p.mode is None
