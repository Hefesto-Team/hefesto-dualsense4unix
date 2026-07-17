"""Estado central de configuração da GUI — DraftConfig (FEAT-PROFILE-STATE-01).

``DraftConfig`` é imutável (``frozen=True`` pydantic v2). Toda mudança de
campo deve criar uma nova instância via ``model_copy(update=...)``. O objeto
é mantido em ``HefestoApp.draft`` e compartilhado por todos os *ActionsMixin.

Ciclo de vida:
- Criado em ``HefestoApp.__init__`` via ``DraftConfig.default()``.
- Populado em ``_load_draft_from_active_profile()`` após daemon conectar.
- Cada mixin lê ``self.draft.<secao>`` para popular widgets.
- Cada handler de signal substitui ``self.draft`` por ``model_copy(update=...)``.
- Aplicação atômica via IPC ``profile.apply_draft`` (método ``apply_draft``
  em ``ipc_bridge``) — consumido pela sprint UI-GLOBAL-FOOTER-ACTIONS-01.

Persistência entre sessões NÃO é escopo desta sprint; o draft é in-memory only.
"""
from __future__ import annotations

from collections.abc import Iterable
from typing import TYPE_CHECKING, Any, Literal, cast

from pydantic import BaseModel, ConfigDict, Field

if TYPE_CHECKING:
    from hefesto_dualsense4unix.profiles.schema import Profile


# ---------------------------------------------------------------------------
# Sub-drafts (um por secao de hardware)
# ---------------------------------------------------------------------------


class TriggerDraft(BaseModel):
    """Draft de um único trigger (L2 ou R2)."""

    model_config = ConfigDict(frozen=True)

    mode: str = "Off"
    params: tuple[int, ...] = ()


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
    mic_led: bool = False  # reservado V2
    auto_player_colors: bool = True  # COR-04 (default do schema: ligado)


class RumbleDraft(BaseModel):
    """Draft de rumble.

    ``weak``/``strong``: teste de motores (não persistem no perfil).

    ``policy``/``custom_mult``: política de intensidade persistível no PERFIL
    (FEAT-RUMBLE-POLICY-PROFILE-01). ``policy=None`` = perfil sem opinião
    (ativar não mexe na política global do daemon). A aba Rumble grava aqui
    cada escolha da usuária, para o "Salvar Perfil" do rodapé persistir o que
    ela vê; ``custom_mult`` (0.0-2.0) só acompanha ``policy="custom"``.

    ``passthrough``: preserva o campo v1 do perfil no round-trip
    (não editável pela GUI nesta sprint).
    """

    model_config = ConfigDict(frozen=True)

    weak: int = Field(default=0, ge=0, le=255)
    strong: int = Field(default=0, ge=0, le=255)
    policy: Literal["economia", "balanceado", "max", "auto", "custom"] | None = None
    custom_mult: float | None = Field(default=None, ge=0.0, le=2.0)
    passthrough: bool = True


class MouseDraft(BaseModel):
    """Draft da emulacao de mouse.

    ``dirty``: True enquanto houver edição de mouse POR APLICAR (a usuária
    mexeu no toggle ou nos sliders nesta sessão). ``to_ipc_dict`` só emite a
    seção mouse quando dirty — BUG-MOUSE-GUI-SYNC-01 (A2): o "Aplicar" com
    seção intocada NÃO pode desligar (nem persistir off) uma emulação ligada
    por CLI/applet. Sincronizações programáticas (bootstrap, refresh da aba)
    NÃO marcam dirty, e o rodapé o baixa depois de aplicar com sucesso
    (HARM-05: sem isso ele nunca baixava e todo "Aplicar" seguinte religava o
    mouse, matando o vpad no meio do jogo).

    ``in_profile``: True quando a seção ``mouse`` FAZ PARTE da configuração —
    o perfil de origem já a tinha, ou a usuária a editou e aplicou. Separa
    "a seção existe" de "há edição pendente" (``dirty``)
    (BUG-MOUSE-SAVE-DROPS-SECTION-01): sem essa distinção, salvar um perfil
    point-and-click sem mexer na aba Mouse descartava a seção e matava a
    feature. ``to_profile`` persiste a seção quando ``dirty`` OU
    ``in_profile``; o overlay do bootstrap e o refresh da aba preservam este
    flag (só atualizam enabled/speed/scroll para exibir o estado vivo).
    """

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


