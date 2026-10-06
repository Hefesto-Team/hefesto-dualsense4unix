"""Estado central de configuração da GUI — DraftConfig (FEAT-PROFILE-STATE-01)."""
from __future__ import annotations

from collections.abc import Iterable
from typing import TYPE_CHECKING, Any, Literal, cast

from pydantic import BaseModel, ConfigDict, Field

from hefesto_dualsense4unix.profiles.schema import RUMBLE_CUSTOM_MULT_MAX, LedsConfig

if TYPE_CHECKING:
    from hefesto_dualsense4unix.profiles.schema import Profile


class TriggerDraft(BaseModel):
    """Draft de um único trigger (L2 ou R2).

    ``params`` é sempre PLANO — é a forma que os widgets de
    ``triggers_actions.py`` leem por índice (``params[i]``), e alargar o tipo
    para aceitar aninhado quebraria essa leitura sem tocar no mixin (Z4/T4,
    24/08/2026 — ``draft_config.py`` é a posse desta tarefa, `app/actions/*.py`
    não é).

    ``params_aninhado_original`` é o crachá do formato que o disco tinha
    *antes* de achatar (só quando o perfil trouxe ``list[list[int]]`` para
    ``MultiPositionFeedback``/``MultiPositionVibration`` — ver
    ``_triggers_config_to_draft``). Ele existe só para uma coisa: quando o
    perfil é salvo SEM que este trigger tenha sido tocado, ``to_profile``
    devolve o arquivo com a MESMA forma aninhada que tinha — nada muda por
    baixo dela. Qualquer edição pela tela cria um ``TriggerDraft`` novo sem
    este campo (`TriggerDraft(mode=..., params=...)`, sem ``model_copy``), e
    a partir daí o arquivo passa a guardar plano — que é forma válida e é o
    formato que a PRÓPRIA edição produz. Não é lido pelos widgets.
    """

    model_config = ConfigDict(frozen=True)

    mode: str = "Off"
    params: tuple[int, ...] = ()
    params_aninhado_original: tuple[tuple[int, ...], ...] | None = None


class TriggersDraft(BaseModel):
    """Draft do par de triggers."""

    model_config = ConfigDict(frozen=True)

    left: TriggerDraft = Field(default_factory=TriggerDraft)
    right: TriggerDraft = Field(default_factory=TriggerDraft)


class LedsDraft(BaseModel):
    """Draft dos LEDs (lightbar + player LEDs).

    ``lightbar_rgb``: cor RGB ou None (apagado).
    ``lightbar_brightness``: 0-100 inteiro (%) — equivale a 0.0-1.0 no
        protocolo IPC (dividido por 100 antes de enviar).
    ``player_leds``: tupla de 5 booleanos (LED1..LED5).
    ``mic_led``: reservado para V2 (INFRA-SET-MIC-LED-01); default False,
        não acessado por nenhum widget desta sprint.
    ``auto_player_colors``: toggle "Cores automáticas por controle" (COR-04)
        — espelha ``LedsConfig.auto_player_colors`` do schema. Campo do
        PERFIL: só a seção GLOBAL do draft o carrega com significado; os
        overrides por-controle NUNCA o gravam (``_leds_draft_to_config`` só
        o emite com ``include_auto=True``, usado pelo ``to_profile`` e pelo
        ``to_ipc_dict`` — nunca por ``with_controller_leds``).
    """

    model_config = ConfigDict(frozen=True)

    lightbar_rgb: tuple[int, int, int] | None = (255, 128, 0)
    lightbar_brightness: int = Field(default=100, ge=0, le=100)
    player_leds: tuple[bool, bool, bool, bool, bool] = (False, False, False, False, False)
    mic_led: bool = False
    auto_player_colors: bool = True
    player_led_brightness: str = str(
        LedsConfig.model_fields["player_led_brightness"].default
    )


