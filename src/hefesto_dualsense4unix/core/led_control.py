"""Controle de LEDs do DualSense.

API de alto nível: lightbar RGB, 5 LEDs de jogador (bitmask) e LED do microfone.

Cobertura atual:
- Lightbar RGB: `IController.set_led` (implementado).
- LED do microfone: `IController.set_mic_led` (implementado — INFRA-SET-MIC-LED-01).
  **Não é aplicado por `apply_led_settings`**: mic_led é tratado como estado
  runtime puro (ver AUDIT-FINDING-PROFILE-MIC-LED-RESET-01 e armadilha A-06).
  Transições de mic_led vêm do botão físico ou de handlers IPC dedicados
  (`udp_server` MicLED, `HotkeyManager` mic_btn), nunca de profile switch.
- Player LEDs: `IController.set_player_leds` (implementado — player bitmask).
  Player LEDs continuam com API básica de bitmask; efeitos avançados (animação)
  dependem de sprint futura.

Uso:
    from hefesto_dualsense4unix.core.led_control import LedSettings, apply_led_settings
    apply_led_settings(controller, LedSettings(lightbar=(255, 128, 0)))
"""
from __future__ import annotations

import colorsys
from collections.abc import Iterable
from dataclasses import dataclass

from hefesto_dualsense4unix.core.controller import IController

RGB = tuple[int, int, int]


#: O PISO DO BRILHO — D-2909-O-BRILHO-TEM-PISO (29/09/2026, a resposta (a) da
#: A-LUZ-DO-CONTROLE-NUNCA-SAI-PRETA-01): todo passo do trilho acima de 0%
#: acende uma cor que se vê, e só o 0% (o «Desligar», D-2509) apaga. A escala
#: inteira vai até ele: o fator é `PISO_DO_BRILHO + (1 - PISO_DO_BRILHO) *
#: brilho`, e cada passo do trilho ainda muda o tom (a ilusão do slicer que
#: ela declarou, D-0909-O-BRILHO-DA-BARRA-E-ILUSAO-DECLARADA).
#:
#: O FATO QUE O ANCORA: às 02:30 de 29/09 a luz do White a 8% era
#: `(0, 0, 20)`, e ela a leu como preto (*«a lightbar do controle tá preto»*).
#: Com o piso, 1% acende o canal maior em 53 e 8% em 67. O valor é de quem
#: coordenou, pelo padrão dela, sem a sessão com a luz na mão (ela dormia): a
#: sprint mandava medir de 2% a 20% e ficar com o maior em que ela reconhece a
#: cor, e 20% é o topo dessa faixa — o mais seguro para quem enxerga pouco.
#: Quem se incomoda com luz tem o 0%.
PISO_DO_BRILHO = 0.20


def fator_do_brilho(brilho: float) -> float:
    """O fator que multiplica o RGB no `brilho` do trilho — a conta do piso.

    `0` (e abaixo) apaga; acima de 0 o fator parte do piso e chega a 1 no
    100%. Acima de 1 (o fator relativo de um controle mais claro que o perfil)
    passa como está: o corte por canal é de `apply_brightness`. O
    arredondamento desfaz o ruído do ponto flutuante na borda.
    """
    if brilho <= 0.0:
        return 0.0
    if brilho >= 1.0:
        return brilho
    return round(PISO_DO_BRILHO + (1.0 - PISO_DO_BRILHO) * brilho, 9)


def _escala_crua(rgb: RGB, fator: float) -> RGB:
    """`rgb` vezes `fator`, truncado por canal — a conta sem o piso."""
    r, g, b = rgb
    return (
        max(0, min(255, int(r * fator))),
        max(0, min(255, int(g * fator))),
        max(0, min(255, int(b * fator))),
    )


@dataclass(frozen=True)
class LedSettings:
    """Configuração imutável de LEDs.

    - `lightbar`: RGB 0-255 cada.
    - `brightness_level`: multiplicador de brilho [0.0, 1.0]; aplicado
      sobre o RGB antes de enviar ao hardware. 1.0 = sem dimming.
    - `player_leds`: lista de 5 booleanos para os indicadores inferiores
      (esquerda para direita). Padrão: todos apagados.
    - `mic_led`: **reservado / no-op em `apply_led_settings`**. Preservado no
      dataclass por compatibilidade de API (callers antigos que instanciavam
      `LedSettings(lightbar=..., mic_led=...)` seguem válidos), mas o valor
      NÃO é propagado ao hardware pelo apply. Mic LED é estado runtime puro:
      muda via botão físico ou IPC `led.mic_set` / `udp MicLED`, nunca via
      profile switch (AUDIT-FINDING-PROFILE-MIC-LED-RESET-01; A-06).
    """

    lightbar: RGB
    brightness_level: float = 1.0
    player_leds: tuple[bool, bool, bool, bool, bool] = (False, False, False, False, False)
    mic_led: bool = False

    def __post_init__(self) -> None:
        if len(self.lightbar) != 3:
            raise ValueError(f"lightbar precisa 3 componentes, recebeu {len(self.lightbar)}")
        for idx, v in enumerate(self.lightbar):
            if not (0 <= v <= 255):
                raise ValueError(f"lightbar[{idx}] fora de byte: {v}")
        if not (0.0 <= self.brightness_level <= 1.0):
            raise ValueError(
                f"brightness_level fora de [0.0, 1.0]: {self.brightness_level}"
            )

    def apply_brightness(self, level: float) -> LedSettings:
        """Devolve cópia com canais RGB escalados por ``level`` (clamp 0-255).

        ``level`` é o brilho do trilho, e passa pelo PISO (`fator_do_brilho`,
        D-2909-O-BRILHO-TEM-PISO): acima de 0 a luz nunca sai abaixo do piso,
        e 0 apaga. Valores acima de 1.0 são tolerados e acabam truncados pelo
        clamp por canal. É o DONO da conta «tom vezes brilho → luz»: o provider,
        o manager, o `led.set` e o backend passam por aqui.
        """
        scaled = _escala_crua(self.lightbar, fator_do_brilho(level))
        return LedSettings(
            lightbar=scaled,
            brightness_level=self.brightness_level,
            player_leds=self.player_leds,
            mic_led=self.mic_led,
        )


