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

from dataclasses import dataclass

from hefesto_dualsense4unix.core.controller import IController

RGB = tuple[int, int, int]


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

        ``level`` é multiplicador linear. Valores fora de [0.0, 1.0] são
        tolerados e acabam truncados pelo clamp por canal; isso cobre
        futura curva de resposta não-linear sem quebrar o contrato atual.
        """
        r, g, b = self.lightbar
        scaled: RGB = (
            max(0, min(255, int(r * level))),
            max(0, min(255, int(g * level))),
            max(0, min(255, int(b * level))),
        )
        return LedSettings(
            lightbar=scaled,
            brightness_level=self.brightness_level,
            player_leds=self.player_leds,
            mic_led=self.mic_led,
        )


def player_bitmask(leds: tuple[bool, bool, bool, bool, bool]) -> int:
    """Converte 5 flags em bitmask 0-31 (mesmo layout usado pelo protocolo DSX)."""
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
    """

    uniq: str
    pedida: RGB | None
    do_numero: RGB | None
    procedencia: object = LEGADO
    numero: int | None = None
    brilho: float | None = None


def _e_fossil(peca: PecaDaMesa, numeros: set[RGB]) -> bool:
    """A cor desta peça é o número de ontem congelado, e não uma escolha?

    As três respostas, e as três se LEEM — nenhuma se adivinha:

    * **procedência inteira** — a cor foi escolhida para um número. É fóssil
      exatamente quando esse número não é mais o dela. É o caso medido na
      mesa dela em 08/09/2026: os ranks 2 e 4 guardavam as cores dos slots 1
      e 2, escolhidas num dia em que eles eram outros;
    * **`LEGADO`** — override do disco anterior ao campo. Aqui, e SÓ aqui, a
      regra prova pela FORMA: uma cor que é exatamente a do número de OUTRO
      da mesa (e não a do próprio) é fóssil. Perfil antigo com uma escolha de
      verdade — um roxo que não é número de ninguém — sobrevive à migração;
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
    return peca.pedida in numeros and peca.pedida != peca.do_numero


def _acende_o_tom(acesa: RGB, tom: RGB) -> bool:
    """A luz `acesa` é o `tom` em algum brilho? — a pergunta do TOM, e não do byte.

    A-BARRA-NAO-ESCURECE-AO-REAPLICAR-01, 25/09/2026: o azul do P1 a 82% é
    `(0,0,209)` e o azul cheio é `(0,0,255)` — bytes diferentes, a MESMA cor
    na mão de quem joga. A régua de cor única comparava bytes, e o fóssil do
    P3 era deslocado para o azul cheio ao lado do P1 azul.

    A CONTA É A DO DONO DA ESCALA (`LedSettings.apply_brightness`: cada canal
    vezes o brilho, truncado), e a resposta é exata, sem tolerância: existe um
    brilho `b` em [0, 1] que leva o `tom` à `acesa` quando os intervalos de
    `b` de cada canal se cruzam. O brilho do meio do cruzamento é conferido
    pela própria conta, para a borda de ponto flutuante não mentir.
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
    return LedSettings(lightbar=tom).apply_brightness((baixo + alto) / 2).lightbar == acesa


def _na_escala(tom: RGB, brilho: float | None) -> RGB:
    """O `tom` aceso no `brilho` da peça — cheio quando o brilho não é sabido."""
    if brilho is None:
        return tom
    return LedSettings(lightbar=tom).apply_brightness(brilho).lightbar


def reescalar(acesa: RGB, de: float, para: float) -> RGB:
    """A luz `acesa`, que está no brilho `de`, levada ao brilho `para`.

    O BRILHO ENTRA UMA VEZ SÓ — A-BARRA-NAO-ESCURECE-AO-REAPLICAR-01,
    25/09/2026. O brilho por controle é um fator sobre a cor que já chegou no
    brilho do perfil (`backend._scaled_led`), e a conta em dois passos trunca
    duas vezes: o P1 a 60% saía `(0,0,152)` do perfil e `(0,0,153)` do trilho,
    e com o perfil a 1% e o controle a 100% o azul voltava `(0,0,200)`. Quando
    a luz é um tom da paleta NAQUELE brilho — é a automática, e é o caso de
    todo controle que nasce sem cor escolhida —, o tom é levado ao brilho novo
    pela conta do dono, uma vez só, e a resposta é a do trilho. Fora da paleta
    (o global dela, `#2850B4`) não há tom a provar, e vale a razão, como antes.
    O tom tem de ser ÚNICO: abaixo de 1% o vermelho, o rosa e o laranja acendem
    o mesmo `(1,0,0)`, e escolher um deles seria trocar a cor pelo brilho.
    """
    if de > 0.0:
        tons = [t for t in _PLAYER_SLOT_COLORS.values() if _na_escala(t, de) == acesa]
        if len(tons) == 1:
            return _na_escala(tons[0], para)
    fator = para / de if de > 0.0 else 0.0
    return LedSettings(lightbar=acesa).apply_brightness(fator).lightbar


def cores_sem_colisao(mesa: list[PecaDaMesa]) -> dict[str, RGB]:
    """Resolve a mesa inteira de modo que duas peças nunca fiquem da mesma cor.

    `D-DUAS-PECAS-NUNCA-TEM-A-MESMA-COR` (26/08/2026), decidida por ela como
    **REGRA DO PRODUTO, SEMPRE**: *"duas coisas que precisam ser
    distinguíveis não podem colidir"*. A barra é como ela sabe de quem é o
    controle — na mesa dela quatro DualSense são do MESMO modelo, e a luz é a
    única coisa que os separa.

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
    numeros = {
        peca.do_numero for peca in mesa
        if peca.do_numero is not None and peca.do_numero != _APAGADA
    }
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
        if acesa in acesas:
            return True
        return any(
            _acende_o_tom(luz, tom)
            for luz in acesas
            for tom in tons
        )

    def _primeiro_tom_livre(peca: PecaDaMesa) -> RGB | None:
        # A COR DO NÚMERO já chega no brilho da peça (é a automática, pela
        # mesma escala da saída); os tons da paleta chegam cheios e são
        # levados ao brilho dela — sem isso o fóssil do P3 saía em
        # (0,0,255) ao lado do P1 a (0,0,209). A-BARRA-NAO-ESCURECE-AO-REAPLICAR-01.
        candidatas: list[tuple[RGB, tuple[RGB, ...]]] = []
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
        if _e_fossil(peca, numeros) or peca.pedida in tomadas:
            _acomodar(peca, peca.pedida)
            continue
        tomadas.setdefault(peca.pedida, peca.uniq)

    for peca in do_global:
        pedida = peca.pedida
        if pedida is None or pedida not in tomadas:
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
    (profiles/manager.py:358). O backend converte ali mesmo, em
    `_write_partial_output`: `mask = sum(1 << i for i, b in
    enumerate(out.player_leds) if b)` (core/backend_pydualsense.py:5031) — o
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
    "PRETO",
    "RGB",
    "LedSettings",
    "PecaDaMesa",
    "apply_led_settings",
    "cor_escolhida",
    "cores_sem_colisao",
    "degrau_do_brilho_das_luzes",
    "hex_to_rgb",
    "off",
    "player_bitmask",
    "player_led_pattern",
    "player_slot_color",
    "reescalar",
]
