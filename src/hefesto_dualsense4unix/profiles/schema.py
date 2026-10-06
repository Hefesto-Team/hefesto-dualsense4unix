"""Schema de perfil v1 com pydantic."""
from __future__ import annotations

import os
import re
from typing import Any, Literal, NamedTuple

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

MascaraDeGamepad = Literal["dualsense", "xbox", "nintendo"]

#: teto o acompanha. O tooltip do deslizador já prometia *"acima de 100 sai mais
RUMBLE_CUSTOM_MULT_MAX = 2.0


def _casa_sem_caixa(valor: object, aceitos: list[str]) -> bool:
    """Pertence-à-lista SEM diferenciar maiúsculas de minúsculas."""
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
    """Sentinel explícito de perfil SÓ-MANUAL: nunca casa com janela nenhuma."""

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
        """Aceita dois formatos canônicos, rejeita mistura."""
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


#: rigidos e os controles com tudo ativado por default"*  # (noqa-acento: citação literal)
MODO_DE_NASCIMENTO_DO_GATILHO = "Rigid"
PARAMS_DE_NASCIMENTO_DO_GATILHO: list[int] = [5, 200]


def _gatilho_de_nascimento() -> TriggerConfig:
    """O gatilho com que um perfil sem opinião nasce. Um lugar só, dois lados."""
    return TriggerConfig(
        mode=MODO_DE_NASCIMENTO_DO_GATILHO,
        params=list(PARAMS_DE_NASCIMENTO_DO_GATILHO),
    )


class TriggersConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    left: TriggerConfig = Field(default_factory=_gatilho_de_nascimento)
    right: TriggerConfig = Field(default_factory=_gatilho_de_nascimento)


class LedsConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    lightbar: tuple[int, int, int] = (0, 0, 0)
    player_leds: list[bool] = Field(default_factory=lambda: [False] * 5)
    lightbar_brightness: float = Field(default=1.0, ge=0.0, le=1.0)
    # — cada DualSense acende a cor do SEU slot (paleta PS5) + o LED do número
    auto_player_colors: bool = True
    # outro dia fossilizado no arquivo — e dois DualSense acendiam o MESMO
    # `#0000FF`. Sem este campo o resolvedor tinha de ADIVINHAR qual repetição
    lightbar_para_o_numero: int | None = None
    # linha LEDs, nascendo no Fraco"*. Quem enxerga pouco não tinha como
    player_led_brightness: Literal["fraco", "medio", "forte"] = "fraco"  # noqa-acento: chave ASCII

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


def com_o_brilho_das_luzes_de(antes: LedsConfig | None, novos: LedsConfig) -> LedsConfig:
    """`novos` com o brilho das luzes de número que o override `antes` guardava."""
    campo = "player_led_brightness"
    if antes is None or campo not in antes.model_fields_set:
        return novos
    if campo in novos.model_fields_set:
        return novos
    return novos.model_copy(update={campo: antes.player_led_brightness})


class RumbleConfig(BaseModel):
    """Seção de rumble do perfil."""

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


class ProfileMovimentoConfig(BaseModel):
    """A mira por MOVIMENTO por perfil — MOVIMENTO-EM-QUALQUER-MASCARA-01.

    Aditiva ao schema v1 (sem bump de versão), mesmo contrato do `mouse` e do
    `remapeamento`: perfil sem a seção não tem opinião, e ativá-lo NÃO liga
    mira nenhuma.

    POR QUE ELA NÃO NASCE LIGADA, e a NASCE-LIGADO-01 exige a justificativa
    escrita: a tradução é um ARRANJO, não uma feature do aparelho. A regra
    *"nasce ligado"* vale para o que o plástico já faz — o microfone, o giro, a
    vibração. Ligar a tradução sem pedido moveria a câmera de todo jogo que ela
    já joga quando o controle se mexesse na mesa; e no caminho `uhid`, onde a
    IMU nativa já chega ao jogo, ela criaria DOIS giros e a câmera andaria em
    dobro. O arranjo é de quem usa.

    NO PERFIL E POR CONTROLE — A-MIRA-POR-MOVIMENTO-NA-TELA-01 (23/09/2026).
    Esta seção nasceu só global, pelo precedente do `remapeamento`; a palavra
    de produto pôs o chip «Mira Virtual» no cartão de CADA controle, e o override
    entrou em `ControllerOverrides.movimento` com ESTA mesma classe, sem
    migração. A peça sobrepõe o perfil campo a campo — só os campos que o usuário
    escreveu (`roteador_de_movimento.arranjo_da_peca`).
    """

    model_config = ConfigDict(extra="forbid")

    destino: Literal["nenhum", "analogico_direito", "analogico_esquerdo", "mouse"] = (
        "nenhum"
    )
    sensibilidade: int = Field(default=6, ge=1, le=12)
    eixo_horizontal: Literal["yaw", "roll"] = "yaw"
    inverter_horizontal: bool = False
    inverter_vertical: bool = False
    zona_morta_graus_s: float = Field(default=3.0, ge=0.0, le=60.0)
    teto_graus_s: float = Field(default=220.0, gt=0.0, le=2000.0)
    pixels_por_grau: float = Field(default=12.0, gt=0.0, le=200.0)
    gatilho: str | None = None
    #: quem não os alcança. `nenhum` = sem opinião: o touchpad é o do computador
    #: (TOUCHPAD-DO-SISTEMA-01). Vale onde há controle virtual, P1 a P4.
    toque: Literal["nenhum", "cursor", "zonas"] = "nenhum"
    #: A INCLINAÇÃO — o acelerômetro vira analógico (mesma resposta). A tela tem
    #: um chip «Inclinação» embaixo de cada analógico, e ele escolhe qual dos
    #: dois ela move; os dois apagados são o `nenhum`.
    acelerometro: Literal["nenhum", "analogico_esquerdo", "analogico_direito"] = (
        "nenhum"
    )

    @model_serializer(mode="wrap")
    def _o_toque_e_a_inclinacao_sem_opiniao_nao_vao_ao_disco(
        self, handler: SerializerFunctionWrapHandler
    ) -> Any:
        """Os dois campos de 28/09 só vão ao arquivo quando alguém os escreveu."""
        dados = handler(self)
        if isinstance(dados, dict):
            for novo in ("toque", "acelerometro"):
                if novo not in self.model_fields_set:
                    dados.pop(novo, None)
        return dados

    @field_validator("destino", mode="after")
    @classmethod
    def _o_cursor_fora_da_navegacao_e_o_analogico_direito(cls, value: str) -> str:
        """O destino «mouse» é o analógico direito — A-MIRA-NA-NAVEGACAO-02."""
        return "analogico_direito" if value == "mouse" else value

    @model_validator(mode="after")
    def _o_teto_fica_acima_da_zona_morta(self) -> ProfileMovimentoConfig:
        """Teto abaixo da zona morta é arranjo que nunca move nada."""
        if self.teto_graus_s <= self.zona_morta_graus_s:
            raise ValueError(
                f"teto_graus_s ({self.teto_graus_s}) tem de ser maior que "
                f"zona_morta_graus_s ({self.zona_morta_graus_s})"
            )
        return self

    @field_validator("gatilho")
    @classmethod
    def _o_gatilho_e_um_botao_que_o_jogo_conhece(cls, value: str | None) -> str | None:
        """O gatilho sai do vocabulário do JOGO, e o PS não entra."""
        if value is None:
            return None
        from hefesto_dualsense4unix.core.remapeamento_de_botao import REMAPEAVEIS

        if value not in REMAPEAVEIS:
            raise ValueError(
                f"gatilho desconhecido: {value!r} "
                f"(conhecidos: {', '.join(sorted(REMAPEAVEIS))})"
            )
        return value