# ---------------------------------------------------------------------------
# Conversores sub-draft <-> schema (compartilhados por from_profile/to_profile
# e pelos overrides por-controle do PERFIL-04)
# ---------------------------------------------------------------------------


def _leds_config_to_draft(leds_cfg: Any) -> LedsDraft:
    """Converte ``LedsConfig`` (schema) no sub-draft de LEDs da GUI.

    Mesma conversão histórica de ``from_profile``: brilho float 0.0-1.0 vira
    percentual inteiro 0-100 e ``player_leds`` é normalizado para 5 flags.
    COR-04: ``auto_player_colors`` é lido junto (perfil antigo sem o campo
    valida com o default True do schema — o getattr é só defesa contra
    objetos parciais de teste). Para OVERRIDES por-controle o valor lido é
    inócuo: o toggle é do perfil e ninguém consulta o campo no efetivo.
    """
    rgb_raw = leds_cfg.lightbar  # tuple[int, int, int]
    brightness_raw = float(leds_cfg.lightbar_brightness)  # 0.0-1.0
    brightness_pct = max(0, min(100, round(brightness_raw * 100)))
    player = tuple(bool(b) for b in leds_cfg.player_leds)
    # Garante 5 elementos (schema valida, mas defensive)
    while len(player) < 5:
        player = (*player, False)
    player_5: tuple[bool, bool, bool, bool, bool] = (
        player[0], player[1], player[2], player[3], player[4]
    )
    return LedsDraft(
        lightbar_rgb=(int(rgb_raw[0]), int(rgb_raw[1]), int(rgb_raw[2])),
        lightbar_brightness=brightness_pct,
        player_leds=player_5,
        auto_player_colors=bool(getattr(leds_cfg, "auto_player_colors", True)),
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

    rgb = leds.lightbar_rgb or (0, 0, 0)
    kwargs: dict[str, Any] = {
        "lightbar": rgb,
        "player_leds": list(leds.player_leds),
        "lightbar_brightness": leds.lightbar_brightness / 100.0,
    }
    if include_auto:
        kwargs["auto_player_colors"] = leds.auto_player_colors
    if only_fields is not None:
        kwargs = {nome: val for nome, val in kwargs.items() if nome in only_fields}
    return LedsConfig(**kwargs)


def _triggers_config_to_draft(cfg: Any) -> TriggersDraft:
    """Converte ``TriggersConfig`` (schema) no sub-draft de gatilhos da GUI.

    Nota: TriggerConfig.params é Union[list[int], list[list[int]]];
    TriggerDraft aceita ambos via tuple, mas mypy precisa cast.
    """
    return TriggersDraft(
        left=TriggerDraft(
            mode=cfg.left.mode,
            params=tuple(cast("list[int]", cfg.left.params)),
        ),
        right=TriggerDraft(
            mode=cfg.right.mode,
            params=tuple(cast("list[int]", cfg.right.params)),
        ),
    )


def _triggers_draft_to_config(triggers: TriggersDraft) -> Any:
    """Converte o sub-draft de gatilhos em ``TriggersConfig`` persistível."""
    from hefesto_dualsense4unix.profiles.schema import TriggerConfig, TriggersConfig

    return TriggersConfig(
        left=TriggerConfig(
            mode=triggers.left.mode,
            params=list(triggers.left.params),
        ),
        right=TriggerConfig(
            mode=triggers.right.mode,
            params=list(triggers.right.params),
        ),
    )


# ---------------------------------------------------------------------------
# DraftConfig raiz
# ---------------------------------------------------------------------------


class DraftConfig(BaseModel):
    """Estado central imutavel da GUI — snapshot de tudo que o daemon pode aplicar.

    Uso correto:
        self.draft = self.draft.model_copy(update={"leds": novo_leds_draft})

    Nunca mute campos diretamente — pydantic v2 frozen bloqueia, mas
    a convencao explicita e mais fácil de rastrear em code review.
    """

    model_config = ConfigDict(frozen=True)

    triggers: TriggersDraft = Field(default_factory=TriggersDraft)
    leds: LedsDraft = Field(default_factory=LedsDraft)
    rumble: RumbleDraft = Field(default_factory=RumbleDraft)
    mouse: MouseDraft = Field(default_factory=MouseDraft)
    emulation: EmulationDraft = Field(default_factory=EmulationDraft)
    # FEAT-KEYBOARD-UI-01: bindings de teclado do perfil em edição.
    # None = herdar DEFAULT_BUTTON_BINDINGS; {} = teclado silencioso; dict
    # parcial = override explícito. Mapeia 1:1 para `Profile.key_bindings`.
    key_bindings: dict[str, list[str]] | None = None

    # BUG-FOOTER-SAVE-DROPS-SECTIONS-01: seções do perfil que o draft NÃO
    # edita (match, mode, suppress_desktop_emulation, priority) transportadas
    # do perfil de origem e reemitidas em ``to_profile`` — sem isso, o
    # "Salvar Perfil" do rodapé zerava o match para "any", apagava a seção
    # mode e resetava a prioridade do perfil ativo. ``Any`` evita importar o
    # schema aqui (os valores são revalidados no ``model_validate`` final).
    source_match: Any | None = None
    source_mode: Any | None = None
    source_suppress: bool = False
    source_priority: int | None = None
    # PERFIL-02 (sprint perfis-por-controle): o mapa ``controllers`` do
    # perfil (overrides por MAC) atravessa o draft — ``to_profile`` reconstrói
    # o Profile do zero e o apagaria no primeiro "Salvar Perfil" (a mesma
    # classe de bug dos dois BUG-*-DROPS-SECTION acima). Mesmo padrão dos
    # ``source_*`` vizinhos: ``Any`` evita importar o schema aqui.
    # PERFIL-04: diferente dos demais ``source_*``, este a GUI EDITA — os
    # handlers de lightbar/gatilhos com um controle selecionado no seletor
    # gravam via ``with_controller_leds``/``with_controller_triggers``
    # (entradas não tocadas seguem passthrough byte-idêntico).
    source_controllers: Any | None = None

    # --- construtores ---

    @classmethod
    def default(cls) -> DraftConfig:
        """Instancia com valores padrão seguros (sem hardware aplicado)."""
        return cls()

    @classmethod
    def from_profile(cls, profile: Profile) -> DraftConfig:
        """Constroi DraftConfig a partir de um Profile persistido.

        Mapeia os campos do schema ``Profile`` para o draft equivalente.
        Campos ausentes no perfil recebem defaults seguros.
        """
        # Triggers e LEDs — conversores compartilhados (mesma semântica
        # histórica; ver _triggers_config_to_draft/_leds_config_to_draft).
        triggers = _triggers_config_to_draft(profile.triggers)
        leds = _leds_config_to_draft(profile.leds)

        # Rumble — weak/strong não persistem no perfil (teste de motores);
        # a POLÍTICA persiste (FEAT-RUMBLE-POLICY-PROFILE-01): policy e
        # custom_mult vêm da seção ``rumble`` (None = perfil sem opinião) e
        # ``passthrough`` é preservado para o round-trip.
        rumble = RumbleDraft(
            policy=profile.rumble.policy,
            custom_mult=profile.rumble.custom_mult,
            passthrough=profile.rumble.passthrough,
        )

        # Mouse — FEAT-POINT-AND-CLICK-01: a seção opcional ``profile.mouse``
        # popula o draft (dirty=False: carga programática não é toque da
        # usuária). Perfil sem a seção mantém os defaults do draft.
        # BUG-MOUSE-SAVE-DROPS-SECTION-01: ``in_profile=True`` marca que o
        # perfil TINHA a seção, para ``to_profile`` preservá-la mesmo sem toque.
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
        # Emulacao (xbox360) — não presente no Profile v1; defaults
        emulation = EmulationDraft()

        return cls(
            triggers=triggers,
            leds=leds,
            rumble=rumble,
            mouse=mouse,
            emulation=emulation,
            key_bindings=profile.key_bindings,
            source_match=profile.match,
            source_mode=profile.mode,
            source_suppress=profile.suppress_desktop_emulation,
            source_priority=profile.priority,
            source_controllers=profile.controllers,
        )

    def to_profile(self, name: str, priority: int = 5) -> Profile:
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

        Retorna instancia validada via ``Profile.model_validate``.
        """
        from hefesto_dualsense4unix.profiles.schema import (
            MatchAny,
            Profile,
            ProfileMouseConfig,
            RumbleConfig,
        )

        mouse_cfg = (
            ProfileMouseConfig(
                enabled=self.mouse.enabled,
                speed=self.mouse.speed,
                scroll_speed=self.mouse.scroll_speed,
            )
            if (self.mouse.dirty or self.mouse.in_profile)
            else None
        )

        profile = Profile(
            name=name,
            priority=(
                self.source_priority if self.source_priority is not None else priority
            ),
            match=self.source_match if self.source_match is not None else MatchAny(),
            mode=self.source_mode,
            suppress_desktop_emulation=self.source_suppress,
            triggers=_triggers_draft_to_config(self.triggers),
            # COR-04: a seção GLOBAL emite auto_player_colors explicitamente
            # (round-trip do toggle "Cores automáticas por controle").
            leds=_leds_draft_to_config(self.leds, include_auto=True),
            rumble=RumbleConfig(
                passthrough=self.rumble.passthrough,
                policy=self.rumble.policy,
                custom_mult=self.rumble.custom_mult,
            ),
            key_bindings=self.key_bindings,
            mouse=mouse_cfg,
            controllers=self.source_controllers,
        )
        # Revalida para garantir round-trip (captura regressoes de schema).
        # Fix do review (2026-07-16): o `model_dump` DENSIFICA as seções
        # PARCIAIS dos overrides por-controle (campos não escritos viram
        # defaults do schema marcados como explícitos) — reintroduziria a
        # resolução-por-objeto refutada um save depois (a ativação pisaria o
        # global do controle). Passamos as INSTÂNCIAS já validadas: pydantic
        # (revalidate_instances="never") as preserva com o `model_fields_set`
        # original — parcial continua parcial.
        payload = profile.model_dump(mode="python")
        payload["controllers"] = profile.controllers
        return Profile.model_validate(payload)

    # --- overrides por-controle (PERFIL-04) ---

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
        """LEDs EFETIVOS que a aba exibe para o alvo ``uniq``.

        Override presente → a seção ``leds`` dele (brilho incluso, LIDO DO
        PERFIL — nunca do backend, senão o valor exibido diverge do salvo);
        sem override (ou alvo "Todos") → a seção global do draft.

        Fix do review (2026-07-16): o merge aqui é POR CAMPO, guiado pelo
        ``model_fields_set`` do pydantic — campo NÃO escrito no JSON do
        override herda o global (paridade com a ativação de perfil). Sem
        isso, um override parcial escrito à mão exibia (e, via semeadura,
        SALVAVA) os defaults do schema no lugar do global. Overrides criados
        pela GUI carregam SÓ os campos que a usuária mudou (COR-04) — este
        mesmo caminho por campo herda o resto do global.
        """
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
        """Gatilhos EFETIVOS que a aba exibe para o alvo ``uniq`` (ver leds).

        Merge POR LADO: um override só de ``left`` exibe o ``right`` global
        (mesma regra de ``effective_leds_for``, fix do review 2026-07-16).
        """
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
        """Novo draft com a seção ``leds`` do override de ``uniq`` substituída.

        PERFIL-04: é por aqui que a edição de lightbar/player-LEDs com um
        controle selecionado no seletor entra no mapa ``controllers`` do
        perfil (e o "Salvar Perfil" do rodapé a persiste). O chamador semeia
        ``leds`` com o efetivo em tela (``effective_leds_for`` + o campo
        editado) — o que a usuária vê é o que salva.

        COR-04: o override guarda SÓ os campos de LED que DIVERGEM do global do
        draft (o efetivo semeado = global + o que a usuária mexeu). Campo igual
        ao global não entra no override — herda o global no merge por campo do
        backend; no caso dos player-LEDs, isso deixa a paleta automática acender
        o LED do NÚMERO do controle em vez de congelá-lo. Sem nenhuma
        divergência, o alvo não precisa de opinião própria: a seção ``leds`` do
        override é limpa (herda tudo do global).
        """
        campos: set[str] = set()
        if leds.lightbar_rgb != self.leds.lightbar_rgb:
            campos.add("lightbar")
        if leds.lightbar_brightness != self.leds.lightbar_brightness:
            campos.add("lightbar_brightness")
        if leds.player_leds != self.leds.player_leds:
            campos.add("player_leds")
        if not campos:
            return self.with_controller_fields_cleared(
                uniq, "leds", {"lightbar", "lightbar_brightness", "player_leds"}
            )
        return self._with_override_section(
            uniq, "leds", _leds_draft_to_config(leds, only_fields=campos)
        )

    def with_controller_triggers(
        self, uniq: str, triggers: TriggersDraft
    ) -> DraftConfig:
        """Novo draft com a seção ``triggers`` do override de ``uniq`` substituída."""
        return self._with_override_section(
            uniq, "triggers", _triggers_draft_to_config(triggers)
        )

    def _with_override_section(
        self, uniq: str, section: str, value: Any
    ) -> DraftConfig:
        """Grava ``value`` na seção ``section`` do override de ``uniq``.

        Nunca muta o dict compartilhado do draft congelado: constrói um mapa
        NOVO (entradas não tocadas seguem os mesmos objetos — passthrough
        byte-idêntico preservado) e devolve o draft substituído.
        """
        from hefesto_dualsense4unix.profiles.schema import ControllerOverrides

        mapa: dict[str, Any] = dict(self.source_controllers or {})
        atual = self.controller_override(uniq) or ControllerOverrides()
        mapa[uniq] = atual.model_copy(update={section: value})
        return self.model_copy(update={"source_controllers": mapa})

    def with_override_fields_cleared(
        self, section: str, fields: Iterable[str]
    ) -> DraftConfig:
        """Limpa ``fields`` da seção ``section`` de TODOS os overrides do mapa.

        Fix do review (2026-07-16, HIGH): espelha no DRAFT a regra que o
        backend já aplica ao vivo (`_record_desired_locked` com broadcast) —
        uma edição em "Todos" vale para todo mundo, então o campo editado sai
        dos overrides por-controle. Sem isso, "mudei todos para azul" ao vivo
        + "Salvar Perfil" persistia o override antigo intacto e a PRÓXIMA
        ativação ressuscitava a cor velha no alvo (o "voltou verde" que o
        sprint doc proíbe, na camada de persistência).

        Granularidade guiada pelo ``model_fields_set``: só os campos pedidos
        saem; o resto do override (ex.: player-LEDs próprios) fica. Seção que
        esvazia vira ``None``; entrada sem nenhuma seção some do mapa; mapa
        vazio volta a ``None`` (nenhuma chave fantasma no JSON salvo).
        """
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
                # Nada da seção/campos editados aqui — passthrough intacto.
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
            if novo_override.leds is None and novo_override.triggers is None:
                continue  # entrada esvaziou — some do mapa
            novo[uniq] = novo_override
        if not mudou:
            return self
        return self.model_copy(update={"source_controllers": novo or None})

    def with_controller_fields_cleared(
        self, uniq: str, section: str, fields: Iterable[str]
    ) -> DraftConfig:
        """Limpa ``fields`` da seção ``section`` do override de UM ``uniq``.

        COR-04 ("Voltar ao automático" com um controle selecionado): remove a
        cor explícita SÓ do alvo — a automática (ou o global, com o auto
        desligado) volta a valer nele no próximo Aplicar. Mesma granularidade
        por campo de ``with_override_fields_cleared``: campos não pedidos
        (ex.: player-LEDs próprios, gatilhos) ficam; seção que esvazia vira
        ``None``; entrada sem nenhuma seção some do mapa; mapa vazio volta a
        ``None``. Sem override (ou sem os campos) devolve ``self`` intacto.
        """
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
        if novo_override.leds is None and novo_override.triggers is None:
            mapa.pop(uniq, None)  # entrada esvaziou — some do mapa
        else:
            mapa[uniq] = novo_override
        return self.model_copy(update={"source_controllers": mapa or None})

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
        (o RGB pré-escalado); quando só um dos dois é escrito, o outro é
        resolvido do GLOBAL do draft aqui na borda, para o alvo receber a
        mesma cor efetiva que a ativação produziria.
        """
        mapa = self.source_controllers
        if not isinstance(mapa, dict) or not mapa:
            return None
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
                    rgb = (
                        tuple(override.leds.lightbar)
                        if "lightbar" in campos
                        else self.leds.lightbar_rgb
                    )
                    brilho = (
                        float(override.leds.lightbar_brightness)
                        if "lightbar_brightness" in campos
                        else self.leds.lightbar_brightness / 100.0
                    )
                    if rgb is not None:
                        leds_entry["lightbar_rgb"] = list(rgb)
                        leds_entry["lightbar_brightness"] = brilho
                if "player_leds" in campos:
                    leds_entry["player_leds"] = [
                        bool(b) for b in override.leds.player_leds
                    ]
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

        A seção ``keyboard`` é SEMPRE emitida (mesmo com ``key_bindings`` None) —
        BUG-FOOTER-APPLY-IGNORA-KEYBINDINGS-01: antes ``to_ipc_dict`` omitia os
        key_bindings, então o rodapé "Aplicar" nunca empurrava o teclado editado
        ao device (só ``profile.switch`` fazia). O DraftApplier resolve o inner
        ``key_bindings`` (None → DEFAULT_BUTTON_BINDINGS; dict → override). Daemon
        antigo ignora a seção desconhecida (aditivo, sem quebra de contrato).

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
                # COR-04: o toggle viaja no "Aplicar" — o DraftApplier o
                # propaga ao registro de identidade (mesmo destino da
                # ativação de perfil); daemon antigo ignora a chave (aditivo).
                "auto_player_colors": self.leds.auto_player_colors,
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
            "keyboard": {
                "key_bindings": (
                    {b: list(tokens) for b, tokens in self.key_bindings.items()}
                    if self.key_bindings is not None
                    else None
                ),
            },
            # PERFIL-04: overrides por-controle do mapa em edição — o
            # DraftApplier os aplica via API por-uniq (apply_output_for),
            # DEPOIS das seções globais (o override vence no alvo). None
            # quando não há mapa (seção pulada; daemon antigo ignora).
            "controllers": self._controllers_to_ipc(),
        }


__all__ = [
    "DraftConfig",
    "EmulationDraft",
    "LedsDraft",
    "MouseDraft",
    "RumbleDraft",
    "TriggerDraft",
    "TriggersDraft",
]
