"""PERFIL-SALVA-TUDO-01 — "salvei em todas as abas e só parte ficou" (29/07).

A queixa dela: *"temos o perfil do jogo tipo Pragmata, e em todas as abas fiz
alterações e salvei o perfil, e essas configurações de outras abas não ficam
salvas"*. A transcrição LITERAL, com a grafia dela intacta, está na sprint
``docs/process/sprints/2026-07-29-PERFIL-SALVA-TUDO-01-*.md``.

Medido no disco dela antes de qualquer linha de código: ``pragmata.json`` e
``pragmata2.json`` são byte-idênticos fora o ``name``, os dois com
``"match": {"type": "any"}``, ``"priority": 5``, ``"mode": null`` e
``"suppress_desktop_emulation": false`` — enquanto o daemon tinha
``gamepad_emulation.flag = dualsense`` VIVO. O gesto que existe para preservar o
trabalho dela é o que o desfaz.

Este módulo cobre a camada do RASCUNHO (sem GTK — roda no CI headless):

- **E1a** — o gate que decide entre preservar e zerar comparava string CRUA;
  agora compara por SLUG (R-10), que é a identidade do arquivo em disco;
- **E2** — o ``priority: int = 5`` da assinatura de ``to_profile`` era a
  assinatura digital dos perfis dela: um número que ela nunca escolheu;
- **E3 (metade do rascunho)** — ``mode`` e ``suppress_desktop_emulation`` deixam
  de ser só-transporte e ganham dono: ``with_mode``/``with_suppress``. É o que
  dá às abas Emulação e Início um lugar para escrever (hoje elas têm
  ``grep -c 'self\\.draft'`` = 0) sem reabrir o R-11.

A metade da aba Perfis está em ``test_perfil_salva_tudo_abas.py``.
"""
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

#: MAC forjado da faixa permitida (tests/unit/test_anonimato_de_fixtures.py).
UNIQ = "aabbcc000001"

ROXO = (97, 53, 131)


def _perfil_com_todas_as_secoes(nome: str = "Pragmata") -> Profile:
    """Perfil com TODAS as seções do esquema preenchidas — a prova pedida.

    Nenhum campo fica no default por acidente: é a única forma de um round-trip
    provar que nada se perde. Os valores imitam os do disco dela (gatilhos
    ``SemiAutoGun``/``Pulse``, lightbar roxa, política ``economia``, override
    por-controle com SÓ a cor) mais as três seções que os arquivos dela nunca
    tiveram (``mouse``, ``mic``, ``mode``) e o ``suppress`` ligado.
    """
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
        rumble=RumbleConfig(passthrough=True, policy="custom", custom_mult=1.5),
        key_bindings={"r1": ["KEY_DOT"]},
        mouse=ProfileMouseConfig(enabled=True, speed=9, scroll_speed=3),
        mic=ProfileMicConfig(button_toggles_system=False),
        mode=ProfileModeConfig(kind="gamepad", gamepad_flavor="dualsense"),
        suppress_desktop_emulation=True,
        controllers={UNIQ: ControllerOverrides(leds=LedsConfig(lightbar=ROXO))},
    )


# ---------------------------------------------------------------------------
# A prova pedida pela sprint: salvo e relido, volta IDÊNTICO
# ---------------------------------------------------------------------------


class TestRoundTripDeTudo:
    def test_perfil_com_todas_as_secoes_volta_identico(self) -> None:
        """from_profile → to_profile com o MESMO nome não perde uma seção.

        Comparação por ``model_dump`` do perfil inteiro: qualquer seção que o
        rascunho esqueça de transportar aparece aqui como diferença, sem eu ter
        de listar campo por campo (uma seção NOVA no esquema entra nesta prova
        de graça).
        """
        original = _perfil_com_todas_as_secoes()
        draft = DraftConfig.from_profile(original)

        salvo = draft.to_profile(original.name)

        assert salvo.model_dump(mode="python") == original.model_dump(mode="python")

    def test_override_por_controle_continua_parcial(self) -> None:
        """O override com SÓ a cor não pode densificar (R-09 item 2).

        ``model_dump`` marca os defaults do esquema como explícitos e
        ``lightbar: [0,0,0]`` apagaria a lightbar daquele controle. O único
        override nos perfis dela tem SÓ ``leds.lightbar`` — é exatamente este
        caso, e é uma entrada parcial em risco.
        """
        original = _perfil_com_todas_as_secoes()
        salvo = DraftConfig.from_profile(original).to_profile(original.name)

        assert salvo.controllers is not None
        leds = salvo.controllers[UNIQ].leds
        assert leds is not None
        assert leds.model_fields_set == {"lightbar"}


# ---------------------------------------------------------------------------
# E1a — o gate compara por SLUG, não por string crua (R-10)
# ---------------------------------------------------------------------------


