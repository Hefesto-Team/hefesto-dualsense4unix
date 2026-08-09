"""Schema de perfil v1 com pydantic.

Ver `docs/adr/005-profile-schema-v1.md` para a justificativa semântica
(AND entre campos, OR dentro de listas, `MatchAny` sentinel V2-8).
"""
from __future__ import annotations

import os
import re
from typing import Any, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    SerializerFunctionWrapHandler,
    field_validator,
    model_serializer,
    model_validator,
)

from hefesto_dualsense4unix.profiles.steam_app import steam_appid_from_wm_class

#: Teto do multiplicador de rumble da política "custom". Acima de 1.0 AMPLIFICA o
#: que o jogo pediu — é a razão de existir da faixa (BUG-RUMBLE-CUSTOM-MULT-CAP-01).
#:
#: HARM-19: mora aqui, num dono só, porque a faixa já valeu 2.0 no esquema, 1.0 no
#: handler `rumble.policy_custom` e 200% no slider da GUI ao mesmo tempo — de 101%
#: em diante a usuária levava um erro de validação que a aba reportava como
#: "daemon offline?". Quem mudar o teto muda AQUI e os três seguem juntos.
RUMBLE_CUSTOM_MULT_MAX = 2.0


def _casa_sem_caixa(valor: object, aceitos: list[str]) -> bool:
    """Pertence-à-lista SEM diferenciar maiúsculas de minúsculas.

    R-12 (auditoria 23/07), a metade que faltava. O editor simples aplicava um
    ``.lower()`` no que a usuária digitava, e o matcher comparava com o dado
    CRU do sistema — ``Cyberpunk2077.exe`` (basename de ``/proc/PID/exe``)
    nunca casava com o ``cyberpunk2077.exe`` gravado. O agente do R-12 tirou o
    ``.lower()`` (parar de corromper o dado guardado é o dano garantido); a
    cura completa é esta: **guardar como veio, comparar sem caixa**.

    Vale para os dois lados porque nenhum dos dois é confiável:

    - ``wm_class`` chega do X/XWayland com a caixa que o toolkit escolheu
      (``Steam`` vs. ``steam``, ``Firefox`` vs. ``firefox``), e a mesma janela
      muda de grafia entre backends de detecção;
    - o basename do executável é o que o jogo enviou (``Sackboy.exe``), e
      ninguém digita isso à mão com a caixa certa.

    Alvo vazio nunca casa: janela sem ``wm_class``/sem ``exe_basename`` é
    ausência de evidência, não igualdade com uma entrada vazia do perfil.
    """
    alvo = str(valor or "").casefold()
    if not alvo:
        return False
    return any(alvo == item.casefold() for item in aceitos)


class MatchCriteria(BaseModel):
    """Casamento por critérios específicos (V2-8, V2-10).

    - AND entre campos preenchidos.
    - OR dentro de cada lista.
    - Campos None/[] são ignorados na avaliação.
    - `window_title_regex` usa `re.search` (V2-10); padrões com `.*`
      continuam válidos mas redundantes.
    - `process_name` casa com basename de `/proc/PID/exe` (V2-9).
    - A comparação IGNORA maiúsculas/minúsculas nos três campos (R-12).
    """

    model_config = ConfigDict(extra="forbid")

    type: Literal["criteria"] = "criteria"
    window_class: list[str] = Field(default_factory=list)
    window_title_regex: str | None = None
    process_name: list[str] = Field(default_factory=list)

    def matches(self, window_info: dict[str, Any]) -> bool:
        conditions: list[bool] = []
        if self.window_class:
            conditions.append(
                _casa_sem_caixa(window_info.get("wm_class"), self.window_class)
            )
        if self.window_title_regex:
            pattern = self.window_title_regex
            title = window_info.get("wm_name", "") or ""
            # R-12: `re.IGNORECASE` pela MESMA razão das listas — título de
            # janela é texto de marketing ("Sackboy: A Big Adventure",
            # "SACKBOY"), e um regex que só casa com a grafia exata é uma
            # armadilha silenciosa (o perfil simplesmente nunca ativa, sem erro
            # nenhum). Deixar só as listas tolerantes seria pior que os dois
            # extremos: a mesma tela do editor teria dois campos com regras de
            # caixa diferentes. Quem PRECISA de caixa exata continua tendo
            # saída, com o grupo local `(?-i:...)` do próprio `re`.
            conditions.append(bool(re.search(pattern, title, re.IGNORECASE)))
        if self.process_name:
            conditions.append(
                _casa_sem_caixa(window_info.get("exe_basename"), self.process_name)
            )
        if not conditions:
            return False
        return all(conditions)


class MatchAny(BaseModel):
    """Sentinel explícito para o perfil fallback (V2-8)."""

    model_config = ConfigDict(extra="forbid")

    type: Literal["any"] = "any"

    def matches(self, window_info: dict[str, Any]) -> bool:
        return True