class ProfileMouseConfig(BaseModel):
    """Seção opcional de emulação de mouse por perfil (FEAT-POINT-AND-CLICK-01)."""

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
    nem na GUI, nem no draft, nem no perfil.

    MIC-DA-MESA-ELEICAO-01 (01/09/2026) — O QUE ESTE CAMPO LIGA MUDOU. Ligado
    (default do daemon), apertar o botão do microfone ELEGE o canal de captura
    daquele controle como microfone padrão do sistema, e acende o LED dele
    quando a eleição é conferida. Ele não muta mais nada: o texto anterior
    dizia *"alterna o mute do microfone padrão do sistema"*, e essa é
    exatamente a coisa que o usuário mandou parar de fazer — *"mexendo com ambos os
    canais de áudio é péssimo"*.

    Desligado, o botão não mexe no áudio do sistema — é o que se quer num
    perfil de gravação/live, em que o mute é do OBS/da mesa e um toque
    acidental no controle não pode trocar a captura.

    NÃO confundir com o mudo de microfone do FIRMWARE (`common[9]` do report
    de saída): esse é do kernel e o hefesto deixou de disputá-lo
    (AUDIO-OWNER-01).

    O VOLUME E O MUDO (MIC-VOLUME-01, 16/08/2026)
    ----------------------------------------------
    Pedido, olhando a aba Status: *"dá espaço a um slider de microfone pra
    definir o volume do microfone real (independente de saber se tá via bt ou
    via cabo), o app deve ser inteligente pra saber qual caminho usar"* — e,
    sobre gravar: *"ao clicarmos em salvar perfil ou aplicar no perfil ativo ele
    de fato o faz e na próxima sessão lembra disso"*.

    Até aqui esta seção guardava UM booleano, enquanto a do alto-falante
    (`ProfileSpeakerConfig`) já guardava `volume`, `muted` e `rota`. A
    assimetria aparecia na tela: o alto-falante tinha controle deslizante e
    lembrança, o microfone tinha só um botão.

    **Os dois campos são opcionais, e `None` é "sem opinião".** É o mesmo
    contrato do `mouse` e do `speaker`, e ele importa aqui pelo motivo de
    sempre: um perfil que não pediu nada não pode impor nada. A queixa que
    originou essa regra — *"a config que eu deixo nunca é respeitada"* — vale
    nos dois sentidos.

    **ATIVAR UM PERFIL APLICA O MICROFONE (18/08/2026).** Esta docstring dizia
    que a seção era só lembrança, e que ativar o perfil não tocava no
    microfone. Isso caducou por decisão de produto: microfone, som, touchpad, acelerômetro e
    giroscópio se salvam sempre no perfil, e o contrato antigo era de quando o perfil não tinha
    microfone. Quem aplica é `ProfileManager.apply_mic`.

    **O MUDO NÃO É DO PERFIL — O-MUDO-E-DO-CONTROLE-01.** Os dois campos NÃO
    custam a mesma coisa, e por isso não atravessam pelos mesmos caminhos:

    - `volume` aplica em TODA ativação (respeitada a trava manual de áudio):
      ele é o ganho da fonte no PipeWire e não apaga luz nenhuma;
    - `muted` não aplica em ativação NENHUMA — nem na troca automática, nem na
      explícita, nem no boot. O mudo é do CONTROLE e mora no `maquina.json`
      (`controles[k].microfone_mudo`, `utils/maquina.py`); a migração
      `loader.o_mudo_do_microfone_vai_para_o_controle` o tira de todo perfil,
      e `ProfileManager.apply_mic` ignora o que um arquivo ainda carregue. O
      campo fica no esquema para esse arquivo carregar, e só.

    Nota datada: a exceção MIC-GRAVACAO-01 (o `muted` atravessava só a troca
    explícita de perfil) foi revogada em 29/09/2026 pela
    O-BOTAO-DO-MIC-SO-OBEDECE-A-MAO-01, na metade O-MUDO-E-DO-CONTROLE-01.

    **`volume` é do CAMINHO, e desde 09/09/2026 também do aparelho.** Ele é o
    volume da fonte de captura no sistema (o source do PipeWire), e por isso
    funciona igual no cabo e no rádio — que é exatamente o "independente de
    saber se tá via bt ou via cabo" do pedido. O segundo degrau é o
    `common[6]` do controle, o ganho de captura do firmware, pela régua única
    `core/backend_pydualsense.byte_do_volume_do_microfone` (MIC-VOLUME-02,
    D-0909-O-VOLUME-DO-MIC-LIGA-O-BYTE-DO-APARELHO). Fato errado substituído
    em 29/09/2026: este bloco dizia que o DualSense não expõe registrador de
    ganho de microfone. O MUDO do firmware é do controle (ver o bloco acima).

    A faixa é 0-100 (por cento), diferente do `volume` do alto-falante, que é
    0-255 porque escreve um byte do report. Aqui o número é de sistema, e usar a
    escala do report seria pedir que ela pensasse em bytes.
    """

    model_config = ConfigDict(extra="forbid")

    button_toggles_system: bool
    volume: int | None = Field(default=None, ge=0, le=100)
    muted: bool | None = None
    #: controle — o `Headset Capture Volume` do DualSense. São eixos diferentes
    gain: int | None = Field(default=None, ge=0, le=100)


class ProfileSpeakerConfig(BaseModel):
    """Seção opcional de ALTO-FALANTE por perfil (SOM-02/E4, 29/07).

    Aditiva ao schema v1 (sem bump de versão), mesmo contrato do `mouse` e do
    `mic`: perfil SEM a seção não tem opinião e ativá-lo **não toca no volume
    e não toma a posse** dos bytes de áudio do report de saída. (A frase vale
    para a AUSÊNCIA da seção nos três. Perfil COM seção aplica — inclusive o
    `mic`, desde 18/08/2026.) Tomar posse
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

    A ROTA DE SAÍDA (``rota``), pedido em 09/08/2026: *"tanto usar o mic
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
    o campo carrega com ``rota=None``, que significa **o perfil não opina** — o
    ``common[7]`` guarda a rota de saída E o caminho do microfone, e escrever
    o byte inteiro apagaria o caminho do mic sem ninguém notar
    (``_byte_da_rota``, SOM-ROTA-01).

    **"SEM OPINIÃO CONTINUA SENDO SILÊNCIO" CAIU EM 16/09/2026 — SOM-ROTA-02.**
    Esta linha dizia isso, e a premissa era que não escrever fosse o lado
    neutro. Não é: o default do FIRMWARE é ``SAIDA_ESTEREO_NO_FONE``, e o
    conector está vazio. Medido com ela do lado do controle — sem rota, nada;
    com a rota escrita, *"Saiu som"*.

    O que mudou não é este campo, é quem responde quando ele cala: o controle
    passou a NASCER em ``ROTA_PADRAO_DO_SOM`` («Sons do jogo») na adoção — um
    ponto de partida até alguém mudar, palavra de produto no mesmo dia. Perfil sem
    rota herda esse nascimento em vez de herdar o fone vazio; perfil COM rota
    continua mandando, e é ele quem escreve por último.

    **FATO ERRADO, SUBSTITUÍDO — 17/09/2026.** Esta passagem dizia que a rota
    nascia *"do mesmo jeito que já nascia com vibração balanceada e gatilho
    rígido"*. Medido: nenhum dos dois nasce assim. A vibração nasce
    ``policy=None`` — perfil SEM opinião, o default de ``RumbleConfig`` — e os
    gatilhos nascem ``TriggerConfig(mode="Off")``, os dois em
    ``TriggersConfig``. A rota do som é, até aqui, o ÚNICO campo com
    nascimento preparado.

    Que os outros dois passem a ter é decisão, de 16/09/2026: o botão de
    balanceado pré-setado em todo perfil sem configuração alterada, os
    gatilhos nascendo rígidos e os controles com tudo ativado por padrão.
    Isso é trabalho a fazer, não o estado de hoje — e escrever aqui que já
    era verdade custou a esta casa uma sessão de diagnóstico do lado errado.

    A rota não pode vir SOZINHA porque a seção inteira exige ``volume``: quem
    escreve o byte é o mesmo ``set_speaker_volume`` que escreve o volume, e é
    a mesma posse. Na janela isso já é verdade — o seletor de canal do card
    manda ``rota`` e ``volume`` juntos desde a cura de 04/08, justamente
    porque mandar a rota sem volume trancava o alto-falante em zero.

    LIMITE DECLARADO: a rota é a CAMADA 2 (o firmware). O estado "Todo o som
    do PC" da janela também mexe na CAMADA 1 (o *default sink* do PipeWire),
    que é um fato GLOBAL do sistema e não é campo de perfil — restaurá-lo na
    ativação é decisão de produto, não efeito colateral de trocar de janela.
    """

    model_config = ConfigDict(extra="forbid")

    volume: int = Field(ge=0, le=255)
    muted: bool = False
    rota: int | None = Field(default=None, ge=0, le=3)
    #: A FONTE do nó de som deste controle — ``"mix"`` (todo o som do PC cai
    #: aqui também, o *«HDMI completo»* dela) ou ``"sfx"`` (o nó fica livre para
    #: a corrente que o jogo mandar). Pedido, 08/09/2026: *"os somns seja
    #: hdmi completo seja o canal do sfx caindo pra cada controle"*.
    #: <!-- noqa-acento: citação literal -->
    #:
    #: **ADITIVO e sem bump de versão**, como a ``rota``: perfil antigo carrega
    #: com ``None``, que é **não mexer** — o nó daquele controle segue o padrão
    #: da casa, que é ``sfx`` por decisão de produto
    fonte: Literal["mix", "sfx"] | None = None
    #: O BOTÃO «PADRÃO» DO VOLUME (04/10/2026, desenho aprovado em `docs/process/estudos/
    #: 2026-10-04-o-jogo-decide/`): ligado, o volume do alto-falante deste controle é o do JOGO
    #: (100% do registrador, sem ajuste do Hefesto) e a barra fica travada; o ``volume`` guardado
    #: espera e volta quando ela desliga o botão. ``None`` e ``False`` não mudam o que o perfil
    #: já fazia: quem tinha um volume escolhido segue com ele. O perfil SEM a seção também é Padrão
    #: (não opina; a adoção põe o controle em 100%), e é assim que o perfil novo nasce.
    volume_padrao: bool | None = None

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
        o perfil do usuário continua idêntico ao que era, byte a byte, e só quem de
        fato escolheu um canal carrega a chave nova.
        """
        dados = handler(self)
        if not isinstance(dados, dict):
            return dados
        for sem_opiniao in ("rota", "fonte", "volume_padrao"):
            if dados.get(sem_opiniao) is None:
                dados.pop(sem_opiniao, None)
        return dados


class ProfileModeConfig(BaseModel):
    """Seção opcional de MODO do sistema por perfil (FEAT-PROFILE-MODE-01)."""

    model_config = ConfigDict(extra="forbid")

    kind: Literal["desktop", "gamepad", "native"]
    gamepad_flavor: MascaraDeGamepad | None = None
    #: próprio do DualSense, o vpad `uhid`) ou ``"xbox"`` (o canal comum, o vpad
    caminho: Literal["dualsense", "xbox"] | None = None

    @model_serializer(mode="wrap")
    def _sem_caminho_a_chave_nem_aparece(
        self, handler: SerializerFunctionWrapHandler
    ) -> Any:
        """Perfil sem caminho escolhido sai do dump IDÊNTICO ao que era."""
        dados = handler(self)
        if isinstance(dados, dict) and dados.get("caminho") is None:
            dados.pop("caminho", None)
        return dados


CONFIRMADA_POR_GESTO: Literal["gesto"] = "gesto"
CONFIRMADA_POR_SILENCIO: Literal["silencio"] = "silencio"
CONFIRMADA_POR_ESCOLHA: Literal["escolha_dela"] = "escolha_dela"


def _agora_em_iso() -> str:
    """Instante atual em ISO-8601, segundo a segundo, com fuso."""
    from datetime import datetime

    return datetime.now().astimezone().isoformat(timespec="seconds")


class PonteConfirmada(BaseModel):
    """O CARIMBO: esta ponte foi confirmada NESTE jogo, e quando.

    PONTE-CONFIRMADA-01 (19/08/2026). O perfil já guardava a ponte — ela é a
    tupla ``(mode.kind, mode.gamepad_flavor, está na allowlist do Steam
    Input)``, com as duas primeiras em ``mode`` e a terceira no
    ``steam_input_apps.txt``. O que faltava não é vocabulário novo: é a resposta
    da pergunta que decide tudo — **"esta combinação foi CONFIRMADA aqui, ou é
    só o que estava no arquivo quando ninguém sabia?"**.

    Sem essa distinção o produto não separa "nunca tentei" de "tentei e
    funciona", e uma escada que tenta as pontes em ordem **nunca para**: ela
    rodaria de novo em todo jogo, a cada abertura, arrancando o controle da mão
    do usuário a cada degrau (R-04, medido em 23/07 — recriar o vpad com o jogo aberto
    tira o controle do jogo).

    POR QUE A TUPLA SE REPETE AQUI, em vez de o carimbo ser um simples
    ``confirmado: true`` sobre o ``mode``. Porque as duas coisas divergem, e a
    divergência é o fato mais útil que este campo produz: ela troca a máscara
    na aba Início, ou tira o jogo da lista de exceções, e o ``mode`` do arquivo
    passa a ser OUTRA ponte — a que foi confirmada continua sendo a de antes.
    Um booleano em cima do ``mode`` seria apagado por essa troca sem que
    ninguém notasse, e o produto voltaria a "não sei" logo depois de saber.
    Guardando a tupla inteira, o produto sabe as duas coisas e pode dizer qual
    é qual (é o que o ``prontuario_dos_jogos`` faz com ela).

    ADITIVO, sem bump de versão — mesmo caminho do ``mouse``, do ``mic``, do
    ``speaker`` e do ``mode``: perfil antigo, SEM o campo, carrega e vale.
    ``None`` aqui significa exatamente **"ainda não sei"**, e é isso que os 18
    perfis do disco do usuário passam a dizer. Um perfil que já traz
    ``gamepad_flavor="dualsense"`` NÃO vira confirmado por existir: nenhuma
    migração escreve este campo, e o portão
    ``test_ponte_confirmada_01`` reprova quem tentar.

    A serialização OMITE o campo quando ``None`` (ver o serializador do
    ``Profile``), pela mesma razão medida do ``rota``/``controllers``:
    ``extra="forbid"`` faz um hefesto ANTIGO recusar o perfil inteiro ao ver
    uma chave que não conhece, e gravar ``"ponte": null`` em todo save
    transformaria "voltar uma versão" em "todos os perfis quebrados".
    """

    model_config = ConfigDict(extra="forbid")

    kind: Literal["desktop", "gamepad", "native"]
    gamepad_flavor: MascaraDeGamepad | None = None
    steam_input: bool = False
    confirmada_em: str = Field(default_factory=_agora_em_iso)
    confirmada_por: Literal["gesto", "silencio", "escolha_dela"] = (
        CONFIRMADA_POR_GESTO
    )

    @field_validator("confirmada_em")
    @classmethod
    def _e_uma_data_de_verdade(cls, value: str) -> str:
        """Data ilegível é pior que data ausente: ela PARECE conhecimento."""
        from datetime import datetime

        try:
            datetime.fromisoformat(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                f"ponte.confirmada_em não é uma data ISO-8601: {value!r} "
                "(ex.: '2026-08-19T21:30:00-03:00')"
            ) from exc
        return value

    @model_validator(mode="after")
    def _mascara_so_existe_com_gamepad(self) -> PonteConfirmada:
        """Máscara sem gamepad virtual é uma ponte que não existe."""
        if self.gamepad_flavor is not None and self.kind != "gamepad":
            raise ValueError(
                "ponte.gamepad_flavor só vale com kind='gamepad' "
                f"(kind={self.kind!r}): sem o gamepad virtual não há máscara "
                "para o jogo ver"
            )
        return self

    def mesma_ponte(
        self,
        mode: ProfileModeConfig | None,
        *,
        na_allowlist: bool,
    ) -> bool:
        """A ponte de HOJE é a que foi confirmada?"""
        if mode is None:
            return False
        return (
            self.kind == mode.kind
            and self.gamepad_flavor == (mode.gamepad_flavor if mode.kind == "gamepad" else None)
            and self.steam_input is bool(na_allowlist)
        )


MOTOR_PCT_PADRAO = 100

#: Teto da barra de motor. **Não é o ``RUMBLE_CUSTOM_MULT_MAX``, e a diferença
MOTOR_PCT_MAX = 100


def pcts_dos_motores(rumble: ControllerRumbleOverride | None) -> tuple[int, int]:
    """``(forte_pct, fraco_pct)`` desta peça — ``(100, 100)`` sem opinião."""
    if rumble is None:
        return (MOTOR_PCT_PADRAO, MOTOR_PCT_PADRAO)
    forte = rumble.motor_forte_pct
    fraco = rumble.motor_fraco_pct
    return (
        MOTOR_PCT_PADRAO if forte is None else int(forte),
        MOTOR_PCT_PADRAO if fraco is None else int(fraco),
    )