def player_bitmask(leds: tuple[bool, bool, bool, bool, bool]) -> int:
    """Converte 5 flags em bitmask 0-31 (mesmo layout usado pelo protocolo DSX).

    É o DONO da conta: `core.lightbar_gatilho.mascara_de_player_leds`, que
    escreve o ``common[43]`` do report das luzes, pergunta aqui (28/09/2026).
    """
    value = 0
    for idx, on in enumerate(leds):
        if on:
            value |= 1 << idx
    return value


#: FEAT-COOP-PLAYER-LED-01 / COR-03 — padrões canônicos do DualSense para os 5
#: LEDs de player (ordem física esquerda→direita: [L2, L1, centro, R1, R2]), os
#: mesmos que o PS5 usa para indicar P1..P4. Moraram em
#: `daemon.subsystems.coop` até o COR-03; agora vivem aqui (camada core, sem
#: dependência de daemon) porque a cor automática por controle usa o MESMO
#: padrão fora do co-op (D7 — "número do controle"). O coop reexporta.
#:
#: R-25 (auditoria 25/07): a tabela vai até 8. Antes ela ia até 4 e TODO
#: índice ≥5 caía no mesmo "acende os 5" — dois controles em slots 5 e 6
#: exibiam o MESMO padrão, que é exatamente a colisão que a numeração única
#: (R-24) existe para matar. Os padrões 6..8 são escolhas desta casa, com um
#: único critério: serem distinguíveis A OLHO dos canônicos 1..5 e entre si
#: (extremos / três centrais / três à esquerda).
_PLAYER_LED_PATTERNS: dict[int, tuple[bool, bool, bool, bool, bool]] = {
    1: (False, False, True, False, False),
    2: (False, True, False, True, False),
    3: (True, False, True, False, True),
    4: (True, True, False, True, True),
    5: (True, True, True, True, True),
    6: (True, False, False, False, True),
    7: (False, True, True, True, False),
    8: (True, True, True, False, False),
}

#: R-25: padrão de "slot fora da tabela" (≥9). Distinto de TODOS os de cima,
#: então nunca é confundido com um número real; só colide consigo mesmo, e
#: para isso a casa precisaria de nove controles ligados ao mesmo tempo.
_PLAYER_LED_OVERFLOW = (True, False, True, True, False)


#: O BRILHO DAS LUZES DE NÚMERO — `D-2409-AS-LUZES-DE-NUMERO-TEM-TRES-BRILHOS`,
#: decisão dela de 24/09/2026: *"Fraco, Médio e Forte na linha LEDs, nascendo
#: no Fraco"*. A razão que ela escolheu: quem enxerga pouco não tinha como
#: aumentar, e quem se incomoda com luz não tinha como escolher.
#:
#: A CHAVE É A PALAVRA, O VALOR É O DEGRAU DO FIRMWARE — e o degrau é INVERTIDO:
#: o `common[42]` do report de saída diz 0 alto · 1 médio · 2 baixo, e só vale
#: com o `flag2` bit0 (`SET_PLAYER_LED_BRIGHTNESS`) ligado. Medido pelo olho
#: dela nos dois transportes (BRILHO-DE-HARDWARE-01, 09/09/2026): o degrau muda
#: as cinco lâmpadas de numeração, e a barra de cor não.
#:
#: A ORDEM DO DICIONÁRIO É A DA TELA (do mais fraco ao mais forte), e quem
#: desenha as três pílulas a lê daqui. A palavra do meio vai sem acento
#: porque é valor legível por máquina (o disco, o gesto); a tela escreve
#: «Médio». A régua de acento a pula pela marca na linha do dicionário.
BRILHOS_DAS_LUZES: dict[str, int] = {"fraco": 2, "medio": 1, "forte": 0}  # noqa-acento: chave ASCII

#: O Fraco é o de antes da decisão — o degrau baixo que a pydualsense manda
#: por padrão — e é onde todo perfil e todo controle nascem.
BRILHO_DAS_LUZES_PADRAO = "fraco"


def degrau_do_brilho_das_luzes(nome: str | None) -> int:
    """O degrau do firmware (`common[42]`) para a palavra do perfil.

    `None` é quem não opinou, e vale o padrão (Fraco): o Hefesto sempre manda
    no brilho das lâmpadas, e sem escolha nenhuma ele manda o de antes.
    Palavra desconhecida levanta — o esquema já recusa na entrada, e um
    degrau inventado aqui acenderia um brilho que ninguém pediu.
    """
    if nome is None:
        nome = BRILHO_DAS_LUZES_PADRAO
    try:
        return BRILHOS_DAS_LUZES[nome]
    except KeyError as erro:
        raise ValueError(
            f"brilho das luzes de número desconhecido: {nome!r} "
            f"(as palavras são {', '.join(BRILHOS_DAS_LUZES)})"
        ) from erro


def player_led_pattern(index: int) -> tuple[bool, bool, bool, bool, bool]:
    """Padrão canônico de player-LED do jogador/controle `index`.

    1..4 são os padrões do PS5. 5..8 são extensões desta casa (R-25) — o
    espaço de numeração é ÚNICO entre DualSense, externos e co-op (R-24), e
    um DualSense pode legitimamente cair no slot 5+ quando há externos
    numerados antes dele. ≥9 cai no padrão de overflow, distinto dos oito.
    """
    return _PLAYER_LED_PATTERNS.get(index, _PLAYER_LED_OVERFLOW)


#: COR-03 — paleta automática de lightbar por controle, estilo PS5 (cores por
#: ordem de conexão). Valores canônicos desta casa (decisão documentada do
#: sprint 2026-07-16-sprint-cores-e-led-automaticos): primárias puras + rosa
#: vivo — máxima distinguibilidade entre colunas lado a lado, e o rosa (255,
#: 0, 128) em vez do magenta puro para não confundir com o azul em brilho
#: baixo. A cor daqui é a IDENTIDADE (pré-brilho, D8); quem escala pelo
#: `lightbar_brightness` do perfil é o provider (D11), pelo mesmo caminho do
#: global (`LedSettings.apply_brightness`).
#:
#: R-25: 5..8 seguem o MESMO motivo da tabela de padrões acima — com o espaço
#: de numeração único (R-24) o slot 5+ é alcançável, e "branco para todo mundo
#: acima de 4" fazia dois controles ficarem da mesma cor. Amarelo/ciano/laranja
#: fecham o círculo cromático sem chegar perto do azul-em-brilho-baixo.
_PLAYER_SLOT_COLORS: dict[int, RGB] = {
    1: (0, 0, 255),  # azul (P1 no PS5)
    2: (255, 0, 0),  # vermelho (P2)
    3: (0, 255, 0),  # verde (P3)
    4: (255, 0, 128),  # rosa (P4)
    5: (255, 255, 0),  # amarelo
    6: (0, 255, 255),  # ciano
    7: (255, 128, 0),  # laranja
    8: (128, 0, 255),  # roxo
}