class RumbleDraft(BaseModel):
    """Draft de rumble.

    ``weak``/``strong``: teste de motores (não persistem no perfil).

    ``policy``/``custom_mult``: política de intensidade persistível no PERFIL
    (FEAT-RUMBLE-POLICY-PROFILE-01). ``policy=None`` = perfil sem opinião
    (ativar não mexe na política global do daemon). A aba Rumble grava aqui
    cada escolha da usuária, para o "Salvar Perfil" do rodapé persistir o que
    ela vê; ``custom_mult`` só acompanha ``policy="custom"``, e a faixa dele é
    a do esquema do perfil (``RUMBLE_CUSTOM_MULT_MAX``), nunca um número
    escrito aqui.

    ``passthrough``: preserva o campo v1 do perfil no round-trip
    (não editável pela GUI nesta sprint).
    """

    model_config = ConfigDict(frozen=True)

    weak: int = Field(default=0, ge=0, le=255)
    strong: int = Field(default=0, ge=0, le=255)
    policy: Literal["economia", "balanceado", "max", "auto", "custom"] | None = None
    custom_mult: float | None = Field(default=None, ge=0.0, le=RUMBLE_CUSTOM_MULT_MAX)
    passthrough: bool = True


class MouseDraft(BaseModel):
    """Draft da emulacao de mouse."""

    model_config = ConfigDict(frozen=True)

    enabled: bool = False
    speed: int = Field(default=6, ge=1, le=12)
    scroll_speed: int = Field(default=1, ge=1, le=5)
    dirty: bool = False
    in_profile: bool = False


class EmulationDraft(BaseModel):
    """Draft da emulacao Xbox360."""

    model_config = ConfigDict(frozen=True)

    xbox360_enabled: bool = False


class MicDraft(BaseModel):
    """Draft do MICROFONE (MIC-EXPOSE-01, 25/07; volume e mudo em 18/08/2026).

    ``button_toggles_system`` espelha ``ProfileMicConfig.button_toggles_system``
    e o ``DaemonConfig.mic_button_toggles_system`` (daemon/lifecycle.py:163): o
    botão de mic do controle alterna (ou não) o mute do microfone PADRÃO DO
    SISTEMA. ``None`` = **sem opinião**, e é o default DAQUI de propósito —
    ver o gate por campo no parágrafo abaixo.

    ``volume`` (0-100, o por cento da FONTE de captura no sistema) e ``muted``
    (o mudo do FIRMWARE do controle) espelham os dois campos homônimos de
    ``ProfileMicConfig``. Eles entraram em 18/08/2026, a pedido — depois
    de o microfone ficar mudo e o DON'T SCREAM não ouvir nada: *"informação de
    microfone e som, touch, acelerômetro, giroscópio e afins. cara, temos que
    salvar isso no perfil sempre."*

    **NOTA DATADA — 18/08/2026.** Este parágrafo dizia que o mic não tinha
    escritor na janela e que a seção só nascia pela leitura do disco. Isso
    caducou: o controle deslizante e o botão Silenciar do card do controle
    passam a anotar aqui pelo escritor único
    ``registrar_microfone_no_rascunho``, no callback de sucesso do daemon —
    a mesma disciplina do alto-falante.

    ``dirty``/``in_profile`` seguem a mesma disciplina do ``MouseDraft``:
    ``to_ipc_dict`` só emite a seção quando a usuária mexeu nela (dirty), e
    ``to_profile`` só a persiste quando ela foi mexida OU o perfil de origem
    já a tinha — perfis legados fazem round-trip sem ganhar seção fantasma.

    ``volume=None``/``muted=None`` = o gesto que passou por aqui não tinha
    opinião sobre AQUELE campo, e a ausência é preservada (mesma razão do
    ``rota`` do ``SpeakerDraft``): mexer no volume não pode apagar o mudo que
    ela acabou de escolher, nem o contrário.

    **O GATE É POR CAMPO, e desde 22/08/2026 vale também para o booleano.**
    Ele era por SEÇÃO: qualquer gesto de microfone (arrastar o volume, clicar
    em Silenciar) marcava ``dirty``, e o "Aplicar" do rodapé levava junto o
    ``button_toggles_system`` — que NENHUMA superfície escreve, então o valor
    que viajava era o default de fábrica, uma opinião que ninguém deu.
    O molde da cura é o ``rota`` do ``SpeakerDraft``, que já fazia certo:
    ``None`` é sem opinião, a chave não viaja, e campo ausente é campo não
    tocado. O custo do defeito era pequeno (a ativação de perfil não lê este
    campo — ``profiles/manager.py::apply_mic`` só aplica volume e mudo — e o
    valor volta no restart do daemon), mas ele derrubava calado um ``False``
    escolhido no ``DaemonConfig``.
    """

    model_config = ConfigDict(frozen=True)

    button_toggles_system: bool | None = None
    volume: int | None = Field(default=None, ge=0, le=100)
    muted: bool | None = None
    gain: int | None = Field(default=None, ge=0, le=100)
    dirty: bool = False
    in_profile: bool = False