class MatchManual(BaseModel):
    """Sentinel explícito de perfil SÓ-MANUAL: nunca casa com janela nenhuma.

    R-12 item 3 (débito da auditoria 23/07). Existia um jeito de escrever "este
    perfil só entra quando eu mandar": um ``MatchCriteria`` com os três campos
    vazios, que ``matches()`` reprova por falta de condição. O problema é que
    esse estado é INDISTINGUÍVEL do acidente — foi exatamente assim que o
    preset ``coop_local`` de fábrica saiu inalcançável e ninguém percebeu, e é
    o que a GUI teve de adivinhar para escrever "Só manual (nunca ativa
    sozinho)" na coluna "Quando usar".

    Com o sentinel, intenção e acidente param de ter a mesma forma: quem
    declara ``{"type": "manual"}`` está dizendo isso, e o
    ``check_perfis_inalcancaveis`` do ``doctor.sh`` deixa de reclamar dele (e
    continua reclamando do criteria vazio, que agora é só o acidente).

    Retrocompatível: o tipo é ADITIVO na união discriminada — perfis já
    gravados com ``any``/``criteria`` validam sem migração, e nada no código
    escreve ``manual`` sozinho (só o editor avançado com os três campos
    vazios e o ``profile create --manual``). ATENÇÃO downgrade, mesma nota do
    ``auto_player_colors``: um perfil salvo com este tipo é rejeitado por
    binário antigo, que não conhece o discriminador.
    """

    model_config = ConfigDict(extra="forbid")

    type: Literal["manual"] = "manual"

    def matches(self, window_info: dict[str, Any]) -> bool:
        return False


Match = MatchCriteria | MatchAny | MatchManual


class TriggerConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: str
    params: list[int] | list[list[int]] = Field(default_factory=list)

    @field_validator("mode", mode="after")
    @classmethod
    def _validate_mode(cls, value: str) -> str:
        """Rejeita modos fora do conjunto canônico aceito por `build_from_name`.

        O registro de fábricas (`PRESET_FACTORIES`) é a fonte única de verdade
        dos modos válidos — inclui "Off", "Custom", "MultiPositionFeedback" etc.
        Sem esta checagem, um typo no `mode` (ex.: "Galoping") passa pela
        validação do perfil e só explode com `ValueError` lá no `apply()`, em
        runtime, longe da origem do erro. Import lazy de `core.trigger_effects`
        evita ciclo de import com `profiles.schema`.
        """
        from hefesto_dualsense4unix.core.trigger_effects import PRESET_FACTORIES

        if value not in PRESET_FACTORIES:
            validos = ", ".join(sorted(PRESET_FACTORIES))
            raise ValueError(
                f"modo de trigger desconhecido: {value!r} "
                f"(modos válidos: {validos})"
            )
        return value

    @field_validator("params", mode="after")
    @classmethod
    def _validate_params(
        cls, value: list[int] | list[list[int]]
    ) -> list[int] | list[list[int]]:
        """Aceita dois formatos canônicos, rejeita mistura.

        - Simples: `list[int]` — todos os elementos inteiros.
        - Aninhado: `list[list[int]]` — todos os elementos são sublistas de int.

        Mistura (`[[1, 2], 3]`) é erro semântico: sinaliza JSON corrompido
        ou migração pela metade. Schema rejeita cedo, com mensagem clara.
        """
        if not value:
            return value
        first = value[0]
        if isinstance(first, list):
            for idx, item in enumerate(value):
                if not isinstance(item, list):
                    raise ValueError(
                        "params aninhado exige todos os elementos como list[int]; "
                        f"índice {idx} tem tipo {type(item).__name__}"
                    )
                for jdx, num in enumerate(item):
                    if not isinstance(num, int) or isinstance(num, bool):
                        raise ValueError(
                            f"params aninhado: elemento [{idx}][{jdx}] deve ser int, "
                            f"recebeu {type(num).__name__}"
                        )
        else:
            for idx, item in enumerate(value):
                if not isinstance(item, int) or isinstance(item, bool):
                    raise ValueError(
                        f"params simples: elemento [{idx}] deve ser int, "
                        f"recebeu {type(item).__name__}"
                    )
        return value

    @property
    def is_nested(self) -> bool:
        """True quando `params` está no formato aninhado `list[list[int]]`."""
        return bool(self.params) and isinstance(self.params[0], list)


class TriggersConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    left: TriggerConfig = Field(default_factory=lambda: TriggerConfig(mode="Off"))
    right: TriggerConfig = Field(default_factory=lambda: TriggerConfig(mode="Off"))


class LedsConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    lightbar: tuple[int, int, int] = (0, 0, 0)
    player_leds: list[bool] = Field(default_factory=lambda: [False] * 5)
    lightbar_brightness: float = Field(default=1.0, ge=0.0, le=1.0)
    # COR-03 (sprint cores-e-led-automaticos): cores automáticas por controle
    # — cada DualSense acende a cor do SEU slot (paleta PS5) + o LED do número
    # do controle (D7). Default True = o comportamento pedido pela mantenedora
    # nasce ligado; False = comportamento broadcast histórico intacto (D5).
    # Perfil antigo sem o campo valida com o default (aditivo, sem migração).
    # SÓ tem efeito na seção GLOBAL `profile.leds`: dentro de um override
    # por-controle (`ControllerOverrides.leds`) o campo é aceito pelo schema
    # (reuso do modelo) mas ignorado — o toggle é do perfil, não do controle
    # (`_controllers_to_specs` não o lê, então ele nunca densifica um
    # override parcial). ATENÇÃO downgrade: perfil salvo com este campo fica
    # inválido em binário antigo (`extra="forbid"`) — coberto nas notas de
    # release (COR-08).
    auto_player_colors: bool = True

    @field_validator("lightbar")
    @classmethod
    def _rgb_bytes(cls, value: tuple[int, int, int]) -> tuple[int, int, int]:
        if len(value) != 3:
            raise ValueError("lightbar precisa 3 componentes")
        for idx, b in enumerate(value):
            if not (0 <= b <= 255):
                raise ValueError(f"lightbar[{idx}] fora de byte: {b}")
        return value

    @field_validator("player_leds")
    @classmethod
    def _player_leds_len(cls, value: list[bool]) -> list[bool]:
        if len(value) != 5:
            raise ValueError(f"player_leds precisa 5 flags, recebeu {len(value)}")
        return value