def cor_automatica(numero: int | None, tom_do_plastico: RGB | None) -> RGB:
    """A cor AUTOMÁTICA de um controle: a do plástico, e a do número sem ela.

    D-2909-A-COR-AUTOMATICA-VEM-DO-PLASTICO (29/09/2026, a resposta (b) da
    A-LUZ-DO-CONTROLE-NUNCA-SAI-PRETA-01): o plástico já é a identidade do
    controle na tela inteira, e o número já tem as lâmpadas dele. Um dono só:
    o provider do daemon, o degrau 4 da aba Iluminação, a peça da tela e a
    prévia da troca de número perguntam aqui. `tom_do_plastico` é o de
    `integrations.cor_do_plastico.tom_da_luz` — `None` quando o plástico não
    foi lido ou não tem tom, e aí vale a cor do número. Quem perde o tom do
    plástico para outra peça (dois plásticos iguais) vai à do número pelo
    `cores_sem_colisao`, que leva as duas.
    """
    if tom_do_plastico is not None:
        return tom_do_plastico
    return player_slot_color(numero if numero is not None else 0)


def player_slot_color(slot: int) -> RGB:
    """Cor canônica de lightbar do controle `slot` (1=azul, 2=vermelho, 3=verde, 4=rosa).

    5..8 são extensões desta casa (R-25, ver tabela). Slot ≥9 cai no branco —
    fallback neutro, distinguível das oito cores acima.

    **ELA NÃO É INJETIVA ACIMA DE 8, e o irmão é.** `player_led_pattern` tem o
    `_PLAYER_LED_OVERFLOW` declarado como *"só colide consigo mesmo"*; aqui
    dois controles em 9 e 10 recebem o MESMO branco. A garantia de que duas
    peças nunca ficam da mesma cor NÃO mora nesta função — mora em
    :func:`cores_sem_colisao`, que resolve a mesa inteira e desempata o branco
    repetido. Quem chamar isto direto, sem passar por lá, herda a colisão.
    """
    return _PLAYER_SLOT_COLORS.get(slot, (255, 255, 255))


#: DE ONDE VEIO A COR DE UMA PEÇA — a PROCEDÊNCIA, e ela é o conserto de
#: 08/09/2026.
#:
#: A primeira volta desta regra não tinha este campo, e por isso o resolvedor
#: **adivinhava**: ele chamava de fóssil toda cor que fosse a do número de
#: outro da mesa. No disco, um broadcast (`led.set` sem `uniq`, que grava a
#: MESMA cor em todos de propósito) é indistinguível de duas escolhas que
#: colidiram — então o palpite desfez o "pinta os quatro de verde" dela: os
#: quatro saíam `[verde, vermelho, azul, rosa]`, e o P1 ficava com a cor do
#: número do 3 enquanto o P3 ficava com a do 1.
#:
#: DECISÃO DELA (delegada), 08/09/2026: *"o override de cor por MAC ganha
#: PROCEDÊNCIA — para qual número ele foi escolhido. Quando o número daquele
#: aparelho muda, a cor gravada é FÓSSIL e sai sozinha."* Com ela gravada, o
#: resolvedor **lê** em vez de adivinhar.
#:
#: A cor veio da camada AUTOMÁTICA: é a do número dele, por construção.
DA_PALETA = "paleta"
#: `led.set` SEM `uniq` — o "Todos" dela. A mesma cor em todos, de propósito.
#: **Nunca é deslocada**, e é esta linha que devolve o broadcast ao produto.
DO_BROADCAST = "todos"
#: A cor é o GLOBAL do perfil: este controle não tem opinião própria. Cede a
#: quem tem identidade, mas não cede à irmã que também está no global — vários
#: controles na cor global é o gesto "Todos" do perfil, não uma colisão.
DO_GLOBAL = "global"
#: Escolha POR CONTROLE sem número conhecido na hora (controle fora da mesa,
#: backend sem a consulta de número). Vale como escolha viva: não é fóssil.
DA_MAO = "mao"  # noqa-acento: VALOR de carimbo, legível por máquina — a mesma escolha de `sim`/`nao` desta casa
#: Override que veio do disco SEM procedência gravada — todo perfil escrito
#: antes de 08/09/2026. Não dá para ler para qual número ele foi escolhido, e
#: é o ÚNICO caso em que a regra ainda prova pela forma (ver `_e_fossil`).
LEGADO = "legado"

#: Preto é AUSÊNCIA de cor, não identidade. Uma barra apagada não colide com
#: outra apagada — "as duas estão desligadas" é uma resposta, e deslocar uma
#: delas para roxo acenderia um controle que a usuária mandou apagar.
_APAGADA: RGB = (0, 0, 0)


