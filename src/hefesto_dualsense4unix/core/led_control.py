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


#: Uma peça na mesa da regra de cor única: o endereço, a cor que ela PEDE e a
#: cor do NÚMERO dela (a automática, já escalada — ou None quando ela não tem
#: número: ausente da mesa, vpad, ou key sem MAC de 12 hex).
PecaDaMesa = tuple[str, "RGB | None", "RGB | None"]

#: Preto é AUSÊNCIA de cor, não identidade. Uma barra apagada não colide com
#: outra apagada — "as duas estão desligadas" é uma resposta, e deslocar uma
#: delas para roxo acenderia um controle que a usuária mandou apagar.
_APAGADA: RGB = (0, 0, 0)


def cores_sem_colisao(mesa: list[PecaDaMesa]) -> dict[str, RGB]:
    """Resolve a mesa inteira de modo que duas peças nunca fiquem da mesma cor.

    `D-DUAS-PECAS-NUNCA-TEM-A-MESMA-COR` (26/08/2026), decidida por ela como
    **REGRA DO PRODUTO, SEMPRE**: *"duas coisas que precisam ser
    distinguíveis não podem colidir"*. A barra é como ela sabe de quem é o
    controle — na mesa dela dois DualSense são do MESMO modelo, e a luz é a
    única coisa que os separa.

    **`mesa` já vem NA ORDEM que decide** (o número do controle, quando há
    um), e a ordem é o contrato: *"o segundo desloca para o tom vizinho"* são
    as palavras dela, e "primeiro" só tem definição estável se for o número.
    Quem chama ordena; aqui a regra é cega e determinista — a MESMA mesa
    devolve SEMPRE a mesma resposta, que é o que impede a barra de piscar
    (medido em 05/09/2026: um endereço com dois donos repintou a tela 80
    vezes em 80 tiques).

    **DESLOCA SÓ O QUE CONSEGUE PROVAR QUE É FÓSSIL**, e o critério é o que a
    medição de 08/09/2026 achou no disco dela: *uma cor que é exatamente a do
    NÚMERO DE OUTRO controle da mesa não é uma escolha — é o número de ontem
    congelado no arquivo*. A prova está nos ranks 2 e 4 dela, que guardavam as
    cores dos slots **1 e 2**: o produto gravou o lugar de cada um num dia em
    que eles eram outros, e a mesa girou.

    A regra, então:

    1. quem pede a cor do PRÓPRIO número fica com ela — ela é dele;
    2. quem pede a cor do número de OUTRO da mesa é deslocado: para a cor do
       próprio número se estiver livre, senão para a primeira livre da paleta;
    3. com as oito tomadas, **recusa**: devolve o que foi pedido em vez de
       girar. Rodízio com a mesa cheia troca a cor de todo mundo a cada
       tique, que é o defeito que esta função existe para não ter;
    4. **cor que não é de número nenhum da mesa NÃO se toca.**

    A LINHA 4 É O LIMITE HONESTO DESTE LUGAR, e ela custou três testes
    vermelhos até ficar escrita. O `led.set` sem `uniq` é um BROADCAST: ele
    grava a MESMA cor no override de todos, de propósito — *"pinta os dois de
    verde"*. No disco isso é indistinguível de duas escolhas independentes que
    calharam de colidir, porque `ControllerOverrides.leds` não guarda
    procedência. Um resolvedor que deslocasse toda repetição desfaria o
    broadcast dela no tique seguinte.

    Então a metade que falta — *"mesmo que eu escolha cor X, meu amigo não pode
    escolher a mesma"* — **não mora aqui**: ela mora no GESTO, onde se sabe se
    o alvo é UM controle ou todos, e onde a tela pode dizer o que fez (é o que
    `D-DUAS-PECAS-NUNCA-TEM-A-MESMA-COR` pede com todas as letras: *"o segundo
    desloca para o tom vizinho e a tela diz o que fez"*). Ver
    `interface/pacotes/a04_iluminacao.py::_sem_repetir_a_cor_do_vizinho`.

    Preto (`_APAGADA`) fica de fora nos dois sentidos: não é deslocado e não
    toma cor de ninguém — barra apagada é ausência de cor, não identidade.

    Rodada na mesa dela, esta regra devolve as quatro cores do número: o rank 1
    pede azul, que é o dele, e fica; o rank 2 pede o MESMO azul, que é o número
    do rank 1, e volta para o vermelho do dele; o rank 4 pede esse vermelho,
    que é o número do rank 2, e volta para o rosa do dele. Sem que uma linha do
    disco dela seja apagada: o override só se desloca quando usa o número de
    outro, então uma cor escolhida de verdade sobrevive.
    """
    numeros = {
        do_numero for _, _, do_numero in mesa
        if do_numero is not None and do_numero != _APAGADA
    }
    tomadas: dict[RGB, str] = {}
    saida: dict[str, RGB] = {}
    for uniq, pedida, do_numero in mesa:
        if pedida is None:
            continue
        saida[uniq] = pedida
        if pedida == _APAGADA:
            continue
        # DONO POR DIREITO: a cor do próprio número, e só enquanto ninguém a
        # tomou antes. O "enquanto" não é zelo — `player_slot_color` devolve
        # BRANCO para todo slot ≥ 9, então dois controles em 9 e 10 têm o
        # MESMO "próprio número". Sem esta metade, os dois seriam donos e os
        # dois ficariam brancos, que é o buraco que esta regra veio fechar.
        e_dono = pedida == do_numero and pedida not in tomadas
        # As TRÊS condições do fóssil, e as três têm de valer juntas: a cor já
        # está tomada por outro (colisão de verdade, não hipótese), quem pede
        # não é o dono dela, e ela É a do número de alguém na mesa — o que a
        # torna provável fóssil em vez de escolha.
        e_fossil = pedida in tomadas and not e_dono and pedida in numeros
        if not e_fossil:
            tomadas.setdefault(pedida, uniq)
            continue
        for candidata in (do_numero, *_PLAYER_SLOT_COLORS.values()):
            if candidata is None or candidata == _APAGADA:
                continue
            if candidata not in tomadas:
                saida[uniq] = candidata
                tomadas[candidata] = uniq
                break
        else:  # as oito tomadas: recusa, não gira
            tomadas.setdefault(pedida, uniq)
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
    (profiles/manager.py:392). O backend converte ali mesmo, em
    `_write_partial_output`: `mask = sum(1 << i for i, b in
    enumerate(out.player_leds) if b)` (core/backend_pydualsense.py:2801) — o
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
    "RGB",
    "LedSettings",
    "PecaDaMesa",
    "apply_led_settings",
    "cores_sem_colisao",
    "hex_to_rgb",
    "off",
    "player_bitmask",
    "player_led_pattern",
    "player_slot_color",
]