def motores_dos_controles(
    controllers: dict[str, ControllerOverrides] | None,
) -> dict[str, tuple[int, int]]:
    """``{uniq: (forte_pct, fraco_pct)}`` do perfil — só quem TEM opinião."""
    fora: dict[str, tuple[int, int]] = {}
    for uniq, cfg in (controllers or {}).items():
        rumble = getattr(cfg, "rumble", None)
        if rumble is None:
            continue
        campos = rumble.model_fields_set
        if "motor_forte_pct" not in campos and "motor_fraco_pct" not in campos:
            continue
        par = pcts_dos_motores(rumble)
        if par == (MOTOR_PCT_PADRAO, MOTOR_PCT_PADRAO):
            continue
        fora[uniq] = par
    return fora


def politicas_dos_controles(
    controllers: dict[str, ControllerOverrides] | None,
) -> dict[str, str]:
    """``{uniq: policy}`` de toda peça do perfil que ESCOLHEU o degrau da força."""
    fora: dict[str, str] = {}
    for uniq, cfg in (controllers or {}).items():
        rumble = getattr(cfg, "rumble", None)
        if rumble is None or "policy" not in rumble.model_fields_set:
            continue
        if rumble.policy is not None:
            fora[uniq] = rumble.policy
    return fora


class ControllerRumbleOverride(BaseModel):
    """A INTENSIDADE da vibração de UMA unidade física (POR-UNIDADE-01, 10/08)."""

    model_config = ConfigDict(extra="forbid")

    policy: Literal["economia", "balanceado", "max", "custom"] | None = None
    custom_mult: float | None = None

    motor_forte_pct: int | None = None

    #: 50% então será 150 em um e 75% no outro"*. <!-- noqa-acento: citação literal -->
    motor_fraco_pct: int | None = None

    haptica_pct: int | None = None

    @model_serializer(mode="wrap")
    def _o_ganho_da_haptica_sem_opiniao_nao_vai_ao_disco(
        self, handler: SerializerFunctionWrapHandler
    ) -> Any:
        """O ``haptica_pct`` só vai ao arquivo quando alguém o escreveu."""
        dados = handler(self)
        if isinstance(dados, dict) and "haptica_pct" not in self.model_fields_set:
            dados.pop("haptica_pct", None)
        return dados

    @model_validator(mode="before")
    @classmethod
    def _auto_nao_e_por_unidade(cls, data: Any) -> Any:
        """Mensagem que EXPLICA a recusa do ``auto`` em vez do literal cru."""
        if isinstance(data, dict) and data.get("policy") == "auto":
            raise ValueError(
                "controllers[...].rumble: 'auto' não vale por unidade — ele "
                "escala pela BATERIA, e quem a lê é o controle PRIMÁRIO "
                "(core.rumble._effective_mult). Guardar 'auto' aqui faria as "
                "duas peças escalarem pela bateria da mesma. Use 'economia', "
                "'balanceado', 'max' ou 'custom'; o 'auto' continua valendo "
                "na seção GLOBAL do perfil."
            )
        return data

    @model_validator(mode="after")
    def _validate_custom_mult(self) -> ControllerRumbleOverride:
        """MESMA regra do ``RumbleConfig`` — a borda recusa o par incoerente."""
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

    @model_validator(mode="after")
    def _validate_barras_de_motor(self) -> ControllerRumbleOverride:
        """A faixa das barras é 0-100, e a recusa EXPLICA por que não passa de 100."""
        for nome, valor in (
            ("motor_forte_pct", self.motor_forte_pct),
            ("motor_fraco_pct", self.motor_fraco_pct),
        ):
            if valor is None:
                continue
            if not (0 <= valor <= MOTOR_PCT_MAX):
                raise ValueError(
                    f"controllers[...].rumble.{nome} fora de [0, "
                    f"{MOTOR_PCT_MAX}]: {valor}. A barra é o SEGUNDO fator — "
                    f"ela multiplica o degrau da coluna (Máximo = 150%, "
                    f"'custom' até {int(RUMBLE_CUSTOM_MULT_MAX * 100)}%), e "
                    f"quem amplifica é o degrau. Uma barra acima de "
                    f"{MOTOR_PCT_MAX} daria à mesma peça duas portas para o "
                    f"mesmo estouro."
                )
        return self

    @model_validator(mode="after")
    def _validate_haptica_pct(self) -> ControllerRumbleOverride:
        """A faixa da háptica é 0-``HAPTICA_PCT_MAX``, recusada na borda."""
        valor = self.haptica_pct
        if valor is not None and not (0 <= valor <= HAPTICA_PCT_MAX):
            raise ValueError(
                f"controllers[...].rumble.haptica_pct fora de [0, "
                f"{HAPTICA_PCT_MAX}]: {valor}"
            )
        return self


class ControllerMicOverride(BaseModel):
    """O MICROFONE de UMA unidade física (MIC-QUINTO-AJUSTE-01, 03/09/2026).

    Decisão, 03/09/2026 — o microfone vira o QUINTO ajuste por controle:
    é o `Virtual` que faz o mic soar igual no cabo e no rádio, ou seja, é o
    ajuste que faz o CANAL daquele controle funcionar; e com
    ``CANAL-POR-CONTROLE-01`` — *"4 controles os 4 tem que ter canais de
    entrada unico pra cada qual"* (noqa-acento: citação literal) —
    um controle no cabo e outro no rádio precisam poder ter tratamentos
    diferentes.

    Subconjunto DELIBERADO de ``ProfileMicConfig``, no molde exato do
    ``ControllerRumbleOverride``: entra o campo cujo caminho por unidade EXISTE
    HOJE, e os outros dois ficam de fora com a medição escrita. A ordem não se
    inverte — **campo que grava e ninguém lê é pior que campo nenhum**: ele faz
    a coluna "Ajuste próprio" da aba Perfis acender sobre um valor que nada
    aplica. Há régua exaustiva nos dois sentidos
    (``tests/unit/test_perfil_por_controle_o_campo_espera_o_caminho.py``).

    O QUE ENTRA — ``muted``, e a escada inteira já carrega o endereço
    -----------------------------------------------------------------
    ``manager.apply_controller_mics`` → ``apply_mic(uniq=…)`` →
    ``lifecycle.apply_profile_mic(uniq=…)`` →
    ``set_microphone_mute(muted, uniq=…)`` → ``_handle_for(uniq)``, que casa o
    MAC normalizado com o handle daquela peça
    (``core/backend_pydualsense.py:4510``). O alvo está no parâmetro em todo
    degrau, e é o que separa *"guardei"* de *"chegou ao aparelho"*.

    **DESDE A O-MUDO-E-DO-CONTROLE-01 O PERFIL NÃO LEVA O MUDO**, nem o da
    peça: ele é do controle e mora no ``maquina.json``
    (``controles[k].microfone_mudo``). A escada acima, de ``apply_mic`` para
    baixo, continua sendo o caminho, mas quem a sobe com o mudo é só o replug
    (``ProfileManager.reapply_mic_on_connect``), com o valor do DONO no lugar
    deste campo; ativação de perfil nenhuma o aplica, e a guarda mora em
    ``ProfileManager.apply_mic``, reusado VERBATIM — não há segunda cópia da
    regra aqui.

    O SEGUNDO QUE ENTROU — ``volume``, e ele tem DOIS DEGRAUS
    ---------------------------------------------------------
    **FATO SUBSTITUÍDO EM 03/09/2026, e completado em 09/09.** Esta seção
    listava o ``volume`` entre os campos DE FORA, primeiro porque o applier
    *"não chamava"* a primitiva por peça (falso desde 03/09 pela manhã) e
    depois porque faltava a palavra de produto. As duas coisas caíram: o usuário mandou
    abrir (*"manda a ver em tudo que falta por favor"*), o campo existe logo
    abaixo, e ``Daemon.apply_profile_mic`` resolve a fonte com
    ``audio_control.fonte_de_captura_do_uniq(uniq)`` quando há ``uniq`` — **sem
    queda** para a rota global, que mandaria o ganho ao microfone do vizinho.
    Manter a recusa escrita aqui ao lado de um campo aberto obrigaria a próxima
    pessoa a escolher entre duas afirmações da mesma classe.

    E desde 09/09/2026 o campo chega ao APARELHO, não só à fonte do sistema:
    ``set_microphone_volume`` escreve o ``common[6]`` daquele controle
    (MIC-VOLUME-02, decisão de produto ``D-0909-O-VOLUME-DO-MIC-LIGA-O-BYTE-DO-
    APARELHO``, depois de a bancada medir o byte obedecendo no cabo —
    ``docs/data/ensaios.csv``, ``folha-mic-volume-o-byte-age-cabo-0909``). Um
    campo, dois degraus, e os dois por ``uniq``.

    O QUE FICA DE FORA, e cada um por uma MEDIÇÃO
    ----------------------------------------------
    - ``button_toggles_system``. O interruptor é UM por máquina:
      ``hotkey.mic_button_loop`` lê ``daemon.config.mic_button_toggles_system``
      (``daemon/subsystems/hotkey.py:906``) e não consulta ``uniq`` nenhum.
      Guardá-lo por peça faria quatro controles gravarem quatro opiniões sobre
      um interruptor só.

    A recusa é na BORDA do esquema, e não no applier, pela mesma razão do
    ``custom_mult`` do rumble e do ``auto`` por unidade: o arquivo inválido
    morre no load, com mensagem que EXPLICA, em vez de virar comportamento
    errado silencioso meses depois. ``extra="forbid"`` faz a recusa; os dois
    validadores abaixo trocam o ``extra_forbidden`` cru pela razão.

    Campo não escrito = sem opinião: o merge POR CAMPO herda o global do
    perfil, exatamente como em ``leds``/``triggers``/``rumble``/``speaker``.
    ``None`` continua sendo silêncio, e perfil antigo sem a seção carrega e
    vale.
    """

    model_config = ConfigDict(extra="forbid")

    muted: bool | None = None

    #: diferentes"*. Com dois DualSense no cabo há DUAS placas de som
    volume: int | None = Field(default=None, ge=0, le=100)

    #: acima, só que mais forte: o ganho é da PLACA ALSA, e com dois DualSense
    gain: int | None = Field(default=None, ge=0, le=100)

    @model_validator(mode="before")
    @classmethod
    def _o_que_ainda_nao_tem_caminho_por_peca(cls, data: Any) -> Any:
        """Mensagem que EXPLICA a recusa em vez do ``extra_forbidden`` cru."""
        if not isinstance(data, dict):
            return data
        if "button_toggles_system" in data:
            raise ValueError(
                "controllers[...].mic: 'button_toggles_system' é UM por "
                "MÁQUINA — quem o lê é `hotkey.mic_button_loop`, em "
                "`daemon.config.mic_button_toggles_system`, sem consultar "
                "`uniq` nenhum. Guardá-lo por peça faria quatro controles "
                "gravarem quatro opiniões sobre um interruptor só. Ele "
                "continua valendo na seção GLOBAL `mic` do perfil."
            )
        return data


class ControllerSensoresOverride(BaseModel):
    """Giroscópio e acelerômetro DESTA peça — ligados ou desligados.

    SENSOR-DE-VERDADE-01 (04/09/2026). Decisão de produto, depois de se recomendar a
    saída barata (virar leitura, um selo "no ar / parado", zero linha nova):

        *"ele tem que funcionar de verdade. ambos independente do modo e da
        mascara."* <!-- noqa-acento: citação literal -->

    **DOIS campos e não um**, porque o usuário disse *"ambos"* e cada um por si —
    e porque o caminho do report sabe separá-los: giroscópio e acelerômetro
    viajam na mesma janela de 25 bytes, em faixas distintas
    (``core/virtual_motion.FAIXA_GIROSCOPIO`` / ``FAIXA_ACELEROMETRO``), e
    zerar meia faixa desliga um sem tocar no outro.

    ``None`` = sem opinião, e sem opinião é LIGADO — ``D-AUDIO-E-GIRO-NASCEM-
    LIGADOS`` (25/08/2026) diz que giroscópio nasce ligado em todo jogo. Um
    perfil que não pediu nada não pode desligar o sensor dela por omissão.

    POR QUE O CAMPO PODE EXISTIR AGORA, e não podia até ontem
    ---------------------------------------------------------
    Porque o caminho por unidade nasceu ANTES do campo, que é a ordem que esta
    classe cobra de si mesma: ``sensor.set`` no IPC, o registro por ``uniq``
    (``core/virtual_motion.REGISTRO``), o filtro na janela que o vpad entrega
    ao jogo e o ``EVIOCGRAB`` no nó "Motion Sensors" pelo ``SensorHub``. Quem
    lê este campo por peça é ``manager.apply_controller_sensores``.

    O QUE O CAMPO **NÃO** ALCANÇA, e está escrito porque medir é o trabalho
    ------------------------------------------------------------------------
    Em **Modo Nativo** o jogo lê o giro pelo ``hidraw`` do controle FÍSICO
    (medido em 04/09/2026 com SDL 2.30: ``tem_giro=true``, 192 amostras
    distintas em 2 s, com o SDL abrindo ``/dev/hidraw4``), e ali o daemon não
    está no caminho — o kernel entrega o report direto. Não há byte a zerar, e
    o DualSense não tem comando de firmware que desligue a IMU
    (``docs/data/mapa-controles.csv``, ``movimento.imu.ligar`` =
    ``existe=nao-tem``). O que sobra em Nativo é o braço evdev, que alcança
    quem lê o nó — e a resposta do ``sensor.set`` diz isso em vez de mentir
    "aplicado".
    """

    model_config = ConfigDict(extra="forbid")

    giroscopio: bool | None = None

    acelerometro: bool | None = None