class RumbleConfig(BaseModel):
    """Seção de rumble do perfil.

    FEAT-RUMBLE-POLICY-PROFILE-01: além do ``passthrough`` (v1), o perfil pode
    declarar a POLÍTICA de intensidade de rumble, aplicada na ativação em
    paridade com a seção ``mode``:

    - ``policy=None`` (default) — perfil SEM opinião: ativar não mexe na
      política global do daemon; apenas reverte política que OUTRO perfil
      tenha aplicado (ver ``Daemon.apply_profile_rumble_policy``).
    - ``policy`` preenchida — aplicada via ``rumble_policy_applier`` injetado
      no ``ProfileManager``, respeitando o lock manual de 30s.
    - ``custom_mult`` — multiplicador 0.0-2.0; só faz sentido com
      ``policy="custom"`` (validado abaixo).

    Aditivo/retrocompatível: perfis v1 sem os campos continuam válidos.
    """

    model_config = ConfigDict(extra="forbid")

    passthrough: bool = True
    policy: Literal["economia", "balanceado", "max", "auto", "custom"] | None = None
    custom_mult: float | None = None

    @model_validator(mode="after")
    def _validate_custom_mult(self) -> RumbleConfig:
        """Range de ``custom_mult`` + coerência com ``policy``.

        ``custom_mult`` fora de ``policy="custom"`` é erro semântico (o valor
        seria silenciosamente ignorado pelo daemon) — rejeitamos cedo, na
        borda do schema, com mensagem clara.
        """
        if self.custom_mult is not None:
            if not (0.0 <= self.custom_mult <= RUMBLE_CUSTOM_MULT_MAX):
                raise ValueError(
                    f"custom_mult fora de [0.0, {RUMBLE_CUSTOM_MULT_MAX}]: "
                    f"{self.custom_mult}"
                )
            if self.policy != "custom":
                raise ValueError(
                    "custom_mult só é válido com policy='custom' "
                    f"(policy={self.policy!r})"
                )
        return self


class ProfileMouseConfig(BaseModel):
    """Seção opcional de emulação de mouse por perfil (FEAT-POINT-AND-CLICK-01).

    Aditiva ao schema v1 (sem bump de versão): perfis sem a seção continuam
    válidos e NÃO tocam no estado de emulação ao serem ativados. Ranges de
    `speed`/`scroll_speed` espelham o contrato do daemon
    (`Daemon.set_mouse_emulation`: 1-12 / 1-5).
    """

    model_config = ConfigDict(extra="forbid")

    enabled: bool
    speed: int = Field(default=6, ge=1, le=12)
    scroll_speed: int = Field(default=1, ge=1, le=5)


class ProfileMicConfig(BaseModel):
    """Seção opcional de MICROFONE por perfil (MIC-EXPOSE-01, 25/07).

    Aditiva ao schema v1 (sem bump de versão), mesmo contrato do `mouse`:
    perfil sem a seção não tem opinião e ativá-lo NÃO mexe no comportamento
    do botão de mic.

    `button_toggles_system` espelha `DaemonConfig.mic_button_toggles_system`,
    que até aqui era um campo SECRETO: existia no dataclass do lifecycle,
    gateava o subsystem `mic_hotkey` no boot e não aparecia em lugar nenhum —
    nem na GUI, nem no draft, nem no perfil. Ligado (default do daemon), o
    botão de mic do controle alterna o mute do microfone PADRÃO DO SISTEMA
    (wpctl/pactl) e acende o LED do mic junto. Desligado, o botão não mexe no
    áudio do sistema — é o que se quer num perfil de gravação/live, em que o
    mute é do OBS/da mesa e um toque acidental no controle não pode derrubar
    a captura.

    NÃO confundir com o mudo de microfone do FIRMWARE (`common[9]` do report
    de saída): esse é do kernel e o hefesto deixou de disputá-lo
    (AUDIO-OWNER-01).
    """

    model_config = ConfigDict(extra="forbid")

    button_toggles_system: bool