class SpeakerDraft(BaseModel):
    """Draft do ALTO-FALANTE do controle (SOM-02/E4, 29/07)."""

    model_config = ConfigDict(frozen=True)

    volume: int | None = Field(default=None, ge=0, le=255)
    muted: bool = False
    rota: int | None = Field(default=None, ge=0, le=3)
    #: escrevo".
    #:
    #: **ELE FALTAVA AQUI, e a falta DESTRUÍA a escolha do usuário** — 10/09/2026.
    #: `ProfileSpeakerConfig.fonte` existe desde 09/09 e o daemon o OBEDECE
    #: (`AltoFalanteSubsystem._fonte_do_controle`), mas o caminho de disco da
    #: janela e da aba Perfis passa por este draft: sem o campo, todo "Salvar
    #: Perfil" reescrevia a seção do som sem ele. É a família exata do item 13
    #: do laudo de 05/09 — *"o Salvar DESTRUÍA o que a aba tinha gravado"*.
    fonte: Literal["mix", "sfx"] | None = None
    #: o botão «Padrão» do volume (`ProfileSpeakerConfig.volume_padrao`): sem o campo aqui, todo
    #: «Salvar Perfil» o apagaria, que é a família do `fonte` logo acima.
    volume_padrao: bool | None = None
    dirty: bool = False
    in_profile: bool = False


def _leds_config_to_draft(leds_cfg: Any) -> LedsDraft:
    """Converte ``LedsConfig`` (schema) no sub-draft de LEDs da GUI."""
    rgb_raw = leds_cfg.lightbar
    brightness_raw = float(leds_cfg.lightbar_brightness)
    brightness_pct = max(0, min(100, round(brightness_raw * 100)))
    player = tuple(bool(b) for b in leds_cfg.player_leds)
    while len(player) < 5:
        player = (*player, False)
    player_5: tuple[bool, bool, bool, bool, bool] = (
        player[0], player[1], player[2], player[3], player[4]
    )
    from hefesto_dualsense4unix.core.led_control import cor_escolhida

    lida = cor_escolhida((int(rgb_raw[0]), int(rgb_raw[1]), int(rgb_raw[2])))
    return LedsDraft(
        lightbar_rgb=lida,
        lightbar_brightness=brightness_pct,
        player_leds=player_5,
        auto_player_colors=bool(getattr(leds_cfg, "auto_player_colors", True)),
        player_led_brightness=str(getattr(
            leds_cfg, "player_led_brightness",
            LedsConfig.model_fields["player_led_brightness"].default)),
    )


def _leds_draft_to_config(
    leds: LedsDraft,
    *,
    include_auto: bool = False,
    only_fields: set[str] | None = None,
) -> Any:
    """Converte o sub-draft de LEDs em ``LedsConfig`` persistível (schema).

    COR-04: ``include_auto=True`` (usado SÓ pela seção GLOBAL — ``to_profile``)
    emite ``auto_player_colors`` explicitamente. O default False mantém os
    overrides por-controle (``with_controller_leds``) SEM o campo: o toggle é
    do perfil, e gravá-lo no override densificaria uma seção parcial com um
    campo que o backend ignora (regra documentada no schema ``LedsConfig``).

    ``only_fields`` (COR-04) restringe o ``LedsConfig`` aos campos nomeados
    (nomes do schema: ``lightbar``/``lightbar_brightness``/``player_leds``), de
    modo que o ``model_fields_set`` resultante fique PARCIAL — o backend herda
    os campos ausentes do global por campo (a paleta automática segue acendendo
    o LED do número no controle). ``None`` (default) mantém a seção densa (usada
    pela seção GLOBAL do ``to_profile``).
    """
    from hefesto_dualsense4unix.profiles.schema import LedsConfig

    rgb = leds.lightbar_rgb
    kwargs: dict[str, Any] = {
        "player_leds": list(leds.player_leds),
        "lightbar_brightness": leds.lightbar_brightness / 100.0,
    }
    if rgb is not None:
        kwargs["lightbar"] = rgb
    if include_auto:
        kwargs["auto_player_colors"] = leds.auto_player_colors
        kwargs["player_led_brightness"] = leds.player_led_brightness
    if only_fields is not None:
        kwargs = {nome: val for nome, val in kwargs.items() if nome in only_fields}
    return LedsConfig(**kwargs)