@dataclass(frozen=True)
class PecaDaMesa:
    """Uma peça na mesa da regra de cor única.

    `pedida` é a cor que as camadas do daemon resolveram para ela (já
    escalada pelo brilho); `do_numero` é a cor AUTOMÁTICA do número dela — é
    para onde ela volta quando é deslocada, e é `None` quando ela não tem
    número (ausente da mesa, vpad, key sem MAC, paleta automática desligada).

    `procedencia` é de onde a `pedida` veio: uma das constantes acima, ou o
    **número inteiro** para o qual a cor foi escolhida. `numero` é o número
    que ela tem AGORA — e a comparação entre os dois é a regra inteira: um
    override escolhido para o número 1 num aparelho que hoje é o 2 é fóssil,
    e sai sozinho.

    `brilho` é o brilho em que ESTA peça acende (o do perfil, ou o do
    controle quando ele tem o seu): é nele que sai o tom da paleta para onde
    ela for deslocada (A-BARRA-NAO-ESCURECE-AO-REAPLICAR-01, 25/09/2026).
    `None` é *"não se sabe"*, e o tom sai cheio, como antes do campo.

    `do_plastico` é o tom do PLÁSTICO no brilho dela (29/09/2026,
    D-2909-A-COR-AUTOMATICA-VEM-DO-PLASTICO): quando existe, é a cor
    automática, e o fóssil volta a ele antes do número. `None` é o plástico
    não lido ou sem tom, e a automática é a do número, como antes do campo.
    """

    uniq: str
    pedida: RGB | None
    do_numero: RGB | None
    procedencia: object = LEGADO
    numero: int | None = None
    brilho: float | None = None
    do_plastico: RGB | None = None

    @property
    def automatica(self) -> RGB | None:
        """A cor automática desta peça: a do plástico, e a do número sem ela."""
        return self.do_plastico if self.do_plastico is not None else self.do_numero


def _e_fossil(peca: PecaDaMesa, numeros: set[RGB]) -> bool:
    """A cor desta peça é o número de ontem congelado, e não uma escolha?

    As três respostas, e as três se LEEM — nenhuma se adivinha:

    * **procedência inteira** — a cor foi escolhida para um número. É fóssil
      exatamente quando esse número não é mais o dela. É o caso medido na
      mesa dela em 08/09/2026: os ranks 2 e 4 guardavam as cores dos slots 1
      e 2, escolhidas num dia em que eles eram outros;
    * **`LEGADO`** — override do disco anterior ao campo. Aqui, e SÓ aqui, a
      regra prova pela FORMA: uma cor que acende o TOM automático de OUTRO da
      mesa (e não o do próprio) é fóssil. Perfil antigo com uma escolha de
      verdade — um roxo que não é número de ninguém — sobrevive à migração.
      A pergunta é do TOM, e não do byte (A-LUZ-DO-CONTROLE-NUNCA-SAI-PRETA-01,
      29/09/2026): as cores de número chegam escaladas pelo brilho de CADA
      peça, e o byte fazia o vermelho legado do P1 ficar ou sair conforme o
      trilho do P2 estivesse a 99% ou a 100%;
    * **todo o resto** (`DA_PALETA`, `DO_BROADCAST`, `DO_GLOBAL`, `DA_MAO`)
      nunca é fóssil. O broadcast dela é o caso que derrubou a primeira
      volta desta regra.
    """
    if isinstance(peca.procedencia, bool):  # bool é int em Python; não é número
        return False
    if isinstance(peca.procedencia, int):
        return peca.numero is None or peca.procedencia != peca.numero
    if peca.procedencia is not LEGADO or peca.pedida is None:
        return False
    # O TOM EXATO, e não a vizinhança: o legado prova fóssil pela FORMA (a
    # cor é a automática de outro), e uma escolha de verdade ao lado de um
    # tom automático não é esse tom congelado.
    proprias = (peca.do_plastico, peca.do_numero)
    if any(p is not None and _mesmo_tom(peca.pedida, p, vizinhanca=False)
           for p in proprias):
        return False
    return any(_mesmo_tom(peca.pedida, numero, vizinhanca=False) for numero in numeros)


def _acende_o_tom(acesa: RGB, tom: RGB) -> bool:
    """A luz `acesa` é o `tom` em algum brilho? — a pergunta do TOM, e não do byte.

    A-BARRA-NAO-ESCURECE-AO-REAPLICAR-01, 25/09/2026: o azul do P1 a 82% é
    `(0,0,209)` e o azul cheio é `(0,0,255)` — bytes diferentes, a MESMA cor
    na mão de quem joga. A régua de cor única comparava bytes, e o fóssil do
    P3 era deslocado para o azul cheio ao lado do P1 azul.

    A CONTA É A CRUA DO DONO DA ESCALA (`_escala_crua`: cada canal vezes o
    fator, truncado), e a resposta é exata, sem tolerância: existe um fator
    `f` em [0, 1] que leva o `tom` à `acesa` quando os intervalos de `f` de
    cada canal se cruzam. O fator do meio do cruzamento é conferido pela
    própria conta, para a borda de ponto flutuante não mentir. O piso do
    trilho (D-2909-O-BRILHO-TEM-PISO) não entra: ele diz quais fatores o
    trilho alcança, e não de que tom uma luz é.
    """
    baixo, alto = 0.0, 1.0
    for luz, canal in zip(acesa, tom, strict=True):
        if canal == 0:
            if luz != 0:
                return False
            continue
        baixo = max(baixo, luz / canal)
        alto = min(alto, (luz + 1) / canal)
    if baixo > alto:
        return False
    # A CONTA CRUA, e não a do trilho: a pergunta é se a luz está no RAIO do
    # tom, em qualquer fator. O piso (D-2909-O-BRILHO-TEM-PISO) só limita os
    # fatores que o trilho alcança, e não muda de que tom uma luz é.
    return _escala_crua(tom, (baixo + alto) / 2) == acesa


