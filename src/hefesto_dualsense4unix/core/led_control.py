"""Controle de LEDs do DualSense.

API de alto nível: lightbar RGB, 5 LEDs de jogador (bitmask) e LED do microfone.

Cobertura atual:
- Lightbar RGB: `IController.set_led` (implementado).
- LED do microfone: `IController.set_mic_led` (implementado — INFRA-SET-MIC-LED-01).
  **Não é aplicado pelo perfil**: mic_led é tratado como estado
  runtime puro (ver AUDIT-FINDING-PROFILE-MIC-LED-RESET-01 e armadilha A-06).
  Transições de mic_led vêm do botão físico ou de handlers IPC dedicados
  (`udp_server` MicLED, `HotkeyManager` mic_btn), nunca de profile switch.
- Player LEDs: `IController.set_player_leds` (implementado — player bitmask).
  Player LEDs continuam com API básica de bitmask; efeitos avançados (animação)
  dependem de sprint futura.
"""
from __future__ import annotations

import colorsys
from collections.abc import Iterable
from dataclasses import dataclass

RGB = tuple[int, int, int]


PISO_DO_BRILHO = 0.20


def fator_do_brilho(brilho: float) -> float:
    """O fator que multiplica o RGB no `brilho` do trilho — a conta do piso."""
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
    - `mic_led`: **reservado / no-op na aplicação do perfil**. Preservado no
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
    """Converte 5 flags em bitmask 0-31 (mesmo layout usado pelo protocolo DSX)."""
    value = 0
    for idx, on in enumerate(leds):
        if on:
            value |= 1 << idx
    return value


#: FEAT-COOP-PLAYER-LED-01 / COR-03 — padrões canônicos do DualSense para os 5
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

_PLAYER_LED_OVERFLOW = (True, False, True, True, False)


#: O BRILHO DAS LUZES DE NÚMERO — `D-2409-AS-LUZES-DE-NUMERO-TEM-TRES-BRILHOS`,
BRILHOS_DAS_LUZES: dict[str, int] = {"fraco": 2, "medio": 1, "forte": 0}  # noqa-acento: chave ASCII

BRILHO_DAS_LUZES_PADRAO = "fraco"


def degrau_do_brilho_das_luzes(nome: str | None) -> int:
    """O degrau do firmware (`common[42]`) para a palavra do perfil."""
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


#: `lightbar_brightness` do perfil é o provider (D11), pelo mesmo caminho do
_PLAYER_SLOT_COLORS: dict[int, RGB] = {
    1: (0, 0, 255),
    2: (255, 0, 0),
    3: (0, 255, 0),
    4: (255, 0, 128),
    5: (255, 255, 0),
    6: (0, 255, 255),
    7: (255, 128, 0),
    8: (128, 0, 255),
}


def cor_automatica(numero: int | None, tom_do_plastico: RGB | None) -> RGB:
    """A cor AUTOMÁTICA de um controle: a do plástico, e a do número sem ela."""
    if tom_do_plastico is not None:
        return tom_do_plastico
    return player_slot_color(numero if numero is not None else 0)


def player_slot_color(slot: int) -> RGB:
    """Cor canônica de lightbar do controle `slot` (1=azul, 2=vermelho, 3=verde, 4=rosa)."""
    return _PLAYER_SLOT_COLORS.get(slot, (255, 255, 255))


DA_PALETA = "paleta"
DO_BROADCAST = "todos"
DO_GLOBAL = "global"
DA_MAO = "mao"  # noqa-acento: VALOR de carimbo, legível por máquina — a mesma escolha de `sim`/`nao` desta casa
LEGADO = "legado"

_APAGADA: RGB = (0, 0, 0)


@dataclass(frozen=True)
class PecaDaMesa:
    """Uma peça na mesa da regra de cor única."""

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
    """A cor desta peça é o número de ontem congelado, e não uma escolha?"""
    if isinstance(peca.procedencia, bool):
        return False
    if isinstance(peca.procedencia, int):
        return peca.numero is None or peca.procedencia != peca.numero
    if peca.procedencia is not LEGADO or peca.pedida is None:
        return False
    proprias = (peca.do_plastico, peca.do_numero)
    if any(p is not None and _mesmo_tom(peca.pedida, p, vizinhanca=False)
           for p in proprias):
        return False
    return any(_mesmo_tom(peca.pedida, numero, vizinhanca=False) for numero in numeros)


def _acende_o_tom(acesa: RGB, tom: RGB) -> bool:
    """A luz `acesa` é o `tom` em algum brilho? — a pergunta do TOM, e não do byte."""
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
    return _escala_crua(tom, (baixo + alto) / 2) == acesa


def _mesmo_tom(a: RGB, b: RGB, *, vizinhanca: bool = True) -> bool:
    """As duas luzes são o MESMO TOM, cada uma no seu brilho? — o dono único."""
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
    return _vizinhos(a, b)


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
    """Os `uniq` da mesa cuja cor pedida é FÓSSIL — a pergunta da tela e do daemon."""
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
    """A luz `acesa`, que está no brilho `de`, levada ao brilho `para`."""
    if de > 0.0:
        candidatos = dict.fromkeys((*_PLAYER_SLOT_COLORS.values(), *extras))
        tons = [t for t in candidatos if _na_escala(t, de) == acesa]
        if len(tons) == 1:
            return _na_escala(tons[0], para)
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
    ficam: list[tuple[str, RGB]] = [
        (peca.uniq, peca.pedida) for peca in mesa
        if peca.pedida is not None and peca.pedida != _APAGADA
        and not _e_fossil(peca, numeros)
    ]

    def _tomado(acesa: RGB, tons: tuple[RGB, ...], uniq: str) -> bool:
        acesas = [*tomadas, *(luz for dono, luz in ficam if dono != uniq)]
        if _ja_acesa(acesa, acesas):
            return True
        return any(
            _acende_o_tom(luz, tom)
            for luz in acesas
            for tom in tons
        )

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
        candidatas: list[tuple[RGB, tuple[RGB, ...]]] = []
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
        return None

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
            tomadas.setdefault(peca.pedida, peca.uniq)
            continue
        if _e_fossil(peca, numeros) or _repetida(peca):
            _acomodar(peca, peca.pedida)
            continue
        tomadas.setdefault(peca.pedida, peca.uniq)

    for peca in do_global:
        pedida = peca.pedida
        if pedida is None or not _ja_acesa(pedida, tomadas):
            continue
        _acomodar(peca, pedida)
    return saida


def off() -> LedSettings:
    return LedSettings(lightbar=(0, 0, 0))


PRETO: RGB = (0, 0, 0)


def cor_escolhida(rgb: RGB | None) -> RGB | None:
    """A cor que a pessoa escolheu — ``None`` quando não houve escolha.

    **O PRETO É BANIDO COMO COR — 22/09/2026, ordem dela:** *"vamos banir esse
    preto de aparecer independente do controle tambem"*. <!-- noqa-acento: citação literal -->

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
