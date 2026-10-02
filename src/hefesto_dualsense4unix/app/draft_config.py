"""Estado central de configuração da GUI — DraftConfig (FEAT-PROFILE-STATE-01)."""
from __future__ import annotations

from collections.abc import Iterable
from typing import TYPE_CHECKING, Any, Literal, cast

from pydantic import BaseModel, ConfigDict, Field

from hefesto_dualsense4unix.app.alvo_de_edicao import alvo_de_edicao
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
    ``ProfileMicConfig``. Eles entraram em 18/08/2026, a pedido dela — depois
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
    que viajava era o default de fábrica, uma opinião que ninguém deu. Do outro
    lado, ``ipc_draft_applier._apply_mic`` a escreve na config VIVA do daemon.
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
    #: **ELE FALTAVA AQUI, e a falta DESTRUÍA a escolha dela** — 10/09/2026.
    #: `ProfileSpeakerConfig.fonte` existe desde 09/09 e o daemon o OBEDECE
    #: (`AltoFalanteSubsystem._fonte_do_controle`), mas o caminho de disco da
    #: janela e da aba Perfis passa por este draft: sem o campo, todo "Salvar
    #: Perfil" reescrevia a seção do som sem ele. É a família exata do item 13
    #: do laudo de 05/09 — *"o Salvar DESTRUÍA o que a aba tinha gravado"*.
    fonte: Literal["mix", "sfx"] | None = None
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
    # método. O `button_actions` nasceu por decisão dela em 01/09 e nenhum
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
        porque é gesto dela e não a regra herdada de outro perfil.

        ``priority=None`` (default) significa "o chamador não tem opinião": o
        número vem do perfil de ORIGEM quando é o mesmo perfil e, na falta dele,
        do DEFAULT DO ESQUEMA. Nunca de um literal inventado aqui: o antigo
        default 5 desta assinatura era a assinatura digital dos perfis dela
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
            )
            if (
                self.speaker.volume is not None
                and (self.speaker.dirty or self.speaker.in_profile)
            )
            else None
        )

        # título do FPS e prioridade 60 — e nenhuma regra para o jogo dela.
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


    def with_profile_identity(self, profile: Any) -> DraftConfig:
        """Rascunho reapontado para ``profile``, o perfil ACABADO DE GRAVAR."""
        return self.model_copy(
            update={
                "source_name": profile.name,
                "source_match": profile.match,
                "source_mode": profile.mode,
                "source_priority": profile.priority,
                "source_suppress": bool(profile.suppress_desktop_emulation),
                "source_ponte": profile.ponte,
                "mode_dirty": False,
                "suppress_dirty": False,
            }
        )


    def with_mode(self, mode: Any | None) -> DraftConfig:
        """Rascunho com o MODO do perfil trocado por gesto DELA."""
        return self.model_copy(update={"source_mode": mode, "mode_dirty": True})

    def with_suppress(self, suppress: bool) -> DraftConfig:
        """Rascunho com o "modo jogo" (suspender mouse/teclado) trocado por ela."""
        return self.model_copy(
            update={"source_suppress": bool(suppress), "suppress_dirty": True}
        )

    def with_mic(
        self,
        *,
        volume: int | None = None,
        muted: bool | None = None,
        soltar_mudo: bool = False,
    ) -> DraftConfig:
        """Rascunho com o MICROFONE trocado por gesto DELA (18/08/2026)."""
        del muted, soltar_mudo
        return self.model_copy(
            update={
                "mic": self.mic.model_copy(
                    update={
                        "volume": (
                            self.mic.volume
                            if volume is None
                            else max(0, min(100, int(volume)))
                        ),
                        "dirty": True,
                        "in_profile": True,
                    }
                )
            }
        )

    def with_speaker(
        self, volume: int, *, muted: bool = False, rota: int | None = None
    ) -> DraftConfig:
        """Rascunho com o ALTO-FALANTE trocado por gesto DELA."""
        return self.model_copy(
            update={
                "speaker": SpeakerDraft(
                    volume=max(0, min(255, int(volume))),
                    muted=bool(muted),
                    rota=self.speaker.rota if rota is None else int(rota),
                    fonte=self.speaker.fonte,
                    dirty=True,
                    in_profile=True,
                )
            }
        )

    def without_speaker(self) -> DraftConfig:
        """Rascunho SEM a seção do alto-falante — ela DEVOLVEU a posse.

        SOM-02/E3 mais SOM-02/E4. "Soltar" faz o hefesto parar de mandar os
        bytes de volume: o registrador volta a ser do firmware e o
        ``daemon.state_full`` deixa de publicar a chave ``speaker``. Um perfil
        salvo DEPOIS desse gesto não pode continuar carregando um número —
        ``lifecycle.apply_profile_speaker`` o reaplicaria na ativação seguinte
        e tomaria de volta uma posse que ela acabou de largar, que é
        exatamente o eco de estado velho que esta fiação existe para matar.

        Zera a seção inteira (volta ao ``SpeakerDraft()`` de fábrica) em vez de
        só apagar o número: com ``volume=None`` o gate de ``to_profile`` já
        omite a seção, e deixar ``muted``/``in_profile`` de pé seria guardar a
        sombra de uma opinião que não existe mais.
        """
        return self.model_copy(update={"speaker": SpeakerDraft()})


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

    def effective_leds_for(self, uniq: str | None) -> LedsDraft:
        """LEDs EFETIVOS que a aba exibe para o alvo ``uniq``."""
        override = self.controller_override(uniq)
        leds_cfg = getattr(override, "leds", None)
        if leds_cfg is None:
            return self.leds
        campos = leds_cfg.model_fields_set
        base = _leds_config_to_draft(leds_cfg)
        herdados: dict[str, Any] = {}
        if "lightbar" not in campos:
            herdados["lightbar_rgb"] = self.leds.lightbar_rgb
        if "lightbar_brightness" not in campos:
            herdados["lightbar_brightness"] = self.leds.lightbar_brightness
        if "player_leds" not in campos:
            herdados["player_leds"] = self.leds.player_leds
        return base.model_copy(update=herdados) if herdados else base

    def effective_triggers_for(self, uniq: str | None) -> TriggersDraft:
        """Gatilhos EFETIVOS que a aba exibe para o alvo ``uniq`` (ver leds)."""
        override = self.controller_override(uniq)
        triggers_cfg = getattr(override, "triggers", None)
        if triggers_cfg is None:
            return self.triggers
        lados = triggers_cfg.model_fields_set
        base = _triggers_config_to_draft(triggers_cfg)
        herdados: dict[str, Any] = {}
        if "left" not in lados:
            herdados["left"] = self.triggers.left
        if "right" not in lados:
            herdados["right"] = self.triggers.right
        return base.model_copy(update=herdados) if herdados else base

    def with_controller_leds(self, uniq: str, leds: LedsDraft) -> DraftConfig:
        """Novo draft com a seção ``leds`` do override de ``uniq`` substituída."""
        campos: set[str] = set()
        if leds.lightbar_rgb is not None and leds.lightbar_rgb != self.leds.lightbar_rgb:
            campos.add("lightbar")
        if leds.lightbar_brightness != self.leds.lightbar_brightness:
            campos.add("lightbar_brightness")
        if leds.player_leds != self.leds.player_leds:
            campos.add("player_leds")
        if not campos:
            return self.with_controller_fields_cleared(
                uniq, "leds", {"lightbar", "lightbar_brightness", "player_leds"}
            )
        from hefesto_dualsense4unix.profiles.schema import com_o_brilho_das_luzes_de

        antes = getattr(self.controller_override(uniq), "leds", None)
        secao = com_o_brilho_das_luzes_de(
            antes, _leds_draft_to_config(leds, only_fields=campos))
        return self._with_override_section(
            uniq, "leds", _com_a_procedencia_da_mesma_cor(antes, secao))

    def with_controller_triggers(
        self, uniq: str, triggers: TriggersDraft
    ) -> DraftConfig:
        """Novo draft com a seção ``triggers`` do override de ``uniq`` substituída."""
        return self._with_override_section(
            uniq, "triggers", _triggers_draft_to_config(triggers)
        )


    def effective_rumble_for(self, uniq: str | None) -> RumbleDraft:
        """Vibração EFETIVA que a aba Rumble exibe para o alvo ``uniq``."""
        override = self.controller_override(uniq)
        cfg = getattr(override, "rumble", None)
        if cfg is None:
            return self.rumble
        campos = cfg.model_fields_set
        if "policy" not in campos:
            return self.rumble
        return self.rumble.model_copy(
            update={"policy": cfg.policy, "custom_mult": cfg.custom_mult}
        )

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
        )
        if speaker.volume is None or igual_ao_global:
            return self.with_controller_fields_cleared(
                uniq, "speaker", {"volume", "muted", "rota", "fonte"}
            )
        return self._with_override_section(
            uniq,
            "speaker",
            ProfileSpeakerConfig(
                volume=int(speaker.volume),
                muted=bool(speaker.muted),
                rota=speaker.rota,
                fonte=speaker.fonte,
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

    def effective_sensores_for(self, uniq: str | None) -> Any:
        """Giroscópio e acelerômetro DESTA peça, ou ``None`` — sem opinião."""
        override = self.controller_override(uniq)
        return getattr(override, "sensores", None)

    def with_controller_sensores(
        self, uniq: str, *,
        giroscopio: bool | None = None,
        acelerometro: bool | None = None,
    ) -> DraftConfig:
        """Novo draft com os sensores de ``uniq`` substituídos."""
        from hefesto_dualsense4unix.profiles.schema import ControllerSensoresOverride

        campos: dict[str, Any] = {}
        if giroscopio is not None:
            campos["giroscopio"] = bool(giroscopio)
        if acelerometro is not None:
            campos["acelerometro"] = bool(acelerometro)
        if not campos:
            return self.with_controller_fields_cleared(
                uniq, "sensores", {"giroscopio", "acelerometro"}
            )
        return self._with_override_section(
            uniq, "sensores", ControllerSensoresOverride(**campos)
        )

    def with_controller_mascara(self, uniq: str, mascara: str | None) -> DraftConfig:
        """Novo draft com a MÁSCARA de ``uniq`` substituída (08/09/2026)."""
        from hefesto_dualsense4unix.profiles.schema import normalizar_gamepad_flavor

        if mascara is None:
            return self._with_override_scalar_cleared(uniq, "mascara")
        valor = normalizar_gamepad_flavor(mascara)
        if valor is None:
            raise ValueError(
                f"máscara desconhecida {mascara!r} — use 'dualsense', 'xbox' "
                "ou 'nintendo', ou None para o controle herdar a do perfil"
            )
        return self._with_override_section(uniq, "mascara", valor)

    def _with_override_scalar_cleared(self, uniq: str, section: str) -> DraftConfig:
        """Apaga uma seção de UM VALOR SÓ do override de ``uniq``."""
        override = self.controller_override(uniq)
        if override is None or getattr(override, section, None) is None:
            return self
        novo_override = override.model_copy(update={section: None})
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

    def with_override_fields_cleared(
        self, section: str, fields: Iterable[str]
    ) -> DraftConfig:
        """Limpa ``fields`` da seção ``section`` de TODOS os overrides do mapa."""
        mapa = self.source_controllers
        if not isinstance(mapa, dict) or not mapa:
            return self
        alvo_campos = set(fields)
        novo: dict[str, Any] = {}
        mudou = False
        for uniq, entry in mapa.items():
            override = self.controller_override(str(uniq))
            if override is None:
                novo[uniq] = entry
                continue
            cfg = getattr(override, section, None)
            if cfg is None or not (cfg.model_fields_set & alvo_campos):
                novo[uniq] = entry
                continue
            mudou = True
            restantes = cfg.model_fields_set - alvo_campos
            nova_secao = (
                type(cfg)(**{nome: getattr(cfg, nome) for nome in restantes})
                if restantes
                else None
            )
            novo_override = override.model_copy(update={section: nova_secao})
            if _override_vazio(novo_override):
                continue
            novo[uniq] = novo_override
        if not mudou:
            return self
        return self.model_copy(
            update={
                "source_controllers": novo or None,
                "controllers_esvaziados_nesta_edicao": not novo,
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

    def _controllers_to_ipc(self) -> dict[str, Any] | None:
        """Seção ``controllers`` do contrato IPC ``profile.apply_draft``.

        ``{uniq: {leds?, triggers?}}`` com os MESMOS formatos das seções
        globais (rgb lista, brilho float 0.0-1.0, params lista). None quando
        não há mapa — o DraftApplier pula seção None e daemon antigo ignora
        a chave desconhecida (aditivo).

        Fix do review (2026-07-16): emissão POR CAMPO guiada pelo
        ``model_fields_set`` — campo não escrito no override NÃO viaja (o
        DraftApplier trata chave ausente como "sem opinião" e o merge por
        campo do backend herda o global), em paridade com a ativação de
        perfil. Exceção deliberada: cor e brilho formam UM campo no backend
        (o RGB pré-escalado); quando só a COR é escrita, o brilho é resolvido
        do GLOBAL do draft aqui na borda, para o alvo receber a mesma cor
        efetiva que a ativação produziria. O BRILHO SOZINHO viaja só, e o
        ``DraftApplier`` o publica como fator (A-BARRA-NAO-ESCURECE-AO-REAPLICAR-01),
        salvo com o global a 0%, em que a cor do global vai junto.

        Z4/T8 (24/08/2026): mapa vazio tem DUAS origens que o
        ``DraftApplier`` do daemon já trata de formas diferentes (verificado
        empiricamente, sem precisar de cura do lado dele — ver
        ``tests/unit/test_z4_apagar_override.py``) — ``None`` (chave ausente,
        ele pula a seção e não mexe) e ``{}`` (objeto vazio presente, ele
        substitui o mapa de overrides por um vazio e arma a trava manual).
        ``controllers_esvaziados_nesta_edicao`` é o crachá de qual das duas
        é esta: só é ``True`` quando o mapa TINHA algo e um "clear" o
        esvaziou nesta mesma edição (``with_override_fields_cleared`` /
        ``with_controller_fields_cleared``) — nunca em carregamento de perfil
        sem overrides.
        """
        mapa = self.source_controllers
        if not isinstance(mapa, dict) or not mapa:
            return {} if self.controllers_esvaziados_nesta_edicao else None
        out: dict[str, Any] = {}
        for uniq in mapa:
            override = self.controller_override(str(uniq))
            if override is None:
                continue
            entry: dict[str, Any] = {}
            if override.leds is not None:
                campos = override.leds.model_fields_set
                leds_entry: dict[str, Any] = {}
                if "lightbar" in campos or "lightbar_brightness" in campos:
                    brilho = (
                        float(override.leds.lightbar_brightness)
                        if "lightbar_brightness" in campos
                        else self.leds.lightbar_brightness / 100.0
                    )
                    # O BRILHO SOZINHO NÃO VIRA COR — 25/09/2026,
                    # A-BARRA-NAO-ESCURECE-AO-REAPLICAR-01. Aqui ele levava a
                    # cor GLOBAL junto, que é o achado R-20
                    # `brilho-por-controle-materializa-cor-global` vivo no
                    # "Aplicar": medido na mesa de quatro real, o P1 a 60% na
                    # cor do número saía do Aplicar no global do perfil a 60%.
                    # O brilho viaja só, e o `DraftApplier` o publica como
                    # fator, como a ativação. A exceção é a do manager
                    # (`_brilho_materializa_cor`): com o global a 0% não há
                    # cor a escalar de volta, e a cor vai junto.
                    materializa = (
                        "lightbar" not in campos and self.leds.lightbar_brightness <= 0
                    )
                    rgb = (
                        tuple(override.leds.lightbar)
                        if "lightbar" in campos
                        else self.leds.lightbar_rgb if materializa else None
                    )
                    if rgb is not None:
                        leds_entry["lightbar_rgb"] = list(rgb)
                        leds_entry["lightbar_brightness"] = brilho
                        # O NÚMERO PARA O QUAL A COR FOI ESCOLHIDA viaja com
                        # ela: o controle em economia vai na camada do perfil,
                        numero = override.leds.lightbar_para_o_numero
                        if "lightbar" in campos and numero is not None:
                            leds_entry["lightbar_para_o_numero"] = int(numero)
                    elif "lightbar_brightness" in campos:
                        leds_entry["lightbar_brightness"] = brilho
                if "player_leds" in campos:
                    leds_entry["player_leds"] = [
                        bool(b) for b in override.leds.player_leds
                    ]
                if "player_led_brightness" in campos:
                    leds_entry["player_led_brightness"] = str(
                        override.leds.player_led_brightness)
                if leds_entry:
                    entry["leds"] = leds_entry
            if override.triggers is not None:
                lados = override.triggers.model_fields_set
                trig_entry: dict[str, Any] = {}
                if "left" in lados:
                    trig_entry["left"] = {
                        "mode": override.triggers.left.mode,
                        "params": list(override.triggers.left.params),
                    }
                if "right" in lados:
                    trig_entry["right"] = {
                        "mode": override.triggers.right.mode,
                        "params": list(override.triggers.right.params),
                    }
                if trig_entry:
                    entry["triggers"] = trig_entry
            if override.rumble is not None:
                campos_r = override.rumble.model_fields_set
                if "policy" in campos_r and override.rumble.policy is not None:
                    rumble_entry: dict[str, Any] = {"policy": override.rumble.policy}
                    if override.rumble.custom_mult is not None:
                        rumble_entry["custom_mult"] = float(
                            override.rumble.custom_mult
                        )
                    entry["rumble"] = rumble_entry
            if override.speaker is not None:
                speaker_entry: dict[str, Any] = {
                    "volume": int(override.speaker.volume),
                    "muted": bool(override.speaker.muted),
                }
                rota_ovr = getattr(override.speaker, "rota", None)
                if rota_ovr is not None:
                    speaker_entry["rota"] = int(rota_ovr)
                entry["speaker"] = speaker_entry
            if entry:
                out[str(uniq)] = entry
        return out or None

    def to_ipc_dict(self) -> dict:  # type: ignore[type-arg]
        """Serializa draft para o formato do contrato IPC ``profile.apply_draft``.

        Retorna dicionario com secoes triggers/leds/rumble/mouse/keyboard/
        controllers (esta última só quando o perfil em edição tem overrides
        por-controle — PERFIL-04; ver ``_controllers_to_ipc``).
        Campos reservados (mic_led, emulation) sao omitidos para não causar
        erros em versões de daemon sem suporte. A política de rumble
        (policy/custom_mult) também não entra aqui: ela já é aplicada na hora
        pelo IPC vivo (rumble.policy_set/policy_custom) ao mexer na aba e
        persiste via ``to_profile`` (FEAT-RUMBLE-POLICY-PROFILE-01).

        PERFIL-SALVA-TUDO-01: ``mode`` e ``suppress_desktop_emulation`` seguem a
        MESMA regra da política de rumble e NÃO viajam no "Aplicar". As abas
        Emulação/Início já os aplicam ao vivo pelos handlers próprios
        (``daemon.emulation.suppress``, ``apply_mode``) e o rascunho só guarda o
        que ficou, para o "Salvar Perfil" persistir. Emiti-los aqui repetiria o
        estrago do HARM-05 numa seção pior: um "Aplicar" disparado por ter mexido
        num gatilho recriaria o vpad (ou suspenderia a emulação) no meio do jogo.

        A seção ``keyboard`` é SEMPRE emitida (mesmo com ``key_bindings`` None) —
        BUG-FOOTER-APPLY-IGNORA-KEYBINDINGS-01: antes ``to_ipc_dict`` omitia os
        key_bindings, então o rodapé "Aplicar" nunca empurrava o teclado editado
        ao device (só ``profile.switch`` fazia). O DraftApplier resolve o inner
        ``key_bindings`` (None → DEFAULT_BUTTON_BINDINGS; dict → override). Daemon
        antigo ignora a seção desconhecida (aditivo, sem quebra de contrato).

        SOM-02/E4: a seção ``speaker`` NÃO viajava aqui, de propósito. Quem
        manda o volume ao vivo é o ``speaker.set`` do IPC, disparado pela
        superfície que a usuária tocou (o controle deslizante da E1) — o
        rascunho só guardava o que ficou, para o "Salvar Perfil" persistir.
        Emiti-la no "Aplicar" repetiria o estrago do HARM-05 numa seção com
        preço: um Aplicar disparado por ter mexido num gatilho tomaria a posse
        dos bytes de volume do controle sem ninguém ter pedido volume nenhum.

        NOTA DATADA — 10/08/2026 (pedido dela: *"cada feature de cada aba ao
        clicarmos em salvar perfil e aplicar (botão verde) tudo fique salvo no
        perfil ativo (...) speaker, mic (...) tudo"*). O parágrafo acima
        CADUCOU como ausência e sobrevive INTEIRO como regra de portão: a seção
        viaja, mas só com ``speaker.dirty`` — a MESMA regra do ``mouse`` e do
        ``mic``, e é ela que impede o Aplicar de outra aba de mexer no som pelas
        costas dela. O medo era de emissão INCONDICIONAL, e com o portão ele não
        se realiza: sem gesto de som nesta sessão não há chave nenhuma no
        payload, e "Soltar" (``without_speaker``) zera o rascunho e cala a seção
        junto.

        O que a nota corrige, medido em 10/08/2026: o botão verde levava o
        volume, o mudo e o canal para o ARQUIVO (``to_profile``) e não os levava
        ao CONTROLE — a única seção do rascunho que ela edita e que o "Aplicar"
        não conhecia. ``volume=None`` nunca viaja, porque seção sem número faz o
        backend cair na preferência ZERO e tomar a posse (SOM-02, armadilha 1);
        e ``rota`` só viaja quando há opinião, porque o byte ``common[7]``
        carrega junto o caminho do MICROFONE — chave ausente é "não escrevo".

        A RÉGUA, que é o contrato com a outra ponta: o ``volume`` daqui é
        **0-255**, a régua do REGISTRADOR — a mesma do ``SpeakerDraft``, a do
        ``ProfileSpeakerConfig`` do esquema e a do IPC ``speaker.set``, que
        recusa com *"'volume' fora de 0-255"*. Não é a porcentagem da tela:
        quem converte é o ``core/speaker_scale.volume_do_percentual``, uma vez
        só, no card (a régua única da SOM-02). Quem ler esta seção do outro lado
        valida 0-255; validar 0-100 recusaria o volume normal dela (180 no
        registrador) e o botão verde reportaria a seção como falha.

        A chave é ADITIVA: seção desconhecida é IGNORADA pelo ``DraftApplier``,
        nunca recusada, então daemon sem suporte não quebra — e sem ela a ponta
        do daemon não teria o que receber.

        A seção ``mouse`` é ``None`` quando não foi tocada nesta sessão
        (``MouseDraft.dirty`` False) — o DraftApplier pula seção None
        (BUG-MOUSE-GUI-SYNC-01 A2: "Aplicar" não desliga emulação viva).

        HARM-05: a seção mouse NÃO leva ``enabled``. O dono do liga/desliga é o
        MODO (aba Início), e o Aplicar é o rodapé de ajustes — se ele emitisse
        ``enabled``, um Aplicar feito durante "Jogar pelo Hefesto" (por ter
        mexido num gatilho) mandaria ``enabled=True`` de uma sessão de desktop
        anterior, o daemon aplicaria a exclusão mútua e o vpad morreria no meio
        da partida. Não é hipótese: ``dirty`` só é ligado pelos SLIDERS
        (``mouse_actions``); o switch confirma pelo IPC e baixa o dirty na hora.
        Logo ``enabled`` aqui nunca foi edição pendente — era sempre eco de
        estado velho, e só podia causar dano. O que sobra (velocidades) cai na
        rota speed-only do applier, que não liga nem desliga nada.
        """
        rgb = self.leds.lightbar_rgb
        speaker_ipc: dict[str, Any] | None = None
        if self.speaker.dirty and self.speaker.volume is not None:
            speaker_ipc = {
                "volume": int(self.speaker.volume),
                "muted": bool(self.speaker.muted),
            }
            if self.speaker.rota is not None:
                speaker_ipc["rota"] = int(self.speaker.rota)
        mic_ipc: dict[str, Any] | None = None
        if self.mic.dirty:
            mic_ipc = {"volume": self.mic.volume}
            if self.mic.button_toggles_system is not None:
                mic_ipc["button_toggles_system"] = self.mic.button_toggles_system
        return {
            "triggers": {
                "left": {
                    "mode": self.triggers.left.mode,
                    "params": list(self.triggers.left.params),
                },
                "right": {
                    "mode": self.triggers.right.mode,
                    "params": list(self.triggers.right.params),
                },
            },
            "leds": {
                "lightbar_rgb": list(rgb) if rgb is not None else None,
                "lightbar_brightness": self.leds.lightbar_brightness / 100.0,
                "player_leds": list(self.leds.player_leds),
                "auto_player_colors": self.leds.auto_player_colors,
                "player_led_brightness": self.leds.player_led_brightness,
            },
            "rumble": {
                "weak": self.rumble.weak,
                "strong": self.rumble.strong,
            },
            "mouse": (
                {
                    "speed": self.mouse.speed,
                    "scroll_speed": self.mouse.scroll_speed,
                }
                if self.mouse.dirty
                else None
            ),
            "mic": mic_ipc,
            "speaker": speaker_ipc,
            "keyboard": {
                "key_bindings": (
                    {b: list(tokens) for b, tokens in self.key_bindings.items()}
                    if self.key_bindings is not None
                    else None
                ),
            },
            # quando não há mapa (seção pulada; daemon antigo ignora).
            "controllers": self._controllers_to_ipc(),
        }

    # NO FIM DA CLASSE DE PROPÓSITO: este arquivo é citado por número de linha
    # nas planilhas de `docs/data/`, e um método no meio dele deslocaria as
    # âncoras de baixo.
    def with_controller_movimento(
        self, uniq: str, *,
        ligada: bool | None = None,
        sensibilidade: int | None = None,
        zona_morta_graus_s: float | None = None,
    ) -> DraftConfig:
        """Novo draft com a MIRA POR MOVIMENTO de ``uniq`` — o chip «Mira Virtual».

        A-MIRA-POR-MOVIMENTO-NA-TELA-01 (24/09/2026). Os três campos são os que
        a tela oferece: o chip (``ligada`` vira o destino ``analogico_direito``
        ou ``nenhum``) e os dois deslizantes da Calibrar. É o mesmo contrato do
        ``mira.set`` do IPC: ``None`` é *sem opinião* e NÃO mexe no que a peça
        já tinha — campo omitido não é campo zerado. Os três ``None`` limpam a
        seção inteira, e a peça volta a seguir a mira do perfil.
        """
        from hefesto_dualsense4unix.core.roteador_de_movimento import (
            DESTINO_ANALOGICO_DIREITO,
            DESTINO_NENHUM,
        )
        from hefesto_dualsense4unix.profiles.schema import ProfileMovimentoConfig

        campos: dict[str, Any] = {}
        if ligada is not None:
            campos["destino"] = DESTINO_ANALOGICO_DIREITO if ligada else DESTINO_NENHUM
        if sensibilidade is not None:
            campos["sensibilidade"] = int(sensibilidade)
        if zona_morta_graus_s is not None:
            campos["zona_morta_graus_s"] = float(zona_morta_graus_s)
        if not campos:
            # A seção inteira sai — `_with_override_scalar_cleared` põe `None`
            # nela e tira a entrada do mapa se ela esvaziar.
            return self._with_override_scalar_cleared(uniq, "movimento")
        atual = getattr(self.controller_override(uniq), "movimento", None)
        if atual is not None:
            escritos = {n: getattr(atual, n) for n in atual.model_fields_set}
            campos = {**escritos, **campos}
        return self._with_override_section(
            uniq, "movimento", ProfileMovimentoConfig(**campos)
        )


def registrar_alto_falante_no_rascunho(
    janela: Any,
    *,
    volume: int | None,
    muted: bool = False,
    rota: int | None = None,
    uniq: str | None = None,
) -> None:
    """Anota no rascunho o alto-falante que ficou DE PÉ. NÃO aplica nada."""
    draft = getattr(janela, "draft", None)
    if not isinstance(draft, DraftConfig):
        return
    if volume is None:
        janela.draft = draft.without_speaker().with_override_fields_cleared(
            "speaker", {"volume", "muted", "rota"}
        )
        return
    estado_alvo = alvo_de_edicao(janela)
    if estado_alvo.desconhecido:
        return
    alvo = estado_alvo.uniq
    if uniq and alvo and str(alvo) == str(uniq):
        atual = draft.effective_speaker_for(uniq)
        update: dict[str, Any] = {
            "volume": max(0, min(255, int(volume))),
            "muted": bool(muted),
        }
        if rota is not None:
            update["rota"] = int(rota)
        janela.draft = draft.with_controller_speaker(
            uniq, atual.model_copy(update=update)
        )
        return
    janela.draft = draft.with_speaker(volume, muted=muted, rota=rota)


def registrar_microfone_no_rascunho(
    janela: Any,
    *,
    volume: int | None = None,
    muted: bool | None = None,
    soltar_mudo: bool = False,
) -> None:
    """Anota no rascunho o MICROFONE que ficou DE PÉ. NÃO aplica nada."""
    draft = getattr(janela, "draft", None)
    if not isinstance(draft, DraftConfig):
        return
    if volume is None:
        return
    janela.draft = draft.with_mic(
        volume=volume, muted=muted, soltar_mudo=soltar_mudo
    )


def _com_a_procedencia_da_mesma_cor(antes: Any, novos: Any) -> Any:
    """``novos`` com o número para o qual a MESMA cor de ``antes`` foi escolhida."""
    campo = "lightbar_para_o_numero"
    if antes is None or not {"lightbar", campo} <= antes.model_fields_set:
        return novos
    if ("lightbar" not in novos.model_fields_set or campo in novos.model_fields_set
            or tuple(novos.lightbar) != tuple(antes.lightbar)):
        return novos
    return novos.model_copy(update={campo: getattr(antes, campo)})


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
    "registrar_alto_falante_no_rascunho",
    "registrar_microfone_no_rascunho",
]