class ProfileSpeakerConfig(BaseModel):
    """Seção opcional de ALTO-FALANTE por perfil (SOM-02/E4, 29/07).

    Aditiva ao schema v1 (sem bump de versão), mesmo contrato do `mouse` e do
    `mic`: perfil SEM a seção não tem opinião e ativá-lo **não toca no volume
    e não toma a posse** dos bytes de áudio do report de saída. Tomar posse
    por um perfil que não pediu nada é exatamente o hábito que produziu a
    queixa "a config que eu deixo nunca é respeitada".

    POR QUE ``volume`` É OBRIGATÓRIO (e ``muted`` sozinho é recusado aqui).
    Medido na SOM-02 (armadilha 1) com o `set_speaker_volume` real: uma
    chamada sem `volume` e sem preferência guardada faz o `pref` cair para
    `0`, o efetivo ir a `0` e o estado publicado virar
    ``{'volume': 0, 'muted': True}`` — a posse é tomada E o alto-falante
    tranca em zero, sem que o próprio mudo consiga soltá-lo (armadilha 2:
    `muted=False` restaura a preferência, e a preferência é `0`).

    Um perfil que trouxesse só ``muted`` cairia direto nessa armadilha na
    ativação. A recusa é na BORDA do esquema, e não no applier, pela mesma
    razão do ``custom_mult`` do rumble: o arquivo inválido é rejeitado no
    load, com mensagem que explica, em vez de virar um comportamento errado
    silencioso meses depois. Quem quer "mudo" escreve o volume que quer de
    volta ao clicar em Ativar — que é o que o par
    ``{"volume": 180, "muted": true}`` diz.

    ``muted=True`` manda 0 ao firmware e guarda os 180 como preferência; o
    ``muted=False`` posterior devolve os 180 (medido na sprint).

    A ROTA DE SAÍDA (``rota``), pedido DELA em 09/08/2026: *"tanto usar o mic
    do controle quanto usar o canal de saída de som específico do DS"*. É o
    ``OUTPUT_PATH_SEL`` (``audio_control``, bits 4-5) da referência canônica,
    o mesmo número que o ``rota`` do ``speaker.set`` já carrega:

    ==== ==========================================================
    0    estéreo → fone
    1    canal L → fone (mono)
    2    L → fone, R → ALTO-FALANTE (o caso Zelda; "Sons do jogo")
    3    canal R → alto-falante interno ("Todo o som do PC")
    ==== ==========================================================

    ADITIVO e sem bump de versão, como a seção inteira já é: perfil antigo sem
    o campo carrega com ``rota=None``, que significa **não tocar no byte** — o
    ``common[7]`` guarda a rota de saída E o caminho do microfone, e escrever
    o byte inteiro apagaria o caminho do mic sem ninguém notar
    (``_byte_da_rota``, SOM-ROTA-01). Sem opinião continua sendo silêncio.

    A rota não pode vir SOZINHA porque a seção inteira exige ``volume``: quem
    escreve o byte é o mesmo ``set_speaker_volume`` que escreve o volume, e é
    a mesma posse. Na janela isso já é verdade — o seletor de canal do card
    manda ``rota`` e ``volume`` juntos desde a cura de 04/08, justamente
    porque mandar a rota sem volume trancava o alto-falante em zero.

    LIMITE DECLARADO: a rota é a CAMADA 2 (o firmware). O estado "Todo o som
    do PC" da janela também mexe na CAMADA 1 (o *default sink* do PipeWire),
    que é um fato GLOBAL do sistema e não é campo de perfil — restaurá-lo na
    ativação é decisão dela, não efeito colateral de trocar de janela.
    """

    model_config = ConfigDict(extra="forbid")

    volume: int = Field(ge=0, le=255)
    muted: bool = False
    rota: int | None = Field(default=None, ge=0, le=3)

    @model_validator(mode="before")
    @classmethod
    def _volume_e_obrigatorio(cls, data: Any) -> Any:
        """Mensagem que EXPLICA a armadilha 1 em vez do "field required" cru."""
        if isinstance(data, dict) and "volume" not in data:
            raise ValueError(
                "speaker: 'volume' é obrigatório (0-255). Um perfil com "
                "'muted' e sem 'volume' faria a ativação mandar volume ZERO "
                "e tomar a posse do alto-falante — e o próprio mudo não "
                "conseguiria soltá-lo (SOM-02, armadilhas 1 e 2)."
            )
        return data

    @model_serializer(mode="wrap")
    def _rota_sem_opiniao_nao_vai_para_o_disco(
        self, handler: SerializerFunctionWrapHandler
    ) -> Any:
        """Sem opinião de rota, a chave nem aparece no arquivo.

        Não é faxina de estética: ``extra="forbid"`` faz um hefesto ANTIGO
        RECUSAR o perfil inteiro ao ver uma chave que ele não conhece. Gravar
        ``"rota": null`` em todo perfil salvo transformaria "voltar uma versão"
        em "todos os perfis com som quebrados" — e daemon velho com janela nova
        é combinação real nesta casa. Omitindo o campo quando ninguém opinou,
        o perfil dela continua idêntico ao que era, byte a byte, e só quem de
        fato escolheu um canal carrega a chave nova.
        """
        dados = handler(self)
        if isinstance(dados, dict) and dados.get("rota") is None:
            dados.pop("rota", None)
        return dados