def _mesmo_tom(a: RGB, b: RGB, *, vizinhanca: bool = True) -> bool:
    """As duas luzes são o MESMO TOM, cada uma no seu brilho? — o dono único.

    A-LUZ-DO-CONTROLE-NUNCA-SAI-PRETA-01, 29/09/2026. O resolvedor fazia três
    perguntas pelo BYTE — o legado fóssil (`in numeros`), a cor repetida (`in
    tomadas`) e o global que cede (`not in tomadas`) — e as três mudavam de
    resposta com o brilho de OUTRA peça. Medido na função pura, com a mesa
    dela das 02:30: com o White a 99% o Cosmic Red ficava vermelho, e a 100%
    virava azul e o White, vermelho. As três passam a perguntar aqui.

    Duas luzes são o mesmo tom quando acendem o mesmo tom da paleta, ou
    quando uma acende a outra num brilho (`_acende_o_tom`, nos dois
    sentidos). O preto é ausência de cor: só é «o mesmo» que o próprio preto.

    A LUZ AMBÍGUA NÃO TOMA O TOM DE NINGUÉM: abaixo de 1% o vermelho, o rosa
    e o laranja acendem o mesmo `(1, 0, 0)` (`reescalar` já recusa escolher
    entre eles), e ela só é «a mesma» que o próprio byte. Sem esta guarda, um
    controle a 0,5% deslocava o vizinho rosa (`test_a_marca_da_cor_nao_some`).

    `vizinhanca=False` é o TOM EXATO: sem a vizinhança de matiz. É a pergunta
    de toda cor que alguém ESCOLHEU (o legado, a escolha por número, a mão, o
    «Todos»): a tela recusa com o X só a casa exata
    (`a04_iluminacao._sem_repetir_a_cor_do_vizinho`), e o daemon não pode
    deslocar por vizinhança uma escolha que a tela aceitou
    (D-0909-A-COR-DE-OUTRO-CONTROLE-SE-RECUSA-COM-X: *«nada se desloca
    sozinho»*). A vizinhança vale para a cor AUTOMÁTICA e para o tom livre.
    """
    if a == b:
        return True
    if a == _APAGADA or b == _APAGADA:
        return False
    tons_a, tons_b = _tons_da_paleta(a), _tons_da_paleta(b)
    if len(tons_a) > 1 or len(tons_b) > 1:
        return False
    if tons_a and tons_b:
        return tons_a == tons_b
    if _acende_o_tom(a, b) or _acende_o_tom(b, a):
        return True
    if not vizinhanca:
        return False
    # E O «MESMO» É POR VIZINHANÇA desde a cor do plástico
    # (D-2909-A-COR-AUTOMATICA-VEM-DO-PLASTICO): os tons do plástico caem ao
    # lado dos da paleta — o Galactic Purple `(131, 0, 255)` e o roxo
    # `(128, 0, 255)` são a mesma luz na mão, e o Cosmic Red `(255, 0, 82)`
    # fica perto do rosa `(255, 0, 128)`. Ver `_vizinhos`.
    return _vizinhos(a, b)


#: A VIZINHANÇA ENTRE DUAS LUZES — 29/09/2026, com a cor do plástico. Duas
#: luzes coloridas são a mesma na mão quando o matiz delas fica a menos de
#: `LIMIAR_DE_MATIZ` graus e a saturação a menos de `LIMIAR_DE_SATURACAO`; duas
#: neutras (brancos e cinzas, abaixo de `SATURACAO_NEUTRA_DA_LUZ`) são sempre
#: a mesma. Os tons da paleta ficam a 30° uns dos outros (o vermelho, o
#: laranja e o rosa; o azul e o roxo), e o limiar de 15° é a metade: nenhum
#: tom da paleta vira vizinho de outro, e o Galactic Purple (a 0,8° do roxo)
#: e o Cosmic Red (a 10,7° do rosa) viram. Escolhidos por quem coordenou, pelo
#: padrão dela, sem a sessão com a luz na mão.
LIMIAR_DE_MATIZ = 15.0
LIMIAR_DE_SATURACAO = 0.25
SATURACAO_NEUTRA_DA_LUZ = 0.15


def _vizinhos(a: RGB, b: RGB) -> bool:
    """As duas luzes (nenhuma apagada) são a mesma na mão, pelo matiz?"""
    ha, sa, _va = colorsys.rgb_to_hsv(*(c / 255 for c in a))
    hb, sb, _vb = colorsys.rgb_to_hsv(*(c / 255 for c in b))
    neutra_a = sa < SATURACAO_NEUTRA_DA_LUZ
    neutra_b = sb < SATURACAO_NEUTRA_DA_LUZ
    if neutra_a or neutra_b:
        return neutra_a and neutra_b
    distancia = abs(ha - hb) * 360.0
    distancia = min(distancia, 360.0 - distancia)
    return distancia < LIMIAR_DE_MATIZ and abs(sa - sb) < LIMIAR_DE_SATURACAO


def _tons_da_paleta(luz: RGB) -> tuple[RGB, ...]:
    """Os tons da paleta que `luz` acende em algum brilho."""
    return tuple(t for t in _PLAYER_SLOT_COLORS.values() if _acende_o_tom(luz, t))


def _ja_acesa(luz: RGB, acesas: Iterable[RGB], *, vizinhanca: bool = True) -> bool:
    """`luz` é o tom de alguma das `acesas`? — a pergunta de `in`, pelo tom."""
    return any(_mesmo_tom(luz, outra, vizinhanca=vizinhanca) for outra in acesas)


def _automaticas(mesa: list[PecaDaMesa]) -> set[RGB]:
    """As cores automáticas da mesa (o plástico, ou o número), cada uma no brilho da sua peça."""
    return {
        peca.automatica for peca in mesa
        if peca.automatica is not None and peca.automatica != _APAGADA
    }


def fosseis(mesa: list[PecaDaMesa]) -> frozenset[str]:
    """Os `uniq` da mesa cuja cor pedida é FÓSSIL — a pergunta da tela e do daemon.

    A-LUZ-DO-CONTROLE-NUNCA-SAI-PRETA-01, 29/09/2026. A aba Iluminação montava
    a peça com as cores de número cheias e chamava `_e_fossil` por conta
    própria, e o daemon a montava com as cores escaladas: para o Cosmic Red
    das 02:30 a tela respondia «fóssil» e o daemon, «não». As duas passam a
    perguntar a esta função, com a mesa inteira, e a resposta é pelo tom:
    ela não depende do brilho de ninguém.
    """
    numeros = _automaticas(mesa)
    return frozenset(peca.uniq for peca in mesa if _e_fossil(peca, numeros))


def _na_escala(tom: RGB, brilho: float | None) -> RGB:
    """O `tom` aceso no `brilho` da peça — cheio quando o brilho não é sabido."""
    if brilho is None:
        return tom
    return LedSettings(lightbar=tom).apply_brightness(brilho).lightbar