def _trigger_params_para_draft(
    raw: list[int] | list[list[int]],
) -> tuple[tuple[int, ...], tuple[tuple[int, ...], ...] | None]:
    """Achata ``TriggerConfig.params`` para o rascunho (Z4/T4, 24/08/2026).

    O disco aceita ``list[int]`` (plano) OU ``list[list[int]]`` (aninhado,
    canônico para ``MultiPositionFeedback``/``MultiPositionVibration`` — ver
    ``core.trigger_effects._flatten_multi_position``). O rascunho só entende
    plano (os widgets leem por índice). Quando a entrada é aninhada, devolve
    também a forma original, para ``_triggers_draft_to_config`` poder
    devolvê-la intacta se ninguém tocou no gatilho entre abrir e salvar —
    sem isso, TODO perfil com gatilho aninhado mudaria de forma no primeiro
    "Salvar Perfil", mesmo sem editar nada (era o defeito medido em
    ``aventura.json``/``corrida.json``, seção 2.1 da sprint).
    """
    from hefesto_dualsense4unix.core.trigger_effects import _flatten_multi_position

    if raw and isinstance(raw[0], list):
        nested = tuple(tuple(int(v) for v in sub) for sub in raw)
        flat = tuple(_flatten_multi_position([list(sub) for sub in nested]))
        return flat, nested
    return tuple(int(v) for v in cast("list[int]", raw)), None


def _triggers_config_to_draft(cfg: Any) -> TriggersDraft:
    """Converte ``TriggersConfig`` (schema) no sub-draft de gatilhos da GUI."""
    left_flat, left_nested = _trigger_params_para_draft(cfg.left.params)
    right_flat, right_nested = _trigger_params_para_draft(cfg.right.params)
    return TriggersDraft(
        left=TriggerDraft(
            mode=cfg.left.mode,
            params=left_flat,
            params_aninhado_original=left_nested,
        ),
        right=TriggerDraft(
            mode=cfg.right.mode,
            params=right_flat,
            params_aninhado_original=right_nested,
        ),
    )


def _override_vazio(override: Any) -> bool:
    """True quando um ``ControllerOverrides`` não tem mais NENHUMA seção."""
    campos = getattr(type(override), "model_fields", None)
    if not campos:
        return False
    return all(getattr(override, nome, None) is None for nome in campos)


def _trigger_params_para_disco(trigger: TriggerDraft) -> list[int] | list[list[int]]:
    """Devolve ``TriggerConfig.params`` no formato que vai para o disco.

    Se este trigger não foi tocado desde que veio do arquivo (o achatado
    ainda bate com o aninhado original — ver ``params_aninhado_original`` em
    ``TriggerDraft``), devolve a forma aninhada intacta: salvar sem editar o
    gatilho não pode mudar a forma do arquivo dela (Z4/T4). Se foi editado —
    ou nunca teve forma aninhada — devolve o achatado, que é forma válida
    para ``TriggerConfig.params`` (``profiles/schema.py``) e é o que a
    própria edição produziu.
    """
    from hefesto_dualsense4unix.core.trigger_effects import _flatten_multi_position

    original = trigger.params_aninhado_original
    if original is not None:
        flat_do_original = tuple(
            _flatten_multi_position([list(sub) for sub in original])
        )
        if flat_do_original == trigger.params:
            return [list(sub) for sub in original]
    return list(trigger.params)


def _triggers_draft_to_config(triggers: TriggersDraft) -> Any:
    """Converte o sub-draft de gatilhos em ``TriggersConfig`` persistível."""
    from hefesto_dualsense4unix.profiles.schema import TriggerConfig, TriggersConfig

    return TriggersConfig(
        left=TriggerConfig(
            mode=triggers.left.mode,
            params=_trigger_params_para_disco(triggers.left),
        ),
        right=TriggerConfig(
            mode=triggers.right.mode,
            params=_trigger_params_para_disco(triggers.right),
        ),
    )