class ProfileModeConfig(BaseModel):
    """Seção opcional de MODO do sistema por perfil (FEAT-PROFILE-MODE-01).

    O perfil do JOGO declara como o controle deve se comportar quando ele está
    em foco — as features passam a COEXISTIR porque o contexto decide, sem
    toggles globais brigando entre si:

    - ``kind="native"`` — release total: o jogo usa os gatilhos adaptativos
      NATIVOS da Sony (Sackboy & cia); o hefesto solta o controle.
    - ``kind="gamepad"`` — gamepad virtual com a máscara `gamepad_flavor`
      (prompts PlayStation ou Xbox). Cada controle físico vira um jogador
      (``coop``, ligado por padrão — ver o campo).
    - ``kind="desktop"`` — declaração explícita de app de desktop: desliga
      gamepad/nativo/co-op vindos de perfil (e também os expirados do lock).

    Perfis SEM a seção não têm opinião: liberam apenas o modo que outro PERFIL
    tinha ligado (gesto manual da usuária é respeitado — mesma semântica do
    `suppress_desktop_emulation`). Toggles manuais recentes vencem por
    ``MANUAL_PROFILE_LOCK_SEC`` (30s), como no `mouse`.
    """

    model_config = ConfigDict(extra="forbid")

    kind: Literal["desktop", "gamepad", "native"]
    gamepad_flavor: Literal["dualsense", "xbox"] | None = None
    # LEIGO-01: default True. Ninguém pluga dois controles esperando que os dois
    # movam o MESMO personagem — o default False fazia todo perfil salvo pela GUI
    # carregar `coop: false` e desligar o co-op ao ativar, pelas costas de quem
    # nunca pediu isso. Perfis já gravados são migrados em
    # `loader.migrate_profiles_coop_default`.
    #
    # COOP-SEM-INTERRUPTOR-01 (06/08/2026) — NOTA DATADA: o campo passou a ser
    # ACEITO E IGNORADO. Nenhum perfil liga nem desliga o co-op
    # (`lifecycle._apply_profile_mode` só o LÊ, e loga quando um perfil antigo
    # pede `false`). Ele NÃO sai do modelo de propósito: `model_config` acima é
    # `extra="forbid"`, então tirá-lo faria **todo perfil dela que traz `"coop"`
    # falhar na validação** — inclusive dois presets de fábrica
    # (`assets/profiles_default/coop_local.json` e `sackboy_nativo.json`).
    # Remover o campo seria trocar um interruptor inútil por um perfil que não
    # abre; a lápide é mais barata que a migração.
    coop: bool = True


class ControllerOverrides(BaseModel):
    """Overrides POR CONTROLE dentro do perfil (PERFIL-02, 2026-07-16).

    Subconjunto deliberado das seções do perfil que fazem sentido por
    controle físico: ``leds`` (lightbar + player_leds + brilho) e
    ``triggers``. Campo ``None`` = sem opinião — o controle herda a seção
    GLOBAL do perfil (merge POR CAMPO na aplicação, PERFIL-01: override
    parcial nunca apaga a cor global no replug).

    Fora por decisão (revisão adversarial do sprint perfis-por-controle):
    - ``label`` — identidade visível é outra frente (4P-03);
    - ``mic_led`` — o mic jamais é colateral de troca de perfil
      (AUDIT-FINDING-PROFILE-MIC-LED-RESET-01).
    """

    model_config = ConfigDict(extra="forbid")

    leds: LedsConfig | None = None
    triggers: TriggersConfig | None = None


# Regex para tokens aceitos em `Profile.key_bindings` values (FEAT-KEYBOARD-PERSISTENCE-01).
# - `KEY_*` é validado contra `evdev.ecodes` (via lookup lazy em `_validate_key_bindings`).
# - `__*__` são tokens virtuais reservados para a sub-sprint UI (59.3): o dispatcher
#   delega ao subsystem de OSK em vez de emitir evento de tecla. Aqui aceitamos
#   pelo regex mas não validamos contra ecodes — o schema não conhece a lista fechada.
_KEY_BINDING_TOKEN_RE = re.compile(r"^(KEY_[A-Z0-9_]+|__[A-Z_]+__)$")


#: Faixa de `Profile.priority` que a JANELA oferece — o piso e o teto do
#: `profile_priority_adj` do glade, e a faixa que o verificador semântico usa
#: para dizer "este número NÃO veio do controle de prioridade".
#:
#: UNIFICA-CONSTANTE-01 (decisão dela, 05/08/2026: *"preciso que as constantes
#: apontem pros arquivos reais do import"*). O 200 morava em três lugares —
#: `app/actions/profiles_actions.py`, `profiles/sanidade.py` e o `upper` do
#: glade — e só UM par tinha portão. Mora AQUI, na camada mais baixa, por dois
#: motivos: é de onde `app/draft_config.py` já lê o DEFAULT de `priority`
#: (`Profile.model_fields["priority"].default`), então quem manda na faixa e
#: quem manda no default passam a morar juntos; e este módulo importa só
#: stdlib + pydantic, o que permite `profiles/`, `app/` e o CLI lerem a faixa
#: sem nenhum deles puxar GTK.
#:
#: Quem mudar o teto muda AQUI. O glade tem de acompanhar na mão (XML não
#: importa nada), e há portão que reprova a divergência:
#: `tests/unit/test_teto_da_prioridade_tem_uma_fonte_so.py`.
#:
#: Histórico do número: era 100 até PERFIL-NASCE-CERTO-01 (entrega 2, item 1),
#: e o catch-all do disco dela estava EXATAMENTE em 100 — não existia número
#: escolhível pela janela que fizesse o perfil de um jogo vencer o dela. O
#: conserto de 26/07 exigiu escrever 110 direto no JSON, um valor que a janela
#: não aceitava digitar. Subir o teto não mexe em perfil nenhum já salvo: é só
#: a faixa que a escala oferece.
PRIORIDADE_MINIMA = 0
PRIORIDADE_MAXIMA = 200


