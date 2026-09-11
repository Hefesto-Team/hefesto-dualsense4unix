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

#: A máscara do gamepad virtual, na forma FECHADA que o esquema de perfil
#: aceita. É a única lista de máscaras digitada nesta casa, e ela é digitada
#: porque tem de ser: `Literal` é resolvido pelo verificador de tipos, e um
#: `frozenset` calculado do `uinput_gamepad.FLAVORS` não vira anotação.
#:
#: Por ser digitada, ela DIVERGE calada — e já divergiu: de 07/09/2026 até
#: esta linha o esquema só conhecia `dualsense` e `xbox`, e um perfil que
#: pedisse a máscara nova era recusado pelo pydantic com a máscara já viva no
#: catálogo. Quem acrescentar um sabor ao `FLAVORS` acrescenta AQUI, e o portão
#: `tests/unit/test_a_mascara_nintendo_pro_atravessa_a_casa.py` compara os
#: `get_args` deste alias com o `external_mask.mascaras_validas()` — nos DOIS
#: sentidos, para que sobrar aqui também reprove.
MascaraDeGamepad = Literal["dualsense", "xbox", "nintendo"]

#: Teto do multiplicador de rumble da política "custom". Acima de 1.0 AMPLIFICA o
#: que o jogo pediu — é a razão de existir da faixa (BUG-RUMBLE-CUSTOM-MULT-CAP-01).
#:
#: HARM-19: mora aqui, num dono só, porque a faixa já valeu 2.0 no esquema, 1.0 no
#: handler `rumble.policy_custom` e 200% no slider da GUI ao mesmo tempo — de 101%
#: em diante a usuária levava um erro de validação que a aba reportava como
#: "daemon offline?". Quem mudar o teto muda AQUI e os três seguem juntos.
#:
#: NOTA DATADA — 11/08/2026: o teto foi a 1.0 de manhã (nota SATURA-01) e
#: DECISÃO DELA o devolveu a 2.0 no mesmo dia, com o preço na mesa. As duas
#: metades ficam registradas porque a medição de baixo continua verdadeira; o
#: que mudou foi o que se aceita pagar por ela.
#:
#: **O que ela decidiu:** o deslizador "Intensidade global" vai até 200, e este
#: teto o acompanha. O tooltip do deslizador já prometia *"acima de 100 sai mais
#: forte"* desde sempre, contra um teto de 100 que impedia a usuária de chegar
#: lá. A amplificação está MEDIDA no aparelho (11/08): um report com
#: ``common[2]=200``, daemon parado, fez o motor obedecer, e ela confirmou de
#: olho.
#:
#: **ESTE TETO NÃO É O DO BOTÃO "Máximo", e a diferença é deliberada.** O botão
#: vale **1,5** (`daemon.subsystems.rumble.RUMBLE_POLICY_MULT`, que é o dono da
#: escada); este 2.0 é o fim do curso do deslizador. A divisão de papéis:
#:
#: * os quatro botões são **presets seguros** — quem só quer clicar não pode
#:   cair numa armadilha;
#: * o deslizador é o **ajuste livre** de quem quer ir além e aceita o preço,
#:   que está escrito no tooltip.
#:
#: **O preço, medido** (é a nota SATURA-01, de 11/08/2026, e ela continua
#: valendo — foi por causa dela que o BOTÃO parou em 1,5). Rodando a conta exata
#: do produto — `max(0, min(255, round(bruto * mult)))` — sobre os 256 valores
#: que o jogo pode pedir:
#:
#:     mult 1.0 → nenhum valor satura
#:     mult 1.5 → satura a partir de 170: 33% da faixa vira 255
#:     mult 2.0 → satura a partir de 128: METADE da faixa vira 255
#:
#: A 2.0 o jogo manda 128, 180 e 255 e o controle recebe 255 nas três — naquela
#: metade a variação da vibração some, e o que se sente é força CONSTANTE, não
#: força maior. Foi o que ela relatou em 10/08: *"vibra muito mais do que o
#: normal a ponto de não parar"*. Amplificar sem nuance não é amplificar: é
#: achatar.
#:
#: **O que continua por fazer:** amplificar SEM achatar exige comprimir (uma
#: curva) em vez de cortar. Quem for fazer isso mexe AQUI e na tabela da escada,
#: com a medição na mão.
#:
#: HARM-19 continua valendo: o teto tem um dono só. O handler
#: `rumble.policy_custom`, o `RumbleDraft.custom_mult` da GUI e o slider do
#: glade derivam deste número — e há portão (`test_rumble_mult_um_dono.py`) que
#: reprova quem escrever o número à mão de novo.
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
    # A PROCEDÊNCIA DA COR — decisão de produto de 08/09/2026: *"o override de
    # cor por MAC ganha PROCEDÊNCIA: para qual número ele foi escolhido. Quando
    # o número daquele aparelho muda, a cor gravada é FÓSSIL e sai sozinha,
    # caindo de volta na paleta automática."*
    #
    # O DEFEITO QUE ELE FECHA, medido na mesa dela: o override é por MAC e
    # CONGELADO; o número do jogador é de SESSÃO e muda com a ordem de conexão.
    # Os ranks 2 e 4 dela guardavam as cores dos slots 1 e 2 — o número de
    # outro dia fossilizado no arquivo — e dois DualSense acendiam o MESMO
    # `#0000FF`. Sem este campo o resolvedor tinha de ADIVINHAR qual repetição
    # era fóssil e qual era o "pinta os quatro de verde" dela, e o palpite
    # matou o broadcast (`core/led_control.py::cores_sem_colisao`).
    #
    # SÓ TEM SENTIDO DENTRO DE UM OVERRIDE POR CONTROLE (`ControllerOverrides.
    # leds`): na seção GLOBAL do perfil não há "qual número", a cor é de todos.
    # É aceito pelo schema nos dois lugares (reuso do modelo) e ignorado no
    # global, exatamente como o `auto_player_colors` acima é ignorado aqui.
    #
    # `None` = sem procedência gravada. É o valor de TODO perfil escrito antes
    # deste dia, e o resolvedor o trata como `LEGADO`: volta a provar fóssil
    # pela forma (a cor é a do número de OUTRO da mesa), que é o melhor que se
    # pode fazer sem o dado. Aditivo, sem migração; ATENÇÃO downgrade, mesma
    # nota do `auto_player_colors` (`extra="forbid"`).
    lightbar_para_o_numero: int | None = None

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
    nem na GUI, nem no draft, nem no perfil.

    MIC-DA-MESA-ELEICAO-01 (01/09/2026) — O QUE ESTE CAMPO LIGA MUDOU. Ligado
    (default do daemon), apertar o botão do microfone ELEGE o canal de captura
    daquele controle como microfone padrão do sistema, e acende o LED dele
    quando a eleição é conferida. Ele não muta mais nada: o texto anterior
    dizia *"alterna o mute do microfone padrão do sistema"*, e essa é
    exatamente a coisa que ela mandou parar de fazer — *"mexendo com ambos os
    canais de áudio é péssimo"*.

    Desligado, o botão não mexe no áudio do sistema — é o que se quer num
    perfil de gravação/live, em que o mute é do OBS/da mesa e um toque
    acidental no controle não pode trocar a captura.

    NÃO confundir com o mudo de microfone do FIRMWARE (`common[9]` do report
    de saída): esse é do kernel e o hefesto deixou de disputá-lo
    (AUDIO-OWNER-01).

    O VOLUME E O MUDO (MIC-VOLUME-01, 16/08/2026)
    ----------------------------------------------
    Pedido dela, olhando a aba Status: *"dá espaço a um slider de microfone pra
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
    microfone. Isso caducou, e foi ELA quem o derrubou: *"informação de
    microfone e som, touch, acelerômetro, giroscópio e afins. cara, temos que
    salvar isso no perfil sempre"* — e, sobre o contrato antigo: *"isso é
    informação antiga. o sistema de perfis não funcionava, mas acho que não vem
    ao caso, até pq na época não tinhamos microfone dentro do sistema de
    perfis."* Quem aplica é `ProfileManager.apply_mic`.

    **A EXCEÇÃO NOMEADA, MIC-GRAVACAO-01.** Os dois campos NÃO custam a mesma
    coisa, e por isso não atravessam pelos mesmos caminhos:

    - `volume` aplica em TODA ativação (respeitada a trava manual de áudio):
      ele é o ganho da fonte no PipeWire e não apaga luz nenhuma;
    - `muted` só aplica em troca EXPLÍCITA de perfil (`origin="manual"` — ela
      escolhendo na GUI/CLI ou no PS+D-pad). Ele é o mudo do FIRMWARE, o mesmo
      que apaga o LED vermelho, e há decisão medida proibindo o perfil de
      apagá-lo como COLATERAL (AUDIT-FINDING-PROFILE-MIC-LED-RESET-01). Sem
      essa separação, abrir um jogo durante uma gravação roubaria o mudo dela:
      o perfil do jogo limpa a trava manual ao entrar.

    **`volume` é do CAMINHO, não do firmware.** Ele é o volume da fonte de
    captura no sistema (o source do PipeWire), e por isso funciona igual no cabo
    e no rádio — que é exatamente o "independente de saber se tá via bt ou via
    cabo" do pedido dela. O DualSense não expõe um registrador de ganho de
    microfone; o que existe no firmware é o MUDO, e é o `muted` que fala com ele.

    A faixa é 0-100 (por cento), diferente do `volume` do alto-falante, que é
    0-255 porque escreve um byte do report. Aqui o número é de sistema, e usar a
    escala do report seria pedir que ela pensasse em bytes.
    """

    model_config = ConfigDict(extra="forbid")

    button_toggles_system: bool
    #: Volume da captura, em por cento. `None` = o perfil não tem opinião e
    #: ativá-lo não toca no volume do microfone; com número, ativar APLICA.
    volume: int | None = Field(default=None, ge=0, le=100)
    #: Mudo do microfone. `None` = sem opinião. Ver o bloco acima: quem
    #: responde por ele é o mudo do FIRMWARE, o mesmo que apaga o LED vermelho
    #: — e por isso ele só atravessa a troca EXPLÍCITA de perfil
    #: (MIC-GRAVACAO-01).
    muted: bool | None = None


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
    #: A FONTE do nó de som deste controle — ``"mix"`` (todo o som do PC cai
    #: aqui também, o *«HDMI completo»* dela) ou ``"sfx"`` (o nó fica livre para
    #: a corrente que o jogo mandar). Pedido dela, 08/09/2026: *"os somns seja
    #: hdmi completo seja o canal do sfx caindo pra cada controle"*.
    #: <!-- noqa-acento: citação literal dela -->
    #:
    #: **ADITIVO e sem bump de versão**, como a ``rota``: perfil antigo carrega
    #: com ``None``, que é **não mexer** — o nó daquele controle segue o padrão
    #: da casa, que é ``sfx`` por decisão dela
    #: (``D-0809-NO-CABO-O-PADRAO-DO-SOM-E-SFX``, *"concordo com as 5"*). Com
    #: ``mix`` por padrão o controle viraria a saída de todo o som do PC
    #: sozinho, que é a regra que esta casa já recusou.
    #:
    #: É CAMADA 1 (o PipeWire), e a ``rota`` é a CAMADA 2 (o byte do firmware).
    #: São campos diferentes de propósito: a fonte diz **o que entra no nó**, a
    #: rota diz **por onde o plástico toca o que saiu dele** — o fone, o
    #: alto-falante, ou os dois. Fundir os dois num só tiraria dela a escolha
    #: do fone, que ela nomeou com todas as letras.
    #:
    #: TIPO FECHADO: um valor que ``rota_do_no`` não saiba tratar não chega ao
    #: disco. Os dois nomes têm UM dono
    #: (``integrations.alto_falante_bt.FONTE_MIX`` / ``FONTE_SFX``), e o
    #: ``Literal`` daqui é conferido contra ele por
    #: ``tests/unit/test_o_som_por_controle_cai_em_cada_um.py``.
    fonte: Literal["mix", "sfx"] | None = None

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
        if not isinstance(dados, dict):
            return dados
        # A `fonte` entra na MESMA regra, e pela mesma razão: um hefesto de
        # antes de 09/09/2026 tem `extra="forbid"` e RECUSA o perfil inteiro ao
        # ver a chave nova. Gravá-la como `null` em todo perfil salvo faria
        # "voltar uma versão" virar "todos os perfis com som quebrados".
        for sem_opiniao in ("rota", "fonte"):
            if dados.get(sem_opiniao) is None:
                dados.pop(sem_opiniao, None)
        return dados


class ProfileModeConfig(BaseModel):
    """Seção opcional de MODO do sistema por perfil (FEAT-PROFILE-MODE-01).

    O perfil do JOGO declara como o controle deve se comportar quando ele está
    em foco — as features passam a COEXISTIR porque o contexto decide, sem
    toggles globais brigando entre si:

    - ``kind="native"`` — release total: o jogo usa os gatilhos adaptativos
      NATIVOS da Sony (Sackboy & cia); o hefesto solta o controle.
    - ``kind="gamepad"`` — gamepad virtual com a máscara `gamepad_flavor`
      (prompts PlayStation ou Xbox). **Cada controle físico é um jogador**, e
      isso não é ajustável: quem liga dois controles quer dois jogadores, não
      dois comandos para o mesmo personagem.
    - ``kind="desktop"`` — declaração explícita de app de desktop: desliga
      gamepad/nativo/co-op vindos de perfil (e também os expirados do lock).

    Perfis SEM a seção não têm opinião: liberam apenas o modo que outro PERFIL
    tinha ligado (gesto manual da usuária é respeitado — mesma semântica do
    `suppress_desktop_emulation`). Toggles manuais recentes vencem por
    ``MANUAL_PROFILE_LOCK_SEC`` (30s), como no `mouse`.
    """

    model_config = ConfigDict(extra="forbid")

    kind: Literal["desktop", "gamepad", "native"]
    gamepad_flavor: MascaraDeGamepad | None = None


#: PONTE-CONFIRMADA-01 (19/08/2026) — COMO a ponte foi confirmada.
#:
#: São os caminhos que ela fixou em 19/08/2026: o produto tenta em ordem e ela
#: confirma UMA vez, com um gesto no controle, qual pegou (``gesto``); ou ela já
#: sabe e escolhe direto na aba de perfil (``escolha_dela``). O automático é o
#: caminho; a escolha dela é o atalho — e os dois carimbam o MESMO campo, porque
#: a pergunta que o carimbo responde é a mesma ("esta ponte foi confirmada?").
#:
#: Guardar QUAL deles é o que separa "o produto adivinhou e ela confirmou" de
#: "ela mandou" no dia em que a escada errar — sem isso, o journal é o único
#: lugar onde essa diferença existe, e o journal roda.
#:
#: OS TRÊS NOMES SÃO OS DE ``integrations/ponte_escada.py`` (``POR_GESTO``,
#: ``POR_SILENCIO``, ``POR_ESCOLHA_DELA``), e a coincidência é o ponto: quem
#: DECIDE que a ponte pegou é a escada, quem GUARDA é este campo, e um esquema
#: que não soubesse representar uma das confirmações que o produto já produz
#: seria um esquema obrigando a uma segunda gaveta para o mesmo fato. O
#: ``silencio`` é a confirmação mais barata que existe — ela jogou e não
#: reclamou — e é justamente a que não pode ficar de fora.
#:
#: Anotados como `Literal` (e não `str`) de propósito: é o que permite usá-los
#: como default do campo sem que o verificador de tipos perca a faixa fechada.
CONFIRMADA_POR_GESTO: Literal["gesto"] = "gesto"
CONFIRMADA_POR_SILENCIO: Literal["silencio"] = "silencio"
CONFIRMADA_POR_ESCOLHA: Literal["escolha_dela"] = "escolha_dela"


def _agora_em_iso() -> str:
    """Instante atual em ISO-8601, segundo a segundo, com fuso.

    Local e com offset (`astimezone()`), não UTC cru: quem lê o carimbo é ela,
    olhando para *"quando foi que eu confirmei isto?"*, e um `Z` obriga a
    pessoa a fazer a conta de cabeça. O offset preserva a ordenação e o
    `fromisoformat` de volta.
    """
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
    dela a cada degrau (R-04, medido em 23/07 — recriar o vpad com o jogo aberto
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
    perfis do disco dela passam a dizer. Um perfil que já traz
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

    #: Os três termos da ponte, com os MESMOS nomes de ``ProfileModeConfig`` e
    #: da allowlist — quem lê os dois lado a lado compara campo com campo. É o
    #: mesmo trio do ``ponte_escada.Ponte``, que chama a máscara de ``mascara``;
    #: aqui ela se chama ``gamepad_flavor`` porque o vizinho de comparação é o
    #: ``mode`` do próprio perfil, e nome igual é o que torna a comparação
    #: campo a campo (``mesma_ponte``) legível em vez de uma tradução.
    kind: Literal["desktop", "gamepad", "native"]
    gamepad_flavor: MascaraDeGamepad | None = None
    #: O terceiro termo: o jogo estava na allowlist do Steam Input
    #: (``steam_input_apps.txt``) quando a ponte foi confirmada.
    steam_input: bool = False
    confirmada_em: str = Field(default_factory=_agora_em_iso)
    confirmada_por: Literal["gesto", "silencio", "escolha_dela"] = (
        CONFIRMADA_POR_GESTO
    )

    @field_validator("confirmada_em")
    @classmethod
    def _e_uma_data_de_verdade(cls, value: str) -> str:
        """Data ilegível é pior que data ausente: ela PARECE conhecimento.

        A borda recusa, como o ``custom_mult`` e o ``volume`` do alto-falante:
        o arquivo inválido morre no load, com mensagem que explica, em vez de
        virar uma tela mostrando "confirmada em nunca".
        """
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
        """Máscara sem gamepad virtual é uma ponte que não existe.

        ``ProfileModeConfig`` aceita o par incoerente por história (perfis já
        gravados o trazem, e rejeitá-los agora fecharia arquivo dela que abre
        hoje). Aqui não há história a preservar — o campo nasce neste commit e
        só o produto o escreve —, então a incoerência morre na borda em vez de
        virar uma escada perguntando "a máscara do modo nativo é dualsense?".
        """
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
        """A ponte de HOJE é a que foi confirmada?

        Os três termos comparados de uma vez, que é a única comparação honesta:
        ``mode`` ausente é "sem opinião", e sem opinião nunca é igual a uma
        ponte confirmada.
        """
        if mode is None:
            return False
        return (
            self.kind == mode.kind
            and self.gamepad_flavor == (mode.gamepad_flavor if mode.kind == "gamepad" else None)
            and self.steam_input is bool(na_allowlist)
        )


#: O QUE UMA BARRA DE MOTOR VALE QUANDO NINGUÉM A ARRASTOU — 100 %, ou seja,
#: fator 1,0: o degrau da coluna chega ao motor inteiro. É a conta de hoje, e o
#: número mora aqui num dono só para que "sem opinião" e "escolheu 100" sejam
#: byte-idênticos no aparelho (só o disco os distingue: um grava, o outro não).
MOTOR_PCT_PADRAO = 100

#: Teto da barra de motor. **Não é o ``RUMBLE_CUSTOM_MULT_MAX``, e a diferença
#: é o ponto inteiro da decisão dela de 04/09/2026:** a barra é o SEGUNDO fator,
#: e quem amplifica é o degrau (``Máximo`` = 150 %, ``custom`` até 200 %). Uma
#: barra acima de 100 amplificaria de novo, e a mesma peça teria duas portas
#: para o mesmo estouro — que é o defeito HARM-19 pela outra porta.
MOTOR_PCT_MAX = 100


def pcts_dos_motores(rumble: ControllerRumbleOverride | None) -> tuple[int, int]:
    """``(forte_pct, fraco_pct)`` desta peça — ``(100, 100)`` sem opinião.

    O ÚNICO lugar que resolve o "campo não escrito = sem opinião" das duas
    barras. Quem multiplicar (``daemon.subsystems.gamepad``) lê daqui em vez de
    repetir o ``or 100``: dois defaults digitados divergem no primeiro dia em
    que um deles mudar, e a casa já pagou por isso (HARM-19).
    """
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
    """``{uniq: (forte_pct, fraco_pct)}`` do perfil — só quem TEM opinião.

    Espelho de ``manager._controllers_to_rumble_scales``, campo por campo, e
    pela mesma razão de desenho: a peça sem opinião **não entra no mapa**, para
    que o consumidor não precise distinguir "escreveu 100" de "não escreveu".

    A diferença de fundo, e ela é a decisão dela de 04/09/2026: a escala do
    irmão é RELATIVA ao degrau global (``mult_da_unidade / mult_global``, e por
    isso ela pula sob um global em ``auto``); esta é um SEGUNDO FATOR que
    *compõe* com o degrau — ``efetivo(motor) = degrau x barra(motor)`` —, então
    não há denominador para se mover, e ela vale com o global em ``auto``
    também.
    """
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
            continue  # 100/100 é "sem opinião" no aparelho — não ocupa o mapa
        fora[uniq] = par
    return fora


class ControllerRumbleOverride(BaseModel):
    """A INTENSIDADE da vibração de UMA unidade física (POR-UNIDADE-01, 10/08).

    Subconjunto DELIBERADO de ``RumbleConfig``: ``policy`` e ``custom_mult``,
    os dois campos que descrevem *o quanto* aquela peça de plástico vibra. É o
    que ela pediu em 10/08/2026 — "uma guia específica do perfil X pro controle
    branco e outra pro mesmo perfil pro controle preto".

    **E, desde 04/09/2026, as DUAS BARRAS DE MOTOR** — ``motor_forte_pct`` e
    ``motor_fraco_pct``. A decisão é dela, e veio FORA das três opções que eu
    ofereci (eu perguntei se a barra mandava o par ``rumble.set`` agora ou
    virava leitura; as duas perguntas estavam erradas):

        *"os slcers do botão esquerdo e direito (forte e fraco) se multiplicam*
        *(interagem com os botões economia, moderado, máximo, se eu tiver 150%*
        *do perfil de vibração e as duas linhas estiverem 100 entao a vibração*
        *dos 2 será 150%, mas se so a do motor fraco tiver 100 e a outrqa 50%*
        *então será 150 em um e 75% no outro entende?"*
        <!-- noqa-acento: citação literal dela -->

    A barra **não é um comando: é POLÍTICA**, e por isso mora no perfil ao lado
    do degrau, e não no ``DaemonConfig``. ``efetivo(motor) = degrau x barra``,
    e quem faz a conta é ``daemon.subsystems.gamepad``, num lugar só.

    ``rumble.set {weak, strong}`` continua sendo o comando de tremer AGORA, e a
    barra não o chama — são camadas diferentes, pela mesma razão que separa
    ``mic.set`` de ``mic.volume.set``.

    ``passthrough`` FICA DE FORA, e a ausência é a entrega. Ele não descreve a
    peça: descreve *quem manda na vibração agora* — soltar o rumble que a GUI
    TRAVOU (``DaemonConfig.rumble_active``, um valor só para o daemon inteiro)
    de volta para o jogo. Duas unidades pedindo passthrough diferente no mesmo
    perfil não têm resposta honesta enquanto a trava for uma só, e a casa já
    recusa campo aceito-e-ignorado na BORDA do esquema em vez de deixá-lo
    virar comportamento errado silencioso meses depois (ver ``custom_mult``
    fora de ``policy='custom'``, logo abaixo). ``extra="forbid"`` faz a recusa:
    um override com ``passthrough`` é rejeitado no load, com mensagem.

    ``auto`` também fica de fora, e pela mesma disciplina — mas por uma
    MEDIÇÃO, não por uma opinião. O ``auto`` resolve o multiplicador pela
    BATERIA, e quem a lê é ``core.rumble._effective_mult``, a partir do
    ``store.snapshot().controller`` — o controle PRIMÁRIO, um só. Aceitar
    ``auto`` por unidade guardaria no perfil dela uma promessa que o caminho
    do rumble não sabe cumprir: as duas peças escalariam pela bateria da
    mesma. Quando o dia do ``auto`` por peça chegar, o que falta é a bateria
    POR UNIQ chegando ao ponto de escala — não este campo.

    Campo não escrito = sem opinião: o merge POR CAMPO herda o global do
    perfil, exatamente como em ``leds``/``triggers``.
    """

    model_config = ConfigDict(extra="forbid")

    policy: Literal["economia", "balanceado", "max", "custom"] | None = None
    custom_mult: float | None = None

    #: A BARRA DO MOTOR FORTE (``strong``, o grande) desta peça, 0-100.
    #: ``None`` = sem opinião, que vale ``MOTOR_PCT_PADRAO``. Segundo fator: ele
    #: MULTIPLICA o degrau da coluna, nunca o substitui.
    motor_forte_pct: int | None = None

    #: A BARRA DO MOTOR FRACO (``weak``, o pequeno) desta peça, 0-100. Mesmo
    #: contrato do irmão acima. Os dois são independentes de propósito — é
    #: exatamente o caso dela: *"se so a do motor fraco tiver 100 e a outrqa
    #: 50% então será 150 em um e 75% no outro"*. <!-- noqa-acento: citação literal dela -->
    motor_fraco_pct: int | None = None

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
        """A faixa das barras é 0-100, e a recusa EXPLICA por que não passa de 100.

        Na BORDA, e não no consumidor, pela mesma disciplina do ``custom_mult``:
        o arquivo inválido morre no load com mensagem, em vez de virar
        comportamento errado silencioso meses depois. ``0`` é aceito de
        propósito — "este motor não treme neste perfil" é uma escolha, e é a
        mesma que o irmão ``set_rumble_scales`` já aceita com fator ``0``.
        """
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


class ControllerMicOverride(BaseModel):
    """O MICROFONE de UMA unidade física (MIC-QUINTO-AJUSTE-01, 03/09/2026).

    Decisão dela, 03/09/2026 — o microfone vira o QUINTO ajuste por controle:
    é o `Virtual` que faz o mic soar igual no cabo e no rádio, ou seja, é o
    ajuste que faz o CANAL daquele controle funcionar; e com
    ``CANAL-POR-CONTROLE-01`` — *"4 controles os 4 tem que ter canais de
    entrada unico pra cada qual"* (noqa-acento: citação literal dela) —
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
    (``core/backend_pydualsense.py:4611``). O alvo está no parâmetro em todo
    degrau, e é o que separa *"guardei"* de *"chegou ao aparelho"*.

    Vale para ele a MESMA exceção MIC-GRAVACAO-01 do campo global: o ``muted``
    é o mudo do FIRMWARE, o mesmo que apaga o LED vermelho, e por isso só
    atravessa a troca EXPLÍCITA de perfil (``origin="manual"``). Quem aplica a
    guarda é ``ProfileManager.apply_mic``, reusado VERBATIM — não há segunda
    cópia da regra aqui.

    O QUE FICA DE FORA, e cada um por uma MEDIÇÃO
    ----------------------------------------------
    - ``volume``. **FATO SUBSTITUÍDO EM 03/09/2026** — esta linha dizia que o
      applier *"não chama"* a primitiva por peça, e isso deixou de ser verdade
      no mesmo dia. ``Daemon.apply_profile_mic`` resolve a fonte com
      ``audio_control.fonte_de_captura_do_uniq(uniq)`` quando há ``uniq``, e
      **não cai** para a rota global quando ele não resolve — sem fonte daquele
      controle ninguém escreve e ninguém diz "aplicado".
      ``fonte_de_captura_do_controle()``, que devolve a PRIMEIRA fonte da
      lista, ficou sendo o que a seção GLOBAL usa, e ali está certo: o global
      não tem dono.

      **O QUE SEGURA O CAMPO HOJE NÃO É MEDIÇÃO, É DECISÃO.** Abrir a borda
      muda o que o perfil dela aceita no disco, e com dois DualSense no cabo há
      DUAS placas de som (MIC-DA-MESA-CHEIA-01, 20/08/2026) — quem decide se
      cada peça passa a guardar o seu ganho é ela. Enquanto não disser, a
      recusa fica, e a razão na mensagem é esta.
    - ``button_toggles_system``. O interruptor é UM por máquina:
      ``hotkey.mic_button_loop`` lê ``daemon.config.mic_button_toggles_system``
      (``daemon/subsystems/hotkey.py:1173``) e não consulta ``uniq`` nenhum.
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

    #: Mudo do microfone DESTA peça. `None` = sem opinião. Só atravessa a troca
    #: EXPLÍCITA de perfil (MIC-GRAVACAO-01) — a guarda mora em
    #: `ProfileManager.apply_mic`.
    muted: bool | None = None

    #: GANHO DE CAPTURA DESTA PEÇA, 0..100. `None` = sem opinião.
    #:
    #: ABERTO EM 03/09/2026, E A PALAVRA É DELA. O campo esteve travado o dia
    #: inteiro por uma razão que NÃO era técnica: a costura por unidade ficou
    #: pronta pela manhã (`apply_profile_mic` resolve a fonte com
    #: `fonte_de_captura_do_uniq(uniq)` e NÃO cai para a global quando o uniq
    #: não resolve — cair seria escrever no microfone do vizinho). O que
    #: faltava era a decisão de mudar o que o perfil dela aceita no disco.
    #:
    #: ELA MANDOU, com estas palavras: *"manda a ver em tudo que falta por
    #: favor"* — depois de ter dito, no mesmo dia, o que o produto tem de
    #: entregar: *"4 controles funcionarem no mesmo modo com configs
    #: diferentes"*. Com dois DualSense no cabo há DUAS placas de som
    #: (MIC-DA-MESA-CHEIA-01, 20/08/2026), e o ganho de cada uma é justamente
    #: uma config que difere por peça.
    #:
    #: A FAIXA É A DA SEÇÃO GLOBAL, e é lida dela, não digitada aqui: uma
    #: segunda definição de 0..100 envelheceria no dia em que a primeira
    #: mudasse.
    volume: int | None = Field(default=None, ge=0, le=100)

    @model_validator(mode="before")
    @classmethod
    def _o_que_ainda_nao_tem_caminho_por_peca(cls, data: Any) -> Any:
        """Mensagem que EXPLICA a recusa em vez do ``extra_forbidden`` cru."""
        if not isinstance(data, dict):
            return data
        # O `volume` SAIU DAQUI EM 03/09/2026 — ela mandou abrir. A recusa que
        # morava nesta linha dizia, com todas as letras, que *"o que falta
        # agora é a PALAVRA DELA, não o caminho"*. A palavra veio.
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

    SENSOR-DE-VERDADE-01 (04/09/2026). Decisão dela, depois de eu recomendar a
    saída barata (virar leitura, um selo "no ar / parado", zero linha nova):

        *"ele tem que funcionar de verdade. ambos independente do modo e da
        mascara."* <!-- noqa-acento: citação literal dela -->

    **DOIS campos e não um**, porque ela disse *"ambos"* e cada um por si —
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

    #: ``False`` desliga o giroscópio desta peça. ``None`` = sem opinião (ligado).
    giroscopio: bool | None = None

    #: ``False`` desliga o acelerômetro desta peça. Independente do irmão acima
    #: de propósito — é o *"ambos"* dela, cada um por si.
    acelerometro: bool | None = None


class ControllerOverrides(BaseModel):
    """Overrides POR CONTROLE dentro do perfil (PERFIL-02, 2026-07-16).

    Campo ``None`` = sem opinião: o controle herda a seção GLOBAL do perfil
    (merge POR CAMPO na aplicação, PERFIL-01 — override parcial nunca apaga a
    cor global no replug).

    **A EXCEÇÃO É UMA, E É DECISÃO DELA (09/09/2026):** em ``mascara``, ``None``
    quer dizer *"volte ao padrão"* — *"Default é Hefesto dualsense padrão"*. O
    controle que o perfil não declara **perde** a máscara própria que estivesse
    valendo, em vez de mantê-la. A diferença existe porque a máscara é a única
    seção cujo estado anterior sobreviveria FORA do perfil: as outras seis são
    reaplicadas por inteiro a cada ativação, e a máscara morava num registro
    próprio que atravessava a troca. Ver o campo, lá embaixo, e
    ``manager.apply_controller_mascaras``, que mede o que a devolução custa.

    O ALVO É TUDO — DECISÃO DELA, 02/09/2026
    -----------------------------------------
    *"acelerômetro, giroscópio, e todas as demais features. **é tudo mesmo**"*
    — e ela marcou junto: teclas e ações de botão, mouse e teclado emulado,
    modo (Hefesto/Xbox/Steam) e microfone.

    **O QUE ISSO DERRUBA:** esta docstring trazia uma lista de seções *"FORA
    porque NÃO TÊM RESPOSTA HONESTA por unidade"*. Essa lista caiu — a resposta
    dela é que tem resposta, e é por controle. As medições que sustentavam a
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
    - ``mic``, desde MIC-QUINTO-AJUSTE-01 (03/09/2026, decisão dela):
      ``manager.apply_controller_mics`` chama ``apply_mic(uniq=...)`` →
      ``apply_profile_mic(uniq=...)`` → ``set_microphone_mute(uniq=...)``. É um
      subconjunto — só o ``muted`` —, e ``ControllerMicOverride`` diz por
      medição o que ficou de fora e o que cada um espera;
    - ``mascara``, desde MASCARA-NO-PERFIL-01 (08/09/2026, decisão dela — *"pode
      entrar sim"*): ``manager.apply_controller_mascaras`` escreve a máscara
      daquela peça no registro que ``external_mask.mascara_efetiva`` consulta na
      criação de cada gamepad virtual, e é o perfil que passa a mandar (ver o
      item 3 da fila abaixo, que dizia o contrário até 08/09).

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
         que o perfil dela aceita no disco. Há teste que reprova no dia em que
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
       (decisão dela, 10/08/2026): existe um só, e o daemon não pode estar em
       dois ao mesmo tempo. **A MÁSCARA do gamepad NÃO está nessa frase** —
       ela ficou larga demais e ela a reescreveu em 15/08/2026
       (MÁSCARA-POR-JOGADOR-01): o co-op cria um gamepad virtual por controle e
       cada um carrega o próprio ``flavor``, então a máscara **é do jogador**,
       com a do jogo como padrão herdado.

       **A MÁSCARA SAIU DESTA FILA EM 08/09/2026 — decisão dela, MASCARA-NO-
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
       (decisão dela): a devolução apaga a entrada, mas só cai o vpad de quem
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

    A CONTRADIÇÃO ABERTA, E ELA É DELA — não se fecha escrevendo código
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

    # SÃO SETE, e a tela oferece nove. O que falta, e o CAMINHO que cada um
    # espera antes de poder entrar, está na fila da docstring acima — ordenada
    # por custo. O `mic` entrou em 03/09/2026 pelo `muted`, que é o campo dele
    # cuja escada carrega o `uniq` em todo degrau; o `sensores` entrou em
    # 04/09/2026, quando o interruptor que ele prometia passou a existir; a
    # `mascara` entrou em 08/09/2026, por decisão dela — e é a primeira que não
    # é uma SEÇÃO, e sim um valor só.
    leds: LedsConfig | None = None
    triggers: TriggersConfig | None = None
    rumble: ControllerRumbleOverride | None = None
    speaker: ProfileSpeakerConfig | None = None
    mic: ControllerMicOverride | None = None
    sensores: ControllerSensoresOverride | None = None
    #: *"Como este controle aparece nos jogos"*, SÓ desta peça — MASCARA-NO-
    #: PERFIL-01 (08/09/2026, decisão dela: *"pode entrar sim"*).
    #:
    #: ``None`` = **volte ao padrão**, e esta é a ÚNICA seção desta classe em
    #: que ``None`` não quer dizer *"sem opinião"*. É decisão dela, 09/09/2026:
    #: *"Default é Hefesto dualsense padrão"*. O controle que o perfil não
    #: declara perde a máscara própria e passa a seguir o
    #: ``mode.gamepad_flavor`` do perfil e, sem ele, o
    #: ``DaemonConfig.gamepad_flavor`` — de fábrica ``dualsense``. Um perfil
    #: antigo (que nunca falou de máscara) carrega igual e devolve a mesa ao
    #: padrão; **quem já estava no padrão não tem vpad derrubado**, porque a
    #: máscara efetiva dele não muda (medido em
    #: ``manager.apply_controller_mascaras``: 0 de 4).
    #:
    #: A ORDEM DE DECISÃO, e ela é UMA só desde esta sprint:
    #: ``controllers[uniq].mascara`` > ``mode.gamepad_flavor`` > o padrão. Os
    #: degraus 2 e 3 são resolvidos por ``external_mask.mascara_efetiva``; o
    #: degrau 1 é EXECUTADO por ``manager.apply_controller_mascaras``, que
    #: escreve no cache que aquela função consulta — e o apaga de quem o perfil
    #: não declara. A régua da ordem mede o comportamento dos três degraus, não
    #: o texto: ``tests/unit/test_a_mascara_mora_no_perfil.py``.
    #:
    #: TIPO FECHADO, e é o mesmo do ``mode.gamepad_flavor``: um valor que o
    #: vpad não saiba criar não pode chegar ao disco. O ``MascaraDeGamepad`` é
    #: comparado com ``external_mask.mascaras_validas()`` nos dois sentidos por
    #: ``tests/unit/test_a_mascara_nintendo_pro_atravessa_a_casa.py``, então
    #: uma máscara nova não precisa ser declarada aqui de novo.
    mascara: MascaraDeGamepad | None = None


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
    # FEAT-ACOES-DE-BOTAO-01 (01/09/2026): o que cada um dos 21 botões da tela
    # faz, num campo só. Decisão dela, ao ler que doze das vinte e uma linhas
    # aceitavam escolha e não tinham onde ser guardadas: *"ganha campo. essa é a
    # parte das features que precisam ou serem ajustadas ou desenvolvidas."*
    #
    # - None = herda o de fábrica INTEIRO (`core/acoes_de_botao.padrao()`, que
    #   por sua vez é derivado dos mapas do produto — não há terceira cópia).
    # - {"cross": "KEY_ENTER"} = troca só esse botão; os outros seguem o padrão.
    #
    # POR QUE ELE NÃO SUBSTITUI O `key_bindings` ACIMA: aquele é o contrato do
    # TECLADO virtual e tem chamador vivo desde a FEAT-KEYBOARD-PERSISTENCE-01.
    # Este é o da TELA, que fala dos dois devices de uma vez — o `resolver()` do
    # `acoes_de_botao` é quem os separa. Aposentar um em favor do outro é
    # trabalho com dono e não se faz junto com o nascimento do campo.
    button_actions: dict[str, str] | None = None
    # FEAT-POINT-AND-CLICK-01: seção opcional de emulação de mouse.
    # - None = ativar o perfil não toca no estado da emulação (comportamento v1).
    # - Preenchida = ativar o perfil liga/desliga a emulação com as velocidades
    #   dadas (via `mouse_applier` injetado no ProfileManager).
    mouse: ProfileMouseConfig | None = None
    # Z4/T14 (24/08/2026), PROVISÓRIO — decisão dela em aberto (D-A do
    # 2026-08-24-ONDA0-Z4). Hoje o liga/desliga do TECLADO emulado mora só na
    # flag global `keyboard_emulation.flag` (utils/session.py:372), enquanto o
    # `mouse` logo acima — o interruptor VIZINHO na mesma aba — é por perfil
    # desde a FEAT-POINT-AND-CLICK-01. Mesmo contrato dos outros opcionais
    # desta classe: None = sem opinião (a ativação NÃO mexe na flag; ela
    # continua mandando). Preenchido = a ativação IMPÕE este valor, e vence a
    # flag (a precedência mora em
    # ``hefesto_dualsense4unix.profiles.schema.resolver_teclado_emulado`` —
    # pura, testada, e ainda NÃO chamada por nenhum caminho de ativação real:
    # a T14 entrega o campo e a régua, não o fio. Quem liga o fio (o widget na
    # Onda 9/Emulação e Onda 10/Navegação, e a chamada em
    # ``daemon/lifecycle.py`` na ativação) é de outra frente — ligar aqui,
    # sem a palavra dela sobre a frase de tela, seria "escolher em silêncio"
    # (regra da casa, COMO-EXECUTAR-UMA-SPRINT.md §8).
    teclado_emulado: bool | None = None
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
    # PONTE-CONFIRMADA-01 (19/08/2026): a ponte que já foi CONFIRMADA neste
    # jogo — ver `PonteConfirmada`. None = **ainda não sei**, que é o que todo
    # perfil existente diz (nenhuma migração escreve este campo). É a distinção
    # entre "nunca tentei" e "tentei e funciona", e é ela que faz a escada de
    # pontes parar em vez de recomeçar a cada abertura do jogo.
    ponte: PonteConfirmada | None = None

    @model_serializer(mode="wrap")
    def _sem_ponte_a_chave_nem_aparece(
        self, handler: SerializerFunctionWrapHandler
    ) -> Any:
        """Perfil sem ponte confirmada sai do dump IDÊNTICO ao que era.

        Mesma cura medida do ``rota`` em ``ProfileSpeakerConfig`` e das seções
        opcionais em ``loader.save_profile``, e pelo mesmo motivo: com
        ``extra="forbid"``, um hefesto ANTIGO recusa o perfil INTEIRO ao ver uma
        chave que não conhece. Gravar ``"ponte": null`` em todo save faria um
        downgrade quebrar os 18 perfis dela de uma vez — inclusive os que nunca
        ouviram falar de ponte. Aqui, só quem de fato confirmou uma carrega a
        chave nova, e o round-trip ``load → save`` de um perfil antigo não
        acrescenta nada ao arquivo.

        Mora no ESQUEMA, e não na lista de omissões do ``loader``, porque o
        dump também sai por outros caminhos (o estado do IPC, a exportação da
        GUI) — e a omissão que só vale num deles é a que se descobre no
        downgrade.
        """
        dados = handler(self)
        if isinstance(dados, dict) and dados.get("ponte") is None:
            dados.pop("ponte", None)
        return dados

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

        A FORMA DA CHAVE É UMA SÓ, e isso passou a ser MEDIDO em 06/09/2026
        (QUEM-E-QUEM-04, depois da O-CONTROLE-SEM-MAC-01). O plano era este
        validador aprender uma SEGUNDA gramática, "com prefixo explícito",
        para o controle cujo firmware não expõe serial. Ela não existe: dos
        cinco crachás candidatos sobrou o feature ``0x09``, e o que ele
        devolve é **o endereço de rádio** — é de onde o próprio
        ``hid_playstation`` tira o ``HID_UNIQ``. O crachá é *outra estrada
        para o mesmo valor*, e ``identity.resolver_crachas`` só o aceita
        depois das MESMAS guardas do serial (12 hex canônicos, não-vpad).

        **Consequência para quem vier alargar isto:** a porta já está aberta,
        e uma segunda forma seria uma segunda identidade para a mesma peça de
        plástico. Se um dia ela precisar existir, as três rejeições acima têm
        de vir junto — alargar a chave sem preservá-las troca "não lembra, em
        silêncio" por dois controles dividindo a MESMA memória, que é pior.
        A régua nomeada é
        ``tests/unit/test_quem_e_quem_04_a_chave_atravessa_o_transporte.py``,
        e ela morde nas duas pontas (este validador e o
        ``describe_controllers`` do backend).
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


#: AS `wm_class` QUE ESTE PRODUTO SABE SEREM DE JOGO E NÃO SÃO DA STEAM —
#: PERFIL-DOS-LANCADORES-E1, 11/09/2026. Já em minúsculas (`casefold`), porque
#: toda comparação de janela desta casa é sem caixa (`_casa_sem_caixa`).
#:
#: **POR QUE UM CADASTRO, E NÃO UM PREDICADO:** *"esta janela é de um jogo?"*
#: não se responde olhando a janela. Para a Steam há um CARIMBO — a `wm_class`
#: é `steam_app_<id>` e ninguém mais a usa. Para um jogo do Heroic a janela
#: anuncia `gotg.exe`, que é indistinguível de qualquer outro programa. Quem
#: sabe a resposta é o censo dos lançadores, que lê a biblioteca no disco; e
#: `perfil_e_regra_de_jogo` roda a 2 Hz, dentro do tique do autoswitch, onde
#: não cabe leitura de disco. Então o dono RESPONDE UMA VEZ por varredura e o
#: predicado consulta o que ele respondeu.
#:
#: **VAZIO = O COMPORTAMENTO HISTÓRICO**, e isso é fail-safe deliberado: sem
#: ninguém ter registrado nada (o processo que não semeia, o opt-out da suíte,
#: a máquina sem lançador), `e_endereco_de_jogo` volta a ser exatamente o
#: `steam_appid_from_wm_class(...) is not None` de antes.
_CLASSES_DE_JOGO_CONHECIDAS: frozenset[str] = frozenset()


def registrar_classes_de_jogo(classes: object) -> None:
    """Declara QUAIS `wm_class` de fora da Steam são de jogo. Um dono só.

    O dono é `profiles.loader.semear_perfis_dos_jogos`, que já lê a biblioteca
    dos lançadores e a marca de semeadura a cada varredura — é a única peça
    desta casa que sabe a resposta inteira e a recalcula sozinha.

    **SUBSTITUI, não soma**: a varredura conhece o conjunto COMPLETO, e somar
    faria uma classe sobreviver ao jogo desinstalado para sempre. Entrada
    inválida vira conjunto vazio, que é o fail-safe (ver o cadastro acima).
    """
    global _CLASSES_DE_JOGO_CONHECIDAS
    if not isinstance(classes, (list, tuple, set, frozenset)):
        # Algo que não é coleção não pode deixar o cadastro pela metade: ele
        # fica VAZIO, que é o fail-safe declarado acima.
        _CLASSES_DE_JOGO_CONHECIDAS = frozenset()
        return
    _CLASSES_DE_JOGO_CONHECIDAS = frozenset(
        c.strip().casefold() for c in classes if isinstance(c, str) and c.strip()
    )


def classes_de_jogo_conhecidas() -> frozenset[str]:
    """O cadastro de agora — o ÚNICO leitor do módulo, e o de fora também.

    `e_endereco_de_jogo` lê por aqui de propósito: um `global` com dois leitores
    é duas verdades esperando divergir, e esta é a função que a régua e a tela
    perguntam quando querem saber o que foi declarado.
    """
    return _CLASSES_DE_JOGO_CONHECIDAS


def e_endereco_de_jogo(wm_class: object) -> bool:
    """Esta `wm_class` endereça um JOGO?

    Duas respostas verdadeiras, e a segunda é a que a E1 acrescentou:

    1. ``steam_app_<id>`` — o carimbo da Steam, que nunca é outra coisa;
    2. uma classe que o censo dos lançadores declarou
       (`registrar_classes_de_jogo`) — ``gotg.exe``, do Heroic.

    **O QUE ISTO NÃO PODE VIRAR, e foi medido no disco dela em 11/09/2026:**
    *"qualquer `window_class` que case"*. O perfil `personalizado.json` dela
    mira ``Hefesto-Dualsense4Unix`` — a janela DO PRODUTO, gravada ali pelo
    «Detectar» — com prioridade 1. Solto o critério, focar a janela do Hefesto
    passaria a valer como "a regra própria do jogo": o cadeado cederia e o
    `manual_trigger_active` seria LIMPO em `AutoSwitcher._activate`, ou seja, o
    perfil pisaria no gatilho que ela acabou de aplicar na aba — no momento em
    que ela está justamente olhando para a janela. É o buraco da R-01 pela
    porta dos fundos, e é a única coisa que a linha antiga protegia.
    """
    if not isinstance(wm_class, str):
        return False
    # `is not None` e nunca a verdade do valor: `steam_app_0` devolve o int 0,
    # que é FALSO — o mesmo engano que `if appid:` já produziu nesta casa.
    if steam_appid_from_wm_class(wm_class) is not None:
        return True
    return wm_class.strip().casefold() in classes_de_jogo_conhecidas()


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
    2. a ``wm_class`` em foco ser ENDEREÇO DE JOGO (`e_endereco_de_jogo`: o
       carimbo ``steam_app_<id>``, ou uma classe que o censo dos lançadores
       declarou) e estar listada em ``match.window_class``.

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
    # PERFIL-DOS-LANCADORES-E1 (11/09/2026): era
    # `if steam_appid_from_wm_class(wm_class) is None: return False` — de
    # quando «perfil de jogo» e «perfil da Steam» eram sinônimos. Com o perfil
    # do Heroic nascendo sozinho, ele nascia e NÃO ENTRAVA: a linha aparecia na
    # lista e não fazia nada. O que a linha protegia continua protegido, e está
    # medido na docstring de `e_endereco_de_jogo` — o critério não afrouxou
    # para "qualquer window_class", ele passou a perguntar ao DONO da resposta.
    if not e_endereco_de_jogo(wm_class):
        return False
    # Mesma comparação de `MatchCriteria.matches` (R-12): sem ela, um
    # `steam_app_` digitado com maiúscula faria o perfil CASAR pelo matcher e
    # não ser reconhecido como regra do jogo aqui — a divergência entre os dois
    # predicados é justamente o buraco que este módulo existe para fechar.
    return _casa_sem_caixa(wm_class, match.window_class)


def normalizar_gamepad_flavor(valor: object) -> MascaraDeGamepad | None:
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
    if valor == "nintendo":
        return "nintendo"
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


def resolver_teclado_emulado(profile: Profile | None, flag_global: bool) -> bool:
    """A precedência da T14 (Z4, 24/08/2026), PURA: perfil com opinião VENCE.

    ``Profile.teclado_emulado`` é ``None`` por padrão — "sem opinião", e nesse
    caso a flag global (``utils.session.load_keyboard_preference`` hoje) segue
    mandando, o comportamento de sempre. Quando o perfil TEM opinião
    (``True``/``False``), ele vence — mesma regra do ``mouse``/``mic``/
    ``speaker`` desta classe (contrato ``None`` = sem opinião), e a MESMA
    proteção do ``mic.muted`` (MIC-GRAVACAO-01, ``schema.py``): perfil SEM
    opinião nunca pode apagar o que a flag diz.

    NÃO É CHAMADA por nenhum caminho de ativação real ainda — ver a nota
    datada no campo ``Profile.teclado_emulado``. É a metade "régua" da T14; a
    metade "fio" (o widget e a chamada em ``daemon/lifecycle.py`` na
    ativação) é de outra frente.
    """
    if profile is None or profile.teclado_emulado is None:
        return flag_global
    return profile.teclado_emulado


__all__ = [
    "CONFIRMADA_POR_ESCOLHA",
    "CONFIRMADA_POR_GESTO",
    "CONFIRMADA_POR_SILENCIO",
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
    "PonteConfirmada",
    "Profile",
    "ProfileMicConfig",
    "ProfileMouseConfig",
    "ProfileSpeakerConfig",
    "RumbleConfig",
    "TriggerConfig",
    "TriggersConfig",
    "classes_de_jogo_conhecidas",
    "e_endereco_de_jogo",
    "normalizar_gamepad_flavor",
    "perfil_declara_modo_de_jogo",
    "perfil_e_regra_de_jogo",
    "registrar_classes_de_jogo",
    "resolver_teclado_emulado",
]