class ControllerOverrides(BaseModel):
    """Overrides POR CONTROLE dentro do perfil (PERFIL-02, 2026-07-16).

    Campo ``None`` = sem opinião: o controle herda a seção GLOBAL do perfil
    (merge POR CAMPO na aplicação, PERFIL-01 — override parcial nunca apaga a
    cor global no replug).

    **A EXCEÇÃO É UMA, E É DECISÃO (09/09/2026):** em ``mascara``, ``None``
    quer dizer *"volte ao padrão"* — *"Default é Hefesto dualsense padrão"*. O
    controle que o perfil não declara **perde** a máscara própria que estivesse
    valendo, em vez de mantê-la. A diferença existe porque a máscara é a única
    seção cujo estado anterior sobreviveria FORA do perfil: as outras seis são
    reaplicadas por inteiro a cada ativação, e a máscara morava num registro
    próprio que atravessava a troca. Ver o campo, lá embaixo, e
    ``manager.apply_controller_mascaras``, que mede o que a devolução custa.

    O ALVO É TUDO — DECISÃO, 02/09/2026
    -----------------------------------------
    *"acelerômetro, giroscópio, e todas as demais features. **é tudo mesmo**"*
    — e ela marcou junto: teclas e ações de botão, mouse e teclado emulado,
    modo (Hefesto/Xbox/Steam) e microfone.

    **O QUE ISSO DERRUBA:** esta docstring trazia uma lista de seções *"FORA
    porque NÃO TÊM RESPOSTA HONESTA por unidade"*. Essa lista caiu — a resposta
    de produto é que tem resposta, e é por controle. As medições que sustentavam a
    lista continuam de pé, mas mudaram de papel: não são recusa, são FILA DE
    ENGENHARIA, e estão abaixo com o que falta construir em cada uma.

    **A ORDEM, e ela não se inverte:** primeiro o caminho por unidade EXISTIR,
    depois o campo entrar aqui. Campo que grava e ninguém lê é pior que campo
    nenhum — ele faz a tela prometer: a coluna da aba Perfis acende dizendo
    *"este controle tem ajuste próprio"* sobre um valor que nada aplica. Há
    régua, e ela é exaustiva nos dois sentidos:
    ``tests/unit/test_perfil_por_controle_o_campo_espera_o_caminho.py``
    classifica CADA campo desta classe contra o consumidor por-``uniq`` que o
    lê, e reprova tanto campo sem consumidor quanto consumidor órfão.

    O QUE JÁ CHEGA À PEÇA — e é só o que está declarado abaixo
    ----------------------------------------------------------
    - ``leds`` (lightbar + player_leds + brilho) e ``triggers``, desde
      PERFIL-02: ``manager._controllers_to_specs`` os converte em ``OutputSpec``
      por MAC, e o brilho sozinho vira fator em ``_controllers_to_led_scales``;
    - ``rumble``, desde POR-UNIDADE-01 (10/08/2026):
      ``manager._controllers_to_rumble_scales`` devolve ``{uniq: fator}``, que
      o backend aplica na saída de cada handle (``set_rumble_scales``);
    - ``speaker``, da mesma sprint: ``manager.apply_controller_speakers`` chama
      ``apply_speaker(uniq=...)`` → ``apply_profile_speaker(uniq=...)`` →
      ``set_speaker_volume(uniq=...)``, com o alvo no parâmetro em toda a
      escada;
    - ``mic``, desde MIC-QUINTO-AJUSTE-01 (03/09/2026, decisão de produto):
      ``manager.apply_controller_mics`` chama ``apply_mic(uniq=...)`` →
      ``apply_profile_mic(uniq=...)`` → ``set_microphone_mute(uniq=...)``. É um
      subconjunto — só o ``muted`` —, e ``ControllerMicOverride`` diz por
      medição o que ficou de fora e o que cada um espera;
    - ``mascara``, desde MASCARA-NO-PERFIL-01 (08/09/2026, decisão de produto):
      ``manager.apply_controller_mascaras`` escreve a máscara
      daquela peça no registro que ``external_mask.mascara_efetiva`` consulta na
      criação de cada gamepad virtual, e é o perfil que passa a mandar (ver o
      item 3 da fila abaixo, que dizia o contrário até 08/09).
    - ``movimento``, desde A-MIRA-POR-MOVIMENTO-NA-TELA-01 (24/09/2026, a
      palavra de produto: o chip «Mira Virtual» no cartão de cada controle):
      ``manager._controllers_to_miras`` monta o arranjo daquela peça por cima
      do do perfil, e o tique o pergunta com o ``uniq`` de cada jogador
      (``roteador_de_movimento.da_peca``).

    Fora por decisão, e não por falta de caminho:
    - ``label`` — identidade visível é outra frente (4P-03);
    - ``mic_led`` — o mic jamais é colateral de troca de perfil
      (AUDIT-FINDING-PROFILE-MIC-LED-RESET-01).

    A FILA DO QUE FALTA, ORDENADA POR CUSTO — medida em 02/09/2026
    ---------------------------------------------------------------
    1. O que sobrou do ``mic``, e são os DOIS campos que
       ``ControllerMicOverride`` recusa na borda com a razão escrita. O
       ``muted`` entrou em 03/09/2026 (MIC-QUINTO-AJUSTE-01); faltam:

       - ``volume`` — **A COSTURA DO APPLIER FOI FEITA EM 03/09/2026**, e o que
         falta agora é OUTRA metade. Esta linha dizia que
         ``lifecycle.apply_profile_mic`` "hoje usa a rota GLOBAL
         ``fonte_de_captura_do_controle()``"; **FATO SUBSTITUÍDO**: ele passou
         a chamar ``fonte_de_captura_do_uniq(uniq)`` quando recebe ``uniq``, e
         **não cai** para a rota global quando o ``uniq`` não resolve — cair
         seria escrever no microfone do vizinho, que é o estrago inteiro.
         ``tests/unit/test_o_volume_do_mic_segue_o_controle.py`` morde as duas
         formas.

         O QUE FALTA É ABRIR O CAMPO AQUI, e é decisão à parte: abrir muda o
         que o perfil do usuário aceita no disco. Há teste que reprova no dia em que
         alguém o abrir, para que esse dia seja DELIBERADO;
       - ``button_toggles_system`` — ``hotkey.mic_button_loop`` precisa
         consultar o override daquele ``uniq`` antes de
         ``daemon.config.mic_button_toggles_system``, que é um por máquina.

       **NOTA DATADA — 02/09/2026.** Esta docstring dizia que o ``mic`` não
       cabia aqui porque *"o ``EventTopic.BUTTON_DOWN`` publica ``{"button",
       "pressed"}`` e não carrega uniq, então o laço do mic não tem como saber
       de qual peça veio o toque"*. A frase sobre o ``BUTTON_DOWN`` continua
       verdadeira e o motivo dela morreu: o gesto do microfone deixou de passar
       por ali. **O item mais caro da lista virou o mais barato.**

    2. ``giroscopio`` e ``acelerometro`` — **SAÍRAM DA FILA EM 04/09/2026**
       (SENSOR-DE-VERDADE-01). O campo é ``sensores``, e ele entrou porque o
       caminho por unidade nasceu primeiro: ``sensor.set`` no IPC, o registro
       por ``uniq`` (``core/virtual_motion.REGISTRO``), a meia-janela zerada no
       que o vpad entrega ao jogo e o ``EVIOCGRAB`` no nó "Motion Sensors"
       pelo ``SensorHub``. Quem o lê por peça é
       ``manager.apply_controller_sensores``.

       **FATO SUBSTITUÍDO:** esta entrada dizia *"não existe no produto nada
       que desligue um sensor"* e que o hub *"só LÊ"*. Passou a existir, e o
       hub ganhou o braço do grab. O que a medição de 04/09 acrescentou, e
       nenhuma versão desta fila previa, é que **o nó evdev não é por onde o
       SDL lê o giro** — ele lê pelo ``hidraw`` — e que em Modo Nativo o
       daemon não está nesse caminho. O limite está escrito em
       ``ControllerSensoresOverride`` e sai na resposta do método.

    3. ``mode``, e ele é o único da fila com DOIS eixos. O ``mode`` é da SESSÃO
       (decisão, 10/08/2026): existe um só, e o daemon não pode estar em
       dois ao mesmo tempo. **A MÁSCARA do gamepad NÃO está nessa frase** —
       ela ficou larga demais e ela a reescreveu em 15/08/2026
       (MÁSCARA-POR-JOGADOR-01): o co-op cria um gamepad virtual por controle e
       cada um carrega o próprio ``flavor``, então a máscara **é do jogador**,
       com a do jogo como padrão herdado.

       **A MÁSCARA SAIU DESTA FILA EM 08/09/2026 — decisão de produto, MASCARA-NO-
       PERFIL-01.** A pergunta foi *"a máscara por controle deve entrar no
       perfil, junto com luz, gatilho, vibração, som, mic e sensores — ou fica
       da máquina?"*, e a resposta foi *"pode entrar sim"*. **FATO
       SUBSTITUÍDO:** esta entrada dizia *"a máscara não é campo daqui"* e que
       trazê-la *"exige antes uma troca de máscara que NÃO derrube o vpad"*. O
       campo é o ``mascara`` declarado abaixo, e a razão de a porta ter sido
       aberta sem essa troca é a consequência que ela sentiu: **trocar de perfil
       trocava o modo e não trocava a máscara de ninguém** — um perfil de jogo
       que precisa do P2 em Xbox não tinha como dizer isso.

       O custo medido continua de pé e não some por decisão: trocar a máscara
       **derruba e recria o gamepad virtual**. O que o desenho garante é que
       isso só aconteça para quem MUDOU — ``apply_controller_mascaras`` escreve
       peça por peça e ``external_mask.vpad_ficou_para_tras`` compara antes de
       recriar, então um perfil que repete a máscara de alguém não o faz sumir
       no meio da partida (é a regra da NUMA-03). Isso vale inclusive para o
       perfil CALADO, que desde 09/09/2026 devolve todo mundo ao padrão
       (decisão de produto): a devolução apaga a entrada, mas só cai o vpad de quem
       estava FORA do padrão — medido, 0 de 4 com a mesa já no padrão.

       ONDE A MÁSCARA É RESOLVIDA, e a resposta continua num arquivo só:
       ``daemon/subsystems/external_mask.py``. O que mudou é o papel dele — de
       DONO da escolha para CACHE do perfil ativo, consultado por
       ``mascara_efetiva`` na criação de todo vpad e no tique do co-op. Ler o
       perfil do disco naquele tique seria a tempestade de syscalls que o mapa
       de motores do ``gamepad.py`` já pagou uma vez.

       O ``mode`` fica na fila; ele é o eixo que continua sendo da sessão.

    4. ``mouse``, ``key_bindings``, ``button_actions``, ``teclado_emulado`` e
       ``suppress_desktop_emulation``. Os cinco esbarram na MESMA medição, e
       ela continua de pé: ``PyDualSenseController.read_state`` diz, em
       comentário de código, que *"INPUT vem SEMPRE do controle PRIMÁRIO"* e
       que a emulação de mouse/teclado/gamepad é **single-controller por
       construção**; o ``Daemon`` tem UM ``_mouse_device`` e UM
       ``_keyboard_device`` (``daemon/lifecycle.py``), alimentados por um
       ``read_state()`` por tique. Guardar por controle é fácil; **fazer valer**
       exige um caminho de ENTRADA por unidade — ler cada peça e despachar para
       o device dela. É o item mais caro da fila, e é o que destrava os cinco de
       uma vez.

    5. ``touchpad``. Continua sem campo em lugar nenhum do perfil e sem tela
       aprovada que ofereça interruptor: na aba Controles ele é leitura viva.
       **É pergunta aberta para ela, não dívida com dono** — inventá-lo aqui
       seria feature nova.

    A CONTRADIÇÃO ABERTA, E É DO USUÁRIO — não se fecha escrevendo código
    -------------------------------------------------------------------
    Três frases desta casa não cabem juntas, e a decisão de 02/09 as põe frente
    a frente:

    - o contrato do topo desta classe: **campo ``None`` = sem opinião**, e
      perfil que não pediu nada não impõe nada;
    - ela, em 18/08/2026, derrubando o princípio geral: *"o perfil tem de
      guardar tudo"*;
    - ``D-AUDIO-E-GIRO-NASCEM-LIGADOS`` (25/08): áudio e giroscópio nascem
      **LIGADOS** em todo jogo — que é um default, não uma ausência.

    Com "é tudo por controle", os três precisam ser reconciliados POR ELA. Está
    registrado, não resolvido.
    """

    model_config = ConfigDict(extra="forbid")

    # SÃO OITO, e a tela oferece dez. O que falta, e o CAMINHO que cada um
    # espera antes de poder entrar, está na fila da docstring acima — ordenada
    # por custo. O `mic` entrou em 03/09/2026 pelo `muted`, que é o campo dele
    # cuja escada carrega o `uniq` em todo degrau; o `sensores` entrou em
    # 04/09/2026, quando o interruptor que ele prometia passou a existir; a
    # `mascara` entrou em 08/09/2026, por decisão de produto — e é a primeira que não
    # é uma SEÇÃO, e sim um valor só; o `movimento` entrou em 24/09/2026, com o
    # chip «Mira Virtual» que o usuário pediu no cartão de cada controle.
    leds: LedsConfig | None = None
    triggers: TriggersConfig | None = None
    rumble: ControllerRumbleOverride | None = None
    speaker: ProfileSpeakerConfig | None = None
    mic: ControllerMicOverride | None = None
    sensores: ControllerSensoresOverride | None = None
    #: *"Como este controle aparece nos jogos"*, SÓ desta peça — MASCARA-NO-
    #: PERFIL-01 (08/09/2026, decisão de produto: *"pode entrar sim"*).
    #:
    #: ``None`` = **volte ao padrão**, e esta é a ÚNICA seção desta classe em
    #: que ``None`` não quer dizer *"sem opinião"*. É decisão, 09/09/2026:
    #: *"Default é Hefesto dualsense padrão"*. O controle que o perfil não
    #: declara perde a máscara própria e passa a seguir o
    #: ``mode.gamepad_flavor`` do perfil e, sem ele, o
    #: não declara. A régua da ordem mede o comportamento dos três degraus, não
    mascara: MascaraDeGamepad | None = None
    movimento: ProfileMovimentoConfig | None = None