class Profile(BaseModel):
    """Perfil v1 (ADR-005)."""

    model_config = ConfigDict(extra="forbid")

    name: str
    version: Literal[1] = 1
    match: Match = Field(discriminator="type")
    priority: int = 0
    triggers: TriggersConfig = Field(default_factory=TriggersConfig)
    leds: LedsConfig = Field(default_factory=LedsConfig)
    rumble: RumbleConfig = Field(default_factory=RumbleConfig)
    # FEAT-KEYBOARD-PERSISTENCE-01: override de bindings por perfil.
    # - None = herda DEFAULT_BUTTON_BINDINGS do core.
    # - {} = desativa todos os bindings do perfil (teclado silencioso).
    # - {"triangle": ["KEY_C"]} = override apenas desse botão; demais seguem default.
    key_bindings: dict[str, list[str]] | None = None
    # FEAT-POINT-AND-CLICK-01: seção opcional de emulação de mouse.
    # - None = ativar o perfil não toca no estado da emulação (comportamento v1).
    # - Preenchida = ativar o perfil liga/desliga a emulação com as velocidades
    #   dadas (via `mouse_applier` injetado no ProfileManager).
    mouse: ProfileMouseConfig | None = None
    # MIC-EXPOSE-01: comportamento do botão de mic por perfil. None = sem
    # opinião (ativar o perfil não mexe no `mic_button_toggles_system`).
    mic: ProfileMicConfig | None = None
    # SOM-02/E4: volume do ALTO-FALANTE por perfil. None = sem opinião — a
    # ativação não escreve áudio nenhum e NÃO toma a posse dos bytes de
    # volume (armadilha 1 da sprint). Preenchida = a ativação manda
    # `{volume, muted}` pelo `speaker_applier` injetado no ProfileManager.
    # A serialização em `save_profile` OMITE a chave quando None, pelo mesmo
    # requisito de compatibilidade do `controllers` (extra="forbid" acima
    # rejeitaria TODO perfil num binário antigo, não só os que usam a seção).
    speaker: ProfileSpeakerConfig | None = None
    # FEAT-PROFILE-MODE-01: modo do sistema por perfil (nativo/gamepad/desktop
    # + co-op). None = sem opinião (libera só modo vindo de outro perfil).
    mode: ProfileModeConfig | None = None
    # FEAT-POINT-AND-CLICK-01: modo-jogo por perfil. True = ativar o perfil
    # suprime a emulação de mouse/teclado no desktop (jogos de GAMEPAD que
    # leem o controle cru); False (default) = ativar o perfil LIBERA a
    # supressão apenas se ela veio de outro perfil (toggle manual da usuária
    # é respeitado — ver `Daemon.apply_profile_suppression`).
    suppress_desktop_emulation: bool = False
    # PERFIL-02 (sprint 2026-07-16-perfis-por-controle): mapa ADITIVO de
    # overrides por controle físico, keyed pelo MAC normalizado (12 hex
    # minúsculos — o mesmo `norm_mac` do backend; PROVADO ao vivo estável
    # entre USB e BT no DualSense). None = perfil v1 puro, sem opinião
    # por-controle. A serialização em `save_profile` OMITE o campo quando
    # None/vazio — requisito de compatibilidade: sem a omissão, todo save
    # gravaria `"controllers": null` e binário antigo (extra="forbid")
    # rejeitaria TODO perfil no downgrade, não só os que usam o mapa.
    controllers: dict[str, ControllerOverrides] | None = None

    @field_validator("name")
    @classmethod
    def _name_nonempty(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("name não pode ser vazio")
        if "/" in value or ".." in value or os.sep in value:
            raise ValueError(f"name contém caractere inválido: {value!r}")
        # Garante que slugify() produz slug válido — rejeita nomes exóticos
        # (só símbolos, só emoji, etc.) que virariam filename vazio.
        from hefesto_dualsense4unix.profiles.slug import slugify
        try:
            slugify(value)
        except ValueError as exc:
            raise ValueError(f"name não produz slug válido: {value!r}") from exc
        return value

    @field_validator("key_bindings")
    @classmethod
    def _validate_key_bindings(
        cls, value: dict[str, list[str]] | None
    ) -> dict[str, list[str]] | None:
        """Rejeita tokens fora do padrão ou KEY_* inexistentes em evdev.ecodes.

        - `None` passa direto (default = herdar).
        - Values são listas de tokens; cada token casa
          `^(KEY_[A-Z0-9_]+|__[A-Z_]+__)$`.
        - Tokens `KEY_*` são verificados contra `evdev.ecodes` via lookup lazy;
          se evdev não estiver disponível no ambiente (fallback CLI sem deps),
          aceita qualquer KEY_* bem-formado (validação completa fica para runtime).
        """
        if value is None:
            return value
        ecodes_ns: Any | None = None
        try:
            from evdev import ecodes as _ec
            ecodes_ns = _ec
        except Exception:
            ecodes_ns = None
        for button, tokens in value.items():
            if not isinstance(tokens, list):
                raise ValueError(
                    f"key_bindings[{button!r}] precisa ser lista, recebeu "
                    f"{type(tokens).__name__}"
                )
            for idx, tok in enumerate(tokens):
                if not isinstance(tok, str):
                    raise ValueError(
                        f"key_bindings[{button!r}][{idx}] precisa ser str, "
                        f"recebeu {type(tok).__name__}"
                    )
                if not _KEY_BINDING_TOKEN_RE.match(tok):
                    raise ValueError(
                        f"key_bindings[{button!r}][{idx}]={tok!r} não casa "
                        f"padrão 'KEY_*' ou '__TOKEN__'"
                    )
                if (
                    tok.startswith("KEY_")
                    and ecodes_ns is not None
                    and not hasattr(ecodes_ns, tok)
                ):
                    raise ValueError(
                        f"key_bindings[{button!r}][{idx}]={tok!r} não existe "
                        f"em evdev.ecodes"
                    )
        return value

    @field_validator("controllers", mode="after")
    @classmethod
    def _validate_controllers_keys(
        cls, value: dict[str, ControllerOverrides] | None
    ) -> dict[str, ControllerOverrides] | None:
        """Chave do mapa = MAC normalizado (12 hex); rejeita degenerados.

        Usa o MESMO ``norm_mac`` do backend (import lazy, padrão do módulo):
        ``"AA:BB:CC:00:00:02"`` é aceito e canonizado para ``"aabbcc000002"``
        — JSON editado à mão continua casando com a key que o backend
        enumera. Rejeições, com mensagem clara:

        - o que não vira 12 dígitos hex (ex.: key de fallback ``path:...``);
        - uniq DEGENERADO, que não identifica UMA unidade — OUI ``00:00:00``
          (medido ao vivo no Pro Controller, ``000000000001``, idêntico
          entre unidades) e broadcast ``ff:ff:ff:ff:ff:ff``;
        - duas chaves que canonizam para o mesmo MAC (colisão silenciosa:
          um dos overrides venceria por ordem de inserção, sem aviso).
        """
        if value is None:
            return value
        from hefesto_dualsense4unix.core.sysfs_leds import norm_mac

        canonizado: dict[str, ControllerOverrides] = {}
        for key, overrides in value.items():
            mac = norm_mac(key)
            if mac is None or len(mac) != 12:
                raise ValueError(
                    f"controllers: chave {key!r} não é um MAC de 12 dígitos "
                    "hex (ex.: 'aabbcc000002')"
                )
            if mac.startswith("000000") or mac == "ffffffffffff":
                raise ValueError(
                    f"controllers: chave {key!r} é um uniq degenerado — não "
                    "identifica um controle único (visto em receivers 2.4G "
                    "e no Pro Controller)"
                )
            if mac in canonizado:
                raise ValueError(
                    "controllers: chaves duplicadas após normalização "
                    f"({mac!r}) — remova uma das grafias"
                )
            canonizado[mac] = overrides
        return canonizado

    def matches(self, window_info: dict[str, Any]) -> bool:
        return self.match.matches(window_info)

    @property
    def e_catch_all(self) -> bool:
        """True quando o perfil casa com QUALQUER janela.

        R-01 (auditoria 23/07): há duas formas de catch-all, e as duas
        precisam ser tratadas igual na hora de decidir especificidade —
        ``MatchAny`` explícito (``vitoria``, ``fallback``, ``meu_perfil``) e
        um ``MatchCriteria`` com todos os campos vazios (o preset
        ``coop_local`` de fábrica). O segundo na prática nunca casa
        (``MatchCriteria.matches`` devolve ``False`` sem condição alguma),
        mas ele TAMBÉM não é uma regra específica — então some dos dois
        lados da comparação pelo mesmo predicado.

        ``MatchManual`` NÃO entra aqui, e a diferença é de propósito. Este
        predicado responde "o perfil chegou por acidente?" — é o que segura a
        reversão de modo/supressão em `lifecycle._perfil_tem_opiniao`. Um
        catch-all chega quando nenhuma regra casou; um perfil manual só entra
        porque a usuária o escolheu na mão, então ele tem a autoridade que o
        catch-all não tem. Na seleção do autoswitch a distinção é inócua: o
        manual nunca vira candidato (``matches`` é sempre False).
        """
        if isinstance(self.match, MatchAny):
            return True
        if isinstance(self.match, MatchManual):
            return False
        criteria = self.match
        return not (
            criteria.window_class
            or criteria.window_title_regex
            or criteria.process_name
        )


def perfil_e_regra_de_jogo(profile: Profile | None, window_info: dict[str, Any]) -> bool:
    """True quando o perfil é a regra PRÓPRIA do jogo em foco.

    R-01 (auditoria 23/07). Antes, o autoswitch tratava como "perfil do jogo"
    qualquer candidato que aparecesse enquanto uma janela ``steam_app_*``
    estivesse em foco — sem checar se o perfil casou POR CAUSA dela. Com três
    perfis catch-all no disco e nenhum perfil para o Mullet Mad Jack, o
    vencedor era o ``vitoria`` (genérico de desktop): a trava manual das três
    categorias era apagada e o genérico entrava por cima da configuração que a
    usuária tinha acabado de fazer.

    Ser regra de jogo exige as duas coisas:

    1. ``match.type == "criteria"`` com critério de verdade (catch-all não é
       regra de jogo, nem o ``MatchAny`` nem o criteria vazio);
    2. a ``wm_class`` ``steam_app_<id>`` em foco estar listada em
       ``match.window_class``.

    Regex de título **não** conta: o ``fps.json`` da usuária tem ``|Control)``
    e ``|Metro)`` sem âncora — deixá-lo valer como regra de jogo reabriria o
    mesmo buraco por outra porta. (Hoje o ``fps.json`` também preenche
    ``process_name``, e o ``matches`` é AND, então na prática ele não dispara
    em "Painel de Controle"; mas a regra aqui não pode depender disso.)

    A checagem é por ESTRUTURA, não pelo rótulo ``match.type``: um
    ``MatchCriteria`` com ``window_class`` preenchido já é, por definição, não
    catch-all. Isso também mantém o predicado tolerante a dublês de teste
    (``getattr`` defensivo), no mesmo idioma de
    ``lifecycle._profile_rule_matches_game``.
    """
    match = getattr(profile, "match", None)
    if not isinstance(match, MatchCriteria) or not match.window_class:
        return False
    wm_class = str(window_info.get("wm_class") or "")
    # UNIFICA-PREDICADO-01 (05/08/2026): era `wm_class.startswith("steam_app_")`
    # — SENSÍVEL a caixa, uma linha acima de uma comparação INSENSÍVEL. A
    # incoerência estava denunciada no próprio comentário abaixo e mesmo assim
    # valia: com a janela se anunciando `STEAM_APP_2111190` (a `wm_class` chega
    # com a grafia do toolkit e muda entre backends, ver `_casa_sem_caixa`), o
    # perfil do jogo casava pelo matcher e saía daqui como "não é regra de
    # jogo". Agora as duas linhas usam a MESMA noção de caixa. Portão:
    # `tests/unit/test_match_sem_caixa_e_sentinel_manual.py::
    # TestComparacaoSemCaixa::test_regra_de_jogo_com_a_janela_em_caixa_alta`.
    if steam_appid_from_wm_class(wm_class) is None:
        return False
    # Mesma comparação de `MatchCriteria.matches` (R-12): sem ela, um
    # `steam_app_` digitado com maiúscula faria o perfil CASAR pelo matcher e
    # não ser reconhecido como regra do jogo aqui — a divergência entre os dois
    # predicados é justamente o buraco que este módulo existe para fechar.
    return _casa_sem_caixa(wm_class, match.window_class)


def normalizar_gamepad_flavor(valor: object) -> Literal["dualsense", "xbox"] | None:
    """Converte uma máscara CRUA na forma fechada que `ProfileModeConfig` aceita.

    MODO-01. A máscara viaja como `str` solto por todo o daemon
    (`DaemonConfig.gamepad_flavor` nasce de um flag em disco) e como `Literal`
    fechado no schema de perfil. Quem constrói um `ProfileModeConfig` a partir do
    estado vivo — o modo jogo padrão do daemon e o editor de perfis da GUI —
    precisa atravessar essa fronteira; um `cast` em cada callsite mentiria para o
    verificador de tipos sobre um valor que vem de arquivo.

    Desconhecido vira `None`, que no applier significa "mantém a máscara atual"
    — o fail-safe certo: um flag corrompido não pode recriar o vpad no meio do
    jogo, que invalida os handles que o jogo já abriu.
    """
    if valor == "dualsense":
        return "dualsense"
    if valor == "xbox":
        return "xbox"
    return None


def perfil_declara_modo_de_jogo(profile: Profile | None) -> bool:
    """True quando o perfil DIZ, no próprio arquivo, que serve para jogar.

    MODO-01/B2 (sprint 25/07). O cadeado de autoswitch prometia uma coisa só —
    *"não trocar de perfil sozinho ao abrir um jogo"* — e congelava muito mais
    do que isso, porque o único jeito de ceder a ele era o
    `perfil_e_regra_de_jogo`, que exige critério por ``window_class`` COM uma
    ``steam_app_<id>`` em foco. Duas vítimas medidas:

    - o preset ``coop_local``, que **tem** ``mode: gamepad`` mas casa por TÍTULO
      de janela (Sackboy, Overcooked, It Takes Two, Cuphead) — ficava congelado;
    - todo jogo fora da Steam (GOG, Heroic, itch, nativo) com perfil próprio,
      pelo mesmo motivo.

    O predicado aqui é o complemento honesto: o perfil **não é catch-all** (não
    chegou por acidente — casou por regra de verdade) e **declara** ``mode.kind``
    em ``{gamepad, native}``. Isso é o perfil dizendo "eu sou de jogo" sem
    depender da Steam ter carimbado a janela.

    Por que é uma função NOVA em vez de afrouxar `perfil_e_regra_de_jogo`: o
    predicado estrito tem um segundo consumidor, o furo da trava manual em
    `AutoSwitcher._activate` (F2/R-01), onde afrouxar reabriria por outra porta
    o buraco que a R-01 fechou — ali um regex de título solto (``|Control)``,
    ``|Metro)`` do ``fps.json``) passaria a apagar a configuração que ela acabou
    de fazer na mão. O cadeado e a trava manual protegem coisas diferentes e
    agora podem ceder por critérios diferentes.

    `getattr` defensivo (mesmo idioma do resto do módulo): dublê de teste sem
    `mode`/`e_catch_all` responde False — na dúvida o cadeado continua segurando,
    que é o comportamento histórico.
    """
    if profile is None:
        return False
    if bool(getattr(profile, "e_catch_all", True)):
        return False
    kind = getattr(getattr(profile, "mode", None), "kind", None)
    return kind in ("gamepad", "native")


__all__ = [
    "PRIORIDADE_MAXIMA",
    "PRIORIDADE_MINIMA",
    "ControllerOverrides",
    "LedsConfig",
    "Match",
    "MatchAny",
    "MatchCriteria",
    "MatchManual",
    "Profile",
    "ProfileMicConfig",
    "ProfileMouseConfig",
    "ProfileSpeakerConfig",
    "RumbleConfig",
    "TriggerConfig",
    "TriggersConfig",
    "normalizar_gamepad_flavor",
    "perfil_declara_modo_de_jogo",
    "perfil_e_regra_de_jogo",
]