def reescalar(
    acesa: RGB, de: float, para: float, extras: tuple[RGB, ...] = ()
) -> RGB:
    """A luz `acesa`, que está no brilho `de`, levada ao brilho `para`.

    O BRILHO ENTRA UMA VEZ SÓ — A-BARRA-NAO-ESCURECE-AO-REAPLICAR-01,
    25/09/2026. O brilho por controle é um fator sobre a cor que já chegou no
    brilho do perfil (`backend._scaled_led`), e a conta em dois passos trunca
    duas vezes: o P1 a 60% saía `(0,0,152)` do perfil e `(0,0,153)` do trilho,
    e com o perfil a 1% e o controle a 100% o azul voltava `(0,0,200)`. Quando
    a luz é um tom da paleta NAQUELE brilho — é a automática, e é o caso de
    todo controle que nasce sem cor escolhida —, o tom é levado ao brilho novo
    pela conta do dono, uma vez só, e a resposta é a do trilho. Fora da paleta
    e dos `extras` não há tom a provar, e vale a razão, como antes.
    O tom tem de ser ÚNICO: abaixo de 1% o vermelho, o rosa e o laranja acendem
    o mesmo `(1,0,0)`, e escolher um deles seria trocar a cor pelo brilho.

    `extras` são tons a mais que o chamador SABE que estão na base — o global
    do perfil (conferência, 25/09/2026). Sem a paleta, o controle no global
    com o brilho dele saía pela razão, com duas truncagens: o P4 a 30% do
    trilho acendia `(12,24,54)` e o perfil reaplicado `(11,23,53)`; com o
    perfil a 2% e o controle a 100%, o `#2850B4` virava `(0,50,150)`, sem o
    vermelho. Com o global entre os tons, a conta é a do trilho.
    """
    if de > 0.0:
        candidatos = dict.fromkeys((*_PLAYER_SLOT_COLORS.values(), *extras))
        tons = [t for t in candidatos if _na_escala(t, de) == acesa]
        if len(tons) == 1:
            return _na_escala(tons[0], para)
    # A RAZÃO É ENTRE OS FATORES do piso (D-2909-O-BRILHO-TEM-PISO), e não
    # entre os brilhos: a luz `acesa` saiu do fator de `de`, e vai ao de `para`.
    fator = fator_do_brilho(para) / fator_do_brilho(de) if de > 0.0 else 0.0
    return _escala_crua(acesa, fator)