class TestGatePorSlug:
    def test_mesmo_arquivo_com_acento_diferente_nao_rebaixa(self) -> None:
        """"Navegação" no disco, "Navegacao" digitado: é o MESMO arquivo.

        A cura: `mesmo_perfil` por slug. Arrancá-la (voltar a
        ``name == self.source_name``) faz o perfil nascer ``MatchAny`` com a
        prioridade do parâmetro e sem modo — o arquivo ``navegacao.json``
        substituído SEM aviso, que é o R-10 inteiro.
        """
        origem = _perfil_com_todas_as_secoes("Navegação")
        draft = DraftConfig.from_profile(origem)

        salvo = draft.to_profile("Navegacao")

        assert isinstance(salvo.match, MatchCriteria)
        assert salvo.match.window_class == ["steam_app_3357650"]
        assert salvo.priority == 100
        assert salvo.mode is not None and salvo.mode.kind == "gamepad"
        assert salvo.suppress_desktop_emulation is True

    def test_nome_de_verdade_novo_continua_nascendo_sem_regra(self) -> None:
        """O outro lado da mordida: R-11 continua de pé.

        Sem esta prova, a cura do slug reabriria "perfil novo nasce com a regra
        de OUTRO perfil" — medido em 23/07: com o FPS ativo, "Salvar Perfil"
        como "MadJack" produzia um perfil com o regex de título do FPS e
        prioridade 60, e nenhuma regra para o jogo dela.
        """
        origem = _perfil_com_todas_as_secoes("Fps")
        draft = DraftConfig.from_profile(origem)

        salvo = draft.to_profile("MadJack")

        assert isinstance(salvo.match, MatchAny), "nome novo não herda a regra"
        assert salvo.priority != 100, "nome novo não herda a prioridade"
        assert salvo.mode is None
        assert salvo.suppress_desktop_emulation is False
        # ... mas a CONFIGURAÇÃO dela vai junto ("guarde o que eu tenho agora").
        assert tuple(salvo.leds.lightbar) == ROXO
        assert salvo.triggers.left.mode == "SemiAutoGun"
        assert salvo.controllers is not None and UNIQ in salvo.controllers


# ---------------------------------------------------------------------------
# E2 — nenhum perfil sai da janela com um número que ela não escolheu
# ---------------------------------------------------------------------------


class TestPrioridadeSemNumeroInventado:
    def test_sem_origem_e_sem_chamador_usa_o_default_do_esquema(self) -> None:
        """``to_profile("novo")`` não pode inventar 5.

        5 era o default do parâmetro e a assinatura digital dos dois perfis
        dela salvos pelo rodapé. Sem opinião de ninguém, o número é o do
        ESQUEMA — um lugar só decide qual é o default.
        """
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
        """Portão de busca (pedido da sprint, E2).

        O literal ``priority: int = 5`` tinha UMA ocorrência no projeto e ela
        produzia arquivo. Se voltar, este teste reprova antes de o disco dela
        ganhar outro catch-all empatado.
        """
        raiz = Path(__file__).resolve().parents[2] / "src"
        ofensores = [
            str(caminho.relative_to(raiz))
            for caminho in raiz.rglob("*.py")
            if "priority: int = 5" in caminho.read_text(encoding="utf-8")
        ]
        assert ofensores == []


# ---------------------------------------------------------------------------
# E3 (metade do rascunho) — modo e "modo jogo" ganham dono
# ---------------------------------------------------------------------------


class TestModoEModoJogoTemDono:
    def test_modo_editado_na_aba_sobrevive_ao_nome_novo(self) -> None:
        """O gesto DELA não é a regra de outro perfil — e por isso viaja.

        A aba Emulação escreve por ``with_mode``; salvar com nome novo tem de
        levar o modo. Arrancar o ``or self.mode_dirty`` do ``to_profile`` faz o
        modo virar ``None``, que é o estado dos perfis dela hoje.
        """
        origem = _perfil_com_todas_as_secoes("Pragmata")
        draft = DraftConfig.from_profile(origem)

        draft = draft.with_mode(
            ProfileModeConfig(kind="gamepad", gamepad_flavor="dualsense")
        )
        salvo = draft.to_profile("Pragmata3")

        assert salvo.mode is not None
        assert salvo.mode.kind == "gamepad"
        assert salvo.mode.gamepad_flavor == "dualsense"
        # A regra, não: só a configuração viaja para o nome novo (R-11).
        assert isinstance(salvo.match, MatchAny)

    def test_modo_jogo_ligado_na_aba_sobrevive_ao_nome_novo(self) -> None:
        """"Modo jogo" = suspender mouse e teclado (o esclarecimento dela)."""
        draft = DraftConfig.default().with_suppress(True)

        salvo = draft.to_profile("Pragmata3")

        assert salvo.suppress_desktop_emulation is True

    def test_desligar_o_modo_jogo_tambem_e_gesto(self) -> None:
        """Desligar é opinião como ligar — o False dela tem de sobreviver.

        Sem o flag de gesto, ``suppress=False`` seria indistinguível do default
        e o passthrough do perfil de origem (``True``) voltaria por cima.
        """
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
        """``with_profile_identity`` fecha o ciclo: o rascunho descreve o DISCO.

        Sem baixar os flags, o modo que ela ligou para o perfil A viajaria
        junto no próximo "Salvar Perfil" com o nome B — o rascunho passaria a
        semear opinião em perfil que nunca a pediu.
        """
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
        """HARM-05, na seção pior de todas.

        Um "Aplicar" disparado por ter mexido num gatilho não pode recriar o vpad
        nem suspender a emulação no meio da partida: as duas seções são
        aplicadas ao vivo pelas abas e só PERSISTEM pelo "Salvar Perfil".
        """
        draft = DraftConfig.default().with_mode(
            ProfileModeConfig(kind="gamepad", gamepad_flavor="xbox")
        ).with_suppress(True)

        payload = draft.to_ipc_dict()

        assert "mode" not in payload
        assert "suppress_desktop_emulation" not in payload
        assert "suppress" not in payload