_KEY_BINDING_TOKEN_RE = re.compile(r"^(KEY_[A-Z0-9_]+|__[A-Z_]+__)$")


#: quem manda no default passam a morar juntos; e este módulo importa só
#: stdlib + pydantic, o que permite `profiles/`, `app/` e o CLI lerem a faixa
#: sem nenhum deles puxar GTK.
#: Quem mudar o teto muda AQUI. O glade tem de acompanhar na mão (XML não
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
    # - None = herda DEFAULT_BUTTON_BINDINGS do core.
    key_bindings: dict[str, list[str]] | None = None
    # - None = herda o de fábrica INTEIRO (`core/acoes_de_botao.padrao()`, que
    # `acoes_de_botao` é quem os separa. Aposentar um em favor do outro é
    button_actions: dict[str, str] | None = None
    # GLOBAL no perfil, não por controle (D-0809-A-NAVEGACAO-E-GLOBAL-NO-PERFIL):
    # POR QUE NÃO É O `button_actions` ACIMA: aquele fala a língua de TECLA e
    remapeamento: dict[str, str] | None = None
    movimento: ProfileMovimentoConfig | None = None
    mouse: ProfileMouseConfig | None = None
    # flag global `keyboard_emulation.flag` (utils/session.py:306), enquanto o
    # chamada por nenhum caminho de ativação real"*. Por 24 dias foi verdade —
    # preferência GLOBAL, e esta precedência deixaria de existir na ativação
    teclado_emulado: bool | None = None
    mic: ProfileMicConfig | None = None
    speaker: ProfileSpeakerConfig | None = None
    mode: ProfileModeConfig | None = None
    suppress_desktop_emulation: bool = False
    # entre USB e BT no DualSense). None = perfil v1 puro, sem opinião
    controllers: dict[str, ControllerOverrides] | None = None
    ponte: PonteConfirmada | None = None

    @model_serializer(mode="wrap")
    def _sem_ponte_a_chave_nem_aparece(
        self, handler: SerializerFunctionWrapHandler
    ) -> Any:
        """Perfil sem ponte confirmada sai do dump IDÊNTICO ao que era."""
        dados = handler(self)
        if isinstance(dados, dict):
            for opcional in ("ponte", "remapeamento", "movimento"):
                if dados.get(opcional) is None:
                    dados.pop(opcional, None)
        return dados

    @field_validator("name")
    @classmethod
    def _name_nonempty(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("name não pode ser vazio")
        if "/" in value or ".." in value or os.sep in value:
            raise ValueError(f"name contém caractere inválido: {value!r}")
        from hefesto_dualsense4unix.profiles.slug import slugify
        try:
            slugify(value)
        except ValueError as exc:
            raise ValueError(f"name não produz slug válido: {value!r}") from exc
        return value

    @field_validator("button_actions")
    @classmethod
    def _validate_button_actions(
        cls, value: dict[str, str] | None
    ) -> dict[str, str] | None:
        """Recusa botão que a tela não mostra e ação que o vocabulário não tem.

        AS DUAS RECUSAS SÃO DERIVADAS, e é o que as impede de envelhecer: os
        nomes válidos saem de `core/acoes_de_botao.BOTOES` e `.ACOES`, que por
        sua vez saem dos mapas do produto. Uma lista escrita aqui seria a quarta
        cópia do mesmo fato — e a que ninguém lembraria de atualizar.

        O ERRO NOMEIA O QUE ACEITA. Um perfil que chega de outra máquina com um
        botão que esta versão não conhece precisa dizer QUAL, senão a mensagem
        vira "perfil inválido" e a pessoa perde a tarde.
        """
        if value is None:
            return value
        from hefesto_dualsense4unix.core.acoes_de_botao import ACOES, BOTOES

        for botao, acao in value.items():
            if botao not in BOTOES:
                raise ValueError(
                    f"button_actions: {botao!r} não é um dos botões da tela. "
                    f"Os que existem: {', '.join(BOTOES)}"
                )
            if not isinstance(acao, str) or acao not in ACOES:
                raise ValueError(
                    f"button_actions[{botao!r}]: {acao!r} não é uma ação "
                    f"conhecida. As que existem estão em "
                    f"`core/acoes_de_botao.ACOES`."
                )
        return value

    @field_validator("remapeamento")
    @classmethod
    def _validate_remapeamento(
        cls, value: dict[str, str] | None
    ) -> dict[str, str] | None:
        """A troca que o produto sabe fazer, limpa — ou a recusa nomeando."""
        if value is None:
            return None
        from hefesto_dualsense4unix.core.remapeamento_de_botao import resolver

        return resolver(value) or None

    @field_validator("key_bindings")
    @classmethod
    def _validate_key_bindings(
        cls, value: dict[str, list[str]] | None
    ) -> dict[str, list[str]] | None:
        """Rejeita tokens fora do padrão ou KEY_* inexistentes em evdev.ecodes."""
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
        """Chave do mapa = MAC normalizado (12 hex); rejeita degenerados."""
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
        """True quando o perfil casa com QUALQUER janela."""
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


_CLASSES_DE_JOGO_CONHECIDAS: frozenset[str] = frozenset()


def registrar_classes_de_jogo(classes: object) -> None:
    """Declara QUAIS `wm_class` de fora da Steam são de jogo. Um dono só."""
    global _CLASSES_DE_JOGO_CONHECIDAS
    if not isinstance(classes, (list, tuple, set, frozenset)):
        _CLASSES_DE_JOGO_CONHECIDAS = frozenset()
        return
    _CLASSES_DE_JOGO_CONHECIDAS = frozenset(
        c.strip().casefold() for c in classes if isinstance(c, str) and c.strip()
    )


def classes_de_jogo_conhecidas() -> frozenset[str]:
    """O cadastro de agora — o ÚNICO leitor do módulo, e o de fora também."""
    return _CLASSES_DE_JOGO_CONHECIDAS


def e_endereco_de_jogo(wm_class: object) -> bool:
    """Esta `wm_class` endereça um JOGO?"""
    if not isinstance(wm_class, str):
        return False
    if steam_appid_from_wm_class(wm_class) is not None:
        return True
    return wm_class.strip().casefold() in classes_de_jogo_conhecidas()


def perfil_e_regra_de_jogo(profile: Profile | None, window_info: dict[str, Any]) -> bool:
    """True quando o perfil é a regra PRÓPRIA do jogo em foco."""
    match = getattr(profile, "match", None)
    if not isinstance(match, MatchCriteria) or not match.window_class:
        return False
    wm_class = str(window_info.get("wm_class") or "")
    if not e_endereco_de_jogo(wm_class):
        return False
    return _casa_sem_caixa(wm_class, match.window_class)


def normalizar_gamepad_flavor(valor: object) -> MascaraDeGamepad | None:
    """Converte uma máscara CRUA na forma fechada que `ProfileModeConfig` aceita."""
    if valor == "dualsense":
        return "dualsense"
    if valor == "xbox":
        return "xbox"
    if valor == "nintendo":
        return "nintendo"
    return None


def perfil_declara_modo_de_jogo(profile: Profile | None) -> bool:
    """True quando o perfil DIZ, no próprio arquivo, que serve para jogar."""
    if profile is None:
        return False
    if bool(getattr(profile, "e_catch_all", True)):
        return False
    kind = getattr(getattr(profile, "mode", None), "kind", None)
    return kind in ("gamepad", "native")


def resolver_teclado_emulado(profile: Profile | None, flag_global: bool) -> bool:
    """A precedência da T14 (Z4, 24/08/2026), PURA: perfil com opinião VENCE."""
    if profile is None or profile.teclado_emulado is None:
        return flag_global
    return profile.teclado_emulado


# <!-- noqa-acento: citação literal -->


BRILHO_DA_BARRA_NA_ECONOMIA = 0.3

BRILHO_DAS_LUZES_NA_ECONOMIA: Literal["fraco"] = "fraco"

POLITICA_DA_VIBRACAO_NA_ECONOMIA: Literal["economia"] = "economia"

FATOR_DO_GATILHO_NA_ECONOMIA = 0.5

FORCAS_DO_GATILHO: dict[str, tuple[int, ...]] = {
    "Rigid": (1,),
    "SimpleRigid": (0,),
    "PulseA": (2,),
    "PulseB": (2,),
    "Resistance": (1,),
    "Bow": (2, 3),  # (start, end, force, snap)
    "SemiAutoGun": (2,),  # (start, end, force)
    "AutoGun": (1,),  # (start, strength, frequency)
    "Machine": (2, 3),  # (start, end, amp_a, amp_b, frequency, period)
    "Feedback": (1,),  # (position, strength)
    "Weapon": (2,),  # (start, end, force)
    "Vibration": (1,),  # (position, amplitude, frequency)
    "SlopeFeedback": (2, 3),  # (start, end, start_strength, end_strength)
    "MultiPositionFeedback": tuple(range(10)),
    "MultiPositionVibration": tuple(range(1, 11)),
}

MODOS_DE_GATILHO_SEM_FORCA: frozenset[str] = frozenset(
    {"Off", "Pulse", "Galloping", "Custom"}
)


class PecaDaEconomia(NamedTuple):
    """Uma coisa que gasta bateria, e o que a economia faz com ela."""

    nome: str
    o_que_faz: str
    ponto_de_aplicacao: str | None


A_ECONOMIA_EM_CADA_PECA: tuple[PecaDaEconomia, ...] = (
    PecaDaEconomia(
        "Barra de luz",
        f"Brilho até {round(BRILHO_DA_BARRA_NA_ECONOMIA * 100)}%, na mesma cor.",
        "hefesto_dualsense4unix.profiles.schema:leds_na_economia",
    ),
    PecaDaEconomia(
        "Luzes de número",
        "Brilho Fraco, com o número do jogador aceso.",
        "hefesto_dualsense4unix.profiles.schema:leds_na_economia",
    ),
    PecaDaEconomia(
        "Vibração",
        "O teto da Economia, nos dois motores e na háptica.",
        "hefesto_dualsense4unix.profiles.schema:vibracao_na_economia",
    ),
    PecaDaEconomia(
        "Gatilhos",
        "O mesmo efeito, no mesmo ponto, com metade da força.",
        "hefesto_dualsense4unix.profiles.schema:gatilho_na_economia",
    ),
    PecaDaEconomia(
        "Microfone",
        "Fica como está: é escolha de privacidade, não de bateria "
        "(D-PERFIL-DE-DESEMPENHO, 24/08/2026).",
        None,
    ),
    PecaDaEconomia(
        "Alto-falante",
        "Fica como está: o volume é o que se ouve, e baixar seria perder o som.",
        None,
    ),
    PecaDaEconomia(
        "Giroscópio",
        "Fica como está: o DualSense não tem comando que desligue a IMU, e "
        "desligar seria perder a mira.",
        None,
    ),
)


def economia_vale(escolha_do_controle: bool | None, mesa_em_economia: bool) -> bool:
    """A economia vale nesta peça? A regra entre o global e o do controle."""
    return bool(mesa_em_economia) or escolha_do_controle is True


def origem_da_economia(
    escolha_do_controle: bool | None, mesa_em_economia: bool
) -> Literal["mesa", "controle"] | None:
    """QUEM ligou a economia nesta peça: a mesa, o controle, ou ninguém."""
    if mesa_em_economia:
        return "mesa"
    if escolha_do_controle is True:
        return "controle"
    return None


def mesa_em_economia(teto_da_mesa: str | None) -> bool:
    """A chave do Perfil Global de Bateria liga a economia na mesa inteira?"""
    from hefesto_dualsense4unix.core.rumble import teto_do_orcamento

    return teto_do_orcamento(teto_da_mesa) is not None


_FONTE_DA_DECLARACAO: Any = None


def registrar_declaracao_da_mesa(fonte: Any) -> None:
    """O daemon diz de onde ler a declaração da mesa (o ``maquina.json`` vivo)."""
    global _FONTE_DA_DECLARACAO
    _FONTE_DA_DECLARACAO = fonte if callable(fonte) else None


def _declaracao_viva() -> Any:
    """A declaração de agora, ou ``None``. Fonte que levanta é ``None``."""
    fonte = _FONTE_DA_DECLARACAO
    if fonte is None:
        return None
    try:
        return fonte()
    except Exception:
        return None


def economia_da_declaracao(declaracao: Any) -> tuple[bool, frozenset[str]]:
    """``(a mesa em «Bateria longa», os uniq que ligaram a sua)`` de UMA declaração."""
    orcamento = getattr(declaracao, "orcamento", None)
    teto = getattr(orcamento, "teto", None)
    mesa = mesa_em_economia(teto if isinstance(teto, str) else None)
    controles = getattr(declaracao, "controles", None)
    if not isinstance(controles, dict):
        return mesa, frozenset()
    ligados = frozenset(
        uniq
        for uniq, declarado in controles.items()
        if isinstance(uniq, str) and getattr(declarado, "economia", None) is True
    )
    return mesa, ligados


def economia_da_mesa() -> bool:
    """A mesa está em «Bateria longa» AGORA?"""
    return economia_da_declaracao(_declaracao_viva())[0]


def controles_em_economia() -> frozenset[str]:
    """Os ``uniq`` (doze hexa) cujo controle LIGOU a sua economia, AGORA."""
    return economia_da_declaracao(_declaracao_viva())[1]


def declaracao_da_economia(uniq: str, ligada: bool) -> dict[str, Any]:
    """A declaração PARCIAL que liga ou desliga a economia de um controle."""
    from pydantic import ValidationError

    from hefesto_dualsense4unix.profiles.manager import chave_de_peca_que_grava
    from hefesto_dualsense4unix.utils.maquina import MaquinaConfig

    chave = chave_de_peca_que_grava(str(uniq or ""))
    if chave is None:
        raise ValueError(f"economia: {uniq!r} não é o endereço de um controle")
    try:
        MaquinaConfig.model_validate({"controles": {chave: {"economia": True}}})
    except ValidationError as exc:
        raise ValueError(f"economia: {uniq!r} não é chave de controle: {exc}") from exc
    return {"controles": {chave: {"economia": True if ligada else None}}}


def _escritos(modelo: BaseModel) -> dict[str, Any]:
    """Só os campos que o modelo ESCREVEU — o vocabulário parcial do override."""
    return modelo.model_dump(exclude_unset=True)


def _forca_na_economia(valor: int) -> int:
    """Metade da força, com piso 1. Zero continua zero: é zona inativa."""
    import math

    if valor <= 0:
        return valor
    return max(1, math.ceil(valor * FATOR_DO_GATILHO_NA_ECONOMIA))


def gatilho_na_economia(gatilho: TriggerConfig) -> TriggerConfig:
    """O mesmo gatilho, no mesmo modo e no mesmo ponto, com a força no teto."""
    indices = FORCAS_DO_GATILHO.get(gatilho.mode)
    if not indices or not gatilho.params:
        return gatilho.model_copy()
    params: list[int] | list[list[int]]
    if gatilho.is_nested:
        aninhado: list[list[int]] = gatilho.params  # type: ignore[assignment]
        params = [[_forca_na_economia(int(v)) for v in sub] for sub in aninhado]
    else:
        plano: list[int] = list(gatilho.params)  # type: ignore[arg-type]
        for i in indices:
            if i < len(plano):
                plano[i] = _forca_na_economia(int(plano[i]))
        params = plano
    return TriggerConfig(mode=gatilho.mode, params=params)


def gatilhos_na_economia(
    dele: TriggersConfig | None, do_perfil: TriggersConfig | None
) -> TriggersConfig | None:
    """Os gatilhos de UMA peça na economia, lado a lado."""
    lados: dict[str, Any] = {}
    for lado in ("left", "right"):
        escrito = dele is not None and lado in dele.model_fields_set
        if escrito:
            fonte = getattr(dele, lado)
        elif do_perfil is not None:
            fonte = getattr(do_perfil, lado)
        else:
            continue
        lados[lado] = gatilho_na_economia(fonte)
    if not lados:
        return dele
    return TriggersConfig(**lados)


def leds_na_economia(
    dele: LedsConfig | None, do_perfil: LedsConfig | None
) -> LedsConfig | None:
    """A luz de UMA peça na economia — o brilho no teto, a cor de sempre."""
    campos = _escritos(dele) if dele is not None else {}
    if "lightbar_brightness" in campos:
        brilho: float | None = float(campos["lightbar_brightness"])
    elif do_perfil is not None:
        brilho = float(do_perfil.lightbar_brightness)
    else:
        brilho = None
    if brilho is not None:
        campos["lightbar_brightness"] = min(brilho, BRILHO_DA_BARRA_NA_ECONOMIA)
    if do_perfil is not None or "player_led_brightness" in campos:
        campos["player_led_brightness"] = BRILHO_DAS_LUZES_NA_ECONOMIA
    if not campos:
        return dele
    return LedsConfig.model_validate(campos)


def leds_do_perfil_na_economia(leds: LedsConfig) -> LedsConfig:
    """A seção GLOBAL da luz com a economia — a da mesa em «Bateria longa»."""
    return leds.model_copy(
        update={
            "lightbar_brightness": min(
                float(leds.lightbar_brightness), BRILHO_DA_BARRA_NA_ECONOMIA
            ),
            "player_led_brightness": BRILHO_DAS_LUZES_NA_ECONOMIA,
        }
    )


def gatilhos_do_perfil_na_economia(triggers: TriggersConfig) -> TriggersConfig:
    """A seção GLOBAL dos gatilhos com a economia — os dois lados."""
    return TriggersConfig(
        left=gatilho_na_economia(triggers.left),
        right=gatilho_na_economia(triggers.right),
    )


def _mult_da_vibracao(policy: str | None, custom_mult: float | None) -> float | None:
    """O multiplicador de uma política fixa, lido do dono dos degraus."""
    if policy is None:
        return None
    if policy == "custom":
        return None if custom_mult is None else float(custom_mult)
    from hefesto_dualsense4unix.daemon.subsystems.rumble import RUMBLE_POLICY_MULT

    return RUMBLE_POLICY_MULT.get(policy)


def vibracao_na_economia(
    dela: ControllerRumbleOverride | None,
    politica_do_perfil: str | None,
    custom_do_perfil: float | None = None,
    *,
    mesa: bool = False,
) -> ControllerRumbleOverride | None:
    """A vibração de UMA peça sob o teto da economia."""
    base = _mult_da_vibracao(politica_do_perfil or "balanceado", custom_do_perfil)
    if base is None or base <= 0.0:
        return dela
    escrito = dela is not None and "policy" in dela.model_fields_set
    da_peca = (
        _mult_da_vibracao(dela.policy, dela.custom_mult)
        if escrito and dela is not None
        else base
    )
    if da_peca is None:
        return dela
    teto = base if mesa else _mult_da_vibracao(POLITICA_DA_VIBRACAO_NA_ECONOMIA, None)
    if teto is None or da_peca <= teto:
        return dela
    campos = _escritos(dela) if dela is not None else {}
    campos.pop("policy", None)
    campos.pop("custom_mult", None)
    if not mesa:
        campos["policy"] = POLITICA_DA_VIBRACAO_NA_ECONOMIA
    if not campos:
        return None
    return ControllerRumbleOverride.model_validate(campos)


#     teclado      `DaemonConfig.keyboard_emulation_enabled` nasce True

E_CONTRATO = "contrato"

E_OBRIGATORIO = "obrigatório"

E_SECAO = "seção"

NASCE_NO_ESQUEMA = "no-esquema"

NASCE_NO_LEITOR = "no-leitor"

NASCE_NA_ADOCAO = "na-adoção"

AGUARDA_A_PALAVRA_DELA = "aguarda-a-palavra-dela"

PILHA_DAS_FEATURES = frozenset(
    {NASCE_NO_ESQUEMA, NASCE_NO_LEITOR, NASCE_NA_ADOCAO, AGUARDA_A_PALAVRA_DELA}
)


class Nascimento(NamedTuple):
    """De onde vem o valor de um campo quando ninguém opinou."""

    onde: str
    razao: str
    dono: str = ""
    falta: str = ""


NASCIMENTO_DOS_CAMPOS: dict[str, Nascimento] = {
    "MatchAny.type": Nascimento(
        E_CONTRATO, "Discriminador da união; é o NOME do sentinel, não um valor."
    ),
    "MatchManual.type": Nascimento(
        E_CONTRATO, "Discriminador da união; ver `MatchAny.type`."
    ),
    "MatchCriteria.type": Nascimento(
        E_CONTRATO, "Discriminador da união; ver `MatchAny.type`."
    ),
    "MatchCriteria.window_class": Nascimento(
        E_CONTRATO,
        "Lista vazia é critério IGNORADO em `matches`. Semear uma classe de "
        "fábrica faria todo perfil casar com a janela errada.",
    ),
    "MatchCriteria.window_title_regex": Nascimento(
        E_CONTRATO,
        "`None` é critério ignorado. Um regex de fábrica casaria com título "
        "nenhum ou com todos, e as duas coisas são piores que não perguntar.",
    ),
    "MatchCriteria.process_name": Nascimento(
        E_CONTRATO, "Mesma regra do `window_class`: lista vazia não é condição."
    ),
    "TriggerConfig.mode": Nascimento(
        E_OBRIGATORIO,
        "Quem constrói um gatilho diz qual é o modo. O nascimento é decidido "
        "no pai, `TriggersConfig.left`/`right`.",
    ),
    "TriggerConfig.params": Nascimento(
        E_CONTRATO,
        "Vazio não é 'desligado': é 'este modo não pede parâmetro' (`Off`, "
        "`Pulse`). Modo que pede e não recebe estoura em `build_from_name`, "
        "que é a borda certa.",
    ),
    "TriggersConfig.left": Nascimento(
        NASCE_NO_ESQUEMA,
        "NASCE RÍGIDO desde 20/09/2026 — a decisão dela de 16/09 e a única "
        "das catorze que nascia muda de verdade. A razão da camada está em "
        "`MODO_DE_NASCIMENTO_DO_GATILHO`.",
    ),
    "TriggersConfig.right": Nascimento(
        NASCE_NO_ESQUEMA, "Ver `TriggersConfig.left`; os dois lados, sempre juntos."
    ),
    "LedsConfig.lightbar": Nascimento(
        NASCE_NO_LEITOR,
        "`(0, 0, 0)` é a cor do BROADCAST, e ela só vale com "
        "`auto_player_colors=False`. De fábrica a cor de cada peça sai da "
        "paleta por slot, então a barra nasce ACESA.",
        dono="hefesto_dualsense4unix.core.led_control:cores_sem_colisao",
    ),
    "LedsConfig.player_leds": Nascimento(
        NASCE_NO_LEITOR,
        "Cinco `False` é a lista do broadcast. Com as cores automáticas "
        "ligadas quem acende o LED do número é a COR-03 (D7), por slot.",
        dono="hefesto_dualsense4unix.core.led_control:cores_sem_colisao",
    ),
    "LedsConfig.lightbar_brightness": Nascimento(
        NASCE_NO_ESQUEMA, "1.0 é o topo da escala: a barra nasce no brilho máximo."
    ),
    "LedsConfig.player_led_brightness": Nascimento(
        NASCE_NO_ESQUEMA,
        "`\"fraco\"` é a decisão dela de 24/09 "
        "(`D-2409-AS-LUZES-DE-NUMERO-TEM-TRES-BRILHOS`): as luzes de número "
        "nascem no Fraco, e o produto MANDA esse degrau. O silêncio seria não "
        "mandar — o firmware no último degrau que alguém autorizou.",
    ),
    "LedsConfig.auto_player_colors": Nascimento(
        NASCE_NO_ESQUEMA,
        "`True` desde a COR-03. É ele que faz a barra e o LED do número "
        "nascerem acesos — os dois campos acima dependem deste.",
    ),
    "LedsConfig.lightbar_para_o_numero": Nascimento(
        E_CONTRATO,
        "É a PROCEDÊNCIA de uma cor gravada (para qual número ela foi "
        "escolhida), não uma feature. `None` = sem procedência, tratado como "
        "LEGADO pelo resolvedor.",
    ),
    "RumbleConfig.passthrough": Nascimento(
        NASCE_NO_ESQUEMA, "`True`: a vibração que o jogo manda passa para o motor."
    ),
    "RumbleConfig.policy": Nascimento(
        NASCE_NO_LEITOR,
        "A VIBRAÇÃO JÁ NASCE BALANCEADA, e não é aqui. Medido em 20/09/2026: "
        "`DaemonConfig.rumble_policy` nasce `\"balanceado\"`, e `policy=None` "
        "é o perfil dizendo 'não mexo' — a política global segue valendo. "
        "ENCHER este default teria PREÇO medido: `apply_profile_rumble_policy` "
        "passaria a IMPOR balanceado em toda ativação, e a escolha manual dela "
        "(`rumble.policy_set`) seria desfeita na primeira troca de janela "
        "depois dos 30 s da trava. O que falta é a TELA mostrar o herdado, e "
        "isso é a VIBRA-ACESA-01.",
        dono="hefesto_dualsense4unix.daemon.lifecycle:DaemonConfig",
    ),
    "RumbleConfig.custom_mult": Nascimento(
        E_CONTRATO,
        "Só vale com `policy='custom'`; o validador do modelo recusa fora "
        "disso. Não é feature, é coerência de um par.",
    ),
    "ProfileMouseConfig.enabled": Nascimento(
        E_OBRIGATORIO, "Não existe seção de mouse sem opinião: quem a escreve diz."
    ),
    "ProfileMouseConfig.speed": Nascimento(
        E_CONTRATO,
        "Parâmetro da seção, não a feature — quem liga é o `enabled`. O "
        "`ge=1` do campo garante que nenhum nascimento seja mudo: a faixa "
        "1-12 do daemon não tem 'desligado'.",
    ),
    "ProfileMouseConfig.scroll_speed": Nascimento(
        E_CONTRATO, "Ver `ProfileMouseConfig.speed`; faixa 1-5, mesmo piso."
    ),
    "ProfileMicConfig.button_toggles_system": Nascimento(
        E_OBRIGATORIO, "Quem escreve a seção diz. O global nasce `True` no daemon."
    ),
    "ProfileMicConfig.volume": Nascimento(
        AGUARDA_A_PALAVRA_DELA,
        "O ganho de captura não tem degrau de nascimento: a SOM-SEMPRE-01 pôs "
        "o ALTO-FALANTE em 100% na adoção e deixou o microfone de fora, "
        "escrito com todas as letras (*'o microfone continua SEM DONO'*).",
        falta="qual é o ganho de captura de fábrica, e se ele se escreve na adoção",
    ),
    "ProfileMicConfig.gain": Nascimento(
        NASCE_NO_LEITOR,
        "O ganho de ENTRADA é da PLACA DE SOM do controle, não do firmware — "
        "`None` quer dizer *não opino*, e quem responde é o elemento `cvolume` "
        "da placa, que já tem um valor. Escrever um default aqui poria o "
        "perfil mandando na amplificação de um aparelho que ele não conhece: "
        "a mesma placa responde 0-101 no DualSense e outra coisa em qualquer "
        "outro microfone. Só o número que ELA arrastou vai ao disco.",
        dono="hefesto_dualsense4unix.integrations.ganho_do_microfone:definir",
    ),
    "ProfileMicConfig.muted": Nascimento(
        NASCE_NO_LEITOR,
        "O microfone NASCE NO AR desde 17/09/2026, e `None` herda isso — só "
        "`true` gravado no disco cala. A inversão é ordem dela (18/09): todo "
        "controle nasce com tudo, e o silêncio dela vence porque é explícito.",
        dono="hefesto_dualsense4unix.integrations.plano_de_radio:microfone_nasce_ligado",
    ),
    "ProfileSpeakerConfig.volume": Nascimento(
        E_OBRIGATORIO,
        "Obrigatório por medição (SOM-02, armadilhas 1 e 2): seção sem volume "
        "tranca o alto-falante em zero, e nem o próprio mudo o solta.",
    ),
    "ProfileSpeakerConfig.muted": Nascimento(
        NASCE_NO_ESQUEMA, "`False`: o alto-falante nasce com voz. Não se mexe."
    ),
    "ProfileSpeakerConfig.rota": Nascimento(
        NASCE_NA_ADOCAO,
        "SOM-ROTA-02 (16/09): não escrever a rota NÃO é o lado neutro — o "
        "firmware cai no fone vazio. O controle passou a nascer em "
        "`ROTA_PADRAO_DO_SOM` na adoção, e o perfil calado herda isso.",
        dono="hefesto_dualsense4unix.core.backend_pydualsense:ROTA_PADRAO_DO_SOM",
    ),
    "ProfileSpeakerConfig.volume_padrao": Nascimento(
        NASCE_NA_ADOCAO,
        "O botão «Padrão» do volume (04/10/2026): ausente, vale o volume que o perfil escolheu, "
        "como antes; o perfil sem a seção também é Padrão, e o controle nasce nos 100% de "
        "sempre na adoção. Ligado, o perfil aplica esses 100% e guarda o `volume` dela.",
        dono="hefesto_dualsense4unix.core.backend_pydualsense:VOLUME_PADRAO_DO_SOM",
    ),
    "ProfileSpeakerConfig.fonte": Nascimento(
        NASCE_NO_LEITOR,
        "O MODELO DESTA TABELA: `None` cai no padrão da casa, `sfx`, por "
        "decisão dela de 08/09 (D-0809-NO-CABO-O-PADRAO-DO-SOM-E-SFX). Com "
        "`mix` de fábrica o controle viraria a saída de todo o som do PC "
        "sozinho — a justificativa está escrita ao lado do campo.",
        dono="hefesto_dualsense4unix.integrations.alto_falante_bt:FONTE_SFX",
    ),
    "ProfileModeConfig.kind": Nascimento(
        E_OBRIGATORIO, "Não existe seção de modo sem dizer qual modo."
    ),
    "ProfileModeConfig.gamepad_flavor": Nascimento(
        NASCE_NO_LEITOR,
        "`None` é o degrau 2 vazio: a máscara efetiva cai no "
        "`DaemonConfig.gamepad_flavor`, que nasce `dualsense`. O controle "
        "nunca fica SEM máscara.",
        dono="hefesto_dualsense4unix.daemon.subsystems.external_mask:mascara_efetiva",
    ),
    "ProfileModeConfig.caminho": Nascimento(
        NASCE_NO_LEITOR,
        "`None` = ninguém escolheu, e o caminho sai da máscara. A ordem de "
        "HERANÇA entre perfis tem defeito medido (perfil sem `caminho` herda "
        "o do jogo anterior) e o dono é o resolvedor, não este campo.",
        dono="hefesto_dualsense4unix.integrations.virtual_pad:caminho_resolvido",
    ),
    "PonteConfirmada.kind": Nascimento(
        E_OBRIGATORIO, "Registro de uma confirmação; sem o modo não há o que registrar."
    ),
    "PonteConfirmada.gamepad_flavor": Nascimento(
        E_CONTRATO, "O que foi confirmado, não o que se pede. `None` = não se aplica."
    ),
    "PonteConfirmada.steam_input": Nascimento(
        E_CONTRATO, "`False` = não havia Steam Input quando confirmei. É fato, não pedido."
    ),
    "PonteConfirmada.confirmada_em": Nascimento(
        E_CONTRATO, "Carimbo de tempo da confirmação."
    ),
    "PonteConfirmada.confirmada_por": Nascimento(
        E_CONTRATO, "Procedência da confirmação (gesto, silêncio, escolha dela)."
    ),
    "ControllerRumbleOverride.policy": Nascimento(
        E_CONTRATO, "Override por peça: `None` = esta peça usa a seção global do perfil."
    ),
    "ControllerRumbleOverride.custom_mult": Nascimento(
        E_CONTRATO, "Ver `ControllerRumbleOverride.policy`."
    ),
    "ControllerRumbleOverride.motor_forte_pct": Nascimento(
        E_CONTRATO, "Ver `ControllerRumbleOverride.policy`."
    ),
    "ControllerRumbleOverride.motor_fraco_pct": Nascimento(
        E_CONTRATO, "Ver `ControllerRumbleOverride.policy`."
    ),
    "ControllerRumbleOverride.haptica_pct": Nascimento(
        NASCE_NO_LEITOR,
        "`None` vale `HAPTICA_PCT_PADRAO` (150): a háptica por áudio nasce "
        "ligada, pela palavra dela de 17/09.",
        dono="hefesto_dualsense4unix.profiles.schema:pct_da_haptica",
    ),
    "ControllerMicOverride.muted": Nascimento(
        E_CONTRATO,
        "Override por peça. O nascimento do microfone é global e já é NO AR — "
        "ver `ProfileMicConfig.muted`.",
    ),
    "ControllerMicOverride.volume": Nascimento(
        E_CONTRATO, "Override por peça; ver `ControllerMicOverride.muted`."
    ),
    "ControllerMicOverride.gain": Nascimento(
        E_CONTRATO, "Override por peça; ver `ProfileMicConfig.gain`."
    ),
    "ControllerSensoresOverride.giroscopio": Nascimento(
        NASCE_NO_LEITOR,
        "Aqui `None` NÃO é 'usa o global': é LIGADO, por "
        "D-AUDIO-E-GIRO-NASCEM-LIGADOS (25/08). Ausência de registro devolve "
        "os dois sensores de pé, e é o registro que o caminho quente consulta.",
        dono="hefesto_dualsense4unix.core.virtual_motion:EstadoDosSensores",
    ),
    "ControllerSensoresOverride.acelerometro": Nascimento(
        NASCE_NO_LEITOR,
        "Ver `ControllerSensoresOverride.giroscopio` — o *'ambos'* dela, cada "
        "um por si.",
        dono="hefesto_dualsense4unix.core.virtual_motion:EstadoDosSensores",
    ),
    "ControllerOverrides.leds": Nascimento(
        E_CONTRATO, "Seção ausente = esta peça herda a global do perfil (PERFIL-01)."
    ),
    "ControllerOverrides.triggers": Nascimento(
        E_CONTRATO, "Ver `ControllerOverrides.leds`."
    ),
    "ControllerOverrides.rumble": Nascimento(
        E_CONTRATO, "Ver `ControllerOverrides.leds`."
    ),
    "ControllerOverrides.speaker": Nascimento(
        E_CONTRATO, "Ver `ControllerOverrides.leds`."
    ),
    "ControllerOverrides.mic": Nascimento(E_CONTRATO, "Ver `ControllerOverrides.leds`."),
    "ControllerOverrides.sensores": Nascimento(
        E_CONTRATO, "Ver `ControllerOverrides.leds`."
    ),
    "ControllerOverrides.mascara": Nascimento(
        NASCE_NO_LEITOR,
        "A EXCEÇÃO nomeada desta classe: `None` = *'volte ao padrão'* "
        "(decisão dela, 09/09), e o padrão é `dualsense`. O controle não "
        "declarado perde a máscara própria em vez de mantê-la.",
        dono="hefesto_dualsense4unix.daemon.subsystems.external_mask:mascara_efetiva",
    ),
    "ControllerOverrides.movimento": Nascimento(
        E_CONTRATO,
        "Seção ausente = esta peça segue a mira do perfil, e a do perfil não "
        "existe por padrão. É ARRANJO, como o `Profile.movimento`: ligada sem o "
        "gesto dela no chip «Mira Virtual», a câmera andaria com o controle na "
        "mesa.",
    ),
    "Profile.name": Nascimento(E_OBRIGATORIO, "Não há perfil sem nome."),
    "Profile.version": Nascimento(
        E_CONTRATO, "`1` é o único valor que o `Literal` aceita."
    ),
    "Profile.match": Nascimento(E_OBRIGATORIO, "Não há perfil sem regra de casamento."),
    "Profile.priority": Nascimento(
        E_CONTRATO,
        "`0` é o piso da faixa e significa 'não disputa'. Um número de fábrica "
        "faria todo perfil novo ganhar de um dela sem ela ter pedido.",
    ),
    "Profile.triggers": Nascimento(
        E_SECAO, "A seção nasce inteira; quem decide os dois lados é `TriggersConfig`."
    ),
    "Profile.leds": Nascimento(
        E_SECAO, "A seção nasce inteira; quem decide é `LedsConfig`."
    ),
    "Profile.rumble": Nascimento(
        E_SECAO, "A seção nasce inteira; quem decide é `RumbleConfig`."
    ),
    "Profile.key_bindings": Nascimento(
        NASCE_NO_LEITOR,
        "`None` HERDA o mapa de fábrica inteiro — quem silencia o teclado é "
        "`{}`, que não é `None`. O contrato já distingue os dois.",
        dono="hefesto_dualsense4unix.core.keyboard_mappings:DEFAULT_BUTTON_BINDINGS",
    ),
    "Profile.button_actions": Nascimento(
        NASCE_NO_LEITOR,
        "`None` herda o de fábrica INTEIRO, derivado dos mapas do produto. "
        "Nenhum botão da tela nasce sem ação.",
        dono="hefesto_dualsense4unix.core.acoes_de_botao:padrao",  # (noqa-acento) símbolo real
    ),
    "Profile.remapeamento": Nascimento(
        NASCE_NO_LEITOR,
        "`None` = todos os botões passam intactos, que é o estado ÍNTEGRO da "
        "feature. Trocar botão de fábrica seria o oposto do pedido dela.",
        dono="hefesto_dualsense4unix.core.remapeamento_de_botao:resolver",
    ),
    "Profile.mouse": Nascimento(
        AGUARDA_A_PALAVRA_DELA,
        "A ÚNICA assimetria que sobra depois da triagem: o teclado emulado "
        "nasce LIGADO no daemon e o mouse nasce DESLIGADO "
        "(`mouse_emulation_enabled=False`), os dois interruptores vizinhos na "
        "mesma aba. Ligar o ponteiro por padrão muda o desktop dela.",
        falta="se a emulação de mouse entra no 'tudo ativado' ou fica no gesto dela",
    ),
    "Profile.teclado_emulado": Nascimento(
        NASCE_NO_LEITOR,
        "`None` = a flag global manda, e ela nasce `True`. O teclado emulado "
        "já nasce ligado.",
        dono="hefesto_dualsense4unix.daemon.lifecycle:DaemonConfig",
    ),
    "Profile.mic": Nascimento(
        NASCE_NO_LEITOR,
        "Seção ausente não cala ninguém: o microfone nasce no ar na chegada "
        "do controle. Ver `ProfileMicConfig.muted`.",
        dono="hefesto_dualsense4unix.integrations.plano_de_radio:microfone_nasce_ligado",
    ),
    "Profile.speaker": Nascimento(
        NASCE_NA_ADOCAO,
        "Seção ausente não toma a posse dos bytes — e não precisa: a adoção "
        "escreve volume e rota. Ver `ProfileSpeakerConfig.rota`.",
        dono="hefesto_dualsense4unix.core.backend_pydualsense:ROTA_PADRAO_DO_SOM",
    ),
    "Profile.mode": Nascimento(
        NASCE_NO_LEITOR,
        "Seção ausente = o modo vigente segue; a máscara e o caminho têm "
        "resolvedores próprios com padrão de fábrica.",
        dono="hefesto_dualsense4unix.daemon.subsystems.external_mask:mascara_efetiva",
    ),
    "Profile.suppress_desktop_emulation": Nascimento(
        NASCE_NO_ESQUEMA,
        "`False` é o estado LIGADO desta linha: o perfil NÃO suprime a "
        "emulação de desktop. O mudo aqui é `True`, e é por isso que o portão "
        "guarda o mudo de cada campo em vez de recusar `False` em bloco.",
    ),
    "Profile.controllers": Nascimento(
        E_CONTRATO,
        "`None` = perfil v1 puro, sem opinião por peça. Semear o mapa "
        "gravaria o MAC de aparelhos que a pessoa nem tem.",
    ),
    "Profile.ponte": Nascimento(
        E_CONTRATO,
        "`None` = **ainda não sei**, e é a distinção entre 'nunca tentei' e "
        "'tentei e funciona' que faz a escada de pontes parar.",
    ),
    "Profile.movimento": Nascimento(
        E_CONTRATO,
        "`None` = nenhuma tradução do giro. É ARRANJO, não feature: ligada sem "
        "pedido ela moveria a câmera de todo jogo quando o controle se mexe na "
        "mesa, e no caminho `uhid` — onde o giro nativo já chega — daria DOIS "
        "giros. Ver `ProfileMovimentoConfig`.",
    ),
    "ProfileMovimentoConfig.destino": Nascimento(
        E_CONTRATO,
        "`nenhum` guarda o arranjo e desliga a mira: é o estado que ela ESCOLHE "
        "para experimentar sem perder a calibração. A seção só existe por gesto "
        "dela; ver `Profile.movimento`.",
    ),
    "ProfileMovimentoConfig.sensibilidade": Nascimento(
        E_CONTRATO,
        "Parâmetro do arranjo, não a feature. O `ge=1` garante que nenhum "
        "nascimento seja mudo — a faixa 1-12 é a do cursor.",
    ),
    "ProfileMovimentoConfig.eixo_horizontal": Nascimento(
        E_CONTRATO,
        "Parâmetro: `yaw` é girar o controle como quem mira; `roll` é incliná-lo "
        "como volante. Os dois movem — nenhum é o silêncio.",
    ),
    "ProfileMovimentoConfig.inverter_horizontal": Nascimento(
        E_CONTRATO,
        "`False` é o sentido NATURAL do giro, não um desligado: a mira anda nos "
        "dois casos.",
    ),
    "ProfileMovimentoConfig.inverter_vertical": Nascimento(
        E_CONTRATO, "Ver `ProfileMovimentoConfig.inverter_horizontal`."
    ),
    "ProfileMovimentoConfig.zona_morta_graus_s": Nascimento(
        E_CONTRATO,
        "Parâmetro: 3°/s é a deriva do giro parado. Zero seria a mira andando "
        "sozinha com o controle na mesa.",
    ),
    "ProfileMovimentoConfig.teto_graus_s": Nascimento(
        E_CONTRATO,
        "Parâmetro: os graus/s que valem deflexão cheia. O `gt=0` e a trava "
        "acima da zona morta impedem um teto que nunca mova nada.",
    ),
    "ProfileMovimentoConfig.pixels_por_grau": Nascimento(
        E_CONTRATO, "Parâmetro do cursor (a Navegação) só; o `gt=0` impede o mudo."
    ),
    "ProfileMovimentoConfig.gatilho": Nascimento(
        NASCE_NO_LEITOR,
        "`None` = a mira fica SEMPRE ligada enquanto o destino não é `nenhum` — "
        "o vazio aqui é LIGADO. Um botão escolhido a restringe ao aperto.",
        dono="hefesto_dualsense4unix.daemon.subsystems.gamepad:aplicar_o_movimento",
    ),
    "ProfileMovimentoConfig.toque": Nascimento(
        E_CONTRATO,
        "`nenhum` = o touchpad é o do computador, como sempre foi "
        "(TOUCHPAD-DO-SISTEMA-01). Nascer em `zonas` tiraria o ponteiro dela; "
        "em `cursor`, trocaria o dono do cursor sem pedido.",
    ),
    "ProfileMovimentoConfig.acelerometro": Nascimento(
        E_CONTRATO,
        "`nenhum` = a inclinação não move analógico nenhum. Ligada sem o gesto "
        "dela, o personagem andaria sozinho com o controle torto na mão.",
    ),
}


__all__ = [
    "AGUARDA_A_PALAVRA_DELA",
    "A_ECONOMIA_EM_CADA_PECA",
    "BRILHO_DAS_LUZES_NA_ECONOMIA",
    "BRILHO_DA_BARRA_NA_ECONOMIA",
    "CONFIRMADA_POR_ESCOLHA",
    "CONFIRMADA_POR_GESTO",
    "CONFIRMADA_POR_SILENCIO",
    "E_CONTRATO",
    "E_OBRIGATORIO",
    "E_SECAO",
    "FATOR_DO_GATILHO_NA_ECONOMIA",
    "FORCAS_DO_GATILHO",
    "MODOS_DE_GATILHO_SEM_FORCA",
    "MODO_DE_NASCIMENTO_DO_GATILHO",
    "NASCE_NA_ADOCAO",
    "NASCE_NO_ESQUEMA",
    "NASCE_NO_LEITOR",
    "NASCIMENTO_DOS_CAMPOS",
    "PARAMS_DE_NASCIMENTO_DO_GATILHO",
    "PILHA_DAS_FEATURES",
    "POLITICA_DA_VIBRACAO_NA_ECONOMIA",
    "PRIORIDADE_MAXIMA",
    "PRIORIDADE_MINIMA",
    "ControllerMicOverride",
    "ControllerOverrides",
    "ControllerRumbleOverride",
    "ControllerSensoresOverride",
    "LedsConfig",
    "Match",
    "MatchAny",
    "MatchCriteria",
    "MatchManual",
    "Nascimento",
    "PecaDaEconomia",
    "PonteConfirmada",
    "Profile",
    "ProfileMicConfig",
    "ProfileMouseConfig",
    "ProfileSpeakerConfig",
    "RumbleConfig",
    "TriggerConfig",
    "TriggersConfig",
    "classes_de_jogo_conhecidas",
    "com_o_brilho_das_luzes_de",
    "controles_em_economia",
    "declaracao_da_economia",
    "e_endereco_de_jogo",
    "economia_da_declaracao",
    "economia_da_mesa",
    "economia_vale",
    "gatilho_na_economia",
    "gatilhos_do_perfil_na_economia",
    "gatilhos_na_economia",
    "leds_do_perfil_na_economia",
    "leds_na_economia",
    "mesa_em_economia",
    "normalizar_gamepad_flavor",
    "origem_da_economia",
    "perfil_declara_modo_de_jogo",
    "perfil_e_regra_de_jogo",
    "registrar_classes_de_jogo",
    "registrar_declaracao_da_mesa",
    "resolver_teclado_emulado",
    "vibracao_na_economia",
]


HAPTICA_PCT_PADRAO = 150

HAPTICA_PCT_MAX = 200


def pct_da_haptica(rumble: ControllerRumbleOverride | None) -> int:
    """O ganho da háptica por áudio desta peça, em % — o padrão sem opinião."""
    if rumble is None or rumble.haptica_pct is None:
        return HAPTICA_PCT_PADRAO
    return int(rumble.haptica_pct)


def pcts_da_haptica_dos_controles(
    controllers: dict[str, ControllerOverrides] | None,
) -> dict[str, int]:
    """``{uniq: haptica_pct}`` de toda peça do perfil que ESCREVEU o campo."""
    fora: dict[str, int] = {}
    for uniq, cfg in (controllers or {}).items():
        rumble = getattr(cfg, "rumble", None)
        if rumble is None or "haptica_pct" not in rumble.model_fields_set:
            continue
        fora[uniq] = pct_da_haptica(rumble)
    return fora