class DraftConfig(BaseModel):
    """Estado central imutavel da GUI — snapshot de tudo que o daemon pode aplicar."""

    model_config = ConfigDict(frozen=True)

    triggers: TriggersDraft = Field(default_factory=TriggersDraft)
    leds: LedsDraft = Field(default_factory=LedsDraft)
    rumble: RumbleDraft = Field(default_factory=RumbleDraft)
    mouse: MouseDraft = Field(default_factory=MouseDraft)
    emulation: EmulationDraft = Field(default_factory=EmulationDraft)
    mic: MicDraft = Field(default_factory=MicDraft)
    speaker: SpeakerDraft = Field(default_factory=SpeakerDraft)
    # None = herdar DEFAULT_BUTTON_BINDINGS; {} = teclado silencioso; dict
    key_bindings: dict[str, list[str]] | None = None

    source_match: Any | None = None
    source_mode: Any | None = None
    source_suppress: bool = False
    source_priority: int | None = None
    mode_dirty: bool = False
    suppress_dirty: bool = False
    source_controllers: Any | None = None
    controllers_esvaziados_nesta_edicao: bool = False
    # (`profiles_actions._build_profile_from_editor`). O gesto mais banal dela
    # `manager.pontes_confirmadas()` e a escada de `integrations/ponte_escada.py`
    source_ponte: Any | None = None
    # valendo): `button_actions={"circle": "KEY_ESC"}` entrava e saía `None`;
    # `Profile` (`Profile.button_actions` e `Profile.teclado_emulado`, em
    # método. O `button_actions` nasceu por decisão em 01/09 e nenhum
    source_button_actions: Any | None = None
    source_teclado_emulado: bool | None = None
    source_remapeamento: dict[str, str] | None = None
    source_movimento: Any | None = None

    source_name: str | None = None


    @classmethod
    def default(cls) -> DraftConfig:
        """Instancia com valores padrão seguros (sem hardware aplicado)."""
        return cls()

    @classmethod
    def from_profile(cls, profile: Profile) -> DraftConfig:
        """Constroi DraftConfig a partir de um Profile persistido."""
        triggers = _triggers_config_to_draft(profile.triggers)
        leds = _leds_config_to_draft(profile.leds)

        rumble = RumbleDraft(
            policy=profile.rumble.policy,
            custom_mult=profile.rumble.custom_mult,
            passthrough=profile.rumble.passthrough,
        )

        if profile.mouse is not None:
            mouse = MouseDraft(
                enabled=profile.mouse.enabled,
                speed=profile.mouse.speed,
                scroll_speed=profile.mouse.scroll_speed,
                dirty=False,
                in_profile=True,
            )
        else:
            mouse = MouseDraft()
        emulation = EmulationDraft()

        if profile.mic is not None:
            mic = MicDraft(
                button_toggles_system=profile.mic.button_toggles_system,
                volume=profile.mic.volume,
                muted=profile.mic.muted,
                gain=profile.mic.gain,
                dirty=False,
                in_profile=True,
            )
        else:
            mic = MicDraft()

        if profile.speaker is not None:
            speaker = SpeakerDraft(
                volume=profile.speaker.volume,
                muted=profile.speaker.muted,
                rota=getattr(profile.speaker, "rota", None),
                fonte=getattr(profile.speaker, "fonte", None),
                volume_padrao=getattr(profile.speaker, "volume_padrao", None),
                dirty=False,
                in_profile=True,
            )
        else:
            speaker = SpeakerDraft()

        return cls(
            triggers=triggers,
            leds=leds,
            rumble=rumble,
            mouse=mouse,
            mic=mic,
            speaker=speaker,
            emulation=emulation,
            key_bindings=profile.key_bindings,
            source_match=profile.match,
            source_mode=profile.mode,
            source_suppress=profile.suppress_desktop_emulation,
            source_priority=profile.priority,
            source_controllers=profile.controllers,
            source_ponte=profile.ponte,
            source_button_actions=profile.button_actions,
            source_teclado_emulado=profile.teclado_emulado,
            source_remapeamento=profile.remapeamento,
            source_movimento=profile.movimento,
            source_name=profile.name,
        )

    def to_profile(self, name: str, priority: int | None = None) -> Profile:
        """Converte o draft em um Profile persistivel.

        Apenas os campos suportados pelo schema Profile v1 sao preenchidos.
        FEAT-POINT-AND-CLICK-01: a seção ``mouse`` agora É suportada pelo
        schema — incluída quando ``self.mouse.dirty`` (a usuária tocou a seção
        nesta sessão) OU ``self.mouse.in_profile`` (o perfil de origem já a
        tinha). BUG-MOUSE-SAVE-DROPS-SECTION-01: sem o segundo caso, salvar um
        perfil point-and-click sem mexer na aba Mouse descartava a seção e
        matava a feature; perfis legados (sem seção) seguem round-trip
        inalterados (in_profile=False e dirty=False → sem seção fantasma).
        FEAT-RUMBLE-POLICY-PROFILE-01: a política de rumble agora É persistida
        — ``rumble.policy``/``rumble.custom_mult`` do draft vão para a seção
        ``rumble`` do perfil (None = perfil sem opinião, round-trip sem
        inventar política) e ``passthrough`` é preservado. Campos ainda sem
        suporte no schema (emulation) continuam descartados.
        BUG-FOOTER-SAVE-DROPS-SECTIONS-01: ``match``, ``mode``,
        ``suppress_desktop_emulation`` e ``priority`` do perfil de ORIGEM são
        reemitidos (o draft não os edita; salvar o perfil ativo pelo rodapé
        não pode zerá-los). Draft sem origem (perfil novo) usa os defaults.
        PERFIL-02: o mapa ``controllers`` (overrides por MAC) é reemitido do
        perfil de origem pelo mesmo motivo — sem o passthrough, o primeiro
        "Salvar Perfil" apagaria os ajustes por-controle da usuária.
        PONTE-CONFIRMADA-01: o carimbo ``ponte`` é reemitido pelo mesmo
        passthrough, gateado pelo ``mesmo_perfil`` — sem escritor na janela.
        PERFIL-SALVA-TUDO-01: ``mode`` e ``suppress_desktop_emulation`` também
        saem daqui quando ELA os editou nesta sessão (``mode_dirty`` /
        ``suppress_dirty``) — nesse caso o valor vale mesmo com nome NOVO,
        porque é gesto do usuário e não a regra herdada de outro perfil.

        ``priority=None`` (default) significa "o chamador não tem opinião": o
        número vem do perfil de ORIGEM quando é o mesmo perfil e, na falta dele,
        do DEFAULT DO ESQUEMA. Nunca de um literal inventado aqui: o antigo
        default 5 desta assinatura era a assinatura digital dos perfis do usuário
        salvos pelo rodapé (``pragmata.json`` e ``pragmata2.json``, prioridade 5
        sem ela ter tocado no slider, empatados entre si e com os outros
        catch-all). Um portão de busca em
        ``tests/unit/test_perfil_salva_tudo_rascunho.py`` impede a volta dele.

        Retorna instancia validada via ``Profile.model_validate``.
        """
        from hefesto_dualsense4unix.profiles.schema import (
            MatchAny,
            Profile,
            ProfileMicConfig,
            ProfileMouseConfig,
            ProfileSpeakerConfig,
            RumbleConfig,
        )
        from hefesto_dualsense4unix.profiles.slug import mesmo_slug

        mouse_cfg = (
            ProfileMouseConfig(
                enabled=self.mouse.enabled,
                speed=self.mouse.speed,
                scroll_speed=self.mouse.scroll_speed,
            )
            if (self.mouse.dirty or self.mouse.in_profile)
            else None
        )
        mic_cfg = (
            ProfileMicConfig(
                button_toggles_system=(
                    True
                    if self.mic.button_toggles_system is None
                    else self.mic.button_toggles_system
                ),
                volume=self.mic.volume,
                muted=self.mic.muted,
                gain=self.mic.gain,
            )
            if (self.mic.dirty or self.mic.in_profile)
            else None
        )
        speaker_cfg = (
            ProfileSpeakerConfig(
                volume=self.speaker.volume,
                muted=self.speaker.muted,
                rota=self.speaker.rota,
                fonte=self.speaker.fonte,
                volume_padrao=self.speaker.volume_padrao,
            )
            if (
                self.speaker.volume is not None
                and (self.speaker.dirty or self.speaker.in_profile)
            )
            else None
        )

        # título do FPS e prioridade 60 — e nenhuma regra para o jogo do usuário.
        # já tem a comparação certa (`profiles/slug.mesmo_slug`, usada nas duas
        mesmo_perfil = self.source_name is not None and (
            name == self.source_name or mesmo_slug(name, self.source_name)
        )
        prioridade_final: int
        if mesmo_perfil and self.source_priority is not None:
            prioridade_final = int(self.source_priority)
        elif priority is not None:
            prioridade_final = int(priority)
        else:
            prioridade_final = int(Profile.model_fields["priority"].default)
        profile = Profile(
            name=name,
            priority=prioridade_final,
            match=(
                self.source_match
                if (mesmo_perfil and self.source_match is not None)
                else MatchAny()
            ),
            mode=self.source_mode if (mesmo_perfil or self.mode_dirty) else None,
            suppress_desktop_emulation=(
                self.source_suppress
                if (mesmo_perfil or self.suppress_dirty)
                else False
            ),
            triggers=_triggers_draft_to_config(self.triggers),
            leds=_leds_draft_to_config(self.leds, include_auto=True),
            rumble=RumbleConfig(
                passthrough=self.rumble.passthrough,
                policy=self.rumble.policy,
                custom_mult=self.rumble.custom_mult,
            ),
            key_bindings=self.key_bindings,
            button_actions=self.source_button_actions,
            teclado_emulado=self.source_teclado_emulado,
            remapeamento=self.source_remapeamento,
            movimento=self.source_movimento,
            mouse=mouse_cfg,
            mic=mic_cfg,
            speaker=speaker_cfg,
            controllers=self.source_controllers,
            ponte=self.source_ponte if mesmo_perfil else None,
        )
        payload = profile.model_dump(mode="python")
        payload["controllers"] = profile.controllers
        return Profile.model_validate(payload)


    def controller_override(self, uniq: str | None) -> Any | None:
        """Override do controle ``uniq`` no mapa em edição, ou None.

        ``uniq`` é o MAC normalizado (12 hex) que o seletor de alvo da GUI
        deriva do ``state_full`` (o mesmo ``uniq`` do bloco ``controllers``).
        Devolve o ``ControllerOverrides`` do schema (validando entradas cruas
        defensivamente) — None quando não há mapa, não há entrada, ou o alvo
        é "Todos" (``uniq`` None).
        """
        if not uniq:
            return None
        mapa = self.source_controllers
        if not isinstance(mapa, dict):
            return None
        entry = mapa.get(uniq)
        if entry is None:
            return None
        from hefesto_dualsense4unix.profiles.schema import ControllerOverrides

        if isinstance(entry, ControllerOverrides):
            return entry
        return ControllerOverrides.model_validate(entry)


    def with_controller_rumble(self, uniq: str, rumble: RumbleDraft) -> DraftConfig:
        """Novo draft com a INTENSIDADE de ``uniq`` substituída."""
        from hefesto_dualsense4unix.profiles.schema import ControllerRumbleOverride

        igual_ao_global = (
            rumble.policy == self.rumble.policy
            and rumble.custom_mult == self.rumble.custom_mult
        )
        if igual_ao_global or rumble.policy is None or rumble.policy == "auto":
            return self.with_controller_fields_cleared(
                uniq, "rumble", {"policy", "custom_mult"}
            )
        campos: dict[str, Any] = {"policy": rumble.policy}
        if rumble.policy == "custom":
            campos["custom_mult"] = rumble.custom_mult
        return self._with_override_section(
            uniq, "rumble", ControllerRumbleOverride(**campos)
        )

    def effective_speaker_for(self, uniq: str | None) -> SpeakerDraft:
        """Alto-falante EFETIVO que o card exibe para o alvo ``uniq``."""
        override = self.controller_override(uniq)
        cfg = getattr(override, "speaker", None)
        if cfg is None:
            return self.speaker
        return SpeakerDraft(
            volume=int(cfg.volume),
            muted=bool(cfg.muted),
            rota=getattr(cfg, "rota", None),
            fonte=getattr(cfg, "fonte", None),
            volume_padrao=getattr(cfg, "volume_padrao", None),
            dirty=self.speaker.dirty,
            in_profile=True,
        )

    def with_controller_speaker(self, uniq: str, speaker: SpeakerDraft) -> DraftConfig:
        """Novo draft com o alto-falante de ``uniq`` substituído."""
        from hefesto_dualsense4unix.profiles.schema import ProfileSpeakerConfig

        igual_ao_global = (
            speaker.volume == self.speaker.volume
            and speaker.muted == self.speaker.muted
            and speaker.rota == self.speaker.rota
            and speaker.fonte == self.speaker.fonte
            and speaker.volume_padrao == self.speaker.volume_padrao
        )
        if speaker.volume is None or igual_ao_global:
            return self.with_controller_fields_cleared(
                uniq, "speaker", {"volume", "muted", "rota", "fonte", "volume_padrao"}
            )
        return self._with_override_section(
            uniq,
            "speaker",
            ProfileSpeakerConfig(
                volume=int(speaker.volume),
                muted=bool(speaker.muted),
                rota=speaker.rota,
                fonte=speaker.fonte,
                volume_padrao=speaker.volume_padrao,
            ),
        )

    def effective_mic_for(self, uniq: str | None) -> MicDraft:
        """Microfone EFETIVO que o card exibe para o alvo ``uniq``."""
        override = self.controller_override(uniq)
        cfg = getattr(override, "mic", None)
        if cfg is None:
            return self.mic
        campos = cfg.model_fields_set
        return self.mic.model_copy(update={
            nome: getattr(cfg, nome)
            for nome in type(cfg).model_fields if nome in campos
        } | {"in_profile": True})

    def with_controller_mic(self, uniq: str, mic: MicDraft) -> DraftConfig:
        """Novo draft com o microfone de ``uniq`` substituído."""
        from hefesto_dualsense4unix.profiles.schema import ControllerMicOverride

        campos: dict[str, Any] = {}
        if mic.volume is not None and mic.volume != self.mic.volume:
            campos["volume"] = int(mic.volume)
        if mic.gain is not None and mic.gain != self.mic.gain:
            campos["gain"] = int(mic.gain)
        if not campos:
            return self.with_controller_fields_cleared(uniq, "mic", {"volume", "gain"})
        antes = getattr(self.controller_override(uniq), "mic", None)
        if antes is not None and "muted" in antes.model_fields_set:
            campos["muted"] = antes.muted
        return self._with_override_section(
            uniq, "mic", ControllerMicOverride(**campos)
        )


    def _with_override_section(
        self, uniq: str, section: str, value: Any
    ) -> DraftConfig:
        """Grava ``value`` na seção ``section`` do override de ``uniq``."""
        from hefesto_dualsense4unix.profiles.schema import ControllerOverrides

        mapa: dict[str, Any] = dict(self.source_controllers or {})
        atual = self.controller_override(uniq) or ControllerOverrides()
        mapa[uniq] = atual.model_copy(update={section: value})
        return self.model_copy(
            update={
                "source_controllers": mapa,
                "controllers_esvaziados_nesta_edicao": False,
            }
        )


    def with_controller_fields_cleared(
        self, uniq: str, section: str, fields: Iterable[str]
    ) -> DraftConfig:
        """Limpa ``fields`` da seção ``section`` do override de UM ``uniq``."""
        override = self.controller_override(uniq)
        if override is None:
            return self
        cfg = getattr(override, section, None)
        alvo_campos = set(fields)
        if cfg is None or not (cfg.model_fields_set & alvo_campos):
            return self
        restantes = cfg.model_fields_set - alvo_campos
        nova_secao = (
            type(cfg)(**{nome: getattr(cfg, nome) for nome in restantes})
            if restantes
            else None
        )
        novo_override = override.model_copy(update={section: nova_secao})
        mapa: dict[str, Any] = dict(self.source_controllers or {})
        if _override_vazio(novo_override):
            mapa.pop(uniq, None)
        else:
            mapa[uniq] = novo_override
        return self.model_copy(
            update={
                "source_controllers": mapa or None,
                "controllers_esvaziados_nesta_edicao": not mapa,
            }
        )


__all__ = [
    "DraftConfig",
    "EmulationDraft",
    "LedsDraft",
    "MicDraft",
    "MouseDraft",
    "RumbleDraft",
    "SpeakerDraft",
    "TriggerDraft",
    "TriggersDraft",
]