def cores_sem_colisao(mesa: list[PecaDaMesa]) -> dict[str, RGB]:
    """Resolve a mesa inteira de modo que duas peças nunca fiquem da mesma cor.

    A `D-DUAS-PECAS-NUNCA-TEM-A-MESMA-COR` (26/08/2026) FOI REVOGADA em
    09/09/2026 pela `D-0909-A-COR-DE-OUTRO-CONTROLE-SE-RECUSA-COM-X`: a cor
    de outro controle se recusa no GESTO, com o X, *«e nada se desloca
    sozinho»*. O que este resolvedor segue cumprindo é o FÓSSIL de 08/09 (a
    cor escolhida para outro número sai sozinha, ver `_e_fossil`). O SALTO do
    fóssil, do legado e da cor repetida ao primeiro tom livre não tem decisão
    de pé: é o que evita duas luzes iguais sem apagar nenhuma, e a
    A-LUZ-DO-CONTROLE-NUNCA-SAI-PRETA-01 o registra como o que é
    (29/09/2026). A barra é como ela sabe de quem é o controle — na mesa dela
    quatro DualSense são do MESMO modelo, e a luz os separa.

    AS PERGUNTAS DE COR SÃO PELO TOM, e não pelo byte (29/09/2026): o fóssil
    legado, a cor repetida e o global que cede perguntam a `_mesmo_tom`, e a
    resposta não depende do brilho de outra peça.

    **`mesa` já vem NA ORDEM que decide** (o número do controle, quando há
    um), e a ordem é o contrato: *"o segundo desloca para o tom vizinho"* são
    as palavras dela, e "primeiro" só tem definição estável se for o número.
    Quem chama ordena; aqui a regra é cega e determinista — a MESMA mesa
    devolve SEMPRE a mesma resposta, que é o que impede a barra de piscar
    (medido em 05/09/2026: um endereço com dois donos repintou a tela 80
    vezes em 80 tiques).

    ELA LÊ A PROCEDÊNCIA, E NÃO ADIVINHA. A primeira volta desta regra
    deslocava toda cor que fosse o número de outro, e isso **matou o
    broadcast dela**: `led.set {rgb:[0,255,0]}` sem `uniq` saía
    `[verde, vermelho, azul, rosa]`. Com a procedência gravada, o "Todos" é
    LIDO como "Todos" (`DO_BROADCAST`) e nunca se desloca — ver `_e_fossil`.

    AS DUAS VOLTAS, e a segunda é o que faltava na primeira versão:

    1. **quem tem identidade** — paleta, broadcast, escolha viva, legado
       honesto. O primeiro a pedir uma cor fica com ela; o fóssil vai para a
       cor do próprio número, e quem chega numa cor já tomada vai para o
       primeiro tom livre da paleta;
    2. **quem está no GLOBAL do perfil** — cor sem dono. Cede a quem tem
       identidade (era o buraco: um controle numerado em azul automático e
       outro caindo no azul global ficavam os dois `#0000FF`), mas **não cede
       à irmã que também está no global**: quatro controles na mesma cor
       global é o gesto "Todos" do perfil (D4), não uma colisão.

    O TOM LIVRE SAI NO BRILHO DA PEÇA E É LIVRE PELO TOM — 25/09/2026,
    A-BARRA-NAO-ESCURECE-AO-REAPLICAR-01. Medido na mesa de quatro real, com a
    paleta desligada: o fóssil do P3 ia para o azul CHEIO, `(0,0,255)`, ao
    lado do P1 azul a 82%, `(0,0,209)` — o byte estava livre, a cor não, e o
    brilho do P3 sumia. O tom da paleta agora é levado ao `brilho` da peça, e
    ele só está livre se nenhuma outra peça o acende em brilho nenhum
    (`_acende_o_tom`).

    Com as oito tomadas, **recusa**: devolve o que foi pedido em vez de
    girar. Rodízio com a mesa cheia troca a cor de todo mundo a cada tique,
    que é o defeito que esta função existe para não ter.

    Preto (`_APAGADA`) fica de fora nos dois sentidos: não é deslocado e não
    toma cor de ninguém — barra apagada é ausência de cor, não identidade.

    A METADE QUE NÃO MORA AQUI é a recusa no GESTO — *"mesmo que eu escolha
    cor X, meu amigo não pode escolher a mesma"*. Lá se sabe que o alvo é UM
    controle e a tela pode dizer de quem é a cor; ver
    `interface/pacotes/a04_iluminacao.py::_sem_repetir_a_cor_do_vizinho`.
    """
    numeros = _automaticas(mesa)
    tomadas: dict[RGB, str] = {}
    saida: dict[str, RGB] = {}
    do_global: list[PecaDaMesa] = []

    paleta = tuple(_PLAYER_SLOT_COLORS.values())
    # O QUE AS OUTRAS PEÇAS ACENDEM E NÃO VÃO LARGAR — conferência da
    # A-BARRA-NAO-ESCURECE-AO-REAPLICAR-01, 25/09/2026. `tomadas` só conhece
    # quem já passou na ordem, e o global só entra na segunda volta: sem a
    # paleta, o fóssil do P3 a 50% ia para o azul a 50% com o P1 no azul
    # GLOBAL a 82% ao lado, e o fóssil do P1 ia para o azul a 82% com o P4
    # escolhido azul a 50% logo atrás na ordem — o byte livre, o tom não. O
    # deslocado evita também o tom de toda peça que fica onde está (quem não
    # é fóssil); o fóssil larga a cor dele, e por isso não reserva nada.
    ficam: list[tuple[str, RGB]] = [
        (peca.uniq, peca.pedida) for peca in mesa
        if peca.pedida is not None and peca.pedida != _APAGADA
        and not _e_fossil(peca, numeros)
    ]

    def _tomado(acesa: RGB, tons: tuple[RGB, ...], uniq: str) -> bool:
        # O TOM, E NÃO O BYTE — 25/09/2026. O azul do P1 a 82% e o azul cheio
        # são bytes diferentes e a mesma cor; ver `_acende_o_tom`.
        acesas = [*tomadas, *(luz for dono, luz in ficam if dono != uniq)]
        if _ja_acesa(acesa, acesas):
            return True
        return any(
            _acende_o_tom(luz, tom)
            for luz in acesas
            for tom in tons
        )

    # A ESCOLHA NÃO CEDE À VIZINHANÇA, E A AUTOMÁTICA CEDE — conferência da
    # A-LUZ-DO-CONTROLE-NUNCA-SAI-PRETA-01, 29/09/2026. Com a vizinhança em
    # toda pergunta, o roxo da paleta escolhido para o P2 saía branco ao lado
    # do Galactic Purple P1 automático `(131, 0, 255)`: a tela não o recusa (a
    # casa do roxo não é a do plástico), e o daemon o deslocava calado. A cor
    # que alguém escolheu só cede ao TOM EXATO já tomado, que é o que o X da
    # tela recusa; a cor AUTOMÁTICA cede por vizinhança, e a do plástico cede
    # também à escolha de quem vem depois na ordem, porque a escolha fica.
    escolhas_que_ficam: list[tuple[str, RGB]] = [
        (peca.uniq, peca.pedida) for peca in mesa
        if peca.pedida is not None and peca.pedida != _APAGADA
        and peca.procedencia is not DA_PALETA and peca.procedencia is not DO_GLOBAL
        and not _e_fossil(peca, numeros)
    ]

    def _repetida(peca: PecaDaMesa) -> bool:
        assert peca.pedida is not None
        if peca.procedencia is not DA_PALETA:
            return _ja_acesa(peca.pedida, tomadas, vizinhanca=False)
        if _ja_acesa(peca.pedida, tomadas):
            return True
        if peca.do_plastico is None:
            return False
        return _ja_acesa(
            peca.pedida,
            (luz for dono, luz in escolhas_que_ficam if dono != peca.uniq),
        )

    def _primeiro_tom_livre(peca: PecaDaMesa) -> RGB | None:
        # A COR DO NÚMERO já chega no brilho da peça (é a automática, pela
        # mesma escala da saída); os tons da paleta chegam cheios e são
        # levados ao brilho dela — sem isso o fóssil do P3 saía em
        # (0,0,255) ao lado do P1 a (0,0,209). A-BARRA-NAO-ESCURECE-AO-REAPLICAR-01.
        candidatas: list[tuple[RGB, tuple[RGB, ...]]] = []
        # O PLÁSTICO PRIMEIRO (29/09/2026, D-2909-A-COR-AUTOMATICA-VEM-DO-PLASTICO):
        # o fóssil volta à cor automática, e ela é a do plástico quando ele
        # tem tom. Quem o perde para outra peça cai no número, e depois na
        # paleta, como antes.
        if peca.do_plastico is not None:
            candidatas.append((peca.do_plastico, ()))
        if peca.do_numero is not None:
            tons = tuple(t for t in paleta if _acende_o_tom(peca.do_numero, t))
            candidatas.append((peca.do_numero, tons))
        candidatas.extend((_na_escala(t, peca.brilho), (t,)) for t in paleta)
        for acesa, tons in candidatas:
            if acesa == _APAGADA:
                continue
            if not _tomado(acesa, tons, peca.uniq):
                return acesa
        return None  # as oito tomadas: recusa, não gira

    def _acomodar(peca: PecaDaMesa, pedida: RGB) -> None:
        nova = _primeiro_tom_livre(peca)
        if nova is None:
            tomadas.setdefault(pedida, peca.uniq)
            return
        saida[peca.uniq] = nova
        tomadas[nova] = peca.uniq

    for peca in mesa:
        if peca.pedida is None:
            continue
        saida[peca.uniq] = peca.pedida
        if peca.pedida == _APAGADA:
            continue
        if peca.procedencia is DO_GLOBAL:
            do_global.append(peca)
            continue
        if peca.procedencia is DO_BROADCAST:
            # O "Todos" dela. NUNCA se desloca — nem quando a cor já está
            # tomada, porque estar tomada é justamente o que ele pediu.
            tomadas.setdefault(peca.pedida, peca.uniq)
            continue
        if _e_fossil(peca, numeros) or _repetida(peca):
            _acomodar(peca, peca.pedida)
            continue
        tomadas.setdefault(peca.pedida, peca.uniq)

    for peca in do_global:
        pedida = peca.pedida
        if pedida is None or not _ja_acesa(pedida, tomadas):
            # Ninguém COM IDENTIDADE nessa cor: fica. Duas peças no mesmo
            # global não se deslocam — é o gesto "Todos" do perfil (D4).
            continue
        _acomodar(peca, pedida)
    return saida


def apply_led_settings(controller: IController, settings: LedSettings) -> None:
    """Aplica settings no controle.

    Escala o RGB pelo `brightness_level` antes de enviar — garante que perfis
    com brilho reduzido chegam ao hardware com a intensidade correta.

    Propaga os 5 Player LEDs via `controller.set_player_leds(settings.player_leds)`
    (BUG-PLAYER-LEDS-APPLY-01; armadilha A-06 fechada para player_leds).

    CORREÇÃO DATADA (13/08/2026) — o parágrafo que morava aqui afirmava que,
    sem esta propagação, perfis com `player_leds` no JSON eram carregados e
    salvos no draft "mas os bits nunca chegam ao controle". Isso é FALSO, e era
    o sintoma do BUG-PLAYER-LEDS-APPLY-01 descrito como se ele estivesse de pé.
    Os bits CHEGAM — por outro caminho, e este é o endereço dele. O texto sai em
    vez de ganhar nota ao lado porque um fato errado não é decisão medida:
    mantê-lo obrigaria a próxima pessoa a escolher entre duas afirmações.

    Quem acende os cinco pontinhos numa troca de perfil é `ProfileManager.apply`,
    que emite `player_leds` dentro do `OutputSpec` de `apply_output_defaults`
    (profiles/manager.py:605). O backend converte ali mesmo, em
    `_write_partial_output`: `mask = sum(1 << i for i, b in
    enumerate(out.player_leds) if b)` (core/backend_pydualsense.py:5558) — o
    MESMO layout que `player_bitmask` calcula neste arquivo. As duas conversões
    não divergem, e não divergirem é conferido por teste, não por leitura:
    `tests/unit/test_perfil_acende_os_pontinhos_do_jogador.py` troca de perfil e
    exige o bitmask na ponta.

    O que isto muda para quem lê: esta função continua correta e continua
    pública, mas NÃO é o caminho vivo. Ela é a forma "aplicar um `LedSettings`
    inteiro de uma vez"; o perfil chega ao aparelho pelo `OutputSpec`, que sabe
    dizer "não mexe neste campo" com `None` — e é dessa distinção que a trava
    manual por categoria depende.

    **Mic LED é intencionalmente preservado**: `settings.mic_led` NÃO é aplicado
    (AUDIT-FINDING-PROFILE-MIC-LED-RESET-01; A-06 variante "campo ausente em
    LedsConfig mas aplicado com default regride estado runtime"). Transições do
    LED do microfone seguem caminho explícito — botão físico via HotkeyManager,
    IPC dedicado via UDP MicLED / `led.mic_set` futuro — e jamais colateral de
    profile switch.
    """
    effective = settings.apply_brightness(settings.brightness_level)
    controller.set_led(effective.lightbar)
    controller.set_player_leds(settings.player_leds)


def off() -> LedSettings:
    return LedSettings(lightbar=(0, 0, 0))


#: O PRETO, escrito uma vez. Ele é o default do `LedsConfig.lightbar` do
#: esquema, e é isso que faz dele o valor de QUEM NÃO OPINOU.
PRETO: RGB = (0, 0, 0)


def cor_escolhida(rgb: RGB | None) -> RGB | None:
    """A cor que a pessoa escolheu — ``None`` quando não houve escolha.

    **O PRETO É BANIDO COMO COR — 22/09/2026, ordem dela:** *"vamos banir esse
    preto de aparecer independente do controle tambem"*. <!-- noqa-acento: citação literal dela -->

    A QUEIXA QUE O REVELOU, e ela é de um controle só: *"pq o lightbar do
    starlight blue sempre desliga após conectar? mesmo o perfil atual não
    mandando ele desligar"*. O perfil MANDAVA: a peça daquele controle tinha
    `leds.lightbar: [0,0,0]`, escrita por um "Salvar Perfil" das 13:53 daquele
    dia, quando a cor lida veio vazia. Medido no mesmo disco: **sete dos 29
    perfis dela** guardam o preto na seção GLOBAL — neles, abrir o jogo apaga
    a barra dos QUATRO.

    A CAUSA É DE FORMA, e está no esquema: `LedsConfig.lightbar` nasce
    `(0, 0, 0)`, então *"não opinou"* e *"quero apagado"* são o mesmo byte. Com
    um valor só para as duas coisas, a leitura honesta é a que não apaga nada:
    preto vira `None`, e quem decide a cor passa a ser a paleta automática do
    número (`cores_sem_colisao`).

    **APAGAR A BARRA CONTINUA POSSÍVEL, e por outro caminho:** o brilho. O
    `lightbar_brightness` em 0.0 zera os três canais DEPOIS desta função
    (`LedSettings.apply_brightness`), e esse é um campo que só a mão dela move.
    Banir a cor preta não tira dela o apagar; tira do produto o direito de
    apagar sozinho.
    """
    if rgb is None:
        return None
    return None if tuple(rgb) == PRETO else rgb


def hex_to_rgb(hex_str: str) -> RGB:
    """Converte '#RRGGBB' ou 'RRGGBB' para tupla (r, g, b)."""
    s = hex_str.strip().lstrip("#")
    if len(s) != 6:
        raise ValueError(f"hex_to_rgb espera formato RRGGBB, recebeu: {hex_str!r}")
    try:
        r = int(s[0:2], 16)
        g = int(s[2:4], 16)
        b = int(s[4:6], 16)
    except ValueError as exc:
        raise ValueError(f"hex_to_rgb: componente não numérico em {hex_str!r}") from exc
    return (r, g, b)


__all__ = [
    "BRILHOS_DAS_LUZES",
    "BRILHO_DAS_LUZES_PADRAO",
    "DA_MAO",
    "DA_PALETA",
    "DO_BROADCAST",
    "DO_GLOBAL",
    "LEGADO",
    "PISO_DO_BRILHO",
    "PRETO",
    "RGB",
    "LedSettings",
    "PecaDaMesa",
    "apply_led_settings",
    "cor_automatica",
    "cor_escolhida",
    "cores_sem_colisao",
    "degrau_do_brilho_das_luzes",
    "fator_do_brilho",
    "fosseis",
    "hex_to_rgb",
    "off",
    "player_bitmask",
    "player_led_pattern",
    "player_slot_color",
    "reescalar",
]
